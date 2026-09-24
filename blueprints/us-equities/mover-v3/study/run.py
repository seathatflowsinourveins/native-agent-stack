#!/usr/bin/env python3
"""Command line for the mover v3 core study. Every command that fetches or evaluates stage data refuses unless the
protocol is frozen and the running study tree is the frozen one (core.runner.context).

  run.py build-calendar --first 2015-09-01 --last YYYY-MM-DD --out data/session-calendar.json
  run.py enumerate --snapshot DIR --sha SHA --out ENUM.json            (part 0 -> the sealed symbol list)
  run.py fetch --stage development|validation --enumeration ENUM.json --snapshot DIR
  run.py evaluate --stage development|validation --enumeration ENUM.json --snapshot DIR --sha SHA --results OUT
  run.py count --enumeration ENUM.json --snapshot DIR --n0 N0 --last LAST   (holdout count, integers only)

Pre-freeze count-only runs use core.count_only directly from the committed tree; they refuse if coverage_rule
hashes differently from core.params.COVERAGE_RULE_SHA256.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from core import calendar as CAL  # noqa: E402
from core.params import DATA_DIR, RUN_LOG  # noqa: E402

REPO = HERE.parents[3]


def _spec(a, ctx, stage):
    from core import costs, stage as ST
    enum = json.loads(Path(a.enumeration).read_text())
    cal = CAL.Calendar.from_files(REPO / DATA_DIR / "session-calendar.json",
                                  REPO / DATA_DIR / "session-calendar-amendments.jsonl")
    fees = costs.Fees.from_files(REPO / DATA_DIR / "fees-v3.json", REPO / DATA_DIR / "fees-v3-amendments.jsonl")
    cells = costs.monotone(costs.load_table(REPO / "blueprints/us-equities/mover-early-entry/evidence/cost-table-run-v1.json"))
    dropped = frozenset(ctx["protocol"].get("coverage_decision", {}).get("dropped_years", []))
    return ST.StageSpec(stage=stage, cal=cal, symbols=enum["symbols"], actions=enum["actions"],
                        active=frozenset(enum.get("active", [])), dropped_years=dropped, fees=fees, cells=cells,
                        n0=getattr(a, "n0", None), holdout_last=getattr(a, "last", None))


def cmd_build_calendar(a) -> int:
    body = CAL.build_calendar(a.first, a.last)
    Path(a.out).write_text(json.dumps(body, indent=1) + "\n")
    return 0


def cmd_enumerate(a) -> int:
    from core import identity
    from core.store import Store
    store = Store.read(a.snapshot, a.sha)
    assets, actions = [], []
    for key, req in store.req.items():
        if store.status(key) != "complete":
            raise SystemExit(f"enumeration request {key} is incomplete")
        if req["kind"] == "assets":
            assets.extend(store.parsed(key))
        elif req["kind"] == "corporate_actions":
            actions.extend(store.parsed(key))
    enum = identity.enumerate_symbols(assets, actions)
    out = {"symbols": enum["symbols"], "counts": enum["counts"], "actions": actions,
           "active": sorted(x["symbol"] for x in assets if x.get("status") == "active"), "part0_sha256": a.sha}
    Path(a.out).write_text(json.dumps(out, sort_keys=True) + "\n")
    print(json.dumps(enum["counts"]))
    return 0


def cmd_fetch(a) -> int:
    from core import driver, logs, runner, stage as ST
    from core.store import Store
    from fetch.transport import Transport
    ctx = runner.context(REPO)
    spec = _spec(a, ctx, a.stage)
    store = Store()
    start = driver.utc_now()
    res = driver.stage_fetch(ST.planner(spec), {"data": Transport()}, store, start[:10])
    sha = store.write(a.snapshot)
    rate = runner.void_from_fetch(res["incomplete_by_kind"])
    logs.append_line(REPO / RUN_LOG, runner.run_line(
        ctx, stage=a.stage, purpose="fetch", commit=runner.guards.git(REPO, "rev-parse", "HEAD"), utc_start=start,
        utc_end=driver.utc_now(), snapshots=[sha], status="complete", results_sha256=None,
        extra={"fetch_incomplete_rate": rate["rate"], "fetch_incomplete_by_kind": rate["by_kind"],
               "stage_void": rate["void"]}))
    print(json.dumps({"snapshot_sha256": sha, "fetch_incomplete_rate": rate["rate"], "void": rate["void"]}))
    return 0


def cmd_evaluate(a) -> int:
    from core import driver, logs, runner, stage as ST
    from core.store import Store
    ctx = runner.context(REPO)
    spec = _spec(a, ctx, a.stage)
    store = Store.read(a.snapshot, a.sha)
    line = runner.fetch_line_for(ctx["run_log"], a.stage, a.sha) or {}
    tested = ctx["protocol"].get("coverage_decision", {}).get("items_tested", False)
    start = driver.utc_now()
    status, digest = "failed", None
    try:
        out = runner.evaluate_and_write(
            ctx, stage=a.stage, snapshot_sha256=a.sha, vintages=store.vintages(),
            freeze_utc=runner.guards.freeze_commit_utc(REPO),
            compute=lambda: ST.evaluate_stage(spec, store, ctx["protocol"]["id"], tested=tested,
                                              void={"void": bool(line.get("stage_void")),
                                                    "rate": line.get("fetch_incomplete_rate")}),
            results_path=a.results)
        status, digest = "complete", out["results_sha256"]
    finally:
        logs.append_line(REPO / RUN_LOG, runner.run_line(
            ctx, stage=a.stage, purpose="evaluate", commit=runner.guards.git(REPO, "rev-parse", "HEAD"),
            utc_start=start, utc_end=driver.utc_now(), snapshots=[a.sha], status=status, results_sha256=digest))
    print(json.dumps({"results_sha256": digest}))
    return 0


def cmd_count(a) -> int:
    from core import runner, stage as ST
    from core.store import Store
    ctx = runner.context(REPO)
    spec = _spec(a, ctx, "holdout")
    counts = ST.count_stage(spec, Store.read(a.snapshot, a.sha))
    print(json.dumps(counts, sort_keys=True))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build-calendar")
    b.add_argument("--first", required=True)
    b.add_argument("--last", required=True)
    b.add_argument("--out", required=True)
    e = sub.add_parser("enumerate")
    e.add_argument("--snapshot", required=True)
    e.add_argument("--sha", required=True)
    e.add_argument("--out", required=True)
    for name in ("fetch", "evaluate", "count"):
        p = sub.add_parser(name)
        p.add_argument("--enumeration", required=True)
        p.add_argument("--snapshot", required=True)
        if name != "count":
            p.add_argument("--stage", choices=("development", "validation"), required=True)
        if name in ("evaluate", "count"):
            p.add_argument("--sha", required=True)
        if name == "evaluate":
            p.add_argument("--results", required=True)
        if name == "count":
            p.add_argument("--n0", required=True)
            p.add_argument("--last", required=True)
    a = ap.parse_args(argv)
    return {"build-calendar": cmd_build_calendar, "enumerate": cmd_enumerate, "fetch": cmd_fetch,
            "evaluate": cmd_evaluate, "count": cmd_count}[a.cmd](a)


if __name__ == "__main__":
    raise SystemExit(main())
