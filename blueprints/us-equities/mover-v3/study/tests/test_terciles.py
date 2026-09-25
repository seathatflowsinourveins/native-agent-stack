"""tercile_rule: trailing breakpoints, assignment ties, the 60-event minimum, validation-only and holdout pools."""
import unittest

import numpy as np

from core import terciles as TC
from tests import synth


class Terciles(unittest.TestCase):
    def setUp(self):
        self.cal = synth.calendar("2015-09-01", "2021-06-30")

    def test_breakpoints_linear_quantiles_of_the_trailing_window(self):
        pool = self.cal.range("2020-01-02", "2020-12-31")
        by = {d: [float(i)] for i, d in enumerate(pool[:100])}
        s = pool[100]
        bps = TC.breakpoints(pool, by, s)
        q = np.quantile(np.arange(100, dtype=float), [1 / 3, 2 / 3], method="linear")
        self.assertAlmostEqual(bps[0], q[0])
        self.assertAlmostEqual(bps[1], q[1])
        # the event's own session is not in its window
        by[s] = [1000.0]
        self.assertEqual(TC.breakpoints(pool, by, s), bps)

    def test_minimum_60_prior_events(self):
        pool = self.cal.range("2020-01-02", "2020-12-31")
        by = {d: [1.0] for d in pool[:59]}
        self.assertIsNone(TC.breakpoints(pool, by, pool[59]))
        by[pool[59]] = [2.0]
        self.assertIsNotNone(TC.breakpoints(pool, by, pool[60]))

    def test_minimum_counts_prior_events_with_a_defined_max21(self):
        # review round 10, F7: 59 prior events with a defined MAX21 and 30 with an undefined one are fewer than 60
        # (tercile_rule.minimum counts D events with a defined MAX21), both in breakpoints and in assign_terciles
        from core import evaluate as EV
        pool = self.cal.range("2020-01-02", "2020-12-31")
        by = {d: [1.0 + i % 7] for i, d in enumerate(pool[:59])}
        for d in pool[:30]:
            by[d].append(None)
        self.assertIsNone(TC.breakpoints(pool, by, pool[89]))
        events = [{"symbol": f"S{i}", "t": d, "max21": m} for i, d in enumerate(pool[:59]) for m in by[d]]
        events.append({"symbol": "LATE", "t": pool[89], "max21": 3.0})
        terc = EV.assign_terciles(events, pool, lambda ev: ev["symbol"] == "LATE")
        self.assertIsNone(terc[("LATE", pool[89])])
        events.append({"symbol": "S60", "t": pool[60], "max21": 2.0})
        terc = EV.assign_terciles(events, pool, lambda ev: ev["symbol"] == "LATE")
        self.assertIsNotNone(terc[("LATE", pool[89])])

    def test_window_is_252_kept_sessions(self):
        pool = self.cal.range("2019-01-02", "2020-12-31")
        s = pool[300]
        w = TC.trailing_window(pool, s)
        self.assertEqual(len(w), 252)
        self.assertEqual(w[-1], pool[299])

    def test_assignment_ties_go_lower(self):
        self.assertEqual(TC.assign(0.1, (0.1, 0.2)), "low")
        self.assertEqual(TC.assign(0.2, (0.1, 0.2)), "middle")
        self.assertEqual(TC.assign(0.2000001, (0.1, 0.2)), "high")
        self.assertIsNone(TC.assign(None, (0.1, 0.2)))
        self.assertIsNone(TC.assign(0.5, None))

    def test_validation_pool_has_no_development_session(self):
        pool = TC.pool_validation(self.cal)
        self.assertEqual(pool[0], "2020-01-02")
        self.assertTrue(all(d.startswith("2020") for d in pool))
        dev = TC.pool_development(self.cal)
        self.assertEqual(dev[0], "2016-01-04")
        self.assertNotIn("2018-05-01", TC.pool_development(self.cal, frozenset({2018})))

    def test_first_holdout_breakpoints_from_part_a_alone(self):
        cal = synth.calendar("2024-06-03", "2028-06-30")
        n0 = "2026-11-23"
        pool = TC.pool_holdout(cal, n0, cal.offset(n0, 251))
        self.assertNotIn("2026-06-01", pool)                       # the gap 2026-01-02 .. N0 - 1
        by = {d: [float(i % 7)] for i, d in enumerate(cal.range("2024-11-01", "2025-12-31"))}
        by["2026-06-01"] = [99.0]
        w = TC.trailing_window(pool, n0)
        self.assertEqual(w[-1], "2025-12-31")
        self.assertEqual(len(w), 252)
        self.assertIsNotNone(TC.breakpoints(pool, by, n0))
        self.assertLess(TC.breakpoints(pool, by, n0)[1], 99.0)


if __name__ == "__main__":
    unittest.main()
