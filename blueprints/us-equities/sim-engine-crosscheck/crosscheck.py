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
  <nautilus python>   crosscheck.py run-nautilus     --stream STREAM.json --latency-ms 70 [--exact-latency] --out OUT.json
  <hftbacktest python> crosscheck.py run-hftbacktest --stream STREAM.json --latency-ms 70 --exchange partial_fill --out OUT.json
  <hftbacktest python> crosscheck.py determinism-check --stream STREAM.json --latency-ms 70 --exchange partial_fill
  python3 crosscheck.py report --stream STREAM.json --runs RUNS.json --out REPORT.json

`report` writes an intermediate, machine-generated `report.json` (metrics,
oracle confusion tables, hard-check results) -- it is NOT the committed
receipt itself. The committed receipt under `receipts/` is hand-assembled
from that report plus prose (mechanistic findings, the overturn evaluation);
see README.md for the exact, current provenance of each committed number.
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
import oracle  # noqa: E402
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
    outcomes = run_nautilus.run_stream(bounded["quotes"], intents, latency_ms=args.latency_ms,
                                        exact_latency=args.exact_latency)
    payload = {"engine": "nautilus_trader", "engine_version": importlib.metadata.version("nautilus_trader"),
               "python_version": platform.python_version(), "latency_ms": args.latency_ms,
               "exchange": None, "exact_latency": args.exact_latency,
               "generated_at_utc": utcnow_iso(), "outcomes": outcomes}
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
    """Build the aggregated comparison report, with two hard integrity
    checks added in the 2026-09-25 repair round (both raise, not merely
    report, on failure): no fill beats the displayed touch at fill time
    (metrics.better_than_touch_violations), on EITHER engine; and the
    per-run oracle confusion table (oracle.py) is attached so agreement can
    be asserted downstream (see tests/test_sim_engine_crosscheck.py's
    receipt-level oracle-agreement checks)."""
    bounded = sample.load_bounded_sample()
    quotes = bounded["quotes"]
    intents, _ = _load_stream(args.stream)
    run_paths = json.loads(Path(args.runs).read_text())  # {"label": "path.json", ...}
    runs = {}
    for label, path in run_paths.items():
        payload = json.loads(Path(path).read_text())
        outcomes = payload["outcomes"]
        violations = metrics.better_than_touch_violations(outcomes, quotes)
        if violations:
            raise RuntimeError(f"{label}: {len(violations)} fill(s) beat the displayed touch at fill "
                                f"time -- first: {violations[0]}")
        predictions = oracle.predict_stream(quotes, intents, latency_ms=payload["latency_ms"])
        runs[label] = {
            "engine": payload["engine"], "engine_version": payload["engine_version"],
            "python_version": payload["python_version"], "latency_ms": payload["latency_ms"],
            "exchange": payload["exchange"], "exact_latency": payload.get("exact_latency", False),
            "overall": metrics.summarize(outcomes, quotes, commission_plan=args.commission_plan),
            "by_symbol": metrics.summarize_by_symbol(outcomes, quotes, commission_plan=args.commission_plan),
            "better_than_touch_violations": violations,
            "oracle_confusion": {"overall": oracle.confusion(predictions, outcomes),
                                  "by_symbol": oracle.confusion_by_symbol(predictions, outcomes)},
        }
    _save_json(Path(args.out), {"generated_at_utc": utcnow_iso(), "commission_plan": args.commission_plan,
                                 "sample_window": bounded["window"], "symbols": bounded["symbols"], "runs": runs})
    print(json.dumps({"out": args.out, "labels": list(runs)}, indent=2))
    return 0


def cmd_determinism_check(args) -> int:
    """Run one hftbacktest configuration twice and compare outcome hashes.
    Raises on mismatch -- this is a hard check, not a soft metric (added in
    the 2026-09-25 repair round after the first attempt's use-after-free
    made hftbacktest runs silently non-deterministic; see
    run_hftbacktest.py's module docstring)."""
    import hashlib

    import run_hftbacktest

    bounded = sample.load_bounded_sample()
    intents, _ = _load_stream(args.stream)
    quotes = bounded["quotes"]
    first = run_hftbacktest.run_stream(quotes, intents, latency_ms=args.latency_ms, exchange=args.exchange)
    second = run_hftbacktest.run_stream(quotes, intents, latency_ms=args.latency_ms, exchange=args.exchange)

    def _hash(outcomes):
        return hashlib.sha256(json.dumps(outcomes, sort_keys=True, default=str).encode()).hexdigest()

    h1, h2 = _hash(first), _hash(second)
    result = {"latency_ms": args.latency_ms, "exchange": args.exchange, "hash_1": h1, "hash_2": h2,
              "match": h1 == h2, "n_outcomes": len(first)}
    if args.out:
        _save_json(Path(args.out), result)
    print(json.dumps(result, indent=2))
    if h1 != h2:
        raise RuntimeError(f"determinism check failed: hash_1={h1} != hash_2={h2}")
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
    p.add_argument("--exact-latency", action="store_true",
                    help="Add the no-op per-order release alert (see run_nautilus.py); default matches "
                         "sim-capacity's own runner.run_one")
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_run_nautilus)

    p = sub.add_parser("run-hftbacktest")
    p.add_argument("--stream", required=True)
    p.add_argument("--latency-ms", type=int, required=True)
    p.add_argument("--exchange", choices=EXCHANGE_MODELS, required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_run_hftbacktest)

    p = sub.add_parser("report")
    p.add_argument("--stream", required=True)
    p.add_argument("--runs", required=True, help="JSON file mapping label -> outcome-file path")
    p.add_argument("--commission-plan", default="none", choices=("none", "all_in", "cost_plus"))
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_report)

    p = sub.add_parser("determinism-check")
    p.add_argument("--stream", required=True)
    p.add_argument("--latency-ms", type=int, required=True)
    p.add_argument("--exchange", choices=EXCHANGE_MODELS, required=True)
    p.add_argument("--out", default=None)
    p.set_defaults(func=cmd_determinism_check)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
