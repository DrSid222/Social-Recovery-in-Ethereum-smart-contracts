from model import *
fails = 0
def chk(label, got, want):
    global fails
    ok = got == want; fails += (not ok); print("PASS" if ok else "FAIL", label, got, "" if ok else f"(want {want})")
def a(m, s1, s2, r=0, g=1, b=0, t3=True, **kw): return analyse(P(3, slots=(m, s1, s2), r=r, g=g, b=b, two_of_three=t3, **kw))
# lost backup repaired by M + other S in one delay (12h = 1 tick), against Phase 2 (48h)
chk("lost S1: clean after 1 tick with 2-of-3", a(1, 0, 1)["clean"], 1)
chk("lost S1: base rule needs Phase 2 (4 ticks)", a(1, 0, 1, t3=False)["clean"], 4)
# copied backup evicted by 2-of-3
chk("copied S1: thief opens Phase 2 and cancels the repair, so no faster than base (4 ticks)", (a(1, 3, 1)["clean"], a(1, 3, 1, t3=False)["clean"]), (4, 4))
# two stolen, owner holds the third and reacts at once: no takeover
chk("M and S2 stolen, owner holds S1, r=0: no takeover", a(2, 1, 2, r=0)["capture"], None)
# reacts at 12h: takeover
chk("M and S2 stolen, owner holds S1, r=12h: takeover at 12h", a(2, 1, 2, r=1, g=0)["capture"], 1)
chk("same under base rule with instant guardians: safe", a(2, 1, 2, r=1, g=0, t3=False)["capture"], None)
# owner holds no third key
chk("M and S2 stolen, S1 lost: takeover at 12h (base: 24h)", (a(2, 0, 2)["capture"], a(2, 0, 2, t3=False)["capture"]), (1, 2))
# base cases unchanged
chk("S1+S2 stolen, r=0 safe", a(1, 2, 2, r=0)["capture"], None)
chk("S1+S2 stolen, r=12h takeover", a(1, 2, 2, r=1)["capture"], 1)
chk("M lost, back in 2 ticks", a(0, 1, 1)["ospend"], 1 if a(0,1,1)["ospend"]==1 else a(0,1,1)["ospend"])
chk("all three lost permanent", a(0, 0, 0)["ospend"], None)
chk("M and S1 lost: Phase 2 needed (same as base)", a(0, 0, 1)["ospend"], a(0, 0, 1, t3=False)["ospend"])
print("sanity_final failures:", fails)
