"""cost_model and the net-return formula of populations.corporate_actions.

Cost cell (review round 8, R8-12): time_bucket, price_tier and dv_tier are the pinned copies of rules.py at
aa6fc79, so the intervals are half-open: time buckets [04:00, 08:00), [08:00, 09:30), [09:30, 10:00),
[10:00, 16:01) ET; price tiers [0, 2), [2, 5), [5, 20), [20, inf); dv tiers [0, 1M), [1M, 5M), [5M, inf).
A boundary value goes to the upper tier ($5.00 is in $5-20).

Fees: SEC Section 31 at rate x sell value / 1e6 plus FINRA TAF min(usd_per_share x shares, max_per_trade),
unrounded, from data/fees-v3.json and its append-only amendments; commission 0.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from pinned.rules_copy import dv_tier, price_tier, time_bucket
from core.canon import sha256_bytes
from core.params import C, COST_TABLE, S

N_TIME, N_PRICE, N_DV = 4, 4, 3


class TableHashMismatch(Exception):
    pass


def load_table(path) -> dict:
    """{cell_key: half_spread} from the v1 cost table; refuses a file whose sha256 is not the pinned one."""
    raw = Path(path).read_bytes()
    if sha256_bytes(raw) != COST_TABLE["sha256"]:
        raise TableHashMismatch("cost table sha256 differs from cost_model.base_table")
    body = json.loads(raw)
    return {k: float(v["half_spread"]) for k, v in body["cells"].items()}


def monotone(cells: dict) -> dict:
    """fix_1: within each time x price bucket, a less liquid dv tier is never cheaper than a more liquid one."""
    out = dict(cells)
    for tb in range(N_TIME):
        for pt in range(N_PRICE):
            k = lambda d: f"{tb}|{pt}|{d}"  # noqa: E731
            out[k(2)] = cells[k(2)]
            out[k(1)] = max(cells[k(1)], out[k(2)])
            out[k(0)] = max(cells[k(0)], out[k(1)])
    return out


def cell_key(session: str, ts: float, price: float, cum_dv: float) -> str:
    tb = time_bucket(session, ts)
    if tb is None:
        raise ValueError("fill time outside the cost table's time buckets")
    return f"{tb}|{price_tier(price)}|{dv_tier(cum_dv)}"


def filled_notional(med20, entry_bar_dv):
    """min($20,000; 1% of med20; 10% of the entry bar's vwap x volume); None if the trade cannot be sized."""
    if med20 is None or entry_bar_dv is None:
        return None
    return min(S["notional_cap_usd"], S["med20_fraction"] * med20, S["entry_bar_fraction"] * entry_bar_dv)


def is_no_fill(notional) -> bool:
    return notional is None or notional < S["min_notional_usd"]


def impact(c: float, sigma_d: float, notional: float, med20: float) -> float:
    """c x sigma_d x sqrt(q), q = filled notional / med20 (per side, as a return)."""
    return c * sigma_d * math.sqrt(notional / med20)


def per_side(hs_cell: float, h_fill: float, imp: float, mode: str = "primary") -> float:
    """primary: 1.25 x max(hs'(cell), h_fill) + impact. table_only: 1.25 x hs'(cell) + impact (v1's convention).
    stress: 2 x 1.25 x max(hs'(cell), h_fill) + impact, where the caller passes impact at c = 2.0."""
    if mode == "primary":
        return C["table_multiplier"] * max(hs_cell, h_fill) + imp
    if mode == "table_only":
        return C["table_multiplier"] * hs_cell + imp
    if mode == "stress":
        return C["stress_multiplier"] * C["table_multiplier"] * max(hs_cell, h_fill) + imp
    raise ValueError(mode)


class Fees:
    """Review round 14, F2: the base file's rows of one kind never overlap and each has from <= to (a base that
    breaks this is refused at load, never at a read). An amendment line supersedes, for the dates it covers, every
    earlier row of its kind (the base's open-ended last row included): the latest appended line that covers a date
    governs, and a base row governs a date no amendment line covers. No line is edited; supersession is by
    precedence. core.holdout.require_fee_coverage checks that every date a count or read can book has a row before
    that action fetches anything."""

    def __init__(self, base: dict, amendments: list[dict] = (), freeze_session: str | None = None):
        """freeze_session, when given, refuses an amendment line whose first date precedes it (review round 9, F5);
        from_files requires it whenever the amendment file has a line."""
        self.sec = list(base["sec_section31_usd_per_million_of_sales"])
        self.taf = list(base["finra_taf_covered_equity_sales"])
        for name, rows in (("SEC", self.sec), ("TAF", self.taf)):
            spans = sorted((r["from"], r["to"]) for r in rows)
            for lo, hi in spans:
                if lo > hi:
                    raise ValueError(f"a base {name} fee row runs from {lo} to {hi}")
            for (_, hi), (lo, _) in zip(spans, spans[1:]):
                if lo <= hi:
                    raise ValueError(f"base {name} fee rows overlap on {lo}")
        self.sec_amend, self.taf_amend = [], []
        for a in amendments:
            if freeze_session is not None and (a.get("from") or "") < freeze_session:
                raise ValueError(f"fee amendment starts {a.get('from')}, before the freeze session")
            if not a.get("from") or not a.get("to") or a["from"] > a["to"]:
                raise ValueError(f"fee amendment runs from {a.get('from')} to {a.get('to')}")
            if a.get("kind") == "sec_section31":
                self.sec_amend.append(a)
            elif a.get("kind") == "finra_taf":
                self.taf_amend.append(a)
            else:
                raise ValueError(f"unknown fee amendment kind {a.get('kind')!r}")
        if any(r.get("max_per_trade") is None for r in self.taf + self.taf_amend):
            raise ValueError("a TAF row must carry its max_per_trade cap")

    @classmethod
    def from_files(cls, base_path, amendments_path=None, *, freeze_session: str | None = None):
        base = json.loads(Path(base_path).read_text(encoding="utf-8"))
        lines = []
        if amendments_path and Path(amendments_path).exists():
            lines = [json.loads(x) for x in Path(amendments_path).read_text(encoding="utf-8").splitlines() if x.strip()]
        if lines and freeze_session is None:
            raise ValueError("a fee amendment line applies only with the freeze session known")
        return cls(base, lines, freeze_session=freeze_session)

    @staticmethod
    def _row(rows, amended, day):
        for r in reversed(amended):
            if r["from"] <= day <= r["to"]:
                return r
        hit = [r for r in rows if r["from"] <= day <= r["to"]]
        if len(hit) != 1:
            raise KeyError(f"{len(hit)} fee rows for {day}")
        return hit[0]

    def rates(self, day: str):
        taf = self._row(self.taf, self.taf_amend, day)
        return self._row(self.sec, self.sec_amend, day)["rate"], taf["usd_per_share"], taf["max_per_trade"]

    def gaps(self, days) -> list:
        """The days of `days` that have no governing SEC or TAF row."""
        out = []
        for d in days:
            try:
                self.rates(d)
            except KeyError:
                out.append(d)
        return out

    def sale_fees(self, day: str, shares: float, sell_value: float) -> float:
        sec, taf, cap = self.rates(day)
        return sec * sell_value / 1e6 + min(taf * shares, cap)


def cash_term(cal, raw: dict, split: dict, allc: dict, e: str, x: str):
    """The cash per original share from entry session e to exit session x (review round 14, Codex P2), or None
    without the raw, split and all bars of e and x, or when a dividend's previous close is missing.

    D(d) = all_c(d) / split_c(d) is the dividend-only adjustment of session d. For consecutive XNYS sessions p < k
    of [e, x], the step s_k = 1 - D(p) / D(k) is an ex-dividend on k; the cash per split-adjusted share is
    split_c(p) x s_k (the dividend at the close of the session immediately before its ex-date, D7's arithmetic at
    the ex-date), and per original share it is a(e) x split_c(p) x s_k, a(e) = raw_c(e) / split_c(e). A step with
    |s_k| at or below 2e-3 is adjustment-rounding noise (review round 8, E6) and books nothing, and the sum is kept
    with its sign only when |cash| > 2e-3 x raw_c(e). No price after the ex-date enters: D7's raw_c(e) x all_c(x) /
    all_c(e) - F x raw_c(x) scaled the dividend by the close of x, so an exit at the open of x booked cash that
    moved with x's later intraday return.

    Review of 202968f, Codex P2: a session of [e, x] without its split or all bar is not skipped. The step across
    it cannot name the ex-date or its previous close (closes $20, $40, $39: a $1 dividend ex on the third session
    with the second session's split bar missing booked 20 x 0.025 = $0.50, not $1), so a step outside the band
    across a missing bar leaves the cash undefined (populations.corporate_actions: the trade or H3-c event is
    excluded and counted like an undefined F); a step inside the band there books nothing, as between any two
    sessions."""
    r_e = raw.get(e)
    sessions = cal.range(e, x)
    days = [d for d in sessions if (split.get(d) or {}).get("c") and (allc.get(d) or {}).get("c")]
    if not r_e or not r_e.get("c") or not days or days[0] != e or days[-1] != x:
        return None
    pos = {d: i for i, d in enumerate(sessions)}
    a_e = float(r_e["c"]) / float(split[e]["c"])
    total = 0.0
    for p_, k in zip(days, days[1:]):
        step = 1.0 - (allc[p_]["c"] / split[p_]["c"]) / (allc[k]["c"] / split[k]["c"])
        if abs(step) > C["cash_band"]:
            if pos[k] - pos[p_] != 1:
                return None
            total += float(split[p_]["c"]) * step
    cash = a_e * total
    return cash if abs(cash) > C["cash_band"] * float(r_e["c"]) else 0.0


def trade_net_return(notional, entry_mid, exit_price, F, cash, c_in, c_out, fees: Fees, exit_day: str) -> float:
    """net = (N F exit_mid (1 - c_out) - sell_fees + N cash) / (N entry_mid (1 + c_in)) - 1, N = notional / entry_mid.
    sell_fees are on selling N x F shares at the raw exit price."""
    n = notional / entry_mid
    shares = n * F
    gross = shares * exit_price
    return (gross * (1.0 - c_out) - fees.sale_fees(exit_day, shares, gross) + n * cash) / (n * entry_mid * (1.0 + c_in)) - 1.0


TERMINAL_ZERO_NET = -1.0
