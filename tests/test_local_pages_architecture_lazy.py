"""The initial Architecture page defers evidence-heavy layer tables."""
import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("architecture_lazy_view", ROOT / "tools/local-pages/architecture_view.py")
VIEW = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VIEW)


class ArchitectureLazyTests(unittest.TestCase):
    def setUp(self):
        self.tool = {"name": "sample-tool", "invoke": {"status": "unmeasured", "reason": "Bash-run CLI invocations are outside the producer's MCP counters"}}
        self.layer = {"key": "foundation:runtime", "catalog": "foundation", "layer_id": "runtime", "title": "Runtime", "candidates": [self.tool], "winners": [self.tool], "alternatives": [], "rejected": [], "g5_candidates": [], "source_refs": []}
        self.model = {"layers": [self.layer], "adoption_observation": {}, "sources": [], "design": {}}

    def test_initial_page_excludes_component_rows_and_all_tables(self):
        self.layer["g5_candidates"] = [dict(self.tool, name=f"candidate-{i}", rationale="Evidence details " * 100) for i in range(200)]
        outputs = {}
        html, receipt = VIEW.render(self.model, {"items": []}, detail_outputs=outputs)
        self.assertNotIn("<table>", html)
        self.assertNotIn("candidate-199", html)
        self.assertIn("data-layer-src=", html)
        self.assertIn("200 G5 candidates", html)
        self.assertLess(len(html.encode()), 20000)
        self.assertEqual(receipt["rendered_layer_count"], 1)
        self.assertTrue(outputs)
        self.assertTrue(all(isinstance(body, bytes) for body in outputs.values()))
        detail = b"".join(outputs.values()).decode()
        self.assertIn("candidate-199", detail)
        self.assertIn("<table>", detail)
        self.assertNotIn("<details open", detail)
        self.assertIn("Bash-run CLI invocations", detail)

    def test_mapping_accepts_catalog_join_keys_and_keeps_the_basis(self):
        inventory = {"items": [{"name": "stack-runtime", "kind": "component", "layer_keys": ["foundation/runtime"], "mapping_source": "foundation.json#winners/component_id", "mapping_reason": "canonical component ID join"}]}
        mapped, unmapped = VIEW.join_inventory(self.model, inventory)
        self.assertEqual(unmapped, [])
        self.assertEqual(mapped["foundation:runtime"][0]["mapping_basis"], "canonical component ID join")

    def test_observational_sessions_and_newest_failed_native_receipt_are_visible(self):
        self.tool["invoke"] = {"status": "measured", "measure": "sessions", "calls": 7, "window_hours": 24, "roles": [{"client": "Codex", "role": "owning-lane", "calls": 7, "sessions": 7}]}
        self.tool["e2e"] = {"verified": False, "kind": "native_cli_e2e", "evidence_scope": "native_host", "date": "2026-10-08T12:00:00Z", "path": "evidence/latest.json", "sha256": "a" * 64, "result": "fail", "command": "vendor-cli check", "reason": "newest receipt records failure"}
        html, _ = VIEW.render(self.model, {"items": []})
        self.assertIn("observational (organic use, not a controlled trial)", html)
        self.assertIn("7 recorded sessions", html)
        self.assertNotIn("7 recorded calls", html)
        self.assertIn("native E2E on this host", html)
        self.assertIn("result: fail", html)
        self.assertIn("a" * 64, html)

    def test_sanitized_local_receipts_remain_metadata_and_deferred(self):
        self.model["host_receipts"] = {"items": [{"path": f"command-center/windows/window-{i}/RECEIPT.md", "sha256": "c" * 64, "bytes": 100, "title": f"Local source {i}", "mtime_utc": "2026-10-08T12:00:00Z", "label": "local host receipt (state root)"} for i in range(14)], "sources": [{"path": "/state/coordination/command-center/pages/host-receipts-index.json", "sha256": "d" * 64}], "coverage": {"status": "recorded"}}
        outputs = {}
        html, receipt = VIEW.render(self.model, {"items": []}, detail_outputs=outputs)
        self.assertIn("14 local host receipts", html)
        self.assertNotIn("Local source 13", html)
        self.assertEqual(receipt["unmapped_inventory_items"], 0)
        local = b"".join(raw for name, raw in outputs.items() if "local-host-receipts" in name).decode()
        self.assertEqual(local.count("local host receipt (state root)"), 14)
        self.assertIn("Local source 13", local)
        self.assertIn("index-declared", local)
        self.assertIn("mtime", local)
        self.assertIn("does not supply execution date, command or result", local)
        self.assertNotIn("verified upstream", local)


if __name__ == "__main__":
    unittest.main()
