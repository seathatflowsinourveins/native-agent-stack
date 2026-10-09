"""Inventory boundary, provenance and explicit-mapping behavior."""

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "architecture_inventory", Path(__file__).resolve().parents[1] / "tools/local-pages/architecture_inventory.py"
)
inventory = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(inventory)


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "repo"
        self.user = self.base / "user"
        self.skills = self.user / ".agents/skills"
        self.root.mkdir()
        self.user.mkdir()
        self.addCleanup(patch.stopall)
        patch.object(inventory, "USER_ROOT", self.user).start()
        patch.object(inventory, "MAPPING_PATH", self.root / "tools/local-pages/architecture_mapping.json", create=True).start()
        self.timer = patch.object(inventory, "_timers", return_value=([], "UNREPORTED: fixture query unavailable")).start()

    def write(self, path, text):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def manifest(self, records, excluded=None):
        self.write(self.root / "adoption/skills/manifest.json", json.dumps({"skills": records, "excluded": excluded or []}))

    def build(self):
        return inventory.build(self.root, self.base / "state", [self.skills])

    def catalog(self, catalog, layers):
        self.write(self.root / "catalogs/landscape/manifest.json", json.dumps({
            "catalogs": {catalog: "catalogs/landscape/" + catalog + ".json"}
        }))
        self.write(self.root / ("catalogs/landscape/" + catalog + ".json"), json.dumps({"layers": layers}))

    def record(self, name, digest, **extra):
        return dict(name=name, source="upstream/skills", ref="a" * 40, tree_sha="b" * 40, skill_md_sha256=digest, status="trial", **extra)

    def test_exact_skill_hash_and_recorded_pin_without_guessed_layer(self):
        path = self.write(self.skills / "known/SKILL.md", "fixture skill\n")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        self.manifest([self.record("known", digest)], [{"skills": ["excluded"], "source": "upstream/skills"}])
        result = self.build()
        item = result["items"][0]
        self.assertEqual(item["status"], "SOURCE_MATCHED")
        self.assertEqual(item["repository"], "https://github.com/upstream/skills")
        self.assertEqual(item["pin"], "a" * 40)
        self.assertNotIn("layer_id", item)
        self.assertEqual(result["coverage"]["unmapped"][0]["path"], str(path))
        self.assertEqual(result["coverage"]["excluded_skills"][0]["skills"], ["excluded"])

    def test_mismatch_and_unrecorded_skill_remain_unreported(self):
        self.write(self.skills / "changed/SKILL.md", "changed")
        self.write(self.skills / "unknown/SKILL.md", "unrecorded")
        self.manifest([self.record("changed", "0" * 64)])
        result = self.build()
        items = {item["name"]: item for item in result["items"]}
        self.assertFalse(items["changed"]["hash_match"])
        self.assertEqual(items["changed"]["status"], "UNREPORTED")
        self.assertIsNone(items["unknown"]["repository"])
        self.assertEqual(items["unknown"]["source_refs"], [])

    def test_only_explicit_manifest_ids_bind_layers(self):
        path = self.write(self.skills / "known/SKILL.md", "fixture")
        self.manifest([self.record("known", hashlib.sha256(path.read_bytes()).hexdigest(), layer_id="recorded-layer", component_id="recorded-component")])
        result = self.build()
        self.assertEqual(result["items"][0]["layer_id"], "recorded-layer")
        self.assertEqual(result["coverage"]["unmapped"], [])

    def test_canonical_winner_ids_and_candidate_repositories_join_stack_components(self):
        self.catalog("foundation", [
            {"catalog": "foundation", "layer_id": "native-clients", "winners": [{"component_id": "native-cli"}]},
            {"catalog": "foundation", "layer_id": "agent-sdks", "candidates": [{"repository": "https://github.com/upstream/sdk"}]},
        ])
        self.write(self.root / "manifests/stack.json", json.dumps({"components": [
            {"id": "native-cli", "repository": "https://github.com/upstream/cli"},
            {"id": "sdk-native", "repository": "https://github.com/upstream/sdk/releases/tag/v1.0"},
        ]}))
        result = self.build()
        items = {item["name"]: item for item in result["items"]}
        self.assertEqual(items["native-cli"]["layer_keys"], ["foundation/native-clients"])
        self.assertEqual(items["sdk-native"]["layer_keys"], ["foundation/agent-sdks"])
        self.assertIn("winners/0", items["native-cli"]["mapping_source"])
        self.assertIn("candidates/0", items["sdk-native"]["mapping_source"])
        self.assertEqual(result["coverage"]["unmapped"], [])
        self.assertTrue(all(item["status"] == "UNREPORTED" for item in result["items"]))

    def test_explicit_mapping_supports_multiple_layers_and_explains_unmapped_items(self):
        self.catalog("foundation", [
            {"catalog": "foundation", "layer_id": "workers", "winners": []},
            {"catalog": "foundation", "layer_id": "quality-evaluation", "winners": []},
        ])
        self.write(self.user / ".codex/agents/reviewer.toml", "fixture reviewer")
        self.write(self.skills / "unknown/SKILL.md", "fixture skill")
        mapping = self.write(inventory.MAPPING_PATH, json.dumps({
            "schema": "local-architecture-mapping/1", "mappings": [
                {"kinds": ["role"], "names": ["reviewer"], "layer_keys": ["foundation/workers", "foundation/quality-evaluation"],
                 "reason": "reviewer owns independent quality checks", "source_refs": ["catalogs/landscape/foundation.json#/layers/1"]},
                {"kinds": ["skill"], "names": ["unknown"], "unmapped_reason": "no recorded architecture responsibility for this fixture"},
            ],
        }))
        result = self.build()
        reviewer = next(item for item in result["items"] if item["name"] == "reviewer")
        self.assertEqual(reviewer["layer_keys"], ["foundation/quality-evaluation", "foundation/workers"])
        self.assertEqual(reviewer["mapping_reason"], "reviewer owns independent quality checks")
        self.assertIn(str(mapping), reviewer["mapping_source"])
        self.assertEqual(reviewer["status"], "UNREPORTED")
        self.assertEqual(result["coverage"]["unmapped"][0]["reason"], "no recorded architecture responsibility for this fixture")
        self.assertEqual(next(source for source in result["sources"] if source["path"] == str(mapping))["sha256"], hashlib.sha256(mapping.read_bytes()).hexdigest())

    def test_mapping_rejects_a_layer_absent_from_registered_catalog(self):
        self.catalog("foundation", [{"catalog": "foundation", "layer_id": "workers", "winners": []}])
        self.write(self.skills / "unknown/SKILL.md", "fixture")
        self.write(inventory.MAPPING_PATH, json.dumps({"schema": "local-architecture-mapping/1", "mappings": [
            {"kinds": ["skill"], "names": ["unknown"], "layer_keys": ["foundation/invented"], "reason": "invalid fixture target"}
        ]}))
        result = self.build()
        self.assertNotIn("layer_keys", result["items"][0])
        self.assertIn("unknown canonical layer", result["coverage"]["unmapped"][0]["reason"])

    def test_catalog_registration_cannot_follow_external_metadata(self):
        self.catalog("foundation", [{"catalog": "foundation", "layer_id": "workers", "winners": [{"component_id": "native-cli"}]}])
        outside = self.write(self.base / "outside/registry.json", json.dumps({"catalogs": {"foundation": "catalogs/landscape/foundation.json"}}))
        registry = self.root / "catalogs/landscape/manifest.json"
        registry.unlink()
        registry.symlink_to(outside)
        self.write(self.root / "manifests/stack.json", json.dumps({"components": [{"id": "native-cli"}]}))
        result = self.build()
        self.assertNotIn("layer_keys", result["items"][0])
        self.assertFalse(any(source["path"] == str(registry) for source in result["sources"]))

    def test_boundary_excludes_credentials_trash_deep_paths_and_external_targets(self):
        external = self.write(self.base / "outside/SKILL.md", "external")
        target = self.skills / "escape"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.symlink_to(external.parent, target_is_directory=True)
        self.write(self.skills / ".trash/retired/SKILL.md", "retired")
        self.write(self.skills / "deep/one/two/SKILL.md", "too deep")
        self.write(self.user / ".codex/agents/auth.json", "unread")
        self.write(self.user / ".codex/agents/config.toml", "unread")
        self.write(self.root / "scripts/.env", "unread")
        auth = self.write(self.skills / "alias/auth.json", "unread")
        (auth.parent / "SKILL.md").symlink_to(auth)
        visited = []
        original = inventory._hash
        with patch.object(inventory, "_hash", side_effect=lambda path: (visited.append(path), original(path))[1]):
            result = self.build()
        self.assertEqual(visited, [])
        self.assertTrue(all(item["sha256"] is None for item in result["items"]))
        self.assertEqual({item["name"] for item in result["items"]}, {"escape", "alias"})

    def test_system_skills_and_approved_symlink_are_bounded(self):
        real = self.write(self.skills / ".system/native/SKILL.md", "native")
        alias = self.skills / "alias"
        alias.symlink_to(real.parent, target_is_directory=True)
        result = self.build()
        self.assertEqual(len(result["items"]), 2)
        self.assertTrue(all(item["sha256"] == hashlib.sha256(real.read_bytes()).hexdigest() for item in result["items"]))
        self.assertEqual(result["coverage"]["hash_bytes"], real.stat().st_size)

    def test_roles_checksums_and_components_do_not_assert_wiring(self):
        role = self.write(self.root / "adoption/agents/codex/reviewer.toml", "fixture role")
        digest = hashlib.sha256(role.read_bytes()).hexdigest()
        self.write(role.parent / "SHA256SUMS", digest + "  reviewer.toml\n")
        self.write(self.root / "manifests/stack.json", json.dumps({"components": [{"id": "sdk-native", "repository": "https://github.com/upstream/sdk", "source_pin": "c" * 40, "version": "1.0"}]}))
        self.write(self.root / "adoption/manifest.json", json.dumps({"recipe_map": {"sdk-native": "recipes/sdk.md"}, "sources": {"runtime_receipt": "adoption/runtime.md"}, "toolchain": {"sdk_lock": "adoption/sdk/requirements.lock"}}))
        result = self.build()
        role_item = next(item for item in result["items"] if item["kind"] == "role")
        self.assertTrue(role_item["hash_match"])
        self.assertEqual(role_item["status"], "UNREPORTED")
        component = next(item for item in result["items"] if item["kind"] == "component")
        self.assertEqual(component["component_id"], "sdk-native")
        self.assertEqual(component["pin"], "c" * 40)
        self.assertIn(str(self.root / "recipes/sdk.md"), component["source_refs"])
        self.assertEqual(component["status"], "UNREPORTED")
        source = next(source for source in result["sources"] if source["path"].endswith("adoption/manifest.json"))
        self.assertEqual(source["reference_paths"], [{"key": "runtime_receipt", "path": "adoption/runtime.md"}])
        self.assertEqual(source["sdk_reference_paths"], [{"key": "sdk_lock", "path": "adoption/sdk/requirements.lock"}])

    def test_workflow_records_full_action_pins_only_and_units_never_parse_commands(self):
        sha = "d" * 40
        self.write(self.root / ".github/workflows/check.yml", "steps:\n - uses: upstream/action@" + sha + "\n - uses: upstream/action@main\nenv:\n IGNORED_VALUE: fixture\n")
        self.write(self.user / ".config/systemd/user/example.timer", "[Timer]\nOnCalendar=daily\n")
        self.write(self.user / ".config/systemd/user/example.service", "[Service]\nEnvironment=IGNORED_VALUE=fixture\nExecStart=/fixture\n")
        result = self.build()
        workflow = next(item for item in result["items"] if item["kind"] == "workflow")
        self.assertEqual(workflow["action_refs"], [{"repository": "https://github.com/upstream/action", "pin": sha}])
        self.assertNotIn("IGNORED_VALUE", json.dumps(result))
        self.assertNotIn("ExecStart", json.dumps(result))
        self.assertTrue(result["coverage"]["cron_status"].startswith("UNREPORTED"))

    def test_missing_sanitized_projection_never_reads_hook_sources(self):
        for root in (self.root / "hooks", self.root / "scripts/hooks", self.user / ".claude/hooks"):
            self.write(root / "registered.py", "hook source fixture")
        visited = []
        original = inventory._hash
        with patch.object(inventory, "_hash", side_effect=lambda path: (visited.append(path), original(path))[1]):
            result = self.build()
        self.assertEqual(visited, [])
        self.assertFalse(any(item["kind"] == "hook" for item in result["items"]))
        self.assertIn("sanitized projection absent", result["coverage"]["client_hook_wiring"])

    def test_sanitized_projection_preserves_each_registration_and_binds_digest(self):
        projection = self.write(self.base / "state/coordination/command-center/pages/automation-projection.json", json.dumps({
            "schema": "automation-projection/1", "generated_utc": "2026-10-09T03:01:39Z",
            "method": "program basename only", "limits": ["registration is not execution"],
            "hooks": [
                {"client": "codex", "scope": "user", "event": "PreToolUse", "matcher": "Bash", "program": "rtk", "timeout_s": 5, "command": "omitted-command"},
                {"client": "codex", "scope": "user", "event": "SessionStart", "matcher": "startup", "program": "rtk", "timeout_s": None},
            ],
            "cron": [{"schedule": "0 * * * *", "program": "refresh-pages"}],
        }))
        result = self.build()
        hooks = [item for item in result["items"] if item["kind"] == "hook"]
        self.assertEqual(len(hooks), 2)
        self.assertEqual({item["event"] for item in hooks}, {"PreToolUse", "SessionStart"})
        self.assertTrue(all(item["name"] == "rtk" for item in hooks))
        self.assertTrue(all(item["status"] == "UNREPORTED" for item in hooks))
        self.assertEqual(result["coverage"]["projection_limits"], ["registration is not execution"])
        source = next(source for source in result["sources"] if source["path"] == str(projection))
        self.assertEqual(source["sha256"], hashlib.sha256(projection.read_bytes()).hexdigest())
        self.assertEqual(result["coverage"]["projected_hook_registrations"], 2)
        self.assertEqual(result["coverage"]["projected_cron_registrations"], 1)
        self.assertNotIn("omitted-command", json.dumps(result))

    def test_large_read_stops_before_hashing(self):
        self.write(self.skills / "large/SKILL.md", "over limit")
        with patch.object(inventory, "MAX_HASH_BYTES", 1), patch.object(inventory, "_hash") as hash_file:
            with self.assertRaisesRegex(ValueError, "LARGE-READ"):
                self.build()
            hash_file.assert_not_called()


if __name__ == "__main__":
    unittest.main()
