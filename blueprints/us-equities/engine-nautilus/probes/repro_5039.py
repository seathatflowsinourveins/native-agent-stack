"""Reproduce nautilus_trader#5039 on the installed wheel: an exception raised inside a
Python Strategy.on_order_filled neither propagates out of the engine nor stops it.

Moved into the repository from the 2026-09-24 data and execution convergence work
(backlog item 3, E3). Evidence class: local integration on the installed wheel, a
synthetic EUR/USD bar series through NautilusTrader's own BacktestEngine; no network,
no credentials, no broker. The LiveNode counterpart is UpstreamCallbackLoss in
tests/test_adaptive_paper_native.py; the engine's defence is
blueprints/us-equities/adaptive-paper/native_adapter.guarded_callback.

    rtk proxy "$NT" blueprints/us-equities/engine-nautilus/probes/repro_5039.py

Exit 0 while the upstream loss reproduces (the handler raised, run() raised nothing
and later bars were still processed). Exit 1 when it does not: a release that surfaces
the exception or stops is E3's overturn signal (the guard can shrink to record and
freeze), to be confirmed against the release notes before acting on it.
"""
import datetime
import importlib.metadata as md
import random
import sys
from decimal import Decimal

from nautilus_trader.backtest import BacktestEngine
from nautilus_trader.common import LogLevel
from nautilus_trader.config import BacktestEngineConfig, LoggerConfig, StrategyConfig
from nautilus_trader.model import (AccountType, Bar, BarType, Currency, CurrencyPair, InstrumentId, Money,
                                   OmsType, OrderSide, Price, Quantity, Symbol, Venue)
from nautilus_trader.trading import Strategy


class Cfg(StrategyConfig):
    def __init__(self, *, instrument_id, bar_type, **kw):
        super().__init__()
        self.instrument_id, self.bar_type = instrument_id, bar_type


class Raiser(Strategy):
    def __init__(self, config):
        super().__init__(config)
        self.bars_after_fill = 0
        self.fills = 0
        self.reached_after_raise = False
        self.submitted = False

    def on_start(self):
        self.subscribe_bars(self.config.bar_type)

    def on_bar(self, bar):
        if self.fills:
            self.bars_after_fill += 1
        if not self.submitted:
            ins = self.cache.instrument(self.config.instrument_id)
            self.submit_order(self.order_factory.market(self.config.instrument_id, OrderSide.BUY,
                                                        ins.make_qty(Decimal(100000))))
            self.submitted = True

    def on_order_filled(self, event):
        self.fills += 1
        raise RuntimeError("REPRO_5039_deliberate_exception_in_on_order_filled")
        self.reached_after_raise = True  # unreachable


def main():
    eur, usd = Currency.from_str("EUR"), Currency.from_str("USD")
    pair = CurrencyPair(instrument_id=InstrumentId.from_str("EUR/USD.SIM"), raw_symbol=Symbol("EUR/USD"),
                        base_currency=eur, quote_currency=usd, price_precision=5, size_precision=0,
                        price_increment=Price.from_str("0.00001"), size_increment=Quantity.from_int(1), ts_event=0,
                        ts_init=0, lot_size=Quantity.from_int(1000), margin_init=Decimal("0.03"),
                        margin_maint=Decimal("0.03"))
    random.seed(1)
    n, prices, x = 50, [], 1.10
    for _ in range(n):
        x += random.gauss(0, 0.0002)
        prices.append(x)
    t0 = int(datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc).timestamp()) * 1_000_000_000
    stamps = [t0 + i * 60_000_000_000 for i in range(n)]
    bar_type = BarType.from_str("EUR/USD.SIM-1-MINUTE-LAST-EXTERNAL")
    bars = [Bar(bar_type=bar_type, open=Price(p, precision=5), high=Price(p + 0.0003, precision=5),
                low=Price(p - 0.0003, precision=5), close=Price(p, precision=5), volume=Quantity.from_int(1_000_000),
                ts_event=t, ts_init=t) for t, p in zip(stamps, prices)]
    engine = BacktestEngine(config=BacktestEngineConfig(logging=LoggerConfig(stdout_level=LogLevel.WARNING)))
    engine.add_venue(venue=Venue("SIM"), oms_type=OmsType.NETTING, account_type=AccountType.MARGIN,
                     starting_balances=[Money(1_000_000, usd)], base_currency=usd, default_leverage=Decimal(1))
    engine.add_instrument(pair)
    engine.add_data(bars)
    strategy = Raiser(Cfg(instrument_id=pair.id, bar_type=bar_type))
    engine.add_strategy(strategy)
    propagated = None
    try:
        engine.run()
    except BaseException as error:  # noqa: BLE001 - the probe records whatever surfaces
        propagated = repr(error)
    finally:
        engine.dispose()
    print("RESULT nautilus_trader", md.version("nautilus_trader"), "python", sys.version.split()[0])
    print("RESULT fills_seen_by_handler", strategy.fills, "| statement_after_raise_reached",
          strategy.reached_after_raise, "| bars_processed_after_fill", strategy.bars_after_fill,
          "| exception_propagated_from_run", propagated)
    loss = strategy.fills >= 1 and propagated is None and strategy.bars_after_fill > 0
    print("RESULT upstream_loss_reproduced", loss)
    return 0 if loss else 1


if __name__ == "__main__":
    sys.exit(main())
