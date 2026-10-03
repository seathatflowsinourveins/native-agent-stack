#!/usr/bin/env python3
"""Build the publishable record of the final review pass of the terminal lane (2026-09-30) from the private run files: the consolidated results of the six jobs (collect_reviews.py: three lenses, each on
`cx/gpt-6.1-sol` and on `cx/gpt-6-astra-ultra`), the verifier journals of the Claude workflow, and the disposition table `final_dispositions.json` beside this script (one entry per finding: how it was checked, its
disposition and where the repair is, written by the coordinator after reading the verifier's evidence, or, where no verifier ran, the code or the primary source itself). Writes three sanitized files into the artifact
directory: final-results.json, final-verification.json and final-findings.json. The sanitizer rules come from record_sanitizer.py, shared with the other record builders, so the records cannot disagree.
usage: build_final_record.py <consolidated.json> [<consolidated.json> ...] --journals <journal.jsonl> [<journal.jsonl> ...] --out <artifact directory>"""
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
HERE = Path(__file__).resolve().parent

# One reviewed false positive of the repository's secret gate (gitleaks generic-api-key): a reviewer's sentence "... all eight extraction keys present, <a config key=value example>." reads as a key. Only that sentence's
# punctuation changes (the example goes into parentheses); the pattern is exact and anchored and must apply exactly once, so any other secret-shaped text still reaches the gate.
GATE_PROSE = [(re.compile(r"(all eight extraction keys present), ([A-Za-z0-9_=.-]+?)\.(?= Real-source)"), r"\1 (\2).")]
RULES = record_sanitizer.rules() + GATE_PROSE
DISPOSITIONS = {key: tuple(value) for key, value in json.loads((HERE / "final_dispositions.json").read_text(encoding="utf-8")).items()}


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

applied = sum(len(pattern.findall(json.dumps(results, ensure_ascii=False))) for pattern, _replacement in GATE_PROSE)
assert applied == 1, f"the reviewed secret-gate prose pattern applied {applied} times, expected once"
for name, payload in (("final-results.json", results), ("final-verification.json", verification), ("final-findings.json", {"findings": rows})):
    payload = clean(payload)
    (out / name).write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    text = (out / name).read_text(encoding="utf-8")
    record_sanitizer.assert_clean(text, name)
    print(f"wrote {name}: {len(text)} bytes")
by_disposition, kinds, graded, severities, by_model = {}, {}, {}, {}, {}
for row in rows:
    by_disposition[row["disposition"]] = by_disposition.get(row["disposition"], 0) + 1
    key = "verifier" if row["checked_by"].startswith("verifier") else "duplicate" if row["checked_by"].startswith("duplicate") else "coordinator"
    kinds[key] = kinds.get(key, 0) + 1
for v in verdicts.values():
    graded[v["verdict"]] = graded.get(v["verdict"], 0) + 1
for f in findings_in:
    severities[f["severity"]] = severities.get(f["severity"], 0) + 1
    lane = f["id"].split("-")[1]   # ids are F-<lane>-<job>-<n>
    by_model[lane] = by_model.get(lane, 0) + 1
print("findings:", len(rows), "| by lane:", by_model, "| reviewer severity:", severities, "| by disposition:", by_disposition, "| checked by:", kinds, "| verifier verdicts:", graded)
