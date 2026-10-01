"""run_discipline refusals: frozen protocol and running tree (R8-4), protocol sha256 (R8-2), vintages before the
freeze (R8-4), the committed-tree requirement and the freeze commit time. Review round 18, second repair (R2-2): the
running tree is HEAD's only when no index flag hides a tracked file from git status and every tracked file's bytes are
HEAD's blob."""
import contextlib
import json
import re
import shlex
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core import guards
from core.params import PROTOCOL_PATH, STUDY_PATH

TRANSPORT = f"{STUDY_PATH}/fetch/transport.py"
# git-ls-files(1) -v: the tag of an index entry marked assume-unchanged is lowercase, that of one marked skip-worktree
# is S, and s with both; git-update-index(1) sets each flag. (flag names in the refusal, tag, update-index options)
INDEX_FLAGS = (("assume-unchanged", "h", ("--assume-unchanged",)),
               ("skip-worktree", "S", ("--skip-worktree",)),
               ("assume-unchanged and skip-worktree", "s", ("--assume-unchanged", "--skip-worktree")))


def sh(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True,
                                   env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
                                        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid",
                                        "GIT_COMMITTER_DATE": "2026-10-02T21:30:00+00:00", "PATH": "/usr/bin:/bin"}).strip()


def status(repo) -> str:
    """What core.guards.running_tree asks git first: the study tree's changes, untracked files included."""
    return sh(repo, "status", "--porcelain", "--untracked-files=all", "--", STUDY_PATH)


class RunningTreeContent(unittest.TestCase):
    """Review round 18, second repair (R2-2). At 406ad3c5 running_tree returned HEAD's study tree whenever git status
    reported no change, so the tree a run named (and every seal identity bound, H1) could differ from the files that
    ran. Each case builds a state in which git status reports nothing."""

    @contextlib.contextmanager
    def study_repo(self):
        """A temporary repository (tests/fixture_repo.py) whose committed, clean study tree holds two files."""
        from tests import fixture_repo as FR
        with tempfile.TemporaryDirectory() as tmp:
            repo = FR.init_repo(Path(tmp) / "repo")
            FR.write(repo / STUDY_PATH / "core" / "a.py", "x = 1\n")
            FR.write(repo / TRANSPORT, "HOST = 'fixture'\n")
            FR.commit_push(repo, "2026-10-01T21:30:00+00:00", "study tree")
            self.assertEqual(guards.running_tree(repo), sh(repo, "rev-parse", f"HEAD:{STUDY_PATH}"))
            yield repo, Path(tmp)

    def change(self, repo, tmp, how):
        from tests import fixture_repo as FR
        path = repo / TRANSPORT
        if how == "changed":
            path.write_text("HOST = 'changed'\n")
        elif how == "deleted":
            path.unlink()
        elif how == "replaced_by_a_link":       # a link to a file outside the repository that holds the same bytes
            target = FR.write(tmp / "transport-outside.py", path.read_bytes())
            path.unlink()
            path.symlink_to(target)

    def test_running_tree_refuses_an_index_entry_marked_assume_unchanged_or_skip_worktree(self):
        """The index-flag refusal: an entry with either flag is refused, with a message that names the file and the
        flag, whether or not the file changed (git status reports nothing in each case, a deleted file included)."""
        for flag, tag, options in INDEX_FLAGS:
            for how in ("unchanged", "changed", "deleted"):
                with self.subTest(flag=flag, file=how), self.study_repo() as (repo, tmp):
                    for option in options:
                        sh(repo, "update-index", option, TRANSPORT)
                    self.change(repo, tmp, how)
                    self.assertEqual(status(repo), "")
                    self.assertEqual(sh(repo, "ls-files", "-v", "--", TRANSPORT), f"{tag} {TRANSPORT}")
                    with self.assertRaisesRegex(guards.Refused, re.escape(f"{TRANSPORT} ({flag})")):
                        guards.running_tree(repo)

    def test_running_tree_compares_every_tracked_file_with_its_blob_when_the_flag_refusal_is_bypassed(self):
        """The content check alone: with the index-flag refusal bypassed, a flagged file that changed, was deleted or
        was replaced by a link to the same bytes is still refused, because the working file's own bytes are hashed."""
        cases = {"changed": "differs from HEAD's blob", "deleted": "is missing",
                 "replaced_by_a_link": "is not a regular file"}
        for flag, _, options in INDEX_FLAGS[:2]:
            for how, problem in cases.items():
                with self.subTest(flag=flag, file=how), self.study_repo() as (repo, tmp):
                    for option in options:
                        sh(repo, "update-index", option, TRANSPORT)
                    self.change(repo, tmp, how)
                    self.assertEqual(status(repo), "")
                    with mock.patch.object(guards, "_masked_index_entries", lambda *args: []), \
                            self.assertRaisesRegex(guards.Refused, re.escape(f"{TRANSPORT} {problem}")):
                        guards.running_tree(repo)

    def test_running_tree_refuses_a_change_that_a_clean_filter_hides(self):
        """Only the content check can refuse this one: no index flag is set, and git status reports nothing because a
        clean filter (set in the repository's own configuration and .git/info/attributes, neither of them tracked)
        gives the committed bytes back for the edited file. git hash-object --no-filters hashes the file itself."""
        from tests import fixture_repo as FR
        with self.study_repo() as (repo, tmp):
            committed = FR.write(tmp / "transport-committed.py", (repo / TRANSPORT).read_bytes())
            sh(repo, "config", "filter.committed.clean", f"cat {shlex.quote(str(committed))}")
            FR.write(repo / ".git" / "info" / "attributes", f"{TRANSPORT} filter=committed\n")
            (repo / TRANSPORT).write_text("HOST = 'changed'\n")      # the committed length: git compares content
            self.assertEqual(len("HOST = 'changed'\n"), len(committed.read_bytes()))
            self.assertEqual(status(repo), "")
            self.assertEqual(sh(repo, "ls-files", "-v", "--", TRANSPORT), f"H {TRANSPORT}")
            self.assertEqual(sh(repo, "hash-object", TRANSPORT), sh(repo, "rev-parse", f"HEAD:{TRANSPORT}"))
            with self.assertRaisesRegex(guards.Refused, re.escape(f"{TRANSPORT} differs from HEAD's blob")):
                guards.running_tree(repo)

    def test_running_tree_refuses_a_committed_symbolic_link(self):
        """A symbolic-link entry is refused: the tree hash covers the link's text, not the file it names."""
        from tests import fixture_repo as FR
        with self.study_repo() as (repo, tmp):
            link = f"{STUDY_PATH}/core/b.py"
            (repo / link).symlink_to("a.py")
            FR.commit_push(repo, "2026-10-01T22:00:00+00:00", "a symbolic link")
            self.assertEqual(status(repo), "")
            self.assertEqual(sh(repo, "ls-tree", "HEAD", "--", link).split()[0], "120000")
            with self.assertRaisesRegex(guards.Refused, re.escape(f"{link} is a symbolic link or submodule entry")):
                guards.running_tree(repo)

    def test_running_tree_refuses_files_that_match_a_replacement_of_heads_tree(self):
        """running_tree reads HEAD's own tree, without replace refs (git-replace(1); git --no-replace-objects). With a
        replace ref on HEAD's study tree object, git reads another tree in its place: plain git status reports nothing
        for files that match that other tree, no index flag is set, and git ls-tree lists its blobs under the id of
        HEAD's tree. At 28fafe84 the content check compared the files with those blobs and running_tree returned
        HEAD's tree. At ba106834 the content check listed the tree without replace refs and refused the file. Since
        follow-up F2 every git command of core.guards ignores replace refs (git_command), so its git status already
        reports the files as changed."""
        from tests import fixture_repo as FR
        with self.study_repo() as (repo, _):
            head, tree = sh(repo, "rev-parse", "HEAD"), sh(repo, "rev-parse", f"HEAD:{STUDY_PATH}")
            (repo / TRANSPORT).write_text("HOST = 'changed'\n")
            FR.commit_push(repo, "2026-10-01T22:00:00+00:00", "another tree")
            sh(repo, "replace", tree, sh(repo, "rev-parse", f"HEAD:{STUDY_PATH}"))
            sh(repo, "reset", "-q", "--soft", head)         # HEAD names the first tree; the files are the second's
            self.assertEqual(sh(repo, "rev-parse", f"HEAD:{STUDY_PATH}"), tree)
            self.assertEqual((status(repo), (repo / TRANSPORT).read_text()), ("", "HOST = 'changed'\n"))
            self.assertEqual(sh(repo, "ls-files", "-v", "--", TRANSPORT), f"H {TRANSPORT}")
            self.assertEqual(guards.git(repo, "rev-parse", f"HEAD:{STUDY_PATH}"), tree)
            self.assertIn(TRANSPORT, guards.git(repo, "status", "--porcelain", "--", STUDY_PATH))
            with self.assertRaisesRegex(guards.Refused, "^the study tree has uncommitted changes"):
                guards.running_tree(repo)

    def test_running_tree_refuses_a_file_name_that_one_line_cannot_carry(self):
        """git hash-object --stdin-paths reads one path per line, so a tracked file whose name holds a control
        character (here a line break) is refused by name, before any path is handed to it."""
        from tests import fixture_repo as FR
        with self.study_repo() as (repo, _):
            FR.write(repo / STUDY_PATH / "core" / "two\nlines.py", "y = 1\n")
            FR.commit_push(repo, "2026-10-01T22:00:00+00:00", "a line break in a file name")
            self.assertEqual(status(repo), "")
            with self.assertRaisesRegex(guards.Refused, "lines.py' has a control character in its name"):
                guards.running_tree(repo)

    def test_running_tree_refuses_when_git_does_not_hash_every_file(self):
        """The content check fails closed: if git hash-object exits with an error, or prints fewer hashes than the
        files it was given, the tree is refused, whatever the hashes it did print."""
        real = subprocess.run

        def altered(change):
            def run(command, *args, **kwargs):
                done = real(command, *args, **kwargs)
                return change(done) if "hash-object" in command else done
            return run
        cases = {"an_error_exit": lambda done: subprocess.CompletedProcess(done.args, 128, done.stdout, b"fatal: x"),
                 "one_hash_short": lambda done: subprocess.CompletedProcess(
                     done.args, 0, done.stdout.split(b"\n", 1)[0] + b"\n", done.stderr)}
        for case, change in cases.items():
            with self.subTest(case=case), self.study_repo() as (repo, _):
                with mock.patch.object(guards.subprocess, "run", altered(change)), \
                        self.assertRaisesRegex(guards.Refused, "git hash-object could not read every tracked file"):
                    guards.running_tree(repo)


class RealObjects(unittest.TestCase):
    """Review round 18, second repair, follow-up F2: every git command core.guards runs is built by
    core.guards.git_command with --no-replace-objects (git(1); git-replace(1)), so a guard reads the repository's own
    commit, tree or blob and not an object that a local replace ref puts in its place. The running-tree case is
    RunningTreeContent.test_running_tree_refuses_files_that_match_a_replacement_of_heads_tree; these are two other
    guards. In each, git without the option gives the replacement, which the test shows first."""

    def test_committed_bytes_returns_the_real_blob_under_a_replace_ref(self):
        """committed_bytes reads the protocol, the logs and the deviations at a commit (frozen_protocol, void_records,
        first_reach). With a replace ref on the committed blob, git show prints the replacement."""
        from tests import fixture_repo as FR
        with tempfile.TemporaryDirectory() as tmp:
            repo = FR.init_repo(Path(tmp) / "repo")
            committed = FR.write(repo / PROTOCOL_PATH, json.dumps({"status": "frozen"})).read_bytes()
            first = FR.commit_push(repo, "2026-10-01T21:30:00+00:00", "the protocol")
            FR.write(repo / PROTOCOL_PATH, json.dumps({"status": "edited"}))
            FR.commit_push(repo, "2026-10-01T22:00:00+00:00", "another protocol")
            sh(repo, "replace", sh(repo, "rev-parse", f"{first}:{PROTOCOL_PATH}"),
               sh(repo, "rev-parse", f"HEAD:{PROTOCOL_PATH}"))
            self.assertEqual(json.loads(sh(repo, "show", f"{first}:{PROTOCOL_PATH}")), {"status": "edited"})
            self.assertEqual(guards.committed_bytes(repo, first, PROTOCOL_PATH), committed)

    def test_the_transport_deviation_diff_compares_the_real_trees_under_a_replace_ref(self):
        """fetch_only_diff decides whether a running tree differs from the pinned tree only under fetch/ (the
        transport-deviation rule, check_study_tree; run.py transport-check lists the changed paths the same way).
        Here the trees also differ in core/a.py. With a replace ref that puts the pinned tree's core/ in place of the
        other tree's, git diff-tree lists the transport alone."""
        from tests import fixture_repo as FR
        with tempfile.TemporaryDirectory() as tmp:
            repo = FR.init_repo(Path(tmp) / "repo")
            FR.write(repo / STUDY_PATH / "core" / "a.py", "x = 1\n")
            FR.write(repo / TRANSPORT, "HOST = 'fixture'\n")
            first = FR.commit_push(repo, "2026-10-01T21:30:00+00:00", "the pinned tree")
            FR.write(repo / STUDY_PATH / "core" / "a.py", "x = 2\n")
            FR.write(repo / TRANSPORT, "HOST = 'changed'\n")
            FR.commit_push(repo, "2026-10-01T22:00:00+00:00", "a tree that also changes core/")
            pinned, tree = (sh(repo, "rev-parse", f"{commit}:{STUDY_PATH}") for commit in (first, "HEAD"))
            self.assertEqual(sh(repo, "diff-tree", "-r", "--name-only", pinned, tree).splitlines(),
                             ["core/a.py", "fetch/transport.py"])
            sh(repo, "replace", sh(repo, "rev-parse", f"HEAD:{STUDY_PATH}/core"),
               sh(repo, "rev-parse", f"{first}:{STUDY_PATH}/core"))
            self.assertEqual(sh(repo, "diff-tree", "-r", "--name-only", pinned, tree).splitlines(),
                             ["fetch/transport.py"])
            self.assertFalse(guards.fetch_only_diff(repo, pinned, tree))
            self.assertEqual(guards.git(repo, "diff-tree", "-r", "--name-only", pinned, tree).splitlines(),
                             ["core/a.py", "fetch/transport.py"])


class Guards(unittest.TestCase):
    def test_require_frozen_and_matching_tree(self):
        tree = "a" * 40
        draft = {"status": "draft_pending_independent_pre_outcome_review", "frozen_before_outcomes": False,
                 "run_discipline": {"study_code": {"tree": None}}}
        with self.assertRaises(guards.Refused):
            guards.require_frozen(draft, tree)
        frozen = {"status": "frozen", "frozen_before_outcomes": True, "run_discipline": {"study_code": {"tree": tree}}}
        guards.require_frozen(frozen, tree)
        with self.assertRaises(guards.Refused):
            guards.require_frozen(frozen, "b" * 40)

    def test_the_protocol_refuses_a_tree_it_does_not_pin(self):
        # true of the draft (not frozen) and of the frozen protocol (another tree), so it holds after the freeze (F6)
        proto = json.loads((Path(__file__).resolve().parents[2] / "protocol-core-draft.json").read_text())
        with self.assertRaises(guards.Refused):
            guards.require_frozen(proto, "a" * 40)

    def test_protocol_sha_and_vintages(self):
        with self.assertRaises(guards.Refused):
            guards.check_protocol_sha(b"{}", "0" * 64)
        guards.check_vintages(["2026-10-03T00:00:00Z"], "2026-10-02T21:30:00Z")
        with self.assertRaises(guards.Refused):
            guards.check_vintages(["2026-09-30T00:00:00Z", "2026-10-03T00:00:00Z"], "2026-10-02T21:30:00Z")

    def test_running_tree_refuses_uncommitted_changes_and_finds_the_freeze_commit(self):
        from tests import fixture_repo as FR
        with tempfile.TemporaryDirectory() as tmp:
            repo = FR.init_repo(Path(tmp) / "repo")
            (repo / STUDY_PATH).mkdir(parents=True)
            (repo / STUDY_PATH / "a.py").write_text("x = 1\n")
            (repo / PROTOCOL_PATH).write_text(json.dumps({"status": "draft"}))
            FR.commit_push(repo, "2026-10-01T21:30:00+00:00", "draft")
            tree = guards.running_tree(repo)
            self.assertEqual(tree, sh(repo, "rev-parse", f"HEAD:{STUDY_PATH}"))
            (repo / PROTOCOL_PATH).write_text(json.dumps({"status": "frozen"}))
            FR.commit_push(repo, "2026-10-02T21:30:00+00:00", "freeze")
            self.assertEqual(guards.freeze_commit_utc(repo), "2026-10-02T21:30:00Z")
            self.assertEqual(guards.running_tree(repo), tree)  # appending logs elsewhere keeps the tree
            (repo / STUDY_PATH / "a.py").write_text("x = 2\n")
            with self.assertRaises(guards.Refused):
                guards.running_tree(repo)

    def test_the_freeze_time_needs_a_signed_merge_commit(self):
        # review round 10, M3: a backdated commit that no merge key signed gives no freeze time
        from tests import fixture_repo as FR
        with tempfile.TemporaryDirectory() as tmp:
            repo = FR.init_repo(Path(tmp) / "repo")
            (repo / PROTOCOL_PATH).parent.mkdir(parents=True)
            (repo / PROTOCOL_PATH).write_text(json.dumps({"status": "frozen"}))
            FR.commit_push(repo, "2026-10-02T21:30:00+00:00", "freeze", sign=False)
            with self.assertRaisesRegex(guards.Refused, "not a merge commit signed"):
                guards.freeze_commit(repo)
            # signed, but by a committer other than the merge key's identity
            (repo / PROTOCOL_PATH).write_text(json.dumps({"status": "frozen", "n": 2}))
            FR.sh(repo, "commit", "-q", "-am", "x", committer=("t", "t@example.invalid"))
            self.assertFalse(guards.verified_merge(repo, FR.sh(repo, "rev-parse", "HEAD")))

    def test_the_pinned_merge_key_verifies_a_real_origin_main_commit(self):
        # the pinned public key is GitHub's web-flow key, and a squash merge of this repository verifies against it
        repo = Path(__file__).resolve().parents[5]
        out = subprocess.run(["gpg", "--batch", "--with-colons", "--show-keys", guards.REAL_MERGE_KEY["path"]],
                             capture_output=True, text=True, check=True).stdout
        fprs = [line.split(":")[9] for line in out.splitlines() if line.startswith("fpr:")]
        self.assertIn(guards.REAL_MERGE_KEY["fingerprint"], fprs)
        self.assertTrue(guards.verified_merge(repo, "4911baf411370517b1c5e0e83ca4d49c14e36db3", key=guards.REAL_MERGE_KEY))
        self.assertFalse(guards.verified_merge(repo, "4911baf411370517b1c5e0e83ca4d49c14e36db3",
                                               key={**guards.REAL_MERGE_KEY, "fingerprint": "0" * 40}))

if __name__ == "__main__":
    unittest.main()
