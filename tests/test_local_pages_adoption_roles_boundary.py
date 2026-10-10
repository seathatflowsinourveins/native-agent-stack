"""Adoption role reads stay bounded even when their fixed paths are aliased."""

from contextlib import contextmanager, ExitStack
import builtins
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "adoption_roles_read_boundary", ROOT / "tools/local-pages/adoption_roles.py"
)
roles = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(roles)
from tests import test_local_pages as composer_fixture


@contextmanager
def observed_file_reads(observe, before_open=None):
    """Observe successful read opens using portable descriptor ancestry."""
    originals = {"builtins": builtins.open, "io": io.open,
                 "os": os.open, "close": os.close}
    descriptors = {}

    def wrapper(kind):
        def invoke(value, *args, **options):
            path = None
            if not isinstance(value, int):
                path = Path(os.fsdecode(value))
                if not path.is_absolute() and options.get("dir_fd") is not None:
                    parent = descriptors.get(options["dir_fd"])
                    if parent is None:
                        raise AssertionError("untracked directory descriptor")
                    path = parent / path
                path = path.absolute()
            flags = args[0] if kind == "os" and args else options.get("flags", 0)
            directory = kind == "os" and flags & os.O_DIRECTORY
            mode = args[0] if kind != "os" and args else options.get("mode", "r")
            reading = (flags & os.O_ACCMODE) != os.O_WRONLY if kind == "os" else (
                isinstance(mode, str) and ("r" in mode or "+" in mode)
            )
            if path is not None and reading and not directory and before_open:
                before_open(kind, path)
            result = originals[kind](value, *args, **options)
            if kind == "os":
                descriptors[result] = path
            if path is not None and reading and not directory:
                observe(path)
            return result
        return invoke

    def close(descriptor):
        try:
            return originals["close"](descriptor)
        finally:
            descriptors.pop(descriptor, None)

    with ExitStack() as stack:
        for kind, owner in (("builtins", builtins), ("io", io), ("os", os)):
            stack.enter_context(patch.object(owner, "open", wrapper(kind)))
        stack.enter_context(patch.object(os, "close", close))
        yield


def published_document():
    return {
        "schema": "adoption-now/1", "generated_utc": "2026-10-09T01:00:00Z",
        "window_hours": 24, "claude_by_role": {}, "layers": {},
        "claude_total_sessions": 0, "codex_total_conversations": 4,
        "codex_by_lane": {"mahe": {"conversations": 4, "servers": {
            "context-mode": {"calls": 17, "conversations": 4}}}},
        "orchestration": {"claude_by_role": {}, "codex_by_lane": {
            "mahe": {"spawn_agent": 0, "send_message": 2}}, "unmeasured": []},
    }


def parking_receipt():
    return {"before": {"at": "2026-10-08T12:00:00Z"}, "plan": [
        {"lane": "aliased-lane", "name": "tag-mahe"}]}


def lane_registry():
    return {"aliased-lane": {"name": "tag-mahe",
                             "launched": "2026-10-08T12:00:00Z"}}


class AdoptionRolesReadBoundaryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="adoption-read-boundary-")
        self.addCleanup(temporary.cleanup)
        self.temp = Path(temporary.name).resolve()
        self.state = self.temp / "state"
        self.base = self.state / "coordination/ns2604-coop"

    def write(self, path, document):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(document), encoding="utf-8")
        return path

    def assert_unattributed(self, result, source):
        self.assertEqual(result["instances"]["role_map"], {"mahe": None})
        self.assertEqual(result["codex_roles"], {})
        record = result["instances"]["records"]["mahe"]
        self.assertEqual(record["status"], "UNATTRIBUTED")
        self.assertEqual(record["candidate_roles"], [])
        self.assertEqual(record["counts"], source["codex_by_lane"]["mahe"])
        self.assertEqual(record["orchestration"], {"spawn_agent": 0, "send_message": 2})
        shown = result["document"]["codex_by_lane"]
        self.assertEqual(shown, {"unattributed instances": {
            "conversations": 4, "calls": 17, "instances": 1,
            "servers": {"context-mode": {"calls": 17, "conversations": 4}},
            "aggregation_scope": "sum of published instance counts; distinct cross-instance conversations unverified",
        }})
        self.assertEqual(result["orchestration"]["codex_unattributed"], {
            "mahe": {"spawn_agent": 0, "send_message": 2}})

    def assert_unreported_error(self, result, path):
        selected = [row for row in result["source_errors"] if row["path"] == str(path)]
        self.assertTrue(selected, "a refused registry input needs an honest error")
        self.assertTrue(all(row["status"].startswith("UNREPORTED:") for row in selected))
        self.assertFalse(any(row["path"] == str(path) for row in result["sources"]))

    def test_parking_parent_alias_never_opens_protected_receipt(self):
        self.write(self.base / "lanes/hcom-lanes.json", {})
        protected = self.write(
            self.state / "coordination/e2e-truth-fixture/park-fixture.json",
            parking_receipt(),
        )
        parking = self.base / "notes/parking-20261008"
        parking.parent.mkdir(parents=True)
        parking.symlink_to(protected.parent, target_is_directory=True)
        source = published_document()
        before = copy.deepcopy(source)
        opened = []
        with observed_file_reads(lambda path: opened.append(path.resolve())):
            result = roles.project(source, self.state)
        self.assertEqual([path for path in opened if path == protected], [])
        self.assert_unattributed(result, source)

        self.assert_unreported_error(result, parking)
        self.assertEqual(source, before)

    def test_registry_parent_alias_never_opens_protected_registry(self):
        target = self.write(self.state / "coordination/e2e-truth-fixture/hcom-lanes.json",
                            lane_registry())
        lanes = self.base / "lanes"
        lanes.parent.mkdir(parents=True)
        lanes.symlink_to(target.parent, target_is_directory=True)
        source = published_document()
        before = copy.deepcopy(source)
        opened = []
        with observed_file_reads(lambda path: opened.append(path.resolve())):
            result = roles.project(source, self.state)
        self.assertNotIn(target, opened)
        self.assert_unattributed(result, source)
        self.assert_unreported_error(result, lanes / "hcom-lanes.json")
        self.assertEqual(source, before)

    def test_registry_parent_cannot_escape_state_through_symlink(self):
        target = self.write(self.temp / "outside-state/hcom-lanes.json", lane_registry())
        lanes = self.base / "lanes"
        lanes.parent.mkdir(parents=True)
        lanes.symlink_to(target.parent, target_is_directory=True)
        source = published_document()
        opened = []
        with observed_file_reads(lambda path: opened.append(path.resolve())):
            result = roles.project(source, self.state)
        self.assertNotIn(target, opened)
        self.assert_unattributed(result, source)
        self.assert_unreported_error(result, lanes / "hcom-lanes.json")

    def test_leaf_replaced_at_open_never_opens_protected_target(self):
        registry = self.write(self.base / "lanes/hcom-lanes.json", {})
        target = self.write(self.state / "coordination/e2e-truth-fixture/registry.json",
                            lane_registry())
        swapped, opened = [], []

        def replace_leaf(kind, path):
            if path == registry and not swapped:
                registry.unlink()
                registry.symlink_to(target)
                swapped.append((kind, path))

        source = published_document()
        with observed_file_reads(lambda path: opened.append(path.resolve()), replace_leaf):
            result = roles.project(source, self.state)
        self.assertEqual(len(swapped), 1, "the race must occur at the real open seam")
        self.assertEqual(swapped[0][0], "os")
        self.assertNotIn(target, opened)
        self.assert_unattributed(result, source)
        self.assert_unreported_error(result, registry)

    def test_protected_parking_names_are_refused_before_content_open(self):
        self.write(self.base / "lanes/hcom-lanes.json", {})
        parking = self.base / "notes/parking-20261008"
        blocked = [self.write(parking / name, parking_receipt()) for name in (
            "park-credentials.json", "park-client-secret.json", "park-.env.json",
            "park-e2e-truth-fixture.json",
        )]
        source = published_document()
        opened = []
        with observed_file_reads(lambda path: opened.append(path.resolve())):
            result = roles.project(source, self.state)
        self.assertEqual([path for path in opened if path in blocked], [])
        self.assert_unattributed(result, source)
        for path in blocked:
            self.assert_unreported_error(result, path)

    def test_capacity_parent_alias_never_opens_protected_receipts(self):
        self.write(self.base / "lanes/hcom-lanes.json", {})
        target = self.write(self.state / "coordination/e2e-truth-fixture/relay-receipt.json",
                            parking_receipt())
        capacity = self.base / "notes/capacity-ruling-20261008"
        capacity.parent.mkdir(parents=True)
        capacity.symlink_to(target.parent, target_is_directory=True)
        source = published_document()
        opened = []
        with observed_file_reads(lambda path: opened.append(path.resolve())):
            result = roles.project(source, self.state)
        self.assertNotIn(target, opened)
        self.assert_unattributed(result, source)
        self.assert_unreported_error(result, capacity / "relay-receipt.json")

    def test_missing_registry_keeps_sources_empty_and_counts_unattributed(self):
        source = published_document()
        before = copy.deepcopy(source)
        result = roles.project(source, self.state)
        self.assert_unattributed(result, source)
        self.assertEqual(result["sources"], [])
        self.assertEqual(result["source_errors"], [])
        self.assertEqual(source, before)

    def test_malformed_and_nonobject_registry_keep_only_actual_byte_receipts(self):
        path = self.base / "lanes/hcom-lanes.json"
        path.parent.mkdir(parents=True)
        for raw in (b'{"unfinished":', b'[]', b'null', b'\xff'):
            with self.subTest(raw=raw):
                path.write_bytes(raw)
                source = published_document()
                before = copy.deepcopy(source)
                opened = []
                with observed_file_reads(lambda value: opened.append(value.resolve())):
                    result = roles.project(source, self.state)
                self.assertEqual(opened.count(path), 1)
                self.assert_unattributed(result, source)
                self.assertEqual(len(result["sources"]), 1)
                receipt = result["sources"][0]
                self.assertEqual(receipt["path"], str(path))
                self.assertEqual(receipt["sha256"], hashlib.sha256(raw).hexdigest())
                self.assertEqual(result["source_errors"], [{
                    "path": str(path), "status": "UNREPORTED: malformed registry metadata"}])
                self.assertEqual(path.read_bytes(), raw)
                self.assertEqual(source, before)

    def test_only_fixed_registry_and_receipt_families_supply_bindings(self):
        approved = self.write(self.base / "lanes/hcom-lanes.json", {})
        unselected = [self.write(self.base / relative, lane_registry()) for relative in (
            "lanes/arbitrary.json", "notes/parking-20261008/other-receipt.json",
            "notes/parking-20261008/park-fixture.txt",
            "notes/capacity-ruling-20261008/relay-receipt-unreviewed.json",
        )]
        source = published_document()
        opened = []
        with observed_file_reads(lambda value: opened.append(value.resolve())):
            result = roles.project(source, self.state)
        self.assertEqual([path for path in opened if path in unselected], [])
        self.assertEqual([row["path"] for row in result["sources"]], [str(approved)])
        self.assert_unattributed(result, source)

    def test_read_failure_reports_exception_category_without_private_message(self):
        registry = self.write(self.base / "lanes/hcom-lanes.json", {})
        original_open = os.open
        private_message = "SYNTHETIC-PRIVATE-ERROR-BODY"
        failures = []

        def denied_leaf(path, flags, *args, **options):
            if Path(os.fsdecode(path)).name == registry.name and not flags & os.O_DIRECTORY:
                failures.append(path)
                raise PermissionError(private_message)
            return original_open(path, flags, *args, **options)

        source = published_document()
        with patch.object(os, "open", side_effect=denied_leaf):
            result = roles.project(source, self.state)
        self.assertEqual(len(failures), 1)
        self.assert_unattributed(result, source)
        self.assertEqual(result["sources"], [])
        self.assertEqual(result["source_errors"], [{
            "path": str(registry), "status": "UNREPORTED: registry input refused (PermissionError)"}])
        self.assertNotIn(private_message, json.dumps(result))


class AdoptionRolesComposerBoundaryTests(unittest.TestCase):
    """The composer must use the guarded public role projection unchanged."""

    write_json = staticmethod(composer_fixture.LocalPagesTests.write_json)
    refresh = composer_fixture.LocalPagesTests.refresh

    def setUp(self):
        composer_fixture.LocalPagesTests.setUp(self)
        self.coop = self.state / "coordination/ns2604-coop"
        self.registry = self.coop / "lanes/hcom-lanes.json"
        self.adoption = published_document()
        self.write_json(self.adoption_path, self.adoption)
        self.write_json(self.registry, {})
        # Keep the actual native module and policy adapter, but replace its
        # build with a minimal manifest containing only synthetic identities.
        builder = composer_fixture.BUILDER
        native, identity = builder.load_native(self.root)
        fixture_manifest = {
            "source_index": {"root": "repo", "path": "tools/north-star/sources.json",
                             "sha256": hashlib.sha256(self.source_index.read_bytes()).hexdigest()},
            "gates": [], "layers": [], "receipts": {},
            "summary": {"recorded_claims": 0, "unverified_claims": 0,
                        "unverified_sources": 0},
        }
        native.build = lambda *args, **options: copy.deepcopy(fixture_manifest)
        native.render_fragment = lambda manifest: "<section><p>Synthetic readiness fixture</p></section>"
        native_patch = patch.object(builder, "load_native", return_value=(native, identity))
        native_patch.start()
        self.addCleanup(native_patch.stop)

    @contextmanager
    def protected_reads(self, target):
        opened = []
        with observed_file_reads(lambda path: opened.append(path.resolve())), patch.object(
            subprocess, "Popen", side_effect=AssertionError("synthetic composer invokes no native jobs")
        ):
            yield opened
        self.assertEqual([path for path in opened if path == target], [])

    def assert_projection_unattributed(self, receipt):
        projection = receipt["adoption_role_attribution"]
        self.assertEqual(projection["instances"]["role_map"], {"mahe": None})
        record = projection["instances"]["records"]["mahe"]
        self.assertEqual(record["counts"], self.adoption["codex_by_lane"]["mahe"])
        self.assertEqual(record["status"], "UNATTRIBUTED")
        self.assertEqual(record["candidate_roles"], [])
        self.assertTrue(any(row["status"].startswith("UNREPORTED:")
                            for row in projection["source_errors"]))
        fleet = (self.output / "fleet.html").read_text()
        self.assertIn("unattributed instances", fleet)
        self.assertNotIn("aliased-lane", fleet)

    def test_refresh_uses_guarded_projection_for_protected_parking_alias(self):
        source_before = self.adoption_path.read_bytes()
        self.refresh()
        target = self.state / "coordination/e2e-truth-fixture/park-fixture.json"
        self.write_json(target, parking_receipt())
        parking = self.coop / "notes/parking-20261008"
        parking.parent.mkdir(parents=True)
        parking.symlink_to(target.parent, target_is_directory=True)
        with self.protected_reads(target):
            receipt = self.refresh()
        self.assert_projection_unattributed(receipt)
        self.assertFalse(any(row["path"].startswith(str(parking))
                             for row in receipt["adoption_role_attribution"]["sources"]))
        self.assertEqual(self.adoption_path.read_bytes(), source_before)
        self.assertEqual(receipt["adoption"]["sha256"], hashlib.sha256(source_before).hexdigest())
        self.assertEqual(set(receipt["outputs"]), {
            "index.html", "readiness.html", "gaps.html", "roadmap.html", "fleet.html",
            "sources.html", "assets/site.css", "assets/site.js",
        })

    def test_refresh_uses_guarded_projection_for_protected_registry_alias(self):
        source_before = self.adoption_path.read_bytes()
        self.registry.unlink()
        self.registry.parent.rmdir()
        target = self.state / "coordination/e2e-truth-fixture/hcom-lanes.json"
        self.write_json(target, lane_registry())
        self.registry.parent.symlink_to(target.parent, target_is_directory=True)
        with self.protected_reads(target):
            receipt = self.refresh()
        self.assert_projection_unattributed(receipt)
        self.assertEqual(receipt["adoption_role_attribution"]["sources"], [])
        self.assertEqual(self.adoption_path.read_bytes(), source_before)

    def test_refresh_preserves_raw_attribution_and_aggregates_before_display(self):
        registry = {
            "fixture-role": {"name": "tag-mahe", "launched": "2026-10-08T12:00:00Z",
                             "previous_name": "tag-luva", "previous_launched": "2026-10-08T03:00:00Z"},
        }
        self.write_json(self.registry, registry)
        self.adoption["codex_by_lane"]["luva"] = {
            "conversations": 2, "servers": {"context-mode": {"calls": 7, "conversations": 2}}}
        self.adoption["codex_total_conversations"] = 6
        self.adoption["orchestration"]["codex_by_lane"]["luva"] = {"spawn_agent": 4}
        self.write_json(self.adoption_path, self.adoption)
        raw_adoption = self.adoption_path.read_bytes()
        raw_registry = self.registry.read_bytes()
        projection_calls = []
        builder = composer_fixture.BUILDER
        original_load = builder.load_local

        def load(name):
            module = original_load(name)
            if name == "adoption_roles":
                project = module.project

                def observe(document, state_root):
                    result = project(document, state_root)
                    projection_calls.append(copy.deepcopy(result))
                    return result

                module.project = observe
            return module

        with patch.object(builder, "load_local", side_effect=load), patch.object(
            subprocess, "Popen", side_effect=AssertionError("synthetic composer invokes no native jobs")
        ):
            receipt = self.refresh()
        self.assertEqual(len(projection_calls), 1)
        projection = projection_calls[0]
        self.assertEqual(projection["instances"]["role_map"], {
            "luva": "fixture-role", "mahe": "fixture-role"})
        role = projection["codex_roles"]["fixture-role"]
        self.assertEqual(role["instance_labels"], ["mahe", "luva"])
        self.assertEqual(role["conversations"], 6)
        self.assertEqual(role["calls"], 24)
        self.assertEqual(role["servers"]["context-mode"], {"calls": 24, "conversations": 6})
        self.assertEqual(projection["orchestration"]["codex_by_role"]["fixture-role"], {
            "spawn_agent": 4, "send_message": 2})
        self.assertEqual(receipt["adoption_role_attribution"]["instances"], projection["instances"])
        self.assertEqual(self.adoption_path.read_bytes(), raw_adoption)
        self.assertEqual(self.registry.read_bytes(), raw_registry)
        self.assertEqual(projection["sources"][0]["sha256"], hashlib.sha256(raw_registry).hexdigest())
        fleet = (self.output / "fleet.html").read_text()
        self.assertIn("fixture-role", fleet)
        self.assertIn("mahe", fleet)
        self.assertIn("luva", fleet)


if __name__ == "__main__":
    unittest.main()
