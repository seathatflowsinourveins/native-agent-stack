"""Causal availability and immutable acquisition contracts, using synthetic SEC text."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1] / "blueprints/us-equities/catalyst-provenance/catalyst.py"


def load_module():
    if not MODULE.exists():
        return None
    spec = importlib.util.spec_from_file_location("catalyst", MODULE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


INDEX = b"Description: Master Index of EDGAR Dissemination Feed\nCIK|Company Name|Form Type|Date Filed|Filename\n----\n2|Example B|8-K/A|2020-03-02|edgar/data/2/0000000002-20-000002.txt\n1|Example A|8-K|2020-03-02|edgar/data/1/0000000001-20-000001.txt\n3|Example C|10-K|2020-03-02|edgar/data/3/0000000003-20-000003.txt\n"
# Header and compact date syntax observed in the retained SEC 2020-03-02 index.
NATIVE_INDEX = b"Description: Master Index of EDGAR Dissemination Feed\nCIK|Company Name|Form Type|Date Filed|File Name\n----\n2|Example B|8-K/A|20200302|edgar/data/2/0000000002-20-000002.txt\n1|Example A|8-K|20200302|edgar/data/1/0000000001-20-000001.txt\n3|Example C|CORRESP|20190801|edgar/data/3/0000000003-19-000003.txt\n"
HEADER = b"<SEC-HEADER>\n<ACCEPTANCE-DATETIME>20200302100000\nACCESSION NUMBER: 0000000001-20-000001\nCONFORMED SUBMISSION TYPE: 8-K\nFILED AS OF DATE: 20200302\n</SEC-HEADER>\n"


class CatalystProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.m = load_module()
        self.assertIsNotNone(self.m, "catalyst provenance implementation is required")

    def test_full_cohort_is_sorted_independent_of_acquisition_cap(self):
        rows = self.m.parse_index(INDEX, "2020-03-02")
        self.assertEqual([x["cik"] for x in rows], [1, 2])
        self.assertEqual([x["form"] for x in rows], ["8-K", "8-K/A"])

    def test_native_index_header_and_compact_dates_normalize_catalyst_rows(self):
        rows = self.m.parse_index(NATIVE_INDEX, "2020-03-02")
        self.assertEqual([x["cik"] for x in rows], [1, 2])
        self.assertEqual([x["filed_date"] for x in rows], ["2020-03-02", "2020-03-02"])
        self.assertEqual([x["form"] for x in rows], ["8-K", "8-K/A"])

    def test_native_index_rejects_malformed_dates_and_off_day_catalysts(self):
        for value in [b"2020032", b"202003020", b"20201302", b"20200230", b"2020-3-02", b"2020/03/02", b"20200303"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.m.parse_index(NATIVE_INDEX.replace(b"20200302", value), "2020-03-02")

    def test_native_shared_accession_keeps_distinct_cik_members(self):
        raw = NATIVE_INDEX + b"4|Example Co-filer|8-K|20200302|edgar/data/4/0000000001-20-000001.txt\n"
        rows = self.m.parse_index(raw, "2020-03-02")
        self.assertEqual([x["cik"] for x in rows], [1, 2, 4])
        self.assertEqual(rows[0]["accession"], rows[2]["accession"])
        with self.assertRaises(ValueError):
            self.m.parse_index(raw + raw.splitlines()[-1] + b"\n", "2020-03-02")

    def test_native_non_target_rows_still_require_valid_dates_and_paths(self):
        for raw in [NATIVE_INDEX.replace(b"20190801", b"20190230"), NATIVE_INDEX.replace(b"edgar/data/3/", b"../data/3/")]:
            with self.subTest(raw=raw[-60:]), self.assertRaises(ValueError):
                self.m.parse_index(raw, "2020-03-02")

    def test_index_rejects_wrong_day_traversal_and_duplicate_accessions(self):
        for raw in [INDEX.replace(b"2020-03-02", b"2020-03-03"), INDEX.replace(b"edgar/data/1/", b"../data/1/"), INDEX + INDEX.splitlines()[4] + b"\n"]:
            with self.subTest(raw=raw[-60:]), self.assertRaises(ValueError):
                self.m.parse_index(raw, "2020-03-02")

    def test_acceptance_is_separate_from_first_observation(self):
        member = self.m.parse_index(INDEX, "2020-03-02")[0]
        event = self.m.parse_header(HEADER, member, "2026-09-19T12:00:00Z")
        self.assertEqual(event["accepted_at"], "2020-03-02T15:00:00Z")
        self.assertEqual(event["available_at"], "2026-09-19T12:00:00Z")
        self.assertEqual(event["status"], "qualified")

    def test_missing_or_mismatched_header_is_quarantined(self):
        member = self.m.parse_index(INDEX, "2020-03-02")[0]
        for raw in [HEADER.replace(b"20200302100000", b"bad"), HEADER.replace(b"0000000001-20-000001", b"0000000001-20-000004"), HEADER.replace(b"TYPE: 8-K", b"TYPE: 8-K/A"), HEADER.replace(b"20200302\n", b"20200303\n")]:
            with self.subTest(raw=raw):
                self.assertEqual(self.m.parse_header(raw, member, "2026-09-19T12:00:00Z")["status"], "quarantined")

    def test_ambiguous_and_nonexistent_eastern_times_are_rejected(self):
        for value in ["20201101013000", "20200308023000"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.m.acceptance_time(value)

    def test_future_acceptance_is_not_available_early(self):
        member = self.m.parse_index(INDEX, "2020-03-02")[0]
        event = self.m.parse_header(HEADER, member, "2020-03-02T14:00:00Z")
        self.assertEqual(event["available_at"], "2020-03-02T15:00:00Z")

    def test_real_upstream_fixture_stays_quarantined_without_acceptance(self):
        base = MODULE.parent
        source = json.loads((base / "upstream-8k-source.json").read_text())
        raw = (base / "upstream-8k.html").read_bytes()[:-1]
        import hashlib
        self.assertEqual(hashlib.sha256(raw).hexdigest(), source["sha256"])
        event = self.m.parse_header(raw, {"accession": "0000887919-21-000012", "form": "8-K", "filed_date": None}, source["first_local_observed_at"])
        self.assertFalse(self.m.eligible_at(event, "2021-12-31T00:00:00Z"))
        self.assertFalse(self.m.eligible_at(event, "2030-12-31T00:00:00Z"))

    def test_qualified_gate_rejects_one_second_before_availability(self):
        event = {"status": "qualified", "available_at": "2026-09-19T12:00:00Z"}
        self.assertFalse(self.m.eligible_at(event, "2026-09-19T11:59:59Z"))
        self.assertTrue(self.m.eligible_at(event, "2026-09-19T12:00:00Z"))

    def acquire(self, root):
        with patch.object(self.m, "fetch", side_effect=[INDEX, HEADER]), patch.object(self.m, "now", return_value="2026-09-19T12:00:00Z"), patch.object(self.m.time, "sleep"):
            return self.m.acquire(root, "sample", "Example research admin@example.org", member_limit=1)

    def test_offline_packet_verifies_raw_dependencies_and_rejects_early_cutoff(self):
        with tempfile.TemporaryDirectory() as directory:
            self.acquire(Path(directory))
            run = Path(directory) / "sample"
            early = self.m.packet(run, "2020-03-03T00:00:00Z")
            self.assertEqual(early["eligible_count"], 0)
            self.assertEqual(early["exclusions"], {"before_first_availability": 1})
            current = self.m.packet(run, "2026-09-19T12:00:00Z")
            self.assertEqual(current["eligible_count"], 1)
            self.assertEqual(current["cohort_count"], 2)
            self.assertEqual(current["selected_count"], 1)
            original = (run / "index.idx").read_bytes()
            (run / "index.idx").write_bytes(original + b"changed")
            with self.assertRaises(ValueError):
                self.m.packet(run, "2026-09-19T12:00:00Z")

    def test_acquisition_never_overwrites_a_run(self):
        with tempfile.TemporaryDirectory() as directory:
            self.acquire(Path(directory))
            receipt = (Path(directory) / "sample/receipt.json").read_bytes()
            with self.assertRaises(FileExistsError):
                self.acquire(Path(directory))
            self.assertEqual((Path(directory) / "sample/receipt.json").read_bytes(), receipt)

    def test_refusal_stops_network_branch_and_is_not_a_completed_dataset(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(self.m, "fetch", side_effect=ValueError("http_403")):
                receipt = self.m.acquire(Path(directory), "refused", "Example research admin@example.org")
            self.assertEqual(receipt["status"], "failed")
            self.assertEqual(receipt["request_count"], 1)
            self.assertEqual(receipt["error_code"], "http_403")
            with self.assertRaises(ValueError):
                self.m.packet(Path(directory) / "refused", "2026-09-19T12:00:00Z")

    def test_member_failure_retains_selected_member_and_stops_later_requests(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(self.m, "fetch", side_effect=[INDEX, ValueError("http_403")]), patch.object(self.m.time, "sleep"):
                receipt = self.m.acquire(Path(directory), "partial", "Example research admin@example.org")
            self.assertEqual(receipt["status"], "failed")
            self.assertEqual(receipt["request_count"], 2)
            self.assertEqual(len(receipt["selected"]), 2)
            self.assertEqual(receipt["selected"][0]["acquisition_status"], "failed")
            self.assertEqual(receipt["selected"][1]["acquisition_status"], "not_requested")

    def test_member_blob_corruption_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            self.acquire(Path(directory))
            run = Path(directory) / "sample"
            (run / "1-0000000001-20-000001.hdr.sgml").write_bytes(b"changed")
            with self.assertRaises(ValueError):
                self.m.packet(run, "2026-09-19T12:00:00Z")

    def test_shared_accession_acquisition_preserves_both_cik_artifacts(self):
        raw = b"CIK|Company Name|Form Type|Date Filed|File Name\n1|Example A|8-K|20200302|edgar/data/1/0000000001-20-000001.txt\n4|Example Co-filer|8-K|20200302|edgar/data/4/0000000001-20-000001.txt\n"
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(self.m, "fetch", side_effect=[raw, HEADER, HEADER]), patch.object(self.m, "now", return_value="2026-09-19T12:00:00Z"), patch.object(self.m.time, "sleep"):
                receipt = self.m.acquire(Path(directory), "cofilers", "Example research admin@example.org")
            self.assertEqual(receipt["status"], "complete")
            self.assertEqual(len(receipt["files"]), 3)
            self.assertEqual(len({row["path"] for row in receipt["files"]}), 3)
            packet = self.m.packet(Path(directory) / "cofilers", "2026-09-19T12:00:00Z")
            self.assertEqual(packet["eligible_count"], 2)
            self.assertEqual([event["cik"] for event in packet["events"]], [1, 4])

    def test_packet_reads_legacy_accession_only_artifact_name(self):
        with tempfile.TemporaryDirectory() as directory:
            self.acquire(Path(directory))
            run = Path(directory) / "sample"
            receipt = json.loads((run / "receipt.json").read_text())
            entry = next(row for row in receipt["files"] if row["path"].endswith(".hdr.sgml"))
            legacy_name = "0000000001-20-000001.hdr.sgml"
            (run / entry["path"]).rename(run / legacy_name)
            entry["path"] = legacy_name
            (run / "receipt.json").write_text(json.dumps(receipt))
            self.assertEqual(self.m.packet(run, "2026-09-19T12:00:00Z")["eligible_count"], 1)


if __name__ == "__main__":
    unittest.main()
