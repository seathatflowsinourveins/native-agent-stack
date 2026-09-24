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
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts import release_due as rd

ROOT = Path(__file__).resolve().parents[1]
IN_CI = os.environ.get("GITHUB_ACTIONS") == "true"
GIT = ("git", "-c", "user.name=release-due-test", "-c", "user.email=release-due-test@example.invalid",
       "-c", "commit.gpgsign=false", "-c", "core.autocrlf=false")


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


class ReleaseDueContentDriftTests(unittest.TestCase):
    """release_due reported "current" while ten new-machine files (the shipped guard, bootstrap.md,
    recipes/README.md ...) differed from v2026.09.23.1 (readiness sweep, 2026-09-24). A throwaway
    repository with a copy of the script: the release is its first commit, main is the working tree."""

    def setUp(self):
        self.repo = Path(tempfile.mkdtemp(prefix="release-due-drift-"))
        self.addCleanup(shutil.rmtree, self.repo, True)
        files = {
            "README.md": "# Catalog\n\n## Start here\n\nFollow adoption/bootstrap.md.\n\n## Other\n\nNotes.\n",
            "adoption/bootstrap.md": "Run `scripts/tool.py`, then read docs/next-host-stages.md.\n",
            "adoption/platforms/linux-wsl2.md": "Linux page.\n",
            "docs/next-host-stages.md": "Stages.\n",
            "scripts/tool.py": "print('v1')\n",
            "manifests/evidence.json": "{}\n",
            "adoption/manifest.json": json.dumps({"source": {"release_tag": "vT", "release_commit": "0" * 40}}) + "\n",
        }
        for rel, text in files.items():
            self.write(rel, text)
        shutil.copy(ROOT / "scripts/release_due.py", self.repo / "scripts/release_due.py")
        self.git("init", "-q")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "release")
        self.release = self.git("rev-parse", "HEAD").stdout.strip()
        self.write("adoption/manifest.json",
                   json.dumps({"source": {"release_tag": "vT", "release_commit": self.release}}) + "\n")

    def git(self, *args):
        return subprocess.run([*GIT, "-C", str(self.repo), *args], capture_output=True, text=True, check=True)

    def write(self, rel, text):
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def report(self, *args):
        proc = subprocess.run([sys.executable, str(self.repo / "scripts/release_due.py"), *args],
                              capture_output=True, text=True)
        return proc.returncode, json.loads(proc.stdout)

    def test_a_re_pin_alone_is_current(self):
        # adoption/manifest.json (the pin) and manifests/evidence.json always change on a re-pin.
        self.write("manifests/evidence.json", '{"files": []}\n')
        self.assertEqual(self.report("--strict"), (0, {"release_tag": "vT", "release_commit": self.release,
                                                       "due": [], "changed": [], "strict": True,
                                                       "status": "current"}))

    def test_a_changed_script_is_reported_and_strict_fails(self):
        self.write("scripts/tool.py", "print('v2')\n")
        code, report = self.report()
        self.assertEqual((code, report["status"], report["changed"], report["due"]),
                         (0, "content_changed", ["scripts/tool.py"], []))
        self.assertEqual(self.report("--strict")[0], 1)

    def test_changed_pages_and_the_start_here_section_are_reported(self):
        self.write("adoption/platforms/linux-wsl2.md", "Linux page, new step.\n")
        self.write("docs/next-host-stages.md", "Stages, updated.\n")
        self.write("README.md", "# Catalog\n\n## Start here\n\nFollow adoption/bootstrap.md.\n\n## Other\n\nMore.\n")
        self.assertEqual(self.report()[1]["changed"], ["adoption/platforms/linux-wsl2.md", "docs/next-host-stages.md"])
        self.write("README.md", "# Catalog\n\n## Start here\n\nFollow adoption/bootstrap.md first.\n")
        self.assertIn(rd.START_HERE, self.report()[1]["changed"])

    def test_a_missing_path_is_still_due_and_takes_precedence(self):
        self.write("adoption/bootstrap.md", "Run `scripts/tool.py` and `scripts/new.py`.\n")
        self.write("scripts/new.py", "print('new')\n")
        code, report = self.report("--strict")
        self.assertEqual((code, report["status"], report["due"], report["changed"]),
                         (1, "release_due", ["scripts/new.py"], ["adoption/bootstrap.md"]))

    def test_strict_if_repinned_is_strict_only_after_a_re_pin(self):
        self.write("scripts/tool.py", "print('v2')\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "re-pin plus a script change")
        self.assertEqual(self.report("--strict-if-repinned", self.release)[0], 1)  # the base pins 000...0
        self.assertEqual(self.report("--strict-if-repinned", "HEAD")[0], 0)  # same pin: report only


if __name__ == "__main__":
    unittest.main()
