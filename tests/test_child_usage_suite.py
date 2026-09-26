"""Runs examples/claude-native/workflows/test-child-usage.mjs, the synthetic-row suite of
child-usage.mjs (usage accounting and the per-child lanes object), so `python3 -m unittest` and the
CI step that runs it exercise that script. No provider call; not native evidence."""
from __future__ import annotations

import re
import shutil
import subprocess
import unittest
from pathlib import Path

SUITE = Path(__file__).resolve().parents[1] / "examples" / "claude-native" / "workflows" / "test-child-usage.mjs"


class ChildUsageNodeSuite(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "node is not installed")
    def test_node_suite_passes(self):
        result = subprocess.run(["node", str(SUITE)], cwd=SUITE.parent, capture_output=True, text=True,
                                timeout=300, check=False)
        self.assertEqual(result.returncode, 0, result.stdout[-4000:] + result.stderr[-2000:])
        summary = re.search(r"^SUMMARY passed=(\d+) failed=(\d+) total=(\d+)$", result.stdout, re.M)
        self.assertIsNotNone(summary, result.stdout[-2000:])
        self.assertEqual(summary.group(2), "0")
        self.assertGreater(int(summary.group(1)), 0)


if __name__ == "__main__":
    unittest.main()
