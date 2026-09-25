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
    def test_buy_rounds_to_zero_at_small_quantity(self):
        # CAT now applies to buys too (0.000003 x 100 = 0.0003), but that is
        # far below a cent, so the rounded commission is still 0.00 at the
        # exerciser's typical 1-5 share fills.
        self.assertEqual(FM.commission_usd(side="BUY", quantity=100, price="200.00"), Decimal("0.00"))

    def test_cat_fee_applies_to_buys_at_large_enough_quantity(self):
        # 10,000 * 0.000003 = 0.03 exactly: large enough to survive rounding,
        # proving CAT is charged on buys (mutating commission_usd's side check
        # to skip buys entirely, or dropping the CAT term, would zero this).
        self.assertEqual(FM.cat_fee(quantity=10_000), Decimal("0.03"))
        self.assertEqual(FM.commission_usd(side="BUY", quantity=10_000, price="200.00"), Decimal("0.03"))

    def test_sell_charges_sec_taf_and_cat(self):
        # sell_side_regulatory_fee is SEC+TAF only: notional = 100 * 200.00 =
        # 20000; SEC fee = 20000 * 20.60/1e6 = 0.412; TAF = 100 * 0.000195 =
        # 0.0195; unrounded total = 0.4315.
        reg = FM.sell_side_regulatory_fee(quantity=100, price="200.00")
        self.assertEqual(reg, Decimal("0.4315"))
        # commission_usd additionally adds CAT (100 * 0.000003 = 0.0003) before
        # rounding once, half-up: 0.4315 + 0.0003 = 0.4318 -> 0.43.
        self.assertEqual(FM.commission_usd(side="SELL", quantity=100, price="200.00"), Decimal("0.43"))

    def test_sell_side_is_strictly_higher_than_buy_side(self):
        # A direct behavioral guard against a side-check flip (mutate.py's
        # M3a/M3b): SEC+TAF must land only on sells, so a sell of the same
        # quantity/price must cost strictly more than a buy.
        buy = FM.commission_usd(side="BUY", quantity=500, price="100.00")
        sell = FM.commission_usd(side="SELL", quantity=500, price="100.00")
        self.assertGreater(sell, buy)

    def test_taf_cap_applies(self):
        # A large sale should hit the $9.79 TAF cap, not scale linearly forever.
        uncapped_taf = Decimal(200000) * FM.FINRA_TAF_USD_PER_SHARE
        self.assertGreater(uncapped_taf, FM.FINRA_TAF_MAX_USD_PER_TRADE)
        reg = FM.sell_side_regulatory_fee(quantity=200000, price="1.00")
        sec_fee = Decimal("200000.00") * FM.SEC_SECTION31_RATE_USD_PER_DOLLAR
        self.assertEqual(reg, sec_fee + FM.FINRA_TAF_MAX_USD_PER_TRADE)

    def test_zero_or_negative_quantity_is_zero_fee(self):
        self.assertEqual(FM.sell_side_regulatory_fee(quantity=0, price="50.00"), Decimal("0"))
        self.assertEqual(FM.cat_fee(quantity=0), Decimal("0"))
        self.assertEqual(FM.elite_commission(quantity=0, plan="all_in"), Decimal("0"))

    def test_elite_commission_plans(self):
        self.assertEqual(FM.elite_commission(quantity=1000, plan="none"), Decimal("0"))
        self.assertEqual(FM.elite_commission(quantity=1000, plan="all_in"), Decimal("4.00"))
        self.assertEqual(FM.elite_commission(quantity=1000, plan="cost_plus"), Decimal("2.50"))
        with self.assertRaises(ValueError):
            FM.elite_commission(quantity=1000, plan="bogus")

    def test_all_in_commission_applies_to_both_sides(self):
        # The Elite Smart Router commission is not sells-only: a buy under
        # commission_plan="all_in" must cost more than the same buy under
        # "none".
        buy_none = FM.commission_usd(side="BUY", quantity=1000, price="50.00", commission_plan="none")
        buy_all_in = FM.commission_usd(side="BUY", quantity=1000, price="50.00", commission_plan="all_in")
        self.assertEqual(buy_all_in - buy_none, Decimal("4.00"))

    def test_paper_parity_default_has_no_elite_commission(self):
        # commission_plan defaults to "none" for backward compatibility with
        # existing callers (including the reviewer's analyze.py harness).
        default = FM.commission_usd(side="SELL", quantity=100, price="200.00")
        explicit_none = FM.commission_usd(side="SELL", quantity=100, price="200.00", commission_plan="none")
        self.assertEqual(default, explicit_none)


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

    def test_never_proposes_sell_when_flat_or_short(self):
        # A CASH account rejects any sell that would take a position negative
        # ("Short selling not permitted on a CASH account"); next_side must
        # never propose SELL at position <= 0, regardless of alternation state.
        rr = SCH.RoundRobin(["A"], position_cap=50)
        for position in (0, -1, -5):
            rr._last_side["A"] = "SELL"  # would normally alternate to BUY anyway; force it
            self.assertEqual(rr.next_side("A", position), "BUY")

    def test_never_returns_none(self):
        # Unlike the earlier cap-blocking design, next_side always returns a
        # legal side now (BUY when flat/short, SELL at/above the cap).
        rr = SCH.RoundRobin(["A"], position_cap=3)
        for position in (0, 1, 2, 3, 4):
            self.assertIn(rr.next_side("A", position), ("BUY", "SELL"))

    def test_forces_sell_at_or_above_cap(self):
        rr = SCH.RoundRobin(["A"], position_cap=3)
        self.assertEqual(rr.next_side("A", 3), "SELL")
        self.assertEqual(rr.next_side("A", 10), "SELL")


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
        column reports 1,800,000,500,000,000 ns as 1800000500 -- a plain
        units mismatch (milliseconds, i.e. exactly true_ns // 1_000_000, not
        nanoseconds) -- `dataframe_to_rows` must recover the exact original
        nanosecond integer instead."""
        import pandas as pd
        true_ns = 1_800_000_500_000_000
        df = pd.DataFrame({"ts_event": [pd.Timestamp(true_ns, unit="ns", tz="UTC")], "qty": [5]})
        rows = self.runner.dataframe_to_rows(df)
        self.assertEqual(int(rows[0]["ts_event"]), true_ns)
        # Demonstrate the trap this helper avoids: to_json's default epoch
        # format reports milliseconds, not nanoseconds.
        import json as _json
        lossy = _json.loads(df.to_json(orient="records", date_format="epoch"))
        self.assertEqual(int(lossy[0]["ts_event"]), true_ns // 1_000_000)
        self.assertNotEqual(int(lossy[0]["ts_event"]), true_ns)

    @unittest.skipUnless(_pandas_available(), "requires pandas (present on the pinned runtime)")
    def test_dataframe_to_rows_handles_microsecond_column(self):
        # A datetime64[us, UTC] column's raw .astype("int64") would be
        # microseconds, not nanoseconds -- 1000x too small. dataframe_to_rows
        # must force ns precision first so this cannot slip through silently.
        import pandas as pd
        true_ns = 1_800_000_500_000_000
        df = pd.DataFrame({"ts_event": [pd.Timestamp(true_ns, unit="ns", tz="UTC")]})
        df["ts_event"] = df["ts_event"].astype("datetime64[us, UTC]")
        self.assertEqual(str(df["ts_event"].dtype), "datetime64[us, UTC]")
        rows = self.runner.dataframe_to_rows(df)
        self.assertEqual(int(rows[0]["ts_event"]), true_ns)

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

    def _synthetic_result(self, *, submit_ts_ns, fill_ts_ns, report_ts_ns, run_seconds=120.0):
        """Minimal but complete `result` dict shaped exactly like `run_one`'s
        return value, for exercising `summarize_run` (and, through it, the
        recount comparison) with no nautilus_trader dependency."""
        events = [
            {"ts_ns": submit_ts_ns, "kind": "submit", "client_order_id": "CAP-1", "symbol": "AAPL",
             "side": "BUY", "qty": 1, "limit_price": "100.02"},
            {"ts_ns": fill_ts_ns, "kind": "fill", "client_order_id": "CAP-1", "qty": 1, "price": "100.02",
             "side": "BUY", "fee_usd": "0.00", "instrument_id": "AAPL.SIM", "mid_at_fill": "100.01"},
        ]
        return {
            "profile": "paper-parity", "latency_ms": 70, "start_ns": 0, "counters": {"fills": 1},
            "events": events, "filled_qty": 1, "filled_notional": "100.02",
            "fills_report_rows": [{"ts_event": report_ts_ns}], "n_ticks": 10, "wall_seconds": 0.01,
            "net_positions_at_end": {"AAPL": 0}, "flat_at_end": True, "run_seconds": run_seconds,
        }

    def _synthetic_quotes(self):
        return {"AAPL": [{"symbol": "AAPL", "ts_ns": 0, "bid": "100.00", "ask": "100.02",
                          "bid_size": 100, "ask_size": 100}]}

    def test_summarize_run_detects_a_real_recount_disagreement(self):
        # The fill happened in minute 0 by the strategy's own event log, but the
        # (deliberately mismatched) fills_report row is stamped in minute 1:
        # summarize_run's recount must catch this, not paper over it.
        result = self._synthetic_result(submit_ts_ns=10_000_000_000, fill_ts_ns=40_000_000_000,
                                         report_ts_ns=SCH.NS_PER_MIN + 40_000_000_000)
        summary = self.runner.summarize_run(result, self._synthetic_quotes())
        self.assertFalse(summary["recount"]["agrees"])

    def test_summarize_run_recount_uses_the_events_own_start_ns(self):
        # A fill at 40s past start_ns=0 is minute 0 by both the strategy's
        # events and a correctly-start_ns-anchored report row: this must
        # agree. (If recount_fills_from_report's start_ns argument were ever
        # shifted -- e.g. by 30s, as in a prior regression -- this same fill
        # would land in a different minute than the strategy's own bucket for
        # it, and this assertion would catch that by going False.)
        result = self._synthetic_result(submit_ts_ns=10_000_000_000, fill_ts_ns=40_000_000_000,
                                         report_ts_ns=40_000_000_000)
        summary = self.runner.summarize_run(result, self._synthetic_quotes())
        self.assertTrue(summary["recount"]["agrees"])

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


@unittest.skipUnless(_pinned_runtime_active(), "requires the pinned nautilus_trader==2.0.0rc5 runtime")
class RealVenueRunOneTests(unittest.TestCase):
    """Calls `runner.run_one` directly -- the real production function, with
    its real venue/risk/fee configuration (not a hand-built engine with, e.g.,
    latency_model=None) -- on a small synthetic quote set. Covers the
    reviewer's explicit checklist: fill qty <= displayed size; fill ts >=
    submit + latency; no fill beats the touch (H1); fees on sells only for the
    paper-parity (commission_plan="none") profile; an independent recount;
    TIF is IOC; and the configured budget values."""

    DISPLAYED_SIZE = 3  # tight enough that "fill qty <= displayed size" is a real check

    @classmethod
    def setUpClass(cls):
        cls.runner = _load("sim_capacity_runner_realvenue", "runner.py")
        symbols = ["AAPL", "MSFT"]
        quotes = {}
        for s in symbols:
            rows = []
            for i in range(3000):  # 3000 * 20ms = 60s of quotes
                ts = i * 20_000_000
                rows.append({"symbol": s, "ts_ns": ts, "bid": "100.00", "ask": "100.02",
                             "bid_size": cls.DISPLAYED_SIZE, "ask_size": cls.DISPLAYED_SIZE})
            quotes[s] = rows
        cls.quotes = quotes
        cls.result = cls.runner.run_one(quotes, {}, profile_name="paper-parity", latency_ms=70, run_seconds=20.0)

    def test_fill_qty_never_exceeds_displayed_size(self):
        fills = [e for e in self.result["events"] if e["kind"] == "fill"]
        self.assertGreater(len(fills), 0)
        self.assertTrue(all(f["qty"] <= self.DISPLAYED_SIZE for f in fills))

    def test_fill_ts_never_precedes_submit_plus_latency(self):
        latency_ns = self.result["latency_ms"] * 1_000_000
        submits = {e["client_order_id"]: e["ts_ns"] for e in self.result["events"] if e["kind"] == "submit"}
        fills = [e for e in self.result["events"] if e["kind"] == "fill"]
        for f in fills:
            self.assertGreaterEqual(f["ts_ns"], submits[f["client_order_id"]] + latency_ns)

    def test_no_fill_beats_the_nbbo_touch(self):
        check = self.runner.check_no_fill_beats_nbbo_touch(self.result["events"], self.quotes)
        self.assertGreater(check["checked"], 0)
        self.assertEqual(check["violation_count"], 0, check["violations"])

    def test_fees_charged_on_sells_only_at_commission_plan_none(self):
        # paper-parity uses commission_plan="none": CAT alone rounds to 0.00 at
        # this run's tiny (<=3 share) fills, so BUY fees must be exactly 0.00
        # while SELL fees (SEC+TAF) must be nonzero.
        fills = [e for e in self.result["events"] if e["kind"] == "fill"]
        buys = [f for f in fills if f["side"] == "BUY"]
        sells = [f for f in fills if f["side"] == "SELL"]
        self.assertGreater(len(buys), 0)
        self.assertGreater(len(sells), 0)
        self.assertTrue(all(f["fee_usd"] == "0.00" for f in buys))
        self.assertTrue(all(f["fee_usd"] != "0.00" for f in sells))

    def test_independent_recount_agrees(self):
        summary = self.runner.summarize_run(self.result, self.quotes)
        self.assertTrue(summary["recount"]["agrees"])

    def test_every_exerciser_order_is_ioc(self):
        self.assertIn("IOC", self.result["tif_counts"])
        self.assertEqual(sum(self.result["tif_counts"].values()), self.result["tif_counts"]["IOC"])

    def test_venue_realism_flags_are_all_on(self):
        # A direct source-level regression guard on run_one's add_venue call:
        # liquidity_consumption is the one flag measured to actually change
        # results in this quotes-only, IOC-only setup (see README.md); all
        # three are still pinned on here so a silent drop of any of them (a
        # config-literal regression that a same-process behavioral test on a
        # single-order-per-instant synthetic book would not reliably surface)
        # is caught directly.
        source = (SIM_CAPACITY / "runner.py").read_text()
        self.assertIn("trade_execution=True, liquidity_consumption=True,", source)
        self.assertIn("queue_position=True", source)

    def test_configured_budget_values(self):
        self.assertEqual(self.runner.PROFILES["paper-parity"]["max_order_submit_rate"], "180/00:01:00")
        self.assertEqual(self.runner.PROFILES["elite-tier"]["max_order_submit_rate"], "900/00:01:00")
        self.assertEqual(self.runner.PRIMARY_LATENCY_MS, 70)

    def test_latency_model_actually_delays_fills(self):
        # A separate, explicit latency_ms (not the module's PRIMARY_LATENCY_MS
        # constant) directly exercises the StaticLatencyModel wiring: if it
        # were ever forced to None regardless of latency_ms (a prior
        # regression class), fills would arrive before submit + 100ms.
        result = self.runner.run_one(self.quotes, {}, profile_name="paper-parity", latency_ms=100, run_seconds=15.0)
        submits = {e["client_order_id"]: e["ts_ns"] for e in result["events"] if e["kind"] == "submit"}
        fills = [e for e in result["events"] if e["kind"] == "fill"]
        self.assertGreater(len(fills), 0)
        for f in fills:
            self.assertGreaterEqual(f["ts_ns"] - submits[f["client_order_id"]], 100_000_000)


if __name__ == "__main__":
    unittest.main()
