"""The fetch loop (run_discipline.fetch): plan from sealed inputs, hand each request to the transport, record the
pages, repeat until the plan adds nothing, re-fetch the incomplete requests once, and seal.

The loop, the plan and the records are evaluation code; only transport.get (study/fetch/) moves bytes.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

from core.identity import check_asof


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _fetch(req, transports, store, vintage, attempt):
    # CPython 3.13.15 Lib/timeit.py: retain the elapsed interval through the final operation's completion.
    started = time.perf_counter()
    res = transports[req["api"]].get(req["endpoint"], req["params"])
    elapsed = time.perf_counter() - started
    store.put(req, res["complete"], res["pages"], vintage, attempt=attempt, error=res["error"],
              elapsed_seconds=elapsed)


def to_fixpoint(planner, transports, store, fetch_date: str, clock=utc_now, max_rounds: int = 10_000) -> int:
    """Fetch every planned request not yet in the store until the plan is stable. Returns requests fetched."""
    n = 0
    for _ in range(max_rounds):
        new = [r for r in planner(store) if not store.has(r["key"])]
        if not new:
            return n
        for req in sorted({r["key"]: r for r in new}.values(), key=lambda r: r["key"]):
            check_asof(req)
            _fetch(req, transports, store, clock(), attempt=0)
            n += 1
    raise RuntimeError("the plan did not reach a fixpoint")


def refetch_once(transports, store, clock=utc_now) -> int:
    """The single re-fetch: only the requests that are incomplete now, once (attempt 1)."""
    keys = sorted(k for k in store.state if store.status(k) == "incomplete" and store.state[k]["attempt"] == 0)
    for k in keys:
        _fetch(store.req[k], transports, store, clock(), attempt=1)
    return len(keys)


def stage_fetch(planner, transports, store, fetch_date: str, clock=utc_now) -> dict:
    """Phase A to fixpoint, the single re-fetch, phase C to fixpoint (new windows that became plannable). The
    returned rate is committed in the run log before any outcome of the stage."""
    a = to_fixpoint(planner, transports, store, fetch_date, clock)
    r = refetch_once(transports, store, clock)
    c = to_fixpoint(planner, transports, store, fetch_date, clock)
    return {"fetched": a + c, "refetched": r, "incomplete_by_kind": store.incomplete_by_kind()}
