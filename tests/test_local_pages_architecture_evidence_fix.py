"""Receipt registry, result recency, and observation producer regressions."""

import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("architecture_evidence_fix", ROOT / "tools/local-pages/architecture_evidence.py")
evidence = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evidence)


class ArchitectureEvidenceFixTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "repo"
        self.state = Path(temporary.name) / "state"

    def write(self, relative, document, root=None):
        path = (root or self.root) / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(document), encoding="utf-8")
        return path

    def register(self, receipts):
        rows, files = [], []
        for path, document in receipts:
            output = self.write(path, document)
            rows.append({"kind": document["kind"], "component_ids": document.get("component_ids", []), "path": path})
            raw = output.read_bytes()
            files.append({"path": path, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)})
        self.write("manifests/evidence.json", {"receipts": rows, "files": files})

    def result(self, **component):
        return evidence._e2e(self.root, {"component_id": "context-mode", "pin": "v2", **component}, [], "matrix", evidence._EvidenceSources(self.root))

    def test_kind_registry_component_ids_and_nested_results_bind(self):
        path = "adoption/receipt.json"
        self.register([(path, {"kind": "native_cli_e2e", "component_ids": ["context-mode"], "recorded_at_utc": "2026-10-08T22:00:00Z", "data": {"pin": "v1", "command": "context-mode --version", "exit_code": 0}})])
        result = self.result()
        self.assertEqual(result["path"], path)
        self.assertEqual(result["evidence_scope"], "native_host")
        self.assertEqual(result["evidence_class"], "native_cli_e2e")
        self.assertEqual(result["date"], "2026-10-08T22:00:00Z")
        self.assertEqual(result["command"], "context-mode --version")
        self.assertEqual(result["result"], "pass")
        self.assertEqual(result["selected_pin"], "v2")
        self.assertEqual(result["observed_pin"], "v1")
        self.assertFalse(result["pin_matches"])

    def test_newest_failure_does_not_disappear_behind_older_pass(self):
        self.register([(f"evidence/receipts/{name}.json", {"kind": "native_cli_e2e", "component_ids": ["context-mode"], "recorded_at_utc": date, "pin": "v2", "command": "context-mode --version", "result": result}) for name, date, result in [("older", "2026-10-08T21:00:00Z", "pass"), ("newer", "2026-10-08T22:00:00Z", "failure")]])
        result = self.result()
        self.assertTrue(result["path"].endswith("newer.json"))
        self.assertEqual(result["result"], "failure")
        self.assertFalse(result["verified"])
        self.assertIn("failure", result["reason"])

    def test_registry_hash_mismatch_cannot_be_used_as_evidence(self):
        path = "evidence/receipts/exact.json"
        document = {"kind": "native_cli_e2e", "component_ids": ["context-mode"], "recorded_at_utc": "2026-10-08T22:00:00Z", "pin": "v2", "command": "context-mode --version", "result": "pass"}
        self.register([(path, document)])
        self.write(path, {**document, "result": "failure"})
        self.assertIsNone(self.result()["path"])

    def test_client_sessions_use_retained_population_without_server_attribution(self):
        observation = {"status": "recorded", "verified": True, "window_hours": 24, "roles": [{"name": "CC", "client": "Claude", "sessions": 4, "servers": {"context-mode": {"calls": 7, "sessions": 2}}}, {"name": "lane", "client": "Codex", "conversations": 3, "servers": {}}]}
        claude = evidence._invoke({"component_id": "claude-code"}, observation)
        codex = evidence._invoke({"component_id": "codex"}, observation)
        self.assertEqual(claude["measure"], "sessions")
        self.assertEqual(claude["calls"], 4)
        self.assertEqual(codex["measure"], "sessions")
        self.assertEqual(codex["calls"], 3)
        self.assertEqual(codex["roles"][0]["conversations"], 3)

    def test_cli_unmeasured_reason_names_producer_boundary(self):
        result = evidence._invoke({"component_id": "gh"}, {"status": "recorded", "roles": [], "window_hours": 24})
        self.assertIsNone(result["calls"])
        self.assertIn("Bash", result["reason"])
        self.assertIn("producer", result["reason"])

    def test_checked_at_uses_its_recorded_timezone(self):
        self.register([("evidence/receipts/exact.json", {"kind": "native_cli_e2e", "component_ids": ["context-mode"], "checked_at": "2026-10-08T16:00:00", "timezone": "America/New_York", "command": "context-mode --version", "result": "pass"})])
        result = self.result()
        self.assertEqual(result["date"], "2026-10-08T20:00:00Z")
        self.assertEqual(result["date_original"], "2026-10-08T16:00:00")
        self.assertEqual(result["date_timezone"], "America/New_York")

    def test_vector_command_is_one_execution_with_a_program_basename(self):
        self.register([("evidence/receipts/exact.json", {"kind": "native_cli_e2e", "component_ids": ["context-mode"], "recorded_at_utc": "2026-10-08T22:00:00Z", "native_primary_metadata": {"executed_command_vector": ["/usr/bin/context-mode", "--version"], "exit_code": 0}})])
        result = self.result()
        self.assertEqual(result["command_count"], 1)
        self.assertEqual(result["command_programs"], ["context-mode"])

    def test_multi_component_observation_does_not_inherit_harness_version(self):
        self.register([("evidence/receipts/exact.json", {"kind": "native_cli_e2e", "component_ids": ["context-mode", "codex"], "recorded_at_utc": "2026-10-08T22:00:00Z", "command": "context-mode --version", "result": "pass", "execution": {"harness": {"repository": "harbor-framework/harbor", "version": "v55"}, "context-mode": {"repository": "mksglu/context-mode", "version": "v1"}}})])
        result = self.result()
        self.assertEqual(result["observed_pin"], "v1")
        self.assertFalse(result["pin_matches"])

    def test_kind_and_absent_result_remain_visible_without_e2e_promotion(self):
        self.register([("evidence/receipts/exact.json", {"kind": "historical_inventory", "component_ids": ["context-mode"], "recorded_at_utc": "2026-10-08T22:00:00Z"})])
        result = self.result()
        self.assertEqual(result["kind"], "historical_inventory")
        self.assertEqual(result["result"], "result field absent")
        self.assertTrue(result["receipt_verified"])
        self.assertFalse(result["verified"])

    def test_native_receipt_with_absent_fields_keeps_digest_and_kind(self):
        self.register([("evidence/receipts/exact.json", {"kind": "native_model_e2e", "component_ids": ["context-mode"]})])
        result = self.result()
        self.assertEqual(result["kind"], "native_model_e2e")
        self.assertEqual(result["result"], "result field absent")
        self.assertEqual(result["command_count"], 0)
        self.assertTrue(result["receipt_verified"])
        self.assertFalse(result["verified"])
        self.assertNotIn("no upstream", result["status"])

    def test_vendor_suite_class_is_kept_apart_from_native_host_receipts(self):
        self.register([("evidence/receipts/exact.json", {"kind": "native_cli_e2e", "evidence_class": "RECORDED-UPSTREAM-TEST", "component_ids": ["context-mode"], "recorded_at_utc": "2026-10-08T22:00:00Z", "command": "npm test", "result": "pass"})])
        self.assertEqual(self.result()["evidence_scope"], "vendor_test_suite")

    def test_linked_command_array_needs_its_registered_digest(self):
        path = "evidence/receipts/exact.json"
        commands_path = "evidence/artifacts/exact/commands.json"
        self.register([(path, {"kind": "native_cli_e2e", "component_ids": ["context-mode"], "recorded_at_utc": "2026-10-08T22:00:00Z", "commands": commands_path})])
        output = self.write(commands_path, [{"argv": ["context-mode", "--version"], "exit_code": 0}])
        index_path = self.root / "manifests/evidence.json"
        index = json.loads(index_path.read_text())
        raw = output.read_bytes()
        index["files"].append({"path": commands_path, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)})
        self.write("manifests/evidence.json", index)
        result = self.result()
        self.assertEqual(result["command_count"], 1)
        self.assertEqual(result["command_programs"], ["context-mode"])
        self.assertEqual(result["result"], "pass")
        self.write(commands_path, [{"argv": ["context-mode", "--version"], "exit_code": 1}])
        result = self.result()
        self.assertEqual(result["command_count"], 0)
        self.assertEqual(result["result"], "result field absent")

    def test_inventory_attachment_does_not_restore_older_success(self):
        self.register([("evidence/receipts/newer.json", {"kind": "native_cli_e2e", "component_ids": ["context-mode"], "recorded_at_utc": "2026-10-08T22:00:00Z", "command": "context-mode --version", "result": "failure"})])
        items = [{"component_id": "context-mode", "pin": "v2"}]
        index = {"context-mode": [{"e2e": {"path": "older.json", "date": "2026-10-08T21:00:00Z", "verified": True}}]}
        evidence.attach_inventory(items, index, root=self.root, state_root=self.state)
        self.assertEqual(items[0]["e2e"]["result"], "failure")
        self.assertFalse(items[0]["evidence_complete"])

    def test_missing_component_pin_does_not_fall_back_to_harness_pin(self):
        self.register([("evidence/receipts/exact.json", {"kind": "native_cli_e2e", "component_ids": ["context-mode", "codex"], "recorded_at_utc": "2026-10-08T22:00:00Z", "pin": "harness-v55", "command": "context-mode --version", "result": "pass", "execution": {"harness": {"repository": "harbor-framework/harbor", "version": "v55"}}})])
        result = self.result()
        self.assertIsNone(result["observed_pin"])
        self.assertIsNone(result["pin_matches"])

    def test_recorded_date_outranks_observed_date_for_registered_receipts(self):
        self.register([("evidence/receipts/exact.json", {"kind": "native_cli_e2e", "component_ids": ["context-mode"], "recorded_at_utc": "2026-10-08T22:00:00Z", "observed_at_utc": "2026-10-09T22:00:00Z", "command": "context-mode --version", "result": "pass"})])
        result = self.result()
        self.assertEqual(result["date"], "2026-10-08T22:00:00Z")
        self.assertEqual(result["metadata_locators"]["date"], "/recorded_at_utc")

    def test_generic_vendor_suite_retains_newest_failure_or_absent_fields(self):
        path = "evidence/receipts/exact.json"
        for extra in [{"command": "npm test", "result": "failure"}, {}]:
            self.register([(path, {"kind": "e2e", "evidence_class": "RECORDED-UPSTREAM-TEST", "component_ids": ["context-mode"], "recorded_at_utc": "2026-10-08T22:00:00Z", **extra})])
            result = self.result()
            self.assertEqual(result["evidence_scope"], "vendor_test_suite")
            self.assertEqual(result["kind"], "e2e")
            self.assertEqual(result["path"], path)
            self.assertEqual(result["result"], extra.get("result", "result field absent"))
            self.assertTrue(result["receipt_verified"])
            self.assertFalse(result["verified"])


if __name__ == "__main__":
    unittest.main()
