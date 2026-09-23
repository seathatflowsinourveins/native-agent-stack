"""Behavioral tests for the shipped copy of effort-default-guard.py
(adoption/hooks/claude/effort-default-guard.py), run under a temporary HOME
so no real ~/.claude/settings.json is ever read or written. Each test invokes
the guard exactly as Claude Code's SessionStart/SessionEnd hooks do: stdin
carries the hook event JSON, stdout is a JSON object (systemMessage / a
SessionStart-specific hookSpecificOutput), and the guard always exits 0.
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


if __name__ == "__main__":
    unittest.main()
