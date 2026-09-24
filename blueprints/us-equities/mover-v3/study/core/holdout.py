"""The holdout path (holdout_gate, chronology.holdout; review round 9, H-1, F4 and M-5). run.py is the only caller.

Every holdout action runs in two committed steps. (1) authorize: the evaluator refusals are computed by rule from
the committed logs, and an authorization record (granted or refused, never decided by a person) is appended to the
access log, which is then committed and pushed. (2) The action (collect, count or read) runs only under that
committed granted authorization (gate.require_granted; runner.context refuses an access log that differs from
origin/main), writes its results file atomically at a fixed path, appends its run-log line and appends its
completion record, even when it fails. The window is fixed by the freeze commit alone: N0 is the 40th session after
the freeze session on the pinned, unamended calendar, and the last session counts 252 + 63 x (extension blocks)
actual sessions of the amended calendar, the blocks coming only from committed count results (M-5). A read that is
refused, void, or not completed by 15 sessions after the last session writes the fixed label 'not supported
(holdout not read)' for every carried item (chronology.holdout.read_timing).
"""
from __future__ import annotations

import json
from pathlib import Path

from core import chronology as CH
from core import count_unit as CU
from core import driver, gate, guards, identity, logs, plan
from core import stage as STG
from core import stats as ST
from core.calendar import iso_utc
from core.canon import atomic_write_results, dumps, sha256_bytes, sha256_file
from core.evaluate import void_rate
from core.holdout_store import HoldoutStore
from core.params import ACCESS_LOG, CHRONO, ITEM_IDS, RESULTS_DIR, RUN_LOG, T
from core.store import Store


class HoldoutRefused(Exception):
    pass


# ---------------------------------------------------------------- the window

def window(ctx: dict, blocks: int):
    """(N0, last) after `blocks` extension blocks. N0 keeps the date computed at the freeze on the pinned calendar;
    if an amendment removed it, the holdout starts at the next session (populations.session_calendar)."""
    if ctx["n0_pinned"] is None:
        raise HoldoutRefused("the pinned calendar does not reach N0")
    start = ctx["cal"].next_on_or_after(ctx["n0_pinned"])
    seg = CH.holdout_segment(ctx["cal"], start, blocks) if start else None
    if seg is None:
        raise HoldoutRefused("the pinned calendar does not reach the end of the holdout window")
    return seg


def count_lines(run_log: list) -> list:
    return [x for x in run_log if x.get("stage") == "holdout" and x.get("purpose") == "count" and x.get("results_sha256")]


def blocks_done(run_log: list) -> int:
    return sum(1 for x in count_lines(run_log) if (x.get("extension") or {}).get("extend"))


def final_count(run_log: list):
    done = count_lines(run_log)
    return done[-1] if done and not (done[-1].get("extension") or {}).get("extend") else None


def read_deadline(ctx: dict, last: str) -> float:
    d = ctx["cal"].offset(last, CHRONO["read_deadline_sessions"])
    return ctx["cal"].close(d) if d else float("inf")


def count_due(ctx: dict, now: float) -> bool:
    """Once at the end of the 252 sessions and once at the end of each extension block, until a count decides no
    extension."""
    if final_count(ctx["run_log"]) is not None:
        return False
    _, last = window(ctx, blocks_done(ctx["run_log"]))
    return now >= ctx["cal"].close(last)


def read_due(ctx: dict, now: float) -> bool:
    """After the final count and after the terminal-search windows of censored trades end (5 sessions after the
    last session)."""
    if final_count(ctx["run_log"]) is None:
        return False
    _, last = window(ctx, blocks_done(ctx["run_log"]))
    end = ctx["cal"].offset(last, T["search_sessions"])
    return end is not None and now >= ctx["cal"].close(end)


# ---------------------------------------------------------------- committed state

def first_reach(repo, path: str, ref: str = guards.MAIN):
    """Committer epoch of the first first-parent commit of origin/main that holds path, or None."""
    rows = guards.git(repo, "log", "--first-parent", "--reverse", "--format=%H %ct", ref, "--", path).splitlines()
    for row in rows:
        commit, ct = row.split()
        if guards.committed_bytes(repo, commit, path) is not None:
            guards.require_verified(repo, commit, f"the first commit holding {path}")    # review round 10, M3
            return int(ct)
    return None


def validation_state(ctx: dict) -> dict:
    """The governing validation results file and its run-log line (holdout_gate.evaluator_refusals)."""
    rel = f"{RESULTS_DIR}/validation.json"
    path = Path(ctx["repo"]) / rel
    try:
        gov = logs.governing_results(ctx["run_log"], "validation")
    except logs.AppendOnlyViolation:
        gov = None
    present = path.exists() and gov is not None
    n0, _ = window(ctx, 0)
    reach = first_reach(ctx["repo"], rel)
    return {"present": present, "sha256": sha256_file(path) if path.exists() else None,
            "committed_sha256": (gov or {}).get("results_sha256"),
            "reachable_before_n0": reach is not None and reach < ctx["cal"].at(n0, "09:30"),
            "run_tree": (gov or {}).get("study_tree"), "run_protocol_sha256": (gov or {}).get("protocol_sha256"),
            "results": json.loads(path.read_text()) if present else None}


def batches(ctx: dict) -> list:
    """Completed collection batches: {"authorization_id", "sessions", "snapshot_sha256", "exposed", "reachable"}
    (reachable: when the completion line, which carries the batch's accrual log, reached origin/main)."""
    reach = logs.line_reach(ctx["repo"], ACCESS_LOG)
    lines = {x.get("authorization_id"): x for x in ctx["run_log"]
             if x.get("stage") == "holdout" and x.get("purpose") == "collect" and x.get("status") == "complete"}
    out = []
    for i, rec in enumerate(ctx["access_log"]):
        if rec.get("record_kind") != "completion" or rec.get("status") != "complete":
            continue
        line = lines.get(rec["authorization_id"])
        if line is None:
            continue
        out.append({"authorization_id": rec["authorization_id"], "sessions": line["sessions"],
                    "snapshot_sha256": rec["snapshot_sha256"], "exposed": rec.get("exposed_symbol_sessions") or [],
                    "reachable": reach[i][1] if i < len(reach) else None})
    return out


def sealed_stores(ctx: dict, snapshot_root, purposes=("collect", "count")) -> list:
    """Every sealed snapshot named by a completion of a granted action of these purposes, in access-log order, read
    from <root>/<purpose>-<authorization_id> of the action that sealed it and checked against its sha256 (a retry
    that reused a failed attempt's snapshot names the same sha256, which is read once)."""
    granted = {a["authorization_id"]: a for a in ctx["access_log"]
               if a.get("record_kind") == "authorization" and a.get("decision") == "granted"}
    out, seen = [], set()
    for rec in ctx["access_log"]:
        a = granted.get(rec.get("authorization_id"))
        sha = rec.get("snapshot_sha256")
        if rec.get("record_kind") != "completion" or a is None or a["purpose"] not in purposes or not sha or sha in seen:
            continue
        seen.add(sha)
        out.append(Store.read(Path(snapshot_root) / f"{a['purpose']}-{a['authorization_id']}", sha))
    return out


def enumeration(stores: list) -> dict:
    """The union of every enumeration response held (collection batches refresh it; the first count adds the
    breakpoint screen's), with the latest asset-master response deciding the active set."""
    assets, actions, active, seen = [], [], set(), set()
    for st in stores:
        latest = []
        for key, req in sorted(st.req.items()):
            if st.status(key) != "complete":
                continue
            if req["kind"] == "assets":
                latest.extend(st.parsed(key))
            elif req["kind"] == "corporate_actions":
                for r in st.parsed(key):
                    k = dumps(r)
                    if k not in seen:
                        seen.add(k)
                        actions.append(r)
        if latest:
            assets.extend(latest)
            active = {x["symbol"] for x in latest if x.get("status") == "active"}
    if not assets:
        raise HoldoutRefused("no complete asset-master response: the enumeration is unknown")
    return {"symbols": identity.enumerate_symbols(assets, actions)["symbols"], "actions": actions,
            "active": frozenset(active)}


# ---------------------------------------------------------------- the authorization

def gate_context(ctx: dict, purpose: str, now: float, retry_of=None) -> dict:
    """The evaluator's inputs for gate.evaluator_refusals, every one computed from committed state."""
    seq = gate.sequence(ctx["access_log"])
    voids = ctx.get("voids") or frozenset()
    g = {"purpose": purpose, "protocol_status": ctx["protocol"].get("status"),
         "protocol_sha256": ctx["protocol_sha256"], "frozen_protocol_sha256": ctx["protocol_sha256"],
         "access_log": ctx["access_log"], "retry_of": retry_of, "study_code_tree": ctx["tree"]}
    if purpose in ("collect", "amend"):
        return g
    val = validation_state(ctx)
    complete = gate.validation_complete(val["results"])
    validated = gate.validated_items(val["results"]) if val["results"] and complete else []
    _, last = window(ctx, blocks_done(ctx["run_log"]))
    g.update({"validation_present": val["present"], "validation_sha256": val["sha256"],
              "validation_committed_sha256": val["committed_sha256"], "validation_complete": complete,
              "validation_reachable_before_n0": val["reachable_before_n0"], "validation_run_tree": val["run_tree"],
              "validation_run_protocol_sha256": val["run_protocol_sha256"], "frozen_tree": ctx["pinned_tree"],
              "running_tree": ctx["tree"], "fetch_only_deviation_passed": ctx["transport_deviation"] is not None,
              "runtime_ok": True, "data_files_ok": True, "amendment_refusals": [],   # runner.context refused otherwise
              "validation_void": bool(voids & {"tests", "validation"}), "holdout_void": "holdout" in voids,
              "validated_items": validated, "requested_items": validated,
              "accrual_logs_complete": all(aid in seq["completions"] for aid, a in seq["granted"].items()
                                           if a["purpose"] == "collect"),
              "count_due": count_due(ctx, now), "same_snapshot": True,   # a retry reuses the sealed snapshot
              "before_deadline": now < read_deadline(ctx, last), "count_outputs": list(CU.KEYS)})
    return g


def authorize(ctx: dict, purpose: str, now: float, retry_of=None) -> dict:
    from core.runner import check_clock
    check_clock(ctx, now)
    if purpose == "read" and not read_due(ctx, now):
        _, last = window(ctx, blocks_done(ctx["run_log"]))
        if now < read_deadline(ctx, last):
            raise HoldoutRefused("the read comes after the final count and the last terminal-search window (no "
                                 "authorization is written)")
    g = gate_context(ctx, purpose, now, retry_of)
    n = sum(1 for r in ctx["access_log"] if r.get("record_kind") == "authorization") + 1
    val_sha = g.get("validation_sha256")
    rec = gate.authorization(g, f"{purpose}-{n:03d}", iso_utc(now), {
        "protocol_id": ctx["protocol"]["id"], "protocol_sha256": ctx["protocol_sha256"],
        "code_revision": ctx["commit"], "study_code_tree": ctx["tree"],
        "runtime_lock_sha256": ctx["runtime_lock_sha256"], "data_file_sha256s": ctx["data_file_sha256s"],
        "validation_results_sha256": val_sha})
    logs.append_line(Path(ctx["repo"]) / ACCESS_LOG, rec)
    return rec


def _authorization(ctx: dict, authorization_id: str) -> dict:
    for r in ctx["access_log"]:
        if r.get("record_kind") == "authorization" and r.get("authorization_id") == authorization_id:
            return r
    raise gate.NoAuthorization(f"no committed authorization {authorization_id}")


def authorization_reach(ctx: dict, authorization_id: str):
    """The GitHub-recorded time the authorization record reached origin/main (review round 10, M2)."""
    reach = logs.line_reach(ctx["repo"], ACCESS_LOG)
    for i, r in enumerate(ctx["access_log"]):
        if r.get("record_kind") == "authorization" and r.get("authorization_id") == authorization_id:
            return reach[i][1] if i < len(reach) else None
    return None


def rows_in(store) -> int:
    """Normalized records held by a sealed store's complete requests (the completion's rows_read; review round 10,
    F13)."""
    n = 0
    for key in store.req:
        if store.status(key) != "complete":
            continue
        parsed = store.parsed(key)
        n += len(parsed) if isinstance(parsed, list) else sum(len(v) for v in parsed.values())
    return n


def _finish(ctx, auth_id, start, now, status, sha, rows, digest, exposed, line_extra, snapshots):
    from core.runner import run_line
    logs.append_line(Path(ctx["repo"]) / RUN_LOG, run_line(
        ctx, stage="holdout", purpose=line_extra.pop("purpose"), commit=ctx["commit"], utc_start=start,
        utc_end=iso_utc(now), snapshots=snapshots, status=status, results_sha256=digest,
        extra={"authorization_id": auth_id, **line_extra}))
    logs.append_line(Path(ctx["repo"]) / ACCESS_LOG, gate.completion(auth_id, iso_utc(now), status, sha, rows, digest,
                                                                     exposed))


# ---------------------------------------------------------------- amend (review round 10, F2)

def amend(ctx: dict, authorization_id: str, file_key: str, line: int, now: float) -> dict:
    """Logs one committed amendment line under its granted 'amend' authorization: a completion that cites the file,
    the line index, the line's sha256 and its primary source (session_calendar, cost_model.fees). The line itself
    must already be on origin/main (runner.context), and runner.context refuses any later run while a line has no
    such record, or while its record reached origin/main at or after the line's deadline."""
    from core.runner import AMENDMENT_FILES, check_clock
    from core.params import DATA_DIR
    check_clock(ctx, now)
    gate.require_granted(ctx["access_log"], authorization_id, "amend")
    names = {"calendar": AMENDMENT_FILES[0], "fees": AMENDMENT_FILES[1]}
    if file_key not in names:
        raise HoldoutRefused(f"--file is calendar or fees, not {file_key!r}")
    name = names[file_key]
    raws = logs.raw_lines(Path(ctx["repo"]) / DATA_DIR / name)
    if not 0 <= line < len(raws):
        raise HoldoutRefused(f"{name} has no line {line}")
    rec = json.loads(raws[line])
    if not rec.get("source"):
        raise HoldoutRefused(f"{name} line {line} cites no primary source")
    if (name, line) in logs.amend_records(ctx["access_log"]):
        raise HoldoutRefused(f"{name} line {line} is already logged")
    done = gate.completion(authorization_id, iso_utc(now), "complete", None, 0, None, [])
    done["amendment"] = {"file": name, "line": line, "line_sha256": sha256_bytes(raws[line]), "source": rec["source"]}
    logs.append_line(Path(ctx["repo"]) / ACCESS_LOG, done)
    return done


# ---------------------------------------------------------------- collect

def collect(ctx: dict, authorization_id: str, last: str, accrual: list, snapshot_root, transports, now: float,
            clock=driver.utc_now) -> dict:
    """One collection batch: the enumeration refresh and the screen of every session from the session after the
    previous batch (the freeze session for the first) through `last`, for the whole enumerated list with asof = s,
    plus the rename-day re-fetch. No quote, no minute bar, no membership selection, no outcome."""
    from core.runner import check_clock
    check_clock(ctx, now)
    gate.require_granted(ctx["access_log"], authorization_id, "collect")
    cal, prev = ctx["cal"], batches(ctx)
    first = cal.offset(prev[-1]["sessions"][1], 1) if prev else cal.next_on_or_after(ctx["freeze_session"])
    if not cal.is_session(last) or last < first or cal.close(last) > now:
        raise HoldoutRefused(f"a batch collects closed sessions from {first}; {last} is not one")
    prev_sessions = set(cal.range(*prev[-1]["sessions"])) if prev else set()
    bases = sealed_stores(ctx, snapshot_root, ("collect",))
    fetch_date = iso_utc(now)[:10]
    enum_reqs = plan.assets_requests() + [plan.corporate_actions_request("2016-01-01", fetch_date)]

    def planner(store):
        # each batch refreshes the enumeration itself (the asset-master request has no date, so it is fetched into
        # this batch's own store), united with every earlier batch's list
        if any(not store.has(r["key"]) for r in enum_reqs):
            return enum_reqs
        enum = enumeration([*bases, store])
        renames = [r for r in enum["actions"] if r.get("type") == "name_change" and r.get("date") in prev_sessions]
        return plan.collection_requests(cal, cal.range(first, last), enum["symbols"], renames, fetch_date)

    start, status, sha = iso_utc(now), "failed", None
    store = Store()
    try:
        driver.stage_fetch(planner, transports, store, fetch_date, clock=clock)
        sha = store.write(Path(snapshot_root) / f"collect-{authorization_id}")
        status = "complete"
    finally:
        _finish(ctx, authorization_id, start, now, status, sha, 0, None, list(accrual),
                {"purpose": "collect", "sessions": [first, last]}, [sha] if sha else [])
    return {"snapshot_sha256": sha, "sessions": [first, last], "requests": len(store.req)}


# ---------------------------------------------------------------- count and read

def _setup(ctx: dict, purpose: str, authorization_id: str, snapshot_root):
    auth = gate.require_granted(ctx["access_log"], authorization_id, purpose)
    blocks = blocks_done(ctx["run_log"])
    n0, last = window(ctx, blocks)
    got = batches(ctx)
    collected = {d for b in got for d in ctx["cal"].range(*b["sessions"])}
    missing = [d for d in ctx["cal"].range(ctx["cal"].offset(n0, -1), last) if d not in collected]
    if missing:
        raise HoldoutRefused(f"{len(missing)} holdout screen sessions are in no collection batch (first {missing[0]})")
    late = frozenset(plan.late_collected(ctx["cal"], [{"sessions": ctx["cal"].range(*b["sessions"]),
                                                      "reachable": b["reachable"]} for b in got]))
    exposed = frozenset((e["symbol"], e["session"]) for b in got for e in b["exposed"])
    bases = sealed_stores(ctx, snapshot_root, ("collect", "count"))
    first = [x for x in ctx["run_log"] if x.get("stage") == "holdout" and x.get("enumeration_fetch_date")]
    return auth, blocks, n0, last, late, exposed, bases, first[0]["enumeration_fetch_date"] if first else None


def fetch_line_of(ctx: dict, purpose: str, auth: dict):
    """The committed '<purpose>_fetch' run-log line that sealed this action's snapshot: its own, or, for a retry,
    the one of the authorization it retries (followed back along retry_of). None if no snapshot was sealed."""
    by_id = {r.get("authorization_id"): r for r in ctx["access_log"] if r.get("record_kind") == "authorization"}
    a, seen = auth, set()
    while a is not None and a["authorization_id"] not in seen:
        seen.add(a["authorization_id"])
        for x in ctx["run_log"]:
            if x.get("stage") == "holdout" and x.get("purpose") == f"{purpose}_fetch" and \
                    x.get("authorization_id") == a["authorization_id"] and x.get("status") == "complete" and \
                    x.get("input_snapshot_sha256s"):
                return x
        a = by_id.get(a.get("retry_of")) if a.get("retry_of") else None
    return None


def _planner(spec_for, mode, enum_date):
    enum_reqs = plan.assets_requests() + [plan.corporate_actions_request("2016-01-01", enum_date)]

    def planner(store):
        if any(not store.has(r["key"]) for r in enum_reqs):
            return enum_reqs
        return enum_reqs + STG.planner(spec_for(store), mode)(store)
    return planner


def _fetch_step(ctx, purpose, auth, bases, snapshot_root, spec_for, mode, enum_date, transports, clock, now,
                sessions):
    """Step 1 of a count or read (review round 10, H2): fetch and seal the action's snapshot, and log a
    '<purpose>_fetch' run-log line with its sha256 and fetch-incomplete rate. No outcome is computed. The step
    that computes (step 2) runs only once this line is on origin/main, over this snapshot alone, so a discarded
    local attempt never yields a second draw of provider data after an outcome was seen."""
    start, status, sha, rate = iso_utc(now), "failed", None, None
    planner = _planner(spec_for, mode, enum_date)
    try:
        live = HoldoutStore(bases, Store())
        driver.stage_fetch(planner, transports, live, enum_date, clock=clock)
        sha = live.write(Path(snapshot_root) / f"{purpose}-{auth['authorization_id']}")
        rate = _rate(ctx, HoldoutStore(bases, Store.read(Path(snapshot_root) / f"{purpose}-{auth['authorization_id']}",
                                                         sha)), planner)
        status = "complete"
    finally:
        from core.runner import run_line
        logs.append_line(Path(ctx["repo"]) / RUN_LOG, run_line(
            ctx, stage="holdout", purpose=f"{purpose}_fetch", commit=ctx["commit"], utc_start=start,
            utc_end=iso_utc(now), snapshots=[sha] if sha else [], status=status, results_sha256=None,
            extra={"authorization_id": auth["authorization_id"], "sessions": sessions,
                   "enumeration_fetch_date": enum_date, "snapshot_dir": f"{purpose}-{auth['authorization_id']}",
                   **({"fetch_incomplete_rate": rate["rate"], "fetch_incomplete_by_kind": rate["by_kind"],
                       "stage_void": rate["void"]} if rate else {})}))
        if status != "complete":
            logs.append_line(Path(ctx["repo"]) / ACCESS_LOG,
                             gate.completion(auth["authorization_id"], iso_utc(now), "failed", None, 0, None, []))
    return {"step": "fetch", "snapshot_sha256": sha, "fetch_incomplete_rate": rate["rate"] if rate else None}


def _rate(ctx, sealed, planner) -> dict:
    """The fetch-incomplete rate over the requests the action's own plan required; a collection batch's failed
    screen request makes its symbol-sessions membership-unknown instead (populations.fetch_failures)."""
    guards.check_vintages(sealed.vintages(), ctx["freeze_utc"])
    by_kind = {}
    for r in {r["key"]: r for r in planner(sealed)}.values():
        row = by_kind.setdefault(r["kind"], {"requests": 0, "incomplete": 0})
        row["requests"] += 1
        row["incomplete"] += sealed.status(r["key"]) != "complete"
    return void_rate(by_kind)


def _sealed(ctx, fetch_line, bases, snapshot_root):
    sha = fetch_line["input_snapshot_sha256s"][0]
    return HoldoutStore(bases, Store.read(Path(snapshot_root) / fetch_line["snapshot_dir"], sha)), sha


def _spec_factory(ctx, n0, last, late, exposed, carried):
    def spec_for(store):
        enum = enumeration([*store.bases, store.live])
        return STG.StageSpec(stage="holdout", cal=ctx["cal"], symbols=enum["symbols"], actions=enum["actions"],
                             active=enum["active"], n0=n0, holdout_last=last, fees=ctx["fees"], cells=ctx["cells"],
                             paper_exposed=exposed, late_sessions=late, carried=carried)
    return spec_for


def _validation_reach_utc(ctx):
    t = first_reach(ctx["repo"], f"{RESULTS_DIR}/validation.json")
    return iso_utc(t) if t is not None else None


def count(ctx: dict, authorization_id: str, snapshot_root, transports, now: float, clock=driver.utc_now) -> dict:
    """The holdout 'count' (count_unit only) and the extension decision, into results/holdout-count-<block>.json,
    in two committed steps (review round 10, H2): the first run fetches and seals, the second (after that line is
    pushed) counts over the sealed snapshot."""
    from core.runner import check_clock
    check_clock(ctx, now)
    auth, blocks, n0, last, late, exposed, bases, enum_date = _setup(ctx, "count", authorization_id, snapshot_root)
    carried = tuple(auth["requested_items"])
    enum_date = enum_date or iso_utc(now)[:10]
    path = Path(ctx["repo"]) / RESULTS_DIR / f"holdout-count-{blocks}.json"
    if path.exists():
        raise HoldoutRefused(f"the count of block {blocks} has its results file")
    spec_for = _spec_factory(ctx, n0, last, late, exposed, None)
    fl = fetch_line_of(ctx, "count", auth)
    if fl is None:
        return _fetch_step(ctx, "count", auth, bases, snapshot_root, spec_for, "count", enum_date, transports, clock,
                           now, [n0, last])
    enum_date = fl["enumeration_fetch_date"]
    start, status, sha, digest, ext, void, rows = iso_utc(now), "failed", fl["input_snapshot_sha256s"][0], None, \
        None, None, 0
    try:
        sealed, sha = _sealed(ctx, fl, bases, snapshot_root)
        rate = _rate(ctx, sealed, _planner(spec_for, "count", enum_date))
        rows = sum(rows_in(st) for st in [*sealed.bases, sealed.live])
        counts = STG.count_stage(spec_for(sealed), sealed)
        if "needs" in counts:
            raise HoldoutRefused("the count's plan is not sealed")
        ext, void = CU.extension_decision(counts, carried, blocks), rate["void"]
        digest = atomic_write_results(path, {
            "kind": "mover_v3_holdout_count", "block": blocks, "window": [n0, last], "carried": list(carried),
            "counts": counts, "extension": ext, "fetch_incomplete_rate": rate["rate"], "void": void,
            "protocol_sha256": ctx["protocol_sha256"], "study_tree": ctx["tree"],
            "runtime_lock_sha256": ctx["runtime_lock_sha256"], "input_snapshot_sha256": sha})
        status = "complete"
    finally:
        if digest is None and path.exists():
            body = json.loads(path.read_text())
            status, digest, ext, void = "complete", sha256_file(path), body["extension"], body["void"]
        _finish(ctx, authorization_id, start, now, status, sha, rows, digest, [],
                {"purpose": "count", "sessions": [n0, last], "block": blocks, "extension": ext, "void": void,
                 "enumeration_fetch_date": enum_date, "validation_results_reach_utc": _validation_reach_utc(ctx)},
                [sha])
    return {"results_sha256": digest, "extension": ext, "window": [n0, last]}


def not_read_results(ctx: dict, carried, reason: str) -> dict:
    """chronology.holdout.read_timing and outcome_reporting.rule: the fixed label for every carried item. With no
    carried item (nothing validated) the holdout is never labelled or read (holdout_gate.no_pass): the record holds
    no label and no verdict (review round 10, F8)."""
    base = {"kind": "mover_v3_holdout_read", "stage": "holdout", "read": False, "reason": reason,
            "carried": list(carried), "protocol_sha256": ctx["protocol_sha256"], "study_tree": ctx["tree"],
            "runtime_lock_sha256": ctx["runtime_lock_sha256"]}
    if not carried:
        return {**base, "no_holdout": "nothing validated: the holdout is never labelled or read (holdout_gate.no_pass)"}
    labels = {i: ("not supported (holdout not read)" if i in carried else "not carried") for i in ITEM_IDS}
    return {**base, "labels": labels, "verdicts": ST.hypothesis_verdict("holdout", labels)}


def read(ctx: dict, authorization_id: str, snapshot_root, transports, now: float, clock=driver.utc_now,
         B: int | None = None) -> dict:
    """The single holdout read into results/holdout-read.json, or the not-read labels when its authorization was
    refused, a count or the read's own fetch is void, or the deadline has passed. Two committed steps (review round
    10, H2): the first run fetches and seals the read's snapshot and logs its line; the second, once that line is on
    origin/main, evaluates over that snapshot only. The deadline is judged by recorded times too (M2): the
    authorization and the fetch line must have reached origin/main before it, and the clock may not be earlier than
    origin/main's tip."""
    from core.runner import check_clock
    check_clock(ctx, now)
    auth = _authorization(ctx, authorization_id)
    if auth.get("purpose") != "read":
        raise gate.NoAuthorization(f"{authorization_id} is not a 'read' authorization")
    path = Path(ctx["repo"]) / RESULTS_DIR / "holdout-read.json"
    if path.exists():
        raise HoldoutRefused("the holdout read results file exists: the holdout is read once")
    carried = tuple(auth.get("requested_items") or ())
    _, last = window(ctx, blocks_done(ctx["run_log"]))
    deadline = read_deadline(ctx, last)
    no_final = final_count(ctx["run_log"]) is None
    if no_final and now < deadline:
        raise HoldoutRefused("the read comes after the final count")
    fl = fetch_line_of(ctx, "read", auth) if auth.get("decision") == "granted" else None
    auth_reach = authorization_reach(ctx, authorization_id)
    reason = None
    if auth.get("decision") != "granted":
        reason = f"refused: {auth.get('refusal')}"
    elif no_final:
        reason = "no final holdout count by 15 sessions after the last holdout session (the holdout is void)"
    elif now >= deadline or auth_reach is None or auth_reach >= deadline:
        reason = "not completed by 15 sessions after the last holdout session"
    elif fl is not None and (logs.line_reach_of(ctx["repo"], RUN_LOG, ctx["run_log"].index(fl)) or deadline) >= deadline:
        reason = "the read's fetch reached origin/main after 15 sessions after the last holdout session"
    elif any(x.get("void") for x in count_lines(ctx["run_log"])):
        reason = "a holdout count was void (populations.fetch_failures)"
    elif "holdout" in (ctx.get("voids") or ()):
        reason = "the holdout is void (exposure_registry.update_rule)"
    start, status, sha, digest = iso_utc(now), "failed", None, None
    if reason is not None:
        if auth.get("decision") == "granted":
            gate.require_granted(ctx["access_log"], authorization_id, "read")
        digest = atomic_write_results(path, not_read_results(ctx, carried, reason))
        from core.runner import run_line
        logs.append_line(Path(ctx["repo"]) / RUN_LOG, run_line(
            ctx, stage="holdout", purpose="read", commit=ctx["commit"], utc_start=start, utc_end=iso_utc(now),
            snapshots=[], status="complete", results_sha256=digest,
            extra={"authorization_id": authorization_id, "not_read": reason}))
        if auth.get("decision") == "granted":
            logs.append_line(Path(ctx["repo"]) / ACCESS_LOG,
                             gate.completion(authorization_id, iso_utc(now), "complete", None, 0, digest, []))
        return {"results_sha256": digest, "read": False, "reason": reason}
    auth, blocks, n0, last, late, exposed, bases, enum_date = _setup(ctx, "read", authorization_id, snapshot_root)
    spec_for = _spec_factory(ctx, n0, last, late, exposed, carried)
    if fl is None:
        return _fetch_step(ctx, "read", auth, bases, snapshot_root, spec_for, "plan", enum_date or iso_utc(now)[:10],
                           transports, clock, now, [n0, last])
    val = validation_state(ctx)["results"]
    signs = {"H3-c": ((val or {}).get("items", {}).get("H3-c") or {}).get("estimate")}
    deviated = ctx["transport_deviation"] is not None or any(
        x.get("study_tree") != ctx["pinned_tree"] for x in ctx["run_log"] if x.get("stage") == "holdout")
    sha, rows = fl["input_snapshot_sha256s"][0], 0
    try:
        sealed, sha = _sealed(ctx, fl, bases, snapshot_root)
        rate = _rate(ctx, sealed, _planner(spec_for, "plan", fl["enumeration_fetch_date"]))
        rows = sum(rows_in(st) for st in [*sealed.bases, sealed.live])
        if rate["void"]:
            res = not_read_results(ctx, carried, f"the read's fetch is void (rate {rate['rate']})")
        else:
            res = STG.evaluate_stage(spec_for(sealed), sealed, ctx["protocol"]["id"], carried=carried,
                                     validation_signs=signs, B=B,
                                     qualifiers=("transport-deviation",) if deviated else ())
            res.update({"kind": "mover_v3_holdout_read", "read": True, "window": [n0, last]})
        res.update({"protocol_sha256": ctx["protocol_sha256"], "study_tree": ctx["tree"],
                    "runtime_lock_sha256": ctx["runtime_lock_sha256"], "input_snapshot_sha256": sha,
                    "fetch_incomplete_rate": rate["rate"]})
        digest = atomic_write_results(path, res)
        status = "complete"
    finally:
        if digest is None and path.exists():
            status, digest = "complete", sha256_file(path)
        _finish(ctx, authorization_id, start, now, status, sha, rows, digest, [],
                {"purpose": "read", "sessions": [n0, last],
                 "validation_results_reach_utc": _validation_reach_utc(ctx)}, [sha])
    return {"results_sha256": digest, "read": True}
