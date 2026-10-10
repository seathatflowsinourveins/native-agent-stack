"""Execute the current workflows' accounting shell on synthetic failed exchanges.

The fixed class describes a result shape, not an Anthropic Console deny reason.
Existing workflow helpers isolate the environment; no model or authentication runs.
"""

import json
import shutil
import unittest

from tests import test_claude_harness_audit_bounds as audit
from tests import test_claude_pr_review_workflow as review
from tests import test_claude_pr_toolkit_review_workflow as toolkit


ERROR_CLASS = "zero_cost_error_without_model_usage"
RAW_MARKER = "UNTRUSTED-PROVIDER-DIAGNOSTIC-MUST-NOT-BE-PUBLISHED"
WORKFLOWS = (review, toolkit, audit)


def failed_exchange():
    return [{"type": "result", "subtype": "error_during_execution", "is_error": True,
             "num_turns": 0, "total_cost_usd": 0, "modelUsage": {},
             "errors": [RAW_MARKER], "result": RAW_MARKER}]


@unittest.skipUnless(shutil.which("bash") and shutil.which("jq") and review.yaml,
                     "workflow execution requires bash, jq and PyYAML")
class FederationDiagnosticTests(unittest.TestCase):
    def test_failed_exchange_keeps_fixed_diagnosis_and_still_fails(self):
        for module in WORKFLOWS:
            with self.subTest(workflow=module.__name__):
                code, console, summary, usage, *_ = module.run_step(
                    module.NUMBERS, execution_file=failed_exchange())
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


if __name__ == "__main__":
    unittest.main()
