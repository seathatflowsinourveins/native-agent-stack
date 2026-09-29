"""Tests for evidence/artifacts/claude-spend-scan.py.txt and the receipt that pins it.

The scan is stored as a text artifact, so it is loaded from that path. The synthetic control holds hand-computed
expected values and one mutant run per counting rule, so removing a rule from the scan fails the control."""

from __future__ import annotations

import hashlib
import importlib.machinery
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "evidence" / "artifacts" / "claude-spend-scan.py.txt"
RECEIPT = ROOT / "evidence" / "receipts" / "claude-spend-attribution-20260929.json"


def _load_scan():
    loader = importlib.machinery.SourceFileLoader("claude_spend_scan", str(ARTIFACT))
    spec = importlib.util.spec_from_loader("claude_spend_scan", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class SpendScanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scan = _load_scan()
        cls.receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))

    def test_control_passes_and_every_rule_has_a_mutant(self):
        result = self.scan.control()
        self.assertTrue(result["passed"], result)
        self.assertEqual({rule for rule in result["mutants"]}, {rule for rule in self.scan.DEFAULT_RULES})
        for rule, mutant in result["mutants"].items():
            self.assertTrue(mutant["moved_as_expected"], rule)

    def test_a_removed_rule_fails_the_control(self):
        original = dict(self.scan.DEFAULT_RULES)
        try:
            # The control's baseline runs with the default rules, so breaking one must break the baseline.
            self.scan.DEFAULT_RULES["dedup"] = False
            self.assertFalse(self.scan.control()["passed"])
        finally:
            self.scan.DEFAULT_RULES.clear()
            self.scan.DEFAULT_RULES.update(original)

    def test_receipt_pins_this_script(self):
        digest = hashlib.sha256(ARTIFACT.read_bytes()).hexdigest()
        self.assertEqual(self.receipt["provenance"]["script_sha256"], digest)

    def test_receipt_records_a_passing_control_and_a_close_reconciliation(self):
        data = self.receipt["data"]
        self.assertTrue(data["control"]["passed"])
        for key in ("inputTokens", "outputTokens", "cacheReadTokens", "cacheCreationTokens"):
            self.assertLess(abs(data["reconciliation"][key]["relative_difference"]), 5e-5, key)
        for command in data["commands"]:
            self.assertEqual(command["exit_code"], 0, command["command"])


if __name__ == "__main__":
    unittest.main()
