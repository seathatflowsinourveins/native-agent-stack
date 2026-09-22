"""Synthetic-fixture tests for tools/sota-convergence. No network, no real catalogs.

Modules are loaded by file path (tools/sota-convergence is not a dotted-import
package name) and skipped cleanly if a required stdlib module is unexpectedly
absent from the interpreter under test.
"""
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL_DIR = ROOT / "tools" / "sota-convergence"


def load_module(name, filename):
    path = TOOL_DIR / filename
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except ModuleNotFoundError as exc:  # pragma: no cover - defensive, stdlib only expected
        raise unittest.SkipTest(f"{filename} needs an absent module: {exc}")
    return module


extract_layers = load_module("extract_layers", "extract_layers.py")
build_manifest_mod = load_module("build_manifest", "build_manifest.py")


class TaxonomyExtractionTests(unittest.TestCase):
    def test_zero_unmapped_tags_for_a_fully_covered_fixture(self):
        taxonomy = {
            "market-data-reference": ["market-data", "reference-data"],
            "backtesting-engine": ["backtesting", "execution-engine"],
        }
        entries = [
            {"id": "a", "layers": ["market-data"]},
            {"id": "b", "layers": ["reference-data", "backtesting"]},
            {"id": "c", "layers": ["execution-engine"]},
        ]
        tag_map = extract_layers.tag_to_layers_map(taxonomy)
        self.assertEqual(extract_layers.unmapped_tags(entries, tag_map), [])

    def test_unmapped_tag_is_reported(self):
        taxonomy = {"market-data-reference": ["market-data"]}
        entries = [{"id": "a", "layers": ["market-data", "some-unknown-tag"]}]
        tag_map = extract_layers.tag_to_layers_map(taxonomy)
        self.assertEqual(extract_layers.unmapped_tags(entries, tag_map), ["some-unknown-tag"])

    def test_trading_by_layer_consolidates_fine_grained_tags(self):
        taxonomy = {"backtesting-engine": ["backtesting", "execution-engine"], "portfolio-risk": ["risk"]}
        catalog = {"entries": [
            {"id": "engine-x", "repository": "https://github.com/example/engine-x", "layers": ["backtesting"]},
            {"id": "risk-y", "repository": "https://github.com/example/risk-y", "layers": ["risk"]},
            {"id": "both-z", "repository": "https://github.com/example/both-z", "layers": ["execution-engine", "risk"]},
        ]}
        by_layer = extract_layers.build_trading_by_layer(catalog, taxonomy)
        self.assertEqual({e["id"] for e in by_layer["layers"]["backtesting-engine"]}, {"engine-x", "both-z"})
        self.assertEqual({e["id"] for e in by_layer["layers"]["portfolio-risk"]}, {"risk-y", "both-z"})

    def test_foundation_layers_group_decisions_and_sort_components(self):
        manifest = {"layers": [{"id": "native-clients", "title": "Native clients"}], "top_gaps": []}
        decisions_doc = {"checked_at": "2026-01-01", "decisions": [
            {"id": "d1", "capability": "c", "selection": "default", "review_status": "accepted_within_scope",
             "layer_ids": ["native-clients"], "component_ids": ["zeta", "alpha"], "activation": "a",
             "candidate": None, "evidence_ids": []},
        ]}
        stack = {"components": [
            {"id": "zeta", "repository": "https://github.com/example/zeta", "version": "1.0", "license": "MIT",
             "role": "r", "profile": "core"},
            {"id": "alpha", "repository": "https://github.com/example/alpha", "version": "1.0", "license": "MIT",
             "role": "r", "profile": "core"},
        ]}
        result = extract_layers.build_foundation_layers(manifest, decisions_doc, stack)
        self.assertEqual(len(result["layers"]), 1)
        layer = result["layers"][0]
        self.assertEqual([c["id"] for c in layer["components"]], ["alpha", "zeta"])
        self.assertEqual(len(layer["decisions"]), 1)


class FreshnessParsingTests(unittest.TestCase):
    def test_missing_release_falls_back_to_latest_tag(self):
        repositories = {"https://github.com/example/tagged-only": {"latest_tag": "v3.2.0", "pushed_at": "2026-01-01T00:00:00Z"}}
        upstream = build_manifest_mod.compute_upstream("https://github.com/example/tagged-only", repositories)
        self.assertEqual(upstream["latest"], "v3.2.0")

    def test_rename_is_carried_through(self):
        repositories = {"https://github.com/old/name": {"renamed_to": "new/name",
                                                          "latest_release": {"tag": "v1.0.0"}}}
        upstream = build_manifest_mod.compute_upstream("https://github.com/old/name", repositories)
        self.assertEqual(upstream["renamed_to"], "new/name")

    def test_unknown_repository_does_not_crash(self):
        upstream = build_manifest_mod.compute_upstream("https://github.com/nowhere/absent", {})
        self.assertIsNone(upstream["latest"])
        self.assertIsNone(upstream["renamed_to"])


class PinVsUpstreamRuleTests(unittest.TestCase):
    def test_older_pin_counts_as_behind(self):
        result = build_manifest_mod.classify_pin("2.3.2", "https://github.com/akitaonrails/ai-memory", "v2.4.0")
        self.assertTrue(result["behind"])
        self.assertFalse(result["excluded"])

    def test_commit_pin_is_not_counted_even_when_ahead(self):
        result = build_manifest_mod.classify_pin("2.0.0.dev0 (c6fbd1c)", "https://github.com/oraios/serena", "v1.7.0")
        self.assertFalse(result["behind"])
        self.assertTrue(result["excluded"])
        self.assertEqual(result["reason"], "commit_pinned")

    def test_non_github_component_is_excluded(self):
        result = build_manifest_mod.classify_pin("255.4-1ubuntu8.17", None, None)
        self.assertFalse(result["behind"])
        self.assertTrue(result["excluded"])
        self.assertEqual(result["reason"], "non_github_or_os_package")

    def test_equal_versions_are_not_behind(self):
        result = build_manifest_mod.classify_pin("2.0.0", "https://github.com/example/x", "v2.0.0")
        self.assertFalse(result["behind"])
        self.assertFalse(result["excluded"])


class DispositionMappingTests(unittest.TestCase):
    CASES = {
        ("not_adopted", None): "not_adopted_unverified",
        ("not_adopted", False): "refuted_not_adopted",
        ("not_adopted", True): "not_adopted_confirmed",
        ("keep_but_compare", None): "keep_but_compare_unverified",
        ("keep_but_compare", False): "refuted_keep_but_compare",
        ("keep_but_compare", True): "keep_but_compare",
        ("targeted_candidate", None): "targeted_candidate_unverified",
        ("targeted_candidate", False): "refuted_targeted_candidate",
        ("targeted_candidate", True): "targeted_candidate",
    }

    def test_every_label_survives_pair(self):
        for (label, survives), expected in self.CASES.items():
            with self.subTest(label=label, survives=survives):
                self.assertEqual(build_manifest_mod.disposition(label, survives), expected)

    def test_unknown_label_passes_through_when_it_survives(self):
        self.assertEqual(build_manifest_mod.disposition("unlabelled-thing", True), "unlabelled-thing")

    def test_missing_label_survives_is_labelled(self):
        self.assertEqual(build_manifest_mod.disposition(None, True), "unlabelled")


class SanitizerTests(unittest.TestCase):
    def test_sanitize_removes_host_paths(self):
        text = 'note: "/home/example/code/native-agent-stack/state/x.json" was read'
        cleaned = build_manifest_mod.sanitize(text)
        self.assertNotIn("/home/", cleaned)
        self.assertIn("<host-path>", cleaned)

    def test_writer_refuses_when_a_leak_survives_sanitization(self):
        # sanitize() only strips /home/ paths; a literal secret-prefix marker
        # like an Alpaca key survives it, and the writer must refuse.
        leaking = build_manifest_mod.sanitize('{"note": "APCA1234567890ABCDEF"}')
        with self.assertRaises(build_manifest_mod.LeakDetected):
            build_manifest_mod.assert_no_leak(leaking)

    def test_writer_accepts_clean_text(self):
        clean = build_manifest_mod.sanitize('{"note": "no secrets or host paths here"}')
        build_manifest_mod.assert_no_leak(clean)  # must not raise


class CountsReconcileTests(unittest.TestCase):
    def build_fixture_manifest(self):
        foundation_layers = {
            "checked_at": "2026-01-01",
            "layers": [{
                "layer_id": "layer-a", "title": "Layer A", "summary": "", "decisions": [],
                "components": [
                    {"id": "comp-old", "repository": "https://github.com/example/comp-old",
                     "version": "1.0.0", "license": "MIT", "role": "r", "profile": "core"},
                    {"id": "comp-current", "repository": "https://github.com/example/comp-current",
                     "version": "2.0.0", "license": "MIT", "role": "r", "profile": "core"},
                    {"id": "comp-commit", "repository": "https://github.com/example/comp-commit",
                     "version": "2.0.0.dev0 (abc1234)", "license": "MIT", "role": "r", "profile": "core"},
                    {"id": "systemd", "repository": None, "version": "255.4",
                     "license": "GPL", "role": "scheduler", "profile": "optional"},
                ],
            }],
            "top_gaps": [],
        }
        # A distinct layer id from foundation's "layer-a": real foundation (16 ids)
        # and trading (12 ids) taxonomies never collide, and lane candidates below
        # are keyed only by layer id, so a shared id here would double-count them.
        trading_by_layer = {
            "taxonomy": {"layer-b": ["tag-a"]},
            "layers": {"layer-b": [
                {"id": "trade-old", "repository": "https://github.com/example/trade-old",
                 "decision": "default", "version_or_commit": "1.0.0", "layers": ["tag-a"]},
            ]},
        }
        freshness_doc = {
            "count": 4, "generated_at": "2026-01-02T00:00:00+00:00",
            "repositories": {
                "https://github.com/example/comp-old": {
                    "latest_release": {"tag": "v1.5.0", "published_at": "2026-01-01T00:00:00Z", "prerelease": False},
                    "pushed_at": "2026-01-01T00:00:00Z", "stargazers_count": 10, "license": "MIT", "archived": False},
                "https://github.com/example/comp-current": {
                    "latest_tag": "v2.0.0", "pushed_at": "2026-01-01T00:00:00Z", "stargazers_count": 5,
                    "license": "MIT", "archived": False},
                "https://github.com/example/comp-commit": {
                    "latest_release": {"tag": "v1.7.0", "published_at": "2025-01-01T00:00:00Z"},
                    "pushed_at": "2025-01-01T00:00:00Z", "stargazers_count": 1, "license": "MIT", "archived": False},
                "https://github.com/example/trade-old": {
                    "full_name": "example/trade-new", "renamed_to": "example/trade-new",
                    "latest_release": {"tag": "v1.1.0", "published_at": "2026-01-01T00:00:00Z"},
                    "pushed_at": "2026-01-01T00:00:00Z", "stargazers_count": 2, "license": "MIT", "archived": False},
            },
        }
        lanes_doc = {
            "critic": {"layers_without_confirmed_selection": []},
            "lanes": [{
                "lane": "foundation",
                "result": {"calls": {"gh_api": 1}, "limits": ["read-only"], "layers": [{
                    "layer_id": "layer-a", "selected": [],
                    "alternatives_keep_but_compare": [],
                    "new_candidates": [
                        {"repository": "https://github.com/example/newcomer", "source": "s",
                         "demonstrated_gap": "g", "proposed_label": "not_adopted",
                         "comparison_that_would_overturn": "c", "evidence": []},
                        {"repository": "https://github.com/example/newcomer2", "source": "s",
                         "demonstrated_gap": "g", "proposed_label": "keep_but_compare",
                         "comparison_that_would_overturn": "c", "evidence": []},
                    ],
                    "open_gaps": ["gap-1"],
                }]},
                "proposals": [
                    {"layer": "layer-a", "repository": "https://github.com/example/newcomer",
                     "kind": "new_candidate", "survives": False,
                     "votes": [{"refuted": True, "confidence": 0.9, "reasoning": "no gap"}]},
                    {"layer": "layer-a", "repository": "https://github.com/example/newcomer2",
                     "kind": "new_candidate", "survives": True,
                     "votes": [{"refuted": False, "confidence": 0.5, "reasoning": "plausible"}]},
                ],
            }],
        }
        reconciliations = [{"layer": "layer-a", "kind": "note",
                             "repository": "https://github.com/example/comp-current",
                             "pin": "2.0.0", "source": "s", "note": "n"}]
        return build_manifest_mod.build_manifest(
            checked_at="2026-01-03", manifest_id="test-id", scope="test scope",
            foundation_layers=foundation_layers, trading_by_layer=trading_by_layer,
            freshness_doc=freshness_doc, lanes_doc=lanes_doc, reconciliations=reconciliations,
            taxonomy=trading_by_layer["taxonomy"],
        )

    def test_candidates_by_disposition_sums_to_candidates_total(self):
        manifest = self.build_fixture_manifest()
        counts = manifest["counts"]
        self.assertEqual(sum(counts["candidates_by_disposition"].values()), counts["candidates_total"])
        self.assertEqual(counts["candidates_total"], 2)
        self.assertEqual(counts["candidates_by_disposition"]["refuted_not_adopted"], 1)
        self.assertEqual(counts["candidates_by_disposition"]["keep_but_compare"], 1)

    def test_only_the_plain_version_pin_counts_as_behind(self):
        manifest = self.build_fixture_manifest()
        components = {c["id"]: c for c in manifest["foundation"][0]["components"]}
        self.assertTrue(components["comp-old"]["pin_behind_upstream"])
        self.assertFalse(components["comp-current"]["pin_behind_upstream"])
        self.assertFalse(components["comp-commit"]["pin_behind_upstream"])
        self.assertFalse(components["systemd"]["pin_behind_upstream"])
        # comp-old (1.0.0 < 1.5.0) and trade-old (1.0.0 < 1.1.0) are both behind;
        # unique count is over distinct component ids across foundation + trading.
        entry = manifest["trading"][0]["entries"][0]
        self.assertTrue(entry["pin_behind_upstream"])
        self.assertEqual(manifest["counts"]["pins_behind_upstream_unique_components"], 2)

    def test_reconciliation_upstream_is_computed_from_freshness(self):
        manifest = self.build_fixture_manifest()
        self.assertEqual(manifest["reconciliations"][0]["upstream"]["latest"], "v2.0.0")

    def test_rename_is_visible_on_the_trading_entry(self):
        manifest = self.build_fixture_manifest()
        entry = manifest["trading"][0]["entries"][0]
        self.assertEqual(entry["upstream"]["renamed_to"], "example/trade-new")

    def test_manifest_serializes_and_writer_would_accept_it(self):
        import json
        manifest = self.build_fixture_manifest()
        text = build_manifest_mod.sanitize(json.dumps(manifest, indent=1))
        build_manifest_mod.assert_no_leak(text)  # must not raise


if __name__ == "__main__":
    unittest.main()
