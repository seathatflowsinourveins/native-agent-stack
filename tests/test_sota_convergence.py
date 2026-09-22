"""Synthetic-fixture tests for tools/sota-convergence. No network, no real catalogs.

Modules are loaded by file path (tools/sota-convergence is not a dotted-import
package name) and skipped cleanly if a required stdlib module is unexpectedly
absent from the interpreter under test.
"""
import importlib.util
import json
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
        self.assertEqual(reparsed["note"], 'read "<host-path>" before publishing')

    def test_sanitize_value_walks_nested_lists_and_dicts(self):
        obj = {"evidence": ["/home/example/a.json", {"nested": "/Users/example/b.json"}], "count": 3, "ok": None}
        cleaned = build_manifest_mod.sanitize_value(obj)
        self.assertEqual(cleaned["evidence"][0], "<host-path>")
        self.assertEqual(cleaned["evidence"][1]["nested"], "<host-path>")
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

    def test_unmaintained_signal_with_survives_false_is_confirmed_default_with_a_refuted_note(self):
        status, notes, alts, cands, gaps, calls, limits = build_manifest_mod.merge_lanes(
            self._lanes_doc(False, [{"refuted": True, "confidence": 0.9, "reasoning": "still maintained"}]), {})
        key = ("layer-a", "https://github.com/example/fredapi")
        self.assertEqual(status[key]["status"], "confirmed_default")
        self.assertTrue(any("refuted" in item for item in notes.get(key, [])))

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


if __name__ == "__main__":
    unittest.main()
