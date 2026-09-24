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

    def test_undefined_rebooking_is_excluded_not_a_total_loss(self):
        """Review round 12, Codex P2: a terminal-zero trade with an eligible last bid but an undefined factor at the
        bid's session has no rebooked value; it leaves the sensitivity and is counted, never booked at -1."""
        recs = [rec(i, 0.02) for i in range(20)]
        recs.append(rec(20, -1.0, exit="terminal_zero", terminal_rebooked_at_last_bid=None))
        recs.append(rec(21, -1.0, exit="terminal_zero"))        # no eligible bid: stays at -1
        res = EV.item_result("H3-a", "validation", rows(recs), SESSIONS, PID, B=50)
        sens = res["sensitivities"]
        self.assertAlmostEqual(sens["terminal_zero_rebooked_at_last_bid"], (20 * 0.02 - 1.0) / 21)
        self.assertEqual(sens["terminal_zero_rebooked_undefined_factor_n"], 1)
        self.assertAlmostEqual(res["estimate"], (20 * 0.02 - 2.0) / 22)   # the primary is unchanged

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


class OppositeDirection(unittest.TestCase):
    def test_opposite_direction_is_flagged_with_its_interval(self):
        """Review round 11, C12: a result opposite a one-sided alternative, or H3-c at the holdout opposite the
        validation sign, is flagged and carries its estimate and 95% interval; it never passes."""
        self.assertTrue(EV.opposite_direction("H3-a", "validation", -0.02))
        self.assertFalse(EV.opposite_direction("H3-a", "validation", 0.02))
        self.assertTrue(EV.opposite_direction("H1-D", "validation", 0.01))          # alternative 'less'
        self.assertFalse(EV.opposite_direction("H3-c", "validation", -0.01, 0.004))  # two-sided before the holdout
        self.assertTrue(EV.opposite_direction("H3-c", "holdout", -0.01, 0.004))
        self.assertFalse(EV.opposite_direction("H3-c", "holdout", 0.01, 0.004))
        recs = [rec(i, -0.05 - 0.001 * (i % 3)) for i in range(40)]
        res = EV.item_result("H3-a", "validation", rows(recs), SESSIONS, PID, B=200)
        lo, hi = res["interval_95"]
        self.assertLess(hi, 0.0)
        self.assertLessEqual(lo, res["estimate"])
        self.assertGreater(res["p"], 0.5)
        label = ST.item_label("validation", "H3-a", p_stage=res["p"], n_ok=True, robust_ok=False,
                              mde_ok=res["mde_excluded"])
        self.assertNotEqual(label, "screened")


def run_evaluate(stage, item_rows, trades=(), **kw):
    """evaluate() with item_trades and build_trades replaced: item_rows {item: rows}."""
    with mock.patch.object(EV, "item_trades", lambda item, t, h: item_rows.get(item, [])), \
            mock.patch.object(EV, "build_trades", lambda *a, **k: (list(trades), [], [])):
        return EV.evaluate(stage, [], mock.Mock(fees=None), None, protocol_id=PID, stage_sessions=SESSIONS, pool=[],
                           **kw)


def h3c_rows(n, value):
    return [{"session": SESSIONS[i % len(SESSIONS)], "value": value + 0.002 * (i % 5),
             "rec": {"symbol": f"S{i % 7}", "status": "complete"}} for i in range(n)]


class StageRules(unittest.TestCase):
    def test_holdout_h3c_opposite_to_the_validation_sign_does_not_pass(self):
        """Review round 12, F2 (multiple_testing.no_direction_lock): the sign check inside evaluate()."""
        rows = {"H3-c": h3c_rows(200, 0.02)}
        same = run_evaluate("holdout", rows, carried=("H3-c",), validation_signs={"H3-c": 0.004}, B=400)
        self.assertEqual(same["labels"]["H3-c"], "supported (confirmatory)")
        self.assertFalse(same["items"]["H3-c"]["opposite_direction"])
        opp = run_evaluate("holdout", rows, carried=("H3-c",), validation_signs={"H3-c": -0.004}, B=400)
        self.assertLessEqual(opp["items"]["H3-c"]["p_stage"], 0.05)
        self.assertNotEqual(opp["labels"]["H3-c"], "supported (confirmatory)")
        self.assertTrue(opp["items"]["H3-c"]["opposite_direction"])
        none = run_evaluate("holdout", rows, carried=("H3-c",), validation_signs=None, B=400)
        self.assertNotEqual(none["labels"]["H3-c"], "supported (confirmatory)")

    def test_void_and_untested_stages_score_p_one_even_for_a_significant_item(self):
        """Review round 12, F3: the fixture has an item whose Holm p is below 1 when the stage is not void."""
        rows = {"H3-a": rows_of(200, 0.05)}
        base = run_evaluate("validation", rows, B=400)
        self.assertLess(base["items"]["H3-a"]["p_stage"], 0.05)
        self.assertEqual(base["labels"]["H3-a"], "screened")
        for kw in ({"void": {"void": True, "rate": 0.02}}, {"tested": False}):
            res = run_evaluate("validation", rows, B=400, **kw)
            self.assertTrue(all(r["p_stage"] == 1.0 for r in res["items"].values()), kw)
            self.assertEqual(res["labels"]["H3-a"], "underpowered", kw)

    def test_an_opposite_estimate_is_passed_to_the_label(self):
        """Review round 12, F9: evaluate() hands opposite_direction to item_label for one-sided items."""
        seen = {}

        def spy(stage, item, **kw):
            seen[item] = kw.get("opposite")
            return "underpowered"
        with mock.patch.object(ST, "item_label", spy):
            run_evaluate("validation", {"H3-a": rows_of(40, -0.05), "H3-b": rows_of(40, 0.05)}, B=50)
        self.assertEqual((seen["H3-a"], seen["H3-b"], seen["H3-c"]), (True, False, False))

    def test_descriptive_b_lane_high_and_middle_cells(self):
        """Review round 12, F8: the descriptive H1 cells (outcome_reporting.validation_reporting)."""
        trades = [dict(rec(i, 0.01 * (i + 1)), t=SESSIONS[i], tercile=("middle" if i < 3 else "high" if i < 5 else "low"))
                  for i in range(7)]
        res = run_evaluate("validation", {}, trades=trades, B=50)
        self.assertEqual(res["descriptive"]["b_lane_middle"]["n"], 3)
        self.assertAlmostEqual(res["descriptive"]["b_lane_middle"]["mean"], 0.02)
        self.assertEqual(res["descriptive"]["b_lane_high"]["n"], 2)
        self.assertAlmostEqual(res["descriptive"]["b_lane_high"]["mean"], 0.045)
        self.assertEqual(set(res["descriptive"]), {"b_lane_high", "b_lane_middle"})


def rows_of(n, value):
    return rows([rec(i, value + 0.002 * (i % 5)) for i in range(n)])


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
