"""Scratch probes against installed nautilus_trader 2.0.0rc5.
mode div : Python SimulationModule credits per-share cash for the open position at an ex timestamp.
mode opentick : MARKET order from on_bar(close) with StaticLatencyModel, released by a TradeTick at next open.
mode opentick_nolat : same without latency (control).
"""
import json, sys
from decimal import Decimal
from nautilus_trader.backtest import BacktestEngine, SimulationModule
from nautilus_trader.common import LogLevel
from nautilus_trader.config import BacktestEngineConfig, LoggerConfig, StrategyConfig
from nautilus_trader.model import (AccountType, Bar, BarType, Currency, Equity, InstrumentId, Money,
    OmsType, OrderSide, Price, Quantity, Symbol, Venue, TradeTick, AggressorSide, TradeId)
from nautilus_trader.trading import Strategy

mode = sys.argv[1]
usd, venue = Currency.from_str("USD"), Venue("SIM")
eq = Equity(InstrumentId.from_str("SPY.SIM"), Symbol("SPY"), usd, 2, Price.from_str("0.01"), 0, 0, lot_size=Quantity.from_int(1))
bt = BarType.from_str("SPY.SIM-1-DAY-LAST-EXTERNAL")
DAY = 86_400_000_000_000
T0 = 1_600_000_000_000_000_000  # bar 0 close (ts_init)
specs = [(100, 101, 99, 100.5), (110, 112, 108, 111), (120, 122, 118, 121)]
bars = [Bar(bt, *[Price.from_str(f"{x:.2f}") for x in s], Quantity.from_int(1000), T0 + i*DAY, T0 + i*DAY) for i, s in enumerate(specs)]
data = list(bars)
OPEN1 = T0 + DAY - 6*3_600_000_000_000 - 30*60_000_000_000  # 6.5h before bar1 close = its open
if mode.startswith("opentick") or mode == "ontick":
    data.append(TradeTick(eq.id, Price.from_str("110.00"), Quantity.from_int(500), AggressorSide.NO_AGGRESSOR, TradeId("OPEN1"), OPEN1, OPEN1))

class Div(SimulationModule):
    def __init__(self, ex_ns, per_share):
        self.ex_ns, self.per_share, self.done, self.log = ex_ns, per_share, False, []
    def process(self, ts_now, ctx):
        if self.done or ts_now < self.ex_ns:
            return []
        qty = sum(Decimal(str(p.signed_qty)) for p in ctx.positions if str(p.instrument_id) == "SPY.SIM")
        self.done = True
        amt = (qty * self.per_share).quantize(Decimal("0.01"))
        self.log.append({"ts_now": ts_now, "qty": str(qty), "amount": str(amt)})
        return [Money(amt, usd)] if amt else []
    def acknowledge(self, outcomes):
        self.log.append({"ack": [(o.applied, o.error) for o in outcomes]})

class S(Strategy):
    def __init__(self):
        super().__init__(StrategyConfig()); self.i = -1; self.ev = []
    def on_start(self):
        self.subscribe_bars(bt); self.pending = False
        if mode == "ontick": self.subscribe_trades(eq.id)
    def on_trade(self, t):
        if self.pending:
            self.pending = False
            self.submit_order(self.order_factory.market(eq.id, OrderSide.BUY, Quantity.from_int(10)))
    def on_bar(self, bar):
        self.i += 1
        if self.i == 0 and mode == "ontick":
            self.pending = True
        elif self.i == 0:
            self.submit_order(self.order_factory.market(eq.id, OrderSide.BUY, Quantity.from_int(10)))
    def on_order_event(self, e):
        self.ev.append({"event": type(e).__name__, "ts_event": e.ts_event, "last_px": str(getattr(e, "last_px", "") or "") or None, "reason": str(getattr(e, "reason", "") or "") or None})

kw = {}
if mode == "opentick":
    from nautilus_trader.execution import StaticLatencyModel
    kw["latency_model"] = StaticLatencyModel(base_latency_nanos=OPEN1 - T0)
mods = []
if mode == "div":
    mod = Div(T0 + DAY // 2, Decimal("1.2345")); mods = [mod]; kw["modules"] = mods
eng = BacktestEngine(BacktestEngineConfig(logging=LoggerConfig(stdout_level=LogLevel.ERROR)))
try:
    eng.add_venue(venue, OmsType.NETTING, AccountType.CASH, [Money(Decimal("100000"), usd)], base_currency=usd, **kw)
    eng.add_instrument(eq); eng.add_data(data)
    s = S(); eng.add_strategy(s); eng.run()
    acct = eng.cache.account_for_venue(venue)
    rep = json.loads(eng.generate_account_report(venue).to_json(orient="records"))
    out = {"mode": mode, "open1_ns": OPEN1, "t0": T0, "events": s.ev, "final_balance_total": str(acct.balance_total(usd)),
           "account_events": len(acct.events), "module_log": mods[0].log if mods else None, "account_report": rep}
    print(json.dumps(out, indent=1, default=str))
finally:
    eng.dispose()
