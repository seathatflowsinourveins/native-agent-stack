"""Checks for the wave-2 gap ledger (local integration)."""
from __future__ import annotations

import importlib.util
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "catalogs/landscape/gap-wave2-20260923--gap-resolution.json"
RANK = {"not_run": 0, "not_settled": 1, "advanced": 2, "settled": 3}


def _tool():
    spec = importlib.util.spec_from_file_location("gap_wave_ledger", ROOT / "tools/sota-convergence/gap_wave_ledger.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class GapWaveLedgerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = json.loads(LEDGER.read_text(encoding="utf-8"))
        cls.tool = _tool()

    def test_ledger_is_up_to_date(self):
        self.assertEqual(self.tool.main(["--root", str(ROOT), "--wave", "gap-wave2-20260923",
                                         "--owner", "gap-resolution", "--check"]), 0)

    def test_status_is_the_best_credit_and_multi_gap_receipts_never_settle(self):
        receipts = {r["path"]: r for r in self.doc["receipts"]}
        for layer in self.doc["layers"]:
            for gap in layer["gaps"]:
                with self.subTest(layer=layer["layer_id"], gap=gap["index"]):
                    credits = []
                    for entry in gap["receipts"]:
                        receipt = receipts[entry["path"]]
                        override = (receipt.get("per_gap_settles") or {}).get(f"{layer['layer_id']}:{gap['index']}")
                        if override:
                            base = {"true": "settled", "partially": "advanced", "false": "not_settled"}[override]
                            if len(receipt["gap_refs"]) > 1 and base == "settled":
                                base = "advanced"
                            self.assertEqual(entry["credit"], base)
                        self.assertTrue((ROOT / entry["path"]).is_file())
                        self.assertIn([layer["layer_id"], gap["index"]], receipt["gap_refs"])
                        if len(receipt["gap_refs"]) > 1:
                            self.assertNotEqual(entry["credit"], "settled")
                        credits.append(entry["credit"])
                    expected = max(credits, key=RANK.get) if credits else "not_run"
                    self.assertEqual(gap["status"], expected)

    def test_settle_key_rejects_unknown_values(self):
        self.assertEqual(self.tool.settle_key("partially (was true)"), "partially")
        self.assertEqual(self.tool.settle_key(True), "true")
        with self.assertRaises(SystemExit):
            self.tool.settle_key("maybe")

    def test_every_receipt_names_the_crosswalk_revision(self):
        for receipt in self.doc["receipts"]:
            self.assertTrue(self.doc["source_revision"].startswith(receipt["source_revision"][:7]), receipt["path"])

    def test_repo_raw_artifacts_match_their_recorded_hash(self):
        import hashlib
        for path in sorted((ROOT / "evidence/artifacts/gap-wave2-20260923").rglob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                continue
            for artifact in data.get("raw_artifacts") or []:
                if not isinstance(artifact, dict) or not artifact.get("sha256"):
                    continue
                rel = artifact.get("path", "")
                if rel.startswith(("~", "/", "<")) or not (ROOT / rel).is_file():
                    continue  # host-side or scratch artifact, recorded by hash only
                with self.subTest(receipt=path.name, artifact=rel):
                    actual = hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
                    self.assertEqual(actual, artifact.get("published_sha256", artifact["sha256"]))

    def test_no_host_paths_or_session_identifiers(self):
        text = LEDGER.read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"/home/(?!example/)|/tmp/claude-|[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}", text))


if __name__ == "__main__":
    unittest.main()
