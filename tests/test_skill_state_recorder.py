"""Local integration fixtures for the passive S3 recorder, not client acceptance."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import stat
import subprocess
import sys
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
        self.recorder = RECORDER.Recorder(self.home, self.project, self.state, environment={})
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

    def main(self, payload, mode="record", environment=None):
        content = json.dumps(payload).encode() if isinstance(payload, dict) else payload
        stdin = io.TextIOWrapper(io.BytesIO(content))
        output = io.StringIO()
        with mock.patch.object(RECORDER.sys, "stdin", stdin), contextlib.redirect_stdout(output):
            result = RECORDER.main([
                "--home", str(self.home), "--project-dir", str(self.project), "--state-dir", str(self.state), "--mode", mode,
            ], environment={} if environment is None else environment)
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
        self.assertEqual(row["after"]["locator"], "<home_agents>/example/SKILL.md")

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
        recorder = RECORDER.Recorder(self.home, self.home, self.state, environment={})
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
        recorder = RECORDER.Recorder(self.home, second, self.state, environment={})
        recorder.record("SessionStart")
        self.assertEqual([row["event"] for row in self.rows()], ["observed"])

    def profile(self, label):
        claude_root = self.base / (label + "-claude")
        codex_root = self.base / (label + "-codex")
        claude_root.mkdir()
        codex_root.mkdir()
        environment = {"CLAUDE_CONFIG_DIR": str(claude_root), "CODEX_HOME": str(codex_root)}
        recorder = RECORDER.Recorder(self.home, self.project, self.state, environment=environment)
        return recorder, claude_root, codex_root, environment

    def test_selected_native_roots_include_skills_and_plugin_caches_without_default_fallback(self):
        recorder, claude_root, codex_root, _ = self.profile("custom")
        self.skill("default-claude", root=self.home / ".claude/skills")
        self.skill("default-codex", root=self.home / ".codex/skills")
        self.skill("custom-claude", root=claude_root / "skills")
        self.skill("custom-codex", root=codex_root / "skills")
        self.skill("custom-claude-plugin", root=claude_root / "plugins/cache/vendor/plugin/1.0/skills")
        self.skill("custom-codex-plugin", root=codex_root / "plugins/cache/vendor/plugin/1.0/skills")
        recorder.record("SessionStart")
        self.assertEqual({row["skill_name"] for row in self.rows()},
                         {"custom-claude", "custom-codex", "custom-claude-plugin", "custom-codex-plugin"})
        self.assertEqual({row["scope"] for row in self.rows()}, {"home_claude", "home_codex", "claude_plugin", "codex_plugin"})

    def test_two_profile_hashes_survive_visits_without_physical_removals(self):
        first, first_claude, _, _ = self.profile("one")
        second, second_claude, _, _ = self.profile("two")
        self.skill(root=first_claude / "skills", body="Profile one public fixture.\n")
        self.skill(root=second_claude / "skills", body="Profile two public fixture.\n")
        first.record("SessionStart")
        second.record("SessionStart")
        self.assertFalse(first.record("SessionStart"))
        rows = self.rows()
        self.assertEqual([row["event"] for row in rows], ["observed", "observed"])
        self.assertEqual(len({row["after"]["skill_md_sha256"] for row in rows}), 2)
        self.assertEqual(len({row["state_key"] for row in rows}), 2)
        self.assertNotIn(str(self.base), json.dumps(rows))

    def test_two_profile_aliases_share_one_physical_transition_stream(self):
        first, first_claude, _, _ = self.profile("one")
        second, second_claude, _, _ = self.profile("two")
        directory = self.skill()
        for root in (first_claude, second_claude):
            alias = root / "skills/example"
            alias.parent.mkdir()
            alias.symlink_to(directory, target_is_directory=True)
        first.record("SessionStart")
        self.assertFalse(second.record("SessionStart"))
        self.assertEqual(len(self.rows()), 1)
        (directory / "SKILL.md").write_text("---\nname: example\n---\nChanged public fixture.\n")
        self.assertTrue(second.record("FileChanged"))
        self.assertFalse(first.record("FileChanged"))
        (directory / "SKILL.md").unlink()
        self.assertTrue(first.record("FileChanged"))
        self.assertFalse(second.record("FileChanged"))
        self.assertEqual([row["event"] for row in self.rows()], ["observed", "changed", "removed"])
        self.assertEqual(len({row["state_key"] for row in self.rows()}), 1)

    def test_redirected_or_relative_native_roots_fail_open_as_unknown_without_fallback(self):
        public = self.base / "public-other"
        public.mkdir()
        alias = self.base / "redirected-profile"
        alias.symlink_to(public, target_is_directory=True)
        self.skill(root=self.home / ".claude/skills")
        for environment in ({"CLAUDE_CONFIG_DIR": "relative-profile"}, {"CODEX_HOME": str(alias)},
                            {"CODEX_HOME": str(self.base / "missing-profile")}):
            with self.subTest(environment=environment):
                code, output = self.main({"hook_event_name": "SessionStart"}, environment=environment)
                self.assertEqual((code, output), (0, ""))
                self.assertFalse(self.rows())
        self.assertTrue(self.rows("errors.jsonl"))

    def test_selected_native_instruction_roots_hash_only_plain_sources(self):
        _, claude_root, codex_root, environment = self.profile("custom")
        user_claude = claude_root / "CLAUDE.md"
        user_agents = codex_root / "AGENTS.md"
        other = codex_root / "public-other.md"
        default = self.home / ".claude/CLAUDE.md"
        default.parent.mkdir()
        for path in (user_claude, user_agents, other, default):
            path.write_text("Unretained public instruction fixture.\n")
        for path in (user_claude, user_agents, other, default):
            self.main({"hook_event_name": "InstructionsLoaded", "file_path": str(path)}, "instructions", environment=environment)
        rows = self.rows("instructions-loaded.jsonl")
        self.assertEqual([row["scope_status"] for row in rows], ["known", "known", "unknown", "unknown"])
        self.assertTrue(all(str(self.base) not in json.dumps(row) for row in rows))

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
        self.assertEqual(run.call_args.kwargs["env"], {"PATH": os.defpath, "PYTHONDONTWRITEBYTECODE": "1",
                         "CLAUDE_CONFIG_DIR": str(self.home / ".claude"), "CODEX_HOME": str(self.home / ".codex")})
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

    def run_fixture_hook(self, payload, *, state_dir, mode="record"):
        content = json.dumps(payload).encode() if isinstance(payload, dict) else payload
        result = subprocess.run([
            sys.executable, str(ROOT / "tools/adoption/skill_state_recorder.py"),
            "--home", str(self.home), "--project-dir", str(self.project),
            "--state-dir", str(state_dir), "--mode", mode,
        ], input=content, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=2, cwd=self.project,
            env={"PATH": os.defpath, "PYTHONDONTWRITEBYTECODE": "1", "TMPDIR": str(self.base)})
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"")
        self.assertEqual(result.stderr, b"")

    def test_real_fifo_state_paths_fail_open_under_subprocess_timeout(self):
        self.skill()
        instruction = self.project / "CLAUDE.md"
        instruction.write_text("Public fixture instruction.\n")
        cases = [
            ("ledger.jsonl", "record", {"hook_event_name": "SessionStart"}),
            ("state.json", "record", {"hook_event_name": "SessionStart"}),
            ("state.json.next", "record", {"hook_event_name": "SessionStart"}),
            ("recorder.lock", "record", {"hook_event_name": "SessionStart"}),
            ("instructions-loaded.jsonl", "instructions", {"hook_event_name": "InstructionsLoaded", "file_path": str(instruction)}),
            ("errors.jsonl", "record", b"MALFORMED_FIXTURE_INPUT"),
        ]
        for number, (filename, mode, payload) in enumerate(cases):
            for reader_present in (False, True):
                with self.subTest(filename=filename, reader_present=reader_present):
                    case_dir = self.base / f"fifo-{number}-{reader_present}"
                    case_dir.mkdir()
                    poisoned = case_dir / filename
                    os.mkfifo(poisoned)
                    reader = os.open(poisoned, os.O_RDONLY | os.O_NONBLOCK) if reader_present else None
                    try:
                        self.run_fixture_hook(payload, state_dir=case_dir, mode=mode)
                        self.assertTrue(stat.S_ISFIFO(poisoned.lstat().st_mode))
                        if reader is not None:
                            self.assertEqual(os.read(reader, 1024), b"")
                        error_file = case_dir / "errors.jsonl"
                        if filename != "errors.jsonl":
                            rows = [json.loads(line) for line in error_file.read_text().splitlines()]
                            self.assertTrue(rows)
                            self.assertIn(rows[-1]["error_type"], {"ValueError", "OSError"})
                    finally:
                        if reader is not None:
                            os.close(reader)

    def test_real_instruction_fifo_is_rejected_in_subprocess(self):
        instruction = self.project / "named-pipe.md"
        os.mkfifo(instruction)
        self.run_fixture_hook({"hook_event_name": "InstructionsLoaded", "file_path": str(instruction)}, state_dir=self.state, mode="instructions")
        self.assertEqual(self.rows("errors.jsonl")[0]["error_type"], "ValueError")

    def test_prevalidation_rejection_preserves_atomic_sentinel_and_closes_fd(self):
        self.state.mkdir()
        target = self.state / "state.json"
        temporary = self.state / "state.json.next"
        temporary.write_bytes(b"UNTRUNCATED_FIXTURE_SENTINEL")
        original_open = os.open
        descriptors = []

        def tracked_open(*args, **kwargs):
            self.assertFalse(args[1] & os.O_TRUNC)
            descriptor = original_open(*args, **kwargs)
            descriptors.append(descriptor)
            return descriptor

        with mock.patch.object(RECORDER.os, "open", side_effect=tracked_open), mock.patch.object(RECORDER.os, "fstat", return_value=SimpleNamespace(st_mode=stat.S_IFIFO)), mock.patch.object(RECORDER.os, "fdopen") as fdopen, mock.patch.object(RECORDER.os, "ftruncate") as truncate:
            with self.assertRaises(ValueError):
                RECORDER.atomic_json(target, {"fixture": True})
        fdopen.assert_not_called()
        truncate.assert_not_called()
        self.assertEqual(temporary.read_bytes(), b"UNTRUNCATED_FIXTURE_SENTINEL")
        self.assertFalse(target.exists())
        self.assertEqual(len(descriptors), 1)
        with self.assertRaises(OSError):
            os.fstat(descriptors[0])

    def test_fdopen_failure_closes_validated_descriptor(self):
        file = self.base / "regular.txt"
        file.write_text("Public fixture.\n")
        original_open = os.open
        descriptors = []

        def tracked_open(*args, **kwargs):
            descriptor = original_open(*args, **kwargs)
            descriptors.append(descriptor)
            return descriptor

        with mock.patch.object(RECORDER.os, "open", side_effect=tracked_open), mock.patch.object(RECORDER.os, "fdopen", side_effect=ValueError("synthetic fdopen failure")):
            with self.assertRaises(ValueError):
                RECORDER.bounded_read(file, 1024)
        self.assertEqual(len(descriptors), 1)
        with self.assertRaises(OSError):
            os.fstat(descriptors[0])

    def test_missing_required_flag_never_falls_back_to_zero(self):
        with mock.patch.object(RECORDER.os, "O_NOFOLLOW", 0), mock.patch.object(RECORDER.os, "open") as opened:
            with self.assertRaises(NotImplementedError):
                RECORDER.bounded_read(self.base / "fixture", 1)
        opened.assert_not_called()

    def test_fifo_ledger_failure_recovers_pending_without_duplicate_rows(self):
        self.recorder.record("SessionStart")
        self.skill()
        os.mkfifo(self.recorder.ledger)
        self.run_fixture_hook({"hook_event_name": "PostToolUse"}, state_dir=self.state)
        self.assertIn("pending", json.loads(self.recorder.state_file.read_text()))
        self.recorder.ledger.unlink()
        self.run_fixture_hook({"hook_event_name": "PostToolUse"}, state_dir=self.state)
        self.run_fixture_hook({"hook_event_name": "PostToolUse"}, state_dir=self.state)
        self.assertEqual([row["action"] for row in self.rows()], ["add"])
        self.assertNotIn("pending", json.loads(self.recorder.state_file.read_text()))


if __name__ == "__main__":
    unittest.main()
