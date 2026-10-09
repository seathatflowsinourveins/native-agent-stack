"""Local source-binding regressions; no native process, network or model task.

Uses the repository's unittest receipt checks (test_ecosystem_manifest.py) and
the SHA256-pinned adoption/G5 captures selected by the #835 review. These checks
establish record consistency, never truth or upstream memory acceptance.
"""

import copy
import hashlib
import json
from pathlib import Path
import shlex
import unittest


ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / "docs/decisions/2026-10-08-memory-roles-live-host.json"
SOURCE = ROOT / "docs/decisions/memory-adoption-835"
DECISIONS = {
    "claude_native_memory", "ai_memory", "hindsight", "context_mode",
    "codebase_memory", "qmd", "graphiti",
}
HASHES = {
    "adoption-now-5de97cf238b3d28a.json":
        "5de97cf238b3d28aa9f7d5110a05857204a847b0c75cda8971de8e142e362e36",
    "adoption-now-8682d1d326f29798.json":
        "8682d1d326f2979802efa32d156d9db14dba3ce04273328b6b48a0e227533ac7",
    "INVOKE-RATES-24H-20261008T2330Z.md":
        "86e8a4e0db11846eed1c4e99d5e89321b576cab087aa07676188705de593e541",
    "g5-grand-catalog-ae6cc228.json":
        "ff3b593c34b5f27caba29a915d3ed5443cb3a3d3ebb7e46937277529f0637dc9",
    "ROLE-MCP-TRIAL-REPORT-20261009.md":
        "f0afc2c734b3ad1b70e68cd38d3c844c7f4b1338cc030c8fc40fc88db1e53989",
}
NAMESPACES = {
    "ai-memory", "hindsight", "context-mode", "plugin_context-mode_context-mode",
    "codebase-memory-mcp", "qmd", "qmdshared",
}


def projection(snapshot):
    """Only the exact counter and denominator fields used by this decision."""
    result = {
        "/codex_total_conversations": snapshot["codex_total_conversations"],
        "/claude_total_sessions": snapshot["claude_total_sessions"],
    }
    for group, identities in (("codex_by_lane", "conversations"),
                              ("claude_by_role", "sessions")):
        for bucket, row in snapshot[group].items():
            prefix = f"/{group}/{bucket}"
            result[f"{prefix}/{identities}"] = row[identities]
            for namespace, counter in row["servers"].items():
                if namespace in NAMESPACES:
                    for field in ("calls", identities):
                        result[f"{prefix}/servers/{namespace}/{field}"] = counter[field]
    for layer, row in snapshot["layers"].items():
        for namespace, counter in row["servers"].items():
            if namespace in NAMESPACES:
                for field, value in counter.items():
                    result[f"/layers/{layer}/servers/{namespace}/{field}"] = value
    return result


class MemoryRoleEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.record = json.loads(RECORD.read_text())
        self.evidence = self.record["adoption_evidence"]
        self.snapshots = {
            key: json.loads((ROOT / reference["source_file"]).read_text())
            for key, reference in self.evidence["snapshots"].items()
        }

    def assert_role_bindings(self, evidence):
        self.assertEqual(set(evidence["per_decision_bindings"]), DECISIONS)
        for component, decision in evidence["per_decision_bindings"].items():
            self.assertTrue(decision["owning_lane_or_role"], component)
            self.assertTrue(decision["evidence_limit"], component)
            self.assertEqual(decision["snapshot_sources"], ["baseline", "reconciled"])
            self.assertTrue(decision["role_evidence"], component)
            for binding in decision["role_evidence"]:
                kind = "conversations" if binding["client"] == "codex" else "sessions"
                group = "codex_by_lane" if binding["client"] == "codex" else "claude_by_role"
                self.assertEqual(binding["identity_kind"], kind)
                self.assertEqual(binding["scope_pointer"], f"/{group}/{binding['snapshot_bucket']}")
                for window, measured in binding["snapshots"].items():
                    row = self.snapshots[window][group].get(binding["snapshot_bucket"])
                    counter = row["servers"].get(binding["server_namespace"]) if row else None
                    self.assertEqual(measured["denominator"], row[kind] if row else None)
                    self.assertEqual(measured["calls"], counter["calls"] if counter else None)
                    self.assertEqual(measured["identities"], counter[kind] if counter else None)
                    for field in ("calls", "identities", "denominator"):
                        if measured[field] is not None:
                            self.assertIs(type(measured[field]), int)
                    if counter is None:
                        self.assertTrue(measured["measurement"].startswith("UNMEASURED"))

    def assert_g5_bindings(self, evidence):
        self.assertEqual(set(evidence["per_decision_bindings"]), DECISIONS)
        for component, decision in evidence["per_decision_bindings"].items():
            self.assertIn("g5_binding", decision, component)
            binding = decision["g5_binding"]
            self.assertEqual(binding["commit"], "ae6cc2286643822d3a0218136722c69d0127fcd4")
            self.assertEqual(binding["pr"], 878)
            self.assertTrue(binding["catalog_owner"])
            self.assertTrue(binding["resolution_dependency"])
            source = ROOT / binding["source_file"]
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), binding["source_sha256"])
            rows = json.loads(source.read_text())["rows"]
            pointer = binding["row_pointer"]
            if pointer is not None:
                self.assertEqual(binding["status"], "PENDING until G5 lands")
                self.assertEqual(rows[int(pointer.rsplit("/", 1)[1])]["repository_or_entry"].lower(),
                                 binding["component_identity"].lower())
            else:
                self.assertEqual(binding["status"], "PENDING — row absent at this G5 pin")
                identity = binding["component_identity"].removeprefix("https://github.com/").lower()
                self.assertFalse(any(identity in json.dumps(row).lower() for row in rows))

    def test_source_bytes_and_snapshot_metadata_match_exact_pins(self):
        for filename, digest in HASHES.items():
            with self.subTest(source=filename):
                self.assertEqual(hashlib.sha256((SOURCE / filename).read_bytes()).hexdigest(), digest)
        self.assertEqual(set(self.snapshots), {"baseline", "reconciled"})
        for key, source in self.evidence["snapshots"].items():
            snapshot = self.snapshots[key]
            self.assertEqual(source["sha256"], HASHES[Path(source["source_file"]).name])
            self.assertEqual(source["generated_utc"], snapshot["generated_utc"])
            self.assertEqual(source["window_hours"], snapshot["window_hours"])
            self.assertEqual(source["window_hours"], 24)
            self.assertEqual(source["codex_population"], snapshot["codex_total_conversations"])
            self.assertEqual(source["claude_population"], snapshot["claude_total_sessions"])
        self.assertNotEqual(self.snapshots["baseline"]["generated_utc"],
                            self.snapshots["reconciled"]["generated_utc"])

    def test_every_decision_binds_exact_role_calls_identities_and_denominator(self):
        self.assert_role_bindings(self.evidence)

    def test_reconciliation_covers_every_changed_relevant_scalar(self):
        before = projection(self.snapshots["baseline"])
        after = projection(self.snapshots["reconciled"])
        expected = {
            pointer: {
                "pointer": pointer, "baseline_present": pointer in before,
                "baseline": before.get(pointer), "reconciled_present": pointer in after,
                "reconciled": after.get(pointer),
            }
            for pointer in set(before) | set(after)
            if before.get(pointer) != after.get(pointer) or (pointer in before) != (pointer in after)
        }
        actual_rows = self.evidence["reconciliation"]["changed_fields"]
        actual = {row["pointer"]: row for row in actual_rows}
        self.assertEqual(len(actual), len(actual_rows), "duplicate scalar reconciliation")
        self.assertEqual(actual, expected)
        for window, snapshot in self.snapshots.items():
            rollups = {name: value for layer in snapshot["layers"].values()
                       for name, value in layer["servers"].items() if name in NAMESPACES}
            self.assertEqual(self.evidence["reconciliation"]["producer_layer_rollups"][window], rollups)

    def test_native_memory_and_graphiti_remain_unmeasured(self):
        for component in ("claude_native_memory", "graphiti"):
            decision = self.evidence["per_decision_bindings"][component]
            self.assertTrue(decision["organic_use"].startswith("UNRESOLVED"))
            for binding in decision["role_evidence"]:
                for measured in binding["snapshots"].values():
                    self.assertIsNone(measured["calls"])
                    self.assertIsNone(measured["identities"])
                    self.assertTrue(measured["measurement"].startswith("UNMEASURED"))

    def test_each_g5_binding_is_present_or_individually_pending(self):
        self.assert_g5_bindings(self.evidence)
        present = {key: value["g5_binding"]["row_pointer"]
                   for key, value in self.evidence["per_decision_bindings"].items()
                   if value["g5_binding"]["row_pointer"] is not None}
        self.assertEqual(present, {"ai_memory": "/rows/7", "codebase_memory": "/rows/32"})

    def test_old_markdown_is_history_with_reproducible_source_bytes(self):
        self.assertNotIn("invoke_rates", self.record["routing_supplement"])
        history = self.record["routing_supplement"]["historical_invoke_rates"]
        self.assertTrue(history["evidence_status"].startswith("DATED HISTORY ONLY"))
        source = ROOT / history["source_file"]
        self.assertEqual(source.stat().st_size, 2438)
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), history["sha256"])

    def test_missing_role_binding_cannot_pass_as_client_total_evidence(self):
        changed = copy.deepcopy(self.evidence)
        changed["per_decision_bindings"]["ai_memory"]["role_evidence"] = []
        with self.assertRaises(AssertionError):
            self.assert_role_bindings(changed)

    def test_mixed_window_counter_is_rejected(self):
        changed = copy.deepcopy(self.evidence)
        measured = changed["per_decision_bindings"]["context_mode"]["role_evidence"][0]["snapshots"]
        measured["reconciled"]["calls"] = measured["baseline"]["calls"]
        with self.assertRaises(AssertionError):
            self.assert_role_bindings(changed)

    def test_invented_pending_g5_pointer_is_rejected(self):
        changed = copy.deepcopy(self.evidence)
        binding = changed["per_decision_bindings"]["graphiti"]["g5_binding"]
        binding["row_pointer"] = "/rows/7"
        binding["status"] = "PENDING until G5 lands"
        with self.assertRaises(AssertionError):
            self.assert_g5_bindings(changed)

    def test_accepted_research_job_is_preserved_by_wiring(self):
        landscape = json.loads((ROOT / "manifests/landscape.json").read_text())
        job = landscape["research_memory_jobs"][0]
        self.assertEqual(job["id"], "hindsight-research-memory")
        self.assertIn("native operation accepted", job["status"])
        decision = self.evidence["per_decision_bindings"]["hindsight"]
        self.assertEqual(decision["disposition"], "WIRE")
        self.assertEqual(decision["accepted_job_reference"],
                         "manifests/landscape.json#/research_memory_jobs/0")
        self.assertEqual(decision["wiring"]["recall_types"], ["world", "experience"])
        self.assertEqual(decision["wiring"]["tags_match"], "all_strict")
        self.assertEqual(decision["wiring"]["mcp_allowlist_tools"], 15)
        self.assertFalse(decision["wiring"]["applied"])
        self.assertEqual(self.evidence["per_decision_bindings"]["ai_memory"]["disposition"], "WIRE")
        self.assertEqual(self.evidence["per_decision_bindings"]["graphiti"]["disposition"], "DEFER")
        self.assertFalse(self.evidence["retention_policy"]["counters_gate_readiness"])

    def test_draft_commands_use_named_native_config_and_project(self):
        drafts = ROOT / "adoption/drafts/memory-maintenance-20261008"
        for name in ("ai-lint", "ai-retention-review"):
            lines = (drafts / f"native-memory-{name}.service").read_text().splitlines()
            command = next(line.removeprefix("ExecStart=") for line in lines
                           if line.startswith("ExecStart="))
            args = shlex.split(command)
            self.assertIn("--config", args)
            self.assertEqual(args[args.index("--config") + 1], "%h/.config/ai-memory/config.toml")
            self.assertEqual(args[args.index("--workspace") + 1], "default")
        command = next(line.removeprefix("ExecStart=") for line in
                       (drafts / "native-memory-codegraph-coverage.service").read_text().splitlines()
                       if line.startswith("ExecStart="))
        parameters = json.loads(shlex.split(command)[-1])
        self.assertEqual(parameters["project"],
                         self.record["review_correction"]["codegraph_registered_project"])

    def test_observation_groups_and_context_sources_are_separate(self):
        self.assertNotIn("observation_window_utc", self.record)
        windows = self.record["observation_windows_utc"]
        self.assertEqual(windows["routing_supplement"]["observed_at_utc"],
                         self.record["routing_supplement"]["observed_at_utc"])
        self.assertEqual(windows["native_memory_freshness"]["observed_at_utc"],
                         self.record["routing_supplement"]["native_memory_freshness"]["observed_at_utc"])
        context = next(v for v in self.record["versions"] if v["layer"] == "context-mode")["returned"]
        self.assertNotEqual(context["claude_plugin_record_commit"], context["codex_source_checkout"])
        self.assertNotEqual(context["claude_plugin_record_commit"], context["claude_marketplace_checkout"])

    def test_stage_two_cannot_infer_component_pss_from_whole_arm_memory(self):
        stages = self.record["adoption_stages"]
        choices = stages["stage1"]["role_slots"]
        self.assertEqual(set(choices), DECISIONS)
        self.assertEqual(len({row["role_slot"] for row in choices.values()}), len(DECISIONS))
        for row in choices.values():
            self.assertTrue(row["current_choice"])
            self.assertTrue(row["overlap_disposition"])
            self.assertFalse(row["parallel_default"])
            self.assertIsNone(row["per_session_pss_kb"])
            self.assertTrue(row["stage2_admission"].startswith("BLOCKED ADOPT-NOW"))
            self.assertFalse(row["alwaysLoad"]["applied"])
        gate = stages["stage2"]
        self.assertTrue(gate["memory_cost_required_for_adopt_now"])
        context = gate["trial_context"]
        self.assertEqual(hashlib.sha256((ROOT / context["source_file"]).read_bytes()).hexdigest(),
                         context["sha256"])
        self.assertEqual([v["owned_pss_kb"] for v in context["measurements"]],
                         [1431973, 674966, 837623, 947334])


if __name__ == "__main__":
    unittest.main()
