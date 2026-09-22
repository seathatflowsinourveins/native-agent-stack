"""Local causal policy fixtures; not historical or broker performance evidence."""
from dataclasses import asdict
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ENGINE = Path(__file__).resolve().parents[1] / "blueprints/us-equities/adaptive-paper"
PATH = ENGINE / "strategies.py"
sys.path.insert(0, str(ENGINE))  # strategies.py imports sibling strategies_v1/selector modules
SPEC = importlib.util.spec_from_file_location("adaptive_policies", PATH)
M = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = M
SPEC.loader.exec_module(M)

GOLDEN_PATH = ENGINE / "receipts" / "adaptive_policy_v1.golden.json"
RECEIPT_PATH = ENGINE / "adaptive_policy_v1.receipt.json"


class PolicyTests(unittest.TestCase):
    def policy(self, **changes):
        return M.AdaptivePolicy(M.PolicyConfig(symbols=("SPY", "QQQ", "IWM", "DIA", "AAPL", "MSFT"),
                                              max_positions=6, **changes))

    def feed(self, policy, stock_prices, *, benchmark_slope=0, start=1000):
        for i, price in enumerate(stock_prices):
            for s in policy.config.symbols:
                p = 100 + benchmark_slope * i if s in policy.config.benchmarks else price
                policy.observe(s, p - .005, p + .005, start + i)
        return start + len(stock_prices) - 1

    def test_warmup_is_cash_and_no_future_or_reordered_quotes(self):
        p = self.policy()
        now = self.feed(p, [100] * 10)
        d = p.decide(now)
        self.assertEqual(d.targets, {})
        self.assertEqual(d.regime, "unavailable")
        self.assertFalse(p.observe("AAPL", 99, 100, now - 10))
        self.assertFalse(p.observe("AAPL", float("nan"), 100, now + 1))
        self.assertFalse(p.observe("AAPL", 101, 100, now + 1))

    def test_trend_allocates_cost_qualified_signals_with_exposure_cap(self):
        p = self.policy()
        now = self.feed(p, [100 + i * .04 for i in range(40)], benchmark_slope=.015)
        d = p.decide(now)
        self.assertEqual(d.regime, "trend")
        self.assertIn("trend_momentum", {s.family for s in d.signals})
        self.assertIn("relative_strength", {s.family for s in d.signals})
        self.assertGreater(len(d.targets), 0)
        self.assertLessEqual(sum(p.latest[s].ask * q for s, q in d.targets.items()), p.config.gross_cap)
        self.assertTrue(all(q <= 1 for q in d.targets.values()))

    def test_breakout_uses_previous_range_only(self):
        p = self.policy()
        now = self.feed(p, [100] * 39 + [100.20])
        d = p.decide(now)
        self.assertIn("range_breakout", {s.family for s in d.signals})
        self.assertIn("AAPL", d.targets)

    def test_mean_reversion_requires_observed_turn(self):
        p = self.policy()
        now = self.feed(p, [100] * 36 + [99.7, 99.65, 99.6, 99.65, 99.7])
        d = p.decide(now)
        self.assertEqual(d.regime, "range")
        self.assertIn("mean_reversion", {s.family for s in d.signals})
        q = self.policy()
        now = self.feed(q, [100] * 36 + [99.7, 99.65, 99.6, 99.55, 99.5])
        self.assertNotIn("mean_reversion", {s.family for s in q.decide(now).signals})

    def test_regime_shift_reduces_positions_to_cash(self):
        p = self.policy()
        now = self.feed(p, [100 + i * .04 for i in range(40)], benchmark_slope=.015)
        self.assertTrue(p.decide(now).targets)
        p.sync_positions({"AAPL": {"qty": 1, "avg_entry_price": "101"}}, now)
        now = self.feed(p, [100] * 40, benchmark_slope=-.04, start=1040)
        d = p.decide(now)
        self.assertEqual(d.targets, {})
        self.assertEqual(d.exits["AAPL"], "risk_off")

    def test_stop_and_take_profit_and_trailing_exit(self):
        for expected, price, high in [("stop_loss", 99.7, 100), ("take_profit", 100.5, 100),
                                      ("trailing_stop", 100.1, 100.3)]:
            with self.subTest(expected=expected):
                p = self.policy()
                now = self.feed(p, [100] * 40)
                p.sync_positions({"AAPL": {"qty": 1, "avg_entry_price": "100"}}, now - 10)
                p.holdings["AAPL"].high_bid = high
                p.observe("AAPL", price, price + .01, now + .1)
                d = p.decide(now + .1)
                self.assertEqual(d.exits["AAPL"], expected)
                self.assertNotIn("AAPL", d.targets)

    def test_stale_benchmark_and_stop_prevent_entries(self):
        p = self.policy()
        now = self.feed(p, [100 + i * .04 for i in range(40)], benchmark_slope=.015)
        self.assertFalse(p.decide(now, allow_entries=False).targets)
        self.assertFalse(p.decide(now + 4).targets)
        self.assertFalse(p.decide(now + 4, force_exit=True).targets)

    def test_never_churn_to_meet_rate_target(self):
        p = self.policy()
        now = self.feed(p, [100] * 120)
        d = p.decide(now)
        self.assertEqual(d.targets, {})
        self.assertEqual(d.signals, ())

    def test_expensive_one_share_and_cap_headroom(self):
        p = self.policy()
        for i in range(40):
            for symbol in p.config.symbols:
                price = (700 + i * .30) if symbol == "AAPL" else (100 + i * .015)
                p.observe(symbol, price - .005, price + .005, 1000 + i)
        d = p.decide(1039)
        self.assertEqual(d.targets.get("AAPL"), 1)
        self.assertLessEqual(sum(p.latest[s].ask * q for s, q in d.targets.items()),
                             p.config.gross_cap - p.config.max_order_notional)

    def test_stale_benchmark_freezes_entries_without_risk_off_liquidation(self):
        p = self.policy()
        now = self.feed(p, [100] * 40)
        p.sync_positions({"AAPL": {"qty": "0.123456789", "avg_entry_price": "100"}}, now)
        p.observe("AAPL", 99.995, 100.005, now + 4)
        d = p.decide(now + 4)
        self.assertEqual(d.regime, "unavailable")
        self.assertEqual(d.targets, {"AAPL": M.Decimal("0.123456789")})
        self.assertEqual(d.exits, {})

    def test_trailing_high_starts_at_observed_post_entry_bid(self):
        p = self.policy()
        now = self.feed(p, [10] * 40)
        p.sync_positions({"AAPL": {"qty": "1", "avg_entry_price": "10.02"}}, now)
        self.assertEqual(p.holdings["AAPL"].high_bid, 0)
        d = p.decide(now)
        self.assertNotEqual(d.exits.get("AAPL"), "trailing_stop")

    def test_quote_buckets_do_not_drift_to_a_shorter_sample_count(self):
        p = self.policy()
        for i in range(340):
            t = 1000 + i * .101
            for symbol in p.config.symbols:
                price = 100 + i * .004
                p.observe(symbol, price - .005, price + .005, t)
        self.assertNotEqual(p.decide(t).regime, "unavailable")

    def test_limits_and_decimal_prices(self):
        with self.assertRaises(ValueError):
            self.policy(max_leverage=3)
        with self.assertRaises(ValueError):
            self.policy(capital=float("nan"))
        self.assertEqual(M.limit_price("99.99", "100.01", "buy"), "100.03")
        self.assertEqual(M.limit_price("99.99", "100.01", "sell"), "99.97")
        with self.assertRaises(ValueError):
            M.limit_price("nan", "100", "buy")


class GoldenEquivalenceTests(unittest.TestCase):
    """Byte-identical decisions vs. the fixture captured before the G-d
    strategy-rotation refactor (task-record: docs/tasks -- selector.py,
    strategies_v1.py split). Default `AdaptivePolicy(config)` (empty
    strategy_pool, no selector) must reproduce the pre-refactor engine
    exactly; see strategies.py's module docstring for why.

    POLICY_CLASS is overridden by GoldenEquivalenceV1DirectTests below to run
    the exact same 16 cases against strategies_v1.AdaptivePolicy directly
    (D6: the receipt's note previously implied only the v1 engine was
    checked, but this class actually instantiates the strategies.py wrapper
    -- both are now asserted against the same fixture)."""

    POLICY_CLASS = M.AdaptivePolicy

    def policy(self, **changes):
        return self.POLICY_CLASS(M.PolicyConfig(symbols=("SPY", "QQQ", "IWM", "DIA", "AAPL", "MSFT"),
                                                 max_positions=6, **changes))

    def feed(self, policy, stock_prices, *, benchmark_slope=0, start=1000):
        for i, price in enumerate(stock_prices):
            for s in policy.config.symbols:
                p = 100 + benchmark_slope * i if s in policy.config.benchmarks else price
                policy.observe(s, p - .005, p + .005, start + i)
        return start + len(stock_prices) - 1

    def ser(self, d):
        if d is None:
            return None
        out = asdict(d)
        out["targets"] = {k: str(v) for k, v in out["targets"].items()}
        out["signals"] = [dict(s) for s in out["signals"]]
        return json.loads(json.dumps(out, default=str))

    def test_golden_fixture_matches_current_default_engine(self):
        golden = json.loads(GOLDEN_PATH.read_text())
        cases = {}

        p = self.policy(); now = self.feed(p, [100] * 10)
        cases["warmup"] = self.ser(p.decide(now))

        p = self.policy(); now = self.feed(p, [100 + i * .04 for i in range(40)], benchmark_slope=.015)
        cases["trend"] = self.ser(p.decide(now))

        p = self.policy(); now = self.feed(p, [100] * 39 + [100.20])
        cases["breakout"] = self.ser(p.decide(now))

        p = self.policy(); now = self.feed(p, [100] * 36 + [99.7, 99.65, 99.6, 99.65, 99.7])
        cases["mean_reversion_yes"] = self.ser(p.decide(now))
        q = self.policy(); now2 = self.feed(q, [100] * 36 + [99.7, 99.65, 99.6, 99.55, 99.5])
        cases["mean_reversion_no"] = self.ser(q.decide(now2))

        p = self.policy(); now = self.feed(p, [100 + i * .04 for i in range(40)], benchmark_slope=.015)
        p.decide(now)
        p.sync_positions({"AAPL": {"qty": 1, "avg_entry_price": "101"}}, now)
        now = self.feed(p, [100] * 40, benchmark_slope=-.04, start=1040)
        cases["regime_shift_to_cash"] = self.ser(p.decide(now))

        exits_cases = {}
        for label, price, high in [("stop_loss", 99.7, 100), ("take_profit", 100.5, 100),
                                    ("trailing_stop", 100.1, 100.3)]:
            p = self.policy(); now = self.feed(p, [100] * 40)
            p.sync_positions({"AAPL": {"qty": 1, "avg_entry_price": "100"}}, now - 10)
            p.holdings["AAPL"].high_bid = high
            p.observe("AAPL", price, price + .01, now + .1)
            exits_cases[label] = self.ser(p.decide(now + .1))
        cases["exits"] = exits_cases

        p = self.policy(); now = self.feed(p, [100 + i * .04 for i in range(40)], benchmark_slope=.015)
        cases["stale_stop_1"] = self.ser(p.decide(now, allow_entries=False))
        cases["stale_stop_2"] = self.ser(p.decide(now + 4))
        cases["stale_stop_3"] = self.ser(p.decide(now + 4, force_exit=True))

        p = self.policy(); now = self.feed(p, [100] * 120)
        cases["never_churn"] = self.ser(p.decide(now))

        p = self.policy()
        for i in range(40):
            for symbol in p.config.symbols:
                price = (700 + i * .30) if symbol == "AAPL" else (100 + i * .015)
                p.observe(symbol, price - .005, price + .005, 1000 + i)
        cases["expensive_share"] = self.ser(p.decide(1039))

        p = self.policy(); now = self.feed(p, [100] * 40)
        p.sync_positions({"AAPL": {"qty": "0.123456789", "avg_entry_price": "100"}}, now)
        p.observe("AAPL", 99.995, 100.005, now + 4)
        cases["stale_no_liq"] = self.ser(p.decide(now + 4))

        p = self.policy(); now = self.feed(p, [10] * 40)
        p.sync_positions({"AAPL": {"qty": "1", "avg_entry_price": "10.02"}}, now)
        cases["trailing_high_start_hb"] = str(p.holdings["AAPL"].high_bid)
        cases["trailing_high_start"] = self.ser(p.decide(now))

        p = self.policy()
        for i in range(340):
            t = 1000 + i * .101
            for symbol in p.config.symbols:
                price = 100 + i * .004
                p.observe(symbol, price - .005, price + .005, t)
        cases["quote_bucket_regime"] = p.decide(t).regime

        self.assertEqual(cases, golden)
        self.assertEqual(len(golden), 16)

    def test_golden_fixture_sha_and_case_count_match_the_registry_receipt(self):
        # D10: the receipt registry.json pins for adaptive_policy_v1 must
        # actually describe this fixture, not just be present.
        import hashlib
        receipt = json.loads(RECEIPT_PATH.read_text())
        fixture_bytes = GOLDEN_PATH.read_bytes()
        self.assertEqual(receipt["golden_fixture_sha256"], hashlib.sha256(fixture_bytes).hexdigest())
        self.assertEqual(receipt["case_count"], len(json.loads(fixture_bytes)))


class GoldenEquivalenceV1DirectTests(GoldenEquivalenceTests):
    """D6: same 16 cases, same fixture, but strategies_v1.AdaptivePolicy
    (the moved-verbatim engine) is instantiated directly, not through
    strategies.py's wrapper -- see adaptive_policy_v1.receipt.json's note."""

    POLICY_CLASS = M.AdaptivePolicyV1


class _V1Spec:
    id = "adaptive_policy_v1"
    receipt_sha256 = "0" * 64
    sessions = ("regular",)
    regime_affinity = ()

    def propose(self, decision_inputs):
        return {}


class _LiquidatingFakeSelector:
    """Always returns a decision whose liquidate flag is True, regardless
    of inputs -- isolates AdaptivePolicy.decide()'s own force_exit_reason
    logic from RegimeSelector's real state machine."""

    def decide(self, decision_inputs):
        from selector import SelectionDecision, ACTIVE
        return SelectionDecision(timestamp=decision_inputs.timestamp, prior_state=ACTIVE, new_state=ACTIVE,
                                 regime=decision_inputs.regime, confidence=1.0, advantage_bps=50.0,
                                 incumbent_id="adaptive_policy_v1", candidate_id="adaptive_policy_v1",
                                 reason_codes=("switched",), blocked_by=(), liquidate=True)


class RotationForceExitReasonTests(unittest.TestCase):
    """R6: when the caller passes force_exit=True (trial deadline/STOP/
    cleanup) on the same tick a rotation selector also decides to
    liquidate, the caller's own reason ("trial_end") must win over the
    generic "rotation_flatten" label -- a caller-forced exit is not a
    rotation event. Only a liquidation that itself turns force_exit on
    (the caller had not already asked for one) is genuinely
    selector-driven and keeps "rotation_flatten"."""

    def policy(self):
        config = M.PolicyConfig(symbols=("SPY", "QQQ", "IWM", "DIA", "AAPL", "MSFT"), max_positions=6)
        return M.AdaptivePolicy(config, strategy_pool=(_V1Spec(),), selector=_LiquidatingFakeSelector())

    def seed(self, p, now):
        for i in range(40):
            for s in p.config.symbols:
                p.observe(s, 100 - .005, 100 + .005, now - 40 + i)
        p.sync_positions({"AAPL": {"qty": 1, "avg_entry_price": "100"}}, now)

    def test_selector_driven_liquidation_without_caller_force_exit_is_rotation_flatten(self):
        p = self.policy()
        now = 2000.0
        self.seed(p, now)
        d = p.decide(now, force_exit=False)
        self.assertEqual(d.exits.get("AAPL"), "rotation_flatten")

    def test_caller_force_exit_wins_over_same_tick_liquidation(self):
        p = self.policy()
        now = 2000.0
        self.seed(p, now)
        d = p.decide(now, force_exit=True)
        self.assertEqual(d.exits.get("AAPL"), "trial_end")


if __name__ == "__main__":
    unittest.main()
