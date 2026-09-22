"""Local cross-module tests: native engine, controller, ledger, synthetic port."""
import asyncio
from dataclasses import replace
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / "blueprints/us-equities/adaptive-paper"
sys.path.insert(0, str(SOURCE))
try:
    import nautilus_trader
    import alpaca
    from runner import Controller, reconcile, run_native, load_config, validate_preflight
    from safety import Ledger, Quote, RiskLimits, SafetyError
    from strategies import PolicyConfig
    from simulation import SimulatedPort
    NATIVE = True
except ImportError:
    NATIVE = False

# runner.py itself (and safety.py) import cleanly without nautilus_trader/alpaca
# (those are only imported lazily inside run_native/recovery paths), so the
# promotion-gate and credential-permission tests below run unconditionally.
import runner as runner_module
from runner import credentials, validate_preflight as validate_preflight_always
from safety import SafetyError as SafetyErrorAlways


@unittest.skipUnless(NATIVE, "requires pinned combined native runtime")
class IntegratedRunner(unittest.TestCase):
    def test_default_config_is_bounded(self):
        config, risk, policy = load_config(SOURCE / "config.json")
        self.assertEqual(risk.max_submits_per_minute, 180)
        self.assertEqual(policy.max_leverage, 1)
        self.assertEqual(len(policy.symbols), 24)

    def test_native_adaptive_policy_reaches_ledger_and_flat_reconciliation(self):
        config, _, _ = load_config(SOURCE / "config.json")
        config.update(duration_seconds=2, cleanup_seconds=2, order_timeout_seconds=1)
        with tempfile.TemporaryDirectory() as root:
            limits = RiskLimits(trial_seconds=2, cleanup_seconds=2)
            ledger = Ledger(Path(root) / "journal.db", limits)
            ledger.start_trial(time.time())
            controller = Controller(ledger, time.time() + 3600, market_open=True)
            policy = PolicyConfig(symbols=("SPY", "QQQ", "IWM", "DIA", "AAPL", "MSFT"), max_positions=6,
                                  warmup_samples=4, warmup_seconds=.06, sample_seconds=.02,
                                  rebalance_seconds=.02, min_hold_seconds=.05, max_hold_seconds=.4,
                                  cooldown_seconds=.05)
            def price(symbol, tick):
                slope = Decimal(".03") if symbol in policy.benchmarks else Decimal(".10")
                return Decimal("100") + min(tick, 70) * slope
            port = SimulatedPort(controller, policy.symbols, price=price)
            controller.port = port
            result = asyncio.run(run_native(controller, policy, [{"symbol": s} for s in policy.symbols],
                                            "fixture", config, "100000"))
            self.assertEqual(result["status"], "passed", result)
            self.assertTrue(result["flat"])
            self.assertGreater(result["native_fill_events"], 0, result)
            self.assertTrue(any(e["type"] == "intent" for e in controller.events))
            self.assertEqual(len(ledger.unresolved()), 0)
            self.assertEqual(port.started, 1)
            self.assertEqual(port.stopped, 1)
            ledger.close()

    def test_reconcile_rejects_external_position_and_cash_gap(self):
        with tempfile.TemporaryDirectory() as root:
            ledger = Ledger(Path(root) / "journal.db")
            snapshot = {"complete": True, "orders": [], "positions": [{"symbol": "SPY", "qty": "1"}],
                        "account": {"cash": "100000"}}
            with self.assertRaisesRegex(SafetyError, "position_mismatch"):
                reconcile(ledger, snapshot, "100000")
            snapshot["positions"] = []
            snapshot["account"]["cash"] = "99999"
            with self.assertRaisesRegex(SafetyError, "cash_mismatch"):
                reconcile(ledger, snapshot, "100000")
            ledger.close()

    def test_submission_rate_defers_without_waiting_or_selling_held_positions(self):
        from native_adapter import NativeOrderRejected
        from strategies import AdaptivePolicy
        now = time.time()
        with tempfile.TemporaryDirectory() as root:
            ledger = Ledger(Path(root) / "journal.db")
            ledger.start_trial(now)
            controller = Controller(ledger, now + 3600, market_open=True, clock=lambda: now)
            controller.port = type("Port", (), {"ready": True})()
            controller.quote({"symbol": "SPY", "bid": "100", "ask": "100.01", "ts_ns": int(now * 1e9)})
            payload = {"client_order_id": "rate-test", "symbol": "SPY", "side": "buy", "qty": "1", "limit_price": "100.03"}
            controller.before_submit(payload)
            for _ in range(180):
                self.assertEqual(ledger.request_budget(now, "submit"), 0)
            started = time.monotonic()
            with self.assertRaisesRegex(SafetyError, "submission_rate_deferred"):
                asyncio.run(controller.before_request("submit", "rate-test"))
            self.assertLess(time.monotonic() - started, .1)
            self.assertGreater(controller.defer_until, now)
            self.assertEqual(ledger.request_budget(now, "cancel"), 0)
            self.assertFalse(ledger.intents()[0].submit_attempted)
            ledger.close()

    def test_restart_ids_use_highest_reserved_sequence_and_native_config(self):
        from native_strategy import AdaptiveStrategy
        from strategies import AdaptivePolicy
        now = time.time()
        with tempfile.TemporaryDirectory() as root:
            ledger = Ledger(Path(root) / "journal.db")
            ledger.start_trial(now)
            for sequence in (1, 2, 4):
                cid = f"adp-fixture-{sequence:07d}"
                ledger.reserve_intent(cid, "SPY", "buy", "1", "100.03",
                    quote=Quote("SPY", "100", "100.01", now), now=now,
                    market_open=True, session_close=now + 3600)
                ledger.mark_not_sent(cid, "fixture_unsent")
            _, _, policy = load_config(SOURCE / "config.json")
            strategy = AdaptiveStrategy(AdaptivePolicy(policy), ledger, "fixture")
            self.assertEqual(strategy.sequence, 4)
            self.assertEqual(str(strategy.strategy_id), "ADAPTIVE-001-A")
            ledger.close()

    def test_proven_broker_refusal_is_retained_without_poisoning_flat_reconciliation(self):
        from transport import RejectedSubmission
        now = time.time()
        with tempfile.TemporaryDirectory() as root:
            ledger = Ledger(Path(root) / "journal.db")
            ledger.start_trial(now)
            controller = Controller(ledger, now + 3600, market_open=True)
            class RefusingPort:
                ready = True
                async def submit(self, payload):
                    controller.before_submit(payload)
                    await controller.before_request("submit", payload["client_order_id"])
                    raise RejectedSubmission(403)
            controller.port = controller.bind(RefusingPort())
            controller.quote({"symbol": "SPY", "bid": "100", "ask": "100.01", "ts_ns": time.time_ns()})
            payload = {"client_order_id": "refused-test", "symbol": "SPY", "side": "buy", "qty": "1", "limit_price": "100.03"}
            with self.assertRaises(RejectedSubmission):
                asyncio.run(controller.port.submit(payload))
            intent = ledger.intents()[0]
            self.assertEqual(intent.status, "broker_refused")
            self.assertTrue(intent.submit_attempted)
            proof = reconcile(ledger, {"complete": True, "orders": [], "positions": [], "account": {"cash": "100000"}}, "100000")
            self.assertEqual(proof["open_orders"], 0)
            ledger.close()

    def test_recovery_preflight_does_not_require_entry_cash_or_unrelated_quotes(self):
        config, _, _ = load_config(SOURCE / "config.json")
        now = time.time_ns()
        observation = {"account": {"status": "ACTIVE", "currency": "USD", "cash": "500", "equity": "1000",
                        "trading_blocked": False, "account_blocked": False, "trade_suspended_by_user": False},
                       "clock": {"timestamp_ns": now, "received_at_ns": now, "next_close_ns": now + 60_000_000_000, "is_open": True},
                       "positions": [{"symbol": "SPY", "qty": "1"}], "orders": [],
                       "assets": [{"symbol": "SPY", "status": "active", "tradable": True}], "quotes": []}
        validate_preflight(observation, config, require_open=True, allow_existing=True)
        with self.assertRaisesRegex(SafetyError, "account_not_ready"):
            validate_preflight(observation, config, require_open=True)


def _paper_ready_observation(now_ns, symbols=("SPY",)):
    return {"account": {"status": "ACTIVE", "currency": "USD", "cash": "10000", "equity": "30000",
                        "trading_blocked": False, "account_blocked": False, "trade_suspended_by_user": False},
            "clock": {"timestamp_ns": now_ns, "received_at_ns": now_ns, "next_close_ns": now_ns + 3600_000_000_000,
                      "is_open": True},
            "positions": [], "orders": [],
            "assets": [{"symbol": s, "status": "active", "tradable": True} for s in symbols],
            "quotes": [{"symbol": s, "ts_ns": now_ns} for s in symbols]}


def _paper_ready_config(symbols=("SPY",)):
    return {"capital_usd": "10000", "duration_seconds": 60, "cleanup_seconds": 10,
            "symbols": list(symbols), "benchmarks": list(symbols), "quote_max_age_seconds": 5}


def _full_gate_result(*, status="pass", row_count=4, checks_status="pass", input_sha256=None):
    """A gate-result.json body with the full contract `_check_promotion_gate`
    now requires (status, input_sha256, row_count, checks, versions,
    checked_at) -- shaped like a real `promotion_gate.py` output, not the
    bare {status, input_sha256} pairs the pre-fix runtime accepted."""
    return {
        "status": status,
        "input_sha256": input_sha256,
        "row_count": row_count,
        "checks": [{"name": "rows_present", "status": checks_status, "detail": "ok"}],
        "versions": {"pandera": "0.33.1"},
        "checked_at": "2026-09-22T00:00:00+00:00",
    }


class PromotionGatePreflight(unittest.TestCase):
    """`mode="paper"` requires a complete, fully-passing, hash-matched
    promotion-gate result; `mode=None` (every pre-existing call) is
    unaffected. Does not require the pinned nautilus_trader/alpaca runtime:
    runner.py imports those lazily."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.snapshot = self.root / "snapshot.csv"
        self.snapshot.write_text("symbol\nSPY\n")
        self.snapshot_hash = hashlib.sha256(self.snapshot.read_bytes()).hexdigest()
        self.now_ns = time.time_ns()
        self.observation = _paper_ready_observation(self.now_ns)
        self.config = _paper_ready_config()

    def tearDown(self):
        self.tmp.cleanup()

    def _call(self, **gate_kwargs):
        return validate_preflight_always(self.observation, self.config, require_open=True,
                                          mode="paper", **gate_kwargs)

    def _write_gate(self, **fields):
        gate_path = self.root / "gate-result.json"
        gate_path.write_text(json.dumps(_full_gate_result(**fields)))
        return gate_path

    def test_mode_none_is_unaffected_by_missing_gate_arguments(self):
        # Every pre-existing preflight/recover call site omits mode/gate args.
        validate_preflight_always(self.observation, self.config, require_open=True)

    def test_missing_gate_result_path_raises_promotion_gate_missing(self):
        with self.assertRaisesRegex(SafetyErrorAlways, "promotion_gate_missing"):
            self._call(snapshot_path=self.snapshot)

    def test_missing_snapshot_path_raises_promotion_gate_missing(self):
        gate_path = self._write_gate(input_sha256=self.snapshot_hash)
        with self.assertRaisesRegex(SafetyErrorAlways, "promotion_gate_missing"):
            self._call(gate_result_path=gate_path)

    def test_nonexistent_gate_result_file_raises_promotion_gate_missing(self):
        with self.assertRaisesRegex(SafetyErrorAlways, "promotion_gate_missing"):
            self._call(gate_result_path=self.root / "does-not-exist.json", snapshot_path=self.snapshot)

    def test_unparseable_gate_result_file_raises_promotion_gate_missing(self):
        gate_path = self.root / "gate-result.json"
        gate_path.write_text("not json")
        with self.assertRaisesRegex(SafetyErrorAlways, "promotion_gate_missing"):
            self._call(gate_result_path=gate_path, snapshot_path=self.snapshot)

    def test_failing_gate_status_raises_promotion_gate_failed(self):
        gate_path = self._write_gate(status="fail", input_sha256=self.snapshot_hash)
        with self.assertRaisesRegex(SafetyErrorAlways, "promotion_gate_failed$"):
            self._call(gate_result_path=gate_path, snapshot_path=self.snapshot)

    def test_mismatched_hash_raises_promotion_gate_mismatch(self):
        gate_path = self._write_gate(input_sha256="0" * 64)
        with self.assertRaisesRegex(SafetyErrorAlways, "promotion_gate_mismatch"):
            self._call(gate_result_path=gate_path, snapshot_path=self.snapshot)

    def test_passing_matched_gate_allows_preflight_to_proceed(self):
        gate_path = self._write_gate(input_sha256=self.snapshot_hash)
        close = self._call(gate_result_path=gate_path, snapshot_path=self.snapshot)
        self.assertEqual(close, (self.now_ns + 3600_000_000_000) / 1e9)

    def test_passing_gate_still_enforces_ordinary_account_checks(self):
        gate_path = self._write_gate(input_sha256=self.snapshot_hash)
        self.observation["account"]["trading_blocked"] = True
        with self.assertRaisesRegex(SafetyErrorAlways, "account_not_ready"):
            self._call(gate_result_path=gate_path, snapshot_path=self.snapshot)

    # --- Regression (finding 3): the pre-fix _check_promotion_gate only ever
    # read gate["status"] and gate["input_sha256"], so a gate result declaring
    # row_count=0 or carrying a failed check but a "pass" top-level status
    # (and a matching hash) was wrongly accepted. ---

    def test_gate_result_missing_required_keys_raises_promotion_gate_incomplete(self):
        gate_path = self.root / "gate-result.json"
        gate_path.write_text(json.dumps({"status": "pass", "input_sha256": self.snapshot_hash}))
        with self.assertRaisesRegex(SafetyErrorAlways, "promotion_gate_incomplete"):
            self._call(gate_result_path=gate_path, snapshot_path=self.snapshot)

    def test_gate_result_with_empty_checks_list_raises_promotion_gate_incomplete(self):
        gate_path = self.root / "gate-result.json"
        body = _full_gate_result(input_sha256=self.snapshot_hash)
        body["checks"] = []
        gate_path.write_text(json.dumps(body))
        with self.assertRaisesRegex(SafetyErrorAlways, "promotion_gate_incomplete"):
            self._call(gate_result_path=gate_path, snapshot_path=self.snapshot)

    def test_gate_result_with_zero_row_count_raises_promotion_gate_empty(self):
        """The exact review-finding scenario: top-level status "pass", hash
        matches, but row_count is 0."""
        gate_path = self._write_gate(row_count=0, input_sha256=self.snapshot_hash)
        with self.assertRaisesRegex(SafetyErrorAlways, "promotion_gate_empty"):
            self._call(gate_result_path=gate_path, snapshot_path=self.snapshot)

    def test_gate_result_with_a_failed_check_raises_promotion_gate_failed_check(self):
        """The other review-finding scenario: top-level status "pass", hash
        matches, but one of the named checks reports status "fail"."""
        gate_path = self._write_gate(checks_status="fail", input_sha256=self.snapshot_hash)
        with self.assertRaisesRegex(SafetyErrorAlways, "promotion_gate_failed_check"):
            self._call(gate_result_path=gate_path, snapshot_path=self.snapshot)

    def test_snapshot_with_unaccepted_extension_raises_promotion_gate_missing(self):
        """`--snapshot` must reference a file the gate itself could accept
        (`.csv`/`.parquet`); a `.json` config file (or any other extension)
        can never legitimately be the gated snapshot."""
        bogus_snapshot = self.root / "config.json"
        bogus_snapshot.write_text('{"symbols": ["SPY"]}')
        bogus_hash = hashlib.sha256(bogus_snapshot.read_bytes()).hexdigest()
        gate_path = self._write_gate(input_sha256=bogus_hash)
        with self.assertRaisesRegex(SafetyErrorAlways, "promotion_gate_missing"):
            self._call(gate_result_path=gate_path, snapshot_path=bogus_snapshot)

    def test_snapshot_path_that_is_a_directory_raises_promotion_gate_missing(self):
        directory_snapshot = self.root / "snapshot-dir.csv"
        directory_snapshot.mkdir()
        gate_path = self._write_gate(input_sha256="0" * 64)
        with self.assertRaisesRegex(SafetyErrorAlways, "promotion_gate_missing"):
            self._call(gate_result_path=gate_path, snapshot_path=directory_snapshot)


class MainCommandGateWiring(unittest.TestCase):
    """Regression: review found `python3 runner.py paper ...` bypassed the
    promotion gate entirely -- `main()` registered no `--gate-result`/
    `--snapshot` arguments and its `paper`/`recover` call site omitted the
    new `mode`/`gate_result_path`/`snapshot_path` kwargs, so `validate_preflight`
    always ran with `mode=None`. These tests drive `runner.main()` itself
    (mocking only the network-touching `preflight` call and the
    native-runtime entry past the gate check) to prove the CLI wiring, not
    just the already-covered `validate_preflight` unit behavior."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.env_file = self.root / "paper.env"
        self.env_file.write_text("APCA_API_KEY_ID=fixture-key\nAPCA_API_SECRET_KEY=fixture-secret\n")
        os.chmod(self.env_file, 0o600)
        self.config_file = self.root / "config.json"
        self.config_file.write_text("{}")
        self.output = self.root / "output.json"
        self.snapshot = self.root / "universe.csv"
        self.snapshot.write_text("symbol\nSPY\n")
        self.snapshot_hash = hashlib.sha256(self.snapshot.read_bytes()).hexdigest()
        self.now_ns = time.time_ns()
        self.observation = _paper_ready_observation(self.now_ns)
        self.observation["account_identity_sha256"] = "fixture-account"
        self.config = _paper_ready_config()

    def tearDown(self):
        self.tmp.cleanup()

    def _argv(self, command, extra):
        return ["runner.py", command, "--env-file", str(self.env_file), "--config", str(self.config_file),
                "--output", str(self.output), "--state-root", str(self.root / "state"), *extra]

    def _run_main(self, command, extra=()):
        """Patches every dependency `main()` reaches before/at the gate check
        (config loading, credential parsing, the network preflight call) and
        makes `account_lock_fingerprint` -- the first thing `main()` touches
        immediately *after* a passing gate check -- raise a sentinel so the
        test can tell "gate check passed and execution continued" apart from
        "gate check raised/returned" without needing the pinned native
        runtime or an SQLite ledger. Returns `(sentinel, code, raised)`:
        `code` is `main()`'s return value (`None` if it raised instead), and
        `raised` is the exception instance if one propagated out of `main()`."""
        sentinel = RuntimeError("reached_post_gate_execution")
        with patch.object(sys, "argv", self._argv(command, extra)), \
             patch.object(runner_module, "load_config", return_value=(self.config, None, None)), \
             patch.object(runner_module, "credentials", return_value=("fixture-key", "fixture-secret")), \
             patch.object(runner_module, "preflight", return_value=self.observation), \
             patch.object(runner_module, "account_lock_fingerprint", side_effect=sentinel):
            try:
                code = runner_module.main()
                return sentinel, code, None
            except Exception as exc:  # noqa: BLE001 -- deliberately catches the sentinel too
                return sentinel, None, exc

    def test_paper_without_gate_arguments_is_blocked_before_execution_continues(self):
        sentinel, code, raised = self._run_main("paper")
        self.assertIsNone(raised)
        self.assertEqual(code, 2)
        result = json.loads(self.output.read_text())
        self.assertEqual(result["status"], "not_started")
        self.assertEqual(result["reason"], "promotion_gate_missing")

    def test_paper_with_failing_gate_result_is_blocked_before_execution_continues(self):
        gate_path = self.root / "gate-result.json"
        gate_path.write_text(json.dumps(_full_gate_result(status="fail", input_sha256=self.snapshot_hash)))
        sentinel, code, raised = self._run_main("paper", ["--gate-result", str(gate_path), "--snapshot", str(self.snapshot)])
        self.assertIsNone(raised)
        self.assertEqual(code, 2)
        result = json.loads(self.output.read_text())
        self.assertEqual(result["status"], "not_started")
        self.assertEqual(result["reason"], "promotion_gate_failed")

    def test_paper_with_mismatched_snapshot_hash_is_blocked(self):
        gate_path = self.root / "gate-result.json"
        gate_path.write_text(json.dumps(_full_gate_result(input_sha256="0" * 64)))
        sentinel, code, raised = self._run_main("paper", ["--gate-result", str(gate_path), "--snapshot", str(self.snapshot)])
        self.assertIsNone(raised)
        self.assertEqual(code, 2)
        result = json.loads(self.output.read_text())
        self.assertEqual(result["reason"], "promotion_gate_mismatch")

    def test_paper_with_zero_row_count_gate_result_is_blocked(self):
        """Regression (finding 3): a gate result with top-level status "pass"
        and a matching hash, but row_count=0, must not reach execution."""
        gate_path = self.root / "gate-result.json"
        gate_path.write_text(json.dumps(_full_gate_result(row_count=0, input_sha256=self.snapshot_hash)))
        sentinel, code, raised = self._run_main("paper", ["--gate-result", str(gate_path), "--snapshot", str(self.snapshot)])
        self.assertIsNone(raised)
        self.assertEqual(code, 2)
        result = json.loads(self.output.read_text())
        self.assertEqual(result["reason"], "promotion_gate_empty")

    def test_paper_with_a_failed_check_in_gate_result_is_blocked(self):
        """Regression (finding 3): a gate result with top-level status
        "pass" and a matching hash, but a failed named check, must not
        reach execution."""
        gate_path = self.root / "gate-result.json"
        gate_path.write_text(json.dumps(_full_gate_result(checks_status="fail", input_sha256=self.snapshot_hash)))
        sentinel, code, raised = self._run_main("paper", ["--gate-result", str(gate_path), "--snapshot", str(self.snapshot)])
        self.assertIsNone(raised)
        self.assertEqual(code, 2)
        result = json.loads(self.output.read_text())
        self.assertEqual(result["reason"], "promotion_gate_failed_check")

    def test_paper_with_passing_matched_gate_reaches_post_gate_execution(self):
        gate_path = self.root / "gate-result.json"
        gate_path.write_text(json.dumps(_full_gate_result(input_sha256=self.snapshot_hash)))
        sentinel, code, raised = self._run_main("paper", ["--gate-result", str(gate_path), "--snapshot", str(self.snapshot)])
        self.assertIsNone(code)
        self.assertIs(raised, sentinel)

    def test_recover_command_is_unaffected_by_missing_gate_arguments(self):
        """`recover` resumes a trial already admitted by an earlier `paper`
        run; it must not additionally require --gate-result/--snapshot."""
        self.observation["positions"] = [{"symbol": "SPY", "qty": "1"}]
        sentinel, code, raised = self._run_main("recover")
        self.assertIsNone(code)
        self.assertIs(raised, sentinel)

    def test_preflight_command_is_unaffected_by_missing_gate_arguments(self):
        sentinel, code, raised = self._run_main("preflight")
        self.assertIsNone(raised)
        self.assertEqual(code, 0)
        result = json.loads(self.output.read_text())
        self.assertEqual(result["status"], "ready")


class CredentialFilePermissions(unittest.TestCase):
    """runner.credentials() fails closed on env-file mode, ownership, and
    Git-worktree location before any line of the file is parsed."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _write_env(self, directory, name="paper.env", mode=0o600):
        path = directory / name
        path.write_text("APCA_API_KEY_ID=fixture-key\nAPCA_API_SECRET_KEY=fixture-secret\n")
        os.chmod(path, mode)
        return path

    def test_wrong_mode_is_rejected(self):
        path = self._write_env(self.root, mode=0o644)
        with self.assertRaisesRegex(SafetyErrorAlways, "credential_file_permissions"):
            credentials(path)

    def test_group_or_other_readable_mode_is_rejected(self):
        path = self._write_env(self.root, mode=0o640)
        with self.assertRaisesRegex(SafetyErrorAlways, "credential_file_permissions"):
            credentials(path)

    def test_wrong_owner_is_rejected(self):
        path = self._write_env(self.root)
        with patch.object(runner_module.os, "getuid", return_value=os.getuid() + 1):
            with self.assertRaisesRegex(SafetyErrorAlways, "credential_file_permissions"):
                credentials(path)

    def test_inside_git_worktree_is_rejected(self):
        repo_root = Path(__file__).resolve().parents[1]
        self.assertTrue((repo_root / ".git").exists(), "test assumes this checkout is a Git worktree")
        with tempfile.TemporaryDirectory(dir=repo_root) as inside:
            path = self._write_env(Path(inside))
            with self.assertRaisesRegex(SafetyErrorAlways, "credential_file_permissions"):
                credentials(path)

    def test_missing_file_is_rejected(self):
        with self.assertRaisesRegex(SafetyErrorAlways, "credential_file_permissions"):
            credentials(self.root / "does-not-exist.env")

    def test_passing_case_outside_worktree_mode_0600_own_uid_returns_credentials(self):
        path = self._write_env(self.root)
        self.assertEqual(credentials(path), ("fixture-key", "fixture-secret"))

    def test_error_never_includes_file_contents(self):
        path = self._write_env(self.root, mode=0o644)
        with self.assertRaises(SafetyErrorAlways) as ctx:
            credentials(path)
        self.assertNotIn("fixture-key", str(ctx.exception))
        self.assertNotIn("fixture-secret", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
