"""Read-only SIP quote-cadence sample for a config's symbols (market data only, no account data).

Takes ``--samples`` latest-quote snapshots ``--interval`` seconds apart through alpaca-py's
StockHistoricalDataClient and writes, per sample and symbol, the quote's age in seconds and its
spread in basis points. No order, account or position endpoint is called. Run with the
adaptive-paper interpreter from this directory:

  python quote_cadence_sample.py --env-file ENV --config CONFIG --out quote-cadence-<time>.json
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--env-file", type=Path, required=True)
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--samples", type=int, default=8)
    ap.add_argument("--interval", type=float, default=2.5)
    ap.add_argument("--engine-dir", type=Path, required=True, help="adaptive-paper source dir (for runner.credentials)")
    a = ap.parse_args(argv)
    sys.path.insert(0, str(a.engine_dir))
    from runner import credentials
    from alpaca.data.enums import DataFeed
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockLatestQuoteRequest

    config = json.loads(a.config.read_text())
    limit = config["quote_max_age_seconds"]
    key, secret = credentials(a.env_file)
    client = StockHistoricalDataClient(key, secret)
    symbols = config["symbols"]
    samples = []
    for _ in range(a.samples):
        quotes = client.get_stock_latest_quote(StockLatestQuoteRequest(symbol_or_symbols=symbols, feed=DataFeed.SIP))
        now = datetime.now(timezone.utc)
        row = {"observed_at": now.isoformat(), "quotes": {}}
        for s in symbols:
            q = quotes.get(s)
            if q is None:
                row["quotes"][s] = None
                continue
            mid = (q.ask_price + q.bid_price) / 2 if q.ask_price and q.bid_price else None
            row["quotes"][s] = {"age_s": round((now - q.timestamp).total_seconds(), 3),
                                "spread_bps": round((q.ask_price - q.bid_price) / mid * 1e4, 2) if mid else None}
        samples.append(row)
        time.sleep(a.interval)
    summary = {}
    for s in symbols:
        ages = [r["quotes"][s]["age_s"] for r in samples if r["quotes"].get(s)]
        spreads = [r["quotes"][s]["spread_bps"] for r in samples if r["quotes"].get(s) and r["quotes"][s]["spread_bps"] is not None]
        summary[s] = {"fresh": sum(x <= limit for x in ages), "samples": len(ages),
                      "median_age_s": round(statistics.median(ages), 1) if ages else None,
                      "max_age_s": round(max(ages), 1) if ages else None,
                      "median_spread_bps": round(statistics.median(spreads), 1) if spreads else None}
    out = {"kind": "sip_quote_cadence_sample", "endpoint": "market_data_only", "feed": "sip",
           "config_sha256": __import__("hashlib").sha256(a.config.read_bytes()).hexdigest(),
           "quote_max_age_seconds": limit, "interval_seconds": a.interval, "samples": samples, "summary": summary}
    a.out.write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps({s: (v["fresh"], v["samples"], v["median_age_s"]) for s, v in summary.items()}))


if __name__ == "__main__":
    main()
