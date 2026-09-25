"""NautilusTrader 2.0.0rc5 side of the engine-vs-engine cross-check.

Replays the SAME precomputed `order_stream.OrderIntent` list sim-capacity's
own `runner.run_one` would face (quotes-only L1_MBP feed, `StaticLatencyModel`,
`liquidity_consumption=True`, `queue_position=True`, `trade_execution=True` --
moot here since no TradeTick is ever added, exactly as sim-capacity's own H1
fix; see sim-capacity/README.md's H1 section), but through a strategy that
submits each intent's EXACT (symbol, side, qty, limit_price) at its EXACT
scheduled simulated time, instead of `CapacityExerciser`'s own live,
inventory-reactive decision loop -- see order_stream.py's module docstring
for why. `fee_model=None`: cost is computed post-hoc, uniformly for both
engines, by metrics.py using sim-capacity's own fee_model.commission_usd.

Requires the pinned runtime
(~/.local/share/codex-ecosystem/tools/adaptive-paper-20260921/bin/python);
imports nautilus_trader lazily inside `run_stream` so this module stays
importable (for signature/shape inspection) without it.
"""
from __future__ import annotations

import functools
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from order_stream import OrderIntent

_SIM_CAPACITY = Path(__file__).resolve().parents[1] / "sim-capacity"
if str(_SIM_CAPACITY) not in sys.path:
    sys.path.insert(0, str(_SIM_CAPACITY))

VENUE_NAME = "SIM"
CLIENT_ORDER_PREFIX = "XC-"


def _outcome_row(intent: OrderIntent, status: str, exec_qty: int, notional: Decimal, resolved_ts_ns) -> dict:
    avg_px = str((notional / exec_qty).quantize(Decimal("0.0001"))) if exec_qty > 0 else None
    return {
        "order_id": intent.order_id, "symbol": intent.symbol, "side": intent.side,
        "submit_ts_ns": intent.ts_ns, "submit_qty": intent.qty, "limit_price": intent.limit_price,
        "touch_price_at_submit": intent.touch_price, "mid_price_at_submit": intent.mid_price,
        "status": status, "exec_qty": exec_qty, "avg_exec_price": avg_px, "resolved_ts_ns": resolved_ts_ns,
    }


def run_stream(quotes_by_symbol: dict, stream: list[OrderIntent], *, latency_ms: int) -> list[dict]:
    """Run one (stream, latency) combination through a fresh BacktestEngine.
    Returns a list of outcome dicts (see metrics.py's module docstring for
    the schema), one per intent in `stream`, in intent order."""
    from nautilus_trader.backtest import BacktestEngine
    from nautilus_trader.common import LogLevel
    from nautilus_trader.config import BacktestEngineConfig, LoggerConfig, StrategyConfig
    from nautilus_trader.execution import StaticLatencyModel
    from nautilus_trader.model import (AccountType, BookType, ClientOrderId, Currency, Equity, InstrumentId,
                                        Money, OmsType, OrderSide, Price, Quantity, QuoteTick, Symbol,
                                        TimeInForce, Venue)
    from nautilus_trader.trading import Strategy

    @dataclass(frozen=True)
    class ReplayParams:
        # Plain dataclass, not a StrategyConfig subclass -- see
        # sim-capacity/exerciser.py's CapacityExerciserParams docstring for
        # why a StrategyConfig subclass silently drops constructor kwargs for
        # any field it did not already declare, on this pinned rc5 runtime.
        stream: tuple

    class ReplayExerciser(Strategy):
        def __init__(self, params: ReplayParams):
            super().__init__(StrategyConfig())
            self.params = params
            self.instruments: dict[str, InstrumentId] = {}
            self.outcomes: dict[int, dict] = {}
            self._exec_qty: dict[int, int] = {}
            self._notional: dict[int, Decimal] = {}
            self._intent_by_id: dict[int, OrderIntent] = {intent.order_id: intent for intent in params.stream}

        def on_start(self):
            symbols = sorted({intent.symbol for intent in self.params.stream})
            self.instruments = {s: InstrumentId.from_str(f"{s}.{VENUE_NAME}") for s in symbols}
            for iid in self.instruments.values():
                self.subscribe_quotes(iid)
            for intent in self.params.stream:
                self.clock.set_time_alert_ns(name=f"submit-{intent.order_id}", alert_time_ns=intent.ts_ns,
                                              callback=functools.partial(self._on_submit, intent))

        def on_stop(self):
            for order in list(self.cache.orders_open()):
                self.cancel_order(order.client_order_id)

        def _on_submit(self, intent: OrderIntent, event):
            iid = self.instruments[intent.symbol]
            order = self.order_factory.limit(
                instrument_id=iid, order_side=OrderSide.BUY if intent.side == "BUY" else OrderSide.SELL,
                quantity=Quantity.from_int(intent.qty), price=Price.from_str(intent.limit_price),
                time_in_force=TimeInForce.IOC,
                client_order_id=ClientOrderId(f"{CLIENT_ORDER_PREFIX}{intent.order_id}"))
            self.submit_order(order)

        def _order_id_of(self, client_order_id) -> int | None:
            s = str(client_order_id)
            if not s.startswith(CLIENT_ORDER_PREFIX):
                return None
            return int(s[len(CLIENT_ORDER_PREFIX):])

        def _record_fill(self, event):
            oid = self._order_id_of(event.client_order_id)
            if oid is None:
                return
            qty, px = int(event.last_qty), event.last_px.as_decimal()
            self._exec_qty[oid] = self._exec_qty.get(oid, 0) + qty
            self._notional[oid] = self._notional.get(oid, Decimal("0")) + Decimal(qty) * px
            order = self.cache.order(event.client_order_id)
            if order is not None and int(order.filled_qty) >= int(order.quantity):
                self._finalize(oid, "FILLED", int(event.ts_event))

        def _finalize(self, oid: int, terminal_kind: str, ts_event: int):
            if oid in self.outcomes:
                return
            intent = self._intent_by_id[oid]
            exec_qty = self._exec_qty.get(oid, 0)
            notional = self._notional.get(oid, Decimal("0"))
            status = terminal_kind if exec_qty == 0 else ("FILLED" if exec_qty == intent.qty else "PARTIAL")
            self.outcomes[oid] = _outcome_row(intent, status, exec_qty, notional, ts_event)

        def on_order_filled(self, event):
            self._record_fill(event)

        def on_order_canceled(self, event):
            oid = self._order_id_of(event.client_order_id)
            if oid is not None:
                self._finalize(oid, "NO_FILL", int(event.ts_event))

        def on_order_expired(self, event):
            oid = self._order_id_of(event.client_order_id)
            if oid is not None:
                self._finalize(oid, "NO_FILL", int(event.ts_event))

        def on_order_rejected(self, event):
            oid = self._order_id_of(event.client_order_id)
            if oid is not None:
                self._finalize(oid, "REJECTED", int(event.ts_event))

        def on_order_denied(self, event):
            oid = self._order_id_of(event.client_order_id)
            if oid is not None:
                self._finalize(oid, "DENIED", int(event.ts_event))

    usd, venue = Currency.from_str("USD"), Venue(VENUE_NAME)
    symbols = sorted(quotes_by_symbol)
    instruments = {}
    for symbol in symbols:
        iid = InstrumentId.from_str(f"{symbol}.{VENUE_NAME}")
        instruments[symbol] = Equity(iid, Symbol(symbol), usd, 2, Price.from_str("0.01"), 0, 0,
                                      lot_size=Quantity.from_int(1))

    ticks = []
    for symbol, rows in quotes_by_symbol.items():
        iid = instruments[symbol].id
        for row in rows:
            ticks.append(QuoteTick(iid, Price.from_str(row["bid"]), Price.from_str(row["ask"]),
                                    Quantity.from_int(row["bid_size"]), Quantity.from_int(row["ask_size"]),
                                    row["ts_ns"], row["ts_ns"]))
    ticks.sort(key=lambda t: t.ts_event)

    engine_cfg = BacktestEngineConfig(logging=LoggerConfig(stdout_level=LogLevel.ERROR))
    engine = BacktestEngine(engine_cfg)
    latency_model = StaticLatencyModel(base_latency_nanos=int(latency_ms * 1_000_000)) if latency_ms else None
    try:
        engine.add_venue(venue, OmsType.NETTING, AccountType.CASH, [Money(Decimal("10000000"), usd)],
                          base_currency=usd, fee_model=None, latency_model=latency_model,
                          book_type=BookType.L1_MBP, trade_execution=True, liquidity_consumption=True,
                          queue_position=True)
        for instrument in instruments.values():
            engine.add_instrument(instrument)
        engine.add_data(ticks)
        strategy = ReplayExerciser(ReplayParams(stream=tuple(stream)))
        engine.add_strategy(strategy)
        engine.run()

        # Any intent with no terminal event at all by the end of the run
        # (should not happen for an IOC-only stream, but recorded rather than
        # silently dropped if it ever does).
        for intent in stream:
            if intent.order_id not in strategy.outcomes:
                strategy.outcomes[intent.order_id] = _outcome_row(intent, "UNRESOLVED", 0, Decimal("0"), None)
        return [strategy.outcomes[intent.order_id] for intent in stream]
    finally:
        engine.dispose()
