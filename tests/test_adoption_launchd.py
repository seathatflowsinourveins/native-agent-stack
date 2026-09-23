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
    "EMBED_MODEL_PATH": "/Users/example/.local/share/codex-ecosystem/state/models/embeddinggemma-300M-Q8_0.gguf",
}


def templates() -> dict[str, Path]:
    return {
        path.name[: -len(TEMPLATE_SUFFIX)] + ".plist": path
        for path in sorted(LAUNCHD_DIR.glob(f"*{TEMPLATE_SUFFIX}"))
    }


def _shell_functions(text: str, *names: str) -> str:
    """The source of top-level shell functions, from `name() {` to its `}`.

    Same helper (and the same regex) as tests/test_adoption_bootstrap_macos.py's
    own `_shell_functions`: used here to SCOPE a structural assertion to one
    function's body, so a pattern that happens to also match some OTHER
    function's near-identical code (cmd_remove's own `is_enabled_label`/
    `launchctl print` gate looks a lot like cmd_install's, for one) cannot
    silently satisfy an assertion meant for cmd_install alone.
    """
    blocks = []
    for name in names:
        match = re.search(rf"(?ms)^{re.escape(name)}\(\) \{{\n.*?^\}}\n", text)
        assert match, f"function {name} not found"
        blocks.append(match.group(0))
    return "".join(blocks)


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

    def test_llama_embed_names_the_model_file_via_m_flag(self):
        # Round 3h (2026-09-23 readiness audit defect): the template used to
        # run llama-server with no model argument at all -- KeepAlive would
        # restart it in a loop forever, never actually serving embeddings.
        rendered = string.Template(self.templates["com.native-stack.llama-embed.plist"].read_text()) \
            .substitute(FIXTURE_VALUES)
        data = plistlib.loads(rendered.encode("utf-8"))
        arguments = data["ProgramArguments"]
        self.assertIn("-m", arguments)
        self.assertEqual(arguments[arguments.index("-m") + 1], FIXTURE_VALUES["EMBED_MODEL_PATH"])
        self.assertTrue(arguments[arguments.index("-m") + 1].endswith("embeddinggemma-300M-Q8_0.gguf"))

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
                 "--set", "AI_MEMORY_URL=127.0.0.1:49374",
                 "--set", "EMBED_MODEL_PATH=/Volumes/R&D/eco/state/models/embeddinggemma-300M-Q8_0.gguf"],
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
                 "--set", "AI_MEMORY_URL=127.0.0.1:49374",
                 "--set", "EMBED_MODEL_PATH=/Users/example/.local/share/codex-ecosystem/state/models/embeddinggemma-300M-Q8_0.gguf"],
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

    def test_no_ownership_file_or_transactional_backup_machinery_remains(self):
        # Round 3g: converges on brew-services' stateless model (Homebrew/
        # brew Library/Homebrew/services/cli.rb @ 8e3a5dc0a7) -- no backup,
        # no rollback, no ownership file. Five rounds (3b-3f) of a
        # transactional backup/reconcile design each produced a NEW
        # recovery defect; this asserts none of that machinery -- or the
        # concepts it depended on -- survives the rewrite as actual CODE
        # (comment lines are allowed to name them historically, e.g. this
        # very design note above explaining what is gone and why).
        code_only = "\n".join(
            line for line in self.text.splitlines() if not line.strip().startswith("#")
        )
        for gone in (
            "record_enabled_label", "is_enabled_label", "forget_enabled_label",
            "enabled_state_file", "reconcile_install", "was_already_enabled",
            "backup_plist", "current_install_bootout_pending", "current_install_label",
            ".bak",
        ):
            self.assertNotIn(gone, code_only, gone)

    def test_install_and_remove_both_check_launchctl_label_state_before_any_destructive_action(self):
        install_body = _shell_functions(self.text, "cmd_install")
        remove_body = _shell_functions(self.text, "cmd_remove")
        for body, label in ((install_body, "cmd_install"), (remove_body, "cmd_remove")):
            self.assertIn('launchctl_label_state "$label" "$dest_plist"', body, label)
            # The state check's own result must be branched on BEFORE any
            # "launchctl bootout" call appears later in the same body.
            state_call = body.index('launchctl_label_state "$label" "$dest_plist"')
            first_bootout = body.find("launchctl bootout")
            self.assertGreater(first_bootout, state_call, label)

    def _refusal_case_arms(self, body: str) -> tuple[str, str]:
        elsewhere_match = re.search(r"(?ms)^\s*loaded_elsewhere\)\n(.*?)\n\s*;;", body)
        unknown_match = re.search(r"(?ms)^\s*unknown\)\n(.*?)\n\s*;;", body)
        self.assertIsNotNone(elsewhere_match, "no loaded_elsewhere case arm")
        self.assertIsNotNone(unknown_match, "no unknown case arm")
        return elsewhere_match.group(1), unknown_match.group(1)

    def test_install_refuses_on_loaded_elsewhere_and_unknown_without_bootout(self):
        # Round 3g stateless-ownership rule, structural: install must
        # refuse outright -- never bootout, never rename, never bootstrap
        # -- on loaded_elsewhere or unknown. Scoped to cmd_install's OWN
        # body (the same _shell_functions helper test_adoption_bootstrap_
        # macos.py already uses) so this can never be satisfied by
        # cmd_remove's textually similar gate instead.
        body = _shell_functions(self.text, "cmd_install")
        elsewhere, unknown = self._refusal_case_arms(body)
        for arm, name in ((elsewhere, "loaded_elsewhere"), (unknown, "unknown")):
            self.assertIn("Refusing to install", arm, name)
            self.assertIn("exit 1", arm, name)
            self.assertNotIn("launchctl bootout", arm, name)
            self.assertNotIn("mv -f", arm, name)
            self.assertNotIn("launchctl bootstrap", arm, name)

    def test_remove_refuses_on_loaded_elsewhere_and_unknown_without_bootout(self):
        # Round 3f finding 1 (fixed here): remove must never bootout or
        # delete anything on loaded_elsewhere or unknown, only on a
        # path-verified loaded_here (or not_found with a file to clean up).
        body = _shell_functions(self.text, "cmd_remove")
        elsewhere, unknown = self._refusal_case_arms(body)
        for arm, name in ((elsewhere, "loaded_elsewhere"), (unknown, "unknown")):
            self.assertIn("refusing to remove", arm, name)
            self.assertNotIn("launchctl bootout", arm, name)
            self.assertNotIn("rm -f", arm, name)

    def test_int_term_hup_are_trapped_to_defer_to_a_completed_step(self):
        # Explicitly trapping INT/TERM/HUP -- not leaving them at their
        # default disposition -- makes bash defer acting on a caught signal
        # until the current foreign command finishes, so the EXIT handler
        # (cleanup) never observes a step still in flight.
        self.assertIn("trap 'exit 130' INT", self.text)
        self.assertIn("trap 'exit 143' TERM", self.text)
        self.assertIn("trap 'exit 129' HUP", self.text)

    def test_exit_trap_only_removes_the_current_temp_file(self):
        # Round 3g: there is no reconcile logic left to run as the EXIT
        # trap -- only cleaning up this run's own still-inert temp file,
        # cleared the moment the rename that would make it live succeeds.
        self.assertIn("trap cleanup EXIT", self.text)
        cleanup_body = _shell_functions(self.text, "cleanup")
        self.assertIn('rm -f -- "$current_temp_file"', cleanup_body)
        self.assertNotIn("launchctl", cleanup_body)
        self.assertNotIn("mv", cleanup_body)

    def test_install_treats_only_exit_113_as_confidently_unloaded(self):
        # launchctl_label_state's own tri-state print: any launchctl print
        # exit other than 0 (loaded) or 113 (not found) is "unknown", never
        # silently treated as "not loaded".
        self.assertIn("launchctl_label_state()", self.text)
        self.assertIn('if [[ "$print_status" == 113 ]]; then', self.text)
        self.assertIn("printf 'not_found\\n'", self.text)
        self.assertIn("printf 'unknown\\n'", self.text)

    def test_install_waits_for_unloaded_after_a_successful_bootout(self):
        # Round 3i: the wait now lives in the shared bootout_and_wait
        # helper (also absorbing EINPROGRESS), called from cmd_install's
        # own body rather than polling inline.
        body = _shell_functions(self.text, "cmd_install")
        self.assertIn("bootout_and_wait", body)
        self.assertIn("wait_until_unloaded", _shell_functions(self.text, "bootout_and_wait"))

    def test_remove_waits_for_unloaded_after_a_successful_bootout(self):
        body = _shell_functions(self.text, "cmd_remove")
        self.assertIn("bootout_and_wait", body)
        self.assertIn("wait_until_unloaded", _shell_functions(self.text, "bootout_and_wait"))

    def test_bootout_and_wait_absorbs_einprogress_instead_of_refusing_outright(self):
        # Round 3i (Codex Medium): the pinned Homebrew cli.rb @ 8e3a5dc0a7
        # retries on Errno::EINPROGRESS (Darwin 36) rather than treating it
        # as a bootout failure; bootout_and_wait must do the same, not
        # refuse on any nonzero bootout exit unconditionally.
        body = _shell_functions(self.text, "bootout_and_wait")
        self.assertIn('"$bootout_status" != 36', body)
        # Never uses a command substitution to call itself out -- a global
        # result variable, so a signal during launchctl bootout is never
        # swallowed by a subshell (verified empirically; see the function's
        # own comment, which names the avoided pattern only in prose).
        code_only = "\n".join(
            line for line in self.text.splitlines() if not line.strip().startswith("#")
        )
        self.assertNotIn("$(bootout_and_wait", code_only)

    def test_remove_deletes_only_the_labels_own_plist_never_component_data_or_logs(self):
        # Every `rm` in the script targets exactly the copied unit-
        # definition file this script itself placed under
        # ~/Library/LaunchAgents, or (cleanup's own, EXIT-trap-only rm) the
        # current run's own inert temp file; none may ever target
        # state/logs, state/qdrant, or any bookkeeping file (there is none
        # left to protect specifically, but the absence is itself asserted
        # by test_no_ownership_file_or_transactional_backup_machinery_
        # remains above).
        self.assertNotIn("rm -rf", self.text)
        rm_lines = [
            line.strip() for line in self.text.splitlines()
            if not line.strip().startswith("#") and re.search(r"\brm\b", line)
        ]
        self.assertGreaterEqual(len(rm_lines), 1, rm_lines)
        allowed_targets = (
            'rm -f -- "$dest_plist"',
            'rm -f -- "$current_temp_file"',
        )
        for rm_line in rm_lines:
            self.assertTrue(any(target in rm_line for target in allowed_targets), rm_line)
            for forbidden in ("state/logs", "state/qdrant"):
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
        # bootstrap "loads" the label its plist path names, storing that
        # exact path in the marker file's own content; print reports loaded
        # (0), with a "path = <that path>" line matching real launchctl's
        # own output (launchctl_label_state parses this to distinguish a
        # label loaded from dest_plist itself from one loaded from
        # somewhere else), once that label's marker exists, else 113
        # ("Could not find service"); bootout always succeeds and clears
        # the marker; enable always succeeds (falls through to the `*`
        # case). install's and remove's own pre-action state check rely on
        # this to tell a genuine first install (nothing loaded yet) from a
        # reinstall/removal of an already-loaded label.
        shim = directory / "shim"
        shim.mkdir(exist_ok=True)
        (shim / "launchctl").write_text(
            '#!/bin/sh\n'
            f'printf "%s\\n" "launchctl $*" >> {str(log)!r}\n'
            'case "$1" in\n'
            '  bootstrap)\n'
            '    label="$(basename "$3" .plist)"\n'
            f'    echo "$3" > "{shim!s}/$label.loaded.marker"\n'
            '    exit 0 ;;\n'
            '  print)\n'
            '    label="$(basename "$2")"\n'
            f'    if [ -f "{shim!s}/$label.loaded.marker" ]; then\n'
            f'      echo "path = $(cat "{shim!s}/$label.loaded.marker")"\n'
            '      exit 0\n'
            '    else\n'
            '      exit 113\n'
            '    fi ;;\n'
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
            # No stray "*.new.<pid>" temp file left behind by a completed install.
            leftover_temp = [p.name for p in launch_agents_dir.iterdir() if ".new." in p.name]
            self.assertEqual(leftover_temp, [], leftover_temp)

            # An explicit --label still installs llama-embed even though the
            # default set skips it.
            explicit_install = self._run(["install", "--label", "com.native-stack.llama-embed"], env=env)
            self.assertEqual(explicit_install.returncode, 0, explicit_install.stdout + explicit_install.stderr)
            self.assertTrue((launch_agents_dir / "com.native-stack.llama-embed.plist").is_file())

            # Reinstalling an already-loaded label unloads it first, then
            # loads the fresh content (brew-services semantics: no
            # ownership check on the pre-existing file, only on whether the
            # LABEL is currently loaded).
            reinstall = self._run(["install", "--label", "com.native-stack.qdrant"], env=env)
            self.assertEqual(reinstall.returncode, 0, reinstall.stdout + reinstall.stderr)

            status_result = self._run(["status", "--label", "com.native-stack.qdrant"], env=env)
            self.assertEqual(status_result.returncode, 0, status_result.stdout + status_result.stderr)
            self.assertIn("path =", status_result.stdout)

            remove_result = self._run(["remove", "--label", "com.native-stack.qdrant"], env=env)
            self.assertEqual(remove_result.returncode, 0, remove_result.stdout + remove_result.stderr)
            self.assertIn("Booted out 1 label(s); skipped 0", remove_result.stdout)
            # A successful bootout deletes the copied plist (so it cannot
            # reload at the next login); it never touches component data or
            # logs (state/logs, state/qdrant are untouched, still directories).
            self.assertFalse((launch_agents_dir / "com.native-stack.qdrant.plist").exists())
            self.assertTrue((eco_root / "state" / "logs").is_dir())
            self.assertTrue((eco_root / "state" / "qdrant").is_dir())

            # A second remove of the same, now-absent label is a no-op skip.
            second_remove = self._run(["remove", "--label", "com.native-stack.qdrant"], env=env)
            self.assertEqual(second_remove.returncode, 0, second_remove.stdout + second_remove.stderr)
            self.assertIn("does not exist; nothing to do", second_remove.stdout)
            self.assertIn("Booted out 0 label(s); skipped 1", second_remove.stdout)

    def test_remove_keeps_the_plist_when_bootout_fails(self):
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
            # always fails.
            (failing_shim / "launchctl").write_text(
                '#!/bin/sh\n'
                'case "$1" in\n'
                '  bootstrap)\n'
                '    label="$(basename "$3" .plist)"\n'
                '    echo "$3" > "$(dirname "$0")/$label.loaded.marker"\n'
                '    exit 0 ;;\n'
                '  print)\n'
                '    label="$(basename "$2")"\n'
                '    if [ -f "$(dirname "$0")/$label.loaded.marker" ]; then\n'
                '      echo "path = $(cat "$(dirname "$0")/$label.loaded.marker")"\n'
                '      exit 0\n'
                '    else\n'
                '      exit 113\n'
                '    fi ;;\n'
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
            self.assertIn("was NOT removed", remove_result.stderr)
            # The plist survives a failed bootout, so a retry (with a
            # working launchctl) can find and finish the job.
            self.assertTrue((launch_agents_dir / "com.native-stack.qdrant.plist").is_file())

    def test_install_leaves_the_new_plist_in_place_unloaded_when_bootstrap_persistently_fails_and_a_retry_converges(self):
        # Round 3g: no backup, no rollback (brew services does not roll
        # back either) -- a persistently failing bootstrap leaves the new
        # plist ON DISK, unloaded, with the exact recovery commands printed,
        # rather than deleting it (the pre-round-3g design's own "removed
        # the unconfirmed plist" behavior) or trying to restore something
        # that no longer exists to restore.
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
            self.assertIn("Failed to bootstrap", install_result.stderr)
            self.assertIn("the new plist is in place but not loaded", install_result.stderr)
            self.assertIn('install --label com.native-stack.qdrant', install_result.stderr)
            self.assertIn('remove --label com.native-stack.qdrant', install_result.stderr)
            launch_agents_dir = fake_home / "Library" / "LaunchAgents"
            self.assertTrue((launch_agents_dir / "com.native-stack.qdrant.plist").is_file(),
                             "the new plist stays on disk even though bootstrap never succeeded")
            leftover_temp = [p.name for p in launch_agents_dir.iterdir() if ".new." in p.name]
            self.assertEqual(leftover_temp, [], leftover_temp)

            # A retry with a working launchctl converges cleanly: the
            # rename simply overwrites the same, already-current content.
            working_shim = self._launchctl_shim(tmp_path, tmp_path / "working-launchctl.log")
            working_env = {**env, "PATH": f"{working_shim}{os.pathsep}{os.environ['PATH']}"}
            retry = self._run(["install", "--label", "com.native-stack.qdrant"], env=working_env)
            self.assertEqual(retry.returncode, 0, retry.stdout + retry.stderr)

    def test_reinstalling_an_already_loaded_label_unloads_it_first_then_bootstraps_the_new_content(self):
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

            reinstall = self._run(["install", "--label", "com.native-stack.qdrant"], env=env)
            self.assertEqual(reinstall.returncode, 0, reinstall.stdout + reinstall.stderr)
            invocations = log.read_text()
            self.assertIn("launchctl bootout", invocations)
            self.assertEqual(invocations.count("launchctl bootstrap"), 2, invocations)


    def test_install_never_boots_out_a_label_loaded_from_elsewhere(self):
        # Round 3g stateless-ownership rule, named test (loaded_elsewhere
        # refused by install): a fresh install attempt for a label that is
        # currently loaded from some OTHER path entirely must refuse
        # outright and never call bootout, regardless of whether a
        # destination plist exists yet.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            eco_root = tmp_path / "eco"
            fake_home = tmp_path / "home"
            fake_home.mkdir()
            log = tmp_path / "launchctl.log"
            log.touch()
            unrelated_plist = tmp_path / "unrelated" / "com.native-stack.qdrant.plist"
            unrelated_plist.parent.mkdir(parents=True)
            unrelated_plist.write_text("<plist>unrelated service, not ours</plist>")
            shim = tmp_path / "shim"
            shim.mkdir()
            (shim / "launchctl").write_text(
                "#!/bin/sh\n"
                f'printf "%s\\n" "launchctl $*" >> {str(log)!r}\n'
                'case "$1" in\n'
                f'  print) echo "path = {unrelated_plist}"; exit 0 ;;\n'
                "  bootstrap) exit 5 ;;\n"
                "  bootout) exit 0 ;;\n"
                "  *) exit 0 ;;\n"
                "esac\n"
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
            self.assertIn("it is loaded from somewhere other than", install_result.stderr)
            launch_agents_dir = fake_home / "Library" / "LaunchAgents"
            self.assertFalse((launch_agents_dir / "com.native-stack.qdrant.plist").exists())
            invocations = log.read_text()
            self.assertNotIn("bootout", invocations,
                              "install must never bootout a label loaded from elsewhere")
            self.assertTrue(unrelated_plist.is_file(), "the unrelated service's own plist is never touched")

            # A second invocation refuses identically -- there is no
            # ownership state that could make a LATER run behave
            # differently from the first.
            second_install = self._run(["install", "--label", "com.native-stack.qdrant"], env=env)
            self.assertNotEqual(second_install.returncode, 0, second_install.stdout + second_install.stderr)
            self.assertNotIn("bootout", log.read_text())

    def test_install_refuses_when_print_fails_with_neither_loaded_nor_not_found(self):
        # Round 3g stateless-ownership rule, named test (unknown touches
        # nothing, install side): only launchctl print exit 113 is
        # confidently "not loaded"; any other failure must refuse rather
        # than silently assume "not loaded" and bootstrap over state print
        # could not determine.
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
            self.assertIn("did not confidently report loaded, not-found, or a matching path", reinstall.stderr)
            invocations = log.read_text()
            self.assertNotIn("bootout", invocations)
            # Nothing was touched: the original, still-present plist
            # survives untouched (the refusal happens before the rename).
            self.assertTrue(dest_plist.is_file())
            self.assertEqual(dest_plist.read_bytes(), original_content)
            leftover_temp = [p.name for p in launch_agents_dir.iterdir() if ".new." in p.name]
            self.assertEqual(leftover_temp, [], leftover_temp)

    def test_install_refuses_when_bootout_succeeds_but_the_service_never_reports_unloaded(self):
        # On real launchd, bootout can return before teardown finishes.
        # install must poll launchctl print for a bounded time and refuse
        # -- never bootstrap over a service that never actually stopped --
        # rather than trust bootout's own exit code alone.
        # WAIT_UNTIL_UNLOADED_ATTEMPTS/_INTERVAL are overridden here so the
        # bounded wait this exercises costs no real wall-clock time.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            eco_root = tmp_path / "eco"
            fake_home = tmp_path / "home"
            fake_home.mkdir()
            log = tmp_path / "launchctl.log"
            log.touch()
            shim = tmp_path / "shim"
            shim.mkdir()
            dest_plist_path = fake_home / "Library" / "LaunchAgents" / "com.native-stack.qdrant.plist"
            # print reports not_found until dest_plist actually exists on
            # disk (so the FIRST install, before anything is installed,
            # proceeds normally), then loaded from dest_plist's own path
            # forever after (launchctl_label_state must confirm loaded_here
            # for the bootout gate to be reached at all); bootout exits 0
            # but never actually removes the file, simulating teardown that
            # has not actually finished.
            (shim / "launchctl").write_text(
                "#!/bin/sh\n"
                f'printf "%s\\n" "launchctl $*" >> {str(log)!r}\n'
                'case "$1" in\n'
                f'  print) if [ -e {str(dest_plist_path)!r} ]; then echo "path = {dest_plist_path}"; exit 0; else exit 113; fi ;;\n'
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
            # Refused before the rename: the original plist survives.
            self.assertTrue(dest_plist.is_file())
            self.assertEqual(dest_plist.read_bytes(), original_content)

    def test_remove_refuses_when_it_is_loaded_from_elsewhere(self):
        # Round 3g stateless-ownership rule, named test (loaded_elsewhere
        # refused by remove) AND Codex's own round-3f finding 1
        # reproduction: a previously installed label's plist is on disk,
        # and its label is now loaded from a COMPLETELY DIFFERENT path (an
        # unrelated service took it over). The pre-round-3g design
        # (historical ownership plus an unchecked successful print) booted
        # the unrelated service out and deleted the destination file; the
        # fix shares the exact same path-verified launchctl_label_state
        # check install uses, so remove refuses identically: exit != 0,
        # the unrelated service is never booted out, and dest_plist
        # survives untouched.
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

            # The label is now loaded from a DIFFERENT path entirely -- an
            # unrelated service took it over (Codex's exact reproduction
            # shape: "a previously owned label now loaded from another
            # plist").
            unrelated_plist = tmp_path / "unrelated" / "com.native-stack.qdrant.plist"
            unrelated_plist.parent.mkdir(parents=True)
            unrelated_plist.write_text("<plist>unrelated service, not ours</plist>")
            takeover_shim = tmp_path / "takeover-shim"
            takeover_shim.mkdir()
            (takeover_shim / "launchctl").write_text(
                "#!/bin/sh\n"
                f'printf "%s\\n" "launchctl $*" >> {str(log)!r}\n'
                'case "$1" in\n'
                f'  print) echo "path = {unrelated_plist}"; exit 0 ;;\n'
                "  bootout) echo BOOTOUT_CALLED >&2; exit 0 ;;\n"
                "  *) exit 0 ;;\n"
                "esac\n"
            )
            (takeover_shim / "launchctl").chmod(0o755)
            remove_env = {**env, "PATH": f"{takeover_shim}{os.pathsep}{env['PATH']}"}
            remove_result = self._run(["remove", "--label", "com.native-stack.qdrant"], env=remove_env)
            self.assertNotEqual(remove_result.returncode, 0, remove_result.stdout + remove_result.stderr)
            self.assertIn("it is loaded from somewhere other than", remove_result.stderr)
            self.assertNotIn("BOOTOUT_CALLED", remove_result.stderr,
                              "remove must never bootout a label loaded from a different path")
            self.assertTrue(dest_plist.is_file(), "our own destination plist must survive untouched")
            self.assertEqual(dest_plist.read_bytes(), original_content)
            self.assertTrue(unrelated_plist.is_file(), "the unrelated service's own plist is never touched")

    def test_remove_refuses_when_print_fails_with_neither_loaded_nor_not_found(self):
        # Round 3g stateless-ownership rule, named test (unknown touches
        # nothing, remove side).
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
            self.assertIn("did not confidently report loaded, not-found, or a matching path", remove_result.stderr)
            self.assertTrue(dest_plist.is_file())
            invocations = log.read_text()
            self.assertNotIn("bootout", invocations)

    def test_no_temp_file_survives_a_completed_install(self):
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
            reinstall = self._run(["install", "--label", "com.native-stack.qdrant"], env=env)
            self.assertEqual(reinstall.returncode, 0, reinstall.stdout + reinstall.stderr)
            leftover = [p.name for p in launch_agents_dir.iterdir() if ".new." in p.name]
            self.assertEqual(leftover, [], leftover)

    def test_a_failed_copy_into_the_temp_file_never_touches_the_live_destination(self):
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

            # Real cp, except: writing to the temp file ("*.plist.new.*",
            # the only pattern this script's cp ever targets) writes
            # partial content, then fails -- simulating a disk-full or
            # otherwise interrupted copy.
            failing_cp_shim = tmp_path / "failing-cp-shim"
            failing_cp_shim.mkdir()
            (failing_cp_shim / "cp").write_text(
                "#!/bin/sh\n"
                'dest=""\n'
                'for arg in "$@"; do dest="$arg"; done\n'
                'case "$dest" in\n'
                "  *.plist.new.*)\n"
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
            self.assertNotEqual(reinstall.returncode, 0, reinstall.stdout + reinstall.stderr)
            # The live plist's own definition is intact and unchanged.
            self.assertTrue(dest_plist.is_file())
            self.assertNotEqual(dest_plist.read_bytes(), b"PARTIAL")
            self.assertEqual(dest_plist.read_bytes(), original_content)
            # No stray "*.new.<pid>" temp file either -- the EXIT trap
            # removed it even though it holds partial content.
            leftover_tmp = [p.name for p in launch_agents_dir.iterdir() if ".new." in p.name]
            self.assertEqual(leftover_tmp, [], leftover_tmp)

    def test_remove_on_an_unloaded_label_cleans_up_without_calling_bootout(self):
        # bootout always fails on a label that is not currently loaded
        # (already unloaded outside this script, crashed, or never
        # finished bootstrapping); check launchctl print first and clean up
        # directly instead of guaranteeing a failed bootout call.
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
            invocations = log.read_text()
            self.assertNotIn("bootout", invocations, "bootout must not be called on an unloaded label")

    def test_install_creates_directories_from_the_plists_own_declared_paths_not_eco_install_root(self):
        # --host renders can point ECO_ROOT somewhere entirely different
        # from this shell's own ECO_INSTALL_ROOT; the directories install
        # creates must come from the rendered plist's own StandardOutPath/
        # StandardErrorPath/WorkingDirectory, not the shell.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fake_home = tmp_path / "home"
            fake_home.mkdir()
            other_root = tmp_path / "elsewhere" / "eco-root"
            host_file = ROOT / "adoption" / "hosts" / "test-launchd-other-host.json"
            host_file.write_text(json.dumps({
                "HOME": str(fake_home), "ECO_ROOT": str(other_root), "AI_MEMORY_URL": "127.0.0.1:49374",
                "EMBED_MODEL_PATH": str(other_root / "state" / "models" / "embeddinggemma-300M-Q8_0.gguf"),
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
            self.assertFalse((eco_root_unused / "state" / "logs").exists())
            self.assertFalse((eco_root_unused / "state" / "qdrant").exists())


    def _matrix_binary_shim(self, tmp_path, marker_dir, log, binary, target, mode, signal_name=None):
        """Builds a shim for `binary` used in the convergence matrix below.

        `target` selects WHERE this shim injects: a launchctl subcommand
        name ("bootout" or "bootstrap") for binary=="launchctl", or the
        "*.plist.new.*" temp-file path pattern (this script's ONLY staging
        target) for binary in ("cp", "mv"). `mode` is "failure" (never
        performs the real action) or a signal name (performs the real
        action, then signals $PPID -- the same real-command-then-signal
        design test_adoption_bootstrap_macos.py's own signal shims use).
        For launchctl, every OTHER subcommand keeps working exactly like
        _launchctl_shim (marker-based, reading/writing marker_dir), so the
        matrix isolates exactly one step at a time.
        """
        shim_dir = tmp_path / f"matrix-{binary}-{target}-{mode}-shim"
        shim_dir.mkdir()
        if binary == "launchctl":
            lines = ["#!/bin/sh", f'printf "%s\\n" "launchctl $*" >> {str(log)!r}', 'case "$1" in']
            for subcmd in ("bootstrap", "print", "bootout", "enable"):
                if subcmd == target:
                    if mode == "failure":
                        lines.append(f"  {subcmd}) exit 1 ;;")
                    else:
                        if subcmd == "bootstrap":
                            real = ('label="$(basename "$3" .plist)"\n'
                                    f'    echo "$3" > "{marker_dir!s}/$label.loaded.marker"')
                        elif subcmd == "bootout":
                            real = ('label="$(basename "$2")"\n'
                                    f'    rm -f "{marker_dir!s}/$label.loaded.marker"')
                        else:
                            real = ":"
                        lines += [
                            f"  {subcmd})",
                            f"    {real}",
                            f'    kill -{signal_name} "$PPID"',
                            "    sleep 0.3",
                            "    exit 0 ;;",
                        ]
                elif subcmd == "bootstrap":
                    lines += [
                        "  bootstrap)",
                        '    label="$(basename "$3" .plist)"',
                        f'    echo "$3" > "{marker_dir!s}/$label.loaded.marker"',
                        "    exit 0 ;;",
                    ]
                elif subcmd == "print":
                    lines += [
                        "  print)",
                        '    label="$(basename "$2")"',
                        f'    marker="{marker_dir!s}/$label.loaded.marker"',
                        '    if [ -f "$marker" ]; then echo "path = $(cat "$marker")"; exit 0; else exit 113; fi ;;',
                    ]
                elif subcmd == "bootout":
                    lines += [
                        "  bootout)",
                        '    label="$(basename "$2")"',
                        f'    rm -f "{marker_dir!s}/$label.loaded.marker"',
                        "    exit 0 ;;",
                    ]
                else:
                    lines.append("  enable) exit 0 ;;")
            lines += ["  *) exit 0 ;;", "esac"]
            (shim_dir / "launchctl").write_text("\n".join(lines) + "\n")
            (shim_dir / "launchctl").chmod(0o755)
        else:
            if binary == "cp":
                picker = 'check=""\nfor arg in "$@"; do check="$arg"; done\n'
            else:
                picker = ('check=""\n'
                          'for arg in "$@"; do\n'
                          '  case "$arg" in -f|--) continue ;; esac\n'
                          '  if [ -z "$check" ]; then check="$arg"; fi\n'
                          "done\n")
            if mode == "failure":
                body = ('case "$check" in\n'
                        "  *.plist.new.*)\n"
                        f"    echo '{binary}: injected failure for testing' >&2\n"
                        "    exit 1\n"
                        "    ;;\n"
                        "esac\n"
                        f'exec /bin/{binary} "$@"\n')
            else:
                body = ('case "$check" in\n'
                        "  *.plist.new.*)\n"
                        f'    /bin/{binary} "$@" || exit $?\n'
                        f'    kill -{signal_name} "$PPID"\n'
                        "    sleep 0.3\n"
                        "    exit 0\n"
                        "    ;;\n"
                        "esac\n"
                        f'exec /bin/{binary} "$@"\n')
            (shim_dir / binary).write_text("#!/bin/sh\n" + picker + body)
            (shim_dir / binary).chmod(0o755)
        return shim_dir

    def test_convergence_matrix_every_step_x_failure_term_int_then_fault_free_retry(self):
        # Round 3g, coordinator's explicit method: for every step of
        # install x {failure, TERM, INT}, then a fault-free re-run of
        # install, the end state must be NEW loaded from dest_plist; a
        # re-run of remove must leave nothing loaded and no file. Replaces
        # every round 3b-3f backup/reconcile test: there is no backup or
        # reconcile left to test -- only this one end-to-end convergence
        # guarantee, exactly the promise brew services itself makes ("run
        # the command again"), never a stronger one.
        matrix = [
            ("cp", "stage"),
            ("launchctl", "bootout"),
            ("mv", "rename"),
            ("launchctl", "bootstrap"),
        ]
        for binary, step in matrix:
            for mode in ("failure", "TERM", "INT"):
                with self.subTest(step=step, mode=mode):
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
                        self.assertEqual(first_install.returncode, 0,
                                          first_install.stdout + first_install.stderr)
                        launch_agents_dir = fake_home / "Library" / "LaunchAgents"
                        dest_plist = launch_agents_dir / "com.native-stack.qdrant.plist"

                        signal_name = None if mode == "failure" else mode
                        fault_shim = self._matrix_binary_shim(
                            tmp_path, working_shim, log, binary, step, mode, signal_name)
                        fault_env = {**env, "PATH": f"{fault_shim}{os.pathsep}{env['PATH']}"}
                        interrupted = self._run(
                            ["install", "--label", "com.native-stack.qdrant"], env=fault_env)
                        self.assertNotEqual(interrupted.returncode, 0,
                                             interrupted.stdout + interrupted.stderr)
                        leftover_temp = [p.name for p in launch_agents_dir.iterdir() if ".new." in p.name]
                        self.assertEqual(leftover_temp, [], leftover_temp)

                        # A fault-free retry always converges to NEW loaded
                        # from dest_plist.
                        retry = self._run(["install", "--label", "com.native-stack.qdrant"], env=env)
                        self.assertEqual(retry.returncode, 0, retry.stdout + retry.stderr)
                        self.assertTrue(dest_plist.is_file())
                        status = self._run(["status", "--label", "com.native-stack.qdrant"], env=env)
                        self.assertIn(f"path = {dest_plist}", status.stdout, status.stdout)

                        # A fault-free remove leaves nothing loaded and no file.
                        remove = self._run(["remove", "--label", "com.native-stack.qdrant"], env=env)
                        self.assertEqual(remove.returncode, 0, remove.stdout + remove.stderr)
                        self.assertFalse(dest_plist.exists())
                        status_after = self._run(["status", "--label", "com.native-stack.qdrant"], env=env)
                        self.assertNotIn("path =", status_after.stdout)

    def test_a_failed_or_signaled_bootout_during_remove_leaves_the_plist_and_a_retry_converges(self):
        # remove's own single fallible external step: bootout. Covers
        # failure and both signals; a retry with a working launchctl always
        # converges to nothing loaded and no file.
        for mode in ("failure", "TERM", "INT"):
            with self.subTest(mode=mode):
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
                    self.assertEqual(install_result.returncode, 0,
                                      install_result.stdout + install_result.stderr)
                    launch_agents_dir = fake_home / "Library" / "LaunchAgents"
                    dest_plist = launch_agents_dir / "com.native-stack.qdrant.plist"

                    signal_name = None if mode == "failure" else mode
                    fault_shim = self._matrix_binary_shim(
                        tmp_path, working_shim, log, "launchctl", "bootout", mode, signal_name)
                    fault_env = {**env, "PATH": f"{fault_shim}{os.pathsep}{env['PATH']}"}
                    interrupted = self._run(["remove", "--label", "com.native-stack.qdrant"], env=fault_env)
                    self.assertNotEqual(interrupted.returncode, 0, interrupted.stdout + interrupted.stderr)
                    self.assertTrue(dest_plist.is_file(),
                                     "the plist must survive a failed or interrupted bootout during remove")

                    retry = self._run(["remove", "--label", "com.native-stack.qdrant"], env=env)
                    self.assertEqual(retry.returncode, 0, retry.stdout + retry.stderr)
                    self.assertFalse(dest_plist.exists())

    def test_a_hard_linked_alias_of_dest_plist_is_never_loaded_here(self):
        # Round 3i Codex Medium (finding 1): `-ef` compares device+inode,
        # so a DISTINCT hard-linked filename sharing dest_plist's own
        # inode incorrectly compared equal, letting remove bootout and
        # delete dest_plist for a label that is actually loaded from an
        # unrelated, merely hard-linked, path. canonical_plist_path
        # (string comparison of resolved paths, never inode identity)
        # must treat these as loaded_elsewhere: a hard link has no stored
        # "canonical name" to resolve to, so neither `cd -P` nor python3's
        # os.path.realpath ever collapses it the way `-ef` did.
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

            # A DISTINCT filename, hard-linked to dest_plist's own inode --
            # existing, real files, both genuinely present on disk.
            hardlink_alias = launch_agents_dir / "decoy-hardlink.plist"
            os.link(dest_plist, hardlink_alias)
            self.assertTrue(hardlink_alias.samefile(dest_plist), "setup: must genuinely share an inode")

            takeover_shim = tmp_path / "takeover-shim"
            takeover_shim.mkdir()
            (takeover_shim / "launchctl").write_text(
                "#!/bin/sh\n"
                f'printf "%s\\n" "launchctl $*" >> {str(log)!r}\n'
                'case "$1" in\n'
                f'  print) echo "path = {hardlink_alias}"; exit 0 ;;\n'
                "  bootout) echo BOOTOUT_CALLED >&2; exit 0 ;;\n"
                "  *) exit 0 ;;\n"
                "esac\n"
            )
            (takeover_shim / "launchctl").chmod(0o755)
            remove_env = {**env, "PATH": f"{takeover_shim}{os.pathsep}{env['PATH']}"}
            remove_result = self._run(["remove", "--label", "com.native-stack.qdrant"], env=remove_env)
            self.assertNotEqual(remove_result.returncode, 0, remove_result.stdout + remove_result.stderr)
            self.assertIn("it is loaded from somewhere other than", remove_result.stderr)
            self.assertNotIn("BOOTOUT_CALLED", remove_result.stderr,
                              "a distinct hard-linked alias must never be treated as loaded_here")
            self.assertTrue(dest_plist.is_file())
            self.assertEqual(dest_plist.read_bytes(), original_content)

            # install must refuse identically for the same reason.
            install_result = self._run(["install", "--label", "com.native-stack.qdrant"], env=remove_env)
            self.assertNotEqual(install_result.returncode, 0, install_result.stdout + install_result.stderr)
            self.assertNotIn("BOOTOUT_CALLED", install_result.stderr)

    def test_retry_converges_while_an_earlier_runs_teardown_is_still_asynchronously_in_progress(self):
        # Round 3i Codex Medium (finding 2): an interrupted run's own
        # bootout can leave launchd genuinely tearing the label down --
        # not yet finished -- when a clean retry begins. The retry's OWN
        # bootout call then observes that in-progress teardown (real
        # launchctl: EINPROGRESS, Darwin errno 36; the pinned Homebrew
        # cli.rb @ 8e3a5dc0a7 retries on exactly this) rather than a
        # settled state. bootout_and_wait must absorb that and keep
        # polling (reusing wait_until_unloaded) until it actually
        # resolves, never refuse outright on the retry's own bootout
        # call. Unlike _matrix_binary_shim's bootout-signal case (which
        # clears the loaded marker synchronously, before signalling, and
        # so cannot model this at all -- Codex's own point about that
        # shim), teardown here only actually completes after a bounded
        # number of TOTAL print polls, shared across BOTH the interrupted
        # run and the retry, modelling a real asynchronous teardown that
        # keeps progressing on its own regardless of which process asks.
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

            for signal_name in ("TERM", "INT"):
                with self.subTest(signal=signal_name):
                    async_shim = tmp_path / f"async-teardown-{signal_name}-shim"
                    async_shim.mkdir()
                    (async_shim / "launchctl").write_text(
                        "#!/bin/sh\n"
                        f'printf "%s\\n" "launchctl $*" >> {str(log)!r}\n'
                        'case "$1" in\n'
                        '  bootstrap)\n'
                        '    label="$(basename "$3" .plist)"\n'
                        f'    echo "$3" > "{working_shim!s}/$label.loaded.marker"\n'
                        f'    rm -f "{async_shim!s}/teardown-started" "{async_shim!s}/poll-count"\n'
                        "    exit 0 ;;\n"
                        '  print)\n'
                        f'    if [ -f "{async_shim!s}/teardown-started" ]; then\n'
                        f'      count_file="{async_shim!s}/poll-count"\n'
                        '      count=0\n'
                        '      [ -f "$count_file" ] && count="$(cat "$count_file")"\n'
                        '      count=$((count + 1))\n'
                        '      echo "$count" > "$count_file"\n'
                        '      if [ "$count" -ge 3 ]; then\n'
                        f'        rm -f "{working_shim!s}/com.native-stack.qdrant.loaded.marker"\n'
                        '        exit 113\n'
                        "      fi\n"
                        f'      echo "path = {dest_plist}"\n'
                        "      exit 0\n"
                        "    fi\n"
                        '    label="$(basename "$2")"\n'
                        f'    marker="{working_shim!s}/$label.loaded.marker"\n'
                        '    if [ -f "$marker" ]; then echo "path = $(cat "$marker")"; exit 0; else exit 113; fi ;;\n'
                        '  bootout)\n'
                        f'    if [ -f "{async_shim!s}/teardown-started" ]; then\n'
                        "      exit 36\n"
                        "    fi\n"
                        f'    touch "{async_shim!s}/teardown-started"\n'
                        f'    kill -{signal_name} "$PPID"\n'
                        "    sleep 0.3\n"
                        "    exit 0 ;;\n"
                        '  enable) exit 0 ;;\n'
                        '  *) exit 0 ;;\n'
                        "esac\n"
                    )
                    (async_shim / "launchctl").chmod(0o755)
                    async_env = {
                        **env,
                        "PATH": f"{async_shim}{os.pathsep}{env['PATH']}",
                        "WAIT_UNTIL_UNLOADED_ATTEMPTS": "3",
                        "WAIT_UNTIL_UNLOADED_INTERVAL": "0",
                    }
                    interrupted = self._run(["install", "--label", "com.native-stack.qdrant"], env=async_env)
                    self.assertNotEqual(interrupted.returncode, 0, interrupted.stdout + interrupted.stderr)
                    # The interrupted run's own bootout initiated teardown
                    # but never itself reached wait_until_unloaded (the
                    # signal fired right after that one call) -- no print
                    # poll happened yet, so teardown is still 0/3 complete.
                    self.assertTrue((async_shim / "teardown-started").exists())
                    self.assertFalse((async_shim / "poll-count").exists())

                    # A clean retry: its own bootout call observes the
                    # ALREADY in-progress teardown (EINPROGRESS) and must
                    # poll through to convergence, not refuse outright.
                    retry = self._run(["install", "--label", "com.native-stack.qdrant"], env=async_env)
                    self.assertEqual(retry.returncode, 0, retry.stdout + retry.stderr)
                    self.assertIn("Installed", retry.stdout)
                    invocations = log.read_text()
                    self.assertIn("launchctl bootout", invocations)
                    self.assertTrue(dest_plist.is_file())


if __name__ == "__main__":
    unittest.main()
