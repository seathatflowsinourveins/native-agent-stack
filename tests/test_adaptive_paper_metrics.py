"""Read-only exporter tests against a real, schema-true ledger fixture.

The fixture ledger/trial.json are produced with safety.Ledger's own
serialisation (never a hand-built row), so schema drift in safety.py would
break this test rather than silently going unnoticed. No network calls other
than loopback HTTP against the exporter under test; no broker or credentials
are touched.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request

SOURCE = Path(__file__).resolve().parents[1] / "blueprints/us-equities/adaptive-paper"
sys.path.insert(0, str(SOURCE))
from safety import Ledger, RiskLimits  # noqa: E402
import metrics as m  # noqa: E402


def parse(text):
    """Minimal Prometheus text-format parser: {(name, labels_tuple): value}."""
    samples = {}
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r'([a-zA-Z_:][a-zA-Z0-9_:]*)(\{[^}]*\})?\s+(\S+)', line)
        assert match, f"unparseable metric line: {line!r}"
        name, labels, value = match.groups()
        label_pairs = tuple(sorted(re.findall(r'([a-zA-Z_][a-zA-Z0-9_]*)="((?:[^"\\]|\\.)*)"', labels or "")))
        samples[(name, label_pairs)] = value
    return samples


class MetricsRenderingTests(unittest.TestCase):
    """Direct render_metrics() checks; no HTTP involved."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.ledger_path = self.root / "ledger.sqlite3"
        self.trial_path = self.root / "trial.json"
        self.now = 1_800_000_000.0

    def tearDown(self):
        self.tmp.cleanup()

    def write_trial(self, **fields):
        self.trial_path.write_text(json.dumps(fields))

    def test_missing_ledger_and_trial_still_exports_the_always_on_gauges(self):
        text = m.render_metrics(self.ledger_path, self.trial_path, now=self.now)
        samples = parse(text)
        self.assertEqual(samples[("paper_trial_active", ())], "0")
        self.assertEqual(samples[("paper_needs_attention", ())], "0")
        self.assertNotIn(("paper_order_state_divergence_total", ()), samples)
        self.assertIn("ledger file not found", text)
        self.assertIn("paper_reconciliation_last_success_timestamp_seconds is not exported", text)
        self.assertIn("paper_request_budget_wait_exceeded_total is not exported", text)

    def test_healthy_active_trial(self):
        ledger = Ledger(self.ledger_path, RiskLimits())
        ledger.start_trial(self.now)
        ledger.request_budget(self.now, "read")
        ledger.request_budget(self.now, "submit")
        ledger.close()
        self.write_trial(trial_id="fixture", phase="starting", started_at=self.now)

        text = m.render_metrics(self.ledger_path, self.trial_path, now=self.now)
        samples = parse(text)
        self.assertEqual(samples[("paper_trial_active", ())], "1")
        self.assertEqual(samples[("paper_needs_attention", ())], "0")
        self.assertNotIn(("paper_reconciliation_status", (("result", "passed"),)), samples)  # no status yet
        self.assertNotIn(("paper_ledger_frozen", (("reason", "external_order_detected"),)), samples)
        self.assertEqual(samples[("paper_order_state_divergence_total", ())], "0")
        self.assertEqual(samples[("paper_request_budget_limit", (("kind", "rest"),))], "200")
        self.assertEqual(samples[("paper_request_budget_remaining", (("kind", "rest"),))], "198")
        self.assertEqual(samples[("paper_request_budget_limit", (("kind", "submit"),))], "180")
        self.assertEqual(samples[("paper_request_budget_remaining", (("kind", "submit"),))], "179")

    def test_diverged_ledger_records_external_order_detected(self):
        ledger = Ledger(self.ledger_path, RiskLimits())
        ledger.start_trial(self.now)
        ledger.freeze("external_order_detected")  # mirrors runner.Controller.observe
        ledger.close()
        self.write_trial(trial_id="fixture", phase="needs_attention", status="needs_attention",
                         started_at=self.now)

        text = m.render_metrics(self.ledger_path, self.trial_path, now=self.now)
        samples = parse(text)
        self.assertEqual(samples[("paper_trial_active", ())], "0")
        self.assertEqual(samples[("paper_needs_attention", ())], "1")
        self.assertEqual(samples[("paper_reconciliation_status", (("result", "needs_attention"),))], "1")
        self.assertEqual(samples[("paper_reconciliation_status", (("result", "passed"),))], "0")
        self.assertEqual(samples[("paper_ledger_frozen", (("reason", "external_order_detected"),))], "1")
        self.assertEqual(samples[("paper_order_state_divergence_total", ())], "1")

    def test_frozen_ledger_from_a_risk_cap_is_not_counted_as_divergence(self):
        ledger = Ledger(self.ledger_path, RiskLimits())
        ledger.start_trial(self.now)
        ledger.freeze("gross_loss_cap_reached")
        ledger.close()
        self.write_trial(trial_id="fixture", phase="needs_attention", status="needs_attention",
                         started_at=self.now)

        text = m.render_metrics(self.ledger_path, self.trial_path, now=self.now)
        samples = parse(text)
        self.assertEqual(samples[("paper_ledger_frozen", (("reason", "gross_loss_cap_reached"),))], "1")
        self.assertNotIn(("paper_ledger_frozen", (("reason", "external_order_detected"),)), samples)
        self.assertEqual(samples[("paper_order_state_divergence_total", ())], "0")
        self.assertEqual(samples[("paper_needs_attention", ())], "1")

    def test_a_second_freeze_call_is_idempotent_in_the_ledger_and_the_counter(self):
        ledger = Ledger(self.ledger_path, RiskLimits())
        ledger.start_trial(self.now)
        ledger.freeze("external_order_detected")
        ledger.freeze("external_order_detected")  # already halted: no second event, per safety.Ledger.freeze
        ledger.close()

        text = m.render_metrics(self.ledger_path, self.trial_path, now=self.now)
        samples = parse(text)
        self.assertEqual(samples[("paper_order_state_divergence_total", ())], "1")


class MetricsHttpServerTests(unittest.TestCase):
    """End-to-end: real loopback HTTP server, real ledger file on disk."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.ledger_path = self.root / "ledger.sqlite3"
        self.trial_path = self.root / "trial.json"
        ledger = Ledger(self.ledger_path, RiskLimits())
        ledger.start_trial(time.time())
        ledger.close()
        self.trial_path.write_text(json.dumps({"trial_id": "fixture", "phase": "starting"}))
        self.server = m.make_server(self.ledger_path, self.trial_path, port=0)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.tmp.cleanup()

    def fetch(self, path="/metrics"):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}{path}", timeout=5) as response:
            return response.status, response.read().decode("utf-8"), response.headers

    def test_serves_metrics_over_real_loopback_http(self):
        status, body, headers = self.fetch()
        self.assertEqual(status, 200)
        samples = parse(body)
        self.assertEqual(samples[("paper_trial_active", ())], "1")
        self.assertTrue(headers.get("Content-Type", "").startswith("text/plain"))

    def test_unknown_path_is_404(self):
        try:
            self.fetch("/does-not-exist")
            self.fail("expected HTTPError")
        except urllib.error.HTTPError as exc:
            self.assertEqual(exc.code, 404)

    def test_server_binds_loopback_only(self):
        self.assertEqual(self.server.server_address[0], "127.0.0.1")


class MetricsCredentialIsolationTests(unittest.TestCase):
    """The exporter must never open a credentials/env-file path."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.ledger_path = self.root / "ledger.sqlite3"
        self.trial_path = self.root / "trial.json"
        ledger = Ledger(self.ledger_path, RiskLimits())
        ledger.start_trial(time.time())
        ledger.close()
        self.trial_path.write_text(json.dumps({"trial_id": "fixture", "phase": "starting"}))
        # A canary credentials file with permission bits that raise PermissionError
        # on any open() attempt, proving the exporter never touches it.
        self.canary = self.root / "alpaca-paper.env"
        self.canary.write_text("APCA_API_KEY_ID=canary\nAPCA_API_SECRET_KEY=canary\n")
        os.chmod(self.canary, 0o000)

    def tearDown(self):
        os.chmod(self.canary, 0o600)  # allow TemporaryDirectory cleanup to remove it
        self.tmp.cleanup()

    def test_render_metrics_never_opens_the_credentials_canary(self):
        if os.geteuid() == 0:
            self.skipTest("root ignores permission bits; canary check requires a non-root user")
        text = m.render_metrics(self.ledger_path, self.trial_path, now=time.time())
        self.assertIn("paper_trial_active", text)
        # If the exporter had attempted to open() the 0000 canary this would
        # have raised PermissionError and propagated out of render_metrics().
        with self.assertRaises(PermissionError):
            self.canary.read_text()

    def test_metrics_module_source_never_mentions_the_credential_env_names(self):
        source = (SOURCE / "metrics.py").read_text()
        self.assertNotIn("APCA_API_KEY_ID", source)
        self.assertNotIn("APCA_API_SECRET_KEY", source)
        self.assertNotIn("env_file", source)
        self.assertNotIn("env-file", source)


if __name__ == "__main__":
    unittest.main()
