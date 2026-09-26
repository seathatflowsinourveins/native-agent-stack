"""Native Nautilus v2 LiveNode glue; injected port owns broker I/O and risk.

No credentials or Alpaca client live in this module. Native events reflect port
confirmations, never locally simulated broker acceptance. Whole-share USD equity
limit/DAY orders only; unknown submission outcomes freeze and stop the node.

Fills are booked one broker execution at a time: a stream fill or partial_fill row that
carries event_qty, event_price and execution_id is booked as exactly that execution
(TradeId from the execution id, last_px the execution price). A cumulative quantity no
booked execution explains is a fill gap, closed from the stream or from the broker's
FILL activities for that order; a price is never derived from a cumulative average.
Once the broker reports an order canceled or expired (even before its fills are
booked), no execution may end above the cumulative quantity it reported then.
"""
from __future__ import annotations

import asyncio
import functools
import hashlib
from datetime import datetime, timezone
from decimal import Decimal
import importlib.metadata
import inspect
from pathlib import Path
import re
import sys
import time
import traceback
from typing import Protocol, Callable

# This module is sometimes loaded directly via importlib file-spec (see
# tests/test_adaptive_paper_native.py) without its own directory on
# sys.path; self-heal so the local sessions.py sibling import below resolves
# regardless of how the caller imported this module.
_HERE = str(Path(__file__).resolve().parent)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
from sessions import DEFAULT_SESSION_POLICY, order_extended_hours_flag, reconciliation_receipt

from nautilus_trader.common import Environment, FileWriterConfig, LogLevel
from nautilus_trader.config import DataClientConfig, ExecutionClientConfig, LiveNodeConfig
from nautilus_trader.config import LiveExecutionEngineConfig, LiveRiskEngineConfig, LoggerConfig
from nautilus_trader.live import LiveNode
from nautilus_trader.live.clients import MarketDataClient, ExecutionClient, DataClientFactory, ExecutionClientFactory
from nautilus_trader.model import (AccountBalance, AccountId, AccountType, ClientOrderId,
    Currency, Equity, FillReport, InstrumentId, LiquiditySide, Money, OmsType,
    OrderSide, OrderStatus, OrderStatusReport, OrderType, PositionSide,
    PositionStatusReport, Price, Quantity, QuoteTick, Symbol, TimeInForce,
    TradeId, TraderId, Venue, VenueOrderId)

VENUE = Venue("ALPACA")
USD = Currency.from_str("USD")
STATUSES = {"new": OrderStatus.ACCEPTED, "accepted": OrderStatus.ACCEPTED,
    "pending_new": OrderStatus.SUBMITTED, "partially_filled": OrderStatus.PARTIALLY_FILLED,
    "filled": OrderStatus.FILLED, "canceled": OrderStatus.CANCELED,
    "expired": OrderStatus.EXPIRED, "rejected": OrderStatus.REJECTED,
    "pending_cancel": OrderStatus.PENDING_CANCEL}
TERMINAL = {"filled", "canceled", "expired", "rejected"}
# trade_updates events (https://docs.alpaca.markets/us/docs/websocket-streaming.md,
# "Common Events" and "Less Common Events"; alpaca-py 0.44.0 TradeEvent adds
# "restated"). Every documented event string has exactly one handling here; any other
# string (trade corrections and busts are not trade_updates events) fails closed.
EXECUTION_EVENTS = frozenset({"fill", "partial_fill"})
STATUS_EVENTS = frozenset({"new", "accepted", "pending_new", "canceled", "expired", "rejected",
                           "pending_cancel", "order_cancel_rejected"})
REPLACE_EVENTS = frozenset({"replaced", "pending_replace", "order_replace_rejected"})
UNSUPPORTED_EVENTS = frozenset({"done_for_day", "calculated", "stopped", "suspended", "restated"})
FILL_GAP_GRACE_SECONDS = 2.0   # a stream fill normally lands well inside this after a REST read
# Alpaca reports cumulative averages rounded to 6 decimals, so filled_qty x average is
# within 0.5e-6 per share of the executions' notional. Recorded, never a freeze.
AVERAGE_ROUNDING = Decimal("0.0000005")
CALLBACK_FAULT_REASON = re.compile(r"[a-z][a-z0-9_]{0,79}")
# E2's overturn condition (convergence record 2026-09-24, E2; critic U4/B2) as named receipt
# signals: a stream fill event without its execution_id, qty or price, and a fill gap the
# activities had not closed when the session stopped (also the adapter error below).
OVERTURN_SIGNALS = {"fill_events_carry_execution_fields": "e2_fill_event_without_execution_fields",
                    "no_fill_gap_open_at_stop": "e2_fill_gap_open_at_stop"}
FILL_GAP_OPEN_AT_STOP = "fill_gap_open_at_stop"


def error_code(error):
    message = str(error)
    return message if isinstance(error, ValueError) and re.fullmatch(r"[a-z_]+", message) else type(error).__name__


def trade_event_kind(event):
    """How observe() handles one trade_updates ``event`` string (None for a REST row):
    "execution", "status", or the freeze reason it raises."""
    if event is None or event in STATUS_EVENTS:
        return "status"
    if event in EXECUTION_EVENTS:
        return "execution"
    if event in REPLACE_EVENTS:
        return "replace_event_requires_reconciliation"
    if event in UNSUPPORTED_EVENTS:
        return "unsupported_trade_event_requires_reconciliation"
    return "unknown_trade_event_requires_reconciliation"


def execution_trade_id(execution_id):
    """NautilusTrader TradeId for one broker execution: the execution id itself (an
    Alpaca execution_id is a 36-character UUID, TradeId's limit), or a 36-character
    digest of a longer id so an identity never overflows."""
    text = str(execution_id)
    if not text:
        raise ValueError("invalid_execution_id")
    return TradeId(text if len(text) <= 36 else hashlib.sha256(text.encode()).hexdigest()[:36])


def guarded_callback(method):
    """Wrap a Strategy on_order_* / on_position_* handler. NautilusTrader 2.0.0rc5's
    LiveNode discards an exception raised in such a handler (upstream issue #5039:
    strategy.rs dispatches with ``let _ =``), so the order state the handler was keeping
    would silently diverge. On any exception this records the callback name, exception
    type and a digest of the traceback, stops the strategy's submits, freezes the ledger
    with ``strategy_callback_exception_<name>``, stops the session through the
    strategy's ``fault_sink`` (the runner binds NativeSession.fail, so the node stops,
    cleanup runs through recovery and the run ends needs_attention) and re-raises."""
    name = method.__name__
    reason = "strategy_callback_exception_" + name
    if not CALLBACK_FAULT_REASON.fullmatch(reason):
        raise ValueError("callback_name_is_not_a_valid_freeze_reason")

    @functools.wraps(method)
    def guarded(self, event):
        try:
            return method(self, event)
        except Exception as error:
            record_callback_fault(self, name, reason, error)
            raise

    guarded.guarded_callback_reason = reason
    return guarded


def record_callback_fault(strategy, name, reason, error):
    """The guard's side effects; each step is attempted even when an earlier one fails."""
    digest = hashlib.sha256("".join(traceback.format_exception(error)).encode()).hexdigest()
    fault = {"callback": name, "error_type": type(error).__name__, "traceback_sha256": digest,
             "freeze_reason": reason}
    faults = getattr(strategy, "callback_faults", None)
    if isinstance(faults, list):
        faults.append(fault)
    strategy.faulted = True
    strategy.enabled = False
    try:
        strategy.ledger.freeze(reason)
    except Exception as freeze_error:
        fault["freeze_error"] = type(freeze_error).__name__
    sink = getattr(strategy, "fault_sink", None)
    if sink is not None:
        try:
            sink(reason + ":" + type(error).__name__)
        except Exception as stop_error:
            fault["stop_error"] = type(stop_error).__name__
    events = getattr(strategy, "event_sink", None)
    if events is not None:
        try:
            events({"type": "strategy_callback_exception", **fault})
        except Exception:
            pass
    return fault


class BrokerPort(Protocol):
    async def start(self, on_quote: Callable[[dict], None], on_order: Callable[[dict], None]) -> None: ...
    async def stop(self) -> None: ...
    async def submit(self, order: dict) -> dict: ...
    async def cancel(self, client_order_id: str) -> dict | None: ...
    async def snapshot(self) -> dict: ...
    # Every execution of one broker order, oldest first, each {"trade_id", "qty",
    # "price", "cum_qty", "symbol", "side", "transaction_time_ns"} (transport.
    # AlpacaPaperTransport.fill_activities). Used for fill gaps and startup fill reports.
    async def fill_activities(self, order_id: str) -> list[dict]: ...


class NativeOrderRejected(RuntimeError):
    """Only use for a definitive local refusal before any broker HTTP submit."""
    definitive_rejection = True
    not_sent = True


def dec(value, *, signed=False):
    value = Decimal(str(value))
    if not value.is_finite() or (not signed and value < 0):
        raise ValueError("invalid_decimal")
    return value


def shares(value):
    value = dec(value)
    if value != value.to_integral_value():
        raise ValueError("fractional_shares_unsupported")
    return Quantity.from_int(int(value))


def instrument(metadata):
    symbol = metadata["symbol"]
    if metadata.get("currency", "USD") != "USD" or not isinstance(symbol, str) or not symbol:
        raise ValueError("unsupported_instrument")
    return Equity(InstrumentId.from_str(symbol + ".ALPACA"), Symbol(symbol), USD,
                  metadata.get("price_precision", 2), Price.from_str(metadata.get("price_increment", "0.01")),
                  0, 0, lot_size=shares(metadata.get("lot_size", "1")))


class NativeSession:
    """Shared owner-loop state, deduplication and externally observable failures."""
    def __init__(self, port, symbols, session_policy=None):
        self.port = port
        self.instruments = {m["symbol"]: instrument(m) for m in symbols}
        if len(self.instruments) != len(symbols) or not symbols:
            raise ValueError("empty_or_duplicate_symbols")
        self.data = self.execution = self.node = self.handle = None
        self.errors = []
        self.started = self.stopped = False
        self._start_lock = self._stop_lock = None
        self.quotes = {}
        self.observations = []
        self.unresolved_orders = {}
        self.snapshot_state = None
        self.session_policy = dict(session_policy) if session_policy else dict(DEFAULT_SESSION_POLICY)
        self.reconciliation = None
        self.fee_assumption = "Port has no fees; native booking uses zero commission pending external fee reconciliation."
        self.fill_gap_grace_seconds = FILL_GAP_GRACE_SECONDS
        # Receipt counters for per-execution booking (E2 native assertions: every fill
        # event should carry its execution fields; activities should close every gap).
        self.execution_stats = {"executions_booked": 0, "duplicate_executions": 0,
                                "fill_events_missing_execution_fields": 0, "activity_fill_reconciliations": 0,
                                "activity_executions_booked": 0, "startup_fill_reports": 0,
                                "average_invariant_mismatches": 0, "open_fill_gaps_at_stop": 0}
        self.average_invariant_mismatches = []

    def fail(self, code):
        self.errors.append(str(code))
        if self.handle is not None and self.handle.is_running:
            self.handle.stop()

    def native_assertions(self):
        """E2's native assertions for the receipt, read after the session stopped: every
        stream fill event carried its execution fields, and no fill gap was still open at
        stop. Each false assertion is named in ``overturn_signals`` (an open gap is also
        the adapter error fill_gap_open_at_stop, so that run ends needs_attention)."""
        stats = self.execution_stats
        held = {"fill_events_carry_execution_fields": stats["fill_events_missing_execution_fields"] == 0,
                "no_fill_gap_open_at_stop": stats["open_fill_gaps_at_stop"] == 0}
        return {**held, "overturn_signals": [OVERTURN_SIGNALS[name] for name, ok in held.items() if not ok]}

    async def start(self):
        if self._start_lock is None:
            self._start_lock = asyncio.Lock()
        async with self._start_lock:
            if not self.started:
                await self.port.start(self.on_quote, self.on_order)
                self.started = True

    async def stop_port(self):
        if self._stop_lock is None:
            self._stop_lock = asyncio.Lock()
        async with self._stop_lock:
            if not self.stopped:
                if self.execution is not None:
                    self.execution.cancel_fill_gap_tasks()
                await self.port.stop()
                self.stopped = True

    def on_quote(self, row):
        try:
            sym = row["symbol"]
            ins = self.instruments[sym]
            bid, ask = dec(row["bid"]), dec(row["ask"])
            if bid <= 0 or ask < bid or type(row["ts_ns"]) is not int or row["ts_ns"] <= 0:
                raise ValueError("invalid_quote")
            # QuoteTick requires matching precision on both sides. Normalized
            # decimal strings may have different trailing-zero counts; pad to
            # their common exact precision, independently of cent order ticks.
            precision = max(0, -bid.as_tuple().exponent, -ask.as_tuple().exponent)
            if precision > 16:
                raise ValueError("quote_precision_unsupported")
            q = QuoteTick(ins.id, Price.from_str(format(bid, f".{precision}f")),
                          Price.from_str(format(ask, f".{precision}f")),
                          shares(row["bid_size"]), shares(row["ask_size"]), row["ts_ns"],
                          self.data.clock.timestamp_ns())
            previous = self.quotes.get(sym)
            if previous is not None and q.ts_event < previous.ts_event:
                return
            self.quotes[sym] = q
            if sym in self.data.subscriptions:
                self.data._handle_data(q)
        except Exception as error:
            self.fail("quote_" + error_code(error))

    def on_order(self, row):
        try:
            self.execution.observe(row)
        except Exception as error:
            if isinstance(row, dict) and row.get("client_order_id"):
                self.unresolved_orders[row["client_order_id"]] = dict(row)
            self.fail("order_" + error_code(error))

    async def run_async(self):
        try:
            await self.node.run_async()
        finally:
            await self.stop_port()

    def stop(self):
        if self.handle.is_running:
            self.handle.stop()


class AlpacaDataClient(MarketDataClient):
    def __init__(self, session, **kwargs):
        super().__init__(venue=VENUE, **kwargs)
        self.session, self.subscriptions = session, set()
        session.data = self

    async def _connect(self):
        for ins in self.session.instruments.values():
            self._handle_instrument(ins)
        await self.session.start()

    async def _disconnect(self):
        # Execution disconnect also awaits this single shared shutdown.
        await self.session.stop_port()

    async def _subscribe_quotes(self, command):
        sym = str(command.instrument_id.symbol)
        if sym not in self.session.instruments:
            raise ValueError("unknown_instrument")
        self.subscriptions.add(sym)
        if sym in self.session.quotes:
            self._handle_data(self.session.quotes[sym])

    async def _unsubscribe_quotes(self, command):
        self.subscriptions.discard(str(command.instrument_id.symbol))


class AlpacaExecutionClient(ExecutionClient):
    def __init__(self, session, account_id, account_type, **kwargs):
        super().__init__(venue=VENUE, account_id=AccountId(account_id), account_type=account_type,
                         oms_type=OmsType.NETTING, base_currency=USD, **kwargs)
        self.session = session
        self.orders, self.seen = {}, {}
        # Adopted open orders' executions up to their startup filled quantity (one FILL
        # activities read each, at connect), shared by the startup order and fill reports.
        self.startup_executions = {}
        self.reported_fills = set()
        session.execution = self

    async def _connect(self):
        # The port binds its REST callbacks to the owner loop during start.
        # Strategies remain stopped until this snapshot and native reconciliation
        # succeed; do not rely on data-client connection scheduling for ordering.
        await self.session.start()
        snapshot = await self.session.port.snapshot()
        self._validate_snapshot(snapshot)
        if self.session.session_policy.get("overnight_holds"):
            # Startup reconciliation (deliverable 3): accept existing positions
            # and open orders and record a reconciliation receipt instead of
            # requiring a flat account. The local ledger side of this delta is
            # populated by the caller (runner.py), which has ledger access;
            # this adapter only records the broker-side snapshot it observed.
            self.session.reconciliation = reconciliation_receipt(snapshot, boundary=False)
            # S6: transport.snapshot() merges open + recent-history pages, so
            # the raw snapshot can include historical terminal orders (e.g.
            # already filled/canceled/expired/rejected). snapshot_state is
            # later read by order_status_reports/generate_order_status_report
            # to replay open-order state into native on startup; a stale
            # terminal order there would be replayed as if still live.
            # reconciliation_receipt above already recorded the full
            # snapshot (open + terminal) for the reconciliation audit trail;
            # snapshot_state itself must keep only genuinely open orders.
            self.session.snapshot_state = {**snapshot,
                                           "orders": [row for row in snapshot["orders"]
                                                     if row["status"] not in TERMINAL]}
            # An adopted order's executions are read here, before native reconciliation
            # asks for its order and fill reports (rc5 requests both concurrently): the
            # order report's acceptance time must not follow its first execution.
            for row in self.session.snapshot_state["orders"]:
                if dec(row.get("filled_qty") or "0"):
                    await self._adopted_executions(row)
        else:
            if any(dec(row["qty"], signed=True) != 0 for row in snapshot["positions"]):
                raise ValueError("startup_requires_flat_account_use_external_recovery")
            if any(row["status"] not in TERMINAL for row in snapshot["orders"]):
                raise ValueError("startup_requires_no_open_orders_use_external_recovery")
            # Closed historical broker rows are not current native positions or
            # fills. This new session deliberately does not adopt an old
            # strategy's ledger.
            self.session.snapshot_state = {**snapshot, "orders": [], "positions": []}
        self._account(snapshot["account"])

    async def _disconnect(self):
        await self.session.stop_port()

    def _validate_snapshot(self, snapshot):
        if not isinstance(snapshot, dict) or not {"account", "orders", "positions"} <= snapshot.keys():
            raise ValueError("invalid_snapshot")
        for key in ("cash", "buying_power", "equity"):
            dec(snapshot["account"][key], signed=key == "cash")
        if not isinstance(snapshot["orders"], list) or not isinstance(snapshot["positions"], list):
            raise ValueError("invalid_snapshot_lists")

    def _account(self, row):
        # Buying power/equity remain risk inputs on the port; never label buying
        # power as cash. Broker locked-cash semantics are not supplied here.
        cash = dec(row["cash"], signed=True)
        self.generate_account_state([AccountBalance(Money(cash, USD), Money(0, USD), Money(cash, USD))],
                                    [], True, self.clock.timestamp_ns(),
                                    info={"buying_power": str(row["buying_power"]), "equity": str(row["equity"]),
                                          "locked_cash_supplied": False})

    def _normalized(self, row):
        ins = self.session.instruments[row["symbol"]]
        qty, filled = dec(row["qty"]), dec(row["filled_qty"])
        if qty <= 0 or filled > qty or row["status"] not in STATUSES or row["side"] not in ("buy", "sell"):
            raise ValueError("invalid_order_state")
        shares(qty); shares(filled)
        if type(row["updated_at_ns"]) is not int or row["updated_at_ns"] <= 0:
            raise ValueError("invalid_order_timestamp")
        if not row.get("id") or not row.get("client_order_id"):
            raise ValueError("missing_order_identity")
        avg = dec(row["filled_avg_price"]) if filled else Decimal(0)
        if filled and avg <= 0:
            raise ValueError("invalid_fill_price")
        return ins, qty, filled, avg

    @staticmethod
    def _new_state(broker_id):
        """Per-order booking state: executions keyed by the cumulative quantity after
        them (the join key shared by stream fills and FILL activities). pending_terminal
        is (status, stamp, the broker's filled quantity then); gap_opened maps each
        cumulative quantity a booked execution did not yet explain to the monotonic time
        it was first reported."""
        return {"id": broker_id, "accepted": False, "terminal": None, "pending_terminal": None,
                "broker_filled": Decimal(0), "booked": Decimal(0), "averages": {}, "executions": {},
                "trade_ids": {}, "checked": set(), "gap_task": None, "gap_opened": {}}

    @staticmethod
    def _terminal_limit(prior):
        """The cumulative quantity no execution may end above, or None while the order
        works: the broker's filled quantity once the order is terminal natively, or when
        the broker reported the cancel or expiry that is still waiting for its fills."""
        if prior["terminal"]:
            return prior["broker_filled"]
        if prior["pending_terminal"] is not None:
            return prior["pending_terminal"][2]
        return None

    @staticmethod
    def _covered(prior, target):
        """How much of the cumulative range (0, target] booked executions cover (booked
        executions never overlap, so this equals target exactly when none is missing)."""
        return sum((row["qty"] for cum, row in prior["executions"].items() if cum <= target), Decimal(0))

    @staticmethod
    def _price(ins, price):
        return Price.from_str(format(price, f".{ins.price_precision}f"))

    def _checked_execution(self, ins, trade_id, qty, price, cum, source):
        qty, price, cum = dec(qty), dec(price), dec(cum)
        if not str(trade_id) or qty <= 0 or price <= 0 or qty > cum:
            raise ValueError("invalid_execution")
        shares(qty)
        shares(cum)
        # An execution price the instrument cannot represent is never rounded.
        if price != price.quantize(Decimal(1).scaleb(-ins.price_precision)):
            raise ValueError("execution_price_precision_requires_reconciliation")
        return {"trade_id": str(trade_id), "qty": qty, "price": price, "cum": cum, "source": source}

    def _stream_execution(self, row, ins, filled):
        """The execution a stream fill row carries, or None when its execution_id, qty
        or price is missing: the row then only reports a cumulative quantity, and a gap
        it opens is closed from the stream or the FILL activities."""
        if any(row.get(key) in (None, "") for key in ("execution_id", "event_qty", "event_price")):
            self.session.execution_stats["fill_events_missing_execution_fields"] += 1
            return None
        return self._checked_execution(ins, row["execution_id"], row["event_qty"], row["event_price"], filled, "stream")

    def _book(self, order, prior, execution, broker_id, stamp):
        """Book one execution natively, exactly as the broker reported it, unless it is
        already booked (same execution id, or same cumulative quantity with the same qty
        and price from the other source). A conflicting or overlapping execution, a new
        one after the native terminal event, or one ending above the filled quantity of
        a cancel or expiry the broker already reported, fails closed."""
        cum, qty, price, trade_id = execution["cum"], execution["qty"], execution["price"], execution["trade_id"]
        if prior["trade_ids"].get(trade_id, cum) != cum:
            raise ValueError("execution_conflict_requires_reconciliation")
        booked = prior["executions"].get(cum)
        if booked is not None:
            if (booked["qty"], booked["price"]) != (qty, price):
                raise ValueError("execution_conflict_requires_reconciliation")
            prior["trade_ids"].setdefault(trade_id, cum)
            self.session.execution_stats["duplicate_executions"] += 1
            return False
        limit = self._terminal_limit(prior)
        if prior["terminal"] or (limit is not None and cum > limit):
            raise ValueError("post_terminal_fill_requires_reconciliation")
        if cum > dec(str(order.quantity)):
            raise ValueError("execution_exceeds_order_quantity")
        lower = cum - qty
        if any(lower < other and other - row["qty"] < cum for other, row in prior["executions"].items()):
            raise ValueError("execution_overlap_requires_reconciliation")
        ins = self.session.instruments[str(order.instrument_id.symbol)]
        self.generate_order_filled(order, broker_id, None, execution_trade_id(trade_id), shares(qty),
                                   self._price(ins, price), USD, Money(0, USD), LiquiditySide.NO_LIQUIDITY_SIDE,
                                   stamp)
        prior["executions"][cum] = {"qty": qty, "price": price, "trade_id": trade_id, "source": execution["source"],
                                    "ts": stamp}
        prior["trade_ids"][trade_id] = cum
        prior["booked"] += qty
        self.session.execution_stats["executions_booked"] += 1
        return True

    def _settle(self, order, prior, broker_id):
        """Emit the native terminal event once every reported fill is booked; a cancel or
        expiry reported (e.g. by a REST read) before its fills arrived waits until then."""
        if prior["terminal"] or prior["booked"] < prior["broker_filled"]:
            return
        if prior["booked"] == dec(str(order.quantity)):
            prior["terminal"], prior["pending_terminal"] = "filled", None
            return
        if prior["pending_terminal"] is None:
            return
        status, stamp, _ = prior["pending_terminal"]
        if status == "canceled":
            self.generate_order_canceled(order, broker_id, stamp)
        else:
            self.generate_order_expired(order, broker_id, stamp)
        prior["terminal"], prior["pending_terminal"] = status, None

    def _check_average(self, prior, cid, filled, avg):
        """E2 invariant, recorded and never a freeze: once booked executions tile
        (0, filled], their notional equals filled x the broker's average within Alpaca's
        6-decimal rounding."""
        if not filled or filled in prior["checked"]:
            return
        total, previous = Decimal(0), Decimal(0)
        for cum in sorted(c for c in prior["executions"] if c <= filled):
            row = prior["executions"][cum]
            if cum - row["qty"] != previous:
                return
            total, previous = total + row["qty"] * row["price"], cum
        if previous != filled:
            return
        prior["checked"].add(filled)
        if abs(total - filled * avg) > filled * AVERAGE_ROUNDING:
            self.session.execution_stats["average_invariant_mismatches"] += 1
            if len(self.session.average_invariant_mismatches) < 20:
                self.session.average_invariant_mismatches.append(
                    {"client_order_id": cid, "filled_qty": str(filled), "average": str(avg),
                     "executions_notional": str(total)})

    def observe(self, row):
        kind = trade_event_kind(row.get("event"))
        if kind not in ("status", "execution"):
            raise ValueError(kind)
        ins, qty, filled, avg = self._normalized(row)
        cid, status = row["client_order_id"], row["status"]
        order = self.orders.get(cid) or self.cache.order(ClientOrderId(cid))
        if order is None:
            # Unknown broker orders must go through native reconciliation, never
            # be attributed to a strategy by guessing a current intent.
            self._handle_report(self.order_report(row))
            return
        if (order.instrument_id != ins.id or str(order.side).lower() != row["side"]
                or dec(str(order.quantity)) != qty):
            raise ValueError("confirmation_does_not_match_intent")
        prior = self.seen.get(cid) or self._new_state(row["id"])
        if prior["id"] != row["id"]:
            raise ValueError("broker_order_identity_changed")
        reported = prior["averages"].get(filled)
        if reported is not None and reported != avg:
            raise ValueError("same_quantity_fill_correction_requires_reconciliation")
        limit = self._terminal_limit(prior)
        if limit is not None and filled > limit:
            # Above the filled quantity of the native terminal event, or of a cancel or
            # expiry the broker already reported while its fills were still unbooked.
            raise ValueError("post_terminal_fill_requires_reconciliation")
        execution = self._stream_execution(row, ins, filled) if kind == "execution" else None
        if execution is None and filled < prior["broker_filled"]:
            return  # A delayed cumulative snapshot must never roll back fills.
        if status == "filled" and filled != qty:
            raise ValueError("filled_status_quantity_mismatch")
        broker_id, stamp = VenueOrderId(row["id"]), row["updated_at_ns"]
        self.seen[cid] = prior
        if status != "rejected" and status != "pending_new" and not prior["accepted"]:
            self.generate_order_accepted(order, broker_id, stamp)
            prior["accepted"] = True
        prior["averages"].setdefault(filled, avg)
        prior["broker_filled"] = max(prior["broker_filled"], filled)
        if execution is not None:
            self._book(order, prior, execution, broker_id, stamp)
        if not prior["terminal"]:
            if status in ("canceled", "expired") and prior["pending_terminal"] is None:
                prior["pending_terminal"] = (status, stamp, filled)
            elif status == "rejected":
                if prior["broker_filled"] or prior["booked"]:
                    raise ValueError("rejected_order_with_fills_requires_reconciliation")
                self.generate_order_rejected(order, str(row.get("reason", "broker_rejected")), stamp, False)
                prior["terminal"] = status
        self._settle(order, prior, broker_id)
        self._check_average(prior, cid, filled, avg)
        if prior["booked"] < prior["broker_filled"]:
            prior["gap_opened"].setdefault(prior["broker_filled"], time.monotonic())
            self._schedule_fill_gap(cid)
        self.session.observations.append({"client_order_id": cid, "status": status, "filled_qty": str(filled)})

    def _schedule_fill_gap(self, cid):
        prior = self.seen[cid]
        if prior["gap_task"] is not None or self.session.stopped:
            return  # a running gap task picks up every newer gap, each with its own grace
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return  # no owner loop (a direct call): reconcile_fills() stays available
        prior["gap_task"] = loop.create_task(self._fill_gap(cid))

    def _open_gaps(self, prior):
        """The gap targets (cumulative quantities reported but not yet explained by booked
        executions), oldest quantity first; closed ones are dropped."""
        for target in [t for t in prior["gap_opened"] if self._covered(prior, t) >= t]:
            del prior["gap_opened"][target]
        return sorted(prior["gap_opened"])

    async def _fill_gap(self, cid):
        """Close each fill gap of one order once it is fill_gap_grace_seconds old: the
        stream normally books the missing execution first; otherwise one FILL activities
        read books it. A gap opened while another was pending gets its own full grace,
        and a quantity reported during the read is a new gap, not a failure of this one."""
        prior = self.seen[cid]
        try:
            while not self.session.stopped and not self.session.errors:
                targets = self._open_gaps(prior)
                if not targets:
                    return
                target = targets[0]
                wait = prior["gap_opened"][target] + self.session.fill_gap_grace_seconds - time.monotonic()
                if wait > 0:
                    await asyncio.sleep(wait)
                    continue
                await self.reconcile_fills(cid, target)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            code = error_code(error)
            self.session.fail(code if code.startswith("fill_gap_") else "fill_gap_" + code)
        finally:
            prior["gap_task"] = None

    def cancel_fill_gap_tasks(self):
        """At shutdown: count gaps still open and cancel their pending reads. An open gap
        is an execution the native side never booked, so it is also the named adapter
        error fill_gap_open_at_stop (the run ends needs_attention), not only a counter."""
        open_gaps = sum(1 for prior in self.seen.values() if prior["booked"] < prior["broker_filled"])
        self.session.execution_stats["open_fill_gaps_at_stop"] = open_gaps
        if open_gaps and FILL_GAP_OPEN_AT_STOP not in self.session.errors:
            self.session.errors.append(FILL_GAP_OPEN_AT_STOP)
        for prior in self.seen.values():
            task = prior.get("gap_task")
            if task is not None and not task.done():
                task.cancel()

    async def reconcile_fills(self, cid, target=None):
        """Close a fill gap from the broker's FILL activities for the order: book every
        execution not yet booked (TradeId from the activity id's UUID, last_px its price;
        deduplicated by cumulative quantity against stream fills), then emit a deferred
        terminal event. One port read; never derives a price from an average. It fails
        only when the activities leave (0, target] (default: the broker's cumulative
        quantity at the call) uncovered, or when an activity ends above the filled
        quantity of a cancel or expiry the broker already reported."""
        prior = self.seen[cid]
        target = prior["broker_filled"] if target is None else target
        fetch = getattr(self.session.port, "fill_activities", None)
        if fetch is None:
            raise ValueError("fill_gap_unresolved_without_activities")
        activities = await fetch(prior["id"])
        self.session.execution_stats["activity_fill_reconciliations"] += 1
        order = self.orders.get(cid) or self.cache.order(ClientOrderId(cid))
        ins = self.session.instruments[str(order.instrument_id.symbol)]
        broker_id = VenueOrderId(prior["id"])
        executions = []
        for activity in activities:
            if (activity["symbol"], activity["side"]) != (str(order.instrument_id.symbol), str(order.side).lower()):
                raise ValueError("fill_activity_does_not_match_order")
            executions.append((self._checked_execution(ins, activity["trade_id"], activity["qty"], activity["price"],
                                                       activity["cum_qty"], "activity"),
                               activity["transaction_time_ns"]))
        limit = self._terminal_limit(prior)
        if limit is not None and any(execution["cum"] > limit for execution, _ in executions):
            raise ValueError("post_terminal_fill_requires_reconciliation")
        sink_observation = getattr(self.session.port, "sink_observation", None)
        if sink_observation is not None:
            # Use the same hook as AlpacaPaperTransport._observe_locked. Validate
            # the whole prefix before persisting any of it; FILL activities bypass
            # the normal observation path and must precede native fill callbacks.
            covered = Decimal(0)
            for execution, _ in executions:
                cum = execution["cum"]
                if cum - execution["qty"] != covered:
                    raise ValueError("fill_activity_ledger_incomplete")
                covered = cum
            if covered < target and self._covered(prior, target) < target:
                raise ValueError("fill_gap_unresolved_after_activities")
            notional = Decimal(0)
            for execution, stamp in executions:
                cum = execution["cum"]
                notional += execution["qty"] * execution["price"]
                status = "filled" if cum == dec(str(order.quantity)) else "partially_filled"
                if limit is not None and cum == limit:
                    status = prior["terminal"] or prior["pending_terminal"][0]
                # Retain reported averages where available; Alpaca reports new ones
                # to six decimals. Exact execution prices drive ledger accounting.
                average = prior["averages"].get(cum, (notional / cum).quantize(Decimal("0.000001")))
                result = sink_observation({"client_order_id": cid, "id": prior["id"], "status": status,
                    "filled_qty": str(cum), "filled_avg_price": str(average), "updated_at_ns": stamp,
                    "event": "fill" if status == "filled" else "partial_fill",
                    "execution_id": execution["trade_id"], "event_qty": str(execution["qty"]),
                    "event_price": str(execution["price"])})
                if inspect.isawaitable(result):
                    await result
        for execution, stamp in executions:
            if self._book(order, prior, execution, broker_id, stamp):
                self.session.execution_stats["activity_executions_booked"] += 1
            prior["broker_filled"] = max(prior["broker_filled"], execution["cum"])
        if self._covered(prior, target) < target:
            raise ValueError("fill_gap_unresolved_after_activities")
        self._settle(order, prior, broker_id)

    def order_report(self, row):
        ins, qty, filled, avg = self._normalized(row)
        accepted = row["updated_at_ns"]
        executions = self.startup_executions.get(row["client_order_id"])
        if executions:
            # rc5 applies startup reconciliation events in ts_event order: an acceptance
            # stamped at the order's last update (after its fills) would come after them,
            # and the fills would be dropped as invalid transitions on a still-initialized
            # order (then rc5 synthesizes a separate order for the position instead). The
            # order was accepted no later than its first execution.
            accepted = min(accepted, min(execution["ts"] for execution in executions))
        return OrderStatusReport(self.account_id, ins.id, VenueOrderId(row["id"]),
            OrderSide.BUY if row["side"] == "buy" else OrderSide.SELL, OrderType.LIMIT, TimeInForce.DAY,
            STATUSES[row["status"]], shares(qty), shares(filled), accepted, row["updated_at_ns"],
            self.clock.timestamp_ns(), client_order_id=ClientOrderId(row["client_order_id"]),
            price=Price.from_str(str(row["limit_price"])), avg_px=avg if filled else None)

    async def _submit_order(self, command):
        order = command.order
        if self.session.errors:
            self.generate_order_denied(order, "adapter_frozen")
            return
        if (order.order_type != OrderType.LIMIT or order.time_in_force != TimeInForce.DAY
                or str(order.instrument_id.symbol) not in self.session.instruments):
            self.generate_order_denied(order, "only_USD_equity_limit_DAY_supported")
            return
        cid = str(order.client_order_id)
        if cid in self.orders:
            self.session.fail("duplicate_native_submit")
            return
        self.orders[cid] = order
        tags = list(order.tags or [])
        now = datetime.fromtimestamp(self.clock.timestamp_ns() / 1e9, tz=timezone.utc)
        extended_hours = order_extended_hours_flag(now, self.session.session_policy)
        payload = {"client_order_id": cid, "symbol": str(order.instrument_id.symbol),
            "side": str(order.side).lower(), "qty": str(order.quantity), "limit_price": str(order.price),
            "type": "limit", "time_in_force": "day", "extended_hours": extended_hours,
            "tags": tags, "strategy": str(order.strategy_id)}
        for tag in tags:
            if tag.startswith("reason="):
                payload["reason"] = tag.split("=", 1)[1]
        self.generate_order_submitted(order)
        try:
            result = await self.session.port.submit(payload)
            self.observe(result)
        except Exception as error:
            if getattr(error, "definitive_rejection", False) is True:
                self.generate_order_rejected(order, str(error), self.clock.timestamp_ns(), False)
            else:
                self.session.fail("unknown_submit:" + cid + ":" + type(error).__name__)

    async def _cancel_order(self, command):
        try:
            result = await self.session.port.cancel(str(command.client_order_id))
            if result is not None:
                self.observe(result)
        except Exception as error:
            self.session.fail("unknown_cancel:" + type(error).__name__)

    async def _cancel_all_orders(self, command):
        try:
            for order in self.cache.orders_open(venue=VENUE, instrument_id=command.instrument_id,
                                                side=command.order_side):
                result = await self.session.port.cancel(str(order.client_order_id))
                if result is not None:
                    self.observe(result)
        except Exception as error:
            self.session.fail("unknown_cancel_all:" + type(error).__name__)

    async def _modify_order(self, command):
        order = self.cache.order(command.client_order_id)
        if order is None:
            self.session.fail("modify_unknown_order")
            return
        self.generate_order_modify_rejected(order, order.venue_order_id,
                                            "replace_not_qualified_use_cancel_then_new_intent", self.clock.timestamp_ns())

    async def _query_account(self, command):
        snapshot = await self.session.port.snapshot()
        self._validate_snapshot(snapshot)
        self._account(snapshot["account"])

    async def _query_order(self, command):
        report = await self._generate_order_status_report(command)
        if report is not None:
            self._handle_report(report)

    async def _generate_order_status_report(self, command):
        snapshot = await self.session.port.snapshot()
        self._validate_snapshot(snapshot)
        for row in snapshot["orders"]:
            if row["client_order_id"] == str(command.client_order_id):
                return self.order_report(row)
        return None

    async def _generate_order_status_reports(self, command):
        return [self.order_report(row) for row in self.session.snapshot_state["orders"]]

    async def _adopted_executions(self, row):
        """The executions of one adopted open order up to its startup filled quantity,
        from one read of the broker's FILL activities (cached per order). They must tile
        that quantity exactly from zero; a later one reaches the order through the stream
        or a fill gap. Nonzero startup fills are never fabricated from an average."""
        cid = row["client_order_id"]
        if cid in self.startup_executions:
            return self.startup_executions[cid]
        fetch = getattr(self.session.port, "fill_activities", None)
        if fetch is None:
            raise ValueError("historical_fill_ledger_not_supplied_by_port")
        ins, qty, filled, avg = self._normalized(row)
        executions, covered = [], Decimal(0)
        for activity in await fetch(row["id"]):
            execution = self._checked_execution(ins, activity["trade_id"], activity["qty"], activity["price"],
                                                activity["cum_qty"], "activity")
            if execution["cum"] > filled:
                continue
            if ((activity["symbol"], activity["side"]) != (row["symbol"], row["side"])
                    or execution["cum"] - execution["qty"] != covered):
                raise ValueError("historical_fill_ledger_incomplete")
            covered = execution["cum"]
            executions.append(dict(execution, ts=activity["transaction_time_ns"]))
        if covered != filled:
            raise ValueError("historical_fill_ledger_incomplete")
        self.startup_executions[cid] = executions
        return executions

    async def _generate_fill_reports(self, command):
        """One FillReport per execution of every adopted open order with fills (only an
        overnight-holds start adopts open orders), honouring the command's venue_order_id
        and instrument_id filters (start and end are not applied: an adopted order's
        report always carries its whole execution history). An order's booking state is
        seeded from its FILL activities only the first time; a later call reports the
        executions booked natively since (their own trade ids), never rolls them back and
        reads nothing."""
        venue_order_id = getattr(command, "venue_order_id", None)
        instrument_id = getattr(command, "instrument_id", None)
        reports = []
        for row in self.session.snapshot_state["orders"]:
            if not dec(row["filled_qty"]):
                continue
            ins = self.session.instruments[row["symbol"]]
            if ((venue_order_id is not None and str(venue_order_id) != row["id"])
                    or (instrument_id is not None and instrument_id != ins.id)):
                continue
            cid = row["client_order_id"]
            prior = self.seen.get(cid)
            if prior is None:
                ins, qty, filled, avg = self._normalized(row)
                prior = self._new_state(row["id"])
                sink_observation = getattr(self.session.port, "sink_observation", None)
                notional = Decimal(0)
                for execution in await self._adopted_executions(row):
                    cum = execution["cum"]
                    notional += execution["qty"] * execution["price"]
                    if sink_observation is not None:
                        # NautilusTrader 2.0.0rc5 installed contract:
                        # live/clients.py:_generate_fill_reports and model/__init__.pyi:
                        # FillReport(trade_id, last_qty, last_px), ExecutionMassStatus.add_fill_reports.
                        # Reconciliation consumes these per-execution reports; persist them
                        # through the same observation hook as activity recovery before
                        # exposing them to native reconciliation (or caching booking state).
                        average = avg if cum == filled else (notional / cum).quantize(Decimal("0.000001"))
                        status = row["status"] if cum == filled else "partially_filled"
                        result = sink_observation(dict(row, status=status, filled_qty=str(cum),
                            filled_avg_price=str(average), updated_at_ns=execution["ts"],
                            event="fill" if status == "filled" else "partial_fill",
                            execution_id=execution["trade_id"], event_qty=str(execution["qty"]),
                            event_price=str(execution["price"])))
                        if inspect.isawaitable(result):
                            await result
                    prior["executions"][execution["cum"]] = {"qty": execution["qty"], "price": execution["price"],
                                                             "trade_id": execution["trade_id"], "source": "activity",
                                                             "ts": execution["ts"]}
                    prior["trade_ids"][execution["trade_id"]] = execution["cum"]
                    prior["booked"] += execution["qty"]
                prior["accepted"], prior["broker_filled"] = True, filled
                prior["averages"][filled] = avg
                self.seen[cid] = prior
            side = OrderSide.BUY if row["side"] == "buy" else OrderSide.SELL
            for cum in sorted(prior["executions"]):
                execution = prior["executions"][cum]
                reports.append(FillReport(self.account_id, ins.id, VenueOrderId(row["id"]),
                    execution_trade_id(execution["trade_id"]), side, shares(execution["qty"]),
                    self._price(ins, execution["price"]), Money(0, USD), LiquiditySide.NO_LIQUIDITY_SIDE,
                    execution["ts"], self.clock.timestamp_ns(), client_order_id=ClientOrderId(cid)))
                self.reported_fills.add((cid, execution["trade_id"]))
        self.session.execution_stats["startup_fill_reports"] = len(self.reported_fills)
        return reports

    async def _generate_position_status_reports(self, command):
        out = []
        for row in self.session.snapshot_state["positions"]:
            qty = dec(row["qty"], signed=True)
            if not qty:
                continue
            ins = self.session.instruments[row["symbol"]]
            out.append(PositionStatusReport(self.account_id, ins.id, PositionSide.LONG if qty > 0 else PositionSide.SHORT,
                shares(abs(qty)), self.clock.timestamp_ns(), self.clock.timestamp_ns(),
                avg_px_open=dec(row["avg_entry_price"]) if row.get("avg_entry_price") else None))
        return out


def logger_config(log_directory=None):
    """Errors on stdout, as before. With ``log_directory``, NautilusTrader's own file
    writer also records INFO and above as JSON lines there (upstream FileWriterConfig,
    file_format "json"), the native live record of the engine's order and fill events."""
    if log_directory is None:
        return LoggerConfig(stdout_level=LogLevel.ERROR)
    Path(log_directory).mkdir(parents=True, exist_ok=True, mode=0o700)
    return LoggerConfig(stdout_level=LogLevel.ERROR, fileout_level=LogLevel.INFO,
                        file_config=FileWriterConfig(directory=str(log_directory), file_format="json"))


def build_node(port, symbols, strategies, *, account_id="ALPACA-PAPER", trader_id="ADAPTIVE-001",
               max_order_submit_rate="180/00:01:00", account_type=AccountType.CASH, session_policy=None,
               log_directory=None):
    if importlib.metadata.version("nautilus_trader") != "2.0.0rc5":
        raise ValueError("unqualified_native_version")
    if not account_id.startswith("ALPACA-"):
        raise ValueError("account_identity_must_be_ALPACA_scoped")
    session = NativeSession(port, symbols, session_policy=session_policy)

    class DataFactory(DataClientFactory):
        @staticmethod
        def create(*, name, config, cache, clock):
            return AlpacaDataClient(session, name=name, config=config, cache=cache, clock=clock)

    class ExecutionFactory(ExecutionClientFactory):
        @staticmethod
        def create(*, name, config, cache, clock, trader_id):
            return AlpacaExecutionClient(session, account_id, account_type, name=name, config=config,
                                         cache=cache, clock=clock, trader_id=trader_id)

    config = LiveNodeConfig(environment=Environment.SANDBOX, trader_id=TraderId(trader_id),
        load_state=False, save_state=False, shutdown_on_error=True,
        logging=logger_config(log_directory), timeout_connection_secs=10,
        timeout_reconciliation_secs=10, timeout_portfolio_secs=10, timeout_disconnection_secs=10,
        delay_post_stop_secs=0.2, timeout_shutdown_secs=10,
        risk_engine=LiveRiskEngineConfig(bypass=False, max_order_submit_rate=max_order_submit_rate,
                                         max_order_modify_rate=max_order_submit_rate),
        exec_engine=LiveExecutionEngineConfig(reconciliation=True, reconciliation_startup_delay_secs=0,
            inflight_check_interval_ms=0, open_check_interval_secs=None, position_check_interval_secs=None),
        data_clients={"ALPACA": DataClientConfig()}, exec_clients={"ALPACA": ExecutionClientConfig()})
    session.node = LiveNode.build("ALPACA-PAPER", config,
                                 data_factories={"ALPACA": DataFactory}, exec_factories={"ALPACA": ExecutionFactory})
    session.handle = session.node.handle()
    for strategy in strategies:
        session.node.add_strategy(strategy)
    return session
