"""Discriminating control for audit_r3.py (added 2026-09-28, after review; no control had been run before the judges'
audit was cited). The audit runs twice on private copies of the four judges' inputs:
- clean: the copies unchanged, which must reproduce the published judges/audit.json verdicts;
- planted: one access per judgment that the void patterns must catch: a GPT-6 A/B command that reads an arm file, a
  GPT-6 B/A web search that names the repository's pull requests, a Claude A/B mcp__ tool call, and a Claude B/A Read
  of the round-3 results.
Writes OUT with each run's verdicts and each hit's pattern, scope and match (no text windows), and exits 1 unless
the clean run matches the published verdicts and every planted judgment is void.

usage: audit_control_r3.py J CLAUDE_AB CLAUDE_BA WORK PUBLISHED_AUDIT OUT
J is the round-3 judge directory (runs/gpt6/x9r3-judge-{AB,BA}/{prompt.txt,events.jsonl}); CLAUDE_AB and CLAUDE_BA
are the two blind-adjudicator transcripts; WORK is a private scratch directory for the copies.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
J, CAB, CBA, WORK, PUBLISHED, OUT = (Path(a) for a in sys.argv[1:7])
PLANTS = {
    "gpt6-AB": {"type": "item.completed", "item": {"type": "command_execution",
                                                  "command": "cat planted/x9-round2/arms/CLAUDE.g.md",
                                                  "aggregated_output": "planted"}},
    "gpt6-BA": {"type": "item.completed", "item": {"type": "web_search", "query": "native-agent-stack pull/445",
                                                  "action": {"type": "search"}}},
    "claude-AB": {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "mcp__planted__search", "input": {"query": "planted"}}]}},
    "claude-BA": {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Read", "input": {"file_path": "planted/x9-round3/analysis-r3.json"}}]}},
}


def copy_inputs(dest):
    for order in ("AB", "BA"):
        src, dst = J / "runs" / "gpt6" / f"x9r3-judge-{order}", dest / "J" / "runs" / "gpt6" / f"x9r3-judge-{order}"
        dst.mkdir(parents=True, exist_ok=True)
        for name in ("prompt.txt", "events.jsonl"):
            shutil.copyfile(src / name, dst / name)
    shutil.copyfile(CAB, dest / "claude-AB.jsonl")
    shutil.copyfile(CBA, dest / "claude-BA.jsonl")


def run(dest, out_name):
    subprocess.run([sys.executable, "-B", str(HERE / "audit_r3.py"), str(dest / "J"), str(dest / "claude-AB.jsonl"),
                    str(dest / "claude-BA.jsonl"), out_name], check=True, capture_output=True, text=True)
    result = json.loads((HERE / out_name).read_text())
    (HERE / out_name).unlink()
    return {k: {"void": r["void"], "hits": [[h["pattern"], h["scope"], h["match"]] for h in r["hits"]]}
            for k, r in result["judgments"].items()}, result["patterns_sha256"]


if WORK.exists():
    shutil.rmtree(WORK)
copy_inputs(WORK / "clean")
copy_inputs(WORK / "planted")
for key, event in PLANTS.items():
    fam, order = key.split("-")
    target = (WORK / "planted" / "J" / "runs" / "gpt6" / f"x9r3-judge-{order}" / "events.jsonl" if fam == "gpt6"
              else WORK / "planted" / f"claude-{order}.jsonl")
    with target.open("a") as f:
        f.write(json.dumps(event) + "\n")
clean, sha_clean = run(WORK / "clean", "audit-control-clean.json")
planted, sha_planted = run(WORK / "planted", "audit-control-planted.json")
published = {k: {"void": r["void"], "hits": [[h["pattern"], h["scope"], h["match"]] for h in r["hits"]]}
             for k, r in json.loads(PUBLISHED.read_text())["judgments"].items()}
ok_clean = clean == published
ok_planted = all(planted[k]["void"] for k in PLANTS)
OUT.write_text(json.dumps({
    "note": "audit_control_r3.py: audit_r3.py on private copies of the four judges' inputs, unchanged (clean) and with "
            "one planted access per judgment (planted). Hits are pattern, scope and match only. The copies are not "
            "published, because the Claude transcripts carry the host's injected session context.",
    "patterns_sha256": sha_clean, "plants": PLANTS,
    "clean": clean, "clean_matches_published_audit": ok_clean,
    "planted": planted, "every_planted_judgment_void": ok_planted}, ensure_ascii=False, indent=1) + "\n")
print("clean matches the published audit:", ok_clean, "| every planted judgment void:", ok_planted,
      "| patterns", sha_clean[:12], sha_planted[:12])
for k in PLANTS:
    print(" ", k, "planted:", "VOID" if planted[k]["void"] else "clean", planted[k]["hits"][:3])
sys.exit(0 if ok_clean and ok_planted and sha_clean == sha_planted else 1)
