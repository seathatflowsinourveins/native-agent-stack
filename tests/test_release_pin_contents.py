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
    """release_due reported "current" while new-machine files (the shipped guard, the bounded runner,
    bootstrap.md, recipes/README.md ...) differed from v2026.09.23.1 (readiness sweep, 2026-09-24).
    A throwaway repository with a copy of the script: the release is its first commit, main is the
    next commit, which re-pins adoption/manifest.json to the release."""

    MANIFEST = {"updated_at": "2026-01-01", "default_profile": "cpu",
                "source": {"release_tag": "vT", "release_commit": "0" * 40}}

    def setUp(self):
        self.repo = Path(tempfile.mkdtemp(prefix="release-due-drift-"))
        self.addCleanup(shutil.rmtree, self.repo, True)
        files = {
            "README.md": "# Catalog\n\n## Start here\n\nFollow adoption/bootstrap.md.\n\n## Other\n\nNotes.\n",
            "adoption/bootstrap.md": ("Run `scripts/tool.py`, then read docs/next-host-stages.md.\n"
                                      "Run adoption/tools/runner, see [the sums](hooks/SHA256SUMS).\n"
                                      "Profiles live in adoption/manifest.json; hashes in "
                                      "[the index](../manifests/evidence.json). Install per "
                                      "adoption/tools/README.md.\n"),
            "adoption/tools/README.md": "Install adoption/tools/guarded with install -m 0755.\n",
            "adoption/tools/guarded": "#!/bin/sh\necho guarded v1\n",
            "adoption/platforms/linux-wsl2.md": "Linux page.\n",
            "adoption/tools/runner": "#!/bin/sh\necho v1\n",
            "adoption/hooks/SHA256SUMS": "aaaa  guard.py\n",
            "docs/next-host-stages.md": "Stages.\n",
            "scripts/tool.py": "print('v1')\n",
            "manifests/evidence.json": "{}\n",
            "adoption/manifest.json": json.dumps(self.MANIFEST) + "\n",
        }
        for rel, text in files.items():
            self.write(rel, text)
        shutil.copy(ROOT / "scripts/release_due.py", self.repo / "scripts/release_due.py")
        self.git("init", "-q")
        self.commit("release")
        self.release = self.git("rev-parse", "HEAD").stdout.strip()
        self.repin()

    def git(self, *args):
        return subprocess.run([*GIT, "-C", str(self.repo), *args], capture_output=True, text=True, check=True)

    def write(self, rel, text):
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def commit(self, message="main"):
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", message)

    def repin(self, **changes):
        manifest = json.loads(json.dumps(self.MANIFEST))
        manifest["source"].update(release_commit=self.release)
        manifest["updated_at"] = "2026-02-02"
        manifest.update(changes)
        self.write("adoption/manifest.json", json.dumps(manifest) + "\n")
        self.write("manifests/evidence.json", '{"files": ["re-registered"]}\n')
        self.commit("re-pin")

    def report(self, *args, env=None):
        proc = subprocess.run([sys.executable, str(self.repo / "scripts/release_due.py"), *args],
                              capture_output=True, text=True, encoding="utf-8", env=env)
        return proc.returncode, json.loads(proc.stdout)

    def test_a_re_pin_alone_is_current(self):
        # The pin fields, updated_at and manifests/evidence.json always change on a re-pin.
        self.assertEqual(self.report("--strict"), (0, {"release_tag": "vT", "release_commit": self.release,
                                                       "due": [], "changed": [], "strict": True,
                                                       "status": "current"}))

    def test_a_changed_script_is_reported_and_strict_fails(self):
        self.write("scripts/tool.py", "print('v2')\n")
        self.commit()
        code, report = self.report()
        self.assertEqual((code, report["status"], report["changed"], report["due"]),
                         (0, "content_changed", ["scripts/tool.py"], []))
        self.assertEqual(self.report("--strict")[0], 1)

    def test_changed_pages_and_the_start_here_section_are_reported(self):
        self.write("adoption/platforms/linux-wsl2.md", "Linux page, new step.\n")
        self.write("docs/next-host-stages.md", "Stages, updated.\n")
        self.write("README.md", "# Catalog\n\n## Start here\n\nFollow adoption/bootstrap.md.\n\n## Other\n\nMore.\n")
        self.commit()
        self.assertEqual(self.report()[1]["changed"], ["adoption/platforms/linux-wsl2.md", "docs/next-host-stages.md"])
        self.write("README.md", "# Catalog\n\n## Start here\n\nFollow adoption/bootstrap.md first.\n")
        self.commit()
        self.assertIn(rd.START_HERE, self.report()[1]["changed"])

    def test_extensionless_files_named_by_bare_path_or_link_are_compared(self):
        self.write("adoption/tools/runner", "#!/bin/sh\necho v2\n")
        self.write("adoption/hooks/SHA256SUMS", "bbbb  guard.py\n")
        self.commit()
        self.assertEqual(self.report()[1]["changed"], ["adoption/hooks/SHA256SUMS", "adoption/tools/runner"])

    def test_a_non_ascii_start_here_section_is_read_as_utf8_in_any_locale(self):
        # README's Start here section has em dashes; the git output was decoded with the locale codec.
        self.write("README.md", "# Catalog\n\n## Start here\n\nFollow adoption/bootstrap.md \u2014 then run.\n")
        self.commit()
        env = {**os.environ, "LC_ALL": "C", "PYTHONUTF8": "0", "PYTHONCOERCECLOCALE": "0", "PYTHONIOENCODING": "utf-8"}
        self.assertEqual(self.report(env=env)[1]["changed"], [rd.START_HERE])

    def test_a_file_named_only_by_a_referenced_install_guide_is_compared(self):
        self.write("adoption/tools/guarded", "#!/bin/sh\necho guarded v2\n")
        self.commit()
        self.assertEqual(self.report()[1]["changed"], ["adoption/tools/guarded"])

    def test_a_mode_or_kind_change_is_drift_even_with_the_same_bytes(self):
        (self.repo / "adoption/tools/runner").chmod(0o755)
        self.commit()
        self.assertEqual(self.report()[1]["changed"], ["adoption/tools/runner"])
        target = self.repo / "scripts/tool-v1.py"
        target.write_text("print('v1')\n", encoding="utf-8")
        (self.repo / "scripts/tool.py").unlink()
        (self.repo / "scripts/tool.py").symlink_to("tool-v1.py")
        self.commit()
        self.assertIn("scripts/tool.py", self.report()[1]["changed"])

    def test_the_manifest_is_compared_without_its_pin_fields(self):
        self.repin(default_profile="gpu")
        self.assertEqual(self.report()[1]["changed"], ["adoption/manifest.json"])

    def test_a_missing_path_or_platform_page_is_due_and_takes_precedence(self):
        self.write("adoption/bootstrap.md", (self.repo / "adoption/bootstrap.md").read_text(encoding="utf-8")
                   + "Then run `scripts/new.py`.\n")
        self.write("scripts/new.py", "print('new')\n")
        self.write("adoption/platforms/macos-arm64.md", "A new platform page.\n")
        self.commit()
        code, report = self.report("--strict")
        self.assertEqual((code, report["status"], report["due"], report["changed"]),
                         (1, "release_due", ["adoption/platforms/macos-arm64.md", "scripts/new.py"],
                          ["adoption/bootstrap.md"]))

    def test_strict_if_repinned_is_strict_only_after_a_re_pin(self):
        self.write("scripts/tool.py", "print('v2')\n")
        self.commit("a script change")
        self.assertEqual(self.report("--strict-if-repinned", self.release)[0], 1)  # the base pins 000...0
        self.assertEqual(self.report("--strict-if-repinned", "HEAD")[0], 0)  # same pin: report only


if __name__ == "__main__":
    unittest.main()
