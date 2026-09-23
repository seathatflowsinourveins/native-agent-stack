"""Protect comparison coverage and evidence boundaries using local fixtures."""

import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from scripts.landscape import MANIFEST, build_landscape


# Bytes the fixture writes for the sealed Claude run (self.write serializes with json.dumps).
SEALED_RUN_1_SHA256 = hashlib.sha256(json.dumps({"run_id": "run-1", "lane": "claude"}).encode("utf-8")).hexdigest()

class LandscapeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.manifest = {
            "schema_version": 1, "checked_at": "2026-09-21", "source_base": "a" * 40,
            "scope": "Fixture selection", "status": "reviewed_baseline",
            "new_pc_scope": "New host acceptance required", "universal_superiority": "not_established",
            "rules": ["Execution is not superiority"],
            "catalogs": {"foundation": "foundation.json", "us-equities": "domain.json"},
            "sources": {"foundation_manifest": "foundation-manifest.json",
                        "foundation_decisions": "decisions.json", "domain_manifest": "domain-manifest.json",
                        "trading_taxonomy": "taxonomy.json",
                        "repository_index": "index.json", "selected_manifest": "stack.json",
                        "freshness_snapshot": "freshness.json"},
        }
        self.candidate = {
            "name": "Native selected tool", "repository": "https://github.com/example/selected",
            "disposition": "selected", "rationale": "Passed the required scoped operation",
            "evidence_kind": "native_execution", "evidence_refs": ["receipt.json"],
        }
        # Layer-verdict schema v2 defaults: every row starts "pending_lanes"
        # with empty winners/alternatives/open_gaps -- the same shape the real
        # migrated catalogs.landscape.{foundation,us-equities}.json rows use.
        self.v2_defaults = {
            "verdict_status": "pending_lanes",
            "winners": [], "alternatives": [],
            "overturn_protocol": {"fixture_paths": [], "metric": "", "arms": []},
            "lanes": {"claude": {"run_id": "", "sealed_sha256": ""},
                      "codex": {"run_id": "", "sealed_sha256": ""}, "agreement": "pending"},
            "open_gaps": [],
            "checked_at": "2026-09-21",
        }
        self.layer = {
            "catalog": "foundation", "layer_id": "retrieval", "title": "Retrieval",
            "requirement": "Find the source", "current_choice": "Native selected tool",
            "decision": "keep_but_compare", "rationale": "Useful retained operation",
            "evidence_refs": ["guide.md"], "limitations": ["One input"],
            "overturn_when": "A matched task improves quality",
            "candidates": [self.candidate, {**self.candidate, "name": "Alternative",
                "repository": "https://github.com/example/alternative", "disposition": "unqualified",
                "evidence_kind": "source_review", "rationale": "Not tested on this host"}],
            **copy.deepcopy(self.v2_defaults),
        }
        self.foundation = {"schema_version": 2, "checked_at": "2026-09-21", "scope": "General",
                           "layers": [self.layer]}
        self.domain = copy.deepcopy(self.foundation)
        self.domain["layers"][0].update(catalog="us-equities", layer_id="data", title="Data",
                                        group="data-domain")
        self.write("foundation-manifest.json", {"layers": [{"id": "retrieval"}]})
        self.write("domain-manifest.json", {"catalog_files": ["data.json"]})
        self.write("data.json", {"layer": "data-domain", "checked_at": "2026-09-19", "entries": [{
            "id": "old", "repository": "https://github.com/example/alternative", "role": "Old source candidate",
            "decision": "default", "rationale": "Historical reason", "evidence_level": "source_review",
            "version_or_commit": "v1", "limitations": ["Historical only"], "evidence_refs": ["receipt.json"]}]})
        # The sota-pin check is scoped per layer_id (matching
        # tools/sota-convergence/build_verdicts.py's own sota_layer_index
        # join), so the taxonomy row's "layer" must equal self.layer's own
        # layer_id ("retrieval") for the pin-match tests below to exercise it.
        self.write("taxonomy.json", {"foundation": [{"layer": "retrieval", "components": [
            {"id": "selected", "pin": "1"}]}], "trading": [{"layer": "data", "entries": [
            {"id": "old-trading", "pin": "2"}]}]})
        self.write("adoption/manifest.json", {"recipe_map": {"selected-recipe": "recipes/example.md"}})
        self.write("index.json", {"aliases": {}, "records": [{"repository": row["repository"]}
                   for row in self.layer["candidates"]]})
        self.write("stack.json", {"components": [{"id": "selected", "version": "1",
                   "repository": self.candidate["repository"], "source_pin": "a" * 40}]})
        self.write("decisions.json", {"decisions": [{"review_status": "accepted_within_scope"}]})
        self.freshness = {"schema_version": 1, "scope": "Metadata only",
                          "components": [{"component_id": "selected", "selected_version": "1",
                                          "selected_repository_url": self.candidate["repository"],
                                          "selected_source_pin": "a" * 40}],
                          "stars": {"status": "checked", "repository_snapshot_count": 1,
                                    "repositories": [{"repository": self.candidate["repository"]}],
                                    "observed_identity_set_sha256": hashlib.sha256(self.candidate["repository"].encode()).hexdigest()}}
        self.write("freshness.json", self.freshness)
        self.write("receipt.json", {"exit_code": 0, "scope": "A local fixture, not upstream E2E"})
        (self.root / "guide.md").write_text("# Selection\n", encoding="utf-8")

    def write(self, path, value):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(value), encoding="utf-8")

    def build(self, **kwargs):
        self.write(MANIFEST, self.manifest)
        self.write("foundation.json", self.foundation)
        self.write("domain.json", self.domain)
        return build_landscape(self.root, **kwargs)

    def test_current_and_historical_choices_stay_separate_and_counts_are_derived(self):
        self.domain["layers"][0]["candidates"][0]["repository"] = "https://github.com/Example/SELECTED"
        data = self.build()
        self.assertEqual(data["counts"]["layers"], 2)
        self.assertEqual(data["counts"]["comparison_candidates"], 4)
        self.assertEqual(data["counts"]["comparison_repositories"], 2)
        self.assertEqual(data["counts"]["historical_candidate_cards"], 1)
        domain = data["layers"][1]
        self.assertEqual(domain["current_choice"], "Native selected tool")
        self.assertEqual(domain["catalog_candidates"][0]["decision"], "default")
        self.assertEqual(domain["catalog_candidates"][0]["checked_at"], "2026-09-19")
        self.assertEqual(domain["candidates"][1]["disposition"], "unqualified")

    def quality_fixture(self):
        self.manifest["sources"]["quality_review"] = "quality.json"
        self.manifest["handbook_guides"] = [{"path": "guide.md", "label": "Handbook"}]
        self.quality_url = "https://raw.githubusercontent.com/example/selected/" + "a" * 40 + "/README.md"
        self.write("quality-sources.json", {"scope": "Synthetic source record", "repositories": [{
            "repository": self.candidate["repository"], "revision": "a" * 40,
            "source_files": [{"url": self.quality_url, "bytes": 1, "sha256": "b" * 64}]}]})
        return {"schema_version": 1, "checked_at": "2026-09-21",
                "scope": "Source review, no execution claim", "no_universal_ranking": True,
                "claim_limits": ["Not a benchmark"], "source_snapshot": "quality-sources.json",
                "criteria": [{"id": "capability", "question": "Does it fit?"}],
                "candidates": [{"name": "Selected source", "repository": self.candidate["repository"],
                                "revision": "a" * 40, "disposition": "selected",
                                "evidence_kind": "source_review", "requirement_fit": "Source fits",
                                "source_findings": ["Documented capability"],
                                "qualification_gap": "No matched comparison",
                                "overturn_when": "An independently measured improvement",
                                "evidence_refs": ["receipt.json", self.quality_url],
                                "criteria": {"capability": {"finding": "Unknown on the new host",
                                                            "evidence_refs": []}}}],
                "layer_coverage": [{"catalog": c, "layer_id": l, "decision_ref": f + "#/layers/0",
                                    "decision": "keep_but_compare", "requirement": self.layer["requirement"],
                                    "current_choice": self.layer["current_choice"], "evidence_gap": "New host",
                                    "challenger_repositories": ["https://github.com/example/alternative"],
                                    "overturn_when": self.layer["overturn_when"]}
                                   for c, l, f in [("foundation", "retrieval", "foundation.json"),
                                                  ("us-equities", "data", "domain.json")]]}

    def test_quality_review_joins_sources_without_promoting_unknowns(self):
        quality = self.quality_fixture()
        self.write("quality.json", quality)
        tracked = []
        data = self.build(track=tracked.append)
        self.assertEqual(data["counts"]["quality_review_repositories"], 1)
        attached = data["layers"][0]["candidates"][0]["quality_review"]
        self.assertEqual(attached["criteria"]["capability"]["sources"], [])
        self.assertEqual(attached["evidence_kind"], "source_review")
        self.assertIn("quality-sources.json", tracked)
        self.assertIn("guide.md", tracked)

    def test_quality_review_rejects_false_execution_incomplete_coverage_and_unsafe_sources(self):
        quality = self.quality_fixture()
        cases = [
            (lambda q: q.update(no_universal_ranking=False), "unestablished universal"),
            (lambda q: q["candidates"][0].update(evidence_kind="native_execution"), "cannot certify execution"),
            (lambda q: q["candidates"][0].update(disposition="observed_failure"), "observed failure"),
            (lambda q: q["candidates"][0].update(revision="latest"), "full revision"),
            (lambda q: q["candidates"][0].update(revision="f" * 40), "revision differs from source snapshot"),
            (lambda q: q["candidates"][0].update(evidence_refs=[self.quality_url.replace("a" * 40, "f" * 40)]), "pinned sources differ"),
            (lambda q: q["candidates"][0].update(evidence_refs=[self.quality_url, self.quality_url]), "contains duplicates"),
            (lambda q: q["candidates"][0]["criteria"].clear(), "each declared criterion"),
            (lambda q: q["layer_coverage"].pop(), "every layer"),
            (lambda q: q["layer_coverage"][0].update(decision="retain"), "decision differs"),
            (lambda q: q["layer_coverage"][0].update(current_choice="Unrelated engine"), "current_choice differs"),
            (lambda q: q["layer_coverage"][0].update(requirement="Unrelated requirement"), "requirement differs"),
            (lambda q: q["layer_coverage"][0].update(overturn_when="Unrelated trigger"), "overturn_when differs"),
            (lambda q: q["layer_coverage"][0].update(challenger_repositories=["https://github.com/missing/repo"]), "absent from its layer"),
            (lambda q: q["candidates"][0].update(evidence_refs=["https://user:password@example.com/source"]), "unsafe source"),
        ]
        for change, message in cases:
            with self.subTest(message=message):
                mutated = copy.deepcopy(quality)
                change(mutated)
                self.write("quality.json", mutated)
                with self.assertRaisesRegex(ValueError, message):
                    self.build()

    def test_handbook_cannot_reference_files_outside_checkout(self):
        self.manifest["handbook_guides"] = [{"label": "Unsafe", "path": "../outside.md"}]
        with self.assertRaisesRegex(ValueError, "confined"):
            self.build()

    def test_missing_and_duplicate_layers_fail(self):
        self.domain["layers"] = []
        with self.assertRaisesRegex(ValueError, "exactly match"):
            self.build()
        self.foundation["layers"].append(copy.deepcopy(self.layer))
        with self.assertRaisesRegex(ValueError, "duplicate comparison"):
            self.build()

    def test_each_selected_component_needs_a_current_role_explanation(self):
        stack = json.loads((self.root / "stack.json").read_text())
        stack["components"][0]["repository"] = "https://github.com/example/unexplained"
        self.write("stack.json", stack)
        with self.assertRaisesRegex(ValueError, "lacks a current role explanation"):
            self.build()

    def test_research_queue_requires_complete_layers_safe_evidence_and_supported_closure(self):
        self.manifest["sources"]["research_state"] = "research.json"
        queue = {"schema_version": 1, "checked_at": "2026-09-21", "scope": "Bounded research",
                 "resume_order": ["Read one layer"], "guide": "guide.md",
                 "source_inventory_refs": ["receipt.json"],
                 "saturation": {"status": "not_established", "close_only_when": ["Frozen comparison"],
                                "reopen_on": ["Changed requirement"]},
                 "layers": [{"catalog": c, "layer_id": l, "status": "comparison_required",
                             "saturation": "not_established", "next_action": "Run matched comparison",
                             "decision_ref": path, "evidence_refs": ["receipt.json"]}
                            for c, l, path in [("foundation", "retrieval", "foundation.json"),
                                               ("us-equities", "data", "domain.json")]]}
        self.write("research.json", queue)
        data = self.build()
        self.assertEqual(data["counts"]["research_queue_layers"], 2)
        self.assertEqual(data["layers"][0]["research"]["next_action"], "Run matched comparison")
        for mutation in (lambda q: q["layers"].pop(),
                         lambda q: q["layers"].append(copy.deepcopy(q["layers"][0])),
                         lambda q: q["layers"][0].update(decision_ref="other.json"),
                         lambda q: q["layers"][0].update(evidence_refs=["../outside.json"]),
                         lambda q: q["layers"][0].update(status="bounded_review_complete", saturation="bounded_review_complete"),
                         lambda q: q["saturation"].update(status="bounded_review_complete", closure_refs=["receipt.json"])):
            broken = copy.deepcopy(queue)
            mutation(broken)
            self.write("research.json", broken)
            with self.assertRaises(ValueError):
                self.build()
        for item in queue["layers"]:
            item.update(status="bounded_review_complete", saturation="bounded_review_complete",
                        closure_refs=["receipt.json"], next_action="Monitor declared reopening trigger")
        queue["saturation"].update(status="bounded_review_complete", closure_refs=["receipt.json"])
        self.write("research.json", queue)
        self.assertEqual(self.build()["research_state"]["saturation"]["status"], "bounded_review_complete")

    def test_unknown_repository_and_duplicate_candidate_fail(self):
        self.candidate["repository"] = "https://github.com/example/missing"
        with self.assertRaisesRegex(ValueError, "absent from canonical index"):
            self.build()
        self.candidate["repository"] = "https://github.com/example/alternative"
        with self.assertRaisesRegex(ValueError, "duplicate candidate"):
            self.build()

    def test_source_review_cannot_be_promoted_to_an_observed_failure(self):
        alternative = self.layer["candidates"][1]
        alternative["disposition"] = "observed_failure"
        with self.assertRaisesRegex(ValueError, "needs execution evidence"):
            self.build()
        alternative["evidence_kind"] = "native_execution"
        alternative["evidence_refs"] = ["https://github.com/example/alternative"]
        with self.assertRaisesRegex(ValueError, "needs a retained local result"):
            self.build()

    def test_sources_are_confined_existing_and_safe(self):
        for path, message in [("missing.md", "file missing"), ("../outside.json", "confined"),
                              ("https://user:secret@example.com/file", "unsafe source URL"),
                              ("javascript:alert(1)", "confined")]:
            with self.subTest(path=path):
                self.layer["evidence_refs"] = [path]
                with self.assertRaisesRegex(ValueError, message):
                    self.build()
        (self.root / "alias.md").symlink_to(self.root / "guide.md")
        self.layer["evidence_refs"] = ["alias.md"]
        with self.assertRaisesRegex(ValueError, "symlinks"):
            self.build()

    def test_limits_alternatives_and_reopening_criteria_are_required(self):
        for field, value, message in [("limitations", [], "nonempty"),
                                      ("overturn_when", "", "nonempty"),
                                      ("candidates", [self.candidate], "named alternative")]:
            with self.subTest(field=field):
                prior = self.layer[field]
                self.layer[field] = value
                with self.assertRaisesRegex(ValueError, message):
                    self.build()
                self.layer[field] = prior

    def test_evidence_sources_are_added_to_explorer_hashes_and_links(self):
        tracked = set()
        data = self.build(track=tracked.add, file_url=lambda p: "https://example.com/" + p)
        self.assertTrue({"guide.md", "receipt.json"} <= tracked)
        self.assertEqual(data["layers"][0]["sources"][0]["url"], "https://example.com/guide.md")

    def test_universal_claim_and_mismatched_dates_are_rejected(self):
        self.manifest["universal_superiority"] = "proven"
        with self.assertRaisesRegex(ValueError, "universal-superiority"):
            self.build()
        self.manifest["universal_superiority"] = "not_established"
        self.foundation["checked_at"] = "2026-09-19"
        with self.assertRaisesRegex(ValueError, "review date differs"):
            self.build()

    def test_freshness_cannot_omit_components_or_change_the_star_identity_set(self):
        checked = self.freshness["components"]
        self.freshness["components"] = []
        self.write("freshness.json", self.freshness)
        with self.assertRaisesRegex(ValueError, "every selected component"):
            self.build()
        self.freshness["components"] = checked
        self.freshness["stars"]["observed_identity_set_sha256"] = "0" * 64
        self.write("freshness.json", self.freshness)
        with self.assertRaisesRegex(ValueError, "star identity hash"):
            self.build()

    def test_a_changed_source_pin_requires_fresh_corresponding_evidence(self):
        self.freshness["components"][0]["selected_source_pin"] = "b" * 40
        self.write("freshness.json", self.freshness)
        with self.assertRaisesRegex(ValueError, "selected source pin differs"):
            self.build()

    def test_native_skills_keep_source_pins_limits_and_local_evidence(self):
        self.manifest["sources"]["native_practice"] = "practice.json"
        skill = {"name": "semantic-skill", "repository": self.candidate["repository"],
                 "source_pin": "a" * 40, "skill_sha256": "b" * 64,
                 "rationale": "Selected scoped skill", "limits": ["No universal ranking"],
                 "evidence_refs": ["receipt.json"]}
        practice = {"schema_version": 1, "checked_at": self.manifest["checked_at"], "skills": [skill]}
        self.write("practice.json", practice)
        data = self.build()
        self.assertEqual(data["counts"]["applied_skills"], 1)
        self.assertEqual(data["native_practice"]["skills"][0]["sources"][0]["path"], "receipt.json")
        for key, value, message in [("source_pin", "main", "full source commit"),
                                    ("skill_sha256", "unknown", "content hash"),
                                    ("repository", "https://github.com/missing/skill", "absent from index"),
                                    ("limits", [], "needs limits"),
                                    ("evidence_refs", ["missing.json"], "file missing")]:
            with self.subTest(key=key):
                changed = copy.deepcopy(practice)
                changed["skills"][0][key] = value
                self.write("practice.json", changed)
                with self.assertRaisesRegex(ValueError, message):
                    self.build()
        practice["skills"].append(copy.deepcopy(skill))
        self.write("practice.json", practice)
        with self.assertRaisesRegex(ValueError, "duplicate selected skill"):
            self.build()

    def test_repository_transfers_use_aliases_but_unrelated_substitutions_fail(self):
        self.freshness["components"][0]["selected_repository_url"] = "https://github.com/previous/selected"
        self.write("freshness.json", self.freshness)
        with self.assertRaisesRegex(ValueError, "selected repository differs"):
            self.build()
        self.write("index.json", {"aliases": {"previous/selected": "example/selected"},
                   "records": [{"repository": row["repository"]} for row in self.layer["candidates"]]})
        self.assertEqual(self.build()["counts"]["selected_components"], 1)


class LayerVerdictSchemaV2Tests(LandscapeTests):
    """Schema v2 rules: verdict_status, winners/alternatives, overturn_protocol,
    lanes and the group-based binding of a domain document to every landscape
    row sharing its group. Each rule below has a passing and a failing case."""

    def recorded_fields(self, **overrides):
        fields = {
            "verdict_status": "recorded",
            "winners": [{
                "component_id": "selected", "repository": self.candidate["repository"],
                "pin": "1", "evidence_class": "native_proven",
                "why_selected": "Passed the native scoped operation",
                "evidence_refs": ["receipt.json"], "recipe_ref": "selected-recipe",
                "platform_status": {"linux-wsl2-x86_64": "accepted", "macos-arm64": "untested"},
            }],
            "alternatives": [{
                "name": "Alternative", "repository": "https://github.com/example/alternative",
                "disposition": "unqualified", "why_not_default": "Not tested on this host",
                "evidence_class": "source_review", "evidence_refs": [], "source": "discovery_index",
            }],
            "verdict_overturn_when": "python3 tests/test_landscape.py replays the comparison",
            "lanes": {"claude": {"run_id": "run-1", "sealed_sha256": SEALED_RUN_1_SHA256},
                      "codex": {"run_id": "", "sealed_sha256": ""}, "agreement": "codex_absent"},
        }
        fields.update(overrides)
        return fields

    def seal_claude_run(self, run_id="run-1"):
        self.write(f"evidence/artifacts/layer-verdicts-20260922/claude/{run_id}.json",
                   {"run_id": run_id, "lane": "claude"})

    def test_recorded_verdict_with_full_evidence_passes(self):
        self.seal_claude_run()
        self.layer.update(self.recorded_fields())
        data = self.build()
        self.assertEqual(data["layers"][0]["verdict_status"], "recorded")
        self.assertEqual(data["layers"][0]["winners"][0]["component_id"], "selected")

    def test_unknown_verdict_status_is_rejected(self):
        self.layer["verdict_status"] = "maybe"
        with self.assertRaisesRegex(ValueError, "verdict_status is unknown"):
            self.build()

    def test_recorded_verdict_needs_at_least_one_winner_and_one_alternative(self):
        self.seal_claude_run()
        self.layer.update(self.recorded_fields(winners=[]))
        with self.assertRaisesRegex(ValueError, "needs at least one winner"):
            self.build()
        self.layer.update(self.recorded_fields(alternatives=[]))
        with self.assertRaisesRegex(ValueError, "needs at least one alternative"):
            self.build()

    def test_why_selected_cannot_equal_an_alternatives_why_not_default(self):
        self.seal_claude_run()
        fields = self.recorded_fields()
        fields["winners"][0]["why_selected"] = fields["alternatives"][0]["why_not_default"]
        self.layer.update(fields)
        with self.assertRaisesRegex(ValueError, "must differ from every alternative"):
            self.build()

    def test_recorded_overturn_when_needs_a_fixture_or_command_marker(self):
        self.seal_claude_run()
        self.layer.update(self.recorded_fields(verdict_overturn_when="A vague future improvement"))
        with self.assertRaisesRegex(ValueError, "must name a fixture"):
            self.build()

    def test_winner_repository_must_resolve_in_the_canonical_index(self):
        self.seal_claude_run()
        fields = self.recorded_fields()
        fields["winners"][0]["repository"] = "https://github.com/example/missing"
        self.layer.update(fields)
        with self.assertRaisesRegex(ValueError, "winner.repository absent from canonical index"):
            self.build()

    def test_winner_repository_may_be_null(self):
        self.seal_claude_run()
        fields = self.recorded_fields()
        fields["winners"][0]["repository"] = None
        self.layer.update(fields)
        data = self.build()
        self.assertIsNone(data["layers"][0]["winners"][0]["repository"])

    def test_recipe_ref_must_not_be_empty_on_a_recorded_row(self):
        # Codex cross-family review of PR-2: an empty string used to skip resolution.
        self.seal_claude_run()
        fields = self.recorded_fields()
        fields["winners"][0]["recipe_ref"] = ""
        self.layer.update(fields)
        with self.assertRaisesRegex(ValueError, "recipe_ref"):
            self.build()

    def test_platform_status_vocabulary_is_per_platform(self):
        # Codex cross-family review of PR-2: macOS may only be untested on this profile
        # and Linux may not be untested.
        self.seal_claude_run()
        fields = self.recorded_fields()
        fields["winners"][0]["platform_status"] = {"linux-wsl2-x86_64": "accepted", "macos-arm64": "accepted"}
        self.layer.update(fields)
        with self.assertRaisesRegex(ValueError, "platform_status.macos-arm64"):
            self.build()
        fields = self.recorded_fields()
        fields["winners"][0]["platform_status"] = {"linux-wsl2-x86_64": "untested", "macos-arm64": "untested"}
        self.layer.update(fields)
        with self.assertRaisesRegex(ValueError, "platform_status.linux-wsl2-x86_64"):
            self.build()

    def test_recipe_ref_must_resolve_to_a_recipe_map_key_or_an_existing_path(self):
        self.seal_claude_run()
        fields = self.recorded_fields()
        fields["winners"][0]["recipe_ref"] = "recipes/unknown-nowhere.md"
        self.layer.update(fields)
        with self.assertRaisesRegex(ValueError, "recipe_ref must resolve"):
            self.build()
        fields["winners"][0]["recipe_ref"] = "guide.md"
        self.layer.update(fields)
        self.build()

    def test_winner_pin_must_match_the_sota_manifest_pin_for_a_known_component(self):
        self.seal_claude_run()
        fields = self.recorded_fields()
        fields["winners"][0]["pin"] = "2"
        self.layer.update(fields)
        with self.assertRaisesRegex(ValueError, "pin differs from the sota manifest pin"):
            self.build()

    def test_sota_pin_check_does_not_conflate_a_shared_component_id_across_layers(self):
        self.seal_claude_run()
        fields = self.recorded_fields()
        # A different layer ("data", the us-equities row) pins the same
        # component id to a different value; the winner check must use the
        # pin recorded for this row's own layer_id ("retrieval"), not
        # whichever layer happened to be read last while building a single
        # flattened component_id -> pin map (the fixed bug).
        self.write("taxonomy.json", {"foundation": [{"layer": "retrieval", "components": [
            {"id": "selected", "pin": "1"}]}], "trading": [{"layer": "data", "entries": [
            {"id": "selected", "pin": "9"}]}]})
        self.layer.update(fields)
        data = self.build()
        self.assertEqual(data["layers"][0]["winners"][0]["pin"], "1")

    def test_sealed_sha256_needs_a_retained_lane_file(self):
        self.layer.update(self.recorded_fields())
        with self.assertRaisesRegex(ValueError, "sealed_sha256 needs a sealed file"):
            self.build()

    def test_malformed_sealed_base_is_rejected(self):
        self.seal_claude_run()
        fields = self.recorded_fields()
        fields["lanes"]["sealed_base"] = "evidence/artifacts/layer-verdicts-2026-09-23"  # "-" not allowed
        self.layer.update(fields)
        with self.assertRaisesRegex(ValueError, "lanes.sealed_base must be evidence/artifacts/layer-verdicts"):
            self.build()

    def test_sealed_base_path_traversal_is_rejected(self):
        self.seal_claude_run()
        fields = self.recorded_fields()
        fields["lanes"]["sealed_base"] = "evidence/artifacts/layer-verdicts-../../etc"
        self.layer.update(fields)
        with self.assertRaisesRegex(ValueError, "lanes.sealed_base must be evidence/artifacts/layer-verdicts"):
            self.build()

    def test_a_later_wave_row_verifies_against_its_own_sealed_base_while_an_older_wave_stays_valid(self):
        # One row on the default (20260922, no sealed_base recorded) fallback and a second
        # row carrying an explicit sealed_base for a later wave both verify in the same build;
        # this is the "older sealed runs stay intact and verifiable" acceptance criterion.
        self.seal_claude_run()  # writes evidence/artifacts/layer-verdicts-20260922/claude/run-1.json
        # Register the second layer_id as a known foundation layer (foundation-manifest.json)
        # and give it a taxonomy pin entry matching the winner recorded below.
        self.write("foundation-manifest.json", {"layers": [{"id": "retrieval"}, {"id": "retrieval-2"}]})
        self.write("taxonomy.json", {"foundation": [
            {"layer": "retrieval", "components": [{"id": "selected", "pin": "1"}]},
            {"layer": "retrieval-2", "components": [{"id": "selected", "pin": "1"}]},
        ], "trading": [{"layer": "data", "entries": [{"id": "old-trading", "pin": "2"}]}]})
        later_sha = hashlib.sha256(json.dumps({"run_id": "run-2", "lane": "claude"}).encode("utf-8")).hexdigest()
        self.write("evidence/artifacts/layer-verdicts-20260923/claude/run-2.json",
                  {"run_id": "run-2", "lane": "claude"})
        later_layer = copy.deepcopy(self.layer)
        later_layer["layer_id"] = "retrieval-2"
        later_fields = self.recorded_fields(
            lanes={"claude": {"run_id": "run-2", "sealed_sha256": later_sha},
                   "codex": {"run_id": "", "sealed_sha256": ""}, "agreement": "codex_absent",
                   "sealed_base": "evidence/artifacts/layer-verdicts-20260923"})
        later_layer.update(later_fields)
        self.layer.update(self.recorded_fields())
        self.foundation["layers"].append(later_layer)
        data = self.build()
        foundation_ids = {row["layer_id"] for row in data["layers"] if row["catalog"] == "foundation"}
        self.assertEqual(foundation_ids, {"retrieval", "retrieval-2"})

        # Tampering with the older (20260922) sealed run's file still fails verification even
        # though a new (20260923) wave has since been recorded.
        (self.root / "evidence/artifacts/layer-verdicts-20260922/claude/run-1.json").write_text(
            json.dumps({"run_id": "run-1", "lane": "claude", "tampered": True}))
        with self.assertRaisesRegex(ValueError, "sealed_sha256 does not match"):
            self.build()

    def test_no_selection_needs_open_gaps(self):
        self.layer.update(self.recorded_fields(
            verdict_status="no_selection", winners=[], alternatives=[],
            lanes={"claude": {"run_id": "", "sealed_sha256": ""},
                   "codex": {"run_id": "", "sealed_sha256": ""}, "agreement": "pending"}))
        with self.assertRaisesRegex(ValueError, "no_selection verdict needs open_gaps"):
            self.build()
        self.layer["open_gaps"] = ["No qualified candidate reviewed yet"]
        self.build()

    def test_pending_rows_render_with_empty_winners_and_alternatives(self):
        data = self.build()
        self.assertEqual(data["layers"][0]["verdict_status"], "pending_lanes")
        self.assertEqual(data["layers"][0]["winners"], [])
        self.assertEqual(data["layers"][0]["alternatives"], [])

    def test_us_equities_row_needs_a_valid_domain_group(self):
        self.domain["layers"][0]["group"] = "unknown-domain"
        with self.assertRaisesRegex(ValueError, "group must be a domain document id"):
            self.build()

    def test_foundation_row_cannot_declare_a_group(self):
        self.foundation["layers"][0]["group"] = "data-domain"
        with self.assertRaisesRegex(ValueError, "group is only used for trading rows"):
            self.build()

    def test_domain_document_binds_through_group_to_every_matching_row(self):
        second_layer = copy.deepcopy(self.domain["layers"][0])
        second_layer.update(layer_id="second", title="Second")
        self.domain["layers"].append(second_layer)
        self.write("taxonomy.json", {"foundation": [{"layer": "native-clients", "components": [
            {"id": "selected", "pin": "1"}]}], "trading": [
            {"layer": "data", "entries": []}, {"layer": "second", "entries": []}]})
        data = self.build()
        us_layers = [row for row in data["layers"] if row["catalog"] == "us-equities"]
        self.assertEqual(len(us_layers), 2)
        for row in us_layers:
            self.assertEqual(len(row["catalog_candidates"]), 1)
            self.assertEqual(row["catalog_candidates"][0]["id"], "old")
        # One domain document, one historical card: fanning that same card
        # out onto every row sharing its group must not multiply the
        # published count (it must stay 1, not len(us_layers)).
        self.assertEqual(data["counts"]["historical_candidate_cards"], 1)

    def test_domain_document_must_map_to_at_least_one_row(self):
        # "data.json" (group "data-domain") still matches the row; "orphan.json"
        # (group "orphan-domain") has no landscape row using that group, so its
        # domain document cannot bind to anything.
        self.write("domain-manifest.json", {"catalog_files": ["data.json", "orphan.json"]})
        self.write("orphan.json", {"layer": "orphan-domain", "checked_at": "2026-09-19", "entries": [{
            "id": "old", "repository": "https://github.com/example/alternative", "role": "Old source candidate",
            "decision": "default", "rationale": "Historical reason", "evidence_level": "source_review",
            "version_or_commit": "v1", "limitations": ["Historical only"], "evidence_refs": ["receipt.json"]}]})
        with self.assertRaisesRegex(ValueError, "maps to no landscape row group"):
            self.build()

    def test_trading_layer_set_is_sourced_from_the_taxonomy_document_not_hardcoded(self):
        self.write("taxonomy.json", {"foundation": [], "trading": [{"layer": "renamed", "entries": []}]})
        self.domain["layers"][0]["layer_id"] = "renamed"
        data = self.build()
        self.assertEqual(data["layers"][1]["layer_id"], "renamed")


if __name__ == "__main__":
    unittest.main()
