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

    def test_the_current_draft_refuses_every_fetch_and_evaluation(self):
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
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            sh(repo, "init", "-q", "-b", "main")
            (repo / STUDY_PATH).mkdir(parents=True)
            (repo / STUDY_PATH / "a.py").write_text("x = 1\n")
            (repo / PROTOCOL_PATH).write_text(json.dumps({"status": "draft"}))
            sh(repo, "add", "-A")
            sh(repo, "commit", "-q", "-m", "draft")
            tree = guards.running_tree(repo)
            self.assertEqual(tree, sh(repo, "rev-parse", f"HEAD:{STUDY_PATH}"))
            (repo / PROTOCOL_PATH).write_text(json.dumps({"status": "frozen"}))
            sh(repo, "commit", "-q", "-am", "freeze")
            sh(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
            self.assertEqual(guards.freeze_commit_utc(repo), "2026-10-02T21:30:00Z")
            self.assertEqual(guards.running_tree(repo), tree)  # appending logs elsewhere keeps the tree
            (repo / STUDY_PATH / "a.py").write_text("x = 2\n")
            with self.assertRaises(guards.Refused):
                guards.running_tree(repo)


if __name__ == "__main__":
    unittest.main()
