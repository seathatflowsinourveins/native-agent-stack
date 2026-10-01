"""Offline tests for the sim-capacity infrastructure lane (blueprints/us-equities/
sim-capacity). Most classes here use no network, no credential file and no
NautilusTrader runtime; the two runtime-gated classes at the bottom skip
themselves cleanly when the active interpreter is not the pinned
nautilus_trader==2.0.0rc5 runtime, matching tests.test_sim_paper_compare's
pattern.
"""
import importlib.metadata
import importlib.util
import json
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

    def test_clamp_sell_quantity_respects_reserved_in_flight(self):
        # M3 regression (concurrent in-flight sells): a desired sell of 5
        # shares against an actual position of 5, but with 3 already
        # reserved by another in-flight SELL for the same symbol (sellable
        # position = 5 - 3 = 2), must clamp to 2, not 5.
        self.assertEqual(SCH.clamp_sell_quantity(desired_qty=5, sellable_position=2), 2)

    def test_clamp_sell_quantity_never_negative(self):
        # Fully reserved (sellable_position <= 0): clamp to 0, not a negative
        # "sell" quantity.
        self.assertEqual(SCH.clamp_sell_quantity(desired_qty=5, sellable_position=0), 0)
        self.assertEqual(SCH.clamp_sell_quantity(desired_qty=5, sellable_position=-2), 0)

    def test_clamp_sell_quantity_is_a_noop_when_ample(self):
        self.assertEqual(SCH.clamp_sell_quantity(desired_qty=3, sellable_position=100), 3)


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
        # Forcing _last_side="BUY" is the discriminating case: plain
        # alternation (BUY -> SELL) would propose SELL here, so this only
        # passes because the inventory rule overrides alternation at
        # position <= 0. (Forcing _last_side="SELL" instead would make plain
        # alternation itself return BUY too, which would pass even with the
        # inventory rule reverted -- proving nothing about the rule.)
        rr = SCH.RoundRobin(["A"], position_cap=50)
        for position in (0, -1, -5):
            rr._last_side["A"] = "BUY"
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

    def test_summarize_run_recount_detects_a_10s_start_shift(self):
        # A fill at 55s past start_ns=0 is minute 0 both by the strategy's
        # events and a correctly-anchored report row -- but shifting the
        # recount's start_ns by only 10s (55 + 10 = 65s) already crosses the
        # 60s minute boundary into minute 1, unlike the 40s fill used by
        # test_summarize_run_recount_uses_the_events_own_start_ns (which a
        # 10s shift does not move into a different minute, only a 30s+
        # shift). This is the case that actually distinguishes a 10s
        # regression from a 30s one.
        result = self._synthetic_result(submit_ts_ns=50_000_000_000, fill_ts_ns=55_000_000_000,
                                         report_ts_ns=55_000_000_000)
        summary = self.runner.summarize_run(result, self._synthetic_quotes())
        self.assertTrue(summary["recount"]["agrees"])

    def test_fills_per_minute_stats(self):
        stats = self.runner.fills_per_minute_stats({0: 180, 1: 200, 2: 100}, total_full_minutes=3)
        self.assertEqual(stats["min"], 100)
        self.assertEqual(stats["max"], 200)
        self.assertEqual(stats["median"], 180)
        self.assertEqual(stats["full_minutes_at_or_above_180"], 2)


# ---------------------------------------------------------------------------
# README latency-sweep table vs the committed receipt (no engine needed --
# pure file parsing, so this runs on system Python too)
# ---------------------------------------------------------------------------

class ReadmeReceiptDriftTests(unittest.TestCase):
    def test_readme_latency_sweep_table_matches_receipt(self):
        # A stale copy of this exact table (README.md's elite-tier latency
        # sweep) was caught by review once already (a hand-retyped 1000ms row
        # no longer matched the committed receipt). This test reads both and
        # asserts every row still agrees, so a future edit to one without the
        # other fails the suite instead of silently drifting.
        import re

        readme = (SIM_CAPACITY / "README.md").read_text()
        receipt = json.loads((SIM_CAPACITY / "receipts/20260925-elite-tier.json").read_text())
        by_latency = {row["latency_ms"]: row["fills_per_minute_stats"]
                      for row in receipt["latency_sensitivity_elite_tier"]}
        self.assertTrue(by_latency, "receipt has no latency_sensitivity_elite_tier rows")

        row_re = re.compile(r"^\|\s*(\d+)(?:\s*\(primary\))?\s*\|\s*(\d+)\s*\|\s*([\d.]+)\s*\|\s*(\d+)\s*\|\s*(\d+)/30\s*\|\s*$",
                            re.M)
        found = {}
        for m in row_re.finditer(readme):
            latency_ms, min_v, median_v, max_v, full_v = m.groups()
            found[int(latency_ms)] = {"min": int(min_v), "median": float(median_v), "max": int(max_v),
                                      "full_minutes_at_or_above_180": int(full_v)}
        self.assertEqual(set(found), set(by_latency), "README table latencies must match the receipt's")
        for latency_ms, readme_stats in found.items():
            receipt_stats = by_latency[latency_ms]
            for key in ("min", "median", "max", "full_minutes_at_or_above_180"):
                self.assertEqual(readme_stats[key], receipt_stats[key],
                                 f"README latency-sweep row for {latency_ms}ms.{key} does not match the receipt")


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

    DISPLAYED_SIZE = 7  # max of the cycled sizes below; still tight enough that
    # "fill qty <= displayed size" is a real check

    @classmethod
    def setUpClass(cls):
        cls.runner = _load("sim_capacity_runner_realvenue", "runner.py")
        symbols = ["AAPL", "MSFT"]
        quotes = {}
        for s in symbols:
            rows = []
            for i in range(3000):  # 3000 * 20ms = 60s of quotes
                ts = i * 20_000_000
                # Cycle displayed size 3,4,5,6,7,3,4,... (never a constant
                # repeated (price, size) pair) -- see README.md's Limitations
                # section: on the pinned rc5 engine, a book level's consumed
                # tally under liquidity_consumption=True resets only when its
                # displayed size actually changes; an unmodified, constant
                # quote every tick was measured to lock up after literally 4
                # fills (95-99% of every subsequent order then expiring for
                # the rest of the run), which would have made every
                # behavioral assertion in this class rest on those same 4
                # fills. A plain two-value alternation (3,4,3,4,...) was
                # tried and measured to still lock up; a wider 5-value cycle
                # was measured to sustain fills throughout the run instead.
                size = 3 + (i % 5)
                rows.append({"symbol": s, "ts_ns": ts, "bid": "100.00", "ask": "100.02",
                             "bid_size": size, "ask_size": size})
            quotes[s] = rows
        cls.quotes = quotes
        cls.result = cls.runner.run_one(quotes, {}, profile_name="paper-parity",
                                         latency_ms=cls.runner.PRIMARY_LATENCY_MS, run_seconds=20.0)

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
        # paper-parity uses commission_plan="none": every fill's engine-charged
        # fee must exactly match an independent recomputation via
        # fee_model.commission_usd (CAT on both sides, SEC+TAF sells only).
        # Some individual sells round to "0.00" at a small enough partial-fill
        # quantity, so the meaningful assertion is exact-match-per-fill, not a
        # blanket "sells are always nonzero" -- SELL fees must still be
        # strictly higher on average than BUY fees at comparable quantities.
        fills = [e for e in self.result["events"] if e["kind"] == "fill"]
        buys = [f for f in fills if f["side"] == "BUY"]
        sells = [f for f in fills if f["side"] == "SELL"]
        self.assertGreater(len(buys), 0)
        self.assertGreater(len(sells), 0)
        for f in fills:
            expected = FM.commission_usd(side=f["side"], quantity=f["qty"], price=f["price"], commission_plan="none")
            self.assertEqual(Decimal(f["fee_usd"]), expected, f)
        self.assertGreater(sum(Decimal(f["fee_usd"]) for f in sells), sum(Decimal(f["fee_usd"]) for f in buys))

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

    def test_run_one_excludes_trade_ticks_even_when_provided(self):
        # H1 regression guard: build a trades_by_symbol input containing a
        # sub-penny print (rounding to 100.00, the current bid) injected
        # *mid-gap* between sparse quotes -- exactly the condition under which
        # the rc5 book-overwrite bug persists long enough to be the book state
        # an order actually matches against (a dense, every-20ms quote
        # schedule "heals" the corruption before any latency-delayed order can
        # land in it, which is why RealVenueRunOneTests' shared dense fixture
        # alone would not reproduce H1 even with trades reintroduced) -- and
        # confirm the production run_one still excludes it entirely: every
        # fill is at its clean touch, with zero NBBO-touch violations. This
        # reproduces a real violation when the anchor mutation (mutate.py's
        # X1: trade ticks fed back into run_one) is manually applied (43 of
        # 174 fills beat the touch), and passes cleanly against the real,
        # unmutated run_one.
        symbols = ["AAPL", "MSFT"]
        quotes, trades = {}, {}
        gap_ns = 2_000_000_000  # 2s between quotes: long enough for a mid-gap
        for s in symbols:                                        # trade's corruption to persist past a 70ms latency
            rows, trows = [], []
            for i in range(20):  # 40s of sparse quotes
                ts = i * gap_ns
                rows.append({"symbol": s, "ts_ns": ts, "bid": "100.00", "ask": "100.02",
                             "bid_size": 500, "ask_size": 500})
                trows.append({"symbol": s, "ts_ns": ts + 1_000_000_000, "price": "100.0001",
                              "size": 500, "trade_id": f"{s}-{i}"})
            quotes[s], trades[s] = rows, trows
        result = self.runner.run_one(quotes, trades, profile_name="paper-parity",
                                      latency_ms=self.runner.PRIMARY_LATENCY_MS, run_seconds=35.0)
        fills = [e for e in result["events"] if e["kind"] == "fill"]
        self.assertGreater(len(fills), 20)
        check = self.runner.check_no_fill_beats_nbbo_touch(fills, quotes)
        self.assertEqual(check["checked"], len(fills))
        self.assertEqual(check["violation_count"], 0, check["violations"])

    def test_touch_guard_detects_an_injected_violation(self):
        # The guard itself must actually flag a genuine violation, not just
        # stay silent on real (clean) data. A single BUY fill priced strictly
        # below the ask in force is exactly the H1 artifact this guard exists
        # to catch.
        quotes = {"AAPL": [{"symbol": "AAPL", "ts_ns": 0, "bid": "100.00", "ask": "100.02",
                            "bid_size": 100, "ask_size": 100}]}
        events = [{"ts_ns": 0, "kind": "fill", "client_order_id": "CAP-1", "side": "BUY",
                   "price": "100.01", "instrument_id": "AAPL.SIM", "qty": 1}]  # better than the 100.02 ask
        check = self.runner.check_no_fill_beats_nbbo_touch(events, quotes)
        self.assertEqual(check["checked"], 1)
        self.assertEqual(check["violation_count"], 1)

    def test_touch_guard_same_ns_quotes_are_not_a_false_positive(self):
        # M1 regression: two quotes can legitimately share one nanosecond
        # timestamp (1,342 such pairs measured in the real fetched data). A
        # fill that is at-or-through the touch of EITHER same-ns quote must
        # not be flagged, even though it beats the OTHER same-ns quote's touch
        # (the guard cannot observe which of the two the engine actually
        # matched against).
        quotes = {"AAPL": [{"symbol": "AAPL", "ts_ns": 1000, "bid": "100.00", "ask": "100.05"},
                           {"symbol": "AAPL", "ts_ns": 1000, "bid": "100.00", "ask": "100.02"}]}
        # A BUY fill at 100.02 beats the first quote's 100.05 ask, but is
        # exactly at-touch for the second quote sharing the same timestamp.
        events = [{"ts_ns": 1000, "kind": "fill", "client_order_id": "CAP-1", "side": "BUY",
                   "price": "100.02", "instrument_id": "AAPL.SIM", "qty": 1}]
        check = self.runner.check_no_fill_beats_nbbo_touch(events, quotes)
        self.assertEqual(check["checked"], 1)
        self.assertEqual(check["violation_count"], 0, check["violations"])

    def test_elite_commission_is_applied_to_fills(self):
        # commission_plan="all_in" for elite-tier applies to BOTH sides (not
        # sells-only like SEC/TAF): a BUY fill's fee must be nonzero here,
        # unlike the paper-parity ("none" plan) case above.
        result = self.runner.run_one(self.quotes, {}, profile_name="elite-tier",
                                      latency_ms=self.runner.PRIMARY_LATENCY_MS, run_seconds=15.0)
        buys = [e for e in result["events"] if e["kind"] == "fill" and e["side"] == "BUY"]
        self.assertGreater(len(buys), 0)
        self.assertTrue(all(f["fee_usd"] != "0.00" for f in buys))

    def test_paper_parity_denial_count_matches_the_180_per_minute_budget(self):
        # Behavioral pin of the actual configured budget (replacing a bare
        # constant-equality check where a real run's outcome can serve the
        # same purpose). The native limiter is a token bucket that starts
        # FULL at the configured limit (not prorated to elapsed time), so no
        # denial can occur until cumulative submits exceed the 180 budget:
        # at 5 submits/sec for 45s (~225 attempts), ~180 should be admitted
        # and ~45 denied. A materially different default budget (mutate.py's
        # X4: RiskEngineConfig() with run_one's profile-budget wiring
        # dropped) would miss this band by a wide margin.
        result = self.runner.run_one(self.quotes, {}, profile_name="paper-parity",
                                      latency_ms=self.runner.PRIMARY_LATENCY_MS, run_seconds=45.0)
        denied = result["counters"].get("rate_limit_denied", 0)
        submits = result["counters"].get("submits", 0)
        self.assertGreater(submits, 200)
        self.assertTrue(25 <= denied <= 65, f"submits={submits} denied={denied}")

    def test_no_short_sale_rejects_with_concurrent_sells_in_flight(self):
        # M3 regression: at a higher cadence (elite-tier) and a long enough
        # latency (1000ms) that several sells for the same symbol can be
        # submitted before any of them resolve, the reservation-based clamp
        # (not just the plain position clamp) must still prevent every
        # short-sale reject.
        #
        # Deliberately uses its own small, constant (unvarying) quote --
        # *not* the class-shared `self.quotes` fixture -- because a thin,
        # slowly-replenishing position is exactly what exposes this race:
        # the shared fixture's now-abundant, always-replenishing liquidity
        # (see the class docstring and README.md's Limitations section) lets
        # inventory grow large enough, fast enough, that even a *reverted*
        # reservation mechanism never actually oversells in that fixture
        # (measured directly: this exact mutation went uncaught once the
        # shared fixture was fixed to vary size). This fixture's own
        # liquidity-lock quirk is what keeps positions thin here, which is
        # the genuinely discriminating condition for this specific race.
        quotes = {}
        for s in ("AAPL", "MSFT"):
            quotes[s] = [{"symbol": s, "ts_ns": i * 20_000_000, "bid": "100.00", "ask": "100.02",
                         "bid_size": 3, "ask_size": 3} for i in range(3000)]
        result = self.runner.run_one(quotes, {}, profile_name="elite-tier",
                                      latency_ms=1000, run_seconds=20.0)
        reject_reasons = {}
        for ev in result["events"]:
            if ev["kind"] == "reject":
                reject_reasons[ev["reason"]] = reject_reasons.get(ev["reason"], 0) + 1
        self.assertEqual(result["counters"].get("rejects", 0), 0, reject_reasons)
        self.assertFalse(any("Short selling not permitted on a CASH account" in r for r in reject_reasons),
                         reject_reasons)

    def test_clamp_binds_with_asymmetric_buy_sell_sizes(self):
        # LOW#3: the two tests above exercise the in-flight *reservation*, not
        # the qty *clamp* itself -- disabling the clamp alone (mutate.py's
        # X6a/b/c) was measured to still pass the whole suite, since neither
        # existing fixture ever proposes a SELL for more than is genuinely
        # held. This fixture forces it directly: ask size (buys) cycles
        # 2..6, bid size (sells) cycles 5..9 -- always bigger -- so a SELL
        # decision's displayed-size-derived desired quantity habitually
        # exceeds a thin position built from smaller buys. Disabling the
        # clamp on this exact fixture was measured to produce 44 short-sale
        # rejects (out of 332 submits, latency 70ms); the real, unmutated
        # clamp must produce zero.
        quotes = {"AAPL": []}
        for i in range(3000):
            ts = i * 20_000_000
            ask_size = 2 + (i % 5)
            bid_size = 5 + (i % 5)
            quotes["AAPL"].append({"symbol": "AAPL", "ts_ns": ts, "bid": "100.00", "ask": "100.02",
                                   "bid_size": bid_size, "ask_size": ask_size})
        result = self.runner.run_one(quotes, {}, profile_name="elite-tier",
                                      latency_ms=self.runner.PRIMARY_LATENCY_MS, run_seconds=20.0)
        reject_reasons = {}
        for ev in result["events"]:
            if ev["kind"] == "reject":
                reject_reasons[ev["reason"]] = reject_reasons.get(ev["reason"], 0) + 1
        self.assertGreater(result["counters"].get("submits", 0), 100)
        self.assertEqual(result["counters"].get("rejects", 0), 0, reject_reasons)
        self.assertFalse(any("Short selling not permitted on a CASH account" in r for r in reject_reasons),
                         reject_reasons)


@unittest.skipUnless(_pinned_runtime_active(), "requires the pinned nautilus_trader==2.0.0rc5 runtime")
class ExactReleaseTimingTests(unittest.TestCase):
    """Direct coverage of `CapacityExerciserParams.release_alert_latency_ns`
    and `runner.run_one`'s `exact_release` parameter -- the fix for the
    measured rc5 release-on-next-event timing slack (see README.md's Latency
    section, exerciser.py's `release_alert_latency_ns` comment, and
    sim-engine-crosscheck/run_nautilus.py's `exact_latency`, which isolated
    the same finding: extra delay of median 28ms SPY / 53ms NVDA, p90
    135ms/263ms).

    Uses its own, deliberately SPARSE synthetic quote set (400ms per symbol)
    -- much sparser than either profile's own submit-tick interval (200ms
    paper-parity, 60ms elite-tier) -- so the pre-fix "release at the next
    quote or any due timer" mechanism has real, deterministic slack to show:
    an order submitted on a tick has its submit+latency instant fall between
    quotes, so the next actual release trigger (the following tick timer or
    the following sparse quote, whichever is first) lands measurably later
    than submit+latency. The shared dense (20ms) RealVenueRunOneTests
    fixture would not reliably show this, since its next quote almost always
    arrives within a few ms of submit+latency in either release mode."""

    LATENCY_MS = 70

    @classmethod
    def setUpClass(cls):
        cls.runner = _load("sim_capacity_exact_release_runner", "runner.py")
        symbols = ["AAPL", "MSFT"]
        quotes = {}
        for s in symbols:
            rows = []
            for i in range(90):  # 90 * 400ms = 36s of sparse quotes
                ts = i * 400_000_000
                size = 20 + (i % 5)  # vary size tick-to-tick -- see README's
                # Limitations section: an unvarying (price, size) quote can
                # lock up liquidity_consumption's per-price consumed tally.
                rows.append({"symbol": s, "ts_ns": ts, "bid": "100.00", "ask": "100.02",
                             "bid_size": size, "ask_size": size})
            quotes[s] = rows
        cls.quotes = quotes

    @staticmethod
    def _submits_and_fills(result):
        submits = {e["client_order_id"]: e["ts_ns"] for e in result["events"] if e["kind"] == "submit"}
        fills = [e for e in result["events"] if e["kind"] == "fill"]
        return submits, fills

    def test_exact_release_resolves_every_fill_at_exactly_submit_plus_latency(self):
        # exact_release defaults to True: this is the production default.
        result = self.runner.run_one(self.quotes, {}, profile_name="paper-parity",
                                      latency_ms=self.LATENCY_MS, run_seconds=20.0)
        self.assertTrue(result["exact_release"])
        latency_ns = self.LATENCY_MS * 1_000_000
        self.assertEqual(result["release_alert_latency_ns"], latency_ns)
        submits, fills = self._submits_and_fills(result)
        self.assertGreater(len(fills), 0)
        for f in fills:
            self.assertEqual(f["ts_ns"] - submits[f["client_order_id"]], latency_ns, f)
        check = self.runner.check_release_timing(result["events"], self.LATENCY_MS,
                                                   result["release_alert_latency_ns"])
        self.assertEqual(check["checked"], len(fills))
        self.assertTrue(check["exact_release_expected"])
        self.assertEqual(check["early_violation_count"], 0, check["early_violations"])
        self.assertEqual(check["inexact_violation_count"], 0, check["inexact_violations"])

    def test_legacy_release_resolves_some_fills_later_than_exact(self):
        # Same sparse quote set, same latency, exact_release=False (the
        # --release-timing legacy CLI switch): fills must never arrive before
        # submit + latency, but on this sparse fixture at least one fill must
        # resolve strictly LATER -- real, measured release-on-next-event
        # slack, not merely "not proven exact."
        result = self.runner.run_one(self.quotes, {}, profile_name="paper-parity",
                                      latency_ms=self.LATENCY_MS, run_seconds=20.0, exact_release=False)
        self.assertFalse(result["exact_release"])
        self.assertEqual(result["release_alert_latency_ns"], 0)
        latency_ns = self.LATENCY_MS * 1_000_000
        submits, fills = self._submits_and_fills(result)
        self.assertGreater(len(fills), 0)
        deltas_ns = [f["ts_ns"] - submits[f["client_order_id"]] for f in fills]
        self.assertTrue(all(d >= latency_ns for d in deltas_ns), deltas_ns)
        self.assertTrue(any(d > latency_ns for d in deltas_ns), deltas_ns)
        check = self.runner.check_release_timing(result["events"], self.LATENCY_MS,
                                                   result["release_alert_latency_ns"])
        self.assertFalse(check["exact_release_expected"])
        self.assertEqual(check["early_violation_count"], 0, check["early_violations"])

    def test_summarize_run_reports_release_timing_for_both_modes(self):
        exact_result = self.runner.run_one(self.quotes, {}, profile_name="paper-parity",
                                            latency_ms=self.LATENCY_MS, run_seconds=15.0)
        legacy_result = self.runner.run_one(self.quotes, {}, profile_name="paper-parity",
                                             latency_ms=self.LATENCY_MS, run_seconds=15.0, exact_release=False)
        exact_summary = self.runner.summarize_run(exact_result, self.quotes)
        legacy_summary = self.runner.summarize_run(legacy_result, self.quotes)
        self.assertTrue(exact_summary["release_timing"]["exact_release"])
        self.assertEqual(exact_summary["release_timing"]["release_alert_latency_ns"], self.LATENCY_MS * 1_000_000)
        self.assertEqual(exact_summary["release_timing"]["check"]["inexact_violation_count"], 0)
        self.assertFalse(legacy_summary["release_timing"]["exact_release"])
        self.assertEqual(legacy_summary["release_timing"]["release_alert_latency_ns"], 0)
        self.assertFalse(legacy_summary["release_timing"]["check"]["exact_release_expected"])


@unittest.skipUnless(_pinned_runtime_active(), "requires the pinned nautilus_trader==2.0.0rc5 runtime")
class CmdRunIntegrationTests(unittest.TestCase):
    """End-to-end `runner.cmd_run` calls against a small synthetic private
    catalog (a temp dir with quotes/trades JSON and a fetch-manifest.json),
    written and read exactly like the real CLI path. Catches regressions in
    cmd_run's own wiring that a call to run_one alone cannot -- e.g.
    mutate.py's X3 (cmd_run's primary run hardcoded to latency_ms=0 instead of
    using PRIMARY_LATENCY_MS)."""

    @classmethod
    def setUpClass(cls):
        cls.runner = _load("sim_capacity_runner_cmdrun", "runner.py")
        import tempfile
        symbols = ["AAPL", "MSFT"]
        quotes = {}
        for s in symbols:
            rows = []
            for i in range(420):  # every 5s for 2100s: covers a 30min run plus its flatten pad
                ts = i * 5_000_000_000
                rows.append({"symbol": s, "ts_ns": ts, "bid": "100.00", "ask": "100.02",
                             "bid_size": 500, "ask_size": 500})
            quotes[s] = rows
        trades = {s: [] for s in symbols}
        cls._tmpdir = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls._tmpdir.cleanup)  # always removed, even on failure/error
        cls.tmp = Path(cls._tmpdir.name)
        (cls.tmp / "quotes.private.json").write_text(json.dumps(quotes))
        (cls.tmp / "trades.private.json").write_text(json.dumps(trades))
        manifest = {
            "window": {"start": "2026-09-24T14:00:00Z", "end": "2026-09-24T14:30:00Z"}, "symbols": symbols,
            "quote_counts": {s: len(quotes[s]) for s in symbols}, "trade_counts": {s: 0 for s in symbols},
            "quote_drop_counts": {s: {"one_sided_or_nonpositive": 0, "crossed": 0} for s in symbols},
            "trade_drop_counts": {s: {"nonpositive": 0} for s in symbols},
            "page_events": {"this_run_page_count": 0, "this_run_page_hashes": [], "this_run_page_hashes_digest": "x"},
        }
        (cls.tmp / "fetch-manifest.json").write_text(json.dumps(manifest))

    def _run(self, profile: str):
        import argparse
        receipt_path = self.tmp / f"receipt-{profile}.json"
        args = argparse.Namespace(command="run", catalog=self.tmp, receipt=receipt_path, profile=profile,
                                  env_file=None, pages=None, out=None, replay=False, latency_ms=None)
        self.runner.cmd_run(args)
        return json.loads(receipt_path.read_text())

    def test_primary_run_uses_the_configured_primary_latency(self):
        receipt = self._run("paper-parity")
        self.assertEqual(receipt["runs"][0]["latency_ms"], self.runner.PRIMARY_LATENCY_MS)
        self.assertNotEqual(receipt["runs"][0]["latency_ms"], 0)


@unittest.skipUnless(_pinned_runtime_active(), "requires the pinned nautilus_trader==2.0.0rc5 runtime")
class SellReservationBookkeepingTests(unittest.TestCase):
    """Pure bookkeeping tests for CapacityExerciser's in-flight-sell
    reservation tracking (`_reserved_sell_qty`/`_sell_reservations`), which
    needs no engine or cache access -- only the exerciser module import
    (hence still pinned-runtime-gated)."""

    @classmethod
    def setUpClass(cls):
        cls.exerciser_module = _load("sim_capacity_exerciser_reservation", "exerciser.py")
        cls.CapacityExerciser = cls.exerciser_module.CapacityExerciser
        cls.RoundRobin = SCH.RoundRobin

    def _bare_exerciser(self):
        # Bypass __init__ (which needs a registered Strategy/trader) since the
        # reservation dicts and their release logic touch no cache/portfolio
        # state at all.
        ex = self.CapacityExerciser.__new__(self.CapacityExerciser)
        from collections import defaultdict
        ex._reserved_sell_qty = defaultdict(int)
        ex._sell_reservations = {}
        return ex

    def test_reservation_accumulates_and_releases_per_order(self):
        ex = self._bare_exerciser()
        ex._reserved_sell_qty["AAPL"] += 3
        ex._sell_reservations["CAP-1"] = ("AAPL", 3)
        ex._reserved_sell_qty["AAPL"] += 2
        ex._sell_reservations["CAP-2"] = ("AAPL", 2)
        self.assertEqual(ex._reserved_sell_qty["AAPL"], 5)
        ex._release_sell_reservation("CAP-1")
        self.assertEqual(ex._reserved_sell_qty["AAPL"], 2)
        ex._release_sell_reservation("CAP-2")
        self.assertEqual(ex._reserved_sell_qty["AAPL"], 0)

    def test_release_is_idempotent(self):
        ex = self._bare_exerciser()
        ex._reserved_sell_qty["AAPL"] += 4
        ex._sell_reservations["CAP-1"] = ("AAPL", 4)
        ex._release_sell_reservation("CAP-1")
        ex._release_sell_reservation("CAP-1")  # second release: harmless no-op
        self.assertEqual(ex._reserved_sell_qty["AAPL"], 0)

    def test_release_is_scoped_per_symbol(self):
        ex = self._bare_exerciser()
        ex._reserved_sell_qty["AAPL"] += 3
        ex._sell_reservations["CAP-1"] = ("AAPL", 3)
        ex._reserved_sell_qty["MSFT"] += 5
        ex._sell_reservations["CAP-2"] = ("MSFT", 5)
        ex._release_sell_reservation("CAP-1")
        self.assertEqual(ex._reserved_sell_qty["AAPL"], 0)
        self.assertEqual(ex._reserved_sell_qty["MSFT"], 5)

    def test_on_tick_uses_clamp_sell_quantity_for_the_sell_branch(self):
        # Source-contract companion to SCH.clamp_sell_quantity's own direct
        # unit tests (ScheduleMathTests): confirms _on_tick's SELL branch
        # actually calls the shared pure clamp function, rather than some
        # unclamped or differently-computed quantity. Strategy's cache/
        # portfolio/clock attributes are not writable outside a registered
        # engine (verified directly), which is why the clamp arithmetic
        # itself is factored out and unit-tested as a pure function instead
        # of by driving _on_tick with a faked self.
        source = (SIM_CAPACITY / "exerciser.py").read_text()
        self.assertIn("qty = clamp_sell_quantity(qty, sellable_position)", source)


if __name__ == "__main__":
    unittest.main()
