import json
from pathlib import Path
import tempfile
import unittest
from stage import EXPECTED, actions, execute


class ClaudeRecoveryFixtureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "input.json").write_text('{"records":[{"id":"delta","value":8},{"id":"alpha","value":3},{"id":"charlie","value":5},{"id":"bravo","value":2}]}\n')

    def pending(self):
        execute(self.root, "checkpoint")
        with (self.root / "actions.jsonl").open("a") as out:
            out.write('{"action":"wait"}\n')
        (self.root / "resume-authorized.json").write_text('{}\n')

    def test_fixed_checkpoint_and_resumed_result(self):
        self.pending()
        execute(self.root, "finalize")
        self.assertEqual((self.root / "checkpoint.json").read_bytes(), EXPECTED)
        self.assertEqual(actions(self.root), ["checkpoint", "wait", "finalize"])
        self.assertEqual(json.loads((self.root / "final.json").read_text())["execution_count"], 1)

    def test_repeated_checkpoint_is_counted_and_rejected(self):
        execute(self.root, "checkpoint")
        with self.assertRaisesRegex(ValueError, "checkpoint_repeated"):
            execute(self.root, "checkpoint")
        self.assertEqual(actions(self.root).count("checkpoint"), 2)

    def test_existing_checkpoint_is_not_overwritten(self):
        (self.root / "checkpoint.json").write_bytes(b"existing")
        with self.assertRaises(FileExistsError):
            execute(self.root, "checkpoint")
        self.assertEqual((self.root / "checkpoint.json").read_bytes(), b"existing")

    def test_tampered_checkpoint_cannot_finalize(self):
        self.pending()
        (self.root / "checkpoint.json").write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "checkpoint_changed"):
            execute(self.root, "finalize")

    def test_completion_before_supervisor_resume_fails(self):
        self.pending()
        (self.root / "resume-authorized.json").unlink()
        with self.assertRaisesRegex(ValueError, "resume_not_authorized"):
            execute(self.root, "finalize")

    def test_input_drift_fails_frozen_oracle(self):
        (self.root / "input.json").write_text('{"records":[]}\n')
        with self.assertRaisesRegex(ValueError, "input_oracle_mismatch"):
            execute(self.root, "checkpoint")


if __name__ == "__main__":
    unittest.main()
