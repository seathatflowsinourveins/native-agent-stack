"""T22 engine acceptance and order-state inverse checks; synthetic inputs only."""

from __future__ import annotations

import asyncio
import importlib
import importlib.util
import json
import re
import tempfile
import time
import unittest
from contextlib import ExitStack, contextmanager
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

contracts = importlib.import_module("blueprints.us-equities.strategies.contracts")
presets = importlib.import_module("blueprints.us-equities.strategies.presets")
NATIVE = importlib.util.find_spec("nautilus_trader") is not None
if NATIVE:
    families = importlib.import_module("blueprints.us-equities.strategies.families")
    simulation = importlib.import_module("blueprints.us-equities.strategies.simulation")


@contextmanager
def synthetic_rth_context():
    """Declare the LiveNode fixture's market session independently of today.

    Event/quote timestamps still come from the registered native engine clock.
    Only the external calendar boundary is a synthetic RTH scenario; the native
    engine, callbacks, risk engine and FakePort order lifecycle remain real.
    """
    sessions = families._sessions
    anchor = datetime(2026, 10, 8, 13, 35, tzinfo=timezone.utc)
    info = sessions.session_at(anchor)

    def session_at(ts):
        return replace(
            info,
            session_date=ts.astimezone(sessions.NY).date(),
            open=ts + (info.open - anchor),
            close=ts + (info.close - anchor),
            next_open=ts + (info.next_open - anchor),
        )

    # The reused adapter exposes a supported local import as well as the
    # package module; both must see this same explicit synthetic scenario.
    modules = [sessions, importlib.import_module("sessions")]
    with ExitStack() as stack:
        for module in {id(m): m for m in modules}.values():
            stack.enter_context(
                patch.object(module, "session_at", side_effect=session_at)
            )
        yield


@contextmanager
def synthetic_native_status_context():
    """Supply declared native statuses to the synthetic LiveNode data client.

    rc5 requires a client implementation for status subscriptions. This fixture
    publishes a real native TRADING event through the upstream client output;
    it does not qualify the shared adapter's broker trading-status stream.
    """
    from nautilus_trader.model import InstrumentStatus, MarketStatusAction

    adapter = importlib.import_module(
        "blueprints.us-equities.adaptive-paper.native_adapter"
    )

    class StatusFixtureClient(adapter.AlpacaDataClient):
        async def _subscribe_instrument_status(self, command):
            if command.instrument_id not in {
                instrument.id for instrument in self.session.instruments.values()
            }:
                raise ValueError("unknown_status_fixture_instrument")
            now = self.clock.timestamp_ns()
            self._handle_data(
                InstrumentStatus(
                    command.instrument_id,
                    MarketStatusAction.TRADING,
                    now,
                    now,
                    is_trading=True,
                )
            )

    with patch.object(adapter, "AlpacaDataClient", StatusFixtureClient):
        yield


class ContractTests(unittest.TestCase):
    def test_owner_override_is_dated_attributed_history(self):
        root = Path(__file__).resolve().parents[1]
        receipt = json.loads(
            (
                root / "blueprints/us-equities/strategies/vectorbt-acceptance.json"
            ).read_text()
        )
        override = receipt["owner_override"]
        self.assertTrue(
            "instruction" not in override, "owner direction must be attributed history"
        )
        self.assertEqual(override["attribution"], "owner")
        self.assertIn(override["dispatch_at"], override["paraphrase"])
        self.assertIn("they", override["paraphrase"])
        self.assertIn("Nautilus", override["paraphrase"])

    def test_correction_records_bind_pinned_source_lines_and_first_hand_results(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "blueprints/us-equities/strategies/source-review.md").read_text()
        section = text.split("## Codex correction at 45ebe5c4", 1)[1]
        for thread in ("4235547318", "4235547324", "4235547328"):
            with self.subTest(thread=thread):
                start = section.index("Comment " + thread)
                correction = section[start:].split("\n\n", 1)[0]
                self.assertRegex(
                    correction,
                    r"https://github\.com/[^\s)]+/blob/[0-9a-f]{40}/[^\s)]+#L\d+",
                )
        self.assertIn("native-before.log", section)
        self.assertIn("native-after.log", section)
        self.assertIn("upstream-source-captures", section)
        clock_record = text.split("Clock primary sources", 1)[1].split("\n\n", 1)[0]
        for mechanism in (
            "crates/common/src/python/clock.rs",
            "crates/live/src/python/node.rs",
            "crates/system/src/python/registration.rs",
            "crates/system/src/trader.rs",
        ):
            with self.subTest(clock_mechanism=mechanism):
                self.assertRegex(
                    clock_record,
                    r"https://github\.com/nautechsystems/nautilus_trader/blob/"
                    r"1b0a49d2792a9432a3aca3fcb617ce7a630d905e/"
                    + re.escape(mechanism)
                    + r"#L\d+",
                )
        heading = "## Native instrument-status correction after 79a17b21"
        self.assertIn(heading, text)
        status_record = text.split(heading, 1)[1]
        for mechanism in (
            "python/nautilus_trader/model/__init__.pyi",
            "python/nautilus_trader/trading/__init__.pyi",
            "crates/trading/src/python/strategy.rs",
            "crates/model/src/enums.rs",
            "python/nautilus_trader/live/clients.py",
            "examples/live/_template/data.py",
        ):
            with self.subTest(status_mechanism=mechanism):
                self.assertRegex(
                    status_record,
                    r"https://github\.com/nautechsystems/nautilus_trader/blob/"
                    r"1b0a49d2792a9432a3aca3fcb617ce7a630d905e/"
                    + re.escape(mechanism)
                    + r"#L\d+",
                )
        for evidence in (
            "native-status-before.log",
            "native-consolidated-executions.json",
            "native-status-source-captures/SOURCE.json",
        ):
            self.assertIn(evidence, status_record)

    def test_live_lazy_import_comment_locators_include_the_cited_blocks(self):
        root = Path(__file__).resolve().parents[1]
        source = (
            (root / "tools/sota-convergence/blind_checkout.py").read_text().splitlines()
        )
        locations = (
            (
                "blueprints/runtime-workers/openhands/resolver/patch_policy.py",
                "imported lazily:",
            ),
            (
                "tests/test_runtime_worker_openhands_resolver.py",
                "# As tools/sota-convergence/",
            ),
            (
                "tests/test_runtime_worker_openhands_resolver.py",
                "# A loaded file that puts",
            ),
        )
        for path, marker in locations:
            comment = next(
                line
                for line in (root / path).read_text().splitlines()
                if marker in line
            )
            refs = re.search(r"blind_checkout\.py:([0-9,\-]+)", comment).group(1)
            for locator in refs.split(","):
                first, _, last = locator.partition("-")
                start, end = int(first), int(last or first)
                with self.subTest(path=path, locator=locator):
                    snippet = "\n".join(source[start - 1 : end])
                    self.assertIn("sys.path.insert", snippet)
                    self.assertRegex(snippet, r"from \w+ import ")

    def test_instance_identity_is_explicit_stable_and_bounded(self):
        for value in ("", "a-b", "x" * 65, None, True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                contracts.StrategySpec("SPY.ALPACA", "1" * 64, instance_id=value)
        self.assertEqual(
            contracts.StrategySpec("SPY.ALPACA", "1" * 64).instance_id, "default"
        )

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
            exit_policy="regular-close-v1",
            exit_evidence_sha256="3" * 64,
        )
        self.assertEqual(accepted.evidence_class, "development")

    def test_measured_exit_candidates_are_registered_and_development_binds_evidence(
        self,
    ):
        spec = contracts.StrategySpec("T22.ALPACA", "1" * 64)
        for policy in presets.EXIT_POLICIES:
            with self.subTest(policy=policy):
                candidate = replace(spec, exit_policy=policy)
                resolved = presets.preset_for(
                    candidate.preset, "trend_new_highs", exit_policy=policy
                )
                self.assertEqual(resolved.exit_policy.version, policy)
                self.assertEqual(resolved.max_sessions, 2 if resolved.overnight else 1)
        with self.assertRaisesRegex(ValueError, "unregistered_exit_policy"):
            replace(spec, exit_policy="model-selected")
        with self.assertRaises(TypeError):
            presets.EXIT_POLICIES["overnight-v1"] = None
        for policy, evidence in ((None, "3" * 64), ("overnight-v1", None)):
            with self.assertRaisesRegex(
                ValueError, "measured_exit_policy_and_evidence"
            ):
                replace(
                    spec,
                    evidence_class="development",
                    qualified_data=("released_development", "horizon_qualified"),
                    exit_deadline_ns=contracts.DEVELOPMENT_CUTOFF_NS - 1,
                    exit_policy=policy,
                    exit_evidence_sha256=evidence,
                )
        with self.assertRaisesRegex(ValueError, "exit_evidence_hash_required"):
            replace(
                spec, exit_policy="overnight-v1", exit_evidence_sha256="not-evidence"
            )

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
    def test_option_and_currency_instruments_cannot_start_equity_family(self):
        from nautilus_trader.model import (
            AssetClass,
            Currency,
            CurrencyPair,
            InstrumentId,
            OptionContract,
            OptionKind,
            Price,
            Quantity,
            Symbol,
        )

        common = {
            "instrument_id": InstrumentId.from_str(simulation.INSTRUMENT_ID),
            "raw_symbol": Symbol("TST"),
            "price_precision": 4,
            "price_increment": Price.from_str("0.0001"),
            "lot_size": Quantity.from_int(1),
            "ts_event": 0,
            "ts_init": 0,
        }
        # Both share the declared symbol/venue with the valid equity fixture:
        # symbol naming and option-underlying asset_class cannot bypass the gate.
        option = OptionContract(
            **common,
            currency=Currency.from_str("USD"),
            asset_class=AssetClass.EQUITY,
            underlying="TST",
            option_kind=OptionKind.CALL,
            multiplier=Quantity.from_int(100),
            strike_price=Price.from_str("10.0000"),
            activation_ns=0,
            expiration_ns=simulation.BASE_NS + 86400_000_000_000,
        )
        currency = CurrencyPair(
            **common,
            base_currency=Currency.from_str("EUR"),
            quote_currency=Currency.from_str("USD"),
            size_precision=0,
            size_increment=Quantity.from_int(1),
        )
        factory = simulation.fixture_engine
        for instrument in (option, currency):
            with self.subTest(instrument=type(instrument).__name__):
                with patch.object(
                    simulation, "fixture_engine", return_value=factory(instrument)
                ):
                    result = simulation.run_case("gap_premarket")
                self.assertEqual(result["orders"], 0)
                self.assertEqual(result["callback_faults"], [])
                self.assertIn("equity_instrument_required", result["flags"])

    def test_measured_deadlines_use_shared_calendar_early_close_holiday_and_dst(self):
        def stamp(value):
            return int(datetime.fromisoformat(value).timestamp() * 1_000_000_000)

        cases = (
            # Thanksgiving Friday: native early RTH close; weekend and DST
            # conversion are inherited from the existing XNYS session helper.
            (
                "2026-11-27T15:00:00+00:00",
                (
                    "2026-11-27T17:58:00+00:00",
                    "2026-11-28T00:58:00+00:00",
                    "2026-11-30T08:58:00+00:00",
                    "2026-11-30T14:28:00+00:00",
                ),
            ),
            # Friday before US DST ends: the following PRE uses UTC-5.
            (
                "2026-10-30T14:00:00+00:00",
                (
                    "2026-10-30T19:58:00+00:00",
                    "2026-10-30T23:58:00+00:00",
                    "2026-11-02T08:58:00+00:00",
                    "2026-11-02T14:28:00+00:00",
                ),
            ),
            # Independence Day observed Friday: Thursday's next session Monday.
            (
                "2026-07-02T14:00:00+00:00",
                (
                    "2026-07-02T19:58:00+00:00",
                    "2026-07-02T23:58:00+00:00",
                    "2026-07-06T07:58:00+00:00",
                    "2026-07-06T13:28:00+00:00",
                ),
            ),
        )
        tags = set()
        for entered, boundaries in cases:
            for policy, expected in zip(presets.EXIT_POLICIES, boundaries, strict=True):
                with self.subTest(entered=entered, policy=policy):
                    spec = contracts.StrategySpec(
                        simulation.INSTRUMENT_ID,
                        simulation.COHORT_SHA256,
                        exit_policy=policy,
                    )
                    strategy = families.TrendNewHighsStrategy(spec)
                    self.assertEqual(
                        strategy._holding_deadline(stamp(entered)), stamp(expected)
                    )
                    tags.add(strategy.instance_tag)
        self.assertEqual(len(tags), 4)
        base = contracts.StrategySpec(
            simulation.INSTRUMENT_ID, simulation.COHORT_SHA256
        )
        self.assertNotIn(families.TrendNewHighsStrategy(base).instance_tag, tags)
        first = families.TrendNewHighsStrategy(
            replace(base, exit_policy="overnight-v1")
        )
        second = families.TrendNewHighsStrategy(
            replace(base, exit_policy="overnight-v1")
        )
        self.assertEqual(first.instance_tag, second.instance_tag)

    def test_all_measured_exit_candidates_run_in_native_engine(self):
        for policy in presets.EXIT_POLICIES:
            for family in families.FAMILIES:
                with self.subTest(policy=policy, family=family):
                    result = simulation.run_case(
                        family, spec_overrides={"exit_policy": policy}
                    )
                    self.assertTrue(result["passed"], result)
                    self.assertGreaterEqual(result["fill_callbacks"], 2)
                    self.assertEqual(result["exit_policy"], policy)

    def test_overnight_candidate_holds_and_flags_unsupported_execution_session(self):
        # A real native entry just before POST closes crosses 20:00 ET into the
        # current classifier's unsupported window with fresh execution quotes.
        start = int(
            datetime(2026, 10, 8, 23, 59, 58, tzinfo=timezone.utc).timestamp() * 1e9
        )
        snapshot = replace(
            simulation.fixture_snapshot(),
            ts_event=start - 600_000_000_000,
            ts_init=start - 600_000_000_000,
            valid_until_ns=start + 7200_000_000_000,
        )
        result = simulation.run_case(
            "gap_premarket",
            "aggressive-v1",
            start_ns=start,
            snapshot=snapshot,
            bids=("10",) * 12,
            spec_overrides={"exit_policy": "overnight-v1"},
        )
        self.assertEqual(result["callback_faults"], [])
        self.assertGreater(float(result["owned_quantity"]), 0)
        self.assertIn("closed_session_requires_handoff", result["flags"])
        self.assertFalse(
            any(r["event"] == "submit" and r["side"] == "SELL" for r in result["trace"])
        )

    def test_same_family_presets_register_together_in_BacktestEngine_and_LiveNode(self):
        adapter = importlib.import_module(
            "blueprints.us-equities.adaptive-paper.native_adapter"
        )
        fixture = importlib.import_module("tests.test_adaptive_paper_native")
        spec = contracts.StrategySpec(
            simulation.INSTRUMENT_ID, simulation.COHORT_SHA256
        )

        def instances(spec):
            return [
                families.GapPremarketStrategy(spec),
                families.GapPremarketStrategy(replace(spec, preset="aggressive-v1")),
                families.MomentumBreakoutStrategy(spec),
                families.GapPremarketStrategy(replace(spec, instance_id="second")),
            ]

        engine, instrument = simulation.fixture_engine()
        strategies = instances(spec)
        try:
            for strategy in strategies:
                engine.add_strategy(strategy)
            self.assertEqual(len({str(s.strategy_id) for s in strategies}), 4)
            self.assertEqual(len({s.config.order_id_tag for s in strategies}), 4)
            self.assertEqual(
                [str(s.strategy_id) for s in strategies],
                [str(s.config.strategy_id) for s in instances(spec)],
            )
            engine.add_data(simulation.fixture_quotes(instrument, bids=("10", "10")))
            engine.run()
            self.assertTrue(all(not s.callback_faults for s in strategies))
        finally:
            engine.dispose()

        # A single real LiveNode must accept these exact classes/presets too.
        async def exercise():
            strategies = instances(replace(spec, instrument_id="SPY.ALPACA"))
            session = adapter.build_node(
                fixture.FakePort(), [{"symbol": "SPY", "currency": "USD"}], strategies
            )

            async def stop_when_started():
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    if all(
                        s.is_running()
                        and any(row["event"] == "instrument_status" for row in s.trace)
                        for s in strategies
                    ):
                        session.stop()
                        return True
                    await asyncio.sleep(0.05)
                session.stop()
                return False

            started = asyncio.create_task(stop_when_started())
            await asyncio.wait_for(session.run_async(), timeout=8)
            return await started, strategies, session

        with synthetic_native_status_context():
            started, strategies, session = asyncio.run(exercise())
        self.assertTrue(started)
        self.assertEqual(session.errors, [])
        self.assertTrue(all(not s.callback_faults for s in strategies))

    def test_restart_ambiguous_submit_refuses_new_id_from_durable_ledger(self):
        safety = importlib.import_module("blueprints.us-equities.adaptive-paper.safety")
        spec = contracts.StrategySpec(
            simulation.INSTRUMENT_ID, simulation.COHORT_SHA256
        )
        seed = families.GapPremarketStrategy(spec)
        now = simulation.BASE_NS / 1e9
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.sqlite3"
            ledger = safety.Ledger(path)
            try:
                ledger.start_trial(now)
                first = seed.client_id_prefix + "0000007"
                ledger.reserve_intent(
                    first,
                    "TST",
                    "buy",
                    "1",
                    "10.03",
                    quote=safety.Quote("TST", "10", "10.01", now),
                    now=now,
                    market_open=True,
                    session_close=now + 3600,
                    stop_file=Path(directory) / "unused-stop-fixture",
                )
                self.assertEqual(ledger.request_budget(now, "submit", first), 0)
            finally:
                ledger.close()
            ledger = safety.Ledger(path)
            try:
                self.assertTrue(ledger.intents()[0].submit_attempted)
                result = simulation.run_case("gap_premarket", ledger=ledger)
                self.assertEqual(result["orders"], 0, result)
                self.assertIn(
                    "startup_unresolved_intent_requires_reconciliation", result["flags"]
                )
                self.assertEqual([i.client_id for i in ledger.intents()], [first])
            finally:
                ledger.close()

    def test_ambiguous_LiveNode_submit_journals_id_then_restart_sends_nothing(self):
        adapter = importlib.import_module(
            "blueprints.us-equities.adaptive-paper.native_adapter"
        )
        safety = importlib.import_module("blueprints.us-equities.adaptive-paper.safety")
        fixture = importlib.import_module("tests.test_adaptive_paper_native")
        cohort = contracts.digest(
            {"fixture": "t22-ambiguous-restart", "members": ["SPY.ALPACA"]}
        )
        spec = contracts.StrategySpec(
            "SPY.ALPACA", cohort, preset="aggressive-v1", max_quantity=1
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.sqlite3"
            ledger = safety.Ledger(path)

            async def attempt(ambiguous):
                port = fixture.FakePort("unknown" if ambiguous else "fills")
                probe = families.NoTradeStrategy(
                    contracts.StrategySpec(
                        "SPY.ALPACA", cohort, instance_id="clock_fixture"
                    )
                )
                session = adapter.build_node(
                    port, [{"symbol": "SPY", "currency": "USD"}], [probe]
                )
                strategy = families.GapPremarketStrategy(spec, ledger=ledger)
                session.node.add_strategy(strategy)
                now = strategy.clock.timestamp_ns()
                if ambiguous:
                    ledger.start_trial(now / 1e9)
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
                )
                original_start, original_submit = port.start, port.submit

                async def start(on_quote, on_order):
                    strategy.on_data(snapshot)
                    await original_start(on_quote, on_order)

                async def submit(payload):
                    # Synthetic wire seam uses the unchanged durable governor:
                    # reserve and journal the explicit native ID before send.
                    observed = strategy.clock.timestamp_ns() / 1e9
                    ledger.reserve_intent(
                        payload["client_order_id"],
                        "SPY",
                        payload["side"],
                        payload["qty"],
                        payload["limit_price"],
                        quote=safety.Quote("SPY", "100", "100.01", observed),
                        now=observed,
                        market_open=True,
                        session_close=observed + 3600,
                        stop_file=Path(directory) / "unused-stop-fixture",
                    )
                    self.assertEqual(
                        ledger.request_budget(
                            observed, "submit", payload["client_order_id"]
                        ),
                        0,
                    )
                    return await original_submit(payload)

                port.start, port.submit = start, submit
                strategy.fault_sink = session.fail

                async def stop_when_resolved():
                    for _ in range(100):
                        if session.errors or strategy.flags:
                            session.stop()
                            return
                        await asyncio.sleep(0.05)
                    session.stop()

                waiter = asyncio.create_task(stop_when_resolved())
                await asyncio.wait_for(session.run_async(), timeout=8)
                await waiter
                return strategy, port, session

            try:
                with synthetic_rth_context(), synthetic_native_status_context():
                    first, port, session = asyncio.run(attempt(True))
                self.assertEqual(len(port.submissions), 1, first.trace)
                self.assertTrue(session.errors)
                original_id = port.submissions[0]["client_order_id"]
                self.assertEqual(original_id, first.client_id_prefix + "0000001")
                self.assertTrue(ledger.intents()[0].submit_attempted)
                ledger.close()
                ledger = safety.Ledger(path)
                with synthetic_rth_context(), synthetic_native_status_context():
                    restarted, port, session = asyncio.run(attempt(False))
                self.assertEqual(port.submissions, [])
                self.assertIn(
                    "startup_unresolved_intent_requires_reconciliation", restarted.flags
                )
                self.assertEqual(restarted.sequence, 1)
                self.assertEqual([i.client_id for i in ledger.intents()], [original_id])
            finally:
                ledger.close()

    def test_restored_sequence_and_existing_position_prevent_restart_entry(self):
        safety = importlib.import_module("blueprints.us-equities.adaptive-paper.safety")
        spec = contracts.StrategySpec(
            simulation.INSTRUMENT_ID, simulation.COHORT_SHA256
        )
        seed = families.GapPremarketStrategy(spec)
        now = simulation.BASE_NS / 1e9
        with tempfile.TemporaryDirectory() as directory:
            ledger = safety.Ledger(Path(directory) / "ledger.sqlite3")
            try:
                ledger.start_trial(now)
                for seq in (2, 7):
                    cid = seed.client_id_prefix + f"{seq:07d}"
                    ledger.reserve_intent(
                        cid,
                        "TST",
                        "buy",
                        "1",
                        "10.03",
                        quote=safety.Quote("TST", "10", "10.01", now),
                        now=now,
                        market_open=True,
                        session_close=now + 3600,
                        stop_file=Path(directory) / "unused-stop-fixture",
                    )
                    ledger.mark_not_sent(cid, "synthetic_pre_wire_refusal")
                # An older/other lineage's real position for this symbol also
                # blocks startup, even though its client prefix differs.
                ledger.reserve_intent(
                    "other-lineage-1",
                    "TST",
                    "buy",
                    "1",
                    "10.03",
                    quote=safety.Quote("TST", "10", "10.01", now),
                    now=now,
                    market_open=True,
                    session_close=now + 3600,
                    stop_file=Path(directory) / "unused-stop-fixture",
                )
                ledger.record_order(
                    "other-lineage-1",
                    "synthetic-venue-1",
                    "filled",
                    "1",
                    "10.01",
                    timestamp=now,
                )
                result = simulation.run_case("gap_premarket", ledger=ledger)
                self.assertEqual(result["orders"], 0, result)
                self.assertIn(
                    "startup_position_requires_reconciliation", result["flags"]
                )
                self.assertEqual(result["sequence"], 7)
            finally:
                ledger.close()

    def test_client_ids_are_stable_across_engine_clock_changes(self):
        first = simulation.run_case("gap_premarket")
        later = simulation.run_case(
            "gap_premarket", start_ns=simulation.BASE_NS + 60_000_000_000
        )
        ids = lambda result: [
            r["client_order_id"] for r in result["trace"] if r["event"] == "submit"
        ]
        self.assertTrue(first["passed"] and later["passed"])
        self.assertGreaterEqual(len(ids(first)), 2)
        self.assertEqual(ids(first), ids(later))

    def test_same_family_classes_use_real_LiveNode_and_owned_partial_fills(self):
        fixture = importlib.import_module("tests.test_adaptive_paper_native")
        adapter = importlib.import_module(
            "blueprints.us-equities.adaptive-paper.native_adapter"
        )
        for name, cls in families.FAMILIES.items():
            with self.subTest(family=name):

                async def exercise(strategy_class=cls):
                    port = fixture.FakePort()
                    cohort = contracts.digest(
                        {"fixture": "t22-live-port", "members": ["SPY.ALPACA"]}
                    )
                    probe = families.NoTradeStrategy(
                        contracts.StrategySpec(
                            "SPY.ALPACA", cohort, instance_id="clock_fixture"
                        )
                    )
                    session = adapter.build_node(
                        port, [{"symbol": "SPY", "currency": "USD"}], [probe]
                    )
                    now = probe.clock.timestamp_ns()
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
                    session.node.add_strategy(strategy)
                    now = strategy.clock.timestamp_ns()
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
                                        "ts_ns": strategy.clock.timestamp_ns(),
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

                with synthetic_rth_context(), synthetic_native_status_context():
                    port, strategy, session = asyncio.run(exercise())
                self.assertEqual(session.errors, [], session.errors)
                self.assertEqual(strategy.callback_faults, [])
                self.assertTrue(
                    any(
                        row["event"] == "instrument_status"
                        and row["action"] == "TRADING"
                        for row in strategy.trace
                    )
                )
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
