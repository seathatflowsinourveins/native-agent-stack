"""Consumer-facing checks for the offline public ecosystem explorer."""

import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "scripts/build_ecosystem.py"


class Page(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.scripts = []
        self.external_assets = []
        self.data = ""
        self.reading_data = False
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "script":
            self.scripts.append(attrs)
            self.reading_data = attrs.get("id") == "ecosystem-data"
        if tag in {"script", "img", "iframe", "link"}:
            url = attrs.get("src", attrs.get("href", ""))
            if url and not url.startswith("data:"):
                self.external_assets.append(url)

    def handle_endtag(self, tag):
        if tag == "script":
            self.reading_data = False

    def handle_data(self, data):
        if self.reading_data:
            self.data += data


class EcosystemManifestTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.config = {
            "schema_version": 1, "snapshot_date": "2026-09-20",
            "repository_url": "https://github.com/example/public-stack",
            "source_revision": "a" * 40,
            "layers": [
                {"id": "retrieval", "name": "Retrieval", "summary": "Selected context",
                 "keywords": ["retrieval"], "repositories": []},
                {"id": "beyond", "name": "Beyond", "summary": "Other work",
                 "keywords": [], "repositories": []},
            ],
            "policies": [], "guides": [], "highlights": [], "annotations": [],
        }
        self.records = [
            {"repository": "https://github.com/example/search", "aliases": [],
             "public_star": True, "record_types": ["star_review", "component_record"],
             "references": [
                 {"kind": "star_review", "path": "catalogs/review.json", "pointer": "/entries/0",
                  "review_level": "source_review"},
                 {"kind": "component_record", "path": "manifests/stack.json",
                  "pointer": "/components/0"}]},
            {"repository": "https://github.com/example/idea", "aliases": [],
             "public_star": False, "record_types": ["research_supplement"],
             "references": [{"kind": "research_supplement", "path": "catalogs/review.json",
                             "pointer": "/entries/1"}]},
        ]
        self.review = {"checked_at": "2026-09-19", "entries": [
            {"repository": "example/search", "role": "Scoped retrieval", "decision": "retain",
             "review_level": "source_review", "source_commit": "b" * 40,
             "sources": ["https://github.com/example/search/blob/main/README.md"]},
            {"repository": "example/idea", "role": "Unverified idea", "decision": "investigate"},
        ]}
        self.stack = {"recorded_at_utc": "2026-09-18", "components": [
            {"id": "search", "repository": "https://github.com/example/search", "version": "1.0",
             "role": "Scoped retrieval", "evidence_ids": ["historical-only"], "license": "MIT"}
        ]}
        self.evidence = {"receipts": [
            {"id": "historical-only", "kind": "historical_inventory",
             "path": "evidence/history.json", "claim": "Version was recorded",
             "limitations": ["No useful execution"], "component_ids": ["search"]}
        ], "files": []}
        self.adoption = {"default_profile": "foundation", "recipe_map": {"search": "recipes/search.md"},
                         "profiles": [{"id": "foundation", "label": "Foundation",
                                       "component_ids": ["search"], "required_commands": ["search"]}],
                         "supported_platforms": [{"os": "linux", "architecture": "x86_64"}]}
        self.saturation = {"recorded_date_utc": "2026-09-20", "scope": "Historical fixture audit",
                           "components": []}
        self.token_ids = ["token-practice-native-counters-20260920", "native-jcodemunch-20260920",
                          "native-headroom-mcp-20260920", "token-practice-catalog-toon-20260920",
                          "native-token-focus-clients-20260920"]
        for identifier in self.token_ids:
            path = "evidence/" + identifier + ".json"
            self.evidence["receipts"].append({"id": identifier, "path": path,
                "kind": "historical_inventory", "claim": "Dated token evidence",
                "component_ids": [], "limitations": ["Not a new host's acceptance"]})
            self.write(path, {"id": identifier, "data": {"saved_estimate": 12}})
        for path in ("recipes/search.md", "adoption/README.md", "adoption/update.md",
                     "tools/token-report/README.md"):
            self.write(path, "# Native recipe\n\n```sh\nsearch --native\n```\n")
        self.save()
        self.write("docs/ecosystem/template.html", "<!doctype html><html><body>@@BODY@@"
                   '<script id="ecosystem-data" type="application/json">@@DATA@@</script>'
                   '<script>"use strict";</script></body></html>')
        self.write("evidence/history.json", {"recorded_at": "2026-09-18"})

    def write(self, path, value):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(value) if not isinstance(value, str) else value,
                          encoding="utf-8")

    def save(self):
        self.write("docs/ecosystem/manifest.json", self.config)
        self.write("catalogs/us-equities/decision-index.json", {"records": self.records})
        self.write("manifests/stack.json", self.stack)
        self.write("manifests/evidence.json", self.evidence)
        self.write("adoption/manifest.json", self.adoption)
        self.write("blueprints/token-native-focus/saturation-audit.json", self.saturation)
        self.write("catalogs/review.json", self.review)
        self.write("catalogs/convergence-practice/public-starred.json", {
            "retrieved_at": "2026-09-20T00:00:00Z", "count": 1, "repositories": [
                {"repository": "example/search", "description": "Search", "topics": ["retrieval"]}]})
        self.write("catalogs/convergence-practice/source-review.json", {"awesome_sources": []})

    def run_generator(self, *extra):
        return subprocess.run([sys.executable, str(GENERATOR), "--root", str(self.root), *extra],
                              capture_output=True, text=True, timeout=15)

    def build(self):
        result = self.run_generator("--write")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        text = (self.root / "docs/ecosystem/index.html").read_text()
        return Page(text), text

    def test_public_filter_data_preserves_review_without_inventing_execution(self):
        page, _ = self.build()
        data = json.loads(page.data)
        search, idea = data["repositories"]
        self.assertEqual(search.get("repository_id"), "example/search")
        self.assertEqual(search["layers"], ["retrieval"])
        self.assertTrue(search["starred"])
        self.assertTrue(search["source_reviewed"])
        self.assertFalse(search["executed"])
        self.assertEqual(search["live_status"], "Unknown on this browser's host")
        self.assertFalse(idea["source_reviewed"])
        self.assertEqual(idea["layers"], ["beyond"])
        self.assertEqual(data["counts"]["stars"], 1)

    def test_useful_execution_requires_a_linked_receipt_and_keeps_limits(self):
        self.evidence["receipts"][0].update(kind="native_cli_e2e", claim="Exact query returned",
                                             limitations=["One historical fixture only"])
        self.save()
        page, _ = self.build()
        record = json.loads(page.data)["repositories"][0]
        self.assertTrue(record["executed"])
        self.assertEqual(record["receipts"][0]["limitations"], ["One historical fixture only"])
        self.assertEqual(record["live_status"], "Unknown on this browser's host")

    def test_untrusted_source_text_cannot_close_data_script_or_load_an_asset(self):
        hostile = '</script><script src="https://invalid.example/steal.js"></script>&\u2028'
        self.review["entries"][0]["role"] = hostile
        self.review["entries"][0]["sources"] = ["javascript:alert(1)", "https://good.example/docs"]
        self.save()
        page, text = self.build()
        self.assertEqual(len(page.scripts), 2)
        self.assertEqual(page.external_assets, [])
        record = json.loads(page.data)["repositories"][0]
        self.assertEqual(record["description"], hostile)
        self.assertNotIn('href="javascript:', text)
        self.assertNotIn("javascript:alert", page.data)
        self.assertIn("https://good.example/docs", page.data)

    def test_canonical_public_repository_urls_reject_credentials_or_script_schemes(self):
        for bad in ["javascript:alert(1)", "https://user:secret@github.com/example/idea"]:
            with self.subTest(url=bad):
                self.records[1]["repository"] = bad
                self.save()
                result = self.run_generator("--write")
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse((self.root / "docs/ecosystem/index.html").exists())

    def test_source_pointer_cannot_escape_or_follow_a_symlink(self):
        for path in ["../outside.json", "catalogs/linked.json"]:
            with self.subTest(path=path):
                if path.endswith("linked.json"):
                    (self.root / path).symlink_to(self.root / "catalogs/review.json")
                self.records[0]["references"][0]["path"] = path
                self.save()
                self.assertNotEqual(self.run_generator("--write").returncode, 0)

    def test_duplicate_identities_and_unresolved_pointers_fail_before_publication(self):
        self.records.append(self.records[0])
        self.save()
        self.assertNotEqual(self.run_generator("--write").returncode, 0)
        self.records.pop()
        self.records[0]["references"][0]["pointer"] = "/entries/99"
        self.save()
        self.assertNotEqual(self.run_generator("--write").returncode, 0)

    def test_rebuild_check_detects_changed_source_and_changed_generated_bytes(self):
        self.build()
        self.assertEqual(self.run_generator("--check").returncode, 0)
        self.review["entries"][0]["role"] = "Corrected scope"
        self.save()
        self.assertNotEqual(self.run_generator("--check").returncode, 0)
        self.build()
        output = self.root / "docs/ecosystem/index.html"
        output.write_text(output.read_text() + "tampered")
        self.assertNotEqual(self.run_generator("--check").returncode, 0)

    def test_input_hashes_and_section_hash_avoid_evidence_self_reference(self):
        page, first = self.build()
        sources = json.loads(page.data)["inputs"]
        review = next(row for row in sources if row["path"] == "catalogs/review.json")
        self.assertEqual(review["sha256"], hashlib.sha256(
            (self.root / "catalogs/review.json").read_bytes()).hexdigest())
        self.evidence["files"] = [{"path": "docs/ecosystem/index.html", "sha256": "changed"}]
        self.save()
        _, second = self.build()
        self.assertEqual(first, second)

    def test_new_integration_is_searchable_without_recounting_the_repository_union(self):
        self.config["integrations"] = [{
            "id": "search-service", "name": "New search service", "description": "Bounded web search",
            "layers": ["retrieval"], "status": "Dated native observation", "date": "2026-09-20",
            "pin": "0.1.8", "url": "https://service.example/docs",
            "receipt_path": "docs/ecosystem/search-receipt.json",
        }]
        self.write("docs/ecosystem/search-receipt.json", {
            "claim": "Three results returned", "limits": ["Fresh agent discovery pending"]})
        self.save()
        page, _ = self.build()
        data = json.loads(page.data)
        self.assertEqual(data["counts"]["repositories"], 2)
        self.assertEqual(data["counts"]["stars"], 1)
        self.assertTrue(data.get("integrations"), "New integration is missing from the searchable data")
        integration = data["integrations"][0]
        self.assertIn("bounded web search", integration["search"])
        self.assertIn("/blob/main/docs/ecosystem/search-receipt.json", integration["receipt_url"])
        self.assertEqual(integration["receipt"]["limits"], ["Fresh agent discovery pending"])

    def test_linked_curated_document_is_hashed_and_changes_invalidate_the_page(self):
        self.config["guides"] = [{"title": "Adoption", "body": "Read selected scope",
                                  "path": "docs/adoption.md"}]
        self.write("docs/adoption.md", "One frozen adoption boundary.")
        self.save()
        page, _ = self.build()
        self.assertIn("docs/adoption.md", [row["path"] for row in json.loads(page.data)["inputs"]])
        source = next(row for row in json.loads(page.data)["inputs"]
                      if row["path"] == "docs/adoption.md")
        self.assertEqual(source["sha256"], hashlib.sha256(b"One frozen adoption boundary.").hexdigest())
        self.write("docs/adoption.md", "A corrected adoption boundary.")
        self.assertNotEqual(self.run_generator("--check").returncode, 0)

    def test_selected_stack_contains_every_component_even_without_old_audit_coverage(self):
        page, _ = self.build()
        setup = json.loads(page.data)["setup"]
        self.assertEqual([row["id"] for row in setup["components"]], ["search"])
        self.assertEqual(setup["missing_audit_count"], 1)
        row = setup["components"][0]
        self.assertEqual(row["audit_status"], "missing")
        self.assertIsNone(row["audit"])
        self.assertEqual(row["profiles"], ["foundation"])
        self.assertEqual(row["layers"], ["retrieval"])
        self.assertEqual(row["current_host_acceptance"], "Unknown on this browser's host")
        self.assertIn("search --native", next(recipe for recipe in setup["recipes"]
                                              if recipe["path"] == "recipes/search.md")["text"])

    def test_recipe_coverage_drift_and_unknown_profile_components_fail(self):
        self.adoption["recipe_map"] = {}
        self.save()
        self.assertNotEqual(self.run_generator("--write").returncode, 0)
        self.adoption["recipe_map"] = {"search": "recipes/search.md"}
        self.adoption["profiles"][0]["component_ids"].append("unknown")
        self.save()
        self.assertNotEqual(self.run_generator("--write").returncode, 0)

    def test_recipe_bytes_are_escaped_and_confined_and_changes_invalidate_build(self):
        hostile = '# Native\n</script><img src="https://evil.example/read">\n```sh\nsearch --native\n```'
        self.write("recipes/search.md", hostile)
        page, _ = self.build()
        self.assertEqual(page.external_assets, [])
        self.assertEqual(len(page.scripts), 2)
        self.assertEqual(next(row for row in json.loads(page.data)["setup"]["recipes"]
                              if row["path"] == "recipes/search.md")["text"], hostile)
        self.write("recipes/search.md", "Changed native installation")
        self.assertNotEqual(self.run_generator("--check").returncode, 0)
        self.adoption["recipe_map"]["search"] = "../outside.md"
        self.save()
        self.assertNotEqual(self.run_generator("--write").returncode, 0)

    def test_audit_version_mismatch_and_negative_comparison_remain_visible(self):
        self.saturation["components"] = [{"component_id": "search", "version": "0.9",
            "artifact_baselines": [{"id": "larger-candidate", "baseline_tokens": 601,
                "candidate_tokens": 861, "tokens_removed": -260, "acceptance_passed": True,
                "limitations": ["Known source read is cheaper."]}],
            "lifecycle_stages": {"recovery": {"status": "not_established", "scope": "Not run"}}}]
        self.save()
        page, _ = self.build()
        data = json.loads(page.data)
        self.assertEqual(data["setup"]["components"][0]["audit_status"], "different_version")
        self.assertEqual(data["efficiency"]["comparisons"][0]["tokens_removed"], -260)
        self.assertEqual(data["setup"]["components"][0]["audit"]["lifecycle_stages"]
                         ["recovery"]["status"], "not_established")
        self.saturation["components"][0]["artifact_baselines"][0]["tokens_removed"] = 260
        self.save()
        self.assertNotEqual(self.run_generator("--write").returncode, 0)

    def test_audit_receipts_must_join_registered_evidence_by_identity_and_path(self):
        self.saturation["components"] = [{"component_id": "search", "version": "1.0",
            "functional_evidence": {"public_receipts": [
                {"id": "historical-only", "path": "evidence/wrong.json"}]}}]
        self.save()
        self.assertNotEqual(self.run_generator("--write").returncode, 0)
        self.saturation["components"][0]["functional_evidence"]["public_receipts"][0]["path"] = "evidence/history.json"
        self.save()
        page, _ = self.build()
        self.assertEqual(json.loads(page.data)["setup"]["components"][0]["audit_status"], "matched_version")

    def test_counter_receipt_identity_must_match_registered_receipt(self):
        path = "evidence/" + self.token_ids[0] + ".json"
        self.write(path, {"id": "different-receipt", "data": {"saved_estimate": 99999}})
        self.assertNotEqual(self.run_generator("--write").returncode, 0)

    def test_quality_policy_preserves_larger_full_original_choice(self):
        self.config["selection_policy"] = [{"task": "Recover complete original source",
            "preferred": "Original source", "baseline_tokens": 36625, "candidate_tokens": 19714,
            "chosen_tokens": 36625, "unit": "artifact tokens",
            "quality_check": "Full original bytes required", "boundary": "Summary is incomplete",
            "source_paths": ["evidence/history.json"]}]
        self.save()
        page, _ = self.build()
        policy = json.loads(page.data)["efficiency"]["selection_policy"][0]
        self.assertEqual(policy["chosen_tokens"], 36625)
        self.assertGreater(policy["chosen_tokens"], policy["candidate_tokens"])
        self.assertEqual(policy["quality_check"], "Full original bytes required")
        self.config["selection_policy"][0]["source_paths"] = ["../outside.json"]
        self.save()
        self.assertNotEqual(self.run_generator("--write").returncode, 0)

    def test_optional_confirmation_and_lifecycle_guide_are_embedded_when_registered(self):
        identifier = "token-practice-confirmation-20260920"
        path = "evidence/receipts/" + identifier + ".json"
        self.evidence["receipts"].append({"id": identifier, "path": path,
            "kind": "historical_inventory", "claim": "Counters independently checked",
            "component_ids": [], "limitations": ["Not causal savings"]})
        self.write(path, {"id": identifier, "data": {"native_snapshots": [{"saved": 1708}]}})
        self.write("adoption/lifecycle.md", "# Lifecycle\n\nUse and restore only owned state.")
        self.save()
        page, _ = self.build()
        data = json.loads(page.data)
        receipt = next(row for row in data["efficiency"]["receipts"] if row["id"] == identifier)
        self.assertEqual(receipt["record"]["data"]["native_snapshots"][0]["saved"], 1708)
        self.assertIn("/blob/main/evidence/receipts/", receipt["url"])
        guide = next(row for row in data["setup"]["recipes"] if row["path"] == "adoption/lifecycle.md")
        self.assertIn("Use and restore only owned state", guide["text"])
        self.assertIn("/blob/main/adoption/lifecycle.md", guide["url"])


if __name__ == "__main__":
    unittest.main()
