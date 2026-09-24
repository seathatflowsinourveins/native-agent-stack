"""holdout_gate.prospective_collection: the collector's plan (screen only, asof = s, the enumeration refresh and the
rename-day re-fetch), timeliness and late-collected sessions."""
import unittest

from core import identity, plan
from tests import synth


class Collection(unittest.TestCase):
    def setUp(self):
        self.cal = synth.calendar("2026-06-01", "2027-06-30")

    def test_batch_is_screen_only_with_asof_the_session(self):
        cal = self.cal
        sessions = cal.range("2026-10-05", "2026-10-09")
        rn = [{"type": "name_change", "old_symbol": "OLDN", "new_symbol": "NEWN", "date": "2026-10-02"}]
        reqs = plan.collection_requests(cal, sessions, ["AAA", "BBB"], rn, "2026-10-10")
        kinds = {r["kind"] for r in reqs}
        self.assertFalse(any("quote" in k or "minute" in k for k in kinds))
        self.assertIn("corporate_actions", kinds)
        self.assertEqual(sum(r["kind"] == "assets" for r in reqs), 2)
        for r in reqs:
            identity.check_asof(r if not r["kind"].startswith("rename_refetch_") else {**r, "kind": r["kind"][15:]})
        screen = [r for r in reqs if r["kind"] == "screen_daily_raw"]
        self.assertEqual({r["params"]["asof"] for r in screen}, set(sessions))
        refetch = [r for r in reqs if r["kind"].startswith("rename_refetch_")]
        self.assertEqual(len(refetch), 4)
        self.assertTrue(all(r["params"]["symbols"] == "NEWN" and r["params"]["asof"] == "2026-10-02" for r in refetch))
        self.assertEqual(len({r["key"] for r in reqs}), len(reqs))

    def test_holdout_event_lookback_never_reaches_the_reserved_window(self):
        """Review round 9, L-5: a holdout event's daily bars start at t-22; for the earliest possible freeze
        (2026-09-25) the first holdout decision N0 - 1 still looks back no earlier than 2026-09-21."""
        from core import chronology as CH
        from core import events as EVS
        cal = synth.calendar("2026-01-02", "2028-06-30")
        freeze = cal.at("2026-09-25", "12:00")
        t = cal.offset(CH.n0(cal, freeze), -1)
        reqs = plan.event_requests(cal, "ABC", t, cal.offset(t, 10), holdout=True)
        self.assertGreaterEqual(min(r["params"]["start"][:10] for r in reqs), "2026-09-21")
        self.assertEqual(plan.event_requests(cal, "ABC", t, cal.offset(t, 10))[0]["params"]["start"],
                         cal.offset(t, -60))                          # development and validation keep t-60
        self.assertEqual(plan.per_event_requests_max(), 58)
        from collections import Counter
        from tests.test_trades import make_event
        c2 = synth.calendar()
        ev = make_event(c2, "2020-06-01")
        data = {"incomplete": [], "empty": [], "daily": {"raw": ev["raw"], "split": ev["split"], "all": ev["all"]},
                "minute": ev["minute"], "prints": ev["prints"]}
        cand = {"symbol": "MOVR", "t": "2020-06-01"}
        self.assertIsNone(EVS.build_event(c2, cand, data, Counter(), holdout=True)["least_exposed"])
        self.assertIsInstance(EVS.build_event(c2, cand, data, Counter())["least_exposed"], bool)

    def test_late_collected_sessions(self):
        cal = self.cal
        b1 = {"sessions": cal.range("2026-10-05", "2026-10-09"), "reachable": cal.at("2026-10-12", "09:00")}
        b2 = {"sessions": cal.range("2026-10-12", "2026-10-16"), "reachable": cal.at("2026-10-19", "09:30")}
        b3 = {"sessions": cal.range("2026-10-19", "2026-10-23"), "reachable": None}
        late = plan.late_collected(cal, [b1, b2, b3])
        self.assertEqual(late, b2["sessions"] + b3["sessions"])


if __name__ == "__main__":
    unittest.main()
