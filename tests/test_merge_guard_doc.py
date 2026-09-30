"""docs/lanes.md must not read `gh pr checks --required`'s exit code as the merge verdict.

Found 2026-09-29: the documented guard said the command exits 0 only when every required check passed. gh
v2.101.0 (pkg/cmd/pr/checks/checks.go L248-252, aggregate.go L72-88) exits 0 for a cancelled required check, so
the merge read has to print the buckets. This is a local structural check of the document, not an upstream test.
"""
from pathlib import Path
import json
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
LANES = (ROOT / "docs/lanes.md").read_text(encoding="utf-8")


def merge_block():
    match = re.search(r"Merge with the checked and reviewed head pinned:\n\n```sh\n(.*?)```", LANES, re.S)
    assert match, "the merge-guard command block is missing from docs/lanes.md"
    return match.group(1)


class MergeGuardDocTests(unittest.TestCase):
    def test_the_guard_reads_buckets_not_the_exit_code(self):
        block = merge_block()
        self.assertRegex(block, r"gh pr checks <N> --required --json name,bucket")
        self.assertIn("--match-head-commit <SHA>", block)
        self.assertNotRegex(block, r"gh pr checks <N> --required\s*\n")

    def test_the_text_says_a_cancelled_check_exits_zero(self):
        text = " ".join(LANES.split())
        self.assertIn("a cancelled or skipped required check also exits 0", text)
        self.assertNotIn("exits 0 only when every required check has passed", text)
        self.assertNotIn("1 when one has failed and none is pending", text)

    def test_the_documented_count_matches_the_committed_ruleset(self):
        ruleset = json.loads((ROOT / ".github/main-ruleset.json").read_text(encoding="utf-8"))
        rule = next(item for item in ruleset["rules"] if item["type"] == "required_status_checks")
        contexts = rule["parameters"]["required_status_checks"]
        self.assertIn(f"({len(contexts)} in `.github/main-ruleset.json`)", " ".join(LANES.split()))


if __name__ == "__main__":
    unittest.main()
