"""Local structural checks, not a model run or upstream harness acceptance.

Reference seam: tests/test_token_e2e_preregistration.py at 0f76651d;
the #416 compaction draft supplies document structure only.
"""

import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
BLUEPRINT = ROOT / "blueprints/gpt6-lane-compression-ab"
ENGINES = {
    "session-dedup", "ccr", "lite", "rtk", "codex-responses", "headroom",
    "relevance", "caveman", "aggressive", "llmlingua", "ultra", "omniglyph",
}
SAFE_LABELS = {"session-dedup", "ccr", "lite", "headroom"}
ROLES = {"builder", "reviewer", "researcher"}


def digest(value):
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, ensure_ascii=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")).hexdigest()


class CompressionPreregistrationTests(unittest.TestCase):
    def test_draft_contract(self):
        # Fail first at the public document boundary, before either file exists.
        self.assertTrue((BLUEPRINT / "preregistration.json").is_file(),
                        "preregistration.json does not exist yet")
        self.assertTrue((BLUEPRINT / "PREREGISTRATION.md").is_file())
        data = json.loads((BLUEPRINT / "preregistration.json").read_text())
        prose = (BLUEPRINT / "PREREGISTRATION.md").read_text()

        with self.subTest(contract="honest draft"):
            self.assertEqual(data["status"], "DRAFT")
            self.assertFalse(data["frozen"])
            self.assertFalse(data["run_started"])
            self.assertFalse(data["execution_authorized"])
            self.assertIsNone(data["results"])
            self.assertIsNone(data["sealing"]["sealed_at"])
            self.assertIn("DRAFT", prose)
            self.assertEqual(data["client"]["version"], "0.157.1")
            self.assertEqual(data["client"]["profile"], "stack-worker")
            self.assertEqual(data["client"]["effort"], "max")

        cells = {cell["id"]: cell for cell in data["cells"]}
        with self.subTest(contract="clean control and crossed factors"):
            self.assertEqual(set(cells), {"C", "D0", "D1", "A0", "A1"})
            self.assertEqual(cells["C"]["base_url"], "http://127.0.0.1:20128/v1")
            self.assertEqual(cells["C"]["model"], "cx/gpt-6-astra-max")
            self.assertEqual(cells["C"]["engines"], [])
            for cell_id in ("D0", "D1", "A0", "A1"):
                cell = cells[cell_id]
                self.assertEqual(cell["classification"], "confirmatory")
                self.assertEqual(cell["base_url"], "http://127.0.0.1:20129/v1")
                self.assertEqual(cell["model"], "sharedgw/cx/gpt-6-astra-max")
                self.assertEqual(set(cell["engines"]),
                                 SAFE_LABELS if cell_id[0] == "D" else ENGINES)
                self.assertEqual(cell["compression_header"],
                                 None if cell_id[0] == "D" else "allow-lossy")
                self.assertEqual(cell["output_styles_on"], cell_id.endswith("1"))
            self.assertFalse(data["factorization"]["header_off_is_clean_control"])
            self.assertEqual(set(data["exploratory"]["single_engine_order"]),
                             ENGINES - SAFE_LABELS)
            self.assertEqual(data["exploratory"]["keyed_live_zone"]["ttl_minutes"], 60)
            self.assertEqual(data["exploratory"]["keyed_live_zone"]["key_file_mode"], "0600")
            self.assertFalse(data["exploratory"]["allows_promotion"])

        with self.subTest(contract="frozen task packets and controls"):
            self.assertEqual(set(data["task_sets"]), ROLES)
            for role, packet in data["task_sets"].items():
                self.assertEqual(packet["sha256"], digest(packet["packet"]), role)
                self.assertIn(packet["sha256"], prose)
                tasks = packet["packet"]["tasks"]
                self.assertGreaterEqual(len(tasks), 3)
                self.assertEqual(len(tasks), len({t["id"] for t in tasks}))
                for task in tasks:
                    self.assertTrue(task["prompt"])
                    self.assertTrue(task["oracle"])
                    self.assertTrue(task["source_ids"])
                    if role != "builder":
                        examples = task["grader_controls"]
                        self.assertEqual(json.loads(examples[0]["output"]),
                                         task["expected"])
                        self.assertNotEqual(json.loads(examples[1]["output"]),
                                            task["expected"])
                        with self.assertRaises(json.JSONDecodeError):
                            json.loads(examples[2]["output"])
                controls = packet["packet"]["controls"]
                self.assertEqual({c["kind"] for c in controls},
                                 {"known-pass", "known-fail", "malformed"})
                self.assertEqual([c["expected_accept"] for c in controls],
                                 [True, False, False])
                self.assertNotEqual(controls[0]["input"], controls[1]["input"])
                self.assertNotEqual(controls[0]["input"], controls[2]["input"])
            canaries = data["canaries"]
            self.assertEqual(canaries["sha256"], digest(canaries["packet"]))
            self.assertIn("1234567890123456711", canaries["packet"]["numeric_tool_output"])
            self.assertIn("1.50", canaries["packet"]["numeric_tool_output"])
            self.assertGreater(len(canaries["packet"]["long_tool_output"]), 2000)
            self.assertGreater(canaries["packet"]["long_tool_output"].index("TAIL_PIN="), 2000)
            self.assertEqual(set(canaries["packet"]["roles"]), ROLES)
            self.assertIn("multipart", canaries["packet"]["dedup_probe"])
            numeric = canaries["packet"]["numeric_engine_tool_output"]
            self.assertGreater(len(numeric.encode()), 512)
            lexical = json.loads(numeric, parse_int=str, parse_float=str)
            self.assertEqual(lexical["integer"], "1234567890123456711")
            self.assertEqual(lexical["decimal"], "1.50")

        with self.subTest(contract="measurement boundaries"):
            metrics = {m["id"] for m in data["metrics"]}
            self.assertTrue({"task_success", "apply_patch_failures", "verification_failures",
                             "schema_retries", "tool_output_recall", "tokens_in",
                             "tokens_cache_read", "tokens_reasoning", "compression_savings",
                             "latency", "cancellations"} <= metrics)
            accounting = data["accounting"]
            self.assertEqual(accounting["usage_authority"], "20128.call_logs")
            self.assertEqual(accounting["savings_authority"],
                             "20129 GET /api/analytics/compression")
            self.assertFalse(accounting["add_savings_to_usage"])
            self.assertTrue(accounting["cache_read_is_input_subset"])
            self.assertTrue(accounting["reasoning_is_output_subset"])
            self.assertIsNone(accounting["output_column_verified_on_host"])
            self.assertIn("tokens_out", accounting["required_additional_columns"])
            self.assertIn("tokens_in - tokens_cache_read", accounting["uncached_input_formula"])
            self.assertEqual(accounting["total_billed_tokens_formula"],
                             "sum(tokens_in + tokens_out)")
            self.assertTrue(accounting["include_failed_retried_cancelled_attempts"])

        with self.subTest(contract="multi-turn transport and role gates"):
            multi = data["multi_turn"]
            self.assertGreaterEqual(multi["user_turns"], 3)
            self.assertTrue(multi["tools_required_each_turn"])
            self.assertEqual(multi["aggregation_unit"], "task/session/user_turn")
            self.assertTrue({"prompt_cache_key", "session_headers", "affinity_headers",
                             "store", "include", "encrypted_reasoning", "turn_2_tool_roundtrip"}
                            <= set(multi["required_checks"]))
            self.assertEqual(data["role_policy"]["early_canary_roles"], ["builder"])
            self.assertTrue({"reviewer", "researcher", "judgment", "verification", "evidence"}
                            <= set(data["role_policy"]["control_until_pass"]))
            self.assertTrue(data["role_policy"]["record_outputs_require_exact_preservation"])

        with self.subTest(contract="statistics and stopping are specified"):
            analysis = data["analysis"]
            self.assertEqual(analysis["planned_repetitions_per_role_cell"], 240)
            self.assertEqual(analysis["expected_repetitions_per_task_cell"], 40)
            self.assertIn("independent", analysis["sampling"])
            self.assertEqual(analysis["total_confirmatory_sessions"],
                             len(ROLES) * len(cells) * 240)
            self.assertEqual(analysis["success_ni_margin"], 0.05)
            self.assertEqual(analysis["failure_ni_margin"], 0.05)
            self.assertEqual(analysis["multiplicity"]["method"], "holm")
            self.assertEqual(analysis["multiplicity"]["comparisons"], 24)
            self.assertTrue(analysis["degenerate_interval_guard"])
            self.assertIn("bootstrap", analysis["upstream_functions"])
            self.assertIn("permutation_test", analysis["upstream_functions"])
            self.assertTrue(data["decision_rule"]["per_role"])
            self.assertEqual(data["decision_rule"]["objective"],
                             "minimum total billed tokens among non-inferior cells")
            self.assertTrue(data["decision_rule"]["tie_rule"])
            self.assertEqual(data["decision_rule"]["minimum_absolute_combined_success_rate"],
                             0.90)
            budget = data["budget"]
            self.assertGreater(budget["total_token_cap"], 0)
            self.assertEqual(sum(budget["allocations"].values()), budget["total_token_cap"])
            self.assertEqual(budget["max_concurrent_sessions"], 1)
            self.assertTrue(budget["owned_process_cancellation"])
            self.assertTrue(budget["stop_conditions"])

        with self.subTest(contract="source-backed hazards and unresolved acceptance"):
            sources = {s["id"]: s for s in data["sources"]}
            self.assertTrue({"harbor-codex", "promptfoo-responses", "scipy", "statsmodels"}
                            <= set(sources))
            self.assertEqual({h["id"] for h in data["hazards"]},
                             {"H1", "H2", "H3", "H4", "H5", "H6"})
            for hazard in data["hazards"]:
                self.assertTrue(hazard["checks"])
                self.assertTrue(hazard["verification_status"])
                self.assertIsNone(hazard["live_result"])
                for source_id in hazard["source_ids"]:
                    self.assertIn(source_id, sources)
            for gate in data["open_host_gates"]:
                self.assertIsNone(gate["passed"])
            self.assertTrue(data["anti_pattern_log"])


if __name__ == "__main__":
    unittest.main()
