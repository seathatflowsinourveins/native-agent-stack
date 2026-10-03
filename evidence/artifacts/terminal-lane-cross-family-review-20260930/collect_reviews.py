#!/usr/bin/env python3
"""Collect the review jobs of one or more staged lane work dirs through the packaged runner's own `result` command and print a compact table.
Writes <out>.json (private: per job the runner's record without stderr, plus the parsed review and flattened findings with ids F-<lane>-<job>-<n>).
usage: collect_reviews.py <checkout> <out-prefix> <lane>=<work-dir> [<lane>=<work-dir> ...] -- <job> [<job> ...]"""
import json, subprocess, sys
from pathlib import Path

argv = sys.argv[1:]
CALL = Path(argv.pop(0)) / "tools/sota-convergence/landscape-sweep/codex_call.sh"   # the checkout that holds the packaged runner
out_prefix = Path(argv[0])
split = argv.index("--")
lanes = dict(item.split("=", 1) for item in argv[1:split])
jobs = argv[split + 1:]
records, findings = [], []
for lane, work in lanes.items():
    for job in jobs:
        if not (Path(work) / "gpt6" / job).is_dir():
            continue
        raw = subprocess.run(["bash", str(CALL), "--work-dir", work, "result", job], capture_output=True, text=True, timeout=60, cwd="/tmp")
        record = json.loads(raw.stdout.strip().splitlines()[-1])
        text = record.get("output_text")
        review = None
        if text:
            try:
                review = json.loads(text)
            except ValueError:
                review = None
        slim = {k: record.get(k) for k in ("status", "exit", "started", "finished", "usage", "usage_status", "limit", "model", "effort", "codex_version", "attempts")}
        slim.update(lane=lane, job=job, stderr_tail=(record.get("stderr_tail") or "")[-200:], review=review)
        records.append(slim)
        for number, finding in enumerate((review or {}).get("findings") or [], 1):
            findings.append({"id": f"F-{lane}-{job}-{number}", "lane": lane, "job": job, **finding})
out_prefix.with_suffix(".json").write_text(json.dumps({"records": records, "findings": findings}, indent=1) + "\n", encoding="utf-8")
print("lane  job        status      exit verdict          F(h/m/l) claims(c/x/u) tokens(in/cached/out)")
for record in records:
    review = record["review"] or {}
    counts = {s: sum(1 for f in review.get("findings") or [] if f["severity"] == s) for s in ("high", "medium", "low")}
    claims = {r: sum(1 for c in review.get("claims_checked") or [] if c["result"] == r) for r in ("confirmed", "contradicted", "unverifiable")}
    usage = record.get("usage") or {}
    print(f"{record['lane']:5} {record['job']:10} {record['status']:11} {str(record['exit']):4} {review.get('verdict', '-'):16} "
          f"{counts['high']}/{counts['medium']}/{counts['low']}      {claims['confirmed']}/{claims['contradicted']}/{claims['unverifiable']}          "
          f"{usage.get('input_tokens', '-')}/{usage.get('cached_input_tokens', '-')}/{usage.get('output_tokens', '-')}")
order = {"high": 0, "medium": 1, "low": 2}
print()
for finding in sorted(findings, key=lambda f: (order[f["severity"]], f["id"])):
    print(f"{finding['id']:18} {finding['severity']:6} {'T' if finding['tested'] else '-'} {finding['file']}:{finding['line']} :: {finding['claim'][:170]}")
