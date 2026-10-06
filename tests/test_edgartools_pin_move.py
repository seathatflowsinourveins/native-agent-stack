"""Dated corrections preserve the old inventory and identify current pin mirrors."""

import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
CLASSIFICATION = "evidence/artifacts/edgartools-5600-20261004/pin-site-classification.json"
RECEIPT = "evidence/receipts/edgartools-5600-pin-move-20261004.json"
AUDIT = "blueprints/token-native-focus/saturation-audit.json"
SNAPSHOT = "catalogs/landscape/upstream-snapshot.json"


class EdgarToolsPinMoveTests(unittest.TestCase):
    def test_dated_correction_identifies_all_five_live_mirrors(self):
        inventory = json.loads((ROOT / CLASSIFICATION).read_text(encoding="utf-8"))
        self.assertTrue("classification_corrections_20261005" in inventory,
                        "the five live mirrors need an explicit dated correction")
        corrections = inventory["classification_corrections_20261005"]
        expected = {(AUDIT, 3209, "version"), (SNAPSHOT, 3496, "selected_version"),
                    (SNAPSHOT, 3539, "latest_stable_release/tag_name"),
                    (SNAPSHOT, 3541, "latest_stable_release/html_url"),
                    (SNAPSHOT, 3553, "latest_release_source/ref")}
        self.assertEqual({(row["path"], row["line_at_base"], row["key"]) for row in corrections}, expected)
        self.assertEqual(len(corrections), len(expected))
        for correction in corrections:
            with self.subTest(path=correction["path"], key=correction["key"]):
                self.assertEqual(correction["classification"], "live selection mirror")
                self.assertEqual(correction["action"], "moved_to_5.60.0")
                # The original classification is retained, not silently replaced.
                original, = [row for row in inventory["records"]
                             if (row["path"], row["line_at_base"]) ==
                             (correction["path"], correction["line_at_base"])]
                self.assertEqual(original["classification"], "dated historical snapshot")
                self.assertEqual(original["action"], "keep_history")
                document = json.loads((ROOT / correction["path"]).read_text(encoding="utf-8"))
                value = next(row for row in document["components"] if row["component_id"] == "edgartools")
                for key in correction["key"].split("/"):
                    value = value[key]
                self.assertEqual(value, correction["new_value"])
                self.assertIn("5.60.0", value)
        historical, = [row for row in inventory["records"]
                       if (row["path"], row["line_at_base"]) == (SNAPSHOT, 3524)]
        self.assertEqual(historical["action"], "keep_history")
        snapshot = json.loads((ROOT / SNAPSHOT).read_text(encoding="utf-8"))
        edgar = next(row for row in snapshot["components"] if row["component_id"] == "edgartools")
        self.assertTrue(any(check["endpoint"] == "repos/dgunning/edgartools/commits/v5.58.0"
                            for check in edgar["checks"]))

    def test_correction_is_relayed_with_matching_registry_and_artifact_hash(self):
        raw = (ROOT / CLASSIFICATION).read_bytes()
        inventory = json.loads(raw)
        receipt = json.loads((ROOT / RECEIPT).read_text(encoding="utf-8"))
        self.assertTrue("pin_classification_correction_20261005" in receipt,
                        "the receipt must correct its relayed classification")
        note = receipt["pin_classification_correction_20261005"]
        self.assertIn(f"relayed by {RECEIPT}:", note)
        self.assertEqual(note, inventory["correction_note_20261005"])
        self.assertTrue(note.startswith("2026-10-05:"))
        evidence = json.loads((ROOT / "manifests/evidence.json").read_text(encoding="utf-8"))
        registered = next(row for row in evidence["receipts"] if row["id"] == receipt["id"])
        self.assertEqual(registered["pin_classification_correction_20261005"], note)
        artifact = next(row for row in receipt["artifacts"] if row["path"] == CLASSIFICATION)
        self.assertEqual(artifact["sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(artifact["bytes"], len(raw))


if __name__ == "__main__":
    unittest.main()
