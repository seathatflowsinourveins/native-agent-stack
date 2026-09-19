"""Offline adversarial checks for the SEC snapshot and availability boundary."""
import copy
import importlib.util
import io
import http.client
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / "blueprints/us-equities/financial-data/sec_data.py"
SPEC = importlib.util.spec_from_file_location("sec_data", SOURCE) if SOURCE.exists() else None
SEC = importlib.util.module_from_spec(SPEC) if SPEC else None
if SPEC:
    SPEC.loader.exec_module(SEC)

ACCN = "0000320193-25-000001"
ACCN2 = "0000320193-25-000002"
OBSERVED = "2026-09-19T12:00:00Z"


def submissions():
    return {"cik": "0000320193", "filings": {"recent": {
        "accessionNumber": [ACCN, ACCN2],
        "acceptanceDateTime": ["2025-02-01T21:00:00Z", "2025-03-01T21:00:00Z"],
        "filingDate": ["2025-02-01", "2025-03-01"],
        "form": ["10-Q", "10-Q/A"],
        "primaryDocument": ["aapl-20241231.htm", "aapl-amendment.htm"],
    }, "files": []}}


def facts():
    return {"cik": 320193, "entityName": "Illustrative Test Entity", "facts": {"us-gaap": {
        "Assets": {"units": {"USD": [
            {"end": "2024-12-31", "val": 100, "accn": ACCN, "fy": 2025,
             "fp": "Q1", "form": "10-Q", "filed": "2025-02-01"},
            {"end": "2024-12-31", "val": 90, "accn": ACCN2, "fy": 2025,
             "fp": "Q1", "form": "10-Q/A", "filed": "2025-03-01"},
        ]}}}}}


def normalize(data=None, metadata=None):
    return SEC.normalize_facts(
        "AAPL", "0000320193", data or facts(), metadata or submissions(),
        {"sha256": "a" * 64, "first_observed_at": OBSERVED},
        {"sha256": "b" * 64, "first_observed_at": OBSERVED},
    )


class FinancialDataTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(SEC, "SEC workflow must be implemented before acceptance")

    def test_new_snapshot_cannot_leak_old_facts_into_historical_research(self):
        rows = normalize()
        self.assertEqual(SEC.select_facts(rows, "2026-09-18T23:59:59Z")[0], [])
        selected, counts = SEC.select_facts(rows, OBSERVED)
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["available_at"], OBSERVED)
        self.assertEqual(selected[0]["value_text"], "90")

    def test_amendment_is_separate_evidence_and_only_wins_after_available(self):
        rows = normalize()
        self.assertEqual(len(rows), 2)
        self.assertNotEqual(rows[0]["row_id"], rows[1]["row_id"])
        self.assertTrue(rows[1]["is_amendment"])
        rows[0]["available_at"] = "2025-02-01T21:00:00Z"
        rows[1]["available_at"] = "2025-03-01T21:00:00Z"
        earlier, _ = SEC.select_facts(rows, "2025-02-10T00:00:00Z")
        later, _ = SEC.select_facts(rows, "2025-03-10T00:00:00Z")
        self.assertEqual(earlier[0]["accession"], ACCN)
        self.assertEqual(earlier[0]["value_text"], "100")
        self.assertEqual(later[0]["accession"], ACCN2)
        self.assertEqual(later[0]["value_text"], "90")

    def test_unknown_or_conflicting_acceptance_and_mismatch_fail_closed(self):
        for change in (None, "2025-02-01", "bad"):
            with self.subTest(acceptance=change):
                metadata = submissions()
                metadata["filings"]["recent"]["acceptanceDateTime"][0] = change
                rows = normalize(metadata=metadata)
                self.assertIsNone(rows[0]["available_at"])
                self.assertEqual(rows[0]["status"], "excluded")
        metadata = submissions()
        recent = metadata["filings"]["recent"]
        for key, values in recent.items():
            values.append(values[0])
        recent["acceptanceDateTime"][-1] = "2025-02-02T21:00:00Z"
        self.assertEqual(normalize(metadata=metadata)[0]["exclusion_reason"], "ambiguous_submission")
        metadata = submissions()
        metadata["filings"]["recent"]["form"][0] = "10-K"
        self.assertEqual(normalize(metadata=metadata)[0]["exclusion_reason"], "submission_mismatch")

    def test_currency_mismatch_never_converts_or_chooses_other_unit(self):
        data = facts()
        entries = data["facts"]["us-gaap"]["Assets"]["units"].pop("USD")
        data["facts"]["us-gaap"]["Assets"]["units"]["CAD"] = entries
        selected, counts = SEC.select_facts(normalize(data=data), OBSERVED)
        self.assertEqual(selected, [])
        self.assertEqual(counts["unit_mismatch"], 2)

    def test_same_accession_conflicting_values_do_not_arbitrarily_win(self):
        data = facts()
        entry = copy.deepcopy(data["facts"]["us-gaap"]["Assets"]["units"]["USD"][-1])
        entry["val"] = 91
        data["facts"]["us-gaap"]["Assets"]["units"]["USD"].append(entry)
        selected, counts = SEC.select_facts(normalize(data=data), OBSERVED)
        self.assertEqual(selected, [])
        self.assertEqual(counts["ambiguous_latest_report"], 1)

    def test_partial_download_and_response_limit_never_become_snapshots(self):
        class Response(io.BytesIO):
            status = 200
            headers = {"Content-Type": "application/json", "Content-Length": "40"}
            def geturl(self):
                return "https://data.sec.gov/submissions/CIK0000320193.json"
        for payload, max_bytes in [(b'{"cik": 320193}', 100), (b"x" * 41, 20)]:
            with self.subTest(size=len(payload)):
                with self.assertRaises(SEC.AcquisitionError):
                    SEC.fetch_json(
                        "https://data.sec.gov/submissions/CIK0000320193.json",
                        "test-suite/1.0 (https://example.org)", max_bytes=max_bytes,
                        opener=lambda request, timeout: Response(payload))

    def test_interrupted_http_body_is_a_recordable_bounded_failure(self):
        def interrupted(request, timeout):
            raise http.client.IncompleteRead(b"incomplete", 30)
        with self.assertRaises(SEC.AcquisitionError):
            SEC.fetch_json("https://data.sec.gov/submissions/CIK0000320193.json",
                           "test-suite/1.0 (https://example.org)", opener=interrupted)

    def test_snapshots_preserve_first_observation_and_refuse_corruption(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = json.dumps(facts()).encode()
            first = SEC.store_snapshot(root, "companyfacts", "0000320193", payload,
                                       "https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json", OBSERVED)
            second = SEC.store_snapshot(root, "companyfacts", "0000320193", payload,
                                        first["url"], "2026-09-20T12:00:00Z")
            self.assertEqual(second["first_observed_at"], OBSERVED)
            self.assertEqual(first["sha256"], second["sha256"])
            self.assertEqual(len(list(root.glob("raw/companyfacts/0000320193/*/source.json"))), 1)
            source = root / first["relative_path"]
            self.assertEqual(source.stat().st_mode & 0o777, 0o600)
            source.write_bytes(b"corruption")
            with self.assertRaises(SEC.AcquisitionError):
                SEC.store_snapshot(root, "companyfacts", "0000320193", payload, first["url"], OBSERVED)

    def test_atomic_output_never_overwrites_and_leaves_no_pending_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "packet.json"
            SEC.atomic_write(path, b"original")
            with self.assertRaises(FileExistsError):
                SEC.atomic_write(path, b"replacement")
            self.assertEqual(path.read_bytes(), b"original")
            self.assertEqual([p.name for p in path.parent.iterdir()], ["packet.json"])

    def test_packet_is_deterministic_cited_and_keeps_numbers_out_of_prose(self):
        rows = normalize()
        first = SEC.make_packet(rows, OBSERVED)
        second = SEC.make_packet(list(reversed(rows)), OBSERVED)
        self.assertEqual(first, second)
        self.assertEqual(first["numerical_facts"][0]["value"], "90")
        self.assertEqual(first["numerical_facts"][0]["citation_id"], "F1")
        self.assertEqual(first["numerical_facts"][0]["source_id"], "S1")
        self.assertIn("https://www.sec.gov/Archives/edgar/data/320193/", first["sources"][0]["filing_url"])
        self.assertEqual(first["sources"][0]["companyfacts_sha256"], "a" * 64)
        self.assertEqual(first["sources"][0]["submissions_sha256"], "b" * 64)
        self.assertIn("constraints", first)

    def test_ready_requires_all_requested_symbol_concept_pairs_and_unique_fact_ids(self):
        rows = normalize()
        second_symbol = copy.deepcopy(rows)
        for row in second_symbol:
            row["symbol"] = "MSFT"
        result = SEC.make_packet(rows + second_symbol, OBSERVED)
        self.assertEqual(result["status"], "incomplete")
        self.assertEqual([r["citation_id"] for r in result["numerical_facts"]], ["F1", "F2"])

    def test_precision_overflow_and_invalid_period_are_excluded(self):
        data = facts()
        entries = data["facts"]["us-gaap"]["Assets"]["units"]["USD"]
        entries[0]["val"] = 10 ** 40
        entries[1]["end"] = "not-a-date"
        rows = normalize(data=data)
        self.assertEqual([r["status"] for r in rows], ["excluded", "excluded"])
        self.assertEqual(SEC.select_facts(rows, OBSERVED)[0], [])

    def test_partial_acquisition_retains_source_and_failure_but_no_dataset(self):
        def responses(url, user_agent):
            if "/submissions/" in url:
                return json.dumps(submissions()).encode()
            raise SEC.AcquisitionError("http_403")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(SEC, "fetch_json", side_effect=responses):
                receipt = SEC.acquire(root, "partial", "test-suite/1.0 (https://example.org)")
            self.assertEqual(receipt["status"], "failed")
            self.assertEqual(receipt["error_code"], "http_403")
            self.assertEqual([r["status"] for r in receipt["requests"]], ["completed", "failed"])
            self.assertFalse((root / "acquisitions/partial/facts.parquet").exists())
            self.assertEqual(len(list(root.glob("raw/submissions/*/*/source.json"))), 1)
            saved = json.loads((root / "acquisitions/partial/receipt.json").read_bytes())
            self.assertEqual(saved["status"], "failed")
            with self.assertRaises(FileExistsError):
                SEC.acquire(root, "partial", "test-suite/1.0 (https://example.org)")

    @unittest.skipUnless(importlib.util.find_spec("duckdb"), "native DuckDB integration needs the pinned research environment")
    def test_native_parquet_roundtrip_preserves_exact_decimals_and_cutoffs(self):
        data = facts()
        data["facts"]["us-gaap"]["Assets"]["units"]["USD"][1]["val"] = 9007199254740993
        rows = normalize(data=data)
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "facts.parquet"
            result = SEC.write_parquet(rows, target)
            self.assertEqual(result["rows"], 2)
            restored = SEC.read_parquet(target)
            packet = SEC.make_packet(restored, OBSERVED)
            self.assertEqual(packet["numerical_facts"][0]["value"], "9007199254740993")
            self.assertEqual(SEC.select_facts(restored, "2026-09-18T00:00:00Z")[0], [])
            with self.assertRaises(FileExistsError):
                SEC.write_parquet(rows, target)
            self.assertEqual(SEC.read_parquet(target), restored)

    @unittest.skipUnless(importlib.util.find_spec("duckdb"), "native DuckDB integration needs the pinned research environment")
    def test_full_precision_decimal_and_cli_ready_packet_roundtrip(self):
        from decimal import Decimal
        all_rows = []
        for symbol in ("AAPL", "MSFT"):
            data = facts()
            concept = data["facts"]["us-gaap"]["Assets"]
            concept["units"]["USD"][1]["val"] = Decimal("12345678901234567890123456.123456789012")
            for name in ("Liabilities", "StockholdersEquity", "NetIncomeLoss"):
                data["facts"]["us-gaap"][name] = copy.deepcopy(concept)
            rows = normalize(data=data)
            for row in rows:
                row["symbol"] = symbol
            all_rows.extend(rows)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = SEC.write_parquet(all_rows, root / "facts.parquet")
            restored = SEC.read_parquet(root / "facts.parquet")
            self.assertIn("12345678901234567890123456.123456789012", [r["value_decimal"] for r in restored])
            (root / "receipt.json").write_bytes(SEC.json_bytes({"status": "completed", "artifact": result}))
            command = [sys.executable, str(SOURCE), "packet", "--run", str(root), "--as-of", OBSERVED,
                       "--out", str(root / "packet.json"), "--text-out", str(root / "packet.md")]
            process = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
            packet = json.loads((root / "packet.json").read_bytes())
            self.assertEqual(packet["status"], "ready")
            self.assertEqual(len(packet["numerical_facts"]), 8)
            self.assertLessEqual((root / "packet.md").stat().st_size, 8192)
            self.assertEqual(len({f["citation_id"] for f in packet["numerical_facts"]}), 8)
            self.assertTrue(all(f["value"] == "12345678901234567890123456.123456789012" for f in packet["numerical_facts"]))
            # A tampered numerical artifact must not produce another packet.
            with (root / "facts.parquet").open("ab") as stream:
                stream.write(b"tampered")
            process = subprocess.run(command[:-4] + ["--out", str(root / "invalid.json")], capture_output=True, text=True)
            self.assertNotEqual(process.returncode, 0)
            self.assertFalse((root / "invalid.json").exists())


if __name__ == "__main__":
    unittest.main()
