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

# The jcodemunch entry adoption/mcp/claude-user.json carried until 2026-09-25, when jCodeMunch moved
# to a per-project opt-in (adoption/bootstrap.md step 4a). It stays here, inline, as the fixture for
# a stdio server with ${HOME} in an env value and env names to match: no template entry has either now.
JCODEMUNCH_SPEC = {
    "type": "stdio",
    "command": "${ECO_ROOT}/bin/jcodemunch-mcp",
    "args": [],
    "env": {"CODE_INDEX_PATH": "${HOME}/.code-index", "JCODEMUNCH_SHARE_SAVINGS": "0"},
}


def template_server_names() -> list[str]:
    return list(json.loads(icp.MCP_TEMPLATE.read_text())["mcpServers"])


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


class ShippedAgentFrontmatterTests(unittest.TestCase):
    """Every shipped agent's frontmatter parses as a YAML mapping, uses only documented subagent
    fields with documented types and values, and names an explicit model beside its effort (the
    repository rule: effort max with an explicit model).

    Source: the "Frontmatter reference" table and "Subagent files Claude Code skips" section of
    https://code.claude.com/docs/en/sub-agents, read 2026-09-26 against Claude Code 2.1.283. Claude
    Code ignores a field it does not recognize without an error and skips a user or project agent
    whose YAML does not parse, while `claude plugin validate --strict` 2.1.283 passed an agents
    directory holding an unknown field and unparseable YAML (evidence/artifacts/
    skills-agents-layer-20260926), so a misspelled key such as ``omitClaudeMD`` would silently drop
    its setting and a broken value would silently drop the agent; these are the checks that see it.
    The text reader runs everywhere; the YAML checks skip where PyYAML is absent, as the
    repository's other YAML checks do (the Linux validate job has it). A field added to the docs
    later belongs in DOCUMENTED_FIELDS, and in the type table below, before an agent uses it.
    """

    DOCUMENTED_FIELDS = frozenset({
        "name", "description", "tools", "disallowedTools", "model", "permissionMode", "maxTurns",
        "skills", "mcpServers", "hooks", "memory", "background", "omitClaudeMd", "effort",
        "isolation", "color", "initialPrompt", "experimental"})
    MODEL_ALIASES = frozenset({"sonnet", "opus", "haiku", "fable"})
    ENUMS = {
        "permissionMode": {"default", "acceptEdits", "auto", "dontAsk", "bypassPermissions", "plan", "manual"},
        "memory": {"user", "project", "local"},
        "effort": {"low", "medium", "high", "xhigh", "max"},
        "isolation": {"worktree"},
        "color": {"red", "blue", "green", "yellow", "purple", "orange", "pink", "cyan"},
        "background": {"true", "false"},
        "omitClaudeMd": {"true", "false"},
    }
    # Types by the docs table and its examples: strings; `tools` and `disallowedTools` as a
    # comma-separated string or a list; `skills` as a list of names; `mcpServers` as a list of server
    # names or one-key inline definitions; `hooks` and `experimental` as maps; `maxTurns` as a
    # positive integer; `background` and `omitClaudeMd` as booleans.
    STRING_FIELDS = frozenset({"name", "description", "model", "permissionMode", "memory", "effort",
                               "isolation", "color", "initialPrompt"})

    @staticmethod
    def yaml_frontmatter(path: Path, yaml):
        """(mapping or other parsed value, None) or (None, reason) for the text between the markers."""
        lines = path.read_text(encoding="utf-8").splitlines()
        if not lines or lines[0] != "---" or "---" not in lines[1:]:
            return None, "no frontmatter between --- markers on the first lines"
        try:
            return yaml.safe_load("\n".join(lines[1:lines.index("---", 1)])), None
        except yaml.YAMLError as error:
            return None, f"frontmatter does not parse as YAML ({type(error).__name__})"

    def yaml_problems(self, path: Path, yaml) -> list[str]:
        data, reason = self.yaml_frontmatter(path, yaml)
        if reason:
            return [reason]
        if not isinstance(data, dict):
            return [f"frontmatter parses to {type(data).__name__}, not a mapping"]

        def strings(value):
            return isinstance(value, list) and all(isinstance(item, str) for item in value)

        valid = {
            "tools": lambda v: isinstance(v, str) or strings(v),
            "disallowedTools": lambda v: isinstance(v, str) or strings(v),
            "skills": strings,
            "mcpServers": lambda v: isinstance(v, list) and all(
                isinstance(item, str) or (isinstance(item, dict) and len(item) == 1) for item in v),
            "hooks": lambda v: isinstance(v, dict),
            "experimental": lambda v: isinstance(v, dict),
            "maxTurns": lambda v: isinstance(v, int) and not isinstance(v, bool) and v > 0,
            "background": lambda v: isinstance(v, bool),
            "omitClaudeMd": lambda v: isinstance(v, bool),
            **{key: (lambda v: isinstance(v, str)) for key in self.STRING_FIELDS},
        }
        found = [f"{key} has the undocumented type {type(value).__name__}"
                 for key, value in data.items() if key in valid and not valid[key](value)]
        if set(data) != set(self.top_level_fields(path)):
            found.append("the YAML keys and the text reader's keys differ")
        return found

    @staticmethod
    def top_level_fields(path: Path) -> dict[str, str]:
        """Column-0 ``key: value`` lines of the frontmatter (list items and nested maps are
        indented and belong to the key above them)."""
        lines = path.read_text(encoding="utf-8").splitlines()
        if not lines or lines[0] != "---" or "---" not in lines[1:]:
            return {}
        fields: dict[str, str] = {}
        for line in lines[1:lines.index("---", 1)]:
            if line[:1].isalpha():
                key, _, value = line.partition(":")
                fields[key.strip()] = value.strip()
        return fields

    def problems(self, path: Path) -> list[str]:
        fields = self.top_level_fields(path)
        found = [f"undocumented field {key!r}" for key in sorted(set(fields) - self.DOCUMENTED_FIELDS)]
        for key in ("name", "description", "model"):
            if not fields.get(key):
                found.append(f"missing {key}")
        name = fields.get("name", "")
        if ":" in name or name.startswith("-"):
            found.append("name must not contain ':' or start with '-'")
        model = fields.get("model", "")
        if model and model not in self.MODEL_ALIASES and not model.startswith("claude-"):
            found.append(f"model {model!r} is neither an alias nor a full model ID (inherit is not explicit)")
        for key, allowed in self.ENUMS.items():
            if key in fields and fields[key] not in allowed:
                found.append(f"{key} value {fields[key]!r} is not documented")
        if "maxTurns" in fields and not (fields["maxTurns"].isdigit() and int(fields["maxTurns"]) > 0):
            found.append("maxTurns must be a positive integer")
        return found

    def test_each_shipped_agent_uses_documented_fields_and_an_explicit_model(self):
        agents = sorted(icp.AGENTS_SRC_DIR.glob("*.md"))
        self.assertTrue(agents)
        for path in agents:
            with self.subTest(agent=path.name):
                self.assertEqual(self.problems(path), [])
                self.assertEqual(self.top_level_fields(path)["name"], path.stem)

    def test_the_check_rejects_a_misspelled_field_an_inherited_model_and_a_bad_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            for body in ("---\nname: a\ndescription: d\nmodel: opus\neffort: max\nomitClaudeMD: true\n---\nx\n",
                         "---\nname: a\ndescription: d\nmodel: inherit\neffort: max\n---\nx\n",
                         "---\nname: a\ndescription: d\neffort: max\n---\nx\n",
                         "---\nname: a\ndescription: d\nmodel: opus\neffort: max\ncolor: magenta\n---\nx\n",
                         "---\nname: a:b\ndescription: d\nmodel: opus\neffort: max\n---\nx\n"):
                path = Path(tmp) / "a.md"
                path.write_text(body, encoding="utf-8")
                with self.subTest(body=body):
                    self.assertNotEqual(self.problems(path), [])

    def test_each_shipped_agent_parses_as_a_yaml_mapping_with_documented_types(self):
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not installed; the text reader alone checked the frontmatter")
        agents = sorted(icp.AGENTS_SRC_DIR.glob("*.md"))
        self.assertTrue(agents)
        for path in agents:
            with self.subTest(agent=path.name):
                self.assertEqual(self.yaml_problems(path, yaml), [])

    def test_the_yaml_check_rejects_unparseable_yaml_a_non_mapping_and_wrong_types(self):
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not installed; the text reader alone checked the frontmatter")
        head = "---\nname: a\ndescription: d\nmodel: opus\neffort: max\n"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.md"
            # A positive control first: every documented shape, lists and maps included, passes both checks.
            path.write_text(head + "tools:\n  - Read\n  - Grep\nskills:\n  - s\nmcpServers:\n  - github\n"
                            "  - local:\n      type: stdio\n      command: c\nhooks:\n  PreToolUse: []\n"
                            "experimental:\n  cacheTtl: 1h\nmaxTurns: 5\nomitClaudeMd: true\n---\nx\n", encoding="utf-8")
            self.assertEqual(self.problems(path), [])
            self.assertEqual(self.yaml_problems(path, yaml), [])
            # Each fails the YAML check; all but the list-shaped one pass the text reader alone, which
            # is the gap the YAML check closes (a quoted key is invisible to the text reader).
            for body, text_reader_passes in (
                    ("---\nname: a\ndescription: [unclosed\nmodel: opus\neffort: max\n---\nx\n", True),
                    ("---\n- name: a\n---\nx\n", False),
                    (head + "tools: {Read: true}\n---\nx\n", True),
                    (head + "skills: [1, 2]\n---\nx\n", True),
                    (head + "mcpServers: github\n---\nx\n", True),
                    (head + "hooks: [PreToolUse]\n---\nx\n", True),
                    (head + "\"omitClaudeMD\": true\n---\nx\n", True)):
                path.write_text(body, encoding="utf-8")
                with self.subTest(body=body):
                    self.assertNotEqual(self.yaml_problems(path, yaml), [])
                    self.assertEqual(self.problems(path) == [], text_reader_passes)


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
            "  Command: /home/example/.local/share/codex-ecosystem/bin/serena\n"
            "  Args: start-mcp-server --transport stdio --project-from-cwd\n"
        )
        self.assertTrue(icp.existing_config_matches(
            existing, "stdio", "/home/example/.local/share/codex-ecosystem/bin/serena",
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
    def test_template_names_the_two_expected_servers(self):
        # jcodemunch left the user-scope template on 2026-09-25 for a per-project opt-in.
        data = json.loads(icp.MCP_TEMPLATE.read_text())
        self.assertEqual(set(data["mcpServers"].keys()), {"ai-memory", "serena"})
        self.assertEqual(data["mcpServers"]["ai-memory"]["type"], "http")
        self.assertEqual(data["mcpServers"]["serena"]["type"], "stdio")
        self.assertIn("--project-from-cwd", data["mcpServers"]["serena"]["args"])

    def test_the_jcodemunch_opt_in_snippets_keep_savings_sharing_off(self):
        # The template no longer carries JCODEMUNCH_SHARE_SAVINGS=0, so the two documented opt-in
        # forms in adoption/bootstrap.md step 4a are where it ships: the local command and the
        # checked-in .mcp.json entry must both keep it.
        text = (ROOT / "adoption" / "bootstrap.md").read_text()
        start = text.index("**jCodeMunch, per project.**")
        paragraph = text[start:text.index("Then apply the settings template itself", start)]
        self.assertIn("-e JCODEMUNCH_SHARE_SAVINGS=0", paragraph)
        self.assertIn('"JCODEMUNCH_SHARE_SAVINGS": "0"', paragraph)
        self.assertEqual(paragraph.count("JCODEMUNCH_SHARE_SAVINGS"), 2)


class McpRenderAndCommandTests(unittest.TestCase):
    def test_placeholders_are_rendered_for_the_target_host(self):
        servers = icp.render_servers(json.loads(icp.MCP_TEMPLATE.read_text()),
                                     Path("/home/example"), Path("/opt/eco"))
        self.assertEqual(servers["serena"]["command"], "/opt/eco/bin/serena")
        self.assertNotIn("${", json.dumps(servers))

    def test_home_and_eco_root_are_rendered_in_command_and_env_values(self):
        servers = icp.render_servers({"mcpServers": {"jcodemunch": JCODEMUNCH_SPEC}},
                                     Path("/home/example"), Path("/opt/eco"))
        self.assertEqual(servers["jcodemunch"]["command"], "/opt/eco/bin/jcodemunch-mcp")
        self.assertEqual(servers["jcodemunch"]["env"],
                         {"CODE_INDEX_PATH": "/home/example/.code-index", "JCODEMUNCH_SHARE_SAVINGS": "0"})
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
        self.assertEqual(results, ["differs"] * len(template_server_names()))
        self.assertEqual(calls, [])

    def test_registers_only_the_servers_the_template_names(self):
        # A jcodemunch registration left by an earlier template is neither re-added nor removed.
        asked, ran = [], []

        def fake_get(claude_bin, name):
            asked.append(name)
            return None

        def fake_run(cmd, **kwargs):
            ran.append(cmd)
            return mock.Mock(returncode=0, stdout="", stderr="")
        with mock.patch.object(icp, "claude_mcp_get", side_effect=fake_get), \
             mock.patch.object(icp.subprocess, "run", side_effect=fake_run):
            results = icp.install_mcp_servers("claude", False, Path("/home/example"), Path("/e"))
        names = template_server_names()
        rendered = icp.render_servers(json.loads(icp.MCP_TEMPLATE.read_text()), Path("/home/example"), Path("/e"))
        self.assertEqual(asked, names)
        self.assertEqual(results, ["installed"] * len(names))
        self.assertEqual(ran, [icp.mcp_add_command("claude", name, rendered[name]) for name in names])
        self.assertNotIn("jcodemunch", json.dumps(ran))


class McpGetOutputTests(unittest.TestCase):
    # SERENA_CONTEXT_20260923, JCODEMUNCH and AI_MEMORY were recorded from `claude mcp get` (claude
    # 2.1.280, 2026-09-23) with the home path replaced. That day's serena entry ran the recording
    # host's own `serena-context` wrapper, which nothing in this repository installs. JCODEMUNCH is
    # the user-scope entry the template carried until 2026-09-25; it stays the recorded fixture for
    # a stdio server with empty args and env names, matched against JCODEMUNCH_SPEC.
    SERENA_CONTEXT_20260923 = (
        "serena:\n  Scope: User config (available in all your projects)\n  Status: \u2714 Connected\n"
        "  Type: stdio\n  Command: /home/example/.local/share/codex-ecosystem/bin/serena-context\n"
        "  Args: start-mcp-server --transport stdio --project-from-cwd --context claude-code "
        "--enable-web-dashboard true --open-web-dashboard false --enable-gui-log-window false\n"
        "  Environment:\n\nTo remove this server, run: claude mcp remove serena -s user\n"
    )
    # Recorded 2026-09-25 (claude 2.1.282) after install_claude_profile.py --only mcp registered the
    # current template under a temporary CLAUDE_CONFIG_DIR, with Serena installed as a uv tool at the
    # stack pin; the scratch ecosystem prefix is replaced by the default one.
    SERENA = (
        "serena:\n  Scope: User config (available in all your projects)\n  Status: \u2714 Connected\n"
        "  Type: stdio\n  Command: /home/example/.local/share/codex-ecosystem/bin/serena\n"
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

    def rendered_jcodemunch(self):
        return icp.render_servers({"mcpServers": {"jcodemunch": JCODEMUNCH_SPEC}}, Path("/home/example"),
                                  Path("/home/example/.local/share/codex-ecosystem"))["jcodemunch"]

    def matches(self, text, spec):
        kind = spec.get("type", "stdio")
        return icp.existing_config_matches(text, kind, spec["url"] if kind == "http" else spec["command"],
                                           spec.get("args", []), spec.get("env", {}))

    def test_recorded_outputs_match_the_rendered_template(self):
        servers = self.rendered()
        self.assertTrue(self.matches(self.SERENA, servers["serena"]))
        self.assertTrue(self.matches(self.AI_MEMORY, servers["ai-memory"]))

    def test_recorded_env_output_matches_on_env_names(self):
        spec = self.rendered_jcodemunch()
        self.assertTrue(self.matches(self.JCODEMUNCH, spec))
        # The running host owns env values: another value still matches, a missing name does not.
        other_value = self.JCODEMUNCH.replace("=/home/example/.code-index", "=/srv/code-index")
        missing_name = self.JCODEMUNCH.replace("    JCODEMUNCH_SHARE_SAVINGS=0\n", "")
        self.assertNotEqual(other_value, self.JCODEMUNCH)
        self.assertNotEqual(missing_name, self.JCODEMUNCH)
        self.assertTrue(self.matches(other_value, spec))
        self.assertFalse(self.matches(missing_name, spec))

    def test_the_earlier_wrapper_registration_differs(self):
        # A host registered from the 2026-09-23 template is reported as differing and left
        # unchanged until --replace-mcp re-registers it with the upstream script.
        self.assertFalse(self.matches(self.SERENA_CONTEXT_20260923, self.rendered()["serena"]))

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
        self.assertEqual(results, ["other-scope"] * len(template_server_names()))
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
