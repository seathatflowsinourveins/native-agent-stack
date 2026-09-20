"""Replay frozen repair artifacts offline; this does not launch a native agent."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


FIXTURE = Path(__file__).resolve().parents[1] / "blueprints/convergence-practice/native-worker"


class NativeWorkerFixtureTests(unittest.TestCase):
    def replay(self, implementation):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            shutil.copy2(FIXTURE / implementation / "planner.py", directory)
            shutil.copy2(FIXTURE / "seed/test_planner.py", directory)
            return subprocess.run(
                [sys.executable, "-m", "unittest", "-v", "test_planner"],
                cwd=directory, capture_output=True, text=True, timeout=15,
            )

    def test_original_fixture_exposes_eight_failures(self):
        result = self.replay("seed")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Ran 12 tests", result.stderr)
        self.assertIn("FAILED (failures=8)", result.stderr)

    def test_native_child_patch_passes_unchanged_oracle(self):
        result = self.replay("accepted")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Ran 12 tests", result.stderr)


if __name__ == "__main__":
    unittest.main()
