"""Final design (any two keys replace the third, 24h Phase 1) against Argent release 2.1. tick = 12h. Attacker moves first.
A: time to a working owner, counted FROM THE OWNER'S ACTION (r=0), for guardian response g = 0/12/24h.
B: reaction window: the longest owner delay r (hours) that still avoids takeover, for g = 0/12/24h."""
import itertools, csv
from model import *
FATE = {"ok": 1, "lost": 0, "gone": 2, "copy": 3}; nm = {v: k for k, v in FATE.items()}
def FINAL(slots, r, g, b=0, first=ATK, D1=2): return P(3, slots=slots, r=r, g=g, b=b, first=first, two_of_three=True, D1=D1)
def ARG(m, r, g, b=0, first=ATK): return P(1, slots=(m, 1, 1), r=r, g=g, b=b, first=first, zero=True)
def hrs(x): return "never" if x is None else f"{x*12}h"
rows = []
print("A. time to a working owner from the owner's action (r=0)")
for g in (0, 1, 2):
    for label, m, s1, s2, key in (("M lost", 0, 1, 1, "ospend"), ("one backup lost", 1, 0, 1, "clean"), ("M and one backup lost", 0, 0, 1, "ospend"), ("all three lost", 0, 0, 0, "ospend")):
        a_f = analyse(FINAL((m, s1, s2), 0, g))[key]
        a_a = analyse(ARG(m, 0, g))[key] if label == "M lost" else "n/a"
        print(f"  g={g*12:>2}h  {label:<24} final {hrs(a_f):>6}   Argent {a_a if a_a=='n/a' else hrs(a_a)}")
        rows.append(dict(part="A", g_h=g*12, scenario=label, final=hrs(a_f), argent=a_a if a_a == "n/a" else hrs(a_a)))
print("\nB. longest owner delay r that is still safe (no takeover), hours; attacker first; 3 honest guardians")
scen = [("M stolen (owner has nothing)", (2, 1, 1)), ("M copied", (3, 1, 1)), ("S1 + S2 stolen", (1, 2, 2)), ("M + S2 stolen, owner holds S1", (2, 1, 2)), ("M + S2 stolen, S1 lost", (2, 0, 2)), ("S1 stolen (alone)", (1, 2, 1))]
for g in (0, 1, 2):
    for label, sl in scen:
        out = {}
        for who in ("final", "argent"):
            if who == "argent" and sl[1:] != (1, 1): out[who] = "n/a"; continue
            safe = -1
            for r in range(0, 8):
                a = analyse(FINAL(sl, r, g)) if who == "final" else analyse(ARG(sl[0], r, g))
                if a["capture"] is None: safe = r
                else: break
            out[who] = "none" if safe < 0 else (">=84h" if safe == 7 else f"{safe*12}h")
        print(f"  g={g*12:>2}h  {label:<34} final {out['final']:>6}   Argent {out['argent']}")
        rows.append(dict(part="B", g_h=g*12, scenario=label, final=out["final"], argent=out["argent"]))
with open("results/K_final.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["part", "g_h", "scenario", "final", "argent"]); w.writeheader(); w.writerows(rows)
