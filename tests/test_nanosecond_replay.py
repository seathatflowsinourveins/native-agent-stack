import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "blueprints/us-equities/nanosecond-replay"
SPEC = importlib.util.spec_from_file_location("nanosecond_replay", HERE / "replay.py")
NS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(NS)


@unittest.skipUnless(importlib.util.find_spec("pandas") and importlib.util.find_spec("duckdb"),
                     "native pandas and DuckDB are required")
class NanosecondReplayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = json.loads((HERE / "fixture.json").read_text())
        self.source = self.root / "source.json"
        self.source.write_text(json.dumps(self.data))
        self.snapshot = self.root / "snapshot"
        self.manifest = NS.materialize(self.source, self.snapshot)

    def select(self, cutoff="2025-02-01T21:00:00.000000100Z"):
        return NS.select(self.snapshot, self.manifest["snapshot_sha256"], cutoff,
                         "fixture-universe", "fixture-feed")

    def test_same_microsecond_revision_and_effective_universe(self):
        early = self.select()
        self.assertEqual([r["row_id"] for r in early["records"]], ["original"])
        self.assertEqual(early["records"][0]["available_ns"], str(NS.utc_ns("2025-02-01T21:00:00.000000100Z")))
        later = self.select("2025-02-01T21:00:00.000000200Z")
        self.assertEqual([r["row_id"] for r in later["records"]], ["correction", "future-member"])
        self.assertEqual(self.select(), early)

    def test_sequence_resolves_declared_same_clock_revision(self):
        result = self.select("2025-02-01T21:00:00.000000201Z")
        self.assertEqual([r["row_id"] for r in result["records"]], ["sequence-correction", "future-member"])
        self.assertEqual(result["records"][0]["source_sequence"], "3")

    def test_offset_equivalence_and_cutoff_ties(self):
        self.assertEqual(NS.utc_ns("2025-02-01T16:00:00.000000100-05:00"),
                         NS.utc_ns("2025-02-01T21:00:00.000000100Z"))
        self.assertEqual(self.select("2025-02-01T21:00:00.000000099Z")["records"], [])
        self.assertEqual(len(self.select()["records"]), 1)

    def test_nanosecond_signed_bounds_are_exact(self):
        self.assertEqual(NS.utc_ns("1677-09-21T00:12:43.145224193Z"), -(2**63) + 1)
        self.assertEqual(NS.utc_ns("2262-04-11T23:47:16.854775807Z"), 2**63 - 1)

    def test_precision_timezone_invalid_calendar_and_overflow_rejected(self):
        for value in ["2025-02-01T21:00:00.0000000001Z", "2025-02-01T21:00:00",
                      "2025-02-01T21:00:00+00:99", "2025-02-30T21:00:00Z",
                      "1677-09-21T00:12:43.145224192Z", "2262-04-11T23:47:16.854775808Z",
                      "NaT", None, 10]:
            with self.subTest(value=value), self.assertRaises(NS.PIT.ContractError):
                NS.utc_ns(value)

    def test_each_source_timestamp_and_query_cutoff_are_validated(self):
        for collection, fields in [("observations", ("event_at", "available_at")),
                                   ("universe", ("effective_at", "available_at"))]:
            for field in fields:
                data = copy.deepcopy(self.data)
                data[collection][0][field] = "2025-02-01T21:00:00.0000000001Z"
                with self.subTest(collection=collection, field=field), self.assertRaises(NS.PIT.ContractError):
                    NS.validate(data)
        with self.assertRaises(NS.PIT.ContractError):
            self.select("2025-02-01T21:00:00.0000000001Z")

    def test_ambiguous_revision_or_negative_sequence_rejected(self):
        for mutate in (lambda d: d["observations"].append(dict(d["observations"][0], row_id="duplicate")),
                       lambda d: d["observations"][0].update(source_sequence=-1)):
            data = copy.deepcopy(self.data)
            mutate(data)
            with self.assertRaises(NS.PIT.ContractError):
                NS.validate(data)

    def test_source_scope_missing_availability_and_backdating_rejected(self):
        for mutate in (lambda d: d.update(synthetic=False),
                       lambda d: d["observations"][0].pop("available_at"),
                       lambda d: d["observations"][0].update(event_at="2025-02-01T21:00:00.000000101Z")):
            data = copy.deepcopy(self.data)
            mutate(data)
            with self.assertRaises(NS.PIT.ContractError):
                NS.validate(data)

    def test_manifest_or_parquet_mutation_rejected(self):
        with self.assertRaises(NS.PIT.ContractError):
            NS.select(self.snapshot, "0" * 64, "2025-02-01T21:00:00Z", "fixture-universe", "fixture-feed")
        parquet = self.snapshot / "observations.parquet"
        parquet.chmod(0o600)
        parquet.write_bytes(parquet.read_bytes() + b"corruption")
        with self.assertRaises(NS.PIT.ContractError):
            self.select()

    def test_snapshot_is_not_overwritten(self):
        with self.assertRaises(FileExistsError):
            NS.materialize(self.source, self.snapshot)

    def test_late_universe_removal_preserves_previous_decision(self):
        data = copy.deepcopy(self.data)
        data["universe"].append(dict(data["universe"][1], row_id="late-removal", is_member=False,
                                     available_at="2025-02-01T21:00:00.000000250Z", source_sequence=2))
        self.source.write_text(json.dumps(data))
        self.snapshot = self.root / "late-universe"
        self.manifest = NS.materialize(self.source, self.snapshot)
        self.assertEqual(len(self.select("2025-02-01T21:00:00.000000201Z")["records"]), 2)
        self.assertEqual(len(self.select("2025-02-01T21:00:00.000000250Z")["records"]), 1)

    def test_integer_parquet_storage_and_json_safe_representation(self):
        import duckdb
        with duckdb.connect() as connection:
            relation = connection.read_parquet(str(self.snapshot / "observations.parquet"))
            types = dict(zip(relation.columns, map(str, relation.types)))
            self.assertEqual(types["available_ns"], "BIGINT")
            self.assertEqual(types["event_ns"], "BIGINT")
        result = self.select()
        self.assertIsInstance(result["cutoff_ns"], str)
        self.assertEqual(int(result["cutoff_ns"]), NS.utc_ns(result["cutoff_text"]))
        self.assertEqual(NS.select(self.snapshot, self.manifest["snapshot_sha256"], result["cutoff_text"],
                                   "fixture-universe", "different-feed")["records"], [])


if __name__ == "__main__":
    unittest.main()
