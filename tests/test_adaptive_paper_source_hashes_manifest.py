"""Enforces that blueprints/us-equities/adaptive-paper/source-hashes.json
really is a file-path -> sha256 map: every key must be an existing repo file
whose current content hashes to exactly the recorded value, and no other
keys may appear.

Round-7 security-config follow-up: `.gitleaks.toml` carries a dedicated,
line-anchored allowlist for this exact file (a real content digest under a
repo-path-shaped key would otherwise trip the generic-api-key rule, since
several of this module's own paths contain the word "credential"). That
allowlist alone does not stop a real secret from being smuggled into this
file under a filename-shaped key -- this test does: any entry that is not
that path's own current sha256, or any key that is not a real path under
`blueprints/us-equities/adaptive-paper/` or `tests/`, fails here.

Stdlib only (hashlib, json, re, unittest, pathlib) -- no `nautilus_trader`,
no `alpaca`, no third-party package at all -- so this runs unmodified in
CI's system-python "Test validation failure modes" step
(`.github/workflows/validate.yml`'s bare `python3 -m unittest`, which has
neither installed), not only in the pinned adaptive-paper runtime.
"""
from __future__ import annotations

import hashlib
import json
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = REPO_ROOT / "blueprints/us-equities/adaptive-paper/source-hashes.json"

# Matches .gitleaks.toml's dedicated allowlist regex for this exact file
# (kept in sync deliberately: a key this test accepts as a real path must be
# exactly the same shape gitleaks is told to trust as a content digest, and
# vice versa).
_KEY_RE = re.compile(r"^(?:blueprints/us-equities/adaptive-paper|tests)/(?:[A-Za-z0-9_\-][A-Za-z0-9_\-.]*/)*[A-Za-z0-9_\-][A-Za-z0-9_\-.]*\.(?:py|json|sh|txt)$")
_HEX_RE = re.compile(r"^[0-9a-f]{64}$")


class SourceHashesManifestIsHonest(unittest.TestCase):
    """A secret can never sit in this manifest without failing this test."""

    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_manifest_is_a_flat_string_to_string_object(self):
        self.assertIsInstance(self.manifest, dict)
        for key, value in self.manifest.items():
            self.assertIsInstance(key, str, key)
            self.assertIsInstance(value, str, key)

    def test_manifest_has_no_duplicate_keys(self):
        # json.loads silently keeps only the last of a duplicate key; a
        # strict object_pairs_hook catches one explicitly, so a duplicate
        # can never quietly shadow a real entry's digest with something else.
        seen = set()
        duplicates = []

        def _check_pairs(pairs):
            for key, _value in pairs:
                if key in seen:
                    duplicates.append(key)
                seen.add(key)
            return dict(pairs)

        json.loads(MANIFEST.read_text(encoding="utf-8"), object_pairs_hook=_check_pairs)
        self.assertEqual(duplicates, [], f"duplicate keys in the manifest: {duplicates}")

    def test_every_key_is_a_real_repo_path_under_adaptive_paper_or_tests(self):
        # "no other keys may appear": the manifest is scoped to exactly the
        # two directories .gitleaks.toml's dedicated allowlist trusts.
        bad = sorted(key for key in self.manifest if not _KEY_RE.match(key))
        self.assertEqual(bad, [], f"keys that are not adaptive-paper/tests .py/.json repo paths: {bad}")

    def test_every_value_is_exactly_64_lowercase_hex(self):
        bad = {key: value for key, value in self.manifest.items() if not _HEX_RE.match(value)}
        self.assertEqual(bad, {}, f"values that are not exactly 64 lowercase hex characters: {bad}")

    def test_every_entry_is_the_named_files_actual_sha256(self):
        missing = []
        mismatched = {}
        for key, expected in self.manifest.items():
            path = REPO_ROOT / key
            if not path.is_file():
                missing.append(key)
                continue
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual != expected:
                mismatched[key] = {"expected": expected, "actual": actual}
        self.assertEqual(missing, [], f"manifest keys with no matching file on disk: {missing}")
        self.assertEqual(mismatched, {},
                         f"manifest entries whose recorded sha256 does not match the file's actual content: "
                         f"{mismatched}")


if __name__ == "__main__":
    unittest.main()


class KeyShapeRejectsDotSegments(unittest.TestCase):
    """The accepted key shape (shared with .gitleaks.toml) refuses "." and ".." segments."""

    def test_dot_and_dotdot_segments_are_refused(self):
        for key in ("tests/../scripts/validate.py", "tests/./x.py",
                    "blueprints/us-equities/adaptive-paper/../x.py", "tests/.hidden.py"):
            with self.subTest(key=key):
                self.assertIsNone(_KEY_RE.match(key))

    def test_ordinary_repo_paths_are_accepted(self):
        for key in ("tests/test_adaptive_paper_runner.py",
                    "blueprints/us-equities/adaptive-paper/native-faults/harness.py",
                    "blueprints/us-equities/adaptive-paper/config-leverage-1x.json"):
            with self.subTest(key=key):
                self.assertIsNotNone(_KEY_RE.match(key))
