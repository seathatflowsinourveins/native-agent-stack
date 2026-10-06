"""Synthetic source-projection checks; these tests perform no model operation."""

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "evidence/artifacts/new-wsl-definitive-defaults-20261001/assemble_manifest.py"
SPEC = importlib.util.spec_from_file_location("local_model_ruling_assembler", SOURCE)
ASSEMBLER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ASSEMBLER)


class CurrentModelRulings(unittest.TestCase):
    def fixture(self, temporary):
        root = Path(temporary)
        receipt = root / "source-choice.json"
        receipt.write_text('{"evidence_class":"source_review","native_runs":0}\n')
        ruling = {
            "date_utc": "2026-10-06", "evidence_class": "source_review",
            "default": {"name": "Not installed: retired", "repository": ""},
            "state": "resolved", "installs_nothing_extra": True,
            "label": "dated owner retirement; no current returned measurement",
            "resolution": {"outcome": "not_installed", "by": "owner",
                           "reason": "no consumer", "covered_by": "not needed"},
            "receipts": [{"path": receipt.name,
                          "sha256": hashlib.sha256(receipt.read_bytes()).hexdigest()}],
        }
        row = {
            "slot_id": "local-generation-model", "state": "measurement",
            "default": "historical generator", "repository": "https://example.invalid/model",
            "installs_nothing_extra": False, "definitive": False,
            "label": "historical measurement", "resolution": {"outcome": "split"},
            "measurement": {"returned": True, "receipts": [{"path": "old-receipt.json"}]},
        }
        settlements = root / "settlements.json"
        settlements.write_text(json.dumps([{"slot_id": row["slot_id"], "current_ruling": ruling}]))
        return root, settlements, row, ruling

    def test_retirement_retains_returned_history_without_claiming_a_new_run(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, settlements, row, ruling = self.fixture(temporary)
            historical = copy.deepcopy(row)
            with mock.patch.object(ASSEMBLER, "ROOT", root), mock.patch.object(ASSEMBLER, "SETTLEMENTS", settlements):
                ASSEMBLER.apply_current_rulings([row])
            self.assertEqual(row["historical_settlement"], historical)
            self.assertIsNone(row["measurement"])
            self.assertEqual(row["state"], "resolved")
            self.assertTrue(row["installs_nothing_extra"])
            self.assertEqual(row["repository"], "")
            self.assertEqual(row["resolution"]["first_round_record"]["label"], historical["label"])
            self.assertEqual(row["current_ruling"], ruling)

    def test_source_receipt_hash_mismatch_is_rejected_before_projection(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, settlements, row, ruling = self.fixture(temporary)
            historical = copy.deepcopy(row)
            ruling["receipts"][0]["sha256"] = "0" * 64
            settlements.write_text(json.dumps([{"slot_id": row["slot_id"], "current_ruling": ruling}]))
            with mock.patch.object(ASSEMBLER, "ROOT", root), mock.patch.object(ASSEMBLER, "SETTLEMENTS", settlements):
                with self.assertRaisesRegex(ValueError, "sha256 mismatch"):
                    ASSEMBLER.apply_current_rulings([row])
            self.assertEqual(row, historical)

    def test_current_choice_cannot_declare_itself_a_returned_measurement(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, settlements, row, ruling = self.fixture(temporary)
            ruling["state"] = "measurement"
            settlements.write_text(json.dumps([{"slot_id": row["slot_id"], "current_ruling": ruling}]))
            with mock.patch.object(ASSEMBLER, "ROOT", root), mock.patch.object(ASSEMBLER, "SETTLEMENTS", settlements):
                with self.assertRaisesRegex(ValueError, "resolved source-review"):
                    ASSEMBLER.apply_current_rulings([row])

    def test_historical_only_settlement_keeps_its_returned_record(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, settlements, row, _ = self.fixture(temporary)
            settlements.write_text(json.dumps([{"slot_id": row["slot_id"]}]))
            historical = copy.deepcopy(row)
            with mock.patch.object(ASSEMBLER, "ROOT", root), mock.patch.object(ASSEMBLER, "SETTLEMENTS", settlements):
                ASSEMBLER.apply_current_rulings([row])
            self.assertEqual(row, historical)


if __name__ == "__main__":
    unittest.main()
