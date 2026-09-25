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
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SWITCH_BIN = ROOT / "adoption" / "tools" / "ecosystem-switch"

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
        self.root = Path(self.tmp.name) / "eco"
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
            "install": {"class": "tarball", "root": "${STACK_HOME}/tools/x", "marker_sha256": "0" * 64,
                       "argv": ["true"], "private_env_names": []},
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

    def test_relink_skips_a_component_with_no_switch_managed_root(self):
        self.write_components({"native-thing": {
            "version": "1.0.0", "kind": "native", "root_name": None, "current_link": None,
            "entrypoints": [], "surfaces": [], "state_dirs": [], "window": "default",
            "rollback_class": "not_applicable",
        }})
        result = self.relink("native-thing")
        self.assertIn("skipped", json.loads(result.stdout)["results"]["native-thing"])

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

    def write_bar_spec(self, surface_path, expected_count=2):
        self.write_components({"bar": {
            "version": "1.0.0", "kind": "tarball", "root_name": "bar-1.0.0", "current_link": "current/bar",
            "entrypoints": [{"bin": "bin/bar", "in_root": "bin/bar"}],
            "surfaces": [{"kind": "text-replace", "path": str(surface_path), "expected_count": expected_count}],
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

    def test_reapply_after_rollback_does_not_false_positive_drift(self):
        self.write_receipt("R1", "foo", "2.0.0")
        self.apply("foo", self.root_v2, "R1")
        run(self.env, "rollback", "foo")
        result = self.apply("foo", self.root_v2, "R1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.run_entrypoint(), "v2")

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

    def test_relative_to_root_is_refused(self):
        self.write_receipt("R1", "foo", "2.0.0")
        result = run(self.env, "apply", "foo", "--to-root", "tools/foo-2.0.0", "--receipt", "R1",
                     "--window", "default", "--plan-sha256", "0" * 64)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("absolute", result.stderr)

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
        self.assertIn("rolled back", result.stderr.lower() + result.stdout.lower() or "rolled back")
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


class UnitRestartTests(SwitchFixture):
    STUB_SYSTEMCTL = textwrap.dedent("""\
        #!/usr/bin/env python3
        import sys, os
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
            print(os.environ.get("STUB_MAIN_PID", str(os.getpid())))
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
        # The health probe reads /proc/<MainPID>/exe and requires it to resolve *inside* the new
        # root; os.getpid() would only ever resolve to this test's own /usr/bin/python3, so a
        # real, separate copy of the interpreter is placed inside root_v2 and run as a genuine
        # long-lived process -- exec through a symlink still reports the symlink's real target,
        # not a path inside root_v2, so this needs an actual independent copy of the binary.
        daemon_bin = self.root_v2 / "bin" / "svc-daemon"
        shutil.copy2(sys.executable, daemon_bin)
        daemon_bin.chmod(0o755)
        self.daemon = subprocess.Popen([str(daemon_bin), "-c", "import time; time.sleep(60)"])
        self.addCleanup(self._stop_daemon)
        self.env = {**self.env, "ECOSYSTEM_SWITCH_SYSTEMCTL": f"{sys.executable} {stub_path}",
                   "STUB_LOG": str(self.stub_log), "STUB_MAIN_PID": str(self.daemon.pid)}
        self.write_window("default", allowed=("svc",), open_now=True)
        self.write_receipt("R1", "svc", "2.0.0")

    def _stop_daemon(self):
        self.daemon.terminate()
        with contextlib.suppress(subprocess.TimeoutExpired):
            self.daemon.wait(timeout=5)

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

    def test_low_memory_refuses_the_restart(self):
        self.write_svc_spec()
        self.relink("svc")
        digest = self.plan_sha("svc", self.root_v2, "R1")
        env = {**self.env, "ECOSYSTEM_SWITCH_MIN_MEMORY_KIB": str(2**62)}
        result = run(env, "apply", "svc", "--to-root", str(self.root_v2), "--receipt", "R1",
                     "--window", "default", "--plan-sha256", digest)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("kib", result.stderr.lower())
        self.assertIn("model-loading", result.stderr.lower())


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
        fields, inverse = switch.op_native_cli([sys.executable, "-c", "print('ok')"], None)
        self.assertIsNotNone(fields["to"])
        with self.assertRaises(switch.SwitchError):
            switch.op_native_cli([sys.executable, "-c", "import sys; sys.exit(3)"], None)

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
