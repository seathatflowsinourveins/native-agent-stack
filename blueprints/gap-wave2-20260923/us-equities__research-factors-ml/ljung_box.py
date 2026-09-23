#!/usr/bin/env python3
"""Ljung-Box diagnostic on reserved-fold training episode net labels (diagnostic only)."""
import json, sys, hashlib, importlib.metadata
from statsmodels.stats.diagnostic import acorr_ljungbox
r = json.load(open(sys.argv[1]))
out = {"statsmodels": importlib.metadata.version("statsmodels"), "source_sha256": hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest(), "arms": {}}
for arm in ["P6", "P6E5"]:
    labels = r["arms"][arm]["reserved"]["training_net_labels"]
    res = {}
    for cand, xs in labels.items():
        xs = [float(x) for x in xs]
        if len(set(xs)) < 2:
            res[cand] = {"n": len(xs), "note": "constant series (cash); test undefined"}
            continue
        lb = acorr_ljungbox(xs, lags=[1, 2, 3, 4], return_df=True)
        res[cand] = {"n": len(xs), "lb_stat": [round(v, 4) for v in lb["lb_stat"]], "lb_pvalue": [round(v, 4) for v in lb["lb_pvalue"]]}
    out["arms"][arm] = res
print(json.dumps(out, indent=1))
