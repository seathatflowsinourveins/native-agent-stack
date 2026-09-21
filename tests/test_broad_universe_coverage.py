"""Local integration checks for the broad-universe coverage/corporate-actions
tooling. Synthetic fixtures only: no network, no credentials, no real dataset.
Loaded the same way as tests/test_adaptive_market_research.py (importlib spec
from the blueprint path).

The repository's default CI runs `python3 -m unittest` without duckdb/numpy/requests.
coverage.py imports duckdb at module scope, so it is loaded only when duckdb is
present and every test that needs it skips otherwise; corporate_actions.py and
collect_daily.py are stdlib-only and their checks run everywhere.
"""
import csv
import gzip
import hashlib
import importlib.util
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

BASE = Path(__file__).resolve().parents[1] / "blueprints/us-equities/broad-universe"

HAS_DUCKDB = importlib.util.find_spec("duckdb") is not None
NEEDS_DUCKDB = "requires the pinned native research SDK environment (duckdb)"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, BASE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


corporate_actions = _load("corporate_actions")
collect_daily = _load("collect_daily")
coverage = _load("coverage") if HAS_DUCKDB else None


def write_csv_gz(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with gzip.open(path, "wt", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["symbol", "t", "o", "h", "l", "c", "v", "n", "vw"])
        writer.writerows(rows)


def write_action_page(directory, year, page, payload):
    year_dir = os.path.join(directory, "pages", str(year))
    os.makedirs(year_dir, exist_ok=True)
    with gzip.open(os.path.join(year_dir, f"p{page:04d}.json.gz"), "wt", encoding="utf-8") as handle:
        json.dump(payload, handle)


def write_actions_ledger(directory, start, end, types_key="tk", failed=0, skip_years=()):
    with open(os.path.join(directory, "plan.json"), "w", encoding="utf-8") as handle:
        json.dump({"start": start, "end": end, "types_key": types_key, "types": ["name_change"]}, handle)
    with open(os.path.join(directory, "ledger.jsonl"), "w", encoding="utf-8") as handle:
        for year in range(int(start[:4]), int(end[:4]) + 1):
            if year in skip_years:
                continue
            handle.write(json.dumps({"event": "year_complete", "year": year, "types_key": types_key}) + "\n")
        handle.write(json.dumps({"event": "run_complete", "types_key": types_key, "failed": failed}) + "\n")


@unittest.skipUnless(HAS_DUCKDB, NEEDS_DUCKDB)
class PaginationProofTests(unittest.TestCase):
    def test_contiguous_terminal_page_passes(self):
        events = [
            {"adjustment": "raw", "batch": "b00000", "page": 0, "next_page_token_present": True},
            {"adjustment": "raw", "batch": "b00000", "page": 1, "next_page_token_present": False},
        ]
        result = coverage.pagination_proof(events)
        self.assertEqual(result["symbol_groups_checked"], 1)
        self.assertEqual(result["violations"], [])

    def test_missing_terminal_page_detected(self):
        # Only page 0 exists but its next_page_token is present: no terminal page was ever recorded.
        events = [{"adjustment": "raw", "batch": "b00000", "page": 0, "next_page_token_present": True}]
        result = coverage.pagination_proof(events)
        self.assertEqual(len(result["violations"]), 1)
        self.assertEqual(result["violations"][0]["batch"], "b00000")

    def test_non_contiguous_pages_detected(self):
        events = [
            {"adjustment": "raw", "batch": "b00001", "page": 0, "next_page_token_present": True},
            {"adjustment": "raw", "batch": "b00001", "page": 2, "next_page_token_present": False},
        ]
        result = coverage.pagination_proof(events)
        self.assertEqual(len(result["violations"]), 1)
        self.assertEqual(result["violations"][0]["pages"], [0, 2])

    def test_non_terminal_page_falsely_marked_final_detected(self):
        events = [
            {"adjustment": "raw", "batch": "b00002", "page": 0, "next_page_token_present": False},
            {"adjustment": "raw", "batch": "b00002", "page": 1, "next_page_token_present": False},
        ]
        result = coverage.pagination_proof(events)
        self.assertEqual(len(result["violations"]), 1)


@unittest.skipUnless(HAS_DUCKDB, NEEDS_DUCKDB)
class ShaReverificationTests(unittest.TestCase):
    def test_matching_sha_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw = b"hello world"
            os.makedirs(os.path.join(tmp, "pages", "raw"))
            with gzip.open(os.path.join(tmp, "pages", "raw", "b00000-p0000.json.gz"), "wb") as handle:
                handle.write(raw)
            events = [{"adjustment": "raw", "file": "b00000-p0000.json.gz",
                       "sha256": hashlib.sha256(raw).hexdigest()}]
            result = coverage.verify_page_sha256(tmp, events)
            self.assertEqual(result["verified"], 1)
            self.assertEqual(result["mismatches"], [])

    def test_mismatch_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw = b"hello world"
            os.makedirs(os.path.join(tmp, "pages", "raw"))
            with gzip.open(os.path.join(tmp, "pages", "raw", "b00000-p0000.json.gz"), "wb") as handle:
                handle.write(raw)
            events = [{"adjustment": "raw", "file": "b00000-p0000.json.gz", "sha256": "0" * 64}]
            result = coverage.verify_page_sha256(tmp, events)
            self.assertEqual(result["verified"], 0)
            self.assertEqual(len(result["mismatches"]), 1)
            self.assertEqual(result["mismatches"][0]["reason"], "sha_mismatch")

    def test_missing_file_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "pages", "raw"))
            events = [{"adjustment": "raw", "file": "absent.json.gz", "sha256": "0" * 64}]
            result = coverage.verify_page_sha256(tmp, events)
            self.assertEqual(result["mismatches"][0]["reason"], "missing")


@unittest.skipUnless(HAS_DUCKDB, NEEDS_DUCKDB)
class LedgerCompletenessTests(unittest.TestCase):
    def test_complete_ledger_accepted(self):
        plan = {"adjustments": ["raw", "all"], "batches": 2}
        events = [
            {"event": "batch_complete", "adjustment": "raw", "batch": 0},
            {"event": "batch_complete", "adjustment": "raw", "batch": 1},
            {"event": "batch_complete", "adjustment": "all", "batch": 0},
            {"event": "batch_complete", "adjustment": "all", "batch": 1},
            {"event": "run_complete", "failed": 0},
        ]
        ok, reasons = coverage.check_ledger_complete(plan, events)
        self.assertTrue(ok, reasons)

    def test_missing_batch_refused(self):
        plan = {"adjustments": ["raw", "all"], "batches": 2}
        events = [
            {"event": "batch_complete", "adjustment": "raw", "batch": 0},
            {"event": "batch_complete", "adjustment": "all", "batch": 0},
            {"event": "batch_complete", "adjustment": "all", "batch": 1},
            {"event": "run_complete", "failed": 0},
        ]
        ok, reasons = coverage.check_ledger_complete(plan, events)
        self.assertFalse(ok)
        self.assertTrue(any("raw" in r and "batch=1" in r for r in reasons))

    def test_failed_run_refused(self):
        plan = {"adjustments": ["raw"], "batches": 1}
        events = [
            {"event": "batch_complete", "adjustment": "raw", "batch": 0},
            {"event": "run_complete", "failed": 3},
        ]
        ok, reasons = coverage.check_ledger_complete(plan, events)
        self.assertFalse(ok)

    def test_no_run_complete_refused(self):
        plan = {"adjustments": ["raw"], "batches": 1}
        events = [{"event": "batch_complete", "adjustment": "raw", "batch": 0}]
        ok, reasons = coverage.check_ledger_complete(plan, events)
        self.assertFalse(ok)


@unittest.skipUnless(HAS_DUCKDB, NEEDS_DUCKDB)
class MaterializeDatasetTests(unittest.TestCase):
    def _base_dataset(self, tmp, raw_rows, all_rows):
        write_csv_gz(os.path.join(tmp, "bars", "raw", "b00000.csv.gz"), raw_rows)
        write_csv_gz(os.path.join(tmp, "bars", "all", "b00000.csv.gz"), all_rows)

    def test_materialize_refuses_on_incomplete_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._base_dataset(tmp, [("AAA", "2020-01-02T05:00:00Z", 1, 2, 0.5, 1.5, 100, 3, 1.1)],
                                [("AAA", "2020-01-02T05:00:00Z", 1, 2, 0.5, 1.5, 100, 3, 1.1)])
            plan = {"adjustments": ["raw", "all"], "batches": 1}
            with open(os.path.join(tmp, "plan.json"), "w") as handle:
                json.dump(plan, handle)
            # ledger only shows the raw batch complete: incomplete.
            with open(os.path.join(tmp, "ledger.jsonl"), "w") as handle:
                handle.write(json.dumps({"event": "batch_complete", "adjustment": "raw", "batch": 0}) + "\n")
                handle.write(json.dumps({"event": "run_complete", "failed": 0}) + "\n")
            events = coverage.read_ledger_events(tmp)
            ok, reasons = coverage.check_ledger_complete(plan, events)
            self.assertFalse(ok)
            self.assertFalse(os.path.exists(os.path.join(tmp, "daily.parquet")))

    def test_materialize_detects_duplicate_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            dup_rows = [
                ("AAA", "2020-01-02T05:00:00Z", 1, 2, 0.5, 1.5, 100, 3, 1.1),
                ("AAA", "2020-01-02T05:00:00Z", 1, 2, 0.5, 1.6, 101, 3, 1.1),
            ]
            self._base_dataset(tmp, dup_rows, dup_rows)
            import duckdb
            con = duckdb.connect()
            coverage.load_bars_view(con, tmp, "raw", "raw_bars", "raw")
            dups = coverage.detect_duplicate_rows(con, "raw_bars")
            self.assertEqual(len(dups), 1)
            self.assertEqual(dups[0]["symbol"], "AAA")
            ok, detail = coverage.materialize(tmp)
            self.assertFalse(ok)
            self.assertIn("duplicate", detail["reason"])

    def test_materialize_builds_parquet_with_raw_all_mismatch_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw_rows = [
                ("AAA", "2020-01-02T05:00:00Z", 1, 2, 0.5, 1.5, 100, 3, 1.1),
                ("BBB", "2020-01-02T05:00:00Z", 5, 6, 4, 5.5, 200, 3, 5.1),  # raw-only
            ]
            all_rows = [
                ("AAA", "2020-01-02T05:00:00Z", 1, 2, 0.5, 1.5, 100, 3, 1.1),
                ("CCC", "2020-01-02T05:00:00Z", 7, 8, 6, 7.5, 300, 3, 7.1),  # all-only
            ]
            self._base_dataset(tmp, raw_rows, all_rows)
            ok, detail = coverage.materialize(tmp)
            self.assertTrue(ok, detail)
            self.assertEqual(detail["rows"], 3)
            import duckdb
            con = duckdb.connect()
            con.execute(f"CREATE VIEW daily AS SELECT * FROM read_parquet('{detail['path']}')")
            quality = coverage.build_quality_section(con)
            self.assertEqual(quality["raw_all_presence_mismatch"], 2)
            self.assertEqual(quality["total_rows"], 3)


@unittest.skipUnless(HAS_DUCKDB, NEEDS_DUCKDB)
class GapCountingTests(unittest.TestCase):
    def test_gap_counted_against_spy_calendar(self):
        with tempfile.TemporaryDirectory() as tmp:
            spy_dates = ["2020-01-02", "2020-01-03", "2020-01-06", "2020-01-07", "2020-01-08"]
            spy_rows = [("SPY", f"{d}T05:00:00Z", 1, 1, 1, 1, 1, 1, 1) for d in spy_dates]
            # AAA has bars on the first, third and fifth SPY sessions only: two gap sessions.
            aaa_dates = ["2020-01-02", "2020-01-06", "2020-01-08"]
            aaa_rows = [("AAA", f"{d}T05:00:00Z", 1, 1, 1, 1, 1, 1, 1) for d in aaa_dates]
            write_csv_gz(os.path.join(tmp, "bars", "raw", "b00000.csv.gz"), spy_rows + aaa_rows)
            write_csv_gz(os.path.join(tmp, "bars", "all", "b00000.csv.gz"), spy_rows + aaa_rows)
            ok, detail = coverage.materialize(tmp)
            self.assertTrue(ok, detail)
            import duckdb
            con = duckdb.connect()
            con.execute(f"CREATE VIEW daily AS SELECT * FROM read_parquet('{detail['path']}')")
            gaps = coverage.compute_gap_by_symbol(con)
            self.assertEqual(gaps["AAA"], 2)
            self.assertEqual(gaps["SPY"], 0)


@unittest.skipUnless(HAS_DUCKDB, NEEDS_DUCKDB)
class EligibilityPriorSessionsTests(unittest.TestCase):
    def _dataset_with_volume_at_t(self, tmp, volume_at_t):
        # 25 sessions; raw_c is always >= 5. Sessions 0..21 have a fixed dv so
        # med20 for session t (index 22, 0-based) is deterministic; only the
        # LAST session's own volume varies, and must not move that med20.
        rows = []
        dates = [f"2020-{(i // 28) + 1:02d}-{(i % 28) + 1:02d}" for i in range(23)]
        for i, d in enumerate(dates):
            if i == len(dates) - 1:
                volume = volume_at_t
            else:
                volume = 1_000_000  # dv = 10 * 1_000_000 = 10,000,000 for every prior session
            rows.append(("AAA", f"{d}T05:00:00Z", 10, 10, 10, 10, volume, 1, 10))
        write_csv_gz(os.path.join(tmp, "bars", "raw", "b00000.csv.gz"), rows)
        write_csv_gz(os.path.join(tmp, "bars", "all", "b00000.csv.gz"), rows)
        return dates[-1]

    def test_current_session_volume_does_not_move_med20(self):
        med20_values = []
        for volume_at_t in (1, 999_999_999):
            with tempfile.TemporaryDirectory() as tmp:
                last_date = self._dataset_with_volume_at_t(tmp, volume_at_t)
                ok, detail = coverage.materialize(tmp)
                self.assertTrue(ok, detail)
                import duckdb
                con = duckdb.connect()
                con.execute(f"CREATE VIEW daily AS SELECT * FROM read_parquet('{detail['path']}')")
                row = con.execute("""
                    WITH r AS (
                        SELECT symbol, session_date, raw_c, raw_c * raw_v AS dv
                        FROM daily WHERE in_raw
                    )
                    SELECT session_date,
                           median(dv) OVER (PARTITION BY symbol ORDER BY session_date
                                             ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING) AS med20
                    FROM r ORDER BY session_date
                """).fetchall()
                med20_values.append(dict((str(d), m) for d, m in row)[last_date])
        self.assertEqual(med20_values[0], med20_values[1])
        self.assertEqual(med20_values[0], 10_000_000)


class CorporateActionsPaginationTests(unittest.TestCase):
    def _fake_response(self, payload, status=200):
        response = MagicMock()
        response.status_code = status
        response.content = json.dumps(payload).encode()
        response.text = json.dumps(payload)
        response.headers = {}
        return response

    def test_collect_year_pages_to_terminal_token(self):
        pages = [
            {"corporate_actions": {"forward_split": [{"ex_date": "2022-01-05"}]}, "next_page_token": "tok1"},
            {"corporate_actions": {"forward_split": [{"ex_date": "2022-03-01"}]}, "next_page_token": None},
        ]
        session = MagicMock()
        session.get.side_effect = [self._fake_response(p) for p in pages]
        headers = {"APCA-API-KEY-ID": "k", "APCA-API-SECRET-KEY": "s"}
        with tempfile.TemporaryDirectory() as tmp:
            ledger_path = os.path.join(tmp, "ledger.jsonl")

            class FakeLedger:
                def __init__(self, path):
                    self.path = path

                def write(self, **rec):
                    with open(self.path, "a") as handle:
                        handle.write(json.dumps(rec) + "\n")

            ledger = FakeLedger(ledger_path)
            total = corporate_actions.collect_year(session, headers, 2022, "2022-01-01", "2022-12-31",
                                                    ("forward_split",), tmp, ledger, "typeskey")
            self.assertEqual(total, 2)
            self.assertEqual(session.get.call_count, 2)
            page_files = sorted(os.path.join(tmp, "pages", "2022", n)
                                 for n in os.listdir(os.path.join(tmp, "pages", "2022")))
            self.assertEqual(len(page_files), 2)
            with open(ledger_path) as handle:
                events = [json.loads(line) for line in handle]
            page_events = [e for e in events if e["event"] == "page"]
            self.assertEqual([e["page"] for e in page_events], [0, 1])
            self.assertFalse(page_events[0]["next_page_token_present"] is False)
            self.assertFalse(page_events[1]["next_page_token_present"])
            complete = [e for e in events if e["event"] == "year_complete"][0]
            self.assertEqual(complete["items"], 2)

            summary = corporate_actions.summarize_dict(tmp)
            self.assertEqual(summary["per_type_per_year_counts"]["forward_split"], {"2022": 2})
            self.assertEqual(summary["earliest_by_type"]["forward_split"], "2022-01-05")
            self.assertEqual(summary["latest_by_type"]["forward_split"], "2022-03-01")

    def test_bad_request_raises(self):
        session = MagicMock()
        session.get.return_value = self._fake_response({"message": "bad"}, status=400)
        headers = {}
        with self.assertRaises(corporate_actions.BadRequest):
            corporate_actions.fetch_page(session, headers, {"start": "2022-01-01"})



@unittest.skipUnless(HAS_DUCKDB, NEEDS_DUCKDB)
class SupplementLedgerTests(unittest.TestCase):
    PLAN = {"adjustments": ["raw"], "batches": 1}

    def test_supplement_series_must_be_complete_too(self):
        events = [{"event": "batch_complete", "adjustment": "raw", "batch": 0},
                  {"event": "run_complete", "failed": 0}]
        self.assertTrue(coverage.check_ledger_complete(self.PLAN, events)[0])
        ok, reasons = coverage.check_ledger_complete(self.PLAN, events, {"adjustments": ["raw"], "batches": 1})
        self.assertFalse(ok)
        self.assertTrue(any("series=s" in r for r in reasons))
        events += [{"event": "batch_complete", "series": "s", "adjustment": "raw", "batch": 0},
                   {"event": "run_complete", "series": "s", "failed": 0}]
        self.assertTrue(coverage.check_ledger_complete(self.PLAN, events, {"adjustments": ["raw"], "batches": 1})[0])

    def test_main_batch_does_not_satisfy_supplement_batch(self):
        events = [{"event": "batch_complete", "adjustment": "raw", "batch": 0},
                  {"event": "run_complete", "failed": 0},
                  {"event": "run_complete", "series": "s", "failed": 0}]
        self.assertFalse(coverage.check_ledger_complete(self.PLAN, events, {"adjustments": ["raw"], "batches": 1})[0])


@unittest.skipUnless(HAS_DUCKDB, NEEDS_DUCKDB)
class IdentityDedupTests(unittest.TestCase):
    """The provider serves an old ticker with its successor's history; exactly the
    identical rows must leave the old ticker and nothing else may move."""

    def _con(self, rows):
        import duckdb
        con = duckdb.connect()
        con.execute("CREATE TABLE joined (symbol VARCHAR, session_date DATE, raw_o DOUBLE, raw_h DOUBLE, "
                    "raw_l DOUBLE, raw_c DOUBLE, raw_v DOUBLE)")
        con.executemany("INSERT INTO joined VALUES (?, ?, ?, ?, ?, ?, ?)", rows)
        return con

    @staticmethod
    def _series(symbol, start_day, count, price, volume=1000.0):
        from datetime import date, timedelta
        return [(symbol, date(2022, 1, 1) + timedelta(days=start_day + i), price + i, price + i + 1,
                 price + i - 1, price + i + 0.5, volume + i) for i in range(count)]

    def test_rename_record_keeps_successor_and_reused_ticker_keeps_its_own_rows(self):
        shared = self._series("NEW", 0, 25, 100.0)
        rows = shared + [("OLD",) + r[1:] for r in shared]
        rows += self._series("NEW", 25, 5, 125.0)            # successor keeps trading
        rows += self._series("OLD", 40, 5, 20.0)             # ticker reused by another asset
        con = self._con(rows)
        report = coverage.dedupe_identity(con, {("OLD", "NEW")})
        self.assertEqual(report["pairs"], 1)
        self.assertEqual(report["detail"][0]["kept"], "NEW")
        self.assertEqual(report["detail"][0]["rule"], "rename_record")
        self.assertEqual(report["rows_removed"], 25)
        self.assertEqual(con.execute("SELECT count(*) FROM joined WHERE symbol='OLD'").fetchone()[0], 5)
        self.assertEqual(con.execute("SELECT count(*) FROM joined WHERE symbol='NEW'").fetchone()[0], 30)

    def test_price_continuity_decides_without_a_rename_record(self):
        shared = self._series("AAA", 0, 25, 100.0)
        rows = shared + [("ZZZ",) + r[1:] for r in shared]
        rows += self._series("ZZZ", 25, 5, 126.0)            # ZZZ continues near the last shared close
        rows += self._series("AAA", 60, 5, 9.0)              # AAA later reused far from that close
        report = coverage.dedupe_identity(self._con(rows), set())
        self.assertEqual((report["detail"][0]["kept"], report["detail"][0]["rule"]), ("ZZZ", "price_continuity"))

    def test_active_status_then_lexicographic_fallback(self):
        shared = self._series("BBB", 0, 25, 50.0)
        rows = shared + [("CCC",) + r[1:] for r in shared]
        report = coverage.dedupe_identity(self._con(list(rows)), set(), frozenset({"CCC"}))
        self.assertEqual((report["detail"][0]["kept"], report["detail"][0]["rule"]), ("CCC", "active_status"))
        report = coverage.dedupe_identity(self._con(list(rows)), set())
        self.assertEqual((report["detail"][0]["kept"], report["detail"][0]["rule"]), ("BBB", "lexicographic_fallback"))

    def test_short_coincidence_and_zero_volume_rows_are_not_duplicates(self):
        shared = self._series("DDD", 0, 19, 30.0)             # one session short of the threshold
        rows = shared + [("EEE",) + r[1:] for r in shared]
        flat = self._series("FFF", 0, 30, 10.0, volume=0.0)
        flat = [r[:6] + (0.0,) for r in flat]
        rows += flat + [("GGG",) + r[1:] for r in flat]
        con = self._con(rows)
        report = coverage.dedupe_identity(con, set())
        self.assertEqual(report["pairs"], 0)
        self.assertEqual(con.execute("SELECT count(*) FROM joined").fetchone()[0], len(rows))


def _identical(symbols, day, price, volume=1000.0, raw=True):
    """One session repeated byte-identically under several tickers."""
    session = date(2022, 1, 1) + timedelta(days=day)
    if not raw:  # present only in the adjustment=all series: every raw column is NULL
        return [(symbol, session, None, None, None, None, None) for symbol in symbols]
    return [(symbol, session, price, price + 1, price - 1, price + 0.5, volume) for symbol in symbols]


@unittest.skipUnless(HAS_DUCKDB, NEEDS_DUCKDB)
class IdentityComponentTests(unittest.TestCase):
    """Rename chains and three-way duplicates: one survivor per connected component,
    every decision taken from a snapshot made before the first DELETE."""

    def _con(self, rows):
        import duckdb
        con = duckdb.connect()
        con.execute("CREATE TABLE joined (symbol VARCHAR, session_date DATE, raw_o DOUBLE, raw_h DOUBLE, "
                    "raw_l DOUBLE, raw_c DOUBLE, raw_v DOUBLE)")
        con.executemany("INSERT INTO joined VALUES (?, ?, ?, ?, ?, ?, ?)", rows)
        return con

    def _shared(self, symbols, count=25, start_day=0, price=100.0):
        rows = []
        for i in range(count):
            rows += _identical(symbols, start_day + i, price + i)
        return rows

    def test_rename_chain_resolves_to_the_terminal_ticker(self):
        # A -> B -> C: the pair loop used to DELETE A's rows for pair (A,B) and then
        # dereference the very same rows for pair (A,C), raising TypeError.
        rows = self._shared(["AAA", "BBB", "CCC"])
        con = self._con(rows)
        report = coverage.dedupe_identity(con, {("AAA", "BBB"), ("BBB", "CCC")})
        self.assertEqual(report["components"], 1)
        self.assertEqual(report["pairs"], 2)
        self.assertEqual({item["kept"] for item in report["detail"]}, {"CCC"})
        self.assertEqual({item["dropped"] for item in report["detail"]}, {"AAA", "BBB"})
        self.assertEqual({item["rule"] for item in report["detail"]}, {"rename_record"})
        self.assertEqual(con.execute("SELECT count(*) FROM joined WHERE symbol <> 'CCC'").fetchone()[0], 0)
        self.assertEqual(con.execute("SELECT count(*) FROM joined").fetchone()[0], 25)

    def test_staggered_rename_chain_keeps_every_session_exactly_once(self):
        # AAA/BBB share sessions 0-24, BBB/CCC share 25-49 and CCC has no bars for 0-24.
        # Collapsing onto CCC used to delete both predecessors' whole spans: 50 sessions -> 25.
        rows = self._shared(["AAA", "BBB"], start_day=0, count=25)
        rows += self._shared(["BBB", "CCC"], start_day=25, count=25, price=200.0)
        con = self._con(rows)
        report = coverage.dedupe_identity(con, {("AAA", "BBB"), ("BBB", "CCC")})
        self.assertEqual({item["kept"] for item in report["detail"]}, {"CCC"})
        per_session = con.execute("SELECT session_date, count(*) FROM joined GROUP BY 1").fetchall()
        self.assertEqual(len(per_session), 50)
        self.assertEqual({n for _, n in per_session}, {1})
        self.assertEqual(con.execute("SELECT count(*) FROM joined WHERE symbol='AAA'").fetchone()[0], 0)
        self.assertEqual(con.execute("SELECT count(*) FROM joined WHERE symbol='BBB'").fetchone()[0], 25)
        self.assertEqual(con.execute("SELECT count(*) FROM joined WHERE symbol='CCC'").fetchone()[0], 25)

    def test_transitive_links_leave_one_row_per_session(self):
        # AAA~BBB on sessions 0-24, BBB~CCC on 20-44; AAA is later reused (a far-off bar), which
        # ranks it above BBB. AAA/CCC share only 5 sessions, so they never qualify directly, yet on
        # sessions 20-24 all three are one security: exactly one row per session may remain.
        rows = self._shared(["AAA", "BBB"], start_day=0, count=20)
        rows += self._shared(["AAA", "BBB", "CCC"], start_day=20, count=5, price=120.0)
        rows += self._shared(["BBB", "CCC"], start_day=25, count=20, price=125.0)
        rows += self._shared(["CCC"], start_day=45, count=5, price=145.0)      # CCC keeps trading
        rows += self._shared(["AAA"], start_day=300, count=3, price=7.0)       # ticker reused later
        con = self._con(rows)
        coverage.dedupe_identity(con, {("BBB", "CCC")})
        per_session = dict(con.execute(
            "SELECT session_date, count(*) FROM joined WHERE session_date < DATE '2022-02-20' GROUP BY 1").fetchall())
        self.assertEqual(len(per_session), 50)
        self.assertEqual(set(per_session.values()), {1})
        self.assertEqual(con.execute("SELECT count(*) FROM joined WHERE symbol='CCC'").fetchone()[0], 30)

    def test_residue_is_counted_among_the_rows_actually_removed(self):
        # BBB keeps 25 early sessions (its survivor CCC has no bar there) and loses 86 later ones,
        # one of which is a zero-volume halt that is not byte-identical. Residue must be 1, not 0.
        # (85 identical of 86 rows keeps the BBB/CCC pair above the 98% span-coverage test.)
        rows = self._shared(["AAA", "BBB"], start_day=0, count=25)
        rows += self._shared(["BBB", "CCC"], start_day=25, count=25, price=200.0)
        halt_day = 50
        rows += [("BBB",) + _identical(["BBB"], halt_day, 225.0)[0][1:6] + (0.0,),
                 ("CCC",) + _identical(["CCC"], halt_day, 225.0)[0][1:6] + (5.0,)]
        rows += self._shared(["BBB", "CCC"], start_day=51, count=60, price=226.0)
        con = self._con(rows)
        report = coverage.dedupe_identity(con, {("AAA", "BBB"), ("BBB", "CCC")})
        bbb = next(item for item in report["detail"] if item["dropped"] == "BBB")
        self.assertEqual(bbb["rows_removed"], 86)
        self.assertEqual(bbb["residue_rows_removed"], 1)
        self.assertEqual(con.execute("SELECT count(*) FROM joined WHERE symbol='BBB'").fetchone()[0], 25)

    def test_three_way_duplicate_without_rename_records_is_reported_unresolved(self):
        rows = self._shared(["AAA", "MMM", "ZZZ"])
        con = self._con(rows)
        report = coverage.dedupe_identity(con, set())
        self.assertEqual(report["pairs"], 2)
        self.assertEqual({item["kept"] for item in report["detail"]}, {"AAA"})
        self.assertEqual(report["by_rule"], {"lexicographic_fallback": 2})
        self.assertEqual(report["identity_unresolved_pairs"], 2)
        self.assertTrue(all(item["identity_unresolved"] for item in report["detail"]))
        self.assertEqual(con.execute("SELECT count(DISTINCT symbol) FROM joined").fetchone()[0], 1)

    def test_rename_pair_recorded_in_both_directions_is_not_evidence(self):
        rows = self._shared(["BBB", "CCC"])
        report = coverage.dedupe_identity(self._con(rows), {("BBB", "CCC"), ("CCC", "BBB")},
                                          frozenset({"CCC"}))
        self.assertEqual(report["detail"][0]["rule"], "active_status")
        self.assertEqual(report["detail"][0]["kept"], "CCC")

    def test_scattered_coincidental_matches_never_delete_a_live_series(self):
        # Two distinct securities with 800 overlapping sessions that happen to print the
        # same round tick on 25 scattered days. 20 identical sessions alone must not
        # merge them, or 25 holes are punched into a genuine, still-trading series.
        rows = []
        for day in range(800):
            if day % 32 == 0 and day // 32 < 25:
                rows += _identical(["XAA", "XBB"], day, 10.0)
            else:
                rows += _identical(["XAA"], day, 10.0 + day * 0.01)
                rows += _identical(["XBB"], day, 41.0 + day * 0.01)
        con = self._con(rows)
        before = con.execute("SELECT count(*) FROM joined").fetchone()[0]
        report = coverage.dedupe_identity(con, set())
        self.assertEqual(report["pairs"], 0)
        self.assertEqual(report["rows_removed"], 0)
        self.assertEqual(report["candidate_pairs"], 1)
        self.assertEqual(report["qualified_pairs"], 0)
        self.assertEqual(len(report["partial_overlap_not_deduped"]), 1)
        partial = report["partial_overlap_not_deduped"][0]
        self.assertEqual((partial["sym_a"], partial["sym_b"]), ("XAA", "XBB"))
        self.assertLess(partial["span_coverage_sym_a"], 0.1)
        self.assertEqual(con.execute("SELECT count(*) FROM joined").fetchone()[0], before)

    def test_zero_volume_and_all_only_residue_rows_leave_with_the_dropped_ticker(self):
        # A halted (volume 0) session and an adjustment=all-only session are never
        # byte-identical, so the old raw-equal DELETE left OLD behind as a sparse
        # phantom series spanning NEW's history.
        rows = self._shared(["OLD", "NEW"], count=100, start_day=0)
        rows += _identical(["OLD", "NEW"], 100, 50.0, volume=0.0)      # halted session
        rows += _identical(["OLD", "NEW"], 101, 0.0, raw=False)        # all-series only
        rows += self._shared(["OLD", "NEW"], count=100, start_day=102, price=300.0)
        rows += _identical(["NEW"], 400, 500.0)                        # successor keeps trading
        con = self._con(rows)
        report = coverage.dedupe_identity(con, {("OLD", "NEW")})
        detail = report["detail"][0]
        self.assertEqual((detail["kept"], detail["dropped"], detail["rule"]), ("NEW", "OLD", "rename_record"))
        self.assertEqual(detail["identical_sessions"], 200)
        self.assertEqual(detail["rows_removed"], 202)
        self.assertEqual(detail["residue_rows_removed"], 2)
        self.assertEqual(report["residue_rows_removed"], 2)
        self.assertEqual(con.execute("SELECT count(*) FROM joined WHERE symbol = 'OLD'").fetchone()[0], 0)
        self.assertEqual(con.execute("SELECT count(*) FROM joined WHERE symbol = 'NEW'").fetchone()[0], 203)


@unittest.skipUnless(HAS_DUCKDB, NEEDS_DUCKDB)
class RenameEvidenceTests(unittest.TestCase):
    def test_singular_and_plural_envelope_keys_are_both_loaded_and_counted(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_action_page(tmp, 2022, 0, {"corporate_actions": {
                "name_change": [{"old_symbol": "FB", "new_symbol": "META"}],
                "unit_splits": [{"old_symbol": "AAU", "new_symbol": "AA"}],
                "forward_split": [{"symbol": "NVDA", "ex_date": "2022-07-20"}],
            }})
            stats = {}
            pairs = coverage.load_rename_pairs(tmp, stats)
            self.assertEqual(pairs, {("FB", "META"), ("AAU", "AA")})
            self.assertEqual(stats["rename_pairs_loaded"], 2)
            self.assertEqual(stats["rename_pairs_by_kind"], {"name_change": 1, "unit_splits": 1})
            self.assertEqual(stats["rename_evidence"], "present")
            self.assertEqual(stats["other_action_kinds_seen"], {"forward_split": 1})

    def test_absent_corporate_actions_is_recorded_as_absent(self):
        stats = {}
        self.assertEqual(coverage.load_rename_pairs(None, stats), set())
        self.assertEqual(stats["rename_evidence"], "absent")
        self.assertEqual(stats["rename_pairs_loaded"], 0)

    def test_dedupe_report_carries_the_rename_evidence(self):
        import duckdb
        con = duckdb.connect()
        con.execute("CREATE TABLE joined (symbol VARCHAR, session_date DATE, raw_o DOUBLE, raw_h DOUBLE, "
                    "raw_l DOUBLE, raw_c DOUBLE, raw_v DOUBLE)")
        report = coverage.dedupe_identity(con, set(), frozenset(), {"rename_evidence": "absent",
                                                                    "rename_pairs_loaded": 0})
        self.assertEqual(report["rename_evidence"], "absent")
        self.assertEqual(report["pairs"], 0)

    def test_materialize_refuses_when_supplied_actions_yield_no_rename_pair(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows = [("AAA", "2020-01-02T05:00:00Z", 1, 2, 0.5, 1.5, 100, 3, 1.1)]
            write_csv_gz(os.path.join(tmp, "bars", "raw", "b00000.csv.gz"), rows)
            write_csv_gz(os.path.join(tmp, "bars", "all", "b00000.csv.gz"), rows)
            actions = os.path.join(tmp, "actions")
            os.makedirs(actions)
            write_action_page(actions, 2020, 0, {"corporate_actions": {"forward_split": [{"symbol": "AAA"}]}})
            write_actions_ledger(actions, "2020-01-01", "2020-12-31")
            ok, detail = coverage.materialize(tmp, corporate_actions_dir=actions)
            self.assertFalse(ok)
            self.assertIn("no rename pair", detail["reason"])
            self.assertFalse(os.path.exists(os.path.join(tmp, "daily.parquet")))

    def test_materialize_refuses_an_incomplete_corporate_actions_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows = [("AAA", "2020-01-02T05:00:00Z", 1, 2, 0.5, 1.5, 100, 3, 1.1)]
            write_csv_gz(os.path.join(tmp, "bars", "raw", "b00000.csv.gz"), rows)
            write_csv_gz(os.path.join(tmp, "bars", "all", "b00000.csv.gz"), rows)
            actions = os.path.join(tmp, "actions")
            os.makedirs(actions)
            write_action_page(actions, 2020, 0, {"corporate_actions": {
                "name_change": [{"old_symbol": "FB", "new_symbol": "META"}]}})
            write_actions_ledger(actions, "2020-01-01", "2021-12-31", skip_years=(2021,))
            ok, detail = coverage.materialize(tmp, corporate_actions_dir=actions)
            self.assertFalse(ok)
            self.assertIn("incomplete", detail["reason"])
            self.assertTrue(any("year=2021" in r for r in detail["corporate_actions_reasons"]))

    def test_corporate_actions_gate_accepts_a_complete_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_actions_ledger(tmp, "2020-01-01", "2021-12-31")
            ok, reasons = coverage.check_corporate_actions_complete(tmp)
            self.assertTrue(ok, reasons)
            write_actions_ledger(tmp, "2020-01-01", "2021-12-31", failed=2)
            ok, reasons = coverage.check_corporate_actions_complete(tmp)
            self.assertFalse(ok)


class CollectionResumeScopeTests(unittest.TestCase):
    """A completed batch may only be reused for the SAME request scope: widening --end
    once produced zero collection calls while plan.json advertised the wider window."""

    def _fixture(self, tmp):
        env_path = os.path.join(tmp, "env")
        with open(env_path, "w", encoding="utf-8") as handle:
            handle.write("APCA_API_KEY_ID=abc123\nAPCA_API_SECRET_KEY=def456\n")
        assets_path = os.path.join(tmp, "assets.json")
        with open(assets_path, "w", encoding="utf-8") as handle:
            json.dump([{"symbol": s, "class": "us_equity", "exchange": "NASDAQ", "status": "active", "id": s}
                       for s in ("AAA", "BBB", "CCC")], handle)
        return env_path, assets_path

    def _run(self, tmp, env_path, assets_path, end, out=None, extra=()):
        out = out or os.path.join(tmp, "out")
        argv = ["collect_daily.py", "--env-file", env_path, "--assets", assets_path, "--out", out,
                "--start", "2016-01-01", "--end", end, "--adjustments", "raw", "--batch-size", "2",
                "--workers", "1", *extra]
        calls = []

        def fake_run_batch(index, symbols, adjustment, args, headers, out_dir, ledger, prefix="b",
                           run_id=None, request_sha256=None):
            calls.append((index, adjustment, tuple(symbols)))
            ledger.write(event="batch_complete", adjustment=adjustment, batch=index,
                         label=f"{prefix}{index:05d}", series=prefix, run_id=run_id,
                         request_sha256=request_sha256, symbols=len(symbols),
                         symbols_sha256=collect_daily.symbols_digest(symbols), bars=1,
                         symbols_with_bars=len(symbols))
            return index, adjustment, True, 1

        with patch.object(collect_daily, "run_batch", fake_run_batch), patch.object(sys, "argv", argv):
            collect_daily.main()
        return calls, out

    def test_unchanged_rerun_resumes_with_zero_jobs(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_path, assets_path = self._fixture(tmp)
            first, out = self._run(tmp, env_path, assets_path, "2024-12-31")
            self.assertEqual(len(first), 2)
            second, _ = self._run(tmp, env_path, assets_path, "2024-12-31", out)
            self.assertEqual(second, [])

    def test_widened_end_refuses_instead_of_reusing_completions(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_path, assets_path = self._fixture(tmp)
            _, out = self._run(tmp, env_path, assets_path, "2024-12-31")
            with self.assertRaises(SystemExit) as caught:
                self._run(tmp, env_path, assets_path, "2026-09-18", out)
            message = str(caught.exception)
            self.assertIn("REFUSED", message)
            self.assertIn("end", message)
            self.assertIn("new --out", message)
            # the recorded plan still describes the scope that was actually collected
            with open(os.path.join(out, "plan.json"), encoding="utf-8") as handle:
                self.assertEqual(json.load(handle)["end"], "2024-12-31")

    def test_changed_feed_refuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_path, assets_path = self._fixture(tmp)
            _, out = self._run(tmp, env_path, assets_path, "2024-12-31")
            with self.assertRaises(SystemExit) as caught:
                self._run(tmp, env_path, assets_path, "2024-12-31", out, extra=["--feed", "iex"])
            self.assertIn("feed", str(caught.exception))

    def test_legacy_completion_without_a_fingerprint_still_resumes(self):
        plan = {"start": "2016-01-01", "end": "2024-12-31", "feed": "sip", "timeframe": "1Day",
                "page_limit": 10000, "adjustments": ["raw"], "batch_size": 2, "symbols_sha256": "d" * 64}
        digest = collect_daily.symbols_digest(["AAA", "BBB"])
        fingerprint = collect_daily.request_fingerprint(plan)
        legacy = {"symbols_sha256": digest, "request_sha256": None}
        self.assertTrue(collect_daily.batch_is_done(legacy, digest, fingerprint))
        self.assertFalse(collect_daily.batch_is_done(legacy, "other", fingerprint))
        scoped = {"symbols_sha256": digest, "request_sha256": fingerprint}
        self.assertTrue(collect_daily.batch_is_done(scoped, digest, fingerprint))
        self.assertFalse(collect_daily.batch_is_done(scoped, digest, "0" * 64))
        self.assertFalse(collect_daily.batch_is_done(None, digest, fingerprint))

    def test_scope_fingerprint_moves_with_every_scope_field(self):
        base = {"start": "2016-01-01", "end": "2024-12-31", "feed": "sip", "timeframe": "1Day",
                "page_limit": 10000, "adjustments": ["raw"], "batch_size": 2, "symbols_sha256": "d" * 64}
        for field, value in (("start", "2017-01-01"), ("end", "2026-09-18"), ("feed", "iex"),
                             ("timeframe", "1Hour"), ("page_limit", 5000), ("adjustments", ["raw", "all"]),
                             ("batch_size", 50), ("symbols_sha256", "e" * 64)):
            changed = dict(base, **{field: value})
            self.assertNotEqual(collect_daily.request_fingerprint(base),
                                collect_daily.request_fingerprint(changed), field)
            self.assertEqual([c["field"] for c in collect_daily.scope_conflicts(base, changed)], [field])
        self.assertEqual(collect_daily.scope_conflicts(base, dict(base, created_at="later")), [])


@unittest.skipUnless(HAS_DUCKDB, NEEDS_DUCKDB)
class LedgerScopeVerificationTests(unittest.TestCase):
    def test_batch_complete_from_another_scope_is_refused(self):
        plan = {"adjustments": ["raw"], "batches": 1, "request_sha256": "a" * 64}
        events = [{"event": "batch_complete", "adjustment": "raw", "batch": 0, "request_sha256": "b" * 64},
                  {"event": "run_complete", "failed": 0}]
        ok, reasons = coverage.check_ledger_complete(plan, events)
        self.assertFalse(ok)
        self.assertTrue(any("different request scope" in r for r in reasons))

    def test_matching_and_legacy_fingerprints_are_accepted(self):
        plan = {"adjustments": ["raw"], "batches": 1, "request_sha256": "a" * 64}
        matching = [{"event": "batch_complete", "adjustment": "raw", "batch": 0, "request_sha256": "a" * 64},
                    {"event": "run_complete", "failed": 0}]
        self.assertTrue(coverage.check_ledger_complete(plan, matching)[0])
        legacy = [{"event": "batch_complete", "adjustment": "raw", "batch": 0},
                  {"event": "run_complete", "failed": 0}]
        self.assertTrue(coverage.check_ledger_complete(plan, legacy)[0])


@unittest.skipUnless(HAS_DUCKDB, NEEDS_DUCKDB)
class AttemptScopedEvidenceTests(unittest.TestCase):
    """A retried batch leaves two attempts in the append-only ledger. The completing
    attempt is the evidence; the earlier one is superseded, not a violation."""

    def _pages(self, run_id, pages, batch="b00007"):
        return [{"adjustment": "raw", "batch": batch, "run_id": run_id, "page": p,
                 "next_page_token_present": p != pages[-1], "bytes": 10, "bars": 5,
                 "file": collect_daily.page_file_name(batch, run_id, p), "sha256": "0" * 64}
                for p in pages]

    def test_retried_batch_is_superseded_not_a_violation(self):
        pages = self._pages("r1", [0, 1]) + self._pages("r2", [0, 1, 2])
        batches = [{"event": "batch_complete", "adjustment": "raw", "batch": 7, "series": "b",
                    "label": "b00007", "run_id": "r2", "bars": 15}]
        result = coverage.pagination_proof(pages, batches)
        self.assertEqual(result["violations"], [])
        self.assertEqual(result["symbol_groups_checked"], 1)
        self.assertEqual(len(result["superseded_attempts"]), 1)
        self.assertEqual(result["superseded_attempts"][0]["run_id"], "r1")
        self.assertEqual(result["superseded_attempts"][0]["pages"], [0, 1])

    def test_a_genuine_gap_in_the_completing_attempt_is_still_a_violation(self):
        pages = self._pages("r1", [0, 1]) + self._pages("r2", [0, 2])
        batches = [{"event": "batch_complete", "adjustment": "raw", "batch": 7, "series": "b",
                    "label": "b00007", "run_id": "r2", "bars": 15}]
        result = coverage.pagination_proof(pages, batches)
        self.assertEqual(len(result["violations"]), 1)
        self.assertEqual(result["violations"][0]["run_id"], "r2")

    def test_bisect_children_belong_to_their_parent_batch_attempt(self):
        pages = self._pages("r1", [0], batch="b00007a") + self._pages("r2", [0], batch="b00007a")
        batches = [{"event": "batch_complete", "adjustment": "raw", "batch": 7, "series": "b",
                    "label": "b00007", "run_id": "r2", "bars": 3}]
        result = coverage.pagination_proof(pages, batches)
        self.assertEqual(result["violations"], [])
        self.assertEqual([a["run_id"] for a in result["superseded_attempts"]], ["r1"])

    def test_legacy_events_without_run_ids_are_checked_as_one_group(self):
        pages = [{"adjustment": "raw", "batch": "b00000", "page": 0, "next_page_token_present": True,
                  "bytes": 1, "bars": 1},
                 {"adjustment": "raw", "batch": "b00000", "page": 1, "next_page_token_present": False,
                  "bytes": 1, "bars": 1}]
        batches = [{"event": "batch_complete", "adjustment": "raw", "batch": 0, "series": "b", "bars": 2}]
        result = coverage.pagination_proof(pages, batches)
        self.assertEqual(result["violations"], [])
        self.assertEqual(result["superseded_attempts"], [])

    def test_attempt_scoped_page_names_do_not_collide(self):
        self.assertNotEqual(collect_daily.page_file_name("b00007", "r1", 0),
                            collect_daily.page_file_name("b00007", "r2", 0))
        self.assertEqual(collect_daily.page_file_name("b00007", None, 0), "b00007-p0000.json.gz")

    def test_collection_totals_count_the_completing_attempt_only(self):
        import duckdb
        with tempfile.TemporaryDirectory() as tmp:
            write_csv_gz(os.path.join(tmp, "bars", "raw", "b00007.csv.gz"),
                         [("AAA", "2020-01-02T05:00:00Z", 1, 2, 0.5, 1.5, 100, 3, 1.1)] * 15)
            events = self._pages("r1", [0, 1]) + self._pages("r2", [0, 1, 2])
            for event in events:
                event["event"] = "page"
            events += [{"event": "batch_failed", "adjustment": "raw", "batch": 7, "series": "b",
                        "label": "b00007", "run_id": "r1"},
                       {"event": "batch_complete", "adjustment": "raw", "batch": 7, "series": "b",
                        "label": "b00007", "run_id": "r2", "bars": 15}]
            with open(os.path.join(tmp, "ledger.jsonl"), "w", encoding="utf-8") as handle:
                for event in events:
                    handle.write(json.dumps(event) + "\n")
            plan = {"adjustments": ["raw"], "batches": 1}
            con = duckdb.connect()
            section = coverage.build_collection_section(con, tmp, plan, events, 1.0)
            self.assertEqual(section["per_adjustment_pages"]["raw"]["pages"], 3)
            self.assertEqual(section["per_adjustment_pages"]["raw"]["superseded_pages"], 2)
            self.assertEqual(section["row_totals"]["ledger_totals"]["raw"], 15)
            self.assertTrue(section["row_totals"]["match"])
            self.assertEqual(section["pagination_proof"]["violations"], [])

    def test_pages_of_an_earlier_completed_attempt_are_superseded(self):
        # Two COMPLETED attempts (9 then 15 bars): page totals used to report 24 effective
        # bars beside a 15-bar batch total, with nothing classified as superseded.
        def page(run_id, bars):
            return {"event": "page", "adjustment": "raw", "batch": "b00007", "page": 0, "run_id": run_id,
                    "bars": bars, "bytes": 10, "next_page_token_present": False}
        batch_events = [{"event": "batch_complete", "adjustment": "raw", "batch": 7, "series": "b", "run_id": r}
                        for r in ("r1", "r2")]
        checked, superseded = coverage.partition_attempts([page("r1", 9), page("r2", 15)], batch_events)
        self.assertEqual(sum(e["bars"] for items in checked.values() for e in items), 15)
        self.assertEqual(sum(e["bars"] for items in superseded.values() for e in items), 9)

    def test_two_completions_for_one_batch_do_not_double_count(self):
        import duckdb
        with tempfile.TemporaryDirectory() as tmp:
            write_csv_gz(os.path.join(tmp, "bars", "raw", "b00007.csv.gz"),
                         [("AAA", "2020-01-02T05:00:00Z", 1, 2, 0.5, 1.5, 100, 3, 1.1)] * 15)
            events = [{"event": "batch_complete", "adjustment": "raw", "batch": 7, "series": "b",
                       "label": "b00007", "run_id": "r1", "bars": 9},
                      {"event": "batch_complete", "adjustment": "raw", "batch": 7, "series": "b",
                       "label": "b00007", "run_id": "r2", "bars": 15}]
            with open(os.path.join(tmp, "ledger.jsonl"), "w", encoding="utf-8") as handle:
                for event in events:
                    handle.write(json.dumps(event) + "\n")
            section = coverage.build_collection_section(duckdb.connect(), tmp, {"adjustments": ["raw"],
                                                                                "batches": 1}, events, 1.0)
            self.assertEqual(section["per_adjustment_batches"]["raw"]["complete"], 1)
            self.assertEqual(section["per_adjustment_batches"]["raw"]["superseded"], 1)
            self.assertEqual(section["row_totals"]["ledger_totals"]["raw"], 15)
            self.assertTrue(section["row_totals"]["match"])


@unittest.skipUnless(HAS_DUCKDB, NEEDS_DUCKDB)
class UniverseDenominatorTests(unittest.TestCase):
    """Bar counts are computed over daily.parquet, which holds the supplement too, so the
    denominators and the survivorship histogram must say which basis they are on."""

    def test_supplement_symbols_are_reported_and_counted_as_known_delisted(self):
        import duckdb
        with tempfile.TemporaryDirectory() as tmp:
            rows = []
            for day, symbol in ((2, "SPY"), (3, "SPY")):
                rows.append((symbol, f"2020-01-0{day}T05:00:00Z", 1, 1, 1, 1, 1, 1, 1))
            rows.append(("AAA", "2020-01-02T05:00:00Z", 1, 1, 1, 1, 1, 1, 1))   # active main-list name
            rows.append(("DEAD", "2020-01-02T05:00:00Z", 1, 1, 1, 1, 1, 1, 1))  # inactive main-list name
            rows.append(("TWTR", "2020-01-03T05:00:00Z", 1, 1, 1, 1, 1, 1, 1))  # supplement only
            write_csv_gz(os.path.join(tmp, "bars", "raw", "b00000.csv.gz"), rows)
            write_csv_gz(os.path.join(tmp, "bars", "all", "b00000.csv.gz"), rows)
            ok, detail = coverage.materialize(tmp)
            self.assertTrue(ok, detail)
            con = duckdb.connect()
            con.execute(f"CREATE VIEW daily AS SELECT * FROM read_parquet('{detail['path']}')")
            identities = {"SPY": [{"status": "active", "exchange": "ARCA"}],
                          "AAA": [{"status": "active", "exchange": "NASDAQ"}],
                          "DEAD": [{"status": "inactive", "exchange": "NASDAQ"}]}
            sessions = [r[0] for r in con.execute(
                "SELECT DISTINCT session_date FROM daily WHERE symbol='SPY' ORDER BY 1").fetchall()]
            section = coverage.build_universe_section(con, identities, sessions, {"TWTR"})
            self.assertEqual(section["requested_symbols_main_list"], 3)
            self.assertEqual(section["requested_symbols_supplement"], 1)
            self.assertEqual(section["requested_symbols_combined"], 4)
            self.assertEqual(section["inactive_last_bar_year_histogram"], {"2020": 1})
            self.assertEqual(section["supplement_last_bar_year_histogram"], {"2020": 1})
            self.assertEqual(section["known_inactive_or_supplement_last_bar_year_histogram"], {"2020": 2})
            # without the supplement the survivorship measure understates by exactly TWTR
            bare = coverage.build_universe_section(con, identities, sessions)
            self.assertEqual(bare["known_inactive_or_supplement_last_bar_year_histogram"], {"2020": 1})


class CorporateActionsResumeScopeTests(unittest.TestCase):
    def test_a_narrower_recorded_window_is_not_treated_as_done(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "ledger.jsonl")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(json.dumps({"event": "year_complete", "year": 2026, "types_key": "tk",
                                         "window_start": "2026-01-01", "window_end": "2026-06-30"}) + "\n")
            windows = dict((year, (start, end))
                           for year, start, end in corporate_actions.year_windows("2026-01-01", "2026-09-21"))
            self.assertEqual(corporate_actions.completed_years(path, "tk", windows), set())
            same = {2026: ("2026-01-01", "2026-06-30")}
            self.assertEqual(corporate_actions.completed_years(path, "tk", same), {2026})
            # legacy records carry no window at all and still resume
            self.assertEqual(corporate_actions.completed_years(path, "tk"), {2026})

    def test_legacy_year_complete_without_a_window_still_resumes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "ledger.jsonl")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(json.dumps({"event": "year_complete", "year": 2026, "types_key": "tk"}) + "\n")
            windows = {2026: ("2026-01-01", "2026-09-21")}
            self.assertEqual(corporate_actions.completed_years(path, "tk", windows), {2026})

    def test_changed_window_refuses_instead_of_rewriting_the_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "plan.json"), "w", encoding="utf-8") as handle:
                json.dump({"start": "2016-01-01", "end": "2026-06-30", "types": ["name_change"],
                           "types_key": "tk", "page_limit": 1000}, handle)
            plan = {"start": "2016-01-01", "end": "2026-09-21", "types": ["name_change"],
                    "types_key": "tk", "page_limit": 1000}
            with open(os.path.join(tmp, "plan.json"), encoding="utf-8") as handle:
                existing = json.load(handle)
            conflicts = corporate_actions.scope_conflicts(existing, plan)
            self.assertEqual([c["field"] for c in conflicts], ["end"])
            env_path = os.path.join(tmp, "env")
            with open(env_path, "w", encoding="utf-8") as handle:
                handle.write("APCA_API_KEY_ID=abc123\nAPCA_API_SECRET_KEY=def456\n")
            with self.assertRaises(SystemExit) as caught:
                corporate_actions.collect(env_path, tmp, "2016-01-01", "2026-09-21", False)
            self.assertIn("REFUSED", str(caught.exception))
            with open(os.path.join(tmp, "plan.json"), encoding="utf-8") as handle:
                self.assertEqual(json.load(handle)["end"], "2026-06-30")


class CorporateActionsSummaryBasisTests(unittest.TestCase):
    def test_actions_are_bucketed_by_the_queried_window_not_a_stray_earlier_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_action_page(tmp, 2020, 0, {"corporate_actions": {"forward_split": [
                {"ex_date": "2020-01-03", "record_date": "2019-12-30", "payable_date": "2020-01-06"}]}})
            summary = corporate_actions.summarize_dict(tmp)
            self.assertEqual(summary["per_type_per_year_counts"]["forward_split"], {"2020": 1})
            self.assertEqual(summary["date_field_by_type"]["forward_split"]["primary"], "ex_date")
            self.assertEqual(summary["earliest_by_type"]["forward_split"], "2020-01-03")
            self.assertEqual(summary["secondary_min_of_all_dates"]["earliest_by_type"]["forward_split"],
                             "2019-12-30")
            self.assertIn("request window", summary["year_basis"])

    def test_the_named_date_field_is_reported_per_type(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_action_page(tmp, 2021, 0, {"corporate_actions": {
                "name_change": [{"process_date": "2021-05-04"}],
                "cash_merger": [{"effective_date": "2021-07-01", "payable_date": "2021-07-09"}],
            }})
            summary = corporate_actions.summarize_dict(tmp)
            self.assertEqual(summary["date_field_by_type"]["name_change"]["primary"], "process_date")
            self.assertEqual(summary["date_field_by_type"]["cash_merger"]["primary"], "effective_date")
            self.assertEqual(summary["per_type_per_year_counts"]["name_change"], {"2021": 1})

    def test_an_action_with_no_date_is_still_counted_in_its_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_action_page(tmp, 2019, 0, {"corporate_actions": {"redemption": [{"symbol": "AAA"}]}})
            summary = corporate_actions.summarize_dict(tmp)
            self.assertEqual(summary["per_type_per_year_counts"]["redemption"], {"2019": 1})
            self.assertNotIn("redemption", summary["date_field_by_type"])


if __name__ == "__main__":
    unittest.main()
