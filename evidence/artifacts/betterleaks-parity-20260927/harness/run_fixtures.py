#!/usr/bin/env python3
"""Run unchanged tests/test_gitleaks_config.py classes with whichever `gitleaks` is first on PATH
(local integration helper, scratch only). Prints only test ids and outcome classes; tracebacks and
assertion messages (which can quote report Match/Secret fields) go to a 0600 scratch file."""
import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

root, label, out_dir = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
names = sys.argv[4:]
sys.path.insert(0, str(root))
os.chdir(root)
binary = shutil.which("gitleaks")
version = subprocess.run([binary, "version"], capture_output=True, text=True).stdout.strip() if binary else None


class Collect(unittest.TestResult):
    def __init__(self):
        super().__init__()
        self.rows = []

    def addSuccess(self, test):
        self.rows.append((test.id(), "ok", ""))

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.rows.append((test.id(), "FAIL", err[0].__name__))

    def addError(self, test, err):
        super().addError(test, err)
        self.rows.append((test.id(), "ERROR", err[0].__name__))

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        # A skip reason can quote scanner stderr; record only whether it is the lock skip.
        self.rows.append((test.id(), "skipped", "lock-skip" if "lock" in reason.lower() else "other-skip"))


suite = unittest.defaultTestLoader.loadTestsFromNames(names)
result = Collect()
suite.run(result)
private = out_dir / f"fixtures-{label}.tracebacks.txt"
private.write_text("\n\n".join(f"{t.id()}\n{tb}" for t, tb in result.failures + result.errors))
private.chmod(0o600)
summary = {"label": label, "gitleaks_on_path_version": version, "tests_run": result.testsRun,
           "counts": {k: sum(1 for r in result.rows if r[1] == k) for k in ("ok", "FAIL", "ERROR", "skipped")},
           "rows": [{"id": r[0].replace("tests.test_gitleaks_config.", ""), "outcome": r[1], "detail": r[2]} for r in result.rows]}
(out_dir / f"fixtures-{label}.json").write_text(json.dumps(summary, indent=1))
print(json.dumps({k: summary[k] for k in ("label", "gitleaks_on_path_version", "tests_run", "counts")}))
for r in summary["rows"]:
    if r["outcome"] != "ok":
        print("  ", r["outcome"], r["id"], r["detail"])
