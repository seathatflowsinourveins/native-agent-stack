"""populations.session_calendar and session_times: early closes, amendments, the freeze session and N0."""
import json
import tempfile
import unittest
from pathlib import Path

from core import chronology as CH
from core.calendar import Calendar, build_calendar
from tests import synth

EARLY = ("2017-07-03", "2017-11-24", "2018-11-23", "2019-12-24", "2020-11-27")


class CalendarTests(unittest.TestCase):
    def setUp(self):
        self.cal = synth.calendar()

    def test_2016_2020_early_closes_and_1555_stamp(self):
        for d in EARLY:
            self.assertTrue(self.cal.is_early_close(d), d)
            self.assertEqual(self.cal.close(d), self.cal.at(d, "13:00"))
            self.assertEqual(self.cal.stamp_1555(d), self.cal.at(d, "12:55"))
        self.assertFalse(self.cal.is_early_close("2017-07-05"))
        self.assertEqual(self.cal.stamp_1555("2017-07-05"), self.cal.at("2017-07-05", "15:55"))

    def test_calendar_starts_early_enough_for_2016_lookbacks(self):
        self.assertIsNotNone(self.cal.offset("2016-01-04", -60))
        self.assertEqual(self.cal.offset("2016-01-04", -1), "2015-12-31")

    def test_refuses_other_exchange_calendars_version(self):
        import exchange_calendars
        self.assertEqual(exchange_calendars.__version__, "4.13.2")
        body = build_calendar("2020-01-02", "2020-01-10")
        self.assertEqual((body["source"]["package"], body["source"]["version"]), ("exchange_calendars", "4.13.2"))
        self.assertEqual([s[0] for s in body["sessions"]][:3], ["2020-01-02", "2020-01-03", "2020-01-06"])

    def test_removed_session_amendment_shifts_the_holdout_count(self):
        body = build_calendar("2026-01-02", "2028-06-30")
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "session-calendar.json"
            amend = Path(tmp) / "session-calendar-amendments.jsonl"
            base.write_text(json.dumps(body))
            amend.write_text("")
            cal0 = Calendar.from_files(base, amend)
            n0 = "2026-11-02"
            seg0 = CH.holdout_segment(cal0, n0)
            removed = cal0.offset(n0, 100)
            amend.write_text(json.dumps(synth.calendar_line(removed)) + "\n")
            with self.assertRaises(ValueError):            # an amendment applies only with the freeze session known
                Calendar.from_files(base, amend)
            with self.assertRaises(ValueError):            # and never to a session before it (review round 9, F5)
                Calendar.from_files(base, amend, freeze_session=cal0.offset(removed, 1))
            cal1 = Calendar.from_files(base, amend, freeze_session="2026-10-05")
            seg1 = CH.holdout_segment(cal1, n0)
            self.assertFalse(cal1.is_session(removed))
            self.assertEqual(len(cal1.range(*seg1)), 252)
            self.assertEqual(cal1.offset(seg0[1], 1), seg1[1])

    def test_freeze_session_and_n0(self):
        cal = Calendar.from_document(build_calendar("2026-09-01", "2027-03-31"))
        # a Saturday freeze commit: the freeze session is Monday's
        sat = cal.at("2026-09-26", "12:00") if cal.is_session("2026-09-26") else \
            synth.datetime(2026, 9, 26, 12, tzinfo=synth.ET).timestamp()
        fs = CH.freeze_session(cal, sat)
        self.assertEqual(fs, "2026-09-28")
        # a commit after the open belongs to the next session
        self.assertEqual(CH.freeze_session(cal, cal.at("2026-09-28", "10:00")), "2026-09-29")
        self.assertEqual(CH.n0(cal, sat), cal.offset("2026-09-28", 40))
        self.assertEqual(len(cal.range(cal.offset(fs, 1), CH.n0(cal, sat))), 40)


class PinnedCalendarFile(unittest.TestCase):
    """Review round 15, N01: the committed data/session-calendar.json loads in its own schema (the former loader
    expected a {"d", "open", "close"} dictionary per session and raised on the committed columnar rows), and it
    reaches the study's farthest lookback (t-60 of 2016-01-04; the calendar reviewed at b1655799 began 2016-01-04)."""

    PATH = Path(__file__).resolve().parents[2] / "data" / "session-calendar.json"

    def test_the_committed_calendar_loads_and_reaches_the_lookback(self):
        from core.calendar import check_study_reach
        cal = Calendar.from_files(self.PATH, self.PATH.with_name("session-calendar-amendments.jsonl"))
        check_study_reach(cal)
        self.assertEqual(cal.days[0], "2015-09-01")
        self.assertEqual(cal.offset("2016-01-04", -60), "2015-10-07")
        for d in EARLY + ("2015-11-27", "2015-12-24"):
            self.assertTrue(cal.is_early_close(d), d)
            self.assertEqual(cal.stamp_1555(d), cal.at(d, "12:55"))
        self.assertEqual(cal.close("2020-03-16"), cal.at("2020-03-16", "16:00"))

    def test_the_committed_rows_equal_the_study_builder(self):
        doc = json.loads(self.PATH.read_text())
        built = build_calendar(doc["requested_range"]["start"], doc["requested_range"]["end"])
        # assertTrue, not assertEqual: a diff of two 3,854-row lists would take minutes to render
        self.assertTrue(built["sessions"] == doc["sessions"], "the builder's rows differ from the committed file's")
        self.assertEqual(built["columns"], doc["columns"])

    def test_the_former_format_a_short_calendar_and_inconsistent_rows_are_refused(self):
        from core.calendar import CalendarSchemaError, check_study_reach
        doc = json.loads(self.PATH.read_text())
        old = {"schema_version": 1, "sessions": [{"d": r[0], "open": r[3], "close": r[4]} for r in doc["sessions"]]}
        with self.assertRaises(CalendarSchemaError):
            Calendar.from_document(old)
        short = Calendar.from_document(build_calendar("2016-01-04", "2016-12-30"))
        with self.assertRaises(CalendarSchemaError):
            check_study_reach(short)
        bad = json.loads(self.PATH.read_text())
        i = next(k for k, r in enumerate(bad["sessions"]) if r[0] == "2019-12-24")
        bad["sessions"][i][5] = False                             # an early close not flagged
        with self.assertRaises(CalendarSchemaError):
            Calendar.from_document(bad)
        bad = json.loads(self.PATH.read_text())
        bad["sessions"][10][3] = "2015-09-15T13:31:00Z"          # UTC and ET instants differ
        with self.assertRaises(CalendarSchemaError):
            Calendar.from_document(bad)
        bad = json.loads(self.PATH.read_text())
        bad["session_count"] += 1
        with self.assertRaises(CalendarSchemaError):
            Calendar.from_document(bad)


if __name__ == "__main__":
    unittest.main()
