#!/usr/bin/env python3
"""Install this catalog's Claude Code user-scope profile assets onto a host:

  guard   -- sha256-checked copies of the user-scope hooks to ~/.claude/hooks/:
             adoption/hooks/claude/effort-default-guard.py (effort self-heal) and
             scripts/hooks/secret_path_guard.py (PreToolUse Bash secret guard;
             the same file the project .claude/settings.json runs)
  agents  -- verbatim copies of adoption/agents/claude/*.md to ~/.claude/agents/
  mcp     -- `claude mcp add --scope user` for each server named in
             adoption/mcp/claude-user.json after rendering its ${HOME} and
             ${ECO_ROOT} placeholders; skipped when a server of the same name
             is already registered with the same config, and left unchanged
             (reported) when it differs unless --replace-mcp is given

Each step is independently runnable (`--only guard|agents|mcp`) and safe to
re-run: a hook is only overwritten if its checksum in
adoption/hooks/claude/SHA256SUMS (paths relative to that file, so
`sha256sum -c SHA256SUMS` works from its directory) differs from what's
already installed, agent
copies are always refreshed (they're catalog-owned files, not host edits),
and MCP registration never replaces a differing entry without --replace-mcp.
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
SHA256SUMS = ROOT / "adoption" / "hooks" / "claude" / "SHA256SUMS"
# Installed name under ~/.claude/hooks/ -> checked-in source. The settings template runs both.
HOOKS = {
    "effort-default-guard.py": GUARD_SRC,
    "secret_path_guard.py": SECRET_GUARD_SRC,
}
AGENTS_SRC_DIR = ROOT / "adoption" / "agents" / "claude"
MCP_TEMPLATE = ROOT / "adoption" / "mcp" / "claude-user.json"


class InstallError(ValueError):
    pass


def sha256sums_entries() -> dict[Path, str]:
    """SHA256SUMS entries as {resolved source path: sha256}; paths are relative to the file."""
    entries = {}
    for line in SHA256SUMS.read_text().splitlines():
        parts = line.split()
        if len(parts) == 2:
            entries[(SHA256SUMS.parent / parts[1].lstrip("*")).resolve()] = parts[0]
    return entries


def expected_sha256(source: Path) -> str:
    digest = sha256sums_entries().get(source.resolve())
    if digest is None:
        raise InstallError(f"no {source.name} entry in {SHA256SUMS}")
    return digest


def expected_guard_sha256() -> str:
    return expected_sha256(GUARD_SRC)


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def install_guard(home: Path, dry_run: bool, name: str = "effort-default-guard.py") -> str:
    source = HOOKS[name]
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


def install_guards(home: Path, dry_run: bool) -> dict[str, str]:
    """Every user-scope hook in HOOKS; all are checked before any is copied."""
    for source in HOOKS.values():
        if sha256_of(source) != expected_sha256(source):
            raise InstallError(f"refusing to install {source}: sha256 does not match {SHA256SUMS}")
    return {name: install_guard(home, dry_run, name) for name in HOOKS}


def install_agents(home: Path, dry_run: bool) -> list[str]:
    if not AGENTS_SRC_DIR.is_dir():
        raise InstallError(f"missing source directory: {AGENTS_SRC_DIR}")
    dest_dir = home / ".claude" / "agents"
    results = []
    for src in sorted(AGENTS_SRC_DIR.glob("*.md")):
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
                        replace: bool = False) -> list[str]:
    if not MCP_TEMPLATE.is_file():
        raise InstallError(f"missing template: {MCP_TEMPLATE}")
    servers = render_servers(json.loads(MCP_TEMPLATE.read_text()), home, eco_root)
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
    parser.add_argument("--only", choices=["guard", "agents", "mcp"], action="append",
                         help="Run only the named step(s); default: all three")
    parser.add_argument("--dry-run", action="store_true", help="Report what would happen; write and register nothing")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    steps = args.only or ["guard", "agents", "mcp"]
    home = Path(args.home)
    try:
        if "guard" in steps:
            install_guards(home, args.dry_run)
        if "agents" in steps:
            install_agents(home, args.dry_run)
        if "mcp" in steps:
            eco_root = Path(args.eco_root) if args.eco_root else default_eco_root(home)
            install_mcp_servers(args.claude_bin, args.dry_run, home, eco_root, args.replace_mcp)
    except FileNotFoundError as error:
        print(f"install failed: {error.filename or error} not found (pass --claude-bin)", file=sys.stderr)
        return 1
    except InstallError as error:
        print(f"install failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
