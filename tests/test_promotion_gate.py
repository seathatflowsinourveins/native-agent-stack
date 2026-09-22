"""Fail-closed data-snapshot promotion gate: pure-Python parsing tests always
run; fixture tests that execute pandera/exchange_calendars validation run
through the gate's own isolated venv (never the ambient test interpreter) and
are skipped when that venv is not present on this host.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
GATE_FILE = ROOT / "blueprints/us-equities/data/promotion_gate.py"
FIXTURES = ROOT / "blueprints/us-equities/data/fixtures"

SPEC = importlib.util.spec_from_file_location("promotion_gate", GATE_FILE)
g = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = g
SPEC.loader.exec_module(g)


def _find_gate_python():
    """Locate the gate's isolated venv interpreter without embedding a literal
    personal path in this source file: an explicit override env var wins,
    then the documented ecosystem tool location resolved at runtime via
    Path.home()."""
    override = os.environ.get("PROMOTION_GATE_PYTHON")
    if override and Path(override).exists():
        return override
    candidate = Path.home() / ".local/share/codex-ecosystem/tools/promotion-gate-20260922/.venv/bin/python3"
    return str(candidate) if candidate.exists() else None


GATE_PYTHON = _find_gate_python()


class PurePythonParsing(unittest.TestCase):
    """No pandas/pandera import required for these; promotion_gate.py only
    imports those lazily inside functions that need them."""

    def test_snapshot_path_for_plain_file(self):
        self.assertEqual(g._snapshot_path("snapshot.parquet"), Path("snapshot.parquet"))

    def test_snapshot_path_for_duckdb_spec(self):
        self.assertEqual(g._snapshot_path("duckdb:///tmp/db.duckdb#bars"), Path("/tmp/db.duckdb"))

    def test_duckdb_spec_without_table_is_rejected(self):
        with self.assertRaises(ValueError):
            g._snapshot_path("duckdb:///tmp/db.duckdb")

    def test_duckdb_table_name_pattern_rejects_injection_attempt(self):
        self.assertIsNone(g.DUCKDB_TABLE_RE.match("bars; DROP TABLE bars"))
        self.assertIsNotNone(g.DUCKDB_TABLE_RE.match("bars"))
        self.assertIsNotNone(g.DUCKDB_TABLE_RE.match("schema.bars"))

    def test_write_result_is_atomic_and_readable(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "nested" / "gate-result.json"
            g.write_result({"status": "pass", "row_count": 1}, out)
            self.assertEqual(json.loads(out.read_text())["status"], "pass")
            self.assertFalse(out.with_suffix(out.suffix + ".tmp").exists())

    def test_check_names_are_fixed_and_cover_the_declared_rules(self):
        expected = {"symbol_nonempty", "valid_trading_session", "open_positive", "high_positive",
                    "low_positive", "close_positive", "volume_non_negative", "observed_at_not_future",
                    "high_ge_max_open_close", "low_le_min_open_close", "unique_symbol_session"}
        self.assertEqual(set(g.CHECK_NAMES), expected)

    def test_summarize_with_no_failures_marks_every_check_pass(self):
        checks = g._summarize(None, row_count=3)
        self.assertEqual(len(checks), len(g.CHECK_NAMES))
        self.assertTrue(all(c["status"] == "pass" for c in checks))


@unittest.skipUnless(GATE_PYTHON, "requires the gate's isolated venv "
                      "(uv venv + pandera==0.33.1 pandas exchange_calendars==4.13.2 pyarrow)")
class FixtureGateRuns(unittest.TestCase):
    """Runs the CLI in its own venv subprocess, as it runs in real use: the
    paper runtime never imports pandera/pandas, only reads this JSON output."""

    def _run(self, fixture_name):
        fixture = FIXTURES / fixture_name
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "gate-result.json"
            proc = subprocess.run([GATE_PYTHON, str(GATE_FILE), "--input", str(fixture), "--out", str(out)],
                                   capture_output=True, text=True, timeout=60)
            result = json.loads(out.read_text())
            return proc.returncode, result

    def test_good_fixture_passes_every_named_check(self):
        code, result = self._run("good.csv")
        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "pass")
        self.assertEqual({c["name"] for c in result["checks"]}, set(g.CHECK_NAMES))
        self.assertTrue(all(c["status"] == "pass" for c in result["checks"]), result["checks"])
        self.assertEqual(result["input_sha256"],
                          hashlib.sha256((FIXTURES / "good.csv").read_bytes()).hexdigest())
        self.assertEqual(result["row_count"], 4)
        for field in ("versions", "checked_at"):
            self.assertIn(field, result)
        for package in ("pandas", "pandera", "pyarrow", "exchange_calendars"):
            self.assertIn(package, result["versions"])

    def test_bad_fixture_fails_the_expected_named_checks(self):
        code, result = self._run("bad.csv")
        self.assertEqual(code, 1)
        self.assertEqual(result["status"], "fail")
        failing = {c["name"] for c in result["checks"] if c["status"] == "fail"}
        self.assertEqual(failing, {"valid_trading_session", "volume_non_negative", "observed_at_not_future",
                                    "high_ge_max_open_close", "unique_symbol_session"})
        passing = {c["name"] for c in result["checks"] if c["status"] == "pass"}
        self.assertEqual(passing, set(g.CHECK_NAMES) - failing)

    def test_missing_input_fails_closed_with_exception_class(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "gate-result.json"
            missing = Path(tmp) / "does-not-exist.parquet"
            proc = subprocess.run([GATE_PYTHON, str(GATE_FILE), "--input", str(missing), "--out", str(out)],
                                   capture_output=True, text=True, timeout=60)
            self.assertEqual(proc.returncode, 1)
            result = json.loads(out.read_text())
            self.assertEqual(result["status"], "fail")
            self.assertEqual(result.get("exception_class"), "FileNotFoundError")
            self.assertIsNone(result["input_sha256"])

    def test_unsupported_format_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            bogus = Path(tmp) / "bars.tsv"
            bogus.write_text("symbol\tsession\n")
            out = Path(tmp) / "gate-result.json"
            proc = subprocess.run([GATE_PYTHON, str(GATE_FILE), "--input", str(bogus), "--out", str(out)],
                                   capture_output=True, text=True, timeout=60)
            self.assertEqual(proc.returncode, 1)
            result = json.loads(out.read_text())
            self.assertEqual(result["status"], "fail")
            self.assertEqual(result.get("exception_class"), "ValueError")

    def test_null_price_cell_fails_closed_via_unmapped_failures(self):
        """Regression: pandera's own `not_nullable` failure identifier is not
        one of the 11 hardcoded CHECK_NAMES. Before the fix, `_summarize`
        silently dropped it and marked every named check "pass", so the gate
        emitted status "pass" (exit 0) for a snapshot with a null open cell.
        It must now fail closed via a synthetic `unmapped_failures` check."""
        code, result = self._run("null-price-cell.csv")
        self.assertEqual(code, 1)
        self.assertEqual(result["status"], "fail")
        unmapped = next((c for c in result["checks"] if c["name"] == "unmapped_failures"), None)
        self.assertIsNotNone(result["checks"])
        self.assertIsNotNone(unmapped, result["checks"])
        self.assertEqual(unmapped["status"], "fail")
        self.assertIn("not_nullable", unmapped["detail"])
        # Every hardcoded CHECK_NAMES entry still reports "pass": the
        # unmapped identifier must not be silently absorbed into one of them.
        named = {c["name"]: c["status"] for c in result["checks"] if c["name"] in g.CHECK_NAMES}
        self.assertTrue(all(status == "pass" for status in named.values()), named)

    def test_invalid_calendar_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "gate-result.json"
            proc = subprocess.run([GATE_PYTHON, str(GATE_FILE), "--input", str(FIXTURES / "good.csv"),
                                    "--out", str(out), "--calendar", "NOT_A_REAL_CALENDAR"],
                                   capture_output=True, text=True, timeout=60)
            self.assertEqual(proc.returncode, 1)
            result = json.loads(out.read_text())
            self.assertEqual(result["status"], "fail")


if __name__ == "__main__":
    unittest.main()
