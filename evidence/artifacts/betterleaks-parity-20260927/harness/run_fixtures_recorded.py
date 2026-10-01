#!/usr/bin/env python3
"""Diagnostic re-run of the unchanged GitleaksConfigContextRestrictionTests (local integration helper,
scratch only). Wraps the module's own _run_gitleaks to record (RuleID, File, StartLine) per test and
returns its result unchanged; never records Match/Secret. Output: fixtures-<label>-findings.json."""
import json
import os
import sys
import unittest
from pathlib import Path

root, label, out_dir = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
sys.path.insert(0, str(root))
os.chdir(root)
import tests.test_gitleaks_config as mod  # noqa: E402

current = {"id": None}
record = {}
original = mod._run_gitleaks


def recording(target_dir):
    result = original(target_dir)
    rows = record.setdefault(current["id"], [])
    rows.append({"report": "null" if result is None else "list",
                 "findings": sorted([f["RuleID"], f["File"], f["StartLine"]] for f in (result or []))})
    return result


mod._run_gitleaks = recording


class Track(unittest.TestResult):
    def startTest(self, test):
        current["id"] = test.id().replace("tests.test_gitleaks_config.", "")
        super().startTest(test)


suite = unittest.defaultTestLoader.loadTestsFromName("tests.test_gitleaks_config.GitleaksConfigContextRestrictionTests")
result = Track()
suite.run(result)
(out_dir / f"fixtures-{label}-findings.json").write_text(json.dumps(record, indent=1, sort_keys=True))
print(label, "tests_run", result.testsRun, "recorded_tests", len(record))
