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


import importlib.util as _ilu  # noqa: E402
_LEV_FILE = ENGINE / "leverage.py"
_LEV_SPEC = _ilu.spec_from_file_location("adaptive_policy_leverage", _LEV_FILE)
LEV = _ilu.module_from_spec(_LEV_SPEC)
sys.modules[_LEV_SPEC.name] = LEV
_LEV_SPEC.loader.exec_module(LEV)


class LeveragePolicyConfigBoundsTests(unittest.TestCase):
    """G-e: PolicyConfig.leverage_policy_id / __post_init__ max_leverage bound."""

    def config(self, max_leverage, leverage_policy_id=None, gross_cap=None):
        # PolicyConfig.capital defaults to 10000; gross_cap here matches
        # that default (10000 * max_leverage) unless overridden, so the
        # "gross_cap <= capital*max_leverage" bound is exercised precisely.
        return M.PolicyConfig(symbols=("SPY", "QQQ", "IWM", "DIA", "AAPL", "MSFT"), max_positions=6,
                              max_leverage=max_leverage,
                              gross_cap=gross_cap if gross_cap is not None else 10000 * max_leverage,
                              leverage_policy_id=leverage_policy_id)

    def test_3x_and_4x_refused_without_id_existing_bound_kept(self):
        with self.assertRaises(ValueError):
            self.config(3)
        with self.assertRaises(ValueError):
            self.config(4)

    def test_4x_accepted_with_v1_id(self):
        c = self.config(4, leverage_policy_id=LEV.LEVERAGE_POLICY_VERSION)
        self.assertEqual(c.max_leverage, 4)

    def test_4_5x_refused_with_id(self):
        with self.assertRaises(ValueError):
            self.config(4.5, leverage_policy_id=LEV.LEVERAGE_POLICY_VERSION)

    def test_unknown_id_refused(self):
        with self.assertRaises(ValueError):
            self.config(2, leverage_policy_id="some-other-version")

    def test_gross_cap_exceeding_capital_times_max_leverage_still_refused(self):
        with self.assertRaises(ValueError):
            self.config(4, leverage_policy_id=LEV.LEVERAGE_POLICY_VERSION, gross_cap=10000 * 4 + 1)


class LeveragePolicyWrapperTests(unittest.TestCase):
    """G-e: strategies.AdaptivePolicy leverage-ceiling entry-budget gating."""

    def leverage_policy(self, max_leverage="4"):
        from decimal import Decimal as D
        capital = D("1000")  # matches this class's PolicyConfig.capital default (see policy())
        config = {"max_leverage": max_leverage, "capital_usd": str(capital), "leverage_policy": LEV.CANONICAL_V1_BLOCK,
                  "max_gross_exposure_usd": str(capital * D(max_leverage))}
        session_policy = {"overnight_holds": False, "overnight_gross_multiple": D("1.0")}
        return LEV.validate_leverage_policy(config, session_policy)

    def policy(self, max_leverage="4"):
        lev = self.leverage_policy(max_leverage)
        config = M.PolicyConfig(symbols=("SPY", "QQQ", "IWM", "DIA", "AAPL", "MSFT"), max_positions=6,
                                capital=1000, gross_cap=1000 * float(max_leverage), max_leverage=float(max_leverage),
                                leverage_policy_id=LEV.LEVERAGE_POLICY_VERSION)
        return M.AdaptivePolicy(config, leverage_policy=lev)

    def feed(self, policy, stock_prices, *, benchmark_slope=0, start=1000):
        for i, price in enumerate(stock_prices):
            for s in policy.config.symbols:
                p = 100 + benchmark_slope * i if s in policy.config.benchmarks else price
                policy.observe(s, p - .005, p + .005, start + i)
        return start + len(stock_prices) - 1

    def test_ceiling_zero_yields_no_new_entries(self):
        p = self.policy()
        now = self.feed(p, [100 + i * .04 for i in range(40)], benchmark_slope=.015)
        p.sync_positions({"AAPL": {"qty": 1, "avg_entry_price": "101"}}, now)
        d = p.decide(now, leverage_inputs=M.LeverageInputs(session="RTH",
                     drawdown_fraction=__import__("decimal").Decimal("0"), kill_switch=True))
        self.assertEqual(p.last_leverage_ceiling, 0.0)
        # A ceiling of 0 authorizes zero new entry budget; nothing (including
        # the already-held AAPL, which is not re-signaled at 0 budget) is
        # newly targeted. No leverage-specific liquidation mechanism exists:
        # a holding that falls out of targets is handled entirely by the
        # unchanged, pre-existing exit chain (portfolio_rotation fallback,
        # exactly as any other budget-exhaustion cause already produces --
        # see strategies_v1.AdaptivePolicy._decide_core's trailing "for
        # symbol in self.holdings: exits.setdefault(...)" fallback).
        self.assertEqual(d.targets, {})
        # Whatever reason the unchanged exit chain assigns (take_profit here,
        # given this fixture's entry price/trend -- or portfolio_rotation's
        # fallback otherwise), it is unaffected by the leverage ceiling: no
        # new "leverage_ceiling_zero"-style exit reason is introduced.
        self.assertIn(d.exits.get("AAPL"), ("take_profit", "portfolio_rotation"))

    def test_ceiling_2_vs_4_gives_expected_budget_difference(self):
        from decimal import Decimal as D
        p4 = self.policy("4")
        now4 = self.feed(p4, [100 + i * .04 for i in range(40)], benchmark_slope=.015)
        d4 = p4.decide(now4, leverage_inputs=M.LeverageInputs(session="RTH", drawdown_fraction=D("0"), kill_switch=False))

        p2 = self.policy("4")  # same config; only the observed ceiling differs
        now2 = self.feed(p2, [100 + i * .04 for i in range(40)], benchmark_slope=.015)
        d2 = p2.decide(now2, leverage_inputs=M.LeverageInputs(session="RTH", drawdown_fraction=D("0"), kill_switch=False,
                       account_multiplier=D("2")))
        used4 = sum(p4.latest[s].ask * q for s, q in d4.targets.items())
        used2 = sum(p2.latest[s].ask * q for s, q in d2.targets.items())
        self.assertGreaterEqual(used4, used2)

    def test_range_regime_still_capped_at_1_regardless_of_schedule(self):
        from decimal import Decimal as D
        p = self.policy()
        now = self.feed(p, [100] * 39 + [100.20])  # breakout -> "range" regime
        d = p.decide(now, leverage_inputs=M.LeverageInputs(session="RTH", drawdown_fraction=D("0"), kill_switch=False))
        self.assertEqual(d.regime, "range")
        self.assertLessEqual(sum(p.latest[s].ask * q for s, q in d.targets.items()), p.config.capital * 1)

    def test_decide_without_leverage_inputs_fails_closed_to_zero(self):
        p = self.policy()
        now = self.feed(p, [100 + i * .04 for i in range(40)], benchmark_slope=.015)
        d = p.decide(now)
        self.assertEqual(p.last_leverage_ceiling, 0.0)
        self.assertEqual(d.targets, {})

    def test_policy_without_id_raises_config_mismatch(self):
        lev = self.leverage_policy()
        # max_leverage=2.0 (valid without an id) isolates AdaptivePolicy's
        # own leverage_policy/leverage_policy_id agreement check from
        # PolicyConfig's separate max_leverage bound (already covered by
        # LeveragePolicyConfigBoundsTests above).
        config = M.PolicyConfig(symbols=("SPY", "QQQ", "IWM", "DIA", "AAPL", "MSFT"), max_positions=6,
                                capital=1000, gross_cap=2000, max_leverage=2.0)  # no leverage_policy_id
        with self.assertRaisesRegex(ValueError, "leverage_policy_config_mismatch"):
            M.AdaptivePolicy(config, leverage_policy=lev)

    def test_id_without_policy_raises_config_mismatch(self):
        config = M.PolicyConfig(symbols=("SPY", "QQQ", "IWM", "DIA", "AAPL", "MSFT"), max_positions=6,
                                capital=1000, gross_cap=4000, max_leverage=4.0,
                                leverage_policy_id=LEV.LEVERAGE_POLICY_VERSION)
        with self.assertRaises(ValueError):
            M.AdaptivePolicy(config, leverage_policy=None)

    def test_pending_buy_notional_usd_consumes_leveraged_entry_budget(self):
        """LEV-RI-A (2026-09-22 leverage fix round 1): a still-resting,
        unfilled buy order's notional is invisible to `p.holdings` (only
        filled positions sync there -- see sync_positions) but is still
        capital this tick's new entries must not re-spend. Without the
        fix, `pending_buy_notional_usd` was not even an accepted keyword;
        with it wired through LeverageInputs -> AdaptivePolicy.decide ->
        _decide_core, a pending notional at least as large as the whole
        leveraged budget must authorize zero new entries."""
        from decimal import Decimal as D
        p_baseline = self.policy("4")
        now1 = self.feed(p_baseline, [100 + i * .04 for i in range(40)], benchmark_slope=.015)
        d_baseline = p_baseline.decide(now1, leverage_inputs=M.LeverageInputs(
            session="RTH", drawdown_fraction=D("0"), kill_switch=False))
        self.assertGreater(len(d_baseline.targets), 0, d_baseline)

        p_pending = self.policy("4")
        now2 = self.feed(p_pending, [100 + i * .04 for i in range(40)], benchmark_slope=.015)
        d_pending = p_pending.decide(now2, leverage_inputs=M.LeverageInputs(
            session="RTH", drawdown_fraction=D("0"), kill_switch=False,
            pending_buy_notional_usd=D("100000")))
        self.assertEqual(d_pending.targets, {})

    def test_leveraged_budget_counts_a_same_tick_exit_position_as_still_committed(self):
        """CX-P1 (2026-09-22 leverage fix round 1): a symbol whose exit
        this tick's plan decides (take_profit/stop/trailing/...) leaves
        `targets` immediately even though the position is still physically
        held until its sell order actually fills. The leveraged budget must
        still count it as committed capital -- exposed via
        Decision.effective_leverage (`used / capital`, computed after the
        same-tick entry loop) -- not treat it as already-freed room for a
        fresh entry."""
        from decimal import Decimal as D
        p = self.policy("4")
        now = self.feed(p, [100 + i * .04 for i in range(40)], benchmark_slope=.015)
        # Mirrors test_ceiling_zero_yields_no_new_entries's fixture: this
        # trend/entry-price combination triggers AAPL's take_profit exit.
        p.sync_positions({"AAPL": {"qty": 27, "avg_entry_price": "101"}}, now)
        d = p.decide(now, leverage_inputs=M.LeverageInputs(session="RTH", drawdown_fraction=D("0"), kill_switch=False))
        self.assertIn("AAPL", d.exits, d)
        self.assertNotIn("AAPL", d.targets, d)
        committed = float(p.latest["AAPL"].ask) * 27
        self.assertGreaterEqual(d.effective_leverage * p.config.capital, committed - 1e-6)

    def test_non_leveraged_path_used_stays_targets_only(self):
        """The non-leveraged path (leverage_ceiling is None, e.g. every
        default config) must stay byte-identical to the pre-fix targets-only
        `used` computation -- a same-tick exit must NOT be folded into
        Decision.effective_leverage there, preserving the golden-equivalence
        contract documented in strategies.py's module docstring."""
        # Constructing without a leverage_policy exercises AdaptivePolicyV1's
        # own decide() (no leverage_ceiling ever computed/passed).
        import strategies_v1 as v1
        p = v1.AdaptivePolicy(M.PolicyConfig(symbols=("SPY", "QQQ", "IWM", "DIA", "AAPL", "MSFT"),
                                             max_positions=6, capital=1000, gross_cap=1000))
        now = self.feed(p, [100 + i * .04 for i in range(40)], benchmark_slope=.015)
        p.sync_positions({"AAPL": {"qty": 27, "avg_entry_price": "101"}}, now)
        d = p.decide(now)
        self.assertIn("AAPL", d.exits, d)
        self.assertNotIn("AAPL", d.targets, d)
        # AAPL's committed notional must NOT appear in effective_leverage
        # here -- only this tick's `targets` (fresh entries plus any kept
        # holding) do, exactly as before this task's leveraged-path fix.
        entered = sum(p.latest[s].ask * q for s, q in d.targets.items())
        self.assertAlmostEqual(d.effective_leverage * p.config.capital, entered, places=6)

    def test_default_wrapper_still_uses_super_decide_fast_path(self):
        # No pool, no selector, no leverage_policy -- unchanged fast path;
        # _decide_core must not observe a leverage_ceiling kwarg (verified
        # indirectly: golden-equivalence tests already assert byte-identical
        # decisions for exactly this construction).
        p = M.AdaptivePolicy(M.PolicyConfig(symbols=("SPY", "QQQ", "IWM", "DIA", "AAPL", "MSFT"), max_positions=6))
        self.assertIsNone(p.leverage_policy)
        now = self.feed(p, [100] * 10)
        d = p.decide(now)
        self.assertEqual(d.targets, {})


if __name__ == "__main__":
    unittest.main()
