"""Pure-module tests for the G-e leverage-schedule policy (leverage.py).

No I/O, no broker/transport, no strategy/ledger fixtures here -- see
test_adaptive_paper_safety.py, test_adaptive_paper_strategies.py and
test_adaptive_paper_runner.py for the enforcement-point integration tests.
"""
from decimal import Decimal as D
import importlib.util
from itertools import product
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / "blueprints/us-equities/adaptive-paper/leverage.py"
SPEC = importlib.util.spec_from_file_location("adaptive_paper_leverage", FILE)
L = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = L
SPEC.loader.exec_module(L)


def base_config(*, max_leverage="4", capital_usd="10000", max_gross_exposure_usd="40000", block=None):
    return {"max_leverage": max_leverage, "capital_usd": capital_usd,
            "max_gross_exposure_usd": max_gross_exposure_usd,
            "leverage_policy": L.CANONICAL_V1_BLOCK if block is None else block}


def base_session_policy(*, overnight_holds=False, overnight_gross_multiple="1.0"):
    return {"overnight_holds": overnight_holds, "overnight_gross_multiple": D(overnight_gross_multiple)}


def block_with(**changes):
    import copy
    block = copy.deepcopy(L.CANONICAL_V1_BLOCK)
    block.update(changes)
    return block


class CanonicalValidationTests(unittest.TestCase):
    def test_canonical_block_validates_for_1_2_and_4x(self):
        for lev in ("1", "2", "4"):
            gross = str(int(D("10000") * D(lev)))
            config = base_config(max_leverage=lev, max_gross_exposure_usd=gross)
            policy = L.validate_leverage_policy(config, base_session_policy())
            self.assertEqual(policy.max_leverage, D(lev))
            self.assertFalse(policy.apply_overnight_cap)

    def test_canonical_block_validates_with_overnight_holds_true(self):
        # capital*overnight_max_leverage(2) = 20000; gross*multiple must fit.
        config = base_config(max_leverage="2", max_gross_exposure_usd="20000")
        policy = L.validate_leverage_policy(config, base_session_policy(overnight_holds=True))
        self.assertTrue(policy.apply_overnight_cap)


class RefusalTests(unittest.TestCase):
    def assertRefused(self, config, reason, session_policy=None):
        with self.assertRaises(L.LeveragePolicyError) as ctx:
            L.validate_leverage_policy(config, session_policy or base_session_policy())
        self.assertEqual(str(ctx.exception), reason)

    def test_version_mismatch(self):
        self.assertRefused(base_config(block=block_with(version="other")), "leverage_policy_version_mismatch")

    def test_unknown_key(self):
        block = block_with()
        block["extra"] = "x"
        self.assertRefused(base_config(block=block), "leverage_policy_keys")

    def test_missing_required_key(self):
        block = block_with()
        del block["overnight_max_leverage"]
        self.assertRefused(base_config(block=block), "leverage_policy_keys")

    def test_schedule_missing_a_session(self):
        block = block_with()
        del block["schedule"]["CLOSED"]
        self.assertRefused(base_config(block=block), "leverage_schedule_shape")

    def test_schedule_missing_a_regime(self):
        block = block_with()
        del block["schedule"]["RTH"]["range"]
        self.assertRefused(base_config(block=block), "leverage_schedule_shape")

    def test_schedule_extra_regime(self):
        block = block_with()
        block["schedule"]["RTH"]["extra"] = "1"
        self.assertRefused(base_config(block=block), "leverage_schedule_shape")

    def test_cell_value_float_refused(self):
        block = block_with()
        block["schedule"]["RTH"]["trend"] = 4.0
        self.assertRefused(base_config(block=block), "leverage_value_invalid")

    def test_cell_value_int_refused(self):
        block = block_with()
        block["schedule"]["RTH"]["trend"] = 4
        self.assertRefused(base_config(block=block), "leverage_value_invalid")

    def test_cell_value_bool_refused(self):
        block = block_with()
        block["schedule"]["RTH"]["trend"] = True
        self.assertRefused(base_config(block=block), "leverage_value_invalid")

    def test_cell_value_nan_refused(self):
        block = block_with()
        block["schedule"]["RTH"]["trend"] = "NaN"
        self.assertRefused(base_config(block=block), "leverage_value_invalid")

    def test_cell_value_negative_refused(self):
        block = block_with()
        block["schedule"]["RTH"]["trend"] = "-1"
        self.assertRefused(base_config(block=block), "leverage_value_invalid")

    def test_cell_value_more_than_2dp_refused(self):
        block = block_with()
        block["schedule"]["RTH"]["trend"] = "1.001"
        self.assertRefused(base_config(block=block), "leverage_value_invalid")

    def test_cell_value_above_4_refused(self):
        block = block_with()
        block["schedule"]["RTH"]["trend"] = "4.01"
        self.assertRefused(base_config(block=block), "leverage_value_invalid")

    def test_risk_off_nonzero_refused(self):
        block = block_with()
        block["schedule"]["RTH"]["risk_off"] = "1"
        self.assertRefused(base_config(block=block), "leverage_nonzero_in_risk_off")

    def test_unavailable_nonzero_refused(self):
        block = block_with()
        block["schedule"]["PRE"]["unavailable"] = "1"
        self.assertRefused(base_config(block=block), "leverage_nonzero_in_risk_off")

    def test_closed_nonzero_refused(self):
        block = block_with()
        block["schedule"]["CLOSED"]["trend"] = "1"
        self.assertRefused(base_config(block=block), "leverage_nonzero_when_closed")

    def test_range_above_engine_cap_refused(self):
        block = block_with()
        block["schedule"]["RTH"]["range"] = "2"
        self.assertRefused(base_config(block=block), "leverage_range_exceeds_engine_cap")

    def test_overnight_max_leverage_zero_refused(self):
        self.assertRefused(base_config(block=block_with(overnight_max_leverage="0")),
                           "leverage_overnight_out_of_bounds")

    def test_overnight_max_leverage_above_2_refused(self):
        self.assertRefused(base_config(block=block_with(overnight_max_leverage="2.01")),
                           "leverage_overnight_out_of_bounds")

    def test_config_max_leverage_below_1_refused(self):
        self.assertRefused(base_config(max_leverage="0.5"), "leverage_requested_out_of_bounds")

    def test_config_max_leverage_above_4_refused(self):
        self.assertRefused(base_config(max_leverage="4.01", max_gross_exposure_usd="40000"),
                           "leverage_requested_out_of_bounds")

    def test_config_max_leverage_5_refused(self):
        self.assertRefused(base_config(max_leverage="5", max_gross_exposure_usd="40000"),
                           "leverage_requested_out_of_bounds")

    # -- drawdown ladder refusals ------------------------------------------

    def test_ladder_non_monotone_refused(self):
        block = block_with(drawdown_ladder=[
            {"from_drawdown_fraction": "0", "max_leverage": "2"},
            {"from_drawdown_fraction": "0.5", "max_leverage": "4"},
            {"from_drawdown_fraction": "0.9", "max_leverage": "0"}])
        self.assertRefused(base_config(block=block), "leverage_ladder_not_monotone")

    def test_ladder_not_starting_at_zero_refused(self):
        block = block_with(drawdown_ladder=[
            {"from_drawdown_fraction": "0.1", "max_leverage": "4"},
            {"from_drawdown_fraction": "0.9", "max_leverage": "0"}])
        self.assertRefused(base_config(block=block), "leverage_ladder_must_start_at_zero")

    def test_ladder_last_step_not_zero_refused(self):
        block = block_with(drawdown_ladder=[
            {"from_drawdown_fraction": "0", "max_leverage": "4"},
            {"from_drawdown_fraction": "0.5", "max_leverage": "1"}])
        self.assertRefused(base_config(block=block), "leverage_ladder_must_end_at_zero")

    def test_ladder_thresholds_not_strictly_increasing_refused(self):
        block = block_with(drawdown_ladder=[
            {"from_drawdown_fraction": "0", "max_leverage": "4"},
            {"from_drawdown_fraction": "0.5", "max_leverage": "2"},
            {"from_drawdown_fraction": "0.5", "max_leverage": "0"}])
        self.assertRefused(base_config(block=block), "leverage_ladder_thresholds")

    def test_ladder_threshold_at_or_above_1_refused(self):
        block = block_with(drawdown_ladder=[
            {"from_drawdown_fraction": "0", "max_leverage": "4"},
            {"from_drawdown_fraction": "1", "max_leverage": "0"}])
        self.assertRefused(base_config(block=block), "leverage_ladder_thresholds")

    def test_ladder_first_step_above_4_refused(self):
        block = block_with(drawdown_ladder=[
            {"from_drawdown_fraction": "0", "max_leverage": "4.5"},
            {"from_drawdown_fraction": "0.5", "max_leverage": "0"}])
        self.assertRefused(base_config(block=block), "leverage_value_invalid")

    def test_ladder_fewer_than_2_steps_refused(self):
        block = block_with(drawdown_ladder=[{"from_drawdown_fraction": "0", "max_leverage": "4"}])
        self.assertRefused(base_config(block=block), "leverage_ladder_must_start_at_zero")

    # -- absolute notional consistency refusals ------------------------------

    def test_gross_exceeds_capital_times_max_leverage_refused(self):
        self.assertRefused(base_config(max_leverage="2", max_gross_exposure_usd="20000.01"),
                           "leverage_gross_cap_exceeds_capital_times_leverage")

    def test_overnight_gross_exceeds_regt_refused(self):
        # capital 10000 * overnight_max_leverage 2 = 20000; gross*multiple must not exceed it.
        config = base_config(max_leverage="2", max_gross_exposure_usd="20000")
        session_policy = base_session_policy(overnight_holds=True, overnight_gross_multiple="1.5")
        self.assertRefused(config, "leverage_overnight_gross_exceeds_regt", session_policy)

    # -- DP-2: shape/bounds-valid but non-canonical block refusal -----------

    def test_shape_valid_non_canonical_block_refused(self):
        """DP-2 finding scenario: a schedule/ladder that individually passes
        every generic shape/bounds check above (RTH trend stays 4x, PRE/POST
        trend also 4x, ladder steps straight to 0 at 0.99 drawdown instead of
        the canonical 0.25/0.5/0.75 steps) must still be refused because it
        is not the pre-registered CANONICAL_V1_BLOCK."""
        block = block_with(
            schedule={
                "RTH":    {"trend": "4", "range": "1", "risk_off": "0", "unavailable": "0"},
                "PRE":    {"trend": "4", "range": "1", "risk_off": "0", "unavailable": "0"},
                "POST":   {"trend": "4", "range": "1", "risk_off": "0", "unavailable": "0"},
                "CLOSED": {"trend": "0", "range": "0", "risk_off": "0", "unavailable": "0"},
            },
            drawdown_ladder=[
                {"from_drawdown_fraction": "0", "max_leverage": "4"},
                {"from_drawdown_fraction": "0.99", "max_leverage": "0"},
            ])
        self.assertRefused(base_config(block=block), "leverage_policy_block_not_canonical")

    def test_block_without_decision_record_still_compared_to_canonical(self):
        import copy
        block = copy.deepcopy(L.CANONICAL_V1_BLOCK)
        del block["decision_record"]
        # Still shape/bounds-valid (decision_record is optional) and equal to
        # the canonical block modulo the dropped optional key -> accepted.
        policy = L.validate_leverage_policy(base_config(block=block), base_session_policy())
        self.assertEqual(policy.max_leverage, D("4"))
        # But a further, otherwise-valid deviation is still refused.
        block["schedule"]["PRE"]["trend"] = "4"
        self.assertRefused(base_config(block=block), "leverage_policy_block_not_canonical")


class PropertyGridTests(unittest.TestCase):
    """session x regime x drawdown_fraction x max_leverage x overnight x kill."""

    def policy(self, max_leverage, overnight_holds=False):
        # With overnight_holds, gross is also bounded by capital*overnight_max_leverage(2).
        bound = min(D(str(max_leverage)), D("2")) if overnight_holds else D(str(max_leverage))
        gross = str(int(D("10000") * bound))
        config = base_config(max_leverage=str(max_leverage), max_gross_exposure_usd=gross)
        return L.validate_leverage_policy(config, base_session_policy(overnight_holds=overnight_holds))

    def test_ceiling_equals_min_of_components(self):
        for lev, overnight in product((1, 2, 4), (False, True)):
            policy = self.policy(lev, overnight_holds=overnight)
            for session, regime, frac in product(L.SESSIONS, L.REGIMES, (D("0"), D("0.1"), D("0.3"), D("0.6"), D("0.9"))):
                expected = min(policy.max_leverage, policy._cell(session, regime), policy.ladder_step(frac))
                if overnight:
                    expected = min(expected, policy.overnight_max_leverage)
                expected = max(expected, L.ZERO)
                got = policy.ceiling(session=session, regime=regime, drawdown_fraction=frac, kill_switch=False)
                self.assertEqual(got, expected, (lev, overnight, session, regime, frac))

    def test_ceiling_never_exceeds_envelope(self):
        for lev, overnight in product((1, 2, 4), (False, True)):
            policy = self.policy(lev, overnight_holds=overnight)
            for session, regime, frac in product(L.SESSIONS, L.REGIMES, (D("0"), D("0.2"), D("0.5"), D("0.8"))):
                ceiling = policy.ceiling(session=session, regime=regime, drawdown_fraction=frac, kill_switch=False)
                envelope = policy.envelope(session=session, drawdown_fraction=frac)
                self.assertLessEqual(ceiling, envelope)

    def test_ceiling_non_increasing_in_drawdown(self):
        policy = self.policy(4)
        fractions = [D("0"), D("0.1"), D("0.24"), D("0.25"), D("0.4"), D("0.5"), D("0.6"), D("0.74"), D("0.75"), D("0.9")]
        values = [policy.ceiling(session="RTH", regime="trend", drawdown_fraction=f, kill_switch=False) for f in fractions]
        self.assertEqual(values, sorted(values, reverse=True))

    def test_kill_switch_zeroes_ceiling(self):
        policy = self.policy(4)
        self.assertEqual(policy.ceiling(session="RTH", regime="trend", drawdown_fraction=D("0"), kill_switch=True), L.ZERO)

    def test_risk_off_and_unavailable_zero(self):
        policy = self.policy(4)
        for regime in ("risk_off", "unavailable"):
            self.assertEqual(policy.ceiling(session="RTH", regime=regime, drawdown_fraction=D("0"), kill_switch=False), L.ZERO)

    def test_closed_zero(self):
        policy = self.policy(4)
        for regime in L.REGIMES:
            self.assertEqual(policy.ceiling(session="CLOSED", regime=regime, drawdown_fraction=D("0"), kill_switch=False), L.ZERO)

    def test_unknown_session_zero(self):
        policy = self.policy(4)
        self.assertEqual(policy.ceiling(session="XYZ", regime="trend", drawdown_fraction=D("0"), kill_switch=False), L.ZERO)
        self.assertEqual(policy.envelope(session="XYZ", drawdown_fraction=D("0")), L.ZERO)
        self.assertEqual(policy.ceiling(session=None, regime="trend", drawdown_fraction=D("0"), kill_switch=False), L.ZERO)

    def test_nan_or_negative_drawdown_zero(self):
        policy = self.policy(4)
        self.assertEqual(policy.ladder_step(D("NaN")), L.ZERO)
        self.assertEqual(policy.ladder_step(D("-0.01")), L.ZERO)

    def test_overnight_cap_bounds_ceiling_at_2_in_every_session(self):
        policy = self.policy(4, overnight_holds=True)
        for session, regime in product(L.SESSIONS, L.REGIMES):
            ceiling = policy.ceiling(session=session, regime=regime, drawdown_fraction=D("0"), kill_switch=False)
            self.assertLessEqual(ceiling, D("2"))

    def test_account_multiplier_clamps_ceiling(self):
        policy = self.policy(4)
        full = policy.ceiling(session="RTH", regime="trend", drawdown_fraction=D("0"), kill_switch=False)
        clamped = policy.ceiling(session="RTH", regime="trend", drawdown_fraction=D("0"), kill_switch=False,
                                 account_multiplier=D("2"))
        self.assertEqual(full, D("4"))
        self.assertEqual(clamped, D("2"))
        self.assertLess(clamped, full)


class NextLowerRungCeilingTests(unittest.TestCase):
    """F2 (2026-09-22 residual review, reachability): leverage.
    next_lower_rung_ceiling -- the pure rung-ladder lookup the runner's
    achieved-leverage receipt uses to know what "the next rung down" means
    for a given config's max_leverage."""

    def test_1x_has_no_lower_rung(self):
        self.assertIsNone(L.next_lower_rung_ceiling(D("1")))

    def test_2x_next_lower_is_1x(self):
        self.assertEqual(L.next_lower_rung_ceiling(D("2")), D("1"))

    def test_4x_next_lower_is_2x(self):
        self.assertEqual(L.next_lower_rung_ceiling(D("4")), D("2"))

    def test_below_lowest_rung_has_no_lower_rung(self):
        self.assertIsNone(L.next_lower_rung_ceiling(D("0.5")))
        self.assertIsNone(L.next_lower_rung_ceiling(D("0")))

    def test_a_value_between_rungs_returns_the_rung_strictly_below_it(self):
        # Not itself one of the pre-registered rungs, but the mapping stays
        # total (every shipped config's max_leverage is 1, 2 or 4 in
        # practice; this just documents the lookup does not require that).
        self.assertEqual(L.next_lower_rung_ceiling(D("3")), D("2"))


if __name__ == "__main__":
    unittest.main()
