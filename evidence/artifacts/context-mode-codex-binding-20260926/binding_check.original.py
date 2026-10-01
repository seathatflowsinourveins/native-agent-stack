#!/usr/bin/env python3
"""Local integration check: which directory a Codex-launched context-mode server runs shell commands in.

Two "worktrees" (wt-a, wt-b) each have a fresh Codex session log under a scratch HOME, as two concurrent
Codex sessions would. Each context-mode server is launched the way Codex 0.155.1 launches a stdio MCP
server (codex-rs rmcp-client LocalStdioServerLauncher: env cleared to DEFAULT_ENV_VARS plus the server's
own env, then the configured cwd, or the session's cwd when none is configured), asked
ctx_execute(language="shell", code="pwd") over MCP stdio, and the directory it answers is compared with the
session that launched it. Arms:

- plugin: the context-mode Codex plugin's own server (.codex-plugin/mcp.json: `node ./start.mjs`, cwd ".",
  which Codex joins to the plugin root), from a copy of the plugin clone placed at a plugin-cache path;
- user-scope start.mjs: the adoption template's replacement (`node <npm package>/start.mjs`, no cwd, so
  the session's directory), from a copy of the pinned npm install;
- user-scope CLI: upstream's manual Codex fallback (`context-mode`, i.e. cli.bundle.mjs, no cwd).

Both packages are copied into the work directory first, so start.mjs's self-heal writes and every store
land in scratch, never in the installed tools or the real home. Prints one JSON object with every scratch
path replaced by a placeholder.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import queue
import shutil
import signal
import subprocess
import sys
import threading
import time

VERSION_DIR = "1.0.169"
# codex-rs/rmcp-client/src/utils.rs DEFAULT_ENV_VARS (unix) at rust-v0.155.1, minus the macOS-only one.
CODEX_DEFAULT_ENV_VARS = ("HOME", "LOGNAME", "PATH", "SHELL", "USER", "LANG", "LC_ALL", "TERM", "TMPDIR", "TZ")
FRESH_SECONDS, OLDER_SECONDS = 5, 90  # both inside context-mode's 5-minute session-log freshness guard


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Server:
    """One MCP stdio server in its own process group, spoken to with newline-delimited JSON-RPC."""

    def __init__(self, argv: list[str], cwd: Path, env: dict, stderr_path: Path):
        self.stderr = stderr_path.open("wb")
        self.process = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=self.stderr, start_new_session=True)
        self.lines: queue.Queue = queue.Queue()
        threading.Thread(target=self._read, daemon=True).start()
        self.next_id = 0

    def _read(self):
        for line in self.process.stdout:
            self.lines.put(line)
        self.lines.put(None)

    def send(self, message: dict):
        self.process.stdin.write((json.dumps(message) + "\n").encode())
        self.process.stdin.flush()

    def request(self, method: str, params: dict, seconds: float = 90) -> dict:
        self.next_id += 1
        self.send({"jsonrpc": "2.0", "id": self.next_id, "method": method, "params": params})
        deadline = time.monotonic() + seconds
        while True:
            line = self.lines.get(timeout=max(0.1, deadline - time.monotonic()))
            if line is None:
                raise RuntimeError(f"server closed stdout before answering {method}")
            try:
                message = json.loads(line)
            except ValueError:
                continue
            if message.get("id") == self.next_id:
                return message

    def close(self) -> int | None:
        try:
            self.process.stdin.close()
            self.process.wait(timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            pass
        for signum in (signal.SIGTERM, signal.SIGKILL):
            try:
                os.killpg(self.process.pid, signum)
            except OSError:
                break
            time.sleep(0.5)
        self.process.wait()
        self.stderr.close()
        return self.process.returncode


def write_session(home: Path, name: str, cwd: Path, age_seconds: float):
    """A Codex rollout log whose first line is the session_meta record context-mode reads (payload.cwd)."""
    path = home / ".codex" / "sessions" / "2026" / "09" / "26" / f"rollout-2026-09-26T00-00-00-{name}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"timestamp": "2026-09-26T00:00:00Z", "type": "session_meta",
                                "payload": {"id": f"session-{name}", "cwd": str(cwd)}}) + "\n")
    stamp = time.time() - age_seconds
    os.utime(path, (stamp, stamp))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--plugin-src", type=Path, required=True, help="the Codex plugin clone of context-mode")
    parser.add_argument("--npm-src", type=Path, required=True, help="the pinned npm install's package directory")
    parser.add_argument("--node", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True, help="an empty scratch directory")
    args = parser.parse_args()
    work = args.work.resolve()
    home, eco = work / "home", work / "eco"
    plugin_root = home / ".codex" / "plugins" / "cache" / "context-mode" / "context-mode" / VERSION_DIR
    npm_root = eco / "tools" / f"context-mode-{VERSION_DIR}" / "lib" / "node_modules" / "context-mode"
    shutil.copytree(args.plugin_src, plugin_root, symlinks=True)
    shutil.copytree(args.npm_src, npm_root, symlinks=True)
    git_head = subprocess.run(["git", "-C", str(plugin_root), "rev-parse", "HEAD"], capture_output=True,
                              text=True).stdout.strip()
    git_status = subprocess.run(["git", "-C", str(plugin_root), "status", "--porcelain"], capture_output=True,
                                text=True).stdout.splitlines()
    worktrees = {"a": work / "wt-a", "b": work / "wt-b"}
    for tree in worktrees.values():
        tree.mkdir()
    (work / "tmp").mkdir()
    node_dir = args.node.resolve().parent
    base_env = {name: os.environ[name] for name in CODEX_DEFAULT_ENV_VARS if name in os.environ}
    base_env.update(HOME=str(home), TMPDIR=str(work / "tmp"), PATH=f"{node_dir}:/usr/bin:/bin")
    arms = {
        "plugin": {"argv": [str(args.node), "./start.mjs"], "cwd": lambda session: plugin_root,
                   "env": {"CONTEXT_MODE_PLATFORM": "codex"}},
        "user-scope start.mjs": {"argv": [str(args.node), str(npm_root / "start.mjs")],
                                 "cwd": lambda session: worktrees[session],
                                 "env": {"RTK_TELEMETRY_DISABLED": "1", "PATH": f"{node_dir}:/usr/bin:/bin",
                                         "CONTEXT_MODE_PLATFORM": "codex"}},
        "user-scope CLI": {"argv": [str(args.node), str(npm_root / "cli.bundle.mjs")],
                           "cwd": lambda session: worktrees[session],
                           "env": {"RTK_TELEMETRY_DISABLED": "1", "PATH": f"{node_dir}:/usr/bin:/bin",
                                   "CONTEXT_MODE_PLATFORM": "codex"}},
    }
    placeholders = [(str(plugin_root), "<home>/.codex/plugins/cache/context-mode/context-mode/1.0.169"),
                    (str(npm_root), "<eco>/tools/context-mode-1.0.169/lib/node_modules/context-mode"),
                    (str(worktrees["a"]), "<work>/wt-a"), (str(worktrees["b"]), "<work>/wt-b"),
                    (str(home), "<home>"), (str(work), "<work>"), (str(args.node.resolve()), "<node>"),
                    (str(node_dir), "<node-dir>"), (str(Path.home()), "~")]

    def clean(text: str) -> str:
        for real, placeholder in placeholders:
            text = text.replace(real, placeholder)
        return text

    calls = []
    for newest in ("b", "a"):  # the session whose log was written last
        other = "a" if newest == "b" else "b"
        for arm, spec in arms.items():
            for session in ("a", "b"):
                write_session(home, newest, worktrees[newest], FRESH_SECONDS)
                write_session(home, other, worktrees[other], OLDER_SECONDS)
                env = {**base_env, **spec["env"]}
                cwd = spec["cwd"](session)
                label = f"{arm}-{session}-newest-{newest}".replace(" ", "_").replace(".", "")
                started = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                server = Server(spec["argv"], cwd, env, work / f"{label}.stderr")
                record = {"arm": arm, "launching_session": session, "newest_session_log": newest,
                          "argv": [clean(item) for item in spec["argv"]], "cwd": clean(str(cwd)),
                          "env_names": sorted(env), "started_at_utc": started}
                try:
                    init = server.request("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                                         "clientInfo": {"name": "codex-mcp-client",
                                                                        "title": "Codex", "version": "0.155.1"}})
                    server.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
                    record["server_info"] = init.get("result", {}).get("serverInfo")
                    reply = server.request("tools/call", {"name": "ctx_execute",
                                                          "arguments": {"language": "shell", "code": "pwd"}})
                    text = "".join(item.get("text", "") for item in reply.get("result", {}).get("content", []))
                    record["reply_text"] = clean(text.strip())
                    answered = next((name for name, tree in worktrees.items()
                                     if str(tree) in text.split()), None)
                    record["answered_worktree"] = answered
                    record["bound_to_its_session"] = answered == session
                except (RuntimeError, OSError, queue.Empty) as error:
                    record["error"] = clean(f"{type(error).__name__}: {error}")
                    record["bound_to_its_session"] = False
                record["server_exit"] = server.close()
                record["stderr_bytes"] = (work / f"{label}.stderr").stat().st_size
                calls.append(record)

    def summary(arm: str) -> dict:
        rows = [row for row in calls if row["arm"] == arm]
        return {"calls": len(rows), "bound_to_its_session": sum(row["bound_to_its_session"] for row in rows)}

    result = {
        "schema_version": 1,
        "evidence_class": "local_integration",
        "node": subprocess.run([str(args.node), "--version"], capture_output=True, text=True).stdout.strip(),
        "packages": {
            "plugin_clone": {
                "package_json_version": json.loads((plugin_root / "package.json").read_text())["version"],
                "git_head": git_head,
                "git_status_porcelain_before_launch": git_status,
                "start_mjs_sha256": sha256(plugin_root / "start.mjs"),
                "server_bundle_sha256": sha256(plugin_root / "server.bundle.mjs"),
            },
            "npm_install": {
                "package_json_version": json.loads((npm_root / "package.json").read_text())["version"],
                "start_mjs_sha256": sha256(npm_root / "start.mjs"),
                "server_bundle_sha256": sha256(npm_root / "server.bundle.mjs"),
                "cli_bundle_sha256": sha256(npm_root / "cli.bundle.mjs"),
            },
        },
        "calls": calls,
        "summary": {arm: summary(arm) for arm in arms},
    }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
