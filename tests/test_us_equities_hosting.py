"""Stdlib contract and fault tests; native restic execution has a separate receipt.

Calendar and restic doubles below test our integration, not upstream acceptance.
All mutable state belongs to a temporary directory; no service or broker is used.
"""

from __future__ import annotations

from contextlib import closing, redirect_stdout
from datetime import datetime, timedelta, timezone
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


class HostingContractTests(unittest.TestCase):
    def test_coordinator_disabled_in_configuration(self):
        config = (HERE / "config.yaml.example").read_text()
        self.assertRegex(config, r"(?m)^coordinator:\n  enabled: false$")
        self.assertRegex(config, r"(?m)^  run_dags: false$")

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
                  "status": 4, "scheduleTime": "2026-10-05T20:30:00Z"}
        self.assertTrue(RESTART.due_run(native, due, {"fixture-run"}))
        for change in ({"triggerType": 2}, {"status": 2}, {"scheduleTime": "2026-10-06T20:30:00Z"},
                       {"name": "another-dag"}):
            with self.subTest(change=change):
                self.assertFalse(RESTART.due_run({**native, **change}, due, {"fixture-run"}))


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
        self.assertFalse((self.root / "rotation.json.lock").exists())

    def test_missed_rotation_interval_requires_successful_full_read(self):
        runner = self.runner()
        state = self.root / "rotation.json"
        now = datetime.now(timezone.utc)
        RECOVERY.check_rotation(runner, state, now=now)
        later = now + timedelta(hours=25)
        with self.assertRaisesRegex(RECOVERY.RecoveryError, "overdue"):
            RECOVERY.check_rotation(runner, state, now=later)
        self.assertEqual(RECOVERY.check_rotation(runner, state, now=later, full_check=True), "1/7")
        self.assertIn(("check", "--read-data"), runner.commands)

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
                self.assertIn("exit 3" if control == "snapshot" else "inventory mismatch", result["reason"])
                if control == "snapshot":
                    self.assertFalse((work / "restored").exists())


if __name__ == "__main__":
    unittest.main()
