import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "blueprints/convergence-practice/job-recovery"
SPEC = importlib.util.spec_from_file_location("job_recovery_fixture", HERE / "fixture.py")
FIXTURE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FIXTURE)


class JobRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.work = Path(self.temporary.name)
        (self.work / "source").mkdir()
        for name, part in (("planner.py", "accepted"), ("test_planner.py", "seed")):
            shutil.copyfile(ROOT / f"blueprints/convergence-practice/native-worker/{part}/{name}",
                            self.work / "source" / name)
        FIXTURE.exclusive(self.work / "expected.json", FIXTURE.source_hashes(self.work))

    def test_checkpoint_and_finalize_preserve_bytes_and_count(self):
        FIXTURE.checkpoint(self.work)
        before = (self.work / "checkpoint.json").read_bytes()
        (self.work / "release-finalize").touch()
        FIXTURE.finalize(self.work)
        self.assertEqual(before, (self.work / "checkpoint.json").read_bytes())
        result = json.loads((self.work / "completed.json").read_text())
        self.assertEqual(result["tests"], 12)
        self.assertEqual(result["execution_count"], 1)
        self.assertIn("Ran 12 tests", (self.work / "final-tests.log").read_text())

    def test_duplicate_checkpoint_fails_before_reexecution(self):
        FIXTURE.checkpoint(self.work)
        before = (self.work / "checkpoint-tests.log").read_bytes()
        with self.assertRaises(FileExistsError):
            FIXTURE.checkpoint(self.work)
        self.assertEqual(before, (self.work / "checkpoint-tests.log").read_bytes())

    def test_changed_source_is_rejected(self):
        FIXTURE.checkpoint(self.work)
        (self.work / "source/planner.py").write_text("raise RuntimeError('changed')\n")
        with self.assertRaisesRegex(ValueError, "Frozen source"):
            FIXTURE.verify_checkpoint(self.work)

    def test_changed_oracle_is_rejected(self):
        (self.work / "source/test_planner.py").write_text("# silently removed tests\n")
        with self.assertRaisesRegex(ValueError, "Frozen source"):
            FIXTURE.checkpoint(self.work)
        self.assertFalse((self.work / "checkpoint.json").exists())

    def test_forged_checkpoint_count_is_rejected(self):
        FIXTURE.checkpoint(self.work)
        checkpoint = json.loads((self.work / "checkpoint.json").read_text())
        checkpoint["execution_count"] = 2
        (self.work / "checkpoint.json").write_text(json.dumps(checkpoint))
        with self.assertRaisesRegex(ValueError, "Checkpoint content"):
            FIXTURE.verify_checkpoint(self.work)

    def test_failed_checkpoint_cannot_be_silently_reclaimed(self):
        FIXTURE.exclusive(self.work / "checkpoint-started.json", {"execution_count": 1})
        with self.assertRaises(FileExistsError):
            FIXTURE.checkpoint(self.work)
        self.assertFalse((self.work / "checkpoint.json").exists())

    def test_finalizer_requires_checkpoint(self):
        (self.work / "release-finalize").touch()
        with self.assertRaises(FileNotFoundError):
            FIXTURE.finalize(self.work)
        self.assertFalse((self.work / "completed.json").exists())


if __name__ == "__main__":
    unittest.main()
