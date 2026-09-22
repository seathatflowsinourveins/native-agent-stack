"""Synthetic (SYN) tests for the G-f exit-plan/cancel-replace/notional-qty
deliverables: exits.ExitPlan ordering and vol/time-decay thresholds,
native_strategy.AdaptiveStrategy.replace_exit's cancel-then-submit, and
safety.RiskLimits' notional max_order_qty mode. No credentials, sockets, or
broker execution; native tests use fakes only, matching every other
tests/test_adaptive_paper_*.py file in this directory.
"""
from dataclasses import replace
from decimal import Decimal as D
import importlib.util
from pathlib import Path
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "blueprints/us-equities/adaptive-paper"
sys.path.insert(0, str(SOURCE))

import exits as X  # noqa: E402 (path inserted above)
from strategies_v1 import AdaptivePolicy, PolicyConfig  # noqa: E402
from safety import Ledger, Quote, RiskLimits, SafetyError, decimal as safety_decimal  # noqa: E402

NATIVE = importlib.util.find_spec("nautilus_trader") is not None


def policy_config(**changes):
    changes.setdefault("symbols", ("SPY", "QQQ", "IWM", "DIA", "AAPL", "MSFT"))
    changes.setdefault("max_positions", 6)
    return PolicyConfig(**changes)


class ExitPlanOrderingTests(unittest.TestCase):
    """Deliverable 1: same precedence as the pre-G-f inline chain, exercised
    directly against exits.DEFAULT_PLAN with a synthetic ExitContext stream
    (no quote feed needed -- each rule's trigger condition is set directly)."""

    def ctx(self, **overrides):
        base = dict(now=1000.0, entered_at=900.0, pnl_bps=0.0, trail_bps=0.0,
                    quote_fresh=True, risk_off=False, force_exit=False,
                    force_exit_reason="trial_end", volatility_bps=None)
        base.update(overrides)
        return X.ExitContext(**base)

    def test_force_exit_wins_over_every_other_trigger(self):
        c = policy_config()
        ctx = self.ctx(force_exit=True, force_exit_reason="trial_end", risk_off=True,
                       quote_fresh=False, pnl_bps=-100, trail_bps=-100)
        decision = X.DEFAULT_PLAN.evaluate(ctx, c)
        self.assertEqual(decision.reason, "trial_end")

    def test_risk_off_wins_over_quote_stale_and_stop(self):
        c = policy_config()
        ctx = self.ctx(risk_off=True, quote_fresh=False, pnl_bps=-100)
        decision = X.DEFAULT_PLAN.evaluate(ctx, c)
        self.assertEqual(decision.reason, "risk_off")

    def test_quote_stale_wins_over_stop_take_profit_and_trailing(self):
        c = policy_config()
        ctx = self.ctx(quote_fresh=False, pnl_bps=-100, trail_bps=-100)
        decision = X.DEFAULT_PLAN.evaluate(ctx, c)
        self.assertEqual(decision.reason, "quote_stale")

    def test_stop_wins_over_take_profit_when_both_conditions_hold(self):
        # Contrived (pnl can't simultaneously be both) but locks in ordering
        # if a rule's threshold math ever regresses to overlap.
        c = policy_config(stop_bps=10, take_profit_bps=5)
        ctx = self.ctx(pnl_bps=-20)
        decision = X.DEFAULT_PLAN.evaluate(ctx, c)
        self.assertEqual(decision.reason, "stop_loss")

    def test_take_profit_wins_over_trailing(self):
        c = policy_config(take_profit_bps=40, trailing_bps=15)
        ctx = self.ctx(pnl_bps=50, trail_bps=-50)
        decision = X.DEFAULT_PLAN.evaluate(ctx, c)
        self.assertEqual(decision.reason, "take_profit")

    def test_trailing_wins_over_time_exit(self):
        c = policy_config(trailing_bps=15, max_hold_seconds=90, min_hold_seconds=5)
        ctx = self.ctx(trail_bps=-20, now=1000.0, entered_at=900.0)  # entered 100s ago > max_hold
        decision = X.DEFAULT_PLAN.evaluate(ctx, c)
        self.assertEqual(decision.reason, "trailing_stop")

    def test_time_exit_is_the_last_resort_before_no_exit(self):
        c = policy_config(max_hold_seconds=90, min_hold_seconds=5)
        ctx = self.ctx(now=1000.0, entered_at=900.0)  # 100s >= 90s max hold, nothing else triggers
        decision = X.DEFAULT_PLAN.evaluate(ctx, c)
        self.assertEqual(decision.reason, "time_exit")

    def test_no_rule_fires_returns_none(self):
        c = policy_config(max_hold_seconds=90, min_hold_seconds=5)
        ctx = self.ctx(now=950.0, entered_at=900.0)  # 50s held, nothing triggers
        self.assertIsNone(X.DEFAULT_PLAN.evaluate(ctx, c))


class DefaultByteIdentityTests(unittest.TestCase):
    """Deliverable 1: with every new PolicyConfig field left at its default,
    AdaptivePolicy._decide_core (now routed through exits.DEFAULT_PLAN) must
    still reach the exact same reason strings as the pre-G-f inline chain
    for stop/take-profit/trailing -- the three cases the golden fixture also
    locks in (see tests/test_adaptive_paper_strategies.py's
    GoldenEquivalenceTests, which independently re-verifies all 16 cases)."""

    def feed(self, policy, stock_prices, *, start=1000):
        for i, price in enumerate(stock_prices):
            for s in policy.config.symbols:
                policy.observe(s, price - .005, price + .005, start + i)
        return start + len(stock_prices) - 1

    def exit_case(self, price, high):
        p = AdaptivePolicy(policy_config())
        now = self.feed(p, [100] * 40)
        p.sync_positions({"AAPL": {"qty": 1, "avg_entry_price": "100"}}, now - 10)
        p.holdings["AAPL"].high_bid = high
        p.observe("AAPL", price, price + .01, now + .1)
        decision = p.decide(now + .1)
        return decision, p

    def test_stop_loss_default_reason_and_fraction(self):
        decision, p = self.exit_case(99.7, 100)
        self.assertEqual(decision.exits["AAPL"], "stop_loss")
        self.assertEqual(p.last_exit_fractions["AAPL"], 1.0)

    def test_take_profit_default_reason_and_fraction(self):
        decision, p = self.exit_case(100.5, 100)
        self.assertEqual(decision.exits["AAPL"], "take_profit")
        self.assertEqual(p.last_exit_fractions["AAPL"], 1.0)

    def test_trailing_stop_default_reason_and_fraction(self):
        decision, p = self.exit_case(100.1, 100.3)
        self.assertEqual(decision.exits["AAPL"], "trailing_stop")
        self.assertEqual(p.last_exit_fractions["AAPL"], 1.0)


class VolScaledStopClampTests(unittest.TestCase):
    """Deliverable 1: vol-scaled stop/trailing, clamped to
    [stop_min_bps, stop_max_bps] / [trailing_min_bps, trailing_max_bps]."""

    def ctx(self, **overrides):
        base = dict(now=1000.0, entered_at=900.0, pnl_bps=0.0, trail_bps=0.0,
                    quote_fresh=True, risk_off=False, force_exit=False,
                    force_exit_reason="trial_end", volatility_bps=None)
        base.update(overrides)
        return X.ExitContext(**base)

    def test_multiplier_scales_stop_bps_with_matching_vol(self):
        c = policy_config(stop_bps=20, vol_stop_multiplier=2.0, vol_reference_bps=10,
                          stop_min_bps=1, stop_max_bps=1000)
        stop_bps, _ = X.effective_thresholds(self.ctx(volatility_bps=10), c)
        self.assertAlmostEqual(stop_bps, 40.0)

    def test_clamp_caps_a_large_scaled_stop_at_stop_max_bps(self):
        c = policy_config(stop_bps=20, vol_stop_multiplier=5.0, vol_reference_bps=10,
                          stop_min_bps=1, stop_max_bps=60)
        stop_bps, _ = X.effective_thresholds(self.ctx(volatility_bps=10), c)
        self.assertEqual(stop_bps, 60.0)

    def test_clamp_floors_a_small_scaled_stop_at_stop_min_bps(self):
        c = policy_config(stop_bps=20, vol_stop_multiplier=0.1, vol_reference_bps=10,
                          stop_min_bps=10, stop_max_bps=1000)
        stop_bps, _ = X.effective_thresholds(self.ctx(volatility_bps=10), c)
        self.assertEqual(stop_bps, 10.0)

    def test_default_config_clamp_is_zero_width_and_scale_invariant(self):
        # Even with a non-1.0 multiplier, the *shipped default* clamp bounds
        # (None -> stop_bps/trailing_bps in __post_init__) pin the effective
        # threshold to the unscaled stop_bps/trailing_bps -- this is the
        # exact mechanism the module docstring says makes every default
        # PolicyConfig() byte-identical regardless of multiplier.
        c = policy_config(stop_bps=25, trailing_bps=15)  # stop_min/max_bps left at sentinel defaults
        stop_bps, trailing_bps = X.effective_thresholds(self.ctx(volatility_bps=999), c)
        self.assertEqual((stop_bps, trailing_bps), (25.0, 15.0))

    def test_missing_volatility_data_falls_back_to_multiplier_only(self):
        c = policy_config(stop_bps=20, vol_stop_multiplier=1.5, stop_min_bps=1, stop_max_bps=1000)
        stop_bps, _ = X.effective_thresholds(self.ctx(volatility_bps=None), c)
        self.assertAlmostEqual(stop_bps, 30.0)


class PartialTakeProfitTests(unittest.TestCase):
    """Deliverable 1 (+2 downstream): take_profit_fraction < 1.0 reports a
    partial fraction via AdaptivePolicy.last_exit_fractions; the remaining
    (synced-down) quantity then keeps trailing on a later tick, using the
    same high_bid tracking as a full position."""

    def feed(self, policy, stock_prices, start=1000):
        for i, price in enumerate(stock_prices):
            for s in policy.config.symbols:
                policy.observe(s, price - .005, price + .005, start + i)
        return start + len(stock_prices) - 1

    def test_partial_fraction_below_one_recorded_on_take_profit(self):
        p = AdaptivePolicy(policy_config(take_profit_fraction=.5))
        now = self.feed(p, [100] * 40)
        p.sync_positions({"AAPL": {"qty": 2, "avg_entry_price": "100"}}, now - 10)
        p.holdings["AAPL"].high_bid = 100
        p.observe("AAPL", 100.5, 100.51, now + .1)
        decision = p.decide(now + .1)
        self.assertEqual(decision.exits["AAPL"], "take_profit")
        self.assertEqual(p.last_exit_fractions["AAPL"], .5)

    def test_remainder_after_partial_take_profit_still_trails(self):
        p = AdaptivePolicy(policy_config(take_profit_fraction=.5, trailing_bps=15))
        now = self.feed(p, [100] * 40)
        p.sync_positions({"AAPL": {"qty": 2, "avg_entry_price": "100"}}, now - 10)
        p.holdings["AAPL"].high_bid = 100
        p.observe("AAPL", 100.5, 100.51, now + .1)
        first = p.decide(now + .1)
        self.assertEqual(first.exits["AAPL"], "take_profit")
        # Broker fill reduces the position to the remainder; sync_positions
        # reconciles it exactly as an ordinary partial fill would.
        p.sync_positions({"AAPL": {"qty": 1, "avg_entry_price": "100"}}, now + 2.5)
        p.observe("AAPL", 100.30, 100.31, now + 2.6)  # pulled back from the 100.5 high, past rebalance_seconds
        second = p.decide(now + 2.6)
        self.assertEqual(second.exits["AAPL"], "trailing_stop")
        self.assertEqual(p.last_exit_fractions["AAPL"], 1.0)


class TimeDecayTighteningTests(unittest.TestCase):
    def ctx(self, **overrides):
        base = dict(now=1000.0, entered_at=900.0, pnl_bps=0.0, trail_bps=0.0,
                    quote_fresh=True, risk_off=False, force_exit=False,
                    force_exit_reason="trial_end", volatility_bps=None)
        base.update(overrides)
        return X.ExitContext(**base)

    def test_disabled_by_default_leaves_thresholds_unchanged_near_max_hold(self):
        c = policy_config(stop_bps=25, trailing_bps=15, max_hold_seconds=90, min_hold_seconds=5)
        ctx = self.ctx(now=989.0, entered_at=900.0)  # 89s held, 1s from max_hold_seconds
        stop_bps, trailing_bps = X.effective_thresholds(ctx, c)
        self.assertEqual((stop_bps, trailing_bps), (25.0, 15.0))

    def test_enabled_tightens_linearly_toward_time_decay_min_multiplier(self):
        c = policy_config(stop_bps=100, trailing_bps=100, max_hold_seconds=100, min_hold_seconds=5,
                          stop_min_bps=1, stop_max_bps=1000, trailing_min_bps=1, trailing_max_bps=1000,
                          time_decay_start_seconds=50, time_decay_min_multiplier=0.2)
        # Halfway between decay start (50s elapsed) and max_hold (100s elapsed).
        ctx = self.ctx(now=975.0, entered_at=900.0)  # 75s elapsed
        stop_bps, trailing_bps = X.effective_thresholds(ctx, c)
        # t = (75-50)/(100-50) = 0.5; decay = 1 - 0.5*(1-0.2) = 0.6
        self.assertAlmostEqual(stop_bps, 60.0)
        self.assertAlmostEqual(trailing_bps, 60.0)

    def test_tightening_makes_a_stop_fire_that_would_not_have_without_it(self):
        c = policy_config(stop_bps=100, max_hold_seconds=100, min_hold_seconds=5,
                          stop_min_bps=1, stop_max_bps=1000,
                          time_decay_start_seconds=50, time_decay_min_multiplier=0.2)
        ctx = self.ctx(now=1000.0, entered_at=900.0, pnl_bps=-70)  # 100s elapsed -> full decay (multiplier .2 -> 20bps)
        decision = X.DEFAULT_PLAN.evaluate(ctx, c)
        self.assertEqual(decision.reason, "stop_loss")


class PolicyConfigValidationTests(unittest.TestCase):
    def test_rejects_stop_min_above_stop_max(self):
        with self.assertRaises(ValueError):
            policy_config(stop_min_bps=50, stop_max_bps=10)

    def test_rejects_trailing_min_above_trailing_max(self):
        with self.assertRaises(ValueError):
            policy_config(trailing_min_bps=50, trailing_max_bps=10)

    def test_rejects_take_profit_fraction_out_of_bounds(self):
        with self.assertRaises(ValueError):
            policy_config(take_profit_fraction=1.5)
        with self.assertRaises(ValueError):
            policy_config(take_profit_fraction=0)

    def test_rejects_exit_replace_max_attempts_out_of_bounds(self):
        with self.assertRaises(ValueError):
            policy_config(exit_replace_max_attempts=0)
        with self.assertRaises(ValueError):
            policy_config(exit_replace_max_attempts=21)

    def test_rejects_time_decay_start_at_or_past_max_hold(self):
        with self.assertRaises(ValueError):
            policy_config(max_hold_seconds=90, time_decay_start_seconds=90)

    def test_default_construction_still_succeeds(self):
        policy_config()  # must not raise


class NotionalMaxOrderQtyTests(unittest.TestCase):
    """Deliverable 3 (+ D6, round 2): RiskLimits.max_order_qty_mode --
    "fixed" (default, byte-identical) vs "notional" (min(configured
    max_order_qty, floor(max_order_notional_usd / price), 100) -- D6:
    notional mode narrows the operator's own configured max_order_qty when
    the notional budget is the tighter constraint, but never *discards* or
    widens past it; an operator who wants more than the fixed-mode literal
    default of 1 share must explicitly raise max_order_qty too)."""

    def test_fixed_mode_is_the_default_and_matches_pre_g_f_behavior(self):
        limits = RiskLimits()
        self.assertEqual(limits.max_order_qty_mode, "fixed")
        self.assertEqual(limits.effective_max_order_qty("100"), D("1"))

    def test_notional_mode_computes_floor_of_notional_over_price(self):
        limits = replace(RiskLimits(), max_order_qty_mode="notional", max_order_notional_usd=D("1000"),
                         max_order_qty=D("50"))
        self.assertEqual(limits.effective_max_order_qty("333.34"), D("2"))
        self.assertEqual(limits.effective_max_order_qty("100"), D("10"))

    def test_notional_mode_allows_more_than_the_fixed_literal_of_one_when_operator_raises_the_cap(self):
        limits = replace(RiskLimits(), max_order_qty_mode="notional", max_order_notional_usd=D("1000"),
                         max_order_qty=D("50"))
        self.assertGreater(limits.effective_max_order_qty("100"), D("1"))

    def test_notional_mode_never_exceeds_the_hundred_share_ceiling(self):
        limits = replace(RiskLimits(), max_order_qty_mode="notional", max_order_notional_usd=D("10000"),
                         max_gross_exposure_usd=D("10000"), capital_usd=D("10000"), max_order_qty=D("100"))
        self.assertEqual(limits.effective_max_order_qty("1"), D("100"))

    def test_notional_mode_still_binds_the_operators_configured_cap(self):
        """D6: the pre-fix version discarded max_order_qty entirely in
        notional mode -- a notional budget implying 10 shares at this price
        used to silently override an operator's explicit 3-share cap. Now
        the smaller of the two (the operator's own configured cap) wins."""
        limits = replace(RiskLimits(), max_order_qty_mode="notional", max_order_notional_usd=D("1000"),
                         max_order_qty=D("3"))
        self.assertEqual(limits.effective_max_order_qty("100"), D("3"))  # notional would imply 10; capped at 3

    def test_notional_mode_with_default_max_order_qty_stays_at_one(self):
        """The shipped configs keep max_order_qty at its default of 1 and
        mode "fixed" -- but even if an operator flips to notional mode
        without also raising max_order_qty, the operator's (default) cap
        of 1 still binds; notional mode alone cannot widen it."""
        limits = replace(RiskLimits(), max_order_qty_mode="notional", max_order_notional_usd=D("1000"))
        self.assertEqual(limits.effective_max_order_qty("100"), D("1"))

    def test_invalid_mode_rejected_at_construction(self):
        with self.assertRaises(SafetyError):
            replace(RiskLimits(), max_order_qty_mode="unbounded")

    def test_notional_mode_enforced_through_reserve_intent(self):
        import tempfile
        with tempfile.TemporaryDirectory() as root:
            limits = replace(RiskLimits(), max_order_qty_mode="notional", max_order_qty=D("9"),
                             max_order_notional_usd=D("1000"), max_gross_exposure_usd=D("5000"))
            ledger = Ledger(Path(root) / "journal.db", limits)
            now = 1_800_000_000.0
            ledger.start_trial(now)
            quote = Quote("SPY", "99.99", "100.00", now)
            # D4 (round 3): the notional cap is derived from the live
            # quote's own ask (100.00) for this buy, not the order's own
            # limit price (100.02) -- floor(1000/100.00) = 10 shares, and
            # the operator's own configured max_order_qty=9 is the
            # tighter, binding constraint here regardless (see
            # test_reserve_intent_uses_the_quote_price_not_the_limit_price_for_the_notional_cap
            # below for a case where the price source alone changes the
            # result). 9 shares * 100.02 = 900.18 <= max_order_notional_usd,
            # so this would have been rejected outright under the pre-G-f
            # fixed cap of 1 share but succeeds here.
            reserved = ledger.reserve_intent("buy-1", "SPY", "buy", "9", "100.02", quote=quote,
                                             now=now, market_open=True, session_close=now + 3600,
                                             stop_file=Path(root) / "STOP")
            self.assertEqual(reserved.qty, D("9"))
            with self.assertRaises(SafetyError):
                ledger.reserve_intent("buy-2", "SPY", "buy", "11", "100.02", quote=quote,
                                      now=now, market_open=True, session_close=now + 3600,
                                      stop_file=Path(root) / "STOP")
            ledger.close()

    # -- D4 (round 3): the notional-implied qty is derived from the live
    #    quote price, not the order's own (possibly offset) limit price --

    def test_effective_max_order_qty_uses_quote_price_when_given(self):
        limits = replace(RiskLimits(), max_order_qty_mode="notional", max_order_qty=D("50"),
                         max_order_notional_usd=D("1000"))
        # quote_price=100 -> floor(1000/100) = 10, ignoring the unrelated
        # `price` (200) entirely.
        self.assertEqual(limits.effective_max_order_qty("200", quote_price="100"), D("10"))

    def test_effective_max_order_qty_falls_back_to_price_without_quote_price(self):
        limits = replace(RiskLimits(), max_order_qty_mode="notional", max_order_qty=D("50"),
                         max_order_notional_usd=D("1000"))
        self.assertEqual(limits.effective_max_order_qty("200"), D("5"))

    def test_reserve_intent_uses_the_quote_price_not_the_limit_price_for_the_notional_cap(self):
        """D4 (round 3), end-to-end via reserve_intent. For a SELL, using
        a lower reference price (the pre-fix behavior used the order's own
        limit price -- here 60.00, well below the quote's bid) inflates
        floor(notional/price): old cap = floor(3000/60.00) = 50, clamped
        by max_order_qty=60 to 50 -- would have let a 35-share sell
        through (35*60.00 = 2100 <= max_order_notional_usd, so the
        separate qty*price check would not itself have refused it
        either). The live quote's own bid of 100.00 gives the correct cap:
        floor(3000/100.00) = 30. 35 shares must now be refused; 30 must
        still be accepted (the position is large enough for both, built
        up via two smaller buys that each individually clear the same
        notional-mode cap at the ask)."""
        import tempfile
        with tempfile.TemporaryDirectory() as root:
            limits = replace(RiskLimits(), max_order_qty_mode="notional", max_order_qty=D("60"),
                             max_order_notional_usd=D("3000"), max_gross_exposure_usd=D("5000"))
            ledger = Ledger(Path(root) / "journal.db", limits)
            now = 1_800_000_000.0
            ledger.start_trial(now)
            quote = Quote("SPY", "100.00", "100.01", now)
            # Build a 40-share position via two buys (each: qty=20 <=
            # effective_max_order_qty(quote_price=100.01)=floor(3000/100.01)=29,
            # cost 20*100.01=2000.2 <= 3000), comfortably covering both
            # sell attempts below.
            for cid, broker_id in (("buy-1", "broker-buy-1"), ("buy-2", "broker-buy-2")):
                ledger.reserve_intent(cid, "SPY", "buy", "20", "100.01", quote=quote, now=now,
                                      market_open=True, session_close=now + 3600, stop_file=Path(root) / "STOP")
                ledger.record_order(cid, broker_id, "filled", "20", "100.00", timestamp=now)
            self.assertEqual(ledger.positions()["SPY"].qty, D("40"))
            # Direct unit-level confirmation of the price-source distinction.
            self.assertEqual(limits.effective_max_order_qty("60.00"), D("50"))  # fallback path
            self.assertEqual(limits.effective_max_order_qty("60.00", quote_price="100.00"), D("30"))
            with self.assertRaises(SafetyError):
                ledger.reserve_intent("sell-1", "SPY", "sell", "35", "60.00", quote=quote,
                                      now=now, market_open=True, session_close=now + 3600,
                                      stop_file=Path(root) / "STOP")
            reserved = ledger.reserve_intent("sell-2", "SPY", "sell", "30", "60.00", quote=quote,
                                             now=now, market_open=True, session_close=now + 3600,
                                             stop_file=Path(root) / "STOP")
            self.assertEqual(reserved.qty, D("30"))
            ledger.close()


@unittest.skipUnless(NATIVE, "requires pinned Nautilus 2.0.0rc5 runtime")
class ReplaceExitTests(unittest.TestCase):
    """Deliverable 2: native_strategy.AdaptiveStrategy.replace_exit --
    cancel-then-submit only (native_adapter.py rejects order modify),
    busy-set, residue protection, and the per-symbol exit_attempts cap.
    Real (not added to any node) AdaptiveStrategy construction with fakes
    for policy/ledger/order_factory/submit_order/cancel_order, matching
    tests/test_adaptive_paper_sessions.py's GapRiskExitChainTests and
    tests/test_adaptive_paper_runner.py's FakeStrategy pattern."""

    class _FakeQuote:
        def __init__(self, bid, ask, timestamp):
            self.bid, self.ask, self.timestamp = bid, ask, timestamp

    class _FakePolicyConfig:
        def __init__(self, *, quote_age_seconds=3, max_shares=5, exit_replace_max_attempts=3,
                    exit_replace_tolerance_bps=0, exit_replace_min_interval_seconds=0,
                    gap_stop_enabled=False, exit_replace_enabled=True):
            self.quote_age_seconds = quote_age_seconds
            self.max_shares = max_shares
            self.exit_replace_max_attempts = exit_replace_max_attempts
            self.exit_replace_tolerance_bps = exit_replace_tolerance_bps
            self.exit_replace_min_interval_seconds = exit_replace_min_interval_seconds
            # Round 5: this class's tests call replace_exit/on_order_* directly,
            # not rebalance(), so the gap-risk hook is never exercised here;
            # off by default defensively.
            self.gap_stop_enabled = gap_stop_enabled
            # Round 8: this class's tests call replace_exit directly, not
            # through rebalance()'s new opt-in gate -- default True here
            # so every existing direct-call test keeps exercising
            # replace_exit exactly as before; RebalanceBusySymbolReplaceExitTests
            # covers the gate itself (both states) at the rebalance() level.
            self.exit_replace_enabled = exit_replace_enabled

    class _FakePolicy:
        def __init__(self, config):
            self.latest = {}
            self.config = config

    class _FakeLedger:
        def intents(self):
            return []

        def prior_rth_closes(self):
            return {}

    def strategy(self, *, exit_replace_max_attempts=3, exit_replace_tolerance_bps=0,
                exit_replace_min_interval_seconds=0, synchronous_cancel=False, clock=lambda: 1000.0,
                exit_replace_enabled=True):
        from native_strategy import AdaptiveStrategy

        class FakeOrderFactory:
            def __init__(self):
                self.calls = []

            def limit(self, instrument_id, side, quantity, price, *, time_in_force, client_order_id, tags):
                self.calls.append({"instrument_id": str(instrument_id), "side": side,
                                   "quantity": str(quantity), "price": str(price),
                                   "tags": list(tags), "client_order_id": str(client_order_id)})
                return self.calls[-1]

        class FakeStrategy(AdaptiveStrategy):
            @property
            def order_factory(self):
                return self._fake_order_factory

        config = self._FakePolicyConfig(exit_replace_max_attempts=exit_replace_max_attempts,
                                        exit_replace_tolerance_bps=exit_replace_tolerance_bps,
                                        exit_replace_min_interval_seconds=exit_replace_min_interval_seconds,
                                        exit_replace_enabled=exit_replace_enabled)
        policy = self._FakePolicy(config)
        # D2 (round 6): on_order_canceled now reads the ack-time clock
        # (self._clock()), not a frozen requested_now -- default to 1000.0,
        # the synthetic `now` every existing test in this class already
        # uses; a test exercising a genuinely different ack-time clock
        # passes its own `clock=`.
        strategy = FakeStrategy(policy, self._FakeLedger(), "fixture", clock=clock)
        strategy._fake_order_factory = FakeOrderFactory()
        strategy.submitted, strategy.cancelled = [], []
        strategy.submit_order = strategy.submitted.append
        if synchronous_cancel:
            # D3: a port/fake whose cancel_order acknowledges inline, before
            # cancel_order() itself returns -- exercises the exact race
            # replace_exit's D3 fix (mutate-before-cancel) closes.
            def synchronous_cancel_order(cid):
                strategy.cancelled.append(str(cid))
                class Event:
                    client_order_id = cid
                strategy.on_order_canceled(Event())
            strategy.cancel_order = synchronous_cancel_order
        else:
            strategy.cancel_order = lambda cid: strategy.cancelled.append(str(cid))
        return strategy

    def seed_resting_sell(self, strategy, symbol="AAPL", price_rule="stop", client_id="adp-fixture-0000001",
                          price=None):
        entry = {"symbol": symbol, "side": "sell", "created": 1000.0, "price_rule": price_rule}
        if price is not None:
            entry["price"] = price
        strategy.pending[client_id] = entry
        return client_id

    def test_replace_cancels_resting_order_when_price_rule_changes(self):
        strategy = self.strategy()
        client_id = self.seed_resting_sell(strategy, price_rule="stop")
        ok = strategy.replace_exit("AAPL", 1000.0, D("3"), "trailing_stop")
        self.assertEqual(ok, "cancel_requested")
        self.assertEqual(strategy.cancelled, [client_id])
        self.assertTrue(strategy.pending[client_id]["cancel_requested"])
        self.assertIn("replace_with", strategy.pending[client_id])

    def test_no_op_when_price_rule_is_unchanged(self):
        strategy = self.strategy()
        self.seed_resting_sell(strategy, price_rule="trailing")
        ok = strategy.replace_exit("AAPL", 1000.0, D("3"), "trailing_stop")
        self.assertEqual(ok, "noop")
        self.assertEqual(strategy.cancelled, [])

    def test_no_op_when_nothing_resting_for_symbol(self):
        strategy = self.strategy()
        ok = strategy.replace_exit("AAPL", 1000.0, D("3"), "trailing_stop")
        self.assertEqual(ok, "refused")
        self.assertEqual(strategy.cancelled, [])

    def test_no_op_for_non_positive_quantity(self):
        strategy = self.strategy()
        self.seed_resting_sell(strategy, price_rule="stop")
        ok = strategy.replace_exit("AAPL", 1000.0, D("0"), "trailing_stop")
        self.assertEqual(ok, "refused")
        self.assertEqual(strategy.cancelled, [])

    def test_busy_set_prevents_double_submit_before_cancel_is_acked(self):
        strategy = self.strategy()
        self.seed_resting_sell(strategy, price_rule="stop")
        self.assertEqual(strategy.replace_exit("AAPL", 1000.0, D("3"), "trailing_stop"), "cancel_requested")
        self.assertIn("AAPL", strategy._exit_replace_busy)
        # A second call before on_order_canceled fires must not cancel again.
        ok = strategy.replace_exit("AAPL", 1000.1, D("3"), "trailing_stop")
        self.assertEqual(ok, "refused")
        self.assertEqual(len(strategy.cancelled), 1)

    def test_on_order_canceled_submits_the_replacement_and_clears_busy(self):
        strategy = self.strategy()
        client_id = self.seed_resting_sell(strategy, price_rule="stop")
        strategy.replace_exit("AAPL", 1000.0, D("3"), "trailing_stop")
        # D5 (round 4): _submit_replacement_exit (invoked from
        # on_order_canceled) now uses the SAME caller-supplied `now`
        # (1000.0, staged by replace_exit above) for its freshness check
        # -- no separate wall-clock read -- so the fake quote must be
        # timestamped on that same clock, not real wall-clock time.
        strategy.policy.latest["AAPL"] = self._FakeQuote(100.0, 100.02, 1000.0)

        class Event:
            client_order_id = client_id
        strategy.on_order_canceled(Event())

        self.assertNotIn("AAPL", strategy._exit_replace_busy)
        self.assertEqual(len(strategy.submitted), 1)
        self.assertEqual(len(strategy._fake_order_factory.calls), 1)
        call = strategy._fake_order_factory.calls[0]
        self.assertIn("strategy=trailing_stop", call["tags"])
        self.assertIn("price_rule=trailing", call["tags"])
        # D5 (round 2): _exit_price_rule was removed as dead (write-only)
        # state; self.pending[...]["price_rule"] is the single source
        # replace_exit itself reads, asserted below.
        self.assertFalse(hasattr(strategy, "_exit_price_rule"))
        self.assertEqual(len(strategy.pending), 1)
        new_client_id = next(iter(strategy.pending))
        self.assertEqual(strategy.pending[new_client_id]["price_rule"], "trailing")

    def test_residue_protection_skips_replacement_without_a_fresh_quote_but_clears_busy(self):
        """No resubmission happens synchronously without a fresh quote, but
        the symbol is freed from the busy-set so the very next ordinary
        rebalance() exit-action tick (not exercised here, see
        native_strategy.AdaptiveStrategy.replace_exit's docstring) is free
        to resubmit it from live held-vs-target -- residue is never
        permanently unprotected."""
        strategy = self.strategy()
        client_id = self.seed_resting_sell(strategy, price_rule="stop")
        strategy.replace_exit("AAPL", 1000.0, D("3"), "trailing_stop")
        # No quote observed at all for AAPL.
        class Event:
            client_order_id = client_id
        strategy.on_order_canceled(Event())

        self.assertNotIn("AAPL", strategy._exit_replace_busy)
        self.assertEqual(strategy.submitted, [])
        self.assertNotIn(client_id, strategy.pending)  # the cancelled resting order is gone

    def test_exit_attempts_cap_refuses_further_replacement(self):
        strategy = self.strategy(exit_replace_max_attempts=2)
        client_id = self.seed_resting_sell(strategy, price_rule="stop")
        strategy.policy.latest["AAPL"] = self._FakeQuote(100.0, 100.02, 1000.0)

        def cycle(rule, cid):
            class Event:
                client_order_id = cid
            self.assertEqual(strategy.replace_exit("AAPL", 1000.0, D("3"), rule), "cancel_requested")
            strategy.on_order_canceled(Event())
            return next(iter(c for c in strategy.pending if strategy.pending[c]["symbol"] == "AAPL"))

        client_id = cycle("trailing_stop", client_id)   # attempt 1
        client_id = cycle("stop_loss", client_id)        # attempt 2, reaches the cap
        self.assertEqual(strategy._exit_attempts["AAPL"], 2)
        ok = strategy.replace_exit("AAPL", 1000.0, D("3"), "trailing_stop")
        self.assertEqual(ok, "refused")  # capped: no further cancel-then-replace this session

    def test_attempts_are_tracked_per_symbol(self):
        strategy = self.strategy(exit_replace_max_attempts=1)
        self.seed_resting_sell(strategy, symbol="AAPL", price_rule="stop", client_id="adp-fixture-0000001")
        self.seed_resting_sell(strategy, symbol="MSFT", price_rule="stop", client_id="adp-fixture-0000002")
        self.assertEqual(strategy.replace_exit("AAPL", 1000.0, D("3"), "trailing_stop"), "cancel_requested")
        # MSFT has not been attempted yet, so it is unaffected by AAPL's cap.
        self.assertEqual(strategy.replace_exit("MSFT", 1000.0, D("3"), "trailing_stop"), "cancel_requested")

    # -- D1 (round 2): price-change gating -----------------------------

    def test_ratcheting_trail_same_price_rule_but_moved_price_triggers_replace(self):
        """The exact bug D1 fixes: a resting trailing-stop exit recomputes
        the *same* price_rule ("trailing") every tick while its actual
        limit price tightens. Gating on price_rule alone (the pre-fix
        behavior) never replaces it; gating on price OR price_rule does."""
        strategy = self.strategy()
        client_id = self.seed_resting_sell(strategy, price_rule="trailing", price="99.90")
        strategy.policy.latest["AAPL"] = self._FakeQuote(100.20, 100.22, 1000.0)  # new, higher trail level
        ok = strategy.replace_exit("AAPL", 1000.0, D("3"), "trailing_stop")  # same price_rule as resting
        self.assertEqual(ok, "cancel_requested")
        self.assertEqual(strategy.cancelled, [client_id])

    def test_unchanged_price_and_rule_with_default_tolerance_is_a_no_op(self):
        strategy = self.strategy()
        # limit_price("sell") = bid - .02 by default; a resting price
        # recorded exactly at that computed value, with an identical quote,
        # must not be treated as "changed".
        self.seed_resting_sell(strategy, price_rule="trailing", price="99.98")
        strategy.policy.latest["AAPL"] = self._FakeQuote(100.00, 100.02, 1000.0)
        ok = strategy.replace_exit("AAPL", 1000.0, D("3"), "trailing_stop")
        self.assertEqual(ok, "noop")
        self.assertEqual(strategy.cancelled, [])

    def test_tolerance_bps_suppresses_a_small_price_move(self):
        strategy = self.strategy(exit_replace_tolerance_bps=50)  # 0.5%
        self.seed_resting_sell(strategy, price_rule="trailing", price="100.00")
        # ~0.1% move: well inside a 50bps tolerance.
        strategy.policy.latest["AAPL"] = self._FakeQuote(100.10, 100.12, 1000.0)
        ok = strategy.replace_exit("AAPL", 1000.0, D("3"), "trailing_stop")
        self.assertEqual(ok, "noop")

    def test_tolerance_bps_still_allows_a_large_price_move(self):
        strategy = self.strategy(exit_replace_tolerance_bps=50)  # 0.5%
        client_id = self.seed_resting_sell(strategy, price_rule="trailing", price="100.00")
        # ~2% move: well past a 50bps tolerance.
        strategy.policy.latest["AAPL"] = self._FakeQuote(102.00, 102.02, 1000.0)
        ok = strategy.replace_exit("AAPL", 1000.0, D("3"), "trailing_stop")
        self.assertEqual(ok, "cancel_requested")
        self.assertEqual(strategy.cancelled, [client_id])

    def test_min_interval_seconds_rate_limits_repeated_replacement(self):
        now0 = 3_000_000.0
        strategy = self.strategy(exit_replace_min_interval_seconds=10, clock=lambda: now0)
        client_id = self.seed_resting_sell(strategy, price_rule="trailing", price="99.90")
        strategy.policy.latest["AAPL"] = self._FakeQuote(100.20, 100.22, now0)
        self.assertEqual(strategy.replace_exit("AAPL", now0, D("3"), "trailing_stop"), "cancel_requested")

        # Ack the cancel (a real resting replacement order must exist for a
        # later replace_exit call to have anything to compare a price
        # against) and confirm a fresh resting order landed in self.pending.
        class Event:
            client_order_id = client_id
        strategy.on_order_canceled(Event())
        self.assertNotIn("AAPL", strategy._exit_replace_busy)
        self.assertEqual(len(strategy.pending), 1)
        new_client_id = next(iter(strategy.pending))

        strategy.policy.latest["AAPL"] = self._FakeQuote(100.40, 100.42, now0)
        too_soon = strategy.replace_exit("AAPL", now0 + 5, D("3"), "trailing_stop")  # only 5s later
        self.assertEqual(too_soon, "refused")

        strategy.policy.latest["AAPL"] = self._FakeQuote(100.60, 100.62, now0)
        past_interval = strategy.replace_exit("AAPL", now0 + 11, D("3"), "trailing_stop")  # 11s later
        self.assertEqual(past_interval, "cancel_requested")
        self.assertEqual(strategy.cancelled, [client_id, new_client_id])

    # -- D3 (round 2): synchronous cancel acknowledgement ---------------

    def test_synchronous_cancel_ack_does_not_raise_keyerror(self):
        """D3: replace_exit must not access self.pending[client_id] after
        calling cancel_order -- a synchronous ack (cancel_order invoking
        on_order_canceled inline, e.g. SimulatedPort/backtest) pops it
        during that very call."""
        strategy = self.strategy(synchronous_cancel=True)
        self.seed_resting_sell(strategy, price_rule="stop")
        strategy.policy.latest["AAPL"] = self._FakeQuote(100.0, 100.02, 1000.0)
        ok = strategy.replace_exit("AAPL", 1000.0, D("3"), "trailing_stop")  # must not raise
        self.assertEqual(ok, "cancel_requested")
        self.assertEqual(len(strategy.cancelled), 1)
        # The synchronous ack already ran on_order_canceled -> submitted the
        # replacement and cleared the busy-set, all within replace_exit's
        # own call.
        self.assertNotIn("AAPL", strategy._exit_replace_busy)
        self.assertEqual(len(strategy.submitted), 1)

    # -- D1 (round 3): busy/staged-replacement release on every terminal
    #    path, not just on_order_canceled -------------------------------

    def _stage_replacement(self, strategy, client_id):
        """Get `strategy` into "cancel-then-replace in flight" state for
        `client_id` without going through the real cancel_order (so the
        original resting order stays in self.pending, as it would for a
        real broker before any terminal event lands)."""
        strategy.policy.latest["AAPL"] = self._FakeQuote(100.20, 100.22, 1000.0)
        ok = strategy.replace_exit("AAPL", 1000.0, D("3"), "trailing_stop")
        self.assertTrue(ok)
        self.assertIn("AAPL", strategy._exit_replace_busy)
        self.assertIn("replace_with", strategy.pending[client_id])

    def test_on_order_filled_releases_busy_and_drops_staged_replacement(self):
        strategy = self.strategy()
        client_id = self.seed_resting_sell(strategy, price_rule="stop")
        self._stage_replacement(strategy, client_id)

        class Event:
            client_order_id = client_id
        strategy.on_order_filled(Event())

        self.assertNotIn("AAPL", strategy._exit_replace_busy)
        self.assertIsNone(strategy.pending[client_id]["replace_with"])
        # The stale replacement must never itself be submitted.
        self.assertEqual(strategy.submitted, [])

    def test_on_order_rejected_releases_busy_and_drops_staged_replacement(self):
        strategy = self.strategy()
        client_id = self.seed_resting_sell(strategy, price_rule="stop")
        self._stage_replacement(strategy, client_id)

        class Event:
            client_order_id = client_id
            reason = "some_transient_reason"
        strategy.on_order_rejected(Event())

        self.assertNotIn("AAPL", strategy._exit_replace_busy)
        self.assertNotIn(client_id, strategy.pending)  # on_order_rejected pops it
        self.assertEqual(strategy.submitted, [])

    def test_on_order_expired_releases_busy_and_drops_staged_replacement(self):
        strategy = self.strategy()
        client_id = self.seed_resting_sell(strategy, price_rule="stop")
        self._stage_replacement(strategy, client_id)

        class Event:
            client_order_id = client_id
        strategy.on_order_expired(Event())

        self.assertNotIn("AAPL", strategy._exit_replace_busy)
        self.assertNotIn(client_id, strategy.pending)
        self.assertEqual(strategy.submitted, [])

    def test_on_order_cancel_rejected_releases_busy_and_unmarks_cancel_requested(self):
        """The cancel itself failed: the resting order is still live and
        must become visible to _resting_exit_client_id / cancel_expired
        again (cancel_requested reset to False), and no replacement may be
        submitted for an order that was never actually cancelled."""
        strategy = self.strategy()
        client_id = self.seed_resting_sell(strategy, price_rule="stop")
        self._stage_replacement(strategy, client_id)
        self.assertTrue(strategy.pending[client_id]["cancel_requested"])

        class Event:
            client_order_id = client_id
        strategy.on_order_cancel_rejected(Event())

        self.assertNotIn("AAPL", strategy._exit_replace_busy)
        self.assertIsNone(strategy.pending[client_id]["replace_with"])
        self.assertFalse(strategy.pending[client_id]["cancel_requested"])
        self.assertEqual(strategy.submitted, [])
        # The order is resting and unmodified again -- visible to a fresh
        # replace_exit call.
        self.assertEqual(strategy._resting_exit_client_id("AAPL"), client_id)

    def test_on_order_denied_releases_busy_and_drops_staged_replacement(self):
        strategy = self.strategy()
        client_id = self.seed_resting_sell(strategy, price_rule="stop")
        self._stage_replacement(strategy, client_id)

        class Event:
            client_order_id = client_id
        strategy.on_order_denied(Event())

        self.assertNotIn("AAPL", strategy._exit_replace_busy)
        self.assertNotIn(client_id, strategy.pending)
        self.assertEqual(strategy.submitted, [])

    # -- D1 (round 5): fire-once cleared by a terminal non-fill for a
    #    gap_risk_stop order, kept on a genuine fill ---------------------

    def _seed_applied_gap_stop_order(self, strategy, client_id="adp-fixture-0000001"):
        strategy.pending[client_id] = {"symbol": "AAPL", "side": "sell", "created": 1000.0,
                                       "price_rule": "market", "reason": "gap_risk_stop"}
        strategy._gap_stop_applied.add("AAPL")
        return client_id

    def test_on_order_rejected_clears_fire_once_for_gap_risk_stop(self):
        strategy = self.strategy()
        client_id = self._seed_applied_gap_stop_order(strategy)

        class Event:
            client_order_id = client_id
            reason = "some_reason"
        strategy.on_order_rejected(Event())
        self.assertNotIn("AAPL", strategy._gap_stop_applied)

    def test_on_order_denied_clears_fire_once_for_gap_risk_stop(self):
        strategy = self.strategy()
        client_id = self._seed_applied_gap_stop_order(strategy)

        class Event:
            client_order_id = client_id
        strategy.on_order_denied(Event())
        self.assertNotIn("AAPL", strategy._gap_stop_applied)

    def test_on_order_expired_clears_fire_once_for_gap_risk_stop(self):
        strategy = self.strategy()
        client_id = self._seed_applied_gap_stop_order(strategy)

        class Event:
            client_order_id = client_id
        strategy.on_order_expired(Event())
        self.assertNotIn("AAPL", strategy._gap_stop_applied)

    def test_on_order_cancel_rejected_clears_fire_once_for_gap_risk_stop(self):
        strategy = self.strategy()
        client_id = self._seed_applied_gap_stop_order(strategy)

        class Event:
            client_order_id = client_id
        strategy.on_order_cancel_rejected(Event())
        self.assertNotIn("AAPL", strategy._gap_stop_applied)

    def test_on_order_filled_keeps_fire_once_for_gap_risk_stop(self):
        """A genuine fill must NOT clear fire-once -- the sell actually
        executed, the position is reduced/exited as intended."""
        strategy = self.strategy()
        client_id = self._seed_applied_gap_stop_order(strategy)

        class Event:
            client_order_id = client_id
        strategy.on_order_filled(Event())
        self.assertIn("AAPL", strategy._gap_stop_applied)

    def test_terminal_clearing_is_a_no_op_for_a_non_gap_stop_reason(self):
        strategy = self.strategy()
        client_id = self.seed_resting_sell(strategy, price_rule="stop")
        strategy.pending[client_id]["reason"] = "trailing_stop"
        strategy._gap_stop_applied.add("MSFT")  # unrelated symbol, must stay untouched

        class Event:
            client_order_id = client_id
            reason = "x"
        strategy.on_order_rejected(Event())
        self.assertIn("MSFT", strategy._gap_stop_applied)

    def test_ordinary_timeout_cancel_of_a_gap_risk_stop_order_clears_fire_once(self):
        """D1 (round 6): on_order_canceled was the only terminal handler
        that never called _clear_gap_stop_applied_if_matches -- an
        ORDINARY cancel (e.g. cancel_expired's plain timeout cancel, not a
        staged cancel-then-replace) of a gap_risk_stop sell reaches here
        with no `replace_with` staged. Left marked, the position would
        stay unprotected (fire-once "consumed") for the rest of the RTH
        session even though nothing is resting for it anymore."""
        strategy = self.strategy()
        client_id = self._seed_applied_gap_stop_order(strategy)
        # No replace_exit call here at all -- this is a plain timeout
        # cancel (cancel_expired), so self.pending[client_id] has no
        # "replace_with" key staged.
        self.assertNotIn("replace_with", strategy.pending[client_id])

        class Event:
            client_order_id = client_id
        strategy.on_order_canceled(Event())
        self.assertNotIn("AAPL", strategy._gap_stop_applied)
        self.assertNotIn(client_id, strategy.pending)

    def test_staged_replace_cancel_does_not_clear_fire_once_here(self):
        """The staged cancel-then-replace case must NOT clear fire-once in
        on_order_canceled -- the replacement itself carries the
        "gap_risk_stop" reason and (re-)marks fire-once only once it is
        actually submitted (see GapStopFireOnceOnlyAfterSubmitTests)."""
        strategy = self.strategy()
        client_id = self._seed_applied_gap_stop_order(strategy)
        strategy.policy.latest["AAPL"] = self._FakeQuote(90.0, 90.02, 1000.0)
        self.assertEqual(strategy.replace_exit("AAPL", 1000.0, D("3"), "gap_risk_stop"), "cancel_requested")
        self.assertIn("replace_with", strategy.pending[client_id])

        class Event:
            client_order_id = client_id
        strategy.on_order_canceled(Event())
        # The replacement was actually submitted (fresh quote, matching
        # clock), re-marking fire-once itself -- not cleared here.
        self.assertIn("AAPL", strategy._gap_stop_applied)
        self.assertEqual(len(strategy.submitted), 1)

    # -- D2 (round 7): a staged gap_risk_stop replacement that never gets
    #    submitted must clear fire-once too -------------------------------

    def test_replacement_abandoned_at_ack_time_clears_fire_once(self):
        """D2 (round 7): the OLD resting gap_risk_stop order is already
        successfully cancelled (that is how on_order_canceled got called
        at all); if the staged replacement then never gets submitted
        (no fresh quote at ack time), nothing is resting for this symbol
        any more, yet fire-once used to stay marked -- reading the stop as
        "already fired" for the rest of the session with no order actually
        protecting the position."""
        strategy = self.strategy()
        client_id = self._seed_applied_gap_stop_order(strategy)
        strategy.policy.latest["AAPL"] = self._FakeQuote(90.0, 90.02, 1000.0)
        self.assertEqual(strategy.replace_exit("AAPL", 1000.0, D("3"), "gap_risk_stop"), "cancel_requested")
        self.assertIn("AAPL", strategy._gap_stop_applied)  # still marked (staged, not yet resolved)

        # No quote at ack time -- the replacement is abandoned.
        del strategy.policy.latest["AAPL"]

        class Event:
            client_order_id = client_id
        strategy.on_order_canceled(Event())

        self.assertEqual(strategy.submitted, [])  # nothing was actually submitted
        self.assertNotIn("AAPL", strategy._gap_stop_applied)  # cleared: the stop is unarmed now

    def test_replacement_dropped_by_a_terminal_original_order_clears_fire_once(self):
        """The mirror case in _release_staged_replacement: the ORIGINAL
        order terminates some other way (here: rejected) before the
        staged gap_risk_stop replacement is ever acknowledged/submitted."""
        strategy = self.strategy()
        client_id = self._seed_applied_gap_stop_order(strategy)
        strategy.policy.latest["AAPL"] = self._FakeQuote(90.0, 90.02, 1000.0)
        self.assertEqual(strategy.replace_exit("AAPL", 1000.0, D("3"), "gap_risk_stop"), "cancel_requested")
        self.assertIn("AAPL", strategy._gap_stop_applied)

        class Event:
            client_order_id = client_id
            reason = "some_reason"
        strategy.on_order_rejected(Event())

        self.assertEqual(strategy.submitted, [])
        self.assertNotIn("AAPL", strategy._gap_stop_applied)

    # -- D3 (round 7): a cancel-reject rolls back the attempt/min-interval
    #    accounting replace_exit consumed -- no replacement happened -----

    def test_cancel_rejected_rolls_back_attempts_but_not_last_replace_at(self):
        """D1 (round 8): exit_attempts IS still rolled back (no
        replacement actually happened, so it must not silently burn part
        of the attempts budget) -- but _last_replace_at is deliberately
        NOT rolled back anymore (round 7 rolled it back too). Rolling it
        back removed the only bound (the min-interval gate) on a broker
        that keeps refusing to cancel the same resting order: without
        this, replace_exit could be retried again on the very next tick,
        forever. See __init__'s _cancel_reject_counts docstring for the
        separate, never-rolled-back cap that bounds it outright on top of
        this spacing."""
        strategy = self.strategy(exit_replace_max_attempts=2)
        client_id = self.seed_resting_sell(strategy, price_rule="stop")
        self.assertNotIn("AAPL", strategy._exit_attempts)
        self.assertNotIn("AAPL", strategy._last_replace_at)

        strategy.policy.latest["AAPL"] = self._FakeQuote(90.0, 90.02, 1000.0)
        self.assertEqual(strategy.replace_exit("AAPL", 1000.0, D("3"), "trailing_stop"), "cancel_requested")
        self.assertEqual(strategy._exit_attempts["AAPL"], 1)
        self.assertEqual(strategy._last_replace_at["AAPL"], 1000.0)

        class Event:
            client_order_id = client_id
        strategy.on_order_cancel_rejected(Event())

        # exit_attempts rolled back to its pre-attempt value (0) -- no
        # replacement happened. _last_replace_at stays at the value the
        # (refused) attempt set, preserving min-interval spacing for the
        # next retry.
        self.assertEqual(strategy._exit_attempts.get("AAPL", 0), 0)
        self.assertEqual(strategy._last_replace_at["AAPL"], 1000.0)
        self.assertEqual(strategy._cancel_reject_counts.get("AAPL", 0), 1)

    def test_cancel_rejected_rollback_restores_prior_nonzero_attempts_not_just_clears_them(self):
        """The exit_attempts rollback must restore the actual pre-attempt
        value (not merely reset to "unset"), so a symbol already replaced
        once before this attempt keeps its real attempt count after a
        cancel-reject undoes only THIS attempt. _last_replace_at (round 8:
        no longer rolled back at all) keeps the SECOND attempt's value,
        not the first's -- it always reflects the most recent replace_exit
        call, successful or refused."""
        strategy = self.strategy(exit_replace_max_attempts=3, synchronous_cancel=False)
        client_id = self.seed_resting_sell(strategy, price_rule="stop")

        # First, a genuinely successful replace (consumes attempt 1, sets
        # last_replace_at) -- simulate its ack directly.
        strategy.policy.latest["AAPL"] = self._FakeQuote(90.0, 90.02, 1000.0)
        self.assertEqual(strategy.replace_exit("AAPL", 1000.0, D("3"), "trailing_stop"), "cancel_requested")

        class Event:
            client_order_id = client_id
        strategy.on_order_canceled(Event())  # acks -> submits the replacement
        self.assertEqual(strategy._exit_attempts["AAPL"], 1)
        self.assertEqual(strategy._last_replace_at["AAPL"], 1000.0)
        new_client_id = next(iter(strategy.pending))

        # A second replace attempt whose cancel then gets rejected.
        strategy.policy.latest["AAPL"] = self._FakeQuote(95.0, 95.02, 1010.0)
        self.assertEqual(strategy.replace_exit("AAPL", 1010.0, D("3"), "trailing_stop"), "cancel_requested")
        self.assertEqual(strategy._exit_attempts["AAPL"], 2)
        self.assertEqual(strategy._last_replace_at["AAPL"], 1010.0)

        class Event2:
            client_order_id = new_client_id
        strategy.on_order_cancel_rejected(Event2())

        # exit_attempts restored to the value from the FIRST (successful)
        # attempt, not cleared to "never replaced". _last_replace_at stays
        # at 1010.0 (round 8: never rolled back).
        self.assertEqual(strategy._exit_attempts["AAPL"], 1)
        self.assertEqual(strategy._last_replace_at["AAPL"], 1010.0)
        self.assertEqual(strategy._cancel_reject_counts.get("AAPL", 0), 1)

    def test_repeated_cancel_rejects_are_bounded_by_a_separate_counter(self):
        """D1 (round 8) regression: since exit_attempts is rolled back on
        every cancel-reject, that budget alone never bounds a broker that
        keeps refusing to cancel the same resting order -- replace_exit
        would otherwise be retried and cancel-rejected forever, each
        attempt fully refunded. A SEPARATE, never-rolled-back
        _cancel_reject_counts must cap replace_exit's refusal at
        exit_replace_max_attempts, independent of exit_attempts."""
        strategy = self.strategy(exit_replace_max_attempts=2,
                                 exit_replace_min_interval_seconds=0)
        client_id = self.seed_resting_sell(strategy, price_rule="stop")

        class Event:
            client_order_id = client_id

        for i in range(2):
            strategy.policy.latest["AAPL"] = self._FakeQuote(90.0, 90.02, 1000.0 + i)
            result = strategy.replace_exit("AAPL", 1000.0 + i, D("3"), "trailing_stop")
            self.assertEqual(result, "cancel_requested")
            strategy.on_order_cancel_rejected(Event())
            # exit_attempts always rolls back to 0 -- never bounds this loop.
            self.assertEqual(strategy._exit_attempts.get("AAPL", 0), 0)

        self.assertEqual(strategy._cancel_reject_counts["AAPL"], 2)
        # A third attempt is refused outright, bounded by
        # _cancel_reject_counts reaching exit_replace_max_attempts (2),
        # even though exit_attempts itself is still 0.
        strategy.policy.latest["AAPL"] = self._FakeQuote(90.0, 90.02, 1002.0)
        self.assertEqual(strategy.replace_exit("AAPL", 1002.0, D("3"), "trailing_stop"), "refused")

    def test_terminal_release_is_a_no_op_when_nothing_was_staged(self):
        """A plain (non-replace-staged) resting order terminating normally
        must not error or touch a busy-set entry that was never set."""
        strategy = self.strategy()
        client_id = self.seed_resting_sell(strategy, price_rule="stop")

        class Event:
            client_order_id = client_id
        strategy.on_order_filled(Event())  # must not raise
        self.assertEqual(strategy._exit_replace_busy, set())

    def test_partial_fill_residue_gets_a_fresh_resting_exit_next_tick(self):
        """D1 (round 3) residue protection: after on_order_filled releases
        busy for a partially-filled, replace-staged order, the very next
        rebalance() tick (not the terminal handler itself) is responsible
        for resubmitting a resting exit for whatever remains -- exercised
        at the rebalance() level via RebalanceBusySymbolReplaceExitTests'
        harness below; this test only locks in the precondition that
        on_order_filled leaves the symbol free (not busy) for that tick to
        act on."""
        strategy = self.strategy()
        client_id = self.seed_resting_sell(strategy, price_rule="stop")
        self._stage_replacement(strategy, client_id)

        class Event:
            client_order_id = client_id
        strategy.on_order_filled(Event())  # a partial fill, from the strategy's point of view
        self.assertNotIn("AAPL", strategy._exit_replace_busy)  # symbol not permanently blocked

    # -- D5 (round 4): ONE clock convention (the caller-supplied `now`),
    #    no separate wall-clock read -------------------------------------

    def test_replacement_works_under_a_synthetic_clock_where_now_differs_from_time_time(self):
        """D5 (round 4)/D2 (round 6): replace_exit/_submit_replacement_exit
        must work end to end on a synthetic clock far from real wall-clock
        time -- the ack-time clock (self._clock(), see the strategy()
        factory's `clock=` override) and the quote's own timestamp are
        both on that same synthetic clock here."""
        synthetic_now = 5_000_000.0  # far from real wall-clock time
        strategy = self.strategy(clock=lambda: synthetic_now)
        client_id = self.seed_resting_sell(strategy, price_rule="stop")
        strategy.policy.latest["AAPL"] = self._FakeQuote(100.20, 100.22, synthetic_now)
        self.assertEqual(strategy.replace_exit("AAPL", synthetic_now, D("3"), "trailing_stop"),
                         "cancel_requested")
        staged = strategy.pending[client_id]["replace_with"]
        # D4 (round 8): "requested_now" was removed (dead/write-only);
        # only "previous_attempts" remains on the staged dict.
        self.assertNotIn("requested_now", staged)
        self.assertEqual(staged["previous_attempts"], 0)

        # The quote is still fresh on the SAME synthetic clock at ack time.
        strategy.policy.latest["AAPL"] = self._FakeQuote(100.0, 100.02, synthetic_now)

        class Event:
            client_order_id = client_id
        strategy.on_order_canceled(Event())

        self.assertEqual(len(strategy.submitted), 1)
        new_client_id = next(iter(strategy.pending))
        # "created" is stamped on the exact same synthetic clock, not real
        # wall-clock time (which would differ by ~1.7 billion seconds).
        self.assertEqual(strategy.pending[new_client_id]["created"], synthetic_now)

    def test_replacement_skipped_when_quote_is_stale_at_ack_time(self):
        """The freshness check still correctly rejects an actually-stale
        quote -- "stale" is judged against the ack-time clock (matching
        quote.timestamp's clock in live mode), not requested_now."""
        synthetic_now = 5_000_000.0
        strategy = self.strategy(clock=lambda: synthetic_now)
        client_id = self.seed_resting_sell(strategy, price_rule="stop")
        strategy.policy.latest["AAPL"] = self._FakeQuote(100.20, 100.22, synthetic_now)
        self.assertEqual(strategy.replace_exit("AAPL", synthetic_now, D("3"), "trailing_stop"),
                         "cancel_requested")
        # A quote timestamped well before the ack-time clock, beyond
        # quote_age_seconds (3s default in this fake config).
        strategy.policy.latest["AAPL"] = self._FakeQuote(100.0, 100.02, synthetic_now - 10)

        class Event:
            client_order_id = client_id
        strategy.on_order_canceled(Event())
        self.assertEqual(strategy.submitted, [])  # skipped: genuinely stale at ack time
        self.assertNotIn("AAPL", strategy._exit_replace_busy)

    # -- D2 (round 6): the ack-time clock, not the frozen requested_now --

    def test_ack_arriving_later_than_request_accepts_a_quote_fresh_at_ack_time(self):
        """The exact bug D2 fixes: in live asynchronous operation the
        cancel ack can arrive well after the request (network/broker
        latency). requested_now (the clock at REQUEST time) must not be
        used for the ack-time freshness check -- a quote fresh at the
        (later) ack time, but stamped more than
        QUOTE_FUTURE_TOLERANCE_SECONDS (0.25s) ahead of requested_now,
        used to be wrongly rejected as "from the future" relative to that
        stale frozen clock."""
        request_now = 1_000_000.0
        ack_now = request_now + 2.0  # the ack arrives 2s after the request
        strategy = self.strategy(clock=lambda: ack_now)
        client_id = self.seed_resting_sell(strategy, price_rule="stop")
        strategy.policy.latest["AAPL"] = self._FakeQuote(100.20, 100.22, request_now)
        self.assertEqual(strategy.replace_exit("AAPL", request_now, D("3"), "trailing_stop"),
                         "cancel_requested")
        staged = strategy.pending[client_id]["replace_with"]
        # D4 (round 8): the write-only "requested_now" field was removed
        # from the staged dict entirely -- only "previous_attempts" (used
        # by on_order_cancel_rejected's rollback) remains.
        self.assertNotIn("requested_now", staged)
        self.assertEqual(staged["previous_attempts"], 0)

        # A quote fresh AT ACK TIME (ack_now), but stamped 2s -- well past
        # QUOTE_FUTURE_TOLERANCE_SECONDS -- ahead of the stale request_now.
        # The round-5 (requested_now-based) freshness check would have
        # rejected this as future-stamped; the round-6 fix (ack-time
        # clock) must accept it.
        strategy.policy.latest["AAPL"] = self._FakeQuote(100.0, 100.02, ack_now)

        class Event:
            client_order_id = client_id
        strategy.on_order_canceled(Event())

        self.assertEqual(len(strategy.submitted), 1)
        new_client_id = next(iter(strategy.pending))
        self.assertEqual(strategy.pending[new_client_id]["created"], ack_now)


class _FakeDecision:
    def __init__(self, targets, exits):
        self.targets, self.exits = targets, exits
        self.regime, self.effective_leverage, self.signals = "trend", 0.0, ()


class _FakePosition:
    def __init__(self, symbol, qty, average_cost):
        self.symbol, self.qty, self.average_cost = symbol, qty, average_cost


@unittest.skipUnless(NATIVE, "requires pinned Nautilus 2.0.0rc5 runtime")
class RebalanceBusySymbolReplaceExitTests(unittest.TestCase):
    """Drives replace_exit through rebalance()'s own busy-symbol branch
    (not calling replace_exit directly), using a fully fake policy/ledger
    across two rebalance() ticks: tick 1 submits a fresh trailing-stop
    exit order; tick 2 keeps the same "trailing_stop" reason (so price_rule
    is unchanged) but the quote has moved, landing in rebalance()'s
    `if symbol in busy:` branch and exercising replace_exit from there."""

    class _FakePolicyConfig:
        quote_age_seconds = 3
        max_shares = 5
        exit_replace_max_attempts = 3
        exit_replace_tolerance_bps = 0
        exit_replace_min_interval_seconds = 0
        gap_stop_enabled = False  # this class tests the trailing-stop replace path only
        exit_replace_enabled = True  # round 8: default on for this class; see the dedicated
                                      # disabled-state test below for the opt-in gate itself

    class _FakePolicy:
        def __init__(self, decisions):
            self.config = RebalanceBusySymbolReplaceExitTests._FakePolicyConfig()
            self.latest = {}
            self.selector = None
            self.last_exit_fractions = {}
            self._decisions = list(decisions)
            self.synced = []

        def sync_positions(self, positions, now):
            self.synced.append(positions)

        def decide(self, now, *, allow_entries, force_exit, operational=None):
            return self._decisions.pop(0) if self._decisions else None

    class _FakeLedger:
        def __init__(self, position):
            self._position = position

        def positions(self):
            return {"AAPL": self._position}

        def unresolved(self):
            return []

        def intents(self):
            return []

        def prior_rth_closes(self):
            return {}

    def strategy_and_policy(self, *, exit_replace_enabled=True):
        from native_strategy import AdaptiveStrategy

        class FakeOrderFactory:
            def __init__(self):
                self.calls = []

            def limit(self, instrument_id, side, quantity, price, *, time_in_force, client_order_id, tags):
                self.calls.append({"side": side, "quantity": str(quantity), "price": str(price),
                                   "tags": list(tags), "client_order_id": str(client_order_id)})
                return self.calls[-1]

        class FakeStrategy(AdaptiveStrategy):
            @property
            def order_factory(self):
                return self._fake_order_factory

        decisions = [
            _FakeDecision(targets={}, exits={"AAPL": "trailing_stop"}),
            _FakeDecision(targets={}, exits={"AAPL": "trailing_stop"}),
        ]
        policy = self._FakePolicy(decisions)
        policy.config.exit_replace_enabled = exit_replace_enabled
        position = _FakePosition("AAPL", D("5"), D("100.00"))
        ledger = self._FakeLedger(position)
        strategy = FakeStrategy(policy, ledger, "fixture")
        strategy._fake_order_factory = FakeOrderFactory()
        strategy.submitted, strategy.cancelled = [], []
        strategy.submit_order = strategy.submitted.append
        strategy.cancel_order = lambda cid: strategy.cancelled.append(str(cid))
        strategy.started = True
        strategy.enabled = False  # exits do not require entries to be enabled
        return strategy, policy

    def test_second_tick_with_moved_quote_replaces_via_the_busy_branch(self):
        strategy, policy = self.strategy_and_policy()

        class Q:
            def __init__(self, bid, ask, timestamp):
                self.bid, self.ask, self.timestamp = bid, ask, timestamp

        policy.latest["AAPL"] = Q(100.00, 100.02, 1000.0)
        decision1 = strategy.rebalance(1000.0)
        self.assertIsNotNone(decision1)
        self.assertEqual(len(strategy.submitted), 1)
        self.assertEqual(len(strategy.cancelled), 0)
        self.assertEqual(len(strategy.pending), 1)
        first_client_id = next(iter(strategy.pending))
        self.assertEqual(strategy.pending[first_client_id]["price_rule"], "trailing")

        # Tick 2: same "trailing_stop" reason (price_rule unchanged), but
        # the quote (and therefore the recomputed limit price) has moved --
        # rebalance() finds AAPL already busy (the tick-1 resting order is
        # in self.pending) and must call replace_exit, not silently skip.
        policy.latest["AAPL"] = Q(100.50, 100.52, 1000.5)
        decision2 = strategy.rebalance(1000.5)
        self.assertIsNotNone(decision2)
        self.assertEqual(strategy.cancelled, [first_client_id])
        self.assertTrue(strategy.pending[first_client_id]["cancel_requested"])
        self.assertIn("replace_with", strategy.pending[first_client_id])
        # Only one order was ever actually submit_order()'d for real (the
        # tick-1 entry); the replacement is only submitted once
        # on_order_canceled fires, which this fake cancel_order does not do
        # synchronously -- covered separately by
        # ReplaceExitTests.test_synchronous_cancel_ack_does_not_raise_keyerror.
        self.assertEqual(len(strategy.submitted), 1)

    def test_disabled_flag_keeps_pre_g_f_skip_behavior_in_the_busy_branch(self):
        """Round 8: cancel-then-replace is opt-in on
        PolicyConfig.exit_replace_enabled (default False). With it off,
        rebalance()'s busy-symbol branch must keep the pre-G-f behavior:
        the resting order from tick 1 is simply left exactly as-is on
        tick 2 -- no cancel_order call, no "replace_with" staged, no
        change to strategy.pending's entry at all -- even though the
        quote has moved exactly as in the enabled-state test above."""
        strategy, policy = self.strategy_and_policy(exit_replace_enabled=False)

        class Q:
            def __init__(self, bid, ask, timestamp):
                self.bid, self.ask, self.timestamp = bid, ask, timestamp

        policy.latest["AAPL"] = Q(100.00, 100.02, 1000.0)
        decision1 = strategy.rebalance(1000.0)
        self.assertIsNotNone(decision1)
        self.assertEqual(len(strategy.submitted), 1)
        first_client_id = next(iter(strategy.pending))
        pending_before = dict(strategy.pending[first_client_id])

        policy.latest["AAPL"] = Q(100.50, 100.52, 1000.5)
        decision2 = strategy.rebalance(1000.5)
        self.assertIsNotNone(decision2)
        self.assertEqual(strategy.cancelled, [])  # replace_exit was never called
        self.assertEqual(strategy.pending[first_client_id], pending_before)
        self.assertNotIn("replace_with", strategy.pending[first_client_id])
        self.assertEqual(len(strategy.submitted), 1)  # still just the tick-1 order


@unittest.skipUnless(NATIVE, "requires pinned Nautilus 2.0.0rc5 runtime")
class GapStopFireOnceOnlyAfterSubmitTests(unittest.TestCase):
    """D2 (round 3): rebalance() must mark self._gap_stop_applied only
    once the gap_risk_stop exit action is actually accepted into the
    submit path (a direct submit_order(), or a replace_exit() that
    returns True), never merely because _gap_risk_stop_symbols returned
    the symbol as triggered. _gap_risk_stop_symbols itself is monkeypatched
    to force a trigger, isolating these tests to rebalance()'s own
    accept/reject-then-mark logic (the trigger's own freshness guard is
    covered by StaleQuoteGapRiskTests in test_adaptive_paper_sessions.py)."""

    class _FakePolicyConfig:
        quote_age_seconds = 3
        max_shares = 5
        exit_replace_max_attempts = 3
        exit_replace_tolerance_bps = 0
        exit_replace_min_interval_seconds = 0
        # _gap_risk_stop_symbols is monkeypatched by strategy() below, so
        # this value is never actually consulted, but kept truthful.
        gap_stop_enabled = True
        # Round 8: several tests below drive a gap_risk_stop action into
        # rebalance()'s busy-symbol branch (an already-resting order for
        # the same symbol) and exercise replace_exit from there -- keep
        # the opt-in gate on for this class so those tests keep testing
        # what they always tested; the gate itself is covered by
        # RebalanceBusySymbolReplaceExitTests.
        exit_replace_enabled = True

    class _FakePolicy:
        def __init__(self, decision):
            self.config = GapStopFireOnceOnlyAfterSubmitTests._FakePolicyConfig()
            self.latest = {}
            self.selector = None
            self.last_exit_fractions = {}
            self._decision = decision

        def sync_positions(self, positions, now):
            pass

        def decide(self, now, *, allow_entries, force_exit, operational=None):
            return self._decision

    class _FakeLedger:
        def __init__(self, position):
            self._position = position

        def positions(self):
            return {"AAPL": self._position}

        def unresolved(self):
            return []

        def intents(self):
            return []

        def prior_rth_closes(self):
            return {}

    class _Q:
        def __init__(self, bid, ask, timestamp):
            self.bid, self.ask, self.timestamp = bid, ask, timestamp

    def strategy(self, *, held_qty=D("5"), set_gap_bps=False, clock=lambda: 2000.0):
        from native_strategy import AdaptiveStrategy

        class FakeOrderFactory:
            def __init__(self):
                self.calls = []

            def limit(self, instrument_id, side, quantity, price, *, time_in_force, client_order_id, tags):
                self.calls.append({"side": side, "quantity": str(quantity), "tags": list(tags)})
                return self.calls[-1]

        class FakeStrategy(AdaptiveStrategy):
            @property
            def order_factory(self):
                return self._fake_order_factory

        # No held-vs-target delta beyond the gap stop itself: an empty
        # exits/targets decision means only the forced gap_risk_stop
        # action is in play this tick.
        decision = _FakeDecision(targets={}, exits={})
        policy = self._FakePolicy(decision)
        position = _FakePosition("AAPL", held_qty, D("100.00"))
        ledger = self._FakeLedger(position)
        # D2 (round 6): on_order_canceled now reads the ack-time clock
        # (self._clock()) rather than a frozen requested_now -- default to
        # the same 2000.0 every test in this class already uses for both
        # rebalance() and its quotes.
        strategy = FakeStrategy(policy, ledger, "fixture", clock=clock)
        strategy._fake_order_factory = FakeOrderFactory()
        strategy.submitted, strategy.cancelled = [], []
        strategy.submit_order = strategy.submitted.append
        strategy.cancel_order = lambda cid: strategy.cancelled.append(str(cid))
        strategy.started = True
        strategy.enabled = False

        def fake_gap_risk_stop_symbols(now, held):
            if set_gap_bps:
                strategy._gap_bps["AAPL"] = D("-123.45")
            return {"AAPL"}
        strategy._gap_risk_stop_symbols = fake_gap_risk_stop_symbols  # force-trigger
        return strategy

    def test_stale_quote_at_submit_time_leaves_the_stop_armed(self):
        strategy = self.strategy()
        # Quote is far too old by the time the submit-path freshness check
        # runs (rebalance()'s own per-action guard), even though the
        # (mocked) trigger already fired.
        strategy.policy.latest["AAPL"] = self._Q(100.0, 100.02, 1000.0)
        decision = strategy.rebalance(now=2000.0)
        self.assertIsNotNone(decision)
        self.assertEqual(strategy.submitted, [])
        self.assertEqual(strategy._gap_stop_applied, set())

    def test_refused_replace_leaves_the_stop_armed(self):
        strategy = self.strategy()
        # AAPL is already "busy" (a resting sell exists) and capped at
        # zero attempts, so replace_exit is guaranteed to refuse.
        strategy.pending["adp-fixture-0000001"] = {
            "symbol": "AAPL", "side": "sell", "created": 1000.0, "price_rule": "market"}
        strategy._exit_attempts["AAPL"] = strategy.policy.config.exit_replace_max_attempts
        strategy.policy.latest["AAPL"] = self._Q(100.0, 100.02, 2000.0)
        decision = strategy.rebalance(now=2000.0)
        self.assertIsNotNone(decision)
        self.assertEqual(strategy.cancelled, [])
        self.assertEqual(strategy._gap_stop_applied, set())  # refused: stays armed

    def test_accepted_submit_marks_fire_once(self):
        strategy = self.strategy()
        strategy.policy.latest["AAPL"] = self._Q(100.0, 100.02, 2000.0)
        decision = strategy.rebalance(now=2000.0)
        self.assertIsNotNone(decision)
        self.assertEqual(len(strategy.submitted), 1)
        self.assertEqual(strategy._gap_stop_applied, {"AAPL"})

    def test_accepted_replace_marks_fire_once_only_once_actually_submitted(self):
        """D1 (round 4): rebalance()'s busy-branch replace_exit() call only
        ever returns "cancel_requested" (never "submitted" itself) -- the
        gap stop must stay un-marked until the replacement order is
        actually submitted, asynchronously, once the cancel is
        acknowledged (here: a synchronous ack, simulated directly)."""
        strategy = self.strategy()
        strategy.pending["adp-fixture-0000001"] = {
            "symbol": "AAPL", "side": "sell", "created": 1000.0, "price_rule": "stop"}
        strategy.policy.latest["AAPL"] = self._Q(100.0, 100.02, 2000.0)  # price_rule for gap_risk_stop -> "market" != "stop"
        decision = strategy.rebalance(now=2000.0)
        self.assertIsNotNone(decision)
        self.assertEqual(strategy.cancelled, ["adp-fixture-0000001"])
        # Cancel requested, but nothing submitted yet -- must not be marked.
        self.assertEqual(strategy._gap_stop_applied, set())
        self.assertEqual(strategy.submitted, [])

        class Event:
            client_order_id = "adp-fixture-0000001"
        strategy.on_order_canceled(Event())  # simulates the broker's ack

        self.assertEqual(len(strategy.submitted), 1)
        self.assertEqual(strategy._gap_stop_applied, {"AAPL"})

    def test_fill_racing_a_staged_gap_replacement_keeps_fire_once(self):
        """D3 (round 8) regression: the exact bug -- _release_staged_
        replacement used to unconditionally clear gap-risk fire-once for
        any dropped gap_risk_stop replacement, including via
        on_order_filled. A genuine fill (the original resting order fills
        in full, or in part, WHILE a cancel-then-replace of it is staged
        -- e.g. the broker fills the old resting order just as its cancel
        request is in flight) must NOT clear fire-once: the stop already
        did its job (the position is filled away, fully or partially),
        and clearing fire-once would incorrectly re-arm the gap stop for
        the rest of the RTH session as if nothing had happened yet."""
        strategy = self.strategy()
        strategy.pending["adp-fixture-0000001"] = {
            "symbol": "AAPL", "side": "sell", "created": 1000.0, "price_rule": "stop"}
        strategy.policy.latest["AAPL"] = self._Q(100.0, 100.02, 2000.0)  # price_rule -> "market" != "stop"
        decision = strategy.rebalance(now=2000.0)
        self.assertIsNotNone(decision)
        # A cancel-then-replace is staged on the original resting order,
        # carrying the "gap_risk_stop" reason -- but fire-once is not yet
        # marked (the replacement has not been submitted).
        self.assertIn("replace_with", strategy.pending["adp-fixture-0000001"])
        self.assertEqual(strategy.pending["adp-fixture-0000001"]["replace_with"]["reason"], "gap_risk_stop")
        self.assertEqual(strategy._gap_stop_applied, set())

        # Manually mark fire-once as though an EARLIER tick's direct
        # submit already consumed it for this symbol (the realistic
        # precondition for this race: fire-once is only ever cleared for
        # an order that carries "gap_risk_stop", and the staged
        # replacement here does -- but the ORIGINAL resting order's own
        # `pending` entry does not carry a "reason" key at all in this
        # fixture, matching seed_resting_sell's shape elsewhere, so mark
        # it directly to set up the precondition this test exercises).
        strategy._gap_stop_applied.add("AAPL")

        # The original resting order fills (in full) WHILE the
        # cancel-then-replace is still staged on it -- races
        # on_order_canceled entirely.
        class FillEvent:
            client_order_id = "adp-fixture-0000001"
        strategy.on_order_filled(FillEvent())

        # Fire-once stays marked: the fill means the stop already did its
        # job. Before the D3 fix, on_order_filled -> _release_staged_
        # replacement -> _clear_gap_stop_for_dropped_replacement would
        # have wrongly cleared it here.
        self.assertEqual(strategy._gap_stop_applied, {"AAPL"})
        # The staged replacement itself is still dropped/released (the
        # busy flag and "replace_with" are cleared exactly as before --
        # only the gap-stop clearing is skipped for a fill).
        self.assertNotIn("AAPL", strategy._exit_replace_busy)
        self.assertIsNone(strategy.pending["adp-fixture-0000001"]["replace_with"])

    # -- D6 (round 4): a truncated (by max_shares) gap-stop submit must not
    #    mark fire-once, leaving the remainder protected --------------

    def test_direct_submit_truncated_by_max_shares_leaves_the_stop_armed(self):
        # max_shares=5 (this class's _FakePolicyConfig); held qty=10 means
        # the order factory receives only 5, truncating the sell.
        strategy = self.strategy(held_qty=D("10"))
        strategy.policy.latest["AAPL"] = self._Q(100.0, 100.02, 2000.0)
        decision = strategy.rebalance(now=2000.0)
        self.assertIsNotNone(decision)
        self.assertEqual(len(strategy.submitted), 1)
        self.assertEqual(strategy._fake_order_factory.calls[0]["quantity"], "5")  # truncated
        self.assertEqual(strategy._gap_stop_applied, set())  # remainder still unprotected -> stays armed

    def test_direct_submit_of_the_full_quantity_marks_fire_once(self):
        # held qty=5 == max_shares: the full quantity is submitted, no
        # truncation, so fire-once is correctly marked.
        strategy = self.strategy(held_qty=D("5"))
        strategy.policy.latest["AAPL"] = self._Q(100.0, 100.02, 2000.0)
        decision = strategy.rebalance(now=2000.0)
        self.assertIsNotNone(decision)
        self.assertEqual(len(strategy.submitted), 1)
        self.assertEqual(strategy._fake_order_factory.calls[0]["quantity"], "5")
        self.assertEqual(strategy._gap_stop_applied, {"AAPL"})

    def test_replacement_submit_truncated_by_max_shares_leaves_the_stop_armed(self):
        """The same D6 truncation guard applies to the cancel-then-replace
        path (_submit_replacement_exit), not just the direct submit."""
        strategy = self.strategy(held_qty=D("10"))
        strategy.pending["adp-fixture-0000001"] = {
            "symbol": "AAPL", "side": "sell", "created": 1000.0, "price_rule": "stop"}
        strategy.policy.latest["AAPL"] = self._Q(100.0, 100.02, 2000.0)
        strategy.rebalance(now=2000.0)  # cancel_requested via replace_exit
        self.assertEqual(strategy._gap_stop_applied, set())

        class Event:
            client_order_id = "adp-fixture-0000001"
        strategy.on_order_canceled(Event())  # submits the (truncated) replacement

        self.assertEqual(len(strategy.submitted), 1)
        self.assertEqual(strategy._fake_order_factory.calls[0]["quantity"], "5")
        self.assertEqual(strategy._gap_stop_applied, set())  # still unprotected remainder

    # -- D4 (round 4): gap_bps recorded in the decision event ------------

    def test_decision_event_includes_gap_bps(self):
        strategy = self.strategy(set_gap_bps=True)
        events = []
        strategy.event_sink = events.append
        strategy.policy.latest["AAPL"] = self._Q(100.0, 100.02, 2000.0)
        strategy.rebalance(now=2000.0)
        decision_events = [e for e in events if e["type"] == "decision"]
        self.assertEqual(len(decision_events), 1)
        self.assertEqual(decision_events[0]["gap_bps"]["AAPL"], "-123.45")


if __name__ == "__main__":
    unittest.main()
