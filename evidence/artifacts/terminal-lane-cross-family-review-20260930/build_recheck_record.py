#!/usr/bin/env python3
"""Build the publishable record of the bounded re-check of the repair pull request (2026-09-30) from the private run files: the consolidated re-check results (collect_reviews.py: three jobs of the
first review model, one of a second model), the verifier journals of the Claude workflows, and the disposition table below (one entry per finding, written by the coordinator after reading the verifier's
evidence, or, where no verifier ran, the code or the primary source itself). Writes three sanitized files into the artifact directory: recheck-results.json, recheck-verification.json and
recheck-findings.json. The sanitizer rules are read from build_findings_record.py, so the two records cannot disagree.
usage: build_recheck_record.py <consolidated.json> [<consolidated.json> ...] --journals <journal.jsonl> [<journal.jsonl> ...] --out <artifact directory>"""
import json, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import record_sanitizer  # noqa: E402  (the shared sanitizer rules; the private labels come from a private file)

args = sys.argv[1:]
out = Path(args[args.index("--out") + 1])
journals_at = args.index("--journals")
consolidated = [Path(a) for a in args[:journals_at]]
journals = [Path(a) for a in args[journals_at + 1:args.index("--out")]]
HOME, USER = str(Path.home()), Path.home().name

RULES = record_sanitizer.rules()

V, DUP, C = "verifier", "duplicate", "coordinator"
DISPOSITIONS = {
    # the second model's job U1 (adversarial second opinion)
    "F-ultra-U1-1": (V, "repaired", "replace_bell_group.py compares the live file again right before the rename and states the residual (a save after that comparison is in neither file); harness modes after-backup, during-backup and at-replace; controls and a mutant; docstring, README and decision wording"),
    "F-ultra-U1-2": (V, "repaired", "login_path_digest.py and scrub_placeholder_probe.py read the PATH from a nonce-framed byte record; selftest cases with a logged PATH= line, a plain line, a non-UTF-8 byte, a newline in a component"),
    "F-ultra-U1-3": (V, "repaired", "alert_probe.py and push_notification_probe.py: SIGINT, SIGTERM and SIGHUP, the first signal wins, the cleanup runs with the signals deferred; two-signal, two-SIGINT and during-cleanup cases; pty_probe_mutants.py"),
    "F-ultra-U1-4": (V, "repaired", "signal_case: the stand-in publishes its PID, the probe must be running and exit with the signal's status, the recorded stand-in must be gone; a never-started stand-in must fail the case"),
    "F-ultra-U1-5": (V, "repaired", "notification_types_scan.py lookbehind excludes member access; a test, a mutant and the stated scope limit"),
    "F-ultra-U1-6": (V, "repaired", "landscape_refresh.py compares Notifications' Default impl, the terminal_title field and multi-line attributes; selftest checks and an attribute-dropping mutant"),
    "F-ultra-U1-7": (V, "repaired", "color_capture.py reads colon groups as the pinned parser does and consumes incomplete groups; unclassified_groups; corrected fixtures"),
    "F-ultra-U1-8": (V, "repaired", "scrub_placeholder_probe.py selftest: a fresh home per operation, the exact set of changed names, a state that skips the name must miss the change"),
    "F-ultra-U1-9": (V, "repaired", "both sanitizers replace the private profile labels; the recorded practice commit subjects are sanitized; the rebuilt review JSON holds none"),
    "F-ultra-U1-10": (V, "repaired", "the artifact README says four pool points, with the cached before and after figures"),
    # the first model's re-check jobs R1 (tool and probes), R2 (scan, tests, scripts), R3 (claims and evidence)
    "F-sol-R1-1": (V, "repaired", "replace_bell_group.py: the final comparison catches an atomic save made while the backup is copied; harness mode during-backup and its case"),
    "F-sol-R1-2": (V, "repaired", "both probes enter the cleanup guard before the client exists and create it with a spawn flag (the handler waits until the client is recorded; a signal mask would be inherited by the client, which the verifier showed); client_boundary_case and a stand-in signal-mask check; pty_probe_mutants.py"),
    "F-sol-R1-3": (V, "repaired", "with_private_dir cleans up with the signals deferred and restores the handlers afterwards; cleanup_phase_case; pty_probe_mutants.py"),
    "F-sol-R1-4": (f"{DUP} of F-ultra-U1-4 (verifier: confirmed)", "repaired", "see F-ultra-U1-4; the process scan is replaced by the recorded PID with an exact argv match"),
    "F-sol-R1-5": (V, "repaired", "push_notification_probe.py exit_status: 1 when the hooks-disabled control saw a BEL; five selftest cases"),
    "F-sol-R1-6": (f"{C}: reproduced under umask 077 (the mode control failed for the backup)", "repaired", "replace_bell_group_controls.py runs the tool with a fixed umask"),
    "F-sol-R1-7": (f"{DUP} of F-ultra-U1-10", "repaired", "see F-ultra-U1-10"),
    "F-sol-R2-1": (f"{DUP} of F-ultra-U1-5", "repaired", "see F-ultra-U1-5"),
    "F-sol-R2-2": (f"{DUP} of F-ultra-U1-2", "repaired", "see F-ultra-U1-2"),
    "F-sol-R2-3": (f"{DUP} of F-ultra-U1-7", "repaired", "see F-ultra-U1-7"),
    "F-sol-R2-4": (V, "repaired", "landscape_refresh.py: multi-line attributes are captured whole and formatting is normalized; checks for a changed one-line and multi-line attribute and a wrapped derive (an attribute-dropping mutant fails three of them); the verifier's run and the coordinator's on the real rust-v0.157.1 and rust-v0.159.2 files found the parts identical (ad hoc, not recorded)"),
    "F-sol-R2-5": (f"{DUP} of F-ultra-U1-8", "repaired", "see F-ultra-U1-8"),
    "F-sol-R2-6": (V, "repaired", "tests: a matcher quote is a backtick list directly after the word matcher or any pipe list of known types; single-type and no-permission_prompt controls"),
    "F-sol-R2-7": (f"{DUP} of F-ultra-U1-10", "repaired", "see F-ultra-U1-10"),
    "F-sol-R3-1": (V, "repaired", "the login-shell check requires an executable regular file (-f and -x); controls J (stale hash) and K (mode 0644); the practice repository's doctor; docs wording"),
    "F-sol-R3-2": (f"{DUP} of F-ultra-U1-2", "repaired", "see F-ultra-U1-2"),
    "F-sol-R3-3": (f"{DUP} of F-ultra-U1-8", "repaired", "see F-ultra-U1-8"),
    "F-sol-R3-4": (f"{DUP} of F-sol-R2-4", "repaired", "see F-sol-R2-4"),
    "F-sol-R3-5": (V, "repaired", "a native rerun of the revised scrub probe and a real-host digest run are recorded; the decision record and the login-shell receipt say only what those runs show"),
    "F-sol-R3-6": (f"{DUP} of F-ultra-U1-9", "repaired", "see F-ultra-U1-9"),
    "F-sol-R3-7": (V, "repaired", "both tmux probes keep their socket inside their own private directory (-S)"),
    "F-sol-R3-8": (f"{DUP} of F-ultra-U1-10", "repaired", "see F-ultra-U1-10"),
    "F-sol-R3-9": (f"{C}: read the receipt prose (the unmutated baseline was counted as a mutant run)", "repaired", "the receipt and the decision record count runs as the baseline plus the mutants"),
}


def clean(value):
    if isinstance(value, str):
        for pattern, replacement in RULES:
            value = pattern.sub(replacement, value)
        return value
    if isinstance(value, list):
        return [clean(item) for item in value]
    if isinstance(value, dict):
        return {key: clean(item) for key, item in value.items()}
    return value


def trim(text, limit):
    return text if len(text) <= limit else text[:limit] + " [trimmed]"


records, findings_in = [], []
for path in consolidated:
    data = json.loads(path.read_text(encoding="utf-8"))
    records += data["records"]
    findings_in += data["findings"]
ids = {f["id"] for f in findings_in}
assert ids == set(DISPOSITIONS), (sorted(ids - set(DISPOSITIONS)), sorted(set(DISPOSITIONS) - ids))

verdicts = {}
for journal in journals:
    for line in journal.read_text(encoding="utf-8").splitlines():
        entry = json.loads(line)
        if entry.get("type") == "result":
            result = entry["result"] if isinstance(entry["result"], dict) else json.loads(entry["result"])
            for v in result["verdicts"]:
                verdicts[v["id"]] = {**v, "unit": result["unit"]}
directly_verified = {i for i, (how, *_rest) in DISPOSITIONS.items() if how.startswith("verifier")}
assert directly_verified <= set(verdicts), sorted(directly_verified - set(verdicts))
extra = set(verdicts) - directly_verified
assert not extra, f"a verifier graded findings the table calls something else: {sorted(extra)}"

results = {"jobs": [{k: (v if k != "review" else {"verdict": (v or {}).get("verdict"), "summary": (v or {}).get("summary"), "claims_checked": (v or {}).get("claims_checked"),
                          "commands_run": (v or {}).get("commands_run"), "finding_count": len((v or {}).get("findings") or [])}) for k, v in r.items()} for r in records],
           "findings": [{k: (trim(v, 3000) if isinstance(v, str) else v) for k, v in f.items()} for f in findings_in]}
verification = {"verdicts": [{"id": i, "unit": v["unit"], "verdict": v["verdict"], "severity": v["severity"], "evidence": trim(v["evidence"], 2500), "fix_assessment": trim(v["fix_assessment"], 1200),
                              "smallest_repair": trim(v["smallest_repair"], 1200), "adjacent": trim(v["adjacent"], 1200)} for i, v in sorted(verdicts.items())]}
rows = []
for f in sorted(findings_in, key=lambda f: f["id"]):
    how, disposition, where = DISPOSITIONS[f["id"]]
    row = {"id": f["id"], "reviewer_severity": f["severity"], "file": f["file"], "line": f["line"], "claim": trim(f["claim"], 240), "checked_by": how, "disposition": disposition, "repair": where}
    if f["id"] in verdicts:
        row["verifier_verdict"], row["verifier_severity"] = verdicts[f["id"]]["verdict"], verdicts[f["id"]]["severity"]
    rows.append(row)

for name, payload in (("recheck-results.json", results), ("recheck-verification.json", verification), ("recheck-findings.json", {"findings": rows})):
    payload = clean(payload)
    (out / name).write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    text = (out / name).read_text(encoding="utf-8")
    record_sanitizer.assert_clean(text, name)
    print(f"wrote {name}: {len(text)} bytes")
by_disposition, kinds, graded = {}, {}, {}
for row in rows:
    by_disposition[row["disposition"]] = by_disposition.get(row["disposition"], 0) + 1
    key = "verifier" if row["checked_by"].startswith("verifier") else "duplicate" if row["checked_by"].startswith("duplicate") else "coordinator"
    kinds[key] = kinds.get(key, 0) + 1
for v in verdicts.values():
    graded[v["verdict"]] = graded.get(v["verdict"], 0) + 1
severities = {}
for f in findings_in:
    severities[f["severity"]] = severities.get(f["severity"], 0) + 1
print("findings:", len(rows), "| reviewer severity:", severities, "| by disposition:", by_disposition, "| checked by:", kinds, "| verifier verdicts:", graded)
