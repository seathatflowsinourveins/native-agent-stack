"""run_discipline refusals: frozen protocol and running tree (R8-4), protocol sha256 (R8-2), vintages before the
freeze (R8-4), the committed-tree requirement and the freeze commit time."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from core import guards
from core.params import PROTOCOL_PATH, STUDY_PATH


def sh(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True,
                                   env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
                                        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid",
                                        "GIT_COMMITTER_DATE": "2026-10-02T21:30:00+00:00", "PATH": "/usr/bin:/bin"}).strip()


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
