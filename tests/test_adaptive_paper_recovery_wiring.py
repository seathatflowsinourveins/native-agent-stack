"""Offline recovery CLI wiring; broker, credentials and engine are replaced at their seams."""
import contextlib
from decimal import Decimal
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / "blueprints/us-equities/adaptive-paper"
sys.path.insert(0, str(SOURCE))
import recovery
import runner
from safety import Ledger, Quote, RiskLimits

try:
    from .adaptive_paper_hermetic import patch_default_stop, restore_default_stop
    from .test_adaptive_paper_recovery import RecoveryClock, TwoSymbolPort
    from .test_adaptive_paper_runner import _paper_ready_config, _paper_ready_observation
except ImportError:
    from adaptive_paper_hermetic import patch_default_stop, restore_default_stop
    from test_adaptive_paper_recovery import RecoveryClock, TwoSymbolPort
    from test_adaptive_paper_runner import _paper_ready_config, _paper_ready_observation


class RecoveryQuoteWiring(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="paper-recovery-wiring-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        token = patch_default_stop()
        self.addCleanup(restore_default_stop, token)
        self.config_path = self.root / "config.json"
        self.config_path.write_text("{}")
        self.output = self.root / "result.json"
        self.config = _paper_ready_config(("SPY", "QQQ"))
        self.config.update(benchmarks=["SPY"], order_timeout_seconds=0.05, cleanup_seconds=3)
        self.limits = RiskLimits(cleanup_seconds=3)
        self.observation = _paper_ready_observation(time.time_ns(), ("SPY", "QQQ"))
        self.observation["account_identity_sha256"] = "fixture-account"
        self.ports = []
        self.clock = RecoveryClock()

    def hold(self, ledger):
        now = time.time()
        ledger.start_trial(now)
        for symbol in ("SPY", "QQQ"):
            client_id = "entry-" + symbol.lower()
            ledger.reserve_intent(client_id, symbol, "buy", "1", "100.01",
                                  quote=Quote(symbol, "100", "100.01", now), now=now,
                                  market_open=True, session_close=now + 3600)
            ledger.request_budget(now, "submit", client_id=client_id)
            ledger.record_order(client_id, "broker-" + client_id, "filled", "1", "100.01", timestamp=now)

    def port(self, _key, _secret, symbols, **kwargs):
        clock = self.clock

        class StartupPort(TwoSymbolPort):
            SYMBOLS = ("SPY", "QQQ")
            PRICES = {"SPY": ("100.00", "100.01"), "QQQ": ("100.00", "100.01")}

            def publish_quote(self):
                # The broker never quotes QQQ during this bounded recovery.
                self.on_quote({"symbol": "SPY", "bid": "100.00", "ask": "100.01",
                               "ts_ns": time.time_ns()})

            async def start(self, *callbacks):
                await super().start(*callbacks)
                if set(self.required_quote_symbols) - self.c.quotes.keys():
                    raise runner.TransportError("required_startup_quote_missing")

            async def submit(self, payload):
                row = await super().submit(payload)
                # Deterministic deadline: the fresh SPY exit completes, leaving
                # too little frozen cleanup time to wait for unquoted QQQ.
                clock.now = 2.95
                return row

        value = StartupPort(kwargs["before_request"].__self__)
        value.required_quote_symbols = kwargs["required_quote_symbols"]
        value.before_request = kwargs["before_request"]
        value.cash = Decimal("10000") + value.c.ledger.accounting().cash_delta_usd
        value.held = {s: value.c.ledger.positions()[s].qty if s in value.c.ledger.positions() else Decimal(0)
                      for s in value.SYMBOLS}
        value.rows = {i.client_id: {"client_order_id": i.client_id, "id": i.broker_id,
            "symbol": i.symbol, "side": i.side, "qty": str(i.qty), "limit_price": str(i.limit_price),
            "status": i.status, "filled_qty": str(i.filled_qty), "filled_avg_price": "100.01",
            "updated_at_ns": time.time_ns()} for i in value.c.ledger.intents()}
        self.ports.append(value)
        return value

    def invoke(self, command):
        async def native_fault(controller, *_args, **_kwargs):
            self.hold(controller.ledger)
            return {"status": "needs_attention", "flat": False}

        argv = ["runner.py", command, "--env-file", str(self.root / "unused.env"),
                "--config", str(self.config_path), "--output", str(self.output),
                "--state-root", str(self.root / "state"), "--trial", "wiring-test"]
        with patch.object(sys, "argv", argv), \
             patch.object(runner, "load_config", return_value=(self.config, self.limits, None)), \
             patch.object(runner, "paper_credentials", return_value=("fixture-key", "fixture-secret")), \
             patch.object(runner, "preflight", return_value=self.observation), \
             patch.object(runner, "_check_promotion_gate"), \
             patch.object(runner, "account_lock_fingerprint", lambda _fingerprint: contextlib.nullcontext()), \
             patch.object(runner, "fee_checkpoint", return_value={"account": {"cash": "10000"}, "fees": []}), \
             patch.object(runner, "AlpacaPaperTransport", side_effect=self.port), \
             patch.object(runner, "run_native", side_effect=native_fault), \
             patch.object(runner.signal, "signal"), \
             patch.object(recovery, "time", self.clock), \
             contextlib.redirect_stdout(io.StringIO()):
            return runner.main()

    def assert_owned_exit_and_retained_residual(self):
        port = self.ports[-1]
        self.assertEqual([(p["symbol"], p["side"], p["qty"]) for p in port.submissions],
                         [("SPY", "sell", "1")])
        result = json.loads(self.output.read_text())
        recovery_result = result.get("recovery", result)
        self.assertEqual(recovery_result["errors"], ["recovery_quote_not_fresh"])
        self.assertEqual(recovery_result["positions"], [{"symbol": "QQQ", "qty": "1"}])
        self.assertEqual(recovery_result["stale_symbols"], ["QQQ"])
        self.assertFalse(result["flat"])
        self.assertEqual(port.stopped, 1)

    def test_explicit_recovery_waits_only_on_benchmarks_with_an_unquoted_holding(self):
        state = self.root / "state" / "fixture-account" / "adaptive"
        state.mkdir(parents=True)
        ledger = Ledger(state / "ledger.sqlite3", self.limits)
        try:
            self.hold(ledger)
        finally:
            ledger.close()
        (state / "trial.json").write_text(json.dumps({
            "trial_id": "wiring-test", "started_at": time.time() - 1, "baseline_cash": "10000",
            "config_sha256": hashlib.sha256(self.config_path.read_bytes()).hexdigest(), "phase": "running"}))
        self.assertEqual(self.invoke("recover"), 3)
        self.assertEqual(len(self.ports), 1)
        self.assertEqual(json.loads(self.output.read_text())["status"], "needs_attention")
        self.assert_owned_exit_and_retained_residual()

    def test_forced_recovery_retains_benchmark_readiness_after_native_fault(self):
        self.assertEqual(self.invoke("paper"), 3)
        self.assertEqual(len(self.ports), 2)
        self.assertEqual(json.loads(self.output.read_text())["status"], "needs_attention")
        self.assert_owned_exit_and_retained_residual()
