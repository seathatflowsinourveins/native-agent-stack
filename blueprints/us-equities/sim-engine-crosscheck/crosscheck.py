#!/usr/bin/env python3
"""Engine-vs-engine cross-check orchestrator (Phase C): NautilusTrader
2.0.0rc5 vs hftbacktest 2.4.4 on the SAME deterministic order stream over the
SAME bounded, retained Alpaca SIP sample.

NautilusTrader and hftbacktest live in two DIFFERENT, mutually incompatible
Python runtimes (the pinned adaptive-paper-20260921 venv and the isolated
hftbacktest-2.4.4 venv respectively) -- this script is therefore split into
subcommands run under each interpreter separately, plus a final `report`
step (any interpreter; metrics.py and fee_model.py have no special
dependency) that reads both engines' JSON outcome files and builds the
comparison receipt. See README.md's "Running it" section for the exact
per-interpreter invocations.

  python3 crosscheck.py sample                         # bounded SPY+NVDA sample (system python)
  python3 crosscheck.py stream --out STREAM.json        # deterministic order stream (system python)
  <nautilus python>   crosscheck.py run-nautilus     --stream STREAM.json --latency-ms 70 --out OUT.json
  <hftbacktest python> crosscheck.py run-hftbacktest --stream STREAM.json --latency-ms 70 --exchange partial_fill --out OUT.json
  python3 crosscheck.py report --stream STREAM.json --runs RUNS.json --out RECEIPT.json
"""
from __future__ import annotations

import argparse
import json
import platform
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import metrics  # noqa: E402
import order_stream  # noqa: E402
import sample  # noqa: E402

UTC = timezone.utc
LATENCY_SWEEP_MS = (70, 250)
EXCHANGE_MODELS = ("partial_fill", "no_partial_fill")


def utcnow_iso() -> str:
    return datetime.now(UTC).isoformat()


def _save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True, default=str) + "\n")


def cmd_sample(args) -> int:
    manifest = sample.extract_bounded_sample()
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


def cmd_stream(args) -> int:
    bounded = sample.load_bounded_sample()
    stream = order_stream.generate_order_stream(bounded["quotes"])
    payload = {"window": bounded["window"], "symbols": bounded["symbols"],
               "submits_per_sec": order_stream.PAPER_PARITY_SUBMITS_PER_SEC,
               "n_orders": len(stream), "orders": [asdict(intent) for intent in stream]}
    _save_json(Path(args.out), payload)
    print(json.dumps({"out": args.out, "n_orders": len(stream)}, indent=2))
    return 0


def _load_stream(path: str) -> tuple[list[order_stream.OrderIntent], dict]:
    payload = json.loads(Path(path).read_text())
    intents = [order_stream.OrderIntent(**row) for row in payload["orders"]]
    return intents, payload


def cmd_run_nautilus(args) -> int:
    import importlib.metadata

    import run_nautilus

    bounded = sample.load_bounded_sample()
    intents, _ = _load_stream(args.stream)
    outcomes = run_nautilus.run_stream(bounded["quotes"], intents, latency_ms=args.latency_ms)
    payload = {"engine": "nautilus_trader", "engine_version": importlib.metadata.version("nautilus_trader"),
               "python_version": platform.python_version(), "latency_ms": args.latency_ms,
               "exchange": None, "generated_at_utc": utcnow_iso(), "outcomes": outcomes}
    _save_json(Path(args.out), payload)
    print(json.dumps({"out": args.out, "n_outcomes": len(outcomes)}, indent=2))
    return 0


def cmd_run_hftbacktest(args) -> int:
    import importlib.metadata

    import run_hftbacktest

    bounded = sample.load_bounded_sample()
    intents, _ = _load_stream(args.stream)
    outcomes = run_hftbacktest.run_stream(bounded["quotes"], intents, latency_ms=args.latency_ms,
                                           exchange=args.exchange)
    payload = {"engine": "hftbacktest", "engine_version": importlib.metadata.version("hftbacktest"),
               "python_version": platform.python_version(), "latency_ms": args.latency_ms,
               "exchange": args.exchange, "generated_at_utc": utcnow_iso(), "outcomes": outcomes}
    _save_json(Path(args.out), payload)
    print(json.dumps({"out": args.out, "n_outcomes": len(outcomes)}, indent=2))
    return 0


def cmd_report(args) -> int:
    bounded = sample.load_bounded_sample()
    quotes = bounded["quotes"]
    run_paths = json.loads(Path(args.runs).read_text())  # {"label": "path.json", ...}
    runs = {}
    for label, path in run_paths.items():
        payload = json.loads(Path(path).read_text())
        outcomes = payload["outcomes"]
        runs[label] = {
            "engine": payload["engine"], "engine_version": payload["engine_version"],
            "python_version": payload["python_version"], "latency_ms": payload["latency_ms"],
            "exchange": payload["exchange"],
            "overall": metrics.summarize(outcomes, quotes, commission_plan=args.commission_plan),
            "by_symbol": metrics.summarize_by_symbol(outcomes, quotes, commission_plan=args.commission_plan),
        }
    _save_json(Path(args.out), {"generated_at_utc": utcnow_iso(), "commission_plan": args.commission_plan,
                                 "sample_window": bounded["window"], "symbols": bounded["symbols"], "runs": runs})
    print(json.dumps({"out": args.out, "labels": list(runs)}, indent=2))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0], allow_abbrev=False)
    sub = ap.add_subparsers(dest="command", required=True)

    sub.add_parser("sample").set_defaults(func=cmd_sample)

    p = sub.add_parser("stream")
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_stream)

    p = sub.add_parser("run-nautilus")
    p.add_argument("--stream", required=True)
    p.add_argument("--latency-ms", type=int, required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_run_nautilus)

    p = sub.add_parser("run-hftbacktest")
    p.add_argument("--stream", required=True)
    p.add_argument("--latency-ms", type=int, required=True)
    p.add_argument("--exchange", choices=EXCHANGE_MODELS, required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_run_hftbacktest)

    p = sub.add_parser("report")
    p.add_argument("--runs", required=True, help="JSON file mapping label -> outcome-file path")
    p.add_argument("--commission-plan", default="none", choices=("none", "all_in", "cost_plus"))
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_report)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
