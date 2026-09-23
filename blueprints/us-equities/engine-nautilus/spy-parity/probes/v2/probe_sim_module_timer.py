"""Engine-semantics probe (synthetic bars): can a Python SimulationModule subclass,
passed through add_venue(modules=[...]), credit cash to a CASH account natively
(SimulatedExchange.process_modules -> try_adjust_account -> AccountState)?"""
import json
from decimal import Decimal

from nautilus_trader.backtest import BacktestEngine, SimulationModule
from nautilus_trader.common import LogLevel
from nautilus_trader.config import BacktestEngineConfig, LoggerConfig, StrategyConfig
from nautilus_trader.model import (AccountType, Bar, BarType, Currency, Equity, InstrumentId, Money,
                                   OmsType, OrderSide, Price, Quantity, Symbol, Venue)
from nautilus_trader.trading import Strategy

BASE, STEP = 1_600_000_000_000_000_000, 3_600_000_000_000
EX_TS = BASE + STEP + STEP // 2  # between bar 1 and bar 2
PER_SHARE = Decimal("1.57")
usd = Currency.from_str("USD")


class DividendModule(SimulationModule):
    def __init__(self, *a, **k):
        self.log = []
        self.paid = False

    def pre_process(self, data):
        pass

    def process(self, ts_now, ctx):
        qty = sum((Decimal(str(p.signed_qty)) for p in ctx.positions
                   if str(p.instrument_id) == "SPY.SIM"), Decimal(0))
        self.log.append({"call": "process", "ts_now": ts_now, "venue": str(ctx.venue),
                         "positions_signed_qty": str(qty), "n_instruments": len(ctx.instruments)})
        if not self.paid and ts_now >= EX_TS:
            self.paid = True
            amt = (qty * PER_SHARE).quantize(Decimal("0.01"))
            self.log.append({"call": "emit", "ts_now": ts_now, "amount": str(amt)})
            return [Money(amt, usd)]
        return []  # completed empty batch (None would mean NotReady)

    def acknowledge(self, outcomes):
        self.log.append({"call": "acknowledge",
                         "outcomes": [{"applied": o.applied, "error": o.error} for o in outcomes]})

    def log_diagnostics(self):
        pass

    def reset(self):
        self.paid = False


def main():
    venue = Venue("SIM")
    eq = Equity(InstrumentId.from_str("SPY.SIM"), Symbol("SPY"), usd, 2, Price.from_str("0.01"), 0, 0,
                lot_size=Quantity.from_int(1))
    bt = BarType.from_str("SPY.SIM-1-HOUR-LAST-EXTERNAL")
    specs = [(100.0, 101.0, 99.0, 100.0), (100.0, 101.0, 99.0, 100.0), (100.0, 101.0, 99.0, 100.0),
             (100.0, 101.0, 99.0, 100.0)]
    bars = [Bar(bt, *[Price.from_str(f"{x:.2f}") for x in s], Quantity.from_int(1000),
                BASE + i * STEP, BASE + i * STEP) for i, s in enumerate(specs)]

    class P(Strategy):
        def __init__(self):
            super().__init__(StrategyConfig())
            self.i, self.bal = -1, []

        def on_start(self):
            self.subscribe_bars(bt)
            self.clock.set_time_alert_ns("ex_date", EX_TS, lambda e: None)

        def on_bar(self, bar):
            self.i += 1
            acct = self.cache.account_for_venue(venue)
            self.bal.append({"bar": self.i, "ts": bar.ts_event,
                             "total": str(acct.balance_total(usd)) if acct else None})
            if self.i == 0:
                self.submit_order(self.order_factory.market(eq.id, OrderSide.BUY, Quantity.from_int(100)))

    mod = DividendModule()
    eng = BacktestEngine(BacktestEngineConfig(logging=LoggerConfig(stdout_level=LogLevel.ERROR)))
    try:
        eng.add_venue(venue, OmsType.NETTING, AccountType.CASH, [Money(Decimal("100000"), usd)],
                      base_currency=usd, modules=[mod])
        eng.add_instrument(eq); eng.add_data(bars)
        p = P(); eng.add_strategy(p); eng.run()
        rep = eng.generate_account_report(venue)
        rows = json.loads(rep.to_json(orient="records", default_handler=str)) if hasattr(rep, "to_json") else str(rep)
        acct = eng.cache.account_for_venue(venue)
        return {"module_log": mod.log, "strategy_balance_seen": p.bal,
                "final_total": str(acct.balance_total(usd)),
                "account_report_rows": rows,
                "expected_if_credited": str(Decimal("100000") - 100 * Decimal("100") + 100 * PER_SHARE)}
    finally:
        eng.dispose()


if __name__ == "__main__":
    print(json.dumps(main(), indent=1, default=str))
