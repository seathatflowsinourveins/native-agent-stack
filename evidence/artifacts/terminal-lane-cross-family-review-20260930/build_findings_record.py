#!/usr/bin/env python3
"""Build the publishable record of the cross-family review of the terminal lane (2026-09-30) from the private run files: the consolidated review results (collect_reviews.py), the verifier
journals of the Claude workflow, and the disposition table below (one entry per finding, written by the coordinator after reading the verifier's evidence and, where no verifier was run, the
code or the upstream source itself). Writes three sanitized files into the artifact directory: results.json (the reviewer's findings and job records), verification.json (the verifiers'
verdicts) and findings.json (one row per finding: reviewer severity, how it was checked, disposition, where the repair is). The sanitizer replaces this host's paths and user name.
usage: build_findings_record.py <consolidated.json> <journal.jsonl> [<journal.jsonl> ...] --out <artifact directory>"""
import json, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import record_sanitizer  # noqa: E402  (the shared sanitizer rules; the private labels come from a private file)

args = sys.argv[1:]
out = Path(args[args.index("--out") + 1])
del args[args.index("--out"):args.index("--out") + 2]
consolidated, journals = Path(args[0]), [Path(a) for a in args[1:]]
HOME, USER = str(Path.home()), Path.home().name

# ---- disposition table: id -> (how checked, disposition, where the repair is)
V = "verifier"
DUP = "duplicate"
C = "coordinator"
DISPOSITIONS = {
    "F-sol-u484-A-1": (f"{C}: the same defect was confirmed on the derived push probe (u519-A2-8)", "repaired", "alert_probe.py: SIGTERM/SIGHUP handler; end-to-end SIGTERM case in --selftest of both probes"),
    "F-sol-u484-A-2": (f"{C}: read microsoft/terminal v1.24.11911.0 stateMachine.cpp L1855-1868 (C1 ignored when AcceptC1 is off)", "repaired", "BelCounter decodes UTF-8 and ignores C1 in both probes; six selftest cases"),
    "F-sol-u484-A-3": (f"{C}: read the host check (prefix plus last path segment only)", "repaired", "practice repository check-terminal-profiles.py (exact Media path, existence) and its controls; decision text"),
    "F-sol-u484-A-4": (f"{C}: read alert_probe.py (unconditional return 0)", "repaired", "alert_probe.py exit_status and five selftest cases"),
    "F-sol-u484-A-5": (f"{C}: 27 receipts carry the same host_scope.host", "kept", "the host id is the repository's host_scope convention; recorded as a residual"),
    "F-sol-u484-B-1": (f"{C}: read tmux 3.4 and 3.6 tty-features.c and measured tmux 3.4 (tmux_sync_probe.py)", "repaired", "decision record: the false sentence corrected, with the measurement"),
    "F-sol-u484-B-2": (f"{C}: read the regexes; a native rerun of the capture gives the receipt's counts", "repaired", "color_capture.py sgr_counts (SGR final byte, parameter boundaries) and eight selftest cases"),
    "F-sol-u484-B-3": (f"{DUP} of F-sol-u484-A-2", "repaired", "see F-sol-u484-A-2"),
    "F-sol-u484-B-4": (f"{DUP} of F-sol-u519-A2-10 (verifier: confirmed, low)", "repaired", "alert_probe.py prints message lengths; the screen tail only with --show-screen"),
    "F-sol-u484-B-5": (f"{C}: read the plan probe's prompt and the README", "repaired", "terminal-experience README names the plan-file exception"),
    "F-sol-u484-B-6": (f"{DUP} of F-sol-u484-A-5", "kept", "see F-sol-u484-A-5"),
    "F-sol-u484-B-7": (f"{C}: read Tab.cpp v1.24.11911.0 L1148-1154 and L456 (2000 ms timer on the focused tab)", "repaired", "recipe: the icon lifetime on a focused tab"),
    "F-sol-u498-A-1": (V, "repaired", "login_shell_check_controls.py (type -P, control I); recipe and platform page probes"),
    "F-sol-u498-A-2": (f"{DUP} of F-sol-u498-B-1", "repaired", "see F-sol-u498-B-1"),
    "F-sol-u498-A-3": (f"{DUP} of F-sol-u498-B-3", "repaired", "see F-sol-u498-B-3"),
    "F-sol-u498-A-4": (V, "repaired", "login_shell_check_controls.py (first startup file rule, control F); harness-defaults rule"),
    "F-sol-u498-A-5": (f"{DUP} of F-sol-u498-B-2", "repaired", "see F-sol-u498-B-2"),
    "F-sol-u498-A-6": (V, "repaired", "landscape_refresh.py definitions comparison (null when a part is missing); eleven selftest checks"),
    "F-sol-u498-A-7": (f"{DUP} of F-sol-u498-B-4", "repaired", "see F-sol-u498-B-4"),
    "F-sol-u498-B-1": (V, "repaired", "login_shell_check_controls.py (FOUND or MISSING per name plus DONE; controls G and H); practice repository doctor"),
    "F-sol-u498-B-2": (V, "repaired", "scrub_placeholder_probe.py (19 names, lstat mode/size/mtime/inode, selftest)"),
    "F-sol-u498-B-3": (V, "repaired", "login_path_digest.py (marker, exit 1 on a measurement error, selftest)"),
    "F-sol-u498-B-4": (V, "repaired", "receipt limitation no longer names the private profiles; the host id is kept (convention)"),
    "F-sol-u510-A-1": (V, "repaired", "platform page step 5 and recipe: defaults rank above a fragment's values"),
    "F-sol-u510-A-2": (V, "repaired", "codex_tui_strict_check.py (banner rule, exit status, selftest)"),
    "F-sol-u510-A-3": (f"{V}: refuted (Claude Code runs identical command hooks once)", "refuted", "no change to the verdict; the occurrence count is printed as information and a second group still fails"),
    "F-sol-u510-A-4": (V, "repaired", "tests/test_adoption_status.py and login_shell_bash_truth.py compare first_read"),
    "F-sol-u510-B-1": (f"{DUP} of F-sol-u510-A-1", "repaired", "see F-sol-u510-A-1"),
    "F-sol-u510-B-2": (f"{DUP} of F-sol-u510-A-2", "repaired", "see F-sol-u510-A-2"),
    "F-sol-u510-B-3": (V, "repaired", "overlay_noop_check.py (disableAllHooks, honest label); oracle tests"),
    "F-sol-u519-A1-1": (V, "repaired", "notification_types_scan.py resolves the catalog's spread identifier; eight reader tests; seven mutants"),
    "F-sol-u519-A1-2": (V, "repaired", "test: every quoted matcher outside HTML comments equals the overlay's"),
    "F-sol-u519-A1-3": (f"{V}: refuted (the terminal path is inactivity-timed; the reviewer read the Agent SDK path)", "refuted", "the reason keeps the terminal timing and names the SDK difference; the coordinator's own earlier wording about a fixed-delay timer was wrong and is corrected"),
    "F-sol-u519-A2-1": (f"{DUP} of F-sol-u519-B-1", "repaired", "see F-sol-u519-B-1"),
    "F-sol-u519-A2-2": (f"{C}: the code path is gone", "removed", "the second-distro target was removed with that distro (unregistered 2026-09-29); not verified separately"),
    "F-sol-u519-A2-3": (V, "repaired", "replace_bell_group.py refuses keys beyond matcher and hooks; control and mutant"),
    "F-sol-u519-A2-4": (f"{C}: the code path is gone", "removed", "as F-sol-u519-A2-2"),
    "F-sol-u519-A2-5": (V, "repaired", "controls: a 0640 file keeps its mode, an old matcher with the overlay's keys is replaced, a current matcher with an extra hook key is refused; mutants"),
    "F-sol-u519-A2-6": (f"{DUP} of F-sol-u519-B-3", "repaired", "see F-sol-u519-B-3"),
    "F-sol-u519-A2-7": (f"{C}: the code path is gone", "removed", "as F-sol-u519-A2-2"),
    "F-sol-u519-A2-8": (V, "repaired", "push_notification_probe.py and alert_probe.py: SIGTERM/SIGHUP handler; end-to-end SIGTERM case with a negative control"),
    "F-sol-u519-A2-9": (V, "repaired", "replace_bell_group.py refusal counts the types and names none"),
    "F-sol-u519-A2-10": (V, "repaired", "push_notification_probe.py prints message lengths; the screen tail only with --show-screen"),
    "F-sol-u519-B-1": (f"{V}: partly (medium, not high: the other writer's save survives in the backup)", "repaired", "replace_bell_group.py compares the live file with its read before the backup and the backup with its read; two controls through concurrent_writer_harness.py; two mutants"),
    "F-sol-u519-B-2": (V, "repaired", "decision record, recipe, platform page and the scan's reason: a local session only"),
    "F-sol-u519-B-3": (V, "repaired", "tmux_bell_probe.py verdict covers all five arms; --selftest"),
}

RULES = record_sanitizer.rules()
replaced = {}


def clean(value):
    if isinstance(value, str):
        for pattern, replacement in RULES:
            value, hits = pattern.subn(replacement, value)
            if hits:
                replaced[replacement] = replaced.get(replacement, 0) + hits
        return value
    if isinstance(value, list):
        return [clean(item) for item in value]
    if isinstance(value, dict):
        return {key: clean(item) for key, item in value.items()}
    return value


def trim(text, limit):
    return text if len(text) <= limit else text[:limit] + " [trimmed]"


data = json.loads(consolidated.read_text(encoding="utf-8"))
ids = {f["id"] for f in data["findings"]}
assert ids == set(DISPOSITIONS), (sorted(ids - set(DISPOSITIONS)), sorted(set(DISPOSITIONS) - ids))

verdicts = {}
for journal in journals:
    for line in journal.read_text(encoding="utf-8").splitlines():
        entry = json.loads(line)
        if entry.get("type") == "result":
            for v in entry["result"]["verdicts"]:
                verdicts[v["id"]] = {**v, "unit": entry["result"]["unit"]}
directly_verified = {i for i, (how, *_rest) in DISPOSITIONS.items() if how.startswith("verifier")}
assert directly_verified <= set(verdicts), sorted(directly_verified - set(verdicts))
extra = set(verdicts) - directly_verified
assert not extra or all(DISPOSITIONS[i][0].startswith("duplicate") is False for i in extra), extra

results = {"jobs": [{k: (v if k != "review" else {"verdict": (v or {}).get("verdict"), "summary": (v or {}).get("summary"), "claims_checked": (v or {}).get("claims_checked"),
                          "commands_run": (v or {}).get("commands_run"), "finding_count": len((v or {}).get("findings") or [])}) for k, v in r.items()} for r in data["records"]],
           "findings": [{k: (trim(v, 3000) if isinstance(v, str) else v) for k, v in f.items()} for f in data["findings"]]}
verification = {"verdicts": [{"id": i, "unit": v["unit"], "verdict": v["verdict"], "severity": v["severity"], "evidence": trim(v["evidence"], 2500), "fix_assessment": trim(v["fix_assessment"], 1200),
                              "smallest_repair": trim(v["smallest_repair"], 1200), "adjacent": trim(v["adjacent"], 1200)} for i, v in sorted(verdicts.items())]}
rows = []
for f in sorted(data["findings"], key=lambda f: f["id"]):
    how, disposition, where = DISPOSITIONS[f["id"]]
    row = {"id": f["id"], "reviewer_severity": f["severity"], "file": f["file"], "line": f["line"], "claim": trim(f["claim"], 240), "checked_by": how, "disposition": disposition, "repair": where}
    if f["id"] in verdicts:
        row["verifier_verdict"], row["verifier_severity"] = verdicts[f["id"]]["verdict"], verdicts[f["id"]]["severity"]
    rows.append(row)
findings = {"note": "The repair column describes the state after the first repair round; the re-check of the repairs (recheck-findings.json) and the fifth round changed some of these scripts and their counts.", "findings": rows}

for name, payload in (("results.json", results), ("verification.json", verification), ("findings.json", findings)):
    payload = clean(payload)
    (out / name).write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    text = (out / name).read_text(encoding="utf-8")
    record_sanitizer.assert_clean(text, name)
    print(f"wrote {name}: {len(text)} bytes")
by_disposition = {}
for row in rows:
    by_disposition[row["disposition"]] = by_disposition.get(row["disposition"], 0) + 1
kinds = {}
for row in rows:
    key = "verifier" if row["checked_by"].startswith("verifier") else "duplicate" if row["checked_by"].startswith("duplicate") else "coordinator"
    kinds[key] = kinds.get(key, 0) + 1
graded = {}
for i, v in verdicts.items():
    graded[v["verdict"]] = graded.get(v["verdict"], 0) + 1
print("findings:", len(rows), "| by disposition:", by_disposition, "| checked by:", kinds, "| verifier verdicts:", graded, "| replacements:", replaced)
