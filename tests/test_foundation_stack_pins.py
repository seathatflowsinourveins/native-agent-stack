"""docs/foundation-stack.md names the component pins of manifests/stack.json.

Found by the 2026-09-26 review of a living-document sweep: the page's table had been corrected
to the manifest pins, but its release-archive example still read `gh release view v2.3.2 --repo
akitaonrails/ai-memory` after the Linux pin had moved to 2.4.1. Every GitHub release link and every
`gh release view` example on the page must name the manifest version of the component whose
repository it points at. Earlier versions stay in dated prose, never in a link or a command.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs/foundation-stack.md"
REPOSITORY = re.compile(r"https://github\.com/([\w.-]+/[\w.-]+)")
RELEASE_LINK = re.compile(r"https://github\.com/([\w.-]+/[\w.-]+)/releases/tag/v?(\d[\w.-]*)")
RELEASE_VIEW = re.compile(r"gh release view v?(\d[\w.-]*) --repo ([\w.-]+/[\w.-]+)")


def manifest_pins(components: list[dict]) -> dict[str, set[str]]:
    """{owner/repo in lower case: versions} for the components whose repository is on GitHub."""
    pins: dict[str, set[str]] = {}
    for component in components:
        match = REPOSITORY.match(component.get("repository", ""))
        if match and component.get("version"):
            pins.setdefault(match.group(1).lower(), set()).add(component["version"])
    return pins


def cited_releases(text: str) -> list[tuple[str, str]]:
    """(owner/repo, version) for each release link and each `gh release view` command."""
    return RELEASE_LINK.findall(text) + [(repo, version) for version, repo in RELEASE_VIEW.findall(text)]


def mismatches(text: str, pins: dict[str, set[str]]) -> list[str]:
    return [f"{repo} {version} (manifest: {', '.join(sorted(pins[repo.lower()]))})"
            for repo, version in cited_releases(text)
            if repo.lower() in pins and version not in pins[repo.lower()]]


class FoundationStackPinTests(unittest.TestCase):
    def test_release_links_and_commands_name_the_manifest_pins(self):
        pins = manifest_pins(json.loads((ROOT / "manifests/stack.json").read_text(encoding="utf-8"))["components"])
        text = DOC.read_text(encoding="utf-8")
        known = [repo for repo, _ in cited_releases(text) if repo.lower() in pins]
        self.assertIn("akitaonrails/ai-memory", known)
        self.assertIn("vllm-project/vllm", known)
        self.assertEqual(mismatches(text, pins), [])

    def test_the_check_rejects_an_older_release_in_a_link_or_a_command(self):
        pins = manifest_pins([{"repository": "https://github.com/example/tool/releases/tag/v2.4.1", "version": "2.4.1"}])
        self.assertEqual(pins, {"example/tool": {"2.4.1"}})
        current = ("[tool 2.4.1](https://github.com/example/tool/releases/tag/v2.4.1)\n"
                   "gh release view v2.4.1 --repo example/tool --json tagName,assets\n"
                   "[other](https://github.com/example/other/releases/tag/v9.9.9)\n")
        self.assertEqual(mismatches(current, pins), [])
        self.assertEqual(mismatches("gh release view v2.3.2 --repo example/tool --json tagName", pins),
                         ["example/tool 2.3.2 (manifest: 2.4.1)"])
        self.assertEqual(mismatches("[tool](https://github.com/Example/Tool/releases/tag/v2.3.2)", pins),
                         ["Example/Tool 2.3.2 (manifest: 2.4.1)"])


if __name__ == "__main__":
    unittest.main()
