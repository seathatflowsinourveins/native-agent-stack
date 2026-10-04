#!/usr/bin/env python3
"""Part B gate C and the per-query metric (amendment 4): read one arm's saved MTEB predictions, compute nDCG@10 per
query against the frozen task's relevance judgements with pytrec_eval (MTEB's own dependency), write one JSON line per
query, and check that their mean, rounded to five decimals as MTEB rounds it, equals MTEB's reported ndcg_at_10. Queries are all 1,072 queries of the
test split; a query without a prediction scores 0. usage: partb_perquery.py <run dir>"""
import json
import pathlib
import sys

import pytrec_eval

import partb_arms

RUN = pathlib.Path(sys.argv[1])
record = json.loads((RUN / "run-record.json").read_text())
the_task = partb_arms.task()
the_task.load_data()
split = the_task.dataset["default"]["test"]
qrels = {}
for row in split["relevant_docs"].items() if isinstance(split["relevant_docs"], dict) else []:
    qrels[row[0]] = {doc: int(score) for doc, score in row[1].items()}
if not qrels:
    raise SystemExit("could not read the relevance judgements in the expected form; nothing is computed")
queries = [str(q) for q in split["queries"]["id"]]
files = sorted((RUN / "predictions").glob("*.json"))
if len(files) != 1:
    raise SystemExit(f"expected one prediction file, found {len(files)}")
predictions = json.loads(files[0].read_text())["default"]["test"]
run = {str(q): {str(d): float(s) for d, s in docs.items()} for q, docs in predictions.items()}
evaluator = pytrec_eval.RelevanceEvaluator({q: qrels[q] for q in qrels}, {"ndcg_cut.10"})
per_query = evaluator.evaluate({q: run.get(q, {}) for q in qrels})
rows = []
for q in queries:
    value = per_query.get(q, {}).get("ndcg_cut_10", 0.0) if q in qrels else None
    rows.append({"query": q, "ndcg_at_10": value, "has_judgement": q in qrels, "has_prediction": q in run})
scored = [r["ndcg_at_10"] for r in rows if r["ndcg_at_10"] is not None]
mean = sum(scored) / len(scored) if scored else None
reported = record.get("ndcg_at_10")
# MTEB reports nDCG@10 rounded to five decimals (mteb/_evaluators/retrieval_metrics.py:508); amendment 4a, B2
gate_c = reported is not None and mean is not None and abs(round(mean, 5) - reported) < 1e-9
(RUN / "per-query.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
summary = {"arm": record["arm"], "queries": len(queries), "with_judgement": len(qrels), "scored": len(scored),
           "mean_ndcg_at_10": mean, "mteb_ndcg_at_10": reported, "gate_c": gate_c,
           "missing_predictions": sum(1 for r in rows if r["has_judgement"] and not r["has_prediction"])}
(RUN / "per-query-summary.json").write_text(json.dumps(summary, indent=1) + "\n")
print(json.dumps(summary))
raise SystemExit(0 if gate_c else 1)
