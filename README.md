# Model-checking social recovery: formal specification and adversarial analysis of guardian policies

Start with `SUMMARY.md`: the two designs, the scenarios tested and the final statistics on one page.

CS731 project H4. Authors: Siddharth Miglani and Brinda Fadadu.

This folder holds the code behind the report and the deck: an exact two-player game model (attacker against owner plus honest guardians) of Argent's social recovery and of our layered three-key design, the checks that validate it, the analysis scripts, and the generated reports. Python 3.10 or newer, standard library only, no installation.

**What this is not:** there is no Solidity implementation yet and the model is a Python solver, not TLA+ or Alloy. Everything below is evidence about the design from the model, not from deployed contracts.

## The design that is analysed (final)

- Three owner keys: M (daily), S1 and S2 (cold backups).
- **Phase 1 (fast lane):** any two of M, S1, S2 held by one side replace the third after 24h. The wallet is locked while it runs.
- **Phase 2 (safe lane):** any one key opens Argent-style guardian recovery; this cancels a pending Phase 1 replacement. Guardians act only here.
- **Key lock:** only S1 or S2 can lock, for one Phase 1 delay; no single key unlocks.
- **Guardian add, remove, confirm, cancel:** exactly as in Argent release 2.1 (24h security period, 12h confirm window). No veto, no minimum number of guardians.
- Baseline: Argent `argent-contracts` release 2.1 (tag `2.1`, Oct 2020), audited by Trail of Bits and G0 Group. Recovery period 36h and guardian-change delay 24h are taken from Argent's published description and are not yet checked against the deployed contracts.

One tick is 12 hours. The attacker moves first, so every tie goes to the attacker. n = 3 guardians.

## Quick start

```
python3 demo.py            # side-by-side scenarios, Argent against the final design (a few seconds)
./run_checks.sh            # all validation checks (a few minutes)
```

`demo.py` prints, for example, that a lost M is back in 24h with no guardians against Argent's 36 to 60h, and that three bad guardians take Argent at 36h but not our design.

## Checks (all pass)

| Script | What it checks | Expected last line |
|---|---|---|
| `sanity.py` | Argent's threshold table and hand-computed Argent recovery times | `sanity failures: 0` |
| `sanity_final.py` | Hand-computed predictions for the final design (two-of-three rule, key lock, takeover cases) | `sanity_final failures: 0` |
| `selfcheck_final.py` | Monotonicity for both designs: a later reaction, slower guardians or more bad guardians never give a better result (3,828 comparisons, a few minutes) | `MONOTONE` |

## Solidity: AuthorityGuard (`authguard/`)

A demo of a defence against **authority reentrancy**. In wallets where recovery finalization is permissionless, a contract called mid-`executeBatch` can re-enter `finalizeRecovery()` and change the wallet's authority while the batch is still running.

**Defences** (`AuthorityGuard.sol`):
- Checks-Effects-Interactions: authority state and epoch are committed before events.
- Authority epoch: a counter plus a hash of owner, guardians and modules.
- Transient execution lock (EIP-1153): `executeBatch` sets it, and permissionless recovery functions revert with `AuthorityInFlux()` while it is set.
- Snapshot-and-verify: after the batch, the epoch must equal the pre-batch snapshot, otherwise `AuthorityEpochModified` reverts the batch.

**Contracts**

| File | Purpose |
|---|---|
| `AuthorityGuard.sol` | The guard (abstract, ERC-7201 namespaced storage) |
| `SocialRecoveryWallet.sol` | Demo wallet: guardian threshold, 24h timelock, permissionless finalize, owner cancel |
| `MaliciousCallee.sol` | Attacker that re-enters `finalizeRecovery()` from `fallback`/`receive` |
| `AuthGuard.t.sol` | Foundry tests |

**Run the tests** (needs [Foundry](https://book.getfoundry.sh/)):

```
forge install foundry-rs/forge-std
forge test -vvv
```

`foundry.toml` pins solc 0.8.24 and `evm_version = "cancun"`. Chains without EIP-1153 cannot run the transient lock.

**What the tests show**
- The attack is blocked mid-batch, using a recovery that is otherwise finalizable (after warping past the timelock with the threshold met).
- A control wallet without the guard is successfully taken over by the same attacker.
- Nested `executeBatch` by a contract owner reverts with `BatchReentrancyDetected`.
- Snapshot-and-verify catches authority drift inside a guarded batch.
- Timelock, threshold and access-control checks revert with the expected errors.

**Limits**
- Guardians and threshold are fixed at construction; there is no guardian management.
- The authority hash does not include the threshold, which is acceptable only while it is immutable.
- No audit and no fuzz or invariant tests yet. The two hard-coded storage slot constants should be re-derived with `cast` before any real use.
- The guard addresses reentrancy only; the guardian-policy results above come solely from the Python model.

## Files

| File | Purpose |
|---|---|
| `SUMMARY.md` | One page: scenarios and final statistics, Argent against the final design |
| `FINAL_RESULTS.md` | Detailed results: recovery times, longest safe owner delay, weighted view |
| `WEIGHTED_RESULTS.md` | Yearly weighted view, sources for the rates, sensitivity tables |
| `model.py` | The model: state, rules for Argent (`ver=1`, `zero=True`) and the final design (`ver=3, two_of_three=True, D1=2`), the game graph, the min-max solver (backward Dijkstra), trace extraction |
| `demo.py` | Scenario table, Argent against the final design |
| `final_analysis.py` | Time to recover from the owner's action and longest safe owner delay. Writes `results/K_final.csv`. About 8 minutes |
| `weighted_analysis.py` | Weights the exact outcomes by assumed yearly rates, with sensitivity tables and the repair what-if. Writes `results/I_weighted.csv`. About 2 minutes |
| `make_report_weighted.py` | Builds `WEIGHTED_RESULTS.md` from the CSV |
| `traces.py` | Attack traces, step by step (`results/traces.md`) |
| `results/` | CSV output and traces |


## Reproduce the results

```
./run_checks.sh
python3 final_analysis.py
python3 weighted_analysis.py && python3 make_report_weighted.py
```

The report script writes the numbers into the markdown from the CSV; no table values are typed by hand.

## Outcome definitions

- **Takeover:** the attacker permanently holds the wallet and the owner has no move left that wins it back. Reached through a finished Phase 1 or guardian recovery with the attacker's keys, guardians the attacker installed, or an attacker holding all three keys.
- **Drain:** funds taken at once, owner later regains the wallet. No design here has a spending limit.
- **Lockout:** no theft, but the owner can never spend again (all three keys lost, since guardians cannot open Phase 2 without a key).
- **Hours unable to spend:** time until the owner can spend again, counted from the owner's action.

## Assumptions and limits

- The yearly rates in `weighted_analysis.py` (M lost 5%, M stolen 3%, backups lost 5% and stolen 0.3%, guardians bad 2%) are assumptions. No public data gives per-user yearly rates of key loss or theft. `WEIGHTED_RESULTS.md` section 2b brackets them with Chainalysis and three surveys and runs three scenarios (low, mid, high); the conclusions hold across that range.
- One incident at a time; a guardian is either honest or bad; keys are independent except for a same-thief rule on the backups.
- Relayers, gas, and reentrancy are not modelled. Owner reaction r and guardian response g are parameters.
- The model is of the design, not of contracts. Contract-level work (Solidity prototype, Foundry tests, deployed delays) and a TLA+ or Alloy port are listed as future work.
