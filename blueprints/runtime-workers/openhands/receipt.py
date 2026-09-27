"""Sanitized evidence from native SDK events, independent check and gateway rows.

Uses Python's sqlite3 URI mode=ro + query_only. The only SQL SELECT reads the
nine user-authorized columns from call_logs. No schema introspection, other
tables, credentials, prompts, responses, request identifiers or client config.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sqlite3

from recipe import HERE, read_json, tool_filter


COLUMNS = (
    "timestamp", "path", "status", "model", "reasoning_effort_requested",
    "reasoning_effort_upstream", "tokens_in", "tokens_cache_read", "tokens_reasoning",
)
EFFORTS = {"none", "minimal", "low", "medium", "high", "xhigh", "max", "auto"}


def time_value(value):
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000 if value > 100_000_000_000 else value, timezone.utc)
    if isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed
    raise ValueError("invalid_timestamp")


def gateway_rows(database, started_at, finished_at):
    """Time-window evidence only: the allowed columns cannot correlate sessions."""
    start = time_value(started_at)
    end = time_value(finished_at)
    uri = Path(database).resolve().as_uri() + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True, timeout=3)
    try:
        connection.execute("PRAGMA query_only = ON")
        # Timestamp storage may be ISO text, epoch seconds, or epoch milliseconds.
        # All predicates still reference the single authorized timestamp column.
        query = "SELECT " + ", ".join(COLUMNS) + " FROM call_logs WHERE " + (
            "(typeof(timestamp) = 'text' AND julianday(timestamp) BETWEEN julianday(?) AND julianday(?)) "
            "OR (typeof(timestamp) IN ('integer','real') AND (timestamp BETWEEN ? AND ? OR timestamp BETWEEN ? AND ?)) "
            "ORDER BY timestamp"
        )
        rows = connection.execute(query, (started_at, finished_at, start.timestamp(), end.timestamp(),
                                          start.timestamp() * 1000, end.timestamp() * 1000)).fetchall()
    finally:
        connection.close()
    return [sanitize_row(dict(zip(COLUMNS, row))) for row in rows]


def sanitize_row(row):
    output = {}
    try:
        output["timestamp"] = time_value(row["timestamp"]).astimezone(timezone.utc).isoformat()
    except (ValueError, TypeError, OverflowError):
        output["timestamp"] = None
    output["path"] = row["path"] if row["path"] in {"/v1/responses", "/v1/chat/completions"} else "<other-path>"
    status = row["status"]
    if isinstance(status, str) and re.fullmatch(r"[1-5][0-9]{2}", status):
        status = int(status)
    output["status"] = status if (isinstance(status, int) and 100 <= status <= 599) or status in {"success", "error", "failed", "ok"} else None
    model = row["model"]
    output["model"] = model if isinstance(model, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{0,159}", model) else "<redacted>"
    for key in ("reasoning_effort_requested", "reasoning_effort_upstream"):
        output[key] = row[key] if row[key] in EFFORTS else None
    for key in ("tokens_in", "tokens_cache_read", "tokens_reasoning"):
        value = row[key]
        output[key] = value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None
    return output


def observations(events):
    """A call counts as observed only with a native ObservationEvent."""
    policy = read_json(HERE / "config/mcp-policy.json")
    pattern = re.compile(tool_filter(policy))
    known_skills = {s["name"] for s in read_json(HERE / "config/skills.lock.json")["skills"]}
    completed, failed, skills = Counter(), Counter(), Counter()
    for event in events:
        if event.get("kind") != "ObservationEvent":
            continue
        name = event.get("tool_name", "")
        observation = event.get("observation", {})
        if any(name.startswith(server + "_") for server in policy) and pattern.fullmatch(name):
            completed[name] += 1
            if observation.get("is_error"):
                failed[name] += 1
        if name == "invoke_skill" and not observation.get("is_error"):
            skill = observation.get("skill_name")
            if skill in known_skills:
                skills[skill] += 1
    return {"mcp_calls_observed": dict(completed), "mcp_errors_observed": dict(failed),
            "skills_observed": dict(skills), "basis": "native ObservationEvent fields; registration alone is not usage"}


def create_receipt(result, database=None):
    result = Path(result)
    window = read_json(result / "window.json")
    checked = read_json(result / "check.json")
    events_path = result / "worker/events.jsonl"
    events = []
    trace_status = "missing"
    if events_path.is_file():
        try:
            events = [json.loads(line) for line in events_path.read_text().splitlines() if line]
            trace_status = "observed" if events else "empty"
        except (ValueError, OSError):
            trace_status = "unreadable"
    db = database or Path.home() / ".local/share/omniroute/storage.sqlite"
    rows, db_status = [], "unavailable"
    try:
        rows = gateway_rows(db, window["started_at"], window["finished_at"])
        db_status = "observed" if rows else "empty_window"
    except (OSError, sqlite3.Error, ValueError, TypeError):
        pass  # Unknown usage is not zero usage. No raw exception text is exported.
    pins = read_json(HERE / "pins.json")
    versions = None
    summary = result / "worker/native-summary.json"
    if summary.is_file():
        try:
            native = read_json(summary)
            candidate = native.get("versions", {}) if isinstance(native, dict) else {}
            if isinstance(candidate, dict) and all(candidate.get(name) == pins["version"] for name in ("openhands-sdk", "openhands-tools")):
                versions = {name: candidate[name] for name in ("openhands-sdk", "openhands-tools")}
        except (OSError, ValueError, TypeError):
            pass
    tests = checked.get("tests") or {}
    # Never copy arbitrary checker output, file paths or error strings into public evidence.
    allowed_failures = {
        "missing_result", "frozen_fixture_changed", "diff_outside_allowed_files_or_empty", "nonregular_result",
        "baseline_not_one_failing_test", "no_native_test_failure_before_edit", "tests_mutated_workspace",
        "tests_not_passing_unskipped", "invalid_or_incomplete_result", "checker_did_not_return_json",
    }
    task_passed = checked.get("passed") is True and checked.get("exit_code") == 0 and window.get("worker_exit_code") == 0
    observed = observations(events)
    expected_model = window.get("model")
    matching_gateway_rows = [row for row in rows if (
        row["model"] == expected_model and row["path"] == "/v1/responses"
        and row["status"] in (200, "success", "ok") and row["reasoning_effort_upstream"] == "max"
    )]
    cleanup = []
    for path in sorted(result.glob("*.log.cleanup.json")):
        try:
            cleanup.append(read_json(path).get("confirmed_removed") is True)
        except (OSError, ValueError, AttributeError):
            cleanup.append(False)
    return {
        "schema_version": 1, "evidence_class": "local integration on a synthetic fixture",
        "framework": "OpenHands software-agent-sdk", "expected_version": pins["version"], "observed_versions": versions,
        "image": pins["image"]["ref"], "source_commit": pins["commit"],
        "window": {key: window[key] for key in ("started_at", "finished_at")},
        "worker_exit_code": window.get("worker_exit_code"),
        "failure_stage": window.get("failure_stage") if window.get("failure_stage") in {"baseline", "qmd_setup", "agent"} else None,
        "task_passed": task_passed,
        "evidence_complete": bool(matching_gateway_rows) and trace_status == "observed"
        and versions is not None and observed["skills_observed"].get("tdd", 0) > 0 and bool(cleanup) and all(cleanup),
        "container_cleanup": {"attempts": len(cleanup), "confirmed_removed": sum(cleanup), "complete": bool(cleanup) and all(cleanup)},
        "gateway": {
            "read_mode": "read_only", "columns": list(COLUMNS), "status": db_status, "rows": rows,
            "matching_model_responses_max_rows": len(matching_gateway_rows),
            "attribution": "Time window only; may include concurrent callers. Session/request identifiers are forbidden by this receipt contract.",
            "totals": None,
            "usage_note": "Rows are not summed or claimed as exclusive worker cost. Cache-read is a subset of input; missing counters remain null.",
        },
        "trace_status": trace_status, **observed,
        "check": {
            "passed": checked.get("passed") is True,
            "exit_code": checked.get("exit_code"),
            "failures": [reason if reason in allowed_failures else "invalid_or_incomplete_result" for reason in checked.get("failures", [])],
            "allowed_file_changed": "range_utils.py" in checked.get("changed_files", []),
            "tests": {key: tests.get(key) for key in ("tests_run", "failures", "errors", "skipped", "exit_code")},
        },
        "limits": ["Not an upstream SDK test suite", "No matched token-savings comparison", "No SDK cold-start/crash-resume acceptance"],
    }
