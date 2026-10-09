"""Evidence readers refuse invalid candidates and redirected registered files."""

from contextlib import contextmanager
import builtins
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("architecture_evidence_boundary", ROOT / "tools/local-pages/architecture_evidence.py")
evidence = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evidence)
SNAPSHOT_DIRECTORY = "coordination/ns2604-coop/notes/adoption-evidence-20261008"


class ArchitectureEvidenceBoundaryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root, self.state = Path(temporary.name) / "repo", Path(temporary.name) / "state"
        self.root.mkdir()
        self.state.mkdir()
        self.policy_path = self.root.parent / "independent-policy.json"
        policy = json.loads((ROOT / "tools/local-pages/source_policy.json").read_text())
        policy["architecture"] = {
            "architecture_registry": [{"root": "repo", "path": "manifests/evidence.json"}],
            "architecture_readiness": [{"root": "repo", "path": "catalogs/north-star/readiness.json"}],
            "architecture_receipt": [{"root": "repo", "path": path} for path in ("evidence/receipts/redirected/receipt.json", "evidence/receipts/approved-large.json")],
        }
        policy["architecture_families"] = {"architecture_adoption_snapshot": {"root": "state", "directory": SNAPSHOT_DIRECTORY, "filename": r"adoption-now-[a-f0-9]{16}\.json"}}
        self.write(self.root.parent, self.policy_path.name, policy)
        approval = patch.object(evidence, "SOURCE_POLICY_PATH", self.policy_path)
        approval.start()
        self.addCleanup(approval.stop)

    def write(self, base, relative, value):
        path = base / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def legitimate_snapshot(self):
        document = {"schema": "adoption-now/1", "generated_utc": "2026-10-09T03:55:28Z", "window_hours": 24, "claude_by_role": {}, "codex_by_lane": {}}
        raw = json.dumps(document).encode()
        path = self.state / SNAPSHOT_DIRECTORY / ("adoption-now-" + hashlib.sha256(raw).hexdigest()[:16] + ".json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        return path

    def registry(self, relative, path):
        raw = path.read_bytes()
        self.write(self.root, "manifests/evidence.json", {"receipts": [{"kind": "native_cli_e2e", "component_ids": ["context-mode"], "path": relative}], "files": [{"path": relative, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}]})

    @contextmanager
    def forbid(self, forbidden):
        forbidden = forbidden.resolve()
        calls = []
        originals = builtins.open, io.open, os.open
        def guarded(function):
            def checked(value, *args, **kwargs):
                if not isinstance(value, int):
                    lexical = Path(os.fsdecode(value))
                    if lexical.resolve() == forbidden:
                        calls.append(str(lexical))
                        raise AssertionError("unapproved evidence reached a real file open")
                return function(value, *args, **kwargs)
            return checked
        with patch.object(builtins, "open", guarded(originals[0])), patch.object(io, "open", guarded(originals[1])), patch.object(os, "open", guarded(originals[2])):
            yield calls

    def test_invalid_snapshot_names_are_filtered_before_any_read(self):
        selected = self.legitimate_snapshot()
        for name in ["adoption-now-credentials.json", "adoption-now-fffffffffffffff.json", "adoption-now-FFFFFFFFFFFFFFFF.json", "adoption-now-unrelated.json"]:
            with self.subTest(name=name):
                invalid = self.write(self.state, SNAPSHOT_DIRECTORY + "/" + name, {"synthetic": "unapproved candidate"})
                with self.forbid(invalid) as calls:
                    observation = evidence.invocation_source(self.state)
                self.assertEqual(calls, [])
                self.assertEqual(observation["path"], str(selected))

    def test_valid_snapshot_leaf_symlink_is_refused_before_target_read(self):
        self.legitimate_snapshot()
        forbidden = self.write(self.state, "coordination/e2e-truth-20261006/synthetic.json", {"synthetic": "private target"})
        link = self.state / SNAPSHOT_DIRECTORY / "adoption-now-0123456789abcdef.json"
        link.symlink_to(forbidden)
        with self.forbid(forbidden) as calls, self.assertRaises(ValueError):
            evidence.invocation_source(self.state)
        self.assertEqual(calls, [])

    def test_snapshot_parent_symlink_is_refused_before_target_read(self):
        forbidden_root = self.state / "coordination/e2e-truth-20261006"
        forbidden = self.write(self.state, "coordination/e2e-truth-20261006/adoption-now-0123456789abcdef.json", {"synthetic": "private target"})
        directory = self.state / SNAPSHOT_DIRECTORY
        directory.parent.mkdir(parents=True, exist_ok=True)
        directory.symlink_to(forbidden_root)
        with self.forbid(forbidden) as calls, self.assertRaises(ValueError):
            evidence.invocation_source(self.state)
        self.assertEqual(calls, [])

    def test_registered_receipt_parent_symlink_is_refused_even_with_matching_digest(self):
        forbidden_root = self.state / "coordination/e2e-truth-20261006"
        forbidden = self.write(self.state, "coordination/e2e-truth-20261006/receipt.json", {"kind": "native_cli_e2e", "component_ids": ["context-mode"], "recorded_at_utc": "2026-10-09T03:55:28Z", "command": "context-mode --version", "result": "pass"})
        relative = "evidence/receipts/redirected/receipt.json"
        redirected = self.root / "evidence/receipts/redirected"
        redirected.parent.mkdir(parents=True, exist_ok=True)
        redirected.symlink_to(forbidden_root)
        self.registry(relative, forbidden)
        with self.forbid(forbidden) as calls, self.assertRaises(ValueError):
            evidence._EvidenceSources(self.root, self.state)
        self.assertEqual(calls, [])

    def test_registration_does_not_authorize_an_unlisted_ordinary_receipt(self):
        relative = "evidence/receipts/ordinary-unreviewed.json"
        target = self.write(self.root, relative, {"kind": "native_cli_e2e", "component_ids": ["context-mode"]})
        self.registry(relative, target)
        with self.forbid(target) as calls, self.assertRaises(ValueError):
            evidence._EvidenceSources(self.root, self.state)
        self.assertEqual(calls, [])

    def test_fixed_registry_symlink_is_refused_before_target_read(self):
        forbidden = self.write(self.state, "coordination/e2e-truth-20261006/evidence.json", {"receipts": [], "files": []})
        index = self.root / "manifests/evidence.json"
        index.parent.mkdir(parents=True)
        index.symlink_to(forbidden)
        with self.forbid(forbidden) as calls, self.assertRaises(ValueError):
            evidence._EvidenceSources(self.root, self.state)
        self.assertEqual(calls, [])

    def test_registered_protected_name_is_a_policy_failure_without_read(self):
        relative = "evidence/receipts/credentials.json"
        target = self.write(self.root, relative, {"kind": "native_cli_e2e", "component_ids": ["context-mode"]})
        self.registry(relative, target)
        with self.forbid(target) as calls, self.assertRaises(ValueError):
            evidence._EvidenceSources(self.root, self.state)
        self.assertEqual(calls, [])

    def test_host_index_parent_symlink_propagates_before_open(self):
        forbidden_root = self.state / "coordination/e2e-truth-20261006"
        forbidden = self.write(self.state, "coordination/e2e-truth-20261006/host-receipts-index.json", {"schema": "host-receipts-index/1"})
        parent = self.state / "coordination/command-center/pages"
        parent.parent.mkdir(parents=True)
        parent.symlink_to(forbidden_root)
        policy = json.loads(self.policy_path.read_text())
        policy["architecture"]["architecture_projection"] = [{"root": "state", "path": "coordination/command-center/pages/host-receipts-index.json"}]
        self.write(self.root.parent, self.policy_path.name, policy)
        with self.forbid(forbidden) as calls, self.assertRaises(ValueError):
            evidence.host_receipts_index(self.state)
        self.assertEqual(calls, [])

    def test_reader_from_another_module_cannot_hide_policy_failure_as_missing_evidence(self):
        policy_spec = importlib.util.spec_from_file_location("independent_architecture_policy_instance", ROOT / "tools/local-pages/source_policy.py")
        policy = importlib.util.module_from_spec(policy_spec)
        policy_spec.loader.exec_module(policy)
        self.write(self.root, "manifests/evidence.json", {"receipts": [], "files": []})
        sources = evidence._EvidenceSources(self.root, self.state)
        sources.reads = policy.ArchitectureReads(self.root, self.state, policy_path=self.policy_path)
        target = self.write(self.root, "evidence/receipts/ordinary-unreviewed.json", {"kind": "native_cli_e2e"})
        with self.forbid(target) as calls, self.assertRaises(ValueError):
            sources.load("evidence/receipts/ordinary-unreviewed.json")
        self.assertEqual(calls, [])
        self.assertNotIn("evidence/receipts/ordinary-unreviewed.json", sources.cache)

    def test_approved_large_receipt_is_unmeasured_without_unbounded_body_read(self):
        relative = "evidence/receipts/approved-large.json"
        target = self.write(self.root, relative, {"padding": "x" * (evidence._LIMIT + 1)})
        self.registry(relative, target)
        sources = evidence._EvidenceSources(self.root, self.state)
        self.assertIsNone(sources.load(relative))
        self.assertEqual(sources.stats["registry_read_limit"], 1)
        self.assertIn("read bound", sources.readability[relative])

    def test_large_receipt_parent_symlink_still_fails_closed_before_target_read(self):
        forbidden_root = self.state / "coordination/e2e-truth-20261006"
        forbidden = self.write(self.state, "coordination/e2e-truth-20261006/receipt.json", {"padding": "x" * (evidence._LIMIT + 1)})
        relative = "evidence/receipts/redirected/receipt.json"
        redirected = self.root / "evidence/receipts/redirected"
        redirected.parent.mkdir(parents=True, exist_ok=True)
        redirected.symlink_to(forbidden_root)
        self.registry(relative, forbidden)
        with self.forbid(forbidden) as calls, self.assertRaises(ValueError):
            evidence._EvidenceSources(self.root, self.state)
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
