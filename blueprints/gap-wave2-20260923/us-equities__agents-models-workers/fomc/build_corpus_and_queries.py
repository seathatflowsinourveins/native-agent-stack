#!/usr/bin/env python3
"""Extract FOMC statement text/date/target range from downloaded federalreserve.gov pages
and generate the dated query set mechanically (before any retrieval).

Usage: build_corpus_and_queries.py FOMC_DIR OUT_CORPUS_JSONL OUT_QUERIES_JSON
Gold per statement: its release date (from the URL) and the federal funds target range
regex-extracted from its own text. Queries name only the meeting month and year.
"""
import calendar
import html
import json
import re
import sys
from pathlib import Path

RANGE = re.compile(r"target range for the federal funds rate (?:by \S+ percentage point )?(?:at|to) ([0-9][0-9/\-‑]* to [0-9][0-9/\-‑]*) percent", re.I)


def text_from(raw: str) -> str:
    m = re.search(r'<div[^>]+id="article"[^>]*>(.*?)<div[^>]+(?:id="lastUpdate"|class="lastUpdate")', raw, re.S)
    body = m.group(1) if m else raw
    body = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", body, flags=re.S)
    body = re.sub(r"<[^>]+>", " ", body)
    body = html.unescape(body)
    return re.sub(r"\s+", " ", body).strip()


def main():
    root, corpus_out, queries_out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    docs, queries = [], []
    for page in sorted((root / "html").glob("monetary*a.htm")):
        date = re.search(r"monetary(\d{4})(\d{2})(\d{2})a", page.name)
        iso = f"{date.group(1)}-{date.group(2)}-{date.group(3)}"
        text = text_from(page.read_text(encoding="utf-8", errors="replace"))
        rng = RANGE.search(text)
        doc = {"doc_id": page.stem, "date": iso, "url": f"https://www.federalreserve.gov/newsevents/pressreleases/{page.name}",
               "chars": len(text), "target_range": rng.group(1).strip().replace("\u2011", "-") if rng else None, "text": text}
        docs.append(doc)
    for d in docs:
        if not d["target_range"]:
            continue
        y, m, _ = d["date"].split("-")
        month = calendar.month_name[int(m)]
        queries.append({"id": d["doc_id"], "gold_date": d["date"], "gold_doc": d["doc_id"],
                        "gold_target_range": d["target_range"],
                        "query": f"What target range for the federal funds rate did the FOMC set at its {month} {y} meeting?",
                        "filter_month": f"{y}-{m}"})
    with corpus_out.open("w") as f:
        for d in docs:
            f.write(json.dumps(d) + "\n")
    queries_out.write_text(json.dumps({"queries": queries}, indent=1) + "\n")
    print(json.dumps({"docs": len(docs), "queries": len(queries),
                      "docs_without_range": [d["doc_id"] for d in docs if not d["target_range"]],
                      "distinct_ranges": sorted({d["target_range"] for d in docs if d["target_range"]})}))


if __name__ == "__main__":
    main()
