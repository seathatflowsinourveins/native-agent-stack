#!/usr/bin/env python3
"""Sanitized independent observation; SQLite mode=ro reads only approved fields.

References: Python 3.12 sqlite3 URI mode=ro; user's gateway column contract;
docs/acceptance-evidence-policy.md. No schema/table discovery, prompts or IDs.
"""
import argparse
import hashlib
import json
import re
import sqlite3
import sys
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from grade import observation

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from worker import arm_settings

COLUMNS = ("timestamp", "path", "status", "model", "reasoning_effort_requested",
           "reasoning_effort_upstream", "tokens_in", "tokens_cache_read", "tokens_reasoning", "correlation_id")
EFFORTS = {"none", "minimal", "low", "medium", "high", "xhigh", "max"}
PATHS = {"/v1/chat/completions", "/v1/responses", "/chat/completions", "/responses"}


def timestamp(value):
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000 if value > 100_000_000_000 else value, timezone.utc).isoformat()
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return (parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)).astimezone(timezone.utc).isoformat()


def gateway_rows(database, start, end, *, models=None, correlations=None):
    try:
        if not database.is_file():
            raise FileNotFoundError("entry gateway database not present")
        # sqlite3's transaction context does not close the connection; the
        # Python 3.12 sqlite3 context-manager docs prescribe closing for that.
        with closing(sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True, timeout=5)) as db:
            # Common requirements sections 2 + 3: usage, correlation and the
            # two conditional effort fields only. IDs are never exported.
            def authorize(action, table, column, *_):
                if action == sqlite3.SQLITE_READ and (table != "call_logs" or column not in COLUMNS):
                    return sqlite3.SQLITE_DENY
                return sqlite3.SQLITE_OK
            db.set_authorizer(authorize)
            sql = "SELECT " + ", ".join(COLUMNS) + """ FROM call_logs
                WHERE CASE WHEN typeof(timestamp) IN ('integer', 'real') THEN
                    CASE WHEN timestamp > 100000000000 THEN timestamp / 1000.0 ELSE timestamp END
                ELSE (julianday(timestamp) - 2440587.5) * 86400 END BETWEEN ? AND ?"""
            bounds = [datetime.fromisoformat(v.replace("Z", "+00:00")).timestamp() for v in (start, end)]
            for column, values in (("path", sorted(PATHS)), ("model", models), ("correlation_id", correlations)):
                if values:
                    sql += f" AND {column} IN ({','.join('?' for _ in values)})"
                    bounds.extend(values)
            sql += " ORDER BY timestamp"
            rows = [dict(zip(COLUMNS, row)) for row in db.execute(sql, bounds)]
        for row in rows:
            row.pop("correlation_id")
            row["timestamp"] = timestamp(row["timestamp"])
            row["path"] = row["path"] if row["path"] in PATHS else "[redacted]"
            model = row["model"]
            row["model"] = model if isinstance(model, str) and re.fullmatch(r"(?:(?:cx|sharedgw)/)?gpt-6(?:-[A-Za-z0-9]+)+", model) else "[redacted]"
            status = row["status"]
            row["status"] = status if str(status) in {"success", "error", "completed", "failed"} or re.fullmatch(r"[1-5][0-9]{2}", str(status)) else "[redacted]"
            for name in ("reasoning_effort_requested", "reasoning_effort_upstream"):
                row[name] = row[name] if row[name] in EFFORTS else None
            for name in ("tokens_in", "tokens_cache_read", "tokens_reasoning"):
                row[name] = row[name] if type(row[name]) is int and row[name] >= 0 else None
        return {"status": "observed" if rows else "no_rows", "rows": rows,
                "attribution": ("entry gateway correlation + window + model + path" if correlations else
                                "entry gateway window + model + path; concurrent traffic may be included"),
                "correlation_capture_complete": bool(correlations)}
    except (OSError, sqlite3.Error, ValueError, TypeError, OverflowError) as exc:
        return {"status": "unavailable", "error_class": type(exc).__name__, "rows": []}


def effort_observation(rows, expected):
    """OmniRoute@a58000c7 src/lib/usage/callLogs.ts:642-653.

    Null effort is not evidence of an omitted request. Reasoning-bearing rows
    need both observations; rows without reasoning are counted separately.
    """
    reasoning = [r for r in rows if (r.get("tokens_reasoning") or 0) > 0]
    unknown = sum(r.get("tokens_reasoning") is None for r in rows)
    return {"expected": expected, "reasoning_rows": reasoning,
            "no_returned_reasoning_count": sum(r.get("tokens_reasoning") == 0 for r in rows),
            "unknown_reasoning_count": unknown,
            "passed": bool(rows) and not unknown and all(
                r["reasoning_effort_requested"] == expected and r["reasoning_effort_upstream"] == expected
                for r in reasoning)}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def compression_delta(snapshots):
    # OmniRoute@a58000c7 src/lib/db/compressionAnalytics.ts:613-617.
    keys = ("totalRequests", "totalTokensSaved")
    try:
        before, after = ({k: snapshots[side][k] for k in keys} for side in ("before", "after"))
        if any(type(v) is not int or v < 0 for values in (before, after) for v in values.values()):
            raise ValueError("invalid cumulative counter")
        delta = {k: after[k] - before[k] for k in keys}
        if any(v < 0 for v in delta.values()):
            raise ValueError("counter reset")
        return {"status": "observed", "delta": delta,
                "scope": "20129 analytics over run; may include concurrent traffic; never added to usage"}
    except (KeyError, TypeError, ValueError):
        return {"status": "unavailable", "delta": None}


def exit_code(receipt):
    if receipt.get("setup_error_class"):
        return 2
    if any(a["grader"].get("status") == "observed" and not a["grader"]["passed"] for a in receipt.get("arms", [])):
        return 3
    return 0 if receipt.get("passed") else 4


def make_receipt(directory, databases=None, correlations=None):
    metadata = json.loads((directory / "run.json").read_text())
    config = json.loads((ROOT / "config/worker.json").read_text())
    databases = databases or {"control": Path.home() / ".local/share/omniroute/storage.sqlite",
                              "engines-on": Path.home() / ".local/share/omniroute-fw/storage.sqlite",
                              "comparison": Path.home() / ".local/share/omniroute/storage.sqlite"}
    correlations = correlations or {}
    native_log = directory / "container.log"
    log = native_log.read_text(errors="replace") if native_log.exists() else ""
    route_calls = len(re.findall(r'POST /md(?:\s|\?)', log))
    mcp_requests = len(re.findall(r"Processing request of type CallToolRequest", log))
    arms = []
    for arm in metadata.get("selected_arms", config["e2e"]["arms"]):
        info = metadata["arms"].get(arm)
        if info is None:
            arms.append({"arm": arm, "grader": {"passed": False, "status": "not_run"},
                         "gateway": {"status": "not_run", "rows": []}})
            continue
        route = arm_settings(config, arm)
        ids = correlations.get(arm, [])
        complete = len(ids) == len(config["e2e"]["pages"]) and all(ids) and len(set(ids)) == len(ids)
        model = info["model"]
        models = [model, model.split("/", 1)[-1]]
        gateway = gateway_rows(databases[arm], info["start"], info["end"], models=models,
                               correlations=ids if complete else None)
        effort = effort_observation(gateway["rows"], route["expected_effort"])
        relevant = gateway["rows"]
        routing = len(relevant) == len(config["e2e"]["pages"]) and effort["passed"] and all(
            str(row["status"]) in {"200", "success", "completed"} for row in relevant)
        grader = observation(directory / arm)
        arms.append({"arm": arm, "base_url": route["base_url"], "model": model,
                     "gateway_port": 20129 if arm == "engines-on" else 20128,
                     "header_names": ["x-omniroute-session", "Idempotency-Key"] +
                         (["x-omniroute-compression"] if arm == "engines-on" else []),
                     "effort": effort, "grader": grader, "routing_observed_in_window": routing,
                     "gateway": gateway, "framework_log_sha256": digest(directory / arm / "native.log"),
                     "result_sha256": digest(directory / arm / "result.json"),
                     "error_class": info.get("error_class") if re.fullmatch(r"[A-Za-z]+(?:Error|Exception)", info.get("error_class", "")) else None,
                     "content_measurements": safe_measurements(info.get("measurements", []))})
    required_probes = ("auth_/mcp/sse", "auth_/crawl", "api_fit", "sse")
    probes = metadata.get("probes", {})
    probe_checks = {key: probes.get(key) is True for key in required_probes}
    controls = {name: observation(directory / "controls" / name)
                for name in ("known-pass", "known-fail", "malformed-output")}
    controls_passed = all(controls[name]["status"] == "observed"
                          and controls[name].get("exit_code") == code
                          and controls[name]["passed"] is (code == 0)
                          for name, code in (("known-pass", 0), ("known-fail", 100), ("malformed-output", 100)))
    passed = (all(a["grader"]["passed"] and a.get("routing_observed_in_window", False) for a in arms)
              and all(probe_checks.values()) and route_calls >= 1 and mcp_requests >= 1
              and metadata.get("cleanup_passed") is True and controls_passed)
    compression = compression_delta(metadata.get("compression", {})) if "engines-on" in metadata["arms"] else {"status": "not_applicable", "delta": None}
    passed = passed and compression["status"] != "unavailable" and not metadata.get("setup_error_class")
    return {
        "schema_version": 3, "compression": compression,
        "setup_error_class": metadata.get("setup_error_class"), "framework": "crawl4ai", "framework_version": metadata.get("framework_version"),
        "expected_version": "0.9.4", "evidence_class": "local integration on synthetic frozen fixtures",
        "passed": passed and metadata.get("framework_version") == "0.9.4",
        "arms": arms, "container_checks": probe_checks, "cleanup_passed": metadata.get("cleanup_passed", False),
        "grader_controls": controls, "grader_controls_passed": controls_passed,
        "mcp_observation": {
            "source": "framework container stdout/stderr bounded by this run start", "log_sha256": digest(native_log),
            "native_call_tool_request_count": mcp_requests,
            "native_post_md_count": route_calls,
            "tool_names_observed": [],
            "tool_names_inferred_from_routes": [],
            "limitation": "v0.9.4 does not log MCP tool names; POST /md counts direct REST and MCP traffic together; no MCP tool identity is inferred",
        },
        "skills_observation": {"names_at_start": [], "events": [],
                               "status": "not applicable: no native SKILL.md loader or inventory API found in reviewed v0.9.4 sources; no activation claimed"},
        "frozen_artifacts": {str(path.relative_to(ROOT)): digest(path) for path in sorted((ROOT / "e2e/fixtures").glob("*.html"))},
        "grader": {"name": "promptfoo", "version": "0.123.1", "mode": "standalone unchanged is-json and equals assertions",
                   "assertions_sha256": digest(ROOT / "e2e/assertions.json")},
        "transport_sha256": digest(ROOT / "e2e/check.py"), "schema_sha256": digest(ROOT / "e2e/schema.json"),
        "oracle_expected_sha256": digest(ROOT / "e2e/expected.json"), "pins_sha256": digest(ROOT / "pins.json"),
        "recipe_artifacts": {name: digest(ROOT / name) for name in (
            "worker.py", "requirements.lock", "browser-artifacts.json", "config/worker.json",
            "config/compose.yaml", "config/server.yml", "config/supervisord.conf", "config/logging.ini",
            "container-entrypoint.sh", "e2e/run.py", "e2e/mcp_probe.py", "e2e/receipt.py", "e2e/grade.py",
        )},
        "sanitization": "No raw logs, paths, credentials, emails, session/request identifiers or unapproved DB columns; unknown counters stay null",
        "qualification": "A passing comparison check qualifies only this frozen extraction contract; no global model substitution",
        "routing_gate": "Three successful entry-gateway rows per arm; reasoning-bearing rows require requested/upstream expected effort; unknown or overlapping evidence fails closed",
    }


def safe_measurements(measurements):
    output = []
    for item in measurements:
        if item.get("page") not in {"beacon.html", "flask.html", "lamp.html"}:
            continue
        safe = {"page": item["page"]}
        for name in ("raw_markdown_bytes", "fit_markdown_bytes", "estimated_chunk_tokens"):
            value = item.get(name)
            safe[name] = value if type(value) is int and value >= 0 else None
        value = item.get("fit_sha256", "")
        safe["fit_sha256"] = value if isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) else None
        output.append(safe)
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--db", type=Path, default=Path.home() / ".local/share/omniroute/storage.sqlite")
    parser.add_argument("--engines-db", type=Path, default=Path.home() / ".local/share/omniroute-fw/storage.sqlite")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = make_receipt(args.run_dir, {"control": args.db, "comparison": args.db, "engines-on": args.engines_db})
    args.output.write_text(json.dumps(receipt, indent=2) + "\n")
    print("PASS: host receipt" if receipt["passed"] else "FAIL: host receipt contains incomplete or failed gates")
    return exit_code(receipt)


if __name__ == "__main__":
    raise SystemExit(main())
