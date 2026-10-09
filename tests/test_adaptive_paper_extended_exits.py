"""Synthetic exit decisions only; no engine, transport, credentials or broker."""
from dataclasses import replace
from decimal import Decimal
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch


SOURCE = Path(__file__).resolve().parents[1] / "blueprints/us-equities/adaptive-paper"
sys.path.insert(0, str(SOURCE))

import exits as X  # noqa: E402
from strategies_v1 import PolicyConfig  # noqa: E402
from strategies import AdaptivePolicy  # noqa: E402

NATIVE = importlib.util.find_spec("nautilus_trader") is not None


class ExtendedExitDecisionTests(unittest.TestCase):
    def config(self, **changes):
        return PolicyConfig(
            symbols=("SPY", "QQQ", "IWM", "DIA", "AAPL", "MSFT"),
            max_positions=6, **changes,
        )

    def context(self, **changes):
        fields = dict(
            now=1000.0, entered_at=950.0, pnl_bps=0.0, trail_bps=0.0,
            quote_fresh=True, risk_off=False, force_exit=False,
            force_exit_reason="trial_end", session="PRE", bid="100.00",
            ask="100.02", exit_side="sell",
        )
        fields.update(changes)
        return X.ExitContext(**fields)

    def assert_flagged_hold(self, decision, reason):
        self.assertEqual(decision.reason, reason)
        self.assertFalse(decision.submit)
        self.assertTrue(decision.flag_position)
        self.assertEqual(decision.fraction, 0.0)
        self.assertEqual(decision.price_rule, "hold")
        self.assertIsNone(decision.limit_price)

    def test_stale_extended_quote_holds_even_when_force_and_risk_rules_fire(self):
        for session in ("PRE", "POST", "OVERNIGHT"):
            with self.subTest(session=session):
                decision = X.DEFAULT_PLAN.evaluate(self.context(
                    session=session, quote_fresh=False, force_exit=True,
                    risk_off=True, pnl_bps=-100.0, trail_bps=-100.0,
                    now=2000.0, bid=None, ask=None,
                ), self.config())
                self.assert_flagged_hold(decision, "quote_stale")

    def test_stale_guard_cannot_be_removed_by_a_custom_rule_order(self):
        plan = X.ExitPlan(rules=(lambda *args: X.ExitDecision("custom_exit"),))
        decision = plan.evaluate(self.context(quote_fresh=False), self.config())
        self.assert_flagged_hold(decision, "quote_stale")

    def test_fresh_extended_long_exit_is_an_explicit_marketable_limit(self):
        for session in ("PRE", "POST"):
            with self.subTest(session=session):
                ctx = self.context(session=session, pnl_bps=-30.0)
                decision = X.DEFAULT_PLAN.evaluate(ctx, self.config())
                self.assertEqual(decision.reason, "stop_loss")
                self.assertEqual(decision.price_rule, "limit")
                self.assertEqual(decision.limit_price, "99.98")
                self.assertTrue(decision.submit)
                self.assertFalse(decision.flag_position)
                self.assertEqual(decision.fraction, 1.0)
                self.assertEqual(ctx.bid, "100.00")

    def test_unqualified_overnight_holds_fresh_quotes_for_every_exit_trigger(self):
        cases = (
            {}, {"force_exit": True}, {"risk_off": True},
            {"pnl_bps": -30.0}, {"pnl_bps": 50.0},
            {"trail_bps": -20.0}, {"now": 1100.0},
        )
        for fields in cases:
            with self.subTest(fields=fields):
                decision = X.DEFAULT_PLAN.evaluate(
                    self.context(session="OVERNIGHT", **fields), self.config())
                self.assert_flagged_hold(decision, "overnight_unqualified")

    def test_failed_classification_has_a_distinct_attention_reason(self):
        for quote_fresh in (False, True):
            with self.subTest(quote_fresh=quote_fresh):
                decision = X.DEFAULT_PLAN.evaluate(self.context(
                    session="CLASSIFICATION_FAILED", quote_fresh=quote_fresh,
                    force_exit=True, risk_off=True,
                ), self.config())
                self.assert_flagged_hold(decision, "session_classification_failed")

    def test_fresh_extended_short_cover_uses_ask_side_limit(self):
        decision = X.DEFAULT_PLAN.evaluate(
            self.context(pnl_bps=-30.0, exit_side="buy"), self.config())
        self.assertEqual(decision.limit_price, "100.04")
        self.assertEqual(decision.price_rule, "limit")
        self.assertTrue(decision.submit)
        self.assertFalse(decision.flag_position)

    def test_every_extended_rule_uses_a_limit_without_losing_its_reason(self):
        cases = (
            ({"force_exit": True}, "trial_end"),
            ({"risk_off": True}, "risk_off"),
            ({"pnl_bps": -30.0}, "stop_loss"),
            ({"pnl_bps": 50.0}, "take_profit"),
            ({"trail_bps": -20.0}, "trailing_stop"),
            ({"now": 1100.0}, "time_exit"),
        )
        for fields, reason in cases:
            with self.subTest(reason=reason):
                decision = X.DEFAULT_PLAN.evaluate(self.context(**fields), self.config())
                self.assertEqual(decision.reason, reason)
                self.assertEqual(decision.price_rule, "limit")
                self.assertEqual(decision.limit_price, "99.98")
                self.assertTrue(decision.submit)
                self.assertFalse(decision.flag_position)

    def test_partial_take_profit_fraction_survives_extended_limit_projection(self):
        decision = X.DEFAULT_PLAN.evaluate(self.context(pnl_bps=50.0),
                                           self.config(take_profit_fraction=0.5))
        self.assertEqual(decision.reason, "take_profit")
        self.assertEqual(decision.fraction, 0.5)
        self.assertEqual(decision.price_rule, "limit")

    def test_fresh_quote_with_no_trigger_creates_no_exit_decision(self):
        self.assertIsNone(X.DEFAULT_PLAN.evaluate(self.context(), self.config()))

    def test_closed_and_unknown_sessions_hold_instead_of_creating_orders(self):
        for session in ("CLOSED", "unknown"):
            with self.subTest(session=session):
                decision = X.DEFAULT_PLAN.evaluate(
                    self.context(session=session, force_exit=True), self.config())
                self.assert_flagged_hold(decision, "session_unavailable")

    def test_invalid_extended_quote_or_side_flags_a_hold(self):
        cases = (
            {"bid": None}, {"ask": None}, {"bid": "0"}, {"ask": "-1"},
            {"bid": "100.03"}, {"bid": "NaN"}, {"ask": "Infinity"},
            {"bid": "invalid"}, {"exit_side": "short"},
        )
        for fields in cases:
            with self.subTest(fields=fields):
                decision = X.DEFAULT_PLAN.evaluate(
                    self.context(force_exit=True, **fields), self.config())
                self.assert_flagged_hold(decision, "quote_invalid")

    def test_rth_default_preserves_stale_quote_reason_and_pricing_label(self):
        ctx = X.ExitContext(
            now=1000.0, entered_at=950.0, pnl_bps=-100.0, trail_bps=-100.0,
            quote_fresh=False, risk_off=False, force_exit=False,
            force_exit_reason="trial_end",
        )
        decision = X.DEFAULT_PLAN.evaluate(ctx, self.config())
        self.assertEqual(decision, X.ExitDecision("quote_stale", 1.0, "market"))
        self.assertTrue(decision.submit)
        self.assertFalse(decision.flag_position)
        self.assertIsNone(decision.limit_price)

    def test_rth_ordering_and_configured_fraction_are_unchanged(self):
        ctx = self.context(session="RTH", force_exit=True, risk_off=True,
                           quote_fresh=False)
        self.assertEqual(X.DEFAULT_PLAN.evaluate(ctx, self.config()),
                         X.ExitDecision("trial_end", 1.0, "market"))
        ctx = replace(ctx, force_exit=False, risk_off=False,
                      quote_fresh=True, pnl_bps=50.0)
        self.assertEqual(X.DEFAULT_PLAN.evaluate(ctx, self.config(take_profit_fraction=0.5)),
                         X.ExitDecision("take_profit", 0.5, "take_profit"))


class ExtendedPolicyCallerTests(unittest.TestCase):
    def policy(self, **changes):
        config = PolicyConfig(
            symbols=("SPY", "QQQ", "IWM", "DIA", "AAPL", "MSFT"),
            max_positions=6, **changes,
        )
        policy = AdaptivePolicy(config)
        policy.sync_positions({"AAPL": {"qty": "2", "avg_entry_price": "100"}}, 950.0)
        policy.exit_session = "PRE"
        return policy

    def test_flag_preserves_held_target_instead_of_portfolio_rotation(self):
        policy = self.policy()
        policy.observe("AAPL", 100.0, 100.02, 900.0)
        decision = policy.decide(1000.0, allow_entries=True, force_exit=True)
        self.assertEqual(decision.targets["AAPL"], Decimal("2"))
        self.assertNotIn("AAPL", decision.exits)
        self.assertNotIn("AAPL", policy.last_exit_fractions)
        self.assertTrue(policy.last_exit_decisions["AAPL"].flag_position)
        self.assertFalse(policy.last_exit_decisions["AAPL"].submit)
        self.assertNotIn("last_exit_decisions", decision.__dataclass_fields__)

    def test_fresh_overnight_keeps_the_holding_even_during_forced_cleanup(self):
        policy = self.policy()
        policy.exit_session = "OVERNIGHT"
        policy.observe("AAPL", 100.0, 100.02, 1000.0)
        decision = policy.decide(1000.0, allow_entries=True, force_exit=True)
        self.assertEqual(decision.targets["AAPL"], Decimal("2"))
        self.assertNotIn("AAPL", decision.exits)
        self.assertNotIn("AAPL", policy.last_exit_fractions)
        flagged = policy.last_exit_decisions["AAPL"]
        self.assertEqual(flagged.reason, "overnight_unqualified")
        self.assertFalse(flagged.submit)
        self.assertTrue(flagged.flag_position)

    def test_future_quote_flags_without_advancing_the_holding_watermark(self):
        policy = self.policy()
        policy.observe("AAPL", 101.0, 101.02, 1001.0)
        original_high = policy.holdings["AAPL"].high_bid
        decision = policy.decide(1000.0, force_exit=True)
        self.assertEqual(policy.last_exit_decisions["AAPL"].reason, "quote_stale")
        self.assertEqual(policy.holdings["AAPL"].high_bid, original_high)
        self.assertEqual(decision.targets["AAPL"], Decimal("2"))

    def test_fresh_partial_exit_preserves_fraction_and_rich_limit_decision(self):
        policy = self.policy(take_profit_fraction=0.5)
        policy.observe("AAPL", 100.5, 100.52, 1000.0)
        decision = policy.decide(1000.0, allow_entries=False)
        self.assertEqual(decision.exits["AAPL"], "take_profit")
        self.assertEqual(policy.last_exit_fractions["AAPL"], 0.5)
        self.assertEqual(policy.last_exit_decisions["AAPL"].limit_price, "100.48")
        self.assertTrue(policy.last_exit_decisions["AAPL"].submit)

    def test_a_new_decision_replaces_old_attention_flags(self):
        policy = self.policy()
        policy.decide(1000.0, force_exit=True)
        self.assertTrue(policy.last_exit_decisions["AAPL"].flag_position)
        policy.observe("AAPL", 100.0, 100.02, 1001.0)
        policy.decide(1001.0, force_exit=True)
        self.assertFalse(policy.last_exit_decisions["AAPL"].flag_position)


@unittest.skipUnless(NATIVE, "requires installed native engine; all broker operations are fakes")
class NativeExtendedExitCallerTests(unittest.TestCase):
    def strategy(self, *, session="PRE"):
        # Reuse the existing fake-native strategy factory, not an order adapter.
        import test_adaptive_paper_exits as legacy

        helper = legacy.ReplaceExitTests()
        now = [1000.0]
        strategy = helper.strategy(clock=lambda: now[0])
        strategy.policy = AdaptivePolicy(PolicyConfig(
            symbols=("SPY", "QQQ", "IWM", "DIA", "AAPL", "MSFT"),
            max_positions=6, exit_replace_enabled=True,
        ))
        strategy._exit_session_at = lambda at: session
        # The synthetic resting fixture uses sequence 1; subsequent submits
        # must use a fresh identity, as the real journal-seeded sequence does.
        strategy.sequence = 1
        strategy.positions = lambda: {"AAPL": {"qty": "2", "avg_entry_price": "100"}}
        strategy.ledger.unresolved = lambda: []
        strategy._gap_risk_stop_symbols = lambda at, held: set()
        strategy._corporate_action_guard_symbols = lambda *args: (set(), set())
        strategy.started, strategy.enabled = True, False
        events = []
        strategy.event_sink = events.append
        return strategy, helper, now, events

    def test_existing_extended_transport_automatically_selects_session_context(self):
        strategy, helper, now, events = self.strategy()
        with patch("native_strategy.session_at", return_value=SimpleNamespace(kind="PRE")) as classify:
            actual = type(strategy)(strategy.policy, strategy.ledger, "fixture",
                                    transport=SimpleNamespace(extended_hours_allowed=True))
            self.assertEqual(actual._exit_session(now[0]), "PRE")
            classify.assert_called_once()

    def test_default_transport_never_classifies_even_on_a_2028_clock(self):
        strategy, helper, now, events = self.strategy()
        with patch("native_strategy.session_at", side_effect=AssertionError("calendar consulted")):
            actual = type(strategy)(strategy.policy, strategy.ledger, "fixture",
                                    transport=SimpleNamespace(extended_hours_allowed=False))
            self.assertEqual(actual._exit_session(1832677200.0), "RTH")

    def test_stale_extended_rebalance_flags_without_submit_or_replacement(self):
        strategy, helper, now, events = self.strategy()
        strategy.policy.observe("AAPL", 100.0, 100.02, 900.0)
        helper.seed_resting_sell(strategy)
        decision = strategy.rebalance(now=now[0], force_exit=True)
        self.assertEqual(decision.targets["AAPL"], Decimal("2"))
        self.assertEqual(strategy.submitted, [])
        self.assertEqual(strategy.cancelled, [])
        self.assertTrue(any(e["type"] == "exit_attention" and e["reason"] == "quote_stale"
                            for e in events))

    def test_forced_stale_exit_cannot_be_a_successful_overnight_hold(self):
        from datetime import datetime, timezone
        from zoneinfo import ZoneInfo
        import runner

        strategy, helper, now, events = self.strategy(session="POST")
        strategy.policy.observe("AAPL", 100.0, 100.02, 900.0)
        strategy.rebalance(now=now[0], force_exit=True)
        self.assertEqual(strategy.submitted, [])
        self.assertTrue(any(e["type"] == "exit_attention" and e["reason"] == "quote_stale"
                            for e in events))
        boundary = datetime(2026, 3, 10, 18, tzinfo=ZoneInfo("America/New_York")) \
            .astimezone(timezone.utc).timestamp()
        reconciliation = {"positions": 1, "open_orders": 0}
        outcome = {"reconciliation": reconciliation, "adapter_errors": [],
                   "accounting": {"halted_reason": None}, "flat": False,
                   "events": events,
                   "corporate_action_guard": runner._final_corporate_action_guard_summary(
                       strategy, {"AAPL"}, boundary)}
        outcome["status"] = runner._run_native_status(
            reconciliation, [], 0, outcome,
            {"overnight_holds": True, "extended_hours": True}, boundary)
        self.assertEqual(outcome["status"], "needs_attention")
        self.assertEqual(runner.trial_phase_and_exit_code(outcome), ("needs_attention", 3))

    def test_a_fresh_disposition_clears_only_that_holdings_exit_attention(self):
        import runner

        strategy, helper, now, events = self.strategy(session="POST")
        strategy.policy.observe("AAPL", 100.0, 100.02, 900.0)
        strategy.rebalance(now=now[0], force_exit=True)
        held = runner._final_corporate_action_guard_summary(strategy, {"AAPL"}, now[0])
        self.assertIn("AAPL", held["pending_needs_attention_held"])
        strategy.policy.observe("AAPL", 100.0, 100.02, now[0])
        strategy.rebalance(now=now[0], force_exit=True)
        cleared = runner._final_corporate_action_guard_summary(strategy, {"AAPL"}, now[0])
        self.assertNotIn("AAPL", cleared["pending_needs_attention_held"])

    def test_fresh_extended_rebalance_reuses_native_limit_order_factory(self):
        strategy, helper, now, events = self.strategy()
        strategy.policy.observe("AAPL", 100.0, 100.02, now[0])
        strategy.rebalance(now=now[0], force_exit=True)
        self.assertEqual(len(strategy.submitted), 1)
        self.assertEqual(strategy._fake_order_factory.calls[0]["price"], "99.98")
        pending = next(iter(strategy.pending.values()))
        self.assertEqual(pending["price_rule"], "limit")
        self.assertFalse(any(e["type"] == "exit_attention" for e in events))

    def test_closed_session_rebalance_flags_even_with_a_fresh_quote(self):
        for session in ("CLOSED", "unknown"):
            with self.subTest(session=session):
                strategy, helper, now, events = self.strategy(session=session)
                strategy.policy.observe("AAPL", 100.0, 100.02, now[0])
                strategy.rebalance(now=now[0], force_exit=True)
                self.assertEqual(strategy.submitted, [])
                self.assertTrue(any(e["type"] == "exit_attention" and e["reason"] == "session_unavailable"
                                    for e in events))

    def test_fresh_overnight_rebalance_flags_without_submit_or_replacement(self):
        strategy, helper, now, events = self.strategy(session="OVERNIGHT")
        strategy.policy.observe("AAPL", 100.0, 100.02, now[0])
        helper.seed_resting_sell(strategy)
        decision = strategy.rebalance(now=now[0], force_exit=True)
        self.assertEqual(decision.targets["AAPL"], Decimal("2"))
        self.assertEqual(strategy.submitted, [])
        self.assertEqual(strategy.cancelled, [])
        self.assertTrue(any(e["type"] == "exit_attention" and e["reason"] == "overnight_unqualified"
                            for e in events))

    def test_failed_session_classification_flags_rebalance(self):
        strategy, helper, now, events = self.strategy()
        def unavailable(at):
            raise ValueError("synthetic calendar unavailable")
        strategy._exit_session_at = unavailable
        strategy.policy.observe("AAPL", 100.0, 100.02, now[0])
        strategy.rebalance(now=now[0], force_exit=True)
        self.assertEqual(strategy.submitted, [])
        self.assertTrue(any(e["type"] == "exit_attention" and e["reason"] == "session_classification_failed"
                            for e in events))

    def test_cancel_ack_crossing_into_closed_session_submits_no_replacement(self):
        strategy, helper, now, events = self.strategy()
        strategy._exit_session_at = lambda at: "PRE" if at < 1001.0 else "CLOSED"
        strategy.policy.observe("AAPL", 100.0, 100.02, now[0])
        helper.seed_resting_sell(strategy)
        self.assertEqual(strategy.replace_exit("AAPL", now[0], Decimal("2"), "stop_loss"),
                         "cancel_requested")
        now[0] = 1001.0
        strategy.policy.observe("AAPL", 100.0, 100.02, now[0])
        strategy.on_order_canceled(SimpleNamespace(client_order_id="adp-fixture-0000001"))
        self.assertEqual(strategy.submitted, [])
        self.assertNotIn("AAPL", strategy._exit_replace_busy)
        self.assertTrue(any(e["type"] == "exit_attention" and e["reason"] == "session_unavailable"
                            for e in events))

    def test_cancel_ack_with_newly_stale_quote_flags_no_replacement(self):
        strategy, helper, now, events = self.strategy()
        strategy.policy.observe("AAPL", 100.0, 100.02, now[0])
        helper.seed_resting_sell(strategy)
        strategy.replace_exit("AAPL", now[0], Decimal("2"), "stop_loss")
        now[0] += strategy.policy.config.quote_age_seconds + 1
        strategy.on_order_canceled(SimpleNamespace(client_order_id="adp-fixture-0000001"))
        self.assertEqual(strategy.submitted, [])
        self.assertTrue(any(e["type"] == "exit_attention" and e["reason"] == "quote_stale"
                            for e in events))

    def test_failed_session_classification_at_ack_flags_without_callback_fault(self):
        strategy, helper, now, events = self.strategy()
        def classify(at):
            if at >= 1001.0:
                raise ValueError("synthetic calendar unavailable")
            return "PRE"
        strategy._exit_session_at = classify
        strategy.policy.observe("AAPL", 100.0, 100.02, now[0])
        helper.seed_resting_sell(strategy)
        strategy.replace_exit("AAPL", now[0], Decimal("2"), "stop_loss")
        now[0] = 1001.0
        strategy.policy.observe("AAPL", 100.0, 100.02, now[0])
        strategy.on_order_canceled(SimpleNamespace(client_order_id="adp-fixture-0000001"))
        self.assertEqual(strategy.submitted, [])
        self.assertFalse(strategy.faulted)
        self.assertTrue(any(e["type"] == "exit_attention" and e["reason"] == "session_classification_failed"
                            for e in events))

    def test_stale_rth_ack_cannot_be_an_honest_hold_without_another_tick(self):
        import runner

        strategy, helper, now, events = self.strategy(session="RTH")
        strategy.policy.observe("AAPL", 100.0, 100.02, now[0])
        helper.seed_resting_sell(strategy)
        self.assertEqual(strategy.replace_exit("AAPL", now[0], Decimal("2"), "stop_loss"),
                         "cancel_requested")
        now[0] += strategy.policy.config.quote_age_seconds + 1
        strategy.on_order_canceled(SimpleNamespace(client_order_id="adp-fixture-0000001"))
        self.assertEqual(strategy.submitted, [])
        summary = runner._final_corporate_action_guard_summary(strategy, {"AAPL"}, now[0])
        self.assertIn("AAPL", summary["pending_needs_attention_held"])
        self.assertTrue(any(e["type"] == "exit_attention" and e["reason"] == "quote_stale"
                            for e in events))

    def test_pre_to_rth_ack_uses_rth_rule_without_an_unchanged_price_cancel(self):
        strategy, helper, now, events = self.strategy()
        strategy._exit_session_at = lambda at: "PRE" if at < 1001.0 else "RTH"
        strategy.policy.observe("AAPL", 100.0, 100.02, now[0])
        helper.seed_resting_sell(strategy)
        strategy.replace_exit("AAPL", now[0], Decimal("2"), "trailing_stop")
        now[0] = 1001.0
        strategy.policy.observe("AAPL", 100.0, 100.02, now[0])
        strategy.on_order_canceled(SimpleNamespace(client_order_id="adp-fixture-0000001"))
        self.assertEqual(len(strategy.submitted), 1)
        self.assertEqual(next(iter(strategy.pending.values()))["price_rule"], "trailing")
        cancels_before = list(strategy.cancelled)
        self.assertEqual(strategy.replace_exit("AAPL", now[0], Decimal("2"), "trailing_stop"),
                         "noop")
        self.assertEqual(strategy.cancelled, cancels_before)


if __name__ == "__main__":
    unittest.main()
