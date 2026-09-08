# program-picker

You browse the bug-bounty platforms yourself, jot a few facts about each program
you're weighing into a small JSON file, and this tool ranks them **against your
priorities** and tells you which one to hunt first — and *why*.

It does **not** discover programs for you. No platform (HackerOne, Bugcrowd,
Intigriti, YesWeHack, Immunefi, Code4rena) exposes a clean public API for hunter
discovery, and scraping them is fragile and often against ToS. This tool does the
part a tool can do reliably, and the part that's actually the bottleneck: turning
"here are 6 candidates" into "start with this one, because ...".

## The idea

Every criterion is **toggle-on/off and re-weighted** — at the top of the script
or on the command line. Turn off what you don't care about right now; scoring
uses only what's left on. Weights don't need to add up to anything; they're
auto-normalised.

Default criteria (highest weight first — tuned to "criticals live in fresh code"):

| Criterion   | What it rewards                                   | Default |
|-------------|---------------------------------------------------|---------|
| `fresh`     | fewer prior audits, newer program                 | 30 |
| `low_comp`  | fewer reports / hunters (lower dup risk)          | 25 |
| `reward`    | the Medium/High ladder, not just the max headline | 20 |
| `skill_fit` | your edge per chain (Clarity rare → highest)      | 15 |
| `payout`    | KYC-free + fast payout                            | 10 |

## Install

No dependencies — pure Python 3 (standard library only), nothing to pip install. Just clone:

    git clone https://github.com/mirahahmed3690/program-picker
    cd program-picker

Python 3.8+ is all you need.


## Usage

```bash
python3 program_picker.py --example > programs.json   # get the input format
# ...edit programs.json with the candidates you're weighing...
python3 program_picker.py programs.json

# reward matters most to you today
python3 program_picker.py programs.json --weight reward=50

# ignore chain and payout for now
python3 program_picker.py programs.json --off skill_fit,payout
```

## Input format

A JSON list. Every field is optional — a missing field scores neutral for that
axis, so fill in what your PDF/screenshots actually show:

```json
[
  {
    "name": "Zest Protocol V2", "platform": "immunefi", "chain": "clarity",
    "audits": 4, "age_days": 240, "reports": 0, "hunters": 5,
    "max_reward": 100000, "med_reward": 0, "kyc": false, "fast_payout": false
  }
]
```

| Field | Meaning |
|---|---|
| `chain` | evm / solidity / solana / rust / clarity / stacks / web2 |
| `audits` | prior audits (0 = freshest) |
| `age_days` | how long it's been live |
| `reports` / `hunters` | competition proxy |
| `max_reward` / `med_reward` | reward ladder (Medium ≈ realistic first bug) |
| `kyc` / `fast_payout` | your payout rails |

## Output

A ranked list with a 0–100 score, the per-criterion breakdown behind each score,
and a "start with X" pick. It ranks *your* candidates by *your* weights — it does
not verify the numbers; you enter them, you own the judgement.

## License

MIT — see [LICENSE](LICENSE).

---

Built by [MIRAZ AHMED](https://github.com/mirahahmed3690) — security researcher (EVM · Solana · Clarity + web app security).
