"""One native strategy owns the shared portfolio across policy families."""
from __future__ import annotations

import time
from decimal import Decimal
from nautilus_trader.trading import Strategy
from nautilus_trader.config import StrategyConfig
from nautilus_trader.model import (ClientOrderId, InstrumentId, OrderSide, Price,
                                  Quantity, StrategyId, TimeInForce)
from strategies import AdaptivePolicy, limit_price


class AdaptiveStrategy(Strategy):
    def __new__(cls, policy, ledger, trial_id, **kwargs):
        return super().__new__(cls, StrategyConfig(strategy_id=StrategyId("ADAPTIVE-001"),
                                order_id_tag="A", log_events=False, log_commands=False, manage_stop=False))

    def __init__(self, policy: AdaptivePolicy, ledger, trial_id: str, *, event_sink=None):
        self.policy = policy
        self.ledger = ledger
        self.trial_id = trial_id
        self.event_sink = event_sink or (lambda event: None)
        self.pending = {}
        prefix = f"adp-{trial_id}-"
        self.sequence = max((int(i.client_id[len(prefix):]) for i in ledger.intents()
                             if i.client_id.startswith(prefix) and i.client_id[len(prefix):].isdigit()), default=0)
        self.native_fills = 0
        self.native_rejections = 0
        self.received_quotes = 0
        self.started = False
        self.enabled = False

    def on_start(self):
        for symbol in self.policy.config.symbols:
            self.subscribe_quotes(InstrumentId.from_str(symbol + ".ALPACA"))
        self.started = True

    def on_quote(self, quote):
        symbol = str(quote.instrument_id).rsplit(".", 1)[0]
        if self.policy.observe(symbol, float(str(quote.bid_price)), float(str(quote.ask_price)),
                               quote.ts_event / 1_000_000_000):
            self.received_quotes += 1

    def on_order_filled(self, event):
        self.native_fills += 1
        self._finish_if_terminal(str(event.client_order_id))

    def on_order_canceled(self, event):
        self.pending.pop(str(event.client_order_id), None)

    def on_order_expired(self, event):
        self.pending.pop(str(event.client_order_id), None)

    def on_order_rejected(self, event):
        self.native_rejections += 1
        if str(event.reason).startswith("broker definitively rejected"):
            self.ledger.freeze("broker_refusal_needs_reconciliation")
        else:
            self._mark_definitive_refusal(str(event.client_order_id))
        self.pending.pop(str(event.client_order_id), None)

    def on_order_denied(self, event):
        self.native_rejections += 1
        self._mark_definitive_refusal(str(event.client_order_id))
        self.pending.pop(str(event.client_order_id), None)

    def _mark_definitive_refusal(self, client_id):
        intent = next((i for i in self.ledger.intents() if i.client_id == client_id), None)
        if intent and intent.broker_id is None and intent.filled_qty == 0:
            self.ledger.mark_not_sent(client_id, "native_definitive_refusal")

    def _finish_if_terminal(self, client_id):
        intent = next((i for i in self.ledger.intents() if i.client_id == client_id), None)
        if intent and intent.terminal:
            self.pending.pop(client_id, None)

    def positions(self):
        return {p.symbol: {"qty": str(p.qty), "avg_entry_price": str(p.average_cost)}
                for p in self.ledger.positions().values() if p.qty}

    def rebalance(self, now=None, *, force_exit=False):
        """Called on the native owner loop, never a socket thread."""
        now = time.time() if now is None else now
        self.policy.sync_positions(self.positions(), now)
        for client_id in list(self.pending):
            self._finish_if_terminal(client_id)
        decision = self.policy.decide(now, allow_entries=self.enabled, force_exit=force_exit)
        if decision is None or not self.started:
            return None
        self.event_sink({"type": "decision", "timestamp": now, "regime": decision.regime,
                         "targets": decision.targets, "exits": decision.exits,
                         "effective_leverage": decision.effective_leverage,
                         "signals": [{"symbol": s.symbol, "family": s.family,
                                      "edge_bps": s.edge_bps, "score": s.score} for s in decision.signals]})
        held = {s: Decimal(p["qty"]) for s, p in self.positions().items()}
        busy = {i.symbol for i in self.ledger.unresolved()}
        busy.update(item["symbol"] for item in self.pending.values())
        # Exits consume capacity before fresh entries; one outstanding order per
        # symbol also prevents sell-before-entry-terminal and oversell races.
        actions = [(s, "sell", qty - decision.targets.get(s, 0), decision.exits.get(s, "rebalance"))
                   for s, qty in held.items() if qty > decision.targets.get(s, 0)]
        if self.enabled and not force_exit:
            actions += [(s, "buy", qty - held.get(s, 0),
                         next((x.family for x in decision.signals if x.symbol == s), "rebalance"))
                        for s, qty in decision.targets.items() if qty > held.get(s, 0)]
        for symbol, side, quantity, reason in actions:
            quote = self.policy.latest.get(symbol)
            if (symbol in busy or not quote or now - quote.timestamp > self.policy.config.quote_age_seconds
                    or now < quote.timestamp - .25):
                continue
            self.sequence += 1
            client_id = f"adp-{self.trial_id}-{self.sequence:07d}"
            order = self.order_factory.limit(
                InstrumentId.from_str(symbol + ".ALPACA"),
                OrderSide.BUY if side == "buy" else OrderSide.SELL,
                Quantity.from_str(str(min(quantity, self.policy.config.max_shares))),
                Price.from_str(limit_price(quote.bid, quote.ask, side)),
                time_in_force=TimeInForce.DAY, client_order_id=ClientOrderId(client_id),
                tags=[f"strategy={reason}", f"reason={reason}"])
            self.pending[client_id] = {"symbol": symbol, "side": side, "created": now}
            busy.add(symbol)
            self.submit_order(order)
        return decision

    def cancel_expired(self, now, timeout, *, all_entries=False):
        for client_id, info in list(self.pending.items()):
            if info.get("cancel_requested"):
                continue
            if now - info["created"] >= timeout or (all_entries and info["side"] == "buy"):
                self.cancel_order(ClientOrderId(client_id))
                info["cancel_requested"] = True
