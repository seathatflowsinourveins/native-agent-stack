#!/usr/bin/env python3
"""Evaluate the frozen EAP protocol on the daily dataset.

  python evaluate.py --root ROOT --daily DAILY.parquet [--freeze-record PATH] [--protocol-sha256 SHA] [--out RESULT.json]
  python evaluate.py --print-pins --root ROOT --daily DAILY.parquet     # hashes only, no data read

``run()`` refuses (exit 2) before it opens any price unless all of these hold:
* receipts/freeze-record.json names the sha256 of protocol.json (and --protocol-sha256, when
  given, equals it); protocol.json has status 'frozen_pre_outcome', frozen_before_outcomes true
  and frozen_at set;
* every pin in protocol.json#/pins (code, fees, cost table, universe.json, filings.jsonl.gz and
  daily.parquet) matches;
* ``git status --porcelain`` is empty for this directory; the HEAD commit is recorded.
The data pass can only be entered with the FrozenProtocol token that guard() creates.

Primary family (adoption): fixed sequence at alpha 0.05, EAP-2 then EAP-4. Secondary family:
Holm at alpha 0.05 over EAP-1 and EAP-3. Newey-West 4 lags; 3 and 12 as sensitivity.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import eap_signal as S  # noqa: E402
import expected_dates as E  # noqa: E402

PROTOCOL_PATH = HERE / "protocol.json"
FREEZE_RECORD_PATH = HERE / "receipts" / "freeze-record.json"
FROZEN_STATUS = "frozen_pre_outcome"
P = S.PROTOCOL
ST = P["statistics"]
MIN = {"long": 10, "short": 10, "tercile_pool": 30}
MIN_MONTHS = ST["minimum_samples"]["min_valid_months"]
LAGS = ST["nw_lags"]
LAGS_SENS = ST["nw_lags_sensitivity"]
PRIMARY = ST["multiplicity"]["primary"]
SECONDARY = ST["multiplicity"]["secondary"]
CODE_PINS = ("eap_signal.py", "expected_dates.py", "evaluate.py", "collect_edgar.py", "spreads.py", "prefreeze.py")
_TOKEN = object()


class Refusal(SystemExit):
    def __init__(self, reason: str):
        super().__init__(2)
        self.reason = reason


class FrozenProtocol:
    """Proof that guard() accepted the protocol; cannot be built without the module token."""

    def __init__(self, protocol: dict, sha256: str, token: object):
        if token is not _TOKEN:
            raise Refusal("FrozenProtocol can only be created by guard()")
        self.protocol, self.sha256, self._token = protocol, sha256, token


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def freeze_record_sha(path: Path) -> str:
    try:
        rec = json.loads(Path(path).read_text())
    except FileNotFoundError:
        raise Refusal(f"freeze record missing: {path}") from None
    sha = str(rec.get("protocol_sha256") or "").strip().lower()
    if len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
        raise Refusal("freeze record has no protocol_sha256")
    return sha


def freeze_record_commit(path: Path) -> str:
    rec = json.loads(Path(path).read_text())
    commit = str(rec.get("protocol_commit") or "").strip().lower()
    if len(commit) != 40 or any(c not in "0123456789abcdef" for c in commit):
        raise Refusal("freeze record has no full protocol_commit")
    return commit


def verify_freeze_commit(directory: Path, commit: str, expected_sha256: str) -> None:
    """The freeze commit is an ancestor of HEAD and its protocol.json bytes hash to the recorded sha256."""
    anc = subprocess.run(["git", "merge-base", "--is-ancestor", commit, "HEAD"], cwd=directory, capture_output=True)
    if anc.returncode != 0:
        raise Refusal(f"freeze commit {commit} is not an ancestor of HEAD")
    shown = subprocess.run(["git", "show", f"{commit}:./protocol.json"], cwd=directory, capture_output=True)
    if shown.returncode != 0 or hashlib.sha256(shown.stdout).hexdigest() != expected_sha256:
        raise Refusal("protocol.json at the freeze commit does not match the freeze record")


def guard(protocol_path: Path, expected_sha256: str | None) -> FrozenProtocol:
    """The parsed protocol, only when frozen and its bytes match ``expected_sha256``."""
    raw = Path(protocol_path).read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    p = json.loads(raw)
    if not expected_sha256 or expected_sha256.strip().lower() != actual:
        raise Refusal(f"protocol sha256 mismatch: expected {expected_sha256!r}, file has {actual}")
    if p.get("status") != FROZEN_STATUS or p.get("frozen_before_outcomes") is not True or not p.get("frozen_at"):
        raise Refusal(f"protocol is not frozen (status={p.get('status')!r}, frozen_before_outcomes={p.get('frozen_before_outcomes')!r})")
    if Path(protocol_path).resolve() == PROTOCOL_PATH.resolve() and p != S.PROTOCOL:
        raise Refusal("protocol.json changed after the modules loaded it")
    return FrozenProtocol(p, actual, _TOKEN)


def pin_paths(root: Path, daily: Path) -> dict:
    return {"code": {n: HERE / n for n in CODE_PINS},
            "reference": {"fees-v3.json": S.FEES_PATH, "cost-table-eap-v1.json": S.COST_TABLE_PATH},
            "private_inputs": {"universe.json": Path(root) / "universe.json",
                               "filings.jsonl.gz": Path(root) / "derived" / "filings.jsonl.gz",
                               "daily.parquet": Path(daily)}}


def compute_pins(root: Path, daily: Path) -> dict:
    return {g: {n: sha256_file(p) for n, p in d.items()} for g, d in pin_paths(root, daily).items()}


def verify_pins(protocol: dict, root: Path, daily: Path) -> None:
    pins = protocol.get("pins") or {}
    for group, files in pin_paths(root, daily).items():
        want = pins.get(group) or {}
        for name, path in files.items():
            if not want.get(name):
                raise Refusal(f"pin missing: {group}/{name}")
            if not path.exists():
                raise Refusal(f"pinned file missing: {group}/{name}")
            if sha256_file(path) != want[name]:
                raise Refusal(f"pin mismatch: {group}/{name}")


def git_clean_head(directory: Path) -> str:
    def git(*args):
        return subprocess.run(["git", *args], cwd=directory, capture_output=True, text=True)
    st = git("status", "--porcelain", "--", ".")
    if st.returncode != 0:
        raise Refusal("not a git checkout: " + st.stderr.strip())
    if st.stdout.strip():
        raise Refusal("study directory has uncommitted changes")
    head = git("rev-parse", "HEAD")
    if head.returncode != 0:
        raise Refusal("git rev-parse HEAD failed")
    return head.stdout.strip()


# ---------------------------------------------------------------- pure core

def _minus(a, b):
    return a - b if a is not None and b is not None else None


def month_series(rows: dict[str, dict], spy: float | None) -> dict:
    """Portfolio returns of one month. rows: symbol -> {lane, eligible, expected, weight, ret, proxy}."""
    long, short = S.split_portfolios(rows)
    ok_long, ok_short = len(long) >= MIN["long"], len(short) >= MIN["short"]
    L, Sh = S.portfolio_return(long), S.portfolio_return(short)
    M = S.portfolio_return({**long, **short})
    wl = S.capped_weights({s: m[0] for s, m in long.items()})
    out = {"n_long": len(long), "n_short": len(short), "L": L, "S": Sh, "M": M, "spy": spy,
           "max_w_long": max(wl.values()) if wl else None, "eff_n_long": S.effective_n(wl)}
    out["eap1"] = L - Sh if ok_long and ok_short else None
    out["eap2"] = _minus(L, spy) if ok_long else None
    prox = {s: rows[s]["proxy"] for s in long if rows[s].get("proxy") is not None}
    out["n_proxy"] = len(prox)
    out["eap3"] = None
    if len(prox) >= MIN["tercile_pool"]:
        top = S.top_tercile(prox)
        out["n_top"] = len(top)
        out["eap3"] = _minus(S.portfolio_return({s: long[s] for s in top}), spy)
    out["l_minus_m"] = L - M if ok_long and ok_short else None
    out["dv_eap1"] = (S.portfolio_return(long, None) - S.portfolio_return(short, None)) if ok_long and ok_short else None
    out["dv_eap2"] = _minus(S.portfolio_return(long, None), spy) if ok_long else None
    lew, sew = S.split_portfolios(rows, equal_weight=True)
    out["ew_eap1"] = (S.vw_return(lew) - S.vw_return(sew)) if len(lew) >= MIN["long"] and len(sew) >= MIN["short"] else None
    out["ew_eap2"] = _minus(S.vw_return(lew), spy) if len(lew) >= MIN["long"] else None
    ls, ss = S.split_portfolios(rows, lane_name="small")
    out["small_eap1"] = (S.portfolio_return(ls) - S.portfolio_return(ss)) if len(ls) >= MIN["long"] and len(ss) >= MIN["short"] else None
    out["small_eap2"] = _minus(S.portfolio_return(ls), spy) if len(ls) >= MIN["long"] else None
    return out


def cost_pass(months: list[dict], fees: dict, table: dict | None = None) -> list[dict]:
    """Long-leg rebalancing costs month by month with capped weights (months ordered)."""
    prev_w, prev_r = {}, {}
    last_px, last_dv, last_lane = {}, {}, {}
    out = []
    for m in months:
        rows = m["rows"]
        for s, r in rows.items():
            if r.get("price") is not None:
                last_px[s], last_dv[s], last_lane[s] = r["price"], r["dv"], r["lane"] or "small"
        long, _ = S.split_portfolios(rows)
        new = S.capped_weights({s: w for s, (w, _) in long.items()}) if len(long) >= MIN["long"] else {}
        old = S.drift(prev_w, prev_r) if prev_w else {}
        cost, turnover = S.rebalance_cost(old, new, last_px, last_dv, last_lane, m["d"], fees, table)
        out.append({"cost": cost, "turnover": turnover})
        prev_w, prev_r = new, {s: rows[s]["ret"] for s in new}
    return out


def item_test(xs: list[float], min_months: int) -> dict:
    n = len(xs)
    if n < max(3, min_months):
        return {"n_valid_months": n, "status": "inconclusive_below_minimum", "p_one_sided": 1.0}
    mean, se, t = S.nw_t(xs, LAGS)
    q95, q80 = S.t_ppf(0.95, n - 1), S.t_ppf(0.80, n - 1)
    out = {"n_valid_months": n, "status": "tested", "mean_monthly": mean, "nw_lags": LAGS, "nw_se": se, "t": t,
           "p_one_sided": S.t_sf(t, n - 1), "upper_bound_95_one_sided": mean + q95 * se,
           "realized_mde_80": (q95 + q80) * se, "sensitivity": {}}
    for L in LAGS_SENS:
        m2, se2, t2 = S.nw_t(xs, L)
        out["sensitivity"][f"nw{L}"] = {"se": se2, "t": t2, "p_one_sided": S.t_sf(t2, n - 1)}
    return out


def wording(item: dict) -> str | None:
    if item.get("rejected"):
        return None
    if item["status"] != "tested":
        return "inconclusive: below the preregistered minimum number of valid months"
    return (f"not rejected at the preregistered level; the design had 80% power only above "
            f"≈{100 * item['realized_mde_80']:.2f}%/month, so an effect of the published size is not ruled out")


def evaluate_core(months: list[dict], fees: dict, tables: dict | None = None) -> dict:
    tables = tables or {"measured": S.load_cost_table(), "mover_v1_sensitivity": S.load_cost_table("mover_v1_sensitivity")}
    series = [dict(t=m["t"], **month_series(m["rows"], m.get("spy"))) for m in months]
    for name, table in tables.items():
        for s, c in zip(series, cost_pass(months, fees, table)):
            suffix = "" if name == "measured" else "_" + name
            s["cost" + suffix], s["turnover"] = c["cost"], c["turnover"]
            s["eap4" + suffix] = s["eap2"] - c["cost"] if s["eap2"] is not None else None
    items = {}
    for name, key in (("EAP-1", "eap1"), ("EAP-2", "eap2"), ("EAP-3", "eap3"), ("EAP-4", "eap4")):
        items[name] = item_test([s[key] for s in series if s[key] is not None], MIN_MONTHS[name])
    seq = S.fixed_sequence([(k, items[k]["p_one_sided"]) for k in PRIMARY["items"]], PRIMARY["alpha"])
    holm = S.holm({k: items[k]["p_one_sided"] for k in SECONDARY["items"]}, SECONDARY["alpha"])
    for k in items:
        family = "primary" if k in PRIMARY["items"] else "secondary"
        rej = (seq if family == "primary" else holm)[k]
        items[k].update(family=family, rejected=bool(rej and items[k]["status"] == "tested"))
        items[k]["report"] = wording(items[k])
    r = {k: items[k]["rejected"] for k in items}
    if r["EAP-2"] and r["EAP-4"]:
        decision = "adopt_for_pre_positioning_research"
    elif r["EAP-2"]:
        decision = "premium_exists_not_tradable"
    elif r["EAP-1"]:
        decision = "long_short_premium_only"
    else:
        decision = "no_evidence_underpowered"
    valid = [s for s in series if s["eap2"] is not None]
    turn = sum(s["turnover"] for s in valid)
    by_year = defaultdict(lambda: defaultdict(list))
    for s in series:
        for key in ("eap1", "eap2", "eap3", "eap4"):
            if s[key] is not None:
                by_year[s["t"][0]][key].append(s[key])
    descriptive = {
        "break_even_cost_per_unit_turnover": (sum(s["eap2"] for s in valid) / turn) if turn else None,
        "measured_cost_per_unit_turnover": (sum(s["cost"] for s in valid) / turn) if turn else None,
        "mean_monthly_turnover": turn / len(valid) if valid else None,
        "by_year_mean": {y: {k: sum(v) / len(v) for k, v in d.items()} for y, d in sorted(by_year.items())},
    }
    for key in ("l_minus_m", "dv_eap1", "dv_eap2", "ew_eap1", "ew_eap2", "small_eap1", "small_eap2", "eap4_mover_v1_sensitivity"):
        xs = [s[key] for s in series if s.get(key) is not None]
        descriptive[key] = item_test(xs, 3)
    return {"items": items, "decision": decision, "descriptive": descriptive,
            "months": [{k: v for k, v in s.items() if k != "t"} | {"t": f"{s['t'][0]}-{s['t'][1]:02d}"} for s in series]}


# ---------------------------------------------------------------- loaders (after the guard only)

def load_adjusted(con, daily: Path, symbols: set[str]) -> None:
    con.execute("CREATE OR REPLACE TEMP TABLE eap_syms(symbol VARCHAR)")
    con.executemany("INSERT INTO eap_syms VALUES (?)", [(s,) for s in sorted(symbols | {"SPY"})])
    con.execute(f"""CREATE OR REPLACE TEMP TABLE eap_bars AS
        SELECT symbol, session_date, all_c,
               lag(all_c) OVER (PARTITION BY symbol ORDER BY session_date) AS prev_c
        FROM read_parquet('{daily}') WHERE symbol IN (SELECT symbol FROM eap_syms) AND all_c > 0""")


def holding_inputs(con, windows: list[tuple]) -> dict:
    con.execute("CREATE OR REPLACE TEMP TABLE eap_win(i INTEGER, d DATE, e DATE)")
    con.executemany("INSERT INTO eap_win VALUES (?, ?, ?)", windows)
    rows = con.execute("""
        SELECT w.i, b.symbol, max(b.all_c) FILTER (WHERE b.session_date = w.d),
               max(b.session_date) FILTER (WHERE b.session_date > w.d),
               arg_max(b.all_c, b.session_date) FILTER (WHERE b.session_date > w.d)
        FROM eap_bars b JOIN eap_win w ON b.session_date BETWEEN w.d AND w.e GROUP BY 1, 2""").fetchall()
    out = defaultdict(dict)
    for i, sym, dc, ls, lc in rows:
        out[i][sym] = (dc, [(ls, lc)] if ls is not None else [])
    return out


def event_day_returns(con, keys: set) -> dict:
    con.execute("CREATE OR REPLACE TEMP TABLE eap_ev(symbol VARCHAR, s DATE)")
    con.executemany("INSERT INTO eap_ev VALUES (?, ?)", sorted(keys))
    rows = con.execute("""SELECT b.symbol, b.session_date, b.all_c / b.prev_c - 1 FROM eap_bars b
        JOIN eap_ev e ON b.symbol = e.symbol AND b.session_date = e.s WHERE b.prev_c > 0""").fetchall()
    return {(s, d): r for s, d, r in rows}


def closes_at(con, keys: set) -> dict:
    con.execute("CREATE OR REPLACE TEMP TABLE eap_ck(symbol VARCHAR, s DATE)")
    con.executemany("INSERT INTO eap_ck VALUES (?, ?)", sorted(keys))
    rows = con.execute("""SELECT b.symbol, b.session_date, b.all_c FROM eap_bars b
        JOIN eap_ck k ON b.symbol = k.symbol AND b.session_date = k.s""").fetchall()
    return {(s, d): c for s, d, c in rows}


def run(a) -> dict:
    """Guarded evaluation: freeze record, frozen protocol, pins and clean git tree, then data."""
    expected = freeze_record_sha(getattr(a, "freeze_record", None) or FREEZE_RECORD_PATH)
    given = getattr(a, "protocol_sha256", None)
    if given and given.strip().lower() != expected:
        raise Refusal("--protocol-sha256 differs from the freeze record")
    frozen = guard(PROTOCOL_PATH, expected)
    verify_pins(frozen.protocol, a.root, a.daily)
    head = git_clean_head(HERE)
    verify_freeze_commit(HERE, freeze_record_commit(getattr(a, "freeze_record", None) or FREEZE_RECORD_PATH), expected)
    result = _data_pass(a, frozen)
    result.update(git_head=head, protocol_sha256=frozen.sha256, protocol_id=frozen.protocol["id"], label="HIST")
    return result


def _data_pass(a, frozen: FrozenProtocol) -> dict:
    if not isinstance(frozen, FrozenProtocol) or frozen._token is not _TOKEN:
        raise Refusal("data pass requires the guard's FrozenProtocol")
    protocol = frozen.protocol
    con = S.duck(a.root)
    sessions = E.load_sessions(con, a.daily)
    universe = json.loads((Path(a.root) / "universe.json").read_text())["ciks"]
    filings = E.load_filings(Path(a.root))
    events = {c: E.announcement_events(filings.get(c, []), sessions)[0] for c in universe}
    periods = {c: E.period_filings(filings.get(c, [])) for c in universe}
    months = E.study_months(tuple(map(int, protocol["segments"]["first_month"].split("-"))),
                            tuple(map(int, protocol["segments"]["last_month"].split("-"))))
    decisions = [E.decision_session(sessions, t) for t in months]
    symbols = {s for v in universe.values() for s in v}
    lane_in = S.load_lane_inputs(con, a.daily, sessions, decisions, symbols)
    load_adjusted(con, a.daily, symbols)
    windows = [(i, d, E.month_sessions(sessions, t)[-1]) for i, (t, d) in enumerate(zip(months, decisions))]
    hold = holding_inputs(con, windows)
    status, ev_keys = {}, set()
    for i, t in enumerate(months):
        cutoff = E.information_cutoff(sessions, t)
        for cik in universe:
            st = E.monthly_status(events[cik], t, cutoff)
            prior = E.known(events[cik], cutoff)[-4:] if st["expected"] else []
            status[(i, cik)] = (st, prior)
            for sym in universe[cik]:
                ev_keys.update((sym, e.session) for e in prior)
    edr = event_day_returns(con, ev_keys)
    flags = Counter()
    month_inputs = []
    for i, (t, d) in enumerate(zip(months, decisions)):
        dc, bars = hold[i].get("SPY", (None, []))
        spy, spy_flag = S.holding_return(dc, bars, windows[i][2])
        spy = spy if spy_flag == "complete" else None
        flags["spy_" + spy_flag] += 1
        rows = {}
        for cik, syms in universe.items():
            st, prior = status[(i, cik)]
            for sym in syms:
                li = lane_in[d].get(sym)
                if li is None:
                    continue
                ln = S.lane(sym, *li)
                if ln is None:
                    continue
                dc, bars = hold[i].get(sym, (None, []))
                ret, flag = S.holding_return(dc, bars, windows[i][2])
                flags[flag] += 1
                proxy = S.extreme_proxy([edr.get((sym, e.session)) for e in prior], 3) if prior else None
                rows[sym] = {"lane": ln, "eligible": st["eligible"], "expected": st["expected"], "weight": li[1],
                             "ret": ret, "proxy": proxy, "price": li[0], "dv": li[1]}
        month_inputs.append({"t": t, "d": d, "rows": rows, "spy": spy})
    result = evaluate_core(month_inputs, S.load_fees())
    result["descriptive"]["flags"] = dict(flags)
    result["descriptive"]["event_time"] = event_time_descriptive(con, sessions, months, decisions, universe, events, periods, lane_in)
    return result


def event_time_descriptive(con, sessions, months, decisions, universe, events, periods, lane_in) -> dict:
    et = P["expectation"]["secondary_event_time_rule"]
    trades = []
    for t, d in zip(months, decisions):
        cutoff = E.information_cutoff(sessions, t)
        last = E.month_sessions(sessions, t)[-1]
        for cik, syms in universe.items():
            if not E.monthly_status(events[cik], t, cutoff)["eligible"]:
                continue
            x = E.event_time_expectation(events[cik], periods[cik], cutoff)
            if x is None:
                continue
            tr = E.event_time_trade(events[cik], x["expected_date"], cutoff, sessions, d, last, et["k_sessions"], et["fallback_exit_days"])
            if tr is None:
                continue
            for sym in syms:
                li = lane_in[d].get(sym)
                if li and S.lane(sym, *li) == "main":
                    trades.append((sym, *tr))
    keys = {(s, x) for s, a, b in trades for x in (a, b)} | {("SPY", x) for _, a, b in trades for x in (a, b)}
    c = closes_at(con, keys)
    rets, rel = [], []
    for s, a, b in trades:
        if (s, a) in c and (s, b) in c:
            r = c[(s, b)] / c[(s, a)] - 1
            rets.append(r)
            if ("SPY", a) in c and ("SPY", b) in c:
                rel.append(r - (c[("SPY", b)] / c[("SPY", a)] - 1))
    med = lambda xs: S.median(xs) if xs else None
    return {"trades": len(trades), "with_prices": len(rets), "mean": sum(rets) / len(rets) if rets else None,
            "median": med(rets), "mean_minus_spy": sum(rel) / len(rel) if rel else None, "median_minus_spy": med(rel)}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--daily", type=Path, required=True)
    p.add_argument("--freeze-record", type=Path, default=FREEZE_RECORD_PATH)
    p.add_argument("--protocol-sha256")
    p.add_argument("--out", type=Path)
    p.add_argument("--print-pins", action="store_true")
    a = p.parse_args(argv)
    if a.print_pins:
        print(json.dumps(compute_pins(a.root, a.daily), indent=2, sort_keys=True))
        return 0
    try:
        result = run(a)
    except Refusal as r:
        print(f"REFUSED: {r.reason}", file=sys.stderr)
        return 2
    out = a.out or (Path(a.root) / "receipts" / "evaluation.json")
    out.write_text(json.dumps(result, indent=1, sort_keys=True, default=str))
    print(json.dumps({"items": result["items"], "decision": result["decision"], "git_head": result["git_head"]},
                     sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
