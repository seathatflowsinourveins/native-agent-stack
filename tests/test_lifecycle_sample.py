"""Synthetic lifecycle documents; no network, private records or provider prices."""
import importlib.util
import importlib.metadata
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "blueprints/us-equities/lifecycle-sample"


def load():
    spec = importlib.util.spec_from_file_location("lifecycle_sample", HERE / "sample.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.m = load()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def fixture(self, name="capture", mutate=None):
        m = self.m
        root = self.root / name
        root.mkdir()
        def put(name, raw):
            (root / name).write_bytes(raw)
            return m.B.digest(name, raw)
        plan = put("plan.json", (HERE / "plan.json").read_bytes())
        transport = {"library": "requests", "version": "2.34.2", "sources": [{"module": x, "sha256": "a"*64, "bytes": 1} for x in ["requests.adapters", "requests.models", "requests.sessions"]],
                     "capture_code": {"sha256": "b"*64, "bytes": 1}, "shared_helper": m.B.digest("alpaca-historical/collect.py", m.B.read(m.BASE)),
                     "automatic_retries": 0, "environment_proxy_and_netrc": False}
        freeze = put("freeze.json", m.B.encode({"frozen_at": "2026-09-20T13:00:00.000000000Z", "plan_sha256": m.PLAN_SHA, "transport": transport}))
        sources = []
        for i, spec in enumerate(m.plan()["sources"]):
            name = spec["source_id"]
            text = " ".join(m.POLICY[name][-1]) if name in m.POLICY else "synthetic metadata"
            source = {"source_id": name, "url": spec["url"], "started_at": f"2026-09-20T13:00:00.{i*2+1:09d}Z", "observed_at": f"2026-09-20T13:00:00.{i*2+2:09d}Z", "status": 200,
                      "body_complete": True, "transport_error": None, "actual_request": {"method": "GET", "url": spec["url"]}}
            if mutate:
                source, text = mutate(i, source, text)
            source["body"] = put(name + ".body", text.encode())
            source["meta"] = put(name + ".meta.json", m.B.encode(source))
            sources.append(source)
        manifest = {"schema_version": 1, "kind": "lifecycle-source-capture-v1", "synthetic": True, "sources": sources,
                    "plan": plan, "freeze": freeze, "transport": transport,
                    "http_attempts": sum(s["transport_error"] != "skipped_origin_access_refusal" for s in sources)}
        raw = m.B.encode(manifest)
        (root / "manifest.json").write_bytes(raw)
        return root, m.B.sha(raw)

    @staticmethod
    def fake_parse(source_id, raw):
        return {"text": raw.decode(), "metadata": {"acceptance_utc_ns": None}}

    def qualify(self, **kwargs):
        source, anchor = self.fixture(**kwargs)
        out = self.root / "qualified"
        result = self.m.qualify(source, anchor, out, self.fake_parse)
        return out, result["receipt_sha256"], result

    def test_documentary_identity_and_observation_axes_stay_separate(self):
        m = load()
        row = m.claim("meta_release", " ".join(m.POLICY["meta_release"][-1]), 100, "a" * 64)
        self.assertEqual(row["available_ns"], 100)
        self.assertEqual(row["effective_date"], "2022-06-09")
        self.assertIsNone(row["permanent_security_id"])
        self.assertIsNone(row["original_publication_ns"])
        self.assertFalse(row["historical_universe_eligible"])
        self.assertEqual(row["status"], "supported_documentary_claim")

    def test_reuse_has_distinct_documentary_scopes_without_price_or_id_merge(self):
        out, anchor, result = self.qualify()
        _, rows = self.m.verify(out, anchor)
        self.assertEqual(len(rows), 3)
        self.assertEqual(result["supported_claims"], 3)
        self.assertTrue(result["relationships"]["documented_meta_ticker_reuse"])
        self.assertFalse(result["relationships"]["permanent_identity_crosswalk_established"])
        self.assertFalse(result["relationships"]["quarantined_bar_origin_established"])
        self.assertNotEqual(rows[0]["documentary_security_scope"], rows[1]["documentary_security_scope"])

    def test_unavailable_source_and_origin_refusal_remain_explicit(self):
        def mutate(i, s, text):
            if i == 2:
                s["status"] = 403
                return s, "denied"
            if i > 2:
                s.update(status=None, body_complete=False, transport_error="skipped_origin_access_refusal", actual_request=None)
                return s, ""
            return s, text
        out, anchor, result = self.qualify(mutate=mutate)
        _, rows = self.m.verify(out, anchor)
        self.assertEqual(result["supported_claims"], 2)
        self.assertIsNone(rows[-1]["effective_date"])
        self.assertEqual(result["source_statuses"]["twtr_25_sgml"], "source_unavailable")

    def test_wrong_scope_late_precision_and_origin_refusal_violation_rejected(self):
        for label in ["url", "precision", "refusal"]:
            def mutate(i, s, text):
                if i == 2:
                    if label == "url": s["actual_request"]["url"] += "?other=1"
                    if label == "precision": s["observed_at"] = "2026-09-20T13:00:00.0000000001Z"
                    if label == "refusal": s["status"] = 403
                return s, text
            source, anchor = self.fixture(label, mutate)
            with self.assertRaises(ValueError): self.m.capture(source, anchor)

    def test_source_tamper_wrong_anchor_extra_files_and_overwrite_refused(self):
        source, anchor = self.fixture()
        with self.assertRaisesRegex(ValueError, "anchor"): self.m.capture(source, "0"*64)
        body = source / "meta_release.body"
        raw = body.read_bytes()
        body.write_bytes(raw + b"x")
        with self.assertRaisesRegex(ValueError, "artifact_hash"): self.m.capture(source, anchor)
        body.write_bytes(raw)
        extra = source / "extra"
        extra.write_bytes(b"x")
        with self.assertRaisesRegex(ValueError, "artifact_set"): self.m.capture(source, anchor)
        extra.unlink()
        out = self.root / "qualified"
        self.m.qualify(source, anchor, out, self.fake_parse)
        with self.assertRaises(FileExistsError): self.m.qualify(source, anchor, out, self.fake_parse)

    def test_offline_verify_never_discovers_runtime_or_fetches(self):
        out, anchor, _ = self.qualify()
        with patch.object(self.m, "native_identity", side_effect=AssertionError("native discovery forbidden")), patch.object(self.m, "native_parse", side_effect=AssertionError("parse forbidden")):
            self.m.verify(out, anchor)

    def test_parser_failure_does_not_erase_good_sources(self):
        source, anchor = self.fixture()
        def parse(name, raw):
            if name == "meta_release": raise ValueError("private parser detail")
            return self.fake_parse(name, raw)
        result = self.m.qualify(source, anchor, self.root / "qualified", parse)
        self.assertEqual(result["supported_claims"], 2)
        self.assertEqual(result["source_statuses"]["meta_release"], "native_parse_failed")

    def test_missing_witness_is_unresolved_not_silently_inferred(self):
        row = self.m.claim("twtr_8k_sgml", "Twitter NYSE October 28, 2022", 101, "b"*64)
        self.assertEqual(row["status"], "unresolved_missing_document_witness")
        self.assertIsNone(row["effective_date"])
        self.assertIsNone(row["legal_delisting_effective_ns"])

    def test_timing_is_not_promoted_when_source_witness_is_missing(self):
        for source_id in ["meta_release", "roundhill_release"]:
            markers = self.m.POLICY[source_id][-1]
            row = self.m.claim(source_id, " ".join(markers[:-1]), 100, "b"*64)
            self.assertEqual(row["status"], "unresolved_missing_document_witness")
            self.assertIsNone(row["effective_timing"])

    def test_qualified_tamper_and_code_replacement_refused(self):
        out, anchor, _ = self.qualify()
        (out / "claims.json").write_text("[]")
        with self.assertRaisesRegex(ValueError, "artifact_hash"): self.m.verify(out, anchor)

    def test_native_duckdb_observation_boundaries_and_parquet_reconciliation(self):
        try: version = importlib.metadata.version("duckdb")
        except importlib.metadata.PackageNotFoundError: self.skipTest("DuckDB runtime not installed")
        if version != "1.5.5": self.skipTest("Different DuckDB runtime")
        out, anchor, _ = self.qualify()
        ledger = self.root / "ledger"
        result = self.m.materialize(out, anchor, ledger)
        verified = self.m.verify_ledger(ledger, result["receipt_sha256"])
        proof = verified["proof"]
        self.assertEqual([proof[k]["eligible_documentary_claims"] for k in ["historical", "before_first_observation", "at_first_observation", "at_last_observation"]], [0,0,1,3])
        self.assertEqual(proof["historical"], proof["historical_replay"])
        with self.assertRaises(ValueError): self.m.selection(None, "", True)
        (ledger / "claims.parquet").write_bytes(b"bad")
        with self.assertRaisesRegex(ValueError, "artifact_hash"): self.m.verify_ledger(ledger, result["receipt_sha256"])

    def test_native_edgar_html_parser_and_naive_acceptance(self):
        try: version = importlib.metadata.version("edgartools")
        except importlib.metadata.PackageNotFoundError: self.skipTest("EdgarTools runtime not installed")
        if version != "5.58.0": self.skipTest("Different EdgarTools runtime")
        raw = b"<html><body><p>Synthetic lifecycle document</p></body></html>"
        parsed = self.m.native_parse("meta_release", raw)
        self.assertIn("Synthetic lifecycle document", parsed["text"])
        self.assertIsNone(parsed["metadata"]["acceptance_utc_ns"])
        identity = self.m.native_identity()
        self.assertEqual(len(identity["sources"]), 4)
        # The fixed accession is a schema selector; this body/header is fabricated.
        sgml = """<SEC-DOCUMENT>0001193125-22-272772.txt : 20230102
<SEC-HEADER>0001193125-22-272772.hdr.sgml : 20230102
<ACCEPTANCE-DATETIME>20230102030405
ACCESSION NUMBER: 0001193125-22-272772
CONFORMED SUBMISSION TYPE: 8-K
PUBLIC DOCUMENT COUNT: 1
FILED AS OF DATE: 20230102
FILER:
\tCOMPANY DATA:
\t\tCOMPANY CONFORMED NAME: SYNTHETIC TEST ONLY
\t\tCENTRAL INDEX KEY: 0000000001
</SEC-HEADER>
<DOCUMENT>
<TYPE>8-K
<SEQUENCE>1
<FILENAME>synthetic.htm
<TEXT>
<html><body><p>Synthetic only</p></body></html>
</TEXT>
</DOCUMENT>
</SEC-DOCUMENT>"""
        parsed = self.m.native_parse("twtr_8k_sgml", sgml.encode())
        self.assertEqual(parsed["metadata"]["acceptance_raw"], "2023-01-02 03:04:05")
        self.assertIsNone(parsed["metadata"]["acceptance_zone"])
        self.assertIsNone(parsed["metadata"]["acceptance_utc_ns"])


if __name__ == "__main__":
    unittest.main()
