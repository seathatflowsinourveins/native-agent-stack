"""The primary-source reading's published counts recompute from its artifact, by this code, on every run.

A published figure is computed from the published events, never from a separate summary (the first read of #923 found a
rate that did not recompute). Each check recounts one figure that reference/slots.json or the addendum of
docs/decisions/2026-10-09-claude-code-native-practice.md states, from
evidence/artifacts/claude-native-practice-20261009/primary-source-reading.json. Repository-text checks only: no page is
fetched, so the sha256 values are compared with each other and never with the web.
"""

from __future__ import annotations

import collections
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
READING = ROOT / "evidence/artifacts/claude-native-practice-20261009/primary-source-reading.json"
SLOTS = ROOT / ".claude/skills/claude-native-practice/reference/slots.json"
RECORD = ROOT / "docs/decisions/2026-10-09-claude-code-native-practice.md"
RELATIONS = ("agrees", "extends", "contradicts", "not-covered")


class ReadingCountsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reading = json.loads(READING.read_text(encoding="utf-8"))
        cls.slots = json.loads(SLOTS.read_text(encoding="utf-8"))["slots"]
        cls.practices = [p for source in cls.reading["sources"] for p in source["practices"]]
        cls.kept = [p for p in cls.practices if p["status"] == "kept"]

    def test_the_headline_counts_recount_from_the_practices(self):
        counts = self.reading["counts"]
        self.assertEqual(counts["sources"], len(self.reading["sources"]))
        self.assertEqual(counts["practices"], len(self.practices))
        self.assertEqual(counts["kept"], len(self.kept))
        self.assertEqual({p["status"] for p in self.practices}, {"kept", "refuted"})

    def test_by_slot_kept_recounts_slot_and_relation(self):
        for p in self.kept:  # a correction only ever applies to a refuted practice
            self.assertFalse(p.get("corrected_slot") or p.get("corrected_relation"), p["statement"][:60])
        by_slot = collections.defaultdict(collections.Counter)
        for p in self.kept:
            by_slot[p["slot"]][p["relation_to_our_default"]] += 1
        recorded = {slot: {r: counts.get(r, 0) for r in RELATIONS} for slot, counts in self.reading["by_slot_kept"].items()}
        recount = {slot: {r: counts.get(r, 0) for r in RELATIONS} for slot, counts in by_slot.items()}
        self.assertEqual(recount, recorded)

    def test_every_slot_total_and_listing_follows_the_reading(self):
        recorded = {slot: sum(counts.values()) for slot, counts in self.reading["by_slot_kept"].items()}
        sources = {source["url"]: source for source in self.reading["sources"]}
        for slot in self.slots:
            with self.subTest(slot=slot["id"]):
                total = slot.get("primary_sources_total", 0)
                self.assertEqual(total, recorded.get(slot["id"], 0))
                listed = slot.get("primary_sources") or []
                self.assertLessEqual(len(listed), total)
                self.assertEqual(bool(listed), total > 0)
                for entry in listed:
                    source = sources[entry["url"]]
                    self.assertEqual(entry["sha256"], source["sha256"])
                    self.assertEqual(entry["fetched_utc"], source["fetched_utc"])
                    self.assertRegex(entry["sha256"], r"^[0-9a-f]{64}$")

    def test_the_addendum_states_the_recounted_figures(self):
        relation = collections.Counter(p["relation_to_our_default"] for p in self.kept)
        in_slots = sum(slot.get("primary_sources_total", 0) for slot in self.slots)
        slots_with_sources = sum(1 for slot in self.slots if slot.get("primary_sources_total", 0))
        measured = sum(1 for p in self.kept if p["evidence_kind"] == "measured")
        both = sum(1 for p in self.kept if p["clients"] == "both")
        refuted = len(self.practices) - len(self.kept)
        sentence = (f"Of {len(self.practices)} practices the refuters kept {len(self.kept)} and refuted {refuted}; "
                    f"of the {len(self.kept)}, {relation['agrees']} agree with a default, {relation['extends']} extend one, "
                    f"{relation['contradicts']} contradict one and {relation['not-covered']} are not covered by any default; "
                    f"{in_slots} map to one of {slots_with_sources} role slots and {len(self.kept) - in_slots} to none; "
                    f"{measured} rest on a measurement the source reports, and {both} apply to both clients.")
        text = " ".join(RECORD.read_text(encoding="utf-8").split())
        self.assertIn(sentence, text)
        self.assertEqual(len(self.kept) - in_slots, sum(self.reading["by_slot_kept"]["none"].values()))

    def test_sources_carry_a_fetch_time_and_a_full_hash(self):
        for source in self.reading["sources"]:
            with self.subTest(url=source["url"]):
                self.assertRegex(source["sha256"], r"^[0-9a-f]{64}$")
                self.assertRegex(source["fetched_utc"], r"^2026-10-09T\d\d:\d\d:\d\dZ|^2026-10-09T\d\d:\d\d")
        self.assertEqual(len({s["url"] for s in self.reading["sources"]}), len(self.reading["sources"]))


if __name__ == "__main__":
    unittest.main()
