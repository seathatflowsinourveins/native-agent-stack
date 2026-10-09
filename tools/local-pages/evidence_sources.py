"""Bounded projection of registered receipt metadata, without artifact discovery.

Receipt schemas predate the page contract. Their recorded field names and JSON
pointers are retained; receipt declarations are never promoted to vendor tests.
"""

from datetime import datetime, timezone
from collections import deque
import errno
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import stat
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


NATIVE_KINDS = {"native_cli_e2e", "native_model_e2e"}
_OMIT = re.compile(r"credential|secret|(?:^|_)env(?:ironment)?(?:$|_)|private|prompt|authorization|api[_-]?key|raw|logs?|stdout|stderr|stdin|fix_plan|pending|next_action|policy", re.I)
_DATES = ("recorded_at_utc", "checked_at", "observed_at_utc", "recorded_date_utc", "observed_at", "recorded_at", "captured_at", "date", "timestamp", "written_utc", "generated_utc", "ended_at_utc", "startTime")
_COMMANDS = {"command", "cmd", "harness", "source_reported_command", "native_command", "upstream_test_command", "run_command", "reproduce_command", "command_line", "run_commands", "commands", "native_commands", "native_cli_invocations", "executed_command_vector", "command_vector", "argv"}
_RESULTS = {"result", "status", "outcome", "verdict", "conclusion"}
_EXITS = {"exit", "exit_code", "returncode", "return_code", "rc", "pr_and_file_calls_exit_code"}
_PINS = ("pin", "version_or_commit", "package_version", "source_pin", "version", "source_revision", "source_git_commit")
_HISTORY = re.compile(r"prior|retained.fail|failed.attempt|previous|before|baseline|superseded", re.I)
_HOST_INDEX_LIMIT = 256 * 1024
_HOST_INDEX_RELATIVE = "coordination/command-center/pages/host-receipts-index.json"
_HOST_LABEL = "local host receipt (state root)"
_HOST_PATH = re.compile(r"command-center/(?:windows/[A-Za-z0-9][A-Za-z0-9_.-]{0,119}/RECEIPT[A-Za-z0-9_.-]{0,119}\.md|host-changes-[A-Za-z0-9][A-Za-z0-9_.-]{0,119}/[A-Za-z0-9][A-Za-z0-9_.-]{0,159}\.md)\Z")


def _scalar(value, limit=300):
    if not isinstance(value, str) or not value or len(value) > limit:
        return None
    if re.search(r"\bBearer\s|\bsk-|\bgh[pousr]_|\bgithub_pat_|[\w.+%-]+@[\w.-]+\.[A-Za-z]{2,}", value, re.I):
        return None
    return value


def observation_time(value):
    """Keep date-only UTC observations distinct from exact timestamps."""
    if not isinstance(value, str) or len(value) > 40:
        return None
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)
        observed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return observed.astimezone(timezone.utc) if observed.tzinfo is not None else None
    except ValueError:
        return None


def _index_string(value, limit):
    value = _scalar(value, limit)
    return value if value is not None and not re.search(r"[\x00-\x1f\x7f<>]", value) else None


def _index_utc(value):
    if not isinstance(value, str) or not 20 <= len(value) <= 40 or "T" not in value or not value.endswith(("Z", "+00:00")):
        return None
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return value if timestamp.tzinfo is not None and timestamp.utcoffset().total_seconds() == 0 else None
    except ValueError:
        return None


def host_receipts_index(state_root):
    """Project only the CC index; never access any referenced host receipt.

    Source custody is computed from the index bytes. Receipt hashes and mtimes
    remain index declarations, with no execution or acceptance inferred.
    """
    path = Path(state_root) / _HOST_INDEX_RELATIVE

    def unavailable(reason, sources=None):
        return {"items": [], "sources": sources or [], "scope": "local", "generated_utc": None, "label": _HOST_LABEL, "coverage": {"status": "unreported", "reason": reason, "retained_receipts": 0, "rejected_receipts": 0}}

    # O_NOFOLLOW rejects a symlink atomically. Metadata checks concern this one
    # index descriptor; target paths are never passed to filesystem functions.
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
        with os.fdopen(descriptor, "rb") as source:
            metadata = os.fstat(source.fileno())
            if not stat.S_ISREG(metadata.st_mode):
                return unavailable("source index is not a regular file")
            if metadata.st_size > _HOST_INDEX_LIMIT:
                return unavailable("source index exceeds the bounded read limit")
            raw = source.read(_HOST_INDEX_LIMIT + 1)
    except FileNotFoundError:
        return unavailable("CC host receipt index is absent")
    except OSError as error:
        return unavailable("source index symlink is not an authorized source" if error.errno == errno.ELOOP else "CC host receipt index is unreadable")
    if len(raw) > _HOST_INDEX_LIMIT:
        return unavailable("source index exceeds the bounded read limit")
    custody = [{"path": str(path), "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw), "scope": "local", "label": _HOST_LABEL}]
    try:
        document = json.loads(raw)
    except (ValueError, UnicodeError):
        return unavailable("CC host receipt index is not valid JSON", custody)
    if not isinstance(document, dict) or document.get("schema") != "host-receipts-index/1":
        return unavailable("CC host receipt index schema is unsupported", custody)
    generated = _index_utc(document.get("generated_utc"))
    scope = _index_string(document.get("scope"), 600)
    rows = document.get("receipts")
    if generated is None or scope is None or not isinstance(rows, list) or len(rows) > 256:
        return unavailable("CC host receipt index has invalid date, scope or bounded receipt-list metadata", custody)
    items, rejected = [], []
    for position, row in enumerate(rows):
        reason = None
        if not isinstance(row, dict):
            reason = "receipt metadata is not an object"
        else:
            relative = row.get("path")
            digest = row.get("sha256")
            size = row.get("bytes")
            title = _index_string(row.get("title"), 240)
            mtime = _index_utc(row.get("mtime_utc"))
            if not isinstance(relative, str) or not _HOST_PATH.fullmatch(relative) or ".." in relative or re.search(r"credential|secret|(?:^|[./_-])env(?:[./_-]|$)", relative, re.I):
                reason = "receipt path is outside the allowed local metadata paths"
            elif not isinstance(digest, str) or not re.fullmatch(r"[a-fA-F0-9]{64}", digest):
                reason = "receipt hash is not a 64-character index declaration"
            elif not isinstance(size, int) or isinstance(size, bool) or size < 0:
                reason = "receipt bytes is not a nonnegative integer"
            elif title is None or mtime is None:
                reason = "receipt title or UTC file metadata is invalid"
        if reason:
            rejected.append({"index": position, "reason": reason})
            continue
        locator = f"{_HOST_INDEX_RELATIVE}#/receipts/{position}"
        items.append({"path": relative, "sha256": digest, "bytes": size, "title": title, "mtime_utc": mtime, "label": _HOST_LABEL, "scope": "local", "generated_utc": generated, "source": locator, "receipt_hash_status": "index-declared hash", "mtime_status": "index-provided file metadata", "native_acceptance": False, "vendor_acceptance": False})
    custody[0]["generated_utc"] = generated
    coverage = {"status": "partial" if rejected else "reported", "reason": "some local index metadata rows were rejected" if rejected else "local host receipt metadata comes only from the sanitized CC index", "declared_receipts": len(rows), "retained_receipts": len(items), "rejected_receipts": len(rejected), "rejections": rejected[:32], "receipt_contents": "unread", "receipt_hashes": "index-declared hash", "file_times": "index-provided file metadata"}
    return {"items": items, "sources": custody, "coverage": coverage, "scope": "local", "declared_scope": scope, "generated_utc": generated, "label": _HOST_LABEL}


def _nodes(document, component_id=None):
    """Visit public metadata dictionaries only, with bounded depth and work."""
    pending, visited = deque([("", document, 0)]), 0
    while pending and visited < 12000:
        pointer, node, depth = pending.popleft()
        visited += 1
        if depth > 8:
            continue
        if isinstance(node, dict):
            named = node.get("component_id")
            if component_id and isinstance(named, str) and named.lower() != component_id.lower():
                continue
            yield pointer, node
            pending.extend((f"{pointer}/{key}", value, depth + 1) for key, value in node.items() if isinstance(value, (dict, list)) and not _OMIT.search(str(key)) and not _HISTORY.search(str(key)))
        elif isinstance(node, list):
            pending.extend((f"{pointer}/{index}", value, depth + 1) for index, value in enumerate(node[:2000]) if isinstance(value, (dict, list)))


def linked_receipt_paths(document):
    """Only explicit receipt pointers are eligible for a registry digest check."""
    paths = []
    for _, node in _nodes(document):
        for key in ("artifact_path", "receipt_path", "receipt_ref", "native_receipt", "receipt", "commands"):
            value = node.get(key)
            if isinstance(value, str) and value.endswith(".json") and value not in paths:
                paths.append(value)
    return paths[:20]


def _recorded_pin(document, registry, component_id, nodes):
    normalize = lambda value: str(value).lower().replace("_", "-")
    target = normalize(component_id)
    components = set(document.get("component_ids", registry.get("component_ids", [])))
    single = components == {component_id} or document.get("component_id") == component_id
    for pointer, node in nodes:
        for key in ("tool_versions", "versions", "pins", "source_pins", "new_installed_pins", "upstream_pins"):
            values = node.get(key)
            if isinstance(values, dict):
                for name, value in values.items():
                    if normalize(name) == target:
                        if isinstance(value, dict):
                            value = value.get("version", value.get("pin", value.get("version_or_commit")))
                        if pin := _scalar(value, 100):
                            return pin
        labeled = target in [normalize(part) for part in pointer.split("/")]
        labeled |= any(normalize(node.get(key)) == target for key in ("component_id", "name", "id", "binary", "program", "executable"))
        repository = node.get("repository")
        if isinstance(repository, str):
            repository = normalize(repository).removeprefix("https://github.com/").removesuffix(".git").rstrip("/")
            labeled |= repository == target or repository.endswith("/" + target)
        if not labeled and not (single and pointer in ("", "/data", "/upstream", "/installation")):
            continue
        for key in _PINS:
            value = node.get(key)
            if isinstance(value, dict):
                value = value.get("version_or_commit")
            if pin := _scalar(value, 100):
                return pin
    return None


def receipt_projection(document, registry, component_id, safe_command):
    """Extract explicit date/command/result fields and their source locators."""
    nodes = list(_nodes(document, component_id))
    kind = _scalar(document.get("kind"), 100) or _scalar(registry.get("kind"), 100)
    cls = _scalar(document.get("evidence_class"), 100) or _scalar(registry.get("evidence_class"), 100) or kind
    date, date_pointer, date_original, date_timezone = None, None, None, None
    for pointer, node in nodes:
        for key in _DATES:
            recorded = node.get(key)
            value = recorded
            zone = node.get("timezone", document.get("timezone"))
            if key == "checked_at" and isinstance(recorded, str) and len(recorded) <= 40 and isinstance(zone, str) and not observation_time(recorded):
                try:
                    value = datetime.fromisoformat(recorded).replace(tzinfo=ZoneInfo(zone)).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
                except (ValueError, ZoneInfoNotFoundError):
                    pass
            if observation_time(value):
                date, date_pointer, date_original = value, f"{pointer}/{key}", recorded
                date_timezone = zone if isinstance(zone, str) and len(zone) < 60 else None
                break
        if date:
            break
    commands, command_pointers = [], []
    results, result_pointers, exits, explicit_result = [], [], [], None
    for pointer, node in nodes:
        for key, value in node.items():
            if _OMIT.search(str(key)) or _HISTORY.search(str(key)):
                continue
            locator = f"{pointer}/{key}"
            if key in _COMMANDS:
                if key in ("argv", "executed_command_vector", "command_vector") or isinstance(value, list) and (key in ("command", "cmd", "harness") or key.endswith("_command")):
                    values = [shlex.join(value)] if isinstance(value, list) and all(isinstance(part, str) for part in value) else []
                else:
                    values = value if isinstance(value, list) else [value]
                for item in values[:20]:
                    if isinstance(item, str) and not item.endswith(".json") and (command := safe_command(item)) and command not in commands:
                        commands.append(command)
                        command_pointers.append(locator)
            if key in _RESULTS and (result := _scalar(value)):
                results.append(result)
                result_pointers.append(locator)
            if key in _EXITS and isinstance(value, int) and not isinstance(value, bool):
                exits.append(value)
                result_pointers.append(locator)
        if pointer == "" and results:
            # A receipt-level result outranks its diagnostic/retained details.
            explicit_result = results[0]
        elif not pointer:
            explicit_result = None
    if explicit_result:
        result = explicit_result
    elif exits:
        result = "pass" if all(value == 0 for value in exits) else "failure"
    elif results:
        failed = [value for value in results if value.lower() in ("fail", "failed", "failure", "error", "errors")]
        passed = [value for value in results if value.lower() in ("pass", "passed", "success", "succeeded", "verified")]
        result = failed[0] if failed else "pass" if len(passed) == len(results) else "; ".join(dict.fromkeys(results))[:300]
    else:
        result = None
    pin = _recorded_pin(document, registry, component_id, nodes)
    missing = []
    if date is None:
        missing.append("receipt does not record a parseable UTC observation date")
    if not commands:
        missing.append("receipt does not publish a safe execution command")
    if result is None:
        missing.append("receipt does not publish a machine result or exit code")
    programs = []
    for command in commands:
        try:
            parts = shlex.split(command)
            while parts and re.match(r"[A-Za-z_][A-Za-z0-9_]*=", parts[0]):
                parts.pop(0)
            basename = Path(parts[0]).name
            if _scalar(basename, 100) and basename not in programs:
                programs.append(basename)
        except (ValueError, IndexError):
            continue
    return {"kind": kind, "evidence_class": cls, "date": date, "date_original": date_original, "date_timezone": date_timezone, "date_precision": "day" if date and len(date) == 10 else "timestamp" if date else None, "command": "\n".join(commands[:8])[:1500] or None, "command_count": len(commands), "command_programs": programs[:20], "result": result, "observed_pin": pin, "metadata_locators": {"date": date_pointer, "commands": command_pointers[:8], "results": result_pointers[:20]}, "missing_metadata": missing}
