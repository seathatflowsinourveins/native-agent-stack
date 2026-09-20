"""Reject overclaims and evidence drift without rerunning native work."""

import copy
import importlib.util
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location(
    "wsl_transport_audit", Path(__file__).resolve().parent / "audit.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
audit, load = MODULE.audit, MODULE.load


class TransportEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.receipt = load("receipt.json")
        self.prior = load("receipt-attempt-1.json")
        self.freeze = load("frozen-evidence.json")

    def check(self):
        return audit(self.receipt, self.prior, self.freeze)

    def test_retained_evidence_matches_frozen_source(self):
        self.assertEqual(self.check(), [])

    def test_failed_reconnect_cannot_qualify_survival(self):
        self.receipt["native"]["reconnected_status"] = "aborted"
        self.assertIn("native survival sequence differs", self.check())

    def test_retry_success_is_not_transport_survival(self):
        self.receipt["native"]["native_selected_step_retry"] = True
        self.assertIn("stop/retry is not survival", self.check())

    def test_duplicate_checkpoint_fails(self):
        self.receipt["native"]["checkpoint_execution_count"] = 2
        self.assertIn("checkpoint or unchanged oracle differs", self.check())

    def test_oracle_reduction_fails(self):
        self.receipt["native"]["oracle_tests_after"] = 11
        self.assertIn("checkpoint or unchanged oracle differs", self.check())

    def test_live_controller_or_listener_fails(self):
        for key in ["observed_owned_processes_remaining", "observed_owned_listeners_remaining"]:
            with self.subTest(key=key):
                receipt = copy.deepcopy(self.receipt)
                receipt["native"][key] = 1
                self.assertIn("owned cleanup incomplete", audit(receipt, self.prior, self.freeze))

    def test_original_failure_remains_visible(self):
        self.prior["transport_survival_qualified"] = True
        self.assertIn("original failure/repair was relabeled", self.check())

    def test_unexpected_ssh_exit_is_rejected(self):
        self.receipt["transport"]["local_ssh_exit_code"] = 0
        self.assertIn("owned controlled transport protocol differs", self.check())

    def test_source_hash_drift_fails(self):
        self.freeze["attempts"]["attempt-2"]["files"][0]["sha256"] = "0" * 64
        self.assertTrue(any("frozen source changed" in error for error in self.check()))

    def test_outage_claim_is_rejected(self):
        self.receipt["transport"]["real_network_outage_or_host_restart"] = True
        self.assertIn("controlled disconnect broadened to outage", self.check())


if __name__ == "__main__":
    unittest.main()
