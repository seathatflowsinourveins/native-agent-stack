"""The paired-run results of 2026-10-10 recompute from their artifact, and the skill's rows say what the artifact shows.

evidence/artifacts/native-practice-paired-runs-20261010/paired-runs.json holds the per-run rows of each paired run (hidden-test result, sessions, cost, lost-work count), the
decision rule's inputs and the sha256 of every private paper the results rest on. The rows of the claude-native-practice skill (reference/slots.json) and the record's addendum
(docs/decisions/2026-10-09-claude-code-native-practice.md) state the decisions; each statement here is derived from the artifact, so a row that drifts from the data, or an artifact
whose rows no longer give the decision it records, fails. Repository-text checks only: the private papers and transcripts are not in the repository.

Paired run 5 (model routing for review micros, decided 2026-10-11) is the routing_5 section: its 20 run rows, the 12 decisive findings with the runs that found each, the cost, the ruling and the sha256 of
every paper. `routing_rule()` recomputes the registered rule from those rows, and the record's paragraph and owed table are checked against the artifact.
"""

from __future__ import annotations

import copy
import importlib.util
import itertools
import json
import os
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_REL = "evidence/artifacts/native-practice-paired-runs-20261010/paired-runs.json"
SLOTS = ROOT / ".claude/skills/claude-native-practice/reference/slots.json"
RECORD = ROOT / "docs/decisions/2026-10-09-claude-code-native-practice.md"
SHA256 = re.compile(r"^[0-9a-f]{64}$")
CELLS = [("F5", 1), ("F6", 1), ("F5", 2), ("F6", 2)]


def decision_from_runs(runs: list[dict]) -> dict:
    """The preregistered rule of paired run 2b, from the per-run rows alone: B or C replaces A only when it passes at least as many runs as A and uses fewer sessions or less cost in a
    majority of the counted fixture-trial cells (a cell counts when at least one of the two compared runs passes), with no more lost-work events than A."""
    by = {(r["fixture"], r["trial"], r["arm"]): r for r in runs}
    out = {}
    for arm in "BC":
        wins, counted, won_cells = 0, 0, []
        for fixture, trial in CELLS:
            a, other = by[(fixture, trial, "A")], by[(fixture, trial, arm)]
            if not (a["resolved"] or other["resolved"]):
                continue
            counted += 1
            if other["sessions_used"] < a["sessions_used"] or other["cost_usd_list_equivalent"] < a["cost_usd_list_equivalent"]:
                wins += 1
                won_cells.append(f"{fixture}-t{trial}")
        mine = [r for r in runs if r["arm"] == arm]
        a_runs = [r for r in runs if r["arm"] == "A"]
        out[arm] = {"passes": sum(r["resolved"] for r in mine), "a_passes": sum(r["resolved"] for r in a_runs), "counted_cells": counted, "cell_wins": wins,
                    "won_cells": won_cells, "majority": wins * 2 > counted, "lost_work_events": sum(r["lost_work_events"] for r in mine),
                    "a_lost_work_events": sum(r["lost_work_events"] for r in a_runs)}
        out[arm]["replaces_a"] = (out[arm]["passes"] >= out[arm]["a_passes"] and out[arm]["majority"]
                                  and out[arm]["lost_work_events"] <= out[arm]["a_lost_work_events"])
    return out


FIXTURES = ["F1", "F2", "F3", "F4", "F5", "F6"]
PRIMARY = ["F3", "F4", "F5", "F6"]
VOID_PAIRS = [("F3", "AC"), ("F3", "BC")]


def orchestration_rule(o: dict, fixtures: list) -> dict:
    """The preregistered rule of paired run 1, from the per-run rows and the pairwise judgements alone: an orchestrated arm (B or C) clears only when it resolves at least 2 more of the fixtures that count than A, or the
    judges' counted preference puts it over A on at least 4 of them, at no more than twice A's mean cost over those fixtures. A void pair carries no preference."""
    runs = {(r["fixture"], r["arm"]): r for r in o["runs"]}
    pairs = {(p["fixture"], p["pair"]): p for p in o["judging"]["pairs"]}
    resolved = {a: sum(1 for f in fixtures if runs[(f, a)]["resolved"]) for a in "ABC"}
    mean = {a: sum(runs[(f, a)]["cost_usd_list_equivalent"] for f in fixtures) / len(fixtures) for a in "ABC"}
    out = {"resolved": resolved, "mean_cost": mean}
    for arm, pair in (("B", "AB"), ("C", "AC")):
        wins = sum(1 for f in fixtures if pairs[(f, pair)]["counted_preference"] == arm)
        within = mean[arm] <= 2 * mean["A"]
        extra = resolved[arm] - resolved["A"]
        out[arm] = {"extra_resolved": extra, "judge_wins": wins, "cost_within_2x": within, "clears_rule": within and (extra >= 2 or wins >= 4)}
    return out


ROUTING_HEADS = [989, 974, 982, 970, 978]
ROUTING_COST_BOUND = 0.60
SONNET_CONDITION = "where the change is mechanical or a second Claude-family read exists"  # the command center's ruling: Sonnet at medium takes non-gate foundation changes only under this condition
STOP_RECORD = "addendum-06-owner-priority-stop-20261011.md"  # in paired-advisor/, a private working paper named by file only


def noise_floor(p: float, n: int, strict: bool) -> float:
    """Chance that two identical reviewers, each finding a finding with probability p in each of two runs, satisfy the rule over n findings (strict: S_f >= O_f; tolerant: S_f >= O_f - 1)."""
    b = [(1 - p) ** 2, 2 * p * (1 - p), p ** 2]
    return (1 - sum(b[o] * b[s] for o in range(3) for s in range(3) if (s < o if strict else s < o - 1))) ** n


def tolerant_floor(p: float, n: int) -> float:
    """Chance that two identical reviewers satisfy the whole tolerant reading over n findings: S_f >= O_f - 1 for every finding AND Sonnet's detections in total at least Opus's minus 2. `noise_floor(p, n, False)`
    models the first clause only and printed 0.62 where this gives 0.56 (the Codex review in GitHub of #1005 at 5c5eecaad, P2, line 82; the command center's Claude read of the same head, P3-1): the sum over the findings of
    the difference S_f - O_f is convolved with each difference held at -1 or more, and the outcomes whose running total is -2 or more are added.
    The reading and the null model are the run's own, registered before any run (papers.addendum_01, paired-routing/addendum-01-ruling-and-extension-20261011.md, sha256 1917091f..., lines 17-18); no third-party
    statistical source defines them, so the reference is the brute-force enumeration in test_the_tolerant_floor_counts_both_clauses_of_the_reading. The sum of independent differences is convolved as numpy 2.5.3
    documents numpy.convolve: "In probability theory, the sum of two independent random variables is distributed according to the convolution of their individual distributions." The cross-check test runs where numpy
    is installed (the Codex review in GitHub of #1005 at 425240f6e, P1, line 91)."""
    b = [(1 - p) ** 2, 2 * p * (1 - p), p ** 2]
    step = {}
    for o in range(3):
        for s in range(3):
            if s - o >= -1:
                step[s - o] = step.get(s - o, 0.0) + b[o] * b[s]
    total = {0: 1.0}
    for _ in range(n):
        following = {}
        for running, chance in total.items():
            for difference, weight in step.items():
                following[running + difference] = following.get(running + difference, 0.0) + chance * weight
        total = following
    return sum(chance for running, chance in total.items() if running >= -2)


def per_finding_floor(counts: dict) -> float:
    """The strict rule's chance for two identical reviewers when each finding keeps its own pooled detection rate (the runs of both arms that found it, out of 4): a plug-in calculation from these runs,
    not a measurement and not a significance test."""
    chance = 1.0
    for finding in counts["O"]:
        chance *= noise_floor((counts["O"][finding] + counts["S"][finding]) / 4, 1, True)
    return chance


def routing_rule(r: dict) -> dict:
    """The registered rule of paired run 5, from the per-run rows and the per-finding detections alone: Sonnet takes review micros only if, for every decisive finding, it found the finding in at least as many
    of its runs as Opus did, and its runs cost (the counter, main and subagent sources) at most 60% of Opus's; otherwise Opus stays. The tolerant reading and the noise floors are reported, not decisive."""
    counts = {arm: {f["id"]: len(f["found"][arm]) for f in r["findings"]} for arm in "OS"}
    cost = {arm: sum(run["cost_usd_m2"] for run in r["runs"] if run["arm"] == arm) for arm in "OS"}
    missed = [g for g in counts["O"] if counts["S"][g] < counts["O"][g]]
    ratio = cost["S"] / cost["O"]
    n = len(counts["O"])
    pooled = (sum(counts["O"].values()) + sum(counts["S"].values())) / (2 * n * 2)
    return {"verdict": "SONNET TAKES" if not missed and ratio <= ROUTING_COST_BOUND else "OPUS STAYS", "counts": counts, "detections": {arm: sum(counts[arm].values()) for arm in "OS"}, "missed": missed,
            "cost": cost, "ratio": ratio, "tolerant": all(counts["S"][g] >= counts["O"][g] - 1 for g in counts["O"]) and sum(counts["S"].values()) >= sum(counts["O"].values()) - 2,
            "pooled": pooled, "strict_floor": noise_floor(pooled, n, True), "tolerant_floor": tolerant_floor(pooled, n), "tolerant_clause_floor": noise_floor(pooled, n, False),
            "strict_floor_per_finding": per_finding_floor(counts)}


def routing_paragraph(r: dict) -> str:
    """The record's paragraph for paired run 5, written from the artifact alone (paraphrase; no owner quotation)."""
    got, dec, beside, ruling, papers = routing_rule(r), r["decision"], r["beside_the_rule"], r["ruling"], r["papers"]
    gid = got["missed"][0]
    runs = {x["run"]: x for x in r["runs"]}
    approved = sorted(f"#{x['pr']} t{x['trial']}" for x in r["runs"] if x["arm"] == "S" and x["verdict"] == "ACK" and runs[f"{x['pr']}-O-{x['trial']}"]["verdict"] == "CHANGES_REQUESTED")
    differ_heads = sorted({a.split()[0] for a in approved})
    both_trials = all(f"{h} t{t}" in approved for h in differ_heads for t in (1, 2))
    detections = got["counts"]["O"][gid]
    one_detection = "one Opus detection" if detections == 1 else f"{detections} Opus detections"
    return (f"**Model routing for review micros (paired run 5).** Sonnet 5.5 against Opus 5.5, both at medium effort in `claude -p` on client 2.1.296 with the repository's own brief alone (tools Bash, Read, Glob and Grep; "
            f"the home tree and the other runs' directories denied; the network closed), reviewed {len(ROUTING_HEADS)} pull-request heads of this repository whose findings were known from earlier Opus and GPT reads, "
            f"two trials each ({len(r['runs'])} runs). A blind first judge and a refuter (Opus 5.5 at max effort) scored each run's recall of the {dec['decisive_findings']} decisive known findings, its false positives and its cost from the counter. "
            f"The rule fixed before the first run: Sonnet takes review micros only if, for every decisive finding, it found the finding in at least as many of its runs as Opus did, and its runs cost at most {ROUTING_COST_BOUND:.0%} of Opus's. "
            f"Opus found {got['detections']['O']} detections of {2 * dec['decisive_findings']} and Sonnet {got['detections']['S']}; Sonnet missed {len(got['missed'])} decisive finding that Opus found "
            f"({gid}, found in {got['counts']['O'][gid]} of Opus's 2 runs and {got['counts']['S'][gid]} of Sonnet's), at {got['ratio']:.0%} of Opus's cost, so by the strict rule Opus stays. Trial 1 alone met the rule and said Sonnet takes micros "
            f"(its noise floor was {dec['trial_1_alone']['strict_pass_chance_if_identical']:.2f}); the registered trigger ended the run there (Sonnet takes review micros, no second trial), and the command center added one after seeing the result, so the "
            f"two-trial verdict is a ruled extension and not a preregistered outcome, and extending after a pass can only move the verdict toward Opus. Over the two trials the strict rule's noise floor is {got['strict_floor']:.2f} "
            f"at one shared detection rate of {got['pooled']:.2f} (two identical reviewers would pass it that rarely) and {got['strict_floor_per_finding']:.2f} with each finding's own pooled rate (a plug-in calculation from these runs, "
            f"not a significance test: a miss is less easily put down to chance than the first figure suggests, though it rests on {one_detection}); the tolerant reading, reported and not decisive, holds, and two identical "
            f"reviewers would satisfy it {got['tolerant_floor']:.2f} of the time ({got['tolerant_clause_floor']:.2f} for its per-finding clause alone, the figure the result record prints; the command center's ruling prints it too and is corrected in a sidecar "
            f"file `{papers['ruling_correction']['path']}`, which leaves the ruling's bytes unchanged). "
            f"Beside the rule, not inputs: outside the known findings Opus reported {beside['real_new_p1_p2']['O']} real and new P1 or P2 findings against Sonnet's {beside['real_new_p1_p2']['S']}, "
            f"and Sonnet approved {', '.join(differ_heads)}{' in both trials' if both_trials else ''} where Opus requested changes. The command center ruled the strict reading on {ruling['date']} "
            f"(ruling `{papers['ruling']['path']}`): Opus for trading code, gate code and any micro that is the only Claude-family read of a gate; Sonnet at medium only for non-gate foundation "
            f"changes (docs, pages, catalogs, generated reports) {SONNET_CONDITION}, which is the command center's routing discretion under the owner's direction to use the cheapest model that holds quality and not something "
            f"run 5 measured (none of the {len(ROUTING_HEADS)} heads was a docs, pages or generated-report change); no slot row, default or skill text changes. Limits: the same {len(ROUTING_HEADS)} heads in both trials, so the second trial measures run-to-run variation on them; one brief; medium effort only; "
            f"the judge and refuter are one family; the fence denies the client's persisted tool outputs and refused the runs that tried to read them ({r['exposure']['limit'].split('(')[1].rstrip(')')}); costs are API-list-equivalent, not billed. "
            f"The preregistration is `{papers['preregistration']['path']}` and the result record `{papers['result']['path']}`, both private, and the registration allows no third trial.")


class PlanningRunTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.artifact = json.loads((ROOT / ARTIFACT_REL).read_text(encoding="utf-8"))
        cls.plan = cls.artifact["planning_2b"]
        cls.runs = cls.plan["runs"]
        cls.slots = {slot["id"]: slot for slot in json.loads(SLOTS.read_text(encoding="utf-8"))["slots"]}

    def test_the_artifact_names_its_schema_and_says_the_papers_are_private(self):
        self.assertEqual(self.artifact["schema"], "claude-native-practice-paired-runs/1")
        self.assertIn("private working papers", self.artifact["root"])

    def test_the_grid_is_complete_and_every_run_carries_a_hash_of_its_result(self):
        self.assertEqual(sorted((r["fixture"], r["trial"], r["arm"]) for r in self.runs), sorted((f, t, a) for f, t in CELLS for a in "ABC"))
        for run in self.runs:
            with self.subTest(run=run["run"]):
                self.assertEqual(run["run"], f"{run['fixture']}-{run['arm']}-{run['trial']}")
                self.assertRegex(run["result_sha256"], SHA256)
                if run["sessions_used"] > 1:
                    self.assertTrue(all(SHA256.match(h) for h in run["lost_work_readers"].values()))
                else:
                    self.assertNotIn("lost_work_readers", run)

    def test_a_run_that_did_not_declare_done_used_every_session_of_the_design(self):
        limit = self.plan["design"]["max_sessions"]
        for run in self.runs:
            if not run["declared_done"]:
                with self.subTest(run=run["run"]):
                    self.assertEqual(run["sessions_used"], limit)

    def test_the_recorded_decision_is_what_the_runs_give(self):
        recomputed = decision_from_runs(self.runs)
        for arm in "BC":
            recorded = self.plan["decision"][arm]
            for key in ("passes", "a_passes", "counted_cells", "cell_wins", "majority", "lost_work_events", "a_lost_work_events", "replaces_a"):
                with self.subTest(arm=arm, field=key):
                    self.assertEqual(recorded[key], recomputed[arm][key])
        self.assertEqual(self.plan["outcome"], "A stays the default" if not any(recomputed[a]["replaces_a"] for a in "BC") else "an arm replaces A")
        self.assertEqual(self.plan["outcome"], "A stays the default")

    def test_the_decision_is_live_not_typed_in(self):
        flipped = copy.deepcopy(self.runs)
        for run in flipped:
            if run["run"] in ("F5-B-1", "F5-B-2"):  # make the task list cheaper than A on both F5 cells: it would then win four of four
                run["cost_usd_list_equivalent"] = 1.0
        self.assertTrue(decision_from_runs(flipped)["B"]["replaces_a"])
        self.assertFalse(decision_from_runs(self.runs)["B"]["replaces_a"])
        failed = copy.deepcopy(self.runs)
        for run in failed:
            if run["arm"] == "B":
                run["resolved"] = False
        self.assertFalse(decision_from_runs(failed)["B"]["replaces_a"], "an arm that passes fewer runs than A cannot replace it")

    def test_lost_work_adds_up_and_the_single_session_run_has_no_readers(self):
        self.assertEqual(self.plan["lost_work"]["total_events"], sum(r["lost_work_events"] for r in self.runs))
        self.assertEqual(self.plan["lost_work"]["runs_with_one_session"], [r["run"] for r in self.runs if r["sessions_used"] == 1])
        self.assertNotEqual(self.plan["lost_work"]["first_reader_model"], self.plan["lost_work"]["second_reader_model"])

    def test_the_papers_the_results_rest_on_are_hashed(self):
        papers = list(self.plan["papers"].values()) + [self.plan["lost_work"][k] for k in ("protocol", "counts", "table")]
        for paper in papers:
            with self.subTest(path=paper["path"]):
                self.assertRegex(paper["sha256"], SHA256)
                self.assertGreater(paper["bytes"], 0)
                self.assertNotIn("/home/", paper["path"])

    def test_the_planning_rows_state_what_the_artifact_shows(self):
        recomputed = decision_from_runs(self.runs)
        planning, loops = self.slots["planning-persistence"], self.slots["loops-completion"]
        task_list = planning["alternatives"][0]
        self.assertTrue(task_list.startswith("Native Task tools with `CLAUDE_CODE_TASK_LIST_ID`: ranked second"))
        self.assertIn(f"won {recomputed['B']['cell_wins']} of {recomputed['B']['counted_cells']} cells", task_list)
        self.assertEqual(sorted(recomputed["B"]["won_cells"]), ["F6-t1", "F6-t2"])
        self.assertIn("both on the smaller F6 fixture", task_list)
        self.assertIn("`--allowedTools`", task_list)
        self.assertIn("ran all 8 sessions without declaring TASK-DONE", task_list)
        # The Codex review in GitHub of #1005 at 5c5eecaad (P2, workers.md:76): the ranked fallback reported the missing completion and supplied no condition, while the Ralph row requires one for the same failure.
        f5 = [run for run in self.runs if run["arm"] == "B" and run["fixture"] == "F5"]
        self.assertEqual((len(f5), [run["declared_done"] for run in f5], [run["sessions_used"] for run in f5]), (2, [False, False], [8, 8]))
        self.assertIn("it has no completion condition of its own (on F5 neither measured run declared TASK-DONE and both used all 8 sessions)", task_list)
        self.assertIn("so a headless driver needs an external done check, the Stop-hook completion gate of loops-completion (a test or an explicit condition), or it keeps launching sessions to its cap", task_list)
        self.assertIn("ranked third, for fallback only", planning["alternatives"][1])
        self.assertIn(f"task list {recomputed['B']['cell_wins']} of {recomputed['B']['counted_cells']}, loop {recomputed['C']['cell_wins']} of {recomputed['C']['counted_cells']}", planning["notes"])
        self.assertIn("0 events in all twelve runs", planning["notes"])
        self.assertEqual(planning["default"].split(" per ")[0], "Repository-resident task state")

    def test_the_ralph_row_carries_the_rulings_three_statements(self):
        loops = self.slots["loops-completion"]
        ralph = next(alt for alt in loops["alternatives"] if alt.startswith("Ralph-style headless loops"))
        self.assertNotIn("candidate until", ralph)
        for needle in ("third behind repository state files and the native task list", "for fallback only", "when neither can be used",
                       "An external done check is required", "never with the session cap alone",
                       "post hoc and provisional", "the preregistration named no criterion",
                       "preregisters its criterion before its first session", "ranked if it wins at least one cell, or ties repository state files on sessions and cost in some cell; else rejected"):
            with self.subTest(statement=needle):
                self.assertIn(needle, ralph)
        recomputed = decision_from_runs(self.runs)
        self.assertEqual(recomputed["C"]["cell_wins"], 0)
        self.assertIn("won no cell", ralph)
        self.assertEqual(recomputed["C"]["passes"], 4)
        self.assertIn("passed 4 of 4 runs", ralph)
        self.assertIn("with 0 lost work", ralph)

    def test_the_rows_cite_the_hashes_of_the_artifact(self):
        papers = self.plan["papers"]
        cited = {"RESULT.md": papers["result"]["sha256"], "analysis.txt": papers["analysis"]["sha256"], "lost_work.json": self.plan["lost_work"]["counts"]["sha256"]}
        for slot_id in ("planning-persistence", "loops-completion"):
            text = " ".join(self.slots[slot_id]["evidence"])
            self.assertIn(ARTIFACT_REL, text)
            for name, full in cited.items():
                with self.subTest(slot=slot_id, paper=name):
                    match = re.search(re.escape(name) + r"(?: sha256)? ([0-9a-f]{12})", text)
                    self.assertIsNotNone(match, f"{slot_id} does not cite {name}")
                    self.assertTrue(full.startswith(match.group(1)))

    def test_the_record_addendum_cites_the_artifact_and_states_the_decision(self):
        record = RECORD.read_text(encoding="utf-8")
        addendum = record.split("## Addendum (2026-10-10 and 2026-10-11): paired-run results", 1)[1]
        self.assertIn(f"../../{ARTIFACT_REL}", addendum)
        self.assertTrue((ROOT / ARTIFACT_REL).is_file())
        for needle in ("All 12 runs passed the hidden tests", "the task list won 2 of 4 cells (both F6) and the loop none", "Lost work: 0 events in all 12 runs",
                       "third behind repository state files and the native task list and for fallback only", "post hoc and provisional"):
            with self.subTest(statement=needle):
                self.assertIn(needle, " ".join(addendum.split()))


class OrchestrationRunTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.artifact = json.loads((ROOT / ARTIFACT_REL).read_text(encoding="utf-8"))
        cls.o = cls.artifact["orchestration_1"]
        cls.runs = {r["run"]: r for r in cls.o["runs"]}
        cls.slots = {slot["id"]: slot for slot in json.loads(SLOTS.read_text(encoding="utf-8"))["slots"]}

    def test_the_grid_is_complete_and_every_run_carries_a_hash_of_its_result(self):
        self.assertEqual(sorted(self.runs), sorted(f"{f}-{a}-1" for f in FIXTURES for a in "ABC"))
        for name, run in self.runs.items():
            with self.subTest(run=name):
                self.assertEqual(name, f"{run['fixture']}-{run['arm']}-1")
                self.assertRegex(run["result_sha256"], SHA256)
                self.assertEqual(run["void_in_primary"], run["fixture"] in ("F1", "F2"))
                if run["arm"] == "B":
                    self.assertRegex(run["workflow"]["journal_sha256"], SHA256)
                if run["arm"] == "C":
                    self.assertTrue(run["cost_is_estimate"])

    def test_the_recorded_rule_is_what_the_runs_and_the_pairs_give(self):
        for name, fixtures in (("primary_f3_to_f6", PRIMARY), ("sensitivity_all_six_regraded", FIXTURES)):
            recomputed, recorded = orchestration_rule(self.o, fixtures), self.o["analysis"][name]
            self.assertEqual(recorded["fixtures"], fixtures)
            self.assertEqual(recorded["resolved"], recomputed["resolved"])
            for arm in "ABC":
                self.assertAlmostEqual(recorded["mean_cost_usd_list_equivalent_not_billed"][arm], recomputed["mean_cost"][arm], places=2)
            for arm in "BC":
                with self.subTest(analysis=name, arm=arm):
                    self.assertEqual(recorded[f"{arm}_vs_A"], recomputed[arm])
                    self.assertFalse(recomputed[arm]["clears_rule"], "an orchestrated arm clears the rule: the rows say none does")

    def test_the_rule_is_live_not_typed_in(self):
        wins = copy.deepcopy(self.o)
        for pair in wins["judging"]["pairs"]:
            if pair["pair"] == "AB" and pair["fixture"] in PRIMARY:
                pair["counted_preference"] = "B"  # the judges prefer the Workflow on all four fixtures that count
        self.assertTrue(orchestration_rule(wins, PRIMARY)["B"]["clears_rule"])
        fails = copy.deepcopy(self.o)
        for run in fails["runs"]:
            if run["arm"] == "A" and run["fixture"] in ("F3", "F4"):
                run["resolved"] = False  # the single session fails two fixtures that B and C pass
        self.assertTrue(orchestration_rule(fails, PRIMARY)["B"]["clears_rule"])
        cheap = copy.deepcopy(self.o)
        for pair in cheap["judging"]["pairs"]:
            if pair["pair"] == "AC" and pair["fixture"] in PRIMARY:
                pair["counted_preference"] = "C"
        self.assertFalse(orchestration_rule(cheap, PRIMARY)["C"]["clears_rule"], "four judge wins do not clear a rule whose cost bound the team misses")
        for run in cheap["runs"]:
            if run["arm"] == "C":
                run["cost_usd_list_equivalent"] = run["cost_usd_list_equivalent"] / 4
        self.assertTrue(orchestration_rule(cheap, PRIMARY)["C"]["clears_rule"])

    def test_the_pairs_are_consistent_and_exactly_the_uncaptured_ones_are_void(self):
        pairs = self.o["judging"]["pairs"]
        self.assertEqual(sorted((p["fixture"], p["pair"]) for p in pairs), sorted((f, q) for f in FIXTURES for q in ("AB", "AC", "BC")))
        for p in pairs:
            with self.subTest(pair=f"{p['fixture']}-{p['pair']}"):
                self.assertEqual(sorted((p["x"], p["y"])), sorted(p["pair"]))
                self.assertIn(p["first_judge_prefers"], (p["x"], p["y"], "tie"))
                self.assertRegex(p["judge_sha256"], SHA256)
                self.assertRegex(p["refute_sha256"], SHA256)
                void = (p["fixture"], p["pair"]) in VOID_PAIRS
                self.assertEqual(p["void"], void)
                expected = None if (void or not p["refuter_holds"]) else p["first_judge_prefers"]
                self.assertEqual(p["counted_preference"], expected)
        self.assertEqual(sorted(name for name, run in self.runs.items() if not run["diff_captured"]), ["F3-C-1"])
        self.assertTrue(self.runs["F3-C-1"]["resolved"], "the hidden-test result of the run whose diff was not captured stands")

    def test_the_papers_the_orchestration_result_rests_on_are_hashed(self):
        for name, paper in self.o["papers"].items():
            with self.subTest(paper=name):
                self.assertRegex(paper["sha256"], SHA256)
                self.assertGreater(paper["bytes"], 0)
                self.assertNotIn("/home/", paper["path"])

    def test_the_orchestration_rows_state_what_the_artifact_shows(self):
        runs, o = self.runs, self.o
        mean = {a: sum(runs[f"{f}-{a}-1"]["cost_usd_list_equivalent"] for f in FIXTURES) / 6 for a in "ABC"}
        pairs = {(p["fixture"], p["pair"]): p for p in o["judging"]["pairs"]}
        a_over_b = sum(1 for f in FIXTURES if pairs[(f, "AB")]["counted_preference"] == "A")
        a_over_c = sum(1 for f in FIXTURES if pairs[(f, "AC")]["counted_preference"] == "A")
        b_over_a = sum(1 for f in FIXTURES if pairs[(f, "AB")]["counted_preference"] == "B")
        c_over_a = sum(1 for f in FIXTURES if pairs[(f, "AC")]["counted_preference"] == "C")
        c_runs = [runs[f"{f}-C-1"] for f in FIXTURES]
        b_wf = [runs[f"{f}-B-1"]["workflow"] for f in FIXTURES]
        returned = sum(w["verifier_returned"] for w in b_wf)
        cut = sum(1 for w in b_wf if w["verifier_started"] and not w["verifier_returned"])
        never = sum(1 for w in b_wf if not w["verifier_started"])
        orch, teams, workflow = self.slots["orchestration-frameworks"], self.slots["agent-teams"], self.slots["background-workflows"]
        evidence = next(e for e in orch["evidence"] if e.startswith("Paired run 1, 2026-10-10"))
        for needle in (f"the single session cost ${mean['A']:.2f} on average", f"the verify Workflow {mean['B'] / mean['A']:.1f}x and the agent team {mean['C'] / mean['A']:.1f}x",
                       f"on {a_over_b} of 6 fixtures and to the team's on {a_over_c} of the 5 where the team's diff was captured", "every mode passed 6 of 6"):
            with self.subTest(statement=needle):
                self.assertIn(needle, evidence)
        self.assertIn(evidence, teams["evidence"])
        self.assertIn(evidence, workflow["evidence"])
        for key, label in (("result", "RESULT.md"), ("score", "score.json")):
            match = re.search(re.escape(label) + r"(?: sha256)? ([0-9a-f]{12})", evidence)
            self.assertIsNotNone(match, f"the row does not cite {label}")
            self.assertTrue(o["papers"][key]["sha256"].startswith(match.group(1)))
        self.assertIn(f"(Workflow {b_over_a} of 6, team {c_over_a} of 5 comparable)", orch["notes"])
        self.assertIn(f"{mean['B'] / mean['A']:.1f}x and {mean['C'] / mean['A']:.1f}x its mean cost", orch["notes"])
        self.assertIn(f"it reached TEAM-DONE in {sum(r['team_done'] for r in c_runs)} of 6 runs, hit its $30 cap in {sum(r['capped_at_30_usd'] for r in c_runs)}", teams["notes"])
        # The Codex review in GitHub of #1005 at 5c5eecaad (P2, workers.md:29): the measured team cost 3.0x for the same bounded work, which the row's own Overturn when ("cost more for the same work") covers; the default is
        # scoped to work where workers must message each other, which paired run 1 did not measure, so the condition names that class.
        self.assertGreater(mean["C"] / mean["A"], 2.5)
        self.assertIn("A paired run on work where workers must message each other (the class this default is scoped to; paired run 1 measured bounded fixes, which need no messaging and fall outside it) shows teams "
                      "lose quality or cost more for the same work", teams["overturn_when"])
        self.assertIn("used only where workers must message each other", teams["default"])
        self.assertIn(f"the verifier returned in {returned} of 6 runs ({sum(1 for w in b_wf if w['verifier_refuted'])} refuted), was cut by the background-wait ceiling of `claude -p` in {cut} (45 minutes as the runner set it with `CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=2700000`; the client's default is 10 minutes: env-vars.md and headless.md of the pinned documentation), "
                      f"and in {never} the implementer itself ran to that ceiling", workflow["notes"])
        self.assertEqual((returned, cut, never), (2, 3, 1))
        self.assertIn("not found by name in 6 of 6 headless runs", workflow["notes"])
        # The Codex review in GitHub of #1005 at bf864c370 (P2, workers.md:44): the measured failure matched the row's Overturn when, but the route still sent a fenced headless run to the name lookup
        # that failed in 6 of 6 runs. The route now carries the scope, with the numbers the artifact gives, and Overturn when says which measured failures the scoped route does not avoid.
        self.assertIn("Scoped to headless `claude -p` runs fenced with `--setting-sources local`: launch a saved Workflow by `scriptPath` (its name was not found in 6 of 6 runs of paired run 1, arm B)", workflow["route"])
        self.assertIn(f"expect `claude -p` to stop waiting for a long verifier at its background-wait ceiling (10 minutes by default; the runner of paired run 1 set it to 45 minutes with `CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS`, "
                      f"and the verifier returned in {returned} of 6 runs and was cut in {cut})", workflow["route"])
        self.assertIn("a measured failure mode on our runs beyond the two that paired run 1, arm B measured in fenced headless runs "
                      "(the name lookup, which `scriptPath` avoids, and the verifier's wait ceiling, which the route above tells a session to expect)", workflow["overturn_when"])
        self.assertEqual(workflow["status"], "default-scoped")
        # The same review (P2, workers.md:29): the note said the team won no fixture, while the artifact counts one win (F2) and one tie (F4) against the single session.
        c_won = [f for f in FIXTURES if pairs[(f, "AC")]["counted_preference"] == "C"]
        a_won = [f for f in FIXTURES if pairs[(f, "AC")]["counted_preference"] == "A"]
        tied = [f for f in FIXTURES if pairs[(f, "AC")]["counted_preference"] == "tie"]
        primary_c_won = [f for f in PRIMARY if pairs[(f, "AC")]["counted_preference"] == "C"]
        self.assertEqual((c_won, tied, len(a_won), primary_c_won), (["F2"], ["F4"], 3, []))
        self.assertIn(f"it won {len(c_won)} of the 5 fixtures where its diff was captured ({c_won[0]}, in the analysis over all six fixtures; the single session won {len(a_won)} and {tied[0]} was a tie) "
                      f"and none of the primary fixtures {PRIMARY[0]} to {PRIMARY[-1]}", teams["notes"])
        self.assertNotIn("won no fixture", teams["notes"])

    def test_the_time_bounds_the_row_and_the_record_state_are_the_registered_ones(self):
        # The Codex review in GitHub of #1005 at 425240f6e (P2, workers.md:61): the orchestration-frameworks row and the record said "a 45-minute ceiling per run", while the registered design has two bounds, a 50-minute
        # process cap for a headless session (arms A and B) and a 45-minute cap for the team (arm C; preregistration.md:156), and the Workflow's verifier was cut by the background-wait ceiling of `claude -p`, which the runner
        # set to 45 minutes (the stderr of the four B runs reads "Background tasks still running 45m after the last turn"); the client's default is 10 minutes (the command center's Claude micro of #1005 at 49bb6494e, P2-1).
        caps = self.o["design"]["caps"]
        self.assertEqual((caps["headless_session_minutes"], caps["team_minutes"]), (50, 45))
        for run in self.o["runs"]:
            if run["arm"] != "C":
                self.assertLess(run["seconds"], caps["headless_session_minutes"] * 60, f"{run['run']} stayed inside the headless cap")
        c_runs = [x for x in self.o["runs"] if x["arm"] == "C"]
        stopped = sum(x["stopped_at_45_minutes"] for x in c_runs)
        not_done = sum(not x["team_done"] for x in c_runs)
        at_wait = sum(1 for x in self.o["runs"] if x["arm"] == "B" and not x["workflow"]["verifier_returned"])
        self.assertEqual((at_wait, stopped, not_done), (4, 3, 4))
        bounds = f"process caps of {caps['headless_session_minutes']} minutes per headless session and {caps['team_minutes']} per team"
        notes = self.slots["orchestration-frameworks"]["notes"]
        page = (SLOTS.parent / "workers.md").read_text(encoding="utf-8")
        record = " ".join(RECORD.read_text(encoding="utf-8").split())
        self.assertIn(bounds, notes)
        self.assertIn(f"{at_wait} of the 6 Workflow runs ended at the background-wait ceiling of `claude -p`, which the runner set to 45 minutes (`CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=2700000`; the client's default is 10 minutes), "
                      f"before the {caps['headless_session_minutes']}-minute process cap", notes)
        self.assertIn(f"{not_done} of the 6 team runs did not reach TEAM-DONE ({stopped} stopped at the {caps['team_minutes']}-minute team cap)", notes)
        self.assertIn(notes, page, "the page mirrors the row")
        self.assertIn(bounds, record)
        self.assertIn(f"was stopped at the {caps['team_minutes']}-minute team cap in {stopped}", record)
        for text in (notes, record, page):
            self.assertNotIn("a 45-minute ceiling", text)
        for text in (notes, record, page, self.slots["background-workflows"]["notes"], self.slots["background-workflows"]["route"], (SLOTS.parent / "workers.md").read_text(encoding="utf-8")):
            self.assertNotIn("own 45-minute wait", text)  # the command center's Claude micro of #1005 at 49bb6494e (P2-1): the 45 minutes is the runner's setting, not a property of the client
            self.assertNotIn("the 45-minute wait ceiling", text)

    def test_the_background_wait_ceiling_is_the_runners_setting_and_the_clients_default_is_ten_minutes(self):
        # The command center's Claude micro of #1005 at 49bb6494e (P2-1): "claude -p's own 45-minute wait" was false. The runner set CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=2700000 for every headless run (paired/orch_run.py
        # line 137, retained and hashed in papers.runner); the client's default is 10 minutes (env-vars.md line 357, headless.md line 77 of the retained documentation, papers.client_env_vars_page and client_headless_page).
        caps, papers = self.o["design"]["caps"], self.o["papers"]
        self.assertEqual((caps["bg_wait_ceiling_minutes"], caps["client_default_bg_wait_ceiling_minutes"]), (45, 10))
        self.assertIn("CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=2700000", caps["bg_wait_ceiling_setting"])
        self.assertEqual(2700000 // 60000, caps["bg_wait_ceiling_minutes"])
        self.assertEqual(papers["runner"]["line"], 137)
        self.assertEqual((papers["client_env_vars_page"]["line"], papers["client_headless_page"]["line"]), (357, 77))
        for name in ("runner", "client_env_vars_page", "client_headless_page"):
            self.assertRegex(papers[name]["sha256"], SHA256)
            self.assertGreater(papers[name]["bytes"], 0)
        # the four Workflow runs that ended at the ceiling had run background work for the ceiling and a few seconds: implementer plus verifier seconds are 2,702 to 2,703, the ceiling being 2,700 seconds
        waiting = [run["workflow"] for run in self.o["runs"] if run["arm"] == "B" and not run["workflow"]["verifier_returned"]]
        self.assertEqual(len(waiting), 4)
        for workflow in waiting:
            background = workflow["implementer_seconds"] + (workflow["verifier_seconds"] or 0)
            self.assertTrue(caps["bg_wait_ceiling_minutes"] * 60 <= background <= caps["bg_wait_ceiling_minutes"] * 60 + 10, background)
        # the rows, the pages and the record name the setting and the default, and the page carries the rows' text
        page = (SLOTS.parent / "workers.md").read_text(encoding="utf-8")
        for text in (self.slots["background-workflows"]["notes"], self.slots["orchestration-frameworks"]["notes"], page, " ".join(RECORD.read_text(encoding="utf-8").split())):
            self.assertIn("CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=2700000", text)
            self.assertIn("default is 10", text)
        for field in ("route", "notes"):
            self.assertIn(self.slots["background-workflows"][field], page, f"the page carries the {field} of background-workflows")
        self.assertIn("10 minutes by default", self.slots["background-workflows"]["route"])

    def test_the_record_addendum_states_the_orchestration_decision(self):
        record = " ".join(RECORD.read_text(encoding="utf-8").split())
        paragraph = record.split("**Orchestration (paired run 1).**", 1)[1].split("**", 1)[0]
        for needle in ("Every run passed the hidden tests in both analyses (18 of 18)", "F3's two pairs with the team are void: its diff was not captured", "Neither orchestrated arm clears the rule",
                       "the routing guidance for bounded fixes on north-star code names the single session", "Four defects of the measurement were found during the run"):
            with self.subTest(statement=needle):
                self.assertIn(needle, paragraph)
        self.assertIn("18 of 18 verdicts held", paragraph)


class RoutingRunTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.artifact = json.loads((ROOT / ARTIFACT_REL).read_text(encoding="utf-8"))
        cls.r = cls.artifact["routing_5"]
        cls.runs = {x["run"]: x for x in cls.r["runs"]}
        cls.record = " ".join(RECORD.read_text(encoding="utf-8").split())

    def test_the_grid_is_complete_and_every_run_is_a_structured_result_of_its_arm(self):
        self.assertEqual(sorted(self.runs), sorted(f"{pr}-{arm}-{t}" for pr in ROUTING_HEADS for arm in "OS" for t in (1, 2)))
        models = {"O": "claude-opus-5-5", "S": "claude-sonnet-5-5"}
        for name, run in self.runs.items():
            with self.subTest(run=name):
                self.assertEqual(name, f"{run['pr']}-{run['arm']}-{run['trial']}")
                self.assertEqual((run["model"], run["effort"], run["end_state"]), (models[run["arm"]], "medium", "structured"))
                self.assertRegex(run["result_sha256"], SHA256)
                self.assertRegex(run["head"], r"^[0-9a-f]{40}$")
                self.assertGreater(run["cost_usd_m2"], 0)
                self.assertIn(run["verdict"], ("ACK", "CHANGES_REQUESTED"))
        for entry in self.r["design"]["heads"]:
            with self.subTest(pr=entry["pr"]):
                self.assertEqual({x["head"] for x in self.r["runs"] if x["pr"] == entry["pr"]}, {entry["head"]}, "one head per pull request in both trials")
        self.assertEqual(sorted(e["pr"] for e in self.r["design"]["heads"]), sorted(ROUTING_HEADS))

    def test_the_findings_name_runs_of_their_own_head_and_arm(self):
        self.assertEqual(len(self.r["findings"]), 12)
        self.assertEqual(len({f["id"] for f in self.r["findings"]}), 12)
        for finding in self.r["findings"]:
            for arm in "OS":
                with self.subTest(finding=finding["id"], arm=arm):
                    self.assertEqual(len(set(finding["found"][arm])), len(finding["found"][arm]))
                    for run in finding["found"][arm]:
                        self.assertEqual((self.runs[run]["pr"], self.runs[run]["arm"]), (finding["pr"], arm))

    def test_the_recorded_decision_is_what_the_rows_give(self):
        got, dec = routing_rule(self.r), self.r["decision"]
        self.assertEqual(got["verdict"], "OPUS STAYS")
        self.assertTrue(dec["verdict"].startswith(got["verdict"]))
        self.assertEqual(dec["detections"], got["detections"])
        self.assertEqual(dec["detections"], {"O": 7, "S": 6})
        self.assertEqual(dec["missed_by_sonnet"], got["missed"])
        self.assertEqual(got["missed"], ["G10"])
        self.assertEqual(dec["opus_found_any"], sum(1 for f in self.r["findings"] if f["found"]["O"]))
        self.assertEqual(dec["decisive_findings"], len(self.r["findings"]))
        for arm in "OS":
            self.assertAlmostEqual(dec["cost_usd_list_equivalent"][arm], got["cost"][arm], places=1)
        self.assertAlmostEqual(dec["cost_ratio_sonnet_over_opus"], got["ratio"], places=3)
        self.assertLessEqual(got["ratio"], ROUTING_COST_BOUND, "the cost rule holds; the recall rule is what fails")
        self.assertEqual(dec["tolerant_reading_holds"], got["tolerant"])
        self.assertTrue(got["tolerant"])
        for key, value in (("pooled_mean_detection_rate", got["pooled"]), ("strict_pass_chance_if_identical", got["strict_floor"]), ("tolerant_pass_chance_if_identical", got["tolerant_floor"]),
                           ("tolerant_per_finding_clause_pass_chance_if_identical", got["tolerant_clause_floor"]), ("strict_pass_chance_if_identical_per_finding_rates", got["strict_floor_per_finding"])):
            with self.subTest(figure=key):
                self.assertAlmostEqual(dec[key], value, places=3)
        self.assertAlmostEqual(noise_floor(0.8, 12, True), 0.035, places=3)
        self.assertAlmostEqual(noise_floor(0.8, 12, False), 0.733, places=3)
        self.assertAlmostEqual(got["tolerant_floor"], 0.5551, places=3)
        self.assertAlmostEqual(got["tolerant_clause_floor"], 0.6204, places=3)
        self.assertAlmostEqual(got["strict_floor_per_finding"], 0.7305, places=3)
        self.assertEqual(self.r["judging"]["contested_cells"], 0)

    @unittest.skipUnless(importlib.util.find_spec("numpy"), "numpy is not installed")
    def test_the_tolerant_floor_matches_numpy_convolve_where_numpy_is_installed(self):
        # The Codex review in GitHub of #1005 at 425240f6e (P1, line 91): the sum of the per-finding differences is the convolution of their distributions (numpy 2.5.3, numpy.convolve documentation); the running
        # total of tolerant_floor is checked against numpy's own convolution, for the pooled rate of the run and for other rates and sizes.
        import numpy
        for p, n in ((0.27, 12), (0.3, 3), (0.5, 7), (0.9, 12)):
            with self.subTest(p=p, n=n):
                b = [(1 - p) ** 2, 2 * p * (1 - p), p ** 2]
                step = numpy.zeros(4)  # the differences S_f - O_f of -1, 0, 1 and 2 (a difference below -1 is outside the per-finding clause)
                for o in range(3):
                    for s in range(3):
                        if s - o >= -1:
                            step[s - o + 1] += b[o] * b[s]
                total = numpy.array([1.0])
                for _ in range(n):
                    total = numpy.convolve(total, step)
                expected = float(sum(chance for index, chance in enumerate(total) if index - n >= -2))  # entry k holds the running total k - n
                self.assertAlmostEqual(tolerant_floor(p, n), expected, places=12)

    def test_the_tolerant_floor_counts_both_clauses_of_the_reading(self):
        # The Codex review in GitHub of #1005 at 5c5eecaad (P2): the tolerant reading needs every S_f >= O_f - 1 AND a total within two, and the floor printed (0.62) modelled the first clause only.
        p, n = 0.3, 3
        b = [(1 - p) ** 2, 2 * p * (1 - p), p ** 2]
        brute = 0.0
        for outcome in itertools.product(range(3), repeat=2 * n):
            opus, sonnet = outcome[:n], outcome[n:]
            if all(s >= o - 1 for o, s in zip(opus, sonnet)) and sum(sonnet) >= sum(opus) - 2:
                chance = 1.0
                for count in outcome:
                    chance *= b[count]
                brute += chance
        self.assertAlmostEqual(tolerant_floor(p, n), brute, places=9)
        self.assertLess(tolerant_floor(p, n), noise_floor(p, n, False), "the clause on the totals removes outcomes the per-finding clause admits")
        got = routing_rule(self.r)
        self.assertLess(got["tolerant_floor"], got["tolerant_clause_floor"])
        self.assertEqual((round(got["tolerant_floor"], 2), round(got["tolerant_clause_floor"], 2)), (0.56, 0.62))
        # the reading itself: three findings each one run short is within the per-finding clause and outside the totals
        shorter = copy.deepcopy(self.r)
        taken = 0
        for finding in shorter["findings"]:
            if len(finding["found"]["S"]) >= 1 and taken < 3 and finding["id"] != "G10":
                finding["found"]["S"] = finding["found"]["S"][:-1]
                taken += 1
        got = routing_rule(shorter)
        self.assertEqual(taken, 3)
        self.assertFalse(got["tolerant"], "a total more than two behind is outside the tolerant reading")

    def test_the_ruling_keeps_its_condition_and_the_two_trial_verdict_says_what_it_rests_on(self):
        ruling, dec = self.r["ruling"], self.r["decision"]
        self.assertIn(SONNET_CONDITION, ruling["routing"])
        paragraph = routing_paragraph(self.r)
        for needle in (SONNET_CONDITION, "a ruled extension and not a preregistered outcome", "not something run 5 measured", "not a significance test"):
            with self.subTest(statement=needle):
                self.assertIn(needle, paragraph)
        self.assertIn("a ruled extension", dec["two_trial_verdict_basis"])
        self.assertIn("after seeing that result", dec["two_trial_verdict_basis"])
        # The command center's Claude micro of #1005 at 425240f6e (P3-1): addendum 1 (line 13), written before any run, fixed the trigger too, which ends the run after a passing trial 1.
        self.assertIn("and so was its trigger, which ends the run after a passing trial 1 (Sonnet takes review micros, no second trial)", dec["two_trial_verdict_basis"])
        self.assertNotIn("but the decision to run them was not", dec["two_trial_verdict_basis"])
        self.assertIn("the registered trigger ended the run there (Sonnet takes review micros, no second trial), and the command center added one after seeing the result", paragraph)
        self.assertIn("Opus for every Claude read or micro of trading code and gate code", ruling["routing"])
        self.assertIn("papers.addendum_01, lines 17-18", dec["tolerant_floor_basis"]["reading_and_null_model"])
        self.assertIn("numpy.convolve", dec["tolerant_floor_basis"]["sum_of_independent_differences"])
        self.assertEqual(dec["two_trial_verdict_basis_source"], self.r["papers"]["addendum_03"], "the basis cites addendum 3 of the run's papers by path, size and hash")
        self.assertEqual(self.r["papers"]["addendum_03"]["path"], "paired-routing/addendum-03-trial-2-extension-20261011.md")
        self.assertIn("papers.ruling_correction", self.r["ruling"]["correction_note"])
        self.assertTrue(self.r["papers"]["ruling_correction"]["path"].endswith("ruling-routing-run5-two-trial-20261011.correction-01.md"))
        self.assertIn("second_trial", self.r["design"])
        self.assertIn("decided after trial 1", self.r["design"]["second_trial"])

    @unittest.skipUnless(os.environ.get("PAIRED_PAPER_ROOTS"), "set PAIRED_PAPER_ROOTS to the directories (separated like PATH) that hold the private papers: the research directory of the run and the command center's directory")
    def test_the_private_papers_resolve_to_their_recorded_hashes_where_they_are_available(self):
        # The command center's Claude read of #1005 at 5c5eecaad (P2-1): a cited ruling was edited after the record cited it and nothing in the repository could notice.
        import hashlib
        roots = [Path(item) for item in os.environ["PAIRED_PAPER_ROOTS"].split(os.pathsep) if item]
        cited = []

        def walk(value, trail=""):
            if isinstance(value, dict):
                if "path" in value and "sha256" in value:
                    cited.append((trail, value))
                for key, item in value.items():
                    walk(item, f"{trail}/{key}")
            elif isinstance(value, list):
                for index, item in enumerate(value):
                    walk(item, f"{trail}[{index}]")

        walk(self.artifact)
        self.assertGreaterEqual(len(cited), 29)
        for trail, entry in cited:
            with self.subTest(entry=trail):
                relative = entry["path"].split(" (")[0]
                files = [root / relative for root in roots if (root / relative).is_file()]
                self.assertTrue(files, f"{relative} is under none of the roots")
                content = files[0].read_bytes()
                self.assertEqual(hashlib.sha256(content).hexdigest()[:len(entry["sha256"])], entry["sha256"])
                if "bytes" in entry:
                    self.assertEqual(len(content), entry["bytes"])
                if "line" in entry:  # a cited line holds what the artifact says it holds
                    self.assertIn(entry["contains"], files[0].read_text(encoding="utf-8").split("\n")[entry["line"] - 1])
        # the registered reading and null model the tolerant floor cites (Codex on #1005 at 425240f6e, P1, line 91) are at the lines the artifact names
        relative = self.r["papers"]["addendum_01"]["path"]
        lines = next(root / relative for root in roots if (root / relative).is_file()).read_text(encoding="utf-8").splitlines()
        self.assertIn("a tolerant reading (S_f >= O_f - 1 on every decisive finding and the total of Sonnet's detections at least Opus's total minus 2)", lines[16])
        self.assertIn("Noise floors for two identical reviewers who each find a finding with probability p", lines[17])

    def test_the_rule_is_live_not_typed_in(self):
        finds = copy.deepcopy(self.r)
        for finding in finds["findings"]:
            if finding["id"] == "G10":
                finding["found"]["S"] = ["989-S-2"]  # Sonnet finds the finding in one run, as often as Opus does
        self.assertEqual(routing_rule(finds)["verdict"], "SONNET TAKES")
        pricey = copy.deepcopy(finds)
        for run in pricey["runs"]:
            if run["arm"] == "S":
                run["cost_usd_m2"] *= 4  # four times the cost: 67% of Opus's, over the bound
        self.assertEqual(routing_rule(pricey)["verdict"], "OPUS STAYS")
        misses = copy.deepcopy(finds)
        for finding in misses["findings"]:
            if finding["id"] == "G1":
                finding["found"]["S"] = []
        self.assertEqual(routing_rule(misses)["verdict"], "OPUS STAYS")
        self.assertFalse(routing_rule(misses)["tolerant"], "a finding Opus found twice and Sonnet never is outside the tolerant reading")

    def test_the_papers_are_hashed_and_the_ruling_is_cited_by_path_and_hash(self):
        for name, paper in self.r["papers"].items():
            with self.subTest(paper=name):
                self.assertRegex(paper["sha256"], SHA256)
                self.assertGreater(paper["bytes"], 0)
                self.assertNotIn("/home/", paper["path"])
        ruling = self.r["ruling"]
        self.assertEqual(ruling["sha256"], self.r["papers"]["ruling"]["sha256"])
        self.assertIn("research-cc-role-20261008/ruling-routing-run5-two-trial-20261011.md", ruling["path"])
        self.assertRegex(self.r["papers"]["preregistration"]["sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(self.r["beside_the_rule"]["verdicts_that_differ"], sorted(f"#{x['pr']} t{x['trial']}" for x in self.r["runs"] if x["arm"] == "S" and self.runs[f"{x['pr']}-O-{x['trial']}"]["verdict"] != x["verdict"]))

    def test_the_record_states_the_routing_decision_and_the_owed_table_is_right(self):
        paragraph = routing_paragraph(self.r)
        self.assertEqual(self.record.count(paragraph), 1, "the addendum carries the paragraph the artifact gives")
        self.assertNotIn("Paired run 5 (preregistration", self.record, "a decided run is not owed")
        row = next(line for line in RECORD.read_text(encoding="utf-8").splitlines() if line.startswith("| Paired run 4 ("))
        self.assertIn("(its private preregistration, approved by the command center", row)
        self.assertIn("stopped on 2026-10-11 at the owner's priority after 2 of 8 pairs, with no verdict", row)
        self.assertIn(f"(private record `{STOP_RECORD}`)", row)
        self.assertNotRegex(row, r"sha256 `[0-9a-f]{7,}`", "the row names its private records by file only")
        self.assertNotIn("its result is a later record", row)
        for needle in ("no slot row, default or skill text changes", f"`{self.r['papers']['ruling']['path']}`"):
            self.assertIn(needle, paragraph)
        self.assertNotRegex(paragraph, r"sha256 `[0-9a-f]{7,}`", "the paragraph names its private papers by path only")

    def test_a_changed_figure_in_the_paragraph_is_caught(self):
        paragraph = routing_paragraph(self.r)
        mutated = copy.deepcopy(self.r)
        mutated["decision"]["trial_1_alone"]["strict_pass_chance_if_identical"] = 0.5
        self.assertNotEqual(routing_paragraph(mutated), paragraph)
        for run in mutated["runs"]:
            if run["arm"] == "S":
                run["cost_usd_m2"] *= 2
        self.assertNotIn(paragraph, routing_paragraph(mutated))


class PrivateRecordNamingTests(unittest.TestCase):
    def test_the_third_selection_row_names_its_private_sweep_by_file_only(self):
        row = next(line for line in RECORD.read_text(encoding="utf-8").splitlines() if line.startswith("| Third selection |"))
        self.assertIn("`research/api-surfaces-20261008/FINAL.md` on the producing host (corrected bytes)", row)
        self.assertNotRegex(row, r"sha256 `[0-9a-f]{7,}`", "the row names its private sweep by file only")


if __name__ == "__main__":
    unittest.main()
