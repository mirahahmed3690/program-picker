#!/usr/bin/env python3
"""
program-picker
==============
You browse the bug-bounty platforms (HackerOne, Bugcrowd, Intigriti, YesWeHack,
Immunefi, Code4rena, ...), jot a few facts about each program you're considering
into a simple file, and this tool ranks them against YOUR priorities and tells
you which one to hunt — and why.

It does NOT discover programs for you (no platform exposes a clean public API for
that, and scraping them is fragile + often against ToS). It does the part a tool
can do reliably and that is the real bottleneck: turning "here are 6 candidates"
into "hunt this one first, because ..."

Every criterion can be toggled on/off and re-weighted — at the top of this file,
or on the command line. Turn off what you don't care about right now; the score
uses only the criteria left on.

Author: MIRAZ AHMED  (https://github.com/mirahahmed3690)
License: MIT
"""

import argparse
import json
import sys

# ─────────────────────────────────────────────────────────────────────────────
#  CONFIG  —  edit freely. `on`: include this criterion. `weight`: its importance.
#  Only criteria with on=True count; weights are auto-normalised, so you don't
#  have to make them add up to 100.
# ─────────────────────────────────────────────────────────────────────────────
CRITERIA = {
    # the #1 lesson: criticals live in fresh / lightly-audited code
    "fresh":       {"on": True,  "weight": 30},
    # fewer hunters / reports = lower duplicate risk
    "low_comp":    {"on": True,  "weight": 25},
    # first realistic payout is Medium/High — judge the whole ladder, not max
    "reward":      {"on": True,  "weight": 20},
    # your edge: rare skill = thinner competition
    "skill_fit":   {"on": True,  "weight": 15},
    # rails: no KYC + fast payout is a plus
    "payout":      {"on": True,  "weight": 10},
}

# how much you rate each chain/skill (0..1). Clarity rare -> highest by default.
SKILL_FIT = {
    "clarity": 1.0, "stacks": 1.0,
    "solana": 0.8, "rust": 0.8,
    "evm": 0.6, "solidity": 0.6,
    "web2": 0.7, "web": 0.7,
}

# ─────────────────────────────────────────────────────────────────────────────
#  Per-program input fields (all optional; missing = neutral 0.5 for that axis):
#    name        str
#    platform    str   (hackerone/bugcrowd/intigriti/yeswehack/immunefi/code4rena)
#    chain       str   (evm/solidity/solana/rust/clarity/stacks/web2)
#    audits      int   number of prior audits (0 = freshest)
#    age_days    int   how long the program/contest has been live
#    reports     int   resolved reports / findings so far (competition proxy)
#    hunters     int   researchers on it (competition proxy)
#    max_reward  num   top payout (USD)
#    med_reward  num   Medium-tier payout (USD)  ← often the realistic first bug
#    kyc         bool  true if KYC required
#    fast_payout bool  true if pays fast / has a fast-payment badge
# ─────────────────────────────────────────────────────────────────────────────


def clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def score_fresh(p):
    # fewer audits and younger = fresher = better
    a = p.get("audits")
    age = p.get("age_days")
    if a is None and age is None:
        return None
    s = []
    if a is not None:
        s.append(clamp(1.0 - a / 6.0))          # 0 audits->1.0 ; 6+ ->0
    if age is not None:
        s.append(clamp(1.0 - age / 365.0))      # brand new->~1 ; 1yr+ ->0
    return sum(s) / len(s)


def score_low_comp(p):
    r = p.get("reports")
    h = p.get("hunters")
    if r is None and h is None:
        return None
    s = []
    if r is not None:
        s.append(clamp(1.0 - r / 300.0))        # 0 reports->1 ; 300+ ->0
    if h is not None:
        s.append(clamp(1.0 - h / 150.0))
    return sum(s) / len(s)


def score_reward(p):
    med = p.get("med_reward")
    mx = p.get("max_reward")
    if med is None and mx is None:
        return None
    s = []
    if med is not None:
        s.append(clamp(med / 25000.0))          # $25k medium -> full marks
    if mx is not None:
        s.append(clamp(mx / 200000.0))          # $200k max -> full marks
    return sum(s) / len(s)


def score_skill(p):
    ch = str(p.get("chain", "")).lower()
    if not ch:
        return None
    return SKILL_FIT.get(ch, 0.5)


def score_payout(p):
    kyc = p.get("kyc")
    fast = p.get("fast_payout")
    if kyc is None and fast is None:
        return None
    s = 0.5
    if kyc is not None:
        s = 1.0 if not kyc else 0.4
    if fast:
        s = min(1.0, s + 0.3)
    return s


SCORERS = {
    "fresh": score_fresh, "low_comp": score_low_comp,
    "reward": score_reward, "skill_fit": score_skill, "payout": score_payout,
}

LABELS = {
    "fresh": "fresh/low-audit", "low_comp": "low competition",
    "reward": "reward ladder", "skill_fit": "skill fit", "payout": "payout/KYC",
}


def active_weights(criteria):
    active = {k: v["weight"] for k, v in criteria.items() if v.get("on")}
    total = sum(active.values()) or 1
    return {k: w / total for k, w in active.items()}


def evaluate(program, criteria):
    weights = active_weights(criteria)
    parts, total = {}, 0.0
    for key, w in weights.items():
        raw = SCORERS[key](program)
        val = 0.5 if raw is None else raw        # missing data = neutral
        parts[key] = {"raw": val, "missing": raw is None, "contrib": val * w}
        total += val * w
    return round(total * 100, 1), parts


def reason_line(parts):
    # rank the criteria by contribution, describe the top drivers
    ranked = sorted(parts.items(), key=lambda kv: kv[1]["contrib"], reverse=True)
    bits = []
    for k, v in ranked:
        tag = LABELS[k]
        note = "?" if v["missing"] else f"{int(v['raw']*100)}%"
        bits.append(f"{tag} {note}")
    return " · ".join(bits)


def load_programs(path):
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, dict) and "programs" in data:
        data = data["programs"]
    if not isinstance(data, list):
        sys.exit("input must be a JSON list of programs (or {\"programs\":[...]})")
    return data


def apply_cli_overrides(criteria, off, on, weights):
    for k in off:
        if k in criteria:
            criteria[k]["on"] = False
    for k in on:
        if k in criteria:
            criteria[k]["on"] = True
    for pair in weights:
        if "=" in pair:
            k, val = pair.split("=", 1)
            if k in criteria:
                try:
                    criteria[k]["weight"] = float(val)
                    criteria[k]["on"] = True
                except ValueError:
                    pass
    return criteria


def main():
    ap = argparse.ArgumentParser(
        description="Rank bug-bounty programs against your priorities.")
    ap.add_argument("input", nargs="?", help="programs JSON file")
    ap.add_argument("--off", default="", help="comma-list criteria to turn OFF "
                    "(fresh,low_comp,reward,skill_fit,payout)")
    ap.add_argument("--on", default="", help="comma-list criteria to turn ON")
    ap.add_argument("--weight", action="append", default=[],
                    help="override a weight, e.g. --weight reward=40 (repeatable)")
    ap.add_argument("--example", action="store_true",
                    help="print an example input file and exit")
    args = ap.parse_args()

    if args.example:
        print(EXAMPLE)
        return
    if not args.input:
        ap.error("give a programs JSON file (or --example to see the format)")

    crit = json.loads(json.dumps(CRITERIA))  # deep copy
    crit = apply_cli_overrides(
        crit,
        [x for x in args.off.split(",") if x],
        [x for x in args.on.split(",") if x],
        args.weight,
    )

    active = [k for k, v in crit.items() if v["on"]]
    w = active_weights(crit)
    print("active criteria (normalised weight):")
    for k in active:
        print(f"  {LABELS[k]:<18} {w[k]*100:4.0f}%")
    print()

    programs = load_programs(args.input)
    ranked = []
    for p in programs:
        sc, parts = evaluate(p, crit)
        ranked.append((sc, p, parts))
    ranked.sort(key=lambda t: t[0], reverse=True)

    print("=" * 66)
    for i, (sc, p, parts) in enumerate(ranked, 1):
        star = " ⭐" if i == 1 else ""
        name = p.get("name", "?")
        plat = p.get("platform", "")
        chain = p.get("chain", "")
        print(f"{i}. [{sc:5.1f}] {name}{star}   ({plat} · {chain})")
        print(f"        {reason_line(parts)}")
    print("=" * 66)
    if ranked:
        best = ranked[0][1]
        print(f"\n→ start with: {best.get('name','?')}  "
              f"(score {ranked[0][0]}, {len(active)} criteria on)")
    print("\nnote: this ranks YOUR candidates by YOUR weights. it does not verify "
          "the data — you enter it, you own the judgement.")


EXAMPLE = json.dumps([
    {"name": "Zest Protocol V2", "platform": "immunefi", "chain": "clarity",
     "audits": 4, "age_days": 240, "reports": 0, "hunters": 5,
     "max_reward": 100000, "med_reward": 0, "kyc": False, "fast_payout": False},
    {"name": "Some Fresh Contest", "platform": "code4rena", "chain": "solidity",
     "audits": 0, "age_days": 4, "reports": 2, "hunters": 20,
     "max_reward": 100000, "med_reward": 5000, "kyc": False, "fast_payout": False},
    {"name": "Mature Web2 BBP", "platform": "hackerone", "chain": "web2",
     "audits": 0, "age_days": 900, "reports": 400, "hunters": 300,
     "max_reward": 15000, "med_reward": 1500, "kyc": False, "fast_payout": True},
], indent=2)


if __name__ == "__main__":
    main()
