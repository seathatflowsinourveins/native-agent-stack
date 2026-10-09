"""T22 engine acceptance and order-state inverse checks; synthetic inputs only."""

from __future__ import annotations

import asyncio
import importlib
import importlib.util
import time
import unittest
from dataclasses import replace
from datetime import datetime, timezone

contracts = importlib.import_module("blueprints.us-equities.strategies.contracts")
presets = importlib.import_module("blueprints.us-equities.strategies.presets")
NATIVE = importlib.util.find_spec("nautilus_trader") is not None
if NATIVE:
    families = importlib.import_module("blueprints.us-equities.strategies.families")
    simulation = importlib.import_module("blueprints.us-equities.strategies.simulation")


class ContractTests(unittest.TestCase):
    def snapshot(self, **kwargs):
        base = {
            "instrument_id": "T22.ALPACA",
            "cohort_sha256": "1" * 64,
            "source_sha256": "2" * 64,
            "ts_event": 100,
            "ts_init": 200,
            "valid_until_ns": 300,
            "values": (("momentum_20", "0.1"),),
        }
        base.update(kwargs)
        return contracts.FactorSnapshot(**base)

    def test_availability_cannot_precede_event_or_outlive_validation_window(self):
        for overrides in ({"ts_init": 99}, {"valid_until_ns": 199}, {"ts_event": True}):
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                self.snapshot(**overrides)

    def test_factors_require_exact_finite_decimals_and_unique_sorted_keys(self):
        for values in (
            (("a", "NaN"),),
            (("a", "Infinity"),),
            (("a", 0.1),),
            (("a", "1"), ("a", "2")),
            (("b", "1"), ("a", "2")),
        ):
            with (
                self.subTest(values=values),
                self.assertRaises((TypeError, ValueError)),
            ):
                self.snapshot(values=values)

    def test_historical_cutoff_is_explicit_and_development_requires_release(self):
        cutoff = int(datetime(2026, 10, 14, tzinfo=timezone.utc).timestamp() * 1e9)
        self.assertEqual(contracts.DEVELOPMENT_CUTOFF_NS, cutoff)
        with self.assertRaises(ValueError):
            self.snapshot(
                evidence_class="development",
                ts_event=cutoff,
                ts_init=cutoff,
                valid_until_ns=cutoff,
            )
        with self.assertRaises(ValueError):
            contracts.StrategySpec("T22.ALPACA", "1" * 64, evidence_class="development")
        accepted = contracts.StrategySpec(
            "T22.ALPACA",
            "1" * 64,
            evidence_class="development",
            qualified_data=("released_development", "horizon_qualified"),
            exit_deadline_ns=cutoff - 1,
        )
        self.assertEqual(accepted.evidence_class, "development")

    def test_serialization_preserves_exact_values_and_provenance(self):
        value = self.snapshot(values=(("momentum_20", "0.10000000001"),))
        self.assertEqual(contracts.FactorSnapshot.from_json(value.as_dict()), value)

    def test_presets_are_versioned_and_narrative_squeeze_override_is_explicit(self):
        with self.assertRaises(ValueError):
            presets.preset_for("model-generated", "catalyst")
        with self.assertRaises(TypeError):
            presets.PRESETS["aggressive-v1"] = presets.PRESETS["standard-v1"]
        self.assertEqual(
            presets.preset_for("aggressive-v1", "squeeze_borrow").trail_atr,
            presets.PRESETS["conservative-v1"].trail_atr,
        )
        self.assertIsNone(
            presets.preset_for("standard-v1", "trend_new_highs").take_profit_r
        )
        self.assertEqual(
            presets.preset_for("standard-v1", "halt_reopen").max_hold_seconds, 3600
        )


@unittest.skipUnless(NATIVE, "requires the exact locked Nautilus rc5 runtime")
class NativeStrategyTests(unittest.TestCase):
    def test_same_family_classes_use_real_LiveNode_and_owned_partial_fills(self):
        fixture = importlib.import_module("tests.test_adaptive_paper_native")
        adapter = importlib.import_module(
            "blueprints.us-equities.adaptive-paper.native_adapter"
        )
        for name, cls in families.FAMILIES.items():
            with self.subTest(family=name):

                async def exercise(strategy_class=cls):
                    port = fixture.FakePort()
                    now = time.time_ns()
                    cohort = contracts.digest(
                        {"fixture": "t22-live-port", "members": ["SPY.ALPACA"]}
                    )
                    spec = contracts.StrategySpec(
                        "SPY.ALPACA",
                        cohort,
                        preset="aggressive-v1",
                        position_cap_usd="1000",
                        cash_cap_usd="1000",
                        loss_cap_usd="20",
                        exit_deadline_ns=now + 1_000_000_000,
                    )
                    strategy = strategy_class(spec)
                    values = dict(
                        simulation.POSITIVE_FACTORS,
                        atr_price="2",
                        entry_trigger="100",
                        structure_low="99.7",
                    )
                    snapshot = contracts.FactorSnapshot(
                        "SPY.ALPACA",
                        cohort,
                        contracts.digest(values),
                        now,
                        now,
                        now + 10_000_000_000,
                        tuple(sorted(values.items())),
                        expiry_ns=now + 86400_000_000_000,
                    )
                    original_start = port.start

                    async def start(on_quote, on_order):
                        # Caller injection of already-known factors. No broker,
                        # provider, paper runner or durable account ledger exists.
                        strategy.on_data(snapshot)
                        await original_start(on_quote, on_order)

                    port.start = start
                    session = adapter.build_node(
                        port, [{"symbol": "SPY", "currency": "USD"}], [strategy]
                    )
                    strategy.fault_sink = session.fail

                    async def feed():
                        deadline = time.monotonic() + 5
                        while time.monotonic() < deadline:
                            if port.started:
                                port.on_quote(
                                    {
                                        "symbol": "SPY",
                                        "bid": "100",
                                        "ask": "100.01",
                                        "bid_size": "100",
                                        "ask_size": "100",
                                        "ts_ns": time.time_ns(),
                                    }
                                )
                                if (
                                    len(port.submissions) >= 2
                                    and port.qty == 0
                                    and not port.active
                                ):
                                    session.stop()
                                    return
                            await asyncio.sleep(0.05)
                        session.stop()

                    job = asyncio.create_task(feed())
                    try:
                        await asyncio.wait_for(session.run_async(), timeout=8)
                        await job
                    finally:
                        if not job.done():
                            job.cancel()
                    return port, strategy, session

                port, strategy, session = asyncio.run(exercise())
                self.assertEqual(session.errors, [], session.errors)
                self.assertEqual(strategy.callback_faults, [])
                self.assertEqual(len(port.submissions), 2, strategy.trace)
                self.assertEqual(
                    (strategy.quantity, strategy.pending, port.qty, port.active),
                    (0, None, 0, {}),
                )
                self.assertGreater(
                    len([r for r in strategy.trace if r["event"] == "fill"]), 2
                )

    def test_all_families_and_presets_run_same_strategy_classes(self):
        for family in families.FAMILIES:
            for preset in presets.PRESETS:
                with self.subTest(family=family, preset=preset):
                    result = simulation.run_case(family, preset)
                    self.assertTrue(result["passed"], result)
                    self.assertGreaterEqual(result["fill_callbacks"], 2, result)
                    self.assertEqual(result["native_order_types"], ["LIMIT"])

    def test_noncohort_missing_inputs_and_halt_never_enter(self):
        for family in families.FAMILIES:
            for snapshot in (
                simulation.fixture_snapshot(member=False),
                simulation.fixture_snapshot(
                    values={"atr_price": "0.2", "entry_trigger": "10"}
                ),
                simulation.fixture_snapshot(halted=True),
            ):
                with self.subTest(family=family, snapshot=snapshot):
                    result = simulation.run_case(family, snapshot=snapshot)
                    self.assertEqual(result["orders"], 0, result)
                    self.assertEqual(result["owned_quantity"], "0")

    def test_forward_or_wrong_cohort_snapshot_never_enters(self):
        wrong = replace(simulation.fixture_snapshot(), cohort_sha256="0" * 64)
        future = simulation.fixture_snapshot(
            ts_init=simulation.BASE_NS + 20_000_000_000
        )
        for snapshot in (wrong, future):
            result = simulation.run_case("gap_premarket", snapshot=snapshot)
            self.assertEqual(result["orders"], 0, result)

    def test_native_target_profile_refuses_unqualified_T15_capability(self):
        result = simulation.run_case(
            "momentum_breakout",
            "standard-v1",
            spec_overrides={"execution_profile": "native-target-v1"},
        )
        self.assertEqual(result["orders"], 0)
        self.assertIn("T15_native_order_capability_unqualified", result["flags"])
        self.assertFalse(result["passed"])

    def test_extended_hours_stop_uses_limit_only(self):
        # PRE on a completed synthetic date, never acquired broker data.
        pre = int(datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc).timestamp() * 1e9)
        s = replace(
            simulation.fixture_snapshot(),
            ts_event=pre - 600_000_000_000,
            ts_init=pre - 600_000_000_000,
            valid_until_ns=pre + 7200_000_000_000,
        )
        result = simulation.run_case(
            "gap_premarket",
            "aggressive-v1",
            snapshot=s,
            start_ns=pre,
            bids=("10", "10", "9", "9", "9", "9", "9", "9", "9", "9", "9", "9"),
        )
        self.assertTrue(result["passed"], result)
        self.assertEqual(result["native_order_types"], ["LIMIT"])
        exits = [
            r for r in result["trace"] if r["event"] == "submit" and r["side"] == "SELL"
        ]
        self.assertTrue(exits)
        self.assertEqual(exits[0]["reason"], "stop_loss")

    def test_stale_extended_quote_flags_held_position_and_sends_no_exit(self):
        pre = int(datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc).timestamp() * 1e9)
        s = replace(
            simulation.fixture_snapshot(),
            ts_event=pre - 600_000_000_000,
            ts_init=pre - 600_000_000_000,
            valid_until_ns=pre + 7200_000_000_000,
        )
        # Quotes stop after an entry fill. The watchdog reaches the forced
        # deadline without a fresh execution quote, and must retain the residual.
        result = simulation.run_case(
            "gap_premarket",
            "aggressive-v1",
            snapshot=s,
            start_ns=pre,
            bids=("10", "10"),
            spec_overrides={"exit_deadline_ns": pre + 5_000_000_000},
            advance_to_ns=pre + 12_000_000_000,
        )
        self.assertTrue(float(result["owned_quantity"]) > 0, result)
        self.assertIn("held_quote_stale", result["flags"])
        self.assertFalse(
            any(r["event"] == "submit" and r["side"] == "SELL" for r in result["trace"])
        )

    def test_replay_is_deterministic_and_no_trade_control_is_independent(self):
        first = simulation.run_case("momentum_breakout")
        second = simulation.run_case("momentum_breakout")
        self.assertEqual(first["fixture_sha256"], second["fixture_sha256"])
        self.assertEqual(first["trace_sha256"], second["trace_sha256"])
        none = simulation.run_case("control_no_trade")
        self.assertEqual(none["orders"], 0)
        self.assertTrue(none["passed"])


if __name__ == "__main__":
    unittest.main()
