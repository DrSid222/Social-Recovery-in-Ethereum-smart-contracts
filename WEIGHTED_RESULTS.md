# Statistical view: how the design holds up when key problems are weighted by how often they happen

Generated 2026-11-08 from `weighted_analysis.py`. The exact solver gives the outcome of every situation; this file weights those outcomes by assumed yearly probabilities.

## 1. What the data can and cannot say

No public source separates, per user and per year, how many key problems are **losses** and how many are **thefts**. These are the indicators found:

| Indicator | Figure | Source and limit |
|---|---|---|
| Holders who ever lost access to a wallet or account | 35% of 1,000 US holders; 31% of those never recovered it | Oobit survey (a crypto payments company), self-reported, undated page |
| Causes of that loss | forgotten password 33%, lost seed phrase 21%, lost 2FA 20%, external events 16% | same survey; hacking/theft not quantified |
| Bitcoin that appears permanently inaccessible | about 20% of supply (about 3.7M BTC) | Chainalysis via press reports; method not published; a stock built up over 12 years |
| Theft from individuals in 2025 | $713M, 158,000 incidents, at least 80,000 victims (2024: $1.5B) | Chainalysis via The Block; about $9k per victim by arithmetic |

Reading: by headcount, losing access is the more common event for ordinary holders; theft is rarer but takes value fast. The two figures measure different things (lifetime survey, stock of coins, yearly flow), so **they give a direction, not a ratio**. Every rate below is therefore an illustrative assumption, chosen to be of the right order of magnitude, and the second half of this file shows which assumptions matter.

## 2. Assumptions (base case, per year)

| Event | Base | Why |
|---|---|---|
| M (hot key) lost | 5% | roughly consistent with a large lifetime loss rate; assumption |
| M stolen | 3% | assumption; 90% of thefts leave the owner holding a copy (malware, phishing), 10% leave the owner without it |
| S1 or S2 (cold backup) lost | 5% each | backups are easy to misplace; assumption |
| S1 or S2 stolen | 0.3% each; if one is stolen the other is stolen by the same thief with probability 10% | cold keys are assumed to be kept safe and rarely stolen together; assumption |
| A guardian is bad | 2% each, independent | assumption |
| Owner notices / guardians answer | 12h / 12h in a race with a thief (as in the model runs) | downtime is counted from the owner's action, with guardians taking 24h to gather when nobody is racing |

Outcomes: **takeover** (the attacker ends with the wallet), **drain** (funds taken at once, owner gets the wallet back; no design has a spending limit), **lockout** (owner can never spend again), **ok** (owner spends again after a downtime).

## 2b. Where the rates come from, and a range that the data supports

Nothing public gives a yearly rate of key loss or key theft per self-custody user. Two kinds of evidence bracket it. Both need an assumption to become a yearly rate, so the result is a range, not a measurement.

**Lifetime surveys** (share of holders who ever had the problem):

| Survey | Finding | Limit |
|---|---|---|
| Oobit, US holders (about 1,000) | 35% lost access to a wallet or account; 31% of them never recovered; causes: forgotten password 33%, lost seed phrase 21%, lost 2FA 20% | undated, self-reported, run by a crypto payments company |
| Kraken, about 800 crypto users, June 2025 (DL News) | 20% had been victims of scams or hacks; more than two-thirds admitted a common mistake such as forgetting a password or misplacing a seed phrase | country not stated in the article; scams are not all key thefts |
| Kaspersky, US owners, March 2023 | 32% lost access to a crypto-related account; a third had crypto stolen | sample size not stated; three years old |

**Yearly flow** (Chainalysis, via The Block): in 2025, 158,000 personal-wallet compromise incidents and at least 80,000 unique victims, $713M stolen from individuals (2024: $1.5B).

**Turning them into yearly per-user rates (arithmetic)**
- Theft from the flow: 80,000 victims divided by the active self-custody base. MetaMask has about 30M monthly active users and Phantom reached about 17M in 2025 (Datawallet, citing its own review and DL News); taking 47M to 100M users gives **0.08% to 0.17% a year**. "At least 80,000" and unreported thefts make this a floor.
- Theft from the surveys: 20% lifetime divided by an assumed 4 to 6 years of ownership gives **3% to 5% a year**. This is a ceiling because scams are included.
- Loss from the surveys: 35% lifetime for any cause is **6% to 9% a year**; the lost-seed-phrase share alone (35% times 21%, about 7%) is **1.2% to 1.8% a year**. A hot key is closer to the second number.
- Backups (cold storage): no data. Lower loss and theft than M are assumed.

Three scenarios inside those bounds (backup theft rates are assumptions):

| Scenario | M lost | M stolen | Backup lost | Backup stolen |
|---|---|---|---|---|
| Low | 1.5% | 0.2% | 2% | 0.05% |
| Mid | 5% | 1% | 3% | 0.1% |
| High | 9% | 4% | 5% | 0.3% |


| Scenario | Design | Takeover | Drain only | Lockout | Hours unable to spend |
|---|---|---|---|---|---|
| Low | Plain wallet | 0.200% | n/a | 1.497% | n/a |
| Low | Argent | 0.033% | 0.169% | 0.000% | 2.3 |
| Low | Our design | 0.031% | 0.169% | 0.001% | 0.4 |
| Mid | Plain wallet | 1.000% | n/a | 4.950% | n/a |
| Mid | Argent | 0.160% | 0.847% | 0.000% | 4.3 |
| Mid | Our design | 0.155% | 0.845% | 0.005% | 1.3 |
| High | Plain wallet | 4.000% | n/a | 8.640% | n/a |
| High | Argent | 0.623% | 3.388% | 0.000% | 6.4 |
| High | Our design | 0.631% | 3.369% | 0.022% | 2.5 |

Across the whole range, the picture is the same as at the base rates: takeover is within a few hundredths of a point of Argent, the time unable to spend is about a sixth to two fifths of Argent's, and permanent lockout is small but not zero (up to about 0.02%). A plain wallet loses much more through lockout (1.5% to 8.6% a year). What changes with the rates is the size of the drain: 0.17% (low), 0.85% (mid) and 3.4% (high) in both designs.

## 3. Result with the base assumptions

| Design | Takeover | Drain only | Lockout | Expected hours unable to spend per year |
|---|---|---|---|---|
| Plain wallet (no recovery) | 3.000% (any theft) | n/a | 4.850% (any loss) | n/a |
| Argent (release 2.1) | 0.465% | 2.541% | 0.000% | 4.21 |
| **Final design: 2-of-3, 24h lane, only S1 and S2 lock** | 0.473% | 2.527% | 0.013% | 1.46 |

**What this says**
- A plain wallet loses the holder's funds in 7.85% of years. Both recovery designs bring the lockout part to about zero. That is the real gain of social recovery, and it is the same for both.
- **The big risk is M being stolen, and neither design touches it.** About 2.5% of years end with funds drained at once, because M has no spending limit. This dominates everything else by a factor of five or more. A spending limit or a delay on large transfers would help more than any recovery rule.
- Between Argent and our design the differences are small: takeover 0.465% against 0.473% (a gap of 0.008 percentage points), lockout 0.013% against 0, and expected time unable to spend 4.2h against 1.5h per year.
- The small extra takeover comes from backup-key thefts. The extra lockout is all three keys lost; if lost backups are replaced before the next loss it nearly disappears (section 5).
- Downtime is counted from the moment the owner acts, with guardians taking 24h to gather when nobody is racing. Argent's number is that 24h plus the 36h recovery period.

## 4. How sensitive is that to the assumptions?

Each table varies one assumption and keeps the rest at base. Cells: takeover / lockout / expected hours unable to spend.


**Each backup key stolen per year**

| value | Argent | Our design |
|---|---|---|
| 0.05% | 0.465% / 0.000% / 4.2h | 0.461% / 0.013% / 1.3h |
| 0.3% | 0.465% / 0.000% / 4.2h | 0.473% / 0.013% / 1.5h |
| 1% | 0.465% / 0.000% / 4.2h | 0.507% / 0.012% / 1.8h |
| 3% | 0.465% / 0.000% / 4.2h | 0.604% / 0.012% / 2.7h |

**Chance the same thief gets both backups, given one**

| value | Argent | Our design |
|---|---|---|
| 0% | 0.465% / 0.000% / 4.2h | 0.474% / 0.013% / 1.5h |
| 10% | 0.465% / 0.000% / 4.2h | 0.473% / 0.013% / 1.5h |
| 50% | 0.465% / 0.000% / 4.2h | 0.470% / 0.013% / 1.4h |
| 100% | 0.465% / 0.000% / 4.2h | 0.466% / 0.013% / 1.4h |

**Each backup key lost per year**

| value | Argent | Our design |
|---|---|---|
| 2% | 0.465% / 0.000% / 4.2h | 0.473% / 0.002% / 1.4h |
| 5% | 0.465% / 0.000% / 4.2h | 0.473% / 0.013% / 1.5h |
| 10% | 0.465% / 0.000% / 4.2h | 0.473% / 0.049% / 1.6h |
| 20% | 0.465% / 0.000% / 4.2h | 0.473% / 0.195% / 1.8h |

**Chance a guardian is bad**

| value | Argent | Our design |
|---|---|---|
| 0% | 0.300% / 0.000% / 2.9h | 0.315% / 0.012% / 1.5h |
| 2% | 0.465% / 0.000% / 4.2h | 0.473% / 0.013% / 1.5h |
| 5% | 0.732% / 0.000% / 6.0h | 0.699% / 0.015% / 1.5h |
| 10% | 1.260% / 0.000% / 8.8h | 1.044% / 0.025% / 1.5h |
| 20% | 2.859% / 0.000% / 13.2h | 1.633% / 0.060% / 1.4h |

**M lost per year**

| value | Argent | Our design |
|---|---|---|
| 2% | 0.462% / 0.000% / 2.5h | 0.473% / 0.005% / 0.7h |
| 5% | 0.465% / 0.000% / 4.2h | 0.473% / 0.013% / 1.5h |
| 10% | 0.471% / 0.000% / 7.0h | 0.473% / 0.025% / 2.8h |
| 20% | 0.482% / 0.000% / 12.7h | 0.473% / 0.050% / 5.4h |

**Owner reaction time (ticks of 12h)**

| value | Argent | Our design |
|---|---|---|
| 0h | 0.027% / 0.000% / 4.2h | 0.019% / 0.013% / 1.5h |
| 12h | 0.465% / 0.000% / 4.2h | 0.473% / 0.013% / 1.5h |
| 24h | 3.115% / 0.000% / 4.2h | 3.030% / 0.013% / 1.5h |
| 48h | 3.115% / 0.000% / 4.2h | 3.030% / 0.013% / 1.5h |

## 5. Where the design holds its own, and where it does not

**It holds its own**
- Across every backup-theft setting tested (0.05% to 3% a year each, same-thief chance 0% to 100%) the takeover gap to Argent stays under 0.15 percentage points.
- Time unable to spend: 1.5h a year against Argent's 4.2h (2.9h for Argent with honest guardians). The gap grows with how often M is lost: 5.4h against 12.7h at 20% a year.
- Bad guardians: ours is slightly higher at 2% (0.473% against 0.465%), slightly lower at 5% (0.699% against 0.732%), and clearly lower at 10% (1.04% against 1.26%) and 20% (1.63% against 2.86%), because Argent's guardians alone can take a wallet. This is the trust problem the design was meant to attack.
- The lockout cost mostly goes away if lost backups are replaced before the next loss. With the 2-of-3 rule and 90% replaced, lockout is 0.0002% instead of 0.013%; at 10% and 20% backup loss a year it is 0.0006% and 0.0022% instead of 0.049% and 0.195%. That 90% is an assumption (section 5).

**It does not**
- If backups are lost often and nobody replaces them, permanent lockout rises to 0.05% to 0.2% a year. Argent has no such failure.
- Owner reaction time matters more than any rule: from 12h to 24h takeover goes from about 0.5% to about 3.0% in both designs.
- A stolen M still drains the wallet at once in about 2.5% of years in both designs.
- A copied M together with a stolen backup: the 24h lane ties with the 24h guardian change, and the thief wins the tie (39 of the cases in the wide grid, `FINAL_RESULTS.md`).

## 6. Limits

- **The rates are assumptions.** The data above supports a direction (losing access is more common than theft; theft is costly) and not these exact numbers. Read the tables as "what changes if the assumption moves", not as forecasts.
- Keys are treated as independent except for the same-thief rule on the backups. Real losses are correlated (one fire, one phishing kit, one home burglary).
- Guardians are all-or-nothing honest or bad; collusion is modelled only as independent bad guardians.
- Outcomes are not priced against each other: a takeover, a lockout and an hour of downtime are different harms.
- Only one wallet-year at a time; no repeated incidents, no key rotation after an incident.
- The solver results behind every cell come from `model.py`; the modelling limits in `README.md` apply.
