#!/usr/bin/env python3
"""Primary metric of A2 (PREREGISTRATION-local-models.md, Part A2 and amendment 3b): first-pass valid tool calls,
read from the evaluation package's own logs. A case is valid when the first model answer of the sample carries at
least one tool call and every call in it parses, names a tool that was offered in that request, and has arguments
that satisfy that tool's JSON schema. No repair and no retry: a request that errored, or an answer without a tool
call, is invalid. Prints one JSON line per case and a last summary line. The package's own score is copied beside
it and is not the primary metric. usage: a2_validity.py <log directory>"""
import json
import pathlib
import sys

import jsonschema
from inspect_ai.log import read_eval_log


def schema_of(tool):
    params = tool.parameters
    data = params.model_dump(exclude_none=True) if hasattr(params, "model_dump") else dict(params)
    return data


def judge(sample):
    first = next((event for event in sample.events if getattr(event, "event", "") == "model"), None)
    if sample.error is not None and first is None:
        return False, "the sample errored before any model answer", 0
    if first is None:
        return False, "no model request was recorded", 0
    if getattr(first, "error", None):
        return False, "the first request errored: " + str(first.error)[:160], 0
    offered = {tool.name: schema_of(tool) for tool in (first.tools or [])}
    choices = first.output.choices if first.output else []
    calls = (choices[0].message.tool_calls if choices else None) or []
    if not calls:
        return False, "no tool call in the first answer", 0
    for call in calls:
        if call.parse_error:
            return False, "arguments did not parse: " + str(call.parse_error)[:120], len(calls)
        if call.function not in offered:
            return False, f"names a tool that was not offered: {call.function}"[:160], len(calls)
        try:
            jsonschema.validate(call.arguments, offered[call.function])
        except jsonschema.ValidationError as error:
            return False, "arguments do not satisfy the schema: " + error.message[:120], len(calls)
        except jsonschema.SchemaError as error:
            return False, "the offered schema itself is not valid: " + error.message[:120], len(calls)
    return True, "", len(calls)


total = valid = errors = 0
package_correct = package_scored = 0
files = sorted(pathlib.Path(sys.argv[1]).glob("*.eval")) + sorted(pathlib.Path(sys.argv[1]).glob("*.json"))
tokens = {"input": 0, "output": 0}
for path in files:
    if path.name == "validity.jsonl":
        continue
    try:
        log = read_eval_log(str(path))
    except Exception:
        continue
    for sample in log.samples or []:
        ok, reason, n_calls = judge(sample)
        score = None
        for value in (sample.scores or {}).values():
            score = value.value
            break
        if score is not None:
            package_scored += 1
            package_correct += score in ("C", 1, 1.0, True)
        for usage in (sample.model_usage or {}).values():
            tokens["input"] += usage.input_tokens or 0
            tokens["output"] += usage.output_tokens or 0
        total += 1
        valid += ok
        errors += sample.error is not None
        print(json.dumps({"id": str(sample.id), "valid": ok, "reason": reason, "tool_calls": n_calls,
                          "package_score": score, "sample_error": sample.error is not None,
                          "seconds": round(sample.total_time or 0, 1) if getattr(sample, "total_time", None) else None}))
print(json.dumps({"summary": True, "logs": [p.name for p in files if p.name != "validity.jsonl"], "cases": total, "valid": valid,
                  "valid_share": round(valid / total, 4) if total else None, "sample_errors": errors,
                  "package_correct": package_correct, "package_scored": package_scored, "tokens": tokens}))
