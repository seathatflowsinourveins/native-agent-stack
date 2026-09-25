"""Tests for adoption/pins-linux-x86_64.json's schema_version 2 shape
(adoption/pins-schema-v2.json) and scripts/validate.py's validate_pins_v2 parity
check against manifests/stack.json and catalogs/landscape/*.json winners.
"""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from scripts.validate import validate_pins_v2

ROOT = Path(__file__).resolve().parents[1]
PINS_PATH = ROOT / "adoption" / "pins-linux-x86_64.json"
SCHEMA_PATH = ROOT / "adoption" / "pins-schema-v2.json"

REQUIRED_TOOL_FIELDS = (
    "id", "version", "kind", "url", "install_note",
    "root_name", "current_link", "entrypoints", "surfaces", "state_dirs", "window", "rollback_class",
)
VALID_KINDS = {"tarball", "npm", "pip", "uv-tool", "native"}
VALID_ROLLBACK_CLASSES = {"safe", "restart_required", "manual_required", "not_applicable"}


def load_pins() -> dict:
    return json.loads(PINS_PATH.read_text())


class ShippedFileShapeTests(unittest.TestCase):
    """Structural checks of the actual committed adoption/pins-linux-x86_64.json, not a
    fixture: this is the deliverable, so it is checked directly (mirroring
    tests/test_adoption_bootstrap.py's PinsSchemaTests, extended for the new v2 fields)."""

    def setUp(self):
        self.pins = load_pins()

    def test_schema_version_is_2(self):
        self.assertEqual(self.pins["schema_version"], 2)
        self.assertEqual(self.pins["platform"], "linux-x86_64")

    def test_every_tool_has_every_v2_field(self):
        for tool in self.pins["tools"]:
            for field in REQUIRED_TOOL_FIELDS:
                self.assertIn(field, tool, f"{tool.get('id')} missing {field}")
            self.assertIn(tool["kind"], VALID_KINDS)
            self.assertIn(tool["rollback_class"], VALID_ROLLBACK_CLASSES)
            self.assertIsInstance(tool["entrypoints"], list)
            self.assertIsInstance(tool["surfaces"], list)
            self.assertIsInstance(tool["state_dirs"], list)

    def test_current_link_null_iff_root_name_null(self):
        for tool in self.pins["tools"]:
            self.assertEqual(tool["root_name"] is None, tool["current_link"] is None,
                              f"{tool['id']}: root_name and current_link must be null together")
            if tool["current_link"] is not None:
                self.assertTrue(tool["current_link"].startswith("current/"), tool["id"])

    def test_legacy_v1_fields_are_byte_identical_to_the_original_review(self):
        # Regression: migrating to v2 must never change an id/version/kind/url/sha256/
        # install_note value, only add new fields (switch.md: "Migrate the existing v1
        # entries faithfully"). This is the same set test_adoption_bootstrap.py's
        # test_every_tool_has_required_fields already checks presence of; here their
        # VALUES are pinned against the pre-migration 2026-09-22 review.
        expected = {
            "node": "24.21.0", "uv": "0.12.17", "gh": "2.101.0", "codex": "0.155.1",
            "claude-code": "2.1.280", "qmd": "2.8.3", "rtk": "0.49.0", "ai-memory": "2.3.2",
            "mcporter": "0.13.13", "context-mode": "1.0.169", "markitdown": "0.1.7",
            "tavily-cli": "0.1.8", "orx": "0.2.7", "agent-browser": "0.38.1",
        }
        by_id = {tool["id"]: tool for tool in self.pins["tools"]}
        self.assertEqual(set(by_id), set(expected))
        for tool_id, version in expected.items():
            self.assertEqual(by_id[tool_id]["version"], version)
            self.assertIsNotNone(by_id[tool_id]["sha256"])

    def test_candidates_are_all_pending(self):
        for candidate in self.pins.get("candidates", []):
            self.assertEqual(candidate["status"], "pending")
            self.assertTrue(candidate["note"])

    def test_supersedes_entries_carry_sha256_provenance_not_content(self):
        for entry in self.pins.get("supersedes", []):
            self.assertRegex(entry["sha256"], r"^[0-9a-f]{64}$")
            self.assertTrue(entry["path"])
            self.assertNotIn("HOME", entry.get("note", "").upper().replace("STACK_HOME", ""))

    def test_claude_code_divergence_is_declared_and_consistent(self):
        divergence = {entry["id"]: entry for entry in self.pins.get("divergence", [])}
        self.assertIn("claude-code", divergence)
        by_id = {tool["id"]: tool for tool in self.pins["tools"]}
        self.assertEqual(divergence["claude-code"]["pinned_floor"], by_id["claude-code"]["version"])

    def test_schema_doc_exists_next_to_the_pins_file_and_is_valid_json(self):
        self.assertTrue(SCHEMA_PATH.is_file())
        document = json.loads(SCHEMA_PATH.read_text())
        self.assertEqual(document["properties"]["schema_version"]["const"], 2)

    def test_every_landscape_winner_has_a_tools_or_candidates_entry(self):
        # switch.md: "pins v2 has one entry per installable winner ... unknown fields for other
        # winners can be filled later by the qualify wave (mark pending)" -- every real winner
        # component_id (excluding the landscape's own "candidate:"-prefixed alternative rows,
        # which are unpinned by construction and not adopted winners) must appear somewhere in
        # this file, even if only as a pending candidates[] stub.
        have = {tool["id"] for tool in self.pins["tools"]} | {c["id"] for c in self.pins.get("candidates", [])}
        landscape_dir = ROOT / "catalogs" / "landscape"
        missing = set()
        for landscape_file in sorted(landscape_dir.glob("*.json")):
            document = json.loads(landscape_file.read_text())
            for layer in document.get("layers") or []:
                for winner in layer.get("winners") or []:
                    component_id = winner.get("component_id")
                    if isinstance(component_id, str) and not component_id.startswith("candidate:") and component_id not in have:
                        missing.add(component_id)
        self.assertEqual(missing, set(), f"{len(missing)} landscape winner(s) have no pins-v2 entry at all")


class ShippedFileParityTests(unittest.TestCase):
    """The real, committed pins v2 file cross-checked against the real, committed
    manifests/stack.json and catalogs/landscape/*.json: must pass with zero errors
    (the one declared claude-code divergence is report-only, not an error)."""

    def test_real_repository_state_has_no_parity_errors(self):
        errors, warnings = validate_pins_v2(ROOT)
        self.assertEqual(errors, [])

    def test_the_declared_claude_code_divergence_is_reported_not_swallowed(self):
        _errors, warnings = validate_pins_v2(ROOT)
        self.assertTrue(any("claude-code" in warning and "divergence" in warning for warning in warnings),
                         warnings)


class SyntheticParityTests(unittest.TestCase):
    """validate_pins_v2 exercised against synthetic fixtures under a temp --root, so the
    mismatch/divergence/pending logic is proven independently of today's real content."""

    def write(self, root: Path, relative: str, content) -> None:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(content))

    def pins_fixture(self, tools, *, candidates=None, divergence=None):
        return {"schema_version": 2, "platform": "linux-x86_64", "tools": tools,
                "candidates": candidates or [], "divergence": divergence or []}

    def tool(self, tool_id, version, **overrides):
        base = {
            "id": tool_id, "version": version, "kind": "tarball", "url": "https://example.invalid/x",
            "sha256": "0" * 64, "install_note": "fixture",
            "root_name": f"{tool_id}-{version}", "current_link": f"current/{tool_id}",
            "entrypoints": [], "surfaces": [], "state_dirs": [], "window": "default", "rollback_class": "safe",
        }
        base.update(overrides)
        return base

    def test_matching_versions_across_stack_and_landscape_have_no_errors_or_warnings(self):
        with self._temp_root() as root:
            self.write(root, "adoption/pins-linux-x86_64.json",
                      self.pins_fixture([self.tool("foo", "1.0.0")]))
            self.write(root, "manifests/stack.json",
                      {"components": [{"id": "foo", "version": "1.0.0"}]})
            self.write(root, "catalogs/landscape/foundation.json",
                      {"layers": [{"catalog": "foundation", "layer_id": "l1",
                                  "winners": [{"component_id": "foo", "pin": "1.0.0"}]}]})
            errors, warnings = validate_pins_v2(root)
            self.assertEqual(errors, [])
            self.assertEqual(warnings, [])

    def test_undeclared_mismatch_against_stack_is_an_error(self):
        with self._temp_root() as root:
            self.write(root, "adoption/pins-linux-x86_64.json", self.pins_fixture([self.tool("foo", "2.0.0")]))
            self.write(root, "manifests/stack.json", {"components": [{"id": "foo", "version": "1.0.0"}]})
            errors, _warnings = validate_pins_v2(root)
            self.assertTrue(any("foo" in e and "1.0.0" in e for e in errors))

    def test_declared_divergence_downgrades_the_same_mismatch_to_a_warning(self):
        with self._temp_root() as root:
            self.write(root, "adoption/pins-linux-x86_64.json", self.pins_fixture(
                [self.tool("foo", "2.0.0")],
                divergence=[{"id": "foo", "kind": "native-auto-update", "note": "expected drift"}]))
            self.write(root, "manifests/stack.json", {"components": [{"id": "foo", "version": "1.0.0"}]})
            errors, warnings = validate_pins_v2(root)
            self.assertEqual(errors, [])
            self.assertTrue(any("foo" in w for w in warnings))

    def test_landscape_mismatch_is_also_caught(self):
        with self._temp_root() as root:
            self.write(root, "adoption/pins-linux-x86_64.json", self.pins_fixture([self.tool("foo", "1.0.0")]))
            self.write(root, "catalogs/landscape/foundation.json",
                      {"layers": [{"catalog": "foundation", "layer_id": "l1",
                                  "winners": [{"component_id": "foo", "pin": "0.9.0"}]}]})
            errors, _warnings = validate_pins_v2(root)
            self.assertTrue(any("foundation/l1" in e for e in errors))

    def test_a_tool_id_absent_from_stack_and_landscape_is_silently_skipped(self):
        with self._temp_root() as root:
            self.write(root, "adoption/pins-linux-x86_64.json", self.pins_fixture([self.tool("node", "24.0.0")]))
            errors, warnings = validate_pins_v2(root)
            self.assertEqual(errors, [])
            self.assertEqual(warnings, [])

    def test_pending_candidate_is_a_warning_not_an_error(self):
        with self._temp_root() as root:
            self.write(root, "adoption/pins-linux-x86_64.json", self.pins_fixture(
                [self.tool("foo", "1.0.0")], candidates=[{"id": "vllm", "status": "pending", "note": "not pinned yet"}]))
            errors, warnings = validate_pins_v2(root)
            self.assertEqual(errors, [])
            self.assertTrue(any("vllm" in w for w in warnings))

    def test_non_pending_candidate_is_an_error(self):
        with self._temp_root() as root:
            self.write(root, "adoption/pins-linux-x86_64.json", self.pins_fixture(
                [self.tool("foo", "1.0.0")], candidates=[{"id": "vllm", "status": "installed", "note": "oops"}]))
            errors, _warnings = validate_pins_v2(root)
            self.assertTrue(any("vllm" in e for e in errors))

    def test_divergence_naming_an_unknown_id_is_an_error(self):
        with self._temp_root() as root:
            self.write(root, "adoption/pins-linux-x86_64.json", self.pins_fixture(
                [self.tool("foo", "1.0.0")],
                divergence=[{"id": "does-not-exist", "kind": "x", "note": "y"}]))
            errors, _warnings = validate_pins_v2(root)
            self.assertTrue(any("does-not-exist" in e for e in errors))

    def test_schema_version_1_pins_file_is_skipped_entirely(self):
        # A platform not yet migrated (e.g. a future adoption/pins-macos-arm64.json
        # migration wave) must not be cross-checked by this v2-specific rule.
        with self._temp_root() as root:
            self.write(root, "adoption/pins-linux-x86_64.json",
                      {"schema_version": 1, "platform": "linux-x86_64", "tools": [self.tool("foo", "9.9.9")]})
            self.write(root, "manifests/stack.json", {"components": [{"id": "foo", "version": "1.0.0"}]})
            errors, warnings = validate_pins_v2(root)
            self.assertEqual(errors, [])
            self.assertEqual(warnings, [])

    def test_missing_pins_file_is_not_an_error(self):
        with self._temp_root() as root:
            errors, warnings = validate_pins_v2(root)
            self.assertEqual(errors, [])
            self.assertEqual(warnings, [])

    class _TempRootContext:
        def __enter__(self):
            import tempfile
            self._tmp = tempfile.TemporaryDirectory()
            return Path(self._tmp.name)

        def __exit__(self, *exc_info):
            self._tmp.cleanup()

    def _temp_root(self):
        return self._TempRootContext()


if __name__ == "__main__":
    unittest.main()
