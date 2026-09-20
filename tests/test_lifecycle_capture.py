import importlib.metadata
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("lifecycle_capture", ROOT / "blueprints/us-equities/catalyst-convergence/capture_sources.py")
C = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(C)
try:
    importlib.metadata.version("requests")
    HAS_REQUESTS = True
except importlib.metadata.PackageNotFoundError:
    HAS_REQUESTS = False


class Response:
    def __init__(self, chunks, url="https://www.sec.gov/example", status=200):
        self.chunks, self.status_code, self.closed = chunks, status, False
        self.request = type("Request", (), {"url": url, "method": "GET"})()

    def iter_content(self, chunk_size):
        for item in self.chunks:
            if isinstance(item, Exception):
                raise item
            yield item

    def close(self):
        self.closed = True


class Session:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.response

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


@unittest.skipUnless(HAS_REQUESTS, "optional native Requests dependency unavailable")
class CaptureTests(unittest.TestCase):
    source = {"source_id": "fixture", "url": "https://www.sec.gov/example"}

    def test_single_get_preserves_body_and_refusal(self):
        response = Response([b"denied"], status=403)
        session = Session(response)
        entry, body = C.fetch(session, self.source, "Research test@example.invalid")
        self.assertEqual((entry["status"], body, entry["body_complete"]), (403, b"denied", True))
        self.assertEqual(len(session.calls), 1)
        self.assertFalse(session.calls[0][1]["allow_redirects"])
        self.assertEqual(session.calls[0][1]["timeout"], (10, 30))
        self.assertTrue(response.closed)

    def test_oversized_body_retains_only_bounded_prefix(self):
        response = Response([b"abc", b"def"])
        with patch.object(C.B, "MAX_BODY", 4):
            entry, body = C.fetch(Session(response), self.source, "Research test@example.invalid")
        self.assertEqual(body, b"abcd")
        self.assertFalse(entry["body_complete"])
        self.assertEqual(entry["transport_error"], "body_limit_exceeded")
        self.assertTrue(response.closed)

    def test_interrupted_body_retains_prefix_without_exception_details(self):
        import requests
        response = Response([b"prefix", requests.ConnectionError("sensitive diagnostic")])
        entry, body = C.fetch(Session(response), self.source, "Research test@example.invalid")
        self.assertEqual(body, b"prefix")
        self.assertEqual(entry["transport_error"], "ConnectionError")
        self.assertFalse(entry["body_complete"])
        self.assertNotIn("sensitive", str(entry))

    def test_scope_mismatch_does_not_consume_body(self):
        response = Response([b"unexpected"], url="https://other.invalid/")
        entry, body = C.fetch(Session(response), self.source, "Research test@example.invalid")
        self.assertEqual(body, b"")
        self.assertEqual(entry["transport_error"], "prepared_request_scope_mismatch")

    def test_sec_contact_is_not_forwarded_to_other_publishers(self):
        url = "https://issuer.invalid/release"
        session = Session(Response([b"ok"], url=url))
        C.fetch(session, {"source_id": "issuer", "url": url}, "Research test@example.invalid")
        self.assertEqual(session.calls[0][1]["headers"]["User-Agent"], C.PUBLIC_IDENTITY)

    def test_origin_refusal_skips_later_request_but_keeps_other_publisher(self):
        sources = [{"source_id": key, "url": url} for key, url in [
            ("one", "https://www.sec.gov/first"), ("two", "https://www.sec.gov/second"),
            ("three", "https://issuer.invalid/release")]]
        raw_plan = C.B.encode({"sources": sources})
        class Routed(Session):
            def get(self, url, **kwargs):
                self.calls.append((url, kwargs))
                return Response([b"body"], url=url, status=403 if "sec.gov" in url else 200)
        session = Routed(None)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            plan = root / "input.json"
            plan.write_bytes(raw_plan)
            with patch.object(C, "PLAN_SHA256", C.B.sha(raw_plan)), \
                 patch.object(C, "native_session", return_value=session), \
                 patch.object(C, "transport_identity", return_value={"synthetic_test": True}), \
                 patch.dict(C.os.environ, {"SEC_USER_AGENT": "Research test@example.invalid"}):
                result = C.capture(plan, root / "capture")
            manifest = json.loads((root / "capture/manifest.json").read_text())
            self.assertEqual(result["http_attempts"], 2)
            self.assertEqual(len(session.calls), 2)
            self.assertEqual([x["status"] for x in manifest["sources"]], [403, None, 200])
            skipped = manifest["sources"][1]
            self.assertEqual(skipped["transport_error"], "skipped_origin_access_refusal")
            self.assertIsNone(skipped["actual_request"])
            self.assertEqual((root / "capture/two.body").read_bytes(), b"")
            meta = json.loads((root / "capture/two.meta.json").read_text())
            self.assertEqual(meta, {k: v for k, v in skipped.items() if k != "meta"})
            self.assertEqual(skipped["meta"]["sha256"], C.B.sha((root / "capture/two.meta.json").read_bytes()))
            self.assertEqual(manifest["freeze"]["sha256"], C.B.sha((root / "capture/freeze.json").read_bytes()))

    def test_git_checkout_output_is_refused_before_native_session(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / ".git").write_text("gitdir: /fixture/not-used")
            plan = root / "plan.json"
            raw = b"{}"
            plan.write_bytes(raw)
            with patch.object(C, "PLAN_SHA256", C.B.sha(raw)), \
                 patch.object(C, "native_session") as session, \
                 patch.dict(C.os.environ, {"SEC_USER_AGENT": "Research test@example.invalid"}):
                with self.assertRaisesRegex(ValueError, "inside_git"):
                    C.capture(plan, root / "private")
                session.assert_not_called()
                self.assertFalse((root / "private").exists())


if __name__ == "__main__":
    unittest.main()
