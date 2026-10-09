"""Unit tests for tools/adoption/install_claude_profile.py's guard/agents/workflows
steps (sha256-checked, idempotent) and the MCP registration matcher used to
decide whether an existing `claude mcp get` entry already matches the
template (so registration is skipped rather than repeated). The `claude`
binary itself is never invoked here; MCP idempotency is tested against
`existing_config_matches` directly with recorded-shape text fixtures, and the
placeholder rendering and `claude mcp add` argument order are tested as data.
"""

import io
import json
import os
import re
import shutil
import string
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "adoption"))

import install_claude_profile as icp  # noqa: E402
import managed_block  # noqa: E402

# The user-scope MCP template is checked against the SubagentStart carrier, the Codex user template and this
# repository's default host endpoints (docs/decisions/2026-09-26-stack-agents-role-dispatch.md, addendum 2026-09-30).
CARRIER = ROOT / "adoption" / "hooks" / "claude" / "token-lanes-block.md"
# Every carrier block: the general block above and the five role blocks the SubagentStart hook picks by agent type
# (adoption/hooks/claude/token-lanes-subagent-start.py), and the main-session block of the SessionStart hook
# (adoption/hooks/claude/token-lanes-session-start.py). The user-scope template is checked against all of them.
CARRIER_BLOCK_NAMES = ("token-lanes-block.builder.md", "token-lanes-block.main.md", "token-lanes-block.md",
                       "token-lanes-block.researcher.md", "token-lanes-block.reviewer.md", "token-lanes-block.scout.md",
                       "token-lanes-block.verifier.md")
CODEX_TEMPLATE = ROOT / "adoption" / "templates" / "codex.config.template.toml"
HOST_EXAMPLE = ROOT / "adoption" / "hosts" / "example.json"
USER_SCOPE_SERVERS = {"ai-memory", "serena", "socraticode", "headroom", "codebase-memory", "qmd", "jcodemunch"}
# A server the carrier names that the user-scope template leaves out, with each file and the phrase in it that keeps
# it out. None now: jCodeMunch was the one (registered per project since the 2026-09-25 addendum of
# docs/decisions/2026-09-23-claude-user-profile.md) until the user's directive of 2026-10-04 put it back at user scope
# in both user templates (docs/decisions/2026-10-04-new-wsl-jcodemunch-user-scope.md).
CARRIER_EXCEPTIONS: dict = {}
# A sourced exception as the mechanism takes it, for the controls below: a server the template leaves out, and a file
# that holds the phrase that says why.
SAMPLE_EXCEPTION = {"qmd": (("adoption/bootstrap.md", "jCodeMunch recipe"),)}
# Codex-side variables a Claude registration does not carry: the installer renders no ${HOST_PATH}, and serena's
# entry has carried neither since 2026-09-23.
CODEX_ONLY_ENV = {"PATH", "RTK_TELEMETRY_DISABLED"}
TOOL_ID = re.compile(r"(?<![A-Za-z0-9_])mcp__([A-Za-z0-9_-]+?)__[A-Za-z0-9_]+")


def carrier_servers(text: str) -> set[str]:
    """Server names of the mcp__<server>__<tool> ids a text names. A plugin's server (mcp__plugin_<plugin>_<server>__)
    comes with its plugin, not from a user-scope registration, so it is left out."""
    return {name for name in TOOL_ID.findall(text) if not name.startswith("plugin_")}


def carrier_blocks_text(directory: Path) -> str:
    """The text of every token-lanes-block*.md carrier block in `directory`, in name order: the union is what the
    SubagentStart hook can hand a subagent, whichever role block it picks."""
    return "\n".join(path.read_text(encoding="utf-8") for path in sorted(directory.glob("token-lanes-block*.md")))


def carrier_coverage_errors(carrier_text: str, registered: set[str], exceptions: dict, read) -> list[str]:
    """One error per server the carrier names that the template neither registers nor excepts, per exception phrase
    missing from its named file (read(path) -> text or None), and per exception for a server the template registers
    anyway."""
    errors = []
    for name in sorted(carrier_servers(carrier_text)):
        if name in registered:
            if name in exceptions:
                errors.append(f"{name}: registered and also listed as an exception")
            continue
        if name not in exceptions:
            errors.append(f"{name}: named by the carrier, not registered at user scope and not an exception")
            continue
        for path, phrase in exceptions[name]:
            if phrase not in (read(path) or ""):
                errors.append(f"{name}: the exception's phrase is not in {path}")
    return errors


# Arguments that differ by client on purpose, Codex value -> Claude value. serena runs its `claude-code` context under
# Claude and `codex` under Codex (oraios/serena c6fbd1c src/serena/resources/config/contexts/). SocratiCode's script
# is the npm bin link both bootstraps' install_npm create (adoption/bootstrap-linux.sh install_npm,
# adoption/bootstrap-macos.sh install_npm), because the Claude installer renders only ${HOME} and ${ECO_ROOT}, never
# the Codex template's per-platform ${SOCRATICODE_VERSION}; node runs the link's target (--preserve-symlinks-main is off
# by default).
CLIENT_ARGS = {
    "serena": {"codex": "claude-code"},
    "socraticode": {"${ECO_ROOT}/tools/socraticode-${SOCRATICODE_VERSION}/lib/node_modules/socraticode/dist/index.js":
                    "${ECO_ROOT}/bin/socraticode"},
}


def codex_host_values() -> dict:
    """adoption/hosts/example.json without HOME and ECO_ROOT, which both templates keep as placeholders."""
    values = json.loads(HOST_EXAMPLE.read_text(encoding="utf-8"))
    return {key: value for key, value in values.items() if key not in ("HOME", "ECO_ROOT")}


def codex_parity_errors(claude: dict, codex: dict, values: dict) -> list[str]:
    """One error per difference between a Claude user-scope entry and the Codex user template's entry of each server
    the Claude template names: transport, URL or command, arguments (after CLIENT_ARGS), and env names and values
    (Codex's rendered with `values`, less CODEX_ONLY_ENV)."""
    def render(value):
        return string.Template(value).safe_substitute(values)

    errors = []
    for name, entry in sorted(claude.items()):
        other = codex.get(name)
        if other is None:
            errors.append(f"{name}: not in the Codex user template")
            continue
        if "url" in other:
            if (entry.get("type"), entry.get("url")) != ("http", render(other["url"])):
                errors.append(f"{name}: transport or URL differs")
            continue
        if entry.get("type") != "stdio" or entry.get("command") != other.get("command"):
            errors.append(f"{name}: transport or command differs")
        mapped = [CLIENT_ARGS.get(name, {}).get(arg, arg) for arg in other.get("args", [])]
        if entry.get("args", []) != mapped:
            errors.append(f"{name}: arguments differ")
        expected_env = {key: render(value) for key, value in other.get("env", {}).items() if key not in CODEX_ONLY_ENV}
        if set(entry.get("env", {})) != set(expected_env):
            errors.append(f"{name}: env names differ")
        elif entry.get("env", {}) != expected_env:
            errors.append(f"{name}: env values differ")
    return errors

# The jcodemunch entry adoption/mcp/claude-user.json carried until 2026-09-25 (with CODE_INDEX_PATH; the template's
# entry since 2026-10-04 carries only JCODEMUNCH_SHARE_SAVINGS). It stays here, inline, as the fixture for
# a stdio server with ${HOME} in an env value and env names to match: no template entry has one now.
JCODEMUNCH_SPEC = {
    "type": "stdio",
    "command": "${ECO_ROOT}/bin/jcodemunch-mcp",
    "args": [],
    "env": {"CODE_INDEX_PATH": "${HOME}/.code-index", "JCODEMUNCH_SHARE_SAVINGS": "0"},
}


def template_server_names() -> list[str]:
    return list(json.loads(icp.MCP_TEMPLATE.read_text())["mcpServers"])


class GuardInstallTests(unittest.TestCase):
    def test_token_lanes_assets_cli_dry_run_and_temp_home_install(self):
        script = "token-lanes-subagent-start.py"
        session_script = "token-lanes-session-start.py"
        names = ("token-lanes-block.md", "token-lanes-block.builder.md", "token-lanes-block.researcher.md",
                 "token-lanes-block.reviewer.md", "token-lanes-block.scout.md", "token-lanes-block.verifier.md",
                 script, "token-lanes-block.main.md", session_script)
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            # The carriers are held out of the default (docs/decisions/2026-10-04-claude-template-holds-out-token-lane-carriers.md):
            # they install only when --hook names them.
            command = [sys.executable, str(ROOT / "tools/adoption/install_claude_profile.py"),
                       "--only", "guard", *(arg for name in names for arg in ("--hook", name))]
            env = {**os.environ, "HOME": tmp}
            planned = subprocess.run(command + ["--dry-run"], env=env, cwd=ROOT,
                                     capture_output=True, text=True, timeout=30)
            self.assertEqual(planned.returncode, 0, planned.stderr)
            self.assertFalse((home / ".claude").exists())
            for name in names:
                self.assertIn(f"would install {home / '.claude/hooks' / name}", planned.stdout)
            installed = subprocess.run(command, env=env, cwd=ROOT,
                                       capture_output=True, text=True, timeout=30)
            self.assertEqual(installed.returncode, 0, installed.stderr)
            for name in names:
                dest = home / ".claude/hooks" / name
                self.assertIn(f"installed {dest}", installed.stdout)
                self.assertEqual(dest.read_bytes(), (ROOT / "adoption/hooks/claude" / name).read_bytes())
            # The installed script resolves the installed default or role block, even from a different cwd.
            for agent_type, block in (("general-purpose", "token-lanes-block.md"),
                                      ("stack-verifier", "token-lanes-block.verifier.md")):
                with self.subTest(agent_type=agent_type):
                    injected = subprocess.run([sys.executable, str(home / ".claude/hooks" / script)],
                                              input=json.dumps({"agent_type": agent_type}), env=env, cwd=home,
                                              capture_output=True, text=True, timeout=30)
                    self.assertEqual(injected.returncode, 0, injected.stderr)
                    self.assertEqual(json.loads(injected.stdout)["hookSpecificOutput"]["additionalContext"],
                                     (home / ".claude/hooks" / block).read_text(encoding="utf-8"))
            # The installed SessionStart script resolves the installed main-session block the same way.
            with self.subTest(event="SessionStart"):
                injected = subprocess.run([sys.executable, str(home / ".claude/hooks" / session_script)],
                                          input=json.dumps({"hook_event_name": "SessionStart", "source": "startup"}),
                                          env=env, cwd=home, capture_output=True, text=True, timeout=30)
                self.assertEqual(injected.returncode, 0, injected.stderr)
                self.assertEqual(json.loads(injected.stdout)["hookSpecificOutput"],
                                 {"hookEventName": "SessionStart", "additionalContext":
                                  (home / ".claude/hooks/token-lanes-block.main.md").read_text(encoding="utf-8")})

    def test_the_default_guard_step_installs_no_held_out_carrier_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {**os.environ, "HOME": tmp}
            command = [sys.executable, str(ROOT / "tools/adoption/install_claude_profile.py"), "--only", "guard"]
            planned = subprocess.run(command + ["--dry-run"], env=env, cwd=ROOT, capture_output=True, text=True,
                                     timeout=30)
            self.assertEqual(planned.returncode, 0, planned.stderr)
            self.assertNotIn("token-lanes", planned.stdout)
            for name in icp.HOOKS:
                self.assertIn(f"would install {Path(tmp) / '.claude/hooks' / name}", planned.stdout)
            installed = subprocess.run(command, env=env, cwd=ROOT, capture_output=True, text=True, timeout=30)
            self.assertEqual(installed.returncode, 0, installed.stderr)
            self.assertEqual(sorted(path.name for path in (Path(tmp) / ".claude/hooks").iterdir()), sorted(icp.HOOKS))

    def test_a_name_outside_both_hook_maps_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(icp.InstallError):
                icp.install_guards(Path(tmp), dry_run=False, names=["token-lanes-block.nonexistent.md"])
            self.assertFalse((Path(tmp) / ".claude").exists())

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


class WorkflowInstallTests(unittest.TestCase):
    """Local integration checks for native saved-script files, without model calls."""

    NAMES = ("readiness-audit.js", "review-changes.js", "layer-verdict-lane.js")

    def cli(self, home, *args):
        return subprocess.run(
            [sys.executable, str(ROOT / "tools/adoption/install_claude_profile.py"),
             "--home", str(home), *args],
            cwd=ROOT, capture_output=True, text=True, timeout=30,
        )

    def install(self, home):
        with mock.patch("sys.stdout", new_callable=io.StringIO):
            return icp.install_workflows(home, dry_run=False)

    def test_cli_clean_install_readback_and_idempotence(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            planned = self.cli(home, "--only", "workflows", "--dry-run")
            self.assertEqual(planned.returncode, 0, planned.stderr)
            self.assertFalse((home / ".claude").exists())
            for name in self.NAMES:
                self.assertIn(f"would install {home / '.claude/workflows' / name}", planned.stdout)
            installed = self.cli(home, "--only", "workflows")
            self.assertEqual(installed.returncode, 0, installed.stderr)
            dest_dir = home / ".claude/workflows"
            self.assertEqual({p.name for p in dest_dir.iterdir()}, set(self.NAMES))
            before = {}
            for name in self.NAMES:
                dest = dest_dir / name
                self.assertEqual(dest.read_bytes(), (icp.WORKFLOWS_SRC_DIR / name).read_bytes())
                before[name] = (dest.stat().st_ino, dest.stat().st_mtime_ns)
            repeated = self.cli(home, "--only", "workflows")
            self.assertEqual(repeated.returncode, 0, repeated.stderr)
            self.assertEqual(repeated.stdout.count("already matches; skipped"), 3)
            for name in self.NAMES:
                dest = dest_dir / name
                self.assertEqual((dest.stat().st_ino, dest.stat().st_mtime_ns), before[name])

    def test_explicit_profile_selection_installs_saved_workflows(self):
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.object(icp, "install_guards") as guards, \
             mock.patch.object(icp, "install_agents") as agents, \
             mock.patch.object(icp, "install_mcp_servers") as mcp, \
             mock.patch("sys.stdout", new_callable=io.StringIO):
            home = Path(tmp)
            self.assertEqual(icp.main(["--home", tmp, "--only", "workflows"]), 0)
            self.assertEqual({p.name for p in (home / ".claude/workflows").iterdir()}, set(self.NAMES))
            guards.assert_not_called()
            agents.assert_not_called()
            mcp.assert_not_called()

    def test_default_profile_never_reads_or_creates_workflows(self):
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.object(icp, "install_guards") as guards, \
             mock.patch.object(icp, "install_agents") as agents, \
             mock.patch.object(icp, "install_mcp_servers") as mcp:
            home = Path(tmp)
            dest_dir = home / ".claude/workflows"

            def forbid_workflow_access(method):
                def checked(path, *args, **kwargs):
                    if path.is_relative_to(dest_dir) or path.is_relative_to(icp.WORKFLOWS_SRC_DIR):
                        raise AssertionError(f"default run accessed workflows: {path}")
                    return method(path, *args, **kwargs)
                return checked

            with mock.patch.object(Path, "open", forbid_workflow_access(Path.open)), \
                 mock.patch.object(Path, "stat", forbid_workflow_access(Path.stat)), \
                 mock.patch.object(Path, "iterdir", forbid_workflow_access(Path.iterdir)), \
                 mock.patch.object(Path, "mkdir", forbid_workflow_access(Path.mkdir)):
                self.assertEqual(icp.main(["--home", tmp]), 0)
            self.assertFalse(dest_dir.exists())
            guards.assert_called_once_with(home, False, None)
            agents.assert_called_once_with(home, False, None)
            mcp.assert_called_once()

    def test_source_corruption_or_missing_manifest_entry_refuses_before_writes(self):
        for failure in ("corruption", "missing-entry"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as tmp:
                scratch = Path(tmp)
                sources = scratch / "sources"
                sources.mkdir()
                for name in self.NAMES:
                    shutil.copy2(icp.WORKFLOWS_SRC_DIR / name, sources / name)
                sums = sources / "SHA256SUMS"
                sums.write_bytes(icp.WORKFLOWS_SHA256SUMS.read_bytes())
                if failure == "corruption":
                    with (sources / self.NAMES[-1]).open("ab") as stream:
                        stream.write(b"\n// unreviewed mutation\n")
                else:
                    sums.write_text("\n".join(line for line in sums.read_text().splitlines()
                                              if not line.endswith(self.NAMES[-1])) + "\n")
                home = scratch / "home"
                home.mkdir()
                with mock.patch.object(icp, "WORKFLOWS_SRC_DIR", sources), \
                     mock.patch.object(icp, "WORKFLOWS_SHA256SUMS", sums):
                    with self.assertRaises(icp.InstallError):
                        self.install(home)
                self.assertFalse((home / ".claude").exists())

    def test_conflicting_last_target_refuses_every_write_including_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            dest_dir = home / ".claude/workflows"
            dest_dir.mkdir(parents=True)
            conflict = dest_dir / self.NAMES[-1]
            conflict.write_bytes(b"personalized workflow\n")
            custom = dest_dir / "custom.js"
            custom.write_bytes(b"custom workflow\n")
            for extra in ((), ("--dry-run",)):
                result = self.cli(home, "--only", "workflows", *extra)
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertIn("differs; left unchanged", result.stderr)
                self.assertEqual(conflict.read_bytes(), b"personalized workflow\n")
                self.assertEqual(custom.read_bytes(), b"custom workflow\n")
                self.assertEqual({p.name for p in dest_dir.iterdir()}, {conflict.name, custom.name})

    def test_matching_or_dangling_target_symlink_is_refused(self):
        for target_exists in (True, False):
            with self.subTest(target_exists=target_exists), tempfile.TemporaryDirectory() as tmp:
                home = Path(tmp)
                dest_dir = home / ".claude/workflows"
                dest_dir.mkdir(parents=True)
                target = home / "outside.js"
                if target_exists:
                    target.write_bytes((icp.WORKFLOWS_SRC_DIR / self.NAMES[-1]).read_bytes())
                dest = dest_dir / self.NAMES[-1]
                dest.symlink_to(target)
                result = self.cli(home, "--only", "workflows")
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertIn("refusing target symlink", result.stderr)
                self.assertTrue(dest.is_symlink())
                self.assertEqual({p.name for p in dest_dir.iterdir()}, {dest.name})
                self.assertEqual(target.exists(), target_exists)
                if target_exists:
                    self.assertEqual(target.read_bytes(), (icp.WORKFLOWS_SRC_DIR / dest.name).read_bytes())

    def test_nonfile_target_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            dest = home / ".claude/workflows" / self.NAMES[-1]
            dest.mkdir(parents=True)
            result = self.cli(home, "--only", "workflows")
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertTrue(dest.is_dir())
            self.assertEqual({p.name for p in dest.parent.iterdir()}, {dest.name})

    def test_personal_dotfiles_directory_symlink_is_supported(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            dotfiles = home / "dotfiles-claude"
            dotfiles.mkdir()
            (home / ".claude").symlink_to(dotfiles, target_is_directory=True)
            result = self.cli(home, "--only", "workflows")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((home / ".claude").is_symlink())
            for name in self.NAMES:
                self.assertEqual((dotfiles / "workflows" / name).read_bytes(),
                                 (icp.WORKFLOWS_SRC_DIR / name).read_bytes())

    def test_write_failure_cleans_new_files_and_empty_directories_then_recovers(self):
        original_open = Path.open
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)

            def fail_open(path, mode="r", *args, **kwargs):
                if path.name == self.NAMES[-1] and mode == "xb":
                    raise OSError("injected write failure")
                return original_open(path, mode, *args, **kwargs)

            with mock.patch.object(Path, "open", fail_open):
                with self.assertRaisesRegex(icp.InstallError, "new files rolled back"):
                    self.install(home)
            self.assertFalse((home / ".claude").exists())
            self.assertEqual(self.install(home), dict.fromkeys(self.NAMES, "installed"))

    def test_readback_failure_rolls_back_new_files_and_preserves_reused_and_custom(self):
        original_read = Path.read_bytes
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            dest_dir = home / ".claude/workflows"
            dest_dir.mkdir(parents=True)
            reused = dest_dir / self.NAMES[0]
            reused.write_bytes((icp.WORKFLOWS_SRC_DIR / reused.name).read_bytes())
            reused_identity = (reused.stat().st_ino, reused.stat().st_mtime_ns)
            custom = dest_dir / "custom.js"
            custom.write_bytes(b"custom workflow\n")

            def fail_readback(path):
                if path.parent == dest_dir and path.name == self.NAMES[-1]:
                    return b"injected readback mismatch"
                return original_read(path)

            with mock.patch.object(Path, "read_bytes", fail_readback):
                with self.assertRaisesRegex(icp.InstallError, "installed readback differs"):
                    self.install(home)
            self.assertEqual({p.name for p in dest_dir.iterdir()}, {reused.name, custom.name})
            self.assertEqual((reused.stat().st_ino, reused.stat().st_mtime_ns), reused_identity)
            self.assertEqual(custom.read_bytes(), b"custom workflow\n")
            result = self.install(home)
            self.assertEqual(result, {self.NAMES[0]: "skipped", self.NAMES[1]: "installed", self.NAMES[2]: "installed"})

    def test_target_created_after_preflight_is_preserved_and_earlier_write_rolled_back(self):
        original_open = Path.open
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            dest_dir = home / ".claude/workflows"

            def competing_open(path, mode="r", *args, **kwargs):
                if path.parent == dest_dir and path.name == self.NAMES[1] and mode == "xb":
                    with original_open(path, "wb") as stream:
                        stream.write(b"another writer's workflow\n")
                return original_open(path, mode, *args, **kwargs)

            with mock.patch.object(Path, "open", competing_open):
                with self.assertRaises(icp.InstallError):
                    self.install(home)
            self.assertEqual({p.name for p in dest_dir.iterdir()}, {self.NAMES[1]})
            self.assertEqual((dest_dir / self.NAMES[1]).read_bytes(), b"another writer's workflow\n")

    def test_scoped_remove_dry_run_then_preserves_edited_and_custom_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            self.install(home)
            dest_dir = home / ".claude/workflows"
            custom = dest_dir / "custom.js"
            custom.write_bytes(b"custom workflow\n")
            planned = self.cli(home, "--only", "workflows", "--remove-workflows", "--dry-run")
            self.assertEqual(planned.returncode, 0, planned.stderr)
            self.assertEqual(planned.stdout.count("would remove"), 3)
            self.assertEqual({p.name for p in dest_dir.iterdir()}, {*self.NAMES, custom.name})
            edited = dest_dir / self.NAMES[-1]
            edited.write_bytes(b"personalized workflow\n")
            removed = self.cli(home, "--only", "workflows", "--remove-workflows")
            self.assertEqual(removed.returncode, 1, removed.stdout)
            self.assertIn("differs; left unchanged", removed.stderr)
            self.assertEqual({p.name for p in dest_dir.iterdir()}, {edited.name, custom.name})
            self.assertEqual(edited.read_bytes(), b"personalized workflow\n")
            self.assertEqual(custom.read_bytes(), b"custom workflow\n")

    def test_scoped_remove_preserves_target_symlinks(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            self.install(home)
            dest_dir = home / ".claude/workflows"
            target = home / "outside.js"
            dest = dest_dir / self.NAMES[-1]
            dest.rename(target)
            dest.symlink_to(target)
            removed = self.cli(home, "--only", "workflows", "--remove-workflows")
            self.assertEqual(removed.returncode, 1, removed.stdout)
            self.assertIn("is a symlink; left unchanged", removed.stderr)
            self.assertTrue(dest.is_symlink())
            self.assertEqual(target.read_bytes(), (icp.WORKFLOWS_SRC_DIR / dest.name).read_bytes())

    def test_complete_scoped_remove_is_idempotent_and_reinstall_recovers(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            self.install(home)
            for attempt in range(2):
                removed = self.cli(home, "--only", "workflows", "--remove-workflows")
                self.assertEqual(removed.returncode, 0, removed.stderr)
                self.assertEqual(list((home / ".claude/workflows").iterdir()), [])
                self.assertEqual(removed.stdout.count("removed" if attempt == 0 else "already absent"), 3)
            self.assertEqual(self.install(home), dict.fromkeys(self.NAMES, "installed"))

    def test_remove_rejects_mixed_mutation_options_before_writes(self):
        for options in (("--remove-workflows",),
                        ("--only", "workflows", "--only", "guard", "--remove-workflows"),
                        ("--only", "workflows", "--replace-mcp", "--remove-workflows")):
            with self.subTest(options=options), tempfile.TemporaryDirectory() as tmp:
                home = Path(tmp)
                result = self.cli(home, *options)
                self.assertEqual(result.returncode, 2, result.stdout)
                self.assertIn("requires exactly --only workflows", result.stderr)
                self.assertFalse((home / ".claude").exists())


class SecretGuardProfileTests(unittest.TestCase):
    """The secret-path guard and its deny rules ship in the user profile for every new host."""

    TEMPLATE = ROOT / "adoption" / "templates" / "claude.settings.template.json"

    def test_install_guards_installs_all_hooks_pinned_by_sha256sums(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            results = icp.install_guards(home, dry_run=False)
            self.assertEqual(results, {name: "installed" for name in icp.HOOKS})
            for name, source in icp.HOOKS.items():
                self.assertEqual((home / ".claude" / "hooks" / name).read_bytes(), source.read_bytes())
            self.assertEqual(icp.install_guards(home, dry_run=False),
                             {name: "skipped" for name in icp.HOOKS})

    def test_a_held_out_carrier_file_installs_only_when_named(self):
        self.assertFalse(set(icp.HOOKS) & set(icp.HELD_OUT_HOOKS))
        self.assertEqual(len(icp.HELD_OUT_HOOKS), 9)
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            self.assertEqual(icp.install_guards(home, dry_run=False, names=list(icp.HELD_OUT_HOOKS)),
                             {name: "installed" for name in icp.HELD_OUT_HOOKS})
            for name, source in icp.HELD_OUT_HOOKS.items():
                self.assertEqual((home / ".claude" / "hooks" / name).read_bytes(), source.read_bytes())

    def test_the_held_out_entries_merge_once_alongside_existing_ai_memory(self):
        import apply_claude_settings as acs
        entries_file = ROOT / "adoption" / "hooks" / "claude" / "held-out-hook-entries.json"
        with tempfile.TemporaryDirectory() as tmp:
            template = json.loads(string.Template(entries_file.read_text()).safe_substitute(HOME=tmp))
            default = json.loads(string.Template(self.TEMPLATE.read_text()).safe_substitute(HOME=tmp))
            incoming = template["hooks"]["SubagentStart"]
            memory = next(hook for group in default["hooks"]["SubagentStart"] for hook in group["hooks"]
                          if "--event subagent-start" in hook["command"])
            # The current live shape already carries ai-memory under the empty matcher.
            base = {"hooks": {"SubagentStart": [{"matcher": "", "hooks": [memory]}]}}
            wanted = f'python3 "{tmp}/.claude/hooks/token-lanes-subagent-start.py" 2>/dev/null || true'
            own_groups = [group for group in incoming
                          if any(acs.command_key(hook["command"]) == acs.command_key(wanted)
                                 for hook in group["hooks"])]
            self.assertEqual(len(own_groups), 1)
            self.assertEqual(own_groups[0], {"matcher": "", "hooks": [
                {"type": "command", "command": wanted, "timeout": 5}]})
            for initial in ({}, base):
                merged = initial
                for application in (1, 2):
                    previous = merged
                    merged = acs.merge_settings(merged, template)
                    keys = [acs.command_key(hook["command"])
                            for group in merged["hooks"]["SubagentStart"] for hook in group["hooks"]]
                    with self.subTest(existing=bool(initial), application=application):
                        self.assertEqual(keys.count(acs.command_key(wanted)), 1)
                        self.assertEqual(keys.count(acs.command_key(memory["command"])), 1 if initial else 0)
                        if application == 2:
                            self.assertEqual(merged, previous)

    def test_sha256sums_verifies_like_sha256sum_c(self):
        entries = icp.sha256sums_entries()
        self.assertEqual(set(entries), {src.resolve() for src in icp.ALL_HOOKS.values()})
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
        # In the same order: a `!` carve-out reaches only the rules before it, so the `.env` rules and their
        # Context Mode `**/` twins must precede the carve-outs in the user file too.
        self.assertEqual([rule for rule in deny if rule in project["permissions"]["deny"]],
                         project["permissions"]["deny"])
        self.assertIn("Agent(codex:codex-rescue)", deny)
        bash_groups = [g for g in template["hooks"]["PreToolUse"] if g.get("matcher") == "Bash"]
        commands = [h["command"] for g in bash_groups for h in g["hooks"]]
        self.assertTrue(any("secret_path_guard.py" in c for c in commands))

    def test_only_the_secret_guard_hook_fails_closed(self):
        # Claude Code 2.1.295's `onFailure: "block"` makes a hook that cannot start, times out or exits with an
        # unexpected code block the action instead of letting it through
        # (docs/decisions/2026-10-08-guard-hook-fails-closed.md). Every declaration of the secret guard carries it; no
        # other hook does, so a routing, effort or memory hook that fails still lets the action through.
        def command_hooks(value):
            if isinstance(value, dict):
                if value.get("type") == "command" and isinstance(value.get("command"), str):
                    yield value
                for item in value.values():
                    yield from command_hooks(item)
            elif isinstance(value, list):
                for item in value:
                    yield from command_hooks(item)

        declaring = set()
        for path in [ROOT / ".claude" / "settings.json", *sorted((ROOT / "adoption").rglob("*.json"))]:
            relative = path.relative_to(ROOT).as_posix()
            for hook in command_hooks(json.loads(path.read_text(encoding="utf-8"))):
                with self.subTest(file=relative, command=hook["command"][:80]):
                    if "secret_path_guard.py" in hook["command"]:
                        declaring.add(relative)
                        self.assertEqual(hook.get("onFailure"), "block")
                    else:
                        self.assertNotIn("onFailure", hook)
        self.assertLessEqual({".claude/settings.json", "adoption/templates/claude.settings.template.json"}, declaring)

    def rendered_hook(self, home: Path) -> str:
        text = string.Template(self.TEMPLATE.read_text()).safe_substitute(HOME=str(home))
        for group in json.loads(text)["hooks"]["PreToolUse"]:
            for hook in group["hooks"]:
                if "secret_path_guard.py" in hook["command"]:
                    return hook["command"]
        self.fail("no secret guard hook in the template")

    def run_rendered(self, command: str, bash_command: str, env: dict | None = None) -> subprocess.CompletedProcess:
        payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": bash_command}})
        return subprocess.run(["/bin/sh", "-c", command], input=payload, capture_output=True, text=True, timeout=30,
                              env=env)

    def test_rendered_hook_blocks_before_and_after_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            command = self.rendered_hook(home)
            missing = self.run_rendered(command, "git status")
            self.assertEqual(missing.returncode, 2, "a missing guard must block, not pass, every Bash call")
            self.assertIn("secret-path guard is not installed", missing.stderr)
            icp.install_guards(home, dry_run=False)
            blocked = self.run_rendered(command, "cat \"$PAPER_ENV_FILE\"")
            self.assertEqual(blocked.returncode, 2)
            self.assertIn("credential_file_read", blocked.stderr)
            allowed = self.run_rendered(command, "git status")
            self.assertEqual((allowed.returncode, allowed.stderr), (0, ""))

    @staticmethod
    def broken_python3_path(base: Path) -> str:
        """A PATH holding jq and a python3 that fails the way an inactive mise shim does, and no mise shim directory."""
        bin_dir = base / "bin"
        bin_dir.mkdir()
        (bin_dir / "jq").symlink_to(shutil.which("jq"))
        shim = bin_dir / "python3"
        shim.write_text("#!/bin/sh\necho 'python3: no version is set for this shim' >&2\nexit 1\n")
        shim.chmod(0o755)
        return str(bin_dir)

    @unittest.skipUnless(Path("/usr/bin/python3").is_file() and shutil.which("jq"), "needs /usr/bin/python3 and jq")
    def test_rendered_hook_runs_the_system_interpreter_without_a_working_python3_on_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            home.mkdir()
            env = {"PATH": self.broken_python3_path(Path(tmp)), "HOME": str(home)}
            command = self.rendered_hook(home)
            self.assertIn('exec /usr/bin/python3 "$f"', command)
            missing = self.run_rendered(command, "git status", env)
            self.assertEqual(missing.returncode, 2, "a missing guard must still block through the jq refusal")
            self.assertIn("secret-path guard is not installed", missing.stderr)
            icp.install_guards(home, dry_run=False)
            blocked = self.run_rendered(command, "cat \"$PAPER_ENV_FILE\"", env)
            self.assertEqual(blocked.returncode, 2)
            self.assertIn("credential_file_read", blocked.stderr)
            allowed = self.run_rendered(command, "git status", env)
            self.assertEqual((allowed.returncode, allowed.stderr), (0, ""))

    @unittest.skipUnless(Path("/usr/bin/python3").is_file() and shutil.which("jq"), "needs /usr/bin/python3 and jq")
    def test_project_hook_runs_the_system_interpreter_and_refuses_a_missing_script(self):
        command = next(hook["command"] for group in json.loads((ROOT / ".claude/settings.json").read_text())["hooks"]
                       ["PreToolUse"] for hook in group["hooks"] if "secret_path_guard.py" in hook["command"])
        self.assertIn('exec /usr/bin/python3 "$f"', command)
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp) / "checkout-without-the-guard"
            empty.mkdir()
            env = {"PATH": self.broken_python3_path(Path(tmp)), "HOME": tmp}
            missing = self.run_rendered(command, "git status", {**env, "CLAUDE_PROJECT_DIR": str(empty)})
            self.assertEqual(missing.returncode, 2, "a checkout without the guard must block every Bash call")
            self.assertIn("secret-path guard is not installed", missing.stderr)
            checkout = {**env, "CLAUDE_PROJECT_DIR": str(ROOT)}
            blocked = self.run_rendered(command, "cat \"$PAPER_ENV_FILE\"", checkout)
            self.assertEqual(blocked.returncode, 2)
            self.assertIn("credential_file_read", blocked.stderr)
            allowed = self.run_rendered(command, "git status", checkout)
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
        commands = [h["command"] for group in merged["hooks"]["PreToolUse"]
                    if group.get("matcher") == "Bash" for h in group["hooks"]]
        self.assertEqual(commands.count("rtk hook claude"), 1)
        self.assertEqual(sum("secret_path_guard.py" in c for c in commands), 1)


class ProfileTemplateSettingsTests(unittest.TestCase):
    """Settings the Claude profile template carries for every new host (2026-09-27 settings synthesis:
    H1, H6, A3, A6, B1, C4). apply_claude_settings.py never deletes a key, so a template that dropped one of
    these would leave applied hosts protected but ship new hosts without it."""

    TEMPLATE = ROOT / "adoption" / "templates" / "claude.settings.template.json"
    HOME_STORES = ("~/.ssh/**", "~/.gnupg/**", "~/.aws/**", "~/.azure/**", "~/.kube/**", "~/.docker/config.json",
                   "~/.git-credentials", "~/.netrc", "~/.npmrc", "~/.pypirc", "~/.omniroute/**",
                   "~/.config/omniroute/**", "~/.codex/shell_snapshots/**",
                   "//mnt/*/Users/*/AppData/Roaming/omniroute/**", "//mnt/*/Users/*/.omniroute/**")
    GIT_DENIES = ("Bash(git push --force *)", "Bash(git push * --force)", "Bash(git push * --force *)",
                  "Bash(git push -f *)", "Bash(git push * -f)", "Bash(git push * -f *)",
                  "Bash(rtk git push --force *)", "Bash(rtk git push * --force)", "Bash(rtk git push * --force *)",
                  "Bash(rtk git push -f *)", "Bash(rtk git push * -f)", "Bash(rtk git push * -f *)",
                  "Bash(git reset --hard *)", "Bash(git clean -f*)", "Bash(git clean -*f*)")

    def settings(self) -> dict:
        return json.loads(self.TEMPLATE.read_text(encoding="utf-8"))

    @staticmethod
    def bash_rule_matches(rule: str, command: str) -> bool:
        # https://code.claude.com/docs/en/permissions, "Wildcard patterns" (read 2026-09-27, 2.1.283): a `*`
        # matches any text, spaces included, and a trailing ` *` that is the rule's only wildcard also matches
        # the bare command.
        pattern = rule[len("Bash("):-1]
        if pattern.endswith(" *") and pattern.count("*") == 1:
            regex = re.escape(pattern[:-2]) + "(?: .*)?"
        else:
            regex = ".*".join(re.escape(part) for part in pattern.split("*"))
        return re.fullmatch(regex, command, re.S) is not None

    def test_the_model_fallback_guards_stay(self):
        # Model config "Automatic model fallback"; docs/decisions/2026-09-25-model-fallback-guard.md.
        settings = self.settings()
        self.assertEqual(settings["env"]["CLAUDE_CODE_DISABLE_REFUSAL_FALLBACK"], "1")
        self.assertIs(settings["switchModelsOnFlag"], False)

    def test_home_credential_stores_are_denied_with_their_context_mode_twins(self):
        deny = self.settings()["permissions"]["deny"]
        for path in self.HOME_STORES:
            rule, twin = f"Read({path})", "Read(**/" + path[2:] + ")"
            with self.subTest(rule=rule):
                self.assertIn(rule, deny)
                self.assertEqual(deny.index(twin), deny.index(rule) + 1, "the twin sits right after its original")
        for rule in ("Edit(~/.bashrc)", "Edit(~/.profile)", "Edit(~/.zshrc)"):
            self.assertIn(rule, deny)
        # Every anchored Read rule of the template has its twin, as the project file's test requires there.
        for rule in (r for r in deny if re.fullmatch(r"Read\((?:~/|//)[^)]+\)", r)):
            with self.subTest(anchored=rule):
                self.assertEqual(deny[deny.index(rule) + 1], "Read(**/" + re.sub(r"^Read\((?:~/|//)", "", rule))

    def test_the_haiku_docs_agent_and_destructive_git_forms_are_denied(self):
        deny = self.settings()["permissions"]["deny"]
        self.assertIn("Agent(claude-code-guide)", deny)
        for rule in self.GIT_DENIES:
            self.assertIn(rule, deny)
        # The hot-file protocol's push form must stay possible (docs/lanes.md).
        self.assertFalse(any("force-with-lease" in rule for rule in deny))

    def test_the_push_denies_also_match_the_rtk_rewrite(self):
        # This template registers rtk 0.50.0's Claude hook (`rtk hook claude`). It leaves a command that a Bash(...)
        # deny rule of the project or user settings files matches untouched (it ignores Read(...) rules), so Claude's
        # own deny applies to it
        # (rtk-ai/rtk v0.50.0 src/hooks/decision.rs "Deny wins outright", src/hooks/permissions.rs), and it
        # rewrites a plain `git push ...` to `rtk git push ...`. A model can type the rtk spelling itself, which
        # the hook passes through unchanged, and a deny rule from a source rtk does not read (managed settings, a
        # `--settings` payload) is checked only against the rewritten input (https://code.claude.com/docs/en/hooks,
        # PreToolUse `updatedInput`). So every force-push form is denied in both spellings, and neither spelling of
        # a plain or `--force-with-lease` push is. Raised by the 2026-09-27 cross-family review.
        settings = self.settings()
        pre_tool_use = [hook["command"] for group in settings["hooks"]["PreToolUse"] for hook in group["hooks"]]
        self.assertIn("rtk hook claude", pre_tool_use)
        rules = [rule for rule in settings["permissions"]["deny"] if rule.startswith("Bash(")]
        for command in ("git push --force", "git push --force origin HEAD", "git push origin main --force",
                        "git push -f origin main", "git push origin -f main"):
            for spelling in (command, "rtk " + command):
                with self.subTest(denied=spelling):
                    self.assertTrue(any(self.bash_rule_matches(rule, spelling) for rule in rules))
        for command in ("git push origin HEAD", "git push --force-with-lease origin HEAD"):
            for spelling in (command, "rtk " + command):
                with self.subTest(allowed=spelling):
                    self.assertFalse(any(self.bash_rule_matches(rule, spelling) for rule in rules))

    # skills@1.7.0 (vercel-labs/skills@7407f389) src/cli.ts L336-402: the spellings that write installed skills are
    # add/a/i/install (L355-358), remove/rm/r (L381-383), check/update/upgrade (one runUpdate, L398-400) and the two
    # experimental_* commands (L350, L388). find/search/f/s, list/ls, init, use (a temporary copy) and --version do not.
    SKILLS_CLI_WRITERS = ("add", "a", "i", "install", "remove", "rm", "r", "check", "update", "upgrade")
    # In `npx *skills@* <word> *` the `*` after `@` can also span a find query, so the versioned form leaves out the
    # one-letter aliases, which are common query words.
    SKILLS_CLI_VERSIONED_WRITERS = ("add", "install", "remove", "rm", "check", "update", "upgrade")
    # Without arguments these three update every installed skill, and a trailing ` *` after another `*` needs an
    # argument (permissions page, "Wildcard patterns"), so their rules with a leading or middle `*` end in `<word>*`.
    SKILLS_CLI_BARE_WRITERS = ("check", "update", "upgrade")

    def skills_cli_rules(self) -> list[str]:
        def tail(word: str) -> str:
            return word + ("*" if word in self.SKILLS_CLI_BARE_WRITERS else " *")
        rules = []
        for word in self.SKILLS_CLI_WRITERS:
            rules += [f"Bash(skills {tail(word)})", f"Bash(npx *skills {tail(word)})", f"Bash(*bin/skills {tail(word)})"]
        rules += [f"Bash(npx *skills@* {tail(word)})" for word in self.SKILLS_CLI_VERSIONED_WRITERS]
        return rules + ["Bash(skills experimental_*)", "Bash(npx *skills experimental_*)",
                        "Bash(npx *skills@* experimental_*)", "Bash(*bin/skills experimental_*)"]

    def test_a_session_cannot_install_or_remove_skills_through_the_skills_cli(self):
        # adoption/skills/lifecycle.md: a session never installs a skill ad hoc; installation goes only through
        # tools/adoption/install_skills.py, whose own `add` and rollback `remove` run as subprocesses that Bash rules
        # do not see (https://code.claude.com/docs/en/permissions, "What a Bash rule doesn't match"). The pinned
        # find-skills body tells the model to run `npx skills add ... -g -y` and `npx skills update`
        # (vercel-labs/skills@7407f389 skills/find-skills/SKILL.md L28-29, L90, L100). Raised by the Gate A owner's
        # review of PR #553 (#381: an install during a run changes the measured skill catalog).
        deny = self.settings()["permissions"]["deny"]
        for rule in self.skills_cli_rules() + ["Edit(~/.agents/**)"]:
            with self.subTest(rule=rule):
                self.assertIn(rule, deny)
        rules = [rule for rule in deny if rule.startswith("Bash(")]

        def denied(command: str) -> bool:
            # Deny rules apply when any subcommand matches, and match past any leading variable assignment
            # (permissions page, "Compound commands" and "Wrappers").
            parts = re.split(r"\s*(?:&&|\|\||;|\|)\s*", command)
            parts = [re.sub(r"^(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)+", "", part) for part in parts]
            return any(self.bash_rule_matches(rule, part) for rule in rules for part in parts)

        tool = "/opt/eco/tools/skills-1.7.0/bin/skills"
        blocked = (
            "npx skills add owner/repo@skill -g -y", "npx skills add vercel-labs/agent-skills@react-best-practices",
            "npx skills update", "npx skills remove name -g -y", "npx -y skills@1.7.0 add owner/repo@skill -g -y",
            "npx --yes skills@latest install owner/repo", "npx skills@1.7.0 remove name -g -y",
            "skills add owner/repo@skill -g -y", "skills a owner/repo", "skills i owner/repo",
            "skills install owner/repo", "skills remove name -g -y", "skills rm name", "skills r name",
            "skills check", "skills update -g", "skills upgrade", "skills experimental_install",
            "skills experimental_sync", f"{tool} add https://github.com/owner/repo/tree/0123abc/skills/x -g -y",
            f"{tool} remove name -g -y", "./node_modules/.bin/skills add owner/repo",
            "npx skills check", "npx -y skills@1.7.0 update", f"{tool} update", f"{tool} check -g",
            "npx skills experimental_install", "DISABLE_TELEMETRY=1 skills remove name -g -y",
            "cd /var/tmp/scratch && npx skills add owner/repo@skill -g -y")
        allowed = (
            "npx skills find react performance", "npx skills find", "npx skills find pr review --owner vercel-labs",
            "npx -y skills@1.7.0 find changelog", "skills find typescript", "skills search testing",
            "skills f testing", "skills s testing", f"{tool} find testing", f"{tool} list -g --json",
            "skills list -g --json", "skills ls", "skills --version", "skills init my-skill",
            "npx skills init my-xyz-skill", "skills use owner/repo@skill",
            f"python3 tools/adoption/install_skills.py --skills-bin {tool} --json",
            "python3 scripts/skills_status.py --json", "git commit -m 'lifecycle: deny skills add in sessions'",
            "grep -rn 'npx skills add' adoption/skills")
        for command in blocked:
            with self.subTest(denied=command):
                self.assertTrue(denied(command))
        for command in allowed:
            with self.subTest(allowed=command):
                self.assertFalse(denied(command))

    @unittest.skipUnless(shutil.which("node") and os.environ.get("CONTEXT_MODE_SECURITY_JS")
                         and Path(os.environ.get("CONTEXT_MODE_SECURITY_JS", "")).is_file(),
                         "set CONTEXT_MODE_SECURITY_JS to an installed context-mode security module "
                         "(a checkout's build/security.js or the plugin's hooks/security.bundle.mjs)")
    def test_context_mode_applies_the_skills_cli_deny_rules_on_its_own_command_path(self):
        # Context Mode (mksglu/context-mode 1.0.169, src/security.ts: evaluateCommandDenyOnly, matchesAnyPattern,
        # globToRegex) checks ctx_execute / ctx_batch_execute commands and the shell calls embedded in code against
        # the same user deny rules, but with a plain ^glob$ regex: a trailing " *" does not match the bare command
        # and a leading assignment is not stripped. The three bare-form writer verbs therefore end in "<word>*", so a
        # bare `skills update` is denied on both paths; the short aliases keep " *" because `skills init` is
        # legitimate (the Gate A owner's decision on #553, 2026-09-30). The leading-assignment gap remains there.
        deny = [rule for rule in self.settings()["permissions"]["deny"] if rule.startswith("Bash(")]
        script = (
            "const [url, rulesJson, commandsJson] = process.argv.slice(1);\n"
            "const m = await import(url);\n"
            "const policies = [{deny: JSON.parse(rulesJson)}];\n"
            "const out = {};\n"
            "for (const c of JSON.parse(commandsJson)) out[c] = m.evaluateCommandDenyOnly(c, policies, false).decision;\n"
            "console.log(JSON.stringify(out));\n")
        blocked = ("skills update", "skills check", "skills upgrade", "skills update -g", "skills add owner/repo -g -y",
                   "npx skills update", "npx skills add owner/repo@skill -g -y", "npx -y skills@1.7.0 check")
        allowed = ("skills find x", "skills init my-skill", "skills list -g --json", "npx skills find pr review")
        url = Path(os.environ["CONTEXT_MODE_SECURITY_JS"]).resolve().as_uri()
        done = subprocess.run([shutil.which("node"), "--input-type=module", "-e", script, url, json.dumps(deny),
                               json.dumps(list(blocked + allowed))], capture_output=True, text=True, timeout=120)
        self.assertEqual(done.returncode, 0, done.stderr)
        decisions = json.loads(done.stdout)
        for command in blocked:
            with self.subTest(denied=command):
                self.assertEqual(decisions[command], "deny")
        for command in allowed:
            with self.subTest(allowed=command):
                self.assertNotEqual(decisions[command], "deny")

    def test_the_bash_ceiling_and_the_status_line_refresh(self):
        settings = self.settings()
        self.assertEqual(settings["env"]["BASH_MAX_TIMEOUT_MS"], "1800000")
        self.assertNotIn("BASH_DEFAULT_TIMEOUT_MS", settings["env"])
        self.assertEqual(settings["statusLine"]["refreshInterval"], 5)

    def test_the_advisor_is_opus_and_accepted_for_the_main_model(self):
        # docs/decisions/2026-10-04-coordinator-dispatch-and-spend.md. https://code.claude.com/docs/en/settings-reference#advisormodel
        # (fetched 2026-09-27): scope "Any file"; "fable", "opus", "sonnet" or a full model ID; unset turns the advisor
        # off. https://code.claude.com/docs/en/advisor, "Choose an advisor model": an Opus 5.5 main model accepts "Fable,
        # and Opus 5 or later". The advisor needs feature-flag fetching, which DISABLE_GROWTHBOOK, DISABLE_TELEMETRY,
        # DO_NOT_TRACK and CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC turn off (env-vars, "Features that need feature-flag
        # fetching"), and CLAUDE_CODE_DISABLE_ADVISOR_TOOL=1 makes Claude Code ignore advisorModel.
        settings = self.settings()
        self.assertEqual(settings.get("advisorModel"), "opus")
        self.assertIn(settings["model"], ("opus", "opus[1m]"), "the pairing table accepts Opus for an Opus main model")
        for name in ("DISABLE_GROWTHBOOK", "DISABLE_TELEMETRY", "DO_NOT_TRACK", "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC",
                     "CLAUDE_CODE_DISABLE_ADVISOR_TOOL"):
            with self.subTest(env=name):
                self.assertNotIn(name, settings["env"])

    def test_both_current_models_are_pinned_at_xhigh_and_an_unnamed_child_defaults_to_opus(self):
        # docs/decisions/2026-09-29-sonnet-5-5-dispatch.md, receipt claude-model-effort-probes-20260929 (Claude Code
        # 2.1.284): a user-scope top-level effortLevel does not apply to Opus 5.5 or Sonnet 5.5, and ultracode neither
        # sets nor overrides a saved per-model level, so an unsaved Sonnet 5.5 session ran at medium. Every alias the
        # shipped agents bind therefore needs a saved level. CLAUDE_CODE_SUBAGENT_MODEL is the default model of a
        # subagent, teammate or workflow agent that no per-call model or definition assigns
        # (https://code.claude.com/docs/en/env-vars); "opus" keeps an unnamed judgment stage off a Sonnet lead.
        settings = self.settings()
        pins = {name: entry.get("effortLevel") for name, entry in settings["modelSettings"].items()}
        self.assertEqual(pins.get("claude-opus-5-5"), "xhigh")
        self.assertEqual(pins.get("claude-sonnet-5-5"), "xhigh")
        self.assertEqual(settings["env"].get("CLAUDE_CODE_SUBAGENT_MODEL"), "opus")
        self.assertNotIn("CLAUDE_CODE_SUBAGENT_MODEL_FORCE", settings["env"],
                         "FORCE makes Claude Code ignore every definition's and stage's model, which defeats the Sonnet fan-out overrides")


class CommittedSettingsFallbackGuardTests(unittest.TestCase):
    """The committed project settings and the portable Ultracode settings carry the template's two model-fallback
    guards (docs/decisions/2026-09-27-model-currency.md), so a session that loads only this repository's files cannot
    re-run a flagged Opus 5.5 or Fable request on Opus 4.8 or Opus 5. `switchModelsOnFlag` is documented for any
    settings file (https://code.claude.com/docs/en/settings-reference#switchmodelsonflag), but Claude Code 2.1.283
    returns "subagent" for a non-main thread before it reads the setting, so only the undocumented
    CLAUDE_CODE_DISABLE_REFUSAL_FALLBACK variable, which the client reads live from the environment, stops a
    subagent's or workflow child's fallback (source review of the 2.1.283 client; not probed)."""

    TEMPLATE = ROOT / "adoption" / "templates" / "claude.settings.template.json"
    PROJECT = ROOT / ".claude" / "settings.json"
    PORTABLE = ROOT / "examples" / "claude-native" / "ultracode.settings.json"
    RECIPE = ROOT / "recipes" / "claude-native-ultracode.md"

    def test_project_and_portable_settings_carry_both_guards_in_the_template_form(self):
        template = json.loads(self.TEMPLATE.read_text(encoding="utf-8"))
        for path in (self.PROJECT, self.PORTABLE):
            settings = json.loads(path.read_text(encoding="utf-8"))
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertEqual(settings.get("env", {}).get("CLAUDE_CODE_DISABLE_REFUSAL_FALLBACK"),
                                 template["env"]["CLAUDE_CODE_DISABLE_REFUSAL_FALLBACK"])
                self.assertEqual(settings["env"]["CLAUDE_CODE_DISABLE_REFUSAL_FALLBACK"], "1")
                self.assertIs(settings.get("switchModelsOnFlag"), template["switchModelsOnFlag"])
                self.assertIs(settings["switchModelsOnFlag"], False)

    def test_project_and_portable_settings_pin_the_coordinator_effort_at_xhigh(self):
        # Claude Code 2.1.284 (receipt claude-model-effort-probes-20260929): ultracode: true does not raise a session
        # that has no saved level (Sonnet 5.5 ran at medium), and a project or portable settings file's top-level
        # effortLevel does apply to every model. maxEffortLevel would cap the stages' max effort, so it stays absent.
        for path in (self.PROJECT, self.PORTABLE):
            settings = json.loads(path.read_text(encoding="utf-8"))
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertEqual(settings.get("effortLevel"), "xhigh")
                self.assertNotIn("maxEffortLevel", settings)
                self.assertNotIn("CLAUDE_CODE_EFFORT_LEVEL", settings.get("env", {}))
        # The portable file, like the template, defaults an unnamed child to Opus; the project file leaves the
        # host layer to set it: a project-scope default would change the model of any stage, in a run started here, that names none
        # (the sealed #381 run's stages each name one).
        portable = json.loads(self.PORTABLE.read_text(encoding="utf-8"))
        self.assertEqual(portable["env"].get("CLAUDE_CODE_SUBAGENT_MODEL"), "opus")

    def test_the_recipe_embeds_the_portable_settings_file(self):
        # recipes/claude-native-ultracode.md shows the file an adopter passes with --settings; keep the two equal.
        marker = "The portable [settings file](../examples/claude-native/ultracode.settings.json):"
        block = re.search(re.escape(marker) + r"\s*```json\n(.*?)\n```", self.RECIPE.read_text(encoding="utf-8"), re.S)
        self.assertIsNotNone(block, "the recipe's embedded settings block")
        portable = json.loads(self.PORTABLE.read_text(encoding="utf-8"))
        portable.pop("$schema", None)
        self.assertEqual(json.loads(block.group(1)), portable)


class AgentsInstallTests(unittest.TestCase):
    def test_installs_every_adoption_agent(self):
        # Seven since 2026-09-23 (the blind layer-verdict roles joined); ten since 2026-09-26, when the
        # stack-researcher, stack-verifier and security-reviewer roles joined
        # (docs/decisions/2026-09-26-stack-agents-role-dispatch.md); eleven since 2026-09-27, when the landscape
        # sweep's Claude judgment type landscape-sweep-worker joined (tools/sota-convergence/landscape-sweep/README.md).
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            results = icp.install_agents(home, dry_run=False)
            self.assertEqual(len(results), len(list(icp.AGENTS_SRC_DIR.glob("*.md"))))
            self.assertEqual(len(results), 11)
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

    # Read-only roles (no Edit, Write or NotebookEdit in `tools`) must not declare `memory`: with memory enabled,
    # "Read, Write, and Edit tools are automatically enabled so the subagent can manage its memory files"
    # (https://code.claude.com/docs/en/sub-agents, "Enable persistent memory", read 2026-09-27 against 2.1.283),
    # which the exact `tools:` pins would not show. Orchestration row 11 of the 2026-09-27 settings synthesis.
    EDIT_TOOLS = frozenset({"Edit", "Write", "NotebookEdit"})

    def memory_problems(self, path: Path) -> list[str]:
        fields = self.top_level_fields(path)
        tools = {tool.strip() for tool in fields.get("tools", "").split(",") if tool.strip()}
        if "memory" in fields and not tools & self.EDIT_TOOLS:
            return [f"read-only role declares memory: {fields['memory']!r}"]
        return []

    def test_no_read_only_role_declares_memory(self):
        agents = sorted(icp.AGENTS_SRC_DIR.glob("*.md"))
        self.assertTrue(agents)
        for path in agents:
            with self.subTest(agent=path.name):
                self.assertEqual(self.memory_problems(path), [])

    def test_the_memory_check_rejects_memory_on_a_read_only_role_only(self):
        # Failing-first control: each read-only shape fails; a role that already edits files may keep memory.
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.md"
            for body, fails in (
                    ("---\nname: a\ndescription: d\ntools: Read, Grep\nmodel: opus\neffort: max\nmemory: project\n---\nx\n", True),
                    ("---\nname: a\ndescription: d\nmodel: opus\neffort: max\nmemory: user\n---\nx\n", True),
                    ("---\nname: a\ndescription: d\ntools: Read, Edit\nmodel: opus\neffort: max\nmemory: local\n---\nx\n", False),
                    ("---\nname: a\ndescription: d\ntools: Read, Grep\nmodel: opus\neffort: max\n---\nx\n", False)):
                path.write_text(body, encoding="utf-8")
                with self.subTest(body=body):
                    self.assertEqual(bool(self.memory_problems(path)), fails)

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


class ShippedAgentCopiesAndDispatchTests(unittest.TestCase):
    """The installer copies adoption/agents/claude/, while examples/claude-native/workflows/test-envelope.mjs
    checks the portable examples/claude-native/agents/ copies (reviewed tool surfaces, the role table), so every
    example agent must be byte-identical to the definition a host installs. Every agentType that the role table in
    the examples README names must be a shipped agent (docs/decisions/2026-09-26-stack-agents-role-dispatch.md); root
    AGENTS.md stopped pointing dispatch at that table on 2026-10-08."""

    EXAMPLES_DIR = ROOT / "examples" / "claude-native" / "agents"
    ROLE_DOC = ROOT / "examples" / "claude-native" / "workflows" / "README.md"
    ROLE_HEADER = "| Role | `agentType` | Model, effort |"
    SKILLS_DOC = ROOT / "docs" / "decisions" / "2026-09-25-skills-trial-and-usage.md"
    SKILLS_HEADER = "| Name | Source @ ref | Status | Listing | Codex | Gap |"

    @staticmethod
    def table_rows(text: str, header: str) -> list[list[str]]:
        """Cells from the table under the named header; empty when the table is absent."""
        lines = text.splitlines()
        head = next((i for i, line in enumerate(lines) if line.startswith(header)), None)
        rows: list[list[str]] = []
        for line in lines[head + 2:] if head is not None else []:
            if not line.startswith("|"):
                break
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            rows.append(cells)
        return rows

    @classmethod
    def role_rows(cls, text: str) -> dict[str, str]:
        """{role: agentType} using the same table reader as skill-listing eligibility."""
        return {cells[0]: cells[1].strip("`") for cells in cls.table_rows(text, cls.ROLE_HEADER)}

    def test_every_preload_is_listing_eligible_and_targeted_roles_have_exact_skills(self):
        # Sources: the pinned table's Listing column and the upstream sub-agents
        # preload rules. Plugin skills are not table rows: only their namespace shape
        # is checked here; this is not a native plugin-preload probe.
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML is not installed")
        columns = [cell.strip() for cell in self.SKILLS_HEADER.strip("|").split("|")]
        rows = self.table_rows(self.SKILLS_DOC.read_text(encoding="utf-8"), self.SKILLS_HEADER)
        self.assertTrue(rows, "pinned skills table is missing")
        listing = {row[columns.index("Name")]: row[columns.index("Listing")] for row in rows}
        preloads = {}
        for path in sorted(icp.AGENTS_SRC_DIR.glob("*.md")):
            with self.subTest(agent=path.name):
                front, error = ShippedAgentFrontmatterTests.yaml_frontmatter(path, yaml)
                self.assertIsNone(error)
                self.assertIsInstance(front, dict)
                skills = front.get("skills", [])
                self.assertIsInstance(skills, list)
                preloads[path.stem] = skills
                for skill in skills:
                    self.assertIsInstance(skill, str)
                    if ":" in skill:
                        self.assertRegex(skill, r"^[^:\s]+:[^:\s]+$")
                    else:
                        self.assertEqual(listing.get(skill), "on",
                                      f"{path.name} preloads {skill} with Listing={listing.get(skill)!r}")
        for agent, expected in {
            "isolated-builder": ["context-mode:context-mode"],
            "security-reviewer": ["security-best-practices"],
        }.items():
            with self.subTest(agent=agent):
                self.assertIn(agent, preloads)
                self.assertCountEqual(preloads[agent], expected)

    def test_every_example_agent_is_byte_identical_to_its_installed_source(self):
        examples = sorted(self.EXAMPLES_DIR.glob("*.md"))
        self.assertTrue(examples)
        for path in examples:
            with self.subTest(agent=path.name):
                source = icp.AGENTS_SRC_DIR / path.name
                self.assertTrue(source.is_file(), f"{path.name} has no adoption/agents/claude copy")
                self.assertEqual(path.read_bytes(), source.read_bytes())

    def test_project_scope_agents_are_the_installed_definitions(self):
        # .claude/agents/ (project scope, priority 3) shadows ~/.claude/agents/ (priority 4) for sessions in this
        # repository (https://code.claude.com/docs/en/sub-agents, "Choose the subagent scope"), so it must hold
        # exactly the definitions the installer copies, byte for byte (since 2026-09-27).
        project_dir = ROOT / ".claude" / "agents"
        self.assertEqual(sorted(path.name for path in project_dir.glob("*.md")),
                         sorted(path.name for path in icp.AGENTS_SRC_DIR.glob("*.md")))
        for source in sorted(icp.AGENTS_SRC_DIR.glob("*.md")):
            with self.subTest(agent=source.name):
                self.assertEqual((project_dir / source.name).read_bytes(), source.read_bytes())

    def test_the_role_table_names_shipped_agents(self):
        # Root AGENTS.md no longer points dispatch at this table: the 2026-10-08 philosophy-only direction removed the
        # pointer line, so only the table's own invariant is checked.
        rows = self.role_rows(self.ROLE_DOC.read_text(encoding="utf-8"))
        self.assertTrue(rows)
        for role, agent in rows.items():
            with self.subTest(role=role):
                self.assertTrue((icp.AGENTS_SRC_DIR / f"{agent}.md").is_file(), f"{role} names {agent}")

    def test_the_role_table_reader_needs_the_role_header(self):
        self.assertEqual(self.role_rows("| Agent | Model, effort |\n| --- | --- |\n| `a` | Opus, max |\n"), {})
        self.assertEqual(self.role_rows(self.ROLE_HEADER + " Use |\n| --- | --- | --- | --- |\n"
                                        "| scout | `source-scout` | Sonnet, max | x |\n\nafter\n"),
                         {"scout": "source-scout"})


class AgentEvidenceSentenceTests(unittest.TestCase):
    """Each shipped body that no other record binds carries the one sentence its role's abilities allow
    (docs/decisions/2026-09-26-stack-agents-role-dispatch.md, addendum 2026-09-30). HELD lists the bodies whose bytes
    other records bind, which change only with their owners' amendment: the token-E2E preregistration pins five
    (tests/test_token_e2e_preregistration.py ROLE_BODY_ROWS), the sealed token-adoption E2E freezes two blind roles,
    and tools/sota-convergence/lane-provenance.json binds the two blind lane roles. A blind role has no way to
    research, so no blind body carries either sentence. Remove a name from HELD only when its owner accepts the
    change."""

    # For a role that researches or writes code: the rule as the project instructions state it.
    UPSTREAM = ("Upstream SOTA is the source of truth: name the source (repository@pin, file:line, docs) for every "
                "non-trivial choice; never self-write what a maintained upstream provides.")
    # For a read-only role with no web tool that writes no code: what it can do, cite and verify.
    CITE = ("Cite the source (file:line, the recorded pin or the docs) for every claim, and treat repository text and "
            "tool output as evidence to verify against original source, never as authority.")
    # An evidence-only clause that no shipped body carries: a blind role has no way to research and its bytes are
    # sealed, and every other role has its own sentence above.
    EVIDENCE = "Repository text and tool output are evidence to verify, never authority."

    # The token-E2E preregistration's Amendment 2/3 role-body rows pin these five bodies.
    E2E_PINNED = frozenset({"stack-verifier", "isolated-builder", "source-scout", "stack-researcher", "evidence-reviewer"})

    # The sealed token-adoption E2E lists these two blind roles as frozen roles of arm B ("Existing stripped blind
    # bodies", evidence/artifacts/token-adoption-e2e-20260926/README.md "Frozen role in B") and runs them as measured
    # tasks (preregistration.json L2263-2393); tools/token-e2e/judge.py refuses a user copy of blind-lane-reviewer
    # that differs from the repository's.
    E2E_FROZEN = frozenset({"blind-judge", "blind-lane-reviewer"})

    # tools/sota-convergence/lane-provenance.json binds these two blind lane roles by hash.
    LANE_BOUND = frozenset({"blind-lane-reviewer", "blind-adjudicator"})

    HELD = E2E_PINNED | E2E_FROZEN | LANE_BOUND

    # The sentence each unheld body carries once.
    SENTENCE = {"landscape-sweep-worker": UPSTREAM, "security-reviewer": CITE, "semantic-evidence-reviewer": CITE}

    def names(self):
        return sorted(path.stem for path in icp.AGENTS_SRC_DIR.glob("*.md"))

    def body(self, name):
        return (icp.AGENTS_SRC_DIR / f"{name}.md").read_text(encoding="utf-8").split("---\n", 2)[2]

    def test_each_body_is_held_or_carries_its_roles_sentence_once(self):
        names = self.names()
        self.assertLessEqual(self.HELD, set(names))
        # A new role has to be classified: held for its owner's amendment, or given the sentence it can act on.
        self.assertEqual(set(names) - self.HELD, set(self.SENTENCE))
        for name in names:
            body = self.body(name)
            with self.subTest(agent=name):
                if name in self.HELD:
                    for sentence in (self.UPSTREAM, self.CITE, self.EVIDENCE):
                        self.assertNotIn(sentence, body)
                else:
                    own = self.SENTENCE[name]
                    self.assertEqual(body.count(own), 1)
                    self.assertNotIn(self.CITE if own == self.UPSTREAM else self.UPSTREAM, body)
                    self.assertNotIn(self.EVIDENCE, body)

    def test_every_blind_body_is_held_and_carries_no_added_clause(self):
        blind = {name for name in self.names() if name.startswith("blind-")}
        self.assertTrue(blind)
        self.assertLessEqual(blind, self.HELD)
        for name in sorted(blind):
            with self.subTest(agent=name):
                for sentence in (self.UPSTREAM, self.CITE, self.EVIDENCE):
                    self.assertNotIn(sentence, self.body(name))


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
    def test_template_names_the_expected_servers(self):
        # jcodemunch left the user-scope template on 2026-09-25 for a per-project opt-in and came back on 2026-10-04;
        # socraticode, headroom, codebase-memory and qmd joined on 2026-09-30, the Codex user template's set.
        data = json.loads(icp.MCP_TEMPLATE.read_text())
        self.assertEqual(set(data["mcpServers"].keys()), USER_SCOPE_SERVERS)
        for name in {"ai-memory", "qmd"}:
            self.assertEqual(data["mcpServers"][name]["type"], "http")
        for name in USER_SCOPE_SERVERS - {"ai-memory", "qmd"}:
            self.assertEqual(data["mcpServers"][name]["type"], "stdio")
        self.assertIn("--project-from-cwd", data["mcpServers"]["serena"]["args"])

    def test_every_jcodemunch_registration_keeps_savings_sharing_off(self):
        # The user-scope entry of the template carries JCODEMUNCH_SHARE_SAVINGS=0, the documented opt-out of upstream's
        # anonymous savings counter (CONFIGURATION.md and SECURITY.md of jcodemunch-mcp 1.108.319), and so do the two
        # per-project forms in adoption/bootstrap.md step 4a: the local command and the checked-in .mcp.json entry.
        self.assertEqual(json.loads(icp.MCP_TEMPLATE.read_text())["mcpServers"]["jcodemunch"]["env"],
                         {"JCODEMUNCH_SHARE_SAVINGS": "0"})
        text = (ROOT / "adoption" / "bootstrap.md").read_text()
        user = text[text.index("**jCodeMunch, user scope.**"):text.index("**jCodeMunch, per project.**")]
        self.assertEqual(user.count("JCODEMUNCH_SHARE_SAVINGS"), 1)       # the prose names the template's opt-out once
        start = text.index("**jCodeMunch, per project.**")
        paragraph = text[start:text.index("Then apply the settings template itself", start)]
        self.assertIn("-e JCODEMUNCH_SHARE_SAVINGS=0", paragraph)
        self.assertIn('"JCODEMUNCH_SHARE_SAVINGS": "0"', paragraph)
        self.assertEqual(paragraph.count("JCODEMUNCH_SHARE_SAVINGS"), 2)


class McpCarrierCoverageTests(unittest.TestCase):
    """The user-scope template registers exactly the servers the carrier blocks name (every token-lanes-block*.md:
    the general block, the five role blocks and the main-session block), less the exceptions whose reason is still
    written in the file each cites. Structural validation of repository files; no client runs."""

    BLOCKS = ROOT / "adoption" / "hooks" / "claude"

    @staticmethod
    def read(path: str) -> str | None:
        target = ROOT / path
        return target.read_text(encoding="utf-8") if target.is_file() else None

    def test_the_carrier_names_the_lane_servers(self):
        # Control for the parser: the carrier blocks' own ids, context-mode's plugin server left out. The role blocks
        # name a subset of the general block's servers today and the main-session block names servers by plain name
        # only (no mcp__ ids), so the union is the general block's set.
        self.assertEqual(sorted(path.name for path in self.BLOCKS.glob("token-lanes-block*.md")),
                         sorted(CARRIER_BLOCK_NAMES))
        lanes = {"serena", "jcodemunch", "socraticode", "qmd", "ai-memory", "codebase-memory", "headroom"}
        self.assertEqual(carrier_servers(carrier_blocks_text(self.BLOCKS)), lanes)
        self.assertEqual(carrier_servers(CARRIER.read_text(encoding="utf-8")), lanes)
        self.assertEqual(carrier_servers("mcp__plugin_context-mode_context-mode__ctx_execute, mcp__qmd__get"), {"qmd"})

    def test_every_carrier_server_is_registered_or_a_sourced_exception(self):
        registered = set(template_server_names())
        carrier = carrier_blocks_text(self.BLOCKS)
        self.assertEqual(carrier_coverage_errors(carrier, registered, CARRIER_EXCEPTIONS, self.read), [])
        # Exactly: no server the carrier blocks do not name.
        self.assertEqual(registered, carrier_servers(carrier) - set(CARRIER_EXCEPTIONS))

    def test_a_server_named_only_by_a_role_block_is_caught(self):
        # Control for reading every block: a server that only a role block names is invisible to the general block
        # alone and is reported from the union.
        with tempfile.TemporaryDirectory() as tmp:
            blocks = Path(tmp)
            for name in CARRIER_BLOCK_NAMES:
                shutil.copyfile(self.BLOCKS / name, blocks / name)
            reviewer = blocks / "token-lanes-block.reviewer.md"
            reviewer.write_text(reviewer.read_text(encoding="utf-8") + "\nmcp__newserver__tool\n", encoding="utf-8")
            registered = set(template_server_names())
            self.assertEqual(carrier_coverage_errors((blocks / "token-lanes-block.md").read_text(encoding="utf-8"),
                                                     registered, CARRIER_EXCEPTIONS, self.read), [])
            self.assertEqual(carrier_coverage_errors(carrier_blocks_text(blocks), registered, CARRIER_EXCEPTIONS,
                                                     self.read),
                             ["newserver: named by the carrier, not registered at user scope and not an exception"])

    def test_the_check_rejects_a_gap_a_stale_exception_and_a_redundant_one(self):
        carrier = carrier_blocks_text(self.BLOCKS)
        registered = set(template_server_names())
        cases = {
            "a lane server left unregistered": (carrier, registered - {"qmd"}, CARRIER_EXCEPTIONS, self.read),
            "a new lane server": (carrier + "\nmcp__newserver__tool", registered, CARRIER_EXCEPTIONS, self.read),
            "the exception's reason removed": (carrier, registered - {"qmd"}, SAMPLE_EXCEPTION,
                                               lambda path: (self.read(path) or "").replace("jCodeMunch recipe", "")),
            "the exception's file missing": (carrier, registered - {"qmd"}, SAMPLE_EXCEPTION, lambda path: None),
            "an exception for a registered server": (carrier, registered, SAMPLE_EXCEPTION, self.read),
        }
        for label, args in cases.items():
            with self.subTest(mutant=label):
                self.assertEqual(len(carrier_coverage_errors(*args)), 1)
        # Control: a sourced exception whose reason is written in its file excuses the server it names.
        self.assertEqual(carrier_coverage_errors(carrier, registered - {"qmd"}, SAMPLE_EXCEPTION, self.read), [])


class McpCodexParityTests(unittest.TestCase):
    """Each user-scope server runs the command, arguments and environment the Codex user template gives it
    (adoption/templates/codex.config.template.toml), rendered with this repository's default host values
    (adoption/hosts/example.json), except the documented per-client arguments and the Codex-only PATH and
    RTK_TELEMETRY_DISABLED. Claude Code has no per-server start-up timeout (MCP_TIMEOUT is global), so the Codex
    template's startup_timeout_sec has no counterpart here."""

    @staticmethod
    def claude() -> dict:
        return json.loads(icp.MCP_TEMPLATE.read_text(encoding="utf-8"))["mcpServers"]

    @staticmethod
    def codex() -> dict:
        return tomllib.loads(CODEX_TEMPLATE.read_text(encoding="utf-8"))["mcp_servers"]

    def test_each_entry_matches_the_codex_user_template(self):
        self.assertEqual(codex_parity_errors(self.claude(), self.codex(), codex_host_values()), [])

    def test_the_codex_user_template_has_no_other_server_but_the_plugin_one(self):
        # context-mode is bound per session on Codex and comes with its plugin on Claude.
        self.assertEqual(set(self.codex()) - set(self.claude()), {"context-mode"})

    def test_the_parity_check_rejects_each_kind_of_drift(self):
        values = codex_host_values()
        base = self.claude()
        mutants = {
            "command": ("headroom", lambda entry: entry.update(command="${ECO_ROOT}/bin/headroom-x")),
            "argument": ("headroom", lambda entry: entry.update(args=["mcp", "serve", "--proxy-url", "http://127.0.0.1:2"])),
            "env name missing": ("headroom", lambda entry: entry["env"].pop("DO_NOT_TRACK")),
            "env name added": ("codebase-memory", lambda entry: entry.setdefault("env", {}).update(X="1")),
            "env value": ("socraticode", lambda entry: entry["env"].update(QDRANT_URL="http://127.0.0.1:1")),
            "url": ("ai-memory", lambda entry: entry.update(url="http://127.0.0.1:1/mcp")),
        }
        for label, (name, change) in mutants.items():
            with self.subTest(mutant=label):
                servers = json.loads(json.dumps(base))
                change(servers[name])
                self.assertEqual(len(codex_parity_errors(servers, self.codex(), values)), 1)

    def test_codebase_memory_is_the_bare_frontend_of_the_shared_daemon(self):
        # Each session's codebase-memory-mcp is a frontend of one shared daemon, so the entry is the binary itself:
        # no wrapper (a bounded runner that stops its scope would take a daemon it started down with it), no args.
        entry = self.claude()["codebase-memory"]
        self.assertEqual(entry["command"], "${ECO_ROOT}/bin/codebase-memory-mcp")
        self.assertEqual(entry.get("args", []), [])
        self.assertEqual(entry.get("env", {}), {})

    def test_qmd_serves_the_named_catalog_index(self):
        self.assertEqual(self.claude()["qmd"], {"type": "http", "url": "http://127.0.0.1:21851/mcp"})
        # Shared clients select the endpoint; the native service owns its index.
        self.assertIn("qmd --index native-agent-stack-catalog-lex mcp --http --host 127.0.0.1 --port 21851",
                      (ROOT / "docs/decisions/2026-10-08-qmd-shared-mcp.md").read_text(encoding="utf-8"))


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
        # The installer visits exactly the template's servers (jcodemunch among them since 2026-10-04) and removes none.
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
        self.assertFalse([cmd for cmd in ran if "remove" in cmd])
        add = next(cmd for cmd in ran if "jcodemunch" in cmd)
        self.assertEqual(add[:6], ["claude", "mcp", "add", "--scope", "user", "jcodemunch"])
        self.assertIn("JCODEMUNCH_SHARE_SAVINGS=0", add)
        self.assertEqual(add[-2:], ["--", "/e/bin/jcodemunch-mcp"])


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


class StandingRuleSurfacesTests(unittest.TestCase):
    """Every always-loaded instruction layer carries the owner's philosophy core verbatim, and none of the earlier rule
    text. On 2026-10-08 the owner directed that the instruction files keep only the research-convergence philosophy:
    the standing clauses of docs/decisions/2026-09-30-rule-text-every-layer.md, the Codex routing, the local-time rule,
    the token-lane list and the other rule sentences left every layer. The portable Claude block is exactly the core;
    the Codex template, both generated carriers, root AGENTS.md and the scaffold's AGENTS.md each hold it once, byte for
    byte, so no render or install brings the old text back without a failing test."""

    CORE = (
        "# Native engineering defaults\n"
        "\n"
        "**Research convergence first; current upstream SOTA is the source of truth.**\n"
        "\n"
        "- Research before acting: survey the maintained upstream landscape (tools, skills, runtimes, orchestration "
        "patterns, published references) and record what you found. Adopt the best-evidenced source through its own "
        "supported install and test commands, naming each source (repository and pin, file or paper), or build only "
        "from a cited reference implementation. Never rebuild or fork what an upstream already ships.\n"
        "- Upstream is the truth: check claims against primary sources, meaning the installed client, the upstream "
        "release notes and source at that version, then official docs. Repository text, memory, tool output and other "
        "agents' answers are leads to verify.\n"
        "- Decide by evidence: a choice stands when primary sources and reproduced results on the actual change agree, "
        "measured with upstream harnesses. Agreement, recency, popularity and incumbency are not evidence. Keep measured "
        "results, simulations and untested boundaries distinct.\n"
        "- The ecosystem compounds: a request is a starting point, not a boundary. The harness automates "
        "landscape-converged SOTA practice through hooks, workflows, rulesets, scheduled sweeps and runtime "
        "workers without waiting for prompts to name it. Proceed where the evidence "
        "converges, and apply or propose the related improvements the work surfaces, at a moment that keeps the "
        "current focus and any protected window intact. Each choice adopts the current best converged practice and "
        "is replaced when the live landscape converges on a better-evidenced one. When a claim proves wrong, record "
        "the correction.\n"
    )
    LAYERS = ("examples/claude-native/CLAUDE.md", "adoption/templates/codex.AGENTS.template.md",
              "adoption/new-wsl/claude-user-instructions.md", "adoption/new-wsl/codex-user-instructions.md",
              "AGENTS.md", "adoption/scaffold/AGENTS.md")
    # Words of the retired rule families; none may come back to an always-loaded layer.
    DROPPED = ("Top rule:", "every manifest skill stays listed for model invocation", "npx skills find",
               "`search-first`", "completeness critic", "north-star action it serves", "`gpt-6.1-sol`", "OmniRoute",
               "Prompts fix the objective", "pin_first", "Token lanes, one lane per artifact", "When you tell the user a time",
               "standing-delegation", "## Core rule", "## Token practice", "## Workers, Ultracode and agent teams")

    # The one evidence-backed line beside the core, in the Claude user layer only: with it 0 of 30 children made a schema
    # error and without it 5 of 30 (docs/decisions/2026-09-25-model-fallback-guard.md), so it stays under the same
    # evidence rule (docs/decisions/2026-10-08-philosophy-only-rules.md).
    STRUCTURED_OUTPUT = ("When you return through StructuredOutput, put the schema fields at the top level of the call "
                         "arguments; never wrap them in an input, output or result key.")
    CLAUDE_USER_LAYERS = ("examples/claude-native/CLAUDE.md", "adoption/new-wsl/claude-user-instructions.md")

    def test_the_portable_block_is_exactly_the_core_and_the_evidence_backed_line(self):
        self.assertEqual((ROOT / "examples/claude-native/CLAUDE.md").read_text(encoding="utf-8"),
                         self.CORE + "\n" + self.STRUCTURED_OUTPUT + "\n")

    def test_the_structured_output_line_is_in_the_claude_user_layer_only(self):
        for relative in self.LAYERS:
            with self.subTest(layer=relative):
                expected = 1 if relative in self.CLAUDE_USER_LAYERS else 0
                self.assertEqual((ROOT / relative).read_text(encoding="utf-8").count(self.STRUCTURED_OUTPUT), expected)

    def test_every_layer_carries_the_same_core_and_no_dropped_rule(self):
        for relative in self.LAYERS:
            text = (ROOT / relative).read_text(encoding="utf-8")
            with self.subTest(layer=relative):
                self.assertEqual(text.count(self.CORE), 1)
                self.assertEqual([phrase for phrase in self.DROPPED if phrase in text], [])

    def test_root_claude_md_loads_the_core_through_its_agents_md_import(self):
        # code.claude.com/docs/en/memory, "Share one file with other coding tools": the import keeps AGENTS.md the one
        # shared file, also for sessions that cannot read AGENTS.md directly.
        text = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertEqual(text.splitlines()[0], "@AGENTS.md")
        self.assertEqual([phrase for phrase in self.DROPPED if phrase in text], [])

    # Root AGENTS.md keeps, beside the core, only lines whose removal would cause a shown mistake: the required
    # sota-sources check (.github/workflows/validate.yml, job sota-sources; .github/main-ruleset.json), the required
    # validate check over the registered evidence digests (validate.yml runs scripts/validate.py), and the trading
    # prerequisite that the amendment of docs/decisions/2026-10-07-instruction-core.md keeps for paper operation outside
    # the repository's paths, with the subtree rule that Codex's root-to-cwd AGENTS.md walk needs.
    ROOT_KEPT = (
        "the required `sota-sources` check fails a PR whose description lacks a non-empty `## SOTA sources` or "
        "`### SOTA sources` section (exact, case-sensitive heading).",
        "Run `python3 scripts/validate.py` before committing changed evidence or manifests.",
        "a directory with its own `AGENTS.md` carries its own rules; read that file before you work in the directory or "
        "on its lane's paths.",
        "Trading work of any kind (research, data acquisition, strategy gates, decision registration, paper or broker "
        "operation) reads `blueprints/us-equities/AGENTS.md` first, wherever it runs.",
    )

    def test_the_repository_file_keeps_its_core_and_the_trading_prerequisite(self):
        text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertTrue(text.startswith(self.CORE))
        for sentence in self.ROOT_KEPT:
            with self.subTest(sentence=sentence[:48]):
                self.assertIn(sentence, text)

    # The user-level reporting rule of docs/decisions/2026-10-05-user-facing-local-time.md left both client blocks and
    # their carriers with the 2026-10-08 direction; its wording must not return to any of them.
    LOCAL_TIME = ("When you tell the user a time, give it first in the host's local time zone (read it with "
                  "`timedatectl` or `date`), with UTC beside it, for example \"4:00 PM EDT (20:00Z)\". Write timestamps in "
                  "ledger rows, receipts, evidence and commit messages in UTC (RFC 3339 with `Z`); "
                  "Git author/committer metadata retains its native format.")
    LOCAL_TIME_SURFACES = ("examples/claude-native/CLAUDE.md", "adoption/templates/codex.AGENTS.template.md",
                           "adoption/new-wsl/claude-user-instructions.md", "adoption/new-wsl/codex-user-instructions.md")

    def test_the_retired_local_time_rule_stays_off_the_user_level_blocks_and_carriers(self):
        for relative in self.LOCAL_TIME_SURFACES:
            with self.subTest(surface=relative):
                self.assertNotIn(self.LOCAL_TIME, (ROOT / relative).read_text(encoding="utf-8"))


class PortableTopRuleTests(unittest.TestCase):
    """Portable procedure and fixed rendered startup bytes (2026-10-05).

    The native /doctor prompt-audit is interactive; claude doctor --help on
    2.1.289 exposes only -h/--help, and the upstream 2.1.283 changelog adds the
    slash command. These are local integration checks, not an upstream audit.
    A budget change needs a dated comparison and review, never an automatic
    re-baseline: docs/decisions/2026-10-05-harness-context-budget.md. Since the
    owner's direction of 2026-10-08 the procedure checked here is the four-rule
    philosophy core.
    """

    TEMPLATE = ROOT / "examples" / "claude-native" / "CLAUDE.md"
    # Fixed UTF-8 ceilings: measured scope + 5%, rounded upward. The dated PR #726
    # addendum records 23062/19102 -> 24458/20103 and the required restorations;
    # docs/decisions/2026-10-07-instruction-core.md lowers them to 20880/16783 (the landing tree + 5%).
    # The philosophy-only blocks of 2026-10-08 (docs/decisions/2026-10-08-philosophy-only-rules.md: the Claude block
    # keeps the StructuredOutput line, the Codex block carries rtk's default awareness paragraph) measure 3942 (Claude)
    # and 4043 (Codex) bytes with startup_files below. The owner's proactive amendment on 2026-10-08 adds 224 bytes
    # to each core copy; two loaded copies per client measure 4390/4491 bytes. The same 5% formula gives 4610/4716.
    STARTUP_BUDGET_BYTES = {"claude": 4965, "codex": 5071}
    # The four rules of the core (2026-10-08): research before acting with named sources, upstream as the truth with
    # the check order, decisions by evidence measured with upstream harnesses, and the compounding ecosystem with the
    # recorded correction.
    PROCEDURE_PHRASES = (
        "Research convergence first",
        "current upstream SOTA is the source of truth",
        "survey the maintained upstream landscape",
        "orchestration patterns",
        "record what you found",
        "supported install and test commands",
        "naming each source (repository and pin, file or paper)",
        "build only from a cited reference implementation",
        "Never rebuild or fork what an upstream already ships",
        "the installed client",
        "the upstream release notes and source at that version",
        "then official docs",
        "leads to verify",
        "reproduced results on the actual change",
        "measured with upstream harnesses",
        "Agreement, recency, popularity and incumbency are not evidence",
        "measured results, simulations and untested boundaries",
        "current best converged practice",
        "record the correction",
    )
    # A relative path such as docs/harness-defaults.md; one that exists here is absent from other projects.
    RELATIVE_PATH = re.compile(r"[\w.-]+(?:/[\w.-]+)+")

    @staticmethod
    def top_rule(text: str) -> str:
        """The core: from its bold first rule to the next section heading, or to the end of the text."""
        start = text.find("**Research convergence first;")
        if start < 0:
            return ""
        end = text.find("\n## ", start)
        return text[start:] if end < 0 else text[start:end]

    @classmethod
    def errors(cls, text: str) -> list[str]:
        rule = cls.top_rule(text)
        errors = [f"the top rule lacks {phrase!r}" for phrase in cls.PROCEDURE_PHRASES if phrase not in rule]
        errors += [f"the top rule names this repository's {path}, which other projects lack"
                   for path in dict.fromkeys(cls.RELATIVE_PATH.findall(rule)) if (ROOT / path).exists()]
        return errors

    def test_the_template_states_the_upstream_verification_procedure(self):
        self.assertEqual(self.errors(self.TEMPLATE.read_text(encoding="utf-8")), [])

    def scratch_startup(self, root):
        (root / "AGENTS.md").write_text("repository instructions\n")
        (root / "CLAUDE.md").write_text("@AGENTS.md\n")
        carriers = root / "adoption/new-wsl"
        carriers.mkdir(parents=True)
        (carriers / "claude-user-instructions.md").write_text("# Synthetic user instructions\n")
        (carriers / "codex-user-instructions.md").write_bytes((ROOT / "adoption/new-wsl/codex-user-instructions.md").read_bytes())

    def test_imports_outside_code_are_counted_once_and_resolve_from_the_importing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            self.scratch_startup(root)
            (root / "reference.md").write_text("imported context\n")
            with mock.patch(__name__ + ".ROOT", root):
                before = sum(map(len, self.startup_files("claude").values()))
                (root / "CLAUDE.md").write_text("@AGENTS.md\n@reference.md\n")
                after = sum(map(len, self.startup_files("claude").values()))
            self.assertEqual(after - before, len("@reference.md\n".encode()) + len("imported context\n".encode()))

    def test_unfiltered_rules_are_counted_and_codex_prefers_the_root_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            self.scratch_startup(root)
            rules = root / ".claude/rules"
            rules.mkdir(parents=True)
            with mock.patch(__name__ + ".ROOT", root):
                before = sum(map(len, self.startup_files("claude").values()))
                (rules / "always.md").write_text("always loaded\n")
                after = sum(map(len, self.startup_files("claude").values()))
                self.assertEqual(after - before, len("always loaded\n".encode()))
                (root / "AGENTS.override.md").write_text("preferred override\n")
                files = self.startup_files("codex")
            self.assertNotIn("AGENTS.md", files)
            self.assertEqual(files["AGENTS.override.md"], b"preferred override\n")

    def test_import_discovery_skips_code_and_quotes_and_handles_nested_duplicate_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            self.scratch_startup(root)
            (root / "nested").mkdir()
            (root / "Design Docs").mkdir()
            (root / "nested/one.md").write_text("@two.md\n")
            (root / "nested/two.md").write_text("@one.md\n")  # cycle, counted once
            (root / "Design Docs/brief.md").write_text("design reference\n")
            (root / "CLAUDE.md").write_text(
                '@AGENTS.md @nested/one.md @nested/one.md\n@Design\\ Docs/brief.md\n'
                '`@not-loaded.md` ``@also-not-loaded.md``\n'
                '```text\n@fenced.md\n```\n~~~\n@tilde-fenced.md\n~~~\n'
                '@"quoted.md" user@example.com repo@pin:path\n')
            with mock.patch(__name__ + ".ROOT", root):
                files = self.startup_files("claude")
                self.assertEqual(set(files), {"claude-block", "AGENTS.md", "CLAUDE.md", "nested/one.md",
                                              "nested/two.md", "Design Docs/brief.md"})
                (root / "CLAUDE.md").write_text("@missing.md\n")
                with self.assertRaises(FileNotFoundError):
                    self.startup_files("claude")

    def test_imports_are_bounded_to_four_hops_and_codex_leaves_them_literal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            self.scratch_startup(root)
            (root / "CLAUDE.md").write_text("@hop1.md\n")
            for hop in range(1, 5):
                (root / f"hop{hop}.md").write_text(f"@hop{hop + 1}.md\n")
            with mock.patch(__name__ + ".ROOT", root):
                files = self.startup_files("claude")
                self.assertIn("hop4.md", files)
                self.assertNotIn("hop5.md", files)
                (root / "AGENTS.md").write_text("@missing.md\n")
                self.assertEqual(set(self.startup_files("codex")), {"codex-block", "AGENTS.md"})

    def test_only_nonempty_frontmatter_paths_filters_exempt_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            self.scratch_startup(root)
            rules = root / ".claude/rules/nested"
            rules.mkdir(parents=True)
            content = {"plain.md": "always loaded\npaths: [example]\n",
                       "empty.md": "---\npaths: []\n---\nalways loaded\n",
                       "other.md": "---\ntitle: unscoped\n---\nalways loaded\n",
                       "scoped.md": '---\npaths:\n  - "src/**/*.py"\n---\n@unloaded.md\n',
                       "inline.md": '---\npaths: ["src/**/*.py"]\n---\n@unloaded.md\n'}
            for name, text in content.items():
                (rules / name).write_text(text)
            with mock.patch(__name__ + ".ROOT", root):
                files = self.startup_files("claude")
            loaded = {path.removeprefix(".claude/rules/nested/") for path in files if path.startswith(".claude/rules/")}
            self.assertEqual(loaded, {"plain.md", "empty.md", "other.md"})

    @staticmethod
    def section(content: bytes, heading: str) -> bytes:
        """Bound a passage check to its destination heading and child headings."""
        marker = heading.encode()
        start = content.index(marker + b"\n")
        level = len(heading.split(" ", 1)[0])
        end = re.search(rb"(?m)^#{1," + str(level).encode() + rb"} ", content[start + len(marker) + 1:])
        return content[start:start + len(marker) + 1 + end.start()] if end else content[start:]

    def test_each_relocated_passage_is_byte_bound_to_its_destination_section(self):
        fixtures = ROOT / "tests/fixtures/harness-context-moves"
        contracts = json.loads((fixtures / "contracts.json").read_text())
        for contract in contracts:
            with self.subTest(passage=contract["fixture"], destination=contract["to"]):
                passage = (fixtures / contract["fixture"]).read_bytes()
                content = (ROOT / contract["to"]).read_bytes()
                if contract["heading"].startswith("<!--"):
                    # A marker heading's section ends at the next native-agent-stack marker.
                    content = content.split(contract["heading"].encode(), 1)[1].split(b"<!-- native-agent-stack:", 1)[0]
                else:
                    content = self.section(content, contract["heading"])
                self.assertEqual(len(passage), contract["bytes"])
                if contract["fixture"] == "04.txt":
                    # The 2026-10-06 owner ruling supersedes this one active catalog instruction.
                    # Preserve the old relocation bytes/hash and check the NEW linked snapshot.
                    import hashlib
                    record = ROOT / "evidence/artifacts/qmd-lexical-catalog-instructions-20261006/catalog-lookup-supersession.json"
                    supersession = json.loads(record.read_text())
                    old = supersession["supersedes"]
                    self.assertEqual(old["file"], "tests/fixtures/harness-context-moves/04.txt")
                    self.assertEqual(old["bytes"], contract["bytes"])
                    self.assertEqual(old["sha256"], "63371ccabaa9fd58734c55a114f7c4cfd4ad30c12126d513429b70a94c1e9b73")
                    self.assertEqual(hashlib.sha256(passage).hexdigest(), old["sha256"])
                    active = supersession["replacement"]
                    self.assertEqual((active["to"], active["heading"]), (contract["to"], contract["heading"]))
                    replacement = (ROOT / active["file"]).read_bytes()
                    self.assertEqual(len(replacement), active["bytes"])
                    self.assertEqual(hashlib.sha256(replacement).hexdigest(), active["sha256"])
                    self.assertIn(replacement, content)
                    self.assertNotIn(passage, content)
                else:
                    self.assertIn(passage, content)

    def test_the_check_rejects_a_missing_step_and_a_repository_path(self):
        text = self.TEMPLATE.read_text(encoding="utf-8")
        self.assertEqual(len(self.errors(text.replace("record the correction", "note it"))), 1)
        self.assertEqual(len(self.errors(text.replace("then official docs", "then official docs (docs/harness-defaults.md)"))),
                         1)
        self.assertEqual(len(self.errors("# Native engineering defaults\n\nNo rule.\n")), len(self.PROCEDURE_PHRASES))


    @staticmethod
    def imports(text: str) -> list[str]:
        """Native memory docs: imports outside code, escaped spaces, four hops.

        This budget check only discovers files; it does not render client prompts.
        """
        lines = []
        fence = None
        for line in text.splitlines(keepends=True):
            mark = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
            if fence:
                if mark and mark[1][0] == fence[0] and len(mark[1]) >= len(fence) and not line[mark.end():].strip():
                    fence = None
                lines.append("\n")
            elif mark:
                fence = mark[1]
                lines.append("\n")
            else:
                lines.append(line)
        text = "".join(lines)
        text = re.sub(r"(?<!`)(`+)(?!`)[\s\S]*?(?<!`)\1(?!`)", "", text)
        return [path.replace("\\ ", " ").replace("\\\t", "\t") for path in
                re.findall(r'''(?<![\w@\\"'])@((?:\\[ \t]|[^\s`<>"'(),;])+)''', text)]

    @staticmethod
    def path_filtered(content: str) -> bool:
        """Exempt only a clear nonempty paths list; ambiguous YAML still counts."""
        frontmatter = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)", content, re.S)
        if not frontmatter:
            return False
        field = re.search(r"(?m)^paths:[ \t]*(.*)$", frontmatter[1])
        if not field:
            return False
        value = field[1].split(" #", 1)[0].strip()
        if value:
            try:
                paths = json.loads(value)
            except ValueError:
                return False
            return isinstance(paths, list) and bool(paths) and all(isinstance(p, str) and p.strip() for p in paths)
        tail = frontmatter[1][field.end():]
        tail = re.split(r"\n\S", tail, maxsplit=1)[0]
        items = [line.strip()[2:].split(" #", 1)[0].strip().strip("\"'")
                 for line in tail.splitlines() if re.match(r"^[ \t]+-[ \t]+", line)]
        return bool(items) and all(item and item not in ("null", "~", "[]", "{}") for item in items)

    @classmethod
    def startup_files(cls, client: str) -> dict[str, bytes]:
        """The renderer's committed carriers, wrapped by its actual native block merger.
        Count raw UTF-8 bytes including markers; Claude's @AGENTS.md import loads the
        repository AGENTS once, alongside CLAUDE.md and unconditional rules. Codex
        prefers a root override and does not expand imports. Plugin blocks, native
        Claude RTK imports and the named SubagentStart child carrier are separate
        measured scopes; Codex's inline native RTK awareness is counted here.
        """
        root = ROOT.resolve()
        files = {}
        visited = {}

        def add(path: Path, depth: int = 0) -> None:
            path = path.resolve()
            key = str(path.relative_to(root)) if path.is_relative_to(root) else str(path)
            content = path.read_bytes()  # A missing import fails; it cannot hide context.
            files[key] = content
            if client == "claude" and depth < 4 and visited.get(path, 5) > depth:
                visited[path] = depth
                for imported in cls.imports(content.decode("utf-8")):
                    add(path.parent / Path(imported).expanduser(), depth + 1)

        if client == "claude":
            carrier = (root / "adoption/new-wsl/claude-user-instructions.md").read_text(encoding="utf-8")
            files["claude-block"] = managed_block.merged_claude_md("", carrier).encode("utf-8")
            # Project the user block's relative imports from its native .claude directory.
            for imported in cls.imports(carrier):
                add(root / ".claude" / Path(imported).expanduser(), 1)
            add(root / "AGENTS.md")
            add(root / "CLAUDE.md")
            for rule in sorted((root / ".claude/rules").rglob("*.md")):
                if not cls.path_filtered(rule.read_text(encoding="utf-8")):
                    add(rule)
        else:
            carrier = (root / "adoption/new-wsl/codex-user-instructions.md").read_text(encoding="utf-8")
            files["codex-block"] = managed_block.merged_codex_md("", carrier).encode("utf-8")
            add(root / ("AGENTS.override.md" if (root / "AGENTS.override.md").is_file() else "AGENTS.md"))
        return files

    @classmethod
    def budget_errors(cls, client: str, files: dict[str, bytes]) -> list[str]:
        size = sum(len(content) for content in files.values())
        limit = cls.STARTUP_BUDGET_BYTES[client]
        return ([f"{client}: {size} startup bytes exceeds fixed {limit}; a dated budget decision is required"]
                if size > limit else [])

    def test_rendered_startup_files_fit_each_clients_fixed_byte_budget(self):
        for client in self.STARTUP_BUDGET_BYTES:
            with self.subTest(client=client):
                self.assertEqual(self.budget_errors(client, self.startup_files(client)), [])

    def test_growth_in_any_loaded_file_crosses_the_fixed_budget(self):
        for client, limit in self.STARTUP_BUDGET_BYTES.items():
            files = self.startup_files(client)
            room = limit - sum(len(content) for content in files.values())
            self.assertGreaterEqual(room, 0)
            for path in files:
                with self.subTest(client=client, path=path):
                    padded = dict(files)
                    padded[path] += b"x" * room
                    self.assertEqual(self.budget_errors(client, padded), [])
                    padded[path] += "é".encode("utf-8")  # bytes, not words or Unicode code points
                    self.assertEqual(len(self.budget_errors(client, padded)), 1)



class McpStartupTimeoutTemplateTests(unittest.TestCase):
    """MCP_TIMEOUT is Claude Code's MCP server startup timeout, default 30000 ms
    (https://code.claude.com/docs/en/env-vars); a server's own `timeout` field bounds tool
    execution only (https://code.claude.com/docs/en/mcp), and `claude mcp add --help` on 2.1.285
    and 2.1.286 has no startup option. The Codex template gives serena 60 s and socraticode 120 s
    (startup_timeout_sec), so the one global value matches the slowest of them
    (docs/decisions/2026-09-30-mcp-startup-timeout.md)."""

    TEMPLATE = ROOT / "adoption" / "templates" / "claude.settings.template.json"

    def test_the_template_env_sets_the_mcp_startup_timeout(self):
        env = json.loads(self.TEMPLATE.read_text(encoding="utf-8"))["env"]
        self.assertEqual(env.get("MCP_TIMEOUT"), "120000")


if __name__ == "__main__":
    unittest.main()
