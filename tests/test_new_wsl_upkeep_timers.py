"""Source and native-parser checks; these do not activate host services."""
import os
import json
import hashlib
import datetime
import io
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
UNITS = ROOT / "adoption/templates/systemd"
DATA_SERVICE = "ecosystem-native-data.service"
DATA_TIMER = "ecosystem-native-data.timer"
GUARD_SERVICE = "disk-headroom-guard.service"
GUARD_TIMER = "disk-headroom-guard.timer"


class NativeUpkeepTimerTests(unittest.TestCase):
    def run_render(self, mutate=None, node_major=24, missing=None, wrong_pin=False):
        text = (UNITS / "upkeep-transfer.md").read_text().split("<!-- upkeep:render -->", 1)[1]
        code = re.findall(r"<<'PY'\n(.*?)\nPY", text, re.S)[0]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = root / "repo"
            repo.mkdir()
            # A tiny real Git fixture proves clean-pin gating without a network or host apply.
            for relative in ("observability/native-data/snapshot.py", "tools/maintenance/disk-headroom-guard.sh",
                             *("adoption/templates/systemd/" + x for x in
                               (DATA_SERVICE, DATA_TIMER, GUARD_SERVICE, GUARD_TIMER))):
                target = repo / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((ROOT / relative).read_bytes())
            git = ["git", "-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false",
                   "-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid", "-C", str(repo)]
            subprocess.run(git + ["init", "--quiet"], check=True, capture_output=True)
            subprocess.run(git + ["add", "."], check=True, capture_output=True)
            subprocess.run(git + ["commit", "--quiet", "-m", "fixture"], check=True, capture_output=True)
            approved = subprocess.check_output(git + ["rev-parse", "HEAD"], text=True).strip()
            node = root / "node"
            node.mkdir()
            binary = node / "node"
            binary.write_text(f"#!/bin/sh\nprintf 'v{node_major}.10.0\\n'\n")
            binary.chmod(0o755)
            native = root / "native"
            native.write_text("#!/bin/sh\nexit 0\n")
            native.chmod(0o755)
            for name in ("project", "data", "state"):
                (root / name).mkdir(mode=0o700)
            report = root / "report.json"
            report.write_text("{}\n")
            config = json.loads((ROOT / "observability/native-data/config.ns2604.example.json").read_text())
            config.update(token_report=str(report), project=str(root / "project"), rtk=str(native), state_dir=str(root / "state"))
            config["ai_memory"].update(binary=str(native), data_dir=str(root / "data"))
            config["qmd"]["binary"] = str(native)
            if mutate:
                mutate(config)
            if missing:
                (root / missing).unlink()
            path = root / "config.json"
            path.write_text(json.dumps(config))
            output = root / "rendered"
            env = {"PATH": os.environ["PATH"], "HOME": os.environ["HOME"], "LANG": "C",
                   "UPKEEP_APPROVED_SHA": "0" * 40 if wrong_pin else approved,
                   "XDG_CONFIG_HOME": str(root / "private-config"), "PYTHONDONTWRITEBYTECODE": "1"}
            result = subprocess.run(["python3", "-B", "-", str(repo), str(path), str(node), str(output)],
                                    input=code, env=env, capture_output=True, text=True, timeout=20)
            rendered = sorted(x.name for x in output.iterdir()) if output.exists() else []
        return result, rendered

    def test_runbook_rejects_config_for_the_prior_distribution(self):
        """Execute the real inline render gate; existing files alone are insufficient."""
        result, rendered = self.run_render(lambda c: c.update(loki_url="http://127.0.0.1:13100/loki/api/v1/push"))
        self.assertNotEqual(result.returncode, 0, "prior-distribution config was accepted")
        self.assertIn("Loki 21300", result.stderr)
        self.assertFalse(rendered)

    def test_render_accepts_pinned_destination_and_optional_qdrant(self):
        for selected in (False, True):
            def select(c):
                if selected:
                    c["qdrant"] = {"url": "http://127.0.0.1:21633", "collection": "fixture"}
            with self.subTest(selected=selected):
                result, rendered = self.run_render(select)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(rendered, sorted([DATA_SERVICE, DATA_TIMER, GUARD_SERVICE, GUARD_TIMER,
                                                  "disk-headroom-guard.sh", "native-data.json"]))

    def test_render_rejects_wrong_read_endpoints_node_missing_input_and_pin(self):
        cases = [
            ({"mutate": lambda c: c["ai_memory"].update(server_url="http://127.0.0.1:49374")}, "ai-memory 29374"),
            ({"mutate": lambda c: c.update(qdrant={"url": "http://127.0.0.1:26333", "collection": "fixture"})}, "Qdrant 21633"),
            ({"node_major": 20}, "Node 22"),
            ({"missing": "report.json"}, "token report"),
            ({"wrong_pin": True}, "approved clean checkout"),
        ]
        for kwargs, message in cases:
            with self.subTest(message=message):
                result, rendered = self.run_render(**kwargs)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message, result.stderr)
                self.assertFalse(rendered)

    def test_runbook_rollback_rejects_a_fresh_shell_without_a_manifest(self):
        text = (UNITS / "upkeep-transfer.md").read_text().split("<!-- upkeep:restore -->", 1)[1]
        code = re.search(r"```sh\n(.*?)```", text, re.S).group(1)
        with tempfile.TemporaryDirectory() as directory:
            binary = Path(directory) / "bin"
            binary.mkdir()
            calls = Path(directory) / "calls"
            for name in ("rtk", "systemctl", "rm", "cp"):
                p = binary / name
                p.write_text("#!/bin/sh\nprintf '%s\\n' invoked >> \"$FIXTURE_CALLS\"\nexit 0\n")
                p.chmod(0o755)
            env = {"PATH": str(binary) + ":/usr/bin:/bin", "HOME": os.environ["HOME"],
                   "FIXTURE_CALLS": str(calls)}
            result = subprocess.run(["bash"], input=code, env=env, capture_output=True, text=True, timeout=10)
            invoked = calls.exists()
        self.assertNotEqual(result.returncode, 0, "unset rollback was a false success")
        self.assertFalse(invoked, "rollback operated before validating its manifest")

    def run_restore(self, edit=False, corrupt=False, early=False, pending=False, deleted=False, rollback_pending=False):
        text = (UNITS / "upkeep-transfer.md").read_text().split("<!-- upkeep:restore -->", 1)[1]
        code = re.search(r"```sh\n(.*?)```", text, re.S).group(1)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            batch = root / "batch"
            batch.mkdir(mode=0o700)
            baseline = batch / "baseline"
            baseline.mkdir()
            config_root = root / "config"
            units = config_root / "systemd/user"
            units.mkdir(parents=True)
            runtime = root / "runtime"
            runtime.mkdir()
            binary = root / "bin"
            binary.mkdir()
            calls = root / "calls"
            (binary / "rtk").write_text('#!/bin/sh\n[ "$1" != proxy ] || shift\nexec "$@"\n')
            (binary / "date").write_text("#!/bin/sh\nprintf '202610060500\\n'\n")
            (binary / "systemctl").write_text(
                '#!/bin/sh\nprintf "%s\\n" "$*" >> "$FIXTURE_CALLS"\n'
                'case "$*" in\n'
                '  *Id,NeedDaemonReload*) printf "Id=untouched.service\\nNeedDaemonReload=no\\n" ;;\n'
                '  *LoadState*) printf "not-found\\n" ;;\n'
                '  *ActiveState*) printf "inactive\\n" ;;\n'
                'esac\n')
            for path in binary.iterdir():
                path.chmod(0o755)
            def identity(raw, mode):
                return {"kind": "file", "sha256": hashlib.sha256(raw).hexdigest(), "mode": mode}
            paths = []
            restored = units / GUARD_SERVICE
            restored.write_bytes(b"candidate\n")
            restored.chmod(0o600)
            backup = baseline / GUARD_SERVICE
            backup.write_bytes(b"operator baseline\n")
            backup.chmod(0o640)
            paths.append({"path": str(restored), "before": identity(backup.read_bytes(), 0o640),
                          "expected": identity(restored.read_bytes(), 0o600), "backup": str(backup),
                          "prepared": True, "phase": "rollback_copy_prepared" if rollback_pending else "install_prepared" if pending else "installed"})
            if pending or deleted or rollback_pending:
                restored.unlink()
            link_path = units / DATA_SERVICE
            link_path.write_bytes(b"candidate\n")
            link_path.chmod(0o600)
            link_backup = baseline / DATA_SERVICE
            link_backup.symlink_to("absent-original.service")
            paths.append({"path": str(link_path), "before": {"kind": "link", "target": "absent-original.service"},
                          "expected": identity(link_path.read_bytes(), 0o600), "backup": str(link_backup),
                          "prepared": True, "phase": "installed"})
            created = units / DATA_TIMER
            created.write_bytes(b"created\n")
            created.chmod(0o600)
            paths.append({"path": str(created), "before": {"kind": "absent"},
                          "expected": identity(created.read_bytes(), 0o600), "backup": str(baseline / DATA_TIMER),
                          "prepared": True, "phase": "installed"})
            unrelated = units / "operator-alias.service"
            unrelated.symlink_to("operator-owned-missing.service")
            if edit:
                restored.write_bytes(b"later operator edit\n")
            manifest = {"schema_version": 1, "approved_sha": "a" * 40, "home": os.environ["HOME"],
                        "batch": str(batch), "config_root": str(config_root), "runtime_root": str(runtime),
                        "ops": str(Path.home() / ".local/state/native-agent-stack/ops"), "paths": [] if early else paths,
                        "timers": {}, "timer_actions": {}}
            manifest_path = batch / "manifest.json"
            manifest_path.write_text("invalid-json" if corrupt else json.dumps(manifest))
            manifest_path.chmod(0o600)
            env = {"PATH": str(binary) + ":" + os.environ["PATH"], "HOME": os.environ["HOME"],
                   "LANG": "C", "UPKEEP_TRANSFER_DIR": str(batch), "FIXTURE_CALLS": str(calls),
                   "PYTHONDONTWRITEBYTECODE": "1"}
            result = subprocess.run(["bash"], input=code, env=env, capture_output=True, text=True, timeout=20)
            observations = {"regular": restored.read_bytes() if restored.is_file() else None,
                            "mode": restored.stat().st_mode & 0o777 if restored.is_file() else None,
                            "link": os.readlink(link_path) if link_path.is_symlink() else None,
                            "created_exists": created.exists(), "unrelated": os.readlink(unrelated),
                            "manager_calls": calls.read_text() if calls.exists() else ""}
        return result, observations

    def test_fresh_shell_restore_preserves_bytes_modes_dangling_links_and_unrelated_alias(self):
        result, observed = self.run_restore()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(observed["regular"], b"operator baseline\n")
        result, observed = self.run_restore(rollback_pending=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(observed["regular"], b"operator baseline\n")
        self.assertEqual(observed["mode"], 0o640)
        self.assertEqual(observed["link"], "absent-original.service")
        self.assertFalse(observed["created_exists"])
        self.assertEqual(observed["unrelated"], "operator-owned-missing.service")

    def test_rollback_rejects_corrupt_manifest_and_operator_edit_before_manager_calls(self):
        for kwargs in ({"corrupt": True}, {"edit": True}, {"deleted": True}):
            with self.subTest(kwargs=kwargs):
                result, observed = self.run_restore(**kwargs)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(observed["manager_calls"])
                self.assertTrue(observed["created_exists"])
                if kwargs.get("edit"):
                    self.assertEqual(observed["regular"], b"later operator edit\n")

    def test_partial_remove_install_is_recoverable_and_early_manifest_leaves_manager_untouched(self):
        result, observed = self.run_restore(pending=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(observed["regular"], b"operator baseline\n")
        result, observed = self.run_restore(early=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(observed["manager_calls"])
        self.assertEqual(observed["regular"], b"candidate\n")

    def run_green(self, bad_job=False, unchanged=False, wrong_marker=False, wrong_endpoint=False, crosses_window=False):
        text = (UNITS / "upkeep-transfer.md").read_text().split("<!-- upkeep:green -->", 1)[1]
        code = re.findall(r"<<'PY'\n(.*?)\nPY", text, re.S)[0]
        base = int(datetime.datetime(2026, 10, 6, 6, 0, tzinfo=datetime.timezone.utc).timestamp())
        class Clock(datetime.datetime):
            calls = 0
            @classmethod
            def now(cls, tz=None):
                cls.calls += 1
                if crosses_window and cls.calls > 1:
                    return cls(2026, 10, 6, 11, 0, tzinfo=tz)
                return cls.fromtimestamp(base, tz)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            batch = root / "batch"
            batch.mkdir()
            config_root = root / "config"
            state = root / "state"
            ops = root / "ops"
            config_path = config_root / "ecosystem-observability/native-data.json"
            config_path.parent.mkdir(parents=True)
            state.mkdir()
            ops.mkdir()
            config_path.write_text(json.dumps({"loki_url": "http://127.0.0.1:13100/loki/api/v1/push" if wrong_endpoint else "http://127.0.0.1:21300/loki/api/v1/push",
                "ai_memory": {"server_url": "http://127.0.0.1:29374"}, "state_dir": str(state), "qdrant": None}))
            (batch / "manifest.json").write_text(json.dumps({"config_root": str(config_root), "ops": str(ops), "paths": []}))
            csv = ops / "disk-headroom.csv"
            csv.write_text("utc,free_gib\n2026-10-06T05:59:00Z,634\n")
            calls = []
            ids = {GUARD_SERVICE: "a" * 32, DATA_SERVICE: "b" * 32}
            marker = {"entity_id": "snapshot", "record_kind": "snapshot", "observed_unix": base + 2.4,
                      "unknown_count": 3, "stale_count": 2}
            def output(argv, **kwargs):
                calls.append(argv)
                if argv[0] == "systemctl":
                    return "inactive\n" if "--property=ActiveState" in argv else "Result=success\nExecMainStatus=0\n"
                if "--output-fields=__CURSOR" in argv:
                    return '{"__CURSOR":"fixture-cursor"}\n'
                unit = next(x.split("=", 1)[1] for x in argv if x.startswith("--user-unit="))
                if "json" in argv:
                    return json.dumps({"MESSAGE_ID": "39f53479d3a045ac8e11786248231fbf", "USER_UNIT": unit,
                        "USER_INVOCATION_ID": ids[unit], "JOB_TYPE": "start", "JOB_RESULT": "failed" if bad_job else "done",
                        "__REALTIME_TIMESTAMP": str((base + (1 if unit == GUARD_SERVICE else 2)) * 1000000 + 500000)}) + "\n"
                self.assertIn("--invocation=" + ids[unit], argv)
                return json.dumps({"snapshot_sha256": hashlib.sha256((state / "snapshot.json").read_bytes()).hexdigest(),
                                   "observed_unix": marker["observed_unix"]}) + "\n"
            def run(argv, **kwargs):
                calls.append(argv)
                if "systemctl" in argv:
                    if argv[-1] == GUARD_SERVICE and not unchanged:
                        csv.write_text(csv.read_text() + "2026-10-06T06:00:01Z,634\n")
                    elif argv[-1] == DATA_SERVICE:
                        (state / "snapshot.json").write_text(json.dumps({"observed_unix": marker["observed_unix"],
                            "loki": {"http_status": 204, "error": None}, "rows": [marker]}))
                    return subprocess.CompletedProcess(argv, 0)
                self.assertEqual(argv[argv.index("--get") + 1], "http://127.0.0.1:21300/loki/api/v1/query_range")
                self.assertIn('query={service_name="agent-stack-native-data",record_kind="snapshot"}', argv)
                returned = dict(marker, observed_unix=base - 100) if wrong_marker else marker
                Path(argv[argv.index("--output") + 1]).write_text(json.dumps({"status": "success", "data": {
                    "resultType": "streams", "result": [{"stream": {"service_name": "agent-stack-native-data", "record_kind": "snapshot"},
                        "values": [[str((base + 2) * 1000000000 + 400000000), json.dumps(returned)]]}]}}))
                return subprocess.CompletedProcess(argv, 0, stdout="200", stderr="")
            error = None
            with mock.patch.object(subprocess, "check_output", side_effect=output), \
                 mock.patch.object(subprocess, "run", side_effect=run), \
                 mock.patch("time.time_ns", side_effect=[(base + 1) * 1000000000 + 100000000,
                     (base + 2) * 1000000000 + 100000000, (base + 3) * 1000000000]), \
                 mock.patch.object(datetime, "datetime", Clock), \
                 mock.patch("sys.argv", ["inline", str(batch)]), mock.patch("sys.stdout", io.StringIO()):
                try:
                    exec(compile(code, "native-green-runbook", "exec"), {})
                except SystemExit as exc:
                    error = str(exc)
            files = sorted(p.name for p in batch.glob('*.green.json'))
            proof = json.loads((batch / "native-data-proof.json").read_text()) if (batch / "native-data-proof.json").exists() else None
        return error, calls, files, proof

    def test_green_uses_journal_artifacts_when_inactive_live_start_fields_are_gone(self):
        error, calls, files, proof = self.run_green()
        self.assertIsNone(error, error)
        self.assertEqual(files, sorted([DATA_SERVICE + ".green.json", GUARD_SERVICE + ".green.json"]))
        self.assertEqual((proof["unknown_count"], proof["stale_count"], proof["loki_query_http_status"]), (3, 2, 200))
        self.assertFalse(any("InvocationID" in str(c) or "ExecMainStartTimestamp" in str(c) for c in calls))

    def test_green_rejects_failed_job_or_unchanged_artifact_without_restarting(self):
        for kwargs in ({"bad_job": True}, {"unchanged": True}):
            with self.subTest(kwargs=kwargs):
                error, calls, files, proof = self.run_green(**kwargs)
                self.assertIsNotNone(error)
                starts = [c for c in calls if "start" in c and "systemctl" in c]
                self.assertEqual(len(starts), 1)
                self.assertFalse(files)
                self.assertIsNone(proof)

    def test_green_rejects_old_endpoint_and_wrong_loki_generation(self):
        error, calls, files, proof = self.run_green(wrong_endpoint=True)
        self.assertIsNotNone(error)
        self.assertFalse(calls)
        error, calls, files, proof = self.run_green(wrong_marker=True)
        self.assertIn("marker", error)
        self.assertEqual(files, [GUARD_SERVICE + ".green.json"])
        self.assertIsNone(proof)

    def test_green_pauses_between_cases_when_the_paper_window_opens(self):
        error, calls, files, proof = self.run_green(crosses_window=True)
        self.assertIn("pause", error)
        starts = [c for c in calls if "start" in c and "systemctl" in c]
        self.assertEqual(len(starts), 1)
        self.assertEqual(files, [GUARD_SERVICE + ".green.json"])
        self.assertIsNone(proof)

    def test_runbook_gates_pending_reload_and_dated_window_without_mutating_manager(self):
        text = (UNITS / "upkeep-transfer.md").read_text().split("<!-- upkeep:manager-gates -->", 1)[1]
        code = re.search(r"```sh\n(.*?)```", text, re.S).group(1)
        for stamp, pending, expected in (("202610061100", False, 78), ("202610062000", False, 78),
                                          ("202610070005", False, 78), ("202610060500", True, 78),
                                          ("202610061400", False, 0)):
            with self.subTest(stamp=stamp, pending=pending), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                calls = root / "calls"
                (root / "rtk").write_text('#!/bin/sh\n[ "$1" != proxy ] || shift\nexec "$@"\n')
                (root / "date").write_text(f"#!/bin/sh\nprintf '{stamp}\\n'\n")
                (root / "systemctl").write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$FIXTURE_CALLS"\n'
                    + f'printf "Id=paper.service\\nNeedDaemonReload={"yes" if pending else "no"}\\n"\n')
                for path in root.iterdir():
                    path.chmod(0o755)
                env = {"PATH": str(root) + ":/usr/bin:/bin", "HOME": os.environ["HOME"], "FIXTURE_CALLS": str(calls)}
                result = subprocess.run(["bash"], input=code, env=env, capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, expected, result.stderr)
                self.assertNotIn("daemon-reload", calls.read_text() if calls.exists() else "")

    def test_effective_readback_requires_both_timers_and_rejects_wrong_cadence(self):
        text = (UNITS / "upkeep-transfer.md").read_text().split("## Read-back and rollback", 1)[1]
        code = re.findall(r"<<'PY'\n(.*?)\nPY", text, re.S)[0]
        for bad in (None, "inactive", "static", "cadence", "bytes"):
            with self.subTest(bad=bad), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                batch = root / "batch"
                batch.mkdir()
                config = root / "config"
                target = root / "candidate-file"
                target.write_bytes(b"candidate\n")
                target.chmod(0o600)
                record = {"path": str(target), "expected": {"kind": "file", "mode": 0o600,
                          "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}}
                (batch / "manifest.json").write_text(json.dumps({"config_root": str(config), "paths": [record]}))
                for name in (GUARD_SERVICE + ".green.json", DATA_SERVICE + ".green.json", "native-data-proof.json"):
                    (batch / name).write_text("{}\n")
                if bad == "bytes":
                    target.write_bytes(b"unexpected operator bytes\n")
                calls = []
                def output(argv, **kwargs):
                    calls.append(argv)
                    name = argv[3]
                    if "is-enabled" in argv:
                        return "static\n" if bad == "static" and name == DATA_TIMER else "enabled\n"
                    boot, accuracy = ("2min", "15s") if name == GUARD_TIMER else ("45s", "10s")
                    active = "inactive" if bad == "inactive" and name == DATA_TIMER else "active"
                    interval = "3min" if bad == "cadence" and name == DATA_TIMER else "2min"
                    return (f"Unit={name.replace('.timer', '.service')}\nAccuracyUSec={accuracy}\n"
                            f"TimersMonotonic={{ OnBootUSec={boot} ; next_elapse=1h }}\n"
                            f"TimersMonotonic={{ OnUnitActiveUSec={interval} ; next_elapse=1h }}\n"
                            f"NeedDaemonReload=no\nDropInPaths=\nActiveState={active}\nUnitFileState=disabled\n"
                            f"FragmentPath={config / 'systemd/user' / name}\n")
                error = None
                with mock.patch.object(subprocess, "check_output", side_effect=output), \
                     mock.patch("sys.argv", ["inline", str(batch)]), mock.patch("sys.stdout", io.StringIO()):
                    try:
                        exec(compile(code, "native-readback-runbook", "exec"), {})
                    except SystemExit as exc:
                        error = str(exc)
                self.assertEqual(error is None, bad is None, error)
                # Cached show UnitFileState=disabled cannot substitute for the fresh native filesystem query.
                self.assertTrue(any("is-enabled" in c for c in calls))


    def test_native_data_keeps_the_recorded_observer_and_timer_contract(self):
        service = (UNITS / DATA_SERVICE).read_text()
        timer = (UNITS / DATA_TIMER).read_text()
        for directive in ("Type=oneshot", "UMask=0077", "NoNewPrivileges=true",
                          "TimeoutStartSec=90", "Nice=19", "After=ns2604-loki.service",
                          "Environment=RTK_TELEMETRY_DISABLED=1"):
            self.assertIn(directive, service.splitlines())
        self.assertIn('ExecStart=/usr/bin/python3 -B "@REPOSITORY@/observability/native-data/snapshot.py" '
                      '--config "@PRIVATE_CONFIG@" --publish', service.splitlines())
        self.assertIn('Environment="PATH=@NODE_DIRECTORY@:/usr/local/bin:/usr/bin:/bin"', service.splitlines())
        self.assertNotIn("RemainAfterExit=yes", service)
        self.assertNotIn("[Install]", service)
        for directive in ("OnBootSec=45s", "OnUnitActiveSec=2min", "AccuracySec=10s",
                          "Unit=ecosystem-native-data.service", "WantedBy=timers.target"):
            self.assertIn(directive, timer.splitlines())
        self.assertNotIn("Persistent=true", timer)  # Only calendar timers persist.

    def test_guard_keeps_the_observed_scope_and_cadence(self):
        service = (UNITS / GUARD_SERVICE).read_text()
        timer = (UNITS / GUARD_TIMER).read_text()
        for directive in ("Type=oneshot", "Nice=19", "UMask=0077", "NoNewPrivileges=true",
                          "Environment=UV_CACHE_DIR=%h/.cache/uv",
                          "Environment=UV_LOCK_TIMEOUT=10",
                          "ExecStart=%h/.local/state/native-agent-stack/ops/disk-headroom-guard.sh"):
            self.assertIn(directive, service.splitlines())
        for directive in ("OnBootSec=2min", "OnUnitActiveSec=2min", "AccuracySec=15s",
                          "Unit=disk-headroom-guard.service", "WantedBy=timers.target"):
            self.assertIn(directive, timer.splitlines())
        self.assertNotIn("RemainAfterExit=yes", service)
        self.assertNotIn("[Install]", service)
        self.assertNotIn("Persistent=true", timer)

    def verify(self, directory, timer_text, strict=True):
        executable = shutil.which("systemd-analyze")
        if not executable:
            self.skipTest("systemd-analyze unavailable; host validation remains required")
        help_result = subprocess.run([executable, "--help"], capture_output=True, text=True)
        if not all(flag in help_result.stdout for flag in ("--recursive-errors", "--generators")):
            self.skipTest("Native verifier options unavailable; installed 259.5 host validation required")
        service = (UNITS / DATA_SERVICE).read_text()
        # A whitespace-bearing path checks the reviewed unit quoting with the native parser.
        service = service.replace("@REPOSITORY@", str(ROOT))
        service = service.replace("@PRIVATE_CONFIG@", str(directory / "private configuration.json"))
        service = service.replace("@NODE_DIRECTORY@", str(directory / "node directory"))
        self.assertNotIn("@REPOSITORY@", service)
        self.assertNotIn("@PRIVATE_CONFIG@", service)
        self.assertNotIn("@NODE_DIRECTORY@", service)
        service_path, timer_path = directory / DATA_SERVICE, directory / DATA_TIMER
        service_path.write_text(service)
        timer_path.write_text(timer_text)
        guard = (UNITS / GUARD_SERVICE).read_text().replace(
            "%h/.local/state/native-agent-stack/ops/disk-headroom-guard.sh",
            str(ROOT / "tools/maintenance/disk-headroom-guard.sh"))
        guard_service, guard_timer = directory / GUARD_SERVICE, directory / GUARD_TIMER
        guard_service.write_text(guard)
        guard_timer.write_text((UNITS / GUARD_TIMER).read_text())
        runtime = directory / "runtime"
        runtime.mkdir(mode=0o700, exist_ok=True)
        env = {"PATH": os.environ["PATH"], "HOME": os.environ["HOME"], "LANG": "C",
               "XDG_RUNTIME_DIR": str(runtime),
               "SYSTEMD_UNIT_PATH": str(directory) + ":/usr/lib/systemd/user"}
        argv = [executable, "--user", "--man=no", "--generators=no"]
        if strict:
            argv.append("--recursive-errors=no")
        return subprocess.run(argv + ["verify", str(service_path), str(timer_path),
                                      str(guard_service), str(guard_timer)],
                              env=env, capture_output=True, text=True, timeout=20)

    def test_native_parser_accepts_all_four_rendered_transfer_units(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.verify(Path(directory), (UNITS / DATA_TIMER).read_text())
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_verification_fails_an_unknown_directive_instead_of_accepting_warning_only(self):
        timer = (UNITS / DATA_TIMER).read_text().replace("OnBootSec=", "OnBootSecc=")
        self.assertIn("OnBootSecc=", timer)
        with tempfile.TemporaryDirectory() as directory:
            # systemd 259.5's default verify exits 0 despite this warning.
            ordinary = self.verify(Path(directory), timer, strict=False)
            strict = self.verify(Path(directory), timer)
        self.assertEqual(ordinary.returncode, 0, ordinary.stderr)
        self.assertIn("OnBootSecc", ordinary.stderr)
        self.assertNotEqual(strict.returncode, 0, strict.stdout)
        self.assertIn("OnBootSecc", strict.stderr)


if __name__ == "__main__":
    unittest.main()
