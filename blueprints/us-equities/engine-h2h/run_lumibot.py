#!/usr/bin/env python3
"""Lumibot 4.6.0 runner for the Alpaca engine head-to-head (paper only; never live).

backtest  The frozen order script through Lumibot's own Strategy API and its
          PandasDataBacktesting engine, over LEAN's bundled SPY minute trade and quote
          bars (read-only; the same bars LEAN's backtest uses). Offline: it refuses to
          start while any credential variable is set, and removes LUMIWEALTH_API_KEY,
          Lumibot's only cloud and error-reporting switch.
paper     Untested boundary. The same strategy under Lumibot's own Alpaca broker with
          PAPER forced true. Refuses unless given this engine's dedicated env file and a
          paper host.

Orders use Lumibot's documented API only: create_order/submit_order/modify_order/
cancel_order/sell_all, order_class for bracket/OTO/OCO, time_in_force passed through
for opg/cls, and custom_params={"extended_hours": True} (Lumibot's documented raw
passthrough) for extended hours. trail_percent follows Lumibot's documented unit
(0.10 = 10 percent).

Run it with the isolated Lumibot interpreter, without writing bytecode:
  tools/lumibot-4.6.0-r20260925/bin/python -B run_lumibot.py backtest --lean-data ... --out ...
"""
from __future__ import annotations

import argparse
import datetime as dt
from decimal import Decimal
import json
import math
import os
from pathlib import Path
import sys
import zipfile

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import h2h_common as common  # noqa: E402

ET = "America/New_York"
AUCTION = {"opg": dt.time(9, 30), "cls": dt.time(16, 0)}
STATE = {"unprocessed": "submitted", "submitted": "open", "open": "open", "new": "open", "cancelling": "open",
         "canceled": "canceled", "fill": "filled", "partial_fill": "partially_filled", "error": "refused",
         "expired": "expired", "unknown": "unknown"}


def lean_minute_frame(data_dir, dates):
    """LEAN's bundled SPY minute trade and quote bars as one Lumibot DataFrame
    (open/high/low/close/volume plus bid/ask closes), indexed by bar start in ET."""
    import pandas as pd
    frames = []
    for date in dates:
        stamp = date.replace("-", "")
        day = pd.Timestamp(date, tz=ET)
        with zipfile.ZipFile(Path(data_dir) / f"{stamp}_trade.zip") as archive:
            trade = pd.read_csv(archive.open(archive.namelist()[0]), header=None,
                                names=["ms", "open", "high", "low", "close", "volume"])
        with zipfile.ZipFile(Path(data_dir) / f"{stamp}_quote.zip") as archive:
            quote = pd.read_csv(archive.open(archive.namelist()[0]), header=None,
                                names=["ms", "bo", "bh", "bl", "bid", "bs", "ao", "ah", "al", "ask", "as"])
        frame = trade.merge(quote[["ms", "bid", "ask"]], on="ms", how="left").sort_values("ms")
        frame[["bid", "ask"]] = frame[["bid", "ask"]].ffill()
        for column in ("open", "high", "low", "close", "bid", "ask"):
            frame[column] = frame[column] / 10000.0
        frame.index = day + pd.to_timedelta(frame.pop("ms"), unit="ms")
        frames.append(frame)
    return pd.concat(frames)


def _usable(value):
    return value is not None and not (isinstance(value, float) and math.isnan(value)) and value > 0


class LumibotOps:
    """h2h_common.StepMachine operations through Lumibot's own Strategy methods."""

    def __init__(self, strategy, asset, script):
        self.s, self.asset, self.script = strategy, asset, script
        self.meta = {}

    def now(self):
        return self.s.get_datetime()

    def quote(self):
        quote = self.s.get_quote(self.asset)
        bid, ask = getattr(quote, "bid", None), getattr(quote, "ask", None)
        if not (_usable(bid) and _usable(ask)) or ask < bid:
            last = self.s.get_last_price(self.asset)
            if not _usable(last):
                raise common.NoQuote()
            bid = ask = last
        return Decimal(str(bid)), Decimal(str(ask))

    def position(self):
        position = self.s.get_position(self.asset)
        return Decimal(str(position.quantity)) if position is not None else Decimal(0)

    def open_orders(self):
        return sum(1 for order in self.s.get_orders() if order.is_active())

    def submit(self, tag, order):
        from lumibot.entities import Order
        kwargs = {"time_in_force": order["tif"]}
        if order["extended_hours"]:
            kwargs["custom_params"] = {"extended_hours": True}
        if order["class"] == "bracket":
            kwargs.update(order_class=Order.OrderClass.BRACKET, limit_price=float(order["limit"]),
                          secondary_limit_price=float(order["take_profit"]), secondary_stop_price=float(order["stop_loss"]))
        elif order["class"] == "oto":
            kwargs.update(order_class=Order.OrderClass.OTO, limit_price=float(order["limit"]),
                          secondary_stop_price=float(order["stop_loss"]))
        elif order["class"] == "oco":
            kwargs.update(order_class=Order.OrderClass.OCO, limit_price=float(order["take_profit"]),
                          stop_price=float(order["stop_loss"]))
        elif order["type"] == "limit":
            kwargs["limit_price"] = float(order["limit"])
        elif order["type"] == "stop":
            kwargs["stop_price"] = float(order["stop"])
        elif order["type"] == "stop_limit":
            kwargs.update(stop_price=float(order["stop"]), stop_limit_price=float(order["limit"]))
        elif order["type"] == "trailing_stop":
            kwargs["trail_percent"] = float(order["trail_percent"] / 100)   # Lumibot's documented unit
        handle = self.s.create_order(self.asset, order["qty"], order["side"], **kwargs)
        handle = self.s.submit_order(handle) or handle
        self.meta[id(handle)] = {"order": order, "fill_time": None}
        return handle

    def replace(self, handle, limit):
        self.s.modify_order(handle, limit_price=float(limit))

    def cancel(self, handle):
        self.s.cancel_order(handle)

    def is_open(self, handle):
        return handle.is_active()

    def flatten(self, session):
        if session == "regular":
            self.s.sell_all()
            return
        for order in self.s.get_orders():
            if order.is_active():
                self.s.cancel_order(order)
        quantity = self.position()
        if quantity:
            bid, ask = self.quote()
            price = common.price("marketable_sell" if quantity > 0 else "marketable_buy", bid, ask, self.script)
            side = "sell" if quantity > 0 else "buy"
            order = self.s.create_order(self.asset, abs(quantity), side, limit_price=float(price), time_in_force="day",
                                        custom_params={"extended_hours": True})
            self.s.submit_order(order)

    cleanup = flatten

    def observe(self, handle):
        status = str(getattr(handle, "status", "unknown")).lower()
        state = STATE.get(status, "unknown")
        filled = sum(Decimal(str(t.quantity)) for t in getattr(handle, "transactions", []) or [])
        if state == "open" and filled:
            state = "partially_filled"
        meta = self.meta.get(id(handle), {})
        order = meta.get("order", {})
        observed = {"state": state, "filled_qty": filled, "qty": order.get("qty"),
                    "accepted_price": getattr(handle, "limit_price", None)}
        children = list(getattr(handle, "child_orders", []) or [])
        if order.get("class") in ("bracket", "oto", "oco"):
            observed["legs_open"] = sum(1 for child in children if child.is_active())
            observed["legs_expected"] = {"bracket": 2, "oto": 1, "oco": 2}[order["class"]]
            if order["class"] == "oco":
                observed["state"] = "open" if observed["legs_open"] else state
        if state == "filled" and meta:
            if meta["fill_time"] is None:
                meta["fill_time"] = self.now()
            auction = AUCTION.get(order.get("tif"))
            observed["filled_before_auction"] = bool(auction and meta["fill_time"].time() < auction)
        return observed

    def fault_point(self, kind, tag):
        """Paper only: the step machine journals the fault point; the orchestrator acts
        on it (kill/stop end this process; the step waits until then or times out)."""


def make_strategy_class():
    from lumibot.entities import Asset
    from lumibot.strategies import Strategy

    class H2HLumibotStrategy(Strategy):
        def initialize(self):
            params = self.parameters
            # Minute bars offline; a finer step on paper so step timeouts are meaningful.
            self.sleeptime = "5S" if params["mode"] == "paper" else "1M"
            self.set_market("24/7")   # the script's own phase clock decides what runs when
            self.h2h_script = common.load_script(params["script"])
            self.h2h_asset = Asset(self.h2h_script["symbol"])
            self.h2h_journal = common.Journal(params["journal"], engine="lumibot", mode=params["mode"],
                                              script_sha256=common.file_sha256(params["script"]))
            self.h2h_ops = LumibotOps(self, self.h2h_asset, self.h2h_script)
            self.h2h_machine = common.StepMachine(self.h2h_script, self.h2h_ops, self.h2h_journal,
                                                  offline=params["mode"] != "paper")
            self.h2h_pending = sorted((date, self.h2h_script["phases"][phase]["at_et"], phase)
                                      for date, phases in params["plan"].items() for phase in phases)

        def on_trading_iteration(self):
            now = self.get_datetime()
            today = now.strftime("%Y-%m-%d")
            while self.h2h_pending:
                date, at, phase = self.h2h_pending[0]
                date = today if date == "today" else date
                if (date, at) > (today, now.strftime("%H:%M")):
                    break
                self.h2h_pending.pop(0)
                self.h2h_machine.enqueue_phase(phase)
            self.h2h_machine.advance()

        # Lumibot's own order lifecycle events, journaled with the engine clock and the
        # host wall clock (paper latency: fill -> engine uses the wall clock).
        def _engine_event(self, event, order, **fields):
            self.h2h_journal.event("engine_event", event=event, order_id=str(getattr(order, "identifier", "")),
                                   status=str(getattr(order, "status", "")), engine_time=str(self.get_datetime()), **fields)

        def on_new_order(self, order):
            self._engine_event("new", order)

        def on_canceled_order(self, order):
            self._engine_event("canceled", order)

        def on_partially_filled_order(self, position, order, price, quantity, multiplier):
            self._engine_event("partial_fill", order, price=price, quantity=quantity)
            self.h2h_journal.event("order_state", state="partially_filled", order_id=str(order.identifier))

        def on_filled_order(self, position, order, price, quantity, multiplier):
            self._engine_event("fill", order, price=price, quantity=quantity)

        def on_strategy_end(self):
            self.h2h_journal.event("run_end", results=self.h2h_machine.results,
                                   final_quantity=self.h2h_ops.position(), open_orders=self.h2h_ops.open_orders(),
                                   unfinished=not self.h2h_machine.idle(), pending_phases=len(self.h2h_pending))
            self.h2h_journal.close()

    return H2HLumibotStrategy


def lumibot_environment():
    """Before Lumibot is imported: its credentials module otherwise walks from the script
    directory and the cwd up to / and loads the first .env and .env.local it finds
    (lumibot/credentials.py:118-173), and LUMIWEALTH_API_KEY enables its cloud reports."""
    os.environ["LUMIBOT_DISABLE_DOTENV"] = "1"
    os.environ.pop("LUMIWEALTH_API_KEY", None)


def offline_environment():
    for name in os.environ:
        if name.startswith(("APCA_", "ALPACA_")):
            raise common.H2HRefusal("h2h:credentials_present_in_offline_run")
    lumibot_environment()
    os.environ["IS_BACKTESTING"] = "True"


def results_from_journal(path, script):
    rows = [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
    end = next((row for row in reversed(rows) if row["kind"] == "run_end"), None)
    if end is None:
        raise ValueError("journal_without_run_end")
    partial = any(row["kind"] == "order_state" and row.get("state") == "partially_filled" for row in rows)
    return common.finalize_offline_results(end["results"], script, partial_fills_seen=partial), end


def command_backtest(args):
    offline_environment()
    output = args.out.resolve()
    if output.exists():
        raise ValueError("use a fresh output directory")
    os.umask(0o077)
    output.mkdir(parents=True, mode=0o700)
    os.chdir(output)   # Lumibot writes its logs and tearsheets under the working directory
    from lumibot.backtesting import PandasDataBacktesting
    from lumibot.entities import Asset, Data
    script = common.load_script()
    dates = list(common.BACKTEST_PLAN)
    asset = Asset(script["symbol"])
    frame = lean_minute_frame(args.lean_data, dates)
    start = dt.datetime.fromisoformat(dates[0])
    end = dt.datetime.fromisoformat(dates[-1]) + dt.timedelta(days=1)
    strategy = make_strategy_class()
    journal = output / "journal.jsonl"
    strategy.run_backtest(
        PandasDataBacktesting, start, end, pandas_data={asset: Data(asset, frame, timestep="minute")},
        benchmark_asset=None, budget=100000, show_plot=False, show_tearsheet=False, save_tearsheet=False,
        show_indicators=False, save_stats_file=False, show_progress_bar=False, analyze_backtest=False,
        parameters={"script": str(common.SCRIPT_PATH), "journal": str(journal), "mode": "backtest",
                    "plan": {date: list(phases) for date, phases in common.BACKTEST_PLAN.items()}})
    results, end_row = results_from_journal(journal, script)
    summary = common.summarize(results, script=script)
    receipt = {"engine": "lumibot", "mode": "backtest",
               "evidence_class": "HIST-backtest (local integration; LEAN's bundled SPY bars through Lumibot's PandasData)",
               "script_sha256": common.file_sha256(common.SCRIPT_PATH), "runner_sha256": common.file_sha256(__file__),
               "journal_sha256": common.file_sha256(journal), "final_quantity": str(end_row["final_quantity"]),
               "open_orders": end_row["open_orders"], "unfinished": end_row["unfinished"],
               "results": results, "summary": summary}
    (output / "results.json").write_text(json.dumps(receipt, indent=2, default=str) + "\n")
    print(json.dumps({"summary": summary, "final_quantity": receipt["final_quantity"],
                      "open_orders": receipt["open_orders"]}, indent=2, default=str))
    return 0


def command_paper(args):
    credentials = common.load_paper_env("lumibot", args.env_file)
    # Only the dedicated file's pair reaches the broker: no inherited broker variables.
    for name in list(os.environ):
        if name.startswith(("APCA_", "ALPACA_")):
            os.environ.pop(name)
    lumibot_environment()
    from lumibot.brokers import Alpaca
    from lumibot.traders import Trader
    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    broker = Alpaca({"API_KEY": credentials["key_id"], "API_SECRET": credentials["secret"], "PAPER": True})
    if broker.is_paper is not True:
        raise common.H2HRefusal("h2h:not_paper_host")
    strategy = make_strategy_class()(broker=broker, parameters={
        "script": str(common.SCRIPT_PATH), "journal": str(output / "journal.jsonl"), "mode": "paper",
        "plan": {"today": args.phases.split(",")}})
    trader = Trader()
    trader.add_strategy(strategy)
    trader.run_all()
    return 0


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    backtest = commands.add_parser("backtest")
    backtest.add_argument("--lean-data", type=Path, required=True,
                          help="LEAN's Data/equity/usa/minute/spy directory (read-only)")
    backtest.add_argument("--out", type=Path, required=True)
    paper = commands.add_parser("paper")
    paper.add_argument("--env-file", type=Path, default=None,
                       help="this engine's dedicated file: " + common.env_file_name("lumibot"))
    paper.add_argument("--out", type=Path, required=True)
    paper.add_argument("--phases", default="pre_open,regular,faults,close,reconcile")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return {"backtest": command_backtest, "paper": command_paper}[args.command](args)
    except common.H2HRefusal as refusal:
        print(json.dumps({"refused": str(refusal)}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
