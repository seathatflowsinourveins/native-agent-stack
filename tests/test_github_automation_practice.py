"""Tests for the current GitHub automation practice: the "Current practice" section of docs/github-automation.md and
the dated block of catalogs/foundation/automation.json match the committed main ruleset, the section points at the
merge guard instead of restating it, and the decision record names every pick and challenger of the three layers it
covers."""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs/github-automation.md"
MANIFEST = ROOT / "catalogs/foundation/automation.json"
RULESET = ROOT / ".github/main-ruleset.json"
RECORD = ROOT / "docs/decisions/2026-10-02-github-automation-practice.md"
HEADING = "## Current practice (2026-10-10)"


def ruleset_rule(kind: str) -> dict:
    rules = json.loads(RULESET.read_text(encoding="utf-8"))["rules"]
    return next(rule for rule in rules if rule["type"] == kind)["parameters"]


def section() -> str:
    text = DOC.read_text(encoding="utf-8")
    start = text.index(HEADING)
    end = text.index("\n## ", start + len(HEADING))
    return text[start:end]


class CurrentPracticeSectionTests(unittest.TestCase):
    def test_the_section_comes_first_and_names_every_required_check(self):
        text = DOC.read_text(encoding="utf-8")
        self.assertLess(text.index(HEADING), text.index("## Event and execution policy"))
        checks = [check["context"] for check in ruleset_rule("required_status_checks")["required_status_checks"]]
        self.assertTrue(checks)
        for check in checks:
            self.assertIn(f"`{check}`", section(), check)

    def test_the_section_states_the_merge_method_and_strict_setting_of_the_ruleset(self):
        self.assertEqual(ruleset_rule("pull_request")["allowed_merge_methods"], ["squash"])
        self.assertIn("Squash merges only", section())
        self.assertFalse(ruleset_rule("required_status_checks")["strict_required_status_checks_policy"])
        self.assertIn("strict up-to-date checks off", section())

    def test_the_section_links_the_merge_guard_and_does_not_restate_it(self):
        self.assertIn("lanes.md#labels-and-prs", section())
        self.assertNotIn("gh pr merge", section())
        self.assertNotIn("not yet live", section())

    def test_the_decision_record_link_resolves(self):
        for target in re.findall(r"\]\(([^)#]+)", section()):
            if target.startswith("http"):
                continue
            self.assertTrue((DOC.parent / target).resolve().exists(), target)


class ManifestBlockTests(unittest.TestCase):
    def setUp(self):
        self.block = json.loads(MANIFEST.read_text(encoding="utf-8"))["current_practice_20261010"]

    def test_the_block_matches_the_ruleset(self):
        checks = [check["context"] for check in ruleset_rule("required_status_checks")["required_status_checks"]]
        self.assertEqual(self.block["required_checks"], checks)
        self.assertEqual(self.block["allowed_merge_methods"], ruleset_rule("pull_request")["allowed_merge_methods"])
        self.assertEqual(self.block["strict_required_status_checks"],
                         ruleset_rule("required_status_checks")["strict_required_status_checks_policy"])

    def test_the_block_cites_an_existing_decision_record(self):
        self.assertTrue((ROOT / self.block["decision_record"]).is_file())
        self.assertEqual(self.block["merge_guard"], "docs/lanes.md#labels-and-prs")


class DecisionRecordTests(unittest.TestCase):
    # The standing picks and challengers of the final catalog of 2026-10-01 for the three layers the record covers.
    LAYERS = {
        "git-github-automation": ["git", "gh", "Worktrunk", "sem", "difftastic", "claude-code-action"],
        "ci-supply-chain": ["actions/attest", "Syft", "Dependabot", "actionlint", "zizmor", "github/codeql-action"],
        "secrets-credentials": ["betterleaks", "trufflehog"],
    }

    def test_every_pick_and_challenger_is_named_in_its_layer_row(self):
        text = RECORD.read_text(encoding="utf-8")
        for layer, names in self.LAYERS.items():
            row = next(line for line in text.splitlines() if line.startswith(f"| {layer} |"))
            for name in names:
                self.assertIn(name, row, (layer, name))

    def test_the_record_changes_no_gate_and_preregisters_each_comparison(self):
        text = RECORD.read_text(encoding="utf-8")
        self.assertIn("changes no workflow, ruleset, required check, gate or selection", text)
        for label in ("**P1, the secret-scan gate.**", "**P2, structural diffs.**", "**P3, review automation.**"):
            self.assertIn(label, text)


if __name__ == "__main__":
    unittest.main()
