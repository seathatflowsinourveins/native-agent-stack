"""Offline integrity, cohort identity and observation-time dataset contracts."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1] / "blueprints/us-equities/catalyst-dataset/dataset.py"
OBSERVED = "2026-09-19T23:48:29.649862Z"
ACC = "0000000001-20-000001"
HASH = lambda raw: hashlib.sha256(raw).hexdigest()


def load_module():
    spec = importlib.util.spec_from_file_location("catalyst_dataset", MODULE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_run(root, missing_acceptance=False):
    run = root / "run"
    run.mkdir()
    index = ("CIK|Company Name|Form Type|Date Filed|File Name\n---\n"
             f"1|One|8-K|20200302|edgar/data/1/{ACC}.txt\n"
             f"2|Co-filer|8-K|20200302|edgar/data/2/{ACC}.txt\n"
             "3|Unknown amendment|8-K/A|20200302|edgar/data/3/0000000003-20-000003.txt\n").encode()
    header = (f"<SEC-HEADER>\n<ACCESSION-NUMBER>{ACC}\n<TYPE>8-K\n"
              "<FILING-DATE>20200302\n<ACCEPTANCE-DATETIME>20200302100000\n"
              "<ITEMS>5.02\n<ITEMS>9.01\n</SEC-HEADER>\n").encode()
    if missing_acceptance:
        header = header.replace(b"<ACCEPTANCE-DATETIME>20200302100000\n", b"")
    files = []
    for name, raw, observed in [("index.idx", index, OBSERVED),
                                (f"1-{ACC}.hdr.sgml", header, "2026-09-19T23:48:28Z"),
                                (f"2-{ACC}.hdr.sgml", header, OBSERVED)]:
        (run / name).write_bytes(raw)
        files.append({"path": name, "sha256": HASH(raw), "bytes": len(raw), "first_observed_at": observed})
    receipt = {"schema_version": 1, "status": "complete", "day": "2020-03-02",
               "index_url": "https://www.sec.gov/Archives/edgar/daily-index/2020/QTR1/master.20200302.idx",
               "member_limit": 2, "cohort_count": 3, "files": files,
               "selected": [{"cik": cik, "accession": ACC, "event": {"status": "quarantined"}} for cik in [1, 2]]}
    raw = (json.dumps(receipt, sort_keys=True) + "\n").encode()
    (run / "receipt.json").write_bytes(raw)
    return run, HASH(raw)


def native_view(raw):
    return {"form": "8-K", "accession": ACC, "filed_date": "2020-03-02",
            "acceptance_raw": "20200302100000", "filer_ciks": [1, 2],
            "items": [{"code": "5.02", "title": "Officers"}, {"code": "9.01", "title": "Exhibits"}],
            "items_status": "declared"}


class CatalystDatasetTests(unittest.TestCase):
    def setUp(self):
        self.m = load_module()
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.run, self.receipt_hash = make_run(self.root)
        self.native = patch.object(self.m, "native_view", side_effect=native_view)
        self.provenance = patch.object(self.m, "native_parser_identity", return_value={"version": "5.58.0", "source_files": []})
        self.native.start()
        self.provenance.start()
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(self.native.stop)
        self.addCleanup(self.provenance.stop)

    def extract(self, name="extract"):
        path = self.root / name
        self.m.extract(self.run, path, self.receipt_hash)
        return path, HASH((path / "manifest.json").read_bytes())

    def test_cofilers_and_unfetched_unknowns_survive_stale_receipt_events(self):
        path, _ = self.extract()
        data = json.loads((path / "extraction.json").read_bytes())
        self.assertEqual(data["summary"], {"members": 3, "unique_accessions": 2, "cofiling_groups": 1,
                                          "headers": 2, "qualified_headers": 2, "not_fetched": 1, "items": 4})
        self.assertEqual([x["cik"] for x in data["headers"]], [1, 2])
        self.assertEqual({x["first_observed_at"] for x in data["headers"]}, {OBSERVED})
        self.assertEqual({x["available_at"] for x in data["headers"]}, {OBSERVED})
        unknown = data["members"][2]
        self.assertEqual(unknown["fetch_status"], "not_fetched")
        self.assertTrue(unknown["is_amendment"])
        for field in ["header_sha256", "ticker", "amends_accession"]:
            self.assertIsNone(unknown[field])
        self.assertEqual(unknown["index_observed_at"], OBSERVED)
        self.assertEqual(len({(x["cik"], x["accession"], x["source_sha256"], x["ordinal"]) for x in data["items"]}), 4)

    def test_receipt_and_raw_tampering_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "receipt_hash_mismatch"):
            self.m.extract(self.run, self.root / "bad", "0" * 64)
        (self.run / "index.idx").write_bytes((self.run / "index.idx").read_bytes() + b"\n")
        with self.assertRaisesRegex(ValueError, "artifact_hash_mismatch"):
            self.extract()

    def test_receipt_and_ancestor_symlinks_are_refused(self):
        alias = self.root / "alias"
        alias.symlink_to(self.run, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.m.extract(alias, self.root / "bad", self.receipt_hash)
        raw = (self.run / "receipt.json").read_bytes()
        (self.run / "receipt.json").unlink()
        (self.root / "receipt-copy.json").write_bytes(raw)
        (self.run / "receipt.json").symlink_to(self.root / "receipt-copy.json")
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.extract()

    def test_existing_or_symlink_output_is_refused_without_overwrite(self):
        path, _ = self.extract()
        before = (path / "manifest.json").read_bytes()
        with self.assertRaises(FileExistsError):
            self.extract()
        self.assertEqual((path / "manifest.json").read_bytes(), before)
        alias = self.root / "alias"
        alias.symlink_to(path, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.m.extract(self.run, alias / "child", self.receipt_hash)

    def test_native_identity_or_acceptance_disagreement_is_not_silently_preferred(self):
        for key, value in [("form", "8-K/A"), ("accession", "0000000002-20-000002"),
                           ("filed_date", "2020-03-03"), ("acceptance_raw", "20200302110000"),
                           ("filer_ciks", [9])]:
            with self.subTest(key=key), patch.object(self.m, "native_view", return_value={**native_view(b""), key: value}):
                with self.assertRaisesRegex(ValueError, "native_header_disagreement"):
                    self.extract(key)

    def test_missing_acceptance_retains_quarantine_without_items_or_availability(self):
        other = self.root / "missing"
        other.mkdir()
        self.run, self.receipt_hash = make_run(other, missing_acceptance=True)
        path, _ = self.extract()
        data = json.loads((path / "extraction.json").read_bytes())
        self.assertEqual(data["summary"]["qualified_headers"], 0)
        self.assertEqual(data["items"], [])
        for row in data["headers"]:
            self.assertEqual(row["status"], "quarantined")
            self.assertIsNone(row["available_at"])
            self.assertIsNone(row["item_count"])

    def test_duplicate_member_and_item_identity_rejected(self):
        path, _ = self.extract()
        data = json.loads((path / "extraction.json").read_bytes())
        for name in ["members", "items"]:
            with self.subTest(name=name):
                value = json.loads(json.dumps(data))
                value[name].append(value[name][0])
                with self.assertRaisesRegex(ValueError, "duplicate"):
                    self.m.validate_data(value)

    def test_null_or_backdated_availability_cannot_qualify(self):
        path, _ = self.extract()
        data = json.loads((path / "extraction.json").read_bytes())
        for value in [None, "2020-03-02T15:00:00Z"]:
            changed = json.loads(json.dumps(data))
            changed["headers"][0]["available_at"] = value
            with self.assertRaisesRegex(ValueError, "availability"):
                self.m.validate_data(changed)

    def test_missing_items_remain_unknown_instead_of_zero_catalysts(self):
        view = {**native_view(b""), "items": [], "items_status": "not_declared"}
        with patch.object(self.m, "native_view", return_value=view):
            path, _ = self.extract()
        data = json.loads((path / "extraction.json").read_bytes())
        self.assertEqual(data["items"], [])
        self.assertTrue(all(h["item_count"] is None and h["items_status"] == "not_declared" for h in data["headers"]))

    def test_stage_manifest_anchor_payload_tampering_and_extra_file_refused(self):
        path, anchor = self.extract()
        with self.assertRaisesRegex(ValueError, "manifest_hash_mismatch"):
            self.m.load_extraction(path, "0" * 64)
        (path / "unlisted.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "unexpected_payload_set"):
            self.m.load_extraction(path, anchor)
        (path / "unlisted.json").unlink()
        (path / "extraction.json").write_bytes((path / "extraction.json").read_bytes() + b"\n")
        with self.assertRaisesRegex(ValueError, "artifact_hash_mismatch"):
            self.m.load_extraction(path, anchor)


try:
    import duckdb
except ImportError:
    duckdb = None


@unittest.skipUnless(duckdb is not None, "DuckDB adopted SDK environment is required")
class CatalystDatasetDuckDBTests(unittest.TestCase):
    setUp = CatalystDatasetTests.setUp
    extract = CatalystDatasetTests.extract

    def test_parquet_preserves_nulls_cofilers_utc_and_exact_cutoff(self):
        path, anchor = self.extract()
        out = self.root / "tables"
        self.m.materialize(path, out, anchor)
        con = duckdb.connect()
        con.execute("SET TimeZone='UTC'")
        rows = con.execute("SELECT cik, accepted_at, available_at, item_count FROM read_parquet(?) ORDER BY cik", [str(out / "headers.parquet")]).fetchall()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0][2].microsecond, 649862)
        self.assertEqual(rows[0][2].utcoffset().total_seconds(), 0)
        unknown = con.execute("SELECT m.cik,h.accepted_at,h.available_at,h.item_count,m.ticker,m.amends_accession FROM read_parquet(?) m LEFT JOIN read_parquet(?) h USING(cik,accession) WHERE m.cik=3", [str(out / "members.parquet"), str(out / "headers.parquet")]).fetchone()
        self.assertEqual(unknown, (3, None, None, None, None, None))
        for cutoff, expected in [("2020-03-03T00:00:00Z", 0), ("2026-09-19T23:48:28.649862Z", 0), (OBSERVED, 2)]:
            self.assertEqual(len(self.m.query(out, cutoff, HASH((out / "manifest.json").read_bytes()))), expected)
        con.close()

    def test_deterministic_parquet_and_exclusive_materialization(self):
        path, anchor = self.extract()
        a, b = self.root / "a", self.root / "b"
        self.m.materialize(path, a, anchor)
        self.m.materialize(path, b, anchor)
        for name in ["members", "headers", "items"]:
            self.assertEqual(HASH((a / f"{name}.parquet").read_bytes()), HASH((b / f"{name}.parquet").read_bytes()))
        with self.assertRaises(FileExistsError):
            self.m.materialize(path, a, anchor)

    def test_empty_item_table_is_typed_and_quarantine_never_eligible(self):
        other = self.root / "missing"
        other.mkdir()
        self.run, self.receipt_hash = make_run(other, missing_acceptance=True)
        path, anchor = self.extract()
        out = self.root / "tables"
        self.m.materialize(path, out, anchor)
        self.assertEqual(self.m.query(out, "2030-01-01T00:00:00Z", HASH((out / "manifest.json").read_bytes())), [])
        con = duckdb.connect()
        self.assertEqual(con.execute("SELECT count(*) FROM read_parquet(?)", [str(out / "items.parquet")]).fetchone()[0], 0)
        con.close()

    def test_query_refuses_missing_anchor_tampered_or_symlink_parquet(self):
        path, anchor = self.extract()
        out = self.root / "tables"
        self.m.materialize(path, out, anchor)
        final_anchor = HASH((out / "manifest.json").read_bytes())
        with self.assertRaisesRegex(ValueError, "manifest_hash_mismatch"):
            self.m.query(out, OBSERVED)
        parquet = out / "headers.parquet"
        raw = parquet.read_bytes()
        parquet.write_bytes(raw + b"tamper")
        with self.assertRaisesRegex(ValueError, "artifact_hash_mismatch"):
            self.m.query(out, OBSERVED, final_anchor)
        parquet.unlink()
        copy = self.root / "copy.parquet"
        copy.write_bytes(raw)
        parquet.symlink_to(copy)
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.m.query(out, OBSERVED, final_anchor)


if __name__ == "__main__":
    unittest.main()
