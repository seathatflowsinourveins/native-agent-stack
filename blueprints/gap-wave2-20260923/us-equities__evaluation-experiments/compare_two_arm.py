"""Compare the promptfoo (arm 1) and inspect-ai (arm 2) runs produced by run_two_arm.sh.

Usage: compare_two_arm.py RUN_DIR REPO_ROOT > comparison.json
Only reads the run directory; prints one JSON document.
"""
import glob
import hashlib
import json
import sys
from pathlib import Path

RUN, REPO = Path(sys.argv[1]), Path(sys.argv[2])
CASES = json.loads((REPO / "blueprints/native-skill-practice/catalog-cases.json").read_text())
IDS = [c["metadata"]["case_id"] for c in CASES]
FROZEN_SOURCE_SHA = {c["metadata"]["case_id"]: hashlib.sha256(c["vars"]["source"].encode()).hexdigest() for c in CASES}


def pf_rows(path):
    d = json.loads(Path(path).read_text())
    rows = {}
    for r in d["results"]["results"]:
        cid = IDS[r["testIdx"]]
        out = (r.get("response") or {}).get("output")
        gated = json.loads(out) if isinstance(out, str) and out.startswith("{") else None
        comps = (r.get("gradingResult") or {}).get("componentResults") or []
        rows[cid] = {"verdict": gated and gated["verdict"], "eligible": gated and gated["eligible"],
                     "disposition": gated and gated["disposition"], "pass": bool(r["success"]),
                     "assertions": [c["pass"] for c in comps], "error": r.get("failureReason") == 2,
                     "source_sha256": gated and gated["source_sha256"], "provider": r["provider"].get("label"),
                     "result_id": r["id"]}
    return d, rows


def in_rows(path):
    d = json.loads(Path(path).read_text())
    rows = {}
    for s in d.get("samples") or []:
        score = next(iter((s.get("scores") or {}).values()), None)
        meta = (score or {}).get("metadata") or {}
        gated = meta.get("gated")
        rows[s["id"]] = {"verdict": gated and gated["verdict"], "eligible": gated and gated["eligible"],
                         "disposition": gated and gated["disposition"],
                         "pass": bool(score) and score["value"] == "C",
                         "assertions": [a["pass"] for a in meta.get("assertions", [])],
                         "error": bool(s.get("error")), "source_sha256": gated and gated["source_sha256"],
                         "error_retries": [e["message"] for e in s.get("error_retries") or []],
                         "error_message": (s.get("error") or {}).get("message"),
                         "uuid": s.get("uuid"), "started_at": s.get("started_at")}
    return d, rows


def vector(rows):
    return {cid: {k: rows[cid][k] for k in ("verdict", "eligible", "disposition", "pass", "assertions")}
            for cid in IDS if cid in rows}


def one(pattern):
    found = sorted(glob.glob(str(RUN / pattern)))
    return found


out = {"cases": IDS}
_, pf1 = pf_rows(RUN / "pf-clean-1/results.json")
_, pf2 = pf_rows(RUN / "pf-clean-2/results.json")
_, in1 = in_rows(one("in-clean-1/logs/*.json")[0])
d_in2, in2 = in_rows(one("in-clean-2/logs/*.json")[0])
out["outcome_vector"] = {"promptfoo": vector(pf1), "inspect": vector(in1)}
out["label_matches"] = {"promptfoo": sum(r["pass"] for r in pf1.values()), "inspect": sum(r["pass"] for r in in1.values()), "cases": len(IDS)}
out["reproducibility"] = {
    "promptfoo_repeat_identical": vector(pf1) == vector(pf2),
    "inspect_repeat_identical": vector(in1) == vector(in2),
    "cross_arm_identical": vector(pf1) == vector(in1),
    "differing_cases": [cid for cid in IDS if vector(pf1).get(cid) != vector(in1).get(cid)],
}
out["gate_source_hash"] = {cid: {"frozen": FROZEN_SOURCE_SHA[cid], "promptfoo": pf1[cid]["source_sha256"],
                                 "inspect": in1[cid]["source_sha256"]} for cid in IDS}
out["gate_source_hash_summary"] = {
    "promptfoo_equal_frozen": [cid for cid in IDS if pf1[cid]["source_sha256"] == FROZEN_SOURCE_SHA[cid]],
    "inspect_equal_frozen": [cid for cid in IDS if in1[cid]["source_sha256"] == FROZEN_SOURCE_SHA[cid]],
}
out["provider_calls"] = {
    "promptfoo_provider_labels": sorted({r["provider"] for r in pf1.values()}),
    "promptfoo_error_rows_clean": sum(r["error"] for r in pf1.values()),
    "inspect_model": d_in2["eval"]["model"], "inspect_model_usage": d_in2["stats"].get("model_usage"),
    "inspect_sample_errors_clean": sum(r["error"] for r in in1.values()),
    "network": "all arms under unshare -rn (loopback down, no route); any HTTP attempt would error",
}

# Failure-log fidelity.
def fidelity(rows):
    failed = [cid for cid in IDS if not rows[cid]["pass"]]
    recoverable = [cid for cid in failed if len(rows[cid]["assertions"]) == 3 and not all(rows[cid]["assertions"]) and rows[cid]["verdict"]]
    return {"failed_cases": failed, "failed_with_per_assertion_detail": recoverable}

pf_first_db = json.loads((RUN / "pf-fault/db-after-first.json").read_text())
pf_retry_db = json.loads((RUN / "pf-fault/db-after-retry.json").read_text())
_, pf_fault_final = pf_rows(RUN / "pf-fault/results.json")
err_logs = sorted((RUN / "pf-fault" / "home" / "logs").glob("promptfoo-error-*.log"))
d_inf, in_fault = in_rows(one("in-fault/logs/*.json")[0])
d_nr, in_noretry = in_rows(one("in-fault-noretry/logs/*.json")[0])
out["failure_log_fidelity"] = {
    "promptfoo": dict(fidelity(pf1), injected_error={
        "first_run_db_row_failure_reason": [r["failure_reason"] for r in pf_first_db["eval_results"] if r["test_idx"] == 2],
        "after_retry_db_row_failure_reason": [r["failure_reason"] for r in pf_retry_db["eval_results"] if r["test_idx"] == 2],
        "db_row_id_replaced_on_retry": [r["id"] for r in pf_first_db["eval_results"] if r["test_idx"] == 2] != [r["id"] for r in pf_retry_db["eval_results"] if r["test_idx"] == 2],
        "final_output_has_error_row": any(r["error"] for r in pf_fault_final.values()),
        "retained_error_log_files_with_text": [p.name for p in err_logs if "injected transient failure" in p.read_text()],
        "retry_recovered_outcome_equals_clean": vector(pf_fault_final) == vector(pf1),
        "output_file_overwritten_by_retry": not (RUN / "pf-fault-retry/results.json").exists(),
    }),
    "inspect": dict(fidelity(in1), injected_error={
        "final_log_status": d_inf["status"],
        "C3_error_retries_in_final_log": in_fault["C3"]["error_retries"],
        "retry_recovered_outcome_equals_clean": vector(in_fault) == vector(in1),
        "no_retry_log_status": d_nr["status"],
        "no_retry_error_message": d_nr.get("error", {}).get("message"),
        "no_retry_samples_in_log": len(in_noretry),
    }),
}

# Interrupt and resume.
db_int = json.loads((RUN / "pf-int/db-after-interrupt.json").read_text())
db_res = json.loads((RUN / "pf-int/db-after-resume.json").read_text())
_, pf_res = pf_rows(RUN / "pf-int/results-interrupted.json")
pre = {r["test_idx"]: r["id"] for r in db_int["eval_results"]}
post = {r["test_idx"]: r["id"] for r in db_res["eval_results"]}
in_logs = sorted(one("in-int/logs/*.json"))
d_can, in_can = in_rows(in_logs[0]); d_fin, in_fin = in_rows(in_logs[-1])
done_before = [cid for cid, r in in_can.items() if not r["error"]]
out["interrupt_resume"] = {
    "promptfoo": {"evals_before": len(db_int["evals"]), "evals_after": len(db_res["evals"]),
                  "same_eval_id": [e["id"] for e in db_int["evals"]] == [e["id"] for e in db_res["evals"]],
                  "rows_before_resume": len(pre), "rows_after_resume": len(post),
                  "duplicate_test_idx_after": len(db_res["eval_results"]) != len(post),
                  "pre_interrupt_rows_preserved": all(post.get(k) == v for k, v in pre.items()),
                  "final_outcome_equals_clean": vector(pf_res) == vector(pf1)},
    "inspect": {"interrupted_log_status": d_can["status"], "completed_before": done_before,
                "cancelled_samples": [cid for cid, r in in_can.items() if r["error"]],
                "resumed_log_status": d_fin["status"], "samples_after": len(in_fin),
                "completed_samples_reused_not_rerun": all(in_fin[c]["uuid"] == in_can[c]["uuid"] and in_fin[c]["started_at"] == in_can[c]["started_at"] for c in done_before),
                "final_outcome_equals_clean": vector(in_fin) == vector(in1)},
}
print(json.dumps(out, indent=1))
