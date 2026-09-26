"""The transport-deviation reproduction check (run_discipline.transport_deviations; review round 8, R8-1).

A tree that differs from the frozen tree only under study/fetch/ passes only if, against the most recently sealed
snapshot of each request kind (or the pre-freeze native dry run's snapshot, freeze_preconditions):
  (a) plan: the new tree regenerates the request plan from the sealed inputs, and its canonical request records
      equal the sealed request records byte for byte;
  (b) reparse: every sealed raw page, re-parsed offline by the new tree, gives byte-identical normalized records
      (the sealed normalized_sha256 of every page, not a sample);
  (c) live: the new transport re-requests 200 requests of each kind, the first in sha256 order of the seed
      followed by their request records, and their normalized records (every field; the vintage is not part of
      them) equal the sealed ones. Review round 11, F3: the seed is the id of the first origin/main commit holding
      the new tree, a signed merge made after the transport was written, so the sample cannot be known when the
      transport is written; with no seed the order is the plain sha256 order of the records.
Parsing and planning are evaluation code outside study/fetch/, so (a) and (b) can fail only if the tree changed
outside study/fetch/; they are kept as mechanical evidence of that. (b) and (c) also run against every sealed
holdout snapshot (collection batches, count and read snapshots; run.py transport-check --holdout-root).
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


def sample_order(req: dict, seed: str | None = None) -> str:
    return hashlib.sha256(((seed + "\n") if seed else "").encode() + record(req).encode()).hexdigest()


def live_sample(store, per_kind: int = 200, seed: str | None = None) -> list:
    """The requests (c) re-requests: per kind, the first per_kind complete requests in sample_order."""
    by_kind = {}
    for key, req in store.req.items():
        if store.status(key) == "complete":
            by_kind.setdefault(req["kind"], []).append(req)
    return [(kind, sorted(reqs, key=lambda r: sample_order(r, seed))[:per_kind]) for kind, reqs in sorted(by_kind.items())]


def fetch_live(store, transports, per_kind: int = 200, seed: str | None = None, clock=None):
    """Review round 15, N02 (R14-open-2): the live sample fetched through the new transport into its own Store, so
    it can be sealed and the check recomputed from the seal instead of drawing the sample again."""
    from core.driver import utc_now
    from core.store import Store
    live = Store()
    for _, reqs in live_sample(store, per_kind, seed):
        for req in reqs:
            res = transports[req["api"]].get(req["endpoint"], req["params"])
            live.put(req, res["complete"], res["pages"], (clock or utc_now)(), error=res.get("error"))
    return live


def compare_live(store, live, per_kind: int = 200, seed: str | None = None) -> dict:
    """(c) from a live sample already held (fetched now, or read back from its seal)."""
    results, bad = {}, []
    for kind, reqs in live_sample(store, per_kind, seed):
        ok = 0
        for req in reqs:
            if live.status(req["key"]) == "complete" and \
                    _merged(req, live.state[req["key"]]["pages"]) == _merged(req, store.state[req["key"]]["pages"]):
                ok += 1
            else:
                bad.append(req["key"])
        results[kind] = {"requested": len(reqs), "equal": ok}
    return {"passes": not bad, "by_kind": results, "mismatches": bad, "seed": seed}


def check_live(store, transports, per_kind: int = 200, seed: str | None = None) -> dict:
    return compare_live(store, fetch_live(store, transports, per_kind, seed), per_kind, seed)


def _combine(out: dict) -> dict:
    out["passes"] = out["plan"]["passes"] and out["reparse"]["passes"] and out["live"]["passes"] and all(
        h["reparse"]["passes"] and h["live"]["passes"] for h in out["holdout"].values())
    return out


def reproduction_from_sealed(planner, store, changed_paths: list, fetch_prefix: str, seed, holdout_stores,
                             live_root, live_shas: dict) -> dict:
    """The check from sealed inputs only: the stage snapshot, every holdout snapshot and each one's sealed live
    sample (<live_root>/<label>, label 'stage' for the stage snapshot), read back against live_shas. run.py
    transport-check computes every output this way, and recomputes it to adopt an output that a hard kill left
    with no run-log line (review round 15, N02 / R14-open-2)."""
    from pathlib import Path
    from core.store import Store
    only_fetch = tree_diff_only_under_fetch(changed_paths, fetch_prefix)
    out = {"only_fetch_changed": only_fetch}
    if not only_fetch:
        out["passes"] = False
        return out
    out["plan"] = check_plan(planner, store)
    out["reparse"] = check_reparse(store)
    out["live"] = compare_live(store, Store.read(Path(live_root) / "stage", live_shas["stage"]), seed=seed)
    out["holdout"] = {}
    for label, st in holdout_stores:
        live = Store.read(Path(live_root) / label, live_shas[label])
        out["holdout"][label] = {"reparse": check_reparse(st), "live": compare_live(st, live, seed=seed)}
    out["live_snapshots"] = dict(sorted(live_shas.items()))
    return _combine(out)


def seal_live_samples(store, transports, seed, holdout_stores, live_root, clock=None) -> dict:
    """{label: sha256} of each snapshot's sealed live sample. A label whose sample is already sealed under live_root
    (a run killed after sealing it) is validated and recovered only for the same source and seeded requests,
    never fetched again, so a sample is drawn at most once."""
    from pathlib import Path
    from core.canon import sha256_bytes, sha256_file
    from core.store import SealError, Store
    shas = {}
    for label, st in [("stage", store), *holdout_stores]:
        d = Path(live_root) / label
        # Bind the source's requests and sealed attempts (raw-page digests, not parsed outcomes), as collect's
        # base_snapshots bind its inputs. Follow core.holdout.collect's recovery pattern at 803bc351.
        source = {"binding": st.binding, "requests": st.request_records(), "attempts": {
            key: [{**attempt, "pages": [sha256_bytes(raw) for raw in attempt["pages"]]}
                  for attempt in st.history.get(key, []) + [st.state[key]]] for key in sorted(st.req)}}
        identity = {"label": label, "seed": seed, "source_sha256": sha256_bytes(dumps(source).encode("utf-8")),
                    "requests": sorted(record(r) for _, reqs in live_sample(st, seed=seed) for r in reqs)}
        if (d / "ledger.jsonl").exists():
            sha = sha256_file(d / "ledger.jsonl")
            try:
                live = Store.read(d, sha)
            except (OSError, ValueError, KeyError, EOFError) as exc:
                raise SealError("live sample snapshot is invalid or partially written") from exc
            if live.binding != {"identity": identity}:
                raise SealError("live sample snapshot binding differs from the source or seeded requests")
            if live.request_records() != identity["requests"] or set(live.state) != set(live.req):
                raise SealError("live sample snapshot is partially written: requests or completion stamps differ")
            shas[label] = sha
        elif (d / "pages").exists():
            raise SealError("live sample snapshot is partially written: cannot overwrite or fetch it again")
        else:
            shas[label] = fetch_live(st, transports, seed=seed, clock=clock).write(d, binding={"identity": identity})
    return shas


def reproduction_check(planner, store, transports, changed_paths: list, fetch_prefix: str, seed: str | None = None,
                       holdout_stores: tuple = (), live_root=None, clock=None) -> dict:
    """holdout_stores: [(label, sealed store)] of every sealed holdout snapshot (review round 11, F3), each checked
    by (b) and (c); (a) needs the holdout planners and is a deterministic function of unchanged code. With live_root
    (run.py transport-check), each live sample is sealed first and the check is computed from the seals."""
    only_fetch = tree_diff_only_under_fetch(changed_paths, fetch_prefix)
    out = {"only_fetch_changed": only_fetch}
    if not only_fetch:
        out["passes"] = False
        return out
    if live_root is not None:
        shas = seal_live_samples(store, transports, seed, holdout_stores, live_root, clock)
        return reproduction_from_sealed(planner, store, changed_paths, fetch_prefix, seed, holdout_stores, live_root,
                                        shas)
    out["plan"] = check_plan(planner, store)
    out["reparse"] = check_reparse(store)
    out["live"] = check_live(store, transports, seed=seed)
    out["holdout"] = {}
    for label, st in holdout_stores:
        out["holdout"][label] = {"reparse": check_reparse(st), "live": check_live(st, transports, seed=seed)}
    return _combine(out)
