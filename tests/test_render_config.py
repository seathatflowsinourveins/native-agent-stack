"""Local integration tests for tools/adoption/render_config.py (fixture host, no live host claims)."""

import importlib.util
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
    # Derived by render_config.py when a host file leaves it out (AiMemoryBinTests); the direct
    # substitutions below need it spelled out, so it names the Linux pin's install like the derivation.
    "AI_MEMORY_BIN": "/home/example/.local/share/codex-ecosystem/tools/ai-memory-{}/ai-memory".format(next(
        tool["version"] for tool in json.loads((ROOT / "adoption" / "pins-linux-x86_64.json").read_text(
            encoding="utf-8"))["tools"] if tool["id"] == "ai-memory")),
    # Derived the same way (SocratiCodeVersionTests), spelled out as the Linux pin for the direct substitutions.
    "SOCRATICODE_VERSION": next(
        tool["version"] for tool in json.loads((ROOT / "adoption" / "pins-linux-x86_64.json").read_text(
            encoding="utf-8"))["tools"] if tool["id"] == "socraticode"),
    # Derived from the platform's Codex pin (CodexModelTests), spelled out as the Linux pin's (0.159.2) model.
    "CODEX_MODEL": "gpt-6.1-sol",
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

    def test_hud_statusline_requires_an_installed_entry(self):
        # Upstream claude-hud v0.10.0 scripts/statusline.mjs checks that the
        # selected entry exists. A missing plugin must never fall back to the
        # open project's dist/index.js during installation or rollback.
        ecosystem = self.tmp_path / "ecosystem"
        node = ecosystem / "bin" / "node"
        node.parent.mkdir(parents=True)
        node.write_text('#!/bin/sh\nprintf "%s\\n" "$1"\n')
        node.chmod(0o755)
        workspace = self.tmp_path / "workspace"
        (workspace / "dist").mkdir(parents=True)
        (workspace / "dist" / "index.js").write_text("project code must not run\n")
        config = self.tmp_path / "claude"
        values = {**FIXTURE_VALUES, "ECO_ROOT": str(ecosystem)}
        settings = json.loads(string.Template(
            (TEMPLATES / "claude.settings.template.json").read_text()
        ).substitute(values))
        env = {**os.environ, "CLAUDE_CONFIG_DIR": str(config), "COLUMNS": "120"}

        def invoke():
            return subprocess.run(
                ["bash", "-c", settings["statusLine"]["command"]],
                cwd=workspace, env=env, stdin=subprocess.DEVNULL,
                capture_output=True, text=True, check=False,
            )

        with self.subTest(plugin="absent"):
            result = invoke()
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "")
        plugin = config / "plugins" / "cache" / "claude-hud" / "claude-hud" / "0.10.0"
        (plugin / "dist").mkdir(parents=True)
        with self.subTest(plugin="missing_entry"):
            result = invoke()
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "")
        entry = plugin / "dist" / "index.js"
        entry.write_text("installed plugin fixture\n")
        with self.subTest(plugin="installed"):
            result = invoke()
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, str(entry) + "\n")

    def test_versioned_tool_paths_follow_the_linux_pins(self):
        # A pinned install's own path in a template (${ECO_ROOT}/tools/<id>-<version>/) moves with that pin.
        # The templates carry the WSL2 workstation's values, so the Linux pins file is the reference.
        pins = {tool["id"]: tool["version"] for tool in
                json.loads((ROOT / "adoption" / "pins-linux-x86_64.json").read_text(encoding="utf-8"))["tools"]}
        # SocratiCode's version is a derived placeholder instead, since its Linux and macOS pins differ
        # (SocratiCodeVersionTests).
        pattern = r"\$\{ECO_ROOT\}/tools/([a-z][a-z0-9-]*?)-([0-9][0-9A-Za-z.]*)/"
        paths = [(name, tool, version) for name in TEMPLATE_NAMES
                 for tool, version in re.findall(pattern, (TEMPLATES / name).read_text(encoding="utf-8"))]
        self.assertLessEqual({"context-mode"}, {tool for _, tool, _ in paths}, paths)
        self.assertNotIn("socraticode", {tool for _, tool, _ in paths}, paths)
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
        self.assertEqual(server.get("default_tools_approval_mode"), "approve")

    def test_codex_user_template_sets_the_verified_base_keys(self):
        # PR-F and H4 of the 2026-09-27 settings synthesis (codex rows 8, 10, 20 and 21), each read at openai/codex
        # rust-v0.157.1: live search in every sandbox (core/src/config/mod.rs), no startup update check on a pinned
        # client (config/src/config_toml.rs L520-523), no shell snapshot of exported variables
        # (shell-command/src/shell_snapshot_exports.rs), and no trust for dated directories that no longer exist.
        # The user's 2026-09-30 defaults are Sol/Ultra coordination and Sol/Max generic children, supported by
        # rust-v0.159.2 models-manager/models.json and core/src/agent/child_config.rs L204-249. Selected role
        # configs still apply afterwards (L62-73). The gateway route lives only in the omniroute profile. Both
        # models are the one CODEX_MODEL placeholder, which CodexModelTests renders from each platform's Codex pin.
        import tomllib  # Python 3.11+, as above

        text = (TEMPLATES / "codex.config.template.toml").read_text(encoding="utf-8")
        user = tomllib.loads(string.Template(text).substitute(FIXTURE_VALUES))
        self.assertEqual(user["web_search"], "live")
        self.assertIs(user["check_for_update_on_startup"], False)
        self.assertIs(user["features"]["shell_snapshot"], False)  # exported secrets never land in a snapshot file
        self.assertIs(user["agents"]["enabled"], True)
        self.assertEqual(user["agents"]["max_concurrent_threads_per_session"], 3)
        self.assertEqual(user["agents"]["default_subagent_reasoning_effort"], "max")
        self.assertEqual(user["agents"]["default_subagent_model"], FIXTURE_VALUES["CODEX_MODEL"])
        self.assertEqual(user["model"], FIXTURE_VALUES["CODEX_MODEL"])
        self.assertEqual(user["model_reasoning_effort"], "ultra")
        self.assertEqual(sorted(user["projects"]), [FIXTURE_VALUES["PROJECT_ROOT"],
                                                    FIXTURE_VALUES["HOME"] + "/code/native-agent-stack-publication"])
        self.assertNotIn("codex-ecosystem/validation", text)
        self.assertNotIn("model_providers", user)
        self.assertNotIn("model_provider", user)

    def test_recipe_project_form_mirrors_start_mjs_and_approves_tools(self):
        # recipes/README.md "Retained Context Mode": the project-scoped form runs the bare `context-mode` CLI,
        # which skips upstream start.mjs. start.mjs sets both CLAUDE_PROJECT_DIR and CONTEXT_MODE_PROJECT_DIR
        # from the launch directory (start.mjs:42-51 at 6f0cc684), and the server reads project Bash denies
        # only through CLAUDE_PROJECT_DIR (src/server.ts:1111-1120), so the static form sets both. Approval
        # mode is the plugin manifest's own (.codex-plugin/mcp.json:10); without it a Codex run whose policy
        # is `never` refuses every ctx_* call.
        import tomllib  # Python 3.11+, as above

        section = (ROOT / "recipes" / "README.md").read_text(encoding="utf-8").split("\n## Retained Context Mode\n", 1)[1]
        section = section.split("\n## ", 1)[0]
        block = tomllib.loads(section.split("```toml\n", 1)[1].split("```", 1)[0])
        self.assertIs(block["plugins"]["context-mode@context-mode"]["mcp_servers"]["context-mode"]["enabled"], False)
        server = block["mcp_servers"]["context-mode"]
        self.assertEqual(server["command"], "context-mode")
        self.assertEqual(server.get("default_tools_approval_mode"), "approve")
        project = server["cwd"]
        self.assertEqual(server["env"].get("CONTEXT_MODE_PROJECT_DIR"), project)
        self.assertEqual(server["env"].get("CLAUDE_PROJECT_DIR"), project)
        self.assertEqual(server["env"].get("CONTEXT_MODE_PLATFORM"), "codex")

    def test_recipe_jcodemunch_step_copies_only_the_server_tables(self):
        # recipes/README.md "Focused jCodeMunch retrieval": the Codex step copies the rendered project template's
        # jcodemunch tables with the recipe's own sed range, and nothing else. The template's approval_policy,
        # sandbox_mode, [agents] and shell PATH would outrank the user config and its profiles in that directory
        # (codex-rs/config/src/config_layer_source.rs L33-51 at rust-v0.157.1). The server runs from the prefix
        # the recipe installs into.
        import tomllib  # Python 3.11+, as above

        section = (ROOT / "recipes" / "README.md").read_text(encoding="utf-8")
        section = section.split("\n## Focused jCodeMunch retrieval\n", 1)[1].split("\n## ", 1)[0]
        expression = re.search(r"sed -n '([^']+)' \\\n", section).group(1)
        text = string.Template((TEMPLATES / "project.codex.config.template.toml").read_text(encoding="utf-8"))
        rendered = text.substitute(FIXTURE_VALUES)
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "project.codex.config.toml"
            source.write_text(rendered, encoding="utf-8")
            copied = subprocess.run(["sed", "-n", expression, str(source)], capture_output=True, text=True,
                                    check=True).stdout
        full = tomllib.loads(rendered)
        self.assertIn("approval_policy", full)  # the control: the whole template carries more than the server
        self.assertEqual(tomllib.loads(copied), {"mcp_servers": {"jcodemunch": full["mcp_servers"]["jcodemunch"]}})
        self.assertEqual(full["mcp_servers"]["jcodemunch"]["command"],
                         FIXTURE_VALUES["ECO_ROOT"] + "/bin/jcodemunch-mcp")
        self.assertIn('UV_TOOL_BIN_DIR="$eco/bin"', section)
        self.assertIn('-- "$eco/bin/jcodemunch-mcp"', section)
        self.assertNotIn("codex mcp add jcodemunch --", section)  # the user-scope form is named, never copyable
        # Each copyable block that uses $eco defines it first, so either block works pasted on its own.
        for block in re.findall(r"```sh\n(.*?)```", section, flags=re.S):
            if "$eco" in block:
                self.assertTrue(block.startswith('eco="${ECO_INSTALL_ROOT:-$HOME/.local/share/codex-ecosystem}"\n'),
                                block[:80])

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


class AiMemoryBinTests(unittest.TestCase):
    """Token gap ai-memory#2 (2026-09-27): the Claude template's eight ai-memory hook commands named the
    Linux pin's install (tools/ai-memory-2.4.1) on every platform, while adoption/pins-macos-arm64.json
    installs 2.3.2. Upstream's native hook commands invoke the installed binary directly
    (akitaonrails/ai-memory v2.4.1 docs/install.md), so render_config.py now renders ${AI_MEMORY_BIN}
    from the selected platform's pin unless a host supplies the binary it actually runs."""

    SETTINGS = TEMPLATES / "claude.settings.template.json"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.hosts_dir = ROOT / "adoption" / "hosts"
        # A host value file without AI_MEMORY_BIN, as adoption/hosts/example.json is.
        self.host = "test-fixture-no-bin"
        values = {key: value for key, value in FIXTURE_VALUES.items() if key != "AI_MEMORY_BIN"}
        (self.hosts_dir / f"{self.host}.json").write_text(json.dumps(values, indent=2))
        self.addCleanup((self.hosts_dir / f"{self.host}.json").unlink, missing_ok=True)

    @staticmethod
    def pinned(platform_id: str) -> str:
        tools = json.loads((ROOT / "adoption" / f"pins-{platform_id}.json").read_text(encoding="utf-8"))["tools"]
        return next(tool["version"] for tool in tools if tool["id"] == "ai-memory")

    def memory_commands(self, settings_path: Path) -> list[str]:
        hooks = json.loads(settings_path.read_text())["hooks"]
        return [hook["command"] for groups in hooks.values() for group in groups for hook in group["hooks"]
                if " hook --event " in hook["command"]]

    def test_the_template_names_no_versioned_ai_memory_install(self):
        text = self.SETTINGS.read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"tools/ai-memory-[0-9]", text))
        self.assertEqual(text.count("${AI_MEMORY_BIN} --data-dir"), 8)

    def test_each_platform_renders_its_own_pinned_install(self):
        platforms = sorted(path.name[len("pins-"):-len(".json")] for path in (ROOT / "adoption").glob("pins-*.json"))
        self.assertLessEqual({"linux-x86_64", "macos-arm64"}, set(platforms))
        for platform_id in platforms:
            with self.subTest(platform=platform_id):
                out_dir = Path(self.tmp.name) / platform_id
                result = run("--host", self.host, "--platform", platform_id, "--out", str(out_dir))
                self.assertEqual(result.returncode, 0, result.stderr)
                expected = f"{FIXTURE_VALUES['ECO_ROOT']}/tools/ai-memory-{self.pinned(platform_id)}/ai-memory "
                commands = self.memory_commands(out_dir / "settings.json")
                self.assertEqual(len(commands), 8)
                for command in commands:
                    self.assertTrue(command.startswith(expected), command)

    def test_a_host_supplied_binary_wins_over_the_pin(self):
        out_dir = Path(self.tmp.name) / "override"
        result = run("--host", self.host, "--platform", "macos-arm64",
                     "--set", "AI_MEMORY_BIN=/opt/running/ai-memory", "--out", str(out_dir))
        self.assertEqual(result.returncode, 0, result.stderr)
        commands = self.memory_commands(out_dir / "settings.json")
        self.assertEqual(len(commands), 8)
        self.assertTrue(all(command.startswith("/opt/running/ai-memory --data-dir ") for command in commands))

    def test_a_platform_without_a_pins_file_fails_closed_unless_the_binary_is_given(self):
        out_dir = Path(self.tmp.name) / "unknown"
        result = run("--host", self.host, "--platform", "linux-aarch64", "--out", str(out_dir))
        self.assertEqual(result.returncode, 1)
        self.assertIn("no pins file for platform 'linux-aarch64'", result.stderr)
        self.assertFalse((out_dir / "settings.json").exists())
        given = run("--host", self.host, "--platform", "linux-aarch64",
                    "--set", "AI_MEMORY_BIN=/opt/running/ai-memory", "--out", str(out_dir))
        self.assertEqual(given.returncode, 0, given.stderr)
        # The platform names a file under adoption/, so anything but <os>-<arch> is refused.
        escape = run("--host", self.host, "--platform", "../hosts/example", "--out", str(out_dir) + "-escape")
        self.assertEqual(escape.returncode, 1)
        self.assertIn("--platform must look like", escape.stderr)


class SocratiCodeVersionTests(unittest.TestCase):
    """PR #446 review R1 (2026-09-28): the Codex user template named tools/socraticode-1.15.0 on every
    platform, while adoption/pins-macos-arm64.json keeps 1.14.0 and adoption/bootstrap-macos.sh installs
    tools/<id>-<version> from it, so a Mac render launched a file that does not exist. render_config.py now
    renders ${SOCRATICODE_VERSION} from the selected platform's pin unless a host supplies it."""

    CODEX = TEMPLATES / "codex.config.template.toml"
    DIST = "lib/node_modules/socraticode/dist/index.js"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.hosts_dir = ROOT / "adoption" / "hosts"
        # A host value file without either derived value, as adoption/hosts/example.json is.
        self.host = "test-fixture-no-socraticode-version"
        values = {key: value for key, value in FIXTURE_VALUES.items()
                  if key not in ("AI_MEMORY_BIN", "SOCRATICODE_VERSION")}
        (self.hosts_dir / f"{self.host}.json").write_text(json.dumps(values, indent=2))
        self.addCleanup((self.hosts_dir / f"{self.host}.json").unlink, missing_ok=True)

    @staticmethod
    def pinned(platform_id: str) -> str:
        tools = json.loads((ROOT / "adoption" / f"pins-{platform_id}.json").read_text(encoding="utf-8"))["tools"]
        return next(tool["version"] for tool in tools if tool["id"] == "socraticode")

    def socraticode_args(self, out_dir: Path) -> list[str]:
        import tomllib  # Python 3.11+, as the Codex wiring check already requires

        return tomllib.loads((out_dir / "codex.config.toml").read_text(encoding="utf-8"))[
            "mcp_servers"]["socraticode"]["args"]

    def test_the_template_names_no_versioned_socraticode_install(self):
        text = self.CODEX.read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"tools/socraticode-[0-9]", text))
        self.assertEqual(text.count("${ECO_ROOT}/tools/socraticode-${SOCRATICODE_VERSION}/" + self.DIST), 1)

    def test_each_platform_renders_its_own_pinned_install(self):
        # The two pins differ today (Linux 1.15.0, macOS 1.14.0), so one literal could not match both.
        self.assertNotEqual(self.pinned("linux-x86_64"), self.pinned("macos-arm64"))
        platforms = sorted(path.name[len("pins-"):-len(".json")] for path in (ROOT / "adoption").glob("pins-*.json"))
        self.assertLessEqual({"linux-x86_64", "macos-arm64"}, set(platforms))
        for platform_id in platforms:
            with self.subTest(platform=platform_id):
                out_dir = Path(self.tmp.name) / platform_id
                result = run("--host", self.host, "--platform", platform_id, "--out", str(out_dir))
                self.assertEqual(result.returncode, 0, result.stderr)
                expected = f"{FIXTURE_VALUES['ECO_ROOT']}/tools/socraticode-{self.pinned(platform_id)}/{self.DIST}"
                self.assertEqual(self.socraticode_args(out_dir), [expected])

    def test_a_host_supplied_version_wins_over_the_pin(self):
        out_dir = Path(self.tmp.name) / "override"
        result = run("--host", self.host, "--platform", "macos-arm64",
                     "--set", "SOCRATICODE_VERSION=9.9.9", "--out", str(out_dir))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.socraticode_args(out_dir),
                         [f"{FIXTURE_VALUES['ECO_ROOT']}/tools/socraticode-9.9.9/{self.DIST}"])

    def test_a_platform_without_a_pins_file_fails_closed_unless_the_version_is_given(self):
        out_dir = Path(self.tmp.name) / "unknown"
        result = run("--host", self.host, "--platform", "linux-aarch64",
                     "--set", "AI_MEMORY_BIN=/opt/running/ai-memory", "--out", str(out_dir))
        self.assertEqual(result.returncode, 1)
        self.assertIn("no pins file for platform 'linux-aarch64'", result.stderr)
        self.assertIn("--set SOCRATICODE_VERSION=", result.stderr)
        self.assertFalse((out_dir / "codex.config.toml").exists())
        given = run("--host", self.host, "--platform", "linux-aarch64", "--set", "AI_MEMORY_BIN=/opt/running/ai-memory",
                    "--set", "SOCRATICODE_VERSION=1.15.0", "--out", str(out_dir))
        self.assertEqual(given.returncode, 0, given.stderr)


class CodexModelTests(unittest.TestCase):
    """PR #542 cross-family review (2026-09-30): the Codex user template set model = "gpt-6.1-sol" on every
    platform, while adoption/pins-macos-arm64.json keeps Codex 0.155.1, whose bundled catalog has no GPT-6.1 entry
    (evidence/receipts/codex-01592-qualification-20260930.json, data.checks_after_the_constant_move
    .bundled_catalogs_offline; openai/codex rust-v0.159.1 release notes: "Added GPT-6.1 Sol as the default model in
    the bundled catalog"). render_config.py now renders ${CODEX_MODEL} from the selected platform's Codex pin unless
    a host supplies it, like ${SOCRATICODE_VERSION} (SocratiCodeVersionTests)."""

    CODEX = TEMPLATES / "codex.config.template.toml"
    # Today's two pins sit on either side of the rule: Linux 0.159.3, macOS 0.155.1.
    EXPECTED = {"linux-x86_64": "gpt-6.1-sol", "macos-arm64": "gpt-6-astra"}

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.hosts_dir = ROOT / "adoption" / "hosts"
        # A host value file without any derived value, as adoption/hosts/example.json is.
        self.host = "test-fixture-no-codex-model"
        values = {key: value for key, value in FIXTURE_VALUES.items()
                  if key not in ("AI_MEMORY_BIN", "SOCRATICODE_VERSION", "CODEX_MODEL")}
        (self.hosts_dir / f"{self.host}.json").write_text(json.dumps(values, indent=2))
        self.addCleanup((self.hosts_dir / f"{self.host}.json").unlink, missing_ok=True)

    @staticmethod
    def pinned(platform_id: str) -> str:
        tools = json.loads((ROOT / "adoption" / f"pins-{platform_id}.json").read_text(encoding="utf-8"))["tools"]
        return next(tool["version"] for tool in tools if tool["id"] == "codex")

    @staticmethod
    def renderer():
        spec = importlib.util.spec_from_file_location("render_config_under_test", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def models(self, out_dir: Path) -> tuple[str, str]:
        import tomllib  # Python 3.11+, as the Codex wiring check already requires

        config = tomllib.loads((out_dir / "codex.config.toml").read_text(encoding="utf-8"))
        return config["model"], config["agents"]["default_subagent_model"]

    def test_the_template_names_its_models_only_through_the_placeholder(self):
        text = self.CODEX.read_text(encoding="utf-8")
        self.assertEqual(re.findall(r'^(model|default_subagent_model) = "([^"]*)"$', text, flags=re.M),
                         [("model", "${CODEX_MODEL}"), ("default_subagent_model", "${CODEX_MODEL}")])

    def test_each_platform_renders_the_model_its_pinned_codex_lists(self):
        self.assertEqual((self.pinned("linux-x86_64"), self.pinned("macos-arm64")), ("0.159.3", "0.155.1"))
        for platform_id, model in self.EXPECTED.items():
            with self.subTest(platform=platform_id):
                out_dir = Path(self.tmp.name) / platform_id
                result = run("--host", self.host, "--platform", platform_id, "--out", str(out_dir))
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.models(out_dir), (model, model))

    def test_gpt_6_1_sol_starts_at_codex_0_159_1(self):
        # openai/codex codex-rs/models-manager/models.json has no "gpt-6.1-sol" slug at rust-v0.159.0 (687a119f) and
        # one at rust-v0.159.1 (8e68a98e, line 178), the release whose notes add it.
        renderer = self.renderer()
        for version, model in (("0.155.1", "gpt-6-astra"), ("0.157.1", "gpt-6-astra"), ("0.159.0", "gpt-6-astra"),
                               ("0.159.1", "gpt-6.1-sol"), ("0.159.2", "gpt-6.1-sol"), ("0.160.0", "gpt-6.1-sol"),
                               ("1.0.0", "gpt-6.1-sol")):
            with self.subTest(version=version):
                self.assertEqual(renderer.codex_model_for(version), model)
        # Anything but a plain release version is refused rather than guessed.
        for version in ("0.159", "0.159.1-alpha.1", "v0.159.1", ""):
            with self.subTest(version=version):
                with self.assertRaises(renderer.RenderError) as refused:
                    renderer.codex_model_for(version)
                self.assertIn("--set CODEX_MODEL=", str(refused.exception))

    def test_a_host_supplied_model_wins_over_the_pin(self):
        out_dir = Path(self.tmp.name) / "override"
        result = run("--host", self.host, "--platform", "macos-arm64", "--set", "CODEX_MODEL=gpt-6-sol",
                     "--out", str(out_dir))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.models(out_dir), ("gpt-6-sol", "gpt-6-sol"))
        self.assertNotIn("CODEX_MODEL", result.stdout)  # nothing was derived, so nothing is explained

    def test_a_platform_without_a_pins_file_fails_closed_unless_the_model_is_given(self):
        out_dir = Path(self.tmp.name) / "unknown"
        others = ("--set", "AI_MEMORY_BIN=/opt/running/ai-memory", "--set", "SOCRATICODE_VERSION=1.15.0")
        result = run("--host", self.host, "--platform", "linux-aarch64", *others, "--out", str(out_dir))
        self.assertEqual(result.returncode, 1)
        self.assertIn("no pins file for platform 'linux-aarch64'", result.stderr)
        self.assertIn("--set CODEX_MODEL=", result.stderr)
        self.assertFalse((out_dir / "codex.config.toml").exists())
        given = run("--host", self.host, "--platform", "linux-aarch64", *others, "--set", "CODEX_MODEL=gpt-6-astra",
                    "--out", str(out_dir))
        self.assertEqual(given.returncode, 0, given.stderr)
        self.assertEqual(self.models(out_dir), ("gpt-6-astra", "gpt-6-astra"))

    def test_out_and_check_name_the_derived_model_its_pin_and_the_rules_sources(self):
        for platform_id, model in self.EXPECTED.items():
            with self.subTest(platform=platform_id):
                out_dir = Path(self.tmp.name) / f"check-{platform_id}"
                written = run("--host", self.host, "--platform", platform_id, "--out", str(out_dir))
                self.assertEqual(written.returncode, 0, written.stderr)
                checked = run("--host", self.host, "--platform", platform_id, "--check",
                              "--live-settings", str(out_dir / "settings.json"),
                              "--live-codex-user", str(out_dir / "codex.config.toml"),
                              "--live-codex-project", str(out_dir / "project.codex.config.toml"))
                self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
                self.assertIn("codex.config.toml: byte-identical", checked.stdout)
                for result in (written, checked):
                    notes = [line for line in result.stdout.splitlines() if line.startswith("derived CODEX_MODEL: ")]
                    self.assertEqual(len(notes), 1, result.stdout)
                    note = notes[0]
                    self.assertTrue(note.startswith(f"derived CODEX_MODEL: {model} "), note)
                    self.assertIn(f"adoption/pins-{platform_id}.json pins codex {self.pinned(platform_id)}", note)
                    self.assertIn("0.159.1", note)
                    self.assertIn("rust-v0.159.1", note)
                    self.assertIn("evidence/receipts/codex-01592-qualification-20260930.json", note)


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
