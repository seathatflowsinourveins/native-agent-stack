"""Unit tests for tools/adoption/install_claude_profile.py's guard/agents
steps (sha256-checked, idempotent) and the MCP registration matcher used to
decide whether an existing `claude mcp get` entry already matches the
template (so registration is skipped rather than repeated). The `claude`
binary itself is never invoked here; MCP idempotency is tested against
`existing_config_matches` directly with recorded-shape text fixtures, and the
placeholder rendering and `claude mcp add` argument order are tested as data.
"""

import io
import json
import string
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "adoption"))

import install_claude_profile as icp  # noqa: E402


class GuardInstallTests(unittest.TestCase):
    def test_installs_when_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            status = icp.install_guard(home, dry_run=False)
            self.assertEqual(status, "installed")
            dest = home / ".claude" / "hooks" / "effort-default-guard.py"
            self.assertTrue(dest.is_file())
            self.assertEqual(icp.sha256_of(dest), icp.expected_guard_sha256())

    def test_skips_when_already_matching(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            icp.install_guard(home, dry_run=False)
            status = icp.install_guard(home, dry_run=False)
            self.assertEqual(status, "skipped")

    def test_dry_run_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            status = icp.install_guard(home, dry_run=True)
            self.assertEqual(status, "planned")
            self.assertFalse((home / ".claude" / "hooks" / "effort-default-guard.py").exists())


class SecretGuardProfileTests(unittest.TestCase):
    """The secret-path guard and its deny rules ship in the user profile for every new host."""

    TEMPLATE = ROOT / "adoption" / "templates" / "claude.settings.template.json"

    def test_install_guards_installs_both_hooks_pinned_by_sha256sums(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            results = icp.install_guards(home, dry_run=False)
            self.assertEqual(results, {"effort-default-guard.py": "installed", "secret_path_guard.py": "installed"})
            dest = home / ".claude" / "hooks" / "secret_path_guard.py"
            self.assertEqual(dest.read_bytes(), icp.SECRET_GUARD_SRC.read_bytes())
            self.assertEqual(icp.install_guards(home, dry_run=False),
                             {"effort-default-guard.py": "skipped", "secret_path_guard.py": "skipped"})

    def test_sha256sums_verifies_like_sha256sum_c(self):
        entries = icp.sha256sums_entries()
        self.assertEqual(set(entries), {src.resolve() for src in icp.HOOKS.values()})
        for source, digest in entries.items():
            with self.subTest(source=source.name):
                self.assertEqual(icp.sha256_of(source), digest)

    def test_modified_hook_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(icp, "expected_sha256", return_value="0" * 64):
                with self.assertRaises(icp.InstallError):
                    icp.install_guards(Path(tmp), dry_run=False)
            self.assertFalse((Path(tmp) / ".claude").exists())

    def test_template_carries_project_deny_rules_and_the_guard_hook(self):
        template = json.loads(self.TEMPLATE.read_text())
        project = json.loads((ROOT / ".claude" / "settings.json").read_text())
        deny = template["permissions"]["deny"]
        for rule in project["permissions"]["deny"]:
            self.assertIn(rule, deny)
        self.assertIn("Agent(codex:codex-rescue)", deny)
        bash_groups = [g for g in template["hooks"]["PreToolUse"] if g.get("matcher") == "Bash"]
        commands = [h["command"] for g in bash_groups for h in g["hooks"]]
        self.assertTrue(any("secret_path_guard.py" in c for c in commands))

    def rendered_hook(self, home: Path) -> str:
        text = string.Template(self.TEMPLATE.read_text()).safe_substitute(HOME=str(home))
        for group in json.loads(text)["hooks"]["PreToolUse"]:
            for hook in group["hooks"]:
                if "secret_path_guard.py" in hook["command"]:
                    return hook["command"]
        self.fail("no secret guard hook in the template")

    def run_rendered(self, command: str, bash_command: str) -> subprocess.CompletedProcess:
        payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": bash_command}})
        return subprocess.run(["sh", "-c", command], input=payload, capture_output=True, text=True, timeout=30)

    def test_rendered_hook_blocks_after_install_and_is_inert_before(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            command = self.rendered_hook(home)
            missing = self.run_rendered(command, "cat \"$PAPER_ENV_FILE\"")
            self.assertEqual(missing.returncode, 0, "no installed guard must not block every Bash call")
            icp.install_guards(home, dry_run=False)
            blocked = self.run_rendered(command, "cat \"$PAPER_ENV_FILE\"")
            self.assertEqual(blocked.returncode, 2)
            self.assertIn("credential_file_read", blocked.stderr)
            allowed = self.run_rendered(command, "git status")
            self.assertEqual((allowed.returncode, allowed.stderr), (0, ""))

    def test_apply_merge_keeps_host_rules_and_adds_the_guard(self):
        import apply_claude_settings as acs
        with tempfile.TemporaryDirectory() as tmp:
            template = json.loads(string.Template(self.TEMPLATE.read_text()).safe_substitute(HOME=tmp))
        base = {"permissions": {"deny": ["Bash(rm -rf /)"]},
                "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "rtk hook claude"}]}]}}
        merged = acs.merge_settings(base, template)
        self.assertEqual(merged["permissions"]["deny"][0], "Bash(rm -rf /)")
        self.assertIn("Read(~/.config/native-agent-stack/**)", merged["permissions"]["deny"])
        commands = [h["command"] for h in merged["hooks"]["PreToolUse"][0]["hooks"]]
        self.assertEqual(commands.count("rtk hook claude"), 1)
        self.assertTrue(any("secret_path_guard.py" in c for c in commands))


class AgentsInstallTests(unittest.TestCase):
    def test_installs_every_adoption_agent(self):
        # Seven since 2026-09-23: the blind layer-verdict roles (blind-lane-reviewer, blind-adjudicator) joined.
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            results = icp.install_agents(home, dry_run=False)
            self.assertEqual(len(results), len(list(icp.AGENTS_SRC_DIR.glob("*.md"))))
            self.assertEqual(len(results), 7)
            dest_dir = home / ".claude" / "agents"
            installed = sorted(p.name for p in dest_dir.glob("*.md"))
            expected = sorted(p.name for p in icp.AGENTS_SRC_DIR.glob("*.md"))
            self.assertEqual(installed, expected)
            for name in installed:
                self.assertEqual((dest_dir / name).read_bytes(), (icp.AGENTS_SRC_DIR / name).read_bytes())

    def test_second_run_skips_unchanged_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            icp.install_agents(home, dry_run=False)
            results = icp.install_agents(home, dry_run=False)
            self.assertTrue(all(r == "skipped" for r in results))


class ShippedAgentEffortTests(unittest.TestCase):
    """Every shipped agent runs at effort max beside its task-matched model
    (docs/decisions/2026-09-23-max-effort-default.md): an agent's frontmatter effort
    is what a stage without its own effort runs at, and a second, lower effort line
    must not hide behind the first."""

    @staticmethod
    def frontmatter(path: Path) -> list[str]:
        lines = path.read_text(encoding="utf-8").splitlines()
        if not lines or lines[0] != "---" or "---" not in lines[1:]:
            return []
        return lines[1:lines.index("---", 1)]

    def test_each_shipped_agent_has_exactly_one_effort_max_line(self):
        agents = sorted(icp.AGENTS_SRC_DIR.glob("*.md"))
        self.assertTrue(agents)
        for path in agents:
            with self.subTest(agent=path.name):
                effort_lines = [line for line in self.frontmatter(path) if line.startswith("effort:")]
                self.assertEqual(effort_lines, ["effort: max"])

    def test_the_check_rejects_a_lower_or_repeated_effort(self):
        with tempfile.TemporaryDirectory() as tmp:
            for body in ("---\nname: a\nmodel: opus\neffort: high\n---\nx\n",
                         "---\nname: a\nmodel: opus\neffort: max\neffort: high\n---\nx\n",
                         "---\nname: a\nmodel: opus\n---\neffort: max\n"):
                path = Path(tmp) / "a.md"
                path.write_text(body, encoding="utf-8")
                with self.subTest(body=body):
                    effort_lines = [line for line in self.frontmatter(path) if line.startswith("effort:")]
                    self.assertNotEqual(effort_lines, ["effort: max"])


class McpMatchTests(unittest.TestCase):
    def test_http_server_matches_on_url_and_type(self):
        existing = "ai-memory:\n  Type: http\n  URL: http://127.0.0.1:49374/mcp\n"
        self.assertTrue(icp.existing_config_matches(existing, "http", "http://127.0.0.1:49374/mcp", [], {}))

    def test_http_server_does_not_match_a_different_url(self):
        existing = "ai-memory:\n  Type: http\n  URL: http://127.0.0.1:9999/mcp\n"
        self.assertFalse(icp.existing_config_matches(existing, "http", "http://127.0.0.1:49374/mcp", [], {}))

    def test_stdio_server_matches_command_args_and_env_names(self):
        existing = (
            "serena:\n  Type: stdio\n"
            "  Command: /home/example/.local/share/codex-ecosystem/bin/serena-context\n"
            "  Args: start-mcp-server --transport stdio --project-from-cwd\n"
        )
        self.assertTrue(icp.existing_config_matches(
            existing, "stdio", "/home/example/.local/share/codex-ecosystem/bin/serena-context",
            ["start-mcp-server", "--transport", "stdio", "--project-from-cwd"], {}))

    def test_stdio_server_checks_env_var_names_present(self):
        existing = (
            "jcodemunch:\n  Type: stdio\n"
            "  Command: /home/example/.local/share/codex-ecosystem/bin/jcodemunch-mcp\n"
            "  Environment:\n    CODE_INDEX_PATH=/home/example/.code-index\n    JCODEMUNCH_SHARE_SAVINGS=0\n"
        )
        self.assertTrue(icp.existing_config_matches(
            existing, "stdio", "/home/example/.local/share/codex-ecosystem/bin/jcodemunch-mcp", [],
            {"CODE_INDEX_PATH": "/home/example/.code-index", "JCODEMUNCH_SHARE_SAVINGS": "0"}))

    def test_stdio_server_does_not_match_missing_env_var(self):
        existing = (
            "jcodemunch:\n  Type: stdio\n"
            "  Command: /home/example/.local/share/codex-ecosystem/bin/jcodemunch-mcp\n"
            "  Environment:\n    CODE_INDEX_PATH=/home/example/.code-index\n"
        )
        self.assertFalse(icp.existing_config_matches(
            existing, "stdio", "/home/example/.local/share/codex-ecosystem/bin/jcodemunch-mcp", [],
            {"CODE_INDEX_PATH": "/home/example/.code-index", "JCODEMUNCH_SHARE_SAVINGS": "0"}))

    def test_stdio_type_mismatch_against_http_entry(self):
        existing = "ai-memory:\n  Type: http\n  URL: http://127.0.0.1:49374/mcp\n"
        self.assertFalse(icp.existing_config_matches(existing, "stdio", "some-command", [], {}))


class McpTemplateShapeTests(unittest.TestCase):
    def test_template_names_the_three_expected_servers(self):
        import json
        data = json.loads(icp.MCP_TEMPLATE.read_text())
        self.assertEqual(set(data["mcpServers"].keys()), {"ai-memory", "jcodemunch", "serena"})
        self.assertEqual(data["mcpServers"]["ai-memory"]["type"], "http")
        self.assertEqual(data["mcpServers"]["jcodemunch"]["env"]["JCODEMUNCH_SHARE_SAVINGS"], "0")
        self.assertIn("--project-from-cwd", data["mcpServers"]["serena"]["args"])


class McpRenderAndCommandTests(unittest.TestCase):
    def test_placeholders_are_rendered_for_the_target_host(self):
        servers = icp.render_servers(json.loads(icp.MCP_TEMPLATE.read_text()),
                                     Path("/home/example"), Path("/opt/eco"))
        self.assertEqual(servers["jcodemunch"]["command"], "/opt/eco/bin/jcodemunch-mcp")
        self.assertEqual(servers["jcodemunch"]["env"]["CODE_INDEX_PATH"], "/home/example/.code-index")
        self.assertEqual(servers["serena"]["command"], "/opt/eco/bin/serena-context")
        self.assertNotIn("${", json.dumps(servers))

    def test_unknown_placeholder_fails(self):
        with self.assertRaises(icp.InstallError):
            icp.render_servers({"mcpServers": {"x": {"command": "${NOPE}/bin/x"}}}, Path("/h"), Path("/e"))

    def test_name_precedes_env_and_command_follows_double_dash(self):
        cmd = icp.mcp_add_command("claude", "jcodemunch", {
            "type": "stdio", "command": "/e/bin/jcodemunch-mcp", "args": ["--flag"],
            "env": {"CODE_INDEX_PATH": "/h/.code-index"}})
        self.assertEqual(cmd, ["claude", "mcp", "add", "--scope", "user", "jcodemunch",
                               "-e", "CODE_INDEX_PATH=/h/.code-index", "--", "/e/bin/jcodemunch-mcp", "--flag"])

    def test_http_command(self):
        cmd = icp.mcp_add_command("claude", "ai-memory", {"type": "http", "url": "http://127.0.0.1:49374/mcp"})
        self.assertEqual(cmd, ["claude", "mcp", "add", "--scope", "user", "--transport", "http",
                               "ai-memory", "http://127.0.0.1:49374/mcp"])

    def test_differing_registration_is_left_unchanged_without_replace(self):
        calls = []
        with mock.patch.object(icp, "claude_mcp_get", return_value="x:\n  Scope: User config\n  Type: stdio\n  Command: /other\n"), \
             mock.patch.object(icp.subprocess, "run", side_effect=lambda *a, **k: calls.append(a[0])):
            results = icp.install_mcp_servers("claude", False, Path("/h"), Path("/e"))
        self.assertEqual(results, ["differs", "differs", "differs"])
        self.assertEqual(calls, [])


class McpGetOutputTests(unittest.TestCase):
    # Recorded from `claude mcp get` (claude 2.1.280, 2026-09-23) with the home path replaced.
    SERENA = (
        "serena:\n  Scope: User config (available in all your projects)\n  Status: \u2714 Connected\n"
        "  Type: stdio\n  Command: /home/example/.local/share/codex-ecosystem/bin/serena-context\n"
        "  Args: start-mcp-server --transport stdio --project-from-cwd --context claude-code "
        "--enable-web-dashboard true --open-web-dashboard false --enable-gui-log-window false\n"
        "  Environment:\n\nTo remove this server, run: claude mcp remove serena -s user\n"
    )
    JCODEMUNCH = (
        "jcodemunch:\n  Scope: User config (available in all your projects)\n  Status: \u2714 Connected\n"
        "  Type: stdio\n  Command: /home/example/.local/share/codex-ecosystem/bin/jcodemunch-mcp\n  Args:\n"
        "  Environment:\n    CODE_INDEX_PATH=/home/example/.code-index\n    JCODEMUNCH_SHARE_SAVINGS=0\n"
        "\nTo remove this server, run: claude mcp remove jcodemunch -s user\n"
    )
    AI_MEMORY = (
        "ai-memory:\n  Scope: User config (available in all your projects)\n  Status: \u2714 Connected\n"
        "  Type: http\n  URL: http://127.0.0.1:49374/mcp\n\nTo remove this server, run: claude mcp remove ai-memory -s user\n"
    )

    def rendered(self):
        return icp.render_servers(json.loads(icp.MCP_TEMPLATE.read_text()),
                                  Path("/home/example"), Path("/home/example/.local/share/codex-ecosystem"))

    def matches(self, text, spec):
        kind = spec.get("type", "stdio")
        return icp.existing_config_matches(text, kind, spec["url"] if kind == "http" else spec["command"],
                                           spec.get("args", []), spec.get("env", {}))

    def test_recorded_outputs_match_the_rendered_template(self):
        servers = self.rendered()
        self.assertTrue(self.matches(self.SERENA, servers["serena"]))
        self.assertTrue(self.matches(self.JCODEMUNCH, servers["jcodemunch"]))
        self.assertTrue(self.matches(self.AI_MEMORY, servers["ai-memory"]))

    def test_reordered_or_extra_args_do_not_match(self):
        spec = dict(self.rendered()["serena"])
        reordered = self.SERENA.replace("--transport stdio --project-from-cwd", "--project-from-cwd --transport stdio")
        extra = self.SERENA.replace("--enable-gui-log-window false", "--enable-gui-log-window false --verbose")
        self.assertFalse(self.matches(reordered, spec))
        self.assertFalse(self.matches(extra, spec))

    def test_header_lines_do_not_override_fields(self):
        text = self.AI_MEMORY.replace("  URL: http://127.0.0.1:49374/mcp\n",
                                      "  URL: http://127.0.0.1:49374/mcp\n  Headers:\n    URL: http://evil.invalid/\n")
        self.assertEqual(icp.parse_mcp_get(text)["url"], "http://127.0.0.1:49374/mcp")

    def test_a_non_user_scope_server_is_left_alone(self):
        managed = self.AI_MEMORY.replace("User config (available in all your projects)", "Managed config")
        with mock.patch.object(icp, "claude_mcp_get", return_value=managed), \
             mock.patch.object(icp.subprocess, "run") as run:
            results = icp.install_mcp_servers("claude", False, Path("/home/example"), Path("/e"), replace=True)
        self.assertEqual(results, ["other-scope"] * 3)
        run.assert_not_called()

    def test_missing_claude_binary_is_a_clean_failure(self):
        with mock.patch("sys.stderr", new_callable=io.StringIO) as err:
            code = icp.main(["--only", "mcp", "--claude-bin", "/nonexistent/claude", "--home", "/home/example"])
        self.assertEqual(code, 1)
        self.assertIn("pass --claude-bin", err.getvalue())

    def test_get_runs_outside_any_project(self):
        seen = {}

        def fake_run(cmd, **kwargs):
            seen["cwd"] = kwargs.get("cwd")
            return mock.Mock(returncode=1, stdout="")
        with mock.patch.object(icp.subprocess, "run", side_effect=fake_run):
            self.assertIsNone(icp.claude_mcp_get("claude", "serena"))
        self.assertIsNotNone(seen["cwd"])
        self.assertNotEqual(Path(seen["cwd"]).resolve(), Path.cwd().resolve())

    def test_dry_run_with_replace_shows_the_remove(self):
        with mock.patch.object(icp, "claude_mcp_get", return_value="x:\n  Scope: User config\n  Type: stdio\n  Command: /other\n"), \
             mock.patch("sys.stdout", new_callable=io.StringIO) as out:
            icp.install_mcp_servers("claude", True, Path("/home/example"), Path("/e"), replace=True)
        self.assertIn("mcp remove serena -s user", out.getvalue())

    def test_default_eco_root_follows_home(self):
        with mock.patch.dict(icp.os.environ, {}, clear=False):
            icp.os.environ.pop("ECO_INSTALL_ROOT", None)
            self.assertEqual(icp.default_eco_root(Path("/home/example")),
                             Path("/home/example/.local/share/codex-ecosystem"))


if __name__ == "__main__":
    unittest.main()
