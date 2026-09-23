"""Start AlpacaPaperTransport alone (no node, no orders), watch its health, then stop it.

Read-only. Records every change of health reasons with its time, and the time of each
alpaca-py log record that reports a websocket restart, relative to the moment stop() is
called, so it shows whether that log line appears while running or only at shutdown.
Run from blueprints/us-equities/adaptive-paper with the adaptive-paper interpreter.
"""
import argparse
import asyncio
import json
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, ".")
from runner import credentials  # noqa: E402
import transport  # noqa: E402


class Capture(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        message = record.getMessage()
        if "restarting" in message or "stopped" in message:
            self.records.append({"t": time.monotonic(), "logger": record.name, "message": message[:120]})


async def watch(key, secret, symbols, feed, seconds):
    async def before_request(kind, client_id=None):
        return None

    async def before_submit(*_, **__):
        return None

    port = transport.AlpacaPaperTransport(key, secret, symbols, before_request=before_request,
                                          before_submit=before_submit, sink_observation=lambda _: None,
                                          feed=feed, required_quote_symbols=symbols)
    quotes, changes, last = [0], [], None
    started = time.monotonic()
    await port.start(lambda _: quotes.__setitem__(0, quotes[0] + 1), lambda _: None)
    while time.monotonic() - started < seconds:
        health = port.health
        state = (tuple(health["reasons"]), health["ready"])
        if state != last:
            changes.append({"t": round(time.monotonic() - started, 2), "reasons": health["reasons"],
                            "ready": health["ready"]})
            last = state
        await asyncio.sleep(0.1)
    stop_at = time.monotonic()
    await port.stop()
    return started, stop_at, quotes[0], changes


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--env-file", type=Path, required=True)
    ap.add_argument("--feed", default="sip")
    ap.add_argument("--seconds", type=float, default=25)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    capture = Capture()
    logging.getLogger("alpaca").addHandler(capture)
    logging.getLogger("alpaca").setLevel(logging.INFO)
    key, secret = credentials(a.env_file)
    symbols = ["SPY", "QQQ", "IWM", "DIA"]
    started, stop_at, quotes, changes = asyncio.run(watch(key, secret, symbols, a.feed, a.seconds))
    result = {"kind": "transport_isolation_check", "feed": a.feed, "symbols": symbols, "window_seconds": a.seconds,
              "transport_sha256": __import__("hashlib").sha256(Path("transport.py").read_bytes()).hexdigest(),
              "quotes_received": quotes, "health_changes": changes,
              "restart_log_records": [{"seconds_after_stop_called": round(r["t"] - stop_at, 3),
                                       "logger": r["logger"], "message": r["message"]} for r in capture.records]}
    a.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"quotes": quotes, "health_changes": len(changes),
                      "restart_records_before_stop": sum(r["t"] < stop_at for r in capture.records)}))


if __name__ == "__main__":
    main()
