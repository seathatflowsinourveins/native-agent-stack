"""SYN: news-forward auto-leverage (evidence gate, shrinkage, fractional Kelly) and its
composition with the adaptive-paper leverage.py caps (session schedule, overnight Reg T
cap, drawdown ladder, kill switch, account multiplier). Synthetic returns only.
"""

import math
import sys
import unittest
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "blueprints/us-equities/sota-mover/news-forward"))

import autolev  # noqa: E402

E = Decimal("900000")


def rows(values, trips=10, label="confirmatory", flat=True):
    return [{"session": f"2026-10-{i + 1:02d}" if i < 31 else f"2026-11-{i - 30:02d}", "evidence_label": label,
             "net_return_on_gross": v, "round_trips": trips, "core_flat": flat} for i, v in enumerate(values)]


def cap(**kw):
    base = dict(equity=E, session="RTH", drawdown_fraction=0, kill_switch=False, account_multiplier="4", overnight=False)
    base.update(kw)
    return autolev.policy_ceiling(**base)


class Statistics(unittest.TestCase):
    def test_shrunk_mean(self):
        self.assertEqual(autolev.shrunk_mean([]), 0.0)
        self.assertAlmostEqual(autolev.shrunk_mean([0.001] * 20), 20 * 0.001 / 80)
        self.assertAlmostEqual(autolev.shrunk_mean([0.002] * 60), 0.001)

    def test_ewma_sigma(self):
        self.assertIsNone(autolev.ewma_sigma([0.01]))
        self.assertIsNone(autolev.ewma_sigma([0.01, 0.01]))
        xs = [0.01, -0.01] * 10
        self.assertAlmostEqual(autolev.ewma_sigma(xs), 0.01, places=3)
        # the latest observation carries weight 1, one 20 sessions older 0.5
        n = 21
        weights = [0.5 ** ((n - 1 - i) / 20) for i in range(n)]
        self.assertAlmostEqual(weights[0], 0.5)
        self.assertAlmostEqual(weights[-1], 1.0)

    def test_lower_bound(self):
        xs = [0.004, 0.006] * 10
        s = math.sqrt(sum((x - 0.005) ** 2 for x in xs) / 19)
        self.assertAlmostEqual(autolev.lower_bound_95(xs), 0.005 - 1.645 * s / math.sqrt(20))


class Gate(unittest.TestCase):
    GOOD = [0.004, 0.006] * 20  # 40 sessions, mean 0.005, sd ~0.001

    def test_one_row_per_session_and_flat_days_only(self):
        base = rows(self.GOOD, trips=10)
        duplicated = base + [dict(base[0], net_return_on_gross=-0.5)]  # a second reconciliation of day 1
        kept = autolev.counted(duplicated)
        self.assertEqual(len(kept), 40)
        self.assertEqual(kept[0]["net_return_on_gross"], -0.5)  # the last row written for a session wins
        not_flat = rows(self.GOOD, trips=10)
        not_flat[5]["core_flat"] = False
        self.assertEqual(len(autolev.counted(not_flat)), 39)
        self.assertEqual(autolev.counted(rows([0.01] * 3, flat=False)), [])

    def test_pilot_rows_are_excluded(self):
        level, inputs = autolev.kelly_leverage(rows(self.GOOD, trips=10, label="pilot"))
        self.assertEqual((level, inputs["n_sessions"], inputs["gate_passed"]), (Decimal("1.0"), 0, False))

    def test_execution_test_rows_are_excluded(self):
        # the overnight core arm is an execution test once its study (NEWS-1) failed: never evidence for leverage
        level, inputs = autolev.kelly_leverage(rows(self.GOOD, trips=10, label="execution_test"))
        self.assertEqual((level, inputs["n_sessions"], inputs["gate_passed"]), (Decimal("1.0"), 0, False))

    def test_needs_20_sessions(self):
        level, inputs = autolev.kelly_leverage(rows(self.GOOD[:19], trips=10))
        self.assertFalse(inputs["gate"]["n_ge_20"])
        self.assertEqual(level, Decimal("1.0"))

    def test_needs_100_round_trips(self):
        level, inputs = autolev.kelly_leverage(rows(self.GOOD, trips=2))
        self.assertEqual(inputs["round_trips"], 80)
        self.assertFalse(inputs["gate"]["round_trips_ge_100"])
        self.assertEqual(level, Decimal("1.0"))

    def test_needs_positive_lower_bound(self):
        level, inputs = autolev.kelly_leverage(rows([0.02, -0.019] * 20, trips=10))
        self.assertFalse(inputs["gate"]["lower_bound_95_gt_0"])
        self.assertEqual(level, Decimal("1.0"))

    def test_passing_gate_uses_quarter_kelly(self):
        level, inputs = autolev.kelly_leverage(rows(self.GOOD, trips=10))
        self.assertTrue(inputs["gate_passed"])
        mu = 40 * 0.005 / 100
        self.assertAlmostEqual(inputs["shrunk_mean"], mu)
        expected = 0.25 * mu / inputs["ewma_sigma"] ** 2
        self.assertAlmostEqual(inputs["kelly_quarter"], expected)
        self.assertEqual(level, Decimal(str(round(expected, 6))))


class Composition(unittest.TestCase):
    def test_policy_caps(self):
        self.assertEqual(cap(), Decimal("4"))
        self.assertEqual(cap(account_multiplier="1"), Decimal("1"))
        self.assertEqual(cap(account_multiplier=None), Decimal("4"))
        self.assertEqual(cap(drawdown_fraction="0.25"), Decimal("2"))
        self.assertEqual(cap(drawdown_fraction="0.5"), Decimal("1"))
        self.assertEqual(cap(drawdown_fraction="0.75"), Decimal("0"))
        self.assertEqual(cap(kill_switch=True), Decimal("0"))
        self.assertEqual(cap(session="PRE"), Decimal("1"))
        self.assertEqual(cap(session="POST", overnight=True), Decimal("1"))
        self.assertEqual(cap(overnight=True), Decimal("2"))  # Reg T overnight cap
        self.assertEqual(cap(session="CLOSED"), Decimal("0"))

    def test_decide_composes_min(self):
        good = rows(Gate.GOOD, trips=10)
        level, inputs = autolev.decide(good, equity=E, session="RTH", drawdown_fraction=0, kill_switch=False,
                                       account_multiplier="4")
        self.assertEqual(level, Decimal("4"))  # quarter Kelly is far above the policy cap
        self.assertEqual(inputs["policy_cap"], "4")
        level, _ = autolev.decide(good, equity=E, session="RTH", drawdown_fraction=Decimal("0.3"), kill_switch=False,
                                  account_multiplier="4")
        self.assertEqual(level, Decimal("2"))
        level, _ = autolev.decide(good, equity=E, session="RTH", drawdown_fraction=0, kill_switch=True, account_multiplier="4")
        self.assertEqual(level, Decimal("0"))

    def test_todays_pilot_is_one(self):
        level, inputs = autolev.decide(rows([0.01] * 30, label="pilot"), equity=E, session="RTH", drawdown_fraction=0,
                                       kill_switch=False, account_multiplier="4")
        self.assertEqual(level, Decimal("1.0"))
        self.assertEqual((inputs["l_autolev"], inputs["policy_cap"], inputs["l_final"]), ("1.0", "4", "1.0"))

    def test_drawdown_fraction(self):
        self.assertEqual(autolev.drawdown_fraction("100", "75"), Decimal("0.25"))
        self.assertEqual(autolev.drawdown_fraction("100", "120"), Decimal("0"))


if __name__ == "__main__":
    unittest.main()
