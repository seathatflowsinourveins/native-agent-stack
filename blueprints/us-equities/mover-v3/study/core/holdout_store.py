"""The holdout's input: the sealed collection batches, earlier sealed count snapshots and the snapshot the current
count or read is filling, read as one store (holdout_gate.prospective_collection; review round 9, M-6).

Collection batches are separate sealed snapshots, and each groups its screen requests by its own enumeration, so a
holdout plan built from a later enumeration cannot find their keys. The screen is therefore merged per (symbol,
session): a screen row of session s for symbol X comes from the latest batch whose asof = s screen request names X
(a complete one before an incomplete one), and the rename-day re-fetch rows of X for session s, when present, join
that screen (they replace the batch's rows for the sessions they hold). Only symbol-sessions that no batch holds
are requested by the plan (core.stage._screen_reqs), with asof = s. Every other request is found by its key.

Review round 14, F1: a per-event or quote request held by an earlier sealed snapshot (a count's) is found there only
if that snapshot fetched it after the request's data end had passed: the scheduled close of its 'end' session (daily
bars, auctions) or its 'end' timestamp (minute bars, quotes) is at or before the request's vintage. Otherwise the
earlier response cannot hold the sessions after its fetch (the bars and prints of a delayed exit after the window's
last session, fetched by the count at its close), so the request is fetched again into the live snapshot, and the
live copy governs. Screen and enumeration requests are unaffected.
"""
from __future__ import annotations

from core.screen import SCREEN_KINDS

RENAME_PREFIX = "rename_refetch_"


STALE_KINDS = ("event_", "quote_")


def data_end(cal, req: dict):
    """The epoch at which a per-event or quote request's data are complete, or None for another kind."""
    from core.calendar import parse_utc
    if not req["kind"].startswith(STALE_KINDS):
        return None
    end = (req.get("params") or {}).get("end")
    if not end:
        return None
    if len(end) == 10:
        return cal.close(end) if cal.is_session(end) else None
    return parse_utc(end)


class HoldoutStore:
    def __init__(self, bases: list, live, cal=None):
        """cal: the calendar that dates a base response's data end (review round 14, F1); without it every base
        response is used as held (the pre-round-14 behaviour, kept for the key-only unit tests)."""
        self.bases, self.live, self.cal = list(bases), live, cal
        self.index, self.rename = {}, {}
        for st in [*self.bases, self.live]:
            for key in sorted(st.req):
                self._index(st, st.req[key])

    # ------------------------------------------------------------ the live store (written and re-fetched)
    @property
    def req(self):
        return self.live.req

    @property
    def state(self):
        return self.live.state

    @property
    def history(self):
        return self.live.history

    def put(self, req, complete, pages, vintage, attempt=0, error=None, elapsed_seconds=None):
        self.live.put(req, complete, pages, vintage, attempt=attempt, error=error, elapsed_seconds=elapsed_seconds)
        self._index(self.live, req)

    def write(self, directory) -> str:
        return self.live.write(directory)

    def incomplete_by_kind(self) -> dict:
        return self.live.incomplete_by_kind()

    # ------------------------------------------------------------ lookup by key across every store
    def stale(self, st, key) -> bool:
        """A base response fetched before its data end (review round 14, F1)."""
        if self.cal is None:
            return False
        from core.calendar import parse_utc
        end = data_end(self.cal, st.req[key])
        return end is not None and parse_utc(st.state[key]["vintage"]) < end

    def _holder(self, key):
        if self.live.has(key):
            return self.live
        for st in reversed(self.bases):
            if st.has(key) and not self.stale(st, key):
                return st
        return None

    def has(self, key) -> bool:
        return self._holder(key) is not None

    def status(self, key):
        st = self._holder(key)
        return None if st is None else st.status(key)

    def parsed(self, key):
        return self._holder(key).parsed(key)

    def empty(self, key, symbol=None) -> bool:
        return self._holder(key).empty(key, symbol)

    def vintages(self) -> list:
        return sorted({v for st in [*self.bases, self.live] for v in st.vintages()})

    def request_of(self, key):
        return self._holder(key).req[key]

    # ------------------------------------------------------------ the merged screen
    def _index(self, st, req):
        kind = req["kind"]
        target = self.index
        if kind.startswith(RENAME_PREFIX):
            kind, target = kind[len(RENAME_PREFIX):], self.rename
        if kind not in SCREEN_KINDS:
            return
        s = req["asof_session"]
        for sym in req["params"]["symbols"].split(","):
            prev = target.get((kind, s, sym))
            if prev is not None and prev[0].status(prev[1]) == "complete" and st.status(req["key"]) != "complete":
                continue
            target[(kind, s, sym)] = (st, req["key"])

    def uncovered(self, s: str, batch: list) -> list:
        return [x for x in batch if any((k, s, x) not in self.index and (k, s, x) not in self.rename
                                        for k in SCREEN_KINDS)]

    def screen_view(self, cal, s: str, batch: list) -> dict:
        """core.screen.view for one batch of session s, assembled per symbol from the merged index."""
        keys, unknown, bad, data = set(), set(), set(), {k: {} for k in SCREEN_KINDS}
        for sym in batch:
            for k in SCREEN_KINDS:
                hit, rn = self.index.get((k, s, sym)), self.rename.get((k, s, sym))
                if hit is None and rn is None:
                    raise KeyError(f"screen {s} {sym}: unsealed request (no outcome is computed from unsealed data)")
                st, key = hit if hit is not None else rn
                keys.add(key)
                if st.status(key) != "complete":
                    unknown.add(sym)
                    bad.add(k)
                    continue
                rows = dict(st.parsed(key).get(sym) or {})
                if hit is not None and rn is not None and rn[0].status(rn[1]) == "complete":
                    rows.update(rn[0].parsed(rn[1]).get(sym) or {})
                if rows:
                    data[k][sym] = rows
        return {"requests": len(keys), "incomplete_kinds": sorted(bad), "unknown": unknown,
                "empty": [k for k in SCREEN_KINDS if not data[k]], "data": data}
