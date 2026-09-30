"""Prove void_patterns_a2.py both ways before dispatch; exits nonzero on any disagreement.

- Negative controls, real runs of the same runtimes: the GPT-6 probe and lane-A GPT-6 lane of round 3 and attempt 2's
  two GPT-6 adjudications (each reads ~/.codex/RTK.md and a skill under ~/.agents at startup), and attempt 2's two
  Claude adjudications. None may hit a home, store, transcript, live-checkout or other-lane part; the only hits
  allowed are their own work directories (hold_and_work_dirs), which the final round's fresh paths avoid.
- Positive and negative synthetic cases, one judge each: every planted access must void with the named part, and
  every allowed read must come back clean.
Writes audit-selftest-a2.json.
"""
import json
import sys
from pathlib import Path

X = Path(__file__).resolve().parent
sys.path.insert(0, str(X))
import audit_a2 as au  # noqa: E402

HOLD = X.parent.parent
SUB = Path.home() / ".claude/projects/<project-dir>/<session-id>/subagents"
SID = "<session-id>"
K2 = "<session-root>/" + SID + "/scratchpad/k2"
F = X / "selftest"
ALLOWED_REAL = {"ACCESS:hold_and_work_dirs"}
out, bad = {"real": {}, "synthetic": {}}, []

real = {"gpt6-probe-r3": ("gpt6", HOLD / "convergence-r3/gpt6/gpt6-probe-r3"),
        "lane-a-gpt6": ("gpt6", HOLD / "convergence-r3/gpt6/lane-a-gpt6"),
        "adj2-gpt6-AB": ("gpt6", HOLD / "j6/x5/runs/gpt6/x5-adj-AB"),
        "adj2-gpt6-BA": ("gpt6", HOLD / "j6/x5/runs/gpt6/x5-adj-BA"),
        "adj2-claude-AB": ("claude", SUB / "agent-<agent-id-1>.jsonl"),
        "adj2-claude-BA": ("claude", SUB / "agent-<agent-id-2>.jsonl")}
for name, (kind, path) in real.items():
    r = (au.audit_gpt6 if kind == "gpt6" else au.audit_claude)(path).result()
    parts = sorted({h["pattern"] for h in r["hits"]})
    out["real"][name] = {"hit_parts": parts, "hits": len(r["hits"])}
    if set(parts) - ALLOWED_REAL:
        bad.append(f"real {name}: {parts}")


def gpt6_case(cmd):
    job = F / "gpt6-case"
    job.mkdir(parents=True, exist_ok=True)
    (job / "prompt.txt").write_text("Task: judge the two items.\n")
    (job / "events.jsonl").write_text(json.dumps({"type": "item.completed", "item": {
        "type": "command_execution", "command": cmd, "aggregated_output": "", "exit_code": 0}}) + "\n")
    return au.audit_gpt6(job).result()


def claude_case(events):
    F.mkdir(parents=True, exist_ok=True)
    t = F / "claude-case.jsonl"
    t.write_text("\n".join(json.dumps(e) for e in [
        {"type": "user", "message": {"role": "user", "content": "Task: judge the two items."}}] + events) + "\n")
    return au.audit_claude(t).result()


def read(path, tool="Read"):
    key = "file_path" if tool == "Read" else "path"
    return [{"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "t1", "name": tool,
                                                           "input": {key: path, "pattern": "x"}}]}}]


cases = [
    ("gpt6", "/bin/bash -lc 'cat ~/.codex/sessions/2026/09/28/rollout-x.jsonl'", {"ACCESS:codex_home"}),
    ("gpt6", "/bin/bash -lc 'rtk rg -n Top ~/.codex'", {"ACCESS:codex_home"}),
    ("gpt6", "/bin/bash -lc 'sqlite3 $HOME/.codex/state_5.sqlite .tables'", {"ACCESS:codex_home"}),
    ("gpt6", "/bin/bash -lc 'rtk cat ~/.codex/RTK.md'", set()),
    ("gpt6", "/bin/bash -lc 'cat ~/.codex/AGENTS.md'", set()),
    ("gpt6", "/bin/bash -lc \"sed -n '1,80p' ~/.agents/skills/<skill>/SKILL.md\"",
     set()),
    ("gpt6", "/bin/bash -lc 'ls ~/.claude/context-mode'", {"ACCESS:claude_home"}),
    ("gpt6", "/bin/bash -lc 'cat <projects>/p/memory/MEMORY.md'", {"ACCESS:claude_home"}),
    ("gpt6", "/bin/bash -lc 'cat ~/.claude/CLAUDE.md'", set()),
    ("gpt6", "/bin/bash -lc 'ls ~/.local/share/ai-memory'", {"ACCESS:memory_store"}),
    ("gpt6", f"/bin/bash -lc 'cat <tmp-root>/p/{SID}/tasks/abc.output'", {"ACCESS:session_transcripts"}),
    ("gpt6", "/bin/bash -lc 'cat ~/code/native-agent-stack/AGENTS.md'", {"ACCESS:live_checkout"}),
    ("gpt6", "/bin/bash -lc 'ls ../../../.hold3'", {"ACCESS:hold_and_work_dirs"}),
    ("gpt6", f"/bin/bash -lc 'git diff --no-index {K2}/root/base/AGENTS.md {K2}/root/proposed/AGENTS.md'", set()),
    ("gpt6", f"/bin/bash -lc 'cat {K2}/work/gpt6/a2-gpt6/prompt.txt'", set()),
    ("claude", read(f"{K2}/work/gpt6/a2-gpt6/result.json"), {"ACCESS:other_lane"}),
    ("claude", read(f"/tmp/c/{SID}/subagents/agent-x.jsonl"), {"ACCESS:session_transcripts"}),
    ("claude", read("<projects>", tool="Grep"), {"ACCESS:claude_home"}),
    ("claude", read(f"{K2}/root/base/examples/claude-native/CLAUDE.md"), set()),
    ("claude", [{"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "t1",
                                                               "name": "mcp__ai-memory__memory_query",
                                                               "input": {"query": "x"}}]}}], {"mcp__ call"}),
    ("claude", [{"type": "attachment", "attachment": {"type": "hook_additional_context",
                                                      "content": "So never self-write without a SOTA source."}}],
     {"PHRASES"}),
    ("claude", [{"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t1",
                                                          "content": "see lane-a/claude.json"}]}}], {"MAPPING"}),
]
for kind, payload, want in cases:
    r = gpt6_case(payload) if kind == "gpt6" else claude_case(payload)
    got = {h["pattern"] for h in r["hits"]}
    label = payload if isinstance(payload, str) else json.dumps(payload)[:160]
    out["synthetic"][label] = {"want": sorted(want), "got": sorted(got)}
    if got != want:
        bad.append(f"synthetic {label}: want {sorted(want)} got {sorted(got)}")
out["disagreements"] = bad
(X / "audit-selftest-a2.json").write_text(json.dumps(out, indent=1) + "\n")
for k, r in out["real"].items():
    print("real", k, r)
print(len(cases), "synthetic cases;", len(bad), "disagreements")
for b in bad:
    print("  ", b)
sys.exit(1 if bad else 0)
