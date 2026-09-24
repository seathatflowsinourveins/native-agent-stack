#!/usr/bin/env python3
"""Index the FOMC corpus into a disposable Qdrant collection and evaluate the sealed
dated queries. Embeddings: the adopted SocratiCode profile's Nemotron-3-Embed-1B endpoint
(read-only /v1/embeddings calls), passage/query prefixes as in that profile.

Arms: dense (no filter) and dense+date_filter (month/year parsed from the query text,
applied as a Qdrant payload range filter on date_int).
Usage: index_and_eval.py CORPUS_JSONL QUERIES_JSON OUT_JSON
"""
import calendar
import json
import re
import sys
import time
import urllib.request

QDRANT = "http://127.0.0.1:27333"
EMBED = "http://127.0.0.1:8231/v1/embeddings"
MODEL = "nvidia/Nemotron-3-Embed-1B-BF16"
COLL = "g2amw_fomc_statements"
import os
if os.environ.get("FOMC_ABLATE_DATES") == "1":
    COLL = "g2amw_fomc_statements_nodate"
MONTHS = {m: i for i, m in enumerate(calendar.month_name) if m}


def call(url, body=None, method="POST"):
    req = urllib.request.Request(url, data=None if body is None else json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"}, method=method)
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def embed(texts):
    out = call(EMBED, {"model": MODEL, "input": texts})
    return [d["embedding"] for d in sorted(out["data"], key=lambda d: d["index"])]


def month_filter(query):
    m = re.search(r"\b(" + "|".join(MONTHS) + r") (\d{4})\b", query)
    if not m:
        return None
    y, mo = int(m.group(2)), MONTHS[m.group(1)]
    last = calendar.monthrange(y, mo)[1]
    return {"must": [{"key": "date_int", "range": {"gte": y * 10000 + mo * 100 + 1, "lte": y * 10000 + mo * 100 + last}}]}


def main():
    docs = [json.loads(l) for l in open(sys.argv[1])]
    if os.environ.get("FOMC_ABLATE_DATES") == "1":
        # Late-preregistered ablation: strip datelines and explicit full dates from the indexed text.
        dl = re.compile(r"\b(" + "|".join(MONTHS) + r") \d{1,2}, \d{4}\b")
        for d in docs:
            t = re.sub(r"^.*?For release at [^S]*Share", " ", d["text"], count=1)
            d["text"] = re.sub(r"\s+", " ", dl.sub(" ", t)).strip()
    queries = json.load(open(sys.argv[2]))["queries"]
    t0 = time.time()
    try:
        call(f"{QDRANT}/collections/{COLL}", method="DELETE")
    except Exception:
        pass
    vecs = embed(["passage: " + d["text"] for d in docs])
    call(f"{QDRANT}/collections/{COLL}", {"vectors": {"size": len(vecs[0]), "distance": "Cosine"}}, method="PUT")
    points = [{"id": i + 1, "vector": v, "payload": {"doc_id": d["doc_id"], "date": d["date"],
               "date_int": int(d["date"].replace("-", "")), "url": d["url"], "target_range": d["target_range"]}}
              for i, (d, v) in enumerate(zip(docs, vecs))]
    call(f"{QDRANT}/collections/{COLL}/points?wait=true", {"points": points}, method="PUT")
    index_s = round(time.time() - t0, 2)
    qv = embed(["query: " + q["query"] for q in queries])
    results = {"dense": [], "dense_date_filter": []}
    for q, v in zip(queries, qv):
        for arm in results:
            body = {"vector": v, "limit": 5, "with_payload": True}
            if arm == "dense_date_filter":
                f = month_filter(q["query"])
                if f:
                    body["filter"] = f
            hits = call(f"{QDRANT}/collections/{COLL}/points/search", body)["result"]
            ranked = [{"doc_id": h["payload"]["doc_id"], "date": h["payload"]["date"], "score": round(h["score"], 5),
                       "target_range": h["payload"]["target_range"]} for h in hits]
            rank = next((i + 1 for i, h in enumerate(ranked) if h["doc_id"] == q["gold_doc"]), None)
            top = ranked[0] if ranked else None
            results[arm].append({"id": q["id"], "gold_date": q["gold_date"], "rank": rank,
                                 "top1_date": top and top["date"], "top1_date_correct": bool(top and top["date"] == q["gold_date"]),
                                 "top1_answer_correct": bool(top and top["target_range"] == q["gold_target_range"]),
                                 "ranked": ranked})
    summary = {}
    for arm, rows in results.items():
        n = len(rows)
        summary[arm] = {"queries": n,
                        **{f"recall@{k}": round(sum(1 for r in rows if r["rank"] and r["rank"] <= k) / n, 4) for k in (1, 3, 5)},
                        "mrr@5": round(sum(1 / r["rank"] for r in rows if r["rank"]) / n, 4),
                        "top1_date_correct": round(sum(r["top1_date_correct"] for r in rows) / n, 4),
                        "top1_answer_correct": round(sum(r["top1_answer_correct"] for r in rows) / n, 4)}
    out = {"collection": COLL, "qdrant": QDRANT, "embedding_model": MODEL, "docs": len(docs),
           "vector_dim": len(vecs[0]), "index_seconds": index_s,
           "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "summary": summary, "results": results}
    json.dump(out, open(sys.argv[3], "w"), indent=1)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
