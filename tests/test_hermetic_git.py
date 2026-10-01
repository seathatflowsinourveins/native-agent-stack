"""The test package isolates git from the developer's global and system config (#179)."""

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import tests

ROOT = Path(__file__).resolve().parents[1]

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
        # Only the settings that stop git reading ~/.config/git/ignore and attributes by default,
        # and the one that stops writing commands from starting background maintenance.
        listing = subprocess.run(
            ["git", "config", "--show-scope", "--list", "--global"],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(listing.stdout.splitlines(), ["global\tcore.excludesfile=/dev/null",
                                                       "global\tcore.attributesfile=/dev/null",
                                                       "global\tmaintenance.auto=false"])
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

    def test_a_commit_in_a_scratch_repository_starts_no_maintenance(self):
        # Since Git 2.47 the maintenance git commit starts runs detached, and a scratch repository's
        # TemporaryDirectory cleanup can then race its objects/maintenance.lock (CI, git 2.55.0).
        environment = tests.hermetic_git_environment()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            subprocess.run(["git", "init", "-q", str(root / "repository")], env=environment, check=True)

            def commit(name, *config):
                """The git maintenance or gc child processes a commit starts, from its trace2 events."""
                (root / "repository" / name).write_text(name, encoding="utf-8")
                git = ["git", "-C", str(root / "repository"), "-c", "user.name=t", "-c", "user.email=t@example.invalid",
                       *config]
                subprocess.run([*git, "add", name], env=environment, check=True)
                trace = root / f"{name}.trace2.json"
                subprocess.run([*git, "commit", "-q", "-m", name], check=True,
                               env={**environment, "GIT_TRACE2_EVENT": str(trace)})
                events = [json.loads(line) for line in trace.read_text(encoding="utf-8").splitlines()]
                return [event["argv"][1:3] for event in events
                        if event.get("event") == "child_start" and event["argv"][1:2] in (["maintenance"], ["gc"])]

            hermetic = commit("hermetic")
            # Non-vacuous: with auto maintenance re-enabled, in the foreground, the trace records its child.
            enabled = commit("enabled", "-c", "maintenance.auto=true", "-c", "maintenance.autoDetach=false")
        self.assertEqual(hermetic, [])
        self.assertIn(["maintenance", "run"], enabled)

    @staticmethod
    def outer_repository(root):
        """A repository standing in for the one a git hook's GIT_DIR names, and the variables that select it."""
        outer = root / "outer"
        subprocess.run(["git", "init", "-q", str(outer)], env=tests.hermetic_git_environment(), check=True)
        return outer, {**tests.hermetic_git_environment(), "GIT_DIR": str(outer / ".git"),
                       "GIT_WORK_TREE": str(outer), "GIT_INDEX_FILE": str(outer / ".git" / "index")}

    @staticmethod
    def outer_state(outer):
        """(the outer repository's local config, whether it has any commit)."""
        environment = tests.hermetic_git_environment()
        config = subprocess.run(["git", "-C", str(outer), "config", "--local", "--list"], env=environment,
                                capture_output=True, text=True, check=True).stdout
        head = subprocess.run(["git", "-C", str(outer), "rev-parse", "--verify", "-q", "HEAD"], env=environment,
                              capture_output=True, text=True, check=False)
        return config, head.returncode == 0

    def test_importing_the_package_drops_inherited_variables_that_select_a_repository(self):
        # A scratch repository's git init and git config, in a process that imported this package.
        probe = ("import os, subprocess, sys, tempfile{imports}\n"
                 "scratch = tempfile.mkdtemp(dir=sys.argv[1])\n"
                 "subprocess.run(['git', 'init', '-q'], cwd=scratch, check=True)\n"
                 "subprocess.run(['git', 'config', 'core.hooksPath', '/probe'], cwd=scratch, check=True)\n"
                 "print(sorted(key for key in os.environ if key.startswith('GIT_')))\n")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            outer, environment = self.outer_repository(root)
            before = self.outer_state(outer)
            result = subprocess.run([sys.executable, "-c", probe.format(imports=", tests"), temporary], cwd=ROOT,
                                    env=environment, capture_output=True, text=True, check=True)
            after = self.outer_state(outer)
            # Non-vacuous: without the package, the same commands write into the outer repository.
            subprocess.run([sys.executable, "-c", probe.format(imports=""), temporary], cwd=ROOT,
                           env=environment, capture_output=True, text=True, check=True)
            exposed = self.outer_state(outer)
        self.assertEqual(result.stdout.strip(), str(sorted(tests.HERMETIC_GIT_ENVIRONMENT)))
        self.assertEqual(after, before)
        self.assertIn("core.hookspath=/probe", exposed[0])

    def test_the_pre_commit_gate_tests_leave_the_repository_a_hook_names_untouched(self):
        # Their setUp writes an absolute core.hooksPath, which an inherited GIT_DIR would send to that repository.
        with tempfile.TemporaryDirectory() as temporary:
            outer, environment = self.outer_repository(Path(temporary))
            before = self.outer_state(outer)
            subprocess.run([sys.executable, "-m", "unittest", "tests.test_pre_commit_gate"], cwd=ROOT,
                           env=environment, capture_output=True, text=True, check=False, timeout=600)
            after = self.outer_state(outer)
        self.assertEqual(after, before)
        self.assertNotIn("hookspath", after[0])

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
