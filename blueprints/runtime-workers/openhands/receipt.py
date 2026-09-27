"""Sanitized evidence from native SDK events, independent check and gateway rows.

Uses Python's sqlite3 URI mode=ro + query_only. The only SQL SELECT reads the
authorized usage/effort columns from call_logs. Correlation IDs may be used
in memory for matching, but are never returned in receipts.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sqlite3
import stat

from recipe import HERE, arm_config, read_json, tool_filter
from e2e.check import read_report


COLUMNS = (
    "timestamp", "path", "status", "model", "reasoning_effort_requested",
    "reasoning_effort_upstream", "tokens_in", "tokens_cache_read", "tokens_reasoning", "correlation_id",
)
EFFORTS = {"none", "minimal", "low", "medium", "high", "xhigh", "max", "auto"}


def read_bounded(path, limit=4 * 1024 * 1024):
    """CPython@v3.13.15 os.open dir_fd/O_NOFOLLOW; refuse every symlink hop.

    Worker files are untrusted even if their content parses. O_NONBLOCK avoids
    hanging on a malicious FIFO; fstat checks the opened object, not its name.
    """
    path = Path(path).absolute()
    directory = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            os.close(directory)
            directory = child
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
    finally:
        os.close(directory)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
            raise ValueError("receipt_input_not_bounded_regular_file")
        data = stream.read(limit + 1)
        if len(data) > limit:
            raise ValueError("receipt_input_too_large")
    return data.decode("utf-8")


def gateway_database(arm):
    arm_config(arm)
    store = "omniroute" if arm == "control" else "omniroute-fw"
    return Path.home() / ".local/share" / store / "storage.sqlite"


def summarize_gateway(rows, selection):
    matched = [row for row in rows if row.get("model") == selection["gateway_model"]
               and row.get("path") == selection["gateway_path"]]
    counters = ("tokens_in", "tokens_cache_read", "tokens_reasoning")
    known = bool(matched) and all(isinstance(row.get(k), int) and not isinstance(row[k], bool)
                                 and row[k] >= 0 for row in matched for k in counters)
    reasoning = [row for row in matched if (row.get("tokens_reasoning") or 0) > 0]
    return {"rows": [{k: row.get(k) for k in COLUMNS if k != "correlation_id"} for row in matched],
            "totals": {k: sum(row[k] for row in matched) for k in counters} if known else None,
            "reasoning_rows": len(reasoning),
            "no_returned_reasoning_rows": sum(row.get("tokens_reasoning") == 0 for row in matched),
            "unknown_reasoning_rows": sum(row.get("tokens_reasoning") is None for row in matched),
            "effort_verified": bool(reasoning) and all(
                row.get("reasoning_effort_requested") == row.get("reasoning_effort_upstream") == "max"
                for row in reasoning),
            "successful_rows": sum(row.get("status") in (200, "success", "ok") for row in matched)}


def time_value(value):
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000 if value > 100_000_000_000 else value, timezone.utc)
    if isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed
    raise ValueError("invalid_timestamp")


def gateway_rows(database, started_at, finished_at, correlation_ids=None):
    """Read only the arm entry gateway; discard IDs after optional exact matching."""
    start = time_value(started_at)
    end = time_value(finished_at)
    database = Path(database)
    if not database.is_file() or database.is_symlink():
        raise ValueError("gateway_database_must_be_existing_regular_file")
    uri = database.resolve().as_uri() + "?mode=ro"
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
    records = [dict(zip(COLUMNS, row)) for row in rows]
    if correlation_ids is not None:
        records = [row for row in records if row["correlation_id"] in correlation_ids]
    return [sanitize_row(row) for row in records]


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


def observations(events, known_skills=()):
    """A call counts as observed only with a native ObservationEvent."""
    policy = read_json(HERE / "config/mcp-policy.json")
    pattern = re.compile(tool_filter(policy))
    known_skills = set(known_skills)
    completed, failed, skills = Counter(), Counter(), Counter()
    for event in events:
        if not isinstance(event, dict) or event.get("kind") != "ObservationEvent":
            continue
        name = event.get("tool_name", "")
        observation = event.get("observation", {})
        if not isinstance(name, str) or not isinstance(observation, dict):
            continue
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
            events = [json.loads(line) for line in read_bounded(events_path).splitlines() if line]
            trace_status = "observed" if events else "empty"
        except (ValueError, OSError):
            trace_status = "unreadable"
    selection = arm_config(window.get("arm", "control"), window.get("requested_model", window.get("model")),
                           window.get("base_url"))
    db = database or gateway_database(selection["arm"])
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
            native = json.loads(read_bounded(summary))
            candidate = native.get("versions", {}) if isinstance(native, dict) else {}
            if isinstance(candidate, dict) and all(candidate.get(name) == pins["version"] for name in ("openhands-sdk", "openhands-tools")):
                versions = {name: candidate[name] for name in ("openhands-sdk", "openhands-tools")}
        except (OSError, ValueError, TypeError):
            pass
    # Re-read the actual upstream report; a wrapper's own passed field is never
    # a task oracle. The official grader determines all resolved/unresolved IDs.
    verdict = {"upstream_resolved": None, "upstream_bucket": None, "report_sha256": None}
    run_id, instance_id = window.get("run_id"), window.get("instance_id")
    if isinstance(run_id, str) and re.fullmatch(r"rw-openhands-[a-z0-9-]+", run_id) and isinstance(instance_id, str):
        try:
            verdict = read_report(result / ("OpenHands." + run_id + ".json"), instance_id)
        except (OSError, ValueError, TypeError):
            pass
    task_passed = (verdict["upstream_resolved"] is True and checked.get("grader_exit_code") == 0
                   and checked.get("conversion_exit_code") == 0 and window.get("worker_exit_code") == 0)
    listed_skills, skills_match = [], False
    try:
        expected = read_json(result / "input/skills.json")["names"]
        listed = json.loads(read_bounded(result / "worker/skills-startup.json"))["listed_skills"]
        if (isinstance(expected, list) and isinstance(listed, list) and expected
                and all(isinstance(name, str) and re.fullmatch(r"[a-z0-9-]+", name) for name in expected)
                and sorted(expected) == sorted(listed)):
            listed_skills, skills_match = sorted(listed), True
    except (OSError, ValueError, TypeError, KeyError):
        pass
    observed = observations(events, listed_skills)
    usage = summarize_gateway(rows, selection)
    cleanup = []
    for path in sorted(result.glob("*.log.cleanup.json")):
        try:
            cleanup.append(read_json(path).get("confirmed_removed") is True)
        except (OSError, ValueError, AttributeError):
            cleanup.append(False)
    return {
        "schema_version": 3, "evidence_class": "SDK inference adapter with official SWE-bench grading",
        **{k: selection[k] for k in ("arm", "base_url", "requested_model", "gateway_model", "gateway_path")},
        "header_names": window.get("header_names", sorted(selection["headers"])),
        "framework": "OpenHands software-agent-sdk", "expected_version": pins["version"], "observed_versions": versions,
        "image": pins["image"]["ref"], "source_commit": pins["commit"],
        "window": {key: window[key] for key in ("started_at", "finished_at")},
        "worker_exit_code": window.get("worker_exit_code"),
        "failure_stage": window.get("failure_stage") if window.get("failure_stage") in {"preflight", "prepare", "skills", "qmd_setup", "agent", "export", "grader", "start", "wait", "result", "deadline"} else None,
        "task_passed": task_passed,
        # The terminal shares the SDK's UID and writable persistence. Source:
        # SDK@fcc102a tools/terminal/terminal/subprocess_terminal.py. Without a
        # separate observer these files cannot prove skill use or SDK identity.
        "evidence_complete": False,
        "worker_evidence_trust": "worker-reported; not independent acceptance",
        "independent_trace_required": True,
        "skills_listed_at_start": listed_skills, "skill_listing_matches_manifest": skills_match,
        "container_cleanup": {"attempts": len(cleanup), "confirmed_removed": sum(cleanup), "complete": bool(cleanup) and all(cleanup)},
        "gateway": {
            "read_mode": "read_only", "columns": list(COLUMNS), "status": db_status, **usage,
            "entry_port": selection["gateway_port"],
            "attribution": "Time window + model + path at the arm entry gateway; concurrent callers cannot be excluded by the recipe lock.",
            "usage_note": "Sum each entry row once, including failed calls; never add 20128 to 20129. Cache-read is an input subset. Missing counters keep totals null.",
        },
        "compression": window.get("compression", {"delta": None, "status": "unavailable"}),
        "trace_status": trace_status, **observed,
        "upstream_grader": {
            **{key: verdict.get(key) for key in ("upstream_resolved", "upstream_bucket", "report_sha256")},
            "benchmark_commit": pins["grader"]["commit"],
            "sdk_submodule_commit": pins["grader"]["sdk_submodule_commit"],
            "swebench_version": pins["grader"]["swebench_version"],
            "grader_exit_code": checked.get("grader_exit_code"),
            "conversion_exit_code": checked.get("conversion_exit_code"),
        },
        "limits": ["Not unchanged benchmark inference or an upstream SDK test suite",
                   "No matched A/B or token-savings comparison", "No SDK cold-start/crash-resume acceptance"],
    }
