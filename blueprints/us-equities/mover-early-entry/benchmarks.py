"""Fetch IWM's official auction prints for the baseline in protocol.json outcomes_and_metrics (C16).

  python benchmarks.py --env-file ENV --start 2021-01-04 --end 2025-12-31 --out PRIVATE_DIR

GET only. Every page is kept (gzip) and hashed into ledger.jsonl. The holdout range is fetched only
at the holdout step.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import collect  # noqa: E402

ASOF = "2026-09-21"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--env-file", type=Path, required=True)
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--symbol", default="IWM")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=True, mode=0o700)
    client = collect.Client(*collect.credentials(a.env_file), 5)
    tag = f"{a.symbol}-{a.start}-{a.end}"
    ok = True
    with (a.out / "ledger.jsonl").open("a") as ledger:
        ledger.write(json.dumps({"event": "run_start", "at": datetime.now(timezone.utc).isoformat(), "tag": tag, "asof": ASOF}) + "\n")
        params = {"symbols": a.symbol, "start": a.start, "end": a.end, "feed": "sip", "asof": ASOF, "limit": 10000}
        for page, (status, q, raw) in enumerate(client.pages("/v2/stocks/auctions", params)):
            name = f"auctions-{tag}-{page:04d}.json.gz"
            with gzip.open(a.out / name, "wb", compresslevel=6) as f:
                f.write(raw)
            ledger.write(json.dumps({"event": "page", "tag": tag, "file": name, "status": status,
                                     "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}) + "\n")
            ok = ok and status == 200
        ledger.write(json.dumps({"event": "complete" if ok else "incomplete", "tag": tag}) + "\n")
    print(json.dumps({"tag": tag, "complete": ok}))
    return 0 if ok else 1


def load(out: Path, symbol: str = "IWM") -> dict:
    """{date: {"o": [...], "c": [...]}} from every complete tag, each page checked against the ledger."""
    pages, done = {}, set()
    for line in (out / "ledger.jsonl").read_text().splitlines():
        rec = json.loads(line)
        if rec["event"] == "page":
            pages[rec["file"]] = rec
        elif rec["event"] == "complete":
            done.add(rec["tag"])
    days = {}
    for name, rec in sorted(pages.items()):
        if rec["tag"] not in done or not rec["tag"].startswith(symbol + "-"):
            continue
        raw = gzip.decompress((out / name).read_bytes())
        if hashlib.sha256(raw).hexdigest() != rec["sha256"]:
            raise SystemExit(f"benchmark page hash mismatch: {name}")
        for d in (json.loads(raw).get("auctions") or {}).get(symbol) or []:
            days.setdefault(d["d"], {"o": d.get("o") or [], "c": d.get("c") or []})
    return days


if __name__ == "__main__":
    raise SystemExit(main())
