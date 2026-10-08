"""Collector failure/provenance tests using Prometheus API-shaped fixtures."""

import importlib.util
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "local_pages_workstation", Path(__file__).resolve().parents[1] / "tools/local-pages/workstation.py"
)
workstation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(workstation)
NOW = 1791496800.0
FALLBACK = {
    "windows_available_gib": 17.4,
    "wsl_available_gib": 70.7,
    "swap_used_gib": 0,
    "read_utc": "2026-10-08T21:16:52Z",
}


def series(metric, value, timestamp=NOW - 5, instance="127.0.0.1:9100", job=None):
    if job is None:
        job = workstation.WINDOWS_JOB if metric.startswith("windows_") else "fixture-wsl"
    return {
        "metric": {"__name__": metric, "job": job, "instance": instance},
        "values": [[timestamp, str(value)]],
    }


def payload(rows):
    return {"status": "success", "data": {"resultType": "matrix", "result": rows}}


class WorkstationTests(unittest.TestCase):
    def collect(self, rows, fallback=FALLBACK, **kwargs):
        with patch.object(workstation.time, "time", return_value=NOW):
            return workstation.collect(fallback, lambda query, timeout: payload(rows), **kwargs)

    def assert_fallback(self, actual, field):
        self.assertEqual(actual[field]["value_gib"], FALLBACK[field])
        self.assertEqual(actual[field]["read_utc"], FALLBACK["read_utc"])
        self.assertEqual(actual[field]["source"], "cc-now fallback")

    def test_exact_valid_values_zero_and_original_sample_times(self):
        actual = self.collect([
            series(workstation.METRICS[0], 0, NOW - 2, "localhost:9182"),
            series(workstation.METRICS[1], 3 * 1024 ** 3, NOW - 7),
            series(workstation.METRICS[2], 4 * 1024 ** 3, NOW - 9),
            series(workstation.METRICS[3], 4 * 1024 ** 3, NOW - 9),
        ])
        for field in FALLBACK.keys() - {"read_utc"}:
            self.assertEqual(actual[field]["source"], "prometheus")
        self.assertEqual(actual["windows_available_gib"]["value_gib"], 0)
        self.assertEqual(actual["wsl_available_gib"]["value_gib"], 3)
        self.assertEqual(actual["swap_used_gib"]["value_gib"], 0)
        self.assertNotEqual(actual["windows_available_gib"]["read_utc"], actual["wsl_available_gib"]["read_utc"])
        self.assertEqual(actual["swap_used_gib"]["read_utc"], workstation._utc(NOW - 9))
        self.assertEqual(actual["API_errors"], [])

    def test_missing_series_uses_exact_cc_values_and_read_time(self):
        actual = self.collect([])
        for field in FALLBACK.keys() - {"read_utc"}:
            self.assert_fallback(actual, field)

    def test_invalid_stale_future_and_ambiguous_samples_keep_fallback(self):
        metric = workstation.METRICS[0]
        cases = [
            [series(metric, "NaN")], [series(metric, "+Inf")],
            [series(metric, -1)], [series(metric, 1, NOW - 121)],
            [series(metric, 1, NOW + 1)],
            [series(metric, 1), series(metric, 2, instance="localhost:9182")],
            [series(metric, 1, instance="other-host:9182", job="unrelated-windows")],
        ]
        for rows in cases:
            with self.subTest(rows=rows):
                self.assert_fallback(self.collect(rows), "windows_available_gib")

    def test_latest_invalid_sample_is_not_replaced_by_old_good_value(self):
        row = series(workstation.METRICS[0], 3)
        row["values"].append([NOW - 1, "NaN"])
        self.assert_fallback(self.collect([row]), "windows_available_gib")

    def test_swap_requires_same_target_recent_times_and_valid_difference(self):
        total, free = workstation.METRICS[2:4]
        cases = [
            [series(total, 4)],
            [series(total, 4), series(free, 3, instance="localhost:9101")],
            [series(total, 4, NOW - 50), series(free, 3, NOW - 1)],
            [series(total, 4), series(free, 5)],
        ]
        for rows in cases:
            with self.subTest(rows=rows):
                self.assert_fallback(self.collect(rows), "swap_used_gib")
        self.assertEqual(self.collect([series(total, 3 * 1024 ** 3), series(free, 1024 ** 3)])["swap_used_gib"]["value_gib"], 2)

    def test_timeout_and_api_errors_preserve_fallback_and_finite_timeout(self):
        calls = []

        def failing(query, timeout):
            calls.append((query, timeout))
            raise TimeoutError()

        with patch.object(workstation.time, "time", return_value=NOW):
            actual = workstation.collect(FALLBACK, failing)
        self.assertEqual(calls, [(workstation.QUERY, 2.0)])
        self.assertEqual(actual["API_errors"][0]["type"], "TimeoutError")
        for field in FALLBACK.keys() - {"read_utc"}:
            self.assert_fallback(actual, field)
        for body in [
            {"status": "error", "errorType": "timeout"},
            {"status": "success", "data": {"resultType": "vector", "result": []}},
            dict(payload([]), warnings=["partial result"]),
        ]:
            actual = workstation.collect(FALLBACK, lambda query, timeout: body)
            self.assertTrue(actual["API_errors"])
            self.assert_fallback(actual, "windows_available_gib")

    def test_default_fetch_uses_loopback_no_proxy_and_bounded_read(self):
        with patch.object(workstation, "build_opener") as opener:
            response = opener.return_value.open.return_value.__enter__.return_value
            response.read.return_value = b'{"status":"success","data":{"resultType":"matrix","result":[]}}'
            workstation.collect(FALLBACK)
        args, kwargs = opener.return_value.open.call_args
        self.assertTrue(args[0].startswith("http://127.0.0.1:21090/api/v1/query?"))
        self.assertEqual(parse_qs(urlparse(args[0]).query)["timeout"], ["1s"])
        self.assertEqual(kwargs["timeout"], 2.0)
        response.read.assert_called_once_with(workstation.MAX_RESPONSE_BYTES + 1)
        self.assertEqual(opener.call_args.args[0].proxies, {})

    def test_redirects_are_refused_without_a_second_request(self):
        requests = []
        redirect = {"code": 302}

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                requests.append(self.path)
                if self.path.startswith("/api/v1/query?"):
                    self.send_response(redirect["code"])
                    self.send_header("Location", f"http://127.0.0.1:{self.server.server_port}/redirect-target")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                else:
                    body = b'{"status":"success","data":{"resultType":"matrix","result":[]}}'
                    self.send_response(200)
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        thread.start()
        try:
            with patch.object(workstation, "ENDPOINT", f"http://127.0.0.1:{server.server_port}"):
                for code in (301, 302, 303, 307, 308):
                    with self.subTest(code=code):
                        redirect["code"] = code
                        requests.clear()
                        actual = workstation.collect(FALLBACK)
                        self.assertEqual(len(requests), 1)
                        self.assertTrue(requests[0].startswith("/api/v1/query?"))
                        self.assertEqual(actual["API_errors"][0]["type"], "HTTPError")
                        for field in workstation.FIELDS:
                            self.assert_fallback(actual, field)
                            self.assertEqual(actual[field]["fallback_reason"], "API read failed")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
    def test_windows_uses_supplied_job_not_loopback_instance(self):
        metric = workstation.METRICS[0]
        actual = self.collect([
            series(metric, 7 * 1024 ** 3, instance="172.26.16.1:9182"),
            series(metric, 2 * 1024 ** 3, job="unrelated-windows"),
        ])
        self.assertEqual(actual["windows_available_gib"]["value_gib"], 7)
        self.assertEqual(actual["windows_available_gib"]["source"], "prometheus")

    def test_node_identity_is_unique_labelled_and_can_be_narrowed(self):
        metric = workstation.METRICS[1]
        total = workstation.METRICS[2]
        actual = self.collect([
            series(metric, 1, instance="wsl:9100"),
            series(total, 4, instance="other-linux:9100"),
        ])
        self.assert_fallback(actual, "wsl_available_gib")
        self.assert_fallback(actual, "swap_used_gib")
        row = series(metric, 1)
        del row["metric"]["job"]
        self.assert_fallback(self.collect([row]), "wsl_available_gib")
        self.assert_fallback(self.collect([series(metric, 1, job=workstation.WINDOWS_JOB)]), "wsl_available_gib")
        actual = self.collect([
            series(metric, 3 * 1024 ** 3, job="known-wsl"),
            series(metric, 8 * 1024 ** 3, job="another-linux"),
        ], wsl_job="known-wsl")
        self.assertEqual(actual["wsl_available_gib"]["value_gib"], 3)

    def test_totals_are_optional_and_have_individual_sample_times(self):
        actual = self.collect([])
        for field in workstation.OPTIONAL_TOTALS:
            self.assertNotIn(field, actual)
        fallback = dict(FALLBACK, windows_total_gib=127.8, wsl_total_gib=102.2)
        actual = self.collect([], fallback)
        self.assertEqual(actual["windows_total_gib"]["value_gib"], 127.8)
        self.assertEqual(actual["wsl_total_gib"]["value_gib"], 102.2)
        actual = self.collect([
            series(workstation.METRICS[4], 128 * 1024 ** 3, NOW - 4, "172.26.16.1:9182"),
            series(workstation.METRICS[5], 100 * 1024 ** 3, NOW - 8),
        ])
        self.assertEqual(actual["windows_total_gib"]["value_gib"], 128)
        self.assertEqual(actual["wsl_total_gib"]["value_gib"], 100)
        self.assertEqual(actual["windows_total_gib"]["read_utc"], workstation._utc(NOW - 4))
        self.assertEqual(actual["wsl_total_gib"]["read_utc"], workstation._utc(NOW - 8))

    def test_authored_per_figure_fallback_times_are_preserved(self):
        fallback = dict(
            FALLBACK,
            windows_total_gib={"value_gib": 127.8, "read_utc": "2026-10-08T21:01:00Z"},
            wsl_total_gib=102.2,
            wsl_total_gib_read_utc="2026-10-08T21:02:00Z",
        )
        actual = self.collect([], fallback)
        self.assertEqual(actual["windows_total_gib"]["value_gib"], 127.8)
        self.assertEqual(actual["windows_total_gib"]["read_utc"], "2026-10-08T21:01:00Z")
        self.assertEqual(actual["wsl_total_gib"]["read_utc"], "2026-10-08T21:02:00Z")
        fallback = dict(FALLBACK, read_utc={"swap_used_gib": "2026-10-08T21:03:00Z"})
        self.assertEqual(self.collect([], fallback)["swap_used_gib"]["read_utc"], "2026-10-08T21:03:00Z")


if __name__ == "__main__":
    unittest.main()
