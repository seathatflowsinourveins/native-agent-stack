"""Refutation probe: same synthetic cases as probe_gap_open.py but the STOP/MIT pair is
constructed directly with native ContingencyType.OCO + linked_order_ids (matching-engine
contingency), no strategy-level sibling cancel."""
import json, sys
from decimal import Decimal
from nautilus_trader.backtest import BacktestEngine
from nautilus_trader.common import LogLevel
from nautilus_trader.config import BacktestEngineConfig, LoggerConfig, StrategyConfig
from nautilus_trader.core import UUID4
from nautilus_trader.model import (AccountType, Bar, BarType, Currency, Equity, InstrumentId, Money,
    OmsType, OrderSide, Price, Quantity, Symbol, Venue, StopMarketOrder, MarketIfTouchedOrder,
    ContingencyType, TriggerType, TimeInForce, OrderListId, ClientOrderId)
from nautilus_trader.trading import Strategy

BASE, STEP = 1_600_000_000_000_000_000, 3_600_000_000_000
CASES = {
    "no_gap_both": (100.5, 103.0, 99.0, 102.0),
    "gap_up_both_range_crosses_back": (110.0, 112.0, 95.0, 111.0),
    "gap_down_both": (90.0, 91.0, 88.0, 89.0),
    "gap_up_both": (110.0, 112.0, 109.0, 111.0),
}
ADAPT = sys.argv[1] == "adaptive" if len(sys.argv) > 1 else False

def run(name):
    bar1 = CASES[name]
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
            if self.i != 0:
                return
            c = bar.close.as_decimal(); tick = Decimal("0.01"); q = Quantity.from_int(990)
            sid = ClientOrderId("O-STOP"); mid = ClientOrderId("O-MIT"); lid = OrderListId("OL-1")
            ts = self.clock.timestamp_ns()
            common = dict(trader_id=self.trader_id, strategy_id=self.id if hasattr(self,'id') else self.strategy_id,
                          instrument_id=eq.id, order_side=OrderSide.BUY, quantity=q,
                          trigger_type=TriggerType.DEFAULT, time_in_force=TimeInForce.GTC,
                          reduce_only=False, quote_quantity=False, ts_init=ts,
                          contingency_type=ContingencyType.OCO, order_list_id=lid)
            so = StopMarketOrder(client_order_id=sid, trigger_price=Price.from_str(str(c + tick)),
                                 init_id=UUID4(), linked_order_ids=[mid], **common)
            mo = MarketIfTouchedOrder(client_order_id=mid, trigger_price=Price.from_str(str(c - tick)),
                                      init_id=UUID4(), linked_order_ids=[sid], **common)
            self.ids = {sid: "stop", mid: "mit"}
            self.submit_order(so); self.submit_order(mo)
        def on_order_event(self, e):
            t = type(e).__name__
            rec = {"event": t, "order": self.ids.get(e.client_order_id), "ts_event": e.ts_event}
            if t == "OrderFilled": rec["last_px"] = str(e.last_px)
            if t in ("OrderRejected", "OrderCanceled", "OrderDenied"): rec["reason"] = str(getattr(e, "reason", "") or "")
            self.ev.append(rec)

    eng = BacktestEngine(BacktestEngineConfig(logging=LoggerConfig(stdout_level=LogLevel.ERROR)))
    try:
        eng.add_venue(venue, OmsType.NETTING, AccountType.CASH, [Money(Decimal("100000"), usd)], base_currency=usd,
                      bar_adaptive_high_low_ordering=ADAPT)
        eng.add_instrument(eq); eng.add_data(bars)
        p = P(); eng.add_strategy(p); eng.run()
        keep = ("OrderFilled", "OrderTriggered", "OrderCanceled", "OrderRejected", "OrderDenied")
        return {"case": name, "bar1": bar1, "events": [e for e in p.ev if e["event"] in keep]}
    finally:
        eng.dispose()

if __name__ == "__main__":
    print(json.dumps([run(n) for n in CASES], indent=1))
