"""Run the lane-A template's own checks, which the anti-pattern log names, against this round's audit and patterns.
A reproduction of the round's mistake: both checks must fail on it.

The template is evidence/artifacts/prompt-audit-20260927/lane-a/final/adjudication/:
1. Its self-test (audit_selftest_final.py) requires two Claude payloads to come back clean (`set()`):
   - repository prose about the two lanes read as a tool result (line 131);
   - the judge's own agent definition as a prompt_snapshot attachment (lines 136-138).
   The payloads are copied verbatim and checked against that file. Both are run through this round's audit_m45.py
   as the two Claude judgments of a synthetic adjudication whose GPT-6 jobs are clean.
2. Its root scan (root_scan_final.py) exits 1 on any exported root file whose name or text matches MAPPING.
   Here, this round's MAPPING runs over every tracked path and file text at the export's commit.

usage: reproduce_template_checks_m45.py REPO COMMIT WORK OUT
REPO is a clone that holds COMMIT (9f8db582, the export the judges read). WORK is an empty scratch directory for the
copies and the synthetic inputs. OUT is the JSON written. Exits 1 unless both payloads come back void and the root
scan counts at least one hit, that is, unless both template checks fail on this round's patterns.
"""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

X = Path(__file__).resolve().parent
REPO, COMMIT, WORK, OUT = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3]), Path(sys.argv[4])
TEMPLATE = "evidence/artifacts/prompt-audit-20260927/lane-a/final/adjudication/audit_selftest_final.py"
PROSE = "docs: the GPT-6 lane and the Claude lane agreed on F1 (round 1)."
DEFINITION = ("a phrase that attributes a return to a reviewer family, such as \"the Codex lane\" or "
              "\"Claude's proposal\"")

template = subprocess.run(["git", "-C", str(REPO), "show", f"{COMMIT}:{TEMPLATE}"], check=True,
                          capture_output=True, text=True).stdout
assert f'result("{PROSE}"), set()' in template, "the tool-result payload is not the template's"
assert json.dumps(DEFINITION)[1:-1] in template, "the prompt_snapshot payload is not the template's"

# The frozen audit and patterns, copied, so the audit writes its output into WORK.
if WORK.exists() and any(WORK.iterdir()):
    sys.exit(f"{WORK} is not empty")
code = WORK / "audit"
code.mkdir(parents=True)
for name in ("audit_m45.py", "void_patterns_m45.py"):
    shutil.copy(X / name, code / name)
jobs = WORK / "runs" / "gpt6"
for order in ("AB", "BA"):
    job = jobs / f"m5-judge-{order}"
    job.mkdir(parents=True)
    (job / "prompt.txt").write_text("Task: adjudicate unit M5.\n")
    (job / "events.jsonl").write_text(json.dumps({"type": "item.completed", "item": {
        "type": "agent_message", "text": "{}"}}) + "\n")
start = {"type": "user", "message": {"role": "user", "content": "Adjudicate unit M5."}}
cases = {
    "AB": ("prompt_snapshot: the judge's own agent definition (template lines 136-138)",
           {"type": "attachment", "attachment": {"type": "prompt_snapshot", "systemPrompt": [DEFINITION]}}),
    "BA": ("tool_result: repository prose about the lanes (template line 131)",
           {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t1", "content": PROSE}]}}),
}
for order, (_, event) in cases.items():
    (WORK / f"claude-{order}.jsonl").write_text("\n".join(json.dumps(e) for e in (start, event)) + "\n")
subprocess.run([sys.executable, "-B", str(code / "audit_m45.py"), str(WORK / "runs"), str(WORK / "claude-AB.jsonl"),
                str(WORK / "claude-BA.jsonl"), "template-cases.json"], check=True, capture_output=True)
audit = json.loads((code / "template-cases.json").read_text())["judgments"]
payloads = {}
for order, (label, _) in cases.items():
    j = audit[f"claude-{order}"]
    payloads[label] = {"template_expects": "clean", "void": j["void"],
                       "hits": [[h["pattern"], h["scope"], h["match"]] for h in j["hits"]]}
gpt6_clean = not audit["gpt6-AB"]["void"] and not audit["gpt6-BA"]["void"]

# The root scan: this round's MAPPING over the export's tracked paths and file text.
sys.path.insert(0, str(code))
import void_patterns_m45 as v  # noqa: E402

entries = []  # (blob id, path) for every tracked file; -z keeps unusual file names unquoted
for record in subprocess.run(["git", "-C", str(REPO), "ls-tree", "-r", "-z", COMMIT], check=True,
                             capture_output=True).stdout.split(b"\0"):
    if record:
        meta, path = record.split(b"\t", 1)
        entries.append((meta.split()[2].decode(), path.decode("utf-8", errors="replace")))
paths = [p for _, p in entries]
batch = subprocess.run(["git", "-C", str(REPO), "cat-file", "--batch"], input="".join(
    f"{oid}\n" for oid, _ in entries).encode(), check=True, capture_output=True).stdout
path_hits, text_hits, pos = [], [], 0
for oid, p in entries:
    header_end = batch.index(b"\n", pos)
    header = batch[pos:header_end].split()
    assert header[0].decode() == oid and header[1] == b"blob", header
    size = int(header[2])
    blob = batch[header_end + 1:header_end + 1 + size]
    pos = header_end + 1 + size + 1
    if v.MAPPING.search(p):
        path_hits.append(p)
    if v.MAPPING.search(blob.decode("utf-8", errors="replace")):
        text_hits.append(p)

result = {
    "note": "Reproduction, after the fact, of this round's mistake against the lane-A template's checks, which the "
            "anti-pattern log names. Both checks fail on this round's audit and patterns.",
    "template": {"file": TEMPLATE, "commit": COMMIT, "sha256": hashlib.sha256(template.encode()).hexdigest()},
    "patterns_sha256": hashlib.sha256((X / "void_patterns_m45.py").read_bytes()).hexdigest(),
    "self_test_payloads": payloads,
    "synthetic_gpt6_jobs_clean": gpt6_clean,
    "root_scan": {"commit": COMMIT, "tracked_files": len(paths), "paths_matching_mapping": path_hits,
                  "files_whose_text_matches_mapping": len(text_hits)},
}
OUT.write_text(json.dumps(result, indent=1) + "\n")
failed = all(p["void"] for p in payloads.values()) and gpt6_clean and (path_hits or text_hits)
print(json.dumps({"payloads_void": [p["void"] for p in payloads.values()], "gpt6_clean": gpt6_clean,
                  "path_hits": len(path_hits), "text_hits": len(text_hits), "reproduced": bool(failed)}))
sys.exit(0 if failed else 1)
