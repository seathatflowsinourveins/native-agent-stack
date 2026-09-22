"""Consistency checks for catalogs/landscape/gap-resolution-20260922.json (local integration)."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "catalogs/landscape/gap-resolution-20260922.json"
STATUSES = {"settled", "advanced", "not_settled", "open"}
CATEGORIES = {
    "executable_now", "needs_user_login", "needs_paid_entitlement", "needs_hardware", "time_gated",
    "peer_owned", "codex_limited", "manifest_gap", "documentation_fix", "not_actionable", "needs_user_input",
}


class GapResolutionLedgerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = json.loads(LEDGER.read_text(encoding="utf-8"))

    def test_covers_every_landscape_row(self):
        rows = set()
        for catalog in ("foundation", "us-equities"):
            data = json.loads((ROOT / f"catalogs/landscape/{catalog}.json").read_text(encoding="utf-8"))
            rows |= {(catalog, row["layer_id"]) for row in data["layers"]}
        ledger_rows = {(layer["catalog"], layer["layer_id"]) for layer in self.doc["layers"]}
        self.assertEqual(ledger_rows, rows)

    def test_vocabularies_and_receipt_links(self):
        receipt_paths = {r["path"] for r in self.doc["receipts"]}
        for layer in self.doc["layers"]:
            indexes = [g["index"] for g in layer["gaps"]]
            self.assertEqual(len(indexes), len(set(indexes)), layer["layer_id"])
            for gap in layer["gaps"]:
                with self.subTest(layer=layer["layer_id"], gap=gap["index"]):
                    self.assertIn(gap["status"], STATUSES)
                    self.assertIn(gap["category"], CATEGORIES)
                    self.assertTrue(gap["blocker"].strip())
                    self.assertEqual(gap["status"] == "open", not gap["receipts"])
                    for path in gap["receipts"]:
                        self.assertIn(path, receipt_paths)
                        self.assertTrue((ROOT / path).is_file(), path)

    def test_every_receipt_is_referenced_and_exists(self):
        referenced = {p for layer in self.doc["layers"] for g in layer["gaps"] for p in g["receipts"]}
        for receipt in self.doc["receipts"]:
            with self.subTest(receipt=receipt["path"]):
                self.assertTrue((ROOT / receipt["path"]).is_file())
                if receipt["gap_refs"]:
                    self.assertIn(receipt["path"], referenced)
                else:
                    # Operational receipts (e.g. the Headroom live-store cleanup) settle no gap.
                    self.assertEqual(receipt["settles_gap"], "not_applicable")

    def test_no_host_paths(self):
        text = LEDGER.read_text(encoding="utf-8")
        self.assertNotRegex(text, r"/home/(?!example/)")
        self.assertNotIn("/tmp/claude-", text)


if __name__ == "__main__":
    unittest.main()
