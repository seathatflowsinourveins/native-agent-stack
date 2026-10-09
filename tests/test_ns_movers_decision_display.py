"""The registered NSM display text must preserve readable identity tokens."""

import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
SUPPLEMENT = "catalogs/us-equities/ns-movers-phase0-decisions-20261009.json"
INDEX = "catalogs/us-equities/decision-index.json"
SPLIT_TOKEN = re.compile(r"\b[0-9a-f]{3} [0-9a-f]{4,}\b|\bOD [0-9]+\b")


class DecisionDisplayTests(unittest.TestCase):
    def test_supplement_decision_text_has_no_split_identifier(self):
        rows = json.loads((ROOT / SUPPLEMENT).read_text())["decisions"]
        self.assertTrue(rows)
        for row in rows:
            with self.subTest(id=row["id"]):
                self.assertIsNone(SPLIT_TOKEN.search(row["decision"]))

    def test_generated_index_preserves_the_guarded_decision_text(self):
        source = json.loads((ROOT / SUPPLEMENT).read_text())["decisions"]
        expected = {row["id"]: row["decision"] for row in source}
        index = json.loads((ROOT / INDEX).read_text())
        registered = {ref["id"]: ref["decision"] for row in index["records"]
                      for ref in row["references"] if ref["path"] == SUPPLEMENT}
        self.assertEqual(registered, expected)
        for row_id, text in registered.items():
            with self.subTest(id=row_id):
                self.assertIsNone(SPLIT_TOKEN.search(text))


if __name__ == "__main__":
    unittest.main()
