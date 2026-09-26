"""F12 regressions at the dry-run acquisition and frozen-allowance boundaries.

Bounds follow protocol-core-draft.json, pipeline_allowance.rule (review round 15, F12).
Only synthetic transport responses and temporary calibration outputs are used.
"""
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from core import count_only as CO
from core import driver, guards, plan, runner
from core.canon import sha256_file
from core.params import DRY_RUN_OUTPUT
from core.store import Store
from fetch.transport import Transport
from tests import fixture_repo as FR
from tests.test_identity import fixed_clock


def check_calibration(output, allowance=None):
    """Bind the output to a completed producer line, as the frozen runner requires."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / DRY_RUN_OUTPUT
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(output), encoding="utf-8")
        protocol = {"run_discipline": {"study_code": {"tree": "synthetic-study-tree"}}}
        line = {"stage": "pre_freeze", "purpose": "dry_run", "status": "complete",
                "results_sha256": sha256_file(path), "study_tree": "synthetic-study-tree"}
        return runner.check_dry_run_bound(tmp, protocol, [line], allowance or FR.ALLOWANCE)


class CalibrationAcceptance(unittest.TestCase):
    def test_failure_only_acquisition_cannot_calibrate(self):
        req = plan.quote_request("quote_exit", "AAA", "2023-03-01", 1.68e9, 1.68e9 + 60)
        transport = Transport(opener=lambda *args, **kwargs: (503, b"{}"), headers={}, sleep=lambda s: None)
        store = Store()
        result = driver.stage_fetch(lambda st: [req], {"data": transport}, store, "2026-09-25",
                                    clock=fixed_clock)
        self.assertEqual(result["refetched"], 1)
        with tempfile.TemporaryDirectory() as tmp:
            sha = store.write(Path(tmp) / "dry-run")
            output = CO.dry_run_output(tmp, sha, ["2023-03-01"], ["AAA"])
        self.assertEqual(output["measured"]["pages"], 0)
        self.assertIsNone(output["measured"]["seconds_per_page"])
        with self.assertRaisesRegex(guards.Refused, "calibration"):
            check_calibration(output)

    def test_absent_or_invalid_calibration_cannot_pass(self):
        for measured in (None, {}, {**FR.MEASURED, "seconds_per_page": None},
                         {**FR.MEASURED, "seconds_per_page": 0.0},
                         {**FR.MEASURED, "seconds_per_page": float("nan")},
                         {**FR.MEASURED, "pages": 0}):
            with self.subTest(measured=measured):
                with self.assertRaisesRegex(guards.Refused, "calibration"):
                    check_calibration({"measured": measured})

    def test_unmeasured_kinds_use_the_largest_observed_quote_bound(self):
        measured = {"pages_per_request_max": {"screen_daily_raw": 1, "quote_entry": 10, "quote_exit": 100},
                    "pages": 111, "elapsed_seconds": 1.11, "seconds_per_page": 0.01}
        output = {"measured": measured}
        bounds = {k: measured["pages_per_request_max"].get(k, 100) for k in CO.PAGE_KINDS}
        allowance = {**FR.ALLOWANCE, "pages_per_request": bounds}
        self.assertEqual(check_calibration(output, allowance), output)
        for kind in CO.PAGE_KINDS:
            if kind in measured["pages_per_request_max"]:
                continue
            with self.subTest(kind=kind):
                underbounded = {**allowance, "pages_per_request": {**bounds, kind: 1}}
                with self.assertRaisesRegex(guards.Refused, kind):
                    check_calibration(output, underbounded)

    def test_invalid_page_maxima_refuse_with_no_valid_page_calibration(self):
        """check_dry_run_bound requires a mapping of nonnegative integer page maxima, excluding booleans."""
        for maxima in (None, [], 1, "pages", {"quote_entry": 1, "event_minute": -1},
                       {"quote_entry": True}, {"quote_entry": 1.0}, {"quote_entry": "1"}):
            with self.subTest(maxima=maxima):
                with self.assertRaisesRegex(guards.Refused,
                                            "^the native dry run has no valid page calibration$"):
                    check_calibration({"measured": {**FR.MEASURED, "pages_per_request_max": maxima}})

    def test_missing_quote_measurements_cannot_bound_unmeasured_kinds(self):
        for maxima in ({}, {"screen_daily_raw": 1}, {"screen_daily_raw": 1, "quote_exit": 0}):
            with self.subTest(maxima=maxima):
                with self.assertRaisesRegex(guards.Refused, "calibration"):
                    check_calibration({"measured": {**FR.MEASURED, "pages_per_request_max": maxima}})


class CalibrationTiming(unittest.TestCase):
    def _acquire(self, symbols, responses):
        """Ten seconds per HTTP call; retry waits advance the same synthetic clock."""
        now = [0.0]
        replies = iter(responses)

        def sleep(seconds):
            now[0] += seconds

        def opener(*args, **kwargs):
            sleep(10.0)
            return next(replies), b"{}"

        def clock():
            return datetime.fromtimestamp(1.79e9 + now[0], timezone.utc).isoformat()

        reqs = [plan.quote_request("quote_exit", symbol, "2023-03-01", 1.68e9, 1.68e9 + 60)
                for symbol in symbols]
        store = Store()
        transport = Transport(opener=opener, headers={}, sleep=sleep)
        with mock.patch("time.perf_counter", side_effect=lambda: now[0]):
            driver.stage_fetch(lambda st: reqs, {"data": transport}, store, "2026-09-25", clock=clock)
        with tempfile.TemporaryDirectory() as tmp:
            sha = store.write(Path(tmp) / "dry-run")
            return CO.dry_run_output(tmp, sha, ["2023-03-01"], symbols)

    def test_two_ten_second_requests_measure_ten_seconds_per_page(self):
        output = self._acquire(["AAA", "BBB"], [200, 200])
        measured = output["measured"]
        self.assertEqual(measured["seconds_per_page"], 10.0)
        self.assertEqual((measured["pages"], measured["elapsed_seconds"]), (2, 20.0))

    def test_retry_and_refetch_durations_survive_the_seal(self):
        output = self._acquire(["AAA"], [503, 503, 503, 503, 200])
        measured = output["measured"]
        # Four failed calls, waits of 1 + 4 + 16 seconds, and the successful re-fetch.
        self.assertEqual(measured["elapsed_seconds"], 71.0)
        self.assertEqual((measured["pages"], measured["seconds_per_page"]), (1, 71.0))

    def test_a_seal_without_complete_durations_has_no_throughput_measurement(self):
        req = plan.quote_request("quote_exit", "AAA", "2023-03-01", 1.68e9, 1.68e9 + 60)
        store = Store()
        store.put(req, True, [b"{}"], fixed_clock())
        with tempfile.TemporaryDirectory() as tmp:
            sha = store.write(tmp)
            measured = CO.dry_run_measured(Store.read(tmp, sha))
        self.assertIsNone(measured["seconds_per_page"])
        self.assertIsNone(measured["elapsed_seconds"])
        with self.assertRaisesRegex(guards.Refused, "calibration"):
            check_calibration({"measured": measured})
