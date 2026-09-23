"""Regression tests for the two `promotion_gate.py` findings from the blind
Codex cross-family review recorded in
`codex-ecosystem/state/grand-catalog-20260922/tools/codex-review-64-last.md`
(fd8e7fb parent commit):

1. A recognized pandera failure whose `failure_cases` row has `index: null`
   (e.g. `calendar.is_session()` raising on an unparseable `session` string
   rather than returning False) was silently dropped by `_summarize()`'s
   `.dropna()` on the index column, so the check reported "pass".
2. `_raw_volume_failure_indices()` validated a float/`pd.to_numeric()`
   conversion of the raw `volume` column, which is already lossy for values
   like `-1e-400` (underflows to `-0.0`, reads as non-negative/integral) and
   `9007199254740992.5` (loses its fractional part past float64 precision).

Plus one follow-up finding from a second-round blind Codex cross-family
review of the fix for (1) above (`codex-review-72`, 0a6ab80 parent commit):

3. The fix for (1) changed `_summarize()`'s per-check `count` to
   `len(subset)` -- the raw number of pandera `failure_cases` ROWS for that
   check name. Pandera emits more than one failure-case row per failed
   index for a dataframe-level check (one row per referenced column) and for
   `unique=[...]` multi-field-uniqueness checks (one row per field), so
   `len(subset)` overcounts distinct failed rows and falsely appends
   "row index unavailable" even when every case has an index. `count` must
   instead be the number of distinct non-null indices plus the number of
   failure cases that truly have no index.

Kept separate from `tests/test_promotion_gate.py` (owned by another session);
mirrors its structure: pure-stdlib tests (no pandas/numpy import, matching
`promotion_gate.py`'s own lazy-import discipline) always run; anything that
needs pandas/numpy/pandera runs through the gate's own isolated venv via
`_run_snippet`/`_run`, skipped when that venv is absent.
"""
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

SPEC = importlib.util.spec_from_file_location("promotion_gate_codex_review", GATE_FILE)
g = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = g
SPEC.loader.exec_module(g)


def _find_gate_python():
    override = os.environ.get("PROMOTION_GATE_PYTHON")
    if override and Path(override).exists():
        return override
    candidate = Path.home() / ".local/share/codex-ecosystem/tools/promotion-gate-20260922/.venv/bin/python3"
    return str(candidate) if candidate.exists() else None


GATE_PYTHON = _find_gate_python()


class SummarizeNullIndexPurePython(unittest.TestCase):
    """Finding 1, pure stdlib (no pandas): `_summarize()`'s `failure_cases`
    argument only needs to behave like a DataFrame with `.copy()`,
    `["check"].replace(...)`/`.unique()` and boolean-mask `[...]` indexing
    plus a `["index"].dropna()` column -- a minimal stand-in object avoids
    requiring pandas in the ambient test interpreter."""

    class _FakeFailureCases:
        """Just enough of the pandas API surface `_summarize()` touches:
        `.copy()`, `frame["col"] = frame["col"].replace(mapping)`,
        `frame["col"].unique()`, boolean-mask `frame[frame["col"] == name]`,
        and `subset["index"].dropna()`."""

        def __init__(self, rows):
            self._rows = rows  # list of dicts, e.g. {"check": ..., "index": ...}

        def __len__(self):
            return len(self._rows)

        def copy(self):
            return SummarizeNullIndexPurePython._FakeFailureCases([dict(row) for row in self._rows])

        def __getitem__(self, key):
            if isinstance(key, SummarizeNullIndexPurePython._Mask):
                return SummarizeNullIndexPurePython._FakeFailureCases(
                    [row for row, keep in zip(self._rows, key.values) if keep])
            return SummarizeNullIndexPurePython._FakeColumn(self, key)

        def __setitem__(self, key, value):
            pass  # the assigned `_FakeColumn` already mutated `self._rows` in place via `.replace()`

    class _Mask:
        def __init__(self, values):
            self.values = values

    class _FakeColumn:
        def __init__(self, table, key):
            self._table = table
            self._key = key

        def replace(self, mapping):
            for row in self._table._rows:
                if row[self._key] in mapping:
                    row[self._key] = mapping[row[self._key]]
            return self

        def unique(self):
            seen = []
            for row in self._table._rows:
                if row[self._key] not in seen:
                    seen.append(row[self._key])
            return seen

        def __eq__(self, other):
            return SummarizeNullIndexPurePython._Mask(
                [row[self._key] == other for row in self._table._rows])

        def dropna(self):
            return [row[self._key] for row in self._table._rows if row[self._key] is not None]

    def _failure_cases(self, index):
        return self._FakeFailureCases([
            {"check": "valid_trading_session", "index": index},
        ])

    def test_null_index_failure_fails_its_named_check(self):
        checks = g._summarize(self._failure_cases(None), row_count=1)
        by_name = {c["name"]: c for c in checks}
        self.assertEqual(by_name["valid_trading_session"]["status"], "fail")
        self.assertIn("row index unavailable", by_name["valid_trading_session"]["detail"])
        # Every other named check still reports "pass": the null-index
        # failure must not be silently absorbed into, or leak onto, another
        # check.
        self.assertTrue(all(c["status"] == "pass" for name, c in by_name.items()
                             if name != "valid_trading_session"), by_name)

    def test_indexed_failure_still_reports_example_indices(self):
        """The null-index fix must not regress the normal indexed path."""
        checks = g._summarize(self._failure_cases(0), row_count=1)
        by_name = {c["name"]: c for c in checks}
        self.assertEqual(by_name["valid_trading_session"]["status"], "fail")
        self.assertIn("example row indices [0]", by_name["valid_trading_session"]["detail"])
        self.assertNotIn("row index unavailable", by_name["valid_trading_session"]["detail"])


class SummarizeDuplicateIndexPurePython(unittest.TestCase):
    """Finding 3 (second-round review, `codex-review-72`): pandera can emit
    more than one `failure_cases` row for the SAME index -- one row per
    referenced column for a dataframe-level check (`high_ge_max_open_close`,
    `low_le_min_open_close`), or one row per field for a multi-field
    `unique=[...]` check (`unique_symbol_session`). `_summarize()` must count
    each distinct index once, not once per failure-case row, and must only
    say "row index unavailable" when a failure case truly has no index."""

    def _failure_cases(self, rows):
        return SummarizeNullIndexPurePython._FakeFailureCases(rows)

    def test_duplicate_index_rows_counted_once_no_unavailable_note(self):
        # Two failure-case rows share index 3 (e.g. touching both `open`
        # and `close`), plus one row for a distinct index 5. A buggy
        # `count = len(subset)` would report 3 failed rows here and wrongly
        # append "row index unavailable" even though every case has an
        # index.
        rows = [
            {"check": "high_ge_max_open_close", "index": 3},
            {"check": "high_ge_max_open_close", "index": 3},
            {"check": "high_ge_max_open_close", "index": 5},
        ]
        checks = g._summarize(self._failure_cases(rows), row_count=6)
        by_name = {c["name"]: c for c in checks}
        detail = by_name["high_ge_max_open_close"]["detail"]
        self.assertEqual(by_name["high_ge_max_open_close"]["status"], "fail")
        self.assertIn("2 of 6 rows failed", detail)
        self.assertIn("example row indices [3, 5]", detail)
        self.assertNotIn("row index unavailable", detail)

    def test_duplicate_index_rows_plus_genuine_null_index_row(self):
        # One duplicated index (2 rows -> 1 distinct) plus one genuinely
        # index-less failure case: count must be
        # len(distinct indices) + null-index case count = 1 + 1 = 2, and
        # the detail must still flag the unavailable index.
        rows = [
            {"check": "unique_symbol_session", "index": 1},
            {"check": "unique_symbol_session", "index": 1},
            {"check": "unique_symbol_session", "index": None},
        ]
        checks = g._summarize(self._failure_cases(rows), row_count=3)
        by_name = {c["name"]: c for c in checks}
        detail = by_name["unique_symbol_session"]["detail"]
        self.assertEqual(by_name["unique_symbol_session"]["status"], "fail")
        self.assertIn("2 of 3 rows failed", detail)
        self.assertIn("example row indices [1]", detail)
        self.assertIn("row index unavailable", detail)


class VolumeDecimalPurePython(unittest.TestCase):
    """Finding 2, pure stdlib: `_volume_cell_fails` must Decimal-parse the
    exact raw string form, not a lossy float conversion, and must not
    require numpy/pandas to be importable."""

    def test_underflowing_negative_literal_fails(self):
        # A naive float() conversion underflows this to -0.0, which then
        # reads as non-negative and integral.
        self.assertTrue(g._volume_cell_fails("-1e-400"))

    def test_precision_losing_fraction_fails(self):
        # float64 cannot represent this value's fractional part; a naive
        # float() round-trip makes it look integral.
        self.assertTrue(g._volume_cell_fails("9007199254740992.5"))

    def test_non_canonical_numeric_text_fails(self):
        # Decimal parses these; pd.to_numeric turns them into NaN.
        for text in ("1_000", "\u0661\u0662\u0663", "1 000", "Infinity", "NaN", "0x10"):
            with self.subTest(text=text):
                self.assertTrue(g._volume_cell_fails(text))
        for text in ("0", "1000", "1000.0", "1e3", "+5"):
            with self.subTest(text=text):
                self.assertFalse(g._volume_cell_fails(text))

    def test_int64_max_passes_and_one_above_fails(self):
        self.assertFalse(g._volume_cell_fails(str(g.INT64_MAX)))
        self.assertTrue(g._volume_cell_fails(str(g.INT64_MAX + 1)))

    def test_negative_zero_literal_fails(self):
        self.assertTrue(g._volume_cell_fails("-0"))
        self.assertTrue(g._volume_cell_fails("-0.0"))
        self.assertFalse(g._volume_cell_fails("0"))

    def test_exact_integer_text_passes(self):
        self.assertFalse(g._volume_cell_fails("45231000"))

    def test_non_finite_text_fails(self):
        self.assertTrue(g._volume_cell_fails("1e400"))
        self.assertTrue(g._volume_cell_fails("nan"))

    def test_plain_python_int_is_exact_and_passes(self):
        """A plain Python int (e.g. a Parquet int64 column read without
        pandas' numpy dtype) goes straight through `Decimal(int(...))`,
        never a float."""
        self.assertFalse(g._volume_cell_fails(g.INT64_MAX))
        self.assertTrue(g._volume_cell_fails(-1))


@unittest.skipUnless(GATE_PYTHON, "requires the gate's isolated venv "
                      "(uv venv + pandera==0.33.1 pandas exchange_calendars==4.13.2 pyarrow)")
class FixtureGateRuns(unittest.TestCase):
    """Runs the CLI in its own venv subprocess, matching real use, plus a
    couple of pandas/numpy-dependent unit checks that must not run in the
    ambient (no-pandas) test interpreter."""

    def _run(self, fixture_name):
        fixture = FIXTURES / fixture_name
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "gate-result.json"
            proc = subprocess.run([GATE_PYTHON, str(GATE_FILE), "--input", str(fixture), "--out", str(out)],
                                   capture_output=True, text=True, timeout=60)
            result = json.loads(out.read_text())
            return proc.returncode, result

    def _run_snippet(self, body):
        script = (f"import importlib.util as u\n"
                   f"spec = u.spec_from_file_location('promotion_gate', {str(GATE_FILE)!r})\n"
                   "g = u.module_from_spec(spec); spec.loader.exec_module(g)\n" + body)
        with tempfile.TemporaryDirectory() as tmp:
            script_path = Path(tmp) / "snippet.py"
            script_path.write_text(script)
            return subprocess.run([GATE_PYTHON, str(script_path)], capture_output=True, text=True, timeout=30)

    def test_null_index_session_fixture_fails_closed(self):
        """Finding 1: session='not-a-date' raises inside the element-wise
        check rather than returning False, so pandera's `failure_cases` has
        `index: null` for this row. The gate must still fail
        `valid_trading_session` for it."""
        code, result = self._run("null-index-session.csv")
        self.assertEqual(code, 1)
        self.assertEqual(result["status"], "fail")
        by_name = {c["name"]: c for c in result["checks"]}
        self.assertEqual(by_name["valid_trading_session"]["status"], "fail")
        self.assertIn("row index unavailable", by_name["valid_trading_session"]["detail"])
        self.assertTrue(all(c["status"] == "pass" for name, c in by_name.items()
                             if name != "valid_trading_session"), by_name)

    def test_lossy_volume_conversion_fixture_fails_closed(self):
        """Finding 2: '-1e-400' and '9007199254740992.5' must both fail
        `volume_integral_non_negative` via exact Decimal parsing of the raw
        text, not a lossy float conversion."""
        code, result = self._run("lossy-volume-conversion.csv")
        self.assertEqual(code, 1)
        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["row_count"], 2)
        by_name = {c["name"]: c for c in result["checks"]}
        self.assertEqual(by_name["volume_integral_non_negative"]["status"], "fail")
        self.assertIn("example row indices [0, 1]", by_name["volume_integral_non_negative"]["detail"])
        self.assertTrue(all(c["status"] == "pass" for name, c in by_name.items()
                             if name != "volume_integral_non_negative"), by_name)

    def test_int64_dtype_cell_is_exact_and_passes(self):
        """`raw_frame['volume']` values already read by pandas as int64 (a
        whole-number CSV column, or a Parquet int64 column) go straight
        through `Decimal(int(...))`, never a float."""
        proc = self._run_snippet(
            "import json, numpy as np\n"
            f"print(json.dumps([g._volume_cell_fails(np.int64({g.INT64_MAX})),\n"
            "                    g._volume_cell_fails(np.int64(-1))]))\n")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout), [False, True])

    def test_raw_volume_failure_indices_over_string_series(self):
        proc = self._run_snippet(
            "import json, pandas as pd\n"
            "frame = pd.DataFrame({'volume': ['-1e-400', '9007199254740992.5', '100']})\n"
            "print(json.dumps(g._raw_volume_failure_indices(frame)))\n")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout), [0, 1])

    def test_bad_fixture_detail_counts_match_distinct_row_indices(self):
        """Finding 3: `bad.csv` fails `high_ge_max_open_close` for exactly
        one row (index 3, which fails on both the `high >= open` and
        `high >= close` comparisons touching the same row) and
        `unique_symbol_session` for exactly two rows (indices 0 and 1,
        each producing one `failure_cases` row per uniqueness field). A
        buggy `count = len(subset)` (Codex `codex-review-72`) would report
        more failed rows than exist and a spurious "row index unavailable"
        even though every case here has an index."""
        code, result = self._run("bad.csv")
        self.assertEqual(code, 1)
        by_name = {c["name"]: c for c in result["checks"]}
        self.assertEqual(by_name["high_ge_max_open_close"]["detail"],
                          "1 of 4 rows failed; example row indices [3]")
        self.assertEqual(by_name["unique_symbol_session"]["detail"],
                          "2 of 4 rows failed; example row indices [0, 1]")

    def test_load_frame_preserves_exact_volume_text_from_csv(self):
        """The CSV loader must hand `volume` to `_raw_volume_failure_indices`
        as its exact source text (`dtype=str`), not an already-lossy float64
        column -- otherwise Decimal-parsing downstream is moot."""
        proc = self._run_snippet(
            "import json\n"
            f"frame = g._load_frame({str(FIXTURES / 'lossy-volume-conversion.csv')!r})\n"
            "print(json.dumps(list(frame['volume'])))\n")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout), ["-1e-400", "9007199254740992.5"])


if __name__ == "__main__":
    unittest.main()
