"""Checks for the mover v3 data files (protocol-core-draft.json freeze_preconditions[2]).

The structural checks use only the standard library. The regeneration check runs
blueprints/us-equities/mover-v3/data-tools/generate_session_calendar.py in a
runtime that has the pinned packages and compares the output byte for byte with
the committed calendar and its pin. It uses MOVER_V3_CALENDAR_PYTHON, else
PROMOTION_GATE_PYTHON (the CI venv built from blueprints/us-equities/data/
requirements.lock, which pins the same versions and hashes), else
data-tools/.venv; without one of them it is skipped.
"""

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V3 = ROOT / "blueprints/us-equities/mover-v3"
DATA = V3 / "data"
TOOLS = V3 / "data-tools"
PINS = V3 / "data-pins.json"
CALENDAR = DATA / "session-calendar.json"
FEES = DATA / "fees-v3.json"
OFFICIAL_HOSTS = ("www.federalregister.gov", "www.ecfr.gov", "www.sec.gov", "www.finra.org")
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December")


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def pinned_versions() -> dict:
    pins = {}
    for line in (TOOLS / "requirements.in").read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            name, version = line.split("==")
            pins[name] = version
    return pins


def utc(stamp: str) -> datetime:
    return datetime.fromisoformat(stamp.replace("Z", "+00:00"))


class Pins(unittest.TestCase):
    def setUp(self):
        self.pins = load(PINS)

    def test_base_files_match_their_pins(self):
        paths = [entry["path"] for entry in self.pins["base_files"]]
        self.assertEqual(paths, ["blueprints/us-equities/mover-v3/data/session-calendar.json",
                                 "blueprints/us-equities/mover-v3/data/fees-v3.json"])
        for entry in self.pins["base_files"]:
            raw = (ROOT / entry["path"]).read_bytes()
            self.assertEqual((sha256(raw), len(raw)), (entry["sha256"], entry["bytes"]), entry["path"])

    def test_amendment_files_keep_their_pinned_content_as_a_byte_prefix(self):
        paths = [entry["path"] for entry in self.pins["amendment_files"]]
        self.assertEqual(paths, ["blueprints/us-equities/mover-v3/data/session-calendar-amendments.jsonl",
                                 "blueprints/us-equities/mover-v3/data/fees-v3-amendments.jsonl"])
        for entry in self.pins["amendment_files"]:
            raw = (ROOT / entry["path"]).read_bytes()
            self.assertGreaterEqual(len(raw), entry["bytes"], entry["path"])
            self.assertEqual(sha256(raw[:entry["bytes"]]), entry["sha256"], entry["path"])
            if raw:
                self.assertTrue(raw.endswith(b"\n"), entry["path"])
                for line in raw.decode("utf-8").splitlines():
                    self.assertIsInstance(json.loads(line), dict, entry["path"])

    def test_generator_inputs_match_their_pins(self):
        for entry in self.pins["calendar_generator"]["files"]:
            self.assertEqual(sha256((ROOT / entry["path"]).read_bytes()), entry["sha256"], entry["path"])

    def test_calendar_summary_and_holdout_reach_match_the_calendar(self):
        calendar = load(CALENDAR)
        sessions = [row[0] for row in calendar["sessions"]]
        summary = self.pins["calendar_summary"]
        self.assertEqual(summary["session_count"], len(sessions))
        self.assertEqual(summary["early_close_count"], sum(row[5] for row in calendar["sessions"]))
        self.assertEqual((summary["first_session"], summary["last_session"]), (sessions[0], sessions[-1]))
        reach = self.pins["holdout_reach"]
        # N0 = freeze session + 40; 252 holdout sessions from N0; two 63-session blocks; read within 15 more.
        self.assertEqual(reach["sessions_needed_after_freeze_session"], 40 + 251 + 2 * 63 + 15)
        self.assertEqual(reach["latest_freeze_session_covered"],
                         sessions[len(sessions) - 1 - reach["sessions_needed_after_freeze_session"]])


class SessionCalendar(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = load(CALENDAR)
        cls.rows = cls.doc["sessions"]
        cls.dates = [row[0] for row in cls.rows]

    def test_header_describes_the_rows(self):
        doc = self.doc
        self.assertEqual((doc["calendar"], doc["source"]["package"], doc["source"]["version"]),
                         ("XNYS", "exchange_calendars", "4.13.2"))
        self.assertEqual(doc["columns"], ["session", "open_et", "close_et", "open_utc", "close_utc", "early_close"])
        self.assertEqual(doc["requested_range"], {"start": "2016-01-01", "end": "2030-12-31"})
        self.assertEqual((doc["first_session"], doc["last_session"]), (self.dates[0], self.dates[-1]))
        self.assertEqual(doc["session_count"], len(self.rows))
        self.assertEqual(doc["early_close_count"], sum(row[5] for row in self.rows))
        self.assertEqual(doc["late_open_count"], 0)
        self.assertEqual(doc["generator"], "blueprints/us-equities/mover-v3/data-tools/generate_session_calendar.py")

    def test_sessions_are_unique_ascending_weekdays_covering_the_protocol_chronology(self):
        self.assertEqual(self.dates, sorted(set(self.dates)))
        self.assertTrue(all(date.fromisoformat(day).weekday() < 5 for day in self.dates))
        self.assertEqual(self.dates[0], "2016-01-04")
        for day in ("2016-01-04", "2016-12-30", "2017-01-03", "2019-12-31", "2020-01-02", "2020-12-31"):
            self.assertIn(day, self.dates)  # chronology warmup, development and validation bounds

    def test_times_are_consistent_scheduled_opens_and_closes(self):
        for session, open_et, close_et, open_utc, close_utc, early in self.rows:
            opened, closed = datetime.fromisoformat(open_et), datetime.fromisoformat(close_et)
            self.assertEqual(opened.date().isoformat(), session)
            self.assertEqual(closed.date().isoformat(), session)
            self.assertEqual(opened.utcoffset(), closed.utcoffset(), session)
            self.assertIn(opened.utcoffset(), (timedelta(hours=-5), timedelta(hours=-4)), session)
            self.assertEqual((opened.hour, opened.minute), (9, 30), session)
            self.assertEqual((closed.hour, closed.minute), (13, 0) if early else (16, 0), session)
            self.assertEqual(opened.astimezone(timezone.utc), utc(open_utc), session)
            self.assertEqual(closed.astimezone(timezone.utc), utc(close_utc), session)

    def test_utc_offsets_follow_the_host_time_zone_rules_when_available(self):
        try:
            from zoneinfo import ZoneInfo
            new_york = ZoneInfo("America/New_York")
        except Exception as error:  # no time zone database on this host
            self.skipTest(f"America/New_York unavailable: {error}")
        for session, open_et, *_ in self.rows:
            opened = datetime.fromisoformat(open_et)
            self.assertEqual(opened.utcoffset(), opened.replace(tzinfo=new_york).utcoffset(), session)

    def test_2016_2020_early_closes_include_the_protocol_cases(self):
        early = [row[0] for row in self.rows if row[5] and row[0] <= "2020-12-31"]
        self.assertEqual(early, ["2016-11-25", "2017-07-03", "2017-11-24", "2018-07-03", "2018-11-23", "2018-12-24",
                                 "2019-07-03", "2019-11-29", "2019-12-24", "2020-11-27", "2020-12-24"])
        for day in ("2017-07-03", "2017-11-24", "2018-11-23", "2019-12-24", "2020-11-27"):  # session_calendar
            self.assertIn(day, early)

    def test_2021_2026_early_closes_equal_the_list_rules_py_took_from_the_same_version(self):
        source = (ROOT / "blueprints/us-equities/mover-early-entry/rules.py").read_text(encoding="utf-8")
        block = re.search(r"EARLY_CLOSES = frozenset\(\{(.*?)\}\)", source, re.S).group(1)
        expected = sorted(re.findall(r'"(\d{4}-\d{2}-\d{2})"', block))
        self.assertEqual([row[0] for row in self.rows if row[5] and "2021" <= row[0][:4] <= "2026"], expected)

    def test_known_closures_are_absent_and_yearly_counts_match(self):
        for day in ("2018-12-05", "2025-01-09",  # national days of mourning
                    "2020-07-03", "2021-12-24", "2022-06-20", "2026-06-19"):  # observed holidays
            self.assertNotIn(day, self.dates)
        counts = {}
        for day in self.dates:
            counts[day[:4]] = counts.get(day[:4], 0) + 1
        self.assertEqual([counts[str(year)] for year in range(2016, 2026)],
                         [252, 251, 251, 252, 253, 252, 251, 250, 252, 250])


class Fees(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = load(FEES)
        cls.sec = cls.doc["sec_section31"]["rows"]
        cls.taf = cls.doc["finra_taf_covered_equity"]["rows"]

    def check_contiguous(self, rows):
        self.assertLessEqual(rows[0]["from"], self.doc["coverage"]["from"])
        for earlier, later in zip(rows, rows[1:]):
            self.assertIsNotNone(earlier["to"])
            self.assertLessEqual(earlier["from"], earlier["to"])
            self.assertEqual(date.fromisoformat(earlier["to"]) + timedelta(days=1), date.fromisoformat(later["from"]))
        self.assertIsNone(rows[-1]["to"])  # open-ended: covers retrieval and the freeze until an amendment

    def test_rows_are_contiguous_from_2017_through_retrieval_with_no_unverified_gap(self):
        self.assertEqual(self.doc["coverage"], {"from": "2017-01-01", "through_retrieval": "2026-09-24"})
        self.assertEqual(self.doc["unverified_periods"], [])
        self.check_contiguous(self.sec)
        self.check_contiguous(self.taf)

    def test_every_row_has_official_sources_with_retrieval_dates_and_quotes(self):
        sources = [self.doc["sec_section31"]["date_basis_source"]]
        for row in self.sec + self.taf:
            self.assertTrue(row["sources"], row["from"])
            sources.extend(row["sources"])
        for source in sources:
            host = re.match(r"https://([^/]+)/", source["url"]).group(1)
            self.assertIn(host, OFFICIAL_HOSTS)
            self.assertEqual(source["retrieved_at"], "2026-09-24")
            self.assertTrue(source["quotes"] and all(isinstance(q, str) and q for q in source["quotes"]))
            if source["retrieved_format"] not in ("federalregister_text", "finra_revision_json", "ecfr_xml"):
                self.assertIn("verification_note", source)

    def test_sec_rates_and_start_dates_appear_in_the_order_quotes(self):
        for row in self.sec:
            order = row["sources"][0]["quotes"][0]
            start = date.fromisoformat(row["from"])
            self.assertIn(f"${row['usd_per_million']:.2f} per $1,000,000", order)
            self.assertIn(f"effective on {MONTHS[start.month - 1]} {start.day}, {start.year}.", order)
            if row["to"]:
                end = date.fromisoformat(row["to"])
                closing = " ".join(row["sources"][1]["quotes"])
                self.assertIn(f"{MONTHS[end.month - 1]} {end.day}, {end.year}.", closing)
                self.assertIn(f"current fee rate of ${row['usd_per_million']:.2f} per million", closing)

    def test_taf_rates_appear_in_the_finra_rule_text_quotes(self):
        for row in self.taf:
            per_share = "0.00" if row["usd_per_share"] == 0 else f"{row['usd_per_share']:.6f}"
            clause = (f"${per_share} per share for each sale of a covered equity security, "
                      f"with a maximum charge of ${row['max_usd_per_trade']:.2f} per trade")
            rulebook = [q for s in row["sources"] if s["retrieved_format"] == "finra_revision_json" for q in s["quotes"]]
            self.assertTrue(any(clause in quote for quote in rulebook), row["from"])

    def lookup(self, rows, day):
        found = [row for row in rows if row["from"] <= day and (row["to"] is None or day <= row["to"])]
        self.assertEqual(len(found), 1, day)
        return found[0]

    def test_lookups(self):
        cases = {"2017-01-03": (21.80, 0.000119, 5.95), "2017-07-04": (23.10, 0.000119, 5.95),
                 "2019-06-03": (20.70, 0.000119, 5.95), "2020-12-31": (22.10, 0.000119, 5.95),
                 "2022-05-13": (5.10, 0.000130, 6.49), "2025-05-14": (0.00, 0.000166, 8.30),
                 "2026-09-24": (20.60, 0.000195, 9.79), "2026-10-01": (20.60, 0.0, 0.0),
                 "2027-01-04": (20.60, 0.000195, 9.79)}
        for day, (sec_rate, per_share, cap) in cases.items():
            self.assertEqual(self.lookup(self.sec, day)["usd_per_million"], sec_rate, day)
            taf = self.lookup(self.taf, day)
            self.assertEqual((taf["usd_per_share"], taf["max_usd_per_trade"]), (per_share, cap), day)


class Regeneration(unittest.TestCase):
    def interpreter(self):
        for variable in ("MOVER_V3_CALENDAR_PYTHON", "PROMOTION_GATE_PYTHON"):
            if os.environ.get(variable):
                return os.environ[variable], variable
        local = TOOLS / ".venv/bin/python"
        return (str(local), "data-tools/.venv") if local.exists() else (None, None)

    def installed(self, python):
        names = list(pinned_versions())
        probe = ("import json, sys\nfrom importlib import metadata\nout = {}\nfor n in sys.argv[1:]:\n"
                 "    try:\n        out[n] = metadata.version(n)\n    except metadata.PackageNotFoundError:\n"
                 "        out[n] = None\nprint(json.dumps(out))\n")
        result = subprocess.run([python, "-c", probe, *names], capture_output=True, text=True, timeout=120)
        return json.loads(result.stdout) if result.returncode == 0 else None

    def test_generator_regenerates_the_pinned_calendar_byte_for_byte(self):
        python, origin = self.interpreter()
        if python is None:
            self.skipTest("no locked runtime (set MOVER_V3_CALENDAR_PYTHON or build data-tools/.venv)")
        if self.installed(python) != pinned_versions():
            if origin == "MOVER_V3_CALENDAR_PYTHON":
                self.fail(f"{origin} does not have the versions pinned in data-tools/requirements.in")
            self.skipTest(f"{origin} does not have the versions pinned in data-tools/requirements.in")
        pin = next(e for e in load(PINS)["base_files"] if e["path"].endswith("session-calendar.json"))
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "session-calendar.json"
            result = subprocess.run([python, str(TOOLS / "generate_session_calendar.py"), "--output", str(output)],
                                    capture_output=True, text=True, timeout=600)
            self.assertEqual(result.returncode, 0, result.stderr[-2000:])
            raw = output.read_bytes()
        self.assertEqual((sha256(raw), len(raw)), (pin["sha256"], pin["bytes"]))
        self.assertEqual(raw, CALENDAR.read_bytes())

    def test_generator_refuses_outside_the_locked_runtime(self):
        if self.installed(sys.executable) == pinned_versions():
            self.skipTest("this interpreter is the locked runtime")
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "session-calendar.json"
            result = subprocess.run([sys.executable, str(TOOLS / "generate_session_calendar.py"), "--output", str(output)],
                                    capture_output=True, text=True, timeout=120)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("refusing to generate outside the locked runtime", result.stderr)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
