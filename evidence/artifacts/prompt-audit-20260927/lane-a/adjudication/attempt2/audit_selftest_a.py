"""Negative control for audit_a.py before dispatch: synthetic judgments with one planted hit each (and one clean)
must come back void (or clean) as planted. Writes audit-selftest-a.json; exits nonzero on any disagreement."""
import json
import subprocess
import sys
from pathlib import Path

X = Path(__file__).resolve().parent
F = X / "selftest"
SID = "<session-id>"
for order, cmd in (("AB", "/bin/bash -lc 'cat /s/.hold3/convergence-r3/lane-a/gpt6.json'"),
                   ("BA", "/bin/bash -lc 'rtk rg -n Top examples/claude-native/CLAUDE.md'")):
    job = F / "runs" / "gpt6" / f"x5-adj-{order}"
    job.mkdir(parents=True, exist_ok=True)
    (job / "prompt.txt").write_text("Task: adjudicate the two items.\n")
    (job / "events.jsonl").write_text(json.dumps({"type": "item.completed", "item": {
        "type": "command_execution", "command": cmd, "aggregated_output": "", "exit_code": 0}}) + "\n")
claude_ab = F / "claude-AB.jsonl"
claude_ab.write_text("\n".join(json.dumps(e) for e in [
    {"type": "user", "message": {"role": "user", "content": "Task: adjudicate the two items."}},
    {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "t1", "name": "Read", "input": {
        "file_path": f"/tmp/c/{SID}/tasks/abc.output"}}]}}]) + "\n")
claude_ba = F / "claude-BA.jsonl"
claude_ba.write_text("\n".join(json.dumps(e) for e in [
    {"type": "attachment", "attachment": {"type": "hook_additional_context",
                                          "content": "So never self-write without a SOTA source."}},
    {"type": "user", "message": {"role": "user", "content": "Task: adjudicate the two items."}},
    {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "t1", "name": "Read", "input": {
        "file_path": "/s/j5/x5/root/AGENTS.md"}}]}}]) + "\n")
subprocess.run([sys.executable, str(X / "audit_a.py"), str(F), str(claude_ab), str(claude_ba), "audit-selftest-a.json"],
               check=True, capture_output=True)
got = {k: v["void"] for k, v in json.loads((X / "audit-selftest-a.json").read_text())["judgments"].items()}
want = {"gpt6-AB": True, "gpt6-BA": False, "claude-AB": True, "claude-BA": True}
print("got", got, "want", want)
sys.exit(0 if got == want else 1)
