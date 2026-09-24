"""The test package isolates git from the developer's global and system config (#179)."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import tests


class HermeticGitTests(unittest.TestCase):
    def test_environment_points_git_at_an_empty_global_file_and_no_system_file(self):
        self.assertEqual(os.environ.get("GIT_CONFIG_NOSYSTEM"), "1")
        path = Path(os.environ["GIT_CONFIG_GLOBAL"])
        self.assertEqual(path, Path(tests.HERMETIC_GIT_CONFIG))
        self.assertTrue(path.is_file())
        self.assertEqual(path.read_text(encoding="utf-8"), "")

    def test_no_global_or_system_setting_is_visible(self):
        listing = subprocess.run(
            ["git", "config", "--show-scope", "--list", "--global"],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(listing.stdout.strip(), "")
        hooks = subprocess.run(
            ["git", "config", "--get", "core.hooksPath"],
            capture_output=True, text=True, check=False, cwd=tempfile.gettempdir(),
        )
        self.assertEqual(hooks.stdout.strip(), "")

    def test_a_hostile_home_config_cannot_block_scratch_commits(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            hooks = root / "hooks"
            hooks.mkdir()
            blocker = hooks / "pre-commit"
            blocker.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
            blocker.chmod(0o755)
            home = root / "home"
            (home / ".config" / "git").mkdir(parents=True)
            (home / ".gitconfig").write_text(f"[core]\n\thooksPath = {hooks}\n", encoding="utf-8")
            (home / ".config" / "git" / "config").write_text(
                f"[core]\n\thooksPath = {hooks}\n", encoding="utf-8")
            repo = root / "repo"
            repo.mkdir()
            env = {**os.environ, "HOME": str(home), "XDG_CONFIG_HOME": str(home / ".config")}
            git = ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid"]
            subprocess.run(["git", "init", "-q"], cwd=repo, env=env, check=True)
            (repo / "file.txt").write_text("scratch\n", encoding="utf-8")
            subprocess.run([*git, "add", "file.txt"], cwd=repo, env=env, check=True)
            commit = subprocess.run([*git, "commit", "-q", "-m", "scratch"], cwd=repo, env=env,
                                    capture_output=True, text=True, check=False)
            self.assertEqual(commit.returncode, 0, commit.stderr)


if __name__ == "__main__":
    unittest.main()
