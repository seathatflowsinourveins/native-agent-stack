"""Keep security-scan.yml's OSV-Scanner inventory complete (docs/decisions/2026-09-22-github-automation-closure.md).

.github/osv-scanner-lockfiles.json is the one checked-in list of files the osv-scanner job
scans. These tests fail when a tracked lockfile or manifest is missing from it, when a listed
file no longer exists, when a parser name is not one OSV-Scanner v2 accepts for that file, and
when an ignore in .github/osv-scanner.toml lacks an id, a reason or an ignoreUntil at most 90
days away.
"""

from datetime import date, timedelta
from pathlib import Path
import json
import os
import re
import subprocess
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / ".github/osv-scanner-lockfiles.json"
CONFIG = ROOT / ".github/osv-scanner.toml"
WORKFLOW = ROOT / ".github/workflows/security-scan.yml"
# Dependency lockfile and manifest names in this repository or supported by OSV-Scanner v2's
# source extractors (docs/supported_languages_and_lockfiles.md at v2.6.0).
TRACKED = re.compile(
    r"(?:^|/)(?:"
    r"requirements[^/]*\.(?:txt|in)|[^/]*constraints[^/]*\.txt|[^/]*\.lock|[^/]*\.lock\.txt"
    r"|[^/]*packages\.lock\.json|packages\.config|[^/]*\.deps\.json|uv\.lock|pylock(?:\.[^/]+)?\.toml"
    r"|poetry\.lock|pdm\.lock|Pipfile(?:\.lock)?|pnpm-lock\.yaml|package-lock\.json|yarn\.lock"
    r"|bun\.lock|package\.json|pyproject\.toml|go\.mod|Cargo\.lock|Gemfile\.lock|gems\.locked"
    r"|composer\.lock|pom\.xml|[^/]*gradle\.lockfile|mix\.lock|pubspec\.lock|renv\.lock|conan\.lock"
    r")$"
)
# File names OSV-Scanner infers without a parser prefix, and the parsers this inventory uses.
INFERRED = {"requirements.txt", "uv.lock", "pnpm-lock.yaml", "packages.lock.json"}
PARSERS = {"requirements.txt", "packages.lock.json"}


def tracked_files():
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    listing = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "-z"], env=environment,
        capture_output=True, check=True,
    )
    return {os.fsdecode(item) for item in listing.stdout.split(b"\0") if item}


class LockfileInventoryTests(unittest.TestCase):
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))

    def listed(self):
        return [entry["path"] for entry in self.inventory["lockfiles"]]

    def covered(self):
        return [entry["path"] for entry in self.inventory["covered_by_lockfile"]]

    def test_every_tracked_lockfile_and_manifest_is_listed(self):
        try:
            files = tracked_files()
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("not a Git checkout; the listed paths are still checked below")
        expected = sorted(path for path in files if TRACKED.search(path))
        self.assertGreater(len(expected), 0)
        missing = sorted(set(expected) - set(self.listed()) - set(self.covered()))
        self.assertEqual(missing, [], "add these to .github/osv-scanner-lockfiles.json")

    def test_entries_are_unique_existing_files(self):
        paths = self.listed() + self.covered()
        self.assertEqual(len(paths), len(set(paths)), "duplicate inventory entry")
        for path in paths:
            self.assertTrue((ROOT / path).is_file(), f"{path} is listed but missing")

    def test_parsers_are_explicit_where_osv_cannot_infer_them(self):
        for entry in self.inventory["lockfiles"]:
            name = entry["path"].rsplit("/", 1)[-1]
            parser = entry.get("parser")
            if parser is None:
                self.assertIn(name, INFERRED, f"{entry['path']} needs an explicit parser")
            else:
                self.assertIn(parser, PARSERS, entry["path"])
                if parser == "packages.lock.json":
                    self.assertTrue(name.endswith("packages.lock.json"), entry["path"])

    def test_manifests_without_an_extractor_point_at_a_scanned_lockfile(self):
        listed = set(self.listed())
        for entry in self.inventory["covered_by_lockfile"]:
            self.assertIn(entry["lockfile"], listed, entry["path"])
            self.assertEqual(entry["path"].rsplit("/", 1)[0], entry["lockfile"].rsplit("/", 1)[0])

    def test_workflow_scans_the_inventory_with_the_config(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn(".github/osv-scanner-lockfiles.json", text)
        self.assertIn("--config .github/osv-scanner.toml", text)
        self.assertIn("--no-resolve", text)


class IgnorePolicyTests(unittest.TestCase):
    def test_every_ignore_has_id_reason_and_a_near_expiry(self):
        config = tomllib.loads(CONFIG.read_text(encoding="utf-8"))
        latest = date.today() + timedelta(days=90)
        for entry in config.get("IgnoredVulns", []):
            self.assertTrue(entry.get("id"), entry)
            self.assertTrue(str(entry.get("reason", "")).strip(), entry)
            until = entry.get("ignoreUntil")
            self.assertIsInstance(until, date, f"{entry.get('id')}: ignoreUntil must be a TOML date")
            if hasattr(until, "date"):
                until = until.date()
            self.assertLessEqual(until, latest, f"{entry.get('id')}: ignoreUntil more than 90 days away")


if __name__ == "__main__":
    unittest.main()
