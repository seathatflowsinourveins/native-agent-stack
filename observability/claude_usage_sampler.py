#!/usr/bin/env python3
"""CC-owned bounded sampler. Tests select a fixture client; lanes never run real probes.

Only explicit non-secret identity files are read. The native client owns its
authentication; this module never opens credentials, settings or account caches.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import time

if __package__:
    from .claude_usage_metrics import InputError, collect, number, read_data, save_state, WINDOWS, STATUSES
else:
    from claude_usage_metrics import InputError, collect, number, read_data, save_state, WINDOWS, STATUSES

INTERVAL = 900
MAX_TIMEOUT = 180
COMMAND = ["-p", "Reply with the single word ok.", "--tools", "", "--strict-mcp-config",
           "--setting-sources", "local", "--permission-mode", "dontAsk", "--max-turns", "1",
           "--max-budget-usd", "0.2", "--output-format", "stream-json", "--verbose", "--no-session-persistence"]


def accounts_from_file(path):
    try:
        rows = json.loads(read_data(path, 64 * 1024)[0])
    except (ValueError, RecursionError):
        raise InputError("invalid account file") from None
    if not isinstance(rows, list) or not 1 <= len(rows) <= 8:
        raise InputError("account pool must contain one to eight entries")
    accounts = {}
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"identity_file", "config_dir"}:
            raise InputError("account file requires identity and runtime directory paths")
        if not all(isinstance(row[k], str) and row[k] for k in row):
            raise InputError("invalid account file path")
        identity = Path(row["identity_file"])
        config = Path(row["config_dir"])
        # The identity contract is a CC-created, non-secret single-line file,
        # explicitly separate from the native client's credential directory.
        if not identity.is_absolute() or not config.is_absolute() or identity.is_relative_to(config):
            raise InputError("identity must be an explicit file outside the runtime directory")
        if identity.name in (".claude.json", "credentials.json", ".credentials.json"):
            raise InputError("identity file cannot be a credential or account cache")
        metadata = identity.lstat()
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_mode & 0o077 or not config.is_dir():
            raise InputError("identity requires a private regular file and a runtime directory")
        content = read_data(identity, 1024)[0].strip()
        if not content or "\n" in content or "\r" in content or content.startswith(("sk-", "{", "[")):
            raise InputError("identity must be a non-secret stable identifier")
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        del content
        if digest in accounts:
            raise InputError("duplicate account identity")
        accounts[digest] = config
    return accounts


def check_fence(workdir):
    if workdir.is_symlink():
        raise InputError("probe directory must not be a symlink")
    workdir.mkdir(parents=True, exist_ok=True, mode=0o700)
    if workdir.stat().st_mode & 0o077:
        raise InputError("probe directory must be private")
    # Metadata checks only, including dangling symlinks. Never read settings.
    for parent in (workdir.resolve(), *workdir.resolve().parents):
        if os.path.lexists(parent / ".claude/settings.local.json"):
            raise InputError("local settings are present; probe fence refused")


def sanitized_events(output):
    """Keep bounded native numeric/status fields only; discard all other output."""
    if len(output) > 2 * 1024 * 1024:
        raise InputError("probe output exceeds size bound")
    lines = []
    for line in output.decode("utf-8", errors="replace").splitlines():
        try:
            event = json.loads(line)
        except (ValueError, RecursionError):
            lines.append("{invalid}")  # bounded marker, never raw input
            continue
        if not isinstance(event, dict) or event.get("type") != "rate_limit_event":
            continue
        info = event.get("rate_limit_info")
        if not isinstance(info, dict) or info.get("status") not in STATUSES:
            lines.append("{invalid}")
            continue

        def fields(source):
            kept = {}
            for field in ("utilization", "resetsAt"):
                if field in source:
                    value = number(source[field])
                    kept[field] = value if value is not None else "invalid"
            if "status" in source:
                kept["status"] = source["status"] if source["status"] in STATUSES else "invalid"
            return kept

        clean = fields(info)
        scope = info.get("rateLimitType")
        if scope in (*WINDOWS, "seven_day_opus", "seven_day_sonnet", "overage"):
            clean["rateLimitType"] = scope
        windows = info.get("unifiedWindows", {})
        if isinstance(windows, dict):
            clean["unifiedWindows"] = {w: fields(v) if isinstance(v, dict) else "invalid"
                                       for w, v in windows.items() if w in WINDOWS}
        lines.append(json.dumps({"type": "rate_limit_event", "rate_limit_info": clean}, allow_nan=False))
    return "\n".join(lines) + "\n"


def publish_capture(path, text, stamp):
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, prefix="capture.", delete=False) as target:
        temporary = Path(target.name)
        try:
            target.write(text)
            target.flush()
            os.fsync(target.fileno())
            os.utime(temporary, (stamp, stamp))
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


def load_sampler_state(path):
    if not path.exists():
        return {"version": 1, "account_indexes": {}}
    try:
        raw = json.loads(read_data(path, 1024 * 1024)[0])
        if raw["version"] != 1 or not isinstance(raw["account_indexes"], dict):
            raise InputError("invalid sampler state")
        indexes = {}
        seen = set()
        for digest, entry in raw["account_indexes"].items():
            if (len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest)
                    or not isinstance(entry, dict)):
                raise InputError("invalid sampler state")
            index = entry["index"]
            if (not isinstance(index, str) or not index.startswith("acct-")
                    or not index[5:].isdigit() or int(index[5:]) < 1 or index in seen
                    or number(entry.get("attempted_at", 0)) is None or entry.get("success", 0) not in (0, 1)):
                raise InputError("invalid sampler state")
            seen.add(index)
            indexes[digest] = {"index": index, "attempted_at": entry.get("attempted_at", 0),
                               "success": entry.get("success", 0)}
        return {"version": 1, "account_indexes": indexes}
    except (KeyError, ValueError, TypeError, RecursionError):
        raise InputError("invalid sampler state") from None


def sample(accounts_file, ledger, state, output, workdir, *, now=None, timeout=MAX_TIMEOUT, legacy_key_alias=None):
    """One cadence-locked pass; the CC runs this with its authenticated native client."""
    clock = time.time if now is None else lambda: now
    started_at = clock()
    if number(started_at) is None or started_at == 0 or not 0 < timeout <= MAX_TIMEOUT:
        raise InputError("invalid sampler bounds")
    if output.suffix != ".prom":
        raise InputError("sampler output must be a .prom textfile")
    check_fence(workdir)
    accounts = accounts_from_file(accounts_file)
    client = shutil.which("claude")
    if not client:
        raise InputError("native client is unavailable")
    state.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    data = state.parent / "captures"
    data.mkdir(exist_ok=True, mode=0o700)
    with state.with_suffix(state.suffix + ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        saved = load_sampler_state(state)
        indexes = saved["account_indexes"]
        next_index = max((int(e["index"][5:]) for e in indexes.values()), default=0) + 1
        captures, outcomes = {}, {}
        for digest, config in sorted(accounts.items()):
            attempted_at = clock()
            if digest not in indexes:
                indexes[digest] = {"index": f"acct-{next_index}", "attempted_at": 0, "success": 0}
                next_index += 1
            entry = indexes[digest]
            account = entry["index"]
            capture = data / f"{account}.jsonl"
            # Persist before launch so a crash, timeout, clock rollback or retry
            # cannot consume a second request in the same UTC calendar slot.
            # Timer jitter must not suppress the next slot's probe.
            if not entry["attempted_at"] or attempted_at // INTERVAL > entry["attempted_at"] // INTERVAL:
                check_fence(workdir)
                entry.update(attempted_at=attempted_at, success=0)
                save_state(state, saved)
                # Pass only ordinary runtime variables. API credentials and
                # parent/session telemetry environments are never read/copied.
                environment = {k: os.environ[k] for k in ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR") if k in os.environ}
                environment["CLAUDE_CONFIG_DIR"] = str(config)
                try:
                    result = subprocess.run([client, *COMMAND], cwd=workdir, env=environment,
                                            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                            stderr=subprocess.DEVNULL, timeout=timeout)
                    text = sanitized_events(result.stdout)
                    if '"type": "rate_limit_event"' in text:
                        publish_capture(capture, text, clock())
                        # A native rejected event is useful even when the CLI exits 1.
                        entry["success"] = 1
                except (OSError, subprocess.TimeoutExpired, InputError):
                    pass  # fixed numeric failure state; never print native output or exceptions
                save_state(state, saved)
            captures[account] = capture
            outcomes[account] = bool(entry["success"])
        collect(captures, ledger, state.with_name(state.stem + ".metrics.json"), output,
                now=clock(), legacy_key_alias=legacy_key_alias, capture_outcomes=outcomes)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--accounts-file", required=True, type=Path)
    parser.add_argument("--ledger", required=True, type=Path)
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--working-directory", required=True, type=Path)
    parser.add_argument("--legacy-key-alias")
    args = parser.parse_args()
    try:
        sample(args.accounts_file, args.ledger, args.state, args.output, args.working_directory,
               legacy_key_alias=args.legacy_key_alias)
    except (InputError, OSError):
        print("Claude usage sampler refused or failed; check its fence and named data files.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
