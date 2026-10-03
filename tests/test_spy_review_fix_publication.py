"""Publication contracts for actual corrected-source SPY qualifications.

These tests read historical public evidence and hash its original source bytes. They run no engine,
broker, model or service. Missing new refusal publication is an incomplete
qualification, never a skip. Existing test_spy_parity.V2PublishedResultTests
and test_spy_over_limit retain the historical and runtime-source contracts.
"""
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
HARNESS = Path("blueprints/us-equities/engine-nautilus/spy-parity")
STRESS = "receipt-stress-review-fixes-20261003.json"
REFUSAL = "receipt-over-limit-review-fixes-20261003.json"
SUCCESSOR = "mapping-manifest-over-limit-review-fixes-20261003.json"
ARCHIVE = "historical-source-review-fixes-e73af98"
ARCHIVED_FILES = {"compare.py", "cost_models.py", "run.py"}
STRESS_COMMIT = "ae6778e850d5fd05e510d9cef65c0988ec849ef2"
REFUSAL_COMMIT = "e73af98d5eea2325113a64fc62d7981303757287"
STRESS_FILES = {
    "convert.py", "fixture_strategy.py", "distribution_module.py", "run.py", "compare.py",
    "cost_models.py", "mapping-manifest-stress-20261002.json", "PREREGISTRATION-stress-20261002.md",
    "requirements-stress-macos-arm64-py313.lock", "requirements-stress-linux-arm64-py313.lock",
}
REFUSAL_FILES = STRESS_FILES | {"over_limit.py", SUCCESSOR, "PREREGISTRATION-over-limit-20261002.md"}
DENIAL_REASON = "INITIAL_MARGIN_EXCEEDS_FREE_BALANCE: free=100000.00 USD, margin=195851.81 USD"


class CorrectedSpyPublicationTests(unittest.TestCase):
    def load(self, name):
        path = ROOT / HARNESS / name
        self.assertTrue(path.is_file(), "incomplete qualification: missing publication " + name)
        self.assertFalse(path.is_symlink(), "publication must be an actual file: " + name)
        return json.loads(path.read_text())

    def sha256(self, name):
        self.assertEqual(Path(name).name, name)
        # Only three mutable files changed for the unexecuted six-case successor.
        # Historical qualification remains bound to the exact reviewed originals;
        # it supplies no acceptance for the current successor source.
        path = ROOT / HARNESS / (ARCHIVE if name in ARCHIVED_FILES else "") / name
        self.assertTrue(path.is_file(), "missing bound source: " + name)
        self.assertFalse(path.is_symlink(), "bound source must be an actual file: " + name)
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def digest(self, value):
        self.assertIsInstance(value, str)
        self.assertRegex(value, r"\A[0-9a-f]{64}\Z")

    def zero(self, value):
        self.assertIs(type(value), int)
        self.assertEqual(value, 0)

    def timestamp(self, value):
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        self.assertIsNotNone(stamp.tzinfo)
        self.assertEqual(stamp.utcoffset(), timedelta(0))
        return stamp

    def reviewed_sources(self, receipt, names):
        observed = receipt["prospective_review"]["reviewed_source_sha256"]
        self.assertEqual(set(observed), names)
        self.assertEqual(observed, {name: self.sha256(name) for name in names})
        return observed

    def prospective_processes(self, receipt, receipt_key, verdict_key):
        review = receipt["prospective_review"]
        self.assertEqual(review["verdict"], "PASS")
        self.zero(review["unresolved_findings"])
        self.digest(review["original_record_sha256"])
        completed = self.timestamp(review["completed_utc"])
        processes = receipt["fresh_processes"]
        self.assertEqual([p["process"] for p in processes], [1, 2])
        starts = [self.timestamp(p["started_utc"]) for p in processes]
        self.assertLess(starts[0], starts[1])
        for process, started in zip(processes, starts):
            self.assertLess(completed, started)
            self.assertGreaterEqual(started, self.timestamp("2026-10-03T00:00:00Z"))
            self.zero(process["native_exit"])
            self.zero(process["comparison_exit"])
            self.digest(process[receipt_key])
            self.digest(process[verdict_key])
        self.assertNotEqual(processes[0][receipt_key], processes[1][receipt_key])
        self.assertEqual(receipt["determinism"]["fresh_native_engine_exports"], 4)
        self.digest(receipt["determinism"]["all_four_normalized_sha256"])
        return processes

    def test_stress_identity_and_actual_reviewed_runtime_sources(self):
        receipt = self.load(STRESS)
        old = self.load("receipt-stress-20261002.json")
        self.assertEqual(receipt["schema"], "spy-parity-qualified-summary/1")
        self.assertEqual(receipt["id"], "nautilus-spy-stress-review-fixes-two-processes-20261003")
        self.assertNotEqual(receipt["id"], old["id"])
        self.assertEqual(receipt["case"], "one_stress")
        self.assertEqual(receipt["raw_receipt_id"], "spy-parity-one-stress-v2")
        self.assertEqual(receipt["harness_commit"], STRESS_COMMIT)
        self.assertNotEqual(receipt["harness_commit"], old["harness_commit"])
        reviewed = self.reviewed_sources(receipt, STRESS_FILES)
        runtime = STRESS_FILES | {"mapping-manifest.json", "mapping-manifest-v2.json", "tolerances.json"}
        self.assertEqual(set(receipt["receipt_source_sha256"]), runtime)
        self.assertEqual(receipt["receipt_source_sha256"], {name: self.sha256(name) for name in runtime})
        self.assertEqual({n: receipt["receipt_source_sha256"][n] for n in STRESS_FILES}, reviewed)

    def test_successor_seal_and_review_inventory_bind_qualified_stress(self):
        mapping = self.load(SUCCESSOR)
        stress = self.load(STRESS)
        reviewed = self.reviewed_sources(stress, STRESS_FILES)
        self.assertEqual(mapping["sealed_stress_source_sha256"], reviewed)
        self.assertEqual(mapping["id"], "spy-over-limit-native-refusal-review-fixes-20261003")
        self.assertEqual(mapping["inherits"], {"path": "mapping-manifest-stress-20261002.json",
                         "sha256": self.sha256("mapping-manifest-stress-20261002.json")})
        self.assertEqual(mapping["successor_of"], {
            **mapping["successor_of"], "path": "mapping-manifest-over-limit-20261002.json",
            "sha256": self.sha256("mapping-manifest-over-limit-20261002.json")})
        self.assertEqual(set(mapping["review"]["runtime_source_files"]), REFUSAL_FILES)
        self.assertEqual(len(mapping["review"]["runtime_source_files"]), 13)
        self.assertTrue(mapping["review"]["requires_independent_review_before_engine"])
        self.assertTrue(mapping["review"]["requires_exact_authorized_argv_arrays"])
        qualified = mapping["qualified_stress_evidence"]
        self.assertEqual(qualified["source_harness_commit"], stress["harness_commit"])
        self.assertEqual(qualified["review_sha256"], stress["prospective_review"]["original_record_sha256"])
        self.assertEqual(qualified["frozen_arguments_sha256"], stress["isolation"]["frozen_argv_sha256"])
        self.assertEqual(len(qualified["processes"]), 2)
        for bound, measured in zip(qualified["processes"], stress["fresh_processes"]):
            self.assertEqual(bound["process"], measured["process"])
            self.assertEqual(bound["receipt_sha256"], measured["original_receipt_sha256"])
            self.assertEqual(bound["verdict_sha256"], measured["original_verdict_sha256"])
            self.assertEqual(bound["started_utc"], measured["started_utc"])
            self.assertEqual(bound["id"], measured["receipt_id"])
            self.assertEqual(bound["checks"], {"PASS": 142})
            self.assertEqual(bound["source_files"], 13)
            self.assertEqual(bound["source_mismatches"], [])
            self.assertIs(bound["two_internal_runs_equal"], True)

    def test_stress_has_two_distinct_prospectively_reviewed_complete_processes(self):
        receipt = self.load(STRESS)
        processes = self.prospective_processes(receipt, "original_receipt_sha256", "original_verdict_sha256")
        for process in processes:
            self.assertEqual(process["receipt_id"], "spy-parity-one-stress-v2")
            self.assertEqual((process["execution_checks_passed"], process["preconditions_passed"]), (123, 19))
            self.assertEqual(process["execution_checks_passed"] + process["preconditions_passed"], 142)
            self.zero(process["failed"])
            self.zero(process["skipped"])
            self.assertEqual(process["strict_verdict"], "PASS")
            self.assertIs(process["complete"], True)
            self.assertIs(process["preregistration_qualifying"], True)
        self.assertIs(receipt["economics_equal_between_processes"], True)

    def test_historical_cli_is_eight_source_verification_without_a_new_engine(self):
        historic = self.load(STRESS)["historical_v2_cli"]
        self.assertEqual(historic["case"], self.load("receipt-v2.json")["case"])
        self.assertEqual(historic["archived_source_directory"], "historical-source-v2-a2ad39a")
        self.assertEqual(historic["source_files"], 8)
        self.assertEqual(historic["checks_passed"], 136)
        self.zero(historic["failed"])
        self.zero(historic["skipped"])
        self.zero(historic["exit_code"])
        self.assertIs(historic["new_engine_execution"], False)
        self.digest(historic["verdict_sha256"])
        # Existing historical-source and published receipt tests independently
        # retain all eight hashes and old manifests; do not rebind them here.

    def test_refusal_historical_thirteen_sources_selected_manifest_and_prospective_processes(self):
        receipt = self.load(REFUSAL)
        old = self.load("receipt-over-limit-20261002.json")
        self.assertEqual(receipt["id"], "nautilus-spy-initial-margin-refusal-review-fixes-two-processes-20261003")
        self.assertNotEqual(receipt["id"], old["id"])
        self.assertNotEqual(receipt["id"], self.load(STRESS)["id"])
        self.assertEqual(receipt["case"], "over_limit")
        self.assertEqual(receipt["harness_commit"], REFUSAL_COMMIT)
        self.assertNotEqual(receipt["harness_commit"], old["harness_commit"])
        reviewed = self.reviewed_sources(receipt, REFUSAL_FILES)
        self.assertEqual(receipt["selected_mapping"], {"path": SUCCESSOR, "sha256": self.sha256(SUCCESSOR)})
        self.assertEqual(reviewed[SUCCESSOR], receipt["selected_mapping"]["sha256"])
        self.assertEqual(set(self.load(SUCCESSOR)["review"]["runtime_source_files"]), set(reviewed))
        processes = self.prospective_processes(receipt, "receipt_sha256", "verdict_sha256")
        observed_counts = set()
        for process in processes:
            self.assertIs(type(process["pass"]), int)
            self.assertGreater(process["pass"], 86)  # Actual new callback gates must have run.
            observed_counts.add(process["pass"])
            self.zero(process["fail"])
            self.zero(process["skipped"])
            self.assertEqual(len(process["raw_export_sha256"]), 2)
            for digest in process["raw_export_sha256"]:
                self.digest(digest)
        self.assertEqual(len(observed_counts), 1)

    def test_refusal_requires_retained_complete_native_callbacks_and_original_reason(self):
        receipt = self.load(REFUSAL)
        callbacks = receipt["callback_evidence"]
        self.assertEqual(callbacks["event_sequence"], ["OrderInitialized", "OrderDenied"])
        self.assertEqual(callbacks["callback_events_per_engine"], 2)
        for name in ("all_four_streams_equal_cached_order_events", "checked_by_strict_comparator",
                     "native_callback_events_retained"):
            self.assertIs(callbacks[name], True)
        self.assertEqual(callbacks["order_denied_reason"], DENIAL_REASON)
        economics = receipt["economics_equal_between_processes"]
        self.assertEqual(economics["reason"], callbacks["order_denied_reason"])
        self.assertEqual(economics["native_order_type"], "MARKET")
        self.assertEqual(economics["status"], "DENIED")
        self.assertEqual(economics["quantity"], "1217")
        self.assertEqual(economics["filled_qty"], "0")
        self.assertEqual((economics["balance_free"], economics["balance_total"]),
                         ("100000.00 USD", "100000.00 USD"))
        self.zero(receipt["mapping_boundary"]["fills"])
        self.assertEqual(receipt["mapping_boundary"]["fees_usd"], "0.00")
        self.zero(receipt["determinism"]["strategy_callback_errors"])


if __name__ == "__main__":
    unittest.main()
