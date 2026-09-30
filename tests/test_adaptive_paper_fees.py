"""Broker FEE activities in the adaptive-paper engine (trading-lane brief, 2026-09-30).

Every account 2 recover attempt ended cash_mismatch_or_unmodeled_fees: three paper FEE
activities for 2026-09-29 sells (REG -0.19, TAF -0.27, CAT -0.01 USD) the engine did not
model. These tests cover the allow-listed transport read and its normalization, the
snapshot's fee list, the ledger's schema-3 fee record, reconciliation, runner.main's
next-trial check, each lane's fee window and the mover receipts.

Local synthetic fixtures only: no credentials, broker requests or network. Activity ids
are built at runtime, as in test_adaptive_paper_transport.py (no literal UUID in
published files).
"""
from __future__ import annotations

import asyncio
from contextlib import nullcontext
from datetime import datetime, timezone
from decimal import Decimal as D
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock, patch
import uuid

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "blueprints/us-equities/adaptive-paper"
sys.path.insert(0, str(SOURCE))

import mover_runner  # noqa: E402
import runner as runner_module  # noqa: E402
import safety  # noqa: E402
import transport as t  # noqa: E402
from safety import Ledger, RiskLimits, SafetyError  # noqa: E402

try:
    import alpaca  # noqa: F401
    import requests
    HAS_SDK = True
except ImportError:
    HAS_SDK = False

try:
    import nautilus_trader  # noqa: F401
    import mover
    import native_adapter
    from mover_simulation import MoverSimulatedPort, piecewise_path
    NATIVE = HAS_SDK
except ImportError:
    NATIVE = False

try:  # package mode (python -m unittest tests.x) or discover -s tests (top-level modules)
    from .adaptive_paper_hermetic import patch_default_stop, restore_default_stop
except ImportError:
    from adaptive_paper_hermetic import patch_default_stop, restore_default_stop  # noqa: E402

_HERMETIC_TOKEN = None


def setUpModule():
    global _HERMETIC_TOKEN
    _HERMETIC_TOKEN = patch_default_stop()


def tearDownModule():
    restore_default_stop(_HERMETIC_TOKEN)


# The description of a FEE activity carries the account number; this stands in for it.
ACCOUNT_TEXT = "fixture-description-with-the-account-number"
# The three FEE activities measured on account 2 for 2026-09-29 sells (brief, 2026-09-30).
MEASURED = (("REG", "-0.19"), ("TAF", "-0.27"), ("CAT", "-0.01"))
# An instant of the adaptive lane's first trial (trial.json started_at).
T0 = 1_790_000_000.0


def activity_id(index, stamp="20260930040000"):
    """A documented "<timestamp>::<uuid>" activity id, built at runtime."""
    return "%s%03d::%s" % (stamp, index, uuid.UUID(int=0xFEE0000 + index))


def fee_row(index=0, sub_type="REG", amount="-0.19", **changes):
    """One raw NonTradeActivity of activity_type FEE, shaped like the by-type reference's example."""
    row = {"activity_type": "FEE", "activity_sub_type": sub_type, "id": activity_id(index),
           "date": "2026-09-29", "net_amount": amount, "currency": "USD", "status": "executed",
           "created_at": "2026-09-30T04:00:00.123456Z", "description": ACCOUNT_TEXT}
    row.update(changes)
    return row


def measured_rows():
    return [fee_row(i, sub_type, amount) for i, (sub_type, amount) in enumerate(MEASURED)]


def measured_fees():
    """What transport.normalize_fee_activity returns for measured_rows()."""
    return [{"id": activity_id(i), "date": "2026-09-29", "net_amount": amount, "sub_type": sub_type}
            for i, (sub_type, amount) in enumerate(MEASURED)]


def response(payload=None, status=200):
    value = requests.Response()
    value.status_code = status
    value._content = json.dumps(payload).encode() if payload is not None else b""
    return value


def utc(epoch):
    return datetime.fromtimestamp(epoch, timezone.utc)


# ---------------------------------------------------------------------------
# Item 2: normalization
# ---------------------------------------------------------------------------

class FeeNormalization(unittest.TestCase):
    def test_documented_fee_row_keeps_four_fields_and_never_the_description(self):
        for row, expected in zip(measured_rows(), measured_fees()):
            with self.subTest(sub_type=expected["sub_type"]):
                result = t.normalize_fee_activity(row)
                self.assertEqual(result, expected)
                self.assertNotIn(ACCOUNT_TEXT, json.dumps(result))

    def test_every_documented_fee_sub_type_and_an_absent_or_null_one(self):
        for sub_type in ("REG", "TAF", "LCT", "ORF", "OCC", "NRC", "NRV", "COM", "CAT"):
            with self.subTest(sub_type=sub_type):
                self.assertEqual(t.normalize_fee_activity(fee_row(sub_type=sub_type))["sub_type"], sub_type)
        absent = fee_row()
        del absent["activity_sub_type"]
        self.assertEqual(t.normalize_fee_activity(absent)["sub_type"], "UNSPECIFIED")
        self.assertEqual(t.normalize_fee_activity(fee_row(sub_type=None))["sub_type"], "UNSPECIFIED")

    def test_currency_and_status_may_be_absent(self):
        row = fee_row()
        del row["currency"], row["status"], row["description"], row["created_at"]
        self.assertEqual(t.normalize_fee_activity(row), measured_fees()[0])

    def test_a_credit_and_trailing_zeros(self):
        self.assertEqual(t.normalize_fee_activity(fee_row(amount="0.05"))["net_amount"], "0.05")
        self.assertEqual(t.normalize_fee_activity(fee_row(amount="-0.270"))["net_amount"], "-0.27")

    def test_anything_else_fails_closed_without_provider_text(self):
        def without(key):
            row = fee_row()
            del row[key]
            return row
        cases = {
            "div": fee_row(activity_type="DIV"), "csw": fee_row(activity_type="CSW"),
            "fill": fee_row(activity_type="FILL"), "lowercase_type": fee_row(activity_type="fee"),
            "no_type": without("activity_type"),
            "bad_id": fee_row(id="20260930::not-a-uuid"), "uuid_only_id": fee_row(id=str(uuid.UUID(int=7))),
            "int_id": fee_row(id=7), "no_id": without("id"),
            "text_amount": fee_row(amount="abc"), "nan": fee_row(amount="NaN"), "infinite": fee_row(amount="-Infinity"),
            "empty_amount": fee_row(amount=""), "null_amount": fee_row(amount=None), "float_amount": fee_row(amount=-0.19),
            "bool_amount": fee_row(amount=True), "no_amount": without("net_amount"),
            "timestamp_date": fee_row(date="2026-09-29T00:00:00Z"), "slash_date": fee_row(date="2026/09/29"),
            "impossible_date": fee_row(date="2026-02-30"), "null_date": fee_row(date=None), "no_date": without("date"),
            "unknown_sub_type": fee_row(sub_type="XYZ"), "lowercase_sub_type": fee_row(sub_type="reg"),
            "dividend_sub_type": fee_row(sub_type="CDIV"), "numeric_sub_type": fee_row(sub_type=5),
            "empty_sub_type": fee_row(sub_type=""),
            "euro": fee_row(currency="EUR"), "null_currency": fee_row(currency=None),
            "correction": fee_row(status="correct"), "canceled": fee_row(status="canceled"),
            "null_status": fee_row(status=None),
            "not_a_dict": ["FEE"], "none": None}
        for label, row in cases.items():
            with self.subTest(label=label):
                with self.assertRaises(t.TransportError) as caught:
                    t.normalize_fee_activity(row)
                self.assertNotIn(ACCOUNT_TEXT, str(caught.exception))


# ---------------------------------------------------------------------------
# Item 1: the one allow-listed read
# ---------------------------------------------------------------------------

AFTER = "2026-09-29T08:00:00Z"


@unittest.skipUnless(HAS_SDK, "requires isolated reviewed alpaca-py runtime")
class FeeHTTPBoundary(unittest.TestCase):
    def setUp(self):
        self.budget = Mock(return_value=None)
        self.session = t.GuardedSession(origin=t.PAPER_URL, before_request=self.budget)
        self.addCleanup(self.session.close)

    def test_the_fee_read_is_allowed_only_after_one_utc_instant_and_is_a_budgeted_read(self):
        url = t.PAPER_URL + t.ACTIVITY_FEE_PATH
        self.assertEqual(t.ACTIVITY_FEE_PATH, "/v2/account/activities/FEE")
        allowed = [{"after": AFTER, "direction": "asc"},
                   {"after": AFTER, "direction": "asc", "page_size": 100},
                   {"after": AFTER, "direction": "asc", "page_size": 1, "page_token": activity_id(1)}]
        with patch.object(self.session._session, "request", return_value=response([])) as request:
            for params in allowed:
                self.session.request("GET", url, params=params)
        self.assertEqual(request.call_count, 3)
        self.assertEqual([c.args[0] for c in self.budget.call_args_list], ["read"] * 3)

    def test_every_other_path_parameter_or_method_is_refused_before_the_budget(self):
        url = t.PAPER_URL + t.ACTIVITY_FEE_PATH
        good = {"after": AFTER, "direction": "asc"}
        refused = [
            ("GET", t.PAPER_URL + "/v2/account/activities", good),
            ("GET", t.PAPER_URL + "/v2/account/activities/DIV", good),
            ("GET", t.PAPER_URL + "/v2/account/activities/CSW", good),
            ("GET", t.PAPER_URL + "/v2/account/activities/fee", good),
            ("GET", url + "/", good),
            ("GET", t.PAPER_URL + t.ACTIVITY_FILL_PATH, good),
            ("GET", url + "?after=" + AFTER + "&direction=asc", None),
            ("GET", url, None), ("GET", url, {}),
            ("GET", url, {"direction": "asc"}),
            ("GET", url, {"after": AFTER}),
            ("GET", url, {**good, "after": "2026-09-29"}),
            ("GET", url, {**good, "after": "2026-09-29T08:00:00.5Z"}),
            ("GET", url, {**good, "after": "2026-09-29T08:00:00+00:00"}),
            ("GET", url, {**good, "after": "2026-09-29t08:00:00z"}),
            ("GET", url, {**good, "after": "2026-13-40T25:61:61Z"}),
            ("GET", url, {**good, "after": 1790000000}),
            ("GET", url, {**good, "direction": "desc"}),
            ("GET", url, {**good, "page_size": 0}), ("GET", url, {**good, "page_size": 101}),
            ("GET", url, {**good, "page_size": "100"}), ("GET", url, {**good, "page_size": True}),
            ("GET", url, {**good, "page_token": "not::a-token"}), ("GET", url, {**good, "page_token": 5}),
            ("GET", url, {**good, "until": AFTER}), ("GET", url, {**good, "date": "2026-09-30"}),
            ("GET", url, {**good, "order_id": str(uuid.UUID(int=1))}),
            ("GET", url, {**good, "activity_types": "FEE"}),
            ("GET", url, {**good, "category": "non_trade_activity"}),
            ("POST", url, good), ("DELETE", url, good)]
        with patch.object(self.session._session, "request") as request:
            for method, target, params in refused:
                with self.subTest(method=method, url=target, params=params), self.assertRaises(t.TransportError):
                    self.session.request(method, target, params=params)
        request.assert_not_called()
        self.budget.assert_not_called()


# ---------------------------------------------------------------------------
# Item 3: the snapshot's fee list (and the standalone read item 7 uses)
# ---------------------------------------------------------------------------

HISTORY = datetime(2026, 9, 28, 12, 0, 0, 250000, tzinfo=timezone.utc)     # the lane's first trial
BASELINE = datetime(2026, 9, 29, 8, 0, 0, 750000, tzinfo=timezone.utc)     # this trial's cash baseline
FEE_PATH = "/v2/account/activities/FEE"


@unittest.skipUnless(HAS_SDK, "requires isolated reviewed alpaca-py runtime")
class FeeSnapshot(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.budgets = []
        self.port = self.make_port(fee_history_start=BASELINE)

    async def asyncTearDown(self):
        await self.port.stop()

    def make_port(self, **kwargs):
        def budget(kind, client_id=None):
            self.budgets.append(kind)
        port = t.AlpacaPaperTransport("fixture-key", "fixture-secret", ["SPY"], before_request=budget,
                                      before_submit=lambda intent: None, sink_observation=lambda order: None,
                                      history_start=HISTORY, **kwargs)
        port._loop = asyncio.get_running_loop()
        return port

    async def replace_port(self, **kwargs):
        await self.port.stop()
        self.port = self.make_port(**kwargs)

    def serve(self, fee_pages):
        pages, calls = list(fee_pages), []

        def request(method, url, **kwargs):
            path = t.urlsplit(url).path
            calls.append((method, path, kwargs.get("params")))
            if path == "/v2/account":
                return response({"cash": "1000", "equity": "1000", "buying_power": "1000"})
            if path in ("/v2/positions", "/v2/orders"):
                return response([])
            if path == FEE_PATH:
                page = pages.pop(0)
                return page if isinstance(page, requests.Response) else response(page)
            raise AssertionError("unexpected request " + path)
        return request, calls

    async def snapshot(self, fee_pages):
        request, calls = self.serve(fee_pages)
        with patch.object(self.port._client._session._session, "request", side_effect=request):
            return await self.port.snapshot(), calls

    async def test_snapshot_lists_the_fees_created_after_the_fee_window_oldest_first(self):
        snapshot, calls = await self.snapshot([measured_rows()])
        self.assertEqual(snapshot["fees"], measured_fees())
        self.assertEqual([c for c in calls if c[1] == FEE_PATH],
                         [("GET", FEE_PATH, {"after": "2026-09-29T08:00:00Z", "direction": "asc", "page_size": 100})])
        # The order history keeps its own window; the fees are read last, after the account's cash.
        self.assertEqual([c[2]["after"] for c in calls if c[1] == "/v2/orders" and c[2].get("status") == "all"],
                         [HISTORY.isoformat()])
        self.assertEqual(calls[-1][1], FEE_PATH)
        self.assertEqual(set(self.budgets), {"read"})
        self.assertEqual(snapshot["fee_history_start"], BASELINE.isoformat())
        self.assertNotIn(ACCOUNT_TEXT, json.dumps(snapshot, default=str))

    async def test_the_fee_window_defaults_to_the_history_start(self):
        await self.replace_port()
        snapshot, calls = await self.snapshot([[]])
        self.assertEqual(snapshot["fees"], [])
        self.assertEqual([c[2]["after"] for c in calls if c[1] == FEE_PATH], ["2026-09-28T12:00:00Z"])

    async def test_fee_pages_continue_from_the_last_activity_id(self):
        first = [fee_row(i, "TAF", "-0.01") for i in range(100)]
        second = [fee_row(100, "CAT", "-0.01")]
        snapshot, calls = await self.snapshot([first, second])
        self.assertEqual(len(snapshot["fees"]), 101)
        self.assertEqual([f["id"] for f in snapshot["fees"]], [row["id"] for row in first + second])
        self.assertEqual([c[2] for c in calls if c[1] == FEE_PATH][1],
                         {"after": "2026-09-29T08:00:00Z", "direction": "asc", "page_size": 100,
                          "page_token": first[-1]["id"]})

    async def test_a_full_page_at_the_bound_is_incomplete_not_an_empty_list(self):
        self.port.max_snapshot_pages = 1
        request, _ = self.serve([[fee_row(i, "TAF", "-0.01") for i in range(100)]])
        with patch.object(self.port._client._session._session, "request", side_effect=request):
            with self.assertRaisesRegex(t.TransportError, "snapshot incomplete"):
                await self.port.snapshot()
        self.assertIn("snapshot_incomplete", self.port.health["reasons"])

    async def test_a_failed_or_malformed_fee_read_freezes_instead_of_listing_no_fees(self):
        cases = {"http_500": [response({"code": 50010000, "message": "fixture"}, 500)],
                 "not_a_list": [{"activities": []}],
                 "dividend_row": [[fee_row(activity_type="DIV")]],
                 "withdrawal_row": [[fee_row(activity_type="CSW")]],
                 "duplicate_id": [[fee_row(0), fee_row(0)]],
                 "repeated_across_pages": [[fee_row(i, "TAF", "-0.01") for i in range(100)], [fee_row(0)]],
                 "oversized_page": [[fee_row(i, "TAF", "-0.01") for i in range(101)]]}
        for label, pages in cases.items():
            with self.subTest(label=label):
                await self.replace_port(fee_history_start=BASELINE)
                request, _ = self.serve(pages)
                with patch.object(self.port._client._session._session, "request", side_effect=request):
                    with self.assertRaisesRegex(t.TransportError, "snapshot incomplete"):
                        await self.port.snapshot()
                self.assertIn("snapshot_incomplete", self.port.health["reasons"])

    async def test_a_naive_fee_history_start_is_refused(self):
        with self.assertRaises(t.TransportError):
            self.make_port(fee_history_start=datetime(2026, 9, 29, 8, 0))

    async def test_fee_activities_reads_through_a_fresh_allow_listed_session(self):
        budgets = []
        request, calls = self.serve([measured_rows()])
        with patch("requests.Session.request", side_effect=request):
            fees = t.fee_activities("fixture-key", "fixture-secret", after=BASELINE,
                                    before_request=lambda kind, **kwargs: budgets.append(kind))
        self.assertEqual(fees, measured_fees())
        self.assertEqual(budgets, ["read"])
        self.assertEqual(calls, [("GET", FEE_PATH, {"after": "2026-09-29T08:00:00Z", "direction": "asc",
                                                    "page_size": 100})])
        with patch("requests.Session.request") as sent:
            with self.assertRaises(t.TransportError):
                t.fee_activities("fixture-key", "fixture-secret", after=datetime(2026, 9, 29),
                                 before_request=budgets.append)
        sent.assert_not_called()


# ---------------------------------------------------------------------------
# Item 5: the ledger (schema 3)
# ---------------------------------------------------------------------------

class FeeLedger(unittest.TestCase):
    NOW = 1_790_000_000.0

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "ledger.sqlite3"
        self.ledger = Ledger(self.path)
        self.addCleanup(lambda: self.ledger.close())

    def reopen(self):
        self.ledger.close()
        self.ledger = Ledger(self.path)

    def dump(self):
        return tuple(self.ledger.db.iterdump())

    def schema_version(self):
        return self.ledger.db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0]

    def has_fees_table(self, db=None):
        return (db or self.ledger.db).execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='fees'").fetchone() is not None

    def test_a_new_ledger_is_schema_3_with_the_fees_table(self):
        self.assertEqual(self.schema_version(), "3")
        columns = [(r[1], r[2], r[3], r[5]) for r in self.ledger.db.execute("PRAGMA table_info(fees)")]
        self.assertEqual(columns, [("activity_id", "TEXT", 0, 1), ("date", "TEXT", 1, 0),
                                   ("net_amount", "TEXT", 1, 0), ("sub_type", "TEXT", 1, 0),
                                   ("recorded_at", "REAL", 1, 0)])

    def test_schema_2_1_and_unversioned_ledgers_migrate_to_3(self):
        for version in ("2", "1", None):
            with self.subTest(version=version):
                self.ledger.db.execute("DROP TABLE fees")
                if version is None:
                    self.ledger.db.execute("DELETE FROM meta WHERE key='schema_version'")
                else:
                    self.ledger.db.execute("UPDATE meta SET value=? WHERE key='schema_version'", (version,))
                if version in ("1", None):
                    self.ledger.db.execute("ALTER TABLE executions DROP COLUMN execution_time_ns")
                self.reopen()
                self.assertEqual(self.schema_version(), "3")
                self.assertTrue(self.has_fees_table())
                self.reopen()                                   # a migrated ledger opens unchanged
                self.assertEqual(self.schema_version(), "3")
        self.assertEqual(self.ledger.record_fees(measured_fees(), self.NOW), measured_fees())

    def test_any_other_schema_version_is_refused_before_any_change(self):
        for version in ("4", "0", "3.0", ""):
            with self.subTest(version=version):
                self.ledger.db.execute("DROP TABLE IF EXISTS fees")
                self.ledger.db.execute("UPDATE meta SET value=? WHERE key='schema_version'", (version,))
                self.ledger.close()
                with self.assertRaisesRegex(SafetyError, "^unsupported_ledger_schema$"):
                    Ledger(self.path)
                with sqlite3.connect(self.path) as raw:
                    self.assertFalse(self.has_fees_table(raw))
                    self.assertEqual(raw.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0],
                                     version)
                    raw.execute("UPDATE meta SET value='2' WHERE key='schema_version'")
                raw.close()
                self.ledger = Ledger(self.path)

    def test_the_previous_engine_refuses_a_migrated_ledger(self):
        # The exact open check of Ledger.__init__ at 11227bfd (this change's base), before any insert.
        version = self.schema_version()
        with self.assertRaisesRegex(SafetyError, "^unsupported_ledger_schema$"):
            if version not in (None, "1", "2"):
                raise SafetyError("unsupported_ledger_schema")

    def test_record_fees_books_cash_realized_and_loss_once_with_one_event_each(self):
        self.assertEqual(self.ledger.record_fees(measured_fees(), self.NOW), measured_fees())
        state = self.ledger.accounting()
        self.assertEqual((state.cash_delta_usd, state.realized_pnl_usd, state.cumulative_realized_loss_usd,
                          state.gross_loss_usd, state.peak_pnl_usd, state.drawdown_usd),
                         (D("-0.47"), D("-0.47"), D("0.47"), D("0.47"), D("0"), D("0.47")))
        self.assertEqual([(r["activity_id"], r["date"], r["net_amount"], r["sub_type"], r["recorded_at"])
                          for r in self.ledger.fees()],
                         [(f["id"], f["date"], D(f["net_amount"]), f["sub_type"], self.NOW) for f in measured_fees()])
        events = [json.loads(r[0]) for r in self.ledger.db.execute(
            "SELECT payload FROM events WHERE kind='fee_recorded' ORDER BY id")]
        self.assertEqual(events, [{"activity_id": f["id"], "date": f["date"], "net_amount": f["net_amount"],
                                   "sub_type": f["sub_type"]} for f in measured_fees()])

    def test_re_recording_known_fees_changes_nothing(self):
        self.ledger.record_fees(measured_fees(), self.NOW)
        before = self.dump()
        self.assertEqual(self.ledger.record_fees(measured_fees(), self.NOW + 60), [])
        self.assertEqual(self.ledger.record_fees(list(reversed(measured_fees()))[:2], self.NOW + 120), [])
        same_value = dict(measured_fees()[0], net_amount="-0.190")
        self.assertEqual(self.ledger.record_fees([same_value], self.NOW + 150), [])
        self.assertEqual(self.ledger.record_fees([], self.NOW + 180), [])
        self.assertEqual(self.dump(), before)

    def test_a_changed_fee_activity_is_refused_and_the_whole_batch_rolls_back(self):
        known, fresh = measured_fees()[:2]
        self.ledger.record_fees([known], self.NOW)
        before = self.dump()
        for change in ({"net_amount": "-0.20"}, {"date": "2026-09-30"}, {"sub_type": "TAF"},
                       {"sub_type": "UNSPECIFIED"}):
            with self.subTest(change=change):
                with self.assertRaisesRegex(SafetyError, "^fee_activity_changed$"):
                    self.ledger.record_fees([fresh, dict(known, **change)], self.NOW + 60)
                self.assertEqual(self.dump(), before)

    def test_a_fee_credit_raises_realized_and_the_peak_but_never_lowers_the_loss(self):
        credit = {"id": activity_id(9), "date": "2026-09-29", "net_amount": "0.10", "sub_type": "UNSPECIFIED"}
        self.ledger.record_fees([credit], self.NOW)
        state = self.ledger.accounting()
        self.assertEqual((state.realized_pnl_usd, state.cumulative_realized_loss_usd, state.peak_pnl_usd,
                          state.cash_delta_usd), (D("0.10"), D("0"), D("0.10"), D("0.10")))
        self.ledger.record_fees(measured_fees(), self.NOW + 1)
        state = self.ledger.accounting()
        self.assertEqual((state.realized_pnl_usd, state.cumulative_realized_loss_usd, state.peak_pnl_usd,
                          state.drawdown_usd), (D("-0.37"), D("0.47"), D("0.10"), D("0.47")))

    def test_fees_count_against_the_gross_loss_budget(self):
        ledger = Ledger(Path(self.tmp.name) / "tight.sqlite3", RiskLimits(max_gross_loss_usd=D("0.40")))
        self.addCleanup(ledger.close)
        self.assertIsNone(ledger.halted_reason())
        ledger.record_fees(measured_fees(), self.NOW)
        self.assertEqual(ledger.halted_reason(), "gross_loss_cap_reached")

    def test_malformed_fee_rows_are_refused_before_any_write(self):
        before = self.dump()
        good = measured_fees()[0]
        cases = {"not_a_list": good, "none": None, "text": "fees", "row_not_a_dict": [["x"]],
                 "missing_key": [{k: v for k, v in good.items() if k != "sub_type"}],
                 "description_key": [dict(good, description=ACCOUNT_TEXT)],
                 "bad_id": [dict(good, id="7")], "bad_date": [dict(good, date="2026-9-29")],
                 "impossible_date": [dict(good, date="2026-02-30")], "text_amount": [dict(good, net_amount="abc")],
                 "exponent_amount": [dict(good, net_amount="-1E-2")], "plus_amount": [dict(good, net_amount="+0.19")],
                 "ten_decimals": [dict(good, net_amount="-0.0000000001")],
                 "eleven_digits": [dict(good, net_amount="-10000000000")],
                 "float_amount": [dict(good, net_amount=-0.19)], "unknown_sub_type": [dict(good, sub_type="XYZ")],
                 "null_sub_type": [dict(good, sub_type=None)],
                 "one_bad_row_in_a_batch": [measured_fees()[1], dict(good, sub_type="CDIV")]}
        for label, fees in cases.items():
            with self.subTest(label=label):
                with self.assertRaises(SafetyError):
                    self.ledger.record_fees(fees, self.NOW)
                self.assertEqual(self.dump(), before)
        with self.assertRaises(SafetyError):
            self.ledger.record_fees(measured_fees(), float("nan"))
        self.assertEqual(self.dump(), before)

    def test_rederived_accounting_keeps_recorded_fees_next_to_symbol_money(self):
        self.ledger.start_trial(self.NOW)
        quote = safety.Quote("SPY", "100", "100.01", self.NOW)
        self.ledger.reserve_intent("buy-1", "SPY", "buy", "1", "100.02", quote=quote, now=self.NOW, market_open=True,
                                   session_close=self.NOW + 3600, stop_file=Path(self.tmp.name) / "STOP")
        self.ledger.record_order("buy-1", "broker-buy-1", "filled", "1", "100", timestamp=self.NOW)
        self.ledger.record_fees(measured_fees(), self.NOW + 1)
        expected = (D("-100.47"), D("-0.47"), D("0.47"))
        state = self.ledger.accounting()
        self.assertEqual((state.cash_delta_usd, state.realized_pnl_usd, state.cumulative_realized_loss_usd), expected)
        self.ledger.db.execute("DELETE FROM meta WHERE key='execution_accounting:rule'")
        self.reopen()                                           # the open-time re-derivation runs
        state = self.ledger.accounting()
        self.assertEqual((state.cash_delta_usd, state.realized_pnl_usd, state.cumulative_realized_loss_usd), expected)


# ---------------------------------------------------------------------------
# Items 6 and 8: reconciliation
# ---------------------------------------------------------------------------

class FeeReconciliation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ledger = self.new_ledger("ledger")

    def new_ledger(self, name):
        ledger = Ledger(Path(self.tmp.name) / (name + ".sqlite3"))
        self.addCleanup(ledger.close)
        return ledger

    @staticmethod
    def snapshot(cash, fees=None):
        value = {"complete": True, "orders": [], "positions": [], "account": {"cash": cash}}
        if fees is not None:
            value["fees"] = fees
        return value

    def test_the_measured_gap_fails_without_fees_and_reconciles_with_the_three_rows(self):
        for fees in (None, []):
            with self.subTest(fees=fees), self.assertRaisesRegex(SafetyError, "^cash_mismatch_or_unmodeled_fees$"):
                runner_module.reconcile(self.ledger, self.snapshot("99999.53", fees), "100000")
        proof = runner_module.reconcile(self.ledger, self.snapshot("99999.53", measured_fees()), "100000")
        self.assertEqual((proof["cash_match"], proof["cash_delta_usd"]), (True, "-0.47"))
        self.assertEqual([f["activity_id"] for f in self.ledger.fees()], [f["id"] for f in measured_fees()])
        self.assertEqual(runner_module.reconcile(self.ledger, self.snapshot("99999.53", measured_fees()), "100000"),
                         proof)
        self.assertEqual(len(self.ledger.fees()), 3)
        self.assertEqual(self.ledger.accounting().cash_delta_usd, D("-0.47"))

    def test_a_snapshot_without_the_fees_key_behaves_as_before(self):
        before = tuple(self.ledger.db.iterdump())
        proof = runner_module.reconcile(self.ledger, self.snapshot("100000"), "100000")
        self.assertEqual(proof, {"positions_match": True, "cash_match": True, "cash_delta_usd": "0",
                                 "open_orders": 0, "positions": 0})
        self.assertEqual(tuple(self.ledger.db.iterdump()), before)

    def test_other_account_activity_still_fails_closed(self):
        # A dividend credit, a cash withdrawal or a cash journal beside the recorded fees stays unexplained.
        for label, cash in (("DIV", "100000.55"), ("CSW", "99899.53"), ("JNLC", "99999.00")):
            with self.subTest(activity=label), self.assertRaisesRegex(SafetyError, "^cash_mismatch_or_unmodeled_fees$"):
                runner_module.reconcile(self.ledger, self.snapshot(cash, measured_fees()), "100000")
        self.assertEqual(self.ledger.accounting().cash_delta_usd, D("-0.47"))   # the fees themselves are recorded
        # A non-FEE activity can never be passed off as a fee: the ledger refuses its sub-type.
        dividend = {"id": activity_id(5), "date": "2026-09-29", "net_amount": "1.02", "sub_type": "CDIV"}
        with self.assertRaises(SafetyError):
            runner_module.reconcile(self.new_ledger("dividend"), self.snapshot("100001.02", [dividend]), "100000")

    def test_a_fee_the_per_trial_baseline_already_holds_must_not_reach_reconcile(self):
        # Why the mover's fee window is its own trial's start, not the lane's started_at: trial 1 ended flat
        # at broker cash 100000 (ledger cash_delta 0); overnight the day's three fees posted (cash 99999.53);
        # command_paper then recomputed trial 2's baseline as preflight cash minus the ledger's cash_delta
        # (mover_runner.py), which already holds them. Handing trial 2 those fees again double counts.
        baseline = format(D("99999.53") - self.ledger.accounting().cash_delta_usd, "f")
        with self.assertRaisesRegex(SafetyError, "^cash_mismatch_or_unmodeled_fees$"):
            runner_module.reconcile(self.ledger, self.snapshot("99999.53", measured_fees()), baseline)
        fresh = self.new_ledger("windowed")
        baseline = format(D("99999.53") - fresh.accounting().cash_delta_usd, "f")
        self.assertTrue(runner_module.reconcile(fresh, self.snapshot("99999.53", []), baseline)["cash_match"])

    def test_mover_reconcile_records_fees_through_runner_reconcile(self):
        proof = mover_runner.mover_reconcile(self.ledger, self.snapshot("99999.53", measured_fees()), "100000")
        self.assertTrue(proof["cash_match"])
        self.assertEqual(len(self.ledger.fees()), 3)


# ---------------------------------------------------------------------------
# Items 4 and 7: runner.main (adaptive lane): fee window and next-trial check
# ---------------------------------------------------------------------------

def paper_ready_observation(now_ns, symbols=("SPY",)):
    """The shape test_adaptive_paper_runner.py's _paper_ready_observation uses."""
    return {"account": {"status": "ACTIVE", "currency": "USD", "cash": "10000", "equity": "30000",
                        "trading_blocked": False, "account_blocked": False, "trade_suspended_by_user": False},
            "clock": {"timestamp_ns": now_ns, "received_at_ns": now_ns, "next_close_ns": now_ns + 3600_000_000_000,
                      "is_open": True},
            "positions": [], "orders": [],
            "assets": [{"symbol": s, "status": "active", "tradable": True} for s in symbols],
            "quotes": [{"symbol": s, "ts_ns": now_ns} for s in symbols],
            "account_identity_sha256": "fixture-account"}


def paper_ready_config(symbols=("SPY",)):
    return {"capital_usd": "10000", "duration_seconds": 60, "cleanup_seconds": 10,
            "symbols": list(symbols), "benchmarks": list(symbols), "quote_max_age_seconds": 5,
            "feed": "iex", "regular_session_only": True, "extended_hours_enabled": False,
            "sessions": {"extended_hours": False, "overnight_holds": False, "overnight_gross_multiple": "1.0"}}


def full_gate_result(input_sha256):
    return {"status": "pass", "input_sha256": input_sha256, "row_count": 1,
            "checks": [{"name": name, "status": "pass", "detail": "ok"}
                       for name in sorted(runner_module._GATE_CHECK_NAMES)],
            "versions": {"pandera": "0.33.1"}, "checked_at": "2026-09-22T00:00:00+00:00"}


class AdaptiveLaneFees(unittest.TestCase):
    """runner.main keeps its first trial's baseline_cash (trial.json started_at), so its fee window is
    started_at, and its next-trial cash check records the fees posted since then before comparing."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.env_file = self.root / "paper.env"
        self.env_file.write_text("APCA_API_KEY_ID=fixture-key\nAPCA_API_SECRET_KEY=fixture-secret\n")
        os.chmod(self.env_file, 0o600)
        self.config_file = self.root / "config.json"
        self.config_file.write_text("{}")
        self.output = self.root / "output.json"
        self.universe = self.root / "universe.csv"
        self.universe.write_text("symbol\nSPY\n")
        self.gate = self.root / "gate-result.json"
        self.gate.write_text(json.dumps(full_gate_result(hashlib.sha256(self.universe.read_bytes()).hexdigest())))
        self.observation = paper_ready_observation(time.time_ns())
        self.state = self.root / "state" / "fixture-account" / "adaptive"
        self.state.mkdir(parents=True)
        (self.state / "trial.json").write_text(json.dumps({
            "trial_id": "fee-1", "started_at": T0, "current_trial_started_at": T0 + 86400,
            "config_sha256": hashlib.sha256(self.config_file.read_bytes()).hexdigest(),
            "baseline_cash": "10000.47", "phase": "finished", "status": "passed"}))

    def run_main(self, command, fees, cash):
        self.observation["account"]["cash"] = cash
        seen = {}
        sentinel = RuntimeError("transport_constructed")

        def fake_fees(key, secret, *, after, before_request, request_observer=None, **kwargs):
            seen["fee_after"] = after
            before_request("read")
            return [dict(fee) for fee in fees]

        def fake_transport(*args, **kwargs):
            seen["transport"] = kwargs
            raise sentinel

        argv = ["runner.py", command, "--env-file", str(self.env_file), "--config", str(self.config_file),
                "--output", str(self.output), "--state-root", str(self.root / "state"), "--trial", "fee-2"]
        if command == "paper":
            argv += ["--gate-result", str(self.gate), "--snapshot", str(self.universe)]
        raised = None
        with patch.object(sys, "argv", argv), \
             patch.object(runner_module, "load_config", return_value=(paper_ready_config(), RiskLimits(), None)), \
             patch.object(runner_module, "credentials", return_value=("fixture-key", "fixture-secret")), \
             patch.object(runner_module, "preflight", return_value=self.observation), \
             patch.object(runner_module, "account_lock_fingerprint", lambda _fingerprint: nullcontext()), \
             patch.object(runner_module, "fee_activities", fake_fees, create=True), \
             patch.object(runner_module, "AlpacaPaperTransport", fake_transport):
            try:
                runner_module.main()
            except Exception as exc:  # noqa: BLE001 -- the sentinel says the transport was reached
                raised = exc
        return seen, raised, sentinel

    def ledger(self):
        ledger = Ledger(self.state / "ledger.sqlite3", RiskLimits())
        self.addCleanup(ledger.close)
        return ledger

    def test_fees_posted_since_the_baseline_are_recorded_before_the_next_trial_check(self):
        seen, raised, sentinel = self.run_main("paper", measured_fees(), "10000.00")
        self.assertIs(raised, sentinel, raised)                       # the next-trial cash check passed
        self.assertEqual(seen["fee_after"], utc(T0))
        self.assertEqual((seen["transport"]["fee_history_start"], seen["transport"]["history_start"]),
                         (utc(T0), utc(T0)))
        ledger = self.ledger()
        self.assertEqual([f["activity_id"] for f in ledger.fees()], [f["id"] for f in measured_fees()])
        self.assertEqual(ledger.accounting().cash_delta_usd, D("-0.47"))
        self.assertEqual([r[0] for r in ledger.db.execute("SELECT kind FROM requests")], ["read"])

    def test_an_unexplained_gap_still_refuses_the_next_trial(self):
        for fees, cash in (([], "10000.00"), (measured_fees(), "10001.02")):
            with self.subTest(fees=len(fees), cash=cash):
                seen, raised, sentinel = self.run_main("paper", fees, cash)
                self.assertIsInstance(raised, SafetyError)
                self.assertEqual(str(raised), "next_trial_cash_mismatch")
                self.assertNotIn("transport", seen)

    def test_the_adaptive_recover_transport_reads_fees_from_started_at(self):
        self.observation["positions"] = [{"symbol": "SPY", "qty": "1"}]
        seen, raised, sentinel = self.run_main("recover", [], "10000.00")
        self.assertIs(raised, sentinel, raised)
        self.assertEqual((seen["transport"]["fee_history_start"], seen["transport"]["history_start"]),
                         (utc(T0), utc(T0)))
        self.assertNotIn("fee_after", seen)        # recover records fees through its own snapshots


# ---------------------------------------------------------------------------
# Items 4 and 9: mover helpers, fee window and receipts
# ---------------------------------------------------------------------------

class MoverFeeHelpers(unittest.TestCase):
    def test_fee_receipt_counts_totals_and_sub_types_without_ids(self):
        rows = [{"activity_id": f["id"], "date": f["date"], "net_amount": D(f["net_amount"]),
                 "sub_type": f["sub_type"], "recorded_at": T0} for f in measured_fees()]
        summary = mover_runner.fee_receipt(rows)
        self.assertEqual(summary, {"count": 3, "total_usd": "-0.47",
                                   "sub_types": {"CAT": {"count": 1, "total_usd": "-0.01"},
                                                 "REG": {"count": 1, "total_usd": "-0.19"},
                                                 "TAF": {"count": 1, "total_usd": "-0.27"}}})
        text = json.dumps(summary)
        for fee in measured_fees():
            self.assertNotIn(fee["id"].split("::")[1], text)
        self.assertEqual(mover_runner.fee_receipt([]), {"count": 0, "total_usd": "0", "sub_types": {}})

    def test_the_mover_fee_window_is_the_trials_own_baseline_time(self):
        self.assertEqual(mover_runner.fee_window_start({"started_at": T0 - 86400, "current_trial_started_at": T0}),
                         utc(T0))
        for metadata in ({}, {"started_at": T0}, {"current_trial_started_at": None},
                         {"current_trial_started_at": "1790000000"}, {"current_trial_started_at": True},
                         {"current_trial_started_at": float("nan")}, {"current_trial_started_at": -1.0}, None, []):
            with self.subTest(metadata=metadata):
                with self.assertRaisesRegex(SafetyError, "^trial_metadata_lacks_baseline_time$"):
                    mover_runner.fee_window_start(metadata)


CONFIG = SOURCE / "config-mover.json"
SCAN_TIME = datetime(2026, 9, 24, 12, 0, 5, tzinfo=timezone.utc).timestamp()  # 08:00:05 ET
PRE_TS = datetime(2026, 9, 24, 12, 30, tzinfo=timezone.utc)                   # 08:30 ET


def scan_row(symbol, rank, price):
    return {"symbol": symbol, "rank": rank, "price_at_t": price, "dollar_volume_at_t": "50000000",
            "entry_bar_dollar_volume": "2000000"}


def scan_raw(rows):
    return json.dumps({"schema_version": 1, "kind": "mover_scan", "protocol": "mover-early-entry-v1-20260924",
                       "rule": "08:00|G20|V1000000|any", "scan_time": "2026-09-24T12:00:05Z",
                       "regime": {"factor": "1"}, "symbols": rows}).encode()


@unittest.skipUnless(NATIVE, "requires pinned combined native runtime")
class MoverLaneFees(unittest.TestCase):
    """``mover_runner.py paper``/``recover`` end to end with a fake preflight and the synthetic port in
    place of AlpacaPaperTransport (as test_adaptive_paper_mover_native.MoverPaperCommandWiring), plus a
    broker-side FEE list the port filters by the transport's fee window. A SYN wiring fixture."""

    SERVER = datetime(2026, 9, 24, 12, 0, 30, tzinfo=timezone.utc).timestamp()  # 08:00:30 ET, PRE
    FINGERPRINT = "f" * 64

    def setUp(self):
        self.broker = None
        self.sell_blocked_ports = 0
        self.windows = []            # (fee_history_start, history_start) per transport built
        self.posted = []             # (created_at epoch, raw FEE row) the broker lists
        self.post_on_port = None     # post the measured fees as this transport (1-based) is built

    def post_fees(self):
        """The broker posts the measured FEE activities now: cash falls by 0.47 and the rows are listed."""
        created = time.time()
        self.posted.extend((created, row) for row in measured_rows())
        self.broker.cash -= D("0.47")

    def observation(self, symbols):
        server_ns, now_ns = int(self.SERVER * 1e9), time.time_ns()
        cash = format(self.broker.cash, "f") if self.broker is not None else "100000"
        positions = [] if self.broker is None else [
            {"symbol": s, "qty": format(q, "f"), "avg_entry_price": "10"} for s, q in self.broker.positions.items() if q]
        orders = [] if self.broker is None else [
            self.broker._public(o) for o in self.broker.orders.values() if o["status"] in ("new", "partially_filled")]
        return {"account": {"status": "ACTIVE", "currency": "USD", "cash": cash, "equity": cash,
                            "buying_power": cash, "trading_blocked": False, "account_blocked": False,
                            "trade_suspended_by_user": False},
                "account_identity_sha256": self.FINGERPRINT,
                "clock": {"is_open": False, "received_at_ns": server_ns, "timestamp_ns": server_ns,
                          "next_close_ns": server_ns + 8 * 3600 * 10 ** 9, "next_open_ns": server_ns + 5400 * 10 ** 9},
                "positions": positions, "orders": orders, "open_orders_complete": True,
                "assets": [{"symbol": s, "status": "active", "tradable": True} for s in symbols],
                "quotes": [{"symbol": s, "bid": "100", "ask": "100.01", "ts_ns": now_ns} for s in symbols],
                "quote_errors": {}}

    def fast_config(self, root):
        data = json.loads(CONFIG.read_text())
        data["order_timeout_seconds"] = 1
        path = Path(root) / "config-fast.json"
        path.write_text(json.dumps(data))
        return path

    def trial_json(self, root):
        return json.loads((Path(root) / "state" / self.FINGERPRINT / "mover" / "trial.json").read_text())

    def run_command(self, root, trial, *, command="paper", config=None):
        import signal
        import transport
        out = Path(root) / f"{trial or command}.json"
        real_load_scan, real_build_plan, real_flag = (mover_runner.load_scan, mover_runner.build_plan,
                                                      native_adapter.order_extended_hours_flag)

        def compressed_plan(settings, limits, scan, session, *, t0, **kwargs):
            timing = mover.Timing(t0, t0 + 2.0, 1.0, 1.0, t0 + 4.0, t0 + 8.0, None, 1.5)
            return real_build_plan(settings, limits, scan, session, t0=t0, timing=timing, **kwargs)

        def fake_transport(key, secret, symbols, **kwargs):
            controller = kwargs["before_request"].__self__
            port = MoverSimulatedPort(controller, symbols, path=piecewise_path({s: [(0, D("10.00"), D("0.02"))]
                                                                                for s in symbols}),
                                      extended_hours_allowed=kwargs.get("extended_hours_allowed", False))
            if self.broker is not None:
                port.orders, port.positions, port.cash = self.broker.orders, self.broker.positions, self.broker.cash
                port.t0 = self.broker.t0
            port.fill_sells = self.sell_blocked_ports <= 0
            self.sell_blocked_ports -= 1
            window = kwargs.get("fee_history_start")
            self.windows.append((window, kwargs.get("history_start")))
            listed = port.snapshot

            async def snapshot():
                result = await listed()
                if window is not None:
                    # The broker's `after` filter on created_at; the rows pass the real normalization.
                    result["fees"] = [t.normalize_fee_activity(row) for created, row in self.posted
                                      if created > window.timestamp()]
                return result
            port.snapshot = snapshot
            self.broker = port
            if self.post_on_port == len(self.windows):
                self.post_fees()
            return port

        args = [command, "--env-file", str(Path(root) / "unused.env"), "--output", str(out),
                "--state-root", str(Path(root) / "state")]
        if command == "paper":
            args += ["--scan", str(Path(root) / "scan.json"), "--trial", trial]
        if config is not None:
            args += ["--config", str(config)]
        handlers = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}
        try:
            with patch.object(mover_runner, "credentials", return_value=("key", "secret")), \
                 patch.object(transport, "preflight", lambda key, secret, symbols, **kw: self.observation(symbols)), \
                 patch.object(transport, "AlpacaPaperTransport", fake_transport), \
                 patch.object(mover_runner, "load_scan",
                              lambda raw, settings, *, now: real_load_scan(raw, settings, now=SCAN_TIME + 20)), \
                 patch.object(mover_runner, "build_plan", compressed_plan), \
                 patch.object(mover_runner, "_controller_session", lambda close, now, policy: (now + 36000, True)), \
                 patch.object(native_adapter, "order_extended_hours_flag", lambda ts, p: real_flag(PRE_TS, p)), \
                 patch("builtins.print"):
                code = mover_runner.main(args)
        finally:
            for sig, handler in handlers.items():
                signal.signal(sig, handler)
        return code, json.loads(out.read_text())

    def test_each_mover_transport_reads_fees_from_its_trials_own_baseline_time(self):
        with tempfile.TemporaryDirectory() as root:
            config = self.fast_config(root)
            (Path(root) / "scan.json").write_bytes(scan_raw([scan_row("AAA", 1, "10.00")]))
            self.assertEqual(self.run_command(root, "lane-1", config=config)[0], 0)
            first = self.trial_json(root)
            self.assertEqual(self.run_command(root, "lane-2", config=config)[0], 0)
            second = self.trial_json(root)
            self.assertEqual(second["started_at"], first["started_at"])
            self.assertLess(first["current_trial_started_at"], second["current_trial_started_at"])
            self.assertEqual(self.windows, [(utc(first["current_trial_started_at"]), utc(first["started_at"])),
                                            (utc(second["current_trial_started_at"]), utc(second["started_at"]))])
            code, result = self.run_command(root, None, command="recover", config=config)
            self.assertEqual((code, result["status"]), (0, "passed"))
            self.assertEqual(self.windows[-1], (utc(second["current_trial_started_at"]), utc(second["started_at"])))

    def test_recover_records_fees_posted_after_the_trial_and_reports_them(self):
        # The account 2 case: the trial ends needs_attention holding a position, the day's REG/TAF/CAT
        # then post, and every recover ended cash_mismatch_or_unmodeled_fees.
        with tempfile.TemporaryDirectory() as root:
            config = self.fast_config(root)
            (Path(root) / "scan.json").write_bytes(scan_raw([scan_row("AAA", 1, "10.00")]))
            self.sell_blocked_ports = 2            # the trial's port and the forced recovery's leave sells resting
            code, receipt = self.run_command(root, "ext-1", config=config)
            self.assertEqual((code, receipt["status"], receipt["flat"]), (3, "needs_attention", False))
            self.assertEqual(receipt["fees_recorded"], {"count": 0, "total_usd": "0", "sub_types": {}})
            self.post_fees()
            code, result = self.run_command(root, None, command="recover", config=config)
            self.assertEqual((code, result["kind"], result["status"], result["flat"], result["errors"]),
                             (0, "mover_recovery_receipt", "passed", True, []))
            self.assertEqual(result["fees_recorded"], {"count": 3, "total_usd": "-0.47",
                                                       "sub_types": {"CAT": {"count": 1, "total_usd": "-0.01"},
                                                                     "REG": {"count": 1, "total_usd": "-0.19"},
                                                                     "TAF": {"count": 1, "total_usd": "-0.27"}}})
            text = json.dumps(result)
            for fee in measured_fees():
                self.assertNotIn(fee["id"].split("::")[1], text)
            self.assertNotIn(ACCOUNT_TEXT, text)
            self.assertEqual(self.trial_json(root)["phase"], "finished")
            # The next trial's own baseline already holds the posted fees: nothing re-recorded, no mismatch.
            code, receipt = self.run_command(root, "ext-2", config=config)
            self.assertEqual((code, receipt["status"], receipt["flat"]), (0, "passed", True), receipt.get("error_reason"))
            self.assertEqual(receipt["fees_recorded"]["count"], 0)
            self.assertTrue(receipt["totals"]["pnl_consistent"], receipt["totals"])

    def test_fees_posted_during_a_trial_are_recorded_and_the_receipt_stays_consistent(self):
        with tempfile.TemporaryDirectory() as root:
            config = self.fast_config(root)
            (Path(root) / "scan.json").write_bytes(scan_raw([scan_row("AAA", 1, "10.00")]))
            self.post_on_port = 1                  # the broker posts fees just after the trial's transport exists
            code, receipt = self.run_command(root, "ext-1", config=config)
            self.assertEqual((code, receipt["status"], receipt["flat"]), (0, "passed", True), receipt.get("error_reason"))
            self.assertEqual((receipt["fees_recorded"]["count"], receipt["fees_recorded"]["total_usd"]), (3, "-0.47"))
            totals = receipt["totals"]
            self.assertEqual(totals["fees_recorded_usd"], "-0.47")
            self.assertEqual(D(totals["ledger_realized_pnl_delta_usd"]), D(totals["realized_pnl_usd"]) + D("-0.47"))
            self.assertTrue(totals["pnl_consistent"], totals)
            self.assertNotIn(ACCOUNT_TEXT, json.dumps(receipt))


if __name__ == "__main__":
    unittest.main()
