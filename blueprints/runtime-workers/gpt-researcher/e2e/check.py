"""Pre-grader transport sanity ONLY; no research-quality verdict.

DRB-II b38f360 run_evaluation.py:374-378,530-547 consumes unchanged UTF-8
Markdown at <report-root>/<arm>/idx-ID.md. Upstream supplies all rubric scores.
"""
import json
from pathlib import Path
import sys


def check(result):
    report = result.get("report") if isinstance(result, dict) else None
    errors = []
    if not isinstance(report, str):
        errors.append("invalid_report_type" if report is not None else "empty_report")
    elif not report.strip():
        errors.append("empty_report")
    else:
        try:
            report.encode("utf-8")
        except UnicodeEncodeError:
            errors.append("invalid_utf8")
    return {"ready_for_grading": not errors, "errors": errors,
            "scope": "report transport only; DeepResearch-Bench-II gives the quality scores"}


def export_report(result, destination):
    if not check(result)["ready_for_grading"]:
        raise ValueError("report cannot be exported for grading")
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation avoids mixing another attempt with an upstream append.
    with destination.open("xb") as output:
        output.write(result["report"].encode("utf-8"))


def main():
    try:
        result = json.loads(Path(sys.argv[1]).read_text())
        sanity = check(result)
    except (OSError, ValueError, IndexError):
        sanity = {"ready_for_grading": False, "errors": ["invalid_result"]}
    print(json.dumps(sanity, sort_keys=True))
    return 0 if sanity["ready_for_grading"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
