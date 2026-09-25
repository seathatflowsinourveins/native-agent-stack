#!/usr/bin/env python3
"""NautilusTrader 2.0.0rc5 + our Alpaca adapter: the incumbent's head-to-head runner.

synthetic  The frozen order script through a real 2.0.0rc5 LiveNode, the adaptive-paper
           adapter (native_adapter.build_node), its Controller and durable Ledger, against
           the blueprint's own synthetic port (mover_simulation.MoverSimulatedPort:
           scripted quotes, immediate marketable fills; evidence class SYN). No network,
           credentials or paper orders. Every order goes through Nautilus's own order
           factory; the adapter decides what reaches the port.
paper      Untested boundary. The same strategy on the adapter's AlpacaPaperTransport.
           Refuses unless given this engine's dedicated env file and a paper host.

Run it with the rollout's hash-locked adapter interpreter, without writing bytecode:
  tools/adaptive-paper-r20260925/bin/python -B run_nautilus.py synthetic --out ...
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
from decimal import Decimal
import json
import os
from pathlib import Path
import sys
import time
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import h2h_common as common  # noqa: E402

ADAPTER = common.ADAPTIVE_PAPER
ET = ZoneInfo("America/New_York")
STATE = {"INITIALIZED": "submitted", "SUBMITTED": "submitted", "EMULATED": "open", "RELEASED": "submitted",
         "ACCEPTED": "open", "TRIGGERED": "open", "PENDING_UPDATE": "open", "PENDING_CANCEL": "open",
         "PARTIALLY_FILLED": "partially_filled", "FILLED": "filled", "CANCELED": "canceled",
         "EXPIRED": "expired", "DENIED": "refused", "REJECTED": "refused"}
# The adapter's own session policy keys; extended hours on so X01-X04 can carry the flag,
# overnight holds off (the default: a restart with open orders goes through recovery).
PAPER_SESSION_POLICY = {"extended_hours": True, "overnight_holds": False, "overnight_gross_multiple": "1.0"}
# Admit every scripted order except R12's deliberate 100000-share buy. The ledger admits
# buys for trial_seconds (at most 3600) after a trial starts, so paper starts one per phase.
H2H_LIMITS = dict(capital_usd="100000", max_gross_exposure_usd="100000", max_order_notional_usd="10000",
                  max_order_qty="10", max_gross_loss_usd="100", max_drawdown_usd="100", max_spread_bps="15",
                  max_held_symbols=10, max_outstanding_orders=20, max_rest_per_minute=200,
                  max_submits_per_minute=180, quote_max_age_seconds=3, trial_seconds=3600,
                  cleanup_seconds=600, min_entry_close_seconds=600)


def adapter_imports():
    if str(ADAPTER) not in sys.path:
        sys.path.insert(0, str(ADAPTER))
    import native_adapter
    import runner
    import safety
    return native_adapter, runner, safety


def make_strategy(ledger, symbol):
    from nautilus_trader.config import StrategyConfig
    from nautilus_trader.model import InstrumentId, StrategyId
    from nautilus_trader.trading import Strategy
    from native_adapter import guarded_callback

    class H2HNautilusStrategy(Strategy):
        def __new__(cls, *args, **kwargs):
            return super().__new__(cls, StrategyConfig(strategy_id=StrategyId("H2H-001"), order_id_tag="H",
                                                       log_events=False, log_commands=False, manage_stop=False))

        def __init__(self, ledger, symbol):
            self.ledger = ledger
            self.iid = InstrumentId.from_str(symbol + ".ALPACA")
            self.bid = self.ask = None
            self.started = False
            self.modify_rejected = {}
            self.events = []
            self.callback_faults, self.faulted, self.fault_sink, self.enabled = [], False, None, True

        def on_start(self):
            self.subscribe_quotes(self.iid)
            self.started = True

        def on_quote(self, quote):
            self.bid, self.ask = Decimal(str(quote.bid_price)), Decimal(str(quote.ask_price))

        def _event(self, kind, event, **fields):
            self.events.append({"kind": kind, "client_order_id": str(event.client_order_id),
                                "wall_ns": time.time_ns(), **fields})

        @guarded_callback
        def on_order_accepted(self, event):
            self._event("accepted", event)

        @guarded_callback
        def on_order_filled(self, event):
            self._event("filled", event, last_qty=str(event.last_qty), last_px=str(event.last_px))

        @guarded_callback
        def on_order_canceled(self, event):
            self._event("canceled", event)

        @guarded_callback
        def on_order_expired(self, event):
            self._event("expired", event)

        @guarded_callback
        def on_order_rejected(self, event):
            self._event("rejected", event, reason=str(event.reason))
            self._mark_not_sent(str(event.client_order_id))

        @guarded_callback
        def on_order_denied(self, event):
            self._event("denied", event, reason=str(event.reason))
            self._mark_not_sent(str(event.client_order_id))

        @guarded_callback
        def on_order_modify_rejected(self, event):
            self.modify_rejected[str(event.client_order_id)] = str(event.reason)
            self._event("modify_rejected", event, reason=str(event.reason))

        def _mark_not_sent(self, client_id):
            # As the adapter's own strategies do: a definitive local refusal leaves no live intent.
            intent = next((i for i in self.ledger.intents() if i.client_id == client_id), None)
            if intent and intent.broker_id is None and intent.filled_qty == 0 and intent.status == "reserved":
                self.ledger.mark_not_sent(client_id, "native_definitive_refusal")

    return H2HNautilusStrategy(ledger, symbol)


class NautilusOps:
    """h2h_common.StepMachine operations through Nautilus's own order factory and cache."""

    def __init__(self, strategy, port, script):
        self.s, self.port, self.script = strategy, port, script
        self.meta = {}

    def now(self):
        return dt.datetime.now(ET)

    def quote(self):
        if self.s.bid is None or self.s.ask is None or self.s.bid <= 0 or self.s.ask < self.s.bid:
            raise common.NoQuote()
        return self.s.bid, self.s.ask

    def position(self):
        return Decimal(str(self.s.portfolio.net_position(self.s.iid) or 0))

    def open_orders(self):
        return len(self.s.cache.orders_open(instrument_id=self.s.iid))

    def _px(self, value):
        from nautilus_trader.model import Price
        return Price.from_str(format(value, "f"))

    def submit(self, tag, order):
        from nautilus_trader.model import (OrderSide, OrderType, Quantity, TimeInForce, TrailingOffsetType,
                                           TriggerType)
        factory, iid = self.s.order_factory, self.s.iid
        side = OrderSide.BUY if order["side"] == "buy" else OrderSide.SELL
        qty = Quantity.from_int(order["qty"])
        tif = {"day": TimeInForce.DAY, "opg": TimeInForce.AT_THE_OPEN, "cls": TimeInForce.AT_THE_CLOSE}[order["tif"]]
        tags = ["reason=" + tag.replace(":", "-")]
        legs = []
        if order["class"] == "bracket":
            # rc5's factory returns the entry and its two linked legs as a plain list.
            orders = factory.bracket(iid, side, qty, entry_order_type=OrderType.LIMIT,
                                     entry_price=self._px(order["limit"]), time_in_force=tif,
                                     tp_price=self._px(order["take_profit"]), tp_time_in_force=tif,
                                     tp_post_only=False, sl_trigger_price=self._px(order["stop_loss"]),
                                     sl_time_in_force=tif, entry_tags=tags)
            entry, legs = orders[0], list(orders[1:])
            try:
                self.s.submit_order_list(orders)
            except (TypeError, ValueError, NotImplementedError) as error:
                raise common.Unsupported("bracket_submit_order_list:" + type(error).__name__) from None
        elif order["class"] in ("oto", "oco"):
            raise common.Unsupported("standalone_" + order["class"] + ":rc5_python_order_factory_has_bracket_only")
        else:
            if order["type"] == "limit":
                entry = factory.limit(iid, side, qty, self._px(order["limit"]), time_in_force=tif, tags=tags)
            elif order["type"] == "market":
                entry = factory.market(iid, side, qty, time_in_force=tif, tags=tags)
            elif order["type"] == "stop":
                entry = factory.stop_market(iid, side, qty, self._px(order["stop"]), time_in_force=tif, tags=tags)
            elif order["type"] == "stop_limit":
                entry = factory.stop_limit(iid, side, qty, self._px(order["limit"]), self._px(order["stop"]),
                                           time_in_force=tif, tags=tags)
            else:   # trailing_stop: 10 percent = 1000 basis points
                entry = factory.trailing_stop_market(iid, side, qty, order["trail_percent"] * 100,
                                                     trailing_offset_type=TrailingOffsetType.BASIS_POINTS,
                                                     trigger_type=TriggerType.DEFAULT, time_in_force=tif, tags=tags)
            self.s.submit_order(entry)
        handle = entry.client_order_id
        self.meta[str(handle)] = {"order": order, "legs": [leg.client_order_id for leg in legs]}
        return handle

    def replace(self, handle, limit):
        self.s.modify_order(handle, price=self._px(limit))

    def cancel(self, handle):
        self.s.cancel_order(handle)

    def is_open(self, handle):
        order = self.s.cache.order(handle)
        return bool(order is not None and order.is_open)

    def flatten(self, session):
        # The adapter's own practice: cancel, then close with a marketable limit (it takes limit/DAY only).
        for order in self.s.cache.orders_open(instrument_id=self.s.iid):
            self.s.cancel_order(order.client_order_id)
        quantity = self.position()
        if quantity:
            from nautilus_trader.model import OrderSide, Quantity, TimeInForce
            bid, ask = self.quote()
            rule = "marketable_sell" if quantity > 0 else "marketable_buy"
            limit = common.price(rule, bid, ask, self.script)
            order = self.s.order_factory.limit(self.s.iid, OrderSide.SELL if quantity > 0 else OrderSide.BUY,
                                               Quantity.from_int(int(abs(quantity))), self._px(limit),
                                               time_in_force=TimeInForce.DAY, tags=["reason=h2h-flatten"])
            self.s.submit_order(order)

    cleanup = flatten

    def observe(self, handle):
        order = self.s.cache.order(handle)
        if order is None:
            return {"state": "unknown"}
        status = getattr(order.status, "name", str(order.status)).split(".")[-1]
        observed = {"state": STATE.get(status, "unknown"), "filled_qty": Decimal(str(order.filled_qty)),
                    "accepted_price": Decimal(str(order.price)) if getattr(order, "price", None) is not None else None}
        if observed["state"] == "open" and observed["filled_qty"]:
            observed["state"] = "partially_filled"
        if str(handle) in self.s.modify_rejected:
            observed["modify_rejected"] = self.s.modify_rejected[str(handle)]
        denial = next((e.get("reason") for e in reversed(self.s.events)
                       if e["client_order_id"] == str(handle) and e["kind"] in ("denied", "rejected")), None)
        if denial:
            observed["detail"] = denial
        meta = self.meta.get(str(handle), {})
        if meta.get("legs"):
            observed["legs_open"] = sum(1 for leg in meta["legs"] if self.is_open(leg))
            observed["legs_expected"] = len(meta["legs"])
        requested_ext = meta.get("order", {}).get("extended_hours")
        sent = next((p for p in reversed(self.port.payloads) if p.get("client_order_id") == str(handle)), None)
        if requested_ext and sent is not None and not sent.get("extended_hours") and observed["state"] != "refused":
            observed["detail"] = "extended_hours_flag_set_by_session_policy"
        return observed

    def fault_point(self, kind, tag):
        """Paper only: the step machine journals the fault point; the orchestrator acts
        on it (kill/stop end this process; the step waits until then or times out)."""


def synthetic_account(output, script):
    """A fresh synthetic account per node: ledger, controller and the blueprint's own port."""
    def build(index):
        _, runner, safety = adapter_imports()
        from mover_simulation import MoverSimulatedPort, piecewise_path
        symbol = script["symbol"]
        ledger = safety.Ledger(output / f"ledger-{index}.sqlite3", safety.RiskLimits(**H2H_LIMITS))
        now = time.time()
        ledger.begin_next_trial(now, f"h2h-synthetic-{index}")
        controller = runner.Controller(ledger, now + 36000, market_open=True)
        path = piecewise_path({symbol: [(0, Decimal("500.00"), Decimal("0.02")),
                                        (86400, Decimal("500.00"), Decimal("0.02"))]})
        port = MoverSimulatedPort(controller, [symbol], path=path, extended_hours_allowed=True)
        controller.port = port
        return ledger, controller, port, "ALPACA-PAPER-H2H-SYN"
    return build


class Node:
    """One LiveNode + our adapter + Controller + durable Ledger on the account ``account`` builds."""

    def __init__(self, index, output, script, account):
        self.index, self.output, self.script, self.account = index, output, script, account

    async def start(self):
        native_adapter, _, _ = adapter_imports()
        symbol = self.script["symbol"]
        self.ledger, controller, self.port, account_id = self.account(self.index)
        start = self.port.start

        async def start_with_quotes(on_quote, on_order):
            async def quote_sink(quote):
                controller.quote(quote)
                result = on_quote(quote)
                if hasattr(result, "__await__"):
                    await result
            return await start(quote_sink, on_order)

        self.port.start = start_with_quotes
        self.strategy = make_strategy(self.ledger, symbol)
        self.session = native_adapter.build_node(
            self.port, [{"symbol": symbol, "price_precision": 2, "price_increment": "0.01", "lot_size": "1"}],
            [self.strategy], account_id=account_id, trader_id="H2H-001", session_policy=PAPER_SESSION_POLICY,
            max_order_submit_rate="180/00:01:00", log_directory=self.output / f"native-log-{self.index}")
        self.strategy.fault_sink = self.session.fail
        self.ops = NautilusOps(self.strategy, self.port, self.script)
        self.task = asyncio.create_task(self.session.run_async())
        deadline = time.monotonic() + 60
        while not (self.strategy.started and self.strategy.bid is not None):
            if self.task.done() or time.monotonic() > deadline:
                raise RuntimeError("node_not_ready")
            await asyncio.sleep(.05)
        return self

    def stop_reason(self):
        error = self.task.exception() if self.task.done() and not self.task.cancelled() else None
        return "node_stopped:" + ";".join(list(self.session.errors) + ([type(error).__name__] if error else []))

    async def stop(self):
        self.final = {"final_quantity": str(self.ops.position()), "open_orders": self.ops.open_orders(),
                      "adapter_errors": list(self.session.errors), "port_payloads": len(self.port.payloads),
                      "native_events": len(self.strategy.events),
                      "native_assertions": self.session.native_assertions()}
        self.session.stop()
        try:
            await asyncio.wait_for(self.task, 20)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
        await self.port.stop()
        self.final["ledger_accounting"] = self.ledger.accounting()
        self.ledger.close()
        return self.final


async def run_script(output, script, account, *, mode, phases, scheduled, trial=None):
    """Run ``phases`` through a node on ``account``. Offline, a node that stops itself
    (shutdown_on_error) is recorded against the case that stopped it and the script
    continues on a fresh flat synthetic account; on paper a stopped node ends the run
    (the adapter's own recovery owns an account with live state), and each phase starts
    its own ledger trial, which the ledger refuses unless the account is flat and idle."""
    journal = common.Journal(output / "journal.jsonl", engine="nautilus", mode=mode,
                             script_sha256=common.file_sha256(common.SCRIPT_PATH))
    node = await Node(0, output, script, account).start()
    machine = common.StepMachine(script, node.ops, journal, offline=mode != "paper")
    pending = sorted(phases, key=lambda p: script["phases"][p]["at_et"]) if scheduled else list(phases)
    stopped, finals, partial = [], [], False
    try:
        while pending or not machine.idle():
            if pending and (not scheduled or dt.datetime.now(ET).strftime("%H:%M") >= script["phases"][pending[0]]["at_et"]):
                if machine.idle():
                    phase = pending.pop(0)
                    if mode == "paper":
                        _, _, safety = adapter_imports()
                        try:
                            node.ledger.begin_next_trial(time.time(), f"{trial}-{phase}".replace("_", "-")[:24])
                        except safety.SafetyError as refusal:
                            for case_id in script["phases"][phase]["cases"]:
                                machine.result(case_id, common.FAILED, "trial_start:" + str(refusal))
                            continue
                    machine.enqueue_phase(phase)
            if node.task.done():
                reason = node.stop_reason()
                work = machine.active
                stopped.append({"case": work.case if work else None, "reason": reason})
                journal.event("node_stopped", case=work.case if work else None, reason=reason)
                if work is not None:
                    machine.aborted.add(work.instance)
                    machine.result(work.case, common.FAILED, reason)
                    machine.active = None
                finals.append(await node.stop())
                partial |= _partial_fill_seen(node)
                if mode == "paper":
                    break
                node = await Node(len(finals), output, script, account).start()
                machine.ops = node.ops
                continue
            machine.advance()
            await asyncio.sleep(.05)
    finally:
        if not finals or finals[-1] is not getattr(node, "final", None):
            finals.append(await node.stop())
            partial |= _partial_fill_seen(node)
    results = common.finalize_offline_results(machine.results, script, partial_fills_seen=partial) \
        if mode != "paper" else dict(machine.results)
    for result in results.values():
        result.setdefault("glue_required", True)   # every case runs through our adapter
    last = finals[-1]
    journal.event("run_end", results=results, final_quantity=last["final_quantity"], open_orders=last["open_orders"],
                  node_stops=stopped, adapter_errors=last["adapter_errors"], native_assertions=last["native_assertions"])
    journal.close()
    return results, {"final_quantity": last["final_quantity"], "open_orders": last["open_orders"],
                     "adapter_errors": last["adapter_errors"], "node_stops": stopped, "nodes": finals}


async def run_synthetic(output):
    script = common.load_script()
    phases = [phase for phases in common.BACKTEST_PLAN.values() for phase in phases]
    return await run_script(output, script, synthetic_account(output, script), mode="synthetic",
                            phases=phases, scheduled=False)


def _partial_fill_seen(node):
    return any(event["kind"] == "filled" and Decimal(event["last_qty"]) < Decimal(str(
        node.ops.meta.get(event["client_order_id"], {}).get("order", {}).get("qty", 0) or 0))
        for event in node.strategy.events)


def command_synthetic(args):
    for name in os.environ:
        if name.startswith(("APCA_", "ALPACA_")):
            raise common.H2HRefusal("h2h:credentials_present_in_offline_run")
    output = args.out.resolve()
    if output.exists():
        raise ValueError("use a fresh output directory")
    os.umask(0o077)
    output.mkdir(parents=True, mode=0o700)
    results, extra = asyncio.run(run_synthetic(output))
    script = common.load_script()
    summary = common.summarize(results, script=script)
    receipt = {"engine": "nautilus", "mode": "synthetic",
               "evidence_class": "SYN (real 2.0.0rc5 LiveNode, our adapter, synthetic port; no broker)",
               "script_sha256": common.file_sha256(common.SCRIPT_PATH), "runner_sha256": common.file_sha256(__file__),
               "adapter_sha256": {name: common.file_sha256(ADAPTER / name) for name in
                                  ("native_adapter.py", "runner.py", "safety.py", "transport.py", "mover_simulation.py")},
               "journal_sha256": common.file_sha256(output / "journal.jsonl"),
               **extra, "results": results, "summary": summary}
    (output / "results.json").write_text(json.dumps(receipt, indent=2, default=str) + "\n")
    print(json.dumps({"summary": summary, **{k: extra[k] for k in ("final_quantity", "open_orders", "adapter_errors")}},
                     indent=2, default=str))
    return 0


def paper_account(args, output, script):
    """The adapter's own paper building blocks, as mover_runner.command_paper composes
    them: its credential loader, the read-only SDK preflight, the per-account lock, a
    durable Ledger under the state root, and controller.bind(AlpacaPaperTransport)."""
    _, runner, safety = adapter_imports()
    from transport import AlpacaPaperTransport, preflight
    key, secret = runner.credentials(args.env_file, paper_only=True)
    symbols = [script["symbol"]]
    observation = preflight(key, secret, symbols, feed=args.feed, before_request=lambda *a, **k: None)
    fingerprint = observation["account_identity_sha256"]
    lock = safety.account_lock_fingerprint(fingerprint)
    lock.__enter__()
    state_dir = args.state_root / fingerprint / "h2h"
    state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

    def build(index):
        if index:
            raise RuntimeError("paper_node_restart_requires_adapter_recovery")
        from sessions import extended_session_close
        ledger = safety.Ledger(state_dir / "ledger.sqlite3", safety.RiskLimits(**H2H_LIMITS))
        # Trials start per phase (run_script). As mover_runner._controller_session with
        # extended hours on, admissions end at the close of today's extended session.
        close = extended_session_close(dt.datetime.now(dt.timezone.utc)).astimezone(dt.timezone.utc).timestamp()
        controller = runner.Controller(ledger, close, market_open=True)
        port = controller.bind(AlpacaPaperTransport(
            key, secret, symbols, before_request=controller.before_request, before_submit=controller.before_submit,
            sink_observation=controller.observe, sink_status=controller.trading_status, feed=args.feed,
            extended_hours_allowed=True))
        controller.port = port
        return ledger, controller, port, "ALPACA-PAPER-" + fingerprint[:16]
    return build, lock, fingerprint


def command_paper(args):
    common.load_paper_env("nautilus", args.env_file)   # name, host and file-guard refusals first
    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    script = common.load_script()
    account, lock, fingerprint = paper_account(args, output, script)
    try:
        results, extra = asyncio.run(run_script(output, script, account, mode="paper",
                                                phases=args.phases.split(","), scheduled=True, trial=args.trial))
    finally:
        lock.__exit__(None, None, None)
    (output / "results.json").write_text(json.dumps(
        {"engine": "nautilus", "mode": "paper", "account_fingerprint": common.account_fingerprint(fingerprint),
         "script_sha256": common.file_sha256(common.SCRIPT_PATH), **extra, "results": results},
        indent=2, default=str) + "\n")
    return 0


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    synthetic = commands.add_parser("synthetic")
    synthetic.add_argument("--out", type=Path, required=True)
    paper = commands.add_parser("paper")
    paper.add_argument("--env-file", type=Path, default=None,
                       help="this engine's dedicated file: " + common.env_file_name("nautilus"))
    paper.add_argument("--out", type=Path, required=True)
    paper.add_argument("--state-root", type=Path, required=True)
    paper.add_argument("--trial", required=True)
    paper.add_argument("--feed", default="iex")
    paper.add_argument("--phases", default="pre_open,regular,faults,close,reconcile")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return {"synthetic": command_synthetic, "paper": command_paper}[args.command](args)
    except common.H2HRefusal as refusal:
        print(json.dumps({"refused": str(refusal)}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
