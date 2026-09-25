"""cost_model and the net-return formula of populations.corporate_actions.

Cost cell (review round 8, R8-12): time_bucket, price_tier and dv_tier are the pinned copies of rules.py at
aa6fc79, so the intervals are half-open: time buckets [04:00, 08:00), [08:00, 09:30), [09:30, 10:00),
[10:00, 16:01) ET; price tiers [0, 2), [2, 5), [5, 20), [20, inf); dv tiers [0, 1M), [1M, 5M), [5M, inf).
A boundary value goes to the upper tier ($5.00 is in $5-20).

Fees: SEC Section 31 at usd_per_million x sell value / 1e6 plus FINRA TAF min(usd_per_share x shares,
max_usd_per_trade), unrounded, from data/fees-v3.json and its append-only amendments; commission 0.
"""
from __future__ import annotations

import functools
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


SEC_UNIT = "US dollars per million dollars of covered sales"
TAF_UNIT = "US dollars per share sold, capped per trade"
OPEN_END = "9999-12-31"          # the internal end of a row whose 'to' is null (open-ended)
FEE_TABLES = {"sec_section31": ("sec_section31", SEC_UNIT, ("usd_per_million",)),
              "finra_taf_covered_equity": ("finra_taf_covered_equity", TAF_UNIT,
                                           ("usd_per_share", "max_usd_per_trade"))}


class FeeSchemaError(ValueError):
    pass


# ---------------------------------------------------------------- charge dates (cost_model.fee_charge_dates)
# Review round 15, fee-date item. The simulated sale is a regular-way sale of an exchange-listed equity executed on an
# exchange and cleared and settled through NSCC. Its SEC Section 31 charge date is its settlement date (17 CFR
# 240.31(a)(3)(i): a covered sale a covered SRO reports from data it receives from a designated clearing agency;
# Release 34-49928: 'the settlement date also should be used as the charge date for all covered sales that a covered
# exchange reports to NSCC'), and the FINRA TAF applies to the transaction (trade) date. The settlement cycle is the
# one in force on the trade date: T+3 before 2017-09-05, T+2 from 2017-09-05 (SEC statement 2017-163), T+1 from
# 2024-05-28 (SEC press release 2023-29: the compliance date). A settlement day is a session of the calendar that is
# not a Federal Reserve holiday on which the exchange opens (Columbus Day and Veterans Day, as the Federal Reserve
# observes them), since no settlement occurs on a bank holiday.
T2_FIRST_TRADE = "2017-09-05"
T1_FIRST_TRADE = "2024-05-28"


def settlement_cycle(trade_session: str) -> int:
    """k of T+k for a trade on this session."""
    return 3 if trade_session < T2_FIRST_TRADE else (2 if trade_session < T1_FIRST_TRADE else 1)


@functools.lru_cache(maxsize=None)
def bank_only_holidays(year: int) -> frozenset:
    """Federal Reserve holidays that can fall on an exchange session: Columbus Day (the second Monday of October)
    and Veterans Day (November 11; on a Sunday the Federal Reserve closes the Monday after, on a Saturday it stays
    open on the Friday before)."""
    from datetime import date, timedelta
    oct1 = date(year, 10, 1)
    columbus = oct1 + timedelta(days=(0 - oct1.weekday()) % 7 + 7)
    vet = date(year, 11, 11)
    out = {columbus.isoformat()}
    if vet.weekday() == 6:
        out.add((vet + timedelta(days=1)).isoformat())
    elif vet.weekday() < 5:
        out.add(vet.isoformat())
    return frozenset(out)


def settlement_date(cal, trade_session: str):
    """The settlement date of a regular-way sale on trade_session: the k-th settlement day after it (k =
    settlement_cycle); None when trade_session is not a session or the calendar ends first."""
    if not cal.is_session(trade_session):
        return None
    k, d = settlement_cycle(trade_session), trade_session
    while k:
        d = cal.offset(d, 1)
        if d is None:
            return None
        if d not in bank_only_holidays(int(d[:4])):
            k -= 1
    return d


def _fee_rows(base: dict, kind: str) -> list:
    """The rows of one table of data/fees-v3.json, normalized to {"from", "to", <rate fields>} with an open end as
    OPEN_END (review round 15, N01: the file's sec_section31.rows[].usd_per_million and
    finra_taf_covered_equity.rows[].usd_per_share / max_usd_per_trade, a null 'to' on the open-ended last row)."""
    from core.amendments import _is_date, _is_rate
    key, unit, fields = FEE_TABLES[kind]
    table = base.get(key)
    if not isinstance(table, dict) or table.get("unit") != unit or not isinstance(table.get("rows"), list) \
            or not table["rows"]:
        raise FeeSchemaError(f"fees: {key} must hold a non-empty rows list in '{unit}'")
    out = []
    for i, r in enumerate(table["rows"]):
        if not isinstance(r, dict) or not _is_date(r.get("from")) or \
                (r.get("to") is not None and not _is_date(r.get("to"))) or \
                not all(_is_rate(r.get(f)) for f in fields):
            raise FeeSchemaError(f"fees: {key} row {i} needs from, to (a date or null) and {', '.join(fields)} >= 0")
        out.append({"from": r["from"], "to": r["to"] or OPEN_END, **{f: float(r[f]) for f in fields}})
    return out


class Fees:
    """Review round 14, F2: the base file's rows of one kind never overlap and each has from <= to (a base that
    breaks this is refused at load, never at a read). An amendment line supersedes, for the dates it covers, every
    earlier row of its kind (the base's open-ended last row included): the latest appended line that covers a date
    governs, and a base row governs a date no amendment line covers. No line is edited; supersession is by
    precedence. core.holdout.require_fee_coverage checks that every date a count or read can book has a row before
    that action fetches anything.

    Review round 15, N01 and the amendment-format item: the base is data/fees-v3.json in its committed schema
    (schema_version 1; sec_section31 and finra_taf_covered_equity, each with its unit and rows; a null 'to' is the
    open end), and every amendment line conforms to run_discipline.amendment_format (core.amendments).

    Review round 15, fee-date item: a sale on trade session d pays the SEC row that governs its charge date,
    settlement_date(cal, d), and the TAF row that governs d itself (cost_model.fee_charge_dates). cal is the session
    calendar the settlement days come from (the amended calendar at a run)."""

    def __init__(self, base: dict, amendments: list[dict] = (), freeze_session: str | None = None, *, cal):
        """freeze_session, when given, refuses an amendment line whose first date precedes it (review round 9, F5);
        from_files requires it whenever the amendment file has a line."""
        from core.amendments import fee_line_problems
        self.cal = cal
        if not isinstance(base, dict) or base.get("schema_version") != 1:
            raise FeeSchemaError("fees: schema_version must be 1")
        self.sec = _fee_rows(base, "sec_section31")
        self.taf = _fee_rows(base, "finra_taf_covered_equity")
        for name, rows in (("SEC", self.sec), ("TAF", self.taf)):
            spans = sorted((r["from"], r["to"]) for r in rows)
            for lo, hi in spans:
                if lo > hi:
                    raise FeeSchemaError(f"a base {name} fee row runs from {lo} to {hi}")
            for (_, hi), (lo, _) in zip(spans, spans[1:]):
                if lo <= hi:
                    raise FeeSchemaError(f"base {name} fee rows overlap on {lo}")
        self.sec_amend, self.taf_amend = [], []
        for i, a in enumerate(amendments):
            problems = fee_line_problems(a)
            if problems:
                raise ValueError(f"fee amendment line {i}: {'; '.join(problems)}")
            if freeze_session is not None and a["from"] < freeze_session:
                raise ValueError(f"fee amendment starts {a['from']}, before the freeze session")
            fields = FEE_TABLES[a["kind"]][2]
            row = {"from": a["from"], "to": a["to"] or OPEN_END, **{f: float(a[f]) for f in fields}}
            (self.sec_amend if a["kind"] == "sec_section31" else self.taf_amend).append(row)

    @classmethod
    def from_files(cls, base_path, amendments_path=None, *, freeze_session: str | None = None, cal):
        base = json.loads(Path(base_path).read_text(encoding="utf-8"))
        lines = []
        if amendments_path and Path(amendments_path).exists():
            lines = [json.loads(x) for x in Path(amendments_path).read_text(encoding="utf-8").splitlines() if x.strip()]
        if lines and freeze_session is None:
            raise ValueError("a fee amendment line applies only with the freeze session known")
        return cls(base, lines, freeze_session=freeze_session, cal=cal)

    @staticmethod
    def _row(rows, amended, day):
        for r in reversed(amended):
            if r["from"] <= day <= r["to"]:
                return r
        hit = [r for r in rows if r["from"] <= day <= r["to"]]
        if len(hit) != 1:
            raise KeyError(f"{len(hit)} fee rows for {day}")
        return hit[0]

    def charge_date(self, day: str) -> str:
        """The SEC charge date (the settlement date) of a sale on trade session `day`; KeyError when the calendar
        cannot give it (not a session, or the calendar ends first), which gaps() reports as a gap."""
        s = settlement_date(self.cal, day)
        if s is None:
            raise KeyError(f"no settlement date for a sale on {day} on the session calendar")
        return s

    def rates(self, day: str):
        """(SEC usd_per_million, TAF usd_per_share, TAF max_usd_per_trade) governing a sale on trade session `day`:
        the SEC row of its charge date, the TAF row of the trade date."""
        taf = self._row(self.taf, self.taf_amend, day)
        return self._row(self.sec, self.sec_amend, self.charge_date(day))["usd_per_million"], \
            taf["usd_per_share"], taf["max_usd_per_trade"]

    def gaps(self, days) -> list:
        """The trade sessions of `days` with no governing SEC row at their charge date or no TAF row."""
        out = []
        for d in days:
            try:
                self.rates(d)
            except KeyError:
                out.append(d)
        return out

    def sale_fees(self, day: str, shares: float, sell_value: float) -> float:
        """The SEC fee and the TAF of selling `shares` for `sell_value` dollars on trade session `day`."""
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
    if not cash_defined(cal, raw, split, allc, e, x):
        return None
    r_e = raw[e]
    days = _cash_days(cal, split, allc, e, x)
    a_e = float(r_e["c"]) / float(split[e]["c"])
    total = 0.0
    for p_, k in zip(days, days[1:]):
        step = _dividend_step(split, allc, p_, k)
        if abs(step) > C["cash_band"]:
            total += float(split[p_]["c"]) * step
    cash = a_e * total
    return cash if abs(cash) > C["cash_band"] * float(r_e["c"]) else 0.0


def _cash_days(cal, split, allc, e, x) -> list:
    return [d for d in cal.range(e, x) if (split.get(d) or {}).get("c") and (allc.get(d) or {}).get("c")]


def _dividend_step(split, allc, p_, k) -> float:
    """s_k = 1 - D(p) / D(k), D(d) = all_c(d) / split_c(d): a ratio of two adjustment factors, each a ratio of two
    closes of one session (never a price level or a return)."""
    return 1.0 - (allc[p_]["c"] / split[p_]["c"]) / (allc[k]["c"] / split[k]["c"])


def cash_defined(cal, raw: dict, split: dict, allc: dict, e: str, x: str) -> bool:
    """Whether cash_term is defined, from bar presence and the adjustment factors D(d) alone (review round 15, F05):
    the raw bar of e and the split and all bars of e and x exist, and no step outside the 2e-3 band spans a session
    without its split or all bar. It computes no amount, so the holdout count path (count_unit) applies the same
    eligibility as the read without a price; cash_term is None exactly when this is False."""
    r_e = raw.get(e)
    sessions = cal.range(e, x)
    days = _cash_days(cal, split, allc, e, x)
    if not r_e or not r_e.get("c") or not days or days[0] != e or days[-1] != x:
        return False
    pos = {d: i for i, d in enumerate(sessions)}
    for p_, k in zip(days, days[1:]):
        if abs(_dividend_step(split, allc, p_, k)) > C["cash_band"] and pos[k] - pos[p_] != 1:
            return False
    return True


def trade_net_return(notional, entry_mid, exit_price, F, cash, c_in, c_out, fees: Fees, exit_day: str) -> float:
    """net = (N F exit_mid (1 - c_out) - sell_fees + N cash) / (N entry_mid (1 + c_in)) - 1, N = notional / entry_mid.
    sell_fees are on selling N x F shares at the raw exit price."""
    n = notional / entry_mid
    shares = n * F
    gross = shares * exit_price
    return (gross * (1.0 - c_out) - fees.sale_fees(exit_day, shares, gross) + n * cash) / (n * entry_mid * (1.0 + c_in)) - 1.0


TERMINAL_ZERO_NET = -1.0
