"""Synthetic SDK transport checks; no live TypeSafe calls or credentials.

Run all checks with:
uv run --no-project --with typesafe-sdk==0.7.2 python3 -m unittest discover -s tests -p test_gap_crosswalk_sdk.py
The offline import checks also run without the optional SDK.
"""
import builtins
import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("gap_crosswalk_sdk_test", ROOT / "tools/sota-convergence/gap_crosswalk.py")
crosswalk = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(crosswalk)


class OptionalSDKTests(unittest.TestCase):
    def test_module_import_does_not_load_sdk(self):
        original = builtins.__import__

        def no_sdk(name, *args, **kwargs):
            if name == "typesafe_sdk" or name.startswith("typesafe_sdk."):
                self.fail("offline module import loaded the SDK")
            return original(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=no_sdk):
            SPEC.loader.exec_module(importlib.util.module_from_spec(SPEC))

    def test_missing_sdk_fails_with_pinned_install_command(self):
        original = builtins.__import__

        def no_sdk(name, *args, **kwargs):
            if name == "typesafe_sdk":
                raise ModuleNotFoundError(name)
            return original(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=no_sdk):
            with self.assertRaisesRegex(SystemExit, "including --set and --out.*uv run --with typesafe-sdk==0.7.2"):
                crosswalk.call({}, "synthetic-key")

    def test_other_sdk_version_fails_before_transport(self):
        other = types.SimpleNamespace(RetryPolicy=None, TypeSafeClient=None, __version__="0.0.0")
        with patch.dict(sys.modules, {"typesafe_sdk": other}):
            with self.assertRaisesRegex(SystemExit, r"found 0\.0\.0"):
                crosswalk.call({}, "synthetic-key")


@unittest.skipUnless(importlib.util.find_spec("typesafe_sdk"), "optional typesafe-sdk==0.7.2 not installed")
class SDKTransportTests(unittest.TestCase):
    def setUp(self):
        import httpx2
        import typesafe_sdk

        self.assertEqual(typesafe_sdk.__version__, "0.7.2", "use the pinned SDK test command")
        self.httpx = httpx2
        self.sdk = typesafe_sdk
        with patch.object(crosswalk, "receipt_state", return_value={"purpose": "synthetic check"}):
            self.body = crosswalk.request_body(ROOT, {"layer": "fixture", "gap": "fixture gap",
                                                       "receipts": ["synthetic-receipt.json"]})
        self.payload = {
            "model": crosswalk.MODEL,
            "usage": {"input_tokens": 17, "output_tokens": 9},
            "answers": {
                qid: {"type": "choice", "choice": next(iter(question["criteria"])), "confidence": 1.0,
                      "probabilities": {name: float(i == 0) for i, name in enumerate(question["criteria"])}}
                for qid, question in self.body["questions"].items()
            },
        }

    def run_stub(self, statuses, *, payload=None, request_id="synthetic-request"):
        requests = []
        configurations = []

        def handler(request):
            requests.append(request)
            status = statuses[len(requests) - 1]
            headers = {"Retry-After": "999"}
            if request_id is not None:
                headers["x-typesafe-request-id"] = request_id
            data = (self.payload if payload is None else payload) if status == 200 else {"error": "synthetic failure"}
            headers["Content-Type"] = "application/json"
            # Stream the fixture so the native client reads/closes it and records elapsed.
            return self.httpx.Response(status, headers=headers, stream=self.httpx.ByteStream(json.dumps(data).encode()))

        native_client = self.sdk.TypeSafeClient

        def client(**kwargs):
            configurations.append(kwargs)
            return native_client(transport=self.httpx.MockTransport(handler), **kwargs)

        # The vendor's injected MockTransport seam runs its unchanged HTTP/retry/parser code.
        with patch.object(self.sdk, "TypeSafeClient", side_effect=client), patch("time.sleep") as sleep:
            try:
                result = crosswalk.call(self.body, "synthetic-key")
            except self.sdk.TypeSafeAPIError as error:
                result = error
        return result, requests, configurations, sleep

    def test_structured_questions_metadata_and_final_attempt_retry_count(self):
        result, requests, configurations, sleep = self.run_stub([429, 529, 200])
        body, request_id, latency, retries = result
        crosswalk.validate(body, self.body)
        self.assertEqual(body["usage"], self.payload["usage"])
        self.assertEqual(body["answers"], self.payload["answers"])
        self.assertEqual(request_id, "synthetic-request")
        self.assertGreaterEqual(latency, 0)
        self.assertEqual(retries, 2)
        self.assertEqual([r.headers.get("x-typesafe-retry-count") for r in requests], [None, "1", "2"])
        self.assertEqual([c.args[0] for c in sleep.call_args_list], [1, 2])
        self.assertEqual(configurations[0]["timeout"], 60)
        for request in requests:
            self.assertEqual(request.method, "POST")
            self.assertEqual(str(request.url), crosswalk.URL)
            self.assertEqual(json.loads(request.content), self.body)
            self.assertEqual(request.headers["User-Agent"], "typesafe-sdk/0.7.2")
            self.assertEqual(request.extensions["timeout"]["read"], 60)

    def test_retries_stop_after_five_attempts_with_legacy_backoff(self):
        result, requests, _, sleep = self.run_stub([529] * 5)
        self.assertIsInstance(result, self.sdk.TypeSafeAPIError)
        self.assertEqual(len(requests), 5)
        self.assertEqual([c.args[0] for c in sleep.call_args_list], [1, 2, 4, 8])

    def test_non_retryable_status_stops_immediately(self):
        result, requests, _, sleep = self.run_stub([500])
        self.assertIsInstance(result, self.sdk.TypeSafeAPIError)
        self.assertEqual(len(requests), 1)
        sleep.assert_not_called()

    def test_missing_request_id_stays_optional(self):
        result, requests, _, sleep = self.run_stub([200], request_id=None)
        self.assertIsNone(result[1])
        self.assertEqual(result[3], 0)
        self.assertEqual(len(requests), 1)
        sleep.assert_not_called()

    def test_missing_usage_remains_invalid(self):
        payload = dict(self.payload, usage={})
        result, _, _, _ = self.run_stub([200], payload=payload)
        with self.assertRaisesRegex(ValueError, "usage missing"):
            crosswalk.validate(result[0], self.body)

    def test_wrong_probability_keys_remain_invalid(self):
        payload = json.loads(json.dumps(self.payload))
        payload["answers"]["blocker"]["probabilities"] = {"other": 1.0}
        result, _, _, _ = self.run_stub([200], payload=payload)
        with self.assertRaisesRegex(ValueError, "bad answer for blocker"):
            crosswalk.validate(result[0], self.body)


if __name__ == "__main__":
    unittest.main()
