"""universe_and_identity: enumeration, the asof rule, identity dedup and the same-session guard.

Review round 8, E1 (option a): dedup runs the byte-for-byte pinned copy of coverage.dedupe_identity at aa6fc79
through DuckDB. duckdb is therefore an allowed import, pinned in study/runtime.lock and checked by the evaluator's
version refusal. The screen table is loaded into the DuckDB table `joined` with the schema
(symbol VARCHAR, session_date DATE, raw_o DOUBLE, raw_h DOUBLE, raw_l DOUBLE, raw_c DOUBLE, raw_v DOUBLE),
one row per symbol and session s taken from that session's asof = s screen request.
"""
from __future__ import annotations

from datetime import date

from pinned.collect_daily_copy import DATA_SYMBOL
from pinned.coverage_copy import _rename_terminus, dedupe_identity


class AsofRefused(Exception):
    pass


def enumerate_symbols(assets: list[dict], actions: list[dict]) -> dict:
    """The union of (a) asset-master symbols (active and inactive, us_equity, every exchange) that pass
    DATA_SYMBOL and (b) every old and new symbol named by a corporate-action record (renamed-away tickers kept).
    Returns {"symbols": sorted list, "counts": per-source counts}."""
    master = {a["symbol"] for a in assets if a.get("symbol") and (a.get("class") in (None, "us_equity"))}
    placeholders = {s for s in master if not DATA_SYMBOL.match(s)}
    master_ok = master - placeholders
    from_actions = set()
    for rec in actions:
        for f in ("symbol", "old_symbol", "new_symbol", "acquirer_symbol", "acquiree_symbol"):
            s = rec.get(f)
            if s and DATA_SYMBOL.match(s):
                from_actions.add(s)
    symbols = sorted(master_ok | from_actions)
    return {"symbols": symbols,
            "counts": {"asset_master": len(master_ok), "asset_master_placeholders_removed": len(placeholders),
                       "corporate_actions": len(from_actions), "corporate_actions_only": len(from_actions - master_ok),
                       "union": len(symbols)}}


def rename_pairs(actions: list[dict]) -> set:
    return {(r["old_symbol"], r["new_symbol"]) for r in actions
            if r.get("type") == "name_change" and r.get("old_symbol") and r.get("new_symbol")}


def check_asof(request: dict) -> None:
    """Every bars, auctions or quotes request carries asof = its defining session (universe_and_identity.asof).
    Refuses a missing asof and one that differs from the defining session. A request built with the fetch date as
    asof is refused by the second rule: the plan (core.plan) sets asof_session to the session that defines the
    request (s for a screen row, t for an event), never to the fetch date (review round 9, L-6: the former separate
    fetch-date clause could never fire)."""
    if request["kind"] in ("assets", "corporate_actions") or request["kind"].startswith("count_default_asof"):
        return  # enumeration, and the count-only identity_diagnostic copy at the provider default asof
    asof = request["params"].get("asof")
    if not asof:
        raise AsofRefused(f"{request['key']}: no asof (the provider default is never used)")
    if asof != request["asof_session"]:
        raise AsofRefused(f"{request['key']}: asof {asof} is not the defining session {request['asof_session']}")


def dedupe_screen(rows: list[dict], renames: set, active: frozenset = frozenset()) -> dict:
    """Apply the pinned dedupe_identity to the screen table. rows: {"symbol", "session", "o","h","l","c","v"}
    (raw daily bars of session s from asof = s requests). Returns {"kept": set of (symbol, session),
    "removed": set, "report": dedupe_identity's report}."""
    import duckdb
    import pandas as pd

    con = duckdb.connect()
    con.execute("CREATE TABLE joined (symbol VARCHAR, session_date DATE, raw_o DOUBLE, raw_h DOUBLE, "
                "raw_l DOUBLE, raw_c DOUBLE, raw_v DOUBLE)")
    if rows:
        frame = pd.DataFrame({"symbol": [r["symbol"] for r in rows],
                              "session_date": [date.fromisoformat(r["session"]) for r in rows],
                              "raw_o": [float(r["o"]) for r in rows], "raw_h": [float(r["h"]) for r in rows],
                              "raw_l": [float(r["l"]) for r in rows], "raw_c": [float(r["c"]) for r in rows],
                              "raw_v": [float(r["v"]) for r in rows]})
        con.register("screen_frame", frame)
        con.execute("INSERT INTO joined SELECT symbol, CAST(session_date AS DATE), raw_o, raw_h, raw_l, raw_c, raw_v "
                    "FROM screen_frame")
        con.unregister("screen_frame")
    before = {(r["symbol"], r["session"]) for r in rows}
    report = dedupe_identity(con, renames, frozenset(active))
    after = {(s, d.isoformat()) for s, d in con.execute("SELECT symbol, session_date FROM joined").fetchall()}
    con.close()
    return {"kept": after, "removed": before - after, "report": report}


def rank_key(symbol: str, other: str, renames: set, active: frozenset):
    """Survivor order for the same-session guard: the rename terminus, then active status, then lexicographic."""
    term = _rename_terminus([symbol, other], renames)
    return (0 if term == symbol else 1, 0 if symbol in active else 1, symbol)


def same_session_guard(candidates: list[dict], renames: set, active: frozenset = frozenset()):
    """Two candidates on one session whose raw daily OHLCV (volume > 0) is identical on both s-1 and s are one
    event, kept under the higher-ranked symbol. candidates: {"symbol","session","ohlcv_prev","ohlcv"}.
    Returns (kept list, removed list)."""
    by_session = {}
    for c in candidates:
        by_session.setdefault(c["session"], []).append(c)
    kept, removed = [], []
    for s, cs in sorted(by_session.items()):
        cs = sorted(cs, key=lambda c: c["symbol"])
        dropped = set()
        for i, a in enumerate(cs):
            for b in cs[i + 1:]:
                if a["symbol"] in dropped or b["symbol"] in dropped:
                    continue
                same = (a["ohlcv_prev"] == b["ohlcv_prev"] and a["ohlcv"] == b["ohlcv"]
                        and a["ohlcv"][4] > 0 and a["ohlcv_prev"][4] > 0)
                if same:
                    ka = rank_key(a["symbol"], b["symbol"], renames, active)
                    kb = rank_key(b["symbol"], a["symbol"], renames, active)
                    dropped.add(b["symbol"] if ka < kb else a["symbol"])
        for c in cs:
            (removed if c["symbol"] in dropped else kept).append(c)
    return kept, removed
