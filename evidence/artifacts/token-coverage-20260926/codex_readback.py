#!/usr/bin/env python3
"""Value-free readback of two Codex MCP server registrations, through Codex itself.

Runs `codex --version`, `codex mcp get headroom --json` and `codex mcp get context-mode --json`
from the current directory, with stdin from /dev/null, and prints one JSON object of facts derived
from their output: exit codes, the sha256 of each raw stdout, environment variable names (never
values), argument lists, and booleans about the working directory Codex will start each server in.
The raw output is not printed: it holds this host's absolute paths. Run it from a directory with no
project `.codex/config.toml`, which is what a fresh worktree sees (the user scope plus plugins).
"""

from __future__ import annotations

import datetime
import hashlib
import json
import re
import subprocess
from pathlib import PurePosixPath

# context-mode's own plugin-install-path test (src/util/project-dir.ts isPluginInstallPath, mirrored in
# start.mjs): a start directory that matches it is never used as the project directory.
PLUGIN_INSTALL_PATH = re.compile(r"[/\\]\.(claude|codex)[/\\]plugins[/\\](cache|marketplaces)[/\\]")


def run(argv: list[str]) -> tuple[dict, str]:
    completed = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60,
                               check=False)
    return ({"argv": argv, "exit": completed.returncode,
             "stdout_sha256": hashlib.sha256(completed.stdout.encode()).hexdigest(),
             "stderr_bytes": len(completed.stderr.encode())}, completed.stdout)


def server_facts(stdout: str) -> dict:
    server = json.loads(stdout)
    transport = server.get("transport") or {}
    cwd = transport.get("cwd")
    facts = {
        "enabled": server.get("enabled"),
        "transport": transport.get("type"),
        "command_basename": PurePosixPath(transport["command"]).name if transport.get("command") else None,
        "args_basenames": [PurePosixPath(arg).name if "/" in arg and not arg.startswith("http") else arg
                           for arg in transport.get("args") or []],
        "env_names": sorted(transport.get("env") or {}),
        "env_vars_forwarded": sorted(transport.get("env_vars") or []),
        "cwd_set": cwd is not None,
    }
    if cwd is not None:
        facts["cwd_is_plugin_install_path"] = PLUGIN_INSTALL_PATH.search(cwd) is not None
        parts = PurePosixPath(cwd).parts
        facts["cwd_last_five_parts"] = list(parts[-5:])
    return facts


def main() -> int:
    started = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    version, version_out = run(["codex", "--version"])
    commands, servers = [version], {}
    for name in ("headroom", "context-mode"):
        record, stdout = run(["codex", "mcp", "get", name, "--json"])
        commands.append(record)
        servers[name] = server_facts(stdout) if record["exit"] == 0 else None
    print(json.dumps({"schema_version": 1, "observed_at_utc": started, "codex_version": version_out.strip(),
                      "commands": commands, "servers": servers}, indent=2))
    return 0 if all(record["exit"] == 0 for record in commands) else 1


if __name__ == "__main__":
    raise SystemExit(main())
