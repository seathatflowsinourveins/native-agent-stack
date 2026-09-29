"""Tracked pre-push registry gate (scripts/git-hooks/pre-push).

Local integration class: a temporary clone that borrows this checkout's objects
(`git clone --shared --no-checkout`, so nothing is copied), this checkout's HEAD
commit, commits built on it with plumbing (a synthetic unlisted lockfile, or a
registry test forced onto its skip or expected-failure path), and the zizmor
binary already on PATH. Most tests run the hook directly with the stdin lines
git would give it (githooks(5), pre-push). One pushes natively from a linked
worktree, where git exports GIT_DIR to the hook, to a bare clone that shares
this checkout's objects.

Every hook run sets GIT_CEILING_DIRECTORIES (git(1)) to the parent of its
temporary root. Git's discovery, and the hook's inside-a-repository guard with
it, then never looks above that root, so the result does not depend on what the
host keeps there (on this project's WSL host, an empty /tmp/.git while Codex
sandboxes run). Skips when zizmor is absent, except for the cases that run no
registry test.
"""

from pathlib import Path
import os
import re
import shutil
import signal
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "scripts/git-hooks/pre-push"
ZIZMOR = shutil.which("zizmor")
# A root-level name that TRACKED in tests/test_osv_lockfile_coverage.py matches and no inventory lists.
PROBE = "requirements-pre-push-probe.txt"
PROBE_TEXT = "# synthetic lockfile for the pre-push gate test\n"
LOCKFILE_TEST = "tests/test_osv_lockfile_coverage.py"
LS_FILES_ARGV = '["git", "-C", str(ROOT), "ls-files", "-z"]'
LOCKFILE_METHOD = "    def test_every_tracked_lockfile_and_manifest_is_listed(self):\n"
# The hook's three test methods, as (module, class, method).
REGISTRY_TESTS = (
    ("test_osv_lockfile_coverage", "LockfileInventoryTests", "test_every_tracked_lockfile_and_manifest_is_listed"),
    ("test_blind_checkout", "RepositoryClassificationTests",
     "test_every_blueprint_value_under_a_label_key_is_classified"),
    ("test_workflow_security_coverage", "NewWorkflowSecurityCoverageTests",
     "test_all_published_workflows_are_listed_and_covered"),
)
# Each trapped signal and the status the hook exits with once it has cleaned up (128 plus the signal number).
SIGNAL_STATUS = (("SIGHUP", 129), ("SIGINT", 130), ("SIGQUIT", 131), ("SIGTERM", 143))
TREE_LINE = re.compile(r"^pre-push: running the registry tests on [0-9a-f]+ in (\S+)/tree$", re.M)


class PrePushGateTests(unittest.TestCase):
    def setUp(self):
        if not (ROOT / ".git").exists():
            self.skipTest("not a Git checkout")
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        # The hook's own TMPDIR, so that every run can show it removed its scratch worktree.
        self.hook_tmp = self.root / "hook-tmp"
        self.hook_tmp.mkdir()
        self.repo = self.root / "repo"
        self.head = self.checked(["git", "-C", str(ROOT), "rev-parse", "HEAD"])
        self.checked(["git", "clone", "-q", "--shared", "--no-checkout", str(ROOT), str(self.repo)])
        self.zero = "0" * len(self.head)
        self.main = f"refs/heads/main {self.head} refs/heads/main {self.zero}"

    def checked(self, argv, env=None, input=None, strip=True):
        result = subprocess.run(argv, cwd=self.root, capture_output=True, text=True, env=env, input=input,
                                timeout=120)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip() if strip else result.stdout

    def git(self, *args, env=None, input=None, strip=True):
        return self.checked(["git", "-C", str(self.repo), "-c", "user.email=t@example.invalid", "-c", "user.name=t",
                             *args], env=env, input=input, strip=strip)

    def commit_on_head(self, files):
        """A commit on HEAD that adds or replaces these {path: text} files, built with plumbing in a scratch index."""
        index = {**os.environ, "GIT_INDEX_FILE": str(self.root / "index")}
        self.git("read-tree", self.head, env=index)
        for path, text in files.items():
            blob = self.git("hash-object", "-w", "--stdin", input=text)
            self.git("update-index", "--add", "--cacheinfo", f"100644,{blob},{path}", env=index)
        tree = self.git("write-tree", env=index)
        return self.git("commit-tree", tree, "-p", self.head, "-m", f"probe: {', '.join(files)}")

    def environment(self, tmpdir=None, path=None, **extra):
        """The hook's environment: its TMPDIR, with git's discovery stopping above the temporary root."""
        environment = {**os.environ, "TMPDIR": str(tmpdir or self.hook_tmp),
                       "GIT_CEILING_DIRECTORIES": str(self.root.resolve().parent), **extra}
        if path is not None:
            environment["PATH"] = path
        return environment

    def push(self, *lines, raw=None, **environment):
        """The hook run as git runs it for these "<local ref> <local oid> <remote ref> <remote oid>" lines."""
        return subprocess.run([str(HOOK), "origin", "origin"], cwd=self.repo, capture_output=True, text=True,
                              input="".join(f"{line}\n" for line in lines) if raw is None else raw,
                              env=self.environment(**environment), timeout=300)

    def without_zizmor(self):
        """A PATH that has git but no zizmor."""
        path = f"{os.path.dirname(shutil.which('git'))}:/usr/bin:/bin"
        if any(Path(d, "zizmor").exists() for d in path.split(":")):
            self.skipTest("zizmor shares a directory with git")
        return path

    def assert_nothing_left(self, *tmpdirs, worktrees=1):
        """The hook removed its scratch directory and unregistered its worktree, whatever the outcome."""
        for tmpdir in (self.hook_tmp, *tmpdirs):
            self.assertEqual(list(tmpdir.iterdir()), [])
        listing = self.git("worktree", "list", "--porcelain").splitlines()
        self.assertEqual(len([line for line in listing if line.startswith("worktree ")]), worktrees, listing)

    def test_hook_is_executable(self):
        self.assertTrue(os.access(HOOK, os.X_OK))

    def test_missing_zizmor_fails_closed(self):
        result = self.push(self.main, path=self.without_zizmor())
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("zizmor not on PATH", result.stderr)
        self.assert_nothing_left()

    def test_deletion_is_not_tested_and_needs_no_zizmor(self):
        # Non-vacuous: an all-zero oid that reached the zizmor check or `git rev-parse` would refuse the push.
        result = self.push(f"(delete) {self.zero} refs/heads/gone {self.head}", path=self.without_zizmor())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assert_nothing_left()

    @unittest.skipUnless(ZIZMOR, "zizmor not on PATH")
    def test_clean_push_passes_and_tests_each_commit_once(self):
        result = self.push(self.main, f"refs/heads/copy {self.head} refs/heads/copy {self.zero}")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr.count(f"pre-push: running the registry tests on {self.head}"), 1)
        self.assertIn("Ran 3 tests", result.stderr)
        self.assertNotIn("skipped", result.stderr)
        self.assert_nothing_left()

    @unittest.skipUnless(ZIZMOR, "zizmor not on PATH")
    def test_a_last_line_without_a_newline_is_tested(self):
        result = self.push(raw=self.main)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"pre-push: running the registry tests on {self.head}", result.stderr)
        self.assertIn("Ran 3 tests", result.stderr)
        self.assert_nothing_left()

    @unittest.skipUnless(ZIZMOR, "zizmor not on PATH")
    def test_unset_tmpdir_defaults_to_var_tmp(self):
        # file-hierarchy(7) puts larger temporary files in /var/tmp. The ceiling keeps git's discovery out of the host's
        # /var/tmp itself.
        environment = self.environment(GIT_CEILING_DIRECTORIES="/var/tmp")
        del environment["TMPDIR"]
        result = subprocess.run([str(HOOK), "origin", "origin"], cwd=self.repo, capture_output=True, text=True,
                                input=f"{self.main}\n", env=environment, timeout=300)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Ran 3 tests", result.stderr)
        scratch = TREE_LINE.findall(result.stderr)
        self.assertEqual(len(scratch), 1, result.stderr)
        self.assertTrue(scratch[0].startswith("/var/tmp/pre-push."), scratch)
        self.assertFalse(os.path.lexists(scratch[0]))
        self.assert_nothing_left()

    @unittest.skipUnless(ZIZMOR, "zizmor not on PATH")
    def test_unlisted_lockfile_is_refused(self):
        commit = self.commit_on_head({PROBE: PROBE_TEXT})
        result = self.push(f"refs/heads/probe {commit} refs/heads/probe {self.zero}")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("add these to .github/osv-scanner-lockfiles.json", result.stderr)
        self.assertIn(PROBE, result.stderr)
        self.assertIn("Push refused", result.stderr)
        self.assert_nothing_left()

    @unittest.skipUnless(ZIZMOR, "zizmor not on PATH")
    def test_one_refused_commit_refuses_the_whole_push(self):
        # The refused commit comes first, so a status that the passing commit overwrote would let the push through.
        commit = self.commit_on_head({PROBE: PROBE_TEXT})
        result = self.push(f"refs/heads/probe {commit} refs/heads/probe {self.zero}", self.main)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(f"pre-push: running the registry tests on {commit}", result.stderr)
        self.assertIn(f"pre-push: running the registry tests on {self.head}", result.stderr)
        self.assertEqual(result.stderr.count("Push refused"), 1)
        self.assert_nothing_left()

    @unittest.skipUnless(ZIZMOR, "zizmor not on PATH")
    def test_a_skipped_registry_test_is_refused(self):
        # The lockfile test skips when `git ls-files` cannot run; a pushed commit that forces that path must not pass.
        source = self.git("show", f"{self.head}:{LOCKFILE_TEST}", strip=False)
        self.assertEqual(source.count(LS_FILES_ARGV), 1, "tracked_files() changed; update this fixture")
        commit = self.commit_on_head({LOCKFILE_TEST: source.replace(LS_FILES_ARGV, '["git-absent-pre-push-probe"]')})
        result = self.push(f"refs/heads/probe {commit} refs/heads/probe {self.zero}")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("skipped 'not a Git checkout", result.stderr)
        self.assertIn("Push refused", result.stderr)
        self.assert_nothing_left()

    @unittest.skipUnless(ZIZMOR, "zizmor not on PATH")
    def test_an_expected_failure_is_refused(self):
        # The unlisted lockfile fails the lockfile test; marked as an expected failure, that run would be a success.
        source = self.git("show", f"{self.head}:{LOCKFILE_TEST}", strip=False)
        self.assertEqual(source.count(LOCKFILE_METHOD), 1, "the lockfile test changed; update this fixture")
        marked = source.replace(LOCKFILE_METHOD, "    @unittest.expectedFailure\n" + LOCKFILE_METHOD)
        commit = self.commit_on_head({PROBE: PROBE_TEXT, LOCKFILE_TEST: marked})
        result = self.push(f"refs/heads/probe {commit} refs/heads/probe {self.zero}")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("expected failure", result.stderr)
        self.assertIn("Push refused", result.stderr)
        self.assert_nothing_left()

    @unittest.skipUnless(ZIZMOR, "zizmor not on PATH")
    def test_temporary_directory_inside_a_repository_is_refused(self):
        inside = self.repo / "scratch"
        inside.mkdir()
        result = self.push(self.main, tmpdir=inside)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(f"is inside the git repository {os.path.realpath(self.repo / '.git')};", result.stderr)
        self.assertEqual(list(inside.iterdir()), [])
        self.assert_nothing_left()

    @unittest.skipUnless(ZIZMOR, "zizmor not on PATH")
    def test_an_empty_git_directory_is_not_a_repository(self):
        # A sandbox can leave an empty .git mount point in /tmp (Codex's bubblewrap does on this project's WSL host).
        # Git's discovery passes over it, and so does the guard.
        sandbox = self.root / "sandbox"
        (sandbox / ".git").mkdir(parents=True)
        (sandbox / "tmp").mkdir()
        result = self.push(self.main, tmpdir=sandbox / "tmp")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Ran 3 tests", result.stderr)
        self.assert_nothing_left(sandbox / "tmp")

    @unittest.skipUnless(ZIZMOR, "zizmor not on PATH")
    def test_the_scratch_checkout_runs_no_hook(self):
        # `git worktree add` runs post-checkout (githooks(5)); the hook gives it core.hooksPath=/dev/null.
        hooks = self.root / "hooks"
        hooks.mkdir()
        marker = self.root / "post-checkout-ran"
        (hooks / "post-checkout").write_text(f"#!/bin/sh\n: > '{marker}'\n", encoding="utf-8")
        (hooks / "post-checkout").chmod(0o755)
        self.git("config", "core.hooksPath", str(hooks))
        result = self.push(self.main)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(marker.exists())
        self.assert_nothing_left()

    @unittest.skipUnless(ZIZMOR, "zizmor not on PATH")
    def test_pythonsafepath_cannot_swap_in_another_checkouts_tests(self):
        # Under PYTHONSAFEPATH, `python3 -c` leaves the working directory off sys.path, so a PYTHONPATH naming another
        # checkout would supply the tests. This decoy's three tests pass; the pushed commit must still be refused.
        source = HOOK.read_text(encoding="utf-8")
        decoy = self.root / "decoy"
        (decoy / "tests").mkdir(parents=True)
        (decoy / "tests/__init__.py").write_text("", encoding="utf-8")
        for module, case, method in REGISTRY_TESTS:
            self.assertIn(f"tests.{module}.{case}.{method}", source)
            (decoy / f"tests/{module}.py").write_text(
                f"import unittest\n\n\nclass {case}(unittest.TestCase):\n    def {method}(self):\n        pass\n",
                encoding="utf-8")
        commit = self.commit_on_head({PROBE: PROBE_TEXT})
        result = self.push(f"refs/heads/probe {commit} refs/heads/probe {self.zero}", PYTHONSAFEPATH="1",
                           PYTHONPATH=str(decoy))
        self.assertNotEqual(result.returncode, 0, result.stderr)
        self.assertIn(PROBE, result.stderr)
        self.assert_nothing_left()

    @unittest.skipUnless(ZIZMOR, "zizmor not on PATH")
    def test_a_signal_or_a_closed_reader_still_cleans_up(self):
        # A signal that kills the shell skips its EXIT trap, so the hook traps each one and exits through it. SIGPIPE
        # comes from a reader that closed early, as in `git push 2>&1 | head -n 1`; the shell may then exit through
        # its trap or through `set -e`, but it must exit rather than be killed.
        for name, status in (*SIGNAL_STATUS, ("SIGPIPE", None)):
            with self.subTest(signal=name):
                number = getattr(signal, name)
                if status is not None and signal.getsignal(number) == signal.SIG_IGN:
                    self.skipTest(f"{name} is ignored here, and a shell cannot trap a signal ignored on entry")
                with subprocess.Popen([str(HOOK), "origin", "origin"], cwd=self.repo, stdin=subprocess.PIPE,
                                      stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
                                      env=self.environment()) as process:
                    process.stdin.write(f"{self.main}\n")
                    process.stdin.close()
                    self.assertRegex(process.stderr.readline(), TREE_LINE)
                    if status is None:
                        process.stderr.close()
                    else:
                        process.send_signal(number)
                        process.stderr.read()
                    returncode = process.wait(timeout=300)
                if status is None:
                    self.assertGreater(returncode, 0)
                else:
                    self.assertEqual(returncode, status)
                self.assert_nothing_left()

    @unittest.skipUnless(ZIZMOR, "zizmor not on PATH")
    def test_a_native_push_from_a_linked_worktree_is_gated(self):
        # Pushing from a linked worktree, git exports GIT_DIR to the hook (githooks(5)). GIT_DIR turns off discovery,
        # so the guard must drop it to look at TMPDIR rather than at the pushing repository.
        remote = self.root / "remote.git"
        self.checked(["git", "clone", "-q", "--bare", "--shared", str(ROOT), str(remote)])
        linked = self.root / "linked"
        self.git("worktree", "add", "-q", "--no-checkout", "--detach", str(linked), self.head)
        self.git("config", "core.hooksPath", str(HOOK.parent))
        probe = self.commit_on_head({PROBE: PROBE_TEXT})
        passed, refused = (subprocess.run(["git", "push", str(remote), f"{commit}:refs/heads/{name}"], cwd=linked,
                                          capture_output=True, text=True, env=self.environment(), timeout=300)
                           for commit, name in ((self.head, "pre-push-passed"), (probe, "pre-push-refused")))
        self.assertEqual(passed.returncode, 0, passed.stderr)
        self.assertIn("Ran 3 tests", passed.stderr)
        self.assertEqual(self.checked(["git", "-C", str(remote), "rev-parse", "refs/heads/pre-push-passed"]), self.head)
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("Push refused", refused.stderr)
        absent = subprocess.run(["git", "-C", str(remote), "rev-parse", "--verify", "--quiet",
                                 "refs/heads/pre-push-refused"], capture_output=True, text=True, timeout=120)
        self.assertNotEqual(absent.returncode, 0)
        self.assert_nothing_left(worktrees=2)


if __name__ == "__main__":
    unittest.main()
