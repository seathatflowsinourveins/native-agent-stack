"""run.py: the calendar builder, and every fetch and evaluation command refusing on the unfrozen draft (R8-4)."""
import json
import tempfile
import unittest
from pathlib import Path

import run
from core import guards


class Cli(unittest.TestCase):
    def test_build_calendar(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "session-calendar.json"
            self.assertEqual(run.main(["build-calendar", "--first", "2016-11-23", "--last", "2016-11-28", "--out", str(out)]), 0)
            body = json.loads(out.read_text())
            self.assertEqual([s["d"] for s in body["sessions"]], ["2016-11-23", "2016-11-25", "2016-11-28"])
            self.assertEqual(body["sessions"][1]["close"], "2016-11-25T18:00:00Z")

    def test_fetch_evaluate_and_count_refuse_while_the_protocol_is_a_draft(self):
        with tempfile.TemporaryDirectory() as tmp:
            enum = Path(tmp) / "enum.json"
            enum.write_text(json.dumps({"symbols": [], "actions": []}))
            for argv in (["fetch", "--stage", "validation", "--enumeration", str(enum), "--snapshot", tmp],
                         ["evaluate", "--stage", "validation", "--enumeration", str(enum), "--snapshot", tmp,
                          "--sha", "0" * 64, "--results", str(Path(tmp) / "r.json")],
                         ["count", "--enumeration", str(enum), "--snapshot", tmp, "--sha", "0" * 64,
                          "--n0", "2026-11-23", "--last", "2027-11-22"]):
                with self.assertRaises(guards.Refused):
                    run.main(argv)
            self.assertFalse((Path(tmp) / "r.json").exists())


if __name__ == "__main__":
    unittest.main()
