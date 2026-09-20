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


if __name__ == "__main__":
    unittest.main()
