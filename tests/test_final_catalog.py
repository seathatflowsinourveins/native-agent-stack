"""Tests for scripts/final_catalog.py: pick normalization follows the frozen agreement rule, every agreement class
folds as the rule says, the join covers every edition row once, the GPT-6.1 Sol record changes statuses only through
the rule, and --check fails on a stale record but only reports a grand-list move."""

from __future__ import annotations

import contextlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import final_catalog as f

ROOT = Path(__file__).resolve().parents[1]


def pick(key, label):
    return {"key": key, "label": label}


class NormalizationTests(unittest.TestCase):
    def test_github_urls_reduce_to_owner_and_repository(self):
        for url in ("https://github.com/Owner/Repo", "github.com/owner/repo/", "https://github.com/owner/repo.git",
                    "https://www.github.com/owner/repo/tree/main", "http://github.com/owner/repo#readme"):
            self.assertEqual(f.github_key(url), "owner/repo", url)

    def test_non_github_urls_have_no_repository_key(self):
        self.assertIsNone(f.github_key("https://ubuntu.com/download/server"))
        self.assertIsNone(f.github_key(None))

    def test_a_github_pick_is_its_repository_whatever_its_name(self):
        candidates = ["Claude Code"]
        self.assertEqual(f.pick_key({"name": "anything", "repository": "https://github.com/anthropics/claude-code"},
                                    candidates), "anthropics/claude-code")

    def test_a_named_pick_matches_the_packet_candidate_despite_word_order_and_a_role_suffix(self):
        candidates = ["Ubuntu 26.04.1 LTS (Canonical WSL image)", "Ubuntu 24.04.5 LTS (Canonical WSL image)"]
        primary = {"name": "Ubuntu 26.04.1 LTS (Canonical WSL image), primary", "repository": "https://ubuntu.com/x"}
        record = {"name": "Ubuntu 24.04.5 LTS WSL image (Canonical)", "repository": "https://releases.ubuntu.com/24.04.5"}
        self.assertEqual(f.pick_key(primary, candidates), "name:ubuntu 26.04.1 lts canonical wsl image")
        self.assertEqual(f.pick_key(record, candidates), "name:ubuntu 24.04.5 lts canonical wsl image")

    def test_an_unmatched_name_stands_as_written(self):
        self.assertEqual(f.pick_key({"name": "Command and secret-path guard (K4)"}, []),
                         "name:command and secret path guard k4")


class AgreementTests(unittest.TestCase):
    def test_the_four_cases(self):
        self.assertEqual(f.agreement({"a", "b"}, "recommended", {"a", "b"}, "recommended"), "agree")
        self.assertEqual(f.agreement({"a", "b"}, "recommended", {"b", "c"}, "recommended"), "overlap")
        self.assertEqual(f.agreement({"a"}, "recommended", {"c"}, "recommended"), "differ")
        # Same picks but one family asks for a comparison: not agreement.
        self.assertEqual(f.agreement({"a"}, "compare", {"a"}, "recommended"), "overlap")


class FoldTests(unittest.TestCase):
    def test_agree_and_recommended_gives_two_family_picks(self):
        c = [pick("a", "o/a"), pick("b", "o/b")]
        result = f.fold(c, {"a", "b"}, "recommended", [], c, {"a", "b"}, "recommended", "agree")
        self.assertEqual(result, ("two_family_pick", ["o/a", "o/b"], ["o/a", "o/b"], [], []))

    def test_agree_on_a_comparison_keeps_it_a_comparison(self):
        c = [pick("a", "o/a")]
        status, picks, _, _, arms = f.fold(c, {"a"}, "compare", ["a (recommended)", "baseline"], c, {"a"}, "compare",
                                           "agree")
        self.assertEqual(status, "comparison")
        self.assertEqual(picks, [])
        self.assertEqual(arms, ["a (recommended)", "baseline"])  # o/a is already named by an arm

    def test_overlap_of_two_recommendations_keeps_the_shared_pick_and_challenges_it_with_the_rest(self):
        c = [pick("a", "o/a"), pick("b", "o/b")]
        g = [pick("a", "o/a"), pick("c", "o/c")]
        result = f.fold(c, {"a", "b"}, "recommended", [], g, {"a", "c"}, "recommended", "overlap")
        self.assertEqual(result, ("partial_comparison", ["o/a"], ["o/a"], ["o/b", "o/c"], ["o/b", "o/c"]))

    def test_overlap_keeps_the_shared_pick_standing_even_when_both_families_ask_for_a_comparison(self):
        # The overlap clause ("the shared picks stand") carries no status condition.
        c = [pick("a", "o/a"), pick("b", "o/b")]
        g = [pick("a", "o/a")]
        result = f.fold(c, {"a", "b"}, "compare", ["o/a with reranker", "o/b"], g, {"a"}, "compare", "overlap")
        self.assertEqual(result, ("partial_comparison", ["o/a"], ["o/a"], ["o/b"], ["o/a with reranker", "o/b"]))

    def test_the_same_picks_with_split_statuses_stand_with_nothing_left_to_compare(self):
        c = [pick("a", "o/a")]
        result = f.fold(c, {"a"}, "recommended", [], c, {"a"}, "compare", "overlap")
        self.assertEqual(result, ("shared_pick", ["o/a"], ["o/a"], [], []))

    def test_picks_sharing_a_generic_repository_name_are_both_kept(self):
        # Regression: two packs both named "skills" must stay two arms.
        c = [pick("t", "trailofbits/skills")]
        g = [pick("m", "mattpocock/skills")]
        status, _, _, _, arms = f.fold(c, {"t"}, "recommended", [], g, {"m"}, "compare", "differ")
        self.assertEqual(status, "comparison")
        self.assertEqual(arms, ["mattpocock/skills", "trailofbits/skills"])

    def test_an_arm_description_names_a_pick_as_whole_words_only(self):
        self.assertTrue(f.mentioned("mksglu/context-mode", ["Context Mode (frozen control)"]))
        self.assertTrue(f.mentioned("anthropics/sandbox-runtime", ["sandbox-runtime (recommended)"]))
        self.assertFalse(f.mentioned("rtk-ai/rtk", ["artkit baseline"]))
        self.assertFalse(f.mentioned("qdrant/qdrant", ["SocratiCode (embeddings from the local model server)"]))

    def test_differ_puts_every_pick_of_both_families_into_the_comparison(self):
        c = [pick("a", "o/a")]
        g = [pick("c", "x/c")]
        result = f.fold(c, {"a"}, "recommended", [], g, {"c"}, "recommended", "differ")
        self.assertEqual(result, ("comparison", [], [], [], ["o/a", "x/c"]))


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.data = f.build()
        self.edition = json.loads((ROOT / f.EDITION).read_text(encoding="utf-8"))

    def test_every_edition_row_appears_once_in_order(self):
        self.assertEqual([r["layer_id"] for r in self.data["rows"]], [r["layer_id"] for r in self.edition["rows"]])

    def test_every_status_is_known_and_the_counts_add_up(self):
        for row in self.data["rows"]:
            self.assertIn(row["final"]["status"], f.STATUSES)
        self.assertEqual(sum(self.data["summary"]["final_status"].values()), len(self.data["rows"]))

    def test_trading_rows_wait_for_their_owner_and_uncovered_cross_rows_say_so(self):
        for row in self.data["rows"]:
            if row["blind"] is None:
                expected = "owner_lane_run_pending" if row["catalog"] == "us-equities" else "no_blind_record"
                self.assertEqual(row["final"]["status"], expected, row["layer_id"])
                self.assertEqual(row["final"]["standing_picks"], [])

    def test_standing_picks_only_where_the_rule_allows_them(self):
        for row in self.data["rows"]:
            if row["final"]["standing_picks"]:
                self.assertIn(row["final"]["status"], ("two_family_pick", "shared_pick", "partial_comparison"),
                              row["layer_id"])

    def test_every_pick_both_families_made_stands_and_every_other_pick_challenges_it(self):
        judged = 0
        for row in self.data["rows"]:
            if not row["cross_family"]:
                continue
            judged += 1
            candidates = f.packet_names(row["layer_id"])
            c = {f.pick_key(p, candidates) for p in row["blind"]["picks"]}
            g = {f.pick_key(p, candidates) for p in row["cross_family"]["picks"]}
            final = row["final"]
            if row["agreement"] == "agree" and row["blind"]["status"] == "compare":
                self.assertEqual(final["standing_picks"], [], row["layer_id"])
                continue
            self.assertEqual(len(final["standing_picks"]), len(c & g), row["layer_id"])
            self.assertEqual(final["standing_picks"], final["shared_picks"], row["layer_id"])
            self.assertEqual(len(final["challengers"]), len(c ^ g), row["layer_id"])
        self.assertGreater(judged, 0)

    def test_the_selection_of_record_is_carried_unchanged(self):
        by_id = {r["layer_id"]: r for r in self.edition["rows"]}
        for row in self.data["rows"]:
            self.assertEqual([w["pin"] for w in row["selection_of_record"]],
                             [w.get("pin") for w in by_id[row["layer_id"]]["winners"]])

    def test_every_row_has_a_gate(self):
        for row in self.data["rows"]:
            self.assertTrue(row["gate_ledger"], row["layer_id"])

    def test_picks_of_packet_candidates_carry_the_captured_upstream_facts(self):
        facts = f.load_facts()
        checked = 0
        for row in self.data["rows"]:
            for family in ("blind", "cross_family"):
                for p in (row[family] or {}).get("picks", []):
                    key = f.github_key(p["repository"])
                    if key in facts:
                        checked += 1
                        self.assertEqual(p["upstream"], facts[key], (row["layer_id"], key))
                    else:
                        self.assertIsNone(p["upstream"], (row["layer_id"], p["repository"]))
        self.assertGreater(checked, 0)


class CrossFamilyFoldTests(unittest.TestCase):
    """A synthetic GPT-6.1 Sol record over a copy of the real inputs: statuses move only as the rule says."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        for rel in (f.EDITION, f.SELECTION, f.GRAND_LIST):
            (self.tmp / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(ROOT / rel, self.tmp / rel)
        shutil.copytree(ROOT / f.PACKETS, self.tmp / f.PACKETS)
        selection = json.loads((ROOT / f.SELECTION).read_text(encoding="utf-8"))
        layers = []
        for row in selection["layers"]:
            picks = [dict(p) for p in row["selection"]]
            status = "compare" if row["status"] == "compare" else "recommended"
            if row["layer_id"] == "secrets-credentials":
                picks = [{"name": "gitleaks", "repository": "https://github.com/gitleaks/gitleaks"}]
            if row["layer_id"] == "web-research":
                picks = picks[:1] + [{"name": "Crawl4AI", "repository": "https://github.com/unclecode/crawl4ai"}]
            layers.append({"layer_id": row["layer_id"], "status": status, "critic_verdict": "upheld", "picks": picks,
                           "deciding_head_to_head": ""})
        target = self.tmp / f.CROSS_FAMILY
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({"family": "synthetic", "run": {}, "contamination_audit": {}, "layers": layers}))
        self.patch = mock.patch.object(f, "ROOT", self.tmp)
        self.patch.start()
        self.data = f.build()
        self.rows = {r["layer_id"]: r for r in self.data["rows"]}

    def tearDown(self):
        self.patch.stop()
        shutil.rmtree(self.tmp)

    def test_identical_recommendations_become_two_family_picks(self):
        row = self.rows["native-clients"]
        self.assertEqual(row["agreement"], "agree")
        self.assertEqual(row["final"]["status"], "two_family_pick")
        self.assertEqual(row["final"]["standing_picks"], ["anthropics/claude-code", "openai/codex"])

    def test_disjoint_picks_become_a_comparison_of_both(self):
        row = self.rows["secrets-credentials"]
        self.assertEqual(row["agreement"], "differ")
        self.assertEqual(row["final"]["status"], "comparison")
        self.assertIn("gitleaks/gitleaks", row["final"]["comparison_arms"])
        self.assertIn("betterleaks/betterleaks", row["final"]["comparison_arms"])

    def test_partly_shared_picks_keep_the_shared_one_standing(self):
        row = self.rows["web-research"]
        self.assertEqual(row["agreement"], "overlap")
        self.assertEqual(row["final"]["status"], "partial_comparison")
        self.assertEqual(row["final"]["standing_picks"], ["adbar/trafilatura"])
        self.assertEqual(row["final"]["challengers"], ["microsoft/playwright-cli", "unclecode/crawl4ai"])
        self.assertIn("unclecode/crawl4ai", row["final"]["comparison_arms"])

    def test_agreed_comparisons_stay_comparisons(self):
        for layer in ("durable-memory", "semantic-rag", "token-efficiency", "isolation", "hosting-services"):
            self.assertEqual(self.rows[layer]["final"]["status"], "comparison", layer)

    def test_rows_outside_the_blind_run_are_untouched(self):
        self.assertEqual(self.rows["cross:runtime-workers"]["final"]["status"], "no_blind_record")
        self.assertEqual(self.rows["backtesting-engine"]["final"]["status"], "owner_lane_run_pending")


class CheckTests(unittest.TestCase):
    def test_checked_in_outputs_are_fresh(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(f.main(["--check"]), 0)
        self.assertEqual(json.loads(out.getvalue())["status"], "passed")

    def test_a_grand_list_move_is_drift_and_anything_else_is_stale(self):
        data = f.build()
        moved = json.loads(json.dumps(data))
        moved["inputs"][f.GRAND_LIST] = "0" * 64
        for row in moved["rows"]:
            if row["grand_list"]:
                row["grand_list"]["open_gaps"] = -1
        self.assertEqual(f.without_context(moved), f.without_context(data))
        changed = json.loads(json.dumps(data))
        changed["rows"][0]["final"]["status"] = "comparison"
        self.assertNotEqual(f.without_context(changed), f.without_context(data))

    def test_generated_output_passes_the_private_content_guard(self):
        data = f.build()
        for text in (json.dumps(data, indent=2, ensure_ascii=False), f.render_md(data)):
            for label, pattern in f.PRIVATE_CONTENT:
                self.assertIsNone(pattern.search(text), label)


if __name__ == "__main__":
    unittest.main()
