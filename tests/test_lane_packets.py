"""Synthetic-fixture tests for tools/sota-convergence/lane_packets.py (PR-5,
"packets" unit).

Fixture root: tests/fixtures/lane-packets/ -- two layers (one foundation, one
us-equities), each with one candidate that matches a sota-convergence
manifest component/entry by GitHub slug and one that does not, plus a
foundation decision touching the matched foundation component and an unclaimed
manifest component in the foundation layer. Modules are loaded by file path
(tools/sota-convergence is not a dotted-import package name), matching the
pattern already used by test_layer_verdicts.py.
"""
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL_DIR = ROOT / "tools" / "sota-convergence"
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "lane-packets"


def load_module(name, filename):
    path = TOOL_DIR / filename
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


lane_packets = load_module("lane_packets", "lane_packets.py")
# LeakDetected is raised from build_manifest.py; lane_packets.py imports it
# via its own sys.path-based "from build_manifest import ..." (see its
# module-level import comment) which registers a *separate* build_manifest
# module object in sys.modules than one this test might load independently
# by file path -- pull the actual class off the function the module used, as
# test_layer_verdicts.py already does for build_verdicts.py.
LeakDetected = lane_packets.assert_no_leak.__globals__["LeakDetected"]


# Seeded order of the manifest-mode fixture (seed 20260922, layer-b); newcomers have no component id.
EXPECTED_SEEDED_COMPONENT_ORDER = [None, None, 'data-two', 'data-one', 'data-three']


class LanePacketsFixture(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "repo"
        shutil.copytree(FIXTURE_ROOT, self.root)
        self.out = Path(temporary.name) / "work"

    def read(self, relative):
        return json.loads((self.root / relative).read_text(encoding="utf-8"))

    def write(self, relative, value):
        target = self.root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(value), encoding="utf-8")

    def build(self, out=None, **kwargs):
        return lane_packets.build_all_packets(self.root, catalogs=["foundation", "us-equities"],
                                               seed=lane_packets.DEFAULT_SEED,
                                               checked_at=lane_packets.DEFAULT_CHECKED_AT, **kwargs)

    def packet(self, catalog, layer_id, packets=None):
        packets = packets if packets is not None else self.build()
        return json.loads(packets[lane_packets.packet_filename(catalog, layer_id)])


class BuildAllPacketsTests(LanePacketsFixture):
    def test_two_layers_produce_two_packets_with_expected_filenames(self):
        packets = self.build()
        self.assertEqual(set(packets), {"foundation__layer-a.json", "us-equities__layer-b.json"})

    def test_matched_candidate_carries_manifest_fields_and_recipe_map_ref(self):
        foundation = self.packet("foundation", "layer-a")
        widget_one = next(c for c in foundation["candidates"] if c["name"] == "Widget One")
        self.assertEqual(widget_one["component_id"], "widget-one")
        self.assertEqual(widget_one["pin"], "1.0.0")
        self.assertTrue(widget_one["pin_behind_upstream"])
        self.assertEqual(widget_one["review_status"], "confirmed_default")
        self.assertEqual(widget_one["upstream"]["latest"], "1.1.0")
        self.assertEqual(widget_one["recipe_ref"], "recipes/widget-one.md")  # from recipe_map, not evidence_refs

    def test_recipe_ref_falls_back_to_an_existing_evidence_ref_when_absent_from_recipe_map(self):
        equities = self.packet("us-equities", "layer-b")
        data_one = next(c for c in equities["candidates"] if c["name"] == "Data One")
        self.assertEqual(data_one["component_id"], "data-one")
        self.assertNotIn("data-one", self.read("adoption/manifest.json")["recipe_map"])
        self.assertEqual(data_one["recipe_ref"], "docs/evidence.md")

    def test_candidate_without_a_repository_never_matches(self):
        foundation = self.packet("foundation", "layer-a")
        widget_local = next(c for c in foundation["candidates"] if c["name"] == "Widget Local")
        self.assertIsNone(widget_local["repository"])
        self.assertIsNone(widget_local["component_id"])
        self.assertIsNone(widget_local["pin"])
        self.assertIsNone(widget_local["recipe_ref"])

    def test_candidate_with_an_unindexed_repository_does_not_match(self):
        equities = self.packet("us-equities", "layer-b")
        unmatched = next(c for c in equities["candidates"] if c["name"] == "Data Unmatched")
        self.assertIsNotNone(unmatched["repository"])
        self.assertIsNone(unmatched["component_id"])
        self.assertIsNone(unmatched["pin"])
        self.assertIsNone(unmatched["review_status"])

    def test_adopted_is_derived_from_selected_or_conditional_disposition_only(self):
        foundation = self.packet("foundation", "layer-a")
        equities = self.packet("us-equities", "layer-b")
        by_name = {c["name"]: c["adopted"] for c in foundation["candidates"] + equities["candidates"]}
        self.assertTrue(by_name["Widget One"])       # disposition: selected
        self.assertTrue(by_name["Widget Local"])     # disposition: conditional
        self.assertTrue(by_name["Data One"])         # disposition: selected
        self.assertFalse(by_name["Data Unmatched"])  # disposition: observed_failure

    def test_sota_components_not_in_candidates_lists_the_unclaimed_manifest_component(self):
        foundation = self.packet("foundation", "layer-a")
        self.assertEqual([c["id"] for c in foundation["sota_components_not_in_candidates"]],
                          ["widget-two-unclaimed"])
        equities = self.packet("us-equities", "layer-b")
        self.assertEqual(equities["sota_components_not_in_candidates"], [])

    def test_foundation_decisions_attach_only_to_the_matched_foundation_component(self):
        foundation = self.packet("foundation", "layer-a")
        widget_one = next(c for c in foundation["candidates"] if c["name"] == "Widget One")
        widget_local = next(c for c in foundation["candidates"] if c["name"] == "Widget Local")
        self.assertEqual([d["id"] for d in widget_one["decisions"]], ["decision-1"])
        self.assertEqual(set(widget_one["decisions"][0]),
                          set(lane_packets.DECISION_FIELDS))
        self.assertEqual(widget_local["decisions"], [])

    def test_us_equities_candidates_never_carry_decisions(self):
        equities = self.packet("us-equities", "layer-b")
        for candidate in equities["candidates"]:
            self.assertEqual(candidate["decisions"], [])

    def test_withheld_fields_never_appear_in_a_packet(self):
        for packet in (self.packet("foundation", "layer-a"), self.packet("us-equities", "layer-b")):
            self.assertNotIn("current_choice", packet)
            self.assertNotIn("decision", packet)
            self.assertNotIn("rationale", packet)
            self.assertEqual(packet["withheld"],
                              ["current_choice", "decision", "rationale",
                               "candidates[].disposition", "candidates[].rationale"])
            for candidate in packet["candidates"]:
                self.assertNotIn("disposition", candidate)
                self.assertNotIn("rationale", candidate)

    def test_enums_are_the_sorted_landscape_constants(self):
        packet = self.packet("foundation", "layer-a")
        self.assertEqual(packet["enums"]["evidence_class"], sorted(lane_packets.WINNER_EVIDENCE_CLASSES))
        self.assertEqual(packet["enums"]["disposition"], sorted(lane_packets.DISPOSITIONS))

    def test_rules_are_the_five_lane_prompt_rules(self):
        packet = self.packet("foundation", "layer-a")
        self.assertEqual(len(packet["rules"]), 5)
        self.assertEqual(packet["rules"], lane_packets.load_rules())
        self.assertIn("Judge from retained evidence.", packet["rules"][0])

    def test_group_is_present_for_us_equities_and_null_for_foundation(self):
        self.assertIsNone(self.packet("foundation", "layer-a")["group"])
        self.assertEqual(self.packet("us-equities", "layer-b")["group"], "data-research")


class LoadRulesFailureTests(unittest.TestCase):
    """load_rules() is the guard that keeps a packet's rules field and
    lane-prompt.md from drifting; its two failure paths were previously
    untested."""

    def test_missing_rules_section_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            prompt = Path(tmp) / "lane-prompt.md"
            prompt.write_text("Some prompt text with no rules heading.\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "no 'Rules' section"):
                lane_packets.load_rules(prompt)

    def test_wrong_rule_count_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            prompt = Path(tmp) / "lane-prompt.md"
            prompt.write_text("Intro text.\n\nRules\n1. One.\n2. Two.\n3. Three.\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "must have exactly five numbered rules, found 3"):
                lane_packets.load_rules(prompt)


class ShuffleTests(LanePacketsFixture):
    def test_shuffle_is_seeded_and_stable_across_repeated_builds(self):
        first = self.packet("foundation", "layer-a")
        second = self.packet("foundation", "layer-a")
        self.assertEqual([c["name"] for c in first["candidates"]], [c["name"] for c in second["candidates"]])

    def test_shuffle_actually_reorders_the_original_candidate_list(self):
        packet = self.packet("foundation", "layer-a")
        original_order = [c["name"] for c in self.read("catalogs/landscape/foundation.json")["layers"][0]["candidates"]]
        shuffled_order = [c["name"] for c in packet["candidates"]]
        self.assertEqual(set(shuffled_order), set(original_order))
        self.assertNotEqual(shuffled_order, original_order)  # true for DEFAULT_SEED against this fixture

    def test_a_different_seed_can_produce_a_different_order(self):
        default_names = [c["name"] for c in self.packet("foundation", "layer-a")["candidates"]]
        alternate_packets = lane_packets.build_all_packets(
            self.root, catalogs=["foundation"], seed="a-different-seed",
            checked_at=lane_packets.DEFAULT_CHECKED_AT)
        alternate = json.loads(alternate_packets["foundation__layer-a.json"])
        alternate_names = [c["name"] for c in alternate["candidates"]]
        self.assertEqual(set(alternate_names), set(default_names))
        self.assertNotEqual(alternate_names, default_names)

    def test_keys_are_assigned_positionally_after_the_shuffle(self):
        packet = self.packet("foundation", "layer-a")
        self.assertEqual([c["key"] for c in packet["candidates"]],
                          [f"c{i}" for i in range(1, len(packet["candidates"]) + 1)])


class Sha256sumsTests(LanePacketsFixture):
    def test_sha256sums_lines_match_the_written_packet_files(self):
        exit_code = lane_packets.main(["--root", str(self.root), "--out", str(self.out)])
        self.assertEqual(exit_code, 0)
        packets_dir = self.out / "packets"
        sums = (packets_dir / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(sums), 2)
        seen = set()
        for line in sums:
            digest, name = line.split("  ", 1)
            self.assertTrue(len(digest) == 64 and all(c in "0123456789abcdef" for c in digest))
            actual = hashlib.sha256((packets_dir / name).read_bytes()).hexdigest()
            self.assertEqual(digest, actual)
            seen.add(name)
        self.assertEqual(seen, {"foundation__layer-a.json", "us-equities__layer-b.json"})


class DeterminismTests(LanePacketsFixture):
    def test_output_is_deterministic_across_two_separate_runs(self):
        out_one = self.out / "one"
        out_two = self.out / "two"
        self.assertEqual(lane_packets.main(["--root", str(self.root), "--out", str(out_one)]), 0)
        self.assertEqual(lane_packets.main(["--root", str(self.root), "--out", str(out_two)]), 0)
        for name in ("foundation__layer-a.json", "us-equities__layer-b.json", "SHA256SUMS"):
            self.assertEqual((out_one / "packets" / name).read_bytes(), (out_two / "packets" / name).read_bytes())

    def test_catalog_filter_restricts_the_written_packets(self):
        exit_code = lane_packets.main(["--root", str(self.root), "--out", str(self.out), "--catalog", "foundation"])
        self.assertEqual(exit_code, 0)
        names = {path.name for path in (self.out / "packets").glob("*.json")}
        self.assertEqual(names, {"foundation__layer-a.json"})


class SotaLayerIndexIsolationTests(unittest.TestCase):
    """Regression for a fix-round finding: sota_layer_index() used to key
    solely by layer_id, so a layer id present in both the manifest's
    foundation[] and trading[] taxonomies silently let the trading entry
    (indexed second) overwrite the foundation one. The index is now keyed by
    (catalog, layer_id)."""

    def test_same_layer_id_in_both_taxonomies_stays_isolated(self):
        sota_doc = {
            "foundation": [{"layer": "shared", "title": "Shared", "components": [
                {"id": "foundation-comp", "repository": "https://github.com/acme/foundation-comp",
                 "pin": "1.0.0", "upstream": None, "pin_behind_upstream": False,
                 "review_status": "confirmed_default"},
            ]}],
            "trading": [{"layer": "shared", "entries": [
                {"id": "trading-comp", "repository": "https://github.com/acme/trading-comp",
                 "pin": "2.0.0", "upstream": None, "pin_behind_upstream": False,
                 "review_status": "confirmed_default"},
            ]}],
        }
        index = lane_packets.sota_layer_index(sota_doc)
        self.assertEqual([c["id"] for c in index[("foundation", "shared")]], ["foundation-comp"])
        self.assertEqual([c["id"] for c in index[("us-equities", "shared")]], ["trading-comp"])


class CrossCatalogIsolationTests(LanePacketsFixture):
    def test_a_colliding_layer_id_in_the_other_catalog_never_contaminates_this_catalogs_packet(self):
        # Add a trading[] entry under the same layer id ("layer-a") as the
        # fixture's foundation layer, with a component id that must never
        # reach the foundation packet.
        manifest = self.read("catalogs/sota-convergence/manifest-20260922.json")
        manifest["trading"].append({
            "layer": "layer-a",
            "entries": [{
                "id": "trading-imposter", "repository": "https://github.com/acme/trading-imposter",
                "pin": "9.9.9", "upstream": None, "pin_behind_upstream": False,
                "review_status": "confirmed_default",
            }],
        })
        self.write("catalogs/sota-convergence/manifest-20260922.json", manifest)
        foundation = self.packet("foundation", "layer-a")
        unmatched_ids = {c["id"] for c in foundation["sota_components_not_in_candidates"]}
        matched_ids = {c["component_id"] for c in foundation["candidates"] if c["component_id"]}
        self.assertNotIn("trading-imposter", unmatched_ids | matched_ids)
        self.assertEqual(unmatched_ids, {"widget-two-unclaimed"})


class StdoutRedactionTests(LanePacketsFixture):
    def test_out_dir_host_path_marker_is_redacted_from_the_printed_status(self):
        # Regression for a fix-round finding: main() printed the resolved
        # --out path verbatim, so a host-path marker in --out reached stdout
        # even though written packets are always sanitized/leak-checked.
        # "/home/" needs only to appear as a substring of the resolved --out
        # path to exercise the redaction -- no real home directory is used.
        out = self.out / "home" / "example"
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            exit_code = lane_packets.main(["--root", str(self.root), "--out", str(out)])
        self.assertEqual(exit_code, 0)
        printed = json.loads(buffer.getvalue())
        self.assertNotIn("/home/", printed["out_dir"])
        self.assertIn("<host-path>", printed["out_dir"])


class LeakRefusalTests(LanePacketsFixture):
    def test_host_path_is_sanitized_rather_than_leaking(self):
        # sanitize_value redacts "/home/..." to "<host-path>" *before* the
        # leak check runs (build_manifest.py's contract), so a host path
        # alone does not abort the write -- it must simply never survive
        # into the written packet.
        with_path = self.read("catalogs/landscape/foundation.json")
        with_path["layers"][0]["limitations"] = ['Reviewed at "/home/example/code/x.json"']
        self.write("catalogs/landscape/foundation.json", with_path)
        exit_code = lane_packets.main(["--root", str(self.root), "--out", str(self.out)])
        self.assertEqual(exit_code, 0)
        packet_text = (self.out / "packets" / "foundation__layer-a.json").read_text(encoding="utf-8")
        self.assertNotIn("/home/", packet_text)
        self.assertIn("<host-path>", packet_text)

    def test_secret_marker_leak_aborts_the_run_before_any_file_is_written(self):
        leaking = self.read("catalogs/landscape/us-equities.json")
        leaking["layers"][0]["limitations"] = ["Selected using the APCA-prefixed paper credential name"]
        self.write("catalogs/landscape/us-equities.json", leaking)
        with self.assertRaises(LeakDetected):
            lane_packets.main(["--root", str(self.root), "--out", str(self.out)])
        self.assertFalse((self.out / "packets").exists())

    def test_a_leak_in_one_layer_still_blocks_the_unaffected_layer(self):
        # All-or-nothing write discipline (matching build_verdicts.py): a leak
        # anywhere in the run must not let any other packet reach disk either.
        leaking = self.read("catalogs/foundation/decisions.json")
        leaking["decisions"][0]["next_gap"] = "Leak: the APCA-prefixed credential name reached prose"
        self.write("catalogs/foundation/decisions.json", leaking)
        with self.assertRaises(LeakDetected):
            lane_packets.main(["--root", str(self.root), "--out", str(self.out)])
        self.assertFalse((self.out / "packets" / "us-equities__layer-b.json").exists())


class SchemaAndPromptConsistencyTests(unittest.TestCase):
    def test_lane_return_schema_enums_match_scripts_landscape(self):
        schema = json.loads((TOOL_DIR / "lane-return.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(schema["properties"]["winner_evidence_class"]["enum"],
                          sorted(lane_packets.WINNER_EVIDENCE_CLASSES))
        self.assertEqual(
            schema["properties"]["alternatives"]["items"]["properties"]["disposition"]["enum"],
            sorted(lane_packets.DISPOSITIONS))
        self.assertEqual(
            schema["properties"]["alternatives"]["items"]["properties"]["evidence_class"]["enum"],
            sorted(lane_packets.WINNER_EVIDENCE_CLASSES))

    def test_lane_return_schema_is_a_valid_draft_2020_12_schema(self):
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema is not installed")
        schema = json.loads((TOOL_DIR / "lane-return.schema.json").read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator.check_schema(schema)

    def test_lane_return_schema_validates_a_well_formed_instance_and_rejects_bad_ones(self):
        # check_schema() above only proves the schema document is itself
        # valid Draft 2020-12; this exercises it against actual instances,
        # matching the rules the contract encodes (winner_keys 1-3,
        # why_selected >= 60 chars, additionalProperties: false).
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema is not installed")
        schema = json.loads((TOOL_DIR / "lane-return.schema.json").read_text(encoding="utf-8"))
        validator = jsonschema.Draft202012Validator(schema)
        good = {
            "schema_version": 1, "lane": "claude", "catalog": "foundation", "layer_id": "layer-a",
            "packet_sha256": "a" * 64, "model": {"name": "claude-test", "effort": "high"},
            "winner_keys": ["c1"], "why_selected": "x" * 60,
            "winner_evidence_class": "source_review", "winner_evidence_refs": ["docs/evidence.md"],
            "alternatives": [{
                "key": "c2", "name": "Widget Two", "repository": "https://github.com/acme/widget-two",
                "disposition": "unqualified", "why_not_default": "y" * 30,
                "evidence_class": "source_review", "evidence_refs": [],
            }],
            "challenger_preferred": None,
            "overturn_when": "python3 tests/x.py",
            "overturn_protocol": {"fixture_paths": [], "metric": "", "arms": []},
            "open_gaps": [], "sources_read": ["docs/evidence.md"], "limits": [],
        }
        self.assertEqual(list(validator.iter_errors(good)), [])

        too_many_winners = dict(good, winner_keys=["c1", "c2", "c3", "c4"])
        messages = [error.message for error in validator.iter_errors(too_many_winners)]
        self.assertTrue(any("too long" in message for message in messages), messages)

        short_why = dict(good, why_selected="too short")
        messages = [error.message for error in validator.iter_errors(short_why)]
        self.assertTrue(any("too short" in message for message in messages), messages)

        extra_key = dict(good, unexpected="nope")
        messages = [error.message for error in validator.iter_errors(extra_key)]
        self.assertTrue(any("Additional properties" in message for message in messages), messages)

    def test_lane_prompt_has_the_expected_placeholders(self):
        text = (TOOL_DIR / "lane-prompt.md").read_text(encoding="utf-8")
        for placeholder in ("{PACKET_PATH}", "{REPO_ROOT}", "{LANE}"):
            self.assertIn(placeholder, text)
        formatted = text.format(PACKET_PATH="/x/packet.json", REPO_ROOT="/x", LANE="claude")
        self.assertIn("claude lane", formatted)



class ManifestTradingCandidatesTests(LanePacketsFixture):
    """--trading-candidates manifest builds us-equities candidates from the sota manifest's
    own layer entries, with evidence from their domain catalog cards."""

    def setUp(self):
        super().setUp()
        manifest = self.read("catalogs/sota-convergence/manifest-20260922.json")
        layer = manifest["trading"][0]
        layer["entries"].append({"id": "data-two", "repository": "https://github.com/acme/data-one",
                                 "pin": "3.1.0", "upstream": None, "pin_behind_upstream": False,
                                 "review_status": "not_individually_reviewed"})
        layer["entries"].append({"id": "data-three", "repository": "https://github.com/acme/data-three",
                                 "pin": "1.0.0", "upstream": None, "pin_behind_upstream": True,
                                 "review_status": "confirmed_conditional"})
        layer["candidates"] = [{"repository": "https://github.com/acme/newcomer",
                                "demonstrated_gap": "names the gap but demonstrates nothing"},
                               {"repository": "https://github.com/acme/data-three",
                                "demonstrated_gap": "already an entry, must not be added twice"}]
        layer["alternatives_keep_but_compare"] = [
            {"repository": "https://github.com/acme/newcomer",
             "comparison_that_would_overturn": "listed in both newcomer lists"},
            {"repository": "https://github.com/acme/kbc-only",
             "comparison_that_would_overturn": "an executed comparison would overturn it"}]
        manifest["taxonomy"] = {"layer-b": ["market-data", "reference"]}
        self.write("catalogs/sota-convergence/manifest-20260922.json", manifest)
        self.write("docs/card-evidence.md", "card evidence")
        cards = {"entries": [
            {"id": "data-one", "repository": "https://github.com/acme/data-one", "decision": "default",
             "evidence_level": "native_proven", "evidence_refs": ["docs/card-evidence.md"],
             "role": "Reads the market data", "limitations": ["Same host only"],
             "rationale": "INCUMBENT RATIONALE MUST NOT APPEAR"},
            {"id": "data-two", "repository": "https://github.com/acme/data-one", "decision": "rejected",
             "evidence_level": "source_review", "evidence_refs": [], "role": "Second card, same repository",
             "limitations": [], "rationale": "INCUMBENT RATIONALE MUST NOT APPEAR"},
            {"id": "data-three", "repository": "https://github.com/acme/data-three", "decision": "conditional",
             "evidence_level": "local_integration", "evidence_refs": ["docs/card-evidence.md"],
             "role": "Third card", "limitations": ["Local only"], "rationale": "INCUMBENT RATIONALE MUST NOT APPEAR"},
        ]}
        for relative in lane_packets.TRADING_CARD_FILES:
            self.write(relative, {"entries": []})
        self.write(lane_packets.TRADING_CARD_FILES[0], cards)

    def manifest_packet(self):
        return self.packet("us-equities", "layer-b", self.build(trading_candidates="manifest"))

    def test_candidates_are_the_manifest_layer_entries_plus_newcomers(self):
        packet = self.manifest_packet()
        by_component = {c["component_id"]: c for c in packet["candidates"]}
        self.assertEqual(set(by_component), {"data-one", "data-two", "data-three", None})
        self.assertTrue(by_component["data-one"]["adopted"])
        self.assertFalse(by_component["data-two"]["adopted"], "a card decision outside default/conditional is not adopted")
        self.assertEqual(by_component["data-one"]["evidence_refs"], ["docs/card-evidence.md"])
        self.assertEqual(by_component["data-one"]["pin"], "3.0.0")
        self.assertEqual(by_component["data-two"]["pin"], "3.1.0", "two entries sharing a repository keep their own ids and pins")
        others = [c for c in packet["candidates"] if c["component_id"] is None]
        self.assertEqual(sorted(c["repository"] for c in others),
                         ["https://github.com/acme/kbc-only", "https://github.com/acme/newcomer"],
                         "a repository already an entry is not added, and one in both lists appears once")
        self.assertTrue(all(not c["adopted"] and c.get("newcomer") is True for c in others))
        notes = {c["repository"]: c["note"] for c in others}
        self.assertEqual(notes["https://github.com/acme/newcomer"], "names the gap but demonstrates nothing")
        self.assertEqual(notes["https://github.com/acme/kbc-only"], "an executed comparison would overturn it")
        self.assertTrue(by_component["data-three"]["adopted"], "a conditional card decision is adopted")
        self.assertEqual(by_component["data-three"]["role"], "Third card")
        self.assertEqual(by_component["data-three"]["card_limitations"], ["Local only"])
        self.assertEqual(packet["layer_scope_terms"], ["market-data", "reference"])
        self.assertIn("layer_scope_terms", packet["requirement_note"])
        self.assertEqual(packet["candidate_source"], lane_packets.MANIFEST_CANDIDATE_SOURCE)

    def test_card_rationale_and_decision_are_withheld(self):
        packet = self.manifest_packet()
        text = json.dumps(packet)
        self.assertNotIn("INCUMBENT RATIONALE MUST NOT APPEAR", text)
        self.assertNotIn('"decision"', json.dumps(packet["candidates"]))
        self.assertIn("candidates[].card_rationale", packet["withheld"])

    def test_foundation_packets_and_ledger_mode_are_unchanged(self):
        ledger = self.build()
        manifest = self.build(trading_candidates="manifest")
        self.assertEqual(ledger["foundation__layer-a.json"], manifest["foundation__layer-a.json"])
        self.assertNotIn("candidate_source", json.loads(ledger["us-equities__layer-b.json"]))

    def test_review_labels_are_not_carried(self):
        packet = self.manifest_packet()
        self.assertTrue(all(c["review_status"] is None for c in packet["candidates"]),
                        "every manifest review label correlates with the withheld decision")
        text = json.dumps(packet)
        for label in ("confirmed_", "not_individually_reviewed", "unmaintained_signal", "keep_but_compare"):
            self.assertNotIn(label, text)
        by_component = {c["component_id"]: c for c in packet["candidates"]}
        self.assertTrue(by_component["data-three"]["pin_behind_upstream"], "the pin-behind flag stays as its own field")

    def test_keys_follow_the_seeded_shuffle(self):
        def build(seed):
            return json.loads(lane_packets.build_all_packets(
                self.root, catalogs=["us-equities"], seed=seed, checked_at=lane_packets.DEFAULT_CHECKED_AT,
                trading_candidates="manifest")["us-equities__layer-b.json"])
        manifest = self.read("catalogs/sota-convergence/manifest-20260922.json")
        layer = manifest["trading"][0]
        cards = {e["id"]: e for e in self.read(lane_packets.TRADING_CARD_FILES[0])["entries"]}
        unshuffled = lane_packets.manifest_layer_candidates(layer, cards, {}, {}, self.root)
        expected = list(unshuffled)
        lane_packets.make_rng(lane_packets.DEFAULT_SEED, "us-equities", "layer-b").shuffle(expected)
        packet = build(lane_packets.DEFAULT_SEED)
        identity = lambda c: (c["component_id"], c["repository"])
        self.assertEqual([identity(c) for c in packet["candidates"]], [identity(c) for c in expected])
        # A literal sequence pins the seed derivation itself, not only agreement with the helper.
        self.assertEqual([c["component_id"] for c in packet["candidates"]], EXPECTED_SEEDED_COMPONENT_ORDER)
        self.assertEqual([c["key"] for c in packet["candidates"]],
                         [f"c{index}" for index in range(1, len(expected) + 1)])
        orders = {tuple(c["repository"] for c in build(seed)["candidates"]) for seed in ("s1", "s2", "s3", "s4")}
        self.assertGreater(len(orders), 1, "different seeds must be able to change the order")

    def test_a_manifest_entry_without_a_card_fails_loudly(self):
        manifest = self.read("catalogs/sota-convergence/manifest-20260922.json")
        manifest["trading"][0]["entries"].append({"id": "no-card", "repository": "https://github.com/acme/no-card"})
        self.write("catalogs/sota-convergence/manifest-20260922.json", manifest)
        with self.assertRaisesRegex(ValueError, "has no domain catalog card"):
            self.build(trading_candidates="manifest")

    def test_ledger_mode_packets_carry_no_manifest_mode_fields(self):
        packet = self.packet("us-equities", "layer-b")
        for key in ("candidate_source", "layer_scope_terms", "requirement_note"):
            self.assertNotIn(key, packet)
        self.assertTrue(all("card_limitations" not in c and "role" not in c for c in packet["candidates"]))

    def test_manifest_mode_is_deterministic(self):
        self.assertEqual(self.build(trading_candidates="manifest"), self.build(trading_candidates="manifest"))


class WithholdLabelsTests(LanePacketsFixture):
    def test_withheld_packets_carry_no_decision_bearing_label(self):
        packets = self.build(withhold=True)
        for name, text in packets.items():
            packet = json.loads(text)
            for candidate in packet["candidates"]:
                self.assertIsNone(candidate["review_status"], name)
                for decision in candidate["decisions"]:
                    self.assertNotIn("selection", decision)
                    self.assertNotIn("review_status", decision)
            self.assertIn("candidates[].decisions[].selection", packet["withheld"])
        text = "".join(packets.values())
        self.assertNotIn("confirmed_default", text)

    def test_evidence_prose_of_decisions_is_kept(self):
        plain = json.loads(self.build()["foundation__layer-a.json"])
        withheld = json.loads(self.build(withhold=True)["foundation__layer-a.json"])
        for before, after in zip(plain["candidates"], withheld["candidates"]):
            for d_before, d_after in zip(before["decisions"], after["decisions"]):
                for key in ("id", "capability", "evidence_scope", "limitations", "next_gap"):
                    self.assertEqual(d_before.get(key), d_after.get(key))

    def test_default_mode_is_unchanged(self):
        self.assertEqual(self.build(), self.build(withhold=False))
        self.assertTrue(any(d.get("selection") for c in json.loads(self.build()["foundation__layer-a.json"])["candidates"]
                            for d in c["decisions"]), "the fixture must exercise a decision with a selection")


class WithholdLabelsUnitTests(unittest.TestCase):
    def test_sota_components_outside_the_candidates_lose_their_review_status(self):
        packet = {"candidates": [{"review_status": "confirmed_default",
                                  "decisions": [{"id": "d1", "selection": "default", "review_status": "accepted"}]}],
                  "sota_components_not_in_candidates": [{"component_id": "x", "review_status": "confirmed_default"}],
                  "withheld": ["rationale"]}
        withheld = lane_packets.withhold_labels(packet)
        self.assertIsNone(withheld["sota_components_not_in_candidates"][0]["review_status"])
        self.assertEqual(withheld["sota_components_not_in_candidates"][0]["component_id"], "x")
        self.assertEqual(withheld["candidates"][0]["decisions"], [{"id": "d1"}])
        self.assertEqual(withheld["withheld"][0], "rationale")
        self.assertIn("sota_components_not_in_candidates[].review_status", withheld["withheld"])


class WithholdWithManifestModeTests(ManifestTradingCandidatesTests):
    def test_manifest_mode_trading_packets_only_lose_popularity_and_recency_when_withheld(self):
        # Manifest-mode trading packets carry no decision labels, so --withhold-labels changes
        # them only by the popularity/recency strip (2026-09-23 peer audit); every other field
        # stays as the plain build wrote it.
        plain = json.loads(self.build(trading_candidates="manifest")["us-equities__layer-b.json"])
        withheld = json.loads(self.build(trading_candidates="manifest", withhold=True)["us-equities__layer-b.json"])
        for key in set(plain) | set(withheld):
            if key != "withheld":
                self.assertEqual(scrub_popularity(plain[key]), withheld[key], key)
        self.assertEqual(plain["withheld"], withheld["withheld"][:len(plain["withheld"])])
        self.assertIn("candidates[].upstream.stars", withheld["withheld"])
        self.assertFalse({key for key in keys_anywhere(withheld) if key in POPULARITY_RECENCY_KEYS})
        self.assertIn("newcomer", "".join(json.dumps(plain)), "the fixture must exercise the newcomer flag")
        self.assertFalse({key for key in keys_anywhere(withheld) if key in RECENCY_FLAG_KEYS})
        plain_all = self.build(trading_candidates="manifest")
        withheld_all = self.build(trading_candidates="manifest", withhold=True)
        self.assertNotEqual(plain_all["foundation__layer-a.json"], withheld_all["foundation__layer-a.json"])


# Popularity/recency keys a --withhold-labels packet must never carry (2026-09-23 peer audit:
# lane_packets copied candidates[].upstream verbatim, so judges saw GitHub stars and push dates).
POPULARITY_RECENCY_KEYS = ("stars", "forks", "watchers", "pushed_at", "released_at")
# Re-review 2026-09-23: the latest upstream release is withheld entirely (a date-based tag such as
# "release/2025-11-28" is a release date), with prerelease and the pin_behind_upstream comparison.
RELEASE_KEYS = ("latest", "prerelease", "pin_behind_upstream")
# Final verification 2026-09-23: the newcomer flag marks a recently discovered candidate, a recency signal.
RECENCY_FLAG_KEYS = ("newcomer",)


def keys_anywhere(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from keys_anywhere(item)
    elif isinstance(value, list):
        for item in value:
            yield from keys_anywhere(item)


def scrub_popularity(value):
    """The expected withheld form of a plain packet value: every popularity/recency key and
    archived/license (no fixture requirement names them) removed at any depth."""
    if isinstance(value, dict):
        return {key: scrub_popularity(item) for key, item in value.items()
                if key not in POPULARITY_RECENCY_KEYS + RELEASE_KEYS + RECENCY_FLAG_KEYS + ("archived", "license")}
    if isinstance(value, list):
        return [scrub_popularity(item) for item in value]
    return value


class WithholdPopularityAndRecencyTests(LanePacketsFixture):
    def test_withheld_packets_carry_no_popularity_or_recency_field(self):
        plain = self.build()
        self.assertIn('"stars"', "".join(plain.values()), "the fixture must exercise upstream stars")
        self.assertIn('"pushed_at"', "".join(plain.values()))
        # Manifest-mode trading packets are covered by WithholdWithManifestModeTests (they need
        # the domain catalog cards that fixture adds).
        for trading_candidates in ("ledger",):
            packets = self.build(withhold=True, trading_candidates=trading_candidates)
            for name, text in packets.items():
                packet = json.loads(text)
                found = sorted({key for key in keys_anywhere(packet) if key in POPULARITY_RECENCY_KEYS + RELEASE_KEYS})
                self.assertEqual(found, [], f"{name} ({trading_candidates}) still carries {found}")
                for key in ("stars", "pushed_at", "released_at"):
                    self.assertIn(f"candidates[].upstream.{key}", packet["withheld"], name)
                    self.assertIn(f"sota_components_not_in_candidates[].upstream.{key}", packet["withheld"], name)

    def test_archived_and_license_are_kept_only_where_the_requirement_names_them(self):
        packets = self.build(withhold=True)
        packet = json.loads(packets["foundation__layer-a.json"])
        uploads = [c["upstream"] for c in packet["candidates"] if c.get("upstream")]
        self.assertTrue(uploads, "the fixture must match an upstream record")
        self.assertTrue(all("license" not in u and "archived" not in u for u in uploads))
        self.assertIn("candidates[].upstream.license", packet["withheld"])
        ledger = self.read("catalogs/landscape/foundation.json")
        ledger["layers"][0]["requirement"] = "Use a permissively licensed, non-archived tool."
        self.write("catalogs/landscape/foundation.json", ledger)
        packet = json.loads(self.build(withhold=True)["foundation__layer-a.json"])
        uploads = [c["upstream"] for c in packet["candidates"] if c.get("upstream")]
        self.assertTrue(all("license" in u and "archived" in u for u in uploads))
        self.assertNotIn("candidates[].upstream.license", packet["withheld"])
        self.assertNotIn("stars", json.dumps(uploads))

    def test_a_shared_upstream_record_keeps_license_in_a_later_packet_that_names_it(self):
        # Review finding: withhold_popularity deleted keys in place from the manifest's upstream
        # dict, which build_candidate shares across packets, so a later packet whose requirement
        # names licensing silently lost upstream.license (order-dependent, never listed in withheld).
        shared = {"latest": "1.0", "stars": 10, "pushed_at": "2026-09-01", "license": "MIT", "archived": False}

        def packet(requirement):
            return {"requirement": requirement, "withheld": [],
                    "candidates": [{"key": "c1", "upstream": shared}],
                    "sota_components_not_in_candidates": [{"id": "x", "upstream": shared}]}

        lane_packets.withhold_popularity(packet("Run the tool."))
        later = lane_packets.withhold_popularity(packet("Use a permissively licensed, maintained tool."))
        for copy_ in (later["candidates"][0], later["sota_components_not_in_candidates"][0]):
            self.assertEqual(copy_["upstream"], {"license": "MIT", "archived": False})
        self.assertNotIn("candidates[].upstream.license", later["withheld"])
        self.assertEqual(shared["stars"], 10, "the loaded manifest record itself is never mutated")

    def test_the_latest_release_is_withheld_even_when_it_is_date_shaped(self):
        # Re-review finding: upstream.latest survived stripping, and a date-based tag carries the
        # release date. The stricter option withholds it always, with prerelease and the
        # pin_behind_upstream comparison derived from it; the pin itself stays.
        for latest in ("release/2025-11-28", "2026.09.1", "1.4.0"):
            packet = lane_packets.withhold_popularity({
                "requirement": "Run the tool.", "withheld": [],
                "candidates": [{"key": "c1", "pin": "1.0", "pin_behind_upstream": True,
                                "upstream": {"latest": latest, "prerelease": False, "license": "MIT"}}],
                "sota_components_not_in_candidates": [{"id": "x", "pin": "1.0", "pin_behind_upstream": False,
                                                       "upstream": {"latest": latest}}]})
            self.assertNotIn(latest, json.dumps(packet))
            for collection in ("candidates", "sota_components_not_in_candidates"):
                copy_ = packet[collection][0]
                self.assertEqual(copy_["pin"], "1.0")
                self.assertFalse(set(RELEASE_KEYS) & set(keys_anywhere(copy_)), copy_)
                for label in ("upstream.latest", "upstream.prerelease", "pin_behind_upstream"):
                    self.assertIn(f"{collection}[].{label}", packet["withheld"])

    def test_default_mode_keeps_upstream_metadata_byte_identical(self):
        plain = self.build()
        self.assertEqual(plain, self.build(withhold=False))
        packet = json.loads(plain["foundation__layer-a.json"])
        self.assertTrue(any((c.get("upstream") or {}).get("stars") is not None for c in packet["candidates"]))

if __name__ == "__main__":
    unittest.main()



class CatalogWideSlugJoinTest(unittest.TestCase):
    """The candidate join runs by repository slug against the layer slice first,
    then the whole catalog (the 2026-09-22 manifest keeps the 16-layer foundation
    taxonomy while the ledger is frozen at 20 layers), and never across catalogs."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="lane-packets-join-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)

    @staticmethod
    def component(component_id, repository, pin):
        return {"id": component_id, "repository": repository, "pin": pin, "upstream": None,
                "review_status": "confirmed_default", "pin_behind_upstream": False}

    def build(self, sota_components, catalog_components):
        row = {"layer_id": "agent-sdks", "title": "Agent SDKs", "requirement": "r", "candidates": [
            {"name": "X", "repository": "https://github.com/acme/x", "disposition": "selected",
             "evidence_kind": "source_review", "evidence_refs": []},
            {"name": "Y", "repository": "https://github.com/acme/y", "disposition": "conditional",
             "evidence_kind": "source_review", "evidence_refs": []},
        ]}
        packet = lane_packets.build_packet(row, catalog="foundation", sota_components=sota_components,
                                           recipe_map={}, decisions_by_component={}, seed="s",
                                           checked_at="2026-09-22", root=self.tmp, rules=[],
                                           catalog_components=catalog_components)
        return {candidate["name"]: candidate for candidate in packet["candidates"]}, packet

    def test_component_under_another_layer_of_the_same_catalog_is_joined(self):
        other_layer = [self.component("x-sdk", "https://github.com/acme/x", "1.2.0")]
        by_name, packet = self.build([], other_layer)
        self.assertEqual(by_name["X"]["component_id"], "x-sdk")
        self.assertEqual(by_name["X"]["pin"], "1.2.0")
        self.assertIsNone(by_name["Y"]["component_id"])
        self.assertEqual(packet["sota_components_not_in_candidates"], [],
                         "the layer slice is empty, so nothing is listed as unmatched")

    def test_layer_slice_wins_over_a_catalog_wide_duplicate_slug(self):
        layer = [self.component("x-layer", "https://github.com/acme/x", "1.0.0")]
        catalog_wide = [self.component("x-elsewhere", "https://github.com/acme/x", "9.9.9")]
        by_name, _ = self.build(layer, catalog_wide)
        self.assertEqual(by_name["X"]["component_id"], "x-layer")
        self.assertEqual(by_name["X"]["pin"], "1.0.0")

    def test_catalog_components_excludes_the_other_catalog(self):
        sota_index = {
            ("foundation", "workers"): [self.component("f1", "https://github.com/acme/f1", "1")],
            ("foundation", "agent-sdks"): [],
            ("us-equities", "execution-broker"): [self.component("t1", "https://github.com/acme/t1", "2")],
        }
        foundation = lane_packets.catalog_components(sota_index, "foundation")
        trading = lane_packets.catalog_components(sota_index, "us-equities")
        self.assertEqual([c["id"] for c in foundation], ["f1"])
        self.assertEqual([c["id"] for c in trading], ["t1"])
