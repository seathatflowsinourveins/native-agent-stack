"""Behavioral tests for the shipped copy of effort-default-guard.py
(adoption/hooks/claude/effort-default-guard.py), run under a temporary HOME
so no real ~/.claude/settings.json or notice file is ever read or written.
Each test invokes the guard exactly as Claude Code's SessionStart/SessionEnd
hooks do: stdin carries the hook event JSON, stdout is a JSON object
(systemMessage / a SessionStart-specific hookSpecificOutput), and the guard
always exits 0. Claude Code discards SessionEnd output, so a self-heal also
leaves a one-line notice file that the next SessionStart shows once. The
notice tests cover every claim path: a lost claim race, simultaneous starts, a
notice written during a claim, a failed print, malformed settings, stale
markers and a symlinked notice; the race cases inject the interleaving by
patching os.rename in a driver process that imports the shipped guard.
"""

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
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
# A CI runner's home holds no installed guard of its own; the host copy is compared only on a host.
IN_CI = os.environ.get("GITHUB_ACTIONS") == "true" or os.environ.get("CI", "").lower() == "true"
EIGHT_DAYS = 8 * 24 * 3600

# Imports the shipped guard in a separate process. "leave" calls leave_notice(argv[3]); any other
# mode runs main() on stdin with os.rename patched so that, at the first claim of a notice, either
# another SessionStart claims it first ("lose-race") or a SessionEnd leaves a new notice
# ("end-during-claim"). The guard's own rename calls still run.
DRIVER = r"""
import importlib.util, os, sys
spec = importlib.util.spec_from_file_location("guard", sys.argv[1])
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)
mode = sys.argv[2]
if mode == "leave":
    guard.leave_notice(sys.argv[3])
    sys.exit(0)
real_rename, state = os.rename, {"done": False}
def rename(src, dst):
    if src.endswith(".notice") and ".claimed-" in dst and not state["done"]:
        state["done"] = True
        if mode == "lose-race":
            real_rename(src, src + ".claimed-other")
        elif mode == "end-during-claim":
            guard.leave_notice("Notice written while the claim ran.")
    return real_rename(src, dst)
os.rename = rename
try:
    guard.main()
except Exception:
    pass
sys.exit(0)
"""


def guard_env(home: Path, env_extra: dict | None = None) -> dict:
    env = dict(os.environ)
    env["HOME"] = str(home)
    env.pop("CLAUDE_CODE_EFFORT_LEVEL", None)
    if env_extra:
        env.update(env_extra)
    return env


def run_guard(home: Path, event: dict, env_extra: dict | None = None):
    result = subprocess.run(
        [sys.executable, str(GUARD_PATH)],
        input=json.dumps(event),
        capture_output=True, text=True, timeout=10, env=guard_env(home, env_extra),
    )
    return result


def run_driver(home: Path, mode: str, event: dict | None = None, *args: str):
    return subprocess.run(
        [sys.executable, "-c", DRIVER, str(GUARD_PATH), mode, *args],
        input=json.dumps(event) if event is not None else "",
        capture_output=True, text=True, timeout=10, env=guard_env(home),
    )


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


def notices_dir(home: Path) -> Path:
    return home / ".claude" / "effort-default-guard.notices"


def entries(home: Path) -> list[str]:
    """Every file in the notices directory: pending notices, claimed files and temporary files."""
    directory = notices_dir(home)
    return sorted(p.name for p in directory.iterdir()) if directory.is_dir() else []


def pending(home: Path) -> list[Path]:
    directory = notices_dir(home)
    return sorted(p for p in directory.iterdir() if p.name.endswith(".notice")) if directory.is_dir() else []


def leave(home: Path, message: str) -> Path:
    """Leave a notice through the guard's own writer and return its path."""
    before = set(pending(home))
    result = run_driver(home, "leave", None, message)
    assert result.returncode == 0, result.stderr
    (added,) = set(pending(home)) - before
    return added


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
        if IN_CI:
            self.skipTest("running in CI: a runner has no host install of the guard to compare")
        if not HOST_GUARD_PATH.is_file():
            self.skipTest(f"no host guard at {HOST_GUARD_PATH}; "
                          "tools/adoption/install_claude_profile.py --only guard installs it")
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
            # Claude Code discards the stdout above, so the save also leaves a one-line notice file.
            (notice,) = pending(home)
            lines = notice.read_text().splitlines()
            self.assertEqual(len(lines), 1)
            self.assertIn("modelSettings.claude-opus-5-5.effortLevel = xhigh", lines[0])
            self.assertEqual(notice.stat().st_mode & 0o777, 0o600)
            self.assertEqual(notices_dir(home).stat().st_mode & 0o077, 0)  # private directory
            self.assertEqual(entries(home), [notice.name])  # no temporary file is left behind

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
            self.assertEqual(entries(home), [])

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
            self.assertEqual(len(pending(home)), 1)

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
            self.assertEqual(entries(home), [])

    def test_respects_an_explicit_lower_effort_under_ultracode(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            write_settings(home, {"ultracode": True})
            transcript = Path(tmp) / "transcript.jsonl"
            transcript.write_text(transcript_line("claude-opus-5-5", "low"))
            result = run_guard(home, {"hook_event_name": "SessionEnd", "transcript_path": str(transcript), "cwd": tmp})
            self.assertEqual(result.stdout.strip(), "")
            self.assertNotIn("modelSettings", json.loads((home / ".claude" / "settings.json").read_text()))
            self.assertEqual(entries(home), [])


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
            self.assertEqual(len(pending(home)), 1)
            start = session_start(home)
            self.assertEqual(start.returncode, 0, start.stderr)
            payload = json.loads(start.stdout)
            self.assertIn("modelSettings.claude-opus-5-5.effortLevel = xhigh", payload["systemMessage"])
            self.assertEqual(payload["hookSpecificOutput"],
                             {"hookEventName": "SessionStart", "additionalContext": payload["systemMessage"]})
            # The heal saved xhigh, so this start has no predictive warning of its own.
            self.assertNotIn("Effort default check", payload["systemMessage"])
            self.assertEqual(entries(home), [])  # claimed, printed, then deleted
            self.assertEqual(sorted(p.name for p in (home / ".claude").iterdir()),
                             ["effort-default-guard.notices", "settings.json"])

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
            self.assertEqual(entries(home), [])

    def test_a_session_start_without_a_model_keeps_the_notice(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            write_settings(home, {})
            heal_opus_5_5(home)
            unreported = session_start(home, model=None)
            self.assertEqual(unreported.returncode, 0, unreported.stderr)
            self.assertEqual(unreported.stdout.strip(), "")
            self.assertEqual(len(pending(home)), 1)
            reported = session_start(home)
            self.assertIn("modelSettings.claude-opus-5-5.effortLevel = xhigh",
                          json.loads(reported.stdout)["systemMessage"])
            self.assertEqual(entries(home), [])

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

    def test_notices_are_shown_oldest_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            write_settings(home, {"modelSettings": {"claude-opus-5-5": {"effortLevel": "xhigh"}}})
            leave(home, "First notice.")
            leave(home, "Second notice.")
            start = session_start(home)
            self.assertEqual(json.loads(start.stdout)["systemMessage"], "First notice.\nSecond notice.")
            self.assertEqual(entries(home), [])

    def test_an_unwritable_notice_path_still_saves_and_exits_0(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            write_settings(home, {})
            notices_dir(home).write_text("not a directory\n")  # the notice cannot be written; the heal must be
            end = heal_opus_5_5(home)
            self.assertEqual(end.returncode, 0, end.stderr)
            self.assertIn("Saved modelSettings.claude-opus-5-5.effortLevel", json.loads(end.stdout)["systemMessage"])
            saved = json.loads((home / ".claude" / "settings.json").read_text())
            self.assertEqual(saved["modelSettings"]["claude-opus-5-5"]["effortLevel"], "xhigh")
            start = session_start(home)
            self.assertEqual(start.returncode, 0, start.stderr)
            self.assertEqual(start.stdout.strip(), "")
            self.assertEqual(notices_dir(home).read_text(), "not a directory\n")


@HOST_INDEPENDENT
class NoticeFailSafeTests(unittest.TestCase):
    """A notice is deleted only after it was printed; everything else keeps it or drops it
    whole, and the guard still exits 0."""

    def test_malformed_settings_cost_the_warning_not_the_notice(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            write_settings(home, {})
            heal_opus_5_5(home)
            # resolve() raises TypeError on an unhashable maxEffortLevel; it runs before the claim.
            write_settings(home, {"maxEffortLevel": ["high"]})
            start = session_start(home)
            self.assertEqual(start.returncode, 0, start.stderr)
            message = json.loads(start.stdout)["systemMessage"]
            self.assertIn("modelSettings.claude-opus-5-5.effortLevel = xhigh", message)
            self.assertNotIn("Effort default check", message)
            self.assertEqual(entries(home), [])

    def test_a_failed_print_gives_the_notice_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            write_settings(home, {})
            heal_opus_5_5(home)
            (notice,) = pending(home)
            unwritable = home / "stdout"
            unwritable.write_text("")
            event = {"hook_event_name": "SessionStart", "source": "startup", "cwd": tmp, "model": "claude-opus-5-5"}
            with unwritable.open("rb") as read_only:  # the guard's write to stdout fails
                failed = subprocess.run([sys.executable, str(GUARD_PATH)], input=json.dumps(event).encode(),
                                        stdout=read_only, stderr=subprocess.PIPE, timeout=10, env=guard_env(home))
            self.assertEqual(failed.returncode, 0, failed.stderr)
            self.assertEqual(entries(home), [notice.name])  # renamed back under its own name
            shown = session_start(home)
            self.assertIn("modelSettings.claude-opus-5-5.effortLevel = xhigh",
                          json.loads(shown.stdout)["systemMessage"])
            self.assertEqual(entries(home), [])

    def test_markers_older_than_7_days_are_deleted_unseen(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            write_settings(home, {"modelSettings": {"claude-opus-5-5": {"effortLevel": "xhigh"}}})
            stale = leave(home, "A stale notice.")
            fresh = leave(home, "A fresh notice.")
            directory = notices_dir(home)
            stale_claim = directory / "1-1-aaaaaaaa.notice.claimed-1-bbbbbbbb"  # a start killed mid-claim
            stale_temp = directory / ".stale.tmp"  # a SessionEnd killed mid-write
            live_claim = directory / "2-2-cccccccc.notice.claimed-2-dddddddd"  # a start still printing
            for path in (stale_claim, stale_temp, live_claim):
                path.write_text("Must never be shown.\n")
            old = time.time() - EIGHT_DAYS
            for path in (stale, stale_claim, stale_temp):
                os.utime(path, (old, old))
            start = session_start(home)
            self.assertEqual(start.returncode, 0, start.stderr)
            self.assertEqual(json.loads(start.stdout)["systemMessage"], "A fresh notice.")
            self.assertEqual(entries(home), [live_claim.name])
            self.assertFalse(fresh.exists())

    def test_a_claim_that_loses_the_race_emits_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            write_settings(home, {"modelSettings": {"claude-opus-5-5": {"effortLevel": "xhigh"}}})
            notice = leave(home, "Claimed by the other start.")
            event = {"hook_event_name": "SessionStart", "source": "startup", "cwd": tmp, "model": "claude-opus-5-5"}
            lost = run_driver(home, "lose-race", event)
            self.assertEqual(lost.returncode, 0, lost.stderr)
            self.assertEqual(lost.stdout.strip(), "")
            # The winner's claimed file is untouched: it deletes it after printing.
            self.assertEqual(entries(home), [notice.name + ".claimed-other"])

    def test_simultaneous_starts_show_a_notice_exactly_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            write_settings(home, {"modelSettings": {"claude-opus-5-5": {"effortLevel": "xhigh"}}})
            leave(home, "Shown by exactly one start.")
            event = json.dumps({"hook_event_name": "SessionStart", "source": "startup", "cwd": tmp,
                                "model": "claude-opus-5-5"})
            starts = [subprocess.Popen([sys.executable, str(GUARD_PATH)], stdin=subprocess.PIPE,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                       env=guard_env(home)) for _ in range(8)]
            outputs = [start.communicate(event, timeout=20) for start in starts]
            self.assertEqual([start.returncode for start in starts], [0] * 8)
            shown = [out for out, _ in outputs if out.strip()]
            self.assertEqual(len(shown), 1, outputs)
            self.assertEqual(json.loads(shown[0])["systemMessage"], "Shown by exactly one start.")
            self.assertEqual(entries(home), [])

    def test_a_notice_written_during_a_claim_waits_for_the_next_start(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            write_settings(home, {"modelSettings": {"claude-opus-5-5": {"effortLevel": "xhigh"}}})
            leave(home, "Written before the start.")
            event = {"hook_event_name": "SessionStart", "source": "startup", "cwd": tmp, "model": "claude-opus-5-5"}
            first = run_driver(home, "end-during-claim", event)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(json.loads(first.stdout)["systemMessage"], "Written before the start.")
            self.assertEqual(len(pending(home)), 1)  # not appended to the claimed file, not lost
            second = session_start(home)
            self.assertEqual(json.loads(second.stdout)["systemMessage"], "Notice written while the claim ran.")
            self.assertEqual(entries(home), [])

    def test_a_symlinked_notice_is_never_followed(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            write_settings(home, {"modelSettings": {"claude-opus-5-5": {"effortLevel": "xhigh"}}})
            secret = home / "secret.txt"
            secret.write_text("SECRET-CONTENT\n")
            notices_dir(home).mkdir(mode=0o700)
            (notices_dir(home) / "1-1-aaaaaaaa.notice").symlink_to(secret)
            start = session_start(home)
            self.assertEqual(start.returncode, 0, start.stderr)
            self.assertNotIn("SECRET-CONTENT", start.stdout)
            self.assertEqual(start.stdout.strip(), "")
            self.assertEqual(entries(home), [])  # the link itself is removed
            self.assertEqual(secret.read_text(), "SECRET-CONTENT\n")


if __name__ == "__main__":
    unittest.main()
