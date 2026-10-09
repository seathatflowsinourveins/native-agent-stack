"""Read the prescribed fleet sources and return a small, whitelisted view.

Collection stays with fleet_block.py and the installed gh CLI. The cache stores
sanitized run fields only and must be placed outside the HTTP serving root.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
from http.client import HTTPException
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import tempfile
import time
from typing import Any, Callable
from urllib.parse import urlencode


ACTIONS_TTL_SECONDS = 540
PRODUCER_TIMEOUT_SECONDS = 90
REPO = "seathatflowsinourveins/native-agent-stack"
MAX_SOURCE_BYTES = 2_000_000
RUN_FIELDS = "workflowName,status,conclusion,databaseId,startedAt,updatedAt,url"
# Linux UAPI include/uapi/linux/fcntl.h F_ADD_SEALS/F_GET_SEALS and seal bits:
# https://github.com/torvalds/linux/blob/v6.18/include/uapi/linux/fcntl.h
# Some CPython builds expose memfd_create but omit these fcntl constants.
_ADD_SEALS = getattr(fcntl, "F_ADD_SEALS", 1033)
_GET_SEALS = getattr(fcntl, "F_GET_SEALS", 1034)
_REQUIRED_SEALS = (getattr(fcntl, "F_SEAL_SEAL", 0x0001) | getattr(fcntl, "F_SEAL_SHRINK", 0x0002)
                   | getattr(fcntl, "F_SEAL_GROW", 0x0004) | getattr(fcntl, "F_SEAL_WRITE", 0x0008))
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:/+-]{0,99}\Z")
_OPAQUE = re.compile(r"(?<![A-Za-z0-9])(?:sk-|gh[pousr]_|github_pat_|Bearer\s)|[A-Za-z0-9]{32,}", re.I)
_PRIVATE_LABEL = re.compile(r"(?:https?://|/home/|/Users/|[A-Za-z]:[\\/]|\b[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}\b)", re.I)
_SOURCE_POLICY = None
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
_PRODUCER_BOOTSTRAP = """import hashlib, importlib.machinery, io, linecache, os, sys, tokenize, types
descriptor, source, expected = int(sys.argv[1]), sys.argv[2], sys.argv[3]
with os.fdopen(descriptor, 'rb') as snapshot:
    raw = snapshot.read(2000001)
if len(raw) > 2000000 or hashlib.sha256(raw).hexdigest() != expected:
    raise SystemExit('verified producer snapshot differs from its binding')
encoding, _ = tokenize.detect_encoding(io.BytesIO(raw).readline)
linecache.cache[source] = (len(raw), None, raw.decode(encoding).splitlines(True), source)
sys.argv = [source] + sys.argv[4:]
sys.path.insert(0, os.path.dirname(source))
entry = types.ModuleType('__main__')
entry.__file__, entry.__package__, entry.__spec__, entry.__cached__ = source, None, None, None
entry.__loader__ = importlib.machinery.SourceFileLoader('__main__', source)
sys.modules['__main__'] = entry
exec(compile(raw, source, 'exec'), entry.__dict__)
"""


def _utc(epoch: float | None = None) -> str:
    return datetime.fromtimestamp(time.time() if epoch is None else epoch, timezone.utc).isoformat().replace("+00:00", "Z")


def _stamp(value: Any) -> str | None:
    if not isinstance(value, str) or len(value) > 40:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z") if parsed.tzinfo else None
    except (ValueError, OverflowError):
        return None


def _identifier(value: Any) -> str | None:
    return value if isinstance(value, str) and _IDENTIFIER.fullmatch(value) and not _OPAQUE.search(value) else None


def _text(value: Any, limit: int = 160) -> str | None:
    if not isinstance(value, str) or not value or len(value) > limit or "@" in value or _OPAQUE.search(value):
        return None
    return value if re.fullmatch(r"[A-Za-z0-9 .,;:()_/'+-]+", value) else None


def _workflow_label(value: Any) -> str | None:
    # Workflow names are public labels, including Unicode and punctuation.
    # Preserve the source's exact identity while excluding private/token text.
    if not isinstance(value, str) or not value or len(value) > 100 or not value.isprintable():
        return None
    return value if '@' not in value and not _OPAQUE.search(value) and not _PRIVATE_LABEL.search(value) else None


def _number(value: Any, maximum: float | None = None) -> int | float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        return None
    return value if maximum is None or value <= maximum else None


def _count(value: Any) -> int | None:
    number = _number(value)
    return int(number) if number is not None and int(number) == number else None


def _status(value: Any) -> str | None:
    return value if isinstance(value, str) and value in _STATUSES else None


@contextmanager
def _directory(path: Path, create: bool = False):
    """Open the named directory through non-symlink ancestor descriptors.

    Native Python3.13 os.open(dir_fd, O_NOFOLLOW), fstat and replace contracts:
    https://docs.python.org/3.13/library/os.html#files-and-directories
    """
    path = path.absolute()
    if ".." in path.parts:
        raise OSError("directory traversal rejected")
    descriptor = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in path.parts[1:]:
            if create:
                try:
                    os.mkdir(part, mode=0o700, dir_fd=descriptor)
                except FileExistsError:
                    pass
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        yield descriptor
    finally:
        os.close(descriptor)


def _source_policy():
    global _SOURCE_POLICY
    if _SOURCE_POLICY is None:
        spec = importlib.util.spec_from_file_location("fleet_source_policy", Path(__file__).with_name("source_policy.py"))
        if spec is None or spec.loader is None:
            raise ValueError("native source read helper unavailable")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _SOURCE_POLICY = module
    return _SOURCE_POLICY


def _read_source(path: Path, root: Path, sources: dict | None = None, *, kind: str = "source", limit: int = MAX_SOURCE_BYTES):
    """Read a bounded regular file without following any source symlink."""
    path, root = path.absolute(), root.absolute()
    receipt = {"path": str(path), "type": kind, "status": "unavailable", "sha256": None, "bytes": None, "read_utc": None, "file_utc": None}
    raw = None
    try:
        relative = path.relative_to(root)
        if ".." in relative.parts:
            raise ValueError("source outside approved root")
        # The native helper enforces protected names, regular-file bounds and
        # no-follow ancestors. Metadata and digest bind the same open handle.
        with _source_policy()._open_regular(path, limit=limit) as stream:
            info = os.fstat(stream.fileno())
            raw = stream.read(limit + 1)
            if len(raw) > limit:
                raise ValueError("source exceeds read limit")
            receipt.update(status="reported", sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw), read_utc=_utc(), file_utc=_utc(info.st_mtime))
    except (OSError, ValueError) as error:
        raw = None
        receipt["reason"] = "source missing" if isinstance(error, FileNotFoundError) else "source rejected or unavailable"
    if sources is not None:
        sources[str(path)] = receipt
    return raw, receipt


def _read_json(path: Path, root: Path | None = None, sources: dict | None = None, *, kind: str = "source") -> dict[str, Any]:
    raw, receipt = _read_source(path, root or path.parent, sources, kind=kind)
    if raw is None:
        return {}
    try:
        value = json.loads(raw)
        if isinstance(value, dict):
            return value
    except (ValueError, UnicodeError):
        pass
    receipt.update(status="unavailable", reason="invalid JSON object")
    return {}


def _run_producer(command, *, capture_output=True, text=True, timeout=PRODUCER_TIMEOUT_SECONDS, **kwargs):
    """Use the native Popen session/communicate API to kill a timed-out group.

    CPython3.13.16 subprocess.run kills its direct child only. Official Popen
    start_new_session and communicate(timeout) contracts supply this small seam:
    https://docs.python.org/3.13/library/subprocess.html#subprocess.Popen
    https://docs.python.org/3.13/library/os.html#os.killpg
    """
    kwargs.setdefault("start_new_session", True)
    if capture_output:
        kwargs.update(stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    with subprocess.Popen(command, text=text, **kwargs) as child:
        try:
            stdout, stderr = child.communicate(timeout=timeout)
        except BaseException:
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            child.communicate()
            raise
        return subprocess.CompletedProcess(command, child.returncode, stdout, stderr)


def _execute_producer(path: Path, raw: bytes, receipt: dict, run: Callable[..., Any]):
    """Execute the checked bytes through an immutable native Linux descriptor.

    Python os.memfd_create(MFD_ALLOW_SEALING), fcntl F_ADD_SEALS/F_SEAL_WRITE
    and subprocess.run(pass_fds): https://docs.python.org/3.13/library/os.html#os.memfd_create
    https://docs.python.org/3.13/library/fcntl.html
    https://docs.python.org/3.13/library/subprocess.html#subprocess.Popen
    The child compiles these bytes with the producer's original filename,
    argv and sibling-import path; it never opens that producer pathname.
    """
    execution = {"kind": "sealed memfd producer snapshot", "sha256": hashlib.sha256(raw).hexdigest(),
                 "bytes": len(raw), "status": "unavailable", "attempt_utc": _utc()}
    receipt["execution"] = execution
    descriptor = os.memfd_create("native-fleet-producer", os.MFD_CLOEXEC | os.MFD_ALLOW_SEALING)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as snapshot:
            snapshot.write(raw)
            snapshot.flush()
        fcntl.fcntl(descriptor, _ADD_SEALS, _REQUIRED_SEALS)
        if fcntl.fcntl(descriptor, _GET_SEALS) & _REQUIRED_SEALS != _REQUIRED_SEALS:
            raise ValueError("producer snapshot immutability was not established")
        os.lseek(descriptor, 0, os.SEEK_SET)
        # -I keeps CWD/PYTHONPATH/user-site code out of the bootstrap's imports.
        # The sibling path is added explicitly only after snapshot verification.
        runner = _run_producer if run is subprocess.run else run
        result = runner([sys.executable, "-I", "-c", _PRODUCER_BOOTSTRAP, str(descriptor), str(path),
                      execution["sha256"], "--json", "--no-gh"],
                     pass_fds=(descriptor,), capture_output=True, text=True,
                     timeout=PRODUCER_TIMEOUT_SECONDS, start_new_session=True)
        execution.update(status="completed" if result.returncode == 0 else "failed", returncode=result.returncode)
        return result
    except subprocess.TimeoutExpired:
        execution.update(status="timed out", timeout_seconds=PRODUCER_TIMEOUT_SECONDS)
        raise
    finally:
        os.close(descriptor)


def _destination(directory: int, name: str) -> None:
    try:
        info = os.stat(name, dir_fd=directory, follow_symlinks=False)
    except FileNotFoundError:
        return
    if not stat.S_ISREG(info.st_mode):
        raise OSError("nonregular cache destination rejected")


def _write_cache(path: Path, value: dict) -> None:
    """Use native secure temporary creation and one checked atomic replacement."""
    with _directory(path.parent, create=True) as directory:
        _destination(directory, path.name)
        descriptor, temporary = tempfile.mkstemp(prefix=".fleet-actions-", suffix=".tmp", dir=f"/proc/self/fd/{directory}")
        name = Path(temporary).name
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(value, stream, allow_nan=False)
                stream.flush()
                os.fsync(stream.fileno())
            _destination(directory, path.name)
            os.replace(name, path.name, src_dir_fd=directory, dst_dir_fd=directory)
        finally:
            try:
                os.unlink(name, dir_fd=directory)
            except FileNotFoundError:
                pass


def _names(value: Any) -> list[str] | None:
    if not isinstance(value, list):
        return None
    names = [name for row in value[:200] if (name := _identifier(row.get("name") if isinstance(row, dict) else row))]
    return names if names or not value else None


def _models(value: Any) -> dict[str, int | None] | list[str] | None:
    if isinstance(value, dict):
        return {model: _count(count) for key, count in list(value.items())[:50] if (model := _identifier(key))}
    return _names(value)


def _tiers(raw: dict[str, Any]) -> dict[str, Any]:
    parking = raw.get("parking") if isinstance(raw.get("parking"), dict) else {}
    version = raw.get("codex_version") if isinstance(raw.get("codex_version"), dict) else {}
    holds = version.get("hold") if isinstance(version.get("hold"), dict) else {}
    until = version.get("hold_until") if isinstance(version.get("hold_until"), dict) else {}
    fast = _names(raw.get("fast"))
    if isinstance(raw.get("fast"), list) and len(fast or []) != len(raw["fast"]):
        fast = None
    policy_known = raw.get("schema") == "lane-tiers/1" and fast is not None and _identifier(raw.get("default")) is not None
    return {
        "availability": "reported" if policy_known else "not reported",
        "reason": None if policy_known else "policy absent or required default/fast list unavailable",
        "read_utc": _stamp(raw.get("updated_utc")),
        "default": _identifier(raw.get("default")) if policy_known else None,
        "fast": fast if policy_known else None,
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


def _workflow_names(root: Path, sources: dict | None = None) -> list[str]:
    names = []
    directory = root / ".github/workflows"
    try:
        with _directory(directory) as descriptor:
            entries = sorted(os.listdir(descriptor))
            if len(entries) > 200:
                return []
    except OSError:
        return []
    for name in entries:
        path = directory / name
        if path.suffix not in {".yml", ".yaml"}:
            continue
        raw, _ = _read_source(path, root, sources, kind="workflow", limit=256_000)
        if raw is None:
            continue
        try:
            source = raw.decode("utf-8")
        except UnicodeError:
            continue
        source = "\n".join(line for line in source.splitlines() if not line.lstrip().startswith("#"))
        if not _AI_INVOCATION.search(source):
            continue
        match = re.search(r"(?m)^name:\s*([^\n]+)$", source)
        name = _workflow_label(match[1].strip().strip("\"'")) if match else None
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


def _actions_locked(cache_dir: Path, root: Path, run: Callable[..., Any], now: float, sources: dict | None = None) -> dict[str, Any]:
    names = _workflow_names(root, sources)
    path = cache_dir / "fleet-actions.json"
    cached = _read_json(path, cache_dir, sources, kind="Actions cache")
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
            _write_cache(path, safe_cache)
        except OSError:
            pass
    try:
        age = max(0, now - datetime.fromisoformat(read_utc.replace("Z", "+00:00")).timestamp()) if read_utc else None
    except (ValueError, OverflowError):
        age = None
    return {
        "runs": rows, "workflow_names": names,
        "scope": "Newest 100 repository runs, filtered to workflows that invoke models",
        "read_utc": read_utc, "cache_age_seconds": round(age) if age is not None else None,
        "cache_ttl_seconds": ACTIONS_TTL_SECONDS, "stale": error is not None,
        "error": error, "API_errors": api_errors,
    }


def _actions(cache_dir: Path, root: Path, run: Callable[..., Any], now: float, sources: dict | None = None) -> dict[str, Any]:
    # The service timer, path watch and reviewer may collect concurrently.
    # A separate, stable inode coordinates the native CLI call across processes.
    try:
        with _directory(cache_dir, create=True) as directory:
            _destination(directory, "fleet-actions.json")
            _destination(directory, "fleet-actions.lock")
            lock = os.open("fleet-actions.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, mode=0o600, dir_fd=directory)
            try:
                if not stat.S_ISREG(os.fstat(lock).st_mode):
                    raise OSError("nonregular cache lock rejected")
                fcntl.flock(lock, fcntl.LOCK_EX)
                return _actions_locked(cache_dir, root, run, time.time(), sources)
            finally:
                os.close(lock)
    except OSError:
        return {
            "runs": [], "workflow_names": _workflow_names(root, sources),
            "scope": "Newest 100 repository runs, filtered to workflows that invoke models",
            "read_utc": None, "cache_age_seconds": None,
            "cache_ttl_seconds": ACTIONS_TTL_SECONDS, "stale": True,
            "error": "Actions cache unavailable; native call skipped", "API_errors": [],
        }


def _ledger(path: Path, now: str, jobs: Any, root: Path, sources: dict) -> dict[str, Any]:
    jobs_running = _count(jobs) if not isinstance(jobs, list) else len(jobs)
    raw, receipt = _read_source(path, root, sources, kind="API ledger")
    result = {"read_utc": receipt.get("read_utc"), "file_utc": receipt.get("file_utc"), "jobs_running": jobs_running, "spend_usd": None, "ceiling_usd": None, "source": receipt}
    if raw is None:
        return {**result, "status": "ledger unavailable"}
    # Match native fleet_block.py's per-key event sums (325-343, SHA-256
    # b7b6936e421682da7d699e3f22e8fdf04a2e838c8dff4b8bace60e88edd77cf3).
    # Reserved max_usd amounts are distinct from a CC global credit ceiling.
    try:
        nonblank = [line for line in raw.decode("utf-8").splitlines() if line.strip()]
        sums = {"actual_usd": None, "max_usd": None}
        for line in nonblank:
            row = json.loads(line)
            if not isinstance(row, dict):
                continue
            for key in sums:
                value = _number(row.get(key))
                if value is not None:
                    sums[key] = round((sums[key] or 0) + value, 4)
        if not nonblank:
            return {**result, "status": "no spend yet", "spend_usd": 0, "reserved_max_usd": 0}
        result.update(spend_usd=sums["actual_usd"], reserved_max_usd=sums["max_usd"])
        return {**result, "status": "observed" if result["spend_usd"] is not None else "ledger spend not observed"}
    except (ValueError, UnicodeError):
        return {**result, "status": "ledger unavailable"}


def _exec_reads(value: Any) -> list[dict] | None:
    if not isinstance(value, list):
        return None
    rows = []
    for entry in value[:200]:
        if isinstance(entry, str):
            match = re.fullmatch(r"(.+)\[(fast|standard)\]", entry)
            name, tier = (match[1], match[2]) if match else (entry, None)
        elif isinstance(entry, dict):
            name, tier = entry.get("name"), entry.get("tier")
            if tier not in (None, "fast", "standard"):
                return None
        else:
            return None
        if not _identifier(name):
            return None
        rows.append({"name": name, "tier": tier})
    return rows


def _roster(value: Any, kind: str) -> bool:
    # An explicit empty list reports zero. A nonempty list must contain at
    # least one publishable row; individual rejected rows do not erase peers.
    if not isinstance(value, list):
        return False
    if not value:
        return True
    if kind == "lanes_live":
        return any(_lane(row) is not None for row in value[:200])
    if kind == "lanes_parked":
        return _names(value) is not None
    if kind == "claude_sessions":
        return any(isinstance(row, dict) and _identifier(row.get("name")) for row in value[:100])
    if kind == "pool_accounts":
        return any(isinstance(row, dict) and isinstance(row.get("account"), str) and _POOL_LABEL.fullmatch(row["account"]) for row in value[:100])
    return False


# hcom 0.7.28 list.rs b2a7c192: explicit identities are fatal when stopped;
# the standalone roster command tolerates the absence of a sender identity.
HCOM_TRACKING_COMMAND = ["hcom", "list", "--format", "{name}|{base_name}|{tool}|{tag}|{status}|{status_age_seconds}|{created_at}"]
VLLM_STATE_PROPERTIES = ("LoadState", "ActiveState", "SubState", "UnitFileState")
VLLM_STATE_COMMAND = ["systemctl", "--user", "show", "vllm-embed.service"] + ["--property=" + name for name in VLLM_STATE_PROPERTIES] + ["--no-pager"]
TRACKING_WINDOW_SECONDS = 300
TRACKING_MAX_AGE_SECONDS = 120
TRACKING_TIMEOUT_SECONDS = 2.0
_TRACKING_ENDPOINT = "http://127.0.0.1:21090"
_GRAFANA_ENDPOINT = "http://127.0.0.1:21301"
_HEALTH_ROUTES = {"http://127.0.0.1:28231/health", "http://127.0.0.1:8888/health", "http://127.0.0.1:29374/healthz"}
_CODEX_RATE_QUALIFICATION = "Lower bound until deployed start-timestamp ingestion and a newly born single-turn reconciliation pass."
_TRACKING_RATE_FAMILIES = (
    ("api_requests", "API requests", "codex_api_request_total", "Native API attempts, including retries; these are not completed user turns."),
    ("tool_calls", "Tool calls", "codex_tool_call_total", "Native tool-call counter; separate from API attempts and tool-result records."),
    ("mcp_calls", "MCP calls", "codex_mcp_call_total", "Native MCP calls; separate from outer tool results and general tool calls."),
    ("skill_invocations", "Skill invocations", None, "Skill activation coverage requires a qualified native producer; skill reads are not substituted."),
    ("agent_invocations", "Agent invocations", None, "Agent invocation coverage requires a qualified native producer; delegation and completion records are not substituted."),
)


def _workstation_module():
    spec = importlib.util.spec_from_file_location("fleet_tracking_workstation", Path(__file__).with_name("workstation.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _tracking_fetch(query, *, timeout):
    # Reuse the native loopback/no-proxy/no-redirect bounded Prometheus client.
    return _workstation_module()._fetch(query, timeout=timeout)


def _tracking_probe(url, *, timeout):
    from urllib.error import HTTPError
    from urllib.request import ProxyHandler, build_opener
    if url not in _HEALTH_ROUTES:
        raise ValueError("unreviewed tracking health route")
    module = _workstation_module()
    try:
        with build_opener(ProxyHandler({}), module._NoRedirect()).open(url, timeout=timeout) as response:
            return response.status  # The response body is neither read nor retained.
    except HTTPError as error:
        code = error.code
        error.close()
        if 300 <= code < 400:
            raise ValueError("health redirect refused") from None
        return code


def _tracking_numeric(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        return None
    try:
        result = float(value)
    except (ValueError, OverflowError):
        return None
    return result if math.isfinite(result) and result >= 0 else None


def _tracking_stamp(value):
    value = _tracking_numeric(value)
    try:
        return _utc(value) if value is not None else None
    except (ValueError, OverflowError, OSError):
        return None


def _tracking_hcom(run, now):
    clock = now if callable(now) else lambda: now
    observed = clock()
    result = {"status": "UNKNOWN", "agents": None, "count": None, "rejected_rows": None, "read_utc": _utc(observed),
              "source": {"command": HCOM_TRACKING_COMMAND.copy()}, "reason": None}
    try:
        native = run(HCOM_TRACKING_COMMAND.copy(), capture_output=True, text=True, timeout=TRACKING_TIMEOUT_SECONDS)
        observed = clock()
        result["read_utc"] = _utc(observed)
        if native.returncode or not isinstance(native.stdout, str) or len(native.stdout.encode("utf-8")) > MAX_SOURCE_BYTES:
            raise ValueError("native roster unavailable or oversized")
        agents, rejected = [], 0
        for line in native.stdout.splitlines():
            if not line:
                continue
            fields = line.split("|")
            if len(fields) != 7:
                rejected += 1
                continue
            name, base, tool, tag, status, age, created = fields
            if (not all(_identifier(value) for value in (name, base, tool)) or tag and not _identifier(tag)
                    or status not in {"active", "listening", "blocked", "inactive", "unknown", "launching", "error"}):
                rejected += 1
                continue
            age, created = _tracking_numeric(age), _tracking_numeric(created)
            if age is None or created is None or created > observed or _tracking_stamp(created) is None:
                rejected += 1
                continue
            agents.append({"name": name, "base_name": base, "tool": tool, "tag": tag or None,
                           "status": status, "status_age_seconds": age, "created_at": created})
        result["rejected_rows"] = rejected
        if rejected and not agents:
            raise ValueError("all native roster rows were rejected")
        result.update(status="reported", agents=agents, count=len(agents),
                      reason=f"Rejected {rejected} invalid native roster rows; the published count covers accepted rows only." if rejected else None)
    except (OSError, subprocess.SubprocessError, ValueError, TypeError, AttributeError, OverflowError) as error:
        result["reason"] = "Native hcom roster is UNKNOWN (" + type(error).__name__ + ")."
    return result


def _tracking_manager(run, now):
    values, reason = {}, None
    try:
        native = run(VLLM_STATE_COMMAND.copy(), capture_output=True, text=True, timeout=TRACKING_TIMEOUT_SECONDS)
        if not isinstance(native.stdout, str) or len(native.stdout.encode("utf-8")) > 4096:
            raise ValueError("user-manager properties are unavailable")
        for line in native.stdout.splitlines():
            key, separator, value = line.partition("=")
            if (not separator or key not in VLLM_STATE_PROPERTIES or key in values
                    or not (re.fullmatch(r"[a-z][a-z0-9-]{0,47}", value) or key == "UnitFileState" and value == "")):
                raise ValueError("user-manager property projection is malformed")
            values[key] = value
        if set(values) != set(VLLM_STATE_PROPERTIES):
            raise ValueError("user-manager property projection is incomplete")
        missing = values["LoadState"] == "not-found"
        if (native.returncode and not (native.returncode == 1 and missing)) or (not values["UnitFileState"] and not missing):
            raise ValueError("user-manager property projection is unavailable")
    except (OSError, subprocess.SubprocessError, ValueError, TypeError, AttributeError) as error:
        values, reason = {}, "User-manager state is UNKNOWN (" + type(error).__name__ + ")."
    observed = now() if callable(now) else now
    return [{"metric": name, "value": values.get(name) or None, "unit": "state", "status": "UNKNOWN" if reason or not values.get(name) else "reported",
             "reason": reason or ("No installation state is reported for a not-found unit." if not values.get(name) else None),
             "source_sample_utc": None if reason or not values.get(name) else _utc(observed), "evaluated_utc": _utc(observed), "query": " ".join(VLLM_STATE_COMMAND),
             "source": "native systemctl --user show", "scope": "User-manager property of vllm-embed.service only; no model readiness or port binding is inferred."}
            for name in VLLM_STATE_PROPERTIES]


def _tracking_series(fetch, query, keys):
    try:
        payload = fetch(query, timeout=TRACKING_TIMEOUT_SECONDS)
        data = payload.get("data") if isinstance(payload, dict) else None
        if (payload.get("status") != "success" or payload.get("warnings") or not isinstance(data, dict)
                or data.get("resultType") != "vector" or not isinstance(data.get("result"), list) or len(data["result"]) > 2000):
            raise ValueError("Prometheus result is not a bounded successful vector")
        result = {}
        for row in data["result"]:
            if not isinstance(row, dict) or not isinstance(row.get("metric"), dict):
                raise ValueError("Prometheus series shape is malformed")
            identity = tuple(row["metric"].get(key) for key in keys)
            if not all(_identifier(value) for value in identity):
                raise ValueError("Prometheus series labels are missing or unsafe")
            pair = row.get("value")
            pair = pair if isinstance(pair, list) and len(pair) == 2 else [None, None]
            value, evaluated = _tracking_numeric(pair[1]), _tracking_numeric(pair[0])
            reason = None if value is not None and _tracking_stamp(evaluated) else "Prometheus observation is nonfinite or malformed"
            if identity in result:
                value, reason = None, "Prometheus grouped observation is duplicated"
            result[identity] = {"value": value, "evaluated": evaluated, "reason": reason}
        return result, None
    except (OSError, HTTPException, ValueError, TypeError, KeyError, AttributeError, OverflowError, RecursionError) as error:
        return {}, "Prometheus observation is UNKNOWN (" + type(error).__name__ + ")."


def _tracking_measurement(row, source, *, query, fresh_query, unit, now, scope, window=None, error=None, fresh_error=None, lower_bound=False):
    row, source = row or {}, source or {}
    epoch = source.get("value")
    stamp = _tracking_stamp(epoch)
    reason = error or row.get("reason") or fresh_error or source.get("reason")
    if not reason:
        if not row or row.get("value") is None:
            reason = "Measured series is absent; no zero was inferred."
        elif stamp is None:
            reason = "Underlying source sample timestamp is absent or invalid."
        elif epoch > now:
            reason = "Underlying source sample timestamp is in the future."
        elif now - epoch > TRACKING_MAX_AGE_SECONDS:
            reason = "Underlying source sample is stale."
        elif window is not None and row["value"] == 0:
            reason = "A zero rate has no qualified full-window writer coverage; no measured zero is published."
    status = "UNKNOWN" if reason else "lower bound" if lower_bound else "reported"
    return {"value": None if reason else row["value"], "unit": unit, "status": status,
            "reason": reason or (_CODEX_RATE_QUALIFICATION if lower_bound else None),
            "source_sample_utc": stamp, "evaluated_utc": _tracking_stamp(row.get("evaluated")), "query": query,
            "freshness_query": fresh_query, "window_seconds": window, "scope": scope,
            "source": _TRACKING_ENDPOINT, "max_source_age_seconds": TRACKING_MAX_AGE_SECONDS}


def _tracking_explore(lane, by_client, now):
    # Grafana v13.2.3 Explore's documented panes schema; no dashboard variable
    # or organization ID is inferred. Datasource UID: ns2604_dashboards.py:7-8.
    expressions = dict.fromkeys(row["query"] for client in by_client.values()
                                for row in client["tokens"] + client["rates"] if row.get("query"))
    queries = [{"refId": chr(65 + index), "datasource": {"uid": "ns2604-prometheus", "type": "prometheus"},
                "expr": expression.replace('ecosystem_lane!=""', "ecosystem_lane=" + json.dumps(lane)), "range": True}
               for index, expression in enumerate(expressions)]
    pane = {"datasource": "ns2604-prometheus", "queries": queries,
            "range": {"from": str(int((now - TRACKING_WINDOW_SECONDS) * 1000)), "to": str(int(now * 1000))}}
    return {"title": lane + " · Explore rates", "lane": lane, "uid": "ns2604-prometheus",
            "url": _GRAFANA_ENDPOINT + "/explore?" + urlencode({"panes": json.dumps({"fleet": pane}, separators=(",", ":")), "schemaVersion": "1"})}


def collect_tracking(*, run=None, fetch=None, probe=None, now=None):
    """Observe native roster and telemetry without treating them as one population.

    Primary contracts: hcom 0.7.28 list.rs b2a7c192003e7fd67ed93265289e4ac36276f965;
    observability/lanes_dashboard.py and native-lane-invocation ADR; Prometheus
    rate/timestamp APIs. Token categories are separate; rate runs before sum.
    The ADR's start-timestamp/reconciliation gate remains unqualified here.
    """
    live_clock = now is None
    now = time.time() if live_clock else now
    def read_time():
        return time.time() if live_clock else now
    run, fetch, probe = run or subprocess.run, fetch or _tracking_fetch, probe or _tracking_probe
    hcom = _tracking_hcom(run, read_time)
    clients, query_observations = {}, []
    def observed_query(query, keys, client, measurement):
        rows, reason = _tracking_series(fetch, query, keys)
        query_observations.append({"client": client, "measurement": measurement, "status": "UNKNOWN" if reason else "reported",
                                   "reason": reason or ("No matching series in this returned result; no zero or absence of writers is inferred." if not rows else None),
                                   "query": query, "source": _TRACKING_ENDPOINT, "read_utc": _utc(read_time()), "series_count": None if reason else len(rows)})
        return rows, reason
    for client, counter, label in (("codex", "codex_turn_token_usage_sum", "token_type"),
                                   ("claude", "claude_code_token_usage_tokens_total", "type")):
        selector = counter + '{ecosystem_lane!="",instance!="unscoped"}'
        grouping = "ecosystem_lane," + label
        query = f"sum by ({grouping}) (rate({selector}[5m]))"
        fresh_query = f"max by ({grouping}) (timestamp({selector}))"
        values, error = observed_query(query, ("ecosystem_lane", label), client, "token rates")
        freshness, fresh_error = observed_query(fresh_query, ("ecosystem_lane", label), client, "token source samples")
        for lane, kind in sorted(set(values) | set(freshness)):
            row = _tracking_measurement(values.get((lane, kind)), freshness.get((lane, kind)), query=query, fresh_query=fresh_query,
                                        unit="tokens/s", now=read_time(), window=TRACKING_WINDOW_SECONDS, error=error, fresh_error=fresh_error,
                                        scope="Native token category; categories are not added together." + (" " + _CODEX_RATE_QUALIFICATION if client == "codex" else ""),
                                        lower_bound=client == "codex")
            row["token_type"] = kind
            clients.setdefault(lane, {}).setdefault(client, {"client": client, "tokens": [], "source_refs": ["observability/lanes_dashboard.py"]})["tokens"].append(row)
    codex_rates = {}
    # API/tool/MCP counters are independently qualified in the retained native
    # Fleet source packet; they must never be collapsed to one invoke count.
    for family, label, counter, scope in _TRACKING_RATE_FAMILIES:
        if counter is None:
            continue
        selector = counter + '{ecosystem_lane!="",instance!="unscoped"}'
        query = f"sum by (ecosystem_lane) (rate({selector}[5m]))"
        fresh_query = f"max by (ecosystem_lane) (timestamp({selector}))"
        values, error = observed_query(query, ("ecosystem_lane",), "codex", label + " rates")
        freshness, fresh_error = observed_query(fresh_query, ("ecosystem_lane",), "codex", label + " source samples")
        codex_rates[family] = (values, freshness, query, fresh_query, error, fresh_error)
        for lane, in sorted(set(values) | set(freshness)):
            clients.setdefault(lane, {}).setdefault("codex", {"client": "codex", "tokens": [], "source_refs": ["observability/lanes_dashboard.py"]})
    for lane, by_client in clients.items():
        for client, row in by_client.items():
            row["rates"] = []
            for family, label, counter, scope in _TRACKING_RATE_FAMILIES:
                if client == "codex" and counter:
                    values, freshness, query, fresh_query, error, fresh_error = codex_rates[family]
                    rate = _tracking_measurement(values.get((lane,)), freshness.get((lane,)), query=query, fresh_query=fresh_query,
                                                 unit="calls/s", now=read_time(), window=TRACKING_WINDOW_SECONDS, error=error, fresh_error=fresh_error,
                                                 scope=scope + " " + _CODEX_RATE_QUALIFICATION, lower_bound=True)
                else:
                    reason = f"A native {client.title()} {label.lower()} rate producer and full-window coverage are not qualified."
                    if client == "claude":
                        reason += " Native Loki event contracts exist; a numeric rate transport and source-freshness contract are not qualified for this collector."
                    rate = _tracking_measurement(None, None, query=None, fresh_query=None, unit="calls/s", now=read_time(),
                                                 window=TRACKING_WINDOW_SECONDS, scope=scope, error=reason)
                    rate["source"] = None
                rate.update(family=family, label=label)
                row["rates"].append(rate)
            row["invocations"] = next(rate for rate in row["rates"] if rate["family"] == "mcp_calls")
            row["source_refs"].append("docs/decisions/2026-10-06-native-lane-invocation-observability.md")
    query, fresh_query = 'up{job="workstation-vllm"}', 'timestamp(up{job="workstation-vllm"})'
    values, error = observed_query(query, ("job",), "vllm-embed", "scrape availability")
    freshness, fresh_error = observed_query(fresh_query, ("job",), "vllm-embed", "scrape source sample")
    vllm = _tracking_measurement(values.get(("workstation-vllm",)), freshness.get(("workstation-vllm",)), query=query, fresh_query=fresh_query,
                                 unit="native metric value", now=read_time(), error=error, fresh_error=fresh_error,
                                 scope="Prometheus scrape availability; this does not establish embedding or model readiness.")
    vllm["metric"] = "up"
    if vllm["status"] == "reported" and vllm["value"] not in (0, 1):
        vllm.update(status="UNKNOWN", value=None, reason="Native scrape availability is not zero or one.")
    services = [{"id": "vllm-embed", "title": "vLLM embedding service", "observations": [vllm], "source_refs": ["observability/lanes_dashboard.py"]}]
    services[0]["observations"].extend(_tracking_manager(run, read_time))
    for identity, title, url, scope, source in (
        # CC's 2026-10-09 host measurement corrects the old distro's 8231 route.
        ("vllm-embed", "vLLM embedding service", "http://127.0.0.1:28231/health", "Host port 28231 measured by the command center; HTTP health remains independent of the separate Prometheus scrape job.", "docs/hf-memory-model-qualification.md"),
        ("hindsight", "Hindsight", "http://127.0.0.1:8888/health", "Database reachability only; no LLM or model readiness is established.", "recipes/hindsight-research-memory.md"),
        ("ai-memory", "ai-memory", "http://127.0.0.1:29374/healthz", "Unauthenticated process liveness only; no store, provider, or auth state is read.", "observability/ns2604_dashboards.py"),
    ):
        value, reason = None, None
        try:
            value = probe(url, timeout=TRACKING_TIMEOUT_SECONDS)
            if isinstance(value, bool) or not isinstance(value, int) or not 100 <= value <= 599:
                raise ValueError("health HTTP status is unavailable")
        except (OSError, HTTPException, ValueError, TypeError, AttributeError) as exc:
            reason = "Health-route observation is UNKNOWN (" + type(exc).__name__ + ")."
        reading = _utc(read_time())
        observation = {"metric": "HTTP status", "value": None if reason else value, "unit": "HTTP status",
                       "status": "UNKNOWN" if reason else "reported", "reason": reason, "source_sample_utc": None if reason else reading,
                       "evaluated_utc": reading, "query": url, "scope": scope, "source": url}
        existing = next((row for row in services if row["id"] == identity), None)
        if existing:
            existing["observations"].append(observation)
            existing["source_refs"].append(source)
        else:
            services.append({"id": identity, "title": title, "observations": [observation], "source_refs": [source]})
    return {"schema": "fleet-tracking/1", "observed_utc": _utc(now), "hcom": hcom,
            "lanes": [{"lane": lane, "clients": list(by_client.values()), "source_refs": ["observability/lanes_dashboard.py"]} for lane, by_client in sorted(clients.items())],
            "services": services, "query_observations": query_observations, "grafana": {"base_url": _GRAFANA_ENDPOINT, "links": [
                {"title": title, "uid": uid, "url": _GRAFANA_ENDPOINT + path} for title, uid, path in (
                    ("Lane monitoring", "cc-lanes", "/d/cc-lanes/lanes"),
                    ("Native agent ecosystem", "ecosystem-native", "/d/ecosystem-native/native-agent-ecosystem"),
                    ("Foundation services", "native-foundation-data", "/d/native-foundation-data/253abf9"),
                )] + [_tracking_explore(lane, by_client, now) for lane, by_client in sorted(clients.items())],
                "source_refs": ["observability/ns2604_dashboards.py", "observability/lanes_dashboard.py"]},
            "limitations": ["Live hcom rows and historical telemetry labels are separate observations; no name join is inferred.",
                            "Token categories retain native inclusion semantics and must not be added together.",
                            "Prometheus rate handles counter resets before writer aggregation over five minutes.",
                            "Source freshness is the latest underlying scrape among grouped writers; it is not last invocation time or coverage of every writer.",
                            _CODEX_RATE_QUALIFICATION,
                            "Unscoped writers are excluded; remaining writer coverage is not qualified for measured rate zeros.",
                            "Claude API requests, tool, MCP, skill and agent rates remain UNKNOWN until numeric event-rate transport and source freshness are qualified.",
                            "Missing, stale or unqualified zero rates remain UNKNOWN; reported service zeros remain zero."]}


def collect(state_root: Path, cache_dir: Path, root: Path, run: Callable[..., Any] | None = None,
            *, tracking_run=None, tracking_fetch=None, tracking_probe=None) -> dict[str, Any]:
    """Collect once per page refresh; returned data contains no source free text.

    ``run`` has subprocess.run's calling convention and enables offline tests.
    Unknown observations stay None. A failed direct fleet read uses the dated
    snapshot for all native sections; the co-op list always uses that snapshot.
    """
    run = run or subprocess.run
    now = time.time()
    observed = _utc(now)
    inputs = {}
    # Publish the independently cached Actions observation before attempting
    # a native producer that may consume its whole timeout budget.
    actions = _actions(cache_dir, root, run, now, inputs)
    snapshot_path = state_root / "coordination/ns2604-coop/watchers/fleet-now.json"
    snapshot = _read_json(snapshot_path, state_root, inputs, kind="Fleet snapshot")
    snapshot = snapshot if snapshot.get("schema") == "coop-fleet/1" else {}
    fleet, source = snapshot, "snapshot" if snapshot else "unavailable"
    producer_path = state_root / "coordination/ns2604-coop/tools/fleet_block.py"
    try:
        producer, producer_receipt = _read_source(producer_path, state_root, inputs, kind="native Fleet producer")
        if producer is None:
            raise ValueError("native producer unavailable")
        result = _execute_producer(producer_path, producer, producer_receipt, run)
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
    cc = _read_json(cc_path, state_root, inputs, kind="CC current view")
    cc = cc if cc.get("schema") == "cc-now/1" else {}
    tiers = _tiers(_read_json(tier_path, state_root, inputs, kind="lane tier policy"))
    tiers["source"] = inputs.get(str(tier_path.absolute()))
    cc_agents = cc.get("cc_agents") if isinstance(cc.get("cc_agents"), dict) else {}
    cc_running = cc_agents.get("running") if isinstance(cc_agents.get("running"), list) else None
    if cc_running is not None and not all(isinstance(row, dict) and _identifier(row.get("name")) for row in cc_running[:100]):
        cc_running = None
    availability = {}
    def section(key, valid):
        for document, label, stamp in ((fleet, source, native_time), (snapshot, "snapshot", snapshot_time)):
            value = document.get(key)
            if label != "unavailable" and valid(value):
                availability[key] = {"status": "snapshot fallback" if label == "snapshot" else "reported", "source": label, "read_utc": stamp, "reason": None}
                return value
        availability[key] = {"status": "not reported", "source": "unavailable", "read_utc": None, "reason": "source section absent, null or malformed"}
        return None
    live = section("lanes_live", lambda value: _roster(value, "lanes_live"))
    parked_value = section("lanes_parked", lambda value: _roster(value, "lanes_parked"))
    parked = _names(parked_value)
    subgroup = fleet.get("claude_subagents_running") if isinstance(fleet.get("claude_subagents_running"), dict) else {}
    snap_subgroup = snapshot.get("claude_subagents_running") if isinstance(snapshot.get("claude_subagents_running"), dict) else {}
    subagents = {}
    for group in ("coop", "native_cc", "api_actions"):
        key = "cc" if group == "native_cc" else group
        value = snap_subgroup.get(key) if group == "coop" else subgroup.get(key)
        group_source, group_time = ("snapshot", snapshot_time) if group == "coop" else (source, native_time)
        names = _names(value)
        if group != "coop" and names is None:
            snapshot_names = _names(snap_subgroup.get(key))
            if snapshot_names is not None:
                value, names, group_source, group_time = snap_subgroup[key], snapshot_names, "snapshot", snapshot_time
        subagents[group] = {"names": names, "count": len(value) if names is not None else None, "read_utc": group_time if names is not None else None, "source": group_source if names is not None else "unavailable"}
    cc_time = _stamp(cc.get("updated_utc"))
    cc_names = _names(cc_running)
    subagents["cc"] = {"names": cc_names, "count": len(cc_running) if cc_running is not None else None, "read_utc": cc_time if cc_running is not None else None, "source": "cc-now" if cc_running is not None else "unavailable"}
    availability["cc_agents"] = {"status": "reported" if cc_running is not None else "not reported", "source": "cc-now" if cc_running is not None else "unavailable", "read_utc": cc_time if cc_running is not None else None, "reason": None if cc_running is not None else "CC running-agent section absent, null or malformed"}
    sessions = section("claude_sessions", lambda value: _roster(value, "claude_sessions"))
    accounts = section("pool_accounts", lambda value: _roster(value, "pool_accounts"))
    reads = section("exec_reads_in_flight", lambda value: _exec_reads(value) is not None)
    jobs = section("sdk_jobs_running", lambda value: isinstance(value, list) or _count(value) is not None)
    ledger_path = state_root / "coordination/api-actions-20261008/api-actions-ledger.jsonl"
    native_ledger = fleet.get("api_spend_ledger")
    if isinstance(native_ledger, dict) and isinstance(native_ledger.get("sums"), dict):
        ledger_rows = _count(native_ledger.get("rows"))
        empty_ledger = ledger_rows == 0 and not native_ledger["sums"]
        sdk = {
            "read_utc": native_time, "file_utc": None,
            "jobs_running": len(jobs) if isinstance(jobs, list) else _count(jobs),
            "spend_usd": 0 if empty_ledger else _number(native_ledger["sums"].get("actual_usd")),
            "reserved_max_usd": 0 if empty_ledger else _number(native_ledger["sums"].get("max_usd")),
            "ceiling_usd": None,
            "status": "no spend yet" if empty_ledger else "native ledger observation" if source == "direct" else "snapshot ledger observation",
            "ledger_source": "coop-fleet api_spend_ledger", "ledger_rows": ledger_rows,
            "ledger_last_utc": _stamp(native_ledger.get("last")),
        }
    else:
        sdk = _ledger(ledger_path, observed, jobs, state_root, inputs)
    credit = cc.get("api_credit") if isinstance(cc.get("api_credit"), dict) else {}
    ceiling = _number(credit.get("ceiling_usd"))
    if ceiling is not None:
        sdk.update(ceiling_usd=ceiling, ceiling_source="cc-now api_credit", ceiling_read_utc=_stamp(cc.get("updated_utc")))
    for field in ("stop_and_report_at_usd", "table_at_caps_usd", "table_expected_usd"):
        sdk[field] = _number(credit.get(field))
    source_label = {"direct": "direct native", "snapshot": "snapshot fallback", "unavailable": "not reported"}[source]
    try:
        tracking = collect_tracking(run=tracking_run or run, fetch=tracking_fetch, probe=tracking_probe)
    except Exception as error:
        # Optional adapters must not take the independently collected Fleet,
        # ledger or Actions observations down. Never retain exception payloads.
        tracking = {"schema": "fleet-tracking/1", "status": "UNKNOWN", "observed_utc": _utc(time.time()),
                    "reason": "Optional tracking collection is UNKNOWN (" + type(error).__name__ + ")."}
    return {
        "schema": "local-fleet/1", "observed_utc": observed, "at": native_time,
        "fleet_source": source_label,
        "lanes_live": [safe for row in live[:200] if (safe := _lane(row))] if live is not None else None,
        "lanes_parked": [{"lane": lane, "tier": ("fast" if lane in tiers["fast"] else tiers["default"]) if tiers["fast"] is not None else None, "cli_version": None, "expected_cli_version": tiers["versions"]["hold"].get(lane, tiers["versions"]["default"])} for lane in parked] if parked is not None else None,
        "claude_sessions": [{"name": name, "status": _status(row.get("status"))} for row in sessions[:100] if isinstance(row, dict) and (name := _identifier(row.get("name")))] if sessions is not None else None,
        "claude_subagents_running": subagents,
        "cc_agents": {"running": [{"name": _identifier(row.get("name")), "type": _identifier(row.get("type"))} for row in cc_running[:100] if isinstance(row, dict)] if cc_running is not None else None, "running_count": len(cc_running) if cc_running is not None else None, "read_utc": cc_time},
        "exec_reads_in_flight": _exec_reads(reads),
        "sdk": sdk, "actions": {key: value for key, value in actions.items() if key != "API_errors"},
        "pool_accounts": [{"account": row["account"], "used_pct": _number(row.get("used_pct"), 100)} for row in accounts[:100] if isinstance(row, dict) and isinstance(row.get("account"), str) and _POOL_LABEL.fullmatch(row["account"])] if accounts is not None else None,
        "fresh_total_pct": _number(fleet.get("fresh_total_pct")), "tiers": tiers,
        "totals": {key: _count(fleet.get("totals", {}).get(key)) for key in ("lanes_live", "lanes_parked", "codex_subagents_running", "claude_subagents_running", "claude_subagents_not_reported", "exec_reads_in_flight", "sdk_jobs_running")} if isinstance(fleet.get("totals"), dict) else {},
        "availability": availability, "source_inputs": list(inputs.values()),
        "section_counts": {key: len(value) if isinstance(value, list) else None for key, value in (("lanes_live", live), ("lanes_parked", parked_value), ("claude_sessions", sessions), ("exec_reads_in_flight", reads))},
        "source_times": {"fleet_direct": native_time if source == "direct" else None, "fleet_snapshot": snapshot_time, "cc_now": cc_time, "lane_tiers": tiers["read_utc"], "api_ledger": sdk["read_utc"], "actions": actions["read_utc"]},
        "source_notes": ["Co-op subagents use the separately dated fleet snapshot; CC agents use the CC current view.", "Missing source sections and ledger amounts remain unknown."] + (["Direct fleet collection unavailable; dated snapshot used."] if source == "snapshot" else []),
        "errors": (["Fleet collection not reported."] if source == "unavailable" else []),
        "API_errors": actions["API_errors"],
        "tracking": tracking,
    }
