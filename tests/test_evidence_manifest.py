"""Tests for scripts/evidence_manifest.py: the manifests/evidence.json
files[] sort normalizer/checker."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from scripts import evidence_manifest as em


class EvidenceManifestSortTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "manifests").mkdir(parents=True)
        self.evidence = {
            "schema_version": 1,
            "receipts": [{"id": "sample"}],
            "files": [
                {"path": "z-later.json", "sha256": "a" * 64, "bytes": 1},
                {"path": "a-earlier.json", "sha256": "b" * 64, "bytes": 2},
                {"path": "m-middle.json", "sha256": "c" * 64, "bytes": 3},
            ],
            "convergence_records": [],
        }
        self.write()

    def write(self):
        (self.root / "manifests" / "evidence.json").write_text(
            json.dumps(self.evidence, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    def load(self):
        return json.loads((self.root / "manifests" / "evidence.json").read_text(encoding="utf-8"))

    def test_check_fails_on_unsorted_manifest(self):
        self.assertEqual(em.main(["--root", str(self.root), "--check"]), 1)

    def test_write_sorts_by_path_and_preserves_entry_fields_and_other_keys(self):
        exit_code = em.main(["--root", str(self.root), "--write"])
        self.assertEqual(exit_code, 0)
        data = self.load()
        self.assertEqual([entry["path"] for entry in data["files"]],
                          ["a-earlier.json", "m-middle.json", "z-later.json"])
        by_path = {entry["path"]: entry for entry in data["files"]}
        self.assertEqual(by_path["z-later.json"], {"path": "z-later.json", "sha256": "a" * 64, "bytes": 1})
        self.assertEqual(list(data.keys()), ["schema_version", "receipts", "files", "convergence_records"])

    def test_check_passes_after_write(self):
        self.assertEqual(em.main(["--root", str(self.root), "--write"]), 0)
        self.assertEqual(em.main(["--root", str(self.root), "--check"]), 0)

    def test_check_rejects_duplicate_paths_even_if_adjacent(self):
        self.evidence["files"] = [
            {"path": "a.json", "sha256": "a" * 64, "bytes": 1},
            {"path": "a.json", "sha256": "b" * 64, "bytes": 2},
        ]
        self.write()
        self.assertEqual(em.main(["--root", str(self.root), "--check"]), 1)

    def test_write_is_idempotent(self):
        em.main(["--root", str(self.root), "--write"])
        first = (self.root / "manifests" / "evidence.json").read_text(encoding="utf-8")
        em.main(["--root", str(self.root), "--write"])
        second = (self.root / "manifests" / "evidence.json").read_text(encoding="utf-8")
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
