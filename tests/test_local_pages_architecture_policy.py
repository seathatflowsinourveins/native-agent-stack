"""Architecture role permissions precede every real file-open attempt."""

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
SPEC = importlib.util.spec_from_file_location("architecture_policy_fixture", ROOT / "tools/local-pages/source_policy.py")
policy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(policy)


class ArchitecturePolicyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.root, self.state = self.base / "repo", self.base / "state"
        self.root.mkdir()
        self.state.mkdir()
        self.document = json.loads((ROOT / "tools/local-pages/source_policy.json").read_text())
        self.document["architecture"] = {
            "architecture_manifest": [{"root": "repo", "path": "catalogs/landscape/manifest.json"}],
            "architecture_catalog": [{"root": "repo", "path": "catalogs/landscape/fixture.json"}],
            "architecture_supplement": [{"root": "repo", "path": "catalogs/landscape/supplement.json"}],
            "architecture_registry": [{"root": "repo", "path": "manifests/evidence.json"}],
            "architecture_readiness": [{"root": "repo", "path": "catalogs/north-star/readiness.json"}],
            "architecture_receipt": [{"root": "repo", "path": "evidence/receipts/fixture/receipt.json"}],
            "architecture_projection": [{"root": "state", "path": "coordination/command-center/pages/cc-now.json"}],
        }
        self.document["architecture_families"] = {"architecture_adoption_snapshot": {
            "root": "state", "directory": "coordination/ns2604-coop/notes/adoption-evidence-20261008",
            "filename": "adoption-now-[a-f0-9]{16}\\.json",
        }}
        self.policy_path = self.base / "independent-architecture-policy.json"
        self.write(self.policy_path, self.document)
        self.target = self.state / "coordination/e2e-truth-20261006/credentials.json"
        self.write(self.target, {"controlled": "forbidden fixture"})

    @staticmethod
    def write(path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")

    def reads(self):
        return policy.ArchitectureReads(self.root, self.state, policy_path=self.policy_path)

    @contextmanager
    def watch(self, forbidden):
        calls = []
        target = forbidden.absolute()
        original_builtin, original_io, original_os = builtins.open, io.open, os.open
        def watched(function):
            def call(value, *args, **options):
                if not isinstance(value, int):
                    candidate = Path(os.fsdecode(value))
                    if not candidate.is_absolute() and options.get("dir_fd") is not None:
                        candidate = Path(os.readlink("/proc/self/fd/" + str(options["dir_fd"]))) / candidate
                    if candidate.absolute() == target:
                        calls.append(str(candidate))
                        raise AssertionError("forbidden Architecture target reached file open")
                return function(value, *args, **options)
            return call
        with patch.object(builtins, "open", watched(original_builtin)), patch.object(io, "open", watched(original_io)), patch.object(os, "open", watched(original_os)):
            yield calls

    def test_every_architecture_role_refuses_unapproved_input_before_open(self):
        reads = self.reads()
        for role in self.document["architecture"]:
            with self.subTest(role=role), self.watch(self.target) as calls:
                with self.assertRaises(policy.SourcePolicyError):
                    reads.read(role, self.target)
                self.assertEqual(calls, [])
        with self.watch(self.target) as calls:
            with self.assertRaises(policy.SourcePolicyError):
                reads.read("unapproved-role", self.target)
        self.assertEqual(calls, [])

    def test_authorized_content_and_digest_use_the_same_bounded_bytes(self):
        path = self.root / "manifests/evidence.json"
        self.write(path, {"receipts": [], "files": []})
        raw, metadata = self.reads().read("architecture_registry", path)
        self.assertEqual(raw, path.read_bytes())
        self.assertEqual(metadata["sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(metadata["bytes"], len(raw))
        self.assertEqual(metadata["role"], "architecture_registry")
        with self.assertRaises(policy.SourcePolicyError):
            self.reads().read("architecture_registry", path, max_bytes=1)

    def test_leaf_and_parent_symlinks_are_refused_before_target_open(self):
        projection = self.state / "coordination/command-center/pages/cc-now.json"
        projection.parent.mkdir(parents=True)
        projection.symlink_to(self.target)
        with self.watch(self.target) as calls:
            with self.assertRaises(policy.SourcePolicyError):
                self.reads().read("architecture_projection", projection)
        self.assertEqual(calls, [])
        receipt = self.root / "evidence/receipts/fixture/receipt.json"
        receipt.parent.parent.mkdir(parents=True)
        receipt.parent.symlink_to(self.target.parent, target_is_directory=True)
        with self.watch(self.target) as calls:
            with self.assertRaises(policy.SourcePolicyError):
                self.reads().read("architecture_receipt", receipt)
        self.assertEqual(calls, [])

    def test_only_the_reviewed_immutable_projection_family_is_authorized(self):
        directory = self.state / "coordination/ns2604-coop/notes/adoption-evidence-20261008"
        valid = directory / "adoption-now-0123456789abcdef.json"
        self.write(valid, {"schema": "fixture"})
        reads = self.reads()
        self.assertEqual(reads.authorize("architecture_adoption_snapshot", valid), valid)
        raw, _ = reads.read("architecture_adoption_snapshot", valid)
        self.assertTrue(raw)
        for name in ["adoption-now-credentials.json", "adoption-now-ABCDEF0123456789.json", "adoption-now-123.json"]:
            path = directory / name
            self.write(path, {})
            with self.subTest(name=name), self.watch(path) as calls:
                with self.assertRaises(policy.SourcePolicyError):
                    reads.read("architecture_adoption_snapshot", path)
                self.assertEqual(calls, [])
        valid.unlink()
        valid.symlink_to(self.target)
        with self.watch(self.target) as calls:
            with self.assertRaises(policy.SourcePolicyError):
                reads.read("architecture_adoption_snapshot", valid)
        self.assertEqual(calls, [])

    def test_family_cannot_be_extended_to_a_broad_prefix(self):
        self.document["architecture_families"]["architecture_adoption_snapshot"]["filename"] = ".*"
        self.write(self.policy_path, self.document)
        with self.assertRaises(policy.SourcePolicyError):
            self.reads()

    def test_policy_cannot_approve_protected_architecture_paths(self):
        self.document["architecture"]["architecture_receipt"] = [{"root": "state", "path": "coordination/e2e-truth-20261006/credentials.json"}]
        self.write(self.policy_path, self.document)
        with self.watch(self.target) as calls:
            with self.assertRaises(policy.SourcePolicyError):
                self.reads()
        self.assertEqual(calls, [])

    def test_design_user_grant_is_exact_and_does_not_extend_native_roots(self):
        user = self.base / "user"
        design = user / ".agents/skills/frontend-design/SKILL.md"
        design.parent.mkdir(parents=True)
        design.write_text("controlled design fixture\n")
        self.document["architecture"]["architecture_design"] = [{"root": "user", "path": ".agents/skills/frontend-design/SKILL.md"}]
        self.write(self.policy_path, self.document)
        reads = policy.ArchitectureReads(self.root, self.state, policy_path=self.policy_path, user_root=user)
        raw, metadata = reads.read("architecture_design", design)
        self.assertEqual(raw, b"controlled design fixture\n")
        self.assertEqual(metadata["role"], "architecture_design")
        with self.assertRaises(policy.SourcePolicyError):
            reads.read("architecture_projection", design)
        self.document["sources"]["foundation"] = [{"root": "user", "path": ".agents/skills/frontend-design/SKILL.md"}]
        self.write(self.policy_path, self.document)
        with self.assertRaises(policy.SourcePolicyError):
            policy.load_policy(self.policy_path)

    def test_streaming_open_uses_a_verified_descriptor_after_path_replacement(self):
        receipt = self.root / "evidence/receipts/fixture/receipt.json"
        self.write(receipt, {"controlled": "approved fixture"})
        expected = receipt.read_bytes()
        reads = self.reads()
        with reads.open("architecture_receipt", receipt) as handle:
            receipt.unlink()
            receipt.symlink_to(self.target)
            with self.watch(self.target) as calls:
                self.assertEqual(handle.read(), expected)
            self.assertEqual(calls, [])

    def test_user_inventory_content_is_exact_skill_assets_only(self):
        user = self.base / "user"
        target = user / ".codex/agents/fixture.toml"
        target.parent.mkdir(parents=True)
        target.write_text("content must not be authorized\n")
        self.document["architecture"]["architecture_inventory"] = [{"root": "user", "path": ".codex/agents/fixture.toml"}]
        self.write(self.policy_path, self.document)
        with self.watch(target) as calls, self.assertRaises(policy.SourcePolicyError):
            policy.ArchitectureReads(self.root, self.state, policy_path=self.policy_path, user_root=user)
        self.assertEqual(calls, [])

    def test_metadata_only_grant_never_confers_content_read_permission(self):
        user = self.base / "user"
        target = user / ".config/systemd/user/fixture.service"
        target.parent.mkdir(parents=True)
        target.write_text("fixture body must stay unread\n")
        self.document["architecture"]["architecture_inventory_metadata"] = [{"root": "user", "path": ".config/systemd/user/fixture.service"}]
        self.write(self.policy_path, self.document)
        reads = policy.ArchitectureReads(self.root, self.state, policy_path=self.policy_path, user_root=user)
        self.assertEqual(reads.authorize("architecture_inventory_metadata", target), target)
        with self.watch(target) as calls, self.assertRaisesRegex(policy.SourcePolicyError, "metadata-only"):
            reads.read("architecture_inventory_metadata", target)
        self.assertEqual(calls, [])

    def test_large_logical_bound_reads_small_sources_in_bounded_native_chunks(self):
        path = self.root / "manifests/evidence.json"
        self.write(path, {"fixture": "small approved data"})
        expected = path.read_bytes()
        original = policy._open_regular
        requests = []
        class BoundedStream:
            def __init__(self, stream):
                self.stream = stream
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return self.stream.__exit__(*args)
            def fileno(self):
                return self.stream.fileno()
            def read(self, size):
                requests.append(size)
                if size > 65536:
                    raise AssertionError("logical size bound became an eager allocation")
                return self.stream.read(size)
        reads = self.reads()
        with patch.object(policy, "_open_regular", side_effect=lambda *a, **k: BoundedStream(original(*a, **k))):
            raw, receipt = reads.read("architecture_registry", path, max_bytes=512 * 1024 * 1024)
        self.assertEqual(raw, expected)
        self.assertEqual(receipt["sha256"], hashlib.sha256(expected).hexdigest())
        self.assertTrue(requests)
        self.assertLessEqual(max(requests), 65536)


if __name__ == "__main__":
    unittest.main()
