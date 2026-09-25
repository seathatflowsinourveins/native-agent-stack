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
from core.calendar import Calendar, check_study_reach, read_amendments
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
    # review round 12, F2 (second review): the code-decided freeze conditions, not only the item rule. Without a
    # passing identity probe and fetch margin the protocol is not frozen as written (pre_freeze_access_path.
    # identity_probe, freeze_preconditions), and the margin holds only at the rate limit the frozen protocol pins
    for key in ("identity_probe", "fetch_margin"):
        if (out.get(key) or {}).get("passes") is not True:
            raise guards.Refused(f"the governing count-only output's {key} does not pass")
    from core.count_only import pinned_rate_limit
    try:
        rate = pinned_rate_limit(protocol)
    except ValueError as exc:
        raise guards.Refused(str(exc)) from exc
    if out.get("rate_limit") != rate:
        raise guards.Refused("the count-only output was decided at a rate limit other than the frozen protocol's "
                             "pre_freeze_access_path.rate_limit")
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
    check_study_reach(pinned)                          # review round 15, N01
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
    # review round 13, F1: a committed void applies only if it reached origin/main before the outcome it would void
    # could have been computed; a later one is reported, never applied
    effect = void_effect(repo, run_log, access_log, freeze_ts) if void_scopes else \
        {"effective": frozenset(), "late": [], "after_freeze": []}
    return {"repo": repo, "protocol": protocol, "protocol_sha256": sha256_bytes(pbytes), "tree": tree,
            "pinned_tree": pinned_tree, "transport_deviation": deviation, "voids": effect["effective"],
            "voids_late": effect["late"], "voids_after_freeze": effect["after_freeze"],
            "commit": guards.git(repo, "rev-parse", "HEAD"), "freeze_commit": freeze_commit, "freeze_ts": freeze_ts,
            "freeze_utc": datetime.fromtimestamp(freeze_ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "freeze_session": freeze_session, "n0_pinned": CH.n0(pinned, freeze_ts), "pinned_cal": pinned,
            "cal": cal, "fees": fees, "cells": monotone(load_table(repo / COST_TABLE["path"])), "coverage": coverage,
            "runtime_lock_sha256": sha256_file(lock_path), "runtime_environment_sha256": guards.environment_digest(lock),
            "data_file_sha256s": data,
            "amendment_files": {n: logs.file_state(p) for n, p in amend.items()}, "run_log": run_log,
            "access_log": access_log,
            "main_tip_time": guards.commit_time(repo, tip) if guards.verified_merge(repo, tip) else None}


def gate_opened(repo, access_log: list):
    """The signed time the holdout gate opened: when the first granted 'count' or 'read' authorization reached
    origin/main, or None (exposure_registry.update_rule, review round 13, F1)."""
    idx = [i for i, r in enumerate(access_log) if r.get("record_kind") == "authorization"
           and r.get("decision") == "granted" and r.get("purpose") in ("count", "read")]
    if not idx:
        return None
    reach = logs.line_reach(repo, ACCESS_LOG)
    return reach[idx[0]][1] if idx[0] < len(reach) else None


def validation_started(repo, run_log: list):
    """The signed time the first 'evaluate_start' (or, failing one, 'evaluate') line of the validation stage reached
    origin/main, or None: from then on a validation outcome may have been computed (review round 13, F1)."""
    idx = [i for i, x in enumerate(run_log) if x.get("stage") == "validation"
           and x.get("purpose") in ("evaluate_start", "evaluate")]
    if not idx:
        return None
    reach = logs.line_reach(repo, RUN_LOG)
    return reach[idx[0]][1] if idx[0] < len(reach) else None


def void_effect(repo, run_log: list, access_log: list, freeze_ts: int) -> dict:
    """exposure_registry.update_rule (review round 13, F1). Which committed void deviations apply, by signed reach
    times, so that no void can be chosen after the outcome it would void was computable:
      'tests' and 'validation' apply (every validation p = 1, so nothing is carried and the holdout never opens) only
      if they reached origin/main before the validation stage's first 'evaluate_start' line did;
      'holdout' applies (count and read authorizations are refused and a read that sealed nothing writes the
      not-read label) only if it reached origin/main before the holdout gate opened (the first granted 'count' or
      'read' authorization reached it) and the read it records (read_utc) is no later than the record and before
      the gate opened.
    A void that does not apply is 'late': it is reported (in results/validation.json if that is written after it,
    in the holdout read's voids_late and in its holdout_label), never applied. An applied 'tests' or 'validation'
    void that reached origin/main after the freeze commit (the rule wants it recorded before the freeze) is named
    in after_freeze. Returns {"effective": frozenset of scopes, "late": [...], "after_freeze": [...]}."""
    from core.calendar import iso_utc, parse_utc
    recs = guards.void_records(repo)
    if not recs:
        return {"effective": frozenset(), "late": [], "after_freeze": []}
    started, opened = validation_started(repo, run_log), gate_opened(repo, access_log)
    effective, late, after_freeze = set(), [], []
    for dev, t in recs:
        scope = dev["scope"]
        entry = {"number": dev.get("number"), "scope": scope, "reach_utc": iso_utc(t)}
        reason = None
        if scope in ("tests", "validation"):
            if started is not None and t >= started:
                reason = "reached origin/main at or after the validation evaluation's start line"
        else:
            read_t = parse_utc(dev["read_utc"])
            if opened is not None and t >= opened:
                reason = "reached origin/main at or after the holdout gate opened"
            elif opened is not None and read_t >= opened:
                reason = "cites a read at or after the holdout gate opened"
            elif read_t > t:
                reason = "cites a read later than its own record"
        if reason is None:
            effective.add(scope)
            if scope != "holdout" and t > freeze_ts:
                after_freeze.append(dict(entry, note="recorded after the freeze commit; the rule wants it before"))
        else:
            late.append(dict(entry, reason=reason))
    return {"effective": frozenset(effective), "late": late, "after_freeze": after_freeze}


DEVELOPMENT_YEARS = (2017, 2018, 2019)     # coverage_rule.item_rule: development_computed (2016 is warm-up)


def stage_testing(stage: str, coverage: dict) -> dict:
    """coverage_rule.item_rule (review round 11, C9): 'no item is tested' when 2020 is dropped binds validation (and
    the holdout) only; development years do not condition testing, because development is descriptive. Development is
    'not computed' (every item underpowered there) only when every development year is dropped."""
    if stage != "development":
        return {"tested": coverage["items_tested"]}
    computed = any(y not in coverage["dropped_years"] for y in DEVELOPMENT_YEARS)
    return {"tested": computed, "development_computed": computed}


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
    guards.check_parameters(json.loads(pbytes))        # review round 11, C4: study_code.rule, before any fetch
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


def open_start(run_log: list, stage: str, purpose: str):
    """(index, line) of the latest '<purpose>_start' line of this stage that no end line (purpose, start_index)
    cites, or None (review round 11, F4)."""
    ended = {x.get("start_index") for x in run_log if x.get("stage") == stage and x.get("purpose") == purpose}
    starts = [(i, x) for i, x in enumerate(run_log) if x.get("stage") == stage and x.get("purpose") == f"{purpose}_start"
              and i not in ended]
    return starts[-1] if starts else None


def begin_or_resume(ctx: dict, stage: str, purpose: str, identity: dict, clock):
    """Review round 11, F4: a fetching run (count-only, dry-run, a stage fetch) runs in two committed steps, like a
    holdout count or read. The first call appends a '<purpose>_start' line naming the protocol sha256, the study
    tree and `identity` (for count-only the coverage_rule sha256) and returns None: nothing is fetched until that
    line is on origin/main (the caller's context refuses a run log that differs from it). The next call runs under
    that open start and returns its index, which the end line cites. While a start has no end line, a run whose
    protocol, tree or identity differs is refused, so a discarded local attempt cannot be followed by a changed
    rule without a pushed end line, and every start is a logged exposure."""
    ob = open_start(ctx["run_log"], stage, purpose)
    if ob is None:
        t = clock()
        logs.append_line(Path(ctx["repo"]) / RUN_LOG, run_line(
            ctx, stage=stage, purpose=f"{purpose}_start", commit=ctx["commit"], utc_start=t, utc_end=t, snapshots=[],
            status="started", results_sha256=None, extra=dict(identity)))
        return None
    i, line = ob
    now = {"study_tree": ctx["tree"], "protocol_sha256": ctx["protocol_sha256"], **identity}
    diff = sorted(k for k, v in now.items() if line.get(k) != v)
    if diff:
        raise RunRefused(f"run-log line {i} started a {purpose} run with other {', '.join(diff)} and has no end "
                         "line; a new start is refused until it ends")
    return i


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
    si = begin_or_resume(ctx, stage, "fetch", {}, clock)          # review round 11, F4
    if si is None:
        return {"started": True, "next": "commit and push the start line, then run the fetch again"}
    # review round 14, F3: a sealed ledger that no committed fetch line names is a discarded local attempt
    if (Path(snapshot_dir) / "ledger.jsonl").exists():
        raise RunRefused(f"{snapshot_dir} holds a sealed snapshot that no committed fetch line names: a discarded "
                         "attempt is not fetched again")
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
        extra["start_index"] = si
        logs.append_line(ctx["repo"] / RUN_LOG, run_line(
            ctx, stage=stage, purpose="fetch", commit=ctx["commit"], utc_start=start, utc_end=clock(),
            snapshots=[sha] if sha else [], status=status, results_sha256=None, extra=extra))
    return {"snapshot_sha256": sha, "fetch_incomplete_rate": rate["rate"], "void": rate["void"]}


def evaluate_and_write(ctx: dict, *, stage: str, snapshot_sha256: str, vintages: list, freeze_utc: str,
                       compute, results_path, before_write=None, replace_uncited: str | None = None) -> dict:
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
    digest = atomic_write_results(results_path, results, replace_uncited)
    return {"results_sha256": digest}


def evaluate_run(ctx: dict, stage: str, snapshot_dir, snapshot_sha256: str, compute_for, clock) -> dict:
    """One logged evaluation of a development or validation stage into results/<stage>.json. Refused when the stage
    already has a results file or a results line, when the snapshot is not the one its fetch line sealed, or when
    an earlier failed attempt used another snapshot (review round 9, F1 and M-4). If the run is interrupted after the
    results file is written, the line records that file's sha256 as complete (F10). Two committed steps (review
    round 13, F1): an 'evaluate_start' line first, then the evaluation under it.

    Review round 14, Codex P2: a hard termination (SIGKILL, power loss) between the results rename and the line
    leaves a file no line cites. It never governs; the next run under the open start recomputes from the same sealed
    snapshot, replaces that file, and its line records the replaced sha256 (replaced_uncited_results_sha256)."""
    from core.store import Store
    path = results_path(ctx, stage)
    if logs.results_lines(ctx["run_log"], stage):
        raise RunRefused(f"{stage} already has its results file; the first one governs and a second is refused")
    orphan = sha256_file(path) if path.exists() else None
    fetch_line = fetch_line_for(ctx["run_log"], stage, snapshot_sha256)
    if fetch_line is None or fetch_line.get("status") != "complete":
        raise RunRefused(f"{snapshot_sha256} is not the snapshot sealed by {stage}'s logged fetch")
    # review round 11, F3: validation is fetched and sealed before any development outcome exists, so no transport
    # deviation can be written after the development results are seen and before the validation fetch
    if stage == "development" and not any(x.get("stage") == "validation" and x.get("purpose") in ("fetch", "refetch")
                                          and x.get("status") == "complete" and x.get("input_snapshot_sha256s")
                                          for x in ctx["run_log"]):
        raise RunRefused("development is evaluated only after validation's complete fetch line is on origin/main")
    earlier = logs.results_attempts(ctx["run_log"], stage)
    if any(x.get("input_snapshot_sha256s") != [snapshot_sha256] for x in earlier):
        raise RunRefused("an earlier attempt of this stage used another snapshot; a retry uses the same sealed inputs")
    store = Store.read(snapshot_dir, snapshot_sha256)
    # review round 13, F1: an evaluation runs in two committed steps, like a fetch. The first call appends an
    # 'evaluate_start' line and computes nothing; the evaluation runs only once that line is on origin/main, so every
    # attempt that could have computed an outcome is a logged exposure with a signed time (void_effect)
    si = begin_or_resume(ctx, stage, "evaluate", {"snapshot_sha256": snapshot_sha256}, clock)
    if si is None:
        return {"started": True, "next": "commit and push the start line, then run the evaluation again"}
    start, status, digest = clock(), "failed", None
    try:
        out = evaluate_and_write(ctx, stage=stage, snapshot_sha256=snapshot_sha256, vintages=store.vintages(),
                                 freeze_utc=ctx["freeze_utc"], compute=lambda: compute_for(store, fetch_line),
                                 results_path=path, replace_uncited=orphan)
        status, digest = "complete", out["results_sha256"]
    finally:
        if digest is None and path.exists() and sha256_file(path) != orphan:
            status, digest = "complete", sha256_file(path)
        logs.append_line(ctx["repo"] / RUN_LOG, run_line(
            ctx, stage=stage, purpose="evaluate", commit=ctx["commit"], utc_start=start, utc_end=clock(),
            snapshots=[snapshot_sha256], status=status, results_sha256=digest,
            extra={"results_path": str(Path(RESULTS_DIR) / path.name), "start_index": si,
                   **({"replaced_uncited_results_sha256": orphan} if orphan else {})}))
    return {"results_sha256": digest}


def void_from_fetch(incomplete_by_kind: dict) -> dict:
    return void_rate(incomplete_by_kind)
