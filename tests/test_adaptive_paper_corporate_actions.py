"""Synthetic (SYN) tests for the trading-lane audit gap #8 interim control:
corporate_actions.py's pure guard/monitor logic, and its wiring into
native_strategy.AdaptiveStrategy.rebalance(). No credentials, sockets, or
broker execution; every source is a fake, matching every other
tests/test_adaptive_paper_*.py file in this directory. The real
alpaca-py-backed `corporate_actions.AlpacaCorporateActionsSource` is not
exercised here (see corporate_actions.py's module docstring for how its
field mapping was verified against the installed alpaca-py==0.44.0
package instead).
"""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal as D
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "blueprints/us-equities/adaptive-paper"
sys.path.insert(0, str(SOURCE))

import corporate_actions as CA  # noqa: E402 (path inserted above)
import sessions  # noqa: E402

NATIVE = importlib.util.find_spec("nautilus_trader") is not None
if NATIVE:
    from nautilus_trader.model import OrderSide  # noqa: E402

TODAY = date(2026, 9, 24)
NEXT_SESSION = date(2026, 9, 25)
FAR_FUTURE = date(2026, 12, 1)


def action(symbol, action_type, action_date, source_id=""):
    return CA.ActionRecord(symbol=symbol, action_type=action_type, action_date=action_date,
                           source_id=source_id)


class ActionRecordTests(unittest.TestCase):
    def test_unknown_action_type_rejected(self):
        with self.assertRaises(ValueError):
            CA.ActionRecord(symbol="AAPL", action_type="bogus", action_date=TODAY)

    def test_every_documented_action_type_accepted(self):
        for action_type in ("forward_split", "reverse_split", "cash_dividend", "stock_dividend",
                            "spin_off", "merger", "name_change", "other"):
            action("AAPL", action_type, TODAY)  # must not raise


class EvaluateGuardTests(unittest.TestCase):
    """Covers each action type, entry blocking, pre-close flattening, the
    fail-closed path, and the absence of any effect on symbols without
    actions -- run against corporate_actions.evaluate_guard directly."""

    def evaluate(self, held, candidates, results):
        return CA.evaluate_guard(today=TODAY, next_session_date=NEXT_SESSION,
                                 held_symbols=held, candidate_symbols=candidates,
                                 lookup_results=results)

    def test_each_action_type_on_a_held_symbol_blocks_and_flattens(self):
        for action_type in ("forward_split", "reverse_split", "cash_dividend", "stock_dividend",
                            "spin_off", "merger", "name_change", "other"):
            with self.subTest(action_type=action_type):
                decisions = self.evaluate({"AAPL"}, set(), {"AAPL": [action("AAPL", action_type, TODAY)]})
                d = decisions["AAPL"]
                self.assertTrue(d.block_entry)
                self.assertTrue(d.must_flatten)
                self.assertFalse(d.needs_attention)
                self.assertEqual(d.reason, f"corporate_action_{action_type}")
                self.assertEqual(d.action_type, action_type)
                self.assertEqual(d.action_date, TODAY)

    def test_action_on_next_session_date_also_qualifies(self):
        decisions = self.evaluate({"AAPL"}, set(), {"AAPL": [action("AAPL", "reverse_split", NEXT_SESSION)]})
        self.assertTrue(decisions["AAPL"].block_entry)
        self.assertTrue(decisions["AAPL"].must_flatten)

    def test_action_outside_the_hold_horizon_has_no_effect(self):
        decisions = self.evaluate({"AAPL"}, set(), {"AAPL": [action("AAPL", "cash_dividend", FAR_FUTURE)]})
        d = decisions["AAPL"]
        self.assertFalse(d.block_entry)
        self.assertFalse(d.must_flatten)
        self.assertFalse(d.needs_attention)
        self.assertIsNone(d.reason)

    def test_symbol_with_no_recorded_actions_at_all_has_no_effect(self):
        decisions = self.evaluate({"AAPL"}, {"MSFT"}, {"AAPL": [], "MSFT": []})
        self.assertFalse(decisions["AAPL"].block_entry)
        self.assertFalse(decisions["AAPL"].must_flatten)
        self.assertFalse(decisions["MSFT"].block_entry)

    def test_candidate_not_currently_held_is_blocked_but_never_flattened(self):
        decisions = self.evaluate(set(), {"MSFT"}, {"MSFT": [action("MSFT", "spin_off", TODAY)]})
        d = decisions["MSFT"]
        self.assertTrue(d.block_entry)
        self.assertFalse(d.must_flatten)

    def test_lookup_failed_fails_closed_blocking_entry_without_forcing_flatten(self):
        decisions = self.evaluate({"AAPL"}, {"MSFT"}, {"AAPL": CA.LOOKUP_FAILED, "MSFT": CA.LOOKUP_FAILED})
        for symbol in ("AAPL", "MSFT"):
            d = decisions[symbol]
            self.assertTrue(d.block_entry)
            self.assertTrue(d.needs_attention)
            self.assertFalse(d.must_flatten)
            self.assertEqual(d.reason, "corporate_action_lookup_failed")

    def test_lookup_ambiguous_fails_closed_the_same_way(self):
        decisions = self.evaluate({"AAPL"}, set(), {"AAPL": CA.LOOKUP_AMBIGUOUS})
        d = decisions["AAPL"]
        self.assertTrue(d.block_entry)
        self.assertTrue(d.needs_attention)
        self.assertEqual(d.reason, "corporate_action_lookup_ambiguous")

    def test_symbol_missing_from_results_entirely_fails_closed(self):
        decisions = self.evaluate({"AAPL"}, set(), {})
        d = decisions["AAPL"]
        self.assertTrue(d.block_entry)
        self.assertTrue(d.needs_attention)
        self.assertEqual(d.reason, "corporate_action_lookup_failed")

    def test_earliest_qualifying_action_governs_when_several_are_recorded(self):
        decisions = self.evaluate({"AAPL"}, set(), {"AAPL": [
            action("AAPL", "cash_dividend", NEXT_SESSION), action("AAPL", "reverse_split", TODAY)]})
        d = decisions["AAPL"]
        self.assertEqual(d.action_type, "reverse_split")
        self.assertEqual(d.action_date, TODAY)

    def test_only_relevant_symbols_are_decided(self):
        decisions = self.evaluate({"AAPL"}, {"MSFT"}, {"AAPL": [], "MSFT": [], "IGNORED": []})
        self.assertEqual(set(decisions), {"AAPL", "MSFT"})


class CorporateActionMonitorTests(unittest.TestCase):
    class FakeSource:
        def __init__(self, result=None, error=None):
            self.result = result or {}
            self.error = error
            self.calls = []

        def fetch(self, symbols, start, end):
            self.calls.append((tuple(symbols), start, end))
            if self.error is not None:
                raise self.error
            return {s: self.result.get(s, []) for s in symbols}

    def test_evaluate_before_any_refresh_fails_closed(self):
        monitor = CA.CorporateActionMonitor(self.FakeSource(), clock=lambda: 1000.0)
        decisions = monitor.evaluate(today=TODAY, next_session_date=NEXT_SESSION,
                                     held_symbols={"AAPL"}, candidate_symbols=set(), now=1000.0)
        self.assertTrue(decisions["AAPL"].needs_attention)
        self.assertTrue(decisions["AAPL"].block_entry)

    def test_successful_refresh_feeds_evaluate(self):
        source = self.FakeSource(result={"AAPL": [action("AAPL", "forward_split", TODAY)]})
        monitor = CA.CorporateActionMonitor(source, clock=lambda: 1000.0)
        monitor.refresh({"AAPL"}, start=TODAY, end=NEXT_SESSION, now=1000.0)
        decisions = monitor.evaluate(today=TODAY, next_session_date=NEXT_SESSION,
                                     held_symbols={"AAPL"}, candidate_symbols=set(), now=1000.0)
        self.assertEqual(decisions["AAPL"].reason, "corporate_action_forward_split")
        self.assertFalse(decisions["AAPL"].needs_attention)

    def test_lookup_error_fails_closed_for_every_requested_symbol(self):
        source = self.FakeSource(error=CA.CorporateActionLookupError("boom"))
        monitor = CA.CorporateActionMonitor(source, clock=lambda: 1000.0)
        monitor.refresh({"AAPL", "MSFT"}, start=TODAY, end=NEXT_SESSION, now=1000.0)
        decisions = monitor.evaluate(today=TODAY, next_session_date=NEXT_SESSION,
                                     held_symbols={"AAPL"}, candidate_symbols={"MSFT"}, now=1000.0)
        self.assertTrue(decisions["AAPL"].needs_attention)
        self.assertTrue(decisions["MSFT"].needs_attention)

    def test_unexpected_exception_from_source_also_fails_closed(self):
        source = self.FakeSource(error=RuntimeError("unexpected"))
        monitor = CA.CorporateActionMonitor(source, clock=lambda: 1000.0)
        monitor.refresh({"AAPL"}, start=TODAY, end=NEXT_SESSION, now=1000.0)
        decisions = monitor.evaluate(today=TODAY, next_session_date=NEXT_SESSION,
                                     held_symbols={"AAPL"}, candidate_symbols=set(), now=1000.0)
        self.assertTrue(decisions["AAPL"].needs_attention)

    def test_stale_result_past_max_age_fails_closed_even_after_a_success(self):
        source = self.FakeSource(result={"AAPL": []})
        monitor = CA.CorporateActionMonitor(source, refresh_seconds=1, max_age_seconds=100, clock=lambda: 1000.0)
        monitor.refresh({"AAPL"}, start=TODAY, end=NEXT_SESSION, now=1000.0)
        fresh = monitor.evaluate(today=TODAY, next_session_date=NEXT_SESSION,
                                 held_symbols={"AAPL"}, candidate_symbols=set(), now=1050.0)
        self.assertFalse(fresh["AAPL"].needs_attention)
        stale = monitor.evaluate(today=TODAY, next_session_date=NEXT_SESSION,
                                 held_symbols={"AAPL"}, candidate_symbols=set(), now=1200.0)
        self.assertTrue(stale["AAPL"].needs_attention)

    def test_refresh_is_throttled_within_refresh_seconds_for_the_same_symbols(self):
        source = self.FakeSource(result={"AAPL": []})
        monitor = CA.CorporateActionMonitor(source, refresh_seconds=900, clock=lambda: 1000.0)
        monitor.refresh({"AAPL"}, start=TODAY, end=NEXT_SESSION, now=1000.0)
        monitor.refresh({"AAPL"}, start=TODAY, end=NEXT_SESSION, now=1001.0)
        self.assertEqual(len(source.calls), 1)

    def test_refresh_widens_the_fetch_when_a_new_symbol_appears(self):
        source = self.FakeSource(result={"AAPL": [], "MSFT": []})
        monitor = CA.CorporateActionMonitor(source, refresh_seconds=900, clock=lambda: 1000.0)
        monitor.refresh({"AAPL"}, start=TODAY, end=NEXT_SESSION, now=1000.0)
        monitor.refresh({"AAPL", "MSFT"}, start=TODAY, end=NEXT_SESSION, now=1001.0)
        self.assertEqual(len(source.calls), 2)


@unittest.skipUnless(NATIVE, "requires pinned Nautilus 2.0.0rc5 runtime")
class RebalanceCorporateActionGuardTests(unittest.TestCase):
    """Deliverable: native_strategy.AdaptiveStrategy.rebalance() consults
    the injected corporate-action guard -- entry blocking, pre-close
    flattening, precedence over gap_risk_stop, and no effect when the guard
    is absent or reports nothing relevant. Same FakeStrategy construction
    pattern as tests/test_adaptive_paper_exits.py's ReplaceExitTests and
    tests/test_adaptive_paper_runner.py's FakeStrategy."""

    class _FakeQuote:
        def __init__(self, bid, ask, timestamp):
            self.bid, self.ask, self.timestamp = bid, ask, timestamp

    class _FakePolicyConfig:
        def __init__(self, symbols=("AAPL", "MSFT"), quote_age_seconds=3, max_shares=5,
                    gap_stop_enabled=False, exit_replace_enabled=False):
            self.symbols = symbols
            self.quote_age_seconds = quote_age_seconds
            self.max_shares = max_shares
            self.gap_stop_enabled = gap_stop_enabled
            self.exit_replace_enabled = exit_replace_enabled

    @dataclass
    class _FakePosition:
        symbol: str
        qty: D
        average_cost: float = 100.0

    class _FakeDecision:
        def __init__(self, targets, exits=None, regime="trend", effective_leverage=1.0, signals=()):
            self.targets, self.exits = targets, exits or {}
            self.regime, self.effective_leverage, self.signals = regime, effective_leverage, signals

    class _FakePolicy:
        def __init__(self, config, decision):
            self.latest = {}
            self.config = config
            self.selector = None
            self.last_exit_fractions = {}
            self._decision = decision

        def sync_positions(self, positions, now):
            pass

        def decide(self, now, *, allow_entries, force_exit, operational=None):
            return self._decision

    class _FakeLedger:
        def __init__(self, positions=None):
            self._positions = positions or {}

        def intents(self):
            return []

        def prior_rth_closes(self):
            return {}

        def unresolved(self):
            return []

        def positions(self):
            return self._positions

    class _FakeGuard:
        """Scripted guard: returns exactly the decisions it was constructed
        with (keyed by symbol), regardless of the arguments rebalance()
        passes -- the args themselves are recorded for assertion."""

        def __init__(self, decisions):
            self.decisions = decisions
            self.calls = []

        def evaluate(self, *, today, next_session_date, held_symbols, candidate_symbols, now):
            self.calls.append({"today": today, "next_session_date": next_session_date,
                               "held_symbols": set(held_symbols), "candidate_symbols": set(candidate_symbols)})
            return self.decisions

    def strategy(self, *, held=None, targets=None, guard_decisions=None, clock=lambda: 1790256600.0):
        # 2026-09-24 09:30:00 America/New_York in epoch seconds (RTH open) --
        # picked so session_at()/next_trading_day() both resolve without a
        # ValueError under the frozen 2026 calendar (verified: session_date
        # 2026-09-24, next_trading_day 2026-09-25 -- this file's module-level
        # TODAY/NEXT_SESSION constants).
        from native_strategy import AdaptiveStrategy

        class FakeOrderFactory:
            def __init__(self):
                self.calls = []

            def limit(self, instrument_id, side, quantity, price, *, time_in_force, client_order_id, tags):
                self.calls.append({"instrument_id": str(instrument_id), "side": side,
                                   "quantity": str(quantity), "price": str(price), "tags": list(tags)})
                return self.calls[-1]

        class FakeStrategy(AdaptiveStrategy):
            @property
            def order_factory(self):
                return self._fake_order_factory

        held = held or {}
        positions = {s: self._FakePosition(symbol=s, qty=D(str(q))) for s, q in held.items()}
        config = self._FakePolicyConfig()
        decision = self._FakeDecision(targets=targets or {})
        policy = self._FakePolicy(config, decision)
        guard = self._FakeGuard(guard_decisions) if guard_decisions is not None else None
        strat = FakeStrategy(policy, self._FakeLedger(positions), "fixture", clock=clock,
                             corporate_action_guard=guard)
        strat._fake_order_factory = FakeOrderFactory()
        strat.submitted, strat.events = [], []
        strat.submit_order = strat.submitted.append
        strat.event_sink = strat.events.append
        strat.started = True
        strat.enabled = True
        for symbol in set(held) | set(targets or {}):
            policy.latest[symbol] = self._FakeQuote(100.0, 100.02, clock())
        return strat

    def decision_for(self, symbol, *, block_entry=False, must_flatten=False, needs_attention=False,
                     reason=None, action_type=None, action_date=None):
        return CA.GuardDecision(symbol=symbol, block_entry=block_entry, must_flatten=must_flatten,
                                needs_attention=needs_attention, reason=reason,
                                action_type=action_type, action_date=action_date)

    def test_no_guard_configured_is_inert(self):
        strategy = self.strategy(held={}, targets={"AAPL": 1})
        strategy.rebalance()
        self.assertEqual(len(strategy.submitted), 1)
        self.assertEqual(strategy._fake_order_factory.calls[0]["side"], OrderSide.BUY)

    def test_blocked_entry_symbol_never_gets_a_buy_order(self):
        guard_decisions = {"AAPL": self.decision_for("AAPL", block_entry=True, needs_attention=True,
                                                      reason="corporate_action_lookup_failed"),
                           "MSFT": self.decision_for("MSFT")}
        strategy = self.strategy(held={}, targets={"AAPL": 1, "MSFT": 1}, guard_decisions=guard_decisions)
        strategy.rebalance()
        self.assertEqual(len(strategy.submitted), 1)
        instrument_ids = [c["instrument_id"] for c in strategy._fake_order_factory.calls]
        self.assertNotIn("AAPL.ALPACA", instrument_ids)
        self.assertIn("MSFT.ALPACA", instrument_ids)

    def test_held_symbol_with_qualifying_action_is_flattened_before_close(self):
        guard_decisions = {"AAPL": self.decision_for("AAPL", block_entry=True, must_flatten=True,
                                                      reason="corporate_action_reverse_split",
                                                      action_type="reverse_split", action_date=TODAY)}
        strategy = self.strategy(held={"AAPL": 3}, targets={"AAPL": 3}, guard_decisions=guard_decisions)
        strategy.rebalance()
        self.assertEqual(len(strategy.submitted), 1)
        call = strategy._fake_order_factory.calls[0]
        self.assertEqual(call["side"], OrderSide.SELL)
        self.assertEqual(call["quantity"], "3")
        self.assertIn("reason=corporate_action_flatten", call["tags"])

    def test_flatten_still_forced_even_when_decide_would_have_kept_the_position(self):
        """Unlike an ordinary rebalance-delta sell, the forced flatten fires
        even though this tick's own decision.targets kept the full
        quantity (mirrors gap_risk_stop's own override of the ordinary
        held<=target skip)."""
        guard_decisions = {"AAPL": self.decision_for("AAPL", block_entry=True, must_flatten=True,
                                                      reason="corporate_action_merger",
                                                      action_type="merger", action_date=TODAY)}
        strategy = self.strategy(held={"AAPL": 2}, targets={"AAPL": 2}, guard_decisions=guard_decisions)
        strategy.rebalance()
        self.assertEqual(len(strategy.submitted), 1)
        self.assertEqual(strategy._fake_order_factory.calls[0]["side"], OrderSide.SELL)

    def test_symbol_without_any_action_is_unaffected(self):
        guard_decisions = {"AAPL": self.decision_for("AAPL")}
        strategy = self.strategy(held={}, targets={"AAPL": 2}, guard_decisions=guard_decisions)
        strategy.rebalance()
        self.assertEqual(len(strategy.submitted), 1)
        self.assertEqual(strategy._fake_order_factory.calls[0]["side"], OrderSide.BUY)
        self.assertEqual(strategy._fake_order_factory.calls[0]["quantity"], "2")

    def test_needs_attention_events_are_recorded_without_forcing_a_flatten(self):
        guard_decisions = {"AAPL": self.decision_for("AAPL", block_entry=True, needs_attention=True,
                                                      reason="corporate_action_lookup_ambiguous")}
        strategy = self.strategy(held={"AAPL": 1}, targets={"AAPL": 1}, guard_decisions=guard_decisions)
        strategy.rebalance()
        self.assertEqual(strategy.submitted, [])  # not blocked from holding, not forced to flatten
        events = [e for e in strategy.events if e.get("type") == "corporate_action_guard"]
        self.assertEqual(len(events), 1)
        self.assertTrue(events[0]["needs_attention"])
        self.assertFalse(events[0]["must_flatten"])

    def test_flatten_event_carries_no_credential_value_only_bounded_fields(self):
        guard_decisions = {"AAPL": self.decision_for("AAPL", block_entry=True, must_flatten=True,
                                                      reason="corporate_action_cash_dividend",
                                                      action_type="cash_dividend", action_date=TODAY)}
        strategy = self.strategy(held={"AAPL": 1}, targets={"AAPL": 1}, guard_decisions=guard_decisions)
        strategy.rebalance()
        events = [e for e in strategy.events if e.get("type") == "corporate_action_guard"]
        self.assertEqual(len(events), 1)
        self.assertEqual(set(events[0]), {"type", "symbol", "block_entry", "must_flatten",
                                          "needs_attention", "reason", "action_type", "action_date"})

    def test_decision_event_carries_the_guard_summary_lists(self):
        guard_decisions = {"AAPL": self.decision_for("AAPL", block_entry=True, must_flatten=True,
                                                      reason="corporate_action_spin_off",
                                                      action_type="spin_off", action_date=TODAY),
                           "MSFT": self.decision_for("MSFT", block_entry=True,
                                                      reason="corporate_action_lookup_failed",
                                                      needs_attention=True)}
        strategy = self.strategy(held={"AAPL": 1}, targets={"AAPL": 1, "MSFT": 1}, guard_decisions=guard_decisions)
        strategy.rebalance()
        events = [e for e in strategy.events if e.get("type") == "decision"]
        self.assertEqual(len(events), 1)
        self.assertEqual(sorted(events[0]["corporate_action_must_flatten"]), ["AAPL"])
        self.assertEqual(sorted(events[0]["corporate_action_block_entry"]), ["AAPL", "MSFT"])


if __name__ == "__main__":
    unittest.main()
