"""The metering sentence of the usage-cost-monitoring row recomputes from the host's metered windows.

evidence/artifacts/claude-native-practice-20261009/meter-windows-20261011.json holds, for two fixed 24-hour windows, the cost counter's dollars by model, its token counters by model and type, and the summed
`cost_usd` of the `api_request` events by model, read from the host's local Prometheus and Loki (aggregate figures only), with the pricing page's sha256 and the claude-fable-5-1 rates. The row's Notes and its
Evidence entry state what the artifact shows; each figure here is derived from it by the code below, so a row that drifts from the data, or an artifact whose numbers no longer give the row's statement, fails.

The first version of the row (#1005 at bf864c370) said the events give Opus 5.5 "about 1.9 times" the counter's figure and that they leave the advisor's iterations out, with no window, counter sample or calculation
in the repository (the Codex review in GitHub of #1005, P2, observation-inference.md:13). Metered again at two fixed instants the ratio is 2.56 and 1.64: 1.92 was the figure of the advisor run's preregistration at
the instant it was written, so no single ratio holds across windows. The clause about the advisor was also wrong: the advisor run's Stage 0 (the private working paper addendum-03-stage0-result-20261011.md) found the events
book the advisor's dollars under the executor's model, the opposite of leaving them out. The row now carries the measured ratios of both windows and the Stage 0 finding, and the paired run 4 clause says the run
was stopped, not proposed. Repository-text checks only: the private papers and the live metrics are not read.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_REL = "evidence/artifacts/claude-native-practice-20261009/meter-windows-20261011.json"
ARTIFACT = ROOT / ARTIFACT_REL
REFERENCE = ROOT / ".claude/skills/claude-native-practice/reference"
SHA256 = re.compile(r"^[0-9a-f]{64}$")
STAGE0_PAPER = "addendum-03-stage0-result-20261011.md"  # in paired-advisor/, a private working paper named by file only
STOP_PAPER = "addendum-06-owner-priority-stop-20261011.md"  # in paired-advisor/, a private working paper named by file only
MODELS = ("claude-opus-5-5", "claude-sonnet-5-5", "claude-fable-5-1")
EVIDENCE_ITEM = f"Metered 2026-10-11 over two 24-hour windows ({ARTIFACT_REL})"


def load() -> dict:
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


def fable_dollars_from_tokens(window: dict, rates: dict) -> float:
    tokens = window["tokens_by_model_type"]["claude-fable-5-1"]
    return (tokens["input"] * rates["input"] + tokens["output"] * rates["output"] + tokens["cacheRead"] * rates["cache_read"] + tokens["cacheCreation"] * rates["cache_write_5m"]) / 1e6


def events_over_counter(window: dict, model: str) -> float:
    return window["events_cost_usd_by_model"][model] / window["counter_usd_by_model"][model]


def fable_share(window: dict) -> float:
    return window["counter_usd_by_model"]["claude-fable-5-1"] / sum(window["counter_usd_by_model"].values())


def row_sentence(artifact: dict) -> str:
    """The sentence the row carries, from the artifact alone."""
    first, second = artifact["windows"]
    pair = lambda model: f"{events_over_counter(first, model):.2f} and {events_over_counter(second, model):.2f}"  # noqa: E731
    shares = [f"{fable_share(window):.0%}" for window in (first, second)]
    share = f"{shares[0]} in both windows" if shares[0] == shares[1] else f"{shares[0]} and {shares[1]}"
    return (f"Metered on this host over two fixed 24-hour windows ending {first['end_utc']} and {second['end_utc']} ({ARTIFACT_REL}, aggregate figures by model from the local Prometheus and Loki): "
            f"on claude-fable-5-1 the cost counter equals the token counters at the pricing page's rates (sha256 {artifact['pricing']['sha256'][:12]}) to within a cent in both windows; "
            f"the `api_request` events' `cost_usd` equals the counter on none of the three main models (events over counter in the first and second window: Opus 5.5 {pair('claude-opus-5-5')}, "
            f"Sonnet 5.5 {pair('claude-sonnet-5-5')}, Fable 5.1 {pair('claude-fable-5-1')}), so the events are not a spend meter, and the advisor run's Stage 0 found one cause: the events book the advisor's "
            f"dollars under the executor's model (private working paper `{STAGE0_PAPER}`); Fable 5.1, the model the advisor runs on here, was {share} of the counter's list-equivalent total. "
            f"Paired run 4, which was to weigh that share against what the advisor buys, was stopped on 2026-10-11 at the owner's priority after 2 of 8 pairs and has no verdict (private working paper `{STOP_PAPER}`).")


class MeterWindowsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.artifact = load()
        cls.slots = {slot["id"]: slot for slot in json.loads((REFERENCE / "slots.json").read_text(encoding="utf-8"))["slots"]}
        cls.page = (REFERENCE / "observation-inference.md").read_text(encoding="utf-8")

    def test_the_artifact_is_well_formed_and_holds_aggregate_figures_only(self):
        artifact = self.artifact
        self.assertEqual(artifact["schema"], "claude-native-practice-meter-windows/1")
        self.assertEqual(len(artifact["windows"]), 2)
        for window in artifact["windows"]:
            with self.subTest(window=window["end_utc"]):
                self.assertRegex(window["end_utc"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
                for key in ("counter_usd_by_model", "events_cost_usd_by_model", "tokens_by_model_type"):
                    self.assertTrue(window[key], key)
                for model in MODELS:
                    self.assertGreater(window["counter_usd_by_model"][model], 0)
                    self.assertGreater(window["events_cost_usd_by_model"][model], 0)
                    self.assertEqual(sorted(window["tokens_by_model_type"][model]), ["cacheCreation", "cacheRead", "input", "output"])
        self.assertLess(artifact["windows"][0]["end_utc"], artifact["windows"][1]["end_utc"])
        self.assertRegex(artifact["pricing"]["sha256"], SHA256)
        self.assertRegex(artifact["pricing"]["fetched_utc"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
        text = ARTIFACT.read_text(encoding="utf-8")
        self.assertNotIn("/home/", text)
        self.assertNotIn("@", text)

    def test_the_fable_counter_equals_the_token_counters_at_the_pricing_pages_rates(self):
        rates = self.artifact["pricing"]["usd_per_mtok"]["claude-fable-5-1"]
        self.assertEqual(rates, {"input": 10.0, "cache_write_5m": 12.5, "cache_write_1h": 20.0, "cache_read": 0.25, "output": 50.0})
        for window in self.artifact["windows"]:
            with self.subTest(window=window["end_utc"]):
                self.assertAlmostEqual(window["counter_usd_by_model"]["claude-fable-5-1"], fable_dollars_from_tokens(window, rates), delta=0.01)

    def test_the_events_equal_the_counter_on_none_of_the_three_models_in_either_window(self):
        for window in self.artifact["windows"]:
            for model in MODELS:
                with self.subTest(window=window["end_utc"], model=model):
                    self.assertGreater(abs(events_over_counter(window, model) - 1), 0.05)

    def test_the_ratio_is_not_one_number_across_windows(self):
        first, second = self.artifact["windows"]
        self.assertGreater(abs(events_over_counter(first, "claude-opus-5-5") - events_over_counter(second, "claude-opus-5-5")), 0.5, "a ratio that held would be worth one figure; this one does not")

    def test_the_row_states_the_artifacts_figures_in_the_json_and_on_the_page(self):
        row = self.slots["usage-cost-monitoring"]
        sentence = row_sentence(self.artifact)
        self.assertEqual(row["notes"].count(sentence), 1)
        self.assertIn(sentence, self.page)
        self.assertIn(EVIDENCE_ITEM, row["evidence"])
        self.assertIn(EVIDENCE_ITEM, self.page)
        for gone in ("leaves the advisor's iterations out", "about 1.9 times", "is proposed to weigh"):
            with self.subTest(gone=gone):
                self.assertNotIn(gone, row["notes"])
                self.assertNotIn(gone, self.page)

    def test_a_changed_figure_in_the_row_is_caught(self):
        row = self.slots["usage-cost-monitoring"]
        first, second = self.artifact["windows"]
        figure = f"Opus 5.5 {events_over_counter(first, 'claude-opus-5-5'):.2f} and {events_over_counter(second, 'claude-opus-5-5'):.2f}"
        self.assertIn(figure, row["notes"])
        for label, changed in {"a ratio": row["notes"].replace(figure, "Opus 5.5 1.90 and 1.64"), "the share": row["notes"].replace("23% in both windows", "25% in both windows"),
                               "the pricing hash": row["notes"].replace(self.artifact["pricing"]["sha256"][:12], "0" * 12)}.items():
            with self.subTest(change=label):
                self.assertNotEqual(changed, row["notes"])
                self.assertNotIn(row_sentence(self.artifact), changed)


if __name__ == "__main__":
    unittest.main()
