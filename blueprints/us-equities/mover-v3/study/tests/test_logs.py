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
            logs.append_line(p, synth.calendar_line("2027-01-11"))
            run_log.append({"utc_start": "t1", "amendment_files": {"cal": logs.file_state(p)}})
            logs.append_line(p, synth.calendar_line("2027-03-01"))
            self.assertEqual(logs.check_amendment_files({"cal": p}, run_log), [])
            p.write_text(p.read_text().replace("2027-01-11", "2027-01-12"))
            self.assertTrue(logs.check_amendment_files({"cal": p}, run_log))

    def test_calendar_line_must_reach_main_before_0930_of_its_session(self):
        cal = synth.calendar("2026-06-01", "2027-06-30")
        lines = [synth.calendar_line("2027-01-12")]
        ok = logs.check_calendar_amendments(lines, {0: cal.at("2027-01-11", "20:00")}, cal, "2026-10-01")
        self.assertEqual(ok, [])
        late = logs.check_calendar_amendments(lines, {0: cal.at("2027-01-12", "09:30")}, cal, "2026-10-01")
        self.assertTrue(late)
        early = logs.check_calendar_amendments([synth.calendar_line("2026-09-01")], {0: 0.0}, cal, "2026-10-01")
        self.assertTrue(early)
        # review round 15, amendment format: a line without the format's fields, and a date that is no session
        loose = logs.check_calendar_amendments([{"kind": "remove_session", "session": "2027-01-12", "source": "x"}],
                                               {0: 0.0}, cal, "2026-10-01")
        self.assertIn("schema_version", loose[0])
        weekend = logs.check_calendar_amendments([synth.calendar_line("2027-01-16")], {0: 0.0}, cal, "2026-10-01")
        self.assertIn("not a session", weekend[0])

    def test_fee_line_must_reach_main_before_the_first_use(self):
        line = [synth.fee_line("finra_taf_covered_equity", "2027-01-01", "2027-12-31", usd_per_share=0.0002,
                               max_usd_per_trade=10.0)]
        self.assertEqual(logs.check_fee_amendments(line, {0: 100.0}, {0: 200.0}, "2026-10-01"), [])
        self.assertTrue(logs.check_fee_amendments(line, {0: 300.0}, {0: 200.0}, "2026-10-01"))
        nocap = [dict(line[0], max_usd_per_trade=None)]
        self.assertTrue(logs.check_fee_amendments(nocap, {0: 100.0}, {}, "2026-10-01"))
        # review round 15, amendment format: the former line shape ('rate', 'max_per_trade', no source) is refused
        old = [{"kind": "finra_taf", "from": "2027-01-01", "to": "2027-12-31", "usd_per_share": 0.0002,
                "max_per_trade": 10.0}]
        self.assertTrue(logs.check_fee_amendments(old, {0: 100.0}, {}, "2026-10-01"))
        # an open-ended line (to null) has a first use like any other
        open_line = [synth.fee_line("sec_section31", "2027-06-01", None, usd_per_million=21.0)]
        use = logs.fee_first_use(open_line, [{"purpose": "read", "utc_start": "2028-01-20T21:00:00Z",
                                              "fee_span": ["2027-01-04", "2028-01-07"]}])
        self.assertIn(0, use)


    def test_a_read_uses_the_fee_rows_of_its_terminal_search_windows(self):
        """Review round 13, Codex P2: a read's trades exit, and pay sale fees, through 5 sessions after the window's
        last session. Its line's fee_span covers them, so a fee line for those dates has a first-use deadline;
        before the fix only [N0, last] counted and a line appended after a failed read was accepted on its retry."""
        fee = [synth.fee_line("finra_taf_covered_equity", "2028-01-04", "2028-01-06", usd_per_share=0.0002,
                              max_usd_per_trade=10.0)]
        read = {"stage": "holdout", "purpose": "read", "utc_start": "2028-01-20T21:00:00Z",
                "sessions": ["2027-01-04", "2027-12-31"], "fee_span": ["2027-01-04", "2028-01-07"]}
        use = logs.fee_first_use(fee, [read])
        self.assertIn(0, use)
        self.assertTrue(logs.check_fee_amendments(fee, {0: use[0] + 60}, use, "2026-10-01"))
        # a line without a fee_span (a count) is judged by its sessions
        self.assertEqual(logs.fee_first_use(fee, [dict(read, purpose="count", fee_span=None)]), {})


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
