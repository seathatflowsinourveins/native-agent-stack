"""Engine-semantics probe (SYNTHETIC bars and synthetic factor rows; not SPY/LEAN data,
not a parity run).

Question: on nautilus_trader 2.0.0rc5, can a Python SimulationModule post a per-share
cash distribution through the exchange's native account adjustment path
(SimulatedExchange.process_modules -> try_adjust_account -> AccountState) at an
ex-date instant that carries no market data, using the position the engine itself
reports at that instant, so that:
  1. process() is called at the ex-date instant when the strategy registers a
     no-op time alert there (no bar exists at that instant);
  2. a fill that happens later on the ex-date is NOT counted (eligibility is the
     position at the ex-date instant, as in LEAN's midnight dividend slice);
  3. a zero eligible quantity posts Money(0.00) and is acknowledged as applied;
  4. the credit appears in the native account report and final balance;
  5. the amount is signed_qty * per_share, where per_share is rounded to cents
     half-to-even from (reference_price, price_factor, next_price_factor) exactly
     like LEAN Dividend.ComputeDistribution, with no further rounding;
  6. the ex-date is the NEXT SESSION after the factor row date (a Friday row pays
     on Monday), not the calendar day after it.

Prints one JSON document. Nothing is filtered.
"""
import json
from datetime import date, datetime, time
from decimal import ROUND_HALF_EVEN, Decimal
from zoneinfo import ZoneInfo

from nautilus_trader.backtest import BacktestEngine, SimulationModule
from nautilus_trader.common import LogLevel
from nautilus_trader.config import BacktestEngineConfig, LoggerConfig, StrategyConfig
from nautilus_trader.model import (AccountType, Bar, BarType, Currency, Equity, InstrumentId, Money,
                                   OmsType, OrderSide, Price, Quantity, Symbol, Venue)
from nautilus_trader.trading import Strategy

NY = ZoneInfo("America/New_York")
usd = Currency.from_str("USD")

# Synthetic sessions: Thu 2030-01-03, Fri 2030-01-04, Mon 2030-01-07, Tue 2030-01-08.
SESSIONS = [date(2030, 1, 3), date(2030, 1, 4), date(2030, 1, 7), date(2030, 1, 8)]
# Synthetic factor rows (date, price_factor, reference_price). Two dividend events:
#   row Thu 2030-01-03 -> ex-date Fri 2030-01-04 (held 0 at that instant)
#   row Fri 2030-01-04 -> ex-date Mon 2030-01-07 (calendar +1 would be Sat 2030-01-05);
#   its raw distribution is exactly 1.005, a half-to-even midpoint (1.00, not 1.01)
FACTOR_ROWS = [(date(2030, 1, 3), Decimal("0.9800000"), Decimal("100.00")),
               (date(2030, 1, 4), Decimal("0.9900000"), Decimal("100.50")),
               (date(2030, 12, 31), Decimal("1"), Decimal("0"))]


def ns(d, hh, mm=0):
    return int(datetime.combine(d, time(hh, mm), NY).timestamp()) * 1_000_000_000


def next_session(d):
    later = [s for s in SESSIONS if s > d]
    return later[0] if later else None


def distributions():
    """LEAN DividendEventProvider/ComputeDistribution semantics on synthetic rows."""
    out = []
    for (d0, pf0, ref0), (_d1, pf1, _ref1) in zip(FACTOR_ROWS, FACTOR_ROWS[1:]):
        if pf0 == pf1 or d0 not in SESSIONS:
            continue
        ex = next_session(d0)
        if ex is None:
            continue
        per_share = (ref0 - ref0 * (pf0 / pf1)).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
        out.append({"factor_row_date": d0.isoformat(), "ex_date": ex.isoformat(),
                    "calendar_plus_one": date.fromordinal(d0.toordinal() + 1).isoformat(),
                    "ex_ts_ns": ns(ex, 0), "per_share": str(per_share)})
    return out


DISTS = distributions()


class DistributionModule(SimulationModule):
    def __init__(self, *a, **k):
        self.log, self.pending = [], list(DISTS)

    def pre_process(self, data):
        pass

    def process(self, ts_now, ctx):
        self.log.append({"call": "process", "ts_now": ts_now})
        emit = []
        while self.pending and self.pending[0]["ex_ts_ns"] <= ts_now:
            d = self.pending.pop(0)
            qty = sum((Decimal(str(p.signed_qty)) for p in ctx.positions
                       if str(p.instrument_id) == "SPY.SIM"), Decimal(0))
            amount = qty * Decimal(d["per_share"])  # whole shares x cents: exact, no rounding stage
            self.log.append({"call": "emit", "ts_now": ts_now, "ex_ts_ns": d["ex_ts_ns"],
                             "on_time": ts_now == d["ex_ts_ns"], "eligible_signed_qty": str(qty),
                             "per_share": d["per_share"], "amount": str(amount)})
            emit.append(Money(amount, usd))
        return emit

    def acknowledge(self, outcomes):
        self.log.append({"call": "acknowledge",
                         "outcomes": [{"applied": o.applied, "error": o.error} for o in outcomes]})

    def log_diagnostics(self):
        pass

    def reset(self):
        self.pending = list(DISTS)


def main():
    venue = Venue("SIM")
    eq = Equity(InstrumentId.from_str("SPY.SIM"), Symbol("SPY"), usd, 4, Price.from_str("0.0001"), 0, 0,
                lot_size=Quantity.from_int(1))
    bt = BarType.from_str("SPY.SIM-1-HOUR-LAST-EXTERNAL")
    # One bar per session, stamped at 10:00 New York (bar end), plus a 16:00 bar.
    bars = []
    for s in SESSIONS:
        for hh in (10, 16):
            bars.append(Bar(bt, *[Price.from_str("100.0000")] * 4, Quantity.from_int(4_000_000),
                            ns(s, hh), ns(s, hh)))

    class P(Strategy):
        def __init__(self):
            super().__init__(StrategyConfig())
            self.bal, self.fills, self.errors = [], [], []

        def on_start(self):
            self.subscribe_bars(bt)
            for d in DISTS:  # no-op alerts: they only give the engine a timestamp to run modules at
                self.clock.set_time_alert_ns(f"ex_{d['ex_date']}", d["ex_ts_ns"], lambda e: None)

        def on_bar(self, bar):
            try:
                acct = self.cache.account_for_venue(venue)
                self.bal.append({"ts": bar.ts_event, "total": str(acct.balance_total(usd)) if acct else None})
                # Buy 50 at Fri 10:00 (after the Fri ex-date instant) and 25 more at Mon 10:00
                # (after the Mon ex-date instant): neither may count for its own ex-date.
                if bar.ts_event in (ns(SESSIONS[1], 10), ns(SESSIONS[2], 10)):
                    q = 50 if bar.ts_event == ns(SESSIONS[1], 10) else 25
                    self.submit_order(self.order_factory.market(eq.id, OrderSide.BUY, Quantity.from_int(q)))
            except BaseException as exc:
                self.errors.append(repr(exc))

        def on_order_filled(self, e):
            self.fills.append({"ts_event": e.ts_event, "last_px": str(e.last_px), "last_qty": str(e.last_qty)})

    mod = DistributionModule()
    eng = BacktestEngine(BacktestEngineConfig(logging=LoggerConfig(stdout_level=LogLevel.ERROR)))
    try:
        eng.add_venue(venue, OmsType.NETTING, AccountType.CASH, [Money(Decimal("100000"), usd)],
                      base_currency=usd, use_random_ids=False, modules=[mod])
        eng.add_instrument(eq)
        eng.add_data(bars)
        p = P()
        eng.add_strategy(p)
        eng.run()
        rep = eng.generate_account_report(venue)
        rows = json.loads(rep.to_json(orient="records", default_handler=str))
        acct = eng.cache.account_for_venue(venue)
        emits = [x for x in mod.log if x["call"] == "emit"]
        expected_final = Decimal("100000") - 75 * Decimal("100") + sum(
            Decimal(x["eligible_signed_qty"]) * Decimal(x["per_share"]) for x in emits)
        return {"probe": "probe_sim_module_exdate",
                "data": "synthetic engine-semantics bars and factor rows (not SPY/LEAN data)",
                "distributions_derived": DISTS, "module_log": mod.log, "fills": p.fills,
                "strategy_balance_seen": p.bal, "callback_errors": p.errors,
                "final_total": str(acct.balance_total(usd)), "account_report_rows": rows,
                "expected_final_total_if_posted": f"{expected_final:.2f}"}
    finally:
        eng.dispose()


if __name__ == "__main__":
    print(json.dumps(main(), indent=1, default=str))
