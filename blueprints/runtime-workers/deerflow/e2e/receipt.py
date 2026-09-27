"""Sanitized independent observation from the allowed gateway SQL projection.

Source contract: gateway-owner 2026-09-27 allowlist; SQLite read-only URI and
authorizer APIs; DeerFlow v2.1.0 client.py:492-569 event serialization. Only
call_logs and the round-3 projection plus its required effort fields are read.
Correlation IDs join privately and never enter receipts. This is local glue,
not upstream acceptance. Window fallback cannot attribute concurrent traffic.
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
from urllib.request import urlopen

COLUMNS = ("timestamp", "path", "status", "model", "reasoning_effort_requested",
           "reasoning_effort_upstream", "tokens_in", "tokens_cache_read", "tokens_reasoning", "correlation_id")
EFFORTS = {"none", "minimal", "low", "medium", "high", "xhigh", "max", "auto"}
SERVERS = {"context-mode", "serena", "jcodemunch", "qmd", "ai-memory", "socraticode"}
SKILLS = {"search-first", "verification-before-completion", "modern-python", "iterative-retrieval"}


def compression_snapshot(arm):
    """OmniRoute@a58000c src/app/api/analytics/compression/route.ts:13-24;
    src/lib/db/compressionAnalytics.ts:52-70. Global counters, not usage rows.
    """
    if arm == "control":
        return {"state":"not_applicable"}
    if arm != "engines-on":
        raise ValueError("invalid arm")
    try:
        with urlopen("http://127.0.0.1:20129/api/analytics/compression?since=all", timeout=10) as response:
            raw = json.loads(response.read(1_000_001))
        keys = ("totalRequests", "totalTokensSaved", "totalSkipped")
        if any(type(raw.get(k)) is not int or raw[k] < 0 for k in keys):
            raise ValueError("unsupported compression summary")
        return {"state":"observed", **{k:raw[k] for k in keys}}
    except (OSError, ValueError, TypeError):
        return {"state":"unavailable"}


def compression_delta(before, after):
    keys = ("totalRequests", "totalTokensSaved", "totalSkipped")
    complete = before.get("state") == after.get("state") == "observed"
    if complete:
        complete = all(type(before.get(k)) is int and type(after.get(k)) is int and after[k] >= before[k] for k in keys)
    return {"state":"observed" if complete else "unavailable", "before":before, "after":after,
            "delta":{k:after[k]-before[k] for k in keys} if complete else None,
            "scope":"entry-gateway global compression counter delta; concurrent traffic may contribute; not provider usage"}


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
    safe["model"] = model if isinstance(model, str) and re.fullmatch(r"(?:(?:cx|sharedgw)/)?gpt-6-[a-z0-9-]+-max", model) else "other-model"
    for col in COLUMNS[4:6]:
        safe[col] = raw[col] if raw[col] in EFFORTS else None
    for col in COLUMNS[6:9]:
        safe[col] = raw[col] if type(raw[col]) is int and raw[col] >= 0 else None
    return safe


def gateway_rows(database, start, end, model=None, correlation_ids=None):
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
        rows, seen = [], set()
        for row in connection.execute(query, (start, end)):
            if model and (row[3] not in {model, model.split("/")[-1]}
                          or row[1] not in {"/v1/responses", "/v1/chat/completions"}):
                continue
            if correlation_ids:
                if row[-1] not in correlation_ids:
                    continue
                if row[-1] in seen:
                    raise ValueError("ambiguous duplicate correlation at the entry gateway")
                seen.add(row[-1])
            rows.append(safe_row(row))
        return rows


def gateway_observation(database, window, correlation_ids):
    """Entry-gateway counters only; callLogs.ts effort fields are conditional.

    OmniRoute@a58000c src/sse/handlers/chatHelpers.ts:1172-1184 returns the
    correlation header; the installed build's encrypted-effort rule is the
    gateway owner's round-3 contract, not inferred from null SQL cells.
    """
    try:
        rows = gateway_rows(database, window["start_epoch"], window["end_epoch"],
                            window.get("model"), correlation_ids)
        result = {"state": "observed" if rows else "no_rows", "rows": rows}
    except (OSError, sqlite3.Error, ValueError) as exc:
        result = {"state": "unavailable", "rows": [], "error_class": type(exc).__name__}
        rows = []
    result["entry_gateway"] = 20129 if window.get("arm") == "engines-on" else 20128
    result["scope"] = ("correlated entry-gateway calls; IDs omitted" if correlation_ids else
                       "time window + model + path at entry gateway; concurrent traffic may be included")
    result["correlations_captured"] = len(correlation_ids)
    result["correlations_matched"] = len(rows) if correlation_ids else None
    result["usage_total"] = None
    complete = bool(correlation_ids) and len(rows) == len(correlation_ids)
    if complete and all(type(row[k]) is int for row in rows for k in COLUMNS[6:9]):
        result["usage_total"] = {k: sum(row[k] for row in rows) for k in COLUMNS[6:9]}
    effort = {"with_reasoning_max": 0, "with_reasoning_non_max": 0,
              "with_reasoning_unobserved_effort": 0, "no_returned_reasoning": 0,
              "unknown_reasoning_tokens": 0}
    for row in rows:
        tokens = row["tokens_reasoning"]
        if tokens is None:
            effort["unknown_reasoning_tokens"] += 1
        elif tokens == 0:
            effort["no_returned_reasoning"] += 1
        else:
            values = [row[k] for k in COLUMNS[4:6]]
            key = ("with_reasoning_non_max" if any(v is not None and v != "max" for v in values)
                   else "with_reasoning_unobserved_effort" if None in values else "with_reasoning_max")
            effort[key] += 1
    result["effort"] = effort
    result["evidence_complete"] = bool(complete and result["usage_total"] is not None
        and effort["with_reasoning_max"] and not effort["with_reasoning_non_max"]
        and not effort["with_reasoning_unobserved_effort"] and not effort["unknown_reasoning_tokens"])
    return result


def proxy_correlations(path):
    """Read host-captured nginx logs; this path is never a worker bind mount."""
    found = set()
    if Path(path).is_file():
        with Path(path).open() as source:
            for line in source:
                try:
                    value = json.loads(line).get("correlation_id")
                    if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", value) and value != "-":
                        found.add(value)
                except (ValueError, AttributeError):
                    continue
    return found


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
            # At client.py:527-564 neither serialization includes ToolMessage.status.
            # Preserve emitted additional_kwargs (including subagent_status).
            returns[identity] = {**returns.get(identity, {}), **message}
        for message in message.get("messages", []):
            visit(message)

    inventory = set()
    if Path(trace).is_file():
        for line in Path(trace).read_text().splitlines():
            try:
                event = json.loads(line)
                if not isinstance(event, dict) or not isinstance(event.get("data"), dict):
                    continue
                if event.get("type") == "worker-skills":
                    inventory.update(n for n in event["data"].get("names", [])
                                     if isinstance(n, str) and re.fullmatch(r"[a-zA-Z0-9_-]{1,100}", n))
                visit(event["data"])
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
        if result.get("status") == "error" or not content or content.lstrip().lower().startswith(("error", "failed", "denied")):
            continue
        if any(name.startswith(s + "_") for s in SERVERS) and re.fullmatch(r"[a-zA-Z0-9_-]{1,100}", name):
            mcps[name] += 1
        if name == "read_file":
            path = str(call.get("args", {}).get("path", ""))
            # LocalSandbox@345f08be local_sandbox.py:813-842 returns raw bytes
            # as text, not numbered lines. Require actual bounded frontmatter.
            frontmatter = re.match(r"\A---[ \t]*\r?\n(.*?)\r?\n---(?:[ \t]*\r?\n|$)", content.lstrip(), re.S)
            for skill in inventory | SKILLS:
                if (path in {f"/mnt/skills/{category}/{skill}/SKILL.md" for category in ("legacy", "custom", "public")}
                        and frontmatter and re.search(r"(?m)^name:\s*['\"]?" + re.escape(skill) + r"['\"]?\s*$", frontmatter[1])):
                    skills.add(skill)
    return {"mcp_tool_results_observed": dict(sorted(mcps.items())),
            "skills_listed_at_start": sorted(inventory),
            "required_skills_activated": {"search-first", "verification-before-completion"} <= (inventory & skills),
            "skill_reads_observed": sorted(skills), "task_results_observed": task_results,
            "completed_tasks_observed": task_completed, "failed_tasks_observed": task_failures,
            "scope": "lead native StreamEvents; child-only tool events are not assumed visible; returned results are observations, not semantic success certification"}


def build_receipt(run, database, pins):
    run = Path(run)
    window = json.loads((run / "window.json").read_text())
    gateway = gateway_observation(database, window, proxy_correlations(run / "gateway-correlation.jsonl"))
    transport = {"ok": window.get("transport_ok") is True}
    version = None
    if (run / "framework-events.jsonl").is_file():
        with (run / "framework-events.jsonl").open() as trace:
            for line in trace:
                try:
                    record = json.loads(line)
                except ValueError:
                    continue
                if isinstance(record, dict) and record.get("type") == "worker-version" and isinstance(record.get("data"), dict):
                    candidate = record["data"].get("framework_version")
                    if isinstance(candidate, str) and re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", candidate):
                        version = candidate
                    break
    artifacts = {}
    for name in ("input.txt", "framework-events.jsonl"):
        path = run / name
        if path.is_file() and not path.is_symlink():
            artifacts[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {"schema_version": 3, "evidence_class": "pre-grader native transport with independent SQL observation",
            "arm": window.get("arm"), "base_url": window.get("base_url"), "model": window.get("model"),
            "header_names": window.get("header_names", []), "reasoning_effort": "max",
            "compression": compression_delta(window.get("compression_before", {}), window.get("compression_after", {})),
            "framework": {"tag": pins["tag"], "commit": pins["commit"], "observed_version": version,
                          "images": pins["images"]},
            "window": {"start_epoch": window["start_epoch"], "end_epoch": window["end_epoch"]},
            "framework_exit_code": window.get("framework_exit_code"),
            "cleanup": {k: window.get(k) if window.get(k) in {"absent", "unknown"} else "unknown"
                         for k in ("framework_cleanup", "network_cleanup")},
            "artifact_sha256": artifacts,
            "transport": transport, "gateway": gateway,
            "grader": {"name": "inspect_evals.gaia.gaia_scorer", "version": "0.22.0",
                       "inspect_ai_version": "0.3.271", "verdict": None,
                       "verdict_location": "Inspect .eval log; this receipt is captured before upstream scoring"},
            "observations": observations(run / "framework-events.jsonl"),
            "acceptance": "GAIA score belongs to Inspect; skills, gateway attribution and lifecycle require separate native observations"}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("run", type=Path)
    p.add_argument("--database", type=Path, default=Path.home() / ".local/share/omniroute/storage.sqlite")
    p.add_argument("--pins", type=Path, default=Path(__file__).parents[1] / "pins.json")
    args = p.parse_args()
    receipt = build_receipt(args.run, args.database, json.loads(args.pins.read_text()))
    (args.run / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"receipt_written": True, "transport_ok": receipt["transport"]["ok"],
                      "gateway_observation": receipt["gateway"]["state"]}))
