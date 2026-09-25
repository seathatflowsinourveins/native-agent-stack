"""Offline tests for the sim-capacity infrastructure lane (blueprints/us-equities/
sim-capacity). Most classes here use no network, no credential file and no
NautilusTrader runtime; the two runtime-gated classes at the bottom skip
themselves cleanly when the active interpreter is not the pinned
nautilus_trader==2.0.0rc5 runtime, matching tests.test_sim_paper_compare's
pattern.
"""
import importlib.metadata
import importlib.util
import sys
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SIM_CAPACITY = ROOT / "blueprints/us-equities/sim-capacity"
sys.path.insert(0, str(SIM_CAPACITY))

import fee_model as FM  # noqa: E402
import schedule as SCH  # noqa: E402


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, SIM_CAPACITY / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _pinned_runtime_active() -> bool:
    try:
        return importlib.metadata.version("nautilus_trader") == "2.0.0rc5"
    except importlib.metadata.PackageNotFoundError:
        return False


# ---------------------------------------------------------------------------
# Fee model
# ---------------------------------------------------------------------------

class FeeModelTests(unittest.TestCase):
    def test_buy_is_free(self):
        self.assertEqual(FM.commission_usd(side="BUY", quantity=100, price="200.00"), Decimal("0"))

    def test_sell_charges_sec_and_taf(self):
        # notional = 100 * 200.00 = 20000; SEC fee = 20000 * 20.60/1e6 = 0.412
        # TAF = 100 * 0.000195 = 0.0195; total = 0.4315 -> rounds to 0.43
        fee = FM.sell_side_regulatory_fee(quantity=100, price="200.00")
        self.assertEqual(fee, Decimal("0.43"))
        self.assertEqual(FM.commission_usd(side="SELL", quantity=100, price="200.00"), fee)

    def test_taf_cap_applies(self):
        # A large sale should hit the $9.79 TAF cap, not scale linearly forever.
        uncapped_taf = Decimal(200000) * FM.FINRA_TAF_USD_PER_SHARE
        self.assertGreater(uncapped_taf, FM.FINRA_TAF_MAX_USD_PER_TRADE)
        fee = FM.sell_side_regulatory_fee(quantity=200000, price="1.00")
        sec_fee = Decimal("200000.00") * FM.SEC_SECTION31_RATE_USD_PER_DOLLAR
        expected = (sec_fee + FM.FINRA_TAF_MAX_USD_PER_TRADE).quantize(FM.CENT)
        self.assertEqual(fee, expected)

    def test_zero_or_negative_quantity_is_zero_fee(self):
        self.assertEqual(FM.sell_side_regulatory_fee(quantity=0, price="50.00"), Decimal("0.00"))


# ---------------------------------------------------------------------------
# Schedule / budget math
# ---------------------------------------------------------------------------

class ScheduleMathTests(unittest.TestCase):
    def test_tick_interval_ns(self):
        self.assertEqual(SCH.tick_interval_ns(5.0), 200_000_000)
        self.assertEqual(SCH.tick_interval_ns(3.0), 333_333_333)

    def test_tick_interval_rejects_nonpositive(self):
        with self.assertRaises(ValueError):
            SCH.tick_interval_ns(0)

    def test_expected_submits_per_min(self):
        self.assertEqual(SCH.expected_submits_per_min(3.0), 180.0)
        self.assertEqual(SCH.expected_submits_per_min(15.0), 900.0)

    def test_minute_bucket(self):
        start = 1_000_000_000_000
        self.assertEqual(SCH.minute_bucket(start, start), 0)
        self.assertEqual(SCH.minute_bucket(start + SCH.NS_PER_MIN - 1, start), 0)
        self.assertEqual(SCH.minute_bucket(start + SCH.NS_PER_MIN, start), 1)
        with self.assertRaises(ValueError):
            SCH.minute_bucket(start - 1, start)

    def test_full_minutes(self):
        self.assertEqual(SCH.full_minutes(1800 * SCH.NS_PER_SEC), 30)
        self.assertEqual(SCH.full_minutes(1799 * SCH.NS_PER_SEC), 29)


class RoundRobinTests(unittest.TestCase):
    def test_round_robin_cycles_symbols(self):
        rr = SCH.RoundRobin(["A", "B", "C"], position_cap=10)
        picked = [rr.next_symbol() for _ in range(6)]
        self.assertEqual(picked, ["A", "B", "C", "A", "B", "C"])

    def test_first_side_is_buy_then_alternates(self):
        rr = SCH.RoundRobin(["A"], position_cap=10)
        self.assertEqual(rr.next_side("A", 0), "BUY")
        self.assertEqual(rr.next_side("A", 1), "SELL")
        self.assertEqual(rr.next_side("A", 0), "BUY")

    def test_position_cap_blocks_side_that_would_breach_it(self):
        rr = SCH.RoundRobin(["A"], position_cap=1)
        self.assertEqual(rr.next_side("A", 0), "BUY")   # -> would be +1, OK
        self.assertEqual(rr.next_side("A", 1), "SELL")  # -> would be 0, OK
        # Force two BUYs in a row by manipulating internal state: at position
        # already at the cap, a further BUY must be refused and SELL offered.
        rr._last_side["A"] = "BUY"
        self.assertEqual(rr.next_side("A", 1), "SELL")

    def test_rejects_empty_symbols_or_nonpositive_cap(self):
        with self.assertRaises(ValueError):
            SCH.RoundRobin([], position_cap=1)
        with self.assertRaises(ValueError):
            SCH.RoundRobin(["A"], position_cap=0)


# ---------------------------------------------------------------------------
# Crossed-quote / nonpositive-trade dropping (fetcher.py; pure, no nautilus)
# ---------------------------------------------------------------------------

class NormalizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fetcher = _load("sim_capacity_fetcher", "fetcher.py")

    def test_crossed_quote_dropped_and_counted(self):
        raw = {"AAPL": [
            {"t": "2026-09-24T14:00:00Z", "bp": 100.0, "ap": 100.02, "bs": 5, "as": 5},   # kept
            {"t": "2026-09-24T14:00:01Z", "bp": 100.05, "ap": 100.02, "bs": 5, "as": 5},  # crossed, dropped
            {"t": "2026-09-24T14:00:02Z", "bp": 100.0, "ap": 0, "bs": 5, "as": 5},        # nonpositive, dropped
        ]}
        kept, drops = self.fetcher.normalize_quotes(raw)
        self.assertEqual(len(kept["AAPL"]), 1)
        self.assertEqual(drops["AAPL"], {"one_sided_or_nonpositive": 1, "crossed": 1})

    def test_locked_quote_is_kept(self):
        raw = {"AAPL": [{"t": "2026-09-24T14:00:00Z", "bp": 100.0, "ap": 100.0, "bs": 5, "as": 5}]}
        kept, drops = self.fetcher.normalize_quotes(raw)
        self.assertEqual(len(kept["AAPL"]), 1)
        self.assertEqual(drops["AAPL"], {"one_sided_or_nonpositive": 0, "crossed": 0})

    def test_quotes_sorted_by_time(self):
        raw = {"AAPL": [
            {"t": "2026-09-24T14:00:02Z", "bp": 100.0, "ap": 100.02, "bs": 5, "as": 5},
            {"t": "2026-09-24T14:00:00Z", "bp": 100.0, "ap": 100.02, "bs": 5, "as": 5},
        ]}
        kept, _ = self.fetcher.normalize_quotes(raw)
        self.assertEqual([q["ts_ns"] for q in kept["AAPL"]], sorted(q["ts_ns"] for q in kept["AAPL"]))

    def test_nonpositive_trade_dropped(self):
        raw = {"AAPL": [
            {"t": "2026-09-24T14:00:00Z", "p": 100.0, "s": 10, "i": 1},
            {"t": "2026-09-24T14:00:01Z", "p": 0, "s": 10, "i": 2},
            {"t": "2026-09-24T14:00:02Z", "p": 100.0, "s": 0, "i": 3},
        ]}
        kept, drops = self.fetcher.normalize_trades(raw)
        self.assertEqual(len(kept["AAPL"]), 1)
        self.assertEqual(drops["AAPL"], {"nonpositive": 2})


# ---------------------------------------------------------------------------
# argv redaction and the pandas datetime64-report trap (runner.py; pandas
# required, nautilus_trader is not)
# ---------------------------------------------------------------------------

def _pandas_available() -> bool:
    try:
        import pandas  # noqa: F401
        return True
    except ImportError:
        return False


class RunnerPureLogicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runner = _load("sim_capacity_runner", "runner.py")

    def test_redact_args_hides_sensitive_paths(self):
        import argparse
        ns = argparse.Namespace(command="fetch", pages=Path("/private/pages"),
                                 catalog=Path("/private/catalog"), out=None, replay=False,
                                 receipt=None, profile=None, latency_ms=None)
        redacted = self.runner.redact_args(ns)
        joined = " ".join(redacted)
        self.assertNotIn("/private/pages", joined)
        self.assertNotIn("/private/catalog", joined)
        self.assertIn("<redacted>", joined)

    def test_redact_args_keeps_non_sensitive_fields(self):
        import argparse
        ns = argparse.Namespace(command="run", pages=None, catalog=None, out=None, replay=False,
                                 receipt=None, profile="elite-tier", latency_ms=None)
        redacted = self.runner.redact_args(ns)
        self.assertIn("elite-tier", redacted)

    @unittest.skipUnless(_pandas_available(), "requires pandas (present on the pinned runtime)")
    def test_dataframe_to_rows_recovers_true_ns_epoch(self):
        """Reproduces the exact trap disclosed in dataframe_to_rows's docstring:
        `DataFrame.to_json(date_format='epoch')` on a tz-aware datetime64[ns]
        column truncates 1,800,000,500,000,000 ns to 1800000500 (milliseconds,
        and even then inconsistently scaled) -- `dataframe_to_rows` must recover
        the exact original nanosecond integer instead."""
        import pandas as pd
        true_ns = 1_800_000_500_000_000
        df = pd.DataFrame({"ts_event": [pd.Timestamp(true_ns, unit="ns", tz="UTC")], "qty": [5]})
        rows = self.runner.dataframe_to_rows(df)
        self.assertEqual(int(rows[0]["ts_event"]), true_ns)
        # Demonstrate the trap this helper avoids: to_json's default epoch format
        # does not preserve the same integer.
        import json as _json
        lossy = _json.loads(df.to_json(orient="records", date_format="epoch"))
        self.assertNotEqual(int(lossy[0]["ts_event"]), true_ns)

    def test_recount_matches_between_events_and_report_rows(self):
        start_ns = 0
        events = [
            {"ts_ns": 100, "kind": "submit"}, {"ts_ns": 200, "kind": "fill"},
            {"ts_ns": SCH.NS_PER_MIN + 50, "kind": "fill"},
            {"ts_ns": SCH.NS_PER_MIN + 60, "kind": "fill"},
        ]
        buckets = self.runner.bucket_events_by_minute(events, start_ns)
        self.assertEqual(buckets[0]["fills"], 1)
        self.assertEqual(buckets[1]["fills"], 2)
        fill_rows = [{"ts_event": 200}, {"ts_event": SCH.NS_PER_MIN + 50}, {"ts_event": SCH.NS_PER_MIN + 60}]
        report_counts = self.runner.recount_fills_from_report(fill_rows, start_ns)
        strategy_counts = {m: b.get("fills", 0) for m, b in buckets.items()}
        self.assertEqual(report_counts, strategy_counts)

    def test_fills_per_minute_stats(self):
        stats = self.runner.fills_per_minute_stats({0: 180, 1: 200, 2: 100}, total_full_minutes=3)
        self.assertEqual(stats["min"], 100)
        self.assertEqual(stats["max"], 200)
        self.assertEqual(stats["median"], 180)
        self.assertEqual(stats["full_minutes_at_or_above_180"], 2)


# ---------------------------------------------------------------------------
# --replay never opens credentials
# ---------------------------------------------------------------------------

class ReplayNeverOpensCredentialsTests(unittest.TestCase):
    def test_load_credentials_replay_true_is_a_pure_noop(self):
        fetcher = _load("sim_capacity_fetcher_replay", "fetcher.py")

        def _boom(*a, **kw):
            raise AssertionError("resolve_paper_credential_path must not be called in --replay mode")

        fetcher.resolve_paper_credential_path = _boom
        key, secret = fetcher.load_credentials(replay=True)
        self.assertIsNone(key)
        self.assertIsNone(secret)


# ---------------------------------------------------------------------------
# Pinned-runtime smoke tests: native limiter denies over-rate submits, and the
# IOC collar fills against a synthetic L1 book.
# ---------------------------------------------------------------------------

@unittest.skipUnless(_pinned_runtime_active(), "requires the pinned nautilus_trader==2.0.0rc5 runtime")
class PinnedRuntimeEngineTests(unittest.TestCase):
    def _run(self, submits_per_sec: float, max_rate: str):
        from nautilus_trader.backtest import BacktestEngine
        from nautilus_trader.common import LogLevel
        from nautilus_trader.config import BacktestEngineConfig, LoggerConfig, RiskEngineConfig
        from nautilus_trader.model import (AccountType, BookType, Currency, Equity, InstrumentId, Money,
                                            OmsType, Price, Quantity, QuoteTick, Symbol, Venue)

        exerciser = _load("sim_capacity_exerciser", "exerciser.py")
        fee_model_module = _load("sim_capacity_fee_model", "fee_model.py")

        usd, venue = Currency.from_str("USD"), Venue("SIM")
        symbols = ["AAPL", "MSFT"]
        instruments = {}
        for s in symbols:
            iid = InstrumentId.from_str(f"{s}.SIM")
            instruments[s] = Equity(iid, Symbol(s), usd, 2, Price.from_str("0.01"), 0, 0,
                                     lot_size=Quantity.from_int(1))
        ticks = []
        for s in symbols:
            iid = instruments[s].id
            for i in range(600):
                ts = i * 50_000_000
                ticks.append(QuoteTick(iid, Price.from_str("100.00"), Price.from_str("100.02"),
                                        Quantity.from_int(500), Quantity.from_int(500), ts, ts))
        ticks.sort(key=lambda t: t.ts_event)

        engine = BacktestEngine(BacktestEngineConfig(
            logging=LoggerConfig(stdout_level=LogLevel.ERROR),
            risk_engine=RiskEngineConfig(max_order_submit_rate=max_rate)))
        try:
            engine.add_venue(venue, OmsType.NETTING, AccountType.CASH, [Money(Decimal("100000"), usd)],
                              base_currency=usd, fee_model=fee_model_module.build_nautilus_fee_model(),
                              latency_model=None, book_type=BookType.L1_MBP, trade_execution=True,
                              liquidity_consumption=True, queue_position=True)
            for inst in instruments.values():
                engine.add_instrument(inst)
            engine.add_data(ticks)
            params = exerciser.CapacityExerciserParams(symbols=tuple(symbols), submits_per_sec=submits_per_sec,
                                                        position_cap=50, run_seconds=25.0,
                                                        flatten_buffer_seconds=2.0)
            strategy = exerciser.CapacityExerciser(params)
            engine.add_strategy(strategy)
            engine.run()
            return strategy
        finally:
            engine.dispose()

    def test_native_limiter_denies_over_rate_submits(self):
        # 10/sec = 600/min attempted against a 60/min budget: denials must occur.
        strategy = self._run(submits_per_sec=10.0, max_rate="60/00:01:00")
        self.assertGreater(strategy.counters.get("rate_limit_denied", 0), 0)
        self.assertGreater(strategy.counters.get("submits", 0), strategy.counters.get("fills", 0) - 1)

    def test_ioc_collar_fills_against_synthetic_book(self):
        # Well under budget: essentially every marketable IOC should fill against
        # the abundant synthetic L1 book.
        strategy = self._run(submits_per_sec=2.0, max_rate="180/00:01:00")
        self.assertGreater(strategy.counters.get("fills", 0), 0)
        self.assertEqual(strategy.counters.get("rate_limit_denied", 0), 0)


if __name__ == "__main__":
    unittest.main()
