#!/usr/bin/env python3
"""Command line for the mover v3 core study. Every command that fetches or evaluates data goes through
core.runner.context (after the freeze) or core.runner.count_only_context (the pre-freeze count-only run).

  run.py build-calendar --first 2015-09-01 --last YYYY-MM-DD --out data/session-calendar.json
  run.py count-only --snapshot-root DIR          (pre-freeze, runs once; the rate limit is the protocol's)
  run.py dry-run --sessions D1,D2 --symbols A,B --snapshot-root DIR     (pre-freeze native dry run, runs once)
  run.py fetch --stage development|validation --enumeration ENUM.json --snapshot DIR    (once per stage)
  run.py evaluate --stage development|validation --enumeration ENUM.json --snapshot DIR --sha SHA
                  (first run: the start line; after it is pushed, the evaluation)
  run.py transport-check --stage development|validation --enumeration ENUM.json --snapshot DIR --sha SHA
                  [--holdout-root DIR]   (required once a holdout snapshot is sealed)
  run.py authorize --purpose collect|amend|count|read [--retry-of ID]   (appends the authorization record)
  run.py amend --authorization ID --file calendar|fees --line N          (logs one amendment line)
  run.py collect --authorization ID --last YYYY-MM-DD --accrual-log FILE --snapshot-root DIR
  run.py count --authorization ID --snapshot-root DIR     (holdout count: first run fetches, second counts)
  run.py read --authorization ID --snapshot-root DIR      (the single holdout read: first run fetches, second reads)

Results files have fixed paths under blueprints/us-equities/mover-v3/results/. Every run appends its run-log line
(and a holdout action its completion record); the next run refuses until those lines are committed and pushed.
Run it as `python -I -B run.py` (study/runtime.lock run_command): the script reads no bytecode cache from the tree.
The fetch transport runs in a child process (core/transport_proc.py); this process never imports study/fetch/.
"""
from __future__ import annotations

import sys

if __name__ == "__main__":  # before any study module is imported: no bytecode cache of the tree is read (F9)
    import tempfile
    sys.dont_write_bytecode = True
    sys.pycache_prefix = tempfile.mkdtemp(prefix="mover-v3-pycache-")

import argparse  # noqa: E402
import json  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

REPO = HERE.parents[3]


def transports(protocol: dict) -> dict:
    """The data and trading hosts (the asset master is a trading-API endpoint), served by a child process that alone
    imports study/fetch/ (review round 10, H1), paced at the protocol's pinned rate limit (review round 11, C2; the
    command refuses while it is not pinned)."""
    from core import count_only, transport_proc
    return transport_proc.transports(per_minute=count_only.pinned_rate_limit(protocol)["per_minute"])


def now() -> float:
    return time.time()


def clock() -> str:
    from core.driver import utc_now
    return utc_now()


def _spec(ctx, stage, enumeration):
    from core import guards, stage as ST
    from core.canon import sha256_bytes
    raw = Path(enumeration).read_bytes()
    if sha256_bytes(raw) != ctx["coverage"]["enumeration_sha256"]:
        raise guards.Refused("the enumeration file is not the one the governing count-only output sealed")
    enum = json.loads(raw)
    return ST.StageSpec(stage=stage, cal=ctx["cal"], symbols=enum["symbols"], actions=enum["actions"],
                        active=frozenset(enum.get("active", [])), dropped_years=ctx["coverage"]["dropped_years"],
                        fees=ctx["fees"], cells=ctx["cells"])


def cmd_build_calendar(a) -> int:
    from core import calendar as CAL
    body = CAL.build_calendar(a.first, a.last)
    Path(a.out).write_text(json.dumps(body, indent=1) + "\n")
    return 0


def cmd_count_only(a) -> int:
    """The pre-freeze count-only run (exposure_registry.pre_freeze_access_path; review round 9, M-2 and F8)."""
    from core import calendar as CAL
    from core import count_only, logs, runner
    from core.canon import atomic_write_results, sha256_file
    from core.coverage_rule import checked_thresholds, rule_sha256
    from core.params import COUNT_ONLY_OUTPUT, DATA_DIR, RUN_LOG
    ctx = runner.count_only_context(REPO)
    checked_thresholds(ctx["protocol"])       # before any fetch or read
    rate = count_only.pinned_rate_limit(ctx["protocol"])   # review round 10, L1: pinned before the run
    if any(x.get("purpose") == "count_only" and x.get("status") == "complete" for x in ctx["run_log"]):
        raise runner.RunRefused("the count-only code runs once; a rerun follows only a failed or incomplete run")
    out_path = REPO / COUNT_ONLY_OUTPUT
    if out_path.exists():
        raise runner.RunRefused(f"{COUNT_ONLY_OUTPUT} exists")
    cal = CAL.Calendar.from_files(REPO / DATA_DIR / "session-calendar.json")
    # review round 12, F3: once a failed run has sealed part 1 (the rows its rates come from), a later run keeps its
    # coverage_rule, so a rule is never changed after the rates it would be judged on could have been read
    for x in ctx["run_log"]:
        if x.get("purpose") == "count_only" and "part1" in (x.get("sealed_parts") or ()) and \
                x.get("coverage_rule_sha256") != rule_sha256(ctx["protocol"]):
            raise runner.RunRefused("an earlier count-only run sealed part 1 under another coverage_rule; the rule "
                                    "cannot change after its rates could have been read")
    tr = transports(ctx["protocol"])
    si = runner.begin_or_resume(ctx, "pre_freeze", "count_only",
                                {"coverage_rule_sha256": rule_sha256(ctx["protocol"])}, clock)   # review round 11, F4
    if si is None:
        print(json.dumps({"started": True, "next": "commit and push the start line, then run again"}))
        return 0
    start, status, digest, out, progress = clock(), "failed", None, None, {}
    try:
        out = count_only.run(ctx["protocol"], cal, tr, a.snapshot_root, start[:10], rate["per_minute"],
                             clock=clock, progress=progress)
        out.update({"study_tree": ctx["tree"], "code_revision": ctx["commit"], "rate_limit": rate})
        digest = atomic_write_results(out_path, out)
        status = "complete"
    finally:
        if digest is None and out_path.exists():
            status, digest = "complete", sha256_file(out_path)
        # every part sealed so far, also on a failed run (pre_freeze_access_path.runs; review round 12, F3)
        logs.append_line(REPO / RUN_LOG, runner.run_line(
            ctx, stage="pre_freeze", purpose="count_only", commit=ctx["commit"], utc_start=start, utc_end=clock(),
            snapshots=list(progress.values()), status=status, results_sha256=digest,
            extra={"coverage_rule_sha256": rule_sha256(ctx["protocol"]), "output_path": COUNT_ONLY_OUTPUT,
                   "start_index": si, "sealed_parts": sorted(progress)}))
    print(json.dumps({"output_sha256": digest, "item_rule": out["item_rule"]}, sort_keys=True))
    return 0


def cmd_dry_run(a) -> int:
    """freeze_preconditions: the native dry run of the fetch plumbing on an already exposed window outside every v3
    window, counts only, into results/dry-run-output.json with its run-log line (review round 10, F6)."""
    from core import count_only, logs, runner
    from core import calendar as CAL
    from core.canon import atomic_write_results, sha256_file
    from core.params import DATA_DIR, DRY_RUN_OUTPUT, RUN_LOG
    ctx = runner.count_only_context(REPO)
    sessions, symbols = a.sessions.split(","), a.symbols.split(",")
    count_only.check_dry_run_window(sessions)
    out_path = REPO / DRY_RUN_OUTPUT
    if out_path.exists() or any(x.get("purpose") == "dry_run" and x.get("status") == "complete" for x in ctx["run_log"]):
        raise runner.RunRefused("the native dry run has its output; it runs once")
    cal = CAL.Calendar.from_files(REPO / DATA_DIR / "session-calendar.json")
    count_only.dry_run_requests(cal, sessions, symbols)   # every request's reach, before any fetch or log line (C1)
    tr = transports(ctx["protocol"])                     # the pinned rate limit, before any fetch (C2)
    from core.canon import sha256_obj
    si = runner.begin_or_resume(ctx, "pre_freeze", "dry_run", {"sessions": sessions,
                                                               "symbols_sha256": sha256_obj(symbols)}, clock)  # F4
    if si is None:
        print(json.dumps({"started": True, "next": "commit and push the start line, then run again"}))
        return 0
    start, status, digest, out, progress = clock(), "failed", None, None, {}
    try:
        out = count_only.dry_run(cal, sessions, symbols, tr, a.snapshot_root, start[:10], clock=clock,
                                 progress=progress)
        out.update({"study_tree": ctx["tree"], "code_revision": ctx["commit"]})
        digest = atomic_write_results(out_path, out)
        status = "complete"
    finally:
        if digest is None and out_path.exists():
            status, digest = "complete", sha256_file(out_path)
        logs.append_line(REPO / RUN_LOG, runner.run_line(
            ctx, stage="pre_freeze", purpose="dry_run", commit=ctx["commit"], utc_start=start, utc_end=clock(),
            snapshots=list(progress.values()), status=status, results_sha256=digest,
            extra={"output_path": DRY_RUN_OUTPUT, "sessions": sessions, "symbols_count": len(symbols),
                   "start_index": si}))
    print(json.dumps({"output_sha256": digest}, sort_keys=True))
    return 0


def cmd_transport_check(a) -> int:
    """run_discipline.transport_deviations: the reproduction check of a tree that differs from the pinned tree only
    under study/fetch/, against a stage's sealed snapshot, into results/transport-check-<tree>.json with its run-log
    line. A transport deviation governs only when it cites this output by path and sha256 (review round 10, H1)."""
    from core import guards, logs, runner, stage as ST, transport_check
    from core.canon import atomic_write_results, sha256_file
    from core.params import RESULTS_DIR, RUN_LOG
    from core.store import Store
    ctx = runner.context(REPO, transport_check=True)
    spec = _spec(ctx, a.stage, a.enumeration)
    line = runner.fetch_line_for(ctx["run_log"], a.stage, a.sha)
    if line is None or line.get("status") != "complete":
        raise runner.RunRefused(f"{a.sha} is not the snapshot sealed by {a.stage}'s logged fetch")
    rel = f"{RESULTS_DIR}/transport-check-{ctx['tree'][:12]}.json"
    out_path = REPO / rel
    if out_path.exists():
        raise runner.RunRefused(f"{rel} exists: a tree's reproduction check runs once")
    store = Store.read(a.snapshot, a.sha)
    changed = guards.git(REPO, "diff-tree", "-r", "--name-only", ctx["pinned_tree"], ctx["tree"]).splitlines()
    # review round 11, F3: every sealed holdout snapshot is checked too, and the live sample is seeded by the first
    # origin/main commit that holds the new tree (a signed merge made after the transport was written)
    from core import holdout
    named = bool([r for r in ctx["access_log"] if r.get("record_kind") == "completion" and r.get("snapshot_sha256")]
                 or [x for x in ctx["run_log"] if x.get("stage") == "holdout" and x.get("purpose") in
                     ("count_fetch", "read_fetch") and x.get("input_snapshot_sha256s")])
    if named and not a.holdout_root:
        raise runner.RunRefused("sealed holdout snapshots exist: transport-check needs --holdout-root to check them")
    hstores = holdout.sealed_holdout_snapshots(ctx, a.holdout_root) if a.holdout_root else []
    seed = guards.first_commit_with_tree(REPO, ctx["tree"])
    if seed is None:
        raise runner.RunRefused("the new tree is not yet on origin/main: its first commit there seeds the sample")
    tr = transports(ctx["protocol"])
    start, status, digest = clock(), "failed", None
    try:
        res = transport_check.reproduction_check(ST.planner(spec), store, tr, changed, "fetch", seed=seed,
                                                 holdout_stores=hstores)
        res.update({"kind": "mover_v3_transport_check", "new_tree": ctx["tree"], "pinned_tree": ctx["pinned_tree"],
                    "new_fetch_tree": guards.git(REPO, "rev-parse", f"HEAD:{guards.STUDY_PATH}/fetch"),
                    "stage": a.stage, "snapshot_sha256": a.sha, "changed_paths": changed})
        digest = atomic_write_results(out_path, res)
        status = "complete"
    finally:
        if digest is None and out_path.exists():
            status, digest = "complete", sha256_file(out_path)
        logs.append_line(REPO / RUN_LOG, runner.run_line(
            ctx, stage=a.stage, purpose="transport_check", commit=ctx["commit"], utc_start=start, utc_end=clock(),
            snapshots=[a.sha], status=status, results_sha256=digest, extra={"output_path": rel}))
    print(json.dumps({"output_path": rel, "output_sha256": digest, "passes": res.get("passes")}, sort_keys=True))
    return 0


def cmd_fetch(a) -> int:
    from core import runner, stage as ST
    ctx = runner.context(REPO)
    spec = _spec(ctx, a.stage, a.enumeration)
    out = runner.stage_fetch_run(ctx, a.stage, a.snapshot, ST.planner(spec), transports(ctx["protocol"]), clock)
    print(json.dumps(out, sort_keys=True))
    return 0


def cmd_evaluate(a) -> int:
    from core import runner, stage as ST
    ctx = runner.context(REPO)
    spec = _spec(ctx, a.stage, a.enumeration)
    cov = ctx["coverage"]
    ident = {"rate": cov["identity_unreached_rate_2020"]} if (a.stage == "validation"
                                                               and cov["validation_identity_limited"]) else None
    # review round 10, F4: a committed void deviation (a recorded pre-freeze read) scores every validation item p = 1.
    # Review round 13, F1: only a void that reached origin/main before this stage's evaluate_start line applies
    # (runner.void_effect); one recorded after the freeze is named, and a later one is reported, never applied
    voided = sorted(ctx["voids"] & {"tests", "validation"}) if a.stage == "validation" else []
    void_notes = {"void_deviations_after_freeze": [e for e in ctx["voids_after_freeze"]],
                  "void_deviations_late": [e for e in ctx["voids_late"] if e["scope"] in ("tests", "validation")]} \
        if a.stage == "validation" else {}

    testing = runner.stage_testing(a.stage, cov)     # review round 11, C9: development is not gated by 2020

    def compute_for(store, fetch_line):
        quals = ("transport-deviation",) if runner.transport_qualified(ctx, [fetch_line]) else ()
        res = ST.evaluate_stage(spec, store, ctx["protocol"]["id"], tested=testing["tested"],
                                void={"void": bool(fetch_line.get("stage_void")) or bool(voided),
                                      "rate": fetch_line.get("fetch_incomplete_rate"), "void_deviations": voided,
                                      **void_notes},
                                qualifiers=quals, identity_limited=ident)
        if "development_computed" in testing:
            res["development_computed"] = testing["development_computed"]
        return res
    out = runner.evaluate_run(ctx, a.stage, a.snapshot, a.sha, compute_for, clock)
    print(json.dumps(out, sort_keys=True))
    return 0


def cmd_authorize(a) -> int:
    from core import holdout, runner
    rec = holdout.authorize(runner.context(REPO, amend_pending_ok=a.purpose == "amend"), a.purpose, now(), a.retry_of)
    print(json.dumps(rec, sort_keys=True))
    return 0


def cmd_amend(a) -> int:
    from core import holdout, runner
    rec = holdout.amend(runner.context(REPO, amend_pending_ok=True), a.authorization, a.file, a.line, now())
    print(json.dumps(rec, sort_keys=True))
    return 0


def cmd_collect(a) -> int:
    from core import holdout, runner
    ctx = runner.context(REPO)
    accrual = json.loads(Path(a.accrual_log).read_text())
    out = holdout.collect(ctx, a.authorization, a.last, accrual, a.snapshot_root, transports(ctx["protocol"]), now(),
                          clock)
    print(json.dumps(out, sort_keys=True))
    return 0


def cmd_count(a) -> int:
    from core import holdout, runner
    ctx = runner.context(REPO)
    out = holdout.count(ctx, a.authorization, a.snapshot_root, transports(ctx["protocol"]), now(), clock)
    print(json.dumps(out, sort_keys=True))
    return 0


def cmd_read(a) -> int:
    from core import holdout, runner
    ctx = runner.context(REPO)
    out = holdout.read(ctx, a.authorization, a.snapshot_root, transports(ctx["protocol"]), now(), clock)
    print(json.dumps(out, sort_keys=True))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build-calendar")
    b.add_argument("--first", required=True)
    b.add_argument("--last", required=True)
    b.add_argument("--out", required=True)
    c = sub.add_parser("count-only")
    c.add_argument("--snapshot-root", required=True)
    d = sub.add_parser("dry-run")
    d.add_argument("--sessions", required=True)
    d.add_argument("--symbols", required=True)
    d.add_argument("--snapshot-root", required=True)
    for name in ("fetch", "evaluate", "transport-check"):
        p = sub.add_parser(name)
        p.add_argument("--stage", choices=("development", "validation"), required=True)
        p.add_argument("--enumeration", required=True)
        p.add_argument("--snapshot", required=True)
        if name in ("evaluate", "transport-check"):
            p.add_argument("--sha", required=True)
        if name == "transport-check":
            p.add_argument("--holdout-root", default=None)
    z = sub.add_parser("authorize")
    z.add_argument("--purpose", choices=("collect", "amend", "count", "read"), required=True)
    z.add_argument("--retry-of", default=None)
    m = sub.add_parser("amend")
    m.add_argument("--authorization", required=True)
    m.add_argument("--file", choices=("calendar", "fees"), required=True)
    m.add_argument("--line", type=int, required=True)
    for name in ("collect", "count", "read"):
        p = sub.add_parser(name)
        p.add_argument("--authorization", required=True)
        p.add_argument("--snapshot-root", required=True)
        if name == "collect":
            p.add_argument("--last", required=True)
            p.add_argument("--accrual-log", required=True)
    a = ap.parse_args(argv)
    return {"build-calendar": cmd_build_calendar, "count-only": cmd_count_only, "dry-run": cmd_dry_run,
            "fetch": cmd_fetch, "evaluate": cmd_evaluate, "transport-check": cmd_transport_check,
            "authorize": cmd_authorize, "amend": cmd_amend, "collect": cmd_collect, "count": cmd_count,
            "read": cmd_read}[a.cmd](a)


if __name__ == "__main__":
    raise SystemExit(main())
