"""Engine-semantics probe (synthetic bars, not parity data): does a resting
STOP_MARKET / MARKET_IF_TOUCHED order placed from bar t's close fill at bar t+1's
OPEN via the matching engine's gap-open trade tick (fill_at_market=true)?"""
import json, sys
from decimal import Decimal

from nautilus_trader.backtest import BacktestEngine
from nautilus_trader.common import LogLevel
from nautilus_trader.config import BacktestEngineConfig, LoggerConfig, StrategyConfig
from nautilus_trader.model import (AccountType, Bar, BarType, Currency, Equity, InstrumentId, Money,
                                   OmsType, OrderSide, Price, Quantity, Symbol, Venue)
from nautilus_trader.trading import Strategy

BASE, STEP = 1_600_000_000_000_000_000, 3_600_000_000_000
CASES = {
    # name: (bar1 OHLC, which orders)
    "gap_up_stop": ((110.0, 112.0, 109.0, 111.0), ("stop",)),
    "gap_down_mit": ((90.0, 91.0, 88.0, 89.0), ("mit",)),
    "no_gap_both": ((100.5, 103.0, 99.0, 102.0), ("stop", "mit")),
    "gap_up_both_range_crosses_back": ((110.0, 112.0, 95.0, 111.0), ("stop", "mit")),
    "gap_down_both": ((90.0, 91.0, 88.0, 89.0), ("stop", "mit")),
}


def run(name):
    bar1, kinds = CASES[name]
    usd, venue = Currency.from_str("USD"), Venue("SIM")
    eq = Equity(InstrumentId.from_str("SPY.SIM"), Symbol("SPY"), usd, 2, Price.from_str("0.01"), 0, 0,
                lot_size=Quantity.from_int(1))
    bt = BarType.from_str("SPY.SIM-1-HOUR-LAST-EXTERNAL")
    specs = [(100.0, 101.0, 99.0, 100.5), bar1, (200.0, 202.0, 198.0, 201.0)]
    bars = [Bar(bt, *[Price.from_str(f"{x:.2f}") for x in s], Quantity.from_int(1000),
                BASE + i * STEP, BASE + i * STEP) for i, s in enumerate(specs)]

    class P(Strategy):
        def __init__(self):
            super().__init__(StrategyConfig())
            self.i, self.ev, self.ids = -1, [], {}

        def on_start(self):
            self.subscribe_bars(bt)

        def on_bar(self, bar):
            self.i += 1
            if self.i == 0:
                c = bar.close.as_decimal()
                tick = Decimal("0.01")
                q = Quantity.from_int(10)
                if "stop" in kinds:
                    o = self.order_factory.stop_market(eq.id, OrderSide.BUY, q, Price.from_str(str(c + tick)))
                    self.ids[o.client_order_id] = "stop"; self.submit_order(o)
                if "mit" in kinds:
                    o = self.order_factory.market_if_touched(eq.id, OrderSide.BUY, q, Price.from_str(str(c - tick)))
                    self.ids[o.client_order_id] = "mit"; self.submit_order(o)

        def on_order_event(self, e):
            t = type(e).__name__
            rec = {"event": t, "order": self.ids.get(e.client_order_id), "ts_event": e.ts_event}
            if t == "OrderFilled":
                rec["last_px"] = str(e.last_px)
                self.ev.append(rec)
                try:
                    self._cancel_siblings(e)
                except Exception as exc:
                    self.ev.append({"event": "SiblingCancelError", "order": None, "ts_event": e.ts_event, "reason": repr(exc)})
                return
            if t in ("OrderRejected", "OrderCanceled"):
                rec["reason"] = str(getattr(e, "reason", "") or "")
            self.ev.append(rec)

        def _cancel_siblings(self, e):
                # strategy-level sibling cancel (no native two-sided OCO entry in the factory)
                for cid, k in self.ids.items():
                    if cid != e.client_order_id:
                        o = self.cache.order(cid)
                        if o is not None and (o.is_open() if callable(o.is_open) else o.is_open):
                            self.cancel_order(cid)

    eng = BacktestEngine(BacktestEngineConfig(logging=LoggerConfig(stdout_level=LogLevel.ERROR)))
    try:
        eng.add_venue(venue, OmsType.NETTING, AccountType.CASH, [Money(Decimal("100000"), usd)], base_currency=usd)
        eng.add_instrument(eq); eng.add_data(bars)
        p = P(); eng.add_strategy(p); eng.run()
        keep = ("SiblingCancelError", "OrderFilled", "OrderTriggered", "OrderCanceled", "OrderRejected")
        return {"case": name, "bar0": specs[0], "bar1": bar1, "bar1_ts": BASE + STEP,
                "events": [e for e in p.ev if e["event"] in keep]}
    finally:
        eng.dispose()


if __name__ == "__main__":
    print(json.dumps([run(n) for n in CASES], indent=1))
