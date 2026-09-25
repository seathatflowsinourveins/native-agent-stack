"""Shadow tracking: SIP quotes at release, +15 and +60 minutes; never an order.

Tracked: every scored headline released in extended hours (04:00-09:30 or 16:00-20:00
ET, label ext_pre/ext_post) and every small-cap-lane headline in any session. A
snapshot whose due time is more than LATE_TOLERANCE old (e.g. after a restart or a
backfill) is recorded with ``late: true`` so it is never mistaken for an on-time quote.
"""

import heapq
import itertools
from datetime import timedelta

import common
import planner

LATE_TOLERANCE = timedelta(minutes=2)


class ShadowTracker:
    def __init__(self):
        self._heap = []
        self._seq = itertools.count()
        self._keys = set()

    def __len__(self):
        return len(self._heap)

    def add(self, event, reason, received_utc):
        """Schedule the three snapshots for one scored event (idempotent per event)."""
        for stage, due in planner.shadow_times(event["created_at"], received_utc):
            key = (event["event_id"], stage)
            if key in self._keys:
                continue
            self._keys.add(key)
            heapq.heappush(self._heap, (due, next(self._seq), stage, reason, event))

    def pop_due(self, now):
        out = []
        while self._heap and self._heap[0][0] <= now:
            due, _, stage, reason, event = heapq.heappop(self._heap)
            out.append((due, stage, reason, event))
        return out


def quote_record(due, stage, reason, event, quote, now):
    q = quote or {}
    return {
        "event_id": event["event_id"],
        "symbol": event["symbol"],
        "session_label": event.get("ext_segment") or event.get("session_label"),
        "trade_window": event.get("session_label"),
        "lane": event.get("lane"),
        "label": event.get("label"),
        "shadow_reason": reason,
        "stage": stage,
        "due_at": common.iso(due),
        "late": now - due > LATE_TOLERANCE,
        "bid": q.get("bp"),
        "ask": q.get("ap"),
        "bid_size": q.get("bs"),
        "ask_size": q.get("as"),
        "quote_time": q.get("t"),
        "spread_bps": str(planner.spread_bps(q["bp"], q["ap"])) if q.get("bp") and q.get("ap") and planner.spread_bps(q["bp"], q["ap"]) is not None else None,
    }
