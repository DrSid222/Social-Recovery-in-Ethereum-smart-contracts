"""Monotonicity check: for Argent and for the final design, a worse situation never gives a better result.
Worse = later owner reaction, slower guardians, more bad guardians. Attacker moves first. Prints MONOTONE or FAILURES."""
import itertools, functools
from model import *
FATE = (0, 1, 2, 3)      # lost, ok, stolen-gone, stolen-copy
INF = 10**6
def key(a): return tuple(INF if a[k] is None else a[k] for k in ("capture", "funds", "ospend"))
@functools.lru_cache(maxsize=None)
def argent(m, r, g, b): return analyse(P(1, slots=(m, 1, 1), r=r, g=g, b=b, first=ATK, zero=True))
@functools.lru_cache(maxsize=None)
def final(sl, r, g, b): return analyse(P(3, slots=sl, r=r, g=g, b=b, first=ATK, two_of_three=True, D1=2))
fails = n = 0
def worse_ok(a, b):
    """b (the worse situation) must not capture/steal later, nor spend sooner, than a."""
    return key(b)[0] <= key(a)[0] and key(b)[1] <= key(a)[1]
for name, fn, slots in (("Argent", lambda s, r, g, b: argent(s[0], r, g, b), [(m, 1, 1) for m in FATE]),
                        ("Final", final, [s for s in itertools.product(FATE, repeat=3) if s[1] <= s[2]])):
    for sl in slots:
        for g in range(3):
            for b in (0, 1, 3):
                res = [key(fn(sl, r, g, b)) for r in range(4)]
                for x, y in zip(res, res[1:]):
                    n += 1
                    if not (y[0] <= x[0] and y[1] <= x[1]): fails += 1; print("FAIL reaction", name, sl, g, b)
        for r in range(4):
            for b in (0, 1, 3):
                res = [key(fn(sl, r, g, b)) for g in range(3)]
                for x, y in zip(res, res[1:]):
                    n += 1
                    if not (y[0] <= x[0] and y[1] <= x[1]): fails += 1; print("FAIL guardian speed", name, sl, r, b)
        for r in range(4):
            for g in range(3):
                res = [key(fn(sl, r, g, b)) for b in range(4)]
                for x, y in zip(res, res[1:]):
                    n += 1
                    if not (y[0] <= x[0] and y[1] <= x[1]): fails += 1; print("FAIL bad guardians", name, sl, r, g)
print(f"comparisons: {n}")
print("MONOTONE" if fails == 0 else f"FAILURES: {fails}")
