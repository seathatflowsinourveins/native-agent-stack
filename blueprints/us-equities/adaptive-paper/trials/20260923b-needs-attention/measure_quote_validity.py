"""Count how many live streamed quotes the engine's normalize_quote rejects, by reason.

Read-only: subscribes to Alpaca market-data quotes for the trial config's symbols and
benchmarks for a fixed window, runs each raw quote through transport.normalize_quote and
writes counts plus up to 20 rejected examples (symbol, prices, exchanges, conditions,
tape, timestamp). Credentials go through the runner's loader and are never written.
Run from blueprints/us-equities/adaptive-paper with the adaptive-paper interpreter.
"""
import argparse
import collections
import json
import sys
import threading
import time
from decimal import Decimal, InvalidOperation
import hashlib
from pathlib import Path

sys.path.insert(0, ".")
from runner import credentials  # noqa: E402
import transport  # noqa: E402


def classify(raw):
    try:
        transport.normalize_quote(raw)
        return None
    except getattr(transport, "InvalidQuote", ()) as exc:
        return "untradable:" + exc.reason
    except transport.TransportError:
        bp, ap = raw.get("bp"), raw.get("ap")
        try:
            if bp and ap and Decimal(str(bp)) > Decimal(str(ap)):
                return "crossed"
        except (InvalidOperation, ValueError):
            return "other"
        if not bp or not ap:
            return "one_sided"
        return "other"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--env-file", type=Path, required=True)
    ap.add_argument("--config", type=Path, default=Path("config-sip.json"))
    ap.add_argument("--seconds", type=float, default=60)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    from alpaca.data.enums import DataFeed
    from alpaca.data.live.stock import StockDataStream

    cfg = json.loads(a.config.read_text())
    symbols = sorted(set(cfg["symbols"]) | set(cfg["benchmarks"]))
    key, secret = credentials(a.env_file)
    stream = StockDataStream(key, secret, feed=DataFeed(cfg["feed"]), raw_data=True)
    counts, by_symbol, examples = collections.Counter(), collections.Counter(), []
    first_quote = threading.Event()
    window = {"first": None, "last": None}

    async def on_quote(raw):
        now = time.time()
        if window["first"] is None:
            window["first"] = now
            first_quote.set()
        window["last"] = now
        counts["total"] += 1
        reason = classify(raw)
        if reason:
            counts[reason] += 1
            by_symbol[raw.get("S", "?")] += 1
            if len(examples) < 20:
                examples.append({k: raw.get(k) for k in ("S", "bp", "ap", "bs", "as", "bx", "ax", "c", "z", "t")})

    stream.subscribe_quotes(on_quote, *symbols)
    threading.Thread(target=stream.run, daemon=True).start()
    # The window starts at the first delivered quote, so a slow start cannot shorten it silently.
    if not first_quote.wait(30):
        raise SystemExit("no quote within 30 s of starting the stream")
    time.sleep(a.seconds)
    stream.stop()
    sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
    result = {"kind": "streamed_quote_validity", "feed": cfg["feed"], "symbols": symbols,
              "config_sha256": sha(a.config), "script_sha256": sha(__file__),
              "requested_window_seconds": a.seconds,
              "observed_window_seconds": round(window["last"] - window["first"], 3),
              "started_unix": round(window["first"], 3),
              "transport_sha256": sha("transport.py"),
              "counts": dict(counts), "rejected_by_symbol": dict(by_symbol), "examples": examples}
    a.out.write_text(json.dumps(result, indent=2, default=str) + "\n")
    print(json.dumps({k: result[k] for k in ("counts", "rejected_by_symbol")}))


if __name__ == "__main__":
    main()
