"""Append-only files outside the tree: amendment prefixes, the amendment commit-time rule (R8-10), run-log fields
with protocol_sha256 (R8-2), one results file per stage, and the atomic write."""
import json
import os
import tempfile
import unittest
from pathlib import Path

from core import canon, logs
from tests import synth


class Amendments(unittest.TestCase):
    def test_appended_is_accepted_edited_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "session-calendar-amendments.jsonl"
            p.write_text("")
            run_log = [{"utc_start": "t0", "amendment_files": {"cal": logs.file_state(p)}}]
            logs.append_line(p, {"kind": "remove_session", "session": "2027-01-09", "source": "notice"})
            run_log.append({"utc_start": "t1", "amendment_files": {"cal": logs.file_state(p)}})
            logs.append_line(p, {"kind": "remove_session", "session": "2027-03-01", "source": "notice"})
            self.assertEqual(logs.check_amendment_files({"cal": p}, run_log), [])
            p.write_text(p.read_text().replace("2027-01-09", "2027-01-10"))
            self.assertTrue(logs.check_amendment_files({"cal": p}, run_log))

    def test_calendar_line_must_reach_main_before_0930_of_its_session(self):
        cal = synth.calendar("2026-06-01", "2027-06-30")
        lines = [{"kind": "remove_session", "session": "2027-01-12", "source": "NYSE notice"}]
        ok = logs.check_calendar_amendments(lines, {0: cal.at("2027-01-11", "20:00")}, cal, "2026-10-01")
        self.assertEqual(ok, [])
        late = logs.check_calendar_amendments(lines, {0: cal.at("2027-01-12", "09:30")}, cal, "2026-10-01")
        self.assertTrue(late)
        early = logs.check_calendar_amendments([{"kind": "remove_session", "session": "2026-09-01", "source": "x"}],
                                               {0: 0.0}, cal, "2026-10-01")
        self.assertTrue(early)

    def test_fee_line_must_reach_main_before_the_first_use(self):
        line = [{"kind": "finra_taf", "from": "2027-01-01", "to": "2027-12-31", "usd_per_share": 0.0002,
                 "max_per_trade": 10.0}]
        self.assertEqual(logs.check_fee_amendments(line, {0: 100.0}, {0: 200.0}, "2026-10-01"), [])
        self.assertTrue(logs.check_fee_amendments(line, {0: 300.0}, {0: 200.0}, "2026-10-01"))
        nocap = [dict(line[0], max_per_trade=None)]
        self.assertTrue(logs.check_fee_amendments(nocap, {0: 100.0}, {}, "2026-10-01"))


class RunLog(unittest.TestCase):
    def test_required_fields_include_protocol_sha256(self):
        self.assertIn("protocol_sha256", logs.RUN_LOG_FIELDS)
        self.assertEqual(logs.check_run_log_line({f: None for f in logs.RUN_LOG_FIELDS}), [])
        self.assertTrue(logs.check_run_log_line({"stage": "validation"}))

    def test_a_second_results_file_for_a_stage_is_refused(self):
        log = [{"stage": "validation", "purpose": "evaluate", "status": "failed", "results_sha256": None},
               {"stage": "validation", "purpose": "evaluate", "status": "complete", "results_sha256": "a"}]
        self.assertEqual(logs.governing_results(log, "validation")["results_sha256"], "a")
        log.append({"stage": "validation", "purpose": "evaluate", "status": "complete", "results_sha256": "b"})
        with self.assertRaises(logs.AppendOnlyViolation):
            logs.governing_results(log, "validation")


class AtomicWrite(unittest.TestCase):
    def test_write_once_and_refuse_a_second(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "results.json"
            digest = canon.atomic_write_results(p, {"a": 1.0, "b": float("nan")})
            self.assertEqual(canon.sha256_file(p), digest)
            self.assertIsNone(json.loads(p.read_text())["b"])
            self.assertFalse(Path(str(p) + ".tmp").exists())
            self.assertEqual(oct(os.stat(p).st_mode & 0o777), "0o600")
            with self.assertRaises(canon.ResultsExist):
                canon.atomic_write_results(p, {"a": 2})


if __name__ == "__main__":
    unittest.main()
