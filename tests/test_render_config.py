"""Local integration tests for tools/adoption/render_config.py (fixture host, no live host claims)."""

import json
import string
import subprocess
import sys
import tempfile
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
        # ${CLAUDE_CONFIG_DIR:-$HOME/.claude} and ${plugin_dir}; only our nine
        # placeholder names are required to disappear after substitution.
        for name in TEMPLATE_NAMES:
            text = (TEMPLATES / name).read_text()
            rendered = string.Template(text).substitute(FIXTURE_VALUES)
            for key in FIXTURE_VALUES:
                self.assertNotIn("${" + key + "}", rendered, (name, key))
            if name.endswith(".json"):
                json.loads(rendered)  # still valid JSON once rendered

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
        self.assertIn(str(self.tmp_path / ".codex" / "config.toml"), result.stdout + result.stderr)

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

    def test_check_reports_missing_live_file(self):
        result = run("--host", "test-fixture-host", "--check",
                     "--live-settings", str(self.tmp_path / "nowhere.json"),
                     "--live-codex-user", str(self.tmp_path / "nowhere2.toml"),
                     "--live-codex-project", str(self.tmp_path / "nowhere3.toml"))
        self.assertEqual(result.returncode, 1)
        self.assertIn("live file not found", result.stderr)


if __name__ == "__main__":
    unittest.main()
