"""Synthetic tests for the live run record and its read-only manifest; no broker or sockets."""
from decimal import Decimal as D
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "blueprints/us-equities/adaptive-paper"
sys.path.insert(0, str(SOURCE))
import live_manifest as lm  # noqa: E402
import safety as s  # noqa: E402

try:
    import nautilus_trader  # noqa: F401
    NATIVE = True
except ImportError:
    NATIVE = False

NOW = 1_800_000_000.0
FINGERPRINT = "ab" * 32


class LiveEventLogTests(unittest.TestCase):
    def test_appends_json_lines_as_events_happen_and_keeps_the_list(self):
        import runner
        with tempfile.TemporaryDirectory() as tmp:
            log = runner.LiveEventLog(Path(tmp) / "live" / "events.jsonl")
            log.append({"type": "decision", "regime": "trend", "targets": {"SPY": D("1")}})
            log.append({"type": "intent", "client_id": "c-1", "symbol": "SPY", "side": "buy"})
            rows = [json.loads(line) for line in (Path(tmp) / "live" / "events.jsonl").read_text().splitlines()]
            self.assertEqual([r["type"] for r in rows], ["decision", "intent"])
            self.assertEqual(rows[0]["targets"], {"SPY": "1"})
            self.assertIn("at", rows[0])
            self.assertEqual([e["type"] for e in log], ["decision", "intent"])
            self.assertEqual(log.write_errors, 0)

    def test_a_write_failure_is_counted_and_never_raised(self):
        import runner
        with tempfile.TemporaryDirectory() as tmp:
            log = runner.LiveEventLog(Path(tmp) / "events.jsonl")
            (Path(tmp) / "events.jsonl").mkdir()
            log.append({"type": "decision"})
            self.assertEqual((len(log), log.write_errors), (1, 1))


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        adaptive = self.root / FINGERPRINT / "adaptive"
        adaptive.mkdir(parents=True)
        ledger = s.Ledger(adaptive / "ledger.sqlite3")
        ledger.start_trial(NOW)
        quote = s.Quote("SPY", "100", "100.01", NOW)
        ledger.reserve_intent("adp-1", "SPY", "buy", "1", "100.02", quote=quote, now=NOW, market_open=True,
                              session_close=NOW + 3600, stop_file=self.root / "STOP")
        ledger.record_order("adp-1", "broker-1", "filled", "1", "100")
        ledger.close()
        self.live = self.root / "live" / "adaptive-test"
        (self.live / "nautilus").mkdir(parents=True)
        events = [{"at": NOW, "type": "decision", "regime": "trend", "targets": {"SPY": "1"}, "exits": {},
                   "effective_leverage": "1", "signals": []},
                  {"at": NOW + 1, "type": "intent", "client_id": "adp-1", "symbol": "SPY", "side": "buy",
                   "strategy": "trend_momentum", "reason": "entry"}]
        (self.live / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events) + "{truncated")
        (self.live / "nautilus" / "ADAPTIVE-001_x.jsonl").write_text(json.dumps(
            {"timestamp": "2026-09-23T18:00:00Z", "level": "INFO", "component": "ExecEngine",
             "message": f"Submit order account ALPACA-PAPER-{FINGERPRINT[:16]} id {FINGERPRINT}"}) + "\n" + json.dumps(
            {"timestamp": "2026-09-23T18:00:01Z", "level": "INFO", "component": "nautilus_portfolio::portfolio",
             "message": "Updated AccountState(account_id=ALPACA-PAPER, balances=[AccountBalance(total=123456.78 USD, "
                        "locked=0.00 USD, free=123456.78 USD)], margins=[MarginBalance(initial=1.00 USD)], event_id=x)"}) + "\n")

    def tearDown(self):
        self.tmp.cleanup()

    def test_state_reads_decisions_ledger_and_redacted_engine_log(self):
        st = lm.state(self.live, self.root, self.root / "STOP")
        self.assertFalse(st["stop_present"])
        self.assertEqual(st["events"]["counts"], {"decision": 1, "intent": 1})
        self.assertEqual(st["events"]["latest_decision"]["regime"], "trend")
        self.assertEqual(st["events"]["strategies"], {"trend_momentum": 1})
        ledger = st["ledger"]
        self.assertTrue(ledger["available"])
        self.assertEqual([(i["client_id"], i["status"], i["filled_qty"]) for i in ledger["intents"]],
                         [("adp-1", "filled", "1")])
        self.assertEqual(D(ledger["cash_delta_usd"]), D("-100"))
        text = json.dumps(st)
        self.assertNotIn(FINGERPRINT, text)
        self.assertNotIn(FINGERPRINT[:16], text)
        self.assertIn("[redacted]", st["nautilus_log"][1]["message"])
        self.assertNotIn("123456.78", text)
        self.assertIn("balances=[redacted]", st["nautilus_log"][0]["message"])
        self.assertIn("margins=[redacted]", st["nautilus_log"][0]["message"])

    def test_metrics_are_prometheus_text(self):
        text = lm.metrics(lm.state(self.live, self.root, self.root / "STOP"))
        self.assertIn('adaptive_paper_events{type="decision"} 1', text)
        self.assertIn('adaptive_paper_regime{regime="trend"} 1', text)
        self.assertIn('adaptive_paper_ledger_intents{status="filled"} 1', text)
        self.assertIn("adaptive_paper_cash_delta_usd -100.0", text)
        self.assertIn("adaptive_paper_open_positions 1", text)
        for line in text.splitlines():
            self.assertRegex(line, r'^(# TYPE [a-z_]+ gauge|[a-z_]+(\{[a-z_]+="[^"]*"\})? -?[0-9.]+)$')

    def test_missing_sources_degrade_without_raising(self):
        st = lm.state(None, self.root / "absent", self.root / "STOP")
        self.assertEqual((st["ledger"], st["events"]["counts"], st["nautilus_log"]), ({"available": False}, {}, []))
        lm.metrics(st)

    def test_the_ledger_is_opened_read_only(self):
        path = self.root / FINGERPRINT / "adaptive" / "ledger.sqlite3"
        before = path.stat().st_mtime_ns
        lm.read_ledger(path)
        self.assertEqual(path.stat().st_mtime_ns, before)


@unittest.skipUnless(NATIVE, "requires pinned Nautilus 2.0.0rc5 runtime")
class NativeFileLogTests(unittest.TestCase):
    def test_logger_config_adds_the_upstream_json_file_writer_only_when_asked(self):
        import native_adapter
        self.assertIsNone(native_adapter.logger_config().file_config)
        with tempfile.TemporaryDirectory() as tmp:
            config = native_adapter.logger_config(Path(tmp) / "nautilus")
            self.assertEqual((config.file_config.file_format, config.file_config.directory),
                             ("json", str(Path(tmp) / "nautilus")))
            self.assertEqual(str(config.fileout_level), "INFO")

    def test_a_native_node_writes_its_engine_events_to_the_json_log(self):
        # A fresh process: the native logger is process-wide and initialised once.
        script = (
            "import asyncio, sys; sys.path[:0] = [sys.argv[2], sys.argv[3]]\n"
            "import tests.test_adaptive_paper_native as t\n"
            "port, strategy = t.FakePort('fills'), t.Roundtrip('fills')\n"
            "session = t.ADAPTER.build_node(port, [{'symbol': 'SPY', 'currency': 'USD'}], [strategy], log_directory=sys.argv[1])\n"
            "asyncio.run(asyncio.wait_for(session.run_async(), timeout=8))\n"
            "assert session.errors == [] and strategy.fill_events == 4, (session.errors, strategy.fill_events)\n")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(__file__).resolve().parents[1]
            subprocess.run([sys.executable, "-c", script, str(Path(tmp) / "nautilus"), str(root), str(SOURCE)],
                           check=True, cwd=root, timeout=60, env={**os.environ, "HOME": tmp})
            files = list((Path(tmp) / "nautilus").glob("*.jsonl"))
            self.assertEqual(len(files), 1)
            rows = [json.loads(line) for line in files[0].read_text().splitlines()]
            self.assertTrue(any("SubmitOrder" in r["message"] for r in rows))
            self.assertTrue({"timestamp", "level", "component", "message"} <= rows[0].keys())


if __name__ == "__main__":
    unittest.main()
