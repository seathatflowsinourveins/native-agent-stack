"""Behavioral tests for the shipped copy of effort-default-guard.py
(adoption/hooks/claude/effort-default-guard.py), run under a temporary HOME
so no real ~/.claude/settings.json or notice file is ever read or written.
Each test invokes the guard exactly as Claude Code's SessionStart/SessionEnd
hooks do: stdin carries the hook event JSON, stdout is a JSON object
(systemMessage / a SessionStart-specific hookSpecificOutput), and the guard
always exits 0. Claude Code discards SessionEnd output, so a self-heal also
leaves a one-line notice that the next SessionStart shows once.
"""

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUARD_PATH = ROOT / "adoption/hooks/claude/effort-default-guard.py"
SHA256SUMS_PATH = ROOT / "adoption/hooks/claude/SHA256SUMS"
HOST_GUARD_PATH = Path.home() / ".claude" / "hooks" / "effort-default-guard.py"
# The guard reads this fixed managed-settings path; a host that has one would make
# the behavioral results depend on it, so those tests skip there.
MANAGED_SETTINGS = Path("/etc/claude-code/managed-settings.json")
HOST_INDEPENDENT = unittest.skipIf(MANAGED_SETTINGS.exists(),
                                   f"{MANAGED_SETTINGS} exists; guard results would depend on it")


def run_guard(home: Path, event: dict, env_extra: dict | None = None):
    env = dict(os.environ)
    env["HOME"] = str(home)
    env.pop("CLAUDE_CODE_EFFORT_LEVEL", None)
    if env_extra:
        env.update(env_extra)
    result = subprocess.run(
        [sys.executable, str(GUARD_PATH)],
        input=json.dumps(event),
        capture_output=True, text=True, timeout=10, env=env,
    )
    return result


def write_settings(home: Path, data: dict):
    claude_dir = home / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    (claude_dir / "settings.json").write_text(json.dumps(data))


def transcript_line(model: str, effort: str) -> str:
    return json.dumps({
        "type": "assistant",
        "message": {"model": model, "content": []},
        "effort": effort,
    }) + "\n"


def notice_path(home: Path) -> Path:
    return home / ".claude" / "effort-default-guard.notice"


def heal_opus_5_5(home: Path):
    """One SessionEnd that self-heals claude-opus-5-5 (it ran at medium with no saved level)."""
    transcript = home / "transcript.jsonl"
    transcript.write_text(transcript_line("claude-opus-5-5", "medium"))
    return run_guard(home, {"hook_event_name": "SessionEnd", "transcript_path": str(transcript), "cwd": str(home)})


def session_start(home: Path, model: str | None = "claude-opus-5-5"):
    event = {"hook_event_name": "SessionStart", "source": "startup", "cwd": str(home)}
    if model is not None:
        event["model"] = model
    return run_guard(home, event)


class GuardFileIntegrityTests(unittest.TestCase):
    def test_shipped_guard_is_verbatim(self):
        self.assertTrue(GUARD_PATH.is_file())
        if not HOST_GUARD_PATH.is_file():
            self.skipTest("host guard not present on this machine")
        self.assertEqual(GUARD_PATH.read_bytes(), HOST_GUARD_PATH.read_bytes(),
                          "adoption/hooks/claude/effort-default-guard.py must be a verbatim host copy")

    def test_sha256sums_matches_the_shipped_file(self):
        self.assertTrue(SHA256SUMS_PATH.is_file())
        digest = hashlib.sha256(GUARD_PATH.read_bytes()).hexdigest()
        text = SHA256SUMS_PATH.read_text()
        self.assertIn(digest, text)
        self.assertIn("effort-default-guard.py", text)


@HOST_INDEPENDENT
class SessionStartWarningTests(unittest.TestCase):
    def test_warns_for_an_unsaved_newer_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            write_settings(home, {"effortLevel": "xhigh"})  # top-level effortLevel does not apply to opus-5-5
            result = run_guard(home, {
                "hook_event_name": "SessionStart",
                "model": "claude-opus-5-5",
                "cwd": tmp,
            })
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertIn("Effort default check", payload["systemMessage"])
            self.assertIn("claude-opus-5-5", payload["systemMessage"])
            self.assertEqual(payload["hookSpecificOutput"]["hookEventName"], "SessionStart")

    def test_warns_for_a_project_effortlevel_of_medium(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            write_settings(home, {})
            project_dir = home / "project"
            (project_dir / ".claude").mkdir(parents=True)
            (project_dir / ".claude" / "settings.json").write_text(json.dumps({"effortLevel": "medium"}))
            result = run_guard(home, {
                "hook_event_name": "SessionStart",
                "model": "claude-opus-5-5",
                "cwd": str(project_dir),
            })
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertIn("medium", payload["systemMessage"])

    def test_warns_for_claude_code_effort_level_env_medium(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            write_settings(home, {"effortLevel": "xhigh"})
            result = run_guard(home, {
                "hook_event_name": "SessionStart",
                "model": "claude-opus-5-5",
                "cwd": tmp,
            }, env_extra={"CLAUDE_CODE_EFFORT_LEVEL": "medium"})
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertIn("medium", payload["systemMessage"])
            self.assertIn("CLAUDE_CODE_EFFORT_LEVEL", payload["systemMessage"])

    def test_silent_under_ultracode(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            write_settings(home, {"ultracode": True})
            result = run_guard(home, {
                "hook_event_name": "SessionStart",
                "model": "claude-opus-5-5",
                "cwd": tmp,
            })
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "")

    def test_silent_for_a_saved_xhigh_modelsettings_level(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            write_settings(home, {"modelSettings": {"claude-opus-5-5": {"effortLevel": "xhigh"}}})
            result = run_guard(home, {
                "hook_event_name": "SessionStart",
                "model": "claude-opus-5-5",
                "cwd": tmp,
            })
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "")


@HOST_INDEPENDENT
class SessionEndSelfHealTests(unittest.TestCase):
    def test_self_heals_once_when_no_level_was_saved(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            write_settings(home, {})
            transcript = Path(tmp) / "transcript.jsonl"
            transcript.write_text(transcript_line("claude-opus-5-5", "medium"))
            result = run_guard(home, {
                "hook_event_name": "SessionEnd",
                "transcript_path": str(transcript),
                "cwd": tmp,
            })
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertIn("Saved modelSettings.claude-opus-5-5.effortLevel", payload["systemMessage"])
            saved = json.loads((home / ".claude" / "settings.json").read_text())
            self.assertEqual(saved["modelSettings"]["claude-opus-5-5"]["effortLevel"], "xhigh")
            # Claude Code discards the stdout above, so the save also leaves a one-line notice.
            lines = notice_path(home).read_text().splitlines()
            self.assertEqual(len(lines), 1)
            self.assertIn("modelSettings.claude-opus-5-5.effortLevel = xhigh", lines[0])
            self.assertEqual(notice_path(home).stat().st_mode & 0o777, 0o600)

    def test_never_overwrites_a_saved_level(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            # A person or a prior run deliberately saved a non-default level;
            # the guard must never touch it even though the session ran below xhigh.
            write_settings(home, {"modelSettings": {"claude-opus-5-5": {"effortLevel": "medium"}}})
            transcript = Path(tmp) / "transcript.jsonl"
            transcript.write_text(transcript_line("claude-opus-5-5", "medium"))
            result = run_guard(home, {
                "hook_event_name": "SessionEnd",
                "transcript_path": str(transcript),
                "cwd": tmp,
            })
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "")
            saved = json.loads((home / ".claude" / "settings.json").read_text())
            self.assertEqual(saved["modelSettings"]["claude-opus-5-5"]["effortLevel"], "medium")
            self.assertFalse(notice_path(home).exists())

    def test_heals_only_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            write_settings(home, {})
            transcript = Path(tmp) / "transcript.jsonl"
            transcript.write_text(transcript_line("claude-opus-5-5", "medium"))
            event = {"hook_event_name": "SessionEnd", "transcript_path": str(transcript), "cwd": tmp}
            first = run_guard(home, event)
            self.assertIn("Saved modelSettings.claude-opus-5-5.effortLevel", json.loads(first.stdout)["systemMessage"])
            after_first = (home / ".claude" / "settings.json").read_bytes()
            second = run_guard(home, event)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(second.stdout.strip(), "")
            self.assertEqual((home / ".claude" / "settings.json").read_bytes(), after_first)
            self.assertEqual(len(notice_path(home).read_text().splitlines()), 1)

    def test_respects_an_explicit_lower_session_effort(self):
        # The model already resolves to xhigh from settings (a legacy model covered by the
        # user top-level effortLevel), so a medium session was an explicit --effort/`/effort`
        # choice: no modelSettings entry is written.
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            write_settings(home, {"effortLevel": "xhigh"})
            transcript = Path(tmp) / "transcript.jsonl"
            transcript.write_text(transcript_line("claude-sonnet-5", "low"))
            result = run_guard(home, {"hook_event_name": "SessionEnd", "transcript_path": str(transcript), "cwd": tmp})
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "")
            saved = json.loads((home / ".claude" / "settings.json").read_text())
            self.assertNotIn("modelSettings", saved)
            self.assertFalse(notice_path(home).exists())

    def test_respects_an_explicit_lower_effort_under_ultracode(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            write_settings(home, {"ultracode": True})
            transcript = Path(tmp) / "transcript.jsonl"
            transcript.write_text(transcript_line("claude-opus-5-5", "low"))
            result = run_guard(home, {"hook_event_name": "SessionEnd", "transcript_path": str(transcript), "cwd": tmp})
            self.assertEqual(result.stdout.strip(), "")
            self.assertNotIn("modelSettings", json.loads((home / ".claude" / "settings.json").read_text()))
            self.assertFalse(notice_path(home).exists())


@HOST_INDEPENDENT
class SessionEndNoticeHandoffTests(unittest.TestCase):
    """SessionEnd output never reaches the user (hooks reference, SessionEnd), so the
    self-heal notice travels in a one-line file to the next SessionStart."""

    def test_the_next_session_start_shows_the_session_end_notice(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            write_settings(home, {})
            end = heal_opus_5_5(home)
            self.assertEqual(end.returncode, 0, end.stderr)
            self.assertTrue(notice_path(home).is_file())
            start = session_start(home)
            self.assertEqual(start.returncode, 0, start.stderr)
            payload = json.loads(start.stdout)
            self.assertIn("modelSettings.claude-opus-5-5.effortLevel = xhigh", payload["systemMessage"])
            self.assertEqual(payload["hookSpecificOutput"],
                             {"hookEventName": "SessionStart", "additionalContext": payload["systemMessage"]})
            # The heal saved xhigh, so this start has no predictive warning of its own.
            self.assertNotIn("Effort default check", payload["systemMessage"])
            self.assertFalse(notice_path(home).exists())
            self.assertEqual(sorted(p.name for p in (home / ".claude").iterdir()), ["settings.json"])

    def test_the_notice_is_consumed_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            write_settings(home, {})
            heal_opus_5_5(home)
            first = session_start(home)
            self.assertIn("Effort default", json.loads(first.stdout)["systemMessage"])
            second = session_start(home)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(second.stdout.strip(), "")
            self.assertFalse(notice_path(home).exists())

    def test_a_session_start_without_a_model_keeps_the_notice(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            write_settings(home, {})
            heal_opus_5_5(home)
            unreported = session_start(home, model=None)
            self.assertEqual(unreported.returncode, 0, unreported.stderr)
            self.assertEqual(unreported.stdout.strip(), "")
            self.assertTrue(notice_path(home).is_file())
            reported = session_start(home)
            self.assertIn("modelSettings.claude-opus-5-5.effortLevel = xhigh",
                          json.loads(reported.stdout)["systemMessage"])
            self.assertFalse(notice_path(home).exists())

    def test_the_notice_and_a_warning_share_one_json_object(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            write_settings(home, {})
            heal_opus_5_5(home)
            start = session_start(home, model="claude-sonnet-5")  # no saved level for this model
            self.assertEqual(start.returncode, 0, start.stderr)
            payload = json.loads(start.stdout)  # one object: a second print would not parse
            message = payload["systemMessage"]
            self.assertIn("modelSettings.claude-opus-5-5.effortLevel = xhigh", message)
            self.assertIn("Effort default check: claude-sonnet-5", message)
            self.assertEqual(payload["hookSpecificOutput"]["additionalContext"], message)

    def test_an_unwritable_notice_path_still_saves_and_exits_0(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            write_settings(home, {})
            notice_path(home).mkdir()  # not a file: the append fails, the heal must not
            end = heal_opus_5_5(home)
            self.assertEqual(end.returncode, 0, end.stderr)
            self.assertIn("Saved modelSettings.claude-opus-5-5.effortLevel", json.loads(end.stdout)["systemMessage"])
            saved = json.loads((home / ".claude" / "settings.json").read_text())
            self.assertEqual(saved["modelSettings"]["claude-opus-5-5"]["effortLevel"], "xhigh")
            start = session_start(home)
            self.assertEqual(start.returncode, 0, start.stderr)
            self.assertEqual(start.stdout.strip(), "")
            self.assertTrue(notice_path(home).is_dir())


if __name__ == "__main__":
    unittest.main()
