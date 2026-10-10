"""Permission derivation excludes frozen inputs and never follows registries."""

import importlib.util
from contextlib import ExitStack
import copy
import json
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
REVIEWED_RECEIPT_PIN = "c945ea1f011e4c7e69a0b5f19052717b2af9d46e"
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
        self.assertEqual(len(actual), 93)
        self.assertEqual(actual, expected, "Regenerate reviewed repository grants at the landing head; runtime discovery remains names-only.")

    def test_receipt_documentation_identifies_the_reviewed_union_and_ungranted_proposal(self):
        for relative in (
            "tools/local-pages/README.md",
            "docs/decisions/2026-10-09-architecture-inventory-boundary.md",
        ):
            with self.subTest(document=relative):
                document = (ROOT / relative).read_text()
                declaration = re.search(
                    r"receipt grant set\s+was(?: independently)? reviewed at\s+`([a-f0-9]{40})`",
                    document,
                )
                self.assertIsNotNone(declaration, "Receipt grants must name their independently reviewed full source SHA.")
                self.assertEqual(declaration.group(1), REVIEWED_RECEIPT_PIN)
                paragraph = next(block for block in document.split("\n\n")
                                 if declaration.group(0) in block)
                paragraph = " ".join(paragraph.split())
                self.assertRegex(paragraph, r"\b4648\b")
                self.assertRegex(paragraph, r"\b4725\b")
                self.assertRegex(
                    paragraph,
                    r"\b(?:do not add permissions without independent review|"
                    r"does not expand the independently reviewed pinned receipt grant set)\b",
                )

    def test_committed_receipt_grants_equal_the_native_reviewed_source_proposal(self):
        reviewed = grants.proposal(ROOT, REVIEWED_RECEIPT_PIN)
        self.assertEqual(reviewed["source_pin"], REVIEWED_RECEIPT_PIN)
        self.assertEqual(reviewed["receipt_count"], 4648)
        policy = json.loads((ROOT / "tools/local-pages/source_policy.json").read_text())
        actual = policy["architecture"]["architecture_receipt"]
        expected = reviewed["architecture_receipt"]
        self.assertEqual(len(actual), 4648)
        self.assertTrue(sorted(actual, key=lambda row: (row["root"], row["path"])) == expected,
                        "Receipt grants differ from the exact independently reviewed union; paths omitted.")

    def test_reviewed_user_source_pin_is_reachable_from_main_with_matching_snapshot(self):
        relative = "tools/local-pages/inventory_user_names.json"
        snapshot = json.loads((ROOT / relative).read_text())
        pin = snapshot["source_pin"]
        self.assertRegex(pin, r"\A[a-f0-9]{40}\Z")
        main = subprocess.run(["git", "rev-parse", "--verify", "refs/remotes/origin/main^{commit}"], cwd=ROOT, check=True,
                              capture_output=True, text=True).stdout.strip()
        ancestry = subprocess.run(["git", "merge-base", "--is-ancestor", pin, main],
                                  cwd=ROOT, capture_output=True)
        self.assertEqual(ancestry.returncode, 0,
                         "The user source pin must be reachable from origin/main; an existing object or PR-only ancestor is insufficient.")
        pinned = json.loads(subprocess.run(["git", "show", f"{pin}:{relative}"], cwd=ROOT,
                                           check=True, capture_output=True).stdout)
        self.assertTrue({key: value for key, value in snapshot.items() if key != "source_pin"}
                        == {key: value for key, value in pinned.items() if key != "source_pin"},
                        "Reviewed snapshot differs from its pinned source outside the self-referential source_pin; paths omitted.")

    def test_matching_user_snapshot_on_a_pr_only_ancestor_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def git(*arguments, input=None):
                return subprocess.run(
                    ["git", "-c", "user.name=Synthetic Fixture", "-c", "user.email=fixture@example.invalid",
                     "-C", str(root), *arguments], input=input, check=True,
                    capture_output=True, text=True,
                ).stdout.strip()

            git("init", "--quiet", "--initial-branch=main")
            snapshot = {**reviewed_snapshot(), "source_pin": "0" * 40}
            blob = git("hash-object", "-w", "--stdin", input=json.dumps(snapshot))
            local_pages = git("mktree", input=f"100644 blob {blob}\tinventory_user_names.json\n")
            tools = git("mktree", input=f"040000 tree {local_pages}\tlocal-pages\n")
            tree = git("mktree", input=f"040000 tree {tools}\ttools\n")
            main = git("commit-tree", tree, input="Synthetic main snapshot\n")
            branch = git("commit-tree", tree, "-p", main, input="Synthetic PR-only snapshot\n")
            git("update-ref", "refs/remotes/origin/main", main)
            git("update-ref", "refs/heads/review", branch)
            git("symbolic-ref", "HEAD", "refs/heads/review")
            git("merge-base", "--is-ancestor", branch, "HEAD")
            original_read_text = Path.read_text

            def read_text(path, *arguments, **keywords):
                if path == root / "tools/local-pages/inventory_user_names.json":
                    return json.dumps(snapshot)
                return original_read_text(path, *arguments, **keywords)

            with mock.patch(__name__ + ".ROOT", root), mock.patch.object(Path, "read_text", read_text):
                snapshot["source_pin"] = main
                self.test_reviewed_user_source_pin_is_reachable_from_main_with_matching_snapshot()
                snapshot["source_pin"] = branch
                with self.assertRaisesRegex(AssertionError, "reachable from origin/main"):
                    self.test_reviewed_user_source_pin_is_reachable_from_main_with_matching_snapshot()

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
