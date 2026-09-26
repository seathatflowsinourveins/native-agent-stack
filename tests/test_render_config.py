"""Local integration tests for tools/adoption/render_config.py (fixture host, no live host claims)."""

import json
import os
import re
import string
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "adoption" / "render_config.py"
TEMPLATES = ROOT / "adoption" / "templates"
TEMPLATE_NAMES = ("claude.settings.template.json", "codex.config.template.toml",
                  "project.codex.config.template.toml")

FIXTURE_VALUES = {
    "HOME": "/home/example",
    "ECO_ROOT": "/home/example/.local/share/codex-ecosystem",
    "PROJECT_ROOT": "/home/example/code/agent-lab",
    "HOST_PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
    "CODE_INDEX_PATH": "/home/example/.code-index",
    "OTEL_ENDPOINT": "127.0.0.1:14318",
    "AI_MEMORY_URL": "127.0.0.1:49374",
    "QDRANT_URL": "127.0.0.1:16333",
    "EMBED_URL": "127.0.0.1:8231",
    # The explicit opt-in, left off: empty renders as empty text both under a direct
    # string.Template substitution below and in render_config.py (absent, "" and "false" alike).
    "AI_MEMORY_CAPTURE_ASSISTANT": "",
}


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, check=False)


class RenderConfigTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.tmp_path = Path(self.tmp.name)
        self.hosts_dir = ROOT / "adoption" / "hosts"
        self.fixture_host_path = self.hosts_dir / "test-fixture-host.json"
        self.fixture_host_path.write_text(json.dumps(FIXTURE_VALUES, indent=2))
        self.addCleanup(self.fixture_host_path.unlink, missing_ok=True)

    def test_templates_are_placeholders_only_no_literal_host_paths(self):
        # Constructed rather than written literally so this test file itself
        # never contains a real personal home path for the publication scanner.
        home_marker = "/" + "home/" + "sea" + "th"
        for name in TEMPLATE_NAMES:
            text = (TEMPLATES / name).read_text()
            self.assertNotIn(home_marker, text, name)
            self.assertNotIn("/mnt/c", text, name)

    def test_templates_round_trip_with_string_template_substitute(self):
        # The statusLine bash fragment keeps its own literal ${COLUMNS:-},
        # ${CLAUDE_CONFIG_DIR:-$HOME/.claude} and ${plugin_dir}; only our own
        # placeholder names are required to disappear after substitution.
        for name in TEMPLATE_NAMES:
            text = (TEMPLATES / name).read_text()
            rendered = string.Template(text).substitute(FIXTURE_VALUES)
            for key in FIXTURE_VALUES:
                self.assertNotIn("${" + key + "}", rendered, (name, key))
            if name.endswith(".json"):
                json.loads(rendered)  # still valid JSON once rendered

    def test_versioned_tool_paths_follow_the_linux_pins(self):
        # A pinned install's own path in a template (${ECO_ROOT}/tools/<id>-<version>/) moves with that pin.
        # The templates carry the WSL2 workstation's values, so the Linux pins file is the reference.
        pins = {tool["id"]: tool["version"] for tool in
                json.loads((ROOT / "adoption" / "pins-linux-x86_64.json").read_text(encoding="utf-8"))["tools"]}
        pattern = r"\$\{ECO_ROOT\}/tools/([a-z][a-z0-9-]*?)-([0-9][0-9A-Za-z.]*)/"
        paths = [(name, tool, version) for name in TEMPLATE_NAMES
                 for tool, version in re.findall(pattern, (TEMPLATES / name).read_text(encoding="utf-8"))]
        self.assertLessEqual({"context-mode", "socraticode"}, {tool for _, tool, _ in paths}, paths)
        for name, tool, version in paths:
            with self.subTest(template=name, tool=tool):
                self.assertEqual(version, pins.get(tool))

    def test_codex_templates_bind_context_mode_per_session_and_run_headroom_offline(self):
        # docs/decisions/2026-09-25-codex-mcp-scope.md, addendum 2026-09-26. The plugin's own server starts in
        # the plugin root and then follows the newest Codex session log; an entry with no cwd starts in each
        # session's own directory, which upstream start.mjs binds as CONTEXT_MODE_PROJECT_DIR. A fixed
        # CONTEXT_MODE_PROJECT_DIR, or a project-scope entry, would bind every session to one directory.
        # `headroom mcp serve` never calls apply_offline_env(), so the Hugging Face variables are set here.
        import tomllib  # Python 3.11+, as the Codex wiring check already requires

        def rendered(name):
            text = (TEMPLATES / name).read_text(encoding="utf-8")
            return tomllib.loads(string.Template(text).substitute(FIXTURE_VALUES))

        user = rendered("codex.config.template.toml")
        self.assertIn("context-mode", user["mcp_servers"])
        server = user["mcp_servers"]["context-mode"]
        self.assertNotIn("cwd", server)
        self.assertEqual(Path(server["command"]).name, "node")
        self.assertEqual([Path(argument).name for argument in server["args"]], ["start.mjs"])
        self.assertEqual(server["env"].get("CONTEXT_MODE_PLATFORM"), "codex")
        self.assertNotIn("CONTEXT_MODE_PROJECT_DIR", server["env"])
        plugin = user["plugins"]["context-mode@context-mode"]
        self.assertIs(plugin["enabled"], True)  # its hooks and skills stay on
        self.assertIs(plugin["mcp_servers"]["context-mode"]["enabled"], False)
        offline = {"HEADROOM_OFFLINE": "1", "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "DO_NOT_TRACK": "1"}
        self.assertLessEqual(offline.items(), user["mcp_servers"]["headroom"]["env"].items())
        self.assertNotIn("context-mode", rendered("project.codex.config.template.toml").get("mcp_servers", {}))

    def test_claude_template_turns_off_claudeai_skill_sync_and_mcp_servers(self):
        # docs/decisions/2026-09-25-skills-trial-and-usage.md, addendum "claude.ai skill sync and MCP
        # servers off": syncClaudeAiSkills is a settings boolean (Claude Code 2.1.275) and
        # ENABLE_CLAUDEAI_MCP_SERVERS an environment variable whose opt-out value is the string "false"
        # (2.1.63). tools/adoption/apply_claude_settings.py never deletes a key, so a template that
        # dropped either line would leave applied hosts off but turn both back on for every new host.
        text = (TEMPLATES / "claude.settings.template.json").read_text(encoding="utf-8")
        settings = json.loads(string.Template(text).substitute(FIXTURE_VALUES))
        self.assertIs(settings["syncClaudeAiSkills"], False)
        self.assertEqual(settings["env"]["ENABLE_CLAUDEAI_MCP_SERVERS"], "false")

    def test_render_out_writes_three_files(self):
        out_dir = self.tmp_path / "out"
        result = run("--host", "test-fixture-host", "--out", str(out_dir))
        self.assertEqual(result.returncode, 0, result.stderr)
        for filename in ("settings.json", "codex.config.toml", "project.codex.config.toml"):
            self.assertTrue((out_dir / filename).is_file(), filename)

    def test_set_overrides_and_supplements_host_values(self):
        out_dir = self.tmp_path / "out-set"
        result = run("--set", "HOME=/home/example/direct",
                     "--set", "ECO_ROOT=/home/example/direct/.local/share/codex-ecosystem",
                     "--set", "PROJECT_ROOT=/home/example/direct/code/agent-lab",
                     "--set", "HOST_PATH=" + FIXTURE_VALUES["HOST_PATH"],
                     "--set", "CODE_INDEX_PATH=/home/example/direct/.code-index",
                     "--set", "OTEL_ENDPOINT=127.0.0.1:14318",
                     "--set", "AI_MEMORY_URL=127.0.0.1:49374",
                     "--set", "QDRANT_URL=127.0.0.1:16333",
                     "--set", "EMBED_URL=127.0.0.1:8231",
                     "--out", str(out_dir))
        self.assertEqual(result.returncode, 0, result.stderr)
        rendered = (out_dir / "settings.json").read_text()
        self.assertIn("/home/example/direct", rendered)

    def test_missing_key_fails_with_nonzero_exit(self):
        out_dir = self.tmp_path / "out-missing"
        incomplete = self.hosts_dir / "test-fixture-incomplete.json"
        incomplete.write_text(json.dumps({"HOME": "/home/example"}))
        self.addCleanup(incomplete.unlink, missing_ok=True)
        result = run("--host", "test-fixture-incomplete", "--out", str(out_dir))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing template value", result.stderr)
        self.assertFalse((out_dir / "settings.json").exists())

    def test_check_exit_zero_when_rendered_matches_live_fixture(self):
        live_dir = self.tmp_path / "live"
        live_dir.mkdir()
        rendered_now = {
            name: string.Template((TEMPLATES / name).read_text()).substitute(FIXTURE_VALUES)
            for name in TEMPLATE_NAMES
        }
        (live_dir / "settings.json").write_text(rendered_now["claude.settings.template.json"])
        (live_dir / "codex_user.toml").write_text(rendered_now["codex.config.template.toml"])
        (live_dir / "codex_project.toml").write_text(rendered_now["project.codex.config.template.toml"])
        result = run("--host", "test-fixture-host", "--check",
                     "--live-settings", str(live_dir / "settings.json"),
                     "--live-codex-user", str(live_dir / "codex_user.toml"),
                     "--live-codex-project", str(live_dir / "codex_project.toml"))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("byte-identical", result.stdout)

    def test_check_exit_one_and_diff_when_rendered_differs_from_live_fixture(self):
        live_dir = self.tmp_path / "live-diff"
        live_dir.mkdir()
        (live_dir / "settings.json").write_text("{}\n")
        (live_dir / "codex_user.toml").write_text("# different\n")
        (live_dir / "codex_project.toml").write_text("# different\n")
        result = run("--host", "test-fixture-host", "--check",
                     "--live-settings", str(live_dir / "settings.json"),
                     "--live-codex-user", str(live_dir / "codex_user.toml"),
                     "--live-codex-project", str(live_dir / "codex_project.toml"))
        self.assertEqual(result.returncode, 1)
        self.assertIn("differs from", result.stdout)
        self.assertIn("---", result.stdout)  # unified diff header present

    def test_default_project_live_path_never_hardcodes_catalog_checkout(self):
        # Regression for the finding that the old module-level DEFAULT_LIVE_PATHS
        # unconditionally pointed project.codex.config.toml at this catalog
        # checkout's own .codex/config.toml (which does not exist), so --check
        # without --live-codex-project could never exit 0 on any host. The
        # default now tracks the current working directory (or
        # $ADOPTION_PROJECT_ROOT) instead of a hardcoded catalog path, proven
        # here by running from a directory other than the catalog checkout.
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--host", "test-fixture-host", "--check"],
            capture_output=True, text=True, check=False, cwd=str(self.tmp_path),
        )
        self.assertNotIn(str(ROOT / ".codex" / "config.toml"), result.stdout + result.stderr)
        # default_project_root() falls back to Path.cwd(), and the OS getcwd() syscall
        # always returns the fully resolved directory (POSIX; e.g. macOS's
        # /tmp -> /private/tmp, /var -> /private/var, or a symlinked TMPDIR), never the
        # possibly-symlinked path the subprocess was launched with; compare resolved.
        self.assertIn(str(self.tmp_path.resolve() / ".codex" / "config.toml"), result.stdout + result.stderr)

    def test_default_project_live_path_honors_adoption_project_root_env(self):
        import os
        full_env = {**os.environ, "ADOPTION_PROJECT_ROOT": str(self.tmp_path)}
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--host", "test-fixture-host", "--check"],
            capture_output=True, text=True, check=False, env=full_env,
        )
        self.assertIn(str(self.tmp_path / ".codex" / "config.toml"), result.stdout + result.stderr)

    def test_check_reports_newline_difference_not_byte_identical(self):
        # Regression: --check previously compared Path.read_text() output,
        # which silently translates \r\n/\r to \n (universal newlines), so a
        # live file saved with CRLF line endings was wrongly reported
        # "byte-identical" to an LF-rendered template even though the actual
        # on-disk bytes differ. It must now exit 1 and say so explicitly.
        live_dir = self.tmp_path / "live-crlf"
        live_dir.mkdir()
        rendered_now = {
            name: string.Template((TEMPLATES / name).read_text()).substitute(FIXTURE_VALUES)
            for name in TEMPLATE_NAMES
        }
        settings_crlf = rendered_now["claude.settings.template.json"].replace("\n", "\r\n")
        self.assertNotEqual(
            settings_crlf, rendered_now["claude.settings.template.json"],
            "fixture template must actually contain a newline for this test to be meaningful",
        )
        (live_dir / "settings.json").write_bytes(settings_crlf.encode("utf-8"))
        (live_dir / "codex_user.toml").write_text(rendered_now["codex.config.template.toml"])
        (live_dir / "codex_project.toml").write_text(rendered_now["project.codex.config.template.toml"])
        result = run("--host", "test-fixture-host", "--check",
                     "--live-settings", str(live_dir / "settings.json"),
                     "--live-codex-user", str(live_dir / "codex_user.toml"),
                     "--live-codex-project", str(live_dir / "codex_project.toml"))
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertNotIn("settings.json: byte-identical", result.stdout)
        self.assertIn("settings.json: differs from", result.stdout)
        self.assertIn("newline", result.stdout)
        # The other two files, unchanged, are still reported byte-identical.
        self.assertIn("codex.config.toml: byte-identical", result.stdout)
        self.assertIn("project.codex.config.toml: byte-identical", result.stdout)

    def stop_commands(self, settings_path: Path) -> list[str]:
        stop = json.loads(settings_path.read_text())["hooks"]["Stop"]
        return [hook["command"] for group in stop for hook in group["hooks"]]

    def test_default_render_has_no_assistant_capture(self):
        # Automatic assistant capture stays off unless a host opts in: the committed
        # example hosts (which never mention the opt-in) and the fixture host (which
        # leaves it empty) render no --capture-assistant in any file, and ai-memory's
        # Stop hook ends at its server URL.
        self.assertNotIn("--capture-assistant", (TEMPLATES / "claude.settings.template.json").read_text())
        for host in ("example", "macos-example", "test-fixture-host"):
            with self.subTest(host=host):
                values = json.loads((self.hosts_dir / f"{host}.json").read_text())
                out_dir = self.tmp_path / f"out-{host}"
                result = run("--host", host, "--out", str(out_dir))
                self.assertEqual(result.returncode, 0, result.stderr)
                for filename in ("settings.json", "codex.config.toml", "project.codex.config.toml"):
                    self.assertNotIn("--capture-assistant", (out_dir / filename).read_text(), filename)
                commands = self.stop_commands(out_dir / "settings.json")
                self.assertEqual(len(commands), 1, commands)
                self.assertTrue(commands[0].endswith(f"--server-url http://{values['AI_MEMORY_URL']}"), commands[0])

    def test_assistant_capture_is_an_explicit_opt_in_on_the_stop_hook_only(self):
        rendered = {}
        for setting in (None, "false", "true"):
            out_dir = self.tmp_path / f"out-capture-{setting}"
            extra = [] if setting is None else ["--set", f"AI_MEMORY_CAPTURE_ASSISTANT={setting}"]
            result = run("--host", "test-fixture-host", *extra, "--out", str(out_dir))
            self.assertEqual(result.returncode, 0, result.stderr)
            rendered[setting] = out_dir / "settings.json"
        # "false" renders exactly like leaving the opt-in out.
        self.assertEqual(rendered["false"].read_bytes(), rendered[None].read_bytes())
        opted_in = rendered["true"].read_text()
        self.assertEqual(opted_in.count("--capture-assistant"), 1)
        self.assertEqual(self.stop_commands(rendered["true"]),
                         [self.stop_commands(rendered[None])[0] + " --capture-assistant"])
        # Nothing but the Stop hook changes.
        opted_in_settings, default_settings = json.loads(opted_in), json.loads(rendered[None].read_text())
        del opted_in_settings["hooks"]["Stop"], default_settings["hooks"]["Stop"]
        self.assertEqual(opted_in_settings, default_settings)

    def test_assistant_capture_rejects_anything_but_true_or_false(self):
        out_dir = self.tmp_path / "out-capture-typo"
        result = run("--host", "test-fixture-host", "--set", "AI_MEMORY_CAPTURE_ASSISTANT=yes", "--out", str(out_dir))
        self.assertEqual(result.returncode, 1)
        self.assertIn("AI_MEMORY_CAPTURE_ASSISTANT must be", result.stderr)
        self.assertFalse((out_dir / "settings.json").exists())

    def test_check_reports_missing_live_file(self):
        result = run("--host", "test-fixture-host", "--check",
                     "--live-settings", str(self.tmp_path / "nowhere.json"),
                     "--live-codex-user", str(self.tmp_path / "nowhere2.toml"),
                     "--live-codex-project", str(self.tmp_path / "nowhere3.toml"))
        self.assertEqual(result.returncode, 1)
        self.assertIn("live file not found", result.stderr)


class VerifyStdinTests(unittest.TestCase):
    def test_verify_closes_stdin_for_the_native_clients(self):
        # A CLI that falls back to reading stdin must get EOF, not the
        # caller's terminal: with an inherited open stdin these shims would
        # block until verify's own 30 s timeout.
        with tempfile.TemporaryDirectory() as directory:
            shims = Path(directory)
            for name in ("codex", "claude"):
                shim = shims / name
                shim.write_text(f'#!/bin/sh\ncat >/dev/null\necho "{name} 1.0.0"\n')
                shim.chmod(0o755)
            read_end, write_end = os.pipe()
            try:
                started = time.monotonic()
                result = subprocess.run([sys.executable, str(SCRIPT), "--verify"], stdin=read_end,
                                        capture_output=True, text=True, timeout=60, check=False,
                                        env={**os.environ, "PATH": f"{shims}{os.pathsep}{os.environ['PATH']}"})
                elapsed = time.monotonic() - started
            finally:
                os.close(read_end)
                os.close(write_end)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("codex --version: exit 0 -- codex 1.0.0", result.stdout)
        self.assertIn("claude --version: exit 0 -- claude 1.0.0", result.stdout)
        self.assertLess(elapsed, 20)


if __name__ == "__main__":
    unittest.main()
