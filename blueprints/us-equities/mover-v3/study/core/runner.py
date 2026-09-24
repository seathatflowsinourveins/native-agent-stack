"""Guarded entry points: every stage fetch, evaluation, holdout count and read goes through here.

Order of refusals before anything runs: the protocol at its fixed path is frozen and its study_code.tree is the
running tree (R8-4); its parameters equal the code's (R8-2); the runtime equals study/runtime.lock; the data files
equal their frozen sha256 and the amendment files only grew. An evaluation additionally needs the stage's fetch
line (snapshot sha256 and fetch-incomplete rate) in the run log, and refuses snapshot pages fetched before the
freeze. Results are written once, atomically, with protocol_sha256, the tree and the runtime lock sha256.
"""
from __future__ import annotations

import json
from pathlib import Path

from core import guards, logs
from core.canon import atomic_write_results, sha256_bytes, sha256_file
from core.evaluate import void_rate
from core.params import DATA_DIR, PROTOCOL_PATH, RUN_LOG, STUDY_PATH

DATA_FILES = ("session-calendar.json", "fees-v3.json")
AMENDMENT_FILES = ("session-calendar-amendments.jsonl", "fees-v3-amendments.jsonl")


class RunRefused(Exception):
    pass


def context(repo, *, require_frozen: bool = True, versions=None) -> dict:
    repo = Path(repo)
    pbytes = (repo / PROTOCOL_PATH).read_bytes()
    protocol = json.loads(pbytes)
    tree = guards.running_tree(repo)
    if require_frozen:
        guards.require_frozen(protocol, tree)
        guards.check_parameters(protocol)
    lock_path = repo / STUDY_PATH / "runtime.lock"
    guards.check_runtime(guards.load_lock(lock_path), versions)
    data = {name: sha256_file(repo / DATA_DIR / name) for name in DATA_FILES if (repo / DATA_DIR / name).exists()}
    frozen = (protocol.get("run_discipline", {}).get("study_code") or {}).get("data_file_sha256s") or {}
    if require_frozen and data != frozen:
        raise guards.Refused("a data file differs from its frozen sha256")
    amend = {n: repo / DATA_DIR / n for n in AMENDMENT_FILES}
    run_log = logs.read_lines(repo / RUN_LOG)
    refusals = logs.check_amendment_files(amend, run_log)
    if refusals:
        raise guards.Refused("; ".join(refusals))
    return {"repo": repo, "protocol": protocol, "protocol_sha256": sha256_bytes(pbytes), "tree": tree,
            "runtime_lock_sha256": sha256_file(lock_path), "data_file_sha256s": data,
            "amendment_files": {n: logs.file_state(p) for n, p in amend.items()}, "run_log": run_log}


def fetch_line_for(run_log: list, stage: str, snapshot_sha256: str):
    for line in run_log:
        if line.get("stage") == stage and line.get("purpose") in ("fetch", "refetch") and \
                snapshot_sha256 in (line.get("input_snapshot_sha256s") or []) and line.get("fetch_incomplete_rate") is not None:
            return line
    return None


def run_line(ctx: dict, *, stage, purpose, commit, utc_start, utc_end, snapshots, status, results_sha256,
             extra=None) -> dict:
    line = {"utc_start": utc_start, "utc_end": utc_end, "stage": stage, "purpose": purpose, "commit": commit,
            "study_tree": ctx["tree"], "runtime_lock_sha256": ctx["runtime_lock_sha256"],
            "protocol_sha256": ctx["protocol_sha256"], "data_file_sha256s": ctx["data_file_sha256s"],
            "amendment_files": ctx["amendment_files"], "input_snapshot_sha256s": list(snapshots), "status": status,
            "results_sha256": results_sha256}
    line.update(extra or {})
    return line


def evaluate_and_write(ctx: dict, *, stage: str, snapshot_sha256: str, vintages: list, freeze_utc: str,
                       compute, results_path, before_write=None) -> dict:
    """compute() returns the results dict, in memory. Nothing is written until every item is computed; a failure
    before the write leaves no results file (the caller logs the run as failed and may retry from the same tree
    and the same sealed inputs)."""
    fetch_line = fetch_line_for(ctx["run_log"], stage, snapshot_sha256)
    if fetch_line is None:
        raise RunRefused("the stage's fetch-incomplete rate is not committed in the run log before its outcome")
    guards.check_vintages(vintages, freeze_utc)
    results = compute()
    results.update({"protocol_sha256": ctx["protocol_sha256"], "study_tree": ctx["tree"],
                    "runtime_lock_sha256": ctx["runtime_lock_sha256"], "input_snapshot_sha256": snapshot_sha256,
                    "fetch_incomplete_rate": fetch_line["fetch_incomplete_rate"]})
    if before_write is not None:
        before_write()
    digest = atomic_write_results(results_path, results)
    return {"results_sha256": digest}


def void_from_fetch(incomplete_by_kind: dict) -> dict:
    return void_rate(incomplete_by_kind)
