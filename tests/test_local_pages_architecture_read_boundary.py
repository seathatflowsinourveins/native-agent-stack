"""The real Architecture build may open only independently declared inputs."""

from contextlib import contextmanager, ExitStack
import builtins
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
from tests.local_pages_architecture_policy_fixture import policy_fixture
SPEC = importlib.util.spec_from_file_location("architecture_read_boundary", ROOT / "tools/local-pages/architecture_builder.py")
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)
REFRESH = "research/fullspeed-20261008/g5-stars-gap/local-pages/refresh-receipt.json"
G5 = "research/coverage-gap-20261008/grand-catalog/start-closure-1-20261008T2140Z/class-ruling-20261009T0031Z/g5-landscape-evidence-2026-10-08.tar.zst"
RAW_SDK = "research/fullspeed-20261008/sdk-harness-ready/handoff.receipt.json"


@contextmanager
def observed_file_reads(observe, *, observe_metadata=None):
    """Observe real reads using descriptor ancestry on every supported OS."""
    originals = {"builtins": builtins.open, "io": io.open, "os": os.open, "close": os.close,
                 "stat": os.stat, "lstat": os.lstat}
    descriptors = {}
    def observed_path(value, options):
        if isinstance(value, int):
            return descriptors.get(value)
        path = Path(os.fsdecode(value))
        if not path.is_absolute() and options.get("dir_fd") is not None:
            parent = descriptors.get(options["dir_fd"])
            if parent is None:
                raise AssertionError("read watcher received an untracked directory descriptor")
            path = parent / path
        return path.absolute()
    def wrapper(kind):
        def invoke(value, *args, **options):
            path = None if isinstance(value, int) else observed_path(value, options)
            flags = args[0] if kind == "os" and args else options.get("flags", 0)
            directory = kind == "os" and flags & os.O_DIRECTORY
            mode = args[0] if kind != "os" and args else options.get("mode", "r")
            reading = not flags & (os.O_WRONLY | os.O_RDWR) if kind == "os" else isinstance(mode, str) and "r" in mode
            if path is not None and reading and not directory:
                observe(path)
            result = originals[kind](value, *args, **options)
            if kind == "os":
                descriptors[result] = path
            return result
        return invoke
    def close(descriptor):
        originals["close"](descriptor)
        descriptors.pop(descriptor, None)
    def metadata(kind):
        def invoke(value, *args, **options):
            path = observed_path(value, options)
            if path is not None:
                observe_metadata(path)
            return originals[kind](value, *args, **options)
        return invoke
    with ExitStack() as stack:
        for kind, owner in (("builtins", builtins), ("io", io), ("os", os)):
            stack.enter_context(patch.object(owner, "open", wrapper(kind)))
        stack.enter_context(patch.object(os, "close", close))
        if observe_metadata is not None:
            stack.enter_context(patch.object(os, "stat", metadata("stat")))
            stack.enter_context(patch.object(os, "lstat", metadata("lstat")))
        yield


@contextmanager
def observed_forbidden_targets(targets):
    """Watch content, metadata, resolution and digest access to denied fixtures."""
    targets = {Path(path).absolute() for path in targets}
    calls = {kind: [] for kind in ("open", "metadata", "resolve", "hash")}
    original_resolve, original_load = Path.resolve, builder.load

    def observe(kind, path):
        path = Path(path).absolute()
        if path in targets:
            calls[kind].append(path)
            raise AssertionError("ungranted target reached " + kind)

    def resolve(path, *args, **kwargs):
        observe("resolve", path)
        return original_resolve(path, *args, **kwargs)

    def load(name):
        module = original_load(name)
        if name == "architecture_inventory":
            original_hash = module._hash
            def digest(path, *args, **kwargs):
                observe("hash", path)
                return original_hash(path, *args, **kwargs)
            module._hash = digest
        return module

    with observed_file_reads(lambda path: observe("open", path),
                             observe_metadata=lambda path: observe("metadata", path)), \
            patch.object(Path, "resolve", new=resolve), patch.object(builder, "load", side_effect=load):
        yield calls


class ArchitectureReadBoundaryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.root, self.state, self.user = (self.base / name for name in ("repo", "state", "user"))
        self.output, self.receipt = self.base / "served", self.base / "custody/architecture.json"
        self.home = patch.object(Path, "home", return_value=self.user)
        self.home.start()
        self.addCleanup(self.home.stop)
        self.write(self.root, "catalogs/landscape/manifest.json", {"catalogs": {"foundation": "catalogs/landscape/foundation.json"}})
        self.write(self.root, "catalogs/landscape/foundation.json", {"layers": [{"layer_id": "instructions-skills", "title": "Skill instructions", "current_choice": "dated source", "winners": [{"component_id": "context-mode", "name": "context-mode", "repository": "https://github.com/mksglu/context-mode", "pin": "v1"}]}]})
        self.write(self.root, "catalogs/north-star/readiness.json", {})
        self.write(self.root, "adoption/skills/manifest.json", {"skills": []})
        self.write(self.root, "adoption/manifest.json", {})
        self.write(self.root, "manifests/stack.json", {"components": [{"id": "context-mode", "repository": "https://github.com/mksglu/context-mode", "version": "v1"}]})
        self.write(self.root, "manifests/evidence.json", {"receipts": [], "files": []})
        self.write(self.state, "coordination/command-center/pages/cc-now.json", {"schema": "cc-now/1", "updated_utc": "2026-10-09T04:50:00Z", "gates": [{"id": "G5", "state": "READS PENDING"}], "adoption_program": {"stages": ["installed", "invoked", "measured", "accepted"]}})
        self.adoption = {"schema": "adoption-now/1", "generated_utc": "2026-10-09T03:55:28Z", "window_hours": 24, "claude_by_role": {}, "codex_by_lane": {"beni": {"conversations": 3, "servers": {"context-mode": {"calls": 4, "conversations": 3}}}}}
        self.write(self.state, "coordination/command-center/pages/adoption-now.json", self.adoption)
        self.snapshot = self.immutable(self.adoption)
        self.write(self.state, "coordination/command-center/pages/automation-projection.json", {"schema": "automation-projection/1", "generated_utc": "2026-10-09T04:50:00Z", "hooks": [], "cron": []})
        self.raw_cc = "coordination/command-center/windows/window-u/RECEIPT.md"
        self.write(self.state, self.raw_cc, "RAW-CC-SENTINEL")
        self.write(self.state, "coordination/command-center/pages/host-receipts-index.json", {"schema": "host-receipts-index/1", "generated_utc": "2026-10-09T04:50:00Z", "scope": "CC-written metadata only", "receipts": [{"path": self.raw_cc.removeprefix("coordination/"), "sha256": "b" * 64, "bytes": 23, "title": "Local install metadata", "mtime_utc": "2026-10-09T03:50:00Z"}]})
        self.refresh = {"schema_version": 1, "kind": "local_page_refresh", "generated_utc": "2026-10-09T04:50:00Z", "native_readiness_manifest_sha256": "a" * 64, "adoption_role_attribution": {"window": {"start_utc": "2026-10-08T03:55:28Z", "end_utc": "2026-10-09T03:55:28Z"}, "instances": {"role_map": {"beni": "g5-stars-gap"}}, "sources": [{"path": str(self.state / "coordination/ns2604-coop/notes/parking-20261008/park-raw.json")}]}, "inputs": {"sdk": {"path": str(self.state / RAW_SDK)}}}
        self.refresh_raw = self.write(self.state, REFRESH, self.refresh).read_bytes()
        self.write(self.state, RAW_SDK, {"status": "RAW-SDK-SENTINEL"})
        # Copy the actual native reader only to reproduce the old transitive
        # read. The corrected Architecture path must never import or call it.
        native = self.root / "tools/north-star/build_readiness.py"
        native.parent.mkdir(parents=True)
        shutil.copyfile(ROOT / "tools/north-star/build_readiness.py", native)
        native_sources = {}
        for name in ("foundation", "stack", "evidence", "profile", "sdk_contract", "sdk_rows"):
            relative = f"fixtures/{name}.json"
            self.write(self.root, relative, {})
            native_sources[name] = {"root": "repo", "path": relative}
        native_sources["raw_sdk"] = {"root": "state", "path": RAW_SDK}
        self.write(self.root, "tools/north-star/sources.json", {"schema_version": 1, "sources": native_sources})
        self.asset = self.state / G5
        self.asset.parent.mkdir(parents=True)
        row = {"repository_or_entry": "mksglu/context-mode", "qualification": {"catalog": "foundation", "slot": "instructions-skills"}, "disposition": "TRIAL", "evidence_class": "SOURCE-REVIEW", "pin": {"kind": "commit", "version_or_commit": "c" * 40}, "pending": {"status": "PENDING"}}
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w") as archive:
            raw = json.dumps([row]).encode()
            info = tarfile.TarInfo("compact/rows.json")
            info.size = len(raw)
            archive.addfile(info, io.BytesIO(raw))
            unneeded = b"UNAUTHORIZED-G5-MEMBER"
            info = tarfile.TarInfo("private/unused.json")
            info.size = len(unneeded)
            archive.addfile(info, io.BytesIO(unneeded))
        compressed = subprocess.run(["/usr/bin/zstd", "-q", "-c"], input=buffer.getvalue(), capture_output=True, check=True, timeout=20)
        self.asset.write_bytes(compressed.stdout)
        self.policy_path = policy_fixture(self.base / "independent-policy.json")
        approved = patch.object(builder, "SOURCE_POLICY_PATH", self.policy_path)
        approved.start()
        self.addCleanup(approved.stop)

    def write(self, root, relative, document):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(document), encoding="utf-8")
        return path

    def immutable(self, document):
        raw = json.dumps(document).encode()
        digest = hashlib.sha256(raw).hexdigest()
        path = self.state / f"coordination/ns2604-coop/notes/adoption-evidence-20261008/adoption-now-{digest[:16]}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        return path

    @contextmanager
    def read_guard(self):
        fixed = {self.state / name for name in ("coordination/command-center/pages/cc-now.json", "coordination/command-center/pages/adoption-now.json", "coordination/command-center/pages/automation-projection.json", "coordination/command-center/pages/host-receipts-index.json", REFRESH, G5)}
        approved_repo = {self.root / name for name in (
            "catalogs/landscape/manifest.json", "catalogs/landscape/foundation.json",
            "catalogs/north-star/readiness.json", "adoption/skills/manifest.json",
            "adoption/manifest.json", "manifests/stack.json", "manifests/evidence.json",
            "tools/local-pages/architecture_mapping.json", "scripts/approved.py",
        )}
        approved_fixture = {self.policy_path, self.user / ".agents/skills/frontend-design/SKILL.md"}
        opened, commands = [], []
        original_popen = subprocess.Popen

        def permit(path):
            path = path.resolve()
            if path.is_relative_to(self.state):
                relative = path.relative_to(self.state).as_posix()
                immutable = re.fullmatch(r"coordination/ns2604-coop/notes/adoption-evidence-20261008/adoption-now-[a-f0-9]{16}\.json", relative)
                if path not in fixed and not immutable:
                    raise AssertionError("unauthorized state read: " + relative)
            elif path.is_relative_to(self.root) and path not in approved_repo:
                raise AssertionError("unauthorized repository data read: " + path.relative_to(self.root).as_posix())
            elif path.is_relative_to(self.user) and path not in approved_fixture:
                raise AssertionError("unauthorized fixture-user read")
            opened.append(path)

        def guarded_popen(args, *other, **kwargs):
            expected = ["/usr/bin/zstd", "-dc"]
            if args != expected:
                raise AssertionError("unexpected state-reading subprocess")
            handle = kwargs.get("stdin")
            if handle is None or os.fstat(handle.fileno()).st_ino != self.asset.stat().st_ino:
                raise AssertionError("archive subprocess did not use the approved descriptor")
            commands.append(args)
            return original_popen(args, *other, **kwargs)

        def guarded_run(args, *other, **kwargs):
            if args != ["systemctl", "--help"]:
                raise AssertionError("unexpected collector subprocess")
            commands.append(args)
            return subprocess.CompletedProcess(args, 0, "fixture help without JSON output support", "")

        with ExitStack() as stack:
            stack.enter_context(observed_file_reads(permit))
            stack.enter_context(patch.object(subprocess, "Popen", side_effect=guarded_popen))
            stack.enter_context(patch.object(subprocess, "run", side_effect=guarded_run))
            yield opened, commands

    def test_real_build_binds_retained_identity_without_native_sdk_reads(self):
        with self.read_guard() as (opened, commands):
            result = builder.build(self.root, self.state, self.output, self.receipt)
        self.assertEqual(result["native_readiness_manifest_sha256"], "a" * 64)
        identity = result["native_readiness_source"]
        self.assertEqual(identity["path"], str(self.state / REFRESH))
        self.assertEqual(identity["sha256"], hashlib.sha256(self.refresh_raw).hexdigest())
        self.assertEqual(identity["generated_utc"], "2026-10-09T04:50:00Z")
        self.assertEqual(opened.count(self.state / REFRESH), 1)
        self.assertNotIn(self.root / "tools/north-star/sources.json", opened)
        self.assertNotIn(self.root / "tools/north-star/build_readiness.py", opened)
        self.assertEqual(result["g5"]["rows"], 1)
        self.assertEqual(result["g5"]["matched_rows"], 1)
        self.assertFalse(result["g5"]["accepted"])
        self.assertIn(["/usr/bin/zstd", "-dc"], commands)
        self.assertEqual(result["local_host_receipts"]["coverage"]["retained_receipts"], 1)
        self.assertEqual(json.loads(self.receipt.read_text()), result)
        self.assertTrue((self.output / "architecture.html").is_file())
        emitted = b"".join(path.read_bytes() for path in self.output.rglob("*.html"))
        self.assertNotIn(b"RAW-SDK-SENTINEL", emitted)
        self.assertNotIn(b"RAW-CC-SENTINEL", emitted)
        self.assertNotIn(b"UNAUTHORIZED-G5-MEMBER", emitted)
        self.assertIn(b"g5-stars-gap", emitted)
        self.assertFalse(any(Path(module["path"]).stem in {"adoption_roles", "build_readiness"} for module in result["modules"]))

    def test_raw_role_receipts_are_not_read_for_retained_attribution(self):
        for relative in ("coordination/ns2604-coop/notes/parking-20261008/park-raw.json", "coordination/ns2604-coop/notes/capacity-ruling-20261008/relay-receipt.json", "coordination/ns2604-coop/lanes/hcom-lanes.json", "coordination/ns2604-coop/lanes/threads.json"):
            self.write(self.state, relative, {"lanes": [{"name": "beni", "lane": "unapproved"}]})
        with self.read_guard() as (opened, _):
            result = builder.build(self.root, self.state, self.output, self.receipt)
        self.assertEqual(result["role_attribution_sources"][0]["path"], str(self.state / REFRESH))
        self.assertFalse(any("parking-20261008" in str(path) or "capacity-ruling-20261008" in str(path) for path in opened))

    def test_guard_catches_hidden_reads_late_in_real_rendering(self):
        original_load = builder.load

        def injected_load(name):
            module = original_load(name)
            if name == "architecture_view":
                render = module.render
                def late_read(*args, **kwargs):
                    render(*args, **kwargs)
                    (self.state / self.raw_cc).read_bytes()
                module.render = late_read
            return module

        with self.read_guard(), patch.object(builder, "load", side_effect=injected_load), self.assertRaisesRegex(AssertionError, "unauthorized state read: coordination/command-center/windows"):
            builder.build(self.root, self.state, self.output, self.receipt)

    def test_guard_catches_hidden_repository_inventory_reads_late_in_rendering(self):
        forbidden = self.root / "scripts/unreviewed.py"
        forbidden.parent.mkdir(parents=True)
        original_load = builder.load
        def injected_load(name):
            module = original_load(name)
            if name == "architecture_view":
                original_render = module.render
                def late_read(*args, **kwargs):
                    result = original_render(*args, **kwargs)
                    forbidden.write_text("# Synthetic named late-read target\n", encoding="utf-8")
                    forbidden.read_bytes()
                    return result
                module.render = late_read
            return module
        with self.read_guard(), patch.object(builder, "load", side_effect=injected_load), self.assertRaisesRegex(AssertionError, "unauthorized repository data read: scripts/unreviewed.py"):
            builder.build(self.root, self.state, self.output, self.receipt)

    def test_missing_retained_projection_fails_before_publication(self):
        (self.state / REFRESH).unlink()
        with self.read_guard(), self.assertRaisesRegex(ValueError, "retained.*projection.*unavailable"):
            builder.build(self.root, self.state, self.output, self.receipt)
        self.assertFalse(self.receipt.exists())

    def test_malformed_retained_identity_or_roles_fails_clearly(self):
        for changes in [{"native_readiness_manifest_sha256": "invalid"}, {"generated_utc": "2026-10-09"}, {"kind": "raw_sdk_receipt"}, {"adoption_role_attribution": {"instances": {"role_map": {"unsafe@label": "lane"}}}}]:
            with self.subTest(changes=changes):
                self.write(self.state, REFRESH, {**self.refresh, **changes})
                with self.read_guard(), self.assertRaisesRegex(ValueError, "retained.*projection"):
                    builder.build(self.root, self.state, self.output, self.receipt)

    def test_changed_observation_window_preserves_counts_without_old_mapping(self):
        newer = {**self.adoption, "generated_utc": "2026-10-09T04:55:28Z", "codex_by_lane": {"beni": {"conversations": 3, "servers": {"context-mode": {"calls": 7, "conversations": 3}}}}}
        self.immutable(newer)
        original_load, captured = builder.load, []

        def observed_load(name):
            module = original_load(name)
            if name == "architecture_view":
                render = module.render
                def observe(model, inventory, *args, **kwargs):
                    captured.append(model["layers"][0]["winners"][0]["invoke"])
                    return render(model, inventory, *args, **kwargs)
                module.render = observe
            return module

        with self.read_guard(), patch.object(builder, "load", side_effect=observed_load):
            result = builder.build(self.root, self.state, self.output, self.receipt)
        self.assertEqual(result["role_attribution"]["status"], "unattributed")
        self.assertIn("window differs", result["role_attribution"]["reason"])
        invoke = captured[0]
        self.assertEqual(invoke["calls"], 7)
        self.assertEqual(invoke["roles"][0]["role"], "unattributed instances")
        self.assertEqual(invoke["roles"][0]["instance_observations"][0]["role"], "beni")
        self.assertEqual(invoke["roles"][0]["instance_observations"][0]["calls"], 7)
        self.assertIn("window differs", invoke["roles"][0]["attribution_reason"])

    def test_symlink_retained_projection_fails_without_raw_target_read(self):
        retained = self.state / REFRESH
        retained.unlink()
        retained.symlink_to(self.state / RAW_SDK)
        with self.read_guard(), self.assertRaisesRegex(ValueError, "symlink"):
            builder.build(self.root, self.state, self.output, self.receipt)
        self.assertFalse(self.output.exists())

    def test_real_cache_watches_only_retained_identity_and_declared_sources(self):
        with self.read_guard():
            builder.refresh_if_changed(self.root, self.state, self.output, self.receipt)
            # The first completed build adds the exact G5 source to custody.
            builder.refresh_if_changed(self.root, self.state, self.output, self.receipt)
        with self.read_guard() as (opened, _):
            cached = builder.refresh_if_changed(self.root, self.state, self.output, self.receipt)
        # A cache hit checks the retained projection's authorized digest without
        # rebuilding or following any of its declared source links.
        self.assertEqual(opened.count(self.state / REFRESH), 1)
        self.assertEqual(cached["native_readiness_manifest_sha256"], "a" * 64)
        changed = {**self.refresh, "native_readiness_manifest_sha256": "b" * 64}
        self.write(self.state, REFRESH, changed)
        with self.read_guard() as (opened, _):
            rebuilt = builder.refresh_if_changed(self.root, self.state, self.output, self.receipt)
        # Cache digest verification and the actual render each read the same
        # authorized projection; neither follows its recorded source links.
        self.assertEqual(opened.count(self.state / REFRESH), 2)
        self.assertEqual(rebuilt["native_readiness_manifest_sha256"], "b" * 64)
        self.assertEqual(rebuilt["native_readiness_source"]["sha256"], hashlib.sha256((self.state / REFRESH).read_bytes()).hexdigest())



    @contextmanager
    def forbidden_reads(self, forbidden):
        """Count real open boundaries without allowing a forbidden fixture read."""
        forbidden = Path(forbidden).resolve()
        calls = []
        def observe(path):
            if path.resolve() == forbidden:
                calls.append(str(path))
                raise AssertionError("forbidden Architecture source reached a real open")
        with observed_file_reads(observe):
            yield calls

    def published_bytes(self):
        return {path.relative_to(self.output).as_posix(): path.read_bytes()
                for path in self.output.rglob("*") if path.is_file()}, self.receipt.read_bytes()

    def assert_production_refusal_preserves_publication(self, forbidden, *, cache=False):
        before = self.published_bytes()
        with self.forbidden_reads(forbidden) as calls:
            with self.assertRaises(ValueError):
                if cache:
                    builder.refresh_if_changed(self.root, self.state, self.output, self.receipt)
                else:
                    builder.build(self.root, self.state, self.output, self.receipt)
        self.assertEqual(calls, [])
        self.assertEqual(self.published_bytes(), before)

    def assert_count_only_unknown(self, target, *, cache=False):
        with observed_forbidden_targets([target]) as calls:
            result = builder.refresh_if_changed(self.root, self.state, self.output, self.receipt) if cache else builder.build(self.root, self.state, self.output, self.receipt)
        self.assertEqual(calls, {kind: [] for kind in ("open", "metadata", "resolve", "hash")})
        self.assertGreaterEqual(result["unapproved_inventory_counts"]["total"], 1)
        self.assertNotIn(target.name, json.dumps(result))
        for path in self.output.rglob("*"):
            if path.is_file():
                self.assertFalse(target.name.encode() in path.read_bytes(), "ungranted name reached served output")
        return result

    def test_metadata_watcher_detects_descriptor_relative_stat_and_lstat(self):
        target = self.root / "scripts/unapproved-stat-fixture.py"
        target.parent.mkdir(parents=True)
        target.write_text("unread fixture")
        observed = []
        def metadata(path):
            if path == target:
                observed.append(path)
                raise AssertionError("descriptor-relative forbidden metadata caught")
        with observed_file_reads(lambda unused: None, observe_metadata=metadata):
            descriptor = os.open(target.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                with self.assertRaisesRegex(AssertionError, "forbidden metadata"):
                    os.stat(target.name, dir_fd=descriptor, follow_symlinks=False)
                with self.assertRaisesRegex(AssertionError, "forbidden metadata"):
                    os.lstat(target.name, dir_fd=descriptor)
            finally:
                os.close(descriptor)
        self.assertEqual(observed, [target, target])

    def test_real_builder_refuses_fixed_cc_projection_symlink_before_open(self):
        builder.build(self.root, self.state, self.output, self.receipt)
        forbidden = self.write(self.state, "coordination/e2e-truth-20261006/credentials.json", {"gates": []})
        cc = self.state / "coordination/command-center/pages/cc-now.json"
        cc.unlink()
        cc.symlink_to(forbidden)
        self.assert_production_refusal_preserves_publication(forbidden)

    def test_real_builder_excludes_credential_catalog_before_open(self):
        builder.build(self.root, self.state, self.output, self.receipt)
        forbidden = self.write(self.root, "catalogs/landscape/credentials.json", {"layers": []})
        self.assert_production_refusal_preserves_publication(forbidden)

    def test_real_builder_refuses_ordinary_unapproved_catalog_before_open(self):
        builder.build(self.root, self.state, self.output, self.receipt)
        forbidden = self.write(self.root, "catalogs/landscape/ordinary-unreviewed.json", {"layers": []})
        self.assert_production_refusal_preserves_publication(forbidden)

    def test_real_builder_refuses_protected_inventory_agent_before_open(self):
        builder.build(self.root, self.state, self.output, self.receipt)
        forbidden = self.root / "adoption/agents/e2e-truth-20261006/role.md"
        forbidden.parent.mkdir(parents=True)
        forbidden.write_text("Synthetic protected inventory role\n", encoding="utf-8")
        self.assert_production_refusal_preserves_publication(forbidden)

    def test_real_builder_counts_unreviewed_inventory_script_without_target_access(self):
        builder.build(self.root, self.state, self.output, self.receipt)
        forbidden = self.root / "scripts/unreviewed.py"
        forbidden.parent.mkdir(parents=True)
        forbidden.write_text("# Synthetic unreviewed inventory file\n", encoding="utf-8")
        self.assert_count_only_unknown(forbidden)

    def test_real_builder_counts_unreviewed_inventory_metadata_without_target_access(self):
        builder.build(self.root, self.state, self.output, self.receipt)
        forbidden = self.write(self.root, "adoption/agents/unreviewed-manifest.json", {"agents": []})
        self.assert_count_only_unknown(forbidden)

    def test_real_builder_refuses_protected_inventory_alias_target_before_open(self):
        builder.build(self.root, self.state, self.output, self.receipt)
        forbidden = self.write(self.root, "catalogs/e2e-truth-20261006/role.json", {"source": "synthetic protected alias target"})
        alias = self.root / "scripts/approved.py"
        alias.parent.mkdir(parents=True)
        alias.symlink_to(forbidden)
        self.assert_production_refusal_preserves_publication(forbidden)

    def test_real_builder_refuses_protected_lexical_inventory_alias_before_open(self):
        target = self.root / "scripts/approved.py"
        target.parent.mkdir(parents=True)
        target.write_text("# Synthetic independently approved inventory script\n", encoding="utf-8")
        builder.build(self.root, self.state, self.output, self.receipt)
        alias = self.root / "adoption/agents/e2e-truth-20261006/role.md"
        alias.parent.mkdir(parents=True)
        alias.symlink_to(target)
        self.assert_production_refusal_preserves_publication(target)

    def test_real_cache_tracks_count_only_inventory_additions_and_removals(self):
        initial = builder.refresh_if_changed(self.root, self.state, self.output, self.receipt)
        initial_count = initial["unapproved_inventory_counts"]["total"]
        forbidden = self.root / "scripts/unreviewed.py"
        forbidden.parent.mkdir(parents=True)
        forbidden.write_text("# Synthetic cache discovery cannot add permission\n", encoding="utf-8")
        added = self.assert_count_only_unknown(forbidden, cache=True)
        self.assertEqual(added["unapproved_inventory_counts"]["total"], initial_count + 1)
        cached = self.assert_count_only_unknown(forbidden, cache=True)
        self.assertEqual(cached["unapproved_inventory_counts"], added["unapproved_inventory_counts"])
        forbidden.unlink()
        rebuilt = builder.refresh_if_changed(self.root, self.state, self.output, self.receipt)
        self.assertEqual(rebuilt["unapproved_inventory_counts"]["total"], initial_count)
        self.assertNotIn(forbidden.name, json.dumps(rebuilt))

    def test_inventory_boundary_watchers_need_no_proc_descriptor_lookup(self):
        original = os.readlink
        def no_proc(path, *args, **kwargs):
            if str(path).startswith("/proc/self/fd/"):
                raise FileNotFoundError("synthetic platform has no proc descriptor links")
            return original(path, *args, **kwargs)
        with patch.object(os, "readlink", side_effect=no_proc), self.read_guard():
            builder.build(self.root, self.state, self.output, self.receipt)

    def test_real_builder_user_configuration_inventory_is_metadata_only(self):
        paths = []
        for relative in (".codex/agents/reviewer.toml", ".config/systemd/user/example.timer", ".config/systemd/user/example.service"):
            path = self.user / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("Synthetic user configuration; its body must never be opened\n", encoding="utf-8")
            paths.append(path)
        calls = []
        def observe(path):
            if path in paths:
                calls.append(path)
                raise AssertionError("metadata-only user configuration reached a content open")
        with observed_file_reads(observe):
            result = builder.build(self.root, self.state, self.output, self.receipt)
        self.assertEqual(calls, [])
        for path in paths:
            records = [row for row in result["inventory_sources"] if row["path"] == str(path)]
            self.assertEqual(len(records), 1)
            self.assertIsNone(records[0]["sha256"])
            self.assertNotEqual(records[0].get("sha256_kind"), "computed")

    def test_real_builder_counts_unlisted_user_unit_without_metadata_or_content(self):
        builder.build(self.root, self.state, self.output, self.receipt)
        forbidden = self.user / ".config/systemd/user/unreviewed.service"
        forbidden.parent.mkdir(parents=True)
        forbidden.write_text("Synthetic unreviewed unit; no metadata approval\n", encoding="utf-8")
        self.assert_count_only_unknown(forbidden)

    def test_real_builder_refuses_registered_receipt_parent_symlink_before_open(self):
        builder.build(self.root, self.state, self.output, self.receipt)
        relative = "evidence/receipts/redirected/receipt.json"
        forbidden = self.write(self.state, "coordination/e2e-truth-20261006/receipt.json", {"component_id": "context-mode", "result": "pass"})
        parent = self.root / "evidence/receipts/redirected"
        parent.parent.mkdir(parents=True, exist_ok=True)
        parent.symlink_to(forbidden.parent, target_is_directory=True)
        raw = forbidden.read_bytes()
        self.write(self.root, "manifests/evidence.json", {
            "receipts": [{"path": relative, "kind": "native_cli_e2e", "component_ids": ["context-mode"]}],
            "files": [{"path": relative, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}]})
        self.assert_production_refusal_preserves_publication(forbidden)

    def test_real_builder_never_opens_invalid_immutable_candidate_names(self):
        for name in ["adoption-now-credentials.json", "adoption-now-public.json",
                     "adoption-now-0123456789abcdef0.json", "adoption-now-ABCDEF0123456789.json"]:
            candidate = self.write(self.state, "coordination/ns2604-coop/notes/adoption-evidence-20261008/" + name, self.adoption)
            with self.subTest(name=name), self.forbidden_reads(candidate) as calls:
                result = builder.build(self.root, self.state, self.output, self.receipt)
            self.assertEqual(calls, [])
            self.assertEqual(result["invocation_source"]["path"], str(self.snapshot))

    def test_real_builder_refuses_immutable_candidate_symlink_before_open(self):
        builder.build(self.root, self.state, self.output, self.receipt)
        forbidden = self.write(self.state, "coordination/e2e-truth-20261006/snapshot.json", self.adoption)
        candidate = self.snapshot.with_name("adoption-now-aaaaaaaaaaaaaaaa.json")
        candidate.symlink_to(forbidden)
        self.assert_production_refusal_preserves_publication(forbidden)

    def test_real_cache_refuses_unapproved_catalog_before_open(self):
        builder.refresh_if_changed(self.root, self.state, self.output, self.receipt)
        forbidden = self.write(self.root, "catalogs/landscape/unregistered-cache-source.json", {})
        self.assert_production_refusal_preserves_publication(forbidden, cache=True)


if __name__ == "__main__":
    unittest.main()
