"""Hourly source changes rebuild Architecture; ordinary refreshes reuse it."""
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

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
            evidence_module = SimpleNamespace(invocation_source=lambda unused: observation)
            modules = {"build_pages": page_module, "architecture_evidence": evidence_module}
            calls = []
            def generate(*unused):
                calls.append(observation["sha256"])
                output.mkdir(exist_ok=True)
                (output / "architecture.html").write_text("generated")
                receipt.parent.mkdir(parents=True, exist_ok=True)
                result = {"generated_utc": "2026-01-01T00:00:00Z", "sources": []}
                receipt.write_text(json.dumps(result))
                return result
            with patch.object(MODULE, "load", side_effect=lambda name: modules[name]), patch.object(MODULE, "build", side_effect=generate):
                MODULE.refresh_if_changed(root, state, output, receipt)
                MODULE.refresh_if_changed(root, state, output, receipt)
                self.assertEqual(len(calls), 1)
                observation["sha256"] = "b" * 64
                MODULE.refresh_if_changed(root, state, output, receipt)
                self.assertEqual(len(calls), 2)
                self.assertFalse(receipt.is_relative_to(output))


if __name__ == "__main__":
    unittest.main()
