#!/usr/bin/env python3
"""Decision-hook probe for the Lumibot arm, on synthetic bars only.

Preregistered in ../../preregistration.json ``mechanism_probes``: before the first
attempt, under the run sandbox without the /data mount, and never on SPY rows, the
frozen inputs or the LEAN data. It asks the pinned engine (Lumibot 4.6.1, imported
from the isolated environment; this file contains no Lumibot code) four questions
the preregistration left to observation:

* which bar ``get_historical_prices(asset, 1, "hour", timeshift=...)`` returns at
  each lifecycle hook when bars are indexed at their END instant;
* when each lifecycle hook runs on the engine clock for a pure PandasData backtest
  with an hour timestep;
* at which instant and price a GTC market order fills when it is submitted from
  each candidate decision hook, across a gap longer than a day (like 2019-12-31 to
  2020-01-02) and an overnight gap (like 2020-04-29 to 2020-04-30);
* whether any dividend is credited with hour data, with and without a ``dividend``
  column (the primary attempt never supplies one).

Candidate hooks, each in its own child process with a fresh engine:

* ``after_market_closes``: decide at the session-final bar's end (16:00 New York);
* ``before_market_opens``: decide before the next session (minutes_before_opening);
* ``before_starting_trading``: decide at the next session's open instant (10:00).

The synthetic calendar is made-up 2021 dates (past dates, because the engine clamps
a future backtest end to the current time): sessions Mon 2021-03-08, Tue 03-09,
Thu 03-11, Fri 03-12, Mon 03-15 (after the 2021-03-14 DST change), Tue 03-16 and
Wed 03-17. The entry decision is Tue 03-09 (next session Thu, a 42-hour gap) and the
exit decision Mon 03-15 (next session Tue, an 18-hour gap). Each session has seven
hourly bars labelled 09:00 to 15:00 local start and indexed at their end (10:00 to
16:00). A probe cannot change a row status, the binding, the sheet or the scorer.

Fill instants come from the broker's trade-event log (the engine clock when it processed the
fill). ``on_filled_order`` is delivered when the strategy's event queue drains at the next
lifecycle call, so its clock is recorded only as a delivery time. ``risk_free_rate=0.0`` is
passed because the first run of this probe (probe-01, without it) showed the strategy asking
Yahoo for ^IRX when it dumps its statistics; the sandbox refused each lookup.

Usage (inside the run sandbox, without the /data mount)::

    $ENV/bin/python -I probes/hook_probe.py --out /out/probe
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time as clock
from zoneinfo import ZoneInfo

PROBE = Path(__file__).resolve()
NEW_YORK = ZoneInfo("America/New_York")
SESSIONS = ("2021-03-08", "2021-03-09", "2021-03-11", "2021-03-12", "2021-03-15", "2021-03-16", "2021-03-17")
STARTS = ("09:00", "10:00", "11:00", "12:00", "13:00", "14:00", "15:00")
ENTRY_DECISION, ENTRY_NEXT = "2021-03-09", "2021-03-11"
EXIT_DECISION, EXIT_NEXT = "2021-03-15", "2021-03-16"
SYMBOL = "SYN"
QUANTITY = 100
DIVIDEND_EX_DATE = "2021-03-12"  # held date in every hook variant; only the dividend variant has the column
DIVIDEND_PER_SHARE = 0.37
VARIANTS = ("after_market_closes", "before_market_opens", "before_starting_trading", "dividend_column")


def utc_seconds(value) -> int:
    return int(value.timestamp())


def bars() -> list:
    """Seven hourly bars per session, END-indexed; every open and close is distinct."""
    rows = []
    for s, day in enumerate(SESSIONS):
        for k, start in enumerate(STARTS):
            o = Decimal("100") + Decimal(s) + Decimal("0.1") * k + Decimal("0.01")
            c = o + Decimal("0.05")
            begin = datetime.combine(date.fromisoformat(day), time.fromisoformat(start), NEW_YORK)
            rows.append({"session_date": day, "local_start": start,
                         "end_utc_seconds": utc_seconds(begin + timedelta(hours=1)),
                         "open": str(o), "high": str(max(o, c) + Decimal("0.02")),
                         "low": str(min(o, c) - Decimal("0.02")), "close": str(c), "volume": 1000 + 10 * s + k})
    return rows


def child(variant: str, run_dir: Path) -> int:
    """One backtest in this fresh process; writes run_dir/report.json."""
    import pandas as pd
    from lumibot.backtesting import PandasDataBacktesting
    from lumibot.entities import Asset, Data
    from lumibot.strategies import Strategy

    rows = bars()
    index = pd.DatetimeIndex([datetime.fromtimestamp(r["end_utc_seconds"], tz=timezone.utc) for r in rows])
    frame = pd.DataFrame({"open": [float(r["open"]) for r in rows], "high": [float(r["high"]) for r in rows],
                          "low": [float(r["low"]) for r in rows], "close": [float(r["close"]) for r in rows],
                          "volume": [float(r["volume"]) for r in rows]}, index=index)
    if variant == "dividend_column":
        frame["dividend"] = [DIVIDEND_PER_SHARE if (r["session_date"] == DIVIDEND_EX_DATE and r["local_start"] == "09:00")
                             else 0.0 for r in rows]
    asset = Asset(symbol=SYMBOL, asset_type="stock")
    quote = Asset(symbol="USD", asset_type="forex")
    data = Data(asset, frame, timestep="hour", quote=quote)
    session_of_end = {r["end_utc_seconds"]: r["session_date"] for r in rows}
    last_end = {}
    for r in rows:
        last_end[r["session_date"]] = r["end_utc_seconds"]
    decide_on = {"after_market_closes": {ENTRY_DECISION: "entry", EXIT_DECISION: "exit"},
                 "dividend_column": {ENTRY_DECISION: "entry", EXIT_DECISION: "exit"},
                 "before_market_opens": {ENTRY_NEXT: "entry", EXIT_NEXT: "exit"},
                 "before_starting_trading": {ENTRY_NEXT: "entry", EXIT_NEXT: "exit"}}[variant]
    decision_hook = "after_market_closes" if variant == "dividend_column" else variant
    record = {"calls": [], "reads": [], "orders": [], "fills": []}

    def read(strategy, label, timeshift):
        got = strategy.get_historical_prices(asset, 1, "hour", timeshift=timeshift)
        df = getattr(got, "df", None)
        if df is None or len(df.index) == 0:
            return {"label": label, "timeshift": timeshift, "bar_end_utc_seconds": None}
        stamp = df.index[-1]
        return {"label": label, "timeshift": timeshift, "bar_end_utc_seconds": utc_seconds(stamp),
                "bar_session": session_of_end.get(utc_seconds(stamp)),
                "open": repr(float(df["open"].iloc[-1])), "close": repr(float(df["close"].iloc[-1]))}

    class HookProbe(Strategy):
        def initialize(self):
            self.sleeptime = "60M"

        def _note(self, hook):
            now = self.get_datetime()
            record["calls"].append({"hook": hook, "clock_utc_seconds": utc_seconds(now),
                                    "local": now.astimezone(NEW_YORK).strftime("%Y-%m-%d %H:%M"),
                                    "cash": repr(float(self.cash)),
                                    "position": repr(float(self.get_position(asset).quantity))
                                    if self.get_position(asset) is not None else "0"})
            day = now.astimezone(NEW_YORK).date().isoformat()
            if hook == decision_hook and day in decide_on:
                reason = decide_on[day]
                reads = [read(self, "timeshift=-1", -1), read(self, "timeshift=0", 0)]
                record["reads"].append({"hook": hook, "clock_utc_seconds": utc_seconds(now), "reads": reads})
                side = "buy" if reason == "entry" else "sell"
                order = self.create_order(asset, QUANTITY, side, order_type="market", time_in_force="gtc")
                submitted = self.submit_order(order)
                record["orders"].append({"ordinal": len(record["orders"]) + 1, "reason": reason, "side": side,
                                         "submitted_clock_utc_seconds": utc_seconds(now),
                                         "status_after_submit": str(getattr(submitted, "status", None)),
                                         "time_in_force": str(getattr(submitted, "time_in_force", None))})

        def before_market_opens(self):
            self._note("before_market_opens")

        def before_starting_trading(self):
            self._note("before_starting_trading")

        def on_trading_iteration(self):
            self._note("on_trading_iteration")

        def before_market_closes(self):
            self._note("before_market_closes")

        def after_market_closes(self):
            self._note("after_market_closes")

        def on_filled_order(self, position, order, price, quantity, multiplier):
            now = self.get_datetime()
            record["fills"].append({"clock_utc_seconds": utc_seconds(now),
                                    "local": now.astimezone(NEW_YORK).strftime("%Y-%m-%d %H:%M"),
                                    "price": repr(float(price)), "quantity": repr(float(quantity)),
                                    "side": str(order.side), "avg_fill_price": repr(order.avg_fill_price)})

    started = clock.monotonic()
    # risk_free_rate is given explicitly: left as None, the strategy's risk_free_rate property
    # asks Yahoo for ^IRX when the stats are dumped (probe-01 observed three blocked lookups).
    result, strategy = HookProbe.run_backtest(
        PandasDataBacktesting, datetime(2021, 3, 8, 0, 0), datetime(2021, 3, 17, 23, 59),
        pandas_data=[data], budget=100000.0, benchmark_asset=None, risk_free_rate=0.0,
        analyze_backtest=False, show_plot=False, show_tearsheet=False, save_tearsheet=False,
        show_indicators=False, show_progress_bar=False, save_stats_file=False, save_logfile=False,
        quiet_logs=True, minutes_before_opening=60, minutes_before_closing=5, name="hook_probe_" + variant)
    wall = round(clock.monotonic() - started, 3)
    log = strategy.broker._trade_event_log_df
    trade_events = []
    if log is not None and len(log.index):
        for _, row in log.iterrows():
            trade_events.append({"time_utc_seconds": utc_seconds(row["time"]), "status": str(row["status"]),
                                 "side": str(row["side"]), "price": None if row["price"] is None else repr(row["price"]),
                                 "filled_quantity": None if row["filled_quantity"] is None else repr(row["filled_quantity"]),
                                 "trade_cost": repr(row["trade_cost"]), "time_in_force": str(row["time_in_force"]),
                                 "price_source": None if row.get("price_source") is None else str(row.get("price_source")),
                                 "event_kind": str(row.get("event_kind"))})
    by_end = {r["end_utc_seconds"]: r for r in rows}
    for fill in record["fills"]:
        bar = by_end.get(fill["clock_utc_seconds"])
        opens = [r for r in rows if Decimal(r["open"]) == Decimal(fill["price"])]
        fill["price_is_open_of_bar"] = [{"session_date": r["session_date"], "local_start": r["local_start"],
                                         "end_utc_seconds": r["end_utc_seconds"]} for r in opens]
        fill["bar_indexed_at_fill_clock"] = None if bar is None else {"session_date": bar["session_date"],
                                                                      "local_start": bar["local_start"]}
    report = {"variant": variant, "decision_hook": decision_hook, "wall_seconds": wall,
              "final_cash": repr(float(strategy.cash)),
              "final_position": repr(float(strategy.get_position(asset).quantity))
              if strategy.get_position(asset) is not None else "0",
              "record": record, "trade_events": trade_events,
              "session_last_bar_end": last_end}
    (run_dir / "report.json").write_text(json.dumps(report, indent=1, sort_keys=True) + "\n")
    return 0


def summarize(rows, reports) -> dict:
    first_end = {}
    final_open = {}
    for r in rows:
        first_end.setdefault(r["session_date"], r)
        final_open[r["session_date"]] = r
    target = {"entry": first_end[ENTRY_NEXT], "exit": first_end[EXIT_NEXT]}
    decision_bar = {"entry": final_open[ENTRY_DECISION], "exit": final_open[EXIT_DECISION]}
    out = {}
    for variant, report in reports.items():
        # The fill instant is the broker clock the engine logged with the fill event. The
        # on_filled_order callback is delivered later, when the strategy's event queue drains
        # at the next lifecycle call, so its clock is recorded separately and never used here.
        fills = [e for e in report["trade_events"] if e["status"] == "fill"]
        delivered = report["record"]["fills"]
        orders = report["record"]["orders"]
        rows_out = []
        for order, fill, callback in zip(orders, fills, delivered):
            want = target[order["reason"]]
            rows_out.append({
                "reason": order["reason"], "submitted_clock_utc_seconds": order["submitted_clock_utc_seconds"],
                "fill_clock_utc_seconds": fill["time_utc_seconds"], "fill_price": fill["price"],
                "on_filled_order_delivered_utc_seconds": callback["clock_utc_seconds"],
                "equals_next_session_first_bar_end": fill["time_utc_seconds"] == want["end_utc_seconds"],
                "equals_next_session_first_bar_open": Decimal(fill["price"]) == Decimal(want["open"]),
                "equals_decision_bar_open": Decimal(fill["price"]) == Decimal(decision_bar[order["reason"]]["open"]),
                "submitted_before_fill": order["submitted_clock_utc_seconds"] < fill["time_utc_seconds"]})
        out[variant] = {"orders": len(orders), "fills": len(fills), "per_order": rows_out,
                        "cash_events": sum(1 for e in report["trade_events"] if e["event_kind"] != "trade"),
                        "final_cash": report["final_cash"], "final_position": report["final_position"]}
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--child", choices=VARIANTS, help=argparse.SUPPRESS)
    args = parser.parse_args()
    os.umask(0o077)
    if args.child:
        run_dir = args.out / args.child
        os.chdir(run_dir)
        return child(args.child, run_dir)
    names = [name for _, name in socket.if_nameindex()]
    if names != ["lo"]:
        raise SystemExit("refused: network_not_isolated:" + ",".join(names))
    args.out.mkdir(mode=0o700, parents=True, exist_ok=False)
    runs, reports = {}, {}
    for variant in VARIANTS:
        run_dir = args.out / variant
        run_dir.mkdir(mode=0o700)
        env = dict(os.environ, LUMIBOT_CACHE_FOLDER="/tmp/lumibot-cache/" + variant)
        started = clock.monotonic()
        done = subprocess.run([sys.executable, "-I", str(PROBE), "--out", str(args.out), "--child", variant],
                              env=env, cwd=run_dir, capture_output=True, check=False)
        (run_dir / "stdout.log").write_bytes(done.stdout)
        (run_dir / "stderr.log").write_bytes(done.stderr)
        runs[variant] = {"exit_code": done.returncode, "wall_seconds": round(clock.monotonic() - started, 3),
                         "stderr_sha256": hashlib.sha256(done.stderr).hexdigest(),
                         "stderr_bytes": len(done.stderr),
                         "blocked_host_lookups": done.stderr.count(b"Could not resolve host"),
                         "relative_tilde_directory_created": (run_dir / "~").exists(),
                         "working_directory_entries": sorted(p.name for p in run_dir.iterdir())}
        if done.returncode == 0:
            reports[variant] = json.loads((run_dir / "report.json").read_text())
    rows = bars()
    report = {"probe": "Lumibot decision-hook probe (synthetic bars)",
              "probe_sha256": hashlib.sha256(PROBE.read_bytes()).hexdigest(),
              "evidence_class": "synthetic fixture under the run sandbox (engine executed; no SPY rows, frozen "
                                "inputs or LEAN data mount)",
              "sessions": list(SESSIONS), "bars": len(rows), "runs": runs,
              "summary": summarize(rows, reports) if len(reports) == len(VARIANTS) else None,
              "reports": reports}
    text = json.dumps(report, indent=1, sort_keys=True) + "\n"
    (args.out / "hook-probe.json").write_text(text)
    print(json.dumps({"runs": runs, "summary": report["summary"],
                      "report_sha256": hashlib.sha256(text.encode()).hexdigest()}, indent=1, sort_keys=True))
    return 0 if all(r["exit_code"] == 0 for r in runs.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
