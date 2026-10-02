"""The definitive round's comparison with the definitive manifest (amendment 2): every verdict on synthetic rows."""

import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "evidence/artifacts/new-wsl-definitive-round-20261002"
SPEC = importlib.util.spec_from_file_location("definitive_round_compare", FOLDER / "compare.py")
assert SPEC is not None and SPEC.loader is not None
compare_mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(compare_mod)

FIELD = [{"key": "F01", "name": "A", "repository": "https://github.com/Owner/A", "contender": "owner/a"},
         {"key": "F02", "name": "B", "repository": "https://github.com/owner/b.git", "contender": "owner/b"},
         {"key": "F03", "name": "U", "repository": "https://ubuntu.com/download/server",
          "contender": "page:ubuntu-26-04-1-lts-canonical-wsl-image"}]


def row(slot_id, state, repository="", **extra):
    return {"catalog": "foundation", "layer_id": "layer", "slot_id": slot_id, "state": state,
            "repository": repository, "default": slot_id, **extra}


def definitive(key, contender):
    return {"status": "definitive", "basis": "both families", "default": key, "contender": contender}


class VerdictTest(unittest.TestCase):
    def check(self, manifest_row, outcome):
        return compare_mod.verdict(manifest_row, outcome, FIELD)

    def test_resolved_row_agree_and_contest(self):
        r = row("s", "definitive", "https://github.com/owner/a")
        self.assertEqual(self.check(r, definitive("F01", "owner/a"))["verdict"], "agree")
        self.assertEqual(self.check(r, definitive("F02", "owner/b"))["verdict"], "contest")
        self.assertEqual(self.check(r, definitive("NONE", None))["verdict"], "contest")

    def test_row_that_installs_nothing(self):
        r = row("s", "resolved")
        self.assertEqual(self.check(r, definitive("NONE", None))["verdict"], "agree")
        self.assertEqual(self.check(r, definitive("F01", "owner/a"))["verdict"], "contest")

    def test_split_row_is_a_nomination(self):
        got = self.check(row("s", "split", measurement="ten fixed questions"), definitive("F02", "owner/b"))
        self.assertEqual((got["verdict"], got["manifest_measurement"]), ("nominates", "ten fixed questions"))

    def test_measurement_row_is_a_cross_check(self):
        r = row("s", "measurement", "https://github.com/owner/b")
        got = self.check(r, definitive("F02", "owner/b"))
        self.assertEqual((got["verdict"], got["matches"]), ("cross_check", True))
        self.assertFalse(self.check(r, definitive("F01", "owner/a"))["matches"])

    def test_pinned_row_with_two_repositories(self):
        r = row("s", "", "https://github.com/owner/a ; https://github.com/owner/b")
        self.assertEqual(self.check(r, definitive("F02", "owner/b"))["verdict"], "pin_agree")
        self.assertEqual(self.check(r, definitive("NONE", None))["verdict"], "pin_conflict")

    def test_unsettled_slot_lists_finalists_as_contenders(self):
        out = {"status": "measurement", "basis": "unsettled after adjudication", "finalists": ["F01", "F02"],
               "settling_measurement": "a head-to-head"}
        got = self.check(row("s", "definitive", "https://github.com/owner/a"), out)
        self.assertEqual((got["verdict"], got["finalists"]), ("not_settled", ["owner/a", "owner/b"]))

    def test_page_contender_alias(self):
        r = row("base-distribution", "definitive", "https://releases.ubuntu.com/26.04.1/")
        got = self.check(r, definitive("F03", "page:ubuntu-26-04-1-lts-canonical-wsl-image"))
        self.assertEqual(got["verdict"], "agree")

    def test_user_pin_conflict_outcome_is_judged_against_the_manifest(self):
        out = dict(definitive("F02", "owner/b"), status="user_pin_conflict", user_pin="owner/a")
        r = row("s", "", "https://github.com/owner/a ; https://github.com/owner/b")
        self.assertEqual(self.check(r, out)["verdict"], "pin_agree")


class CompareTest(unittest.TestCase):
    def test_not_covered_and_counts(self):
        units = [{"unit_id": "u", "field": FIELD,
                  "slots": [{"slot_id": "job-a", "source_slot": "row-a"}, {"slot_id": "job-b", "source_slot": "row-b"}]}]
        rows = {"row-a": row("row-a", "definitive", "https://github.com/owner/a"),
                "row-b": row("row-b", "split"), "row-c": row("row-c", "resolved")}
        selection = {"units": [{"unit_id": "u", "slots": [
            {"slot_id": "job-a", "outcome": definitive("F01", "owner/a")},
            {"slot_id": "job-b", "outcome": definitive("F02", "owner/b")}]}]}
        got = compare_mod.compare(selection, units, rows)
        self.assertEqual(got["counts"], {"agree": 1, "nominates": 1})
        self.assertEqual([r["slot_id"] for r in got["not_covered"]], ["row-c"])

    def test_every_round_slot_names_a_source_slot(self):
        data = json.loads((FOLDER / "units.json").read_text(encoding="utf-8"))
        units = data["units"] if isinstance(data, dict) else data
        slots = [s for u in units for s in u["slots"]]
        self.assertEqual(len(slots), 43)
        self.assertTrue(all(s.get("source_slot") for s in slots))


if __name__ == "__main__":
    unittest.main()
