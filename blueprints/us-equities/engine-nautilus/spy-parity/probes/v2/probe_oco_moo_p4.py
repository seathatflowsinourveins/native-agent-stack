"""Engine-semantics probe (SYNTHETIC bars; not SPY data, not a parity run).

Question: on nautilus_trader 2.0.0rc5, does a native OCO pair of STOP_MARKET and
MARKET_IF_TOUCHED orders, both triggered one price increment either side of the
decision bar's close and submitted from that bar's on_bar callback, fill at the
NEXT bar's open, at the next bar's ts_event, exactly once, for BUY and for SELL,
at the parity harness's instrument shape (price precision 4, increment 0.0001,
integer shares, 304-share order against a large bar volume)?

Cases vary the next bar's open relative to the decision close C = 100.0000:
  gap_up          open 101.0000   (open > C + tick)
  gap_down        open  99.0000   (open < C - tick)
  one_tick_up     open 100.0001   (open == C + tick: the stop trigger itself)
  one_tick_down   open  99.9999   (open == C - tick)
  no_gap          open 100.0000   (open strictly between the triggers)
  no_gap_flat     open=high=low=close=100.0000 (nothing moves)
A later bar (open 105.0000) follows the tested bar so an order that survives the
tested bar is observed filling in the wrong bar rather than disappearing.

Usage: probe_oco_moo_p4.py [default|adaptive] [shift220]
  argv[1]: bar_adaptive_high_low_ordering off (default) or on (adaptive)
  argv[2]: shift220 adds 220.0000 to every synthetic price (decision close 320.0000),
           so each 304-share leg is near full allocation of the 100,000 USD CASH
           account and the two resting BUY legs together exceed it (tests whether the
           pinned risk engine or balance locking denies the second leg).
Prints one JSON document. Nothing is filtered.
"""
import json
import sys
from decimal import Decimal

from nautilus_trader.backtest import BacktestEngine
from nautilus_trader.common import LogLevel
from nautilus_trader.config import BacktestEngineConfig, LoggerConfig, StrategyConfig
from nautilus_trader.core import UUID4
from nautilus_trader.model import (AccountType, Bar, BarType, ClientOrderId, ContingencyType, Currency,
                                   Equity, InstrumentId, MarketIfTouchedOrder, Money, OmsType, OrderListId,
                                   OrderSide, Price, Quantity, StopMarketOrder, Symbol, TimeInForce,
                                   TriggerType, Venue)
from nautilus_trader.trading import Strategy

BASE, STEP = 1_600_000_000_000_000_000, 3_600_000_000_000
TICK = Decimal("0.0001")
QTY = 304
VOLUME = 4_000_000
DECISION = ("99.8000", "100.2000", "99.7000", "100.0000")  # close C = 100.0000
CASES = {
    "gap_up": ("101.0000", "101.5000", "100.8000", "101.2000"),
    "gap_down": ("99.0000", "99.2000", "98.5000", "98.8000"),
    "one_tick_up": ("100.0001", "100.5000", "99.5000", "100.2000"),
    "one_tick_down": ("99.9999", "100.5000", "99.5000", "100.2000"),
    "no_gap": ("100.0000", "100.5000", "99.5000", "100.2000"),
    "no_gap_flat": ("100.0000", "100.0000", "100.0000", "100.0000"),
}
LATER = ("105.0000", "105.5000", "104.5000", "105.2000")
ADAPT = len(sys.argv) > 1 and sys.argv[1] == "adaptive"
SHIFT = Decimal("220.0000") if len(sys.argv) > 2 and sys.argv[2] == "shift220" else Decimal("0")


def px(x):
    return Price.from_str(f"{Decimal(x) + SHIFT:.4f}")


def run(name, side):
    usd, venue = Currency.from_str("USD"), Venue("SIM")
    eq = Equity(InstrumentId.from_str("SPY.SIM"), Symbol("SPY"), usd, 4, Price.from_str("0.0001"), 0, 0,
                lot_size=Quantity.from_int(1))
    bt = BarType.from_str("SPY.SIM-1-HOUR-LAST-EXTERNAL")
    # bar 0: setup (a SELL case buys QTY at its close so it has shares to sell)
    # bar 1: decision bar (OCO pair submitted from its on_bar)
    # bar 2: tested bar ("next session's first bar")
    # bar 3: later bar
    specs = [("99.9000", "100.1000", "99.8000", "99.9000"), DECISION, CASES[name], LATER]
    bars = [Bar(bt, *[px(x) for x in s], Quantity.from_int(VOLUME), BASE + i * STEP, BASE + i * STEP)
            for i, s in enumerate(specs)]
    order_side = OrderSide.BUY if side == "BUY" else OrderSide.SELL

    class P(Strategy):
        def __init__(self):
            super().__init__(StrategyConfig())
            self.i, self.ev, self.ids, self.errors = -1, [], {}, []

        def on_start(self):
            self.subscribe_bars(bt)

        def on_bar(self, bar):
            try:
                self._on_bar(bar)
            except BaseException as exc:  # the engine only logs callback errors; surface them
                self.errors.append(repr(exc))

        def _on_bar(self, bar):
            self.i += 1
            if self.i == 0 and side == "SELL":
                o = self.order_factory.market(eq.id, OrderSide.BUY, Quantity.from_int(QTY))
                self.ids[o.client_order_id] = "setup_buy"
                self.submit_order(o)
            if self.i != 1:
                return
            c = bar.close.as_decimal()
            # BUY: stop above close, MIT below. SELL: stop below close, MIT above.
            stop_px = c + TICK if side == "BUY" else c - TICK
            mit_px = c - TICK if side == "BUY" else c + TICK
            sid, mid, lid = ClientOrderId("O-STOP"), ClientOrderId("O-MIT"), OrderListId("OL-1")
            ts = self.clock.timestamp_ns()
            common = dict(trader_id=self.trader_id, strategy_id=self.strategy_id, instrument_id=eq.id,
                          order_side=order_side, quantity=Quantity.from_int(QTY),
                          trigger_type=TriggerType.DEFAULT, time_in_force=TimeInForce.GTC,
                          reduce_only=False, quote_quantity=False, ts_init=ts,
                          contingency_type=ContingencyType.OCO, order_list_id=lid)
            so = StopMarketOrder(client_order_id=sid, trigger_price=Price.from_str(f"{stop_px:.4f}"),
                                 init_id=UUID4(), linked_order_ids=[mid], **common)
            mo = MarketIfTouchedOrder(client_order_id=mid, trigger_price=Price.from_str(f"{mit_px:.4f}"),
                                      init_id=UUID4(), linked_order_ids=[sid], **common)
            self.ids[sid], self.ids[mid] = "stop", "mit"
            self.triggers = {"stop": f"{stop_px:.4f}", "mit": f"{mit_px:.4f}"}
            self.submit_order(so)
            self.submit_order(mo)

        def on_order_event(self, e):
            t = type(e).__name__
            if t not in ("OrderFilled", "OrderTriggered", "OrderCanceled", "OrderRejected", "OrderDenied",
                         "OrderAccepted"):
                return
            rec = {"event": t, "order": self.ids.get(e.client_order_id), "ts_event": e.ts_event,
                   "bar_index_at_ts": (e.ts_event - BASE) // STEP if (e.ts_event - BASE) % STEP == 0 else None}
            if t == "OrderFilled":
                rec["last_px"] = str(e.last_px)
                rec["last_qty"] = str(e.last_qty)
            if t in ("OrderRejected", "OrderCanceled", "OrderDenied"):
                rec["reason"] = str(getattr(e, "reason", "") or "")
            self.ev.append(rec)

    eng = BacktestEngine(BacktestEngineConfig(logging=LoggerConfig(stdout_level=LogLevel.ERROR)))
    try:
        eng.add_venue(venue, OmsType.NETTING, AccountType.CASH, [Money(Decimal("100000"), usd)], base_currency=usd,
                      use_random_ids=False, bar_adaptive_high_low_ordering=ADAPT)
        eng.add_instrument(eq)
        eng.add_data(bars)
        p = P()
        eng.add_strategy(p)
        eng.run()
        oco_fills = [e for e in p.ev if e["event"] == "OrderFilled" and e["order"] in ("stop", "mit")]
        tested_ts = BASE + 2 * STEP
        tested_open = CASES[name][0]
        verdict = {
            "oco_fill_count": len(oco_fills),
            "single_fill_in_tested_bar": len(oco_fills) == 1 and oco_fills[0]["ts_event"] == tested_ts,
            "fill_px_equals_tested_open": len(oco_fills) == 1 and Decimal(oco_fills[0]["last_px"]) == Decimal(tested_open) + SHIFT,
            "fill_qty_total": str(sum(Decimal(f["last_qty"]) for f in oco_fills)),
        }
        acct = eng.cache.account_for_venue(venue)
        return {"case": name, "side": side, "decision_bar": DECISION, "tested_bar": CASES[name],
                "price_shift": str(SHIFT), "final_balance_total": str(acct.balance_total(usd)),
                "tested_bar_ts": tested_ts, "triggers": getattr(p, "triggers", None),
                "events": p.ev, "callback_errors": p.errors, "check": verdict}
    finally:
        eng.dispose()


if __name__ == "__main__":
    out = {"probe": "probe_oco_moo_p4", "data": "synthetic engine-semantics bars (not SPY/LEAN data)",
           "bar_adaptive_high_low_ordering": ADAPT, "price_shift": str(SHIFT),
           "results": [run(n, s) for s in ("BUY", "SELL") for n in CASES]}
    print(json.dumps(out, indent=1))
