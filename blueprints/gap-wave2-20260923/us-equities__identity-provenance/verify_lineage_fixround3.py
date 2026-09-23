#!/usr/bin/env python3
"""Gap-wave-2 identity-provenance gap 5, fix round 3 (preregistration-fixround3.json L5.1, L5.2).

L5.1: from the original, unredacted OpenLineage event file, check that START and COMPLETE of each job share one runId
and that the two jobs' runIds differ; a detector copy with the select COMPLETE runId replaced must fail.
L5.2 (as amended at 13:27:46Z): the repository's publication validator rejects every UUID-shaped string, so the
published file keeps 'uuid-redacted-NN' placeholders. Validate the published bytes against the OpenLineage 2-0-2
RunEvent schema with FormatChecker after mapping only exact 'uuid-redacted-NN' runId values to valid-format UUIDs
(in memory); the unmapped published file is the detector control and must fail on format.
Usage: verify_lineage_fixround3.py --original ORIG.ndjson --expected-source-sha256 HEX --published PUB.ndjson --spec SPEC.json
Prints one JSON object. Full runIds are not printed; each is reported by its published placeholder.
"""
import argparse
import copy
import hashlib
import importlib.metadata
import re
import json
from pathlib import Path

import jsonschema


def runid_structure(events):
    by = {}
    for e in events:
        by.setdefault(e["job"]["name"], {}).setdefault(e["eventType"], []).append(e["run"]["runId"])
    problems = []
    per_job = {}
    for job, types in sorted(by.items()):
        ids = {t: v for t, v in types.items()}
        if sorted(ids) != ["COMPLETE", "START"] or any(len(v) != 1 for v in ids.values()):
            problems.append(f"{job}: expected exactly one START and one COMPLETE, got { {t: len(v) for t, v in ids.items()} }")
            continue
        same = ids["START"][0] == ids["COMPLETE"][0]
        per_job[job] = {"run_id": ids["START"][0], "start_complete_same_run_id": same}
        if not same:
            problems.append(f"{job}: START and COMPLETE runIds differ")
    run_ids = [v["run_id"] for v in per_job.values()]
    distinct = len(set(run_ids)) == len(run_ids) == 2
    if not distinct:
        problems.append(f"expected two jobs with distinct runIds, got {len(run_ids)} jobs and {len(set(run_ids))} distinct runIds")
    return per_job, distinct, problems


PLACEHOLDER_RE = re.compile(r"^uuid-redacted-\d{2}$")


def alignment_problems(orig, pub):
    """Fix round 4 (L5.3a): the published file must be the original with each runId replaced one-for-one."""
    problems = []
    if len(orig) != len(pub):
        problems.append(f"event count differs: original {len(orig)}, published {len(pub)}")
    for i, (o, p) in enumerate(zip(orig, pub)):
        if o["job"]["name"] != p["job"]["name"] or o["eventType"] != p["eventType"]:
            problems.append(f"line {i + 1}: job/eventType differ after publication")
        if not PLACEHOLDER_RE.match(p["run"]["runId"]):
            problems.append(f"line {i + 1}: published runId is not a uuid-redacted-NN placeholder")
    fwd, back = {}, {}
    for o, p in zip(orig, pub):
        a, b = o["run"]["runId"], p["run"]["runId"]
        if fwd.setdefault(a, b) != b:
            problems.append("one original runId maps to several placeholders")
        if back.setdefault(b, a) != a:
            problems.append(f"placeholder {b} stands for several original runIds")
    return sorted(set(problems))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--original", required=True, type=Path)
    ap.add_argument("--expected-source-sha256", required=True)
    ap.add_argument("--published", required=True, type=Path)
    ap.add_argument("--spec", required=True, type=Path)
    a = ap.parse_args()
    raw = a.original.read_bytes()
    orig = [json.loads(line) for line in raw.decode().splitlines() if line.strip()]
    pub = [json.loads(line) for line in a.published.read_text().splitlines() if line.strip()]
    # placeholder mapping by position: the published file is the original with each UUID replaced one-for-one
    placeholder = {o["run"]["runId"]: p["run"]["runId"] for o, p in zip(orig, pub)}
    per_job, distinct, problems = runid_structure(orig)
    shown = {job: {"run_id_published_placeholder": placeholder[v["run_id"]], "start_complete_same_run_id": v["start_complete_same_run_id"]}
             for job, v in per_job.items()}
    tampered = copy.deepcopy(orig)
    mat_job = next(j for j in per_job if "materialize" in j)
    sel_job = next(j for j in per_job if j != mat_job)
    for e in tampered:
        if e["job"]["name"] == sel_job and e["eventType"] == "COMPLETE":
            e["run"]["runId"] = per_job[mat_job]["run_id"]
    _, _, control_problems = runid_structure(tampered)

    doc = json.loads(a.spec.read_text())
    validator = jsonschema.Draft202012Validator({**doc, "$ref": "#/$defs/RunEvent"}, format_checker=jsonschema.FormatChecker())
    ph = re.compile(r"^uuid-redacted-(\d{2})$")
    mapped = copy.deepcopy(pub)
    replaced = 0
    for e in mapped:
        m = ph.match(e["run"]["runId"])
        if m:
            e["run"]["runId"] = f"00000000-0000-4000-8000-{int(m.group(1)):012d}"
            replaced += 1
    pub_errors = [f"line {i + 1}: {err.message}" for i, e in enumerate(mapped) for err in validator.iter_errors(e)]
    # detector control: the published bytes as-is; only short messages are kept (no event dumps)
    bad_errors = sorted({err.message for e in pub for err in validator.iter_errors(e) if "is not a 'uuid'" in err.message})
    all_bad = sum(1 for e in pub for _ in validator.iter_errors(e))
    out = {
        "L5.1": {"original_sha256": hashlib.sha256(raw).hexdigest(),
                 "original_sha256_matches_raw_index_source": hashlib.sha256(raw).hexdigest() == a.expected_source_sha256,
                 "events": [{"job": e["job"]["name"], "eventType": e["eventType"], "run_id_published_placeholder": placeholder[e["run"]["runId"]]} for e in orig],
                 "per_job": shown, "two_distinct_run_ids": distinct, "problems": problems,
                 "detector_control": {"mutation": f"{sel_job} COMPLETE runId replaced by the {mat_job} runId", "problems": control_problems,
                                      "flagged": bool(control_problems)},
                 "passed": not problems and bool(control_problems)
                 and hashlib.sha256(raw).hexdigest() == a.expected_source_sha256},
        "L5.2": {"published_sha256": hashlib.sha256(a.published.read_bytes()).hexdigest(), "spec_sha256": hashlib.sha256(a.spec.read_bytes()).hexdigest(),
                 "spec_id": doc.get("$id"), "format_checker": "jsonschema.FormatChecker()", "jsonschema_version": importlib.metadata.version("jsonschema"),
                 "published_events": len(pub), "runids_mapped_from_placeholder": replaced,
                 "mapping": "only run.runId values matching ^uuid-redacted-NN$ -> 00000000-0000-4000-8000-0000000000NN, in memory",
                 "published_errors_after_runid_mapping": pub_errors,
                 "detector_control": {"input": "the published bytes unmapped", "format_errors": bad_errors, "error_count": all_bad, "flagged": bool(bad_errors)},
                 "passed": not pub_errors and bool(bad_errors) and replaced == len(pub)},
    }
    real = alignment_problems(orig, pub)
    sel_complete = next(i for i, e in enumerate(pub) if e["job"]["name"] == sel_job and e["eventType"] == "COMPLETE")
    dropped = [e for i, e in enumerate(pub) if i != sel_complete]
    collapsed = copy.deepcopy(pub)
    for e in collapsed:
        e["run"]["runId"] = pub[0]["run"]["runId"]
    # the first two events share one job, so swap with the first event of the other job (fix-round-4 late amendment)
    other = next(i for i, e in enumerate(pub) if e["job"]["name"] != pub[0]["job"]["name"])
    swapped = copy.deepcopy(pub)
    swapped[0]["job"]["name"], swapped[other]["job"]["name"] = pub[other]["job"]["name"], pub[0]["job"]["name"]
    controls = {name: alignment_problems(orig, ev) for name, ev in
                (("select_complete_removed", dropped), ("all_runids_collapsed", collapsed), ("job_names_swapped_across_jobs", swapped))}
    out["L5.3"] = {"checks": "equal event counts; per-position job name and eventType; placeholder format; one-to-one runId mapping both ways",
                   "published_problems": real,
                   "detector_controls": {k: {"problems": v, "flagged": bool(v)} for k, v in controls.items()},
                   "passed": not real and all(controls.values())}
    print(json.dumps(out, indent=2))
    return 0 if out["L5.1"]["passed"] and out["L5.2"]["passed"] and out["L5.3"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
