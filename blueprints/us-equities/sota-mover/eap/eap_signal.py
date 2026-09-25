"""EAP signal, portfolio, cost and statistics functions (protocol.json#/universe .. #/statistics).

Pure functions use the standard library only and are exercised by synthetic fixtures. The
DuckDB loaders at the bottom read the daily dataset; ``load_lane_inputs`` reads raw close and
raw volume on sessions before the decision session only (membership, allowed before the
freeze). Adjusted closes are read only by evaluate.py's loaders, after its freeze guard.
"""
from __future__ import annotations

import json
import math
import re
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROTOCOL = json.loads((HERE / "protocol.json").read_text())
FEES_PATH = HERE.parents[1] / "mover-v3" / "data" / "fees-v3.json"
COST_TABLE_PATH = HERE / "data" / "cost-table-eap-v1.json"
WEIGHT_CAP = PROTOCOL["universe"]["weight_cap"]

U = PROTOCOL["universe"]
MAIN_MIN_PRICE = U["main_lane"]["min_prior_raw_close"]
MAIN_MIN_DV = U["main_lane"]["min_prior20_median_dollar_volume"]
SMALL_MIN_PRICE = U["small_cap_lane"]["min_prior_raw_close"]
SMALL_MIN_DV = U["small_cap_lane"]["min_prior20_median_dollar_volume"]
LOOKBACK = U["dollar_volume_lookback_sessions"]
MIN_PRIOR_BARS = U["min_prior_bars_in_lookback"]
DERIVATIVE_RE = re.compile(U["common_stock_heuristic"]["exclude_symbol_regex"])


# ---------------------------------------------------------------- universe

def is_common_like(symbol: str) -> bool:
    return not DERIVATIVE_RE.search(symbol)


def median(xs: list[float]) -> float:
    s = sorted(xs)
    n = len(s)
    if n == 0:
        raise ValueError("median of empty list")
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def lane(symbol: str, prior_raw_close: float | None, median_dv: float | None, n_prior: int, has_decision_bar: bool) -> str | None:
    """Lane of a symbol at decision session D from bars strictly before D (plus D's existence)."""
    if not has_decision_bar or not is_common_like(symbol) or n_prior < MIN_PRIOR_BARS:
        return None
    if prior_raw_close is None or median_dv is None:
        return None
    if prior_raw_close >= MAIN_MIN_PRICE and median_dv >= MAIN_MIN_DV:
        return "main"
    if prior_raw_close >= SMALL_MIN_PRICE and median_dv >= SMALL_MIN_DV:
        return "small"
    return None


# ---------------------------------------------------------------- returns and portfolios

def holding_return(decision_close: float | None, month_bars: list[tuple[date, float]], month_last_session: date) -> tuple[float | None, str]:
    """Close-to-close return from D to the last bar in month t; cash after an early last bar.

    A symbol with no bar after D in the month returns 0 (flag no_bar_in_month); one whose
    bars stop before the month's last session keeps the return to its last bar (flag
    bars_end_early; delisting returns are unavailable, deviation D4).
    """
    if decision_close is None or decision_close <= 0:
        return None, "no_decision_close"
    if not month_bars:
        return 0.0, "no_bar_in_month"
    last_session, last_close = max(month_bars)
    r = last_close / decision_close - 1.0
    return r, ("complete" if last_session >= month_last_session else "bars_end_early")


def vw_return(members: dict[str, tuple[float, float]]) -> float | None:
    """Weighted mean of returns; ``members`` maps symbol -> (weight, return)."""
    tw = sum(w for w, _ in members.values())
    if tw <= 0:
        return None
    return sum(w * r for w, r in members.values()) / tw


def normalized(weights: dict[str, float]) -> dict[str, float]:
    tw = sum(weights.values())
    return {k: v / tw for k, v in weights.items()} if tw > 0 else {}


def capped_weights(raw: dict[str, float], cap: float = WEIGHT_CAP) -> dict[str, float]:
    """Normalised weights with no name above max(cap, 1/n); excess redistributed pro rata."""
    w = normalized({k: v for k, v in raw.items() if v > 0})
    if not w:
        return {}
    cap = max(cap, 1.0 / len(w))
    fixed: dict[str, float] = {}
    while True:
        free = {k: v for k, v in w.items() if k not in fixed}
        room = 1.0 - cap * len(fixed)
        scaled = {k: v * room / sum(free.values()) for k, v in free.items()}
        over = {k for k, v in scaled.items() if v > cap + 1e-15}
        if not over:
            return {**{k: cap for k in fixed}, **scaled}
        fixed.update({k: cap for k in over})


def effective_n(weights: dict[str, float]) -> float:
    return 1.0 / sum(v * v for v in weights.values()) if weights else 0.0


def portfolio_return(members: dict[str, tuple[float, float]], cap: float | None = WEIGHT_CAP) -> float | None:
    """Return of ``members`` (symbol -> (raw weight, return)) with capped weights (cap None: raw)."""
    if not members:
        return None
    if cap is None:
        return vw_return(members)
    w = capped_weights({s: m[0] for s, m in members.items()}, cap)
    return sum(w[s] * members[s][1] for s in w) if w else None


def split_portfolios(rows: dict[str, dict], lane_name: str = "main", equal_weight: bool = False) -> tuple[dict, dict]:
    """rows: symbol -> {eligible, expected, lane, weight, ret}; eligible symbols of one lane."""
    long, short = {}, {}
    for s, r in rows.items():
        if r["lane"] != lane_name or not r["eligible"] or r["ret"] is None:
            continue
        (long if r["expected"] else short)[s] = (1.0 if equal_weight else r["weight"], r["ret"])
    return long, short


def extreme_proxy(event_day_returns: list[float | None], need: int) -> float | None:
    """Mean |announcement-session return| over the prior events; None if fewer than ``need``."""
    xs = [abs(x) for x in event_day_returns if x is not None]
    return sum(xs) / len(xs) if len(xs) >= need else None


def top_tercile(proxies: dict[str, float]) -> set[str]:
    ranked = sorted(proxies.items(), key=lambda kv: (-kv[1], kv[0]))
    return {s for s, _ in ranked[: len(ranked) // 3]}


# ---------------------------------------------------------------- costs

def load_cost_table(which: str = "measured", path: Path = COST_TABLE_PATH) -> dict:
    """{"main_lane": rows, "small_cap_lane_flat": x}: the pinned measured table or the mover-v1 sensitivity."""
    c = PROTOCOL["costs"]
    if which == "mover_v1_sensitivity":
        return c["sensitivity_half_spread_table_mover_v1"]
    doc = json.loads(path.read_text())
    rows = [{k: r[k] for k in ("price_min", "price_max", "dv_min", "dv_max", "half_spread")} for r in doc["rows"]]
    return {"main_lane": rows, "small_cap_lane_flat": c["small_cap_lane_flat_half_spread"]}


def half_spread(price: float, dv: float, lane_name: str, table: dict | None = None) -> float:
    table = table or load_cost_table()
    if lane_name != "main":
        return table["small_cap_lane_flat"]
    for row in table["main_lane"]:
        if row["price_min"] <= price < row["price_max"] and row["dv_min"] <= dv < row["dv_max"]:
            return row["half_spread"]
    raise ValueError(f"no half-spread cell for price {price} dv {dv}")


def load_fees(path: Path = FEES_PATH) -> dict:
    return json.loads(path.read_text())


def _row_for(rows: list[dict], d: date) -> dict:
    iso = d.isoformat()
    for r in rows:
        if r["from"] <= iso and (r["to"] is None or iso <= r["to"]):
            return r
    raise ValueError(f"no fee row for {iso}")


def sell_fee_per_dollar(d: date, price: float, fees: dict) -> float:
    """SEC Section 31 plus FINRA TAF per dollar sold (TAF per-trade cap ignored: conservative)."""
    sec = _row_for(fees["sec_section31"]["rows"], d)["usd_per_million"] / 1e6
    taf = _row_for(fees["finra_taf_covered_equity"]["rows"], d)["usd_per_share"] / price
    return sec + taf


def drift(weights: dict[str, float], returns: dict[str, float]) -> dict[str, float]:
    grown = {s: w * (1.0 + returns.get(s, 0.0)) for s, w in weights.items()}
    return normalized(grown)


def rebalance_cost(old: dict[str, float], new: dict[str, float], price: dict[str, float], dv: dict[str, float],
                   lanes: dict[str, str], d: date, fees: dict, table: dict | None = None) -> tuple[float, float]:
    """(cost, turnover) as fractions of book for moving from drifted ``old`` to ``new`` weights."""
    cost = turnover = 0.0
    for s in set(old) | set(new):
        dw = new.get(s, 0.0) - old.get(s, 0.0)
        if dw == 0:
            continue
        turnover += abs(dw)
        cost += abs(dw) * half_spread(price[s], dv[s], lanes.get(s, "main"), table)
        if dw < 0:
            cost += abs(dw) * sell_fee_per_dollar(d, price[s], fees)
    return cost, turnover


# ---------------------------------------------------------------- statistics

def nw_t(xs: list[float], lags: int) -> tuple[float, float, float]:
    """(mean, Newey-West standard error with Bartlett weights, t)."""
    n = len(xs)
    if n < 3:
        raise ValueError("need at least 3 observations")
    m = sum(xs) / n
    e = [x - m for x in xs]
    s = sum(v * v for v in e) / n
    for L in range(1, min(lags, n - 1) + 1):
        g = sum(e[i] * e[i - L] for i in range(L, n)) / n
        s += 2 * (1 - L / (lags + 1)) * g
    se = math.sqrt(max(s, 0.0) / n)
    return m, se, (m / se if se > 0 else float("inf") if m > 0 else float("-inf") if m < 0 else 0.0)


def _betacf(a: float, b: float, x: float) -> float:
    tiny, qab, qap, qam = 1e-300, a + b, a + 1, a - 1
    c, d = 1.0, 1 - qab * x / qap
    d = 1 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 300):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1 + aa * d
        d = 1 / (d if abs(d) > tiny else tiny)
        c = 1 + aa / c
        c = c if abs(c) > tiny else tiny
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1 + aa * d
        d = 1 / (d if abs(d) > tiny else tiny)
        c = 1 + aa / c
        c = c if abs(c) > tiny else tiny
        dl = d * c
        h *= dl
        if abs(dl - 1) < 1e-14:
            break
    return h


def betainc(a: float, b: float, x: float) -> float:
    """Regularized incomplete beta I_x(a, b)."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    lbt = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1 - x)
    if x < (a + 1) / (a + b + 2):
        return math.exp(lbt) * _betacf(a, b, x) / a
    return 1 - math.exp(lbt) * _betacf(b, a, 1 - x) / b


def t_sf(t: float, df: float) -> float:
    """One-sided P(T > t) for Student's t with ``df`` degrees of freedom."""
    if math.isinf(t):
        return 0.0 if t > 0 else 1.0
    tail = 0.5 * betainc(df / 2, 0.5, df / (df + t * t))
    return tail if t > 0 else 1 - tail


def t_ppf(q: float, df: float) -> float:
    """Quantile of Student's t: the t with P(T <= t) = q (bisection on t_sf)."""
    lo, hi = -60.0, 60.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if 1 - t_sf(mid, df) < q:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def holm(pvalues: dict[str, float], alpha: float) -> dict[str, bool]:
    """Holm step-down: reject while p_(k) <= alpha / (m - k)."""
    m = len(pvalues)
    out = {k: False for k in pvalues}
    for k, (name, p) in enumerate(sorted(pvalues.items(), key=lambda kv: (kv[1], kv[0]))):
        if p <= alpha / (m - k):
            out[name] = True
        else:
            break
    return out


def fixed_sequence(pvalues: list[tuple[str, float]], alpha: float) -> dict[str, bool]:
    """Test in the given order at full alpha; stop at the first non-rejection."""
    out, go = {}, True
    for name, p in pvalues:
        out[name] = go and p <= alpha
        go = out[name]
    return out


# ---------------------------------------------------------------- DuckDB loaders (CLI only)

def duck(root: Path):
    import duckdb  # lazy: tests of the pure functions need no DuckDB
    tmp = Path(root) / "duckdb-tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute(f"SET memory_limit='{PROTOCOL['resources']['duckdb_memory_limit']}'")
    con.execute(f"SET threads={PROTOCOL['resources']['duckdb_threads']}")
    con.execute(f"SET temp_directory='{tmp}'")
    con.execute("SET preserve_insertion_order=false")
    return con


def load_lane_inputs(con, daily: Path, sessions: list[date], decisions: list[date], symbols: set[str]) -> dict:
    """{D: {symbol: (prior_raw_close, median_dv, n_prior, has_decision_bar)}} from raw columns.

    Reads raw close and raw volume on the LOOKBACK sessions before D and only the existence
    of a bar on D; no adjusted close or post-decision value is read.
    """
    pairs = []
    for d in decisions:
        i = sessions.index(d)
        for s in sessions[max(0, i - LOOKBACK): i + 1]:
            pairs.append((d, s))
    con.execute("CREATE OR REPLACE TEMP TABLE eap_pairs(d DATE, s DATE)")
    con.executemany("INSERT INTO eap_pairs VALUES (?, ?)", pairs)
    con.execute("CREATE OR REPLACE TEMP TABLE eap_syms(symbol VARCHAR)")
    con.executemany("INSERT INTO eap_syms VALUES (?)", [(s,) for s in sorted(symbols)])
    rows = con.execute(f"""
        SELECT p.d, b.symbol,
               arg_max(b.raw_c, b.session_date) FILTER (WHERE b.session_date < p.d),
               median(b.raw_c * b.raw_v) FILTER (WHERE b.session_date < p.d),
               count(*) FILTER (WHERE b.session_date < p.d),
               bool_or(b.session_date = p.d)
        FROM (SELECT symbol, session_date, raw_c, raw_v FROM read_parquet('{daily}')
              WHERE symbol IN (SELECT symbol FROM eap_syms)) b
        JOIN eap_pairs p ON b.session_date = p.s
        GROUP BY 1, 2""").fetchall()
    out: dict = {d: {} for d in decisions}
    for d, sym, close, mdv, n, has_d in rows:
        out[d][sym] = (close, mdv, int(n), bool(has_d))
    return out


def lanes_from_inputs(inputs: dict) -> dict:
    return {d: {s: lane(s, *v) for s, v in per.items()} for d, per in inputs.items()}
