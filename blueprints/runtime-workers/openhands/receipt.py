"""Sanitized evidence from the official grader report, host files and gateway rows.

Uses Python's sqlite3 URI mode=ro + query_only. The only SQL SELECT reads the
authorized usage/effort columns from call_logs. Correlation IDs may be used
in memory for matching, but are never returned in receipts. SDK trace, skill,
MCP and version fields are not_collected (NOT_COLLECTED_REASON).
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat

from recipe import HERE, arm_config, read_json, tool_filter
from e2e.check import read_report


# host.run_probe's receipt (plan E1); the summary copies counts and booleans only.
PROBE_MECHANISM = "internal-isolated+nginx-v1-allowlist"
PROBE_FIELDS = {
    "p0": ("requests", "observed", "matched", "passed"),
    "p1": ("requests", "observed", "matched", "passed"),
    "p2": ("control_connected", "connects", "observed", "connected", "errors", "off_subnet",
           "off_subnet_unreachable", "udp_answered", "udp_errors", "dns", "dns_matched", "dns_errors",
           "ipv6_non_loopback", "ipv6_link_local", "ipv6_loopback", "routes_available", "routes",
           "default_routes", "gateway_routes", "passed"),
    "targets": ("addresses", "ports", "pairs", "excluded"),
}
COLUMNS = (
    "timestamp", "path", "status", "model", "reasoning_effort_requested",
    "reasoning_effort_upstream", "tokens_in", "tokens_cache_read", "tokens_reasoning", "correlation_id",
)
EFFORTS = {"none", "minimal", "low", "medium", "high", "xhigh", "max", "auto"}
AGENT_TERMINATIONS = {"finished", "error", "stuck", "max_iterations_reached"}
NOT_COLLECTED = "not_collected"
NOT_COLLECTED_REASON = (
    "The model terminal runs under the agent-server's UID, which can write both /run-output "
    "(host.py model_visible on the worker directory) and the server persistence mounted at "
    "/state/server. The server's event API reads that same store and rebuilds its index from "
    "disk (SDK@fcc102a event_service.py:420-431, event_store.py:144-169,320-362). No event "
    "source outside the model's write reach exists yet, so trace, skill, MCP and version "
    "fields are not read.")


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


def summary_value(value):
    """Numbers, booleans, errno-name counts and port lists only; anything else becomes None."""
    if value is None or type(value) in (bool, int):
        return value
    if isinstance(value, dict):
        return {key: count for key, count in value.items()
                if isinstance(key, str) and re.fullmatch(r"[A-Za-z_<>]{1,32}", key) and type(count) is int}
    if isinstance(value, list) and all(type(item) is int for item in value):
        return value
    return None


def isolation_summary(result):
    """The host-written probe receipt without its network/container IDs or run id."""
    try:
        probe = json.loads(read_bounded(Path(result) / "isolation-probe.json", limit=1024 * 1024))
    except (OSError, ValueError):
        return {"status": "absent"}
    if not isinstance(probe, dict):
        return {"status": "unreadable"}
    try:
        time_value(probe.get("verified_at"))
        verified_at = probe["verified_at"] if isinstance(probe["verified_at"], str) else None
    except (ValueError, TypeError, OverflowError, OSError):
        verified_at = None
    codes = probe.get("exit_codes") if isinstance(probe.get("exit_codes"), dict) else {}
    summary = {"status": "observed",
               "mechanism": PROBE_MECHANISM if probe.get("mechanism") == PROBE_MECHANISM else "<other>",
               "verified_at": verified_at, "passed": probe.get("passed") is True,
               "exit_codes": {role: summary_value(codes.get(role)) for role in ("gw", "int")}}
    for section, keys in PROBE_FIELDS.items():
        values = probe.get(section) if isinstance(probe.get(section), dict) else {}
        summary[section] = {key: summary_value(values[key]) for key in keys if key in values}
    return summary


def independent_observations(result, window, pins):
    """Read an external collector's host-only evidence; never SDK writable state.

    This is a receipt interface, not an independent collector implementation.
    CPython os.stat/open and SHA256 provide owner/type/byte checks, not truth.
    The collector must have a separate trusted native execution/observation
    source; host polling of the SDK's model-writable event API is insufficient.
    No fixture or copied worker summary is accepted by this interface.
    """
    root = Path(result) / "observer"
    try:
        def private_read(name):
            path = root / name
            info = path.lstat()
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                    or stat.S_IMODE(info.st_mode) != 0o600):
                raise ValueError("independent_observer_file_must_be_private")
            return read_bounded(path)
        metadata = json.loads(private_read("receipt.json"))
        expected = {"schema_version": 1, "evidence_class": "independent_native_observation",
                    "source_kind": "isolated_native_executor", "worker_write_reach_excluded": True,
                    "run_id": window.get("run_id"), "arm": window.get("arm", "control"),
                    "profile": window.get("profile", "coding"), "source_commit": pins["commit"],
                    "image": pins["image"]["ref"], "started_at": window.get("started_at"),
                    "finished_at": window.get("finished_at")}
        if any(metadata.get(key) != value for key, value in expected.items()):
            raise ValueError("independent_observer_input_mismatch")
        source = metadata.get("collector_source", {})
        if (not isinstance(source, dict) or not re.fullmatch(r"https://github.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", source.get("repository", ""))
                or not re.fullmatch(r"[a-f0-9]{40}", source.get("commit", "")) or not source.get("file")):
            raise ValueError("independent_observer_requires_pinned_native_source")
        captured = {}
        for name in ("startup.json", "events.jsonl"):
            content = private_read(name)
            if metadata.get("artifact_sha256", {}).get(name) != hashlib.sha256(content.encode()).hexdigest():
                raise ValueError("independent_observer_artifact_mismatch")
            captured[name] = content
        startup = json.loads(captured["startup.json"])
        versions = startup.get("versions", {})
        if versions != {name: pins["version"] for name in ("openhands-sdk", "openhands-tools")}:
            raise ValueError("independently_observed_version_mismatch")
        # /run-input is a host-created read-only mount. Its discovery manifest
        # was frozen before the first model call; it is not model output.
        expected_skills = read_json(Path(result) / "input/skills.json")["names"]
        from recipe import profile_skills, task_profile
        profile = task_profile({"OPENHANDS_PROFILE": window.get("profile", "coding")})[1]
        manifest = read_json(Path(result) / "input/skills.json")
        selected = sorted(profile_skills({name: None for name in expected_skills}, manifest, profile))
        if startup.get("listed_skills") != selected:
            raise ValueError("independently_observed_skill_listing_mismatch")
        events = [json.loads(line) for line in captured["events.jsonl"].splitlines() if line.strip()]
        observed = observations(events, selected)
        transport = metadata.get("transport", {})
        transport_verified = (transport == {"api_mode": "responses", "reasoning_effort": "max",
                                            "sampling_parameters_present": False,
                                            "streaming_observed": True, "tool_round_trip_observed": True})
        return {"status": "observed", "observed_versions": versions,
                "skills_listed_at_start": selected, "skill_listing_matches_manifest": True,
                **observed, "transport_verified": transport_verified,
                "collector_source": {key: source[key] for key in ("repository", "commit", "file")},
                "scope_note": "External collector provenance is declared and must be independently reviewed; hashes check byte binding only."}
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return {"status": NOT_COLLECTED}


def create_receipt(result, database=None):
    result = Path(result)
    window = read_json(result / "window.json")
    checked = read_json(result / "check.json")
    # F17: nothing under result/worker or result/server is read (NOT_COLLECTED_REASON).
    selection = arm_config(window.get("arm", "control"), window.get("requested_model", window.get("model")),
                           window.get("base_url"), window.get("compression_combo"))
    db = database or gateway_database(selection["arm"])
    rows, db_status = [], "unavailable"
    # No run-id match (repair R5, checked against source). At OmniRoute@045aa81f3
    # (20128) and @dd6e9607e (20129), whose files here are identical, /v1/responses
    # hands handleChat a fresh randomUUID (src/app/api/v1/responses/route.ts:193,213;
    # src/shared/utils/requestId.ts:100-102; src/sse/handlers/chat.ts:436), and
    # call_logs.correlation_id stores it (open-sse/handlers/chatCore/attemptLogging.ts:611;
    # src/lib/usage/callLogs.ts:713,786,801). Only /v1/chat/completions keeps a
    # caller X-Correlation-Id (route.ts:292-322). arm_config fixes /v1/responses,
    # so matching the proxy's run id would drop every row and report false zeros.
    try:
        rows = gateway_rows(db, window["started_at"], window["finished_at"])
        db_status = "observed" if rows else "empty_window"
    except (OSError, sqlite3.Error, ValueError, TypeError):
        pass  # Unknown usage is not zero usage. No raw exception text is exported.
    pins = read_json(HERE / "pins.json")
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
    termination = window.get("agent_termination")
    usage = summarize_gateway(rows, selection)
    independent = independent_observations(result, window, pins)
    isolation = isolation_summary(result)
    def removals(*patterns):
        found = []
        for path in sorted(path for pattern in patterns for path in result.glob(pattern)):
            try:
                found.append(read_json(path).get("confirmed_removed") is True)
            except (OSError, ValueError, AttributeError):
                found.append(False)
        return {"attempts": len(found), "confirmed_removed": sum(found), "complete": bool(found) and all(found)}
    containers = removals("*.log.cleanup.json", "probes/*/*.log.cleanup.json")
    networks = removals("network-*.cleanup.json")
    complete = (task_passed and independent["status"] == "observed"
                and independent.get("transport_verified") is True
                and bool(independent.get("skills_observed"))
                and bool(independent.get("mcp_calls_observed"))
                and usage["successful_rows"] > 0 and usage["effort_verified"] and usage["totals"] is not None
                and isolation.get("passed") is True and containers["complete"] and networks["complete"])
    return {
        "schema_version": 7, "evidence_class": "SDK inference adapter with official SWE-bench grading",
        "profile": window.get("profile", "coding"),
        **{k: selection[k] for k in ("arm", "base_url", "gateway_upstream", "requested_model", "gateway_model",
                                     "gateway_path", "compression_combo")},
        "header_names": window.get("header_names", sorted(selection["headers"])),
        "framework": "OpenHands software-agent-sdk", "expected_version": pins["version"],
        "observed_versions": independent.get("observed_versions", NOT_COLLECTED),
        "image": pins["image"]["ref"], "source_commit": pins["commit"],
        "window": {key: window[key] for key in ("started_at", "finished_at")},
        "worker_exit_code": window.get("worker_exit_code"),
        "agent_termination": termination if termination in AGENT_TERMINATIONS else None,
        "agent_termination_basis": ("agent-server REST status and latest ConversationErrorEvent; the server shares "
                                    "the model terminal's UID and store, so this selects exit 1 or 3 only"),
        "failure_stage": window.get("failure_stage") if window.get("failure_stage") in {"preflight", "prepare", "skills", "qmd_setup", "agent", "export", "grader", "start", "probe", "wait", "result", "deadline"} else None,
        "task_passed": task_passed,
        # The terminal shares the SDK's UID and writable persistence. Source:
        # SDK@fcc102a tools/terminal/terminal/subprocess_terminal.py:157-170.
        # Without a separate observer nothing can prove skill use or SDK identity.
        "evidence_complete": bool(complete),
        "independent_trace_required": True,
        "not_collected_reason": NOT_COLLECTED_REASON if independent["status"] != "observed" else None,
        "skills_listed_at_start": independent.get("skills_listed_at_start", NOT_COLLECTED),
        "skill_listing_matches_manifest": independent.get("skill_listing_matches_manifest", NOT_COLLECTED),
        # host.cleanup_container and host.cleanup_network records, counted
        # separately; probe containers log beside their output directories.
        "container_cleanup": containers,
        "network_cleanup": networks,
        "isolation": isolation,
        "gateway": {
            "read_mode": "read_only", "columns": list(COLUMNS), "status": db_status, **usage,
            "entry_port": selection["gateway_port"],
            "attribution": ("Time window + model + path at the arm entry gateway. The proxy fixes X-Correlation-Id "
                            "to the run id, but at the pinned OmniRoute builds /v1/responses logs a gateway-generated "
                            "correlation ID instead, so rows are not matched by run id and concurrent callers of the "
                            "same model and path are included; the recipe lock cannot exclude them."),
            "usage_note": "Sum each entry row once, including failed calls; never add 20128 to 20129. Cache-read is an input subset. Missing counters keep totals null.",
        },
        "compression": window.get("compression", {"delta": None, "status": "unavailable"}),
        "trace_status": independent["status"], "mcp_calls_observed": independent.get("mcp_calls_observed", NOT_COLLECTED),
        "mcp_errors_observed": independent.get("mcp_errors_observed", NOT_COLLECTED),
        "skills_observed": independent.get("skills_observed", NOT_COLLECTED),
        "independent_observer": {key: value for key, value in independent.items()
                                 if key in {"status", "collector_source", "transport_verified", "scope_note"}},
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
