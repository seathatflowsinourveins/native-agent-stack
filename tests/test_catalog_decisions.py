"""Canonical identity and source-pointer checks use synthetic public fixtures."""

import copy
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest

from scripts.catalog_decisions import (
    BASE, BASE_SOURCES, INDEX, MANIFEST, InvalidDecisionIndex,
    build_index, identity, main, pointer, supplement, validate_index,
)


class DecisionIndexTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.documents = {}
        for spec in BASE_SOURCES:
            self.documents[spec["path"]] = {spec["collection"].strip("/"): []}
        self.documents[f"{BASE}/coverage.json"] = {
            "aliases": {"old/project": "new/project"},
            "stars": [{"repository": "https://github.com/old/project", "disposition": "no_catalog_card"}],
        }
        self.documents[f"{BASE}/star-audit.json"]["entries"] = [{
            "repository": "https://github.com/new/project", "decision": "alternative",
            "review_depth": "readme_license_overview",
        }]
        self.documents[BASE_SOURCES[2]["path"]]["entries"] = [{
            "repository": "https://github.com/example/core", "id": "core",
            "decision": "conditional", "evidence_level": "source_review",
        }]
        self.documents["manifests/stack.json"]["components"] = [{
            "repository": "https://github.com/EXAMPLE/core/releases/tag/v1", "id": "core-runtime",
        }]
        self.documents["manifests/candidates.json"]["candidates"] = [{
            "url": "https://github.com/example/legacy", "decision": "Historical candidate only",
        }]
        self.documents["adoption/research.json"]["candidates"] = [{
            "repository": "https://github.com/example/portable", "decision": "conditional",
        }]
        for path, document in self.documents.items():
            self.write(path, document)
        self.save_index()

    def write(self, path, document):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")

    def save_index(self, specs=None):
        self.index = build_index(self.root, specs)
        self.write(INDEX, self.index)
        self.manifest = {"decision_index_file": INDEX,
                         "grand_index_repositories": self.index["counts"]["repositories"],
                         "grand_index_beyond_stars": self.index["counts"]["beyond_public_stars"]}
        self.write(MANIFEST, self.manifest)

    def test_union_deduplicates_alias_and_release_url_without_upgrading_depth(self):
        counts = validate_index(self.root)
        self.assertEqual(counts["repositories"], 4)
        self.assertEqual(counts["public_star_repositories"], 1)
        record = next(item for item in self.index["records"] if item["public_star"])
        self.assertEqual(record["repository"], "https://github.com/new/project")
        self.assertEqual(record["aliases"], ["old/project"])
        self.assertIn("readme_license_overview", json.dumps(record))
        self.assertNotIn("native_proven", json.dumps(record))
        core = next(item for item in self.index["records"] if item["repository"].endswith("/core"))
        self.assertEqual(core["record_types"], ["catalog_card", "component_record"])

    def test_multiple_explicit_supplement_collections_are_supported(self):
        self.write("research/a.json", {"repositories": [{"repository": "example/portable", "decision": "watch",
                                                       "evidence_depth": "pinned_primary_source_review"}]})
        self.write("research/b.json", {"entries": [{"repository": "https://github.com/example/new", "decision": "conditional"}]})
        with redirect_stdout(io.StringIO()):
            code = main(["--root", str(self.root), "--write",
                         "--supplement", "research/a.json#/repositories",
                         "--supplement", "research/b.json#/entries"])
        self.assertEqual(code, 0)
        self.assertEqual(validate_index(self.root)["repositories"], 5)
        self.assertEqual(validate_index(self.root)["repositories_by_record_type"]["research_supplement"], 2)
        generated = json.loads((self.root / INDEX).read_text())
        references = [ref for row in generated["records"] for ref in row["references"]
                      if ref["path"] == "research/a.json"]
        self.assertEqual(references[0]["evidence_depth"], "pinned_primary_source_review")

    def test_repository_whitespace_and_controls_are_rejected_before_url_parsing(self):
        for malformed in ("https://github.com/example/re\tpo", "https://github.com/example/repo\n",
                          " https://github.com/example/repo", "\x01https://github.com/example/repo",
                          "https://github.com/example/repo/releases/\x7f"):
            with self.subTest(value=repr(malformed)), self.assertRaises(InvalidDecisionIndex):
                identity(malformed)

    def test_unknown_collection_or_missing_repository_fails(self):
        self.write("research/new.json", {"entries": [{"name": "example/not-a-repository-field"}]})
        for selected in ("research/new.json#/missing", "research/new.json#/entries"):
            with self.subTest(selected=selected), self.assertRaises(InvalidDecisionIndex):
                build_index(self.root, BASE_SOURCES + [supplement(selected)])

    def test_unsafe_paths_and_symlink_sources_are_rejected(self):
        for path in ("../outside.json", "/tmp/outside.json", "research/../outside.json"):
            with self.subTest(path=path), self.assertRaisesRegex(InvalidDecisionIndex, "confined"):
                build_index(self.root, BASE_SOURCES + [supplement(path + "#/entries")])
        target = self.root / "linked.json"
        target.symlink_to(self.root / "adoption/research.json")
        with self.assertRaisesRegex(InvalidDecisionIndex, "symlinks"):
            build_index(self.root, BASE_SOURCES + [supplement("linked.json#/candidates")])

    def test_json_pointer_escaping_is_explicit(self):
        self.assertEqual(pointer({"a/b": {"~name": ["value"]}}, "/a~1b/~0name/0"), "value")
        for value in ("entries", "/", "/bad~2escape", "/entries/01", "/entries/4"):
            with self.subTest(value=value), self.assertRaises(InvalidDecisionIndex):
                pointer({"entries": [1]}, value)

    def test_stale_or_tampered_counts_are_rejected(self):
        self.index["counts"]["repositories"] += 1
        self.write(INDEX, self.index)
        with self.assertRaisesRegex(InvalidDecisionIndex, "counts"):
            validate_index(self.root)

    def test_wrong_record_pointer_and_fake_review_claim_fail(self):
        for field, value in (("pointer", "/entries/999"), ("evidence_level", "native_proven")):
            with self.subTest(field=field):
                data = copy.deepcopy(self.index)
                data["records"][0]["references"][0][field] = value
                self.write(INDEX, data)
                with self.assertRaisesRegex(InvalidDecisionIndex, "pointers are stale"):
                    validate_index(self.root)

    def test_duplicate_canonical_record_fails(self):
        self.index["records"].append(copy.deepcopy(self.index["records"][0]))
        self.write(INDEX, self.index)
        with self.assertRaisesRegex(InvalidDecisionIndex, "duplicate"):
            validate_index(self.root)

    def test_source_additions_cannot_float_outside_index(self):
        data = self.documents["adoption/research.json"]
        data["candidates"].append({"repository": "https://github.com/example/missing"})
        self.write("adoption/research.json", data)
        with self.assertRaisesRegex(InvalidDecisionIndex, "counts"):
            validate_index(self.root)

    def test_required_base_source_cannot_be_removed_or_reclassified(self):
        for specs in (BASE_SOURCES[1:], [{**BASE_SOURCES[0], "kind": "research_supplement"}] + BASE_SOURCES[1:]):
            with self.assertRaises(InvalidDecisionIndex):
                build_index(self.root, specs)
        with self.assertRaisesRegex(InvalidDecisionIndex, "duplicate source"):
            build_index(self.root, BASE_SOURCES + [BASE_SOURCES[0]])

    def test_alias_cycles_and_stale_alias_maps_fail(self):
        coverage = self.documents[f"{BASE}/coverage.json"]
        coverage["aliases"]["new/project"] = "old/project"
        self.write(f"{BASE}/coverage.json", coverage)
        with self.assertRaisesRegex(InvalidDecisionIndex, "alias cycle"):
            build_index(self.root)
        coverage["aliases"] = {}
        self.write(f"{BASE}/coverage.json", coverage)
        with self.assertRaisesRegex(InvalidDecisionIndex, "aliases are stale"):
            validate_index(self.root)

    def test_manifest_pointer_and_grand_counts_are_validated(self):
        for field, value in (("decision_index_file", "wrong.json"), ("grand_index_repositories", 99),
                             ("grand_index_beyond_stars", 99)):
            with self.subTest(field=field), self.assertRaises(InvalidDecisionIndex):
                validate_index(self.root, {**self.manifest, field: value})
        with self.assertRaisesRegex(InvalidDecisionIndex, "manifest must be an object"):
            validate_index(self.root, [])

    def test_duplicate_json_key_and_supplement_without_write_fail(self):
        (self.root / "adoption/research.json").write_text('{"candidates":[],"candidates":[]}')
        with self.assertRaisesRegex(InvalidDecisionIndex, "invalid source JSON"):
            build_index(self.root)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(["--root", str(self.root), "--supplement", "research/a.json#/entries"]), 1)


if __name__ == "__main__":
    unittest.main()
