#!/usr/bin/env python3
"""local_integration: record Codex's own hooks/list currentHash for a few fixed hook shapes (throwaway CODEX_HOME).
Output: {codex_version, shapes: [{event, matcher, handler, key, current_hash}]}. Codex is asked through
codex_oracle.hooks_list, which reads with a deadline (--timeout seconds) and ends the app-server with bounded waits."""
import argparse, json, subprocess, tempfile
from pathlib import Path

from codex_oracle import hooks_list

parser = argparse.ArgumentParser()
parser.add_argument("--timeout", type=float, default=60.0, help="seconds to wait for the app-server's answers")
args = parser.parse_args()
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
version = subprocess.run(["codex", "--version"], capture_output=True, text=True, stdin=subprocess.DEVNULL,
                         timeout=60).stdout.strip()
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
    listed = hooks_list(Path(home), Path(fake).resolve(), timeout=args.timeout)
    by_key = {h["key"].replace(home, "$CODEX_HOME"): h["currentHash"] for e in listed for h in e["hooks"]}
    out = []
    for event, matcher, handler in SHAPES:
        label = {"SessionStart": "session_start", "UserPromptSubmit": "user_prompt_submit", "SessionEnd": "session_end",
                 "PreToolUse": "pre_tool_use", "PostToolUse": "post_tool_use", "Stop": "stop"}[event]
        key = f"$CODEX_HOME/hooks.json:{label}:0:0"
        out.append({"event": event, "matcher": matcher, "handler": handler, "key": key, "current_hash": by_key.get(key)})
    print(json.dumps({"codex_version": version, "shapes": out}, indent=1, ensure_ascii=False))
