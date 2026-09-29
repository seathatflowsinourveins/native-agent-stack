"""Prove void_patterns_final.py both ways before the final X5c adjudication is dispatched; exits nonzero on any
disagreement. lane-a2/audit_selftest_a2.py with this adjudication's parts.

- Negative controls, real runs of the same runtimes: every GPT-6 run of lane A's rounds (the round-3 probe and lane,
  attempt 2's two adjudications, the final round's probe and lane) and every Claude judge whose transcript is kept
  (attempt 2's two adjudications and the final round's lane). None may hit a home, store, transcript, live-checkout
  or adjudication-runs part, MAPPING or INJECTED. Their own work directories (now under .hold3, and the final lane's
  k2 paths) are the only hits allowed; this adjudication's fresh paths avoid them.
- Synthetic cases, one judge each: every planted access or injected text must void with the named part, and every
  allowed read, and repository prose read as a tool result, must come back clean.
Writes audit-selftest-final.json.
"""
import json
import sys
from pathlib import Path

X = Path(__file__).resolve().parent
sys.path.insert(0, str(X))
import audit_final as au  # noqa: E402

HOLD = X.parent.parent.parent
SID = "<session-id>"
SUB = Path.home() / f".claude/projects/<project-dir>/{SID}/subagents"
SP = f"<session-root>/{SID}/scratchpad"
J7 = f"{SP}/j7/x5c"
F = X / "selftest"
ALLOWED_REAL = {"ACCESS:hold_and_work_dirs", "ACCESS:other_lane"}
out, bad = {"real": {}, "synthetic": {}}, []

real = {"gpt6-probe-r3": ("gpt6", HOLD / "convergence-r3/gpt6/gpt6-probe-r3"),
        "lane-a-gpt6": ("gpt6", HOLD / "convergence-r3/gpt6/lane-a-gpt6"),
        "adj2-gpt6-AB": ("gpt6", HOLD / "j6/x5/runs/gpt6/x5-adj-AB"),
        "adj2-gpt6-BA": ("gpt6", HOLD / "j6/x5/runs/gpt6/x5-adj-BA"),
        "final-gpt6-probe": ("gpt6", HOLD / "k2/work/gpt6/a2-probe"),
        "final-gpt6-lane": ("gpt6", HOLD / "k2/work/gpt6/a2-gpt6"),
        "adj2-claude-AB": ("claude", SUB / "agent-<agent-id-1>.jsonl"),
        "adj2-claude-BA": ("claude", SUB / "agent-<agent-id-2>.jsonl"),
        "final-claude-lane": ("claude", SUB / "agent-<agent-id-3>.jsonl")}
for name, (kind, path) in real.items():
    if not path.exists():
        bad.append(f"real {name}: missing {path}")
        continue
    r = (au.audit_gpt6 if kind == "gpt6" else au.audit_claude)(path).result()
    parts = sorted({h["pattern"] for h in r["hits"]})
    out["real"][name] = {"hit_parts": parts, "hits": len(r["hits"]), "items": r["items"]}
    if set(parts) - ALLOWED_REAL:
        bad.append(f"real {name}: {parts}")


def gpt6_case(cmd):
    job = F / "gpt6-case"
    job.mkdir(parents=True, exist_ok=True)
    (job / "prompt.txt").write_text("Task: adjudicate unit X5c.\n")
    (job / "events.jsonl").write_text(json.dumps({"type": "item.completed", "item": {
        "type": "command_execution", "command": cmd, "aggregated_output": "", "exit_code": 0}}) + "\n")
    return au.audit_gpt6(job).result()


def claude_case(events):
    F.mkdir(parents=True, exist_ok=True)
    t = F / "claude-case.jsonl"
    t.write_text("\n".join(json.dumps(e) for e in [
        {"type": "user", "message": {"role": "user", "content": "Adjudicate unit X5c."}}] + events) + "\n")
    return au.audit_claude(t).result()


def read(path, tool="Read"):
    key = "file_path" if tool == "Read" else "path"
    return [{"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "t1", "name": tool,
                                                           "input": {key: path, "pattern": "x"}}]}}]


def hook(text):
    return [{"type": "attachment", "attachment": {"type": "hook_additional_context", "content": [text]}}]


def result(text, kind="tool_result"):
    return [{"type": "user", "message": {"content": [{"type": kind, "tool_use_id": "t1", "content": text}]}}]


TALLY = ('{"X5a": {"lanes": {"gpt6": ["agree", 0.98], "claude": ["agree", 0.85]}, "outcome": "apply the proposed '
         'change"}, "X5c": {"lanes": {"gpt6": ["agree", 0.94], "claude": ["amend", 0.6]}}}')
PRINT = "===== gpt6 ['items']\n-- X5a agree 0.98\nTEXT: \nREASONS: The proposed line carries the operator's heading"
STATUS = ("X5c split: the GPT-6 lane accepted the proposal, and the Claude lane amended it to keep the \"installed "
          "client is also a source of truth\" clause.")
cases = [
    ("gpt6", "/bin/bash -lc 'cat ~/.codex/sessions/2026/09/28/rollout-x.jsonl'", {"ACCESS:codex_home"}),
    ("gpt6", "/bin/bash -lc 'rtk rg -n Top ~/.codex'", {"ACCESS:codex_home"}),
    ("gpt6", "/bin/bash -lc 'rtk cat ~/.codex/RTK.md'", set()),
    ("gpt6", "/bin/bash -lc 'rtk cat ~/.codex/plugins/cache/<marketplace>/<plugin>/<version>/skills/"
             "<skill>/SKILL.md'", set()),
    ("gpt6", "/bin/bash -lc 'ls ~/.codex/plugins/cache'", {"ACCESS:codex_home"}),
    ("gpt6", "/bin/bash -lc 'cat ~/.codex/skills/<skill>/sessions/x.jsonl'", {"ACCESS:codex_home"}),
    ("gpt6", "/bin/bash -lc 'cat ~/.codex/plugins/cache/m/p/../../../history.jsonl/skills/x'",
     {"ACCESS:codex_home"}),
    ("gpt6", "/bin/bash -lc \"sed -n '1,80p' ~/.agents/skills/<skill>/SKILL.md\"",
     set()),
    ("gpt6", "/bin/bash -lc 'cat <projects>/p/memory/MEMORY.md'", {"ACCESS:claude_home"}),
    ("gpt6", "/bin/bash -lc 'ls ~/.local/share/ai-memory'", {"ACCESS:memory_store"}),
    ("gpt6", f"/bin/bash -lc 'cat <tmp-root>/p/{SID}/subagents/agent-x.jsonl'", {"ACCESS:session_transcripts"}),
    ("gpt6", "/bin/bash -lc 'cat ~/code/native-agent-stack/AGENTS.md'", {"ACCESS:live_checkout"}),
    ("gpt6", f"/bin/bash -lc 'cat {SP}/k2/work/gpt6/a2-gpt6/events.jsonl'",
     {"ACCESS:hold_and_work_dirs", "ACCESS:other_lane", "MAPPING"}),
    ("gpt6", f"/bin/bash -lc 'ls {SP}/.hold3/k2/work/gpt6'", {"ACCESS:hold_and_work_dirs", "ACCESS:other_lane"}),
    ("gpt6", f"/bin/bash -lc 'cat {SP}/.hold3/convergence-r3/lane-a2/returns/claude.json'",
     {"ACCESS:hold_and_work_dirs", "MAPPING"}),
    ("gpt6", "/bin/bash -lc 'ls ../gpt6'", {"ACCESS:adjudication_runs"}),
    ("gpt6", f"/bin/bash -lc 'cat {J7}/runs/gpt6/x5c-final-BA/events.jsonl'", {"ACCESS:adjudication_runs"}),
    ("gpt6", f"/bin/bash -lc 'sed -n 1,60p {J7}/root/amended/tests/test_codex_worker_lane.py'", set()),
    ("gpt6", f"/bin/bash -lc 'git diff --no-index {J7}/root/proposed/adoption {J7}/root/amended/adoption'", set()),
    ("gpt6", f"/bin/bash -lc 'cd {J7}/root/amended && python3 -B -m unittest tests.test_codex_worker_lane'", set()),
    ("claude", read(f"{J7}/root/amended/adoption/templates/codex.AGENTS.template.md"), set()),
    ("claude", read(f"{J7}/adjudication-inputs/x5c.AB.json"), set()),
    ("claude", read(f"{J7}/packets/x5c.json"), set()),
    ("claude", read(f"{SP}/.hold3/k2/work/gpt6/a2-gpt6/result.json"),
     {"ACCESS:hold_and_work_dirs", "ACCESS:other_lane", "MAPPING"}),
    ("claude", read(f"{SP}/.hold3/k2/work", tool="Glob"), {"ACCESS:hold_and_work_dirs", "ACCESS:other_lane"}),
    ("claude", read(f"{J7}/runs/gpt6", tool="Glob"), {"ACCESS:adjudication_runs"}),
    ("claude", read(f"{SP}/.hold3/convergence-r3/lane-a2/tally-final.json"),
     {"ACCESS:hold_and_work_dirs", "MAPPING"}),
    ("claude", read(f"/tmp/c/{SID}/tasks/x.output"), {"ACCESS:session_transcripts"}),
    ("claude", [{"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "t1",
                                                               "name": "mcp__ai-memory__memory_query",
                                                               "input": {"query": "x"}}]}}], {"mcp__ call"}),
    ("claude", hook(TALLY), {"MAPPING", "INJECTED"}),
    ("claude", hook(PRINT), {"INJECTED"}),
    ("claude", hook(STATUS), {"INJECTED"}),
    ("claude", hook("So never self-write without a SOTA source."), {"PHRASES"}),
    ("claude", result("Return B keeps the clause; the Claude lane amended it.", "advisor_tool_result"),
     {"INJECTED"}),
    ("claude", result("docs: the GPT-6 lane and the Claude lane agreed on F1 (round 1)."), set()),
    ("claude", result("see lane-a/claude.json"), {"MAPPING"}),
    ("claude", hook("<context_guidance><tip>Reading to Edit the file? Read is correct.</tip></context_guidance>"),
     set()),
    ("claude", hook('{"gpt6": {"verdict": "amend", "confidence": 0.6}}'), {"MAPPING", "INJECTED"}),
    ("claude", [{"type": "attachment", "attachment": {"type": "prompt_snapshot", "systemPrompt": [
        "a phrase that attributes a return to a reviewer family, such as \"the Codex lane\" or \"Claude's proposal\""]}}],
     set()),
    ("claude", [{"type": "attachment", "attachment": {"type": "session_context", "context": {"gitStatus":
        "4f31ef46 OmniRoute routing convergence: GPT-6 lane account-routing adjudication (51 items)"}}}], set()),
    ("claude", [{"type": "attachment", "attachment": {"type": "session_context", "context": {"gitStatus":
        '{"gpt6": ["agree", 0.94]}'}}}], {"MAPPING"}),
]
for kind, payload, want in cases:
    r = gpt6_case(payload) if kind == "gpt6" else claude_case(payload)
    got = {h["pattern"] for h in r["hits"]}
    label = payload if isinstance(payload, str) else json.dumps(payload)[:160]
    out["synthetic"][label] = {"want": sorted(want), "got": sorted(got)}
    if got != want:
        bad.append(f"synthetic {label}: want {sorted(want)} got {sorted(got)}")
out["disagreements"] = bad
(X / "audit-selftest-final.json").write_text(json.dumps(out, indent=1) + "\n")
for k, r in out["real"].items():
    print("real", k, r["hit_parts"], r["hits"])
print(len(cases), "synthetic cases;", len(bad), "disagreements")
for b in bad:
    print("  ", b)
sys.exit(1 if bad else 0)
