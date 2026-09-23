"""Consumer-facing checks for the offline public ecosystem explorer."""

import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil
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
        self.elements = {}
        self.reading_data = False
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.elements[attrs["id"]] = attrs
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
        self.write("docs/ecosystem/template.html", "<!doctype html><html><body><!--@@BODY@@-->"
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

    def check_report(self):
        result = self.run_generator("--check")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def assert_check_digest_changes(self, mutate):
        """--check no longer compares against a committed file (there isn't
        one); a source change is instead observed as a changed input/output
        digest in two otherwise-passing --check reports."""
        before = self.check_report()
        mutate()
        after = self.check_report()
        self.assertNotEqual(after["input_sha256"], before["input_sha256"])
        self.assertNotEqual(after["output_sha256"], before["output_sha256"])

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

    @unittest.skipUnless(shutil.which("node"), "JavaScript startup regression needs Node")
    def test_research_summary_distinguishes_open_and_bounded_closed_review(self):
        template = (ROOT / "docs/ecosystem/template.html").read_text()
        script = re.search(r"function researchStatusText\(.*?^}", template, re.S | re.M).group(0)
        script += '\nconsole.log(JSON.stringify(["not_established", "bounded_review_complete"].map(status => researchStatusText({saturation: {status}}, "2026-09-21"))));'
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        opened, closed = json.loads(result.stdout)
        self.assertIn("remains open", opened)
        self.assertIn("Bounded review complete", closed)
        self.assertIn("2026-09-21", closed)
        self.assertIn("reopening conditions", closed)
        self.assertNotIn("remains open", closed)

    @unittest.skipUnless(shutil.which("node"), "JavaScript startup regression needs Node")
    def test_template_and_failed_generated_startup_offer_recovery_without_navigation(self):
        """Execute the real startup script; native-browser checks cover complete rendering."""
        template = (ROOT / "docs/ecosystem/template.html").read_text()
        self.write("docs/ecosystem/template.html", template)
        page, generated = self.build()
        raw_page = Page(template)
        self.assertIn("hidden", raw_page.elements["catalog-app"])
        self.assertNotIn("hidden", raw_page.elements["catalog-recovery"])
        self.assertIn("hidden", page.elements["catalog-app"])
        harness = r'''
const vm = require("node:vm");
const input = JSON.parse(require("node:fs").readFileSync(0, "utf8"));
const nodes = {"catalog-app": {hidden: true}, "catalog-recovery": {hidden: false},
  "catalog-recovery-title": {}, "catalog-recovery-message": {}};
const errors = [];
let renderAttempts = 0, navigations = 0;
const document = {
  getElementById(id) {
    if(id === "ecosystem-data") return input.data === null ? null : {textContent: input.data};
    if(nodes[id]) return nodes[id];
    throw Error("Unexpected DOM lookup: " + id);
  },
  querySelectorAll() { renderAttempts++; throw Error("injected renderer failure"); }
};
const location = {set href(value) { navigations++; }, replace() { navigations++; },
  assign() { navigations++; }, hash: "#overview"};
vm.runInNewContext(input.script, {document, location, window: {location},
  console: {error(message, error) { errors.push(error.message); }}});
process.stdout.write(JSON.stringify({nodes, errors, renderAttempts, navigations}));
'''
        for label, html_text, payload, expected_errors, rendered in (
            ("raw source", template, raw_page.data, [], 0),
            ("missing data element", generated, None, [], 0),
            ("empty embedded data", generated, "", [], 0),
            ("corrupt embedded data", generated, "{broken", None, 0),
            ("failure after parsing built data", generated, page.data,
             ["injected renderer failure"], 1),
        ):
            with self.subTest(label=label):
                script, = re.findall(r"<script>(.*?)</script>", html_text, re.S)
                result = subprocess.run(["node", "-e", harness], input=json.dumps({
                    "script": script, "data": payload}), capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                observed = json.loads(result.stdout)
                self.assertTrue(observed["nodes"]["catalog-app"]["hidden"])
                self.assertFalse(observed["nodes"]["catalog-recovery"]["hidden"])
                self.assertIn("index.html", observed["nodes"]["catalog-recovery-message"]["textContent"])
                self.assertEqual(observed["navigations"], 0)
                self.assertEqual(observed["renderAttempts"], rendered)
                if expected_errors is None:
                    self.assertEqual(len(observed["errors"]), 1)
                else:
                    self.assertEqual(observed["errors"], expected_errors)

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

    def test_check_reports_deterministic_digest_without_a_committed_file(self):
        """docs/ecosystem/index.html is no longer committed; --check builds twice
        into temporary directories and reports the input/output digests instead
        of comparing against an on-disk file (which it does not even read)."""
        page, expected = self.build()
        output = self.root / "docs/ecosystem/index.html"
        output.write_text(output.read_text() + "tampered")
        result = self.run_generator("--check")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["bytes"], len(expected.encode("utf-8")))
        self.assertEqual(report["output_sha256"], hashlib.sha256(expected.encode("utf-8")).hexdigest())
        self.assertRegex(report["input_sha256"], r"^[0-9a-f]{64}$")
        output.unlink()
        self.assertEqual(self.run_generator("--check").returncode, 0)

        self.review["entries"][0]["role"] = "Corrected scope"
        self.save()
        second = self.run_generator("--check")
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        second_report = json.loads(second.stdout)
        self.assertNotEqual(second_report["input_sha256"], report["input_sha256"])
        self.assertNotEqual(second_report["output_sha256"], report["output_sha256"])

    def test_check_still_rejects_invalid_sources(self):
        self.records.append(self.records[0])
        self.save()
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
        self.config["publication_ref"] = "codex/review-catalog"
        self.save()
        page, _ = self.build()
        self.assertIn("/blob/codex/review-catalog/docs/ecosystem/search-receipt.json",
                      json.loads(page.data)["integrations"][0]["receipt_url"])

    def test_publication_ref_rejects_path_escape(self):
        self.config["publication_ref"] = "../outside"
        self.save()
        result = subprocess.run([sys.executable, str(GENERATOR), "--root", str(self.root)],
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unsafe publication ref", result.stdout)

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
        self.assert_check_digest_changes(lambda: self.write("docs/adoption.md", "A corrected adoption boundary."))

    def test_unpublished_curated_source_is_available_as_one_complete_offline_recipe(self):
        source = {"title": "Research", "body": "Dated and unqualified",
                  "path": "docs/unpublished.md", "offline": True}
        self.config["guides"] = [source]
        self.config["highlights"] = [{**source, "id": "research", "status": "Recorded"}]
        content = "# Research\nNo strategy qualified.\n\n## Limits\nKeep the failed results.\n"
        self.write(source["path"], content)
        self.save()
        page, _ = self.build()
        data = json.loads(page.data)
        recipes = [row for row in data["setup"]["recipes"] if row["path"] == source["path"]]
        self.assertEqual(len(recipes), 1)
        self.assertEqual(recipes[0]["text"], content)
        for key in ("guides", "highlights"):
            self.assertEqual(data[key][0]["recipe_path"], source["path"])
        self.assertEqual(page.external_assets, [])

    def test_offline_curated_source_rejects_non_markdown(self):
        self.config["guides"] = [{"title": "Receipt", "body": "Read receipt",
                                  "path": "docs/receipt.json", "offline": True}]
        self.write("docs/receipt.json", {"status": "not_established"})
        self.save()
        self.assertIn("offline curated source must be Markdown", self.run_generator("--write").stdout)

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

    def test_real_stack_manifest_exchange_calendars_addition_is_internally_consistent(self):
        """Sanity check on the real repository manifest, not the synthetic fixture above.

        exchange-calendars was newly selected in manifests/stack.json (pr4-stack
        unit) while pinned in catalogs/us-equities/data-research.json. This does
        not run scripts/build_ecosystem.py --write against the real repository
        (the coordinator regenerates the explorer); it only confirms the raw
        manifest/catalog cross-reference this unit owns.
        """
        stack = json.loads((ROOT / "manifests/stack.json").read_text())
        components = {c["id"]: c for c in stack["components"]}
        self.assertIn("exchange-calendars", components)
        component = components["exchange-calendars"]
        profiles = {p["id"]: p for p in stack["profiles"]}
        self.assertIn(component["profile"], profiles)
        self.assertIn("exchange-calendars", profiles[component["profile"]]["component_ids"])

        data_research = json.loads((ROOT / "catalogs/us-equities/data-research.json").read_text())
        card = next(entry for entry in data_research["entries"] if entry["id"] == "data-exchange-calendars")
        self.assertIn(component["repository"], card["repository"])
        self.assertIn("manifests/stack.json", card["evidence_refs"])

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
        self.assert_check_digest_changes(lambda: self.write("recipes/search.md", "Changed native installation"))
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

    def returned_fixture(self, identifier="full-stack-convergence-20260922", kind="native_cli_e2e"):
        path = "evidence/receipts/" + identifier + ".json"
        artifact_path = "evidence/artifacts/selected/returned.txt"
        returned = 'search --native\nexit=0\n</script><img src="https://invalid.example/private">\n'
        self.write(artifact_path, returned)
        artifact = {"path": artifact_path, "bytes": len(returned.encode()),
                    "sha256": hashlib.sha256(returned.encode()).hexdigest()}
        self.evidence["receipts"].append({"id": identifier, "path": path, "kind": kind,
            "claim": "One selected operation returned", "component_ids": ["search"],
            "limitations": ["Not all selected tools or another host"]})
        self.write(path, {"id": identifier, "recorded_at_utc": "2026-09-22T01:02:03Z",
            "claim": "One selected operation returned", "public_artifacts": [artifact],
            "private_log": "/not-an-imported-file/private.log"})
        self.save()
        return identifier, path, artifact

    def test_future_dated_public_result_is_joined_and_exact_bytes_are_embedded(self):
        identifier, path, artifact = self.returned_fixture()
        page, _ = self.build()
        data = json.loads(page.data)
        component = data["setup"]["components"][0]
        self.assertEqual(component["returned_receipt_ids"], [identifier])
        result = next(row for row in data["efficiency"]["receipts"] if row["id"] == identifier)
        self.assertEqual(result["kind"], "native_cli_e2e")
        self.assertEqual(result["component_ids"], ["search"])
        self.assertEqual(result["artifacts"][0]["text"], (self.root / artifact["path"]).read_text())
        self.assertIn("/blob/main/" + path, result["url"])
        self.assertIn("/blob/main/" + artifact["path"], result["artifacts"][0]["url"])
        self.assertIn(artifact["path"], [row["path"] for row in data["inputs"]])
        self.assertNotIn("/not-an-imported-file/private.log", [row["path"] for row in data["inputs"]])
        self.assertEqual(page.external_assets, [])
        self.assertEqual(len(page.scripts), 2)
        self.assertEqual(component["current_host_acceptance"], "Unknown on this browser's host")

    def test_family_name_does_not_promote_inventory_or_unrelated_receipts(self):
        for identifier, kind in [("native-returned-results-20260922", "historical_inventory"),
                                 ("unreviewed-bundle-20260922", "native_cli_e2e")]:
            with self.subTest(identifier=identifier):
                self.returned_fixture(identifier, kind)
                page, _ = self.build()
                data = json.loads(page.data)
                self.assertNotIn(identifier, [row["id"] for row in data["efficiency"]["receipts"]])
                self.assertNotIn(identifier, data["setup"]["components"][0]["returned_receipt_ids"])

    def test_returned_artifact_tampering_and_nonpublic_paths_fail(self):
        _, path, artifact = self.returned_fixture()
        self.write(artifact["path"], "changed returned bytes")
        self.assertIn("hash or size mismatch", self.run_generator("--write").stdout)
        self.write(path, {"id": "full-stack-convergence-20260922",
                          "public_artifacts": [{**artifact, "path": "recipes/search.md"}]})
        self.assertIn("public evidence/artifacts", self.run_generator("--write").stdout)

    def test_returned_receipt_requires_canonical_component_and_confined_artifact(self):
        _, path, artifact = self.returned_fixture()
        self.evidence["receipts"][-1]["component_ids"] = ["unknown-alias"]
        self.save()
        self.assertIn("canonical selected components", self.run_generator("--write").stdout)
        self.evidence["receipts"][-1]["component_ids"] = ["search"]
        self.save()
        link_path = "evidence/artifacts/selected/link.txt"
        (self.root / link_path).symlink_to(self.root / artifact["path"])
        self.write(path, {"id": "full-stack-convergence-20260922",
                          "public_artifacts": [{**artifact, "path": link_path}]})
        self.assertNotEqual(self.run_generator("--write").returncode, 0)

    def test_public_png_is_embedded_with_exact_hash_and_unknown_tools_keep_a_gap(self):
        import base64
        identifier, path, _ = self.returned_fixture()
        png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jfYQAAAAASUVORK5CYII=")
        image_path = "evidence/artifacts/selected/dashboard.png"
        (self.root / image_path).write_bytes(png)
        self.write(path, {"id": identifier, "public_artifacts": [{"path": image_path,
            "bytes": len(png), "sha256": hashlib.sha256(png).hexdigest()}]})
        page, _ = self.build()
        row = next(row for row in json.loads(page.data)["efficiency"]["receipts"] if row["id"] == identifier)
        self.assertEqual(row["artifacts"][0]["mime_type"], "image/png")
        self.assertEqual(base64.b64decode(row["artifacts"][0]["content_base64"]), png)
        self.evidence["receipts"].pop()
        self.save()
        page, _ = self.build()
        self.assertEqual(json.loads(page.data)["setup"]["components"][0]["returned_receipt_ids"], [])


    def test_topic_list_preserves_missing_counters_and_negative_baseline(self):
        row = {"component_id": "search", "group": "core", "purpose": "Find exact source",
               "upstream_commands": {"use": "search --native"},
               "returned_result_summary": "Exact source returned",
               "session_statistics": {"value": None, "summary": "Not provided by upstream"},
               "lifetime_statistics": {"value": None, "summary": "No cumulative savings counter"},
               "baseline_summary": "40 native tokens versus 324 response tokens; keep the focused read",
               "baseline_tokens_removed": -284,
               "lifecycle_summary": "Existing dated acceptance; no full host recertification",
               "source_paths": ["evidence/history.json"]}
        self.write("docs/token-efficiency-stack.json", {"schema_version": 1,
                   "scope": "Dated topic evidence", "rows": [row]})
        page, _ = self.build()
        topic = json.loads(page.data)["efficiency"]["topic"]
        self.assertEqual(len(topic["rows"]), 1)
        actual = topic["rows"][0]
        self.assertIsNone(actual["session_statistics"]["value"])
        self.assertIsNone(actual["lifetime_statistics"]["value"])
        self.assertEqual(actual["baseline_tokens_removed"], -284)
        self.assertEqual(actual["version"], "1.0")
        self.assertEqual(actual["repository"], "https://github.com/example/search")
        self.assertTrue(actual["sources"][0]["url"].endswith("/evidence/history.json"))

    def test_topic_list_rejects_unselected_component(self):
        self.write("docs/token-efficiency-stack.json", {"schema_version": 1,
                   "rows": [{"component_id": "unselected", "group": "core"}]})
        result = self.run_generator("--write")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must be selected and unique", result.stdout)

    def grand_catalog_fixture(self):
        self.config["grand_catalogs"] = {
            "foundation_manifest": "catalogs/foundation/manifest.json",
            "foundation_decisions": "catalogs/foundation/decisions.json",
            "trading_target": "catalogs/us-equities/runtime-target.json",
        }
        layer = {"id": "retrieval", "title": "Retrieval", "purpose": "Find the needed source",
                 "selection": "Use a focused lane", "activation": "On demand",
                 "lifecycle_scope": "One scoped index", "next_gap": "Restore on a new host"}
        self.foundation = {"schema_version": 1, "scope": "General engineering",
                           "layers": [layer], "top_gaps": []}
        self.decisions = {"schema_version": 1, "decisions": [
            {"id": "search-use", "capability": "Find a source", "layer_ids": ["retrieval"],
             "selection": "default", "review_status": "accepted_within_scope", "activation": "On demand",
             "component_ids": ["search"], "evidence_ids": ["historical-only"],
             "evidence_scope": "Only the retained search fixture", "limitations": ["No recovery test"],
             "source_paths": ["evidence/history.json"], "next_gap": "Restore the index",
             "lifecycle": {"scope": "Dated fixture", "unknown": "Recovery", "stage_refs": []},
             "supersedes": []},
            {"id": "search-recovery", "capability": "Restore a source index", "layer_ids": ["retrieval"],
             "selection": "trial", "review_status": "not_established", "activation": "When needed",
             "component_ids": ["search"], "evidence_ids": [], "evidence_scope": "No recovery execution",
             "limitations": [], "source_paths": [], "next_gap": "Run a restore fixture",
             "lifecycle": {"scope": "Unmeasured", "unknown": "All recovery", "stage_refs": []},
             "supersedes": []},
        ]}
        self.trading = {"schema_version": 1, "scope": "Trading-specific acceptance",
                        "engine": {"repository": "https://github.com/example/engine", "requested_version": "2.0rc5",
                                   "source_commit": "c" * 40, "acceptance": "source review",
                                   "sources": ["https://example.org/engine"]},
                        "broker_boundaries": [{"id": "alpaca", "selected_path": "Read-only data",
                                               "local_broker_execution_acceptance": "not_established",
                                               "sources": ["https://example.org/broker"]}],
                        "accepted_reference_paths": ["evidence/history.json"],
                        "next_acceptance": [{"id": "replay", "scope": "Run a retained fixture"}],
                        "limitations": ["No broker orders"]}
        for path in ("docs/harness-defaults.md", "catalogs/README.md", "catalogs/foundation/README.md"):
            self.write(path, "# General foundation\n\nSelect only the needed layer.")
        self.save_grand_catalogs()

    def save_grand_catalogs(self):
        self.write(self.config["grand_catalogs"]["foundation_manifest"], self.foundation)
        self.write(self.config["grand_catalogs"]["foundation_decisions"], self.decisions)
        self.write(self.config["grand_catalogs"]["trading_target"], self.trading)
        self.save()

    def test_optional_catalogs_absent_preserves_repository_discovery(self):
        page, _ = self.build()
        data = json.loads(page.data)
        self.assertIsNone(data.get("grand_catalogs"))
        self.assertEqual(len(data["repositories"]), 2)

    def surface_fixture(self):
        """Local integration fixture; no dashboard or upstream execution claim."""
        self.grand_catalog_fixture()
        common = {"component_ids": ["search"], "upstream_url": "https://example.org/search",
                  "scope": "Dated fixture; current host unknown", "local_url": None,
                  "launch": None, "source_paths": ["recipes/search.md"]}
        self.surfaces = {"schema_version": 1, "checked_at": "2026-09-21",
                         "scope": "Reference surfaces only", "surfaces": [
            {**common, "id": "search-tui", "title": "Search terminal", "kind": "native-tui",
             "launch": "search tui"},
            {**common, "id": "search-local", "title": "Search dashboard", "kind": "local-web",
             "local_url": "http://127.0.0.1:3000/dashboard"},
            {**common, "id": "search-hosted", "title": "Hosted search", "kind": "hosted-web"},
            {**common, "id": "search-cli", "title": "Search command", "kind": "cli",
             "launch": "search --native"}],
            "layers": [{"layer_id": "retrieval", "surface_ids": ["search-tui", "search-local",
                        "search-hosted", "search-cli"], "runbook_paths": ["recipes/search.md"]}]}
        self.save_surfaces()

    def save_surfaces(self):
        self.write("catalogs/foundation/surfaces.json", self.surfaces)

    def test_surface_manifest_joins_native_local_hosted_and_runbook_sources(self):
        self.surface_fixture()
        page, _ = self.build()
        data = json.loads(page.data)
        foundation = data["grand_catalogs"]["foundation"]
        layer = foundation["layers"][0]
        self.assertEqual([row["id"] for row in layer["surfaces"]],
                         self.surfaces["layers"][0]["surface_ids"])
        self.assertEqual(layer["surfaces"][1]["local_url"], "http://127.0.0.1:3000/dashboard")
        self.assertIsNone(layer["surfaces"][2]["local_url"])
        self.assertEqual(layer["surfaces"][0]["launch"], "search tui")
        self.assertEqual(layer["runbooks"][0]["path"], "recipes/search.md")
        self.assertTrue(layer["surfaces"][0]["sources"][0]["url"].endswith("/recipes/search.md"))
        self.assertEqual(foundation["surface_catalog"]["scope"], "Reference surfaces only")
        self.assertEqual(foundation["surface_catalog"]["checked_at"], "2026-09-21")
        self.assertIn("/blob/main/catalogs/foundation/surfaces.json", foundation["surface_catalog"]["url"])
        hashes = {row["path"]: row["sha256"] for row in data["inputs"]}
        path = "catalogs/foundation/surfaces.json"
        self.assertEqual(hashes[path], hashlib.sha256((self.root / path).read_bytes()).hexdigest())
        def change_surface_scope():
            self.surfaces["surfaces"][0]["scope"] = "Changed surface scope"
            self.save_surfaces()
        self.assert_check_digest_changes(change_surface_scope)

    def test_surface_layer_coverage_and_references_must_resolve(self):
        self.surface_fixture()
        cases = [
            ("layers", [], "exactly match"),
            ("layers", self.surfaces["layers"] * 2, "duplicate surface layer"),
            ("layers", [{"layer_id": "unknown", "surface_ids": []}], "exactly match"),
            ("layers", [{"layer_id": "retrieval", "surface_ids": ["missing"]}], "unknown surface"),
            ("layers", [{"layer_id": "retrieval", "surface_ids": ["search-cli", "search-cli"]}], "duplicate"),
            ("surfaces", self.surfaces["surfaces"] * 2, "duplicate foundation surface"),
        ]
        for field, invalid, message in cases:
            with self.subTest(field=field, message=message):
                original = self.surfaces[field]
                self.surfaces[field] = invalid
                self.save_surfaces()
                result = self.run_generator("--write")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message, result.stdout)
                self.surfaces[field] = original

    def test_surface_components_kinds_and_commands_require_valid_contracts(self):
        self.surface_fixture()
        for field, invalid, message in (
            ("component_ids", ["missing"], "unknown component"),
            ("component_ids", [], "has none"),
            ("component_ids", ["search", "search"], "duplicate"),
            ("kind", "remote-shell", "unknown foundation surface kind"),
            ("launch", "", "must be command text"),
            ("launch", {"execute": "search"}, "must be command text"),
        ):
            with self.subTest(field=field):
                row = self.surfaces["surfaces"][0]
                original = row[field]
                row[field] = invalid
                self.save_surfaces()
                result = self.run_generator("--write")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message, result.stdout)
                row[field] = original

    def test_surface_links_reject_unsafe_upstream_and_nonliteral_local_hosts(self):
        self.surface_fixture()
        row = self.surfaces["surfaces"][1]
        cases = [("upstream_url", url) for url in (
            "javascript:alert(1)", "http://example.org/", "https://user:secret@example.org/",
            "https://127.0.0.1/", "https://example.org/\nmalformed")]
        cases += [("local_url", url) for url in (
            "javascript:alert(1)", "http://localhost:3000/", "http://127.1/", "http://2130706433/",
            "http://127.0.0.1.example.org/", "http://user:secret@127.0.0.1:3000/",
            "http://127.0.0.1\\@example.org/", "http://[::1%25eth0]:3000/",
            "http://127.0.0.1:65536/", "http://127.0.0.1:0/", "http://127.0.0.1:3000/?token=secret",
            "http://127.0.0.1:3000/#secret", "http://127.0.0.1:3000/\n")]
        for field, invalid in cases:
            with self.subTest(field=field, url=invalid):
                original = row[field]
                row[field] = invalid
                self.save_surfaces()
                self.assertNotEqual(self.run_generator("--write").returncode, 0)
                row[field] = original
        row["local_url"] = "https://[::1]:3000/dashboard"
        self.save_surfaces()
        page, _ = self.build()
        self.assertEqual(json.loads(page.data)["grand_catalogs"]["foundation"]["layers"][0]
                         ["surfaces"][1]["local_url"], row["local_url"])
        row["kind"] = "hosted-web"
        self.save_surfaces()
        self.assertNotEqual(self.run_generator("--write").returncode, 0)

    def test_surface_source_and_runbook_paths_cannot_escape_or_follow_symlinks(self):
        self.surface_fixture()
        (self.root / "recipes/linked.md").symlink_to(self.root / "recipes/search.md")
        for target, field in ((self.surfaces["surfaces"][0], "source_paths"),
                              (self.surfaces["layers"][0], "runbook_paths")):
            for path in ("../outside.md", "recipes/linked.md", "https://example.org/source.md"):
                with self.subTest(field=field, path=path):
                    original = target[field]
                    target[field] = [path]
                    self.save_surfaces()
                    self.assertNotEqual(self.run_generator("--write").returncode, 0)
                    target[field] = original

    def test_surface_text_and_commands_are_inert_public_data(self):
        self.surface_fixture()
        hostile = '</script><script src="https://invalid.example/steal.js"></script>'
        row = self.surfaces["surfaces"][0]
        row.update(title=hostile, scope=hostile, launch=hostile)
        self.save_surfaces()
        page, _ = self.build()
        self.assertEqual(len(page.scripts), 2)
        self.assertEqual(page.external_assets, [])
        surface = json.loads(page.data)["grand_catalogs"]["foundation"]["layers"][0]["surfaces"][0]
        self.assertEqual(surface["title"], hostile)
        self.assertEqual(surface["launch"], hostile)

    def test_foundation_joins_exact_capability_receipts_and_current_component_pin(self):
        self.stack["components"][0]["source_pin"] = "d" * 40
        self.grand_catalog_fixture()
        page, _ = self.build()
        data = json.loads(page.data)
        self.assertIn("grand_catalogs", data, "Configured catalogs need a first-class payload")
        foundation = data["grand_catalogs"]["foundation"]
        accepted, untested = foundation["decisions"]
        self.assertEqual(accepted["components"][0]["version"], "1.0")
        self.assertEqual(accepted["components"][0].get("source_pin"), "d" * 40)
        self.assertEqual([r["id"] for r in accepted["receipts"]], ["historical-only"])
        self.assertEqual(accepted["evidence_scope"], "Only the retained search fixture")
        self.assertEqual(untested["receipts"], [])
        self.assertEqual(untested["review_status"], "not_established")
        self.assertEqual(foundation["counts"], {"layers": 1, "capabilities": 2, "accepted": 1, "components": 1})
        self.assertEqual(foundation["layers"][0]["next_gap"], "Restore on a new host")
        self.assertEqual(data["grand_catalogs"]["trading"]["engine"]["requested_version"], "2.0rc5")
        self.assertEqual(data["grand_catalogs"]["trading"]["broker_boundaries"][0]
                         ["local_broker_execution_acceptance"], "not_established")
        self.assertEqual(len(data["grand_catalogs"]["trading"]["accepted_references"]), 1)

    def test_catalog_inputs_and_foundation_guides_are_hashed_and_publicly_linked(self):
        self.grand_catalog_fixture()
        plan = "blueprints/trading/acceptance-plan.md"
        self.write(plan, "# Planned replay\n\nNo broker execution is accepted.")
        self.trading["acceptance_plan"] = plan
        self.save_grand_catalogs()
        page, _ = self.build()
        data = json.loads(page.data)
        sources = {row["path"]: row for row in data["inputs"]}
        for path in [*self.config["grand_catalogs"].values(), plan]:
            self.assertIn(path, sources)
            self.assertEqual(sources[path]["sha256"], hashlib.sha256((self.root / path).read_bytes()).hexdigest())
        trading = data["grand_catalogs"]["trading"]
        self.assertTrue(trading["acceptance_plan_source"]["url"].endswith("/" + plan))
        self.assertNotIn(plan, [row["path"] for row in trading["accepted_references"]])
        recipes = {row["path"]: row for row in data["setup"]["recipes"]}
        for path in ("docs/harness-defaults.md", "catalogs/README.md", "catalogs/foundation/README.md"):
            self.assertIn(path, recipes)
            self.assertIn("/blob/main/", recipes[path]["url"])
        self.assertIn("/blob/main/catalogs/foundation/", data["grand_catalogs"]["foundation"]["url"])

        def change_next_gap():
            self.foundation["layers"][0]["next_gap"] = "A changed next check"
            self.save_grand_catalogs()
        self.assert_check_digest_changes(change_next_gap)

    def test_catalog_references_must_resolve_before_publication(self):
        self.grand_catalog_fixture()
        for field, invalid, message in (
            ("component_ids", ["unknown"], "unknown component"),
            ("evidence_ids", ["unknown"], "unknown receipt"),
            ("layer_ids", ["unknown"], "unknown foundation layer"),
            ("source_paths", ["../private.json"], "confined"),
        ):
            with self.subTest(field=field):
                row = self.decisions["decisions"][0]
                original = row[field]
                row[field] = invalid
                self.save_grand_catalogs()
                result = self.run_generator("--write")
                self.assertNotEqual(result.returncode, 0, field)
                self.assertIn(message, result.stdout)
                row[field] = original

    def test_catalog_source_text_is_inert_and_unsafe_external_links_are_removed(self):
        self.grand_catalog_fixture()
        hostile = '</script><img src="https://evil.example/steal"><script>alert(1)</script>'
        self.decisions["decisions"][0]["capability"] = hostile
        self.trading["engine"]["sources"] = ["javascript:alert(1)", "https://good.example/engine"]
        self.trading["broker_boundaries"][0]["sources"] = ["https://user:secret@example.org/"]
        self.save_grand_catalogs()
        page, _ = self.build()
        self.assertEqual(len(page.scripts), 2)
        self.assertEqual(page.external_assets, [])
        data = json.loads(page.data)
        self.assertIn("grand_catalogs", data)
        catalogs = data["grand_catalogs"]
        self.assertEqual(catalogs["foundation"]["decisions"][0]["capability"], hostile)
        self.assertEqual(catalogs["trading"]["engine"]["sources"], ["https://good.example/engine"])
        self.assertEqual(catalogs["trading"]["broker_boundaries"][0]["sources"], [])

    def test_catalog_trading_reference_cannot_escape_repository(self):
        self.grand_catalog_fixture()
        for field, value in (("accepted_reference_paths", ["../private.json"]),
                             ("acceptance_plan", "../private.json")):
            with self.subTest(field=field):
                original = self.trading.get(field)
                self.trading[field] = value
                self.save_grand_catalogs()
                self.assertNotEqual(self.run_generator("--write").returncode, 0)
                if original is None:
                    self.trading.pop(field)
                else:
                    self.trading[field] = original

    def test_catalog_structured_supersession_preserves_scope_and_reason(self):
        self.grand_catalog_fixture()
        current = self.decisions["decisions"][0]
        current.update(capability_key="scoped-search", checked_at="2026-09-20", candidate=None)
        previous = dict(current, id="search-use-previous", checked_at="2026-09-19")
        self.decisions["decisions"].append(previous)
        supersession = {"decision_id": previous["id"], "scope": "The same retained search fixture",
                        "reason": "A later bounded acceptance replaces the earlier decision"}
        current["supersedes"] = [supersession]
        self.save_grand_catalogs()
        page, _ = self.build()
        decision = json.loads(page.data)["grand_catalogs"]["foundation"]["decisions"][0]
        self.assertEqual(decision["supersedes"], [supersession])
        self.assertEqual(decision["components"][0]["id"], "search")

    def test_catalog_structured_supersession_rejects_unknown_decision(self):
        self.grand_catalog_fixture()
        self.decisions["decisions"][0]["supersedes"] = [{
            "decision_id": "unknown", "scope": "Same capability", "reason": "Later acceptance"}]
        self.save_grand_catalogs()
        result = self.run_generator("--write")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("supersedes an unknown decision", result.stdout)


if __name__ == "__main__":
    unittest.main()
