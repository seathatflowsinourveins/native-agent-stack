#!/usr/bin/env python3
"""Mechanism probe for the Lumibot arm's port, on synthetic bars only.

Preregistered in ../../preregistration.json ``mechanism_probes``: before the first
attempt, under the run sandbox without the /data mount, and never on SPY rows, the
frozen inputs or the LEAN data. Where ``hook_probe.py`` observes the engine directly,
this probe runs the port's own ``run_engine`` (fixture_port.py, loaded by path) over
the same synthetic calendar, once per decision hook, each in a fresh child process,
and checks that the port's records and guards report what the engine did:

* ``after_market_closes`` (the primary hook): both fills at the decision bar's end
  instant at that bar's open; the guards causality, submission_clock and
  fill_at_next_session_first_bar fail and every other guard passes;
* ``before_starting_trading``: both fills at the next session's first bar end at its
  open; only submission_clock fails (submission at the fill instant);
* ``before_market_opens``: the entry (42-hour gap) fills at the next session's first
  bar open; the exit (18-hour gap) fills at 09:00 at the decision bar's open.

In every variant the distribution ledger is external (``engine_posted`` false) and the
engine's cash changes only at fills. This file imports GPL-3.0 Lumibot only through
the port, from the isolated environment, and contains no Lumibot code. A probe cannot
change a row status, the binding, the sheet or the scorer.

Usage (inside the run sandbox, without the /data mount)::

    $ENV/bin/python -I probes/mechanism_probe.py --out /out/probe
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, time, timedelta
from decimal import Decimal
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time as clock
from zoneinfo import ZoneInfo

PROBE = Path(__file__).resolve()
PORT = PROBE.parent.parent / "fixture_port.py"
NEW_YORK = ZoneInfo("America/New_York")
SESSIONS = ("2021-03-08", "2021-03-09", "2021-03-11", "2021-03-12", "2021-03-15", "2021-03-16", "2021-03-17")
STARTS = ("09:00", "10:00", "11:00", "12:00", "13:00", "14:00", "15:00")
ENTRY_DECISION, ENTRY_NEXT = "2021-03-09", "2021-03-11"
EXIT_DECISION, EXIT_NEXT = "2021-03-15", "2021-03-16"
ASSET = "SYN"
WINDOW = (datetime(2021, 3, 8, 0, 0), datetime(2021, 3, 17, 23, 59))
CASE = {"id": "synthetic", "initial_cash_usd": "100000", "sizing_buffer": "0.98", "target": "1",
        "fee_usd": "0", "slippage": "0", "entry_decision_date": ENTRY_DECISION,
        "exit_decision_date": EXIT_DECISION, "currency": "USD"}
DISTRIBUTIONS = (("2021-03-08", "0.21"), ("2021-03-12", "0.37"))  # flat, then held
HOOKS = ("after_market_closes", "before_starting_trading", "before_market_opens")
EXPECTED_FAILED_GUARDS = {
    "after_market_closes": ["causality", "fill_at_next_session_first_bar", "submission_clock"],
    "before_starting_trading": ["submission_clock"],
    "before_market_opens": ["fill_at_next_session_first_bar", "fill_price_is_open_of_bar_indexed_at_fill_instant",
                            "submission_clock"],
}


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def synthetic_rows() -> list:
    """Seven hourly bars per session in the converted-row format; opens and closes all distinct.

    The per-session quadratic drift keeps the gap between a session's last open and the next
    session's first open different from session to session, so a fill on the wrong bar moves
    the round trip's cash and not only its prices.
    """
    rows = []
    for s, day in enumerate(SESSIONS):
        for k, start in enumerate(STARTS):
            o = Decimal("100") + Decimal(s) + Decimal("0.1") * k + Decimal("0.01") + Decimal("0.02") * s * s
            c = o + Decimal("0.05")
            begin = datetime.combine(date.fromisoformat(day), time.fromisoformat(start), NEW_YORK)
            end = int((begin + timedelta(hours=1)).timestamp())
            rows.append({"session_date": day, "local_start": start, "ts_event_ns": end * 10 ** 9,
                         "o": str(o.quantize(Decimal("0.0001"))),
                         "h": str((max(o, c) + Decimal("0.02")).quantize(Decimal("0.0001"))),
                         "l": str((min(o, c) - Decimal("0.02")).quantize(Decimal("0.0001"))),
                         "c": str(c.quantize(Decimal("0.0001"))), "v": 1000 + 10 * s + k})
    return rows


def synthetic_distributions() -> list:
    out = []
    for day, per_share in DISTRIBUTIONS:
        midnight = datetime.combine(date.fromisoformat(day), time(0, 0), NEW_YORK)
        out.append({"ex_date": day, "utc_seconds": int(midnight.timestamp()), "per_share": per_share})
    return out


def patch_port(port) -> None:
    """Point the port at the synthetic calendar, in this process only."""
    port.ASSET = ASSET
    port.BACKTEST_START, port.BACKTEST_END = WINDOW


def child(hook: str, out: Path) -> int:
    port = load("lumibot_arm_fixture_port", PORT)
    patch_port(port)
    port.refuse_unless_isolated()
    _, fixture = port.load_helpers()
    outcome = port.run_engine(synthetic_rows(), synthetic_distributions(), CASE, fixture, label="probe", hook=hook)
    outcome.pop("raw_report")
    (out / hook / "outcome.json").write_text(json.dumps(outcome, indent=1, sort_keys=True, default=str) + "\n")
    return 0


def expectations(hook: str, outcome: dict, rows: list) -> dict:
    first, last = {}, {}
    for row in rows:
        first.setdefault(row["session_date"], row)
        last[row["session_date"]] = row
    record = outcome["record"]
    fills, intents, ledger = record["fills"], record["intents"], record["distribution_ledger"]
    held = intents[0]["quantity"] if intents else None
    end = lambda row: int(row["ts_event_ns"]) // 10 ** 9  # noqa: E731
    if hook == "after_market_closes":
        want = [(end(last[ENTRY_DECISION]), last[ENTRY_DECISION]["o"]), (end(last[EXIT_DECISION]), last[EXIT_DECISION]["o"])]
    elif hook == "before_starting_trading":
        want = [(end(first[ENTRY_NEXT]), first[ENTRY_NEXT]["o"]), (end(first[EXIT_NEXT]), first[EXIT_NEXT]["o"])]
    else:
        want = [(end(first[ENTRY_NEXT]), first[ENTRY_NEXT]["o"]), (end(first[EXIT_NEXT]) - 3600, last[EXIT_DECISION]["o"])]
    failed = sorted({g["name"] for g in outcome["guards"] if g["outcome"] != "pass"})
    return {
        "two_intents_entry_then_exit": [i["reason"] for i in intents] == ["entry", "exit"],
        "intent_instants_are_decision_bar_ends": [i["utc_seconds"] for i in intents]
        == [end(last[ENTRY_DECISION]), end(last[EXIT_DECISION])],
        "fill_instants_and_prices": [(f["utc_seconds"], Decimal(f["price"])) for f in fills]
        == [(t, Decimal(p)) for t, p in want],
        "fill_quantities": [f["quantity"] for f in fills] == ([held, -held] if held else []),
        "fees_zero": all(Decimal(f["fee"]) == 0 for f in fills),
        "ledger_external_unposted": [d["engine_posted"] for d in ledger] == [False, False],
        "ledger_quantities_flat_then_held": [d["quantity"] for d in ledger] == ["0", str(held)],
        "native_end_cash_is_fill_path": Decimal(outcome["totals"]["native_end_cash_usd"])
        == Decimal(CASE["initial_cash_usd"]) - sum(Decimal(f["quantity"]) * Decimal(f["price"]) for f in fills),
        "failed_guards_as_expected": failed == EXPECTED_FAILED_GUARDS[hook],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--child", choices=HOOKS, help=argparse.SUPPRESS)
    args = parser.parse_args()
    os.umask(0o077)
    if args.child:
        os.chdir(args.out / args.child / "engine-cwd")
        return child(args.child, args.out)
    port = load("lumibot_arm_fixture_port", PORT)
    port.refuse_unless_isolated()
    args.out.mkdir(mode=0o700, parents=True, exist_ok=False)
    rows = synthetic_rows()
    runs, results = {}, {}
    for hook in HOOKS:
        run_dir = args.out / hook
        run_dir.mkdir(mode=0o700)
        (run_dir / "engine-cwd").mkdir(mode=0o700)
        env = dict(os.environ, LUMIBOT_CACHE_FOLDER="/tmp/lumibot-cache/probe-" + hook)
        started = clock.monotonic()
        done = subprocess.run([sys.executable, "-I", str(PROBE), "--out", str(args.out), "--child", hook],
                              env=env, cwd=run_dir / "engine-cwd", capture_output=True, check=False)
        (run_dir / "stdout.log").write_bytes(done.stdout)
        (run_dir / "stderr.log").write_bytes(done.stderr)
        runs[hook] = {"exit_code": done.returncode, "wall_seconds": round(clock.monotonic() - started, 3),
                      "stderr_bytes": len(done.stderr),
                      "blocked_host_lookups": (done.stdout + done.stderr).count(b"Could not resolve host")}
        if done.returncode != 0:
            continue
        outcome = json.loads((run_dir / "outcome.json").read_text())
        checks = expectations(hook, outcome, rows)
        record = outcome["record"]
        results[hook] = {
            "expectations": checks, "all_expectations_met": all(checks.values()),
            "intents": [{k: i[k] for k in ("reason", "utc_seconds", "quantity", "decision_price", "decision_equity",
                                           "submitted_engine_clock_utc_seconds", "submission_status",
                                           "order_type", "time_in_force")} for i in record["intents"]],
            "fills": [{k: f[k] for k in ("utc_seconds", "quantity", "price", "fee", "order_type", "time_in_force")}
                      for f in record["fills"]],
            "distribution_ledger": record["distribution_ledger"], "cash_ledger": record["cash_ledger"],
            "totals": outcome["totals"], "lifecycle_calls": outcome["lifecycle_calls"],
            "guards": [{k: g[k] for k in ("name", "outcome")} for g in outcome["guards"]],
            "projection": outcome["projection"], "configuration_facts": outcome["configuration_facts"],
            "warnings": outcome["warnings"], "normalized_economic_sha256": outcome["normalized_economic_sha256"],
        }
    report = {
        "probe": "Lumibot port mechanism probe (synthetic bars)",
        "probe_sha256": hashlib.sha256(PROBE.read_bytes()).hexdigest(),
        "port_sha256": hashlib.sha256(PORT.read_bytes()).hexdigest(),
        "evidence_class": "synthetic fixture under the run sandbox (engine executed through the port; no SPY "
                          "rows, frozen inputs or LEAN data mount)",
        "sessions": list(SESSIONS), "bars": len(rows), "asset": ASSET,
        "distributions": synthetic_distributions(), "runs": runs, "results": results,
        "all_expectations_met": len(results) == len(HOOKS) and all(r["all_expectations_met"] for r in results.values()),
    }
    text = json.dumps(report, indent=2, sort_keys=True, default=str) + "\n"
    (args.out / "mechanism-probe.json").write_text(text)
    print(json.dumps({"all_expectations_met": report["all_expectations_met"], "runs": runs,
                      "failed": {h: sorted(k for k, v in r["expectations"].items() if not v) for h, r in results.items()},
                      "fills": {h: [(f["utc_seconds"], f["quantity"], f["price"]) for f in r["fills"]]
                                for h, r in results.items()},
                      "report_sha256": hashlib.sha256(text.encode()).hexdigest()}, sort_keys=True))
    return 0 if report["all_expectations_met"] else 1


if __name__ == "__main__":
    sys.exit(main())
