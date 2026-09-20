"""Offline gates only: this test module never invokes Codex or a provider."""
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BLUEPRINT = ROOT / "blueprints/convergence-practice/native-recovery"
SPEC = importlib.util.spec_from_file_location("native_recovery_fixture", BLUEPRINT / "fixture.py")
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


class NativeRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        shutil.copyfile(BLUEPRINT / "seed/input.json", self.root / "input.json")
        self.fixture = M.Fixture(self.root)

    def test_checkpoint_survives_unanswered_wait(self):
        first = self.fixture.checkpoint()
        self.assertIsNone(self.fixture.wait())
        self.assertFalse((self.root / "final.json").exists())
        final = self.fixture.finalize()
        self.assertEqual(first["checkpoint_sha256"], final["checkpoint_sha256"])
        self.assertEqual((self.root / "checkpoint.json").read_bytes(), M.EXPECTED)
        self.assertEqual(self.fixture.calls, ["checkpoint", "wait", "finalize"])

    def test_checkpoint_replay_is_failure_not_an_idempotent_success(self):
        self.fixture.checkpoint()
        with self.assertRaisesRegex(ValueError, "checkpoint_repeated"):
            self.fixture.checkpoint()
        self.assertEqual(self.fixture.calls.count("checkpoint"), 2)

    def test_preexisting_effect_is_not_overwritten(self):
        path = self.root / "checkpoint.json"
        path.write_bytes(b"preexisting")
        with self.assertRaises(FileExistsError):
            self.fixture.checkpoint()
        self.assertEqual(path.read_bytes(), b"preexisting")

    def test_modified_checkpoint_fails_finalization(self):
        self.fixture.checkpoint()
        self.fixture.wait()
        (self.root / "checkpoint.json").write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "checkpoint_changed"):
            self.fixture.finalize()
        self.assertFalse((self.root / "final.json").exists())

    def test_finalization_cannot_skip_checkpoint_or_wait(self):
        with self.assertRaisesRegex(ValueError, "finalization_order"):
            self.fixture.finalize()

    def test_input_change_does_not_pass_the_frozen_oracle(self):
        (self.root / "input.json").write_text('{"records":[{"id":"alpha","value":99}]}')
        with self.assertRaisesRegex(ValueError, "checkpoint_oracle_mismatch"):
            self.fixture.checkpoint()

    def test_incomplete_checks_cannot_qualify(self):
        self.assertFalse(M.assess({}))
        self.assertFalse(M.assess({"same_thread_id": True, "checkpoint_executed_once": True}))

    def test_published_receipt_when_present_matches_qualification(self):
        path = BLUEPRINT / "receipt.json"
        if not path.exists():
            self.skipTest("Native receipt not yet captured; offline fixture only")
        receipt = json.loads(path.read_text())
        self.assertEqual(receipt["status"] == "passed", M.assess(receipt["checks"]))
        self.assertEqual(receipt["checkpoint_expected_sha256"], M.digest(M.EXPECTED))


if __name__ == "__main__":
    unittest.main()
