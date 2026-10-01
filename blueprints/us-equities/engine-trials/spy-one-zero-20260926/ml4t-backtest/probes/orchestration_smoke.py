#!/usr/bin/env python3
"""Plumbing smoke test of fixture_port.py on synthetic bars (pre-run check, not an attempt).

The mechanism probe (mechanism_probe.py) exercises ``run_engine`` only. This script
exercises the rest of the port on the same synthetic sessions before the first
attempt: the child-process launch, ``child_main``, the two-run determinism diff and
the receipt assembly in ``parent_main``. It never reads SPY rows, the frozen inputs
or the LEAN data mount: the conversion is a stand-in that returns the synthetic
rows, and the port's input and row pins are replaced in this process only.

Checks:

1. A real child launch (``spawn_run``) inside the sandbox reaches ``child_main`` and
   refuses the synthetic rows against the frozen row hash (exit 1,
   ``child_rows_sha256_mismatch``): the launch path works and the pin holds.
2. ``parent_main`` over the synthetic rows, with each run executed in-process through
   ``child_main``, writes a receipt that the pinned compare.py's ``bind`` accepts
   (tolerances, arm manifest, plan and case configuration; the oracle is not opened)
   and that ``compare.compare`` scores PASS against expectations derived from the
   synthetic bars themselves, with the synthetic bars as attribution evidence.

Usage (inside the run sandbox, without the /data mount)::

    $ENV/bin/python -I probes/orchestration_smoke.py --out /out/smoke
"""
from __future__ import annotations

import argparse
from decimal import Decimal
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

PROBES = Path(__file__).resolve().parent
PORT_PATH = PROBES.parent / "fixture_port.py"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    args.out.mkdir(mode=0o700, parents=True, exist_ok=False)
    port = load("ml4t_arm_fixture_port", PORT_PATH)
    probe = load("ml4t_arm_mechanism_probe", PROBES / "mechanism_probe.py")
    compare = load("spy_parity_compare", port.SPY_PARITY / "compare.py")
    port.refuse_unless_isolated()
    real_convert, fixture = port.load_helpers()
    rows = probe.synthetic_rows()
    sessions = probe.SESSIONS
    first = {}
    for row in rows:
        first.setdefault(row["session_date"], row)
    rows_text = json.dumps(rows, indent=2, sort_keys=True, default=str) + "\n"
    rows_sha256 = hashlib.sha256(rows_text.encode()).hexdigest()
    checks = {}

    # 1. A real child launch refuses synthetic rows against the frozen row hash.
    spawn_dir = args.out / "spawn-check"
    spawn_dir.mkdir(mode=0o700)
    (spawn_dir / port.ROWS_FILE).write_text(rows_text)
    port.save(spawn_dir / port.CHILD_INPUT, {"rows_file": port.ROWS_FILE, "rows_sha256": rows_sha256,
                                             "funding_events": [], "case": probe.CASE, "asset": "SYN"})
    launched = port.spawn_run(spawn_dir, "run-1")
    stderr = (spawn_dir / "run-1" / "run-1.stderr.log").read_text()
    checks["real_child_launch_refuses_synthetic_rows"] = (
        launched["exit_code"] == 1 and "refused: child_rows_sha256_mismatch" in stderr)

    # 2. parent_main over synthetic rows, with the conversion and pins replaced here only.
    frozen = dict(real_convert.FROZEN_INPUT_SHA256)
    distributions = [{"ex_date": sessions[0], "utc_seconds": int(first[sessions[0]]["ts_event_ns"]) // 10 ** 9 - 36000,
                      "per_share": "0.21"},
                     {"ex_date": sessions[2], "utc_seconds": int(first[sessions[2]]["ts_event_ns"]) // 10 ** 9 - 36000,
                      "per_share": "0.37"}]

    class SyntheticConvert:
        FROZEN_INPUT_SHA256 = frozen

        @staticmethod
        def verify_inputs(root):
            return dict(frozen)

        @staticmethod
        def convert(root, symbol, start, end, short):
            return {"rows": rows, "counts": {"sessions": len(sessions), "hour_rows": len(rows),
                                             "full_session_rows": 7, "partial_sessions": {},
                                             "declared_short_sessions": short, "missing_session_dates": [],
                                             "extra_session_dates": []},
                    "distributions": distributions, "input_hashes": dict(frozen),
                    "decoded_inputs": ["synthetic"], "forward_filled_rows": 0,
                    "price_encoding": "synthetic", "volume_encoding": "synthetic",
                    "session_source": "synthetic", "map_rows": []}

    frozen_plan, case = port.check_plan()
    case = dict(case, entry_decision_date=sessions[0], exit_decision_date=sessions[2])
    port.load_helpers = lambda: (SyntheticConvert, fixture)
    port.check_plan = lambda: (frozen_plan, case)
    port.ROWS_SHA256, port.ROW_COUNT, port.SESSION_COUNT = rows_sha256, len(rows), len(sessions)
    port.ENTRY_DECISION_DATE, port.EXIT_DECISION_DATE, port.ASSET = sessions[0], sessions[2], "SYN"

    def in_process_run(out, label):
        started = time.monotonic()
        code = port.child_main(out, label)
        return {"label": label, "exit_code": code, "wall_seconds": round(time.monotonic() - started, 3),
                "stdout_sha256": hashlib.sha256(b"").hexdigest(), "stderr_sha256": hashlib.sha256(b"").hexdigest(),
                "stderr_bytes": 0}

    port.spawn_run = in_process_run
    port_out = args.out / "port"
    exit_code = port.parent_main(Path("/usr/share"), port_out)
    receipt = json.loads((port_out / "receipt.json").read_text())
    checks["parent_main_exit_zero"] = exit_code == 0
    checks["two_run_records_equal"] = receipt["two_run_records_equal"] is True
    checks["no_failed_guard"] = receipt["guards_failed"] == []

    limits, manifest = compare.bind(receipt, compare.SOURCE / "tolerances.json", port.MANIFEST,
                                    oracle_path=None, plan_path=compare.SOURCE.parent.parent
                                    / "historical-simulation" / "plan.json")
    checks["compare_bind_accepts_receipt"] = True
    by_end = {int(r["ts_event_ns"]) // 10 ** 9: r for r in rows}
    held = receipt["intents"][0]["quantity"]
    entry_bar, exit_bar = first[sessions[1]], first[sessions[3]]
    entry_price, exit_price = Decimal(entry_bar["o"]), Decimal(exit_bar["o"])
    dividends = held * Decimal("0.37")
    end_cash = Decimal("100000") - held * entry_price + dividends + held * exit_price
    expected = {"id": "one_zero",
                "intents": [{"utc_seconds": int(first[sessions[0]]["ts_event_ns"]) // 10 ** 9 + 6 * 3600,
                             "quantity": held, "reason": "entry"},
                            {"utc_seconds": int(first[sessions[2]]["ts_event_ns"]) // 10 ** 9 + 6 * 3600,
                             "quantity": -held, "reason": "exit"}],
                "fills": [{"utc_seconds": int(entry_bar["ts_event_ns"]) // 10 ** 9, "quantity": held,
                           "price": entry_price, "fee": Decimal(0)},
                          {"utc_seconds": int(exit_bar["ts_event_ns"]) // 10 ** 9, "quantity": -held,
                           "price": exit_price, "fee": Decimal(0)}],
                "fees_usd": Decimal(0), "dividends_usd": dividends, "end_cash_usd": end_cash,
                "final_quantity": 0, "fill_count": 2}
    verdict = compare.compare(receipt, expected, limits, manifest, list(by_end.values()))
    checks["compare_scores_synthetic_expectations_pass"] = verdict["verdict"] == "PASS"
    report = {
        "smoke": "ml4t-backtest port orchestration smoke test (synthetic bars, stand-in conversion)",
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "port_sha256": hashlib.sha256(PORT_PATH.read_bytes()).hexdigest(),
        "evidence_class": "synthetic fixture under the run sandbox; not parity evidence",
        "checks": checks, "all_checks_passed": all(checks.values()),
        "synthetic_verdict": {k: verdict[k] for k in ("verdict", "failed", "complete", "skipped",
                                                       "blocking_mappings", "unattributed_failures",
                                                       "rejected_attributions", "attribution_evidence")},
        "synthetic_verdict_checks": len(verdict["checks"]),
        "receipt_keys": sorted(receipt),
        "guards": [{k: g[k] for k in ("scope", "name", "outcome")} for g in receipt["guards"]],
        "float_projection": receipt["float_projection"],
    }
    text = json.dumps(report, indent=2, sort_keys=True, default=str) + "\n"
    (args.out / "orchestration-smoke.json").write_text(text)
    print(json.dumps({"all_checks_passed": report["all_checks_passed"],
                      "failed": sorted(k for k, v in checks.items() if not v),
                      "synthetic_verdict": verdict["verdict"], "synthetic_checks": len(verdict["checks"]),
                      "report_sha256": hashlib.sha256(text.encode()).hexdigest()}, sort_keys=True))
    return 0 if report["all_checks_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
