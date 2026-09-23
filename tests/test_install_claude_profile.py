"""Unit tests for tools/adoption/install_claude_profile.py's guard/agents
steps (sha256-checked, idempotent) and the MCP registration matcher used to
decide whether an existing `claude mcp get` entry already matches the
template (so registration is skipped rather than repeated). The `claude`
binary itself is never invoked here; MCP idempotency is tested against
`existing_config_matches` directly with recorded-shape text fixtures.
"""

import sys
import tempfile
import unittest
from pathlib import Path

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


class AgentsInstallTests(unittest.TestCase):
    def test_installs_all_five_agents(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            results = icp.install_agents(home, dry_run=False)
            self.assertEqual(len(results), 5)
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


if __name__ == "__main__":
    unittest.main()
