"""Gap 5: replay the frozen 24-query fixture plus the frozen 8-query v2 extension with unmodified
ARB v0.2.1 rankers, add a preregistered leave-one-out score-threshold abstention policy and a
paired bootstrap between rankers. Usage (ARB runtime, PYTHONPATH=upstream/src):
  fixture_abstention_bootstrap.py REPO > result.json
"""
import hashlib
import json
import random
import subprocess
import sys
from pathlib import Path

from agent_retrieval_bench.baseline import (rank_chunks_bm25_with_scores, rank_chunks_for_ranker,
                                            rank_chunks_with_scores, recall_at, sample_metrics,
                                            unique_ranked_paths)
from agent_retrieval_bench.corpus import chunks_for_file

REPO = Path(sys.argv[1])
FIX = REPO / "blueprints/convergence-practice/local-fixture"
EXT = REPO / "blueprints/gap-wave2-20260923/us-equities__evaluation-experiments/fixture-v2/fixture-v2-extension.json"
BASE = "bf99d340f798bf72cc3104619edc482882eb423d"
SHA = {"fixture": "aea5e9616fb19eb1d2fd58ecfadf88ff087d7d2e79b4a70bc9f88207af9d0402",
       "manifest": "7bb986160b332e205208b6767b95b6f019423ffed1f50843534ff7e4272fdded",
       "extension": "6e3aef38502c2521856fd4a75fe9b701abb78082eaabad03e034097681a55401"}
SEED, RESAMPLES = 20260923, 10000


def checked(path, key):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != SHA[key]:
        raise ValueError("frozen hash mismatch: " + key)
    return json.loads(raw)


fixture, manifest, ext = checked(FIX / "fixture.json", "fixture"), checked(FIX / "corpus-manifest.json", "manifest"), checked(EXT, "extension")
docs = []
for item in manifest["files"]:
    raw = subprocess.run(["git", "-C", str(REPO), "show", f"{BASE}:{item['path']}"], check=True,
                         capture_output=True, timeout=10).stdout
    if hashlib.sha256(raw).hexdigest() != item["source_sha256"]:
        raise ValueError("corpus hash mismatch")
    docs.append((item["path"], raw.decode()))
maximum = max(len(t) for _, t in docs)
chunks = [c for p, t in docs for c in chunks_for_file("seathatflowsinourveins/native-agent-stack", BASE, p, t, max_chunk_chars=maximum)]
paths = {p for p, _ in docs}
queries = fixture["queries"] + ext["queries"]
assert len(queries) == 32 and sum(q["expected_abstention"] for q in queries) == 12
SCORED = {"lexical": rank_chunks_with_scores, "bm25": rank_chunks_bm25_with_scores}
retained = {(r["sample_id"], r["ranker"]): r for r in json.loads((FIX / "rankings.json").read_text())["results"]}

rows = {r: [] for r in SCORED}
replay_mismatch = []
for ranker, scored_fn in SCORED.items():
    for q in queries:
        scored = scored_fn(q["query"], chunks)
        ranked = [c for _, c in scored]
        if ranked != rank_chunks_for_ranker(q["query"], chunks, ranker):
            raise ValueError("scored ranking differs from native ranker order")
        files = unique_ranked_paths(ranked)
        gold = set(q["expected_files"])
        top = [s for s, _ in scored]
        row = {"id": q["id"], "answerable": bool(gold), "top1": top[0], "top2": top[1],
               "ratio": top[0] / top[1] if top[1] > 0 else float("inf"), "ranked_files": files}
        if gold:
            m = sample_metrics(sorted(gold), ranked)
            row["MRR"], row["R1"] = m["MRR"], recall_at(gold, files, 1)
        old = retained.get((q["id"], ranker))
        if old is not None and old["ranked_files"] != files:
            replay_mismatch.append((q["id"], ranker))
        rows[ranker].append(row)


def loo_decisions(values, answerable):
    decisions, thresholds = [], []
    for i in range(len(values)):
        train = [(v, a) for j, (v, a) in enumerate(zip(values, answerable)) if j != i]
        cands = sorted({v for v, _ in train})
        grid = [float("-inf")] + [(a + b) / 2 for a, b in zip(cands, cands[1:])] + [float("inf")]
        best = max(grid, key=lambda t: (sum((v < t) != a for v, a in train), -grid.index(t)))
        thresholds.append(best)
        decisions.append(values[i] < best)  # True = abstain
    return decisions, thresholds


summary = {}
for ranker, rs in rows.items():
    ans = [r["answerable"] for r in rs]
    pos = [r for r in rs if r["answerable"]]
    out = {"positive_n": len(pos), "MRR": sum(r["MRR"] for r in pos) / len(pos),
           "Recall@1": sum(r["R1"] for r in pos) / len(pos)}
    for policy in ("top1", "ratio"):
        dec, thr = loo_decisions([r[policy] for r in rs], ans)
        for r, d in zip(rs, dec):
            r[f"abstain_{policy}"] = d
            r[f"correct_{policy}"] = d != r["answerable"]
        n_u = sum(not a for a in ans)
        out[policy] = {"abstention_rate": sum(dec) / len(dec),
                       "abstention_recall_unanswerable": sum(d for d, a in zip(dec, ans) if not a) / n_u,
                       "false_abstention_answerable": sum(d for d, a in zip(dec, ans) if a) / (len(ans) - n_u),
                       "decision_accuracy": sum(d != a for d, a in zip(dec, ans)) / len(ans),
                       "loo_threshold_range": [min(thr), max(thr)]}
    summary[ranker] = out


def bootstrap(values_a, values_b):
    rng = random.Random(SEED)
    n, diffs = len(values_a), []
    for _ in range(RESAMPLES):
        idx = [rng.randrange(n) for _ in range(n)]
        diffs.append(sum(values_b[i] - values_a[i] for i in idx) / n)
    diffs.sort()
    return {"mean_difference": sum(b - a for a, b in zip(values_a, values_b)) / n,
            "ci95": [diffs[int(0.025 * RESAMPLES)], diffs[int(0.975 * RESAMPLES) - 1]], "n": n}


lp = [r for r in rows["lexical"] if r["answerable"]]; bp = [r for r in rows["bm25"] if r["answerable"]]
assert [r["id"] for r in lp] == [r["id"] for r in bp]
boot = {"bm25_minus_lexical": {
    "MRR": bootstrap([r["MRR"] for r in lp], [r["MRR"] for r in bp]),
    "Recall@1": bootstrap([r["R1"] for r in lp], [r["R1"] for r in bp]),
    "decision_accuracy_top1": bootstrap([float(r["correct_top1"]) for r in rows["lexical"]], [float(r["correct_top1"]) for r in rows["bm25"]]),
    "decision_accuracy_ratio": bootstrap([float(r["correct_ratio"]) for r in rows["lexical"]], [float(r["correct_ratio"]) for r in rows["bm25"]]),
}, "seed": SEED, "resamples": RESAMPLES, "method": "paired percentile bootstrap over queries"}
b = boot["bm25_minus_lexical"]
promotion = b["MRR"]["ci95"][0] > 0 and b["decision_accuracy_top1"]["ci95"][0] >= 0
print(json.dumps({"inputs": SHA, "queries": 32, "answerable": 20, "unanswerable": 12, "chunks": len(chunks),
                  "replay_ranking_mismatches_vs_2026_09_20": replay_mismatch,
                  "replay_positive_metrics": {k: {"MRR": v["MRR"], "Recall@1": v["Recall@1"]} for k, v in summary.items()},
                  "summary": summary, "bootstrap": boot,
                  "default_promotion_rule": "MRR CI lower bound > 0 and top1 decision-accuracy CI lower bound >= 0",
                  "default_promotion_claim_follows": promotion,
                  "rows": {k: [{kk: vv for kk, vv in r.items() if kk != "ranked_files"} for r in v] for k, v in rows.items()}},
                 indent=1, default=str))
