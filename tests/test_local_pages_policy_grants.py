"""Permission derivation excludes frozen inputs and never follows registries."""

import importlib.util
from contextlib import ExitStack
import copy
import json
from pathlib import Path
import subprocess
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("local_policy_grant_tests", ROOT / "scripts/local_pages_policy_grants.py")
grants = importlib.util.module_from_spec(spec)
spec.loader.exec_module(grants)


def reviewed_snapshot():
    return {
        "schema": "architecture-user-bindings/1",
        "reviewed_bindings": [
            {"role": "architecture_inventory", "source": ".agents/skills/reviewed/SKILL.md",
             "target": ".agents/skills/reviewed/SKILL.md"},
            {"role": "architecture_inventory", "source": ".agents/skills/plugin-link/SKILL.md",
             "target": ".codex/plugins/cache/reviewed/plugin/1.0/skills/reviewed/SKILL.md"},
            {"role": "architecture_inventory_metadata", "source": ".config/systemd/user/reviewed.service",
             "target": ".config/systemd/user/reviewed.service"},
            {"role": "architecture_design", "source": ".agents/skills/design/SKILL.md",
             "target": ".agents/skills/design/SKILL.md"},
        ],
    }


REVIEWED_GRANTS = {
    "architecture_inventory": [
        {"root": "user", "path": ".agents/skills/reviewed/SKILL.md"},
        {"root": "user", "path": ".codex/plugins/cache/reviewed/plugin/1.0/skills/reviewed/SKILL.md"},
    ],
    "architecture_inventory_metadata": [
        {"root": "user", "path": ".config/systemd/user/reviewed.service"},
    ],
    "architecture_design": [
        {"root": "user", "path": ".agents/skills/design/SKILL.md"},
    ],
    "architecture_inventory_aliases": [
        {"root": "user", "path": ".agents/skills/plugin-link/SKILL.md", "target_root": "user",
         "target_path": ".codex/plugins/cache/reviewed/plugin/1.0/skills/reviewed/SKILL.md"},
    ],
}


class PolicyGrantDerivation(unittest.TestCase):
    def test_registered_metadata_excludes_frozen_subtrees_without_opening(self):
        metadata = {"files": [{"path": "evidence/artifacts/frozen-fixture/report.json"},
                              {"path": "evidence/artifacts/frozen-fixture/variant/package.json"},
                              {"path": "evidence/receipts/allowed.json"},
                              {"path": "evidence/receipts/credentials.json"}],
                    "receipts": [{"path": "evidence/receipts/allowed.json"}]}
        self.assertEqual(grants.receipt_paths(metadata, ("evidence/artifacts/frozen-fixture",), lambda p: p.endswith("credentials.json")), ["evidence/receipts/allowed.json"])

    def test_only_tracked_selector_paths_enter_the_review_proposal(self):
        paths = ["scripts/reviewed.py", "scripts/nested/foreign.py", ".github/workflows/reviewed.yml",
                 "adoption/agents/exact/role.md", "adoption/agents/exact/manifest.json", "adoption/agents/exact/SHA256SUMS"]
        result = grants.inventory_paths(paths, {"foundation": "catalogs/landscape/foundation.json"})
        self.assertIn("scripts/reviewed.py", result)
        self.assertIn("adoption/agents/exact/manifest.json", result)
        self.assertNotIn("scripts/nested/foreign.py", result)
        self.assertIn("catalogs/landscape/foundation.json", result)

    def test_committed_repository_grants_match_current_git_inventory_paths(self):
        tracked = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, check=True, capture_output=True).stdout.decode().split("\0")
        manifest = json.loads((ROOT / "catalogs/landscape/manifest.json").read_text())
        expected = set(grants.inventory_paths([path for path in tracked if path], manifest["catalogs"]))
        policy = json.loads((ROOT / "tools/local-pages/source_policy.json").read_text())
        actual = {row["path"] for row in policy["architecture"]["architecture_inventory"] if row["root"] == "repo"}
        self.assertEqual(len(actual), 89)
        self.assertEqual(actual, expected, "Regenerate reviewed repository grants at the landing head; runtime discovery remains names-only.")

    def test_reviewed_user_snapshot_reproduces_grants_and_aliases(self):
        snapshot = json.loads((ROOT / "tools/local-pages/inventory_user_names.json").read_text())
        derived = grants.user_inventory_grants(snapshot)
        policy = json.loads((ROOT / "tools/local-pages/source_policy.json").read_text())
        for role in ("architecture_inventory", "architecture_inventory_metadata", "architecture_design"):
            actual = sorted([row for row in policy["architecture"][role] if row["root"] == "user"], key=lambda row: row["path"])
            self.assertTrue(actual == derived[role], f"Reviewed {role} grants differ; paths omitted.")
        self.assertTrue(policy["architecture_inventory_aliases"] == derived["architecture_inventory_aliases"],
                        "Reviewed aliases differ; paths omitted.")
        self.assertEqual({role: len(rows) for role, rows in derived.items()}, {
            "architecture_inventory": 41, "architecture_inventory_metadata": 94,
            "architecture_design": 1, "architecture_inventory_aliases": 33,
        })

    def test_public_user_snapshot_retains_only_reviewed_bindings_and_provenance(self):
        snapshot = json.loads((ROOT / "tools/local-pages/inventory_user_names.json").read_text())
        self.assertEqual(snapshot.get("schema"), "architecture-user-bindings/1")
        self.assertFalse({"directories", "unapproved_names", "names"}.intersection(snapshot))
        self.assertTrue(set(snapshot).issubset({
            "schema", "captured_utc", "source_pin", "policy_sha256", "limits",
            "reviewed_bindings", "counts",
        }))
        self.assertEqual(len(snapshot["reviewed_bindings"]), 165)
        self.assertTrue(all(set(row) == {"role", "source", "target"}
                            for row in snapshot["reviewed_bindings"]))

    def test_reviewed_bindings_derive_all_roles_without_directory_observations_or_io(self):
        snapshot = reviewed_snapshot()
        original = copy.deepcopy(snapshot)
        with ExitStack() as stack:
            for boundary in ("builtins.open", "io.open", "os.open", "os.stat", "os.lstat",
                             "pathlib.Path.resolve"):
                stack.enter_context(mock.patch(boundary, side_effect=AssertionError("Derivation attempted filesystem I/O")))
            result = grants.user_inventory_grants(snapshot)
        self.assertEqual(result, REVIEWED_GRANTS)
        self.assertEqual(snapshot, original)

    def test_legacy_names_snapshot_is_refused_even_with_reviewed_bindings(self):
        snapshot = reviewed_snapshot()
        snapshot["schema"] = "architecture-user-names/1"
        snapshot["directories"] = [
            {"path": ".agents/skills", "names": ["reviewed", "plugin-link", "design", "unreviewed"]},
            {"path": ".config/systemd/user", "names": ["reviewed.service", "unreviewed.service"]},
        ]
        with self.assertRaises(ValueError):
            grants.user_inventory_grants(snapshot)

    def test_stale_name_observations_are_refused_with_valid_bindings_intact(self):
        for key, value in (
            ("directories", [{"path": ".agents/skills", "names": ["unreviewed"]}]),
            ("unapproved_names", [{"path": ".agents/skills", "names": ["unreviewed"]}]),
        ):
            with self.subTest(field=key):
                snapshot = reviewed_snapshot()
                snapshot[key] = value
                with self.assertRaises(ValueError):
                    grants.user_inventory_grants(snapshot)

    def test_descriptive_counts_cannot_create_permissions(self):
        snapshot = reviewed_snapshot()
        snapshot["counts"] = {"architecture_inventory": 9999,
                              "architecture_inventory_metadata": 9999,
                              "architecture_design": 9999,
                              "architecture_inventory_aliases": 9999}
        self.assertEqual(grants.user_inventory_grants(snapshot), REVIEWED_GRANTS)

    def test_binding_source_and_target_require_exact_normalized_relative_paths(self):
        bad_paths = ("", "/outside/SKILL.md", "../outside/SKILL.md",
                     ".agents/skills/../../outside/SKILL.md", ".agents\\skills\\reviewed\\SKILL.md",
                     "./.agents/skills/reviewed/SKILL.md", ".agents/skills/reviewed/./SKILL.md",
                     ".agents//skills/reviewed/SKILL.md", ".agents/skills/reviewed/SKILL.md/",
                     None, 7, True)
        for role in ("architecture_inventory", "architecture_inventory_metadata", "architecture_design"):
            for field in ("source", "target"):
                for value in bad_paths:
                    with self.subTest(role=role, field=field, path=value):
                        row = {"role": role, "source": ".agents/skills/reviewed/SKILL.md",
                               "target": ".agents/skills/reviewed/SKILL.md"}
                        row[field] = value
                        with self.assertRaises(ValueError):
                            grants.user_inventory_grants({"schema": "architecture-user-bindings/1",
                                                          "reviewed_bindings": [row]})

    def test_protected_components_never_create_content_metadata_or_alias_grants(self):
        protected = ("credentials.json", ".env.local", "fixture.env", "environment.json",
                     "client_secret.json", "e2e-truth-fixture")
        for role in ("architecture_inventory", "architecture_inventory_metadata", "architecture_design"):
            for field in ("source", "target"):
                for component in protected:
                    with self.subTest(role=role, field=field, component=component):
                        row = {"role": role, "source": ".agents/skills/reviewed/SKILL.md",
                               "target": ".agents/skills/reviewed/SKILL.md"}
                        row[field] = f".agents/skills/{component}/SKILL.md"
                        snapshot = {"schema": "architecture-user-bindings/1", "reviewed_bindings": [row]}
                        with self.assertRaises(ValueError):
                            grants.user_inventory_grants(snapshot)

    def test_both_content_roles_require_skill_assets_for_source_and_target(self):
        for role in ("architecture_inventory", "architecture_design"):
            for field in ("source", "target"):
                with self.subTest(role=role, field=field):
                    row = {"role": role, "source": ".agents/skills/reviewed/SKILL.md",
                           "target": ".agents/skills/reviewed/SKILL.md"}
                    row[field] = ".agents/skills/reviewed/foreign.json"
                    with self.assertRaises(ValueError):
                        grants.user_inventory_grants({"schema": "architecture-user-bindings/1",
                                                      "reviewed_bindings": [row]})

    def test_duplicate_source_alias_to_distinct_target_is_refused_across_roles(self):
        snapshot = reviewed_snapshot()
        snapshot["reviewed_bindings"].append({
            "role": "architecture_design", "source": ".agents/skills/plugin-link/SKILL.md",
            "target": ".agents/skills/conflicting/SKILL.md",
        })
        with self.assertRaises(ValueError):
            grants.user_inventory_grants(snapshot)

    def test_same_source_and_target_can_be_reviewed_independently_for_both_content_roles(self):
        row = {"source": ".agents/skills/reviewed/SKILL.md", "target": ".agents/skills/reviewed/SKILL.md"}
        snapshot = {"schema": "architecture-user-bindings/1", "reviewed_bindings": [
            {"role": "architecture_inventory", **row}, {"role": "architecture_design", **row},
        ]}
        result = grants.user_inventory_grants(snapshot)
        for role in ("architecture_inventory", "architecture_design"):
            self.assertEqual(result[role], [{"root": "user", "path": ".agents/skills/reviewed/SKILL.md"}])
        self.assertEqual(result["architecture_inventory_metadata"], [])
        self.assertEqual(result["architecture_inventory_aliases"], [])

    def test_exact_duplicate_binding_is_refused(self):
        snapshot = reviewed_snapshot()
        snapshot["reviewed_bindings"].append(dict(snapshot["reviewed_bindings"][1]))
        with self.assertRaises(ValueError):
            grants.user_inventory_grants(snapshot)

    def test_identical_alias_mapping_reviewed_for_both_content_roles_is_recorded_once(self):
        snapshot = reviewed_snapshot()
        snapshot["reviewed_bindings"].append({
            "role": "architecture_design", "source": ".agents/skills/plugin-link/SKILL.md",
            "target": ".codex/plugins/cache/reviewed/plugin/1.0/skills/reviewed/SKILL.md",
        })
        result = grants.user_inventory_grants(snapshot)
        self.assertEqual(result["architecture_inventory_aliases"], REVIEWED_GRANTS["architecture_inventory_aliases"])
        self.assertEqual(result["architecture_design"], [
            {"root": "user", "path": ".agents/skills/design/SKILL.md"},
            {"root": "user", "path": ".codex/plugins/cache/reviewed/plugin/1.0/skills/reviewed/SKILL.md"},
        ])

    def test_escaping_catalog_metadata_is_refused_before_any_file_read(self):
        with self.assertRaises(ValueError):
            grants.inventory_paths([], {"bad": "catalogs/landscape/../../private.json"})


if __name__ == "__main__":
    unittest.main()
