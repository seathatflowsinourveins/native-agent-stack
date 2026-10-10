"""Execute the current workflows' accounting shell on synthetic failed exchanges.

The fixed class describes a result shape, not an Anthropic Console deny reason.
Existing workflow helpers isolate the environment; no model or authentication runs.
"""

import json
import hashlib
import shutil
import unittest
from pathlib import Path

from tests import test_claude_harness_audit_bounds as audit
from tests import test_claude_pr_review_workflow as review
from tests import test_claude_pr_toolkit_review_workflow as toolkit


ERROR_CLASS = "zero_cost_error_without_model_usage"
RAW_MARKER = "UNTRUSTED-PROVIDER-DIAGNOSTIC-MUST-NOT-BE-PUBLISHED"
WORKFLOWS = (review, toolkit, audit)
ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_INDEX = ROOT / "evidence/artifacts/claude-federation-docs-20261010/snapshots.json"


def failed_exchange(**changes):
    result = {"type": "result", "subtype": "error_during_execution", "is_error": True,
              "num_turns": 0, "total_cost_usd": 0, "modelUsage": {},
              "errors": [RAW_MARKER], "result": RAW_MARKER}
    result.update(changes)
    return [result]


@unittest.skipUnless(shutil.which("bash") and shutil.which("jq") and review.yaml,
                     "workflow execution requires bash, jq and PyYAML")
class FederationDiagnosticTests(unittest.TestCase):
    def test_failed_exchange_keeps_fixed_diagnosis_and_still_fails(self):
        # S2: native run37988961127; claude-code-action@2dca132f run-claude-sdk.ts:252-256.
        # A result with subtype success can still carry is_error true before any model usage.
        for module in WORKFLOWS:
            for shape in ({}, {"subtype": "success", "num_turns": 1}):
                with self.subTest(workflow=module.__name__, shape=shape):
                    code, console, summary, usage, *_ = module.run_step(
                        module.NUMBERS, execution_file=failed_exchange(**shape))
                    self.assertEqual(code, 1, console)
                    self.assertIsNotNone(usage, "accounting aborted before keeping the diagnosis")
                    record = json.loads(usage)
                    self.assertEqual(record["error_class"], ERROR_CLASS)
                    self.assertIn(ERROR_CLASS, summary)
                    self.assertIn(ERROR_CLASS, console)
                    self.assertFalse(record["successful_result"])
                    self.assertEqual(record["models"], [])
                    if module is toolkit:
                        self.assertFalse(record["complete"])
                        self.assertIsNone(record["total_cost_usd"])
                    else:
                        self.assertEqual(record["total_cost_usd"], 0)
                    for text in (console, summary, usage):
                        self.assertNotIn(RAW_MARKER, text)

    def test_an_error_before_a_later_success_is_not_hidden_in_toolkit_accounting(self):
        log = toolkit.execution()
        log.insert(1, failed_exchange()[0])
        code, console, summary, usage, *_ = toolkit.run_step(toolkit.NUMBERS, execution_file=log)
        self.assertEqual(code, 1, console)
        self.assertIsNotNone(usage)
        record = json.loads(usage)
        self.assertEqual(record["error_class"], ERROR_CLASS)
        self.assertFalse(record["complete"])
        self.assertIn(ERROR_CLASS, summary)
        self.assertNotIn(RAW_MARKER, console + summary + usage)

    def test_a_successful_cached_review_has_no_error_class(self):
        for module in WORKFLOWS:
            with self.subTest(workflow=module.__name__):
                code, console, summary, usage, *_ = module.run_step(
                    module.NUMBERS, execution_file=module.execution())
                self.assertEqual(code, 0, console)
                self.assertIsNone(json.loads(usage)["error_class"])
                self.assertNotIn(ERROR_CLASS, summary + console)

    def test_the_class_requires_all_three_result_fields(self):
        controls = ({"is_error": False}, {"is_error": "true"},
                    {"total_cost_usd": 0.01}, {"total_cost_usd": None},
                    {"modelUsage": None}, {"modelUsage": []})
        for module in WORKFLOWS:
            for changes in controls:
                with self.subTest(workflow=module.__name__, changes=changes):
                    log = failed_exchange()
                    log[0].update(changes)
                    code, console, summary, usage, *_ = module.run_step(
                        module.NUMBERS, execution_file=log)
                    self.assertNotEqual(code, 0)
                    self.assertNotIn(ERROR_CLASS, console + summary + (usage or ""))


class DocumentationSnapshotTests(unittest.TestCase):
    def test_cited_vendor_revisions_match_retained_bytes_and_registry(self):
        self.assertTrue(SNAPSHOT_INDEX.is_file(), "no retained vendor-document revision index")
        index = json.loads(SNAPSHOT_INDEX.read_text())
        manifest = json.loads((ROOT / "manifests/evidence.json").read_text())
        registered = {row["path"]: row for row in manifest["files"]}
        decision = (ROOT / "docs/decisions/2026-10-10-claude-federation-diagnostics.md").read_text()
        self.assertEqual(len(index["snapshots"]), 3)
        for row in index["snapshots"]:
            with self.subTest(snapshot=row["id"]):
                raw = (ROOT / row["path"]).read_bytes()
                digest = hashlib.sha256(raw).hexdigest()
                self.assertEqual(digest, row["sha256"])
                self.assertEqual(len(raw), row["bytes"])
                self.assertEqual(row["revision"], "sha256:" + digest)
                self.assertEqual(row["retrieved_on"], "2026-10-10")
                self.assertEqual(registered[row["path"]]["sha256"], digest)
                self.assertEqual(registered[row["path"]]["bytes"], len(raw))
                self.assertIn(row["revision"], decision)
                self.assertIn(str(row["bytes"]), decision)
                self.assertIn(Path(row["path"]).name, decision)
                lines = raw.decode().splitlines()
                for locator in row["locators"]:
                    self.assertIn(locator["contains"], lines[locator["line"] - 1])


if __name__ == "__main__":
    unittest.main()
