"""Synthetic declarations test ownership; they establish no native acceptance.

Extend native-agent-stack@e28d0eec112527ac02659ac23753533b8ed39a73:
scripts/validate_foundation.py:50-63 and scripts/validate_catalogs.py:110-186.
JSON Schema's uniqueItems compares whole array values; projected repository
identity also needs the existing case/alias canonicalization:
https://json-schema.org/understanding-json-schema/reference/array#uniqueitems
"""

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts.validate import InvalidPublication, validate as validate_publication
from scripts.validate_catalogs import InvalidCatalog
from scripts.validate_foundation import (
    FINALIZED_SELECTION, MANIFEST, REPOSITORY_COVERAGE,
    validate_finalized_selection, validate_foundation,
)
from tests import test_foundation_catalog as foundation_fixtures
from tests import test_validate as publication_fixtures


RESEARCH = "https://github.com/vendor/research"
SDK = "https://github.com/vendor/sdk"
ALTERNATIVE = "https://github.com/vendor/sdk-alternative"
EXCLUDED = "https://github.com/vendor/retired-sdk"
DECISION = "docs/decisions/2026-10-07-finalized-sota-catalog.md"


def slot(identifier, layer_id, role, repositories, references=()):
    return {
        "id": identifier, "layer_id": layer_id, "role": role,
        "purpose": f"One bounded {role} capability.",
        "repositories": repositories, "references": list(references),
    }


def selected(repository, selection="default"):
    return {"repository": repository, "selection": selection}


class FinalizedSelectionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.manifest = {"finalized_selection_file": FINALIZED_SELECTION}
        self.coverage = {"aliases": {"old/sdk": "vendor/sdk"}}
        self.document = {
            "schema_version": 1, "status": "finalized",
            "decision_record": DECISION,
            "source_base_commit": "e28d0eec112527ac02659ac23753533b8ed39a73",
            "included_repositories": [RESEARCH, SDK, ALTERNATIVE, EXCLUDED],
            "slots": [
                slot("research-worker", "web-research", "research-worker",
                     [selected(RESEARCH)], [SDK, SDK]),
                {**slot("python-sdk", "agent-sdks", "agent-sdk", [
                    selected(SDK), selected(ALTERNATIVE, "alternative"),
                    selected(EXCLUDED, "excluded"),
                ], [RESEARCH]), "language": "python",
                 "supported_languages": ["python", "typescript"]},
            ],
        }
        self.write(DECISION, "# Synthetic decision record\n")

    def write(self, relative, value):
        target = self.root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        content = value if isinstance(value, str) else json.dumps(value)
        target.write_text(content, encoding="utf-8")

    def save(self):
        self.write(MANIFEST, self.manifest)
        self.write(REPOSITORY_COVERAGE, self.coverage)
        self.write(FINALIZED_SELECTION, self.document)

    def check(self):
        self.save()
        return validate_finalized_selection(self.root)

    def assert_invalid(self, fragment):
        with self.assertRaisesRegex(InvalidCatalog, fragment):
            self.check()

    def test_valid_final_includes_alternatives_exclusions_and_repeated_references(self):
        self.assertEqual(self.check(), {"status": "finalized", "slots": 2, "repositories": 4})
        del self.document["slots"][1]["supported_languages"]
        self.assertEqual(self.check()["repositories"], 4)

    def test_valid_pending_has_no_selections_or_claimed_census(self):
        self.document["status"] = "pending_synthesis"
        self.document["included_repositories"] = None
        for row in self.document["slots"]:
            row["repositories"] = []
        self.assertEqual(self.check(), {"status": "pending_synthesis", "slots": 2, "repositories": None})

    def test_legacy_manifest_does_not_opt_into_the_new_selection_contract(self):
        self.assertIsNone(validate_finalized_selection(self.root, {}))

    def test_pending_cannot_carry_any_selection_or_nonnull_census(self):
        original = copy.deepcopy(self.document)
        for selection in ("default", "alternative", "excluded"):
            with self.subTest(selection=selection):
                self.document = copy.deepcopy(original)
                self.document["status"] = "pending_synthesis"
                self.document["included_repositories"] = None
                self.document["slots"][0]["repositories"] = [selected(RESEARCH, selection)]
                self.assert_invalid("pending synthesis cannot declare repository selections")
        self.document["included_repositories"] = []
        self.assert_invalid("repository census null")

    def test_missing_and_multiple_defaults_fail(self):
        self.document["slots"][0]["repositories"][0]["selection"] = "alternative"
        self.assert_invalid("exactly one default")
        self.document["slots"][0]["repositories"][0]["selection"] = "default"
        self.document["slots"][1]["repositories"][1]["selection"] = "default"
        self.assert_invalid("exactly one default")

    def test_unknown_repository_selection_cannot_count_as_a_default(self):
        self.document["slots"][0]["repositories"][0]["selection"] = "candidate"
        self.assert_invalid("expected one of alternative, default, excluded")

    def test_duplicate_slot_ids_fail(self):
        self.document["slots"][1]["id"] = "research-worker"
        self.assert_invalid("duplicate ID research-worker")

    def test_repository_cannot_be_owned_twice_within_or_across_slots(self):
        for target_slot in (0, 1):
            with self.subTest(target_slot=target_slot):
                self.document["slots"][target_slot]["repositories"].append(selected(RESEARCH, "alternative"))
                self.assert_invalid("already owned by slot research-worker")
                self.document["slots"][target_slot]["repositories"].pop()

    def test_census_must_be_complete_and_independently_declared(self):
        self.document["included_repositories"].append("https://github.com/vendor/unowned")
        self.assert_invalid(r"unowned=\['vendor/unowned'\]")
        self.document["included_repositories"].pop()
        self.document["included_repositories"].remove(ALTERNATIVE)
        self.assert_invalid(r"outside_census=\['vendor/sdk-alternative'\]")
        del self.document["included_repositories"]
        self.assert_invalid("missing included_repositories")

    def test_case_and_alias_collisions_fail_in_both_ownership_and_census(self):
        for spelling in ("https://github.com/Vendor/SDK", "https://github.com/old/sdk"):
            with self.subTest(spelling=spelling, declaration="ownership"):
                self.document["slots"][0]["repositories"].append(selected(spelling, "excluded"))
                self.assert_invalid("already owned by slot")
                self.document["slots"][0]["repositories"].pop()
            with self.subTest(spelling=spelling, declaration="census"):
                self.document["included_repositories"].append(spelling)
                self.assert_invalid("duplicate canonical repository vendor/sdk")
                self.document["included_repositories"].pop()

    def test_alias_reference_resolves_without_becoming_another_owner(self):
        self.document["slots"][0]["references"].append("https://github.com/old/sdk")
        self.assertEqual(self.check()["repositories"], 4)

    def test_reference_outside_the_final_census_fails(self):
        self.document["slots"][0]["references"].append("https://github.com/vendor/unknown")
        self.assert_invalid("reference outside included repository census")

    def test_duplicate_json_keys_remain_rejected(self):
        self.save()
        self.write(FINALIZED_SELECTION, '{"schema_version": 1, "status": "finalized", "status": "pending_synthesis"}')
        with self.assertRaisesRegex(InvalidCatalog, "duplicate key status"):
            validate_finalized_selection(self.root)

    def test_nonobject_document_roots_raise_invalid_catalog(self):
        self.save()
        for value in (None, False, 0, "scalar", [], [{}]):
            with self.subTest(value=value):
                self.write(FINALIZED_SELECTION, json.dumps(value))
                with self.assertRaisesRegex(InvalidCatalog, "expected object"):
                    validate_finalized_selection(self.root)

    def test_noncanonical_repository_urls_fail(self):
        for value in ("http://github.com/vendor/research", "https://github.com/vendor/research.git",
                      "https://github.com/vendor/research.GIT", "https://github.com/vendor/research.GiT",
                      "https://github.com/vendor/research?view=1", "https://github.com/vendor/research#readme",
                      "https://github.com/vendor/research/issues"):
            with self.subTest(value=value):
                self.document["included_repositories"][0] = value
                self.assert_invalid("HTTPS URL|canonical https")

    def test_malformed_document_and_slot_stages_fail(self):
        original = copy.deepcopy(self.document)
        mutations = [
            ("schema_version", True, "schema_version must be 1"),
            ("status", "accepted", "expected one of"),
            ("source_base_commit", "e28d0eec", "full lowercase Git commit SHA"),
            ("included_repositories", None, "expected nonempty array"),
            ("slots", [], "expected nonempty array"),
            ("slots", ["bad-slot"], "expected object"),
        ]
        for key, value, fragment in mutations:
            with self.subTest(field=key, value=value):
                self.document = copy.deepcopy(original)
                self.document[key] = value
                self.assert_invalid(fragment)
        for key, value, fragment in [
            ("layer_id", "unknown", "expected one of"),
            ("role", "", "expected nonempty text"),
            ("purpose", None, "expected nonempty text"),
            ("language", None, "expected nonempty text"),
            ("supported_languages", [], "expected nonempty array"),
            ("supported_languages", ["python", "python"], "duplicate values"),
            ("supported_languages", [None], "expected nonempty text"),
            ("repositories", [False], "expected object"),
            ("references", {}, "expected array"),
        ]:
            with self.subTest(slot_field=key, value=value):
                self.document = copy.deepcopy(original)
                self.document["slots"][0][key] = value
                self.assert_invalid(fragment)

    def test_projection_and_decision_paths_keep_existing_confinement_checks(self):
        self.manifest["finalized_selection_file"] = "../selection.json"
        self.assert_invalid("canonical selection file")
        self.manifest["finalized_selection_file"] = FINALIZED_SELECTION
        self.document["decision_record"] = "../decision.md"
        self.assert_invalid("canonical, relative and confined")

    def test_existing_foundation_validator_reaches_the_opt_in_guard(self):
        fixture = foundation_fixtures.FoundationCatalogTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.manifest["finalized_selection_file"] = FINALIZED_SELECTION
        fixture.write(MANIFEST, fixture.manifest)
        fixture.write("catalogs/foundation/decisions.json", fixture.decisions)
        fixture.write(REPOSITORY_COVERAGE, self.coverage)
        fixture.write(DECISION, {})
        fixture.write(FINALIZED_SELECTION, self.document)
        self.assertEqual(validate_foundation(fixture.root)["layers"], 20)
        self.document["slots"][0]["repositories"] = []
        fixture.write(FINALIZED_SELECTION, self.document)
        with self.assertRaisesRegex(InvalidCatalog, "exactly one default"):
            validate_foundation(fixture.root)

    def test_direct_script_uses_its_own_modules_with_a_foreign_scripts_package(self):
        self.write("scripts/__init__.py", "")
        self.write("scripts/validate_foundation.py", 'raise RuntimeError("foreign validator imported")\n')
        fixture = publication_fixtures.PublicationValidationTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.write_json(MANIFEST, self.manifest)
        fixture.write_json(REPOSITORY_COVERAGE, self.coverage)
        fixture.write(DECISION, "# Synthetic decision\n")
        fixture.write_json(FINALIZED_SELECTION, self.document)
        script = Path(__file__).resolve().parents[1] / "scripts/validate.py"
        arguments = [sys.executable, str(script), "--root", str(fixture.root)]
        environment = {"PYTHONPATH": str(self.root), "PYTHONDONTWRITEBYTECODE": "1"}
        result = subprocess.run(arguments, cwd=self.root, env=environment,
                                capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout.splitlines()[0])["status"], "passed")
        self.document["slots"][0]["repositories"] = []
        fixture.write_json(FINALIZED_SELECTION, self.document)
        result = subprocess.run(arguments, cwd=self.root, env=environment,
                                capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("exactly one default", result.stdout)

    def test_cold_file_spec_import_exposes_private_patterns_without_catalog_imports(self):
        # Upstream source-file loading recipe, with no repository on sys.path:
        # https://docs.python.org/3.13/library/importlib.html#importing-a-source-file-directly
        script = Path(__file__).resolve().parents[1] / "scripts/validate.py"
        code = """import importlib.util, sys
spec = importlib.util.spec_from_file_location('standalone_publication', sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
assert module.PRIVATE_CONTENT
assert not any(name == 'validate_foundation' or name.endswith('.validate_foundation') for name in sys.modules)
print('private-patterns:', len(module.PRIVATE_CONTENT))
"""
        result = subprocess.run(
            [sys.executable, "-B", "-I", "-c", code, str(script)], cwd=self.root,
            env={"PYTHONDONTWRITEBYTECODE": "1"}, capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("private-patterns:", result.stdout)

    def test_publication_validator_reaches_guard_and_retains_legacy_counts(self):
        fixture = publication_fixtures.PublicationValidationTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.write_json(MANIFEST, self.manifest)
        fixture.write_json(REPOSITORY_COVERAGE, self.coverage)
        fixture.write(DECISION, "# Synthetic decision\n")
        fixture.write_json(FINALIZED_SELECTION, self.document)
        self.assertEqual(validate_publication(fixture.root),
                         {"components": 1, "profiles": 1, "receipts": 1, "hashed_files": 2})
        self.document["slots"][0]["repositories"] = []
        fixture.write_json(FINALIZED_SELECTION, self.document)
        with self.assertRaisesRegex(InvalidPublication, "exactly one default"):
            validate_publication(fixture.root)


if __name__ == "__main__":
    unittest.main()
