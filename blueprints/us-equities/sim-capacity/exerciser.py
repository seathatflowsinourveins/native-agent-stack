"""CapacityExerciser -- NOT A STRATEGY. It carries no signal, forecast or edge:
it round-robins a fixed symbol list on a clock-timer schedule and submits
marketable LIMIT IOC orders (buy at ask+collar, sell at bid-collar) purely to
load the venue/risk-engine pipeline, alternating side per symbol to stay near
flat inventory under a hard per-symbol position cap, and flattening at the end.
Its only purpose is to measure sustained fills/minute under a native rate
limiter and realistic latency/fee/queue models -- infrastructure evidence
(`evidence_class: sim_capacity_infrastructure`), never strategy evidence. No
order here reacts to price direction, volatility, news or any other signal.
"""
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

from nautilus_trader.model import ClientOrderId, InstrumentId, OrderSide, Price, Quantity, TimeInForce
from nautilus_trader.config import StrategyConfig
from nautilus_trader.trading import Strategy

from schedule import RoundRobin, tick_interval_ns

RATE_LIMIT_REASON_MARKERS = ("RATE_LIMIT", "rate limit", "RiskEngine", "throttle")


@dataclass(frozen=True)
class CapacityExerciserParams:
    """Plain-Python parameter object for `CapacityExerciser`.

    Not a `nautilus_trader.config.StrategyConfig` subclass: on the pinned
    2.0.0rc5 runtime, `StrategyConfig`'s constructor is a Rust-backed `__new__`
    that only recognizes the base class's own predeclared fields -- a pure
    Python subclass that adds new annotated fields silently keeps each field's
    class-level default forever, ignoring any constructor keyword for it (this
    was verified directly on the pinned runtime: `class C(StrategyConfig):
    foo: int = 1` then `C(foo=99).foo` reads `1`, not `99`). A plain dataclass,
    passed alongside a bare default `StrategyConfig()` (matching
    sim-paper-compare/replay_compare.py's `ScheduledReplay` pattern), avoids
    that trap entirely."""
    symbols: tuple[str, ...]
    venue: str = "SIM"
    submits_per_sec: float = 3.0
    position_cap: int = 10
    qty_min: int = 1
    qty_max: int = 3
    collar: str = "0.01"
    run_seconds: float = 1800.0
    flatten_buffer_seconds: float = 5.0

    def __post_init__(self):
        if not self.symbols:
            raise ValueError("CapacityExerciserParams.symbols must be non-empty")


class CapacityExerciser(Strategy):
    def __init__(self, params: CapacityExerciserParams):
        super().__init__(StrategyConfig())
        self.params = params
        self.instruments: dict[str, InstrumentId] = {}
        self.rr: RoundRobin | None = None
        self.counters: dict[str, int] = defaultdict(int)
        self.events: list[dict] = []  # {"ts_ns", "kind", "symbol", ...}
        self.filled_qty = 0
        self.filled_notional = Decimal("0")
        self._order_side = {}  # client_order_id -> side, for on_order_filled bookkeeping
        self._client_order_seq = 0

    # -- lifecycle ---------------------------------------------------------
    def on_start(self):
        self.instruments = {s: InstrumentId.from_str(f"{s}.{self.params.venue}") for s in self.params.symbols}
        for iid in self.instruments.values():
            self.subscribe_quotes(iid)
        self.rr = RoundRobin(list(self.params.symbols), self.params.position_cap)
        interval_ns = tick_interval_ns(self.params.submits_per_sec)
        start_ns = self.clock.timestamp_ns()
        run_ns = int(self.params.run_seconds * 1_000_000_000)
        buffer_ns = int(self.params.flatten_buffer_seconds * 1_000_000_000)
        # The exerciser ticks for the *entire* analysis window (no throughput
        # eaten by a pre-flatten quiet period): `stop_ns` is exactly
        # start + run_seconds, so every one of the analysis window's full
        # minutes gets its full submit schedule. Flattening instead happens
        # `flatten_buffer_seconds` *after* that (in the caller-provided data
        # pad beyond the analysis window), which both lets the shared
        # rate-limit budget refill before the close orders need it, and keeps
        # the flatten's own market activity out of the counted minutes.
        stop_ns = start_ns + run_ns
        self._window_start_ns = start_ns
        self.clock.set_timer_ns(name="capacity-tick", interval_ns=interval_ns,
                                 start_time_ns=start_ns + interval_ns, stop_time_ns=stop_ns,
                                 callback=self._on_tick)
        # A single flatten attempt can transiently fail per-instrument (measured
        # directly: an OrderRejected "No market for <symbol>" when a close
        # order is processed at an instant with no book update yet for that
        # instrument) with no automatic retry, leaving a real leftover
        # position. Several spaced retry attempts, each re-checking
        # `positions_open`, cover this without assuming the exact instant a
        # book briefly lacks a quote.
        for i, delay_s in enumerate((0.0, 5.0, 15.0, 30.0)):
            self.clock.set_time_alert_ns(name=f"capacity-flatten-{i}",
                                          alert_time_ns=stop_ns + buffer_ns + int(delay_s * 1_000_000_000),
                                          callback=self._on_flatten)

    def on_stop(self):
        for order in list(self.cache.orders_open()):
            self.cancel_order(order.client_order_id)

    # -- scheduled behavior --------------------------------------------------
    def _next_client_order_id(self) -> ClientOrderId:
        self._client_order_seq += 1
        return ClientOrderId(f"CAP-{self._client_order_seq}")

    def _on_tick(self, event):
        symbol = self.rr.next_symbol()
        iid = self.instruments[symbol]
        quote = self.cache.quote(iid)
        if quote is None:
            self.counters["skipped_no_quote"] += 1
            return
        position = int(self.portfolio.net_position(iid))
        side = self.rr.next_side(symbol, position)
        if side is None:
            self.counters["skipped_position_cap"] += 1
            return
        collar = Decimal(self.params.collar)
        if side == "BUY":
            limit_price = Price(quote.ask_price.as_decimal() + collar, quote.ask_price.precision)
            available = int(quote.ask_size)
        else:
            limit_price = Price(max(quote.bid_price.as_decimal() - collar, Decimal("0.01")), quote.bid_price.precision)
            available = int(quote.bid_size)
        qty = max(self.params.qty_min, min(self.params.qty_max, available))
        if qty <= 0:
            self.counters["skipped_no_size"] += 1
            return
        client_order_id = self._next_client_order_id()
        order = self.order_factory.limit(instrument_id=iid, order_side=OrderSide.BUY if side == "BUY" else OrderSide.SELL,
                                          quantity=Quantity.from_int(qty), price=limit_price,
                                          time_in_force=TimeInForce.IOC, client_order_id=client_order_id)
        self._order_side[str(client_order_id)] = side
        self.counters["submits"] += 1
        self.events.append({"ts_ns": self.clock.timestamp_ns(), "kind": "submit", "symbol": symbol,
                             "side": side, "qty": qty, "client_order_id": str(client_order_id),
                             "limit_price": str(limit_price.as_decimal())})
        self.submit_order(order)

    def _on_flatten(self, event):
        self.counters["flatten_started"] += 1
        for iid in self.instruments.values():
            for position in self.cache.positions_open(instrument_id=iid):
                self.counters["flatten_orders"] += 1
                self.close_position(position)

    # -- order/fill event hooks --------------------------------------------
    def on_order_filled(self, event):
        self.counters["fills"] += 1
        self.counters["filled_orders_seen"] += 1  # counted per fill event; distinct-order dedup done at receipt time
        qty = int(event.last_qty)
        px = event.last_px.as_decimal()
        side = "SELL" if event.is_sell else "BUY"
        fee = event.commission.as_decimal() if event.commission is not None else Decimal("0")
        quote = self.cache.quote(event.instrument_id)
        mid = ((quote.bid_price.as_decimal() + quote.ask_price.as_decimal()) / 2) if quote is not None else None
        self.filled_qty += qty
        self.filled_notional += Decimal(qty) * px
        self.events.append({"ts_ns": int(event.ts_event), "kind": "fill",
                             "client_order_id": str(event.client_order_id), "qty": qty, "price": str(px),
                             "side": side, "fee_usd": str(fee), "instrument_id": str(event.instrument_id),
                             "mid_at_fill": str(mid) if mid is not None else None})

    def on_order_rejected(self, event):
        reason = str(getattr(event, "reason", ""))
        if any(marker.lower() in reason.lower() for marker in RATE_LIMIT_REASON_MARKERS):
            self.counters["rate_limit_denied"] += 1
        else:
            self.counters["rejects"] += 1
        self.events.append({"ts_ns": int(event.ts_event), "kind": "reject", "reason": reason})

    def on_order_denied(self, event):
        # The RiskEngine's max_order_submit_rate denies *before* the venue ever
        # sees the order (a client-side/pre-trade denial, distinct from
        # OrderRejected which is the venue's own decision) -- this is where a
        # RATE_LIMIT budget breach actually surfaces in this engine.
        reason = str(getattr(event, "reason", ""))
        self.counters["rate_limit_denied"] += 1
        self.events.append({"ts_ns": int(event.ts_event), "kind": "denied", "reason": reason})

    def on_order_canceled(self, event):
        # This strategy only submits IOC orders and never cancels one itself
        # outside on_stop's open-order sweep; a cancel seen during the run is
        # the matching engine's own auto-cancel of an IOC order's unfilled
        # remainder, i.e. an "IOC expiry" in this exerciser's counting scheme.
        self.counters["ioc_expiries"] += 1
        self.events.append({"ts_ns": int(event.ts_event), "kind": "ioc_expiry",
                             "client_order_id": str(event.client_order_id)})

    def on_order_expired(self, event):
        self.counters["ioc_expiries"] += 1
        self.events.append({"ts_ns": int(event.ts_event), "kind": "ioc_expiry",
                             "client_order_id": str(event.client_order_id)})
