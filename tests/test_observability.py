"""Offline checks for process identity and preserving prior acceptance evidence."""
import ast
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import uuid

ROOT = Path(__file__).resolve().parents[1]

class ObservabilityTests(unittest.TestCase):
    def test_independent_process_identity_preserves_task_attributes(self):
        source = ast.parse((ROOT / "blueprints/us-equities/workers/native_worker.py").read_text())
        helper = next(n for n in source.body if isinstance(n, ast.FunctionDef) and n.name == "process_telemetry_env")
        module = ast.Module(body=[helper], type_ignores=[])
        scope = {"os": os, "uuid": uuid}
        exec(compile(module, "native_worker.py", "exec"), scope)
        with patch.dict(os.environ, {"OTEL_RESOURCE_ATTRIBUTES": "ecosystem.task.id=retained,service.instance.id=parent,ecosystem.client.scope=parent,custom.key=value"}):
            def attrs():
                return dict(x.split("=", 1) for x in scope["process_telemetry_env"]("sdk-worker")["OTEL_RESOURCE_ATTRIBUTES"].split(","))
            first, second = attrs(), attrs()
        self.assertNotEqual(first["service.instance.id"], second["service.instance.id"])
        self.assertNotEqual(first["service.instance.id"], "parent")
        self.assertEqual(first["ecosystem.task.id"], "retained")
        self.assertEqual(first["custom.key"], "value")
        self.assertEqual(first["ecosystem.client.scope"], "sdk-worker")

    def test_sdk_observation_is_bounded_atomic_and_preserves_unknown_usage(self):
        source = ast.parse((ROOT / "blueprints/us-equities/workers/native_worker.py").read_text())
        helper = next(n for n in source.body if isinstance(n, ast.FunctionDef) and n.name == "write_observation")
        scope = {"os": os, "uuid": uuid, "json": json, "Path": Path}
        exec(compile(ast.Module(body=[helper], type_ignores=[]), "native_worker.py", "exec"), scope)
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            data = {"status": "failed", "usage": None, "usage_status": "unavailable_after_failure",
                    "items": [{"text": "PRIVATE_TOOL_CONTENT"}], "error": "PRIVATE_ERROR_CONTENT"}
            scope["write_observation"](target, data)
            files = list(target.iterdir())
            self.assertEqual(len(files), 1)
            self.assertEqual(files[0].suffix, ".json")
            self.assertEqual(files[0].stat().st_mode & 0o777, 0o600)
            saved = json.loads(files[0].read_text())
            self.assertIsNone(saved["usage"])
            self.assertNotIn("PRIVATE_", files[0].read_text())
            self.assertEqual(saved["status"], "failed")
            self.assertEqual(saved["observation_id"], files[0].stem)
            scope["write_observation"](target, data)
            observations = list(target.glob("*.json"))
            self.assertEqual(len(observations), 2)
            self.assertNotEqual(observations[0].read_bytes()[:1000], observations[1].read_bytes()[:1000])

    def test_sdk_observation_never_replaces_existing_receipt(self):
        source = ast.parse((ROOT / "blueprints/us-equities/workers/native_worker.py").read_text())
        helper = next(n for n in source.body if isinstance(n, ast.FunctionDef) and n.name == "write_observation")
        scope = {"os": os, "uuid": uuid, "json": json, "Path": Path}
        exec(compile(ast.Module(body=[helper], type_ignores=[]), "native_worker.py", "exec"), scope)
        with tempfile.TemporaryDirectory() as directory, patch.object(uuid, "uuid4", return_value="fixed-id"):
            target = Path(directory)
            prior = target / "fixed-id.json"
            prior.write_text("original receipt")
            with self.assertRaises(FileExistsError):
                scope["write_observation"](target, {"status": "completed", "usage": {"total": {"inputTokens": 1}}})
            self.assertEqual(prior.read_text(), "original receipt")
            self.assertEqual(list(target.iterdir()), [prior])

    def test_dashboard_keeps_receipt_identity_separate_from_shared_resource(self):
        dashboard = json.loads((ROOT / "observability/backends/templates/ecosystem-dashboard.json.example").read_text())
        panel = next(p for p in dashboard["panels"] if p["id"] == 20)
        query = panel["targets"][0]["expr"]
        self.assertIn('max by (receipt_id)', query)
        self.assertIn('receipt_id != ""', query)
        self.assertNotIn('service_instance_id', query)

    def test_persistence_replay_refuses_before_credentials_or_network(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prior = root / "persistence-before.json"
            prior.write_text("preserve this previous failed attempt")
            result = subprocess.run([sys.executable, str(ROOT / "observability/backends/check_persistence.py"),
                                     "--evidence-dir", str(root), "--grafana-env", str(root / "absent.env")],
                                    capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Use a fresh evidence directory", result.stderr)
            self.assertEqual(prior.read_text(), "preserve this previous failed attempt")
            self.assertEqual(len(list(root.iterdir())), 1)

if __name__ == "__main__":
    unittest.main()
