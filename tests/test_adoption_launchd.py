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

    def test_a_control_character_from_a_substituted_value_raises_render_error(self):
        # plistlib.dumps raises ValueError for a control character (XML
        # plist text content cannot represent one) -- this must happen
        # inside the same try as _substitute, not after it, or it would be
        # an uncaught exception instead of the usual RenderError.
        module = _load_render_launchd_module()
        with tempfile.TemporaryDirectory() as tmp:
            template = Path(tmp) / "control-char.plist.template"
            template.write_text(
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
                '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
                '<plist version="1.0"><dict><key>Label</key>'
                '<string>${VALUE}</string></dict></plist>\n'
            )
            with self.assertRaises(module.RenderError) as ctx:
                module.render_plist(template, {"VALUE": "bad\x01char"})
            self.assertIn("control character", str(ctx.exception))

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

    def test_install_backup_lives_beside_dest_plist_as_a_hard_link(self):
        # N1 (same directory, round 3d) + round 3e (Codex High #2): the
        # backup is a HARD LINK, not `cp` -- it either exists completely or
        # not at all, so a partial copy can never overwrite the intact
        # original. Same directory as dest_plist (never this script's own
        # state_dir): a restore-by-rename is only genuinely atomic when
        # guaranteed to be on the same filesystem. Its name never ends in
        # ".plist" (never auto-loaded by launchd), and reconcile_install
        # restores it by rename, never by `cp`.
        self.assertIn('backup_plist="$dest_plist.bak"', self.text)
        self.assertIn('ln -- "$dest_plist" "$backup_plist"', self.text)
        self.assertNotIn('cp -- "$dest_plist" "$backup_plist"', self.text)
        self.assertIn("trap reconcile_install EXIT", self.text)
        self.assertIn('mv -f -- "$backup_plist" "$dest_plist"', self.text)

    def test_install_reconciles_from_actual_state_not_recorded_markers(self):
        # Round 3e: replaces round 3d's pending_backup_reload_needed marker
        # (set once, at bootout time, then trusted for the rest of the run)
        # with re-deriving loaded state from launchctl print itself, every
        # time reconcile_install runs -- so a marker that went stale (the
        # exact class of bug rounds 3b-3d each individually patched) cannot
        # recur by construction: there is no marker left to go stale.
        self.assertNotIn("pending_backup_reload_needed", self.text)
        self.assertNotIn("pending_backup_plist", self.text)
        self.assertIn('"$dest_plist" -ef "$backup_plist"', self.text)
        self.assertIn('launchctl print "gui/$(id -u)/$label"', self.text)

    def test_int_term_hup_are_trapped_to_defer_to_a_completed_step(self):
        # Round 3e (Codex Medium #5 boundary case): explicitly trapping
        # INT/TERM/HUP -- not leaving them at their default disposition --
        # makes bash defer acting on a caught signal until the current
        # foreign command finishes, so the EXIT handler (reconcile_install)
        # never observes a step still in flight.
        self.assertIn("trap 'exit 130' INT", self.text)
        self.assertIn("trap 'exit 143' TERM", self.text)
        self.assertIn("trap 'exit 129' HUP", self.text)

    def test_install_gates_its_pre_reinstall_load_check_on_ownership(self):
        # L2, structural: the print/bootout probe before a reinstall must be
        # reached only for a label this script itself recorded as enabled.
        self.assertRegex(
            self.text,
            r"if is_enabled_label \"\$label\"; then\n\s+local print_status=0\n\s+launchctl print",
        )

    def test_install_treats_only_exit_113_as_confidently_unloaded(self):
        # L5, structural: any launchctl print exit other than 0 (loaded) or
        # 113 (not found) must refuse, the same way remove already does.
        self.assertIn('elif [[ "$print_status" != 113 ]]; then', self.text)

    def test_install_waits_for_unloaded_after_a_successful_bootout(self):
        # L4, structural: bootout succeeding is not itself trusted; a
        # bounded poll of launchctl print must confirm 113 before bootstrap.
        self.assertIn("wait_until_unloaded", self.text)

    def test_remove_deletes_only_the_owned_plist_never_component_data_or_logs(self):
        # Every `rm` in the script targets exactly the copied unit-definition
        # file this script itself placed under ~/Library/LaunchAgents (on a
        # successful bootout, on removing an already-unloaded label, or on
        # rolling back a failed bootstrap during install), or install's own
        # backup_plist (a hard link beside dest_plist, round 3e) via either
        # cmd_install's explicit cleanup or reconcile_install's convergence;
        # none may ever target state/logs, state/qdrant, or the
        # enabled-labels state file.
        self.assertNotIn("rm -rf", self.text)
        rm_lines = [line.strip() for line in self.text.splitlines() if re.search(r"\brm\b", line)]
        self.assertGreaterEqual(len(rm_lines), 1, rm_lines)
        allowed_targets = (
            'rm -f -- "$launch_agents_dir/$label.plist"',
            'rm -f -- "$dest_plist"',
            'rm -f -- "$backup_plist"',
        )
        for rm_line in rm_lines:
            self.assertTrue(any(target in rm_line for target in allowed_targets), rm_line)
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
        # Stateful, one marker file per label, mirroring real launchctl:
        # bootstrap "loads" the label its plist path names; print reports
        # loaded (0) once that label's marker exists, else 113 ("Could not
        # find service"); bootout always succeeds and clears the marker.
        # install's own pre-bootstrap print check relies on this to tell a
        # genuine first install (nothing loaded yet) from a reinstall of an
        # already-loaded label.
        shim = directory / "shim"
        shim.mkdir(exist_ok=True)
        (shim / "launchctl").write_text(
            '#!/bin/sh\n'
            f'printf "%s\\n" "launchctl $*" >> {str(log)!r}\n'
            'case "$1" in\n'
            '  bootstrap)\n'
            '    label="$(basename "$3" .plist)"\n'
            f'    touch "{shim!s}/$label.loaded.marker"\n'
            '    exit 0 ;;\n'
            '  print)\n'
            '    label="$(basename "$2")"\n'
            f'    [ -f "{shim!s}/$label.loaded.marker" ] && exit 0 || exit 113 ;;\n'
            '  bootout)\n'
            '    label="$(basename "$2")"\n'
            f'    rm -f "{shim!s}/$label.loaded.marker"\n'
            '    exit 0 ;;\n'
            '  *) exit 0 ;;\n'
            'esac\n'
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
            # cmd_install's own pre-reinstall print check (L2) is gated on
            # was_already_enabled: it never probes a label that was not yet
            # owned before this run, so every install in this cycle skips
            # THAT specific call (the default install's two labels, the
            # explicit llama-embed install, and the reinstall after the
            # unowned-file test are all fresh/unowned at the moment install
            # runs). reconcile_install's OWN print call (round 3e: it
            # re-derives loaded state itself, once per label, for every
            # successful install too, not only a failing one) still runs
            # for each of those four: 2 (default) + 1 (llama-embed) + 1
            # (the reinstall) = 4. Add cmd_remove's own print (mid-test
            # forget, and the final remove) and cmd_status's explicit call:
            # 4 + 1 + 1 + 1 = 7. The refused install (an unowned
            # destination) never reaches even the ownership gate, and the
            # trailing no-op remove never reaches its print or bootout call
            # either (the label is no longer enabled by that point).
            self.assertEqual(invocations.count("launchctl print"), 7)
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
            # A stateful shim, one marker file per label: bootstrap "loads"
            # the label its plist path names; print reports loaded (0) once
            # that label's marker exists, else 113 ("not found"); bootout
            # always fails. This lets install's own pre-check (print -> 113,
            # nothing loaded yet) proceed straight to a normal first install
            # for EVERY label in the default set, while remove's later print
            # (that label's marker now present) reports loaded, so remove
            # reaches -- and fails on -- bootout, which is what this test
            # actually exercises.
            (failing_shim / "launchctl").write_text(
                '#!/bin/sh\n'
                'case "$1" in\n'
                '  bootstrap)\n'
                '    label="$(basename "$3" .plist)"\n'
                '    touch "$(dirname "$0")/$label.loaded.marker"\n'
                '    exit 0 ;;\n'
                '  print)\n'
                '    label="$(basename "$2")"\n'
                '    [ -f "$(dirname "$0")/$label.loaded.marker" ] && exit 0 || exit 113 ;;\n'
                '  bootout) exit 1 ;;\n'
                '  *) exit 0 ;;\n'
                'esac\n'
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

    def test_a_persistently_failing_bootstrap_reports_needs_attention_and_a_retry_converges(self):
        # Round 3e: the previous design deleted the just-written plist on any
        # bootstrap failure ("removes the orphan"). Idempotent convergence
        # does the opposite on purpose: the plist stays on disk (nothing to
        # restore to, since this is a fresh install with no backup), install
        # reports non-convergence and names the retry command, and record_
        # enabled_label already ran, so a later retry (not a fresh install,
        # by ownership) can find and finish it. This is also true when the
        # ORIGINAL bug's root cause -- unrecorded ownership after a failed
        # bootstrap blocking every future retry -- is checked directly: it
        # is recorded regardless of outcome now, by design.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            eco_root = tmp_path / "eco"
            fake_home = tmp_path / "home"
            fake_home.mkdir()
            failing_shim = tmp_path / "failing-shim"
            failing_shim.mkdir()
            (failing_shim / "launchctl").write_text(
                "#!/bin/sh\ncase \"$1\" in\n  bootstrap) exit 1 ;;\n  print) exit 113 ;;\n  *) exit 0 ;;\nesac\n"
            )
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
            self.assertIn("needs attention", install_result.stderr)
            launch_agents_dir = fake_home / "Library" / "LaunchAgents"
            self.assertTrue((launch_agents_dir / "com.native-stack.qdrant.plist").is_file(),
                             "the plist stays on disk; there is nothing to restore to and a retry reuses it")
            state_file = eco_root / "state" / "launchd" / "enabled-labels.txt"
            enabled = state_file.read_text().split() if state_file.exists() else []
            self.assertIn("com.native-stack.qdrant", enabled,
                           "ownership is recorded regardless of outcome, so a retry is never refused as unowned")
            # A retry with a working launchctl converges cleanly.
            working_shim = self._launchctl_shim(tmp_path, tmp_path / "working-launchctl.log")
            working_env = {**env, "PATH": f"{working_shim}{os.pathsep}{os.environ['PATH']}"}
            retry = self._run(["install", "--label", "com.native-stack.qdrant"], env=working_env)
            self.assertEqual(retry.returncode, 0, retry.stdout + retry.stderr)

    def test_reinstalling_an_already_loaded_label_unloads_it_first_and_restores_on_a_failed_bootstrap(self):
        # Medium finding: re-running install on a label that is owned AND
        # already loaded (e.g. after a re-render) used to have cp overwrite
        # the live plist in place, bootstrap fail on an already-bootstrapped
        # label, and the rollback then delete the just-overwritten file out
        # from under the still-running service. install must unload it
        # first (so bootstrap has a chance to succeed), and if bootstrap
        # still fails, restore -- never delete -- a destination that already
        # existed before this reinstall.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            eco_root = tmp_path / "eco"
            fake_home = tmp_path / "home"
            fake_home.mkdir()
            log = tmp_path / "launchctl.log"
            log.touch()
            working_shim = self._launchctl_shim(tmp_path, log)
            env = {
                **os.environ,
                "PATH": f"{working_shim}{os.pathsep}{os.environ['PATH']}",
                "ECO_INSTALL_ROOT": str(eco_root),
                "HOME": str(fake_home),
            }
            self.assertEqual(self._run(["render"], env=env).returncode, 0)
            first_install = self._run(["install", "--label", "com.native-stack.qdrant"], env=env)
            self.assertEqual(first_install.returncode, 0, first_install.stdout + first_install.stderr)
            launch_agents_dir = fake_home / "Library" / "LaunchAgents"
            dest_plist = launch_agents_dir / "com.native-stack.qdrant.plist"
            original_content = dest_plist.read_bytes()

            # Now make bootstrap fail, but keep print/bootout working (the
            # label really is loaded, from the first install above).
            (working_shim / "launchctl").write_text(
                '#!/bin/sh\n'
                f'printf "%s\\n" "launchctl $*" >> {str(log)!r}\n'
                'case "$1" in\n'
                '  bootstrap) exit 1 ;;\n'
                '  print) [ -f "' + str(working_shim) + '/com.native-stack.qdrant.loaded.marker" ] && exit 0 || exit 113 ;;\n'
                '  bootout) rm -f "' + str(working_shim) + '/com.native-stack.qdrant.loaded.marker"; exit 0 ;;\n'
                '  *) exit 0 ;;\n'
                'esac\n'
            )
            reinstall = self._run(["install", "--label", "com.native-stack.qdrant"], env=env)
            self.assertNotEqual(reinstall.returncode, 0, reinstall.stdout + reinstall.stderr)
            # This shim's own bootstrap never succeeds for ANY content, so
            # reconcile_install's own reload-the-restored-original attempt
            # also fails here -- an honest "needs attention", not a false
            # "restored" success claim -- but the restore itself (the part
            # this finding is actually about: never delete a destination
            # that already existed) still happened.
            self.assertIn("restored the previous plist", reinstall.stderr)
            # The destination is restored to its original content, never
            # deleted (it existed and was owned before this reinstall).
            self.assertTrue(dest_plist.is_file())
            self.assertEqual(dest_plist.read_bytes(), original_content)
            # Still owned: the label was enabled before this reinstall and
            # stays that way.
            state_file = eco_root / "state" / "launchd" / "enabled-labels.txt"
            self.assertIn("com.native-stack.qdrant", state_file.read_text().split())
            invocations = log.read_text()
            self.assertIn("launchctl bootout", invocations)

    def test_install_never_boots_out_a_currently_loaded_label_it_does_not_own(self):
        # L2 (Opus round-3 verification / Codex round-3 Medium): without a
        # destination plist yet (a fresh install attempt), install must
        # never call launchctl bootout for that label -- only a label this
        # script ALREADY owned before this run (was_already_enabled) may
        # ever reach it, gated on a snapshot taken before record_enabled_
        # label makes is_enabled_label true for the rest of this same run
        # (round 3e; recording ownership now happens immediately, unlike
        # the previous design, so a plain is_enabled_label re-check right
        # before the bootout gate would otherwise always pass). bootstrap
        # and reconcile_install's own retry both fail here (a stand-in for
        # a persistent launchd-side rejection), so install correctly
        # reports non-convergence without ever having torn anything down.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            eco_root = tmp_path / "eco"
            fake_home = tmp_path / "home"
            fake_home.mkdir()
            log = tmp_path / "launchctl.log"
            log.touch()
            shim = tmp_path / "shim"
            shim.mkdir()
            (shim / "launchctl").write_text(
                "#!/bin/sh\n"
                f'printf "%s\\n" "launchctl $*" >> {str(log)!r}\n'
                'case "$1" in\n'
                '  print) exit 113 ;;\n'
                '  bootstrap) exit 5 ;;\n'
                '  bootout) exit 0 ;;\n'
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
            self.assertNotEqual(install_result.returncode, 0, install_result.stdout + install_result.stderr)
            self.assertIn("needs attention", install_result.stderr)
            invocations = log.read_text()
            self.assertNotIn("bootout", invocations,
                              "install must never bootout a label it does not own, even if it is loaded")

    def test_install_refuses_when_print_fails_with_neither_loaded_nor_not_found(self):
        # L5 (Opus + Codex round-3): install's own pre-reinstall load check
        # must treat only exit 113 as confidently "not loaded"; any other
        # launchctl print failure (permission, launchd unresponsive, ...)
        # must refuse rather than silently assume "not loaded" and bootstrap
        # over state print could not determine -- exactly what remove
        # already does for the same exit code.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            eco_root = tmp_path / "eco"
            fake_home = tmp_path / "home"
            fake_home.mkdir()
            log = tmp_path / "launchctl.log"
            log.touch()
            working_shim = self._launchctl_shim(tmp_path, log)
            env = {
                **os.environ,
                "PATH": f"{working_shim}{os.pathsep}{os.environ['PATH']}",
                "ECO_INSTALL_ROOT": str(eco_root),
                "HOME": str(fake_home),
            }
            self.assertEqual(self._run(["render"], env=env).returncode, 0)
            first_install = self._run(["install", "--label", "com.native-stack.qdrant"], env=env)
            self.assertEqual(first_install.returncode, 0, first_install.stdout + first_install.stderr)
            launch_agents_dir = fake_home / "Library" / "LaunchAgents"
            dest_plist = launch_agents_dir / "com.native-stack.qdrant.plist"
            original_content = dest_plist.read_bytes()

            (working_shim / "launchctl").write_text(
                '#!/bin/sh\n'
                f'printf "%s\\n" "launchctl $*" >> {str(log)!r}\n'
                'case "$1" in\n'
                '  print) exit 5 ;;\n'
                '  *) exit 0 ;;\n'
                'esac\n'
            )
            reinstall = self._run(["install", "--label", "com.native-stack.qdrant"], env=env)
            self.assertNotEqual(reinstall.returncode, 0, reinstall.stdout + reinstall.stderr)
            self.assertIn("not confidently unloaded", reinstall.stderr)
            invocations = log.read_text()
            self.assertNotIn("bootout", invocations)
            # Nothing was touched: the original, still-owned plist survives
            # untouched (the refusal happens before the overwriting cp).
            self.assertTrue(dest_plist.is_file())
            self.assertEqual(dest_plist.read_bytes(), original_content)
            state_file = eco_root / "state" / "launchd" / "enabled-labels.txt"
            self.assertIn("com.native-stack.qdrant", state_file.read_text().split())

    def test_install_refuses_when_bootout_succeeds_but_the_service_never_reports_unloaded(self):
        # L4 (Opus round-3 verification): on real launchd, bootout can
        # return before teardown finishes. install must poll launchctl
        # print for a bounded time and refuse -- never bootstrap over a
        # service that never actually stopped -- rather than trust bootout's
        # own exit code alone. WAIT_UNTIL_UNLOADED_ATTEMPTS/_INTERVAL are
        # overridden here so the bounded wait this exercises costs no real
        # wall-clock time.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            eco_root = tmp_path / "eco"
            fake_home = tmp_path / "home"
            fake_home.mkdir()
            log = tmp_path / "launchctl.log"
            log.touch()
            shim = tmp_path / "shim"
            shim.mkdir()
            # print always reports loaded; bootout exits 0 but never clears
            # anything, simulating teardown that has not actually finished.
            (shim / "launchctl").write_text(
                "#!/bin/sh\n"
                f'printf "%s\\n" "launchctl $*" >> {str(log)!r}\n'
                'case "$1" in\n'
                '  print) exit 0 ;;\n'
                '  bootstrap) exit 0 ;;\n'
                '  bootout) exit 0 ;;\n'
                '  *) exit 0 ;;\n'
                'esac\n'
            )
            (shim / "launchctl").chmod(0o755)
            env = {
                **os.environ,
                "PATH": f"{shim}{os.pathsep}{os.environ['PATH']}",
                "ECO_INSTALL_ROOT": str(eco_root),
                "HOME": str(fake_home),
                "WAIT_UNTIL_UNLOADED_ATTEMPTS": "2",
                "WAIT_UNTIL_UNLOADED_INTERVAL": "0",
            }
            self.assertEqual(self._run(["render"], env=env).returncode, 0)
            first_install = self._run(["install", "--label", "com.native-stack.qdrant"], env=env)
            self.assertEqual(first_install.returncode, 0, first_install.stdout + first_install.stderr)
            launch_agents_dir = fake_home / "Library" / "LaunchAgents"
            dest_plist = launch_agents_dir / "com.native-stack.qdrant.plist"
            original_content = dest_plist.read_bytes()

            reinstall = self._run(["install", "--label", "com.native-stack.qdrant"], env=env)
            self.assertNotEqual(reinstall.returncode, 0, reinstall.stdout + reinstall.stderr)
            self.assertIn("did not report unloaded", reinstall.stderr)
            invocations = log.read_text()
            self.assertIn("launchctl bootout", invocations)
            # Refused before the overwriting cp: the original plist survives.
            self.assertTrue(dest_plist.is_file())
            self.assertEqual(dest_plist.read_bytes(), original_content)

    def test_remove_keeps_ownership_and_the_plist_when_print_fails_unexpectedly(self):
        # L6 (Opus round-3 verification): only launchctl print exit 113
        # means "confidently not loaded"; any other failure (5, here) must
        # keep ownership and the plist, exactly like a failed bootout does,
        # rather than guess either way.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            eco_root = tmp_path / "eco"
            fake_home = tmp_path / "home"
            fake_home.mkdir()
            log = tmp_path / "launchctl.log"
            log.touch()
            working_shim = self._launchctl_shim(tmp_path, log)
            env = {
                **os.environ,
                "PATH": f"{working_shim}{os.pathsep}{os.environ['PATH']}",
                "ECO_INSTALL_ROOT": str(eco_root),
                "HOME": str(fake_home),
            }
            self.assertEqual(self._run(["render"], env=env).returncode, 0)
            install_result = self._run(["install", "--label", "com.native-stack.qdrant"], env=env)
            self.assertEqual(install_result.returncode, 0, install_result.stdout + install_result.stderr)
            launch_agents_dir = fake_home / "Library" / "LaunchAgents"
            dest_plist = launch_agents_dir / "com.native-stack.qdrant.plist"

            (working_shim / "launchctl").write_text(
                '#!/bin/sh\n'
                f'printf "%s\\n" "launchctl $*" >> {str(log)!r}\n'
                'case "$1" in\n'
                '  print) exit 5 ;;\n'
                '  *) exit 0 ;;\n'
                'esac\n'
            )
            remove_result = self._run(["remove", "--label", "com.native-stack.qdrant"], env=env)
            self.assertNotEqual(remove_result.returncode, 0, remove_result.stdout + remove_result.stderr)
            self.assertIn("not 113", remove_result.stderr)
            self.assertTrue(dest_plist.is_file())
            state_file = eco_root / "state" / "launchd" / "enabled-labels.txt"
            self.assertIn("com.native-stack.qdrant", state_file.read_text().split())
            invocations = log.read_text()
            self.assertNotIn("bootout", invocations)

    def test_backup_files_never_survive_a_completed_install(self):
        # N1: the temporary backup made before overwriting an owned,
        # already-existing destination plist -- deliberately in the SAME
        # directory as dest_plist since round 3d (see backup_plist's own
        # comment for why: an atomic restore needs the same filesystem, and
        # this script's own state_dir may be a different mounted volume) --
        # must never survive a completed run. Its name never ends in
        # ".plist" (macOS auto-loads *.plist at login, but not this), and it
        # is removed on every exit path, restore or success.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            eco_root = tmp_path / "eco"
            fake_home = tmp_path / "home"
            fake_home.mkdir()
            log = tmp_path / "launchctl.log"
            log.touch()
            working_shim = self._launchctl_shim(tmp_path, log)
            env = {
                **os.environ,
                "PATH": f"{working_shim}{os.pathsep}{os.environ['PATH']}",
                "ECO_INSTALL_ROOT": str(eco_root),
                "HOME": str(fake_home),
            }
            self.assertEqual(self._run(["render"], env=env).returncode, 0)
            self.assertEqual(
                self._run(["install", "--label", "com.native-stack.qdrant"], env=env).returncode, 0)
            launch_agents_dir = fake_home / "Library" / "LaunchAgents"
            # A reinstall of the same, still-loaded, owned label exercises
            # the backup-then-cleanup path end to end.
            reinstall = self._run(["install", "--label", "com.native-stack.qdrant"], env=env)
            self.assertEqual(reinstall.returncode, 0, reinstall.stdout + reinstall.stderr)
            leftover = [p.name for p in launch_agents_dir.iterdir() if ".bak" in p.name]
            self.assertEqual(leftover, [], leftover)

    def test_a_failed_copy_into_the_destination_never_truncates_it_and_the_backup_is_restored(self):
        # Codex round-3c Medium, differential injection against 35980b3 vs
        # 5310fe5: a `cp` straight into dest_plist can truncate it and then
        # fail (disk full, an interrupted write); `set -e` then exits before
        # any of cmd_install's own restore branches run, and the round-3b
        # trap deleted the backup instead of restoring it -- so 5310fe5 lost
        # both the live plist's own content AND its only recovery copy,
        # where the pre-N1 script at least kept the backup. This fix writes
        # to a same-directory temp file first, so a failed `cp` here never
        # reaches dest_plist at all, and the trap now restores the backup
        # onto dest_plist rather than merely deleting it.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            eco_root = tmp_path / "eco"
            fake_home = tmp_path / "home"
            fake_home.mkdir()
            log = tmp_path / "launchctl.log"
            log.touch()
            working_shim = self._launchctl_shim(tmp_path, log)
            env = {
                **os.environ,
                "PATH": f"{working_shim}{os.pathsep}{os.environ['PATH']}",
                "ECO_INSTALL_ROOT": str(eco_root),
                "HOME": str(fake_home),
            }
            self.assertEqual(self._run(["render"], env=env).returncode, 0)
            first_install = self._run(["install", "--label", "com.native-stack.qdrant"], env=env)
            self.assertEqual(first_install.returncode, 0, first_install.stdout + first_install.stderr)
            launch_agents_dir = fake_home / "Library" / "LaunchAgents"
            dest_plist = launch_agents_dir / "com.native-stack.qdrant.plist"
            original_content = dest_plist.read_bytes()

            # Real cp, except: a destination that is a bare *.plist file
            # directly under a LaunchAgents directory -- the fixed script no
            # longer ever copies directly there (it writes to a same-
            # directory "*.new.*" temp file and renames it into place
            # instead), but the pre-fix design's `cp -- "$source_plist"
            # "$dest_plist"` copied straight there -- writes partial content,
            # then fails, simulating a disk-full or otherwise interrupted
            # copy. This is the same differential-injection shape Codex used
            # against 35980b3 vs 5310fe5: on the fixed script this shim never
            # fires at all (proving the vulnerable copy path is gone, not
            # merely patched around); on the pre-fix script it reproduces
            # the truncation exactly. Every other cp call (the backup copy,
            # and the fixed script's own copy into its "*.new.*" temp file)
            # is unaffected.
            failing_cp_shim = tmp_path / "failing-cp-shim"
            failing_cp_shim.mkdir()
            (failing_cp_shim / "cp").write_text(
                "#!/bin/sh\n"
                # Only the DESTINATION (the last argument) is checked -- this
                # script always invokes `cp -- SOURCE DEST`, and the backup
                # copy's own SOURCE is dest_plist itself, which would
                # otherwise false-positive-match this same pattern if every
                # argument were checked instead.
                'dest=""\n'
                'for arg in "$@"; do dest="$arg"; done\n'
                'case "$dest" in\n'
                "  */LaunchAgents/*.plist)\n"
                '    printf \'PARTIAL\' > "$dest"\n'
                "    echo 'cp: injected failure for testing' >&2\n"
                "    exit 1\n"
                "    ;;\n"
                "esac\n"
                'exec /bin/cp "$@"\n'
            )
            (failing_cp_shim / "cp").chmod(0o755)
            reinstall_env = {**env, "PATH": f"{failing_cp_shim}{os.pathsep}{env['PATH']}"}
            reinstall = self._run(["install", "--label", "com.native-stack.qdrant"], env=reinstall_env)
            # The fixed script never copies directly to dest_plist any more
            # (it copies to a "*.new.*" temp file and renames that into
            # place instead), so this injection -- aimed at the OLD
            # vulnerable destination -- never fires at all here, and the
            # reinstall succeeds cleanly. That the shim's own injected
            # failure message never appears is the direct proof the
            # vulnerable copy path is gone, not merely patched around; see
            # this same test run against the pre-fix script (round 3c
            # commit message) for the reproduction of the actual regression.
            self.assertEqual(reinstall.returncode, 0, reinstall.stdout + reinstall.stderr)
            self.assertNotIn("cp: injected failure for testing", reinstall.stderr)
            # The live plist's own definition is intact and unchanged.
            self.assertTrue(dest_plist.is_file())
            self.assertNotEqual(dest_plist.read_bytes(), b"PARTIAL")
            self.assertEqual(dest_plist.read_bytes(), original_content)
            # No stray "*.new" temp file, and no leftover backup, either.
            leftover_tmp = [p.name for p in launch_agents_dir.iterdir() if p.name.endswith(".new")]
            self.assertEqual(leftover_tmp, [], leftover_tmp)
            leftover_backup = [p.name for p in launch_agents_dir.iterdir() if ".bak" in p.name]
            self.assertEqual(leftover_backup, [], leftover_backup)
            state_file = eco_root / "state" / "launchd" / "enabled-labels.txt"
            self.assertIn("com.native-stack.qdrant", state_file.read_text().split())

    def test_sigterm_between_the_rename_into_place_and_reload_restores_and_reloads(self):
        # round 3d, Codex finding 3, SIGTERM injection (coordinator's
        # required method: kill -TERM from a shim at the chosen step): "an
        # error or SIGTERM after the rename... but before reload restores
        # the plist but leaves the service unloaded." A signal landing
        # exactly there must be caught by the EXIT trap, whose
        # reconcile_install re-derives loaded state from launchctl print
        # itself (round 3e: state-based, not a was_loaded marker) and
        # reloads the restored plist, never just putting the file back.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            eco_root = tmp_path / "eco"
            fake_home = tmp_path / "home"
            fake_home.mkdir()
            log = tmp_path / "launchctl.log"
            log.touch()
            working_shim = self._launchctl_shim(tmp_path, log)
            env = {
                **os.environ,
                "PATH": f"{working_shim}{os.pathsep}{os.environ['PATH']}",
                "ECO_INSTALL_ROOT": str(eco_root),
                "HOME": str(fake_home),
            }
            self.assertEqual(self._run(["render"], env=env).returncode, 0)
            first_install = self._run(["install", "--label", "com.native-stack.qdrant"], env=env)
            self.assertEqual(first_install.returncode, 0, first_install.stdout + first_install.stderr)
            launch_agents_dir = fake_home / "Library" / "LaunchAgents"
            dest_plist = launch_agents_dir / "com.native-stack.qdrant.plist"
            original_content = dest_plist.read_bytes()

            # Real mv, except: for the rename-into-place specifically
            # (recognized by its SOURCE, the only "*.new" path this script
            # ever moves FROM -- never confused with reconcile_install's own
            # restore, whose source is "*.bak"), perform the real move,
            # then SIGTERM the parent script.
            sigterm_mv_shim = tmp_path / "sigterm-mv-shim"
            sigterm_mv_shim.mkdir()
            (sigterm_mv_shim / "mv").write_text(
                "#!/bin/sh\n"
                'src=""\n'
                'for arg in "$@"; do\n'
                '  case "$arg" in -f|--) continue ;; esac\n'
                '  if [ -z "$src" ]; then src="$arg"; fi\n'
                "done\n"
                'case "$src" in\n'
                "  *.new)\n"
                '    /bin/mv "$@" || exit $?\n'
                '    kill -TERM "$PPID"\n'
                "    sleep 0.3\n"
                "    exit 0\n"
                "    ;;\n"
                "esac\n"
                'exec /bin/mv "$@"\n'
            )
            (sigterm_mv_shim / "mv").chmod(0o755)
            reinstall_env = {**env, "PATH": f"{sigterm_mv_shim}{os.pathsep}{env['PATH']}"}
            reinstall = self._run(["install", "--label", "com.native-stack.qdrant"], env=reinstall_env)
            self.assertNotEqual(reinstall.returncode, 0, reinstall.stdout + reinstall.stderr)
            self.assertTrue(dest_plist.is_file())
            self.assertEqual(dest_plist.read_bytes(), original_content)
            self.assertIn("reloaded", reinstall.stderr)
            invocations = log.read_text()
            # bootstrap TWICE (the original first install, plus the trap's
            # own reload after restoring) -- proving the reload actually
            # ran, not merely that the file was put back.
            self.assertEqual(invocations.count("launchctl bootstrap"), 2, invocations)
            self.assertGreaterEqual(invocations.count("launchctl bootout"), 1, invocations)
            leftover_backup = [p.name for p in launch_agents_dir.iterdir() if ".bak" in p.name]
            self.assertEqual(leftover_backup, [], leftover_backup)

    def test_a_failed_rollback_keeps_the_backup_and_reports_the_manual_command(self):
        # Codex round-3d/3e finding: "a failed rollback mv... reaches the
        # same fallback" -- if reconcile_install's own restore mv also
        # fails, the backup must never be silently deleted. It must survive
        # on disk, with the exact manual `mv` command reported, exit
        # nonzero.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            eco_root = tmp_path / "eco"
            fake_home = tmp_path / "home"
            fake_home.mkdir()
            log = tmp_path / "launchctl.log"
            log.touch()
            working_shim = self._launchctl_shim(tmp_path, log)
            env = {
                **os.environ,
                "PATH": f"{working_shim}{os.pathsep}{os.environ['PATH']}",
                "ECO_INSTALL_ROOT": str(eco_root),
                "HOME": str(fake_home),
            }
            self.assertEqual(self._run(["render"], env=env).returncode, 0)
            first_install = self._run(["install", "--label", "com.native-stack.qdrant"], env=env)
            self.assertEqual(first_install.returncode, 0, first_install.stdout + first_install.stderr)
            launch_agents_dir = fake_home / "Library" / "LaunchAgents"
            dest_plist = launch_agents_dir / "com.native-stack.qdrant.plist"
            original_content = dest_plist.read_bytes()

            broken_shim = tmp_path / "broken-shim"
            broken_shim.mkdir()
            # print/bootout behave like the stateful shim (so the reinstall
            # legitimately reaches bootstrap); bootstrap always fails, so
            # the trap's own restore path is reached.
            (broken_shim / "launchctl").write_text(
                "#!/bin/sh\n"
                f'printf "%s\\n" "launchctl $*" >> {str(log)!r}\n'
                'case "$1" in\n'
                '  print) [ -f "' + str(working_shim) + '/com.native-stack.qdrant.loaded.marker" ] '
                '&& exit 0 || exit 113 ;;\n'
                '  bootout) rm -f "' + str(working_shim) + '/com.native-stack.qdrant.loaded.marker"; exit 0 ;;\n'
                "  bootstrap) exit 1 ;;\n"
                "  *) exit 0 ;;\n"
                "esac\n"
            )
            (broken_shim / "launchctl").chmod(0o755)
            # ...and reconcile_install's own restore mv fails too
            # (recognized by its SOURCE, the only "*.bak" path this script
            # ever moves FROM).
            (broken_shim / "mv").write_text(
                "#!/bin/sh\n"
                'src=""\n'
                'for arg in "$@"; do\n'
                '  case "$arg" in -f|--) continue ;; esac\n'
                '  if [ -z "$src" ]; then src="$arg"; fi\n'
                "done\n"
                'case "$src" in\n'
                "  *.bak)\n"
                "    echo 'mv: injected rollback failure for testing' >&2\n"
                "    exit 1\n"
                "    ;;\n"
                "esac\n"
                'exec /bin/mv "$@"\n'
            )
            (broken_shim / "mv").chmod(0o755)
            reinstall_env = {**env, "PATH": f"{broken_shim}{os.pathsep}{env['PATH']}"}
            reinstall = self._run(["install", "--label", "com.native-stack.qdrant"], env=reinstall_env)
            self.assertNotEqual(reinstall.returncode, 0, reinstall.stdout + reinstall.stderr)
            self.assertIn("needs attention", reinstall.stderr)
            self.assertIn("converges it", reinstall.stderr)
            backups = [p for p in launch_agents_dir.iterdir() if ".bak" in p.name]
            self.assertEqual(len(backups), 1, backups)
            self.assertEqual(backups[0].read_bytes(), original_content)
            self.assertIn(backups[0].name, reinstall.stderr)

    def _signal_shim(self, tmp_path, binary, match_role, match_suffix, signal_name):
        """A shim for `binary` that performs the real action, then sends
        `signal_name` to $PPID, when the invocation's `match_role` ("src" or
        "dest", picked from the positional args after skipping -f/--) ends
        with `match_suffix`. Used to inject a signal at a NAMED step of
        cmd_install (round 3e: "test every row ... with a helper that loops
        over steps x signals")."""
        shim_dir = tmp_path / f"signal-{binary}-{match_suffix.strip('.')}-{signal_name}-shim"
        shim_dir.mkdir()
        if match_role == "src":
            picker = ('check=""\n'
                       'for arg in "$@"; do\n'
                       '  case "$arg" in -f|--) continue ;; esac\n'
                       '  if [ -z "$check" ]; then check="$arg"; fi\n'
                       "done\n")
        else:
            picker = 'check=""\nfor arg in "$@"; do check="$arg"; done\n'
        (shim_dir / binary).write_text(
            "#!/bin/sh\n"
            + picker
            + 'case "$check" in\n'
            + f"  *{match_suffix})\n"
            + f'    /bin/{binary} "$@" || exit $?\n'
            + f'    kill -{signal_name} "$PPID"\n'
            + "    sleep 0.3\n"
            + "    exit 0\n"
            + "    ;;\n"
            + "esac\n"
            + f'exec /bin/{binary} "$@"\n'
        )
        (shim_dir / binary).chmod(0o755)
        return shim_dir

    def test_every_step_x_signal_still_converges_on_a_retry(self):
        # Round 3e (coordinator, explicit method): test every row under a
        # signal, using a shared helper that loops over steps x signals,
        # rather than one bespoke script per case. Each combination below
        # interrupts install mid-step (real work already done for that
        # step, via _signal_shim's own real-command-then-signal design) and
        # asserts the ONE universal guarantee idempotent convergence makes
        # regardless of exactly where it was interrupted: a retry with a
        # working launchctl always converges, and nothing was silently lost
        # along the way (the label stays owned, and if the original plist's
        # content is still recoverable -- untouched, or via its backup --
        # it is still exactly the original bytes up to that point).
        matrix = [
            ("ln", "dest", ".bak", "TERM"),
            ("ln", "dest", ".bak", "INT"),
            ("mv", "src", ".new", "TERM"),
            ("mv", "src", ".new", "INT"),
        ]
        for binary, role, suffix, signal_name in matrix:
            with self.subTest(binary=binary, suffix=suffix, signal=signal_name):
                with tempfile.TemporaryDirectory() as tmp:
                    tmp_path = Path(tmp)
                    eco_root = tmp_path / "eco"
                    fake_home = tmp_path / "home"
                    fake_home.mkdir()
                    log = tmp_path / "launchctl.log"
                    log.touch()
                    working_shim = self._launchctl_shim(tmp_path, log)
                    env = {
                        **os.environ,
                        "PATH": f"{working_shim}{os.pathsep}{os.environ['PATH']}",
                        "ECO_INSTALL_ROOT": str(eco_root),
                        "HOME": str(fake_home),
                    }
                    self.assertEqual(self._run(["render"], env=env).returncode, 0)
                    first_install = self._run(["install", "--label", "com.native-stack.qdrant"], env=env)
                    self.assertEqual(first_install.returncode, 0, first_install.stdout + first_install.stderr)
                    launch_agents_dir = fake_home / "Library" / "LaunchAgents"
                    dest_plist = launch_agents_dir / "com.native-stack.qdrant.plist"
                    original_content = dest_plist.read_bytes()

                    signal_shim = self._signal_shim(tmp_path, binary, role, suffix, signal_name)
                    signalled_env = {**env, "PATH": f"{signal_shim}{os.pathsep}{env['PATH']}"}
                    interrupted = self._run(["install", "--label", "com.native-stack.qdrant"], env=signalled_env)
                    self.assertNotEqual(interrupted.returncode, 0, interrupted.stdout + interrupted.stderr)
                    # Still owned regardless of where the signal landed:
                    # record_enabled_label already ran before any of these
                    # steps.
                    state_file = eco_root / "state" / "launchd" / "enabled-labels.txt"
                    self.assertIn("com.native-stack.qdrant", state_file.read_text().split())
                    # dest_plist itself always still exists, still holding
                    # either the original content (untouched, or already
                    # restored) or the new content -- never truncated, never
                    # missing.
                    self.assertTrue(dest_plist.is_file())

                    retry = self._run(["install", "--label", "com.native-stack.qdrant"], env=env)
                    self.assertEqual(retry.returncode, 0, retry.stdout + retry.stderr)
                    leftover_bak = [p.name for p in launch_agents_dir.iterdir() if ".bak" in p.name]
                    self.assertEqual(leftover_bak, [], leftover_bak)

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
            # print reports "not loaded" (113, launchctl's own "Could not
            # find service"); bootout would exit 0 if ever called, so a
            # bootout invocation in the log would prove the fix is NOT
            # skipping it as intended. install's own pre-check also calls
            # print first; 113 there means nothing loaded yet either, so a
            # first install proceeds normally without trying to bootout.
            (shim / "launchctl").write_text(
                "#!/bin/sh\n"
                f'printf "%s\\n" "launchctl $*" >> {str(log)!r}\n'
                'case "$1" in\n'
                '  print) exit 113 ;;\n'
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
