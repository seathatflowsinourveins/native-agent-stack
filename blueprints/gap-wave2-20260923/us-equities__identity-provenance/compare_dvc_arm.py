#!/usr/bin/env python3
"""Compare the DVC-executed, DVC-restored and project-local arms of run_dvc_arm.sh (gaps 0 and 2).

Usage: compare_dvc_arm.py RUN_DIR WORKTREE > comparison.json   (run with the venv-core python; needs duckdb 1.5.5)
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

O, WT = Path(sys.argv[1]), Path(sys.argv[2])


def load(p):
    return json.loads(Path(p).read_text())


def sha_lines(p):
    rows = {}
    for line in Path(p).read_text().splitlines():
        h, name = line.split(None, 1)
        rows[name.strip()] = h
    return rows


def restore(label):
    pre, post = sha_lines(O / f"{label}-pre-delete.sha256"), sha_lines(O / f"{label}-post-checkout.sha256")
    differing = sorted(k for k in set(pre) | set(post) if pre.get(k) != post.get(k))
    git_tracked = [k for k in differing if k.endswith(".gitignore")]
    return {"files_before": len(pre), "files_after": len(post), "differing": differing,
            "differing_are_only_git_tracked_gitignores": set(differing) == set(git_tracked),
            "dvc_tracked_files_identical": all(pre[k] == post.get(k) for k in pre if not k.endswith(".gitignore"))}


def ns_or_pit(kind, key):
    arms = {"dvc_repro": load(O / "git-repro-out" / f"{kind}_select.json"),
            "dvc_restored_rerun": load(O / "restored-rerun" / f"{kind}_select.json"),
            "project_local": load(O / "local" / f"{kind}_select.json")}
    per = {}
    for q in arms["project_local"][key]:
        row = {arm: {f: d[key][q][f] for f in ("exit", "records_sha256", "selection_sql_sha256", "matches_test_assertion")}
               | {"snapshot_sha256": d[key][q]["result"].get("snapshot_sha256")} for arm, d in arms.items()}
        per[q] = {"arms": row,
                  "records_equal_all_arms": len({v["records_sha256"] for v in row.values()}) == 1,
                  "sql_hash_equal_all_arms": len({v["selection_sql_sha256"] for v in row.values()}) == 1,
                  "test_assertion_all_arms": all(v["matches_test_assertion"] for v in row.values()),
                  "dvc_repro_and_restored_same_snapshot_sha256": row["dvc_repro"]["snapshot_sha256"] == row["dvc_restored_rerun"]["snapshot_sha256"],
                  "local_snapshot_sha256_differs": row["project_local"]["snapshot_sha256"] != row["dvc_repro"]["snapshot_sha256"]}
    return {"per_query": per, "all_records_equal": all(v["records_equal_all_arms"] for v in per.values()),
            "all_sql_hash_equal": all(v["sql_hash_equal_all_arms"] for v in per.values()),
            "all_test_assertions": all(v["test_assertion_all_arms"] for v in per.values())}


def quarantine(kind, repo):
    arms = {"dvc_repro": load(O / f"{repo}-repro-out" / f"{kind}_quarantine.json"),
            "dvc_restored_rerun": load(O / "restored-rerun" / f"{kind}_quarantine.json"),
            "project_local": load(O / "local" / f"{kind}_quarantine.json")}
    cases = {c: {arm: d["cases"][c]["exit"] for arm, d in arms.items()} | {"expected": arms["project_local"]["cases"][c]["expected_exit"]}
             for c in arms["project_local"]["cases"]}
    return {"cases": cases, "all_arms_all_ok": all(d["all_ok"] for d in arms.values()),
            "exits_identical_across_arms": all(len({v for k, v in c.items() if k != "expected"}) == 1 for c in cases.values())}


def identity():
    spec = importlib.util.spec_from_file_location("g2_ledger", WT / "blueprints/us-equities/security-identity/ledger.py")
    ledger = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ledger)
    sql = (WT / "blueprints/us-equities/security-identity/select.sql").read_text()
    # The identity repo was force-reproduced after the restore, so the restored bars.parquet is taken from the
    # DVC cache object whose sha256 equals the pre-delete (== post-checkout) hash of data/id_ledger/bars.parquet.
    want = sha_lines(O / "identity-post-checkout.sha256")["data/id_ledger/bars.parquet"]
    cached = [p for p in (O / "repo-identity/.dvc/cache").rglob("*") if p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest() == want]
    stripped = {}
    for arm, path in [("dvc_restored_cache_object", cached[0]), ("project_local", O / "local/id_ledger/bars.parquet")]:
        with ledger.connection() as con:
            con.execute(f"CREATE VIEW bars AS SELECT * REPLACE (NULL::VARCHAR AS acquisition_receipt_sha256, NULL::VARCHAR AS derivation_receipt_sha256) FROM read_parquet('{path}')")
            stripped[arm] = {label: ledger.selection(con, sql, ledger.P.ns(cutoff), case) for label, cutoff, case in [
                ("after-observation-meta_unmapped", "2026-09-21T00:00:00Z", "meta_unmapped"),
                ("after-observation-meta_mapped", "2026-09-21T00:00:00Z", "meta_mapped"),
                ("historical-2022-meta_unmapped", "2022-06-30T00:00:00Z", "meta_unmapped"),
                ("before-first-observation", "2026-09-20T12:00:00.000000100Z", "meta_unmapped")]}
    arms = {"dvc_repro": load(O / "identity-repro-out/id_select.json"),
            "dvc_restored_rerun": load(O / "restored-rerun/id_select.json"),
            "project_local": load(O / "local/id_select.json")}
    counts = {arm: {k: [v["count"], v["qualified_count"], v["quarantined_count"], v["selection_sql_sha256"]] for k, v in d["selections"].items()}
              for arm, d in arms.items()}
    frozen = {arm: re.search(r'"frozen_at":\s*"([^"]+)"', (root / "freeze.json").read_text()).group(1)
              for arm, root in [("dvc_after_force_repro", O / "repo-identity/data/id_capture"), ("project_local", O / "local/id_capture")]}
    return {"counts_and_sql_hash_by_arm": counts,
            "counts_and_sql_hash_equal": counts["dvc_repro"] == counts["dvc_restored_rerun"] == counts["project_local"],
            "quarantine_preserved_all_arms": all(d["quarantine_preserved"] for d in arms.values()),
            "refusals_all_arms": {arm: d["refusals"] for arm, d in arms.items()},
            "raw_selected_rows_sha256_equal": {k: arms["dvc_repro"]["selections"][k]["result"]["selected_rows_sha256"] == arms["project_local"]["selections"][k]["result"]["selected_rows_sha256"] for k in counts["project_local"]},
            "raw_difference_cause": {"frozen_at": frozen, "note": "probe.collect stamps frozen_at (wall clock) into freeze.json; the receipt anchors derived from it are row columns acquisition_receipt_sha256/derivation_receipt_sha256"},
            "anchor_stripped_selected_rows_sha256": {k: {arm: stripped[arm][k]["selected_rows_sha256"] for arm in stripped} for k in stripped["project_local"]},
            "restored_bars_cache_object": str(cached[0].relative_to(O)), "restored_bars_sha256": want,
            "anchor_stripped_rows_equal": all(stripped["dvc_restored_cache_object"][k]["selected_rows_sha256"] == stripped["project_local"][k]["selected_rows_sha256"] for k in stripped["project_local"])}


def added():
    pre, post = sha_lines(O / "add-pre-delete.sha256"), sha_lines(O / "add-post-checkout.sha256")
    sel, local = load(O / "add-restored-ns_select.json"), load(O / "local/ns_select.json")
    return {"files": len(pre), "restore_identical": pre == post, "all_test_assertions": sel["all_match"],
            "records_and_sql_hash_equal_to_local": all(sel["cutoffs"][c]["records_sha256"] == local["cutoffs"][c]["records_sha256"]
                                                        and sel["cutoffs"][c]["selection_sql_sha256"] == local["cutoffs"][c]["selection_sql_sha256"] for c in local["cutoffs"])}


def forced():
    out = {}
    for kind in ("ns", "pit"):
        a, b = load(O / f"first-{kind}-snapshot.json"), load(O / f"forced-{kind}-snapshot.json")
        out[kind] = {"differing_manifest_keys": sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k)),
                     "data_file_hashes_equal": a["files"] == b["files"]}
    pre, post = sha_lines(O / "git-pre-delete.sha256"), sha_lines(O / "git-post-force.sha256")
    out["git_repo_changed_files"] = sorted(k for k in pre if pre[k] != post.get(k))
    return out


log = (O / "run.log").read_text()
exits = dict(re.findall(r"^(\w+_exit)=(\d+)$", log, re.M))
skips = re.findall(r"Stage '(\w+)' didn't change, skipping", log)
print(json.dumps({"exit_codes": exits, "stages_skipped_in_log": skips,
                  "restore": {"git": restore("git"), "identity": restore("identity")},
                  "ns_select": ns_or_pit("ns", "cutoffs"), "pit_select": ns_or_pit("pit", "queries"),
                  "ns_quarantine": quarantine("ns", "git"), "pit_quarantine": quarantine("pit", "git"),
                  "identity": identity(), "dvc_add_arm": added(), "forced_regeneration": forced()}, indent=2, sort_keys=True))
