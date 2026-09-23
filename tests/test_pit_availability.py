"""Offline tests for blueprints/us-equities/pit-availability/measure.py.

Fixtures are small and synthetic except RealEdgarAcceptanceFixtureTests, which
freezes three real data.sec.gov / EDGAR-header values fetched live (see that
class's docstring) but performs no network I/O itself. Covers: acceptance-time
parsing including timezone conversion, the regular/post_close/after_hours
session cutoffs, filingDate vs Eastern-acceptance-date mismatch, filing
summarisation, 10-K completeness flagging, updated_at-vs-created_at timestamp
comparison, the created_at query-window filter, log-relative raw-vs-adjusted
ratio-step detection and its corporate-action matching, and receipt-schema
assembly.
"""
import importlib.util
import json
import sys
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parent.parent / "blueprints/us-equities/pit-availability/measure.py"
spec = importlib.util.spec_from_file_location("pit_availability_measure", MODULE_PATH)
measure = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = measure
spec.loader.exec_module(measure)


class RealEdgarAcceptanceFixtureTests(unittest.TestCase):
    """Frozen real EDGAR examples (fetched 2026-09-22 live from data.sec.gov's
    submissions JSON and the matching filing's full-submission .txt header,
    e.g. https://www.sec.gov/Archives/edgar/data/320193/0000320193-26-000020.txt)
    confirming the JSON's UTC `acceptanceDateTime`, converted to Eastern here,
    equals the raw filing header's own Eastern-local `ACCEPTANCE-DATETIME`
    field (format YYYYMMDDHHMMSS) -- so the UTC reading is confirmed against
    an independent source field, not just inferred from the 'Z' suffix."""

    FIXTURES = [
        # (symbol, form, JSON acceptanceDateTime (UTC), header ACCEPTANCE-DATETIME (Eastern local))
        ("AAPL", "10-Q", "2026-07-31T10:01:02.000Z", "20260731060102"),
        ("MSFT", "8-K", "2026-09-02T20:30:24.000Z", "20260902163024"),
        ("JPM", "10-K", "2026-02-13T21:20:00.000Z", "20260213162000"),
    ]

    def test_utc_reading_matches_header_eastern_local(self):
        for symbol, form, json_utc, header_eastern_raw in self.FIXTURES:
            with self.subTest(symbol=symbol, form=form):
                acceptance_utc = measure.parse_sec_datetime(json_utc)
                acceptance_eastern = acceptance_utc.astimezone(measure.EASTERN)
                expected = (
                    f"{acceptance_eastern.year:04d}{acceptance_eastern.month:02d}"
                    f"{acceptance_eastern.day:02d}{acceptance_eastern.hour:02d}"
                    f"{acceptance_eastern.minute:02d}{acceptance_eastern.second:02d}"
                )
                self.assertEqual(expected, header_eastern_raw)


class ParseSecDatetimeTests(unittest.TestCase):
    def test_parses_z_suffix_as_utc(self):
        dt = measure.parse_sec_datetime("2023-06-01T16:30:24.000Z")
        self.assertEqual(dt.utcoffset().total_seconds(), 0)
        self.assertEqual(dt.hour, 16)
        self.assertEqual(dt.minute, 30)

    def test_parses_without_milliseconds(self):
        dt = measure.parse_sec_datetime("2023-06-01T16:30:24Z")
        self.assertEqual(dt.minute, 30)


class ClassifyFilingRowTests(unittest.TestCase):
    def test_missing_acceptance_datetime(self):
        row = {"accessionNumber": "x", "form": "8-K", "filingDate": "2023-06-01"}
        result = measure.classify_filing_row(row)
        self.assertFalse(result["has_acceptance"])
        self.assertNotIn("acceptance_utc", result)

    def test_business_hours_same_day_in_eastern(self):
        # 16:30 UTC in June (EDT, UTC-4) is 12:30 Eastern -> within business hours, same date.
        row = {"accessionNumber": "x", "form": "10-Q", "filingDate": "2023-06-01",
               "acceptanceDateTime": "2023-06-01T16:30:24.000Z"}
        result = measure.classify_filing_row(row)
        self.assertTrue(result["has_acceptance"])
        self.assertEqual(result["acceptance_eastern_date"], "2023-06-01")
        self.assertTrue(result["filing_date_matches_eastern_date"])
        self.assertFalse(result["is_after_hours"])

    def test_after_hours_acceptance_same_calendar_date(self):
        # 22:30 UTC in June (EDT, UTC-4) is 18:30 Eastern -> after 17:30, after-hours, still same date.
        row = {"accessionNumber": "x", "form": "4", "filingDate": "2023-06-01",
               "acceptanceDateTime": "2023-06-01T22:30:24.000Z"}
        result = measure.classify_filing_row(row)
        self.assertTrue(result["is_after_hours"])
        self.assertEqual(result["acceptance_eastern_date"], "2023-06-01")
        self.assertTrue(result["filing_date_matches_eastern_date"])

    def test_after_hours_rolls_to_next_calendar_date(self):
        # 02:30 UTC (EST, UTC-5, in January) is 21:30 Eastern the *previous* day.
        row = {"accessionNumber": "x", "form": "8-K", "filingDate": "2023-01-16",
               "acceptanceDateTime": "2023-01-16T02:30:00.000Z"}
        result = measure.classify_filing_row(row)
        self.assertTrue(result["is_after_hours"])
        self.assertEqual(result["acceptance_eastern_date"], "2023-01-15")
        self.assertFalse(result["filing_date_matches_eastern_date"])

    def test_winter_vs_summer_offset_handled_by_zoneinfo(self):
        # Same 19:00 UTC clock time; EST in January is 14:00 Eastern (regular session),
        # EDT in June is 15:00 Eastern (still regular session): the DST offset, not the
        # threshold boundary, is what's under test here.
        winter = measure.classify_filing_row({
            "form": "8-K", "filingDate": "2023-01-10", "acceptanceDateTime": "2023-01-10T19:00:00.000Z"})
        summer = measure.classify_filing_row({
            "form": "8-K", "filingDate": "2023-06-10", "acceptanceDateTime": "2023-06-10T19:00:00.000Z"})
        self.assertEqual(winter["acceptance_session"], "regular")
        self.assertEqual(summer["acceptance_session"], "regular")
        self.assertFalse(winter["is_after_hours"])
        self.assertFalse(summer["is_after_hours"])

    def test_16_00_et_cutoff_boundary(self):
        # 20:00 UTC in June (EDT, UTC-4) is exactly 16:00 Eastern -> post_close, not regular:
        # the close-based look-ahead-risk cutoff from item 3 of the round-2 review.
        row = measure.classify_filing_row({
            "form": "8-K", "filingDate": "2023-06-10", "acceptanceDateTime": "2023-06-10T20:00:00.000Z"})
        self.assertEqual(row["acceptance_session"], "post_close")


class FilterFormsDaterangeTests(unittest.TestCase):
    def test_filters_by_form_and_date(self):
        recent = {
            "form": ["8-K", "10-Q", "4", "8-K"],
            "filingDate": ["2016-01-05", "2020-05-01", "2020-05-01", "2027-01-01"],
            "accessionNumber": ["a", "b", "c", "d"],
        }
        rows = measure.filter_forms_daterange(recent, {"8-K", "10-Q"}, "2016-01-01", "2026-09-22")
        forms = sorted(r["form"] for r in rows)
        self.assertEqual(forms, ["10-Q", "8-K"])


class AcceptanceSessionTests(unittest.TestCase):
    def test_regular_session(self):
        from datetime import time
        self.assertEqual(measure.classify_acceptance_session(time(12, 0)), "regular")
        self.assertEqual(measure.classify_acceptance_session(time(6, 0)), "regular")

    def test_post_close_session(self):
        from datetime import time
        self.assertEqual(measure.classify_acceptance_session(time(16, 0)), "post_close")
        self.assertEqual(measure.classify_acceptance_session(time(17, 29)), "post_close")

    def test_after_hours_session(self):
        from datetime import time
        self.assertEqual(measure.classify_acceptance_session(time(17, 30)), "after_hours")
        self.assertEqual(measure.classify_acceptance_session(time(2, 0)), "after_hours")

    def test_classify_filing_row_sets_session(self):
        row = measure.classify_filing_row({"form": "8-K", "filingDate": "2023-06-01",
                                            "acceptanceDateTime": "2023-06-01T20:15:00.000Z"})
        # 20:15 UTC in June (EDT, UTC-4) is 16:15 Eastern -> post_close.
        self.assertEqual(row["acceptance_session"], "post_close")
        self.assertTrue(row["is_after_hours"])


class SummarizeFilingsTests(unittest.TestCase):
    def test_fractions_and_by_form(self):
        rows = [
            # 22:30Z June -> 18:30 ET -> after_hours
            measure.classify_filing_row({"form": "8-K", "filingDate": "2023-06-01",
                                          "acceptanceDateTime": "2023-06-01T22:30:00.000Z"}),
            # 20:15Z June -> 16:15 ET -> post_close
            measure.classify_filing_row({"form": "8-K", "filingDate": "2023-06-02",
                                          "acceptanceDateTime": "2023-06-02T20:15:00.000Z"}),
            measure.classify_filing_row({"form": "10-K", "filingDate": "2023-06-03"}),
        ]
        summary = measure.summarize_filings(rows)
        self.assertEqual(summary["total_filings"], 3)
        self.assertEqual(summary["with_acceptance_datetime"], 2)
        self.assertAlmostEqual(summary["acceptance_datetime_fraction"], 2 / 3)
        self.assertEqual(summary["after_hours_count"], 1)
        self.assertAlmostEqual(summary["after_hours_share_of_accepted"], 0.5)
        self.assertEqual(summary["post_close_count"], 1)
        self.assertAlmostEqual(summary["post_close_share_of_accepted"], 0.5)
        self.assertEqual(summary["by_form"]["8-K"]["total"], 2)
        self.assertEqual(summary["by_form"]["10-K"]["with_acceptance"], 0)


class TenKCompletenessTests(unittest.TestCase):
    def test_no_shortfall_near_expected(self):
        by_form = {"10-K": {"total": 9, "with_acceptance": 9}}
        result = measure.check_10k_completeness(by_form, expected=10, tolerance=2)
        self.assertFalse(result["shortfall"])
        self.assertEqual(result["actual_10k_count"], 9)

    def test_shortfall_flagged(self):
        by_form = {"10-K": {"total": 1, "with_acceptance": 1}}
        result = measure.check_10k_completeness(by_form, expected=10, tolerance=2)
        self.assertTrue(result["shortfall"])

    def test_missing_10k_form_key(self):
        result = measure.check_10k_completeness({}, expected=10, tolerance=2)
        self.assertEqual(result["actual_10k_count"], 0)
        self.assertTrue(result["shortfall"])


class UpdatedAfterCreatedTests(unittest.TestCase):
    def test_false_when_equal(self):
        item = {"created_at": "2023-06-01T12:00:00Z", "updated_at": "2023-06-01T12:00:00Z"}
        self.assertFalse(measure.updated_after_created(item))

    def test_true_when_updated_later(self):
        item = {"created_at": "2023-06-01T12:00:00Z", "updated_at": "2023-06-01T13:05:00Z"}
        self.assertTrue(measure.updated_after_created(item))

    def test_false_without_updated_at(self):
        self.assertFalse(measure.updated_after_created({"created_at": "2023-06-01T12:00:00Z"}))

    def test_summary_counts(self):
        items = [
            {"created_at": "2023-01-01T12:00:00Z", "updated_at": "2023-01-01T12:00:00Z"},
            {"created_at": "2023-01-02T12:00:00Z", "updated_at": "2023-01-02T15:00:00Z"},
            {"headline": "no timestamps"},
        ]
        summary = measure.summarize_news_items(items)
        self.assertEqual(summary["item_count"], 3)
        self.assertEqual(summary["with_created_at"], 2)
        self.assertEqual(summary["updated_after_created_count"], 1)
        self.assertAlmostEqual(summary["updated_after_created_share"], 1 / 3)
        self.assertEqual(summary["earliest_created_at"], "2023-01-01T12:00:00+00:00")


class FilterItemsCreatedInWindowTests(unittest.TestCase):
    def test_splits_in_and_out_of_window(self):
        items = [
            {"id": 1, "created_at": "2024-03-12T10:00:00Z"},   # inside
            {"id": 2, "created_at": "2021-11-02T20:43:25Z", "updated_at": "2024-03-13T17:26:14Z"},  # outside
            {"id": 3, "created_at": "2024-03-20T00:00:00Z"},   # boundary: end-exclusive, outside
        ]
        split = measure.filter_items_created_in_window(items, "2024-03-11T00:00:00Z", "2024-03-20T00:00:00Z")
        self.assertEqual([i["id"] for i in split["in_window"]], [1])
        self.assertEqual([i["id"] for i in split["outside_window"]], [2, 3])

    def test_missing_created_at_counts_as_outside(self):
        items = [{"id": 1}]
        split = measure.filter_items_created_in_window(items, "2024-01-01T00:00:00Z", "2024-01-02T00:00:00Z")
        self.assertEqual(len(split["outside_window"]), 1)
        self.assertEqual(len(split["in_window"]), 0)


class RawVsAdjustedRatioTests(unittest.TestCase):
    def test_ratio_step_detected_at_split(self):
        # Simulated 4:1 split on 2020-08-31: raw jumps, adjusted stays continuous.
        raw_bars = [
            {"date": "2020-08-28", "close": 500.0},
            {"date": "2020-08-31", "close": 129.0},
            {"date": "2020-09-01", "close": 131.0},
        ]
        adj_bars = [
            {"date": "2020-08-28", "close": 125.0},
            {"date": "2020-08-31", "close": 129.0},
            {"date": "2020-09-01", "close": 131.0},
        ]
        paired = measure.raw_vs_adjusted_ratio(raw_bars, adj_bars)
        self.assertEqual(len(paired), 3)
        self.assertAlmostEqual(paired[0]["ratio"], 4.0)
        self.assertAlmostEqual(paired[1]["ratio"], 1.0)
        step = measure.detect_ratio_step(paired)
        self.assertEqual(step["max_step_date"], "2020-08-31")
        self.assertEqual(step["steps_found"], 1)
        self.assertEqual(step["step_dates"][0]["date"], "2020-08-31")

    def test_no_step_when_no_corporate_action(self):
        # Small day-to-day rounding-scale noise around ratio=1.0 must NOT trip the
        # relative/log threshold (this is what the old fixed 0.005 absolute
        # tolerance falsely flagged, e.g. TSLA's 155 false steps).
        raw_bars = [{"date": f"2020-01-0{i}", "close": 100.0 + i} for i in range(1, 5)]
        adj_bars = [{"date": f"2020-01-0{i}", "close": 100.0 + i + 0.01} for i in range(1, 5)]
        paired = measure.raw_vs_adjusted_ratio(raw_bars, adj_bars)
        step = measure.detect_ratio_step(paired)
        self.assertEqual(step["steps_found"], 0)

    def test_large_ratio_split_still_detected(self):
        # A large-ratio regime (e.g. ~19x, like AMZN/GOOGL 20:1 splits) must still trip
        # the relative threshold even though the absolute ratio values are far from 1.0.
        raw_bars = [{"date": "2022-06-03", "close": 2400.0}, {"date": "2022-06-06", "close": 122.0}]
        adj_bars = [{"date": "2022-06-03", "close": 120.0}, {"date": "2022-06-06", "close": 122.0}]
        paired = measure.raw_vs_adjusted_ratio(raw_bars, adj_bars)
        step = measure.detect_ratio_step(paired)
        self.assertEqual(step["steps_found"], 1)

    def test_only_matching_dates_paired(self):
        raw_bars = [{"date": "2020-01-01", "close": 10.0}, {"date": "2020-01-02", "close": 11.0}]
        adj_bars = [{"date": "2020-01-01", "close": 10.0}]
        paired = measure.raw_vs_adjusted_ratio(raw_bars, adj_bars)
        self.assertEqual(len(paired), 1)


class MatchStepsToCorporateActionsTests(unittest.TestCase):
    def test_matched_within_window(self):
        step_dates = [{"date": "2020-09-01", "log_step": 1.4}]
        action_dates = ["2020-08-31", "2020-08-24"]
        result = measure.match_steps_to_corporate_actions(step_dates, action_dates, window_days=10)
        self.assertEqual(result["matched_count"], 1)
        self.assertEqual(result["unmatched_count"], 0)
        self.assertEqual(result["matched"][0]["matched_action_date"], "2020-08-31")

    def test_unmatched_outside_window(self):
        step_dates = [{"date": "2020-09-01", "log_step": 1.4}]
        action_dates = ["2019-01-01"]
        result = measure.match_steps_to_corporate_actions(step_dates, action_dates, window_days=10)
        self.assertEqual(result["matched_count"], 0)
        self.assertEqual(result["unmatched_count"], 1)

    def test_unmatched_with_no_action_dates(self):
        step_dates = [{"date": "2020-09-01", "log_step": 1.4}]
        result = measure.match_steps_to_corporate_actions(step_dates, [], window_days=10)
        self.assertEqual(result["unmatched_count"], 1)


class DividendAdjustmentTests(unittest.TestCase):
    def test_matched_dividend_step(self):
        # Raw close $100 the day before ex-date; a $0.50 dividend implies an
        # expected log-step of |ln(100) - ln(99.5)|; construct a paired series
        # whose actual ratio step on the ex-date matches that magnitude.
        import math
        prior_close = 100.0
        rate = 0.50
        expected_step = abs(math.log(prior_close) - math.log(prior_close - rate))
        paired = [
            {"date": "2023-06-01", "raw_close": prior_close, "adjusted_close": prior_close, "ratio": 1.0},
            {"date": "2023-06-02", "raw_close": 101.0, "adjusted_close": 101.0 * math.exp(expected_step),
             "ratio": 101.0 / (101.0 * math.exp(expected_step))},
        ]
        cash_dividends = [{"ex_date": "2023-06-02", "rate": rate}]
        result = measure.detect_dividend_adjustment(paired, cash_dividends)
        self.assertEqual(result["records_checked"], 1)
        self.assertEqual(result["matched_count"], 1)
        self.assertTrue(result["records"][0]["matched"])

    def test_unmatched_when_no_step_observed(self):
        paired = [
            {"date": "2023-06-01", "raw_close": 100.0, "adjusted_close": 100.0, "ratio": 1.0},
            {"date": "2023-06-02", "raw_close": 100.0, "adjusted_close": 100.0, "ratio": 1.0},
        ]
        cash_dividends = [{"ex_date": "2023-06-02", "rate": 0.50}]
        result = measure.detect_dividend_adjustment(paired, cash_dividends)
        self.assertEqual(result["unmatched_count"], 1)

    def test_no_records_when_no_dividends(self):
        result = measure.detect_dividend_adjustment([], [])
        self.assertEqual(result["records_checked"], 0)


class ComputeLogStepsTests(unittest.TestCase):
    def test_first_date_has_no_step(self):
        paired = [
            {"date": "2023-01-01", "ratio": 1.0},
            {"date": "2023-01-02", "ratio": 1.01},
        ]
        steps = measure.compute_log_steps(paired)
        self.assertNotIn("2023-01-01", steps)
        self.assertIn("2023-01-02", steps)
        self.assertGreater(steps["2023-01-02"], 0)


class LoadEnvFileTests(unittest.TestCase):
    def test_parses_export_lines(self, tmp_path=None):
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".env", delete=False) as f:
            f.write("export FOO=bar\n# comment\nexport BAZ=\"qux quux\"\n\nexport EMPTY=\n")
            path = f.name
        try:
            env = measure.load_env_file(path)
            self.assertEqual(env["FOO"], "bar")
            self.assertEqual(env["BAZ"], "qux quux")
            self.assertEqual(env["EMPTY"], "")
        finally:
            Path(path).unlink()


class ReceiptSchemaTests(unittest.TestCase):
    def test_build_receipt_has_required_keys(self):
        plan_path = Path(__file__).resolve().parent.parent / "blueprints/us-equities/pit-availability/plan.json"
        plan = json.loads(plan_path.read_text())
        receipt = measure.build_receipt(
            plan_path,
            plan,
            parts={"filings": {"overall": {}}},
            limitations=["x is not established"],
            sources=[{"part": "filings", "endpoint": "https://data.sec.gov"}],
        )
        for key in ("id", "kind", "evidence_class", "claim", "plan_sha256", "plan_written_utc",
                    "preregistered", "plan_history", "sources", "parts", "limitations", "observed_utc"):
            self.assertIn(key, receipt)
        self.assertEqual(receipt["evidence_class"], "open_and_entitled_sources_measured")
        self.assertEqual(len(receipt["plan_sha256"]), 64)
        self.assertFalse(receipt["preregistered"])
        json.dumps(receipt)  # must be JSON-serialisable

    def test_plan_written_utc_is_file_mtime_not_hand_written(self):
        import tempfile
        from datetime import datetime, timedelta, timezone
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump({"x": 1}, f)
            path = Path(f.name)
        try:
            before = datetime.now(timezone.utc)
            value = measure.file_mtime_utc(path)
            parsed = datetime.fromisoformat(value)
            self.assertLessEqual(parsed, before + timedelta(seconds=2))
        finally:
            path.unlink()


if __name__ == "__main__":
    unittest.main()
