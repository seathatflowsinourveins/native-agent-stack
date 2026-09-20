"""Post-review supervisor hardening checks; never starts a native client."""
import io
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import run as supervisor


class ClaudeSupervisorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.repo = self.root / "repo"
        self.source = self.repo / "deep/source"
        self.source.mkdir(parents=True)
        subprocess.run(["git", "init", "--quiet", str(self.repo)], check=True)

    def test_private_logs_elsewhere_in_repository_are_refused(self):
        with self.assertRaisesRegex(ValueError, "outside_source_repository"):
            supervisor.private_directory(self.repo / "other/logs", self.source)

    def test_outside_repository_is_accepted(self):
        self.assertEqual(supervisor.private_directory(self.root / "private", self.source),
                         self.root / "private")

    def test_symlink_back_into_repository_is_refused(self):
        (self.root / "alias").symlink_to(self.repo, target_is_directory=True)
        with self.assertRaises(ValueError):
            supervisor.private_directory(self.root / "alias/logs", self.source)

    def test_standalone_copied_source_still_protects_its_own_directory(self):
        source = self.root / "copied"
        source.mkdir()
        with self.assertRaises(ValueError):
            supervisor.private_directory(source / "logs", source)
        self.assertEqual(supervisor.private_directory(self.root / "private", source),
                         self.root / "private")

    def test_cleanup_race_is_recorded_and_receipt_can_be_written(self):
        def fail():
            raise ProcessLookupError("synthetic cleanup race")
        client = SimpleNamespace(label="initial", out=io.StringIO(), close=fail)
        cleanup = {"cli_cleanup_escalations": []}
        with patch.object(supervisor, "wait_alive", side_effect=PermissionError("synthetic")):
            supervisor.cleanup_owned([client], {"pid": 1, "start_ticks": "1"}, self.root, cleanup)
        self.assertEqual([x["type"] for x in cleanup["errors"]],
                         ["ProcessLookupError", "PermissionError"])
        self.assertFalse(cleanup["wait_stopped"])
        path = self.root / "receipt.json"
        supervisor.write(path, {"status": "failed", "cleanup": cleanup})
        self.assertEqual(json.loads(path.read_text())["status"], "failed")


if __name__ == "__main__":
    unittest.main()
