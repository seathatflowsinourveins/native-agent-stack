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
from datetime import datetime, timezone
from pathlib import Path

from check import check

ROOT = Path(__file__).resolve().parents[1]
COLUMNS = ("timestamp", "path", "status", "model", "reasoning_effort_requested",
           "reasoning_effort_upstream", "tokens_in", "tokens_cache_read", "tokens_reasoning")
EFFORTS = {"none", "minimal", "low", "medium", "high", "xhigh", "max"}
PATHS = {"/v1/chat/completions", "/v1/responses", "/chat/completions", "/responses"}


def timestamp(value):
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000 if value > 100_000_000_000 else value, timezone.utc).isoformat()
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return (parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)).astimezone(timezone.utc).isoformat()


def gateway_rows(database, start, end):
    try:
        with sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True, timeout=5) as db:
            # Only call_logs and the nine named columns may be read, even after future edits.
            def authorize(action, table, column, *_):
                if action == sqlite3.SQLITE_READ and (table != "call_logs" or column not in COLUMNS):
                    return sqlite3.SQLITE_DENY
                return sqlite3.SQLITE_OK
            db.set_authorizer(authorize)
            sql = "SELECT " + ", ".join(COLUMNS) + """ FROM call_logs
                WHERE CASE WHEN typeof(timestamp) IN ('integer', 'real') THEN
                    CASE WHEN timestamp > 100000000000 THEN timestamp / 1000.0 ELSE timestamp END
                ELSE (julianday(timestamp) - 2440587.5) * 86400 END BETWEEN ? AND ?
                ORDER BY timestamp"""
            bounds = tuple(datetime.fromisoformat(v.replace("Z", "+00:00")).timestamp() for v in (start, end))
            rows = [dict(zip(COLUMNS, row)) for row in db.execute(sql, bounds)]
        for row in rows:
            row["timestamp"] = timestamp(row["timestamp"])
            row["path"] = row["path"] if row["path"] in PATHS else "[redacted]"
            model = row["model"]
            row["model"] = model if isinstance(model, str) and re.fullmatch(r"(?:cx/)?gpt-[0-9][A-Za-z0-9._-]*", model) else "[redacted]"
            status = row["status"]
            row["status"] = status if str(status) in {"success", "error", "completed", "failed"} or re.fullmatch(r"[1-5][0-9]{2}", str(status)) else "[redacted]"
            for name in ("reasoning_effort_requested", "reasoning_effort_upstream"):
                row[name] = row[name] if row[name] in EFFORTS else None
            for name in ("tokens_in", "tokens_cache_read", "tokens_reasoning"):
                row[name] = row[name] if type(row[name]) is int and row[name] >= 0 else None
        return {"status": "observed" if rows else "no_rows", "rows": rows,
                "attribution": "run window only; concurrent traffic may be included; no totals attributed to this worker"}
    except (OSError, sqlite3.Error, ValueError, TypeError, OverflowError) as exc:
        return {"status": "unavailable", "error_class": type(exc).__name__, "rows": []}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def make_receipt(directory, database):
    metadata = json.loads((directory / "run.json").read_text())
    native_log = directory / "container.log"
    log = native_log.read_text(errors="replace") if native_log.exists() else ""
    route_calls = len(re.findall(r'POST /md(?:\s|\?)', log))
    mcp_requests = len(re.findall(r"Processing request of type CallToolRequest", log))
    arms = []
    for arm in ("primary", "comparison"):
        info = metadata["arms"].get(arm)
        if info is None:
            arms.append({"arm": arm, "check_passed": False, "gateway": {"status": "not_run", "rows": []}})
            continue
        gateway = gateway_rows(database, info["start"], info["end"])
        effort = "max" if arm == "primary" else "medium"
        # A window observation corroborates routing, but cannot prove exclusive attribution.
        model = info["model"]
        acceptable_models = {model, model.removeprefix("cx/"), "cx/" + model.removeprefix("cx/")}
        relevant = [row for row in gateway["rows"] if row["model"] in acceptable_models]
        routing = len(relevant) == 3 and all(
            row["reasoning_effort_upstream"] == effort and row["path"] in PATHS
            and str(row["status"]) in {"200", "success", "completed"} for row in relevant)
        passed = check(directory / arm / "result.json")
        arms.append({"arm": arm, "check_passed": passed, "routing_observed_in_window": routing,
                     "gateway": gateway, "framework_log_sha256": digest(directory / arm / "native.log"),
                     "result_sha256": digest(directory / arm / "result.json"),
                     "error_class": info.get("error_class") if re.fullmatch(r"[A-Za-z]+(?:Error|Exception)", info.get("error_class", "")) else None,
                     "content_measurements": safe_measurements(info.get("measurements", []))})
    required_probes = ("auth_/mcp/sse", "auth_/mcp/ws", "auth_/crawl", "api_fit", "sse", "websocket")
    probes = metadata.get("probes", {})
    probe_checks = {key: probes.get(key) is True for key in required_probes}
    passed = (all(a["check_passed"] and a.get("routing_observed_in_window", False) for a in arms)
              and all(probe_checks.values()) and route_calls >= 1 and mcp_requests >= 1
              and metadata.get("cleanup_passed") is True)
    return {
        "schema_version": 1, "framework": "crawl4ai", "framework_version": metadata.get("framework_version"),
        "expected_version": "0.9.4", "evidence_class": "local integration on synthetic frozen fixtures",
        "passed": passed and metadata.get("framework_version") == "0.9.4",
        "arms": arms, "container_checks": probe_checks, "cleanup_passed": metadata.get("cleanup_passed", False),
        "mcp_observation": {
            "source": "framework container stdout/stderr bounded by this run start", "log_sha256": digest(native_log),
            "native_call_tool_request_count": mcp_requests,
            "native_post_md_count": route_calls,
            "tool_names_observed": [],
            "tool_names_inferred_from_routes": ["md"] if route_calls else [],
            "limitation": "v0.9.4 does not log MCP tool names; API route inference and client transport checks are distinct",
        },
        "skills_observation": {"names": [], "status": "none observed; no native skill loader found in reviewed sources"},
        "frozen_artifacts": {str(path.relative_to(ROOT)): digest(path) for path in sorted((ROOT / "e2e/fixtures").glob("*.html"))},
        "oracle_sha256": digest(ROOT / "e2e/check.py"), "schema_sha256": digest(ROOT / "e2e/schema.json"),
        "oracle_expected_sha256": digest(ROOT / "e2e/expected.json"), "pins_sha256": digest(ROOT / "pins.json"),
        "recipe_artifacts": {name: digest(ROOT / name) for name in (
            "worker.py", "requirements.lock", "browser-artifacts.json", "config/worker.json",
            "config/compose.yaml", "config/server.yml", "config/supervisord.conf", "config/logging.ini",
            "container-entrypoint.sh", "e2e/run.py", "e2e/mcp_probe.py", "e2e/receipt.py",
        )},
        "sanitization": "No raw logs, paths, credentials, emails, session/request identifiers or unapproved DB columns; unknown counters stay null",
        "qualification": "A passing comparison check qualifies only this frozen extraction contract; no global model substitution",
        "routing_gate": "Exactly three successful matching-model rows with the expected effort per arm; extra retries or overlapping same-model traffic require review, never silent attribution",
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
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = make_receipt(args.run_dir, args.db)
    args.output.write_text(json.dumps(receipt, indent=2) + "\n")
    print("PASS: host receipt" if receipt["passed"] else "FAIL: host receipt contains incomplete or failed gates")
    return 0 if receipt["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
