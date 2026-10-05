"""Host-local lease and private append-only lifecycle journal; no broker APIs.

Lease reference: native-agent-stack dca821cca85dce3647fa7b488d5a23fbe5b85d4a,
blueprints/us-equities/adaptive-paper/safety.py account_lock_fingerprint.
Durability uses Python's documented os.open O_APPEND/O_EXCL, flush and os.fsync.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import time


class SafetyError(RuntimeError):
    """Constant reason codes, with no private values or paths."""


def account_lock_name(account_id):
    if not isinstance(account_id, str) or not re.fullmatch(r"DU\d{5,}", account_id) or len(account_id) > 128:
        raise SafetyError("paper_account_required_for_lease")
    return hashlib.sha256(account_id.encode()).hexdigest() + ".lock"


class AccountLease:
    def __init__(self, account_id):
        self.lock_name = account_lock_name(account_id)
        state = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local/state")
        if not state.is_absolute():
            raise SafetyError("absolute_state_home_required")
        root = state / "native-agent-stack/ibkr-paper/locks"
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        root.chmod(0o700)
        self.fd = os.open(root / self.lock_name, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            os.fchmod(self.fd, 0o600)
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(self.fd)
            self.fd = None
            raise SafetyError("account_writer_already_running") from None
        except BaseException:
            os.close(self.fd)
            self.fd = None
            raise

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None


def private_output(directory, repository):
    path = Path(directory).resolve()
    if path == repository or repository in path.parents:
        raise SafetyError("private_output_must_be_outside_repository")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.chmod(0o700)
    return path


class Journal:
    """One process appends at a time; parent resumes after the child has exited."""

    def __init__(self, directory, run_id, repository, *, create, hashes=None):
        if not isinstance(run_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", run_id):
            raise SafetyError("invalid_run_id")
        root = private_output(directory, Path(repository).resolve())
        self.path = root / (run_id + ".jsonl")
        flags = os.O_APPEND | os.O_RDWR | os.O_NOFOLLOW
        flags |= os.O_CREAT | os.O_EXCL if create else 0
        try:
            fd = os.open(self.path, flags, 0o600)
        except FileExistsError:
            raise SafetyError("journal_run_already_exists") from None
        self.stream = os.fdopen(fd, "a", encoding="utf-8")
        self.run_id = run_id
        self.seen = set()
        try:
            os.fchmod(fd, 0o600)
            if create:
                self.append("run_start", run_id=run_id, **(hashes or {}))
                # Persist the file's directory entry as well as its contents.
                directory_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
            else:
                records = self.records()
                if not records or records[0].get("kind") != "run_start" or records[0].get("run_id") != run_id:
                    raise SafetyError("journal_run_mismatch")
                self.seen = {record["event_id"] for record in records if "event_id" in record}
        except BaseException:
            self.close()
            raise

    def append(self, kind, **fields):
        record = {"kind": kind, "recorded_ns": time.time_ns(), **fields}
        self.stream.write(json.dumps(record, sort_keys=True, allow_nan=False) + "\n")
        self.stream.flush()
        os.fsync(self.stream.fileno())

    def event(self, record):
        if record["event_id"] not in self.seen:
            self.append(record["kind"], **{key: value for key, value in record.items() if key != "kind"})
            self.seen.add(record["event_id"])

    def records(self):
        try:
            records = [json.loads(line) for line in self.path.read_text().splitlines()]
        except (ValueError, UnicodeError):
            raise SafetyError("journal_corrupt") from None
        if any(not isinstance(record, dict) or not isinstance(record.get("kind"), str) for record in records):
            raise SafetyError("journal_corrupt")
        return records

    def summary(self):
        records = self.records()
        return {"sha256": hashlib.sha256(self.path.read_bytes()).hexdigest(),
                "record_count": len(records), "record_kinds": list(dict.fromkeys(record["kind"] for record in records))}

    def close(self):
        self.stream.close()
