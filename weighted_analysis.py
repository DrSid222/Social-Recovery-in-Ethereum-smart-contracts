"""Scenario-weighted analysis: turn per-key yearly loss / theft probabilities into scenario probabilities, weight the solver's outcomes.
ALL RATES ARE ILLUSTRATIVE ASSUMPTIONS (no public source gives per-user yearly rates for key loss vs theft; see WEIGHTED_RESULTS.md).
Outcome classes per scenario (from the exact solver, attacker first, 3 honest guardians):
  TAKEOVER = the attacker ends up with the wallet (permanent)
  DRAIN    = funds drained at once but the owner gets the wallet back (no spending limit in any design)
  LOCKOUT  = no theft but the owner can never spend again
  OK       = owner can spend again, after a downtime in hours (time with no way to spend)
"""
import itertools, csv, functools, json
from model import *

FATE = {"ok": 1, "lost": 0, "gone": 2, "copy": 3}

@functools.lru_cache(maxsize=None)
def solve(ver, name, m, s1, s2, r, g=1, b=0):
    kw = {}
    if name == "Argent": ver, kw = 1, dict(zero=True); s1 = s2 = 1
    if name == "Final": ver, kw = 3, dict(two_of_three=True, D1=2)
    a = analyse(P(ver, slots=(m, s1, s2), r=r, g=g, b=b, **kw))
    if a["capture"] is not None: return ("TAKEOVER", None)
    if a["funds"] is not None: return ("DRAIN", None)
    if a["ospend"] is None: return ("LOCKOUT", None)
    return ("OK", a["ospend"] * 12)      # hours until the owner can spend again

DOWN_G = 2      # guardians take 24h to gather when nobody is racing (used only for the downtime metric)

def hours_from_action(name, mf, a, b, bb):
    cls, h = solve(3 if name != 'Argent' else 1, name, FATE[mf], FATE[a] if a != '-' else 1, FATE[b] if b != '-' else 1, 0, DOWN_G, bb)
    return h

def dist_M(pL, pT, copy):
    return {"copy": pT * copy, "gone": pT * (1 - copy), "lost": (1 - pT) * pL, "ok": (1 - pT) * (1 - pL)}

def dist_S(pL, pT, rho):
    """joint over (S1,S2) in {ok,lost,copy}: thefts first (correlated), then independent losses among the rest."""
    c2 = max(rho, pT)
    pat = {(1, 1): pT * c2, (1, 0): pT - pT * c2, (0, 1): pT - pT * c2}
    pat[(0, 0)] = 1 - sum(pat.values())
    out = {}
    for (t1, t2), pp in pat.items():
        for l1, l2 in itertools.product((0, 1), repeat=2):
            if (t1 and l1) or (t2 and l2): continue
            pr = pp * (pL if l1 else (1 - pL) if not t1 else 1) * (pL if l2 else (1 - pL) if not t2 else 1)
            s1 = "copy" if t1 else ("lost" if l1 else "ok"); s2 = "copy" if t2 else ("lost" if l2 else "ok")
            out[(s1, s2)] = out.get((s1, s2), 0) + pr
    return out

def repair(ds, q):
    """what-if for the 2-of-3 rule: a lost backup was already replaced (by M + the other S) with probability q before the next incident."""
    out = {}
    for (a, b), pp in ds.items():
        opts_a = [("ok", q), ("lost", 1 - q)] if a == "lost" else [(a, 1)]
        opts_b = [("ok", q), ("lost", 1 - q)] if b == "lost" else [(b, 1)]
        for (x, px) in opts_a:
            for (y, py) in opts_b:
                out[(x, y)] = out.get((x, y), 0) + pp * px * py
    return out

def run(name, pLM=0.05, pTM=0.03, copy=0.9, pLS=0.05, pTS=0.003, rho=0.1, r=1, beta=0.02, detail=False, q=0.0):
    dm = dist_M(pLM, pTM, copy); ds = dist_S(pLS, pTS, rho)
    if name == "Final" and q > 0: ds = repair(ds, q)
    from math import comb
    db = {k: comb(3, k) * beta ** k * (1 - beta) ** (3 - k) for k in range(4)}      # number of bad guardians among 3
    res = {"TAKEOVER": 0.0, "DRAIN": 0.0, "LOCKOUT": 0.0, "OK": 0.0}; down = 0.0; okp = 0.0; contrib = []
    if name == "EOA":      # one key, no recovery
        res["TAKEOVER"] = dm["copy"] + dm["gone"]; res["LOCKOUT"] = dm["lost"]; res["OK"] = dm["ok"]
        return (res, 0.0, []) if detail else res
    if name == "Argent":
        for mf, pm0 in dm.items():
            for bb, pb in db.items():
                pm = pm0 * pb
                cls, h = solve(1, name, FATE[mf], 1, 1, r, b=bb)
                res[cls] += pm
                if cls == "OK": h = hours_from_action(name, mf, "-", "-", bb); down += pm * h; okp += pm
                contrib.append((pm, mf + f" b={bb}", "-", "-", cls, h))
    else:
        for mf, pm in dm.items():
            for (a, b), ps in ds.items():
                for bb, pb in db.items():
                    p = pm * ps * pb
                    cls, h = solve(3, name, FATE[mf], FATE[a], FATE[b], r, b=bb)
                    res[cls] += p
                    if cls == "OK": h = hours_from_action(name, mf, a, b, bb); down += p * h; okp += p
                    contrib.append((p, mf + f" b={bb}", a, b, cls, h))
    res["E_down_h"] = down      # expected hours of downtime per year (probability-weighted over scenarios that end OK)
    assert abs(sum(res[k] for k in ("TAKEOVER", "DRAIN", "LOCKOUT", "OK")) - 1) < 1e-9, res      # probabilities must sum to 1
    return (res, down, contrib) if detail else res

DESIGNS = ["EOA", "Argent", "Final"]

if __name__ == "__main__":
    rows = []
    base = dict(pLM=0.05, pTM=0.03, copy=0.9, pLS=0.05, pTS=0.003, rho=0.1, r=1, beta=0.02)
    print("BASE ASSUMPTIONS (illustrative):", base)
    print(f"{'design':<20}{'takeover':>10}{'drain only':>12}{'lockout':>10}{'ok':>9}{'E[downtime h/yr]':>20}")
    for d in DESIGNS:
        res, md, _ = run(d, detail=True, **base)
        print(f"{d:<20}{res['TAKEOVER']*100:>9.3f}%{res['DRAIN']*100:>11.3f}%{res['LOCKOUT']*100:>9.3f}%{res['OK']*100:>8.2f}%{md:>19.2f}")
        rows.append(dict(sweep="base", param="", value="", design=d, takeover=res["TAKEOVER"], drain=res["DRAIN"], lockout=res["LOCKOUT"], ok=res["OK"], e_down_h=md))
    res, md, contrib = run("Final", detail=True, **base)
    print("\nFinal design residual risk by scenario (M / S1 / S2 -> outcome), top contributors:")
    for p, mf, a, b, cls, h in sorted([c for c in contrib if c[4] != "OK"], reverse=True)[:10]:
        print(f"  {p*100:8.4f}%  {mf}/{a}/{b} -> {cls}")
    res, md, contrib = run("Argent", detail=True, **base)
    print("\nArgent residual risk by scenario:")
    for p, mf, a, b, cls, h in sorted([c for c in contrib if c[4] != "OK"], reverse=True):
        print(f"  {p*100:8.4f}%  M {mf} -> {cls}")
    print("\nArgent downtime sources:", [(mf, h) for p, mf, a, b, cls, h in contrib if cls == "OK" and h])
    # sensitivity
    grid = {"pTM": [0.005, 0.02, 0.05, 0.10], "pLM": [0.02, 0.05, 0.10, 0.20], "copy": [0.5, 0.9, 1.0], "pLS": [0.02, 0.05, 0.10, 0.20],
            "pTS": [0.0005, 0.003, 0.01, 0.03], "rho": [0.0, 0.1, 0.5, 1.0], "r": [0, 1, 2, 4], "beta": [0.0, 0.02, 0.05, 0.10, 0.20]}
    print("\nSENSITIVITY (one parameter varied, others at base): takeover % / lockout % / E[downtime h per year]")
    for prm, vals in grid.items():
        print(f"\n{prm}")
        print(f"  {'value':<8}" + "".join(f"{d:<34}" for d in ("Argent", "Final")))
        for v in vals:
            kw = dict(base); kw[prm] = v
            line = f"  {v:<8}"
            for d in ("Argent", "Final"):
                res = run(d, **kw)
                line += f"{res['TAKEOVER']*100:6.3f}% /{res['LOCKOUT']*100:6.3f}% /{res['E_down_h']:5.2f}h".ljust(34)
                rows.append(dict(sweep="sens", param=prm, value=v, design=d, takeover=res["TAKEOVER"], drain=res["DRAIN"], lockout=res["LOCKOUT"], ok=res["OK"], e_down_h=res["E_down_h"]))
            print(line)
    print("\nREPAIR WHAT-IF (final design only): q = chance a lost backup was already replaced before the next incident")
    for q in (0.0, 0.5, 0.9, 1.0):
        res = run("Final", q=q, **base)
        print(f"  q={q}: takeover {res['TAKEOVER']*100:.3f}%  lockout {res['LOCKOUT']*100:.4f}%  down {res['E_down_h']:.2f}h")
        rows.append(dict(sweep="repair", param="q", value=q, design="Final", takeover=res["TAKEOVER"], drain=res["DRAIN"], lockout=res["LOCKOUT"], ok=res["OK"], e_down_h=res["E_down_h"]))
    for pls in (0.10, 0.20):
        for q in (0.0, 0.9):
            kw = dict(base); kw["pLS"] = pls
            res = run("Final", q=q, **kw)
            print(f"  backups lost {pls}/yr, q={q}: lockout {res['LOCKOUT']*100:.4f}%  ")
    with open("results/I_weighted.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
