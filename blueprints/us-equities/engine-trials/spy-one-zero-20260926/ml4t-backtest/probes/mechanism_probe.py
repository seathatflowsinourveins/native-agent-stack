#!/usr/bin/env python3
"""Mechanism probe for the ml4t-backtest arm, on synthetic bars only.

Preregistered in ../../preregistration.json ``mechanism_probes``: before the first
attempt, under the same sandbox, and never on SPY rows, the frozen inputs or the
LEAN data mount. It runs the port's own ``run_engine`` (fixture_port.py, loaded by
path) over four synthetic hourly sessions of a made-up asset ``SYN`` and checks the
two preregistered mechanisms:

* market-on-open proxy: an order submitted from ``on_data`` at a session's last bar
  fills at the next session's first bar OPEN, stamped at that bar's end instant
  (docs/user-guide/execution-semantics.md lines 11-17 and 43-44 at
  672804b36915742fe18af9cd09b44e9839d39d6f);
* funding posting: a FundingPayment of zero for a flat asset, zero for a position
  opened at the event's own timestamp, and ``-quantity * amount_per_unit`` for a held
  position (docs/user-guide/market-impact.md lines 229-269 at the same commit).

A probe cannot change a row status, the binding, the sheet or the scorer.

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
import sys
from zoneinfo import ZoneInfo

PROBE = Path(__file__).resolve()
PORT = PROBE.parent.parent / "fixture_port.py"
NEW_YORK = ZoneInfo("America/New_York")
SESSIONS = ("2031-01-06", "2031-01-07", "2031-01-08", "2031-01-09")  # synthetic, EST, Mon-Thu
STARTS = ("09:00", "10:00", "11:00", "12:00", "13:00", "14:00", "15:00")
ASSET = "SYN"
CASE = {"id": "synthetic", "initial_cash_usd": "100000", "sizing_buffer": "0.98", "target": "1",
        "fee_usd": "0", "slippage": "0", "entry_decision_date": SESSIONS[0],
        "exit_decision_date": SESSIONS[2], "currency": "USD"}
PER_SHARE = {"flat": Decimal("0.21"), "opened_same_bar": Decimal("0.29"), "held": Decimal("0.37")}


def load_port():
    spec = importlib.util.spec_from_file_location("ml4t_arm_fixture_port", PORT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def synthetic_rows() -> list:
    """Four 7-bar sessions; each session opens 0.99 below the previous close."""
    rows = []
    for s, day in enumerate(SESSIONS):
        base = Decimal("100") + Decimal("0.5") * s
        for k, start in enumerate(STARTS):
            o = base + Decimal("0.25") * k + Decimal("0.0100")
            c = o + Decimal("0.1300")
            h, low = max(o, c) + Decimal("0.0500"), min(o, c) - Decimal("0.0500")
            begin = datetime.combine(date.fromisoformat(day), time.fromisoformat(start), NEW_YORK)
            end = int((begin + timedelta(hours=1)).timestamp())
            rows.append({"session_date": day, "local_start": start, "ts_event_ns": end * 10 ** 9,
                         "o": str(o.quantize(Decimal("0.0001"))), "h": str(h.quantize(Decimal("0.0001"))),
                         "l": str(low.quantize(Decimal("0.0001"))), "c": str(c.quantize(Decimal("0.0001"))),
                         "v": 1000 + 10 * s + k})
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    args.out.mkdir(mode=0o700, parents=True, exist_ok=False)
    port = load_port()
    port.refuse_unless_isolated()
    _, fixture = port.load_helpers()
    rows = synthetic_rows()
    first = {}
    for row in rows:
        first.setdefault(row["session_date"], row)
    events = []
    for label, day in (("flat", SESSIONS[0]), ("opened_same_bar", SESSIONS[1]), ("held", SESSIONS[2])):
        amount = -float(PER_SHARE[label])
        events.append({"ex_date": day, "per_share": str(PER_SHARE[label]),
                       "utc_seconds": int(first[day]["ts_event_ns"]) // 10 ** 9,
                       "session_date": day, "local_start": first[day]["local_start"],
                       "amount_per_unit": amount, "amount_per_unit_repr": repr(amount),
                       "lean_ex_date_instant_utc_seconds": int(first[day]["ts_event_ns"]) // 10 ** 9 - 36000,
                       "probe_label": label})
    outcome = port.run_engine(rows, events, CASE, ASSET, fixture, label="probe")
    record = outcome["record"]
    fills, ledger, intents = record["fills"], record["distribution_ledger"], record["intents"]
    by_end = {int(r["ts_event_ns"]) // 10 ** 9: r for r in rows}
    entry_bar, exit_bar = first[SESSIONS[1]], first[SESSIONS[3]]
    held = intents[0]["quantity"] if intents else None
    expectations = {
        "two_intents_entry_then_exit": [i["reason"] for i in intents] == ["entry", "exit"],
        "entry_fill_at_next_session_first_bar_end": bool(fills)
        and fills[0]["utc_seconds"] == int(entry_bar["ts_event_ns"]) // 10 ** 9,
        "entry_fill_at_that_bar_open": bool(fills) and Decimal(fills[0]["price"]) == Decimal(entry_bar["o"]),
        "exit_fill_at_next_session_first_bar_end": len(fills) > 1
        and fills[1]["utc_seconds"] == int(exit_bar["ts_event_ns"]) // 10 ** 9,
        "exit_fill_at_that_bar_open": len(fills) > 1 and Decimal(fills[1]["price"]) == Decimal(exit_bar["o"]),
        "fill_price_is_not_the_bar_close": all(Decimal(f["price"]) != Decimal(by_end[f["utc_seconds"]]["c"])
                                               for f in fills),
        "submission_clock_is_decision_bar_end": all(i["submitted_engine_clock_utc_seconds"] == i["utc_seconds"]
                                                    for i in intents),
        "funding_flat_records_zero": len(ledger) > 0 and ledger[0]["engine_posted"] is True
        and ledger[0]["quantity"] == "0" and Decimal(ledger[0]["amount"]) == 0,
        "funding_opened_same_bar_records_zero": len(ledger) > 1 and ledger[1]["engine_posted"] is True
        and ledger[1]["quantity"] == "0" and Decimal(ledger[1]["amount"]) == 0,
        "funding_held_posts_quantity_times_per_share": len(ledger) > 2 and ledger[2]["engine_posted"] is True
        and held is not None and ledger[2]["quantity"] == str(held)
        and Decimal(ledger[2]["amount"]) == held * PER_SHARE["held"],
        "funding_posted_at_event_bar_end": all(d["utc_seconds"] == e["utc_seconds"] for d, e in zip(ledger, events)),
        "every_port_guard_passes": all(g["outcome"] == "pass" for g in outcome["guards"]),
    }
    report = {
        "probe": "ml4t-backtest mechanism probe (synthetic bars)",
        "probe_sha256": hashlib.sha256(PROBE.read_bytes()).hexdigest(),
        "port_sha256": hashlib.sha256(PORT.read_bytes()).hexdigest(),
        "evidence_class": "synthetic fixture under the run sandbox (engine executed; no SPY rows, frozen "
                          "inputs or LEAN data mount)",
        "engine": outcome["engine"],
        "rows": {"sessions": list(SESSIONS), "bars": len(rows), "asset": ASSET,
                 "first_bar_of_each_session": [{k: first[d][k] for k in ("session_date", "ts_event_ns", "o", "c")}
                                               for d in SESSIONS]},
        "funding_input": events,
        "expectations": expectations,
        "all_expectations_met": all(expectations.values()),
        "intents": intents, "fills": fills, "distribution_ledger": ledger,
        "cash_ledger": record["cash_ledger"], "totals": outcome["totals"],
        "guards": outcome["guards"], "projection": outcome["projection"],
        "configuration_facts": outcome["configuration_facts"], "warnings": outcome["warnings"],
        "normalized_economic_sha256": outcome["normalized_economic_sha256"],
    }
    text = json.dumps(report, indent=2, sort_keys=True, default=str) + "\n"
    (args.out / "mechanism-probe.json").write_text(text)
    failed = sorted(name for name, ok in expectations.items() if not ok)
    print(json.dumps({"all_expectations_met": report["all_expectations_met"], "failed": failed,
                      "fills": [(f["utc_seconds"], f["quantity"], f["price"]) for f in fills],
                      "funding": [(d["utc_seconds"], d["quantity"], d["amount"]) for d in ledger],
                      "report_sha256": hashlib.sha256(text.encode()).hexdigest()}, sort_keys=True))
    return 0 if report["all_expectations_met"] else 1


if __name__ == "__main__":
    sys.exit(main())
