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
    def __init__(self, base: dict, amendments: list[dict] = ()):
        self.sec = list(base["sec_section31_usd_per_million_of_sales"])
        self.taf = list(base["finra_taf_covered_equity_sales"])
        for a in amendments:
            if a.get("kind") == "sec_section31":
                self.sec.append(a)
            elif a.get("kind") == "finra_taf":
                self.taf.append(a)
            else:
                raise ValueError(f"unknown fee amendment kind {a.get('kind')!r}")
        if any(r.get("max_per_trade") is None for r in self.taf):
            raise ValueError("a TAF row must carry its max_per_trade cap")

    @classmethod
    def from_files(cls, base_path, amendments_path=None):
        base = json.loads(Path(base_path).read_text(encoding="utf-8"))
        lines = []
        if amendments_path and Path(amendments_path).exists():
            lines = [json.loads(x) for x in Path(amendments_path).read_text(encoding="utf-8").splitlines() if x.strip()]
        return cls(base, lines)

    @staticmethod
    def _row(rows, day):
        hit = [r for r in rows if r["from"] <= day <= r["to"]]
        if len(hit) != 1:
            raise KeyError(f"{len(hit)} fee rows for {day}")
        return hit[0]

    def rates(self, day: str):
        taf = self._row(self.taf, day)
        return self._row(self.sec, day)["rate"], taf["usd_per_share"], taf["max_per_trade"]

    def sale_fees(self, day: str, shares: float, sell_value: float) -> float:
        sec, taf, cap = self.rates(day)
        return sec * sell_value / 1e6 + min(taf * shares, cap)


def cash_term(raw_c_e, all_c_e, raw_c_x, all_c_x, F) -> float:
    """D7's cash per original share, raw_c(e) x all_c(x) / all_c(e) - F x raw_c(x), kept with its sign only when
    |cash| > 2e-3 x raw_c(e) (review round 8, E6: a symmetric band above the measured 6e-4 rounding noise)."""
    cash = raw_c_e * all_c_x / all_c_e - F * raw_c_x
    return cash if abs(cash) > C["cash_band"] * raw_c_e else 0.0


def trade_net_return(notional, entry_mid, exit_price, F, cash, c_in, c_out, fees: Fees, exit_day: str) -> float:
    """net = (N F exit_mid (1 - c_out) - sell_fees + N cash) / (N entry_mid (1 + c_in)) - 1, N = notional / entry_mid.
    sell_fees are on selling N x F shares at the raw exit price."""
    n = notional / entry_mid
    shares = n * F
    gross = shares * exit_price
    return (gross * (1.0 - c_out) - fees.sale_fees(exit_day, shares, gross) + n * cash) / (n * entry_mid * (1.0 + c_in)) - 1.0


TERMINAL_ZERO_NET = -1.0
