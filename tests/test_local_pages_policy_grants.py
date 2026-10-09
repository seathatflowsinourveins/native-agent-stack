"""Permission derivation excludes frozen inputs and never follows registries."""

import importlib.util
import json
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("local_policy_grant_tests", ROOT / "scripts/local_pages_policy_grants.py")
grants = importlib.util.module_from_spec(spec)
spec.loader.exec_module(grants)


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
        self.assertEqual(actual, expected, "Regenerate reviewed repository grants at the landing head; runtime discovery remains names-only.")

    def test_reviewed_user_snapshot_reproduces_grants_and_aliases(self):
        snapshot = json.loads((ROOT / "tools/local-pages/inventory_user_names.json").read_text())
        derived = grants.user_inventory_grants(snapshot)
        policy = json.loads((ROOT / "tools/local-pages/source_policy.json").read_text())
        for role in ("architecture_inventory", "architecture_inventory_metadata", "architecture_design"):
            actual = sorted([row for row in policy["architecture"][role] if row["root"] == "user"], key=lambda row: row["path"])
            self.assertEqual(actual, derived[role])
        self.assertEqual(policy["architecture_inventory_aliases"], derived["architecture_inventory_aliases"])

    def test_unreviewed_user_names_never_create_content_or_metadata_grants(self):
        snapshot = {"schema": "architecture-user-names/1", "directories": [{"path": ".agents/skills", "names": ["known", "unreviewed"]}, {"path": ".config/systemd/user", "names": ["known.service", "unreviewed.service"]}], "reviewed_bindings": [{"role": "architecture_inventory", "source": ".agents/skills/known/SKILL.md", "target": ".agents/skills/known/SKILL.md"}, {"role": "architecture_inventory_metadata", "source": ".config/systemd/user/known.service", "target": ".config/systemd/user/known.service"}]}
        result = grants.user_inventory_grants(snapshot)
        self.assertEqual(result["architecture_inventory"], [{"root": "user", "path": ".agents/skills/known/SKILL.md"}])
        self.assertEqual(result["architecture_inventory_metadata"], [{"root": "user", "path": ".config/systemd/user/known.service"}])
        snapshot["directories"][0]["names"].remove("known")
        self.assertEqual(grants.user_inventory_grants(snapshot)["architecture_inventory"], [])

    def test_escaping_catalog_metadata_is_refused_before_any_file_read(self):
        with self.assertRaises(ValueError):
            grants.inventory_paths([], {"bad": "catalogs/landscape/../../private.json"})


if __name__ == "__main__":
    unittest.main()
