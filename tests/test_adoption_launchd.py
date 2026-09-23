"""Static and local-integration checks for the drafted macOS launchd agents.

No macOS host ran anything here: `plutil` does not exist on this Linux CI/dev
host, so plist parsing below uses Python's stdlib `plistlib` (the same
fallback `launchd-agents.sh lint` itself uses when `plutil` is absent) and
`launchctl`/`id` are replaced with recording shims. Every assertion is
local_integration or structural evidence, never a claim that a launchd agent
has been bootstrapped, kickstarted or booted out on a real Mac (see
adoption/platforms/macos-arm64.md, "What a hosted run proves").
"""

import importlib.util
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
BASH = shutil.which("bash") or "/bin/bash"

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

    def test_qdrant_declares_a_working_directory_under_state(self):
        rendered = string.Template(self.templates["com.native-stack.qdrant.plist"].read_text()) \
            .substitute(FIXTURE_VALUES)
        data = plistlib.loads(rendered.encode("utf-8"))
        self.assertIn("state", data["WorkingDirectory"])
        self.assertTrue(data["WorkingDirectory"].startswith(FIXTURE_VALUES["ECO_ROOT"]))

    def test_no_double_hyphen_inside_any_xml_comment(self):
        # XML forbids "--" inside a comment's content (only "-->" may end it);
        # a template that violates this fails to parse on a real plutil too.
        for template_path in self.templates.values():
            text = template_path.read_text()
            for match in re.finditer(r"<!--(.*?)-->", text, re.S):
                self.assertNotIn("--", match.group(1), template_path.name)


def _load_render_launchd_module():
    spec = importlib.util.spec_from_file_location("render_launchd_direct", RENDER_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RenderLaunchdScriptTests(unittest.TestCase):
    def test_a_malformed_placeholder_raises_render_error_not_an_uncaught_valueerror(self):
        # string.Template.substitute raises ValueError (not KeyError) for a
        # malformed placeholder, e.g. a bare trailing "$"; render_plist must
        # turn that into the same RenderError every other failure mode uses.
        module = _load_render_launchd_module()
        with tempfile.TemporaryDirectory() as tmp:
            bad_template = Path(tmp) / "bad.plist.template"
            bad_template.write_text(
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
                '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
                '<plist version="1.0"><dict><key>Label</key>'
                '<string>trailing-dollar-$</string></dict></plist>\n'
            )
            with self.assertRaises(module.RenderError) as ctx:
                module.render_plist(bad_template, {})
            self.assertIn("invalid placeholder", str(ctx.exception))


    def test_a_literal_ampersand_in_a_substituted_value_round_trips_through_valid_xml(self):
        # Codex review, 2026-09-23: a naive string.Template substitution on
        # raw template text would put an unescaped "&" directly into XML
        # text content (e.g. ECO_ROOT=/Volumes/R&D/eco), which is not
        # well-formed XML ("&D/eco" is not a valid entity reference).
        # Rendering must escape it (plistlib.dumps does, by construction).
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "out"
            result = subprocess.run(
                [sys.executable, str(RENDER_SCRIPT), "--out", str(out_dir),
                 "--set", "HOME=/Volumes/R&D/home",
                 "--set", "ECO_ROOT=/Volumes/R&D/eco",
                 "--set", "AI_MEMORY_URL=127.0.0.1:49374"],
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            rendered = (out_dir / "com.native-stack.qdrant.plist").read_bytes()
            # A literal, unescaped "&" must never appear in the XML bytes;
            # only "&amp;" (or another valid XML entity) may.
            for match in re.finditer(rb"&(?!amp;|lt;|gt;|quot;|apos;|#)", rendered):
                self.fail(f"unescaped & at byte offset {match.start()} in {rendered!r}")
            data = plistlib.loads(rendered)
            self.assertIn("/Volumes/R&D/eco/bin/qdrant", data["ProgramArguments"])

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

    def test_remove_deletes_only_the_owned_plist_never_component_data_or_logs(self):
        # Every `rm` in the script targets exactly the copied unit-definition
        # file this script itself placed under ~/Library/LaunchAgents (on a
        # successful bootout, on removing an already-unloaded label, or on
        # rolling back a failed bootstrap during install); none may ever
        # target state/logs, state/qdrant, or the enabled-labels state file.
        self.assertNotIn("rm -rf", self.text)
        rm_lines = [line.strip() for line in self.text.splitlines() if re.search(r"\brm\b", line)]
        self.assertGreaterEqual(len(rm_lines), 1, rm_lines)
        for rm_line in rm_lines:
            self.assertTrue(
                'rm -f -- "$launch_agents_dir/$label.plist"' in rm_line or 'rm -f -- "$dest_plist"' in rm_line,
                rm_line,
            )
            for forbidden in ("state/logs", "state/qdrant", "enabled_state_file"):
                self.assertNotIn(forbidden, rm_line)

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

    def _render_only_dir(self, tmp_path: Path) -> Path:
        eco_root = tmp_path / "eco"
        result = self._run(["render"], env={**os.environ, "ECO_INSTALL_ROOT": str(eco_root)})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return eco_root / "state" / "launchd" / "rendered"

    def test_lint_falls_back_to_plistlib_when_plutil_is_absent(self):
        # A real Mac has plutil, so the generic end-to-end test above cannot
        # force this path there; PATH is restricted here to exactly one
        # directory (a real python3, no plutil) so this holds everywhere,
        # including on a real Mac.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            rendered_dir = self._render_only_dir(tmp_path)
            python3 = shutil.which("python3")
            self.assertIsNotNone(python3, "python3 must exist for this test to mean anything")
            restricted = tmp_path / "restricted-path"
            restricted.mkdir()
            (restricted / "python3").symlink_to(python3)
            result = subprocess.run(
                [BASH, str(SCRIPT_PATH), "lint", "--dir", str(rendered_dir)],
                capture_output=True, text=True, timeout=30,
                env={"PATH": str(restricted), "HOME": os.environ.get("HOME", str(tmp_path))},
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("plistlib fallback", result.stdout)
            self.assertIn("passed lint", result.stdout)

    def test_lint_prefers_plutil_when_present(self):
        # A fake plutil (not python3) so this holds on Linux too; it only
        # needs to prove cmd_lint calls plutil, by name, when command -v
        # finds one, and skips the plistlib fallback entirely in that case.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            rendered_dir = self._render_only_dir(tmp_path)
            log = tmp_path / "plutil-invocations.log"
            log.touch()
            shim = tmp_path / "plutil-shim"
            shim.mkdir()
            (shim / "plutil").write_text(
                f'#!/bin/sh\nprintf "%s\\n" "plutil $*" >> {str(log)!r}\nexit 0\n'
            )
            (shim / "plutil").chmod(0o755)
            result = subprocess.run(
                [BASH, str(SCRIPT_PATH), "lint", "--dir", str(rendered_dir)],
                capture_output=True, text=True, timeout=30,
                env={"PATH": str(shim), "HOME": os.environ.get("HOME", str(tmp_path))},
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertNotIn("plistlib fallback", result.stdout)
            invocations = log.read_text()
            self.assertEqual(invocations.count("plutil -lint"), 3, invocations)

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
            # Whichever of plutil or the plistlib fallback this host actually
            # used (a real Mac has plutil; this dev host does not) -- which
            # one is exercised deliberately is covered by the two dedicated
            # tests below, each with a controlled PATH.
            self.assertIn("passed lint", lint_result.stdout)

            install_result = self._run(["install"], env=env)
            self.assertEqual(install_result.returncode, 0, install_result.stdout + install_result.stderr)
            launch_agents_dir = fake_home / "Library" / "LaunchAgents"
            # llama-embed is left out of the default install set until a
            # model argument exists; only qdrant and ai-memory install here.
            for label in ("com.native-stack.qdrant", "com.native-stack.ai-memory"):
                self.assertTrue((launch_agents_dir / f"{label}.plist").is_file(), label)
            self.assertFalse((launch_agents_dir / "com.native-stack.llama-embed.plist").exists())
            self.assertTrue((eco_root / "state" / "logs").is_dir())
            self.assertTrue((eco_root / "state" / "qdrant").is_dir())
            state_file = eco_root / "state" / "launchd" / "enabled-labels.txt"
            enabled = state_file.read_text().split()
            self.assertEqual(set(enabled), {"com.native-stack.qdrant", "com.native-stack.ai-memory"})

            # An explicit --label still installs llama-embed even though the
            # default set skips it.
            explicit_install = self._run(["install", "--label", "com.native-stack.llama-embed"], env=env)
            self.assertEqual(explicit_install.returncode, 0, explicit_install.stdout + explicit_install.stderr)
            self.assertTrue((launch_agents_dir / "com.native-stack.llama-embed.plist").is_file())

            # install refuses to overwrite a plist it does not already own.
            unowned = launch_agents_dir / "com.native-stack.qdrant.plist"
            forget_result = self._run(["remove", "--label", "com.native-stack.qdrant"], env=env)
            self.assertEqual(forget_result.returncode, 0, forget_result.stdout + forget_result.stderr)
            self.assertFalse(unowned.exists())
            unowned.write_text("not ours")
            refused = self._run(["install", "--label", "com.native-stack.qdrant"], env=env)
            self.assertEqual(refused.returncode, 1, refused.stdout + refused.stderr)
            self.assertIn("Refusing to overwrite", refused.stderr)
            self.assertEqual(unowned.read_text(), "not ours")
            unowned.unlink()
            # Restore qdrant as owned again for the remainder of this test.
            reinstall = self._run(["install", "--label", "com.native-stack.qdrant"], env=env)
            self.assertEqual(reinstall.returncode, 0, reinstall.stdout + reinstall.stderr)

            status_result = self._run(["status", "--label", "com.native-stack.qdrant"], env=env)
            self.assertEqual(status_result.returncode, 0, status_result.stdout + status_result.stderr)

            remove_result = self._run(["remove", "--label", "com.native-stack.qdrant"], env=env)
            self.assertEqual(remove_result.returncode, 0, remove_result.stdout + remove_result.stderr)
            self.assertIn("Booted out 1 label(s); skipped 0", remove_result.stdout)
            # A successful bootout deletes the copied plist (so it cannot
            # reload at the next login); it never touches component data or
            # logs (state/logs, state/qdrant are untouched, still directories).
            self.assertFalse((launch_agents_dir / "com.native-stack.qdrant.plist").exists())
            self.assertTrue((eco_root / "state" / "logs").is_dir())
            self.assertTrue((eco_root / "state" / "qdrant").is_dir())
            remaining = state_file.read_text().split()
            self.assertEqual(set(remaining), {"com.native-stack.ai-memory", "com.native-stack.llama-embed"})

            # A second remove of the same, now-unrecorded label is a no-op skip,
            # never a bootout of a label this script no longer considers its own.
            second_remove = self._run(["remove", "--label", "com.native-stack.qdrant"], env=env)
            self.assertEqual(second_remove.returncode, 0, second_remove.stdout + second_remove.stderr)
            self.assertIn("was not enabled by this script", second_remove.stderr)
            self.assertIn("Booted out 0 label(s); skipped 1", second_remove.stdout)

            invocations = log.read_text()
            self.assertEqual(invocations.count("launchctl bootstrap"), 4)
            # One explicit `status`, plus one `launchctl print` per remove
            # attempt that actually reaches an enabled label (cmd_remove
            # checks whether a label is loaded before calling bootout); the
            # trailing no-op remove never reaches that check at all (the
            # label is no longer enabled), so it adds neither a print nor a
            # bootout call.
            self.assertEqual(invocations.count("launchctl print"), 3)
            self.assertEqual(invocations.count("launchctl bootout"), 2,
                              "one for the mid-test forget, one for the final remove; "
                              "the trailing no-op remove must not invoke bootout again")

    def test_remove_keeps_ownership_and_the_plist_when_bootout_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            eco_root = tmp_path / "eco"
            fake_home = tmp_path / "home"
            fake_home.mkdir()
            failing_shim = tmp_path / "failing-shim"
            failing_shim.mkdir()
            # bootstrap must still succeed (install uses it); only bootout
            # fails, so the failure exercised here is specific to remove.
            (failing_shim / "launchctl").write_text(
                '#!/bin/sh\ncase "$1" in\n  bootout) exit 1 ;;\n  *) exit 0 ;;\nesac\n'
            )
            (failing_shim / "launchctl").chmod(0o755)
            env = {
                **os.environ,
                "PATH": f"{failing_shim}{os.pathsep}{os.environ['PATH']}",
                "ECO_INSTALL_ROOT": str(eco_root),
                "HOME": str(fake_home),
            }
            self.assertEqual(self._run(["render"], env=env).returncode, 0)
            install_result = self._run(["install"], env=env)
            self.assertEqual(install_result.returncode, 0, install_result.stdout + install_result.stderr)
            launch_agents_dir = fake_home / "Library" / "LaunchAgents"
            self.assertTrue((launch_agents_dir / "com.native-stack.qdrant.plist").is_file())

            remove_result = self._run(["remove", "--label", "com.native-stack.qdrant"], env=env)
            self.assertNotEqual(remove_result.returncode, 0, remove_result.stdout + remove_result.stderr)
            self.assertIn("bootout failed", remove_result.stderr)
            self.assertIn("ownership kept", remove_result.stderr)
            # The plist survives a failed bootout, and the label is still
            # recorded as enabled, so a retry (with a working launchctl) can
            # find and finish the job.
            self.assertTrue((launch_agents_dir / "com.native-stack.qdrant.plist").is_file())
            state_file = eco_root / "state" / "launchd" / "enabled-labels.txt"
            self.assertIn("com.native-stack.qdrant", state_file.read_text().split())

    def test_install_removes_the_orphan_when_bootstrap_fails(self):
        # Medium finding: cp ran before launchctl bootstrap, so a failed
        # bootstrap left an unowned plist under ~/Library/LaunchAgents that
        # would load at the next login, and neither a retry (the ownership
        # check) nor remove (never touches an unrecorded label) could ever
        # reach it again.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            eco_root = tmp_path / "eco"
            fake_home = tmp_path / "home"
            fake_home.mkdir()
            failing_shim = tmp_path / "failing-shim"
            failing_shim.mkdir()
            (failing_shim / "launchctl").write_text("#!/bin/sh\ncase \"$1\" in\n  bootstrap) exit 1 ;;\n  *) exit 0 ;;\nesac\n")
            (failing_shim / "launchctl").chmod(0o755)
            env = {
                **os.environ,
                "PATH": f"{failing_shim}{os.pathsep}{os.environ['PATH']}",
                "ECO_INSTALL_ROOT": str(eco_root),
                "HOME": str(fake_home),
            }
            self.assertEqual(self._run(["render"], env=env).returncode, 0)
            install_result = self._run(["install", "--label", "com.native-stack.qdrant"], env=env)
            self.assertNotEqual(install_result.returncode, 0, install_result.stdout + install_result.stderr)
            self.assertIn("bootstrap failed", install_result.stderr)
            launch_agents_dir = fake_home / "Library" / "LaunchAgents"
            self.assertFalse((launch_agents_dir / "com.native-stack.qdrant.plist").exists())
            state_file = eco_root / "state" / "launchd" / "enabled-labels.txt"
            enabled = state_file.read_text().split() if state_file.exists() else []
            self.assertNotIn("com.native-stack.qdrant", enabled)
            # A retry with a working launchctl succeeds cleanly, proving the
            # rollback did not leave anything behind that would block it.
            working_shim = self._launchctl_shim(tmp_path, tmp_path / "working-launchctl.log")
            working_env = {**env, "PATH": f"{working_shim}{os.pathsep}{os.environ['PATH']}"}
            retry = self._run(["install", "--label", "com.native-stack.qdrant"], env=working_env)
            self.assertEqual(retry.returncode, 0, retry.stdout + retry.stderr)

    def test_remove_on_an_unloaded_owned_label_cleans_up_without_calling_bootout(self):
        # Low finding: bootout always fails on a label that is owned but not
        # currently loaded (already unloaded outside this script, crashed,
        # or never finished bootstrapping); check launchctl print first and
        # clean up directly instead of guaranteeing a failed bootout call.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            eco_root = tmp_path / "eco"
            fake_home = tmp_path / "home"
            fake_home.mkdir()
            log = tmp_path / "launchctl.log"
            log.touch()
            shim = tmp_path / "shim"
            shim.mkdir()
            # print reports "not loaded" (nonzero); bootout would exit 0 if
            # ever called, so a bootout invocation in the log would prove
            # the fix is NOT skipping it as intended.
            (shim / "launchctl").write_text(
                "#!/bin/sh\n"
                f'printf "%s\\n" "launchctl $*" >> {str(log)!r}\n'
                'case "$1" in\n'
                '  print) exit 1 ;;\n'
                '  *) exit 0 ;;\n'
                'esac\n'
            )
            (shim / "launchctl").chmod(0o755)
            env = {
                **os.environ,
                "PATH": f"{shim}{os.pathsep}{os.environ['PATH']}",
                "ECO_INSTALL_ROOT": str(eco_root),
                "HOME": str(fake_home),
            }
            self.assertEqual(self._run(["render"], env=env).returncode, 0)
            install_result = self._run(["install", "--label", "com.native-stack.qdrant"], env=env)
            self.assertEqual(install_result.returncode, 0, install_result.stdout + install_result.stderr)

            remove_result = self._run(["remove", "--label", "com.native-stack.qdrant"], env=env)
            self.assertEqual(remove_result.returncode, 0, remove_result.stdout + remove_result.stderr)
            self.assertIn("was not loaded", remove_result.stdout)
            launch_agents_dir = fake_home / "Library" / "LaunchAgents"
            self.assertFalse((launch_agents_dir / "com.native-stack.qdrant.plist").exists())
            state_file = eco_root / "state" / "launchd" / "enabled-labels.txt"
            self.assertNotIn("com.native-stack.qdrant", state_file.read_text().split())
            invocations = log.read_text()
            self.assertNotIn("bootout", invocations, "bootout must not be called on an unloaded label")

    def test_install_creates_directories_from_the_plists_own_declared_paths_not_eco_install_root(self):
        # Low finding: --host renders can point ECO_ROOT somewhere entirely
        # different from this shell's own ECO_INSTALL_ROOT; the directories
        # install creates must come from the rendered plist's own
        # StandardOutPath/StandardErrorPath/WorkingDirectory, not the shell.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fake_home = tmp_path / "home"
            fake_home.mkdir()
            other_root = tmp_path / "elsewhere" / "eco-root"
            host_file = ROOT / "adoption" / "hosts" / "test-launchd-other-host.json"
            host_file.write_text(json.dumps({
                "HOME": str(fake_home), "ECO_ROOT": str(other_root), "AI_MEMORY_URL": "127.0.0.1:49374",
            }))
            self.addCleanup(host_file.unlink, missing_ok=True)
            log = tmp_path / "launchctl.log"
            log.touch()
            shim = self._launchctl_shim(tmp_path, log)
            eco_root_unused = tmp_path / "eco-unused"
            env = {
                **os.environ,
                "PATH": f"{shim}{os.pathsep}{os.environ['PATH']}",
                # Deliberately different from --host's own ECO_ROOT, so a
                # bug that used $eco_root instead of the plist's own paths
                # would create directories in the WRONG (this) location.
                "ECO_INSTALL_ROOT": str(eco_root_unused),
                "HOME": str(fake_home),
            }
            render_result = self._run(["render", "--host", "test-launchd-other-host"], env=env)
            self.assertEqual(render_result.returncode, 0, render_result.stdout + render_result.stderr)
            install_result = self._run(["install", "--label", "com.native-stack.qdrant"], env=env)
            self.assertEqual(install_result.returncode, 0, install_result.stdout + install_result.stderr)
            self.assertTrue((other_root / "state" / "logs").is_dir())
            self.assertTrue((other_root / "state" / "qdrant").is_dir())
            # eco_root_unused/state/launchd/rendered legitimately exists (the
            # render step's own output directory); state/logs and
            # state/qdrant specifically -- what the old ECO_INSTALL_ROOT-based
            # bug would have created here instead of under other_root -- must
            # not.
            self.assertFalse((eco_root_unused / "state" / "logs").exists())
            self.assertFalse((eco_root_unused / "state" / "qdrant").exists())


if __name__ == "__main__":
    unittest.main()
