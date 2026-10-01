#!/usr/bin/env python3
"""Plumbing smoke test of the Lumibot port on synthetic bars (pre-run check, not an attempt).

``mechanism_probe.py`` exercises ``run_engine`` only. This script exercises the rest of
the port on the same synthetic sessions before the first attempt: the child-process
launch, ``child_main``, the two-run determinism diff and the receipt assembly in
``parent_main``. It never reads SPY rows, the frozen inputs or the LEAN data mount: the
conversion is a stand-in that returns the synthetic rows, and the port's input, row,
window and decision-date pins are replaced in this process and in its own child
processes only.

Checks:

1. A real child launch (``spawn_run`` with the port's own command) refuses the
   synthetic rows against the frozen row hash (exit 1, ``child_rows_sha256_mismatch``).
2. For the primary hook (``after_market_closes``) and for ``before_starting_trading``,
   ``parent_main`` over the synthetic rows, with each run in a fresh child process of
   this script (which applies the same stand-ins and then calls the port's
   ``child_main``), writes a receipt that the pinned compare.py's ``bind`` accepts
   (tolerances, arm manifest, plan and case configuration; the oracle is not opened),
   with equal two-run records. ``compare.compare`` against expectations of the LEAN
   shape derived from the synthetic bars (fills at the next session's first bar open)
   then gives the shape the pre-run finding predicts: FAIL with the four fill checks
   and both end-cash checks unattributed for the primary hook, and BLOCKED on
   native_end_cash by distributions_and_cash for ``before_starting_trading``.

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

PROBES = Path(__file__).resolve().parent
PORT_PATH = PROBES.parent / "fixture_port.py"
SCRIPT = Path(__file__).resolve()
HOOKS = ("after_market_closes", "before_starting_trading")
PRIMARY_FAILING = ["end_cash.reconciled_end_cash_usd", "entry_fill.fill_price_usd", "entry_fill.utc_seconds",
                   "exit_fill.fill_price_usd", "exit_fill.utc_seconds", "native_end_cash.native_end_cash_usd"]


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def stand_ins(port, probe):
    """Replace the conversion and the pins with the synthetic calendar, in this process only."""
    real_convert, fixture = port.load_helpers()
    rows = probe.synthetic_rows()
    rows_text = json.dumps(rows, indent=2, sort_keys=True, default=str) + "\n"
    rows_sha256 = hashlib.sha256(rows_text.encode()).hexdigest()
    frozen = dict(real_convert.FROZEN_INPUT_SHA256)
    distributions = probe.synthetic_distributions()
    sessions = probe.SESSIONS

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
    case = dict(case, entry_decision_date=probe.ENTRY_DECISION, exit_decision_date=probe.EXIT_DECISION)
    port.load_helpers = lambda: (SyntheticConvert, fixture)
    port.check_plan = lambda: (frozen_plan, case)
    port.ROWS_SHA256, port.ROW_COUNT, port.SESSION_COUNT = rows_sha256, len(rows), len(sessions)
    port.ENTRY_DECISION_DATE, port.EXIT_DECISION_DATE = probe.ENTRY_DECISION, probe.EXIT_DECISION
    probe.patch_port(port)
    port.child_command = lambda out, label, hook: [sys.executable, "-I", str(SCRIPT), "--out", str(out),
                                                   "--child-run", label, "--decision-hook", hook]
    return rows, rows_text, rows_sha256, case


def expected_lean_shape(receipt, rows, probe):
    """The oracle's shape on the synthetic bars: fills at the next session's first bar open."""
    first, last = {}, {}
    for row in rows:
        first.setdefault(row["session_date"], row)
        last[row["session_date"]] = row
    end = lambda row: int(row["ts_event_ns"]) // 10 ** 9  # noqa: E731
    held = receipt["intents"][0]["quantity"]
    entry_bar, exit_bar = first[probe.ENTRY_NEXT], first[probe.EXIT_NEXT]
    entry_price, exit_price = Decimal(entry_bar["o"]), Decimal(exit_bar["o"])
    dividends = held * Decimal(probe.DISTRIBUTIONS[1][1])
    end_cash = Decimal("100000") - held * entry_price + dividends + held * exit_price
    return {"id": "one_zero",
            "intents": [{"utc_seconds": end(last[probe.ENTRY_DECISION]), "quantity": held, "reason": "entry"},
                        {"utc_seconds": end(last[probe.EXIT_DECISION]), "quantity": -held, "reason": "exit"}],
            "fills": [{"utc_seconds": end(entry_bar), "quantity": held, "price": entry_price, "fee": Decimal(0)},
                      {"utc_seconds": end(exit_bar), "quantity": -held, "price": exit_price, "fee": Decimal(0)}],
            "fees_usd": Decimal(0), "dividends_usd": dividends, "end_cash_usd": end_cash,
            "final_quantity": 0, "fill_count": 2}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--child-run", help=argparse.SUPPRESS)
    parser.add_argument("--decision-hook", help=argparse.SUPPRESS)
    args = parser.parse_args()
    os.umask(0o077)
    port = load("lumibot_arm_fixture_port", PORT_PATH)
    probe = load("lumibot_arm_mechanism_probe", PROBES / "mechanism_probe.py")
    if args.child_run:
        stand_ins(port, probe)
        return port.child_main(args.out, args.child_run, args.decision_hook)
    compare = load("spy_parity_compare", port.SPY_PARITY / "compare.py")
    port.refuse_unless_isolated()
    args.out.mkdir(mode=0o700, parents=True, exist_ok=False)
    checks, verdicts, receipts = {}, {}, {}

    # 1. A real child launch refuses synthetic rows against the frozen row hash.
    rows = probe.synthetic_rows()
    rows_text = json.dumps(rows, indent=2, sort_keys=True, default=str) + "\n"
    spawn_dir = args.out / "spawn-check"
    spawn_dir.mkdir(mode=0o700)
    (spawn_dir / port.ROWS_FILE).write_text(rows_text)
    port.save(spawn_dir / port.CHILD_INPUT, {"rows_file": port.ROWS_FILE,
                                             "rows_sha256": hashlib.sha256(rows_text.encode()).hexdigest(),
                                             "distributions": [], "case": probe.CASE, "asset": probe.ASSET,
                                             "decision_hook": port.PRIMARY_HOOK})
    launched = port.spawn_run(spawn_dir, "run-1", port.PRIMARY_HOOK)
    stderr = (spawn_dir / "run-1" / "run-1.stderr.log").read_text()
    checks["real_child_launch_refuses_synthetic_rows"] = (
        launched["exit_code"] == 1 and "refused: child_rows_sha256_mismatch" in stderr)

    # 2. parent_main over synthetic rows, runs in child processes of this script.
    stand_ins(port, probe)
    for hook in HOOKS:
        port_out = args.out / ("port-" + hook)
        exit_code = port.parent_main(Path("/usr/share"), port_out, hook)
        receipt = json.loads((port_out / "receipt.json").read_text())
        receipts[hook] = receipt
        checks[hook + ":parent_main_exit_zero"] = exit_code == 0
        checks[hook + ":two_run_records_equal"] = receipt["two_run_records_equal"] is True
        expected_failed = sorted(probe.EXPECTED_FAILED_GUARDS[hook])
        checks[hook + ":guards_failed_as_mechanism_probe"] = all(
            run["guards_failed"] == expected_failed for run in receipt["runs"])
        checks[hook + ":no_port_scope_guard_failed"] = not [g for g in receipt["guards_failed"] if g.startswith("port:")]
        limits, manifest = compare.bind(receipt, compare.SOURCE / "tolerances.json", port.MANIFEST,
                                        oracle_path=None, plan_path=compare.SOURCE.parent.parent
                                        / "historical-simulation" / "plan.json")
        checks[hook + ":compare_bind_accepts_receipt"] = True
        verdict = compare.compare(receipt, expected_lean_shape(receipt, rows, probe), limits, manifest, rows)
        verdicts[hook] = verdict
        failing = sorted(c["id"] + "." + c["field"] for c in verdict["checks"] if c["status"] == "FAIL")
        checks[hook + ":twenty_nine_checks"] = len(verdict["checks"]) == 29
        if hook == "after_market_closes":
            checks[hook + ":compare_shape_fail_unattributed"] = (
                verdict["verdict"] == "FAIL" and failing == PRIMARY_FAILING
                and not verdict["rejected_attributions"] and verdict["blocking_mappings"] == [])
        else:
            checks[hook + ":compare_shape_blocked_by_distributions"] = (
                verdict["verdict"] == "BLOCKED" and failing == ["native_end_cash.native_end_cash_usd"]
                and verdict["blocking_mappings"] == ["distributions_and_cash"] and verdict["complete"] is True)
    report = {
        "smoke": "Lumibot port orchestration smoke test (synthetic bars, stand-in conversion)",
        "script_sha256": hashlib.sha256(SCRIPT.read_bytes()).hexdigest(),
        "port_sha256": hashlib.sha256(PORT_PATH.read_bytes()).hexdigest(),
        "mechanism_probe_sha256": hashlib.sha256((PROBES / "mechanism_probe.py").read_bytes()).hexdigest(),
        "evidence_class": "synthetic fixture under the run sandbox; not parity evidence",
        "checks": checks, "all_checks_passed": all(checks.values()),
        "synthetic_verdicts": {hook: {"verdict": v["verdict"], "checks": len(v["checks"]), "failed": v["failed"],
                                      "failing": sorted(c["key"] for c in v["checks"] if c["status"] == "FAIL"),
                                      "blocking_mappings": v["blocking_mappings"],
                                      "unattributed_failures": v["unattributed_failures"],
                                      "rejected_attributions": v["rejected_attributions"],
                                      "complete": v["complete"], "attribution_evidence": v["attribution_evidence"]}
                               for hook, v in verdicts.items()},
        "receipt_keys": {hook: sorted(r) for hook, r in receipts.items()},
        "guards": {hook: [{k: g[k] for k in ("scope", "name", "outcome")} for g in r["guards"]]
                   for hook, r in receipts.items()},
        "float_projection": {hook: r["float_projection"] for hook, r in receipts.items()},
        "two_run_determinism": {hook: r["two_run_determinism"] for hook, r in receipts.items()},
    }
    text = json.dumps(report, indent=2, sort_keys=True, default=str) + "\n"
    (args.out / "orchestration-smoke.json").write_text(text)
    print(json.dumps({"all_checks_passed": report["all_checks_passed"],
                      "failed": sorted(k for k, v in checks.items() if not v),
                      "synthetic_verdicts": {h: v["verdict"] for h, v in verdicts.items()},
                      "report_sha256": hashlib.sha256(text.encode()).hexdigest()}, sort_keys=True))
    return 0 if report["all_checks_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
