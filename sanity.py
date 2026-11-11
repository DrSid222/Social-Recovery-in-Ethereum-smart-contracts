from model import *
import math
fails = 0
def check(name, cond, extra=""):
    global fails
    print(("PASS " if cond else "FAIL ") + name, extra)
    if not cond: fails += 1

# 1. thresholds vs Argent's threshold table: n -> (start, cancel)
table = {0:(0,1),1:(1,1),2:(1,2),3:(2,2),4:(2,3),5:(3,3),7:(4,4)}
for n,(s,c) in table.items():
    check(f"threshold n={n}", ((n+1)//2, 1+n//2) == (s,c))

# 2. no attacker, nothing lost: clean immediately, nothing bad possible
for ver in (1,2):
    r = analyse(P(ver))
    check(f"V{ver} all safe: clean=0, attacker cannot win", r["clean"]==0 and r["funds"] is None and r["capture"] is None, str(r))

# 3. M lost, S safe, honest guardians, g=1: V1 needs alert + g + D2 ticks; V2 Phase 1 needs D1 ticks
r1 = analyse(P(1, slots=(0,1,1), g=1)); r2 = analyse(P(2, slots=(0,1,1), g=1))
check("V1 lost M: clean in g+D2=4 ticks", r1["clean"]==4, str(r1))
check("V2 lost M (S safe): clean in D1=2 ticks", r2["clean"]==2, str(r2))

# 4. V1 lost M with only bad majority guardians cannot recover (b=2 of 3); attacker holds no keys but guardians alone can start recovery in V1
r = analyse(P(1, slots=(1,1,1), b=2, r=4))
check("V1 guardians-only quorum can take over a slow owner (r=4)", r["capture"] is not None, str(r))
r = analyse(P(2, slots=(1,1,1), b=2))
check("V2 guardians-only quorum cannot take over (S2)", r["capture"] is None, str(r))

# 5. V2: S1+S2 stolen, owner has M, responds at r=0: attacker Phase1 vs owner Phase2
r = analyse(P(2, slots=(1,3,3), r=0, g=0))
print("V2 S1+S2 stolen_copy r=0:", r)
r = analyse(P(2, slots=(1,3,3), r=3, g=0))
print("V2 S1+S2 stolen_copy r=3 (slow owner):", r)

# 6. V2 single S key stolen: no loss/capture
r = analyse(P(2, slots=(1,2,1), r=0))
check("V2 one stolen S key: no capture, no funds loss", r["capture"] is None and r["funds"] is None, str(r))
# 7. V2 stolen M with guardians honest: can only drain (funds), not capture, when owner responsive
r = analyse(P(2, slots=(2,1,1), r=0, g=0, b=0))
print("V2 M stolen_gone r=0 g=0:", {k:v for k,v in r.items() if 'trace' not in k})
print("sanity failures:", fails)
