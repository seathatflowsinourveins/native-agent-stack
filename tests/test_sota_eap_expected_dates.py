"""SYN: point-in-time expected announcement dates for the EAP study (synthetic fixtures only)."""
import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

BASE = Path(__file__).resolve().parents[1] / "blueprints/us-equities/sota-mover/eap"


sys.path.insert(0, str(BASE))
import expected_dates as E  # noqa: E402



def weekdays(start, end):
    d, out = start, []
    while d <= end:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


SESSIONS = E.sessions_2015() + weekdays(date(2016, 1, 4), date(2019, 12, 31))


def utc_stamp(eastern_wallclock):
    """Eastern wall-clock 'YYYY-MM-DDTHH:MM:SS' -> the SEC JSON form (UTC with Z)."""
    local = datetime.fromisoformat(eastern_wallclock).replace(tzinfo=ZoneInfo("America/New_York"))
    return local.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def row(accepted, form="8-K", items="2.02,9.01", acc=None, cik="0000000001", report_date=None):
    """``accepted`` is Eastern wall-clock time; the row carries it as SEC's UTC string."""
    return {"cik": cik, "accession": acc or f"acc-{accepted}-{form}", "form": form, "items": items,
            "acceptance": utc_stamp(accepted), "report_date": report_date}


def quarterly(year_months, day=20, hour="07:30:00"):
    return [row(f"{y}-{m:02d}-{day:02d}T{hour}") for y, m in year_months]


class Rollover(unittest.TestCase):
    def test_before_close_same_session(self):
        self.assertEqual(E.effective_session(datetime(2016, 3, 2, 15, 59, 59), SESSIONS), date(2016, 3, 2))
        self.assertEqual(E.effective_session(datetime(2016, 3, 2, 6, 0), SESSIONS), date(2016, 3, 2))

    def test_at_or_after_close_rolls_to_next_session(self):
        self.assertEqual(E.effective_session(datetime(2016, 3, 2, 16, 0), SESSIONS), date(2016, 3, 3))
        self.assertEqual(E.effective_session(datetime(2016, 3, 4, 16, 5), SESSIONS), date(2016, 3, 7))  # Friday -> Monday

    def test_weekend_and_holiday_roll_forward(self):
        self.assertEqual(E.effective_session(datetime(2016, 3, 5, 10, 0), SESSIONS), date(2016, 3, 7))
        self.assertEqual(E.effective_session(datetime(2015, 11, 26, 9, 0), SESSIONS), date(2015, 11, 27))  # Thanksgiving

    def test_after_close_on_month_end_moves_month(self):
        ev, tally = E.announcement_events([row("2016-01-29T17:10:00")], SESSIONS)
        self.assertEqual(ev[0].session, date(2016, 2, 1))
        self.assertEqual(ev[0].month, (2016, 2))
        self.assertEqual(tally["rolled_to_next_session"], 1)

    def test_acceptance_utc_converted_to_eastern(self):
        # Observed pairs from the tzcheck sample: JSON UTC vs SGML header Eastern (EST and EDT).
        self.assertEqual(E.parse_acceptance("2017-11-17T16:03:24.000Z"), datetime(2017, 11, 17, 11, 3, 24))
        self.assertEqual(E.parse_acceptance("2019-05-08T11:45:26.000Z"), datetime(2019, 5, 8, 7, 45, 26))
        self.assertEqual(E.parse_acceptance("2023-09-11T01:36:31.000Z"), datetime(2023, 9, 10, 21, 36, 31))
        with self.assertRaises(ValueError):
            E.parse_acceptance("2024-01-25T16:05:32")

    def test_utc_evening_is_after_close_eastern(self):
        # 20:30Z in winter is 15:30 ET (same session); 21:05Z is 16:05 ET (next session).
        self.assertEqual(E.effective_session(E.parse_acceptance("2016-03-02T20:30:00.000Z"), SESSIONS), date(2016, 3, 2))
        self.assertEqual(E.effective_session(E.parse_acceptance("2016-03-02T21:05:00.000Z"), SESSIONS), date(2016, 3, 3))
        # 20:05Z in summer is 16:05 ET.
        self.assertEqual(E.effective_session(E.parse_acceptance("2016-07-06T20:05:00.000Z"), SESSIONS), date(2016, 7, 7))


class Announcements(unittest.TestCase):
    def test_only_original_item_202(self):
        rows = [row("2016-02-10T08:00:00"), row("2016-02-12T08:00:00", form="8-K/A"),
                row("2016-05-10T08:00:00", items="5.02"), row("2016-08-10T08:00:00", items="7.01,2.02")]
        ev, tally = E.announcement_events(rows, SESSIONS)
        self.assertEqual([e.session for e in ev], [date(2016, 2, 10), date(2016, 8, 10)])
        self.assertEqual(tally["amendment_excluded"], 1)

    def test_merge_within_seven_days(self):
        rows = [row("2016-02-10T08:00:00"), row("2016-02-16T08:00:00"), row("2016-02-18T08:00:00")]
        ev, tally = E.announcement_events(rows, SESSIONS)
        self.assertEqual([e.session for e in ev], [date(2016, 2, 10), date(2016, 2, 18)])
        self.assertEqual(tally["merged_within_window"], 1)


class MonthlyRule(unittest.TestCase):
    def events(self, rows):
        return E.announcement_events(rows, SESSIONS)[0]

    def test_exactly_four_expected(self):
        ev = self.events(quarterly([(2016, 1), (2016, 4), (2016, 7), (2016, 10), (2017, 1)]))
        t = (2017, 1)
        st = E.monthly_status(ev, t, E.information_cutoff(SESSIONS, t))
        self.assertEqual(st, {"count": 4, "eligible": True, "expected": True})  # the 2017-01 filing is not yet known
        t = (2017, 2)
        st = E.monthly_status(ev, t, E.information_cutoff(SESSIONS, t))
        self.assertEqual((st["eligible"], st["expected"]), (True, False))

    def test_three_or_five_not_eligible(self):
        three = self.events(quarterly([(2016, 1), (2016, 4), (2016, 7)]))
        five = self.events(quarterly([(2016, 1), (2016, 3), (2016, 4), (2016, 7), (2016, 10)]))
        for ev in (three, five):
            st = E.monthly_status(ev, (2017, 1), E.information_cutoff(SESSIONS, (2017, 1)))
            self.assertFalse(st["eligible"])
            self.assertFalse(st["expected"])

    def test_window_is_t_minus_12_to_t_minus_1(self):
        ev = self.events(quarterly([(2015, 12), (2016, 1), (2016, 4), (2016, 7), (2016, 10)]))
        st = E.monthly_status(ev, (2017, 1), E.information_cutoff(SESSIONS, (2017, 1)))
        self.assertEqual(st["count"], 4)  # 2015-12 is outside t-12..t-1
        self.assertTrue(st["expected"])


class PointInTime(unittest.TestCase):
    def test_cutoff_is_16h_on_session_before_decision(self):
        t = (2016, 7)
        self.assertEqual(E.decision_session(SESSIONS, t), date(2016, 6, 30))
        self.assertEqual(E.information_cutoff(SESSIONS, t), datetime(2016, 6, 29, 16, 0))

    def test_later_filing_never_changes_expectation(self):
        base = quarterly([(2016, 1), (2016, 4), (2016, 7)]) + [row("2016-12-20T07:00:00")]
        ev = E.announcement_events(base, SESSIONS)[0]
        t = (2017, 1)
        cut = E.information_cutoff(SESSIONS, t)
        before = E.monthly_status(ev, t, cut)
        # filings accepted at or after the cutoff: on the decision session, in month t, in the future
        late = base + [row("2016-12-29T16:00:00", acc="late1"), row("2016-12-30T09:00:00", acc="late2"),
                       row("2017-01-20T07:00:00", acc="late3"), row("2017-06-01T07:00:00", acc="late4")]
        ev2 = E.announcement_events(late, SESSIONS)[0]
        self.assertEqual(E.monthly_status(ev2, t, cut), before)
        self.assertTrue(all(e.accepted < cut for e in E.known(ev2, cut)))

    def test_filing_just_before_cutoff_counts(self):
        base = quarterly([(2016, 1), (2016, 4), (2016, 7)])
        ev = E.announcement_events(base + [row("2016-12-29T15:59:59")], SESSIONS)[0]
        st = E.monthly_status(ev, (2017, 1), E.information_cutoff(SESSIONS, (2017, 1)))
        self.assertEqual(st["count"], 4)
        ev = E.announcement_events(base + [row("2016-12-29T16:00:00")], SESSIONS)[0]
        st = E.monthly_status(ev, (2017, 1), E.information_cutoff(SESSIONS, (2017, 1)))
        self.assertEqual(st["count"], 3)

    def test_actual_uses_later_filings_only_for_evaluation(self):
        ev = E.announcement_events(quarterly([(2016, 1), (2016, 4), (2016, 7), (2016, 10), (2017, 1)]), SESSIONS)[0]
        self.assertTrue(E.announced_in(ev, (2017, 1)))


def period_row(accepted, period_end, form="10-Q"):
    return row(accepted, form=form, items="", report_date=period_end)


class FiscalQuarter(unittest.TestCase):
    RELEASES = [("2016-04-25", "2016-03-31", "10-Q"), ("2016-07-25", "2016-06-30", "10-Q"),
                ("2016-10-25", "2016-09-30", "10-Q"), ("2017-01-25", "2016-12-31", "10-K"),
                ("2017-04-25", "2017-03-31", "10-Q"), ("2017-07-25", "2017-06-30", "10-Q"),
                ("2017-10-25", "2017-09-30", "10-Q")]

    def fixture(self):
        # Calendar fiscal quarters; release 25 days after period end; 10-Q/10-K 15 days after the release.
        rows = []
        for rel, per, form in self.RELEASES:
            rows.append(row(f"{rel}T07:00:00"))
            filed = date.fromisoformat(rel) + timedelta(days=15)
            rows.append(period_row(f"{filed}T17:00:00", per, form))
        return rows

    def test_assign_period(self):
        ends = [date(2016, 3, 31), date(2016, 6, 30)]
        self.assertEqual(E.assign_period(date(2016, 7, 25), ends), date(2016, 6, 30))
        self.assertIsNone(E.assign_period(date(2016, 12, 25), ends))  # > 100 days
        self.assertIsNone(E.assign_period(date(2016, 3, 31), ends[:1]))  # not strictly before

    def test_same_fiscal_quarter_one_year_earlier(self):
        rows = self.fixture()
        ev = E.announcement_events(rows, SESSIONS)[0]
        per = E.period_filings(rows)
        cut = datetime(2017, 9, 1, 16, 0)  # after the Q2-2017 release and its 10-Q
        x = E.event_time_expectation(ev, per, cut)
        self.assertEqual(x["target_period"], date(2017, 9, 30))
        self.assertEqual(x["ref_period"], date(2016, 9, 30))
        self.assertEqual(x["ref_session"], date(2016, 10, 25))
        self.assertEqual(x["expected_date"], date(2016, 10, 25) + timedelta(days=364))
        actual = E.match_actual(ev, per, x["target_period"], cut)
        self.assertEqual(actual.session, date(2017, 10, 25))

    def test_period_filed_after_cutoff_is_not_used(self):
        rows = self.fixture()
        ev = E.announcement_events(rows, SESSIONS)[0]
        per = E.period_filings(rows)
        # Before the Q2-2017 10-Q (accepted 2017-08-09) the latest known period is 2017-03-31.
        cut = datetime(2017, 8, 1, 16, 0)
        x = E.event_time_expectation(ev, per, cut)
        self.assertEqual(x["target_period"], date(2017, 6, 30))
        self.assertEqual(x["ref_session"], date(2016, 7, 25))

    def test_52_53_week_tolerance(self):
        self.assertTrue(E.near(date(2016, 10, 1), date(2016, 9, 30)))
        self.assertFalse(E.near(date(2016, 10, 15), date(2016, 9, 30)))


class EventTimeTrade(unittest.TestCase):
    def test_entry_k_sessions_before_and_exit_after_actual(self):
        ev = E.announcement_events([row("2017-10-25T07:00:00")], SESSIONS)[0]
        cut = datetime(2017, 9, 28, 16, 0)
        tr = E.event_time_trade(ev, date(2017, 10, 24), cut, SESSIONS, date(2017, 9, 29), date(2017, 10, 31))
        self.assertEqual(tr, (date(2017, 10, 17), date(2017, 10, 26)))

    def test_no_trade_when_announced_before_entry(self):
        ev = E.announcement_events([row("2017-10-16T07:00:00")], SESSIONS)[0]
        cut = datetime(2017, 9, 28, 16, 0)
        self.assertIsNone(E.event_time_trade(ev, date(2017, 10, 24), cut, SESSIONS, date(2017, 9, 29), date(2017, 10, 31)))

    def test_fallback_exit(self):
        cut = datetime(2017, 9, 28, 16, 0)
        tr = E.event_time_trade([], date(2017, 10, 24), cut, SESSIONS, date(2017, 9, 29), date(2017, 10, 31))
        self.assertEqual(tr, (date(2017, 10, 17), date(2017, 11, 23)))

    def test_entry_outside_month_is_skipped(self):
        cut = datetime(2017, 9, 28, 16, 0)
        self.assertIsNone(E.event_time_trade([], date(2017, 10, 3), cut, SESSIONS, date(2017, 9, 29), date(2017, 10, 31)))


if __name__ == "__main__":
    unittest.main()
