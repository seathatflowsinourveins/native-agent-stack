"""Write the promotion-gate snapshot a paper trial consumes.

Fetches the last completed daily bars for the adaptive-paper universe from the
Alpaca market-data API (read-only) and writes the CSV schema that
``promotion_gate.py`` validates (symbol, session, open, high, low, close,
volume, observed_at), plus a receipt with counts and hashes only. Credentials
are loaded through the adaptive-paper runner's hardened loader and never
written or printed. Run with the adaptive-paper interpreter (alpaca-py 0.44.0).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "adaptive-paper"))

COLUMNS = ("symbol", "session", "open", "high", "low", "close", "volume", "observed_at")
NEW_YORK = ZoneInfo("America/New_York")


def rows_from_bars(bars_by_symbol, sessions, observed_at):
    """Keep each symbol's last ``sessions`` completed daily bars as CSV rows.

    A bar's session is its timestamp's New York calendar date. Prices are kept
    as decimal text exactly as returned; volume must be integral."""
    rows = []
    for symbol in sorted(bars_by_symbol):
        bars = sorted(bars_by_symbol[symbol], key=lambda bar: bar["timestamp"])[-sessions:]
        for bar in bars:
            volume = float(bar["volume"])
            if volume != int(volume):
                raise ValueError(f"non_integral_volume:{symbol}")
            rows.append({"symbol": symbol,
                         "session": bar["timestamp"].astimezone(NEW_YORK).date().isoformat(),
                         "open": str(bar["open"]), "high": str(bar["high"]),
                         "low": str(bar["low"]), "close": str(bar["close"]),
                         "volume": str(int(volume)), "observed_at": observed_at})
    return rows


def write_csv(rows, path):
    with open(path, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    data = Path(path).read_bytes()
    return hashlib.sha256(data).hexdigest(), len(data)


def fetch(key, secret, symbols, feed, start, end):
    from alpaca.data.enums import Adjustment, DataFeed
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame

    client = StockHistoricalDataClient(key, secret)
    request = StockBarsRequest(symbol_or_symbols=list(symbols), timeframe=TimeFrame.Day, start=start, end=end,
                               adjustment=Adjustment.RAW, feed=DataFeed(feed))
    result = client.get_stock_bars(request).data
    return {symbol: [{"timestamp": bar.timestamp, "open": bar.open, "high": bar.high, "low": bar.low,
                      "close": bar.close, "volume": bar.volume} for bar in result.get(symbol, [])]
            for symbol in symbols}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--env-file", required=True, type=Path)
    parser.add_argument("--config", type=Path, default=ROOT / "adaptive-paper" / "config.json")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--sessions", type=int, default=20)
    parser.add_argument("--feed", choices=["sip", "iex"], default="sip")
    args = parser.parse_args(argv)
    from runner import credentials

    key, secret = credentials(args.env_file)
    symbols = json.loads(args.config.read_text())["symbols"]
    now = datetime.now(timezone.utc)
    # Historical SIP bars must end at least 15 minutes in the past; the window
    # is wide enough to hold the requested completed sessions.
    end = now - timedelta(minutes=20)
    bars = fetch(key, secret, symbols, args.feed, end - timedelta(days=args.sessions * 2 + 10), end)
    today = now.astimezone(NEW_YORK).date()
    completed = {s: [b for b in v if b["timestamp"].astimezone(NEW_YORK).date() < today
                     or now.astimezone(NEW_YORK).hour >= 17] for s, v in bars.items()}
    missing = sorted(s for s, v in completed.items() if not v)
    rows = rows_from_bars(completed, args.sessions, now.strftime("%Y-%m-%dT%H:%M:%SZ"))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    sha, size = write_csv(rows, args.out)
    import alpaca

    receipt = {"kind": "promotion_gate_snapshot_ingest", "evidence_class": "native_market_data_readonly",
               "fetched_at_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "feed": args.feed, "adjustment": "raw",
               "timeframe": "1Day", "sessions_requested": args.sessions, "symbols": len(symbols),
               "symbols_missing": missing, "row_count": len(rows),
               "sessions_range": [min(r["session"] for r in rows), max(r["session"] for r in rows)] if rows else None,
               "config_sha256": hashlib.sha256(args.config.read_bytes()).hexdigest(),
               "snapshot_sha256": sha, "snapshot_bytes": size, "alpaca_py": alpaca.__version__}
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({k: receipt[k] for k in ("row_count", "symbols_missing", "sessions_range", "snapshot_sha256")}))
    return 0 if rows and not missing else 2


if __name__ == "__main__":
    raise SystemExit(main())
