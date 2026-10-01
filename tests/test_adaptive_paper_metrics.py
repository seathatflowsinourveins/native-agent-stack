"""Read-only exporter tests against a real, schema-true ledger fixture.

The fixture ledger/trial.json are produced with safety.Ledger's own
serialisation (never a hand-built row), so schema drift in safety.py would
break this test rather than silently going unnoticed. No network calls other
than loopback HTTP against the exporter under test; no broker or credentials
are touched.
"""
from __future__ import annotations

import io
import json
import os
import re
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
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
        self.assertEqual(samples[("paper_ledger_readable", ())], "0")
        self.assertNotIn(("paper_order_state_divergence_total", ()), samples)
        self.assertIn("ledger file not found", text)
        self.assertIn("paper_reconciliation_last_success_timestamp_seconds is not exported", text)
        self.assertIn("paper_request_budget_wait_exceeded_total is not exported", text)

    def test_unreadable_ledger_file_reports_readable_zero_but_keeps_the_always_on_gauges(self):
        # Simulates the review finding: a wrong --ledger path or a permissions problem must not
        # silently drop paper_order_state_divergence_total/paper_ledger_frozen/paper_request_budget_*
        # with nothing to alert on. paper_ledger_readable is the guard EquitiesLedgerUnreadable uses.
        if os.geteuid() == 0:
            self.skipTest("root ignores permission bits; this scenario requires a non-root user")
        self.write_trial(trial_id="fixture", phase="starting", started_at=self.now)
        self.ledger_path.write_bytes(b"not a real sqlite file")
        os.chmod(self.ledger_path, 0o000)
        try:
            text = m.render_metrics(self.ledger_path, self.trial_path, now=self.now)
        finally:
            os.chmod(self.ledger_path, 0o600)  # allow tearDown's TemporaryDirectory cleanup
        samples = parse(text)
        self.assertEqual(samples[("paper_trial_active", ())], "1")  # exporter itself is fine
        self.assertEqual(samples[("paper_ledger_readable", ())], "0")
        self.assertNotIn(("paper_order_state_divergence_total", ()), samples)
        self.assertNotIn(("paper_ledger_frozen", (("reason", "external_order_detected"),)), samples)
        self.assertIn("ledger open failed", text)

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
        self.assertEqual(samples[("paper_ledger_readable", ())], "1")
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

    def test_recovered_flat_run_reports_finished_phase_but_needs_attention_status(self):
        # Mirrors runner.py:463-465: an exception/failure path sets status="needs_attention", then
        # a successful post-failure recovery overwrites outcome["flat"] = True, so metadata["phase"]
        # ends up "finished" while metadata["status"] stays "needs_attention". paper_needs_attention
        # alone (phase-derived) misses this; paper_reconciliation_status{result="needs_attention"}
        # is what EquitiesReconciliationFailed's added clause keys off.
        ledger = Ledger(self.ledger_path, RiskLimits())
        ledger.start_trial(self.now)
        ledger.close()
        self.write_trial(trial_id="fixture", phase="finished", status="needs_attention",
                         started_at=self.now)

        text = m.render_metrics(self.ledger_path, self.trial_path, now=self.now)
        samples = parse(text)
        self.assertEqual(samples[("paper_trial_active", ())], "0")
        self.assertEqual(samples[("paper_needs_attention", ())], "0")
        self.assertEqual(samples[("paper_reconciliation_status", (("result", "needs_attention"),))], "1")

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
        self.assertEqual(samples[("paper_ledger_readable", ())], "1")
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


class PathConfinementTests(unittest.TestCase):
    """Regression (finding 4): `--trial-json` (and any other path argument)
    used to accept arbitrary paths, and `_read_trial_json` read them without
    restriction. Every readable path must now be confined to the resolved
    ledger directory (the resolved parent of `--ledger`); a path outside it,
    or a symlink that escapes it, must be refused before any read of its
    contents."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.ledger_dir = self.root / "ledger-dir"
        self.ledger_dir.mkdir()
        self.ledger_path = self.ledger_dir / "ledger.sqlite3"
        ledger = Ledger(self.ledger_path, RiskLimits())
        ledger.start_trial(time.time())
        ledger.close()
        self.outside_dir = self.root / "outside"
        self.outside_dir.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_trial_json_outside_the_ledger_directory_is_refused_with_no_read(self):
        canary = self.outside_dir / "trial.json"
        canary.write_text(json.dumps({"phase": "starting"}))
        with patch.object(Path, "read_text",
                           side_effect=AssertionError("must not read a trial.json outside the ledger dir")):
            text = m.render_metrics(self.ledger_path, canary, now=time.time())
        samples = parse(text)
        # Refused: treated exactly like a missing trial.json, never "1" even
        # though the canary's own phase is "starting".
        self.assertEqual(samples[("paper_trial_active", ())], "0")

    def test_trial_json_symlinked_from_inside_the_ledger_dir_to_outside_is_refused(self):
        canary = self.outside_dir / "trial.json"
        canary.write_text(json.dumps({"phase": "starting"}))
        link = self.ledger_dir / "trial.json"
        os.symlink(canary, link)
        with patch.object(Path, "read_text",
                           side_effect=AssertionError("must not read a symlink escaping the ledger dir")):
            text = m.render_metrics(self.ledger_path, link, now=time.time())
        samples = parse(text)
        self.assertEqual(samples[("paper_trial_active", ())], "0")

    def test_ledger_path_symlinked_from_inside_the_ledger_dir_to_outside_is_refused_with_no_open(self):
        outside_ledger = self.outside_dir / "ledger.sqlite3"
        ledger = Ledger(outside_ledger, RiskLimits())
        ledger.start_trial(time.time())
        ledger.close()
        link = self.ledger_dir / "linked-ledger.sqlite3"
        os.symlink(outside_ledger, link)
        trial_path = self.ledger_dir / "trial.json"
        with patch.object(sqlite3, "connect",
                           side_effect=AssertionError("must not open a ledger path escaping the ledger dir")):
            text = m.render_metrics(link, trial_path, now=time.time())
        samples = parse(text)
        self.assertEqual(samples[("paper_ledger_readable", ())], "0")
        self.assertIn("ledger file not found or outside", text)

    def test_resolve_confined_rejects_a_path_outside_the_boundary(self):
        boundary = self.ledger_dir.resolve()
        outside_file = self.outside_dir / "f.txt"
        outside_file.write_text("x")
        self.assertIsNone(m._resolve_confined(outside_file, boundary))
        self.assertIsNone(m._resolve_confined(self.outside_dir / "does-not-exist", boundary))

    def test_resolve_confined_accepts_a_path_inside_the_boundary(self):
        boundary = self.ledger_dir.resolve()
        self.assertEqual(m._resolve_confined(self.ledger_path, boundary), self.ledger_path.resolve())


class SqliteReadOnlyUriTests(unittest.TestCase):
    """Regression (finding 5): the read-only SQLite URI was built by naive
    string concatenation (``"file:" + str(path) + "?mode=ro"``), so a path
    containing ``?``/``#`` could override ``mode=ro`` -- a probe path of
    ``/synthetic/probe?mode=memory&ignored=`` yielded a writable connection.
    The URI must now be built from `urllib.parse.quote`, and any path
    containing a reserved character refused outright."""

    def test_probe_path_with_reserved_characters_is_refused(self):
        probe = Path("/synthetic/probe?mode=memory&ignored=")
        with self.assertRaises(ValueError):
            m._sqlite_ro_uri(probe)

    def test_probe_path_with_hash_is_also_refused(self):
        probe = Path("/synthetic/probe#fragment")
        with self.assertRaises(ValueError):
            m._sqlite_ro_uri(probe)

    def test_quoted_uri_is_percent_encoded_and_read_only(self):
        uri = m._sqlite_ro_uri(Path("/tmp/plain ledger.sqlite3"))
        self.assertTrue(uri.startswith("file:"))
        self.assertTrue(uri.endswith("?mode=ro"))
        self.assertIn("plain%20ledger.sqlite3", uri)

    def test_uri_does_not_assert_immutable(self):
        """Regression (codexfix pr4-codexfix): ``immutable=1`` was removed --
        it asserts the file never changes for the connection's lifetime, which
        is false for the live WAL ledger a running trial keeps open and
        writes to (see test_render_metrics_sees_live_wal_writes_while_ledger_is_open)."""
        uri = m._sqlite_ro_uri(Path("/tmp/plain ledger.sqlite3"))
        self.assertNotIn("immutable", uri)

    def test_open_ledger_readonly_connection_rejects_a_write_attempt(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger_path = Path(tmp) / "ledger.sqlite3"
            ledger = Ledger(ledger_path, RiskLimits())
            ledger.start_trial(time.time())
            ledger.close()
            conn = m._open_ledger_readonly(ledger_path.resolve())
            try:
                with self.assertRaises(sqlite3.OperationalError):
                    conn.execute("CREATE TABLE canary (x INTEGER)")
            finally:
                conn.close()

    def test_render_metrics_sees_live_wal_writes_while_ledger_is_open(self):
        """Regression (codexfix pr4-codexfix major finding): the ledger the
        exporter reads is a live WAL database that ``safety.Ledger`` holds
        open and writes to for the whole duration of a trial. Opening the
        read-only connection with ``immutable=1`` asserted the file could not
        change, and against this actively-written WAL file that produced an
        outright ``sqlite3.OperationalError: no such table: meta`` on every
        scrape taken while a trial was running (observed empirically: the
        immutable connection never sees the WAL-resident schema at all, not
        even a stale-but-valid snapshot). This keeps a real ``safety.Ledger``
        connection open (never closed, never checkpointed) for the whole
        test, freezes it to produce a fresh WAL-only write, and asserts a
        concurrent scrape via ``render_metrics`` both succeeds and observes
        that freshly committed state -- proving the exporter no longer goes
        stale (or errors) against a live trial."""
        with tempfile.TemporaryDirectory() as tmp:
            ledger_path = Path(tmp) / "ledger.sqlite3"
            trial_path = Path(tmp) / "trial.json"
            ledger = Ledger(ledger_path, RiskLimits())
            self.addCleanup(ledger.close)
            ledger.start_trial(time.time())
            ledger.freeze("live_wal_probe")

            text = m.render_metrics(ledger_path, trial_path, now=time.time())

            samples = parse(text)
            self.assertEqual(samples[("paper_ledger_readable", ())], "1")
            self.assertEqual(
                samples[("paper_ledger_frozen", (("reason", "live_wal_probe"),))], "1"
            )


class FileSdRegistrationTests(unittest.TestCase):
    """``metrics.py --file-sd`` end to end, with real exporter processes and a real file_sd list.

    The backend profile scrapes job ``adaptive-paper`` only at registered targets, and
    ``EquitiesPaperMetricsMissing`` fires for a registered target without ``paper_trial_active``. So an exporter must
    register itself once it serves, and remove itself only on a clean stop of a finished trial: a crashed, killed or
    unfinished trial has to stay registered for the alert to fire."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.ledger_path = self.root / "ledger.sqlite3"
        self.trial_path = self.root / "trial.json"
        ledger = Ledger(self.ledger_path, RiskLimits())
        ledger.start_trial(time.time())
        ledger.close()
        self.targets = self.root / "config" / "adaptive-paper-targets.json"
        self.targets.parent.mkdir()
        self.targets.write_text("[]\n")  # as observability/backends/configure.py ships it
        self.processes = []

    def tearDown(self):
        for process in self.processes:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=10)
            process.stderr.close()
        self.tmp.cleanup()

    def write_phase(self, phase, **fields):
        self.trial_path.write_text(json.dumps({"trial_id": "fixture", "phase": phase, **fields}))

    def listed(self):
        if not self.targets.exists():
            return []
        return [target for group in json.loads(self.targets.read_text()) for target in group["targets"]]

    def run_metrics(self, *argv):
        return subprocess.run([sys.executable, str(SOURCE / "metrics.py"), *argv],
                              capture_output=True, text=True, timeout=60)

    def start(self):
        before = set(self.listed())
        process = subprocess.Popen([sys.executable, str(SOURCE / "metrics.py"), "--ledger", str(self.ledger_path),
                                    "--port", "0", "--file-sd", str(self.targets)], stderr=subprocess.PIPE, text=True)
        self.processes.append(process)
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            added = set(self.listed()) - before
            if added:
                return process, added.pop()
            if process.poll() is not None:
                self.fail(f"exporter exited {process.returncode} before registering: {process.stderr.read()}")
            time.sleep(0.05)
        self.fail("exporter never registered its target")

    def stop(self, process, signum=signal.SIGTERM):
        process.send_signal(signum)
        return process.wait(timeout=30)

    def test_a_running_exporter_is_registered_at_the_loopback_address_it_serves(self):
        self.write_phase("starting")
        _, target = self.start()
        self.assertTrue(target.startswith("127.0.0.1:"), target)
        with urllib.request.urlopen(f"http://{target}/metrics", timeout=5) as response:
            samples = parse(response.read().decode("utf-8"))
        self.assertEqual(samples[("paper_trial_active", ())], "1")

    def test_a_clean_stop_of_a_finished_trial_deregisters_without_leaving_a_temporary_file(self):
        for status in ("passed", "completed_no_signals"):  # the runner's passing statuses for phase finished
            with self.subTest(status=status):
                self.write_phase("starting")
                process, _ = self.start()
                self.write_phase("finished", status=status)
                self.assertEqual(self.stop(process), 0)
                self.assertEqual(json.loads(self.targets.read_text()), [])
                self.assertEqual(sorted(path.name for path in self.targets.parent.iterdir()),
                                 ["adaptive-paper-targets.json", "adaptive-paper-targets.json.lock"])

    def test_a_clean_stop_with_no_trial_json_deregisters(self):
        process, target = self.start()
        self.assertEqual(self.stop(process), 0)
        self.assertNotIn(target, self.listed())

    def test_a_clean_stop_keeps_a_replacement_registered_after_the_listener_closes(self):
        self.write_phase("finished", status="passed")
        make_server = m.make_server
        server = make_server(self.ledger_path, self.trial_path, port=0)
        close = server.server_close
        self.addCleanup(close)
        port = server.server_address[1]
        target = f"127.0.0.1:{port}"
        replacements = []

        def close_and_replace():
            close()
            replacement = make_server(self.ledger_path, self.trial_path, port=port)
            self.addCleanup(replacement.server_close)
            replacements.append(replacement)
            m.update_file_sd(self.targets, target, registered=True)

        with patch.object(m, "make_server", return_value=server), \
                patch.object(m.signal, "signal"), \
                patch.object(server, "serve_forever", side_effect=m._CleanStop), \
                patch.object(server, "server_close", side_effect=close_and_replace):
            self.assertEqual(m.main(["--ledger", str(self.ledger_path), "--port", str(port),
                                     "--file-sd", str(self.targets)]), 0)

        self.assertEqual(len(replacements), 1)
        self.assertGreaterEqual(replacements[0].fileno(), 0)
        self.assertIn(target, self.listed(), "shutdown removed the replacement exporter's registration")

    def test_a_clean_stop_of_an_unfinished_trial_stays_registered(self):
        for phase, status in (("starting", None), ("needs_attention", "needs_attention"),
                              ("held_overnight", "held_overnight"), ("finished", "needs_attention"),
                              ("finished", "failed"), ("finished", None), ("finished", "not_ready"),
                              ("finished", "a-status-this-exporter-does-not-know")):
            with self.subTest(phase=phase, status=status):
                self.write_phase(phase, status=status)
                process, target = self.start()
                self.assertEqual(self.stop(process), 0)
                self.assertIn(target, self.listed())

    def test_a_clean_stop_with_an_unreadable_trial_json_stays_registered(self):
        self.trial_path.write_text("{not json")
        process, target = self.start()
        self.assertEqual(self.stop(process), 0)
        self.assertIn(target, self.listed())

    def test_a_killed_exporter_stays_registered_even_for_a_finished_trial(self):
        self.write_phase("finished", status="passed")
        process, target = self.start()
        self.assertEqual(self.stop(process, signal.SIGKILL), -signal.SIGKILL)
        self.assertIn(target, self.listed())

    def test_deregister_removes_the_target_a_stopped_exporter_left(self):
        self.write_phase("needs_attention")
        process, target = self.start()
        self.stop(process)
        result = self.run_metrics("--deregister", "--port", target.rsplit(":", 1)[1], "--file-sd", str(self.targets))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(target, self.listed())

    def test_other_groups_and_a_concurrent_exporter_are_kept(self):
        # Prometheus v3.15.0 accepts UTF-8 names, empty strings and JSON null label values.
        other = {"targets": ["127.0.0.1:9"],
                 "labels": {"note": "another writer", "nullable": None, "étiquette": "café", "9 owner": ""}}
        self.targets.write_text(json.dumps([other]))
        self.write_phase("finished", status="passed")
        first, _ = self.start()
        second, second_target = self.start()
        self.assertEqual(self.stop(first), 0)
        self.assertEqual(json.loads(self.targets.read_text()),
                         [other, {"targets": [second_target], "labels": {}}])
        self.assertEqual(self.stop(second), 0)
        self.assertEqual(json.loads(self.targets.read_text()), [other])

    def test_a_missing_list_is_created_by_the_first_registration(self):
        self.targets.unlink()
        self.write_phase("starting")
        _, target = self.start()
        self.assertEqual(json.loads(self.targets.read_text()), [{"targets": [target], "labels": {}}])

    def test_a_list_that_is_not_a_file_sd_target_list_refuses_to_start_and_is_left_alone(self):
        for content in ('{"targets": ["127.0.0.1:1"]}', "[not json", '[{"targets": "127.0.0.1:1"}]',
                        '[{"targets": [], "extra": 1}]', '[{"targets": [1]}]'):
            with self.subTest(content=content):
                self.targets.write_text(content)
                result = self.run_metrics("--ledger", str(self.ledger_path), "--port", "0",
                                          "--file-sd", str(self.targets))
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("refused", result.stderr)
                self.assertEqual(self.targets.read_text(), content)

    def test_malformed_file_sd_labels_refuse_startup_and_leave_the_list_unchanged(self):
        for labels in ({"owner": {}}, {"owner": []}, {"owner": 1}, {"owner": True}, {"": "owner"}):
            with self.subTest(labels=labels):
                content = json.dumps([{"targets": ["127.0.0.1:9"], "labels": labels}])
                self.targets.write_text(content)
                with patch.object(m.signal, "signal"), \
                        patch.object(m.ThreadingHTTPServer, "serve_forever") as serve, \
                        patch.object(m.sys, "stderr", new_callable=io.StringIO) as stderr:
                    result = m.main(["--ledger", str(self.ledger_path), "--port", "0",
                                     "--file-sd", str(self.targets)])
                self.assertEqual(result, 2, "malformed file_sd labels must refuse startup")
                serve.assert_not_called()
                self.assertIn("refused", stderr.getvalue())
                self.assertEqual(self.targets.read_text(), content)

    def test_a_list_in_a_missing_directory_refuses_to_start(self):
        result = self.run_metrics("--ledger", str(self.ledger_path), "--port", "0",
                                  "--file-sd", str(self.root / "absent" / "adaptive-paper-targets.json"))
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("refused", result.stderr)

    def test_deregister_needs_file_sd_and_serving_needs_a_ledger(self):
        for argv in (["--deregister"], ["--port", "0"]):
            with self.subTest(argv=argv):
                self.assertEqual(self.run_metrics(*argv).returncode, 2)

    def test_serving_without_file_sd_is_refused_unless_explicitly_unscraped(self):
        # Fail closed: an unregistered exporter is never scraped, so no alert would cover it.
        result = self.run_metrics("--ledger", str(self.ledger_path), "--port", "0")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("--file-sd is required", result.stderr)
        both = self.run_metrics("--ledger", str(self.ledger_path), "--port", "0",
                                "--file-sd", str(self.targets), "--no-file-sd")
        self.assertEqual(both.returncode, 2, both.stderr)
        self.assertEqual(self.targets.read_text(), "[]\n")

    def test_no_file_sd_serves_without_touching_any_target_list(self):
        self.write_phase("starting")
        process = subprocess.Popen([sys.executable, str(SOURCE / "metrics.py"), "--ledger", str(self.ledger_path),
                                    "--port", "0", "--no-file-sd"], stderr=subprocess.PIPE, text=True)
        self.processes.append(process)
        line = process.stderr.readline()
        match = re.search(r"http://(127\.0\.0\.1:\d+)/metrics", line)
        self.assertIsNotNone(match, line)
        with urllib.request.urlopen(f"http://{match.group(1)}/metrics", timeout=5) as response:
            self.assertEqual(parse(response.read().decode("utf-8"))[("paper_trial_active", ())], "1")
        self.assertEqual(self.stop(process), 0)
        self.assertEqual(self.targets.read_text(), "[]\n")
        self.assertEqual(sorted(path.name for path in self.targets.parent.iterdir()), ["adaptive-paper-targets.json"])


if __name__ == "__main__":
    unittest.main()
