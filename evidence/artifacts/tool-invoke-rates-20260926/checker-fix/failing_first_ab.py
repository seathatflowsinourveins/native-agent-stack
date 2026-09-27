#!/usr/bin/env python3
"""Failing-first control for window-2 finding 2 / decision-thread PRRT_kwDOUg_LrM6mT7_M.

Fully synthetic and offline: no network, no real capture, no live host. It builds one fake tagged Loki export
and one fake tagged Collector events-file line, in each of two bodies -- the fixed placeholder
"[content omitted]" (clean) and the bare literal "pwd" (a leaked short executed command) -- and runs both the
OLD (pre-fix) and NEW (fixed) privacy-check logic over each, so the same four combinations show:
  * OLD accepts the clean body AND the "pwd" leak (the defect: it never asserts the body, and its
    forbidden-string list drops literals under 8/12 characters, so a 3-character leak is never even checked).
  * NEW accepts the clean body and REJECTS the "pwd" leak, on both the Loki sink and the events-file sink.

The OLD logic below is a byte-faithful transcription of the pre-fix design/prove_check.py's seven privacy
assertions (sha256 0f78148934b6e19894c0918e2229c93f1038ccef78d9738b2032d826f1fd7722, snapshotted before this fix
as design/prove_check.py.old-20260926), kept separate from the fixed module so this is a true A/B, not two
paths through the same code. The NEW logic is imported unchanged from the fixed prove_check.py.

Usage: python3 failing_first_ab.py [path/to/fixed/prove_check.py's directory]
Exit 0 iff every expected outcome below actually occurred (a self-check on this script, not on the checkers).
"""
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PC_DIR = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE
spec = importlib.util.spec_from_file_location("prove_check", PC_DIR / "prove_check.py")
prove_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prove_check)  # side-effect free: no argparse, no network (see prove_check.py's main())

TASK = "ABTEST-failing-first"
CONTENT_KEYS = ("tool_parameters", "tool_input", "full_command", "bash_command", "arguments", "output",
                "content", "error", "prompt", "user_email", "user_account_id")
# Same two literals prove.sh now emits for the real probe: the long, always-checked command, and the short one
# ("pwd") that the pre-fix length floors (8 chars in prove_check.py, 12 in prove.sh) silently dropped.
FORBIDDEN_LINES = ["git log --oneline -1", "pwd"]


def make_streams(body):
    return [{"stream": {"service_name": "codex-app-server"},
             "values": [["1790000000000000000", body, {"structuredMetadata": {"ecosystem_task_id": TASK}}]]}]


def make_events_line(body):
    return json.dumps({"resourceLogs": [{"resource": {"attributes": [
        {"key": "service.name", "value": {"stringValue": "codex-app-server"}}]},
        "scopeLogs": [{"scope": {"name": "native-agent-telemetry"}, "logRecords": [
            {"body": {"stringValue": body}, "attributes": [
                {"key": "ecosystem.task.id", "value": {"stringValue": TASK}}]}]}]}]})


def old_privacy_checks(streams, forbidden_lines, events_lines, log):
    """Frozen transcription of design/prove_check.py.old-20260926's seven privacy assertions."""
    lines = [(s["stream"], e) for s in streams for e in s["values"]]
    log("the proof's records were fetched without truncation", 0 < len(lines) < 5000)
    label_sets = {tuple(sorted(stream)) for stream, _ in lines}
    log("every stream's labels are exactly {service_name}", label_sets == {("service_name",)})
    meta = [e[2].get("structuredMetadata", {}) if len(e) > 2 and isinstance(e[2], dict) else {} for _, e in lines]
    keys = sorted({k for stream, _ in lines for k in stream} | {k for m in meta for k in m})
    text = json.dumps(streams)  # DEFECT: forbidden strings are searched against the whole serialized blob
    banned = [k for k in CONTENT_KEYS if k in keys]
    log("proof records carry no content or identity key", bool(lines) and not banned)
    forbidden = [ln.strip() for ln in forbidden_lines if len(ln.strip()) >= 8]  # DEFECT: 8-char floor
    hits = sum(1 for f in forbidden if f in text or json.dumps(f)[1:-1] in text)
    log("no Bash command or prompt text of the proof is stored in Loki", bool(forbidden) and hits == 0,
        f"kept={forbidden}")
    event_hits = sum(1 for f in forbidden for line in events_lines if f in line or json.dumps(f)[1:-1] in line)
    banned_keys = [k for k in ("tool_parameters", "tool_input", "full_command", "arguments", "user.email")
                   if any(f'"key":"{k}"' in line for line in events_lines)]
    log("the Collector's events file holds the proof's records without command, prompt or content keys",
        bool(events_lines) and event_hits == 0 and not banned_keys)
    # (allowlist / name-field checks are unchanged by this fix and are not part of the disputed seven; omitted)


def run(label, fn, *a):
    out = []
    fn(*a, log=lambda name, ok, detail="": out.append((name, ok, detail)))
    return out


def new_privacy_checks(streams, forbidden_lines, events_lines, log):
    lines = prove_check.streams_to_lines(streams)
    forbidden = [ln.strip() for ln in forbidden_lines if ln.strip()]  # same rule as the fixed load_forbidden(): no floor
    prove_check.privacy_checks(lines, forbidden, collector=None, events_lines=events_lines,
                                report=lambda name, ok, detail="": log(name, ok, detail))


def show(label, results):
    print(f"-- {label} --")
    for name, ok, detail in results:
        print(f"  {'PASS' if ok else 'FAIL'} {name}" + (f" :: {detail}" if detail else ""))
    return results


scenarios = {
    ("OLD", "clean body"): (old_privacy_checks, make_streams(prove_check.FIXED_BODY),
                             [make_events_line(prove_check.FIXED_BODY)]),
    ("OLD", "leaked pwd body"): (old_privacy_checks, make_streams("pwd"), [make_events_line("pwd")]),
    ("NEW", "clean body"): (new_privacy_checks, make_streams(prove_check.FIXED_BODY),
                            [make_events_line(prove_check.FIXED_BODY)]),
    ("NEW", "leaked pwd body"): (new_privacy_checks, make_streams("pwd"), [make_events_line("pwd")]),
}
outcomes = {}
for (which, case), (fn, streams, events_lines) in scenarios.items():
    results = run(which, fn, streams, FORBIDDEN_LINES, events_lines)
    outcomes[(which, case)] = show(f"{which} checker, {case}", results)

print()
print("== verdict ==")


def all_pass(key):
    return all(ok for _, ok, _ in outcomes[key])


checks = [
    ("OLD accepts a clean body", all_pass(("OLD", "clean body")), True),
    ("OLD ALSO accepts the leaked 'pwd' body (the defect)", all_pass(("OLD", "leaked pwd body")), True),
    ("NEW accepts a clean body (the fix is not just always-red)", all_pass(("NEW", "clean body")), True),
    ("NEW REJECTS the leaked 'pwd' body", all_pass(("NEW", "leaked pwd body")), False),
]
ok_overall = True
for name, actual, expected in checks:
    passed = actual == expected
    ok_overall &= passed
    print(f"{'PASS' if passed else 'FAIL'} {name}: expected all_pass={expected}, got {actual}")
print(f"\nSUMMARY failing_first_ab: {'every expected outcome occurred' if ok_overall else 'UNEXPECTED OUTCOME'}")

# PR #366 cross-family controls. These exercise the real privacy_checks entry point,
# with clean Loki records so each rejection must come from the events-file sink.
# OTLP reference: opentelemetry-proto v1.9.0, logs/v1/logs.proto and
# common/v1/common.proto (AnyValue, ArrayValue, KeyValueList).
def structural_events(case):
    doc = json.loads(make_events_line(prove_check.FIXED_BODY))
    resource_logs = doc["resourceLogs"][0]
    scope_logs = resource_logs["scopeLogs"][0]
    record = scope_logs["logRecords"][0]
    forbidden_attr = {"key": "fixture", "value": {"stringValue": "pwd"}}
    if case == "earlier leaked body in batch":
        scope_logs["logRecords"].insert(0, {
            "body": {"stringValue": "pwd"}, "attributes": record["attributes"]})
    elif case == "missing body":
        record.pop("body")
    elif case == "non-string body":
        record["body"] = {"intValue": "7"}
    elif case == "non-string stringValue":
        record["body"] = {"stringValue": 7}
    elif case == "resource attribute":
        resource_logs["resource"]["attributes"].append(forbidden_attr)
    elif case == "scope attribute":
        scope_logs["scope"]["attributes"] = [forbidden_attr]
    elif case == "nested kvlist value":
        record["attributes"].append({"key": "fixture", "value": {
            "kvlistValue": {"values": [forbidden_attr]}}})
    elif case == "nested array value":
        scope_logs["scope"]["attributes"] = [{"key": "fixture", "value": {
            "arrayValue": {"values": [{"kvlistValue": {"values": [forbidden_attr]}}]}}}]
    elif case == "spaced banned key":
        record["attributes"].append({"key": "user.email", "value": {"stringValue": "fixture"}})
    elif case == "nested banned key":
        resource_logs["resource"]["attributes"].append({"key": "fixture", "value": {
            "kvlistValue": {"values": [{"key": "user.email", "value": {"stringValue": "fixture"}}]}}})
    elif case == "bytes attribute":
        # ProtoJSON writes bytes as base64 (https://protobuf.dev/programming-guides/json/); "cHdk" is b"pwd".
        resource_logs["resource"]["attributes"].append({"key": "service.instance.id", "value": {"bytesValue": "cHdk"}})
    elif case == "nested bytes value":
        record["attributes"].append({"key": "fixture", "value": {
            "kvlistValue": {"values": [{"key": "fixture", "value": {"bytesValue": "cHdk"}}]}}})
    elif case == "undecodable bytes":
        record["attributes"].append({"key": "fixture", "value": {"bytesValue": "!not base64!"}})
    elif case == "multiple clean records":
        scope_logs["logRecords"].append(record.copy())
    elif case != "clean body":
        raise ValueError("unknown synthetic case")
    return json.dumps(doc)  # Default separators deliberately include spaces.


print("\n== structural events-file regression controls ==")
structural_passed = 0
structural_cases = ["clean body", "multiple clean records", "earlier leaked body in batch",
                    "missing body", "non-string body", "non-string stringValue", "resource attribute",
                    "scope attribute", "nested kvlist value", "nested array value", "spaced banned key",
                    "nested banned key", "bytes attribute", "nested bytes value", "undecodable bytes"]
for case in structural_cases:
    checks = run(case, new_privacy_checks, make_streams(prove_check.FIXED_BODY),
                 FORBIDDEN_LINES, [structural_events(case)])
    accepted = all(ok for _, ok, _ in checks)
    expected = case in {"clean body", "multiple clean records"}
    passed = accepted == expected
    structural_passed += passed
    ok_overall &= passed
    print(f"{'PASS' if passed else 'FAIL'} {case}: expected accepted={expected}, got {accepted}")
print(f"SUMMARY structural_events: {structural_passed} passed, "
      f"{len(structural_cases) - structural_passed} failed")
sys.exit(0 if ok_overall else 1)
