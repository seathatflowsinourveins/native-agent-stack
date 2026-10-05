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
        self.inline_scripts = []
        self.inline = None
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
            self.inline = None if attrs else []
        if tag in {"script", "img", "iframe", "link"}:
            url = attrs.get("src", attrs.get("href", ""))
            if url and not url.startswith("data:"):
                self.external_assets.append(url)

    def handle_endtag(self, tag):
        if tag == "script":
            self.reading_data = False
            if self.inline is not None:
                self.inline_scripts.append("".join(self.inline))
                self.inline = None

    def handle_data(self, data):
        if self.reading_data:
            self.data += data
        if self.inline is not None:
            self.inline.append(data)


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
                script, = Page(html_text).inline_scripts
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

    @unittest.skipUnless(shutil.which("node"), "safeHref allowlist check needs Node")
    def test_safe_href_allowlists_http_https_and_rejects_other_schemes(self):
        """Executes the committed `safeHref` helper (the CodeQL js/xss-through-dom
        fix for `link()`'s `node.href = ...` assignment) under Node, not a
        reimplementation, so a regression in the shipped code is caught here."""
        template = (ROOT / "docs/ecosystem/template.html").read_text()
        match = re.search(r"const safeHref = .*?;\n", template)
        self.assertIsNotNone(match, "safeHref helper not found in template.html")
        # `location` is a browser global the standalone helper relies on for relative
        # URL resolution; stub it directly since a plain `node -e` context has none.
        harness = ('const location = {href: "https://catalog.example/page"};\n'
                   + match.group(0) + r'''
const probes = ["javascript:alert(1)", "data:text/html,<script>1</script>",
  "vbscript:msgbox(1)", "https://good.example/x", "http://good.example/y",
  "//good.example/z", "/relative/path", "file:///etc/passwd", "mailto:x@y.example"];
process.stdout.write(JSON.stringify(probes.map(safeHref)));
''')
        result = subprocess.run(["node", "-e", harness], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        resolved = json.loads(result.stdout)
        self.assertEqual(resolved[0], "about:blank", "javascript: URI must not pass through")
        self.assertEqual(resolved[1], "about:blank", "data: URI must not pass through")
        self.assertEqual(resolved[2], "about:blank", "vbscript: URI must not pass through")
        self.assertEqual(resolved[3], "https://good.example/x")
        self.assertEqual(resolved[4], "http://good.example/y")
        self.assertEqual(resolved[5], "https://good.example/z")
        self.assertEqual(resolved[6], "https://catalog.example/relative/path")
        self.assertEqual(resolved[7], "about:blank", "file: URI must not pass through")
        self.assertEqual(resolved[8], "about:blank", "mailto: URI must not pass through")

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

    def test_check_input_digest_covers_the_html_template(self):
        """A template-only change must change input_sha256, not just output_sha256."""
        self.build()
        first = json.loads(self.run_generator("--check").stdout)
        template = self.root / "docs/ecosystem/template.html"
        template.write_text(template.read_text().replace("</body>", "<!-- template-only change --></body>", 1))
        second_run = self.run_generator("--check")
        self.assertEqual(second_run.returncode, 0, second_run.stdout + second_run.stderr)
        second = json.loads(second_run.stdout)
        self.assertNotEqual(second["input_sha256"], first["input_sha256"])
        self.assertNotEqual(second["output_sha256"], first["output_sha256"])

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

    TOPIC_EDITION = "2026-09-27"
    TOPIC_CARD_SOURCE = "evidence/artifacts/token-cards/cards/search.json"

    def topic_card(self, recorded_pin="1.0"):
        """A present per-tool card: every block keeps its own evidence class, the row cites exact card bytes."""
        raw = json.dumps({"tool": "search", "pin": recorded_pin + " (fixture card)"}).encode()
        target = self.root / self.TOPIC_CARD_SOURCE
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        return {"status": "present", "edition": self.TOPIC_EDITION, "recorded_pin": recorded_pin,
                "source": {"path": self.TOPIC_CARD_SOURCE, "bytes": len(raw),
                           "sha256": hashlib.sha256(raw).hexdigest()},
                "upstream": {"evidence_class": "upstream provenance (live release metadata)",
                             "latest_release": "v1.1", "latest_date": "2026-09-24",
                             "behind_by": "One minor release behind",
                             "recommended_install": {"command": "search install",
                                                     "url": "https://github.com/example/search#install"}},
                "native_adaptation": {"evidence_class": "repository configuration review",
                                      "assessment": "Claude hook and Codex instructions follow upstream"},
                "e2e_returned_results": {"evidence_class": "local integration (upstream commands, returned data retained)",
                                         "status": "pass", "records_total": 3,
                                         "cited_records": ["search-01-query"]},
                "adapted_performance": {"evidence_class": "one class per entry; never summed across classes",
                                        "per_payload_and_lane": [
                                            {"lane": "claude_subagent", "payload": "Same query raw versus search output",
                                             "before_tokens": 400, "after_tokens": 100, "change_pct": -75.0,
                                             "encoding": "o200k_base", "evidence_class": "exact artifact comparison"}]},
                "invoke_rates": {"evidence_class": "local integration (transcript counts)",
                                 "window": "2026-09-25T11:37:28Z to 2026-09-26T23:37:28Z",
                                 "populations": [{"population": "agent_subagents", "agents_using": 14, "agents": 71,
                                                  "pct_agents_using": 0.1972, "mcp_calls": 0, "cli_calls": 85}]},
                "gpt6_review": {"evidence_class": "model review (judgment over retained sources, not execution)",
                                "review_verdict": "defects", "final_verdict": "adapted-with-gaps",
                                "summary": "Aligned with one documented gap", "open_findings": []}}

    def write_topic(self, card, **row_fields):
        row = {"component_id": "search", "group": "core", "purpose": "Find exact source",
               "upstream_commands": {"use": "search --native"},
               "returned_result_summary": "Exact source returned",
               "session_statistics": {"value": None, "summary": "Not provided by upstream"},
               "lifetime_statistics": {"value": None, "summary": "No cumulative savings counter"},
               "baseline_summary": "Keep the focused read", "lifecycle_summary": "Dated acceptance only",
               "source_paths": ["evidence/history.json"], "card": card, **row_fields}
        evidence = [card["source"]["path"]] if isinstance(card, dict) and "source" in card else []
        self.write("docs/token-efficiency-stack.json", {
            "schema_version": 1, "scope": "Dated topic evidence",
            "edition": {"date_utc": self.TOPIC_EDITION, "source_paths": evidence},
            "rows": [row]})

    def test_topic_card_joins_the_current_stack_pin_and_keeps_each_evidence_class(self):
        self.write_topic(self.topic_card())
        page, _ = self.build()
        data = json.loads(page.data)
        topic = data["efficiency"]["topic"]
        actual = topic["rows"][0]
        self.assertEqual(actual["pin"], {"version": "1.0", "repository": "https://github.com/example/search",
                                         "source": "manifests/stack.json"})
        self.assertEqual(actual["version"], "1.0")
        self.assertIsNone(actual["pin_drift"])
        self.assertIsNone(actual["card_marker"])
        card = actual["card"]
        for block in ("upstream", "native_adaptation", "e2e_returned_results", "adapted_performance",
                      "invoke_rates", "gpt6_review"):
            with self.subTest(block=block):
                self.assertTrue(card[block]["evidence_class"].strip())
        self.assertEqual(card["adapted_performance"]["per_payload_and_lane"][0]["evidence_class"],
                         "exact artifact comparison")
        # The edition's new artifacts do not exist at the immutable base: they resolve at the publication ref.
        self.assertTrue(card["source"]["url"].endswith("/blob/main/" + self.TOPIC_CARD_SOURCE))
        self.assertTrue(topic["edition"]["sources"][0]["url"].endswith("/blob/main/" + self.TOPIC_CARD_SOURCE))
        self.assertIn(self.TOPIC_CARD_SOURCE, {row["path"] for row in data["inputs"]})

    def test_topic_card_pin_drift_note_appears_only_when_the_stack_pin_differs(self):
        self.write_topic(self.topic_card(recorded_pin="0.9"))
        page, _ = self.build()
        actual = json.loads(page.data)["efficiency"]["topic"]["rows"][0]
        self.assertEqual(actual["version"], "1.0")
        self.assertEqual(actual["pin_drift"],
                         "Pin drift: this card recorded 0.9; manifests/stack.json now pins 1.0. The card's "
                         "upstream, E2E, performance and review facts describe 0.9 until a newer card edition "
                         "is recorded.")
        self.write_topic(self.topic_card(recorded_pin="1.0"))
        page, _ = self.build()
        self.assertIsNone(json.loads(page.data)["efficiency"]["topic"]["rows"][0]["pin_drift"])

    def test_topic_row_without_a_card_carries_only_the_edition_marker(self):
        self.write_topic({"status": "no card in this edition", "edition": self.TOPIC_EDITION})
        page, _ = self.build()
        actual = json.loads(page.data)["efficiency"]["topic"]["rows"][0]
        self.assertEqual(actual["card"], {"status": "no card in this edition", "edition": self.TOPIC_EDITION})
        self.assertEqual(actual["card_marker"], "No card in this edition (2026-09-27)")
        self.assertIsNone(actual["pin_drift"])
        self.assertEqual(actual["pin"]["version"], "1.0")
        # A missing card is a marker, never invented card data.
        self.write_topic({"status": "no card in this edition", "edition": self.TOPIC_EDITION,
                          "gpt6_review": {"evidence_class": "model review"}})
        result = self.run_generator("--write")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("carries only the edition marker", result.stdout)

    def test_topic_card_rejects_missing_blocks_unlabelled_figures_and_tampered_sources(self):
        cases = []
        card = self.topic_card()
        del card["gpt6_review"]
        cases.append(("missing block", card, {}, "gpt6_review with its evidence class"))
        card = self.topic_card()
        del card["adapted_performance"]["per_payload_and_lane"][0]["evidence_class"]
        cases.append(("unlabelled figure", card, {}, "comparison needs its lane, payload and evidence class"))
        card = self.topic_card()
        card["adapted_performance"]["per_payload_and_lane"][0]["change_pct"] = -80.0
        cases.append(("inconsistent change", card, {}, "comparison counts are inconsistent"))
        card = self.topic_card()
        card["source"]["sha256"] = "0" * 64
        cases.append(("tampered source", card, {}, "card source hash or size mismatch"))
        card = self.topic_card()
        card["source"]["path"] = "evidence/history.json"
        cases.append(("non-artifact source", card, {}, "card source must be a public evidence artifact"))
        cases.append(("row-level pin", self.topic_card(), {"version": "9.9"},
                      "pins come from manifests/stack.json"))
        cases.append(("missing card", None, {}, "needs a card of this edition"))
        for label, card, fields, message in cases:
            with self.subTest(case=label):
                self.write_topic(card, **fields)
                if card is None:
                    topic = json.loads((self.root / "docs/token-efficiency-stack.json").read_text())
                    del topic["rows"][0]["card"]
                    self.write("docs/token-efficiency-stack.json", topic)
                result = self.run_generator("--write")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message, result.stdout)

    # docs/ecosystem/template.html topicCard renders these four upstream fields as links (sourcedLine), so they
    # pass the build's public_url gate, the one every other external source link uses (card.source.url is built
    # by file_url instead).
    TOPIC_CARD_LINK_FIELDS = {
        "upstream.recommended_install.url": lambda upstream, url: upstream["recommended_install"].update(url=url),
        "upstream.recommended_wiring[0].url": lambda upstream, url: upstream.update(
            recommended_wiring=[{"client": "claude", "how": "Plugin marketplace", "url": url}]),
        "upstream.new_since_pin[0].url": lambda upstream, url: upstream.update(
            new_since_pin=[{"text": "Adds a JSON report", "url": url}]),
        "upstream.limitations[0].url": lambda upstream, url: upstream.update(
            limitations=[{"text": "Large files are skipped", "url": url}]),
    }

    def test_topic_card_links_outside_the_public_url_gate_fail_the_check(self):
        planted = {"plain http": "http://github.com/example/search#install",
                   "loopback address": "https://127.0.0.1/example/search",
                   "script scheme": "javascript:alert(document.domain)"}
        for field, plant in self.TOPIC_CARD_LINK_FIELDS.items():
            for label, url in planted.items():
                with self.subTest(field=field, url=label):
                    card = self.topic_card()
                    plant(card["upstream"], url)
                    self.write_topic(card)
                    result = self.run_generator("--check")
                    self.assertNotEqual(result.returncode, 0, result.stdout)
                    self.assertIn(f"token topic card {self.TOPIC_CARD_SOURCE}: {field} must be a public HTTPS URL",
                                  result.stdout)

    def test_topic_card_list_fields_reject_any_non_list_value(self):
        # The template maps over these fields, so a falsy non-list ({} or "") must not slip past the list guard.
        for field in ("recommended_wiring", "new_since_pin", "limitations"):
            for label, value in (("empty object", {}), ("empty string", ""), ("null", None)):
                with self.subTest(field=field, value=label):
                    card = self.topic_card()
                    card["upstream"][field] = value
                    self.write_topic(card)
                    result = self.run_generator("--check")
                    self.assertNotEqual(result.returncode, 0, result.stdout)
                    self.assertIn(f"token topic card {self.TOPIC_CARD_SOURCE}: upstream.{field} must be a list", result.stdout)

    def test_topic_card_public_https_links_pass_the_check_unchanged(self):
        card = self.topic_card()
        clean = {"upstream.recommended_install.url": "https://github.com/example/search#install",
                 "upstream.recommended_wiring[0].url": "https://github.com/example/search#claude-code",
                 "upstream.new_since_pin[0].url": "https://github.com/example/search/releases/tag/v1.1",
                 "upstream.limitations[0].url": "https://github.com/example/search/issues/7"}
        for field, url in clean.items():
            self.TOPIC_CARD_LINK_FIELDS[field](card["upstream"], url)
        self.write_topic(card)
        self.check_report()
        page, _ = self.build()
        upstream = json.loads(page.data)["efficiency"]["topic"]["rows"][0]["card"]["upstream"]
        self.assertEqual([upstream["recommended_install"]["url"], upstream["recommended_wiring"][0]["url"],
                          upstream["new_since_pin"][0]["url"], upstream["limitations"][0]["url"]],
                         list(clean.values()))

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

    # ------------------------------------------------------------------------- convergence by layer

    MATRIX = "catalogs/landscape/component-evidence-matrix.json"

    @staticmethod
    def convergence_matrix():
        """A generated-matrix fixture with one layer per layer_state (scripts/component_matrix.py writes the
        repository's own; only rows[].convergence and summary.convergence are read)."""
        def layer(catalog, layer_id, state, counts, factors, unresolved=(), reopened=()):
            in_use, converged, all_rows, winner_rows = counts
            return {"catalog": catalog, "layer_id": layer_id, "title": "Title " + layer_id, "winners": [],
                    "convergence": {
                        "layer_state": state, "verdict_checked_at": "2026-09-22",
                        "reopened_by": [{"sweep_id": sweep, "date": day} for sweep, day in reopened],
                        "in_use": in_use, "converged": converged, "all_rows": all_rows,
                        "recorded_winner_rows": winner_rows,
                        "factors": {name: dict(zip(("true", "false", "unknown"), values)) for name, values in
                                    zip(("verdict_winner", "pin_current", "host_e2e"), factors)},
                        "unresolved": [{"id": name, "repository": "https://github.com/example/" + name,
                                        "reason": "no manifests/stack.json id, alias or repository match"}
                                       for name in unresolved],
                        "manifest_layer_found": True, "winners_without_manifest_row": [],
                        "winner_rows": [], "components": [], "invoke": None,
                        "invoke_reason": "no post-fix invoke receipt yet"}}
        rows = [
            layer("foundation", "f-current", "confirmed_current", (3, 1, 4, 2),
                  ((2, 1, 0), (2, 0, 1), (1, 1, 1)), unresolved=("stranger",)),
            layer("foundation", "f-reopened", "recorded_reopened", (1, 0, 1, 1),
                  ((1, 0, 0), (1, 0, 0), (1, 0, 0)), reopened=(("sweep-0926", "2026-09-26"),)),
            layer("us-equities", "u-none", "no_selection", (1, 0, 2, 0), ((0, 1, 0), (0, 0, 1), (0, 0, 1))),
            layer("us-equities", "u-pending", "pending_lanes", (2, 0, 2, 0), ((0, 0, 2), (1, 1, 0), (0, 0, 2))),
        ]
        block = {
            "frozen_at": "2026-09-27",
            "definitions": [{"term": "layer_state", "definition": "Exactly one of four states."},
                            {"term": "converged", "definition": "Every factor true in a confirmed_current layer."}],
            "sources": {"verdict_ledgers": {"foundation": "catalogs/landscape/foundation.json",
                                            "us-equities": "catalogs/landscape/us-equities.json"},
                        "saturation_ledger": "catalogs/saturation/ledger.json",
                        "completed_sweeps": [{"sweep_id": "sweep-0926", "date": "2026-09-26", "layers": 4,
                                              "manifest_ref": "catalogs/sota-convergence/manifest-20260926.json"}],
                        "stack": "manifests/stack.json",
                        "aliases": "tools/sota-convergence/receipt-component-aliases.json",
                        "host_e2e_platform": "linux-wsl2-x86_64"},
            "layer_states": {"confirmed_current": 1, "no_selection": 1, "pending_lanes": 1, "recorded_reopened": 1},
            "catalogs": {"foundation": {"layers": 2, "in_use": 4, "converged": 1, "share": 0.25, "unresolved": 1},
                         "us-equities": {"layers": 2, "in_use": 3, "converged": 0, "share": 0.0, "unresolved": 0}},
            "overall": {"layers": 4, "in_use": 7, "converged": 1, "share": 0.1429, "unresolved": 1},
            "newest_manifest": {"path": "catalogs/sota-convergence/manifest-20260926.json",
                                "id": "sota-convergence-20260926", "checked_at": "2026-09-26"},
            "newest_verdict_checked_at": {"foundation": "2026-09-22", "us-equities": "2026-09-22"},
            "manifest_layers_without_matrix_row": [],
        }
        return {"schema_version": 1, "checked_at": "2026-09-22", "rows": rows, "summary": {"convergence": block}}

    def join_gap_matrix(self):
        """convergence_matrix() plus a recorded layer missing from the newest manifest, whose winner therefore has
        no manifest row, and a manifest layer without a matrix row."""
        matrix = self.convergence_matrix()
        missing = json.loads(json.dumps(matrix["rows"][1]))
        missing.update(layer_id="f-missing", title="Title f-missing")
        missing["convergence"].update(
            in_use=0, converged=0, all_rows=0, recorded_winner_rows=0, manifest_layer_found=False,
            winners_without_manifest_row=["lonely-winner"],
            factors={name: {"true": 0, "false": 0, "unknown": 0} for name in ("verdict_winner", "pin_current", "host_e2e")})
        matrix["rows"].insert(2, missing)
        summary = matrix["summary"]["convergence"]
        summary["layer_states"]["recorded_reopened"] += 1
        summary["catalogs"]["foundation"]["layers"] += 1
        summary["overall"]["layers"] += 1
        summary["manifest_layers_without_matrix_row"] = [{"catalog": "us-equities", "layer_id": "u-unlisted"}]
        return matrix

    def write_matrix(self, matrix):
        self.matrix = matrix
        self.write(self.MATRIX, matrix)

    def use_real_template(self):
        self.write("docs/ecosystem/template.html", (ROOT / "docs/ecosystem/template.html").read_text())

    def test_convergence_is_absent_without_the_generated_matrix(self):
        self.use_real_template()
        page, _ = self.build()
        self.assertIsNone(json.loads(page.data)["convergence"])
        self.assertIn("hidden", page.elements["tab-convergence"])

    def test_convergence_block_is_embedded_from_the_matrix_with_its_hash_and_dates(self):
        self.use_real_template()
        self.write_matrix(self.convergence_matrix())
        page, text = self.build()
        data = json.loads(page.data)
        convergence = data["convergence"]
        self.assertEqual([(row["catalog"], row["layer_id"], row["title"], row["layer_state"])
                          for row in convergence["layers"]], [
            ("foundation", "f-current", "Title f-current", "confirmed_current"),
            ("foundation", "f-reopened", "Title f-reopened", "recorded_reopened"),
            ("us-equities", "u-none", "Title u-none", "no_selection"),
            ("us-equities", "u-pending", "Title u-pending", "pending_lanes")])
        block = self.matrix["summary"]["convergence"]
        for key in ("frozen_at", "definitions", "sources", "layer_states", "catalogs", "overall",
                    "newest_manifest", "newest_verdict_checked_at", "manifest_layers_without_matrix_row"):
            with self.subTest(key=key):
                self.assertEqual(convergence[key], block[key])
        first = self.matrix["rows"][0]["convergence"]
        embedded = convergence["layers"][0]
        for key in ("verdict_checked_at", "reopened_by", "in_use", "converged", "all_rows", "recorded_winner_rows",
                    "factors", "unresolved", "invoke", "invoke_reason", "manifest_layer_found",
                    "winners_without_manifest_row"):
            with self.subTest(key=key):
                self.assertEqual(embedded[key], first[key])
        # Per-component detail stays in the matrix; the page links it.
        self.assertNotIn("components", embedded)
        self.assertIn("/blob/main/" + self.MATRIX, convergence["url"])
        hashes = {row["path"]: row["sha256"] for row in data["inputs"]}
        self.assertEqual(hashes[self.MATRIX], hashlib.sha256((self.root / self.MATRIX).read_bytes()).hexdigest())
        self.assertEqual(page.elements["convergence"]["role"], "tabpanel")
        self.assertEqual(page.elements["tab-convergence"]["aria-controls"], "convergence")
        self.assertIn("Convergence by layer", text)
        self.assertEqual(len(page.scripts), 2)

        def reopen_another_layer():
            self.matrix["rows"][0]["convergence"]["reopened_by"] = [{"sweep_id": "sweep-0927", "date": "2026-09-27"}]
            self.matrix["rows"][0]["convergence"]["layer_state"] = "recorded_reopened"
            self.matrix["rows"][0]["convergence"]["converged"] = 0
            summary = self.matrix["summary"]["convergence"]
            summary["layer_states"].update(confirmed_current=0, recorded_reopened=2)
            summary["catalogs"]["foundation"].update(converged=0, share=0.0)
            summary["overall"].update(converged=0, share=0.0)
            self.write_matrix(self.matrix)
        self.assert_check_digest_changes(reopen_another_layer)

    def test_convergence_block_must_agree_with_its_rows(self):
        cases = (
            (lambda m: m["summary"].pop("convergence"), "component_matrix.py --write"),
            (lambda m: m["rows"][2].pop("convergence"), "every component matrix row needs a convergence object"),
            (lambda m: m["rows"][0]["convergence"].update(layer_state="converging"), "unknown convergence layer_state"),
            (lambda m: m["rows"][0]["convergence"]["factors"]["host_e2e"].update(unknown=2), "must add up to in_use"),
            (lambda m: m["rows"][1]["convergence"].update(converged=1), "only a confirmed_current layer"),
            (lambda m: m["rows"][0]["convergence"].update(in_use=-1), "nonnegative integers"),
            (lambda m: m["rows"][0]["convergence"].update(invoke_reason=""), "null invoke needs its reason"),
            (lambda m: m["summary"]["convergence"]["overall"].update(converged=2), "differs from its layer rows"),
            (lambda m: m["summary"]["convergence"]["layer_states"].update(pending_lanes=2), "differs from its layer rows"),
            (lambda m: m["summary"]["convergence"]["catalogs"]["foundation"].update(share=0.5), "differs from its layer rows"),
            (lambda m: m["summary"]["convergence"].update(definitions=[]), "convergence definitions"),
            (lambda m: m["rows"][0]["convergence"].update(manifest_layer_found="yes"), "manifest_layer_found"),
            # A layer missing from the newest manifest has no manifest rows to count.
            (lambda m: m["rows"][0]["convergence"].update(manifest_layer_found=False), "manifest_layer_found"),
            (lambda m: m["rows"][0]["convergence"].update(winners_without_manifest_row=[None]),
             "winners_without_manifest_row"),
            (lambda m: m["summary"]["convergence"].update(manifest_layers_without_matrix_row="none"),
             "manifest_layers_without_matrix_row"),
            # A manifest layer listed as having no matrix row while the matrix has that row.
            (lambda m: m["summary"]["convergence"].update(
                manifest_layers_without_matrix_row=[{"catalog": "foundation", "layer_id": "f-current"}]),
             "manifest_layers_without_matrix_row"),
        )
        for mutate, message in cases:
            with self.subTest(message=message):
                matrix = self.convergence_matrix()
                mutate(matrix)
                self.write_matrix(matrix)
                result = self.run_generator("--write")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message, result.stdout)

    def test_convergence_text_is_inert_public_data(self):
        self.use_real_template()
        hostile = '</script><script src="https://invalid.example/steal.js"></script>'
        matrix = self.convergence_matrix()
        matrix["rows"][0]["title"] = hostile
        matrix["rows"][0]["convergence"]["unresolved"][0]["reason"] = hostile
        matrix["summary"]["convergence"]["definitions"][0]["definition"] = hostile
        self.write_matrix(matrix)
        page, _ = self.build()
        self.assertEqual(len(page.scripts), 2)
        self.assertEqual(page.external_assets, [])
        convergence = json.loads(page.data)["convergence"]
        self.assertEqual(convergence["definitions"][0]["definition"], hostile)
        self.assertEqual(convergence["layers"][0]["unresolved"][0]["reason"], hostile)

    CONVERGENCE_FUNCTIONS = ("convergenceSummaryLines", "convergenceTableRows", "convergenceListings",
                             "renderConvergence")

    def render_convergence_functions(self, convergence):
        """Run the page's pure convergence functions (all but renderConvergence) on ``convergence`` in Node."""
        template = (ROOT / "docs/ecosystem/template.html").read_text()
        functions = [re.search(r"function " + name + r"\(.*?^}", template, re.S | re.M).group(0)
                     for name in self.CONVERGENCE_FUNCTIONS]
        for source in functions:
            # No typed number: every count, share and date on the page comes from the matrix. A digit inside
            # an identifier (host_e2e) is a name, not a number.
            self.assertNotRegex(source, r"(?<![A-Za-z_$])\d")
        script = "\n".join(functions[:-1]) + (
            "\nconst input = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));"
            "\nprocess.stdout.write(JSON.stringify({summary: convergenceSummaryLines(input),"
            " rows: convergenceTableRows(input), listings: convergenceListings(input)}));")
        result = subprocess.run(["node", "-e", script], input=json.dumps(convergence), capture_output=True,
                                text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    @unittest.skipUnless(shutil.which("node"), "Convergence rendering check needs Node")
    def test_convergence_rendering_reads_every_number_date_and_definition_from_the_data(self):
        self.write_matrix(self.convergence_matrix())
        page, _ = self.build()
        rendered = self.render_convergence_functions(json.loads(page.data)["convergence"])
        self.assertEqual(rendered["rows"], [
            ["foundation/f-current", "confirmed_current", "2026-09-22", "-", "3", "1", "2/1/0", "2/0/1", "1/1/1",
             "4", "2", "stranger", "null"],
            ["foundation/f-reopened", "recorded_reopened", "2026-09-22", "sweep-0926", "1", "0", "1/0/0", "1/0/0",
             "1/0/0", "1", "1", "-", "null"],
            ["us-equities/u-none", "no_selection", "2026-09-22", "-", "1", "0", "0/1/0", "0/0/1", "0/0/1", "2", "0",
             "-", "null"],
            ["us-equities/u-pending", "pending_lanes", "2026-09-22", "-", "2", "0", "0/0/2", "1/1/0", "0/0/2", "2",
             "0", "-", "null"]])
        summary = "\n".join(rendered["summary"])
        self.assertNotIn("in-use components", summary)
        for expected in ("Layer states: confirmed_current 1 · no_selection 1 · pending_lanes 1 · recorded_reopened 1",
                         "foundation: 1 of 4 in-use layer-component rows converged across 2 layers (share 0.25); "
                         "1 unresolved manifest rows",
                         "overall: 1 of 7 in-use layer-component rows converged across 4 layers (share 0.1429); "
                         "1 unresolved manifest rows",
                         "a component in several layers counts once per layer",
                         "Newest sweep manifest: sota-convergence-20260926, checked_at 2026-09-26 "
                         "(catalogs/sota-convergence/manifest-20260926.json)",
                         "Newest verdict checked_at: foundation 2026-09-22 · us-equities 2026-09-22",
                         "Completed sweeps: sweep-0926 (2026-09-26)",
                         "host_e2e platform: linux-wsl2-x86_64",
                         "Definitions frozen 2026-09-27"):
            with self.subTest(expected=expected):
                self.assertIn(expected, summary)
        self.assertEqual(rendered["listings"], [
            ["Unresolved manifest rows",
             ["foundation/f-current · stranger: no manifests/stack.json id, alias or repository match"]],
            ["Recorded winners without a row in the newest sweep manifest", []],
            ["Layers missing from the newest sweep manifest", []],
            ["Newest sweep manifest layers without a matrix row", []]])

    @unittest.skipUnless(shutil.which("node"), "Convergence rendering check needs Node")
    def test_the_page_lists_join_gaps_from_the_data(self):
        """Next to the unresolved rows, the page lists recorded winners without a manifest row, layers missing
        from the newest manifest and manifest layers without a matrix row, each read from the matrix."""
        self.write_matrix(self.join_gap_matrix())
        page, _ = self.build()
        convergence = json.loads(page.data)["convergence"]
        self.assertEqual(convergence["manifest_layers_without_matrix_row"],
                         [{"catalog": "us-equities", "layer_id": "u-unlisted"}])
        rendered = self.render_convergence_functions(convergence)
        self.assertEqual(rendered["listings"][1:], [
            ["Recorded winners without a row in the newest sweep manifest", ["foundation/f-missing: lonely-winner"]],
            ["Layers missing from the newest sweep manifest", ["foundation/f-missing"]],
            ["Newest sweep manifest layers without a matrix row", ["us-equities/u-unlisted"]]])
        self.assertEqual(rendered["rows"][2][:6], ["foundation/f-missing", "recorded_reopened", "2026-09-22",
                                                   "sweep-0926", "0", "0"])

    # Runs a generated page's whole inline script against the page's own elements (every id and data-tab /
    # data-open / data-catalog-tab element, with its attributes), so a renderer that throws, or looks up an id
    # the page lacks, shows up here instead of as the page's recovery screen.
    PAGE_HARNESS = r'''
const vm = require("node:vm");
const input = JSON.parse(require("node:fs").readFileSync(0, "utf8"));
class Element {
  constructor(tag, attrs) {
    this.tagName = tag.toUpperCase(); this.attrs = {...attrs}; this.children = []; this.text = "";
    this.hidden = Object.prototype.hasOwnProperty.call(attrs, "hidden"); this.className = attrs.class || "";
    this.dataset = {}; this.listeners = {}; this.value = ""; this.checked = false; this.open = false;
    this.type = attrs.type || "";
    for (const [key, value] of Object.entries(attrs)) if (key.startsWith("data-"))
      this.dataset[key.slice(5).replace(/-([a-z])/g, (_, letter) => letter.toUpperCase())] = value === null ? "" : value;
  }
  set textContent(value) { this.text = String(value); this.children = []; }
  get textContent() { return this.text + this.children.map(child => child.textContent).join(""); }
  appendChild(child) { this.children.push(child); return child; }
  replaceChildren(...children) { this.children = children; this.text = ""; }
  get childElementCount() { return this.children.length; }
  setAttribute(key, value) { this.attrs[key] = String(value); }
  getAttribute(key) { return key in this.attrs ? this.attrs[key] : null; }
  addEventListener(type, listener) { (this.listeners[type] ||= []).push(listener); }
  focus() {} click() {} showModal() { this.open = true; } close() { this.open = false; }
  getBoundingClientRect() { return {left: 0, right: 0, top: 0, bottom: 0}; }
}
const byId = {}, ordered = [], missing = [], errors = [];
for (const [tag, attrs] of input.elements) {
  const element = new Element(tag, attrs); ordered.push(element); if (attrs.id) byId[attrs.id] = element;
}
byId["ecosystem-data"].text = input.data;
const document = {
  getElementById(id) { if (!(id in byId)) { missing.push(id); return null; } return byId[id]; },
  createElement(tag) { return new Element(tag, {}); },
  querySelectorAll(selector) {
    const match = selector.match(/^\[([a-z-]+)\]$/);
    if (!match) throw new Error("Unexpected selector: " + selector);
    return ordered.filter(element => match[1] in element.attrs);
  },
  addEventListener() {}, activeElement: {tagName: "BODY"},
};
const location = {hash: "#" + input.tab, href: "https://catalog.example/index.html"};
vm.runInNewContext(input.script, {document, location, window: {scrollTo() {}, addEventListener() {}, location},
  history: {replaceState() {}}, requestAnimationFrame(callback) { callback(); }, URL, Blob: class {}, setTimeout, atob,
  console: {error(message, error) { errors.push(String((error && error.stack) || error || message)); }}});
const text = id => byId[id] ? byId[id].children.map(child => child.textContent) : null;
process.stdout.write(JSON.stringify({errors, missing, app_hidden: byId["catalog-app"].hidden,
  recovery_hidden: byId["catalog-recovery"].hidden, tab_hidden: (byId["tab-convergence"] || {}).hidden,
  panel_hidden: (byId["convergence"] || {}).hidden,
  rows: (byId["convergence-rows"] || {children: []}).children.map(row => row.children.map(cell => cell.textContent)),
  summary: text("convergence-summary"), definitions: byId["convergence-definitions"] ? byId["convergence-definitions"].textContent : null,
  token_topic: byId["token-topic"] ? byId["token-topic"].textContent : null,
  architecture_tab_hidden: (byId["tab-architecture"] || {}).hidden, architecture_panel_hidden: (byId["architecture"] || {}).hidden,
  architecture_edition: byId["architecture-edition"] ? byId["architecture-edition"].textContent : null,
  architecture: byId["architecture-topic"] ? byId["architecture-topic"].textContent : null}));
'''

    @staticmethod
    def page_elements(html_text):
        class Elements(HTMLParser):
            def __init__(self):
                super().__init__()
                self.found = []

            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if "id" in attrs or {"data-tab", "data-open", "data-catalog-tab"} & set(attrs):
                    self.found.append([tag, attrs])

        parser = Elements()
        parser.feed(html_text)
        return parser.found

    def run_page(self, html_text, tab="convergence"):
        page = Page(html_text)
        script, = page.inline_scripts
        result = subprocess.run(["node", "-e", self.PAGE_HARNESS], input=json.dumps({
            "script": script, "data": page.data, "elements": self.page_elements(html_text), "tab": tab}),
            capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    @unittest.skipUnless(shutil.which("node"), "Generated page script execution needs Node")
    def test_the_generated_page_script_renders_the_convergence_tab(self):
        self.use_real_template()
        _, without = self.build()
        observed = self.run_page(without)
        self.assertEqual((observed["errors"], observed["missing"]), ([], []))
        self.assertEqual((observed["app_hidden"], observed["recovery_hidden"]), (False, True))
        # No matrix: the tab stays hidden and #convergence falls back to the overview.
        self.assertEqual((observed["tab_hidden"], observed["panel_hidden"], observed["rows"]), (True, True, []))

        self.write_matrix(self.convergence_matrix())
        _, with_matrix = self.build()
        observed = self.run_page(with_matrix)
        self.assertEqual((observed["errors"], observed["missing"]), ([], []))
        self.assertEqual((observed["app_hidden"], observed["recovery_hidden"]), (False, True))
        self.assertEqual((observed["tab_hidden"], observed["panel_hidden"]), (False, False))
        self.assertEqual([row[:6] for row in observed["rows"]], [
            ["foundation/f-current", "confirmed_current", "2026-09-22", "-", "3", "1"],
            ["foundation/f-reopened", "recorded_reopened", "2026-09-22", "sweep-0926", "1", "0"],
            ["us-equities/u-none", "no_selection", "2026-09-22", "-", "1", "0"],
            ["us-equities/u-pending", "pending_lanes", "2026-09-22", "-", "2", "0"]])
        self.assertEqual(observed["summary"][0],
                         "Layer states: confirmed_current 1 · no_selection 1 · pending_lanes 1 · recorded_reopened 1")
        for item in self.matrix["summary"]["convergence"]["definitions"]:
            self.assertIn(item["term"] + item["definition"], observed["definitions"])
        self.assertIn("foundation/f-current · stranger: no manifests/stack.json id, alias or repository match",
                      observed["definitions"])
        self.assertIn("Recorded winners without a row in the newest sweep manifestNone.", observed["definitions"])

        self.write_matrix(self.join_gap_matrix())
        _, with_gaps = self.build()
        observed = self.run_page(with_gaps)
        self.assertEqual((observed["errors"], observed["missing"]), ([], []))
        for expected in ("Recorded winners without a row in the newest sweep manifestfoundation/f-missing: lonely-winner",
                         "Layers missing from the newest sweep manifestfoundation/f-missing",
                         "Newest sweep manifest layers without a matrix rowus-equities/u-unlisted"):
            self.assertIn(expected, observed["definitions"])

    @unittest.skipUnless(shutil.which("node"), "Generated page script execution needs Node")
    def test_the_generated_page_script_renders_the_token_topic_cards(self):
        """The topic section shows each card block with its evidence class, the drift note and the marker."""
        self.use_real_template()
        self.write_topic(self.topic_card(recorded_pin="0.9"))
        _, with_card = self.build()
        observed = self.run_page(with_card)
        self.assertEqual((observed["errors"], observed["missing"]), ([], []))
        topic = observed["token_topic"]
        for expected in (
                "Edition 2026-09-27",
                "Pin drift: this card recorded 0.9; manifests/stack.json now pins 1.0. The card's upstream, E2E, "
                "performance and review facts describe 0.9 until a newer card edition is recorded.",
                "Per-tool card · edition 2026-09-27",
                "Card source: " + self.TOPIC_CARD_SOURCE + " ↗",
                "UpstreamEvidence class: upstream provenance (live release metadata)",
                "Latest release v1.1 (2026-09-24)", "Behind: One minor release behind",
                "Recommended install: search install",
                "Native adaptationEvidence class: repository configuration review",
                "Assessment: Claude hook and Codex instructions follow upstream",
                "E2E returned resultsEvidence class: local integration (upstream commands, returned data retained)",
                "Status pass", "Records: 3; cited: search-01-query",
                "Adapted performance per payload and laneEvidence class: one class per entry; never summed across classes",
                "claude_subagent · Same query raw versus search output: 400 → 100 tokens (-75%) · o200k_base · "
                "exact artifact comparison",
                "Invoke ratesEvidence class: local integration (transcript counts)",
                "Window: 2026-09-25T11:37:28Z to 2026-09-26T23:37:28Z",
                "agent_subagents: 14 of 71 agents (19.72%) · MCP calls 0 · CLI calls 85",
                "GPT-6 reviewEvidence class: model review (judgment over retained sources, not execution)",
                "Verdict adapted-with-gaps (review: defects)", "Aligned with one documented gap"):
            with self.subTest(expected=expected[:60]):
                self.assertIn(expected, topic)
        self.assertNotIn("No card in this edition", topic)

        self.write_topic({"status": "no card in this edition", "edition": self.TOPIC_EDITION})
        _, without_card = self.build()
        observed = self.run_page(without_card)
        self.assertEqual((observed["errors"], observed["missing"]), ([], []))
        self.assertIn("No card in this edition (2026-09-27)", observed["token_topic"])
        self.assertNotIn("Pin drift", observed["token_topic"])
        self.assertNotIn("Per-tool card", observed["token_topic"])

    def test_the_repository_matrix_convergence_block_is_accepted(self):
        """The real generated matrix, not the fixture: the page accepts what scripts/component_matrix.py writes."""
        source = ROOT / self.MATRIX
        self.write(self.MATRIX, source.read_text(encoding="utf-8"))
        page, _ = self.build()
        convergence = json.loads(page.data)["convergence"]
        real = json.loads(source.read_text(encoding="utf-8"))
        self.assertEqual(convergence["overall"], real["summary"]["convergence"]["overall"])
        self.assertEqual([(row["catalog"], row["layer_id"]) for row in convergence["layers"]],
                         [(row["catalog"], row["layer_id"]) for row in real["rows"]])

    # The dated new-WSL architecture edition (the "Final architecture" tab).
    ARCHITECTURE = "catalogs/foundation/new-wsl-architecture-20261001.json"
    ARCHITECTURE_SOURCE = "docs/decisions/edition-fixture.md"
    ARCHITECTURE_VERDICTS = ("closed", "selection_of_record_open", "provisional", "comparison_required",
                             "new_host_required", "no_selection")
    ARCHITECTURE_CLASSES = ("upstream_test", "upstream_example_or_native_operation", "local_integration_check",
                            "synthetic_fixture", "independent_observation", "structural_validation", "source_review",
                            "none_recorded")
    CLOSE_ONLY_WHEN = ["Selected choice, alternatives and evidence", "Frozen candidate set",
                       "Comparisons and target-host checks", "Second independent review", "Dated closure record"]

    def architecture_winner(self, **fields):
        source = {"source_path": self.ARCHITECTURE_SOURCE}
        return {"component_id": "search", "repository": "https://github.com/example/search", "pin": "1.0",
                "pin_source": "manifests/stack.json:1",
                "install": {"command": "search install", "kind": "repo_recipe", **source},
                "acceptance": {"command": "search --self-test", "evidence_class": "upstream_test", **source},
                "upstream_currency": {"latest_release": "v1.1 (2026-09-30)", "checked_at": "2026-10-01T05:00Z",
                                      "pin_is_latest": "no", "url": "https://github.com/example/search/releases"},
                **fields}

    def architecture_row(self, layer_id="native-clients", catalog="foundation", **fields):
        source = {"source_path": self.ARCHITECTURE_SOURCE}
        return {"layer_id": layer_id, "catalog": catalog, "title": "Title " + layer_id,
                "winners": [self.architecture_winner()], "verdict": "selection_of_record_open",
                "closure": {"c1": "met", "c2": "partial", "c3": "unmet", "c4": "unmet", "c5": "partial",
                            "missing": "c2: candidate set not frozen; c3: no new-distro run; c4: no second review; "
                                       "c5: no closure record"},
                "reasons": [{"text": "Recorded verdict winner", **source}],
                "evidence_class": "upstream_test",
                "alternatives": [{"name": "Other client", "verdict": "refuted on fit", **source}],
                "new_host_steps": ["Install the pinned client", "Sign in natively"],
                "gates": [{"text": "Native sign-in on the new distro", "kind": "user_side", **source}],
                "owner_lane": "foundation", "notes": "", **fields}

    def architecture_edition(self):
        pending = {"path": "docs/pending-recipe.md", "pull_request": 569, "commit": "eabe7654"}
        # The five closure texts joined in order with newlines, no trailing newline.
        texts_sha256 = hashlib.sha256("\n".join(self.CLOSE_ONLY_WHEN).encode()).hexdigest()
        return {"schema_version": 1, "kind": "new_wsl_architecture_edition",
                "edition": {"date_utc": "2026-10-01", "base_commit": "c" * 40, "scope": "Fixture edition",
                            "close_only_when_sha256": texts_sha256,
                            "verdict_rules": ["A layer is closed only when all five close_only_when items hold."],
                            "verdict_values": {value: "Meaning of " + value for value in self.ARCHITECTURE_VERDICTS},
                            "evidence_classes": {value: "Label of " + value for value in self.ARCHITECTURE_CLASSES},
                            "sources": [{"source_path": self.ARCHITECTURE_SOURCE}]},
                "rows": [self.architecture_row(),
                         self.architecture_row("backtesting-engine", "us-equities", verdict="no_selection",
                                               winners=[], evidence_class="none_recorded",
                                               closure={**{item: "unknown" for item in ("c1", "c2", "c3", "c4", "c5")},
                                                        "missing": "; ".join(item + ": assessment pending" for item
                                                                             in ("c1", "c2", "c3", "c4", "c5"))}),
                         self.architecture_row("cross:credential-practice", "cross",
                                               reasons=[{"text": "Recipe lands with its pull request",
                                                         "pending_source": pending}],
                                               gates=[{"text": "Upstream fix pending", "kind": "upstream",
                                                       "url": "https://github.com/example/search/issues/7"}])]}

    def write_architecture(self, edition, close_only_when=None, foundation_layers=("native-clients",)):
        self.write("catalogs/foundation/manifest.json", {"layers": [
            {"id": layer, "title": layer.replace("-", " ").capitalize()} for layer in foundation_layers]})
        self.write("catalogs/landscape/research-state.json", {
            "saturation": {"close_only_when": self.CLOSE_ONLY_WHEN if close_only_when is None else close_only_when},
            "layers": [{"catalog": "foundation", "layer_id": "native-clients", "status": "on_requirement_change"},
                       {"catalog": "us-equities", "layer_id": "backtesting-engine", "status": "comparison_required"},
                       {"catalog": "us-equities", "layer_id": "execution-broker", "status": "comparison_required"}]})
        self.write(self.ARCHITECTURE_SOURCE, "# Fixture edition record\n")
        self.write(self.ARCHITECTURE, edition)

    def test_architecture_edition_validates_and_joins_pins_sources_and_closure_items(self):
        self.write_architecture(self.architecture_edition())
        page, _ = self.build()
        data = json.loads(page.data)
        architecture = data["architecture"]
        self.assertEqual([(row["catalog"], row["layer_id"], row["verdict"]) for row in architecture["rows"]], [
            ("foundation", "native-clients", "selection_of_record_open"),
            ("us-equities", "backtesting-engine", "no_selection"),
            ("cross", "cross:credential-practice", "selection_of_record_open")])
        self.assertEqual([row["research_status"] for row in architecture["rows"]],
                         ["on_requirement_change", "comparison_required", None])
        # A catalog layer without a row is listed as a gap, never silently dropped.
        self.assertEqual(architecture["missing_layers"], ["us-equities/execution-broker"])
        self.assertEqual([(item["id"], item["text"]) for item in architecture["edition"]["closure_items"]],
                         list(zip(("c1", "c2", "c3", "c4", "c5"), self.CLOSE_ONLY_WHEN)))
        winner = architecture["rows"][0]["winners"][0]
        self.assertEqual((winner["label"], winner["pin"]), ("search", "1.0"))
        self.assertTrue(winner["pin_source"]["url"].endswith("/blob/main/manifests/stack.json#L1"))
        # The edition's sources are newer than the immutable base: they resolve at the publication ref.
        self.assertTrue(winner["install"]["source"]["url"].endswith("/blob/main/" + self.ARCHITECTURE_SOURCE))
        self.assertTrue(architecture["url"].endswith("/blob/main/" + self.ARCHITECTURE))
        self.assertEqual(architecture["rows"][2]["reasons"][0]["source"], {
            "kind": "pending", "path": "docs/pending-recipe.md", "pull_request": 569, "commit": "eabe7654",
            "url": "https://github.com/example/public-stack/pull/569"})
        self.assertEqual(architecture["rows"][2]["gates"][0]["source"],
                         {"kind": "url", "url": "https://github.com/example/search/issues/7"})
        hashed = {row["path"] for row in data["inputs"]}
        self.assertLessEqual({self.ARCHITECTURE, self.ARCHITECTURE_SOURCE, "catalogs/foundation/manifest.json",
                              "catalogs/landscape/research-state.json"}, hashed)
        # A pending source whose file is absent is linked through its pull request and hashes nothing.
        self.assertFalse((self.root / "docs/pending-recipe.md").exists())
        self.assertNotIn("docs/pending-recipe.md", hashed)
        # Once the file exists it landed after this edition's base: hashed and linked like a source_path, and the
        # build passes, so a later merge of that pull request never breaks main.
        self.write("docs/pending-recipe.md", "# Landed recipe\n")
        page, _ = self.build()
        data = json.loads(page.data)
        landed = data["architecture"]["rows"][2]["reasons"][0]["source"]
        self.assertEqual({key: value for key, value in landed.items() if key != "url"}, {
            "kind": "landed", "path": "docs/pending-recipe.md", "pull_request": 569, "commit": "eabe7654"})
        self.assertTrue(landed["url"].endswith("/blob/main/docs/pending-recipe.md"))
        self.assertIn("docs/pending-recipe.md", {row["path"] for row in data["inputs"]})

    def test_architecture_tab_is_hidden_without_the_edition(self):
        self.use_real_template()
        page, _ = self.build()
        self.assertIsNone(json.loads(page.data)["architecture"])
        self.assertIn("hidden", page.elements["tab-architecture"])
        self.assertEqual(page.elements["tab-architecture"]["aria-controls"], "architecture")
        self.assertEqual(page.elements["architecture"]["role"], "tabpanel")
        self.write_architecture(self.architecture_edition())
        page, _ = self.build()
        self.assertIsNotNone(json.loads(page.data)["architecture"])
        self.assertEqual(len(page.scripts), 2)

    def test_architecture_edition_change_changes_the_check_digest(self):
        edition = self.architecture_edition()
        self.write_architecture(edition)

        def reword_a_reason():
            edition["rows"][0]["reasons"][0]["text"] = "Recorded verdict winner, reworded"
            self.write(self.ARCHITECTURE, edition)
        self.assert_check_digest_changes(reword_a_reason)

    ARCHITECTURE_HOSTILE = '</script><script src="https://invalid.example/steal.js"></script>'

    def write_hostile_architecture(self):
        hostile = self.ARCHITECTURE_HOSTILE
        edition = self.architecture_edition()
        row = edition["rows"][0]
        row["title"] = row["notes"] = row["reasons"][0]["text"] = hostile
        row["new_host_steps"] = [hostile]
        self.write_architecture(edition)
        return hostile

    def test_architecture_text_is_inert_public_data(self):
        self.use_real_template()
        hostile = self.write_hostile_architecture()
        page, _ = self.build()
        self.assertEqual(len(page.scripts), 2)
        self.assertEqual(page.external_assets, [])
        embedded = json.loads(page.data)["architecture"]["rows"][0]
        self.assertEqual((embedded["title"], embedded["notes"], embedded["reasons"][0]["text"],
                          embedded["new_host_steps"]), (hostile, hostile, hostile, [hostile]))

    @unittest.skipUnless(shutil.which("node"), "Generated page script execution needs Node")
    def test_the_generated_page_renders_hostile_architecture_text_as_text(self):
        """The renderer writes text nodes only: the harness elements have no markup parser, so a renderer that
        wrote the string as markup would lose it from textContent and this test would fail."""
        self.use_real_template()
        hostile = self.write_hostile_architecture()
        _, text = self.build()
        observed = self.run_page(text, tab="architecture")
        self.assertEqual((observed["errors"], observed["missing"]), ([], []))
        table = observed["architecture"]
        for expected in (hostile + "foundation/native-clients", hostile + " (" + self.ARCHITECTURE_SOURCE + ") ↗",
                         "Notes: " + hostile, "New-host steps, in order" + hostile + "Gates"):
            with self.subTest(expected=expected[:60]):
                self.assertIn(expected, table)
        self.assertEqual(table.count(hostile), 4)

    def test_architecture_edition_rejects_each_invalid_contract(self):
        def winner(edition):
            return edition["rows"][0]["winners"][0]

        def reason(edition):
            return edition["rows"][0]["reasons"][0]
        cases = (
            (lambda e: e.update(schema_version=2), "unsupported architecture edition schema"),
            (lambda e: e.update(kind="other"), "architecture edition kind must be new_wsl_architecture_edition"),
            (lambda e: e["edition"].pop("base_commit"), "architecture edition needs exactly its date, base commit"),
            (lambda e: e["edition"].update(close_only_when_sha256="0" * 63),
             "architecture edition needs exactly its date, base commit"),
            (lambda e: e["edition"]["verdict_values"].pop("closed"),
             "architecture edition must define every value of verdict_values"),
            (lambda e: e.update(rows=[]), "architecture rows must be a non-empty list"),
            (lambda e: e["rows"][0].update(winner={}), "architecture row has an unknown field"),
            (lambda e: e["rows"][0].update(layer_id="unknown-layer"),
             "architecture layer_id must be a known catalog layer or a cross: id"),
            (lambda e: e["rows"][0].update(catalog="us-equities"), "architecture row catalog must match its layer"),
            (lambda e: e["rows"][0].update(title=" "), "architecture row needs its title"),
            (lambda e: e["rows"][0].pop("owner_lane"), "architecture row needs its owner_lane"),
            (lambda e: e["rows"][0].update(notes=None), "architecture row notes must be text"),
            (lambda e: e["rows"][0].update(verdict="done"), "unknown architecture verdict"),
            (lambda e: e["rows"][0].update(evidence_class="anecdote"), "unknown architecture evidence class"),
            (lambda e: e["rows"][0]["closure"].pop("c5"), "architecture closure needs c1..c5"),
            (lambda e: e["rows"][0].update(verdict="closed"),
             "a closed architecture verdict requires all five closure items met"),
            (lambda e: e["rows"][0]["closure"].update(missing=" "), "an open architecture row must name what is missing"),
            (lambda e: e["rows"][0].update(verdict="no_selection"),
             "a no_selection architecture row carries no winners, and every other row has one"),
            (lambda e: winner(e).update(name="search"), "architecture winner needs exactly one of component_id or name"),
            (lambda e: winner(e).update(component_id="unlisted"),
             "architecture winner component_id must be a manifests/stack.json component"),
            (lambda e: winner(e).update(role=" "),
             "architecture winner role must be non-empty text of at most 120 characters"),
            (lambda e: winner(e).update(role="r" * 121),
             "architecture winner role must be non-empty text of at most 120 characters"),
            (lambda e: (winner(e).pop("component_id"), winner(e).update(name="ripgrep", pin=" ")),
             "architecture winner needs its name and pin"),
            (lambda e: winner(e).update(repository="http://github.com/example/search"),
             "architecture winner repository must be a public HTTPS URL"),
            (lambda e: winner(e).update(pin_source="manifests/absent.json:1"),
             "architecture winner pin_source must be a repository file with an optional line range"),
            (lambda e: winner(e).update(pin_source="manifests/stack.json:2"),
             "architecture winner pin_source line range must fall inside the file"),
            (lambda e: winner(e)["install"].update(kind="curl"),
             "architecture install needs a known kind and a command unless none is recorded"),
            (lambda e: winner(e)["acceptance"].update(command=""),
             "architecture acceptance needs its evidence class and a command unless none is recorded"),
            (lambda e: winner(e)["upstream_currency"].pop("checked_at"),
             "architecture upstream currency needs latest_release, checked_at and pin_is_latest"),
            (lambda e: winner(e)["upstream_currency"].update(url="javascript:alert(document.domain)"),
             "architecture upstream currency url must be a public HTTPS URL"),
            (lambda e: winner(e)["install"].pop("source_path"),
             "architecture search install needs exactly one of source_path, pending_source or url"),
            (lambda e: reason(e).update(url="https://github.com/example/search"),
             "architecture reason needs exactly one of source_path, pending_source or url"),
            (lambda e: reason(e).update(source_path="docs/absent.md"),
             "architecture reason source_path must be a repository file"),
            (lambda e: (reason(e).pop("source_path"), reason(e).update(
                pending_source={"path": "docs/pending-recipe.md", "pull_request": "569"})),
             "architecture reason pending_source needs a path, a pull request number and an optional commit"),
            (lambda e: (reason(e).pop("source_path"), reason(e).update(url="https://127.0.0.1/record")),
             "architecture reason url must be a public HTTPS URL"),
            (lambda e: reason(e).update(source_path="manifests/evidence.json"),
             "architecture citations cannot use the generated page or the evidence manifest"),
            (lambda e: e["rows"][0].update(reasons=[]), "architecture row needs reasons with their text"),
            (lambda e: e["rows"][0].update(alternatives=[{"name": "Other client"}]),
             "architecture alternatives need their name and verdict"),
            (lambda e: e["rows"][0].update(new_host_steps=[]), "architecture row needs ordered new-host steps"),
            (lambda e: e["rows"][0]["gates"][0].update(kind="defect"),
             "architecture gates need their text and a known kind (user_side, upstream or lane)"),
            (lambda e: e["rows"].append(e["rows"][0]), "architecture layer_id must be unique"),
            # The reverse direction of each "if and only if" rule.
            (lambda e: e["rows"][0]["closure"].update(c2="met", c3="met", c4="met", c5="met", missing=""),
             "a closed architecture verdict requires all five closure items met"),
            (lambda e: e["rows"][0].update(winners=[]),
             "a no_selection architecture row carries no winners, and every other row has one"),
            (lambda e: e["rows"][0].update(verdict="closed", closure={
                **{item: "met" for item in ("c1", "c2", "c3", "c4", "c5")}, "missing": "c1: nothing"}),
             "an open architecture row must name what is missing, and a closed row nothing"),
            # recipes/search.md has five lines, so :5-3 fails on its order, not on the file's bounds.
            (lambda e: winner(e).update(pin_source="recipes/search.md:5-3"),
             "architecture winner pin_source line range must fall inside the file"),
            (lambda e: e["rows"][2].update(catalog="foundation"), "architecture row catalog must match its layer"),
            (lambda e: winner(e)["install"].update(kind="none_recorded"),
             "architecture install needs a known kind and a command unless none is recorded"),
            # A path escape at each architecture call site.
            (lambda e: reason(e).update(source_path="../outside.md"),
             "source path must be canonical and confined to the repository"),
            (lambda e: winner(e).update(pin_source="../manifests/stack.json:1"),
             "source path must be canonical and confined to the repository"),
            (lambda e: (reason(e).pop("source_path"), reason(e).update(
                pending_source={"path": "../pending-recipe.md", "pull_request": 569})),
             "source path must be canonical and confined to the repository"),
        )
        for mutate, message in cases:
            with self.subTest(message=message):
                edition = self.architecture_edition()
                mutate(edition)
                self.write_architecture(edition)
                result = self.run_generator("--check")
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn(message, result.stdout)
        with self.subTest(message="close_only_when"):
            self.write_architecture(self.architecture_edition(), close_only_when=self.CLOSE_ONLY_WHEN[:4])
            result = self.run_generator("--check")
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn("architecture closure items must be the five close_only_when items of the research state",
                          result.stdout)

    def test_architecture_closure_texts_are_bound_by_their_hash(self):
        """The edition records the sha256 of the five close_only_when texts it was written against, so a reworded or
        reordered research state fails the build instead of showing each row's states beside other texts."""
        message = ("architecture edition close_only_when_sha256 must be the sha256 of the research state's five "
                   "close_only_when texts")
        self.write_architecture(self.architecture_edition())
        result = self.run_generator("--check")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        texts = self.CLOSE_ONLY_WHEN
        for name, changed in (("reworded", [texts[0] + ", reworded", *texts[1:]]),
                              ("reordered", [texts[1], texts[0], *texts[2:]])):
            with self.subTest(case=name):
                self.write_architecture(self.architecture_edition(), close_only_when=changed)
                result = self.run_generator("--check")
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn(message, result.stdout)

    def assert_architecture_cases(self, cases):
        """Each case mutates a fresh fixture edition; None expects a passing --check, a string that failure."""
        for name, mutate, message in cases:
            with self.subTest(case=name):
                edition = self.architecture_edition()
                mutate(edition)
                self.write_architecture(edition)
                result = self.run_generator("--check")
                if message is None:
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                else:
                    self.assertNotEqual(result.returncode, 0, result.stdout)
                    self.assertIn(message, result.stdout)

    def test_a_none_recorded_acceptance_may_name_the_check_to_run(self):
        """A check that is prescribed but has no recorded run keeps its command; every other class needs one."""
        def prescribed(edition):
            edition["rows"][0]["winners"][0]["acceptance"].update(command="rg --version", evidence_class="none_recorded")
            edition["rows"][0]["evidence_class"] = "none_recorded"
        self.assert_architecture_cases((
            ("a prescribed check without a recorded run", prescribed, None),
            ("a recorded class without a command",
             lambda e: e["rows"][0]["winners"][0]["acceptance"].update(command=" "),
             "architecture acceptance needs its evidence class and a command unless none is recorded")))

    def recorded_winner(self, evidence_class):
        """A second, name-keyed winner whose acceptance carries the given class."""
        winner = self.architecture_winner(name="ripgrep", pin="14.1.1", acceptance={
            "command": "" if evidence_class == "none_recorded" else "rg --version",
            "evidence_class": evidence_class, "source_path": self.ARCHITECTURE_SOURCE})
        winner.pop("component_id")
        return winner

    def test_architecture_pin_drift_passes_and_is_listed(self):
        """A dated edition keeps the pin it recorded: a later stack move passes the build, the winner carries the
        stack's version and --check lists it; a component_id outside the stack still fails (rejects test)."""
        self.write_architecture(self.architecture_edition())
        self.assertEqual(self.check_report()["architecture_pin_drift"], [])
        self.stack["components"][0]["version"] = "1.1"
        self.save()
        self.assertEqual(self.check_report()["architecture_pin_drift"], [
            {"row": "foundation/native-clients", "component_id": "search", "edition_pin": "1.0", "stack_pin": "1.1"},
            {"row": "cross/cross:credential-practice", "component_id": "search", "edition_pin": "1.0",
             "stack_pin": "1.1"}])
        page, _ = self.build()
        winner = json.loads(page.data)["architecture"]["rows"][0]["winners"][0]
        self.assertEqual((winner["pin"], winner["pin_drift"]), ("1.0", "1.1"))

    def test_architecture_layer_identity_is_the_catalog_and_layer_id_pair(self):
        """The two catalogs may share a layer id; each (catalog, layer id) pair is its own layer."""
        shared = ("native-clients", "backtesting-engine")
        edition = self.architecture_edition()
        edition["rows"].append(self.architecture_row("backtesting-engine", "foundation"))
        self.write_architecture(edition, foundation_layers=shared)
        page, _ = self.build()
        architecture = json.loads(page.data)["architecture"]
        identities = [(row["catalog"], row["layer_id"], row["research_status"]) for row in architecture["rows"]]
        self.assertEqual(identities[1::2], [("us-equities", "backtesting-engine", "comparison_required"),
                                            ("foundation", "backtesting-engine", None)])
        self.assertEqual(architecture["missing_layers"], ["us-equities/execution-broker"])
        # The us-equities row does not cover the foundation layer of the same id.
        self.write_architecture(self.architecture_edition(), foundation_layers=shared)
        page, _ = self.build()
        self.assertEqual(json.loads(page.data)["architecture"]["missing_layers"],
                         ["foundation/backtesting-engine", "us-equities/execution-broker"])

    @unittest.skipUnless(shutil.which("node"), "Generated page script execution needs Node")
    def test_the_generated_page_renders_architecture_roles_pin_drift_and_landed_sources(self):
        self.use_real_template()
        edition = self.architecture_edition()
        edition["rows"][0]["winners"][0]["role"] = "selected destination engine"
        self.write_architecture(edition)
        self.write("docs/pending-recipe.md", "# Landed recipe\n")
        self.stack["components"][0]["version"] = "1.1"
        self.save()
        _, text = self.build()
        observed = self.run_page(text, tab="architecture")
        self.assertEqual((observed["errors"], observed["missing"]), ([], []))
        drift = "Pin drift: the stack now records 1.1; this edition recorded 1.0."
        for expected in ("search ↗ · selected destination engine1.0" + drift,
                         "search · selected destination engine · 1.0Pin of record: manifests/stack.json:1 ↗" + drift,
                         "Recipe lands with its pull request (docs/pending-recipe.md · landed after this edition's base "
                         "(pull request #569)) ↗"):
            with self.subTest(expected=expected[:60]):
                self.assertIn(expected, observed["architecture"])

    def test_architecture_row_class_is_the_floor_its_winners_reach(self):
        """No order is defined among the six policy classes, so the build enforces what it can: a row with a
        none_recorded winner is none_recorded, and otherwise its class is one that a winner's acceptance carries."""
        floor = "architecture row evidence class must be none_recorded when any winner's acceptance is none_recorded"
        carried = "architecture row evidence class must be one that at least one winner's acceptance carries"

        def with_second(evidence_class, row_class):
            def mutate(edition):
                edition["rows"][0]["winners"].append(self.recorded_winner(evidence_class))
                edition["rows"][0]["evidence_class"] = row_class
            return mutate
        self.assert_architecture_cases((
            ("a none_recorded winner under a recorded row class", with_second("none_recorded", "upstream_test"), floor),
            ("a row class no winner carries", lambda e: e["rows"][0].update(evidence_class="local_integration_check"),
             carried),
            ("a none_recorded winner under a none_recorded row", with_second("none_recorded", "none_recorded"), None),
            ("a row class one of two winners carries",
             with_second("local_integration_check", "local_integration_check"), None),
            ("a row without winners keeps its owner's class",
             lambda e: e["rows"][1].update(evidence_class="local_integration_check"), None)))

    def test_architecture_missing_names_exactly_the_open_items(self):
        """`missing` is one "cN: ..." segment per item that is not met (segments separated by "; cN:"), none for a
        met item; a trailing sentence without a cN: prefix belongs to the last segment."""
        message = "architecture closure missing must name each item that is not met in its own cN: segment"

        def missing(text):
            return lambda edition: edition["rows"][0]["closure"].update(missing=text)
        named = "c2: candidate set not frozen; c3: no new-distro run; c4: no second review; c5: no closure record"
        self.assert_architecture_cases((
            ("open items without a segment", missing("c2: candidate set not frozen"), message),
            ("free text only", missing("TBD"), message),
            ("free text before the segments", missing("TBD; " + named), message),
            ("a met item with a segment", missing("c1: already met; " + named), message),
            ("an open item named twice", missing(named + "; c5: and again"), message),
            ("a trailing sentence without a prefix", missing(named + "; the owner re-reads this row next edition."),
             None)))

    @unittest.skipUnless(shutil.which("node"), "Generated page script execution needs Node")
    def test_the_generated_page_script_renders_the_architecture_tab(self):
        self.use_real_template()
        _, without = self.build()
        observed = self.run_page(without, tab="architecture")
        self.assertEqual((observed["errors"], observed["missing"]), ([], []))
        # No edition: the tab stays hidden and #architecture falls back to the overview.
        self.assertEqual((observed["architecture_tab_hidden"], observed["architecture_panel_hidden"]), (True, True))
        self.assertEqual(observed["architecture"], "")

        edition = self.architecture_edition()
        self.write_architecture(edition)
        _, with_edition = self.build()
        observed = self.run_page(with_edition, tab="architecture")
        self.assertEqual((observed["errors"], observed["missing"]), ([], []))
        self.assertEqual((observed["app_hidden"], observed["recovery_hidden"]), (False, True))
        self.assertEqual((observed["architecture_tab_hidden"], observed["architecture_panel_hidden"]), (False, False))
        head, table = observed["architecture_edition"], observed["architecture"]
        for expected in ("Edition 2026-10-01 · base commit " + "c" * 40, "Fixture edition",
                         "Closed: 0 of 3 rows. No layer is closed in this edition: none meets all five closure items",
                         "Verdicts: no selection 1 · selection of record open 2",
                         "Catalog layers without a row in this edition: us-equities/execution-broker",
                         "Verdict rulesA layer is closed only when all five close_only_when items hold.",
                         "c5Dated closure record", "selection of record openMeaning of selection_of_record_open"):
            with self.subTest(expected=expected[:60]):
                self.assertIn(expected, head)
        for expected in ("Foundation layers", "US-equities layers", "Cross-cutting rows",
                         "LayerSource host's selection (pin)VerdictEvidence classReasonsInstall on the new distro",
                         "Title native-clientsfoundation/native-clientsResearch state: on requirement change",
                         "search ↗1.0", "Meaning of selection_of_record_openLabel of upstream_test",
                         "Recorded verdict winner (" + self.ARCHITECTURE_SOURCE + ") ↗",
                         "Recipe lands with its pull request (docs/pending-recipe.md · pull request #569 at eabe7654, "
                         "not on main at this edition's base) ↗",
                         "search · repo recipesearch install", "No selection of record",
                         "c2 · partialFrozen candidate set", "Missing: c2: candidate set not frozen; c3: no new-distro run",
                         "Pin of record: manifests/stack.json:1 ↗", "Acceptance (Label of upstream_test)search --self-test",
                         "Upstream: v1.1 (2026-09-30) · pin is latest: no · checked 2026-10-01T05:00Z ↗",
                         "Other client · refuted on fit · " + self.ARCHITECTURE_SOURCE + " ↗",
                         "Install the pinned clientSign in natively",
                         "user side gate: Native sign-in on the new distro", "upstream gate: Upstream fix pending",
                         "Gate source: https://github.com/example/search/issues/7 ↗",
                         "Missing: c1: assessment pending; c2: assessment pending", "Owner lane: foundation"):
            with self.subTest(expected=expected[:60]):
                self.assertIn(expected, table)

        # One row meeting all five items, closed: the count comes from the data and the "none" sentence goes away.
        edition["rows"][0].update(verdict="closed", closure={**{item: "met" for item in ("c1", "c2", "c3", "c4", "c5")},
                                                              "missing": ""})
        self.write_architecture(edition)
        _, with_closed = self.build()
        observed = self.run_page(with_closed, tab="architecture")
        self.assertEqual((observed["errors"], observed["missing"]), ([], []))
        self.assertIn("Closed: 1 of 3 rows.", observed["architecture_edition"])
        self.assertNotIn("No layer is closed", observed["architecture_edition"])
        self.assertIn("Nothing missing: all five closure items hold.", observed["architecture"])

    @unittest.skipUnless(shutil.which("git"), "Tracked-file check needs git")
    def test_the_repository_architecture_edition_validates_and_cites_tracked_files(self):
        """The real edition, not the fixture: the generator's own validation passes and every file the edition
        cites (and the generator hashes) is tracked by git in this checkout. A catalog layer without a row is
        listed on the page, not a failure, so this test does not require every layer to have a row."""
        sys.path.insert(0, str(ROOT / "scripts"))
        try:
            import build_ecosystem
            from catalog_decisions import load
        finally:
            sys.path.remove(str(ROOT / "scripts"))
        hashed = set()

        def read(path):
            hashed.add(path)
            return load(ROOT, path)
        architecture = build_ecosystem.build_architecture(
            ROOT, "https://github.com/example/public-stack", read(build_ecosystem.STACK), read, hashed.add,
            lambda path: "https://github.com/example/public-stack/blob/main/" + path, set())
        self.assertIsNotNone(architecture)
        tracked = set(subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z"], capture_output=True,
                                     check=True).stdout.decode().split("\0"))
        self.assertGreater(len(hashed), 3)
        self.assertEqual(sorted(hashed - tracked), [])

    def repository_page_data(self):
        """Observe the real repository through the explorer's native render command."""
        target = self.root / "repository-explorer.html"
        result = subprocess.run(
            [sys.executable, str(GENERATOR), "--root", str(ROOT), "--render-to", str(target)],
            capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(Page(target.read_text(encoding="utf-8")).data)

    def test_repository_architecture_links_cite_the_owners_current_pin_fields(self):
        """A drifted edition still links the owner's current version, or the model revision."""
        data = self.repository_page_data()
        stack = json.loads((ROOT / "manifests/stack.json").read_text(encoding="utf-8"))
        components = {row["id"]: row for row in stack["components"]}
        models = {row["id"]: row for row in stack["models"]}
        lines = (ROOT / "manifests/stack.json").read_text(encoding="utf-8").splitlines()
        checked = set()
        errors = []
        for row in data["architecture"]["rows"]:
            for winner in row["winners"]:
                source = winner["pin_source"]
                match = re.fullmatch(r"manifests/stack.json:([1-9][0-9]*)", source["locator"])
                if match is None:
                    continue
                checked.add(source["locator"])
                index = int(match[1]) - 1
                identifier = winner["component_id"]
                if identifier is None:
                    identifier = winner["repository"].removeprefix("https://huggingface.co/")
                    field, expected = "revision", models[identifier]["revision"]
                else:
                    field, expected = "version", components[identifier]["version"]
                owner_line = next(line for line in reversed(lines[:index])
                                  if re.match(r'\s{6}"id":', line))
                owner = json.loads("{" + owner_line.strip().rstrip(",") + "}")["id"]
                expected_line = f'"{field}": {json.dumps(expected)},'
                if owner != identifier or lines[index].strip() != expected_line:
                    errors.append(f"{identifier}: {source['locator']} cites {lines[index].strip()}")
                self.assertTrue(source["url"].endswith(f"/manifests/stack.json#L{index + 1}"))
        self.assertTrue(checked)
        self.assertEqual(sorted(set(errors)), [])

    def test_repository_collector_statuses_name_their_historical_pin(self):
        """The current-pin card attributes September observations to deployed 0.161.0."""
        data = self.repository_page_data()
        row = next(item for item in data["efficiency"]["topic"]["rows"]
                   if item["component_id"] == "opentelemetry-collector-contrib")
        stack = json.loads((ROOT / "manifests/stack.json").read_text(encoding="utf-8"))
        selected = next(item["version"] for item in stack["components"]
                        if item["id"] == row["component_id"])
        self.assertEqual(row["version"], selected)
        for field, historical_fact in (("returned_result_summary", "2026-09-20"),
                                       ("lifecycle_summary", "install: observed_installed")):
            with self.subTest(field=field):
                text = row[field]
                self.assertIn("0.161.0", text)
                self.assertLess(text.index("0.161.0"), text.index(historical_fact))
                self.assertIn("historical", text[:text.index(historical_fact)].lower())
                self.assertIn("host acceptance pending", text)

    def test_the_repository_architecture_record_keeps_the_acceptance_invariant(self):
        """The record states the rule every winner's acceptance class follows and the dated review that corrected
        the edition. The build cannot read prose, so this test keeps a later edit from dropping either silently."""
        record = (ROOT / "docs/decisions/2026-10-01-new-wsl-architecture-edition.md").read_text(encoding="utf-8")
        record = " ".join(record.split())
        for sentence in (
                "A winner's acceptance class describes a run that the cited source, or one file that source links, "
                "shows was run on a host and what it returned.",
                "A check that is only prescribed, planned, not run or failed is `none_recorded`.",
                "A version print is metadata, not an acceptance.",
                "An independent review on 2026-10-01 found 32 of the 119 winner acceptance classes overstated, 13 "
                "commands that were only version or status prints and 6 entries it could not settle"):
            with self.subTest(sentence=sentence[:50]):
                self.assertIn(sentence, record)


if __name__ == "__main__":
    unittest.main()
