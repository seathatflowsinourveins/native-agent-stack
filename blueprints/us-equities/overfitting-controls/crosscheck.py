"""Independent recomputation with numpy (different code path from overfitting.py); normal quantiles from statistics.NormalDist, CDF from math.erf."""
import json, sys, itertools, math
from decimal import Decimal
import numpy as np
from statistics import NormalDist
ppf = NormalDist().inv_cdf
cdf = lambda z: 0.5 * (1 + math.erf(z / math.sqrt(2)))

def rankdata(a):
    a = np.asarray(a); r = np.empty(len(a))
    for i, x in enumerate(a):
        r[i] = (a < x).sum() + ((a == x).sum() + 1) / 2
    return r

root = sys.argv[1] if len(sys.argv) > 1 else "."
ledger = json.load(open(root + "/evidence/artifacts/gap-wave2-20260923/us-equities__portfolio-risk/raw/3/regenerated/run-1/candidate-ledger.json"))
trials = ["momentum20", "momentum60", "momentum120", "cash"]
v = {}
for r in ledger:
    if r["status"] == "observed" and r["decision"] <= "2020-12-31":
        v[(r["candidate"], r["decision"])] = float(Decimal(r["net_proxy"]))
dates = sorted({d for c, d in v})
M = np.array([[v[(c, d)] for c in trials] for d in dates])
sd = M.std(axis=0)
sr = np.where(sd > 0, M.mean(axis=0) / np.where(sd > 0, sd, 1), 0.0)
b = int(np.argmax(sr)); x = M[:, b]; T = len(x)
d = x - x.mean(); g3 = (d**3).mean() / (d**2).mean()**1.5; g4 = (d**4).mean() / (d**2).mean()**2
V = np.var(sr, ddof=1); N = len(trials); g = np.euler_gamma
sr0 = math.sqrt(V) * ((1 - g) * ppf(1 - 1 / N) + g * ppf(1 - 1 / (N * np.e)))
dsr = cdf((sr[b] - sr0) * math.sqrt(T - 1) / math.sqrt(1 - g3 * sr[b] + (g4 - 1) / 4 * sr[b] ** 2))
# PBO, S=16, mean metric, direct slicing
S = 16; size = T // S; U = M[T - size * S:]; blocks = np.split(U, S)
lam = []
for J in itertools.combinations(range(S), S // 2):
    tr = np.vstack([blocks[i] for i in J]); te = np.vstack([blocks[i] for i in range(S) if i not in J])
    ism, osm = tr.mean(0), te.mean(0)
    n = int(np.flatnonzero(ism == ism.max())[0])
    w = rankdata(osm)[n] / (len(trials) + 1)
    lam.append(math.log(w / (1 - w)))
lam = np.array(lam)
print(json.dumps({"T": T, "selected": trials[b], "sr": sr[b], "sr0": sr0, "dsr": dsr,
                  "pbo": float((lam <= 0).mean()), "combinations": len(lam),
                  "numpy": np.__version__}, indent=1))
