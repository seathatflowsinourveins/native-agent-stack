"""Protect comparison coverage and evidence boundaries using local fixtures."""

import copy
import hashlib
import json
import re
from pathlib import Path
import tempfile
import unittest

from scripts.landscape import (MANIFEST, build_landscape, judge_adjudication, verify_sealed_waves,
                               withhold_policy_labels)
from scripts import platform_status


# Bytes the fixture writes for the sealed runs (self.write serializes with json.dumps).
SEALED_RUN_1_SHA256 = hashlib.sha256(json.dumps({"run_id": "run-1", "lane": "claude"}).encode("utf-8")).hexdigest()
SEALED_CODEX_RUN_1_SHA256 = hashlib.sha256(
    json.dumps({"run_id": "run-1", "lane": "codex"}).encode("utf-8")).hexdigest()
NEW_WAVE = "20260923"
NEW_WAVE_BASE = f"evidence/artifacts/layer-verdicts-{NEW_WAVE}"
# The evidence/ receipt a new-wave winner cites; seal_new_wave registers it in files[] (the only
# evidence scripts/platform_status.py counts toward a Linux "accepted").
NEW_WAVE_RECEIPT = "evidence/receipt.json"
# The refutation summary layer-verdict-lane.js returns for a final both lenses left unrefuted.
NEW_WAVE_REFUTATION = {
    "status": "unrefuted", "final_source": "proposal", "proposal_status": "unrefuted", "revision_status": None,
    "votes": [{"lens": "evidence", "round": "proposal", "refuted": False, "reason": "Every cited path holds."},
              {"lens": "challenger", "round": "proposal", "refuted": False, "reason": "No stronger candidate."}]}
NEW_WAVE_MODELS = {"claude": {"name": "claude-opus-5-5", "effort": "high", "family": "anthropic"},
                   "codex": {"name": "gpt-6-astra", "effort": "high", "family": "openai"}}
NEW_WAVE_PROVENANCE = {
    "claude": {"workflow_path": "examples/claude-native/workflows/layer-verdict-lane.js",
               "workflow_sha256": "a" * 64, "agentlab_commit": "b" * 40, "agent_sha256": "e" * 64},
    "codex": {"codex_lane_py_sha256": "c" * 64, "prompt_sha256": "d" * 64},
}
# The fixture's tools/sota-convergence/lane-provenance.json: the lane code above is registered.
NEW_WAVE_REGISTRY = {
    "claude": [{"workflow_path": "examples/claude-native/workflows/layer-verdict-lane.js",
                "vendored_path": "examples/claude-native/workflows/layer-verdict-lane.js",
                "workflow_sha256": "a" * 64, "agent_sha256": "e" * 64}],
    "codex": [{"codex_lane_py_sha256": "c" * 64, "prompt_sha256": "d" * 64}],
}

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
                      "codex": {"run_id": "run-1", "sealed_sha256": SEALED_CODEX_RUN_1_SHA256},
                      "agreement": "same_winner"},
        }
        lanes = overrides.get("lanes")
        if isinstance(lanes, dict) and lanes.get("sealed_base") == NEW_WAVE_BASE:
            # A new-wave row is held to scripts/platform_status.py on every platform.
            fields["winners"][0]["evidence_refs"] = ["receipt.json", NEW_WAVE_RECEIPT]
        fields.update(overrides)
        return fields

    def seal_claude_run(self, run_id="run-1"):
        """Seals both lanes of the grandfathered 2026-09-22 wave (a recorded row needs both
        families unless a single-lane decision record names it)."""
        for lane in ("claude", "codex"):
            self.write(f"evidence/artifacts/layer-verdicts-20260922/{lane}/{run_id}.json",
                       {"run_id": run_id, "lane": lane})

    def seal_new_wave(self, layer_id="retrieval", *, models=None, provenance=None, manifest_lanes=None,
                      register_receipt=True, codex_winner="c1", refutation=None, packet_extra=None):
        """A complete new-wave (20260923) row's sealed folder: the retained --withhold-labels packet
        (c1 the selected tool, c2 the alternative) and its SHA256SUMS, both sealed lane returns
        declaring their family, provenance, packet hash and winner keys (the claude return with its
        refutation summary; the codex return picks ``codex_winner``), the run manifest listing all of
        it, and the registered receipt its accepted winner cites. Returns the row's lanes field,
        bound to the run manifest; ``agreement`` is what the two returns establish."""
        models = models or NEW_WAVE_MODELS
        provenance = provenance or NEW_WAVE_PROVENANCE
        packet = {"schema_version": 1, "catalog": "foundation", "layer_id": layer_id, "requirement": "Find the source",
                  "candidates": [
                      {"key": "c1", "component_id": "selected", "repository": self.candidate["repository"],
                       "adopted": True, "upstream": {}},
                      {"key": "c2", "component_id": None, "repository": "https://github.com/example/alternative",
                       "adopted": True, "upstream": {}}],
                  "sota_components_not_in_candidates": [], "withheld": withhold_policy_labels("Find the source"),
                  **(packet_extra or {})}
        name = f"foundation__{layer_id}.json"
        self.write(f"{NEW_WAVE_BASE}/packets/{name}", packet)
        packet_sha256 = hashlib.sha256(json.dumps(packet).encode("utf-8")).hexdigest()
        sums = f"{packet_sha256}  {name}\n"
        (self.root / NEW_WAVE_BASE / "packets" / "SHA256SUMS").write_text(sums, encoding="utf-8")
        agreement = "same_winner" if codex_winner == "c1" else "disagree"
        lanes = {"agreement": agreement, "sealed_base": NEW_WAVE_BASE}
        manifest_entry_lanes = {}
        for lane in ("claude", "codex"):
            run_id = f"foundation-{layer_id}-{NEW_WAVE}"
            sealed = {"lane": lane, "model": models[lane], "packet_sha256": packet_sha256,
                      "winner_keys": ["c1"] if lane == "claude" else [codex_winner]}
            if provenance.get(lane) is not None:
                sealed["provenance"] = provenance[lane]
            if lane == "claude":
                sealed["refutation"] = copy.deepcopy(NEW_WAVE_REFUTATION if refutation is None else refutation)
            self.write(f"{NEW_WAVE_BASE}/{lane}/{run_id}.json", sealed)
            digest = hashlib.sha256(json.dumps(sealed).encode("utf-8")).hexdigest()
            lanes[lane] = {"run_id": run_id, "sealed_sha256": digest}
            manifest_entry_lanes[lane] = {"outcome": "sealed", "run_id": run_id, "sealed_sha256": digest}
        self.write(f"{NEW_WAVE_BASE}/run-manifest.json", {
            "schema_version": 1, "run_id": NEW_WAVE, "sealed_base": NEW_WAVE_BASE,
            "packets_sha256sums": sums, "retained_packets": [{"name": name, "sha256": packet_sha256}],
            "packets": [{"catalog": "foundation", "layer_id": layer_id, "packet_sha256": packet_sha256,
                         "lanes": manifest_lanes or manifest_entry_lanes}],
            "rejections": [],
        })
        self.bind_manifest(lanes)
        self.write(NEW_WAVE_RECEIPT, {"exit_code": 0, "scope": "A registered local fixture receipt"})
        if register_receipt:
            self.write("manifests/evidence.json", {"schema_version": 1, "receipts": [{"path": "receipt.json"}],
                                                   "files": [{"path": NEW_WAVE_RECEIPT}]})
        self.write("tools/sota-convergence/lane-provenance.json", {"schema_version": 1, **NEW_WAVE_REGISTRY})
        return lanes

    def bind_manifest(self, lanes):
        """Bind ``lanes`` to the run manifest now on disk (lanes.run_manifest_sha256)."""
        manifest = self.root / NEW_WAVE_BASE / "run-manifest.json"
        lanes["run_manifest_sha256"] = hashlib.sha256(manifest.read_bytes()).hexdigest()
        return lanes

    def edit_manifest(self, lanes, change):
        """Apply ``change`` to the run manifest on disk and re-bind ``lanes`` to it."""
        path = self.root / NEW_WAVE_BASE / "run-manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        change(manifest)
        self.write(f"{NEW_WAVE_BASE}/run-manifest.json", manifest)
        return self.bind_manifest(lanes)

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
        # Codex cross-family review of PR-2: Linux may not be untested, and macOS may not
        # claim more than its host receipts support (no receipts here, so not accepted).
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

    def test_macos_flip_needs_a_qualifying_host_receipt(self):
        # Peer-update audit (wf_77c0ea46-091) finding 1: macOS could never leave "untested".
        # The declared status may now rise to what scripts/platform_status.py derives.
        from scripts import host_receipts
        self.seal_claude_run()
        fields = self.recorded_fields()
        fields["winners"][0]["platform_status"] = {"linux-wsl2-x86_64": "accepted", "macos-arm64": "accepted"}
        self.layer.update(fields)
        with self.assertRaisesRegex(ValueError, "supports at most 'untested'"):
            self.build()
        (self.root / "adoption" / "host-receipt.schema.json").write_text(
            (Path(__file__).resolve().parents[1] / "adoption" / "host-receipt.schema.json").read_text(
                encoding="utf-8"), encoding="utf-8")
        recorder = {"identity_sha256": host_receipts.identity_digest("mac-recorder")}
        reviewer = {"identity_sha256": host_receipts.identity_digest("wsl-reviewer")}
        self.write("evidence/hosts/mac-20260923/mac-20260923--selected--use--20260923.json", {
            "schema_version": 1, "id": "mac-20260923--selected--use--20260923", "kind": "host_acceptance",
            "host": {"host_id": "mac-20260923", "platform_id": "macos-arm64", "os": "macos",
                     "architecture": "arm64", "second_physical_machine": True},
            "catalog_revision": "b" * 40, "recorded_by": recorder, "component_id": "selected", "stage": "use",
            "commands": [{"cmd": "selected --version", "exit": 0, "duration_s": 0.1,
                          "output_sha256": "0" * 64, "output_excerpt": "1"}],
            "tool_versions": {"selected": "1"}, "observed_at_utc": "2026-09-23T01:00:00Z", "result": "pass",
            "claim": "Ran on a Mac", "limitations": ["One command"], "evidence_class": "native_proven",
            "reviews": [
                {"kind": "self", "ref": "record", "verdict": "agree", "at_utc": "2026-09-23T01:00:00Z",
                 "reviewer": recorder},
                {"kind": "independent_session", "ref": "review", "verdict": "agree",
                 "at_utc": "2026-09-23T02:00:00Z", "reviewer": reviewer},
            ],
        })
        data = self.build()
        self.assertEqual(data["layers"][0]["winners"][0]["platform_status"]["macos-arm64"], "accepted")

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
        later_layer = copy.deepcopy(self.layer)
        later_layer["layer_id"] = "retrieval-2"
        later_fields = self.recorded_fields(lanes=self.seal_new_wave("retrieval-2"))
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

    # --- Layer-verdict integrity rules (2026-09-23 peer audit) -----------------------
    def test_single_lane_recorded_row_needs_a_dated_decision_record(self):
        self.write("evidence/artifacts/layer-verdicts-20260922/claude/run-1.json", {"run_id": "run-1", "lane": "claude"})
        single = {"claude": {"run_id": "run-1", "sealed_sha256": SEALED_RUN_1_SHA256},
                  "codex": {"run_id": "", "sealed_sha256": ""}, "agreement": "codex_absent"}
        self.layer.update(self.recorded_fields(lanes=copy.deepcopy(single)))
        with self.assertRaisesRegex(ValueError, "single_lane_decision"):
            self.build()
        (self.root / "docs/decisions").mkdir(parents=True)
        (self.root / "docs/decisions/undated.md").write_text("single-lane-authorization: foundation/retrieval\n",
                                                             encoding="utf-8")
        self.layer["lanes"]["single_lane_decision"] = "docs/decisions/undated.md"
        with self.assertRaisesRegex(ValueError, "dated"):
            self.build()
        record = self.root / "docs/decisions/2026-09-23-single-lane.md"
        record.write_text("Another layer only\n", encoding="utf-8")
        self.layer["lanes"]["single_lane_decision"] = "docs/decisions/2026-09-23-single-lane.md"
        with self.assertRaisesRegex(ValueError, "must carry the line 'single-lane-authorization: foundation/retrieval'"):
            self.build()
        # Naming the layer id is not an authorization, nor is the line for a longer layer id.
        record.write_text("Record `retrieval` alone\nsingle-lane-authorization: foundation/retrieval-2\n",
                          encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "must carry the line"):
            self.build()
        record.write_text("# Decision\n\nsingle-lane-authorization: foundation/retrieval\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "single_lane_decision_sha256 must be the sha256"):
            self.build()
        self.layer["lanes"]["single_lane_decision_sha256"] = hashlib.sha256(record.read_bytes()).hexdigest()
        self.build()

    # --- Review of catalog #122 (2026-09-23) ------------------------------------------------
    def test_a_single_lane_decision_outside_docs_decisions_or_edited_later_is_rejected(self):
        # Finding 2: any dated file mentioning the layer id authorized it (a wave document or the run
        # manifest named all 32 layers), and nothing bound the record's content to the row.
        self.write("evidence/artifacts/layer-verdicts-20260922/claude/run-1.json", {"run_id": "run-1", "lane": "claude"})
        lanes = {"claude": {"run_id": "run-1", "sealed_sha256": SEALED_RUN_1_SHA256},
                 "codex": {"run_id": "", "sealed_sha256": ""}, "agreement": "codex_absent"}
        text = b"Wave 2026-09-23 covers `retrieval`.\nsingle-lane-authorization: foundation/retrieval\n"
        (self.root / "docs").mkdir()
        (self.root / "docs/2026-09-23-wave.md").write_bytes(text)
        lanes.update(single_lane_decision="docs/2026-09-23-wave.md",
                     single_lane_decision_sha256=hashlib.sha256(text).hexdigest())
        self.layer.update(self.recorded_fields(lanes=lanes))
        with self.assertRaisesRegex(ValueError, "must be a decision record under docs/decisions/"):
            self.build()
        (self.root / "docs/decisions").mkdir()
        (self.root / "docs/decisions/2026-09-23-wave.md").write_bytes(text)
        self.layer["lanes"]["single_lane_decision"] = "docs/decisions/2026-09-23-wave.md"
        self.build()
        (self.root / "docs/decisions/2026-09-23-wave.md").write_bytes(text + b"Edited after recording.\n")
        with self.assertRaisesRegex(ValueError, "single_lane_decision_sha256"):
            self.build()

    def test_new_wave_row_with_full_integrity_evidence_passes(self):
        self.layer.update(self.recorded_fields(lanes=self.seal_new_wave()))
        self.assertEqual(self.build()["layers"][0]["verdict_status"], "recorded")

    def test_new_wave_sealed_lane_must_declare_a_matching_family(self):
        undeclared = copy.deepcopy(NEW_WAVE_MODELS)
        del undeclared["claude"]["family"]
        self.layer.update(self.recorded_fields(lanes=self.seal_new_wave(models=undeclared)))
        with self.assertRaisesRegex(ValueError, "model.family"):
            self.build()
        mismatched = copy.deepcopy(NEW_WAVE_MODELS)
        mismatched["codex"]["name"] = "claude-opus-5-5"
        self.layer.update(self.recorded_fields(lanes=self.seal_new_wave(models=mismatched)))
        with self.assertRaisesRegex(ValueError, "does not match"):
            self.build()

    def test_new_wave_sealed_lane_must_carry_provenance(self):
        self.layer.update(self.recorded_fields(lanes=self.seal_new_wave(
            provenance={"claude": NEW_WAVE_PROVENANCE["claude"], "codex": None})))
        with self.assertRaisesRegex(ValueError, "provenance"):
            self.build()

    def test_new_wave_row_must_appear_in_its_run_manifest_with_both_lanes(self):
        lanes = self.seal_new_wave()
        self.write(f"{NEW_WAVE_BASE}/run-manifest.json", {
            "schema_version": 1, "run_id": NEW_WAVE, "sealed_base": NEW_WAVE_BASE,
            "packets_sha256sums": "", "packets": [], "rejections": []})
        self.layer.update(self.recorded_fields(lanes=lanes))
        with self.assertRaisesRegex(ValueError, "run manifest"):
            self.build()
        self.seal_new_wave(manifest_lanes={"claude": lanes["claude"] | {"outcome": "sealed"}})
        with self.assertRaisesRegex(ValueError, "codex lane"):
            self.build()
        (self.root / NEW_WAVE_BASE / "run-manifest.json").unlink()
        with self.assertRaisesRegex(ValueError, "run manifest"):
            self.build()

    def test_new_wave_accepted_linux_status_needs_a_registered_receipt(self):
        self.layer.update(self.recorded_fields(lanes=self.seal_new_wave(register_receipt=False)))
        with self.assertRaisesRegex(ValueError, "linux-wsl2-x86_64 declares 'accepted'.*at most 'conditional'"):
            self.build()
        self.layer["winners"][0]["platform_status"]["linux-wsl2-x86_64"] = "conditional"
        self.build()

    def write_adjudication(self, base, run_id, families, winner_lane="claude", stripped_packet_sha256=None,
                           lanes=None):
        judgments = []
        for family in families:
            for claude_position in ("A", "B"):
                judgment = {"claude_position": claude_position, "preferred_position": claude_position,
                            "preferred_lane": winner_lane, "refuting_votes": 0}
                if family is not None:
                    judgment["judge"] = {"model": {"anthropic": "claude-opus-5-5", "openai": "gpt-6-astra"}[family],
                                         "family": family}
                    judgment["stripped_packet_sha256"] = stripped_packet_sha256 or self.packet_sha256()
                judgments.append(judgment)
        adjudication = {"winner_lane": winner_lane, "why": "Retained receipt decides it.",
                        "evidence_refs": ["receipt.json"], "judgments": judgments}
        self.write(f"{base}/adjudication/{run_id}.json", adjudication)
        if lanes is not None:
            digest = hashlib.sha256(json.dumps(adjudication).encode("utf-8")).hexdigest()
            lanes["adjudication_sha256"] = digest
            if base == NEW_WAVE_BASE and (self.root / NEW_WAVE_BASE / "run-manifest.json").is_file():
                # record_verdicts.py lists a sealed adjudication's sha256 in its manifest entry too.
                def seal(manifest):
                    for entry in manifest["packets"]:
                        if f"{entry['catalog']}-{entry['layer_id']}-{NEW_WAVE}" == run_id:
                            entry["adjudication"] = {"outcome": "sealed", "sha256": digest}
                self.edit_manifest(lanes, seal)

    def packet_sha256(self, layer_id="retrieval"):
        path = self.root / NEW_WAVE_BASE / "packets" / f"foundation__{layer_id}.json"
        return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "a" * 64

    def test_new_wave_disagree_row_needs_a_cross_family_adjudication(self):
        lanes = self.seal_new_wave(codex_winner="c2")
        self.assertEqual(lanes["agreement"], "disagree")
        self.layer.update(self.recorded_fields(lanes=lanes))
        with self.assertRaisesRegex(ValueError, "adjudication"):
            self.build()
        self.write_adjudication(NEW_WAVE_BASE, lanes["claude"]["run_id"], ("anthropic",), lanes=lanes)
        with self.assertRaisesRegex(ValueError, "both lane families"):
            self.build()
        self.write_adjudication(NEW_WAVE_BASE, lanes["claude"]["run_id"], ("anthropic", "openai"))
        with self.assertRaisesRegex(ValueError, "adjudication_sha256 does not match"):
            self.build()
        self.write_adjudication(NEW_WAVE_BASE, lanes["claude"]["run_id"], ("anthropic", "openai"), lanes=lanes)
        self.build()

    # --- Review findings (2026-09-23 fix round) -------------------------------------
    def test_new_wave_accepted_linux_status_cannot_cite_a_layer_verdict_artifact(self):
        # A lane's sealed return or a packet is a lane opinion or input, not an execution receipt,
        # even when manifests/evidence.json hash-registers it.
        lanes = self.seal_new_wave(register_receipt=False)
        sealed = f"{NEW_WAVE_BASE}/claude/{lanes['claude']['run_id']}.json"
        packet = "evidence/artifacts/layer-verdicts-20260922/packets/foundation__retrieval.json"
        self.write(packet, {"layer_id": "retrieval"})
        self.write("manifests/evidence.json", {"schema_version": 1, "receipts": [{"path": packet}],
                                               "files": [{"path": sealed}, {"path": packet}]})
        fields = self.recorded_fields(lanes=lanes)
        fields["winners"][0]["evidence_refs"] = [sealed, packet]
        self.layer.update(fields)
        with self.assertRaisesRegex(ValueError, "linux-wsl2-x86_64 declares 'accepted'.*at most 'conditional'"):
            self.build()
        # The shared rule itself excludes them, so component_matrix.py and the recorder agree.
        context = platform_status.load_context(self.root)
        self.assertEqual(platform_status.registered_evidence_refs(fields["winners"][0], context.registered_paths), ())
        self.assertEqual(platform_status.platform_status("linux-wsl2-x86_64", fields["winners"][0], context).status,
                         "conditional")

    # --- Re-review findings (2026-09-23) -----------------------------------------------
    def test_new_wave_macos_status_is_held_to_the_shared_rule(self):
        # A new-wave row is checked on every platform, not only ENFORCED_PLATFORMS.
        fields = self.recorded_fields(lanes=self.seal_new_wave())
        fields["winners"][0]["platform_status"]["macos-arm64"] = "conditional"
        self.layer.update(fields)
        with self.assertRaisesRegex(ValueError, "macos-arm64 declares 'conditional'.*at most 'untested'"):
            self.build()

    def test_a_hand_edited_new_wave_codex_absent_row_without_run_ids_is_rejected(self):
        # Re-review finding 2, case 1: the new-wave block ran only when some lane had a run_id.
        (self.root / "decisions").mkdir()
        (self.root / "decisions/2026-09-23-single-lane.md").write_text("Record `retrieval` alone\n",
                                                                     encoding="utf-8")
        lanes = {"claude": {"run_id": "", "sealed_sha256": ""}, "codex": {"run_id": "", "sealed_sha256": ""},
                 "agreement": "codex_absent", "sealed_base": NEW_WAVE_BASE,
                 "single_lane_decision": "decisions/2026-09-23-single-lane.md"}
        # The wave's run manifest (both lanes missing for this layer) and registry exist.
        self.seal_new_wave(manifest_lanes={"claude": {"outcome": "missing"}, "codex": {"outcome": "missing"}})
        self.bind_manifest(lanes)
        self.layer.update(self.recorded_fields(lanes=lanes))
        with self.assertRaisesRegex(ValueError, "codex_absent verdict needs the claude lane sealed"):
            self.build()
        # Same row in the grandfathered wave: the lane-seal rule for a recorded row still holds.
        lanes.pop("sealed_base")
        self.layer.update(self.recorded_fields(lanes=lanes))
        with self.assertRaisesRegex(ValueError, "codex_absent verdict needs the claude lane sealed"):
            self.build()

    def test_a_hand_edited_disagree_row_needs_both_lanes_sealed(self):
        # Re-review finding 2, case 2: an unsealed disagree row with only a claude run_id passed.
        lanes = self.seal_new_wave()
        lanes["agreement"] = "disagree"
        self.write_adjudication(NEW_WAVE_BASE, lanes["claude"]["run_id"], ("anthropic", "openai"))
        lanes["codex"] = {"run_id": "", "sealed_sha256": ""}
        # The run manifest agrees the codex lane is missing, so only the agreement rule can object.
        self.seal_new_wave(manifest_lanes={"claude": lanes["claude"] | {"outcome": "sealed"},
                                           "codex": {"outcome": "missing"}})
        self.bind_manifest(lanes)
        self.layer.update(self.recorded_fields(lanes=lanes))
        with self.assertRaisesRegex(ValueError, "disagree verdict needs both lanes sealed"):
            self.build()
        lanes["claude"]["sealed_sha256"] = ""
        self.layer.update(self.recorded_fields(lanes=lanes))
        with self.assertRaisesRegex(ValueError, "run_id exactly when it carries a sealed_sha256"):
            self.build()

    def test_a_run_id_naming_a_new_wave_gets_the_new_wave_rules_without_a_sealed_base(self):
        lanes = self.seal_new_wave()
        del lanes["sealed_base"]
        self.layer.update(self.recorded_fields(lanes=lanes))
        with self.assertRaisesRegex(ValueError, "run ids name wave\\(s\\) 20260923 but lanes.sealed_base names "
                                                "the grandfathered wave 20260922"):
            self.build()

    def test_a_new_wave_run_id_must_name_its_own_layer_and_wave(self):
        lanes = self.seal_new_wave()
        lanes["codex"]["run_id"] = "run-1"
        self.layer.update(self.recorded_fields(lanes=lanes))
        with self.assertRaisesRegex(ValueError, "codex.run_id must be 'foundation-retrieval-20260923'"):
            self.build()

    def test_a_unanimous_single_family_adjudication_is_a_split_whatever_its_winner_lane(self):
        # Re-review finding 3: winner_lane was validated before the two-family rule, so the
        # documented null was rejected as malformed instead of classified as a split.
        judgments = [{"claude_position": position, "preferred_position": position, "preferred_lane": "claude",
                      "refuting_votes": 0, "judge": {"model": "claude-opus-5-5", "family": "anthropic"},
                      "stripped_packet_sha256": "a" * 64} for position in ("A", "B")]
        for winner_lane in (None, "claude"):
            issue, result = judge_adjudication(
                {"winner_lane": winner_lane, "why": "Split.", "evidence_refs": [], "judgments": judgments},
                grandfathered=False, packet_sha256="a" * 64)
            self.assertIsNone(issue, winner_lane)
            self.assertIsNone(result["winner_lane"])
            self.assertIn("both lane families", result["split_reason"])
        issue, _ = judge_adjudication({"winner_lane": "codex", "why": "Split.", "evidence_refs": [],
                                       "judgments": judgments}, grandfathered=False, packet_sha256="a" * 64)
        self.assertIn("winner_lane 'codex'", issue)
        # A cross-family unanimous record still needs its lane named: null is not a winner.
        both = judgments + [dict(judgment, judge={"model": "gpt-6-astra", "family": "openai"})
                            for judgment in judgments]
        issue, _ = judge_adjudication({"winner_lane": None, "why": "x", "evidence_refs": [], "judgments": both},
                                      grandfathered=False, packet_sha256="a" * 64)
        self.assertIn("winner_lane None", issue)
        # The recorded row then reports the split, not a malformed adjudication.
        lanes = self.seal_new_wave()
        lanes["agreement"] = "disagree"
        self.write_adjudication(NEW_WAVE_BASE, lanes["claude"]["run_id"], ("anthropic",))
        path = self.root / NEW_WAVE_BASE / "adjudication" / f"{lanes['claude']['run_id']}.json"
        self.write(path.relative_to(self.root).as_posix(),
                   dict(json.loads(path.read_text(encoding="utf-8")), winner_lane=None))
        self.layer.update(self.recorded_fields(lanes=lanes))
        with self.assertRaisesRegex(ValueError, "is a split and cannot record a winner"):
            self.build()

    def test_new_wave_sealed_provenance_must_be_registered_lane_code(self):
        forged = {"claude": NEW_WAVE_PROVENANCE["claude"],
                  "codex": {"codex_lane_py_sha256": "9" * 64, "prompt_sha256": "d" * 64}}
        self.layer.update(self.recorded_fields(lanes=self.seal_new_wave(provenance=forged)))
        with self.assertRaisesRegex(ValueError, "not listed in tools/sota-convergence/lane-provenance.json"):
            self.build()
        moved = {"claude": dict(NEW_WAVE_PROVENANCE["claude"], workflow_path="elsewhere/layer-verdict-lane.js"),
                 "codex": NEW_WAVE_PROVENANCE["codex"]}
        self.layer.update(self.recorded_fields(lanes=self.seal_new_wave(provenance=moved)))
        with self.assertRaisesRegex(ValueError, "claude.*not listed"):
            self.build()

    def test_new_wave_judgments_must_name_the_rows_sealed_packet(self):
        lanes = self.seal_new_wave()
        lanes["agreement"] = "disagree"
        self.layer.update(self.recorded_fields(lanes=lanes))
        self.write_adjudication(NEW_WAVE_BASE, lanes["claude"]["run_id"], ("anthropic", "openai"),
                                stripped_packet_sha256="e" * 64)
        with self.assertRaisesRegex(ValueError, "sealed packet sha256"):
            self.build()

    # --- Review of catalog #122 (2026-09-23): the row must be what its sealed wave establishes ----
    def recorded_disagreement(self):
        """A new-wave disagree row recorded from a cross-family adjudication for the claude lane."""
        lanes = self.seal_new_wave(codex_winner="c2")
        self.write_adjudication(NEW_WAVE_BASE, lanes["claude"]["run_id"], ("anthropic", "openai"), lanes=lanes)
        self.layer.update(self.recorded_fields(lanes=lanes))
        self.build()
        return lanes

    def test_relabelling_a_disagree_row_as_same_winner_fails(self):
        # Finding 1: run_manifest_row_issue compared hashes only, so the agreement was never
        # recomputed from the sealed returns and a disagreement could be relabelled away.
        lanes = self.recorded_disagreement()
        lanes["agreement"] = "same_winner"
        lanes.pop("adjudication_sha256")
        # A thorough editor also drops the manifest's adjudication binding; the recomputed agreement
        # still objects.
        self.edit_manifest(lanes, lambda manifest: manifest["packets"][0].pop("adjudication"))
        with self.assertRaisesRegex(ValueError, "agreement 'same_winner' is not what its sealed returns establish "
                                                "\\('disagree'"):
            self.build()

    def test_swapping_in_the_losing_lanes_winners_fails(self):
        # Finding 1: winner_keys were never read, so the codex lane's winners could stand on a row
        # whose adjudication chose the claude lane.
        self.recorded_disagreement()
        fields = self.recorded_fields(lanes=self.layer["lanes"])
        fields["winners"][0].update(component_id="candidate:example-alternative",
                                    repository="https://github.com/example/alternative")
        fields["alternatives"][0].update(name="Native selected tool", repository=self.candidate["repository"])
        self.layer.update(fields)
        with self.assertRaisesRegex(ValueError, "are not the claude lane's sealed winner set \\['selected'\\]"):
            self.build()

    def test_a_same_winner_row_must_carry_the_lanes_winners_and_a_pending_row_none(self):
        lanes = self.seal_new_wave()
        fields = self.recorded_fields(lanes=lanes)
        fields["winners"].append(dict(fields["winners"][0], component_id="extra", repository=None))
        self.layer.update(fields)
        with self.assertRaisesRegex(ValueError, "are not the claude lane's sealed winner set"):
            self.build()
        self.layer.update(self.recorded_fields(lanes=lanes), verdict_status="pending_lanes")
        with self.assertRaisesRegex(ValueError, "not recorded carries no winners"):
            self.build()

    def test_a_sealed_return_must_name_the_retained_packet(self):
        lanes = self.seal_new_wave()
        packet = self.root / NEW_WAVE_BASE / "packets" / "foundation__retrieval.json"
        packet.write_text(packet.read_text(encoding="utf-8") + " ", encoding="utf-8")
        self.layer.update(self.recorded_fields(lanes=lanes))
        with self.assertRaisesRegex(ValueError, "needs its retained packet"):
            self.build()
        packet.unlink()
        with self.assertRaisesRegex(ValueError, "needs its retained packet"):
            self.build()

    def test_the_row_is_bound_to_its_run_manifest(self):
        # Finding 3: the run manifest was not hash-bound, so a re-run could rewrite it (and drop a
        # dissent) under an unchanged row.
        lanes = self.seal_new_wave()
        self.layer.update(self.recorded_fields(lanes=lanes))
        self.build()
        path = self.root / NEW_WAVE_BASE / "run-manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["rejections"] = []
        manifest["generated_by"] = "a re-run"
        self.write(f"{NEW_WAVE_BASE}/run-manifest.json", manifest)
        with self.assertRaisesRegex(ValueError, "run_manifest_sha256 must be the sha256 of its run manifest"):
            self.build()
        del lanes["run_manifest_sha256"]
        with self.assertRaisesRegex(ValueError, "run_manifest_sha256"):
            self.build()

    def test_a_file_no_row_or_run_manifest_references_is_rejected(self):
        # Finding 3: an orphaned sealed return (a dissent the row no longer names) or a stray
        # adjudication stayed in the sealed folder unnoticed.
        lanes = self.seal_new_wave()
        self.layer.update(self.recorded_fields(lanes=lanes))
        self.build()
        for stray in ("codex/foundation-retrieval-old.json", f"adjudication/{lanes['claude']['run_id']}.json",
                      "packets/foundation__other.json", "notes.txt"):
            self.write(f"{NEW_WAVE_BASE}/{stray}", {"stray": True})
            with self.assertRaisesRegex(ValueError, "referenced by no ledger row and not by the run manifest"):
                self.build()
            (self.root / NEW_WAVE_BASE / stray).unlink()
        self.build()
        # A sealed folder without a run manifest is rejected as a whole.
        (self.root / "evidence/artifacts/layer-verdicts-20260930/claude").mkdir(parents=True)
        self.write("evidence/artifacts/layer-verdicts-20260930/claude/x.json", {})
        with self.assertRaisesRegex(ValueError, "layer-verdicts-20260930 has no run-manifest.json"):
            self.build()

    def test_a_sealed_claude_return_with_a_refuted_or_unknown_final_is_rejected(self):
        # Finding 5: the lane sealed a refuted proposal (final fell back to it) and counted a missing
        # vote as unrefuted; CI now reads the refutation summary the lane returns.
        refuted = copy.deepcopy(NEW_WAVE_REFUTATION)
        refuted.update(status="refuted", final_source=None, proposal_status="refuted")
        refuted["votes"][0]["refuted"] = True
        unknown = copy.deepcopy(NEW_WAVE_REFUTATION)
        unknown["votes"][1].update(refuted=None, reason="no vote returned")
        one_vote = copy.deepcopy(NEW_WAVE_REFUTATION)
        one_vote["votes"] = one_vote["votes"][:1]
        for refutation, message in ((refuted, "refutation.status is 'refuted'"),
                                    (unknown, "both lens votes .* on the sealed proposal"),
                                    (one_vote, "both lens votes"),
                                    ({}, "refutation.status is None")):
            self.layer.update(self.recorded_fields(lanes=self.seal_new_wave(refutation=refutation)))
            with self.assertRaisesRegex(ValueError, message):
                self.build()
        revised = copy.deepcopy(NEW_WAVE_REFUTATION)
        revised.update(final_source="revision", proposal_status="refuted", revision_status="unrefuted")
        revised["votes"] = ([dict(vote, round="proposal", refuted=True) for vote in revised["votes"][:1]]
                            + [dict(vote, round="revision") for vote in revised["votes"]])
        self.layer.update(self.recorded_fields(lanes=self.seal_new_wave(refutation=revised)))
        self.build()

    def test_retained_packets_carry_no_withheld_key(self):
        # Finding 6: new-wave packets were not retained, so the no-stars/no-pushed_at claim could not
        # be checked; the retained packets are now re-read in CI.
        lanes = self.seal_new_wave(packet_extra={"sota_components_not_in_candidates": [
            {"id": "x", "upstream": {"latest": "1.0", "pushed_at": "2026-09-01"}, "newcomer": True}]})
        self.layer.update(self.recorded_fields(lanes=lanes))
        with self.assertRaisesRegex(ValueError, "carries withheld keys \\['sota_components_not_in_candidates\\[\\]"
                                                "\\.newcomer', .*upstream\\.latest', .*upstream\\.pushed_at'\\]"):
            self.build()
        sums = self.root / NEW_WAVE_BASE / "packets" / "SHA256SUMS"
        self.layer.update(self.recorded_fields(lanes=self.seal_new_wave()))
        self.build()
        sums.write_text(sums.read_text(encoding="utf-8") + "0" * 64 + "  foundation__other.json\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "SHA256SUMS must be retained and equal"):
            self.build()

    def test_retained_packets_with_gap_receipts_are_refused(self):
        # Round-2 review: a blind wave cannot seal packets built with lane_packets.py --gap-receipts.
        lanes = self.seal_new_wave(packet_extra={"gap_receipts": ["evidence/artifacts/gap-wave2/x/0-check.json"],
                                                 "gap_receipts_note": "gap_receipts lists receipts"})
        self.layer.update(self.recorded_fields(lanes=lanes))
        with self.assertRaisesRegex(ValueError, "carries withheld keys \\['gap_receipts', 'gap_receipts_note'\\]"):
            self.build()

    def test_retained_packets_are_checked_at_every_depth(self):
        # Review of the #122 fix round: CI only looked where withhold_popularity strips, so a nested
        # release date, a top-level newcomers list or a disposition label passed.
        c1 = {"key": "c1", "component_id": "selected", "repository": self.candidate["repository"],
              "adopted": True, "review_status": None, "upstream": {}}
        c2 = {"key": "c2", "component_id": None, "repository": "https://github.com/example/alternative",
              "adopted": True, "review_status": None, "upstream": {}}
        cases = {
            "candidates[].upstream.latest_flag": {"candidates": [
                c1, dict(c2, upstream={"latest_flag": {"tag": "release/2025-11-28"}})]},
            "candidates[].evidence.stars": {"candidates": [c1, dict(c2, evidence={"stars": 9})]},
            "candidates[].review_status": {"candidates": [c1, dict(c2, review_status="confirmed_default")]},
            "candidates[].decisions[].selection": {"candidates": [
                c1, dict(c2, decisions=[{"id": "d1", "selection": "default"}])]},
            "newcomers": {"newcomers": ["c2"]},
            "withheld[] lacks candidates[].upstream.stars": {"withheld": ["candidates[].upstream.forks"]},
        }
        for label, extra in cases.items():
            with self.subTest(label):
                self.layer.update(self.recorded_fields(lanes=self.seal_new_wave(packet_extra=extra)))
                with self.assertRaisesRegex(ValueError, "carries withheld keys .*" + re.escape(label)):
                    self.build()
        self.layer.update(self.recorded_fields(lanes=self.seal_new_wave(packet_extra={"candidates": [c1, c2]})))
        self.build()

    def test_a_sealed_adjudication_is_bound_by_the_run_manifest(self):
        # Review of the #122 fix round: only the row's lanes.adjudication_sha256 bound an adjudication,
        # so rewriting it (and its winner_lane) needed one row edit; the manifest now lists it too.
        lanes = self.recorded_disagreement()
        manifest = json.loads((self.root / NEW_WAVE_BASE / "run-manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["packets"][0]["adjudication"],
                         {"outcome": "sealed", "sha256": lanes["adjudication_sha256"]})
        path = self.root / NEW_WAVE_BASE / "adjudication" / f"{lanes['claude']['run_id']}.json"
        rewritten = dict(json.loads(path.read_text(encoding="utf-8")), why="A rewritten reason.")
        self.write(path.relative_to(self.root).as_posix(), rewritten)
        lanes["adjudication_sha256"] = hashlib.sha256(json.dumps(rewritten).encode("utf-8")).hexdigest()
        with self.assertRaisesRegex(ValueError, "run manifest's sealed adjudication of foundation/retrieval .* differs "
                                                "from the row's lanes.adjudication_sha256"):
            self.build()
        # The wave check re-hashes the file against the manifest entry as it does a sealed return.
        lanes["adjudication_sha256"] = manifest["packets"][0]["adjudication"]["sha256"]
        self.layer["lanes"] = lanes
        with self.assertRaisesRegex(ValueError, "adjudication_sha256 does not match"):
            self.build()
        with self.assertRaisesRegex(ValueError, "wave 20260923: sealed adjudication adjudication/foundation-retrieval-"
                                                "20260923.json differs from its run-manifest sha256"):
            verify_sealed_waves(self.root, {})

    def test_a_layer_verdicts_folder_no_row_can_name_is_rejected(self):
        # Review of the #122 fix round: evidence/artifacts/layer-verdicts-<id> with a non-alphanumeric
        # id was skipped silently, so sealed-looking files could sit there unchecked.
        self.layer.update(self.recorded_fields(lanes=self.seal_new_wave()))
        self.build()
        self.write("evidence/artifacts/layer-verdicts-2026-09-24/claude/foundation-retrieval.json", {"lane": "claude"})
        with self.assertRaisesRegex(ValueError, "layer-verdicts-2026-09-24 is not a sealed wave folder"):
            self.build()

    def test_a_failed_lane_outcome_carries_its_reason(self):
        # Finding 7: a lane that ran and failed was recorded as a bare "missing".
        lanes = self.seal_new_wave()
        (self.root / NEW_WAVE_BASE / "codex" / f"{lanes['codex']['run_id']}.json").unlink()
        lanes.update(codex={"run_id": "", "sealed_sha256": ""}, agreement="codex_absent")

        def failed(reasons):
            def change(manifest):
                manifest["packets"][0]["lanes"]["codex"] = {"outcome": "failed", **reasons}
            return change

        self.edit_manifest(lanes, failed({}))
        self.layer.update(self.recorded_fields(lanes=lanes, verdict_status="pending_lanes", winners=[],
                                               alternatives=[]))
        with self.assertRaisesRegex(ValueError, "failed codex lane of foundation/retrieval needs its reasons"):
            self.build()
        self.edit_manifest(lanes, failed({"reasons": ["failed after retry: timed out"]}))
        self.build()

    def test_grandfathered_disagree_row_keeps_the_single_family_two_order_rule(self):
        self.seal_claude_run()
        self.layer.update(self.recorded_fields())
        self.layer["lanes"]["agreement"] = "disagree"
        with self.assertRaisesRegex(ValueError, "adjudication"):
            self.build()
        # The 2026-09-22 adjudications carry no judge identity: both orders suffice there.
        self.write_adjudication("evidence/artifacts/layer-verdicts-20260922", "run-1", (None,))
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
