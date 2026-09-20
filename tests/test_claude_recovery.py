"""Include the portable Claude recovery guard suite in ordinary offline CI."""
from pathlib import Path
import subprocess
import sys
import unittest

from scripts.validate_convergence import validate_record


class ClaudeRecoveryOfflineSuite(unittest.TestCase):
    def test_portable_fixture_and_runner_guards(self):
        root = Path(__file__).resolve().parents[1]
        suite = root / "blueprints/convergence-practice/native-recovery/claude"
        result = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", str(suite),
             "-p", "test_*.py"],
            cwd=root, text=True, capture_output=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_published_recovery_and_gpu_contracts(self):
        root = Path(__file__).resolve().parents[1]
        for path in (
            "job-recovery/experiment-macos.json",
            "job-recovery/experiment-wsl.json",
            "native-recovery/experiment.json",
            "native-recovery/claude/experiment.json",
            "gpu-inference/experiment.json",
        ):
            with self.subTest(path=path):
                result = validate_record(root, "blueprints/convergence-practice/" + path)
                self.assertTrue(result["valid"], result["errors"])


if __name__ == "__main__":
    unittest.main()
