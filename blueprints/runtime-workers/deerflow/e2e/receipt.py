"""Sanitized independent observation from the allowed gateway SQL projection.

Source contract: gateway-owner 2026-09-27 allowlist; SQLite read-only URI and
authorizer APIs; DeerFlow v2.1.0 client.py:492-569 event serialization. Only
call_logs and the nine authorized columns are read. This is local glue, not
upstream acceptance. Window rows cannot attribute concurrent gateway traffic.
"""
from __future__ import annotations

import argparse
import collections
from contextlib import closing
import datetime as dt
import json
import hashlib
import re
import sqlite3
from pathlib import Path

COLUMNS = ("timestamp", "path", "status", "model", "reasoning_effort_requested",
           "reasoning_effort_upstream", "tokens_in", "tokens_cache_read", "tokens_reasoning")
EFFORTS = {"none", "minimal", "low", "medium", "high", "xhigh", "max", "auto"}
SERVERS = {"context-mode", "serena", "jcodemunch", "qmd", "ai-memory", "socraticode"}
SKILLS = {"search-first", "verification-before-completion", "modern-python", "iterative-retrieval"}


def sql_authorizer(action, arg1, arg2, database, trigger):
    if action == sqlite3.SQLITE_READ:
        return sqlite3.SQLITE_OK if arg1 == "call_logs" and arg2 in COLUMNS else sqlite3.SQLITE_DENY
    if action in {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_FUNCTION}:
        return sqlite3.SQLITE_OK
    return sqlite3.SQLITE_DENY


def safe_row(row):
    raw = dict(zip(COLUMNS, row, strict=True))
    safe = {}
    value = raw["timestamp"]
    try:
        if isinstance(value, (float, int)) or (isinstance(value, str) and value.replace(".", "", 1).isdigit()):
            number = float(value)
            value = dt.datetime.fromtimestamp(number / (1000 if number > 100_000_000_000 else 1), dt.UTC)
        else:
            value = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        safe["timestamp"] = value.isoformat()
    except (TypeError, ValueError, OverflowError):
        safe["timestamp"] = None
    safe["path"] = raw["path"] if raw["path"] in {"/v1/responses", "/v1/chat/completions"} else "other"
    status = str(raw["status"])
    safe["status"] = raw["status"] if re.fullmatch(r"[1-5][0-9]{2}|success|error|failed|completed", status) else None
    model = raw["model"]
    safe["model"] = model if isinstance(model, str) and re.fullmatch(r"(?:cx/)?gpt-[a-zA-Z0-9._-]{1,64}", model) else "other-model"
    for col in COLUMNS[4:6]:
        safe[col] = raw[col] if raw[col] in EFFORTS else None
    for col in COLUMNS[6:]:
        safe[col] = raw[col] if type(raw[col]) is int and raw[col] >= 0 else None
    return safe


def gateway_rows(database, start, end):
    # mode=ro observes the live WAL. immutable=1 is intentionally NOT used.
    uri = Path(database).resolve().as_uri() + "?mode=ro"
    query = "SELECT " + ", ".join(COLUMNS) + " FROM call_logs WHERE " + (
        "CASE WHEN typeof(timestamp) IN ('integer','real') OR "
        "(typeof(timestamp) = 'text' AND timestamp GLOB '[0-9]*' "
        "AND timestamp NOT GLOB '*[^0-9.]*' "
        "AND length(timestamp)-length(replace(timestamp,'.','')) <= 1) "
        "THEN CAST(timestamp AS REAL) / CASE WHEN CAST(timestamp AS REAL) > 100000000000 THEN 1000.0 ELSE 1.0 END "
        "ELSE (julianday(timestamp)-2440587.5)*86400 END BETWEEN ? AND ? ORDER BY timestamp"
    )
    with closing(sqlite3.connect(uri, uri=True, timeout=3)) as connection:
        connection.set_authorizer(sql_authorizer)
        return [safe_row(row) for row in connection.execute(query, (start, end))]


def observations(trace):
    calls, returns = {}, {}

    def visit(message):
        if not isinstance(message, dict):
            return
        for tool in message.get("tool_calls", []):
            if isinstance(tool, dict) and tool.get("id"):
                calls[str(tool["id"])] = tool
        if message.get("type") == "tool" and message.get("tool_call_id"):
            identity = str(message["tool_call_id"])
            # values snapshots carry status metadata missing from tuple events.
            returns[identity] = {**returns.get(identity, {}), **message}
        for message in message.get("messages", []):
            visit(message)

    if Path(trace).is_file():
        for line in Path(trace).read_text().splitlines():
            try:
                visit(json.loads(line).get("data", {}))
            except (ValueError, TypeError):
                continue
    mcps, skills = collections.Counter(), set()
    task_results, task_completed, task_failures = 0, 0, 0
    for identity, call in calls.items():
        result = returns.get(identity)
        if not result:
            continue
        name = call.get("name", "")
        # Native status is authoritative even when the text is empty or an error.
        # Reference: subagents/status_contract.py:67-89 at the pinned revision.
        if name == "task":
            task_results += 1
            status = result.get("additional_kwargs", {}).get("subagent_status")
            if status == "completed":
                task_completed += 1
            elif status in {"failed", "timed_out", "cancelled", "polling_timed_out"}:
                task_failures += 1
            continue
        content = str(result.get("content", ""))
        if not content or content.lstrip().lower().startswith(("error", "failed", "denied")):
            continue
        if any(name.startswith(s + "_") for s in SERVERS) and re.fullmatch(r"[a-zA-Z0-9_-]{1,100}", name):
            mcps[name] += 1
        if name == "read_file":
            path = str(call.get("args", {}).get("path", ""))
            for skill in SKILLS:
                if path.endswith("/" + skill + "/SKILL.md"):
                    skills.add(skill)
    return {"mcp_tool_results_observed": dict(sorted(mcps.items())),
            "skill_reads_observed": sorted(skills), "task_results_observed": task_results,
            "completed_tasks_observed": task_completed, "failed_tasks_observed": task_failures,
            "scope": "lead native StreamEvents; child-only tool events are not assumed visible; returned results are observations, not semantic success certification"}


def build_receipt(run, database, pins):
    run = Path(run)
    window = json.loads((run / "window.json").read_text())
    try:
        rows = gateway_rows(database, window["start_epoch"], window["end_epoch"])
        gateway = {"state": "observed" if rows else "no_rows", "rows": rows}
    except (OSError, sqlite3.Error, ValueError) as exc:
        gateway = {"state": "unavailable", "rows": [], "error_class": type(exc).__name__}
    gateway["scope"] = "time window only; concurrent traffic may be included; no session IDs or other columns queried"
    gateway["usage_total"] = None  # No total falsely attributed from a shared window.
    try:
        check = json.loads((run / "check.json").read_text())
    except (OSError, ValueError):
        check = {"passed": False, "reason": "checker_result_unavailable"}
    # Keep only declared fields; neither driver metadata nor checker output is a public passthrough.
    check = {"passed": check.get("passed") is True,
             "exit_code": window.get("check_exit_code")}
    version = None
    if (run / "framework-events.jsonl").is_file():
        with (run / "framework-events.jsonl").open() as trace:
            for line in trace:
                try:
                    record = json.loads(line)
                except ValueError:
                    continue
                if record.get("type") == "worker-version":
                    candidate = record.get("data", {}).get("framework_version")
                    if isinstance(candidate, str) and re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", candidate):
                        version = candidate
                    break
    artifacts = {}
    for name in ("files.json", "summarize.py", "report.json"):
        path = run / "artifacts" / name
        if path.is_file() and not path.is_symlink() and path.stat().st_size <= 1_000_000:
            artifacts[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {"schema_version": 1, "evidence_class": "host local integration check with independent SQL observation",
            "framework": {"tag": pins["tag"], "commit": pins["commit"], "observed_version": version,
                          "images": pins["images"]},
            "window": {"start_epoch": window["start_epoch"], "end_epoch": window["end_epoch"]},
            "framework_exit_code": window.get("framework_exit_code"),
            "cleanup": {k: window.get(k) if window.get(k) in {"absent", "unknown"} else "unknown"
                        for k in ("framework_cleanup", "checker_cleanup")},
            "artifact_sha256": artifacts,
            "check": check, "gateway": gateway,
            "observations": observations(run / "framework-events.jsonl"),
            "acceptance": "task check and observations only; host review must establish gateway attribution and lifecycle before adoption"}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("run", type=Path)
    p.add_argument("--database", type=Path, default=Path.home() / ".local/share/omniroute/storage.sqlite")
    p.add_argument("--pins", type=Path, default=Path(__file__).parents[1] / "pins.json")
    args = p.parse_args()
    receipt = build_receipt(args.run, args.database, json.loads(args.pins.read_text()))
    (args.run / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"receipt_written": True, "check_passed": receipt["check"]["passed"],
                      "gateway_observation": receipt["gateway"]["state"]}))
