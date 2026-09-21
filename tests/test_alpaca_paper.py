"""Synthetic adapter failures; these never contact or qualify an Alpaca account."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "blueprints/us-equities/alpaca-paper/paper_runner.py"
spec = importlib.util.spec_from_file_location("alpaca_paper", PATH)
paper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(paper)
D = paper.Decimal


class Time:
    def __init__(self):
        self.value = 1_800_000_000.0

    def now(self):
        return self.value

    def sleep(self, seconds):
        self.value += seconds


class FakeBroker:
    evidence_kind = "synthetic_adapter_fixture"

    def __init__(self, gate, scenario="normal"):
        self.gate, self.scenario = gate, scenario
        self.orders = {}
        self.position = D(0)
        self.submits = []
        self.cancels = []
        self.quote_override = None
        self.external = False
        self.kill_on_entry = None

    def clock(self):
        self.gate.before("GET")
        return {"open": True, "at": self.gate.now(), "close": self.gate.now() + 3600}

    def asset(self):
        self.gate.before("GET")
        return {"symbol": "SPY", "status": "active", "tradable": True}

    def quote(self):
        self.gate.before("GET")
        return self.quote_override or {"bid": "770.40", "ask": "770.45", "at": self.gate.now()}

    def positions(self):
        self.gate.before("GET")
        if self.external:
            return [{"symbol": "AAPL", "qty": "1"}]
        return [{"symbol": "SPY", "qty": str(self.position)}] if self.position else []

    def open_orders(self):
        self.gate.before("GET")
        return [dict(o) for o in self.orders.values() if o["status"] not in paper.TERMINAL]

    def lookup(self, client_id):
        self.gate.before("GET")
        return copy.deepcopy(self.orders.get(client_id))

    def submit(self, intent):
        self.gate.before("POST")
        self.submits.append(dict(intent))
        if self.scenario == "rate_limited":
            raise paper.BrokerError(429)
        if intent["client_order_id"] in self.orders:
            raise AssertionError("duplicate broker submit")
        qty = D(intent["qty"])
        filled = qty
        if intent["side"] == "buy" and self.scenario in ("partial_cancel_race", "full_cancel_race"):
            filled = D("0.4")
        if intent["side"] == "sell" and self.scenario == "unfilled_exit":
            filled = D(0)
        order = {"id": "broker-" + intent["side"], "client_order_id": intent["client_order_id"],
                 "symbol": "SPY", "side": intent["side"], "qty": str(qty),
                 "filled_qty": str(filled), "status": "filled" if filled == qty else "partially_filled",
                 "filled_avg_price": "770.45" if intent["side"] == "buy" else ("770.40" if filled else None)}
        self.orders[intent["client_order_id"]] = order
        self.position += filled if intent["side"] == "buy" else -filled
        if self.kill_on_entry and intent["side"] == "buy":
            self.kill_on_entry.touch()
        if self.scenario == "timeout_accepted" and intent["side"] == "buy":
            raise paper.BrokerError()
        return dict(order)

    def cancel(self, order_id):
        self.gate.before("DELETE")
        self.cancels.append(order_id)
        order = next(o for o in self.orders.values() if o["id"] == order_id)
        if order["side"] == "buy":
            final = D("0.6") if self.scenario == "partial_cancel_race" else D(1)
            self.position += final - D(order["filled_qty"])
            order["filled_qty"] = str(final)
        order["status"] = "canceled"
        if self.scenario == "full_cancel_race":
            raise paper.BrokerError(422)  # Cancel raced with a final fill.


class PaperTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.clock = Time()
        self.config = paper.load_config(PATH.with_name("config.json"))
        self.journal = paper.Journal(self.root / "journal.jsonl")
        self.gate = paper.Gate(self.config, self.journal, self.clock.now, self.clock.sleep)
        self.broker = FakeBroker(self.gate)
        self.runner = paper.Runner(self.broker, self.config, self.journal, self.gate, self.root / "STOP")
        self.account = {"id": "fixture-account", "status": "ACTIVE", "currency": "USD",
                        "blocked": False, "account_blocked": False, "trade_suspended_by_user": False,
                        "buying_power": "10000", "equity": "100000"}

    def tearDown(self):
        self.journal.close()
        self.tmp.cleanup()

    def run_trial(self):
        self.runner.preflight(self.account)
        return self.runner.lifecycle("fixture-trial", False)

    def test_preflight_is_read_only(self):
        self.runner.preflight(self.account)
        self.assertEqual(self.broker.submits, [])
        self.assertIsNone(self.journal.first("trial"))

    def test_round_trip_flat_and_sanitized(self):
        self.assertEqual(self.run_trial(), "passed")
        receipt = self.runner.receipt("passed")
        self.assertEqual(receipt["write_attempts"], 2)
        self.assertEqual(receipt["realized_gross_pnl_usd"], "-0.05")
        self.assertTrue(receipt["final_flat_and_idle_observed"])
        self.assertNotIn("fixture-account", json.dumps(receipt))
        self.assertNotIn("broker-buy", json.dumps(receipt))
        self.assertEqual(receipt["evidence_kind"], "synthetic_adapter_fixture")

    def test_timeout_after_acceptance_never_duplicates(self):
        self.broker.scenario = "timeout_accepted"
        self.assertEqual(self.run_trial(), "passed")
        self.assertEqual(len(self.broker.submits), 2)
        self.assertIsNotNone(self.journal.first("ambiguous_submit"))

    def test_partial_fill_cancel_race_exits_observed_final_qty(self):
        self.broker.scenario = "partial_cancel_race"
        self.assertEqual(self.run_trial(), "inconclusive_no_full_round_trip")
        self.assertEqual(self.broker.submits[-1]["qty"], "0.6")
        self.assertEqual(self.broker.position, 0)
        self.assertEqual(self.broker.cancels, ["broker-buy"])

    def test_cancel_error_with_final_fill_still_exits(self):
        self.broker.scenario = "full_cancel_race"
        self.assertEqual(self.run_trial(), "passed")
        self.assertEqual(self.broker.position, 0)
        self.assertEqual(len(self.broker.submits), 2)

    def test_restart_queries_stable_ids_no_duplicates(self):
        self.assertEqual(self.run_trial(), "passed")
        self.journal.close()
        self.journal = paper.Journal(self.root / "journal.jsonl")
        self.gate.attach(self.journal)
        runner = paper.Runner(self.broker, self.config, self.journal, self.gate, self.root / "STOP")
        self.assertEqual(runner.lifecycle("fixture-trial", True), "passed")
        self.assertEqual(len(self.broker.submits), 2)
        with self.assertRaisesRegex(paper.SafetyError, "existing_trial"):
            runner.lifecycle("new-trial", False)

    def test_restart_after_entry_submit_recovers_only_exit(self):
        self.runner.preflight(self.account)
        self.journal.add("trial", trial="fixture-trial", config=self.config)
        intent = self.runner.intent("buy", "fixture-trial", "1", "770.50")
        self.runner.submit_once(intent)
        self.assertEqual(self.runner.lifecycle("fixture-trial", True), "passed")
        self.assertEqual([i["side"] for i in self.broker.submits], ["buy", "sell"])

    def test_crash_after_intent_before_submit_does_not_retry(self):
        self.journal.add("trial", trial="fixture-trial", config=self.config)
        self.journal.add("submit_intent", intent=self.runner.intent("buy", "fixture-trial", "1", "770.50"))
        with self.assertRaisesRegex(paper.SafetyError, "ambiguous_order_not_found"):
            self.runner.lifecycle("fixture-trial", True)
        self.assertEqual(self.broker.submits, [])

    def test_rate_limit_preserves_ambiguous_status_without_submit_retry(self):
        self.broker.scenario = "rate_limited"
        with self.assertRaisesRegex(paper.SafetyError, "ambiguous_order_not_found"):
            self.run_trial()
        self.assertEqual(len(self.broker.submits), 1)
        self.assertEqual(self.journal.first("ambiguous_submit")["status"], 429)

    def test_unfilled_exit_fails_instead_of_claiming_flat(self):
        self.broker.scenario = "unfilled_exit"
        with self.assertRaisesRegex(paper.SafetyError, "exit_incomplete"):
            self.run_trial()
        self.assertEqual(self.broker.position, 1)
        self.assertFalse(self.runner.receipt("needs_attention")["final_flat_and_idle_observed"])
        self.assertEqual(len(self.broker.submits), 2)

    def test_kill_blocks_entry_but_allows_exit(self):
        stop = self.root / "STOP"
        stop.touch()
        with self.assertRaisesRegex(paper.SafetyError, "kill_switch"):
            self.runner.preflight(self.account)
        stop.unlink()
        self.broker.kill_on_entry = stop
        self.assertEqual(self.run_trial(), "passed")
        self.assertEqual(self.broker.position, 0)

    def test_lock_prevents_second_writer(self):
        with paper.account_lock("fixture-account", self.root / "locks"):
            with self.assertRaisesRegex(paper.SafetyError, "writer_already"):
                with paper.account_lock("fixture-account", self.root / "locks"):
                    self.fail("second writer entered")

    def test_existing_external_position_never_closed(self):
        self.broker.external = True
        with self.assertRaisesRegex(paper.SafetyError, "initial_account"):
            self.run_trial()
        self.assertEqual(self.broker.submits + self.broker.cancels, [])

    def test_frozen_config_rejects_nonfinite_boolean_and_larger_budgets(self):
        for key, value in [("max_requests_per_minute", 1000), ("max_write_attempts", 100),
                           ("qty", "NaN"), ("schema_version", True), ("paper", False)]:
            bad = {**self.config, key: value}
            path = self.root / "bad.json"
            path.write_text(json.dumps(bad))
            with self.assertRaises(paper.SafetyError):
                paper.load_config(path)

    def test_stale_quote_and_invalid_price_block_entry(self):
        for quote in [{"bid": "770", "ask": "771", "at": self.clock.now()},
                      {"bid": "770", "ask": "770.1", "at": self.clock.now() - 16},
                      {"bid": "NaN", "ask": "770.1", "at": self.clock.now()},
                      {"bid": "1100", "ask": "1100.1", "at": self.clock.now()}]:
            self.broker.quote_override = quote
            with self.assertRaises(paper.SafetyError):
                self.runner.preflight(self.account)
        self.assertEqual(self.broker.submits, [])

    def test_nonfinite_and_malformed_numbers_rejected(self):
        for value in ["NaN", "Infinity", "-1", True, 0.5, "1e9", "0", "1.000000001"]:
            with self.assertRaises(paper.SafetyError):
                paper.number(value)

    def test_four_write_attempts_persist_across_restart(self):
        for _ in range(4):
            self.gate.before("POST")
        gate = paper.Gate(self.config, now=self.clock.now, sleep=self.clock.sleep)
        gate.attach(self.journal)
        with self.assertRaisesRegex(paper.SafetyError, "write_budget"):
            gate.before("DELETE")

    def test_total_http_rate_budget_and_timeout(self):
        for _ in range(121):
            self.gate.before("GET")
        times = [e["at"] for e in self.journal.events if e["event"] == "request"]
        self.assertGreaterEqual(times[-1] - times[0], 60)
        self.clock.value = self.gate.deadline - 4
        with self.assertRaisesRegex(paper.SafetyError, "deadline"):
            self.gate.before("GET")

    def test_partial_journal_fails_closed(self):
        path = self.root / "partial.jsonl"
        path.write_text('{"event":"submit_intent"')
        with self.assertRaisesRegex(paper.SafetyError, "incomplete"):
            paper.Journal(path)

    def test_observed_fill_over_qty_or_limit_fails_closed(self):
        intent = self.runner.intent("buy", "fixture-trial", "1", "770.50")
        self.journal.add("submit_intent", intent=intent)
        order = self.broker.submit(intent)
        for changed in [{"filled_qty": "2"}, {"filled_avg_price": "800"}, {"symbol": "AAPL"}]:
            with self.assertRaises(paper.SafetyError):
                self.runner.validate_order({**order, **changed}, intent)

    def test_method_path_allowlist_rejects_live_redirect_and_blanket_close(self):
        self.assertTrue(paper.allowed_request(paper.PAPER_URL, "POST", paper.PAPER_URL + "/v2/orders"))
        self.assertTrue(paper.allowed_request(paper.DATA_URL, "GET", paper.DATA_URL + "/v2/stocks/quotes/latest"))
        for method, url in [("POST", "https://api.alpaca.markets/v2/orders"),
                            ("DELETE", paper.PAPER_URL + "/v2/positions"),
                            ("DELETE", paper.PAPER_URL + "/v2/orders"),
                            ("PATCH", paper.PAPER_URL + "/v2/account"),
                            ("POST", paper.PAPER_URL + "/v2/orders?redirect=live")]:
            self.assertFalse(paper.allowed_request(paper.PAPER_URL, method, url))

    def test_closed_clock_drift_and_nonfinite_close_block_entry(self):
        for patch in [{"open": False}, {"at": self.clock.now() + 6}, {"close": float("nan")},
                      {"close": self.clock.now() + 299}]:
            self.broker.clock = lambda: {"open": True, "at": self.clock.now(), "close": self.clock.now() + 3600, **patch}
            with self.assertRaises(paper.SafetyError):
                self.runner.preflight(self.account)
        self.assertEqual(self.broker.submits, [])

    def test_insufficient_cleanup_reserve_never_submits(self):
        self.runner.preflight(self.account)
        self.gate.deadline = self.clock.now() + 90
        with self.assertRaisesRegex(paper.SafetyError, "cleanup_time_reserve"):
            self.runner.lifecycle("fixture-trial", False)
        self.assertEqual(self.broker.submits, [])

    def test_recovery_rejects_altered_intent(self):
        self.journal.add("trial", trial="fixture-trial", config=self.config)
        intent = self.runner.intent("buy", "fixture-trial", "1", "770.50")
        self.journal.add("submit_intent", intent={**intent, "symbol": "AAPL"})
        with self.assertRaisesRegex(paper.SafetyError, "journal_intent"):
            self.runner.lifecycle("fixture-trial", True)
        self.assertEqual(self.broker.submits, [])

    def test_account_equity_and_flags_fail_closed(self):
        for change in [{"equity": "24999"}, {"blocked": True}, {"account_blocked": None}]:
            with self.assertRaises(paper.SafetyError):
                self.runner.preflight({**self.account, **change})
        self.assertEqual(self.broker.submits, [])

    def test_known_partial_order_is_canceled_despite_lookup_visibility_gap(self):
        self.broker.scenario = "partial_cancel_race"
        def missing_lookup(_):
            self.gate.before("GET")
            return None
        self.broker.lookup = missing_lookup
        with self.assertRaisesRegex(paper.SafetyError, "cancel_finality_unobserved"):
            self.run_trial()
        self.assertEqual(self.broker.cancels, ["broker-buy"])
        self.assertEqual(len(self.broker.submits), 1)

    def test_freshness_revalidated_after_transport_rate_wait(self):
        self.runner.quote()
        at, offset = self.runner.last_quote
        self.clock.value = at + 14.8
        self.gate.recent.append(self.clock.now())
        intent = self.runner.intent("buy", "fixture-trial", "1", "770.50")
        with self.assertRaisesRegex(paper.SafetyError, "quote_not_fresh_at_submit"):
            self.runner.submit_once(intent)
        self.assertEqual(self.broker.submits, [])

    def session_guard_fixture(self, side, remaining, *, rate_wait=False, clock_latency=0):
        """Frozen close and controllable reads; the POST still uses the real Gate."""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        clock = Time()
        journal = paper.Journal(root / "journal.jsonl")
        self.addCleanup(journal.close)
        gate = paper.Gate(self.config, journal, clock.now, clock.sleep)
        broker = FakeBroker(gate)
        close = clock.now() + remaining

        def broker_clock():
            observed = clock.now()
            clock.sleep(clock_latency)
            return {"open": True, "at": observed, "close": close}

        broker.clock = broker_clock
        broker.quote = lambda: {"bid": "770.40", "ask": "770.45", "at": clock.now()}
        runner = paper.Runner(broker, self.config, journal, gate, root / "STOP")
        runner.quote()
        if rate_wait:
            gate.recent.append(clock.now())
        intent = runner.intent(side, "fixture-trial", "1", "770.50" if side == "buy" else "770.35")
        return runner, broker, journal, intent

    def test_entry_and_exit_session_buffers_at_exact_post_boundary(self):
        for side, minimum in (("buy", 300), ("sell", 60)):
            for delta in (-0.01, 0, 0.01):
                with self.subTest(side=side, delta=delta):
                    # Keep the clock read above its 60-second admission threshold;
                    # move time after the read to exercise only final POST admission.
                    runner, broker, journal, intent = self.session_guard_fixture(side, minimum + 1)
                    runner.gate.sleep(1 - delta)
                    if delta < 0:
                        with self.assertRaisesRegex(paper.SafetyError, "session_buffer_exhausted_at_submit"):
                            runner.submit_once(intent)
                        self.assertEqual(broker.submits, [])
                        self.assertFalse(any(e.get("write") for e in journal.events))
                    else:
                        runner.submit_once(intent)
                        self.assertEqual(len(broker.submits), 1)

    def test_entry_and_exit_session_buffers_rechecked_after_rate_wait(self):
        for side, minimum in (("buy", 300), ("sell", 60)):
            with self.subTest(side=side):
                runner, broker, journal, intent = self.session_guard_fixture(side, minimum + 0.25, rate_wait=True)
                with self.assertRaisesRegex(paper.SafetyError, "session_buffer_exhausted_at_submit"):
                    runner.submit_once(intent)
                self.assertEqual(broker.submits, [])
                self.assertFalse(any(e.get("write") for e in journal.events))

    def test_clock_response_latency_cannot_extend_entry_or_exit_buffer(self):
        for side, minimum in (("buy", 300), ("sell", 60)):
            with self.subTest(side=side):
                runner, broker, journal, intent = self.session_guard_fixture(side, minimum + 0.25, clock_latency=1)
                with self.assertRaisesRegex(paper.SafetyError, "session_buffer_exhausted_at_submit"):
                    runner.submit_once(intent)
                self.assertEqual(broker.submits, [])
                self.assertFalse(any(e.get("write") for e in journal.events))

    def test_entry_buffer_rechecked_after_lifecycle_reads(self):
        self.runner.preflight(self.account)
        close = None

        def fixed_clock():
            nonlocal close
            self.gate.before("GET")
            if close is None:
                close = self.clock.now() + 300.1
            return {"open": True, "at": self.clock.now(), "close": close}

        self.broker.clock = fixed_clock
        original_positions = self.broker.positions

        def delayed_positions():
            self.clock.sleep(1)
            return original_positions()

        self.broker.positions = delayed_positions
        with self.assertRaisesRegex(paper.SafetyError, "session_buffer_exhausted_at_submit"):
            self.runner.lifecycle("fixture-trial", False)
        self.assertEqual(self.broker.submits, [])

    def test_submit_requires_retained_clock_and_rejects_backward_time(self):
        for missing in (False, True):
            with self.subTest(missing_clock=missing):
                runner, broker, journal, intent = self.session_guard_fixture("buy", 3600)
                if missing:
                    runner.last_clock = None
                else:
                    runner.gate.sleep(-0.1)
                with self.assertRaisesRegex(paper.SafetyError,
                        "session_clock_required_at_submit" if missing else "clock_moved_backward"):
                    runner.submit_once(intent)
                self.assertEqual(broker.submits, [])


if __name__ == "__main__":
    unittest.main()
