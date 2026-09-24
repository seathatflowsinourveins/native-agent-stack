"""core.evaluate per item (review round 9): the sensitivities of statistics.sensitivities (ratio rule, censored
trades, terminal rebooking without the backward-incomplete trades), the exit counts per group and per arm and year
(terminal_exits.in_statistics and booking), and the holdout contamination rule (chronology.holdout.accrual_exposure).
"""
import unittest
from unittest import mock

from core import evaluate as EV
from core import stats as ST

PID = "mover-v3-core-draft-20260924"
SESSIONS = [f"2020-{m:02d}-{d:02d}" for m in range(1, 7) for d in (6, 13, 20, 27)]


def rec(i, value, **kw):
    nets = {m: value for m in ("primary", "c0.5", "c2.0", "table_only", "stress")}
    base = {"symbol": f"S{i % 7}", "arm": "b_lane", "status": "filled", "exit": "normal", "entry_mid": 10.0,
            "entry_session": SESSIONS[i % len(SESSIONS)], "nets": nets, "primary_parts": None}
    base.update(kw)
    return base


def rows(recs, group=None):
    return [{"session": r["entry_session"], "value": r["nets"]["primary"], "group": group or r.get("tercile"),
             "rec": r} for r in recs]


class Sensitivities(unittest.TestCase):
    def test_ratio_rule_censored_and_rebooking(self):
        recs = [rec(i, 0.01 * (i % 5)) for i in range(20)]
        recs[3]["ratio_rule_in_hold"] = True
        recs[4]["censored"] = True
        recs.append(rec(20, -1.0, exit="terminal_zero", terminal_rebooked_at_last_bid=-0.2))
        recs.append(rec(21, -1.0, exit="terminal_zero", backward_incomplete=True))
        res = EV.item_result("H3-a", "validation", rows(recs), SESSIONS, PID, B=50)
        vals = [r["nets"]["primary"] for r in recs]
        sens = res["sensitivities"]
        self.assertAlmostEqual(sens["ratio_rule_holds_removed"], sum(v for i, v in enumerate(vals) if i != 3) / 21)
        self.assertAlmostEqual(sens["censored_removed"], sum(v for i, v in enumerate(vals) if i != 4) / 21)
        # rebooked at the last bid, and the backward-incomplete trade left out of this sensitivity only
        want = (sum(vals[:20]) - 0.2) / 21
        self.assertAlmostEqual(sens["terminal_zero_rebooked_at_last_bid"], want)
        self.assertEqual(res["n"], 22)

    def test_exit_counts_per_group_and_per_arm_and_year(self):
        recs = [rec(i, 0.01, exit="delayed" if i % 3 == 0 else "normal", tercile="high" if i % 2 else "low")
                for i in range(12)]
        recs[0]["exit"] = "terminal_zero"
        res = EV.item_result("H1-D", "validation", rows(recs), SESSIONS, PID, B=50)
        self.assertEqual(sum(sum(v.values()) for v in res["exits_by_group"].values()), 12)
        self.assertEqual(res["exits_by_group"]["low"]["terminal_zero"], 1)
        trades = [dict(r, no_merger_record=True) for r in recs[:1]] + [
            rec(30, -1.0, arm="b_overnight", exit="terminal_merger", entry_session="2019-03-04"),
            rec(31, -1.0, arm="b_overnight", exit="terminal_zero", entry_session="2019-03-05", merger_without_bid=True)]
        by = EV.terminal_by_arm_year(trades)
        self.assertEqual(by["b_lane"]["2020"], {"terminal_zero": 1, "no_merger_record": 1, "rename_record_in_window": 0,
                                                "merger_without_bid": 0})
        self.assertEqual(by["b_overnight"]["2019"]["terminal_merger"], 1)
        self.assertEqual(by["b_overnight"]["2019"]["merger_without_bid"], 1)


class Contamination(unittest.TestCase):
    def test_paper_exposed_fraction_above_5_percent_contaminates_a_holdout_item(self):
        seen = {}

        def spy(stage, item, **kw):
            seen[item] = kw.get("contaminated")
            return "underpowered" if kw.get("carried", True) else "not carried"
        recs = [rec(i, 0.02, paper_exposed=i < 2) for i in range(20)]          # 10% exposed
        with mock.patch.object(EV, "item_trades", lambda item, t, h: rows(recs) if item == "H3-a" else []), \
                mock.patch.object(EV, "build_trades", lambda *a, **k: ([], [], [])), \
                mock.patch.object(ST, "item_label", spy):
            out = EV.evaluate("holdout", [], mock.Mock(fees=None), None, protocol_id=PID, stage_sessions=SESSIONS,
                              pool=[], carried=("H3-a",), B=50)
        self.assertEqual(out["items"]["H3-a"]["paper_exposed_fraction"], 0.1)
        self.assertTrue(seen["H3-a"])
        self.assertEqual(out["labels"]["H3-b"], "not carried")
        self.assertNotIn("estimate", out["items"]["H3-b"])      # not carried: nothing computed (M-1)


if __name__ == "__main__":
    unittest.main()
