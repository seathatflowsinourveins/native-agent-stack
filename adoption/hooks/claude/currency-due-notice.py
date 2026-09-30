#!/usr/bin/env python3
"""SessionStart: show the stack-currency due line the daily timer left; print nothing otherwise and exit 0.

The stack-currency timer (scripts/currency_due.py) writes
${XDG_STATE_HOME:-~/.local/state}/native-agent-stack/currency-due.json, mode 0600, only while something is due,
and removes it otherwise: {generated_at, due: {pins_behind, stale_receipts, due_layers, reopen_triggers},
summary_line, details}. This hook prints only summary_line, as SessionStart additional context:
- Claude Code: `hookSpecificOutput.additionalContext` (https://code.claude.com/docs/en/hooks#sessionstart,
  "SessionStart decision control", read 2026-09-30).
- Codex 0.157.1 accepts the same two keys (openai/codex rust-v0.157.1,
  codex-rs/hooks/schema/generated/session-start.command.output.schema.json, additionalProperties false, parsed by
  codex-rs/hooks/src/engine/output_parser.rs parse_session_start). Both clients send hook_event_name
  "SessionStart" (Codex: session-start.command.input.schema.json), so one output serves both and the script needs
  no client switch. Only Claude Code registers it (settings template, installer hook map):
  adoption/templates/codex.hooks.template.json, which would run this same file under Codex, is a template only, not
  applied by any installer; B1 applies no Codex hook.

It prints nothing unless stdin is a SessionStart event and the due-file is a regular file of at most 1 MiB, owned
by this user and writable by no one else (the check OpenSSH's StrictModes applies to a user's files, sshd_config(5)),
holding a JSON object whose summary_line, stripped, is 1-160 printable characters and whose generated_at is an
ISO 8601 time at most 8 days old and at most a day ahead (a writer's time-zone slip; a naive time reads as UTC).
XDG_STATE_HOME follows the base directory specification 0.8: unset, empty or relative means $HOME/.local/state.
A state directory that is still not absolute (a relative HOME) would resolve against the working directory, which
the session does not choose, so then nothing is read.
It opens no network connection and starts no process; it imports only json, os, stat, sys and datetime.
Fail-open output pattern: adoption/hooks/claude/token-lanes-subagent-start.py.
"""

import json
import os
import stat
import sys
from datetime import datetime, timedelta, timezone

RELATIVE_PATH = os.path.join("native-agent-stack", "currency-due.json")
MAX_BYTES = 1 << 20
MAX_CHARS = 160
MAX_AGE = timedelta(days=8)
MAX_AHEAD = timedelta(days=1)
FLAGS = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_CLOEXEC", 0)


def due_path():
    """The due-file's absolute path, or None when no absolute state directory is known: a relative HOME would
    otherwise name a file under the working directory, which the session does not choose."""
    base = os.environ.get("XDG_STATE_HOME", "")
    if not os.path.isabs(base):
        base = os.path.join(os.path.expanduser("~"), ".local", "state")
    return os.path.join(base, RELATIVE_PATH) if os.path.isabs(base) else None


def read_due_file(path):
    """The file's bytes, or None when it is absent, not a regular file, not the user's own, writable by group or
    others, unreadable or larger than MAX_BYTES. O_NONBLOCK keeps a FIFO from blocking the open; O_NOFOLLOW
    refuses a link in the last component."""
    try:
        fd = os.open(path, FLAGS)
    except OSError:
        return None
    try:
        info = os.fstat(fd)
        owner = os.geteuid() if hasattr(os, "geteuid") else info.st_uid
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != owner
                or info.st_mode & (stat.S_IWGRP | stat.S_IWOTH) or info.st_size > MAX_BYTES):
            return None
        chunks, size = [], 0
        while size <= MAX_BYTES:
            chunk = os.read(fd, MAX_BYTES + 1 - size)
            if not chunk:
                return b"".join(chunks)
            chunks.append(chunk)
            size += len(chunk)
        return None  # grew past the limit after fstat
    except OSError:
        return None
    finally:
        os.close(fd)


def generated_time(value):
    if not isinstance(value, str) or not value:
        return None
    text = value[:-1] + "+00:00" if value[-1] in "Zz" else value  # fromisoformat takes "Z" only from 3.11
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        return None
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=timezone.utc)


def summary_line(raw):
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, RecursionError):
        return None
    if not isinstance(document, dict):
        return None
    line = document.get("summary_line")
    if not isinstance(line, str):
        return None
    line = line.strip()
    if not line or len(line) > MAX_CHARS or not line.isprintable():
        return None
    moment = generated_time(document.get("generated_at"))
    if moment is None:
        return None
    try:
        age = datetime.now(timezone.utc) - moment
    except OverflowError:
        return None
    if age > MAX_AGE or age < -MAX_AHEAD:
        return None
    return line


def main():
    try:
        event = json.load(sys.stdin)
    except (ValueError, RecursionError):
        return
    if not isinstance(event, dict) or event.get("hook_event_name") != "SessionStart":
        return
    path = due_path()
    raw = read_due_file(path) if path is not None else None
    line = summary_line(raw) if raw is not None else None
    if line is None:
        return
    output = {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": line}}
    # Unbuffered output leaves no failing flush to change the exit status at shutdown.
    encoded = (json.dumps(output) + "\n").encode("utf-8")
    while encoded:
        encoded = encoded[os.write(1, encoded):]


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
