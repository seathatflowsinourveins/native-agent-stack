"""The transport-deviation reproduction check (run_discipline.transport_deviations; review round 8, R8-1).

A tree that differs from the frozen tree only under study/fetch/ passes only if, against the most recently sealed
snapshot of each request kind (or the pre-freeze native dry run's snapshot, freeze_preconditions):
  (a) plan: the new tree regenerates the request plan from the sealed inputs, and its canonical request records
      equal the sealed request records byte for byte;
  (b) reparse: every sealed raw page, re-parsed offline by the new tree, gives byte-identical normalized records
      (the sealed normalized_sha256 of every page, not a sample);
  (c) live: the new transport re-requests the first 200 requests of each kind, in sha256 order of their request
      records, and their normalized records (every field; the vintage is not part of them) equal the sealed ones.
Parsing and planning are evaluation code outside study/fetch/, so (a) and (b) can fail only if the tree changed
outside study/fetch/; they are kept as mechanical evidence of that.
"""
from __future__ import annotations

import hashlib

from core.canon import dumps
from core.plan import record
from core.store import normalized_sha256


def tree_diff_only_under_fetch(changed_paths: list, fetch_prefix: str) -> bool:
    return all(p.startswith(fetch_prefix.rstrip("/") + "/") for p in changed_paths)


def check_plan(planner, store) -> dict:
    regenerated = "\n".join(sorted(record(r) for r in planner(store))).encode()
    sealed = "\n".join(store.request_records()).encode()
    return {"passes": regenerated == sealed, "sealed_requests": len(store.req),
            "regenerated_sha256": hashlib.sha256(regenerated).hexdigest(),
            "sealed_sha256": hashlib.sha256(sealed).hexdigest()}


def check_reparse(store) -> dict:
    pages, bad = 0, []
    for (key, attempt), digests in sorted(store.page_norm.items()):
        st = store.state[key] if store.state[key]["attempt"] == attempt else \
            next(h for h in store.history.get(key, []) if h["attempt"] == attempt)
        for i, (raw, sealed) in enumerate(zip(st["pages"], digests)):
            pages += 1
            if normalized_sha256(store.req[key]["parser"], raw) != sealed:
                bad.append(f"{key}#{attempt}/{i}")
    return {"passes": pages > 0 and not bad, "pages": pages, "mismatches": bad}


def _merged(req, pages) -> str:
    """The request's merged normalized records, independent of how the transport paginated."""
    from core.store import Store
    tmp = Store()
    tmp.put(req, True, pages, "")
    return dumps(tmp.parsed(req["key"]))


def check_live(store, transports, per_kind: int = 200) -> dict:
    by_kind = {}
    for key, req in store.req.items():
        if store.status(key) == "complete":
            by_kind.setdefault(req["kind"], []).append(req)
    results, bad = {}, []
    for kind, reqs in sorted(by_kind.items()):
        reqs = sorted(reqs, key=lambda r: hashlib.sha256(record(r).encode()).hexdigest())[:per_kind]
        ok = 0
        for req in reqs:
            res = transports[req["api"]].get(req["endpoint"], req["params"])
            if res["complete"] and _merged(req, res["pages"]) == _merged(req, store.state[req["key"]]["pages"]):
                ok += 1
            else:
                bad.append(req["key"])
        results[kind] = {"requested": len(reqs), "equal": ok}
    return {"passes": not bad, "by_kind": results, "mismatches": bad}


def reproduction_check(planner, store, transports, changed_paths: list, fetch_prefix: str) -> dict:
    only_fetch = tree_diff_only_under_fetch(changed_paths, fetch_prefix)
    out = {"only_fetch_changed": only_fetch}
    if not only_fetch:
        out["passes"] = False
        return out
    out["plan"] = check_plan(planner, store)
    out["reparse"] = check_reparse(store)
    out["live"] = check_live(store, transports)
    out["passes"] = out["plan"]["passes"] and out["reparse"]["passes"] and out["live"]["passes"]
    return out
