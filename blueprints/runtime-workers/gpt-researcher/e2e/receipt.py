"""Sanitized local integration receipt; no provider calls or state mutations.

SQLite URI mode=ro follows Python sqlite3's URI example. The only SELECT uses
the nine call_logs columns explicitly authorized in the worker brief.
Native tool observations follow gpt_researcher/mcp/research.py:93,123 at v3.7.0.
"""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mcp_proxy import POLICY
from check import check

SQL = """SELECT timestamp, path, status, model, reasoning_effort_requested,
reasoning_effort_upstream, tokens_in, tokens_cache_read, tokens_reasoning
FROM call_logs
WHERE julianday(timestamp) >= julianday(?) AND julianday(timestamp) < julianday(?)
ORDER BY timestamp"""
COLUMNS = ("timestamp", "path", "status", "model", "reasoning_effort_requested",
           "reasoning_effort_upstream", "tokens_in", "tokens_cache_read", "tokens_reasoning")


def gateway_rows(database, started, ended, model):
    # No fallback schema queries, auth stores, or other tables/columns.
    try:
        with sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True, timeout=5) as connection:
            rows = connection.execute(SQL, (started, ended)).fetchall()
    except (OSError, sqlite3.Error):
        return {"status": "unavailable", "rows": [], "error": "read_only_call_logs_query_failed"}
    sanitized = []
    for row in rows:
        item = dict(zip(COLUMNS, row))
        try:
            item["timestamp"] = datetime.fromisoformat(str(item["timestamp"]).replace("Z", "+00:00")).isoformat()
        except ValueError:
            item["timestamp"] = None
        if item["path"] not in ("/v1/responses", "/v1/chat/completions", "/responses", "/chat/completions"):
            item["path"] = "<other-path>"
        if item["model"] not in (model, model.split("/", 1)[-1]):
            item["model"] = "<other-model>"
        for key in ("reasoning_effort_requested", "reasoning_effort_upstream"):
            if item[key] not in (None, "minimal", "low", "medium", "high", "xhigh", "max", "none", "auto"):
                item[key] = "<other-effort>"
        for key in ("status", "tokens_in", "tokens_cache_read", "tokens_reasoning"):
            value = item[key]
            if isinstance(value, str) and value.isdecimal():
                value = int(value)
            item[key] = value if isinstance(value, (int, float)) and value >= 0 else None
        sanitized.append(item)
    return {"status": "observed" if sanitized else "empty", "rows": sanitized,
            "attribution": "time window only; concurrent callers may overlap; no session or request identifiers queried",
            "usage": "raw row counters; no totals or inferred missing counters"}


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


def write_receipt(run_dir, started, ended, model, version, runtime_error=None, database=None):
    recipe = Path(__file__).resolve().parents[1]
    pins = json.loads((recipe / "pins.json").read_text())
    result_path = run_dir / "result.json"
    result = json.loads(result_path.read_text())
    verdict = check(result)  # Re-evaluate frozen oracle, not a wrapper's 'passed' field.
    public_verdict = {key: value for key, value in verdict.items() if key != "fetched_cited_urls"}
    public_verdict["fetched_cited_url_sha256"] = [hashlib.sha256(url.encode()).hexdigest()
                                                 for url in verdict["fetched_cited_urls"]]
    gateway = gateway_rows(database or Path.home() / ".local/share/omniroute/storage.sqlite", started, ended, model)
    observed = native_observations(run_dir / "native.log")
    model_rows = [row for row in gateway["rows"] if row["model"] in (model, model.split("/", 1)[-1])]
    corroborated = any(row["path"] in ("/v1/responses", "/responses")
                       and row["status"] is not None and 200 <= row["status"] < 300
                       and row["reasoning_effort_upstream"] == "max" for row in model_rows)
    qmd_seen = any(item["server"] == "qmd" and item["nonempty_returns"] for item in observed)
    artifact_hashes = {}
    for filename in ("result.json", "report.md", "native.log", "native-events.jsonl", "stdout.log", "stderr.log"):
        path = run_dir / filename
        if path.exists():
            artifact_hashes[filename] = hashlib.sha256(path.read_bytes()).hexdigest()
    receipt = {
        "schema_version": 1, "evidence_class": "local integration; native host run",
        "framework": {"name": "gpt-researcher", "release": pins["release"],
                      "commit": pins["commit"], "installed_package_version": version},
        "window": {"started": started, "ended": ended},
        "gateway": gateway,
        "mcp_calls": {"source": "upstream gpt_researcher.mcp.research INFO records",
                      "observed": observed, "qmd_nonempty_return_observed": bool(qmd_seen)},
        "skills": {"observed": [], "status": "SKILL.md loader not found in pinned runtime; none claimed"},
        "check": public_verdict,
        "runtime_error_class": runtime_error,
        "source_archive_sha256": pins["source_archive"]["sha256"],
        "dependency_lock_sha256": pins["locks"],
        "private_artifact_sha256": artifact_hashes,
        "passed": verdict["passed"] and runtime_error is None and corroborated and bool(qmd_seen),
        "limitations": [
            "Gateway rows corroborate a time window, not an exclusive per-run attribution.",
            "Fresh per-logical-call Idempotency-Key is not provided by static upstream JSON configuration.",
            "Request headers and omitted temperature need independent host wire inspection; allowed DB columns cannot prove them.",
            "No native SKILL.md loading, GPU acceptance, or measured token-saving comparison is claimed."
        ],
        "sanitization": "No raw report, source bodies, tool arguments, host paths, emails, session IDs or request IDs; unexpected column text redacted."
    }
    (run_dir / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


if __name__ == "__main__":
    # Shell timeout/startup failure fallback. Never turn a missing run into a pass.
    run_dir, model, exit_status = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
    ended = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    start_file = run_dir / "window-start.txt"
    started = start_file.read_text() if start_file.exists() else ended
    if not (run_dir / "result.json").exists():
        (run_dir / "result.json").write_text('{"report":"","sources":[]}\n')
    write_receipt(run_dir, started, ended, model, None, "ProcessExit" + str(int(exit_status)))
    print("Preserved failed attempt receipt; native execution did not finalize.")
