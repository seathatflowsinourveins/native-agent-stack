#!/usr/bin/env python3
"""Fix round 5: reconstruct when the fix-round-4 L5.3b(iii) control change was written (source review, no rerun).

Reads the fix-round-4 worker's Claude session transcript (host-local jsonl, outside the repository) and records, for
every tool call between the fix-round-4 preregistration and the verifier run, its logged timestamp, tool name and
which swap-control markers its input contains. Also records the verifier's file mtime and whether the verifier
committed at the preregistration commit contains any swap control.

Detection method: plain substring search for the markers below. The same search finds the markers in the entries that
do contain them (reported per entry), so an absent marker in an entry is a real absence in that logged input, not a
blind spot. A verifier run is detected by the substrings 'run_verify_fixround4.sh' or 'verify_lineage_fixround3.py --'
in a Bash command.
Usage: extract_fixround4_timeline.py TRANSCRIPT_JSONL OUT_JSON   (run from the worktree root)
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

SRC, OUT = Path(sys.argv[1]), Path(sys.argv[2])
HOME = os.path.expanduser("~")
BP = "blueprints/gap-wave2-20260923/us-equities__identity-provenance"
VERIFIER = f"{BP}/verify_lineage_fixround3.py"
WINDOW = ("2026-09-23T15:16:00", "2026-09-23T15:16:45")
MARKERS = {
    "first_two_swap_as_preregistered": 'swapped[1][\\"job\\"][\\"name\\"]',
    "rename_fallback_suffix": '\\"-swapped\\"',
    "across_job_swap": 'swapped[other][\\"job\\"][\\"name\\"]',
    "control_name_first_two": "first_two_job_names_swapped",
    "control_name_across_jobs": "job_names_swapped_across_jobs",
    "late_amendment_comment": "fix-round-4 late amendment",
    "writes_preregistration_fixround4": "preregistration-fixround4.json",
}

raw = SRC.read_bytes()
entries = []
for line in raw.decode().splitlines():
    try:
        d = json.loads(line)
    except json.JSONDecodeError:
        continue
    t = d.get("timestamp", "")
    if not (WINDOW[0] < t < WINDOW[1]):
        continue
    content = d.get("message", {}).get("content")
    for part in content if isinstance(content, list) else []:
        if part.get("type") != "tool_use":
            continue
        s = json.dumps(part.get("input"))
        entries.append({
            "logged_at": t, "tool": part.get("name"),
            "touches_verifier": "verify_lineage_fixround3.py" in s,
            "markers": sorted(k for k, m in MARKERS.items() if m in s),
            "runs_verifier": part.get("name") == "Bash" and ("bash $B/run_verify_fixround4.sh" in s or "verify_lineage_fixround3.py --" in s),
            "description": (part.get("input") or {}).get("description"),
        })


def git(*a):
    return subprocess.run(["git", *a], capture_output=True, text=True, check=True).stdout


at_prereg = git("show", f"aa85595:{VERIFIER}")
out = {
    "purpose": "fix round 5 (late, no preregistration): timestamp the L5.3b(iii) control change; source review of retained host records",
    "transcript": {"path": "$HOME/.claude/projects/<project-dir>/<lead-session>/subagents/workflows/" + "/".join(SRC.parts[-2:]),
                   "sha256": hashlib.sha256(raw).hexdigest(), "window": WINDOW,
                   "timestamp_meaning": "the transcript's logged time of the assistant message carrying each tool call (the call ran just after it)"},
    "tool_calls_in_window": entries,
    "verifier_runs_in_window": [e["logged_at"] for e in entries if e["runs_verifier"]],
    "verifier_file_mtime_utc": subprocess.run(["date", "-u", "-r", VERIFIER, "+%Y-%m-%dT%H:%M:%S.%NZ"], capture_output=True, text=True).stdout.strip(),
    "verifier_at_prereg_commit_aa85595": {"sha256": hashlib.sha256(at_prereg.encode()).hexdigest(),
                                          "contains_swap_control": any(m.replace('\\"', '"') in at_prereg for m in MARKERS.values() if "swap" in m),
                                          "contains_alignment_problems": "alignment_problems" in at_prereg},
    "commit_times": {c: git("show", "-s", "--format=%cI", c).strip() for c in ("aa85595", "87ab1db")},
}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(out, indent=2) + "\n")
print(json.dumps(out, indent=2))
