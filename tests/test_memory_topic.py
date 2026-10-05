"""Publication contracts for the offline memory/RAG evidence export."""

import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts import build_ecosystem as builder
from tests import test_ecosystem_manifest as explorer_tests


ROOT = Path(__file__).resolve().parents[1]


class MemoryTopicTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.paths = ["evidence/selected.json", "docs/landscape-continuation.md"]
        self.inputs = []
        for path in self.paths + [builder.CONFIG, builder.STACK]:
            target = self.root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text('{"claim":"</script> & untrusted evidence"}\n', encoding="utf-8")
            raw = target.read_bytes()
            self.inputs.append({"path": path, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)})
        (self.root / "evidence/private-sibling.json").write_text("must not enter publication")
        self.full = {"repository_url": "https://github.com/example/stack", "source_revision": "a" * 40,
                     "memory_review": {"sources": [{"path": self.paths[0], "url": "https://example.com/source"}],
                                       "decision": {"final_candidate": None}}, "inputs": self.inputs,
                     "unrelated_catalog": {"private": "must not enter publication"}}

    def build(self):
        with patch.object(builder, "build_data", return_value=self.full):
            return builder.build_topic_data(self.root, "memory-rag")

    def test_export_has_exact_selected_evidence_without_sibling_catalogs(self):
        data = self.build()
        self.assertEqual({item["path"] for item in data["documents"]}, set(self.paths))
        self.assertNotIn("must not enter publication", json.dumps(data))
        self.assertIsNone(data["review"]["decision"]["final_candidate"])
        for item in data["documents"]:
            raw = (self.root / item["path"]).read_bytes()
            self.assertEqual(item["text"].encode(), raw)
            self.assertEqual(item["sha256"], hashlib.sha256(raw).hexdigest())
            self.assertEqual(item["bytes"], len(raw))

    def test_changed_evidence_is_rejected_instead_of_using_stale_hash(self):
        (self.root / self.paths[0]).write_text("changed after catalog validation")
        with self.assertRaisesRegex(ValueError, "source changed"):
            self.build()

    def test_source_symlink_cannot_pull_an_unselected_file_into_export(self):
        selected = self.root / self.paths[0]
        selected.unlink()
        selected.symlink_to(self.root / "evidence/private-sibling.json")
        with self.assertRaises(ValueError):
            self.build()

    def test_topic_evidence_cannot_escape_json_script_or_add_network_assets(self):
        data = self.build()
        for path in [builder.TEMPLATE, builder.TOPICS["memory-rag"][0]]:
            target = self.root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT / path).read_bytes())
        page = builder.render_from_data(data, self.root, "memory-rag").decode()
        self.assertNotIn("</script> & untrusted evidence", page)
        self.assertIn("\\u003c/script\\u003e", page)
        self.assertIn("connect-src 'none'", page)
        self.assertNotIn("@@SCRIPT_HASH@@", page)
        self.assertNotIn("@@STYLE@@", page)

    @unittest.skipUnless(shutil.which("node"), "Native DOM contract needs Node")
    def test_real_topic_renders_local_sources_and_candidate_filter(self):
        data = builder.build_topic_data(ROOT, "memory-rag")
        page = builder.render_from_data(data, ROOT, "memory-rag").decode()
        script = re.search(r"<script>(.*?)</script>", page, re.S).group(1)
        harness = explorer_tests.EcosystemManifestTests.PAGE_HARNESS.replace("ecosystem-data", "topic-data")
        harness = harness[:harness.index("const text = id =>")] + r'''
byId['candidate-filter'].value = 'hindsight';
byId['candidate-filter'].listeners.input.forEach(listener => listener());
process.stdout.write(JSON.stringify({errors, missing,
  recommendation: byId.recommendation.textContent,
  evidence_rows: byId['evidence-rows'].children.length,
  coding_rows: byId['coding-rows'].children.length,
  lane_rows: byId['lane-rows'].children.length,
  candidates: byId['candidate-cards'].children.length,
  visible_candidates: byId['candidate-cards'].children.filter(card => !card.hidden).length,
  harness_candidates: byId['harness-candidates'].children.length,
  harness_summary: byId['harness-summary'].textContent,
  stack_gap_rows: byId['stack-gap-rows'].children.length,
  stack_gap_peer: byId['stack-gap-peer'].textContent,
  sdk_gap_candidates: byId['sdk-gap-candidates'].children.length,
  records: byId['record-list'].children.length}));
'''
        result = subprocess.run(["node", "-e", harness], input=json.dumps({
            "script": script, "data": json.dumps(data),
            "elements": explorer_tests.EcosystemManifestTests.page_elements(page), "tab": "decision"}),
            capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        observed = json.loads(result.stdout)
        self.assertEqual(observed["errors"], [])
        self.assertEqual(observed["missing"], [])
        self.assertEqual(observed["recommendation"], data["review"]["decision"]["recommended_target"])
        self.assertEqual(observed["evidence_rows"], len(data["review"]["assurance"]["rows"]))
        self.assertEqual(observed["coding_rows"], 3)
        self.assertEqual(observed["lane_rows"], 32)
        self.assertEqual(observed["candidates"], len(data["review"]["candidates"]))
        self.assertGreater(observed["visible_candidates"], 0)
        self.assertLess(observed["visible_candidates"], observed["candidates"])
        self.assertEqual(observed["records"], len(data["documents"]))
        native_path = data["review"]["resolution"]["native_harness_resolution_record"]
        native = json.loads(next(doc["text"] for doc in data["documents"] if doc["path"] == native_path))
        self.assertEqual(observed["harness_candidates"], len(native["candidates"]))
        self.assertIn("429", observed["harness_summary"])
        gap_path = data["review"]["resolution"]["native_stack_gap_record"]
        gaps = json.loads(next(doc["text"] for doc in data["documents"] if doc["path"] == gap_path))
        self.assertEqual(observed["stack_gap_rows"], len(gaps["rows"]))
        self.assertIn(gaps["peer_coordination"]["status"], observed["stack_gap_peer"])
        self.assertIn("sends: 0", observed["stack_gap_peer"])
        self.assertEqual(observed["sdk_gap_candidates"], len(gaps["conditional_sdks"]))


if __name__ == "__main__":
    unittest.main()
