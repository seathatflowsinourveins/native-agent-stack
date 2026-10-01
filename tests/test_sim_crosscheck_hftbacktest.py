"""Hermetic checks for the hftbacktest L1 feasibility fixture
(blueprints/us-equities/sim-crosscheck-hftbacktest/).

This is OUR integration check (docs/acceptance-evidence-policy.md), not an
upstream test. It skips cleanly if `hftbacktest` is not importable on the
running interpreter -- it is a pinned dependency installed into an isolated
venv (~/.local/share/native-agent-stack/hftbacktest-2.4.4), not into the
repository's own CI Python, so a skip here is expected on hosts that have not
set up that venv. The structure-only tests at the bottom (lockfile contents,
receipt shape, tick-test classification -- none of which touch the
hftbacktest engine) run unconditionally.

Lives at the repository's top-level tests/ directory, not inside the
blueprint, so that `python3 -m unittest`'s bare discovery from the repo root
actually collects it. An earlier version of this file (at
blueprints/us-equities/sim-crosscheck-hftbacktest/tests/) never actually ran
in CI; the cause, verified with a minimal reproduction, is that `blueprints/`
(and every directory under it) has no `__init__.py`, so unittest's
package-based discovery never descended into that path at all -- it is
silently invisible to discovery, not a dotted-name collision with the
top-level `tests` package (which does have an `__init__.py`; an earlier
version of this docstring gave that wrong explanation). No other blueprint
in this repository keeps its own `tests/` subdirectory either way.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLUEPRINT = ROOT / "blueprints" / "us-equities" / "sim-crosscheck-hftbacktest"

try:
    import hftbacktest  # noqa: F401
    HFTBACKTEST_AVAILABLE = True
except ImportError:
    HFTBACKTEST_AVAILABLE = False


def _load_feasibility_module():
    spec = importlib.util.spec_from_file_location(
        "l1_feasibility", BLUEPRINT / "l1_feasibility.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@unittest.skipUnless(HFTBACKTEST_AVAILABLE, "hftbacktest is not installed on this interpreter")
class L1FeasibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load_feasibility_module()
        import hftbacktest.order as order_mod
        cls.order_mod = order_mod

    def test_time_in_force_constants_come_from_hftbacktest_order(self):
        # An earlier version of this module hardcoded FOK/IOC as bare
        # integers with a comment claiming they "are not exported as names"
        # from hftbacktest.order -- they are; this locks in importing them
        # for real instead of hardcoding.
        self.assertEqual(self.mod.GTC, self.order_mod.GTC)
        self.assertEqual(self.mod.GTX, self.order_mod.GTX)
        self.assertEqual(self.mod.FOK, self.order_mod.FOK)
        self.assertEqual(self.mod.IOC, self.order_mod.IOC)

    def test_marketable_ioc_fills_from_l1_depth_alone(self):
        result = self.mod.run_ioc_scenario(self.mod.build_scenario_a, submit_at_ns=1 * self.mod.NS)
        self.assertEqual(result["order_status"], self.order_mod.FILLED)
        self.assertAlmostEqual(result["exec_price"], 10.02, places=6)
        self.assertAlmostEqual(result["exec_qty"], 10.0, places=6)
        self.assertAlmostEqual(result["leaves_qty"], 0.0, places=6)

    def test_ioc_expires_when_touch_moves_away_before_arrival(self):
        result = self.mod.run_ioc_scenario(self.mod.build_scenario_b, submit_at_ns=50 * self.mod.MS)
        self.assertEqual(result["order_status"], self.order_mod.EXPIRED)
        self.assertAlmostEqual(result["exec_qty"], 0.0, places=6)
        self.assertAlmostEqual(result["leaves_qty"], 10.0, places=6)

    def test_queue_trade_depletion_requires_an_aggressor_side(self):
        result = self.mod.run_scenario_c()
        self.assertEqual(result["with_side"]["order_status"], self.order_mod.FILLED)
        self.assertEqual(result["without_side"]["order_status"], self.order_mod.NEW)
        self.assertGreater(result["with_side"]["exec_qty"], 0.0)
        self.assertAlmostEqual(result["without_side"]["exec_qty"], 0.0, places=6)

    def test_l1_verdict_is_unchanged_under_partial_fill_exchange_for_a_to_d(self):
        result_a = self.mod.run_ioc_scenario(
            self.mod.build_scenario_a, submit_at_ns=1 * self.mod.NS, exchange="partial_fill"
        )
        result_b = self.mod.run_ioc_scenario(
            self.mod.build_scenario_b, submit_at_ns=50 * self.mod.MS, exchange="partial_fill"
        )
        result_c = self.mod.run_scenario_c(exchange="partial_fill")
        self.assertEqual(result_a["order_status"], self.order_mod.FILLED)
        self.assertEqual(result_b["order_status"], self.order_mod.EXPIRED)
        self.assertEqual(result_c["with_side"]["order_status"], self.order_mod.FILLED)
        self.assertEqual(result_c["without_side"]["order_status"], self.order_mod.NEW)

    def test_scenario_d1_trade_through_requires_a_side_for_either_exchange_model(self):
        for exchange in ("no_partial_fill", "partial_fill"):
            result = self.mod.run_scenario_d_passive_fill_paths(exchange=exchange)
            self.assertEqual(
                result["d1_trade_through_with_side"]["order_status"], self.order_mod.FILLED, exchange
            )
            self.assertEqual(
                result["d1_trade_through_without_side"]["order_status"], self.order_mod.NEW, exchange
            )

    def test_scenario_d2_depth_zeroed_with_no_trade_never_fills(self):
        for exchange in ("no_partial_fill", "partial_fill"):
            result = self.mod.run_scenario_d_passive_fill_paths(exchange=exchange)
            self.assertEqual(result["d2_depth_zeroed_no_trade"]["order_status"], self.order_mod.NEW, exchange)
            self.assertAlmostEqual(result["d2_depth_zeroed_no_trade"]["exec_qty"], 0.0, places=6)

    def test_scenario_d3_opposite_quote_crossing_fills_with_no_trade_data(self):
        for exchange in ("no_partial_fill", "partial_fill"):
            result = self.mod.run_scenario_d_passive_fill_paths(exchange=exchange)
            self.assertEqual(result["d3_ask_crosses_down"]["order_status"], self.order_mod.FILLED, exchange)
            self.assertAlmostEqual(result["d3_ask_crosses_down"]["exec_qty"], 5.0, places=6)

    def test_scenario_e_optimistic_queue_bias_is_hand_verified(self):
        # HAND-VERIFIED: ProbQueueModel.depth()'s early-return path for a
        # quantity increase never touches the probability formula (see
        # run_scenario_e_optimistic_queue_bias's docstring for the full
        # trace), so this asserts the exactly hand-computed outcome.
        result = self.mod.run_scenario_e_optimistic_queue_bias()
        self.assertEqual(result["order_status"], self.order_mod.FILLED)
        self.assertAlmostEqual(result["exec_qty"], 5.0, places=6)
        self.assertAlmostEqual(result["exec_price"], 9.99, places=6)

    def test_scenario_f_exchange_models_genuinely_diverge_on_oversized_order(self):
        result = self.mod.run_scenario_f_exchange_model_divergence()
        no_partial = result["no_partial_fill"]
        partial = result["partial_fill"]
        self.assertEqual(no_partial["order_status"], self.order_mod.FILLED)
        self.assertAlmostEqual(no_partial["exec_qty"], 150.0, places=6)
        self.assertEqual(partial["order_status"], self.order_mod.EXPIRED)
        self.assertAlmostEqual(partial["exec_qty"], 100.0, places=6)
        self.assertAlmostEqual(partial["leaves_qty"], 50.0, places=6)
        self.assertNotEqual(no_partial["order_status"], partial["order_status"])

    def test_scenario_g_time_in_force_fok_and_gtx(self):
        out = self.mod.run_scenario_g_time_in_force()
        for exchange in ("no_partial_fill", "partial_fill"):
            g = out[exchange]
            self.assertEqual(g["g1_fok_sufficient_depth"]["order_status"], self.order_mod.FILLED, exchange)
            self.assertEqual(g["g3_gtx_crossing"]["order_status"], self.order_mod.EXPIRED, exchange)
            self.assertNotEqual(g["g3_gtx_crossing"]["order_status"], self.order_mod.REJECTED, exchange)
            self.assertEqual(g["g4_gtx_resting"]["order_status"], self.order_mod.NEW, exchange)
        # FOK-with-insufficient-depth is the scenario that actually distinguishes
        # the two exchange models' FOK semantics.
        self.assertEqual(out["no_partial_fill"]["g2_fok_insufficient_depth"]["order_status"], self.order_mod.FILLED)
        self.assertAlmostEqual(out["no_partial_fill"]["g2_fok_insufficient_depth"]["exec_qty"], 150.0, places=6)
        self.assertEqual(out["partial_fill"]["g2_fok_insufficient_depth"]["order_status"], self.order_mod.EXPIRED)
        self.assertAlmostEqual(out["partial_fill"]["g2_fok_insufficient_depth"]["exec_qty"], 0.0, places=6)

    def test_scenario_h_nonzero_fee_is_actually_applied(self):
        result = self.mod.run_scenario_h_fee_accounting()
        self.assertEqual(result["order_status"], self.order_mod.FILLED)
        self.assertAlmostEqual(result["fee"], result["expected_fee"], places=6)
        self.assertGreater(result["fee"], 0.0)

    def test_emo_rule_restores_queue_depletion_on_scenario_c_tape(self):
        result = self.mod.run_scenario_c_emo()
        self.assertEqual(result["order_status"], self.order_mod.FILLED)
        self.assertEqual(result["inferred_sides"], ["sell"] * 5)

    def test_emo_inferred_side_restores_d1_trade_through_fill(self):
        # An earlier version of this fixture's receipt claimed inference
        # "restores trade-through fills" on the D1 tape without ever running
        # it. This actually runs it: a seed trade at the ask gives the tick
        # test a genuine prior price, so the 9.99 print (outside the quotes,
        # below the bid) is classified via the tick test as a downtick/sell.
        result = self.mod.run_scenario_d1_with_inferred_side()
        self.assertEqual(result["inferred_sides"], ["buy", "sell"])
        self.assertEqual(result["order_status"], self.order_mod.FILLED)
        self.assertAlmostEqual(result["exec_qty"], 5.0, places=6)

    def test_scenario_i_partial_fill_never_depletes_displayed_liquidity(self):
        # Reproduces the reviewer's probe: three back-to-back 100-share IOCs
        # against a touch that always shows exactly 100 shares all fill in
        # full under partial_fill_exchange, because executing against
        # self.depth does not mutate self.depth (upstream's own doc comment
        # on PartialFillExchange says this explicitly).
        result = self.mod.run_scenario_i_no_depletion_bias()
        self.assertEqual(len(result["orders"]), 3)
        for order in result["orders"]:
            self.assertEqual(order["order_status"], self.order_mod.FILLED)
            self.assertAlmostEqual(order["exec_qty"], 100.0, places=6)
        self.assertAlmostEqual(result["final_position"], 300.0, places=6)

    def test_scenario_g2_diverges_but_g1_g3_g4_coincide(self):
        # An earlier version of this fixture said Scenarios A-D and G
        # "coincide" between exchange models; that was wrong for G2
        # (oversized FOK), which genuinely diverges.
        out = self.mod.run_scenario_g_time_in_force()
        no_partial = out["no_partial_fill"]
        partial = out["partial_fill"]
        self.assertEqual(no_partial["g1_fok_sufficient_depth"], partial["g1_fok_sufficient_depth"])
        self.assertEqual(no_partial["g3_gtx_crossing"], partial["g3_gtx_crossing"])
        self.assertEqual(no_partial["g4_gtx_resting"], partial["g4_gtx_resting"])
        self.assertNotEqual(no_partial["g2_fok_insufficient_depth"], partial["g2_fok_insufficient_depth"])

    def test_feasibility_script_runs_end_to_end_via_subprocess(self):
        # Runs the script's own __main__ path via an actual subprocess (not
        # "subprocess-free" -- an earlier version of this comment was wrong)
        # so any regression in wiring (imports, argparse, JSON shape) is
        # caught, not just the underlying functions exercised in the tests
        # above.
        proc = subprocess.run(
            [sys.executable, str(BLUEPRINT / "l1_feasibility.py")],
            capture_output=True, text=True, timeout=120,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout)
        for exchange in ("no_partial_fill", "partial_fill"):
            block = out["by_exchange_model"][exchange]
            self.assertEqual(
                block["scenario_a_marketable_ioc_fill_from_l1_depth"]["order_status_name"], "FILLED"
            )
            self.assertEqual(
                block["scenario_b_ioc_expiry_from_l1_depth"]["order_status_name"], "EXPIRED"
            )
        self.assertTrue(out["scenario_f_models_actually_diverge"])
        self.assertTrue(out["identical_under_both_exchange_models_for_scenarios_a_to_d_and_g1_g3_g4"])
        self.assertTrue(out["scenario_g2_fok_insufficient_diverges_between_exchange_models"])
        self.assertAlmostEqual(out["scenario_i_partial_fill_no_depletion_bias"]["final_position"], 300.0, places=6)


class TickTestClassificationTests(unittest.TestCase):
    """Pure-Python classification checks -- no hftbacktest engine involved,
    so these run unconditionally regardless of the venv's availability."""

    @classmethod
    def setUpClass(cls):
        cls.mod = _load_feasibility_module()

    def test_emo_and_lee_ready_are_distinct_rules_and_can_disagree(self):
        demo = self.mod.run_tick_test_coverage_demo()
        self.assertNotEqual(demo["emo"], demo["lee_ready"])
        # index 1 (price 10.015: inside the spread, above the midpoint, a
        # downtick from the seeding trade at 10.02) is the designed
        # disagreement point.
        self.assertEqual(demo["emo"][1], "sell")
        self.assertEqual(demo["lee_ready"][1], "buy")

    def test_emo_applies_exact_quote_rule_only_at_the_bid_or_ask(self):
        # An earlier version of infer_side_emo used >=/<= (at-or-through the
        # quote); EMO's own at-quote condition is equality. A print above
        # the ask, or below the bid, must fall to the tick test instead of
        # being classified directly.
        demo = self.mod.run_emo_boundary_demo()
        prices, sides = demo["prices"], demo["emo"]
        self.assertEqual(prices[0], 10.00)
        self.assertEqual(sides[0], "sell")  # exactly at the bid: direct
        self.assertEqual(prices[1], 10.02)
        self.assertEqual(sides[1], "buy")  # exactly at the ask: direct
        self.assertEqual(prices[2], 10.03)  # strictly ABOVE the ask
        self.assertEqual(sides[2], "buy")  # via the tick test (uptick from 10.02), not the at-quote rule
        self.assertEqual(prices[3], 9.98)  # strictly BELOW the bid
        self.assertEqual(sides[3], "sell")  # via the tick test (downtick from 10.03), not the at-quote rule

        # Confirm directly (independent of the demo tape) that an
        # above-ask/below-bid print is NOT classified by the at-quote
        # condition itself: with no prior trade at all, the tick test has
        # nothing to fall back on and must return an undetermined result --
        # if EMO still returned a definite side here, it would prove the
        # at-quote condition (not the tick test) produced it.
        self.assertIsNone(self.mod.infer_side_emo(10.05, bid=10.00, ask=10.02, tick_state={}))
        self.assertIsNone(self.mod.infer_side_emo(9.90, bid=10.00, ask=10.02, tick_state={}))

    def test_flat_tick_reuses_last_known_direction(self):
        state = {}
        # Prime with an unambiguous at-the-ask trade (established direction: buy),
        # then a genuine downtick to 10.01 (inside the spread -> tick test -> sell),
        # then a FLAT repeat of 10.01: it must reuse 'sell', not fall back to None.
        self.mod.infer_side_emo(10.02, bid=10.00, ask=10.02, tick_state=state)
        first_inside = self.mod.infer_side_emo(10.01, bid=10.00, ask=10.02, tick_state=state)
        second_inside = self.mod.infer_side_emo(10.01, bid=10.00, ask=10.02, tick_state=state)
        self.assertEqual(first_inside, "sell")
        self.assertEqual(second_inside, "sell")


class LockfileAndReceiptStructureTests(unittest.TestCase):
    """These run regardless of whether hftbacktest is installed -- they check
    checked-in artifacts, not native execution."""

    def test_requirements_lock_pins_hftbacktest_2_4_4_with_hashes(self):
        lock_text = (BLUEPRINT / "requirements.lock").read_text(encoding="utf-8")
        self.assertIn("hftbacktest==2.4.4", lock_text)
        self.assertIn("--hash=sha256:", lock_text)

    def test_receipt_is_valid_json_with_required_top_level_keys(self):
        receipt_path = BLUEPRINT / "receipt.json"
        self.assertTrue(receipt_path.is_file(), receipt_path)
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        for key in ("evidence", "versions", "l1_feasibility_verdict", "unverified", "maintenance_precondition"):
            self.assertIn(key, receipt)

    def test_osv_scanner_lockfile_inventory_covers_requirements_in(self):
        inventory = json.loads((ROOT / ".github" / "osv-scanner-lockfiles.json").read_text(encoding="utf-8"))
        covered = {e["path"]: e["lockfile"] for e in inventory["covered_by_lockfile"]}
        rel_in = "blueprints/us-equities/sim-crosscheck-hftbacktest/requirements.in"
        rel_lock = "blueprints/us-equities/sim-crosscheck-hftbacktest/requirements.lock"
        self.assertIn(rel_in, covered)
        self.assertEqual(covered[rel_in], rel_lock)


if __name__ == "__main__":
    unittest.main()
