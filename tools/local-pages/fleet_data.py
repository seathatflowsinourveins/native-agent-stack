"""Read the prescribed fleet sources and return a small, whitelisted view.

Collection stays with fleet_block.py and the installed gh CLI. The cache stores
sanitized run fields only and must be placed outside the HTTP serving root.
"""

from __future__ import annotations

from datetime import datetime, timezone
import fcntl
import json
import math
from pathlib import Path
import re
import subprocess
import time
from typing import Any, Callable


ACTIONS_TTL_SECONDS = 600
REPO = "seathatflowsinourveins/native-agent-stack"
MAX_SOURCE_BYTES = 2_000_000
RUN_FIELDS = "workflowName,status,conclusion,databaseId,startedAt,updatedAt,url"
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:/+-]{0,99}\Z")
_OPAQUE = re.compile(r"[A-Za-z0-9_-]{32,}|(?:sk-|gh[pousr]_|github_pat_|Bearer\s)", re.I)
_POOL_LABEL = re.compile(
    r"(?:position [1-9][0-9]{0,2}|fresh\((?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d\)"
    r"|(?:\d{4}-)?\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)\Z"
)
_VERSION = re.compile(r"\d+\.\d+\.\d+(?:[-a-zA-Z0-9.]*)?\Z")
_AI_INVOCATION = re.compile(
    r"(?m)^\s*(?:-\s*)?uses:\s*[^#\n]*(?:claude-code-action|codex-action|ai-inference)"
    r"|\bgh\s+models\s+run\b|\bcodex\s+exec\b|\bclaude\s+(?:-p|--print)\b"
    r"|inference\.models\.github",
)
_STATUSES = {
    "active", "running", "idle", "listening", "blocked", "parked", "stopped",
    "done", "complete", "completed", "closed", "waiting", "queued", "pending",
    "in_progress", "requested", "waiting_on_owner", "online", "offline",
    "unknown", "error", "busy", "exited", "dead",
}
_CONCLUSIONS = {
    "success", "failure", "neutral", "cancelled", "skipped", "timed_out",
    "action_required", "startup_failure", "stale",
}


def _utc(epoch: float | None = None) -> str:
    return datetime.fromtimestamp(time.time() if epoch is None else epoch, timezone.utc).isoformat().replace("+00:00", "Z")


def _stamp(value: Any) -> str | None:
    if not isinstance(value, str) or len(value) > 40:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z") if parsed.tzinfo else None
    except ValueError:
        return None


def _identifier(value: Any) -> str | None:
    return value if isinstance(value, str) and _IDENTIFIER.fullmatch(value) and not _OPAQUE.search(value) else None


def _text(value: Any, limit: int = 160) -> str | None:
    if not isinstance(value, str) or not value or len(value) > limit or "@" in value or _OPAQUE.search(value):
        return None
    return value if re.fullmatch(r"[A-Za-z0-9 .,;:()_/'+-]+", value) else None


def _number(value: Any, maximum: float | None = None) -> int | float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        return None
    return value if maximum is None or value <= maximum else None


def _count(value: Any) -> int | None:
    number = _number(value)
    return int(number) if number is not None and int(number) == number else None


def _status(value: Any) -> str | None:
    return value if isinstance(value, str) and value in _STATUSES else None


def _read_json(path: Path) -> dict[str, Any]:
    try:
        if path.stat().st_size > MAX_SOURCE_BYTES:
            return {}
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def _mtime(path: Path) -> str | None:
    try:
        return _utc(path.stat().st_mtime)
    except OSError:
        return None


def _names(value: Any) -> list[str] | None:
    if not isinstance(value, list):
        return None
    return [name for row in value[:200] if (name := _identifier(row.get("name") if isinstance(row, dict) else row))]


def _models(value: Any) -> dict[str, int | None] | list[str] | None:
    if isinstance(value, dict):
        return {model: _count(count) for key, count in list(value.items())[:50] if (model := _identifier(key))}
    return _names(value)


def _tiers(raw: dict[str, Any]) -> dict[str, Any]:
    parking = raw.get("parking") if isinstance(raw.get("parking"), dict) else {}
    version = raw.get("codex_version") if isinstance(raw.get("codex_version"), dict) else {}
    holds = version.get("hold") if isinstance(version.get("hold"), dict) else {}
    until = version.get("hold_until") if isinstance(version.get("hold_until"), dict) else {}
    return {
        "read_utc": _stamp(raw.get("updated_utc")),
        "default": _identifier(raw.get("default")),
        "fast": _names(raw.get("fast")),
        "parking": {
            **{key: _number(parking.get(key)) for key in (
                "idle_minutes_default", "idle_minutes_when_memory_tight",
                "windows_available_gib_below", "wsl_available_gib_below",
            )},
            "keep_alive": _names(parking.get("keep_alive")),
        },
        "versions": {
            "default": version.get("default") if isinstance(version.get("default"), str) and _VERSION.fullmatch(version["default"]) else None,
            "hold": {lane: value for key, value in holds.items() if (lane := _identifier(key)) and isinstance(value, str) and _VERSION.fullmatch(value)},
            "hold_until": {lane: _text(value) for key, value in until.items() if (lane := _identifier(key))},
        },
    }


def _lane(row: Any) -> dict[str, Any] | None:
    if not isinstance(row, dict) or not (lane := _identifier(row.get("lane"))):
        return None
    reset = row.get("account")
    version = row.get("cli_version")
    return {
        "lane": lane, "status": _status(row.get("status")), "tier": _identifier(row.get("tier")),
        "cli_version": version if isinstance(version, str) and _VERSION.fullmatch(version) else None,
        "account": reset if isinstance(reset, str) and _POOL_LABEL.fullmatch(reset) else None,
        "subagents_spawned": _count(row.get("subagents_spawned")),
        "subagents_running": _count(row.get("subagents_running")),
        "subagent_models": _models(row.get("subagent_models")),
        "lane_model": _identifier(row.get("lane_model")),
        "subagent_uncached_share_pct": _number(row.get("subagent_uncached_share_pct"), 100),
        "subagent_uncached_tokens": _count(row.get("subagent_uncached_tokens")),
        "lane_uncached_tokens": _count(row.get("lane_uncached_tokens")),
        "flags": _names(row.get("flags")),
    }


def _workflow_names(root: Path) -> list[str]:
    names = []
    for path in sorted((root / ".github/workflows").glob("*.y*ml")):
        try:
            if path.stat().st_size > 256_000:
                continue
            source = path.read_text(encoding="utf-8")
        except OSError:
            continue
        source = "\n".join(line for line in source.splitlines() if not line.lstrip().startswith("#"))
        if not _AI_INVOCATION.search(source):
            continue
        match = re.search(r"(?m)^name:\s*([^\n]+)$", source)
        name = _text(match[1].strip().strip("\"'"), 100) if match else None
        if name:
            names.append(name)
    return sorted(set(names))


def _run_row(row: Any, workflow_names: list[str]) -> dict[str, Any] | None:
    if not isinstance(row, dict) or row.get("workflowName") not in workflow_names:
        return None
    run_id = _count(row.get("databaseId"))
    url = row.get("url")
    expected_url = f"https://github.com/{REPO}/actions/runs/{run_id}" if run_id else None
    return {
        "workflowName": row["workflowName"], "status": _status(row.get("status")),
        "conclusion": row.get("conclusion") if row.get("conclusion") in _CONCLUSIONS else None,
        "databaseId": run_id, "startedAt": _stamp(row.get("startedAt")),
        "updatedAt": _stamp(row.get("updatedAt")), "url": url if url == expected_url else None,
    }


def _actions_locked(cache_dir: Path, root: Path, run: Callable[..., Any], now: float) -> dict[str, Any]:
    names = _workflow_names(root)
    path = cache_dir / "fleet-actions.json"
    cached = _read_json(path)
    cached_runs = cached.get("runs") if isinstance(cached.get("runs"), list) else []
    rows = [safe for row in cached_runs[:100] if (safe := _run_row(row, names))]
    read_utc = _stamp(cached.get("read_utc"))
    last_attempt = _number(cached.get("attempt_epoch"))
    error = "gh run list failed; earlier observation retained" if cached.get("failed") is True else None
    api_errors = []
    due = last_attempt is None or now - last_attempt >= ACTIONS_TTL_SECONDS or now < last_attempt
    if due:
        try:
            result = run(["gh", "run", "list", "--repo", REPO, "--limit", "100", "--json", RUN_FIELDS], capture_output=True, text=True, timeout=25)
            if result.returncode or len(result.stdout) > MAX_SOURCE_BYTES:
                raise ValueError("native collection failed")
            raw = json.loads(result.stdout)
            if not isinstance(raw, list):
                raise ValueError("invalid run list")
            rows = [safe for row in raw[:100] if (safe := _run_row(row, names))]
            read_utc, error = _utc(now), None
        except (OSError, subprocess.SubprocessError, ValueError, TypeError):
            error = "gh run list failed; earlier observation retained" if read_utc else "gh run list unavailable"
            api_errors.append({"what": "gh run list failed", "when": _utc(now)})
        safe_cache = {"schema": "local-fleet-actions/1", "attempt_epoch": now, "read_utc": read_utc, "failed": error is not None, "runs": rows}
        try:
            cache_dir.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(".json.tmp")
            temporary.write_text(json.dumps(safe_cache, allow_nan=False), encoding="utf-8")
            temporary.replace(path)
        except OSError:
            pass
    age = max(0, now - datetime.fromisoformat(read_utc.replace("Z", "+00:00")).timestamp()) if read_utc else None
    return {
        "runs": rows, "workflow_names": names,
        "scope": "Newest 100 repository runs, filtered to workflows that invoke models",
        "read_utc": read_utc, "cache_age_seconds": round(age) if age is not None else None,
        "cache_ttl_seconds": ACTIONS_TTL_SECONDS, "stale": error is not None,
        "error": error, "API_errors": api_errors,
    }


def _actions(cache_dir: Path, root: Path, run: Callable[..., Any], now: float) -> dict[str, Any]:
    # The service timer, path watch and reviewer may collect concurrently.
    # A separate, stable inode coordinates the native CLI call across processes.
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        with (cache_dir / "fleet-actions.lock").open("a", encoding="utf-8") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                return _actions_locked(cache_dir, root, run, now)
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
    except OSError:
        return {
            "runs": [], "workflow_names": _workflow_names(root),
            "scope": "Newest 100 repository runs, filtered to workflows that invoke models",
            "read_utc": None, "cache_age_seconds": None,
            "cache_ttl_seconds": ACTIONS_TTL_SECONDS, "stale": True,
            "error": "Actions cache unavailable; native call skipped", "API_errors": [],
        }


def _ledger(path: Path, now: str, jobs: Any) -> dict[str, Any]:
    jobs_running = _count(jobs) if not isinstance(jobs, list) else len(jobs)
    result = {"read_utc": now, "file_utc": _mtime(path), "jobs_running": jobs_running, "spend_usd": None, "ceiling_usd": None}
    if not path.exists():
        return {**result, "status": "no spend yet", "spend_usd": 0.0}
    # Ledger event formats are not inferred from arbitrary fields or prose.
    # A cumulative spend_usd and explicit ceiling_usd are accepted if present.
    try:
        if path.stat().st_size > MAX_SOURCE_BYTES:
            return {**result, "status": "ledger exceeds read limit"}
        nonblank = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        for line in nonblank:
            row = json.loads(line)
            if not isinstance(row, dict):
                continue
            spend, ceiling = _number(row.get("spend_usd")), _number(row.get("ceiling_usd"))
            if spend is not None:
                result["spend_usd"] = spend
            if ceiling is not None:
                result["ceiling_usd"] = ceiling
        return {**result, "status": "observed" if result["spend_usd"] is not None else "ledger spend not observed"}
    except (OSError, ValueError):
        return {**result, "status": "ledger unavailable"}


def collect(state_root: Path, cache_dir: Path, root: Path, run: Callable[..., Any] | None = None) -> dict[str, Any]:
    """Collect once per page refresh; returned data contains no source free text.

    ``run`` has subprocess.run's calling convention and enables offline tests.
    Unknown observations stay None. A failed direct fleet read uses the dated
    snapshot for all native sections; the co-op list always uses that snapshot.
    """
    run = run or subprocess.run
    now = time.time()
    observed = _utc(now)
    snapshot_path = state_root / "coordination/ns2604-coop/watchers/fleet-now.json"
    snapshot = _read_json(snapshot_path)
    snapshot = snapshot if snapshot.get("schema") == "coop-fleet/1" else {}
    fleet, source = snapshot, "snapshot" if snapshot else "unavailable"
    try:
        result = run(["python3", str(state_root / "coordination/ns2604-coop/tools/fleet_block.py"), "--json", "--no-gh"], capture_output=True, text=True, timeout=25)
        if result.returncode or len(result.stdout) > MAX_SOURCE_BYTES:
            raise ValueError("native collection failed")
        direct = json.loads(result.stdout)
        if not isinstance(direct, dict) or direct.get("schema") != "coop-fleet/1":
            raise ValueError("invalid fleet schema")
        fleet, source = direct, "direct"
    except (OSError, subprocess.SubprocessError, ValueError, TypeError):
        pass
    native_time = _stamp(fleet.get("at"))
    snapshot_time = _stamp(snapshot.get("at"))
    cc_path = state_root / "coordination/command-center/pages/cc-now.json"
    tier_path = state_root / "coordination/command-center/lane-tiers.json"
    cc = _read_json(cc_path)
    tiers = _tiers(_read_json(tier_path))
    cc_agents = cc.get("cc_agents") if isinstance(cc.get("cc_agents"), dict) else {}
    cc_running = cc_agents.get("running") if isinstance(cc_agents.get("running"), list) else None
    live = fleet.get("lanes_live") if isinstance(fleet.get("lanes_live"), list) else []
    parked = _names(fleet.get("lanes_parked"))
    subgroup = fleet.get("claude_subagents_running") if isinstance(fleet.get("claude_subagents_running"), dict) else {}
    snap_subgroup = snapshot.get("claude_subagents_running") if isinstance(snapshot.get("claude_subagents_running"), dict) else {}
    subagents = {}
    for group in ("coop", "cc", "api_actions"):
        value = snap_subgroup.get(group) if group == "coop" else subgroup.get(group)
        names = _names(value)
        subagents[group] = {"names": names, "count": len(value) if isinstance(value, list) else None, "read_utc": snapshot_time if group == "coop" else native_time, "source": "snapshot" if group == "coop" else source}
    sessions = fleet.get("claude_sessions") if isinstance(fleet.get("claude_sessions"), list) else []
    accounts = fleet.get("pool_accounts") if isinstance(fleet.get("pool_accounts"), list) else []
    actions = _actions(cache_dir, root, run, now)
    sdk = _ledger(state_root / "coordination/api-actions-20261008/api-actions-ledger.jsonl", observed, fleet.get("sdk_jobs_running"))
    source_label = {"direct": "direct native", "snapshot": "snapshot fallback", "unavailable": "not reported"}[source]
    return {
        "schema": "local-fleet/1", "observed_utc": observed, "at": native_time,
        "fleet_source": source_label,
        "lanes_live": [safe for row in live[:200] if (safe := _lane(row))],
        "lanes_parked": [{"lane": lane, "tier": "fast" if lane in (tiers["fast"] or []) else tiers["default"], "cli_version": None, "expected_cli_version": tiers["versions"]["hold"].get(lane, tiers["versions"]["default"])} for lane in (parked or [])],
        "claude_sessions": [{"name": name, "status": _status(row.get("status"))} for row in sessions[:100] if isinstance(row, dict) and (name := _identifier(row.get("name")))],
        "claude_subagents_running": subagents,
        "cc_agents": {"running": [{"name": _identifier(row.get("name")), "type": _identifier(row.get("type"))} for row in (cc_running or [])[:100] if isinstance(row, dict)], "running_count": len(cc_running) if cc_running is not None else None, "read_utc": _stamp(cc.get("updated_utc"))},
        "exec_reads_in_flight": _names(fleet.get("exec_reads_in_flight")),
        "sdk": sdk, "actions": {key: value for key, value in actions.items() if key != "API_errors"},
        "pool_accounts": [{"account": row["account"], "used_pct": _number(row.get("used_pct"), 100)} for row in accounts[:100] if isinstance(row, dict) and isinstance(row.get("account"), str) and _POOL_LABEL.fullmatch(row["account"])],
        "fresh_total_pct": _number(fleet.get("fresh_total_pct")), "tiers": tiers,
        "totals": {key: _count(fleet.get("totals", {}).get(key)) for key in ("lanes_live", "lanes_parked", "codex_subagents_running", "claude_subagents_running", "claude_subagents_not_reported", "exec_reads_in_flight", "sdk_jobs_running")} if isinstance(fleet.get("totals"), dict) else {},
        "source_times": {"fleet_direct": native_time if source == "direct" else None, "fleet_snapshot": snapshot_time, "cc_now": _stamp(cc.get("updated_utc")), "lane_tiers": tiers["read_utc"], "api_ledger": sdk["file_utc"], "actions": actions["read_utc"]},
        "source_notes": ["Co-op subagents use the separately dated fleet snapshot.", "A missing ledger records no spend yet; a missing ceiling remains unknown."] + (["Direct fleet collection unavailable; dated snapshot used."] if source == "snapshot" else []),
        "errors": (["Fleet collection not reported."] if source == "unavailable" else []),
        "API_errors": actions["API_errors"],
    }
