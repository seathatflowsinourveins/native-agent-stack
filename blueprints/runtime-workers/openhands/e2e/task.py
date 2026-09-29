"""Transport a frozen SWE-bench row to the standalone worker.

Sources: SWE-bench 4.1.0 harness/utils.py (local JSON/JSONL datasets);
OpenHands/benchmarks 405bae7 swebench/run_infer.py:61-88 and prompts/default.j2.
This is a bare-checkout SDK adaptation, not unchanged benchmark inference.
"""
import hashlib
import json
from pathlib import Path
import re


def load_task(path, expected_sha256):
    path = Path(path)
    raw = path.read_bytes()
    if (not re.fullmatch(r"[0-9a-f]{64}", expected_sha256)
            or hashlib.sha256(raw).hexdigest() != expected_sha256):
        raise ValueError("frozen_task_hash_mismatch")
    if path.suffix == ".jsonl":
        rows = [json.loads(line) for line in raw.decode().splitlines()]
    elif path.suffix == ".json":
        rows = json.loads(raw)
    else:
        raise ValueError("native_json_or_jsonl_dataset_required")
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
        raise ValueError("one_frozen_swebench_row_required")
    row = rows[0]
    for key in ("repo", "instance_id", "base_commit", "version", "problem_statement", "test_patch"):
        if not isinstance(row.get(key), str) or not row[key].strip():
            raise ValueError("missing_swebench_field")
    if (not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", row["repo"])
            or not re.fullmatch(r"[a-zA-Z0-9_-]+", row["instance_id"])
            or not re.fullmatch(r"[0-9a-f]{40}", row["base_commit"])):
        raise ValueError("invalid_swebench_identity")
    for key in ("FAIL_TO_PASS", "PASS_TO_PASS"):
        value = row.get(key)
        cases = json.loads(value) if isinstance(value, str) else value
        if not isinstance(cases, list) or any(not isinstance(case, str) for case in cases):
            raise ValueError("invalid_swebench_test_contract")
        if key == "FAIL_TO_PASS" and not cases:
            raise ValueError("empty_swebench_test_contract")
    return row


def worker_instruction(row):
    # Deliberately exclude patch, test_patch and test-name oracle fields. Name only skills the
    # SWE-bench contract installs (host.workspace_skills): the runtime manifest excludes
    # verification-before-completion, so the check before finishing names no skill.
    return (
        "Repair the repository at /workspace for the following issue.\n"
        f"Repository: {row['repo']}\nBase commit: {row['base_commit']}\n\n"
        + row["problem_statement"]
        + "\n\nInvoke the tdd skill using invoke_skill before editing. Before finishing, run "
        "the tests that reproduce the issue again and report what they returned. The existing code/test "
        "interfaces and test-first work are authorized. Inspect the repository's native "
        "test instructions; reproduce the issue and retain test results in the trace. "
        "This is a bare checkout, not the upstream Conda testbed. Do not claim an "
        "unavailable dependency or test passed. Keep changes scoped to the issue. "
        "Git metadata and installed skills are read-only; do not commit or alter them. "
        "The independent official SWE-bench grader will apply and test your patch."
    )
