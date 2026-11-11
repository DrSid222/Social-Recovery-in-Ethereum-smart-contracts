"""
Explicit-state two-player game model of social-recovery designs.
V1 = Argent-style baseline (2020 code as read from argent-contracts)
V2 = earlier layered design (guardians have NO power outside Phase 2)

Players: ATTACKER (holds some keys, controls b of n guardians) and OWNER (holds keys,
plus h = n-b honest guardians who act only after the owner alerts them and g ticks pass).
One tick = 12 hours. Each side may make up to CAPMOVES actions per tick, then passes.
Solved exactly (min-max over ticks) by backward Dijkstra on the full reachable game graph.
"""
import heapq
from collections import namedtuple

(M, S1, S2, KL, P1H, P1R, PH2, RECH, RECR, GL, GCH, GCR, GCW, B, ALERT, DET, LOSS, CAP, Z, P1T) = range(20)
INF = 10**9
ATK, OWN = 0, 1

class P:
    def __init__(s, ver, n=3, b=0, slots=(1, 1, 1), r=0, g=0, D1=None, D2=3, GCd=None, W=1,
                 Lg=10, first=ATK, cap=3, transfer=None, rev_lock=False, name="", mcancel=True, p1_guard=False, s_close=False,
                 veto="auto", gc_ph2_block=None, clear_pending=None, zero=None, cancel_thru_keylock=False, lock_s_only=None, two_of_three=False):
        # V3 = V2 phase structure (Phase 1 / Phase 2) + Argent-style guardian management + guardian veto, D1 = 12h, no minimum guardians
        s.ver, s.n, s.b, s.slots, s.r, s.g = ver, n, b, tuple(slots), r, g
        if D1 is None: D1 = 1 if ver == 3 else 2
        s.D1, s.D2, s.W, s.Lg, s.first, s.cap = D1, D2, W, Lg, first, cap
        s.phased = ver in (2, 3)
        s.argent_gc = ver in (1, 3)          # owner (M) can cancel; confirm by anyone; pending changes survive recovery unless clear_pending
        s.veto = ("maj" if ver == 2 else None) if veto == "auto" else veto     # None | 'maj' (strict majority) | 'any' (one guardian). V3 main design: no veto (exact Argent guardian rules)
        s.gc_ph2_block = (ver == 3) if gc_ph2_block is None else gc_ph2_block       # guardian change request not allowed while Phase 2 is open
        s.clear_pending = (ver == 2) if clear_pending is None else clear_pending    # recovery / Phase 1 finalize wipes pending guardian changes
        s.lock_s_only = (ver == 3) if lock_s_only is None else lock_s_only    # V3 main design: only S1 / S2 may key-lock (M cannot)
        s.cancel_thru_keylock = cancel_thru_keylock   # owner (M) may cancel a pending guardian change while only a KEY lock is on
        s.zero = (ver == 3) if zero is None else zero                               # attacker/owner may reduce the guardian set to zero (no minimum)
        # GC delay: V1 securityPeriod (must satisfy D2 >= GCd + W); V2: 36h = 3 ticks
        s.GCd = GCd if GCd is not None else (2 if ver != 2 else 3)
        s.transfer = (ver == 1) if transfer is None else transfer   # Argent transferOwnership
        s.mcancel, s.p1_guard, s.s_close = mcancel, p1_guard, s_close
        s.rev_lock = rev_lock        # V1b: lock blocks guardian removal (current Argent support page)
        s.Lkey = D1
        s.t3 = two_of_three     # any two of M,S1,S2 (held by one side) may replace the third after D1; opening Phase 2 cancels the pending replacement
        s.name = name
    @property
    def v2(s): return s.ver == 2

def init_core(p):
    m, s1, s2 = p.slots
    if not p.phased: s1 = s2 = 1
    return (m, s1, s2, 0, 0, 0, 0 if p.phased else 1, 0, 0, 0, 0, 0, 0, p.b, -1, p.r, 0, 0, 0, 0)

def locked(c): return c[GL] > 0 or c[RECH] != 0 or c[P1H] != 0 or c[KL] > 0

def tick(c, p):
    l = list(c)
    for i in (KL, P1R, RECR, GL, DET):
        if l[i] > 0: l[i] -= 1
    if l[GCH]:
        if l[GCR] > 0: l[GCR] -= 1
        else:
            l[GCW] -= 1
            if l[GCW] <= 0: l[GCH] = 0; l[GCW] = 0
    if l[ALERT] >= 0: l[ALERT] = min(l[ALERT] + 1, p.g)
    return tuple(l)

def setv(c, **kw):
    l = list(c)
    for k, v in kw.items(): l[globals()[k]] = v
    return tuple(l)

def rotate(c, p, holder):
    """guardian-recovery finalize / P1 finalize result."""
    l = list(c)
    if p.phased:
        l[M] = l[S1] = l[S2] = holder
        l[P1H] = l[P1R] = 0; l[P1T] = 0; l[KL] = 0; l[GL] = 0
        if p.clear_pending: l[GCH] = l[GCR] = l[GCW] = 0
        l[RECH] = l[RECR] = 0; l[PH2] = 0
    else:
        l[M] = holder; l[RECH] = l[RECR] = 0; l[GL] = 0     # pending guardian changes SURVIVE a recovery (Argent release 2.1)
    if holder == ATK: l[CAP] |= 1
    return tuple(l)

def veto_ok(p, k, n):
    if p.veto == "maj": return 2 * k > n
    if p.veto == "any": return k >= 1
    return False

def can_cancel_gc(c, p):
    lk = locked(c)
    if not lk: return True
    return p.cancel_thru_keylock and c[GL] == 0 and c[RECH] == 0 and c[P1H] == 0

def gc_confirmable(c): return c[GCH] != 0 and c[GCR] == 0 and c[GCW] > 0

def moves(c, side, p):
    out = []
    n = p.n
    b = 0 if c[Z] else c[B]
    h = 0 if c[Z] else n - b
    need_start = (n + 1) // 2
    need_cancel = 1 + n // 2
    v2 = p.phased
    lk = locked(c)
    if side == ATK:
        bit = 2
        if c[M] & bit and not lk and not c[LOSS]: out.append(("A: spend (drain)", setv(c, LOSS=1)))
        if v2:
            anyk = any(c[i] & bit for i in (M, S1, S2))
            if c[PH2] == 0:
                lockk = (c[S1] & bit or c[S2] & bit) if p.lock_s_only else anyk
                if lockk and c[KL] < p.Lkey: out.append(("A: key_lock", setv(c, KL=p.Lkey)))
                openk = (c[S1] & bit or c[S2] & bit) if (p.p1_guard and c[P1H] != 0) else anyk
                if openk: out.append(("A: open Phase 2", setv(c, PH2=1, P1H=0, P1R=0, P1T=0)))
                if c[P1H] == 0:
                    for t in p1_starts(c, p, bit):
                        out.append(("A: Phase1_start (replace " + ("M" if t == M else "S1" if t == S1 else "S2") + ")", setv(c, P1H=2, P1R=p.D1, P1T=t)))
            if c[P1H] == 2 and c[P1R] == 0:
                out.append(("A: Phase1_finalize -> attacker key", rotate_m(c, p, ATK)))
            if p.s_close and c[PH2] == 1 and c[RECH] == 0 and c[S1] & bit and c[S2] & bit:
                out.append(("A: close Phase 2 (S1+S2)", setv(c, PH2=0)))
        # guardian change by M
        if c[M] & bit and c[GCH] == 0 and not (p.zero and c[Z]):
            if p.ver == 2: ok = c[PH2] == 0 and not lk and c[P1H] == 0 and c[RECH] == 0
            else:
                ok = not lk if p.rev_lock else True
                if p.ver == 3 and p.gc_ph2_block and c[PH2] == 1: ok = False
            if ok: out.append(("A: guardian_change request (strip/replace guardians)", setv(c, GCH=2, GCR=p.GCd, GCW=p.W)))
        if c[GCH] == 2 and gc_confirmable(c) and not (p.argent_gc and p.rev_lock and lk):
            if not (p.zero and lk):      # adding the attacker's guardians needs an unlocked wallet (Argent); with zero-state modelled, a lock leaves only the removal
                out.append(("A: guardian_change confirm -> attacker guardians", setv(c, B=n, GCH=0, GCR=0, GCW=0, CAP=c[CAP] | 2)))
            if p.zero: out.append(("A: guardian_change confirm -> strip to zero guardians", setv(c, B=0, Z=1, GCH=0, GCR=0, GCW=0)))
        if p.zero and c[Z] and c[M] & bit and not lk:
            out.append(("A: add attacker guardians (from zero)", setv(c, Z=0, B=n, CAP=c[CAP] | 2)))
        if p.argent_gc and c[GCH] == 1 and c[M] & bit and can_cancel_gc(c, p):
            out.append(("A: cancel owner's guardian change (M)", setv(c, GCH=0, GCR=0, GCW=0)))
        # bad guardians
        if b >= 1:
            if c[PH2] == 1 and not lk: out.append(("BG: lock", setv(c, GL=p.Lg)))
            if c[GL] > 0 and c[RECH] == 0: out.append(("BG: unlock", setv(c, GL=0)))
            if c[PH2] == 1 and c[RECH] == 0 and b >= need_start:
                out.append(("BG: start guardian recovery (attacker keys)", setv(c, RECH=2, RECR=p.D2, GL=0)))
            if c[RECH] == 1 and b + (1 if (c[M] & 2 and p.mcancel) else 0) >= need_cancel:
                cc = setv(c, RECH=0, RECR=0, GL=0)
                if v2: cc = setv(cc, PH2=0)
                out.append(("BG+M: cancel owner's recovery", cc))
            if c[GCH] == 1 and veto_ok(p, b, n):
                out.append(("BG: veto owner's guardian change (final)", setv(c, GCH=0, GCR=0, GCW=0)))
        if c[RECH] == 2 and c[RECR] == 0: out.append(("A: guardian_recovery finalize -> attacker keys", rotate(c, p, ATK)))
        if p.transfer and c[M] & bit and b >= need_start and not lk and (c[PH2] == 1):
            out.append(("A+BG: transferOwnership (immediate)", transfer_to(c, p, ATK)))
    else:
        if c[DET] > 0: return out
        bit = 1
        if c[ALERT] == -1: out.append(("O: alert guardians", setv(c, ALERT=0)))
        if v2:
            anyk = any(c[i] & bit for i in (M, S1, S2))
            if c[PH2] == 0:
                lockk = (c[S1] & bit or c[S2] & bit) if p.lock_s_only else anyk
                if lockk and c[KL] < p.Lkey: out.append(("O: key_lock", setv(c, KL=p.Lkey)))
                openk = (c[S1] & bit or c[S2] & bit) if (p.p1_guard and c[P1H] != 0) else anyk
                if openk: out.append(("O: open Phase 2", setv(c, PH2=1, P1H=0, P1R=0, P1T=0)))
                if c[P1H] == 0:
                    for t in p1_starts(c, p, bit):
                        out.append(("O: Phase1_start (replace " + ("M" if t == M else "S1" if t == S1 else "S2") + ")", setv(c, P1H=1, P1R=p.D1, P1T=t)))
            if c[P1H] == 1 and c[P1R] == 0:
                out.append(("O: Phase1_finalize -> owner key", rotate_m(c, p, OWN)))
            if p.s_close and c[PH2] == 1 and c[RECH] == 0 and c[S1] & bit and c[S2] & bit:
                out.append(("O: close Phase 2 (S1+S2)", setv(c, PH2=0)))
        if c[M] & bit and c[GCH] == 0 and not (p.zero and c[Z]):
            if p.ver == 2: ok = c[PH2] == 0 and not lk and c[P1H] == 0 and c[RECH] == 0
            else:
                ok = not lk if p.rev_lock else True
                if p.ver == 3 and p.gc_ph2_block and c[PH2] == 1: ok = False
            if ok: out.append(("O: guardian_change request (replace guardians)", setv(c, GCH=1, GCR=p.GCd, GCW=p.W)))
        if c[GCH] == 1 and gc_confirmable(c) and not (p.argent_gc and p.rev_lock and lk):
            if not (p.zero and lk):
                out.append(("O: guardian_change confirm -> honest guardians", setv(c, B=0, GCH=0, GCR=0, GCW=0)))
            if p.zero and lk and c[B] > 0:
                out.append(("O: guardian_change confirm -> removal only (locked: additions wait)", setv(c, B=0, Z=1, GCH=0, GCR=0, GCW=0)))
        if p.zero and c[Z] and c[M] & bit and not lk:
            out.append(("O: add honest guardians (from zero)", setv(c, Z=0, B=0)))
        if p.argent_gc and c[GCH] == 2 and c[M] & bit and can_cancel_gc(c, p):
            out.append(("O: cancel attacker's guardian change (M)", setv(c, GCH=0, GCR=0, GCW=0)))
        ready = c[ALERT] >= 0 and c[ALERT] >= p.g
        if ready:
            if h >= 1:
                if c[PH2] == 1 and not lk: out.append(("HG: lock", setv(c, GL=p.Lg)))
                if c[GL] > 0 and c[RECH] == 0: out.append(("HG: unlock", setv(c, GL=0)))
            if c[PH2] == 1 and c[RECH] == 0 and h >= need_start:
                out.append(("HG: start guardian recovery (owner keys)", setv(c, RECH=1, RECR=p.D2, GL=0)))
            if c[RECH] == 2 and h + (1 if (c[M] & 1 and p.mcancel) else 0) >= need_cancel:
                cc = setv(c, RECH=0, RECR=0, GL=0)
                if v2: cc = setv(cc, PH2=0)
                out.append(("HG+M: cancel attacker's recovery", cc))
            if c[GCH] == 2 and veto_ok(p, h, n):
                out.append(("HG: veto attacker's guardian change", setv(c, GCH=0, GCR=0, GCW=0)))
            if p.transfer and c[M] & bit and h >= need_start and not lk and c[PH2] == 1:
                out.append(("O+HG: transferOwnership (immediate)", transfer_to(c, p, OWN)))
        if c[RECH] == 1 and c[RECR] == 0: out.append(("O: guardian_recovery finalize -> owner keys", rotate(c, p, OWN)))
    return out

def rotate_m(c, p, holder):
    l = list(c)
    t = c[P1T]; bit = 2 if holder == ATK else 1
    l[t] = bit; l[P1H] = l[P1R] = 0; l[P1T] = 0; l[KL] = 0
    if t == M:
        if p.clear_pending: l[GCH] = l[GCR] = l[GCW] = 0
        if holder == ATK: l[CAP] |= 1
    elif holder == ATK and all(l[i] == 2 for i in (M, S1, S2)): l[CAP] |= 1     # attacker holds every key, owner can open nothing
    return tuple(l)

def p1_starts(c, p, bit):
    """(target) slots a side may start replacing: M with S1+S2 (base rule), or with two_of_three any slot with the other two."""
    keys = (M, S1, S2); out = []
    for t in keys:
        others = [k for k in keys if k != t]
        if not all(c[k] & bit for k in others): continue
        if t != M and not p.t3: continue
        if t != M and c[t] == bit: continue       # nothing to change
        out.append(t)
    return out

def transfer_to(c, p, holder):
    l = list(c); l[M] = holder
    if p.phased: l[GCH] = l[GCR] = l[GCW] = 0
    if holder == ATK: l[CAP] |= 1
    return tuple(l)

def is_clean(c):
    return (c[CAP] == 0 and c[M] == 1 and c[S1] == 1 and c[S2] == 1
            and c[P1H] != 2 and c[RECH] != 2 and c[GCH] != 2 and c[Z] == 0)

# ----------------------------------------------------------------------------- game graph
def build(p, limit=3_000_000):
    start = (init_core(p), p.first, 0)
    idx = {start: 0}
    nodes = [start]
    succ = []
    i = 0
    second = 1 - p.first
    while i < len(nodes):
        core, turn, cnt = nodes[i]
        edges = []
        if core[CAP]:
            succ.append(edges); i += 1; continue          # terminal (permanent capture)
        if cnt < p.cap:
            for lab, c2 in moves(core, turn, p):
                if c2 == core: continue
                key = (c2, turn, cnt + 1)
                j = idx.get(key)
                if j is None:
                    j = len(nodes); idx[key] = j; nodes.append(key)
                edges.append((j, 0, lab))
        if turn == p.first:
            key = (core, second, 0); cost = 0
        else:
            key = (tick(core, p), p.first, 0); cost = 1
        j = idx.get(key)
        if j is None:
            j = len(nodes); idx[key] = j; nodes.append(key)
        edges.append((j, cost, "pass" if cost == 0 else "tick"))
        succ.append(edges)
        i += 1
        if len(nodes) > limit: raise RuntimeError("state limit")
    return nodes, succ

def solve(nodes, succ, goal, minplayer):
    """value[i] = ticks to reach goal under optimal play (min player minimises, other maximises)."""
    N = len(nodes)
    pred = [[] for _ in range(N)]
    remaining = [0] * N
    for i, es in enumerate(succ):
        remaining[i] = len(es)
        for (j, c, _) in es: pred[j].append((i, c))
    val = [INF] * N
    done = [False] * N
    maxv = [0] * N
    heap = []
    for i, (core, turn, cnt) in enumerate(nodes):
        if goal(core, turn):
            val[i] = 0; heapq.heappush(heap, (0, i))
    while heap:
        v, j = heapq.heappop(heap)
        if done[j]: continue
        done[j] = True
        for (i, c) in pred[j]:
            if done[i] or goal(*nodes[i][:2]): continue
            if nodes[i][1] == minplayer:
                cand = v + c
                if cand < val[i]: val[i] = cand; heapq.heappush(heap, (cand, i))
            else:
                remaining[i] -= 1
                if v + c > maxv[i]: maxv[i] = v + c
                if remaining[i] == 0:
                    val[i] = maxv[i]; heapq.heappush(heap, (maxv[i], i))
    return val

def goal_funds(c, t=None): return c[LOSS] == 1 or c[CAP] != 0
def goal_capture(c, t=None): return c[CAP] != 0
def goal_clean(c, t=None): return is_clean(c)
def goal_ospend(c, t): return t == OWN and c[CAP] == 0 and (c[M] & 1) and not locked(c)       # owner can send a transaction
def goal_gclean(c, t=None): return c[CAP] == 0 and c[B] == 0 and c[Z] == 0                            # guardian set free of attacker guardians

def analyse(p, trace=False):
    nodes, succ = build(p)
    res = {"states": len(nodes)}
    for name, goal, mp in (("funds", goal_funds, ATK), ("capture", goal_capture, ATK), ("clean", goal_clean, OWN),
                           ("ospend", goal_ospend, OWN), ("gclean", goal_gclean, OWN)):
        val = solve(nodes, succ, goal, mp)
        res[name] = val[0] if val[0] < INF else None
        if trace and val[0] < INF and val[0] >= 0:
            res[name + "_trace"] = extract(nodes, succ, val, mp)
    return res

def extract(nodes, succ, val, minplayer, maxlen=60):
    i, steps, t = 0, [], 0
    while val[i] > 0 and len(steps) < maxlen:
        core, turn, cnt = nodes[i]
        es = succ[i]
        pref = lambda e: 0 if e[2] in ("pass", "tick") else 1      # prefer doing nothing on ties
        if turn == minplayer:
            best = min(es, key=lambda e: (val[e[0]] + e[1], pref(e)))
        else:
            best = max(es, key=lambda e: (val[e[0]] + e[1], -pref(e)))
        if best[2] == "tick": t += 1; steps.append(f"-- tick {t} (+12h) --")
        elif best[2] != "pass": steps.append(f"t={t}: {best[2]}")
        i = best[0]
    return steps
