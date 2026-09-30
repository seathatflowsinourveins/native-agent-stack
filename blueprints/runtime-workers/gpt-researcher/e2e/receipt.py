"""Sanitized local integration receipt; no provider calls or state mutations.

SQLite URI mode=ro follows Python sqlite3's URI example. The only SELECT uses
the round-3 usage/correlation columns and the two required effort diagnostics.
Native tool observations follow gpt_researcher/mcp/research.py:93,123 at v3.7.0.
"""
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import math
import urllib.request
from pathlib import Path
import re
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mcp_proxy import POLICY
from check import check
from grader import read_grade
from gateway import select_routes

# Round-3 section 2 authorizes correlation_id, section 3 the two effort fields.
# OmniRoute@a58000c src/lib/usage/callLogs.ts; CPython@v3.12.12 sqlite3 URI mode=ro.
COLUMNS = ("timestamp", "path", "status", "model", "reasoning_effort_requested",
           "reasoning_effort_upstream", "tokens_in", "tokens_cache_read", "tokens_reasoning")
PATHS = ("/v1/responses", "/v1/chat/completions", "/responses", "/chat/completions")
SQL = """SELECT timestamp, path, status, model, reasoning_effort_requested,
reasoning_effort_upstream, tokens_in, tokens_cache_read, tokens_reasoning, correlation_id
FROM call_logs
WHERE julianday(timestamp) >= julianday(?) AND julianday(timestamp) < julianday(?)
AND model IN (?, ?) AND path IN (?, ?, ?, ?)
ORDER BY timestamp"""


def gateway_database(home, arm, engines_verified=False):
    if arm == "engines-on" and not engines_verified:
        raise ValueError("coordinator must verify the 20129 instance database path before use")
    if arm not in ("control", "engines-on"):
        raise ValueError("unknown arm")
    return home / (".local/share/omniroute-fw/storage.sqlite" if arm == "engines-on"
                   else ".local/share/omniroute/storage.sqlite")


def captured_ids(path):
    try:
        events = [json.loads(line) for line in path.read_text().splitlines()]
        requests = sum(e["event"] == "request" for e in events)
        ids = [e.get("correlation_id") for e in events if e["event"] == "response"]
        return set(ids) if requests and len(ids) == requests and all(ids) else None
    except (OSError, ValueError, KeyError, TypeError):
        return None


def gateway_rows(database, started, ended, model, correlation_ids=None):
    try:
        # URI mode=ro does not create a missing database. No schema/auth queries.
        with closing(sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True, timeout=5)) as connection:
            rows = connection.execute(SQL, (started, ended, model, model.split("/", 1)[-1], *PATHS)).fetchall()
    except (OSError, sqlite3.Error):
        return {"status": "unavailable", "rows": [], "error": "read_only_call_logs_query_failed"}
    sanitized = []
    matched_ids = set()
    for row in rows:
        if correlation_ids is not None and row[-1] not in correlation_ids:
            continue
        matched_ids.add(row[-1])
        item = dict(zip(COLUMNS, row[:-1]))  # identifiers never enter a receipt
        try:
            item["timestamp"] = datetime.fromisoformat(str(item["timestamp"]).replace("Z", "+00:00")).isoformat()
        except ValueError:
            item["timestamp"] = None
        for key in ("reasoning_effort_requested", "reasoning_effort_upstream"):
            if item[key] not in (None, "minimal", "low", "medium", "high", "xhigh", "max", "none", "auto"):
                item[key] = "<other-effort>"
        for key in ("status", "tokens_in", "tokens_cache_read", "tokens_reasoning"):
            value = item[key]
            if isinstance(value, str) and value.isdecimal():
                value = int(value)
            item[key] = value if type(value) in (int, float) and math.isfinite(value) and value >= 0 else None
        sanitized.append(item)
    reasoning = [r for r in sanitized if (r["tokens_reasoning"] or 0) > 0]
    effort = {"with_returned_reasoning": len(reasoning),
              "without_returned_reasoning": sum(r["tokens_reasoning"] == 0 for r in sanitized),
              "unknown_reasoning_usage": sum(r["tokens_reasoning"] is None for r in sanitized),
              "non_max_returned_reasoning": sum(any(r[k] not in (None, "max") for k in
                  ("reasoning_effort_requested", "reasoning_effort_upstream")) for r in reasoning),
              "max_upstream_observed": sum(r["reasoning_effort_upstream"] == "max" for r in reasoning),
              "note": "Null effort is unobserved, not evidence of a missing request; fields require encrypted reasoning."}
    missing = len(correlation_ids - matched_ids) if correlation_ids is not None else 0
    return {"status": "incomplete" if missing else ("observed" if sanitized else "empty"),
            "missing_correlation_count": missing, "rows": sanitized, "effort": effort,
            "attribution": "correlation_id" if correlation_ids is not None else
                "time window + model + path at entry gateway; concurrent callers may overlap",
            "usage": "raw row counters; no totals and no addition of the forwarding gateway"}


def compression_snapshot(arm):
    # OmniRoute@a58000c src/app/api/analytics/compression/route.ts:13-25;
    # src/lib/db/compressionAnalytics.ts:52-55. Only cumulative counters.
    if arm != "engines-on":
        return {"status": "not_applicable"}
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open("http://127.0.0.1:20129/api/analytics/compression?since=all", timeout=5) as response:
            data = json.loads(response.read(1024 * 1024))
        values = {k: data[k] for k in ("totalRequests", "totalTokensSaved")}
        if any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in values.values()):
            raise ValueError("invalid compression counters")
        return {"status": "observed", **values}
    except (OSError, ValueError, KeyError, TypeError):
        return {"status": "unavailable"}


def compression_delta(before, after):
    if before.get("status") == after.get("status") == "not_applicable":
        return {"status": "not_applicable"}
    keys = ("totalRequests", "totalTokensSaved")
    if before.get("status") != "observed" or after.get("status") != "observed":
        return {"status": "unavailable"}
    delta = {k: after[k] - before[k] for k in keys}
    if any(v < 0 for v in delta.values()):
        return {"status": "counter_reset"}
    return {"status": "observed", "before": before, "after": after, "delta": delta,
            "scope": "20129 aggregate over worker phase; other callers may overlap; separate from token usage"}


def gateway_evidence_complete(observation):
    return (observation["status"] == "observed"
            and observation.get("effort", {}).get("non_max_returned_reasoning") == 0
            and any(r.get("status") is not None and 200 <= r["status"] < 300
                    for r in observation["rows"]))


def native_observations(log_path):
    tools = {tool: server for server, policy in POLICY["servers"].items() if policy["active"]
             for tool in policy["enabled_tools"]}
    attempts, results = Counter(), Counter()
    if log_path.exists():
        for line in log_path.read_text(errors="replace").splitlines():
            if "gpt_researcher.mcp.research " not in line:
                continue
            called = re.search(r" INFO Executing tool \d+/\d+: ([a-z_]+)$", line)
            returned = re.search(r" INFO Tool ([a-z_]+) returned ([1-9][0-9]*) formatted results$", line)
            if called and called[1] in tools:
                attempts[called[1]] += 1
            if returned and returned[1] in tools:
                results[returned[1]] += 1
    return [{"server": tools[name], "tool": name, "attempts": count,
             "nonempty_returns": results[name]}
            for name, count in sorted(attempts.items())]


def route_metadata(routes):
    metadata = {}
    for phase in ("worker", "judge"):
        headers = ["x-omniroute-session", "Idempotency-Key"]
        if phase == "worker" and routes["arm"] == "engines-on":
            headers.append("x-omniroute-compression")
        metadata[phase] = {**routes[phase], "header_names": headers, "reasoning_effort": "max"}
    return metadata


def phase_usage(run_dir, routes, phases, engines_verified=False, database=None):
    observations = {}
    for phase in ("worker", "judge"):
        if not phases.get(phase + "_started") or not phases.get(phase + "_ended"):
            observations[phase] = {"status": "unavailable", "rows": [], "error": "phase_not_finished"}
            continue
        try:
            db = database or gateway_database(Path.home(), routes["arm"] if phase == "worker" else "control",
                                              engines_verified)
        except ValueError:
            observations[phase] = {"status": "unavailable", "rows": [], "error": "entry_database_not_verified"}
            continue
        observations[phase] = gateway_rows(db, phases[phase + "_started"], phases[phase + "_ended"],
                                           routes[phase]["model"],
                                           correlation_ids=captured_ids(run_dir / (phase + "-correlations.jsonl")))
    return observations


def write_receipt(run_dir, started, ended, model, version, runtime_error=None, database=None,
                  routes=None, phases=None, engines_verified=False):
    recipe = Path(__file__).resolve().parents[1]
    pins = json.loads((recipe / "pins.json").read_text())
    result_path = run_dir / "result.json"
    try:
        result = json.loads(result_path.read_text())
    except (OSError, ValueError):
        result = {}
        runtime_error = runtime_error or "MalformedResult"
    sanity = check(result)
    try:
        evaluation = read_grade(run_dir)
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        evaluation = {"status": "unavailable_or_malformed", "harness": "DeepResearch-Bench-II",
                      "commit": pins["grader"]["commit"]}
    routes = routes or select_routes({"GPTR_MODEL": model})
    phases = phases or {}
    gateway = phase_usage(run_dir, routes, phases, engines_verified, database)
    compression = {"status": "not_applicable" if routes["arm"] == "control" else "unavailable"}
    try:
        snapshots = json.loads((run_dir / "compression.json").read_text())
        compression = compression_delta(snapshots["before"], snapshots["after"])
    except (OSError, ValueError, KeyError, TypeError):
        pass
    observed = native_observations(run_dir / "native.log")
    model_rows = gateway["worker"]["rows"]
    corroborated = any(row["path"] in ("/v1/responses", "/responses")
                       and row["status"] is not None and 200 <= row["status"] < 300
                       and row["reasoning_effort_upstream"] == "max" for row in model_rows)
    qmd_seen = any(item["server"] == "qmd" and item["nonempty_returns"] for item in observed)
    artifact_hashes = {}
    for filename in ("result.json", "report.md", "native.log", "native-events.jsonl", "stdout.log", "stderr.log",
                     "tasks-and-rubrics.jsonl", "drb-result.jsonl", "grade-summary.json", "grader-native.log",
                     "grader-stdout.log", "grader-stderr.log", "scores_inforecall.csv", "scores_analysis.csv",
                     "scores_presentation.csv", "scores_total.csv", "scores_blocked.csv"):
        path = run_dir / filename
        if path.exists():
            artifact_hashes[filename] = hashlib.sha256(path.read_bytes()).hexdigest()
    receipt = {
        "schema_version": 3, "evidence_class": "local transport integration; native worker and upstream grading attempt",
        "framework": {"name": "gpt-researcher", "release": pins["release"],
                      "commit": pins["commit"], "installed_package_version": version},
        "window": {"started": started, "ended": ended},
        "arm": routes["arm"], "routes": route_metadata(routes), "phases": phases,
        "gateway": gateway,
        "compression": compression,
        "evidence_complete": all(gateway_evidence_complete(gateway[p]) for p in ("worker", "judge"))
            and compression["status"] in ("not_applicable", "observed"),
        "worker_responses_max_corroborated": corroborated,
        "mcp_calls": {"source": "upstream gpt_researcher.mcp.research INFO records",
                      "observed": observed, "qmd_nonempty_return_observed": bool(qmd_seen)},
        "skills": {"listed_at_start": [], "activation_events": [],
                   "status": "SKILL.md loader not found in pinned runtime; no native skill activation claimed"},
        "report_sanity": sanity,
        "evaluation": evaluation,
        "runtime_error_class": runtime_error,
        "source_archive_sha256": pins["source_archive"]["sha256"],
        "dependency_lock_sha256": pins["locks"],
        "private_artifact_sha256": artifact_hashes,
        "execution_complete": evaluation["status"] == "graded" and runtime_error is None and sanity["ready_for_grading"],
        "limitations": [
            "Gateway rows corroborate a time window, not an exclusive per-run attribution.",
            "Fresh keys are supplied per SDK generation; native outer retries are new generation attempts, not deduplicated replays.",
            "Request headers and omitted temperature need independent host wire inspection; allowed DB columns cannot prove them.",
            "DRB-II provides rubric scores, not a global binary quality threshold; execution_complete is not a quality verdict.",
            "Native free-text JSON planning uses upstream json_repair; constrained planner schemas are not available through this recipe.",
            "Upstream grader usage omits failed-attempt consumption; retain gateway/provider observations separately.",
            "No native SKILL.md loading, GPU acceptance, or measured A/B or token-saving comparison is claimed."
        ],
        "sanitization": "No raw report, source bodies, tool arguments, host paths, emails, session IDs or request IDs; unexpected column text redacted."
    }
    (run_dir / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt
