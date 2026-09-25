"""Adoption preflight boundaries; no credentials, services, or model calls."""

import contextlib
import io
import json
import os
from pathlib import Path
import shutil
from shutil import which as native_which
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts.adoption_status import (CLIENT_WIRING_KEYS, CLIENT_WIRING_LIMITATIONS, NO_CLIENT_STATE, client_wiring,
                                     git_revision, inspect_adoption, main)

REPO = Path(__file__).resolve().parents[1]
PRIVATE = "private-value-never-reported"
CLAUDE_EVENTS = ("PreToolUse", "SessionStart", "SubagentStop", "PostToolUse", "PreCompact", "Stop", "SessionEnd",
                 "SubagentStart")
CODEX_EVENTS = ("SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "PreCompact", "Stop", "SessionEnd")
CODEX_CONFIG = f"""model = "{PRIVATE}"

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
SERVERS = ("serena", "socraticode", "ai-memory")
WIRED = {
    "claude": {"rtk_hook": True, "ai_memory_hook_events": 8, "context_mode_plugin_enabled": True,
               "subagent_spawn_depth_1": True, "workflow_concurrency_set": True,
               "effort_level_env_unset": True, "agent_teams_off": True},
    "project": {"settings_depth_and_concurrency": True, "codex_mcp_servers_present": dict.fromkeys(SERVERS, True)},
    "codex": {"rtk_instructions": True, "context_mode_plugin_enabled": True,
              "mcp_servers_present": dict.fromkeys(SERVERS, True), "ai_memory_hook_events": 7},
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
        canned = {"claude": {"rtk_hook": True}}
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
            self.assertEqual(main(["--manifest", str(self.path), "--client-wiring"]), 0)
        self.assertIn('Client wiring: {"claude": {"rtk_hook": true}}', output.getvalue())

    def test_client_wiring_is_reported_even_for_an_invalid_manifest(self):
        self.path.write_text("{", encoding="utf-8")
        home = self.root / "empty-home"
        home.mkdir()
        result = inspect_adoption(self.path, self.root, with_client_wiring=True, env={"HOME": str(home)})
        self.assertEqual(result["manifest"]["status"], "invalid")
        self.assertEqual(set(result["client_wiring"]), set(CLIENT_WIRING_KEYS))
        self.assertNotIn(str(self.root), json.dumps(result))


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
        self.assertEqual({group: tuple(values) for group, values in result.items()}, CLIENT_WIRING_KEYS)
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
            "codex": {"rtk_instructions": False, "context_mode_plugin_enabled": False,
                      "mcp_servers_present": dict.fromkeys(SERVERS, False), "ai_memory_hook_events": 0}})

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
                      "mcp_servers_present": dict.fromkeys(SERVERS), "ai_memory_hook_events": None}})

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
        self.assertIsNone(result["codex"]["ai_memory_hook_events"])
        self.assertTrue(result["codex"]["rtk_instructions"])

    def test_wrong_types_inside_valid_files_are_not_wiring(self):
        self.write(".claude/settings.json", {
            "hooks": {"PreToolUse": f"/opt/{PRIVATE}/rtk hook claude",
                      "Stop": [3, {"hooks": "ai-memory hook"}, {"hooks": [{"type": "command", "command": 7}]}]},
            "env": ["CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH"], "enabledPlugins": ["context-mode@context-mode"]})
        self.write(".codex/config.toml", 'plugins = "context-mode@context-mode"\nmcp_servers = ["serena"]\n')
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
                                           "ai_memory_hook_events": 0})

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
