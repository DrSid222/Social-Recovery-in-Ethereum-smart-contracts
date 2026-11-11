# Final design against Argent 2.1: any two keys replace the third, 24h Phase 1, only S1 and S2 lock

Generated 2026-10-31 from `model.py` (`two_of_three=True, D1=2`), `final_analysis.py`, `final_worse_cases.py`, `weighted_analysis.py`. One tick = 12h; attacker moves first; 3 honest guardians unless stated. Argent = release 2.1 as read from the contracts, with the recovery period (36h) and guardian-change delay (24h) taken from Argent's published description and not yet checked against the deployed contracts.

## Rules

- Phase 1: any two of M, S1, S2 held by one side replace the third after 24h; the wallet is locked while it runs. Opening Phase 2 (any one key) cancels a pending replacement and from then on the Argent rules apply.
- Key lock: S1 or S2 only, for one Phase 1 delay; no single key unlocks.
- Guardians: add, remove, confirm, cancel exactly as Argent 2.1; no veto; no minimum; guardians act only in Phase 2.

## A. Time to a working owner, counted from the owner's action

| Situation | Argent, guardians respond in 0 / 12 / 24h | Final design |
|---|---|---|
| M lost | 36 / 48 / 60h | 24h |
| One backup lost | n/a (one key) | 24h |
| M and one backup lost | n/a | 36 / 48 / 60h (needs Phase 2, same as Argent) |
| All three lost | n/a | never |

## B. Longest owner delay that still avoids takeover (hours; guardians answer in 0 / 12 / 24h)

| Situation | Argent | Final design |
|---|---|---|
| M stolen, owner has nothing else | 12 / 0 / none | 12 / 0 / none |
| M copied | 12 / 12 / 12 | 12 / 12 / 12 |
| S1 and S2 stolen | n/a | 12 / 12 / 12 |
| M and one S stolen, owner holds the other S | n/a | 12 / 0 / none |
| M and one S stolen, owner holds nothing | n/a | none |
| One S stolen alone | n/a | 84 or more |

"12" means the owner may start Phase 2 up to one tick after the theft and still win; the replacement lands at 24h. The reading to take away: **the 24h lane protects the case without M (S1 and S2 stolen) for a full day. Every case that includes a stolen M is limited by the 24h guardian removal, as in Argent**, so the lane does not widen that window.

## C. Weighted yearly view (base rates in `WEIGHTED_RESULTS.md`)

| Design | Takeover | Lockout | Hours unable to spend |
|---|---|---|---|
| Argent | 0.465% | 0% | 4.2 |
| **Final design** | **0.473%** | **0.013%** (0.0002% if 90% of lost backups were already replaced) | **1.5** |

## Limits

- Guardian response time is an assumption (the table runs 0, 12, 24h). The replacement rate q is an assumption.
- The model is one incident at a time, and the model, not the contracts, is what was checked.
- Argent's deployed delays are still to be verified.
- Checks: `sanity.py` and `sanity_final.py` 0 failures; `selfcheck_final.py` 3,828 comparisons, monotone.
