"""The test package isolates git from the developer's global and system config (#179)."""

import contextlib
import io
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import tests

# Every hook that git add, status, commit, checkout or worktree add can run in a scratch repository.
HOOKS = ("pre-commit", "prepare-commit-msg", "commit-msg", "post-commit", "post-checkout",
         "post-index-change", "reference-transaction")


@contextlib.contextmanager
def hostile_home():
    """HOME and XDG_CONFIG_HOME whose git config points core.hooksPath at hooks that all exit 1, and
    whose default ignore and attributes files match every path."""
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        hooks = root / "hooks"
        hooks.mkdir()
        for name in HOOKS:
            blocker = hooks / name
            blocker.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
            blocker.chmod(0o755)
        home = root / "home"
        xdg = home / ".config" / "git"
        xdg.mkdir(parents=True)
        for config in (home / ".gitconfig", xdg / "config"):
            config.write_text(f"[core]\n\thooksPath = {hooks}\n", encoding="utf-8")
        (xdg / "ignore").write_text("*\n", encoding="utf-8")
        (xdg / "attributes").write_text("* hostile\n", encoding="utf-8")
        with mock.patch.dict(os.environ, {"HOME": str(home), "XDG_CONFIG_HOME": str(home / ".config")}):
            yield root


class HermeticGitTests(unittest.TestCase):
    def test_environment_points_git_at_the_hermetic_global_file_and_no_system_file(self):
        self.assertEqual(os.environ.get("GIT_CONFIG_NOSYSTEM"), "1")
        path = Path(os.environ["GIT_CONFIG_GLOBAL"])
        self.assertEqual(path, Path(tests.HERMETIC_GIT_CONFIG))
        self.assertTrue(path.is_file())
        self.assertEqual(path.read_text(encoding="utf-8"), tests.HERMETIC_GIT_SETTINGS)

    def test_no_global_or_system_setting_is_visible(self):
        # Only the settings that stop git reading ~/.config/git/ignore and attributes by default.
        listing = subprocess.run(
            ["git", "config", "--show-scope", "--list", "--global"],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(listing.stdout.splitlines(), ["global\tcore.excludesfile=/dev/null",
                                                       "global\tcore.attributesfile=/dev/null"])
        hooks = subprocess.run(
            ["git", "config", "--get", "core.hooksPath"],
            capture_output=True, text=True, check=False, cwd=tempfile.gettempdir(),
        )
        self.assertEqual(hooks.stdout.strip(), "")

    def test_a_stripped_environment_keeps_the_hermetic_configuration(self):
        with mock.patch.dict(os.environ, {"GIT_DIR": "/elsewhere/.git", "GIT_INDEX_FILE": "/elsewhere/index"}):
            environment = tests.hermetic_git_environment()
        self.assertEqual({key: value for key, value in environment.items() if key.startswith("GIT_")},
                         tests.HERMETIC_GIT_ENVIRONMENT)

    @staticmethod
    def scratch(root, environment):
        """(git status, git check-attr --all, whether a commit succeeded) in a new repository."""
        repository = Path(tempfile.mkdtemp(dir=root))
        subprocess.run(["git", "-C", str(repository), "init", "-q"], env=tests.hermetic_git_environment(), check=True)
        (repository / "file.txt").write_text("scratch\n", encoding="utf-8")
        git = ["git", "-C", str(repository), "-c", "user.name=t", "-c", "user.email=t@example.invalid"]

        def run(*args):
            return subprocess.run([*git, *args], env=environment, capture_output=True, text=True, check=False)

        status, attributes = run("status", "--porcelain").stdout, run("check-attr", "--all", "--", "file.txt").stdout
        run("add", "--force", "file.txt")
        return status, attributes, run("commit", "-q", "-m", "scratch").returncode == 0

    def test_a_hostile_home_config_cannot_reach_scratch_repositories(self):
        with hostile_home() as root:
            hermetic = self.scratch(root, tests.hermetic_git_environment())
            # Non-vacuous: a git that reads the hostile HOME ignores the file, sets the attribute and cannot commit.
            stripped = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
            exposed = self.scratch(root, stripped)
        self.assertEqual(hermetic, ("?? file.txt\n", "", True))
        self.assertEqual(exposed, ("", "file.txt: hostile: set\n", False))

    def run_in_hostile_home(self, case):
        result = unittest.TestResult()
        with hostile_home(), contextlib.redirect_stdout(io.StringIO()):
            case.run(result)
        self.assertEqual((result.testsRun, result.skipped), (1, []))
        if result.errors or result.failures:
            self.fail("".join(trace for _case, trace in result.errors + result.failures))

    def test_the_verdict_review_gate_fixture_and_head_worktree_ignore_a_hostile_home(self):
        # GateFixture.git and the gate's own git calls drop inherited GIT_* variables: the fixture's commits
        # must run no pre-commit hook and the gate's head worktree no post-checkout hook.
        from tests import test_verdict_review_gate
        self.run_in_hostile_home(test_verdict_review_gate.NoChangeAndGrandfatheredTests(
            "test_head_revision_is_checked_in_a_temporary_worktree"))

    def test_the_claude_lane_checkout_check_ignores_a_hostile_home(self):
        # claude_lane.py runs git status with the inherited environment: a default ignore file (a managed
        # host's lists .claude/settings.local.json) must not hide local settings from the BIND-R4-8 check.
        from tests import test_claude_lane
        self.run_in_hostile_home(test_claude_lane.ClaudeLaneWriterTests(
            "test_the_agentlab_checkout_must_be_clean_tracked_and_at_the_vendored_commit"))


if __name__ == "__main__":
    unittest.main()
