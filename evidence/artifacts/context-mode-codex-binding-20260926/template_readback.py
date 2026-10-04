#!/usr/bin/env python3
"""Read the rendered Codex user-scope template back through Codex itself, in a scratch CODEX_HOME.

Renders adoption/templates/codex.config.template.toml with tools/adoption/render_config.py --host example,
copies the installed context-mode Codex plugin into the scratch CODEX_HOME's plugin cache, and runs
`codex mcp list --json` from an empty directory for three configurations: the template as rendered, the
template without its [plugins."context-mode@context-mode".mcp_servers.context-mode] override, and the
template without that override and without its [mcp_servers.context-mode] entry (the plugin alone, as
before this repair). Prints, per configuration, which context-mode server Codex would start: its command
basename, arguments' basenames and whether it has a working directory (a plugin-root one, or none, which
Codex replaces with the session's own directory), plus the headroom server's environment variable names.
Needs the checkout root, the plugin directory and an empty scratch directory.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys

OVERRIDE = ('\n# Replaced by the session-bound [mcp_servers.context-mode] above.\n'
            '[plugins."context-mode@context-mode".mcp_servers.context-mode]\nenabled = false\n')
USER_ENTRY = re.compile(r"\n\[mcp_servers\.context-mode\]\n.*?\n\[mcp_servers\.context-mode\.env\]\n(?:[^\n]+\n)+",
                        re.S)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--checkout", type=Path, required=True)
    parser.add_argument("--plugin", type=Path, required=True, help="the installed context-mode plugin directory")
    parser.add_argument("--work", type=Path, required=True)
    args = parser.parse_args()
    work = args.work.resolve()
    out, home, empty = work / "out", work / "home" / ".codex", work / "empty"
    plugin_root = home / "plugins/cache/context-mode/context-mode" / args.plugin.name
    empty.mkdir(parents=True)
    render = subprocess.run([sys.executable, str(args.checkout / "tools/adoption/render_config.py"), "--host",
                             "example", "--out", str(out)], capture_output=True, text=True, check=False)
    rendered = (out / "codex.config.toml").read_text()
    user_entry = USER_ENTRY.search(rendered)
    if OVERRIDE not in rendered or user_entry is None:
        raise SystemExit("the rendered template lacks the context-mode entry or the plugin override")
    shutil.copytree(args.plugin, plugin_root, symlinks=True)
    variants = {
        "template as rendered": rendered,
        "template without the plugin-server override": rendered.replace(OVERRIDE, "\n"),
        "plugin server alone (before this repair)":
            rendered.replace(OVERRIDE, "\n").replace(user_entry.group(0), "\n"),
    }
    base_env = {key: os.environ[key] for key in ("HOME", "PATH", "LANG", "USER", "LOGNAME") if key in os.environ}
    results = []
    for name, config in variants.items():
        (home / "config.toml").write_text(config)
        listed = subprocess.run(["codex", "mcp", "list", "--json"], cwd=empty,
                                env={**base_env, "CODEX_HOME": str(home)}, stdin=subprocess.DEVNULL,
                                capture_output=True, text=True, check=False)
        servers = json.loads(listed.stdout) if listed.returncode == 0 else []
        matches = [server for server in servers if server.get("name") == "context-mode"]
        facts = []
        for server in matches:
            transport = server.get("transport") or {}
            cwd = transport.get("cwd")
            facts.append({"enabled": server.get("enabled"),
                          "command_basename": PurePosixPath(transport.get("command") or "").name,
                          "args_basenames": [PurePosixPath(arg).name for arg in transport.get("args") or []],
                          "env_names": sorted(transport.get("env") or {}),
                          "cwd": None if cwd is None else
                          "plugin root" if Path(cwd).resolve() == plugin_root.resolve() else "other"})
        headroom = [sorted((server.get("transport") or {}).get("env") or {}) for server in servers
                    if server.get("name") == "headroom"]
        results.append({"configuration": name, "codex_mcp_list_exit": listed.returncode,
                        "servers_listed": sorted(server.get("name") for server in servers),
                        "context_mode_servers": facts, "headroom_env_names": headroom})
    version = subprocess.run(["codex", "--version"], capture_output=True, text=True, check=False).stdout.strip()
    print(json.dumps({"schema_version": 1, "codex_version": version, "render_exit": render.returncode,
                      "render_host_values": "adoption/hosts/example.json", "results": results}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
