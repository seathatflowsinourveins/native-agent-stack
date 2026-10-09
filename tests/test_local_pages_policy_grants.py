"""Permission derivation excludes frozen inputs and never follows registries."""

import importlib.util
from pathlib import Path
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

    def test_runtime_like_untracked_files_do_not_gain_inventory_permission(self):
        paths = ["scripts/reviewed.py", "scripts/nested/foreign.py", ".github/workflows/reviewed.yml",
                 "adoption/agents/exact/role.md", "adoption/agents/exact/manifest.json", "adoption/agents/exact/SHA256SUMS"]
        result = grants.inventory_paths(paths, {"foundation": "catalogs/landscape/foundation.json"})
        self.assertIn("scripts/reviewed.py", result)
        self.assertIn("adoption/agents/exact/manifest.json", result)
        self.assertNotIn("scripts/unreviewed.py", result)
        self.assertNotIn("scripts/nested/foreign.py", result)
        self.assertIn("catalogs/landscape/foundation.json", result)

    def test_escaping_catalog_metadata_is_refused_before_any_file_read(self):
        with self.assertRaises(ValueError):
            grants.inventory_paths([], {"bad": "catalogs/landscape/../../private.json"})


if __name__ == "__main__":
    unittest.main()
