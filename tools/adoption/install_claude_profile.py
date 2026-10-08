#!/usr/bin/env python3
"""Install this catalog's Claude Code user-scope profile assets onto a host:

  guard   -- sha256-checked copies of the user-scope hooks to ~/.claude/hooks/:
             adoption/hooks/claude/effort-default-guard.py (effort self-heal) and
             scripts/hooks/secret_path_guard.py (PreToolUse Bash secret guard;
             the same file the project .claude/settings.json runs), and
             currency-due-notice.py (SessionStart stack-currency due line).
             The token-lane carriers of adoption/hooks/claude/ (the
             SubagentStart hook with its default block and five role blocks, and
             the SessionStart hook with its main-session block) are this
             repository's own adaptation and are held out of the default
             (docs/decisions/2026-10-04-claude-template-holds-out-token-lane-carriers.md):
             they stay checksum-pinned and install only when `--hook NAME` names them
  agents  -- verbatim copies of adoption/agents/claude/*.md to ~/.claude/agents/
  workflows -- opt-in (--only workflows), checksum-checked, create-only copies of
             the three reviewed scripts in examples/claude-native/workflows/ to
             ~/.claude/workflows/; matching files are reused, conflicting files
             and target symlinks are refused, and a failed step rolls back only
             its new files
  mcp     -- `claude mcp add --scope user` for each server named in
             adoption/mcp/claude-user.json after rendering its ${HOME} and
             ${ECO_ROOT} placeholders; skipped when a server of the same name
             is already registered with the same config, and left unchanged
             (reported) when it differs unless --replace-mcp is given

A caller that wires only part of the profile narrows each step without changing its defaults:
`--hook NAME` (repeatable) installs only the named files of the hook map (or of the held-out carriers) in the guard step, `--agent NAME`
(repeatable) only the named files of adoption/agents/claude/ in the agents step, and `--mcp-template PATH` registers
the servers of another file in the template's `{"mcpServers": {...}}` shape instead of adoption/mcp/claude-user.json
(tools/adoption/new_wsl_client_config.py passes the three).

Each step is independently runnable (`--only guard|agents|workflows|mcp`) and safe to
re-run: a hook is only overwritten if its checksum in
adoption/hooks/claude/SHA256SUMS (paths relative to that file, so
`sha256sum -c SHA256SUMS` works from its directory) differs from what's
already installed, agent
copies are always refreshed (they're catalog-owned files, not host edits),
and MCP registration never replaces a differing entry without --replace-mcp.
The default steps remain guard, agents and mcp; workflows runs only when named
with --only workflows. `--only workflows --remove-workflows` removes only selected
byte-matching scripts; edited files, symlinks and unrelated workflows are preserved.
This never touches ~/.claude.json, credentials or any other account state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import shutil
import string
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GUARD_SRC = ROOT / "adoption" / "hooks" / "claude" / "effort-default-guard.py"
SECRET_GUARD_SRC = ROOT / "scripts" / "hooks" / "secret_path_guard.py"
TOKEN_LANES_BLOCK_SRC = ROOT / "adoption" / "hooks" / "claude" / "token-lanes-block.md"
TOKEN_LANES_HOOK_SRC = ROOT / "adoption" / "hooks" / "claude" / "token-lanes-subagent-start.py"
SHA256SUMS = ROOT / "adoption" / "hooks" / "claude" / "SHA256SUMS"
# Installed name under ~/.claude/hooks/ -> checked-in source: the files the guard step installs by default.
HOOKS = {
    "currency-due-notice.py": GUARD_SRC.with_name("currency-due-notice.py"),  # SessionStart currency due line
    "effort-default-guard.py": GUARD_SRC,
    "research-routing-guard.py": GUARD_SRC.with_name("research-routing-guard.py"),  # CC/co-op native-session research gate
    "secret_path_guard.py": SECRET_GUARD_SRC,
}
# The token-lane carriers and their sibling blocks: this repository's own adaptation, held out of the default pending
# the upstream A/B (docs/decisions/2026-10-04-claude-template-holds-out-token-lane-carriers.md). They stay
# checksum-pinned in SHA256SUMS and install only when `--hook NAME` names them.
HELD_OUT_HOOKS = {
    "token-lanes-block.md": TOKEN_LANES_BLOCK_SRC,
    "token-lanes-block.builder.md": TOKEN_LANES_BLOCK_SRC.with_name("token-lanes-block.builder.md"),
    "token-lanes-block.main.md": TOKEN_LANES_BLOCK_SRC.with_name("token-lanes-block.main.md"),  # SessionStart text
    "token-lanes-block.researcher.md": TOKEN_LANES_BLOCK_SRC.with_name("token-lanes-block.researcher.md"),
    "token-lanes-block.reviewer.md": TOKEN_LANES_BLOCK_SRC.with_name("token-lanes-block.reviewer.md"),
    "token-lanes-block.scout.md": TOKEN_LANES_BLOCK_SRC.with_name("token-lanes-block.scout.md"),
    "token-lanes-block.verifier.md": TOKEN_LANES_BLOCK_SRC.with_name("token-lanes-block.verifier.md"),
    "token-lanes-session-start.py": TOKEN_LANES_HOOK_SRC.with_name("token-lanes-session-start.py"),  # SessionStart
    "token-lanes-subagent-start.py": TOKEN_LANES_HOOK_SRC,
}
ALL_HOOKS = {**HOOKS, **HELD_OUT_HOOKS}
AGENTS_SRC_DIR = ROOT / "adoption" / "agents" / "claude"
MCP_TEMPLATE = ROOT / "adoption" / "mcp" / "claude-user.json"
WORKFLOWS_SRC_DIR = ROOT / "examples" / "claude-native" / "workflows"
WORKFLOWS_SHA256SUMS = WORKFLOWS_SRC_DIR / "SHA256SUMS"
WORKFLOW_NAMES = ("readiness-audit.js", "review-changes.js", "layer-verdict-lane.js")


class InstallError(ValueError):
    pass


def sha256sums_entries(sums_file: Path | None = None) -> dict[Path, str]:
    """SHA256SUMS entries as {resolved source path: sha256}; paths are relative to the file."""
    sums_file = sums_file or SHA256SUMS
    entries = {}
    for line in sums_file.read_text().splitlines():
        parts = line.split()
        if len(parts) == 2:
            entries[(sums_file.parent / parts[1].lstrip("*")).resolve()] = parts[0]
    return entries


def expected_sha256(source: Path, sums_file: Path | None = None) -> str:
    digest = sha256sums_entries(sums_file).get(source.resolve())
    if digest is None:
        raise InstallError(f"no {source.name} entry in {sums_file or SHA256SUMS}")
    return digest


def expected_guard_sha256() -> str:
    return expected_sha256(GUARD_SRC)


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def install_guard(home: Path, dry_run: bool, name: str = "effort-default-guard.py") -> str:
    source = ALL_HOOKS[name]
    if not source.is_file():
        raise InstallError(f"missing source: {source}")
    expected = expected_sha256(source)
    actual = sha256_of(source)
    if actual != expected:
        raise InstallError(
            f"refusing to install {source}: sha256 {actual} does not match "
            f"{SHA256SUMS} ({expected})"
        )
    dest_dir = home / ".claude" / "hooks"
    dest = dest_dir / name
    if dest.is_file() and sha256_of(dest) == expected:
        print(f"guard: {dest} already matches (sha256 {expected[:12]}...); skipped")
        return "skipped"
    if dry_run:
        print(f"guard: would install {dest} (sha256 {expected[:12]}...)")
        return "planned"
    dest_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, dest)
    dest.chmod(0o755)
    print(f"guard: installed {dest}")
    return "installed"


def install_guards(home: Path, dry_run: bool, names: list[str] | None = None) -> dict[str, str]:
    """Every user-scope hook in HOOKS, or only the files in `names` (which may name a held-out carrier file); all are
    checked before any is copied."""
    selected = list(HOOKS) if names is None else list(dict.fromkeys(names))
    unknown = [name for name in selected if name not in ALL_HOOKS]
    if unknown:
        raise InstallError(f"no such hook file in the hook map: {', '.join(unknown)} (known: {', '.join(ALL_HOOKS)})")
    for name in selected:
        source = ALL_HOOKS[name]
        if sha256_of(source) != expected_sha256(source):
            raise InstallError(f"refusing to install {source}: sha256 does not match {SHA256SUMS}")
    return {name: install_guard(home, dry_run, name) for name in selected}


def install_agents(home: Path, dry_run: bool, names: list[str] | None = None) -> list[str]:
    if not AGENTS_SRC_DIR.is_dir():
        raise InstallError(f"missing source directory: {AGENTS_SRC_DIR}")
    dest_dir = home / ".claude" / "agents"
    results = []
    sources = sorted(AGENTS_SRC_DIR.glob("*.md"))
    if names is not None:
        unknown = [name for name in names if name not in {src.name for src in sources}]
        if unknown:
            raise InstallError(f"no such agent file in {AGENTS_SRC_DIR}: {', '.join(unknown)}")
        sources = [src for src in sources if src.name in names]
    for src in sources:
        dest = dest_dir / src.name
        if dest.is_file() and dest.read_bytes() == src.read_bytes():
            print(f"agents: {dest} already matches; skipped")
            results.append("skipped")
            continue
        if dry_run:
            print(f"agents: would install {dest}")
            results.append("planned")
            continue
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        print(f"agents: installed {dest}")
        results.append("installed")
    return results


def checked_workflows() -> dict[str, bytes]:
    """Freeze all selected source bytes only after checking the reviewed manifest."""
    workflows = {}
    for name in WORKFLOW_NAMES:
        source = WORKFLOWS_SRC_DIR / name
        payload = source.read_bytes()
        expected = expected_sha256(source, WORKFLOWS_SHA256SUMS)
        actual = hashlib.sha256(payload).hexdigest()
        if actual != expected:
            raise InstallError(
                f"refusing to install {source}: sha256 {actual} does not match "
                f"{WORKFLOWS_SHA256SUMS} ({expected})"
            )
        workflows[name] = payload
    return workflows


def install_workflows(home: Path, dry_run: bool) -> dict[str, str]:
    """Personal saved-workflow layout from the official workflows docs.

    Check every source and target before mutation. Never replace a target, even
    if it appears after preflight; rollback owns only files created by this call.
    Personal directory symlinks are supported, as in the native save dialog.
    """
    workflows = checked_workflows()
    dest_dir = home / ".claude" / "workflows"
    results = {}
    for name, payload in workflows.items():
        dest = dest_dir / name
        if dest.is_symlink():
            raise InstallError(f"workflows: refusing target symlink: {dest}")
        if dest.exists():
            if not dest.is_file() or dest.read_bytes() != payload:
                raise InstallError(f"workflows: {dest} differs; left unchanged (review or relocate it first)")
            results[name] = "skipped"
        else:
            results[name] = "planned" if dry_run else "installed"
    if not dry_run and "installed" in results.values():
        missing_dirs = []
        cursor = dest_dir
        while not cursor.exists():
            missing_dirs.append(cursor)
            cursor = cursor.parent
        created: list[tuple[Path, int, int]] = []
        try:
            dest_dir.mkdir(parents=True, exist_ok=True)
            for name, payload in workflows.items():
                if results[name] == "skipped":
                    continue
                dest = dest_dir / name
                # Exclusive creation also refuses a symlink or file that appears after preflight.
                with dest.open("xb") as stream:
                    identity = os.fstat(stream.fileno())
                    created.append((dest, identity.st_dev, identity.st_ino))
                    stream.write(payload)
                if dest.is_symlink() or dest.read_bytes() != payload:
                    raise InstallError(f"workflows: installed readback differs: {dest}")
        except (OSError, InstallError) as error:
            cleanup_errors = []
            for dest, device, inode in reversed(created):
                try:
                    identity = dest.lstat()
                    if (identity.st_dev, identity.st_ino) == (device, inode):
                        dest.unlink()
                    else:
                        cleanup_errors.append(f"{dest} changed identity; preserved")
                except FileNotFoundError:
                    pass
                except OSError as cleanup_error:
                    cleanup_errors.append(f"{dest}: {cleanup_error}")
            for directory in missing_dirs:
                try:
                    directory.rmdir()  # Only empty directories absent before this step.
                except FileNotFoundError:
                    pass
                except OSError:
                    pass  # Preserve directories containing another writer's entries.
            recovery = "; ".join(cleanup_errors) if cleanup_errors else "new files rolled back"
            raise InstallError(f"workflows: install failed: {error}; {recovery}") from error
    for name, status in results.items():
        dest = dest_dir / name
        if status == "skipped":
            print(f"workflows: {dest} already matches; skipped")
        else:
            action = "would install" if status == "planned" else "installed"
            print(f"workflows: {action} {dest}")
    return results


def remove_workflows(home: Path, dry_run: bool) -> dict[str, str]:
    """Remove selected byte-matching scripts, preserving edits and custom entries."""
    workflows = checked_workflows()
    dest_dir = home / ".claude" / "workflows"
    results = {}
    for name, payload in workflows.items():
        dest = dest_dir / name
        if dest.is_symlink():
            results[name] = "symlink"
            print(f"workflows: {dest} is a symlink; left unchanged", file=sys.stderr)
        elif not dest.exists():
            results[name] = "absent"
            print(f"workflows: {dest} already absent")
        elif not dest.is_file() or dest.read_bytes() != payload:
            results[name] = "differs"
            print(f"workflows: {dest} differs; left unchanged", file=sys.stderr)
        elif dry_run:
            results[name] = "planned"
            print(f"workflows: would remove {dest}")
        else:
            dest.unlink()
            results[name] = "removed"
            print(f"workflows: removed {dest}")
    return results


def claude_mcp_get(claude_bin: str, name: str) -> str | None:
    """`claude mcp get <name>` run from an empty temporary directory, so no
    project (.mcp.json) or local (per-path) entry can shadow the user-scope one."""
    with tempfile.TemporaryDirectory() as neutral:
        result = subprocess.run([claude_bin, "mcp", "get", name], capture_output=True, text=True,
                                timeout=30, check=False, cwd=neutral)
    if result.returncode != 0:
        return None
    return result.stdout


def parse_mcp_get(text: str) -> dict:
    """Fields of `claude mcp get` output (claude 2.1.280): `  Type: stdio`,
    `  Command: ...`, `  Args: a b c`, `  URL: ...`, and an `  Environment:`
    block of `    KEY=VALUE` lines."""
    fields: dict = {"env": {}}
    in_env = False
    for line in text.splitlines():
        if in_env and line.startswith("    ") and "=" in line:
            key, _, value = line.strip().partition("=")
            fields["env"][key] = value
            continue
        in_env = False
        stripped = line.strip()
        if stripped == "Environment:":
            in_env = True
            continue
        key, sep, value = stripped.partition(":")
        # Exactly two-space fields only: four-space lines are Environment or Headers entries.
        if sep and line.startswith("  ") and not line.startswith("   ") and key in ("Scope", "Type", "Command", "Args", "URL"):
            fields[key.lower()] = value.strip()
    return fields


def existing_config_matches(existing_text: str, server_type: str, command_or_url: str, args: list[str], env: dict) -> bool:
    """Exact match against `claude mcp get`'s fields: same transport, the same
    command or URL, the same argument list in order, and every expected env
    NAME present (values are not asserted; the running host owns them)."""
    fields = parse_mcp_get(existing_text)
    if fields.get("type") != server_type:
        return False
    if server_type != "stdio":
        return fields.get("url") == command_or_url
    return (fields.get("command") == command_or_url
            and fields.get("args", "") == " ".join(args)
            and all(key in fields["env"] for key in env))


def default_eco_root(home: Path) -> Path:
    """The ecosystem prefix the bootstraps install into (their ECO_INSTALL_ROOT)."""
    env_root = os.environ.get("ECO_INSTALL_ROOT")
    return Path(env_root) if env_root else home / ".local" / "share" / "codex-ecosystem"


def render_servers(data: dict, home: Path, eco_root: Path) -> dict:
    """Substitute the template's ${HOME} and ${ECO_ROOT} placeholders in every
    server's url, command, args and env values; any other placeholder fails."""
    values = {"HOME": str(home), "ECO_ROOT": str(eco_root)}

    def render(value):
        if isinstance(value, str):
            try:
                return string.Template(value).substitute(values)
            except (KeyError, ValueError) as error:
                raise InstallError(f"{MCP_TEMPLATE.name}: cannot render {value!r} ({error})") from None
        if isinstance(value, list):
            return [render(item) for item in value]
        if isinstance(value, dict):
            return {key: render(item) for key, item in value.items()}
        return value

    return {name: render(spec) for name, spec in data.get("mcpServers", {}).items()}


def mcp_add_command(claude_bin: str, name: str, spec: dict) -> list[str]:
    """`claude mcp add [options] <name> <commandOrUrl> [args...]`: the name
    comes before the variadic `-e`, and `--` ends option parsing before a
    stdio command, as in the CLI's own `claude mcp add my-server -e
    API_KEY=xxx -- npx my-mcp-server` example."""
    server_type = spec.get("type", "stdio")
    if server_type != "stdio":
        return [claude_bin, "mcp", "add", "--scope", "user", "--transport", server_type, name, spec["url"]]
    cmd = [claude_bin, "mcp", "add", "--scope", "user", name]
    for key, value in spec.get("env", {}).items():
        cmd += ["-e", f"{key}={value}"]
    return cmd + ["--", spec["command"], *spec.get("args", [])]


def install_mcp_servers(claude_bin: str, dry_run: bool, home: Path, eco_root: Path,
                        replace: bool = False, template: Path | None = None) -> list[str]:
    template = MCP_TEMPLATE if template is None else template
    if not template.is_file():
        raise InstallError(f"missing template: {template}")
    servers = render_servers(json.loads(template.read_text()), home, eco_root)
    results = []
    for name, spec in servers.items():
        server_type = spec.get("type", "stdio")
        command_or_url = spec["url"] if server_type == "http" else spec["command"]
        existing = claude_mcp_get(claude_bin, name)
        scope = parse_mcp_get(existing).get("scope", "") if existing is not None else ""
        if existing is not None and not scope.startswith("User"):
            # From an empty directory only user and managed servers are visible; a managed
            # server of the same name wins over any user entry, so leave it alone.
            print(f"mcp: {name} is registered at another scope ({scope or 'unknown'}); left unchanged", file=sys.stderr)
            results.append("other-scope")
            continue
        if existing is not None and existing_config_matches(
                existing, server_type, command_or_url, spec.get("args", []), spec.get("env", {})):
            print(f"mcp: {name} already registered with matching config; skipped")
            results.append("skipped")
            continue
        if existing is not None and not replace:
            print(f"mcp: {name} is already registered with a different config; left unchanged "
                  f"(re-run with --replace-mcp to re-register it at user scope)", file=sys.stderr)
            results.append("differs")
            continue
        cmd = mcp_add_command(claude_bin, name, spec)
        remove = [claude_bin, "mcp", "remove", name, "-s", "user"] if existing is not None else None
        if dry_run:
            if remove:
                print(f"mcp: would run: {shlex.join(remove)}")
            print(f"mcp: would run: {shlex.join(cmd)}")
            results.append("planned")
            continue
        if remove:
            subprocess.run(remove, capture_output=True, text=True, timeout=30, check=False)
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=False)
        if result.returncode != 0:
            raise InstallError(f"mcp: failed to register {name}: {result.stderr.strip()}")
        print(f"mcp: registered {name}")
        results.append("installed")
    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", default=str(Path.home()), help="Target $HOME (default: current user's)")
    parser.add_argument("--claude-bin", default="claude", help="claude executable to use for MCP registration")
    parser.add_argument("--eco-root", default=None,
                         help="Ecosystem prefix for ${ECO_ROOT} (default: $ECO_INSTALL_ROOT or <home>/.local/share/codex-ecosystem)")
    parser.add_argument("--replace-mcp", action="store_true",
                         help="Re-register a same-named MCP server whose existing config differs (default: leave it)")
    parser.add_argument("--only", choices=["guard", "agents", "workflows", "mcp"], action="append",
                         help="Run only the named step(s); default: guard, agents, mcp (workflows is opt-in)")
    parser.add_argument("--remove-workflows", action="store_true",
                         help="With --only workflows, remove selected byte-matching scripts; preserve edits and custom entries")
    parser.add_argument("--hook", action="append", metavar="NAME",
                         help="Guard step: install only this file of the hook map (repeatable; default: every file of the "
                              "default map; a held-out token-lane carrier file installs only when named)")
    parser.add_argument("--agent", action="append", metavar="NAME",
                         help="Agents step: install only this file of adoption/agents/claude/ (repeatable; "
                              "default: every file)")
    parser.add_argument("--mcp-template", default=None, metavar="PATH",
                         help="MCP step: register the servers of this file, in the shape of "
                              "adoption/mcp/claude-user.json, instead of that file")
    parser.add_argument("--dry-run", action="store_true", help="Report what would happen; write and register nothing")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.remove_workflows and (args.only != ["workflows"] or args.replace_mcp):
        parser.error("--remove-workflows requires exactly --only workflows and cannot use --replace-mcp")
    steps = args.only or ["guard", "agents", "mcp"]
    home = Path(args.home)
    try:
        if "guard" in steps:
            install_guards(home, args.dry_run, args.hook)
        if "agents" in steps:
            install_agents(home, args.dry_run, args.agent)
        if "workflows" in steps:
            if args.remove_workflows:
                results = remove_workflows(home, args.dry_run)
                if any(status in ("differs", "symlink") for status in results.values()):
                    return 1
            else:
                install_workflows(home, args.dry_run)
        if "mcp" in steps:
            eco_root = Path(args.eco_root) if args.eco_root else default_eco_root(home)
            install_mcp_servers(args.claude_bin, args.dry_run, home, eco_root, args.replace_mcp,
                                Path(args.mcp_template) if args.mcp_template else None)
    except FileNotFoundError as error:
        hint = " (pass --claude-bin)" if error.filename == args.claude_bin else ""
        print(f"install failed: {error.filename or error} not found{hint}", file=sys.stderr)
        return 1
    except InstallError as error:
        print(f"install failed: {error}", file=sys.stderr)
        return 1
    except OSError as error:
        print(f"install failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
