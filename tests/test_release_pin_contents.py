"""The release a new machine checks out must contain everything the new-machine steps call.

Step 0 of README.md "Start here" and adoption/bootstrap.md check out adoption/manifest.json
source.release_tag. A reader follows the new-machine documents as written on main (README "Start
here", adoption/bootstrap.md, adoption/README.md, adoption/platforms/*.md, docs/next-host-stages.md,
docs/contributing-evidence.md), so every repository path they reference must exist at
source.release_commit. When this fails, cut a new release tag and
re-pin source.release_tag/release_commit (see docs/grand-catalog-handbook.md), or move the new step
behind a release that has it. Found by the cross-session readiness audit on 2026-09-23: main pinned
v2026.09.22.1 while its steps referenced scripts added later.
"""
from __future__ import annotations

import json
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH_RE = re.compile(r"\b((?:scripts|tools|adoption|docs|recipes|catalogs)/[A-Za-z0-9_./-]+\.(?:py|sh|md|json|toml))\b")


def start_here_section(text: str) -> str:
    match = re.search(r"^## Start here\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    return match.group(1) if match else ""


# The documents a new machine follows after step 0 (all read from main as written).
NEW_HOST_DOCS = ("adoption/bootstrap.md", "adoption/README.md", "docs/next-host-stages.md",
                 "docs/contributing-evidence.md")


def referenced_paths() -> set[str]:
    sources = [start_here_section((ROOT / "README.md").read_text(encoding="utf-8"))]
    docs = [ROOT / d for d in NEW_HOST_DOCS] + sorted((ROOT / "adoption/platforms").glob("*.md"))
    sources += [d.read_text(encoding="utf-8") for d in docs if d.exists()]
    return {m for text in sources for m in PATH_RE.findall(text)}


class ReleasePinContentsTests(unittest.TestCase):
    def test_start_here_section_exists_and_references_paths(self):
        self.assertTrue(start_here_section((ROOT / "README.md").read_text(encoding="utf-8")).strip())
        self.assertIn("adoption/bootstrap.md", referenced_paths())

    def test_pinned_release_contains_every_path_the_new_machine_steps_reference(self):
        source = json.loads((ROOT / "adoption/manifest.json").read_text(encoding="utf-8"))["source"]
        commit, tag = source["release_commit"], source["release_tag"]
        if subprocess.run(["git", "-C", str(ROOT), "cat-file", "-e", f"{commit}^{{commit}}"],
                          capture_output=True).returncode:
            self.skipTest(f"release commit {commit} ({tag}) is not in this clone")
        tagged = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--verify", "--quiet", f"{tag}^{{commit}}"],
                                capture_output=True, text=True)
        if tagged.returncode == 0:
            self.assertEqual(tagged.stdout.strip(), commit, f"{tag} must resolve to source.release_commit")
        missing = []
        for rel in sorted(referenced_paths()):
            if not (ROOT / rel).exists():
                continue  # a path that does not exist on main either is not a callable step
            if subprocess.run(["git", "-C", str(ROOT), "cat-file", "-e", f"{commit}:{rel}"],
                              capture_output=True).returncode:
                missing.append(rel)
        self.assertEqual(missing, [], f"{tag} ({commit[:7]}) lacks paths the new-machine steps reference; "
                                      "cut a new release tag and re-pin adoption/manifest.json source.release_tag/release_commit")


if __name__ == "__main__":
    unittest.main()
