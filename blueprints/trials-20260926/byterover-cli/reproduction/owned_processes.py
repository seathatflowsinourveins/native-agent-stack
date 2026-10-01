#!/usr/bin/env python3
"""Record, then stop, only the ByteRover processes that reproduce-vc-search.sh itself started.

Usage:
  owned_processes.py record <ledger> <daemon.json> <owned-prefix>
  owned_processes.py stop <ledger>

The reproduction points ByteRover's data directory into its own fresh mktemp workspace, so
<daemon.json> (the daemon instance file in that directory) can only name a daemon that the
reproduction's own brv commands spawned. `record` reads that pid and requires one of the
process's arguments to be a brv-server.js under <owned-prefix> (the workspace's npm prefix).
It then appends the pid to <ledger> with its start time (field 22 of /proc/<pid>/stat,
which a later process reusing the pid cannot share), its process group and its session. It
also records every descendant of a recorded daemon, found by following
/proc/<pid>/task/<tid>/children down from that daemon (these are the agent processes the
daemon forks). It never lists /proc and never matches the command lines of other processes.
It reads only pids named by the daemon file or found below a recorded daemon.

`stop` sends SIGTERM to each recorded daemon that is still the recorded process: ByteRover's
own graceful shutdown path, in which the daemon stops its agents. It waits up to 10 s for every
recorded process to exit, sends SIGKILL to any recorded process that is still the recorded
process, and waits up to 5 s more. Each signal goes through a pidfd opened before the start
time is checked, so it cannot reach a process that reused the pid. A zombie counts as
exited. It prints one JSON line per recorded process and exits 0 only when every recorded
process is gone.

This replaces `brv restart`. At v3.16.1 that command reads the command line of every
process visible in /proc and sends SIGKILL to each one containing bin/brv,
byterover-cli/bin/run.js, brv-server.js or agent-process.js, whatever its install or data
directory (../source-review.json#restart-*). This file is local integration glue; the rule
for what counts as stopped is ours.
"""

from __future__ import annotations

import json
import os
import signal
import sys
import time
from pathlib import Path

TERM_WAIT_S = 10.0
KILL_WAIT_S = 5.0
POLL_S = 0.1


def identity(pid: int) -> dict | None:
    """State, parent, process group, session and start time of <pid>, or None when it is gone."""
    try:
        raw = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    fields = raw[raw.rindex(")") + 2:].split()  # fields 3.. of proc_pid_stat(5); comm may hold spaces
    return {"state": fields[0], "ppid": int(fields[1]), "pgrp": int(fields[2]), "session": int(fields[3]),
            "starttime": int(fields[19])}


def arguments(pid: int) -> list[str]:
    try:
        raw = Path(f"/proc/{pid}/cmdline").read_bytes()
    except OSError:
        return []
    return [part.decode("utf-8", "replace") for part in raw.split(b"\0") if part]


def children(pid: int) -> list[int]:
    """Direct children of one process, from its own threads' children files (no /proc listing)."""
    found: set[int] = set()
    try:
        threads = os.listdir(f"/proc/{pid}/task")
    except OSError:
        return []
    for thread in threads:
        try:
            found.update(int(value) for value in Path(f"/proc/{pid}/task/{thread}/children").read_text().split())
        except (OSError, ValueError):
            continue
    return sorted(found)


def script_name(pid: int) -> str:
    """Base name of the first .js argument (or of argv[0]); never a full path."""
    args = arguments(pid)
    for arg in args[1:]:
        if arg.endswith(".js"):
            return Path(arg).name
    return Path(args[0]).name if args else "?"


def still_recorded(entry: dict) -> bool:
    """True while the recorded pid names the recorded process and that process has not exited."""
    now = identity(entry["pid"])
    return now is not None and now["starttime"] == entry["starttime"] and now["state"] not in ("Z", "X")


def load(ledger: Path) -> list[dict]:
    if not ledger.exists():
        return []
    return [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip()]


def record(ledger: Path, daemon_file: Path, prefix: str) -> int:
    entries = load(ledger)
    known = {(entry["pid"], entry["starttime"]) for entry in entries}

    def add(pid: int, role: str, ident: dict) -> None:
        if (pid, ident["starttime"]) in known:
            return
        entry = {"pid": pid, "starttime": ident["starttime"], "ppid": ident["ppid"], "pgrp": ident["pgrp"],
                 "session": ident["session"], "role": role, "script": script_name(pid)}
        known.add((pid, ident["starttime"]))
        entries.append(entry)
        print(json.dumps({"event": "recorded", **entry}))

    try:
        daemon_pid = int(json.loads(daemon_file.read_text(encoding="utf-8"))["pid"])
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({"event": "daemon file unreadable; nothing recorded", "error": type(error).__name__}))
        return 1
    ident = identity(daemon_pid)
    owned = any(arg.startswith(prefix) and arg.endswith("brv-server.js") for arg in arguments(daemon_pid))
    if ident is None or not owned:
        print(json.dumps({"event": "daemon file names a pid that is not this workspace's brv-server.js; "
                          "nothing recorded", "pid": daemon_pid, "alive": ident is not None}))
        return 1
    add(daemon_pid, "daemon", ident)
    pending = [entry["pid"] for entry in entries if entry["role"] == "daemon" and still_recorded(entry)]
    while pending:
        parent = pending.pop()
        for child in children(parent):
            child_ident = identity(child)
            if child_ident is not None and child_ident["ppid"] == parent:
                add(child, "descendant of the daemon", child_ident)
                pending.append(child)
    ledger.write_text("".join(json.dumps(entry) + "\n" for entry in entries), encoding="utf-8")
    return 0


def send(entry: dict, signum: int) -> bool:
    """Signal the recorded process only if it is still the recorded one; pidfd pins it first."""
    try:
        handle = os.pidfd_open(entry["pid"])
    except ProcessLookupError:
        return False
    except (AttributeError, OSError):
        handle = None
    try:
        if not still_recorded(entry):
            return False
        if handle is not None:
            signal.pidfd_send_signal(handle, signum)
        else:
            os.kill(entry["pid"], signum)
        return True
    except ProcessLookupError:
        return False
    finally:
        if handle is not None:
            os.close(handle)


def wait_gone(entries: list[dict], seconds: float) -> None:
    deadline = time.monotonic() + seconds
    while any(still_recorded(entry) for entry in entries) and time.monotonic() < deadline:
        time.sleep(POLL_S)


def stop(ledger: Path) -> int:
    entries = load(ledger)
    sent: list[list[str]] = [[] for _ in entries]
    started = time.monotonic()
    for index, entry in enumerate(entries):
        if entry["role"] == "daemon" and send(entry, signal.SIGTERM):
            sent[index].append("SIGTERM")
    wait_gone(entries, TERM_WAIT_S)
    for index, entry in enumerate(entries):
        if send(entry, signal.SIGKILL):
            sent[index].append("SIGKILL")
    wait_gone(entries, KILL_WAIT_S)
    gone_all = True
    for index, entry in enumerate(entries):
        gone = not still_recorded(entry)
        gone_all = gone_all and gone
        print(json.dumps({"pid": entry["pid"], "role": entry["role"], "script": entry["script"],
                          "signals_sent": sent[index], "gone": gone}))
    print(json.dumps({"event": "summary", "recorded": len(entries), "all_gone": gone_all,
                      "seconds": round(time.monotonic() - started, 2)}))
    return 0 if gone_all else 1


def main(argv: list[str]) -> int:
    if len(argv) == 4 and argv[0] == "record":
        return record(Path(argv[1]), Path(argv[2]), argv[3])
    if len(argv) == 2 and argv[0] == "stop":
        return stop(Path(argv[1]))
    print(__doc__.split("\n\n")[1], file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
