"""Every claim of the memory-owner 3.1.0 run pin points at a native capture that holds it (PR #1242 fold, B3-B6).

The run pin (evidence/artifacts/memory-owner-v3.1.0-run-pin-20261017/run-pin.json) records values and cites the
capture files under outputs/ for them. These tests read each citation: the file exists, the cited lines exist, and the
cited text or digest is the value the pin states. They fail while a citation points at the wrong line, at a file that
does not hold the claim, or at a file that was never captured.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "evidence/artifacts/memory-owner-v3.1.0-run-pin-20261017"
PIN = json.loads((FOLDER / "run-pin.json").read_text(encoding="utf-8"))
RUN = PIN["proposed_run_pin"]
OUTPUTS = FOLDER / "outputs"
CITATION = re.compile(r"^(?P<path>outputs/[A-Za-z0-9._-]+)(?::(?P<first>\d+)(?:-(?P<last>\d+))?)?(?: \(.*\))?$")


def citations(value):
    """The native_capture value as a list of (file, first line, last line) triples; a file-only citation has no lines."""
    values = [value] if isinstance(value, str) else value
    found = []
    for item in values:
        match = CITATION.match(item)
        if match is None:
            raise AssertionError(f"not a capture citation: {item!r}")
        first = int(match["first"]) if match["first"] else None
        last = int(match["last"]) if match["last"] else first
        found.append((FOLDER / match["path"], first, last))
    return found


def lines_of(path):
    return path.read_text(encoding="utf-8").splitlines()


class RunPinCaptureTests(unittest.TestCase):
    def test_every_cited_capture_exists_and_has_the_cited_lines(self):
        cited = []

        def walk(node):
            if isinstance(node, dict):
                for key, value in node.items():
                    if key in ("native_capture", "receipt", "binary_receipt", "blob_at_tag_receipt"):
                        cited.extend(citations(value))
                    else:
                        walk(value)
            elif isinstance(node, list):
                for item in node:
                    walk(item)
        walk(PIN)
        self.assertGreaterEqual(len(cited), 8)
        for path, first, last in cited:
            with self.subTest(capture=path.name, lines=(first, last)):
                self.assertTrue(path.is_file(), f"{path.name} is cited and not in the tree")
                if first:
                    self.assertLessEqual(last, len(lines_of(path)), f"{path.name} has fewer lines than cited")

    def test_the_tag_resolution_citations_hold_the_tag_object_the_commit_the_tagger_date_and_the_unsigned_status(self):
        """B4: the commit is line 2 of upstream-tag-resolution.txt, not line 1; the tagger date and the unsigned status are
        in the GitHub API capture, and the citation must name both files."""
        tag = RUN["tag_resolution"]
        by_name = {path.name: (first, last) for path, first, last in citations(tag["native_capture"])}
        self.assertEqual(by_name["upstream-tag-resolution.txt"], (1, 2))
        resolution = lines_of(OUTPUTS / "upstream-tag-resolution.txt")
        self.assertEqual(resolution[0].split("\t"), [tag["annotated_tag_object"], "refs/tags/v3.1.0"])
        self.assertEqual(resolution[1].split("\t"), [tag["commit"], "refs/tags/v3.1.0^{}"])
        self.assertEqual(tag["commit"], RUN["commit"])
        self.assertIn("github-api-tag.json", by_name)
        captured = json.loads((OUTPUTS / "github-api-tag.json").read_text(encoding="utf-8"))["git_tag"]
        self.assertEqual(captured["tagger"]["date"], tag["tagger_date"])
        self.assertEqual(captured["verification"], {"reason": "unsigned", "verified": False})
        self.assertIs(tag["signed"], captured["verification"]["verified"])
        self.assertEqual(captured["object"]["sha"], tag["commit"])
        self.assertEqual(captured["sha"], tag["annotated_tag_object"])

    def test_each_of_the_four_assets_github_digest_equals_a_local_sha256_in_a_capture(self):
        """B3: the pin says each asset's GitHub digest equals the local sha256; outputs/download-sha256.txt holds only the
        archive and install.sh, so the two sidecars' local sha256 are recorded in outputs/sidecar-sha256.txt."""
        assets = {a["name"]: a["digest"].removeprefix("sha256:")
                  for a in json.loads((OUTPUTS / "github-api-release-assets.json").read_text(encoding="utf-8"))["assets"]}
        self.assertEqual(sorted(assets), ["ai-memory-linux-x86_64.tar.gz", "ai-memory-linux-x86_64.tar.gz.sha256",
                                          "install.sh", "install.sh.sha256"])
        local = {}
        for name in ("download-sha256.txt", "sidecar-sha256.txt"):
            for line in lines_of(OUTPUTS / name):
                digest, asset = line.split("  ")
                local[asset] = digest
        self.assertEqual(local, assets)
        self.assertEqual(len(lines_of(OUTPUTS / "download-sha256.txt")), 2)
        self.assertEqual(len(lines_of(OUTPUTS / "sidecar-sha256.txt")), 2)
        note = next(source["note"] for source in PIN["sources"] if source.get("native_capture") == "outputs/github-api-release-assets.json")
        self.assertIn("outputs/download-sha256.txt", note)
        self.assertIn("outputs/sidecar-sha256.txt", note)

    def test_the_install_script_blob_at_the_tagged_commit_is_captured_with_its_digest(self):
        """B5: the pin says install.sh equals the blob at the tagged commit, read through the GitHub contents API; a capture
        file holds that read."""
        script = RUN["install_script"]
        self.assertIn("contents API", script["verification"])
        receipt = {path.name: (first, last) for path, first, last in citations(script["blob_at_tag_receipt"])}
        self.assertEqual(receipt, {"install-script-blob-at-tag.txt": (1, 3)})
        blob = lines_of(OUTPUTS / "install-script-blob-at-tag.txt")
        self.assertEqual(blob[0].split("  ")[0], script["sha256"])
        self.assertIn(RUN["commit"], blob[0])
        self.assertEqual(blob[1], f"bytes {script['bytes']}")
        self.assertIn("identical to the release asset install.sh", blob[2])

    def test_each_capture_script_names_itself_in_its_usage_line(self):
        """B6: capture.sh's usage line named capture_v310.sh, a file that does not exist."""
        for name in ("capture.sh", "capture-supplement.sh"):
            with self.subTest(script=name):
                usage = [line for line in lines_of(FOLDER / name) if line.startswith("# Usage: ")]
                self.assertEqual(len(usage), 1)
                self.assertTrue(usage[0].startswith(f"# Usage: {name} "), usage[0])
                self.assertNotIn("capture_v310", (FOLDER / name).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
