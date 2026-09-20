"""Synthetic transport fixtures and native DuckDB checks; no provider requests."""
import copy
import hashlib
import importlib.metadata
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
HERE = ROOT / "blueprints/us-equities/security-identity"
OBS = "2026-09-20T12:00:00.000000100Z"


def load(name):
    path = HERE / (name + ".py")
    if not path.exists():
        return None
    spec = importlib.util.spec_from_file_location("identity_" + name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def row(day, price):
    return {"t": day + "T04:00:00Z", "o": price, "h": price + 2,
            "l": price - 2, "c": price + 1, "v": 1000, "n": 50, "vw": price}


class SecurityIdentityTests(unittest.TestCase):
    def setUp(self):
        self.p = load("probe")
        self.assertIsNotNone(self.p, "identity probe not implemented")
        self.plan = json.loads((HERE / "plan.json").read_text())
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.clock = 0

    def payloads(self, case_id):
        all_rows = [row(day, 100 + i) for i, day in enumerate(self.plan["session_dates"])]
        if case_id == "meta_current":
            return [{"id": str(UUID(int=2)), "symbol": "META", "status": "active",
                     "exchange": "NASDAQ", "class": "us_equity", "tradable": True}]
        case = next(c for c in self.plan["cases"] if c["case_id"] == case_id)
        rows = all_rows[1:] if case_id == "meta_unmapped" else all_rows[:1] if case_id == "fb_unmapped" else all_rows
        return [{"bars": {case["symbol"]: rows[i:i+2]}, "next_page_token": "second" if i+2 < len(rows) else None}
                for i in range(0, len(rows), 2)]

    def fetch(self, case_id, query):
        pages = self.payloads(case_id)
        body = pages[1 if query.get("page_token") else 0]
        self.clock += 1
        endpoint = self.plan["asset"]["url"] if case_id == "meta_current" else self.plan["bars_url"]
        return {"body": json.dumps(body).encode(), "body_complete": True, "status": 200,
                "started_at": f"2026-09-20T12:00:00.{self.clock*100:09d}Z",
                "observed_at": f"2026-09-20T12:00:00.{self.clock*100+1:09d}Z", "transport_error": None,
                "actual_request": {"method": "GET", "url": endpoint + ("?" + urlencode(query) if query else "")}}

    def collect(self, name="run", fetch=None):
        with patch.object(self.p, "native_identity", return_value={"alpaca_py_version": "0.44.0", "sources": []}):
            summary = self.p.collect(self.root / name, fetch or self.fetch)
        return self.root / name, summary["receipt_sha256"]

    def test_query_cases_are_not_merged_and_current_validity_is_unknown(self):
        path, anchor = self.collect()
        result = self.p.verify(path, anchor)
        self.assertEqual([len(result["cases"][c]["rows"]) for c in ["meta_mapped", "fb_mapped", "meta_unmapped", "fb_unmapped"]], [3, 3, 2, 1])
        asset = result["asset"]["rows"][0]
        for key in ["valid_from", "valid_to", "original_publication_at", "provider_revision_at"]:
            self.assertIsNone(asset[key])
        self.assertFalse(asset["historical_universe_eligible"])
        self.assertEqual(result["comparison"]["mapped_alias"]["equal_rows"], 3)
        self.assertFalse(result["comparison"]["permanent_identity_established"])

    def test_each_wire_scope_is_checked_before_acceptance(self):
        def fetch(case_id, query):
            page = self.fetch(case_id, query)
            if case_id == "meta_mapped":
                page["actual_request"]["url"] = page["actual_request"]["url"].replace("asof=2022-06-10", "asof=2022-06-08")
            return page
        path, anchor = self.collect(fetch=fetch)
        result = self.p.verify(path, anchor)
        self.assertEqual(result["cases"]["meta_mapped"]["reason"], "wire_request_mismatch")
        self.assertEqual(result["cases"]["fb_mapped"]["status"], "complete")

    def test_duplicate_bars_missing_tokens_and_cap_are_failures(self):
        for problem in ["duplicate", "missing_token", "cycle", "cap"]:
            calls = []
            def fetch(case_id, query):
                page = self.fetch(case_id, query)
                if case_id == "meta_mapped":
                    calls.append(query)
                    body = json.loads(page["body"])
                    if problem == "duplicate" and query.get("page_token"):
                        body["bars"]["META"] = [row("2022-06-08", 100)]
                    elif problem == "missing_token":
                        body.pop("next_page_token")
                    elif problem == "cycle":
                        body["next_page_token"] = "second"
                    elif problem == "cap":
                        body = {"bars": {}, "next_page_token": "next" + str(len(calls))}
                    page["body"] = json.dumps(body).encode()
                return page
            path, anchor = self.collect(problem, fetch)
            result = self.p.verify(path, anchor)
            self.assertEqual(result["cases"]["meta_mapped"]["status"], "failed")
            self.assertLessEqual(len(calls), 3)

    def test_empty_cases_and_asset_404_remain_observations(self):
        def fetch(case_id, query):
            page = self.fetch(case_id, query)
            if case_id == "meta_unmapped":
                page["body"] = b'{"bars":{},"next_page_token":null}'
            if case_id == "meta_current":
                page["status"], page["body"] = 404, b'{"message":"synthetic not found"}'
            return page
        path, anchor = self.collect(fetch=fetch)
        result = self.p.verify(path, anchor)
        self.assertEqual(result["cases"]["meta_unmapped"]["status"], "complete")
        self.assertEqual(result["cases"]["meta_unmapped"]["rows"], [])
        self.assertEqual(result["asset"]["reason"], "http_404")
        self.assertFalse(result["comparison"]["historical_delisting_established"])

    def test_tamper_external_anchor_and_overwrite_are_rejected(self):
        path, anchor = self.collect()
        with self.assertRaises(FileExistsError):
            self.p.collect(path, self.fetch)
        with self.assertRaisesRegex(ValueError, "receipt_hash_mismatch"):
            self.p.verify(path, "0" * 64)
        source = path / "meta_mapped-001.json"
        source.write_bytes(source.read_bytes() + b" ")
        with self.assertRaisesRegex(ValueError, "artifact_hash_mismatch"):
            self.p.verify(path, anchor)

    @unittest.skipUnless(importlib.util.find_spec("duckdb"), "requires the native DuckDB environment")
    def test_native_ledger_exact_observation_boundary_and_case_scope(self):
        ledger = load("ledger")
        self.assertIsNotNone(ledger, "identity ledger not implemented")
        path, anchor = self.collect()
        out = self.root / "ledger"
        result = ledger.materialize(path, anchor, out)
        self.assertEqual(result["counts"], {"bars": 9, "assets": 1})
        proof = result["eligibility"]
        self.assertEqual(proof["historical"]["count"], 0)
        self.assertEqual(proof["before_first_observation"]["count"], 0)
        self.assertEqual(proof["at_first_observation"]["count"], 2)
        self.assertEqual(proof["at_last_observation"]["count"], 9)
        self.assertEqual(proof["historical_replay"]["count"], 0)
        selected = ledger.select(out, result["manifest_sha256"], "2026-09-21T00:00:00Z", "fb_unmapped")
        self.assertEqual(selected["count"], 1)
        self.assertNotIn("rows", selected)
        with self.assertRaisesRegex(ValueError, "query_case"):
            ledger.select(out, result["manifest_sha256"], "2026-09-21T00:00:00Z", "arbitrary")

    @unittest.skipUnless(importlib.util.find_spec("duckdb"), "requires the native DuckDB environment")
    def test_ledger_tamper_source_tamper_and_overwrite(self):
        ledger = load("ledger")
        self.assertIsNotNone(ledger)
        path, anchor = self.collect()
        out = self.root / "ledger"
        result = ledger.materialize(path, anchor, out)
        with self.assertRaises(FileExistsError):
            ledger.materialize(path, anchor, out)
        with self.assertRaisesRegex(ValueError, "manifest_hash"):
            ledger.select(out, "0" * 64, "2026-09-21T00:00:00Z", "fb_mapped")
        parquet = out / "bars.parquet"
        parquet.write_bytes(parquet.read_bytes() + b" ")
        with self.assertRaisesRegex(ValueError, "artifact_hash"):
            ledger.select(out, result["manifest_sha256"], "2026-09-21T00:00:00Z", "fb_mapped")

    def test_synthetic_conflicting_revision_tie_has_no_invented_sequence(self):
        ledger = load("ledger")
        self.assertIsNotNone(ledger)
        path, anchor = self.collect()
        rows = ledger.bar_records(self.p.verify(path, anchor), anchor)
        hypothetical = copy.deepcopy(rows[0])
        hypothetical["c"] = "999"
        with self.assertRaisesRegex(ValueError, "ambiguous_semantic_revision"):
            ledger.validate_rows(rows + [hypothetical])
        hypothetical["observed_ns"] += 1
        hypothetical["available_ns"] += 1
        ledger.validate_rows(rows + [hypothetical])

    def test_native_transport_uses_only_frozen_bars_and_single_paper_asset(self):
        try:
            importlib.metadata.version("alpaca-py")
        except importlib.metadata.PackageNotFoundError:
            self.skipTest("requires the optional native Alpaca SDK")
        self.p.native_identity()
        from requests import Response
        from requests.adapters import BaseAdapter
        calls = []
        class SyntheticHTTP(BaseAdapter):
            def send(self, request, **kwargs):
                calls.append((request.method, request.url, kwargs))
                response = Response()
                response.status_code = 200
                response.raw = io.BytesIO(b'{"bars":{},"next_page_token":null}')
                response.request, response.url = request, request.url
                return response
            def close(self):
                pass
        transport = self.p.NativeIdentityPages("synthetic-key", "synthetic-secret", self.plan)
        self.addCleanup(transport.close)
        for client in transport.clients.values():
            client._session.mount("https://", SyntheticHTTP())
        for case_id, symbol, asof in self.p.CASES:
            result = transport(case_id, self.p.query(self.plan, case_id))
            self.assertTrue(result["body_complete"])
            self.assertIn("symbols=" + symbol, result["actual_request"]["url"])
            self.assertIn("asof=" + asof, result["actual_request"]["url"])
            self.assertIn("end=2022-06-10T23%3A59%3A59.999999999Z", result["actual_request"]["url"])
        result = transport("meta_current", {})
        self.assertEqual(result["actual_request"]["url"], "https://paper-api.alpaca.markets/v2/assets/META")
        self.assertEqual(len(calls), 5)
        self.assertTrue(all(method == "GET" and opts["timeout"] == (10, 30) for method, _, opts in calls))
        with self.assertRaisesRegex(ValueError, "unsupported_transport_request"):
            transport.clients["meta_current"]._session.request("POST", "https://paper-api.alpaca.markets/v2/orders", allow_redirects=False)
        self.assertEqual(len(calls), 5)

    def test_numeric_precision_bad_symbols_and_half_open_bounds(self):
        for changes in [{"o": True}, {"c": None}, {"h": 1}, {"n": 0.1}, {"t": "2022-06-11T00:00:00Z"}, {"t": "2022-06-08T04:00:00.000000001Z"}]:
            self.clock = 0
            def fetch(case_id, query):
                page = self.fetch(case_id, query)
                if case_id == "meta_mapped":
                    body = json.loads(page["body"])
                    body["bars"]["META"][0].update(changes)
                    page["body"] = json.dumps(body).encode()
                return page
            path, anchor = self.collect("bad-" + str(len(list(self.root.iterdir()))), fetch)
            self.assertEqual(self.p.verify(path, anchor)["cases"]["meta_mapped"]["status"], "failed")
        for timestamp in ["2026-09-20T12:00:00.0000000001Z", "2263-01-01T00:00:00Z", "2022-02-30T00:00:00Z"]:
            with self.assertRaises(ValueError):
                self.p.ns(timestamp)
        self.assertEqual(self.p.ns("2026-09-20T12:00:00.000000001Z") - self.p.ns("2026-09-20T12:00:00Z"), 1)

    def test_reforged_current_historical_validity_fails_source_replay(self):
        path, anchor = self.collect()
        receipt = json.loads((path / "receipt.json").read_bytes())
        receipt["stages"]["meta_current"]["assessment"]["rows"][0]["valid_from"] = "2022-06-08"
        raw = json.dumps(receipt).encode()
        (path / "receipt.json").write_bytes(raw)
        with self.assertRaisesRegex(ValueError, "assessment_mismatch"):
            self.p.verify(path, hashlib.sha256(raw).hexdigest())

    def test_symlink_and_unexpected_source_files_are_refused(self):
        path, anchor = self.collect()
        (self.root / "alias").symlink_to(path, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.p.verify(self.root / "alias", anchor)
        (path / "unexpected.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "unexpected_artifact"):
            self.p.verify(path, anchor)

    def zero_capture(self):
        def fetch(case_id, request):
            page = self.fetch(case_id, request)
            if case_id == "meta_unmapped":
                page["body"] = json.dumps({"bars": {"META": [dict(row("2022-06-08", 100), v=0, n=0, vw=0), row("2022-06-09", 101)]}, "next_page_token": "retained-continuation"}).encode()
            return page
        return self.collect("zero-source", fetch)

    def test_zero_activity_reparse_preserves_failed_source_and_partial_query(self):
        quality = load("quality")
        self.assertIsNotNone(quality, "offline quality derivation not implemented")
        source, anchor = self.zero_capture()
        original = {p.name: p.read_bytes() for p in source.iterdir()}
        out = self.root / "quality"
        summary = quality.derive(source, anchor, out)
        result = quality.verify(out, summary["receipt_sha256"])
        case = result["cases"]["meta_unmapped"]
        self.assertEqual(case["status"], "partial")
        self.assertEqual(case["source_status"], "failed")
        self.assertEqual(case["summary"]["rows"], 2)
        self.assertEqual(case["summary"]["qualified_rows"], 1)
        self.assertEqual(case["rows"][0]["vw"], "0")
        self.assertTrue(case["rows"][0]["reported_zero_activity"])
        self.assertFalse(case["rows"][0]["price_observation_qualified"])
        self.assertEqual(original, {p.name: p.read_bytes() for p in source.iterdir()})
        self.assertEqual(self.p.verify(source, anchor)["cases"]["meta_unmapped"]["reason"], "invalid_numeric_field")

    def test_resume_only_uses_retained_token_and_missing_case(self):
        quality = load("quality")
        self.assertIsNotNone(quality)
        source, anchor = self.zero_capture()
        calls = []
        def continuation(case_id, request):
            calls.append((case_id, request.copy()))
            page = self.fetch(case_id, {})
            page["actual_request"]["url"] = self.plan["bars_url"] + "?" + urlencode(request)
            page["body"] = json.dumps({"bars": {"META": [row("2022-06-10", 102)]}, "next_page_token": None}).encode()
            return page
        out = self.root / "resumed"
        summary = quality.derive(source, anchor, out, resume=True, fetch=continuation)
        result = quality.verify(out, summary["receipt_sha256"])
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], "meta_unmapped")
        self.assertEqual(calls[0][1]["page_token"], "retained-continuation")
        self.assertEqual(result["cases"]["meta_unmapped"]["summary"]["rows"], 3)
        self.assertEqual(result["cases"]["meta_unmapped"]["status"], "complete")
        self.assertEqual(result["cases"]["meta_unmapped"]["rows"][-1]["source_phase"], "continuation")
        if importlib.util.find_spec("duckdb"):
            ledger = load("ledger")
            built = ledger.materialize(out, summary["receipt_sha256"], self.root / "quality-ledger", derived=True)
            self.assertEqual(built["counts"]["bars"], 10)
            self.assertEqual(built["eligibility"]["at_last_observation"]["qualified_count"], 9)
            self.assertEqual(built["eligibility"]["at_last_observation"]["quarantined_count"], 1)

    def test_quality_rejects_boolean_zero_and_incomplete_continuation_stays_partial(self):
        quality = load("quality")
        self.assertIsNotNone(quality)
        source, anchor = self.zero_capture()
        calls = []
        def continuation(case_id, request):
            calls.append(request)
            page = self.fetch(case_id, {})
            page["actual_request"]["url"] = self.plan["bars_url"] + "?" + urlencode(request)
            page["body"] = json.dumps({"bars": {}, "next_page_token": "more-" + str(len(calls))}).encode()
            return page
        out = self.root / "capped"
        result = quality.derive(source, anchor, out, resume=True, fetch=continuation)
        self.assertEqual(len(calls), 2)
        self.assertEqual(quality.verify(out, result["receipt_sha256"])["cases"]["meta_unmapped"]["status"], "partial")
        bad = dict(row("2022-06-08", 100), v=False, n=0, vw=0)
        case = self.plan["cases"][2]
        page = self.fetch("meta_unmapped", {})
        with self.assertRaises(ValueError):
            quality.normalized_bar(bad, case, page, self.plan, "original_capture")

    def test_quality_external_anchor_tamper_and_refused_continuation(self):
        quality = load("quality")
        source, anchor = self.zero_capture()
        calls = []
        def refusal(case_id, request):
            calls.append((case_id, request))
            page = self.fetch(case_id, {})
            page["actual_request"]["url"] = self.plan["bars_url"] + "?" + urlencode(request)
            page["status"], page["body"] = 429, b'{"message":"synthetic refusal"}'
            return page
        out = self.root / "refused"
        receipt = quality.derive(source, anchor, out, resume=True, fetch=refusal)
        result = quality.verify(out, receipt["receipt_sha256"])
        case = result["cases"]["meta_unmapped"]
        self.assertEqual(len(calls), 1)
        self.assertEqual((case["status"], case["reason"], len(case["rows"])), ("failed", "http_429", 2))
        with self.assertRaises(FileExistsError):
            quality.derive(source, anchor, out)
        with self.assertRaisesRegex(ValueError, "receipt_hash_mismatch"):
            quality.verify(out, "0" * 64)
        path = out / "continuation-001.json"
        path.write_bytes(path.read_bytes() + b" ")
        with self.assertRaisesRegex(ValueError, "artifact_hash_mismatch"):
            quality.verify(out, receipt["receipt_sha256"])

    def test_quality_derived_ledger_select_preserves_quarantine(self):
        if not importlib.util.find_spec("duckdb"):
            self.skipTest("requires native DuckDB")
        quality, ledger = load("quality"), load("ledger")
        source, anchor = self.zero_capture()
        derived = self.root / "offline-quality"
        summary = quality.derive(source, anchor, derived)
        out = self.root / "offline-ledger"
        built = ledger.materialize(derived, summary["receipt_sha256"], out, derived=True)
        manifest, _ = ledger.verified(out, built["manifest_sha256"])
        self.assertEqual(manifest["source_receipt_sha256"], summary["receipt_sha256"])
        import duckdb
        with duckdb.connect() as connection:
            lineage = connection.read_parquet(str(out / "bars.parquet")).project("acquisition_receipt_sha256, derivation_receipt_sha256").distinct().fetchall()
        self.assertEqual(lineage, [(anchor, summary["receipt_sha256"])])
        result = ledger.select(out, built["manifest_sha256"], "2026-09-21T00:00:00Z", "meta_unmapped")
        self.assertEqual((result["count"], result["qualified_count"], result["quarantined_count"]), (2, 1, 1))
        self.assertFalse(result["historical_universe_eligible"])
        self.assertEqual(built["source_statuses"]["meta_unmapped"]["status"], "partial")

    def test_continuation_freezes_current_sdk_before_client_and_offline_needs_none(self):
        quality = load("quality")
        source, anchor = self.zero_capture()
        offline = self.root / "without-sdk"
        with patch.object(quality.P, "native_identity", side_effect=AssertionError("offline must not inspect SDK")):
            summary = quality.derive(source, anchor, offline)
            quality.verify(offline, summary["receipt_sha256"])
        out, events = self.root / "native-seam", []
        identity = {"alpaca_py_version": "0.44.0", "requests_version": "synthetic-fixture", "sources": [self.p.B.digest("synthetic.py", b"synthetic source")]}
        def identify():
            events.append("identity")
            return identity
        def client_factory(*_):
            frozen = json.loads((out / "freeze.json").read_bytes())
            self.assertEqual(frozen["continuation_runtime"]["identity"], identity)
            events.append("client")
            class Client:
                def __call__(inner, case_id, query):
                    events.append("request")
                    page = self.fetch(case_id, {})
                    page["actual_request"]["url"] = self.plan["bars_url"] + "?" + urlencode(query)
                    page["body"] = json.dumps({"bars": {"META": [row("2022-06-10", 102)]}, "next_page_token": None}).encode()
                    return page
                def close(inner):
                    pass
            return Client()
        with patch.object(quality.P, "native_identity", side_effect=identify), patch.object(quality.P, "NativeIdentityPages", side_effect=client_factory), patch.dict("os.environ", {"APCA_API_KEY_ID": "synthetic-key", "APCA_API_SECRET_KEY": "synthetic-secret"}):
            summary = quality.derive(source, anchor, out, resume=True)
        self.assertEqual(events, ["identity", "client", "request"])
        with patch.object(quality.P, "native_identity", side_effect=AssertionError("verify must not inspect SDK")):
            result = quality.verify(out, summary["receipt_sha256"])
        self.assertEqual(result["continuation_runtime"]["identity"], identity)


if __name__ == "__main__":
    unittest.main()
