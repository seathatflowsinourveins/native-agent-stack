"""Synthetic command and filesystem controls; no real sampling or cache prune."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/maintenance/disk-headroom-guard.sh"


class DiskHeadroomGuardTests(unittest.TestCase):
    def run_guard(self, free="80", df_exit=0, uv_exit=0, broken_csv=False, state_symlink=False, fifo=None,
                  ps_exit=0, ps_match=True, lock_busy=False):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary = root / "bin"
            binary.mkdir()
            state = root / "state"
            state.mkdir(mode=0o700)
            if broken_csv:
                (state / "disk-headroom.csv").mkdir()
            fifo_path = state / fifo if fifo else None
            if fifo_path:
                os.mkfifo(fifo_path, 0o600)
                fifo_before = fifo_path.lstat()
            if state_symlink:
                alias = root / "state-alias"
                alias.symlink_to(state, target_is_directory=True)
                configured_state = alias
            else:
                configured_state = state
            capture = root / "calls.jsonl"
            stub = (
                "#!/usr/bin/env python3\n"
                "import json,os,sys\nfrom pathlib import Path\n"
                "name=Path(sys.argv[0]).name\n"
                "with open(os.environ['FIXTURE_CALLS'],'a') as f: f.write(json.dumps({'name':name,'argv':sys.argv[1:]})+'\\n')\n"
                "if name=='df':\n print('Avail\\n'+os.environ['FIXTURE_FREE']); sys.exit(int(os.environ['FIXTURE_DF_EXIT']))\n"
                "if name=='date': print('2026-10-06T04:30:00Z')\n"
                "if name=='ps':\n print('PID ELAPSED COMMAND\\n123 456 '+('uv' if os.environ['FIXTURE_PS_MATCH']=='1' else 'python')); sys.exit(int(os.environ['FIXTURE_PS_EXIT']))\n"
                "if name=='uv':\n"
                " if os.environ['FIXTURE_LOCK_BUSY']=='1': print('Cache is currently in-use, waiting for other uv processes to finish\\nerror: Timeout (10s) when waiting for lock on cache',file=sys.stderr)\n"
                " sys.exit(int(os.environ['FIXTURE_UV_EXIT']))\n"
            )
            for name in ("df", "date", "ps", "uv"):
                path = binary / name
                path.write_text(stub)
                path.chmod(0o755)
            env = {"PATH": str(binary) + os.pathsep + os.environ["PATH"], "HOME": os.environ["HOME"],
                   "NATIVE_DISK_GUARD_STATE_DIR": str(configured_state), "FIXTURE_CALLS": str(capture),
                   "FIXTURE_FREE": free, "FIXTURE_DF_EXIT": str(df_exit), "FIXTURE_UV_EXIT": str(uv_exit),
                   "FIXTURE_PS_EXIT": str(ps_exit), "FIXTURE_PS_MATCH": '1' if ps_match else '0',
                   "FIXTURE_LOCK_BUSY": '1' if lock_busy else '0'}
            result = subprocess.run(["bash", str(SCRIPT)], env=env, capture_output=True, text=True, timeout=15)
            calls = [json.loads(line) for line in capture.read_text().splitlines()]
            if fifo_path:
                after = fifo_path.lstat()
                self.assertEqual((after.st_ino, after.st_mode, after.st_mtime_ns),
                                 (fifo_before.st_ino, fifo_before.st_mode, fifo_before.st_mtime_ns))
            csv = state / "disk-headroom.csv"
            alert = state / "ALERT-disk-headroom.log"
            return result, calls, csv.read_text() if csv.is_file() else None, alert.read_text() if alert.is_file() else None

    def test_recorded_threshold_boundaries_and_only_upstream_cache_prune(self):
        for free, alerts, prune in (("80", False, False), ("60", False, False),
                                    ("59", True, False), ("30", True, False), ("29", True, True),
                                    ("08", True, True)):
            with self.subTest(free=free):
                result, calls, csv, alert = self.run_guard(free)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("utc,free_gib\n2026-10-06T04:30:00Z," + free, csv)
                self.assertEqual(alert is not None, alerts)
                pruning = [c["argv"] for c in calls if c["name"] == "uv"]
                self.assertEqual(pruning, [["cache", "prune"]] if prune else [])
                for call in calls:
                    if call["name"] == "ps":
                        self.assertEqual(call["argv"], ["-eo", "pid,etimes,comm", "--sort=-etimes"])
                        self.assertNotIn("args", " ".join(call["argv"]))

    def test_failed_or_malformed_sample_fails_closed_without_pruning(self):
        for value, code in (("29", 1), ("", 0), ("not-a-number", 0), ("error123", 0)):
            with self.subTest(value=value, code=code):
                result, calls, csv, alert = self.run_guard(value, df_exit=code)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse([c for c in calls if c["name"] == "uv"])
                self.assertIsNone(csv)
                self.assertIsNone(alert)

    def test_prune_failure_is_not_reported_as_success(self):
        result, calls, csv, alert = self.run_guard("29", uv_exit=1)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("uv cache prune ran", alert)

    def test_cache_lock_timeout_is_distinct_and_never_forced(self):
        result, calls, csv, alert = self.run_guard("29", uv_exit=1, lock_busy=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("uv cache in use", result.stderr)
        self.assertIn("safe prune deferred after lock timeout", alert)
        self.assertEqual([c["argv"] for c in calls if c["name"] == "uv"], [["cache", "prune"]])

    def test_no_matching_process_is_distinct_from_a_failed_lookup(self):
        result, calls, csv, alert = self.run_guard("59", ps_match=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("candidates: none", alert)
        result, calls, csv, alert = self.run_guard("59", ps_exit=1)
        self.assertIn("candidates: unavailable", alert)

    def test_log_failure_does_not_prevent_low_space_mitigation(self):
        result, calls, csv, alert = self.run_guard("29", broken_csv=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual([c["argv"] for c in calls if c["name"] == "uv"], [["cache", "prune"]])

    def test_symlinked_state_is_not_written(self):
        result, calls, csv, alert = self.run_guard("80", state_symlink=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIsNone(csv)
        self.assertIsNone(alert)

    def test_fifo_logs_are_preserved_without_blocking_low_space_mitigation(self):
        for fifo in ("disk-headroom.csv", "ALERT-disk-headroom.log"):
            with self.subTest(fifo=fifo):
                result, calls, csv, alert = self.run_guard("29", fifo=fifo)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual([c["argv"] for c in calls if c["name"] == "uv"], [["cache", "prune"]])


if __name__ == "__main__":
    unittest.main()
