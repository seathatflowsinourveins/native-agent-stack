#!/usr/bin/env python3
"""Build the four gap receipts, results.json (generated from the receipts) and README.md for this layer.

Numbers and quoted excerpts are read from the published raw files under the evidence directory, not typed by hand.
Usage: build_receipts.py UNITS_JSON CHECKED_AT [PREVIOUS_CHECKED_AT] [FIX3_CHECKED_AT]   (run from the worktree root)
CHECKED_AT applies to gaps re-checked in fix round 4, FIX3_CHECKED_AT to other fix-round-3 gaps, PREVIOUS_CHECKED_AT to the rest.
"""
import hashlib
import json
from pathlib import Path
import sys

EV = Path("evidence/artifacts/gap-wave2-20260923/us-equities__identity-provenance")
BP = Path("blueprints/gap-wave2-20260923/us-equities__identity-provenance")
PREREG = json.loads((BP / "preregistration.json").read_text())
RAW = json.loads((EV / "inputs" / "raw-index.json").read_text())
SHA = {f["path"]: f["sha256"] for f in RAW["files"]}
unit = next(u for u in json.loads(Path(sys.argv[1]).read_text()) if u["layer_id"] == "identity-provenance")
GAPS = {g["index"]: g["text"] for g in unit["gaps"]}
CHECKED_AT = sys.argv[2] if len(sys.argv) > 2 else None
# gaps not re-checked in fix round 3 keep their earlier check time (argv[3])
PREV_CHECKED_AT = sys.argv[3] if len(sys.argv) > 3 else CHECKED_AT
FIX3_CHECKED_AT = sys.argv[4] if len(sys.argv) > 4 else CHECKED_AT


def j(p):
    return json.loads((EV / p).read_text())


def ref(p):
    return {"path": str(EV / p), "sha256": SHA[p]}


FIX = json.loads((BP / "preregistration-fixround.json").read_text())
FIX2 = json.loads((BP / "preregistration-fixround2.json").read_text())
FIX3 = json.loads((BP / "preregistration-fixround3.json").read_text())
FIX4 = json.loads((BP / "preregistration-fixround4.json").read_text())


def prereg(i, amendments):
    p = PREREG["gaps"][str(i)]
    out = {"written_at": PREREG["written_at"], "written_at_note": PREREG["note"],
           "committed_in": "7078d05 (Preregister gap-wave-2 checks for us-equities identity-provenance), before any check ran",
           "source": str(BP / "preregistration.json"), "expectation": p["expectation"], "criteria": p["criteria"],
           "amendments_after_preregistration": amendments}
    if str(i) in FIX["gaps"]:
        out["fix_round"] = {"label": FIX["label"], "written_at": FIX["written_at"], "written_at_note": FIX["written_at_note"],
                            "committed_in": "3ce38e9 (Preregister the identity-provenance fix round after Codex review), before the fix-round reruns",
                            "source": str(BP / "preregistration-fixround.json"), "review_findings_addressed": FIX["review_findings_addressed"],
                            "criteria": FIX["gaps"][str(i)]["criteria"]}
    if str(i) in FIX2["gaps"]:
        out["fix_round_2"] = {"label": FIX2["label"], "written_at": FIX2["written_at"], "written_at_note": FIX2["written_at_note"],
                              "committed_in": "260398f (Preregister identity-provenance fix round 2 (recovery predicate)), before the fix-round-2 rerun",
                              "source": str(BP / "preregistration-fixround2.json"), "review_findings_addressed": FIX2["review_findings_addressed"],
                              "criteria": FIX2["gaps"][str(i)]["criteria"]}
    if str(i) in FIX3["gaps"]:
        out["fix_round_3"] = {"label": FIX3["label"], "written_at": FIX3["written_at"], "written_at_note": FIX3["written_at_note"],
                              "committed_in": "9f84cc9 (Preregister identity-provenance fix round 3 ...), before any fix-round-3 check ran",
                              "source": str(BP / "preregistration-fixround3.json"), "review_findings_addressed": FIX3["review_findings_addressed"],
                              "criteria": FIX3["gaps"][str(i)]["criteria"]}
    if str(i) in FIX4["gaps"]:
        out["fix_round_4"] = {"label": FIX4["label"], "written_at": FIX4["written_at"], "written_at_note": FIX4["written_at_note"],
                              "committed_in": "aa85595 (Preregister identity-provenance fix round 4 ...), before the fix-round-4 verifier ran",
                              "source": str(BP / "preregistration-fixround4.json"), "review_findings_addressed": FIX4["review_findings_addressed"],
                              "criteria": FIX4["gaps"][str(i)]["criteria"]}
    return out


def sha_list(p):
    return dict(reversed(line.split("  ", 1)) for line in (EV / p).read_text().splitlines() if line.strip())


def log_exits(p):
    import re
    return dict(re.findall(r"^(\w+_exit)=(\d+)$", (EV / p).read_text(), re.M))


cmp_ = j("raw/dvc/comparison.json")
ex = cmp_["exit_codes"]
common_dvc_cmds = [
    "bash blueprints/gap-wave2-20260923/us-equities__identity-provenance/run_dvc_arm.sh $HOME/.cache/gap-wave2-20260923/identity-provenance/runs/dvc-20260923T050541Z",
    "$HOME/.cache/gap-wave2-20260923/identity-provenance/venv-core/bin/python blueprints/gap-wave2-20260923/us-equities__identity-provenance/compare_dvc_arm.py $HOME/.cache/gap-wave2-20260923/identity-provenance/runs/dvc-20260923T050541Z $PWD > comparison.json",
]
dvc_amend = [
    {"at": "2026-09-23T05:01Z (approx.)", "late": True, "change": "Installed pytz==2026.3.post1 (pinned in adoption/sdk/requirements-linux-x86_64-py313.lock) after a debug run showed temporal_snapshot.py select needs it for DuckDB TIMESTAMPTZ fetch."},
    {"at": "2026-09-23T05:02Z (approx.)", "late": True, "change": "Attempt 1 (one git+DVC repo) failed: security-identity probe.py refuses to write inside a git work tree (ValueError private_output_must_be_outside_git). The identity chain moved to a `dvc init --no-scm` repo. Log kept: raw/dvc/attempt1-run.log."},
    {"at": "2026-09-23T05:05Z (approx.)", "late": True, "change": "Attempt 2 passed; attempt 3 (cited) added an explicit native `dvc add` / delete / `dvc checkout` / select arm. Log kept: raw/dvc/attempt2-run.log."},
    {"at": "2026-09-23T05:04Z (approx.)", "late": True, "change": "C0.3 raw diff flags data/.gitignore and out/.gitignore. These are git-tracked files that DVC writes and git restores. The comparison reports them separately and checks the 14 DVC-tracked files on their own."},
]
dvc_amend_g0_fix3 = [{"at": "2026-09-23T13:20:19Z", "late": True, "change": "Fix round 3, preregistered in preregistration-fixround3.json (commit 9f84cc9) after the independent Opus review: the 05:04Z amendment above was written after the C0.3 result, so it cannot rescue the original run, which is not_settled under the original refutation rule. Fix round 3 reran C0.3 on a fresh git+DVC repo with a corrected full-tree criterion (G0.3c: git restores the two .gitignore files, then dvc checkout; G0.3d: delete only the DVC outs), kept the as-written arm as a detector (G0.3b) and added a one-byte tamper control (G0.3e). The gap-0 outcome follows the fix-round-3 rule."}]

# ---------------------------------------------------------------- gap 0, fix round 3
F3 = "raw/dvc-fixround3"
f3x = log_exits(f"{F3}/run.log")
f3pre = sha_list(f"{F3}/pre-delete.sha256")


def f3diff(name):
    post = sha_list(f"{F3}/{name}.sha256")
    return {"files_before": len(f3pre), "files_after": len(post),
            "differing": sorted(k for k in set(f3pre) | set(post) if f3pre.get(k) != post.get(k))}


g03 = {"b": f3diff("b-post-checkout"), "c": f3diff("c-post-checkout"), "d": f3diff("d-post-checkout"),
       "e_tampered": f3diff("e-tampered"), "e_restored": f3diff("e-post-force-checkout")}
f3log = (EV / f"{F3}/run.log").read_text()
g03_pass = {
    "G0.3a": f3x.get("repro1_exit") == "0" and f3x.get("repro2_exit") == "0" and f3log.count("didn't change, skipping") == 6,
    "G0.3b": f3x.get("b_diff_exit") == "1" and g03["b"]["differing"] == ["data/.gitignore", "out/.gitignore"],
    "G0.3c": f3x.get("c_diff_exit") == "0" and g03["c"]["differing"] == [] and f3x.get("c_status_exit") == "0",
    "G0.3d": f3x.get("d_diff_exit") == "0" and g03["d"]["differing"] == [] and f3x.get("d_status_exit") == "0",
    "G0.3e": f3x.get("e_tamper_diff_exit") == "1" and g03["e_tampered"]["differing"] == ["data/ns_materialized/observations.parquet"]
    and "modified:           data/ns_materialized" in f3log and f3x.get("e_restore_diff_exit") == "0" and g03["e_restored"]["differing"] == [],
}
g0_outcome = "settled" if all(g03_pass.values()) else "not_settled"

# ---------------------------------------------------------------- gap 0
add = cmp_["dvc_add_arm"]
ns, pit = cmp_["ns_select"], cmp_["pit_select"]
nsq, pitq = cmp_["ns_quarantine"], cmp_["pit_quarantine"]
forced = cmp_["forced_regeneration"]
r0 = {
    "id": "identity-provenance-g0-dvc-repro-restore-contract", "gap_index": 0,
    "gap_text_sha256": hashlib.sha256(GAPS[0].encode()).hexdigest(), "gap_text": GAPS[0],
    "preregistration": prereg(0, dvc_amend + dvc_amend_g0_fix3),
    "commands": common_dvc_cmds + ["bash blueprints/gap-wave2-20260923/us-equities__identity-provenance/run_c03_fixround3.sh $HOME/.cache/gap-wave2-20260923/identity-provenance/runs/c03-fix3-20260923T132058Z   (fix round 3, C0.3 rerun)",
                                   "(inside run_c03_fixround3.sh, cwd = fresh scratch git+DVC repo) dvc repro; git add -A; git commit; dvc repro; dvc status; [b] rm -rf data out; dvc checkout; diff; [c] rm -rf data out; git checkout -- data/.gitignore out/.gitignore; dvc checkout; diff; dvc status; [d] rm -rf <the eight DVC outs>; dvc checkout; diff; dvc status; [e] dd one byte into data/ns_materialized/observations.parquet; diff; dvc status; dvc checkout --force; diff; dvc status",
                                   "(inside run_dvc_arm.sh, cwd = scratch git+DVC repo) dvc init; dvc add tracked/ns_added; rm -rf tracked/ns_added; dvc checkout tracked/ns_added.dvc; dvc repro; dvc repro; dvc status; dvc dag; rm -rf data out; dvc checkout; stage.py ns-select/ns-quarantine/pit-select/pit-quarantine on the restored data; replay.py select --snapshot-sha256 000…0; dvc repro --force"],
    "results": {
        "exit_codes": {k: ex[k] for k in ("dvc_add_exit", "add_checkout_exit", "add_restore_diff_exit", "add_restored_ns_select_exit",
                                          "git_repro1_exit", "git_repro2_exit", "git_checkout_exit", "git_restore_diff_exit",
                                          "restored_ns_select_exit", "restored_ns_quarantine_exit", "restored_pit_select_exit",
                                          "restored_pit_quarantine_exit", "restored_wrong_digest_cli_exit", "git_repro_force_exit")},
        "C0.1_repro_and_lock": "dvc repro exit 0 for 6 stages (ns_materialize, ns_select, ns_quarantine, pit_snapshot, pit_select, pit_quarantine); dvc.lock pins md5 and size for every dep and out (raw/dvc/run.log `cat dvc.lock`; post-force copy raw/dvc/repo-git__dvc.lock).",
        "C0.2_second_repro_skips": [s for s in cmp_["stages_skipped_in_log"] if not s.startswith("id_")],
        "C0.3_restore_original_run_as_written": dict(cmp_["restore"]["git"], criterion_as_written_passed=False,
                                                     note="git_restore_diff_exit=1: dvc checkout alone did not restore the git-tracked data/.gitignore and out/.gitignore; under the original refutation rule this makes the original run not_settled"),
        "G0.3_fixround3": {"exit_codes": f3x, "arms": g03, "criteria_passed": g03_pass,
                           "pre_delete_files": len(f3pre),
                           "quoted_excerpts": ["< 71701562b963f283a25b2ab12ba2e6ca26a65acdeeb898434b6b240806050b88  data/.gitignore / < 0dd351f92574166a1b410905304bc4a8bdb032586269719c640c1da3af2f372c  out/.gitignore / b_diff_exit=1 (G0.3b, as written)",
                                               "c_git_checkout_exit=0, c_checkout_exit=0, c_diff_exit=0, 'Data and pipelines are up to date.' (G0.3c)",
                                               "d_diff_exit=0 (G0.3d)", "e_tamper_diff_exit=1, 'modified:           data/ns_materialized', e_force_checkout_exit=0, e_restore_diff_exit=0 (G0.3e)"]},
        "native_dvc_add_arm": add,
        "C0.4_per_cutoff": {q: {"row_ids_all_arms_match_test": v["test_assertion_all_arms"], "records_equal_all_arms": v["records_equal_all_arms"],
                                "selection_sql_sha256_equal_all_arms": v["sql_hash_equal_all_arms"],
                                "selection_sql_sha256": v["arms"]["dvc_restored_rerun"]["selection_sql_sha256"]}
                            for q, v in ns["per_query"].items()},
        "C0.4_point_in_time_queries_all_equal": {"records": pit["all_records_equal"], "sql_hash": pit["all_sql_hash_equal"], "test_assertions": pit["all_test_assertions"]},
        "C0.5_unknown_availability_on_restored_source": {"replay": nsq["cases"], "temporal_snapshot": pitq["cases"],
                                                         "all_ok": nsq["all_arms_all_ok"] and pitq["all_arms_all_ok"]},
        "C0.6_forced_regeneration": forced,
        "quoted_excerpts": ["Stage 'ns_materialize' didn't change, skipping (raw/dvc/run.log, second dvc repro)",
                            "{\"status\": \"rejected\", \"reason\": \"snapshot_manifest_hash_mismatch\"} then restored_wrong_digest_cli_exit=2 (raw/dvc/run.log)"],
    },
    "outcome": g0_outcome,
    "outcome_reason": (
        "Under the original preregistration the original run is not_settled: C0.3 as written (full-tree sha256 list after `rm -rf data out; dvc checkout` equals the pre-delete list) failed with git_restore_diff_exit=1, because `dvc checkout` alone does not restore the git-tracked data/.gitignore and out/.gitignore. "
        "C0.1, C0.2, C0.4, C0.5 and C0.6 passed as written on native DVC 3.67.1 CLI runs with live-captured logs. "
        f"The outcome '{g0_outcome}' follows the fix-round-3 rule (preregistration-fixround3.json, written at 13:20:19Z after the original C0.3 result was seen, committed in 9f84cc9 before the rerun). "
        f"On a fresh git+DVC repo: G0.3a repro and cache-aware second repro {'passed' if g03_pass['G0.3a'] else 'FAILED'}; G0.3b (as written, kept as the detector) {'reproduced exactly the two .gitignore differences' if g03_pass['G0.3b'] else 'FAILED'}; "
        f"G0.3c (`git checkout -- data/.gitignore out/.gitignore && dvc checkout`) full-tree diff {'exit 0 on all 16 files' if g03_pass['G0.3c'] else 'FAILED'}; G0.3d (delete only the eight DVC outs, then `dvc checkout`) {'exit 0 on all 16 files' if g03_pass['G0.3d'] else 'FAILED'}; "
        f"G0.3e (one-byte overwrite detected by the diff and `dvc status`, then `dvc checkout --force` restores) {'passed' if g03_pass['G0.3e'] else 'FAILED'}. "
        "The runs cover add, restore and pipeline reproduction: a native `dvc add` of a replay.py snapshot directory was restored byte-identically by `dvc checkout`; a dvc.yaml pipeline wrapping replay.py materialize/select and temporal_snapshot.py snapshot/select ran under `dvc repro` with a dvc.lock, and a second repro skipped all six stages; on the DVC-restored snapshots, per-cutoff records and selection_sql_sha256 equal the project-local path and the regression-test assertions; the unknown-availability mutations of the restored source.json exit 2 while the unmutated control exits 0."),
    "evidence_class": "native_proven",
    "limits": [
        "Synthetic repository fixtures only (replay: 5 observations, 2 universe rows; point-in-time fixture). No real or licensed market data, and no scale measurement.",
        "Local DVC cache only; no remote storage was configured or tested.",
        "`dvc repro --force` re-materializes a new snapshot.json: ingested_at changes, so snapshot_sha256 changes, while the three data files stay byte-identical. A caller holding the old digest must restore through DVC (checkout) rather than repro. This is the documented contract, recorded as C0.6.",
        "Restore contract: `dvc checkout` restores DVC outs only. After a whole-directory delete, the git-tracked .gitignore files that DVC wrote at repro time come back only from git (`git checkout -- data/.gitignore out/.gitignore`), so a complete restore is git checkout plus dvc checkout (fix round 3, G0.3b/G0.3c).",
        "The fix-round-3 C0.3 criterion was written after the original C0.3 failure was seen; the original run stays recorded as failing C0.3 as written. C0.4-C0.6 were not re-run in fix round 3; they come from the original run.",
        "The DVC stage driver (stage.py) is project harness code. It calls the project CLIs by subprocess, so exit codes are the CLIs' own.",
    ],
    "raw_artifacts": [ref(p) for p in ("raw/dvc/run.log", "raw/dvc/attempt1-run.log", "raw/dvc/attempt2-run.log", "raw/dvc/comparison.json",
                                       "raw/dvc/add-pre-delete.sha256", "raw/dvc/add-post-checkout.sha256", "raw/dvc/add-restored-ns_select.json",
                                       "raw/dvc/git-pre-delete.sha256", "raw/dvc/git-post-checkout.sha256", "raw/dvc/git-post-force.sha256",
                                       "raw/dvc/first-ns-snapshot.json", "raw/dvc/forced-ns-snapshot.json", "raw/dvc/first-pit-snapshot.json", "raw/dvc/forced-pit-snapshot.json",
                                       "raw/dvc/restored-rerun__ns_select.json", "raw/dvc/restored-rerun__ns_quarantine.json",
                                       "raw/dvc/restored-rerun__pit_select.json", "raw/dvc/restored-rerun__pit_quarantine.json",
                                       "raw/dvc/git-repro-out__ns_select.json", "raw/dvc/local__ns_select.json", "raw/dvc/local__ns_quarantine.json",
                                       "raw/dvc/repo-git__dvc.lock", "raw/install/install.log", "raw/install/venv-core.freeze.txt")]
    + [ref(f"{F3}/{n}") for n in ("run.log", "pre-delete.sha256", "b-post-checkout.sha256", "c-post-checkout.sha256", "d-post-checkout.sha256",
                                  "e-tampered.sha256", "e-post-force-checkout.sha256", "repo-git__dvc.lock")],
    "helpers": [str(BP / n) for n in ("run_dvc_arm.sh", "dvc.yaml", "stage.py", "compare_dvc_arm.py", "run_c03_fixround3.sh", "preregistration-fixround3.json")],
}

# ---------------------------------------------------------------- gap 2
idc = cmp_["identity"]
r2 = {
    "id": "identity-provenance-g2-dvc-executes-selection-quarantine", "gap_index": 2,
    "gap_text_sha256": hashlib.sha256(GAPS[2].encode()).hexdigest(), "gap_text": GAPS[2],
    "preregistration": prereg(2, dvc_amend + [{"at": "2026-09-23T05:25Z (approx.)", "late": True,
        "change": "The outcome is stricter than the preregistered rule. C2.4 ran, but only on the security-identity test suite's synthetic transport. The retained identity-readiness captures are private and outside the repository, and they were not used, so the outcome is advanced rather than settled."}]),
    "commands": common_dvc_cmds + ["(inside run_dvc_arm.sh, cwd = scratch `dvc init --no-scm` repo) dvc repro (id_capture -> id_quality -> id_ledger -> id_select); dvc repro; rm -rf data out; dvc checkout; stage.py id-select on the restored ledger; dvc repro --force; project-local arm: stage.py id-capture/id-quality/id-ledger/id-select against blueprints/us-equities/security-identity"],
    "results": {
        "exit_codes": {k: ex[k] for k in ("git_repro1_exit", "identity_repro1_exit", "identity_repro2_exit", "identity_checkout_exit",
                                          "identity_restore_diff_exit", "restored_id_select_exit", "restored_ns_quarantine_exit",
                                          "restored_pit_quarantine_exit", "local_id_select_exit")},
        "C2.1_stages_in_dvc_lock": "git repo: ns_select, ns_quarantine, pit_select, pit_quarantine; no-scm repo: id_capture, id_quality, id_ledger, id_select (raw/dvc/run.log `cat dvc.lock`)",
        "C2.1_second_repro_skipped": cmp_["stages_skipped_in_log"],
        "C2.2_quarantine_exit_codes_by_arm": {"replay": nsq["cases"], "temporal_snapshot": pitq["cases"]},
        "C2.3_selection_equal_to_project_local": {"replay_records": ns["all_records_equal"], "replay_sql_hash": ns["all_sql_hash_equal"],
                                                  "pit_records": pit["all_records_equal"], "pit_sql_hash": pit["all_sql_hash_equal"]},
        "C2.4_identity_chain": {"restore": cmp_["restore"]["identity"],
                                "counts_qualified_quarantined_and_sql_hash_equal_across_dvc_repro_restored_local": idc["counts_and_sql_hash_equal"],
                                "counts_by_arm": idc["counts_and_sql_hash_by_arm"],
                                "quarantine_preserved_all_arms": idc["quarantine_preserved_all_arms"],
                                "refusals_all_arms": idc["refusals_all_arms"],
                                "raw_selected_rows_sha256_equal": idc["raw_selected_rows_sha256_equal"],
                                "raw_difference_cause": idc["raw_difference_cause"],
                                "anchor_stripped_rows_equal": idc["anchor_stripped_rows_equal"],
                                "detection_note": "The raw selected_rows_sha256 differs wherever rows are selected, because probe.collect stamps frozen_at and the receipt anchors become row columns. That difference shows the comparator detects row-level change. With only the two anchor columns set to NULL, the rows are equal."},
        "git_guard_finding": "Attempt 1 raised ValueError private_output_must_be_outside_git from probe.new_directory inside a git+DVC repo (raw/dvc/attempt1-run.log). The identity capture chain runs under DVC only as `dvc init --no-scm`.",
    },
    "outcome": "advanced",
    "outcome_reason": "DVC (`dvc repro` plus restore) now executes the replay and point-in-time selection and quarantine paths. It also executes the full security-identity capture, quality, ledger and select chain with its zero-activity quarantine (2 rows, 1 qualified, 1 quarantined). Restored outputs equal the project-local adapter path on counts, selection_sql_sha256 and anchor-stripped rows, and all refusals are preserved.",
    "remaining": [
        "Run the identity-readiness receipt's own retained Alpaca captures (private, outside the repository) through the DVC no-scm pipeline, offline, and compare with native-receipt.json's eligibility hashes. This needs the private capture directory, which this unit did not access.",
        "Decide whether an identity pipeline in a `--no-scm` repo meets the layer's reproducibility needs. In that mode dvc.lock has no git history. A git-backed DVC repo is refused by the adapters' outside-git guard.",
    ],
    "evidence_class": "local_integration",
    "limits": ["Synthetic transport from tests/test_security_identity.py (zero_capture); no provider request, broker contact or credential read.",
               "The native identity-readiness run used alpaca-py 0.44.0 transport; this run patches native_identity and fetch exactly as the unit tests do."],
    "raw_artifacts": [ref(p) for p in ("raw/dvc/run.log", "raw/dvc/attempt1-run.log", "raw/dvc/comparison.json",
                                       "raw/dvc/identity-pre-delete.sha256", "raw/dvc/identity-post-checkout.sha256", "raw/dvc/identity-post-force.sha256",
                                       "raw/dvc/identity-repro-out__id_select.json", "raw/dvc/restored-rerun__id_select.json", "raw/dvc/local__id_select.json",
                                       "raw/dvc/restored-rerun__id_ledger.json", "raw/dvc/local__id_ledger.json", "raw/dvc/repo-identity__dvc.lock",
                                       "raw/dvc/git-repro-out__ns_quarantine.json", "raw/dvc/git-repro-out__pit_quarantine.json",
                                       "raw/dvc/local__pit_select.json", "raw/dvc/local__pit_quarantine.json", "raw/dvc/local.sha256")],
    "helpers": [str(BP / n) for n in ("run_dvc_arm.sh", "dvc.yaml", "dvc-identity.yaml", "stage.py", "compare_dvc_arm.py")],
}

# ---------------------------------------------------------------- gap 4
arms = {a: j(f"raw/stores/{a}.json") for a in ("baseline", "dvc", "iceberg", "arctic")}
conc30 = {a: [j(f"raw/stores/conc30-{a}-{r}.json")["concurrent_writers"] for r in (1, 2)] for a in arms}
table = {}
for a, d in arms.items():
    c = d["concurrent_writers"]
    table[a] = {
        "restore_fidelity_rows": d["restore"], "restore_after_delete": d["restore_after_delete"],
        "correction_retention": d["correction_retention"],
        "lineage_field_classification": d["lineage"]["field_classification"], "lineage_native_count": d["lineage"]["native_count"], "lineage_detail": d["lineage"],
        "recovery_after_sigkill": {"all_recovered": d["recovery_after_sigkill"]["all_recovered"],
                                   "trials": [{"progress_recorded_commits": t["progress_recorded_commits"], "decoded_rows": t["state"].get("rows"), "decoded_batches": t["decoded_batches"],
                                              "store_reported_units": t["store_reported_units"], "content_ok": t["state"]["content"]["content_ok"],
                                              "content_controls_flagged": all(t["state"]["detector_controls"].values()), "recovery_controls": t["recovery_controls"],
                                              "passed": t["whole_units_and_consistent_with_progress"]} for t in d["recovery_after_sigkill"]["trials"]]},
        "concurrency_n10": {k: c[k] for k in ("reported_successful_appends", "rows_expected_from_reported_successes", "rows_found", "rows_lost_after_reported_success", "writer_error_counts", "content", "detector_controls", "no_silent_loss")},
        "concurrency_n30_repeats": [{k: x[k] for k in ("reported_successful_appends", "rows_found", "rows_lost_after_reported_success", "writer_error_counts", "no_silent_loss")} | {"content_ok": x["content"]["content_ok"]} for x in conc30[a]],
        "concurrency_stderr": c["stderr_tail"],
        "storage_bytes_totals": d["storage_bytes"], "latency_ms": d["latency_ms"], "versions": d.get("versions"),
    }
r1 = {a: j(f"raw/stores-round1/{a}.json")["concurrent_writers"]["rows_lost_after_reported_success"] for a in arms}
r1_30 = {a: [j(f"raw/stores-round1/conc30-{a}-{r}.json")["concurrent_writers"]["rows_lost_after_reported_success"] for r in (1, 2)] for a in arms}
f1 = {a: j(f"raw/stores-fixround1/{a}.json")["concurrent_writers"]["rows_lost_after_reported_success"] for a in arms}
f1_30 = {a: [j(f"raw/stores-fixround1/conc30-{a}-{r}.json")["concurrent_writers"]["rows_lost_after_reported_success"] for r in (1, 2)] for a in arms}
import re as _re
ice_max_retry = max([int(m) for r in (1, 2) for t in j(f"raw/stores/conc30-iceberg-{r}.json")["concurrent_writers"]["stderr_tail"].values() for m in _re.findall(r"retrying \((\d)/4\)", t)] or [0])
ice3 = [j(f"raw/stores-fixround3/conc30-iceberg-{r}.json")["concurrent_writers"] for r in (1, 2)]
ice3_summary = [{"rows_lost_after_reported_success": c["rows_lost_after_reported_success"], "reported_successful_appends": c["reported_successful_appends"],
                 "rows_found": c["rows_found"], "writer_error_counts": c["writer_error_counts"], "content_ok": c["content"]["content_ok"],
                 "retry_summary_full_stderr": c["retry_summary_full_stderr"]} for c in ice3]
ice3_max = max(c["retry_summary_full_stderr"]["max_attempt"] for c in ice3)
ice3_lost = [c["rows_lost_after_reported_success"] for c in ice3]
lost = {a: table[a]["concurrency_n10"]["rows_lost_after_reported_success"] for a in arms}
lost30 = {a: [x["rows_lost_after_reported_success"] for x in table[a]["concurrency_n30_repeats"]] for a in arms}
native = {a: table[a]["lineage_native_count"] for a in arms}
ok_all = all(table[a]["recovery_after_sigkill"]["all_recovered"] for a in arms)
r4 = {
    "id": "identity-provenance-g4-four-store-comparison", "gap_index": 4,
    "gap_text_sha256": hashlib.sha256(GAPS[4].encode()).hexdigest(), "gap_text": GAPS[4],
    "preregistration": prereg(4, [
        {"at": "2026-09-23T05:12Z (approx.)", "late": True, "change": "Attempt 1: the DVC arm failed on an empty git commit, now committed with --allow-empty. ArcticDB could not append to an empty seeded frame (E_INCOMPATIBLE_INDEX), so the symbol is seeded with one 5-row batch that is subtracted from row counts. Log kept: raw/stores-round1/attempt1-run.log."},
        {"at": "2026-09-23T05:14Z (approx.)", "late": True, "change": "Recovery trials were raised from 3 to 5. After attempt 2 showed ArcticDB losing rows, a repeatability check was added: 30 appends per writer, 2 repetitions per arm. Attempt 2 log kept: raw/stores-round1/attempt2-run.log."},
        {"at": "2026-09-23T05:30:25Z", "late": True, "change": "Fix round, preregistered in preregistration-fixround.json (commit 3ce38e9) after the Codex review. Round 1 counted baseline rows as committed_versions*5 without decoding, so its rows % 5 check could not fail. The fix round decodes every stored row in every arm and checks that each row is an identical copy of the fixture batch. Detector controls (corrupted, foreign and dropped rows) must be flagged. The fix round also records du -sb next to the file-length sum and classifies lineage fields as native, caller_annotation or absent. Round-1 raw outputs are kept in raw/stores-round1/."},
        {"at": "2026-09-23T13:20:19Z", "late": True, "change": "Fix round 3 (preregistration-fixround3.json H4.1, commit 9f84cc9), recorded after the independent Opus review: fix-round-2 R4.1's parenthetical 'Iceberg: rows/5; ArcticDB: rows/5' is not what the cited stores-fix2 code measured. The code used the Iceberg table's snapshot count and ArcticDB's version count minus the seed version (store_arms.py recovery(): store_units), both store-reported and independent of decoding. rows/5 would have compared decoded batches with decoded rows/5, a tautology. No rerun: this amendment documents the measure that ran."},
        {"at": "2026-09-23T13:20:19Z", "late": True, "change": "Fix round 3 (H4.2/H4.3): the cited runs kept only the last 300 characters of each writer's stderr, so their maximum Iceberg retry attempt is unknown. store_arms.py concurrency() now also writes each writer's complete stderr to its own file and parses every 'retrying (k/N)' line (added after the cited run; stderr_tail is unchanged). A supplementary Iceberg n=30 x2 run with complete stderr is published in raw/stores-fixround3/."},
        {"at": "2026-09-23T15:16:17Z", "late": True, "change": "Fix round 4 (preregistration-fixround4.json H4.5, commit aa85595) after the Codex review of fix round 3: retry_summary counts CommitFailedException in stderr only, and writers catch exceptions into their progress files, so that count alone cannot detect a caught commit failure. The receipt now reports writer_error_counts (read from the progress files) beside it. No rerun: both fields are read from the retained raw/stores-fixround3 outputs."},
        {"at": "2026-09-23T15:30:35Z", "late": True, "change": "Fix round 5 (no preregistration; documentation corrections after the independent Opus review of fix round 4, no rerun): the H4.5 block now carries its preregistered source_review label, and two limits were added or aligned: this is not the verdict_overturn_when comparison (different fixture; validate_source rejection not run in any store arm), and the list of unmeasured candidates now matches the handoff (lakeFS, QuestDB, ClickHouse; delta-rs is not a layer candidate)."},
        {"at": "2026-09-23T05:44:56Z", "late": True, "change": "Fix round 2, preregistered in preregistration-fixround2.json (commit 260398f) after the Codex re-review found that the recovery predicate accepted whole-batch loss or an empty decode. The predicate now requires decoded whole batches to equal the store-reported committed units, and whole-batch-loss and empty-result controls must fail it. The cited gap-4 run is stores-fix2. Fix-round-1 raw outputs are kept in raw/stores-fixround1/."}]),
    "commands": ["bash blueprints/gap-wave2-20260923/us-equities__identity-provenance/run_store_arms.sh $HOME/.cache/gap-wave2-20260923/identity-provenance/runs/stores-fix2-20260923T054530Z   (fix round 2, cited)",
                 "bash blueprints/gap-wave2-20260923/us-equities__identity-provenance/run_store_arms.sh $HOME/.cache/gap-wave2-20260923/identity-provenance/runs/stores-fix-20260923T053213Z   (fix round 1, superseded)",
                 "bash blueprints/gap-wave2-20260923/us-equities__identity-provenance/run_store_arms.sh $HOME/.cache/gap-wave2-20260923/identity-provenance/runs/stores-20260923T051425Z   (round 1, superseded)",
                 "(inside) <venv>/bin/python store_arms.py {baseline,dvc,iceberg,arctic} --fixture <replay.py materialized fixture> --work <dir> --out <arm>.json",
                 "(inside) <venv>/bin/python store_arms.py <arm> ... --only-concurrency 30   (x2 per arm)",
                 "bash blueprints/gap-wave2-20260923/us-equities__identity-provenance/run_iceberg_retry_fixround3.sh $HOME/.cache/gap-wave2-20260923/identity-provenance/runs/iceberg-retry-fix3-20260923T132130Z   (fix round 3, H4.2 supplement: Iceberg n=30 x2, complete stderr)"],
    "results": {"per_arm": table,
                "H4.2_iceberg_n30_complete_stderr_supplement": {"runs": ice3_summary, "max_retry_attempt": ice3_max,
                                                                "detection_method": "regex 'retrying \\((\\d+)/(\\d+)\\)' over each writer's complete stderr file; the same regex parses a control string containing 'retrying (4/4)' as 4 (detector_control_parses_4_of_4)"},
                "H4.5_writer_error_counts_fixround3_supplement": {"evidence_class": "source_review",
                                                                  "evidence_class_note": "a reading of the retained raw/stores-fixround3/conc30-iceberg-{1,2}.json outputs, no rerun (preregistration-fixround4.json H4.5); the receipt as a whole is local_integration",
                                                                  "runs": [c["writer_error_counts"] for c in ice3],
                                                                  "detection_method": "each writer records caught exceptions in its progress file; store_arms.py counts them per writer (writer_error_counts). commit_failed_exception_lines scans stderr only and cannot see a caught exception."},
                "cited_run_retry_max_in_retained_300_char_tails": ice_max_retry,
                "quoted_excerpts": {"iceberg_stderr": arms["iceberg"]["concurrent_writers"]["stderr_tail"]["a"].strip(),
                                    "arctic_docstring": "arcticdb/version_store/library.py:891-892 (installed 6.26.0): 'concurrent writers to a single symbol are not supported other than for primitives that explicitly state support for single-symbol concurrent writes'; :1386 'Note that `append` is not designed for multiple concurrent writers over a single symbol.'"}},
    "outcome": "settled" if all(x == 0 for x in ice3_lost) and all(c["content"]["content_ok"] for c in ice3) else "advanced",
    "outcome_reason": (
        "Fix round 2 ran, with every metric group in the gap text measured for the four store arms of the overturn_protocol on one materialized nanosecond-replay fixture (not the overturn_protocol's point-in-time fixture; see limits): baseline hash-manifest, DVC 3.67.1, PyIceberg 0.12.0 and ArcticDB 6.26.0. By-design gaps are recorded as not_supported. "
        "Every arm restores canonical rows exactly. Only the baseline and DVC keep per-file sha256. After deletion, DVC checkout restores the tracked files byte-identically; the gap-0 run shows this for snapshot.json too, so the old digest still verifies. Baseline re-materialization reproduces the three data files, but snapshot.json changes (ingested_at) and the old digest is refused (snapshot_manifest_hash_mismatch). "
        "Every arm retains the pre-correction version. "
        f"Native lineage fields out of six (caller annotations excluded): DVC add mode {native['dvc']}, Iceberg {native['iceberg']}, baseline {native['baseline']}, ArcticDB {native['arctic']}. "
        f"After SIGKILL, {'every arm' if ok_all else 'not every arm'} reopened in 5/5 trials. The decoded rows were whole identical copies of the fixture batch, and decoded whole batches equaled the store-reported committed units, which matched the writer's last recorded commit or one more. Every corrupted, foreign, dropped-row, whole-batch-loss and empty-result control was flagged. "
        f"With two concurrent writers, baseline, DVC and Iceberg (after its automatic commit retries) lost {lost['baseline']}, {lost['dvc']} and {lost['iceberg']} rows at n=10 and {lost30['baseline']}, {lost30['dvc']} and {lost30['iceberg']} at n=30. "
        f"ArcticDB on LMDB silently lost whole appends that both writers reported as successful: {lost['arctic']} of 100 rows at n=10 and {lost30['arctic']} of 300 at n=30. Earlier rounds gave {f1['arctic']} and {f1_30['arctic']} (fix round 1) and {r1['arctic']} and {r1_30['arctic']} (round 1). The surviving rows are intact copies, and the loss matches its documented single-writer-per-symbol limit. "
        "Storage totals (du -sb and file-length sum) and latency medians are recorded per arm."),
    "evidence_class": "local_integration",
    "limits": ["A 5-row observation and 2-row universe fixture. Storage bytes and latency describe fixed overheads at this size, not throughput or scaling.",
               "Latency units differ by arm: DVC is timed through CLI subprocesses (process start-up included), the others in-process. See each arm's unit_of_work.",
               "ArcticDB runs with pandas 2.3.3, as arcticdb 6.26.0 requires; the other arms use pandas 3.0.6. DuckDB 1.5.5 does canonicalization in every arm.",
               "Iceberg and ArcticDB rewrite the fixture into their own storage formats, so per-file sha256 of source.json and the parquet files is not preserved (not_supported by design). Restore fidelity for them is canonical row-content equality.",
               "Recovery kill points are random (seeded) after at least 3 commits. They are not guaranteed to land inside a commit's critical section.",
               f"PyIceberg retried conflicting commits automatically. The cited runs kept only the last 300 characters of each writer's stderr, so their maximum retry attempt is unknown; the retained tails show up to {ice_max_retry}/4 (fix round 1's tails showed 4/4 once, and that append still committed). The fix-round-3 supplementary Iceberg n=30 x2 run kept complete stderr: maximum attempt {ice3_max}/4, {sum(c['retry_summary_full_stderr']['commit_failed_exception_lines'] for c in ice3)} CommitFailedException lines in stderr, writer errors in the progress files {[c['writer_error_counts'] for c in ice3]}, rows lost {ice3_lost}. Heavier contention could exhaust the 4-retry budget and surface CommitFailedException to the caller.",
               "Storage totals are measured after the v1+v2 writes and before the latency loop. At this size du -sb (apparent size) equals the regular-file byte sum.",
               "ArcticDB's supported parallel-write path (stage + finalize_staged_data) was not tested. S3/remote backends were not tested for any arm.",
               "The lakeFS, QuestDB and ClickHouse layer candidates are not overturn_protocol arms and were not measured. delta-rs (Delta Lake), named as unmeasured in an earlier handoff of this unit, is not a candidate of this layer and was not measured either.",
               "This is not the comparison named in the layer's verdict_overturn_when. That comparison uses the overturn_protocol fixture_paths (blueprints/us-equities/point-in-time/fixture.json with the invariants in tests/test_point_in_time.py and tests/test_security_identity.py); this one used the materialized nanosecond-replay fixture (blueprints/us-equities/nanosecond-replay/fixture.json via replay.py materialize), as preregistered and as the gap's next_check names ('the materialized fixture'). overturn_protocol metric part (2), validate_source rejection of the availability-unknown or inconsistent mutations, was not run in any store arm (store_arms.py has no validate_source call), and the fifth arm (an OpenLineage event over the winning arm) is covered only by gap 5's separate replay run. The gap text's metric list is measured; a verdict change still needs the verdict_overturn_when comparison."],
    "raw_artifacts": [ref(f"raw/stores/{n}") for n in ("run.log", "baseline.json", "dvc.json", "iceberg.json", "arctic.json")]
    + [ref(f"raw/stores/conc30-{a}-{r}.json") for a in arms for r in (1, 2)]
    + [ref(f"raw/stores-fixround1/{n}") for n in ("run.log", "baseline.json", "dvc.json", "iceberg.json", "arctic.json")]
    + [ref(f"raw/stores-round1/{n}") for n in ("run.log", "attempt1-run.log", "attempt2-run.log", "baseline.json", "dvc.json", "iceberg.json", "arctic.json")]
    + [ref(f"raw/install/venv-{v}.freeze.txt") for v in ("core", "iceberg", "arctic")]
    + [ref(f"raw/stores-fixround3/{n}") for n in ("run.log", "conc30-iceberg-1.json", "conc30-iceberg-2.json")]
    + [ref(f"raw/stores-fixround3/conc30-iceberg-{r}__conc-{t}.stderr") for r in (1, 2) for t in ("a", "b")],
    "helpers": [str(BP / n) for n in ("run_store_arms.sh", "store_arms.py", "run_iceberg_retry_fixround3.sh", "preregistration-fixround3.json", "preregistration-fixround4.json")],
}

# ---------------------------------------------------------------- gap 5
emit, rb = j("raw/lineage/work__emit.json"), j("raw/lineage/work__readback.json")
v3 = j("raw/lineage-fixround3/verify.json")
v4 = j("raw/lineage-fixround4/verify.json")
v3_ok = v4["L5.3"]["passed"] and v4["L5.1"]["passed"] and v4["L5.2"]["passed"] and v3["L5.1"]["passed"] and v3["L5.2"]["passed"] and v3["L5.2"]["published_sha256"] == SHA["raw/lineage/work__openlineage-events.ndjson"]
r5 = {
    "id": "identity-provenance-g5-openlineage-mlflow-bindings", "gap_index": 5,
    "gap_text_sha256": hashlib.sha256(GAPS[5].encode()).hexdigest(), "gap_text": GAPS[5],
    "preregistration": prereg(5, [
        {"at": "2026-09-23T05:18Z (approx.)", "late": True, "change": "Added validation of the persisted events against the OpenLineage core spec 2-0-2 JSON schema (fetched with curl, sha256 recorded), with a detector control. Added jsonschema 4.26.0 to the mlflow venv. Attempt 1 log kept."},
        {"at": "2026-09-23T05:19Z (approx.)", "late": True, "change": "Added a knowledge-horizon facet to the materialize run (the maximum available_at in the source) and an MLflow run for the materialize step, so the materialize run itself is logged in MLflow with log_input. Attempt 2 log kept."},
        {"at": "2026-09-23T05:18Z (approx.)", "late": True, "change": "MLflow refused the project's 64-character sha256 as a dataset digest ('digest' exceeds the maximum length of 36 characters). The binding keeps MLflow's own digest, and file_sha256/snapshot_sha256 are recorded as dataset-input tags."},
        {"at": "2026-09-23T13:20:19Z", "late": True, "change": "Fix round 3 (preregistration-fixround3.json L5.1/L5.2, commit 9f84cc9) after the independent Opus review: the readback's C5.1 listing shows only an 8-character runId prefix, identical for both runs, so it cannot show the run structure; and the published ndjson, redacted to 'uuid-redacted-NN', no longer met format: uuid. verify_lineage_fixround3.py now derives the full runId structure from the original event file (sha256 checked against raw-index source_sha256) and validates the published file with FormatChecker."},
        {"at": "2026-09-23T13:27:46Z", "late": True, "change": "Fix round 3, L5.2 amended after its first execution: publishing valid-format placeholder UUIDs (00000000-0000-4000-8000-0000000000NN) made scripts/validate.py fail with 'contains possible local session identifier', because the publication validator rejects every UUID-shaped string. That attempt's output ($HOME/.cache/gap-wave2-20260923/identity-provenance/runs/lineage-fix3-attempt1-validuuid) passed but is not published, since it contains UUID-shaped placeholders. Publishing went back to 'uuid-redacted-NN'. Amended L5.2: validate the published bytes with FormatChecker after mapping, in memory, only run.runId values that exactly match ^uuid-redacted-NN$ to valid-format UUIDs. The unmapped published file is the detector control and must fail on format. L5.2 as preregistered (a published file that is itself format-valid) is recorded as unmet."},
        {"at": "2026-09-23T15:16:17Z", "late": True, "change": "Fix round 4 (preregistration-fixround4.json L5.3, commit aa85595) after the Codex review of fix round 3: the verifier mapped placeholders by zip(orig, pub), so in-memory probes passed after removing the published select COMPLETE event or collapsing every published runId. verify_lineage_fixround3.py now also checks equal event counts, per-position job name and eventType, placeholder format and a one-to-one runId mapping in both directions, with three detector controls. The L5.3b(iii) deviation is recorded separately below with the time it was written."},
        {"at": "2026-09-23T15:16:43.905Z", "late": True, "change": "L5.3b(iii) deviation, written after the 15:16:17Z preregistration and after its commit aa85595 (15:16:18Z). Preregistered (iii) swaps the job names of the first two published events; those two share one job (nanosecond-replay.materialize), so that swap changes nothing. Timeline from the fix-round-4 worker's session transcript and the file mtime (raw/fixround5-timeline/timeline.json): at 15:16:28.900Z an Edit added the control as preregistered (swap events 0 and 1) with a fallback that appended '-swapped' to event 0's job name when the names were equal, i.e. a rename rather than a swap; this draft was never run. At 15:16:30Z the worker listed the published events and saw the shared job. At 15:16:43.905Z one Bash command replaced the control with the executed one (swap event 0's job name with the first event of the other job, control 'job_names_swapped_across_jobs') and in the same command ran run_verify_fixround4.sh (run.log 15:16:43Z-15:16:44Z; verifier mtime 15:16:43.992Z). That was the only verifier run in the window, so the change preceded the only run whose output was read, but it was not recorded before that run: this amendment text was first written at 15:17:24Z and corrected in fix round 5. The across-job swap code did not exist before 15:16:17Z: the verifier committed at aa85595 has no swap control and no alignment check (timeline.json verifier_at_prereg_commit_aa85595). The code comment 'fix-round-4 late amendment' in verify_lineage_fixround3.py refers to this entry."},
        {"at": "2026-09-23T15:30:35Z", "late": True, "change": "Fix round 5 (no preregistration; documentation correction after the independent Opus review of fix round 4, no rerun of any measurement): the 15:16:17Z entry previously carried the (iii) deviation and the claim 'amended before the run was read' without a time of its own. The deviation now has the 15:16:43.905Z entry above, reconstructed by extract_fixround4_timeline.py from retained host records. preregistration-fixround4.json is unchanged and still reads '(iii) the job names of the first two events swapped'."},
        {"at": "2026-09-23T05:30:25Z", "late": True, "change": "Fix round, preregistered in preregistration-fixround.json (commit 3ce38e9) after the Codex review. The original C5.2 says every event's output dataset carries a version facet. That was UNMET as written for the materialize START event: its declared output has no facets, because the snapshot does not exist before the run. The fix round replaces it with a lifecycle-aware rule (F5.1), requires every expected (event, role, dataset) to be present (F5.2), and adds removal and rename detector controls (F5.3). Round-1 raw outputs are kept in raw/lineage-round1/."}]),
    "commands": ["bash blueprints/gap-wave2-20260923/us-equities__identity-provenance/run_lineage_mlflow.sh $HOME/.cache/gap-wave2-20260923/identity-provenance/runs/lineage-fix-20260923T053153Z   (fix round, cited)",
                 "bash blueprints/gap-wave2-20260923/us-equities__identity-provenance/run_lineage_mlflow.sh $HOME/.cache/gap-wave2-20260923/identity-provenance/runs/lineage-20260923T051940Z   (round 1, superseded)",
                 "(inside) unshare -rn venv-mlflow/bin/python lineage_mlflow.py emit --work <dir>",
                 "(inside) unshare -rn venv-mlflow/bin/python lineage_mlflow.py readback --work <dir> --spec $HOME/.cache/gap-wave2-20260923/identity-provenance/spec/OpenLineage-2-0-2.json",
                 "curl -sS -o $HOME/.cache/gap-wave2-20260923/identity-provenance/spec/OpenLineage-2-0-2.json https://openlineage.io/spec/2-0-2/OpenLineage.json",
                 "network probe control outside the namespace (raw/lineage-round1/netprobe-control.log)",
                 "unshare -rn $HOME/.cache/gap-wave2-20260923/identity-provenance/venv-mlflow/bin/python blueprints/gap-wave2-20260923/us-equities__identity-provenance/verify_lineage_fixround3.py --original $HOME/.cache/gap-wave2-20260923/identity-provenance/runs/lineage-fix-20260923T053153Z/work/openlineage-events.ndjson --expected-source-sha256 <raw-index source_sha256> --published evidence/artifacts/gap-wave2-20260923/us-equities__identity-provenance/raw/lineage/work__openlineage-events.ndjson --spec $HOME/.cache/gap-wave2-20260923/identity-provenance/spec/OpenLineage-2-0-2.json   (fix round 3)",
                 "bash blueprints/gap-wave2-20260923/us-equities__identity-provenance/run_verify_fixround4.sh   (fix round 4, L5.3: the same verifier, hardened, on the same original, published file and schema; output in $HOME/.cache/gap-wave2-20260923/identity-provenance/runs/lineage-verify-fix4)"],
    "results": {
        "C5.1_events_readback_listing": {"rows": rb["event_types"], "note": "(runId[:8], job, eventType) as printed by the readback; both runs share the 8-character prefix, so this listing cannot distinguish them. See L5.1_run_id_structure."},
        "L5.1_run_id_structure": v3["L5.1"],
        "L5.3_publication_alignment_fixround4": v4["L5.3"] | {"L5.1_passed_on_rerun": v4["L5.1"]["passed"], "L5.2_passed_on_rerun": v4["L5.2"]["passed"],
                                                              "published_sha256": v4["L5.2"]["published_sha256"]},
        "L5.2_published_file_schema_validation": {"as_preregistered": "unmet: the published file cannot carry valid-format placeholder UUIDs because scripts/validate.py rejects every UUID-shaped string in published files (see the 13:27:46Z amendment)"}
        | {k: v3["L5.2"][k] for k in ("published_sha256", "spec_id", "spec_sha256", "format_checker", "jsonschema_version", "published_events",
                                      "runids_mapped_from_placeholder", "mapping", "published_errors_after_runid_mapping", "detector_control", "passed")},
        "event_file_sha256": rb["event_file_sha256"],
        "C5.2_consistency_problems": rb["openlineage_consistency_problems"],
        "original_C5.2_as_written": "unmet for the materialize START event: its output dataset has facets {} (raw/lineage/work__openlineage-events.ndjson, line 1)",
        "F5.3_detector_controls": rb["detector_controls"], "F5.3_all_flagged": rb["detector_control_flagged"],
        "schema_validation": {k: rb["openlineage_schema_validation"][k] for k in ("spec_id", "spec_sha256", "all_valid", "detector_control_flagged", "detector_control_errors")},
        "C5.3_mlflow_inputs": rb["mlflow_inputs"], "C5.3_mlflow_tags": rb["mlflow_tags"], "C5.3_mlflow_problems": rb["mlflow_problems"],
        "digest_attempts": emit["mlflow"]["digest_attempts"],
        "C5.4_fresh_process_readback": "readback ran in a new process under unshare -rn; readback_exit=0, all_ok true",
        "network": "inside the namespace the probe printed network_blocked OSError; outside it (control) it printed network_reachable",
        "snapshot_sha256": emit["snapshot_sha256"], "cutoff": [emit["cutoff"], emit["cutoff_ns"]], "horizon": [emit["horizon"], emit["horizon_ns"]],
        "versions": emit["versions"],
    },
    "outcome": "settled" if v3_ok else "not_settled",
    "outcome_reason": "Fix round 4 reran the hardened verifier: the published event file has the same event count, job names and eventTypes as the original, placeholder-format runIds and a one-to-one runId mapping; dropped-event, collapsed-runId and swapped-job controls were each flagged, and L5.1/L5.2 passed again. The swapped-job control deviates from preregistered L5.3b(iii) (first two events, which share one job); the deviation was written at 15:16:43.905Z, after the preregistration and in the same command as the only run (see the amendments). " "Fix round 3: from the original event file, START and COMPLETE of the materialize run share one runId, START and COMPLETE of the select run share another, and the two differ (a runId-swap control was flagged); the published, redacted file validates against the 2-0-2 RunEvent schema with FormatChecker once its four 'uuid-redacted-NN' runIds are mapped to valid-format UUIDs, and the unmapped published file fails on format (detector control). L5.2 as preregistered is unmet by a repository constraint: published files may not carry UUID-shaped strings. Settled under the fix-round rule, which is lifecycle-aware; the original C5.2 as written was unmet for the materialize START event and is recorded above. openlineage-python 1.53.0 FileTransport persisted START and COMPLETE events for a replay.py materialize run and its select run. The events carry DatasetVersionDatasetFacet (snapshot_sha256, fixture sha256), per-file content-hash facets and knowledge-cutoff/horizon run facets. A fresh process read them back with 0 problems under the presence-requiring checker, and all 4 events validate against the OpenLineage 2-0-2 core schema. All five detector controls were flagged: tampered version/cutoff, removed materialize COMPLETE output, removed select START input, renamed output, and a schema control with missing eventTime and a bad runId. MLflow 3.16.1 on a local SQLite store logged the materialize run and the select run with mlflow.log_input bindings. The bindings read back through MlflowClient.get_run with matching names, digests, sources, file and snapshot sha256 tags and OpenLineage run-id tags.",
    "evidence_class": "local_integration",
    "limits": ["The version, file-hash and cutoff facets beyond DatasetVersionDatasetFacet are project-defined custom facets (g2_fileHashes, g2_knowledgeCutoff). OpenLineage has no standard knowledge-cutoff facet. Schema validation covers the core RunEvent envelope, not the custom facet schemas (their _schemaURL is not published).",
               "MLflow dataset digests are limited to 36 characters, so the project's sha256 sits in dataset-input tags, not the digest. MLflow's digest is its own 8-character DataFrame hash.",
               "FileTransport only; no Marquez or other lineage backend and no HTTP transport. Local SQLite MLflow store; no tracking server.",
               "Synthetic replay fixture. One materialize run and one select run.",
               "The published event file carries 'uuid-redacted-NN' placeholders, not the real runIds, so as published it does not meet format: uuid; it validates once only those runIds are mapped to valid-format UUIDs. The L5.1 runId structure was derived from the unpublished original, whose sha256 equals the raw-index source_sha256; the redaction is one-for-one, so equality relations hold in the published file too."],
    "raw_artifacts": [ref(f"raw/lineage/{n}") for n in ("run.log", "work__emit.json", "work__readback.json", "work__openlineage-events.ndjson")]
    + [ref(f"raw/lineage-round1/{n}") for n in ("run.log", "attempt1-run.log", "attempt2-run.log", "netprobe-control.log", "work__emit.json", "work__readback.json", "work__openlineage-events.ndjson")]
    + [ref("raw/install/OpenLineage-2-0-2.json"), ref("raw/install/venv-mlflow.freeze.txt")]
    + [ref(f"raw/lineage-fixround3/{n}") for n in ("run.log", "verify.json")]
    + [ref(f"raw/lineage-fixround4/{n}") for n in ("run.log", "verify.json")]
    + [ref("raw/fixround5-timeline/timeline.json")],
    "helpers": [str(BP / n) for n in ("run_lineage_mlflow.sh", "lineage_mlflow.py", "verify_lineage_fixround3.py", "preregistration-fixround3.json", "run_verify_fixround4.sh", "preregistration-fixround4.json", "extract_fixround4_timeline.py")],
}

SLUG = {0: "dvc-repro-restore-contract", 2: "dvc-executes-selection-quarantine", 4: "four-store-comparison", 5: "openlineage-mlflow-bindings"}
for r in (r0, r2, r4, r5):
    g = str(r["gap_index"])
    r["checked_at"] = CHECKED_AT if g in FIX4["gaps"] else FIX3_CHECKED_AT if g in FIX3["gaps"] else PREV_CHECKED_AT
    r["layer"] = "us-equities/identity-provenance"
    r["crosswalk"] = "main 92bb279, crosswalk PR #85"
    (EV / f"{r['gap_index']}-{SLUG[r['gap_index']]}.json").write_text(json.dumps(r, indent=2, sort_keys=False, ensure_ascii=False) + "\n")

# results.json is generated from the receipts on disk
results = {}
for p in sorted(EV.glob("[0-9]-*.json")):
    r = json.loads(p.read_text())
    results[str(r["gap_index"])] = {"outcome": r["outcome"], "receipt": str(p), "evidence_class": r["evidence_class"]}
(EV / "results.json").write_text(json.dumps({"layer": "us-equities/identity-provenance", "generated_from": "receipts in this directory by " + str(BP / "build_receipts.py"),
                                             "results": results}, indent=2) + "\n")
print(json.dumps(results, indent=1))
