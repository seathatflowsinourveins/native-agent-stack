#!/usr/bin/env python3
"""local_integration: record Codex's own hooks/list currentHash for a few fixed hook shapes (throwaway CODEX_HOME).
Output: JSON list of {event, matcher, handler, key_suffix, current_hash, codex_version}."""
import json, os, subprocess, tempfile, time
from pathlib import Path

AI = "/opt/example/ai-memory --data-dir /opt/example hook --event {} --agent codex --server-url http://127.0.0.1:1"
SHAPES = [
    ("SessionStart", "", {"type": "command", "command": AI.format("session-start")}),
    ("UserPromptSubmit", "", {"type": "command", "command": AI.format("user-prompt-submit")}),
    ("SessionEnd", "", {"type": "command", "command": AI.format("session-end"), "timeout": 10}),
    ("PreToolUse", "Bash", {"type": "command", "command": "rtk hook codex", "timeout": 30,
                            "statusMessage": "rewriting"}),
    ("PostToolUse", "mcp__.*", {"type": "command", "command": AI.format("post-tool-use"), "async": True,
                                "additionalContextLimit": 4000}),
    ("Stop", None, {"type": "command", "command": "echo 'quoted \"text\" é'", "commandWindows": "echo win"}),
]
version = subprocess.run(["codex", "--version"], capture_output=True, text=True, stdin=subprocess.DEVNULL).stdout.strip()
with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as fake:
    home = str(Path(home).resolve())
    events = {}
    for event, matcher, handler in SHAPES:
        group = {"hooks": [handler]}
        if matcher is not None:
            group["matcher"] = matcher
        events.setdefault(event, []).append(group)
    Path(home, "hooks.json").write_text(json.dumps({"hooks": events}))
    Path(home, "config.toml").write_text("")
    p = subprocess.Popen(["codex", "app-server"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                         cwd=fake, env=dict(os.environ, CODEX_HOME=home, HOME=fake, RUST_LOG="error"), text=True)
    def send(m):
        p.stdin.write(json.dumps(m) + "\n"); p.stdin.flush()
    def recv(i):
        end = time.monotonic() + 60
        while time.monotonic() < end:
            m = json.loads(p.stdout.readline())
            if m.get("id") == i and ("result" in m or "error" in m):
                return m
    send({"id": 1, "method": "initialize", "params": {"clientInfo": {"name": "u5", "version": "0"}}}); recv(1)
    send({"method": "initialized"})
    send({"id": 2, "method": "hooks/list", "params": {"cwds": [fake]}})
    listed = recv(2)
    p.stdin.close(); p.wait(timeout=20)
    by_key = {h["key"].replace(home, "$CODEX_HOME"): h["currentHash"] for e in listed["result"]["data"] for h in e["hooks"]}
    out = []
    for event, matcher, handler in SHAPES:
        label = {"SessionStart": "session_start", "UserPromptSubmit": "user_prompt_submit", "SessionEnd": "session_end",
                 "PreToolUse": "pre_tool_use", "PostToolUse": "post_tool_use", "Stop": "stop"}[event]
        key = f"$CODEX_HOME/hooks.json:{label}:0:0"
        out.append({"event": event, "matcher": matcher, "handler": handler, "key": key, "current_hash": by_key.get(key)})
    print(json.dumps({"codex_version": version, "shapes": out}, indent=1, ensure_ascii=False))
