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

from scripts.landscape import SEALED_CANDIDATE_FIELDS, withheld_packet_keys

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


class SealedKeysOutTests(LanePacketsFixture):
    """Review of #145 (F5): --withhold-labels seals every candidate's manifest fields into --keys-out, outside
    --out, bound to each packet's sha256."""

    def run_main(self, *extra):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as err:
            code = lane_packets.main(["--root", str(self.root), "--out", str(self.out), *extra])
        return code, err.getvalue()

    def test_withhold_labels_writes_the_sealed_keys_bound_to_each_packet(self):
        keys_path = self.out.parent / "keys" / "packet-keys.json"
        code, err = self.run_main("--withhold-labels", "--keys-out", str(keys_path))
        self.assertEqual(code, 0, err)
        keys = json.loads(keys_path.read_text(encoding="utf-8"))
        self.assertEqual(keys["schema_version"], 1)
        packets_dir = self.out / "packets"
        names = sorted(path.name for path in packets_dir.glob("*__*.json"))
        self.assertEqual(sorted(keys["packets"]), names)
        restored = 0
        for name in names:
            raw = (packets_dir / name).read_bytes()
            packet = json.loads(raw)
            entry = keys["packets"][name]
            self.assertEqual(entry["packet_sha256"], hashlib.sha256(raw).hexdigest())
            self.assertEqual(sorted(entry["candidates"]), sorted(c["key"] for c in packet["candidates"]))
            self.assertEqual(withheld_packet_keys(packet), [])
            restored += sum(1 for fields in entry["candidates"].values() if fields.get("component_id"))
        self.assertTrue(restored, "the fixture must match a manifest component")

    def test_a_blind_build_never_overwrites_packets_or_keys(self):
        # Round 6, OPR6-3: a re-check must not silently replace a wave's packets or keys.
        keys_path = self.out.parent / "keys" / "packet-keys.json"
        self.assertEqual(self.run_main("--withhold-labels", "--keys-out", str(keys_path))[0], 0)
        code, err = self.run_main("--withhold-labels", "--keys-out", str(self.out.parent / "other.json"))
        self.assertEqual(code, 2)
        self.assertIn("already exists", err)
        (self.out / "packets").rename(self.out.parent / "moved")
        code, err = self.run_main("--withhold-labels", "--keys-out", str(keys_path))
        self.assertEqual(code, 2)
        self.assertIn("already exists", err)

    def test_keys_out_is_required_with_withhold_labels_and_outside_out(self):
        self.assertEqual(self.run_main("--withhold-labels")[0], 2)
        self.assertEqual(self.run_main("--keys-out", str(self.out.parent / "k.json"))[0], 2)
        code, err = self.run_main("--withhold-labels", "--keys-out", str(self.out / "packet-keys.json"))
        self.assertEqual(code, 2)
        self.assertIn("outside --out", err)
        self.assertFalse((self.out / "packets").exists())


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
        sealed = {}
        packets = self.build(withhold=True, sealed_keys=sealed)
        for name, text in packets.items():
            packet = json.loads(text)
            for candidate in packet["candidates"]:
                self.assertIsNone(candidate["review_status"], name)
                # Decision records mark a manifest component and are sealed out of the packet (review of #145).
                self.assertNotIn("decisions", candidate)
                for decision in sealed[name]["candidates"][candidate["key"]].get("decisions", []):
                    self.assertNotIn("selection", decision)
                    self.assertNotIn("review_status", decision)
            self.assertIn("candidates[].decisions[].selection", packet["withheld"])
            self.assertIn("candidates[].decisions", packet["withheld"])
        text = "".join(packets.values())
        self.assertNotIn("confirmed_default", text)

    def test_evidence_prose_of_decisions_is_kept(self):
        # Kept in the sealed keys record_verdicts.py restores; the blind packet carries no decision records.
        plain = json.loads(self.build()["foundation__layer-a.json"])
        sealed = {}
        withheld = json.loads(self.build(withhold=True, sealed_keys=sealed)["foundation__layer-a.json"])
        self.assertTrue(any(candidate["decisions"] for candidate in plain["candidates"]), "the fixture needs decisions")
        for before, after in zip(plain["candidates"], withheld["candidates"]):
            self.assertEqual(before["key"], after["key"])
            after_decisions = sealed["foundation__layer-a.json"]["candidates"][after["key"]]["decisions"]
            self.assertEqual(len(before["decisions"]), len(after_decisions))
            for d_before, d_after in zip(before["decisions"], after_decisions):
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
        # them only by the popularity/recency strip (2026-09-23 peer audit) and the sealed manifest
        # fields (review of #145); every other field stays as the plain build wrote it.
        plain = json.loads(self.build(trading_candidates="manifest")["us-equities__layer-b.json"])
        withheld = json.loads(self.build(trading_candidates="manifest", withhold=True)["us-equities__layer-b.json"])
        for key in set(plain) | set(withheld):
            if key not in ("withheld", "sealed_candidates_sha256"):  # the commitment to the sealed values
                expected = scrub_popularity(plain[key])
                if key == "candidates":
                    # Sealed fields and the withheld evidence_kind label (round 5, N5) leave the packet.
                    expected = [{field: value for field, value in candidate.items()
                                 if field not in SEALED_CANDIDATE_FIELDS + ("evidence_kind",)}
                                for candidate in expected]
                self.assertEqual(expected, withheld[key], key)
        self.assertEqual(plain["withheld"], withheld["withheld"][:len(plain["withheld"])])
        self.assertIn("candidates[].upstream.stars", withheld["withheld"])
        self.assertFalse({key for key in keys_anywhere(withheld) if key in POPULARITY_RECENCY_KEYS})
        self.assertIn("newcomer", "".join(json.dumps(plain)), "the fixture must exercise the newcomer flag")
        self.assertFalse({key for key in keys_anywhere(withheld) if key in RECENCY_FLAG_KEYS})
        # Review of catalog #122, finding 9: the candidate-only note exists only on non-adopted
        # (newcomer or keep-but-compare) candidates, so it hints at their status and is withheld too.
        self.assertTrue(any("note" in candidate for candidate in plain["candidates"]), "the fixture must carry a note")
        self.assertFalse(any("note" in candidate for candidate in withheld["candidates"]))
        self.assertIn("candidates[].note", withheld["withheld"])
        # scripts/landscape.py re-checks retained new-wave packets with the same policy.
        self.assertEqual(withheld_packet_keys(withheld), [])
        self.assertIn("candidates[].newcomer", withheld_packet_keys(plain))
        self.assertIn("candidates[].note", withheld_packet_keys(plain))
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
                if key not in POPULARITY_RECENCY_KEYS + RELEASE_KEYS + RECENCY_FLAG_KEYS + ("archived", "license", "note")}
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
        # The candidates' upstream records are sealed (review of #145); the policy still applies to the sealed copy.
        name = "foundation__layer-a.json"
        sealed = {}
        packet = json.loads(self.build(withhold=True, sealed_keys=sealed)[name])
        uploads = [fields["upstream"] for fields in sealed[name]["candidates"].values() if fields.get("upstream")]
        self.assertTrue(uploads, "the fixture must match an upstream record")
        self.assertTrue(all("license" not in u and "archived" not in u for u in uploads))
        self.assertIn("candidates[].upstream.license", packet["withheld"])
        ledger = self.read("catalogs/landscape/foundation.json")
        ledger["layers"][0]["requirement"] = "Use a permissively licensed, non-archived tool."
        self.write("catalogs/landscape/foundation.json", ledger)
        sealed = {}
        packet = json.loads(self.build(withhold=True, sealed_keys=sealed)[name])
        uploads = [fields["upstream"] for fields in sealed[name]["candidates"].values() if fields.get("upstream")]
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

class RecursiveWithheldKeyTests(unittest.TestCase):
    """Review of the #122 fix round (2026-09-23): withheld_packet_keys only looked at the positions
    withhold_popularity stripped (a copy's own keys and one level under upstream), so a withheld key
    anywhere else, a disposition label and a packet built without --withhold-labels all passed both
    record_verdicts.py and scripts/landscape.py. Each position below returned [] on fcee72b."""

    def withheld_packet(self, requirement="Run the tool."):
        return self.seal(lane_packets.withhold_popularity({
            "schema_version": 1, "requirement": requirement, "checked_at": "2026-09-23",
            "enums": {"disposition": ["selected", "conditional"]}, "withheld": [],
            "candidates": [{"key": "c1", "pin": "1.0", "review_status": None, "adopted": True,
                            "decisions": [{"id": "d1", "capability": "x", "evidence_scope": "y"}],
                            "upstream": {"renamed_to": None}}],
            "sota_components_not_in_candidates": [{"id": "x", "pin": "1.0", "review_status": None,
                                                   "upstream": {}}]}))

    @staticmethod
    def seal(packet):
        return lane_packets.seal_candidate_fields(lane_packets.withhold_candidate_labels(packet))[0]

    def test_a_withhold_labels_packet_is_clean(self):
        # Controls: a null review_status, the packet's own checked_at and the output enums stay.
        self.assertEqual(withheld_packet_keys(self.withheld_packet()), [])

    def test_every_withheld_key_position_is_rejected(self):
        positions = {
            "candidates[].prerelease": lambda p: p["candidates"][0].update(prerelease=False),
            "candidates[].latest": lambda p: p["candidates"][0].update(latest="2.0"),
            "candidates[].upstream.newcomer": lambda p: p["candidates"][0].setdefault("upstream", {}).update(newcomer=True),
            "candidates[].upstream.pin_behind_upstream":
                lambda p: p["candidates"][0].setdefault("upstream", {}).update(pin_behind_upstream=True),
            "candidates[].upstream.latest_release":
                lambda p: p["candidates"][0].setdefault("upstream", {}).update(latest_release="2.0"),
            "candidates[].upstream.latest_flag": lambda p: p["candidates"][0].setdefault("upstream", {}).update(
                latest_flag={"tag": "release/2025-11-28", "reason": "tag_listing_only_not_version_shaped"}),
            "candidates[].upstream.release":
                lambda p: p["candidates"][0].setdefault("upstream", {}).update(release={"published_at": "2026-09-01"}),
            "candidates[].evidence.published_at":
                lambda p: p["candidates"][0].update(evidence={"published_at": "2026-09-01"}),
            "candidates[].evidence.stars": lambda p: p["candidates"][0].update(evidence={"stars": 9}),
            "candidates[].decisions[].note": lambda p: p["candidates"][0].setdefault("decisions", [{"id": "d1"}])[0].update(note="gap"),
            "sota_components_not_in_candidates[].upstream.stars":
                lambda p: p["sota_components_not_in_candidates"][0]["upstream"].update(stars=9),
            "newcomers": lambda p: p.update(newcomers=[{"key": "c1"}]),
            "candidates[].upstream.license": lambda p: p["candidates"][0].setdefault("upstream", {}).update(license="MIT"),
            "candidates[].upstream.archived": lambda p: p["candidates"][0].setdefault("upstream", {}).update(archived=False),
            # The disposition labels lane_packets.withhold_labels removes.
            "candidates[].review_status": lambda p: p["candidates"][0].update(review_status="confirmed_default"),
            "sota_components_not_in_candidates[].review_status":
                lambda p: p["sota_components_not_in_candidates"][0].update(review_status="confirmed_default"),
            "candidates[].decisions[].selection": lambda p: p["candidates"][0].setdefault("decisions", [{"id": "d1"}])[0].update(selection="default"),
            "candidates[].decisions[].review_status":
                lambda p: p["candidates"][0].setdefault("decisions", [{"id": "d1"}])[0].update(review_status="accepted_within_scope"),
            "candidates[].disposition": lambda p: p["candidates"][0].update(disposition="selected"),
            "current_choice": lambda p: p.update(current_choice="Native selected tool"),
            # Manifest membership (review of #145): the sealed candidate fields and a receipt's match route.
            **{f"candidates[].{field}": (lambda field: lambda p: p["candidates"][0].update({field: None}))(field)
               for field in SEALED_CANDIDATE_FIELDS},
            "candidates[].registered_receipts[].matched_by": lambda p: p["candidates"][0].update(
                registered_receipts=[{"kind": "host_e2e", "path": "a.json", "matched_by": "component_id"}]),
            "withheld[] lacks candidates[].component_id": lambda p: p["withheld"].remove("candidates[].component_id"),
            # A packet built without --withhold-labels lacks the policy labels in withheld[].
            "withheld[] lacks candidates[].upstream.stars": lambda p: p["withheld"].remove("candidates[].upstream.stars"),
        }
        for label, change in positions.items():
            with self.subTest(label):
                packet = self.withheld_packet()
                change(packet)
                self.assertIn(label, withheld_packet_keys(packet))

    def test_archived_and_license_pass_only_where_the_requirement_names_them(self):
        packet = self.withheld_packet("Use a permissively licensed, maintained tool.")
        packet["sota_components_not_in_candidates"][0]["upstream"].update(license="MIT", archived=False)
        self.assertEqual(withheld_packet_keys(packet), [])

    def test_the_builder_strips_every_position_the_check_rejects(self):
        packet = self.withheld_packet()
        raw = {"requirement": "Run the tool.", "withheld": [],
               "candidates": [{"key": "c1", "evidence": {"stars": 9, "kept": 1},
                               "upstream": {"latest_flag": {"tag": "release/2025-11-28"},
                                            "release": {"published_at": "2026-09-01", "tag": "v1"}}}],
               "sota_components_not_in_candidates": []}
        built, sealed = lane_packets.seal_candidate_fields(lane_packets.withhold_candidate_labels(
            lane_packets.withhold_popularity(copy.deepcopy(raw))))
        self.assertNotIn("2025-11-28", json.dumps([built, sealed]))
        self.assertEqual(built["candidates"][0]["evidence"], {"kept": 1})
        self.assertEqual(sealed["c1"]["upstream"], {})
        for label in ("candidates[].evidence.stars", "candidates[].upstream.latest_flag",
                      "candidates[].upstream.release"):
            self.assertIn(label, built["withheld"])
        self.assertEqual(withheld_packet_keys(built), [])
        self.assertEqual(raw["candidates"][0]["evidence"]["stars"], 9, "the input is never mutated")
        self.assertEqual(withheld_packet_keys(packet), [])

    def test_a_selection_word_leaves_a_candidate_name(self):
        # Round 6, B6-6: "ECC selected skills" and a "(selected)" suffix name the winner.
        packet = {"candidates": [{"key": "c1", "name": "ECC selected skills"}, {"key": "c2", "name": "Tool (selected)"},
                                 {"key": "c3", "name": "Plain [default]"}, {"key": "c4", "name": "Other"}]}
        built, _ = lane_packets.seal_candidate_fields(packet)
        self.assertEqual([c["name"] for c in built["candidates"]], ["ECC skills", "Tool", "Plain", "Other"])


class WithheldProseTests(unittest.TestCase):
    """Codex review of #145: the ledger's shared prose named the incumbent ("Use the selected NautilusTrader
    destination...") before a blind lane read any evidence."""

    def test_sentences_naming_a_candidate_or_a_selection_are_withheld(self):
        packet = {"candidates": [{"name": "NautilusTrader", "repository": "https://github.com/nautechsystems/nautilus_trader"},
                                 {"name": "LEAN", "repository": "https://github.com/QuantConnect/Lean"}],
                  "requirement": "Use the selected NautilusTrader destination with numeric risk.",
                  "limitations": ["Nautilus 2.0.0rc5 is a prerelease.", "Fills are synthetic. The LEAN default stays."],
                  "existing_overturn_when": "Reopen if a parity check fails. Keep the prior oracle.",
                  "withheld": []}
        out = lane_packets.withhold_prose(packet)
        # No layer_scope_terms in this packet, so it is not pointed at them (round 5, N1/N4).
        self.assertEqual(out["requirement"], lane_packets.NEUTRAL_REQUIREMENT_NO_SCOPE)
        # Round 5, N1: a sentence naming a candidate without stating the choice keeps its content with the name
        # redacted; a bare "Keep" names no choice and stays.
        self.assertEqual(out["limitations"], ["<candidate> 2.0.0rc5 is a prerelease.", "Fills are synthetic."])
        # "the prior oracle" names an earlier choice (Codex review of #145 at a516c477).
        self.assertEqual(out["existing_overturn_when"], "Reopen if a parity check fails.")
        self.assertTrue(any("state the current choice" in label for label in out["withheld"]))

    def test_short_names_owners_variants_and_candidate_prose_are_covered(self):
        # Round 5, N2, and the review of 52344da8: gh, RTK or an owner survived; role and card_limitations kept
        # selection prose.
        packet = {"title": "Git and GitHub automation", "candidates": [
            {"name": "gh", "repository": "https://github.com/cli/cli", "role": "The selected GitHub CLI."},
            {"name": "RTK", "repository": "https://github.com/rtk-ai/rtk",
             "card_limitations": ["Output is condensed.", "RTK stays the default filter."]},
            {"name": "Nautilus Trader", "repository": "https://github.com/nautechsystems/nautilus_trader"}],
                  "requirement": "Automate reviews with gh. Use the gh CLI by default. The nautilus-trader engine replays. "
                                 "Selected pages are cached. Keep receipts.",
                  "withheld": []}
        out = lane_packets.withhold_prose(packet)
        self.assertEqual(out["requirement"], "Automate reviews with <candidate>. The <candidate> engine replays. "
                                             "Selected pages are cached. Keep receipts.")
        self.assertIsNone(out["candidates"][0]["role"])
        self.assertEqual(out["candidates"][1]["card_limitations"], ["Output is condensed."])
        matcher = lane_packets.candidate_matcher(packet["candidates"])
        self.assertTrue(matcher.search("see nautechsystems releases"))  # an owner unique to one candidate
        self.assertFalse(matcher.search("the ghost of rtkx"))  # whole tokens only
        self.assertFalse(lane_packets.candidate_matcher([{"component_id": "one"}]).search("only one run"))

    def test_aliases_catalog_names_and_membership_status_are_withheld(self):
        # Codex review of #145 at a516c477: "gh CLI has no separate manifests/stack.json inventory entry" survived,
        # and a factor layer's prose named Nautilus, LEAN and Alpaca, candidates of other layers.
        packet = {"candidates": [{"name": "GitHub CLI (gh)", "repository": "https://github.com/cli/cli"},
                                 {"name": "Qlib", "repository": "https://github.com/microsoft/qlib"}],
                  "requirement": "Automate with gh. Compare factors against Nautilus fills.",
                  "limitations": ["gh CLI has no separate manifests/stack.json inventory entry.",
                                  "Reopen the implementation choice if Alpaca cannot fill."], "withheld": []}
        others = [{"name": "Nautilus Trader", "repository": "https://github.com/nautechsystems/nautilus_trader"},
                  {"name": "Alpaca", "repository": "https://github.com/alpacahq/alpaca-py"}]
        out = lane_packets.withhold_prose(packet, others)
        self.assertEqual(out["requirement"], "Automate with <candidate>. Compare factors against <candidate> fills.")
        self.assertEqual(out["limitations"], [])

    def test_a_neutral_requirement_is_kept(self):
        packet = {"candidates": [{"name": "Widget One", "repository": "https://github.com/acme/widget-one"}],
                  "requirement": "Reproduce the ledger with deterministic fills.", "withheld": []}
        self.assertEqual(lane_packets.withhold_prose(packet)["requirement"], "Reproduce the ledger with deterministic fills.")


class ManifestNewcomersTests(LanePacketsFixture):
    """--manifest-newcomers (2026-09-23 landscape sweep): the dated manifest's surviving newcomers reach
    foundation packets too, shuffled with the ledger candidates, with their registered evidence files."""

    SWEEP = "evidence/artifacts/landscape-sweep-20260923"

    def setUp(self):
        super().setUp()
        registered = {}
        for name in ("new-alpha.json", "new-gamma-default.json", "stale.json", "new-beta.json"):
            self.write(f"{self.SWEEP}/{name}", {"evidence_class": "source_review", "file": name})
            registered[f"{self.SWEEP}/{name}"] = hashlib.sha256(
                (self.root / self.SWEEP / name).read_bytes()).hexdigest()
        registered[f"{self.SWEEP}/stale.json"] = "0" * 64  # edited after registration
        self.write(f"{self.SWEEP}/unregistered.json", {"evidence_class": "source_review"})
        self.write("manifests/evidence.json", {"schema_version": 1, "convergence_records": [], "receipts": [],
                                               "files": [{"path": path, "sha256": sha, "bytes": 1}
                                                         for path, sha in registered.items()]})
        manifest = self.read(lane_packets.SOTA_MANIFEST_PATH)
        row = manifest["foundation"][0]
        row["candidates"] = [
            {"repository": "https://github.com/new/alpha", "disposition": "keep_but_compare",
             "demonstrated_gap": "a gap", "evidence": [
                 f"{self.SWEEP}/new-alpha.json", "gh api graphql repository(new/alpha): license MIT",
                 f"{self.SWEEP}/new-alpha.json (lines 1-9)", f"{self.SWEEP}/unregistered.json",
                 f"{self.SWEEP}/stale.json", f"{self.SWEEP}/../{self.SWEEP}/new-alpha.json"]},
            {"repository": "https://github.com/new/beta", "disposition": "refuted_keep_but_compare",
             "evidence": [f"{self.SWEEP}/new-beta.json"]},
            {"repository": "https://github.com/acme/widget-one", "disposition": "keep_but_compare"},
        ]
        row["alternatives_keep_but_compare"] = [
            {"repository": "https://github.com/new/beta", "comparison_that_would_overturn": "repeated, unrefuted"},
            {"repository": "https://github.com/new/gamma-default",
             "comparison_that_would_overturn": "a run", "evidence": [f"{self.SWEEP}/new-gamma-default.json"]},
        ]
        self.write(lane_packets.SOTA_MANIFEST_PATH, manifest)

    def candidates(self, **kwargs):
        packet = self.packet("foundation", "layer-a", self.build(**kwargs))
        return packet, {c["repository"]: c for c in packet["candidates"]}

    def test_the_default_build_carries_no_manifest_newcomer(self):
        _, by_repository = self.candidates()
        self.assertEqual(set(by_repository), {"https://github.com/acme/widget-one", None})

    def test_surviving_newcomers_carry_only_registered_unchanged_evidence_files(self):
        _, by_repository = self.candidates(manifest_newcomers_on=True)
        self.assertEqual(set(by_repository), {"https://github.com/acme/widget-one", None,
                                              "https://github.com/new/alpha", "https://github.com/new/gamma-default"})
        alpha = by_repository["https://github.com/new/alpha"]
        self.assertEqual(alpha["evidence_refs"], [f"{self.SWEEP}/new-alpha.json"])
        self.assertFalse(alpha["adopted"])
        self.assertIsNone(alpha["component_id"])
        self.assertEqual(by_repository["https://github.com/new/gamma-default"]["evidence_refs"],
                         [f"{self.SWEEP}/new-gamma-default.json"])

    def test_newcomers_are_shuffled_with_the_ledger_candidates(self):
        packet, _ = self.candidates(manifest_newcomers_on=True)
        ledger = self.read(lane_packets.LEDGER_FILES["foundation"])["layers"][0]["candidates"]
        expected = [c.get("repository") for c in ledger] + ["https://github.com/new/alpha",
                                                            "https://github.com/new/gamma-default"]
        lane_packets.make_rng(lane_packets.DEFAULT_SEED, "foundation", "layer-a").shuffle(expected)
        self.assertEqual([c["repository"] for c in packet["candidates"]], expected)
        self.assertEqual([c["key"] for c in packet["candidates"]], ["c1", "c2", "c3", "c4"])

    def test_a_blind_build_drops_label_bearing_paths_and_newcomer_markers(self):
        packet, by_repository = self.candidates(manifest_newcomers_on=True, withhold=True)
        self.assertEqual(by_repository["https://github.com/new/gamma-default"]["evidence_refs"], [])
        self.assertEqual(by_repository["https://github.com/new/alpha"]["evidence_refs"], [f"{self.SWEEP}/new-alpha.json"])
        for candidate in packet["candidates"]:
            self.assertNotIn("newcomer", candidate)
            self.assertNotIn("note", candidate)
        self.assertEqual(withheld_packet_keys(packet), [])

    def test_a_refuted_discovery_proposal_never_removes_a_ledger_candidate(self):
        # Codex review of #151: the refutation is of the proposal ("not new to the catalog"), not the repository.
        manifest = self.read(lane_packets.SOTA_MANIFEST_PATH)
        manifest["foundation"][0]["candidates"][2]["disposition"] = "refuted_keep_but_compare"
        self.write(lane_packets.SOTA_MANIFEST_PATH, manifest)
        _, by_repository = self.candidates(manifest_newcomers_on=True, withhold=True)
        self.assertTrue(by_repository["https://github.com/acme/widget-one"]["adopted"])

    def test_disposition_named_evidence_paths_are_withheld_from_a_blind_build(self):
        # Codex review of #151: the disposition vocabulary names the withheld label as plainly as "default".
        for name in ("keep-but-compare.json", "refuted-targeted-candidate.json", "newcomer-x.json"):
            self.assertTrue(lane_packets.label_bearing_receipt({"path": f"{self.SWEEP}/{name}"}), name)
        for name in ("candidate-3.json", "new-alpha.json", "owner-repo.json"):
            self.assertFalse(lane_packets.label_bearing_receipt({"path": f"{self.SWEEP}/{name}"}), name)

    def test_non_github_candidates_are_carried_under_a_url_identity(self):
        # Codex review of #151: Hugging Face models have no GitHub slug and were silently dropped.
        manifest = self.read(lane_packets.SOTA_MANIFEST_PATH)
        manifest["foundation"][0]["candidates"] += [
            {"repository": "https://huggingface.co/Org/Embed-Model", "disposition": "keep_but_compare"},
            {"repository": "https://huggingface.co/org/embed-model/", "disposition": "keep_but_compare"},
            {"repository": "https://huggingface.co/org/refuted-model", "disposition": "refuted_keep_but_compare"}]
        self.write(lane_packets.SOTA_MANIFEST_PATH, manifest)
        _, by_repository = self.candidates(manifest_newcomers_on=True)
        self.assertIn("https://huggingface.co/Org/Embed-Model", by_repository)
        self.assertNotIn("https://huggingface.co/org/embed-model/", by_repository, "one identity, first seen wins")
        self.assertNotIn("https://huggingface.co/org/refuted-model", by_repository)
        _, default = self.candidates()
        self.assertNotIn("https://huggingface.co/Org/Embed-Model", default)

    def test_a_path_with_a_locator_attaches_the_path_only(self):
        # Codex review of #151: the manifest writes locators after a path ("<path> items[claude-x].corrections[0]").
        manifest = self.read(lane_packets.SOTA_MANIFEST_PATH)
        manifest["foundation"][0]["candidates"][0]["evidence"] = [
            f"{self.SWEEP}/new-alpha.json items[claude-x].corrections[0]"]
        self.write(lane_packets.SOTA_MANIFEST_PATH, manifest)
        packet, by_repository = self.candidates(manifest_newcomers_on=True, withhold=True)
        self.assertEqual(by_repository["https://github.com/new/alpha"]["evidence_refs"], [f"{self.SWEEP}/new-alpha.json"])
        self.assertNotIn("items[claude-x]", json.dumps(packet))

    def test_the_cli_flag_reaches_the_packets(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(lane_packets.main(["--root", str(self.root), "--out", str(self.out),
                                                "--manifest-newcomers", "--withhold-labels"]), 0)
        packet = json.loads((self.out / "packets" / "foundation__layer-a.json").read_text(encoding="utf-8"))
        self.assertIn("https://github.com/new/alpha", [c["repository"] for c in packet["candidates"]])


class ManifestNewcomersTradingTests(ManifestTradingCandidatesTests):
    """--manifest-newcomers in manifest-mode trading packets: a refuted discovery is left out."""

    def test_a_refuted_newcomer_is_left_out_in_manifest_mode(self):
        self.write("manifests/evidence.json", {"schema_version": 1, "convergence_records": [], "receipts": [],
                                               "files": []})
        manifest = self.read(lane_packets.SOTA_MANIFEST_PATH)
        manifest["trading"][0]["candidates"][0]["disposition"] = "refuted_targeted_candidate"
        self.write(lane_packets.SOTA_MANIFEST_PATH, manifest)
        default = self.packet("us-equities", "layer-b", self.build(trading_candidates="manifest"))
        self.assertIn("https://github.com/acme/newcomer", [c["repository"] for c in default["candidates"]])
        packet = self.packet("us-equities", "layer-b", self.build(trading_candidates="manifest",
                                                                  manifest_newcomers_on=True))
        repositories = [c["repository"] for c in packet["candidates"]]
        self.assertNotIn("https://github.com/acme/newcomer", repositories)
        self.assertIn("https://github.com/acme/kbc-only", repositories)


class GapReceiptsTests(LanePacketsFixture):
    """2026-09-23 re-record: --gap-receipts gives each packet the receipt paths the gap-wave owner ledgers list
    for its layer, and never the gap text (it derives from the previous verdict's open_gaps)."""

    def test_packets_carry_their_layers_gap_receipt_paths_only(self):
        self.write("evidence/artifacts/gap-wave9/layer-a/1-check.json", {"k": 1})
        self.write("evidence/artifacts/gap-wave9/layer-a/0-check.json", {"k": 0})
        for owner in ("owner-a", "owner-b"):
            self.write(f"catalogs/landscape/gap-wave9--{owner}.json", {"layers": [
                {"catalog": "foundation", "layer_id": "layer-a", "gaps": [
                    {"index": 0, "text": "SECRET-GAP-TEXT names the incumbent", "status": "settled", "receipts": [
                        {"path": "evidence/artifacts/gap-wave9/layer-a/1-check.json"},
                        {"path": "evidence/artifacts/gap-wave9/layer-a/0-check.json"},
                        {"path": "evidence/artifacts/gap-wave9/layer-a/missing.json"}]}]}]})
        packets = self.build(gap_receipts=True)
        packet = json.loads(packets[lane_packets.packet_filename("foundation", "layer-a")])
        self.assertEqual(packet["gap_receipts"], ["evidence/artifacts/gap-wave9/layer-a/0-check.json",
                                                  "evidence/artifacts/gap-wave9/layer-a/1-check.json"])
        self.assertIn("gap_receipts lists", packet["gap_receipts_note"])
        self.assertNotIn("SECRET-GAP-TEXT", "".join(packets.values()))
        other = json.loads(packets[lane_packets.packet_filename("us-equities", "layer-b")])
        self.assertEqual(other["gap_receipts"], [])

    def test_default_build_has_no_gap_receipts(self):
        for text in self.build().values():
            self.assertNotIn("gap_receipts", text)

    def test_gap_receipts_are_refused_with_withhold_labels(self):
        """Round-8 review of #145: gap receipts name the previous winner, so a blind build refuses them."""
        with self.assertRaisesRegex(ValueError, "cannot be combined with --withhold-labels"):
            self.build(gap_receipts=True, withhold=True)
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            code = lane_packets.main(["--root", str(self.root), "--out", str(self.out), "--gap-receipts",
                                      "--withhold-labels"])
        self.assertEqual(code, 2)
        self.assertIn("cannot be combined with --withhold-labels", err.getvalue())
        self.assertFalse(self.out.exists(), "nothing is written")


class RegisteredReceiptsTests(LanePacketsFixture):
    """2026-09-23 re-record: --registered-receipts attaches each component's registered receipts, so a
    lane can open and cite a native receipt its ledger row never named. PR #142 re-review: a repository
    match must not attach one component's receipts to another component that shares its repository."""

    def receipts(self, *entries, stack=()):
        self.write("manifests/evidence.json", {"schema_version": 1, "files": [], "convergence_records": [],
                                               "receipts": [dict(entry, claim="c", limitations=[]) for entry in entries]})
        self.write("manifests/stack.json", {"components": [{"id": cid, "repository": repo} for cid, repo in stack]})

    def candidate(self, packets=None, name="Widget One"):
        packet = self.packet("foundation", "layer-a", packets)
        return packet, next(c for c in packet["candidates"] if c["name"] == name)

    def add_manifest_component(self, component_id, repository, layer="layer-a"):
        manifest = self.read(lane_packets.SOTA_MANIFEST_PATH)
        row = next(row for row in manifest["foundation"] if row["layer"] == layer)
        row["components"].append({"id": component_id, "repository": repository, "pin": "0.1.0", "upstream": None,
                                  "review_status": "candidate", "pin_behind_upstream": False})
        self.write(lane_packets.SOTA_MANIFEST_PATH, manifest)

    def test_candidates_carry_their_registered_receipts_sorted_by_path(self):
        _packet, candidate = self.candidate()
        component = candidate["component_id"]
        self.receipts({"id": "r2", "kind": "native_cli_e2e", "component_ids": [component], "path": "evidence/receipts/b.json"},
                      {"id": "r1", "kind": "host_e2e", "component_ids": [component, "other"], "path": "evidence/receipts/a.json"},
                      {"id": "r3", "kind": "native_cli_e2e", "component_ids": ["unrelated"], "path": "evidence/receipts/c.json"})
        packet, candidate = self.candidate(self.build(registered_receipts=True))
        self.assertEqual(candidate["registered_receipts"], [
            {"id": "r1", "kind": "host_e2e", "path": "evidence/receipts/a.json", "matched_by": "component_id"},
            {"id": "r2", "kind": "native_cli_e2e", "path": "evidence/receipts/b.json", "matched_by": "component_id"}])
        self.assertTrue(all("registered_receipts" in c for c in packet["candidates"]))
        self.assertIn("registered_receipts lists", packet["registered_receipts_note"])

    def test_a_receipt_in_the_stack_id_space_matches_by_repository_when_nothing_else_shares_it(self):
        # manifests/stack.json names nautilus-trader where the sota manifest says nautilustrader.
        self.receipts({"id": "r9", "kind": "native_cli_e2e", "component_ids": ["stack-widget"],
                       "path": "evidence/receipts/z.json"},
                      stack=[("stack-widget", "https://github.com/Acme/Widget-One.git")])
        _packet, candidate = self.candidate(self.build(registered_receipts=True))
        self.assertEqual(candidate["registered_receipts"], [
            {"id": "r9", "kind": "native_cli_e2e", "path": "evidence/receipts/z.json", "matched_by": "repository"}])

    def test_two_manifest_ids_sharing_one_repository_get_nothing_by_repository(self):
        # The execution-broker packet gave nautilus-ibkr-adapter all six NautilusTrader engine receipts,
        # and codex-native-sdk got every Codex CLI receipt.
        self.add_manifest_component("widget-one-adapter", "https://github.com/acme/widget-one")
        self.receipts({"id": "r9", "kind": "native_cli_e2e", "component_ids": ["stack-widget"],
                       "path": "evidence/receipts/z.json"},
                      stack=[("stack-widget", "https://github.com/acme/widget-one")])
        packet, candidate = self.candidate(self.build(registered_receipts=True))
        self.assertEqual(candidate["registered_receipts"], [])
        self.assertNotIn("evidence/receipts/z.json", json.dumps(packet))

    def aliases(self, mapping):
        self.write("tools/sota-convergence/receipt-component-aliases.json", {"schema_version": 1, "aliases": mapping})

    def test_an_alias_attaches_receipts_where_a_shared_repository_cannot(self):
        # nautechsystems/nautilus_trader serves nautilustrader and nautilus-ibkr-adapter; the explicit alias
        # nautilus-trader -> nautilustrader reaches the engine only.
        _packet, candidate = self.candidate()
        self.add_manifest_component("widget-one-adapter", candidate["repository"])
        self.receipts({"id": "r9", "kind": "native_cli_e2e", "component_ids": ["stack-widget"],
                       "path": "evidence/receipts/z.json"},
                      stack=[("stack-widget", candidate["repository"])])
        self.aliases({"stack-widget": candidate["component_id"]})
        packet, candidate = self.candidate(self.build(registered_receipts=True))
        self.assertEqual(candidate["registered_receipts"], [
            {"id": "r9", "kind": "native_cli_e2e", "path": "evidence/receipts/z.json", "matched_by": "alias"}])
        adapter = [c for c in packet["sota_components_not_in_candidates"] if c["id"] == "widget-one-adapter"]
        self.assertTrue(adapter and adapter[0]["registered_receipts"] == [], adapter)

    def test_an_alias_between_different_repositories_is_refused(self):
        _packet, candidate = self.candidate()
        self.receipts({"id": "r9", "kind": "native_cli_e2e", "component_ids": ["stack-widget"],
                       "path": "evidence/receipts/z.json"},
                      stack=[("stack-widget", "https://github.com/other/thing")])
        self.aliases({"stack-widget": candidate["component_id"]})
        with self.assertRaisesRegex(ValueError, "do not share one repository"):
            self.build(registered_receipts=True)

    def test_two_stack_ids_sharing_one_repository_get_nothing_by_repository(self):
        self.receipts({"id": "r9", "kind": "native_cli_e2e", "component_ids": ["stack-widget"],
                       "path": "evidence/receipts/z.json"},
                      stack=[("stack-widget", "https://github.com/acme/widget-one"),
                             ("stack-widget-plugin", "https://github.com/acme/widget-one")])
        _packet, candidate = self.candidate(self.build(registered_receipts=True))
        self.assertEqual(candidate["registered_receipts"], [])

    def test_an_id_match_suppresses_every_repository_match(self):
        _packet, candidate = self.candidate()
        self.receipts({"id": "r1", "kind": "host_e2e", "component_ids": [candidate["component_id"]],
                       "path": "evidence/receipts/a.json"},
                      {"id": "r9", "kind": "native_cli_e2e", "component_ids": ["stack-widget"],
                       "path": "evidence/receipts/z.json"},
                      stack=[("stack-widget", "https://github.com/acme/widget-one")])
        _packet, candidate = self.candidate(self.build(registered_receipts=True))
        self.assertEqual([(r["path"], r["matched_by"]) for r in candidate["registered_receipts"]],
                         [("evidence/receipts/a.json", "component_id")])

    def test_label_bearing_receipts_are_left_out_of_blind_packets(self):
        # Codex review of #145: a path such as native-session-defaults-20260920.json repeats the withheld id.
        _packet, candidate = self.candidate()
        component = candidate["component_id"]
        self.receipts({"id": "native-session-defaults-20260920", "kind": "native_cli_e2e", "component_ids": [component],
                       "path": "evidence/receipts/native-session-defaults-20260920.json"},
                      {"id": "neutral-run-20260920", "kind": "native_cli_e2e", "component_ids": [component],
                       "path": "evidence/receipts/neutral-run-20260920.json"})
        packet, candidate = self.candidate(self.build(registered_receipts=True, withhold=True))
        self.assertEqual([r["path"] for r in candidate["registered_receipts"]],
                         ["evidence/receipts/neutral-run-20260920.json"])
        self.assertTrue(any("selection role" in label for label in packet["withheld"]))
        _packet, open_candidate = self.candidate(self.build(registered_receipts=True))
        self.assertEqual(len(open_candidate["registered_receipts"]), 2)

    def test_default_build_is_unchanged(self):
        self.receipts({"id": "r1", "kind": "host_e2e", "component_ids": ["anything"], "path": "evidence/receipts/a.json"})
        self.assertEqual(self.build(), self.build(registered_receipts=False))
        for text in self.build().values():
            self.assertNotIn("registered_receipts", text)

    def test_withheld_packets_keep_kind_and_path_but_not_the_receipt_id(self):
        _packet, candidate = self.candidate()
        self.receipts({"id": "native-session-run-20260920", "kind": "host_e2e",
                       "component_ids": [candidate["component_id"]], "path": "evidence/receipts/a.json"})
        packets = self.build(registered_receipts=True, withhold=True)
        packet, candidate = self.candidate(packets)
        # matched_by component_id exists only for a manifest component, so it is dropped (review of #145).
        self.assertEqual(candidate["registered_receipts"], [{"kind": "host_e2e", "path": "evidence/receipts/a.json"}])
        self.assertNotIn("native-session-run-20260920", "".join(packets.values()))
        self.assertNotIn("matched_by", "".join(json.dumps(json.loads(text)["candidates"]) for text in packets.values()))
        for text in packets.values():
            document = json.loads(text)
            self.assertEqual(withheld_packet_keys(document), [])
            for label in ("candidates[].registered_receipts[].id",
                          "sota_components_not_in_candidates[].registered_receipts[].id",
                          "candidates[].registered_receipts[].matched_by"):
                self.assertIn(label, document["withheld"])
        for text in self.build(registered_receipts=True).values():
            self.assertNotIn("registered_receipts[].id", json.dumps(json.loads(text)["withheld"]))


class RealPacketProseTests(unittest.TestCase):
    """Independent review of #145, round 7, on the real 2026-09-23 blind packets: ordinary words are not candidate
    terms (BL7-3), status-free limitations and evidence stay (BL7-4), and status statements go (BL7-4, BL7-5)."""

    @classmethod
    def setUpClass(cls):
        packets = lane_packets.build_all_packets(
            ROOT, catalogs=["foundation", "us-equities"], seed="20260923", checked_at="2026-09-23",
            trading_candidates="manifest", withhold=True,
            manifest="catalogs/sota-convergence/manifest-20260923.json", registered_receipts=True, sealed_keys={})
        cls.packets = {name: json.loads(text) for name, text in packets.items()}
        cls.text = " ".join(packets.values())

    def test_ordinary_words_are_not_catalog_terms(self):
        clause = "retain scoped telemetry, failed attempts and recoverable state"
        for layer in ("data-quality-orchestration", "evaluation-experiments", "security-supply-chain"):
            self.assertIn(clause, self.packets[f"us-equities__{layer}.json"]["requirement"], layer)
        self.assertTrue(self.packets["foundation__code-navigation.json"]["requirement"].startswith(
            "Retrieve exact source and references"))
        # Another layer's incumbents stay redacted (Codex review of #145 at a516c477).
        for layer in ("research-factors-ml", "portfolio-risk"):
            text = json.dumps(self.packets[f"us-equities__{layer}.json"])
            for name in ("Nautilus", "LEAN", "Alpaca"):
                self.assertNotIn(name, text, (layer, name))

    def test_status_free_limitations_and_evidence_stay(self):
        for sentence in ("reported_execution_blocked_review_incomplete", "Failed-turn usage is retained",
                         "NullSlippageModel", "K-fold validation is inappropriate",
                         "Default examples use model API credentials", "Selected-file handoff",
                         "Retained local sanitized"):
            self.assertIn(sentence, self.text)

    def test_status_statements_go(self):
        for sentence in ("selected destination runtime", "selected live-primary"):
            self.assertNotIn(sentence, self.text)

    def test_joined_proper_nouns_are_redacted_but_paths_are_not(self):
        # Round 8, REG8-4: '-' and '/' join words; only a path token keeps its segments.
        matcher = lane_packets.candidate_matcher(
            [{"name": "Qlib", "repository": "https://github.com/microsoft/qlib"}],
            catalog_candidates=[{"name": "NautilusTrader", "repository": "https://github.com/nautechsystems/nautilus_trader"}])
        self.assertEqual(matcher.sub("<candidate>", "a Nautilus-native adapter"), "a <candidate>-native adapter")
        self.assertEqual(matcher.sub("<candidate>", "Qlib/Nautilus parity"), "<candidate>/<candidate> parity")
        path = "see blueprints/us-equities/engine-Nautilus/spy-parity/verdict.json here"
        self.assertEqual(matcher.sub("<candidate>", path), path)

    def test_the_status_rules(self):
        cases = {"Failed-turn usage is retained.": False, "Default examples use model API credentials;": False,
                 "Default random/K-fold validation is inappropriate.": False, "Selected-file handoff bundles": False,
                 "Retained local sanitized operational logs and LogQL queries": False,
                 "The replay failed; it is retained.": False, "selected destination runtime (runtime-target.json)": True,
                 "IBKR is this catalog's selected live-primary broker path;": True, "The selected GitHub CLI.": True,
                 "Selected north-star engine for backtests.": True, "NautilusTrader remains the default engine.": True}
        for sentence, expected in cases.items():
            self.assertEqual(lane_packets.states_candidate_status(sentence), expected, sentence)
        for marker in ("failed", "Passed", "blocked", "verdict.json", "runtime-target.json",
                       "reported_execution_blocked_review_incomplete", "exit code 1", "4/6"):
            self.assertTrue(lane_packets.RESULT_MARKER.search(marker), marker)


class BlindBuildPlacementTests(unittest.TestCase):
    """Round 7: an absolute --manifest is recorded relative to --root (REG7-4); --out and --keys-out may not sit in a
    repository (OPR7-5)."""

    def setUp(self):
        self.scratch = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.scratch)

    def build(self, out, keys, manifest):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as err:
            code = lane_packets.main(["--root", str(ROOT), "--out", str(out), "--keys-out", str(keys),
                                      "--manifest", manifest, "--trading-candidates", "manifest",
                                      "--withhold-labels", "--registered-receipts", "--checked-at", "2026-09-23",
                                      "--seed", "20260923"])
        return code, err.getvalue()

    def test_an_absolute_manifest_is_recorded_relative_to_root(self):
        relative = "catalogs/sota-convergence/manifest-20260923.json"
        code, err = self.build(self.scratch / "w", self.scratch / "k" / "keys.json", str(ROOT / relative))
        self.assertEqual(code, 0, err)
        keys = json.loads((self.scratch / "k" / "keys.json").read_text(encoding="utf-8"))
        self.assertEqual(keys["manifest"]["path"], relative)
        code, err = self.build(self.scratch / "w2", self.scratch / "k2" / "keys.json", str(self.scratch / "m.json"))
        self.assertEqual(code, 2)
        self.assertIn("not a file under --root", err)

    def test_outputs_inside_a_repository_are_refused(self):
        repo = self.scratch / "repo"
        (repo / ".git").mkdir(parents=True)
        (self.scratch / "link-into-repo").symlink_to(repo)
        relative = "catalogs/sota-convergence/manifest-20260923.json"
        # Round 8, REG8-5: a symlink leading into the checkout is refused too.
        for out, keys in ((repo / "w", self.scratch / "k" / "keys.json"), (self.scratch / "w", repo / "k.json"),
                          (self.scratch / "link-into-repo" / "w", self.scratch / "k2" / "keys.json")):
            code, err = self.build(out, keys, relative)
            self.assertEqual(code, 2)
            self.assertIn("inside the git repository", err)


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
