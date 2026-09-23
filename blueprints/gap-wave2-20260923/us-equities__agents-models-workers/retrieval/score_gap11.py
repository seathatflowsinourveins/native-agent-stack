#!/usr/bin/env python3
"""Exact intended-source recall@1/3/5 and MRR (<=10 documents) for the twelve frozen
queries, per lane. SocratiCode chunk hits are deduplicated to documents in rank order.
Usage: score_gap11.py FIXTURE SOCRATICODE_RAW AIMEMORY_RAW OUT_JSON"""
import json, sys
fx = {q["id"]: q["expected_files"][0] for q in json.load(open(sys.argv[1]))["queries"]}

def docs_sc(r):
    seen = []
    for h in r["hits"]:
        if h["file"] not in seen:
            seen.append(h["file"])
    return seen[:10]

def docs_aim(r):
    return [h["path"] for h in (r["parsed"] or [])][:10]

def score(results, docs_of):
    per = []
    for r in results:
        d = docs_of(r); gold = fx[r["id"]]
        rank = d.index(gold) + 1 if gold in d else None
        per.append({"id": r["id"], "gold": gold, "rank": rank, "top3": d[:3]})
    n = len(per)
    s = {f"recall@{k}": f"{sum(1 for p in per if p['rank'] and p['rank'] <= k)}/{n}" for k in (1, 3, 5)}
    s["mrr@10"] = round(sum(1 / p["rank"] for p in per if p["rank"]) / n, 5)
    return {"summary": s, "per_query": per}

out = {"socraticode": score(json.load(open(sys.argv[2]))["results"], docs_sc),
       "ai_memory_cli_search": score(json.load(open(sys.argv[3]))["results"], docs_aim),
       "qmd_recorded_baseline": {"recall@1": "5/12", "recall@3": "8/12", "recall@5": "9/12", "mrr@10": 0.56875,
                                 "source": "blueprints/us-equities/retrieval-evaluation/README.md (exact intended-source audit)"}}
json.dump(out, open(sys.argv[4], "w"), indent=1)
for lane in ("socraticode", "ai_memory_cli_search"):
    print(lane, json.dumps(out[lane]["summary"]), [(p["id"], p["rank"]) for p in out[lane]["per_query"]])
