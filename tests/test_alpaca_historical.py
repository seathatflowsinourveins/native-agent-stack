"""Synthetic HTTP bodies only; no credentials or provider requests."""
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import urlencode
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "blueprints/us-equities/alpaca-historical/collect.py"
PLAN = ROOT / "blueprints/us-equities/alpaca-historical/plan.json"
STARTED = "2026-09-20T00:00:00.000000001Z"
OBSERVED = "2026-09-20T00:00:01.000000002Z"


def bar(day, **changes):
    row = {"t": day + "T04:00:00Z", "o": 100, "h": 110, "l": 90,
           "c": 101, "v": 12345, "n": 123, "vw": 100.125}
    row.update(changes)
    return row


def action(**changes):
    row = {"id": str(UUID(int=1)), "symbol": "AAPL",
           "cusip": "SYNTHETIC", "rate": 0.82, "special": False, "foreign": False,
           "process_date": "2020-08-13", "ex_date": "2020-08-07"}
    row.update(changes)
    return row


def response(payload, status=200):
    return {"body": json.dumps(payload).encode(), "status": status,
            "started_at": STARTED, "observed_at": OBSERVED, "transport_error": None,
            "body_complete": True}


class AlpacaHistoricalTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(MODULE.exists(), "historical acquisition adapter is not implemented")
        spec = importlib.util.spec_from_file_location("alpaca_historical", MODULE)
        self.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.m)
        self.plan = json.loads(PLAN.read_text())
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def pages(self, kind="bars"):
        if kind == "actions":
            bodies = [{"corporate_actions": {"cash_dividends": [action()]}, "next_page_token": None}]
        else:
            days = self.plan["expected_session_dates"]
            bodies = [{"bars": {"AAPL": [bar(d) for d in days[i:i+10]]},
                       "next_page_token": "page" + str(i+10) if i+10 < len(days) else None}
                      for i in range(0, len(days), 10)]
        pages, token = [], None
        for body in bodies:
            req = dict(self.plan[kind]["query"])
            if token is not None:
                req["page_token"] = token
            pages.append(dict(response(body), request=req, actual_request=self.wire(kind, req)))
            token = body["next_page_token"]
        return pages

    def wire(self, kind, request):
        return {"method": "GET", "url": self.plan[kind]["url"] + "?" + urlencode(request)}

    def mutate(self, pages, index, change):
        body = json.loads(pages[index]["body"])
        change(body)
        pages[index]["body"] = json.dumps(body).encode()

    def test_bounded_sample_accepts_25_synthetic_sessions(self):
        self.assertEqual(self.m.validate_pages("bars", self.pages(), self.plan)["summary"]["rows"], 25)

    def test_page_chain_and_complete_session_set(self):
        result = self.m.validate_pages("bars", self.pages(), self.plan)
        self.assertEqual(result["summary"]["pages"], 3)
        self.assertEqual(result["summary"]["session_dates"], self.plan["expected_session_dates"])
        self.assertEqual(result["rows"][0]["timestamp_ns"], 1596427200000000000)
        self.assertEqual(result["rows"][0]["first_observed_at"], OBSERVED)

    def test_timestamp_parser_preserves_nanosecond_and_rejects_extra_precision(self):
        self.assertEqual(self.m.timestamp_ns("2020-08-03T04:00:00.000000001Z"), 1596427200000000001)
        for bad in ["2020-08-03T04:00:00.0000000001Z", "2020-08-03T04:00:00", "2020-08-03T04:00:00+00:00", "2020-02-30T00:00:00Z"]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.m.timestamp_ns(bad)

    def test_exact_decimal_text_is_not_rounded_via_sdk_float(self):
        pages = self.pages()
        pages[0]["body"] = pages[0]["body"].replace(b'100.125', b'100.1234567890123456789', 1)
        result = self.m.validate_pages("bars", pages, self.plan)
        self.assertEqual(result["rows"][0]["vw"], "100.1234567890123456789")

    def test_inclusive_wire_end_and_half_open_local_rejection(self):
        plan = copy.deepcopy(self.plan)
        plan["bars"]["query"]["end"] = "2020-09-05T00:00:00Z"
        with self.assertRaisesRegex(ValueError, "bounds"):
            self.m.validate_plan(plan)
        pages = self.pages()
        self.mutate(pages, -1, lambda b: b["bars"]["AAPL"][-1].update(t="2020-09-05T00:00:00Z"))
        with self.assertRaisesRegex(ValueError, "bar_outside_window"):
            self.m.validate_pages("bars", pages, self.plan)

    def test_incomplete_token_chain_and_missing_terminal_fail(self):
        for kind in ["bars", "actions"]:
            pages = self.pages(kind)
            self.mutate(pages, -1, lambda b: b.update(next_page_token="more"))
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, "incomplete_page_chain"):
                self.m.validate_pages(kind, pages, self.plan)
        pages = self.pages()
        self.mutate(pages, -1, lambda b: b.pop("next_page_token"))
        with self.assertRaisesRegex(ValueError, "missing_page_token"):
            self.m.validate_pages("bars", pages, self.plan)

    def test_repeated_tokens_wrong_requests_and_duplicate_rows_fail(self):
        for mutation, reason in [
            (lambda p: p[1]["request"].update(page_token="wrong"), "request_mismatch"),
            (lambda p: self.mutate(p, 1, lambda b: b.update(next_page_token="page10")), "page_token_cycle"),
            (lambda p: self.mutate(p, 1, lambda b: b["bars"]["AAPL"][0].update(t="2020-08-14T04:00:00Z")), "duplicate_bar")]:
            pages = self.pages(); mutation(pages)
            with self.subTest(reason=reason), self.assertRaisesRegex(ValueError, reason):
                self.m.validate_pages("bars", pages, self.plan)

    def test_short_complete_query_does_not_claim_session_coverage(self):
        pages = self.pages()
        self.mutate(pages, -1, lambda b: b["bars"]["AAPL"].pop())
        with self.assertRaisesRegex(ValueError, "session_coverage"):
            self.m.validate_pages("bars", pages, self.plan)

    def test_malformed_nonfinite_ohlcv_and_daily_timestamp_are_rejected(self):
        for changes in [{"o": True}, {"v": -1}, {"n": 0.5}, {"h": 99}, {"c": None},
                        {"vw": float("nan")}, {"o": "100"}, {"t": "2020-08-03T04:00:00.000000001Z"}]:
            pages = self.pages()
            self.mutate(pages, 0, lambda b: b["bars"]["AAPL"][0].update(changes))
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.m.validate_pages("bars", pages, self.plan)

    def test_duplicate_json_keys_are_not_silently_replaced(self):
        pages = self.pages()
        pages[0]["body"] = pages[0]["body"].replace(b'"o": 100', b'"o": 1, "o": 100', 1)
        with self.assertRaisesRegex(ValueError, "duplicate_json_key"):
            self.m.validate_pages("bars", pages, self.plan)

    def test_actions_keep_process_event_observation_distinct(self):
        result = self.m.validate_pages("actions", self.pages("actions"), self.plan)
        row = result["rows"][0]
        self.assertEqual((row["process_date"], row["ex_date"], row["first_observed_at"]),
                         ("2020-08-13", "2020-08-07", OBSERVED))
        self.assertEqual(result["summary"]["comparison_targets_observed"], [True, False])
        self.assertFalse(result["summary"]["historical_coverage_established"])

    def test_incomplete_actions_are_retained_as_unqualified(self):
        pages = self.pages("actions")
        self.mutate(pages, 0, lambda b: b["corporate_actions"]["cash_dividends"][0].update(ex_date=None, rate=None))
        result = self.m.validate_pages("actions", pages, self.plan)
        self.assertEqual(result["rows"][0]["qualification"], "incomplete")
        self.assertEqual(result["summary"]["qualified_rows"], 0)

    def test_action_identity_and_process_bounds_are_checked(self):
        for changes in [{"id": ""}, {"process_date": "2020-09-05"}, {"rate": -1}, {"special": "false"}]:
            pages = self.pages("actions")
            self.mutate(pages, 0, lambda b: b["corporate_actions"]["cash_dividends"][0].update(changes))
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.m.validate_pages("actions", pages, self.plan)

    def fake_fetch(self, kind, request):
        pages = self.pages(kind)
        return next({k: v for k, v in p.items() if k != "request"} for p in pages if p["request"] == request)

    def collect(self, fetch=None):
        out = self.root / "run"
        def fixture_transport(kind, request):
            result = (fetch or self.fake_fetch)(kind, request)
            result.setdefault("actual_request", self.wire(kind, request))
            return result
        with patch.object(self.m, "native_identity", return_value={"alpaca_py_version": "0.44.0", "sources": []}):
            result = self.m.collect(out, fixture_transport)
        return out, result

    def test_saved_receipt_raw_tamper_external_anchor_and_overwrite(self):
        out, result = self.collect()
        anchor = result["receipt_sha256"]
        verified = self.m.verify(out, anchor)
        self.assertEqual(verified["bars"]["summary"]["rows"], 25)
        with self.assertRaises(FileExistsError):
            self.m.collect(out, self.fake_fetch)
        with self.assertRaisesRegex(ValueError, "receipt_hash_mismatch"):
            self.m.verify(out, "0" * 64)
        blob = out / "bars-001.json"
        blob.write_bytes(blob.read_bytes() + b" ")
        with self.assertRaisesRegex(ValueError, "artifact_hash_mismatch"):
            self.m.verify(out, anchor)

    def test_action_refusal_is_retained_and_does_not_erase_valid_bars(self):
        def fetch(kind, req):
            return response({"message": "synthetic refusal"}, 403) if kind == "actions" else self.fake_fetch(kind, req)
        out, result = self.collect(fetch)
        verified = self.m.verify(out, result["receipt_sha256"])
        self.assertEqual(verified["bars"]["status"], "complete")
        self.assertEqual(verified["actions"]["status"], "failed")
        self.assertEqual(verified["actions"]["reason"], "http_403")
        self.assertIn(b"synthetic refusal", (out / "actions-001.json").read_bytes())

    def test_page_cap_preserves_failure_and_stops_requests(self):
        calls = []
        def fetch(kind, req):
            calls.append(kind)
            return response({"bars": {"AAPL": []}, "next_page_token": "next" + str(len(calls))}) if kind == "bars" else response({"corporate_actions": {}, "next_page_token": None})
        out, result = self.collect(fetch)
        self.assertEqual(calls.count("bars"), 10)
        self.assertEqual(self.m.verify(out, result["receipt_sha256"])["bars"]["reason"], "incomplete_page_chain")

    def test_symlink_parent_and_unexpected_payload_are_refused(self):
        (self.root / "alias").symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.m.collect(self.root / "alias" / "run", self.fake_fetch)
        out, result = self.collect()
        (out / "extra.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "unexpected_artifact"):
            self.m.verify(out, result["receipt_sha256"])

    def test_native_get_retains_exact_bytes_and_disables_redirect_retry(self):
        try:
            from requests import Response
            from requests.adapters import BaseAdapter
        except ImportError:
            self.skipTest("requests dependency is not installed in this interpreter")
        try:
            self.m.native_identity()
        except importlib.metadata.PackageNotFoundError:
            self.skipTest("alpaca-py is not installed in this interpreter")
        captures = []
        raw = b'{"bars":{"AAPL":[]},"next_page_token":null,"exact":1.1234567890123456789}'

        class SyntheticAdapter(BaseAdapter):
            def send(self, request, **kwargs):
                captures.append((request, kwargs))
                result = Response()
                result.status_code = 200
                result.raw = io.BytesIO(raw)
                result.request = request
                result.url = request.url
                result.headers = {"Content-Type": "application/json"}
                return result

            def close(self):
                pass

        client = self.m.NativePages("synthetic-key", "synthetic-secret", self.plan)
        self.addCleanup(client.close)
        for upstream in client.clients.values():
            upstream._session.mount("https://", SyntheticAdapter())
        result = client("bars", self.plan["bars"]["query"])
        self.assertEqual(result["body"], raw)
        self.assertEqual(len(captures), 1)
        self.assertIn("end=2020-09-04T23%3A59%3A59.999999999Z", captures[0][0].url)
        self.assertIn("asof=2020-09-04", captures[0][0].url)
        self.assertEqual(captures[0][1]["timeout"], (10, 30))
        self.assertEqual(captures[0][0].method, "GET")
        self.assertEqual(captures[0][0].headers["APCA-API-KEY-ID"], "synthetic-key")
        self.assertEqual(result["actual_request"], {"method": "GET", "url": captures[0][0].url})
        client("actions", self.plan["actions"]["query"])
        self.assertIn("region=us", captures[-1][0].url)
        self.assertIn("data_quality=all", captures[-1][0].url)

        class ErrorAdapter(SyntheticAdapter):
            status = 429
            def send(self, request, **kwargs):
                result = super().send(request, **kwargs)
                result.status_code = self.status
                result.headers["Location"] = "https://different.invalid/"
                return result

        adapter = ErrorAdapter()
        client.clients["bars"]._session.mount("https://", adapter)
        for status in [429, 302]:
            adapter.status = status
            before = len(captures)
            result = client("bars", self.plan["bars"]["query"])
            self.assertEqual(result["status"], status)
            self.assertEqual(result["body"], raw)
            self.assertEqual(len(captures), before + 1, "native retry or redirect added an HTTP attempt")

    def test_native_hook_bounds_oversized_body_and_marks_incomplete(self):
        try:
            from requests import Response, Request
            self.m.native_identity()
        except (ImportError, importlib.metadata.PackageNotFoundError):
            self.skipTest("native SDK dependencies are not installed")
        client = self.m.NativePages("synthetic-key", "synthetic-secret", self.plan)
        self.addCleanup(client.close)
        upstream = Response()
        upstream.status_code = 200
        upstream.raw = io.BytesIO(b"x" * (self.m.MAX_BODY + 1))
        upstream.request = Request("GET", self.plan["bars"]["url"]).prepare()
        with self.assertRaisesRegex(ValueError, "incomplete_response_body"):
            client._capture(upstream)
        self.assertEqual(len(client.captured["body"]), self.m.MAX_BODY)
        self.assertFalse(client.captured["body_complete"])
        self.assertTrue(upstream.raw.closed)

    def test_interrupted_stream_is_closed_and_prefix_cannot_be_accepted(self):
        try:
            from requests import Response, Request
            self.m.native_identity()
        except (ImportError, importlib.metadata.PackageNotFoundError):
            self.skipTest("native SDK dependencies are not installed")
        class InterruptedStream:
            calls, closed = 0, False
            def read(self, _size):
                self.calls += 1
                if self.calls == 1:
                    return b"partial"
                raise OSError("synthetic interrupted stream")
            def close(self):
                self.closed = True
        client = self.m.NativePages("synthetic-key", "synthetic-secret", self.plan)
        self.addCleanup(client.close)
        upstream = Response()
        upstream.status_code = 200
        upstream.raw = InterruptedStream()
        upstream.request = Request("GET", self.plan["bars"]["url"]).prepare()
        with self.assertRaises(OSError):
            client._capture(upstream)
        self.assertTrue(upstream.raw.closed)
        self.assertEqual(client.captured["body"], b"partial")
        self.assertFalse(client.captured["body_complete"])

    def test_actual_prepared_request_cannot_change_feed_or_action_quality(self):
        for kind, change in [("bars", {"feed": "iex"}), ("actions", {"data_quality": "complete"})]:
            pages = self.pages(kind)
            req = dict(pages[0]["request"], **change)
            pages[0]["actual_request"] = self.wire(kind, req)
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, "wire_request_mismatch"):
                self.m.validate_pages(kind, pages, self.plan)

    def test_invalid_observation_order_duplicate_actions_and_lower_bound(self):
        pages = self.pages()
        pages[0]["observed_at"] = "2026-09-19T00:00:00Z"
        with self.assertRaisesRegex(ValueError, "observation"):
            self.m.validate_pages("bars", pages, self.plan)
        pages = self.pages()
        self.mutate(pages, 0, lambda b: b["bars"]["AAPL"][0].update(t="2020-08-02T04:00:00Z"))
        with self.assertRaisesRegex(ValueError, "bar_outside_window"):
            self.m.validate_pages("bars", pages, self.plan)
        pages = self.pages("actions")
        self.mutate(pages, 0, lambda b: b.update(next_page_token="more"))
        pages += copy.deepcopy(self.pages("actions"))
        pages[1]["request"]["page_token"] = "more"
        pages[1]["actual_request"] = self.wire("actions", pages[1]["request"])
        with self.assertRaisesRegex(ValueError, "duplicate_action"):
            self.m.validate_pages("actions", pages, self.plan)

    def test_reforged_assessment_and_metadata_are_checked_against_raw(self):
        out, result = self.collect()
        receipt = json.loads((out / "receipt.json").read_bytes())
        receipt["stages"]["bars"]["assessment"]["rows"][0]["c"] = "999"
        raw = json.dumps(receipt).encode()
        (out / "receipt.json").write_bytes(raw)
        with self.assertRaisesRegex(ValueError, "assessment_mismatch"):
            self.m.verify(out, hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    unittest.main()
