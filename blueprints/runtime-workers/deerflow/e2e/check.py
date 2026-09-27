"""Frozen, local integration oracle; not an upstream test.

Source contract: GitHub REST commits API's files/statistics fields, frozen in
expected.json before a run. Subprocess pattern: tests/test_install_skills.py.
Run untrusted worker scripts ONLY in the isolated checker container used by
run.py. The local unit suite supplies only author-controlled synthetic scripts.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


def run_script(script, data):
    result = subprocess.run([sys.executable, "-I", str(script), str(data)],
                            capture_output=True, text=True, timeout=10, check=False)
    if result.returncode != 0:
        raise ValueError("generated script failed")
    return json.loads(result.stdout)


def check(directory):
    directory = Path(directory)
    expected = json.loads(Path(__file__).with_name("expected.json").read_text())
    script = directory / "summarize.py"
    for name in ("summarize.py", "files.json", "report.json"):
        path = directory / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 1_000_000:
            raise ValueError("missing or invalid artifact")
    files = json.loads((directory / "files.json").read_text())
    if sorted(files, key=lambda x: x["filename"]) != expected["files"]:
        raise ValueError("API fields differ from frozen release commit")
    if json.loads((directory / "report.json").read_text()) != expected["summary"]:
        raise ValueError("saved report differs from frozen expected summary")
    if run_script(script, directory / "files.json") != expected["summary"]:
        raise ValueError("script output differs from frozen expected summary")
    # Independent literal controls ensure the script actually reads its input.
    fixtures = [([], {"file_count": 0, "additions": 0, "deletions": 0, "changes": 0,
                      "by_status": {}, "paths": []}),
                ([{"filename": "z.py", "status": "added", "additions": 2, "deletions": 0, "changes": 2},
                  {"filename": "a.md", "status": "modified", "additions": 3, "deletions": 1, "changes": 4}],
                 {"file_count": 2, "additions": 5, "deletions": 1, "changes": 6,
                  "by_status": {"added": 1, "modified": 1}, "paths": ["a.md", "z.py"]})]
    with tempfile.TemporaryDirectory() as tmp:
        fixture = Path(tmp) / "control.json"
        for data, oracle in fixtures:
            fixture.write_text(json.dumps(data))
            if run_script(script, fixture) != oracle:
                raise ValueError("script failed an independent input control")
    return {"passed": True, "checks": ["frozen_files", "saved_report", "executed_script", "independent_inputs"]}


if __name__ == "__main__":
    try:
        result = check(sys.argv[1])
    except (OSError, ValueError, KeyError, TypeError, IndexError, subprocess.TimeoutExpired) as exc:
        result = {"passed": False, "reason": type(exc).__name__}
    print(json.dumps(result, sort_keys=True))
    raise SystemExit(0 if result["passed"] else 1)
