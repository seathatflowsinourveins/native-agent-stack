"""Fail-closed data-snapshot promotion gate: pure-Python parsing tests always
run; fixture tests that execute pandera/exchange_calendars validation run
through the gate's own isolated venv (never the ambient test interpreter) and
are skipped when that venv is not present on this host. When
REQUIRE_PROMOTION_GATE_VENV=1 (set by the CI validate workflow after it
provisions the venv), a missing venv fails this module at import time instead
of silently skipping, so a broken provisioning step cannot pass CI as a
silent skip.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
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

if os.environ.get("REQUIRE_PROMOTION_GATE_VENV") == "1" and not GATE_PYTHON:
    # The CI validate workflow sets this after it provisions the gate venv
    # from blueprints/us-equities/data/requirements.lock; a missing venv here
    # means that provisioning step did not run or did not produce a working
    # interpreter. Fail loudly at import time instead of letting
    # FixtureGateRuns silently skip, so CI cannot go green without actually
    # classifying the fixtures. Local developer runs are unaffected: this
    # variable is unset by default and GATE_PYTHON absence still just skips.
    raise RuntimeError(
        "REQUIRE_PROMOTION_GATE_VENV=1 but no promotion-gate venv was found "
        "(checked PROMOTION_GATE_PYTHON and the documented ecosystem tool "
        "location); the fixture gate tests cannot run.")


class ImportTimeVenvGuard(unittest.TestCase):
    """Regression: REQUIRE_PROMOTION_GATE_VENV must fail this module's import
    when no gate venv is found (so a broken CI provisioning step cannot pass
    as a silent skip), and must never fail the import when unset, even if the
    venv is absent (so local developer runs without the venv still just skip
    FixtureGateRuns). Runs this file's own import in a subprocess with a
    fake HOME so Path.home()'s documented ecosystem-tool candidate cannot
    resolve to a real venv on this host."""

    def _reimport(self, env_overrides):
        env = dict(os.environ)
        env.pop("PROMOTION_GATE_PYTHON", None)
        env.pop("REQUIRE_PROMOTION_GATE_VENV", None)
        env.update(env_overrides)
        return subprocess.run(
            [sys.executable, "-c", "import runpy; runpy.run_path(%r)" % str(Path(__file__).resolve())],
            env=env, capture_output=True, text=True, timeout=30)

    def test_require_venv_with_missing_venv_fails_at_import(self):
        with tempfile.TemporaryDirectory() as empty_home:
            proc = self._reimport({"REQUIRE_PROMOTION_GATE_VENV": "1", "HOME": empty_home})
        self.assertNotEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("REQUIRE_PROMOTION_GATE_VENV=1 but no promotion-gate venv was found", proc.stderr)

    def test_require_venv_unset_with_missing_venv_still_imports(self):
        with tempfile.TemporaryDirectory() as empty_home:
            proc = self._reimport({"HOME": empty_home})
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_require_venv_unset_with_missing_venv_skips_fixture_tests(self):
        """End-to-end companion to the two import checks above: with the
        guard variable unset and no venv discoverable, actually running
        FixtureGateRuns must skip every test in it rather than error."""
        with tempfile.TemporaryDirectory() as empty_home:
            env = dict(os.environ, HOME=empty_home)
            env.pop("PROMOTION_GATE_PYTHON", None)
            env.pop("REQUIRE_PROMOTION_GATE_VENV", None)
            proc = subprocess.run(
                [sys.executable, "-m", "unittest", "-v", "tests.test_promotion_gate.FixtureGateRuns"],
                cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("skipped", proc.stderr)
        self.assertNotIn("ERROR", proc.stderr)


class WorkflowProvisioningContract(unittest.TestCase):
    """Regression: nothing else asserts that validate.yml keeps the venv
    provisioning step, its hash-locked/require-hashes install and the
    REQUIRE_PROMOTION_GATE_VENV=1 export, or that it still runs before the
    step that runs this test module. Without this, deleting the step (or
    just the env export line) would silently bring back skip-as-pass."""

    VALIDATE_YML = ROOT / ".github/workflows/validate.yml"

    def _step_bodies(self):
        text = self.VALIDATE_YML.read_text()
        names = re.findall(r"^ {6}- name: (.+)$", text, re.MULTILINE)
        bodies = re.split(r"^ {6}- name: .+$", text, flags=re.MULTILINE)[1:]
        self.assertEqual(len(names), len(bodies))
        return list(zip(names, bodies))

    def test_provisioning_step_present_before_the_unittest_step(self):
        steps = self._step_bodies()
        step_names = [name for name, _ in steps]
        self.assertIn("Provision the promotion gate's isolated venv", step_names)
        self.assertIn("Test validation failure modes", step_names)
        self.assertLess(step_names.index("Provision the promotion gate's isolated venv"),
                         step_names.index("Test validation failure modes"),
                         "provisioning must run before python3 -m unittest")

    def test_provisioning_step_sets_require_hashes_and_the_guard_env_var(self):
        steps = dict(self._step_bodies())
        body = steps["Provision the promotion gate's isolated venv"]
        self.assertIn("--require-hashes", body)
        self.assertIn("blueprints/us-equities/data/requirements.lock", body)
        self.assertIn('echo "REQUIRE_PROMOTION_GATE_VENV=1" >> "$GITHUB_ENV"', body)

    def test_unittest_step_runs_the_full_suite(self):
        steps = dict(self._step_bodies())
        self.assertIn("python3 -m unittest", steps["Test validation failure modes"])


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
        expected = {"rows_present", "symbol_nonempty", "valid_trading_session", "open_positive",
                    "high_positive", "low_positive", "close_positive", "volume_integral_non_negative",
                    "observed_at_not_future", "high_ge_max_open_close", "low_le_min_open_close",
                    "unique_symbol_session"}
        self.assertEqual(set(g.CHECK_NAMES), expected)

    def test_summarize_with_no_failures_marks_every_check_pass(self):
        checks = g._summarize(None, row_count=3)
        self.assertEqual(len(checks), len(g.CHECK_NAMES))
        self.assertTrue(all(c["status"] == "pass" for c in checks))

    def test_summarize_with_zero_row_count_fails_rows_present_only(self):
        """Regression (finding 1): before the fix, a 0-row snapshot with no
        pandera failure_cases marked every check "pass" (status="pass",
        row_count=0). rows_present must now fail closed on its own,
        independent of every other check."""
        checks = g._summarize(None, row_count=0)
        by_name = {c["name"]: c["status"] for c in checks}
        self.assertEqual(by_name["rows_present"], "fail")
        self.assertTrue(all(status == "pass" for name, status in by_name.items() if name != "rows_present"))


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

    def _run_snippet(self, body):
        """Runs `body` in the gate's own venv with `g` already bound to the
        freshly loaded promotion_gate module, for unit-testing internal
        (pandas-dependent) helpers without requiring pandas in the ambient
        test interpreter."""
        script = (f"import importlib.util as u\n"
                   f"spec = u.spec_from_file_location('promotion_gate', {str(GATE_FILE)!r})\n"
                   "g = u.module_from_spec(spec); spec.loader.exec_module(g)\n" + body)
        with tempfile.TemporaryDirectory() as tmp:
            script_path = Path(tmp) / "snippet.py"
            script_path.write_text(script)
            return subprocess.run([GATE_PYTHON, str(script_path)], capture_output=True, text=True, timeout=30)

    def test_raw_volume_failure_indices_flags_fractional_negative_before_coercion(self):
        """Regression (finding 2): a raw volume of -0.5 must be flagged
        directly, not silently truncated to 0 by int64 coercion first."""
        proc = self._run_snippet(
            "import json, pandas as pd\n"
            "frame = pd.DataFrame({'volume': [-0.5, 100, float('nan'), float('inf'), 3.5, -4]})\n"
            "print(json.dumps(g._raw_volume_failure_indices(frame)))\n")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout), [0, 2, 3, 4, 5])

    def test_prepare_never_raises_on_invalid_raw_volume(self):
        """`_prepare()`'s coercion must not itself raise on a fractional/NaN/
        negative raw volume; pass/fail for volume is decided separately by
        `_raw_volume_failure_indices` on the pre-coercion column."""
        proc = self._run_snippet(
            "import json, pandas as pd\n"
            "raw = pd.DataFrame({'symbol': ['SPY'], 'session': ['2026-09-14'], 'open': [1.0],\n"
            "                     'high': [1.0], 'low': [1.0], 'close': [1.0], 'volume': [-0.5],\n"
            "                     'observed_at': ['2026-09-14T20:00:00Z']})\n"
            "frame = g._prepare(raw)\n"
            "print(json.dumps(int(frame['volume'].iloc[0])))\n")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout), 0)

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
        self.assertEqual(failing, {"valid_trading_session", "volume_integral_non_negative",
                                    "observed_at_not_future", "high_ge_max_open_close",
                                    "unique_symbol_session"})
        passing = {c["name"] for c in result["checks"] if c["status"] == "pass"}
        self.assertEqual(passing, set(g.CHECK_NAMES) - failing)

    def test_empty_snapshot_fails_closed_via_rows_present(self):
        """Regression (finding 1): a 0-row snapshot with every required
        column present used to return status="pass", row_count=0. It must
        now fail closed on a named `rows_present` check, with every other
        check still reporting "pass" (nothing to violate over 0 rows)."""
        code, result = self._run("empty-snapshot.csv")
        self.assertEqual(code, 1)
        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["row_count"], 0)
        by_name = {c["name"]: c["status"] for c in result["checks"]}
        self.assertEqual(by_name["rows_present"], "fail")
        self.assertTrue(all(status == "pass" for name, status in by_name.items() if name != "rows_present"),
                         by_name)

    def test_fractional_negative_volume_fails_closed_via_volume_integral_non_negative(self):
        """Regression (finding 2): before the fix, a raw volume of -0.5 was
        coerced to 0 by `.astype('int64')` BEFORE the (then-named)
        `volume_non_negative` check ran, so the row passed. The raw value
        must now be validated before any coercion."""
        code, result = self._run("fractional-negative-volume.csv")
        self.assertEqual(code, 1)
        self.assertEqual(result["status"], "fail")
        by_name = {c["name"]: c["status"] for c in result["checks"]}
        self.assertEqual(by_name["volume_integral_non_negative"], "fail")
        volume_check = next(c for c in result["checks"] if c["name"] == "volume_integral_non_negative")
        self.assertIn("example row indices [0]", volume_check["detail"])
        self.assertTrue(all(status == "pass" for name, status in by_name.items()
                             if name != "volume_integral_non_negative"), by_name)

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


def _gate_has_duckdb():
    if not GATE_PYTHON:
        return False
    proc = subprocess.run([GATE_PYTHON, "-c", "import duckdb"], capture_output=True, text=True, timeout=60)
    return proc.returncode == 0


GATE_HAS_DUCKDB = _gate_has_duckdb()


@unittest.skipUnless(GATE_PYTHON, "requires the gate's isolated venv")
class DuckdbInputRuns(unittest.TestCase):
    """The duckdb://<db>#<table> input path, run in the gate venv synced from
    requirements.lock (which pins duckdb). Each CSV fixture is copied into a
    DuckDB table by DuckDB's own read_csv (auto-typed columns) and must give
    the same status, row_count and per-check statuses as its retained CSV
    result. A venv provisioned before duckdb entered the lock skips locally;
    under REQUIRE_PROMOTION_GATE_VENV=1 (CI) a missing duckdb fails."""

    def setUp(self):
        if not GATE_HAS_DUCKDB:
            if os.environ.get("REQUIRE_PROMOTION_GATE_VENV") == "1":
                self.fail("gate venv cannot import duckdb although requirements.lock pins it")
            self.skipTest("gate venv predates the duckdb pin in requirements.lock")

    def _build(self, db, body, *args):
        """Runs `body` in the gate venv with `con` open on `db` (read-write)
        and `argv` bound to `args`; closes the connection afterwards unless
        `body` exits the process first."""
        script = ("import duckdb, os, sys\n"
                  "con = duckdb.connect(sys.argv[1])\n"
                  "argv = sys.argv[2:]\n" + body + "\ncon.close()\n")
        build = subprocess.run([GATE_PYTHON, "-c", script, str(db), *map(str, args)],
                               capture_output=True, text=True, timeout=60)
        self.assertEqual(build.returncode, 0, build.stderr)

    def _gate(self, db, relation, tmp):
        out = Path(tmp) / "gate-result.json"
        proc = subprocess.run([GATE_PYTHON, str(GATE_FILE), "--input", f"duckdb://{db}#{relation}",
                                "--out", str(out)], capture_output=True, text=True, timeout=60)
        result = json.loads(out.read_text())
        self.assertEqual(result["input_sha256"], hashlib.sha256(db.read_bytes()).hexdigest())
        return proc.returncode, result

    def _run_duckdb(self, fixture_name, column_types=None):
        """Copies a CSV fixture into a DuckDB base table with DuckDB's own
        read_csv; `column_types` overrides auto-detection for named columns."""
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "snapshot.duckdb"
            self._build(db, "import json\n"
                            "types = json.loads(argv[1])\n"
                            "option = ', types={' + ', '.join(f\"'{k}': '{v}'\" for k, v in types.items()) + '}' if types else ''\n"
                            "con.execute('CREATE TABLE snapshot AS SELECT * FROM read_csv(?' + option + ')', [argv[0]])",
                        FIXTURES / fixture_name, json.dumps(column_types or {}))
            return self._gate(db, "snapshot", tmp)

    def test_duckdb_inputs_match_the_retained_csv_results(self):
        # lossy-volume-conversion stores `volume` as VARCHAR: DuckDB's
        # auto-detection would type it DOUBLE and lose -1e-400 and
        # 9007199254740992.5 at write time, before the gate runs (a lossy
        # snapshot writer, like a Parquet float column). Stored exactly, it
        # must fail the gate exactly as its CSV does, including the detail.
        cases = (("good", None), ("bad", None), ("null-price-cell", None), ("empty-snapshot", None),
                 ("fractional-negative-volume", None), ("lossy-volume-conversion", {"volume": "VARCHAR"}))
        for stem, column_types in cases:
            with self.subTest(fixture=stem):
                code, result = self._run_duckdb(f"{stem}.csv", column_types)
                expected = json.loads((FIXTURES / f"{stem}-gate-result.json").read_text())
                self.assertEqual(code, 0 if expected["status"] == "pass" else 1)
                self.assertEqual(result["status"], expected["status"])
                self.assertEqual(result["row_count"], expected["row_count"])
                self.assertEqual({c["name"]: c["status"] for c in result["checks"]},
                                  {c["name"]: c["status"] for c in expected["checks"]})
                if stem == "lossy-volume-conversion":
                    self.assertEqual(result["checks"], expected["checks"])

    def test_duckdb_decimal_volume_keeps_exact_precision(self):
        """Regression (Codex, PR #132): fetch_df() turned a DECIMAL volume
        into float64, rounding 9007199254740992.5 to 9007199254740992.0, so
        a non-integral volume passed. It must fail, and only that row."""
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "snapshot.duckdb"
            self._build(db, "con.execute(\"CREATE TABLE snapshot AS SELECT * REPLACE "
                            "(CAST(volume AS DECIMAL(38, 1)) AS volume) FROM read_csv(?)\", [argv[0]])\n"
                            "con.execute(\"UPDATE snapshot SET volume = 9007199254740992.5 "
                            "WHERE symbol = 'QQQ' AND session = DATE '2026-09-15'\")",
                        FIXTURES / "good.csv")
            code, result = self._gate(db, "snapshot", tmp)
        self.assertEqual(code, 1)
        self.assertEqual(result["status"], "fail")
        failing = {c["name"]: c["detail"] for c in result["checks"] if c["status"] == "fail"}
        self.assertEqual(failing, {"volume_integral_non_negative": "1 of 4 rows failed; example row indices [3]"},
                         result["checks"])

    def test_duckdb_decimal_numeric_columns_still_pass(self):
        """Every numeric column stored as DECIMAL (integral volume) keeps the
        good fixture's all-pass result: reading volume as text must not break
        the price, volume or row checks."""
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "snapshot.duckdb"
            self._build(db, "con.execute('CREATE TABLE snapshot AS SELECT * REPLACE (CAST(open AS DECIMAL(18, 4)) AS open,"
                            " CAST(high AS DECIMAL(18, 4)) AS high, CAST(low AS DECIMAL(18, 4)) AS low,"
                            " CAST(close AS DECIMAL(18, 4)) AS close, CAST(volume AS DECIMAL(38, 0)) AS volume)"
                            " FROM read_csv(?)', [argv[0]])", FIXTURES / "good.csv")
            code, result = self._gate(db, "snapshot", tmp)
        self.assertEqual(code, 0, result["checks"])
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["row_count"], 4)

    def test_duckdb_view_over_external_file_is_rejected(self):
        """Regression (Codex, PR #132): input_sha256 hashes only the .duckdb
        file, so a view over read_parquet() let the gate validate mutable
        external rows the receipt does not identify. Only a base table in
        the hashed file is accepted; the base table beside the view passes."""
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "snapshot.duckdb"
            parquet = Path(tmp) / "current.parquet"
            self._build(db, "con.execute('CREATE TABLE snapshot AS SELECT * FROM read_csv(?)', [argv[0]])\n"
                            "con.execute(\"COPY snapshot TO '\" + argv[1] + \"' (FORMAT parquet)\")\n"
                            "con.execute(\"CREATE VIEW current_bars AS SELECT * FROM read_parquet('\" + argv[1] + \"')\")",
                        FIXTURES / "good.csv", parquet)
            code, result = self._gate(db, "current_bars", tmp)
            self.assertEqual(code, 1)
            self.assertEqual(result["status"], "fail")
            self.assertEqual([c["name"] for c in result["checks"]], ["gate_execution"])
            self.assertIn("duckdb_relation_not_base_table: current_bars is VIEW", result["checks"][0]["detail"])
            for relation in ("snapshot", "main.snapshot", "Main.SNAPSHOT", "snapshot.main.snapshot"):
                with self.subTest(relation=relation):
                    code, result = self._gate(db, relation, tmp)
                    self.assertEqual(code, 0, result["checks"])
                    self.assertEqual(result["status"], "pass")
            for relation in ("missing_table", "information_schema.tables", "system.information_schema.tables",
                             "temp.main.snapshot"):
                with self.subTest(relation=relation):
                    code, result = self._gate(db, relation, tmp)
                    self.assertEqual(code, 1)
                    self.assertRegex(result["checks"][0]["detail"],
                                     "duckdb_relation_not_found|duckdb_relation_not_base_table")

    def test_duckdb_pending_wal_is_rejected(self):
        """Rows still in `<db>.wal` are replayed by a read-only open but are
        not in the hashed file, so input_sha256 would not identify them."""
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "snapshot.duckdb"
            self._build(db, "con.execute('CREATE TABLE snapshot AS SELECT * FROM read_csv(?)', [argv[0]])",
                        FIXTURES / "good.csv")
            self._build(db, "con.execute(\"UPDATE snapshot SET volume = -1 WHERE symbol = 'SPY'\")\n"
                            "sys.stdout.flush(); os._exit(0)")
            self.assertTrue(Path(str(db) + ".wal").exists(), "builder left no WAL to test against")
            code, result = self._gate(db, "snapshot", tmp)
        self.assertEqual(code, 1)
        self.assertEqual(result["status"], "fail")
        self.assertIn("duckdb_wal_present", result["checks"][0]["detail"])


if __name__ == "__main__":
    unittest.main()
