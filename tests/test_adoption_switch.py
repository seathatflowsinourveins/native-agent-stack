"""Tests for adoption/tools/ecosystem-switch.

Every test uses a synthetic temporary ECO_INSTALL_ROOT and, where a systemd command
is exercised, an instrumented stub pointed to by ECOSYSTEM_SWITCH_SYSTEMCTL /
ECOSYSTEM_SWITCH_SYSTEMD_RUN. No real host tool root, systemd unit, or receipt is
read or changed. CLI-facing behaviour (status/adopt/plan/apply/confirm/rollback/
verify/recover/prune/write-installed-versions) is exercised as a subprocess, the
way a real caller invokes it; the lower-level operation functions (text-replace,
file-write, native-cli, data-backup/restore) are exercised directly through
importlib, since none of this track's shipped adoption/pins-linux-x86_64.json
entries has a populated surfaces[] to drive them through the CLI end to end yet
(see docs/tasks -- an explicitly noted scope limitation, not a hidden gap).
"""

from __future__ import annotations

import contextlib
import importlib.machinery
import importlib.util
import json
import os
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
import unittest.mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SWITCH_BIN = ROOT / "adoption" / "tools" / "ecosystem-switch"

# ecosystem-switch's unit-restart operation and its memory gate are procfs-based
# (/proc/<MainPID>/exe, /proc/meminfo: adoption/tools/ecosystem-switch's available_memory_kib/
# op_unit_restart), and UnitRestartTests additionally spawns real per-root daemon processes and
# probes their own /proc/<pid>/exe -- there is no macOS equivalent to fake. validate-macos (the
# required check that runs this full suite on macos-15) has no /proc at all, so
# memory_gate_issue() would refuse every restart unconditionally regardless of any override
# (blocking finding). Same idiom as tests/test_adoption_bootstrap.py's LINUX_X86_64_ONLY: skip
# the whole platform-specific class rather than special-casing each assertion.
REQUIRES_PROCFS = unittest.skipUnless(sys.platform.startswith("linux"), "requires real /proc (Linux only)")

_loader = importlib.machinery.SourceFileLoader("ecosystem_switch", str(SWITCH_BIN))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
switch = importlib.util.module_from_spec(_spec)
_loader.exec_module(switch)


def run(env, *args, timeout=30, input_text=None):
    return subprocess.run([sys.executable, str(SWITCH_BIN), *args], capture_output=True, text=True,
                           timeout=timeout, env=env, input=input_text)


def iso(offset_seconds: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + offset_seconds))


class SwitchFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        # .resolve() here, once, so every path derived from self.root below (root_v1/root_v2,
        # current/<id> targets, etc.) is already canonical: on macOS tempfile's /var/folders is
        # itself a symlink to /private/var/folders, so an unresolved self.root and a later
        # os.path.realpath()/.resolve() of a path built from it would otherwise disagree (macOS
        # validate-macos blocking finding; same pattern as tests/test_record_verdicts.py's
        # "macOS: /var/folders resolves to /private/var/folders" fixtures).
        self.root = Path(self.tmp.name).resolve() / "eco"
        self.root.mkdir()
        (self.root / "bin").mkdir()
        (self.root / "tools").mkdir()
        self.env = {**os.environ, "ECO_INSTALL_ROOT": str(self.root)}

    # ---- fixture helpers -------------------------------------------------

    def make_tool_root(self, name: str, output: str) -> Path:
        bin_dir = self.root / "tools" / name / "bin"
        bin_dir.mkdir(parents=True)
        script = bin_dir / name.split("-", 1)[0]
        script.write_text(f"#!/bin/sh\necho {output}\n")
        script.chmod(0o755)
        return bin_dir.parent

    def link_entrypoint(self, entry_name: str, target: Path) -> None:
        (self.root / "bin" / entry_name).symlink_to(target)

    def write_components(self, components: dict) -> None:
        spec = {"schema_version": 1, "components": components}
        (self.root / "switch").mkdir(exist_ok=True)
        (self.root / "switch" / "components.json").write_text(json.dumps(spec))

    def write_window(self, name="default", *, allowed=("foo",), open_now=True):
        (self.root / "switch" / "windows").mkdir(parents=True, exist_ok=True)
        start = iso(-3600 if open_now else 3600)
        end = iso(3600 if open_now else 7200)
        window = {"name": name, "start_utc": start, "end_utc": end, "allowed_components": list(allowed)}
        (self.root / "switch" / "windows" / f"{name}.json").write_text(json.dumps(window))

    def write_receipt(self, rid: str, component_id: str, version: str, *, status="passed",
                      install_root: str | None = None,
                      tiers=(("T0", "passed", None), ("T1", "unavailable", "no GPU"),
                             ("T2", "passed", None), ("T4", "passed", None))):
        (self.root / "switch" / "receipts").mkdir(parents=True, exist_ok=True)
        tier_docs = []
        for tier, result, reason in tiers:
            doc = {"tier": tier, "commands": [], "result": result}
            if reason:
                doc["unavailable_reason"] = reason
            tier_docs.append(doc)
        receipt = {
            "schema_version": 1, "id": f"{component_id}-{version}-{rid}", "kind": "native_rollout",
            "status": status,
            "identity": {"component_id": component_id, "version": version, "host_id": "test-host-20260925"},
            "upstream": {"repo": "https://example.invalid/x", "tag": f"v{version}",
                        "artifact_url": "https://example.invalid/x.tar.gz", "sha256": "0" * 64},
            # install_root overrides the default "clean" derivation below: identity.version stays
            # the plain upstream version, but a receipt for a staged (-rDATE) root must bind
            # install.root to that exact staged path (major finding: see cmd_apply).
            "install": {"class": "tarball", "root": install_root or f"${{STACK_HOME}}/tools/{component_id}-{version}",
                       "marker_sha256": "0" * 64, "argv": ["true"], "private_env_names": []},
            "tiers": tier_docs,
            "independent": {"rerun_label": "test", "agreement": "same_result", "loki": []},
            "decision": "retain", "evidence_class_claimed": "local_integration",
            "limitations": ["Synthetic fixture receipt; not a real rollout."],
            "retained_native_failures": [],
        }
        (self.root / "switch" / "receipts" / f"{rid}.json").write_text(json.dumps(receipt))

    def relink(self, *components):
        result = run(self.env, "adopt", "--relink", *([a for c in components for a in ("--component", c)]))
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def plan_sha(self, component: str, to_root: Path, receipt: str) -> str:
        result = run(self.env, "plan", component, "--to-root", str(to_root), "--receipt", receipt)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)["plan_sha256"]

    def apply(self, component, to_root, receipt, window="default", extra=()):
        digest = self.plan_sha(component, to_root, receipt)
        return run(self.env, "apply", component, "--to-root", str(to_root), "--receipt", receipt,
                   "--window", window, "--plan-sha256", digest, *extra)


class ScriptShapeTests(unittest.TestCase):
    def test_executable_and_shebang(self):
        self.assertTrue(SWITCH_BIN.stat().st_mode & stat.S_IXUSR)
        self.assertEqual(SWITCH_BIN.read_text().splitlines()[0], "#!/usr/bin/env python3")

    def test_compiles_clean(self):
        result = subprocess.run([sys.executable, "-m", "py_compile", str(SWITCH_BIN)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_no_bare_argv_exits_usage(self):
        result = subprocess.run([sys.executable, str(SWITCH_BIN)], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)


class StatusOnEmptyRootTests(SwitchFixture):
    def test_status_json_on_untouched_root(self):
        result = run(self.env, "status", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"components": {}, "txns": {}})


class RelinkTests(SwitchFixture):
    def setUp(self):
        super().setUp()
        self.tool_root = self.make_tool_root("foo-1.0.0", "v1")
        self.link_entrypoint("foo", self.tool_root / "bin" / "foo")
        self.write_components({"foo": {
            "version": "1.0.0", "kind": "tarball", "root_name": "foo-1.0.0", "current_link": "current/foo",
            "entrypoints": [{"bin": "bin/foo", "in_root": "bin/foo"}], "surfaces": [], "state_dirs": [],
            "window": "default", "rollback_class": "safe",
        }})

    def test_relink_preserves_the_real_target_and_indirects_through_current(self):
        before_real = os.path.realpath(self.root / "bin" / "foo")
        self.relink("foo")
        after_real = os.path.realpath(self.root / "bin" / "foo")
        self.assertEqual(before_real, after_real, "adopt --relink must never change a real, resolved path")
        self.assertEqual(os.readlink(self.root / "bin" / "foo"), str(self.root / "current" / "foo" / "bin" / "foo"))
        self.assertEqual(os.readlink(self.root / "current" / "foo"), str(self.tool_root.resolve()))
        result = subprocess.run([str(self.root / "bin" / "foo")], capture_output=True, text=True)
        self.assertEqual(result.stdout.strip(), "v1")

    def test_relink_is_idempotent(self):
        self.relink("foo")
        first = os.readlink(self.root / "bin" / "foo")
        self.relink("foo")
        self.assertEqual(os.readlink(self.root / "bin" / "foo"), first)

    def test_recover_rolls_back_a_second_relink_that_fails_after_current_link_already_exists(self):
        # Minor finding: rollback_txn's (and cmd_rollback's own duplicate) superseded refusal
        # used to fire whenever exactly one component was touched, even when THIS txn never
        # itself became the component's current-link setter. A second relink -- current/foo
        # already exists from the first one, so relink links it only when absent (1540-1543) --
        # that fails partway (here: a surface added after the first relink, the finding's own
        # example) only ever ledgers entrypoint/surface ops, never a current/-prefixed "link". Its
        # updated_txn therefore still names the FIRST relink's txn, which the old unconditional
        # check misread as "a later txn already moved it on" and refused every recover forever.
        self.relink("foo")
        first_current_target = os.readlink(self.root / "current" / "foo")
        frozen = self.root / "frozen" / "thing.txt"
        frozen.parent.mkdir()
        frozen.write_text("do not touch")
        self.write_components({"foo": {
            "version": "1.0.0", "kind": "tarball", "root_name": "foo-1.0.0", "current_link": "current/foo",
            "entrypoints": [{"bin": "bin/foo", "in_root": "bin/foo"}],
            "surfaces": [{"kind": "text-replace", "path": str(frozen), "expected_count": 1}],
            "state_dirs": [], "window": "default", "rollback_class": "safe",
        }})
        second = run(self.env, "adopt", "--relink")
        self.assertNotEqual(second.returncode, 0)
        self.assertIn("frozen", second.stderr)

        recover_result = run(self.env, "recover")
        self.assertEqual(recover_result.returncode, 0, recover_result.stderr)
        self.assertEqual(len(json.loads(recover_result.stdout)["recovered_txns"]), 1)
        self.assertEqual(json.loads(recover_result.stdout)["rollback_problems"], [])
        self.assertEqual(os.readlink(self.root / "current" / "foo"), first_current_target,
                         "current/foo must still name the original relink's real root, untouched")

    def test_relink_skips_a_component_with_no_switch_managed_root(self):
        self.write_components({"native-thing": {
            "version": "1.0.0", "kind": "native", "root_name": None, "current_link": None,
            "entrypoints": [], "surfaces": [], "state_dirs": [], "window": "default",
            "rollback_class": "not_applicable",
        }})
        result = self.relink("native-thing")
        self.assertIn("skipped", json.loads(result.stdout)["results"]["native-thing"])

    def test_relink_refuses_before_changing_anything_when_root_name_does_not_exist(self):
        # Blocking finding: a pins root_name that does not match the live root (e.g. this
        # rollout's own node-24.21.0 vs the real tools/node-v24.21.0) must never leave bin/foo
        # dangling or unrecorded; it must refuse before creating current/<id> at all.
        self.write_components({"foo": {
            "version": "1.0.0", "kind": "tarball", "root_name": "foo-does-not-exist", "current_link": "current/foo",
            "entrypoints": [{"bin": "bin/foo", "in_root": "bin/foo"}], "surfaces": [], "state_dirs": [],
            "window": "default", "rollback_class": "safe",
        }})
        before_target = os.readlink(self.root / "bin" / "foo")
        result = run(self.env, "adopt", "--relink")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("root_name", result.stderr)
        self.assertFalse((self.root / "current" / "foo").exists(), "no dangling current/foo must be created")
        self.assertEqual(os.readlink(self.root / "bin" / "foo"), before_target, "bin/foo must be untouched")
        self.assertEqual(switch.Ledger(self.root).all(), [], "a refused relink must leave no ledger entry")

    def test_relink_refuses_a_mismatching_entrypoint_before_changing_it(self):
        # A component spec whose entrypoints[].in_root does not match where bin/foo currently
        # resolves (e.g. qmd/mcporter/context-mode/agent-browser's real node_modules/ targets vs
        # a bare "bin/<x>" guess) must refuse before repointing bin/foo, not after.
        self.write_components({"foo": {
            "version": "1.0.0", "kind": "tarball", "root_name": "foo-1.0.0", "current_link": "current/foo",
            "entrypoints": [{"bin": "bin/foo", "in_root": "somewhere/else/foo"}], "surfaces": [], "state_dirs": [],
            "window": "default", "rollback_class": "safe",
        }})
        before_real = os.path.realpath(self.root / "bin" / "foo")
        before_target = os.readlink(self.root / "bin" / "foo")
        result = run(self.env, "adopt", "--relink")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refused before changing anything", result.stderr)
        self.assertEqual(os.readlink(self.root / "bin" / "foo"), before_target, "bin/foo must be untouched")
        self.assertEqual(os.path.realpath(self.root / "bin" / "foo"), before_real)
        self.assertFalse((self.root / "current" / "foo").exists(),
                         "current/foo must not be created either when an entrypoint would mismatch")

    def test_relink_refuses_when_current_link_already_points_at_a_different_root(self):
        # Minor finding: relink used to keep any existing current/<id> untouched and
        # unconditionally repoint every entrypoint through it. Each entrypoint's own pre-check
        # (above) only compares bin/foo's *current direct* target against real_root -- it says
        # nothing about what current/foo itself already names. If current/foo already existed
        # (e.g. apply ran once before relink ever did) and pointed at a *different* root, relink
        # would still pass that pre-check (bin/foo is still a direct, unredirected symlink into
        # real_root) and then silently move bin/foo to the *other* root by repointing it through
        # current/foo -- the exact real-path change this tool promises never to make.
        other_root = self.make_tool_root("foo-9.9.9", "v9")
        (self.root / "current").mkdir()
        (self.root / "current" / "foo").symlink_to(other_root.resolve())
        before_target = os.readlink(self.root / "bin" / "foo")
        result = run(self.env, "adopt", "--relink")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("already resolves to", result.stderr)
        self.assertEqual(os.readlink(self.root / "bin" / "foo"), before_target, "bin/foo must be untouched")
        self.assertEqual(switch.Ledger(self.root).all(), [], "a refused relink must leave no ledger entry")

    def test_relink_refuses_a_regular_file_entrypoint_instead_of_silently_symlinking_over_it(self):
        # A regular file at a bin/* entrypoint (not a symlink) must never be silently replaced by
        # a symlink: that conversion has no recorded inverse.
        (self.root / "bin" / "foo").unlink()
        (self.root / "bin" / "foo").write_text("#!/bin/sh\necho not-a-symlink\n")
        (self.root / "bin" / "foo").chmod(0o755)
        result = run(self.env, "adopt", "--relink")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("regular file", result.stderr)
        self.assertFalse((self.root / "bin" / "foo").is_symlink())
        self.assertEqual((self.root / "bin" / "foo").read_text(), "#!/bin/sh\necho not-a-symlink\n")

    def test_ledger_is_hash_chained_and_0600(self):
        self.relink("foo")
        ledger_path = self.root / "switch" / "ledger.jsonl"
        self.assertEqual(stat.S_IMODE(ledger_path.stat().st_mode), 0o600)
        problems = switch.Ledger(self.root).verify_chain()
        self.assertEqual(problems, [])

    def test_tampered_ledger_entry_is_detected(self):
        self.relink("foo")
        ledger_path = self.root / "switch" / "ledger.jsonl"
        lines = ledger_path.read_text().splitlines()
        entry = json.loads(lines[0])
        entry["to"] = "tampered"
        lines[0] = json.dumps(entry)
        ledger_path.write_text("\n".join(lines) + "\n")
        problems = switch.Ledger(self.root).verify_chain()
        self.assertTrue(problems)
        result = run(self.env, "verify", "--json")
        self.assertEqual(result.returncode, 1)
        self.assertFalse(json.loads(result.stdout)["_ledger"]["ok"])

    def test_relink_refuses_while_an_earlier_txn_for_the_component_is_in_progress(self):
        # Major finding (round 4): nothing blocked a second relink attempt while an earlier one
        # for the same component was still in_progress. Relink only (re-)links current/<id> when
        # it is absent, so a second, "fixed" attempt never re-ledgers its own current/<id> link --
        # recompute_state's updated_txn still names the FIRST (stale) txn -- and a later `recover`
        # reversing that stale in_progress txn could then unlink current/<id> or revert
        # entrypoints out from under the second attempt's own (already-terminal) work, while every
        # command involved kept exiting 0. Refusing outright while the earlier txn is still
        # in_progress forces `recover` to run first, fully reverting it before a clean retry.
        frozen = self.root / "frozen" / "thing.txt"
        frozen.parent.mkdir()
        frozen.write_text("do not touch")
        self.write_components({"foo": {
            "version": "1.0.0", "kind": "tarball", "root_name": "foo-1.0.0", "current_link": "current/foo",
            "entrypoints": [{"bin": "bin/foo", "in_root": "bin/foo"}],
            "surfaces": [{"kind": "text-replace", "path": str(frozen), "expected_count": 1}],
            "state_dirs": [], "window": "default", "rollback_class": "safe",
        }})
        first = run(self.env, "adopt", "--relink")
        self.assertNotEqual(first.returncode, 0)
        self.assertIn("frozen", first.stderr)
        self.assertTrue((self.root / "current" / "foo").exists(),
                        "current/foo must have been created before the frozen surface aborted the relink")

        second = run(self.env, "adopt", "--relink")
        self.assertNotEqual(second.returncode, 0, "a retry must not proceed while the first attempt is in_progress")
        self.assertIn("in_progress", second.stderr)
        self.assertIn("recover", second.stderr)
        # The refusal must itself be a pure pre-check: no new txn/ledger entries from this attempt.
        state_before_recover = json.loads(run(self.env, "status", "--json").stdout)
        in_progress_txns = [t for t, r in state_before_recover["txns"].items() if r.get("status") == "in_progress"]
        self.assertEqual(len(in_progress_txns), 1, state_before_recover["txns"])

        recover_result = run(self.env, "recover")
        self.assertEqual(recover_result.returncode, 0, recover_result.stderr)
        self.assertEqual(len(json.loads(recover_result.stdout)["recovered_txns"]), 1)
        self.assertFalse((self.root / "current" / "foo").exists(), "recover must fully revert the stale relink")

        # A clean retry (spec fixed, surface removed) now succeeds from scratch.
        self.write_components({"foo": {
            "version": "1.0.0", "kind": "tarball", "root_name": "foo-1.0.0", "current_link": "current/foo",
            "entrypoints": [{"bin": "bin/foo", "in_root": "bin/foo"}], "surfaces": [], "state_dirs": [],
            "window": "default", "rollback_class": "safe",
        }})
        third = run(self.env, "adopt", "--relink")
        self.assertEqual(third.returncode, 0, third.stderr)
        self.assertTrue((self.root / "current" / "foo").exists())
        self.assertEqual(os.readlink(self.root / "bin" / "foo"), str(self.root / "current" / "foo" / "bin" / "foo"))


class TextReplaceAndFrozenTests(SwitchFixture):
    def setUp(self):
        super().setUp()
        self.tool_root = self.make_tool_root("bar-1.0.0", "barv1")
        self.link_entrypoint("bar", self.tool_root / "bin" / "bar")
        self.unit_path = self.root / "units" / "bar.service"
        self.unit_path.parent.mkdir()
        real_root = str(self.tool_root.resolve())
        self.unit_path.write_text(f"[Service]\nEnvironment=PATH={real_root}/bin\nExecStart={real_root}/bin/bar\n")
        self.original_unit_text = self.unit_path.read_text()

    def write_bar_spec(self, surface_path, expected_count=2, expected_pre_sha256=None):
        surface = {"kind": "text-replace", "path": str(surface_path), "expected_count": expected_count}
        if expected_pre_sha256 is not None:
            surface["expected_pre_sha256"] = expected_pre_sha256
        self.write_components({"bar": {
            "version": "1.0.0", "kind": "tarball", "root_name": "bar-1.0.0", "current_link": "current/bar",
            "entrypoints": [{"bin": "bin/bar", "in_root": "bin/bar"}],
            "surfaces": [surface],
            "state_dirs": [], "window": "default", "rollback_class": "safe",
        }})

    def test_relink_rewrites_the_unit_text_and_keeps_a_backup(self):
        self.write_bar_spec(self.unit_path)
        self.relink("bar")
        updated = self.unit_path.read_text()
        self.assertNotIn(str(self.tool_root.resolve()), updated)
        self.assertIn(str(self.root / "current" / "bar"), updated)
        backups = list((self.root / "switch" / "backups").rglob("*.orig"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(), self.original_unit_text)

    def test_relink_is_idempotent_for_a_component_with_a_text_replace_surface(self):
        # Minor finding: a plain second `adopt --relink` used to re-search the already-rewritten
        # file for the original real-root text (0 occurrences), raising after the bin/* link ops
        # were already ledgered and leaving an in_progress txn -- RelinkTests.test_relink_is_
        # idempotent only ever covered a component with no surfaces[] at all.
        self.write_bar_spec(self.unit_path)
        self.relink("bar")
        after_first = self.unit_path.read_text()
        backups_after_first = len(list((self.root / "switch" / "backups").rglob("*.orig")))
        text_replace_ops_after_first = sum(1 for e in switch.Ledger(self.root).all() if e["op"] == "text-replace")

        self.relink("bar")
        self.assertEqual(self.unit_path.read_text(), after_first, "a re-run must leave the surface unchanged")
        self.assertEqual(len(list((self.root / "switch" / "backups").rglob("*.orig"))), backups_after_first,
                         "an already-migrated surface must not be backed up again")
        text_replace_ops_after_second = sum(1 for e in switch.Ledger(self.root).all() if e["op"] == "text-replace")
        self.assertEqual(text_replace_ops_after_second, text_replace_ops_after_first,
                         "an already-migrated surface must not add a new ledger entry")
        # No leftover in_progress txn from the second (no-op) relink.
        recover_result = run(self.env, "recover")
        self.assertEqual(recover_result.returncode, 0, recover_result.stderr)
        self.assertEqual(json.loads(recover_result.stdout)["recovered_txns"], [])

    def test_relink_checks_the_expected_pre_image_sha256_when_the_surface_declares_one(self):
        # Previously-unresolved finding: expected_pre_sha256 existed only as an op_text_replace
        # parameter no production caller ever passed. adopt --relink is that caller for a
        # text-replace surface; a pins-v2 entry can now declare one to refuse a surface that
        # drifted from what the pin was written against, rather than blindly rewriting it.
        wrong_sha = "0" * 64
        self.write_bar_spec(self.unit_path, expected_pre_sha256=wrong_sha)
        before_real = os.path.realpath(self.root / "bin" / "bar")
        result = run(self.env, "adopt", "--relink")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("pre-image", result.stderr)
        self.assertEqual(self.unit_path.read_text(), self.original_unit_text)
        # Same partial-relink-failure shape as test_recover_rolls_back_a_relink_that_failed_
        # partway: the current/bar and bin/bar link ops already ledgered before this surface's
        # own precondition check ran are left in_progress, not silently applied, and `recover`
        # cleans them up rather than leaving bin/bar pointed at a relink that never finished.
        recover_result = run(self.env, "recover")
        self.assertEqual(recover_result.returncode, 0, recover_result.stderr)
        self.assertEqual(len(json.loads(recover_result.stdout)["recovered_txns"]), 1)
        self.assertEqual(os.path.realpath(self.root / "bin" / "bar"), before_real)

        right_sha = switch.sha256_bytes(self.unit_path.read_bytes())
        self.write_bar_spec(self.unit_path, expected_pre_sha256=right_sha)
        result = run(self.env, "adopt", "--relink")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(str(self.root / "current" / "bar"), self.unit_path.read_text())

    def test_relink_refuses_a_frozen_surface(self):
        frozen = self.root / "frozen" / "thing.txt"
        frozen.parent.mkdir()
        frozen.write_text("do not touch")
        self.write_bar_spec(frozen, expected_count=1)
        result = run(self.env, "adopt", "--relink")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("frozen", result.stderr)
        self.assertEqual(frozen.read_text(), "do not touch")

    def test_recover_rolls_back_a_relink_that_failed_partway(self):
        frozen = self.root / "frozen" / "thing.txt"
        frozen.parent.mkdir()
        frozen.write_text("do not touch")
        self.write_bar_spec(frozen, expected_count=1)
        before_real = os.path.realpath(self.root / "bin" / "bar")
        run(self.env, "adopt", "--relink")
        recover_result = run(self.env, "recover")
        self.assertEqual(recover_result.returncode, 0, recover_result.stderr)
        recovered = json.loads(recover_result.stdout)
        self.assertEqual(len(recovered["recovered_txns"]), 1)
        self.assertTrue(recovered["ledger_chain_ok"])
        self.assertEqual(os.path.realpath(self.root / "bin" / "bar"), before_real)

    def test_wrong_expected_count_refuses_without_writing(self):
        self.write_bar_spec(self.unit_path, expected_count=99)
        result = run(self.env, "adopt", "--relink")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.unit_path.read_text(), self.original_unit_text)


class TildeSurfaceRollbackTests(SwitchFixture):
    """Major finding: resolve_surface_path's own "~" expansion (op_text_replace/op_file_write,
    the forward path) was never applied on the rollback/re-run side: apply_inverse built its
    text-replace/file-write targets as root / surface, and relink's own already-migrated probe
    built its target the same unexpanded way. A ~-rooted surface is the only way a consumer
    outside $ECO_INSTALL_ROOT (a user systemd unit, or a ~/codex-ecosystem/bin wrapper) can be
    named at all -- validate.py's personal-home-path scan rejects a literal /home/<user> path in
    a tracked file -- so this exercises exactly that shape with a real ~-relative surface path
    resolved against a fake HOME, the same technique
    OperationUnitTests.test_op_data_backup_expands_a_tilde_state_dir_path already uses for
    state_dirs[], but through the CLI end to end (relink, then rollback/a second relink) instead
    of calling the operation function directly."""

    def setUp(self):
        super().setUp()
        self.fake_home = Path(self.tmp.name) / "fake-home"
        (self.fake_home / ".config" / "bar").mkdir(parents=True)
        self.env = {**self.env, "HOME": str(self.fake_home)}
        self.tool_root = self.make_tool_root("bar-1.0.0", "barv1")
        self.link_entrypoint("bar", self.tool_root / "bin" / "bar")
        self.home_unit = self.fake_home / ".config" / "bar" / "bar.service"
        real_root = str(self.tool_root.resolve())
        self.home_unit.write_text(f"[Service]\nExecStart={real_root}/bin/bar\n")
        self.original_text = self.home_unit.read_text()
        self.write_components({"bar": {
            "version": "1.0.0", "kind": "tarball", "root_name": "bar-1.0.0", "current_link": "current/bar",
            "entrypoints": [{"bin": "bin/bar", "in_root": "bin/bar"}],
            "surfaces": [{"kind": "text-replace", "path": "~/.config/bar/bar.service", "expected_count": 1}],
            "state_dirs": [], "window": "default", "rollback_class": "safe",
        }})

    def test_relink_then_rollback_restores_a_tilde_surface_in_place(self):
        self.relink("bar")
        updated = self.home_unit.read_text()
        self.assertIn(str(self.root / "current" / "bar"), updated)
        self.assertNotEqual(updated, self.original_text)
        # Nothing was ever written under a literal "~" directory inside ECO_INSTALL_ROOT: the
        # bug this guards against wrote a rollback pre-image to $ECO_INSTALL_ROOT/~/... instead
        # of the real ~-expanded file.
        self.assertFalse((self.root / "~").exists())

        result = run(self.env, "rollback", "bar")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.home_unit.read_text(), self.original_text,
                         "rollback must restore the real ~-expanded file in place")
        self.assertFalse((self.root / "~").exists(), "rollback must never write under a literal ~ directory")
        # The real consumer must still resolve, not be left pointing at an unlinked current/bar.
        recover_result = run(self.env, "recover")
        self.assertEqual(recover_result.returncode, 0, recover_result.stderr)
        self.assertEqual(json.loads(recover_result.stdout)["recovered_txns"], [])

    def test_a_second_relink_recognizes_an_already_migrated_tilde_surface(self):
        self.relink("bar")
        after_first = self.home_unit.read_text()
        text_replace_ops_after_first = sum(1 for e in switch.Ledger(self.root).all() if e["op"] == "text-replace")
        # Second run must be a no-op (idempotent), not a failed re-search for text that is
        # already gone -- the same guarantee TextReplaceAndFrozenTests proves for a non-~
        # surface (test_relink_is_idempotent_for_a_component_with_a_text_replace_surface). The
        # bug this guards against built the probe path without expansion, so it always looked at
        # $ECO_INSTALL_ROOT/~/.config/bar/bar.service (never exists), never found the "already
        # migrated" state, and fell through to op_text_replace's own "expected 1, found 0" refusal
        # against the REAL file on every re-run.
        self.relink("bar")
        self.assertEqual(self.home_unit.read_text(), after_first)
        text_replace_ops_after_second = sum(1 for e in switch.Ledger(self.root).all() if e["op"] == "text-replace")
        self.assertEqual(text_replace_ops_after_second, text_replace_ops_after_first,
                         "an already-migrated ~ surface must not add a new ledger entry")
        recover_result = run(self.env, "recover")
        self.assertEqual(recover_result.returncode, 0, recover_result.stderr)
        self.assertEqual(json.loads(recover_result.stdout)["recovered_txns"], [])


class ApplyGateTests(SwitchFixture):
    def setUp(self):
        super().setUp()
        self.root_v1 = self.make_tool_root("foo-1.0.0", "v1")
        self.root_v2 = self.make_tool_root("foo-2.0.0", "v2")
        self.link_entrypoint("foo", self.root_v1 / "bin" / "foo")
        self.write_components({"foo": {
            "version": "1.0.0", "kind": "tarball", "root_name": "foo-1.0.0", "current_link": "current/foo",
            "entrypoints": [{"bin": "bin/foo", "in_root": "bin/foo"}], "surfaces": [], "state_dirs": [],
            "window": "default", "rollback_class": "safe",
        }})
        self.relink("foo")
        self.write_window("default", allowed=("foo",), open_now=True)

    def run_entrypoint(self):
        return subprocess.run([str(self.root / "bin" / "foo")], capture_output=True, text=True).stdout.strip()

    def test_happy_path_apply_then_rollback_by_component(self):
        self.write_receipt("R1", "foo", "2.0.0")
        result = self.apply("foo", self.root_v2, "R1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "applied")
        self.assertEqual(self.run_entrypoint(), "v2")
        state = json.loads(run(self.env, "status", "--json").stdout)
        self.assertEqual(state["components"]["foo"]["current"], str(self.root_v2.resolve()))

        rollback = run(self.env, "rollback", "foo")
        self.assertEqual(rollback.returncode, 0, rollback.stderr)
        self.assertEqual(self.run_entrypoint(), "v1")
        self.assertEqual(os.readlink(self.root / "bin" / "foo"), str(self.root / "current" / "foo" / "bin" / "foo"))

    def test_verify_detects_an_entrypoint_that_bypasses_current_link(self):
        # Minor finding: neither apply's post-verify nor a standalone `verify` checked that
        # bin/* entrypoints still route THROUGH current/<id> at all -- only that current/<id>
        # itself still matched the ledger. A plain bootstrap-linux.sh re-run (without --no-link/
        # --link-dir) or a manual ln -sfn repoints bin/* straight at tools/<name>-<version>
        # again, silently undoing adopt --relink's indirection: current/<id> still flips
        # correctly on the next apply, and status/verify both used to report "ok" throughout
        # while bin/* kept running whatever build it was last pointed at directly.
        bypass_target = self.root_v1 / "bin" / "foo"
        (self.root / "bin" / "foo").unlink()
        (self.root / "bin" / "foo").symlink_to(bypass_target)
        result = run(self.env, "verify", "--json")
        self.assertNotEqual(result.returncode, 0)
        report = json.loads(result.stdout)
        self.assertFalse(report["foo"]["ok"])
        self.assertIn("current/foo", report["foo"]["issue"])

    def test_apply_post_verify_also_catches_a_bypassed_entrypoint_and_rolls_back(self):
        # The same check, exercised through apply's own automatic post-verify: bin/foo is
        # bypassed BEFORE the apply that would otherwise succeed, so the post-apply verify must
        # still catch it and trigger the usual automatic rollback -- not report "applied" while
        # bin/foo silently keeps running a build unrelated to current/foo.
        (self.root / "bin" / "foo").unlink()
        (self.root / "bin" / "foo").symlink_to(self.root_v1 / "bin" / "foo")
        self.write_receipt("R1", "foo", "2.0.0")
        result = self.apply("foo", self.root_v2, "R1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("rolled back", (result.stderr + result.stdout).lower())

    def test_reapply_after_rollback_does_not_false_positive_drift(self):
        self.write_receipt("R1", "foo", "2.0.0")
        self.apply("foo", self.root_v2, "R1")
        run(self.env, "rollback", "foo")
        result = self.apply("foo", self.root_v2, "R1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.run_entrypoint(), "v2")

    def test_apply_backs_up_a_qualified_state_dir_before_flipping_the_link(self):
        # Operation-kind gap: apply never turned a component's state_dirs[] into a data-backup
        # step (the ai-memory pin's own note: a switch "must data-backup it"). A "pending"
        # marker (every state_dirs[] entry shipped so far) is still left alone -- only a
        # qualified entry (no "pending" status) becomes a real backup step.
        state_dir = self.root / "state" / "foo-data"
        state_dir.mkdir(parents=True)
        (state_dir / "db.sqlite").write_text("important")
        self.write_components({"foo": {
            "version": "1.0.0", "kind": "tarball", "root_name": "foo-1.0.0", "current_link": "current/foo",
            "entrypoints": [{"bin": "bin/foo", "in_root": "bin/foo"}], "surfaces": [],
            "state_dirs": [{"path": "state/foo-data"}],
            "window": "default", "rollback_class": "safe",
        }})
        self.write_receipt("R1", "foo", "2.0.0")
        result = self.apply("foo", self.root_v2, "R1")
        self.assertEqual(result.returncode, 0, result.stderr)
        backups = list((self.root / "switch" / "backups").rglob("db.sqlite"))
        self.assertEqual(len(backups), 1, "a qualified state_dirs[] entry must be backed up on apply")
        self.assertEqual(backups[0].read_text(), "important")
        ledger_entries = switch.Ledger(self.root).all()
        self.assertTrue(any(e["op"] == "data-backup" and e["surface"] == "state/foo-data" for e in ledger_entries))

    def test_apply_leaves_a_pending_state_dir_alone(self):
        self.write_components({"foo": {
            "version": "1.0.0", "kind": "tarball", "root_name": "foo-1.0.0", "current_link": "current/foo",
            "entrypoints": [{"bin": "bin/foo", "in_root": "bin/foo"}], "surfaces": [],
            "state_dirs": [{"path": "state/does-not-exist", "status": "pending", "note": "not verified yet"}],
            "window": "default", "rollback_class": "safe",
        }})
        self.write_receipt("R1", "foo", "2.0.0")
        result = self.apply("foo", self.root_v2, "R1")
        self.assertEqual(result.returncode, 0, f"a pending state_dirs[] entry must never be guessed at: {result.stderr}")

    def test_apply_accepts_a_dated_suffixed_to_root_when_the_receipt_uses_the_full_suffix_as_version(self):
        # tools/<id>-<version>-rDATE (this rollout's own bootstrap --tools-suffix convention):
        # the version derived from --to-root is the full "2.0.0-r20260925" suffix, not just
        # "r20260925" (the old rsplit("-", 1) bug). A receipt whose identity.version happens to
        # equal that whole string still authorizes the root (the root name equals
        # "<component>-<identity.version>" exactly).
        dated_root = self.make_tool_root("foo-2.0.0-r20260925", "v2-dated")
        self.write_receipt("R2", "foo", "2.0.0-r20260925")
        result = self.apply("foo", dated_root, "R2")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.run_entrypoint(), "v2-dated")

    def test_apply_accepts_a_dated_suffixed_to_root_when_the_receipt_uses_the_clean_upstream_version(self):
        # Major finding: identity.version must stay the clean upstream version
        # (record_native_rollout.py copies it verbatim into a landscape winner's pin, read
        # downstream by validate_pins_v2 parity and platform_status.py's host-receipt binding
        # against a live host's plain `--version` output) -- it must never be forced to also
        # carry a bootstrap staging suffix just to satisfy this apply. A receipt for the real
        # "2.0.0" now authorizes a staged "2.0.0-r20260925" root as long as its own install.root
        # names that exact staged path (the actual, stronger binding).
        dated_root = self.make_tool_root("foo-2.0.0-r20260925", "v2-dated")
        self.write_receipt("R2", "foo", "2.0.0", install_root="${STACK_HOME}/tools/foo-2.0.0-r20260925")
        result = self.apply("foo", dated_root, "R2")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.run_entrypoint(), "v2-dated")

    def test_apply_refuses_a_receipt_whose_clean_version_is_inconsistent_with_a_dated_root(self):
        # Defense in depth: a receipt for a *different* base version must not authorize a staged
        # root merely because both end in the same date suffix (e.g. a same-day rebuild off a
        # different base) -- even before install.root is ever consulted.
        dated_root = self.make_tool_root("foo-2.0.0-r20260925", "v2-dated")
        self.write_receipt("R2", "foo", "1.9.0", install_root="${STACK_HOME}/tools/foo-2.0.0-r20260925")
        result = self.apply("foo", dated_root, "R2")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not consistent", result.stderr)
        self.assertEqual(self.run_entrypoint(), "v1")

    def test_rollback_refuses_a_txn_a_later_apply_already_superseded(self):
        # Major finding: rollback --txn (including the timer's --if-unconfirmed call) must not
        # blindly re-point current/<id> to an old txn's "from" once a later apply has moved the
        # component on again -- that would clobber the later apply.
        self.write_receipt("R1", "foo", "2.0.0")
        first = self.apply("foo", self.root_v2, "R1")
        self.assertEqual(first.returncode, 0, first.stderr)
        first_txn = json.loads(first.stdout)["txn"]
        root_v3 = self.make_tool_root("foo-3.0.0", "v3")
        self.write_receipt("R3", "foo", "3.0.0")
        second = self.apply("foo", root_v3, "R3")
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(self.run_entrypoint(), "v3")

        result = run(self.env, "rollback", "--txn", first_txn)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("supersed", result.stderr.lower())
        self.assertEqual(self.run_entrypoint(), "v3", "the superseded rollback must never have touched current/foo")

    def test_recover_refuses_to_clobber_a_txn_a_later_apply_already_superseded(self):
        # Previously-unresolved finding: the superseded-txn refusal above only ever protected a
        # manual `rollback --txn` (cmd_rollback's own pre-check). `recover` -- reconciling any
        # txn still in_progress after a crash -- calls rollback_txn directly, with no equivalent
        # check, so a crashed txn whose component a *later*, successful apply has since moved on
        # would be blindly reversed, silently clobbering that later apply.
        crashed_txn = "crashed-1"
        ledger = switch.Ledger(self.root)
        ledger.append(txn=crashed_txn, op="txn_begin", component="foo", surface="_txn")
        # Really move the link (as a real apply's own link step would), but never append
        # verify_pass -- simulating a crash right after the link, before the post-apply verify.
        fields, _inverse = switch.op_link(self.root, "current/foo", str(self.root_v2.resolve()))
        ledger.append(txn=crashed_txn, op="link", component="foo", surface="current/foo", **fields)
        self.assertEqual(self.run_entrypoint(), "v2")

        # A later, real apply succeeds and moves "foo" on again -- superseding the crashed txn.
        root_v3 = self.make_tool_root("foo-3.0.0", "v3")
        self.write_receipt("R3", "foo", "3.0.0")
        later = self.apply("foo", root_v3, "R3")
        self.assertEqual(later.returncode, 0, later.stderr)
        self.assertEqual(self.run_entrypoint(), "v3")

        recover_result = run(self.env, "recover")
        payload = json.loads(recover_result.stdout)
        self.assertNotIn(crashed_txn, payload["recovered_txns"],
                         "a superseded in_progress txn must not be silently reversed")
        self.assertTrue(any(crashed_txn in problem and "supersed" in problem.lower()
                            for problem in payload["rollback_problems"]), payload["rollback_problems"])
        # current/foo must still point at the later, real apply's root -- never clobbered.
        self.assertEqual(self.run_entrypoint(), "v3")
        state = json.loads(run(self.env, "status", "--json").stdout)
        self.assertEqual(state["components"]["foo"]["current"], str(root_v3.resolve()))

    def test_confirm_refuses_a_rolled_back_txn(self):
        self.write_receipt("R1", "foo", "2.0.0")
        applied = self.apply("foo", self.root_v2, "R1")
        txn = json.loads(applied.stdout)["txn"]
        run(self.env, "rollback", "--txn", txn)
        result = run(self.env, "confirm", "--txn", txn)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("rolled back", result.stderr.lower())

    def test_missing_receipt_refuses(self):
        result = self.apply("foo", self.root_v2, "does-not-exist")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("receipt", result.stderr.lower())
        self.assertEqual(self.run_entrypoint(), "v1")

    def test_receipt_for_wrong_version_refuses(self):
        self.write_receipt("R1", "foo", "9.9.9")
        result = self.apply("foo", self.root_v2, "R1")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.run_entrypoint(), "v1")

    def test_receipt_missing_t2_refuses(self):
        self.write_receipt("R1", "foo", "2.0.0", tiers=(("T0", "passed", None), ("T1", "unavailable", "no GPU"),
                                                        ("T4", "passed", None)))
        result = self.apply("foo", self.root_v2, "R1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("T2", result.stderr)

    def test_receipt_t1_neither_passed_nor_declared_unavailable_refuses(self):
        self.write_receipt("R1", "foo", "2.0.0", tiers=(("T0", "passed", None), ("T1", "failed", None),
                                                        ("T2", "passed", None), ("T4", "passed", None)))
        result = self.apply("foo", self.root_v2, "R1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("T1", result.stderr)

    def test_receipt_status_not_passed_refuses(self):
        self.write_receipt("R1", "foo", "2.0.0", status="partial")
        result = self.apply("foo", self.root_v2, "R1")
        self.assertNotEqual(result.returncode, 0)

    def test_window_closed_refuses(self):
        self.write_receipt("R1", "foo", "2.0.0")
        self.write_window("default", allowed=("foo",), open_now=False)
        result = self.apply("foo", self.root_v2, "R1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("window", result.stderr.lower())

    def test_window_excludes_component_refuses(self):
        self.write_receipt("R1", "foo", "2.0.0")
        self.write_window("default", allowed=("someone-else",), open_now=True)
        result = self.apply("foo", self.root_v2, "R1")
        self.assertNotEqual(result.returncode, 0)

    def test_malformed_window_bound_refuses_rather_than_comparing_it_as_open(self):
        # A non-Z-suffixed offset or a garbled bound (e.g. "z") must never be compared as a
        # plain string against now_utc_iso()'s canonical shape -- that can misjudge a window by
        # hours, or leave it looking permanently open (or permanently closed).
        self.write_receipt("R1", "foo", "2.0.0")
        (self.root / "switch" / "windows").mkdir(parents=True, exist_ok=True)
        window = {"name": "default", "start_utc": "2026-09-25T00:00:00+02:00", "end_utc": "z",
                  "allowed_components": ["foo"]}
        (self.root / "switch" / "windows" / "default.json").write_text(json.dumps(window))
        result = self.apply("foo", self.root_v2, "R1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("malformed", result.stderr.lower())
        self.assertEqual(self.run_entrypoint(), "v1")

    def test_relative_to_root_is_refused(self):
        self.write_receipt("R1", "foo", "2.0.0")
        result = run(self.env, "apply", "foo", "--to-root", "tools/foo-2.0.0", "--receipt", "R1",
                     "--window", "default", "--plan-sha256", "0" * 64)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("absolute", result.stderr)

    def test_plan_and_apply_refuse_a_component_relink_never_pointed_bin_through(self):
        # Minor finding: build_apply_plan used to check only that the spec *named* a
        # current_link string, not that adopt --relink had actually created it yet. Applying
        # before that would leave current/<id> created fresh at --to-root while bin/* still
        # resolved directly into the old real root, unredirected -- apply reporting "applied"
        # with no real change to what bin/* runs.
        self.write_components({"never-relinked": {
            "version": "1.0.0", "kind": "tarball", "root_name": "foo-1.0.0",
            "current_link": "current/never-relinked", "entrypoints": [], "surfaces": [],
            "state_dirs": [], "window": "default", "rollback_class": "safe",
        }})
        plan_result = run(self.env, "plan", "never-relinked", "--to-root", str(self.root_v2), "--receipt", "R9")
        self.assertNotEqual(plan_result.returncode, 0)
        self.assertIn("does not exist yet", plan_result.stderr)
        apply_result = run(self.env, "apply", "never-relinked", "--to-root", str(self.root_v2), "--receipt", "R9",
                           "--window", "default", "--plan-sha256", "0" * 64)
        self.assertNotEqual(apply_result.returncode, 0)
        self.assertIn("does not exist yet", apply_result.stderr)
        self.assertFalse((self.root / "current" / "never-relinked").exists())

    def test_stale_plan_sha256_refuses(self):
        self.write_receipt("R1", "foo", "2.0.0")
        result = run(self.env, "apply", "foo", "--to-root", str(self.root_v2), "--receipt", "R1",
                     "--window", "default", "--plan-sha256", "0" * 64)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("plan-sha256", result.stderr)

    def test_drift_is_refused_until_resync(self):
        self.write_receipt("R1", "foo", "2.0.0")
        # Bypass the tool: an operator manually relinks current/foo, as the pre-switch "manual
        # ln -sfn" workflow used to (switch.md Facts).
        current = self.root / "current" / "foo"
        current.unlink()
        current.symlink_to(self.root_v2.resolve())
        result = self.apply("foo", self.root_v2, "R1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("drift", result.stderr)
        resync = run(self.env, "adopt", "--resync", "foo", "--reason", "operator manually relinked for a demo")
        self.assertEqual(resync.returncode, 0, resync.stderr)
        result2 = self.apply("foo", self.root_v2, "R1")
        self.assertEqual(result2.returncode, 0, result2.stderr)

    def test_resync_without_reason_is_refused(self):
        result = run(self.env, "adopt", "--resync", "foo")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("reason", result.stderr.lower())

    def test_failed_verify_triggers_automatic_rollback(self):
        self.write_receipt("R1", "foo", "9.9.9")
        missing_root = self.root / "tools" / "foo-9.9.9"  # never created
        digest = self.plan_sha("foo", missing_root, "R1")
        result = run(self.env, "apply", "foo", "--to-root", str(missing_root), "--receipt", "R1",
                     "--window", "default", "--plan-sha256", digest)
        self.assertNotEqual(result.returncode, 0)
        combined_output = result.stderr.lower() + result.stdout.lower()
        self.assertTrue(combined_output, "apply must print something on stderr/stdout, not fail silently")
        self.assertIn("rolled back", combined_output)
        self.assertEqual(self.run_entrypoint(), "v1")
        state = json.loads(run(self.env, "status", "--json").stdout)
        self.assertEqual(state["components"]["foo"]["current"], str(self.root_v1.resolve()))


class ConfirmAndRevertTests(SwitchFixture):
    STUB_SYSTEMD_RUN = textwrap.dedent("""\
        #!/usr/bin/env python3
        import subprocess, sys
        # Instrumented stand-in for `systemd-run --user --on-active=Ns --unit=... -- CMD...`:
        # records the call and, when FIRE_IMMEDIATELY is set, launches CMD detached (Popen, not
        # run/wait) so it fires after this scheduling call -- and the apply that made it -- has
        # already returned and released switch/switch.lock, the same as a real systemd timer
        # firing seconds later: never synchronously inside the still-locked apply that scheduled it.
        import os
        args = sys.argv[1:]
        dashdash = args.index("--")
        command = args[dashdash + 1:]
        with open(os.environ["STUB_LOG"], "a") as log:
            log.write(" ".join(command) + "\\n")
        if os.environ.get("FIRE_IMMEDIATELY") == "1":
            subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        sys.exit(0)
        """)

    def setUp(self):
        super().setUp()
        self.root_v1 = self.make_tool_root("foo-1.0.0", "v1")
        self.root_v2 = self.make_tool_root("foo-2.0.0", "v2")
        self.link_entrypoint("foo", self.root_v1 / "bin" / "foo")
        self.write_components({"foo": {
            "version": "1.0.0", "kind": "tarball", "root_name": "foo-1.0.0", "current_link": "current/foo",
            "entrypoints": [{"bin": "bin/foo", "in_root": "bin/foo"}], "surfaces": [], "state_dirs": [],
            "window": "default", "rollback_class": "safe",
        }})
        self.relink("foo")
        self.write_window("default", allowed=("foo",), open_now=True)
        self.write_receipt("R1", "foo", "2.0.0")
        stub_path = self.root / "stub-systemd-run.py"
        stub_path.write_text(self.STUB_SYSTEMD_RUN)
        stub_path.chmod(0o755)
        self.stub_log = self.root / "stub.log"
        self.env = {**self.env, "ECOSYSTEM_SWITCH_SYSTEMD_RUN": f"{sys.executable} {stub_path}",
                   "STUB_LOG": str(self.stub_log)}

    def run_entrypoint(self):
        return subprocess.run([str(self.root / "bin" / "foo")], capture_output=True, text=True).stdout.strip()

    def test_pending_confirmation_then_confirm_keeps_the_new_version(self):
        result = self.apply("foo", self.root_v2, "R1", extra=("--confirm-within", "300"))
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "pending_confirmation")
        self.assertTrue(self.stub_log.is_file(), "the confirm-or-revert timer must have been scheduled")
        self.assertIn(payload["txn"], self.stub_log.read_text())
        self.assertEqual(self.run_entrypoint(), "v2")

        confirm = run(self.env, "confirm", "--txn", payload["txn"])
        self.assertEqual(confirm.returncode, 0, confirm.stderr)

        # The timer firing after confirmation must be a no-op (--if-unconfirmed).
        late_fire = run(self.env, "rollback", "--txn", payload["txn"], "--if-unconfirmed")
        self.assertEqual(late_fire.returncode, 0, late_fire.stderr)
        self.assertEqual(json.loads(late_fire.stdout)["status"], "already_confirmed")
        self.assertEqual(self.run_entrypoint(), "v2")

    def test_unconfirmed_timer_firing_reverts(self):
        env = {**self.env, "FIRE_IMMEDIATELY": "1"}
        result = run(env, "apply", "foo", "--to-root", str(self.root_v2), "--receipt", "R1",
                     "--window", "default", "--plan-sha256", self.plan_sha("foo", self.root_v2, "R1"),
                     "--confirm-within", "1")
        self.assertEqual(result.returncode, 0, result.stderr)
        # The stub's detached rollback fires just after this apply returns (and releases the
        # lock it scheduled the timer under); poll briefly rather than assume it has landed yet.
        deadline = time.time() + 5
        while time.time() < deadline and self.run_entrypoint() != "v1":
            time.sleep(0.1)
        self.assertEqual(self.run_entrypoint(), "v1")
        state = json.loads(run(self.env, "status", "--json").stdout)
        self.assertEqual(state["components"]["foo"]["current"], str(self.root_v1.resolve()))

    def test_confirm_refuses_an_in_progress_txn(self):
        # Previously-unresolved finding: confirming a crashed/interrupted apply (still
        # in_progress: never reached a post-apply verify) used to mark it "applied" through the
        # ledger alone, and recover only ever reconciles a txn still "in_progress" -- so it would
        # then never see that transaction again either, contradicting lifecycle.md's "a crashed
        # or interrupted apply never completes after the fact".
        ledger = switch.Ledger(self.root)
        ledger.append(txn="crashed-1", op="txn_begin", component="synthetic", surface="_txn")
        ledger.append(**{"txn": "crashed-1", "op": "link", "component": "synthetic",
                         "surface": "current/synthetic", "from": None, "to": "/does/not/matter"})
        result = run(self.env, "confirm", "--txn", "crashed-1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("in_progress", result.stderr)
        # recover must still see it and roll it back -- confirm must not have "completed" it.
        recover_result = run(self.env, "recover")
        self.assertEqual(recover_result.returncode, 0, recover_result.stderr)
        self.assertEqual(json.loads(recover_result.stdout)["recovered_txns"], ["crashed-1"])

    def test_baseline_between_apply_and_its_revert_timer_must_not_block_the_revert(self):
        # Previously-unresolved finding (round 3/4): adopt --baseline re-records the live
        # current/<id> value under a brand-new txn id for every component in the spec. Since
        # apply's own link step already flips current/<id> before a pending_confirmation txn is
        # confirmed, a baseline run in that window observes the exact same value apply just set --
        # yet recompute_state used to let that observation become the component's own updated_txn
        # anyway, so the still-pending apply's own revert timer (`rollback --txn T
        # --if-unconfirmed`) then refused T as "superseded" by a baseline that changed nothing on
        # disk at all.
        result = self.apply("foo", self.root_v2, "R1", extra=("--confirm-within", "300"))
        self.assertEqual(result.returncode, 0, result.stderr)
        txn = json.loads(result.stdout)["txn"]

        baseline = run(self.env, "adopt", "--baseline")
        self.assertEqual(baseline.returncode, 0, baseline.stderr)
        self.assertEqual(json.loads(baseline.stdout)["observed"]["foo"], str(self.root_v2.resolve()))

        revert = run(self.env, "rollback", "--txn", txn, "--if-unconfirmed")
        self.assertEqual(revert.returncode, 0, revert.stderr)
        self.assertEqual(json.loads(revert.stdout)["status"], "rolled_back")
        self.assertEqual(self.run_entrypoint(), "v1")


@REQUIRES_PROCFS
class UnitRestartTests(SwitchFixture):
    STUB_SYSTEMCTL = textwrap.dedent("""\
        #!/usr/bin/env python3
        import json, sys, os
        args = sys.argv[1:]
        if args[:2] == ["--user", "daemon-reload"]:
            sys.exit(0)
        if args[:2] == ["--user", "restart"]:
            unit = args[2]
            with open(os.environ["STUB_LOG"], "a") as log:
                log.write(f"restart {unit}\\n")
            if unit == os.environ.get("STUB_DENY_RESTART"):
                sys.exit(1)
            sys.exit(0)
        if args[:2] == ["--user", "show"]:
            # Reflects whichever root current/svc *actually* points at right now, read live, so
            # a forward apply and a later rollback correctly report different daemons (the two
            # real, separately copied interpreters started in setUp) instead of one fixed pid.
            pid = os.environ.get("STUB_MAIN_PID", str(os.getpid()))
            eco_root, pid_map_path = os.environ.get("ECO_INSTALL_ROOT"), os.environ.get("STUB_PID_MAP")
            if eco_root and pid_map_path:
                try:
                    current = os.path.realpath(os.path.join(eco_root, "current", "svc"))
                    with open(pid_map_path) as handle:
                        pid = str(json.load(handle).get(current, pid))
                except OSError:
                    pass
            print(pid)
            sys.exit(0)
        sys.exit(1)
        """)

    def setUp(self):
        super().setUp()
        self.root_v1 = self.make_tool_root("svc-1.0.0", "v1")
        self.root_v2 = self.make_tool_root("svc-2.0.0", "v2")
        self.link_entrypoint("svc", self.root_v1 / "bin" / "svc")
        stub_path = self.root / "stub-systemctl.py"
        stub_path.write_text(self.STUB_SYSTEMCTL)
        stub_path.chmod(0o755)
        self.stub_log = self.root / "systemctl.log"
        # The health probe reads /proc/<MainPID>/exe and requires it to resolve *inside* the
        # expected root; os.getpid() would only ever resolve to this test's own /usr/bin/python3,
        # so a real, separate copy of the interpreter is placed inside each root and run as a
        # genuine long-lived process -- exec through a symlink still reports the symlink's real
        # target, not a path inside the root, so this needs an actual independent copy per root
        # (one process per root, so a rollback's re-probe genuinely differs from the forward
        # apply's, rather than trivially reusing the one process that happens to already exist).
        self.daemons = {}
        for root_dir in (self.root_v1, self.root_v2):
            daemon_bin = root_dir / "bin" / "svc-daemon"
            shutil.copy2(sys.executable, daemon_bin)
            daemon_bin.chmod(0o755)
            self.daemons[root_dir] = subprocess.Popen([str(daemon_bin), "-c", "import time; time.sleep(60)"])
        self.addCleanup(self._stop_daemons)
        pid_map_path = self.root / "pid-map.json"
        pid_map_path.write_text(json.dumps({str(root_dir.resolve()): proc.pid for root_dir, proc in self.daemons.items()}))
        self.env = {**self.env, "ECOSYSTEM_SWITCH_SYSTEMCTL": f"{sys.executable} {stub_path}",
                   "STUB_LOG": str(self.stub_log), "STUB_MAIN_PID": str(self.daemons[self.root_v2].pid),
                   "STUB_PID_MAP": str(pid_map_path),
                   # Minor finding: every test below but the two memory-gate ones (which override
                   # this key locally to force a refusal) needs a real restart to proceed past the
                   # memory gate to exercise; without this, they silently depended on the real
                   # host clearing DEFAULT_MIN_MEMORY_KIB (6 GiB) MemAvailable, which
                   # ecosystem-bounded-run's cgroup cap does not itself change and a smaller CI
                   # runner might not clear -- an unrelated failure the acceptance full suite would
                   # then count as a regression. 0 always passes the gate regardless of real host
                   # memory, the same way the low-memory tests already force a refusal with a
                   # locally-overridden huge value.
                   "ECOSYSTEM_SWITCH_TEST_FORCE_MIN_MEMORY_KIB": "0"}
        self.write_window("default", allowed=("svc",), open_now=True)
        self.write_receipt("R1", "svc", "2.0.0")

    def _stop_daemons(self):
        for proc in self.daemons.values():
            proc.terminate()
        for proc in self.daemons.values():
            with contextlib.suppress(subprocess.TimeoutExpired):
                proc.wait(timeout=5)

    def write_svc_spec(self):
        self.write_components({"svc": {
            "version": "1.0.0", "kind": "tarball", "root_name": "svc-1.0.0", "current_link": "current/svc",
            "entrypoints": [{"bin": "bin/svc", "in_root": "bin/svc"}],
            "surfaces": [{"kind": "unit-restart", "path": "svc.service"}],
            "state_dirs": [], "window": "default", "rollback_class": "restart_required",
        }})

    def test_apply_restarts_the_unit_and_health_probes_the_new_root(self):
        self.write_svc_spec()
        self.relink("svc")
        digest = self.plan_sha("svc", self.root_v2, "R1")
        result = run(self.env, "apply", "svc", "--to-root", str(self.root_v2), "--receipt", "R1",
                     "--window", "default", "--plan-sha256", digest)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("restart svc.service", self.stub_log.read_text())

    def test_denylisted_unit_is_never_restarted(self):
        self.write_components({"svc": {
            "version": "1.0.0", "kind": "tarball", "root_name": "svc-1.0.0", "current_link": "current/svc",
            "entrypoints": [{"bin": "bin/svc", "in_root": "bin/svc"}],
            "surfaces": [{"kind": "unit-restart", "path": "mover-daily-scan-0925"}],
            "state_dirs": [], "window": "default", "rollback_class": "restart_required",
        }})
        self.relink("svc")
        digest = self.plan_sha("svc", self.root_v2, "R1")
        result = run(self.env, "apply", "svc", "--to-root", str(self.root_v2), "--receipt", "R1",
                     "--window", "default", "--plan-sha256", digest)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.stub_log.exists() and self.stub_log.read_text(),
                         "a denylisted unit must never reach systemctl restart")
        # Major finding: apply used to flip current/<id> before the denylist check, leaving the
        # component on the new root even though the restart itself never happened. The denylist
        # is now checked before anything is touched, so the live entrypoint must be untouched.
        self.assertEqual(os.path.realpath(self.root / "bin" / "svc"), os.path.realpath(self.root_v1 / "bin" / "svc"))
        state = json.loads(run(self.env, "status", "--json").stdout)
        self.assertEqual(state["components"]["svc"]["current"], str(self.root_v1.resolve()))

    def test_low_memory_refuses_the_restart(self):
        self.write_svc_spec()
        self.relink("svc")
        digest = self.plan_sha("svc", self.root_v2, "R1")
        # ECOSYSTEM_SWITCH_MIN_MEMORY_KIB may only ever raise DEFAULT_MIN_MEMORY_KIB (never lower
        # this safety floor via a casual env var), so a test that needs the gate to reliably
        # refuse regardless of this host's real MemAvailable uses the test-only, unbounded
        # override instead: ECOSYSTEM_SWITCH_TEST_FORCE_MIN_MEMORY_KIB.
        env = {**self.env, "ECOSYSTEM_SWITCH_TEST_FORCE_MIN_MEMORY_KIB": str(2**62)}
        result = run(env, "apply", "svc", "--to-root", str(self.root_v2), "--receipt", "R1",
                     "--window", "default", "--plan-sha256", digest)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("kib", result.stderr.lower())
        self.assertIn("model-loading", result.stderr.lower())
        # The memory gate now runs before current/svc is touched (major finding: apply used to
        # flip the link before the denylist/memory/restart gates), so a refused restart must
        # leave the live entrypoint on the old root entirely, not just fail to finish.
        self.assertEqual(os.path.realpath(self.root / "bin" / "svc"), os.path.realpath(self.root_v1 / "bin" / "svc"))

    def test_min_memory_kib_env_var_can_only_raise_the_floor_not_lower_it(self):
        # Minor finding: the clamp direction used to be inverted (min(requested, DEFAULT)),
        # letting a plain ECOSYSTEM_SWITCH_MIN_MEMORY_KIB silently disable the gate down to 0
        # (the dangerous direction for a floor meant to prevent an OOM during a model-loading
        # restart) while a request to make it *stricter* was the one silently ignored. It must
        # now never make the gate *more* permissive than DEFAULT_MIN_MEMORY_KIB, only ever as
        # strict or stricter -- only ECOSYSTEM_SWITCH_TEST_FORCE_MIN_MEMORY_KIB can loosen it, and
        # only for a test.
        self.assertIsNone(switch.memory_gate_issue(min_kib=0), "an explicit min_kib=0 bypasses "
                          "env-based clamping entirely -- unaffected by this guarantee")
        with unittest.mock.patch.dict(os.environ, {"ECOSYSTEM_SWITCH_MIN_MEMORY_KIB": "0"}, clear=False):
            # Clamped back up to DEFAULT_MIN_MEMORY_KIB, not honoured outright: a request to
            # lower the floor to 0 must never actually let a restart through with less than the
            # real default's worth of memory free.
            available = switch.available_memory_kib()
            issue = switch.memory_gate_issue()
            if available is not None and available < switch.DEFAULT_MIN_MEMORY_KIB:
                self.assertIsNotNone(issue)
        with unittest.mock.patch.dict(os.environ, {"ECOSYSTEM_SWITCH_MIN_MEMORY_KIB": str(2**62)}, clear=False):
            # Raising above the default IS honoured (the safe direction): this host cannot
            # possibly have 2**62 KiB free, so the gate must refuse.
            self.assertIsNotNone(switch.memory_gate_issue())

    def test_rollback_of_a_unit_restart_txn_restores_the_service_on_the_old_root(self):
        # Major finding: rollback used to reverse ops in plain ledger order, so a service
        # txn's unit-restart was reversed *before* its link, restarting the unit while
        # current/<id> still pointed at the new root -- the health probe's "from" was also the
        # pre-restart MainPID, not a root path, so it could never have matched anyway. After a
        # rollback, /proc/<MainPID>/exe for the (re-)restarted unit must resolve under the OLD
        # root, and current/svc must point there too.
        self.write_svc_spec()
        self.relink("svc")
        digest = self.plan_sha("svc", self.root_v2, "R1")
        result = run(self.env, "apply", "svc", "--to-root", str(self.root_v2), "--receipt", "R1",
                     "--window", "default", "--plan-sha256", digest)
        self.assertEqual(result.returncode, 0, result.stderr)
        txn = json.loads(result.stdout)["txn"]

        rollback = run(self.env, "rollback", "--txn", txn)
        self.assertEqual(rollback.returncode, 0, rollback.stderr)
        self.assertEqual(json.loads(rollback.stdout).get("problems"), None)
        state = json.loads(run(self.env, "status", "--json").stdout)
        self.assertEqual(state["components"]["svc"]["current"], str(self.root_v1.resolve()))
        # The stub systemctl restarted the unit a second time (once forward, once on rollback);
        # the health probe inside that second restart must have compared against root_v1, not
        # against the forward entry's own MainPID string.
        restarts = [line for line in self.stub_log.read_text().splitlines() if line.strip()]
        self.assertEqual(len(restarts), 2, restarts)

    def test_a_restart_command_that_itself_fails_is_still_ledgered_and_reflected_in_rollback(self):
        # Major finding: op_unit_restart used to raise a plain SwitchError as soon as the
        # `systemctl ... restart` command itself failed (or its health probe rejected the
        # result) -- before cmd_apply's loop ever reached the ledger.append() for that step. A
        # real side effect (the restart command actually ran) therefore went completely
        # unrecorded: rollback_txn's reverse-order pass found no unit-restart entry for this txn
        # and never tried to restart the unit again after reverting the link, leaving it running
        # whatever the failed restart left behind while the ledger said "rolled_back". The stub
        # systemctl has always supported STUB_DENY_RESTART (it denies exactly the named unit);
        # this is the first test that actually sets it.
        self.write_svc_spec()
        self.relink("svc")
        digest = self.plan_sha("svc", self.root_v2, "R1")
        env = {**self.env, "STUB_DENY_RESTART": "svc.service"}
        result = run(env, "apply", "svc", "--to-root", str(self.root_v2), "--receipt", "R1",
                     "--window", "default", "--plan-sha256", digest)
        self.assertNotEqual(result.returncode, 0)
        combined = (result.stderr + result.stdout).lower()
        self.assertIn("rolled back", combined)

        # The link step (ledgered before the unit-restart step ran) must still have been
        # reverted: this is the primary safety property even when the unit itself cannot be
        # restarted again (systemctl denying it outright).
        state = json.loads(run(self.env, "status", "--json").stdout)
        self.assertEqual(state["components"]["svc"]["current"], str(self.root_v1.resolve()))
        self.assertEqual(os.path.realpath(self.root / "bin" / "svc"), os.path.realpath(self.root_v1 / "bin" / "svc"))

        # The failed restart attempt is exactly what rollback_txn needs to find in order to even
        # try restarting the unit again; before the fix it was never ledgered at all.
        ledger_entries = switch.Ledger(self.root).all()
        self.assertTrue(any(e["op"] == "unit-restart" and e["surface"] == "svc.service" for e in ledger_entries),
                        "the failed restart attempt must still be ledgered so rollback can find it")
        # STUB_DENY_RESTART still applies during the rollback's own re-restart attempt, so that
        # second attempt fails too -- and must be surfaced as a reported problem, never silently
        # dropped.
        self.assertTrue(any(e["op"] == "rollback:unit-restart-failed" for e in ledger_entries),
                        "the rollback's own re-restart attempt (also denied) must be recorded, not skipped")
        self.assertIn("svc.service", combined)

        # The txn must not be left in_progress: apply's own automatic rollback already closed it
        # out (as "rolled_back"), even though the unit itself could not be brought back up.
        recover_result = run(self.env, "recover")
        self.assertEqual(recover_result.returncode, 0, recover_result.stderr)
        self.assertEqual(json.loads(recover_result.stdout)["recovered_txns"], [])


@REQUIRES_PROCFS
class UnitRestartTimeoutTests(unittest.TestCase):
    """Minor finding: a systemctl restart (or the post-restart status show) that exceeds
    run_captured's 60s timeout raised subprocess.TimeoutExpired, which is not a SwitchError --
    cmd_apply's step loop only catches UnitRestartAttempted/SwitchError, so it used to escape as
    an uncaught traceback and skip both this step's ledger entry and the automatic rollback.
    Exercised by mocking run_captured directly (no real 60s wait, no real systemctl).
    op_unit_restart itself reads /proc/meminfo first (memory_gate_issue): gated the same as
    UnitRestartTests (whole class, matching that class's own comment on why: no macOS
    equivalent to fake, so skip the platform-specific class rather than special-casing each
    assertion) rather than only its own two op_unit_restart-calling tests, even though the third
    (main()'s generic safety net) does not itself touch procfs."""

    def test_a_restart_command_timeout_is_reported_as_unit_restart_attempted_not_a_bare_timeout(self):
        def fake_run_captured(argv, **_kwargs):
            if argv[-2:] == ["restart", "svc.service"]:
                raise subprocess.TimeoutExpired(cmd=argv, timeout=60)
            return subprocess.CompletedProcess(argv, 0, stdout="1111\n", stderr="")
        with unittest.mock.patch.object(switch, "run_captured", side_effect=fake_run_captured):
            with self.assertRaises(switch.UnitRestartAttempted) as ctx:
                switch.op_unit_restart("svc.service", window_component_ok=True, expected_root="/nonexistent")
        self.assertIn("timed out", str(ctx.exception))
        self.assertIsInstance(ctx.exception.fields, dict)

    def test_a_post_restart_status_check_timeout_is_reported_as_unit_restart_attempted(self):
        show_calls = []

        def fake_run_captured(argv, **_kwargs):
            if argv[-2:] == ["restart", "svc.service"]:
                return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")
            if "show" in argv:
                show_calls.append(argv)
                if len(show_calls) == 1:  # the pre-restart MainPID probe succeeds normally
                    return subprocess.CompletedProcess(argv, 0, stdout="1111\n", stderr="")
                raise subprocess.TimeoutExpired(cmd=argv, timeout=60)  # the post-restart one hangs
            return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")
        with unittest.mock.patch.object(switch, "run_captured", side_effect=fake_run_captured):
            with self.assertRaises(switch.UnitRestartAttempted) as ctx:
                switch.op_unit_restart("svc.service", window_component_ok=True, expected_root="/nonexistent")
        self.assertIn("post-restart", str(ctx.exception))
        self.assertIn("timed out", str(ctx.exception))

    def test_main_reports_an_uncaught_subprocess_timeout_instead_of_a_bare_traceback(self):
        # Defense-in-depth safety net in main(), beyond op_unit_restart's own two catches above.
        with unittest.mock.patch.object(switch, "cmd_status",
                                        side_effect=subprocess.TimeoutExpired(cmd=["x"], timeout=1)):
            code = switch.main(["status"])
        self.assertEqual(code, 1)


class LockTests(SwitchFixture):
    def test_concurrent_apply_is_refused_with_75(self):
        self.root_v1 = self.make_tool_root("foo-1.0.0", "v1")
        self.link_entrypoint("foo", self.root_v1 / "bin" / "foo")
        self.write_components({"foo": {
            "version": "1.0.0", "kind": "tarball", "root_name": "foo-1.0.0", "current_link": "current/foo",
            "entrypoints": [{"bin": "bin/foo", "in_root": "bin/foo"}], "surfaces": [], "state_dirs": [],
            "window": "default", "rollback_class": "safe",
        }})
        (self.root / "switch").mkdir(exist_ok=True)
        lock_path = self.root / "switch" / "switch.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        handle = open(lock_path, "a+")
        try:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            result = run(self.env, "adopt", "--relink")
            self.assertEqual(result.returncode, 75, result.stderr)
        finally:
            handle.close()

    def test_lock_is_released_after_a_successful_operation(self):
        self.root_v1 = self.make_tool_root("foo-1.0.0", "v1")
        self.link_entrypoint("foo", self.root_v1 / "bin" / "foo")
        self.write_components({"foo": {
            "version": "1.0.0", "kind": "tarball", "root_name": "foo-1.0.0", "current_link": "current/foo",
            "entrypoints": [{"bin": "bin/foo", "in_root": "bin/foo"}], "surfaces": [], "state_dirs": [],
            "window": "default", "rollback_class": "safe",
        }})
        self.relink("foo")
        second = run(self.env, "status", "--json")
        self.assertEqual(second.returncode, 0)

    def test_concurrent_apply_is_also_refused_with_75(self):
        # test_concurrent_apply_is_refused_with_75 above actually exercises adopt --relink; this
        # covers the tool's other mutating command (apply) taking the same lock.
        self.root_v1 = self.make_tool_root("foo-1.0.0", "v1")
        self.root_v2 = self.make_tool_root("foo-2.0.0", "v2")
        self.link_entrypoint("foo", self.root_v1 / "bin" / "foo")
        self.write_components({"foo": {
            "version": "1.0.0", "kind": "tarball", "root_name": "foo-1.0.0", "current_link": "current/foo",
            "entrypoints": [{"bin": "bin/foo", "in_root": "bin/foo"}], "surfaces": [], "state_dirs": [],
            "window": "default", "rollback_class": "safe",
        }})
        self.relink("foo")
        self.write_window("default", allowed=("foo",), open_now=True)
        digest = run(self.env, "plan", "foo", "--to-root", str(self.root_v2), "--receipt", "R1")
        digest = json.loads(digest.stdout)["plan_sha256"]
        lock_path = self.root / "switch" / "switch.lock"
        handle = open(lock_path, "a+")
        try:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            result = run(self.env, "apply", "foo", "--to-root", str(self.root_v2), "--receipt", "R1",
                        "--window", "default", "--plan-sha256", digest)
            self.assertEqual(result.returncode, 75, result.stderr)
        finally:
            handle.close()

    def test_bootstrap_lock_busy_is_also_refused_with_75(self):
        # switch_locks also takes bootstrap.lock (the same lock adoption/bootstrap-linux.sh
        # itself holds while installing), so a switch operation never interleaves with a bootstrap
        # run; this exercises that second lock specifically, not just the tool's own switch.lock.
        self.root_v1 = self.make_tool_root("foo-1.0.0", "v1")
        self.link_entrypoint("foo", self.root_v1 / "bin" / "foo")
        self.write_components({"foo": {
            "version": "1.0.0", "kind": "tarball", "root_name": "foo-1.0.0", "current_link": "current/foo",
            "entrypoints": [{"bin": "bin/foo", "in_root": "bin/foo"}], "surfaces": [], "state_dirs": [],
            "window": "default", "rollback_class": "safe",
        }})
        lock_path = self.root / "bootstrap.lock"
        handle = open(lock_path, "a+")
        try:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            result = run(self.env, "adopt", "--relink")
            self.assertEqual(result.returncode, 75, result.stderr)
        finally:
            handle.close()


class PruneTests(SwitchFixture):
    def test_referenced_root_is_not_a_candidate_and_unreferenced_one_is(self):
        active = self.make_tool_root("foo-2.0.0", "v2")
        stale = self.make_tool_root("foo-1.0.0", "v1")
        self.link_entrypoint("foo", active / "bin" / "foo")
        self.write_components({"foo": {
            "version": "2.0.0", "kind": "tarball", "root_name": "foo-2.0.0", "current_link": "current/foo",
            "entrypoints": [{"bin": "bin/foo", "in_root": "bin/foo"}], "surfaces": [], "state_dirs": [],
            "window": "default", "rollback_class": "safe",
        }})
        self.relink("foo")
        listing = json.loads(run(self.env, "prune", "--list").stdout)
        paths = {c["path"]: c["eligible"] for c in listing["candidates"]}
        self.assertEqual(paths.get(str(stale)), True)
        self.assertNotIn(str(active), paths)

    def test_wrapper_script_text_reference_blocks_a_prune_candidate(self):
        # Previously-unresolved finding: a wrapper script (e.g. ~/codex-ecosystem/bin/
        # gitleaks-guarded) that hard-codes a tools/<root_name> path as plain text, with no bin/
        # symlink, unit file or PATH entry naming it, used to be entirely invisible to prune --
        # --apply would delete a root a live wrapper still depends on.
        active = self.make_tool_root("foo-2.0.0", "v2")
        stale = self.make_tool_root("foo-1.0.0", "v1")
        self.link_entrypoint("foo", active / "bin" / "foo")
        self.write_components({"foo": {
            "version": "2.0.0", "kind": "tarball", "root_name": "foo-2.0.0", "current_link": "current/foo",
            "entrypoints": [{"bin": "bin/foo", "in_root": "bin/foo"}], "surfaces": [], "state_dirs": [],
            "window": "default", "rollback_class": "safe",
        }})
        self.relink("foo")
        wrapper_dir = Path(self.tmp.name) / "wrappers"
        wrapper_dir.mkdir()
        wrapper = wrapper_dir / "foo-guarded"
        wrapper.write_text(f"#!/bin/sh\nexec {stale}/bin/foo \"$@\"\n")
        wrapper.chmod(0o755)
        env = {**self.env, "ECOSYSTEM_SWITCH_WRAPPER_DIRS": str(wrapper_dir)}
        listing = json.loads(run(env, "prune", "--list").stdout)
        match = next(c for c in listing["candidates"] if c["path"] == str(stale))
        self.assertFalse(match["eligible"])
        self.assertTrue(any("wrapper script" in reason and str(wrapper) in reason for reason in match["blocked_by"]),
                        match["blocked_by"])
        # --apply must also refuse it, not just --list report it.
        result = run(env, "prune", "--apply", str(stale), "--reason", "test")
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(stale.exists())

    def test_apply_removes_an_eligible_root_and_records_a_reason(self):
        active = self.make_tool_root("foo-2.0.0", "v2")
        stale = self.make_tool_root("foo-1.0.0", "v1")
        self.link_entrypoint("foo", active / "bin" / "foo")
        self.write_components({"foo": {
            "version": "2.0.0", "kind": "tarball", "root_name": "foo-2.0.0", "current_link": "current/foo",
            "entrypoints": [{"bin": "bin/foo", "in_root": "bin/foo"}], "surfaces": [], "state_dirs": [],
            "window": "default", "rollback_class": "safe",
        }})
        self.relink("foo")
        result = run(self.env, "prune", "--apply", str(stale), "--reason", "superseded by 2.0.0")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(stale.exists())
        ledger_entries = switch.Ledger(self.root).all()
        prune_entries = [e for e in ledger_entries if e["op"] == "prune"]
        self.assertEqual(len(prune_entries), 1)
        self.assertEqual(prune_entries[0]["to"], "superseded by 2.0.0")

    def test_apply_without_reason_is_refused(self):
        stale = self.make_tool_root("foo-1.0.0", "v1")
        result = run(self.env, "prune", "--apply", str(stale))
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(stale.exists())

    def test_the_rollback_target_of_an_unconfirmed_txn_is_not_a_prune_candidate(self):
        # Major finding: prune must not remove the previous root of a txn that has not yet been
        # confirmed or rolled back -- a later `confirm`-or-revert still needs it.
        old_root = self.make_tool_root("foo-1.0.0", "v1")
        new_root = self.make_tool_root("foo-2.0.0", "v2")
        self.link_entrypoint("foo", old_root / "bin" / "foo")
        self.write_components({"foo": {
            "version": "1.0.0", "kind": "tarball", "root_name": "foo-1.0.0", "current_link": "current/foo",
            "entrypoints": [{"bin": "bin/foo", "in_root": "bin/foo"}], "surfaces": [], "state_dirs": [],
            "window": "default", "rollback_class": "safe",
        }})
        self.relink("foo")
        self.write_window("default", allowed=("foo",), open_now=True)
        self.write_receipt("R1", "foo", "2.0.0")
        digest = self.plan_sha("foo", new_root, "R1")
        # No --confirm-within here (this fixture does not stub systemd-run, and must not create a
        # real host timer): a plain apply's txn reaches status "applied" immediately, and its
        # previous root remains a valid `rollback foo` target for as long as that txn is not
        # itself rolled back -- so it must stay excluded from pruning too, not only a txn still
        # literally "pending_confirmation".
        applied = run(self.env, "apply", "foo", "--to-root", str(new_root), "--receipt", "R1",
                      "--window", "default", "--plan-sha256", digest)
        self.assertEqual(applied.returncode, 0, applied.stderr)
        listing = json.loads(run(self.env, "prune", "--list").stdout)
        paths = {c["path"]: c["eligible"] for c in listing["candidates"]}
        self.assertNotIn(str(old_root), paths, "a live rollback target must not even be listed as a candidate")


class WriteInstalledVersionsTests(SwitchFixture):
    def test_writes_a_report_from_switch_state(self):
        root_v1 = self.make_tool_root("foo-1.0.0", "v1")
        self.link_entrypoint("foo", root_v1 / "bin" / "foo")
        self.write_components({"foo": {
            "version": "1.0.0", "kind": "tarball", "root_name": "foo-1.0.0", "current_link": "current/foo",
            "entrypoints": [{"bin": "bin/foo", "in_root": "bin/foo"}], "surfaces": [], "state_dirs": [],
            "window": "default", "rollback_class": "safe",
        }})
        self.relink("foo")
        result = run(self.env, "write-installed-versions")
        self.assertEqual(result.returncode, 0, result.stderr)
        report = Path(result.stdout.strip())
        self.assertTrue(report.is_file())
        self.assertIn("foo", report.read_text())
        self.assertIn(str(root_v1.resolve()), report.read_text())

    def test_a_pre_existing_file_is_backed_up_before_being_overwritten(self):
        # The real installed-versions.txt is a hand-maintained multi-tool --version log (git,
        # node, gh, ...); this command must never silently destroy it with no way back.
        destination = self.root / "installed-versions.txt"
        destination.write_text("Verified executable versions at 2026-09-21T20:22:14Z\n-- git --\ngit version 2.99\n")
        result = run(self.env, "write-installed-versions")
        self.assertEqual(result.returncode, 0, result.stderr)
        backups = list((self.root / "switch" / "backups").glob("write-installed-versions-*/installed-versions.txt.orig"))
        self.assertEqual(len(backups), 1, "the previous report must be preserved somewhere recoverable")
        self.assertIn("git version 2.99", backups[0].read_text())


class OperationUnitTests(unittest.TestCase):
    """Direct tests of the lower-level operation functions this track's shipped pins-v2
    entries have no populated surfaces[] to drive end to end yet (see module docstring)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_op_text_replace_backs_up_and_validates_json(self):
        target = self.root / "config.json"
        target.write_text(json.dumps({"path": "/old/root"}))
        backup_dir = self.root / "backups"
        fields, inverse = switch.op_text_replace(self.root, "config.json", "/old/root", "/new/root",
                                                 backup_dir=backup_dir)
        self.assertEqual(json.loads(target.read_text())["path"], "/new/root")
        self.assertTrue(Path(fields["backup"]).is_file())
        self.assertEqual(json.loads(Path(fields["backup"]).read_text())["path"], "/old/root")
        self.assertEqual(inverse["old"], "/new/root")
        self.assertEqual(inverse["new"], "/old/root")

    def test_op_text_replace_refuses_wrong_occurrence_count(self):
        target = self.root / "unit.txt"
        target.write_text("root=/a\nroot=/a\n")
        with self.assertRaises(switch.SwitchError):
            switch.op_text_replace(self.root, "unit.txt", "/a", "/b", backup_dir=self.root / "backups",
                                   expected_count=1)
        self.assertEqual(target.read_text(), "root=/a\nroot=/a\n")

    def test_op_text_replace_refuses_frozen_path(self):
        (self.root / "frozen").mkdir()
        target = self.root / "frozen" / "unit.txt"
        target.write_text("root=/a\n")
        with self.assertRaises(switch.SwitchError):
            switch.op_text_replace(self.root, "frozen/unit.txt", "/a", "/b", backup_dir=self.root / "backups")

    def test_op_text_replace_refuses_a_parent_symlink_hop_into_frozen(self):
        (self.root / "frozen" / "real").mkdir(parents=True)
        target_in_frozen = self.root / "frozen" / "real" / "unit.txt"
        target_in_frozen.write_text("root=/a\n")
        (self.root / "alias").symlink_to(self.root / "frozen" / "real")
        # "alias/unit.txt" never contains the literal text "/frozen/", but it resolves through a
        # symlink into frozen/real/ -- the frozen check must catch that too.
        with self.assertRaises(switch.SwitchError):
            switch.op_text_replace(self.root, "alias/unit.txt", "/a", "/b", backup_dir=self.root / "backups")
        self.assertEqual(target_in_frozen.read_text(), "root=/a\n")

    def test_op_text_replace_preserves_the_original_exec_bit(self):
        target = self.root / "gitleaks-guarded"
        target.write_text("#!/bin/sh\nexec /old/root/gitleaks \"$@\"\n")
        target.chmod(0o755)
        switch.op_text_replace(self.root, "gitleaks-guarded", "/old/root", "/new/root", backup_dir=self.root / "backups")
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o755, "relinking a wrapper must not drop its exec bit")

    def test_op_text_replace_checks_the_expected_pre_image_sha256(self):
        target = self.root / "unit.txt"
        target.write_text("root=/a\n")
        wrong_sha = "0" * 64
        with self.assertRaises(switch.SwitchError):
            switch.op_text_replace(self.root, "unit.txt", "/a", "/b", backup_dir=self.root / "backups",
                                   expected_pre_sha256=wrong_sha)
        self.assertEqual(target.read_text(), "root=/a\n")
        right_sha = switch.sha256_bytes(target.read_bytes())
        switch.op_text_replace(self.root, "unit.txt", "/a", "/b", backup_dir=self.root / "backups",
                               expected_pre_sha256=right_sha)
        self.assertEqual(target.read_text(), "root=/b\n")

    def test_op_text_replace_refuses_invalid_toml_after_replacement(self):
        try:
            import tomllib  # noqa: F401
        except ImportError:
            self.skipTest("tomllib requires Python 3.11+")
        target = self.root / "config.toml"
        target.write_text('[mcp]\nroot = "/old/root"\n')
        # A replacement that still parses as TOML must succeed.
        switch.op_text_replace(self.root, "config.toml", "/old/root", "/new/root", backup_dir=self.root / "backups")
        self.assertIn('root = "/new/root"', target.read_text())
        # A replacement that breaks TOML syntax must be refused (raises, though not necessarily
        # as SwitchError -- see op_text_replace's docstring note on this being unwrapped, the
        # same as the pre-existing JSON re-parse check).
        target.write_text('[mcp]\nversion = "1.0.0"\n')
        with self.assertRaises(Exception):
            # Removing the closing quote leaves an unterminated basic string: invalid TOML.
            switch.op_text_replace(self.root, "config.toml", '"1.0.0"', '"1.0.0', backup_dir=self.root / "backups")

    def test_op_file_write_backs_up_existing_and_removes_on_inverse_when_new(self):
        fields, inverse = switch.op_file_write(self.root, "new-file.txt", b"hello", backup_dir=self.root / "backups")
        self.assertIsNone(fields["backup"])
        self.assertTrue(inverse["remove_if_no_backup"])
        target = self.root / "existing.txt"
        target.write_bytes(b"old")
        fields2, inverse2 = switch.op_file_write(self.root, "existing.txt", b"new", backup_dir=self.root / "backups")
        self.assertIsNotNone(fields2["backup"])
        self.assertEqual(Path(fields2["backup"]).read_bytes(), b"old")

    def test_op_native_cli_records_before_after_and_propagates_failure(self):
        # op_native_cli only ever runs claude mcp/plugin or codex mcp (a fixed policy, not a
        # caller-supplied allowlist), so the stub executables here are literally named "claude"
        # to pass that check while still exercising the generic before/after/failure mechanics.
        ok_dir = self.root / "ok"
        ok_dir.mkdir()
        claude_ok = ok_dir / "claude"
        claude_ok.write_text(f"#!{sys.executable}\nprint('ok')\n")
        claude_ok.chmod(0o755)
        fields, inverse = switch.op_native_cli([str(claude_ok), "mcp", "list"], None)
        self.assertIsNotNone(fields["to"])

        fail_dir = self.root / "fail"
        fail_dir.mkdir()
        claude_fail = fail_dir / "claude"
        claude_fail.write_text(f"#!{sys.executable}\nimport sys; sys.exit(3)\n")
        claude_fail.chmod(0o755)
        with self.assertRaises(switch.SwitchError):
            switch.op_native_cli([str(claude_fail), "mcp", "list"], None)

    def test_op_native_cli_refuses_argv_outside_the_fixed_policy(self):
        with self.assertRaises(switch.SwitchError):
            switch.op_native_cli([sys.executable, "-c", "print('should never run')"], None)

    def test_op_data_backup_and_restore_round_trip(self):
        source = self.root / "state"
        source.mkdir()
        (source / "a.txt").write_text("A")
        (source / "b.txt").write_text("B")
        backup_dir = self.root / "backups"
        fields, inverse = switch.op_data_backup(self.root, "state", backup_dir=backup_dir)
        (source / "a.txt").write_text("CHANGED")
        (source / "c.txt").write_text("NEW")
        switch.op_data_restore(self.root, inverse["surface"], inverse["restore_from_backup"])
        self.assertEqual((source / "a.txt").read_text(), "A")
        self.assertFalse((source / "c.txt").exists())

    def test_op_data_backup_expands_a_tilde_state_dir_path(self):
        # Minor finding: a state_dirs[] path like adoption/pins-linux-x86_64.json's own pending
        # "~/.cache/qmd" or "~/.local/state/ai-memory" entries used to be treated as a literal
        # relative path under ECO_INSTALL_ROOT (root/"~/.cache/qmd", which never exists) instead
        # of this user's real home directory.
        fake_home = self.root / "fake-home"
        (fake_home / ".cache" / "qmd").mkdir(parents=True)
        (fake_home / ".cache" / "qmd" / "index.db").write_text("data")
        with unittest.mock.patch.dict(os.environ, {"HOME": str(fake_home)}, clear=False):
            fields, inverse = switch.op_data_backup(self.root, "~/.cache/qmd", backup_dir=self.root / "backups")
        self.assertTrue((Path(fields["backup"]) / "index.db").is_file())
        self.assertEqual((Path(fields["backup"]) / "index.db").read_text(), "data")

    def test_op_data_backup_refuses_a_non_directory_source_instead_of_recording_an_empty_backup(self):
        with self.assertRaises(switch.SwitchError):
            switch.op_data_backup(self.root, "does-not-exist", backup_dir=self.root / "backups")
        (self.root / "not-a-dir.txt").write_text("x")
        with self.assertRaises(switch.SwitchError):
            switch.op_data_backup(self.root, "not-a-dir.txt", backup_dir=self.root / "backups")

    def test_op_file_write_preserves_the_original_exec_bit_on_overwrite(self):
        target = self.root / "wrapper.sh"
        target.write_text("#!/bin/sh\necho old\n")
        target.chmod(0o755)
        switch.op_file_write(self.root, "wrapper.sh", b"#!/bin/sh\necho new\n", backup_dir=self.root / "backups")
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o755)

    def test_receipt_gate_issue_matches_the_documented_rule(self):
        base = {
            "status": "passed",
            "identity": {"component_id": "foo", "version": "2.0.0"},
            "tiers": [{"tier": "T0", "result": "passed"}, {"tier": "T1", "result": "unavailable", "unavailable_reason": "n/a"},
                      {"tier": "T2", "result": "passed"}, {"tier": "T4", "result": "passed"}],
        }
        self.assertIsNone(switch.receipt_gate_issue(base, "foo", "2.0.0"))
        self.assertIsNotNone(switch.receipt_gate_issue(None, "foo", "2.0.0"))
        self.assertIsNotNone(switch.receipt_gate_issue({**base, "status": "failed"}, "foo", "2.0.0"))
        self.assertIsNotNone(switch.receipt_gate_issue(base, "foo", "3.0.0"))
        no_t2 = {**base, "tiers": [t for t in base["tiers"] if t["tier"] != "T2"]}
        self.assertIsNotNone(switch.receipt_gate_issue(no_t2, "foo", "2.0.0"))
        t1_failed = {**base, "tiers": [t if t["tier"] != "T1" else {"tier": "T1", "result": "failed"} for t in base["tiers"]]}
        self.assertIsNotNone(switch.receipt_gate_issue(t1_failed, "foo", "2.0.0"))

    def test_receipt_gate_checks_install_root_only_when_root_and_to_root_are_given(self):
        base = {
            "status": "passed",
            "identity": {"component_id": "foo", "version": "2.0.0"},
            "install": {"root": "${STACK_HOME}/tools/foo-2.0.0"},
            "tiers": [{"tier": "T0", "result": "passed"}, {"tier": "T1", "result": "unavailable", "unavailable_reason": "n/a"},
                      {"tier": "T2", "result": "passed"}, {"tier": "T4", "result": "passed"}],
        }
        # Without root/to_root (a direct unit test of the tier rule in isolation): unaffected.
        self.assertIsNone(switch.receipt_gate_issue(base, "foo", "2.0.0"))
        # With root/to_root matching the resolved ${STACK_HOME} placeholder: still fine.
        self.assertIsNone(switch.receipt_gate_issue(base, "foo", "2.0.0", root=self.root, to_root=str(self.root / "tools" / "foo-2.0.0")))
        # A receipt recorded for a *different* real root (e.g. a stale -r20260101 root, or a
        # different component entirely) must not authorize switching to this one.
        issue = switch.receipt_gate_issue(base, "foo", "2.0.0", root=self.root, to_root=str(self.root / "tools" / "foo-2.0.0-r20260101"))
        self.assertIsNotNone(issue)
        self.assertIn("install.root", issue)

    def test_receipt_gate_fails_closed_when_install_root_is_missing(self):
        # Minor finding: a receipt with no (or a non-string) install.root used to skip the root
        # binding check entirely once root/to_root were given, silently authorizing any --to-root
        # whose basename suffix matched the version.
        no_install_root = {
            "status": "passed", "identity": {"component_id": "foo", "version": "2.0.0"}, "install": {},
            "tiers": [{"tier": "T0", "result": "passed"}, {"tier": "T1", "result": "unavailable", "unavailable_reason": "n/a"},
                      {"tier": "T2", "result": "passed"}, {"tier": "T4", "result": "passed"}],
        }
        # Without root/to_root, still unaffected (the tier-rule-in-isolation contract).
        self.assertIsNone(switch.receipt_gate_issue(no_install_root, "foo", "2.0.0"))
        issue = switch.receipt_gate_issue(no_install_root, "foo", "2.0.0", root=self.root,
                                          to_root=str(self.root / "tools" / "foo-2.0.0"))
        self.assertIsNotNone(issue)
        self.assertIn("install.root", issue)

    def test_receipt_gate_version_parsing_handles_dated_and_wave_suffixed_roots(self):
        # The version ecosystem-switch derives from --to-root is the full suffix after
        # "<component>-", not just the text after the last hyphen: a -rDATE or -wN suffixed root
        # (this rollout's own tools/rtk-0.50.0-r20260925, ai-memory-2.3.2-w2 convention) must
        # keep its whole version string, and a receipt for one install must not therefore
        # authorize any other root that happens to end in the same last-hyphen segment.
        base = {
            "status": "passed", "identity": {"component_id": "rtk", "version": "0.50.0-r20260925"},
            "tiers": [{"tier": "T0", "result": "passed"}, {"tier": "T1", "result": "unavailable", "unavailable_reason": "n/a"},
                      {"tier": "T2", "result": "passed"}, {"tier": "T4", "result": "passed"}],
        }
        self.assertIsNone(switch.receipt_gate_issue(base, "rtk", "0.50.0-r20260925"))
        # A receipt for a *different* rtk build that happens to share the same date suffix (e.g.
        # a same-day rebuild under a different base version) must not match.
        self.assertIsNotNone(switch.receipt_gate_issue(base, "rtk", "0.49.0-r20260925"))


class LedgerUnitTests(unittest.TestCase):
    def test_append_chains_hashes_and_all_reads_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = switch.Ledger(root)
            first = ledger.append(txn="t1", op="link", component="foo", surface="bin/foo", to="a")
            second = ledger.append(txn="t1", op="link", component="foo", surface="bin/foo", to="b")
            self.assertEqual(first["prev_hash"], switch.GENESIS_HASH)
            self.assertEqual(second["prev_hash"], first["hash"])
            self.assertEqual(len(ledger.all()), 2)
            self.assertEqual(ledger.verify_chain(), [])
            self.assertEqual(stat.S_IMODE((root / "switch" / "ledger.jsonl").stat().st_mode), 0o600)


if __name__ == "__main__":
    unittest.main()
