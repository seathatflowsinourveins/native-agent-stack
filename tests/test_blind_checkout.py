"""Local integration tests for tools/sota-convergence/blind_checkout.py.

These are local integration tests, not upstream E2E: each test builds a
tiny fixture git repository in a temp dir (``git init`` + a real commit) and
runs the real ``git worktree add``/``git worktree remove`` commands against
it, but the fixture content, taxonomy and every catalog/blueprint shape are
synthetic, not a real repository checkout.
"""
import importlib.util
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL_DIR = ROOT / "tools" / "sota-convergence"


def load_module(name, filename):
    path = TOOL_DIR / filename
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


blind_checkout = load_module("blind_checkout", "blind_checkout.py")


def git(args, cwd):
    subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True)


def ledger_row(**overrides):
    row = {
        "catalog": "foundation", "layer_id": "native-clients", "title": "Native clients",
        "requirement": "Run coding tasks.", "current_choice": "Codex", "decision": "retain",
        "rationale": "Native evidence supports it.",
        "evidence_refs": ["docs/x.md"], "limitations": [], "overturn_when": "fixtures/x.json changes",
        "candidates": [
            {"name": "Codex", "repository": "https://github.com/openai/codex", "disposition": "selected",
             "rationale": "Chosen for native execution.", "evidence_kind": "native_execution",
             "evidence_refs": [], "review_status": "confirmed_default"},
            {"name": "Other", "repository": "https://github.com/example/other", "disposition": "conditional",
             "rationale": "Not chosen.", "evidence_kind": "source_review", "evidence_refs": []},
        ],
        "verdict_status": "recorded",
        "winners": [{"component_id": "codex", "repository": "https://github.com/openai/codex", "pin": "1.0",
                    "evidence_class": "native_proven", "why_selected": "Native execution evidence.",
                    "evidence_refs": [], "recipe_ref": "catalogs/landscape/foundation.json",
                    "platform_status": {"linux-wsl2-x86_64": "accepted", "macos-arm64": "untested"}}],
        "alternatives": [{"name": "Other", "repository": "https://github.com/example/other",
                          "disposition": "conditional", "why_not_default": "Not the default.",
                          "evidence_class": "source_review", "source": "lane:claude"}],
        "verdict_overturn_when": "fixtures/x.json changes and the new candidate passes.",
        "overturn_protocol": {"fixture_paths": [], "metric": "", "arms": []},
        "lanes": {"claude": {"run_id": "foundation-native-clients-20260922", "sealed_sha256": "a" * 64},
                  "codex": {"run_id": "foundation-native-clients-20260922", "sealed_sha256": "b" * 64},
                  "agreement": "same_winner"},
        "checked_at": "2026-09-22",
    }
    row.update(overrides)
    return row


class BlindCheckoutFixture(unittest.TestCase):
    def setUp(self):
        source_temp = tempfile.TemporaryDirectory()
        self.addCleanup(source_temp.cleanup)
        self.source = Path(source_temp.name).resolve()

        dest_parent = tempfile.TemporaryDirectory()
        self.addCleanup(dest_parent.cleanup)
        self.dest = Path(dest_parent.name).resolve() / "dest"

        git(["init", "-q"], self.source)
        git(["config", "user.email", "test@example.com"], self.source)
        git(["config", "user.name", "Test"], self.source)

        self.write("catalogs/landscape/foundation.json", {
            "schema_version": 2, "checked_at": "2026-09-22", "scope": "Fixture",
            "layers": [ledger_row()],
        })
        self.write("catalogs/landscape/us-equities.json", {
            "schema_version": 2, "checked_at": "2026-09-22", "scope": "Fixture", "layers": [], "domain_rows": [],
        })
        self.write("catalogs/other/decisions.json", {
            "decisions": [{"id": "d1", "review_status": "accepted_within_scope", "selection": "top_20",
                          "nested": {"decision": "retain"}}],
        })
        self.write("blueprints/example/manifest.json", {
            "disposition": "selected_destination",  # a label -> stripped
            "top": "top_20",  # a data value under an unrelated key -> kept
            "selection": "top_20",  # a data value under a stripped-elsewhere key -> kept (not a label)
            "current_choice": "keep NautilusTrader selected for now",  # states a selection -> stripped
            "mapping_rule": {"decision": {"if": "condition", "then": "branch"}},  # a rule structure -> kept
            "nested": {"disposition": "conditional"},  # a label, nested -> stripped
        })
        self.write("evidence/artifacts/layer-verdicts-20260922/claude/foundation-native-clients-20260922.json",
                    {"lane": "claude"})
        self.write("catalogs/sota-convergence/layer-verdicts-20260922.json", {"id": "layer-verdicts-20260922"})
        self.write("docs/grand-catalog-handbook.md", "# Handbook\n")
        self.write("docs/ecosystem/index.html", "<html></html>")
        self.write("docs/ecosystem/manifest.json", {"files": []})
        self.write("docs/keep-me.md", "# Keep this one\n")

        git(["add", "-A"], self.source)
        git(["commit", "-q", "-m", "fixture"], self.source)

    def write(self, relative, value):
        path = self.source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(value, str):
            path.write_text(value, encoding="utf-8")
        else:
            path.write_text(json.dumps(value), encoding="utf-8")

    def run_checkout(self, dest=None):
        return blind_checkout.run_blind_checkout(self.source, "HEAD", dest or self.dest)

    def remove_worktree(self, dest=None):
        git(["worktree", "remove", "--force", str(dest or self.dest)], self.source)


class RemovedFilesTests(BlindCheckoutFixture):
    def test_dated_evidence_and_generated_indexes_are_removed(self):
        manifest = self.run_checkout()
        self.addCleanup(self.remove_worktree)
        self.assertIn("evidence/artifacts/layer-verdicts-20260922/claude/foundation-native-clients-20260922.json",
                      manifest["removed_files"])
        self.assertIn("catalogs/sota-convergence/layer-verdicts-20260922.json", manifest["removed_files"])
        self.assertIn("docs/grand-catalog-handbook.md", manifest["removed_files"])
        self.assertIn("docs/ecosystem/index.html", manifest["removed_files"])
        self.assertIn("docs/ecosystem/manifest.json", manifest["removed_files"])
        self.assertFalse((self.dest / "evidence/artifacts/layer-verdicts-20260922").exists())
        self.assertFalse((self.dest / "catalogs/sota-convergence/layer-verdicts-20260922.json").exists())
        self.assertFalse((self.dest / "docs/grand-catalog-handbook.md").exists())
        self.assertFalse((self.dest / "docs/ecosystem/index.html").exists())
        self.assertFalse((self.dest / "docs/ecosystem/manifest.json").exists())
        # An unrelated docs file is untouched.
        self.assertTrue((self.dest / "docs/keep-me.md").is_file())


class LedgerV2ResetTests(BlindCheckoutFixture):
    def test_v2_verdict_fields_reset_to_pending_and_requirement_kept(self):
        self.run_checkout()
        self.addCleanup(self.remove_worktree)
        document = json.loads((self.dest / "catalogs/landscape/foundation.json").read_text(encoding="utf-8"))
        row = document["layers"][0]
        self.assertEqual(row["verdict_status"], "pending_lanes")
        self.assertEqual(row["winners"], [])
        self.assertEqual(row["alternatives"], [])
        self.assertEqual(row["verdict_overturn_when"], "")
        self.assertEqual(row["lanes"], {"claude": {"run_id": "", "sealed_sha256": ""},
                                        "codex": {"run_id": "", "sealed_sha256": ""}, "agreement": "pending"})
        # Requirement and evidence are not v2 fields and stay.
        self.assertEqual(row["requirement"], "Run coding tasks.")
        self.assertEqual(row["evidence_refs"], ["docs/x.md"])
        self.assertEqual(row["overturn_when"], "fixtures/x.json changes")
        # The ledger's own schema (a JSON object with a layers list) still loads.
        self.assertEqual(document["schema_version"], 2)
        self.assertIsInstance(document["layers"], list)


class LedgerV1LabelTests(BlindCheckoutFixture):
    def test_v1_label_fields_removed_from_row_and_candidates(self):
        self.run_checkout()
        self.addCleanup(self.remove_worktree)
        document = json.loads((self.dest / "catalogs/landscape/foundation.json").read_text(encoding="utf-8"))
        row = document["layers"][0]
        for key in ("current_choice", "decision", "rationale"):
            self.assertNotIn(key, row)
        for candidate in row["candidates"]:
            for key in ("disposition", "rationale", "review_status"):
                self.assertNotIn(key, candidate)
        # The candidate's name/repository/evidence fields are kept.
        self.assertEqual(row["candidates"][0]["name"], "Codex")
        self.assertEqual(row["candidates"][0]["repository"], "https://github.com/openai/codex")


class CatalogsUnconditionalTests(BlindCheckoutFixture):
    def test_selection_keys_stripped_anywhere_under_catalogs_regardless_of_value(self):
        self.run_checkout()
        self.addCleanup(self.remove_worktree)
        document = json.loads((self.dest / "catalogs/other/decisions.json").read_text(encoding="utf-8"))
        decision = document["decisions"][0]
        self.assertNotIn("review_status", decision)
        self.assertNotIn("selection", decision)  # even though its value ("top_20") is a data value, not a label
        self.assertNotIn("decision", decision["nested"])
        self.assertEqual(decision["id"], "d1")


class BlueprintLabelExceptionTests(BlindCheckoutFixture):
    def test_label_values_stripped_but_data_values_and_rules_kept(self):
        self.run_checkout()
        self.addCleanup(self.remove_worktree)
        document = json.loads((self.dest / "blueprints/example/manifest.json").read_text(encoding="utf-8"))
        self.assertNotIn("disposition", document)
        self.assertNotIn("current_choice", document)
        self.assertNotIn("disposition", document["nested"])
        # Data values under the same key names are left alone under blueprints/.
        self.assertEqual(document["top"], "top_20")
        self.assertEqual(document["selection"], "top_20")
        # A mapping/rule structure under a stripped-elsewhere key name is left alone.
        self.assertEqual(document["mapping_rule"], {"decision": {"if": "condition", "then": "branch"}})


class ManifestTests(BlindCheckoutFixture):
    def test_manifest_lists_every_removal_and_strip_with_old_value_hashes_only(self):
        manifest = self.run_checkout()
        self.addCleanup(self.remove_worktree)
        on_disk = json.loads((self.dest / "BLIND-MANIFEST.json").read_text(encoding="utf-8"))
        self.assertEqual(on_disk["removed_files"], manifest["removed_files"])
        self.assertEqual(on_disk["stripped_fields"], manifest["stripped_fields"])
        # Every stripped entry names a path and an old-value hash, never the value itself.
        serialized = json.dumps(on_disk)
        self.assertNotIn("Codex", serialized)  # a stripped rationale/current_choice value
        self.assertNotIn("selected_destination", serialized)
        for entry in on_disk["stripped_fields"]:
            self.assertIn("path", entry)
            self.assertRegex(entry["old_sha256"], r"^[a-f0-9]{64}$")
        # At least one entry per strip rule is present.
        paths = {entry["path"] for entry in on_disk["stripped_fields"]}
        self.assertTrue(any(path.endswith("/verdict_status") for path in paths))
        self.assertTrue(any(path.endswith("/current_choice") for path in paths))
        self.assertTrue(any("/candidates/0/disposition" in path for path in paths))


class IdempotenceTests(BlindCheckoutFixture):
    def test_stripping_an_already_blind_worktree_finds_nothing_left_to_strip(self):
        self.run_checkout()
        self.addCleanup(self.remove_worktree)
        second_pass = blind_checkout.strip_worktree(self.dest)
        self.assertEqual(second_pass["removed_files"], [])
        self.assertEqual(second_pass["stripped_fields"], [])

    def test_running_blind_checkout_twice_from_the_same_source_rev_is_stable(self):
        first = self.run_checkout()
        self.addCleanup(self.remove_worktree)
        second_dest = self.dest.parent / "dest2"
        second = self.run_checkout(dest=second_dest)
        self.addCleanup(lambda: self.remove_worktree(second_dest))
        self.assertEqual(first["removed_files"], second["removed_files"])
        self.assertEqual(first["stripped_fields"], second["stripped_fields"])


if __name__ == "__main__":
    unittest.main()
