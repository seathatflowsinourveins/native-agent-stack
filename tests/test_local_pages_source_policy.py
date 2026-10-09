"""Exact read permissions exercised through the real native receipt builder."""

from contextlib import contextmanager, nullcontext
import builtins
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
DEFAULT = json.loads((ROOT / "tools/local-pages/source_policy.json").read_text())
FIXTURE_OVERRIDES = {
    "gaps_source": "fixture-overrides/gaps.json",
    "roadmap_source": "fixture-overrides/roadmap.json",
    "roadmap_inputs": "fixture-overrides/inputs.json",
    "current_source": "fixture-overrides/current.json",
}


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


class SourcePolicyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.root, self.state = self.base / "repo", self.base / "state"
        self.root.mkdir()
        self.state.mkdir()
        native_path = self.root / "tools/north-star/build_readiness.py"
        native_path.parent.mkdir(parents=True)
        shutil.copyfile(ROOT / "tools/north-star/build_readiness.py", native_path)
        self.native = module(native_path, "source_policy_native_fixture")
        self.spec_path = self.root / "tools/north-star/sources.json"
        self.policy_path = self.base / "independent-policy.json"
        # Permissions are created independently of the selecting source index.
        self.permissions = {
            **DEFAULT,
            "sources": {key: [{"root": "repo", "path": "fixtures/" + key + ".json"}] for key in DEFAULT["sources"]},
            "linked_receipts": {
                "supporting": DEFAULT["linked_receipts"]["supporting"] + [{"root": "repo", "path": "fixtures/support.json"}],
                "sdk_item": DEFAULT["linked_receipts"]["sdk_item"] + [{"root": "state", "path": "fixtures/sdk-item.json"}],
                "sdk_raw": DEFAULT["linked_receipts"]["sdk_raw"] + [{"root": "state", "path": "fixtures/sdk-raw.json"}],
            },
            "overrides": {key: [{"root": "state", "path": path}] for key, path in FIXTURE_OVERRIDES.items()},
        }
        self.write(self.policy_path, self.permissions)
        self.spec = {"schema_version": 1, "sources": {key: {"root": "repo", "path": "fixtures/" + key + ".json"} for key in DEFAULT["sources"]}}
        for key in DEFAULT["sources"]:
            self.write(self.root / ("fixtures/" + key + ".json"), {})
        self.write(self.root / "fixtures/foundation.json", {"layers": [{"layer_id": "fixture", "winners": [{"component_id": "fixture"}]}]})
        self.write(self.root / "fixtures/stack.json", {"components": [{"id": "fixture", "evidence_ids": ["fixture-support"]}]})
        self.support = {"receipts": [{"id": "fixture-support", "path": "fixtures/support.json"}], "files": []}
        self.write(self.root / "fixtures/evidence.json", self.support)
        self.write(self.root / "fixtures/support.json", {"kind": "fixture"})
        self.raw_path = self.state / "fixtures/sdk-raw.json"
        self.write(self.raw_path, {"kind": "fixture"})
        self.item_path = self.state / "fixtures/sdk-item.json"
        self.item = {"id": "fixture-sdk", "raw_receipt": {"path": str(self.raw_path), "sha256": self.digest(self.raw_path)}}
        self.write(self.item_path, self.item)
        self.sdk_index = {"items": [{"id": "fixture-sdk", "receipt_path": str(self.item_path), "receipt_sha256": self.digest(self.item_path)}]}
        self.write(self.root / "fixtures/sdk_rows.json", self.sdk_index)
        self.write(self.spec_path, self.spec)
        self.forbidden_repo = self.root / "fixtures/credentials.json"
        self.forbidden_state = self.state / "fixtures/credentials.json"
        # These are controlled synthetic files, never host credential stores.
        self.write(self.forbidden_repo, {})
        self.write(self.forbidden_state, {})
        for relative in FIXTURE_OVERRIDES.values():
            self.write(self.state / relative, {})

    @staticmethod
    def write(path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")

    @staticmethod
    def digest(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def guard(self):
        path = ROOT / "tools/local-pages/source_policy.py"
        if not path.exists():
            return nullcontext()  # RED reproduces the native read before the adapter exists.
        policy = module(path, "source_policy_fixture")
        return policy.guard_native(self.native, self.root, self.state, self.spec_path, policy_path=self.policy_path)

    @contextmanager
    def watch_forbidden_opens(self, forbidden):
        calls = []
        target = forbidden.absolute()
        original_builtin, original_io, original_os = builtins.open, io.open, os.open
        def path_of(value, options):
            if isinstance(value, int):
                return None
            path = Path(os.fsdecode(value))
            if not path.is_absolute() and options.get("dir_fd") is not None:
                path = Path(os.readlink("/proc/self/fd/" + str(options["dir_fd"]))) / path
            return path.absolute()
        def watched(function):
            def call(value, *args, **options):
                candidate = path_of(value, options)
                if candidate == target:
                    calls.append(str(candidate))
                    raise AssertionError("forbidden synthetic input reached a real file open")
                return function(value, *args, **options)
            return call
        with patch.object(builtins, "open", watched(original_builtin)), patch.object(io, "open", watched(original_io)), patch.object(os, "open", watched(original_os)):
            yield calls

    def assert_refused_before_open(self, forbidden):
        with self.watch_forbidden_opens(forbidden) as calls:
            with self.assertRaises(ValueError):
                with self.guard():
                    self.native.build(self.root, self.state, self.spec_path)
        self.assertEqual(calls, [])

    def test_every_direct_source_key_is_independently_approved_before_native_open(self):
        for key in DEFAULT["sources"]:
            with self.subTest(key=key):
                original = self.spec["sources"][key]
                self.spec["sources"][key] = {"root": "repo", "path": "fixtures/credentials.json"}
                self.write(self.spec_path, self.spec)
                self.assert_refused_before_open(self.forbidden_repo)
                self.spec["sources"][key] = original

    def test_unused_declaration_cannot_extend_permissions(self):
        self.spec["sources"]["unused-extra"] = {"root": "repo", "path": "fixtures/credentials.json"}
        self.write(self.spec_path, self.spec)
        self.assert_refused_before_open(self.forbidden_repo)

    def test_every_supporting_receipt_path_requires_its_independent_role(self):
        for permitted in DEFAULT["linked_receipts"]["supporting"]:
            with self.subTest(role="supporting", permitted=permitted["path"]):
                self.permissions["linked_receipts"]["supporting"] = [permitted]
                self.write(self.policy_path, self.permissions)
                self.support["receipts"][0]["path"] = "fixtures/credentials.json"
                self.write(self.root / "fixtures/evidence.json", self.support)
                self.assert_refused_before_open(self.forbidden_repo)

    def test_every_sdk_item_receipt_path_requires_its_independent_role(self):
        for permitted in DEFAULT["linked_receipts"]["sdk_item"]:
            with self.subTest(role="sdk_item", permitted=permitted["path"]):
                self.permissions["linked_receipts"]["sdk_item"] = [permitted]
                self.write(self.policy_path, self.permissions)
                self.sdk_index["items"][0]["receipt_path"] = str(self.forbidden_state)
                self.write(self.root / "fixtures/sdk_rows.json", self.sdk_index)
                self.assert_refused_before_open(self.forbidden_state)

    def test_every_sdk_raw_receipt_path_requires_its_independent_role(self):
        for permitted in DEFAULT["linked_receipts"]["sdk_raw"]:
            with self.subTest(role="sdk_raw", permitted=permitted["path"]):
                self.permissions["linked_receipts"]["sdk_raw"] = [permitted]
                self.write(self.policy_path, self.permissions)
                self.item["raw_receipt"]["path"] = str(self.forbidden_state)
                self.write(self.item_path, self.item)
                self.sdk_index["items"][0]["receipt_sha256"] = self.digest(self.item_path)
                self.write(self.root / "fixtures/sdk_rows.json", self.sdk_index)
                self.assert_refused_before_open(self.forbidden_state)

    def test_approved_native_build_keeps_native_digest_and_restores_module(self):
        expected = self.native.render(self.native.build(self.root, self.state, self.spec_path))
        original_class, original_path, original_build = self.native.Receipts, self.native.Path, self.native.build
        with self.guard():
            actual = self.native.render(self.native.build(self.root, self.state, self.spec_path))
        self.assertEqual(actual, expected)
        self.assertIs(self.native.Receipts, original_class)
        self.assertIs(self.native.Path, original_path)
        self.assertIs(self.native.build, original_build)

    def test_source_index_override_is_approved_before_it_is_opened(self):
        policy = module(ROOT / "tools/local-pages/source_policy.py", "index_policy_fixture")
        with self.watch_forbidden_opens(self.forbidden_repo) as calls:
            with self.assertRaises(ValueError):
                policy.validate_index_path(self.root, self.state, self.forbidden_repo, self.policy_path)
        self.assertEqual(calls, [])

    def test_unapproved_ordinary_filename_is_refused_even_when_its_json_is_valid(self):
        ordinary = self.root / "fixtures/unapproved.json"
        self.write(ordinary, {})
        self.spec["sources"]["foundation"] = {"root": "repo", "path": "fixtures/unapproved.json"}
        self.write(self.spec_path, self.spec)
        self.assert_refused_before_open(ordinary)

    def test_committed_policy_approves_every_committed_native_index_source(self):
        policy = module(ROOT / "tools/local-pages/source_policy.py", "committed_parity_policy").load_policy(ROOT / "tools/local-pages/source_policy.json")
        index = json.loads((ROOT / "tools/north-star/sources.json").read_text())
        self.assertTrue(index["sources"])
        for key, record in index["sources"].items():
            with self.subTest(key=key):
                policy.validate("source:" + key, record["root"], record["path"])
        policy.validate_sources(index)

    def test_ordinary_unlisted_paths_require_each_native_read_role(self):
        repo_path = self.root / "fixtures/ordinary-public.json"
        state_path = self.state / "fixtures/ordinary-public.json"
        self.write(repo_path, {})
        self.write(state_path, {})
        for key in self.spec["sources"]:
            with self.subTest(role="source:" + key):
                original = self.spec["sources"][key]
                self.spec["sources"][key] = {"root": "repo", "path": repo_path.relative_to(self.root).as_posix()}
                self.write(self.spec_path, self.spec)
                self.assert_refused_before_open(repo_path)
                self.spec["sources"][key] = original
        self.write(self.spec_path, self.spec)
        with self.subTest(role="supporting"):
            self.support["receipts"][0]["path"] = repo_path.relative_to(self.root).as_posix()
            self.write(self.root / "fixtures/evidence.json", self.support)
            self.assert_refused_before_open(repo_path)
            self.support["receipts"][0]["path"] = "fixtures/support.json"
            self.write(self.root / "fixtures/evidence.json", self.support)
        with self.subTest(role="sdk_item"):
            self.sdk_index["items"][0]["receipt_path"] = str(state_path)
            self.sdk_index["items"][0]["receipt_sha256"] = self.digest(state_path)
            self.write(self.root / "fixtures/sdk_rows.json", self.sdk_index)
            self.assert_refused_before_open(state_path)
        self.sdk_index["items"][0]["receipt_path"] = str(self.item_path)
        with self.subTest(role="sdk_raw"):
            self.item["raw_receipt"]["path"] = str(state_path)
            self.item["raw_receipt"]["sha256"] = self.digest(state_path)
            self.write(self.item_path, self.item)
            self.sdk_index["items"][0]["receipt_sha256"] = self.digest(self.item_path)
            self.write(self.root / "fixtures/sdk_rows.json", self.sdk_index)
            self.assert_refused_before_open(state_path)
        policy = module(ROOT / "tools/local-pages/source_policy.py", "ordinary_index_policy")
        with self.subTest(role="source_index"), self.watch_forbidden_opens(repo_path) as calls:
            with self.assertRaises(ValueError):
                with policy.guard_native(self.native, self.root, self.state, repo_path, policy_path=self.policy_path):
                    self.native.build(self.root, self.state, repo_path)
        self.assertEqual(calls, [])

    def test_missing_or_malformed_policy_refuses_before_any_native_input_open(self):
        original_builtin, original_io, original_os = builtins.open, io.open, os.open
        cases = ("absent", "invalid JSON", "non-object", "unknown schema", "missing reader pin")
        for invalid in cases:
            with self.subTest(invalid=invalid):
                if invalid == "absent":
                    self.policy_path.unlink(missing_ok=True)
                elif invalid == "invalid JSON":
                    self.policy_path.write_text("{invalid", encoding="utf-8")
                elif invalid == "non-object":
                    self.write(self.policy_path, [])
                elif invalid == "unknown schema":
                    self.write(self.policy_path, {**self.permissions, "schema": "local-pages-source-policy/999"})
                else:
                    self.write(self.policy_path, {**self.permissions, "native_reader": {}})
                attempts = []
                def guard(original):
                    def checked(value, *args, **kwargs):
                        if not isinstance(value, int):
                            path = Path(os.fsdecode(value)).absolute()
                            if path.is_relative_to(self.root) or path.is_relative_to(self.state):
                                attempts.append(path)
                                raise AssertionError("invalid policy reached a native input open")
                        return original(value, *args, **kwargs)
                    return checked
                with patch.object(builtins, "open", guard(original_builtin)), patch.object(io, "open", guard(original_io)), patch.object(os, "open", guard(original_os)):
                    with self.assertRaises((OSError, ValueError)):
                        with self.guard():
                            self.native.build(self.root, self.state, self.spec_path)
                self.assertEqual(attempts, [])

    def test_hypothetical_protected_policy_entries_are_rejected_before_membership(self):
        for relative in ["fixtures/.env", "fixtures/credential.env", "fixtures/env.json", "fixtures/environment.txt", "fixtures/client-secret.json", "fixtures/client_secrets.json", "e2e-truth-20261006/probe/receipt.json"]:
            with self.subTest(relative=relative):
                forbidden = self.state / relative
                self.write(forbidden, {})
                self.permissions["linked_receipts"]["sdk_raw"] = [{"root": "state", "path": relative}]
                self.write(self.policy_path, self.permissions)
                self.assert_refused_before_open(forbidden)

    def test_approved_source_symlink_is_rejected_without_following_target(self):
        path = self.root / "fixtures/profile.json"
        path.unlink()
        path.symlink_to(self.forbidden_repo)
        self.assert_refused_before_open(self.forbidden_repo)

    def test_linked_source_symlink_and_nonregular_file_are_refused(self):
        self.item_path.unlink()
        self.item_path.symlink_to(self.forbidden_state)
        self.assert_refused_before_open(self.forbidden_state)
        self.item_path.unlink()
        os.mkfifo(self.item_path)
        self.assert_refused_before_open(self.forbidden_state)

    def test_policy_file_is_bounded_regular_and_never_follows_a_symlink(self):
        policy = module(ROOT / "tools/local-pages/source_policy.py", "bounded_policy_fixture")
        self.policy_path.unlink()
        self.policy_path.symlink_to(self.forbidden_repo)
        with self.watch_forbidden_opens(self.forbidden_repo) as calls:
            with self.assertRaises((OSError, ValueError)):
                policy.load_policy(self.policy_path)
        self.assertEqual(calls, [])
        self.policy_path.unlink()
        os.mkfifo(self.policy_path)
        with self.assertRaises(ValueError):
            policy.load_policy(self.policy_path)
        self.policy_path.unlink()
        self.policy_path.write_bytes(b"x" * (policy.MAX_POLICY_BYTES + 1))
        with self.assertRaises(ValueError):
            policy.load_policy(self.policy_path)

    def test_unsupported_native_reader_is_refused_and_policy_hash_is_bound(self):
        policy = module(ROOT / "tools/local-pages/source_policy.py", "reader_pin_policy_fixture")
        self.assertEqual(policy.capture_policy(self.policy_path)["sha256"], self.digest(self.policy_path))
        path = Path(self.native.__file__)
        path.write_text(path.read_text() + "\n# changed native fixture\n")
        with self.assertRaisesRegex(ValueError, "approved read seam"):
            with self.guard():
                self.native.build(self.root, self.state, self.spec_path)

    def test_every_override_role_is_exact_and_refused_before_file_open(self):
        policy = module(ROOT / "tools/local-pages/source_policy.py", "override_policy_fixture").load_policy(self.policy_path)
        for key, relative in FIXTURE_OVERRIDES.items():
            with self.subTest(key=key):
                selected = self.state / relative
                self.assertEqual(policy.validate_override(key, selected, self.root, self.state), selected)
                for forbidden in (self.forbidden_repo, self.forbidden_state):
                    with self.watch_forbidden_opens(forbidden) as calls:
                        with self.assertRaises(ValueError):
                            policy.validate_override(key, forbidden, self.root, self.state)
                    self.assertEqual(calls, [])
                unrelated = self.state / "fixture-overrides/unrelated.json"
                self.write(unrelated, {})
                with self.watch_forbidden_opens(unrelated) as calls:
                    with self.assertRaises(ValueError):
                        policy.validate_override(key, unrelated, self.root, self.state)
                self.assertEqual(calls, [])

    def test_override_approval_never_accepts_another_role_or_a_symlink(self):
        policy = module(ROOT / "tools/local-pages/source_policy.py", "cross_role_policy_fixture").load_policy(self.policy_path)
        with self.assertRaises(ValueError):
            policy.validate_override("gaps_source", self.state / FIXTURE_OVERRIDES["current_source"], self.root, self.state)
        path = self.state / FIXTURE_OVERRIDES["gaps_source"]
        path.unlink()
        path.symlink_to(self.forbidden_state)
        with self.watch_forbidden_opens(self.forbidden_state) as calls:
            with self.assertRaises(ValueError):
                policy.validate_override("gaps_source", path, self.root, self.state)
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
