#!/usr/bin/env python3
"""Install this catalog's Claude Code user-scope profile assets onto a host:

  guard   -- sha256-checked copy of adoption/hooks/claude/effort-default-guard.py
             to ~/.claude/hooks/effort-default-guard.py
  agents  -- verbatim copies of adoption/agents/claude/*.md to ~/.claude/agents/
  mcp     -- `claude mcp add --scope user` for each server named in
             adoption/mcp/claude-user.json, idempotent (skipped when a server
             of the same name is already registered with the same config)

Each step is independently runnable (`--only guard|agents|mcp`) and safe to
re-run: the guard is only overwritten if its checksum in
adoption/hooks/claude/SHA256SUMS differs from what's already installed, agent
copies are always refreshed (they're catalog-owned files, not host edits),
and MCP registration is skipped when the existing entry already matches.
This never touches ~/.claude.json, credentials or any other account state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GUARD_SRC = ROOT / "adoption" / "hooks" / "claude" / "effort-default-guard.py"
SHA256SUMS = ROOT / "adoption" / "hooks" / "claude" / "SHA256SUMS"
AGENTS_SRC_DIR = ROOT / "adoption" / "agents" / "claude"
MCP_TEMPLATE = ROOT / "adoption" / "mcp" / "claude-user.json"


class InstallError(ValueError):
    pass


def expected_guard_sha256() -> str:
    text = SHA256SUMS.read_text()
    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1].lstrip("*").endswith("effort-default-guard.py"):
            return parts[0]
    raise InstallError(f"no effort-default-guard.py entry in {SHA256SUMS}")


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def install_guard(home: Path, dry_run: bool) -> str:
    if not GUARD_SRC.is_file():
        raise InstallError(f"missing source: {GUARD_SRC}")
    expected = expected_guard_sha256()
    actual = sha256_of(GUARD_SRC)
    if actual != expected:
        raise InstallError(
            f"refusing to install {GUARD_SRC}: sha256 {actual} does not match "
            f"{SHA256SUMS} ({expected})"
        )
    dest_dir = home / ".claude" / "hooks"
    dest = dest_dir / "effort-default-guard.py"
    if dest.is_file() and sha256_of(dest) == expected:
        print(f"guard: {dest} already matches (sha256 {expected[:12]}...); skipped")
        return "skipped"
    if dry_run:
        print(f"guard: would install {dest} (sha256 {expected[:12]}...)")
        return "planned"
    dest_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(GUARD_SRC, dest)
    dest.chmod(0o755)
    print(f"guard: installed {dest}")
    return "installed"


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


def claude_mcp_list(claude_bin: str) -> dict[str, str]:
    """name -> the exact human-readable block `claude mcp get <name>` prints,
    used only to decide whether an existing registration already matches."""
    result = subprocess.run([claude_bin, "mcp", "list"], capture_output=True, text=True, timeout=30, check=False)
    names = []
    for line in (result.stdout or "").splitlines():
        m = re.match(r"^([A-Za-z0-9_.-]+):\s", line)
        if m:
            names.append(m.group(1))
    return {name: "" for name in names}


def claude_mcp_get(claude_bin: str, name: str) -> str | None:
    result = subprocess.run([claude_bin, "mcp", "get", name], capture_output=True, text=True, timeout=30, check=False)
    if result.returncode != 0:
        return None
    return result.stdout


def existing_config_matches(existing_text: str, server_type: str, command_or_url: str, args: list[str], env: dict) -> bool:
    """Best-effort match against `claude mcp get`'s text output: same
    transport type, same command/URL, same args, and every expected env
    NAME present (values are not asserted; the running host owns them)."""
    if server_type == "http":
        return command_or_url in existing_text and "Type: http" in existing_text
    if "Type: stdio" not in existing_text:
        return False
    if command_or_url not in existing_text:
        return False
    for arg in args:
        if arg and arg not in existing_text:
            return False
    for key in env:
        if key not in existing_text:
            return False
    return True


def install_mcp_servers(claude_bin: str, dry_run: bool) -> list[str]:
    if not MCP_TEMPLATE.is_file():
        raise InstallError(f"missing template: {MCP_TEMPLATE}")
    data = json.loads(MCP_TEMPLATE.read_text())
    servers = data.get("mcpServers", {})
    results = []
    for name, spec in servers.items():
        server_type = spec.get("type", "stdio")
        command_or_url = spec["url"] if server_type == "http" else spec["command"]
        args = spec.get("args", [])
        env = spec.get("env", {})

        existing = claude_mcp_get(claude_bin, name)
        if existing is not None and existing_config_matches(existing, server_type, command_or_url, args, env):
            print(f"mcp: {name} already registered with matching config; skipped")
            results.append("skipped")
            continue

        cmd = [claude_bin, "mcp", "add", "--scope", "user"]
        if server_type != "stdio":
            cmd += ["--transport", server_type]
        for key, value in env.items():
            cmd += ["-e", f"{key}={value}"]
        cmd.append(name)
        if server_type == "http":
            cmd.append(command_or_url)
        else:
            cmd.append(command_or_url)
            if args:
                cmd.append("--")
                cmd += args

        if dry_run:
            print(f"mcp: would run: {' '.join(cmd)}")
            results.append("planned")
            continue
        if existing is not None:
            subprocess.run([claude_bin, "mcp", "remove", name, "-s", "user"],
                            capture_output=True, text=True, timeout=30, check=False)
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
            install_guard(home, args.dry_run)
        if "agents" in steps:
            install_agents(home, args.dry_run)
        if "mcp" in steps:
            install_mcp_servers(args.claude_bin, args.dry_run)
    except InstallError as error:
        print(f"install failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
