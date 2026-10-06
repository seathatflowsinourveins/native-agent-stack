"""Source-ported sync helpers against local Git fixtures; no host or scheduler acceptance.

Every repository and the fake QMD executable are temporary. Git transports are
local filesystem paths; no production checkout, credential or service is used.
"""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
HELPERS = ROOT / "adoption/templates/dagu/helpers"


@unittest.skipUnless(shutil.which("git") and shutil.which("bash"), "native Git and Bash required")
class SyncFixtures(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="dagu-upkeep-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        self.environment.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
                                GIT_AUTHOR_NAME="Fixture", GIT_AUTHOR_EMAIL="fixture@example.invalid",
                                GIT_COMMITTER_NAME="Fixture", GIT_COMMITTER_EMAIL="fixture@example.invalid")
        self.origin = self.base / "origin.git"
        self.seed = self.base / "seed"
        self.git(self.base, "init", "--bare", "--initial-branch=main", str(self.origin))
        self.git(self.base, "init", "--initial-branch=main", str(self.seed))
        (self.seed / "tracked.txt").write_text("initial\n")
        self.git(self.seed, "add", "tracked.txt")
        self.git(self.seed, "commit", "-m", "fixture initial")
        self.git(self.seed, "remote", "add", "origin", str(self.origin))
        self.git(self.seed, "push", "origin", "main")
        self.copy = self.base / "working copy"
        self.git(self.base, "clone", str(self.origin), str(self.copy))
        self.initial = self.head(self.copy)
        self.qmd_record = self.base / "qmd-arguments.txt"
        self.qmd = self.base / "fixture-qmd"
        self.qmd.write_text('#!/bin/bash\nprintf "%s\\n" "$@" > "$QMD_RECORD"\nexit "${QMD_EXIT:-0}"\n')
        self.qmd.chmod(0o700)
        self.environment["QMD_RECORD"] = str(self.qmd_record)

    def git(self, directory, *arguments, check=True):
        return subprocess.run(["git", "-C", str(directory), *arguments], env=self.environment,
                              capture_output=True, text=True, check=check, timeout=20)

    def head(self, directory):
        return self.git(directory, "rev-parse", "HEAD").stdout.strip()

    def upstream_change(self):
        (self.seed / "tracked.txt").write_text("upstream changed\n")
        self.git(self.seed, "add", "tracked.txt")
        self.git(self.seed, "commit", "-m", "fixture upstream")
        self.git(self.seed, "push", "origin", "main")
        return self.head(self.seed)

    def helper(self, name, directory=None):
        args = ["bash", str(HELPERS / name), str(directory or self.copy)]
        if name == "live-clone-sync.sh":
            args.append(str(self.qmd))
        return subprocess.run(args, env=self.environment, capture_output=True, text=True, timeout=20)

    def test_main_pin_detaches_to_fetched_main(self):
        expected = self.upstream_change()
        result = self.helper("main-pin.sh")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.head(self.copy), expected)
        self.assertNotEqual(self.git(self.copy, "symbolic-ref", "-q", "HEAD", check=False).returncode, 0)

    def test_main_pin_leaves_tracked_work_intact(self):
        self.upstream_change()
        (self.copy / "tracked.txt").write_text("owned work\n")
        result = self.helper("main-pin.sh")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.head(self.copy), self.initial)
        self.assertEqual((self.copy / "tracked.txt").read_text(), "owned work\n")
        self.assertIn("HEAD left", result.stdout)

    def test_main_pin_preserves_unpushed_branch(self):
        self.git(self.copy, "checkout", "-b", "owned-work")
        (self.copy / "owned.txt").write_text("unpublished work\n")
        self.git(self.copy, "add", "owned.txt")
        self.git(self.copy, "commit", "-m", "fixture unpushed")
        owned_commit = self.head(self.copy)
        expected = self.upstream_change()
        result = self.helper("main-pin.sh")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.head(self.copy), expected)
        self.assertEqual(self.git(self.copy, "rev-parse", "owned-work").stdout.strip(), owned_commit)

    def test_live_clone_detaches_then_updates_only_the_scoped_text_index(self):
        expected = self.upstream_change()
        result = self.helper("live-clone-sync.sh")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.head(self.copy), expected)
        self.assertEqual(self.qmd_record.read_text().splitlines(),
                         ["--index", "native-agent-stack-catalog", "update"])
        self.assertIn("qmd-index-updated", result.stdout)

    def test_live_clone_refuses_tracked_and_untracked_work(self):
        self.upstream_change()
        for path in ("tracked.txt", "untracked.txt"):
            with self.subTest(path=path):
                target = self.copy / path
                target.write_text("owned work\n")
                result = self.helper("live-clone-sync.sh")
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.head(self.copy), self.initial)
                self.assertEqual(target.read_text(), "owned work\n")
                self.assertFalse(self.qmd_record.exists())
                if path == "tracked.txt":
                    self.git(self.copy, "checkout", "--", path)
                else:
                    target.unlink()

    def test_failed_fetch_does_not_move_or_index(self):
        self.git(self.copy, "remote", "set-url", "origin", str(self.base / "missing.git"))
        result = self.helper("live-clone-sync.sh")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.head(self.copy), self.initial)
        self.assertFalse(self.qmd_record.exists())

    def test_failed_qmd_is_not_a_successful_sync(self):
        self.environment["QMD_EXIT"] = "9"
        result = self.helper("live-clone-sync.sh")
        self.assertEqual(result.returncode, 9)
        self.assertNotIn("qmd-index-updated", result.stdout)

    def test_unreadable_git_status_is_not_treated_as_clean(self):
        outside = self.base / "not-a-checkout"
        outside.mkdir()
        result = self.helper("live-clone-sync.sh", outside)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.qmd_record.exists())


class HeavyWindowBoundaries(unittest.TestCase):
    def check_window(self, now, duration):
        return subprocess.run(['bash', str(HELPERS / 'heavy-window-check.sh'), str(duration), str(now)],
                              capture_output=True, text=True, timeout=5).returncode

    def test_full_phase_bound_defers_before_and_inside_each_corrected_window(self):
        for start, end in ((1791282900, 1791294300), (1791316200, 1791331800)):
            for now, duration, expected in ((start - 360, 360, 0), (start - 359, 360, 1),
                                            (start, 360, 1), (end - 1, 360, 1), (end, 360, 0)):
                with self.subTest(start=start, now=now):
                    self.assertEqual(self.check_window(now, duration), expected)

    def test_next_day_boundary_and_upkeep_duration_are_checked(self):
        self.assertEqual(self.check_window(1791282900 - 2880, 2880), 0)
        self.assertEqual(self.check_window(1791282900 - 2879, 2880), 1)
        self.assertEqual(self.check_window(1791331800 - 1, 2880), 1)
        self.assertEqual(self.check_window(1791331800, 2880), 0)

    def test_bad_inputs_fail_and_decimal_leading_zero_is_supported(self):
        for now, duration in (('not-time', 360), (1791282900, 'bad'), (1791282900, 86401)):
            with self.subTest(now=now, duration=duration):
                self.assertEqual(self.check_window(now, duration), 2)
        self.assertEqual(self.check_window('01791331800', '00360'), 0)


if __name__ == "__main__":
    unittest.main()
