"""Project published instance totals to recorded lanes without reading sessions.

Only bounded co-op registry JSON and named parking/capacity receipts are read.
The shared source_policy descriptor reader refuses protected components and
symlinks before their bodies can contribute to source hashes or bindings.
Window attribution remains uncertain when a recurrent alias has multiple lanes
or no dated registry binding. No counters are inferred from missing telemetry.
"""

import copy
import hashlib
import importlib.util
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

MAX_JSON_BYTES = 1_048_576
MAX_RECEIPTS = 128
OWNER = "native-agent-stack-1a"
OWNER_DISPLAY = "owner session (reports to CC)"
_POLICY_SPEC = importlib.util.spec_from_file_location("adoption_roles_source_policy", Path(__file__).with_name("source_policy.py"))
_policy = importlib.util.module_from_spec(_POLICY_SPEC)
_POLICY_SPEC.loader.exec_module(_policy)


def _time(value):
    if not isinstance(value, str) or len(value) > 50:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc) if parsed.tzinfo else None
    except (ValueError, OverflowError):
        return None


def _utc(value):
    return value.isoformat(timespec="seconds").replace("+00:00", "Z") if value else None


def _count(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _sum(values):
    return sum(values) if values and all(_count(value) for value in values) else None


def _map(value):
    return value if isinstance(value, dict) else {}


def _alias(name):
    if not isinstance(name, str):
        return None
    suffix = name.rsplit("-", 1)[-1]
    return suffix if re.fullmatch(r"[a-z]{4}", suffix) else None


def _read(path, sources, errors):
    try:
        # The shared native reader checks protected components and walks every
        # ancestor with O_NOFOLLOW before opening the bounded regular leaf.
        # Bytes, digest and file metadata all belong to that same descriptor.
        with _policy._open_regular(path, limit=MAX_JSON_BYTES) as handle:
            info = os.fstat(handle.fileno())
            raw = handle.read(MAX_JSON_BYTES + 1)
        if len(raw) > MAX_JSON_BYTES:
            raise _policy.SourceReadLimitError("registry metadata exceeds its bound")
    except FileNotFoundError:
        return {}
    except (OSError, ValueError, OverflowError) as error:
        errors.append({"path": str(path), "status": "UNREPORTED: registry input refused (" + type(error).__name__ + ")"})
        return {}
    source = {
        "path": str(path), "sha256": hashlib.sha256(raw).hexdigest(),
        "read_utc": _utc(datetime.now(timezone.utc)),
        "mtime_utc": _utc(datetime.fromtimestamp(info.st_mtime, timezone.utc)),
    }
    sources.append(source)
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("registry metadata must be an object")
        return data
    except ValueError:
        errors.append({"path": str(path), "status": "UNREPORTED: malformed registry metadata"})
        return {}


def _parking_paths(directory, errors):
    """Enumerate the existing reviewed family without following its parent."""
    if _policy.protected_path(directory.absolute().as_posix()):
        errors.append({"path": str(directory), "status": "UNREPORTED: protected registry directory"})
        return []
    try:
        with _policy._directory(directory) as descriptor:
            names = os.listdir(descriptor)
    except FileNotFoundError:
        return []
    except (OSError, ValueError) as error:
        errors.append({"path": str(directory), "status": "UNREPORTED: registry directory refused (" + type(error).__name__ + ")"})
        return []
    names = sorted(name for name in names if name.startswith("park-") and name.endswith(".json"))
    result = []
    for name in names:
        # The prefix does not make a credentials/protected basename eligible.
        if _policy.protected_path(name) or _policy.protected_path(name.removeprefix("park-")):
            errors.append({"path": str(directory / name), "status": "UNREPORTED: protected receipt name"})
            continue
        result.append(directory / name)
    return result


def _bindings(base):
    sources, errors, bindings = [], [], []

    def add(lane, name, thread, source, start=None, end=None, observed=None):
        if not isinstance(lane, str) or not isinstance(name, str) or not _alias(name):
            return
        bindings.append({
            "lane": lane, "name": name, "alias": _alias(name),
            "thread": thread if isinstance(thread, str) else None,
            "start_utc": _utc(_time(start)), "end_utc": _utc(_time(end)),
            "observed_utc": _utc(_time(observed)), "source_ref": str(source),
        })

    for relative in ("lanes/hcom-lanes.json", "lanes/threads.json"):
        path = base / relative
        data = _read(path, sources, errors)
        for lane, row in data.items():
            if not isinstance(row, dict):
                continue
            launch = row.get("launched")
            times = [row.get("closed"), row.get("stopped")]
            if not row.get("parked_name") or row.get("parked_name") == row.get("name"):
                times.append(row.get("parked"))
            if row.get("last_parked_name") == row.get("name"):
                times.append(row.get("last_parked"))
            ended = [value for value in times if _time(value) and (not _time(launch) or _time(value) >= _time(launch))]
            end = min(ended, key=_time) if ended else None
            add(lane, row.get("name"), row.get("thread"), path, launch, end)
            add(lane, row.get("previous_name"), row.get("previous_thread"), path, row.get("previous_launched"), launch)
            for prefix, field in (("parked", "parked"), ("last_parked", "last_parked")):
                add(lane, row.get(prefix + "_name"), row.get(prefix + "_thread"), path, end=row.get(field))

    parking = base / "notes/parking-20261008"
    capacity = base / "notes/capacity-ruling-20261008"
    paths = _parking_paths(parking, errors)
    paths += [capacity / name for name in ("relay-receipt.json", "relay-receipt-dryrun.json", "relay-reserve-receipt.json")]
    if len(paths) > MAX_RECEIPTS:
        errors.append({"path": str(parking), "status": "UNREPORTED: receipt count exceeds bound"})
        paths = []
    for path in paths:
        data = _read(path, sources, errors)
        observed = _map(data.get("before")).get("at") or data.get("at") or data.get("generated_utc")
        ended = _map(data.get("after")).get("at")
        rows = data.get("plan", data.get("lanes", []))
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, dict):
                continue
            parked = data.get("apply") is True and row.get("park") is True and row.get("kill_rc") == 0
            add(row.get("lane"), row.get("name"), row.get("thread"), path, row.get("launched"), ended if parked else None, observed)
    return bindings, sources, errors


def _compatible(binding, start, end):
    launched = _time(binding["start_utc"])
    stopped = _time(binding["end_utc"])
    if launched and launched > end or stopped and stopped < start:
        return False
    return True


def _dated(binding, start, end):
    return any(start <= value <= end for value in (
        _time(binding["start_utc"]), _time(binding["end_utc"]), _time(binding["observed_utc"])
    ) if value) or bool(_time(binding["start_utc"]) and _time(binding["start_utc"]) <= start and (
        _time(binding["end_utc"]) is None or _time(binding["end_utc"]) >= end
    ))


def _aggregate(rows):
    servers = {}
    for name in sorted({name for row in rows for name in _map(row.get("servers"))}):
        entries = [_map(_map(row.get("servers")).get(name)) for row in rows if name in _map(row.get("servers"))]
        servers[name] = {
            "calls": _sum([entry.get("calls") for entry in entries]),
            "conversations": _sum([entry.get("conversations") for entry in entries]),
        }
    calls = _sum([entry["calls"] for entry in servers.values()])
    return {
        "conversations": _sum([row.get("conversations") for row in rows]),
        "calls": calls, "servers": servers,
        "instances": len(rows),
        "aggregation_scope": "sum of published instance counts; distinct cross-instance conversations unverified",
    }


def _tools(rows):
    return {tool: _sum([row[tool] for row in rows if tool in row])
            for tool in sorted({tool for row in rows for tool in row})}


def project(document, state_root):
    """Return a read-only role projection and retain every unattributed instance."""
    generated = _time(document.get("generated_utc"))
    hours = document.get("window_hours")
    if generated is None or not isinstance(hours, int) or isinstance(hours, bool) or hours <= 0:
        raise ValueError("published UTC window is required")
    start = generated - timedelta(hours=hours)
    bindings, sources, errors = _bindings(Path(state_root) / "coordination/ns2604-coop")
    codex = _map(document.get("codex_by_lane"))
    orchestration = _map(document.get("orchestration"))
    codex_tools = _map(orchestration.get("codex_by_lane"))
    labels = sorted(set(codex) | set(codex_tools))
    role_map, records, unattributed = {}, {}, {}
    for label in labels:
        candidates = [binding for binding in bindings if label in (binding["name"], binding["alias"]) and _compatible(binding, start, generated)]
        lanes = sorted({binding["lane"] for binding in candidates})
        proven = len(lanes) == 1 and any(_dated(binding, start, generated) for binding in candidates)
        reason = None if proven else ("ambiguous recurrent alias in measured window" if len(lanes) > 1 else "no dated launch-window binding" if lanes else "instance absent from bounded registry history")
        role_map[label] = lanes[0] if proven else None
        records[label] = {
            "lane": role_map[label], "candidate_roles": lanes,
            "window_start_utc": _utc(start), "window_end_utc": _utc(generated),
            "bindings": candidates, "status": "ATTRIBUTED" if proven else "UNATTRIBUTED", "reason": reason,
            "counts": copy.deepcopy(codex.get(label)), "orchestration": copy.deepcopy(codex_tools.get(label)),
        }
        if not proven:
            unattributed[label] = records[label]
    codex_roles = {}
    for role in sorted({role for role in role_map.values() if role}):
        members = [label for label in codex if role_map.get(label) == role]
        if members:
            codex_roles[role] = _aggregate([_map(codex[label]) for label in members])
            codex_roles[role]["instance_labels"] = members
    unmatched = [_map(codex[label]) for label in codex if not role_map.get(label)]
    transformed = copy.deepcopy(document)
    transformed["codex_by_lane"] = copy.deepcopy(codex_roles)
    if unmatched:
        transformed["codex_by_lane"]["unattributed instances"] = _aggregate(unmatched)
    claude_tools = copy.deepcopy(_map(orchestration.get("claude_by_role")))
    role_tools = {role: _tools([_map(codex_tools[label]) for label in codex_tools if role_map.get(label) == role])
                  for role in sorted({role for label, role in role_map.items() if role and label in codex_tools})}
    unmeasured = copy.deepcopy(orchestration.get("unmeasured", []))
    if not isinstance(unmeasured, list):
        unmeasured = []
    for name in ("claude_by_role", "codex_by_lane"):
        if name not in orchestration:
            unmeasured.append(name + " orchestration")
    sdk_rows = []
    for layer, row in _map(document.get("layers")).items():
        for server, counts in _map(_map(row).get("servers")).items():
            if isinstance(server, str) and server.startswith("sdk:"):
                entry = {"client": server, "layer": layer, "source_scope": "published layer server row"}
                entry.update({key: value if _count(value) else None for key, value in _map(counts).items()
                              if key in {"claude_calls", "claude_sessions", "codex_calls", "codex_conversations"}})
                sdk_rows.append(entry)
    return {
        "document": transformed, "codex_roles": codex_roles,
        "instances": {"role_map": role_map, "records": records, "unattributed": unattributed},
        "sources": sources, "source_errors": errors,
        "window": {"start_utc": _utc(start), "end_utc": _utc(generated)},
        "orchestration": {
            "claude_by_role": claude_tools, "codex_by_role": role_tools,
            "codex_unattributed": {label: copy.deepcopy(row) for label, row in codex_tools.items() if not role_map.get(label)},
            "unmeasured": unmeasured,
            "scope": "only published tool counters; missing tools remain unmeasured",
        },
        "sdk": {"rows": sdk_rows, "status": "MEASURED" if sdk_rows else "UNREPORTED",
                "unmeasured": [] if sdk_rows else ["SDK client counters absent from published snapshot"]},
    }
