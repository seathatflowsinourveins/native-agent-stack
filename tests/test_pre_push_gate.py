"""Tracked pre-push tip/history name and registry gate (scripts/git-hooks/pre-push).

Local integration class: a temporary clone that borrows this checkout's objects
(`git clone --shared --no-checkout`, so nothing is copied), this checkout's HEAD
commit overlaid with the current scanner sources, commits built on it with plumbing (a synthetic unlisted lockfile, or a
registry test forced onto its skip or expected-failure path), and the zizmor
binary already on PATH. Most tests run the hook directly with the stdin lines
git would give it (githooks(5), pre-push). Native pushes also cover removed
historical bytes and author/committer metadata. A linked-worktree push, where
git exports GIT_DIR to the hook, uses a bare clone sharing this checkout's objects.

Every hook run sets GIT_CEILING_DIRECTORIES (git(1)) to the parent of its
temporary root. Git's discovery, and the hook's inside-a-repository guard with
it, then never looks above that root, so the result does not depend on what the
host keeps there (on this project's WSL host, an empty /tmp/.git while Codex
sandboxes run). Skips when zizmor is absent, except for the cases that run no
registry test.
"""

from pathlib import Path
import json
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
# Split the fixture literal so scanning the test source itself never denies it.
FIXTURE_NAME = "fixture_" + "host_marker"
NAME_PROBE = "pre-push-name-probe.txt"
SCANNER_SOURCES = ("scripts/validate.py", "scripts/host_name_scan.py")
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
        self.source_head = self.checked(["git", "-C", str(ROOT), "rev-parse", "HEAD"])
        self.head = self.source_head
        self.checked(["git", "clone", "-q", "--shared", "--no-checkout", str(ROOT), str(self.repo)])
        # HEAD before F11 lacks --scan-tracked. Commit the new scanner bytes to a
        # synthetic tip; the hook must still scan that immutable tip's checkout.
        self.head = self.commit_on_head({path: (ROOT / path).read_text(encoding="utf-8")
                                         for path in SCANNER_SOURCES})
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

    def commit_on_head(self, files, **identity):
        """Commit {path: text} on the fixture tip; None deletes a file, using a scratch index."""
        index = {**os.environ, "GIT_INDEX_FILE": str(self.root / "index")}
        self.git("read-tree", self.head, env=index)
        for path, text in files.items():
            if text is None:
                self.git("update-index", "--force-remove", path, env=index)
                continue
            blob = self.git("hash-object", "-w", "--stdin", input=text)
            self.git("update-index", "--add", "--cacheinfo", f"100644,{blob},{path}", env=index)
        tree = self.git("write-tree", env=index)
        environment = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
                       "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid", **identity}
        return self.git("commit-tree", tree, "-p", self.head, "-m", f"probe: {', '.join(files)}", env=environment)

    def environment(self, tmpdir=None, path=None, **extra):
        """The hook's environment: its TMPDIR, with git's discovery stopping above the temporary root."""
        environment = {**os.environ, "TMPDIR": str(tmpdir or self.hook_tmp),
                       "GIT_CEILING_DIRECTORIES": str(self.root.resolve().parent),
                       "NATIVE_AGENT_HOST_NAMES_JSON": json.dumps([FIXTURE_NAME]), **extra}
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

    def native_push(self, commit, name, remote_commit=None, **environment):
        """Push through Git's actual pre-push entry point to a local bare remote."""
        self.remote = self.root / "remote.git"
        self.checked(["git", "clone", "-q", "--bare", "--shared", str(self.repo), str(self.remote)])
        if remote_commit is not None:
            self.checked(["git", "-C", str(self.remote), "update-ref", f"refs/heads/{name}", remote_commit])
        self.git("config", "core.hooksPath", str(HOOK.parent))
        return subprocess.run(["git", "push", str(self.remote), f"{commit}:refs/heads/{name}"], cwd=self.repo,
                              capture_output=True, text=True, env=self.environment(**environment), timeout=300)

    def assert_remote_ref_absent(self, name):
        result = subprocess.run(["git", "-C", str(self.remote), "rev-parse", "--verify", "--quiet",
                                 f"refs/heads/{name}"], capture_output=True, text=True, timeout=120)
        self.assertNotEqual(result.returncode, 0)

    def assert_remote_ref_equal(self, name, commit):
        self.assertEqual(self.checked(["git", "-C", str(self.remote), "rev-parse", f"refs/heads/{name}"]), commit)

    def assert_native_metadata_refused(self, field, value):
        """Keep the tree clean and put the denied fixture only in a commit identity."""
        base = self.head
        commit = self.commit_on_head({}, **{field: value})
        result = self.native_push(commit, "metadata-refused", remote_commit=base)
        self.assertNotEqual(result.returncode, 0)
        line = {"GIT_AUTHOR_NAME": 1, "GIT_AUTHOR_EMAIL": 2,
                "GIT_COMMITTER_NAME": 3, "GIT_COMMITTER_EMAIL": 4}[field]
        self.assertIn(f"git-metadata/{commit}:{line}", result.stdout + result.stderr)
        reports = [json.loads(line) for line in result.stdout.splitlines() if line.startswith("{")]
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0]["status"], "failed")
        self.assertEqual(reports[0]["source"], "synthetic")
        self.assertGreater(reports[0]["matching_locations"], 0)
        self.assertIn("committed host-name scan failed", result.stderr)
        self.assertIn("Ran 3 tests", result.stderr)
        self.assertNotIn(FIXTURE_NAME, result.stdout + result.stderr)
        self.assert_remote_ref_equal("metadata-refused", base)
        self.assert_nothing_left()

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
    def test_a_native_push_refuses_a_committed_bare_name_without_echoing_it(self):
        commit = self.commit_on_head({NAME_PROBE: f"{FIXTURE_NAME}\n"})
        result = self.native_push(commit, "name-refused")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(f"{NAME_PROBE}:1", result.stdout + result.stderr)
        self.assertIn("committed host-name scan failed", result.stderr)
        self.assertIn("Ran 3 tests", result.stderr)
        self.assertNotIn(FIXTURE_NAME, result.stdout + result.stderr)
        self.assert_remote_ref_absent("name-refused")
        self.assert_nothing_left()

    @unittest.skipUnless(ZIZMOR, "zizmor not on PATH")
    def test_a_native_push_refuses_a_name_added_then_removed_in_pushed_history(self):
        base = self.head
        self.head = self.commit_on_head({NAME_PROBE: f"{FIXTURE_NAME}\n"})
        tip = self.commit_on_head({NAME_PROBE: None})
        result = self.native_push(tip, "history-refused", remote_commit=base)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(f"{NAME_PROBE}:1", result.stdout + result.stderr)
        self.assertIn("committed host-name scan failed", result.stderr)
        self.assertIn("Ran 3 tests", result.stderr)
        self.assertNotIn(FIXTURE_NAME, result.stdout + result.stderr)
        self.assert_remote_ref_equal("history-refused", base)
        self.assert_nothing_left()

    @unittest.skipUnless(ZIZMOR, "zizmor not on PATH")
    def test_a_new_native_ref_refuses_a_name_removed_before_its_tip(self):
        self.head = self.commit_on_head({NAME_PROBE: f"{FIXTURE_NAME}\n"})
        tip = self.commit_on_head({NAME_PROBE: None})
        result = self.native_push(tip, "new-history-refused")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(f"{NAME_PROBE}:1", result.stdout + result.stderr)
        self.assertIn("committed host-name scan failed", result.stderr)
        self.assertIn("Ran 3 tests", result.stderr)
        self.assertNotIn(FIXTURE_NAME, result.stdout + result.stderr)
        self.assert_remote_ref_absent("new-history-refused")
        self.assert_nothing_left()

    @unittest.skipUnless(ZIZMOR, "zizmor not on PATH")
    def test_shared_tips_scan_every_ref_range_and_run_registry_tests_once(self):
        base = self.head
        self.head = self.commit_on_head({NAME_PROBE: f"{FIXTURE_NAME}\n"})
        self.head = self.commit_on_head({NAME_PROBE: None})
        tip = self.commit_on_head({"pre-push-clean-probe.txt": "synthetic clean content\n"})
        result = self.push(f"refs/heads/clean {tip} refs/heads/clean {self.head}",
                           f"refs/heads/history {tip} refs/heads/history {base}")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(f"{NAME_PROBE}:1", result.stdout + result.stderr)
        self.assertIn("committed host-name scan failed", result.stderr)
        self.assertEqual(result.stderr.count(f"pre-push: running the registry tests on {tip}"), 1)
        self.assertEqual(result.stderr.count("Ran 3 tests"), 1)
        self.assertNotIn(FIXTURE_NAME, result.stdout + result.stderr)
        self.assert_nothing_left()

    @unittest.skipUnless(ZIZMOR, "zizmor not on PATH")
    def test_a_native_push_refuses_a_denied_author_name(self):
        self.assert_native_metadata_refused("GIT_AUTHOR_NAME", f"Synthetic {FIXTURE_NAME}")

    @unittest.skipUnless(ZIZMOR, "zizmor not on PATH")
    def test_a_native_push_refuses_a_denied_author_email(self):
        self.assert_native_metadata_refused("GIT_AUTHOR_EMAIL", f"{FIXTURE_NAME}@example.invalid")

    @unittest.skipUnless(ZIZMOR, "zizmor not on PATH")
    def test_a_native_push_refuses_a_denied_committer_name(self):
        self.assert_native_metadata_refused("GIT_COMMITTER_NAME", f"Synthetic {FIXTURE_NAME}")

    @unittest.skipUnless(ZIZMOR, "zizmor not on PATH")
    def test_a_native_push_refuses_a_denied_committer_email(self):
        self.assert_native_metadata_refused("GIT_COMMITTER_EMAIL", f"{FIXTURE_NAME}@example.invalid")

    @unittest.skipUnless(ZIZMOR, "zizmor not on PATH")
    def test_a_native_push_scans_committed_bytes_despite_local_contamination(self):
        self.git("checkout", "-q", "--detach", self.head)
        (self.repo / "AGENTS.md").write_text(f"{FIXTURE_NAME}\n", encoding="utf-8")
        (self.repo / "pre-push-untracked.txt").write_text(f"{FIXTURE_NAME}\n", encoding="utf-8")
        (self.repo / ".git/info/exclude").write_text("pre-push-ignored.txt\n", encoding="utf-8")
        (self.repo / "pre-push-ignored.txt").write_text(f"{FIXTURE_NAME}\n", encoding="utf-8")
        result = self.native_push(self.head, "clean-committed-tip")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Ran 3 tests", result.stderr)
        self.assertNotIn(FIXTURE_NAME, result.stdout + result.stderr)
        self.assertEqual(self.checked(["git", "-C", str(self.remote), "rev-parse",
                                       "refs/heads/clean-committed-tip"]), self.head)
        self.assert_nothing_left()

    @unittest.skipUnless(ZIZMOR, "zizmor not on PATH")
    def test_a_native_push_scans_the_immutable_tip_when_pushing_from_a_clean_index(self):
        # The name predates this push, so history alone cannot detect it. Git
        # exports GIT_DIR to the hook; it must not redirect ls-files to this
        # pushing checkout's clean index instead of the detached tip's index.
        self.head = self.commit_on_head({NAME_PROBE: f"{FIXTURE_NAME}\n"})
        base = self.head
        tip = self.commit_on_head({"pre-push-clean-probe.txt": "synthetic clean content\n"})
        self.git("checkout", "-q", "--detach", self.source_head)
        result = self.native_push(tip, "immutable-tip-refused", remote_commit=base)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(f"{NAME_PROBE}:1", result.stdout + result.stderr)
        self.assertIn("committed host-name scan failed", result.stderr)
        self.assertIn("Ran 3 tests", result.stderr)
        self.assertNotIn(FIXTURE_NAME, result.stdout + result.stderr)
        self.assert_remote_ref_equal("immutable-tip-refused", base)
        self.assert_nothing_left()

    @unittest.skipUnless(ZIZMOR, "zizmor not on PATH")
    def test_a_native_push_refuses_scanner_errors_and_still_runs_registry_tests(self):
        result = self.native_push(self.head, "scanner-error", NATIVE_AGENT_HOST_NAMES_JSON="invalid-json")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("committed host-name scan failed", result.stderr)
        self.assertIn("Ran 3 tests", result.stderr)
        self.assertNotIn(FIXTURE_NAME, result.stdout + result.stderr)
        self.assert_remote_ref_absent("scanner-error")
        self.assert_nothing_left()

    @unittest.skipUnless(ZIZMOR, "zizmor not on PATH")
    def test_a_tip_without_the_name_scanner_fails_closed(self):
        commit = self.commit_on_head({"scripts/validate.py": None})
        result = self.push(f"refs/heads/old {commit} refs/heads/old {self.zero}")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("committed host-name scan failed", result.stderr)
        self.assertIn("Ran 3 tests", result.stderr)
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
