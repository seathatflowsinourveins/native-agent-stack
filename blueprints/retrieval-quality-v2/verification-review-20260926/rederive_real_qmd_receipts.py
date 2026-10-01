"""Re-derives the Arm A rows of the real-qmd check receipts in repair-review-20260926/.

For every results-*.json in the sibling directory repair-review-20260926/, each Arm A row must name a
native record whose retained stdout hashes to the row's stdout_sha256, whose top 10 hits map to pinned
corpus files with matching docids in the row's ranked_paths order, and whose nDCG@10 equals the row's
value, all recomputed here from queries.json. Standard library only; reads committed files.

Usage: python3 rederive_real_qmd_receipts.py
"""
import hashlib
import json
import math
import pathlib

BLUEPRINT = pathlib.Path(__file__).resolve().parent.parent
PREFIX = {"rqv2-foundation": "blueprints/us-equities", "rqv2-catalog": "catalogs/us-equities",
          "rqv2-observability": "observability"}
sealed = json.loads((BLUEPRINT / "queries.json").read_text(encoding="utf-8"))
queries = {q["id"]: q for q in sealed["queries"]}
pins = {d["path"]: d["sha256"] for d in sealed["corpus"]}


def dcg(grades):
    return sum((2 ** g - 1) / math.log2(i + 2) for i, g in enumerate(grades))


report = {}
for path in sorted((BLUEPRINT / "repair-review-20260926").glob("results-*.json")):
    receipt = json.loads(path.read_text(encoding="utf-8"))
    native = json.loads((path.parent / receipt["outputs"]["native"]).read_text(encoding="utf-8"))
    records = {r["id"]: r for r in native["records"]}
    rows, mismatches = receipt["arm_a"]["per_query"], []
    for row in rows:
        record = records[row["native_record_id"]]
        ok = hashlib.sha256(record["stdout"].encode("utf-8")).hexdigest() == row["stdout_sha256"]
        ranked = []
        for hit in json.loads(record["stdout"])[:10]:
            collection, relative = hit["file"][len("qmd://"):].split("?")[0].split("/", 1)
            repository_path = f"{PREFIX[collection]}/{relative}"
            ok = ok and pins[repository_path][:6] == hit["docid"].lstrip("#")
            ranked.append(repository_path)
        grades = {r["path"]: r["grade"] for r in queries[row["id"]]["relevance"]}
        ndcg = dcg([grades.get(p, 0) for p in ranked]) / dcg(sorted(grades.values(), reverse=True)[:10])
        ok = ok and ranked == row["ranked_paths"] and abs(ndcg - row["ndcg_at_10"]) < 1e-12
        if not ok:
            mismatches.append(row["id"])
    report[path.name] = {
        "schema_version": receipt["schema_version"],
        "harness_sha256": receipt["harness"]["sha256"],
        "status": receipt["status"],
        "arm_a_rows": len(rows),
        "mismatched_rows": mismatches,
        "arm_a_mean_ndcg_at_10": (sum(r["ndcg_at_10"] for r in rows) / len(rows)) if rows else None,
    }
print(json.dumps(report, indent=2))
