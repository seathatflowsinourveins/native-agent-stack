"""Offline tests for the paper execution-capacity harness.

A fake clock, fake broker and fake trade_updates stream stand in for Alpaca;
no credentials, no network and no broker requests. Evidence class of every
run here is offline_fixture.
"""
import contextlib
from datetime import datetime, timezone
from decimal import Decimal
import errno
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import signal
import sys
import tempfile
import threading
import time
import types
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "blueprints/us-equities/order-throughput"
sys.path.insert(0, str(SOURCE))

import capacity as c  # noqa: E402
import capacity_fixture as fx  # noqa: E402
import rate_governor as g  # noqa: E402
import rate_limit_evidence as evidence  # noqa: E402

UUID_TEXT = re.compile(r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}", re.I)
# Every signal the CLI routes to the stop-and-cleanup path (those this platform has).
STOP_SIGNALS = tuple(getattr(signal, name) for name in ("SIGINT", "SIGTERM", "SIGHUP", "SIGQUIT")
                     if hasattr(signal, name))


@contextlib.contextmanager
def restored_signal_handlers():
    """Restore every stop signal's handler afterwards. SIGHUP and SIGQUIT first get a
    recording sentinel, so a signal the code under test failed to route is recorded
    instead of terminating the test process."""
    saved = {sig: signal.getsignal(sig) for sig in STOP_SIGNALS}
    unrouted = []
    try:
        for sig in STOP_SIGNALS:
            if sig not in (signal.SIGINT, signal.SIGTERM):
                signal.signal(sig, lambda signum, _frame: unrouted.append(signum))
        yield unrouted
    finally:
        for sig, handler in saved.items():
            signal.signal(sig, handler)


class Clock:
    def __init__(self, wall=1_790_000_000.0):
        self.t = 100.0
        self.wall0 = wall

    def mono(self):
        return self.t

    def wall(self):
        return self.wall0 + self.t


def governor(cap=200, limit=200, **kwargs):
    clock = Clock()
    gov = g.RateGovernor(cap, clock=clock.mono, wall=clock.wall, **kwargs)
    gov.observe_limit(limit)
    return gov, clock


def drive(gov, clock, seconds, step=0.01):
    """Acquire as fast as admitted; return admission timestamps."""
    admitted = []
    end = clock.t + seconds
    while clock.t < end:
        if gov.try_acquire("submit"):
            admitted.append(clock.t)
        else:
            clock.t += step
    return admitted


def max_in_any_window(times, width=60.0):
    best, lo = 0, 0
    for hi, value in enumerate(times):
        while value - times[lo] >= width:
            lo += 1
        best = max(best, hi - lo + 1)
    return best


def stop_path(tmp):
    return Path(tmp) / "STOP"


def run(tmp, *, broker=None, clock=None, stop=None, **config):
    clock = clock or fx.FakeClock()
    broker = broker or fx.FakeBroker(clock)
    broker.clock = clock
    cfg = c.CapacityConfig(**dict({"max_duration_seconds": 130.0, "required_windows": 2}, **config))
    harness = c.CapacityRun(broker, cfg, clock=clock, executor=c.InlineExecutor(),
                            stop_file=stop or stop_path(tmp))
    return harness.run(), harness, broker


class GovernorTests(unittest.TestCase):
    def test_budget_is_min_of_cap_and_header_times_headroom(self):
        self.assertEqual(governor(200, 200)[0].budget, 180)
        self.assertEqual(governor(1000, 1000)[0].budget, 900)
        self.assertEqual(governor(200, 1000)[0].budget, 180)   # configured cap binds
        self.assertEqual(governor(1000, 200)[0].budget, 180)   # observed header binds

    def test_200_header_never_exceeds_budget_in_any_rolling_window(self):
        gov, clock = governor(200, 200)
        times = drive(gov, clock, 300)
        self.assertLessEqual(max_in_any_window(times), 180)
        self.assertGreaterEqual(len(times), 5 * 180 - 20)

    def test_1000_header_same_code_scales(self):
        gov, clock = governor(1000, 1000)
        times = drive(gov, clock, 300, step=0.002)
        self.assertLessEqual(max_in_any_window(times), 900)
        self.assertGreaterEqual(len(times), 5 * 900 - 60)

    def test_header_rise_mid_run_raises_budget_up_to_cap(self):
        gov, clock = governor(1000, 200)
        first = drive(gov, clock, 120)
        gov.on_response("submit", 200, {"x-ratelimit-limit": "1000"})
        self.assertEqual(gov.budget, 900)
        second = drive(gov, clock, 120, step=0.002)
        self.assertLessEqual(max_in_any_window(first), 180)
        self.assertGreater(len(second), 3 * len(first))
        self.assertEqual([row["limit"] for row in gov.limit_history], [200, 1000])

    def test_429_freezes_counts_and_honours_retry_after(self):
        gov, clock = governor()
        self.assertTrue(gov.try_acquire("submit"))
        delay = gov.on_response("submit", 429, {"Retry-After": "7", "x-ratelimit-limit": "200"})
        self.assertEqual(delay, 7.0)
        self.assertEqual(gov.stats["http_429"], 1)
        clock.t += 6.9
        self.assertFalse(gov.try_acquire("cancel"))
        self.assertGreater(gov.wait_hint(), 0.0)
        clock.t += 0.2
        clock.t += 1.0  # tokens were zeroed by the 429
        self.assertTrue(gov.try_acquire("cancel"))

    def test_429_backoff_sources(self):
        gov, clock = governor()
        date = datetime.fromtimestamp(clock.wall() + 12, timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
        self.assertAlmostEqual(gov.on_response("submit", 429, {"retry-after": date}), 12.0, delta=1.0)
        gov, clock = governor()
        reset = str(int(clock.wall()) + 20)
        self.assertAlmostEqual(gov.on_response("submit", 429, {"x-ratelimit-reset": reset}), 20.0, delta=1.0)
        gov, _ = governor()
        self.assertEqual([gov.on_response("submit", 429, {}) for _ in range(3)], [1.0, 2.0, 4.0])
        self.assertEqual(gov.summary()["backoffs"][-1]["source"], "exponential")

    def test_remaining_header_holds_admission_until_reset(self):
        gov, clock = governor()
        clock.t += 10
        reset = int(clock.wall()) + 30
        gov.on_response("read", 200, {"x-ratelimit-limit": "200", "x-ratelimit-remaining": "20",
                                      "x-ratelimit-reset": str(reset)})
        self.assertFalse(gov.try_acquire("submit"))  # 20 left == reserve kept for others
        self.assertEqual(gov.stats["denied_server_remaining"], 1)
        clock.t += 31
        self.assertTrue(gov.try_acquire("submit"))

    def test_unobserved_limit_and_bounds_fail_closed(self):
        gov = g.RateGovernor(200)
        with self.assertRaises(g.GovernorError):
            gov.try_acquire("submit")
        for bad in (0, 5000, "200"):
            with self.assertRaises(g.GovernorError):
                g.RateGovernor(bad)
        with self.assertRaises(g.GovernorError):
            g.RateGovernor(200, headroom=1.5)


class CapacityRunTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_200_header_sustains_target_and_passes_capacity_criteria(self):
        receipt, _, broker = run(self.tmp.name, max_duration_seconds=330.0, required_windows=5)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["rate"]["budget_per_minute"], 180)
        self.assertEqual(receipt["acceptance"]["target_order_actions_per_window"], 170)
        self.assertGreaterEqual(receipt["throughput"]["min_order_actions_full_window"], 170)
        self.assertLessEqual(receipt["throughput"]["max_order_actions_full_window"], 180)
        self.assertTrue(receipt["acceptance"]["capacity_criteria_met"])
        self.assertFalse(receipt["acceptance"]["passed"])  # offline fixture never qualifies
        self.assertEqual(receipt["http_429"]["total"], 0)
        self.assertEqual(broker.open_orders_with_prefix(receipt["probe_plan"]["client_order_id_prefix"]), [])

    def test_1000_header_same_code_reaches_1000_scale(self):
        clock = fx.FakeClock()
        broker = fx.FakeBroker(clock, limit=1000)
        receipt, _, _ = run(self.tmp.name, broker=broker, clock=clock, configured_cap_per_minute=1000,
                            max_orders=3000)
        self.assertEqual(receipt["rate"]["budget_per_minute"], 900)
        self.assertGreaterEqual(receipt["throughput"]["min_order_actions_full_window"], 850)
        self.assertTrue(receipt["acceptance"]["capacity_criteria_met"])

    def test_data_origin_limit_never_sizes_trading_budget(self):
        receipt, _, _ = run(self.tmp.name, configured_cap_per_minute=1000)
        self.assertEqual(receipt["preflight"]["trading_limit_header"], 200)
        self.assertEqual(receipt["preflight"]["data_limit_headers_seen"], ["10000"])
        self.assertEqual(receipt["rate"]["effective_limit"], 200)

    def test_header_rise_during_run_is_adopted(self):
        clock = fx.FakeClock()
        switch = clock.time() + 90
        broker = fx.FakeBroker(clock, limit_schedule=lambda wall: 200 if wall < switch else 1000)
        receipt, _, _ = run(self.tmp.name, broker=broker, clock=clock, configured_cap_per_minute=1000,
                            max_duration_seconds=250.0, max_orders=3000)
        self.assertEqual([row["limit"] for row in receipt["rate_limit_changes"]], [200, 1000])
        windows = receipt["throughput"]["windows"]
        self.assertLessEqual(windows[0]["order_actions"], 180)
        self.assertGreaterEqual(windows[2]["order_actions"], 850)
        self.assertEqual(receipt["http_429"]["total"], 0)

    def test_429_freezes_backs_off_and_is_resolved(self):
        clock = fx.FakeClock()
        broker = fx.FakeBroker(clock, force_429_calls={25}, retry_after="3")
        receipt, harness, _ = run(self.tmp.name, broker=broker, clock=clock)
        self.assertEqual(receipt["http_429"], {"total": 1, "handled": 1, "unhandled": 0})
        self.assertEqual(receipt["rate"]["backoffs"][0]["source"], "retry_after")
        self.assertEqual(receipt["rate"]["backoffs"][0]["seconds"], 3.0)
        rejected = [row["t"] for row in broker.call_log][24]
        after = [row["t"] for row in broker.call_log[25:]]
        self.assertGreaterEqual(after[0] - rejected, 3.0 - 0.05)  # nothing sent while frozen
        self.assertEqual(receipt["status"], "completed")
        self.assertTrue(receipt["reconciliation"]["clean"])
        self.assertEqual(receipt["acceptance"]["unhandled_http_429"], 0)

    def test_repeated_429_beyond_cap_stops_and_cleans_up(self):
        clock = fx.FakeClock()
        broker = fx.FakeBroker(clock, force_429_calls={10, 20, 30}, retry_after="1")
        receipt, _, _ = run(self.tmp.name, broker=broker, clock=clock, max_http_429=2)
        self.assertEqual(receipt["stop_reason"], "http_429_cap_exceeded")
        self.assertTrue(receipt["cleanup"]["verified_zero_open"])

    def test_live_base_url_is_refused_before_any_request(self):
        receipt, _, broker = run(self.tmp.name, base_url="https://api.alpaca.markets")
        self.assertEqual((receipt["status"], receipt["refusal_reason"]), ("refused", "non_paper_base_url"))
        self.assertEqual(broker.call_log, [])
        self.assertEqual(receipt["orders"]["submit_attempts"], 0)

    def test_cli_refuses_live_base_url_from_env_file_without_network(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as private:
            env = Path(private) / "paper.env"
            env.write_text("APCA_API_KEY_ID=fixturekey\nAPCA_API_SECRET_KEY=fixturesecret\n"
                           "APCA_API_BASE_URL=https://api.alpaca.markets\n")
            os.chmod(env, 0o600)
            out = Path(private) / "receipt.json"
            with restored_signal_handlers(), contextlib.redirect_stdout(io.StringIO()):
                code = c.main(["paper", "--env-file", str(env), "--output", str(out)])
            receipt = json.loads(out.read_text())
        self.assertEqual(code, 2)
        self.assertEqual(receipt["refusal_reason"], "non_paper_base_url")
        text = json.dumps(receipt)
        self.assertNotIn("fixturekey", text)
        self.assertNotIn("fixturesecret", text)

    def test_env_base_url_reads_only_that_key(self):
        with tempfile.TemporaryDirectory() as private:
            env = Path(private) / "e"
            env.write_text("# comment\nexport APCA_API_BASE_URL='https://paper-api.alpaca.markets'\n")
            self.assertEqual(c.env_base_url(env), "https://paper-api.alpaca.markets")
            env.write_text("APCA_API_KEY_ID=x\n")
            self.assertIsNone(c.env_base_url(env))

    def test_stop_file_refuses_start(self):
        stop = stop_path(self.tmp.name)
        stop.write_text("")
        receipt, _, broker = run(self.tmp.name)
        self.assertEqual((receipt["status"], receipt["refusal_reason"]), ("refused", "stop_file_present"))
        self.assertEqual(broker.call_log, [])

    def test_stop_file_mid_run_stops_submissions_and_cleans_up(self):
        stop = stop_path(self.tmp.name)

        class StopAt40(fx.FakeBroker):
            def submit(self, *args):
                response = super().submit(*args)
                if self.submit_count == 40:
                    stop.write_text("")
                return response

        clock = fx.FakeClock()
        receipt, _, broker = run(self.tmp.name, broker=StopAt40(clock), clock=clock)
        self.assertEqual(receipt["stop_reason"], "stop_file_present")
        self.assertEqual(broker.submit_count, 40)
        self.assertTrue(receipt["cleanup"]["verified_zero_open"])

    def test_default_stop_file_is_adaptive_paper_kill_switch(self):
        sys.path.insert(0, str(ROOT / "blueprints/us-equities/adaptive-paper"))
        import safety
        harness = c.CapacityRun(fx.FakeBroker(fx.FakeClock()), c.CapacityConfig())
        self.assertEqual(harness.stop_file, safety.DEFAULT_STOP)

    def test_cancel_all_guard_rules(self):
        prefix = "cap-20260924t140000-abcdef-"
        ours = [{"client_order_id": prefix + "000001"}]
        foreign = ours + [{"client_order_id": "strategy-1"}]
        self.assertEqual(c.cancel_all_guard(ours, True, prefix, preflight_open_orders=0),
                         (True, "only_this_runs_orders_open"))
        self.assertFalse(c.cancel_all_guard(foreign, True, prefix, preflight_open_orders=0)[0])
        self.assertFalse(c.cancel_all_guard(ours, False, prefix, preflight_open_orders=0)[0])
        self.assertEqual(c.cancel_all_guard(ours, True, prefix, preflight_open_orders=1)[1],
                         "preflight_found_open_orders_not_created_by_this_run")

    def test_cancel_all_refused_with_foreign_orders_and_individual_cancels_used(self):
        clock = fx.FakeClock()
        # Dropping "new" keeps probes unacknowledged, so harness orders are open at cleanup.
        broker = fx.FakeBroker(clock, foreign_open_orders=1, drop_events={"new"})
        receipt, _, _ = run(self.tmp.name, broker=broker, clock=clock, allow_cancel_all=True,
                            acknowledged_open_orders=1)
        self.assertEqual(receipt["cleanup"]["cancel_all_decision"],
                         "preflight_found_open_orders_not_created_by_this_run")
        self.assertFalse(receipt["cleanup"]["cancel_all_used"])
        self.assertEqual(broker.cancel_all_calls, 0)
        self.assertGreater(receipt["cleanup"]["individual_cancels"], 0)
        self.assertEqual(broker.orders["strategy-foreign-0"]["status"], "new")  # untouched
        self.assertTrue(receipt["cleanup"]["verified_zero_open"])
        self.assertFalse(receipt["acceptance"]["websocket_completeness_is_1"])

    def test_cancel_all_used_only_when_guard_proves_no_foreign_orders(self):
        clock = fx.FakeClock()
        broker = fx.FakeBroker(clock, drop_events={"new"})
        receipt, _, _ = run(self.tmp.name, broker=broker, clock=clock, allow_cancel_all=True)
        self.assertEqual(receipt["cleanup"]["cancel_all_decision"], "only_this_runs_orders_open")
        self.assertEqual(broker.cancel_all_calls, 1)
        self.assertTrue(receipt["cleanup"]["verified_zero_open"])
        # Default configuration never uses cancel-all.
        broker = fx.FakeBroker(fx.FakeClock(), drop_events={"new"})
        receipt, _, _ = run(self.tmp.name, broker=broker, clock=broker.clock)
        self.assertEqual(broker.cancel_all_calls, 0)
        self.assertEqual(receipt["cleanup"]["cancel_all_decision"], "not_enabled")

    def test_native_port_never_exposes_cancel_all(self):
        import alpaca_capacity_port as native
        self.assertFalse(native.AlpacaCapacityPort.supports_cancel_all)
        self.assertEqual(native.AlpacaCapacityPort.evidence_class, "native_paper")

    def test_cleanup_runs_on_exception(self):
        clock = fx.FakeClock()
        broker = fx.FakeBroker(clock, crash_on_submit_seq=5)
        receipt, _, _ = run(self.tmp.name, broker=broker, clock=clock)
        self.assertEqual((receipt["status"], receipt["error_type"]), ("failed", "RuntimeError"))
        self.assertTrue(receipt["cleanup"]["verified_zero_open"])
        self.assertEqual(broker.open_orders_with_prefix(receipt["probe_plan"]["client_order_id_prefix"]), [])
        self.assertTrue(broker.stream_stopped)

    def test_signal_request_stops_and_cleans_up(self):
        clock = fx.FakeClock()

        class SignalAt30(fx.FakeBroker):
            def submit(self, *args):
                response = super().submit(*args)
                if self.submit_count == 30:
                    self.harness.request_stop("signal")
                return response

        broker = SignalAt30(clock)
        cfg = c.CapacityConfig(max_duration_seconds=130.0)
        harness = c.CapacityRun(broker, cfg, clock=clock, executor=c.InlineExecutor(),
                                stop_file=stop_path(self.tmp.name))
        broker.harness = harness
        receipt = harness.run()
        self.assertEqual(receipt["stop_reason"], "signal")
        self.assertTrue(receipt["cleanup"]["verified_zero_open"])

    def test_reconciliation_detects_missing_mismatch_and_unknown(self):
        clock = fx.FakeClock()
        broker = fx.FakeBroker(clock, hide_from_listing={3}, listing_status_override={4: "filled"},
                               ghost_order=True)
        receipt, _, _ = run(self.tmp.name, broker=broker, clock=clock)
        rec = receipt["reconciliation"]
        self.assertEqual(rec["missing_from_broker"], [3])
        self.assertEqual(rec["status_mismatches"], [{"seq": 4, "stream": "canceled", "rest": "filled"}])
        self.assertEqual(rec["filled_probes"], [4])
        self.assertEqual(rec["unknown_prefix_orders"], 1)
        self.assertFalse(rec["clean"])
        self.assertEqual(receipt["status"], "needs_attention")
        self.assertFalse(receipt["acceptance"]["capacity_criteria_met"])

    def test_missing_stream_terminal_event_breaks_completeness(self):
        clock = fx.FakeClock()

        class DropSeventh(fx.FakeBroker):
            def _emit(self, event, order):
                if event == "canceled" and order["client_order_id"].endswith("000007"):
                    return
                super()._emit(event, order)

        receipt, _, _ = run(self.tmp.name, broker=DropSeventh(clock), clock=clock)
        self.assertIn("stream_terminal_missing", receipt["health_freezes"])
        self.assertLess(receipt["websocket"]["completeness"], 1.0)
        self.assertFalse(receipt["acceptance"]["websocket_completeness_is_1"])

    def test_unacknowledged_positions_or_orders_refuse(self):
        broker = fx.FakeBroker(fx.FakeClock(), positions=[{"symbol": "AAPL", "qty": "5"}])
        receipt, _, _ = run(self.tmp.name, broker=broker, clock=broker.clock)
        self.assertEqual(receipt["refusal_reason"], "unacknowledged_positions")
        self.assertEqual(receipt["orders"]["submit_attempts"], 0)
        broker = fx.FakeBroker(fx.FakeClock(), foreign_open_orders=2)
        receipt, _, _ = run(self.tmp.name, broker=broker, clock=broker.clock, acknowledged_open_orders=1)
        self.assertEqual(receipt["refusal_reason"], "unacknowledged_open_orders")
        broker = fx.FakeBroker(fx.FakeClock(), positions=[{"symbol": "AAPL", "qty": "5"}])
        receipt, _, _ = run(self.tmp.name, broker=broker, clock=broker.clock, acknowledged_positions=1)
        self.assertEqual(receipt["status"], "completed")
        self.assertTrue(receipt["reconciliation"]["position_unchanged"])

    def test_adaptive_lane_state_refuses_paper_scope(self):
        fingerprint = "a" * 64
        state = Path(self.tmp.name) / fingerprint / "adaptive"
        state.mkdir(parents=True)
        (state / "trial.json").write_text("{}")
        with self.assertRaises(c.HarnessRefusal) as raised:
            with c._paper_scope(self.tmp.name, False)(fingerprint):
                pass
        self.assertEqual(str(raised.exception), "account_has_adaptive_paper_state")

    def test_busy_account_lock_is_a_refusal(self):
        import safety
        with safety.account_lock_fingerprint("b" * 64, lock_root=self.tmp.name):
            original = safety.account_lock_fingerprint
            safety.account_lock_fingerprint = lambda fp: original(fp, lock_root=self.tmp.name)
            try:
                with self.assertRaises(c.HarnessRefusal) as raised:
                    with c._paper_scope(self.tmp.name, False)("b" * 64):
                        pass
            finally:
                safety.account_lock_fingerprint = original
        self.assertEqual(str(raised.exception), "account_writer_already_running")

    def test_session_rules(self):
        closed = fx.FakeClock(datetime(2026, 9, 26, 15, 0, tzinfo=timezone.utc).timestamp())  # Saturday
        receipt, _, _ = run(self.tmp.name, clock=closed, broker=fx.FakeBroker(closed))
        self.assertEqual(receipt["refusal_reason"], "market_session_closed")
        pre = fx.FakeClock(datetime(2026, 9, 24, 11, 0, tzinfo=timezone.utc).timestamp())  # 07:00 ET
        broker = fx.FakeBroker(pre)
        receipt, _, _ = run(self.tmp.name, clock=pre, broker=broker)
        self.assertEqual(receipt["session_kind"], "PRE")
        self.assertEqual(broker.extended_hours_flags, {True})
        self.assertTrue(receipt["extended_hours_orders"])
        pre = fx.FakeClock(datetime(2026, 9, 24, 11, 0, tzinfo=timezone.utc).timestamp())
        receipt, _, _ = run(self.tmp.name, clock=pre, broker=fx.FakeBroker(pre), allow_extended_hours=False)
        self.assertEqual(receipt["refusal_reason"], "extended_hours_not_allowed")

    def test_price_band_and_rejections_are_data(self):
        self.assertEqual(c.limit_price_below_bid("500.00", 500), Decimal("475.00"))
        self.assertEqual(c.limit_price_below_bid("123.457", 1000), Decimal("111.11"))
        with self.assertRaises(c.HarnessRefusal):
            c.limit_price_below_bid("1.00", 500)
        clock = fx.FakeClock()
        broker = fx.FakeBroker(clock, reject_submit_seqs={1: 422, 2: 403})
        receipt, _, _ = run(self.tmp.name, broker=broker, clock=clock)
        self.assertEqual(receipt["orders"]["rest_rejections"], {"http_403": 1, "http_422": 1})
        self.assertEqual(receipt["status"], "completed")
        clock = fx.FakeClock()
        broker = fx.FakeBroker(clock, reject_submit_seqs={seq: 422 for seq in range(1, 50)})
        receipt, _, _ = run(self.tmp.name, broker=broker, clock=clock, max_consecutive_rejections=5)
        self.assertEqual(receipt["stop_reason"], "consecutive_rejections")
        self.assertEqual(receipt["orders"]["submit_attempts"], 5)

    def test_caps_bound_orders_open_orders_and_notional(self):
        receipt, harness, _ = run(self.tmp.name, max_orders=25)
        self.assertEqual(receipt["orders"]["submit_attempts"], 25)
        self.assertEqual(receipt["stop_reason"], "max_orders_reached")
        clock = fx.FakeClock()
        broker = fx.FakeBroker(clock, drop_events={"new"})
        receipt, _, _ = run(self.tmp.name, broker=broker, clock=clock, max_open_orders=3)
        self.assertEqual(receipt["orders"]["submit_attempts"], 3)
        receipt, _, _ = run(self.tmp.name, max_order_notional_usd="100")
        self.assertEqual(receipt["refusal_reason"], "order_notional_cap_exceeded")
        clock = fx.FakeClock()
        broker = fx.FakeBroker(clock, drop_events={"new"})
        receipt, _, _ = run(self.tmp.name, broker=broker, clock=clock, max_open_notional_usd="1000")
        self.assertEqual(receipt["orders"]["submit_attempts"], 2)  # 2 x 475.00 <= 1000

    def test_unexpected_fill_freezes_and_needs_attention(self):
        clock = fx.FakeClock()
        broker = fx.FakeBroker(clock, fill_submit_seqs={3})
        receipt, _, _ = run(self.tmp.name, broker=broker, clock=clock)
        self.assertIn("unexpected_fill", receipt["health_freezes"])
        self.assertEqual(receipt["orders"]["unexpected_fill_qty"], "1")
        self.assertEqual(receipt["status"], "needs_attention")
        self.assertFalse(receipt["acceptance"]["no_unexpected_fills"])

    def test_foreign_stream_events_are_ignored(self):
        clock = fx.FakeClock()
        broker = fx.FakeBroker(clock, foreign_open_orders=1)
        receipt, harness, _ = run(self.tmp.name, broker=broker, clock=clock, acknowledged_open_orders=1)
        harness._handle_event({"data": {"event": "new", "order": {"client_order_id": "other-1", "id": "x"}}})
        self.assertEqual(harness.stream_stats["foreign_events_ignored"], 1)
        self.assertEqual(receipt["status"], "completed")

    def test_receipt_fields_and_no_secrets(self):
        receipt, _, _ = run(self.tmp.name)
        for key in ("schema_version", "harness", "evidence_class", "policy", "counts_as_strategy_trades",
                    "strategy_trades", "status", "config", "probe_plan", "preflight", "rate",
                    "observed_rate_limit_headers", "http_status_counts", "http_429", "orders", "latency",
                    "throughput", "websocket", "cleanup", "reconciliation", "acceptance"):
            self.assertIn(key, receipt)
        self.assertEqual(receipt["evidence_class"], "offline_fixture")
        self.assertIs(receipt["counts_as_strategy_trades"], False)
        self.assertEqual(receipt["strategy_trades"], 0)
        self.assertIn("never be counted as strategy", receipt["policy"])
        for name in ("submit_rest_ack", "submit_to_stream_ack", "submit_to_stream_terminal"):
            self.assertTrue({"p50_ms", "p95_ms", "p99_ms"} <= set(receipt["latency"][name]))
        windows = receipt["throughput"]["windows"]
        self.assertTrue(all({"submits", "cancels", "order_actions"} <= set(row) for row in windows))
        self.assertEqual(receipt["observed_rate_limit_headers"]["counts_by_origin_and_limit"]["data:10000"], 1)
        self.assertEqual(receipt["websocket"]["completeness"], 1.0)
        self.assertIn("clean", receipt["reconciliation"])
        text = json.dumps(receipt)
        self.assertIsNone(UUID_TEXT.search(text))   # no broker order ids
        self.assertNotIn(fx.hashlib.sha256(b"fixture-account").hexdigest(), text)  # no account identity
        self.assertNotIn("APCA_", text)

    def test_percentile_nearest_rank(self):
        values = list(range(1, 101))
        self.assertEqual((c.percentile(values, 50), c.percentile(values, 95), c.percentile(values, 99)),
                         (50, 95, 99))
        self.assertIsNone(c.percentile([], 50))

    def test_config_bounds(self):
        for change in ({"qty": 0}, {"band_bps": 50}, {"max_open_orders": 1000}, {"headroom": 0.0},
                       {"symbol": "spy"}, {"max_order_notional_usd": "0"}, {"allow_cancel_all": 1}):
            with self.assertRaises(c.HarnessRefusal):
                c.CapacityConfig(**change).validate()


class NativePortLogicTests(unittest.TestCase):
    """SDK-free checks of the native port's own logic; the SDK client is a stub."""

    def port(self, client, stop_file=None):
        import queue
        import alpaca_capacity_port as native
        port = native.AlpacaCapacityPort("k", "s", "SPY", stop_file=stop_file)
        port._pool = queue.Queue()
        port._pool.put(client)
        return port, native

    def test_response_mapping_uses_guarded_session_observation(self):
        class Client:
            def __init__(self):
                self.owner = None

            def ok(self):
                self.owner._observe({"kind": "cancel", "status": 204,
                                     "headers": {"x-ratelimit-limit": "200", "x-ratelimit-remaining": "150"}})
                return None

            def limited(self):
                self.owner._observe({"kind": "submit", "status": 429, "headers": {"retry-after": "2"}})
                error = RuntimeError("provider text never retained")
                error.status_code = 429
                raise error

        client = Client()
        port, native = self.port(client)
        client.owner = port
        response, _ = port._call(lambda cl: cl.ok())
        self.assertEqual((response.status, response.headers["x-ratelimit-limit"]), (204, "200"))
        response, _ = port._call(lambda cl: cl.limited())
        self.assertEqual((response.status, response.error, response.headers), (429, "RuntimeError", {"retry-after": "2"}))

        def not_sent(_):
            raise native.transport.SubmissionNotSent("prevented")
        response, _ = port._call(not_sent)
        self.assertTrue(response.not_sent)
        self.assertEqual(port._pool.qsize(), 1)  # client always returned to the pool

    def test_stop_file_blocks_submit_at_transport_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            stop = Path(tmp) / "STOP"
            port, native = self.port(object(), stop_file=stop)
            self.assertIsNone(port._before_request("submit", client_id="x"))
            stop.write_text("")
            with self.assertRaises(native.SafetyError):
                port._before_request("submit", client_id="x")
            self.assertIsNone(port._before_request("cancel"))  # cancels stay allowed

    def test_cancel_requires_uuid_and_listing_paginates(self):
        import uuid

        class Client:
            def __init__(self):
                self.calls = []

            def get(self, path, params):
                self.calls.append(dict(params))
                start = 0 if "after_order_id" not in params else 500
                size = 500 if start == 0 else 3
                return [{"id": str(uuid.UUID(int=start + i + 1)), "client_order_id": "c%d" % (start + i),
                         "status": "canceled", "symbol": "SPY", "side": "buy", "filled_qty": "0"}
                        for i in range(size)]

        client = Client()
        port, _ = self.port(client)
        self.assertTrue(port.cancel("not-a-uuid").not_sent)
        orders, complete, responses = port.list_orders("all", 1_790_000_000.0)
        self.assertEqual((len(orders), complete, len(responses)), (503, True, 2))
        self.assertIn("after", client.calls[0])
        self.assertNotIn("after", client.calls[1])  # ID and timestamp cursors are exclusive
        client.calls.clear()
        orders, complete, responses = port.list_orders("all", None, lambda: False)
        self.assertEqual((len(orders), complete, len(responses), len(client.calls)), (500, False, 1, 1))
        with self.assertRaises(Exception):
            port.cancel_all()

    def test_stream_owner_callbacks_drive_health(self):
        port, _ = self.port(object())
        self.assertFalse(port.stream_health()["ready"])
        port._authorized("orders")
        port._ack("orders", True)
        self.assertTrue(port.stream_health()["ready"])
        port._connection("orders", False)
        self.assertEqual(port.stream_health(), {"ready": False, "reasons": ["orders_disconnected"]})

    def test_positions_read_raises_on_an_error_status(self):
        """The native port raises on a 429 or 5xx positions read (there is no retry), so the
        live periodic position check fails closed."""
        class Client:
            def __init__(self, status):
                self.owner, self.status = None, status

            def get_all_positions(self):
                self.owner._observe({"kind": "read", "status": self.status, "headers": {"retry-after": "1"}})
                error = RuntimeError("provider text never retained")
                error.status_code = self.status
                raise error

        for status in (429, 503):
            with self.subTest(status=status):
                client = Client(status)
                port, native = self.port(client)
                client.owner = port
                with self.assertRaises(native.transport.TransportError):
                    port.positions()


class LaggedFuture(c.Future):
    """Resolved at dispatch (the broker saw the call then), but reported done only once
    the fake clock passes ``ready_at``: several calls stay in flight and complete out of order."""

    def __init__(self, clock, ready_at):
        super().__init__()
        self.clock, self.ready_at = clock, ready_at

    def done(self):
        return self.clock.monotonic() >= self.ready_at and super().done()


class LaggedExecutor:
    LAGS = (1.2, 0.1, 2.0, 0.5, 1.6, 0.3)

    def __init__(self, clock):
        self.clock = clock
        self.count = 0
        self.max_pending = 0
        self.pending = []

    def submit(self, fn, *args):
        future = LaggedFuture(self.clock, self.clock.monotonic() + self.LAGS[self.count % len(self.LAGS)])
        self.count += 1
        try:
            future.set_result(fn(*args))
        except Exception as exc:
            future.set_exception(exc)
        now = self.clock.monotonic()
        self.pending = [f for f in self.pending if f.ready_at > now] + [future]
        self.max_pending = max(self.max_pending, len(self.pending))
        return future

    def shutdown(self, wait=True):
        return None


class LockedClock(fx.FakeClock):
    """FakeClock safe for REST worker threads (no lost updates, never goes backwards)."""

    def __init__(self, *args):
        super().__init__(*args)
        self.lock = __import__("threading").RLock()

    def monotonic(self):
        with self.lock:
            return self.now

    def time(self):
        with self.lock:
            return self.now + self.offset

    def sleep(self, seconds):
        with self.lock:
            self.now += max(float(seconds), 1e-4)

    def advance(self, seconds):
        with self.lock:
            self.now += float(seconds)


class LockedBroker(fx.FakeBroker):
    """Serializes the fake broker's state for a real ThreadPoolExecutor."""

    def __init__(self, clock, **kwargs):
        super().__init__(clock, **kwargs)
        self.lock = clock.lock

    def submit(self, *args):
        with self.lock:
            return super().submit(*args)

    def cancel(self, *args):
        with self.lock:
            return super().cancel(*args)

    def list_orders(self, *args):
        with self.lock:
            return super().list_orders(*args)

    def positions(self):
        with self.lock:
            return super().positions()


def max_calls_in_rolling_window(call_log, width=60.0):
    return max_in_any_window(sorted(row["t"] for row in call_log), width)


class ReviewFixTests(unittest.TestCase):
    """Cases added for the independent review of the capacity harness."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def harness(self, broker, clock, executor=None, **config):
        cfg = c.CapacityConfig(**dict({"max_duration_seconds": 130.0, "required_windows": 2}, **config))
        return c.CapacityRun(broker, cfg, clock=clock, executor=executor or c.InlineExecutor(),
                             stop_file=stop_path(self.tmp.name))

    # F1 (review A): several failing in-flight futures must not abort cleanup.
    def test_several_failing_inflight_futures_still_clean_up(self):
        clock = fx.FakeClock()

        class CreatesThenRaises(fx.FakeBroker):
            def submit(self, *args):
                response = super().submit(*args)
                if self.submit_count in (5, 6, 7):
                    raise AttributeError("post-create defect")
                return response

        broker = CreatesThenRaises(clock)
        executor = LaggedExecutor(clock)
        harness = self.harness(broker, clock, executor, inflight=4)
        receipt = harness.run()
        prefix = receipt["probe_plan"]["client_order_id_prefix"]
        self.assertGreaterEqual(executor.max_pending, 3)
        self.assertEqual((receipt["status"], receipt["error_type"]), ("failed", "AttributeError"))
        self.assertEqual(receipt["port_errors"], 3)
        self.assertIn("port_exception", receipt["health_freezes"])
        self.assertEqual(receipt["orders"]["rest_rejections"].get("port_exception"), 3)
        self.assertTrue(receipt["cleanup"]["verified_zero_open"])
        self.assertEqual(broker.open_orders_with_prefix(prefix), [])
        # The orders were created and seen on the stream, so the stream resolves them.
        self.assertEqual(sum(1 for p in harness.probes.values()
                             if p.rest_status is None and p.state == "accepted_by_stream"), 3)
        self.assertTrue(receipt["reconciliation"]["clean"])
        self.assertEqual(receipt["websocket"]["completeness"], 1.0)
        self.assertFalse(receipt["acceptance"]["capacity_criteria_met"])

    # F2 (review A): a 429 during cleanup must not use up the cleanup window.
    def test_429_backoff_during_cleanup_extends_the_cleanup_deadline(self):
        clock = fx.FakeClock()
        box = {}

        class LimitedInCleanup(fx.FakeBroker):
            def _admit(self, kind):
                harness = box.get("harness")
                if harness is not None and harness.stage == "cleanup" and box.setdefault("forced", 0) < 2:
                    box["forced"] += 1
                    self.force_429_calls.add(self.total_trading_calls + 1)
                return super()._admit(kind)

        broker = LimitedInCleanup(clock, drop_events={"new"}, retry_after="60")
        harness = self.harness(broker, clock, max_duration_seconds=5.0)
        box["harness"] = harness
        receipt = harness.run()
        prefix = receipt["probe_plan"]["client_order_id_prefix"]
        self.assertEqual(receipt["http_429"]["total"], 2)
        self.assertEqual([b["seconds"] for b in receipt["rate"]["backoffs"]], [60.0, 60.0])
        self.assertGreater(receipt["cleanup"]["seconds"], c.CapacityConfig().cleanup_timeout_seconds)
        self.assertLessEqual(receipt["cleanup"]["seconds"], receipt["cleanup"]["ceiling_seconds"] + 1.0)
        self.assertTrue(receipt["cleanup"]["verified_zero_open"])
        self.assertEqual(broker.open_orders_with_prefix(prefix), [])

    # F3 (review A): every listing page is admitted by the governor.
    def test_every_listing_page_is_admitted_by_the_governor(self):
        clock = fx.FakeClock()
        broker = fx.FakeBroker(clock, page_size=40)
        receipt = self.harness(broker, clock, headroom=1.0).run()
        broker_reads = sum(1 for row in broker.call_log if row["kind"] == "read")
        self.assertGreater(broker_reads - 4, 3)  # multi-page listings happened
        self.assertEqual(receipt["rate"]["admitted"]["read"], broker_reads - 4)  # 4 preflight GETs
        self.assertEqual(receipt["rate"]["external_calls_noted"], 4)  # only the preflight
        self.assertEqual(receipt["http_429"]["total"], 0)
        self.assertTrue(receipt["reconciliation"]["listing_complete"])

    # F1 (review B): rejected submits are not completed order actions.
    def test_rejected_submits_do_not_count_toward_sustained_capacity(self):
        clock = fx.FakeClock()
        broker = fx.FakeBroker(clock, reject_submit_seqs={s: 422 for s in range(1, 5001) if s % 10})
        receipt = self.harness(broker, clock, max_orders=5000, max_duration_seconds=330.0,
                               required_windows=5).run()
        full = [row for row in receipt["throughput"]["windows"] if row["full"]]
        self.assertEqual(len(full), 5)
        self.assertTrue(all(row["order_actions_attempted"] >= 170 for row in full))
        self.assertTrue(all(row["order_actions"] < 170 for row in full))
        self.assertTrue(all(row["submits"] < row["submits_attempted"] for row in full))
        self.assertGreater(receipt["throughput"]["order_actions_not_completed_in_phase"], 0)
        self.assertEqual(receipt["acceptance"]["best_consecutive_full_windows_at_target"], 0)
        self.assertFalse(receipt["acceptance"]["capacity_criteria_met"])

    # F2 (review B) and F5: an ambiguous submit whose order WAS created.
    def test_created_order_with_lost_response_and_no_stream_breaks_completeness(self):
        clock = fx.FakeClock()
        broker = fx.FakeBroker(clock, lost_response_seqs={10: None}, silent_submit_seqs={10})
        receipt = self.harness(broker, clock).run()
        prefix = receipt["probe_plan"]["client_order_id_prefix"]
        self.assertEqual(receipt["reconciliation"]["ambiguous_submits"]["existed"], 1)
        self.assertEqual(broker.open_orders_with_prefix(prefix), [])  # the prefix sweep cancelled it
        self.assertTrue(receipt["cleanup"]["verified_zero_open"])
        self.assertLess(receipt["websocket"]["completeness"], 1.0)
        self.assertFalse(receipt["acceptance"]["websocket_completeness_is_1"])
        self.assertFalse(receipt["acceptance"]["capacity_criteria_met"])

    def test_created_order_with_lost_5xx_response_resolved_by_stream(self):
        clock = fx.FakeClock()
        broker = fx.FakeBroker(clock, lost_response_seqs={10: 503, 11: None})
        receipt = self.harness(broker, clock).run()
        self.assertEqual(receipt["orders"]["rest_rejections"], {"ambiguous_503": 1, "ambiguous_no_response": 1})
        self.assertEqual(receipt["websocket"]["completeness"], 1.0)
        self.assertTrue(receipt["reconciliation"]["clean"])
        self.assertTrue(receipt["cleanup"]["verified_zero_open"])
        self.assertEqual(receipt["status"], "completed")

    # F3 (review B): configurable criteria cannot lower the frozen qualification.
    def test_passed_requires_frozen_criteria(self):
        class GateOnly(fx.FakeBroker):
            evidence_class = "native_paper"  # labels the fixture ONLY to exercise the gate logic

        for windows, ratio, expected in ((5, 0.85, []), (1, 0.85, ["criteria_below_frozen_minimum"]),
                                         (5, 0.5, ["criteria_below_frozen_minimum"])):
            clock = fx.FakeClock()
            receipt = self.harness(GateOnly(clock), clock, max_duration_seconds=330.0,
                                   required_windows=windows, target_actions_ratio=ratio).run()
            self.assertTrue(receipt["acceptance"]["capacity_criteria_met"])
            self.assertEqual(receipt["acceptance"]["passed_blockers"], expected)
            self.assertEqual(receipt["acceptance"]["passed"], expected == [])
            self.assertTrue(receipt["acceptance"]["passed_is_self_reported"])
        receipt, _, _ = run(self.tmp.name)
        self.assertIn("evidence_class_not_native_paper", receipt["acceptance"]["passed_blockers"])

    # F4 (review B): a durable journal and crash recovery.
    def test_crash_mid_run_then_recover_from_journal(self):
        class Crash(BaseException):
            """Stands in for SIGKILL/OOM: nothing after it runs in the process."""

        clock = fx.FakeClock()

        class CrashAt8(fx.FakeBroker):
            def submit(self, *args):
                response = super().submit(*args)
                if self.submit_count == 8:
                    raise Crash()
                return response

        broker = CrashAt8(clock, drop_events={"new"})
        journal = Path(self.tmp.name) / "private" / "run.journal.jsonl"
        cfg = c.CapacityConfig(max_duration_seconds=130.0)
        harness = c.CapacityRun(broker, cfg, clock=clock, executor=c.InlineExecutor(),
                                stop_file=stop_path(self.tmp.name), journal_path=journal)

        def killed():
            raise Crash()
        harness._cleanup = killed  # the process dies: no cleanup, no receipt
        with self.assertRaises(Crash):
            harness.run()
        harness.journal.close()
        prefix = harness.prefix
        self.assertEqual(len(broker.open_orders_with_prefix(prefix)), 8)
        self.assertEqual(journal.stat().st_mode & 0o777, 0o600)
        lines = journal.read_text().splitlines()
        self.assertEqual(json.loads(lines[0])["prefix"], prefix)
        self.assertEqual(len(lines), 9)  # start + 8 intents written before each POST
        text = journal.read_text()
        self.assertNotIn(fx.hashlib.sha256(b"fixture-account").hexdigest(), text)
        # A torn final write: the last intent line is lost mid-record.
        journal.write_text("\n".join(lines[:-1]) + "\n" + lines[-1][:17])
        stop_path(self.tmp.name).write_text("")  # STOP blocks entries, never cancels

        audit = c.CapacityRun(broker, c.CapacityConfig(), clock=clock, executor=c.InlineExecutor(),
                              stop_file=stop_path(self.tmp.name)).recover(journal, cancel=False)
        self.assertEqual(audit["mode"], "audit")
        self.assertEqual(audit["broker_orders_with_prefix"]["by_status"], {"new": 8})
        self.assertEqual(len(broker.open_orders_with_prefix(prefix)), 8)

        receipt = c.CapacityRun(broker, c.CapacityConfig(), clock=clock, executor=c.InlineExecutor(),
                                stop_file=stop_path(self.tmp.name)).recover(journal)
        self.assertEqual((receipt["mode"], receipt["status"]), ("recover", "completed"))
        self.assertEqual(receipt["journal"], {"intents": 7, "end_record_present": False})
        self.assertTrue(receipt["cleanup"]["verified_zero_open"])
        self.assertEqual(broker.open_orders_with_prefix(prefix), [])
        self.assertEqual(receipt["broker_orders_with_prefix"]["by_status"], {"canceled": 8})
        self.assertIs(receipt["counts_as_strategy_trades"], False)
        self.assertIsNone(UUID_TEXT.search(json.dumps(receipt)))

    def test_journal_is_exclusive_and_records_start_and_end(self):
        journal = Path(self.tmp.name) / "j.jsonl"
        clock = fx.FakeClock()
        receipt = c.CapacityRun(fx.FakeBroker(clock), c.CapacityConfig(max_duration_seconds=70.0,
                                                                      required_windows=1),
                                clock=clock, executor=c.InlineExecutor(), stop_file=stop_path(self.tmp.name),
                                journal_path=journal).run()
        parsed = c.read_journal(journal)
        self.assertEqual(parsed["start"]["prefix"], receipt["probe_plan"]["client_order_id_prefix"])
        self.assertEqual(len(parsed["intents"]), receipt["orders"]["submit_attempts"])
        self.assertEqual(parsed["end"]["status"], "completed")
        clock = fx.FakeClock()
        again = c.CapacityRun(fx.FakeBroker(clock), c.CapacityConfig(), clock=clock,
                              executor=c.InlineExecutor(), stop_file=stop_path(self.tmp.name),
                              journal_path=journal).run()
        self.assertEqual((again["status"], again["refusal_reason"]), ("refused", "journal_exists"))
        self.assertEqual(again["orders"]["submit_attempts"], 0)

    # F5 (review B): several calls in flight, out-of-order completion.
    def test_multi_inflight_out_of_order_completion_holds_budget(self):
        clock = fx.FakeClock()
        broker = fx.FakeBroker(clock)
        executor = LaggedExecutor(clock)
        receipt = self.harness(broker, clock, executor, inflight=4, max_duration_seconds=190.0,
                               required_windows=3).run()
        self.assertGreaterEqual(executor.max_pending, 3)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["http_429"]["total"], 0)
        self.assertLessEqual(max_calls_in_rolling_window(broker.call_log), 180 + 4)  # budget + preflight
        reserve = receipt["rate"]["reserve_per_minute"]
        self.assertGreaterEqual(receipt["observed_rate_limit_headers"]["min_remaining_by_origin"]["trading"],
                                reserve - 1)
        self.assertEqual(receipt["websocket"]["completeness"], 1.0)
        self.assertTrue(receipt["reconciliation"]["clean"])
        self.assertTrue(receipt["acceptance"]["capacity_criteria_met"])
        # REST latency is stamped at completion, not when the lagged future was collected.
        self.assertAlmostEqual(receipt["latency"]["submit_rest_ack"]["max_ms"], 30.0, delta=0.5)

    def test_thread_pool_executor_path(self):
        clock = LockedClock()
        broker = LockedBroker(clock)
        receipt = self.harness(broker, clock, executor=None, inflight=4, max_orders=150).run()
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["http_429"]["total"], 0)
        self.assertEqual(receipt["orders"]["submit_attempts"], 150)
        self.assertLessEqual(max_calls_in_rolling_window(broker.call_log), 200)
        self.assertEqual(receipt["websocket"]["completeness"], 1.0)
        self.assertTrue(receipt["cleanup"]["verified_zero_open"])
        self.assertTrue(receipt["reconciliation"]["clean"])

    # F6 (review B): provenance for the receipt.
    def test_receipt_provenance_and_sanitized_argv(self):
        receipt, _, _ = run(self.tmp.name)
        prov = receipt["provenance"]
        for key in ("git_revision", "source_sha256", "alpaca_py_version", "python_version", "argv",
                    "ended_at", "exit_code"):
            self.assertIn(key, prov)
        self.assertEqual(len(prov["source_sha256"]), 8)
        self.assertTrue(all(re.fullmatch(r"[0-9a-f]{64}", v) for v in prov["source_sha256"].values()))
        self.assertEqual(c.sanitize_argv(["paper", "--env-file", "/srv/private/p.env", "--output=/x/y.json",
                                          "--cap", "1000"]),
                         ["paper", "--env-file", "<path>", "--output=<path>", "--cap", "1000"])
        with tempfile.TemporaryDirectory(dir="/tmp") as private:
            out = Path(private) / "receipt.json"
            with restored_signal_handlers(), contextlib.redirect_stdout(io.StringIO()):
                code = c.main(["offline", "--output", str(out), "--duration", "70", "--required-windows", "1"])
            saved = json.loads(out.read_text())
        self.assertEqual(saved["provenance"]["exit_code"], code)
        self.assertEqual(saved["provenance"]["argv"][:3], ["offline", "--output", "<path>"])
        self.assertNotIn(private, json.dumps(saved))

    def test_script_entry_point_shares_one_response_class(self):
        """Run as ``python3 capacity.py`` the ports import ``capacity.Response``;
        completed actions must still be recognised (no __main__ duplicate)."""
        import subprocess
        with tempfile.TemporaryDirectory(dir="/tmp") as private:
            out = Path(private) / "r.json"
            done = subprocess.run([sys.executable, str(SOURCE / "capacity.py"), "offline", "--output", str(out),
                                   "--duration", "130", "--required-windows", "2"],
                                  capture_output=True, text=True, timeout=120, check=False)
            receipt = json.loads(out.read_text())
        self.assertEqual(done.returncode, 0, done.stderr[-2000:])
        self.assertGreaterEqual(receipt["throughput"]["min_order_actions_full_window"], 170)
        self.assertEqual(receipt["throughput"]["order_actions_not_completed_in_phase"], 0)
        self.assertEqual(receipt["port_errors"], 0)

    # F7 (review B): event times are stamped when the stream thread receives them.
    def test_stream_event_time_is_receipt_time_not_drain_time(self):
        clock = fx.FakeClock()
        harness = c.CapacityRun(fx.FakeBroker(clock), c.CapacityConfig(), clock=clock)
        harness.prefix = "cap-20260924t140000-abcdef-"
        cid = harness.prefix + "000001"
        probe = c.Probe(cid, 1, "475.00", 1, False)
        harness.probes[cid] = harness._live[cid] = probe
        received = clock.monotonic()
        harness._on_stream({"data": {"event": "new", "order": {"client_order_id": cid, "id": "u-1",
                                                                "status": "new"}}})
        clock.advance(7.0)  # the main loop was busy
        harness._drain_events()
        self.assertEqual(probe.stream_ack_at, received)
        response, done_at = harness._timed(lambda: clock.advance(0.25) or "ok")
        self.assertEqual((response, done_at), ("ok", received + 7.25))

    # F8 (review B): any health freeze fails the capacity criteria.
    def test_health_freeze_fails_capacity_criteria(self):
        class StopFails(fx.FakeBroker):
            def stop_stream(self):
                super().stop_stream()
                raise RuntimeError("stream thread failed to terminate")

        clock = fx.FakeClock()
        receipt = self.harness(StopFails(clock), clock).run()
        self.assertEqual(receipt["health_freezes"], ["stream_stop_failed"])
        self.assertTrue(receipt["acceptance"]["sustained"])
        self.assertFalse(receipt["acceptance"]["no_health_freezes"])
        self.assertFalse(receipt["acceptance"]["capacity_criteria_met"])

    # F9 (review B): the session reserve covers every post-loop phase.
    def test_session_reserve_covers_stream_start_cleanup_and_reconciliation(self):
        cfg = c.CapacityConfig()
        harness = c.CapacityRun(fx.FakeBroker(fx.FakeClock()), cfg)
        self.assertEqual(harness.post_loop_reserve_seconds(),
                         cfg.stream_start_timeout_seconds + cfg.cleanup_timeout_seconds + 3 * 60.0
                         + c.RECONCILE_SECONDS + c.SESSION_MARGIN_SECONDS)
        close = datetime(2026, 9, 24, 20, 0, tzinfo=timezone.utc).timestamp()
        late = fx.FakeClock(close - 240.0)
        receipt = self.harness(fx.FakeBroker(late), late).run()
        self.assertEqual(receipt["refusal_reason"], "session_ends_too_soon")
        near = fx.FakeClock(close - 600.0)
        harness = self.harness(fx.FakeBroker(near), near, max_duration_seconds=3600.0)
        receipt = harness.run()
        self.assertEqual(receipt["status"], "completed")
        self.assertLessEqual(receipt["throughput"]["submission_phase_seconds"], 600.0 - 315.0 + 0.01)
        self.assertLessEqual(near.time(), close)  # finished, cleanup included, before the close


class EvidenceFileTests(unittest.TestCase):
    def test_rate_limit_evidence_is_current_and_matches_brief(self):
        data = evidence.build()
        totals = data["repository_observations"]["totals_by_origin_and_limit"]
        self.assertEqual(totals, {"data:10000": 9, "trading:200": 419})
        self.assertEqual(len(data["sources"]["items"]), 4)
        committed = json.loads((SOURCE / "rate-limit-evidence-20260924.json").read_text())
        self.assertEqual(committed, data)
        rows = {row["calls_per_minute_limit"]: row for row in data["round_trip_arithmetic"]["by_limit"]}
        self.assertEqual(rows[200]["submit_cancel_pairs_per_minute_max"], 100)
        self.assertEqual(rows[1000]["round_trips_per_minute_two_submits"], 500)


class PullRequestReviewTests(unittest.TestCase):
    """Regressions for the PR #165 review threads."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def harness(self, broker, clock, **config):
        cfg = c.CapacityConfig(**dict({"max_duration_seconds": 130.0, "required_windows": 2}, **config))
        return c.CapacityRun(broker, cfg, clock=clock, executor=c.InlineExecutor(),
                             stop_file=stop_path(self.tmp.name))

    # Reconciliation compares the whole position snapshot, not only the probe symbol.
    def test_non_probe_symbol_position_drift_makes_reconciliation_unclean(self):
        clock = fx.FakeClock()

        class Drift(fx.FakeBroker):
            def positions(self):
                held, responses = super().positions()
                return [dict(p, qty="6") if p["symbol"] == "AAPL" else p for p in held], responses

        broker = Drift(clock, positions=[{"symbol": "AAPL", "qty": "5"}])
        receipt, _, _ = run(self.tmp.name, broker=broker, clock=clock, acknowledged_positions=1)
        rec = receipt["reconciliation"]
        self.assertTrue(rec["position_unchanged"])  # the probe symbol itself did not move
        self.assertFalse(rec["all_positions_unchanged"])
        self.assertEqual(rec["changed_position_symbols"], 1)
        self.assertFalse(rec["clean"])
        self.assertEqual(receipt["status"], "needs_attention")
        # A new nonzero position in another symbol is drift as well.

        class Appears(fx.FakeBroker):
            def positions(self):
                held, responses = super().positions()
                return held + [{"symbol": "MSFT", "qty": "1"}], responses

        broker = Appears(fx.FakeClock())
        receipt, _, _ = run(self.tmp.name, broker=broker, clock=broker.clock)
        self.assertFalse(receipt["reconciliation"]["clean"])
        self.assertEqual(receipt["reconciliation"]["changed_position_symbols"], 1)
        # Unchanged positions stay clean.
        broker = fx.FakeBroker(fx.FakeClock(), positions=[{"symbol": "AAPL", "qty": "5"}])
        receipt, _, _ = run(self.tmp.name, broker=broker, clock=broker.clock, acknowledged_positions=1)
        self.assertTrue(receipt["reconciliation"]["all_positions_unchanged"])
        self.assertTrue(receipt["reconciliation"]["clean"])

    # Stale quotes are refused before any order, and a stale refresh freezes submissions.
    def test_stale_or_undated_quote_fails_closed(self):
        broker = fx.FakeBroker(fx.FakeClock(), quote_age=120.0)
        receipt, _, _ = run(self.tmp.name, broker=broker, clock=broker.clock)
        self.assertEqual((receipt["status"], receipt["refusal_reason"]), ("refused", "quote_stale"))
        self.assertEqual(broker.submit_count, 0)
        broker = fx.FakeBroker(fx.FakeClock(), quote_age=-5.0)  # far ahead of the host clock
        receipt, _, _ = run(self.tmp.name, broker=broker, clock=broker.clock)
        self.assertEqual(receipt["refusal_reason"], "quote_stale")

        class Undated(fx.FakeBroker):
            def latest_quote(self):
                return {"bid": self.bid, "ask": self.ask}

        broker = Undated(fx.FakeClock())
        receipt, _, _ = run(self.tmp.name, broker=broker, clock=broker.clock)
        self.assertEqual(receipt["refusal_reason"], "quote_timestamp_missing")
        self.assertEqual(broker.submit_count, 0)
        broker = fx.FakeBroker(fx.FakeClock(), quote_age=59.0)
        receipt, _, _ = run(self.tmp.name, broker=broker, clock=broker.clock)
        self.assertEqual(receipt["status"], "completed")

    def test_stale_requote_freezes_submissions_and_cleans_up(self):
        clock = fx.FakeClock()

        class AgesLater(fx.FakeBroker):
            def submit(self, *args):
                if self.submit_count == 20:
                    self.quote_age = 600.0
                return super().submit(*args)

        broker = AgesLater(clock)
        receipt, _, _ = run(self.tmp.name, broker=broker, clock=clock)
        self.assertIn("requote_quote_stale", receipt["health_freezes"])
        self.assertTrue(receipt["cleanup"]["verified_zero_open"])
        self.assertFalse(receipt["acceptance"]["capacity_criteria_met"])

    def test_native_port_keeps_quote_timestamp(self):
        import alpaca_capacity_port as native
        port = native.AlpacaCapacityPort("k", "s", "SPY")
        pre = {"account_identity_sha256": "a" * 64, "positions": [], "orders": [],
               "open_orders_complete": True, "assets": [{"symbol": "SPY", "tradable": True, "status": "active"}],
               "quotes": [{"symbol": "SPY", "bid": "500", "ask": "500.02", "ts_ns": 1_790_000_000_000_000_000}]}
        original, native.transport.preflight = native.transport.preflight, lambda *a, **k: pre
        port._ensure_pool = lambda: None
        try:
            self.assertEqual(port.preflight()["quote"]["ts_ns"], 1_790_000_000_000_000_000)
        finally:
            native.transport.preflight = original

    # Recovery needs only the trading endpoint.
    def test_recover_survives_market_data_outage(self):
        class Crash(BaseException):
            pass

        clock = fx.FakeClock()

        class CrashAt5(fx.FakeBroker):
            def submit(self, *args):
                response = super().submit(*args)
                if self.submit_count == 5:
                    raise Crash()
                return response

        broker = CrashAt5(clock, drop_events={"new"})
        journal = Path(self.tmp.name) / "private" / "run.journal.jsonl"
        harness = c.CapacityRun(broker, c.CapacityConfig(max_duration_seconds=130.0), clock=clock,
                                executor=c.InlineExecutor(), stop_file=stop_path(self.tmp.name),
                                journal_path=journal)

        def killed():
            raise Crash()
        harness._cleanup = killed
        with self.assertRaises(Crash):
            harness.run()
        harness.journal.close()
        prefix = harness.prefix
        self.assertEqual(len(broker.open_orders_with_prefix(prefix)), 5)
        broker.market_data_available = False
        with self.assertRaises(RuntimeError):
            broker.preflight()  # the full preflight would fail before any cancel
        receipt = c.CapacityRun(broker, c.CapacityConfig(), clock=clock, executor=c.InlineExecutor(),
                                stop_file=stop_path(self.tmp.name)).recover(journal)
        self.assertEqual((receipt["mode"], receipt["status"]), ("recover", "completed"))
        self.assertTrue(receipt["cleanup"]["verified_zero_open"])
        self.assertEqual(broker.open_orders_with_prefix(prefix), [])

    def test_native_recovery_preflight_reads_only_the_trading_account(self):
        import hashlib
        import alpaca_capacity_port as native
        seen = {}

        class Session:
            def close(self):
                seen["closed"] = True

        class Client:
            def __init__(self, observer):
                self.observer, self._session = observer, Session()

            def get_account(self):
                self.observer({"kind": "read", "status": 200, "headers": {"x-ratelimit-limit": "200"}})
                return {"id": "account-1"}

        def sdk_client(key, secret, before, observer=None, *, data=False, read_only=False, lock=None):
            seen.setdefault("clients", []).append((data, read_only))
            return Client(observer)

        def no_full_preflight(*args, **kwargs):
            raise AssertionError("recovery must not read assets or market data")

        port = native.AlpacaCapacityPort("k", "s", "SPY")
        port._ensure_pool = lambda: None
        saved = native.transport._sdk_client, native.transport.preflight
        native.transport._sdk_client, native.transport.preflight = sdk_client, no_full_preflight
        try:
            pre = port.recovery_preflight()
        finally:
            native.transport._sdk_client, native.transport.preflight = saved
        self.assertEqual(seen["clients"], [(False, True)])  # one read-only trading client, no data client
        self.assertTrue(seen["closed"])
        self.assertEqual(pre["account_identity_sha256"], hashlib.sha256(b"account-1").hexdigest())
        self.assertEqual([o["origin"] for o in pre["observations"]], ["trading"])

    # A broker-designated delay longer than max_backoff is honoured in full.
    def test_retry_after_beyond_max_backoff_is_honoured(self):
        gov, clock = governor()
        self.assertTrue(gov.try_acquire("submit"))
        self.assertEqual(gov.on_response("submit", 429, {"retry-after": "300"}), 300.0)
        self.assertEqual(gov.summary()["backoffs_over_max"], 1)
        clock.t += 299.0
        self.assertFalse(gov.try_acquire("submit"))
        clock.t += 2.0
        self.assertTrue(gov.try_acquire("submit"))
        gov, clock = governor()
        reset = str(int(clock.wall()) + 120)
        self.assertAlmostEqual(gov.on_response("submit", 429, {"x-ratelimit-reset": reset}), 120.0, delta=1.0)
        # Only the harness's own exponential fallback is capped.
        gov, _ = governor(max_backoff=2.0)
        self.assertEqual([gov.on_response("submit", 429, {}) for _ in range(3)], [1.0, 2.0, 2.0])
        self.assertEqual(gov.stats["backoffs_over_max"], 0)

    def test_long_retry_after_stops_submissions_without_sending_while_frozen(self):
        clock = fx.FakeClock()
        broker = fx.FakeBroker(clock, force_429_calls={25}, retry_after="90")
        receipt, _, _ = run(self.tmp.name, broker=broker, clock=clock)
        self.assertEqual(receipt["stop_reason"], "rate_limit_backoff_exceeds_max")
        self.assertEqual(receipt["rate"]["backoffs"][0]["seconds"], 90.0)
        rejected = broker.call_log[24]["t"]
        self.assertGreaterEqual(broker.call_log[25]["t"] - rejected, 90.0 - 0.05)
        self.assertTrue(receipt["cleanup"]["verified_zero_open"])


# -- live mode (synthetic port only: no credentials, no network, no broker) --------------

HAS_ALPACA_SDK = importlib.util.find_spec("alpaca") is not None
HAS_REQUESTS = importlib.util.find_spec("requests") is not None


def iso(wall):
    return datetime.fromtimestamp(wall, timezone.utc).isoformat().replace("+00:00", "Z")


class LiveFakeBroker(fx.FakeBroker):
    """The offline fake broker plus the broker clock the live preflight reads (running
    ``clock_skew`` seconds behind the host clock, read over ``clock_round_trip``), the
    quote wall time each submit carries, and a fill price on fills. Its evidence class
    stays offline_fixture."""

    def __init__(self, clock, *, market_open=True, clock_skew=0.0, clock_round_trip=0.1, **kwargs):
        super().__init__(clock, **kwargs)
        self.market_open = market_open
        self.clock_skew, self.clock_round_trip = clock_skew, clock_round_trip
        self.quote_walls = []

    def preflight(self):
        sent = self.clock.time()
        broker = sent + self.clock_round_trip / 2 - self.clock_skew
        broker_clock = {"timestamp": iso(broker), "host_sent_wall": sent,
                        "host_received_wall": sent + self.clock_round_trip}
        return dict(super().preflight(), market_open=self.market_open, broker_clock=broker_clock)

    def submit(self, cid, symbol, qty, limit_price, extended_hours, quote_wall=None):
        self.quote_walls.append(quote_wall)
        return super().submit(cid, symbol, qty, limit_price, extended_hours)

    def _emit(self, event, order):
        if event in ("fill", "partial_fill"):
            order["filled_avg_price"] = order["limit_price"]
        super()._emit(event, order)


class LiveCapacityTests(unittest.TestCase):
    """Every live gate, the caps and the fill rule, against the fake broker only."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.env = self.root / "alpaca-live-capacity.env"  # judged by name; never read by these runs
        self.written = 0

    def go(self, at=fx.DEFAULT_WALL_START, mode=0o600, raw=None, **fields):
        """A temporary go file as the user would write it (never the real one)."""
        data = {"live_capacity_go": True, "issued_at": iso(at - 600), "expires_at": iso(at + 6 * 3600),
                "max_order_actions": 2000, "max_open_notional_usd": 2000, "note": "capacity probes; user go"}
        data.update(fields)
        self.written += 1
        path = self.root / ("go-%d.json" % self.written)
        path.write_text(raw if raw is not None else json.dumps(data))
        os.chmod(path, mode)
        return path

    def harness(self, *, go=None, broker=None, clock=None, env=None, journal=None, **config):
        clock = clock or fx.FakeClock()
        broker = broker or LiveFakeBroker(clock)
        broker.clock = clock
        cfg = c.LiveCapacityConfig(**dict({"max_duration_seconds": 130.0, "required_windows": 2,
                                          "live_orders_acknowledged": True}, **config))
        harness = c.LiveCapacityRun(broker, cfg, clock=clock, executor=c.InlineExecutor(),
                                    stop_file=self.root / "STOP",
                                    live_stop_file=self.root / "alpaca-live" / "STOP",
                                    go_file=go or self.go(at=clock.time()), env_file=env or self.env,
                                    journal_path=journal)
        return harness, broker

    def live(self, **kwargs):
        harness, broker = self.harness(**kwargs)
        return harness.run(), harness, broker

    def assert_refused_before_any_request(self, receipt, broker, reason):
        self.assertEqual((receipt["status"], receipt["refusal_reason"]), ("refused", reason))
        self.assertEqual(broker.call_log, [])
        self.assertEqual(receipt["orders"]["submit_attempts"], 0)

    def test_live_run_reuses_the_engine_and_reports_native_live_evidence(self):
        class NativeLabel(LiveFakeBroker):
            evidence_class = "native_live"  # labels the fixture ONLY to exercise the receipt logic

        clock = fx.FakeClock()
        go = self.go(at=clock.time())
        broker = NativeLabel(clock)
        receipt, _, _ = self.live(go=go, broker=broker, clock=clock, max_duration_seconds=330.0,
                                  required_windows=5)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["evidence_class"], "native_live")
        self.assertIs(receipt["counts_as_strategy_trades"], False)
        self.assertEqual(receipt["strategy_trades"], 0)
        self.assertEqual(receipt["config"]["base_url"], "https://api.alpaca.markets")
        self.assertEqual(receipt["session_kind"], "RTH")
        self.assertFalse(receipt["extended_hours_orders"])
        self.assertEqual(broker.extended_hours_flags, {False})
        # Budget = floor(min(--cap 1000, observed limit 200) * 0.9).
        self.assertEqual((receipt["rate"]["configured_cap_per_minute"], receipt["rate"]["budget_per_minute"]),
                         (1000, 180))
        self.assertEqual(receipt["probe_plan"]["limit_price"], "475.00")  # 500 bps below the 500.00 bid
        self.assertEqual(receipt["probe_plan"]["time_in_force"], "day")
        live = receipt["live"]
        self.assertEqual((live["user_go"]["required"], live["user_go"]["verified"], live["user_go"]["sha256"]),
                         (True, True, hashlib.sha256(go.read_bytes()).hexdigest()))
        self.assertGreater(live["user_go"]["rechecks"]["performed"], 0)
        self.assertIsNone(live["user_go"]["rechecks"]["stopped_by"])
        self.assertTrue(live["order_actions"]["within_cap"])
        self.assertEqual((live["fills"], live["filled_qty_total"], live["auto_sell"]), ([], "0", False))
        self.assertGreater(live["position_checks"]["completed"], 0)
        self.assertEqual(live["position_checks"]["changes_detected"], 0)
        self.assertTrue(receipt["acceptance"]["evidence_class_qualifies"])
        self.assertTrue(receipt["acceptance"]["capacity_criteria_met"])
        self.assertEqual(receipt["acceptance"]["passed_blockers"], [])
        self.assertEqual(broker.cancel_all_calls, 0)
        self.assertEqual(broker.open_orders_with_prefix(receipt["probe_plan"]["client_order_id_prefix"]), [])
        text = json.dumps(receipt)
        self.assertIsNone(UUID_TEXT.search(text))  # no broker order ids
        self.assertNotIn(fx.hashlib.sha256(b"fixture-account").hexdigest(), text)  # no account identity
        self.assertNotIn("capacity probes; user go", text)  # the go file's content never reaches the receipt
        # The fixture itself never qualifies.
        receipt, _, _ = self.live()
        self.assertIn("evidence_class_not_native_live", receipt["acceptance"]["passed_blockers"])

    def test_go_file_gate_refuses_before_any_request(self):
        wall = fx.DEFAULT_WALL_START
        link = self.root / "go-link.json"
        link.symlink_to(self.go())
        expired = self.go(issued_at=iso(wall - 3600), expires_at=iso(wall - 1))
        cases = [
            (self.root / "absent.json", "live_go_file_missing"),
            (expired, "live_go_file_expired"),
            (self.go(mode=0o644), "live_go_file_mode_not_0600"),
            (self.go(mode=0o400), "live_go_file_mode_not_0600"),
            (link, "live_go_file_not_regular"),
            (self.go(live_capacity_go=False), "live_go_false"),
            (self.go(raw="{not json"), "live_go_file_malformed"),
            (self.go(issued_at=iso(wall - 3600), expires_at=iso(wall - 3600 + 24 * 3600 + 1)),
             "live_go_validity_exceeds_24h"),
            (self.go(issued_at=iso(wall + 3600), expires_at=iso(wall + 7200)), "live_go_not_yet_valid"),
        ]
        for path, reason in cases:
            with self.subTest(reason=reason, path=path.name):
                receipt, _, broker = self.live(go=path)
                self.assert_refused_before_any_request(receipt, broker, reason)
                self.assertIsNone(receipt["live"]["caps_used"])
                self.assertFalse(receipt["live"]["user_go"]["verified"])
        receipt, _, _ = self.live(go=expired)
        self.assertEqual(receipt["live"]["user_go"]["sha256"], hashlib.sha256(expired.read_bytes()).hexdigest())
        receipt, _, _ = self.live(go=self.root / "absent.json")
        self.assertIsNone(receipt["live"]["user_go"]["sha256"])
        with mock.patch.object(c.os, "getuid", return_value=os.getuid() + 1):
            receipt, _, broker = self.live(go=self.go())
        self.assert_refused_before_any_request(receipt, broker, "live_go_file_not_owned_by_user")

    def test_go_file_is_read_but_never_written(self):
        go = self.go()
        before = (go.read_bytes(), go.stat().st_mode, go.stat().st_mtime_ns)
        receipt, _, _ = self.live(go=go)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual((go.read_bytes(), go.stat().st_mode, go.stat().st_mtime_ns), before)
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), [go.name])

    def test_go_file_content_rules(self):
        now = fx.DEFAULT_WALL_START
        good = {"live_capacity_go": True, "issued_at": iso(now - 60), "expires_at": iso(now + 3600),
                "max_order_actions": 400, "max_open_notional_usd": 1500.5, "note": "probe capacity"}

        def parse(raw=None, **changes):
            return c.parse_live_go(raw if raw is not None else json.dumps(dict(good, **changes)).encode(), now)

        go = parse()
        self.assertEqual((go.max_order_actions, go.max_open_notional_usd), (400, Decimal("1500.5")))
        parse(issued_at=iso(now - 60), expires_at=iso(now - 60 + 24 * 3600))  # exactly 24 h is allowed
        parse(issued_at="2026-09-24T09:59:00-04:00")  # any explicit offset
        malformed = [{"live_capacity_go": 1}, {"live_capacity_go": "true"}, {"max_order_actions": True},
                     {"max_order_actions": 2.5}, {"max_order_actions": 0}, {"max_open_notional_usd": "1500"},
                     {"max_open_notional_usd": 0}, {"max_open_notional_usd": -5}, {"note": ""}, {"note": 7},
                     {"issued_at": "2026-09-24T13:59:00"}, {"expires_at": "tomorrow"},
                     {"expires_at": iso(now - 120)}, {"extra": 1}]
        for changes in malformed:
            with self.subTest(changes=changes):
                with self.assertRaises(c.HarnessRefusal) as raised:
                    parse(**changes)
                self.assertEqual(str(raised.exception), "live_go_file_malformed")
        missing_note = {key: value for key, value in good.items() if key != "note"}
        for raw in (json.dumps(missing_note).encode(), b"[]", b"\xff",
                    json.dumps(good).replace("1500.5", "NaN").encode(),
                    b'{"note": "a", "note": "b"}'):
            with self.assertRaises(c.HarnessRefusal) as raised:
                parse(raw=raw)
            self.assertEqual(str(raised.exception), "live_go_file_malformed")
        with self.assertRaises(c.HarnessRefusal) as raised:
            parse(raw=b'{"live_capacity_go": false}')
        self.assertEqual(str(raised.exception), "live_go_false")  # a revoked go needs no other field

    def test_explicit_acknowledgement_comes_before_reading_the_go_file(self):
        receipt, _, broker = self.live(go=self.root / "absent.json", live_orders_acknowledged=False)
        self.assert_refused_before_any_request(receipt, broker, "live_orders_not_acknowledged")
        self.assertIsNone(receipt["live"]["user_go"]["sha256"])  # the go file was not even read

    def test_env_file_gate_by_name(self):
        target = self.root / "alpaca-paper-agentlab.env"
        target.write_text("")
        link = self.root / "alpaca-live-link.env"
        link.symlink_to(target)
        cases = [(self.root / "alpaca-paper-capacity.env", "paper_env_file_in_live_mode"),
                 (self.root / "paper.env", "paper_env_file_in_live_mode"),
                 (link, "paper_env_file_in_live_mode"),  # a live name that resolves to a paper file
                 (self.root / "credentials.env", "live_env_file_name_required"),
                 (self.root / "alpaca-live.env", "live_env_file_name_required")]
        for env, reason in cases:
            with self.subTest(env=env.name):
                receipt, _, broker = self.live(env=env)
                self.assert_refused_before_any_request(receipt, broker, reason)
        self.assertEqual(c.live_base_url_refusal("https://paper-api.alpaca.markets/"), "paper_base_url_in_live_env")
        self.assertEqual(c.live_base_url_refusal("https://example.invalid"), "non_live_base_url")
        self.assertIsNone(c.live_base_url_refusal("https://api.alpaca.markets/"))
        self.assertIsNone(c.live_base_url_refusal(None))
        self.assertEqual(c.paper_env_refusal(self.env), "live_env_file_in_paper_mode")
        self.assertIsNone(c.paper_env_refusal(self.root / "alpaca-paper-capacity.env"))
        self.assertIsNone(c.paper_env_refusal(self.root / "paper.env"))

    def test_live_env_base_url_is_checked_before_the_live_port_is_built(self):
        """The CLI's port factory: credentials (temporary fixture file), then the base URL."""
        with tempfile.TemporaryDirectory(dir="/tmp") as private:
            env = Path(private) / "alpaca-live-capacity.env"
            env.write_text("APCA_API_KEY_ID=fixturekey\nAPCA_API_SECRET_KEY=fixturesecret\n"
                           "APCA_API_BASE_URL=https://paper-api.alpaca.markets\n")
            os.chmod(env, 0o600)
            args = c.build_parser().parse_args(["live", "--env-file", str(env), "--output", "x.json"])
            harness = c.LiveCapacityRun(LiveFakeBroker(fx.FakeClock()), c.LiveCapacityConfig())
            with mock.patch("alpaca_capacity_port.AlpacaLiveCapacityPort",
                            side_effect=AssertionError("live port built")):
                with self.assertRaises(c.HarnessRefusal) as raised:
                    c._live_port_factory(args, harness)()
                self.assertEqual(str(raised.exception), "paper_base_url_in_live_env")
                os.chmod(env, 0o644)  # runner.credentials refuses it; nothing is echoed
                with self.assertRaises(c.HarnessRefusal) as raised:
                    c._live_port_factory(args, harness)()
                self.assertEqual(str(raised.exception), "live_env_file_rejected")

    def test_regular_trading_hours_only(self):
        cases = [(datetime(2026, 9, 24, 11, 0, tzinfo=timezone.utc), "PRE"),     # 07:00 ET
                 (datetime(2026, 9, 24, 21, 0, tzinfo=timezone.utc), "POST"),    # 17:00 ET
                 (datetime(2026, 9, 26, 15, 0, tzinfo=timezone.utc), "CLOSED"),  # Saturday
                 (datetime(2026, 11, 26, 16, 0, tzinfo=timezone.utc), "CLOSED"),  # Thanksgiving
                 (datetime(2026, 11, 27, 18, 30, tzinfo=timezone.utc), "POST")]  # 13:30 ET, after the early close
        for when, kind in cases:
            with self.subTest(when=when.isoformat()):
                clock = fx.FakeClock(when.timestamp())
                receipt, _, broker = self.live(clock=clock, broker=LiveFakeBroker(clock))
                self.assert_refused_before_any_request(receipt, broker, "live_outside_regular_trading_hours")
                self.assertEqual(receipt["session_kind"], kind)
        # 13:30 ET on a full day is regular hours.
        clock = fx.FakeClock(datetime(2026, 9, 24, 17, 30, tzinfo=timezone.utc).timestamp())
        receipt, _, _ = self.live(clock=clock, broker=LiveFakeBroker(clock))
        self.assertEqual((receipt["status"], receipt["session_kind"]), ("completed", "RTH"))
        # Early close: the run must finish, cleanup included, before 13:00 ET.
        clock = fx.FakeClock(datetime(2026, 11, 27, 17, 56, tzinfo=timezone.utc).timestamp())  # 12:56 ET
        receipt, _, _ = self.live(clock=clock, broker=LiveFakeBroker(clock))
        self.assertEqual(receipt["refusal_reason"], "session_ends_too_soon")
        # The broker's own clock must agree that the market is open.
        clock = fx.FakeClock()
        broker = LiveFakeBroker(clock, market_open=False)
        receipt, _, _ = self.live(clock=clock, broker=broker)
        self.assertEqual(receipt["refusal_reason"], "live_broker_reports_market_closed")
        self.assertEqual(broker.submit_count, 0)

    def test_open_orders_at_preflight_refuse_and_cancel_all_stays_disabled(self):
        clock = fx.FakeClock()
        broker = LiveFakeBroker(clock, foreign_open_orders=1)
        receipt, _, _ = self.live(broker=broker, clock=clock)
        self.assertEqual(receipt["refusal_reason"], "live_account_has_open_orders")
        self.assertEqual((broker.submit_count, broker.cancel_all_calls), (0, 0))
        self.assertEqual(broker.orders["strategy-foreign-0"]["status"], "new")  # untouched
        receipt, _, broker = self.live(acknowledged_open_orders=1)
        self.assert_refused_before_any_request(receipt, broker, "live_requires_zero_open_orders")
        receipt, _, broker = self.live(allow_cancel_all=True)
        self.assert_refused_before_any_request(receipt, broker, "live_cancel_all_disabled")
        # Probes still open at cleanup are cancelled individually, never with cancel-all.
        clock = fx.FakeClock()
        broker = LiveFakeBroker(clock, drop_events={"new"})
        receipt, _, _ = self.live(broker=broker, clock=clock)
        self.assertEqual(broker.cancel_all_calls, 0)
        self.assertEqual(receipt["cleanup"]["cancel_all_decision"], "not_enabled")
        self.assertGreater(receipt["cleanup"]["individual_cancels"], 0)
        self.assertTrue(receipt["cleanup"]["verified_zero_open"])

    def test_band_below_500_bps_refuses(self):
        for band in (499, 100):
            with self.subTest(band=band):
                receipt, _, broker = self.live(band_bps=band)
                self.assert_refused_before_any_request(receipt, broker, "live_band_bps_below_500")
        c.CapacityConfig(band_bps=100).validate()  # paper bounds are unchanged
        receipt, _, _ = self.live(band_bps=1000)
        self.assertEqual(receipt["probe_plan"]["limit_price"], "450.00")

    def test_caps_are_the_minimum_of_cli_go_file_and_live_ceilings(self):
        clock = fx.FakeClock()
        go = self.go(at=clock.time(), max_order_actions=120, max_open_notional_usd=900)
        broker = LiveFakeBroker(clock, drop_events={"new"})  # probes stay open, so the open cap binds
        receipt, _, _ = self.live(go=go, broker=broker, clock=clock, max_order_actions=80,
                                  max_open_notional_usd="10000")
        caps, binding = receipt["live"]["caps_used"], receipt["live"]["cap_binding"]
        self.assertEqual((caps["max_order_actions"], binding["max_order_actions"]), (80, ["cli"]))
        self.assertEqual((caps["max_open_notional_usd"], binding["max_open_notional_usd"]), ("900", ["go_file"]))
        self.assertEqual((caps["max_order_notional_usd"], binding["max_order_notional_usd"]), ("900", ["go_file"]))
        self.assertEqual(receipt["config"]["max_order_actions"], 80)
        self.assertEqual(broker.submit_count, 1)  # 475 open; a second probe (950) would exceed 900
        # The go file's lower action cap binds when the CLI asks for more.
        receipt, _, _ = self.live(go=self.go(max_order_actions=60), max_order_actions=5000)
        self.assertEqual(receipt["live"]["caps_used"]["max_order_actions"], 60)
        self.assertEqual(receipt["live"]["cap_binding"]["max_order_actions"], ["go_file"])
        # A go file above the live ceilings is clipped to 2000 open and 1000 per order.
        receipt, _, _ = self.live(go=self.go(max_order_actions=50, max_open_notional_usd=5000),
                                  max_open_notional_usd="10000", max_order_notional_usd="5000")
        caps, binding = receipt["live"]["caps_used"], receipt["live"]["cap_binding"]
        self.assertEqual((caps["max_open_notional_usd"], caps["max_order_notional_usd"]), ("2000", "1000"))
        self.assertEqual((binding["max_open_notional_usd"], binding["max_order_notional_usd"]),
                         (["live_ceiling"], ["live_ceiling"]))
        # The per-order cap follows the go file's cap too: a 475 probe cannot fit under 400.
        receipt, _, broker = self.live(go=self.go(max_open_notional_usd=400))
        self.assertEqual(receipt["refusal_reason"], "order_notional_cap_exceeded")
        self.assertEqual(broker.submit_count, 0)
        # A cap too small for one probe and its worst-case cancels refuses before any request.
        receipt, _, broker = self.live(go=self.go(max_order_actions=6))
        self.assert_refused_before_any_request(receipt, broker, "live_order_action_cap_below_one_probe")

    def order_actions_at_broker(self, broker):
        return sum(1 for row in broker.call_log if row["kind"] in ("submit", "cancel"))

    def test_total_order_actions_never_exceed_the_cap(self):
        clock = fx.FakeClock()
        receipt, _, broker = self.live(go=self.go(at=clock.time(), max_order_actions=40), clock=clock)
        sent = self.order_actions_at_broker(broker)
        self.assertLessEqual(sent, 40)
        self.assertEqual(receipt["live"]["order_actions"]["sent"], sent)
        self.assertEqual(receipt["stop_reason"], "order_action_cap_reached")
        self.assertTrue(receipt["cleanup"]["verified_zero_open"])

    def test_cleanup_cancels_fit_the_cap_in_the_worst_case(self):
        """The first probe's cancel is refused (429) five times, so it uses every
        reserved cancel: three individual attempts, then one prefix-sweep cancel in
        each of the three cleanup verification rounds. The cap still holds."""

        class StubbornCancel(LiveFakeBroker):
            refused = 0

            def cancel(self, order_id):
                first = next(iter(self.orders.values()))["id"]
                if order_id == first and self.refused < 5:
                    self.refused += 1
                    self.clock.advance(self.cancel_latency)
                    self.call_log.append({"t": self.clock.monotonic(), "kind": "cancel"})
                    return c.Response(429, {"retry-after": "1"})
                return super().cancel(order_id)

        clock = fx.FakeClock()
        broker = StubbornCancel(clock)
        receipt, harness, _ = self.live(go=self.go(at=clock.time(), max_order_actions=30), broker=broker,
                                        clock=clock, max_http_429=10)
        first = min(harness.probes.values(), key=lambda probe: probe.seq)
        self.assertEqual(first.cancel_attempts, c.CANCELS_RESERVED_PER_PROBE)  # 6
        self.assertEqual(broker.refused, 5)
        sent = self.order_actions_at_broker(broker)
        self.assertLessEqual(sent, 30)
        self.assertEqual(receipt["live"]["order_actions"]["sent"], sent)
        self.assertTrue(receipt["live"]["order_actions"]["within_cap"])
        self.assertNotIn("order_action_cap_exhausted", receipt["health_freezes"])
        self.assertTrue(receipt["cleanup"]["verified_zero_open"])
        self.assertEqual(broker.open_orders_with_prefix(receipt["probe_plan"]["client_order_id_prefix"]), [])
        self.assertEqual(receipt["http_429"]["total"], 5)

    def test_fill_stops_submissions_cancels_open_probes_and_never_sells(self):
        class FillsThird(LiveFakeBroker):
            def _emit(self, event, order):
                if event == "new" and order["client_order_id"][-6:] in ("000001", "000002"):
                    return  # not acknowledged yet, so still open when the third probe fills
                super()._emit(event, order)

        clock = fx.FakeClock()
        broker = FillsThird(clock, fill_submit_seqs={3})
        receipt, _, _ = self.live(broker=broker, clock=clock)
        prefix = receipt["probe_plan"]["client_order_id_prefix"]
        self.assertEqual(receipt["status"], "needs_attention")
        self.assertEqual(receipt["stop_reason"], "frozen:unexpected_fill")
        self.assertEqual(broker.submit_count, 3)  # nothing submitted after the fill
        self.assertEqual(broker.open_orders_with_prefix(prefix), [])  # probes 1 and 2 were cancelled
        self.assertGreaterEqual(receipt["cleanup"]["individual_cancels"], 2)
        self.assertEqual(len(broker.orders), 3)
        self.assertEqual({order["side"] for order in broker.orders.values()}, {"buy"})  # no sell order
        held, _ = broker.positions()
        self.assertEqual(held, [{"symbol": "SPY", "qty": "1"}])  # the fill is left for the user
        live = receipt["live"]
        self.assertEqual(live["fills"], [{
            "kind": "probe_fill", "seq": 3, "symbol": "SPY",
            "stream": {"filled_qty": "1", "filled_avg_price": "475.00", "event": "fill"},
            "broker": {"filled_qty": "1", "filled_avg_price": "475.00", "status": "filled"}}])
        self.assertEqual((live["filled_qty_total"], live["auto_sell"]), ("1", False))
        self.assertEqual(receipt["orders"]["unexpected_fill_qty"], "1")
        self.assertEqual(receipt["reconciliation"]["filled_probes"], [3])
        self.assertFalse(receipt["acceptance"]["capacity_criteria_met"])

    def test_foreign_fill_or_position_change_stops_the_run(self):
        class ForeignFill(LiveFakeBroker):
            def submit(self, *args):
                response = super().submit(*args)
                if self.submit_count == 5:
                    self.callback({"stream": "trade_updates", "data": {"event": "fill", "order": {
                        "client_order_id": "manual-1", "id": "m-1", "status": "filled", "filled_qty": "2"}}})
                return response

        clock = fx.FakeClock()
        receipt, _, broker = self.live(broker=ForeignFill(clock), clock=clock)
        self.assertEqual(receipt["stop_reason"], "frozen:live_position_change")
        self.assertEqual(receipt["live"]["foreign_fill_events"], 1)
        self.assertEqual(receipt["status"], "needs_attention")
        self.assertEqual(broker.submit_count, 5)
        self.assertTrue(receipt["cleanup"]["verified_zero_open"])

        clock = fx.FakeClock()
        start = clock.time()

        class Drift(LiveFakeBroker):
            """A position change with no trade update (e.g. a transfer): found by the position check."""
            def positions(self):
                held, responses = super().positions()
                if self.clock.time() - start > 30:
                    held = held + [{"symbol": "MSFT", "qty": "3"}]
                return held, responses

        receipt, _, broker = self.live(broker=Drift(clock), clock=clock)
        self.assertEqual(receipt["stop_reason"], "frozen:live_position_change")
        self.assertEqual(receipt["live"]["position_checks"]["changes_detected"], 1)
        self.assertEqual(receipt["status"], "needs_attention")
        self.assertLess(receipt["throughput"]["submission_phase_seconds"], 45.0)
        self.assertTrue(receipt["cleanup"]["verified_zero_open"])

        class Garbled(LiveFakeBroker):
            def submit(self, *args):
                response = super().submit(*args)
                if self.submit_count == 4:
                    self.callback({"stream": "trade_updates", "data": {"event": "fill"}})
                return response

        clock = fx.FakeClock()
        receipt, _, broker = self.live(broker=Garbled(clock), clock=clock)
        self.assertIn("live_malformed_stream_event", receipt["health_freezes"])
        self.assertEqual((receipt["status"], broker.submit_count), ("needs_attention", 4))

    def test_host_and_live_stop_files_are_honoured(self):
        live_stop = self.root / "alpaca-live" / "STOP"
        live_stop.parent.mkdir()
        live_stop.write_text("")
        receipt, _, broker = self.live()
        self.assert_refused_before_any_request(receipt, broker, "stop_file_present")
        self.assertEqual(receipt["live"]["stop_files_seen"], ["live"])
        live_stop.unlink()
        (self.root / "STOP").write_text("")
        receipt, _, broker = self.live()
        self.assert_refused_before_any_request(receipt, broker, "stop_file_present")
        self.assertEqual(receipt["live"]["stop_files_seen"], ["host"])
        (self.root / "STOP").unlink()

        class LiveStopAt20(LiveFakeBroker):
            def submit(self, *args):
                response = super().submit(*args)
                if self.submit_count == 20:
                    live_stop.write_text("")
                return response

        clock = fx.FakeClock()
        receipt, _, broker = self.live(broker=LiveStopAt20(clock), clock=clock)
        self.assertEqual(receipt["stop_reason"], "stop_file_present")
        self.assertEqual(broker.submit_count, 20)
        self.assertTrue(receipt["cleanup"]["verified_zero_open"])

    def test_revoking_or_changing_the_go_mid_run_stops_submissions(self):
        def edits(go, change):
            class EditsAt10(LiveFakeBroker):
                def submit(self, *args):
                    response = super().submit(*args)
                    if self.submit_count == 10:
                        change(go)  # the user edits their own go file mid-run
                    return response
            return EditsAt10

        def revoke(path):
            path.write_text(json.dumps(dict(json.loads(path.read_text()), live_capacity_go=False)))

        def lower(path):
            path.write_text(json.dumps(dict(json.loads(path.read_text()), max_order_actions=100)))

        for change, freeze, stopped_by in ((revoke, "live_go_revoked", "live_go_false"),
                                           (lambda path: path.unlink(), "live_go_revoked", "live_go_file_missing"),
                                           (lower, "live_go_changed", "live_go_file_changed")):
            with self.subTest(freeze=freeze, stopped_by=stopped_by):
                clock = fx.FakeClock()
                go = self.go(at=clock.time())
                receipt, _, broker = self.live(go=go, broker=edits(go, change)(clock), clock=clock)
                self.assertEqual(receipt["stop_reason"], "frozen:" + freeze)
                self.assertEqual(receipt["live"]["user_go"]["rechecks"]["stopped_by"], stopped_by)
                self.assertLess(receipt["throughput"]["submission_phase_seconds"], 25.0)
                self.assertTrue(receipt["cleanup"]["verified_zero_open"])
                self.assertEqual(broker.open_orders_with_prefix(receipt["probe_plan"]["client_order_id_prefix"]), [])

    def test_go_expiry_mid_run_stops_submissions(self):
        clock = fx.FakeClock()
        go = self.go(issued_at=iso(clock.time() - 3600), expires_at=iso(clock.time() + 40))
        receipt, _, _ = self.live(go=go, clock=clock)
        self.assertEqual(receipt["stop_reason"], "live_go_expired")
        self.assertLess(receipt["throughput"]["submission_phase_seconds"], 45.0)
        self.assertTrue(receipt["cleanup"]["verified_zero_open"])

    def test_paper_and_offline_paths_are_unchanged(self):
        receipt, _, _ = run(self.tmp.name)
        self.assertNotIn("live", receipt)
        self.assertEqual(receipt["config"]["configured_cap_per_minute"], 200)
        with self.assertRaises(c.HarnessRefusal) as raised:
            c.CapacityConfig(base_url=c.LIVE_URL).validate()
        self.assertEqual(str(raised.exception), "non_paper_base_url")  # paper-only validation as before
        # The paper engine never drives a live-origin port, and the live engine never a paper one.

        class LiveOrigin(fx.FakeBroker):
            trading_origin = "https://api.alpaca.markets"

        clock = fx.FakeClock()
        broker = LiveOrigin(clock)
        receipt = c.CapacityRun(broker, c.CapacityConfig(), clock=clock, executor=c.InlineExecutor(),
                                stop_file=stop_path(self.tmp.name)).run()
        self.assert_refused_before_any_request(receipt, broker, "port_trading_origin_mismatch")

        class PaperOrigin(LiveFakeBroker):
            trading_origin = "https://paper-api.alpaca.markets"

        clock = fx.FakeClock()
        receipt, _, broker = self.live(broker=PaperOrigin(clock), clock=clock)
        self.assert_refused_before_any_request(receipt, broker, "port_trading_origin_mismatch")

    def cli(self, argv):
        """c.main with every credential read and native port construction forbidden."""
        out = self.root / ("receipt-%d.json" % len(list(self.root.glob("receipt-*.json"))))
        forbidden = AssertionError("must not be reached")
        with restored_signal_handlers() as unrouted, \
                mock.patch("runner.credentials", side_effect=forbidden), \
                mock.patch("alpaca_capacity_port.AlpacaCapacityPort", side_effect=forbidden), \
                mock.patch("alpaca_capacity_port.AlpacaLiveCapacityPort", side_effect=forbidden), \
                contextlib.redirect_stdout(io.StringIO()):
            code = c.main(list(argv) + ["--output", str(out)])
        self.unrouted_signals = unrouted
        return code, json.loads(out.read_text())

    def test_cli_live_gates_refuse_before_reading_credentials(self):
        go_now = str(self.go(at=time.time()))  # the CLI uses the host clock
        base = ["live", "--env-file", str(self.env), "--live-go-file", go_now]
        code, receipt = self.cli(base)
        self.assertEqual((code, receipt["refusal_reason"]), (2, "live_orders_not_acknowledged"))
        self.assertEqual(receipt["evidence_class"], "native_live")
        self.assertEqual(receipt["provenance"]["argv"][:5], ["live", "--env-file", "<path>", "--live-go-file",
                                                             "<path>"])
        self.assertNotIn(self.tmp.name, json.dumps(receipt))
        paper_env = str(self.root / "alpaca-paper-capacity.env")
        for extra, reason in (
                (["--env-file", paper_env], "paper_env_file_in_live_mode"),
                (["--band-bps", "400"], "live_band_bps_below_500"),
                (["--allow-cancel-all"], "live_cancel_all_disabled"),
                (["--acknowledge-open-orders", "1"], "live_requires_zero_open_orders"),
                (["--live-go-file", str(self.go(at=time.time(), mode=0o640))], "live_go_file_mode_not_0600")):
            with self.subTest(reason=reason):
                code, receipt = self.cli(base + ["--i-understand-live-orders"] + extra)
                self.assertEqual((code, receipt["status"], receipt["refusal_reason"]), (2, "refused", reason))
                self.assertEqual(receipt["orders"]["submit_attempts"], 0)
                self.assertEqual(list(self.root.glob("*.journal.jsonl")), [])  # refused before the journal

    def test_cli_paper_side_commands_refuse_a_live_env_file(self):
        journal = str(self.root / "run.journal.jsonl")
        for argv in (["paper", "--env-file", str(self.env)],
                     ["recover", "--env-file", str(self.env), "--journal", journal],
                     ["audit", "--env-file", str(self.env), "--journal", journal]):
            with self.subTest(command=argv[0]):
                code, receipt = self.cli(argv)
                self.assertEqual((code, receipt["refusal_reason"]), (2, "live_env_file_in_paper_mode"))
                self.assertEqual(receipt["evidence_class"], "native_paper")
                self.assertNotIn("live", receipt)
        for argv in (["paper", "--env-file", "p.env", "--i-understand-live-orders"],
                     ["offline", "--live-go-file", "go.json"], ["offline", "--max-order-actions", "10"],
                     ["live", "--env-file", str(self.env), "--stop-file", "STOP"]):
            with self.subTest(argv=argv), self.assertRaises(SystemExit), \
                    contextlib.redirect_stderr(io.StringIO()):
                c.main(argv + ["--output", str(self.root / "unused.json")])
        self.assertFalse((self.root / "unused.json").exists())

    def test_offline_cli_default_cap_is_unchanged(self):
        code, receipt = self.cli(["offline", "--duration", "70", "--required-windows", "1"])
        self.assertEqual(code, 0)
        self.assertEqual(receipt["config"]["configured_cap_per_minute"], 200)
        self.assertEqual(receipt["evidence_class"], "offline_fixture")
        self.assertNotIn("live", receipt)

    # -- review of f4d505a0: each case below fails on that commit ----------------------------

    def live_cli(self, *extra):
        """The live CLI with a valid go file and the acknowledgement flag (credentials forbidden)."""
        return self.cli(["live", "--env-file", str(self.env), "--live-go-file", str(self.go(at=time.time())),
                         "--i-understand-live-orders"] + list(extra))

    # Finding 1: live probes use SPY, QQQ, IWM or DIA only, priced from a quote at most 10 s old.
    def test_live_accepts_only_spy_qqq_iwm_or_dia(self):
        for symbol in ("AAPL", "TSLA", "QQQM", "SPXL", "BRK.B"):
            with self.subTest(symbol=symbol):
                receipt, _, broker = self.live(symbol=symbol)
                self.assert_refused_before_any_request(receipt, broker, "live_symbol_not_allowed")
        for symbol in ("SPY", "QQQ", "IWM", "DIA"):
            with self.subTest(symbol=symbol):
                clock = fx.FakeClock()
                receipt, _, broker = self.live(broker=LiveFakeBroker(clock, symbol=symbol), clock=clock,
                                               symbol=symbol, max_duration_seconds=70.0, required_windows=1)
                self.assertEqual(receipt["status"], "completed")
                self.assertEqual({order["symbol"] for order in broker.orders.values()}, {symbol})
        code, receipt = self.live_cli("--symbol", "AAPL")
        self.assertEqual((code, receipt["refusal_reason"]), (2, "live_symbol_not_allowed"))
        c.CapacityConfig(symbol="AAPL").validate()  # paper keeps any valid symbol

    def test_live_refuses_a_quote_older_than_10_seconds_before_any_order(self):
        for age in (10.5, 59.0):
            with self.subTest(quote_age=age):
                clock = fx.FakeClock()
                broker = LiveFakeBroker(clock, quote_age=age)
                receipt, _, _ = self.live(broker=broker, clock=clock)
                self.assertEqual((receipt["status"], receipt["refusal_reason"]), ("refused", "quote_stale"))
                self.assertEqual(broker.submit_count, 0)
        clock = fx.FakeClock()
        receipt, _, broker = self.live(broker=LiveFakeBroker(clock, quote_age=9.0), clock=clock,
                                       max_duration_seconds=70.0, required_windows=1)
        self.assertEqual(receipt["status"], "completed")
        self.assertGreater(broker.submit_count, 0)
        # A live configuration cannot allow an older quote or a slower refresh.
        for change, reason in (({"max_quote_age_seconds": 30.0}, "live_max_quote_age_above_10s"),
                               ({"requote_seconds": 60.0}, "live_requote_seconds_above_5s")):
            with self.subTest(reason=reason):
                receipt, _, broker = self.live(**change)
                self.assert_refused_before_any_request(receipt, broker, reason)

    def test_live_prices_come_from_a_quote_at_most_10s_old_and_submits_hold_for_a_fresh_one(self):
        """The data feed stalls for 25 s: its quotes keep one timestamp. No probe is priced
        from a quote more than 10 s old; submissions hold until a fresh quote, then resume.
        Each quote has its own bid, so every probe's price identifies the quote behind it."""
        clock = fx.FakeClock()
        stall_from, stall_until = clock.time() + 20.0, clock.time() + 45.0

        class StallingFeed(LiveFakeBroker):
            def __init__(self, clock):
                super().__init__(clock)
                self.served, self.sent = [], []

            def latest_quote(self):
                wall = self.clock.time()
                ts = stall_from if stall_from <= wall < stall_until else wall
                bid = Decimal(400 + len(self.served))
                self.served.append((wall, ts, bid))
                return {"bid": str(bid), "ask": str(bid + Decimal("0.02")), "ts_ns": int(ts * 1e9)}

            def submit(self, cid, symbol, qty, limit_price, extended_hours, *quote_wall):
                self.sent.append((self.clock.time(), Decimal(limit_price)))
                return super().submit(cid, symbol, qty, limit_price, extended_hours, *quote_wall)

        broker = StallingFeed(clock)
        receipt, _, _ = self.live(broker=broker, clock=clock, max_duration_seconds=70.0, required_windows=1)
        self.assertEqual((receipt["status"], receipt["health_freezes"]), ("completed", []))
        quote_behind = {c.limit_price_below_bid(bid, 500): (wall, ts, bid) for wall, ts, bid in broker.served}
        self.assertTrue(broker.sent)
        for sent_at, price in broker.sent:
            served_at, ts, bid = quote_behind[price]
            self.assertLessEqual(served_at, sent_at)
            self.assertLessEqual(sent_at - ts, 10.0)  # never priced from a quote over 10 s old
            self.assertLessEqual(price, bid * Decimal("0.95"))  # at least 500 bps below that quote's bid
        # Held while every available quote was over 10 s old; resumed after a fresh one.
        self.assertEqual([t for t, _ in broker.sent if stall_from + 10.0 < t < stall_until], [])
        self.assertTrue([t for t, _ in broker.sent if t > stall_until])
        freshness = receipt["live"]["quote_freshness"]
        self.assertEqual((freshness["max_quote_age_seconds"], freshness["requote_seconds"]), (10.0, 5.0))
        self.assertGreaterEqual(freshness["stale_quotes_refused"], 1)
        self.assertGreaterEqual(freshness["submit_holds"], 1)

    def test_live_submit_rechecks_the_quote_age_on_the_rest_worker(self):
        """The worker re-checks the price's quote age immediately before the port call, so a
        submit that waited in the executor is never sent from a quote over 10 s old."""
        clock = fx.FakeClock()
        harness, broker = self.harness(clock=clock)
        harness._price({"bid": "500.00", "ask": "500.02", "ts_ns": int((clock.time() - 9.9) * 1e9)})
        submit = harness._submit_call()
        clock.advance(0.2)  # the worker ran 0.2 s later: the quote is now 10.1 s old
        response = submit("cap-20260924t140000-abcdef-000001", "SPY", 1, "475.00", False)
        self.assertTrue(response.not_sent)
        self.assertEqual(broker.call_log, [])
        harness._price({"bid": "500.00", "ask": "500.02", "ts_ns": int(clock.time() * 1e9)})
        response = harness._submit_call()("cap-20260924t140000-abcdef-000002", "SPY", 1, "475.00", False)
        self.assertEqual((response.status, response.not_sent), (200, False))

    # Finding 2: SIGHUP (terminal or WSL session closed) and SIGQUIT stop and clean up.
    @unittest.skipUnless(hasattr(signal, "SIGHUP") and hasattr(signal, "SIGQUIT"), "POSIX signals")
    def test_hangup_or_quit_stops_a_live_run_and_cleans_up(self):
        for sig in (signal.SIGHUP, signal.SIGQUIT):
            with self.subTest(signal=sig.name):
                class SignalAt20(LiveFakeBroker):
                    def submit(self, *args):
                        response = super().submit(*args)
                        if self.submit_count == 20:
                            signal.raise_signal(sig)
                        return response

                clock = fx.FakeClock()
                harness, broker = self.harness(broker=SignalAt20(clock), clock=clock)
                with restored_signal_handlers() as unrouted:
                    c.install_stop_signals(harness)
                    receipt = harness.run()
                self.assertEqual(unrouted, [])
                self.assertEqual((receipt["status"], receipt["stop_reason"]), ("completed", "signal"))
                self.assertEqual(broker.submit_count, 20)  # nothing submitted after the signal
                self.assertTrue(receipt["cleanup"]["verified_zero_open"])
                self.assertEqual(broker.open_orders_with_prefix(receipt["probe_plan"]["client_order_id_prefix"]),
                                 [])

    @unittest.skipUnless(hasattr(signal, "SIGHUP") and hasattr(signal, "SIGQUIT"), "POSIX signals")
    def test_cli_routes_hangup_and_quit_to_request_stop(self):
        def signalled_run(harness):
            for sig in (signal.SIGHUP, signal.SIGQUIT):
                signal.raise_signal(sig)
            return harness.refuse("stop_reason_%s" % harness._stop_reason)

        go_now = str(self.go(at=time.time()))
        with mock.patch.object(c.CapacityRun, "run", signalled_run):
            for argv in (["live", "--env-file", str(self.env), "--live-go-file", go_now], ["offline"]):
                with self.subTest(command=argv[0]):
                    _, receipt = self.cli(argv)
                    self.assertEqual(self.unrouted_signals, [])
                    self.assertEqual(receipt["refusal_reason"], "stop_reason_signal")

    # Finding 3: any fill or position change ends needs_attention, over failed, and
    # live.fills carries what is known about it.
    def test_probe_fill_with_a_port_error_ends_needs_attention_with_the_fill(self):
        clock = fx.FakeClock()
        broker = LiveFakeBroker(clock, fill_submit_seqs={3}, crash_on_submit_seq=3)
        receipt, _, _ = self.live(broker=broker, clock=clock)
        self.assertEqual((receipt["status"], receipt["error_type"], receipt["port_errors"]),
                         ("needs_attention", "RuntimeError", 1))
        live = receipt["live"]
        self.assertEqual(live["fills"], [{
            "kind": "probe_fill", "seq": 3, "symbol": "SPY",
            "stream": {"filled_qty": "1", "filled_avg_price": "475.00", "event": "fill"},
            "broker": {"filled_qty": "1", "filled_avg_price": "475.00", "status": "filled"}}])
        self.assertEqual((live["filled_qty_total"], live["auto_sell"]), ("1", False))
        self.assertEqual({order["side"] for order in broker.orders.values()}, {"buy"})

    def test_fill_of_another_order_is_reported_with_quantity_and_price(self):
        class ForeignFillThenDefect(LiveFakeBroker):
            def submit(self, *args):
                if self.submit_count == 4:
                    # Another order on the account fills; then the port fails on submit 5.
                    self.callback({"stream": "trade_updates", "data": {"event": "fill", "order": {
                        "client_order_id": "manual-client-7", "id": "manual-order-id-7", "symbol": "AAPL",
                        "side": "buy", "status": "filled", "filled_qty": "2", "filled_avg_price": "187.5"}}})
                return super().submit(*args)

        clock = fx.FakeClock()
        receipt, _, _ = self.live(broker=ForeignFillThenDefect(clock, crash_on_submit_seq=5), clock=clock)
        self.assertEqual((receipt["status"], receipt["error_type"]), ("needs_attention", "RuntimeError"))
        live = receipt["live"]
        self.assertEqual(live["foreign_fill_events"], 1)
        self.assertEqual(live["fills"], [{
            "kind": "other_order_fill", "order": "not_this_run", "symbol": "AAPL", "side": "buy",
            "stream": {"filled_qty": "2", "filled_avg_price": "187.5", "event": "fill"}}])
        self.assertEqual(live["filled_qty_total"], "0")  # the total counts this run's probes
        self.assertTrue(receipt["cleanup"]["verified_zero_open"])
        text = json.dumps(receipt)
        self.assertNotIn("manual-order-id-7", text)  # no broker order id
        self.assertNotIn("manual-client-7", text)

    def test_position_change_with_a_port_error_ends_needs_attention_with_the_change(self):
        clock = fx.FakeClock()
        start = clock.time()

        class DriftThenDefect(LiveFakeBroker):
            """MSFT appears with no trade update; the next positions read raises."""
            reported = False

            def positions(self):
                held, responses = super().positions()
                if self.clock.time() - start > 30:
                    if self.reported:
                        raise RuntimeError("fixture positions defect")
                    self.reported = True
                    held = held + [{"symbol": "MSFT", "qty": "3"}]
                return held, responses

        receipt, _, _ = self.live(broker=DriftThenDefect(clock), clock=clock)
        self.assertEqual((receipt["status"], receipt["error_type"]), ("needs_attention", "RuntimeError"))
        self.assertEqual(receipt["stop_reason"], "frozen:live_position_change")
        self.assertEqual(receipt["live"]["fills"], [{
            "kind": "position_change", "symbol": "MSFT", "before": "0", "after": "3",
            "seen_by": ["periodic_check"]}])

    # Finding 4: a journal's recorded mode must match the command's, checked before credentials.
    def live_journal(self):
        journal = self.root / "live-run.journal.jsonl"
        clock = fx.FakeClock()
        receipt, _, _ = self.live(clock=clock, journal=journal, max_duration_seconds=70.0, required_windows=1)
        self.assertEqual(receipt["status"], "completed")
        return journal

    def paper_journal(self):
        journal = self.root / "paper-run.journal.jsonl"
        clock = fx.FakeClock()
        receipt = c.CapacityRun(fx.FakeBroker(clock), c.CapacityConfig(max_duration_seconds=70.0, required_windows=1),
                                clock=clock, executor=c.InlineExecutor(), stop_file=self.root / "STOP",
                                journal_path=journal).run()
        self.assertEqual(receipt["status"], "completed")
        return journal

    def test_recover_and_audit_refuse_a_live_journal_before_reading_credentials(self):
        journal = self.live_journal()
        # A start record as f4d505a0 wrote it: no mode field, the live base URL in its config.
        legacy = self.root / "legacy-live.journal.jsonl"
        start = json.loads(journal.read_text().splitlines()[0])
        legacy.write_text(json.dumps({key: start[key] for key in ("type", "harness", "prefix", "started_wall",
                                                                  "symbol", "evidence_class", "config")}) + "\n")
        paper_env = str(self.root / "alpaca-paper-capacity.env")  # judged by name, never read
        for path in (journal, legacy):
            for command in ("recover", "audit"):
                with self.subTest(journal=path.name, command=command):
                    code, receipt = self.cli([command, "--env-file", paper_env, "--journal", str(path)])
                    self.assertEqual((code, receipt["status"], receipt["refusal_reason"]),
                                     (2, "refused", "live_journal_in_paper_mode"))

    def test_journals_record_their_mode_and_each_mode_refuses_the_others_journal(self):
        live_journal, paper_journal = self.live_journal(), self.paper_journal()
        live_start = c.read_journal(live_journal)["start"]
        paper_start = c.read_journal(paper_journal)["start"]
        self.assertEqual((live_start["mode"], live_start["trading_origin"]), ("live", c.LIVE_URL))
        self.assertEqual((paper_start["mode"], paper_start["trading_origin"]),
                         ("paper", "https://paper-api.alpaca.markets"))
        # The paper engine's recover and audit refuse the live journal before any request.
        for cancel in (True, False):
            clock = fx.FakeClock()
            broker = fx.FakeBroker(clock)
            receipt = c.CapacityRun(broker, c.CapacityConfig(), clock=clock, executor=c.InlineExecutor(),
                                    stop_file=self.root / "STOP").recover(live_journal, cancel=cancel)
            self.assertEqual((receipt["status"], receipt["refusal_reason"]), ("refused", "live_journal_in_paper_mode"))
            self.assertEqual(broker.call_log, [])
        # A run refuses an existing file at its journal path before any request, naming the other mode.
        receipt, _, broker = self.live(journal=paper_journal)
        self.assert_refused_before_any_request(receipt, broker, "paper_journal_in_live_mode")
        receipt, _, broker = self.live(journal=live_journal)
        self.assert_refused_before_any_request(receipt, broker, "journal_exists")
        clock = fx.FakeClock()
        broker = fx.FakeBroker(clock)
        receipt = c.CapacityRun(broker, c.CapacityConfig(), clock=clock, executor=c.InlineExecutor(),
                                stop_file=self.root / "STOP", journal_path=live_journal).run()
        self.assert_refused_before_any_request(receipt, broker, "live_journal_in_paper_mode")
        code, receipt = self.live_cli("--journal", str(paper_journal))
        self.assertEqual((code, receipt["refusal_reason"]), (2, "paper_journal_in_live_mode"))
        self.assertEqual(c.journal_origin_refusal(paper_start, c.LIVE_URL), "paper_journal_in_live_mode")
        self.assertEqual(c.journal_origin_refusal(live_start, "https://paper-api.alpaca.markets"),
                         "live_journal_in_paper_mode")
        for start in ({}, {"config": {"base_url": "https://example.invalid"}},
                      dict(paper_start, mode="live"), dict(live_start, evidence_class="native_paper",
                                                           trading_origin="https://paper-api.alpaca.markets")):
            self.assertEqual(c.journal_origin_refusal(start, c.LIVE_URL), "journal_origin_unknown")

    # Finding 5: the live budget is floor(min(--cap, observed limit) * 0.9).
    def test_live_headroom_is_held_at_0_9(self):
        for headroom in (1.0, 0.95, 0.5):
            with self.subTest(headroom=headroom):
                receipt, _, broker = self.live(headroom=headroom)
                self.assert_refused_before_any_request(receipt, broker, "live_headroom_must_be_0_9")
        for cap, limit, budget in ((1000, 1000, 900), (500, 1000, 450), (1000, 200, 180)):
            with self.subTest(cap=cap, limit=limit):
                clock = fx.FakeClock()
                receipt, _, _ = self.live(broker=LiveFakeBroker(clock, limit=limit), clock=clock,
                                          configured_cap_per_minute=cap, max_duration_seconds=70.0,
                                          required_windows=1)
                self.assertEqual((receipt["rate"]["headroom"], receipt["rate"]["budget_per_minute"]), (0.9, budget))
        code, receipt = self.live_cli("--headroom", "1.0")
        self.assertEqual((code, receipt["refusal_reason"]), (2, "live_headroom_must_be_0_9"))
        c.CapacityConfig(headroom=1.0).validate()  # paper keeps its configurable headroom

    # The periodic position check fails closed on any failed read (the docstring promised a retry).
    def test_live_position_check_fails_closed_on_any_failed_read(self):
        class Limited(LiveFakeBroker):
            """Every positions read gets a 429 response; the native port raises instead."""
            def positions(self):
                self.clock.advance(self.read_latency)
                return [], [c.Response(429, {"retry-after": "1", "x-ratelimit-limit": "200"})]

        clock = fx.FakeClock()
        receipt, _, _ = self.live(broker=Limited(clock), clock=clock)
        self.assertEqual(receipt["stop_reason"], "frozen:live_position_check_failed")
        self.assertEqual(receipt["live"]["position_checks"]["failed"], 1)
        self.assertLess(receipt["throughput"]["submission_phase_seconds"], 15.0)
        self.assertEqual(receipt["status"], "needs_attention")
        self.assertTrue(receipt["cleanup"]["verified_zero_open"])

    # -- review of 29c5189f: each case below fails on that commit ----------------------------

    # Finding 1: the price's quote wall time reaches the live port, whose refusal at the
    # wire is counted as not sent.
    def test_live_run_passes_the_quote_wall_to_the_port_and_counts_a_wire_refusal(self):
        class WireCheck(LiveFakeBroker):
            """Refuses the third submit, not sent, as the native live port does when the
            price's quote aged past 10 s between the worker's check and the POST."""
            def __init__(self, clock):
                super().__init__(clock)
                self.seen = []

            def submit(self, cid, symbol, qty, limit_price, extended_hours, quote_wall=None):
                self.seen.append((self.clock.time(), quote_wall))
                if len(self.seen) == 3:
                    return c.Response(None, error="quote_stale_at_wire", not_sent=True)
                return super().submit(cid, symbol, qty, limit_price, extended_hours, quote_wall)

        clock = fx.FakeClock()
        receipt, _, broker = self.live(broker=WireCheck(clock), clock=clock, max_duration_seconds=70.0,
                                       required_windows=1)
        self.assertEqual(receipt["status"], "completed")
        freshness = receipt["live"]["quote_freshness"]
        self.assertEqual((freshness["stale_at_wire"], freshness["stale_at_dispatch"]), (1, 0))
        self.assertEqual(receipt["orders"]["rest_rejections"].get("not_sent"), 1)
        self.assertGreater(len(broker.seen), 3)
        for sent_at, wall in broker.seen:  # every submit carried the time of its price's quote
            self.assertIs(type(wall), float)
            self.assertTrue(0.0 <= sent_at - wall <= 10.0, (sent_at, wall))

    # Finding 2: a summary write that fails after SIGHUP (EIO) keeps the run's exit code.
    @unittest.skipUnless(hasattr(signal, "SIGHUP"), "POSIX signals")
    def test_summary_write_failure_after_sighup_keeps_the_run_exit_code(self):
        class ClosedTerminal(io.TextIOBase):
            def writable(self):
                return True

            def write(self, text):
                raise OSError(errno.EIO, "Input/output error")

        def hung_up(harness):
            signal.raise_signal(signal.SIGHUP)  # the terminal closed: stop requested
            receipt = harness.refuse("unused")
            receipt["status"], receipt["refusal_reason"] = "needs_attention", None  # exit code 3
            return receipt

        out = self.root / "hangup.json"
        with restored_signal_handlers() as unrouted, mock.patch.object(c.CapacityRun, "run", hung_up), \
                contextlib.redirect_stdout(ClosedTerminal()):
            code = c.main(["offline", "--output", str(out)])
        self.assertEqual(unrouted, [])
        self.assertEqual(code, 3)
        saved = json.loads(out.read_text())
        self.assertEqual((saved["status"], saved["provenance"]["exit_code"]), ("needs_attention", 3))

    @unittest.skipUnless(hasattr(os, "openpty"), "POSIX pseudo-terminals")
    def test_script_exit_code_survives_a_closed_terminal(self):
        """The script's stdout is a terminal that is already gone (writes fail with EIO):
        the exit code is still the run's, not 1 (traceback) or 120 (a failed final flush)."""
        import subprocess
        master, slave = os.openpty()
        os.close(master)
        out = self.root / "closed-terminal.json"
        try:
            done = subprocess.run([sys.executable, str(SOURCE / "capacity.py"), "offline", "--output", str(out),
                                   "--duration", "70", "--required-windows", "1"],
                                  stdout=slave, stderr=subprocess.PIPE, text=True, timeout=120, check=False)
        finally:
            os.close(slave)
        receipt = json.loads(out.read_text())
        self.assertEqual(receipt["provenance"]["exit_code"], 0)
        self.assertEqual(done.returncode, 0, done.stderr[-2000:])

    # Finding 3: the host clock must agree with the broker clock within 1 s.
    def test_live_preflight_refuses_a_host_clock_more_than_1s_off_the_broker_clock(self):
        # Skew is host minus broker; half the 0.1 s round trip counts against the limit.
        for skew in (1.5, -1.5, 0.96):
            with self.subTest(skew=skew):
                clock = fx.FakeClock()
                broker = LiveFakeBroker(clock, clock_skew=skew)
                receipt, _, _ = self.live(broker=broker, clock=clock)
                self.assertEqual((receipt["status"], receipt["refusal_reason"]), ("refused", "host_clock_skew"))
                self.assertEqual((broker.submit_count, receipt["orders"]["submit_attempts"]), (0, 0))
                measured = receipt["live"]["host_clock"]
                self.assertAlmostEqual(measured["skew_seconds"], skew, places=4)
                self.assertAlmostEqual(measured["round_trip_seconds"], 0.1, places=4)
                self.assertEqual((measured["max_skew_seconds"], measured["within_limit"]), (1.0, False))
        clock = fx.FakeClock()
        receipt, _, _ = self.live(broker=LiveFakeBroker(clock, clock_skew=-0.4), clock=clock,
                                  max_duration_seconds=70.0, required_windows=1)
        self.assertEqual(receipt["status"], "completed")
        self.assertAlmostEqual(receipt["live"]["host_clock"]["skew_seconds"], -0.4, places=4)
        self.assertTrue(receipt["live"]["host_clock"]["within_limit"])

        class Unreadable(LiveFakeBroker):
            def preflight(self):
                pre = super().preflight()
                pre["broker_clock"] = dict(pre["broker_clock"], timestamp="yesterday")
                return pre

        clock = fx.FakeClock()
        broker = Unreadable(clock)
        receipt, _, _ = self.live(broker=broker, clock=clock)
        self.assertEqual((receipt["refusal_reason"], broker.submit_count), ("broker_clock_unreadable", 0))
        # GET /v2/clock gives nanosecond digits and an Eastern offset.
        expected = datetime(2026, 9, 24, 14, 0, tzinfo=timezone.utc).timestamp() + 0.123456789
        self.assertAlmostEqual(c.broker_timestamp_wall("2026-09-24T10:00:00.123456789-04:00"), expected, places=6)
        self.assertEqual(c.broker_timestamp_wall("2026-09-24T14:00:00Z"), expected - 0.123456789)
        for value in ("2026-09-24T14:00:00", "2026-09-24 14:00:00Z", None, 1790000000):
            self.assertIsNone(c.broker_timestamp_wall(value))

    # Finding 4: a 429 on the position read reaches the governor before the freeze.
    def test_a_429_position_read_backs_off_the_cleanup_cancels(self):
        class LimitedRaises(LiveFakeBroker):
            """As the native port: the first positions read (at 10 s) gets a 429 and raises,
            keeping its sanitized response (status and rate-limit headers). Stream acks
            are held from 9 s on, so probes are still open for cleanup to cancel."""
            limited_at = None

            def __init__(self, clock):
                super().__init__(clock)
                self.hold_acks_from = clock.monotonic() + 9.0
                self.open_at_429 = None

            def _emit(self, event, order):
                if event in c.ACK_EVENTS and self.clock.monotonic() >= self.hold_acks_from:
                    return
                super()._emit(event, order)

            def positions(self):
                if self.limited_at is not None:
                    return super().positions()  # the reconciliation read succeeds
                self.clock.advance(self.read_latency)
                self.limited_at = self.clock.monotonic()
                self.open_at_429 = len(self.open_orders_with_prefix("cap-"))
                self.call_log.append({"t": self.limited_at, "kind": "read"})
                error = RuntimeError("positions unavailable")
                error.responses = [c.Response(429, {"retry-after": "20", "x-ratelimit-limit": "200"})]
                raise error

        clock = fx.FakeClock()
        receipt, _, broker = self.live(broker=LimitedRaises(clock), clock=clock)
        self.assertEqual(receipt["stop_reason"], "frozen:live_position_check_failed")
        self.assertEqual(receipt["rate"]["http_429"], 1)
        self.assertIn({"kind": "read", "seconds": 20.0, "source": "retry_after"}, receipt["rate"]["backoffs"])
        self.assertGreater(broker.open_at_429, 0)
        cleanup_cancels = [entry["t"] for entry in broker.call_log
                           if entry["kind"] == "cancel" and entry["t"] > broker.limited_at]
        self.assertGreaterEqual(len(cleanup_cancels), broker.open_at_429)
        self.assertGreaterEqual(min(cleanup_cancels), broker.limited_at + 20.0)  # Retry-After honoured
        self.assertTrue(receipt["cleanup"]["verified_zero_open"])
        self.assertEqual(receipt["status"], "needs_attention")

    # Finding 5: recover and audit guard the journal read as a new run guards its journal path.
    def test_recover_and_audit_refuse_a_fifo_symlink_or_oversized_journal(self):
        paper = self.paper_journal()
        start_line = paper.read_text().splitlines()[0] + "\n"
        fifo = self.root / "fifo.journal.jsonl"
        os.mkfifo(fifo)
        big = self.root / "big.journal.jsonl"
        with open(big, "w") as handle:  # a valid start record, then NUL bytes past 64 MiB (sparse)
            handle.write(start_line)
            handle.truncate(c.JOURNAL_CHECK_MAX_BYTES + 1)
        link = self.root / "link.journal.jsonl"
        link.symlink_to(paper)
        stop = threading.Event()

        def feed_blocked_readers():
            """Unguarded code blocks opening the FIFO; feed it a valid start record so the
            assertion, not a hang, reports that. Guarded code never opens it (ENXIO here)."""
            while not stop.is_set():
                try:
                    fd = os.open(fifo, os.O_WRONLY | os.O_NONBLOCK)
                except OSError:
                    stop.wait(0.05)
                    continue
                try:
                    os.write(fd, start_line.encode())
                except OSError:
                    pass  # the pipe is full: this reader already has a record
                finally:
                    os.close(fd)  # the reader then sees end of file
                stop.wait(0.2)

        feeder = threading.Thread(target=feed_blocked_readers, daemon=True)
        feeder.start()
        paper_env = str(self.root / "alpaca-paper-capacity.env")  # judged by name, never read
        try:
            for path, reason in ((fifo, "journal_not_regular_file"), (link, "journal_not_regular_file"),
                                 (big, "journal_too_large")):
                with self.subTest(journal=path.name):
                    with self.assertRaises(c.HarnessRefusal) as raised:
                        c.read_journal(path)
                    self.assertEqual(str(raised.exception), reason)
                    for cancel in (True, False):
                        clock = fx.FakeClock()
                        broker = fx.FakeBroker(clock)
                        receipt = c.CapacityRun(broker, c.CapacityConfig(), clock=clock, executor=c.InlineExecutor(),
                                                stop_file=self.root / "STOP").recover(path, cancel=cancel)
                        self.assertEqual((receipt["status"], receipt["refusal_reason"]), ("refused", reason))
                        self.assertEqual(broker.call_log, [])
                    for command in ("recover", "audit"):
                        code, receipt = self.cli([command, "--env-file", paper_env, "--journal", str(path)])
                        self.assertEqual((code, receipt["status"], receipt["refusal_reason"]),
                                         (2, "refused", reason))
        finally:
            stop.set()
            feeder.join(5)
        self.assertEqual(c.read_journal(paper)["start"]["mode"], "paper")  # a regular journal still reads


class LivePortTests(unittest.TestCase):
    """The native live port's own logic; no request leaves the process."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.stops = (Path(self.tmp.name) / "STOP", Path(self.tmp.name) / "alpaca-live" / "STOP")

    def go(self, expires_in=3600.0):
        now = time.time()
        return c.LiveGo(now - 60.0, now + expires_in, 100, Decimal("2000"))

    def test_live_port_identity_and_final_boundary(self):
        import alpaca_capacity_port as native
        self.assertEqual(native.AlpacaLiveCapacityPort.evidence_class, "native_live")
        self.assertFalse(native.AlpacaLiveCapacityPort.supports_cancel_all)
        self.assertEqual(native.AlpacaLiveCapacityPort.trading_origin, "https://api.alpaca.markets")
        self.assertEqual(native.AlpacaCapacityPort.trading_origin, "https://paper-api.alpaca.markets")
        self.assertEqual(c.LIVE_WS, "wss://api.alpaca.markets/stream")
        for go in (None, self.go(expires_in=-1.0)):
            with self.assertRaises(native.transport.TransportError):
                native.AlpacaLiveCapacityPort("k", "s", "SPY", go=go, stop_files=self.stops)
        with self.assertRaises(native.transport.TransportError):
            native.AlpacaLiveCapacityPort("k", "s", "SPY", go=self.go(), stop_files=self.stops[:1])
        port = native.AlpacaLiveCapacityPort("k", "s", "SPY", go=self.go(), stop_files=self.stops)
        port._local.quote_wall = time.time()  # as port.submit sets it: a fresh quote prices the probe
        self.assertIsNone(port._before_request("submit", client_id="x"))
        self.stops[1].parent.mkdir()
        self.stops[1].write_text("")
        with self.assertRaises(native.SafetyError):
            port._before_request("submit", client_id="x")
        self.assertIsNone(port._before_request("cancel"))  # cancels stay allowed under STOP
        self.stops[1].unlink()
        port.go = self.go(expires_in=-1.0)
        with self.assertRaises(native.SafetyError):
            port._before_request("submit", client_id="x")  # the go expired: no further submit
        with self.assertRaises(native.transport.TransportError):
            port.recovery_preflight()
        with self.assertRaises(Exception):
            port.cancel_all()

    def test_live_port_refuses_any_symbol_but_spy_qqq_iwm_or_dia(self):
        import queue
        import alpaca_capacity_port as native
        for symbol in ("AAPL", "QQQM"):
            with self.assertRaises(native.transport.TransportError):
                native.AlpacaLiveCapacityPort("k", "s", symbol, go=self.go(), stop_files=self.stops)

        class Client:
            def __init__(self):
                self.orders = []

            def submit_order(self, request):
                self.orders.append(request)
                return {"id": "x"}

        client = Client()
        port = native.AlpacaLiveCapacityPort("k", "s", "SPY", go=self.go(), stop_files=self.stops)
        port._pool = queue.Queue()  # a stub client: no SDK client and no network
        port._pool.put(client)
        for symbol in ("AAPL", "QQQ"):  # QQQ is allowed, but not by a port built for SPY
            with self.subTest(symbol=symbol):
                response = port.submit("cap-20260924t140000-abcdef-000001", symbol, 1, "100.00", False)
                self.assertTrue(response.not_sent)
        self.assertEqual(client.orders, [])

    # Review of 29c5189f, finding 1: the worker's age check ran before pool.get() and the
    # POST, so a slow submit could go out with an older quote.
    def test_live_port_rechecks_the_quote_age_at_the_wire(self):
        import queue
        import alpaca_capacity_port as native
        now = [time.time()]

        class LimitOrderRequest:  # stands in for the SDK request model; no SDK needed
            def __init__(self, **fields):
                self.__dict__.update(fields)

        sdk_requests = types.ModuleType("alpaca.trading.requests")
        sdk_requests.LimitOrderRequest = LimitOrderRequest
        port = native.AlpacaLiveCapacityPort("k", "s", "SPY", go=self.go(), stop_files=self.stops)
        port._wall = lambda: now[0]

        class Client:
            """The SDK client behind GuardedSession: 0.3 s pass before the POST (a slow
            pool.get() or request build), then the session's before_request hook runs,
            and any refusal becomes SubmissionNotSent before HTTP."""
            def __init__(self):
                self.posted = []

            def submit_order(self, request):
                now[0] += 0.3
                try:
                    port._before_request("submit", client_id=request.client_order_id)
                except Exception:
                    raise native.transport.SubmissionNotSent("prevented before HTTP") from None
                self.posted.append(request.client_order_id)
                port._observe({"kind": "submit", "status": 200, "headers": {}})
                return {"id": "00000000-0000-4000-8000-000000000001", "client_order_id": request.client_order_id,
                        "status": "accepted", "symbol": "SPY", "side": "buy", "filled_qty": "0"}

        client = Client()
        port._pool = queue.Queue()  # a stub client: no SDK client and no network
        port._pool.put(client)
        cid = "cap-20260924t140000-abcdef-%06d"
        with mock.patch.dict(sys.modules, {"alpaca.trading.requests": sdk_requests}):
            stale = port.submit(cid % 1, "SPY", 1, "475.00", False, now[0] - 9.9)  # 10.2 s old at the wire
            fresh = port.submit(cid % 2, "SPY", 1, "475.00", False, now[0] - 2.0)
            undated = port.submit(cid % 3, "SPY", 1, "475.00", False)
            ahead = port.submit(cid % 4, "SPY", 1, "475.00", False, now[0] + 5.0)  # ahead of the host clock
            self.stops[0].write_text("")
            stopped = port.submit(cid % 5, "SPY", 1, "475.00", False, now[0])
        for response in (stale, undated, ahead):
            self.assertEqual((response.status, response.not_sent, response.error), (None, True, "quote_stale_at_wire"))
        self.assertEqual((stopped.not_sent, stopped.error), (True, "stop_blocks_entry"))
        self.assertEqual((fresh.status, fresh.not_sent, fresh.order["client_order_id"]), (200, False, cid % 2))
        self.assertEqual(client.posted, [cid % 2])
        self.assertEqual(port._pool.qsize(), 1)

    # Review of 29c5189f, finding 4: the positions read raised on a 429 and dropped its headers.
    def test_positions_read_error_keeps_its_response_for_the_governor(self):
        import queue
        import alpaca_capacity_port as native
        port = native.AlpacaLiveCapacityPort("k", "s", "SPY", go=self.go(), stop_files=self.stops)

        class Client:
            def get_all_positions(self):
                port._observe({"kind": "read", "status": 429, "headers": {"retry-after": "7"}})
                error = RuntimeError("provider text never retained")
                error.status_code = 429
                raise error

        port._pool = queue.Queue()
        port._pool.put(Client())
        with self.assertRaises(native.transport.TransportError) as raised:
            port.positions()
        (response,) = raised.exception.responses
        self.assertEqual((response.status, response.headers, response.origin), (429, {"retry-after": "7"}, "trading"))
        self.assertNotIn("provider text", repr(raised.exception.responses))

    @unittest.skipUnless(HAS_REQUESTS, "requests is not installed in this interpreter")
    def test_each_guarded_session_admits_one_origin(self):
        import alpaca_capacity_port as native
        transport = native.transport
        live = transport.GuardedSession(origin=c.LIVE_URL, before_request=lambda kind, **_: None)
        paper = transport.GuardedSession(origin=transport.PAPER_URL, before_request=lambda kind, **_: None)
        try:
            for session, url in ((live, transport.PAPER_URL + "/v2/account"),
                                 (paper, c.LIVE_URL + "/v2/account"),
                                 (live, c.LIVE_URL + "/v2/orders")):
                method = "DELETE" if url.endswith("/v2/orders") else "GET"
                with self.subTest(origin=session.origin, method=method, url=url):
                    with self.assertRaises(transport.TransportError):
                        session.request(method, url)  # refused before any network I/O
        finally:
            live.close()
            paper.close()

    @unittest.skipUnless(HAS_ALPACA_SDK, "alpaca-py is not installed in this interpreter")
    def test_sdk_clients_and_stream_target_only_their_own_origin(self):
        import alpaca_capacity_port as native
        port = native.AlpacaLiveCapacityPort("k", "s", "SPY", go=self.go(), stop_files=self.stops)
        paper = native.AlpacaCapacityPort("k", "s", "SPY")
        for owner, origin, stream in ((port, c.LIVE_URL, c.LIVE_WS),
                                      (paper, native.transport.PAPER_URL, native.transport.PAPER_WS)):
            client = owner._trading_client(lambda kind, **_: None, None)
            try:
                self.assertEqual((client._session.origin, str(client._base_url), client._retry), (origin, origin, 0))
            finally:
                client._session.close()
            self.assertEqual(owner._orders_stream({"ping_interval": 10})._endpoint, stream)

    @unittest.skipUnless(HAS_ALPACA_SDK, "alpaca-py is not installed in this interpreter")
    def test_live_preflight_returns_identity_hash_and_no_balance(self):
        import alpaca_capacity_port as native

        class Session:
            def close(self):
                return None

        class Trading:
            _session = Session()

            def get_account(self):
                return {"id": "acct-1", "cash": "123456.78", "equity": "234567.89"}

            def get_clock(self):
                return {"is_open": True, "timestamp": "2026-09-24T10:00:00.123456789-04:00"}

            def get_all_positions(self):
                return [{"symbol": "AAPL", "qty": "5"}]

            def get(self, path, params):
                return []

            def get_asset(self, symbol):
                return {"symbol": symbol, "tradable": True, "status": "active"}

        class Data:
            _session = Session()

            def get_stock_latest_quote(self, request):
                return {"SPY": {"bp": "500", "ap": "500.02", "bs": 1, "as": 1, "t": "2026-09-24T14:00:00Z"}}

        port = native.AlpacaLiveCapacityPort("k", "s", "SPY", go=self.go(), stop_files=self.stops)
        port._trading_client = lambda *args, **kwargs: Trading()
        port._ensure_pool = lambda: None
        with mock.patch.object(native.transport, "_sdk_client", lambda *args, **kwargs: Data()):
            pre = port.preflight()
        self.assertEqual(pre["account_identity_sha256"], hashlib.sha256(b"acct-1").hexdigest())
        self.assertIs(pre["market_open"], True)
        clock = pre["broker_clock"]  # the broker timestamp, bracketed by host wall times
        self.assertEqual(clock["timestamp"], "2026-09-24T10:00:00.123456789-04:00")
        self.assertLessEqual(clock["host_sent_wall"], clock["host_received_wall"])
        self.assertEqual((pre["open_orders"], pre["open_orders_complete"], pre["asset_tradable"]), ([], True, True))
        quote_ns = int(datetime(2026, 9, 24, 14, 0, tzinfo=timezone.utc).timestamp()) * 1_000_000_000
        self.assertEqual(pre["quote"], {"bid": "500", "ask": "500.02", "ts_ns": quote_ns, "halted": False})
        text = json.dumps(pre)
        for private in ("acct-1", "123456.78", "234567.89"):
            self.assertNotIn(private, text)


if __name__ == "__main__":
    unittest.main()
