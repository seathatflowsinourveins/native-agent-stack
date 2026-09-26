"""Adoption preflight boundaries; no credentials, services, or model calls."""

import contextlib
import dis
import errno
import io
import json
import os
from pathlib import Path
import platform
import shutil
from shutil import which as native_which
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from scripts import adoption_status
from scripts.adoption_status import (CLIENT_WIRING_KEYS, CLIENT_WIRING_LIMITATIONS, NO_CLIENT_STATE,
                                     NO_PINNED_VERSION, PINNED_VERSION_LIMITATIONS, client_wiring, git_revision,
                                     inspect_adoption, main, pins_file_path, probe_pinned_version,
                                     signals_interrupt_probes, version_output_matches)

REPO = Path(__file__).resolve().parents[1]
# Resolved at import, before a test narrows PATH to its own directory or patches the platform.
SLEEP = native_which("sleep")
HOST_PLATFORM = {"os": platform.system().lower(), "architecture": platform.machine().lower()}
PRIVATE = "private-value-never-reported"
CLAUDE_EVENTS = ("PreToolUse", "SessionStart", "SubagentStop", "PostToolUse", "PreCompact", "Stop", "SessionEnd",
                 "SubagentStart")
CODEX_EVENTS = ("SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "PreCompact", "Stop", "SessionEnd")
CODEX_BASE = f"""model = "{PRIVATE}"

[plugins."context-mode@context-mode"]
enabled = true

[mcp_servers.serena]
command = "/opt/{PRIVATE}/bin/serena"

[mcp_servers.socraticode]
command = "/opt/{PRIVATE}/bin/node"

[mcp_servers.socraticode.env]
QDRANT_URL = "http://{PRIVATE}"

[mcp_servers.ai-memory]
url = "http://{PRIVATE}/mcp"
"""
CODEX_CONFIG = CODEX_BASE + "\n[features]\nhooks = true\n"  # as the recipe's `codex features enable hooks` writes it
SERVERS = ("serena", "socraticode", "ai-memory")
WIRED = {
    "claude": {"rtk_hook": True, "ai_memory_hook_events": 8, "context_mode_plugin_enabled": True,
               "subagent_spawn_depth_1": True, "workflow_concurrency_set": True,
               "effort_level_env_unset": True, "agent_teams_off": True},
    "project": {"settings_depth_and_concurrency": True, "codex_mcp_servers_present": dict.fromkeys(SERVERS, True)},
    "codex": {"rtk_instructions": True, "context_mode_plugin_enabled": True,
              "mcp_servers_present": dict.fromkeys(SERVERS, True), "hooks_feature_enabled": True,
              "ai_memory_hook_events": 7},
    "complete": True,
}


def ai_memory_group(event: str) -> dict:
    command = f"/opt/{PRIVATE}/ai-memory --data-dir /opt/{PRIVATE} hook --event {event} --server-url http://{PRIVATE}"
    return {"matcher": "", "hooks": [{"type": "command", "command": command}]}


def leaves(value):
    if isinstance(value, dict):
        for item in value.values():
            yield from leaves(item)
    else:
        yield value


class Descendant:
    """A child that a probe script starts in the background and leaves running: it writes "x" to a FIFO it
    keeps open on descriptor 3 and its PID to a file, then execs sleep, keeping the probe's stdout and stderr
    open too. The FIFO reads end-of-file only once no process holds it, which observes the kill without
    depending on when a reaper collects the zombie."""

    def __init__(self, test: unittest.TestCase, directory: Path):
        self.fifo, self.pidfile = directory / "descendant.fifo", directory / "descendant.pid"
        os.mkfifo(self.fifo)
        self.reader = os.open(self.fifo, os.O_RDONLY | os.O_NONBLOCK)  # first, so the writer's open never blocks
        test.addCleanup(self.cleanup)

    def script(self, then: str) -> str:
        """A probe script body: start the descendant, wait until it has written its marker, then ``then``."""
        return (f"/bin/sh -c 'printf x >&3; echo $$ > \"$1\"; exec \"$2\" 30' sh '{self.pidfile}' '{SLEEP}' "
                f"3> '{self.fifo}' &\nwhile [ ! -s '{self.pidfile}' ]; do :; done\n{then}")

    def started(self) -> bool:
        return self.pidfile.is_file() and self.pidfile.read_text().strip().isdigit()

    def gone(self, seconds: float = 10.0) -> bool:
        """Whether the FIFO reached end-of-file after the marker, within ``seconds``."""
        seen, deadline = b"", time.monotonic() + seconds
        while True:
            try:
                chunk = os.read(self.reader, 64)
            except BlockingIOError:  # still held open: the descendant is alive
                chunk = None
            if chunk:
                seen += chunk
            elif chunk == b"" and seen:
                return True
            elif time.monotonic() > deadline:
                return False
            else:
                time.sleep(0.02)

    def cleanup(self):
        os.close(self.reader)
        with contextlib.suppress(OSError, ValueError):  # already gone, or never started
            os.kill(int(self.pidfile.read_text()), signal.SIGKILL)


# Sets each named signal's disposition, then execs the rest of argv. exec keeps an ignored signal ignored and
# resets a handled one to its default, so the program starts with exactly these dispositions, whatever the
# test runner inherited (a background job of a non-interactive shell starts with SIGINT ignored; nohup, SIGHUP).
EXEC_WITH_DISPOSITIONS = ("import json, os, signal, sys\n"
                          "for name, action in json.loads(sys.argv[1]).items():\n"
                          "    signal.signal(getattr(signal, name),\n"
                          "                  signal.SIG_IGN if action == 'ignore' else signal.SIG_DFL)\n"
                          "os.execv(sys.argv[2], sys.argv[2:])\n")

# Runs the --pinned-versions CLI in this process and raises a signal on itself at one point inside
# run_version_probe, where a signal from outside would land only by chance. "created": after the probe's fork,
# once its background child runs, but before subprocess.Popen has returned the process. "cleanup": as the kill of
# the probe's group begins, after the test has interrupted the check once. Each point says on stderr that it was
# reached. argv: the point, the signal number, the background child's PID file, the checkout, the CLI's arguments.
INTERRUPT_INSIDE_A_PROBE = """\
import os, signal, subprocess, sys, time
point, signum, pidfile, checkout = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4]
sys.path.insert(0, checkout)
from scripts import adoption_status


def child_runs():
    try:
        with open(pidfile) as handle:
            return handle.read().strip().isdigit()
    except OSError:
        return False


def interrupt(where):
    print(f"raised {signal.Signals(signum).name} {where}", file=sys.stderr, flush=True)
    signal.raise_signal(signum)


if point == "created":
    class Popen(subprocess.Popen):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            if os.path.basename(self.args[0]) == "forking-tool":
                deadline = time.monotonic() + 20
                while not child_runs() and time.monotonic() < deadline:
                    time.sleep(0.01)
                interrupt("after the probe's fork, before subprocess.Popen returned")

    subprocess.Popen = Popen
else:
    kill_group = adoption_status.signal_group

    def signal_group(group, sent):
        if sent == signal.SIGKILL:
            interrupt("as the kill of the probe's group began")
        kill_group(group, sent)

    adoption_status.signal_group = signal_group
sys.exit(adoption_status.main(sys.argv[5:]))
"""


class AdoptionStatusTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "adoption").mkdir()
        (self.root / "recipes").mkdir()
        (self.root / "recipes/README.md").write_text("Native recipe\n")
        self.path = self.root / "adoption/manifest.json"
        self.manifest = {
            "schema_version": 1,
            "supported_platforms": [{"os": "linux", "architecture": "x86_64", "python": "3.13"}],
            "profiles": [{"id": "foundation-cpu", "label": "CPU foundation",
                          "required_commands": ["qmd"], "component_ids": ["qmd"],
                          "recipe_paths": ["recipes/README.md"]}],
            "default_profile": "foundation-cpu",
            "source": {"baseline_commit": "a" * 40,
                       "repository": "https://github.com/example/reference"},
        }
        self.save()
        self.enter = contextlib.ExitStack()
        self.addCleanup(self.enter.close)
        self.enter.enter_context(patch("scripts.adoption_status.platform.system", return_value="Linux"))
        self.enter.enter_context(patch("scripts.adoption_status.platform.machine", return_value="x86_64"))
        self.enter.enter_context(patch("scripts.adoption_status.sys.version_info", (3, 13, 7)))
        self.which = self.enter.enter_context(patch("scripts.adoption_status.shutil.which", return_value="/private/bin/qmd"))
        self.git = self.enter.enter_context(patch("scripts.adoption_status.git_revision", return_value="a" * 40))

    def save(self):
        self.path.write_text(json.dumps(self.manifest), encoding="utf-8")

    def inspect(self, profiles=None):
        return inspect_adoption(self.path, self.root, profiles)

    def test_present_prerequisites_do_not_claim_runtime_acceptance(self):
        result = self.inspect()
        self.assertEqual(result["status"], "prerequisites_present")
        self.assertEqual(result["git"]["comparison"], "baseline_matches")
        self.assertEqual(result["platform"]["python"], "3.13.7")
        self.assertFalse(result["runtime_acceptance_verified"])
        self.assertNotIn("/private/bin", json.dumps(result))
        self.which.assert_called_once_with("qmd")

    def test_missing_command_and_recipe_are_reported(self):
        self.which.return_value = None
        (self.root / "recipes/README.md").unlink()
        result = self.inspect()
        self.assertEqual(result["status"], "prerequisites_missing")
        self.assertFalse(result["profiles"][0]["commands"][0]["present"])
        self.assertFalse(result["profiles"][0]["recipes"][0]["present"])

    def prepare_loki_check(self):
        self.manifest["profiles"][0].update(required_commands=["loki"], component_ids=["loki"])
        self.save()
        directory = self.root / "bin"
        directory.mkdir()
        self.enter.enter_context(patch.dict("os.environ", {"PATH": str(directory)}))
        self.which.side_effect = native_which
        return directory

    def test_loki_archive_basename_is_presence_only_without_execution(self):
        directory = self.prepare_loki_check()
        marker = self.root / "must-not-run"
        executable = directory / "loki-linux-amd64"
        executable.write_text(f"#!/bin/sh\nprintf executed > '{marker}'\n")
        executable.chmod(0o755)
        with patch("scripts.adoption_status.subprocess.run") as run:
            result = self.inspect()
        self.assertEqual(result["status"], "prerequisites_present")
        self.assertEqual(result["profiles"][0]["commands"], [{"name": "loki", "present": True}])
        self.assertFalse(result["runtime_acceptance_verified"])
        self.assertFalse(marker.exists())
        self.assertNotIn(str(directory), json.dumps(result))
        run.assert_not_called()

    def test_conventional_loki_name_is_preferred(self):
        directory = self.prepare_loki_check()
        for name in ("loki", "loki-linux-amd64"):
            executable = directory / name
            executable.write_text("#!/bin/sh\nexit 1\n")
            executable.chmod(0o755)
        self.assertEqual(self.inspect()["status"], "prerequisites_present")
        self.which.assert_called_once_with("loki")

    def test_loki_archive_for_another_host_is_not_accepted(self):
        directory = self.prepare_loki_check()
        executable = directory / "loki-linux-amd64"
        executable.write_text("#!/bin/sh\nexit 1\n")
        executable.chmod(0o755)
        for system, machine in (("Darwin", "x86_64"), ("Windows", "AMD64"), ("Linux", "aarch64")):
            with self.subTest(system=system, machine=machine), \
                    patch("scripts.adoption_status.platform.system", return_value=system), \
                    patch("scripts.adoption_status.platform.machine", return_value=machine):
                self.assertFalse(self.inspect()["profiles"][0]["commands"][0]["present"])

    def test_loki_missing_or_nonexecutable_archive_is_not_present(self):
        directory = self.prepare_loki_check()
        executable = directory / "loki-linux-amd64"
        for exists in (False, True):
            with self.subTest(file_exists=exists):
                if exists:
                    executable.write_text("not an executable\n")
                    executable.chmod(0o644)
                result = self.inspect()
                self.assertEqual(result["status"], "prerequisites_missing")
                self.assertFalse(result["profiles"][0]["commands"][0]["present"])

    def test_unknown_profile_fails_without_probing_commands(self):
        result = self.inspect(["unknown"])
        self.assertEqual(result["manifest"]["status"], "invalid")
        self.assertIn("unknown profile", result["errors"][0])
        self.which.assert_not_called()

    def test_explicit_profiles_do_not_require_unselected_commands(self):
        self.manifest["profiles"].append({"id": "gpu", "label": "GPU",
            "required_commands": ["vllm"], "component_ids": ["vllm"], "recipe_paths": []})
        self.save()
        result = self.inspect(["foundation-cpu", "foundation-cpu"])
        self.assertEqual(len(result["profiles"]), 1)
        self.which.assert_called_once_with("qmd")

    def test_unsupported_platform_or_python_blocks_readiness(self):
        for target, value in [("platform.machine", "arm64"), ("sys.version_info", (3, 12, 9))]:
            override = (patch("scripts.adoption_status." + target, return_value=value)
                        if target.startswith("platform") else patch("scripts.adoption_status." + target, value))
            with self.subTest(target=target), override:
                result = self.inspect()
                self.assertEqual(result["status"], "prerequisites_missing")
                self.assertFalse(result["platform"]["supported"])

    def test_unsafe_recipe_references_are_rejected_before_probing(self):
        for reference in (".", "../outside", "/etc/passwd", "recipes/../secret", "recipes//README.md", "C:\\secret", "recipes/./README.md"):
            with self.subTest(reference=reference):
                self.manifest["profiles"][0]["recipe_paths"] = [reference]
                self.save()
                self.assertEqual(self.inspect()["manifest"]["status"], "invalid")
        self.which.assert_not_called()

    def test_symlink_recipe_and_symlink_parent_are_rejected(self):
        recipe = self.root / "recipes/README.md"
        recipe.unlink()
        recipe.symlink_to(self.path)
        self.assertEqual(self.inspect()["manifest"]["status"], "invalid")
        recipe.unlink()
        recipe.parent.rmdir()
        recipe.parent.symlink_to(self.root / "adoption", target_is_directory=True)
        self.assertEqual(self.inspect()["manifest"]["status"], "invalid")

    def test_malformed_shapes_and_command_paths_are_rejected(self):
        for mutate in (lambda d: d.update(schema_version=True),
                       lambda d: d.update(profiles=[]),
                       lambda d: d["profiles"][0].update(required_commands=["/bin/qmd"]),
                       lambda d: d["profiles"][0].update(required_commands=["qmd --help"]),
                       lambda d: d["source"].update(baseline_commit="not-a-revision"),
                       lambda d: d["source"].update(repository="https://secret@example.com/repo")):
            with self.subTest(mutate=mutate):
                original = json.loads(json.dumps(self.manifest))
                mutate(self.manifest)
                self.save()
                self.assertEqual(self.inspect()["manifest"]["status"], "invalid")
                self.manifest = original

    def test_invalid_json_and_duplicate_keys_are_bounded_errors(self):
        for raw in ('{"bad":', '{"schema_version":1,"schema_version":1}'):
            self.path.write_text(raw)
            result = self.inspect()
            self.assertEqual(result["manifest"]["status"], "invalid")
            self.assertNotIn(str(self.root), json.dumps(result))

    def test_git_difference_is_information_not_failed_acceptance(self):
        self.git.return_value = "b" * 40
        result = self.inspect()
        self.assertEqual(result["status"], "prerequisites_present")
        self.assertEqual(result["git"]["comparison"], "baseline_differs")
        self.git.return_value = None
        self.assertEqual(self.inspect()["git"]["comparison"], "unavailable")

    def test_json_cli_does_not_emit_environment_or_credential_paths(self):
        output = io.StringIO()
        with patch.dict("os.environ", {"OPENAI_API_KEY": "never-publish-this", "HF_TOKEN": "nor-this"}), contextlib.redirect_stdout(output):
            code = main(["--manifest", str(self.path), "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(output.getvalue())
        self.assertNotIn("never-publish-this", output.getvalue())
        self.assertNotIn("nor-this", output.getvalue())
        self.assertNotIn(str(self.root), output.getvalue())
        self.assertEqual(payload["manifest"]["status"], "valid")

    def test_missing_manifest_returns_exit_two_and_help_does_not_read(self):
        self.path.unlink()
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["--manifest", str(self.path), "--json"]), 2)
        with patch("scripts.adoption_status.inspect_adoption") as inspect, contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as raised:
            main(["--help"])
        self.assertEqual(raised.exception.code, 0)
        inspect.assert_not_called()

    def test_component_namespace_ids_are_supported(self):
        self.manifest["profiles"][0]["component_ids"] = ["affaan-m/ECC"]
        self.save()
        self.assertEqual(self.inspect()["status"], "prerequisites_present")

    def test_native_git_output_is_strict_and_timeout_is_bounded(self):
        with patch("scripts.adoption_status.subprocess.run") as run:
            run.return_value = subprocess.CompletedProcess([], 0, f"{self.root}\n{'a' * 40}\n", "")
            self.assertEqual(git_revision(self.root), "a" * 40)
            self.assertEqual(run.call_args.kwargs["timeout"], 5)
            run.return_value = subprocess.CompletedProcess([], 0, f"/another/repository\n{'a' * 40}\n", "")
            self.assertIsNone(git_revision(self.root))
            run.return_value = subprocess.CompletedProcess([], 1, "untrusted output", "private/path/secret")
            self.assertIsNone(git_revision(self.root))
            run.side_effect = subprocess.TimeoutExpired(["git"], 5)
            self.assertIsNone(git_revision(self.root))

    def test_a_symlink_loop_in_root_returns_none_not_an_uncaught_runtimeerror(self):
        # Path.resolve() on Python before 3.13 raises RuntimeError for a
        # symlink loop (3.13+ instead returns the unresolved remainder);
        # either way git_revision must return None, not propagate it.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            link_a = tmp_path / "a"
            link_b = tmp_path / "b"
            os.symlink(link_b, link_a)
            os.symlink(link_a, link_b)
            self.assertIsNone(git_revision(link_a))

    def test_manifest_outside_explicit_root_is_rejected(self):
        result = inspect_adoption(self.path, self.root / "recipes")
        self.assertEqual(result["manifest"]["status"], "invalid")
        self.assertIn("inside the repository root", result["errors"][0])

    def test_client_wiring_is_opt_in(self):
        with patch("scripts.adoption_status.client_wiring") as wiring, \
                contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(["--manifest", str(self.path), "--json"]), 0)
        wiring.assert_not_called()
        payload = json.loads(output.getvalue())
        self.assertNotIn("client_wiring", payload)
        self.assertIn(NO_CLIENT_STATE, payload["limitations"])

    def test_client_wiring_flag_reports_and_restates_the_limitations(self):
        canned = {"claude": {"rtk_hook": True}, "complete": False}
        with patch("scripts.adoption_status.client_wiring", return_value=canned) as wiring, \
                contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(["--manifest", str(self.path), "--json", "--client-wiring"]), 0)
        wiring.assert_called_once_with(self.root.resolve(), None)
        payload = json.loads(output.getvalue())
        self.assertEqual(payload["client_wiring"], canned)
        self.assertNotIn(NO_CLIENT_STATE, payload["limitations"])
        self.assertEqual(payload["limitations"][-2:], CLIENT_WIRING_LIMITATIONS)
        with patch("scripts.adoption_status.client_wiring", return_value=canned), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            # The exit code stays the prerequisite result; incomplete wiring is reported, not exited on.
            self.assertEqual(main(["--manifest", str(self.path), "--client-wiring"]), 0)
        self.assertIn('Client wiring complete: false\nClient wiring: {"claude": {"rtk_hook": true}}\n',
                      output.getvalue())

    def test_client_wiring_is_reported_even_for_an_invalid_manifest(self):
        self.path.write_text("{", encoding="utf-8")
        home = self.root / "empty-home"
        home.mkdir()
        result = inspect_adoption(self.path, self.root, with_client_wiring=True, env={"HOME": str(home)})
        self.assertEqual(result["manifest"]["status"], "invalid")
        self.assertEqual(set(result["client_wiring"]), {*CLIENT_WIRING_KEYS, "complete"})
        self.assertIs(result["client_wiring"]["complete"], False)
        self.assertNotIn(str(self.root), json.dumps(result))


class PinnedVersionProbeTests(unittest.TestCase):
    """probe_pinned_version/version_output_matches units, against a real tiny script on PATH (never a
    fake subprocess): never execs a non-"exec" method, exact and minimum matching, a failing probe never
    matches, a missing command, malformed command string or timeout is unchecked rather than raising, and
    the probe's whole process group is killed on timeout and once it exits."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.bin = Path(temporary.name)
        self.enter = contextlib.ExitStack()
        self.addCleanup(self.enter.close)
        self.enter.enter_context(patch.dict("os.environ", {"PATH": str(self.bin)}))
        self.enter.enter_context(patch("scripts.adoption_status.shutil.which", side_effect=native_which))

    def script(self, name: str, body: str) -> None:
        executable = self.bin / name
        executable.write_text(f"#!/bin/sh\n{body}\n")
        executable.chmod(0o755)

    def test_exact_match_reports_checked_and_matched(self):
        self.script("gh", "printf 'gh version 2.101.0 (2026-09-22)\\n'")
        entry = {"version": "2.101.0", "version_probe": {"method": "exec", "command": "gh", "args": ["--version"]}}
        self.assertEqual(probe_pinned_version(entry),
                          {"pinned_version": "2.101.0", "checked": True, "matches_pin": True})

    def test_exact_mismatch_is_checked_and_not_matched(self):
        self.script("gh", "printf 'gh version 2.100.0\\n'")
        entry = {"version": "2.101.0", "version_probe": {"method": "exec", "command": "gh", "args": ["--version"]}}
        self.assertEqual(probe_pinned_version(entry),
                          {"pinned_version": "2.101.0", "checked": True, "matches_pin": False})

    def test_minimum_match_is_a_floor_not_a_ceiling(self):
        self.script("claude", "printf 'claude-code 2.1.290\\n'")
        entry = {"version": "2.1.281",
                 "version_probe": {"method": "exec", "command": "claude", "match": "minimum", "args": ["--version"]}}
        self.assertTrue(probe_pinned_version(entry)["matches_pin"])
        self.script("claude", "printf 'claude-code 2.1.100\\n'")
        self.assertFalse(probe_pinned_version(entry)["matches_pin"])

    def test_npm_metadata_method_is_never_executed(self):
        self.script("context-mode", "printf 'never run\\n'; exit 1")
        entry = {"version": "1.0.169", "version_probe": {"method": "npm-metadata", "note": "starts a server"}}
        with patch("scripts.adoption_status.subprocess.Popen") as popen:
            result = probe_pinned_version(entry)
        popen.assert_not_called()
        self.assertEqual(result, {"pinned_version": "1.0.169", "checked": False, "matches_pin": None})

    def test_an_undeclared_future_method_is_also_never_executed(self):
        self.script("future-tool", "printf 'never run\\n'; exit 1")
        entry = {"version": "9.9.9",
                 "version_probe": {"method": "some-future-method", "command": "future-tool", "args": ["--version"]}}
        with patch("scripts.adoption_status.subprocess.Popen") as popen:
            result = probe_pinned_version(entry)
        popen.assert_not_called()
        self.assertFalse(result["checked"])

    def test_a_command_not_on_path_is_unchecked_not_an_error(self):
        entry = {"version": "1.0.0",
                 "version_probe": {"method": "exec", "command": "definitely-not-on-any-path-xyz", "args": []}}
        self.assertEqual(probe_pinned_version(entry), {"pinned_version": "1.0.0", "checked": False, "matches_pin": None})

    def test_a_malformed_command_string_is_rejected_before_exec(self):
        for command in ("rm -rf /", "/bin/sh", "../escape", ""):
            with self.subTest(command=command):
                entry = {"version": "1.0.0", "version_probe": {"method": "exec", "command": command, "args": []}}
                with patch("scripts.adoption_status.subprocess.Popen") as popen:
                    result = probe_pinned_version(entry)
                popen.assert_not_called()
                self.assertFalse(result["checked"])

    def test_a_hanging_probe_times_out_and_is_unchecked(self):
        # A shell built-in loop only: PATH is scoped to this test's own bin dir, so an external "sleep"
        # binary would not be found on it (exit 127, not a hang) -- ":" and "while" need no PATH lookup.
        self.script("slow-tool", "while :; do :; done")
        entry = {"version": "1.0.0", "version_probe": {"method": "exec", "command": "slow-tool", "args": [],
                                                        "timeout_seconds": 0.2}}
        self.assertEqual(probe_pinned_version(entry), {"pinned_version": "1.0.0", "checked": False, "matches_pin": None})

    def test_a_failing_probe_never_matches_even_when_its_diagnostics_name_the_pin(self):
        # bootstrap-linux.sh reports any nonzero exit as "FAILED (exit N)" before it looks at the output.
        entry = {"version": "1.2.3", "version_probe": {"method": "exec", "command": "tool", "args": ["--version"]}}
        for stream in ("", " >&2"):
            with self.subTest(stream=stream or "stdout"):
                self.script("tool", f"printf 'tool 1.2.3: cannot open its data directory\\n'{stream}; exit 42")
                self.assertEqual(probe_pinned_version(entry),
                                 {"pinned_version": "1.2.3", "checked": True, "matches_pin": False})
                self.script("tool", f"printf 'tool 1.2.3: cannot open its data directory\\n'{stream}")
                self.assertTrue(probe_pinned_version(entry)["matches_pin"])  # the same output, exit 0

    def test_stdout_and_stderr_are_searched_as_two_streams(self):
        # As the bootstrap greps two files: a stdout without a final newline does not run into stderr.
        self.script("tool", "printf 'tool 1.2.3'; printf '4 warnings\\n' >&2")
        entry = {"version": "1.2.3", "version_probe": {"method": "exec", "command": "tool", "args": []}}
        self.assertTrue(probe_pinned_version(entry)["matches_pin"])

    @unittest.skipUnless(SLEEP, "needs a sleep executable")
    def test_a_timeout_kills_the_probe_s_whole_process_group(self):
        descendant = Descendant(self, self.bin)
        self.script("forking-tool", descendant.script("wait"))
        entry = {"version": "1.2.3", "version_probe": {"method": "exec", "command": "forking-tool", "args": [],
                                                        "timeout_seconds": 1}}
        self.assertEqual(probe_pinned_version(entry), {"pinned_version": "1.2.3", "checked": False, "matches_pin": None})
        self.assertTrue(descendant.started(), "the probe's background child never ran")
        self.assertTrue(descendant.gone(), "the probe's background child outlived the timeout")

    @unittest.skipUnless(SLEEP, "needs a sleep executable")
    def test_a_probe_s_leftover_descendants_are_killed_once_it_exits(self):
        # The leftover child also holds the probe's stdout and stderr open; the result must not wait for it.
        descendant = Descendant(self, self.bin)
        self.script("leaky-tool", descendant.script("printf 'leaky-tool 1.2.3\\n'"))
        entry = {"version": "1.2.3", "version_probe": {"method": "exec", "command": "leaky-tool", "args": [],
                                                        "timeout_seconds": 10}}
        started = time.monotonic()
        self.assertEqual(probe_pinned_version(entry), {"pinned_version": "1.2.3", "checked": True, "matches_pin": True})
        self.assertLess(time.monotonic() - started, 8)
        self.assertTrue(descendant.started(), "the probe's background child never ran")
        self.assertTrue(descendant.gone(), "the probe's background child outlived the probe")

    def test_version_output_matches_rules(self):
        self.assertTrue(version_output_matches("2.101.0", "exact", "gh version 2.101.0 (2026-09-22)\n"))
        self.assertFalse(version_output_matches("2.101.0", "exact", "gh version 2.100.0\n"))
        self.assertTrue(version_output_matches("2.1.281", "minimum", "claude-code 2.1.281\n"))
        self.assertTrue(version_output_matches("2.1.281", "minimum", "claude-code 2.2.0\n"))
        self.assertFalse(version_output_matches("2.1.281", "minimum", "claude-code 2.1.100\n"))
        self.assertFalse(version_output_matches("2.1.281", "minimum", "no version here\n"))

    def test_exact_is_bounded_by_non_version_characters_like_the_bootstrap(self):
        # bootstrap-linux.sh anchors "exact" with (^|[^0-9.])...([^0-9.]|$); a bare substring would match these.
        self.assertFalse(version_output_matches("2.10", "exact", "v12.10.0\n"))
        self.assertFalse(version_output_matches("1.0.0", "exact", "tool 21.0.0\n"))
        self.assertFalse(version_output_matches("0.49.0", "exact", "rtk 0.49.0.1\n"))
        self.assertTrue(version_output_matches("2.8.3", "exact", "qmd 2.8.3 (facd35e)"))
        self.assertTrue(version_output_matches("0.49.0", "exact", "first line\nrtk 0.49.0\n"))

    def test_minimum_with_a_non_numeric_part_is_not_a_match_and_never_raises(self):
        # bootstrap-linux.sh version_at_least returns 1 for a non-numeric part instead of failing.
        self.assertFalse(version_output_matches("2.0.0.dev0", "minimum", "Serena 2.0.0\n"))
        # As in the bootstrap, the observed version is the first dotted number, so ".dev0" is not part of it.
        self.assertTrue(version_output_matches("2.0.0", "minimum", "Serena 2.0.0.dev0\n"))
        self.assertTrue(version_output_matches("1.2", "minimum", "tool 1.2.0\n"))
        self.assertFalse(version_output_matches("1.0", "unknown-rule", "tool 1.0\n"))


class PinnedVersionsCheckTests(unittest.TestCase):
    """--pinned-versions end to end: opt-in, value-free JSON shape, and the swapped limitation."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "adoption").mkdir()
        (self.root / "recipes").mkdir()
        (self.root / "recipes/README.md").write_text("Native recipe\n")
        self.path = self.root / "adoption/manifest.json"
        self.manifest = {
            "schema_version": 1,
            "supported_platforms": [{"os": "linux", "architecture": "x86_64", "python": "3.13"}],
            "profiles": [{"id": "foundation-cpu", "label": "CPU foundation",
                          "required_commands": ["qmd"], "component_ids": ["qmd", "context-mode", "unpinned-tool"],
                          "recipe_paths": ["recipes/README.md"]}],
            "default_profile": "foundation-cpu",
            "source": {"baseline_commit": "a" * 40, "repository": "https://github.com/example/reference"},
        }
        self.path.write_text(json.dumps(self.manifest), encoding="utf-8")
        self.pins = self.root / "adoption/pins-linux-x86_64.json"
        self.pins.write_text(json.dumps({"schema_version": 1, "platform": "linux-x86_64", "tools": [
            {"id": "qmd", "version": "2.8.3",
             "version_probe": {"method": "exec", "command": "qmd", "args": ["--version"]}},
            {"id": "context-mode", "version": "1.0.169", "version_probe": {"method": "npm-metadata"}},
        ]}), encoding="utf-8")
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        executable = bin_dir / "qmd"
        executable.write_text("#!/bin/sh\nprintf 'qmd 2.8.3\\n'\n")
        executable.chmod(0o755)
        self.enter = contextlib.ExitStack()
        self.addCleanup(self.enter.close)
        self.enter.enter_context(patch.dict("os.environ", {"PATH": str(bin_dir)}))
        self.enter.enter_context(patch("scripts.adoption_status.platform.system", return_value="Linux"))
        self.enter.enter_context(patch("scripts.adoption_status.platform.machine", return_value="x86_64"))
        self.enter.enter_context(patch("scripts.adoption_status.sys.version_info", (3, 13, 7)))
        self.enter.enter_context(patch("scripts.adoption_status.shutil.which", side_effect=native_which))
        self.enter.enter_context(patch("scripts.adoption_status.git_revision", return_value="a" * 40))

    def test_pinned_versions_is_opt_in(self):
        with patch("scripts.adoption_status.subprocess.Popen") as popen:
            result = inspect_adoption(self.path, self.root)
        popen.assert_not_called()
        self.assertEqual(result["profiles"][0].keys(), {"id", "commands", "recipes", "status"})
        self.assertIn(NO_PINNED_VERSION, result["limitations"])

    def test_pinned_versions_reports_matched_unchecked_and_absent(self):
        result = inspect_adoption(self.path, self.root, with_pinned_versions=True)
        self.assertEqual(result["profiles"][0]["pinned_versions"], [
            {"id": "qmd", "pinned_version": "2.8.3", "checked": True, "matches_pin": True},
            {"id": "context-mode", "pinned_version": "1.0.169", "checked": False, "matches_pin": None},
            {"id": "unpinned-tool", "pinned_version": None, "checked": False, "matches_pin": None},
        ])
        self.assertNotIn(NO_PINNED_VERSION, result["limitations"])
        self.assertEqual(result["limitations"][-1:], PINNED_VERSION_LIMITATIONS)

    def test_an_absent_pins_file_reports_every_component_unchecked_not_an_error(self):
        self.pins.unlink()
        result = inspect_adoption(self.path, self.root, with_pinned_versions=True)
        self.assertTrue(all(item["checked"] is False and item["matches_pin"] is None
                            for item in result["profiles"][0]["pinned_versions"]))

    def test_a_malformed_pins_file_reports_every_component_unchecked_not_an_error(self):
        for body in ("{not json", "[]", '{"tools": {}}', '{"tools": [1, "x", null]}',
                     '{"tools": [{"version": "1.0"}]}', '{"tools": [{"id": "rtk"}]}'):
            with self.subTest(body=body):
                self.pins.write_text(body, encoding="utf-8")
                result = inspect_adoption(self.path, self.root, with_pinned_versions=True)
                self.assertTrue(all(item["checked"] is False and item["matches_pin"] is None
                                    for item in result["profiles"][0]["pinned_versions"]))

    def test_client_wiring_and_pinned_versions_compose(self):
        canned = {"claude": {"rtk_hook": True}, "complete": False}
        with patch("scripts.adoption_status.client_wiring", return_value=canned):
            result = inspect_adoption(self.path, self.root, with_client_wiring=True, with_pinned_versions=True)
        self.assertNotIn(NO_CLIENT_STATE, result["limitations"])
        self.assertNotIn(NO_PINNED_VERSION, result["limitations"])
        self.assertEqual(result["limitations"][-1:], PINNED_VERSION_LIMITATIONS)
        self.assertIn("client_wiring", result)
        self.assertIn("pinned_versions", result["profiles"][0])

    def test_cli_json_and_text_report_pinned_versions(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(["--manifest", str(self.path), "--repo-root", str(self.root), "--json", "--pinned-versions"])
        self.assertEqual(code, 0)
        payload = json.loads(output.getvalue())
        self.assertIn("pinned_versions", payload["profiles"][0])
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            main(["--manifest", str(self.path), "--repo-root", str(self.root), "--pinned-versions"])
        self.assertIn("pinned versions: 1 matched, unchecked: context-mode, unpinned-tool", output.getvalue())

    def test_pinned_versions_output_is_value_free(self):
        result = inspect_adoption(self.path, self.root, with_pinned_versions=True)
        rendered = json.dumps(result)
        self.assertNotIn(str(self.root), rendered)
        for item in result["profiles"][0]["pinned_versions"]:
            for key, value in item.items():
                self.assertTrue(value is None or isinstance(value, (bool, str)), repr((key, value)))


@unittest.skipUnless(SLEEP, "needs a sleep executable")
class PinnedVersionInterruptionTests(unittest.TestCase):
    """The --pinned-versions CLI, run as its own process on this host's real platform, gets a signal while a
    probe runs. Started with the default dispositions, SIGINT, SIGTERM and SIGHUP all end the check with the
    probe's whole process group killed, as bootstrap-linux.sh's EXIT trap does. Started with one of them
    ignored (nohup; a background job of a non-interactive shell), that signal changes nothing, as CPython leaves
    an ignored SIGINT ignored and bash cannot trap a signal ignored on entry: the probe finishes, is reported,
    and its group is still killed once it exits. The group is also killed when the signal arrives while the
    probe's process is being created, or a second one as the kill begins. Each check starts with exactly the
    dispositions its test sets, whatever the test runner inherited."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "adoption").mkdir()
        self.manifest = self.root / "adoption/manifest.json"
        self.manifest.write_text(json.dumps({
            "schema_version": 1,
            "supported_platforms": [{"os": "linux", "architecture": "x86_64", "python": "3.13"}],
            "profiles": [{"id": "probe", "label": "Probe", "required_commands": [],
                          "component_ids": ["forking-tool"], "recipe_paths": []}],
            "default_profile": "probe",
            "source": {"baseline_commit": "a" * 40, "repository": "https://github.com/example/reference"},
        }), encoding="utf-8")
        pins_file_path(self.root, HOST_PLATFORM).write_text(json.dumps({"tools": [
            {"id": "forking-tool", "version": "1.2.3",
             "version_probe": {"method": "exec", "command": "forking-tool", "args": [], "timeout_seconds": 60}},
        ]}), encoding="utf-8")
        self.bin = self.root / "bin"
        self.bin.mkdir()

    def probe(self, body: str) -> None:
        executable = self.bin / "forking-tool"
        executable.write_text(f"#!/bin/sh\n{body}\n")
        executable.chmod(0o755)

    def start(self, ignored: signal.Signals | None, descendant: Descendant, **streams) -> subprocess.Popen:
        """Start the check with SIGINT, SIGTERM and SIGHUP at their defaults, apart from ``ignored``, and wait
        until the probe's background child runs."""
        dispositions = {signum.name: "ignore" if signum == ignored else "default"
                        for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)}
        check = subprocess.Popen([sys.executable, "-c", EXEC_WITH_DISPOSITIONS, json.dumps(dispositions),
                                  sys.executable, str(REPO / "scripts/adoption_status.py"), "--manifest",
                                  str(self.manifest), "--repo-root", str(self.root), "--pinned-versions", "--json"],
                                 env={"PATH": str(self.bin)}, stdin=subprocess.DEVNULL, **streams)
        self.addCleanup(check.kill)
        deadline = time.monotonic() + 20
        while not descendant.started() and check.poll() is None and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertTrue(descendant.started(), "the probe's background child never ran")
        return check

    @staticmethod
    def release(fifo: Path, check: subprocess.Popen) -> None:
        """Let a probe blocked reading ``fifo`` go on. A nonblocking open for writing fails with ENXIO until the
        probe has the FIFO open, so it is retried while the check runs; a check that already exited is left
        alone."""
        deadline = time.monotonic() + 20
        while check.poll() is None and time.monotonic() < deadline:
            try:
                descriptor = os.open(fifo, os.O_WRONLY | os.O_NONBLOCK)
            except OSError as error:
                if error.errno != errno.ENXIO:
                    raise
                time.sleep(0.02)
                continue
            try:
                os.write(descriptor, b"go\n")
            finally:
                os.close(descriptor)
            return

    def test_an_interrupted_check_kills_the_running_probe_s_process_group(self):
        for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            with self.subTest(signal=signum.name):
                descendant = Descendant(self, Path(tempfile.mkdtemp(dir=self.root)))
                self.probe(descendant.script("wait"))
                check = self.start(None, descendant, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                check.send_signal(signum)
                self.assertIn(check.wait(timeout=20), (-signum, 128 + signum))
                self.assertTrue(descendant.gone(), f"the probe's background child outlived {signum.name}")

    def test_a_signal_ignored_on_entry_leaves_the_check_running(self):
        for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            with self.subTest(signal=signum.name):
                work = Path(tempfile.mkdtemp(dir=self.root))
                descendant, release = Descendant(self, work), work / "release.fifo"
                os.mkfifo(release)
                # The probe waits for the release, so the signal is sure to arrive while it runs.
                self.probe(descendant.script(f"read line < '{release}'\nprintf 'forking-tool 1.2.3\\n'"))
                check = self.start(signum, descendant, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                check.send_signal(signum)
                time.sleep(0.2)  # time for a handler to act, were one installed
                self.release(release, check)
                output, _ = check.communicate(timeout=20)
                # The prerequisite result (2 on a platform or Python this manifest does not list), never a signal's.
                self.assertIn(check.returncode, (0, 2), f"{signum.name}, ignored on entry, ended the check")
                self.assertEqual(json.loads(output)["profiles"][0]["pinned_versions"], [
                    {"id": "forking-tool", "pinned_version": "1.2.3", "checked": True, "matches_pin": True}])
                self.assertTrue(descendant.gone(), "the probe's background child outlived the probe")

    def interrupt_inside(self, point: str, signum: signal.Signals, descendant: Descendant) -> subprocess.Popen:
        """Start the check through INTERRUPT_INSIDE_A_PROBE, with SIGINT, SIGTERM and SIGHUP at their defaults."""
        defaults = {each.name: "default" for each in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)}
        check = subprocess.Popen([sys.executable, "-c", EXEC_WITH_DISPOSITIONS, json.dumps(defaults), sys.executable,
                                  "-c", INTERRUPT_INSIDE_A_PROBE, point, str(int(signum)), str(descendant.pidfile),
                                  str(REPO), "--manifest", str(self.manifest), "--repo-root", str(self.root),
                                  "--pinned-versions", "--json"],
                                 env={"PATH": str(self.bin)}, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.PIPE, text=True)
        self.addCleanup(check.kill)
        return check

    def test_a_signal_while_the_probe_s_process_is_created_still_kills_its_group(self):
        # After the fork, before subprocess.Popen returns: nothing yet holds the process to kill its group.
        for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            with self.subTest(signal=signum.name):
                descendant = Descendant(self, Path(tempfile.mkdtemp(dir=self.root)))
                self.probe(descendant.script("wait"))
                check = self.interrupt_inside("created", signum, descendant)
                _, stderr = check.communicate(timeout=60)
                self.assertIn(f"raised {signum.name} after the probe's fork", stderr)
                self.assertTrue(descendant.started(), "the probe's background child never ran")
                self.assertIn(check.returncode, (-signum, 128 + signum))
                self.assertTrue(descendant.gone(),
                                f"the probe's background child outlived {signum.name} while its process was created")

    def test_a_second_signal_as_the_group_kill_begins_does_not_stop_it(self):
        # The check is interrupted once (SIGTERM from here), and a second signal arrives as its cleanup starts.
        for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            with self.subTest(second_signal=signum.name):
                descendant = Descendant(self, Path(tempfile.mkdtemp(dir=self.root)))
                self.probe(descendant.script("wait"))
                check = self.interrupt_inside("cleanup", signum, descendant)
                deadline = time.monotonic() + 20
                while not descendant.started() and check.poll() is None and time.monotonic() < deadline:
                    time.sleep(0.02)
                self.assertTrue(descendant.started(), "the probe's background child never ran")
                check.send_signal(signal.SIGTERM)
                _, stderr = check.communicate(timeout=60)
                self.assertIn(f"raised {signum.name} as the kill of the probe's group began", stderr)
                self.assertIn(check.returncode, (-signum, 128 + signum))
                self.assertTrue(descendant.gone(),
                                f"the probe's background child outlived a second signal, {signum.name}")


@unittest.skipUnless(hasattr(signal, "SIGHUP"), "needs POSIX signals")
class ProbeSignalDispositionTests(unittest.TestCase):
    """signals_interrupt_probes, in this process: it replaces SIGTERM's and SIGHUP's disposition only while that
    is the default action, and SIGINT's while it is the default action or CPython's own handler, which CPython
    installs only when SIGINT starts at its default action, and restores each afterwards. An ignored signal stays
    ignored and a handler installed by someone else stays in place. Inside held_interrupts, the handlers keep the
    first interrupt and raise it when the hold ends; interrupts_released lets them through again for its block.
    run_version_probe, interrupted at the start of each line it and its helpers run, one line per run, leaves
    nothing of its probe running. The handlers are called directly; no signal is sent."""

    SIGNALS = (signal.SIGTERM, signal.SIGHUP) if hasattr(signal, "SIGHUP") else ()
    ALL = (signal.SIGINT, *SIGNALS)
    # run_version_probe and the helpers it calls while its probe's process exists.
    PROBE_FUNCTIONS = ("run_version_probe", "held_interrupts", "interrupts_released", "signal_group")

    def setUp(self):
        if threading.current_thread() is not threading.main_thread():
            self.skipTest("signal handlers can be changed in the main thread only")
        for signum in self.ALL:
            previous = signal.getsignal(signum)
            if previous is None:  # installed outside Python: it could not be put back
                self.skipTest(f"{signum.name} has a handler installed outside Python")
            self.addCleanup(signal.signal, signum, previous)
        held = getattr(adoption_status, "HELD_INTERRUPTS", {})
        self.addCleanup(held.update, {key: value for key, value in held.items()})

    def set_all(self, handler, signals=None) -> None:
        for signum in self.SIGNALS if signals is None else signals:
            signal.signal(signum, handler)

    def test_an_ignored_signal_stays_ignored(self):
        self.set_all(signal.SIG_IGN, self.ALL)
        with signals_interrupt_probes():
            for signum in self.ALL:
                self.assertEqual(signal.getsignal(signum), signal.SIG_IGN, signum.name)
        for signum in self.ALL:
            self.assertEqual(signal.getsignal(signum), signal.SIG_IGN, signum.name)

    def test_sigint_still_raises_keyboard_interrupt_and_is_restored(self):
        for label, starting in (("default_int_handler", signal.default_int_handler), ("SIG_DFL", signal.SIG_DFL)):
            with self.subTest(starting=label):
                signal.signal(signal.SIGINT, starting)
                with signals_interrupt_probes():
                    handler = signal.getsignal(signal.SIGINT)
                    self.assertTrue(callable(handler))
                    self.assertIsNot(handler, starting)
                    with self.assertRaises(KeyboardInterrupt):
                        handler(signal.SIGINT, None)
                self.assertEqual(signal.getsignal(signal.SIGINT), starting)

    def test_an_interrupt_during_a_hold_is_raised_when_the_hold_ends(self):
        self.set_all(signal.SIG_DFL)
        signal.signal(signal.SIGINT, signal.default_int_handler)
        reached = False
        with signals_interrupt_probes():
            with self.assertRaises(SystemExit) as raised:
                with adoption_status.held_interrupts():
                    signal.getsignal(signal.SIGTERM)(signal.SIGTERM, None)  # held: nothing is raised yet
                    signal.getsignal(signal.SIGINT)(signal.SIGINT, None)  # a second one: the first is kept
                    reached = True
            self.assertTrue(reached, "an interrupt was raised inside the hold")
            self.assertEqual(raised.exception.code, 128 + signal.SIGTERM)
            with adoption_status.held_interrupts():  # nothing is left pending
                pass
            with self.assertRaises(KeyboardInterrupt):  # and outside a hold, the handlers raise at once
                signal.getsignal(signal.SIGINT)(signal.SIGINT, None)

    def test_a_release_raises_what_was_held_then_the_hold_resumes(self):
        # A failure inside the hold would itself be replaced by the interrupt held at its end, so the block
        # records that it ran to the end.
        self.set_all(signal.SIG_DFL)
        reached = False
        with signals_interrupt_probes():
            handler = signal.getsignal(signal.SIGTERM)
            with self.assertRaises(SystemExit):  # the last one, held until the hold ends
                with adoption_status.held_interrupts():
                    handler(signal.SIGTERM, None)
                    with self.assertRaises(SystemExit):
                        with adoption_status.interrupts_released():
                            self.fail("an interrupt held before the release was not raised as it started")
                    self.assertTrue(adoption_status.HELD_INTERRUPTS["holding"], "the hold did not resume")
                    with self.assertRaises(SystemExit):
                        with adoption_status.interrupts_released():
                            handler(signal.SIGTERM, None)  # raised at once
                    self.assertTrue(adoption_status.HELD_INTERRUPTS["holding"], "the hold did not resume")
                    handler(signal.SIGTERM, None)
                    reached = True
            self.assertTrue(reached, "the hold's block stopped early")
            self.assertEqual(adoption_status.HELD_INTERRUPTS, {"holding": False, "pending": None})

    def run_probe_interrupted_at(self, k: int, argv: list[str], seconds: float):
        """run_version_probe(argv, seconds), with the SIGTERM handler called at the start of the k-th line that
        PROBE_FUNCTIONS execute before a KILL to the probe's group has returned, as CPython calls a handler for a
        signal that has arrived. Once that KILL is sent, nothing of the group is left to outlive it. A line that
        starts with a NOP (a try statement's own line) is not counted: CPython runs a Python signal handler only
        where it checks for pending signals, never at a NOP, and a NOP can lie outside every exception handler's
        range, as the NOP of a try statement in run_version_probe does, so an exception raised there would skip
        every cleanup, which no signal can cause. Returns that line, or None when fewer than k lines ran."""
        functions = [getattr(adoption_status, name, None) for name in self.PROBE_FUNCTIONS]
        traced = {getattr(function, "__wrapped__", function).__code__ for function in functions if function}
        handler, count, where, killed = signal.getsignal(signal.SIGTERM), 0, None, False
        signal_group = adoption_status.signal_group

        def signal_group_noting_the_kill(group, signum):
            nonlocal killed
            signal_group(group, signum)
            killed = killed or signum == signal.SIGKILL

        def line(frame, event, _arg):
            nonlocal count, where
            if event == "line" and not killed and frame.f_code.co_code[frame.f_lasti] != dis.opmap["NOP"]:
                count += 1
                if count == k:
                    where = f"{frame.f_code.co_name}, line {frame.f_lineno}"
                    handler(signal.SIGTERM, frame)
            return line

        previous = sys.gettrace()
        with patch.object(adoption_status, "signal_group", signal_group_noting_the_kill):
            sys.settrace(lambda frame, _event, _arg: line if frame.f_code in traced else None)
            try:
                adoption_status.run_version_probe(argv, seconds)
            except SystemExit as error:
                self.assertEqual(error.code, 128 + signal.SIGTERM)
            finally:
                sys.settrace(previous)
        return where

    @unittest.skipUnless(SLEEP, "needs a sleep executable")
    def test_an_interrupt_at_the_start_of_any_line_of_a_probe_run_still_kills_its_group(self):
        # One run per line: the interrupt lands at the start of the first line, then the second, and so on, until a
        # run sends its group the KILL with no line left. The probe and its background child ignore SIGTERM, so only
        # that KILL ends them, whether the probe exits at once or outlives its bound (TERM, then KILL).
        self.set_all(signal.SIG_DFL)
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root, True)
        scenarios = (("exits at once", "printf 'tool 1.2.3\\n'", 10),
                     ("outlives its bound", f"exec '{SLEEP}' 30", 0.1))
        with signals_interrupt_probes(), patch.object(adoption_status, "PINNED_VERSION_KILL_GRACE_SECONDS", 0.05):
            for scenario, then, seconds in scenarios:
                with self.subTest(probe=scenario):
                    left_running, started_then_interrupted, k = [], 0, 0
                    while True:
                        k += 1
                        work = Path(tempfile.mkdtemp(dir=root))
                        descendant = Descendant(self, work)
                        probe = work / "probe"
                        probe.write_text(f"#!/bin/sh\ntrap '' TERM\n{descendant.script(then)}\n")
                        probe.chmod(0o755)
                        where = self.run_probe_interrupted_at(k, [str(probe)], seconds)
                        self.assertEqual(adoption_status.HELD_INTERRUPTS, {"holding": False, "pending": None},
                                         f"a hold was left on after an interrupt at {where}")
                        if descendant.started():
                            started_then_interrupted += where is not None
                            if not descendant.gone(3):
                                left_running.append(where or "no interrupt")
                        if where is None:
                            break
                    self.assertGreater(started_then_interrupted, 0, "no interrupt landed after the child started")
                    self.assertEqual(left_running, [], "the probe's background child outlived these interrupts")

    def test_a_default_signal_ends_the_check_through_system_exit_and_is_restored(self):
        self.set_all(signal.SIG_DFL)
        with signals_interrupt_probes():
            for signum in self.SIGNALS:
                handler = signal.getsignal(signum)
                self.assertTrue(callable(handler), signum.name)
                with self.assertRaises(SystemExit) as raised:
                    handler(signum, None)
                self.assertEqual(raised.exception.code, 128 + signum)
        for signum in self.SIGNALS:
            self.assertEqual(signal.getsignal(signum), signal.SIG_DFL, signum.name)

    def test_a_handler_installed_by_someone_else_is_left_in_place(self):
        def theirs(_signum, _frame):
            pass

        self.set_all(theirs, self.ALL)
        with signals_interrupt_probes():
            for signum in self.ALL:
                self.assertIs(signal.getsignal(signum), theirs, signum.name)
        for signum in self.ALL:
            self.assertIs(signal.getsignal(signum), theirs, signum.name)


class ClientWiringTests(unittest.TestCase):
    """--client-wiring on fake homes: fixed keys, booleans and counts only, never text from a file."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        base = Path(temporary.name)
        self.home, self.root = base / "home", base / "checkout"
        self.home.mkdir()
        self.root.mkdir()
        self.env = {"HOME": str(self.home)}

    def write(self, relative: str, content, base: Path | None = None) -> Path:
        path = (base or self.home) / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content if isinstance(content, str) else json.dumps(content), encoding="utf-8")
        return path

    def claude_settings(self) -> dict:
        hooks = {event: [ai_memory_group(event)] for event in CLAUDE_EVENTS}
        hooks["PreToolUse"].insert(0, {"matcher": "Bash", "hooks": [
            {"type": "command", "command": f"/opt/{PRIVATE}/bin/rtk hook claude"},
            {"type": "command", "command": f"python3 /opt/{PRIVATE}/secret_path_guard.py", "timeout": 10}]})
        env = {"CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH": "1", "CLAUDE_CODE_WORKFLOW_MAX_CONCURRENT_AGENTS": "8",
               "PATH": f"/opt/{PRIVATE}/bin", "OTEL_EXPORTER_OTLP_ENDPOINT": f"http://{PRIVATE}"}
        return {"env": env, "hooks": hooks, "enabledPlugins": {"context-mode@context-mode": True}}

    def wire(self):
        self.write(".claude/settings.json", self.claude_settings())
        self.write(".claude/plugins/installed_plugins.json", {"version": 2, "plugins": {"context-mode@context-mode": [
            {"scope": "user", "installPath": f"/opt/{PRIVATE}", "gitCommitSha": "a" * 40}]}})
        self.write(".codex/config.toml", CODEX_CONFIG)
        self.write(".codex/AGENTS.md", f"# {PRIVATE}\n\n@RTK.md\n")
        self.write(".codex/RTK.md", f"# RTK {PRIVATE}\n")
        self.write(".codex/hooks.json", {"hooks": {event: [ai_memory_group(event)] for event in CODEX_EVENTS}})
        self.write(".codex/plugins/cache/context-mode/context-mode/1.0.169/.codex-plugin/plugin.json",
                   {"name": PRIVATE})
        self.write(".claude/settings.json", {"env": {"CLAUDE_CODE_WORKFLOW_MAX_CONCURRENT_AGENTS": "8",
                                                     "CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH": "1"}}, self.root)
        self.write(".codex/config.toml", CODEX_CONFIG, self.root)

    def wiring(self, env=None) -> dict:
        result = client_wiring(self.root, self.env if env is None else env)
        self.assertEqual(set(result), {*CLIENT_WIRING_KEYS, "complete"})
        self.assertIsInstance(result["complete"], bool)
        self.assertEqual({group: tuple(result[group]) for group in CLIENT_WIRING_KEYS}, CLIENT_WIRING_KEYS)
        for value in leaves(result):
            self.assertTrue(value is None or isinstance(value, (bool, int)), repr(value))
        rendered = json.dumps(result)
        for private in (PRIVATE, str(self.home), str(self.root)):
            self.assertNotIn(private, rendered)
        return result

    def test_a_wired_home_reports_every_check_and_no_file_text(self):
        self.wire()
        self.assertEqual(self.wiring(), WIRED)

    def test_an_unwired_home_reports_false_and_zero(self):
        self.assertEqual(self.wiring(), {
            "claude": {"rtk_hook": False, "ai_memory_hook_events": 0, "context_mode_plugin_enabled": False,
                       "subagent_spawn_depth_1": False, "workflow_concurrency_set": False,
                       "effort_level_env_unset": True, "agent_teams_off": True},
            "project": {"settings_depth_and_concurrency": False,
                        "codex_mcp_servers_present": dict.fromkeys(SERVERS, False)},
            # Without a config.toml Codex keeps its default: hooks on.
            "codex": {"rtk_instructions": False, "context_mode_plugin_enabled": False,
                      "mcp_servers_present": dict.fromkeys(SERVERS, False), "hooks_feature_enabled": True,
                      "ai_memory_hook_events": 0},
            "complete": False})

    def test_malformed_files_report_null_without_raising(self):
        self.wire()
        self.write(".claude/settings.json", '{"hooks": ')
        self.write(".codex/config.toml", f"[mcp_servers.serena\ncommand = \"{PRIVATE}\"\n")
        self.write(".codex/hooks.json", f'["{PRIVATE}"]')
        self.write(".codex/AGENTS.md", b"\xff\xfe@RTK.md\n")
        self.write(".claude/settings.json", "[]", self.root)
        self.write(".codex/config.toml", "= broken", self.root)
        self.assertEqual(self.wiring(), {
            "claude": dict.fromkeys(CLIENT_WIRING_KEYS["claude"]),
            "project": {"settings_depth_and_concurrency": None, "codex_mcp_servers_present": dict.fromkeys(SERVERS)},
            "codex": {"rtk_instructions": None, "context_mode_plugin_enabled": None,
                      "mcp_servers_present": dict.fromkeys(SERVERS), "hooks_feature_enabled": None,
                      "ai_memory_hook_events": None},
            "complete": False})

    def test_directories_oversized_files_and_dangling_links_are_unreadable(self):
        self.wire()
        (self.home / ".codex/config.toml").unlink()
        (self.home / ".codex/config.toml").mkdir()
        hooks = {"hooks": {event: [ai_memory_group(event)] for event in CODEX_EVENTS}}
        self.write(".codex/hooks.json", json.dumps(hooks) + " " * 1_048_576)  # valid JSON, over the limit
        (self.home / ".claude/settings.json").unlink()
        (self.home / ".claude/settings.json").symlink_to(self.home / "missing-settings.json")
        result = self.wiring()
        self.assertEqual(set(result["claude"].values()), {None})
        self.assertIsNone(result["codex"]["context_mode_plugin_enabled"])
        self.assertEqual(result["codex"]["mcp_servers_present"], dict.fromkeys(SERVERS))
        self.assertIsNone(result["codex"]["hooks_feature_enabled"])
        self.assertIsNone(result["codex"]["ai_memory_hook_events"])
        self.assertTrue(result["codex"]["rtk_instructions"])
        self.assertIs(result["complete"], False)

    def test_wrong_types_inside_valid_files_are_not_wiring(self):
        self.write(".claude/settings.json", {
            "hooks": {"PreToolUse": f"/opt/{PRIVATE}/rtk hook claude",
                      "Stop": [3, {"hooks": "ai-memory hook"}, {"hooks": [{"type": "command", "command": 7}]}]},
            "env": ["CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH"], "enabledPlugins": ["context-mode@context-mode"]})
        self.write(".codex/config.toml",
                   'plugins = "context-mode@context-mode"\nmcp_servers = ["serena"]\nfeatures = ["hooks"]\n')
        self.write(".codex/hooks.json", {"hooks": [f"/opt/{PRIVATE}/ai-memory hook"]})
        self.write(".codex/AGENTS.md", "@RTK.md\n")  # the referenced RTK.md is absent
        self.write(".claude/settings.json", {"env": {"CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH": True,
                                                     "CLAUDE_CODE_WORKFLOW_MAX_CONCURRENT_AGENTS": "999"}}, self.root)
        result = self.wiring()
        self.assertEqual(result["claude"], {"rtk_hook": False, "ai_memory_hook_events": 0,
                                            "context_mode_plugin_enabled": False, "subagent_spawn_depth_1": False,
                                            "workflow_concurrency_set": False, "effort_level_env_unset": True,
                                            "agent_teams_off": True})
        self.assertFalse(result["project"]["settings_depth_and_concurrency"])
        self.assertEqual(result["codex"], {"rtk_instructions": False, "context_mode_plugin_enabled": False,
                                           "mcp_servers_present": dict.fromkeys(SERVERS, False),
                                           "hooks_feature_enabled": False, "ai_memory_hook_events": 0})
        self.assertIs(result["complete"], False)

    def test_the_rtk_hook_needs_a_bash_matcher_and_the_claude_hook_subcommand(self):
        self.wire()
        settings = self.claude_settings()
        cases = (("Bash", "rtk hook claude", True), ("", "rtk hook claude", True), ("*", "rtk hook claude", True),
                 (None, "rtk hook claude", True), ("Edit|Bash", "rtk hook claude", True),
                 ("Edit", "rtk hook claude", False), ("(", "rtk hook claude", False),
                 (["Bash"], "rtk hook claude", False),
                 ("Bash", "rtk hook codex", False), ("Bash", "rtk rewrite", False),
                 ("Bash", "echo rtk hook claude", False), ("Bash", "rtk 'hook claude", False))
        for matcher, command, expected in cases:
            with self.subTest(matcher=matcher, command=command):
                group = {"hooks": [{"type": "command", "command": command}]}
                if matcher is not None:
                    group["matcher"] = matcher
                settings["hooks"]["PreToolUse"][0] = group
                self.write(".claude/settings.json", settings)
                self.assertIs(self.wiring()["claude"]["rtk_hook"], expected)
        settings = self.claude_settings()
        settings["disableAllHooks"] = True
        self.write(".claude/settings.json", settings)
        claude = self.wiring()["claude"]
        self.assertEqual((claude["rtk_hook"], claude["ai_memory_hook_events"]), (False, 0))

    def test_codex_hooks_are_on_by_default_and_false_turns_them_off(self):
        # Codex 0.155.1: "hooks" is stable and default-enabled, "codex_hooks" its legacy alias, applied first.
        self.wire()
        cases = (("", True), ("[features]\n", True), ("[features]\nhooks = true\n", True),
                 ("[features]\nhooks = false\n", False), ("[features]\ncodex_hooks = false\n", False),
                 ("[features]\ncodex_hooks = false\nhooks = true\n", True),
                 ("[features]\nhooks = false\ncodex_hooks = true\n", False),
                 ('[features]\nhooks = "true"\n', False), ("[features]\ncodex_hooks = 1\n", False))
        for features, expected in cases:
            with self.subTest(features=features):
                self.write(".codex/config.toml", CODEX_BASE + "\n" + features)
                result = self.wiring()
                self.assertIs(result["codex"]["hooks_feature_enabled"], expected)
                self.assertEqual(result["codex"]["ai_memory_hook_events"], 7 if expected else 0)
                self.assertIs(result["codex"]["context_mode_plugin_enabled"], True)
                self.assertIs(result["complete"], expected)
        self.write(".codex/config.toml", 'features = "hooks"\n' + CODEX_BASE)
        self.assertIs(self.wiring()["codex"]["hooks_feature_enabled"], False)
        self.write(".codex/config.toml", "= broken")  # hooks.json is still valid: the count is unknown, not zero
        codex = self.wiring()["codex"]
        self.assertEqual((codex["hooks_feature_enabled"], codex["ai_memory_hook_events"]), (None, None))

    def test_complete_is_the_documented_rule(self):
        self.wire()
        self.assertIs(self.wiring()["complete"], True)
        elsewhere = CODEX_CONFIG.replace("[mcp_servers.serena]\n", "[mcp_servers.other]\n")
        self.write(".codex/config.toml", elsewhere)  # still named in the project config.toml
        self.assertIs(self.wiring()["complete"], True)
        self.write(".codex/config.toml", elsewhere, self.root)  # now in neither
        self.assertIs(self.wiring()["complete"], False)
        for relative, content, base in ((".codex/hooks.json", {"hooks": {}}, None),  # a zero hook count
                                        (".codex/AGENTS.md", "# no instructions\n", None),  # one false boolean
                                        (".codex/config.toml", "= broken", self.root)):  # one unreadable file
            with self.subTest(relative=relative, project=base is not None):
                self.wire()
                self.write(relative, content, base)
                self.assertIs(self.wiring()["complete"], False)

    def test_the_concurrency_cap_must_be_an_integer_the_client_accepts(self):
        self.wire()
        for value, expected in (("8", True), (8, True), ("256", True), (" 16 ", True), ("1", True), ("0", False),
                                ("257", False), ("-1", False), ("8.5", False), ("", False), (True, False),
                                (None, False)):
            with self.subTest(value=value):
                settings = self.claude_settings()
                settings["env"]["CLAUDE_CODE_WORKFLOW_MAX_CONCURRENT_AGENTS"] = value
                self.write(".claude/settings.json", settings)
                self.write(".claude/settings.json", {"env": settings["env"]}, self.root)
                result = self.wiring()
                self.assertIs(result["claude"]["workflow_concurrency_set"], expected)
                self.assertIs(result["project"]["settings_depth_and_concurrency"], expected)

    def test_only_ai_memory_hook_commands_are_counted(self):
        self.wire()
        settings = self.claude_settings()
        settings["hooks"]["Stop"] = [{"hooks": [{"type": "command", "command": f"/opt/{PRIVATE}/ai-memory status"}]}]
        settings["hooks"]["SessionEnd"] = [{"hooks": [{"type": "command", "command": "echo ai-memory hook"}]}]
        settings["hooks"]["PreCompact"][0]["hooks"][0]["type"] = "prompt"
        self.write(".claude/settings.json", settings)
        self.assertEqual(self.wiring()["claude"]["ai_memory_hook_events"], 5)

    def test_effort_and_agent_team_opt_ins_are_found_by_name_whatever_their_value(self):
        self.wire()
        claude = self.wiring({**self.env, "CLAUDE_CODE_EFFORT_LEVEL": PRIVATE})["claude"]
        self.assertEqual((claude["effort_level_env_unset"], claude["agent_teams_off"]), (False, True))
        claude = self.wiring({**self.env, "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "0"})["claude"]
        self.assertEqual((claude["effort_level_env_unset"], claude["agent_teams_off"]), (True, False))
        settings = self.claude_settings()
        settings["env"].update(CLAUDE_CODE_EFFORT_LEVEL=PRIVATE, CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=PRIVATE)
        self.write(".claude/settings.json", settings)
        claude = self.wiring()["claude"]
        self.assertEqual((claude["effort_level_env_unset"], claude["agent_teams_off"]), (False, False))

    def test_disabled_or_uninstalled_plugins_and_servers_are_not_wired(self):
        self.wire()
        self.write(".claude/plugins/installed_plugins.json",
                   {"version": 2, "plugins": {"context-mode@context-mode": []}})
        shutil.rmtree(self.home / ".codex/plugins")
        self.write(".codex/config.toml",
                   CODEX_CONFIG.replace("[mcp_servers.serena]\n", "[mcp_servers.serena]\nenabled = false\n"))
        result = self.wiring()
        self.assertFalse(result["claude"]["context_mode_plugin_enabled"])
        self.assertFalse(result["codex"]["context_mode_plugin_enabled"])
        self.assertEqual(result["codex"]["mcp_servers_present"],
                         {"serena": False, "socraticode": True, "ai-memory": True})
        self.write(".claude/plugins/installed_plugins.json", "{")
        self.assertIsNone(self.wiring()["claude"]["context_mode_plugin_enabled"])  # enabled, registry unreadable
        settings = self.claude_settings()
        settings["enabledPlugins"]["context-mode@context-mode"] = False
        self.write(".claude/settings.json", settings)
        self.assertFalse(self.wiring()["claude"]["context_mode_plugin_enabled"])

    def test_client_homes_follow_claude_config_dir_and_codex_home(self):
        self.wire()
        moved = self.home / "configured"
        moved.mkdir()
        (self.home / ".claude").rename(moved / "claude")
        (self.home / ".codex").rename(moved / "codex")
        env = {**self.env, "CLAUDE_CONFIG_DIR": str(moved / "claude"), "CODEX_HOME": str(moved / "codex")}
        self.assertEqual(self.wiring(env), WIRED)
        self.assertFalse(self.wiring()["claude"]["rtk_hook"])

    def test_a_text_value_can_never_leave_the_check(self):
        leaked = {**dict.fromkeys(CLIENT_WIRING_KEYS["claude"], True), "rtk_hook": PRIVATE}
        with patch("scripts.adoption_status.claude_wiring", return_value=leaked), self.assertRaises(AssertionError):
            client_wiring(self.root, self.env)
        with patch("scripts.adoption_status.codex_wiring", return_value={"extra": True}), \
                self.assertRaises(AssertionError):
            client_wiring(self.root, self.env)


class TokenEfficiencyProfileTests(unittest.TestCase):
    """The selected token practice is a real, resolvable profile of adoption/manifest.json."""

    LAYERS = ("token-efficiency", "code-navigation", "document-retrieval", "semantic-rag", "durable-memory",
              "mcp-surfaces")
    CURRENT_CHOICE = {"RTK": "rtk", "Context Mode": "context-mode", "Repomix": "repomix", "Headroom": "headroom",
                      "TOON": "toon", "ccusage": "ccusage"}
    OPTIONAL = {"jcodemunch-mcp", "ast-grep", "codebase-memory-mcp", "context-hub", "agentsview", "claude-hud",
                "otel-tui", "omniroute"}

    @staticmethod
    def load(relative: str):
        return json.loads((REPO / relative).read_text(encoding="utf-8"))

    def setUp(self):
        self.profile = next(p for p in self.load("adoption/manifest.json")["profiles"] if p["id"] == "token-efficiency")
        self.rows = {row["component_id"] for row in self.load("docs/token-efficiency-stack.json")["rows"]}

    def test_the_profile_resolves_to_its_commands_and_recipes(self):
        with patch("scripts.adoption_status.shutil.which", return_value="/private/bin/tool"), \
                patch("scripts.adoption_status.git_revision", return_value=None):
            result = inspect_adoption(REPO / "adoption/manifest.json", REPO, ["token-efficiency"])
        self.assertEqual(result["manifest"]["status"], "valid", result["errors"])
        [profile] = result["profiles"]
        self.assertEqual(profile["status"], "prerequisites_present")
        self.assertEqual([item["name"] for item in profile["commands"]], self.profile["required_commands"])
        self.assertTrue(profile["recipes"] and all(item["present"] for item in profile["recipes"]))

    def test_the_profile_is_the_landscape_selection_and_leaves_optional_rows_out(self):
        layers = {layer["layer_id"]: layer for layer in self.load("catalogs/landscape/foundation.json")["layers"]}
        stack = {component["id"] for component in self.load("manifests/stack.json")["components"]}
        selected = set(self.profile["component_ids"])
        self.assertLessEqual(selected, stack)
        self.assertEqual(selected - self.rows, {"codex", "claude-code"})
        choice = layers["token-efficiency"]["current_choice"]
        self.assertTrue(all(name in choice for name in self.CURRENT_CHOICE), choice)
        winners = {winner["component_id"] for layer_id in self.LAYERS for winner in layers[layer_id]["winners"]}
        self.assertEqual(selected & self.rows, (winners & self.rows) | set(self.CURRENT_CHOICE.values()),
                         "a token row these layers now select (or drop) must join (or leave) the profile")
        self.assertEqual(selected & self.OPTIONAL, set())
        self.assertLessEqual(self.OPTIONAL, self.rows)


if __name__ == "__main__":
    unittest.main()
