"""Synthetic temporal contracts exercised through the real native DuckDB API."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "blueprints/us-equities/point-in-time"
SPEC = importlib.util.spec_from_file_location("temporal_snapshot", HERE / "temporal_snapshot.py")
PIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PIT)


@unittest.skipUnless(importlib.util.find_spec("duckdb"), "requires the pinned native research SDK environment")
class PointInTimeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "fixture.json"
        self.data = json.loads((HERE / "fixture.json").read_text())
        self.source.write_text(json.dumps(self.data))
        self.snapshot = self.root / "snapshot"
        self.receipt = PIT.write_snapshot(self.source, self.snapshot)

    def query(self, cutoff="2025-02-10T00:00:00Z", **kwargs):
        return PIT.select(self.snapshot, self.receipt["snapshot_sha256"], cutoff,
                          kwargs.get("universe", "fixture-selected"),
                          kwargs.get("feed", "fixture-feed-a"),
                          kwargs.get("adjustment", "raw"), "Assets", "USD")

    def values(self, cutoff="2025-02-10T00:00:00Z", **kwargs):
        return {row["symbol"]: row["value_text"] for row in self.query(cutoff, **kwargs)["records"]}

    def test_late_correction_cannot_enter_earlier_decision(self):
        self.assertEqual(self.values(), {"AAPL": "100", "MSFT": "200"})
        self.assertEqual(self.values("2025-03-10T00:00:00Z"), {"AAPL": "90"})
        self.assertEqual(self.values(), {"AAPL": "100", "MSFT": "200"})

    def test_announced_future_universe_change_waits_until_effective(self):
        self.assertNotIn("SPY", self.values("2025-03-10T00:00:00Z"))
        self.assertEqual(self.values("2025-04-10T00:00:00Z"), {"AAPL": "90", "SPY": "300"})

    def test_universe_feed_and_adjustment_are_explicit(self):
        self.assertEqual(self.values(universe="fixture-other"), {"ZZZ": "777"})
        self.assertEqual(self.values(feed="fixture-feed-b"), {"AAPL": "999"})
        self.assertEqual(self.values(adjustment="split"), {"AAPL": "50"})
        self.assertEqual(self.values(feed="unavailable-feed"), {})

    def test_source_publication_can_predate_later_ingestion_but_stays_unverified(self):
        row = next(row for row in self.query()["records"] if row["symbol"] == "MSFT")
        self.assertLess(row["available_at"], row["first_observed_at"])
        self.assertEqual(row["availability_basis"], "source_publication")
        self.assertFalse(self.query()["availability_evidence_authenticated"])
        self.assertFalse(self.query()["entitlement_verified"])

    def test_missing_availability_and_naive_timestamps_fail_closed(self):
        for change in (lambda row: row.pop("available_at"),
                       lambda row: row.update(available_at="2025-02-01"),
                       lambda row: row.update(available_at=None)):
            data = copy.deepcopy(self.data)
            change(data["observations"][0])
            with self.assertRaises(ValueError):
                PIT.validate_source(data)

    def test_capture_and_adjustment_evidence_cannot_be_backdated(self):
        for field in ("first_observed_at", "adjustment_available_at", "event_at"):
            data = copy.deepcopy(self.data)
            data["observations"][0][field] = "2026-01-01T00:00:00Z"
            with self.subTest(field=field), self.assertRaises(PIT.ContractError):
                PIT.validate_source(data)

    def test_sub_microsecond_source_and_cutoff_precision_is_rejected(self):
        for collection, schema in (("observations", PIT.OBSERVATIONS), ("universe", PIT.UNIVERSE)):
            for field, kind in schema.items():
                if kind != "TIMESTAMPTZ":
                    continue
                data = copy.deepcopy(self.data)
                data[collection][0][field] = "2025-02-01T21:00:00.0000001Z"
                with self.subTest(collection=collection, field=field), self.assertRaisesRegex(PIT.ContractError, "microsecond_precision"):
                    PIT.validate_source(data)
        with self.assertRaisesRegex(PIT.ContractError, "microsecond_precision"):
            self.query("2025-02-01T21:00:00.0000001Z")
        self.assertEqual(PIT.timestamp("2025-02-01T21:00:00.000001Z").microsecond, 1)
        for value in ("2025-02-01T21:00:00+00:99", "2025-02-01T21:00:00+24:00"):
            with self.subTest(value=value), self.assertRaises(PIT.ContractError):
                PIT.timestamp(value)

    def test_conflicting_revision_ties_are_rejected_even_with_different_ids(self):
        data = copy.deepcopy(self.data)
        row = copy.deepcopy(data["observations"][0])
        row.update(row_id="same-instant-alternative", value_text="101", available_at="2025-02-01T16:00:00-05:00")
        data["observations"].append(row)
        with self.assertRaisesRegex(PIT.ContractError, "ambiguous_temporal_revision"):
            PIT.validate_source(data)

    def test_unknown_provenance_and_unrepresentable_decimal_are_rejected(self):
        for field, value in (("availability_basis", "trust-me"), ("availability_evidence", ""),
                             ("value_text", "NaN"), ("value_text", "0.0000000000001"),
                             ("value_text", "0E+999999")):
            data = copy.deepcopy(self.data)
            data["observations"][0][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(PIT.ContractError):
                PIT.validate_source(data)

    def test_parquet_corruption_and_wrong_manifest_hash_are_rejected(self):
        with self.assertRaisesRegex(PIT.ContractError, "manifest_hash_mismatch"):
            PIT.verified_snapshot(self.snapshot, "0" * 64)
        parquet = self.snapshot / "observations.parquet"
        parquet.chmod(0o600)
        parquet.write_bytes(parquet.read_bytes() + b"corruption")
        with self.assertRaisesRegex(PIT.ContractError, "artifact_hash_mismatch"):
            self.query()

    def test_manifest_corruption_does_not_establish_a_new_trusted_root(self):
        manifest = self.snapshot / "snapshot.json"
        manifest.chmod(0o600)
        manifest.write_bytes(manifest.read_bytes() + b" ")
        with self.assertRaisesRegex(PIT.ContractError, "manifest_hash_mismatch"):
            self.query()

    def test_snapshot_creation_never_overwrites_existing_data(self):
        original = (self.snapshot / "snapshot.json").read_bytes()
        with self.assertRaises(FileExistsError):
            PIT.write_snapshot(self.source, self.snapshot)
        self.assertEqual((self.snapshot / "snapshot.json").read_bytes(), original)

    def test_late_universe_correction_does_not_remove_prior_membership(self):
        data = copy.deepcopy(self.data)
        data["universe"][2].update(available_at="2025-04-01T00:00:00Z", first_observed_at="2025-04-01T00:00:00Z")
        self.source.write_text(json.dumps(data))
        self.snapshot = self.root / "late-universe"
        self.receipt = PIT.write_snapshot(self.source, self.snapshot)
        self.assertEqual(self.values("2025-03-10T00:00:00Z"), {"AAPL": "90", "MSFT": "200"})


if __name__ == "__main__":
    unittest.main()
