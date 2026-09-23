"""Consistency checks for catalogs/landscape/gap-crosswalk-92bb279.json (local integration)."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "catalogs/landscape/gap-crosswalk-92bb279.json"
EVID = ROOT / "evidence/artifacts/gap-crosswalk-92bb279"
CATEGORIES = {"executable_now", "catalog_edit", "needs_user_login", "needs_paid_entitlement", "needs_hardware",
              "time_gated", "needs_user_decision", "not_actionable"}
DECISIONS = {"settles", "partially", "not_addressed"}
STATUS = {"settles": "settled_by_receipt", "partially": "advanced_by_receipt", "not_addressed": "open"}
RANK = {"not_addressed": 0, "partially": 1, "settles": 2}


class GapCrosswalkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = json.loads(LEDGER.read_text(encoding="utf-8"))

    def test_status_follows_the_final_decisions(self):
        threshold = self.doc["method"]["typesafe"]["threshold_p_addressed"]
        for layer in self.doc["layers"]:
            for gap in layer["gaps"]:
                with self.subTest(layer=layer["layer_id"], gap=gap["index"]):
                    self.assertIn(gap["category"], CATEGORIES)
                    best = "not_addressed"
                    for r in gap["receipts"]:
                        self.assertTrue((ROOT / r["receipt"]).is_file(), r["receipt"])
                        self.assertEqual(r["queued"], r["typesafe_p_addressed"] >= threshold)
                        if r["queued"]:
                            self.assertIn(r["review_decision"], DECISIONS, "every queued pair has a review decision")
                        self.assertIn(r["final_decision"], DECISIONS)
                        if (r["review_decision"] or "not_addressed") != "not_addressed":
                            self.assertIn(r.get("verify_verdict"), {"agree", "disagree"}, "positive decisions are verified")
                        if RANK[r["final_decision"]] > RANK[best]:
                            best = r["final_decision"]
                    self.assertEqual(gap["status"], STATUS[best])

    def test_judgment_and_review_files_match_their_recorded_hashes(self):
        method = self.doc["method"]
        for name, digest in method["typesafe"]["judgments_sha256"].items():
            self.assertEqual(hashlib.sha256((EVID / name).read_bytes()).hexdigest(), digest, name)
        self.assertEqual(hashlib.sha256((EVID / "review-results.json").read_bytes()).hexdigest(),
                         method["review_results_sha256"])

    def test_every_gap_of_the_source_revision_is_covered(self):
        rev = self.doc["source_revision"]
        for rel, digest in self.doc["source_files_sha256"].items():
            try:
                raw = subprocess.run(["git", "-C", str(ROOT), "show", f"{rev}:{rel}"], capture_output=True, check=True).stdout
            except (OSError, subprocess.CalledProcessError):
                self.skipTest(f"{rev} is not in this checkout's history (shallow clone)")
            self.assertEqual(hashlib.sha256(raw).hexdigest(), digest, rel)
            catalog = rel.rsplit("/", 1)[1].removesuffix(".json")
            layers = {l["layer_id"]: l for l in self.doc["layers"] if l["catalog"] == catalog}
            for row in json.loads(raw)["layers"]:
                self.assertEqual([g["text"] for g in layers[row["layer_id"]]["gaps"]], row.get("open_gaps", []))

    def test_every_layer_has_one_known_owner(self):
        owners = set(self.doc["owners"])
        self.assertEqual(len(self.doc["layers"]), 32)
        for layer in self.doc["layers"]:
            self.assertIn(layer["owner"], owners)

    def test_no_host_paths_or_session_identifiers(self):
        pattern = re.compile(r"/home/(?!example/)|/tmp/claude-|[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}", re.I)
        for path in [LEDGER, *EVID.iterdir()]:
            with self.subTest(path=path.name):
                self.assertIsNone(pattern.search(path.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
