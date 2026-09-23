"""Static and local-integration checks for the drafted macOS launchd agents.

No macOS host ran anything here: `plutil` does not exist on this Linux CI/dev
host, so plist parsing below uses Python's stdlib `plistlib` (the same
fallback `launchd-agents.sh lint` itself uses when `plutil` is absent) and
`launchctl`/`id` are replaced with recording shims. Every assertion is
local_integration or structural evidence, never a claim that a launchd agent
has been bootstrapped, kickstarted or booted out on a real Mac (see
adoption/platforms/macos-arm64.md, "What a hosted run proves").
"""

import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import string
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
LAUNCHD_DIR = ROOT / "adoption" / "launchd"
SCRIPT_PATH = LAUNCHD_DIR / "launchd-agents.sh"
RENDER_SCRIPT = ROOT / "tools" / "adoption" / "render_launchd.py"
PAGE_PATH = ROOT / "adoption" / "platforms" / "macos-arm64.md"
BOOTSTRAP_SCRIPT = ROOT / "adoption" / "bootstrap-macos.sh"

TEMPLATE_SUFFIX = ".plist.template"
SHELLCHECK = shutil.which("shellcheck")

FIXTURE_VALUES = {
    "HOME": "/Users/example",
    "ECO_ROOT": "/Users/example/.local/share/codex-ecosystem",
    "AI_MEMORY_URL": "127.0.0.1:49374",
}


def templates() -> dict[str, Path]:
    return {
        path.name[: -len(TEMPLATE_SUFFIX)] + ".plist": path
        for path in sorted(LAUNCHD_DIR.glob(f"*{TEMPLATE_SUFFIX}"))
    }


class TemplateRenderAndSchemaTests(unittest.TestCase):
    def setUp(self):
        self.templates = templates()

    def test_at_least_the_three_documented_agents_exist(self):
        expected = {
            "com.native-stack.qdrant.plist",
            "com.native-stack.ai-memory.plist",
            "com.native-stack.llama-embed.plist",
        }
        self.assertEqual(set(self.templates), expected)

    def test_every_template_renders_and_parses_with_plistlib(self):
        for rendered_name, template_path in self.templates.items():
            text = template_path.read_text()
            rendered = string.Template(text).substitute(FIXTURE_VALUES)
            data = plistlib.loads(rendered.encode("utf-8"))
            with self.subTest(template=rendered_name):
                self.assertIsInstance(data, dict)

    def test_label_equals_the_rendered_filename(self):
        for rendered_name, template_path in self.templates.items():
            rendered = string.Template(template_path.read_text()).substitute(FIXTURE_VALUES)
            data = plistlib.loads(rendered.encode("utf-8"))
            expected_label = rendered_name[: -len(".plist")]
            with self.subTest(template=rendered_name):
                self.assertEqual(data["Label"], expected_label)

    def test_run_at_load_and_keep_alive_are_present(self):
        for rendered_name, template_path in self.templates.items():
            rendered = string.Template(template_path.read_text()).substitute(FIXTURE_VALUES)
            data = plistlib.loads(rendered.encode("utf-8"))
            with self.subTest(template=rendered_name):
                self.assertIs(data["RunAtLoad"], True)
                self.assertIs(data["KeepAlive"], True)

    def test_path_starts_with_opt_homebrew_bin(self):
        for rendered_name, template_path in self.templates.items():
            rendered = string.Template(template_path.read_text()).substitute(FIXTURE_VALUES)
            data = plistlib.loads(rendered.encode("utf-8"))
            with self.subTest(template=rendered_name):
                self.assertTrue(data["EnvironmentVariables"]["PATH"].startswith("/opt/homebrew/bin"))

    def test_logs_go_under_state_logs(self):
        for rendered_name, template_path in self.templates.items():
            rendered = string.Template(template_path.read_text()).substitute(FIXTURE_VALUES)
            data = plistlib.loads(rendered.encode("utf-8"))
            with self.subTest(template=rendered_name):
                self.assertIn("state/logs", data["StandardOutPath"])
                self.assertIn("state/logs", data["StandardErrorPath"])

    def test_llama_embed_matches_the_documented_invocation(self):
        rendered = string.Template(self.templates["com.native-stack.llama-embed.plist"].read_text()) \
            .substitute(FIXTURE_VALUES)
        data = plistlib.loads(rendered.encode("utf-8"))
        arguments = data["ProgramArguments"]
        self.assertTrue(arguments[0].endswith("/bin/llama-server"))
        self.assertIn("--embedding", arguments)
        self.assertIn("--port", arguments)
        self.assertEqual(arguments[arguments.index("--port") + 1], "8232")

    def test_no_double_hyphen_inside_any_xml_comment(self):
        # XML forbids "--" inside a comment's content (only "-->" may end it);
        # a template that violates this fails to parse on a real plutil too.
        for template_path in self.templates.values():
            text = template_path.read_text()
            for match in re.finditer(r"<!--(.*?)-->", text, re.S):
                self.assertNotIn("--", match.group(1), template_path.name)


class RenderLaunchdScriptTests(unittest.TestCase):
    def test_render_writes_every_template_to_the_output_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "out"
            result = subprocess.run(
                [sys.executable, str(RENDER_SCRIPT), "--out", str(out_dir),
                 "--set", "HOME=/Users/example",
                 "--set", "ECO_ROOT=/Users/example/.local/share/codex-ecosystem",
                 "--set", "AI_MEMORY_URL=127.0.0.1:49374"],
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for rendered_name in templates():
                self.assertTrue((out_dir / rendered_name).is_file(), rendered_name)

    def test_render_reuses_the_shared_host_value_file_convention(self):
        # adoption/hosts/macos-example.json is a real, committed host file;
        # it supplies more keys (HOST_PATH, QDRANT_URL, ...) than these
        # templates use, which string.Template.substitute tolerates.
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "out"
            result = subprocess.run(
                [sys.executable, str(RENDER_SCRIPT), "--host", "macos-example", "--out", str(out_dir)],
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            with (out_dir / "com.native-stack.qdrant.plist").open("rb") as handle:
                data = plistlib.load(handle)
            self.assertTrue(data["ProgramArguments"][0].startswith("/Users/example/"))

    def test_missing_placeholder_value_fails_with_nonzero_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "out"
            result = subprocess.run(
                [sys.executable, str(RENDER_SCRIPT), "--out", str(out_dir), "--set", "HOME=/Users/example"],
                capture_output=True, text=True, timeout=30,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing template value", result.stderr)


class LaunchdAgentsScriptStructureTests(unittest.TestCase):
    def setUp(self):
        self.text = SCRIPT_PATH.read_text()

    def test_script_is_executable_with_expected_shebang_and_strict_mode(self):
        self.assertTrue(SCRIPT_PATH.stat().st_mode & 0o111, "script is not executable")
        self.assertEqual(self.text.splitlines()[0], "#!/usr/bin/env bash")
        self.assertIn("set -Eeuo pipefail", self.text)

    def test_stays_bash_32_safe(self):
        self.assertNotIn("${#", self.text, "use an explicit counter, not ${#array[@]}, for bash 3.2")
        self.assertNotIn("mapfile", self.text)

    def test_declares_the_five_subcommands(self):
        for subcommand in ("render", "lint", "install", "status", "remove"):
            self.assertIn(f"cmd_{subcommand.replace('-', '_')}", self.text)

    def test_lint_prefers_plutil_and_falls_back_to_plistlib(self):
        self.assertIn("plutil", self.text)
        self.assertIn("plistlib", self.text)

    def test_install_uses_launchctl_bootstrap(self):
        self.assertIn("launchctl bootstrap", self.text)

    def test_status_uses_launchctl_print(self):
        self.assertIn("launchctl print", self.text)

    def test_remove_uses_launchctl_bootout_gated_on_this_scripts_own_state(self):
        self.assertIn("launchctl bootout", self.text)
        self.assertIn("is_enabled_label", self.text)
        self.assertIn("was not enabled by this script", self.text)

    def test_remove_never_deletes_the_installed_plist_or_state(self):
        self.assertNotIn("rm -f", self.text)
        self.assertNotIn("rm -rf", self.text)

    def test_formula_list_equals_the_brew_install_line_documented_in_the_platform_page(self):
        script_match = re.search(
            r"^brew_formulae=\(([^)]*)\)", BOOTSTRAP_SCRIPT.read_text(), re.M)
        self.assertIsNotNone(script_match, "bootstrap-macos.sh must declare brew_formulae=(...)")
        script_formulae = script_match.group(1).split()

        page_match = re.search(r"^brew install (.+)$", PAGE_PATH.read_text(), re.M)
        self.assertIsNotNone(page_match, "macos-arm64.md must document a `brew install ...` line")
        page_formulae = page_match.group(1).split()

        self.assertEqual(script_formulae, page_formulae)

    @unittest.skipUnless(SHELLCHECK, "native shellcheck unavailable; CI installs the pinned analyzer")
    def test_shellcheck_style_is_clean(self):
        result = subprocess.run(
            [SHELLCHECK, "-S", "style", str(SCRIPT_PATH)],
            capture_output=True, text=True, timeout=60, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_bash_n_syntax_is_valid(self):
        result = subprocess.run(["bash", "-n", str(SCRIPT_PATH)],
                                 capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)


class LaunchdAgentsScriptBehaviorTests(unittest.TestCase):
    """Exercises render/lint/install/status/remove offline with a fake
    launchctl/id on PATH; no macOS host and no real launchd session."""

    def _launchctl_shim(self, directory: Path, log: Path) -> Path:
        shim = directory / "shim"
        shim.mkdir(exist_ok=True)
        (shim / "launchctl").write_text(
            f'#!/bin/sh\nprintf "%s\\n" "launchctl $*" >> {str(log)!r}\nexit 0\n'
        )
        (shim / "launchctl").chmod(0o755)
        return shim

    def _run(self, args, env):
        return subprocess.run(
            ["bash", str(SCRIPT_PATH), *args],
            capture_output=True, text=True, timeout=30, env=env,
        )

    def test_help_exits_zero(self):
        result = self._run(["--help"], env={**os.environ})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("render", result.stdout)
        self.assertIn("remove", result.stdout)

    def test_missing_subcommand_exits_two(self):
        result = self._run([], env={**os.environ})
        self.assertEqual(result.returncode, 2)

    def test_unknown_subcommand_exits_two(self):
        result = self._run(["frobnicate"], env={**os.environ})
        self.assertEqual(result.returncode, 2)
        self.assertIn("Unknown subcommand", result.stderr)

    def test_unknown_label_exits_two(self):
        result = self._run(["status", "--label", "com.native-stack.nope"], env={**os.environ})
        self.assertEqual(result.returncode, 2)
        self.assertIn("Unknown --label", result.stderr)

    def test_full_render_lint_install_status_remove_cycle_offline(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            eco_root = tmp_path / "eco"
            fake_home = tmp_path / "home"
            fake_home.mkdir()
            log = tmp_path / "launchctl.log"
            log.touch()
            shim = self._launchctl_shim(tmp_path, log)
            env = {
                **os.environ,
                "PATH": f"{shim}{os.pathsep}{os.environ['PATH']}",
                "ECO_INSTALL_ROOT": str(eco_root),
                "HOME": str(fake_home),
            }

            render_result = self._run(["render"], env=env)
            self.assertEqual(render_result.returncode, 0, render_result.stdout + render_result.stderr)
            rendered_dir = eco_root / "state" / "launchd" / "rendered"
            self.assertTrue((rendered_dir / "com.native-stack.qdrant.plist").is_file())

            lint_result = self._run(["lint"], env=env)
            self.assertEqual(lint_result.returncode, 0, lint_result.stdout + lint_result.stderr)
            self.assertIn("plistlib fallback", lint_result.stdout)

            install_result = self._run(["install"], env=env)
            self.assertEqual(install_result.returncode, 0, install_result.stdout + install_result.stderr)
            launch_agents_dir = fake_home / "Library" / "LaunchAgents"
            for label in ("com.native-stack.qdrant", "com.native-stack.ai-memory", "com.native-stack.llama-embed"):
                self.assertTrue((launch_agents_dir / f"{label}.plist").is_file(), label)
            state_file = eco_root / "state" / "launchd" / "enabled-labels.txt"
            enabled = state_file.read_text().split()
            self.assertEqual(
                set(enabled),
                {"com.native-stack.qdrant", "com.native-stack.ai-memory", "com.native-stack.llama-embed"},
            )

            status_result = self._run(["status", "--label", "com.native-stack.qdrant"], env=env)
            self.assertEqual(status_result.returncode, 0, status_result.stdout + status_result.stderr)

            remove_result = self._run(["remove", "--label", "com.native-stack.qdrant"], env=env)
            self.assertEqual(remove_result.returncode, 0, remove_result.stdout + remove_result.stderr)
            self.assertIn("Booted out 1 label(s); skipped 0", remove_result.stdout)
            # The plist file and its parent LaunchAgents copy are never deleted.
            self.assertTrue((launch_agents_dir / "com.native-stack.qdrant.plist").is_file())
            remaining = state_file.read_text().split()
            self.assertEqual(set(remaining), {"com.native-stack.ai-memory", "com.native-stack.llama-embed"})

            # A second remove of the same, now-unrecorded label is a no-op skip,
            # never a bootout of a label this script no longer considers its own.
            second_remove = self._run(["remove", "--label", "com.native-stack.qdrant"], env=env)
            self.assertEqual(second_remove.returncode, 0, second_remove.stdout + second_remove.stderr)
            self.assertIn("was not enabled by this script", second_remove.stderr)
            self.assertIn("Booted out 0 label(s); skipped 1", second_remove.stdout)

            invocations = log.read_text()
            self.assertEqual(invocations.count("launchctl bootstrap"), 3)
            self.assertEqual(invocations.count("launchctl print"), 1)
            self.assertEqual(invocations.count("launchctl bootout"), 1,
                              "the second remove must not invoke bootout again")


if __name__ == "__main__":
    unittest.main()
