#!/usr/bin/env python3
"""Part B decision statistic (amendment 4): the difference of mean nDCG@10 between two arms over the same queries,
with a 95% paired bootstrap interval over queries (10,000 resamples, seed 20260927). Refuses two runs whose query sets
differ. usage: partb_bootstrap.py --challenger <run dir> --baseline <run dir>; the difference is challenger minus
baseline, and a run that failed gate C is refused."""
import json
import pathlib
import random
import sys


def load(run):
    rows = [json.loads(line) for line in (pathlib.Path(run) / "per-query.jsonl").read_text().splitlines() if line]
    return {r["query"]: r["ndcg_at_10"] for r in rows if r["ndcg_at_10"] is not None}


import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--challenger", required=True)
parser.add_argument("--baseline", required=True)
args = parser.parse_args()
for run in (args.challenger, args.baseline):
    summary = json.loads((pathlib.Path(run) / "per-query-summary.json").read_text())
    if not summary.get("gate_c"):
        raise SystemExit(f"{pathlib.Path(run).name} failed gate C; it is not compared")
a, b = load(args.challenger), load(args.baseline)
if set(a) != set(b):
    raise SystemExit(f"the two runs scored different query sets ({len(set(a) ^ set(b))} differ)")
queries = sorted(a)


def difference(ids):
    return sum(a[q] for q in ids) / len(ids) - sum(b[q] for q in ids) / len(ids)


rng = random.Random(20260927)
draws = sorted(difference([rng.choice(queries) for _ in queries]) for _ in range(10000))
low, high = draws[249], draws[9749]
mean_a, mean_b = sum(a.values()) / len(a), sum(b.values()) / len(b)
print(json.dumps({"challenger": pathlib.Path(args.challenger).name, "baseline": pathlib.Path(args.baseline).name, "queries": len(queries),
                  "mean_challenger": round(mean_a, 6), "mean_baseline": round(mean_b, 6), "difference": round(mean_a - mean_b, 6),
                  "interval_95": [round(low, 6), round(high, 6)], "resamples": 10000, "seed": 20260927,
                  "tie": low <= 0 <= high, "above_zero": low > 0}))
