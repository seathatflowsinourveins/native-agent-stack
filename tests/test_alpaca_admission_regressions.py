"""Offline integration regressions for the selected mover admission source.

Uses the maintained native unittest fixtures and installed SDK; the account and
HTTP observations are independent fake broker values, never native acceptance.
"""
import asyncio
from contextlib import closing, contextmanager
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

try:
    from . import test_adaptive_paper_mover_native as native
    from . import test_adaptive_paper_transport as http_fixture
except ImportError:
    import test_adaptive_paper_mover_native as native
    import test_adaptive_paper_transport as http_fixture

# These modules defer SDK/native imports until port construction. Import them
# before setUpModule so the existing hermetic fixture also isolates Python-only
# admission checks from the host's STOP and account-lock paths.
import mover_runner
import safety
import transport


def setUpModule():
    native.setUpModule()


def tearDownModule():
    native.tearDownModule()


def observation(case, **fields):
    result = {"case": case, **fields}
    if directory := os.environ.get("ALPACA_ADMISSION_CASE_DIRECTORY"):
        path = Path(directory) / (hashlib.sha256(case.encode()).hexdigest()[:16] + ".json")
        with path.open("x") as output:
            json.dump(result, output, sort_keys=True, indent=2, default=str)
            output.write("\n")
    else:
        print("ADMISSION_CASE " + json.dumps(result, sort_keys=True, default=str))


def ledger_state(path):
    # Read-only observation must not initialize or change the ledger.
    with closing(sqlite3.connect(f"file:{path}?mode=ro", uri=True)) as db:
        return {table: db.execute(f"SELECT * FROM {table} ORDER BY 1").fetchall()
                for table in ("meta", "requests", "intents", "fees")}


class NextTrialBaselineValidation(unittest.TestCase):
    """Admission before port construction uses only the Python command and ledger."""

    def refuses(self, baseline_fields, reason):
        wiring = native.MoverPaperCommandWiring()
        wiring.setUp()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            scan_path = root / "scan.json"
            scan_path.write_bytes(native.scan_raw([native.row("AAA", 1, "10.00")]))
            state = root / "state" / wiring.FINGERPRINT / "mover"
            ledger_path = state / "ledger.sqlite3"
            _, limits, _ = mover_runner.load_mover_config(native.CONFIG)
            ledger = safety.Ledger(ledger_path, limits)
            try:
                ledger.begin_next_trial(time.time() - 30, "legacy")
            finally:
                ledger.close()
            metadata_path = state / "trial.json"
            metadata_path.write_text(json.dumps({"trial_id": "legacy", "phase": "finished",
                                                 "started_at": time.time() - 30, **baseline_fields}))
            metadata_before = metadata_path.read_bytes()
            before = ledger_state(ledger_path)
            real_load_scan = mover_runner.load_scan

            def checkpoint(key, secret, *, before_request, **kwargs):
                for _ in range(3):
                    before_request("read")
                return {"account": wiring.observation([])["account"], "fees": []}

            output = root / "refusal.json"
            with patch.object(mover_runner, "credentials", return_value=("key", "secret")), \
                 patch.object(transport, "preflight",
                              side_effect=lambda key, secret, symbols, **kw: wiring.observation(symbols)), \
                 patch.object(transport, "fee_checkpoint", side_effect=checkpoint) as checkpoint_read, \
                 patch.object(transport, "AlpacaPaperTransport",
                              side_effect=AssertionError("refused admission must not build a port")) as port, \
                 patch.object(mover_runner, "load_scan",
                              side_effect=lambda raw, settings, *, now:
                              real_load_scan(raw, settings, now=native.SCAN_TIME + 20)), \
                 patch("builtins.print"):
                code = mover_runner.main(["paper", "--env-file", str(root / "unused.env"),
                                          "--config", str(native.CONFIG), "--scan", str(scan_path),
                                          "--trial", "next", "--state-root", str(root / "state"),
                                          "--output", str(output)])
            receipt = json.loads(output.read_text())
            self.assertEqual((code, receipt["status"], receipt["stage"], receipt["reason"]),
                             (2, "not_started", "trial_start", reason))
            checkpoint_read.assert_called_once()
            port.assert_not_called()
            self.assertEqual(metadata_path.read_bytes(), metadata_before)
            after = ledger_state(ledger_path)
            for table in ("meta", "intents", "fees"):
                self.assertEqual(after[table], before[table])
            with closing(sqlite3.connect(f"file:{ledger_path}?mode=ro", uri=True)) as db:
                self.assertEqual(db.execute("SELECT trial_id FROM trials ORDER BY trial_id").fetchall(),
                                 [("legacy",)])

    def test_missing_baseline_refuses_without_consuming_trial_or_building_port(self):
        self.refuses({}, "next_trial_baseline_missing")

    def test_null_baseline_refuses_without_consuming_trial_or_building_port(self):
        self.refuses({"baseline_cash": None}, "next_trial_baseline_missing")

    def test_malformed_baseline_refuses_without_consuming_trial_or_building_port(self):
        for value in ("not-a-decimal", "", "NaN", "sNaN", "Infinity", "-Infinity", {}, [], True):
            with self.subTest(baseline=value):
                self.refuses({"baseline_cash": value}, "next_trial_baseline_invalid")


@unittest.skipUnless(native.NATIVE, "requires pinned combined native runtime")
class CashContinuity(unittest.TestCase):
    def setUp(self):
        self.wiring = native.MoverPaperCommandWiring()
        self.wiring.setUp()

    def case(self, delta, accepted, *, fee=False, next_config=False):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            (root / "scan.json").write_bytes(native.scan_raw([native.row("AAA", 1, "10.00")]))
            self.assertEqual(self.wiring.run_paper(root, "first")[0], 0)
            old = self.wiring.trial_json(root)
            ledger_path = root / "state" / self.wiring.FINGERPRINT / "mover" / "ledger.sqlite3"
            old_state = ledger_state(ledger_path)
            cash_before = self.wiring.broker.cash
            self.wiring.broker.cash += Decimal(delta)
            if fee:
                self.wiring.checkpoint_fees = [{"id": "20260924::" + str(__import__("uuid").UUID(int=1)),
                                               "date": "2026-09-24", "net_amount": "-0.50", "sub_type": "REG"}]
            config = None
            if next_config:
                data = json.loads(native.CONFIG.read_text())
                data["mover"]["session_scope"] = "any_session"
                data["mover"]["stream_quote_timeout_seconds"] = 30
                config = root / "ext.json"
                config.write_text(json.dumps(data))
            port_count = len(self.wiring.ports)
            code, receipt = self.wiring.run_paper(root, "second", config=config)
            new = self.wiring.trial_json(root)
            new_state = ledger_state(ledger_path)
            observation(f"cash:{delta}:fee={fee}:ext={next_config}",
                        sequence=["first trial", "independent broker cash change", "second admission"],
                        broker_cash_before=cash_before, broker_cash_at_admission=cash_before + Decimal(delta),
                        independent_cash_change=delta, independent_fee=bool(fee),
                        before_trial=old, after_trial=new, before_ledger=old_state, after_ledger=new_state,
                        port_calls_added=len(self.wiring.ports) - port_count, result=receipt, exit_code=code)
            if accepted:
                self.assertEqual(code, 0, receipt)
                self.assertEqual(Decimal(new["baseline_cash"]), Decimal("100000"))
                self.assertEqual(new["trial_id"], "second")
                if next_config:
                    self.assertNotEqual(old["config_sha256"], new["config_sha256"])
            else:
                self.assertEqual((code, receipt.get("reason")), (2, "next_trial_cash_mismatch"))
                self.assertEqual(new, old)
                self.assertEqual(len(self.wiring.ports), port_count)
                self.assertEqual(new_state["intents"], old_state["intents"])
                self.assertEqual(dict(new_state["meta"])["trial_id"], dict(old_state["meta"])["trial_id"])

    def test_unexplained_gain_refuses_before_trial_transition(self):
        self.case("5", False)

    def test_unexplained_loss_refuses_before_trial_transition(self):
        self.case("-5", False)

    def test_cash_tolerance_boundaries_preserve_original_baseline(self):
        for delta, accepted in (("0.01", True), ("-0.01", True),
                                ("0.010001", False), ("-0.010001", False)):
            with self.subTest(delta=delta):
                self.wiring.setUp()
                self.case(delta, accepted)

    def test_known_fee_is_booked_before_cash_comparison(self):
        self.case("-0.50", True, fee=True)

    def test_known_fee_does_not_hide_an_unexplained_gain_or_loss(self):
        for delta in ("4.50", "-5.50"):
            with self.subTest(delta=delta):
                self.wiring.setUp()
                self.case(delta, False, fee=True)

    def test_pre_to_extended_config_transition_keeps_original_cash_baseline(self):
        self.case("0", True, next_config=True)

    def test_paper_and_forced_recovery_supply_order_age_with_watchdog_thirty(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = self.wiring.fast_config(root)
            data = json.loads(config.read_text())
            data["mover"]["stream_quote_timeout_seconds"] = 30
            data["max_api_requests_per_minute"] = 150
            data["max_submit_requests_per_minute"] = 130
            config.write_text(json.dumps(data))
            (root / "scan.json").write_bytes(native.scan_raw([native.row("AAA", 1, "10.00")]))
            self.wiring.sell_blocked_ports = 1
            code, receipt = self.wiring.run_paper(root, "forced", config=config)
            observation("mover:paper-and-forced-port", timeouts=self.wiring.transport_timeouts,
                        exit_code=code, result_status=receipt["status"],
                        independent_broker_positions=self.wiring.broker.positions,
                        independent_broker_cash=self.wiring.broker.cash)
            self.assertEqual(len(self.wiring.transport_timeouts), 2)
            self.assertEqual(self.wiring.transport_timeouts,
                             [{"quote_timeout": 30, "order_quote_max_age_seconds": 3}] * 2)


class RecoveryFixture:
    def seed(self, root, binding="match", *, watchdog=30):
        data = json.loads(native.CONFIG.read_text())
        data["mover"]["stream_quote_timeout_seconds"] = watchdog
        data["max_api_requests_per_minute"] = 150
        data["max_submit_requests_per_minute"] = 130
        config = root / "config.json"
        config.write_text(json.dumps(data))
        config_sha = hashlib.sha256(config.read_bytes()).hexdigest()
        _, limits, _ = mover_runner.load_mover_config(config)
        state = root / "state" / native.MoverPaperCommandWiring.FINGERPRINT / "mover"
        ledger = safety.Ledger(state / "ledger.sqlite3", limits)
        ledger.begin_next_trial(time.time(), "old-trial")
        ledger.freeze("gross_loss_limit")
        ledger.close()
        metadata = {"trial_id": "old-trial", "config_sha256": config_sha,
                    "baseline_cash": "100000", "started_at": time.time() - 30,
                    "fee_window_start": time.time() - 30,
                    "phase": "needs_attention"}
        if binding == "different":
            other = dict(data, order_timeout_seconds=9)
            metadata["config_sha256"] = hashlib.sha256(json.dumps(other).encode()).hexdigest()
        elif binding == "missing":
            metadata.pop("config_sha256")
        elif binding == "malformed":
            metadata["config_sha256"] = {"sha256": config_sha}
        elif binding == "nonobject":
            metadata = []
        (state / "trial.json").write_text(json.dumps(metadata))
        return config, state

    def invoke(self, root, config, recovery, *, lock=None):
        fixture = native.MoverPaperCommandWiring()
        fixture.setUp()
        calls = []
        self.recovery_sequence = calls

        def preflight(key, secret, symbols, *, before_request, **kwargs):
            calls.append("preflight_identity_read")
            before_request("read")
            return fixture.observation(symbols)

        original_lock = mover_runner.account_lock_fingerprint

        @contextmanager
        def locked(fingerprint):
            calls.append("account_mutex")
            with original_lock(fingerprint):
                if lock:
                    lock()
                yield

        args = mover_runner.build_parser().parse_args([
            "recover", "--config", str(config), "--env-file", str(root / "unused.env"),
            "--state-root", str(root / "state"), "--output", str(root / "recover.json")])
        with patch.object(mover_runner, "credentials", return_value=("fixture-key", "fixture-secret")), \
             patch.object(transport, "preflight", preflight), \
             patch.object(transport, "_stream_classes", return_value=(http_fixture.FakeStream,) * 2), \
             patch.object(mover_runner, "account_lock_fingerprint", locked), \
             patch.object(mover_runner, "recover_mover", recovery), patch("builtins.print"):
            result = mover_runner.command_recover(args)
        return result, calls


@unittest.skipUnless(native.NATIVE, "requires pinned combined native runtime")
class RecoveryBinding(RecoveryFixture, unittest.TestCase):
    def test_mismatch_missing_malformed_refuse_before_mutable_ledger_effects(self):
        for binding in ("different", "missing", "malformed", "nonobject"):
            with self.subTest(binding=binding), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                config, state = self.seed(root, binding)
                before = ledger_state(state / "ledger.sqlite3")
                metadata_before = (state / "trial.json").read_bytes()
                effects = []

                async def recover(controller, metadata, config):
                    effects.append("recover")
                    return {"status": "passed", "flat": True, "errors": []}

                error = None
                try:
                    self.invoke(root, config, recover)
                except Exception as exc:
                    error = str(exc) if isinstance(exc, safety.SafetyError) else type(exc).__name__
                after = ledger_state(state / "ledger.sqlite3")
                observation("recover:" + binding, independent_broker={"cash": "100000", "positions": [], "orders": []},
                            numeric_limits=[150, 130], before_ledger=before, after_ledger=after,
                            sequence=self.recovery_sequence, mutable_recovery_calls=effects, error=error)
                self.assertEqual(error, "recovery_config_differs_from_frozen_trial")
                self.assertEqual(effects, [])
                self.assertEqual(after, before)
                self.assertEqual((state / "trial.json").read_bytes(), metadata_before)

    def test_binding_is_rechecked_under_account_mutex(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config, state = self.seed(root)
            before = ledger_state(state / "ledger.sqlite3")

            def replace_binding():
                metadata = json.loads((state / "trial.json").read_text())
                metadata["config_sha256"] = "f" * 64
                (state / "trial.json").write_text(json.dumps(metadata))

            async def recover(*args):
                return {"status": "passed", "flat": True, "errors": []}

            error = None
            try:
                self.invoke(root, config, recover, lock=replace_binding)
            except safety.SafetyError as exc:
                error = str(exc)
            after = ledger_state(state / "ledger.sqlite3")
            observation("recover:binding-race", sequence=self.recovery_sequence, error=error,
                        before_ledger=before, after_ledger=after,
                        independent_broker={"cash": "100000", "positions": [], "orders": []})
            self.assertEqual(error, "recovery_config_differs_from_frozen_trial")
            self.assertEqual(after, before)

    def test_matching_recovery_preserves_numeric_halt_and_creates_no_entries(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config, state = self.seed(root)
            before = ledger_state(state / "ledger.sqlite3")
            recovery_halts = []

            async def recover(controller, metadata, config):
                recovery_halts.append(controller.ledger.accounting().halted_reason)
                return {"status": "passed", "flat": True, "errors": []}

            code, calls = self.invoke(root, config, recover)
            after = ledger_state(state / "ledger.sqlite3")
            observation("recover:matching", sequence=calls, recovery_halts=recovery_halts,
                        before_ledger=before, after_ledger=after,
                        independent_broker={"cash": "100000", "positions": [], "orders": []})
            self.assertEqual(code, 0)
            self.assertEqual(calls, ["preflight_identity_read", "account_mutex"])
            self.assertEqual(recovery_halts, ["gross_loss_limit"])
            self.assertEqual(dict(after["meta"])["halted_reason"], dict(before["meta"])["halted_reason"])
            self.assertEqual(after["intents"], [])


@unittest.skipUnless(native.NATIVE, "requires pinned combined native runtime")
class ComposedRequestBudget(unittest.TestCase):
    NOW = 1_900_000_000.0

    def open(self, path, total, submits):
        return safety.Ledger(path, safety.RiskLimits(max_rest_per_minute=total, max_submits_per_minute=submits))

    def test_mixed_controls_and_submits_leave_twenty_total_slots_across_restart(self):
        for total, submit_cap, admitted in ((150, 130, 100), (200, 180, 150)):
            with self.subTest(total=total), tempfile.TemporaryDirectory() as root:
                path = Path(root) / "ledger.sqlite3"
                ledger = self.open(path, total, submit_cap)
                for kind in ("read", "cancel", "data_read"):
                    for _ in range(10):
                        self.assertEqual(ledger.request_budget(self.NOW, kind), 0)
                for _ in range(admitted):
                    self.assertEqual(ledger.request_budget(self.NOW, "submit"), 0)
                delay = ledger.request_budget(self.NOW, "submit")
                counts = dict(ledger.db.execute("SELECT kind,count(*) FROM requests GROUP BY kind"))
                ledger.close()
                observation(f"budget:mixed:{total}", sequence=["30 controls", f"{admitted} submits", "one deferred submit"],
                            limits=[total, submit_cap], reserved_counts=counts, delay=delay)
                self.assertEqual(delay, 60)
                ledger = self.open(path, total, submit_cap)
                try:
                    for _ in range(20):
                        self.assertEqual(ledger.request_budget(self.NOW, "cancel"), 0)
                    self.assertEqual(ledger.request_budget(self.NOW, "read"), 60)
                    self.assertEqual(ledger.request_budget(self.NOW + 59.5, "submit"), 0.5)
                    self.assertEqual(ledger.request_budget(self.NOW + 60, "submit"), 0)
                    observation(f"budget:restart-rollover:{total}",
                                sequence=["reopen", "20 reserved cancels", "read deferred 60s",
                                          "submit deferred 0.5s at 59.5s", "submit reserved at exact 60s"],
                                limits=[total, submit_cap],
                                request_rows=[list(row) for row in ledger.db.execute("SELECT * FROM requests ORDER BY id")])
                finally:
                    ledger.close()

    def test_unattempted_identity_is_not_changed_by_headroom_deferral(self):
        with tempfile.TemporaryDirectory() as root:
            ledger = self.open(Path(root) / "ledger.sqlite3", 150, 130)
            try:
                ledger.begin_next_trial(self.NOW, "budget")
                ledger.reserve_intent("budget-1", "SPY", "buy", "1", "100.01",
                                      quote=safety.Quote("SPY", "100", "100.01", self.NOW), now=self.NOW,
                                      market_open=True, session_close=self.NOW + 36000)
                for _ in range(130):
                    self.assertEqual(ledger.request_budget(self.NOW, "read"), 0)
                delay = ledger.request_budget(self.NOW, "submit", "budget-1")
                attempted = ledger.db.execute("SELECT submit_attempted FROM intents WHERE client_id='budget-1'").fetchone()[0]
                observation("budget:unattempted", independent_send_calls=[], delay=delay, submit_attempted=attempted,
                            requests=ledger.db.execute("SELECT count(*) FROM requests").fetchone()[0])
                self.assertEqual((delay, attempted), (60, 0))
                self.assertEqual(ledger.request_budget(self.NOW + 60, "submit", "budget-1"), 0)
                self.assertEqual(ledger.db.execute("SELECT submit_attempted FROM intents WHERE client_id='budget-1'").fetchone()[0], 1)
            finally:
                ledger.close()

    def test_two_connections_atomically_reserve_the_last_headroom_slot(self):
        for total, submit_cap, prior in ((150, 130, 129), (200, 180, 179)):
            with self.subTest(total=total), tempfile.TemporaryDirectory() as root:
                path = Path(root) / "ledger.sqlite3"
                first = self.open(path, total, submit_cap)
                other = self.open(path, total, submit_cap)
                try:
                    for _ in range(prior):
                        first.request_budget(self.NOW, "read")
                    barrier, results, errors = threading.Barrier(2), [], []

                    def reserve(ledger):
                        try:
                            barrier.wait()
                            results.append(ledger.request_budget(self.NOW, "submit"))
                        except Exception as exc:
                            errors.append(type(exc).__name__)

                    threads = [threading.Thread(target=reserve, args=(ledger,)) for ledger in (first, other)]
                    for thread in threads:
                        thread.start()
                    for thread in threads:
                        thread.join(timeout=5)
                    observation(f"budget:concurrent:{total}", limits=[total, submit_cap], delays=sorted(results),
                                errors=errors, reservations=first.db.execute("SELECT count(*) FROM requests").fetchone()[0])
                    self.assertFalse(any(thread.is_alive() for thread in threads))
                    self.assertEqual(errors, [])
                    self.assertEqual(sorted(results), [0, 60])
                finally:
                    first.close()
                    other.close()


@unittest.skipUnless(native.NATIVE, "requires pinned combined native runtime")
class MoverWireQuoteAge(RecoveryFixture, unittest.TestCase):
    # Invoke the real mover recovery construction site and real SDK POST boundary.
    # before_submit is replaced only to isolate the integer wire predicate from the
    # separately disclosed ledger float-epoch precision limitation.
    def wire_case(self, side, age_ns, allowed, *, delayed=False):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config, state = self.seed(root)
            sends, guards = [], []
            now = 1_900_000_000_000_000_000

            async def recover(controller, metadata, config):
                port = controller.port
                port._loop = asyncio.get_running_loop()
                port._started = True
                for channel in ("quotes", "orders"):
                    port._authorized(channel)
                    port._ack(channel, True)
                port._quote_seen["SPY"] = time.monotonic()
                port._quote_values["SPY"] = {"ts_ns": now - (0 if delayed else age_ns)}
                port.before_submit = lambda envelope: None
                port.sink_observation = lambda envelope: None

                def budget(kind, client_id=None):
                    if delayed:
                        port._quote_values["SPY"]["ts_ns"] = now - age_ns

                port.before_request = budget

                def request(method, url, **kwargs):
                    sends.append({"method": method, "body": kwargs.get("json")})
                    return http_fixture.response(http_fixture.order(side=side))

                error = None
                with patch.object(transport.time, "time_ns", return_value=now), \
                     patch.object(port._client._session._session, "request", side_effect=request):
                    try:
                        await port.submit(http_fixture.intent(side=side))
                    except transport.SubmissionNotSent:
                        error = "SubmissionNotSent"
                guards.append({"side": side, "age_ns": age_ns, "watchdog_seconds": port.quote_timeout,
                               "delayed": delayed, "error": error, "http_calls": list(sends),
                               "transport_intents": list(port._intents), "transport_not_sent": list(port._not_sent),
                               "predicate_scope": "final_sdk_wire; ledger float timestamp guard is isolated"})
                return {"status": "passed", "flat": True, "errors": []}

            self.invoke(root, config, recover)
            observation(f"mover-wire:{side}:{age_ns}:delayed={delayed}", guards=guards,
                        independent_broker={"cash": "100000", "positions": [], "orders": []})
            self.assertEqual(guards[0]["watchdog_seconds"], 30)
            self.assertEqual([call["method"] for call in sends], ["POST"] if allowed else [])
            self.assertEqual(guards[0]["error"], None if allowed else "SubmissionNotSent")

    def test_both_sides_exact_integer_age_and_future_boundaries(self):
        cases = ((2_999_999_999, True), (3_000_000_000, True), (3_000_000_001, False),
                 (-249_999_999, True), (-250_000_000, True), (-250_000_001, False))
        for side in ("buy", "sell"):
            for age_ns, allowed in cases:
                with self.subTest(side=side, age_ns=age_ns):
                    self.wire_case(side, age_ns, allowed)

    def test_delayed_pre_post_quote_expiry_refuses_both_sides_with_watchdog_thirty(self):
        for side in ("buy", "sell"):
            with self.subTest(side=side):
                self.wire_case(side, 3_000_000_001, False, delayed=True)
