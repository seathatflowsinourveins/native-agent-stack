"""Local negative tests for the SPY/LEAN parity admission, causality and comparator.

These are synthetic boundary fixtures for the gate G-a harness. They do not run
the engine, do not touch a broker and do not establish parity by themselves.
"""
import hashlib
import importlib.util
import json
import re
from decimal import Decimal
from pathlib import Path
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "blueprints/us-equities/engine-nautilus/spy-parity"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CONVERT = _load("spy_parity_convert", SOURCE / "convert.py")
FIXTURE = _load("spy_parity_fixture", SOURCE / "fixture_strategy.py")
COMPARE = _load("spy_parity_compare", SOURCE / "compare.py")
RUN = _load("spy_parity_run", SOURCE / "run.py")
TOLERANCES = json.loads((SOURCE / "tolerances.json").read_text())["limits"]
MANIFEST = json.loads((SOURCE / "mapping-manifest.json").read_text())
LEAN_RECEIPT = ROOT / "blueprints/us-equities/historical-simulation/receipt.json"


class _TrackingLimits(dict):
    """Records which tolerance keys the comparator actually reads."""

    def __init__(self, base):
        super().__init__(base)
        self.used = set()

    def __getitem__(self, key):
        self.used.add(key)
        return super().__getitem__(key)

HOUR_LINES = [
    "20191202 09:00,3146300,3146600,3111800,3116400,66926781",
    "20191202 10:00,3116400,3120000,3110000,3118000,10000000",
    "20191203 09:00,3086400,3096400,3071300,3095500,66499178",
]


class InputAdmissionTests(unittest.TestCase):
    def test_bad_input_hash_and_missing_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = "equity/usa/map_files/spy.csv"
            expected = {target: hashlib.sha256(b"19980102,spy,P\n").hexdigest()}
            (root / "equity/usa/map_files").mkdir(parents=True)
            with self.assertRaisesRegex(ValueError, "missing_input:" + target):
                CONVERT.verify_inputs(root, expected)
            (root / target).write_bytes(b"19980102,spy,P\n")
            self.assertEqual(CONVERT.verify_inputs(root, expected), expected)
            (root / target).write_bytes(b"19980102,tampered,P\n")
            with self.assertRaisesRegex(ValueError, "input_hash_mismatch:" + target):
                CONVERT.verify_inputs(root, expected)

    def test_frozen_table_covers_every_acceptance_plan_input(self):
        self.assertEqual(sorted(CONVERT.FROZEN_INPUT_SHA256), [
            "alternative/interest-rate/usa/interest-rate.csv",
            "equity/usa/daily/spy.zip",
            "equity/usa/factor_files/spy.csv",
            "equity/usa/hour/spy.zip",
            "equity/usa/map_files/spy.csv",
        ])

    def test_unexpected_zip_schema_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "spy.zip"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("spy.csv", "\n".join(HOUR_LINES))
                archive.writestr("extra.csv", "x")
            with self.assertRaisesRegex(ValueError, "unexpected_zip_schema"):
                CONVERT.read_zip_member(path, "spy.csv")


class DecodeTests(unittest.TestCase):
    def test_window_decode_and_bar_end_instant(self):
        rows = CONVERT.parse_hour_rows(HOUR_LINES, "2019-12-02", "2019-12-03")
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["o"], "314.6300")
        self.assertEqual(rows[0]["v"], 66926781)
        # An hourly row labelled by its local start is complete one hour later.
        self.assertEqual(rows[0]["ts_event_ns"], 1575298800 * 10 ** 9)

    def test_decision_bar_instants_across_dst(self):
        for line, expected in (("20191231 15:00,3209400,3221250,3208900,3218600,17744667", 1577826000),
                               ("20200429 15:00,2939900,2940000,2930000,2932100,1000000", 1588190400)):
            row = CONVERT.parse_hour_rows([line], "2019-12-02", "2020-04-30")[0]
            self.assertEqual(row["ts_event_ns"] // 10 ** 9, expected)

    def test_duplicate_timestamp(self):
        lines = HOUR_LINES + [HOUR_LINES[0]]
        with self.assertRaisesRegex(ValueError, "duplicate_timestamp:2019-12-02 09:00"):
            CONVERT.parse_hour_rows(lines, "2019-12-02", "2019-12-03")

    def test_corruption_outside_the_window_still_refuses_the_file(self):
        outside = "20180102 09:00,3146300,3146600,3111800,3116400,1"
        for lines, code in (([outside, outside] + HOUR_LINES, "duplicate_timestamp:2018-01-02"),
                            ([HOUR_LINES[0], outside] + HOUR_LINES[1:],
                             "non_monotonic_timestamp:2018-01-02")):
            with self.subTest(code=code), self.assertRaisesRegex(ValueError, code):
                CONVERT.parse_hour_rows(lines, "2019-12-02", "2019-12-03")

    def test_a_clean_row_outside_the_window_is_still_excluded(self):
        lines = ["20180102 09:00,3146300,3146600,3111800,3116400,1"] + HOUR_LINES
        rows = CONVERT.parse_hour_rows(lines, "2019-12-02", "2019-12-03")
        self.assertEqual([r["session_date"] for r in rows],
                         ["2019-12-02", "2019-12-02", "2019-12-03"])

    def test_non_monotonic_rows(self):
        with self.assertRaisesRegex(ValueError, "non_monotonic_timestamp"):
            CONVERT.parse_hour_rows(list(reversed(HOUR_LINES)), "2019-12-02", "2019-12-03")

    def test_malformed_nonfinite_and_nonintegral_records(self):
        cases = {
            "malformed_row_field_count": "20191202 09:00,3146300,3146600,3111800,3116400",
            "malformed_price_field": "20191202 09:00,31463.00,3146600,3111800,3116400,1",
            "nonfinite_or_nonpositive_price": "20191202 09:00,0,3146600,3111800,3116400,1",
            "nonintegral_volume": "20191202 09:00,3146300,3146600,3111800,3116400,1.5",
            "invalid_ohlc": "20191202 09:00,3146300,3116000,3111800,3146400,1",
            "malformed_timestamp": "20191202T09:00,3146300,3146600,3111800,3116400,1",
        }
        for code, line in cases.items():
            with self.subTest(code=code), self.assertRaisesRegex(ValueError, code):
                CONVERT.parse_hour_rows([line], "2019-12-02", "2019-12-03")


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.rows = CONVERT.parse_hour_rows(HOUR_LINES, "2019-12-02", "2019-12-03")

    SHORT = {"2019-12-02": 2, "2019-12-03": 1}

    def test_exact_membership(self):
        counts = CONVERT.check_sessions(self.rows, ["2019-12-02", "2019-12-03"], self.SHORT)
        self.assertEqual(counts["sessions"], 2)
        self.assertEqual(counts["hour_rows"], 3)
        self.assertEqual(counts["full_session_rows"], 7)
        self.assertEqual(counts["partial_sessions"], self.SHORT)

    def test_missing_session_is_refused_not_forward_filled(self):
        with self.assertRaisesRegex(ValueError, "missing_session:2019-12-04"):
            CONVERT.check_sessions(self.rows, ["2019-12-02", "2019-12-03", "2019-12-04"], self.SHORT)

    def test_extra_session_is_refused(self):
        with self.assertRaisesRegex(ValueError, "extra_session:2019-12-03"):
            CONVERT.check_sessions(self.rows, ["2019-12-02"], self.SHORT)

    def test_undeclared_short_session_is_refused_not_reported(self):
        with self.assertRaisesRegex(ValueError, "unexpected_short_session:2019-12-03"):
            CONVERT.check_sessions(self.rows, ["2019-12-02", "2019-12-03"],
                                   {"2019-12-02": 2})
        with self.assertRaisesRegex(ValueError, "unexpected_short_session:2019-12-02"):
            CONVERT.check_sessions(self.rows, ["2019-12-02", "2019-12-03"],
                                   {"2019-12-02": 5, "2019-12-03": 1})

    def test_declared_short_session_that_is_absent_is_refused(self):
        with self.assertRaisesRegex(ValueError, "declared_short_session_absent:2019-12-09"):
            CONVERT.check_sessions(self.rows, ["2019-12-02", "2019-12-03"],
                                   {**self.SHORT, "2019-12-09": 4})

    def test_long_session_is_refused(self):
        lines = ["20191202 {:02d}:00,3146300,3146600,3111800,3116400,1".format(hour)
                 for hour in range(9, 17)]
        rows = CONVERT.parse_hour_rows(lines, "2019-12-02", "2019-12-02")
        with self.assertRaisesRegex(ValueError, "unexpected_long_session:2019-12-02"):
            CONVERT.check_sessions(rows, ["2019-12-02"], None)

    def test_manifest_declares_the_only_real_short_session(self):
        row = next(m for m in MANIFEST["mappings"] if m["id"] == "sessions_and_time")
        self.assertEqual(row["full_session_rows"], CONVERT.FULL_SESSION_ROWS)
        self.assertEqual(row["known_short_sessions"], {"2019-12-24": 4})
        self.assertEqual(RUN.known_short_sessions(MANIFEST), {"2019-12-24": 4})

    def test_map_file_rename_in_window(self):
        with self.assertRaisesRegex(ValueError, "map_file_rename_in_window"):
            CONVERT.check_map_file("19980102,spy,P\n20200101,spx,P\n", "SPY", "2019-12-02", "2020-04-30")


class CorporateActionTests(unittest.TestCase):
    """Frozen SPY factor rows; the derivation is independent of the LEAN oracle."""

    FACTORS = "20191219,0.9736767,1,320.9\n20200319,0.9784638,1,240.51\n20200618,0.9842156,1,311.78\n"

    def test_distribution_amounts_and_instants(self):
        rows = CONVERT.parse_factor_rows(self.FACTORS)
        found = CONVERT.derive_distributions(rows, "2019-12-02", "2020-04-30")
        self.assertEqual(found, [
            {"ex_date": "2019-12-20", "utc_seconds": 1576818000, "per_share": "1.57"},
            {"ex_date": "2020-03-20", "utc_seconds": 1584676800, "per_share": "1.41"},
        ])

    def test_unexpected_split_blocks_the_fixture(self):
        rows = CONVERT.parse_factor_rows("20200319,0.9784638,1,240.51\n20200618,0.9842156,2,311.78\n")
        with self.assertRaisesRegex(ValueError, "unexpected_split:2020-03-20"):
            CONVERT.check_no_splits(rows, "2019-12-02", "2020-04-30")

    def test_eligible_holdings_only(self):
        fills = [{"utc_seconds": 1577977200, "quantity": 304, "price": "323.58", "fee": "0"}]
        ledger = FIXTURE.distribution_ledger(
            CONVERT.derive_distributions(CONVERT.parse_factor_rows(self.FACTORS),
                                         "2019-12-02", "2020-04-30"), fills)
        self.assertEqual([Decimal(d["amount"]) for d in ledger], [Decimal("0"), Decimal("428.64")])
        self.assertEqual([d["quantity"] for d in ledger], ["0", "304"])
        self.assertTrue(all(d["engine_posted"] is False for d in ledger))


class CausalityTests(unittest.TestCase):
    INTENTS = [{"order_ref": 1, "utc_seconds": 1577826000, "quantity": 304}]

    def test_fill_after_decision_passes(self):
        fills = [{"order_ref": 1, "utc_seconds": 1577977200, "quantity": 304}]
        self.assertIsNone(FIXTURE.check_causality(self.INTENTS, fills))

    def test_look_ahead_guard_rejects_same_bar_and_earlier_fills(self):
        for seconds in (1577826000, 1577825999):
            with self.subTest(seconds=seconds), self.assertRaisesRegex(ValueError, "look_ahead_fill"):
                FIXTURE.check_causality(
                    self.INTENTS, [{"order_ref": 1, "utc_seconds": seconds, "quantity": 304}])

    def test_unattributed_and_oversized_fills(self):
        with self.assertRaisesRegex(ValueError, "unattributed_fill"):
            FIXTURE.check_causality(
                self.INTENTS, [{"order_ref": 9, "utc_seconds": 1577977200, "quantity": 304}])
        with self.assertRaisesRegex(ValueError, "fill_exceeds_intent"):
            FIXTURE.check_causality(
                self.INTENTS, [{"order_ref": 1, "utc_seconds": 1577977200, "quantity": 305}])

    def test_partial_fills_are_accumulated_per_order(self):
        within = [{"order_ref": 1, "utc_seconds": 1577977200, "quantity": 104},
                  {"order_ref": 1, "utc_seconds": 1577980800, "quantity": 200}]
        self.assertIsNone(FIXTURE.check_causality(self.INTENTS, within))
        # No single fill exceeds 304, but together they do.
        over = within + [{"order_ref": 1, "utc_seconds": 1577984400, "quantity": 1}]
        with self.assertRaisesRegex(ValueError, "fill_exceeds_intent:1"):
            FIXTURE.check_causality(self.INTENTS, over)

    def test_a_fill_on_the_wrong_side_is_refused(self):
        with self.assertRaisesRegex(ValueError, "fill_side_mismatch:1"):
            FIXTURE.check_causality(
                self.INTENTS, [{"order_ref": 1, "utc_seconds": 1577977200, "quantity": -10}])

    def test_sizing_rule_is_floor_of_buffered_target(self):
        self.assertEqual(FIXTURE.target_quantity(Decimal("100000"), Decimal("1"),
                                                 Decimal("0.98"), Decimal("321.86")), 304)

    def test_decision_bar_is_the_sixteen_hundred_row(self):
        rows = [{"session_date": "2019-12-31", "local_start": "14:00"},
                {"session_date": "2019-12-31", "local_start": "15:00"}]
        self.assertEqual(FIXTURE.decision_rows(rows, ["2019-12-31"])["2019-12-31"], rows[1])
        with self.assertRaisesRegex(ValueError, "missing_decision_bar"):
            FIXTURE.decision_rows(rows[:1], ["2019-12-31"])


ENTRY_INTENT_TS, ENTRY_FILL_TS = 1577826000, 1577977200
EXIT_INTENT_TS, EXIT_FILL_TS = 1588190400, 1588255200
DIVIDEND_ZERO_TS, DIVIDEND_TS = 1576818000, 1584676800

# Retained first bars of the two fill sessions, plus a later bar to prove the
# comparator uses the session's FIRST bar and not merely any matching row.
BARS = [
    {"session_date": "2020-01-02", "local_start": "09:00", "ts_event_ns": ENTRY_FILL_TS * 10 ** 9,
     "o": "323.5800", "h": "324.0200", "l": "323.4100", "c": "323.8700", "v": 6498003},
    {"session_date": "2020-01-02", "local_start": "10:00",
     "ts_event_ns": (ENTRY_FILL_TS + 3600) * 10 ** 9,
     "o": "323.8800", "h": "323.9000", "l": "322.6100", "c": "323.2500", "v": 7134452},
    {"session_date": "2020-04-30", "local_start": "09:00", "ts_event_ns": EXIT_FILL_TS * 10 ** 9,
     "o": "291.6900", "h": "292.0000", "l": "291.0000", "c": "291.2350", "v": 1000000},
]


def _oracle(fills, dividends, end_cash, fill_count=None):
    return {
        "id": "one_zero",
        "intents": [{"utc_seconds": ENTRY_INTENT_TS, "quantity": 304, "reason": "entry"},
                    {"utc_seconds": EXIT_INTENT_TS, "quantity": -304, "reason": "exit"}],
        "fills": fills, "fees_usd": Decimal("0"), "dividends_usd": Decimal(dividends),
        "end_cash_usd": Decimal(end_cash), "final_quantity": 0,
        "fill_count": len(fills) if fill_count is None else fill_count,
    }


ORACLE = _oracle([{"utc_seconds": ENTRY_FILL_TS, "quantity": 304,
                   "price": Decimal("323.58"), "fee": Decimal("0")},
                  {"utc_seconds": EXIT_FILL_TS, "quantity": -304,
                   "price": Decimal("291.69"), "fee": Decimal("0")}],
                 "428.64", "90734.08")
# A control with no distribution at all, so an exact replay can reach PASS.
ORACLE_CLEAN = _oracle(ORACLE["fills"], "0", "90305.44")


def _receipt(fills, dividends, distributions, **overrides):
    """Build a receipt whose cash ledger is consistent with its own fills."""
    ledger = COMPARE.recompute_cash_ledger(Decimal("100000"), fills, distributions)
    base = {
        "case": "one_zero",
        "case_configuration": {"initial_cash_usd": "100000",
                               "window": {"symbol": "SPY", "start": "2019-12-02",
                                          "end": "2020-04-30"}},
        "intents": [{"utc_seconds": ENTRY_INTENT_TS, "quantity": 304, "reason": "entry"},
                    {"utc_seconds": EXIT_INTENT_TS, "quantity": -304, "reason": "exit"}],
        "fills": fills, "fees_usd": "0", "dividend_cash_usd": dividends,
        "distribution_ledger": distributions,
        "cash_ledger": [{"kind": e["kind"], "utc_seconds": e["utc_seconds"], "cash": str(e["cash"])}
                        for e in ledger],
        "reconciled_end_cash_usd": str(ledger[-1]["cash"]) if ledger else "100000",
        "native_end_cash_usd": str((ledger[-1]["cash"] if ledger else Decimal("100000"))
                                   - Decimal(dividends)),
        "final_quantity": "0", "two_run_records_equal": True,
    }
    base.update(overrides)
    return base


BLOCKED_FILLS = [{"utc_seconds": ENTRY_FILL_TS, "quantity": 304, "price": "323.87", "fee": "0"},
                 {"utc_seconds": EXIT_FILL_TS, "quantity": -304, "price": "291.2350", "fee": "0"}]
MATCHED_FILLS = [{"utc_seconds": ENTRY_FILL_TS, "quantity": 304, "price": "323.58", "fee": "0"},
                 {"utc_seconds": EXIT_FILL_TS, "quantity": -304, "price": "291.69", "fee": "0"}]
DISTRIBUTIONS = [{"utc_seconds": DIVIDEND_ZERO_TS, "amount": "0.00", "engine_posted": False},
                 {"utc_seconds": DIVIDEND_TS, "amount": "428.64", "engine_posted": False}]


def _failing(verdict):
    return [c["id"] for c in verdict["checks"] if c["status"] == "FAIL"]


def _check(verdict, check_id, field):
    return next(c for c in verdict["checks"] if c["id"] == check_id and c["field"] == field)


class ComparatorControlTests(unittest.TestCase):
    def test_exact_replay_with_no_distribution_passes(self):
        verdict = COMPARE.compare(_receipt(MATCHED_FILLS, "0", []), ORACLE_CLEAN,
                                  TOLERANCES, MANIFEST, BARS)
        self.assertEqual(verdict["verdict"], "PASS")
        self.assertEqual(verdict["failed"], 0)

    def test_nondeterministic_runs_fail(self):
        verdict = COMPARE.compare(_receipt(MATCHED_FILLS, "0", [], two_run_records_equal=False),
                                  ORACLE_CLEAN, TOLERANCES, MANIFEST, BARS)
        self.assertEqual(verdict["verdict"], "FAIL")
        self.assertIn("two_run_determinism", _failing(verdict))

    def test_case_mismatch_is_refused(self):
        with self.assertRaisesRegex(ValueError, "case_mismatch"):
            COMPARE.compare(_receipt(MATCHED_FILLS, "0", [], case="two_zero"), ORACLE_CLEAN,
                            TOLERANCES, MANIFEST, BARS)

    def test_skipped_evidence_blocks_a_pass_even_with_no_failures(self):
        clean = _receipt(MATCHED_FILLS, "0", [])
        self.assertEqual(COMPARE.compare(clean, ORACLE_CLEAN, TOLERANCES, MANIFEST, BARS)["verdict"],
                         "PASS")
        for bars in (None, []):
            with self.subTest(bars=bars):
                verdict = COMPARE.compare(clean, ORACLE_CLEAN, TOLERANCES, MANIFEST, bars)
                self.assertEqual(verdict["failed"], 0)
                self.assertEqual(verdict["verdict"], "BLOCKED-INCOMPLETE")
                self.assertFalse(verdict["complete"])
                self.assertEqual(len(verdict["skipped"]), 1)

    def test_empty_bar_list_records_the_same_skip_marker_as_no_bars(self):
        verdict = COMPARE.compare(_receipt(BLOCKED_FILLS, "428.64", DISTRIBUTIONS), ORACLE,
                                  TOLERANCES, MANIFEST, [])
        evidence = _check(verdict, "attribution_evidence", "converted_bars")
        self.assertEqual(evidence["status"], "SKIPPED")
        self.assertEqual(evidence["observed"], "empty")
        self.assertEqual(verdict["attribution_evidence"], "none")
        self.assertEqual(verdict["skipped"], [evidence["key"]])
        self.assertEqual(verdict["blocking_mappings"], [])
        self.assertEqual(verdict["verdict"], "FAIL")

    def test_a_blocked_run_without_evidence_is_named_incomplete(self):
        verdict = COMPARE.compare(_receipt(BLOCKED_FILLS, "428.64", DISTRIBUTIONS), ORACLE,
                                  TOLERANCES, MANIFEST, BARS)
        self.assertEqual(verdict["verdict"], "BLOCKED")
        self.assertTrue(verdict["complete"])


class InternalReconciliationTests(unittest.TestCase):
    """A headline balance must agree with the ledger compare.py rebuilds itself."""

    def test_published_receipt_reconciles_against_its_own_fills(self):
        receipt = json.loads((SOURCE / "receipt.json").read_text())
        oracle = COMPARE.oracle_case(json.loads(LEAN_RECEIPT.read_text()), receipt["case"])
        verdict = COMPARE.compare(receipt, oracle, TOLERANCES, MANIFEST, None)
        for name in ("end_cash_internal", "native_end_cash_internal"):
            with self.subTest(name=name):
                check = next(c for c in verdict["checks"] if c["id"] == name)
                self.assertEqual(check["status"], "PASS", check)
                self.assertEqual(Decimal(check["delta"]), 0)

    def test_reconciled_headline_contradicting_the_ledger_fails(self):
        receipt = _receipt(MATCHED_FILLS, "0", [], reconciled_end_cash_usd="90305.46")
        verdict = COMPARE.compare(receipt, ORACLE_CLEAN, TOLERANCES, MANIFEST, BARS)
        check = _check(verdict, "end_cash_internal", "reconciled_vs_rebuilt_ledger")
        self.assertEqual(check["status"], "FAIL")
        self.assertIsNone(check["blocked_by"])
        self.assertEqual(Decimal(check["expected"]), Decimal("90305.44"))
        self.assertEqual(verdict["verdict"], "FAIL")

    def test_native_headline_contradicting_the_ledger_fails(self):
        receipt = _receipt(BLOCKED_FILLS, "428.64", DISTRIBUTIONS, native_end_cash_usd="90100.00")
        verdict = COMPARE.compare(receipt, ORACLE, TOLERANCES, MANIFEST, BARS)
        check = _check(verdict, "native_end_cash_internal", "native_vs_rebuilt_ledger")
        self.assertEqual(check["status"], "FAIL")
        self.assertIsNone(check["blocked_by"])
        self.assertEqual(Decimal(check["expected"]), Decimal("90078.96"))
        self.assertEqual(verdict["verdict"], "FAIL")

    def test_the_native_identity_holds_for_a_posted_ledger(self):
        posted = [dict(d, engine_posted=True) for d in DISTRIBUTIONS]
        receipt = _receipt(BLOCKED_FILLS, "428.64", posted,
                           native_end_cash_usd="90507.6000")
        verdict = COMPARE.compare(receipt, ORACLE, TOLERANCES, MANIFEST, BARS)
        check = _check(verdict, "native_end_cash_internal", "native_vs_rebuilt_ledger")
        self.assertEqual(check["status"], "PASS")

    def test_internal_reconciliation_uses_cash_usd_abs(self):
        inside = _receipt(MATCHED_FILLS, "0", [], reconciled_end_cash_usd="90305.45")
        self.assertEqual(_check(COMPARE.compare(inside, ORACLE_CLEAN, TOLERANCES, MANIFEST, BARS),
                                "end_cash_internal", "reconciled_vs_rebuilt_ledger")["status"],
                         "PASS")


class MeasuredAttributionTests(unittest.TestCase):
    """A deviation is BLOCKED only when the converted bars measure it as such."""

    def test_declared_deviation_is_blocked_with_zero_residue(self):
        verdict = COMPARE.compare(_receipt(BLOCKED_FILLS, "428.64", DISTRIBUTIONS), ORACLE,
                                  TOLERANCES, MANIFEST, BARS)
        self.assertEqual(verdict["verdict"], "BLOCKED")
        self.assertEqual(verdict["unattributed_failures"], [])
        self.assertEqual(_check(verdict, "entry_fill", "fill_price_usd")["blocked_by"],
                         "market_on_open_proxy")
        self.assertEqual(_check(verdict, "entry_fill", "fill_price_usd")["evidence"],
                         {"session_date": "2020-01-02", "first_bar_open": "323.5800",
                          "first_bar_close": "323.8700"})
        end = _check(verdict, "end_cash", "reconciled_end_cash_usd")
        self.assertEqual(Decimal(end["unexplained_residue"]), 0)
        self.assertEqual(Decimal(end["explained_by_fill_prices"]), Decimal("-226.48"))

    def test_reconciled_end_cash_never_names_a_mapping_that_contributed_nothing(self):
        verdict = COMPARE.compare(_receipt(BLOCKED_FILLS, "428.64", DISTRIBUTIONS), ORACLE,
                                  TOLERANCES, MANIFEST, BARS)
        end = _check(verdict, "end_cash", "reconciled_end_cash_usd")
        self.assertEqual(end["blocked_by"], "market_on_open_proxy")
        self.assertNotIn("distributions_and_cash", end["blocked_by"])

    def test_native_balance_attributes_the_unposted_distribution(self):
        verdict = COMPARE.compare(_receipt(BLOCKED_FILLS, "428.64", DISTRIBUTIONS), ORACLE,
                                  TOLERANCES, MANIFEST, BARS)
        native = _check(verdict, "native_end_cash", "native_end_cash_usd")
        self.assertEqual(native["blocked_by"], "distributions_and_cash,market_on_open_proxy")
        self.assertEqual(Decimal(native["unexplained_residue"]), 0)

    def test_a_wrong_fill_price_is_not_the_declared_deviation(self):
        """The refutation case: a price that is not the first-bar close stays FAIL."""
        wrong = [{"utc_seconds": ENTRY_FILL_TS, "quantity": 304, "price": "999.99", "fee": "0"},
                 {"utc_seconds": EXIT_FILL_TS, "quantity": -304, "price": "291.2350", "fee": "0"}]
        verdict = COMPARE.compare(_receipt(wrong, "428.64", DISTRIBUTIONS), ORACLE,
                                  TOLERANCES, MANIFEST, BARS)
        self.assertEqual(verdict["verdict"], "FAIL")
        entry = _check(verdict, "entry_fill", "fill_price_usd")
        self.assertIsNone(entry["blocked_by"])
        self.assertIn(entry["key"], verdict["unattributed_failures"])

    def test_cash_residue_outside_the_fill_deltas_stays_unattributed(self):
        verdict = COMPARE.compare(
            _receipt(BLOCKED_FILLS, "428.64", DISTRIBUTIONS,
                     reconciled_end_cash_usd="90400.00"), ORACLE, TOLERANCES, MANIFEST, BARS)
        end = _check(verdict, "end_cash", "reconciled_end_cash_usd")
        self.assertIsNone(end["blocked_by"])
        self.assertNotEqual(Decimal(end["unexplained_residue"]), 0)
        self.assertEqual(verdict["verdict"], "FAIL")

    def test_without_converted_bars_nothing_can_be_attributed(self):
        verdict = COMPARE.compare(_receipt(BLOCKED_FILLS, "428.64", DISTRIBUTIONS), ORACLE,
                                  TOLERANCES, MANIFEST, None)
        self.assertEqual(verdict["verdict"], "FAIL")
        self.assertEqual(verdict["blocking_mappings"], [])
        self.assertEqual(verdict["attribution_evidence"], "none")

    def test_absent_attribution_evidence_is_skipped_never_passed(self):
        verdict = COMPARE.compare(_receipt(BLOCKED_FILLS, "428.64", DISTRIBUTIONS), ORACLE,
                                  TOLERANCES, MANIFEST, None)
        evidence = _check(verdict, "attribution_evidence", "converted_bars")
        self.assertEqual(evidence["status"], "SKIPPED")
        self.assertNotEqual(evidence["expected"], evidence["observed"])
        self.assertTrue(evidence["reason"])
        self.assertEqual(verdict["skipped"], [evidence["key"]])
        for check in verdict["checks"]:
            if check["status"] == "PASS":
                self.assertEqual(check["expected"], check["observed"], check["key"])

    def test_distributions_are_attributed_only_when_the_ledger_says_unposted(self):
        posted = [dict(d, engine_posted=True) for d in DISTRIBUTIONS]
        verdict = COMPARE.compare(_receipt(BLOCKED_FILLS, "428.64", posted), ORACLE,
                                  TOLERANCES, MANIFEST, BARS)
        native = _check(verdict, "native_end_cash", "native_end_cash_usd")
        self.assertFalse(native["distribution_ledger_all_unposted"])
        self.assertIsNone(native["blocked_by"])
        self.assertEqual(verdict["verdict"], "FAIL")

    def test_distributions_are_attributed_only_when_the_ledger_sum_matches(self):
        mismatched = [DISTRIBUTIONS[0], dict(DISTRIBUTIONS[1], amount="400.00")]
        receipt = _receipt(BLOCKED_FILLS, "428.64", mismatched)
        receipt["native_end_cash_usd"] = "90078.96"
        verdict = COMPARE.compare(receipt, ORACLE, TOLERANCES, MANIFEST, BARS)
        native = _check(verdict, "native_end_cash", "native_end_cash_usd")
        self.assertFalse(native["distribution_ledger_sum_matches"])
        self.assertIsNone(native["blocked_by"])

    def test_every_check_key_is_unique(self):
        verdict = COMPARE.compare(_receipt(BLOCKED_FILLS, "428.64", DISTRIBUTIONS), ORACLE,
                                  TOLERANCES, MANIFEST, BARS)
        keys = [c["key"] for c in verdict["checks"]]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual([c["ordinal"] for c in verdict["checks"]],
                         list(range(1, len(keys) + 1)))

    def test_a_mapping_the_manifest_does_not_declare_is_rejected(self):
        manifest = {"mappings": [dict(row, status="resolved") if row["id"] == "market_on_open_proxy"
                                 else row for row in MANIFEST["mappings"]]}
        verdict = COMPARE.compare(_receipt(BLOCKED_FILLS, "428.64", DISTRIBUTIONS), ORACLE,
                                  TOLERANCES, manifest, BARS)
        self.assertEqual(verdict["verdict"], "FAIL")
        self.assertIn("market_on_open_proxy", verdict["rejected_attributions"])

    def test_attribution_requires_the_oracle_to_be_the_bar_open(self):
        bars = [dict(BARS[0], o="300.0000"), BARS[1], BARS[2]]
        verdict = COMPARE.compare(_receipt(BLOCKED_FILLS, "428.64", DISTRIBUTIONS), ORACLE,
                                  TOLERANCES, MANIFEST, bars)
        self.assertIsNone(_check(verdict, "entry_fill", "fill_price_usd")["blocked_by"])
        self.assertEqual(verdict["verdict"], "FAIL")


class EventCoverageTests(unittest.TestCase):
    THIRD_ORACLE_FILL = {"utc_seconds": 1588258800, "quantity": 10,
                         "price": Decimal("292.00"), "fee": Decimal("0")}

    def test_extra_fill_beyond_the_oracle_count(self):
        fills = MATCHED_FILLS + [{"utc_seconds": 1588258800, "quantity": 10,
                                  "price": "292.00", "fee": "0"}]
        verdict = COMPARE.compare(_receipt(fills, "0", []), ORACLE_CLEAN, TOLERANCES, MANIFEST, BARS)
        failing = _failing(verdict)
        self.assertIn("extra_fills", failing)
        self.assertIn("fill_count", failing)
        self.assertEqual(_check(verdict, "missing_fills", "oracle_fills_absent")["status"], "PASS")

    def test_missing_fill_is_its_own_check(self):
        verdict = COMPARE.compare(_receipt(MATCHED_FILLS[:1], "0", []), ORACLE_CLEAN,
                                  TOLERANCES, MANIFEST, BARS)
        failing = _failing(verdict)
        self.assertIn("missing_fills", failing)
        self.assertEqual(_check(verdict, "extra_fills", "fills_beyond_oracle")["status"], "PASS")

    def test_every_event_is_compared_not_only_the_first_two(self):
        oracle = _oracle(ORACLE_CLEAN["fills"] + [self.THIRD_ORACLE_FILL], "0", "93225.44")
        fills = MATCHED_FILLS + [{"utc_seconds": 1588258800, "quantity": 10,
                                  "price": "999.00", "fee": "0"}]
        verdict = COMPARE.compare(_receipt(fills, "0", []), oracle, TOLERANCES, MANIFEST, BARS)
        self.assertIn("fill_3", _failing(verdict))
        self.assertEqual(_check(verdict, "fill_3", "fill_price_usd")["observed"], "999.00")


class ToleranceApplicationTests(unittest.TestCase):
    def test_every_declared_limit_is_actually_applied(self):
        tracking = _TrackingLimits(TOLERANCES)
        COMPARE.compare(_receipt(BLOCKED_FILLS, "428.64", DISTRIBUTIONS), ORACLE,
                        tracking, MANIFEST, BARS)
        self.assertEqual(tracking.used, set(TOLERANCES))
        self.assertEqual(set(TOLERANCES), set(COMPARE.REQUIRED_LIMITS))

    def test_intermediate_cash_uses_cash_usd_abs(self):
        receipt = _receipt(MATCHED_FILLS, "0", [])
        receipt["cash_ledger"][0]["cash"] = str(Decimal(receipt["cash_ledger"][0]["cash"])
                                                + Decimal("0.01"))
        inside = COMPARE.compare(receipt, ORACLE_CLEAN, TOLERANCES, MANIFEST, BARS)
        self.assertEqual(inside["failed"], 0)
        receipt["cash_ledger"][0]["cash"] = str(Decimal(receipt["cash_ledger"][0]["cash"])
                                                + Decimal("0.01"))
        outside = COMPARE.compare(receipt, ORACLE_CLEAN, TOLERANCES, MANIFEST, BARS)
        self.assertEqual(_failing(outside), ["cash_ledger[0]"])

    def test_end_cash_inside_and_outside_the_one_cent_allowance(self):
        inside = COMPARE.compare(_receipt(MATCHED_FILLS, "0", [],
                                          reconciled_end_cash_usd="90305.45"),
                                 ORACLE_CLEAN, TOLERANCES, MANIFEST, BARS)
        self.assertEqual(_failing(inside), [])
        outside = COMPARE.compare(_receipt(MATCHED_FILLS, "0", [],
                                           reconciled_end_cash_usd="90305.46"),
                                  ORACLE_CLEAN, TOLERANCES, MANIFEST, BARS)
        self.assertIn("end_cash", _failing(outside))

    def test_dividends_are_exact(self):
        verdict = COMPARE.compare(_receipt(BLOCKED_FILLS, "428.65", DISTRIBUTIONS), ORACLE,
                                  TOLERANCES, MANIFEST, BARS)
        self.assertIn("distributions_total", _failing(verdict))

    def test_tolerance_sheet_defaults_are_exact_except_cash(self):
        self.assertEqual({k: v for k, v in TOLERANCES.items() if Decimal(v) != 0},
                         {"cash_usd_abs": "0.01", "end_cash_usd_abs": "0.01"})


class OracleSchemaTests(unittest.TestCase):
    """Parse the real dated LEAN receipt, including its fragile decimal strings."""

    def setUp(self):
        self.oracle = json.loads(LEAN_RECEIPT.read_text())

    def test_projects_the_real_one_zero_case(self):
        case = COMPARE.oracle_case(self.oracle, "one_zero")
        self.assertEqual(case["intents"], [
            {"utc_seconds": 1577826000, "quantity": 304, "reason": "entry"},
            {"utc_seconds": 1588190400, "quantity": -304, "reason": "exit"}])
        self.assertEqual([(f["utc_seconds"], f["quantity"], f["price"]) for f in case["fills"]],
                         [(1577977200, 304, Decimal("323.58")),
                          (1588255200, -304, Decimal("291.69"))])
        self.assertEqual(case["dividends_usd"], Decimal("428.64"))
        self.assertEqual(case["end_cash_usd"], Decimal("90734.080"))
        self.assertEqual((case["fees_usd"], case["final_quantity"], case["fill_count"]),
                         (Decimal("0.0"), 0, 2))

    def test_every_published_case_projects(self):
        for case in self.oracle["cases"]:
            with self.subTest(case=case["id"]):
                self.assertEqual(COMPARE.oracle_case(self.oracle, case["id"])["id"], case["id"])

    def test_fragile_decimal_string_projection(self):
        self.assertEqual(COMPARE._int("1577977200.0", "non_integral_fill_time"), 1577977200)
        self.assertEqual(COMPARE._int("-304.0", "non_integral_fill_quantity"), -304)
        for value in ("304.5", "1577977200.25"):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "non_integral"):
                COMPARE._int(value, "non_integral_fill_quantity")

    def test_unknown_and_duplicate_cases_are_refused(self):
        with self.assertRaisesRegex(ValueError, "oracle_case_not_found:missing"):
            COMPARE.oracle_case(self.oracle, "missing")
        doubled = {"cases": self.oracle["cases"] + [self.oracle["cases"][0]]}
        with self.assertRaisesRegex(ValueError, "oracle_case_not_found:one_zero"):
            COMPARE.oracle_case(doubled, "one_zero")

    def test_inconsistent_oracle_fill_count_is_refused(self):
        case = dict(self.oracle["cases"][0], fill_count=3)
        with self.assertRaisesRegex(ValueError, "oracle_fill_count_inconsistent"):
            COMPARE.oracle_case({"cases": [case]}, "one_zero")

    def test_fractional_oracle_fill_time_is_refused_not_truncated(self):
        case = json.loads(json.dumps(self.oracle["cases"][0]))
        case["fills"][0]["time"] = "1577977200.5"
        with self.assertRaisesRegex(ValueError, "non_integral_fill_time"):
            COMPARE.oracle_case({"cases": [case]}, "one_zero")


class BindingTests(unittest.TestCase):
    def setUp(self):
        self.receipt = json.loads((SOURCE / "receipt.json").read_text())

    def test_bind_accepts_the_files_the_receipt_recorded(self):
        limits, manifest = COMPARE.bind(self.receipt, SOURCE / "tolerances.json",
                                        SOURCE / "mapping-manifest.json")
        self.assertEqual(set(limits), set(COMPARE.REQUIRED_LIMITS))
        self.assertEqual(manifest["case"], "one_zero")

    def test_bind_refuses_a_sheet_or_manifest_the_run_did_not_use(self):
        for key, code in (("tolerances", "tolerances_sha256_mismatch"),
                          ("mapping_manifest", "mapping_manifest_sha256_mismatch")):
            receipt = json.loads(json.dumps(self.receipt))
            receipt[key]["sha256"] = "0" * 64
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, code):
                COMPARE.bind(receipt, SOURCE / "tolerances.json", SOURCE / "mapping-manifest.json")

    def test_bind_pins_the_lean_oracle_receipt(self):
        oracle = ROOT / "blueprints/us-equities/historical-simulation/receipt.json"
        self.assertEqual(hashlib.sha256(oracle.read_bytes()).hexdigest(),
                         MANIFEST["oracle"]["receipt_sha256"])
        COMPARE.bind(self.receipt, SOURCE / "tolerances.json",
                     SOURCE / "mapping-manifest.json", oracle)
        with tempfile.TemporaryDirectory() as tmp:
            other = Path(tmp) / "receipt.json"
            other.write_text(oracle.read_text() + "\n")
            with self.assertRaisesRegex(ValueError, "oracle_receipt_sha256_mismatch"):
                COMPARE.bind(self.receipt, SOURCE / "tolerances.json",
                             SOURCE / "mapping-manifest.json", other)

    def test_bind_refuses_a_receipt_that_disagrees_with_the_manifest(self):
        cases = {
            "receipt_unsupported_mappings_disagree_with_manifest":
                {"unsupported_mappings": ["market_on_open_proxy"]},
            "engine_version_disagrees_with_manifest": {"engine": {"version": "2.0.0rc4"}},
            "evidence_class_disagrees_with_manifest": {"evidence_class": "SIM"},
        }
        for code, override in cases.items():
            receipt = json.loads(json.dumps(self.receipt))
            receipt.update(override)
            with self.subTest(code=code), self.assertRaisesRegex(ValueError, code):
                COMPARE.bind(receipt, SOURCE / "tolerances.json", SOURCE / "mapping-manifest.json")

    def test_bind_verifies_the_harness_files_on_disk(self):
        COMPARE.check_local_sources(self.receipt)
        for name in sorted(self.receipt["local_source_sha256"]):
            receipt = json.loads(json.dumps(self.receipt))
            receipt["local_source_sha256"][name] = "0" * 64
            with self.subTest(name=name), \
                    self.assertRaisesRegex(ValueError, "local_source_sha256_mismatch:" + name):
                COMPARE.check_local_sources(receipt)

    def test_bind_reports_a_missing_harness_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "local_source_missing:"):
                COMPARE.check_local_sources(self.receipt, Path(tmp))

    def test_bind_pins_the_frozen_plan_and_case_configuration(self):
        plan = ROOT / "blueprints/us-equities/historical-simulation/plan.json"
        self.assertEqual(hashlib.sha256(plan.read_bytes()).hexdigest(),
                         MANIFEST["oracle"]["plan_sha256"])
        COMPARE.bind(self.receipt, SOURCE / "tolerances.json", SOURCE / "mapping-manifest.json",
                     ROOT / "blueprints/us-equities/historical-simulation/receipt.json", plan)
        with tempfile.TemporaryDirectory() as tmp:
            other = Path(tmp) / "plan.json"
            other.write_text(plan.read_text() + "\n")
            with self.assertRaisesRegex(ValueError, "plan_sha256_mismatch"):
                COMPARE.bind(self.receipt, SOURCE / "tolerances.json",
                             SOURCE / "mapping-manifest.json", None, other)

    def test_case_configuration_must_match_the_plan_and_the_manifest(self):
        plan = json.loads((ROOT / "blueprints/us-equities/historical-simulation/plan.json").read_text())
        COMPARE.check_case_configuration(self.receipt, MANIFEST, plan)
        cases = {
            "case_configuration_disagrees_with_plan:initial_cash_usd": {"initial_cash_usd": "50000"},
            "case_configuration_disagrees_with_plan:target": {"target": "2"},
            "case_configuration_disagrees_with_plan:fee_usd": {"fee_usd": "1"},
            "case_configuration_disagrees_with_plan:sizing_buffer": {"sizing_buffer": "1.0"},
            "case_configuration_disagrees_with_manifest:seed": {"seed": 1},
            "case_configuration_disagrees_with_manifest:account_type": {"account_type": "MARGIN"},
            "case_configuration_disagrees_with_manifest:use_random_ids": {"use_random_ids": True},
        }
        for code, override in cases.items():
            receipt = json.loads(json.dumps(self.receipt))
            receipt["case_configuration"].update(override)
            with self.subTest(code=code), self.assertRaisesRegex(ValueError, re.escape(code)):
                COMPARE.check_case_configuration(receipt, MANIFEST, plan)

    def test_a_receipt_pointing_at_another_plan_is_refused(self):
        plan = json.loads((ROOT / "blueprints/us-equities/historical-simulation/plan.json").read_text())
        receipt = json.loads(json.dumps(self.receipt))
        receipt["frozen_plan"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "receipt_plan_sha256_disagrees_with_manifest"):
            COMPARE.check_case_configuration(receipt, MANIFEST, plan)

    def test_bind_refuses_a_sheet_with_unknown_or_missing_limits(self):
        with tempfile.TemporaryDirectory() as tmp:
            sheet = Path(tmp) / "tolerances.json"
            limits = dict(TOLERANCES)
            limits.pop("cash_usd_abs")
            sheet.write_text(json.dumps({"limits": limits, "status": "test"}))
            receipt = json.loads(json.dumps(self.receipt))
            receipt["tolerances"]["sha256"] = hashlib.sha256(sheet.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError, "tolerance_sheet_keys:cash_usd_abs"):
                COMPARE.bind(receipt, sheet, SOURCE / "mapping-manifest.json")


class AttributionEvidenceBindingTests(unittest.TestCase):
    """Attribution evidence is hash-bound; short sessions come from the manifest."""

    ROWS = [{"session_date": "2020-01-02", "local_start": "09:00",
             "ts_event_ns": ENTRY_FILL_TS * 10 ** 9, "o": "323.5800", "h": "324.0200",
             "l": "323.4100", "c": "323.8700", "v": 6498003}]

    def _receipt_for(self, blob: str):
        return {"attribution_evidence": {
            "converted_rows_sha256": hashlib.sha256(blob.encode("utf-8")).hexdigest()},
            "inputs": {"sha256": dict(CONVERT.FROZEN_INPUT_SHA256)},
            "case_configuration": {"window": {"symbol": "SPY", "start": "2019-12-02",
                                              "end": "2020-04-30"}}}

    def test_matching_bars_are_accepted_and_tampered_bars_refused(self):
        blob = COMPARE.serialize_rows(self.ROWS)
        receipt = self._receipt_for(blob)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "converted-rows.private.json"
            path.write_text(blob)
            self.assertEqual(COMPARE.load_bars(path, None, receipt, MANIFEST), self.ROWS)
            path.write_text(blob.replace("323.8700", "999.9900"))
            with self.assertRaisesRegex(ValueError, "converted_rows_sha256_mismatch"):
                COMPARE.load_bars(path, None, receipt, MANIFEST)

    def test_no_evidence_supplied_returns_none(self):
        self.assertIsNone(COMPARE.load_bars(
            None, None, self._receipt_for(COMPARE.serialize_rows(self.ROWS)), MANIFEST))

    def test_rederivation_verifies_the_frozen_inputs_before_use(self):
        receipt = self._receipt_for(COMPARE.serialize_rows(self.ROWS))
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "missing_input:"):
                COMPARE.load_bars(None, Path(tmp), receipt, MANIFEST)

    def test_serialization_matches_the_runner(self):
        self.assertEqual(COMPARE.serialize_rows(self.ROWS),
                         json.dumps(self.ROWS, indent=2, sort_keys=True, default=str) + "\n")

    def test_short_sessions_come_from_the_manifest_not_the_receipt(self):
        self.assertEqual(COMPARE.known_short_sessions(MANIFEST), {"2019-12-24": 4})
        self.assertEqual(COMPARE.known_short_sessions(MANIFEST),
                         RUN.known_short_sessions(MANIFEST))
        source = (SOURCE / "compare.py").read_text()
        self.assertNotIn('receipt.get("conversion"', source)
        self.assertNotIn('receipt["conversion"]', source)


class ProbeArtifactTests(unittest.TestCase):
    """The retained probe transcripts must match the manifest and its claims."""

    PROBES = SOURCE / "probes"

    def test_every_referenced_probe_artifact_hashes_as_recorded(self):
        recorded = MANIFEST["probes"]["artifacts"]
        # Files only: probes/v2/ belongs to the v2 preregistration and is checked below.
        self.assertEqual(sorted(recorded), sorted(p.name for p in self.PROBES.iterdir() if p.is_file()))
        for name, expected in recorded.items():
            with self.subTest(name=name):
                self.assertEqual(hashlib.sha256((self.PROBES / name).read_bytes()).hexdigest(),
                                 expected)

    def test_v2_preregistration_probe_artifacts_hash_as_recorded(self):
        manifest_v2 = json.loads((SOURCE / "mapping-manifest-v2.json").read_text())
        recorded = manifest_v2["probes"]["artifacts"]
        v2 = self.PROBES / "v2"
        self.assertEqual(sorted(recorded), sorted(p.name for p in v2.iterdir() if p.is_file()))
        for name, expected in recorded.items():
            with self.subTest(name=name):
                self.assertEqual(hashlib.sha256((v2 / name).read_bytes()).hexdigest(), expected)

    def test_at_the_open_transcript_carries_the_cited_rejection(self):
        transcript = json.loads((self.PROBES / "fill-semantics-atopen.json").read_text())
        reasons = [e["reason"] for e in transcript["events"] if e["event"] == "OrderRejected"]
        self.assertEqual(reasons, ["time in force AT_THE_OPEN is not currently supported"])
        self.assertEqual(transcript["fills"], [])
        self.assertEqual(transcript["engine_version"], MANIFEST["engine"]["version"])

    def test_pending_order_transcript_shows_a_close_fill_not_an_open_fill(self):
        for mode in ("plain", "on_start"):
            with self.subTest(mode=mode):
                transcript = json.loads((self.PROBES / ("fill-semantics-%s.json" % mode)).read_text())
                first = transcript["bar_specs"][0]
                self.assertEqual([f["avg_px"] for f in transcript["fills"]],
                                 ["%.2f" % first["close"]])
                self.assertNotEqual("%.2f" % first["open"], "%.2f" % first["close"])

    def test_dividend_scan_supports_the_manifest_claim(self):
        scan = json.loads((self.PROBES / "dividend-symbol-scan.json").read_text())
        row = next(m for m in MANIFEST["mappings"] if m["id"] == "distributions_and_cash")
        self.assertEqual(row["symbol_scan"]["source_matches"], scan["source_match_count"])
        self.assertEqual(row["symbol_scan"]["binary_matches"], scan["binary_match_count"])
        self.assertEqual(sorted(m["file"] + ":" + str(m["line"]) for m in scan["source_matches"]),
                         ["adapters/interactive_brokers/__init__.pyi:658",
                          "common/__init__.pyi:1164", "common/__init__.pyi:1208"])


class FixtureGuardTests(unittest.TestCase):
    def test_final_state_accepts_a_clean_run(self):
        self.assertIsNone(FIXTURE.check_final_state(None, 0, 0, Decimal(0)))

    def test_final_state_refusals(self):
        cases = {
            "unsubmitted_pending_intent:2": ({"order_ref": 2}, 0, 0, Decimal(0)),
            "open_orders_at_end:1": (None, 1, 0, Decimal(0)),
            "open_positions_at_end:1": (None, 0, 1, Decimal(0)),
            "nonflat_final_position:5": (None, 0, 0, Decimal(5)),
        }
        for code, args in cases.items():
            with self.subTest(code=code), self.assertRaisesRegex(ValueError, code):
                FIXTURE.check_final_state(*args)

    def test_run_integrity_surfaces_a_swallowed_callback_failure(self):
        self.assertIsNone(FIXTURE.check_run_integrity([], 725, 725, 725))
        with self.assertRaisesRegex(ValueError, "strategy_callback_failed:on_bar:ValueError: x"):
            FIXTURE.check_run_integrity(["on_bar:ValueError: x"], 725, 725, 725)
        with self.assertRaisesRegex(ValueError, "bars_not_fully_processed:3/725"):
            FIXTURE.check_run_integrity([], 3, 725, 725)
        with self.assertRaisesRegex(ValueError, "engine_iterations_mismatch:700"):
            FIXTURE.check_run_integrity([], 725, 725, 700)

    def test_commission_is_asserted_not_merely_recorded(self):
        self.assertIsNone(FIXTURE.assert_commission("0.00", "0", "USD", "USD"))
        with self.assertRaisesRegex(ValueError, "unexpected_commission:1.00"):
            FIXTURE.assert_commission("1.00", "0", "USD", "USD")
        with self.assertRaisesRegex(ValueError, "unexpected_commission_currency:EUR"):
            FIXTURE.assert_commission("0.00", "0", "EUR", "USD")


class UnsupportedMappingSourceTests(unittest.TestCase):
    def test_runner_derives_the_list_from_the_manifest(self):
        self.assertEqual(RUN.unsupported_mappings(MANIFEST),
                         sorted(m["id"] for m in MANIFEST["mappings"]
                                if m["status"] == "unsupported"))
        self.assertEqual(RUN.unsupported_mappings(MANIFEST),
                         ["distributions_and_cash", "market_on_open_proxy"])

    def test_published_receipt_agrees_with_the_manifest(self):
        receipt = json.loads((SOURCE / "receipt.json").read_text())
        self.assertEqual(receipt["unsupported_mappings"], RUN.unsupported_mappings(MANIFEST))
        self.assertEqual(receipt["mapping_manifest"]["sha256"],
                         hashlib.sha256((SOURCE / "mapping-manifest.json").read_bytes()).hexdigest())

    def test_a_changed_status_changes_the_derived_list(self):
        altered = {"mappings": [dict(row, status="resolved")
                                if row["id"] == "distributions_and_cash" else row
                                for row in MANIFEST["mappings"]]}
        self.assertEqual(RUN.unsupported_mappings(altered), ["market_on_open_proxy"])


class ManifestTests(unittest.TestCase):
    def test_every_section_two_mapping_row_has_a_resolved_status(self):
        manifest = json.loads((SOURCE / "mapping-manifest.json").read_text())
        rows = {m["id"]: m for m in manifest["mappings"]}
        self.assertEqual(sorted(rows), [
            "costs_and_rounding", "decision_visibility", "distributions_and_cash",
            "instrument_identity", "margin_and_adaptive_state", "market_on_open_proxy",
            "raw_data_decoding", "sessions_and_time",
        ])
        for name, row in rows.items():
            with self.subTest(mapping=name):
                self.assertIn(row["status"], ("resolved", "unsupported", "blocked"))
                self.assertTrue(row.get("decision"))
                self.assertTrue(row.get("limitations"))


if __name__ == "__main__":
    unittest.main()
