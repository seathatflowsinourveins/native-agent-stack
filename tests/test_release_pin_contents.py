"""The release a new machine checks out must be self-consistent, and main must say when a new one is due.

Step 0 checks out adoption/manifest.json source.release_tag; the reader then follows the documents in
that checkout. So the pinned release must contain every path its own new-machine documents reference
(hard test). Main's documents may already describe unreleased steps; scripts/release_due.py reports
those paths, and is strict only on a re-pin (validate.yml) or before cutting a release, so a feature
PR that documents a new script is not blocked. Found by the cross-session readiness audit on
2026-09-23: main pinned v2026.09.22.1 while its steps referenced scripts added later.
"""
from __future__ import annotations

import json
import os
import unittest
from pathlib import Path

from scripts import release_due as rd

ROOT = Path(__file__).resolve().parents[1]
IN_CI = os.environ.get("GITHUB_ACTIONS") == "true"


class ReleasePinContentsTests(unittest.TestCase):
    def setUp(self):
        self.tag, self.commit = rd.pin((ROOT / "adoption/manifest.json").read_text(encoding="utf-8"))
        if rd.git("cat-file", "-e", f"{self.commit}^{{commit}}").returncode:
            if IN_CI:  # validate.yml checks out full history, so absence there is a real failure
                self.fail(f"release commit {self.commit} ({self.tag}) is not in the CI clone")
            self.skipTest(f"release commit {self.commit} ({self.tag}) is not in this clone")

    def test_tag_resolves_to_the_pinned_commit(self):
        tagged = rd.git("rev-parse", "--verify", "--quiet", f"{self.tag}^{{commit}}")
        if tagged.returncode:
            if IN_CI:
                self.fail(f"{self.tag} is not in the CI clone")
            self.skipTest(f"{self.tag} is not in this clone")
        self.assertEqual(tagged.stdout.strip(), self.commit)

    def test_pinned_release_is_self_consistent(self):
        paths = rd.commit_paths(self.commit)
        self.assertIn("adoption/bootstrap.md", paths)
        missing = sorted(p for p in paths if not rd.ignored(p) and not rd.at_commit(self.commit, p))
        self.assertEqual(missing, [], f"{self.tag}'s own new-machine documents reference paths it does not contain")

    def test_release_due_report_runs_and_is_not_strict_by_default(self):
        self.assertEqual(rd.main([]), 0)
        self.assertIsInstance(rd.due(self.commit), list)

    def test_an_old_pin_would_be_reported_as_due(self):
        old = "bdd04ca50eb781f8366c955f481479b7a7f57cbd"  # v2026.09.22.1, before host receipts and hardware profiles
        if rd.git("cat-file", "-e", f"{old}^{{commit}}").returncode:
            self.skipTest("v2026.09.22.1 is not in this clone")
        self.assertIn("scripts/component_matrix.py", rd.due(old))


class ReleaseDueUnitTests(unittest.TestCase):
    def test_path_pattern_covers_templates_workflows_and_tests(self):
        text = ("run adoption/launchd/agent.plist.template and .github/workflows/validate.yml, "
                "tests/test_x.py, tools/adoption/render_launchd.py, docs/notes.txt")
        self.assertEqual(rd.referenced([text]), {
            "adoption/launchd/agent.plist.template", ".github/workflows/validate.yml", "tests/test_x.py",
            "tools/adoption/render_launchd.py", "docs/notes.txt"})

    def test_start_here_section_is_extracted(self):
        self.assertIn("adoption/bootstrap.md", rd.referenced([rd.start_here_section(
            (ROOT / "README.md").read_text(encoding="utf-8"))]))

    def test_pin_parses_the_manifest_source(self):
        tag, commit = rd.pin(json.dumps({"source": {"release_tag": "vX", "release_commit": "a" * 40}}))
        self.assertEqual((tag, commit), ("vX", "a" * 40))


if __name__ == "__main__":
    unittest.main()
