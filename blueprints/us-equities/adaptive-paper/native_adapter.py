"""Native Nautilus v2 LiveNode glue; injected port owns broker I/O and risk.

No credentials or Alpaca client live in this module. Native events reflect port
confirmations, never locally simulated broker acceptance. Whole-share USD equity
limit/DAY orders only; unknown submission outcomes freeze and stop the node.
"""
from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime, timezone
from decimal import Decimal
import importlib.metadata
from pathlib import Path
import re
import sys
from typing import Protocol, Callable

# This module is sometimes loaded directly via importlib file-spec (see
# tests/test_adaptive_paper_native.py) without its own directory on
# sys.path; self-heal so the local sessions.py sibling import below resolves
# regardless of how the caller imported this module.
_HERE = str(Path(__file__).resolve().parent)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
from sessions import DEFAULT_SESSION_POLICY, order_extended_hours_flag, reconciliation_receipt

from nautilus_trader.common import Environment, LogLevel
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


def error_code(error):
    message = str(error)
    return message if isinstance(error, ValueError) and re.fullmatch(r"[a-z_]+", message) else type(error).__name__


class BrokerPort(Protocol):
    async def start(self, on_quote: Callable[[dict], None], on_order: Callable[[dict], None]) -> None: ...
    async def stop(self) -> None: ...
    async def submit(self, order: dict) -> dict: ...
    async def cancel(self, client_order_id: str) -> dict | None: ...
    async def snapshot(self) -> dict: ...


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


def quote_components(row):
    """Validate native price/size capacity without constructing a QuoteTick."""
    bid, ask = dec(row["bid"]), dec(row["ask"])
    precision = max(0, -bid.as_tuple().exponent, -ask.as_tuple().exponent)
    if precision > 16:
        raise ValueError("quote_precision_unsupported")
    return (Price.from_str(format(bid, f".{precision}f")), Price.from_str(format(ask, f".{precision}f")),
            shares(row["bid_size"]), shares(row["ask_size"]))


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
        self.quote_tombstones = {}
        self.observations = []
        self.unresolved_orders = {}
        self.snapshot_state = None
        self.session_policy = dict(session_policy) if session_policy else dict(DEFAULT_SESSION_POLICY)
        self.reconciliation = None
        self.fee_assumption = "Port has no fees; native booking uses zero commission pending external fee reconciliation."

    def fail(self, code):
        self.errors.append(str(code))
        if self.handle is not None and self.handle.is_running:
            self.handle.stop()

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
                await self.port.stop()
                self.stopped = True

    def on_quote(self, row):
        try:
            sym = row["symbol"]
            if type(row["ts_ns"]) is not int or row["ts_ns"] <= 0:
                raise ValueError("invalid_quote")
            if row["ts_ns"] <= self.quote_tombstones.get(sym, 0):
                return
            ins = self.instruments[sym]
            bid, ask = dec(row["bid"]), dec(row["ask"])
            if bid <= 0 or ask < bid:
                raise ValueError("invalid_quote")
            q = QuoteTick(ins.id, *quote_components(row), row["ts_ns"],
                          self.data.clock.timestamp_ns())
            previous = self.quotes.get(sym)
            if previous is not None and q.ts_event < previous.ts_event:
                return
            self.quotes[sym] = q
            if sym in self.data.subscriptions:
                self.data._handle_data(q)
        except Exception as error:
            self.fail("quote_" + error_code(error))

    def invalidate_quote(self, symbol, ts_ns):
        previous = self.quotes.get(symbol)
        if previous is None or ts_ns >= previous.ts_event:
            self.quote_tombstones[symbol] = max(ts_ns, self.quote_tombstones.get(symbol, 0))
            self.quotes.pop(symbol, None)

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


def fill_trade_id(broker_order_id, cumulative_qty):
    """Reviewed 1c3ccba5: stable native ID within its 36-character limit."""
    return TradeId(hashlib.sha256(f"{broker_order_id}:cum:{cumulative_qty}".encode()).hexdigest()[:36])


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

    def observe(self, row):
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
        prior = self.seen.get(cid, {"qty": Decimal(0), "value": Decimal(0), "accepted": False, "terminal": None, "id": row["id"]})
        if prior["id"] != row["id"]:
            raise ValueError("broker_order_identity_changed")
        if filled < prior["qty"]:
            return  # A delayed cumulative snapshot must never roll back fills.
        value = filled * avg
        if filled == prior["qty"] and value != prior["value"]:
            raise ValueError("same_quantity_fill_correction_requires_reconciliation")
        if prior["terminal"] and filled > prior["qty"]:
            raise ValueError("post_terminal_fill_requires_reconciliation")
        broker_id, stamp = VenueOrderId(row["id"]), row["updated_at_ns"]
        if status != "rejected" and status != "pending_new" and not prior["accepted"]:
            self.generate_order_accepted(order, broker_id, stamp)
            prior["accepted"] = True
        if filled > prior["qty"]:
            delta = filled - prior["qty"]
            last_px = (value - prior["value"]) / delta
            if last_px <= 0 or last_px != last_px.quantize(Decimal(1).scaleb(-ins.price_precision)):
                raise ValueError("cumulative_fill_precision_requires_reconciliation")
            self.generate_order_filled(order, broker_id, None,
                fill_trade_id(row["id"], filled), shares(delta), Price.from_str(str(last_px)),
                USD, Money(0, USD), LiquiditySide.NO_LIQUIDITY_SIDE, stamp)
            prior["qty"], prior["value"] = filled, value
        if not prior["terminal"]:
            if status == "canceled":
                self.generate_order_canceled(order, broker_id, stamp)
                prior["terminal"] = status
            elif status == "expired":
                self.generate_order_expired(order, broker_id, stamp)
                prior["terminal"] = status
            elif status == "rejected":
                self.generate_order_rejected(order, str(row.get("reason", "broker_rejected")), stamp, False)
                prior["terminal"] = status
            elif status == "filled":
                if filled != qty:
                    raise ValueError("filled_status_quantity_mismatch")
                prior["terminal"] = status
        self.seen[cid] = prior
        self.session.observations.append({"client_order_id": cid, "status": status, "filled_qty": str(filled)})

    def order_report(self, row):
        ins, qty, filled, avg = self._normalized(row)
        return OrderStatusReport(self.account_id, ins.id, VenueOrderId(row["id"]),
            OrderSide.BUY if row["side"] == "buy" else OrderSide.SELL, OrderType.LIMIT, TimeInForce.DAY,
            STATUSES[row["status"]], shares(qty), shares(filled), row["updated_at_ns"], row["updated_at_ns"],
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

    async def _generate_fill_reports(self, command):
        # The supplied port has cumulative quantities, not an execution ledger.
        # Nonzero startup fills cannot honestly be fabricated as individual fills.
        if any(dec(row["filled_qty"]) > 0 for row in self.session.snapshot_state["orders"]):
            raise ValueError("historical_fill_ledger_not_supplied_by_port")
        return []

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


def build_node(port, symbols, strategies, *, account_id="ALPACA-PAPER", trader_id="ADAPTIVE-001",
               max_order_submit_rate="180/00:01:00", account_type=AccountType.CASH, session_policy=None):
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
        logging=LoggerConfig(stdout_level=LogLevel.ERROR), timeout_connection_secs=10,
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
