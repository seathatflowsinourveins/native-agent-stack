"""Guarded entry points: every stage fetch, evaluation, holdout collection, count and read goes through here, and
run.py is the only caller. A library call that bypasses run.py writes no run-log line, and a result without its
run-log line never governs (holdout_gate.evaluator_refusals), so such a call is procedurally forbidden and inert
(review round 9, F8).

Order of refusals before anything runs (context): the entry point reads no bytecode cache from the tree and the study
tree is committed and clean (F9); HEAD is reachable from origin/main and the run log, access log, deviations file
and amendment files equal their origin/main content (F2); the protocol that runs is the freeze commit's blob, and
the working copy and HEAD equal it (F3); the running tree is the pinned tree or a committed passing transport
deviation of it (R8-4, H-2); the parameters equal the code's (R8-2); the runtime equals study/runtime.lock; the data
files equal their frozen sha256; the amendment files only grew, and every amendment line concerns a date on or after
the freeze session and reached origin/main in time (R8-10, M-3, F5); coverage_decision agrees with the committed
count-only output (F7). A stage is fetched once (with its single re-fetch) and evaluated into one results file at a
fixed path, and a retry uses the same sealed snapshot (F1, M-4, F10). Review round 10 adds the remote-main check
(H2), the append-only history check (M1), signed reach times (M3), 'amend' records for amendment lines (F2), void
deviations (F4), a bound transport-check output (H1) and the full runtime check (L3); check_clock refuses a holdout
action whose local clock is earlier than origin/main's tip (M2).
"""
from __future__ import annotations

import json
from pathlib import Path

from core import chronology as CH
from core import guards, logs
from core.calendar import Calendar, read_amendments
from core.canon import atomic_write_results, sha256_bytes, sha256_file
from core.costs import Fees, load_table, monotone
from core.coverage_rule import rule_sha256
from core.evaluate import void_rate
from core.params import (ACCESS_LOG, COST_TABLE, COUNT_ONLY_OUTPUT, DATA_DIR, DEVIATIONS, PROTOCOL_PATH, RESULTS_DIR,
                         RUN_LOG, STUDY_PATH)

DATA_FILES = ("session-calendar.json", "fees-v3.json")
AMENDMENT_FILES = ("session-calendar-amendments.jsonl", "fees-v3-amendments.jsonl")
APPEND_ONLY = (RUN_LOG, ACCESS_LOG, DEVIATIONS) + tuple(f"{DATA_DIR}/{n}" for n in AMENDMENT_FILES)


class RunRefused(Exception):
    pass


# ---------------------------------------------------------------- context

def check_coverage_decision(repo, protocol: dict) -> dict:
    """Review round 9, F7: coverage_decision is typed and equals the item_rule of the committed count-only output
    whose sha256 the frozen protocol records; the output's coverage_rule sha256 equals the frozen coverage_rule's."""
    cd = protocol.get("coverage_decision")
    if not isinstance(cd, dict):
        raise guards.Refused("coverage_decision is missing from the frozen protocol")
    dy, tested = cd.get("dropped_years"), cd.get("items_tested")
    if not isinstance(dy, list) or len(set(dy)) != len(dy) or \
            any(type(y) is not int or not 2016 <= y <= 2020 for y in dy):
        raise guards.Refused("coverage_decision.dropped_years must be distinct integers in 2016-2020")
    if type(tested) is not bool:
        raise guards.Refused("coverage_decision.items_tested must be a boolean")
    path = Path(repo) / COUNT_ONLY_OUTPUT
    if cd.get("count_only_output") != COUNT_ONLY_OUTPUT or not path.exists():
        raise guards.Refused(f"coverage_decision.count_only_output must name the committed {COUNT_ONLY_OUTPUT}")
    raw = path.read_bytes()
    if sha256_bytes(raw) != cd.get("count_only_output_sha256"):
        raise guards.Refused("the count-only output differs from coverage_decision.count_only_output_sha256")
    out = json.loads(raw)
    ir = out.get("item_rule") or {}
    if sorted(dy) != ir.get("dropped_years") or tested is not ir.get("items_tested"):
        raise guards.Refused("coverage_decision differs from the governing count-only output's item_rule")
    if out.get("coverage_rule_sha256") != rule_sha256(protocol):
        raise guards.Refused("the count-only output was decided under another coverage_rule")
    rate = (((out.get("years") or {}).get("2020") or {}).get("rates") or {}).get("identity_unreached_rate")
    return {"dropped_years": frozenset(dy), "items_tested": tested,
            "validation_identity_limited": bool(out.get("validation_identity_limited")),
            "identity_unreached_rate_2020": rate, "enumeration_sha256": (out.get("part0") or {}).get(
                "enumeration_sha256")}


def context(repo, *, versions=None, amend_pending_ok: bool = False, transport_check: bool = False) -> dict:
    """amend_pending_ok: the 'amend' authorization and record path, which runs while an amendment line awaits its
    access-log record (review round 10, F2). transport_check: run.py transport-check, which runs from a tree that
    differs from the pinned tree only under study/fetch/ before its deviation exists (H1, F6)."""
    repo = Path(repo)
    guards.check_bytecode_isolated()
    tree = guards.running_tree(repo)
    guards.require_remote_main(repo)                   # review round 10, H2
    guards.require_on_main(repo, APPEND_ONLY)
    guards.check_append_only_history(repo, APPEND_ONLY)   # review round 10, M1
    freeze_commit, freeze_ts = guards.freeze_commit(repo)
    pbytes, protocol = guards.frozen_protocol(repo, freeze_commit)
    guards.require_frozen(protocol)
    run_log = logs.read_lines(repo / RUN_LOG)
    access_log = logs.read_lines(repo / ACCESS_LOG)
    pinned_tree = protocol["run_discipline"]["study_code"]["tree"]
    if transport_check:
        if tree == pinned_tree or not guards.fetch_only_diff(repo, pinned_tree, tree):
            raise guards.Refused("transport-check runs from a tree that differs from the pinned tree only under fetch/")
        deviation = None
    else:
        deviation = guards.check_study_tree(repo, protocol, tree, run_log)
    void_scopes = guards.voids(repo)                   # review round 10, F4
    guards.check_parameters(protocol)
    lock_path = repo / STUDY_PATH / "runtime.lock"
    lock = guards.load_lock(lock_path)
    guards.check_runtime(lock, versions)
    data = {name: sha256_file(repo / DATA_DIR / name) for name in DATA_FILES if (repo / DATA_DIR / name).exists()}
    frozen = (protocol.get("run_discipline", {}).get("study_code") or {}).get("data_file_sha256s") or {}
    if data != frozen:
        raise guards.Refused("a data file differs from its frozen sha256")
    amend = {n: repo / DATA_DIR / n for n in AMENDMENT_FILES}
    refusals = logs.check_amendment_files(amend, run_log)
    cal_path, fee_path = repo / DATA_DIR / DATA_FILES[0], repo / DATA_DIR / DATA_FILES[1]
    pinned = Calendar.from_files(cal_path)
    freeze_session = CH.freeze_session(pinned, freeze_ts)
    if freeze_session is None:
        raise guards.Refused("the pinned calendar has no session after the freeze commit")
    cal_lines, fee_lines = read_amendments(amend[AMENDMENT_FILES[0]]), read_amendments(amend[AMENDMENT_FILES[1]])
    reach = {n: {i: t for i, (_, t) in enumerate(logs.line_reach(repo, f"{DATA_DIR}/{n}"))} for n in AMENDMENT_FILES}
    first_use = logs.fee_first_use(fee_lines, run_log)
    refusals += logs.check_calendar_amendments(cal_lines, reach[AMENDMENT_FILES[0]], pinned, freeze_session)
    refusals += logs.check_fee_amendments(fee_lines, reach[AMENDMENT_FILES[1]], first_use, freeze_session)
    # review round 10, F2: every amendment line is logged under purpose 'amend' before its deadline
    records = logs.amend_records(access_log)
    access_reach = {i: t for i, (_, t) in enumerate(logs.line_reach(repo, ACCESS_LOG))} if records else {}
    deadlines = {AMENDMENT_FILES[0]: {i: (pinned.at(r["session"], "09:30") if r.get("session") and
                                          pinned.is_session(r["session"]) else None) for i, r in enumerate(cal_lines)},
                 AMENDMENT_FILES[1]: {i: first_use.get(i) for i in range(len(fee_lines))}}
    for n, lines in ((AMENDMENT_FILES[0], cal_lines), (AMENDMENT_FILES[1], fee_lines)):
        refusals += logs.check_amend_logged(n, lines, logs.raw_lines(amend[n]), records, access_reach, deadlines[n],
                                            pending_ok=amend_pending_ok)
    if refusals:
        raise guards.Refused("; ".join(refusals))
    cal = Calendar.from_files(cal_path, amend[AMENDMENT_FILES[0]], freeze_session=freeze_session)
    fees = Fees.from_files(fee_path, amend[AMENDMENT_FILES[1]], freeze_session=freeze_session)
    coverage = check_coverage_decision(repo, protocol)
    tip = guards.git(repo, "rev-parse", guards.MAIN)
    from datetime import datetime, timezone
    return {"repo": repo, "protocol": protocol, "protocol_sha256": sha256_bytes(pbytes), "tree": tree,
            "pinned_tree": pinned_tree, "transport_deviation": deviation, "voids": void_scopes,
            "commit": guards.git(repo, "rev-parse", "HEAD"), "freeze_commit": freeze_commit, "freeze_ts": freeze_ts,
            "freeze_utc": datetime.fromtimestamp(freeze_ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "freeze_session": freeze_session, "n0_pinned": CH.n0(pinned, freeze_ts), "pinned_cal": pinned,
            "cal": cal, "fees": fees, "cells": monotone(load_table(repo / COST_TABLE["path"])), "coverage": coverage,
            "runtime_lock_sha256": sha256_file(lock_path), "runtime_environment_sha256": guards.environment_digest(lock),
            "data_file_sha256s": data,
            "amendment_files": {n: logs.file_state(p) for n, p in amend.items()}, "run_log": run_log,
            "access_log": access_log,
            "main_tip_time": guards.commit_time(repo, tip) if guards.verified_merge(repo, tip) else None}


def check_clock(ctx: dict, now: float) -> None:
    """Review round 10, M2: a holdout decision never uses a local time earlier than the GitHub-recorded time of
    origin/main's tip (a signed merge commit), so setting the clock back below the last push is refused."""
    t = ctx.get("main_tip_time")
    if t is None:
        raise guards.Refused("origin/main's tip is not a signed merge commit: no recorded time bounds the clock")
    if now < t:
        raise guards.Refused("the local clock is earlier than origin/main's tip commit time")


def count_only_context(repo, *, versions=None) -> dict:
    """The pre-freeze count-only and dry-run path: a committed, clean study tree reachable from origin/main, the
    pinned runtime, and a protocol and run log that equal origin/main (review round 10, L1: not only HEAD), with the
    remote's main checked by git ls-remote. The protocol is still a draft here, so require_frozen does not apply;
    the coverage_rule hash is checked by the count-only code before any fetch or read
    (coverage_rule.decided_by_code)."""
    repo = Path(repo)
    guards.check_bytecode_isolated()
    tree = guards.running_tree(repo)
    guards.require_remote_main(repo)
    guards.require_on_main(repo, (PROTOCOL_PATH, RUN_LOG))
    guards.check_append_only_history(repo, (RUN_LOG,))
    for p in (PROTOCOL_PATH, RUN_LOG):
        local = repo / p
        if (local.read_bytes() if local.exists() else None) != guards.committed_bytes(repo, "HEAD", p):
            raise guards.Refused(f"{p} differs from HEAD: the count-only code runs from committed files")
    lock_path = repo / STUDY_PATH / "runtime.lock"
    lock = guards.load_lock(lock_path)
    guards.check_runtime(lock, versions)
    pbytes = (repo / PROTOCOL_PATH).read_bytes()
    return {"repo": repo, "protocol": json.loads(pbytes), "protocol_sha256": sha256_bytes(pbytes), "tree": tree,
            "commit": guards.git(repo, "rev-parse", "HEAD"), "runtime_lock_sha256": sha256_file(lock_path),
            "runtime_environment_sha256": guards.environment_digest(lock), "run_log": logs.read_lines(repo / RUN_LOG)}


# ---------------------------------------------------------------- run-log lines

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
            "protocol_sha256": ctx["protocol_sha256"], "data_file_sha256s": ctx.get("data_file_sha256s", {}),
            "amendment_files": ctx.get("amendment_files", {}), "input_snapshot_sha256s": list(snapshots),
            "status": status, "results_sha256": results_sha256,
            "runtime_environment_sha256": ctx.get("runtime_environment_sha256")}
    line.update(extra or {})
    return line


def results_path(ctx: dict, name: str) -> Path:
    return Path(ctx["repo"]) / RESULTS_DIR / f"{name}.json"


def transport_qualified(ctx: dict, fetch_lines: list) -> bool:
    """outcome_reporting.qualifiers: a stage whose data were fetched or collected under a transport deviation, or
    that runs under one, carries 'transport-deviation'."""
    return ctx.get("transport_deviation") is not None or any(
        x.get("study_tree") not in (None, ctx.get("pinned_tree")) for x in fetch_lines)


# ---------------------------------------------------------------- development and validation

def stage_fetch_run(ctx: dict, stage: str, snapshot_dir, planner, transports, clock) -> dict:
    """The stage's single fetch (phase A, the single re-fetch, phase C), sealed and logged with its rate. A second
    fetch of a stage is refused unless every earlier attempt failed and sealed nothing (review round 9, F1)."""
    from core import driver
    from core.store import Store
    prior = [x for x in ctx["run_log"] if x.get("stage") == stage and x.get("purpose") in ("fetch", "refetch")]
    if any(x.get("status") != "failed" or x.get("input_snapshot_sha256s") for x in prior):
        raise RunRefused(f"{stage} already has a fetch in the run log; a stage is fetched once, with its single "
                         "re-fetch inside that run")
    start, status, sha, rate = clock(), "failed", None, None
    try:
        store = Store()
        res = driver.stage_fetch(planner, transports, store, start[:10], clock=clock)
        sha = store.write(snapshot_dir)
        rate = void_rate(res["incomplete_by_kind"])
        status = "complete"
    finally:
        extra = {"fetch_incomplete_rate": rate["rate"], "fetch_incomplete_by_kind": rate["by_kind"],
                 "stage_void": rate["void"]} if rate else {}
        logs.append_line(ctx["repo"] / RUN_LOG, run_line(
            ctx, stage=stage, purpose="fetch", commit=ctx["commit"], utc_start=start, utc_end=clock(),
            snapshots=[sha] if sha else [], status=status, results_sha256=None, extra=extra))
    return {"snapshot_sha256": sha, "fetch_incomplete_rate": rate["rate"], "void": rate["void"]}


def evaluate_and_write(ctx: dict, *, stage: str, snapshot_sha256: str, vintages: list, freeze_utc: str,
                       compute, results_path, before_write=None) -> dict:
    """compute() returns the results dict, in memory. Nothing is written until every item is computed; a failure
    before the write leaves no results file (the caller logs the run as failed and may retry from the same tree
    and the same sealed inputs)."""
    if logs.results_lines(ctx["run_log"], stage):
        raise RunRefused(f"{stage} already has its governing results file; a second one is refused")
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


def evaluate_run(ctx: dict, stage: str, snapshot_dir, snapshot_sha256: str, compute_for, clock) -> dict:
    """One logged evaluation of a development or validation stage into results/<stage>.json. Refused when the stage
    already has a results file or a results line, when the snapshot is not the one its fetch line sealed, or when
    an earlier failed attempt used another snapshot (review round 9, F1 and M-4). If the run is interrupted after the
    results file is written, the line records that file's sha256 as complete (F10)."""
    from core.store import Store
    path = results_path(ctx, stage)
    if logs.results_lines(ctx["run_log"], stage) or path.exists():
        raise RunRefused(f"{stage} already has its results file; the first one governs and a second is refused")
    fetch_line = fetch_line_for(ctx["run_log"], stage, snapshot_sha256)
    if fetch_line is None or fetch_line.get("status") != "complete":
        raise RunRefused(f"{snapshot_sha256} is not the snapshot sealed by {stage}'s logged fetch")
    earlier = logs.results_attempts(ctx["run_log"], stage)
    if any(x.get("input_snapshot_sha256s") != [snapshot_sha256] for x in earlier):
        raise RunRefused("an earlier attempt of this stage used another snapshot; a retry uses the same sealed inputs")
    store = Store.read(snapshot_dir, snapshot_sha256)
    start, status, digest = clock(), "failed", None
    try:
        out = evaluate_and_write(ctx, stage=stage, snapshot_sha256=snapshot_sha256, vintages=store.vintages(),
                                 freeze_utc=ctx["freeze_utc"], compute=lambda: compute_for(store, fetch_line),
                                 results_path=path)
        status, digest = "complete", out["results_sha256"]
    finally:
        if digest is None and path.exists():
            status, digest = "complete", sha256_file(path)
        logs.append_line(ctx["repo"] / RUN_LOG, run_line(
            ctx, stage=stage, purpose="evaluate", commit=ctx["commit"], utc_start=start, utc_end=clock(),
            snapshots=[snapshot_sha256], status=status, results_sha256=digest,
            extra={"results_path": str(Path(RESULTS_DIR) / path.name)}))
    return {"results_sha256": digest}


def void_from_fetch(incomplete_by_kind: dict) -> dict:
    return void_rate(incomplete_by_kind)
