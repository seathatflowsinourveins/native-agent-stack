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
        self.assertEqual(body["source"], "exchange_calendars 4.13.2 XNYS")
        self.assertEqual([s["d"] for s in body["sessions"]][:3], ["2020-01-02", "2020-01-03", "2020-01-06"])

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
            amend.write_text(json.dumps({"kind": "remove_session", "session": removed,
                                         "source": "https://www.nyse.com/ (synthetic notice)"}) + "\n")
            cal1 = Calendar.from_files(base, amend)
            seg1 = CH.holdout_segment(cal1, n0)
            self.assertFalse(cal1.is_session(removed))
            self.assertEqual(len(cal1.range(*seg1)), 252)
            self.assertEqual(cal1.offset(seg0[1], 1), seg1[1])

    def test_freeze_session_and_n0(self):
        cal = Calendar(build_calendar("2026-09-01", "2027-03-31")["sessions"])
        # a Saturday freeze commit: the freeze session is Monday's
        sat = cal.at("2026-09-26", "12:00") if cal.is_session("2026-09-26") else \
            synth.datetime(2026, 9, 26, 12, tzinfo=synth.ET).timestamp()
        fs = CH.freeze_session(cal, sat)
        self.assertEqual(fs, "2026-09-28")
        # a commit after the open belongs to the next session
        self.assertEqual(CH.freeze_session(cal, cal.at("2026-09-28", "10:00")), "2026-09-29")
        self.assertEqual(CH.n0(cal, sat), cal.offset("2026-09-28", 40))
        self.assertEqual(len(cal.range(cal.offset(fs, 1), CH.n0(cal, sat))), 40)


if __name__ == "__main__":
    unittest.main()
