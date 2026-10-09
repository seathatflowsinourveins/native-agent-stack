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
        self.timer = patch.object(inventory, "_timers", return_value=([], "UNREPORTED: fixture query unavailable")).start()

    def write(self, path, text):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def manifest(self, records, excluded=None):
        self.write(self.root / "adoption/skills/manifest.json", json.dumps({"skills": records, "excluded": excluded or []}))

    def build(self):
        return inventory.build(self.root, self.base / "state", [self.skills])

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

    def test_large_read_stops_before_hashing(self):
        self.write(self.skills / "large/SKILL.md", "over limit")
        with patch.object(inventory, "MAX_HASH_BYTES", 1), patch.object(inventory, "_hash") as hash_file:
            with self.assertRaisesRegex(ValueError, "LARGE-READ"):
                self.build()
            hash_file.assert_not_called()


if __name__ == "__main__":
    unittest.main()
