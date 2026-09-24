"""Byte-for-byte copies of definitions from blueprints/us-equities/mover-early-entry/rules.py at aa6fc79 (git blob 9be164c9e1a49a451d3a2381205349ed5003a993).

Listed in study/pinned_copies.json and checked against that blob by tests/test_pinned_copies.py.
Nothing else from the source module is copied, so its module-level code never runs here.
"""
from __future__ import annotations

from datetime import date, datetime, time as dtime
from functools import lru_cache
from zoneinfo import ZoneInfo

import numpy as np


ET = ZoneInfo("America/New_York")


TIME_BUCKETS = (("04:00", "08:00"), ("08:00", "09:30"), ("09:30", "10:00"), ("10:00", "16:01"))


PRICE_TIERS = (2.0, 5.0, 20.0)


DV_TIERS = (1_000_000.0, 5_000_000.0)


@lru_cache(maxsize=None)
def et_epoch(day: str, hhmm: str) -> float:
    h, m = map(int, hhmm.split(":"))
    return datetime.combine(date.fromisoformat(day), dtime(h, m), ET).timestamp()


class Bars:
    """One symbol-day's 1-minute bars as arrays (sorted, one bar per start time, from 04:00)."""

    def __init__(self, t, o, h, l, c, v, vw, day_start: float):
        keep = np.asarray(t, dtype=float) >= day_start
        self.t = np.asarray(t, dtype=float)[keep]
        self.o = np.asarray(o, dtype=float)[keep]
        self.h = np.asarray(h, dtype=float)[keep]
        self.l = np.asarray(l, dtype=float)[keep]
        self.c = np.asarray(c, dtype=float)[keep]
        self.dv = np.asarray(vw, dtype=float)[keep] * np.asarray(v, dtype=float)[keep]
        self.cumdv = np.cumsum(self.dv)

    @classmethod
    def from_rows(cls, rows, day_start):
        cols = list(zip(*[(b["t"], b["o"], b["h"], b["l"], b["c"], b["v"], b.get("vw") or b["c"]) for b in rows])) or [()] * 7
        return cls(*cols, day_start=day_start)

    def __len__(self):
        return len(self.t)

    def index(self, ts: float) -> int:
        """Number of bars starting before ts."""
        return int(np.searchsorted(self.t, ts, side="left"))

    def state(self, ts: float):
        """(price_at_ts, dollar_volume_at_ts): last close and summed vwap x volume of bars starting before ts."""
        i = self.index(ts)
        return (float(self.c[i - 1]), float(self.cumdv[i - 1])) if i else (None, 0.0)

    def cum_dv(self, ts: float) -> float:
        i = self.index(ts)
        return float(self.cumdv[i - 1]) if i else 0.0


def time_bucket(day: str, ts: float):
    for i, (a, b) in enumerate(TIME_BUCKETS):
        if et_epoch(day, a) <= ts < et_epoch(day, b):
            return i
    return None


def price_tier(p: float) -> int:
    return int(np.searchsorted(PRICE_TIERS, p, side="right"))


def dv_tier(dv: float) -> int:
    return int(np.searchsorted(DV_TIERS, dv, side="right"))
