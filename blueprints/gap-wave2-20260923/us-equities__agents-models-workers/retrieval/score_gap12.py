#!/usr/bin/env python3
"""Score gap-12 SocratiCode results against exhaustive pattern-defined gold.

A gold line is recovered at k when one of the top-k chunks has the same file and a
line range containing it. Reports hit@k (>=1 gold recovered), MRR (first chunk that
covers any gold line, within the returned list), completeness@k (recovered/gold)
and fully-complete@k (all gold recovered).
Usage: score_gap12.py QUERIES_JSON RAW_JSON OUT_JSON
"""
import json
import sys


def main():
    queries = {q["id"]: q for q in json.load(open(sys.argv[1]))["queries"]}
    raw = json.load(open(sys.argv[2]))
    per = []
    for r in raw["results"]:
        q = queries[r["id"]]
        gold = [(g["file"], g["line"]) for g in q["gold_locations"]]
        hits = r["hits"]

        def covered(k):
            return {(f, ln) for f, ln in gold for h in hits[:k] if h["file"] == f and h["start"] <= ln <= h["end"]}

        rank = next((i + 1 for i, h in enumerate(hits)
                     if any(h["file"] == f and h["start"] <= ln <= h["end"] for f, ln in gold)), None)
        row = {"id": r["id"], "gold_count": len(gold), "returned": len(hits), "first_gold_rank": rank}
        for k in (1, 5, 10):
            c = covered(k)
            row[f"hit@{k}"] = int(bool(c))
            row[f"completeness@{k}"] = round(len(c) / len(gold), 4)
        row["fully_complete@10"] = int(row["completeness@10"] == 1.0)
        row["missed_at_10"] = sorted({f"{f}:{ln}" for f, ln in gold} - {f"{f}:{ln}" for f, ln in covered(10)})
        per.append(row)
    n = len(per)
    summary = {"queries": n, "gold_locations": sum(p["gold_count"] for p in per),
               "mrr@10": round(sum(1 / p["first_gold_rank"] for p in per if p["first_gold_rank"]) / n, 4)}
    for k in (1, 5, 10):
        summary[f"hit@{k}"] = round(sum(p[f"hit@{k}"] for p in per) / n, 4)
        summary[f"mean_completeness@{k}"] = round(sum(p[f"completeness@{k}"] for p in per) / n, 4)
    summary["fully_complete@10"] = round(sum(p["fully_complete@10"] for p in per) / n, 4)
    summary["micro_completeness@10"] = round(
        sum(p["gold_count"] * p["completeness@10"] for p in per) / summary["gold_locations"], 4)
    single = [p for p in per if p["gold_count"] == 1]
    multi = [p for p in per if p["gold_count"] > 1]
    summary["single_location_queries"] = len(single)
    summary["multi_location_queries"] = len(multi)
    summary["mean_completeness@10_multi"] = round(sum(p["completeness@10"] for p in multi) / len(multi), 4) if multi else None
    json.dump({"summary": summary, "per_query": per}, open(sys.argv[3], "w"), indent=1)
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
