"""Tests for scripts/final_catalog.py: the record names what each blind half picked in neutral evidence terms and is not
an install list (no output states that anything installs or is installed, and quoted pins leave out the edition's
install note); pick normalization and the agreement classes follow the frozen rule except for the two disclosed
extensions, which the record reports next to the class the rule's text gives as written; an arm names a pick only by
its full owner/name; the join covers every edition row once; and --check, run against real files, fails on a stale
output or a changed agreement rule but only reports a grand-list move."""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import final_catalog as f

ROOT = Path(__file__).resolve().parents[1]


def pick(key, label, written=None):
    return {"key": key, "label": label, "written": written or key}


def literal_url(url: str) -> str:
    """The agreement rule's own normalization of a repository URL (its line 2): lowercase, no trailing slash or .git."""
    text = (url or "").strip().lower().rstrip("/")
    return text[:-4] if text.endswith(".git") else text


def run_main(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = f.main(argv)
    return code, out.getvalue(), err.getvalue()


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
        repo = {"name": "anything", "repository": "https://github.com/anthropics/claude-code"}
        self.assertEqual(f.pick_key(repo, candidates), "anthropics/claude-code")
        self.assertEqual(f.written_key(repo), "anthropics/claude-code")

    def test_packet_matching_drops_word_order_and_a_role_suffix(self):
        # The second extension: the rule as written normalizes such a pick by its name alone.
        candidates = ["Ubuntu 26.04.1 LTS (Canonical WSL image)", "Ubuntu 24.04.5 LTS (Canonical WSL image)"]
        primary = {"name": "Ubuntu 26.04.1 LTS (Canonical WSL image), primary", "repository": "https://ubuntu.com/x"}
        record = {"name": "Ubuntu 24.04.5 LTS WSL image (Canonical)", "repository": "https://releases.ubuntu.com/24.04.5"}
        self.assertEqual(f.pick_key(primary, candidates), "name:ubuntu 26.04.1 lts canonical wsl image")
        self.assertEqual(f.pick_key(record, candidates), "name:ubuntu 24.04.5 lts canonical wsl image")

    def test_the_written_normalization_keeps_a_name_as_written(self):
        primary = {"name": "Ubuntu 26.04.1 LTS (Canonical WSL image),  primary", "repository": "https://ubuntu.com/x"}
        plain = {"name": "Ubuntu 26.04.1 LTS (Canonical WSL image)", "repository": "https://ubuntu.com/x"}
        self.assertEqual(f.written_key(primary), "name:ubuntu 26.04.1 lts (canonical wsl image), primary")
        self.assertNotEqual(f.written_key(primary), f.written_key(plain))

    def test_an_unmatched_name_stands_as_written(self):
        self.assertEqual(f.pick_key({"name": "Command and secret-path guard (K4)"}, []),
                         "name:command and secret path guard k4")

    def test_every_pick_url_in_both_records_is_a_plain_repository_url(self):
        # Reducing a GitHub URL to owner/name equals the rule's literal URL form for every pick on record, so that
        # reduction is not a third extension.
        checked = 0
        for rel, field in ((f.SELECTION, "selection"), (f.CROSS_FAMILY, "picks")):
            for row in json.loads((ROOT / rel).read_text(encoding="utf-8"))["layers"]:
                for p in row.get(field) or []:
                    key = f.github_key(p.get("repository"))
                    if key is None:
                        continue
                    checked += 1
                    self.assertEqual(literal_url(p["repository"]), "https://github.com/" + key,
                                     (rel, row["layer_id"], p["repository"]))
        self.assertGreater(checked, 100)


class AgreementTests(unittest.TestCase):
    def test_the_generator_classes(self):
        self.assertEqual(f.agreement({"a", "b"}, "recommended", {"a", "b"}, "recommended"), "agree")
        self.assertEqual(f.agreement({"a", "b"}, "compare", {"a", "b"}, "compare"), "agree")
        self.assertEqual(f.agreement({"a", "b"}, "recommended", {"b", "c"}, "recommended"), "overlap")
        self.assertEqual(f.agreement({"a"}, "recommended", {"c"}, "recommended"), "differ")
        # The first extension: equal sets with unequal statuses count as overlap.
        self.assertEqual(f.agreement({"a"}, "compare", {"a"}, "recommended"), "overlap")

    def test_the_rule_as_written_leaves_equal_sets_with_unequal_statuses_unclassified(self):
        self.assertEqual(f.agreement_as_written({"a"}, "compare", {"a"}, "recommended"), "unclassified")
        self.assertEqual(f.agreement_as_written({"a"}, "compare", {"a"}, "compare"), "agree")
        self.assertEqual(f.agreement_as_written({"a", "b"}, "compare", {"a"}, "recommended"), "overlap")
        self.assertEqual(f.agreement_as_written({"a"}, "compare", {"b"}, "compare"), "differ")

    def test_each_case_has_its_own_neutral_class(self):
        self.assertEqual(f.classify({"a"}, "recommended", {"a"}, "recommended"), "same_picks_both_recommended")
        self.assertEqual(f.classify({"a"}, "compare", {"a"}, "compare"), "same_picks_both_compare")
        self.assertEqual(f.classify({"a"}, "recommended", {"a"}, "compare"), "same_picks_split_status")
        self.assertEqual(f.classify({"a", "b"}, "recommended", {"a"}, "recommended"), "some_picks_shared")
        self.assertEqual(f.classify({"a"}, "recommended", {"b"}, "recommended"), "no_picks_shared")
        for name in ("same_picks_both_recommended", "same_picks_both_compare", "same_picks_split_status",
                     "some_picks_shared", "no_picks_shared"):
            self.assertIn(name, f.CLASSES)

    def test_extensions_are_reported_only_where_they_change_a_row(self):
        self.assertEqual(f.extensions_applied([pick("a", "o/a")], "recommended", [pick("a", "o/a")], "compare"),
                         ["equal_sets_unequal_statuses"])
        # Same matched key, different names as written: the packet matching made the sets equal.
        c = [pick("name:x", "X, primary", "name:x, primary")]
        g = [pick("name:x", "X", "name:x")]
        self.assertEqual(f.extensions_applied(c, "recommended", g, "compare"),
                         ["equal_sets_unequal_statuses", "packet_name_matching"])
        self.assertEqual(f.extensions_applied([pick("a", "o/a"), pick("b", "o/b")], "recommended",
                                              [pick("a", "o/a")], "compare"), [])


class FoldTests(unittest.TestCase):
    def test_the_same_picks_both_recommended_derive_no_comparison_set(self):
        c = [pick("a", "o/a"), pick("b", "o/b")]
        result = f.fold(c, {"a", "b"}, "recommended", ["o/a"], c, {"a", "b"}, "recommended")
        self.assertEqual(result, ("same_picks_both_recommended", ["o/a", "o/b"], [], [], []))

    def test_the_same_picks_both_compare_derive_the_arms_and_every_pick(self):
        c = [pick("a", "o/a")]
        result = f.fold(c, {"a"}, "compare", ["o/a (recommended)", "baseline"], c, {"a"}, "compare")
        # o/a is named by an arm through its full owner/name, so it is not added again.
        self.assertEqual(result, ("same_picks_both_compare", ["o/a"], [], [], ["o/a (recommended)", "baseline"]))

    def test_shared_picks_split_into_both_and_one_half_only(self):
        c = [pick("a", "o/a"), pick("b", "o/b")]
        g = [pick("a", "o/a"), pick("c", "o/c")]
        result = f.fold(c, {"a", "b"}, "recommended", [], g, {"a", "c"}, "recommended")
        self.assertEqual(result, ("some_picks_shared", ["o/a"], ["o/b"], ["o/c"], ["o/b", "o/c"]))

    def test_the_same_picks_with_split_statuses_add_nothing_to_the_arms(self):
        c = [pick("a", "o/a")]
        self.assertEqual(f.fold(c, {"a"}, "recommended", [], c, {"a"}, "compare"),
                         ("same_picks_split_status", ["o/a"], [], [], []))

    def test_no_shared_pick_derives_every_pick_of_both_halves(self):
        c = [pick("a", "o/a")]
        g = [pick("c", "x/c")]
        self.assertEqual(f.fold(c, {"a"}, "recommended", ["o/a arm"], g, {"c"}, "recommended"),
                         ("no_picks_shared", [], ["o/a"], ["x/c"], ["o/a", "x/c"]))

    def test_a_pick_sharing_only_a_repository_name_with_an_arm_is_kept(self):
        # Regression (finding 4 of the #595 review), on a synthetic arm: the earlier whole-word matcher read the arm
        # "trailofbits/skills (recommended)" as naming "mattpocock/skills", because both repositories are named
        # "skills". The collision was latent: the Claude half recorded no arms for instructions-skills, so the real
        # record never lost mattpocock/skills.
        self.assertFalse(f.mentioned("mattpocock/skills", ["trailofbits/skills"]))
        c = [pick("t", "trailofbits/skills")]
        g = [pick("t", "trailofbits/skills"), pick("m", "mattpocock/skills")]
        status, both, c_only, g_only, arms = f.fold(c, {"t"}, "recommended", ["trailofbits/skills (recommended)"],
                                                    g, {"t", "m"}, "compare")
        self.assertEqual((status, both, c_only, g_only), ("some_picks_shared", ["trailofbits/skills"], [],
                                                          ["mattpocock/skills"]))
        self.assertEqual(arms, ["trailofbits/skills (recommended)", "mattpocock/skills"])

    def test_an_arm_names_a_pick_by_its_full_owner_and_name_only(self):
        self.assertTrue(f.mentioned("trailofbits/skills", ["trailofbits/skills (recommended)"]))
        self.assertTrue(f.mentioned("openai/codex", ["see https://github.com/openai/codex."]))
        self.assertTrue(f.mentioned("Ubuntu 24.04.5 LTS (Canonical WSL image)",
                                    ["ubuntu 24.04.5 lts (canonical wsl image) fallback"]))
        self.assertFalse(f.mentioned("mksglu/context-mode", ["Context Mode (frozen control)"]))
        self.assertFalse(f.mentioned("anthropics/sandbox-runtime", ["sandbox-runtime (recommended)"]))
        self.assertFalse(f.mentioned("anthropics/claude-code", ["anthropics/claude-code-action"]))
        self.assertFalse(f.mentioned("rtk-ai/rtk", ["artkit baseline"]))
        self.assertFalse(f.mentioned("", ["anything"]))

    def test_an_arm_described_in_words_and_the_pick_it_describes_both_appear(self):
        # The cost of full-name matching, disclosed in the fields: one tool can appear twice (token-efficiency's shape).
        c = [pick("r", "rtk-ai/rtk"), pick("u", "ccusage/ccusage")]
        g = [pick("u", "ccusage/ccusage"), pick("m", "mksglu/context-mode")]
        c_arms = ["ccusage (measurement, selected)", "RTK", "Context Mode (frozen control)"]
        status, _, _, _, arms = f.fold(c, {"r", "u"}, "compare", c_arms, g, {"u", "m"}, "compare")
        self.assertEqual(status, "some_picks_shared")
        self.assertEqual(arms, c_arms + ["mksglu/context-mode", "rtk-ai/rtk"])


class BuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = f.build()
        cls.rows = {r["layer_id"]: r for r in cls.data["rows"]}
        cls.edition = json.loads((ROOT / f.EDITION).read_text(encoding="utf-8"))
        cls.texts = (json.dumps(cls.data, indent=2, ensure_ascii=False), f.render_md(cls.data))

    def test_every_edition_row_appears_once_in_order(self):
        self.assertEqual([r["layer_id"] for r in self.data["rows"]], [r["layer_id"] for r in self.edition["rows"]])

    def test_every_class_is_known_and_the_counts_add_up(self):
        for row in self.data["rows"]:
            self.assertIn(row["pick_sets"]["class"], f.CLASSES)
        self.assertEqual(sum(self.data["summary"]["class"].values()), len(self.data["rows"]))

    def test_rows_outside_the_blind_run_name_no_picks(self):
        for row in self.data["rows"]:
            if row["blind"] is None:
                expected = "owner_lane_run_pending" if row["catalog"] == "us-equities" else "no_blind_record"
                self.assertEqual(row["pick_sets"]["class"], expected, row["layer_id"])
                for field in ("named_by_both", "named_by_claude_only", "named_by_gpt_only", "fold_comparison_set"):
                    self.assertEqual(row["pick_sets"][field], [], (row["layer_id"], field))

    def test_named_by_both_and_by_one_half_partition_the_two_pick_sets(self):
        judged = 0
        for row in self.data["rows"]:
            if not row["cross_family"]:
                continue
            judged += 1
            candidates = f.packet_names(row["layer_id"])
            c = {f.pick_key(p, candidates) for p in row["blind"]["picks"]}
            g = {f.pick_key(p, candidates) for p in row["cross_family"]["picks"]}
            sets = row["pick_sets"]
            self.assertEqual(len(sets["named_by_both"]), len(c & g), row["layer_id"])
            self.assertEqual(len(sets["named_by_claude_only"]), len(c - g), row["layer_id"])
            self.assertEqual(len(sets["named_by_gpt_only"]), len(g - c), row["layer_id"])
        self.assertEqual(judged, 21)

    def test_the_two_extensions_are_reported_on_the_rows_they_change(self):
        self.assertEqual(self.data["summary"]["extensions_applied"], {
            "equal_sets_unequal_statuses": ["document-retrieval", "scheduling-supervision", "cross:wsl-distro"],
            "packet_name_matching": ["cross:wsl-distro"]})
        for layer in ("document-retrieval", "scheduling-supervision"):
            self.assertEqual((self.rows[layer]["agreement"], self.rows[layer]["agreement_as_written"]),
                             ("overlap", "unclassified"), layer)
        # Compared as written, the two halves' distribution names share nothing.
        self.assertEqual((self.rows["cross:wsl-distro"]["agreement"], self.rows["cross:wsl-distro"]["agreement_as_written"]),
                         ("overlap", "differ"))
        for row in self.data["rows"]:
            if row["cross_family"] and not row["extensions_applied"]:
                self.assertEqual(row["agreement_as_written"], row["agreement"], row["layer_id"])

    def test_the_agreement_rule_is_hashed(self):
        digest = hashlib.sha256((ROOT / f.AGREEMENT_RULE).read_bytes()).hexdigest()
        self.assertEqual(self.data["agreement_rule"]["sha256"], digest)
        self.assertEqual(self.data["inputs"][f.AGREEMENT_RULE], digest)
        self.assertEqual(set(self.data["agreement_rule"]["extensions"]), set(f.EXTENSIONS))

    def test_the_record_is_not_an_install_list_and_names_the_install_record(self):
        md = self.texts[1]
        self.assertTrue(md.splitlines()[2].startswith("**This is not an install list.**"))
        self.assertIn(f.INSTALL_RECORD["manifest"], md.split("\n\n")[1])
        self.assertIn("not an install list", self.data["scope"])
        self.assertNotIn(f.INSTALL_RECORD["manifest"], self.data["inputs"])
        self.assertIn("not the rule applied exactly as written", md)

    # Every install word the outputs may hold: the disclaimers, the pointers to the install record, the selection's
    # name in titles and file paths, and the edition's title of the distribution row. None states an install.
    INSTALL_WORDING_ALLOWED = (
        "clean-install",
        "install_record",
        "not an install list",
        "is an installed tool or a default",
        "not an install decision",
        "the install record is the definitive manifest",
        "nothing here installs, accepts or authorizes",
        "neither half installed or measured",
        "attaches install and comparison consequences",
        "every slot's install decision is the definitive manifest's",
        "leaves out the edition's note on what the new distribution installs",
        "first boot and install order",
    )

    def test_no_row_reads_as_installed_standing_or_a_challenger(self):
        for text in self.texts:
            for word in ("standing", "challenger", "install_command", "install_source", "two_family_pick",
                         "partial_comparison", "gate_ledger", "stage-2"):
                self.assertNotIn(word, text.lower(), word)
            rest = text.lower()
            for phrase in self.INSTALL_WORDING_ALLOWED:
                rest = rest.replace(phrase, "")
            left = [rest[max(0, m.start() - 60):m.end() + 60] for m in re.finditer("instal", rest)]
            self.assertEqual(left, [], "install wording outside the disclaimers")
        for row in self.data["rows"]:
            # No field of a row but the edition's title of the distribution row holds install wording.
            fields = json.dumps({k: v for k, v in row.items() if k != "title"}, ensure_ascii=False).lower()
            self.assertNotIn("instal", fields, row["layer_id"])
            for half in ("blind", "cross_family"):
                for p in (row[half] or {}).get("picks", []):
                    self.assertEqual(set(p), {"name", "repository", "upstream"}, row["layer_id"])

    def test_the_selection_of_record_is_quoted_without_the_editions_install_note(self):
        by_id = {r["layer_id"]: r for r in self.edition["rows"]}
        shortened = []
        for row in self.data["rows"]:
            winners = by_id[row["layer_id"]]["winners"]
            self.assertEqual([(w["name"], w["repository"]) for w in row["selection_of_record"]],
                             [(w.get("component_id") or w.get("name"), w.get("repository")) for w in winners])
            for entry, winner in zip(row["selection_of_record"], winners):
                if entry["pin"] == winner.get("pin"):
                    continue
                shortened.append((row["layer_id"], entry["name"]))
                self.assertEqual(winner["pin"].replace(f.EDITION_INSTALL_NOTE, ""), entry["pin"])
                self.assertTrue(entry["pin"].endswith(" (the 2026-09-22 verdict's baseline)"), entry["pin"])
        # Exactly the four pins that carry the note; a new install clause in the edition fails the wording test above.
        self.assertEqual(shortened, [("identity-provenance", "DVC"), ("data-quality-orchestration", "pandera"),
                                     ("evaluation-experiments", "Inspect AI"), ("evaluation-experiments", "MLflow")])

    def test_a_quoted_pin_leaves_out_only_the_editions_install_note(self):
        self.assertEqual(f.quoted_pin("3.67.1 (the 2026-09-22 verdict's baseline; the new distribution installs the "
                                      "current upstream release)"), "3.67.1 (the 2026-09-22 verdict's baseline)")
        for pin in ("0.119.0 (archive sha256 3fa2dc4b)", "985ef30 with documented dependency remediation",
                    "v0.2.1 at source commit b487f386 (the 2026-09-22 verdict's baseline)", "", None):
            self.assertEqual(f.quoted_pin(pin), pin)

    def test_picks_of_packet_candidates_carry_the_captured_upstream_facts(self):
        facts = f.load_facts()
        checked = 0
        for row in self.data["rows"]:
            for half in ("blind", "cross_family"):
                for p in (row[half] or {}).get("picks", []):
                    key = f.github_key(p["repository"])
                    if key in facts:
                        checked += 1
                        self.assertEqual(p["upstream"], facts[key], (row["layer_id"], key))
                    else:
                        self.assertIsNone(p["upstream"], (row["layer_id"], p["repository"]))
        self.assertGreater(checked, 0)


class TempRoot(unittest.TestCase):
    """A copy of the generator's real inputs and checked-in outputs, with ROOT pointed at it. The definitive manifest is
    deliberately not copied: --check must not depend on it."""

    FILES = (f.EDITION, f.SELECTION, f.CROSS_FAMILY, f.AGREEMENT_RULE, f.GRAND_LIST, f.OUT_JSON, f.OUT_MD)

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        for rel in self.FILES:
            (self.tmp / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(ROOT / rel, self.tmp / rel)
        for rel in (f.PACKETS, f.FACTS):
            shutil.copytree(ROOT / rel, self.tmp / rel)
        patch = mock.patch.object(f, "ROOT", self.tmp)
        patch.start()
        self.addCleanup(patch.stop)


class CrossFamilySyntheticTests(TempRoot):
    """A synthetic GPT-6.1 Sol record over the real Claude record: each case lands in its own class."""

    def setUp(self):
        super().setUp()
        selection = json.loads((ROOT / f.SELECTION).read_text(encoding="utf-8"))
        layers = []
        for row in selection["layers"]:
            picks = [dict(p) for p in row["selection"]]
            status = "compare" if row["status"] == "compare" else "recommended"
            if row["layer_id"] == "secrets-credentials":
                picks = [{"name": "gitleaks", "repository": "https://github.com/gitleaks/gitleaks"}]
            if row["layer_id"] == "web-research":
                picks = picks[:1] + [{"name": "Crawl4AI", "repository": "https://github.com/unclecode/crawl4ai"}]
            layers.append({"layer_id": row["layer_id"], "status": status, "critic_verdict": "upheld", "picks": picks})
        (self.tmp / f.CROSS_FAMILY).write_text(json.dumps({"family": "synthetic", "run": {}, "contamination_audit": {},
                                                           "layers": layers}))
        self.rows = {r["layer_id"]: r for r in f.build()["rows"]}

    def test_identical_recommendations(self):
        row = self.rows["native-clients"]
        self.assertEqual((row["agreement"], row["agreement_as_written"]), ("agree", "agree"))
        self.assertEqual(row["pick_sets"]["class"], "same_picks_both_recommended")
        self.assertEqual(row["pick_sets"]["named_by_both"], ["anthropics/claude-code", "openai/codex"])
        self.assertEqual(row["pick_sets"]["fold_comparison_set"], [])

    def test_disjoint_picks(self):
        row = self.rows["secrets-credentials"]
        self.assertEqual(row["agreement"], "differ")
        self.assertEqual(row["pick_sets"]["class"], "no_picks_shared")
        self.assertEqual(row["pick_sets"]["named_by_gpt_only"], ["gitleaks/gitleaks"])
        self.assertIn("betterleaks/betterleaks", row["pick_sets"]["named_by_claude_only"])
        self.assertIn("gitleaks/gitleaks", row["pick_sets"]["fold_comparison_set"])

    def test_partly_shared_picks(self):
        row = self.rows["web-research"]
        self.assertEqual(row["agreement"], "overlap")
        self.assertEqual(row["pick_sets"]["class"], "some_picks_shared")
        self.assertEqual(row["pick_sets"]["named_by_both"], ["adbar/trafilatura"])
        self.assertEqual(row["pick_sets"]["named_by_claude_only"], ["microsoft/playwright-cli"])
        self.assertEqual(row["pick_sets"]["named_by_gpt_only"], ["unclecode/crawl4ai"])

    def test_the_same_picks_both_asked_to_compare(self):
        for layer in ("durable-memory", "semantic-rag", "token-efficiency", "isolation", "hosting-services"):
            self.assertEqual(self.rows[layer]["pick_sets"]["class"], "same_picks_both_compare", layer)

    def test_rows_outside_the_blind_run_are_untouched(self):
        self.assertEqual(self.rows["cross:runtime-workers"]["pick_sets"]["class"], "no_blind_record")
        self.assertEqual(self.rows["backtesting-engine"]["pick_sets"]["class"], "owner_lane_run_pending")

    def test_without_a_gpt_record_every_judged_layer_is_pending(self):
        (self.tmp / f.CROSS_FAMILY).unlink()
        data = f.build()
        self.assertEqual(data["cross_family"], {"status": "not_run"})
        self.assertEqual(data["summary"]["class"]["pending_cross_family"], 21)


class CheckTests(TempRoot):
    """--check run against real files in a temporary root."""

    def test_the_faithful_copy_passes_without_the_install_record(self):
        self.assertFalse((self.tmp / f.INSTALL_RECORD["manifest"]).exists())
        code, out, err = run_main(["--check"])
        self.assertEqual(code, 0, err)
        result = json.loads(out)
        # A grand-list move alone is drift, not staleness, so the drift flag is not asserted here.
        self.assertEqual((result["status"], result["rows"]), ("passed", 37))

    def test_a_stale_json_output_fails(self):
        path = self.tmp / f.OUT_JSON
        data = json.loads(path.read_text(encoding="utf-8"))
        data["rows"][0]["pick_sets"]["class"] = "no_picks_shared"
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        code, _, err = run_main(["--check"])
        self.assertEqual(code, 1)
        self.assertIn(f.OUT_JSON, err)
        self.assertNotIn(f.OUT_MD, err)

    def test_a_stale_markdown_output_fails(self):
        with (self.tmp / f.OUT_MD).open("a", encoding="utf-8") as handle:
            handle.write("hand edit\n")
        code, _, err = run_main(["--check"])
        self.assertEqual(code, 1)
        self.assertIn(f.OUT_MD, err)

    def test_a_changed_agreement_rule_fails_until_the_outputs_are_regenerated(self):
        with (self.tmp / f.AGREEMENT_RULE).open("a", encoding="utf-8") as handle:
            handle.write("An eighth line.\n")
        code, _, err = run_main(["--check"])
        self.assertEqual(code, 1)
        self.assertIn(f.OUT_JSON, err)
        with mock.patch.object(f.host_receipts, "register_file") as register:
            self.assertEqual(run_main(["--write"])[0], 0)
        self.assertEqual(register.call_count, 2)
        written = json.loads((self.tmp / f.OUT_JSON).read_text(encoding="utf-8"))
        digest = hashlib.sha256((self.tmp / f.AGREEMENT_RULE).read_bytes()).hexdigest()
        self.assertEqual(written["agreement_rule"]["sha256"], digest)
        self.assertEqual(run_main(["--check"])[0], 0)

    def test_a_grand_list_move_alone_is_reported_as_drift(self):
        path = self.tmp / f.GRAND_LIST
        grand = json.loads(path.read_text(encoding="utf-8"))
        grand["layers"][0]["open_gaps"] = -1
        path.write_text(json.dumps(grand), encoding="utf-8")
        code, out, err = run_main(["--check"])
        self.assertEqual(code, 0, err)
        self.assertTrue(json.loads(out)["grand_list_drift"])

    def test_a_missing_output_fails(self):
        (self.tmp / f.OUT_MD).unlink()
        self.assertEqual(run_main(["--check"])[0], 1)


class CheckedInTests(unittest.TestCase):
    def test_checked_in_outputs_are_fresh(self):
        code, out, err = run_main(["--check"])
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out)["status"], "passed")

    def test_generated_output_passes_the_private_content_guard(self):
        data = f.build()
        for text in (json.dumps(data, indent=2, ensure_ascii=False), f.render_md(data)):
            for label, pattern in f.PRIVATE_CONTENT:
                self.assertIsNone(pattern.search(text), label)

    def test_the_markdown_table_cells_hold_no_unescaped_pipe(self):
        md = f.render_md(f.build())
        for line in md.splitlines():
            if line.startswith("| ") and not line.startswith("| ---"):
                cells = re.split(r"(?<!\\)\|", line.strip())[1:-1]
                self.assertIn(len(cells), (2, 9), line[:80])


if __name__ == "__main__":
    unittest.main()
