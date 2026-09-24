"""Native NautilusTrader strategy shell for the mover trial mode.

All entry, exit and flatten decisions live in ``mover.MoverBook`` (pure and tested
without NautilusTrader). This shell subscribes quotes, turns the book's actions into
native limit/DAY orders, and feeds native order events back into the book. Orders
leave through the same adapter, controller and ledger path as ``AdaptiveStrategy``;
the ledger stays the source of truth for positions and terminal order states.
"""
from __future__ import annotations

from decimal import Decimal
import time

from nautilus_trader.config import StrategyConfig
from nautilus_trader.model import ClientOrderId, InstrumentId, OrderSide, Price, Quantity, StrategyId, TimeInForce
from nautilus_trader.trading import Strategy

from mover import broker_ref, price_text


class MoverStrategy(Strategy):
    def __new__(cls, book, ledger, **kwargs):
        return super().__new__(cls, StrategyConfig(strategy_id=StrategyId("MOVER-001"), order_id_tag="M",
                                                   log_events=False, log_commands=False, manage_stop=False))

    def __init__(self, book, ledger, *, clock=time.time):
        self.book = book
        self.ledger = ledger
        self._clock = clock
        self.started = False
        self.enabled = False
        # Set by the runner while a reconciliation snapshot is in flight: no order may be
        # sent then, or the snapshot could miss it (AdaptiveStrategy only sends from the
        # runner's own tick, so it never needed this).
        self.suspended = False
        self.native_fills = 0
        self.native_rejections = 0
        self.received_quotes = 0
        self.submitted = 0

    def on_start(self):
        for symbol in self.book.plan.symbol_names():
            self.subscribe_quotes(InstrumentId.from_str(symbol + ".ALPACA"))
        self.started = True

    def on_quote(self, quote):
        self.received_quotes += 1
        if not self.started or self.suspended:
            return
        symbol = str(quote.instrument_id).rsplit(".", 1)[0]
        leg = self.book.legs.get(symbol)
        if leg is not None and leg.state not in ("skipped", "no_fill", "closed"):
            # Exits (and a waiting entry) are evaluated on every quote update; the
            # runner's tick still sweeps every leg, including resolved ones.
            self._execute(self.book.evaluate(self._clock(), entries_enabled=self.enabled, symbols=(symbol,)))

    def tick(self, now, *, force_reason=None):
        """Owner-loop tick from the runner: latch a force reason, resync terminal order
        states from the ledger, then evaluate every symbol (timeouts, flatten)."""
        if force_reason:
            self.book.set_force(force_reason, now)
        self._sync_terminal()
        self._execute(self.book.evaluate(now, entries_enabled=self.enabled))

    @property
    def pending(self):
        return {record.client_id: record for record in self.book.open_orders()}

    def _sync_terminal(self):
        open_ids = {record.client_id for record in self.book.open_orders()}
        if not open_ids:
            return
        for intent in self.ledger.intents():
            if intent.client_id in open_ids and intent.terminal:
                self.book.on_terminal(intent.client_id, intent.status)

    def _execute(self, actions):
        for action in actions:
            if action.kind == "cancel":
                self.cancel_order(ClientOrderId(action.client_id))
                continue
            record = action.record
            order = self.order_factory.limit(
                InstrumentId.from_str(record.symbol + ".ALPACA"),
                OrderSide.BUY if record.side == "buy" else OrderSide.SELL,
                Quantity.from_int(int(record.qty)), Price.from_str(price_text(record.limit_price)),
                time_in_force=TimeInForce.DAY, client_order_id=ClientOrderId(record.client_id),
                tags=["strategy=mover", f"reason={record.reason}", f"exit_rule={self.book.plan.exit_rule}"])
            self.submitted += 1
            self.submit_order(order)

    # -- native order events ------------------------------------------------
    def on_order_accepted(self, event):
        self.book.on_accepted(str(event.client_order_id), event.ts_event / 1e9, broker_ref(event.venue_order_id))

    def on_order_filled(self, event):
        self.native_fills += 1
        client_id = str(event.client_order_id)
        self.book.on_fill(client_id, event.ts_event / 1e9, Decimal(str(event.last_qty)), Decimal(str(event.last_px)),
                          broker_ref(event.venue_order_id))
        intent = next((i for i in self.ledger.intents() if i.client_id == client_id), None)
        if intent is not None and intent.terminal:
            self.book.on_terminal(client_id, intent.status)

    def on_order_canceled(self, event):
        self.book.on_terminal(str(event.client_order_id), "canceled")

    def on_order_expired(self, event):
        self.book.on_terminal(str(event.client_order_id), "expired")

    def on_order_rejected(self, event):
        self.native_rejections += 1
        client_id = str(event.client_order_id)
        reason = str(event.reason)
        if reason.startswith("broker definitively rejected"):
            self.ledger.freeze("broker_refusal_needs_reconciliation")
        else:
            self._mark_definitive_refusal(client_id)
        self.book.on_terminal(client_id, "rejected", reason)

    def on_order_denied(self, event):
        self.native_rejections += 1
        client_id = str(event.client_order_id)
        self._mark_definitive_refusal(client_id)
        self.book.on_terminal(client_id, "denied", str(event.reason))

    def on_order_cancel_rejected(self, event):
        self.book.on_cancel_rejected(str(event.client_order_id))

    def _mark_definitive_refusal(self, client_id):
        intent = next((i for i in self.ledger.intents() if i.client_id == client_id), None)
        if intent and intent.broker_id is None and intent.filled_qty == 0 and intent.status == "reserved":
            self.ledger.mark_not_sent(client_id, "native_definitive_refusal")
