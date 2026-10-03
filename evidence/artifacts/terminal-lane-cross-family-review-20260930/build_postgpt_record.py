#!/usr/bin/env python3
"""Build the publishable record of the post-merge GPT read of the terminal lane (2026-10-01) from the private run files: the consolidated results of the six jobs (collect_reviews.py: three lenses P1 to P3, each on
`cx/gpt-6.1-sol` and on `cx/gpt-6-astra-ultra`), the disposition table `postgpt_dispositions.json` beside this script (one entry per finding: how it was checked, its disposition, where the repair is, and the coordinator's
severity and harness check) and the recorded output of the verification harness (recorded/post_gpt_verification.txt, produced on the code as merged before any repair). No Claude verifier agent was used for this read (the shared
five-hour meter read 89% when the findings arrived), so the verification record holds the coordinator's own reproductions. Writes three sanitized files into the artifact directory: postgpt-results.json, postgpt-verification.json
and postgpt-findings.json. The sanitizer rules come from record_sanitizer.py, shared with the other record builders.
usage: build_postgpt_record.py <consolidated.json> --out <artifact directory>"""
import json, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import record_sanitizer  # noqa: E402  (the shared sanitizer rules; the private labels come from a private file)

args = sys.argv[1:]
consolidated = Path(args[0])
out = Path(args[args.index("--out") + 1])
HERE = Path(__file__).resolve().parent
RULES = record_sanitizer.rules()
DISPOSITIONS = json.loads((HERE / "postgpt_dispositions.json").read_text(encoding="utf-8"))
recorded = (HERE / "recorded/post_gpt_verification.txt").read_text(encoding="utf-8").splitlines()


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


def harness_line(check):
    """Every line of the recorded harness output that starts with the check's name (the check prints its own name first), joined."""
    found = [line for line in recorded if line.startswith(check + ":") or line.startswith(check + " (")]
    return " / ".join(found) if found else None


data = json.loads(consolidated.read_text(encoding="utf-8"))
records, findings_in = data["records"], data["findings"]
ids = [f["id"] for f in findings_in]
assert len(ids) == len(frozenset(ids)) == 38 and frozenset(ids) == frozenset(DISPOSITIONS), (len(ids), sorted(frozenset(ids) ^ frozenset(DISPOSITIONS)))

results = {"jobs": [{k: (v if k != "review" else {"verdict": (v or {}).get("verdict"), "summary": (v or {}).get("summary"), "claims_checked": (v or {}).get("claims_checked"),
                          "commands_run": (v or {}).get("commands_run"), "finding_count": len((v or {}).get("findings") or [])}) for k, v in r.items()} for r in records],
           "findings": [{k: (trim(v, 3000) if isinstance(v, str) else v) for k, v in f.items()} for f in findings_in]}
verification, rows = [], []
for finding_id in sorted(DISPOSITIONS):
    how, disposition, repair, meta = DISPOSITIONS[finding_id]
    finding = next(f for f in findings_in if f["id"] == finding_id)
    row = {"id": finding_id, "reviewer_severity": finding["severity"], "file": finding["file"], "line": finding["line"], "claim": trim(finding["claim"], 240), "checked_by": how, "disposition": disposition, "repair": repair,
           "coordinator_severity": meta["severity"]}
    rows.append(row)
    if not how.startswith("duplicate"):
        evidence = harness_line(meta["check"]) if meta["check"] != "reading" else None
        if meta["check"] != "reading":
            assert evidence, f"{finding_id}: the recorded harness output has no line for the check {meta['check']!r}"
        verification.append({"id": finding_id, "unit": meta["unit"], "check": meta["check"], "verdict": "confirmed", "severity": meta["severity"],
                             "evidence": trim(evidence, 700) if evidence else how, "repair": repair})
for name, payload in (("postgpt-results.json", results), ("postgpt-verification.json", {"verdicts": verification}), ("postgpt-findings.json", {"findings": rows})):
    payload = clean(payload)
    (out / name).write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    text = (out / name).read_text(encoding="utf-8")
    record_sanitizer.assert_clean(text, name)
    print(f"wrote {name}: {len(text)} bytes")
by_disposition, kinds, severities, by_model, mine = {}, {}, {}, {}, {}
for row in rows:
    by_disposition[row["disposition"]] = by_disposition.get(row["disposition"], 0) + 1
    key = "coordinator" if row["checked_by"].startswith("coordinator") else "duplicate"
    kinds[key] = kinds.get(key, 0) + 1
    mine[row["coordinator_severity"]] = mine.get(row["coordinator_severity"], 0) + 1
for f in findings_in:
    severities[f["severity"]] = severities.get(f["severity"], 0) + 1
    by_model[f["id"].split("-")[1]] = by_model.get(f["id"].split("-")[1], 0) + 1
print("findings:", len(rows), "| by lane:", by_model, "| reviewer severity:", severities, "| coordinator severity (all rows, duplicates inherit):", mine, "| by disposition:", by_disposition, "| checked by:", kinds)
