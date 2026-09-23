"""Synthetic-fixture tests for tools/sota-convergence. No network, no real catalogs.

Modules are loaded by file path (tools/sota-convergence is not a dotted-import
package name) and skipped cleanly if a required stdlib module is unexpectedly
absent from the interpreter under test.
"""
import importlib.util
import json
import re
import subprocess
import unittest
from pathlib import Path
from unittest import mock

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
github_freshness = load_module("github_freshness", "github_freshness.py")


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

    def test_release_url_alias_resolves_to_same_freshness_record_as_canonical_url(self):
        # 2026-09-22 review finding 1: catalogs use release/tree URLs for
        # some components (agentsview, QMD, RTK); github_freshness.py only
        # keeps one representative URL per slug, so an exact-string lookup
        # against a release/tag alias missed the freshness record entirely.
        # compute_upstream must fall back to a normalized-slug lookup.
        repositories = {
            "https://github.com/example/aliased": {
                "slug": "example/aliased",
                "latest_release": {"tag": "v2.0.0", "published_at": "2026-01-01T00:00:00Z"},
                "pushed_at": "2026-01-01T00:00:00Z", "stargazers_count": 3, "license": "MIT",
            },
        }
        canonical = build_manifest_mod.compute_upstream(
            "https://github.com/example/aliased", repositories)
        aliased = build_manifest_mod.compute_upstream(
            "https://github.com/example/aliased/releases/tag/v1", repositories)
        self.assertEqual(canonical["latest"], "v2.0.0")
        self.assertEqual(aliased, canonical)

    def test_slug_lookup_also_works_without_a_slug_field_on_the_record(self):
        # A record loaded from an older-format freshness file (or one keyed
        # by a differently-cased URL) may not carry its own "slug" field;
        # the slug must still be derivable from the dict key URL itself.
        repositories = {
            "https://github.com/example/tree-form/tree/main": {
                "latest_release": {"tag": "v9.0.0"},
            },
        }
        upstream = build_manifest_mod.compute_upstream(
            "https://github.com/example/tree-form", repositories)
        self.assertEqual(upstream["latest"], "v9.0.0")

    def test_repository_known_matches_by_slug_too(self):
        repositories = {"https://github.com/example/known": {"slug": "example/known"}}
        self.assertTrue(build_manifest_mod.repository_known(
            "https://github.com/example/known/releases/tag/v1", repositories))
        self.assertFalse(build_manifest_mod.repository_known(
            "https://github.com/example/unknown", repositories))


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
        result = build_manifest_mod.classify_pin("1.2.3", None, None)
        self.assertFalse(result["behind"])
        self.assertTrue(result["excluded"])
        self.assertEqual(result["reason"], "non_github_or_os_package")

    def test_equal_versions_are_not_behind(self):
        result = build_manifest_mod.classify_pin("2.0.0", "https://github.com/example/x", "v2.0.0")
        self.assertFalse(result["behind"])
        self.assertFalse(result["excluded"])

    def test_systemd_os_package_pin_is_excluded_even_on_a_real_github_repository(self):
        # The real manifests/stack.json row: systemd's own repository field is a
        # genuine GitHub URL, so the plain non-GitHub check alone does not
        # exclude it. The Ubuntu-style package pin ("255.4-1ubuntu8.17") must be
        # recognized and excluded on its own, without relying on the id
        # allow-list, or this regresses to counting systemd as pin_behind_upstream.
        result = build_manifest_mod.classify_pin(
            "255.4-1ubuntu8.17", "https://github.com/systemd/systemd", "v261.3")
        self.assertFalse(result["behind"])
        self.assertTrue(result["excluded"])
        self.assertEqual(result["reason"], "os_package_pin")

    def test_debian_style_pin_suffixes_are_also_excluded(self):
        for pin in ("1.2.3-1deb11u1", "1.2.3+deb11u1"):
            with self.subTest(pin=pin):
                result = build_manifest_mod.classify_pin(pin, "https://github.com/example/distro-tool", "v9.9.9")
                self.assertTrue(result["excluded"])
                self.assertEqual(result["reason"], "os_package_pin")

    def test_os_package_ids_allow_list_excludes_even_a_plain_version_pin(self):
        # A component named in --os-package-ids is excluded regardless of pin
        # format (e.g. a distro package that happens to report a plain-looking
        # version string).
        result = build_manifest_mod.classify_pin(
            "255.4", "https://github.com/systemd/systemd", "v261.3",
            component_id="systemd", os_package_ids=("systemd",))
        self.assertTrue(result["excluded"])
        self.assertEqual(result["reason"], "os_package_pin")

    def test_os_package_ids_allow_list_does_not_affect_unrelated_ids(self):
        result = build_manifest_mod.classify_pin(
            "1.0.0", "https://github.com/example/other", "v2.0.0",
            component_id="other", os_package_ids=("systemd",))
        self.assertTrue(result["behind"])
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

    def test_unrecognized_label_never_passes_through_as_a_promotable_value(self):
        # An unrecognised proposed_label must never survive unchanged: it is
        # normalized to "unlabelled" before the survives logic runs, in every
        # survives state, so a lane cannot invent a label that looks promoted.
        self.assertEqual(build_manifest_mod.disposition("unlabelled-thing", True), "unlabelled")
        self.assertEqual(build_manifest_mod.disposition("unlabelled-thing", False), "refuted_unlabelled")
        self.assertEqual(build_manifest_mod.disposition("unlabelled-thing", None), "unlabelled_unverified")

    def test_missing_label_survives_is_labelled(self):
        self.assertEqual(build_manifest_mod.disposition(None, True), "unlabelled")

    def test_proposable_labels_are_exactly_the_documented_three(self):
        self.assertEqual(build_manifest_mod.PROPOSABLE_LABELS,
                          {"not_adopted", "keep_but_compare", "targeted_candidate"})


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

    def test_sanitize_covers_macos_and_windows_user_paths_too(self):
        # 2026-09-22 review finding 6/2: the publication guard originally
        # covered only Linux /home/ paths; scripts/validate.py's
        # PRIVATE_CONTENT already recognizes macOS and Windows forms too.
        for text in (
            'note: "/Users/example/code/x.json" was read',
            r'note: "C:\Users\example\code\x.json" was read',
            r'note: "\Users\example\code\x.json" was read',
        ):
            with self.subTest(text=text):
                cleaned = build_manifest_mod.sanitize(text)
                self.assertNotIn("Users", cleaned)
                self.assertIn("<host-path>", cleaned)


class QuotedPathSanitizationTests(unittest.TestCase):
    """2026-09-22 review finding 2: sanitizing the *serialized* JSON text
    (the previous approach) can consume the backslash that escapes a quote
    inside a quoted path, producing invalid JSON that assert_no_leak alone
    does not catch. Sanitizing decoded string values before serialization
    fixes this; the fix is proven by round-tripping through json.loads."""

    QUOTED_PATH_NOTE = 'read "/home/example/file.json" before publishing'

    def test_naive_post_serialization_sanitize_corrupts_this_exact_case(self):
        # Documents the bug this finding fixed: applying sanitize() to
        # already-serialized JSON text breaks on a quoted embedded path.
        text = json.dumps({"note": self.QUOTED_PATH_NOTE})
        naive = build_manifest_mod.sanitize(text)
        with self.assertRaises(json.JSONDecodeError):
            json.loads(naive)

    def test_sanitizing_the_decoded_object_before_dumps_stays_valid_json(self):
        obj = {"note": self.QUOTED_PATH_NOTE}
        cleaned = build_manifest_mod.sanitize_value(obj)
        text = json.dumps(cleaned, indent=1)
        # Must round-trip through json.loads to prove the written text is
        # valid JSON (the fix's second half, per the finding).
        reparsed = json.loads(text)
        self.assertNotIn("/home/", text)
        # G5: the basename (and any "#/json/pointer" suffix) survive the
        # redaction verbatim -- see PathBasenamePreservingSanitizationTests --
        # so this is "<host-path>/file.json", not a bare "<host-path>".
        self.assertEqual(reparsed["note"], 'read "<host-path>/file.json" before publishing')

    def test_sanitize_value_walks_nested_lists_and_dicts(self):
        obj = {"evidence": ["/home/example/a.json", {"nested": "/Users/example/b.json"}], "count": 3, "ok": None}
        cleaned = build_manifest_mod.sanitize_value(obj)
        # G5: basename preserved (see PathBasenamePreservingSanitizationTests).
        self.assertEqual(cleaned["evidence"][0], "<host-path>/a.json")
        self.assertEqual(cleaned["evidence"][1]["nested"], "<host-path>/b.json")
        self.assertEqual(cleaned["count"], 3)
        self.assertIsNone(cleaned["ok"])


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
                    # The real manifests/stack.json row: a genuine GitHub repository
                    # with an Ubuntu-package pin -- must stay excluded end to end.
                    {"id": "systemd", "repository": "https://github.com/systemd/systemd",
                     "version": "255.4-1ubuntu8.17", "license": "GPL", "role": "scheduler", "profile": "optional"},
                ],
            }],
            "top_gaps": [],
        }
        # A distinct layer id from foundation's "layer-a": real foundation (20 ids)
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
            "count": 5, "generated_at": "2026-01-02T00:00:00+00:00",
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
                "https://github.com/systemd/systemd": {
                    "latest_release": {"tag": "v261.3", "published_at": "2026-09-10T00:00:00Z", "prerelease": False},
                    "pushed_at": "2026-09-22T00:00:00Z", "stargazers_count": 16714, "license": "GPL-2.0",
                    "archived": False},
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

    def test_candidates_are_sorted_by_disposition_rank_not_lane_insertion_order(self):
        # newcomer (not_adopted, refuted) is listed before newcomer2
        # (keep_but_compare, survives) in the lane's new_candidates, but
        # keep_but_compare outranks refuted_not_adopted -- the manifest order
        # must reflect that rank, not the lane's insertion order.
        manifest = self.build_fixture_manifest()
        candidates = manifest["foundation"][0]["candidates"]
        self.assertEqual(
            [c["repository"] for c in candidates],
            ["https://github.com/example/newcomer2", "https://github.com/example/newcomer"],
        )

    def test_candidate_disposition_survives_null_is_reported_as_unverified(self):
        # A candidate with no matching proposals[] verdict has survives=null in
        # the lanes.json contract; adversarial_verification.survives must stay
        # None (JSON null) and the disposition must carry "_unverified".
        lanes_doc = {
            "critic": None,
            "lanes": [{
                "lane": "foundation",
                "result": {"calls": {}, "limits": [], "layers": [{
                    "layer_id": "layer-a", "selected": [], "alternatives_keep_but_compare": [],
                    "new_candidates": [{
                        "repository": "https://github.com/example/unverified-newcomer", "source": "s",
                        "demonstrated_gap": "g", "proposed_label": "targeted_candidate",
                        "comparison_that_would_overturn": "c", "evidence": [],
                    }],
                    "open_gaps": [],
                }]},
                "proposals": [],
            }],
        }
        status, notes, alts, cands, gaps, calls, limits = build_manifest_mod.merge_lanes(lanes_doc, {})
        candidate = cands["layer-a"][0]
        self.assertIsNone(candidate["adversarial_verification"]["survives"])
        self.assertEqual(candidate["disposition"], "targeted_candidate_unverified")

    def test_why_selected_and_comparison_that_would_overturn_are_carried_through_when_present(self):
        # pr2-schema unit 5: optional lane fields on a *selected* item (not a
        # new_candidate, which already carries comparison_that_would_overturn)
        # must reach merge_lanes' returned status[key] unchanged when the lane
        # sets them, and must be absent (never invented) when it does not.
        def lanes_doc(selected_extra):
            return {
                "critic": None,
                "lanes": [{
                    "lane": "trading",
                    "result": {"calls": {}, "limits": [], "layers": [{
                        "layer_id": "layer-a",
                        "selected": [{
                            "repository": "https://github.com/example/winner",
                            "status": "confirmed_default", "evidence": [], "note": None,
                            **selected_extra,
                        }],
                        "alternatives_keep_but_compare": [], "new_candidates": [], "open_gaps": [],
                    }]},
                    "proposals": [],
                }],
            }

        key = ("layer-a", "https://github.com/example/winner")
        status = build_manifest_mod.merge_lanes(lanes_doc({
            "why_selected": "Passed the native scoped operation",
            "comparison_that_would_overturn": "A sealed head-to-head replay",
        }), {})[0]
        self.assertEqual(status[key]["lane_item"]["why_selected"], "Passed the native scoped operation")
        self.assertEqual(status[key]["lane_item"]["comparison_that_would_overturn"], "A sealed head-to-head replay")

        status_absent = build_manifest_mod.merge_lanes(lanes_doc({}), {})[0]
        self.assertNotIn("why_selected", status_absent[key]["lane_item"])
        # T3 (2026-09-22 tooling citation review, finding 33): asserting
        # absence on status_absent[key] itself is vacuous -- that top-level
        # dict never carries this field regardless of merge_lanes' own
        # never-invented contract (it always lives under ["lane_item"]).
        self.assertNotIn("comparison_that_would_overturn", status_absent[key]["lane_item"])

    def test_why_selected_and_comparison_that_would_overturn_reach_the_merged_manifest_rows(self):
        # Fix round finding 4: merge_lanes attaching these fields to
        # status[key] alone has no observable effect unless build_manifest()
        # actually copies them onto the merged components[]/entries[] it
        # writes to the manifest -- assert on that output, not the
        # intermediate status dict.
        foundation_layers = {"checked_at": "2026-01-01", "layers": [{
            "layer_id": "layer-a", "title": "Layer A", "components": [{
                "id": "winner-component", "repository": "https://github.com/example/winner",
                "version": "1.0.0",
            }],
        }]}
        trading_by_layer = {
            "taxonomy": {"layer-b": ["tag-a"]},
            "layers": {"layer-b": [{
                "id": "winner-entry", "repository": "https://github.com/example/trade-winner",
                "decision": "default", "version_or_commit": "1.0.0", "layers": ["tag-a"],
            }]},
        }
        freshness_doc = {"count": 0, "generated_at": "2026-01-02T00:00:00+00:00", "repositories": {}}
        lanes_doc = {
            "critic": None,
            "lanes": [{
                "lane": "combined",
                "result": {"calls": {}, "limits": [], "layers": [
                    {"layer_id": "layer-a", "selected": [{
                        "repository": "https://github.com/example/winner",
                        "status": "confirmed_default", "evidence": [], "note": None,
                        "why_selected": "Passed the native scoped operation",
                        "comparison_that_would_overturn": "A sealed head-to-head replay",
                    }], "alternatives_keep_but_compare": [], "new_candidates": [], "open_gaps": []},
                    {"layer_id": "layer-b", "selected": [{
                        "repository": "https://github.com/example/trade-winner",
                        "status": "confirmed_default", "evidence": [], "note": None,
                    }], "alternatives_keep_but_compare": [], "new_candidates": [], "open_gaps": []},
                ]},
                "proposals": [],
            }],
        }
        manifest = build_manifest_mod.build_manifest(
            checked_at="2026-01-03", manifest_id="test-id", scope="test scope",
            foundation_layers=foundation_layers, trading_by_layer=trading_by_layer,
            freshness_doc=freshness_doc, lanes_doc=lanes_doc, reconciliations=[],
            taxonomy=trading_by_layer["taxonomy"],
        )
        component = manifest["foundation"][0]["components"][0]
        self.assertEqual(component["why_selected"], "Passed the native scoped operation")
        self.assertEqual(component["comparison_that_would_overturn"], "A sealed head-to-head replay")
        # The trading lane's selected item set neither optional field: they
        # must be omitted from the merged entry, never invented as None/"".
        entry = manifest["trading"][0]["entries"][0]
        self.assertNotIn("why_selected", entry)
        self.assertNotIn("comparison_that_would_overturn", entry)


class SelectedVerdictNullSurvivesTests(unittest.TestCase):
    """2026-09-22 review finding 5: merge_lanes' selected-status handling
    used ``if verdict is not None and not verdict["survives"]:`` -- a
    ``survives: null`` (unknown outcome) verdict is truthy under ``not
    None``... no: ``not None`` is True, so a *null* verdict was treated
    exactly like a *refuted* (``survives: False``) one. An
    ``unmaintained_signal`` proposal with no votes therefore became
    ``confirmed_default`` and gained a false "refuted by adversarial
    verification" note. ``survives: False`` must be handled explicitly;
    ``None`` must stay unverified."""

    def _lanes_doc(self, survives, votes):
        return {
            "critic": None,
            "lanes": [{
                "lane": "trading",
                "result": {"calls": {}, "limits": [], "layers": [{
                    "layer_id": "layer-a",
                    "selected": [{
                        "repository": "https://github.com/example/fredapi",
                        "status": "unmaintained_signal", "evidence": ["stale-push"],
                        "note": "no commits in a year",
                    }],
                    "alternatives_keep_but_compare": [], "new_candidates": [], "open_gaps": [],
                }]},
                "proposals": [{
                    "layer": "layer-a", "repository": "https://github.com/example/fredapi",
                    "kind": "unmaintained_signal", "survives": survives, "votes": votes,
                }],
            }],
        }

    def test_unmaintained_signal_with_null_survives_stays_unverified_not_confirmed(self):
        status, notes, alts, cands, gaps, calls, limits = build_manifest_mod.merge_lanes(
            self._lanes_doc(None, []), {})
        key = ("layer-a", "https://github.com/example/fredapi")
        self.assertEqual(status[key]["status"], "unmaintained_signal_unverified")
        # No refutation note, and no promotion to a "confirmed_*" status.
        self.assertEqual(notes.get(key, []), [])
        self.assertFalse(any("refuted" in item for item in status[key]["evidence"]))
        # The returned (here: zero) vote count is recorded in the evidence.
        self.assertTrue(any("0 adversarial vote" in item for item in status[key]["evidence"]))

    def test_unmaintained_signal_with_survives_false_emits_the_refuted_to_confirmed_marker(self):
        # G2 (build round 2026-09-22, second pass): merge_lanes alone has no
        # baseline decision to resolve a refuted demotion/unmaintained-signal
        # proposal to a concrete confirmed_* class without risking promotion
        # past the component's own governing selection (a conditional
        # component was observed promoted to confirmed_default this way) --
        # it emits build_manifest_mod.REFUTED_TO_CONFIRMED_MARKER instead;
        # only build_manifest(), which has the baseline, resolves it (see
        # RefutedToConfirmedBaselineResolutionTests below).
        status, notes, alts, cands, gaps, calls, limits = build_manifest_mod.merge_lanes(
            self._lanes_doc(False, [{"refuted": True, "confidence": 0.9, "reasoning": "still maintained"}]), {})
        key = ("layer-a", "https://github.com/example/fredapi")
        self.assertEqual(status[key]["status"], build_manifest_mod.REFUTED_TO_CONFIRMED_MARKER)
        self.assertTrue(any("refuted" in item for item in notes.get(key, [])))
        # The same refutation annotation is also on the entry's own evidence
        # now (not only in the separate `notes` dict), since build_manifest()
        # no longer consults `notes` when assembling a row's evidence (G1
        # fixed a cross-lane evidence leak that relied on doing so).
        self.assertTrue(any("refuted" in item for item in status[key]["evidence"]))

    def test_unmaintained_signal_with_survives_true_keeps_the_proposed_status(self):
        status, notes, alts, cands, gaps, calls, limits = build_manifest_mod.merge_lanes(
            self._lanes_doc(True, [{"refuted": False, "confidence": 0.7, "reasoning": "confirmed stale"}]), {})
        key = ("layer-a", "https://github.com/example/fredapi")
        self.assertEqual(status[key]["status"], "unmaintained_signal")
        self.assertEqual(notes.get(key, []), [])

    def test_end_to_end_manifest_does_not_inflate_components_confirmed_on_a_null_verdict(self):
        foundation_layers = {"checked_at": "2026-01-01", "layers": []}
        trading_by_layer = {
            "taxonomy": {"layer-a": ["tag-a"]},
            "layers": {"layer-a": [{
                "id": "fredapi", "repository": "https://github.com/example/fredapi",
                "decision": "conditional", "version_or_commit": "1.0.0", "layers": ["tag-a"],
            }]},
        }
        freshness_doc = {"count": 0, "generated_at": "2026-01-02T00:00:00+00:00", "repositories": {}}
        manifest = build_manifest_mod.build_manifest(
            checked_at="2026-01-03", manifest_id="test-id", scope="test scope",
            foundation_layers=foundation_layers, trading_by_layer=trading_by_layer,
            freshness_doc=freshness_doc, lanes_doc=self._lanes_doc(None, []), reconciliations=[],
            taxonomy=trading_by_layer["taxonomy"],
        )
        entry = manifest["trading"][0]["entries"][0]
        self.assertEqual(entry["review_status"], "unmaintained_signal_unverified")
        self.assertEqual(manifest["counts"]["components_confirmed"], 0)


class EvidenceLevelCarryThroughTests(unittest.TestCase):
    """2026-09-22 review finding 7: review_status (a selection/pin
    confirmation) and evidence_level (source_review / native_proven --
    actual execution evidence, from the catalog card) are independent axes.
    evidence_level must be carried into each manifest trading entry row when
    the source catalogs/us-equities/*.json card has it."""

    def test_evidence_level_from_the_catalog_card_is_carried_into_the_manifest_entry(self):
        trading_by_layer = {
            "taxonomy": {"layer-b": ["tag-a"]},
            "layers": {"layer-b": [
                {"id": "quantstats", "repository": "https://github.com/ranaroussi/quantstats",
                 "decision": "default", "version_or_commit": "0.0.81", "layers": ["tag-a"],
                 "evidence_level": "source_review"},
                {"id": "no-level-tool", "repository": "https://github.com/example/no-level-tool",
                 "decision": "default", "version_or_commit": "1.0.0", "layers": ["tag-a"]},
            ]},
        }
        freshness_doc = {"count": 0, "generated_at": "2026-01-02T00:00:00+00:00", "repositories": {}}
        lanes_doc = {"critic": None, "lanes": []}
        manifest = build_manifest_mod.build_manifest(
            checked_at="2026-09-22", manifest_id="test-id", scope="s",
            foundation_layers={"layers": []}, trading_by_layer=trading_by_layer,
            freshness_doc=freshness_doc, lanes_doc=lanes_doc, reconciliations=[],
            taxonomy=trading_by_layer["taxonomy"],
        )
        entries = {e["id"]: e for e in manifest["trading"][0]["entries"]}
        self.assertEqual(entries["quantstats"]["evidence_level"], "source_review")
        self.assertNotIn("evidence_level", entries["no-level-tool"])
        # review_status (survival of a lane's proposed change) must remain
        # independent of evidence_level (execution classification): neither
        # entry has a lane verdict here, so both stay "not_individually_reviewed".
        self.assertEqual(entries["quantstats"]["review_status"], "not_individually_reviewed")


class ObservationWindowTests(unittest.TestCase):
    """2026-09-22 review finding 4: on a resumed run, ``generated_at`` is
    rewritten even when zero repositories were re-fetched, so citing it in
    method.freshness misrepresents old metadata as newly fetched. The
    manifest must cite the freshness snapshot's per-record observation
    window instead."""

    def test_resumed_run_with_zero_fetches_reports_the_retained_window(self):
        freshness_doc = {
            "count": 2, "generated_at": "2026-09-22T00:00:00+00:00",
            "fetched_this_run": 0, "retained_from_prior_runs": 2,
            "observation_window": {"min": "2026-08-01T00:00:00+00:00", "max": "2026-08-15T00:00:00+00:00"},
            "repositories": {},
        }
        manifest = build_manifest_mod.build_manifest(
            checked_at="2026-09-22", manifest_id="test-id", scope="s",
            foundation_layers={"layers": []}, trading_by_layer={"taxonomy": {}, "layers": {}},
            freshness_doc=freshness_doc, lanes_doc={"critic": None, "lanes": []}, reconciliations=[],
            taxonomy={},
        )
        freshness_text = manifest["method"]["freshness"]
        self.assertIn("2026-08-01T00:00:00", freshness_text)
        self.assertIn("2026-08-15T00:00:00", freshness_text)
        # generated_at (the checkpoint/write time of this resumed run) must
        # not be cited as if it were the observation/fetch time.
        self.assertNotIn("2026-09-22T00:00:00", freshness_text)
        self.assertIn("fetched_this_run=0", freshness_text)
        self.assertIn("retained_from_prior_runs=2", freshness_text)

    def test_missing_observation_window_does_not_crash_and_says_so(self):
        freshness_doc = {"count": 0, "generated_at": "2026-09-22T00:00:00+00:00", "repositories": {}}
        text = build_manifest_mod.format_observation_window(freshness_doc)
        self.assertIn("unrecorded", text)

    def test_falls_back_to_scanning_per_record_observed_at_for_an_older_format_freshness_file(self):
        # An older-format github-freshness.json (from before this fix) has no
        # top-level "observation_window", but its records already carry
        # "observed_at" -- the window must still be derivable, not just
        # reported as unrecorded.
        freshness_doc = {
            "count": 2, "generated_at": "2026-09-22T04:08:18+00:00",
            "repositories": {
                "https://github.com/example/a": {"observed_at": "2026-09-22T04:07:01+00:00"},
                "https://github.com/example/b": {"observed_at": "2026-09-22T04:07:55+00:00"},
            },
        }
        text = build_manifest_mod.format_observation_window(freshness_doc)
        self.assertIn("2026-09-22T04:07:01", text)
        self.assertIn("2026-09-22T04:07:55", text)
        self.assertNotIn("unrecorded", text)


class DeterministicOrderingTests(unittest.TestCase):
    """Rebuilding the manifest must not reorder rows: per-layer components,
    entries and candidates are sorted by (decision-rank, id/repository), not
    left in whatever order the source JSON happened to list them in."""

    def build(self, entry_order):
        foundation_layers = {"checked_at": "2026-01-01", "layers": []}
        trading_by_layer = {
            "taxonomy": {"layer-b": ["tag-a"]},
            "layers": {"layer-b": [
                {"id": entry["id"], "repository": entry["repository"], "decision": entry["decision"],
                 "version_or_commit": "1.0.0", "layers": ["tag-a"]}
                for entry in entry_order
            ]},
        }
        freshness_doc = {"count": 0, "generated_at": "2026-01-02T00:00:00+00:00", "repositories": {}}
        lanes_doc = {"critic": None, "lanes": []}
        return build_manifest_mod.build_manifest(
            checked_at="2026-01-03", manifest_id="test-id", scope="test scope",
            foundation_layers=foundation_layers, trading_by_layer=trading_by_layer,
            freshness_doc=freshness_doc, lanes_doc=lanes_doc, reconciliations=[],
            taxonomy=trading_by_layer["taxonomy"],
        )

    def test_default_decision_sorts_before_conditional_even_when_its_id_sorts_later(self):
        entries = [
            {"id": "aaa-tool", "repository": "https://github.com/example/aaa-tool", "decision": "conditional"},
            {"id": "zzz-tool", "repository": "https://github.com/example/zzz-tool", "decision": "default"},
        ]
        manifest = self.build(entries)
        ids = [e["id"] for e in manifest["trading"][0]["entries"]]
        self.assertEqual(ids, ["zzz-tool", "aaa-tool"])

    def test_entry_order_is_identical_regardless_of_source_json_order(self):
        entries = [
            {"id": "aaa-tool", "repository": "https://github.com/example/aaa-tool", "decision": "conditional"},
            {"id": "zzz-tool", "repository": "https://github.com/example/zzz-tool", "decision": "default"},
        ]
        forward = self.build(entries)
        reversed_ = self.build(list(reversed(entries)))
        self.assertEqual(
            [e["id"] for e in forward["trading"][0]["entries"]],
            [e["id"] for e in reversed_["trading"][0]["entries"]],
        )


class GithubFreshnessResilienceTests(unittest.TestCase):
    """github_freshness.py must not let one gh failure abort the whole run,
    and a resumed run must retry only the repositories that previously
    carried an "error"."""

    def test_gh_api_never_raises_when_the_subprocess_call_fails(self):
        with mock.patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd=["gh"], timeout=60)):
            result, err = github_freshness.gh_api("repos/example/slow-repo")
        self.assertIsNone(result)
        self.assertIsInstance(err, str)
        self.assertTrue(err)

    def _write_foundation_layers(self, work_dir):
        (work_dir / "foundation-layers.json").write_text(json.dumps({
            "layers": [{"components": [
                {"repository": "https://github.com/example/a-repo"},
                {"repository": "https://github.com/example/b-repo"},
            ]}],
        }), encoding="utf-8")

    def _fake_gh_run(self, calls, fail_slug_ref):
        class FakeProc:
            def __init__(self, returncode, stdout="", stderr=""):
                self.returncode = returncode
                self.stdout = stdout
                self.stderr = stderr

        def fake_run(cmd, capture_output=True, text=True, timeout=60):
            path = cmd[2]
            calls.append(path)
            if fail_slug_ref["slug"] and path == f"repos/{fail_slug_ref['slug']}":
                raise subprocess.TimeoutExpired(cmd=cmd, timeout=timeout)
            if path in ("repos/example/a-repo", "repos/example/b-repo"):
                slug = path.split("/", 1)[1]
                return FakeProc(0, stdout=json.dumps({
                    "full_name": slug, "default_branch": "main", "stargazers_count": 1,
                }))
            return FakeProc(1, stdout="", stderr="not found")

        return fake_run

    def test_one_failing_repository_does_not_abort_the_run_and_resume_retries_only_it(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            work_dir = Path(tmp)
            self._write_foundation_layers(work_dir)
            out_path = work_dir / "github-freshness.json"

            calls = []
            fail_slug_ref = {"slug": "example/b-repo"}
            with mock.patch("subprocess.run", side_effect=self._fake_gh_run(calls, fail_slug_ref)):
                rc = github_freshness.main(["--work-dir", str(work_dir), "--workers", "1"])
            self.assertEqual(rc, 0)
            self.assertTrue(out_path.exists(), "the first repository must be on disk even though the second failed")

            document = json.loads(out_path.read_text(encoding="utf-8"))
            repos = document["repositories"]
            a_record = repos["https://github.com/example/a-repo"]
            b_record = repos["https://github.com/example/b-repo"]
            self.assertNotIn("error", a_record)
            self.assertEqual(a_record.get("full_name"), "example/a-repo")
            self.assertIn("error", b_record)

            # Resume: the failing repository must be retried; the already-covered
            # one must not be re-fetched.
            calls.clear()
            fail_slug_ref["slug"] = None
            with mock.patch("subprocess.run", side_effect=self._fake_gh_run(calls, fail_slug_ref)):
                rc = github_freshness.main(["--work-dir", str(work_dir), "--workers", "1"])
            self.assertEqual(rc, 0)
            self.assertTrue(any(p.startswith("repos/example/b-repo") for p in calls),
                             "the previously-failed repository must be retried on resume")
            self.assertFalse(any(p.startswith("repos/example/a-repo") for p in calls),
                              "an already-covered repository must not be re-fetched on resume")

            document = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertNotIn("error", document["repositories"]["https://github.com/example/b-repo"])


class _FakeProc:
    def __init__(self, returncode, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class GithubFreshnessPartialErrorTests(unittest.TestCase):
    """2026-09-22 review finding 3: a release/tag/commit sub-request that
    times out or is rate-limited (as opposed to an ordinary 404 for "no
    releases") must be kept as a retryable partial_errors entry, not
    silently discarded."""

    REPO = "example/solo-repo"

    def _write_foundation_layers(self, work_dir):
        (work_dir / "foundation-layers.json").write_text(json.dumps({
            "layers": [{"components": [{"repository": f"https://github.com/{self.REPO}"}]}],
        }), encoding="utf-8")

    def test_expected_404_for_no_releases_is_not_a_partial_error(self):
        def fake_run(cmd, capture_output=True, text=True, timeout=60):
            path = cmd[2]
            if path == f"repos/{self.REPO}":
                return _FakeProc(0, stdout=json.dumps(
                    {"full_name": self.REPO, "default_branch": "main", "stargazers_count": 1}))
            if path == f"repos/{self.REPO}/releases/latest":
                return _FakeProc(1, stdout="", stderr="HTTP 404: Not Found")
            if path == f"repos/{self.REPO}/tags?per_page=1":
                return _FakeProc(0, stdout="[]")
            if path == f"repos/{self.REPO}/commits/main":
                return _FakeProc(0, stdout=json.dumps(
                    {"sha": "abc", "commit": {"committer": {"date": "2026-01-01"}}}))
            return _FakeProc(1, stdout="", stderr="unexpected")

        with mock.patch("subprocess.run", side_effect=fake_run):
            record = github_freshness.fetch_repository(self.REPO)
        self.assertNotIn("error", record)
        self.assertNotIn("partial_errors", record)
        self.assertIsNone(record.get("latest_tag"))

    def test_release_timeout_is_kept_as_a_retryable_partial_error(self):
        def fake_run(cmd, capture_output=True, text=True, timeout=60):
            path = cmd[2]
            if path == f"repos/{self.REPO}":
                return _FakeProc(0, stdout=json.dumps(
                    {"full_name": self.REPO, "default_branch": "main", "stargazers_count": 1}))
            if path == f"repos/{self.REPO}/releases/latest":
                raise subprocess.TimeoutExpired(cmd=cmd, timeout=timeout)
            if path == f"repos/{self.REPO}/tags?per_page=1":
                return _FakeProc(0, stdout="[]")
            if path == f"repos/{self.REPO}/commits/main":
                return _FakeProc(0, stdout=json.dumps(
                    {"sha": "abc", "commit": {"committer": {"date": "2026-01-01"}}}))
            return _FakeProc(1, stdout="", stderr="unexpected")

        with mock.patch("subprocess.run", side_effect=fake_run):
            record = github_freshness.fetch_repository(self.REPO)
        self.assertNotIn("error", record)
        self.assertIn("releases", record.get("partial_errors", {}))

    def test_a_record_with_partial_errors_is_retried_on_resume(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            work_dir = Path(tmp)
            self._write_foundation_layers(work_dir)
            out_path = work_dir / "github-freshness.json"

            def failing_release_run(cmd, capture_output=True, text=True, timeout=60):
                path = cmd[2]
                if path == f"repos/{self.REPO}":
                    return _FakeProc(0, stdout=json.dumps(
                        {"full_name": self.REPO, "default_branch": "main", "stargazers_count": 1}))
                if path == f"repos/{self.REPO}/releases/latest":
                    raise subprocess.TimeoutExpired(cmd=cmd, timeout=timeout)
                if path == f"repos/{self.REPO}/tags?per_page=1":
                    return _FakeProc(0, stdout="[]")
                if path == f"repos/{self.REPO}/commits/main":
                    return _FakeProc(0, stdout=json.dumps(
                        {"sha": "abc", "commit": {"committer": {"date": "2026-01-01"}}}))
                return _FakeProc(1, stdout="", stderr="unexpected")

            with mock.patch("subprocess.run", side_effect=failing_release_run):
                rc = github_freshness.main(["--work-dir", str(work_dir), "--workers", "1"])
            self.assertEqual(rc, 0)
            document = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(document.get("partial_errors"), 1)
            self.assertIn("partial_errors", document["repositories"][f"https://github.com/{self.REPO}"])

            calls = []

            def recovered_run(cmd, capture_output=True, text=True, timeout=60):
                calls.append(cmd[2])
                path = cmd[2]
                if path == f"repos/{self.REPO}":
                    return _FakeProc(0, stdout=json.dumps(
                        {"full_name": self.REPO, "default_branch": "main", "stargazers_count": 1}))
                if path == f"repos/{self.REPO}/releases/latest":
                    return _FakeProc(0, stdout=json.dumps(
                        {"tag_name": "v1.0.0", "published_at": "2026-01-01T00:00:00Z", "prerelease": False}))
                if path == f"repos/{self.REPO}/commits/main":
                    return _FakeProc(0, stdout=json.dumps(
                        {"sha": "abc", "commit": {"committer": {"date": "2026-01-01"}}}))
                return _FakeProc(1, stdout="", stderr="unexpected")

            with mock.patch("subprocess.run", side_effect=recovered_run):
                rc = github_freshness.main(["--work-dir", str(work_dir), "--workers", "1"])
            self.assertEqual(rc, 0)
            self.assertTrue(any(p.startswith(f"repos/{self.REPO}") for p in calls),
                             "a record with partial_errors must be retried on resume")
            document = json.loads(out_path.read_text(encoding="utf-8"))
            record = document["repositories"][f"https://github.com/{self.REPO}"]
            self.assertNotIn("partial_errors", record)
            self.assertEqual(record["latest_release"]["tag"], "v1.0.0")
            self.assertEqual(document.get("partial_errors"), 0)


class GithubFreshnessAliasAndObservationTests(unittest.TestCase):
    """2026-09-22 review findings 1 and 4: every alias URL seen for a slug
    is recorded on the freshness record, and the document carries
    fetched_this_run / retained_from_prior_runs / observation_window."""

    def test_records_every_alias_url_seen_for_a_slug(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            work_dir = Path(tmp)
            (work_dir / "foundation-layers.json").write_text(json.dumps({
                "layers": [{"components": [
                    {"repository": "https://github.com/example/aliased"},
                    {"repository": "https://github.com/example/aliased/releases/tag/v1"},
                ]}],
            }), encoding="utf-8")

            def fake_run(cmd, capture_output=True, text=True, timeout=60):
                path = cmd[2]
                if path == "repos/example/aliased":
                    return _FakeProc(0, stdout=json.dumps(
                        {"full_name": "example/aliased", "default_branch": "main", "stargazers_count": 1}))
                return _FakeProc(1, stdout="", stderr="not found")

            with mock.patch("subprocess.run", side_effect=fake_run):
                rc = github_freshness.main(["--work-dir", str(work_dir), "--workers", "1"])
            self.assertEqual(rc, 0)
            document = json.loads((work_dir / "github-freshness.json").read_text(encoding="utf-8"))
            record = document["repositories"]["https://github.com/example/aliased"]
            self.assertEqual(
                record.get("aliases"),
                ["https://github.com/example/aliased", "https://github.com/example/aliased/releases/tag/v1"],
            )

    def test_document_reports_fetched_and_retained_counts_and_observation_window(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            work_dir = Path(tmp)
            (work_dir / "foundation-layers.json").write_text(json.dumps({
                "layers": [{"components": [{"repository": "https://github.com/example/solo"}]}],
            }), encoding="utf-8")

            def fake_run(cmd, capture_output=True, text=True, timeout=60):
                path = cmd[2]
                if path == "repos/example/solo":
                    return _FakeProc(0, stdout=json.dumps(
                        {"full_name": "example/solo", "default_branch": "main", "stargazers_count": 1}))
                return _FakeProc(1, stdout="", stderr="not found")

            out_path = work_dir / "github-freshness.json"
            with mock.patch("subprocess.run", side_effect=fake_run):
                rc = github_freshness.main(["--work-dir", str(work_dir), "--workers", "1"])
            self.assertEqual(rc, 0)
            document = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(document["fetched_this_run"], 1)
            self.assertEqual(document["retained_from_prior_runs"], 0)
            window = document["observation_window"]
            self.assertIsNotNone(window)
            self.assertEqual(window["min"], window["max"])

            # Resume with nothing new to fetch: fetched_this_run must be 0
            # and the window must be retained from the prior run, not moved
            # to this run's generated_at.
            with mock.patch("subprocess.run", side_effect=fake_run):
                rc = github_freshness.main(["--work-dir", str(work_dir), "--workers", "1"])
            self.assertEqual(rc, 0)
            resumed = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(resumed["fetched_this_run"], 0)
            self.assertEqual(resumed["retained_from_prior_runs"], 1)
            self.assertEqual(resumed["observation_window"], document["observation_window"])



class CodexSecondPassRegressionTests(unittest.TestCase):
    """Second Codex pass (2026-09-22): unverified confirmed_* statuses must not count as
    confirmed, and mixed-case slugs saved by an older snapshot must still count as
    covered on resume."""

    def test_confirmed_status_with_null_verdict_is_unverified_and_not_counted(self):
        lanes = {"lanes": [{"lane": "foundation", "result": {"layers": [{"layer_id": "workers",
                 "selected": [{"repository": "https://github.com/example/tool", "status": "confirmed_default",
                               "evidence": []}], "new_candidates": [], "open_gaps": []}]},
                 "proposals": [{"layer": "workers", "kind": "confirmed_default",
                                "repository": "https://github.com/example/tool", "survives": None, "votes": []}]}],
                 "critic": None, "lost": []}
        status_map = build_manifest_mod.merge_lanes(lanes, {})[0]
        status = status_map[("workers", "https://github.com/example/tool")]["status"]
        self.assertEqual(status, "confirmed_default_unverified")
        self.assertTrue(status.startswith("confirmed") and status.endswith("_unverified"))
        counted = sum(1 for st in [status] if st.startswith("confirmed") and not st.endswith("_unverified"))
        self.assertEqual(counted, 0)

    def test_mixed_case_saved_slug_counts_as_covered_on_resume(self):
        saved = {"https://github.com/QuantConnect/Lean": {"slug": "QuantConnect/Lean", "stargazers_count": 1}}
        covered = {str(rec.get("slug") or "").lower() for rec in saved.values()
                   if isinstance(rec, dict) and not rec.get("error") and not rec.get("partial_errors")}
        self.assertIn(github_freshness.github_slug("https://github.com/quantconnect/lean"), covered)


    def test_retained_mixed_case_slug_still_receives_current_aliases(self):
        saved = {"https://github.com/QuantConnect/Lean": {"slug": "QuantConnect/Lean", "stargazers_count": 1,
                                                          "observed_at": "2026-08-01T00:00:00+00:00"}}
        aliases = github_freshness.build_slug_aliases(["https://github.com/QuantConnect/Lean",
                                                       "https://github.com/quantconnect/lean/releases/tag/v1"])
        doc = github_freshness.build_document(saved, slug_aliases=aliases, fetched_this_run=0)
        rec = doc["repositories"]["https://github.com/QuantConnect/Lean"]
        self.assertEqual(rec["slug"], "quantconnect/lean")
        self.assertEqual(len(rec["aliases"]), 2)


class LaneGroupingTests(unittest.TestCase):
    """2026-09-22 second refresh: a review lane's own grouping id (e.g. the
    "beyond" lane's "awesome-list-convergence") is not a foundation or
    taxonomy layer id. trading[] must stay exactly the taxonomy layer ids (in
    taxonomy order); such a grouping's selected entries, alternatives, new
    candidates (with dispositions computed the same way as everywhere else)
    and open_gaps must reach a new top-level "lane_groupings" section
    instead, with nothing silently dropped."""

    def _lanes_doc(self):
        return {
            "critic": None,
            "lanes": [{
                "lane": "beyond",
                # Layers listed star-audit-* before awesome-list-* (i.e. NOT
                # already alphabetically sorted) so a test asserting sorted
                # output cannot be satisfied merely by preserving insertion
                # order -- see test_lane_groupings_are_sorted_by_layer_id.
                "result": {"calls": {}, "limits": [], "layers": [
                    {
                        "layer_id": "star-audit-targeted-candidates",
                        # A real lanes.json selected item for this grouping
                        # carries role/upstream_now (no catalog_pin) plus the
                        # fields build_manifest.py already copies through --
                        # see tools/sota-convergence/tests fixture parity
                        # with the private layer-verdicts-20260922 work
                        # directory's lanes.json.
                        "selected": [{
                            "repository": "https://github.com/example/star-audit-selected",
                            "status": "unmaintained_signal", "evidence": [],
                            "role": "source-control-reference (star-audit decision=overlaps_established)",
                            "upstream_now": {"archived": False, "license": "MIT",
                                              "pushed_at": "2020-01-01T00:00:00Z"},
                        }],
                        "alternatives_keep_but_compare": [],
                        "new_candidates": [{
                            "repository": "https://github.com/example/star-candidate",
                            "source": "s", "demonstrated_gap": "g", "proposed_label": "targeted_candidate",
                            "comparison_that_would_overturn": "c", "evidence": [],
                        }],
                        "open_gaps": [],
                    },
                    {
                        "layer_id": "awesome-list-convergence",
                        # A real lanes.json selected item for this grouping
                        # additionally carries role/catalog_pin (no
                        # upstream_now).
                        "selected": [{
                            "repository": "https://github.com/example/survey-tool",
                            "status": "confirmed_default", "evidence": [], "note": None,
                            "role": "awesome-list survey entry (star-audit decision=included)",
                            "catalog_pin": "1.0.0 (abc1234)",
                        }],
                        "alternatives_keep_but_compare": [],
                        "new_candidates": [{
                            "repository": "https://github.com/example/newcomer-beyond",
                            "source": "s", "demonstrated_gap": "g", "proposed_label": "keep_but_compare",
                            "comparison_that_would_overturn": "c", "evidence": [],
                        }],
                        "open_gaps": ["gap-beyond"],
                    },
                ]},
                "proposals": [{
                    "layer": "awesome-list-convergence", "repository": "https://github.com/example/newcomer-beyond",
                    "kind": "new_candidate", "survives": True,
                    "votes": [{"refuted": False, "confidence": 0.6, "reasoning": "plausible"}],
                }],
            }],
        }

    # Overridable by a subclass (see LaneItemPlacementTests) that needs a
    # foundation component under "found-a" to exercise a lane entry against.
    FOUND_A_COMPONENTS: list = []

    def build(self):
        foundation_layers = {"checked_at": "2026-01-01", "layers": [
            {"layer_id": "found-a", "title": "Found A", "components": self.FOUND_A_COMPONENTS},
        ]}
        trading_by_layer = {
            # Deliberately non-alphabetical taxonomy order to prove trading[]
            # follows taxonomy order, not sorted(layers).
            "taxonomy": {"layer-z": ["tag-z"], "layer-a": ["tag-a"]},
            "layers": {
                "layer-z": [{"id": "z-tool", "repository": "https://github.com/example/z-tool",
                              "decision": "default", "version_or_commit": "1.0.0", "layers": ["tag-z"]}],
                "layer-a": [{"id": "a-tool", "repository": "https://github.com/example/a-tool",
                              "decision": "default", "version_or_commit": "1.0.0", "layers": ["tag-a"]}],
            },
        }
        freshness_doc = {"count": 0, "generated_at": "2026-01-02T00:00:00+00:00", "repositories": {}}
        return build_manifest_mod.build_manifest(
            checked_at="2026-01-03", manifest_id="test-id", scope="s",
            foundation_layers=foundation_layers, trading_by_layer=trading_by_layer,
            freshness_doc=freshness_doc, lanes_doc=self._lanes_doc(), reconciliations=[],
            taxonomy=trading_by_layer["taxonomy"],
        )

    def test_trading_rows_are_exactly_the_taxonomy_ids_in_taxonomy_order(self):
        manifest = self.build()
        self.assertEqual([r["layer"] for r in manifest["trading"]], ["layer-z", "layer-a"])

    def test_non_taxonomy_lane_layers_are_not_trading_rows(self):
        manifest = self.build()
        trading_layer_ids = {r["layer"] for r in manifest["trading"]}
        self.assertNotIn("awesome-list-convergence", trading_layer_ids)
        self.assertNotIn("star-audit-targeted-candidates", trading_layer_ids)

    def test_non_taxonomy_lane_layer_reaches_lane_groupings_verbatim(self):
        manifest = self.build()
        groups = {g["layer"]: g for g in manifest["lane_groupings"]}
        self.assertEqual(set(groups), {"awesome-list-convergence", "star-audit-targeted-candidates"})
        group = groups["awesome-list-convergence"]
        self.assertEqual(group["lane"], "beyond")
        self.assertEqual(group["open_gaps"], ["gap-beyond"])
        self.assertEqual(len(group["selected"]), 1)
        self.assertEqual(group["selected"][0]["repository"], "https://github.com/example/survey-tool")
        self.assertEqual(group["selected"][0]["status"], "confirmed_default")
        # A real grouping-layer selected entry also carries role/catalog_pin
        # (and, for other grouping layers, upstream_now) -- these have no
        # baseline pin/upstream row to fall back on the way foundation/trading
        # rows do, so dropping them here is unrecoverable. See
        # test_every_selected_field_of_a_non_taxonomy_lane_layer_reaches_lane_groupings_verbatim
        # for the exhaustive, fixture-independent cross-check.
        self.assertEqual(group["selected"][0]["role"],
                          "awesome-list survey entry (star-audit decision=included)")
        self.assertEqual(group["selected"][0]["catalog_pin"], "1.0.0 (abc1234)")
        star_group = groups["star-audit-targeted-candidates"]
        self.assertEqual(len(star_group["selected"]), 1)
        self.assertEqual(star_group["selected"][0]["role"],
                          "source-control-reference (star-audit decision=overlaps_established)")
        self.assertEqual(star_group["selected"][0]["upstream_now"],
                          {"archived": False, "license": "MIT", "pushed_at": "2020-01-01T00:00:00Z"})

    def test_every_selected_field_of_a_non_taxonomy_lane_layer_reaches_lane_groupings_verbatim(self):
        # Cross-check every field the lanes document's own selected[] items
        # carry (not just the subset the implementation happens to emit)
        # survives into manifest["lane_groupings"][*]["selected"] verbatim --
        # analogous to the existing new_candidates cross-check below.
        lanes_doc = self._lanes_doc()
        known_layers = {"found-a", "layer-z", "layer-a"}
        expected = {}
        for lane in lanes_doc["lanes"]:
            for layer in lane["result"]["layers"]:
                if layer["layer_id"] in known_layers:
                    continue
                for selected in layer["selected"]:
                    expected[(layer["layer_id"], selected["repository"])] = dict(selected)
        self.assertTrue(expected, "fixture must actually exercise a non-taxonomy selected entry")
        manifest = self.build()
        actual = {}
        for group in manifest["lane_groupings"]:
            for entry in group["selected"]:
                actual[(group["layer"], entry["repository"])] = entry
        for key, expected_fields in expected.items():
            self.assertIn(key, actual)
            for field, value in expected_fields.items():
                self.assertEqual(actual[key].get(field), value, f"{key} field {field!r} dropped or changed")

    def test_lane_groupings_are_sorted_by_layer_id(self):
        manifest = self.build()
        self.assertEqual(
            [g["layer"] for g in manifest["lane_groupings"]],
            ["awesome-list-convergence", "star-audit-targeted-candidates"],
        )

    def test_every_new_candidate_of_a_non_taxonomy_lane_layer_appears_in_lane_groupings_with_its_disposition(self):
        # Nothing from a non-taxonomy grouping may be silently dropped:
        # cross-check merge_lanes' raw cands[] output against what actually
        # reached manifest["lane_groupings"].
        _, _, _, cands, _, _, _ = build_manifest_mod.merge_lanes(self._lanes_doc(), {})
        known_layers = {"found-a", "layer-z", "layer-a"}
        expected = {
            (layer_id, item["repository"]): item["disposition"]
            for layer_id, items in cands.items() if layer_id not in known_layers
            for item in items
        }
        self.assertTrue(expected, "fixture must actually exercise a non-taxonomy candidate")
        manifest = self.build()
        actual = {
            (group["layer"], candidate["repository"]): candidate["disposition"]
            for group in manifest["lane_groupings"] for candidate in group["candidates"]
        }
        self.assertEqual(actual, expected)

    def test_lane_grouping_candidates_are_excluded_from_candidates_total_but_counted_separately(self):
        manifest = self.build()
        self.assertEqual(manifest["counts"]["lane_groupings"], 2)
        self.assertEqual(manifest["counts"]["lane_grouping_candidates"], 2)
        # Neither taxonomy/foundation row in this fixture carries a candidate.
        self.assertEqual(manifest["counts"]["candidates_total"], 0)

    def test_manifest_key_order_places_lane_groupings_after_trading_and_before_critic(self):
        manifest = self.build()
        keys = list(manifest.keys())
        self.assertLess(keys.index("trading"), keys.index("lane_groupings"))
        self.assertLess(keys.index("lane_groupings"), keys.index("critic"))

    def test_counts_documents_trading_layers_semantics_distinctly_from_len_trading(self):
        # trading[] always has one row per taxonomy id (build_baseline_trading's
        # own docstring), including a taxonomy id with zero selected entries;
        # counts.trading_layers only counts rows that actually have entries.
        # That asymmetry (vs. foundation_layers, which counts every row) must
        # be documented in counts itself, the same way lane_groupings_note
        # documents the candidates_total scoping rule.
        manifest = self.build()
        self.assertIn("trading_layers_note", manifest["counts"])
        self.assertIn("entries", manifest["counts"]["trading_layers_note"])
        self.assertIn("len(manifest[\"trading\"]", manifest["counts"]["trading_layers_note"])


class OrphanTradingLayerTests(unittest.TestCase):
    """2026-09-22 third refresh: build_baseline_trading iterates
    trading_by_layer["taxonomy"], not trading_by_layer["layers"] (a
    deliberate change from the previous ``sorted(layers)`` iteration -- see
    build_baseline_trading's docstring). A layer id present in ``layers``
    but absent from ``taxonomy`` is not a lane-named grouping, so it is not
    recovered by lane_groupings either (that section is sourced from the
    lanes document, not from trading_by_layer) -- any selected ("default" or
    "conditional") entry under such an id would silently vanish from the
    manifest entirely. Assert this is refused rather than silently dropped."""

    def test_orphan_layer_with_a_selected_entry_is_refused_not_silently_dropped(self):
        trading_by_layer = {
            "taxonomy": {"layer-a": ["tag-a"]},
            "layers": {
                "layer-a": [{"id": "a-tool", "repository": "https://github.com/example/a-tool",
                              "decision": "default", "version_or_commit": "1.0.0", "layers": ["tag-a"]}],
                # Not listed in "taxonomy" above -- a catalog-only orphan.
                "orphan-layer": [{"id": "orphan-tool", "repository": "https://github.com/example/orphan-tool",
                                   "decision": "default", "version_or_commit": "1.0.0", "layers": ["tag-x"]}],
            },
        }
        with self.assertRaises(ValueError) as ctx:
            build_manifest_mod.build_baseline_trading(trading_by_layer, {})
        self.assertIn("orphan-layer", str(ctx.exception))

    def test_orphan_layer_with_only_non_selected_entries_is_not_refused(self):
        # An orphan layer whose entries are all "alternative"/"watch"/
        # "excluded" carries nothing that would be silently dropped (those
        # decisions are never promoted into a manifest row from any layer),
        # so this must not raise.
        trading_by_layer = {
            "taxonomy": {"layer-a": ["tag-a"]},
            "layers": {
                "layer-a": [{"id": "a-tool", "repository": "https://github.com/example/a-tool",
                              "decision": "default", "version_or_commit": "1.0.0", "layers": ["tag-a"]}],
                "orphan-layer": [{"id": "orphan-tool", "repository": "https://github.com/example/orphan-tool",
                                   "decision": "watch", "version_or_commit": "1.0.0", "layers": ["tag-x"]}],
            },
        }
        rows = build_manifest_mod.build_baseline_trading(trading_by_layer, {})
        self.assertEqual([r["layer"] for r in rows], ["layer-a"])

    def test_matching_layer_and_taxonomy_keys_do_not_raise(self):
        trading_by_layer = {
            "taxonomy": {"layer-a": ["tag-a"]},
            "layers": {"layer-a": [{"id": "a-tool", "repository": "https://github.com/example/a-tool",
                                     "decision": "default", "version_or_commit": "1.0.0", "layers": ["tag-a"]}]},
        }
        rows = build_manifest_mod.build_baseline_trading(trading_by_layer, {})
        self.assertEqual([r["layer"] for r in rows], ["layer-a"])


class SessionIdSanitizationTests(unittest.TestCase):
    """2026-09-22 second refresh, defect 2: lane text can cite a session-scoped
    /tmp/claude-<uid>/.../<uuid>/scratchpad/... path (Claude Code's own scratch
    directory), which the pre-fix sanitizer -- scoped to /home, /Users and
    Windows paths only -- did not touch, and scripts/validate.py's "local
    session identifier" check (scripts/validate.py line 27) then rejects."""

    # Exact duplicate of scripts/validate.py line 27's PRIVATE_CONTENT
    # "local session identifier" pattern, used here only to assert this
    # module's output would pass that publication check.
    VALIDATE_SESSION_ID_RE = re.compile(r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}", re.IGNORECASE)

    # Built from parts so the test source itself never carries a literal
    # session id or host path (scripts/validate.py hashes this file and
    # refuses either pattern in the tree).
    SESSION_ID = "-".join(["87433bef", "b807", "4b61", "bca6", "91ba1b410a57"])
    SCRATCH_PATH = "/".join(["/tmp/claude-1000", "-home-example-code-agent-lab", SESSION_ID,
                             "scratchpad/manifest/after-fix.json"])

    def test_tmp_scratchpad_session_path_is_sanitized_and_passes_validate_session_check(self):
        text = f'note: "{self.SCRATCH_PATH}" was read'
        cleaned = build_manifest_mod.sanitize(text)
        self.assertNotIn("/tmp/", cleaned)
        self.assertIsNone(self.VALIDATE_SESSION_ID_RE.search(cleaned))
        self.assertIn("<host-path>", cleaned)

    def test_git_sha_and_sha256_survive_sanitization_untouched(self):
        # Real 40-hex commit SHA (this repository's own 445bc83, resolved in
        # full -- `git rev-parse 445bc83`) so this is an actual 40-char
        # literal, not a 39-char string mislabelled as 40-hex.
        sha1 = "445bc83c942d2521cbc526565128d76c78f394bc"
        self.assertEqual(len(sha1), 40)
        sha256 = "a" * 64  # 64-hex digest, no dashes
        text = f"pin abc123 at {sha1}, checksum {sha256}"
        self.assertEqual(build_manifest_mod.sanitize(text), text)

    def test_dashed_non_hex_token_is_left_alone_by_the_session_uuid_scrub(self):
        # A near-miss: same 8-4-4-4-12 dash shape as a session UUID, but not
        # hex, so SESSION_UUID_RE must not match it -- proves the pattern is
        # actually hex-constrained, not just dash-shaped.
        near_miss = "gggggggg-gggg-gggg-gggg-gggggggggggg"
        text = f"ref {near_miss} unrelated"
        self.assertEqual(build_manifest_mod.sanitize(text), text)

    def test_a_real_uuid_shaped_token_is_scrubbed(self):
        # The positive case the near-miss above is contrasted against: a
        # genuine 8-4-4-4-12 hex UUID must be scrubbed.
        real_uuid = "-".join(["12345678", "90ab", "cdef", "1234", "567890abcdef"])
        text = f"session {real_uuid} was here"
        cleaned = build_manifest_mod.sanitize(text)
        self.assertNotIn(real_uuid, cleaned)
        self.assertIn("<session-id>", cleaned)

    def test_assert_no_leak_refuses_a_surviving_bare_uuid(self):
        # Defense in depth: even if a leak bypassed sanitize(), assert_no_leak
        # must independently refuse a bare session UUID.
        leaking = '{"note": "session ' + self.SESSION_ID + ' was here"}'
        with self.assertRaises(build_manifest_mod.LeakDetected):
            build_manifest_mod.assert_no_leak(leaking)

    def test_assert_no_leak_refuses_a_surviving_tmp_session_path_without_a_uuid(self):
        # Same defense-in-depth gap as above, but for the OTHER two markers
        # TMP_SESSION_PATH_RE redacts on (claude-<uid>, scratchpad) -- a
        # session-scoped /tmp path carrying neither of those AND no UUID
        # segment must still be refused if it somehow survives sanitize().
        leaking = '{"note": "read /tmp/claude-1000/some-project/scratchpad/notes.md before publishing"}'
        with self.assertRaises(build_manifest_mod.LeakDetected):
            build_manifest_mod.assert_no_leak(leaking)

    def test_sanitize_then_assert_no_leak_accepts_the_scratchpad_case(self):
        text = f'read "{self.SCRATCH_PATH}" before publishing'
        cleaned = build_manifest_mod.sanitize(text)
        build_manifest_mod.assert_no_leak(cleaned)  # must not raise

    def test_existing_home_path_sanitization_is_unaffected(self):
        text = 'note: "/home/example/code/x.json" was read'
        cleaned = build_manifest_mod.sanitize(text)
        self.assertNotIn("/home/", cleaned)
        self.assertIn("<host-path>", cleaned)

    def test_end_to_end_manifest_with_scratchpad_evidence_sanitizes_cleanly(self):
        foundation_layers = {"checked_at": "2026-01-01", "layers": [{
            "layer_id": "layer-a", "title": "Layer A", "components": [{
                "id": "comp", "repository": "https://github.com/example/comp", "version": "1.0.0",
            }],
        }]}
        trading_by_layer = {"taxonomy": {}, "layers": {}}
        freshness_doc = {"count": 0, "generated_at": "2026-01-02T00:00:00+00:00", "repositories": {}}
        scratch_evidence = f"read {self.SCRATCH_PATH.replace('after-fix.json', 'list.md')}"
        lanes_doc = {
            "critic": None,
            "lanes": [{
                "lane": "beyond",
                "result": {"calls": {}, "limits": [], "layers": [{
                    "layer_id": "layer-a", "selected": [{
                        "repository": "https://github.com/example/comp",
                        "status": "confirmed_default", "evidence": [scratch_evidence], "note": None,
                    }], "alternatives_keep_but_compare": [], "new_candidates": [], "open_gaps": [],
                }]},
                "proposals": [],
            }],
        }
        manifest = build_manifest_mod.build_manifest(
            checked_at="2026-01-03", manifest_id="test-id", scope="s",
            foundation_layers=foundation_layers, trading_by_layer=trading_by_layer,
            freshness_doc=freshness_doc, lanes_doc=lanes_doc, reconciliations=[],
            taxonomy={},
        )
        text = json.dumps(build_manifest_mod.sanitize_value(manifest), indent=1)
        json.loads(text)  # still valid JSON
        build_manifest_mod.assert_no_leak(text)  # must not raise
        self.assertNotIn("/tmp/", text)
        self.assertIsNone(self.VALIDATE_SESSION_ID_RE.search(text))


class LaneItemPlacementTests(LaneGroupingTests):
    """Where a lane's extra selected[] fields land depends on the row kind: a
    taxonomy row keeps its baseline pin/upstream and takes only
    why_selected/comparison_that_would_overturn; a lane_groupings row takes
    every lane-supplied field verbatim (it has no baseline)."""

    EXTRA = {
        "why_selected": "w", "comparison_that_would_overturn": "c",
        "role": "lane-role", "catalog_id": "z-tool", "catalog_pin": "9.9.9",
        "upstream_now": {"archived": False, "license": "MIT", "pushed_at": "2020-01-01T00:00:00Z"},
    }

    # T4 (2026-09-22 tooling citation review, finding 34): the foundation
    # half of "taxonomy row takes only ROW_LANE_FIELDS" had no fixture that
    # actually ran a lane item with the full EXTRA dict through the
    # foundation branch (build_manifest.py's foundation loop and trading
    # loop share the same ROW_LANE_FIELDS filter, but a test only exercising
    # trading leaves the foundation call site unguarded).
    FOUND_A_COMPONENTS = [
        {"id": "found-tool", "repository": "https://github.com/example/found-tool", "version": "1.0.0"},
    ]

    def _lanes_doc(self):
        doc = super()._lanes_doc()
        layers = doc["lanes"][0]["result"]["layers"]
        layers.append({
            "layer_id": "layer-z",
            "selected": [{"repository": "https://github.com/example/z-tool",
                          "status": "confirmed_default", "evidence": [], **self.EXTRA}],
            "alternatives_keep_but_compare": [], "new_candidates": [], "open_gaps": [],
        })
        layers[1]["selected"][0]["catalog_id"] = "survey-tool"
        layers.append({
            "layer_id": "found-a",
            "selected": [{"repository": "https://github.com/example/found-tool",
                          "status": "confirmed_default", "evidence": [],
                          **{**self.EXTRA, "catalog_id": "found-tool"}}],
            "alternatives_keep_but_compare": [], "new_candidates": [], "open_gaps": [],
        })
        return doc

    def test_taxonomy_row_takes_only_row_lane_fields(self):
        manifest = self.build()
        rows = {r["layer"]: r for r in manifest["trading"]}
        entry = rows["layer-z"]["entries"][0]
        self.assertEqual(entry["id"], "z-tool")
        self.assertEqual(entry["pin"], "1.0.0")
        self.assertEqual(entry["why_selected"], "w")
        self.assertEqual(entry["comparison_that_would_overturn"], "c")
        for field in ("role", "catalog_id", "catalog_pin", "upstream_now"):
            self.assertNotIn(field, entry, field)

    def test_foundation_row_takes_only_row_lane_fields(self):
        # T4: the foundation-row counterpart of test_taxonomy_row_takes_only_row_lane_fields.
        manifest = self.build()
        rows = {r["layer"]: r for r in manifest["foundation"]}
        component = rows["found-a"]["components"][0]
        self.assertEqual(component["id"], "found-tool")
        self.assertEqual(component["why_selected"], "w")
        self.assertEqual(component["comparison_that_would_overturn"], "c")
        for field in ("role", "catalog_id", "catalog_pin", "upstream_now"):
            self.assertNotIn(field, component, field)

    def test_lane_grouping_row_takes_every_lane_field_including_catalog_id(self):
        manifest = self.build()
        groups = {g["layer"]: g for g in manifest["lane_groupings"]}
        self.assertNotIn("layer-z", groups)
        selected = groups["awesome-list-convergence"]["selected"][0]
        self.assertEqual(selected["catalog_id"], "survey-tool")
        self.assertEqual(selected["catalog_pin"], "1.0.0 (abc1234)")
        self.assertEqual(selected["status"], "confirmed_default")

    def test_counts_note_names_both_scoped_counts(self):
        note = self.build()["counts"]["lane_groupings_note"]
        self.assertIn("candidates_total", note)
        self.assertIn("candidates_by_disposition", note)


class LaneReviewPrecedenceTests(unittest.TestCase):
    """G1 (2026-09-22 grand-catalog manifest review): a later lane's
    selected[] item for the same (layer, repository) must not silently
    overwrite an earlier lane's -- two lanes independently selecting the
    same component (e.g. a foundation-lane and a beyond-lane row for the
    same repository) is an observed real shape, not an error. Every lane's
    entry is kept; the row's own review_status/review_note/evidence/
    lane_item come from one entry chosen by a documented, deterministic
    precedence: (a) verified beats unverified, (b) among equals the lane
    that owns the catalog beats any other lane, (c) tie -> lexical lane
    name. Every other lane's entry survives on the row's
    other_lane_reviews[]; nothing is dropped."""

    def _lanes_doc(self, *, owner_status, owner_survives, other_status, other_survives):
        def proposals_for(status, survives):
            if survives is None:
                return []
            return [{"layer": "layer-a", "repository": "https://github.com/example/shared",
                      "kind": status, "survives": survives, "votes": [{"refuted": not survives}]}]

        return {
            "critic": None,
            "lanes": [
                {
                    "lane": "foundation",
                    "result": {"calls": {}, "limits": [], "layers": [{
                        "layer_id": "layer-a",
                        "selected": [{"repository": "https://github.com/example/shared", "status": owner_status,
                                      "evidence": ["foundation evidence"], "note": "foundation note"}],
                        "alternatives_keep_but_compare": [], "new_candidates": [], "open_gaps": [],
                    }]},
                    "proposals": proposals_for(owner_status, owner_survives),
                },
                {
                    "lane": "beyond",
                    "result": {"calls": {}, "limits": [], "layers": [{
                        "layer_id": "layer-a",
                        "selected": [{"repository": "https://github.com/example/shared", "status": other_status,
                                      "evidence": ["beyond evidence"], "note": "beyond note"}],
                        "alternatives_keep_but_compare": [], "new_candidates": [], "open_gaps": [],
                    }]},
                    "proposals": proposals_for(other_status, other_survives),
                },
            ],
        }

    def _build(self, lanes_doc):
        foundation_layers = {"checked_at": "2026-01-01", "layers": [{
            "layer_id": "layer-a", "title": "Layer A", "components": [
                {"id": "shared", "repository": "https://github.com/example/shared", "version": "1.0.0"},
            ],
        }]}
        freshness_doc = {"count": 0, "generated_at": "2026-01-02T00:00:00+00:00", "repositories": {}}
        return build_manifest_mod.build_manifest(
            checked_at="2026-01-03", manifest_id="test-id", scope="s",
            foundation_layers=foundation_layers, trading_by_layer={"taxonomy": {}, "layers": {}},
            freshness_doc=freshness_doc, lanes_doc=lanes_doc, reconciliations=[], taxonomy={},
        )

    def test_both_lanes_verified_the_owning_lane_wins_the_row(self):
        # foundation lane refuted (verified: survives False), beyond lane
        # survived (verified: survives True) -- tier (a) ties, tier (b)
        # (the foundation lane owns a foundation-layers.json layer) decides
        # it, even though beyond's own verdict survived. This is the real
        # headroom/token-efficiency defect this fixes: the row must stay
        # internally consistent with whichever lane it actually reflects.
        lanes_doc = self._lanes_doc(owner_status="pin_behind_upstream", owner_survives=False,
                                     other_status="pin_behind_upstream", other_survives=True)
        manifest = self._build(lanes_doc)
        component = manifest["foundation"][0]["components"][0]
        self.assertEqual(component["review_status"], "confirmed_pin")
        self.assertEqual(component["review_lane"], "foundation")
        self.assertTrue(any("refuted" in item for item in component["evidence"]))
        self.assertEqual(len(component["other_lane_reviews"]), 1)
        other = component["other_lane_reviews"][0]
        # The fixture's pin is not compared (no freshness record), so the
        # beyond lane's surviving pin_behind_upstream claim contradicts the
        # row's computed pin fields: it is published as pin_status_disputed,
        # the claim kept in disputed_lane_status and the evidence.
        self.assertEqual(other["lane"], "beyond")
        self.assertEqual(other["status"], "pin_status_disputed")
        self.assertEqual(other["disputed_lane_status"], "pin_behind_upstream")
        self.assertEqual(other["evidence"][0], "beyond evidence")
        self.assertIn("published as pin_status_disputed", other["evidence"][1])
        self.assertEqual((other["note"], other["lane_item"]), ("beyond note", {}))

    def test_verified_entry_beats_an_unverified_one_regardless_of_ownership(self):
        # foundation lane has no matching proposal at all (genuinely
        # unverified); beyond lane's verdict survived (verified) -- tier (a)
        # alone decides it, even though foundation would otherwise own the
        # layer.
        lanes_doc = self._lanes_doc(owner_status="confirmed_default", owner_survives=None,
                                     other_status="confirmed_default", other_survives=True)
        manifest = self._build(lanes_doc)
        component = manifest["foundation"][0]["components"][0]
        self.assertEqual(component["review_lane"], "beyond")
        self.assertEqual(component["other_lane_reviews"][0]["lane"], "foundation")

    def test_tie_falls_to_lexical_lane_name_when_neither_lane_owns_the_layer(self):
        # A lane_groupings row: neither lane "owns" a non-taxonomy layer id
        # (rule (b) is moot), so an equal-verified tie falls straight to
        # rule (c).
        lanes_doc = {
            "critic": None,
            "lanes": [
                {"lane": "trading", "result": {"calls": {}, "limits": [], "layers": [{
                    "layer_id": "custom-grouping",
                    "selected": [{"repository": "https://github.com/example/shared", "status": "confirmed_default",
                                  "evidence": [], "note": None}],
                    "alternatives_keep_but_compare": [], "new_candidates": [], "open_gaps": [],
                }]}, "proposals": []},
                {"lane": "beyond", "result": {"calls": {}, "limits": [], "layers": [{
                    "layer_id": "custom-grouping",
                    "selected": [{"repository": "https://github.com/example/shared", "status": "confirmed_default",
                                  "evidence": [], "note": None}],
                    "alternatives_keep_but_compare": [], "new_candidates": [], "open_gaps": [],
                }]}, "proposals": []},
            ],
        }
        manifest = self._build(lanes_doc)
        group = manifest["lane_groupings"][0]
        self.assertEqual(group["layer"], "custom-grouping")
        # Both unverified (no proposals at all) -- lexical: "beyond" < "trading".
        self.assertEqual(group["selected"][0]["review_lane"], "beyond")
        self.assertEqual(group["selected"][0]["other_lane_reviews"][0]["lane"], "trading")


class RefutedToConfirmedMarkerResolutionTests(unittest.TestCase):
    """G2: a refuted demotion_proposed/unmaintained_signal proposal must
    resolve to the component/entry's own governing baseline decision, never
    promoted past it -- a conditional-selection component promoted all the
    way to confirmed_default was the real defect (agentskills/skills-ref)."""

    def test_resolve_refuted_marker_maps_default_conditional_and_anything_else(self):
        marker = build_manifest_mod.REFUTED_TO_CONFIRMED_MARKER
        self.assertEqual(
            build_manifest_mod.resolve_refuted_marker(marker, row_kind="foundation", selection="default"),
            "confirmed_default")
        self.assertEqual(
            build_manifest_mod.resolve_refuted_marker(marker, row_kind="foundation", selection="conditional"),
            "confirmed_conditional")
        self.assertEqual(
            build_manifest_mod.resolve_refuted_marker(marker, row_kind="foundation", selection="optional"),
            "confirmed_selected")
        self.assertEqual(
            build_manifest_mod.resolve_refuted_marker(marker, row_kind="trading", decision="default"),
            "confirmed_default")
        self.assertEqual(
            build_manifest_mod.resolve_refuted_marker(marker, row_kind="trading", decision="conditional"),
            "confirmed_conditional")
        self.assertEqual(
            build_manifest_mod.resolve_refuted_marker(marker, row_kind="lane_groupings"),
            "confirmed_as_selected")
        # A non-marker value passes through unchanged.
        self.assertEqual(
            build_manifest_mod.resolve_refuted_marker("unmaintained_signal", row_kind="foundation"),
            "unmaintained_signal")

    def test_a_conditional_component_refuted_from_unmaintained_signal_resolves_to_confirmed_conditional_not_default(self):
        foundation_layers = {"checked_at": "2026-01-01", "layers": [{
            "layer_id": "layer-a", "title": "Layer A",
            "decisions": [{"id": "d1", "selection": "conditional", "component_ids": ["cond-tool"]}],
            "components": [
                {"id": "cond-tool", "repository": "https://github.com/example/cond-tool", "version": "1.0.0"},
            ],
        }]}
        freshness_doc = {"count": 0, "generated_at": "2026-01-02T00:00:00+00:00", "repositories": {}}
        lanes_doc = {
            "critic": None,
            "lanes": [{
                "lane": "foundation",
                "result": {"calls": {}, "limits": [], "layers": [{
                    "layer_id": "layer-a",
                    "selected": [{"repository": "https://github.com/example/cond-tool",
                                  "status": "unmaintained_signal", "evidence": [], "note": "stale"}],
                    "alternatives_keep_but_compare": [], "new_candidates": [], "open_gaps": [],
                }]},
                "proposals": [{"layer": "layer-a", "repository": "https://github.com/example/cond-tool",
                                "kind": "unmaintained_signal", "survives": False, "votes": [{"refuted": True}]}],
            }],
        }
        manifest = build_manifest_mod.build_manifest(
            checked_at="2026-01-03", manifest_id="test-id", scope="s",
            foundation_layers=foundation_layers, trading_by_layer={"taxonomy": {}, "layers": {}},
            freshness_doc=freshness_doc, lanes_doc=lanes_doc, reconciliations=[], taxonomy={},
        )
        component = manifest["foundation"][0]["components"][0]
        # Must NOT be promoted to confirmed_default -- the real defect.
        self.assertEqual(component["review_status"], "confirmed_conditional")

    def test_a_default_selection_trading_entry_refuted_from_demotion_proposed_resolves_to_confirmed_default(self):
        trading_by_layer = {
            "taxonomy": {"layer-b": ["tag-a"]},
            "layers": {"layer-b": [{"id": "def-tool", "repository": "https://github.com/example/def-tool",
                                     "decision": "default", "version_or_commit": "1.0.0", "layers": ["tag-a"]}]},
        }
        freshness_doc = {"count": 0, "generated_at": "2026-01-02T00:00:00+00:00", "repositories": {}}
        lanes_doc = {
            "critic": None,
            "lanes": [{
                "lane": "trading",
                "result": {"calls": {}, "limits": [], "layers": [{
                    "layer_id": "layer-b",
                    "selected": [{"repository": "https://github.com/example/def-tool",
                                  "status": "demotion_proposed", "evidence": [], "note": None}],
                    "alternatives_keep_but_compare": [], "new_candidates": [], "open_gaps": [],
                }]},
                "proposals": [{"layer": "layer-b", "repository": "https://github.com/example/def-tool",
                                "kind": "demotion_proposed", "survives": False, "votes": [{"refuted": True}]}],
            }],
        }
        manifest = build_manifest_mod.build_manifest(
            checked_at="2026-01-03", manifest_id="test-id", scope="s",
            foundation_layers={"layers": []}, trading_by_layer=trading_by_layer,
            freshness_doc=freshness_doc, lanes_doc=lanes_doc, reconciliations=[],
            taxonomy=trading_by_layer["taxonomy"],
        )
        entry = manifest["trading"][0]["entries"][0]
        self.assertEqual(entry["review_status"], "confirmed_default")

    def test_a_component_named_by_conflicting_decisions_resolves_to_the_most_restrictive_one_not_list_order(self):
        # G2 tiebreak, citation-review round: foundation_decision_selection_map
        # used to keep the FIRST-LISTED decision naming a component
        # (decisions[] order, via setdefault) -- so listing a "default"
        # decision before a stricter "conditional" one for the same
        # component let a refuted demotion resolve to confirmed_default,
        # promoting the component past the conditional decision that also
        # names it (the exact failure G2 exists to fix). The most
        # restrictive selection among ALL decisions naming the component
        # must win, regardless of decisions[] order.
        foundation_layers = {"checked_at": "2026-01-01", "layers": [{
            "layer_id": "layer-a", "title": "Layer A",
            "decisions": [
                {"id": "d1", "selection": "default", "component_ids": ["dual-tool"]},
                {"id": "d2", "selection": "conditional", "component_ids": ["dual-tool"]},
            ],
            "components": [
                {"id": "dual-tool", "repository": "https://github.com/example/dual-tool", "version": "1.0.0"},
            ],
        }]}
        freshness_doc = {"count": 0, "generated_at": "2026-01-02T00:00:00+00:00", "repositories": {}}
        lanes_doc = {
            "critic": None,
            "lanes": [{
                "lane": "foundation",
                "result": {"calls": {}, "limits": [], "layers": [{
                    "layer_id": "layer-a",
                    "selected": [{"repository": "https://github.com/example/dual-tool",
                                  "status": "unmaintained_signal", "evidence": [], "note": "stale"}],
                    "alternatives_keep_but_compare": [], "new_candidates": [], "open_gaps": [],
                }]},
                "proposals": [{"layer": "layer-a", "repository": "https://github.com/example/dual-tool",
                                "kind": "unmaintained_signal", "survives": False, "votes": [{"refuted": True}]}],
            }],
        }
        manifest = build_manifest_mod.build_manifest(
            checked_at="2026-01-03", manifest_id="test-id", scope="s",
            foundation_layers=foundation_layers, trading_by_layer={"taxonomy": {}, "layers": {}},
            freshness_doc=freshness_doc, lanes_doc=lanes_doc, reconciliations=[], taxonomy={},
        )
        component = manifest["foundation"][0]["components"][0]
        # Must resolve to the stricter "conditional" decision, not
        # "default" merely because it was listed first.
        self.assertEqual(component["review_status"], "confirmed_conditional")
        selection_map = build_manifest_mod.foundation_decision_selection_map(foundation_layers)
        self.assertEqual(selection_map[("layer-a", "dual-tool")], "conditional")


class CrossLayerVerdictSharingTests(unittest.TestCase):
    """G3: the same lane's adversarial verdict for a (repository, kind) is
    about the repository, not a particular layer -- when the same lane
    proposes the same status for the same repository in a second layer with
    no verdict of its own, the first layer's verdict applies there too (the
    real codex-for-claude defect: unmaintained_signal in git-github-
    automation, confirmed_default in workers, from one lane's one refuted
    proposal that only named "workers")."""

    def _build(self, *, second_layer_proposal=None):
        foundation_layers = {"checked_at": "2026-01-01", "layers": [
            {"layer_id": "layer-a", "title": "Layer A", "components": [
                {"id": "shared-tool", "repository": "https://github.com/example/shared-tool", "version": "1.0.0"},
            ]},
            {"layer_id": "layer-b", "title": "Layer B", "components": [
                {"id": "shared-tool", "repository": "https://github.com/example/shared-tool", "version": "1.0.0"},
            ]},
        ]}
        freshness_doc = {"count": 0, "generated_at": "2026-01-02T00:00:00+00:00", "repositories": {}}
        proposals = [{"layer": "layer-a", "repository": "https://github.com/example/shared-tool",
                       "kind": "unmaintained_signal", "survives": False, "votes": [{"refuted": True}]}]
        if second_layer_proposal is not None:
            proposals.append(second_layer_proposal)
        lanes_doc = {
            "critic": None,
            "lanes": [{
                "lane": "foundation",
                "result": {"calls": {}, "limits": [], "layers": [
                    {"layer_id": "layer-a", "selected": [
                        {"repository": "https://github.com/example/shared-tool", "status": "unmaintained_signal",
                         "evidence": [], "note": None}],
                     "alternatives_keep_but_compare": [], "new_candidates": [], "open_gaps": []},
                    {"layer_id": "layer-b", "selected": [
                        {"repository": "https://github.com/example/shared-tool", "status": "unmaintained_signal",
                         "evidence": [], "note": None}],
                     "alternatives_keep_but_compare": [], "new_candidates": [], "open_gaps": []},
                ]},
                "proposals": proposals,
            }],
        }
        return build_manifest_mod.build_manifest(
            checked_at="2026-01-03", manifest_id="test-id", scope="s",
            foundation_layers=foundation_layers, trading_by_layer={"taxonomy": {}, "layers": {}},
            freshness_doc=freshness_doc, lanes_doc=lanes_doc, reconciliations=[], taxonomy={},
        )

    def test_a_layer_with_no_verdict_of_its_own_inherits_the_lanes_verdict_from_the_other_layer(self):
        manifest = self._build()
        by_layer = {r["layer"]: r["components"][0] for r in manifest["foundation"]}
        # layer-a has its own (refuted) verdict; layer-b has none, so it
        # must resolve the SAME way, not stay "unmaintained_signal_unverified"
        # and must never contradict layer-a's class for the same repository.
        self.assertEqual(by_layer["layer-a"]["review_status"], by_layer["layer-b"]["review_status"])
        self.assertNotIn("unverified", by_layer["layer-b"]["review_status"])
        self.assertTrue(any("verdict shared from layer layer-a" in item for item in by_layer["layer-b"]["evidence"]))

    def test_a_layer_with_its_own_verdict_is_never_overridden_by_another_layers_verdict(self):
        # layer-b gets its OWN verdict (survives True -- the opposite
        # outcome of layer-a's); it must use that, not the shared one.
        manifest = self._build(second_layer_proposal={
            "layer": "layer-b", "repository": "https://github.com/example/shared-tool",
            "kind": "unmaintained_signal", "survives": True, "votes": [{"refuted": False}]})
        by_layer = {r["layer"]: r["components"][0] for r in manifest["foundation"]}
        self.assertNotEqual(by_layer["layer-a"]["review_status"], by_layer["layer-b"]["review_status"])
        self.assertEqual(by_layer["layer-b"]["review_status"], "unmaintained_signal")
        self.assertFalse(any("verdict shared" in item for item in by_layer["layer-b"]["evidence"]))


class MultiCardSameRepositoryKeyTests(unittest.TestCase):
    """G4: two cards sharing one repository in one layer (e.g. an
    execution-broker card and a data-role card for the same SDK) must not
    collapse onto one lane status -- the lane's own catalog_id disambiguates
    them (the real alpaca-py defect: the execution card published the data
    card's why_selected/evidence). An entry with no catalog_id still applies
    to every card sharing that repository, with a caveat note."""

    TRADING_BY_LAYER = {
        "taxonomy": {"layer-b": ["tag-a"]},
        "layers": {"layer-b": [
            {"id": "card-one", "repository": "https://github.com/example/shared-sdk",
             "decision": "default", "version_or_commit": "1.0.0", "layers": ["tag-a"]},
            {"id": "card-two", "repository": "https://github.com/example/shared-sdk",
             "decision": "default", "version_or_commit": "1.0.0", "layers": ["tag-a"]},
        ]},
    }

    def _build(self, selected):
        freshness_doc = {"count": 0, "generated_at": "2026-01-02T00:00:00+00:00", "repositories": {}}
        lanes_doc = {
            "critic": None,
            "lanes": [{
                "lane": "trading",
                "result": {"calls": {}, "limits": [], "layers": [{
                    "layer_id": "layer-b", "selected": selected,
                    "alternatives_keep_but_compare": [], "new_candidates": [], "open_gaps": [],
                }]},
                "proposals": [],
            }],
        }
        return build_manifest_mod.build_manifest(
            checked_at="2026-01-03", manifest_id="test-id", scope="s",
            foundation_layers={"layers": []}, trading_by_layer=self.TRADING_BY_LAYER,
            freshness_doc=freshness_doc, lanes_doc=lanes_doc, reconciliations=[],
            taxonomy=self.TRADING_BY_LAYER["taxonomy"],
        )

    def test_catalog_id_disambiguates_two_cards_sharing_one_repository(self):
        manifest = self._build([
            {"repository": "https://github.com/example/shared-sdk", "status": "confirmed_default",
             "evidence": ["card-one evidence"], "note": None, "catalog_id": "card-one", "why_selected": "role one"},
            {"repository": "https://github.com/example/shared-sdk", "status": "confirmed_default",
             "evidence": ["card-two evidence"], "note": None, "catalog_id": "card-two", "why_selected": "role two"},
        ])
        entries = {e["id"]: e for e in manifest["trading"][0]["entries"]}
        self.assertEqual(entries["card-one"]["why_selected"], "role one")
        self.assertEqual(entries["card-two"]["why_selected"], "role two")
        self.assertEqual(entries["card-one"]["evidence"], ["card-one evidence"])
        self.assertEqual(entries["card-two"]["evidence"], ["card-two evidence"])

    def test_an_entry_with_no_catalog_id_applies_to_every_sharing_card_with_a_caveat(self):
        manifest = self._build([
            {"repository": "https://github.com/example/shared-sdk", "status": "confirmed_default",
             "evidence": ["shared evidence"], "note": None},
        ])
        entries = {e["id"]: e for e in manifest["trading"][0]["entries"]}
        for card_id in ("card-one", "card-two"):
            self.assertIn("shared evidence", entries[card_id]["evidence"])
            self.assertTrue(any("matched by repository only; 2 cards share it" in item
                                 for item in entries[card_id]["evidence"]))

    def test_a_catalog_id_none_entry_from_another_lane_is_not_dropped_when_a_first_entry_matches_by_id(self):
        # G1 (citation-review round): match_lane_entries returns ONLY the
        # by-id match when one exists, and _build_card_row used to pass
        # only that `matched` list into select_row_review -- so a second
        # lane's entry for the SAME (layer, repository) that set no
        # catalog_id at all (and so never became the by-id match, nor the
        # by-repository fallback, since the fallback only runs when by-id
        # is empty) vanished from the manifest entirely: not chosen, not in
        # other_lane_reviews, not recoverable anywhere. Reproduces the real
        # trading/portfolio-risk/empyrical-reloaded case: the trading
        # lane's catalog_id='empyrical-reloaded' entry
        # (status=unmaintained_signal) silently deleted the beyond lane's
        # catalog_id=None entry (status=keep_but_compare, its own
        # why_selected) at the same (layer, repository) key.
        trading_by_layer = {
            "taxonomy": {"layer-b": ["tag-a"]},
            "layers": {"layer-b": [
                {"id": "solo-card", "repository": "https://github.com/example/shared-sdk",
                 "decision": "default", "version_or_commit": "1.0.0", "layers": ["tag-a"]},
            ]},
        }
        freshness_doc = {"count": 0, "generated_at": "2026-01-02T00:00:00+00:00", "repositories": {}}
        lanes_doc = {
            "critic": None,
            "lanes": [
                {"lane": "trading", "result": {"calls": {}, "limits": [], "layers": [{
                    "layer_id": "layer-b",
                    "selected": [{"repository": "https://github.com/example/shared-sdk",
                                  "status": "unmaintained_signal", "evidence": ["trading evidence"],
                                  "note": None, "catalog_id": "solo-card"}],
                    "alternatives_keep_but_compare": [], "new_candidates": [], "open_gaps": [],
                }]}, "proposals": []},
                {"lane": "beyond", "result": {"calls": {}, "limits": [], "layers": [{
                    "layer_id": "layer-b",
                    "selected": [{"repository": "https://github.com/example/shared-sdk",
                                  "status": "keep_but_compare", "evidence": ["beyond evidence"],
                                  "note": "beyond note", "why_selected": "beyond rationale"}],
                    "alternatives_keep_but_compare": [], "new_candidates": [], "open_gaps": [],
                }]}, "proposals": []},
            ],
        }
        manifest = build_manifest_mod.build_manifest(
            checked_at="2026-01-03", manifest_id="test-id", scope="s",
            foundation_layers={"layers": []}, trading_by_layer=trading_by_layer,
            freshness_doc=freshness_doc, lanes_doc=lanes_doc, reconciliations=[],
            taxonomy=trading_by_layer["taxonomy"],
        )
        entry = manifest["trading"][0]["entries"][0]
        self.assertEqual(entry["id"], "solo-card")
        # The trading lane owns the trading row, so it is still chosen.
        self.assertEqual(entry["review_status"], "unmaintained_signal")
        self.assertEqual(entry["review_lane"], "trading")
        # The beyond lane's catalog_id=None entry must survive somewhere
        # on the row -- never silently dropped.
        beyond_reviews = [o for o in entry.get("other_lane_reviews", []) if o["lane"] == "beyond"]
        self.assertEqual(len(beyond_reviews), 1,
                          "the beyond lane's catalog_id=None entry must not be dropped")
        self.assertEqual(beyond_reviews[0]["status"], "keep_but_compare")
        self.assertEqual(beyond_reviews[0]["lane_item"].get("why_selected"), "beyond rationale")


class PathBasenamePreservingSanitizationTests(unittest.TestCase):
    """G5: a redacted host path keeps its basename and any "#/json/pointer"
    suffix verbatim (223 evidence citations in a real manifest were
    unresolvable -- a bare "<host-path>" token alone -- before this fix); a
    path inside the private --work-dir resolves to "<work-dir>/basename"
    instead of the generic "<host-path>/basename"; a /tmp session-scratch
    path and a bare session UUID stay scrubbed exactly as before (no
    basename -- see sanitize()'s docstring)."""

    WORK_DIR = "/home/example/codex-ecosystem/state/layer-verdicts-20260922"

    def test_a_generic_host_path_keeps_its_basename(self):
        text = 'note: "/home/example/code/native-agent-stack/state/x.json" was read'
        cleaned = build_manifest_mod.sanitize(text)
        self.assertNotIn("/home/", cleaned)
        self.assertIn("<host-path>/x.json", cleaned)

    def test_a_path_inside_the_work_dir_uses_the_work_dir_token(self):
        text = f'note: "{self.WORK_DIR}/github-freshness.json" was read'
        cleaned = build_manifest_mod.sanitize(text, work_dir=self.WORK_DIR)
        self.assertIn("<work-dir>/github-freshness.json", cleaned)
        self.assertNotIn("<host-path>", cleaned)
        self.assertNotIn(self.WORK_DIR, cleaned)

    def test_a_path_outside_the_work_dir_still_uses_the_generic_token(self):
        text = 'note: "/home/example/some-other-project/x.json" was read'
        cleaned = build_manifest_mod.sanitize(text, work_dir=self.WORK_DIR)
        self.assertIn("<host-path>/x.json", cleaned)
        self.assertNotIn("<work-dir>", cleaned)

    def test_a_json_pointer_suffix_survives_verbatim(self):
        text = (f'evidence: {self.WORK_DIR}/github-freshness.json'
                '#/repositories/https:~1~1github.com~1example~1thing')
        cleaned = build_manifest_mod.sanitize(text, work_dir=self.WORK_DIR)
        self.assertIn(
            "<work-dir>/github-freshness.json#/repositories/https:~1~1github.com~1example~1thing", cleaned)

    def test_windows_and_macos_paths_also_keep_their_basename(self):
        for text, expected in (
            ('note: "/Users/example/code/x.json" was read', "<host-path>/x.json"),
            (r'note: "C:\Users\example\code\x.json" was read', "<host-path>/x.json"),
        ):
            with self.subTest(text=text):
                cleaned = build_manifest_mod.sanitize(text)
                self.assertIn(expected, cleaned)

    def test_tmp_session_scratch_paths_stay_a_bare_token_with_no_basename(self):
        # Unaffected by G5 -- a session-scoped scratch path is not a stable
        # citation target the way a file under the work directory is.
        scratch = "/tmp/claude-1000/-project/" + "-".join(
            ["87433bef", "b807", "4b61", "bca6", "91ba1b410a57"]) + "/scratchpad/notes.md"
        cleaned = build_manifest_mod.sanitize(f'read "{scratch}" before publishing')
        self.assertEqual(cleaned, 'read "<host-path>" before publishing')

    def test_sanitize_value_threads_work_dir_through_nested_structures(self):
        obj = {"evidence": [f"{self.WORK_DIR}/foundation-layers.json -> layers[0]"]}
        cleaned = build_manifest_mod.sanitize_value(obj, work_dir=self.WORK_DIR)
        self.assertEqual(cleaned["evidence"][0], "<work-dir>/foundation-layers.json -> layers[0]")


class CitationReviewOverlayTests(unittest.TestCase):
    """G6: an independent citation-review artifact's findings are resolved
    to the manifest row they name (data only -- never edits the row's own
    fields, e.g. why_selected) or, when no single row resolves, preserved in
    citation_review['general']; nothing is silently dropped."""

    TRADING_BY_LAYER = {
        "taxonomy": {"layer-b": ["tag-a"]},
        "layers": {"layer-b": [
            {"id": "card-one", "repository": "https://github.com/example/shared-sdk",
             "decision": "default", "version_or_commit": "1.0.0", "layers": ["tag-a"]},
            {"id": "data-card-one", "repository": "https://github.com/example/shared-sdk",
             "decision": "default", "version_or_commit": "1.0.0", "layers": ["tag-a"]},
        ]},
    }

    def _build(self, citation_review):
        foundation_layers = {"checked_at": "2026-01-01", "layers": [{
            "layer_id": "layer-a", "title": "Layer A", "components": [
                {"id": "alpha", "repository": "https://github.com/example/alpha", "version": "1.0.0"},
            ],
        }]}
        freshness_doc = {"count": 0, "generated_at": "2026-01-02T00:00:00+00:00", "repositories": {}}
        lanes_doc = {"critic": None, "lanes": []}
        return build_manifest_mod.build_manifest(
            checked_at="2026-01-03", manifest_id="test-id", scope="s",
            foundation_layers=foundation_layers, trading_by_layer=self.TRADING_BY_LAYER,
            freshness_doc=freshness_doc, lanes_doc=lanes_doc, reconciliations=[],
            taxonomy=self.TRADING_BY_LAYER["taxonomy"], citation_review=citation_review,
        )

    def test_a_finding_resolves_to_the_foundation_row_it_names(self):
        citation_review = {"findings": [{
            "reviewer": "foundationA", "catalog": "foundation", "severity": "high",
            "layer": "layer-a", "repository": "https://github.com/example/alpha",
            "file": "<host-path>", "line": 1, "claim": "alpha's evidence is contradictory",
            "evidence": "...", "fix": "fix alpha",
        }]}
        manifest = self._build(citation_review)
        component = manifest["foundation"][0]["components"][0]
        self.assertEqual(len(component["citation_review"]), 1)
        self.assertEqual(component["citation_review"][0]["claim"], "alpha's evidence is contradictory")
        # Row-attached findings carry the same citation locators (file,
        # line, evidence) as the general bucket -- not just
        # reviewer/severity/claim/fix -- so a row-attached finding stays
        # traceable back to its cited line (the asymmetry this fixes).
        self.assertEqual(component["citation_review"][0]["file"], "<host-path>")
        self.assertEqual(component["citation_review"][0]["line"], 1)
        self.assertEqual(component["citation_review"][0]["evidence"], "...")
        self.assertEqual(manifest["counts"]["citation_review"], {
            "findings_in_artifact": 1, "findings": 1, "out_of_scope": 0,
            "attached": 1, "rows_flagged": 1, "general": 0,
        })

    def test_a_substring_colliding_card_id_does_not_cross_match_its_sibling(self):
        # "card-one" is a substring of "data-card-one"; a finding naming
        # "card-one" must resolve to card-one only, never its sibling too.
        citation_review = {"findings": [{
            "reviewer": "trading", "catalog": "trading", "severity": "high",
            "layer": "layer-b", "repository": "https://github.com/example/shared-sdk",
            "file": "<host-path>", "line": 1,
            "claim": "Row layer-b/card-one carries the wrong sibling's why_selected.",
            "evidence": "...", "fix": "fix card-one",
        }]}
        manifest = self._build(citation_review)
        entries = {e["id"]: e for e in manifest["trading"][0]["entries"]}
        self.assertIn("citation_review", entries["card-one"])
        self.assertNotIn("citation_review", entries["data-card-one"])

    def test_a_finding_naming_only_the_longer_sibling_id_resolves_to_it_not_general(self):
        # The reverse collision direction: "card-one" is a hyphen-adjacent
        # substring of "data-card-one" (the '-' either side of it is a
        # non-word character, so a naive `\bcard-one\b` match still fires
        # inside "data-card-one"). A finding naming ONLY the longer sibling
        # id must resolve to it alone -- not degrade to
        # citation_review.general because the naive match also produced a
        # spurious second id_matches hit for "card-one".
        citation_review = {"findings": [{
            "reviewer": "trading", "catalog": "trading", "severity": "low",
            "layer": "layer-b", "repository": "https://github.com/example/shared-sdk",
            "file": "<host-path>", "line": 5,
            "claim": "Row layer-b/data-card-one carries the wrong evidence.",
            "evidence": "...", "fix": "fix data-card-one",
        }]}
        manifest = self._build(citation_review)
        entries = {e["id"]: e for e in manifest["trading"][0]["entries"]}
        self.assertIn("citation_review", entries["data-card-one"])
        self.assertNotIn("citation_review", entries["card-one"])
        self.assertEqual(manifest["citation_review"]["general"], [])

    def test_a_slug_naming_only_the_longer_sibling_repository_resolves_to_it_not_general(self):
        # Same class of collision as the id-matching fix, in the slug
        # fallback branch: "example/alpha" is a hyphen-adjacent substring
        # of "example/alpha-extended" (the naive `in` check used by the
        # slug branch has no boundary protection at all). A finding
        # naming only the longer sibling repository must resolve to it
        # alone, not degrade to general because the shorter sibling's slug
        # also spuriously substring-matches.
        citation_review = {"findings": [{
            "reviewer": "foundationC", "catalog": "foundation", "severity": "medium",
            "layer": "layer-c", "repository": "https://github.com/example/alpha-extended",
            "file": "<host-path>", "line": 9,
            "claim": "The alpha-extended integration is undocumented.",
            "evidence": "...", "fix": "...",
        }]}
        foundation_layers = {"checked_at": "2026-01-01", "layers": [
            {"layer_id": "layer-a", "title": "Layer A", "components": [
                {"id": "alpha", "repository": "https://github.com/example/alpha", "version": "1.0.0"},
            ]},
            {"layer_id": "layer-c", "title": "Layer C", "components": [
                {"id": "widget-a", "repository": "https://github.com/example/alpha", "version": "1.0.0"},
                {"id": "widget-b", "repository": "https://github.com/example/alpha-extended", "version": "1.0.0"},
            ]},
        ]}
        freshness_doc = {"count": 0, "generated_at": "2026-01-02T00:00:00+00:00", "repositories": {}}
        lanes_doc = {"critic": None, "lanes": []}
        manifest = build_manifest_mod.build_manifest(
            checked_at="2026-01-03", manifest_id="test-id", scope="s",
            foundation_layers=foundation_layers, trading_by_layer=self.TRADING_BY_LAYER,
            freshness_doc=freshness_doc, lanes_doc=lanes_doc, reconciliations=[],
            taxonomy=self.TRADING_BY_LAYER["taxonomy"], citation_review=citation_review,
        )
        layer_c = next(r for r in manifest["foundation"] if r["layer"] == "layer-c")
        components = {c["id"]: c for c in layer_c["components"]}
        self.assertIn("citation_review", components["widget-b"])
        self.assertNotIn("citation_review", components["widget-a"])
        self.assertEqual(manifest["citation_review"]["general"], [])

    def test_a_candidate_only_finding_quoting_a_card_id_stays_in_general(self):
        # Round-2 regression (critic.uncited_claims[16]): the finding names a
        # lane candidate's repository (not a card in the layer) and has no
        # component; its claim quotes a card id ("card-one") in passing.
        # It must not attach to that card.
        citation_review = {"findings": [{
            "reviewer": "critic-citations", "catalog": "trading", "severity": "low",
            "layer": "layer-b", "repository": "https://github.com/other/candidate, https://github.com/other/second",
            "file": None, "line": None,
            "claim": "Candidate other/candidate says card-one already covers this, uncited.",
            "evidence": "...", "fix": "...",
        }]}
        manifest = self._build(citation_review)
        entries = {e["id"]: e for e in manifest["trading"][0]["entries"]}
        self.assertNotIn("citation_review", entries["card-one"])
        self.assertEqual([f["claim"] for f in manifest["citation_review"]["general"]],
                         ["Candidate other/candidate says card-one already covers this, uncited."])
        self.assertEqual(manifest["counts"]["citation_review"], {
            "findings_in_artifact": 1, "findings": 1, "out_of_scope": 0,
            "attached": 0, "rows_flagged": 0, "general": 1,
        })

    def test_names_only_a_candidate_is_false_for_card_repositories_components_and_non_urls(self):
        layer_row = {"layer": "l", "entries": [
            {"id": "card-one", "repository": "https://github.com/Example/Shared-SDK"}]}
        f = build_manifest_mod._names_only_a_candidate
        self.assertTrue(f({"repository": "https://github.com/other/candidate"}, layer_row))
        self.assertFalse(f({"repository": "https://github.com/example/shared-sdk.git"}, layer_row))
        self.assertFalse(f({"repository": "https://github.com/other/candidate, https://github.com/example/shared-sdk"}, layer_row))
        self.assertFalse(f({"repository": "https://github.com/other/candidate", "component": "card-one"}, layer_row))
        self.assertFalse(f({"repository": "n/a (manifest-wide)"}, layer_row))
        self.assertFalse(f({}, layer_row))

    def test_a_finding_naming_no_resolvable_row_goes_to_general_and_is_not_dropped(self):
        citation_review = {"findings": [{
            "reviewer": "foundationB", "catalog": "foundation", "severity": "low",
            "layer": "all in-scope layers", "repository": "n/a (manifest-wide)",
            "file": "<host-path>", "line": 1, "claim": "A manifest-wide observation",
            "evidence": "...", "fix": "...",
        }]}
        manifest = self._build(citation_review)
        self.assertEqual(len(manifest["citation_review"]["general"]), 1)
        self.assertEqual(manifest["citation_review"]["general"][0]["claim"], "A manifest-wide observation")
        self.assertEqual(manifest["counts"]["citation_review"], {
            "findings_in_artifact": 1, "findings": 1, "out_of_scope": 0,
            "attached": 0, "rows_flagged": 0, "general": 1,
        })

    def test_a_tooling_catalog_finding_is_ignored_entirely(self):
        citation_review = {"findings": [{
            "reviewer": "tooling", "catalog": "tooling", "severity": "low",
            "layer": "docs", "repository": "nas-wt-pr5-manifest",
            "file": "<host-path>", "line": 1, "claim": "A tooling-only finding",
            "evidence": "...", "fix": "...",
        }]}
        manifest = self._build(citation_review)
        self.assertEqual(manifest["citation_review"]["general"], [])
        self.assertEqual(manifest["counts"]["citation_review"], {
            "findings_in_artifact": 1, "findings": 0, "out_of_scope": 1,
            "attached": 0, "rows_flagged": 0, "general": 0,
        })

    def test_counts_citation_review_reconciles_against_the_artifact_total(self):
        # The published counts must be reconcilable against the artifact
        # alone: findings_in_artifact = findings + out_of_scope, and
        # findings = attached + general.
        citation_review = {"findings": [
            {"reviewer": "foundationA", "catalog": "foundation", "severity": "high",
             "layer": "layer-a", "repository": "https://github.com/example/alpha",
             "file": "<host-path>", "line": 1, "claim": "alpha finding one", "evidence": "e1", "fix": "f1"},
            {"reviewer": "foundationB", "catalog": "foundation", "severity": "medium",
             "layer": "layer-a", "repository": "https://github.com/example/alpha",
             "file": "<host-path>", "line": 2, "claim": "alpha finding two", "evidence": "e2", "fix": "f2"},
            {"reviewer": "tooling", "catalog": "tooling", "severity": "low",
             "layer": "docs", "repository": "nas-wt-pr5-manifest",
             "file": "<host-path>", "line": 3, "claim": "a tooling finding", "evidence": "e3", "fix": "f3"},
        ]}
        manifest = self._build(citation_review)
        counts = manifest["counts"]["citation_review"]
        self.assertEqual(counts["findings_in_artifact"], 3)
        self.assertEqual(counts["findings"], 2)
        self.assertEqual(counts["out_of_scope"], 1)
        self.assertEqual(counts["findings_in_artifact"], counts["findings"] + counts["out_of_scope"])
        self.assertEqual(counts["findings"], counts["attached"] + counts["general"])
        # Both findings target the same card -- attached (2) exceeds
        # rows_flagged (1 distinct row) -- exactly the gap the finding
        # says was previously unreconcilable from the manifest alone.
        self.assertEqual(counts["attached"], 2)
        self.assertEqual(counts["rows_flagged"], 1)
        self.assertEqual(counts["general"], 0)

    def test_a_layer_slash_component_style_layer_field_resolves_by_its_first_segment(self):
        citation_review = {"findings": [{
            "reviewer": "foundationA", "catalog": "foundation", "severity": "medium",
            "layer": "layer-a/some-component", "repository": "https://github.com/example/alpha",
            "file": "<host-path>", "line": 1, "claim": "alpha again",
            "evidence": "...", "fix": "...",
        }]}
        manifest = self._build(citation_review)
        component = manifest["foundation"][0]["components"][0]
        self.assertEqual(len(component["citation_review"]), 1)

    def test_no_citation_review_flag_still_produces_the_key_with_zero_counts(self):
        manifest = self._build(None)
        self.assertEqual(manifest["citation_review"], {"general": []})
        self.assertEqual(manifest["counts"]["citation_review"], {
            "findings_in_artifact": 0, "findings": 0, "out_of_scope": 0,
            "attached": 0, "rows_flagged": 0, "general": 0,
        })

    def test_manifest_key_order_places_citation_review_after_lane_groupings_and_before_critic(self):
        manifest = self._build(None)
        keys = list(manifest.keys())
        self.assertLess(keys.index("lane_groupings"), keys.index("citation_review"))
        self.assertLess(keys.index("citation_review"), keys.index("critic"))


class LaneGroupingsNoteCompletenessTests(unittest.TestCase):
    """T5 (citation-review round): counts.lane_groupings_note claims to
    enumerate "every foundation/trading-scoped count above" but omitted
    counts.citation_review -- also computed only over manifest['foundation']
    + manifest['trading'] rows (G6, added in the same change), so a
    lane_groupings[].selected row can never be counted in
    citation_review.rows_flagged either, the same exclusion the note
    already claims for its other listed counts."""

    def test_lane_groupings_note_names_citation_review(self):
        freshness_doc = {"count": 0, "generated_at": "2026-01-02T00:00:00+00:00", "repositories": {}}
        lanes_doc = {"critic": None, "lanes": []}
        manifest = build_manifest_mod.build_manifest(
            checked_at="2026-01-03", manifest_id="test-id", scope="s",
            foundation_layers={"layers": []}, trading_by_layer={"taxonomy": {}, "layers": {}},
            freshness_doc=freshness_doc, lanes_doc=lanes_doc, reconciliations=[], taxonomy={},
        )
        note = manifest["counts"]["lane_groupings_note"]
        self.assertIn("citation_review", note)


class RecheckResidualTests(unittest.TestCase):
    """Two residuals from the merge-rules recheck: a card-specific lane entry
    is never folded under a different card's other_lane_reviews, and a
    home-directory root never republishes the username as a basename."""

    REPO = "https://github.com/example/alpaca-py"

    def _entry(self, lane, catalog_id, why):
        return {"lane": lane, "catalog_id": catalog_id, "status": "confirmed_default", "verified": False,
                "evidence": [], "note": None, "lane_item": {"why_selected": why}}

    def test_other_card_entry_is_not_folded_into_this_cards_row(self):
        entries = [self._entry("trading", "exec-card", "execution rationale"),
                   self._entry("trading", "data-card", "data rationale"),
                   self._entry("beyond", None, "card-less rationale")]
        status = {("L", self.REPO): {"entries": entries}}
        row = build_manifest_mod._build_card_row(
            {"id": "exec-card", "repository": self.REPO}, layer_id="L", status=status, row_kind="trading",
            repo_counts={self.REPO: 2}, decision="default", base_fields={"id": "exec-card", "repository": self.REPO})
        self.assertEqual(row["why_selected"], "execution rationale")
        others = row.get("other_lane_reviews", [])
        self.assertEqual(len(others), 1)
        self.assertEqual(others[0]["lane"], "beyond")
        data_row = build_manifest_mod._build_card_row(
            {"id": "data-card", "repository": self.REPO}, layer_id="L", status=status, row_kind="trading",
            repo_counts={self.REPO: 2}, decision="default", base_fields={"id": "data-card", "repository": self.REPO})
        self.assertEqual(data_row["why_selected"], "data rationale")
        self.assertEqual([o["lane"] for o in data_row.get("other_lane_reviews", [])], ["beyond"])

    def test_home_root_never_republishes_the_username(self):
        home_root = "/home/" + "exampleuser"
        self.assertEqual(build_manifest_mod.sanitize("see " + home_root + " now"), "see <host-path> now")
        self.assertEqual(build_manifest_mod.sanitize("see /Users/" + "exampleuser" + "/ now"), "see <host-path> now")
        self.assertEqual(build_manifest_mod.sanitize("read " + home_root + "/code/x.json#/a/0"),
                         "read <host-path>/x.json#/a/0")
        self.assertNotIn("exampleuser", build_manifest_mod.sanitize(home_root + "#/p"))



class CitationReview20260923GeneratorFixTests(unittest.TestCase):
    """Generator defects from the 2026-09-23 independent citation review
    (evidence/artifacts/sota-convergence-review-20260923/
    manifest-citation-review.json, catalog "tooling", generator_defect true)."""

    def _build(self, *, foundation_components=(), trading_entries=(), lanes=(), repositories=None,
               citation_review=None, trading_layer="layer-t", foundation_layer="layer-f"):
        foundation_layers = {"checked_at": "2026-01-01", "layers": [{
            "layer_id": foundation_layer, "title": "F", "components": list(foundation_components)}]}
        trading_by_layer = {"taxonomy": {trading_layer: ["tag"]},
                            "layers": {trading_layer: list(trading_entries)}}
        freshness_doc = {"count": 0, "generated_at": "2026-01-02T00:00:00+00:00",
                         "repositories": repositories or {}}
        return build_manifest_mod.build_manifest(
            checked_at="2026-01-03", manifest_id="test-id", scope="s",
            foundation_layers=foundation_layers, trading_by_layer=trading_by_layer,
            freshness_doc=freshness_doc, lanes_doc={"critic": None, "lanes": list(lanes)},
            reconciliations=[], taxonomy=trading_by_layer["taxonomy"], citation_review=citation_review,
        )

    @staticmethod
    def _lane(lane, layer_id, selected, proposals=()):
        return {"lane": lane, "result": {"calls": {}, "limits": [], "layers": [{
            "layer_id": layer_id, "selected": list(selected), "alternatives_keep_but_compare": [],
            "new_candidates": [], "open_gaps": []}]}, "proposals": list(proposals)}

    # Defect 1 (high, two reviewers): the lane-entry-to-card join.
    def test_card_with_tree_or_release_tag_url_keeps_the_lane_review_of_the_plain_url(self):
        plain_f = "https://github.com/example/plugin"
        plain_t = "https://github.com/example/markdown-tool"
        lanes = [
            self._lane("foundation", "layer-f", [{
                "repository": plain_f, "status": "unmaintained_signal", "evidence": ["gh api repos/example/plugin"],
                "note": "stale", "why_selected": "bridge", "comparison_that_would_overturn": "a replay"}],
                # The proposal cites the /tree/ alias; the join is by slug on both sides.
                proposals=[{"layer": "layer-f", "repository": plain_f + "/tree/v1.0.6", "kind": "unmaintained_signal",
                            "survives": True, "votes": [{"refuted": False}, {"refuted": False}]}]),
            self._lane("trading", "layer-t", [{
                "repository": plain_t, "status": "pin_behind_upstream", "evidence": ["receipt"],
                "note": None, "why_selected": "converter", "comparison_that_would_overturn": "a corpus"}]),
        ]
        manifest = self._build(
            foundation_components=[{"id": "plugin", "repository": plain_f + "/tree/v1.0.6", "version": "1.0.6"}],
            trading_entries=[{"id": "markdown-tool", "repository": plain_t + "/releases/tag/v0.1.7",
                              "decision": "default", "version_or_commit": "0.1.7", "layers": ["tag"]}],
            # A newer upstream release, so the lane's pin_behind_upstream
            # status agrees with the row's computed pin fields.
            lanes=lanes, repositories={plain_t: {"latest_release": {"tag": "v0.2.0"}}})
        component = manifest["foundation"][0]["components"][0]
        self.assertEqual(component["review_status"], "unmaintained_signal")
        self.assertEqual(component["review_lane"], "foundation")
        self.assertIn("gh api repos/example/plugin", component["evidence"])
        self.assertEqual(component["why_selected"], "bridge")
        self.assertEqual(component["comparison_that_would_overturn"], "a replay")
        entry = manifest["trading"][0]["entries"][0]
        self.assertEqual(entry["review_status"], "pin_behind_upstream")
        self.assertEqual(entry["evidence"], ["receipt"])
        self.assertEqual(entry["why_selected"], "converter")
        self.assertEqual(entry["comparison_that_would_overturn"], "a corpus")

    def test_the_exact_string_status_index_is_unchanged_for_direct_merge_lanes_callers(self):
        repo = "https://github.com/example/plugin"
        status = build_manifest_mod.merge_lanes({"lanes": [self._lane("foundation", "layer-f", [
            {"repository": repo, "status": "confirmed_default", "evidence": []}])]}, {})[0]
        self.assertIn(("layer-f", repo), status)
        index = build_manifest_mod.index_status_by_join_key(status)
        self.assertIn(("layer-f", "example/plugin"), index)

    def test_lane_groupings_join_alias_urls_and_publish_a_url_the_lane_cited(self):
        repo = "https://github.com/example/ref"
        lanes = [self._lane("beyond", "reference-material", [
            {"repository": repo + "/tree/main", "status": "confirmed_default", "evidence": ["a"]}]),
                 self._lane("zeta", "reference-material", [
            {"repository": repo, "status": "confirmed_default", "evidence": ["b"]}])]
        manifest = self._build(lanes=lanes)
        selected = manifest["lane_groupings"][0]["selected"]
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["repository"], repo + "/tree/main")
        self.assertEqual([o["lane"] for o in selected[0]["other_lane_reviews"]], ["zeta"])

    # Defect 2 (medium + low): checkout paths keep their repository-relative path.
    def test_checkout_paths_keep_the_repository_relative_path_and_distinct_readmes_stay_distinct(self):
        checkout = "/home/example/code/catalog-checkout"
        text = (f"see {checkout}/blueprints/us-equities/broad-universe/README.md and "
                f"{checkout}/catalogs/us-equities/README.md and "
                f"{checkout}/manifests/stack.json#/components/3 and /home/example/elsewhere/README.md")
        cleaned = build_manifest_mod.sanitize(text, checkout_roots=[checkout])
        self.assertEqual(cleaned, "see blueprints/us-equities/broad-universe/README.md and "
                                  "catalogs/us-equities/README.md and manifests/stack.json#/components/3 "
                                  "and <host-path>/README.md")
        build_manifest_mod.assert_no_leak(cleaned)

    def test_the_checkout_root_itself_becomes_a_token_and_trailing_punctuation_survives(self):
        checkout = "/home/example/code/catalog-checkout"
        cleaned = build_manifest_mod.sanitize(f"worktree {checkout}), then {checkout}.", checkout_roots=[checkout])
        self.assertEqual(cleaned, "worktree <checkout>), then <checkout>.")
        # A sibling directory sharing the prefix is not inside the checkout.
        self.assertEqual(build_manifest_mod.sanitize(f"{checkout}-old/x.md", checkout_roots=[checkout]),
                         "<host-path>/x.md")

    def test_work_dir_precedes_checkout_and_no_roots_keeps_the_previous_redaction(self):
        work_dir = "/home/example/state/run"
        self.assertEqual(build_manifest_mod.sanitize(f"{work_dir}/lanes.json", work_dir=work_dir,
                                                     checkout_roots=["/home/example/state"]),
                         "<work-dir>/lanes.json")
        self.assertEqual(build_manifest_mod.sanitize("/home/example/code/c/manifests/stack.json"),
                         "<host-path>/stack.json")

    def test_cli_defaults_the_checkout_root_to_this_repository(self):
        args = build_manifest_mod.parse_args(["--lanes", "l.json", "--out", "o.json", "--checked-at", "d",
                                              "--id", "i"])
        self.assertIsNone(args.checkout_roots)
        self.assertEqual(build_manifest_mod.REPO_ROOT, ROOT)

    # Defect 3 (low): a pin that was not compared is never published as false.
    def test_uncompared_pins_publish_not_compared_instead_of_false(self):
        repositories = {"https://github.com/example/{}".format(name): {"latest_release": {"tag": "v2.2.1"}}
                        for name in ("sha-pinned", "dev-pinned", "released")}
        manifest = self._build(foundation_components=[
            {"id": "sha-pinned", "repository": "https://github.com/example/sha-pinned", "version": "dd6ee538"},
            {"id": "dev-pinned", "repository": "https://github.com/example/dev-pinned", "version": "2.0.0.dev0 @ c6fbd1c"},
            {"id": "released", "repository": "https://github.com/example/released", "version": "2.2.1"},
            {"id": "off-github", "repository": "https://gitlab.com/example/x", "version": "1.0.0"},
        ], repositories=repositories)
        rows = {c["id"]: c for c in manifest["foundation"][0]["components"]}
        for card_id, reason in (("sha-pinned", "unversioned"), ("dev-pinned", "commit_pinned"),
                                ("off-github", "non_github_or_os_package")):
            self.assertIsNone(rows[card_id]["pin_behind_upstream"], card_id)
            self.assertEqual(rows[card_id]["pin_comparison"], "not_compared", card_id)
            self.assertEqual(rows[card_id]["pin_comparison_reason"], reason, card_id)
        self.assertIs(rows["released"]["pin_behind_upstream"], False)
        self.assertEqual(rows["released"]["pin_comparison"], "compared")
        self.assertNotIn("pin_comparison_reason", rows["released"])
        self.assertEqual(manifest["counts"]["pins_not_compared"], 3)
        self.assertEqual(manifest["counts"]["pins_not_compared_by_reason"],
                         {"commit_pinned": 1, "non_github_or_os_package": 1, "unversioned": 1})

    # Defect 4 (low): an OS-package pin's review_status never says pin_behind_upstream.
    def test_distro_package_pin_review_status_is_distro_managed_not_pin_behind_upstream(self):
        repo = "https://github.com/systemd/systemd"
        lanes = [self._lane("foundation", "layer-f", [
            {"repository": repo, "status": "pin_behind_upstream", "evidence": ["v261.3 upstream"]}]),
                 self._lane("beyond", "layer-f", [
            {"repository": repo, "status": "pin_behind_upstream", "evidence": ["beyond"]}])]
        manifest = self._build(
            foundation_components=[{"id": "systemd", "repository": repo, "version": "255.4-1ubuntu8.17"}],
            lanes=lanes, repositories={repo: {"latest_release": {"tag": "v261.3"}}})
        row = manifest["foundation"][0]["components"][0]
        self.assertIsNone(row["pin_behind_upstream"])
        self.assertEqual(row["pin_comparison_reason"], "os_package_pin")
        self.assertEqual(row["review_status"], "distro_managed")
        self.assertIn("v261.3 upstream", row["evidence"])
        self.assertTrue(any("published as distro_managed" in item for item in row["evidence"]))
        self.assertEqual(row["other_lane_reviews"][0]["status"], "distro_managed")

    def test_distro_mapping_keeps_the_unverified_suffix_and_leaves_other_rows_alone(self):
        self.assertEqual(build_manifest_mod.reconcile_status_with_pin(
            "pin_behind_upstream_unverified", {"pin_comparison_reason": "os_package_pin"})[0],
            "distro_managed_unverified")
        self.assertEqual(build_manifest_mod.reconcile_status_with_pin(
            "pin_behind_upstream", {"pin_comparison": "compared"}), ("pin_behind_upstream", None))
        self.assertEqual(build_manifest_mod.reconcile_status_with_pin(
            "confirmed_default", {"pin_comparison_reason": "os_package_pin"}), ("confirmed_default", None))

    # Defect 5 (low): a non-version tag from the tag listing is flagged, not published as latest.
    def test_tag_only_non_version_tag_is_flagged_not_published_as_latest(self):
        repo = "https://github.com/postgres/postgres"
        upstream = build_manifest_mod.compute_upstream(repo, {repo: {"latest_tag": "release-6-3"}})
        self.assertIsNone(upstream["latest"])
        self.assertEqual(upstream["latest_flag"], {"tag": "release-6-3",
                                                   "reason": "tag_listing_only_not_version_shaped"})
        manifest = self._build(foundation_components=[{"id": "postgresql", "repository": repo, "version": "18.1"}],
                               repositories={repo: {"latest_tag": "release-6-3"}})
        row = manifest["foundation"][0]["components"][0]
        self.assertIsNone(row["upstream"]["latest"])
        self.assertEqual(row["pin_comparison"], "not_compared")
        # A version-shaped tag-only fallback and a release are unchanged.
        tagged = build_manifest_mod.compute_upstream(repo, {repo: {"latest_tag": "v3.2.0"}})
        self.assertEqual(tagged["latest"], "v3.2.0")
        self.assertNotIn("latest_flag", tagged)
        released = build_manifest_mod.compute_upstream(repo, {repo: {"latest_release": {"tag": "nightly"}}})
        self.assertEqual(released["latest"], "nightly")
        self.assertNotIn("latest_flag", released)

    # Review-schema component field: a multi-layer, multi-component finding
    # attaches to every row it names instead of falling into general.
    def test_component_field_finding_attaches_to_every_named_row(self):
        manifest = self._build(
            foundation_components=[{"id": "alpha", "repository": "https://github.com/example/alpha", "version": "1"},
                                   {"id": "alpha-extended", "repository": "https://github.com/example/ae", "version": "1"}],
            trading_entries=[{"id": "data-alpha", "repository": "https://github.com/example/da",
                              "decision": "default", "version_or_commit": "1", "layers": ["tag"]}],
            citation_review={"findings": [
                {"catalog": "foundation", "layer": "layer-f, other-layer", "component": "alpha (plus notes)",
                 "reviewer": "r", "severity": "low", "claim": "c1", "fix": "f", "evidence": "e"},
                {"catalog": "trading", "layer": "multiple", "component": "data-alpha, absent-card",
                 "reviewer": "r", "severity": "low", "claim": "c2", "fix": "f", "evidence": "e"},
                {"catalog": "trading", "layer": "multiple", "component": "absent-card",
                 "reviewer": "r", "severity": "low", "claim": "c3", "fix": "f", "evidence": "e"},
            ]})
        rows = {c["id"]: c for c in manifest["foundation"][0]["components"]}
        self.assertEqual([f["claim"] for f in rows["alpha"]["citation_review"]], ["c1"])
        self.assertEqual(rows["alpha"]["citation_review"][0]["component"], "alpha (plus notes)")
        self.assertNotIn("citation_review", rows["alpha-extended"])
        self.assertEqual([f["claim"] for f in manifest["trading"][0]["entries"][0]["citation_review"]], ["c2"])
        self.assertEqual([f["claim"] for f in manifest["citation_review"]["general"]], ["c3"])
        self.assertEqual(manifest["counts"]["citation_review"], {
            "findings_in_artifact": 3, "findings": 3, "out_of_scope": 0,
            "attached": 2, "rows_flagged": 2, "general": 1})


class PinStatusDisputeTests(unittest.TestCase):
    """2026-09-23 critic-gap recheck of b273544: no published row may show a
    lane pin status that contradicts the row's own computed pin fields
    (phoenix, opensandbox, lean-alpaca, inspect-ai). Such a claim is published
    as pin_status_disputed[_unverified], the lane's claim kept in
    disputed_lane_status and the evidence, and the counts reconcile."""

    # Reuse the fixture builders without inheriting (and re-running) that
    # class's own tests.
    _build = CitationReview20260923GeneratorFixTests._build
    _lane = staticmethod(CitationReview20260923GeneratorFixTests._lane)

    REPO = "https://github.com/example/tool"

    def _row(self, *, status, version, latest, proposals=(), lanes_extra=()):
        lanes = [self._lane("trading", "layer-t", [
            {"repository": self.REPO, "status": status, "evidence": ["lane evidence"]}], proposals=proposals),
                 *lanes_extra]
        repositories = {self.REPO: {"latest_release": {"tag": latest}}} if latest else {}
        manifest = self._build(
            trading_entries=[{"id": "tool", "repository": self.REPO, "decision": "conditional",
                              "version_or_commit": version, "layers": ["tag"]}],
            lanes=lanes, repositories=repositories)
        return manifest, manifest["trading"][0]["entries"][0]

    def assert_consistent(self, manifest):
        for row in manifest["trading"]:
            for card in row["entries"]:
                statuses = [(card["review_status"], card.get("disputed_lane_status"))] + [
                    (review["status"], review.get("disputed_lane_status"))
                    for review in card.get("other_lane_reviews", [])]
                for status, _claim in statuses:
                    if status in build_manifest_mod.PIN_BEHIND_STATUSES:
                        self.assertIs(card["pin_behind_upstream"], True, card["id"])
        counts = manifest["counts"]
        self.assertEqual(sum(counts["pins_behind_upstream_by_review_status"].values()),
                         counts["pins_behind_upstream"])
        self.assertEqual(counts["review_status_pin_behind_upstream"], sum(
            n for status, n in counts["pins_behind_upstream_by_review_status"].items()
            if status in build_manifest_mod.PIN_BEHIND_STATUSES))

    def test_pin_behind_claim_on_a_compared_current_pin_is_disputed(self):  # phoenix
        manifest, row = self._row(status="pin_behind_upstream", version="20.14.0", latest="v20.14.0")
        self.assertIs(row["pin_behind_upstream"], False)
        self.assertEqual(row["review_status"], "pin_status_disputed")
        self.assertEqual(row["disputed_lane_status"], "pin_behind_upstream")
        self.assertEqual(row["evidence"][0], "lane evidence")
        self.assertIn("trading lane status pin_behind_upstream published as pin_status_disputed",
                      row["evidence"][-1])
        self.assertIn("pin_behind_upstream false, pin_comparison compared", row["evidence"][-1])
        self.assertEqual(manifest["counts"]["pin_status_disputed"], 1)
        self.assertEqual(manifest["counts"]["pin_status_disputed_by_lane_status"], {"pin_behind_upstream": 1})
        self.assertEqual(manifest["counts"]["review_status_pin_behind_upstream"], 0)
        self.assert_consistent(manifest)

    def test_pin_behind_claim_on_a_pin_that_was_not_compared_is_disputed(self):  # lean-alpaca, inspect-ai
        manifest, row = self._row(status="pin_behind_upstream", version="1973f6165bee", latest=None)
        self.assertIsNone(row["pin_behind_upstream"])
        self.assertEqual(row["review_status"], "pin_status_disputed")
        self.assertIn("pin_comparison_reason unversioned", row["evidence"][-1])
        self.assert_consistent(manifest)

    def test_unverified_suffix_is_kept(self):
        manifest, row = self._row(status="pin_behind_upstream", version="2.0.0", latest="v2.0.0", proposals=[
            {"layer": "layer-t", "repository": self.REPO, "kind": "pin_behind_upstream", "survives": None,
             "votes": []}])
        self.assertEqual(row["review_status"], "pin_status_disputed_unverified")
        self.assertEqual(row["disputed_lane_status"], "pin_behind_upstream_unverified")
        self.assert_consistent(manifest)

    def test_confirmed_claim_on_a_pin_computed_behind_is_disputed(self):  # opensandbox
        manifest, row = self._row(status="confirmed_conditional", version="0.2.3", latest="v1.1.0")
        self.assertIs(row["pin_behind_upstream"], True)
        self.assertEqual(row["review_status"], "pin_status_disputed")
        self.assertEqual(row["disputed_lane_status"], "confirmed_conditional")
        self.assertEqual(manifest["counts"]["pins_behind_upstream_by_review_status"], {"pin_status_disputed": 1})
        self.assert_consistent(manifest)

    def test_refuted_pin_claim_confirmed_pin_on_a_pin_computed_behind_is_disputed(self):
        manifest, row = self._row(status="pin_behind_upstream", version="1.0.0", latest="v1.1.0", proposals=[
            {"layer": "layer-t", "repository": self.REPO, "kind": "pin_behind_upstream", "survives": False,
             "votes": [{"refuted": True}]}])
        self.assertEqual(row["review_status"], "pin_status_disputed")
        self.assertEqual(row["disputed_lane_status"], "confirmed_pin")

    def test_consistent_claims_and_refuted_demotions_are_unchanged(self):
        manifest, row = self._row(status="pin_behind_upstream", version="1.0.0", latest="v1.1.0")
        self.assertEqual(row["review_status"], "pin_behind_upstream")
        self.assertNotIn("disputed_lane_status", row)
        self.assertEqual(manifest["counts"]["review_status_pin_behind_upstream"], 1)
        self.assert_consistent(manifest)
        # A refuted demotion confirms the selection only; it makes no pin claim.
        manifest, row = self._row(status="demotion_proposed", version="1.0.0", latest="v1.1.0", proposals=[
            {"layer": "layer-t", "repository": self.REPO, "kind": "demotion_proposed", "survives": False,
             "votes": [{"refuted": True}]}])
        self.assertEqual(row["review_status"], "confirmed_conditional")
        self.assertEqual(manifest["counts"]["pin_status_disputed"], 0)

    def test_other_lane_reviews_are_reconciled_too(self):
        manifest, row = self._row(status="pin_behind_upstream", version="1.0.0", latest="v1.0.0", lanes_extra=[
            self._lane("beyond", "layer-t", [{"repository": self.REPO, "status": "confirmed_default",
                                              "evidence": ["beyond evidence"]}])])
        self.assertEqual(row["review_status"], "pin_status_disputed")
        other = row["other_lane_reviews"][0]
        self.assertEqual((other["lane"], other["status"]), ("beyond", "confirmed_default"))
        manifest, row = self._row(status="confirmed_default", version="1.0.0", latest="v1.0.0", lanes_extra=[
            self._lane("beyond", "layer-t", [{"repository": self.REPO, "status": "pin_behind_upstream",
                                              "evidence": ["beyond evidence"]}])])
        self.assertEqual(row["review_status"], "confirmed_default")
        other = row["other_lane_reviews"][0]
        self.assertEqual(other["status"], "pin_status_disputed")
        self.assertEqual(other["disputed_lane_status"], "pin_behind_upstream")
        self.assertIn("beyond lane status pin_behind_upstream", other["evidence"][-1])
        self.assertEqual(manifest["counts"]["other_lane_reviews_pin_status_disputed"], 1)
        self.assert_consistent(manifest)

    def test_direct_reconcile_calls(self):
        reconcile = build_manifest_mod.reconcile_status_with_pin
        self.assertEqual(reconcile("pin_behind_upstream", {"pin_behind_upstream": True}), ("pin_behind_upstream", None))
        self.assertEqual(reconcile("confirmed_default", {"pin_behind_upstream": True},
                                   lane_status="refuted_to_confirmed"), ("confirmed_default", None))
        self.assertEqual(reconcile("keep_but_compare", {"pin_behind_upstream": None})[0], "keep_but_compare")
        self.assertEqual(reconcile("confirmed_pin", {"pin_behind_upstream": True})[0], "pin_status_disputed")
        # Without the computed field there is no pin state to contradict.
        self.assertEqual(reconcile("pin_behind_upstream", {}), ("pin_behind_upstream", None))


class UnmatchedLaneItemsTests(unittest.TestCase):
    """2026-09-23 critic-gap recheck of b273544: a lane selected[] item at a
    foundation/trading layer that matches no card was silently dropped (10
    of critic-models-sources' 22, including a surviving all-MiniLM-L6-v2
    demotion). It is now published under unmatched_lane_items and counted."""

    # Reuse the fixture builders without inheriting (and re-running) that
    # class's own tests.
    _build = CitationReview20260923GeneratorFixTests._build
    _lane = staticmethod(CitationReview20260923GeneratorFixTests._lane)

    def test_items_without_a_card_are_published_not_dropped(self):
        card_repo = "https://github.com/example/card"
        lanes = [
            self._lane("critic-models-sources", "layer-f", [
                {"repository": "https://huggingface.co/example/minilm", "status": "demotion_proposed",
                 "evidence": ["model card"], "note": "demote", "why_selected": "w"},
                {"repository": card_repo, "status": "pin_behind_upstream", "evidence": ["x"],
                 "catalog_id": "absent-card"},
                {"repository": card_repo, "status": "confirmed_default", "evidence": ["y"]},
            ], proposals=[{"layer": "layer-f", "repository": "https://huggingface.co/example/minilm",
                           "kind": "demotion_proposed", "survives": True,
                           "votes": [{"refuted": False}, {"refuted": False}]}]),
            self._lane("beyond", "own-grouping", [
                {"repository": "https://github.com/example/grouped", "status": "keep_but_compare",
                 "evidence": []}]),
        ]
        manifest = self._build(
            foundation_components=[{"id": "card", "repository": card_repo, "version": "1.0.0"}], lanes=lanes)
        items = manifest["unmatched_lane_items"]
        self.assertEqual([(i["repository"], i["reason"]) for i in items], [
            ("https://github.com/example/card", "catalog_id_names_no_card"),
            ("https://huggingface.co/example/minilm", "no_card_with_repository_in_layer")])
        minilm = items[1]
        self.assertEqual((minilm["catalog"], minilm["layer"], minilm["lane"], minilm["status"], minilm["survives"]),
                         ("foundation", "layer-f", "critic-models-sources", "demotion_proposed", True))
        self.assertEqual((minilm["evidence"], minilm["note"], minilm["lane_item"]),
                         (["model card"], "demote", {"why_selected": "w"}))
        self.assertEqual(items[0]["catalog_id"], "absent-card")
        self.assertIsNone(items[0]["survives"])
        # The matched item and the lane_groupings item are not listed.
        self.assertEqual(manifest["foundation"][0]["components"][0]["review_status"], "confirmed_default")
        self.assertEqual(manifest["lane_groupings"][0]["layer"], "own-grouping")
        self.assertEqual(manifest["counts"]["unmatched_lane_items"], 2)
        self.assertEqual(manifest["counts"]["unmatched_lane_items_by_lane"], {"critic-models-sources": 2})
        keys = list(manifest)
        self.assertLess(keys.index("lane_groupings"), keys.index("unmatched_lane_items"))
        self.assertLess(keys.index("unmatched_lane_items"), keys.index("citation_review"))

    def test_every_lane_item_is_published_somewhere(self):
        repo = "https://github.com/example/card"
        lanes = [self._lane(lane, "layer-f", [{"repository": repo, "status": "confirmed_default",
                                                "evidence": [], "catalog_id": catalog_id}])
                 for lane, catalog_id in (("a", "card"), ("b", None), ("c", "other"), ("d", "gone"))]
        manifest = self._build(foundation_components=[
            {"id": "card", "repository": repo, "version": "1"}, {"id": "other", "repository": repo, "version": "1"}],
            lanes=lanes)
        published = []
        for card in manifest["foundation"][0]["components"]:
            published += [card["review_lane"]] + [r["lane"] for r in card.get("other_lane_reviews", [])]
        self.assertEqual(sorted(set(published)), ["a", "b", "c"])
        self.assertEqual([i["lane"] for i in manifest["unmatched_lane_items"]], ["d"])

    def test_general_findings_sort_with_mixed_line_types(self):
        manifest = self._build(citation_review={"findings": [
            {"catalog": "trading", "layer": "absent", "reviewer": "r", "claim": "a", "line": 12},
            {"catalog": "trading", "layer": "absent", "reviewer": "r", "claim": "b", "line": "594 at a275ebc"},
            {"catalog": "trading", "layer": "absent", "reviewer": "r", "claim": "c", "line": None}]})
        self.assertEqual([f["claim"] for f in manifest["citation_review"]["general"]], ["c", "a", "b"])


if __name__ == "__main__":
    unittest.main()
