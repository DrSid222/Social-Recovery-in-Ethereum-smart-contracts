"""Demo: final design (any two keys replace the third, 24h Phase 1, only S1/S2 lock) against Argent release 2.1.
Usage: python3 demo.py            (prints a table of scenarios)
Times are hours from the start of the incident, attacker moves first, tick = 12h.
Key states: ok = only the owner has it, lost = nobody, gone = stolen and the owner has none, copy = stolen and the owner keeps it."""
from model import *
FATE = {"ok": 1, "lost": 0, "gone": 2, "copy": 3}
def final(m, s1, s2, r, g=1, b=0): return analyse(P(3, slots=(FATE[m], FATE[s1], FATE[s2]), r=r, g=g, b=b, two_of_three=True, D1=2))
def argent(m, r, g=1, b=0): return analyse(P(1, slots=(FATE[m], 1, 1), r=r, g=g, b=b, zero=True))
def h(x): return "never" if x is None else f"{x*12}h"
def row(name, m, s1, s2, r, g=1, b=0):
    f = final(m, s1, s2, r, g, b)
    if (s1, s2) != ("ok", "ok") or name.startswith("All three"): atxt = "n/a (one key)"
    else: a = argent(m, r, g, b); atxt = f"takeover {h(a['capture'])}, spend {h(a['ospend'])}"
    return (name, f"r={r*12}h g={g*12}h bad={b}", atxt, f"takeover {h(f['capture'])}, spend {h(f['ospend'])}")
rows = [
 row("M lost", "lost", "ok", "ok", 0, g=0),
 row("M lost, guardians slow", "lost", "ok", "ok", 0, g=2),
 row("M lost, 2 of 3 guardians bad", "lost", "ok", "ok", 0, b=2),
 row("M stolen (owner has nothing)", "gone", "ok", "ok", 1),
 row("M stolen, owner reacts at once", "gone", "ok", "ok", 0, g=0),
 row("M copied", "copy", "ok", "ok", 1),
 row("M copied + 1 bad guardian", "copy", "ok", "ok", 0, b=1),
 row("S1 and S2 stolen, owner reacts at 12h", "ok", "gone", "gone", 1),
 row("S1 and S2 stolen, at once", "ok", "gone", "gone", 0),
 row("One backup lost", "ok", "lost", "ok", 0),
 row("All three keys lost", "lost", "lost", "lost", 0),
]
w = [max(len(r[i]) for r in rows) for i in range(4)]
print(f"{'Situation':<{w[0]}}  {'Settings':<{w[1]}}  {'Argent 2.1':<{w[2]}}  Final design")
for r in rows: print(f"{r[0]:<{w[0]}}  {r[1]:<{w[1]}}  {r[2]:<{w[2]}}  {r[3]}")
print("\nspend = hours until the owner can spend again; takeover = hours until the attacker permanently holds the wallet; never = does not happen.")
