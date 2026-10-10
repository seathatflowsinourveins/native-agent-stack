"""The addendum's published figures recompute from the artifacts it cites, by this code, on every run.

A published figure is computed from the published events, never from a separate summary (the first read of #923 found a
rate that did not recompute). Each check recounts one figure that reference/slots.json or the addendum of
docs/decisions/2026-10-09-claude-code-native-practice.md states, from
evidence/artifacts/claude-native-practice-20261009/primary-source-reading.json (the reading), probes-20261009.json (the
probes) or the checked-in settings template. The reader and refuter settings the addendum names are compared with the
models and efforts the run's children were measured at (usage.by_phase of the reading), not with the reading's own prose.
The spend is recomputed from the recorded tokens of the executors and of the advisor they called, at the rate table the
reading cites, so a figure that leaves out the advisor's separately billed calls cannot pass.
Repository-text checks only: no page is fetched, so the sha256 values are compared with each other and never with the
web, and the host's launcher and archive are read through the probe artifact.
"""

from __future__ import annotations

import collections
import copy
import json
import re
import unittest
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
READING = ROOT / "evidence/artifacts/claude-native-practice-20261009/primary-source-reading.json"
PROBES = ROOT / "evidence/artifacts/claude-native-practice-20261009/probes-20261009.json"
SLOTS = ROOT / ".claude/skills/claude-native-practice/reference/slots.json"
RECORD = ROOT / "docs/decisions/2026-10-09-claude-code-native-practice.md"
TEMPLATE = ROOT / "adoption/templates/claude.settings.template.json"
RELATIONS = ("agrees", "extends", "contradicts", "not-covered")
ANTHROPIC_HOSTS = ("claude.com", "www.anthropic.com")
PHASES = {"reader": "Read", "refuter": "Refute"}
PRICING_PAGE = "https://platform.claude.com/docs/en/about-claude/pricing"
# The pricing page's model table as read on 2026-10-10 (USD per million tokens: base input, 5-minute and 1-hour cache writes,
# cache hits, output). The reading records the same table; the tests hold the two to each other, so neither can drift alone.
RATES_USD_PER_MTOK = {
    "claude-opus-5-5": {"input": 4, "cache_write_5m": 5, "cache_write_1h": 8, "cache_read": 0.2, "output": 20},
    "claude-fable-5-1": {"input": 10, "cache_write_5m": 12.5, "cache_write_1h": 20, "cache_read": 0.25, "output": 50},
}
TOKEN_CLASSES = (("input_tokens", "input"), ("output_tokens", "output"), ("cache_read_input_tokens", "cache_read"),
                 ("cache_creation_5m_input_tokens", "cache_write_5m"), ("cache_creation_1h_input_tokens", "cache_write_1h"))


def record_text() -> str:
    return " ".join(RECORD.read_text(encoding="utf-8").split())


def model_name(model_id: str) -> str:
    family, major, minor = re.fullmatch(r"claude-([a-z]+)-(\d+)-(\d+)", model_id).groups()
    return f"{family.capitalize()} {major}.{minor}"


def recorded_settings(usage: dict) -> list:
    """(role, model name, effort) of the reader and the refuter, from the measured phases of the run's children."""
    settings = []
    for role, phase in PHASES.items():
        (model,), (effort,) = usage["by_phase"][phase]["resolved_models"], usage["by_phase"][phase]["efforts"]
        settings.append((role, model_name(model), effort))
    return sorted(settings)


def priced(tokens: dict, rates: dict) -> Decimal:
    """USD for one model's tokens: each token class times its rate per million tokens."""
    return sum(Decimal(tokens[field]) * Decimal(str(rates[rate])) for field, rate in TOKEN_CLASSES) / Decimal(1_000_000)


def cents(amount: Decimal) -> Decimal:
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def recomputed_spend(usage: dict) -> dict:
    """The executors' spend, the advisor's spend and their total, from the recorded tokens and the recorded rates."""
    rates = usage["pricing"]["rates_usd_per_mtok"]
    executor = sum((priced(tokens, rates[model]) for model, tokens in usage["by_resolved_model"].items()), Decimal(0))
    advisor = sum((priced(tokens, rates[model]) for model, tokens in usage["advisor_by_model"].items()), Decimal(0))
    return {"executor": cents(executor), "advisor": cents(advisor), "total": cents(executor + advisor)}


def published_spend(usage: dict) -> dict:
    return {"executor": Decimal(str(usage["priced_usd_executor_api_list"])),
            "advisor": Decimal(str(usage["priced_usd_advisor_api_list"])),
            "total": Decimal(str(usage["priced_usd_api_list"]))}


def stated_settings(text: str) -> list:
    """(role, model name, effort) as the addendum words them, 'an Opus 5.5 reader at xhigh': one entry per statement."""
    found = re.findall(r"an ([A-Z][a-z]+ \d+\.\d+) (reader|refuter) at ([a-z]+)", text)
    return sorted((role, model, effort) for model, role, effort in found)


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

    def test_the_addendum_states_the_source_split_readability_run_and_spend(self):
        sources = self.reading["sources"]
        anthropic = sum(1 for s in sources if urlparse(s["url"]).netloc in ANTHROPIC_HOSTS)
        text = record_text()
        self.assertIn(f"read {len(sources)} primary sources: {anthropic} Anthropic engineering and Claude blog posts", text)
        self.assertIn(f"and {len(sources) - anthropic} cross-client sources", text)
        self.assertTrue(all(s["readable"] for s in sources))
        self.assertIn(f"All {len(sources)} sources were readable.", text)
        run_id = self.reading["run"].split(" ", 1)[0]
        self.assertIn(f"run `{run_id}` read", text)
        spend = self.reading["usage"]["priced_usd_api_list"]
        self.assertEqual(self.reading["usage"]["status"], "complete")
        self.assertIn(f"Spend: ${spend:.2f} at API list price", text)

    def test_the_run_settings_are_the_measured_phases_of_the_run(self):
        usage = self.reading["usage"]
        self.assertEqual(set(usage["by_phase"]), set(PHASES.values()))
        for phase, entry in usage["by_phase"].items():
            with self.subTest(phase=phase):
                self.assertEqual(entry["children"], len(self.reading["sources"]))  # one reader and one refuter per source
                self.assertEqual(len(entry["resolved_models"]), 1)
                self.assertEqual(len(entry["efforts"]), 1)
        self.assertEqual(sum(entry["children"] for entry in usage["by_phase"].values()),
                         sum(model["children"] for model in usage["by_resolved_model"].values()))
        self.assertEqual({model for entry in usage["by_phase"].values() for model in entry["resolved_models"]},
                         set(usage["by_resolved_model"]))
        self.assertRegex(usage["measurement"]["record"]["sha256"], r"^[0-9a-f]{64}$")

    def test_the_recorded_rates_are_the_cited_pricing_tables_rates(self):
        usage = self.reading["usage"]
        pricing = usage["pricing"]
        self.assertEqual(pricing["source"], PRICING_PAGE)
        self.assertEqual(pricing["rates_usd_per_mtok"], RATES_USD_PER_MTOK)
        for key in ("page_sha256", "advisor_page_sha256"):
            self.assertRegex(pricing[key], r"^[0-9a-f]{64}$")
        self.assertEqual(sorted(pricing["rates_usd_per_mtok"]), sorted([*usage["by_resolved_model"], *usage["advisor_by_model"]]))

    def test_the_published_spend_recomputes_from_the_recorded_tokens_and_rates(self):
        # The advisor's calls bill at the advisor model's rates and are not in the executors' usage (the advisor tool's
        # "Usage and billing"), so the spend is both: the executors' tokens and the advisor's, each at its own rates.
        usage = self.reading["usage"]
        spend = recomputed_spend(usage)
        self.assertEqual(published_spend(usage), spend)
        self.assertGreater(spend["advisor"], 0)
        self.assertEqual(spend["executor"] + spend["advisor"], spend["total"])
        for model, tokens in usage["by_resolved_model"].items():
            with self.subTest(model=model):  # the 5-minute and 1-hour cache writes are priced apart and add up to the total
                self.assertEqual(tokens["cache_creation_5m_input_tokens"] + tokens["cache_creation_1h_input_tokens"],
                                 tokens["cache_creation_input_tokens"])
        (executor_model,), (advisor_model,) = usage["by_resolved_model"], usage["advisor_by_model"]
        self.assertIn(f"Spend: ${spend['total']} at API list price: ${spend['executor']} for the {model_name(executor_model)} "
                      f"executors and ${spend['advisor']} for the answered {model_name(advisor_model)} advisor calls", record_text())

    def test_a_spend_that_leaves_out_the_advisor_is_caught(self):
        usage = self.reading["usage"]
        published = published_spend(usage)
        self.assertEqual(recomputed_spend(usage), published)
        (advisor_model,) = usage["advisor_by_model"]
        without_advisor = copy.deepcopy(usage)
        without_advisor["advisor_by_model"] = {}
        no_advisor_output = copy.deepcopy(usage)
        no_advisor_output["advisor_by_model"][advisor_model]["output_tokens"] = 0
        cheaper_advisor = copy.deepcopy(usage)
        cheaper_advisor["pricing"]["rates_usd_per_mtok"][advisor_model]["output"] = 5
        for label, mutated in (("the advisor's tokens removed", without_advisor),
                               ("the advisor's output tokens removed", no_advisor_output),
                               ("the advisor billed at a lower rate", cheaper_advisor)):
            with self.subTest(change=label):
                self.assertNotEqual(recomputed_spend(mutated), published)
        # A total that equals the executors' spend, the first count of this reading, is not the spend.
        self.assertNotEqual(recomputed_spend(usage), {**published, "total": published["executor"]})
        self.assertNotEqual(published["total"], published["executor"])
        text = record_text()
        self.assertIn(f"Spend: ${published['total']} at API list price", text)
        self.assertNotIn(f"Spend: ${published['executor']} at API list price", text)
        (executor_model,) = usage["by_resolved_model"]
        stated = (f"${published['total']} at API list price: ${published['executor']} for the {model_name(executor_model)} "
                  f"executors and ${published['advisor']} for the answered {model_name(advisor_model)} advisor calls")
        self.assertIn(stated, text)
        self.assertNotIn(stated, text.replace(f"Spend: ${published['total']} at", f"Spend: ${published['executor']} at"))

    def test_the_advisor_is_named_with_its_calls_in_the_run_description_and_the_addendum(self):
        usage = self.reading["usage"]
        calls = usage["advisor_calls"]
        ((advisor_model, advisor),) = usage["advisor_by_model"].items()
        self.assertEqual(calls["made"], calls["answered"] + calls["refused_too_many_requests"])
        self.assertEqual(calls["answered"], advisor["calls"])
        self.assertEqual(calls["children_with_an_answered_call"], advisor["children"])
        self.assertEqual(sorted(calls["by_phase"]), sorted(PHASES.values()))
        for key in ("made", "answered", "refused_too_many_requests"):
            self.assertEqual(sum(entry[key] for entry in calls["by_phase"].values()), calls[key])
        sentence = (f"{model_name(advisor_model)} advisor: {calls['made']} calls, {calls['answered']} answered "
                    f"({calls['by_phase']['Read']['answered']} by readers, {calls['by_phase']['Refute']['answered']} by refuters, "
                    f"in {advisor['children']} children) and {calls['refused_too_many_requests']} refused as too_many_requests")
        self.assertIn(sentence, self.reading["run"])
        self.assertIn(f"a {sentence}.", record_text())

    def test_the_addendum_and_the_run_text_state_the_recorded_reader_and_refuter(self):
        recorded = recorded_settings(self.reading["usage"])
        self.assertEqual(stated_settings(record_text()), recorded)
        for role, model, effort in recorded:
            self.assertIn(f"{model} {effort} {role}", self.reading["run"])

    def test_a_changed_reader_or_refuter_setting_is_caught(self):
        recorded = recorded_settings(self.reading["usage"])
        text = record_text()
        for role, model, effort in recorded:
            for old, new in ((f"{model} {role} at {effort}", f"{model} {role} at low"),
                             (f"{model} {role} at {effort}", f"Sonnet 9.9 {role} at {effort}")):
                with self.subTest(change=new):
                    self.assertIn(old, text)
                    self.assertNotEqual(stated_settings(text.replace(old, new)), recorded)
            with self.subTest(role=role, change="a second statement"):
                self.assertNotEqual(stated_settings(text + f" an {model} {role} at low"), recorded)
        for phase, key, value in (("Read", "efforts", ["low"]), ("Refute", "efforts", ["low"]),
                                  ("Read", "resolved_models", ["claude-sonnet-5-5"]),
                                  ("Refute", "resolved_models", ["claude-opus-4-1"])):
            with self.subTest(phase=phase, key=key):
                usage = copy.deepcopy(self.reading["usage"])
                usage["by_phase"][phase][key] = value
                self.assertNotEqual(recorded_settings(usage), recorded)

    def test_the_gate_rests_on_a_source_figure_the_reading_kept(self):
        # The addendum quotes Anthropic's code-review post (54% of PRs, up from 16%); one kept practice carries both.
        carrying = [p for p in self.kept if "54%" in p["statement"] + p.get("quote", "")
                    and "16%" in p["statement"] + p.get("quote", "")]
        self.assertEqual(len(carrying), 1)
        self.assertIn("substantive review comments on 54% of PRs, up from 16%", record_text())


class ProbeFiguresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.probes = json.loads(PROBES.read_text(encoding="utf-8"))

    def test_the_retention_paragraph_states_the_probe_figures(self):
        coverage = self.probes["old_archive_coverage"]
        deletion = self.probes["old_archive_deletion"]
        freed = sum(item["bytes"] for item in deletion["deleted"])
        self.assertEqual(freed, deletion["bytes_freed"])
        self.assertEqual(coverage["old_sessions_missing_from_live"], 0)
        text = record_text()
        self.assertIn(f"All {coverage['old_sessions']:,} sessions of the pre-move archive were found in the live one", text)
        self.assertIn(f"usage-cache files ({freed:,} bytes) were deleted", text)
        self.assertTrue(deletion["kept_until"].startswith("2026-10-23"))
        self.assertIn("its small leftovers stay until 2026-10-23", text)

    def test_the_sandbox_paragraph_states_the_credential_store_count(self):
        stated = set(re.findall(r"All (\d+) home-relative credential stores", json.dumps(self.probes["m1_sandbox"])))
        self.assertEqual(len(stated), 1, stated)
        self.assertIn(f"all {stated.pop()} credential stores it names", record_text())


class TemplateValueTests(unittest.TestCase):
    def test_the_retention_paragraph_states_the_templates_value(self):
        # The 180 is a decision, not a recount: the checkable part is that the addendum's figure is the template's, and
        # that the host value it reports is the same decision. The deletion time (13:50:06Z) is not checked: the deletion
        # receipt carries no time field, so nothing in the artifacts recounts it.
        stated = re.findall(r"set `cleanupPeriodDays` to (\d+) on the host; the template now carries (\d+)", record_text())
        self.assertEqual(len(stated), 1, stated)
        host, carried = map(int, stated[0])
        self.assertEqual(carried, json.loads(TEMPLATE.read_text(encoding="utf-8"))["cleanupPeriodDays"])
        self.assertEqual(host, carried)


if __name__ == "__main__":
    unittest.main()
