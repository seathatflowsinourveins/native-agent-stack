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


if __name__ == "__main__":
    unittest.main()
