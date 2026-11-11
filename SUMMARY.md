# Argent 2.1 against the final design: scenarios and results

Two designs only.

- **Argent 2.1**: one owner key, guardians recover it (24h guardian-change delay, 36h recovery, one guardian is enough to start).
- **Final design**: three owner keys M (daily), S1, S2 (cold). Any two replace the third after 24h. Any one key opens Argent-style guardian recovery. Only S1 or S2 can lock the wallet.

Model: one tick is 12h, the attacker moves first, 3 honest guardians unless stated. `python3 demo.py` reproduces the table.

## 1. Scenarios tested

| Situation | Settings | Argent 2.1 | Final design |
|---|---|---|---|
| M lost | owner acts at once, guardians answer at once | spend again after 36h | spend again after 24h |
| M lost, guardians slow | guardians take 24h | spend again after 60h | spend again after 24h |
| M lost, 2 of 3 guardians bad | guardians 12h | **takeover after 36h** | spend again after 24h |
| M stolen, owner has nothing else | owner reacts after 12h | **takeover after 24h** | **takeover after 24h** |
| M stolen, owner reacts at once | | safe, spend after 36h | safe, spend after 36h |
| M copied (thief and owner both hold it) | owner reacts after 12h | safe | safe |
| M copied + 1 bad guardian | owner at once | safe, spend after 12h | safe, spend after 12h |
| S1 and S2 stolen | owner reacts after 12h | not applicable | safe, spend after 36h |
| S1 and S2 stolen | owner at once | not applicable | safe, spend after 24h |
| One backup lost | | not applicable | spend never blocked (0h) |
| All three keys lost | | not applicable | **lockout** (never spend again) |

Reading the table:

- **Wins:** a lost M is back in 24h instead of 36 to 60h; a lost backup costs nothing; a bad guardian majority cannot hurt a lost-M case; stolen S1 and S2 are safe.
- **Same as Argent:** every case that includes a stolen M is limited by the same race (owner must act within 12h).
- **Cost:** losing all three keys is a permanent lockout. Argent has none, because guardians can always recover.

## 2. Final statistics (per wallet per year)

Rates are assumptions backed by public figures: M lost 5%, M stolen 3% (90% as a copy), each backup lost 5% and stolen 0.3%, one guardian bad 2%, owner reacts in 12h, guardians need 24h to gather.

| Design | Takeover (attacker keeps wallet) | Lockout (owner never spends) | Hours unable to spend |
|---|---|---|---|
| Plain wallet (one key, no recovery) | 3.00% | 4.85% | n/a |
| Argent 2.1 | 0.465% | 0% | 4.2h |
| **Final design** | **0.473%** | **0.013%** | **1.5h** |

Across the low, mid and high rate scenarios:

| Scenario | Argent takeover / hours | Final takeover / hours | Final lockout |
|---|---|---|---|
| Low | 0.033% / 2.3h | 0.031% / 0.4h | 0.001% |
| Mid | 0.160% / 4.3h | 0.155% / 1.3h | 0.005% |
| High | 0.623% / 6.4h | 0.631% / 2.5h | 0.022% |

## 3. Conclusion

- Takeover risk is the same as Argent (0.473% against 0.465%).
- Time unable to spend drops from 4.2h to 1.5h a year per wallet.
- The price is a small lockout risk (0.013%), only if all three keys are lost, and 0.0002% if lost backups are replaced promptly.

Limits: guardian response time and key rates are assumptions; the model is one incident at a time; Argent's deployed delays still need checking; there is no Solidity prototype yet.
