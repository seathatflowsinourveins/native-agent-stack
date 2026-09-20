#!/usr/bin/env python3
"""Check declared convergence evidence offline; never execute or certify it."""

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re

if __package__:
    from .validate import Validator, _json_without_duplicates
else:
    from validate import Validator, _json_without_duplicates

REPO = Path(__file__).resolve().parents[1]
CONTRACT = REPO / "blueprints/convergence-practice"
EXECUTION = {"offline_artifact_check", "native_cli_execution", "model_task_execution", "recovery_execution"}
INPUT_OUTPUT = ("uncached_input", "cache_creation", "cache_read", "output")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_json_without_duplicates)


def structure(value, schema, definitions, label, errors):
    """Implement only the schema vocabulary used by the checked-in contract."""
    if "$ref" in schema:
        schema = definitions[schema["$ref"].removeprefix("#/$defs/")]
    types = schema.get("type", [])
    types = [types] if isinstance(types, str) else types
    kind = {dict: "object", list: "array", str: "string", int: "integer", bool: "boolean", type(None): "null"}.get(type(value))
    if kind not in types:
        errors.append(f"{label}: invalid type")
        return
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{label}: unsupported value")
    if kind == "object":
        properties = schema.get("properties", {})
        if set(schema.get("required", [])) - value.keys():
            errors.append(f"{label}: missing required fields")
        if schema.get("additionalProperties") is False and value.keys() - properties.keys():
            errors.append(f"{label}: unknown fields")
        for key in sorted(properties.keys() & value.keys()):
            structure(value[key], properties[key], definitions, f"{label}.{key}", errors)
    elif kind == "array":
        if len(value) < schema.get("minItems", 0):
            errors.append(f"{label}: too few items")
        if schema.get("uniqueItems") and len({json.dumps(item, sort_keys=True) for item in value}) != len(value):
            errors.append(f"{label}: duplicate items")
        for index, item in enumerate(value):
            structure(item, schema["items"], definitions, f"{label}[{index}]", errors)
    elif kind == "string":
        if len(value) < schema.get("minLength", 0) or ("pattern" in schema and re.fullmatch(schema["pattern"], value) is None):
            errors.append(f"{label}: invalid text format")
    elif kind == "integer" and "minimum" in schema and value < schema["minimum"]:
        errors.append(f"{label}: below minimum")


def check_artifacts(value, validator, label="record"):
    if isinstance(value, dict):
        if set(value) == {"path", "sha256"}:
            path = validator.path(value["path"], label)
            if path is not None:
                try:
                    with path.open("rb") as handle:
                        actual = hashlib.file_digest(handle, "sha256").hexdigest()
                    if actual != value["sha256"]:
                        validator.error(f"{label}: SHA-256 mismatch")
                except OSError:
                    validator.error(f"{label}: artifact unreadable")
        else:
            for key, item in value.items():
                check_artifacts(item, validator, f"{label}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            check_artifacts(item, validator, f"{label}[{index}]")


def accepted(run):
    return (run["status"] == "passed" and run["exit_code"] == 0
            and all(value is True for value in run["quality"].values()))


def consistency(record, validator):
    error = validator.error
    protocol = read_json(CONTRACT / "protocol.json")
    if not set(protocol["required_experiment_fields"]) <= record.keys():
        error("record: missing protocol evidence fields")
    if record["lane"] not in {lane["id"] for lane in protocol["lanes"]}:
        error("record: unsupported protocol lane")
    decision = record["decision_and_scope"]
    if decision["decision"] not in protocol["adoption_decisions"]:
        error("record: unsupported protocol decision")
    runs, assessment = record["observations"], record["usage_assessment"]
    by_id = {run["id"]: run for run in runs}
    if len(by_id) != len(runs):
        error("observations: duplicate run ID")
    failures = [item["run_id"] for item in record["failures_and_skips"]]
    if len(set(failures)) != len(failures) or set(failures) != {run["id"] for run in runs if run["status"] != "passed"}:
        error("failures_and_skips: must cover every non-passed run exactly once")
    if record["status"] == "planned":
        if runs or failures or decision["qualification_run_ids"] or assessment != {
                "claim": "none", "coverage": "partial", "expected_run_ids": [], "coverage_artifact": None}:
            error("planned record: observations, qualifications or usage assertions forbidden")
    elif not runs:
        error("observed record: at least one run required")
    if record["baseline_and_candidate"]["baseline"] == record["baseline_and_candidate"]["candidate"]:
        error("baseline_and_candidate: distinct conditions required")
    attempts = defaultdict(list)
    for index, run in enumerate(runs):
        label = f"observations[{index}]"
        if run["task"] not in record["frozen_inputs"]["tasks"] or run["role"] not in record["frozen_inputs"]["roles"]:
            error(f"{label}: undeclared task or role")
        if run["command_index"] >= len(record["commands"]):
            error(f"{label}: undeclared command")
        if run["evidence_class"] not in protocol["evidence_classes"]:
            error(f"{label}: unsupported evidence class")
        attempts[(run["task"], run["role"], run["condition"])].append(run["attempt"])
        if run["status"] == "passed" and (run["exit_code"] != 0 or False in run["quality"].values()):
            error(f"{label}: passed run contradicts exit or quality")
        if run["status"] == "skipped" and (run["exit_code"] is not None or any(value is not None for value in run["quality"].values())):
            error(f"{label}: skipped run cannot have exit or graded quality")
        usage = run["usage"]
        if usage["total"] is not None:
            known_sum = sum(usage[key] for key in INPUT_OUTPUT if usage[key] is not None)
            if known_sum > usage["total"]:
                error(f"{label}: known usage categories exceed total")
            elif all(usage[key] is not None for key in INPUT_OUTPUT) and known_sum != usage["total"]:
                error(f"{label}: disjoint usage categories do not equal total")
        if usage["reasoning_in_output"] is not None and usage["output"] is not None and usage["reasoning_in_output"] > usage["output"]:
            error(f"{label}: reasoning exceeds inclusive output")
    if any(len(values) != len(set(values)) for values in attempts.values()):
        error("observations: duplicate task/role/condition attempt")
    qualifications = decision["qualification_run_ids"]
    if decision["decision"] == "adopt_within_scope" and (record["status"] != "observed" or not qualifications):
        error("adopt_within_scope: observed scoped qualification required")
    for identifier in qualifications:
        run = by_id.get(identifier)
        if (run is None or not accepted(run) or run["condition"] != "candidate"
                or run["scope"] != decision["scope"] or run["evidence_class"] not in EXECUTION):
            error("qualification_run_ids: successful candidate execution in exact scope required")
        elif any(other["condition"] == "candidate" and other["task"] == run["task"]
                 and other["role"] == run["role"] and other["scope"] == run["scope"]
                 and other["attempt"] > run["attempt"] for other in runs):
            error("qualification_run_ids: latest candidate attempt in task/role/scope required")
    expected = assessment["expected_run_ids"]
    if not set(expected) <= by_id.keys():
        error("usage_assessment: expected run IDs include absent observations")
    if assessment["coverage"] == "complete":
        artifact = assessment["coverage_artifact"]
        if not runs or set(expected) != by_id.keys() or artifact is None:
            error("usage_assessment: complete coverage needs every run and audit artifact")
        else:
            path = validator.path(artifact["path"], "usage_assessment.coverage_artifact")
            if path is not None:
                try:
                    ledger = read_json(path)
                    if (not isinstance(ledger, dict) or set(ledger) != {"run_ids", "complete"}
                            or ledger["complete"] is not True or ledger["run_ids"] != expected):
                        error("usage_assessment: coverage artifact disagrees with declared run IDs")
                except (OSError, ValueError):
                    error("usage_assessment: invalid coverage JSON")
    if assessment["claim"] == "whole_task_token_savings":
        required = {(task, role, condition) for task in record["frozen_inputs"]["tasks"]
                    for role in record["frozen_inputs"]["roles"] for condition in ("baseline", "candidate")}
        known = all(all(value is not None for value in run["usage"].values()) for run in runs)
        if assessment["coverage"] != "complete" or set(attempts) != required:
            error("savings claim: complete matched task/role/condition coverage required")
        if any(sorted(values) != list(range(1, len(values) + 1)) for values in attempts.values()):
            error("savings claim: consecutive attempt coverage required")
        if any(len(attempts.get((task, role, "baseline"), [])) != len(attempts.get((task, role, "candidate"), []))
               for task in record["frozen_inputs"]["tasks"] for role in record["frozen_inputs"]["roles"]):
            error("savings claim: equal passing attempt counts required per task and role")
        if not runs or not known or not all(accepted(run) for run in runs):
            error("savings claim: every attempt needs passing quality and complete known usage")
        elif any(run["evidence_class"] not in EXECUTION or run["scope"] != decision["scope"] for run in runs):
            error("savings claim: scoped execution evidence required for every attempt")
        elif sum(run["usage"]["total"] for run in runs if run["condition"] == "candidate") >= sum(run["usage"]["total"] for run in runs if run["condition"] == "baseline"):
            error("savings claim: candidate total must be lower than baseline")


def validate_record(root, relative_path):
    validator = Validator(root)
    if Path(root).is_symlink():
        return {"valid": False, "errors": ["root: symlinks are forbidden"], "observations": 0}
    path = validator.path(relative_path, "record")
    record = None
    if path is not None:
        try:
            record = read_json(path)
            schema = read_json(CONTRACT / "contract.schema.json")
            structure(record, schema, schema["$defs"], "record", validator.errors)
            if not validator.errors:
                check_artifacts(record, validator)
                consistency(record, validator)
        except (OSError, ValueError):
            validator.error("record: unreadable or invalid JSON")
    return {"valid": not validator.errors, "errors": validator.errors,
            "observations": len(record.get("observations", [])) if isinstance(record, dict) and isinstance(record.get("observations"), list) else 0}


def recorded_paths(root):
    """Discover declared records from the hash manifest, without running commands."""
    validator = Validator(root)
    path = validator.path("manifests/evidence.json", "manifest")
    if path is None or Path(root).is_symlink():
        raise ValueError("record discovery: invalid manifest path")
    try:
        manifest = read_json(path)
        rows = manifest["files"]
        declared = manifest["convergence_records"]
        if not isinstance(rows, list) or not rows:
            raise ValueError
        if (not isinstance(declared, list) or not declared
                or any(not isinstance(name, str) for name in declared)
                or len(set(declared)) != len(declared)):
            raise ValueError
        paths, seen = [], set()
        for row in rows:
            name = row["path"]
            if not isinstance(name, str) or name in seen:
                raise ValueError
            seen.add(name)
            if not name.endswith(".json"):
                continue
            source = validator.path(name, "manifest record")
            if source is None:
                raise ValueError
            content = source.read_bytes()
            if hashlib.sha256(content).hexdigest() != row["sha256"]:
                raise ValueError
            data = read_json(source)
            is_record = isinstance(data, dict) and data.get("kind") == "convergence_experiment"
            canonical = re.fullmatch(
                r"blueprints/convergence-practice/(?:[^/]+/)+experiment(?:-[^/]+)?\.json", name)
            if (is_record or canonical) and name not in declared:
                raise ValueError
            if name in declared:
                paths.append(name)
        if set(paths) != set(declared):
            raise ValueError
        return sorted(paths)
    except (OSError, ValueError, KeyError, TypeError):
        raise ValueError("record discovery: invalid, changed or empty evidence manifest") from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("records", nargs="*", help="Canonical paths relative to --root")
    parser.add_argument("--all-recorded", action="store_true",
                        help="Validate every convergence record in the evidence hash manifest")
    parser.add_argument("--root", type=Path, default=REPO)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.all_recorded == bool(args.records):
        parser.error("choose explicit records or --all-recorded")
    try:
        paths = recorded_paths(args.root) if args.all_recorded else args.records
        results = [dict(path=path, **validate_record(args.root, path)) for path in paths]
    except ValueError as error:
        results = [{"valid": False, "errors": [str(error)], "observations": 0}]
    valid = all(item["valid"] for item in results)
    if args.json:
        print(json.dumps({"valid": valid, "records": results}, sort_keys=True))
    else:
        for index, result in enumerate(results):
            print(f"record[{index}]: {'valid' if result['valid'] else 'invalid'}")
            for error in result["errors"]:
                print(f"  {error}")
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
