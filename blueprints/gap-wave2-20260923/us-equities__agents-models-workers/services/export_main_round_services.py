#!/usr/bin/env python3
"""Fix round 2: commit how the main-round disposable services were started and stopped.

The main round started Qdrant 1.19.1 (127.0.0.1:27333/27334) and ai-memory 2.3.2 serve
(127.0.0.1:27374, embedding_provider none) with ad hoc Bash calls and no script. This exports
those exact calls and their outputs from the unit's own session transcript (by tool_use id),
plus redacted heads of the cached service logs and the edited config lines.
Nothing is re-run. Host paths become $HOME; ANSI colour codes are stripped; the shell-wrapper
lines of the harness (which carry session ids and plugin paths) are dropped from pgrep output.
Usage: export_main_round_services.py TRANSCRIPT_JSONL OUT_TXT
"""
import json, re, sys
from pathlib import Path

HOME = str(Path.home())
CACHE = Path(HOME) / ".cache/gap-wave2-20260923/agents-models-workers"
IDS = {"toolu_01RvqTTQjWGiBxcjQYEwNvzs": "1 qdrant start",
       "toolu_01RHwpoxj3d5wtzGZy6WBU7w": "2 ai-memory 2.3.2 init",
       "toolu_01Lk2nhxbQuyCgxNSmN2k3wE": "4 ai-memory 2.3.2 serve",
       "toolu_01YTXe8KpYqitpCPyJmspjrt": "5 stop both"}
SED_ID = "3 config edit (bind 27374, embedding_provider none)"
ANSI = re.compile(r"\x1b\[[0-9;]*m")


def red(s):
    return ANSI.sub("", s).replace(HOME, "$HOME")


calls = {}
for line in open(sys.argv[1]):
    try:
        o = json.loads(line)
    except ValueError:
        continue
    c = o.get("message", {}).get("content")
    if not isinstance(c, list):
        continue
    for b in c:
        if b.get("type") == "tool_use":
            cmd = b.get("input", {}).get("command", "")
            key = IDS.get(b.get("id"))
            if key is None and "aim-data/config.toml" in cmd and "sed -i" in cmd:
                key = SED_ID
            if key:
                calls.setdefault(key, {})["cmd"] = cmd
                calls[key]["at"] = o.get("timestamp")
                calls[key]["id"] = b.get("id")
        if b.get("type") == "tool_result":
            for k, v in calls.items():
                if v.get("id") == b.get("tool_use_id"):
                    cc = b.get("content")
                    if isinstance(cc, list):
                        cc = "\n".join(x.get("text", "") for x in cc if isinstance(x, dict))
                    v["out"] = cc
out = ["# Main-round disposable services: exact commands and outputs (exported, not re-run)", ""]
for k in sorted(calls):
    v = calls[k]
    body = "\n".join(l for l in red(v.get("out", "")).splitlines() if "/bin/bash -c source" not in l)
    out += [f"## {k}  issued_at={v['at']}  tool_use_id={v['id']}", "$ " + red(v["cmd"]), body, ""]
out += ["## cached config lines now: $HOME/.cache/gap-wave2-20260923/agents-models-workers/aim-data/config.toml"]
for i, l in enumerate((CACHE / "aim-data/config.toml").read_text().splitlines(), 1):
    if l.startswith(("bind =", "embedding_provider =")):
        out.append(f"{i}: {l}")
out += ["", "## head of logs/aim-serve.log (first 3 lines) and its shutdown line"]
aim = (CACHE / "logs/aim-serve.log").read_text(errors="replace").splitlines()
out += [red(l) for l in aim[:3]] + [red(l) for l in aim if "shutdown signal received" in l]
out += ["", "## logs/qdrant.log: version, bind, telemetry and shutdown lines"]
for l in (CACHE / "logs/qdrant.log").read_text(errors="replace").splitlines():
    l = red(l)
    if re.search(r"Version:|listening on|Telemetry reporting|SIGTERM", l):
        out.append(l)
Path(sys.argv[2]).write_text("\n".join(out) + "\n")
print(f"wrote {len(out)} lines, calls: {sorted(calls)}")
