"""Hourly source changes rebuild Architecture; ordinary refreshes reuse it."""
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from tests.local_pages_architecture_policy_fixture import policy_fixture, G5

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("architecture_builder", ROOT / "tools/local-pages/architecture_builder.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ArchitectureCacheTests(unittest.TestCase):
    def test_same_snapshot_reuses_but_new_hourly_snapshot_rebuilds(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root, state, output = base / "repo", base / "state", base / "served"
            receipt = base / "nonserved/receipt.json"
            for relative in ("catalogs/landscape/manifest.json", "catalogs/north-star/readiness.json", "adoption/skills/manifest.json", "manifests/stack.json", "manifests/evidence.json", "adoption/manifest.json"):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("{}")
            current = state / "coordination/command-center/pages/cc-now.json"
            current.parent.mkdir(parents=True)
            current.write_text("{}")
            observation = {"sha256": "a" * 64}
            page_module = SimpleNamespace(no_symlinks=lambda path: path.absolute())
            evidence_module = SimpleNamespace(invocation_source=lambda unused, reads=None: observation)
            original_load = MODULE.load
            modules = {"build_pages": page_module, "architecture_evidence": evidence_module,
                       "source_policy": original_load("source_policy"),
                       "architecture_inventory": original_load("architecture_inventory"),
                       "architecture_sources": SimpleNamespace(_FINAL_ASSET=G5)}
            policy_path = policy_fixture(base / "independent-policy.json")
            calls = []
            captured_inventory = []
            signature = modules["architecture_inventory"].input_signature
            def observe_signature(*args, **kwargs):
                sources = signature(*args, **kwargs)
                captured_inventory.append(sources)
                return sources
            def generate(*unused):
                calls.append(observation["sha256"])
                output.mkdir(exist_ok=True)
                (output / "architecture.html").write_text(json.dumps({"generation": len(calls), "inventory_sources": captured_inventory[-1]}))
                receipt.parent.mkdir(parents=True, exist_ok=True)
                result = {"generated_utc": "2026-01-01T00:00:00Z", "generation": len(calls), "inventory_sources": captured_inventory[-1]}
                receipt.write_text(json.dumps(result))
                return result
            with patch.object(modules["architecture_inventory"], "USER_ROOT", base / "user"), patch.object(modules["architecture_inventory"], "input_signature", side_effect=observe_signature), patch.object(MODULE, "SOURCE_POLICY_PATH", policy_path), patch.object(MODULE, "load", side_effect=lambda name: modules[name]), patch.object(MODULE, "build", side_effect=generate):
                MODULE.refresh_if_changed(root, state, output, receipt)
                MODULE.refresh_if_changed(root, state, output, receipt)
                self.assertEqual(len(calls), 1)
                observation["sha256"] = "b" * 64
                MODULE.refresh_if_changed(root, state, output, receipt)
                self.assertEqual(len(calls), 2)
                projection = current.with_name("automation-projection.json")
                projection.write_text('{"schema":"automation-projection/1","hooks":[],"cron":[]}')
                MODULE.refresh_if_changed(root, state, output, receipt)
                self.assertEqual(len(calls), 3)
                MODULE.refresh_if_changed(root, state, output, receipt)
                self.assertEqual(len(calls), 3)
                self.assertFalse(receipt.is_relative_to(output))
                local_index = current.with_name("host-receipts-index.json")
                local_index.write_text('{"schema":"host-receipts-index/1","receipts":[]}')
                MODULE.refresh_if_changed(root, state, output, receipt)
                self.assertEqual(len(calls), 4)
                retained = state / "research/fullspeed-20261008/g5-stars-gap/local-pages/refresh-receipt.json"
                retained.parent.mkdir(parents=True, exist_ok=True)
                retained.write_text('{"schema_version":1,"kind":"local_page_refresh"}')
                MODULE.refresh_if_changed(root, state, output, receipt)
                self.assertEqual(len(calls), 5)
                script = root / "scripts/evidence_manifest.py"
                script.parent.mkdir(exist_ok=True)
                script.write_text("# approved fixture one\n")
                MODULE.refresh_if_changed(root, state, output, receipt)
                self.assertEqual(len(calls), 6)
                script.write_text("# approved fixture two\n")
                MODULE.refresh_if_changed(root, state, output, receipt)
                self.assertEqual(len(calls), 7)
                MODULE.refresh_if_changed(root, state, output, receipt)
                self.assertEqual(len(calls), 7)
                previous_page = (output / "architecture.html").read_bytes()
                previous_receipt = receipt.read_bytes()
                (script.parent / "unreviewed.py").write_text("# unlisted fixture\n")
                MODULE.refresh_if_changed(root, state, output, receipt)
                self.assertNotEqual((output / "architecture.html").read_bytes(), previous_page)
                self.assertNotEqual(receipt.read_bytes(), previous_receipt)
                published = json.loads(receipt.read_text())
                self.assertEqual(published["generation"], 8)
                self.assertTrue(any(row["path"] == str(script.parent / "unreviewed.py") and row["status"] == "UNAPPROVED" for row in published["inventory_sources"]))
                self.assertEqual(len(calls), 8)
                MODULE.refresh_if_changed(root, state, output, receipt)
                self.assertEqual(len(calls), 8)
                (script.parent / "unreviewed.py").unlink()
                MODULE.refresh_if_changed(root, state, output, receipt)
                self.assertEqual(len(calls), 9)
                self.assertFalse(any(row["path"] == str(script.parent / "unreviewed.py") for row in json.loads(receipt.read_text())["inventory_sources"]))
if __name__ == "__main__":
    unittest.main()
