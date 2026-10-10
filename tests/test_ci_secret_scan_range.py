"""Exercise CI event range selection against real, disposable Git commit graphs.

No secret scanner runs here. Git's commit-tree builds bounded fixtures without
repository hooks; the production CLI must resolve the event to the commits Git
would actually supply to the scanners.
"""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/ci_secret_scan_range.py"
ZERO_SHA = "0" * 40


class CiSecretScanRangeTests(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory(prefix="ci-secret-scan-range-")
        self.addCleanup(scratch.cleanup)
        self.repo = Path(scratch.name) / "repo"
        self.repo.mkdir()
        # Keep each graph independent of host identities, aliases and hooks. No
        # user-level configuration is read or written by these fixture commands.
        self.env = {
            "PATH": os.environ.get("PATH", os.defpath),
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_AUTHOR_NAME": "range-fixture",
            "GIT_AUTHOR_EMAIL": "range-fixture@example.invalid",
            "GIT_COMMITTER_NAME": "range-fixture",
            "GIT_COMMITTER_EMAIL": "range-fixture@example.invalid",
        }
        self.git("init", "-q", "--object-format=sha1", "--initial-branch=main")
        self.tree = self.git("mktree", input="")
        self.root = self.commit("root")
        self.base = self.commit("shared base", self.root)
        self.main = self.commit("main advanced", self.base)
        self.feature_one = self.commit("feature one", self.base)
        self.feature_two = self.commit("feature two", self.feature_one)
        self.git("update-ref", "refs/heads/main", self.main)
        self.git("update-ref", "refs/remotes/origin/main", self.main)
        self.checkout(self.feature_two)

    def git(self, *args, input=None):
        result = subprocess.run(["git", *args], cwd=self.repo, env=self.env,
                                input=input, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def commit(self, label, *parents):
        args = ["commit-tree", self.tree, "-m", label]
        for parent in parents:
            args.extend(("-p", parent))
        return self.git(*args)

    def checkout(self, head):
        self.git("update-ref", "refs/heads/scan", head)
        self.git("symbolic-ref", "HEAD", "refs/heads/scan")

    def run_range(self, event, payload):
        event_path = self.repo.parent / "event.json"
        event_path.write_text(json.dumps(payload), encoding="utf-8")
        return subprocess.run([sys.executable, "-B", str(SCRIPT),
                               "--event-name", event, "--event-path", str(event_path)],
                              cwd=self.repo, env=self.env, capture_output=True,
                              text=True, timeout=15)

    def assert_range(self, event, payload, start, end, commits):
        result = self.run_range(event, payload)
        self.assertEqual(result.returncode, 0, result.stderr)
        outputs = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
        self.assertEqual(outputs.get("start"), start)
        self.assertEqual(outputs.get("end"), end)
        self.assertEqual(outputs.get("range"), f"{start}..{end}")
        self.assertRegex(outputs.get("reason", ""), r"^[a-z][a-z0-9-]+$")
        actual = set(self.git("rev-list", outputs["range"]).splitlines())
        self.assertEqual(actual, set(commits), "the emitted range must contain exactly the landed commits")
        self.assertGreater(len(actual), 0, "a successful range may not scan nothing")
        return outputs

    def assert_rejected(self, event, payload):
        result = self.run_range(event, payload)
        self.assertNotEqual(result.returncode, 0, "invalid or empty ranges must fail the CI step")
        self.assertNotIn("range=", result.stdout, "a rejected event must not publish scanner inputs")

    @staticmethod
    def pr(base, head):
        return {"pull_request": {"base": {"sha": base}, "head": {"sha": head}}}

    def test_push_scans_the_before_after_range(self):
        self.assert_range("push", {"before": self.base, "after": self.feature_two},
                          self.base, self.feature_two, (self.feature_one, self.feature_two))

    def test_first_branch_push_uses_the_merge_base_with_main(self):
        self.assert_range("push", {"before": ZERO_SHA, "after": self.feature_two},
                          self.base, self.feature_two, (self.feature_one, self.feature_two))

    def test_force_push_excludes_the_shared_history_of_before_and_after(self):
        before = self.commit("abandoned force-push branch", self.base)
        self.assert_range("push", {"before": before, "after": self.feature_two},
                          self.base, self.feature_two, (self.feature_one, self.feature_two))

    def test_pull_request_merge_scans_from_its_actual_first_parent_when_base_moved(self):
        merge = self.commit("PR test merge", self.base, self.feature_two)
        self.checkout(merge)
        # The payload base has moved past the merge checkout's first parent.
        self.assert_range("pull_request", self.pr(self.main, self.feature_two),
                          self.base, merge, (self.feature_one, self.feature_two, merge))

    def test_pull_request_merge_scans_the_checked_out_merge_when_base_advanced(self):
        merge = self.commit("PR test merge with new base", self.main, self.feature_two)
        self.checkout(merge)
        self.assert_range("pull_request", self.pr(self.base, self.feature_two),
                          self.main, merge, (self.feature_one, self.feature_two, merge))

    def test_pull_request_head_checkout_uses_the_event_snapshot_base(self):
        # Moving the remote ref into the feature must not hide its first commit:
        # pull_request has its own exact base SHA and cannot use a fresh ref tip.
        self.git("update-ref", "refs/remotes/origin/main", self.feature_one)
        self.assert_range("pull_request", self.pr(self.main, self.feature_two),
                          self.base, self.feature_two, (self.feature_one, self.feature_two))

    def test_pull_request_head_checkout_may_itself_be_a_merge_commit(self):
        head = self.commit("feature merged main", self.feature_two, self.main)
        self.checkout(head)
        self.assert_range("pull_request", self.pr(self.main, head),
                          self.main, head, (self.feature_one, self.feature_two, head))

    def test_workflow_dispatch_on_a_feature_scans_the_main_merge_base_range(self):
        self.assert_range("workflow_dispatch", {}, self.base, self.feature_two,
                          (self.feature_one, self.feature_two))

    def test_workflow_dispatch_on_main_scans_only_the_latest_commit(self):
        self.checkout(self.main)
        self.assert_range("workflow_dispatch", {}, self.base, self.main, (self.main,))

    def test_empty_push_ranges_fail_closed(self):
        for before, after in ((self.feature_two, self.feature_two), (ZERO_SHA, self.main)):
            with self.subTest(before=before):
                self.checkout(after)
                self.assert_rejected("push", {"before": before, "after": after})

    def test_push_after_must_match_the_checked_out_head(self):
        self.assert_rejected("push", {"before": self.base, "after": self.main})

    def test_missing_event_data_or_commits_fail_closed(self):
        unknown = "a" * 40
        for event, payload in (
                ("push", {}),
                ("push", {"before": self.base}),
                ("push", {"before": unknown, "after": self.feature_two}),
                ("push", {"before": "--all", "after": self.feature_two}),
                ("pull_request", {}),
                ("pull_request", self.pr(unknown, self.feature_two)),
                ("pull_request", self.pr(self.main, unknown))):
            with self.subTest(event=event, payload=payload):
                self.assert_rejected(event, payload)

    def test_unrelated_histories_fail_closed(self):
        unrelated = self.commit("unrelated root")
        for event, payload in (("push", {"before": unrelated, "after": self.feature_two}),
                               ("pull_request", self.pr(unrelated, self.feature_two))):
            with self.subTest(event=event):
                self.assert_rejected(event, payload)
        self.git("update-ref", "refs/remotes/origin/main", unrelated)
        self.assert_rejected("push", {"before": ZERO_SHA, "after": self.feature_two})
        self.assert_rejected("workflow_dispatch", {})

    def test_pull_request_merge_must_contain_the_event_head_as_its_second_parent(self):
        other_head = self.commit("other PR", self.base)
        merge = self.commit("different PR merge", self.main, other_head)
        self.checkout(merge)
        self.assert_rejected("pull_request", self.pr(self.main, self.feature_two))

    def test_pull_request_merge_base_must_follow_the_event_base_ancestry(self):
        other_base = self.commit("unrelated base branch", self.base)
        merge = self.commit("PR merge from a sibling base", other_base, self.feature_two)
        self.checkout(merge)
        self.assert_rejected("pull_request", self.pr(self.main, self.feature_two))

    def test_dispatch_without_a_main_ref_or_commit_parent_fails_closed(self):
        self.git("update-ref", "-d", "refs/remotes/origin/main")
        self.assert_rejected("workflow_dispatch", {})
        self.assert_rejected("push", {"before": ZERO_SHA, "after": self.feature_two})
        self.git("update-ref", "refs/remotes/origin/main", self.root)
        self.checkout(self.root)
        self.assert_rejected("workflow_dispatch", {})

    def test_empty_pull_request_head_range_fails_closed(self):
        self.checkout(self.main)
        self.assert_rejected("pull_request", self.pr(self.main, self.main))

    def test_unsupported_event_fails_closed(self):
        self.assert_rejected("repository_dispatch", {})

    def test_malformed_or_missing_event_file_never_publishes_a_range(self):
        event_path = self.repo.parent / "event.json"
        for body in (None, "{malformed", "[]"):
            with self.subTest(body=body):
                if body is None:
                    event_path.unlink(missing_ok=True)
                else:
                    event_path.write_text(body, encoding="utf-8")
                result = subprocess.run([sys.executable, "-B", str(SCRIPT),
                                         "--event-name", "push", "--event-path", str(event_path)],
                                        cwd=self.repo, env=self.env, capture_output=True,
                                        text=True, timeout=15)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("range=", result.stdout)


if __name__ == "__main__":
    unittest.main()
