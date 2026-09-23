#!/usr/bin/env python3
"""Source-review check for us-equities/observability-hosting gap 0.

Confirms the executed comparison cited as covering the gap (#87,
evidence/artifacts/sota-refresh-20260923/obs-compare/) is on origin/main
unchanged from its merge commit, reports each contested candidate's executed
verdict, and probes which next_check clauses the receipt covers. The clause
probe is a case-insensitive term search over the receipt JSON and README; a
positive control ('restic', known present) shows the probe can detect a term.
Read-only: uses `git show` only; runs no services.
"""
import hashlib
import json
import subprocess
import sys

MERGE = "43bb931"
REF = sys.argv[1] if len(sys.argv) > 1 else "origin/main"
BASE = "evidence/artifacts/sota-refresh-20260923/obs-compare/"
FILES = [
    "observability-hosting-comparison.json",
    "README.md",
    "fixround-preregistration.md",
    "logs-fixround/egress-default-retry.log",
    "logs-fixround/egress-allowlisted.log",
    "logs-fixround/egress-allowlisted-otherhost-denied.log",
]
CLAUSES = {
    "positive_control_restic": ["restic"],
    "both_candidate_sets": ["in_claude_set", "in_codex_set"],
    "log_metric_retention": ["kill -9", "retention"],
    "log_metric_query": ["query_range", "query-back", "/loki/api/v1/query"],
    "snapshot_restore_fidelity": ["restore --verify", "diff -rq", "check --read-data"],
    "sandbox_isolation": ["unshare-net", "no matching config rule"],
    "dagu_workload": ["dagu"],
    "paper_runtime_telemetry": ["paper-runtime", "paper runtime", "paper_runtime", "paper account"],
}


def show(ref, path):
    return subprocess.run(["git", "show", f"{ref}:{path}"], capture_output=True, check=True).stdout


out = {"ref": REF, "merge_commit": MERGE}
out["merge_is_ancestor_of_ref"] = subprocess.run(
    ["git", "merge-base", "--is-ancestor", MERGE, REF]).returncode == 0
files = {}
for f in FILES:
    a, b = show(REF, BASE + f), show(MERGE, BASE + f)
    files[f] = {"sha256_ref": hashlib.sha256(a).hexdigest(), "identical_to_merge": a == b, "bytes": len(a)}
out["files"] = files
receipt = json.loads(show(REF, BASE + FILES[0]))
out["receipt_evidence_class"] = receipt["evidence_class"]
out["receipt_verdict"] = receipt["verdict"]
out["receipt_checked_at"] = receipt["checked_at"]
out["candidates"] = [
    {k: c[k] for k in ("key", "name", "in_claude_set", "in_codex_set", "verdict", "evidence_class", "works_under_requirement")}
    for c in receipt["per_component_verdicts"]
]
text = (json.dumps(receipt) + show(REF, BASE + "README.md").decode()).lower()
out["clause_probe"] = {k: {t: text.count(t.lower()) for t in terms} for k, terms in CLAUSES.items()}
out["clause_covered"] = {k: any(v.values()) for k, v in out["clause_probe"].items()}
row = next(r for r in json.loads(show(REF, "catalogs/landscape/us-equities.json"))["layers"]
           if r.get("layer_id") == "observability-hosting")
out["ledger_row_on_ref"] = {"verdict_status": row.get("verdict_status"), "winners": row.get("winners"),
                            "open_gaps_count": len(row.get("open_gaps", []))}
print(json.dumps(out, indent=1))
