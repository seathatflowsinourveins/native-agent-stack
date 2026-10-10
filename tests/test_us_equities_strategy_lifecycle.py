"""Native regression seams for T22 order lifecycle, durable safety and clocks."""

from __future__ import annotations

import importlib
import importlib.util
import tempfile
import time
import unittest
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

NATIVE = importlib.util.find_spec("nautilus_trader") is not None
if NATIVE:
    simulation = importlib.import_module("blueprints.us-equities.strategies.simulation")
    contracts = importlib.import_module("blueprints.us-equities.strategies.contracts")
    families = importlib.import_module("blueprints.us-equities.strategies.families")
    safety = importlib.import_module("blueprints.us-equities.adaptive-paper.safety")


def run_strategy(
    *,
    ledger,
    faults,
    instrument=None,
    bids=None,
    overrides=None,
    advance_to_ns=None,
    start_ns=None,
    halt_after_ns=None,
    reopen_at_ns=None,
    strategy_type=None,
    quote_offsets_ns=None,
):
    """Drive the real class through native data/clock/callback boundaries."""
    from nautilus_trader.model import CustomData, QuoteTick

    engine, instrument = simulation.fixture_engine(instrument)
    start_ns = simulation.BASE_NS if start_ns is None else start_ns
    fields = {
        "entry_timeout_ns": 2_000_000_000,
        "exit_timeout_ns": 2_000_000_000,
        "exit_deadline_ns": start_ns + 8_000_000_000,
    }
    fields.update(overrides or {})
    spec = replace(
        contracts.StrategySpec(simulation.INSTRUMENT_ID, simulation.COHORT_SHA256),
        **fields,
    )
    strategy = (strategy_type or families.GapPremarketStrategy)(
        spec, ledger=ledger, fault_sink=faults.append
    )
    snapshot = replace(
        simulation.fixture_snapshot(),
        ts_event=start_ns - 600_000_000_000,
        ts_init=start_ns - 600_000_000_000,
        valid_until_ns=start_ns + 3600_000_000_000,
    )
    quotes = simulation.fixture_quotes(
        instrument, start_ns=start_ns, **({"bids": bids} if bids is not None else {})
    )
    if quote_offsets_ns is not None:
        if len(quote_offsets_ns) != len(quotes):
            raise ValueError("one_timestamp_per_quote_required")
        quotes = [
            QuoteTick(
                quote.instrument_id,
                quote.bid_price,
                quote.ask_price,
                quote.bid_size,
                quote.ask_size,
                start_ns + offset,
                start_ns + offset,
            )
            for quote, offset in zip(quotes, quote_offsets_ns, strict=True)
        ]
    data = [
        CustomData(families.snapshot_data_type(simulation.INSTRUMENT_ID), snapshot),
        *quotes,
    ]
    if advance_to_ns is not None:
        data.append(
            CustomData(
                families.snapshot_data_type(simulation.INSTRUMENT_ID),
                replace(snapshot, ts_event=advance_to_ns, ts_init=advance_to_ns),
            )
        )
    if halt_after_ns is not None:
        data.append(
            CustomData(
                families.snapshot_data_type(simulation.INSTRUMENT_ID),
                replace(
                    snapshot, ts_event=halt_after_ns, ts_init=halt_after_ns, halted=True
                ),
            )
        )
    if reopen_at_ns is not None:
        data.append(
            CustomData(
                families.snapshot_data_type(simulation.INSTRUMENT_ID),
                replace(snapshot, ts_event=reopen_at_ns, ts_init=reopen_at_ns),
            )
        )
    try:
        engine.add_strategy(strategy)
        engine.add_data(data, sort=True)
        engine.run()
        return strategy
    finally:
        engine.dispose()


@unittest.skipUnless(NATIVE, "requires the exact locked Nautilus rc5 runtime")
class LifecycleTests(unittest.TestCase):
    def test_fractional_policy_boundary_dispatches_cancel_before_crossing_quote(self):
        native_cancel = families.FamilyStrategy.cancel_order
        observed = []

        def observe_cancel(strategy, client_id):
            observed.append((str(client_id), str(strategy.pending.client_order_id)))
            native_cancel(strategy, client_id)

        for policy, boundary in (
            ("regular-close-v1", "2026-10-08T19:58:00+00:00"),
            ("after-hours-v1", "2026-10-08T23:58:00+00:00"),
        ):
            cutoff = int(datetime.fromisoformat(boundary).timestamp() * 1e9)
            start = cutoff - 500_000_000
            observed.clear()
            with (
                self.subTest(policy=policy),
                patch.object(
                    families.FamilyStrategy, "cancel_order", new=observe_cancel
                ),
            ):
                strategy = run_strategy(
                    ledger=None,
                    faults=[],
                    start_ns=start,
                    bids=("10", "11", "11", "10", "10", "10"),
                    quote_offsets_ns=(
                        0,
                        200_000_000,
                        400_000_000,
                        600_000_000,
                        800_000_000,
                        1_200_000_000,
                    ),
                    overrides={
                        "preset": "aggressive-v1",
                        "exit_policy": policy,
                        "entry_timeout_ns": 10_000_000_000,
                        "exit_deadline_ns": start + 30_000_000_000,
                    },
                )
                cancels = [
                    r for r in strategy.trace if r["event"] == "cancel_requested"
                ]
                buys = [
                    r
                    for r in strategy.trace
                    if r["event"] == "submit" and r["side"] == "BUY"
                ]
                self.assertEqual(len(cancels), 1)
                self.assertEqual(cancels[0]["now_ns"], cutoff)
                self.assertEqual(cancels[0]["role"], "entry")
                self.assertEqual(len(buys), 1)
                self.assertEqual(buys[0]["now_ns"], start)
                self.assertEqual(
                    observed, [(buys[0]["client_order_id"], buys[0]["client_order_id"])]
                )
                # Native cancel latency allows this crossing fill. Dispatch at
                # the boundary must retain fill ownership and the time exit.
                fills = [r for r in strategy.trace if r["event"] == "fill"]
                self.assertEqual([r["side"] for r in fills], ["BUY", "SELL"])
                self.assertEqual(fills[0]["now_ns"], cutoff + 100_000_000)
                self.assertEqual(strategy.quantity, 0)
                self.assertIsNone(strategy.pending)
                self.assertEqual(strategy.sequence, 2)
                self.assertNotIn("t22-pending-entry", strategy.clock.timer_names())

    def test_subsecond_halt_cancels_on_acceptance_before_reopen_and_fill(self):
        start = simulation.BASE_NS
        native_terminal = families.FamilyStrategy.on_order_canceled
        retired = []

        def observe_terminal(strategy, event):
            native_terminal(strategy, event)
            retired.append((str(event.client_order_id), strategy.clock.timer_names()))

        with patch.object(
            families.FamilyStrategy, "on_order_canceled", new=observe_terminal
        ):
            strategy = run_strategy(
                ledger=None,
                faults=[],
                bids=("10", "11", "11", "10", "10", "10"),
                quote_offsets_ns=(
                    0,
                    200_000_000,
                    400_000_000,
                    600_000_000,
                    800_000_000,
                    1_200_000_000,
                ),
                halt_after_ns=start + 300_000_000,
                reopen_at_ns=start + 500_000_000,
                overrides={
                    "entry_timeout_ns": 10_000_000_000,
                    "exit_deadline_ns": start + 30_000_000_000,
                },
            )
        cancels = [r for r in strategy.trace if r["event"] == "cancel_requested"]
        terminals = [r for r in strategy.trace if r["event"] == "terminal"]
        self.assertEqual(len(cancels), 1)
        self.assertEqual(cancels[0]["now_ns"], start + 300_000_000)
        self.assertEqual(cancels[0]["role"], "entry")
        self.assertEqual(len(terminals), 1)
        self.assertEqual(terminals[0]["now_ns"], start + 400_000_000)
        self.assertFalse(any(r["event"] == "fill" for r in strategy.trace))
        self.assertEqual(strategy.quantity, 0)
        self.assertIsNone(strategy.pending)
        self.assertEqual(strategy.sequence, 1)
        self.assertNotIn("t22-pending-entry", strategy.clock.timer_names())
        self.assertEqual(len(retired), 1)
        self.assertEqual(retired[0][0], strategy.client_id_prefix + "0000001")
        self.assertNotIn("t22-pending-entry", retired[0][1])

    def test_native_alert_selects_earliest_pending_entry_limit(self):
        start = simulation.BASE_NS
        for timeout, entry, exit_, earliest in (
            (300_000_000, 350_000_000, 450_000_000, 300_000_000),
            (450_000_000, 300_000_000, 350_000_000, 300_000_000),
            (350_000_000, 450_000_000, 300_000_000, 300_000_000),
        ):
            with self.subTest(timeout=timeout, entry=entry, exit=exit_):
                strategy = run_strategy(
                    ledger=None,
                    faults=[],
                    bids=("10", "11", "11", "10", "10", "10"),
                    quote_offsets_ns=(
                        0,
                        200_000_000,
                        400_000_000,
                        600_000_000,
                        800_000_000,
                        1_200_000_000,
                    ),
                    overrides={
                        "entry_timeout_ns": timeout,
                        "entry_deadline_ns": start + entry,
                        "exit_deadline_ns": start + exit_,
                    },
                )
                cancels = [
                    r for r in strategy.trace if r["event"] == "cancel_requested"
                ]
                self.assertEqual(len(cancels), 1)
                self.assertEqual(cancels[0]["now_ns"], start + earliest)
                self.assertEqual(cancels[0]["role"], "entry")
                self.assertTrue(any(r["event"] == "terminal" for r in strategy.trace))
                self.assertFalse(any(r["event"] == "fill" for r in strategy.trace))
                self.assertEqual(strategy.quantity, 0)
                self.assertEqual(strategy.sequence, 1)

    def test_entry_deadline_cancels_before_timeout_and_preserves_terminal_identity(
        self,
    ):
        start = simulation.BASE_NS
        native_cancel = families.FamilyStrategy.cancel_order
        observed = []

        def observe_cancel(strategy, client_id):
            observed.append((str(client_id), str(strategy.pending.client_order_id)))
            native_cancel(strategy, client_id)

        with patch.object(families.FamilyStrategy, "cancel_order", new=observe_cancel):
            strategy = run_strategy(
                ledger=None,
                faults=[],
                bids=("10", "11", "11", "10", "10", "10"),
                overrides={
                    "entry_deadline_ns": start + 1_000_000_000,
                    "entry_timeout_ns": 10_000_000_000,
                    "exit_deadline_ns": start + 30_000_000_000,
                },
            )
        cancels = [r for r in strategy.trace if r["event"] == "cancel_requested"]
        self.assertEqual(len(cancels), 1)
        self.assertEqual(cancels[0]["now_ns"], start + 1_000_000_000)
        self.assertEqual(cancels[0]["role"], "entry")
        self.assertEqual(observed, [(strategy.client_id_prefix + "0000001",) * 2])
        self.assertTrue(any(r["event"] == "terminal" for r in strategy.trace))
        self.assertFalse(any(r["event"] == "fill" for r in strategy.trace))
        self.assertIsNone(strategy.pending)
        self.assertEqual(strategy.quantity, 0)
        self.assertEqual(strategy.sequence, 1)

    def test_entry_deadline_admits_only_before_boundary(self):
        cutoff = simulation.BASE_NS + 2_000_000_000
        for offset in (-500_000_000, 0, 500_000_000):
            with self.subTest(offset_ns=offset):
                strategy = run_strategy(
                    ledger=None,
                    faults=[],
                    start_ns=cutoff + offset,
                    bids=("10", "11", "11", "11", "11"),
                    quote_offsets_ns=(
                        0,
                        200_000_000,
                        400_000_000,
                        600_000_000,
                        800_000_000,
                    ),
                    overrides={
                        "entry_deadline_ns": cutoff,
                        "entry_timeout_ns": 10_000_000_000,
                        "exit_deadline_ns": cutoff + 30_000_000_000,
                    },
                )
                buys = [
                    r
                    for r in strategy.trace
                    if r["event"] == "submit" and r["side"] == "BUY"
                ]
                self.assertEqual(len(buys), int(offset < 0))
                self.assertFalse(any(r["event"] == "fill" for r in strategy.trace))
                self.assertEqual(strategy.quantity, 0)

    def test_exit_deadline_cancels_pending_entry_before_ordinary_timeout(self):
        start = simulation.BASE_NS
        strategy = run_strategy(
            ledger=None,
            faults=[],
            bids=("10", "11", "11", "10", "10", "10"),
            overrides={
                "entry_timeout_ns": 10_000_000_000,
                "exit_deadline_ns": start + 1_000_000_000,
            },
        )
        cancels = [r for r in strategy.trace if r["event"] == "cancel_requested"]
        self.assertEqual(len(cancels), 1)
        self.assertEqual(cancels[0]["now_ns"], start + 1_000_000_000)
        self.assertEqual(cancels[0]["role"], "entry")
        self.assertFalse(any(r["event"] == "fill" for r in strategy.trace))
        self.assertTrue(any(r["event"] == "terminal" for r in strategy.trace))
        self.assertEqual(strategy.quantity, 0)
        self.assertEqual(strategy.sequence, 1)

    def test_exit_deadline_cancels_pending_exit_before_ordinary_timeout(self):
        start = simulation.BASE_NS
        strategy = run_strategy(
            ledger=None,
            faults=[],
            bids=("10", "10", "9", "8", "8", "9", "9"),
            overrides={
                "entry_timeout_ns": 10_000_000_000,
                "exit_timeout_ns": 10_000_000_000,
                "exit_deadline_ns": start + 3_000_000_000,
            },
        )
        cancels = [r for r in strategy.trace if r["event"] == "cancel_requested"]
        self.assertEqual(len(cancels), 1)
        self.assertEqual(cancels[0]["now_ns"], start + 3_000_000_000)
        self.assertEqual(cancels[0]["role"], "exit")
        sells = [
            r for r in strategy.trace if r["event"] == "submit" and r["side"] == "SELL"
        ]
        self.assertEqual([r["reason"] for r in sells], ["stop_loss", "time_exit"])
        self.assertEqual(strategy.quantity, 0)
        self.assertEqual(strategy.sequence, 3)

    def test_policy_boundary_refuses_new_entries_at_and_after_cutoff(self):
        for policy, boundary in (
            ("regular-close-v1", "2026-10-08T19:58:00+00:00"),
            ("after-hours-v1", "2026-10-08T23:58:00+00:00"),
        ):
            cutoff = int(datetime.fromisoformat(boundary).timestamp() * 1e9)
            for offset in (-2, 0, 60):
                start = cutoff + offset * 1_000_000_000
                with self.subTest(policy=policy, offset=offset):
                    strategy = run_strategy(
                        ledger=None,
                        faults=[],
                        start_ns=start,
                        bids=("10",) * 5,
                        overrides={
                            "preset": "aggressive-v1",
                            "exit_policy": policy,
                            "exit_deadline_ns": start + 30_000_000_000,
                        },
                    )
                    buys = [
                        r
                        for r in strategy.trace
                        if r["event"] == "submit" and r["side"] == "BUY"
                    ]
                    self.assertEqual(len(buys), int(offset < 0))

    def test_resting_entry_is_cancelled_at_selected_policy_boundary(self):
        for policy, boundary in (
            ("regular-close-v1", "2026-10-08T19:58:00+00:00"),
            ("after-hours-v1", "2026-10-08T23:58:00+00:00"),
        ):
            cutoff = int(datetime.fromisoformat(boundary).timestamp() * 1e9)
            start = cutoff - 1_000_000_000
            with self.subTest(policy=policy):
                strategy = run_strategy(
                    ledger=None,
                    faults=[],
                    start_ns=start,
                    bids=("10", "11", "11", "10", "10", "10"),
                    overrides={
                        "preset": "aggressive-v1",
                        "exit_policy": policy,
                        "entry_timeout_ns": 10_000_000_000,
                        "exit_deadline_ns": start + 30_000_000_000,
                    },
                )
                cancels = [
                    r for r in strategy.trace if r["event"] == "cancel_requested"
                ]
                self.assertEqual(len(cancels), 1)
                self.assertEqual(cancels[0]["now_ns"], cutoff)
                self.assertEqual(cancels[0]["role"], "entry")
                self.assertTrue(any(r["event"] == "terminal" for r in strategy.trace))
                self.assertFalse(any(r["event"] == "fill" for r in strategy.trace))
                self.assertEqual(strategy.quantity, 0)
                self.assertEqual(strategy.sequence, 1)

    def test_halt_cancels_entry_and_keeps_identity_until_native_terminal(self):
        native_cancel = families.FamilyStrategy.cancel_order
        observed = []

        def observe_cancel(strategy, client_id):
            native_cancel(strategy, client_id)
            observed.append(
                (
                    str(client_id),
                    str(strategy.pending.client_order_id),
                    strategy.cancel_requested,
                    strategy.clock.timestamp_ns(),
                )
            )

        with patch.object(families.FamilyStrategy, "cancel_order", new=observe_cancel):
            strategy = run_strategy(
                ledger=None,
                faults=[],
                bids=("10", "11", "11", "10", "10", "10"),
                halt_after_ns=simulation.BASE_NS + 1_000_000_000,
                reopen_at_ns=simulation.BASE_NS + 3_000_000_000,
                overrides={"entry_timeout_ns": 10_000_000_000},
            )
        self.assertEqual(len(observed), 1)
        client_id, pending_id, cancel_requested, cancelled_at = observed[0]
        self.assertEqual(client_id, pending_id)
        self.assertTrue(cancel_requested)
        self.assertEqual(cancelled_at, simulation.BASE_NS + 1_000_000_000)
        self.assertTrue(any(r["event"] == "terminal" for r in strategy.trace))
        self.assertFalse(any(r["event"] == "fill" for r in strategy.trace))
        self.assertIsNone(strategy.pending)
        self.assertEqual(strategy.sequence, 1)

    def test_halt_cancel_without_ack_retains_original_entry_identity(self):
        requested = []

        def drop_cancel_ack(strategy, client_id):
            requested.append((str(client_id), strategy.clock.timestamp_ns()))

        with patch.object(families.FamilyStrategy, "cancel_order", new=drop_cancel_ack):
            faults = []
            strategy = run_strategy(
                ledger=None,
                faults=faults,
                bids=("10",) + ("11",) * 7,
                halt_after_ns=simulation.BASE_NS + 1_000_000_000,
            )
        self.assertEqual(
            requested,
            [
                (
                    strategy.client_id_prefix + "0000001",
                    simulation.BASE_NS + 1_000_000_000,
                )
            ],
        )
        self.assertEqual(str(strategy.pending.client_order_id), requested[0][0])
        self.assertEqual(strategy.sequence, 1)
        self.assertEqual(faults, ["cancel_ack_timeout_requires_reconciliation"])
        self.assertTrue(strategy.faulted)

    def test_halt_does_not_apply_entry_cancellation_to_pending_exit(self):
        faults = []
        strategy = run_strategy(
            ledger=None,
            faults=faults,
            bids=("10", "10", "9", "8", "8", "8", "10", "10"),
            halt_after_ns=simulation.BASE_NS + 3_000_000_000,
            reopen_at_ns=simulation.BASE_NS + 6_000_000_000,
            overrides={"exit_deadline_ns": simulation.BASE_NS + 2_000_000_000},
        )
        sells = [
            r for r in strategy.trace if r["event"] == "submit" and r["side"] == "SELL"
        ]
        self.assertEqual(len(sells), 1)
        self.assertEqual(sells[0]["now_ns"], simulation.BASE_NS + 2_000_000_000)
        self.assertFalse(any(r["event"] == "cancel_requested" for r in strategy.trace))
        self.assertEqual(strategy.quantity, 0)
        self.assertEqual(strategy.sequence, 2)
        self.assertEqual(faults, [])

    def test_delayed_first_buy_callback_uses_native_fill_event_time(self):
        from nautilus_trader.model import OrderSide

        class DelayedFillStrategy(families.GapPremarketStrategy):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.delayed_fill = None
                self.first_fill_ns = None
                self.callback_ns = None

            def on_order_filled(self, event):
                if event.order_side == OrderSide.BUY and self.first_fill_ns is None:
                    self.first_fill_ns = event.ts_event
                    self.delayed_fill = event
                else:
                    super().on_order_filled(event)

            def on_quote(self, quote):
                if (
                    self.delayed_fill is not None
                    and quote.ts_event >= self.first_fill_ns + 2_000_000_000
                ):
                    self.callback_ns = self.clock.timestamp_ns()
                    super().on_order_filled(self.delayed_fill)
                    self.delayed_fill = None
                super().on_quote(quote)

        strategy = run_strategy(
            ledger=None,
            faults=[],
            bids=("10",) * 12,
            strategy_type=DelayedFillStrategy,
            overrides={"entry_timeout_ns": 10_000_000_000},
        )
        self.assertIsNotNone(strategy.first_fill_ns)
        self.assertGreater(strategy.callback_ns, strategy.first_fill_ns)
        self.assertEqual(strategy.entered_ns, strategy.first_fill_ns)
        self.assertEqual(
            strategy.close_deadline_ns,
            strategy._holding_deadline(strategy.first_fill_ns),
        )
        self.assertEqual(strategy.quantity, 0)
        self.assertFalse(strategy.faulted)

    def test_session_is_notified_even_when_durable_freeze_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = safety.Ledger(Path(directory) / "ledger.sqlite3")
            faults = []
            try:
                ledger.start_trial(simulation.BASE_NS / 1e9)
                with patch.object(
                    ledger,
                    "freeze",
                    side_effect=RuntimeError("synthetic_journal_failure"),
                ):
                    strategy = run_strategy(
                        ledger=ledger,
                        faults=faults,
                        overrides={"execution_profile": "native-target-v1"},
                    )
                self.assertEqual(faults, ["T15_native_order_capability_unqualified"])
                self.assertTrue(strategy.faulted)
                self.assertEqual(
                    strategy.callback_faults[0]["freeze_error"], "RuntimeError"
                )
                self.assertEqual(
                    ledger.halted_reason(), None
                )  # no false durability claim
                self.assertFalse(any(r["event"] == "submit" for r in strategy.trace))
            finally:
                ledger.close()

    def test_live_node_fixtures_do_not_depend_on_weekend_wall_clock(self):
        legacy = importlib.import_module("tests.test_us_equities_strategies")
        # Saturday noon UTC. Only the fixture module's old wall-time access is
        # replaced; the native engine and asyncio scheduler remain real.
        weekend_ns = 1791633600_000_000_000
        fixed_wall = SimpleNamespace(
            time=lambda: weekend_ns / 1e9,
            time_ns=lambda: weekend_ns,
            monotonic=time.monotonic,
        )
        for name in (
            "test_ambiguous_LiveNode_submit_journals_id_then_restart_sends_nothing",
            "test_same_family_classes_use_real_LiveNode_and_owned_partial_fills",
        ):
            with self.subTest(fixture=name), patch.object(legacy, "time", fixed_wall):
                case = legacy.NativeStrategyTests(name)
                getattr(case, name)()

    def test_unacknowledged_cancel_times_out_without_new_id(self):
        requested = []

        def drop_cancel_ack(strategy, client_id):
            requested.append((str(client_id), strategy.clock.timestamp_ns()))

        with tempfile.TemporaryDirectory() as directory:
            ledger = safety.Ledger(Path(directory) / "ledger.sqlite3")
            faults = []
            try:
                ledger.start_trial(simulation.BASE_NS / 1e9)
                with patch.object(
                    families.FamilyStrategy, "cancel_order", new=drop_cancel_ack
                ):
                    strategy = run_strategy(
                        ledger=ledger, faults=faults, bids=("10",) + ("11",) * 11
                    )
                self.assertEqual(
                    ledger.halted_reason(), "cancel_ack_timeout_requires_reconciliation"
                )
                self.assertEqual(faults, ["cancel_ack_timeout_requires_reconciliation"])
                self.assertEqual(len(requested), 1)
                self.assertEqual(strategy.sequence, 1)
                freezes = [r for r in strategy.trace if r["event"] == "safety_freeze"]
                self.assertEqual(freezes[0]["now_ns"], requested[0][1] + 2_000_000_000)
            finally:
                ledger.close()

    def test_terminal_entry_is_consumed_without_other_startup_refusal(self):
        spec = contracts.StrategySpec(
            simulation.INSTRUMENT_ID, simulation.COHORT_SHA256
        )
        seed = families.GapPremarketStrategy(spec)
        client_id = seed.client_id_prefix + "0000001"
        now = simulation.BASE_NS / 1e9
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.sqlite3"
            ledger = safety.Ledger(path)
            try:
                ledger.start_trial(now)
                ledger.reserve_intent(
                    client_id,
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
                ledger.mark_not_sent(client_id, "synthetic_pre_wire_refusal")
            finally:
                ledger.close()
            ledger = safety.Ledger(path)
            faults = []
            try:
                self.assertEqual(ledger.halted_reason(), None)
                self.assertEqual(ledger.unresolved(), [])
                self.assertEqual(ledger.positions(), {})
                strategy = run_strategy(ledger=ledger, faults=faults, bids=("10",) * 12)
                self.assertEqual(strategy.sequence, 1)  # far below exhaustion
                self.assertFalse(strategy.faulted)
                self.assertEqual(faults, [])
                self.assertIn("prior_entry_attempt_restored", strategy.flags)
                self.assertFalse(any(r["event"] == "submit" for r in strategy.trace))
                # Only the explicitly new trial identity changes. Its positive
                # entry proves no other silent refusal made the first pass.
                control = run_strategy(
                    ledger=ledger,
                    faults=[],
                    bids=("10",) * 12,
                    overrides={"instance_id": "new_trial"},
                )
                self.assertTrue(
                    any(
                        r["event"] == "submit" and r["side"] == "BUY"
                        for r in control.trace
                    )
                )
            finally:
                ledger.close()

    def test_native_cancel_rejection_escalates_without_replacement(self):
        from nautilus_trader.core import UUID4
        from nautilus_trader.model import OrderCancelRejected, TraderId

        observed = []

        def reject_cancel(strategy, client_id):
            event = OrderCancelRejected(
                trader_id=TraderId("TRADER-001"),
                strategy_id=strategy.strategy_id,
                instrument_id=strategy.instrument_id,
                client_order_id=client_id,
                reason="synthetic_cancel_refusal",
                event_id=UUID4(),
                ts_event=strategy.clock.timestamp_ns(),
                ts_init=strategy.clock.timestamp_ns(),
                reconciliation=False,
            )
            handler = getattr(strategy, "on_order_cancel_rejected", None)
            if handler is not None:
                handler(event)
            observed.append((str(client_id), strategy.pending is not None))

        with tempfile.TemporaryDirectory() as directory:
            ledger = safety.Ledger(Path(directory) / "ledger.sqlite3")
            faults = []
            try:
                ledger.start_trial(simulation.BASE_NS / 1e9)
                with patch.object(
                    families.FamilyStrategy, "cancel_order", new=reject_cancel
                ):
                    strategy = run_strategy(
                        ledger=ledger, faults=faults, bids=("10",) + ("11",) * 11
                    )
                self.assertEqual(
                    ledger.halted_reason(),
                    "native_cancel_rejected_requires_reconciliation",
                )
                self.assertEqual(
                    faults, ["native_cancel_rejected_requires_reconciliation"]
                )
                self.assertEqual(
                    observed, [(strategy.client_id_prefix + "0000001", True)]
                )
                self.assertEqual(strategy.sequence, 1)
            finally:
                ledger.close()

    def test_restart_never_enters_when_durable_halt_exists_without_exposure(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.sqlite3"
            ledger = safety.Ledger(path)
            ledger.start_trial(simulation.BASE_NS / 1e9)
            ledger.freeze("prior_safety_halt")
            ledger.close()
            reopened = safety.Ledger(path)
            faults = []
            try:
                self.assertEqual(reopened.unresolved(), [])
                self.assertEqual(reopened.positions(), {})
                strategy = run_strategy(
                    ledger=reopened, faults=faults, bids=("10",) * 12
                )
                self.assertFalse(any(r["event"] == "submit" for r in strategy.trace))
                self.assertIn("startup_ledger_halted_requires_reconciliation", faults)
                self.assertEqual(reopened.halted_reason(), "prior_safety_halt")
            finally:
                reopened.close()

    def test_held_hazards_persist_and_escalate_without_new_exit(self):
        from datetime import datetime, timezone

        closed = int(
            datetime(2026, 10, 8, 23, 59, 58, tzinfo=timezone.utc).timestamp() * 1e9
        )
        cases = (
            (
                "held_quote_stale",
                {
                    "bids": ("10", "10"),
                    "advance_to_ns": simulation.BASE_NS + 12_000_000_000,
                },
            ),
            (
                "held_halted",
                {
                    "bids": ("10",) * 12,
                    "halt_after_ns": simulation.BASE_NS + 3_000_000_000,
                },
            ),
            (
                "closed_session_requires_handoff",
                {
                    "bids": ("10",) * 12,
                    "start_ns": closed,
                    "overrides": {
                        "preset": "aggressive-v1",
                        "exit_policy": "overnight-v1",
                    },
                },
            ),
            (
                "exit_budget_exhausted_requires_handoff",
                {
                    "bids": (
                        "10",
                        "10",
                        "10",
                        "10",
                        "9",
                        "8",
                        "7",
                        "6",
                        "5",
                        "4",
                        "3",
                        "2",
                    ),
                    "overrides": {
                        "max_exit_orders": 1,
                        "exit_deadline_ns": simulation.BASE_NS + 3_000_000_000,
                    },
                },
            ),
        )
        for reason, kwargs in cases:
            with (
                self.subTest(reason=reason),
                tempfile.TemporaryDirectory() as directory,
            ):
                path = Path(directory) / "ledger.sqlite3"
                ledger = safety.Ledger(path)
                faults = []
                try:
                    ledger.start_trial(simulation.BASE_NS / 1e9)
                    strategy = run_strategy(ledger=ledger, faults=faults, **kwargs)
                    self.assertGreater(strategy.quantity, 0)
                    self.assertEqual(ledger.halted_reason(), reason)
                    self.assertIn(reason, faults)
                    sells = [
                        r
                        for r in strategy.trace
                        if r["event"] == "submit" and r["side"] == "SELL"
                    ]
                    self.assertEqual(
                        len(sells),
                        1 if reason == "exit_budget_exhausted_requires_handoff" else 0,
                    )
                finally:
                    ledger.close()
                reopened = safety.Ledger(path)
                try:
                    self.assertEqual(reopened.halted_reason(), reason)
                finally:
                    reopened.close()

    def test_missing_instrument_startup_escalates_and_survives_ledger_reopen(self):
        faults = []
        factory = simulation.fixture_engine

        def missing_instrument(_=None):
            engine, instrument = factory()
            # The actor declares a different valid identifier. Do not register
            # it, so the actual native startup cache lookup is the refusal seam.
            return engine, instrument

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.sqlite3"
            ledger = safety.Ledger(path)
            try:
                ledger.start_trial(simulation.BASE_NS / 1e9)
                from nautilus_trader.model import CustomData

                engine, _ = missing_instrument()
                spec = contracts.StrategySpec(
                    "MISSING.ALPACA", simulation.COHORT_SHA256
                )
                strategy = families.GapPremarketStrategy(
                    spec, ledger=ledger, fault_sink=faults.append
                )
                try:
                    engine.add_strategy(strategy)
                    engine.add_data(
                        [
                            CustomData(
                                families.snapshot_data_type(simulation.INSTRUMENT_ID),
                                simulation.fixture_snapshot(),
                            )
                        ]
                    )
                    try:
                        engine.run()
                    except (ValueError, RuntimeError):
                        # rc5 may propagate startup errors; neither logging nor
                        # raising by itself supplies the durable/session signal.
                        pass
                    self.assertEqual(faults, ["startup_instrument_not_registered"])
                    self.assertEqual(
                        ledger.halted_reason(), "startup_instrument_not_registered"
                    )
                finally:
                    engine.dispose()
            finally:
                ledger.close()
            reopened = safety.Ledger(path)
            try:
                self.assertEqual(
                    reopened.halted_reason(), "startup_instrument_not_registered"
                )
            finally:
                reopened.close()

    def test_non_equity_freeze_is_durable_and_escalates_to_session(self):
        from nautilus_trader.model import (
            Currency,
            CurrencyPair,
            InstrumentId,
            Price,
            Quantity,
            Symbol,
        )

        non_equity = CurrencyPair(
            instrument_id=InstrumentId.from_str(simulation.INSTRUMENT_ID),
            raw_symbol=Symbol("TST"),
            base_currency=Currency.from_str("EUR"),
            quote_currency=Currency.from_str("USD"),
            price_precision=4,
            size_precision=0,
            price_increment=Price.from_str("0.0001"),
            size_increment=Quantity.from_int(1),
            lot_size=Quantity.from_int(1),
            ts_event=0,
            ts_init=0,
        )
        faults = []
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.sqlite3"
            ledger = safety.Ledger(path)
            try:
                ledger.start_trial(simulation.BASE_NS / 1e9)
                strategy = run_strategy(
                    ledger=ledger, faults=faults, instrument=non_equity
                )
                self.assertTrue(strategy.faulted)
                self.assertEqual(ledger.halted_reason(), "equity_instrument_required")
                self.assertEqual(faults, ["equity_instrument_required"])
                self.assertFalse(any(r["event"] == "submit" for r in strategy.trace))
            finally:
                ledger.close()
            reopened = safety.Ledger(path)
            try:
                self.assertEqual(reopened.halted_reason(), "equity_instrument_required")
            finally:
                reopened.close()

    def test_forced_exit_rests_until_timeout_and_fills_once(self):
        result = simulation.run_case(
            "gap_premarket",
            bids=("10",) * 12,
            spec_overrides={
                "exit_deadline_ns": simulation.BASE_NS + 5_000_000_000,
                "exit_timeout_ns": 4_000_000_000,
            },
        )
        sells = [
            r for r in result["trace"] if r["event"] == "submit" and r["side"] == "SELL"
        ]
        self.assertEqual(len(sells), 1, result)
        early_cancels = [
            r
            for r in result["trace"]
            if r["event"] == "cancel_requested"
            and r["role"] == "exit"
            and r["now_ns"] < sells[0]["now_ns"] + 4_000_000_000
        ]
        self.assertEqual(early_cancels, [], result)
        self.assertEqual(result["owned_quantity"], "0", result)
        self.assertEqual(result["callback_faults"], [])


if __name__ == "__main__":
    unittest.main()
