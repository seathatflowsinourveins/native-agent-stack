"""Thin transport validation/relay; never run tests or decide patch correctness.

Input: OpenHands/benchmarks 405bae7 benchmarks/swebench/eval_infer.py:35-105.
Verdict: swebench==4.1.0 swebench/harness/reporting.py:127-142 (schema 2).
The official Docker grader alone produces resolved_ids. A successful process,
empty report or absent task is not a resolved task. See README for source pins.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_json_key")
        result[key] = value
    return result


def read_json(path):
    return json.loads(Path(path).read_text(), object_pairs_hook=unique_object)


def check_input(path, instance_id):
    rows = [json.loads(line, object_pairs_hook=unique_object)
            for line in Path(path).read_text().splitlines() if line.strip()]
    if len(rows) != 1 or not isinstance(rows[0], dict):
        raise ValueError("exactly_one_prediction_required")
    row = rows[0]
    result = row.get("test_result")
    if (row.get("instance_id") != instance_id or not isinstance(result, dict)
            or not isinstance(result.get("git_patch"), str) or row.get("error") is not None):
        raise ValueError("malformed_prediction")
    # Empty/wrong patches remain submissions for the upstream grader to fail.
    return {"ready_to_grade": True, "instance_id": instance_id,
            "evidence_class": "transport sanity only"}


def read_report(path, instance_id):
    data = read_json(path)
    fields = ("submitted_ids", "resolved_ids", "unresolved_ids", "error_ids",
              "empty_patch_ids", "incomplete_ids")
    if not isinstance(data, dict) or data.get("schema_version") != 2:
        raise ValueError("malformed_upstream_report")
    for key in fields:
        values = data.get(key)
        if (not isinstance(values, list) or any(not isinstance(v, str) for v in values)
                or len(set(values)) != len(values)):
            raise ValueError("malformed_upstream_report")
    if data["submitted_ids"] != [instance_id]:
        raise ValueError("submission_scope_mismatch")
    buckets = [key for key in fields[1:] if instance_id in data[key]]
    if len(buckets) != 1:
        raise ValueError("missing_or_conflicting_upstream_outcome")
    return {"verdict_source": "swebench==4.1.0", "instance_id": instance_id,
            "upstream_resolved": buckets == ["resolved_ids"], "upstream_bucket": buckets[0],
            "report_sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--input", type=Path)
    mode.add_argument("--report", type=Path)
    parser.add_argument("--instance-id", required=True)
    args = parser.parse_args()
    try:
        result = (check_input(args.input, args.instance_id) if args.input
                  else read_report(args.report, args.instance_id))
    except (OSError, ValueError, TypeError):
        print(json.dumps({"transport_error": "missing_or_malformed_output", "upstream_resolved": None}))
        return 2
    print(json.dumps(result))
    if result.get("upstream_bucket") in {"error_ids", "incomplete_ids"}:
        return 3
    return 0 if args.input or result["upstream_resolved"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
