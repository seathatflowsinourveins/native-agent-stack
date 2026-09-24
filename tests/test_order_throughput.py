"""Offline tests for the paper execution-capacity harness.

A fake clock, fake broker and fake trade_updates stream stand in for Alpaca;
no credentials, no network and no broker requests. Evidence class of every
run here is offline_fixture.
"""
import contextlib
from datetime import datetime, timezone
from decimal import Decimal
import io
import json
import os
from pathlib import Path
import re
import signal
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "blueprints/us-equities/order-throughput"
sys.path.insert(0, str(SOURCE))

import capacity as c  # noqa: E402
import capacity_fixture as fx  # noqa: E402
import rate_governor as g  # noqa: E402
import rate_limit_evidence as evidence  # noqa: E402

UUID_TEXT = re.compile(r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}", re.I)


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
            handlers = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    code = c.main(["paper", "--env-file", str(env), "--output", str(out)])
            finally:
                for sig, handler in handlers.items():
                    signal.signal(sig, handler)
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


if __name__ == "__main__":
    unittest.main()
