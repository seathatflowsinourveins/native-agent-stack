#!/usr/bin/env python3
"""Command line for the mover v3 core study. Every command that fetches or evaluates data goes through
core.runner.context (after the freeze) or core.runner.count_only_context (the pre-freeze count-only run).

  run.py build-calendar --first 2015-09-01 --last YYYY-MM-DD --out data/session-calendar.json
  run.py count-only --snapshot-root DIR --rate-per-minute N --rate-source TEXT          (pre-freeze, runs once)
  run.py fetch --stage development|validation --enumeration ENUM.json --snapshot DIR    (once per stage)
  run.py evaluate --stage development|validation --enumeration ENUM.json --snapshot DIR --sha SHA
  run.py authorize --purpose collect|count|read [--retry-of ID]          (appends the authorization record)
  run.py collect --authorization ID --last YYYY-MM-DD --accrual-log FILE --snapshot-root DIR
  run.py count --authorization ID --snapshot-root DIR                    (holdout count, integers only)
  run.py read --authorization ID --snapshot-root DIR                     (the single holdout read)

Results files have fixed paths under blueprints/us-equities/mover-v3/results/. Every run appends its run-log line
(and a holdout action its completion record); the next run refuses until those lines are committed and pushed.
Run it as `python -I -B run.py` (study/runtime.lock run_command): the script reads no bytecode cache from the tree.
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


def transports() -> dict:
    """The data and trading hosts (the asset master is a trading-API endpoint)."""
    from fetch.transport import TRADING_HOST, Transport
    return {"data": Transport(), "trading": Transport(host=TRADING_HOST)}


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
    if any(x.get("purpose") == "count_only" and x.get("status") == "complete" for x in ctx["run_log"]):
        raise runner.RunRefused("the count-only code runs once; a rerun follows only a failed or incomplete run")
    out_path = REPO / COUNT_ONLY_OUTPUT
    if out_path.exists():
        raise runner.RunRefused(f"{COUNT_ONLY_OUTPUT} exists")
    cal = CAL.Calendar.from_files(REPO / DATA_DIR / "session-calendar.json")
    start, status, digest, out = clock(), "failed", None, None
    try:
        out = count_only.run(ctx["protocol"], cal, transports(), a.snapshot_root, start[:10], a.rate_per_minute,
                             clock=clock)
        out.update({"study_tree": ctx["tree"], "code_revision": ctx["commit"],
                    "rate_limit": {"per_minute": a.rate_per_minute, "source": a.rate_source}})
        digest = atomic_write_results(out_path, out)
        status = "complete"
    finally:
        if digest is None and out_path.exists():
            status, digest = "complete", sha256_file(out_path)
        logs.append_line(REPO / RUN_LOG, runner.run_line(
            ctx, stage="pre_freeze", purpose="count_only", commit=ctx["commit"], utc_start=start, utc_end=clock(),
            snapshots=list((out or {}).get("snapshots", {}).values()), status=status, results_sha256=digest,
            extra={"coverage_rule_sha256": rule_sha256(ctx["protocol"]), "output_path": COUNT_ONLY_OUTPUT}))
    print(json.dumps({"output_sha256": digest, "item_rule": out["item_rule"]}, sort_keys=True))
    return 0


def cmd_fetch(a) -> int:
    from core import runner, stage as ST
    ctx = runner.context(REPO)
    spec = _spec(ctx, a.stage, a.enumeration)
    out = runner.stage_fetch_run(ctx, a.stage, a.snapshot, ST.planner(spec), transports(), clock)
    print(json.dumps(out, sort_keys=True))
    return 0


def cmd_evaluate(a) -> int:
    from core import runner, stage as ST
    ctx = runner.context(REPO)
    spec = _spec(ctx, a.stage, a.enumeration)
    cov = ctx["coverage"]
    ident = {"rate": cov["identity_unreached_rate_2020"]} if (a.stage == "validation"
                                                               and cov["validation_identity_limited"]) else None

    def compute_for(store, fetch_line):
        quals = ("transport-deviation",) if runner.transport_qualified(ctx, [fetch_line]) else ()
        return ST.evaluate_stage(spec, store, ctx["protocol"]["id"], tested=cov["items_tested"],
                                 void={"void": bool(fetch_line.get("stage_void")),
                                       "rate": fetch_line.get("fetch_incomplete_rate")},
                                 qualifiers=quals, identity_limited=ident)
    out = runner.evaluate_run(ctx, a.stage, a.snapshot, a.sha, compute_for, clock)
    print(json.dumps(out, sort_keys=True))
    return 0


def cmd_authorize(a) -> int:
    from core import holdout, runner
    rec = holdout.authorize(runner.context(REPO), a.purpose, now(), a.retry_of)
    print(json.dumps(rec, sort_keys=True))
    return 0


def cmd_collect(a) -> int:
    from core import holdout, runner
    ctx = runner.context(REPO)
    accrual = json.loads(Path(a.accrual_log).read_text())
    out = holdout.collect(ctx, a.authorization, a.last, accrual, a.snapshot_root, transports(), now(), clock)
    print(json.dumps(out, sort_keys=True))
    return 0


def cmd_count(a) -> int:
    from core import holdout, runner
    out = holdout.count(runner.context(REPO), a.authorization, a.snapshot_root, transports(), now(), clock)
    print(json.dumps(out, sort_keys=True))
    return 0


def cmd_read(a) -> int:
    from core import holdout, runner
    out = holdout.read(runner.context(REPO), a.authorization, a.snapshot_root, transports(), now(), clock)
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
    c.add_argument("--rate-per-minute", type=float, required=True)
    c.add_argument("--rate-source", required=True)
    for name in ("fetch", "evaluate"):
        p = sub.add_parser(name)
        p.add_argument("--stage", choices=("development", "validation"), required=True)
        p.add_argument("--enumeration", required=True)
        p.add_argument("--snapshot", required=True)
        if name == "evaluate":
            p.add_argument("--sha", required=True)
    z = sub.add_parser("authorize")
    z.add_argument("--purpose", choices=("collect", "count", "read"), required=True)
    z.add_argument("--retry-of", default=None)
    for name in ("collect", "count", "read"):
        p = sub.add_parser(name)
        p.add_argument("--authorization", required=True)
        p.add_argument("--snapshot-root", required=True)
        if name == "collect":
            p.add_argument("--last", required=True)
            p.add_argument("--accrual-log", required=True)
    a = ap.parse_args(argv)
    return {"build-calendar": cmd_build_calendar, "count-only": cmd_count_only, "fetch": cmd_fetch,
            "evaluate": cmd_evaluate, "authorize": cmd_authorize, "collect": cmd_collect, "count": cmd_count,
            "read": cmd_read}[a.cmd](a)


if __name__ == "__main__":
    raise SystemExit(main())
