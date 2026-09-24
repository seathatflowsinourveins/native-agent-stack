"""Mover trial runner (protocol mover-early-entry-v1-20260924, paper_e2e section).

Commands:
  check      validate a mover config and a scanner file and print the entry plan (no broker I/O)
  paper      one bounded Alpaca paper trial through the native NautilusTrader LiveNode
  recover    flatten and reconcile an interrupted mover trial (sell-only, engine recovery path)
  synthetic  the same native engine path against a local synthetic port (evidence class SYN)

The universe comes from the scanner's JSON file, never from config. A paper trial
reuses the adaptive-paper engine unchanged: runner.credentials/validate_preflight/
reconcile/Controller, transport.preflight/AlpacaPaperTransport, safety.Ledger and
RiskLimits, native_adapter.build_node and recovery.recover. Its durable state lives
in ``<state-root>/<account fingerprint>/mover/`` under the same account lock as the
adaptive lane. Receipts carry no account id, balance or credential.
"""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from dataclasses import asdict, replace
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
import signal
import sys
import tempfile
import time

_HERE = str(Path(__file__).resolve().parent)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
import safety  # noqa: E402
from mover import (EXIT_HEADROOM_FACTOR, PROTOCOL_ID, X1_FLATTEN_AT_ET, X2_HOLD_SECONDS,  # noqa: E402
                   X3_TRAIL_FRACTION, X4_STOP_FRACTION, X4_TARGET_FRACTION, MoverBook, MoverRefusal, Timing,
                   build_plan, engine_config, load_mover_config, load_scan, plan_session, session_state_after, text)
from runner import (Controller, LiveEventLog, _apply_forced_recovery_outcome, _run_native_status,  # noqa: E402
                    credentials, public_preflight, reconcile, save, trial_phase_and_exit_code, validate_preflight)
from safety import Ledger, SafetyError, account_lock_fingerprint  # noqa: E402
from sessions import SessionKind, extended_session_close, session_at, validate_session_policy  # noqa: E402

SOURCE = Path(__file__).resolve().parent
LAST_OUTPUT = None
LAST_EVIDENCE_CLASS = "PAPER"
RECONCILE_EVERY_SECONDS = 30
TRIAL_ID = re.compile(r"[a-z0-9-]{1,24}")

LIMITATIONS = {
    "PAPER": [
        "Alpaca paper fills are simulated by the broker from quotes; they are not exchange executions and do not "
        "establish live slippage, queue position or partial-fill behaviour.",
        "Exits are marketable limit sells re-priced every exit timeout; stops never rest at the broker, and a gap or "
        "halt can fill below the protocol's stop level or leave a sell unfilled until the flatten or recovery.",
        "One paper session is not a strategy evaluation; the historical study, not this receipt, decides the rule "
        "and exit.",
    ],
    "SYN": [
        "Synthetic port: scripted quotes and immediate marketable fills; no broker, network, fees, halts, auctions, "
        "queue priority or latency. Not paper or live evidence.",
        "Timing is compressed; the protocol's real X2 hold (3600 s) and trial end are not exercised.",
        "The synthetic run uses the regular-session order flag; the extended-hours flag is covered by unit tests.",
    ],
}


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def _iso(epoch):
    return None if epoch is None else datetime.fromtimestamp(epoch, timezone.utc).isoformat()


def instrument_metadata(plan, benchmarks):
    """Native instruments at each symbol's plan precision (mover.symbol_price_decimals:
    4 for every mover symbol, so a sub-penny fill below 1 USD is representable; the
    order prices stay on the 0.01 tick at or above 1 USD). Benchmarks are subscribed for
    stream liveness and preflight readiness only; the mover never trades them unless the
    scan lists them."""
    rows, seen = [], set()
    for item in plan.symbols:
        symbol = item.scan.symbol
        precision = item.price_decimals
        rows.append({"symbol": symbol, "price_precision": precision,
                     "price_increment": "0.0001" if precision == 4 else "0.01", "lot_size": "1"})
        seen.add(symbol)
    for symbol in benchmarks:
        if symbol not in seen:
            rows.append({"symbol": symbol, "price_precision": 2, "price_increment": "0.01", "lot_size": "1"})
            seen.add(symbol)
    return rows


FOREIGN_TERMINAL_STATUSES = frozenset({"filled", "canceled", "expired", "rejected", "replaced"})


class MoverController(Controller):
    """runner.Controller, except that an order this ledger does not own and that is
    already terminal is ignored (counted) instead of freezing the ledger, and that a
    buy above the mover entry cap is refused before the ledger reserves it.

    The transport's snapshot pages and the trade stream carry every order on the
    account since the lane's first trial, including another lane's (the adaptive
    lane's) finished orders. A foreign order that is still open still freezes the
    ledger exactly as before, and a foreign fill during the trial still surfaces as a
    cash or position mismatch at the next reconciliation (mover_reconcile).

    The ledger's per-order cap is sized for exit sells (at least
    mover.EXIT_HEADROOM_FACTOR times the entry cap), so it no longer bounds an entry by
    itself; ``max_entry_notional_usd`` (required) keeps that bound outside the book."""

    def __init__(self, *args, max_entry_notional_usd, **kwargs):
        super().__init__(*args, **kwargs)
        cap = Decimal(str(max_entry_notional_usd))
        if not cap.is_finite() or cap <= 0:
            raise SafetyError("invalid_mover_entry_cap")
        self.max_entry_notional_usd = cap
        self.foreign_terminal_orders = 0

    def before_submit(self, order):
        """Refuse (before any ledger reservation or broker request) a buy whose
        quantity x limit exceeds the mover entry cap; anything else goes to
        runner.Controller.before_submit unchanged."""
        if order.get("side") != "sell":
            try:
                notional = Decimal(str(order["qty"])) * Decimal(str(order["limit_price"]))
            except (KeyError, ArithmeticError, ValueError):
                notional = None
            if notional is None or not notional.is_finite() or notional > self.max_entry_notional_usd:
                from native_adapter import NativeOrderRejected
                raise NativeOrderRejected("mover_entry_notional_cap_exceeded")
        return super().before_submit(order)

    def observe(self, order):
        known = {i.client_id for i in self.ledger.intents()}
        if order.get("client_order_id") not in known and order.get("status") in FOREIGN_TERMINAL_STATUSES:
            self.foreign_terminal_orders += 1
            return
        return super().observe(order)


def mover_reconcile(ledger, snapshot, baseline_cash):
    """runner.reconcile over the ledger's own orders plus every foreign order that is
    not terminal (which still fails as external_order_detected). Positions and cash are
    compared unchanged; the mover's baseline is the trial's own starting cash."""
    owned = {i.client_id for i in ledger.intents()}
    orders = [o for o in snapshot.get("orders", [])
              if o.get("client_order_id") in owned or o.get("status") not in FOREIGN_TERMINAL_STATUSES]
    return reconcile(ledger, {**snapshot, "orders": orders}, baseline_cash)


def scope_recovery_adoption(port, ledger):
    """Wrap a fresh recovery port so recovery.recover adopts only intents it can own.

    recovery.recover adopts every intent the ledger has not retired, and a transport
    refuses to adopt an intent for a symbol it does not subscribe (at most 30 symbols).
    The mover ledger spans every session of the lane and each scan trades other symbols,
    so adopting everything fails from the second session on. Every unresolved intent is
    still adopted (a cancel needs it; the ports built here subscribe every held and
    unresolved symbol, and one outside them still fails closed in the transport), as is
    every terminal intent whose symbol the port subscribes. A terminal intent that is
    skipped stays covered: the snapshot pages every order since the lane's first trial
    (history_start) and reconciliation raises submitted_intent_absent for any attempted
    ledger intent the snapshot lacks. The counts are kept on ``port.adoption_scope``."""
    adopt = port.adopt_intents

    def scoped(intents):
        unresolved = {intent.client_id for intent in ledger.unresolved()}
        subscribed = set(port.symbols)
        intents = list(intents)
        kept = [i for i in intents if i["client_order_id"] in unresolved or i["symbol"] in subscribed]
        port.adoption_scope = {"adopted": len(kept), "skipped_terminal_unsubscribed": len(intents) - len(kept),
                               "subscribed_symbols": len(subscribed)}
        return adopt(kept)

    port.adopt_intents = scoped
    return port


def unsellable_positions(controller):
    """Residual positions that no engine order can sell: one share at the last observed
    bid is worth more than the ledger's per-order cap, so the ledger's share cap for a
    sell (RiskLimits.effective_max_order_qty) is zero and every whole-share sell is
    refused. recovery.recover reports these as recovery_quantity_not_representable;
    this names the symbol, quantity, bid and cap so the needs_attention record says why."""
    cap = controller.ledger.limits.max_order_notional_usd
    rows = []
    for symbol, position in sorted(controller.ledger.positions().items()):
        quote = controller.quotes.get(symbol)
        bid = None if quote is None else Decimal(str(quote.bid))
        if bid is not None and bid > cap:
            rows.append({"symbol": symbol, "qty": text(position.qty), "bid": text(bid),
                         "ledger_max_order_notional_usd": text(cap), "reason": "share_exceeds_ledger_order_cap"})
    return rows


async def recover_mover(controller, metadata, config):
    """recovery.recover on the controller's fresh, unstarted port with the mover's
    adoption scope and reconciliation (mover_reconcile). Sell-only, as the engine's.
    ``unsellable_positions`` lists any residual one share of which exceeds the ledger's
    per-order cap."""
    from recovery import recover
    port = scope_recovery_adoption(controller.port, controller.ledger)
    result = await recover(controller, metadata, config, reconcile_fn=mover_reconcile)
    result["adoption_scope"] = getattr(port, "adoption_scope", None)
    result["unsellable_positions"] = unsellable_positions(controller)
    return result


def make_book(plan, controller):
    ledger = controller.ledger
    return MoverBook(plan, positions=ledger.positions, quote=controller.quotes.get, limits=ledger.limits,
                     trial_id=plan.trial_id, existing_client_ids=[i.client_id for i in ledger.intents()],
                     event_sink=controller.events.append)


async def run_mover(controller, plan, config, baseline_cash, *, account_fingerprint="simulation",
                    log_directory=None, stop_file=None):
    """Run one mover trial through the native LiveNode and return its outcome.

    Mirrors runner.run_native's loop: a force reason (STOP file, controller stop,
    adapter error, ledger halt, transport gap, session close, mark-to-market failure,
    or the plan's hard flatten) stops entries and flattens; quotes are marked every
    tick; a periodic broker snapshot is reconciled when nothing is in flight; the run
    ends once every leg is resolved and the ledger is flat, when the book hands off to
    recovery (MoverBook.handoff_reason: after a force, every held leg's exits blocked or
    no exit fill for mover.HANDOFF_EXIT_TIMEOUTS exit timeouts), or at the ledger's sell
    window end, then takes a final reconciliation when no order is unresolved. The
    caller runs recovery for any residual.

    An exception once the node task exists (for example a periodic reconciliation that
    finds an order this ledger does not own, or the node itself failing) stops the node
    as any other end does and does not discard the trial: the outcome still carries the
    book's legs and orders, the events and the native counts, with status
    needs_attention, no end reconciliation and the bounded error_type/error_reason (and
    a ``mover_loop_error`` event)."""
    from native_adapter import build_node
    from mover_strategy import MoverStrategy
    ledger = controller.ledger
    book = make_book(plan, controller)
    strategy = MoverStrategy(book, ledger)
    port = controller.port
    start = port.start

    async def start_with_quotes(on_quote, on_order):
        async def quote_sink(quote):
            controller.quote(quote)
            result = on_quote(quote)
            if hasattr(result, "__await__"):
                await result
        return await start(quote_sink, on_order)

    port.start = start_with_quotes
    session_policy = validate_session_policy(config)
    session = build_node(port, instrument_metadata(plan, config["benchmarks"]), [strategy],
                         account_id="ALPACA-PAPER-" + account_fingerprint[:16], trader_id="MOVER-001",
                         max_order_submit_rate="180/00:01:00", session_policy=session_policy,
                         log_directory=log_directory)
    # A guarded order callback that raises stops the session (adapter_error): no
    # further submit, the node stops and the caller recovers the residual.
    strategy.fault_sink = session.fail
    # E4: the startup halt seed (when command_paper configured one) is read while the
    # node connects, for the symbols whose statuses the port streams; entries wait for it.
    controller.start_halt_seed(list(getattr(port, "symbols", None) or plan.symbol_names()))
    task = asyncio.create_task(session.run_async())
    started = time.monotonic()
    last_reconciliation = started
    reconciliation = None
    force_reason = None
    handoff = None
    failure = None
    stop_path = Path(stop_file) if stop_file is not None else None
    try:
        try:
            while True:
                now = time.time()
                if task.done() or now >= plan.timing.sell_window_end:
                    break
                state = ledger.accounting()
                health = getattr(port, "health", {})
                serious_gap = any("stale" not in str(reason) for reason in health.get("reasons", []))
                reason = None
                if (stop_path or safety.DEFAULT_STOP).exists():
                    reason = "kill_switch"
                elif controller.stop:
                    reason = "controller_stop"
                elif session.errors:
                    reason = "adapter_error"
                elif state.halted_reason:
                    reason = "risk_halt"
                elif strategy.started and serious_gap:
                    controller.stop = True
                    reason = "transport_gap"
                elif controller.close - now <= config["cleanup_seconds"]:
                    # mover.load_mover_config refuses an X1 config for which this latches at or before 15:58.
                    reason = "session_close"
                if reason is not None and force_reason is None:
                    force_reason = reason
                strategy.enabled = (strategy.started and port.ready and force_reason is None
                                    and now >= controller.defer_until and not controller.halt_seed_pending())
                fresh_quotes = [q for q in controller.quotes.values()
                                if -.25 <= now - q.timestamp <= config["quote_max_age_seconds"]]
                try:
                    ledger.mark_to_market(fresh_quotes, now)
                except SafetyError as exc:
                    strategy.enabled = False
                    if str(exc) != "held_position_mark_stale":
                        controller.stop = True
                        force_reason = force_reason or "mark_to_market_failure"
                if (strategy.started and force_reason is None
                        and time.monotonic() - last_reconciliation >= RECONCILE_EVERY_SECONDS
                        and not ledger.unresolved() and not strategy.pending):
                    strategy.enabled = False
                    strategy.suspended = True  # no quote-driven order while the snapshot is in flight
                    try:
                        snapshot = await port.snapshot()
                        mover_reconcile(ledger, snapshot, baseline_cash)
                    finally:
                        strategy.suspended = False
                    health = getattr(port, "health", {})
                    if any("stale" not in str(item) for item in health.get("reasons", [])):
                        controller.stop = True
                    elif health.get("fresh_quotes") and hasattr(port, "mark_reconciled"):
                        port.mark_reconciled()
                    last_reconciliation = time.monotonic()
                if strategy.started:
                    strategy.tick(now, force_reason=force_reason)
                    if book.complete() and not ledger.unresolved() and not ledger.positions():
                        break
                    reason = book.handoff_reason(now)
                    if reason is not None:
                        handoff = {"reason": reason, "at": _iso(now), "force_reason": book.force_reason,
                                   "seconds_after_force": round(now - book.force_at, 3)}
                        controller.events.append({"type": "mover_handoff_to_recovery", "reason": reason, "at": now})
                        break
                await asyncio.sleep(.1)
            strategy.enabled = False
            strategy.suspended = True
            controller.stop = True
            if not ledger.unresolved() and not strategy.pending:
                snapshot = await port.snapshot()
                reconciliation = mover_reconcile(ledger, snapshot, baseline_cash)
        finally:
            strategy.enabled = False
            strategy.suspended = True
            controller.stop = True
            await controller.stop_halt_seed()
            session.stop()
            try:
                await asyncio.wait_for(task, 20)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
            await port.stop()
    except Exception as exc:
        failure = exc
        controller.events.append({"type": "mover_loop_error", "error_type": type(exc).__name__,
                                  "reason": _bounded_reason(exc), "at": time.time()})
    port_health = getattr(port, "health", {})
    outcome = {"engine": "NautilusTrader LiveNode 2.0.0rc5", "native_quotes": strategy.received_quotes,
               "native_fill_events": strategy.native_fills, "native_rejections": strategy.native_rejections,
               "orders_submitted": strategy.submitted, "reconciliation": reconciliation,
               "startup_reconciliation": session.reconciliation, "adapter_errors": list(session.errors),
               "execution_stats": dict(session.execution_stats),
               "average_invariant_mismatches": list(session.average_invariant_mismatches),
               "callback_faults": list(strategy.callback_faults),
               "halts": controller.halt_summary() if hasattr(controller, "halt_summary") else None,
               "flat": not ledger.positions() and not ledger.unresolved(),
               "force_reason": book.force_reason, "force_at": _iso(book.force_at),
               "handoff_to_recovery": handoff,
               "legs": book.leg_receipts(), "events": list(controller.events),
               "foreign_terminal_orders_ignored": getattr(controller, "foreign_terminal_orders", 0),
               "requests": dict(Counter(r["kind"] for r in controller.requests)),
               "dropped_quotes": {"by_reason": {str(k): int(v) for k, v in port_health.get("dropped_quotes", {}).items()},
                                  "by_symbol": {str(k): int(v) for k, v in
                                                port_health.get("dropped_quotes_by_symbol", {}).items()}},
               "session_policy": {"extended_hours": session_policy["extended_hours"],
                                  "overnight_holds": session_policy["overnight_holds"]},
               "elapsed_seconds": time.monotonic() - started}
    if failure is None:
        outcome["status"] = _run_native_status(reconciliation, session.errors, strategy.native_fills, outcome,
                                               session_policy, time.time())
    else:
        outcome.update(status="needs_attention", error_type=type(failure).__name__,
                       error_reason=_bounded_reason(failure))
    return outcome


# ---------------------------------------------------------------------------
# Receipt
# ---------------------------------------------------------------------------

def pnl_by_symbol(intents, prefixes):
    """Per-symbol fills and realized P&L of one trial's own orders (entry/exit and any
    recovery exits), from the durable ledger. Realized P&L is only stated for a symbol
    whose bought and sold quantities match (each mover trial starts flat)."""
    rows = {}
    for intent in intents:
        if not intent.client_id.startswith(prefixes) or not intent.filled_qty or intent.average_price is None:
            continue
        row = rows.setdefault(intent.symbol, {"buy_qty": Decimal(0), "buy_notional": Decimal(0),
                                              "sell_qty": Decimal(0), "sell_notional": Decimal(0)})
        side = "buy" if intent.side == "buy" else "sell"
        row[side + "_qty"] += intent.filled_qty
        row[side + "_notional"] += intent.filled_qty * intent.average_price
    result = {}
    for symbol, row in rows.items():
        realized = (row["sell_notional"] - row["buy_notional"]) if row["buy_qty"] == row["sell_qty"] else None
        result[symbol] = {"bought_qty": text(row["buy_qty"]), "buy_notional_usd": text(row["buy_notional"]),
                          "sold_qty": text(row["sell_qty"]), "sell_notional_usd": text(row["sell_notional"]),
                          "realized_pnl_usd": None if realized is None else text(realized.quantize(Decimal("0.0001"))),
                          "flat": row["buy_qty"] == row["sell_qty"]}
    return result


def plan_receipt(plan):
    timing = plan.timing
    session = plan.session
    return {
        "timing": {"trial_start": _iso(timing.trial_start), "entry_deadline": _iso(timing.entry_deadline),
                   "entry_timeout_seconds": timing.entry_timeout_seconds,
                   "exit_order_timeout_seconds": timing.exit_timeout_seconds,
                   "hard_flatten_at": _iso(timing.hard_flatten_at), "sell_window_end": _iso(timing.sell_window_end),
                   "x1_flatten_at": _iso(timing.x1_at), "x2_hold_seconds": timing.x2_hold_seconds},
        "session": {"number": session.number, "rung": text(session.rung), "equity_peak_usd": text(session.equity_peak_usd),
                    "drawdown_fraction": text(session.drawdown_fraction.quantize(Decimal("0.000001"))),
                    "drawdown_factor": text(session.drawdown_factor), "paused": session.paused,
                    "pause_sessions_remaining_after": session.pause_sessions_remaining_after,
                    "reason": session.reason},
        "sizing": {"regime_factor": text(plan.regime_factor), "regime_source": plan.regime_source,
                   "leverage_L": text(plan.leverage), "engine_leverage_multiple": text(plan.engine_leverage_multiple),
                   "sizing_equity_usd": text(plan.sizing_equity_usd),
                   "sizing_equity_source": "config capital_usd plus the mover ledger's realized P&L",
                   "gross_budget_usd": text(plan.gross_budget_usd),
                   "appreciation_allowance": text(plan.appreciation_allowance),
                   "gross_guard_usd": text(plan.gross_guard_usd), "entry_limit_cap_bps": text(plan.entry_cap_bps),
                   "exit_limit_cap_bps": text(plan.exit_cap_bps),
                   "max_entry_notional_usd": text(plan.max_entry_notional_usd),
                   "ledger_max_order_notional_usd": text(plan.ledger_max_order_notional_usd),
                   "exit_headroom_factor": text(EXIT_HEADROOM_FACTOR)},
        "exit_parameters": {"rule": plan.exit_rule, "x1_flatten_at_et": X1_FLATTEN_AT_ET.strftime("%H:%M"),
                            "x2_hold_seconds": X2_HOLD_SECONDS, "x3_trail_fraction": text(X3_TRAIL_FRACTION),
                            "x4_stop_fraction": text(X4_STOP_FRACTION), "x4_target_fraction": text(X4_TARGET_FRACTION)},
    }


def build_receipt(*, plan, outcome, config_sha256, scan, ledger, ledger_before, prefixes, preflight=None,
                  extra=None):
    """The trial receipt. Per symbol: scan fields, intended notional and caps, orders
    (client ids, hashed broker refs, submit/accept/fill times and prices), exit reason
    and realized P&L; totals; start/end reconciliation. No account id or balance."""
    after = ledger.accounting()
    intents = {intent.client_id: intent for intent in ledger.intents()}
    pnl = pnl_by_symbol(intents.values(), prefixes)
    recovery_prefix = f"rec-{plan.trial_id}-"
    legs = [dict(leg) for leg in outcome.get("legs", [])]
    for leg in legs:
        # The ledger is the durable source of order state; recovery runs outside the book.
        for order in ([leg["entry"]] if leg.get("entry") else []) + list(leg.get("exits", [])):
            intent = intents.get(order["client_order_id"])
            order["ledger_status"] = None if intent is None else intent.status
            order["ledger_filled_qty"] = None if intent is None else text(intent.filled_qty)
        leg["recovery_exits"] = [
            {"client_order_id": i.client_id, "qty": text(i.qty), "limit_price": text(i.limit_price),
             "ledger_status": i.status, "filled_qty": text(i.filled_qty), "average_price": text(i.average_price)}
            for i in intents.values() if i.symbol == leg["symbol"] and i.client_id.startswith(recovery_prefix)]
        leg["fills_and_pnl"] = pnl.get(leg["symbol"])
        leg["realized_pnl_usd"] = (pnl.get(leg["symbol"]) or {}).get("realized_pnl_usd", "0")
    per_symbol = [Decimal(leg["realized_pnl_usd"]) for leg in legs if leg["realized_pnl_usd"] is not None]
    realized_delta = after.realized_pnl_usd - ledger_before.realized_pnl_usd
    all_flat = all(row["flat"] for row in pnl.values())
    totals = {"symbols": len(legs),
              "entries_submitted": sum(1 for leg in legs if leg.get("entry")),
              "entries_filled": sum(1 for leg in legs if leg.get("entry") and Decimal(leg["entry"]["filled_qty"]) > 0),
              "exit_orders_submitted": sum(len(leg.get("exits", [])) for leg in legs),
              "buy_notional_usd": text(sum((Decimal(r["buy_notional_usd"]) for r in pnl.values()), Decimal(0))),
              "sell_notional_usd": text(sum((Decimal(r["sell_notional_usd"]) for r in pnl.values()), Decimal(0))),
              "realized_pnl_usd": text(sum(per_symbol, Decimal(0))) if all_flat else None,
              "ledger_realized_pnl_delta_usd": text(realized_delta),
              "ledger_cash_delta_usd": text(after.cash_delta_usd - ledger_before.cash_delta_usd),
              "pnl_consistent": bool(all_flat and abs(sum(per_symbol, Decimal(0)) - realized_delta) <= Decimal("0.01")),
              "native_fill_events": outcome.get("native_fill_events", 0),
              "native_rejections": outcome.get("native_rejections", 0)}
    receipt = {
        "schema_version": 1, "kind": "mover_trial_receipt", "protocol": PROTOCOL_ID, "section": "paper_e2e",
        "evidence_class": plan.evidence_class, "status": outcome.get("status"), "flat": outcome.get("flat"),
        "trial_id": plan.trial_id, "config_sha256": config_sha256, "scan_sha256": scan.sha256,
        "rule": plan.rule.text, "exit_rule": plan.exit_rule,
        "scan": {"scan_time": _iso(scan.scan_time), "session_date": scan.session_date.isoformat(),
                 "age_seconds_at_trial_start": round(plan.timing.trial_start - scan.scan_time, 3),
                 "symbols": len(scan.symbols), "regime_inputs": scan.regime_inputs},
        **plan_receipt(plan),
        "symbols": legs, "totals": totals,
        "reconciliation": {"start": {"flat_account_and_no_open_orders": True,
                                     "checked_by": "runner.validate_preflight and the native adapter's startup snapshot"},
                           "end": outcome.get("reconciliation"), "recovery": outcome.get("recovery")},
        "ledger_risk": {"lifetime_realized_pnl_usd": text(after.realized_pnl_usd),
                        "lifetime_gross_loss_usd": text(after.gross_loss_usd), "drawdown_usd": text(after.drawdown_usd),
                        "halted_reason": after.halted_reason},
        "force_reason": outcome.get("force_reason"), "force_at": outcome.get("force_at"),
        "handoff_to_recovery": outcome.get("handoff_to_recovery"),
        # Positions still held because one share exceeds the ledger's per-order cap (the
        # reason a trial that moved past the exit headroom ends needs_attention).
        "unsellable_positions": list((outcome.get("recovery") or {}).get("unsellable_positions", [])),
        "adapter_errors": outcome.get("adapter_errors", []), "error_type": outcome.get("error_type"),
        "error_reason": outcome.get("error_reason"),
        "callback_faults": outcome.get("callback_faults", []),
        "execution_stats": outcome.get("execution_stats"),
        "average_invariant_mismatches": outcome.get("average_invariant_mismatches", []),
        "halts": outcome.get("halts"),
        "foreign_terminal_orders_ignored": outcome.get("foreign_terminal_orders_ignored", 0),
        "native": {key: outcome.get(key) for key in ("engine", "native_quotes", "native_fill_events",
                                                   "native_rejections", "orders_submitted", "requests",
                                                   "dropped_quotes", "session_policy", "elapsed_seconds")},
        "events": outcome.get("events", []),
        "limitations": list(LIMITATIONS[plan.evidence_class])}
    if preflight is not None:
        receipt["preflight"] = preflight
    if extra:
        receipt.update(extra)
    return receipt


def not_started(output, *, evidence_class, reason, config_sha256=None, scan_sha256=None, stage="validation",
                preflight=None):
    result = {"schema_version": 1, "kind": "mover_trial_receipt", "protocol": PROTOCOL_ID, "section": "paper_e2e",
              "evidence_class": evidence_class, "status": "not_started", "stage": stage, "reason": reason,
              "config_sha256": config_sha256, "scan_sha256": scan_sha256, "orders_submitted": 0}
    if preflight is not None:
        result["preflight"] = preflight
    save(output, result)
    print(json.dumps({k: result[k] for k in ("status", "stage", "reason", "orders_submitted")}))
    return 2


def _controller_session(close, now, session_policy):
    """Controller close/market_open exactly as runner.main derives them."""
    if not session_policy["extended_hours"]:
        return close, True
    moment = datetime.fromtimestamp(now, timezone.utc)
    market_open = session_at(moment).kind != SessionKind.CLOSED
    if market_open:
        close = extended_session_close(moment).astimezone(timezone.utc).timestamp()
    return close, market_open


def _bounded_reason(exc):
    """A SafetyError/ValueError reason code when it is one; never provider text."""
    text_value = str(exc)
    if isinstance(exc, (SafetyError, ValueError)) and re.fullmatch(r"[a-z0-9_:]{1,100}", text_value):
        return text_value
    return None


def _preflight_observer(attempts):
    def observe_request(kind, **kwargs):
        attempts.append({"timestamp": time.time(), "kind": kind})
        if len(attempts) > 50:
            raise SafetyError("preflight_request_bound")
    return observe_request


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def command_check(args):
    config, limits, settings = load_mover_config(args.config)
    raw = args.scan.read_bytes()
    # --assume-fresh: load_scan evaluates the scan as of its own scan_time (now=None), so that
    # time comes from the same guarded parser and a malformed file is refused, not raised.
    now = None if args.assume_fresh else time.time()
    try:
        scan = load_scan(raw, settings, now=now)
    except MoverRefusal as exc:
        print(json.dumps({"status": "refused", "reason": str(exc)}))
        return 2
    if now is None:
        now = scan.scan_time
    try:
        session_plan = plan_session(None, equity=limits.capital_usd, rung_schedule=settings.rung_schedule)
        plan = build_plan(settings, limits, scan, session_plan, trial_id="check", evidence_class="SYN", t0=now,
                          equity=limits.capital_usd)
    except MoverRefusal as exc:
        print(json.dumps({"status": "refused", "reason": str(exc)}))
        return 2
    result = {"status": "valid", "freshness_checked": not args.assume_fresh, "scan_sha256": scan.sha256,
              "config_sha256": _sha256(args.config.read_bytes()), "rule": plan.rule.text, "exit_rule": plan.exit_rule,
              "assumed": "session 1, equity = capital_usd, trial start = now",
              **plan_receipt(plan),
              "symbols": [{"symbol": s.scan.symbol, "rank": s.scan.rank, "leverage_i": text(s.leverage_i),
                           "raw_notional_usd": text(s.raw_notional_usd),
                           "caps_usd": {k: text(v) for k, v in s.caps_usd.items()},
                           "intended_notional_usd": text(s.notional_usd), "binding": s.binding,
                           "skip_reason": s.skip_reason} for s in plan.symbols]}
    if args.output:
        save(args.output, result)
    print(json.dumps(result, indent=2, default=str))
    return 0


def command_paper(args):
    global LAST_EVIDENCE_CLASS
    LAST_EVIDENCE_CLASS = "PAPER"
    if not TRIAL_ID.fullmatch(args.trial):
        raise ValueError("invalid_trial_id")
    from transport import AlpacaPaperTransport, TransportError, halt_statuses_supported, nasdaq_halt_seed, preflight
    config, limits, settings = load_mover_config(args.config)
    config_sha = _sha256(args.config.read_bytes())
    try:
        raw = args.scan.read_bytes()
    except OSError:
        return not_started(args.output, evidence_class="PAPER", reason="scan_unreadable", config_sha256=config_sha)
    scan_sha = _sha256(raw)
    try:
        scan = load_scan(raw, settings, now=time.time())
    except MoverRefusal as exc:
        return not_started(args.output, evidence_class="PAPER", reason=str(exc), config_sha256=config_sha,
                           scan_sha256=scan_sha)
    if not scan.symbols:
        return not_started(args.output, evidence_class="PAPER", reason="scan_empty", config_sha256=config_sha,
                           scan_sha256=scan_sha)
    session_policy = validate_session_policy(config)
    key, secret = credentials(args.env_file)
    symbols = [item.symbol for item in scan.symbols]
    attempts, responses = [], []
    probe_config = engine_config(config, symbols)
    try:
        observation = preflight(key, secret, probe_config["symbols"], feed=config["feed"],
                                before_request=_preflight_observer(attempts), request_observer=responses.append,
                                include_margin=config.get("_leverage_policy") is not None)
    except TransportError as exc:
        return not_started(args.output, evidence_class="PAPER", reason=str(exc), stage="preflight",
                           config_sha256=config_sha, scan_sha256=scan_sha)
    except Exception as exc:  # read-only preflight, e.g. the SDK refusing an unknown scan symbol
        return not_started(args.output, evidence_class="PAPER", reason="preflight_error:" + type(exc).__name__,
                           stage="preflight", config_sha256=config_sha, scan_sha256=scan_sha)
    summary = public_preflight(observation, probe_config)
    summary.update(http=responses, config_sha256=config_sha, scan_sha256=scan_sha)
    assets = {asset["symbol"]: asset for asset in observation["assets"]}
    tradable = [s for s in symbols if assets.get(s, {}).get("status") == "active"
                and assets.get(s, {}).get("tradable") is True]
    summary["untradable_scan_symbols"] = [s for s in symbols if s not in tradable]
    if not tradable:
        return not_started(args.output, evidence_class="PAPER", reason="no_tradable_scan_symbol", stage="preflight",
                           config_sha256=config_sha, scan_sha256=scan_sha, preflight=summary)
    trial_config = engine_config(config, tradable)
    gate_mode = "paper" if (args.gate_result is not None or args.snapshot is not None) else None
    summary["promotion_gate"] = "validated" if gate_mode else "not_supplied"
    try:
        close = validate_preflight(observation, trial_config, require_open=True, session_policy=session_policy,
                                   mode=gate_mode, gate_result_path=args.gate_result, snapshot_path=args.snapshot)
        server_now = observation["clock"]["timestamp_ns"] / 1e9
        info = session_at(datetime.fromtimestamp(server_now, timezone.utc))
        if settings.session_scope == "pre_market_only" and info.kind != SessionKind.PRE:
            raise SafetyError("mover_session_scope_mismatch")
        if info.session_date != scan.session_date:
            raise SafetyError("scan_session_date_mismatch")
    except (SafetyError, ValueError) as exc:
        return not_started(args.output, evidence_class="PAPER", reason=str(exc), stage="preflight",
                           config_sha256=config_sha, scan_sha256=scan_sha, preflight=summary)
    fingerprint = observation["account_identity_sha256"]
    with account_lock_fingerprint(fingerprint):
        state_dir = args.state_root / fingerprint / "mover"
        metadata_path = state_dir / "trial.json"
        if (args.state_root / fingerprint / "adaptive").exists() and not args.allow_shared_account:
            # The adaptive lane's own continuity check and snapshot reconciliation do not
            # tolerate another ledger's orders or cash changes on its account (see README-mover.md).
            return not_started(args.output, evidence_class="PAPER", reason="account_shared_with_adaptive_lane",
                               stage="trial_start", config_sha256=config_sha, scan_sha256=scan_sha, preflight=summary)
        previous = json.loads(metadata_path.read_text()) if metadata_path.exists() else None
        if previous is not None and (not isinstance(previous, dict) or previous.get("phase") != "finished"):
            return not_started(args.output, evidence_class="PAPER", reason="existing_trial_requires_explicit_recovery",
                               stage="trial_start", config_sha256=config_sha, scan_sha256=scan_sha, preflight=summary)
        try:
            ledger = Ledger(state_dir / "ledger.sqlite3", limits)
        except SafetyError as exc:
            return not_started(args.output, evidence_class="PAPER", reason=str(exc), stage="trial_start",
                               config_sha256=config_sha, scan_sha256=scan_sha, preflight=summary)
        try:
            now = time.time()
            try:
                for attempt in attempts:
                    if attempt["kind"] != "data_read" and ledger.request_budget(attempt["timestamp"], "read"):
                        raise SafetyError("preflight_budget_inconsistent")
                if ledger.positions() or ledger.unresolved():
                    raise SafetyError("next_trial_requires_recovery")
                scan = load_scan(raw, settings, now=now)  # freshness again, at trial start
                before = ledger.accounting()
                equity = limits.capital_usd + before.realized_pnl_usd
                session_plan = plan_session((previous or {}).get("lane_state"), equity=equity,
                                            rung_schedule=settings.rung_schedule)
                multiple = Decimal(1)
                if limits.leverage is not None:
                    multiple = limits.leverage.envelope(session=info.kind.value,
                                                        drawdown_fraction=before.drawdown_usd / limits.max_drawdown_usd)
                scan = replace(scan, symbols=tuple(s for s in scan.symbols if s.symbol in tradable))
                plan = build_plan(settings, limits, scan, session_plan, trial_id=args.trial, evidence_class="PAPER",
                                  t0=now, equity=equity, engine_leverage_multiple=multiple)
                ledger.begin_next_trial(now, args.trial)
            except SafetyError as exc:
                return not_started(args.output, evidence_class="PAPER", reason=str(exc), stage="trial_start",
                                   config_sha256=config_sha, scan_sha256=scan_sha, preflight=summary)
            baseline = Decimal(observation["account"]["cash"]) - before.cash_delta_usd
            # The engine's next_trial_cash_mismatch quantity, kept as an observation: the
            # baseline is per trial, so activity between mover trials (e.g. another lane on
            # a shared account) is recorded here instead of refusing the trial.
            inter_trial = (None if previous is None or previous.get("baseline_cash") is None else
                           Decimal(observation["account"]["cash"])
                           - (Decimal(previous["baseline_cash"]) + before.cash_delta_usd))
            history = list((previous or {}).get("history", []))
            metadata = {"lane": "mover", "protocol": PROTOCOL_ID, "trial_id": args.trial, "config_sha256": config_sha,
                        "scan_sha256": scan_sha, "symbols": list(plan.symbol_names()),
                        "shared_account_override": bool(args.allow_shared_account),
                        "started_at": (previous or {}).get("started_at", now), "current_trial_started_at": now,
                        "baseline_cash": format(baseline, "f"), "phase": "starting",
                        "inter_trial_cash_change_usd": None if inter_trial is None else format(inter_trial, "f"),
                        "lane_state": session_state_after(session_plan, equity_end=equity), "history": history}
            save(metadata_path, metadata)
            controller_close, market_open = _controller_session(close, now, session_policy)
            controller = MoverController(ledger, controller_close, market_open=market_open,
                                         max_entry_notional_usd=settings.max_entry_notional_usd)
            # E4 startup state, as runner.main: only where the stream carries statuses.
            controller.halt_seed_fetch = nasdaq_halt_seed if halt_statuses_supported(config["feed"]) else None
            if args.live_dir is not None:
                controller.events = LiveEventLog(args.live_dir / "events.jsonl")
                (args.live_dir / "run.json").write_text(json.dumps(
                    {"trial": args.trial, "lane": "mover", "ledger": str(state_dir / "ledger.sqlite3"),
                     "stop_file": str(safety.DEFAULT_STOP)}) + "\n")
            prefixes = (f"mvr-{args.trial}-", f"rec-{args.trial}-")

            def fresh_port(recovering=False):
                needed = sorted(set(ledger.positions()) | {i.symbol for i in ledger.unresolved()})
                return controller.bind(AlpacaPaperTransport(
                    key, secret, trial_config["symbols"], before_request=controller.before_request,
                    before_submit=controller.before_submit, sink_observation=controller.observe,
                    sink_status=controller.trading_status,
                    request_observer=responses.append, quote_timeout=settings.stream_quote_timeout_seconds,
                    feed=config["feed"],
                    required_quote_symbols=needed if recovering and needed else list(settings.benchmarks),
                    # As runner.main: from the lane's first trial, so reconcile sees every owned intent.
                    history_start=datetime.fromtimestamp(metadata["started_at"], timezone.utc),
                    extended_hours_allowed=session_policy["extended_hours"],
                    include_margin=limits.leverage is not None))

            for sig in (signal.SIGINT, signal.SIGTERM):
                signal.signal(sig, lambda *_: setattr(controller, "stop", True))

            async def execute():
                if plan.session.paused or all(item.skip_reason for item in plan.symbols):
                    return {"status": "completed_no_signals", "flat": True, "native_fill_events": 0,
                            "legs": make_book(plan, controller).leg_receipts(),
                            "reconciliation": {"positions_match": True, "cash_match": True, "open_orders": 0,
                                               "positions": 0, "source": "preflight_flat_no_node_started"},
                            "force_reason": plan.session.reason or "no_sizable_symbol"}
                controller.port = fresh_port()
                try:
                    outcome = await run_mover(controller, plan, trial_config, metadata["baseline_cash"],
                                              account_fingerprint=fingerprint,
                                              log_directory=None if args.live_dir is None else args.live_dir / "nautilus")
                except Exception as exc:
                    # run_mover keeps its own outcome, order journal included, for a failure once its
                    # node task exists; this is a failure before that, when no order can have been sent.
                    outcome = {"status": "needs_attention", "flat": False, "native_fill_events": 0,
                               "error_type": type(exc).__name__, "error_reason": _bounded_reason(exc)}
                if ledger.positions() or ledger.unresolved():
                    controller.stop = True
                    controller.port = fresh_port(True)
                    outcome = _apply_forced_recovery_outcome(outcome, await recover_mover(
                        controller, metadata, trial_config))
                return outcome

            outcome = asyncio.run(execute())
            receipt = build_receipt(plan=plan, outcome=outcome, config_sha256=config_sha, scan=scan, ledger=ledger,
                                    ledger_before=before, prefixes=prefixes, preflight=summary,
                                    extra={"shared_account_override": bool(args.allow_shared_account),
                                           "inter_trial_cash_changed": (None if inter_trial is None else
                                                                        abs(inter_trial) > Decimal("0.01"))})
            phase, exit_code = trial_phase_and_exit_code(receipt)
            after = ledger.accounting()
            equity_end = limits.capital_usd + after.realized_pnl_usd
            metadata.update(phase=phase, status=receipt["status"],
                            lane_state=session_state_after(session_plan, equity_end=equity_end))
            history.append({"trial_id": args.trial, "session_number": session_plan.number,
                            "session_date": scan.session_date.isoformat(), "status": receipt["status"],
                            "equity_start_usd": format(equity, "f"), "equity_end_usd": format(equity_end, "f"),
                            "config_sha256": config_sha, "scan_sha256": scan_sha})
            metadata["history"] = history
            save(metadata_path, metadata)
            save(args.output, receipt)
            print(json.dumps({k: receipt.get(k) for k in ("status", "flat", "evidence_class")}, default=str))
            return exit_code
        finally:
            ledger.close()


def command_recover(args):
    global LAST_EVIDENCE_CLASS
    LAST_EVIDENCE_CLASS = "PAPER"
    from transport import AlpacaPaperTransport, TransportError, preflight
    config, limits, settings = load_mover_config(args.config)
    session_policy = validate_session_policy(config)
    key, secret = credentials(args.env_file)
    attempts, responses = [], []
    observe = _preflight_observer(attempts)
    include_margin = config.get("_leverage_policy") is not None
    try:
        observation = preflight(key, secret, list(settings.benchmarks), feed=config["feed"], before_request=observe,
                                request_observer=responses.append, include_margin=include_margin)
        needed = sorted({p["symbol"] for p in observation["positions"]} | {o["symbol"] for o in observation["orders"]}
                        | set(settings.benchmarks))
        if needed != sorted(settings.benchmarks):
            observation = preflight(key, secret, needed, feed=config["feed"], before_request=observe,
                                    request_observer=responses.append, include_margin=include_margin)
    except TransportError as exc:
        return not_started(args.output, evidence_class="PAPER", reason=str(exc), stage="preflight")
    fingerprint = observation["account_identity_sha256"]
    with account_lock_fingerprint(fingerprint):
        state_dir = args.state_root / fingerprint / "mover"
        metadata_path = state_dir / "trial.json"
        if not metadata_path.exists():
            raise SafetyError("no_owned_trial_to_recover")
        metadata = json.loads(metadata_path.read_text())
        ledger = Ledger(state_dir / "ledger.sqlite3", limits)
        try:
            for attempt in attempts:
                if attempt["kind"] != "data_read" and ledger.request_budget(attempt["timestamp"], "read"):
                    raise SafetyError("preflight_budget_inconsistent")
            owned = set(ledger.positions()) | {i.symbol for i in ledger.unresolved()}
            trial_config = engine_config(config, sorted(set(needed) | owned))
            close = validate_preflight(observation, trial_config, require_open=True, allow_existing=True,
                                       session_policy=session_policy)
            controller_close, market_open = _controller_session(close, time.time(), session_policy)
            controller = MoverController(ledger, controller_close, market_open=market_open,
                                         max_entry_notional_usd=settings.max_entry_notional_usd)
            recovering = sorted(owned) or list(settings.benchmarks)
            controller.port = controller.bind(AlpacaPaperTransport(
                key, secret, trial_config["symbols"], before_request=controller.before_request,
                before_submit=controller.before_submit, sink_observation=controller.observe,
                sink_status=controller.trading_status,
                request_observer=responses.append, quote_timeout=settings.stream_quote_timeout_seconds,
                feed=config["feed"], required_quote_symbols=recovering,
                history_start=datetime.fromtimestamp(metadata["started_at"], timezone.utc),
                extended_hours_allowed=session_policy["extended_hours"], include_margin=include_margin))
            result = asyncio.run(recover_mover(controller, metadata, trial_config))
            result.update(kind="mover_recovery_receipt", protocol=PROTOCOL_ID, evidence_class="PAPER",
                          trial_id=metadata["trial_id"])
            phase, exit_code = trial_phase_and_exit_code(result)
            metadata.update(phase=phase, status=result["status"], recovered_at=time.time())
            save(metadata_path, metadata)
            save(args.output, result)
            print(json.dumps({k: result.get(k) for k in ("status", "flat")}))
            return exit_code
        finally:
            ledger.close()


def synthetic_path(plan, hold_seconds):
    """Default scripted path for ``synthetic``: each symbol opens at its scan price,
    rises 10% by half the hold, eases to 95% at the hold and 88% four seconds later,
    so X1/X2 exit on time, X3 trails out in the tail and X4 is flattened."""
    from mover_simulation import piecewise_path
    points = {}
    for item in plan.symbols:
        p = item.scan.price_at_t
        spread = max(Decimal("0.01") if p >= 1 else Decimal("0.0001"), (p * Decimal("0.001")))
        points[item.scan.symbol] = [(0, p, spread), (hold_seconds / 2, p * Decimal("1.10"), spread),
                                    (hold_seconds, p * Decimal("0.95"), spread),
                                    (hold_seconds + 4, p * Decimal("0.88"), spread)]
    return piecewise_path(points)


def synthetic_timing(t0, *, hold_seconds, exit_rule):
    return Timing(trial_start=t0, entry_deadline=t0 + 2, entry_timeout_seconds=2.0, exit_timeout_seconds=1.0,
                  hard_flatten_at=t0 + hold_seconds + 6, sell_window_end=t0 + hold_seconds + 14,
                  x1_at=t0 + hold_seconds if exit_rule == "X1" else None, x2_hold_seconds=float(hold_seconds))


def synthetic_config(config):
    """The config with the regular-session order flag, so a synthetic run never depends
    on the wall-clock session calendar."""
    result = dict(config)
    result.update(regular_session_only=True, extended_hours_enabled=False,
                  sessions={"extended_hours": False, "overnight_holds": False, "overnight_gross_multiple": "1.0"})
    return result


def command_synthetic(args):
    global LAST_EVIDENCE_CLASS
    LAST_EVIDENCE_CLASS = "SYN"
    from mover_simulation import MoverSimulatedPort
    config, limits, settings = load_mover_config(args.config)
    config_sha = _sha256(args.config.read_bytes())
    raw = args.scan.read_bytes()
    now = time.time()
    try:
        # --allow-stale-scan: as of the scan's own scan_time, through load_scan's guarded parser.
        scan = load_scan(raw, settings, now=None if args.allow_stale_scan else now)
    except MoverRefusal as exc:
        return not_started(args.output, evidence_class="SYN", reason=str(exc), config_sha256=config_sha,
                           scan_sha256=_sha256(raw))
    if not scan.symbols:
        return not_started(args.output, evidence_class="SYN", reason="scan_empty", config_sha256=config_sha,
                           scan_sha256=scan.sha256)
    syn_config = engine_config(synthetic_config(config), [s.symbol for s in scan.symbols])
    with tempfile.TemporaryDirectory(prefix="mover-synthetic-") as root:
        ledger = Ledger(Path(root) / "ledger.sqlite3", limits)
        try:
            ledger.begin_next_trial(now, args.trial)
            before = ledger.accounting()
            session_plan = plan_session(None, equity=limits.capital_usd, rung_schedule=settings.rung_schedule)
            timing = synthetic_timing(now, hold_seconds=args.hold_seconds, exit_rule=settings.exit_rule)
            plan = build_plan(settings, limits, scan, session_plan, trial_id=args.trial, evidence_class="SYN", t0=now,
                              equity=limits.capital_usd, timing=timing)
            controller = MoverController(ledger, now + 36000, market_open=True,
                                         max_entry_notional_usd=settings.max_entry_notional_usd)
            port = MoverSimulatedPort(controller, syn_config["symbols"], path=synthetic_path(plan, args.hold_seconds))
            controller.port = port
            baseline = port.cash
            # The host STOP file (safety.DEFAULT_STOP) applies here too, as on every engine path.
            outcome = asyncio.run(run_mover(controller, plan, syn_config, format(baseline, "f")))
            receipt = build_receipt(plan=plan, outcome=outcome, config_sha256=config_sha, scan=scan, ledger=ledger,
                                    ledger_before=before, prefixes=(f"mvr-{args.trial}-", f"rec-{args.trial}-"),
                                    extra={"synthetic": {"scan_age_check": "skipped" if args.allow_stale_scan else "passed",
                                                         "hold_seconds": args.hold_seconds,
                                                         "path": "mover_runner.synthetic_path"}})
        finally:
            ledger.close()
    save(args.output, receipt)
    print(json.dumps({k: receipt.get(k) for k in ("status", "flat", "evidence_class")}, default=str))
    return 0 if receipt["status"] in ("passed", "completed_no_signals") else 3


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check", help="validate config and scan; print the entry plan (no broker I/O)")
    check.add_argument("--config", type=Path, default=SOURCE / "config-mover.json")
    check.add_argument("--scan", type=Path, required=True)
    check.add_argument("--output", type=Path, default=None)
    check.add_argument("--assume-fresh", action="store_true",
                       help="evaluate the scan as of its own scan_time (skips only the age check)")
    paper = commands.add_parser("paper", help="one bounded Alpaca paper mover trial")
    paper.add_argument("--env-file", required=True, type=Path)
    paper.add_argument("--config", type=Path, default=SOURCE / "config-mover.json")
    paper.add_argument("--scan", type=Path, required=True)
    paper.add_argument("--output", type=Path, required=True)
    paper.add_argument("--trial", required=True)
    paper.add_argument("--state-root", type=Path, default=safety.DEFAULT_STOP.parent)
    paper.add_argument("--gate-result", type=Path, default=None)
    paper.add_argument("--snapshot", type=Path, default=None)
    paper.add_argument("--live-dir", type=Path, default=None)
    paper.add_argument("--allow-shared-account", action="store_true",
                       help="run although this state root holds an adaptive lane for the same account; that lane's "
                            "next trial will then refuse or freeze on this lane's orders (see README-mover.md)")
    recover = commands.add_parser("recover", help="flatten and reconcile an interrupted mover trial")
    recover.add_argument("--env-file", required=True, type=Path)
    recover.add_argument("--config", type=Path, default=SOURCE / "config-mover.json")
    recover.add_argument("--output", type=Path, required=True)
    recover.add_argument("--state-root", type=Path, default=safety.DEFAULT_STOP.parent)
    synthetic = commands.add_parser("synthetic", help="native engine against a local synthetic port (SYN)")
    synthetic.add_argument("--config", type=Path, default=SOURCE / "config-mover.json")
    synthetic.add_argument("--scan", type=Path, required=True)
    synthetic.add_argument("--output", type=Path, required=True)
    synthetic.add_argument("--trial", default="synthetic")
    synthetic.add_argument("--hold-seconds", type=float, default=4.0)
    synthetic.add_argument("--allow-stale-scan", action="store_true")
    return parser


def main(argv=None):
    global LAST_OUTPUT
    args = build_parser().parse_args(argv)
    LAST_OUTPUT = getattr(args, "output", None)
    if args.command in ("paper", "synthetic") and not TRIAL_ID.fullmatch(args.trial):
        raise ValueError("invalid_trial_id")
    if args.command == "synthetic" and not 1 <= args.hold_seconds <= 60:
        raise ValueError("invalid_hold_seconds")
    return {"check": command_check, "paper": command_paper, "recover": command_recover,
            "synthetic": command_synthetic}[args.command](args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        # Never serialize provider exception text, request headers or account data.
        failure = {"schema_version": 1, "kind": "mover_trial_receipt", "protocol": PROTOCOL_ID,
                   "evidence_class": LAST_EVIDENCE_CLASS, "status": "failed", "error_type": type(exc).__name__,
                   "reason": _bounded_reason(exc), "reconciliation": "not_established"}
        if LAST_OUTPUT is not None:
            save(LAST_OUTPUT, failure)
        print(json.dumps(failure))
        raise SystemExit(3)
