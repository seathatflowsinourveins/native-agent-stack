"""Local integration fixtures for the passive S3 recorder, not client acceptance."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("skill_state_recorder", ROOT / "tools/adoption/skill_state_recorder.py")
RECORDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RECORDER)


class SkillStateRecorderTests(unittest.TestCase):
    def setUp(self):
        scratch = Path(os.environ.get("NS_SKILL_RECORDER_TEST_CACHE", str(Path.home() / ".cache/ns2604-skills-r2-recorder-tests")))
        scratch.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix="fixture-", dir=scratch)
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.home = self.base / "home"
        self.project = self.base / "project"
        self.home.mkdir()
        self.project.mkdir()
        self.state = self.base / "state"
        self.recorder = RECORDER.Recorder(self.home, self.project, self.state)
        self.status = mock.patch.object(RECORDER.Recorder, "run_status")
        self.status_mock = self.status.start()
        self.addCleanup(self.status.stop)

    def skill(self, name="example", *, root=None, body="Public fixture instructions.\n"):
        directory = (root or self.home / ".agents/skills") / name
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "SKILL.md").write_text(f"---\nname: {name}\ndescription: Fixture applicability.\n---\n{body}")
        return directory

    def rows(self, filename="ledger.jsonl"):
        file = self.state / filename
        return [json.loads(line) for line in file.read_text().splitlines()] if file.exists() else []

    def main(self, payload, mode="record"):
        content = json.dumps(payload).encode() if isinstance(payload, dict) else payload
        stdin = io.TextIOWrapper(io.BytesIO(content))
        output = io.StringIO()
        with mock.patch.object(RECORDER.sys, "stdin", stdin), contextlib.redirect_stdout(output):
            result = RECORDER.main([
                "--home", str(self.home), "--project-dir", str(self.project), "--state-dir", str(self.state), "--mode", mode,
            ])
        return result, output.getvalue()

    def test_first_observation_is_not_install_or_adoption(self):
        self.skill()
        self.assertTrue(self.recorder.record("SessionStart"))
        row = self.rows()[0]
        self.assertEqual(row["event"], "observed")
        self.assertIsNone(row["before"])
        self.assertEqual(row["source"]["status"], "unknown")
        self.assertEqual(row["usage"], "unknown")
        self.assertNotIn("decision", row)
        self.assertEqual(row["after"]["locator"], "<home>/.agents/skills/example/SKILL.md")

    def test_add_remove_add_is_three_transitions(self):
        self.recorder.record("SessionStart")
        directory = self.skill()
        self.recorder.record("PostToolUse")
        (directory / "SKILL.md").unlink()
        directory.rmdir()
        self.recorder.record("FileChanged")
        self.skill()
        self.recorder.record("PostToolUse")
        rows = self.rows()
        self.assertEqual([row["action"] for row in rows], ["add", "remove", "add"])
        self.assertEqual(len({row["id"] for row in rows}), 3)
        self.assertIsNone(rows[1]["after"])

    def test_unchanged_fast_path_reads_no_body_or_lock_and_runs_no_status(self):
        self.skill()
        self.recorder.record("SessionStart")
        self.status_mock.reset_mock()
        with mock.patch.object(RECORDER, "bounded_read", wraps=RECORDER.bounded_read) as reader:
            self.assertFalse(self.recorder.record("PostToolUse"))
        self.assertEqual([call.args[0].name for call in reader.call_args_list], ["state.json"])
        self.status_mock.assert_not_called()
        self.assertEqual(len(self.rows()), 1)

    def test_bytecode_and_parent_directory_touch_do_not_make_changes(self):
        directory = self.skill()
        (directory / "scripts").mkdir()
        (directory / "scripts/run.py").write_text("print('fixture')\n")
        self.recorder.record("SessionStart")
        (directory / "scripts/__pycache__").mkdir()
        (directory / "scripts/__pycache__/run.pyc").write_bytes(b"fixture")
        (directory / "extra.pyc").write_bytes(b"fixture")
        self.assertFalse(self.recorder.record("PostToolUse"))
        self.assertEqual(len(self.rows()), 1)

    def test_skill_touch_is_not_a_body_change(self):
        directory = self.skill()
        self.recorder.record("SessionStart")
        os.utime(directory / "SKILL.md", ns=(1, 2))
        self.assertFalse(self.recorder.record("FileChanged"))
        self.assertEqual(len(self.rows()), 1)

    def test_supporting_files_are_stat_only(self):
        directory = self.skill()
        (directory / "support.bin").write_bytes(b"UNREAD_SUPPORT_FIXTURE")
        with mock.patch.object(RECORDER, "bounded_read", wraps=RECORDER.bounded_read) as reader:
            self.recorder.record("SessionStart")
        self.assertNotIn(directory / "support.bin", [call.args[0] for call in reader.call_args_list])
        self.assertNotIn("UNREAD_SUPPORT_FIXTURE", json.dumps(self.rows()))
        self.assertEqual(self.rows()[0]["after"]["folder_fingerprint_method"], "supporting_file_stat_metadata_bytecode_excluded")

    def test_canonical_claude_alias_is_deduplicated(self):
        directory = self.skill()
        alias = self.home / ".claude/skills/example"
        alias.parent.mkdir(parents=True)
        alias.symlink_to(directory, target_is_directory=True)
        self.recorder.record("SessionStart")
        self.assertEqual(len(self.rows()), 1)
        self.assertEqual(self.rows()[0]["scope"], "home_agents")

    def test_launch_from_home_does_not_duplicate_project_root(self):
        self.skill()
        recorder = RECORDER.Recorder(self.home, self.home, self.state)
        recorder.record("SessionStart")
        self.assertEqual(len(self.rows()), 1)

    def test_alias_add_remove_does_not_duplicate_supporting_fingerprint(self):
        directory = self.skill()
        (directory / "support.py").write_text("print('fixture')\n")
        self.recorder.record("SessionStart")
        fingerprint = self.rows()[0]["after"]["folder_fingerprint"]
        alias = self.home / ".claude/skills/example"
        alias.parent.mkdir(parents=True)
        alias.symlink_to(directory, target_is_directory=True)
        self.assertFalse(self.recorder.record("FileChanged"))
        alias.unlink()
        self.assertFalse(self.recorder.record("FileChanged"))
        self.assertEqual(len(self.rows()), 1)
        self.assertEqual(self.rows()[0]["after"]["folder_fingerprint"], fingerprint)

    def test_visiting_other_project_does_not_remove_previous_project_skills(self):
        self.skill(root=self.project / ".agents/skills")
        self.recorder.record("SessionStart")
        second = self.base / "second-project"
        second.mkdir()
        recorder = RECORDER.Recorder(self.home, second, self.state)
        recorder.record("SessionStart")
        self.assertEqual([row["event"] for row in self.rows()], ["observed"])

    def test_plugin_versions_are_distinct_and_activation_is_not_claimed(self):
        root = self.home / ".claude/plugins/cache/vendor/plugin"
        self.skill(root=root / "1.0/skills")
        self.skill(root=root / "2.0/skills")
        self.recorder.record("SessionStart")
        rows = self.rows()
        self.assertEqual(len(rows), 2)
        self.assertEqual(len({row["state_key"] for row in rows}), 2)
        self.assertTrue(all(row["scope"] == "claude_plugin" for row in rows))
        self.assertNotIn("enabled", json.dumps(rows))

    def test_public_lock_selected_source_fields_only(self):
        self.skill()
        lock = self.home / ".agents/.skill-lock.json"
        lock.write_text(json.dumps({"skills": {"example": {
            "source": "vendor/skills", "ref": "a" * 40, "skillFolderHash": "b" * 40,
            "ignored_private_field": "UNRETAINED_FIXTURE", "sourceUrl": "https://example.invalid/?private=fixture",
        }}}))
        self.recorder.record("SessionStart")
        source = self.rows()[0]["source"]
        self.assertEqual(source, {"repository": "vendor/skills", "ref": "a" * 40, "tree_sha": "b" * 40, "status": "known"})
        self.assertNotIn("UNRETAINED_FIXTURE", json.dumps(self.rows()))
        self.assertNotIn("sourceUrl", json.dumps(self.rows()))

    def test_plugin_name_collision_does_not_borrow_global_lock_source(self):
        self.skill()
        self.skill(root=self.home / ".claude/plugins/cache/vendor/plugin/1.0/skills")
        lock = self.home / ".agents/.skill-lock.json"
        lock.write_text(json.dumps({"skills": {"example": {"source": "other/skills", "ref": "a" * 40}}}))
        self.recorder.record("SessionStart")
        plugin = next(row for row in self.rows() if row["scope"] == "claude_plugin")
        self.assertEqual(plugin["source"]["status"], "unknown")
        self.assertIsNone(plugin["source"]["repository"])

    def test_changed_lock_identity_records_prior_and_next_pin(self):
        self.skill()
        lock = self.home / ".agents/.skill-lock.json"
        lock.write_text(json.dumps({"skills": {"example": {"source": "vendor/skills", "ref": "a" * 40}}}))
        self.recorder.record("SessionStart")
        lock.write_text(json.dumps({"skills": {"example": {"source": "vendor/skills", "ref": "b" * 40}}}))
        self.recorder.record("FileChanged")
        row = self.rows()[-1]
        self.assertEqual(row["action"], "change")
        self.assertEqual(row["before"]["source"]["ref"], "a" * 40)
        self.assertEqual(row["after"]["source"]["ref"], "b" * 40)

    def test_external_skill_symlink_is_never_read(self):
        directory = self.home / ".agents/skills/example"
        directory.mkdir(parents=True)
        excluded = self.base / "outside.json"
        excluded.write_text("UNREAD_EXTERNAL_FIXTURE")
        (directory / "SKILL.md").symlink_to(excluded)
        with mock.patch.object(RECORDER, "bounded_read", wraps=RECORDER.bounded_read) as reader:
            self.recorder.record("SessionStart")
        self.assertNotIn(excluded, [call.args[0] for call in reader.call_args_list])
        self.assertEqual(self.rows(), [])

    def test_journal_recovery_after_append_deduplicates(self):
        self.skill()
        real_atomic = RECORDER.atomic_json
        calls = 0

        def interrupt_after_append(path, value):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("synthetic interruption")
            real_atomic(path, value)

        with mock.patch.object(RECORDER, "atomic_json", side_effect=interrupt_after_append):
            with self.assertRaises(OSError):
                self.recorder.record("SessionStart")
        self.assertEqual(len(self.rows()), 1)
        self.assertTrue(self.recorder.record("SessionStart"))
        self.assertEqual(len(self.rows()), 1)
        self.assertNotIn("pending", json.loads(self.recorder.state_file.read_text()))

    def test_busy_lock_fails_open_without_touching_skill_state(self):
        self.skill()
        with self.recorder.locked():
            code, output = self.main({"hook_event_name": "PostToolUse"})
        self.assertEqual((code, output), (0, ""))
        self.assertEqual(self.rows(), [])
        self.assertEqual(self.rows("errors.jsonl")[0]["error_type"], "BlockingIOError")

    def test_malformed_hook_input_is_sanitized_and_fails_open(self):
        code, output = self.main(b'{"unexpected": UNRETAINED_PAYLOAD_FIXTURE}')
        self.assertEqual((code, output), (0, ""))
        errors = self.rows("errors.jsonl")
        self.assertEqual(errors[0]["error_type"], "JSONDecodeError")
        self.assertNotIn("UNRETAINED_PAYLOAD_FIXTURE", json.dumps(errors))

    def test_hook_unknown_payload_fields_are_not_logged(self):
        self.skill()
        code, output = self.main({"hook_event_name": "PostToolUse", "tool_input": {"command": "UNRETAINED_COMMAND_FIXTURE"}, "tool_response": "UNRETAINED_RESPONSE_FIXTURE"})
        self.assertEqual((code, output), (0, ""))
        self.assertNotIn("UNRETAINED", json.dumps(self.rows()))

    def test_metadata_status_has_only_supported_metadata_arguments(self):
        self.status.stop()
        with mock.patch.object(RECORDER.subprocess, "run", return_value=SimpleNamespace(returncode=1)) as run:
            self.skill()
            self.recorder.record("SessionStart")
            self.recorder.record("PostToolUse")
        run.assert_called_once()
        args = run.call_args.args[0]
        self.assertEqual(args[2:], ["--metadata-only", "--ledger", str(self.recorder.ledger), "--json", "--home", str(self.home)])
        self.assertEqual(run.call_args.kwargs["timeout"], 2.0)
        self.assertEqual(run.call_args.kwargs["cwd"], self.project)
        self.assertEqual(self.rows("errors.jsonl")[0]["exit_code"], 1)

    def test_instructions_audit_keeps_only_hash_and_sanitized_locator(self):
        file = self.project / "CLAUDE.md"
        file.write_text("UNRETAINED_INSTRUCTION_BODY_FIXTURE")
        code, output = self.main({"hook_event_name": "InstructionsLoaded", "file_path": str(file), "session_id": "fixture-session", "memory_type": "Project", "load_reason": "session_start"}, "instructions")
        self.assertEqual((code, output), (0, ""))
        row = self.rows("instructions-loaded.jsonl")[0]
        self.assertEqual(row["locator"], "<project>/CLAUDE.md")
        self.assertEqual(len(row["instruction_sha256"]), 64)
        self.assertNotIn("UNRETAINED", json.dumps(row))
        self.assertNotIn("decision", row)
        self.assertNotIn("fixture-session", json.dumps(row))

    def test_external_instruction_audit_does_not_read_content(self):
        file = self.base / "outside.md"
        file.write_text("UNREAD_EXTERNAL_INSTRUCTION_FIXTURE")
        with mock.patch.object(RECORDER, "bounded_read", wraps=RECORDER.bounded_read) as reader:
            self.main({"hook_event_name": "InstructionsLoaded", "file_path": str(file)}, "instructions")
        self.assertNotIn(file, [call.args[0] for call in reader.call_args_list])
        row = self.rows("instructions-loaded.jsonl")[0]
        self.assertIsNone(row["instruction_sha256"])
        self.assertEqual(row["scope_status"], "unknown")

    def test_instruction_fifo_fails_open_without_blocking(self):
        file = self.project / "blocked.md"
        os.mkfifo(file)
        code, output = self.main({"hook_event_name": "InstructionsLoaded", "file_path": str(file)}, "instructions")
        self.assertEqual((code, output), (0, ""))
        self.assertEqual(self.rows("errors.jsonl")[0]["error_type"], "ValueError")

    def test_watch_registration_has_no_ledger_or_decision(self):
        code, output = self.main({}, "watch-paths")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output), {"watchPaths": [str(self.home / ".agents/.skill-lock.json")]})
        self.assertFalse(self.state.exists())

    def test_state_directory_symlink_cannot_redirect_writes(self):
        destination = self.base / "unowned"
        destination.mkdir()
        self.state.symlink_to(destination, target_is_directory=True)
        code, output = self.main({"hook_event_name": "SessionStart"})
        self.assertEqual((code, output), (0, ""))
        self.assertEqual(list(destination.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
