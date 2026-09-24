#!/usr/bin/env python3
"""Fix round 3 synthetic test for dagu_common.codex_gate and codex_exec_processes (no model call).

Run: python3 test_codex_gate.py [-v]. GW2_DAGU_COMMON may point at another revision of
dagu_common.py (for example the pre-fix one) to show that the test detects the old behaviour.
"""

import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest

HELPER = Path(os.environ.get("GW2_DAGU_COMMON", Path(__file__).resolve().parent / "dagu_common.py"))
spec = importlib.util.spec_from_file_location("dagu_common_under_test", HELPER)
dc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dc)

SLEEPER = "import time; time.sleep(30)"


class CodexGateTest(unittest.TestCase):
    def setUp(self):
        self.original = dc.codex_exec_processes

    def tearDown(self):
        dc.codex_exec_processes = self.original

    def test_a_gate_does_not_release_while_two_others_run(self):
        dc.codex_exec_processes = lambda exclude=(): {101: "codex exec", 102: "codex exec"}
        timeout_class = getattr(dc, "CodexGateTimeout", None)
        self.assertIsNotNone(timeout_class, "helper has no CodexGateTimeout: it returns on timeout")
        with self.assertRaises(timeout_class) as caught:
            dc.codex_gate(max_wait=0.3, poll=0.05)
        self.assertEqual(caught.exception.observation["other_codex_exec_at_release"], 2)
        self.assertGreaterEqual(caught.exception.observation["waited_s"], 0.3)

    def test_b_gate_releases_immediately_with_one_other(self):
        dc.codex_exec_processes = lambda exclude=(): {101: "codex exec"}
        started = time.monotonic()
        observation = dc.codex_gate(max_wait=5, poll=0.05)
        self.assertLess(time.monotonic() - started, 1.0)
        self.assertEqual(observation["other_codex_exec_at_release"], 1)
        self.assertFalse(observation.get("released_by_timeout", False))

    def test_c_matcher_counts_global_options_and_alias_not_decoy(self):
        argvs = {"global-opts-exec": ["codex", "-c", SLEEPER, "-c", "k=v", "exec"],
                 "alias-e": ["codex", "-c", SLEEPER, "--profile", "p", "e"],
                 "decoy-login": ["codex", "-c", SLEEPER, "login"]}
        procs = {name: subprocess.Popen(argv, executable=sys.executable) for name, argv in argvs.items()}
        try:
            time.sleep(0.3)
            found = dc.codex_exec_processes()
            seen = {name: proc.pid in found for name, proc in procs.items()}
            print("matcher observation:", seen, file=sys.stderr)
            self.assertTrue(seen["global-opts-exec"], "`codex <global options> exec` not counted")
            self.assertTrue(seen["alias-e"], "`codex ... e` alias not counted")
            self.assertFalse(seen["decoy-login"], "`codex login` wrongly counted")
        finally:
            for proc in procs.values():
                proc.kill()
                proc.wait()


if __name__ == "__main__":
    print("helper under test:", HELPER, file=sys.stderr)
    unittest.main()
