"""Stdlib contract and fault tests; native restic execution has a separate receipt.

Calendar and restic doubles below test our integration, not upstream acceptance.
All mutable state belongs to a temporary directory; no service or broker is used.
"""

from __future__ import annotations

from contextlib import closing, redirect_stdout
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import fcntl
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "blueprints/us-equities/hosting"


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


RECOVERY = load("journal_recovery")
SESSION = load("session_day")
RESTART = load("drill_process_restart")
DRILL = load("drill_local_recovery")


def calendar_python():
    """Use an already installed locked SDK; never resolve/install dependencies."""
    candidates = [sys.executable]
    if os.environ.get("SDK_ENV"):
        candidates.append(str(Path(os.environ["SDK_ENV"]) / "bin/python"))
    for candidate in candidates:
        try:
            checked = subprocess.run(
                [candidate, "-c", 'import exchange_calendars; from importlib.metadata import version; '
                 'assert version("exchange-calendars") == "4.13.2"'],
                capture_output=True, timeout=30, check=False)
        except OSError:
            continue
        if checked.returncode == 0:
            return candidate
    return None


CALENDAR_PYTHON = calendar_python()
DAGU = Path(os.environ.get("DAGU_BIN", Path.home() / ".local/share/codex-ecosystem/bin/dagu"))


@unittest.skipUnless(CALENDAR_PYTHON, "requires importable exchange-calendars 4.13.2 (or SDK_ENV)")
class RealCalendarTests(unittest.TestCase):
    def test_holidays_and_early_closes_with_real_locked_calendar(self):
        for day, expected in (("2026-01-01", "non_session"), ("2027-01-01", "non_session"),
                              ("2034-01-02", "non_session"), ("2026-11-26", "non_session"),
                              ("2026-11-27", "session"), ("2026-12-24", "session")):
            with self.subTest(day=day):
                result = subprocess.run(
                    [CALENDAR_PYTHON, str(HERE / "session_day.py"), "--at", day + "T16:30:00-05:00"],
                    capture_output=True, text=True, timeout=30, check=False)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.strip(), expected)

    def test_truly_uncovered_date_is_a_hard_failure(self):
        checked = subprocess.run(
            [CALENDAR_PYTHON, "-c", 'import exchange_calendars as x; '
             'from exchange_calendars.errors import DateOutOfBounds; '
             'c=x.get_calendar("XNYS", start="2026-01-01", end="2026-12-31"); '
             'c.is_session("2034-01-02")'], capture_output=True, text=True, timeout=30, check=False)
        self.assertNotEqual(checked.returncode, 0)
        self.assertIn("DateOutOfBounds", checked.stderr)


def native_dagu_probe(token):
    """Native runner + original status, without UI/scheduler/services or network.

    Minimal reproduction of the deployed output/scalar-precondition/dependency
    chain; Dagu@v2.16.6:internal/runtime/runner.go:1267-1281,1633-1648.
    """
    with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR")) as temporary:
        root = Path(temporary).resolve()
        marker = root / "ran"
        config = root / "config.yaml"
        config.write_text((HERE / "config.yaml.example").read_text())
        dag = root / "native-chain.yaml"
        dag.write_text(f'''type: graph
timeout_sec: 15
artifacts:
  enabled: false
steps:
  - id: calendar_check
    run: 'printf {token}'
    output: SESSION_DAY
  - id: nyse_session
    preconditions:
      - condition: '${{SESSION_DAY}}'
        expected: session
    run: 'true'
    depends: [calendar_check]
  - id: evidence
    run: 'touch "{marker}"'
    depends: [nyse_session]
''')
        env = {"HOME": str(root), "PATH": "/usr/bin:/bin", "TMPDIR": os.environ["TMPDIR"]}
        version = subprocess.run([str(DAGU), "version"], env=env, cwd=root,
                                 capture_output=True, text=True, timeout=15, check=False)
        if version.returncode or "2.16.6" not in version.stdout:
            raise AssertionError("native probe requires Dagu 2.16.6")
        command = [str(DAGU), "start", "--context", "local", "--dagu-home", str(root),
                   "--config", str(config), str(dag)]
        result = subprocess.run(command, env=env, cwd=root, capture_output=True, text=True,
                                timeout=30, check=False)
        status_paths = list(root.rglob("status.jsonl"))
        if len(status_paths) != 1:
            raise AssertionError("one original native status record required")
        status = RESTART.last_status(status_paths[0])
        proof = {"token": token, "version_exit": version.returncode, "version_output": version.stdout,
                 "command": "dagu start --context local --dagu-home <scratch> --config <scratch>/config.yaml <scratch>/native-chain.yaml",
                 "exit": result.returncode, "output": result.stdout + result.stderr,
                 "native_status": status, "marker_created": marker.exists()}
        return DRILL.sanitize(proof, root=root, lexical_root=root, binary=DAGU)


@unittest.skipUnless(DAGU.is_file(), "requires the installed Dagu 2.16.6 binary")
class NativeDaguTests(unittest.TestCase):
    def check_probe(self, token, expected, marker):
        proof = native_dagu_probe(token)
        self.assertEqual(proof["exit"], 0, proof["output"])
        self.assertEqual(proof["native_status"]["status"], 4)
        self.assertEqual({n["step"]["id"]: n["status"] for n in proof["native_status"]["nodes"]},
                         {"calendar_check": 4, "nyse_session": expected, "evidence": expected})
        self.assertEqual(proof["marker_created"], marker)
        return proof

    def test_native_non_session_skips_dependents(self):
        self.check_probe("non_session", 5, False)

    def test_native_session_executes_success_chain(self):
        self.check_probe("session", 4, True)

    def test_native_stale_input_is_visible_and_skips_dependents(self):
        self.check_probe("stale_input", 5, False)


class HostingContractTests(unittest.TestCase):
    def test_coordinator_disabled_in_configuration(self):
        config = (HERE / "config.yaml.example").read_text()
        self.assertRegex(config, r"(?m)^coordinator:\n  enabled: false$")
        self.assertRegex(config, r"(?m)^  run_dags: false$")
        for key in ("LEAN_RESULTS", "RESEARCH_WORKSPACE", "NATIVE_CODEX_HOME", "NATIVE_CODEX_BIN",
                    "NATIVE_CLAUDE_BIN", "NATIVE_RUNTIME_PATH", "SDK_OBSERVATION_DIR"):
            self.assertRegex(config, rf"(?m)^  - {key}$")

    def test_unit_start_all_restart_and_job_environment_delivery(self):
        unit = (HERE / "dagu-equities.service.example").read_text()
        line = next(line for line in unit.splitlines() if line.startswith("ExecStart="))
        self.assertIn("=/usr/bin/env -i ", line)
        self.assertIn("/path/to/dagu-2.16.6 start-all", line)
        self.assertIn("--config /path/to/dagu-home/config.yaml", line)
        self.assertRegex(unit, r"(?m)^Restart=on-failure$")
        self.assertNotRegex(unit, r"(?m)^Environment=")
        # env -i eliminates inherited Environment=; the private DAG explicitly owns all four.
        dag = (HERE / "equity-research-evidence.yaml").read_text()
        env_block = dag.split("\nenv:\n", 1)[1].split("\nworking_dir:", 1)[0]
        for key in ("STACK_REPO", "SDK_ENV", "LEAN_EVENTS", "RESEARCH_OUTPUT"):
            self.assertRegex(env_block, rf"(?m)^  {key}: /path/to/.+$")

    def test_schedule_name_timezone_and_skipping_dependency_chain(self):
        dag = (HERE / "equity-research-evidence.yaml").read_text()
        self.assertIn("tags: [nyse-post-close-evidence]", dag)
        self.assertRegex(dag, r"(?m)^schedule: 'CRON_TZ=America/New_York 30 16 \* \* 1-5'$")
        self.assertIn('"${SDK_ENV}/bin/python" "${STACK_REPO}/blueprints/us-equities/hosting/session_day.py"', dag)
        self.assertIn("output: SESSION_DAY", dag)
        self.assertIn("preconditions:\n      - condition: '${SESSION_DAY}'\n        expected: session", dag)
        self.assertIn("depends: [calendar_check]", dag)
        self.assertIn("depends: [nyse_session]", dag)
        self.assertIn("depends: [prepare_output]", dag)
        self.assertIn("order-events-${DAG_RUN_ID}.parquet", dag)
        self.assertIn('--events "${LEAN_EVENTS}"', dag)

    def test_input_mtime_must_follow_actual_session_close(self):
        calendar = mock.Mock()
        calendar.is_session.return_value = True
        calendar.session_close.return_value = datetime.fromisoformat("2026-11-27T18:00:00Z")
        now = datetime.fromisoformat("2026-11-27T21:30:00Z")
        with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR")) as temporary:
            events = Path(temporary) / "events.json"
            self.assertEqual(SESSION.eligibility(calendar, now, events), "missing_input")
            events.write_text("[]")
            for instant, expected in (("2026-11-26T22:00:00Z", "stale_input"),
                                      ("2026-11-27T18:01:00Z", "session"),
                                      ("2026-11-27T21:31:00Z", "future_input")):
                epoch = datetime.fromisoformat(instant).timestamp()
                os.utime(events, (epoch, epoch))
                self.assertEqual(SESSION.eligibility(calendar, now, events), expected)
            calendar.is_session.return_value = False
            self.assertEqual(SESSION.eligibility(calendar, now, events), "non_session")

    def test_wrong_calendar_version_fails_in_the_normal_step(self):
        with mock.patch.object(SESSION, "version", return_value="0.0"):
            with self.assertRaisesRegex(RuntimeError, "locked exchange-calendars"):
                SESSION.main([])

    def test_session_check_uses_new_york_date_and_skips_a_non_session(self):
        calendar = mock.Mock()
        calendar.is_session.return_value = False
        self.assertEqual(SESSION.eligibility(calendar, datetime.fromisoformat("2026-10-05T00:30:00Z")),
                         "non_session")
        calendar.is_session.assert_called_once_with("2026-10-04")
        calendar.session_close.assert_not_called()

    def test_actual_close_is_checked_and_early_close_waits_until_daily_slot(self):
        calendar = mock.Mock()
        calendar.is_session.return_value = True
        calendar.session_close.return_value = datetime.fromisoformat("2026-11-27T18:00:00Z")
        self.assertEqual(SESSION.eligibility(calendar, datetime.fromisoformat("2026-11-27T17:59:00Z")),
                         "before_close")
        self.assertEqual(SESSION.eligibility(calendar, datetime.fromisoformat("2026-11-27T16:30:00-05:00")),
                         "session")

    def test_due_run_requires_slot_scheduler_and_success(self):
        due = datetime.fromisoformat("2026-10-05T16:30:00-04:00")
        native = {"name": "equity-research-evidence", "dagRunId": "fixture-run", "triggerType": 1,
                  "status": 4, "scheduleTime": "2026-10-05T20:30:00Z",
                  "nodes": [{"step": {"id": step}, "status": 4} for step in
                            ("calendar_check", "nyse_session", "prepare_output", "summarize",
                             "baseline_evidence", "catalog_evidence")]}
        self.assertTrue(RESTART.due_run(native, due, {"fixture-run"}))
        for change in ({"triggerType": 2}, {"status": 2}, {"scheduleTime": "2026-10-06T20:30:00Z"},
                       {"name": "another-dag"}):
            with self.subTest(change=change):
                self.assertFalse(RESTART.due_run({**native, **change}, due, {"fixture-run"}))
        skipped = json.loads(json.dumps(native))
        skipped["nodes"][1]["status"] = 5
        self.assertFalse(RESTART.due_run(skipped, due, {"fixture-run"}))
        self.assertFalse(RESTART.due_run({**native, "nodes": []}, due, {"fixture-run"}))

    def test_scripts_use_python_311_compatible_syntax_and_native_digest(self):
        import ast
        self.assertTrue(hasattr(RECOVERY.hashlib, "file_digest"))
        for name in ("journal_recovery", "session_day", "drill_process_restart", "drill_local_recovery"):
            with self.subTest(script=name):
                ast.parse((HERE / f"{name}.py").read_text(), feature_version=(3, 11))


class DrillGuardTests(unittest.TestCase):
    def test_restart_time_window_refuses_wrong_slot_past_close_and_short_reserve(self):
        due = datetime.fromisoformat("2026-10-05T16:30:00-04:00")
        RESTART.validate_window(due, due - timedelta(minutes=5), 900)
        for slot, now, wait in ((due.replace(hour=15), due - timedelta(minutes=5), 900),
                                (due, due, 900), (due, due - timedelta(seconds=10), 900),
                                (due, due - timedelta(minutes=5), 400),
                                (due.replace(tzinfo=None), due - timedelta(minutes=5), 900),
                                (due, due - timedelta(minutes=5), 3601)):
            with self.subTest(slot=slot, wait=wait), self.assertRaises(ValueError):
                RESTART.validate_window(slot, now, wait)

    def test_restart_refuses_holiday_and_calendar_failure_before_signalling(self):
        due = datetime.fromisoformat("2026-01-01T16:30:00-05:00")
        for code, token in ((0, "non_session"), (0, "before_close"), (1, "")):
            with mock.patch.object(RESTART.subprocess, "run", return_value=SimpleNamespace(
                    returncode=code, stdout=token)), mock.patch.object(RESTART.os, "kill") as kill:
                with self.assertRaisesRegex(ValueError, "refused"):
                    RESTART.require_session(due)
                kill.assert_not_called()
        with mock.patch.object(RESTART, "validate_window"), mock.patch.object(RESTART.subprocess, "run",
                return_value=SimpleNamespace(returncode=0, stdout="non_session")), \
                mock.patch.object(RESTART, "unit_state") as unit_state, mock.patch.object(RESTART.os, "kill") as kill, \
                redirect_stdout(io.StringIO()):
            self.assertEqual(RESTART.main(["--dagu-bin", "unused", "--dagu-home", "unused", "--config", "unused",
                                           "--dag-history", "unused", "--due-at", due.isoformat()]), 1)
            unit_state.assert_not_called()
            kill.assert_not_called()

    def test_restart_pid_command_and_executable_identity_guards(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR")) as temporary:
            root = Path(temporary)
            binary = root / "dagu"
            binary.touch()
            process = root / "10"
            process.mkdir()
            (process / "cmdline").write_bytes(b"dagu\0start-all\0--config\0private-config\0")
            (process / "exe").symlink_to(binary)
            RESTART.validate_process(10, binary, root)
            for pid, chosen in ((1, binary), (0, binary), (10, root / "different-binary")):
                with self.subTest(pid=pid), self.assertRaises(ValueError):
                    RESTART.validate_process(pid, chosen, root)
            (process / "cmdline").write_bytes(b"dagu\0server\0")
            with self.assertRaises(ValueError):
                RESTART.validate_process(10, binary, root)

    def test_symlinked_scratch_root_scrubs_both_forms_and_resolves_at_creation(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR")) as temporary:
            parent = Path(temporary)
            actual = parent / "actual"
            actual.mkdir()
            link = parent / "linked"
            link.symlink_to(actual, target_is_directory=True)
            root, lexical = DRILL.scratch_directory(link)
            self.assertEqual(root.parent, actual.resolve())
            self.assertEqual(lexical.parent, link)
            binary = parent / "restic"
            clean = DRILL.sanitize({"a": str(root / "restored"), "b": str(lexical / "stage"),
                                    "binary": str(binary), "relative": "./journals/a.sqlite3"},
                                   root=root, lexical_root=lexical, binary=binary)
            self.assertEqual(clean, {"a": "<scratch>/restored", "b": "<scratch>/stage",
                                     "binary": "<restic-0.19.1>", "relative": "./journals/a.sqlite3"})
            with self.assertRaisesRegex(RECOVERY.RecoveryError, "absolute path"):
                DRILL.sanitize({"leftover": str(parent / "not-in-root")}, root=root,
                               lexical_root=lexical, binary=binary)
            for path in ("/unrecognized/path", "C:\\private\\file", "file:///private/db"):
                with self.subTest(path=path), self.assertRaises(RECOVERY.RecoveryError):
                    DRILL.assert_sanitized({"leftover": path})

    def test_output_refuses_unsanitized_report_before_write(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR")) as temporary:
            output = Path(temporary) / "published.json"
            with mock.patch.object(DRILL, "drill", return_value={"leak": str(output)}), redirect_stdout(io.StringIO()):
                self.assertEqual(DRILL.main(["--restic-bin", "unused", "--scratch-root", temporary,
                                             "--output", str(output)]), 1)
            self.assertFalse(output.exists())


class FakeRestic:
    """Synthetic native responses; only frozen staging files are copied for restore."""

    def __init__(self, binary, repository, password, work, timeout=600):
        self.repository = Path(repository).resolve()
        self.work = Path(work).resolve()
        self.password_file = Path(password).resolve()
        self.commands = []
        self.fail_check = False

    def run(self, *args):
        self.commands.append(args)
        if args[0] == "version":
            return "restic 0.19.1 compiled with fixture\n"
        if args[0] == "backup":
            self.stage = Path(args[1])
            if any(path.stat().st_mode & 0o777 == 0 for path in self.stage.rglob("*.sqlite3")):
                raise RECOVERY.RecoveryError("restic backup refused (exit 3)")
            return json.dumps({"message_type": "summary", "snapshot_id": "a" * 64})
        if args[0] == "restore":
            shutil.copytree(self.stage, args[args.index("--target") + 1])
        if args[0] == "check" and self.fail_check:
            raise RECOVERY.RecoveryError("restic check refused (exit 1)")
        return ""


class JournalRecoveryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR"))
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.sources = {}
        for name, table in (("research", "events"), ("evidence", "runs")):
            path = self.root / f"{name}.sqlite3"
            db = sqlite3.connect(path, isolation_level=None)
            self.addCleanup(db.close)
            db.execute("PRAGMA journal_mode=WAL")
            db.execute(f"CREATE TABLE {table}(id INTEGER PRIMARY KEY, value TEXT)")
            db.execute(f"INSERT INTO {table}(value) VALUES ('committed in WAL')")
            self.sources[name] = (path, [table])
        self.stage = self.root / "stage"
        self.oracle = self.root / "frozen.json"
        (self.root / "repository").mkdir()
        (self.root / "unused-password-file").touch()

    def snapshot(self):
        return RECOVERY.snapshot_journals(self.sources, self.stage, self.oracle)

    def restore_fixture(self):
        self.snapshot()
        restored = self.root / "restored"
        shutil.copytree(self.stage, restored)
        return restored

    def runner(self):
        return FakeRestic("unused", self.root / "repository", self.root / "unused-password-file", self.root)

    def test_online_backup_includes_committed_wal_state_and_freezes_hashes(self):
        inventory = self.snapshot()
        self.assertEqual(len(inventory["files"]), 2)
        self.assertEqual((self.stage / "inventory.json").read_bytes(), self.oracle.read_bytes())
        self.assertEqual(RECOVERY.verify(self.stage, self.oracle)["matched_files"], 2)
        for record in inventory["files"]:
            self.assertEqual(list(record["required_tables"].values()), [1])
            self.assertRegex(record["sha256"], "^[a-f0-9]{64}$")
            self.assertGreater(record["bytes"], 0)
            self.assertEqual(record["integrity_check"], "ok")
        self.assertFalse(list(self.stage.rglob("*-wal")))

    def test_snapshot_calls_backup_api_and_does_not_copy_source_files(self):
        import ast
        tree = ast.parse((HERE / "journal_recovery.py").read_text())
        calls = [node.func.attr for node in ast.walk(tree) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Attribute)]
        self.assertIn("backup", calls)
        self.assertNotIn("copyfile", calls)
        self.assertNotIn("copy2", calls)
        backups = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                   and isinstance(node.func, ast.Attribute) and node.func.attr == "backup"]
        self.assertEqual(len(backups), 1)
        self.assertEqual(ast.literal_eval(next(k.value for k in backups[0].keywords if k.arg == "pages")), -1)

    def test_online_backup_size_and_hard_time_limits_refuse_before_freezing(self):
        with self.assertRaisesRegex(RECOVERY.RecoveryError, "max-journal-bytes"):
            RECOVERY.snapshot_journals(self.sources, self.stage, self.oracle, max_journal_bytes=1)
        self.assertFalse(self.oracle.exists())
        with mock.patch.object(RECOVERY.subprocess, "run", side_effect=subprocess.TimeoutExpired("native backup", 1)):
            with self.assertRaises(subprocess.TimeoutExpired):
                RECOVERY.snapshot_journals(self.sources, self.root / "timeout-stage", self.oracle,
                                           backup_timeout=1)
        self.assertFalse(self.oracle.exists())

    def test_missing_required_table_prevents_freezing(self):
        path = self.sources["research"][0]
        with self.assertRaises(sqlite3.Error):
            RECOVERY.snapshot_journals({"research": (path, ["missing_table"])}, self.stage, self.oracle)
        self.assertFalse(self.oracle.exists())

    def test_empty_selection_and_unreviewed_tables_refused(self):
        for selection in ({}, {"research": (self.sources["research"][0], [])}):
            with self.subTest(selection=list(selection)):
                with self.assertRaises(RECOVERY.RecoveryError):
                    RECOVERY.snapshot_journals(selection, self.stage, self.oracle)

    def test_hash_rejects_changed_contents_even_when_integrity_and_counts_match(self):
        restored = self.restore_fixture()
        journal = restored / "journals/research.sqlite3"
        journal.chmod(0o600)
        with closing(sqlite3.connect(journal)) as db:
            with db:
                db.execute("UPDATE events SET value='changed but complete schema'")
        self.assertEqual(RECOVERY.journal_state(journal, ["events"]),
                         {"integrity_check": "ok", "required_tables": {"events": 1}})
        with self.assertRaisesRegex(RECOVERY.RecoveryError, "sha256/bytes"):
            RECOVERY.verify(restored, self.oracle)

    def test_missing_and_extra_files_refused(self):
        restored = self.restore_fixture()
        extra = restored / "unselected.txt"
        extra.touch()
        with self.assertRaisesRegex(RECOVERY.RecoveryError, "inventory mismatch"):
            RECOVERY.verify(restored, self.oracle)
        extra.unlink()
        (restored / "journals/evidence.sqlite3").unlink()
        with self.assertRaisesRegex(RECOVERY.RecoveryError, "inventory mismatch"):
            RECOVERY.verify(restored, self.oracle)

    def test_restore_cannot_substitute_its_own_inventory(self):
        restored = self.restore_fixture()
        (restored / "inventory.json").chmod(0o600)
        (restored / "inventory.json").write_text('{"schema_version": 1, "files": []}\n')
        with self.assertRaisesRegex(RECOVERY.RecoveryError, "external frozen oracle"):
            RECOVERY.verify(restored, self.oracle)

    def test_symlink_is_refused(self):
        restored = self.restore_fixture()
        (restored / "linked").symlink_to(self.oracle)
        with self.assertRaisesRegex(RECOVERY.RecoveryError, "symlink"):
            RECOVERY.verify(restored, self.oracle)

    def test_row_count_is_a_secondary_required_state_check(self):
        restored = self.restore_fixture()
        inventory = json.loads(self.oracle.read_text())
        inventory["files"][0]["required_tables"]["runs"] = 2
        for path in (self.oracle, restored / "inventory.json"):
            path.chmod(0o600)
            path.write_bytes(RECOVERY.json_bytes(inventory))
        with self.assertRaisesRegex(RECOVERY.RecoveryError, "required journal state"):
            RECOVERY.verify(restored, self.oracle)

    def test_every_nonzero_native_exit_including_three_is_refused(self):
        runner = RECOVERY.Restic(Path("unused"), self.root / "repository",
                                 self.root / "unused-password-file", self.root)
        for code in (1, 2, 3, 10, 11, 12, 130):
            with self.subTest(exit=code):
                with mock.patch.object(RECOVERY.subprocess, "run", return_value=SimpleNamespace(
                        returncode=code, stdout="synthetic incomplete snapshot\n", stderr="")):
                    with self.assertRaisesRegex(RECOVERY.RecoveryError, f"exit {code}"):
                        runner.run("backup", "stage")

    def test_rotation_reads_every_default_subset_within_seven_days(self):
        runner = self.runner()
        state = self.root / "rotation.json"
        first = datetime(2026, 10, 5, tzinfo=timezone.utc)
        observed = [RECOVERY.check_rotation(runner, state, now=first + timedelta(days=i)) for i in range(7)]
        self.assertEqual(observed, [f"{i}/7" for i in range(1, 8)])
        self.assertEqual(json.loads(state.read_text())["next"], 1)
        self.assertEqual([args[1] for args in runner.commands],
                         [f"--read-data-subset={i}/7" for i in range(1, 8)])

    def test_failed_check_does_not_advance_rotation(self):
        runner = self.runner()
        state = self.root / "rotation.json"
        now = datetime.now(timezone.utc)
        RECOVERY.check_rotation(runner, state, now=now)
        before = state.read_bytes()
        runner.fail_check = True
        with self.assertRaises(RECOVERY.RecoveryError):
            RECOVERY.check_rotation(runner, state, now=now + timedelta(hours=1))
        self.assertEqual(state.read_bytes(), before)
        # Native flock is released even on failure; the inode deliberately remains.
        self.assertEqual(RECOVERY.check_rotation(self.runner(), state, now=now + timedelta(hours=2)), "2/7")

    def test_missed_rotation_interval_requires_successful_full_read(self):
        runner = self.runner()
        state = self.root / "rotation.json"
        now = datetime.now(timezone.utc)
        RECOVERY.check_rotation(runner, state, now=now)
        later = now + timedelta(days=7, seconds=1)
        with self.assertRaisesRegex(RECOVERY.RecoveryError, "overdue"):
            RECOVERY.check_rotation(runner, state, now=later)
        self.assertEqual(RECOVERY.check_rotation(runner, state, now=later, full_check=True), "1/7")
        self.assertIn(("check", "--read-data"), runner.commands)

    def test_rotation_allows_daily_jitter_over_multiple_whole_cycles(self):
        runner = self.runner()
        state = self.root / "jitter.json"
        first = datetime(2026, 10, 26, 20, 30, tzinfo=timezone.utc)
        times = [first + i * timedelta(hours=24, seconds=60) for i in range(14)]
        observed = [RECOVERY.check_rotation(runner, state, now=instant) for instant in times]
        self.assertEqual(observed, [f"{i}/7" for i in range(1, 8)] * 2)
        self.assertEqual(json.loads(state.read_text())["cycle_started_at"], times[7].isoformat())

    def test_rotation_across_fall_back_uses_utc_seven_day_cycle(self):
        runner = self.runner()
        state = self.root / "dst.json"
        times = [datetime(2026, 10, 29, 16, 30, tzinfo=ZoneInfo("America/New_York")) + timedelta(days=i)
                 for i in range(7)]
        self.assertEqual(times[3].astimezone(timezone.utc) - times[2].astimezone(timezone.utc), timedelta(hours=25))
        observed = [RECOVERY.check_rotation(runner, state, now=instant) for instant in times]
        self.assertEqual(observed, [f"{i}/7" for i in range(1, 8)])
        self.assertEqual(json.loads(state.read_text())["cycle_started_at"], times[0].astimezone(timezone.utc).isoformat())

    def test_whole_rotation_deadline_refuses_even_without_large_individual_gaps(self):
        runner = self.runner()
        state = self.root / "slow.json"
        first = datetime(2026, 10, 5, tzinfo=timezone.utc)
        for i in range(6):
            RECOVERY.check_rotation(runner, state, now=first + i * timedelta(hours=29))
        before = state.read_bytes()
        with self.assertRaisesRegex(RECOVERY.RecoveryError, "overdue"):
            RECOVERY.check_rotation(runner, state, now=first + 6 * timedelta(hours=29))
        self.assertEqual(state.read_bytes(), before)

    def test_cycle_clock_is_captured_before_snapshot_and_checks_native_completion(self):
        runner = self.runner()
        with mock.patch.object(RECOVERY, "check_rotation", return_value="1/7") as rotation:
            RECOVERY.cycle(runner, self.sources, self.root / "time.json")
        self.assertLessEqual(rotation.call_args.kwargs["now"], rotation.call_args.kwargs["clock"]())
        backup = next(args for args in runner.commands if args[0] == "backup")
        self.assertEqual(backup[backup.index("--group-by") + 1], "host,tags")
        self.assertIn("--group-by host,tags", (HERE / "README.md").read_text())

    def test_slow_native_check_cannot_publish_state_after_cycle_deadline(self):
        runner = self.runner()
        first = datetime(2026, 10, 5, tzinfo=timezone.utc)
        state = self.root / "slow-native.json"
        RECOVERY.check_rotation(runner, state, now=first)
        before = state.read_bytes()
        with self.assertRaisesRegex(RECOVERY.RecoveryError, "after native check"):
            RECOVERY.check_rotation(runner, state, now=first + timedelta(days=6),
                                    clock=lambda: first + timedelta(days=7, seconds=1))
        self.assertEqual(state.read_bytes(), before)

    def test_native_lock_contention_refuses_and_stale_lock_after_exit_is_safe(self):
        state = self.root / "locked.json"
        lock = state.with_suffix(".json.lock")
        command = [sys.executable, "-c", 'import fcntl,sys; f=open(sys.argv[1],"a"); '
                   'fcntl.flock(f,fcntl.LOCK_EX); print("locked",flush=True); sys.stdin.read()', str(lock)]
        holder = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        try:
            self.assertEqual(holder.stdout.readline().strip(), "locked")
            with self.assertRaisesRegex(RECOVERY.RecoveryError, "held by another"):
                RECOVERY.check_rotation(self.runner(), state)
            self.assertFalse(state.exists())
        finally:
            holder.communicate(input="", timeout=10)
        self.assertEqual(holder.returncode, 0)
        self.assertTrue(lock.exists())
        lock.write_text("stale owner information is not a live native lock")
        self.assertEqual(RECOVERY.check_rotation(self.runner(), state), "1/7")

    def test_stale_atomic_publication_file_does_not_reset_or_block_cursor(self):
        state = self.root / "atomic.json"
        RECOVERY.check_rotation(self.runner(), state)
        stale = state.with_suffix(".json.new")
        stale.write_text("incomplete old write")
        self.assertEqual(RECOVERY.check_rotation(self.runner(), state), "2/7")
        self.assertEqual(stale.read_text(), "incomplete old write")

    def test_rotation_refuses_other_repository_and_invalid_part_counts(self):
        runner = self.runner()
        state = self.root / "rotation.json"
        RECOVERY.check_rotation(runner, state)
        runner.repository = self.root / "other-repository"
        with self.assertRaisesRegex(RECOVERY.RecoveryError, "another repository"):
            RECOVERY.check_rotation(runner, state)
        for parts in (0, 8):
            with self.assertRaises(RECOVERY.RecoveryError):
                RECOVERY.check_rotation(runner, self.root / "new-rotation", parts=parts)

    def test_both_controls_make_the_procedure_exit_nonzero(self):
        for control in ("snapshot", "restore"):
            work = self.root / control
            argv = ["cycle", "--restic-bin", "unused", "--repository", str(self.root / "repository"),
                    "--password-file", str(self.root / "unused-password-file"), "--work", str(work),
                    "--rotation-state", str(self.root / f"{control}-rotation.json"), "--control", control]
            for name, (path, tables) in self.sources.items():
                argv.extend(["--journal", f"{name}={path}", "--required-table", f"{name}={tables[0]}"])
            with self.subTest(control=control), mock.patch.object(RECOVERY, "Restic", FakeRestic):
                output = io.StringIO()
                with redirect_stdout(output):
                    self.assertEqual(RECOVERY.main(argv), 1)
                result = json.loads(output.getvalue())
                self.assertEqual(result["result"], "refused")
                self.assertIn("exit 3" if control == "snapshot" else "sha256/bytes mismatch", result["reason"])
                if control == "snapshot":
                    self.assertFalse((work / "restored").exists())
                else:
                    mutation = json.loads((work / "restore-control.json").read_text())
                    self.assertTrue(mutation["required_state_unchanged"])
                    self.assertTrue(mutation["bytes_unchanged"])
                    self.assertTrue(mutation["sha256_changed"])


if __name__ == "__main__":
    unittest.main()
