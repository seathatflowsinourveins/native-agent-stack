"""Local integration checks for the broad-universe coverage/corporate-actions
tooling. Synthetic fixtures only: no network, no credentials, no real dataset.
Loaded the same way as tests/test_adaptive_market_research.py (importlib spec
from the blueprint path)."""
import csv
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock

BASE = Path(__file__).resolve().parents[1] / "blueprints/us-equities/broad-universe"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, BASE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


coverage = _load("coverage")
corporate_actions = _load("corporate_actions")


def write_csv_gz(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with gzip.open(path, "wt", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["symbol", "t", "o", "h", "l", "c", "v", "n", "vw"])
        writer.writerows(rows)


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


if __name__ == "__main__":
    unittest.main()
