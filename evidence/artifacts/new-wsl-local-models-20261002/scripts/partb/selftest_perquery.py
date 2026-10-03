#!/usr/bin/env python3
"""Mechanics check of partb_perquery.py without any model. Synthetic runs from the frozen task's own judgements: a
perfect ranking, an empty one, a ranking with a fixed pseudo-random order whose score is not a round number (its
reference value computed by MTEB's own calculate_retrieval_scores, then rounded as MTEB reports it), and the same run
with a misreported score. Expected: gate C passes for the first three and fails for the fourth. Writes only under a
temporary folder."""
import json
import pathlib
import random
import subprocess
import sys
import tempfile

from mteb._evaluators.retrieval_metrics import calculate_retrieval_scores

import partb_arms

the_task = partb_arms.task()
the_task.load_data()
split = the_task.dataset["default"]["test"]
qrels = split["relevant_docs"]
corpus_ids = [str(d) for d in split["corpus"]["id"]]
here = pathlib.Path(__file__).parent


def make(root, name, predictions, reported):
    run = root / name
    (run / "predictions").mkdir(parents=True)
    (run / "predictions" / f"{partb_arms.TASK}_predictions.json").write_text(
        json.dumps({"mteb_model_meta": {"model_name": "synthetic", "revision": "none"}, "default": {"test": predictions}}))
    (run / "run-record.json").write_text(json.dumps({"arm": name, "ndcg_at_10": reported}))
    done = subprocess.run([sys.executable, "-B", str(here / "partb_perquery.py"), str(run)], capture_output=True, text=True)
    print(name, "exit", done.returncode, done.stdout.strip()[:260])


rng = random.Random(20260927)
mixed = {}
for q, docs in qrels.items():
    pool = list(docs) + rng.sample(corpus_ids, 30)
    rng.shuffle(pool)
    mixed[q] = {d: float(len(pool) - i) for i, d in enumerate(pool)}
reference = calculate_retrieval_scores(mixed, qrels, (1, 3, 5, 10, 20, 100, 1000)).ndcg["NDCG@10"]
print("MTEB's own nDCG@10 for the mixed run:", reference)
with tempfile.TemporaryDirectory() as tmp:
    root = pathlib.Path(tmp)
    make(root, "perfect", {q: {d: float(10 + s) for d, s in docs.items()} for q, docs in qrels.items()}, 1.0)
    make(root, "empty", {q: {"no-such-document": 1.0} for q in qrels}, 0.0)
    make(root, "mixed", mixed, reference)
    make(root, "mixed-misreported", mixed, round(reference + 0.00002, 5))
