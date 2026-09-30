#!/usr/bin/env python3
"""Canary proof: plant a synthetic canary for each of six consumers, then prove zero copies in the named sinks.

    python3 tools/credentials/canary_proof.py prepare [--codex-home DIR] [--transcripts confirmed|exclude]
                                                    [--session ID]
    python3 tools/credentials/canary_proof.py scan --run RUN --phase baseline|final|comparison [--user-run]
    python3 tools/credentials/canary_proof.py arm --run RUN CONSUMER [--codex-home DIR]
    python3 tools/credentials/canary_proof.py disarm|status|verdict|cleanup --run RUN

This process is the coordinator. It holds only synthetic values (the run's canaries, tags, markers, controls and
anchor) and value-free records. Every read of sink bytes, names, headers, diagnostics, Git data, SQLite data and the
journal happens in tools/credentials/canary_scan_worker.py, started inside adoption/tools/ecosystem-bounded-run's
systemd scope, which answers only in fixed 128-byte CP03 records: enums, opaque keyed ids and counts. That worker,
its SQLite dumper and ripgrep read sink bytes; nothing else does (C12). The canary is written create-only to the
store for one consumer attempt at a time, reaches the consumer only through `credential_run.py canary-e2e`, and is
removed by disarm; this tool never reads a store file.

Exit status: 0 success or a clean verdict; 1 refused; 2 usage; 3 incomplete; 4 invalid run record; 5 leak; 75 busy.
`status` and `cleanup` exit with the classifier's verdict code (0, 3, 4 or 5), or 1 when refused. See
docs/secret-storage.md#canary-proof and docs/decisions/2026-09-29-key-management.md (Part 5); the build contract is
draft 3 with amendments C1-C14 (2026-09-30).
"""
from __future__ import annotations

import os
import sys

if __name__ == "__main__" and not (sys.flags.isolated and sys.flags.no_site):
    os.execv(sys.executable, [sys.executable, "-I", "-S", os.path.abspath(__file__), *sys.argv[1:]])

import argparse  # noqa: E402
import bz2  # noqa: E402
import contextlib  # noqa: E402
import fcntl  # noqa: E402
import gzip  # noqa: E402
import hashlib  # noqa: E402
import hmac  # noqa: E402
import json  # noqa: E402
import lzma  # noqa: E402
import re  # noqa: E402
import secrets  # noqa: E402
import select  # noqa: E402
import signal  # noqa: E402
import sqlite3  # noqa: E402  (writes synthetic control databases only; sink databases are read by the dumper)
import stat  # noqa: E402
import subprocess  # noqa: E402
import time  # noqa: E402
from datetime import datetime, timezone  # noqa: E402
from pathlib import Path  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
for _directory in (ROOT / "tools" / "credentials", ROOT / "scripts"):
    if str(_directory) not in sys.path:
        sys.path.insert(0, str(_directory))
import canary_probe as probe  # noqa: E402
import canary_scan_worker as wire  # noqa: E402  (the shared CP03 schema; its scanning runs only in the worker)
import credential_boot_receipt as boot  # noqa: E402
import credential_run as runner  # noqa: E402
import credential_status as cs  # noqa: E402
import set_credential as writer  # noqa: E402

CONSUMERS = wire.CONSUMERS
ENTRY, VARIABLE, STORE_FILE = "canary-e2e", "CANARY_E2E_KEY", "canary-e2e.env"
MARKERS = (f"[REDACTED:{VARIABLE}]", f"[REDACTED-PARTIAL:{VARIABLE}]")
CHILD_PATH = "/usr/local/bin:/usr/bin:/bin"
RUNNER = ROOT / "adoption" / "tools" / "ecosystem-bounded-run"
WORKER, PROBE = ROOT / "tools" / "credentials" / "canary_scan_worker.py", ROOT / "tools" / "credentials" / "canary_probe.py"
TOOLS = {"tool": Path(__file__).resolve(), "worker": WORKER, "probe": PROBE, "runner": RUNNER,
         "credential_run": ROOT / "tools" / "credentials" / "credential_run.py"}
EXECUTABLES = ("bzip2", "git", "gzip", "ionice", "journalctl", "nice", "python3", "rg", "setpriv", "systemctl",
               "systemd-cat", "xz")
WORKER_COMMAND = None   # a test launcher's worker entry ([python, -I, -S, -c, code, config]); None is the file
DUMPER_COMMAND = None
SETTLE_SECONDS = 1200
DRIFT_NS, MARGIN_NS = 60 * 10**9, 3600 * 10**9
ARM_RECOVERY_NS = 5 * 10**9
# RuntimeMaxSec per phase and sink (C13): 7,200 s bounds a walking sink's scope, 900 s the journal, 60 s U4, 120 s a
# setup child; a test launcher shortens them.
SCOPE_SECONDS = {**{sink: 7200 for sink in wire.SINKS}, "A11": 900, "U4": 60, "setup": 120}
PHASE_SECONDS = {phase: dict(SCOPE_SECONDS) for phase in ("baseline", "final", "comparison")}
AGENT_SINKS = ("A1", "A2", "A3", "A4", "A9", "A10", "A11", "A12")
USER_SINKS = tuple(f"U{number}" for number in range(1, 9))
EXIT = {"clean": 0, "refused": 1, "usage": 2, "incomplete": 3, "invalid": 4, "leak": 5, "busy": 75}
RUN_ID = re.compile(r"cp-\d{8}t\d{6}z-[0-9a-f]{6}")
SESSION = re.compile(r"[0-9A-Za-z-]{8,64}")
HOOKS: dict = {}  # a test launcher's module hooks (contract 9.5); there is no environment switch
AUDIT: list = []   # the validated CP03 records of this invocation, kept for the boundary audit (B1)


class Refused(Exception):
    """A safety rule or precondition refused (exit 1). The code is a fixed word; nothing is interpolated."""


class Busy(Exception):
    pass


def hook(name: str, *args) -> None:
    function = HOOKS.get(name)
    if function is not None:
        function(*args)


def keyed(key: bytes, *parts) -> str:
    return wire.keyed(key, *parts).hex()


def digest(data) -> str:
    return hashlib.sha256(data if isinstance(data, bytes) else json.dumps(data, sort_keys=True).encode()).hexdigest()


def clock() -> tuple:
    return (datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"), time.clock_gettime_ns(time.CLOCK_REALTIME),
            time.clock_gettime_ns(time.CLOCK_BOOTTIME))


# ---- The run directory, its lock and its append-only record (contract 5) --------------------------------------------
class Run:
    def __init__(self, env, run_id: str = None):
        runtime = env.get("XDG_RUNTIME_DIR") or ""
        try:
            info = os.lstat(runtime) if os.path.isabs(runtime) else None
        except OSError:
            info = None
        if info is None or not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() \
                or stat.S_IMODE(info.st_mode) != 0o700:
            raise Refused("runtime_directory_unsafe")
        self.env, self.runtime = env, Path(runtime)
        self.base = self.runtime / "native-agent-stack" / "canary-proof"
        self.id = run_id
        self.lock = os.open(self.runtime / "ecosystem-canary-proof.lock",
                            os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Busy() from None
        self.events, self.key = [], None

    @property
    def dir(self) -> Path:
        return self.base / self.id

    def create(self) -> None:
        for path in (self.runtime / "native-agent-stack", self.base):
            with _suppress(FileExistsError):
                os.mkdir(path, 0o700)
        os.mkdir(self.dir, 0o700)

    def write(self, name: str, data: bytes) -> str:
        path = self.dir / name
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
        try:
            os.write(fd, data)
            os.fsync(fd)
        finally:
            os.close(fd)
        return digest(data)

    def read(self, name: str) -> bytes:
        fd = os.open(self.dir / name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
                raise Refused("pattern_file_mismatch")
            return b"".join(iter(lambda: os.read(fd, 1 << 20), b""))
        finally:
            os.close(fd)

    def append(self, event: str, **fields) -> dict:
        utc, realtime, boottime = clock()
        first = self.events[0] if self.events else None
        drift = (realtime - first["realtime_ns"]) - (boottime - first["boottime_ns"]) if first else 0
        record = {"seq": len(self.events) + 1, "run": self.id, "event": event, "utc": utc, "realtime_ns": realtime,
                  "boottime_ns": boottime, "boot_id": boot.small_text(boot.BOOT_ID), "drift_ns": drift, **fields}
        line = json.dumps(record, sort_keys=True, separators=(",", ":")).encode("ascii") + b"\n"
        check_output(line, self.secrets())
        fd = os.open(self.dir / "events.jsonl", os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC,
                     0o600)
        try:
            os.write(fd, line)
            os.fsync(fd)
        finally:
            os.close(fd)
        self.events.append(record)
        return record

    def load(self) -> None:
        if not RUN_ID.fullmatch(self.id or "") or not self.dir.is_dir():
            raise Refused("unknown_run")
        self.key = self.read("key")
        try:
            text = self.read("events.jsonl").decode("ascii")
            self.events = [json.loads(line) for line in text.split("\n")[:-1]] if text.endswith("\n") else None
        except (ValueError, OSError):
            self.events = None
        self.valid = bool(self.events) and validate(self.events, self.id)
        self.events = self.events or []

    def secrets(self) -> list:
        """Every synthetic value this run could print by accident: canary forms, tags and tag lines, the request's
        control values and the journal anchor (contract 12). The public marker strings are not among them."""
        values = list(getattr(self, "extra", []))
        if (self.dir / "anchor").exists():
            values.append(self.read("anchor").decode("ascii").strip())
        for name in sorted(os.listdir(self.dir / "patterns")) if (self.dir / "patterns").is_dir() else ():
            lines = self.read("patterns/" + name).decode("ascii").splitlines()
            consumer, attempt = name.rsplit(".", 1)
            line = tag_line(lines[0], self.id, consumer, int(attempt))
            values += lines + [line, line.rsplit(" ", 1)[1]]
        return values


_suppress = contextlib.suppress


def check_output(data: bytes, values: list) -> None:
    """Defence in depth: refuse to print or publish bytes that hold a synthetic value of the run (contract 12)."""
    for value in values:
        if value and value.encode("ascii") in data:
            raise Refused("synthetic_value_in_output")


# ---- Record validation: structure, fields and transitions (contract 5) ----------------------------------------------
COMMON = {"seq": int, "run": str, "event": str, "utc": str, "realtime_ns": int, "boottime_ns": int, "boot_id": str,
          "drift_ns": int}
EVENTS = {
    "prepared": {"tools": dict, "executables": dict, "versions": dict, "rg_version": int, "checkout": str, "ref": dict,
                 "threshold_ns": int, "roots": dict, "policy": str, "exclusions": str, "anchor": str, "patterns": dict,
                 "transcripts": str, "session_known": bool, "session": str, "proxy_verified": bool, "pointers": list,
                 "guard_pinned": bool, "journal_bound": bool},
    "arming": {"consumer": str, "attempt": int, "pattern": str, "root": str, "root_present": bool},
    "armed": {"consumer": str, "attempt": int, "dev": int, "ino": int, "ctime_ns": int, "guard_pinned": bool,
              "recovered": bool},
    "disarmed": {"consumer": str, "attempt": int, "removed": bool, "absent_verified": bool},
    "scan_requested": {"request": str, "phase": str, "group": str, "selection": str},
    "scan_planned": {"request": str, "attempts": list, "union": str, "classes": dict, "sinks": dict,
                     "controls": dict, "executables": str, "exclusions": str, "deadlines": dict},
    "scan_inventory": {"request": str, "sink": str, "subpass": int, "seal": str, "checks": int, "counters": dict},
    "hit": {"request": str, "sink": str, "subpass": int, "root": str, "object": str, "check": int, "mode": int,
            "view": int, "path": int, "consumer": str, "attempt": int, "count": int},
    "scan_finished": {"request": str, "status": str, "sinks": dict, "reasons": list},
    "clock_stepped": {"drift_ns_seen": int},
    "integrity_failed": {"code": str},
    "cleaned": {"receipt": str, "absent_verified": bool},
}
PHASES = {("baseline", "agent"), ("final", "agent"), ("final", "user"), ("comparison", "user")}


def validate(events: list, run_id: str) -> bool:
    """False for partial records, gaps, unknown events or fields, bad values or an impossible transition."""
    requests, pending, armed = {}, None, None
    for number, event in enumerate(events, 1):
        kind = event.get("event")
        schema = {**COMMON, **EVENTS.get(kind, {})}
        if kind not in EVENTS or set(event) != set(schema) or event["seq"] != number or event["run"] != run_id:
            return False
        if any(not isinstance(event[name], kind_) or kind_ is int and isinstance(event[name], bool)
               for name, kind_ in schema.items()):
            return False
        if not valid_fields(event):
            return False
        if (number == 1) != (kind == "prepared"):
            return False
        if kind in ("arming", "armed", "disarmed", "hit") and event["consumer"] not in CONSUMERS:
            return False
        if kind == "arming":
            if pending or armed:
                return False
            pending = (event["consumer"], event["attempt"])
        elif kind == "armed":
            if pending != (event["consumer"], event["attempt"]):
                return False
            armed, pending = pending, None
        elif kind == "disarmed":
            if armed != (event["consumer"], event["attempt"]):
                return False
            armed = None
        elif kind == "scan_requested":
            if event["request"] in requests or (event["phase"], event["group"]) not in PHASES:
                return False
            requests[event["request"]] = {"planned": False, "finished": False}
        elif kind in ("scan_planned", "scan_inventory", "hit", "scan_finished"):
            state = requests.get(event["request"])
            if state is None or state["finished"] or kind == "scan_planned" and state["planned"] \
                    or kind == "scan_inventory" and not state["planned"]:
                return False
            state["planned"] |= kind == "scan_planned"
            state["finished"] |= kind == "scan_finished"
        elif kind == "cleaned" and number != len(events):
            return False
    return True


def valid_fields(event: dict) -> bool:
    """Closed nested carriers: a parsed JSON object is not automatically a value-free record (§5, B8)."""
    def hex_(value, width=32):
        return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{" + str(width) + "}", value) is not None
    def natural(value):
        return type(value) is int and 0 <= value <= (1 << 48)
    def patterns(rows):
        return all(re.fullmatch(r"(?:" + "|".join(CONSUMERS) + r")\.[1-9][0-9]*", name)
                   and hex_(sha, 64) for name, sha in rows.items())
    try:
        if not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{6}Z", event["utc"]) or not re.fullmatch(
                r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", event["boot_id"]):
            return False
        if not natural(event["seq"]) or min(event["boottime_ns"], event["realtime_ns"]) < 0:
            return False
        kind = event["event"]
        if kind == "prepared":
            return (set(event["roots"]) == set(wire.SINKS) and all(hex_(root) and type(present) is bool
                    for pairs in event["roots"].values() for root, present in pairs)
                    and event["transcripts"] in ("confirmed", "exclude") and not event["proxy_verified"]
                    and set(event["tools"]) == set(TOOLS) and all(hex_(sha, 64) for sha in event["tools"].values())
                    and set(event["executables"]) == set(EXECUTABLES)
                    and all(not sha or hex_(sha, 64) for sha in event["executables"].values())
                    and set(event["versions"]) == set(EXECUTABLES) | {"sqlite"}
                    and all(natural(code) for code in event["versions"].values()) and patterns(event["patterns"])
                    and all(hex_(event[field], 64) for field in ("policy", "exclusions", "anchor"))
                    and hex_(event["checkout"]) and (not event["session"] or hex_(event["session"], 64)))
        if kind in ("arming", "armed", "disarmed", "hit") and not (
                type(event["attempt"]) is int and 1 <= event["attempt"] <= 0xFFFFFFFF):
            return False
        if kind == "arming":
            return hex_(event["pattern"], 64) and (not event["root"] or hex_(event["root"]))
        if kind == "armed":
            return all(type(event[key]) is int and event[key] > 0 for key in ("dev", "ino", "ctime_ns"))
        if kind.startswith("scan_") or kind == "hit":
            if not re.fullmatch(r"[0-9a-f]{12}", event["request"]):
                return False
        if kind == "scan_requested":
            return event["selection"] == ("all" if event["phase"] == "comparison" else "changed")
        if kind == "scan_planned":
            return (all(sink in wire.SINKS and len(ids) == len(set(ids)) and all(hex_(root) for root in ids)
                        for sink, ids in event["sinks"].items()) and hex_(event["union"], 64)
                    and all(c in CONSUMERS and type(a) is int and a > 0 for c, a in event["attempts"])
                    and len(event["attempts"]) == len(set(map(tuple, event["attempts"]))))
        if kind == "scan_inventory":
            return event["sink"] in wire.SINKS and event["subpass"] in (0, 1) and natural(event["checks"])
        if kind == "hit":
            return (event["sink"] in wire.SINKS and event["subpass"] in (0, 1) and hex_(event["root"])
                    and hex_(event["object"]) and 0 < event["count"] <= (1 << 48)
                    and event["mode"] in wire.MODES.values() and event["view"] in wire.VIEWS.values()
                    and event["path"] in wire.PATHS.values() and natural(event["check"]))
        if kind == "scan_finished":
            return (event["status"] in ("complete", "incomplete")
                    and all(reason in wire.R or reason in CODES for reason in event["reasons"])
                    and all(sink in wire.SINKS and row["status"] in ("complete", "incomplete")
                            and all(reason in wire.R or reason == "inventory_unreconciled" for reason in row["reasons"])
                            and all(natural(row[name]) for name in ("checks", "completed", "hits"))
                            and set(row["counters"]) == set(wire.COUNTERS)
                            and all(natural(count) for count in row["counters"].values())
                            and all(hex_(root) for root in row["roots"] + row["absent"])
                            and all(len(item) == 6 and natural(item[0]) and hex_(item[1])
                                    and item[2] in wire.MODES.values() and item[3] in wire.VIEWS.values()
                                    and item[4] in wire.STATUS.values() and item[5] < len(wire.REASONS)
                                    for item in row["ledger"])
                            and all(len(item) == 6 and item[0] in (2, 3, 4, 6) and item[1] in range(7)
                                    and natural(item[2]) and item[3] in wire.PATHS.values()
                                    and hex_(item[4]) and natural(item[5]) for item in row["observations"])
                            for sink, row in event["sinks"].items()))
        if kind == "integrity_failed":
            return event["code"] in CODES
        if kind == "cleaned":
            return re.fullmatch(re.escape(event["run"]) + r"-[0-9]{6}", event["receipt"]) is not None
        return True
    except (KeyError, TypeError, ValueError, AttributeError):
        return False


# ---- Canaries, patterns and the per-request union (contract 6) -------------------------------------------------------
def new_canary() -> str:
    tail = list(secrets.token_hex(16))
    for symbol in "+/=":
        tail.insert(secrets.randbelow(len(tail) + 1), symbol)
    return "CNRYE2E" + "".join(tail)


def forms(canary: str) -> list:
    return list(dict.fromkeys(form.decode("ascii") for form in runner.encoded_forms(canary.encode("ascii"))))


def tag_line(canary: str, run: str, consumer: str, attempt: int) -> str:
    return f"canary-probe {consumer} attempt {attempt}: tag {probe.tag(canary, run, consumer, attempt)}"


def control_value(prefix: str = "CNRYCTL") -> str:
    return prefix + secrets.token_hex(16)


def attempts(run: Run) -> dict:
    """consumer -> every attempt number that has a pattern file, in order."""
    found = {}
    for name in sorted(os.listdir(run.dir / "patterns")):
        consumer, attempt = name.rsplit(".", 1)
        found.setdefault(consumer, []).append(int(attempt))
    return {consumer: sorted(numbers) for consumer, numbers in found.items()}


def canary_of(run: Run, consumer: str, attempt: int) -> str:
    return run.read(f"patterns/{consumer}.{attempt}").decode("ascii").split("\n", 1)[0]


def pattern_integrity(run: Run) -> list:
    """Codes for any attempt pattern file that no longer matches its recorded hash or grammar."""
    recorded = dict(run.events[0]["patterns"])
    for event in run.events:
        if event["event"] == "arming":
            recorded[f"{event['consumer']}.{event['attempt']}"] = event["pattern"]
    try:
        present = {name: run.read("patterns/" + name) for name in os.listdir(run.dir / "patterns")}
    except (OSError, Refused):
        return ["pattern_file_mismatch"]
    for name, sha in recorded.items():
        data = present.get(name)
        lines = data.decode("ascii", "replace").split("\n") if data else []
        if data is None or digest(data) != sha or lines[-1] != "" or any(
                len(line) < 6 or not line.isprintable() for line in lines[:-1]):
            return ["pattern_file_mismatch"]
    return []


class Request:
    """One durable scan request: its directory, union file, controls and the connections that keep WAL controls live."""

    def __init__(self, run: Run, event: dict):
        self.run, self.id, self.phase, self.group = run, event["request"], event["phase"], event["group"]
        self.selection = event["selection"]
        self.name = f"scan-{self.id}"
        self.connections, self.controls, self.ids = [], {}, {}

    def ident(self, kind: str) -> str:
        return keyed(self.run.key, b"control", self.id, kind)

    def value(self, kind: str, prefix: str = "CNRYCTL") -> str:
        self.controls[kind] = self.controls.get(kind) or control_value(prefix)
        return self.controls[kind]

    def build(self) -> dict:
        """The union and every control file of the request, synthetic only (contract 6, 10.4)."""
        run, top = self.run, self.run.dir / self.name
        hook("before_mkdir")
        os.mkdir(top, 0o700)
        hook("before_controls")
        spec = {"m1": [], "m1_negative": [], "bom": [], "bom_negative": [], "m2": [], "m5": [],
                "inband": {name: self.ident(name) for name in ("m2raw", "m2bom", "m3", "m4", "m5", "u4")}}
        for name in spec["inband"]:
            self.value(name)
        files = {"plain": self.value("plain").encode() + b"\n", "nul": b"\0" + self.value("nul").encode(),
                 "bomraw": b"\xff\xfe" + self.value("bomraw").encode(),
                 "fname": gzip_with_name(self.value("fname"))}
        for number, (kind, data) in enumerate(files.items(), 1):
            spec["m1"].append([self.file(f"m1/{number:04d}", data), self.ident(kind), data.count(
                self.controls[kind].encode())])
        main_db, wal_db = top / "m1" / "0005", top / "m1" / "0006"
        self.database(main_db, [("CREATE TABLE t(v)", ()), ("INSERT INTO t VALUES (?)", (self.value("dbmain"),))])
        self.database(wal_db, [("CREATE TABLE t(v)", ()), ("INSERT INTO t VALUES (?)", (self.value("dbwal"),))],
                      wal=True)
        for path, kind in ((main_db, "dbmain"), (Path(str(wal_db) + "-wal"), "dbwal")):
            spec["m1"].append([str(path), self.ident(kind), path.read_bytes().count(self.controls[kind].encode())])
        spec["m1_negative"].append([self.file("m1/0007", b"no synthetic pattern here\n"), self.ident("m1neg")])
        for number, (kind, encoding) in enumerate((("bomle", "utf-16-le"), ("bombe", "utf-16-be")), 1):
            data = {"utf-16-le": b"\xff\xfe", "utf-16-be": b"\xfe\xff"}[encoding] + (
                self.value(kind) + "\n").encode(encoding)
            spec["bom"].append([self.file(f"bom/{number:04d}", data), self.ident(kind), 1])
        spec["bom_negative"].append([self.file("bom/0003", b"\xff\xfe" + "nothing\n".encode("utf-16-le")),
                                     self.ident("bomneg")])
        for fmt, compress in (("gzip", gzip.compress), ("bzip2", bz2.compress), ("xz", lzma.compress),
                              ("lzma", lambda data: lzma.compress(data, format=lzma.FORMAT_ALONE))):
            rows = [("plain", b"", "raw", 1), ("le", b"\xff\xfe", "bom", 1), ("be", b"\xfe\xff", "bom", 1),
                    ("neg", None, "negative", 0)]
            if fmt == "gzip":
                rows += [("two", b"", "raw", 1), ("mixed", b"\xff\xfe", "raw", 1)]
            for label, bom, view, expected in rows:
                kind = f"m2_{fmt}_{label}"
                value = self.value(kind)
                if bom is None:
                    data = compress(b"nothing to find in this stream\n")
                elif label == "mixed":
                    data = compress(bom + value.encode() + b"\n")
                elif bom:
                    data = compress(bom + (value + "\n").encode("utf-16-le" if bom == b"\xff\xfe" else "utf-16-be"))
                else:
                    data = compress(value.encode() + b"\n")
                if label == "two":
                    data = gzip.compress(b"first member\n") + gzip.compress(value.encode() + b"\n")
                spec["m2"].append([self.file(f"m2/{kind}", data), fmt, self.ident(kind), view, expected])
        spec["m5"] = self.databases(top)
        spec["m4"] = {"repo": str(top / "m4.git"), "loose": self.ident("m4_loose"), "packed": self.ident("m4_packed"),
                      "keep_id": self.ident("m4_keep"), "loose_value": self.value("m4_loose"),
                      "packed_value": self.value("m4_packed"), "keep_value": self.value("m4_keep")}
        spec["m6"] = self.names(top / "m6")
        spec["objhdr"] = self.ident("objhdr")
        spec["anchor"] = keyed(run.key, b"anchor")
        self.spec = spec
        return spec

    def file(self, rel: str, data: bytes) -> str:
        self.run.write(f"{self.name}/{rel}", data)
        return str(self.run.dir / self.name / rel)

    def database(self, path: Path, statements: list, wal: bool = False, encoding: str = None) -> None:
        path.parent.mkdir(mode=0o700, exist_ok=True)
        connection = sqlite3.connect(path, isolation_level=None)
        if encoding:
            connection.execute(f"PRAGMA encoding='{encoding}'")
        if wal:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA wal_autocheckpoint=0")
        connection.execute("BEGIN")
        for sql, parameters in statements:
            connection.execute(sql, parameters)
        connection.execute("COMMIT")
        if wal:
            self.connections.append(connection)  # held open: the WAL stays uncheckpointed until the request ends
        else:
            connection.close()
        for suffix in ("", "-wal", "-shm"):
            if os.path.exists(str(path) + suffix):
                os.chmod(str(path) + suffix, 0o600)

    def databases(self, top: Path) -> list:
        """M5 controls (contract 10.4): WAL overflow row, UTF-16LE/BE values, schema-only defaults/views/triggers/names,
        UTF-16 overflow schema, and names that a literal URI would misread."""
        rows, directory = [], top / "m5"
        self.database(directory / "wal-overflow", [("CREATE TABLE t(v)", ()), ("INSERT INTO t VALUES (?)", (
            "x" * 6000 + self.value("m5_overflow") + "y" * 6000,))], wal=True)
        rows.append([str(directory / "wal-overflow"), self.ident("m5_overflow"), 1])
        for kind, encoding in (("m5_le", "UTF-16le"), ("m5_be", "UTF-16be")):
            self.database(directory / kind, [("CREATE TABLE t(v)", ()), ("INSERT INTO t VALUES (?)",
                                                                         (self.value(kind),))], encoding=encoding)
            rows.append([str(directory / kind), self.ident(kind), 1])
        default, view, trigger, name = (self.value(kind) for kind in ("m5_default", "m5_view", "m5_trigger", "m5_name"))
        self.database(directory / "schema", [(f"CREATE TABLE d(x TEXT DEFAULT '{default}')", ()),
                                             (f"CREATE VIEW v AS SELECT '{view}' AS c", ()),
                                             (f"CREATE TRIGGER g AFTER INSERT ON d BEGIN SELECT '{trigger}'; END", ()),
                                             (f'CREATE TABLE "{name}" (x)', ())], encoding="UTF-16le")
        rows += [[str(directory / "schema"), self.ident(kind), count] for kind, count in (
            ("m5_default", 1), ("m5_view", 1), ("m5_trigger", 1), ("m5_name", 3))]
        long = "z" * 9000 + self.value("m5_schema_overflow")
        self.database(directory / "overflow", [(f"CREATE TABLE s(x TEXT DEFAULT '{long}')", ())], encoding="UTF-16be")
        rows.append([str(directory / "overflow"), self.ident("m5_schema_overflow"), 1])
        for number, label in enumerate(("pct%41", "q?mode=memory&cache=private", "hash#x", "all%25?x#y"), 1):
            kind = f"m5_uri{number}"
            self.database(directory / label, [("CREATE TABLE t(v)", ()), ("INSERT INTO t VALUES (?)",
                                                                          (self.value(kind),))])
            rows.append([str(directory / label), self.ident(kind), 1])
        return rows

    def names(self, directory: Path) -> dict:
        """M6 controls: a name, a dangling link target, a path spanning two components, and a negative name."""
        os.mkdir(directory, 0o700)
        name, target = self.value("m6_name"), self.value("m6_target")
        spanning = self.controls["m6_path"] = "CNRYCTL" + secrets.token_hex(8) + "/" + secrets.token_hex(8)
        (directory / f"n-{name}").write_bytes(b"")
        os.symlink(f"/nonexistent/{target}", directory / "dangling")
        first, second = spanning.split("/")
        os.mkdir(directory / f"p-{first}", 0o700)
        (directory / f"p-{first}" / f"{second}-end").write_bytes(b"")
        (directory / f"neg-{self.value('m6_negative')[:14]}").write_bytes(b"")
        return {"dir": str(directory), "ids": [[self.ident(kind), 1, "control"] for kind in
                                               ("m6_name", "m6_target", "m6_path")]}

    def close(self) -> None:
        for connection in self.connections:
            connection.close()


def gzip_with_name(name: str) -> bytes:
    import io
    buffer = io.BytesIO()
    with gzip.GzipFile(filename=name, mode="wb", fileobj=buffer, mtime=0) as handle:
        handle.write(b"member body\n")
    return buffer.getvalue()


def build_union(run: Run, request: Request) -> tuple:
    """(path, sha256, classes): every attempt's forms and tag line, both markers, the request's controls, the object
    marker and the run's journal anchor, deduplicated without losing any class (contract 6)."""
    hook("before_union")
    entries = []
    for consumer, numbers in attempts(run).items():
        for attempt in numbers:
            canary = canary_of(run, consumer, attempt)
            code = CONSUMERS.index(consumer) + 1
            entries += [(form, wire.CLASSES["canary"], code, attempt, "") for form in forms(canary)]
            entries.append((tag_line(canary, run.id, consumer, attempt), wire.CLASSES["tag"], code, attempt, ""))
    entries += [(MARKERS[0], wire.CLASSES["full_marker"], 0, 0, ""),
                (MARKERS[1], wire.CLASSES["partial_marker"], 0, 0, "")]
    for kind, value in request.controls.items():
        if kind != "m6_negative":
            entries.append((value, wire.CLASSES["control"], 0, 0, request.ident(kind)))
    entries.append((request.value("objhdr", "CNRYOBJ"), wire.CLASSES["object_header"], 0, 0, request.ident("objhdr")))
    entries.append((run.read("anchor").decode("ascii").strip(), wire.CLASSES["anchor"], 0, 0,
                    keyed(run.key, b"anchor")))
    lines = list(dict.fromkeys(entry[0] for entry in entries))
    classes = [[lines.index(text), klass, consumer, attempt, ident] for text, klass, consumer, attempt, ident in entries]
    data = ("\n".join(lines) + "\n").encode("ascii")
    sha = run.write(f"{request.name}/patterns", data)
    if set(run.read(f"{request.name}/patterns").decode("ascii").splitlines()) != {entry[0] for entry in entries}:
        raise Refused("pattern_file_mismatch")
    return str(run.dir / request.name / "patterns"), sha, classes


# ---- Configuration: roots, exclusions and executables (contract 8) -------------------------------------------------
def homes(run: Run) -> list:
    return json.loads(run.read("homes"))


TASKS_ROOT = "/tmp/claude-{uid}"  # A10's glob parent, /tmp/claude-<uid>/*/*/tasks (a test launcher points elsewhere)


def sink_roots(home: str, uid: int, codex: list, cursor: str) -> dict:
    """Trusted root recipes per sink, expanded from HOME, the uid and the registered Codex homes."""
    h = home
    return {
        "A1": [("dir", f"{h}/.claude")], "A2": [("file", f"{h}/claude-config-audit.log"), ("file", f"{h}/.bash_history")],
        "A3": [("dir", f"{h}/.cache/claude-cli-nodejs")], "A4": [("dir", path) for path in codex],
        "A9": [("dir", f"{h}/.local/share/codex-ecosystem/observability/collector")],
        "A10": [("tasks", TASKS_ROOT.format(uid=uid))], "A11": [("journal", cursor)],
        "A12": [("git", f"{h}/code/native-agent-stack-live"), ("git", f"{h}/code/native-agent-stack")],
        "U1": [("dir", f"{h}/.omniroute"), ("dir", f"{h}/.local/share/omniroute-fw"), ("dir", f"{h}/.local/share/omniroute")],
        "U2": [("dir", f"{h}/.local/share/docker/containers"), ("file", f"{h}/.docker/config.json")],
        "U3": [("dir", f"{path}/shell_snapshots") for path in codex], "U4": [("environment", "-")],
        "U5": [("dir", f"{h}/.config/systemd/user"), ("dir", f"{h}/.config/environment.d")],
        "U6": [("file", f"{h}/.claude/history.jsonl"), ("dir", f"{h}/.claude/paste-cache")]
        + [("file", f"{path}/history.jsonl") for path in codex],
        "U7": [("glob", f"{h}/.claude.json*"), ("glob", f"{h}/.claude/settings.json*"),
               ("dir", f"{h}/.claude/backups")] + [("glob", f"{path}/*.toml*") for path in codex]
        + [("file", f"{path}/log/codex-login.log") for path in codex],
        "U8": [("dir", f"{h}/.agentsview"), ("dir", f"{h}/.local/share/ai-memory"), ("dir", f"{h}/.claude/context-mode"),
               ("dir", f"{h}/.local/share/rtk"), ("dir", f"{h}/.headroom")]
        + [("dir", f"{path}/context-mode") for path in codex] + [("glob", f"{path}/*.sqlite*") for path in codex],
    }


def exclusions(home: str, codex: list, env, transcripts: str, group: str, pointers: list) -> tuple:
    """(exact, glob): K never scanned; U-in-A locations for agent scans; declined transcripts (C5)."""
    h = home
    exact = [(f"{h}/.ssh", "key"), (f"{h}/.gnupg", "key"), (f"{h}/.claude/.credentials.json", "key"),
             (f"{h}/.claude/daemon/control.key", "key"), (str(cs.expand_template(cs.STORE_ROOT, env)), "key")]
    exact += [(path, "key") for path in pointers]
    inventory = json.loads((ROOT / cs.INVENTORY).read_text(encoding="utf-8"))
    exact += [(str(cs.expand_template(entry["store"]["path_template"], env)), "key")
              for entry in inventory["entries"] if entry["store"]["kind"] in cs.LOCAL_KINDS]
    glob = [(f"{h}/.claude/sessions", "*.key", "key")]
    for path in codex:
        exact.append((f"{path}/auth.json", "key"))
        if group == "agent":
            exact += [(f"{path}/{name}", "user") for name in ("shell_snapshots", "context-mode", "history.jsonl",
                                                                "log/codex-login.log")]
            glob += [(path, "*.toml*", "user"), (path, "*.sqlite*", "user")]
        if transcripts == "exclude":
            exact.append((f"{path}/sessions", "declined"))
    if group == "agent":
        exact += [(f"{h}/.claude/{name}", "user") for name in ("history.jsonl", "paste-cache", "settings.json",
                                                                 "backups", "context-mode")]
        glob.append((f"{h}/.claude", "settings.json.*", "user"))
    if transcripts == "exclude":
        exact.append((f"{h}/.claude/projects", "declined"))
    return sorted(set(exact)), sorted(set(glob))


def resolve_executables() -> dict:
    found = {}
    for name in EXECUTABLES:
        for directory in CHILD_PATH.split(":"):
            path = os.path.join(directory, name)
            if os.path.isfile(path) and os.access(path, os.X_OK):
                found[name] = [path, wire.sha256_file(path)]
                break
        else:
            found[name] = None
    return found


def pointer_paths(env) -> list:
    inventory = json.loads((ROOT / cs.INVENTORY).read_text(encoding="utf-8"))
    names = sorted({name for entry in inventory["entries"] for name in entry["pointer_variables"]})
    return [env[name] for name in names if env.get(name) and os.path.isabs(env[name])]


# ---- Launching the contained worker and reading CP03 (contract 10, 11) ----------------------------------------------
def launch_argv(executables: dict) -> list:
    python = WORKER_COMMAND or [executables["python3"][0], "-I", "-S", str(WORKER)]
    return [executables["setpriv"][0], "--pdeathsig", "TERM", "--", str(RUNNER), executables["nice"][0], "-n", "10",
            executables["ionice"][0], "-c", "2", "-n", "7", *python, "worker"]


class Session:
    """One contained worker: the plan goes in, validated records come out; every HIT is fsynced, then acknowledged."""

    def __init__(self, run: Run, plan: dict, sink: str, seconds: int, request: str = None, attempts_=(),
                 controls=frozenset(), roots=()):
        self.run, self.plan, self.sink, self.request = run, plan, sink, request
        self.attempts, self.controls, self.roots = set(map(tuple, attempts_)), set(controls), set(roots)
        self.records, self.checks, self.completed, self.facts, self.reasons = [], {}, {}, [], []
        self.control_reports, self.observations, self.counters, self.hits = [], [], {}, 0
        self.end, self.seq, self.root, self.bad, self.seconds = None, 0, None, False, seconds

    def fail(self, reason: str) -> None:
        self.bad = True
        self.reasons.append(reason)

    def run_worker(self) -> None:
        body = json.dumps(self.plan, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
        self.nonce, self.seal = secrets.token_bytes(16), wire.keyed(self.run.key, b"plan", body)
        plan_r, plan_w = os.pipe()
        proto_r, proto_w = os.pipe()
        ack_r, ack_w = os.pipe()
        env = {"PATH": CHILD_PATH, "HOME": self.run.env.get("HOME", ""), "LC_ALL": "C",
               "XDG_RUNTIME_DIR": str(self.run.runtime), "ECOSYSTEM_JOB_SECONDS": str(self.seconds),
               "ECOSYSTEM_JOB_CPU_QUOTA": "200%", "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null",
               "GIT_NO_REPLACE_OBJECTS": "1", "GIT_TERMINAL_PROMPT": "0"}
        argv = launch_argv(self.plan["exes"]) + [str(plan_r), str(proto_w), str(ack_r)]
        hook("before_launch", argv)
        try:
            self.process = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                            stderr=subprocess.DEVNULL, pass_fds=(plan_r, proto_w, ack_r),
                                            close_fds=True, start_new_session=True, env=env)
        finally:
            for fd in (plan_r, proto_w, ack_r):
                os.close(fd)
        try:
            with _suppress(OSError):
                _write_all(plan_w, wire.PLAN.pack(b"CPPL", 1, 1, 0, self.nonce, len(body), hashlib.sha256(body).digest(),
                                                  0) + body)
            os.close(plan_w)
            self.read_records(proto_r, ack_w)
        finally:
            os.close(proto_r)
            with _suppress(OSError):
                os.close(ack_w)
            self.stop()

    def read_records(self, proto: int, ack: int) -> None:
        deadline, buffer = time.monotonic() + self.seconds + 30, b""
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return self.fail("deadline")
            if not select.select([proto], [], [], min(remaining, 1.0))[0]:
                continue
            chunk = os.read(proto, 65536)
            if not chunk:
                if buffer:
                    self.fail("protocol_error")
                return
            buffer += chunk
            while len(buffer) >= wire.RECORD.size and not self.bad:
                record, buffer = wire.unpack(buffer[:wire.RECORD.size]), buffer[wire.RECORD.size:]
                if not self.accept(record):
                    self.fail("protocol_error")
                    return
                if record.kind == wire.HIT:
                    self.durable_hit(record, ack)

    def stop(self) -> None:
        """End the runner's group (its trap stops the scope), then reap; 78/64 is containment_unavailable."""
        with _suppress(OSError):
            if self.process.poll() is None and (self.bad or self.end is None):
                os.killpg(self.process.pid, signal.SIGTERM)
        try:
            code = self.process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            with _suppress(OSError):
                os.killpg(self.process.pid, signal.SIGKILL)
            code = self.process.wait()
        if code in (64, 78):
            self.fail("containment_unavailable")
        elif code != 0 and self.end is not None and self.end.status == wire.STATUS["complete"]:
            self.fail("protocol_error")

    def durable_hit(self, record, ack: int) -> None:
        self.hits += 1
        self.run.append("hit", request=self.request or "", sink=self.sink, subpass=record.subpass,
                        root=(self.root or bytes(16)).hex(), object=record.object.hex(), check=record.check,
                        mode=record.mode, view=record.view, path=record.path,
                        consumer=CONSUMERS[record.consumer - 1], attempt=record.attempt, count=record.observed)
        os.write(ack, wire.ACK.pack(b"CPAK", 1, 1, 0, self.nonce, record.seq))
        hook("after_durable_hit")

    def accept(self, r) -> bool:
        """Every field of every kind (contract 10.2): anything unknown, out of range, unbound, out of order or set
        where its kind leaves it unused fails."""
        if r.magic != wire.MAGIC or r.version != wire.VERSION or r.nonce != self.nonce or r.seq != self.seq + 1 \
                or self.end is not None or r.kind not in PERMITTED:
            return False
        self.seq = r.seq
        AUDIT.append(r)
        if unused_set(r):
            return False
        sink = wire.SINKS.get(self.sink, 0)
        if r.sink not in (0, sink) or r.subpass != self.plan.get("subpass", 0) or r.mode > 7 or r.view > 7 \
                or r.klass > 8 or r.path >= len(wire.PATHS) or r.status > 4 or r.reason >= len(wire.REASONS) \
                or r.consumer > 6:
            return False
        if max(r.check, r.observed, r.expected, r.aux) > (1 << 48) or r.subpass > 1:
            return False
        if self.seq == 1 and (r.kind != wire.BEGIN or any(r.object)):
            return False
        if r.kind == wire.BEGIN:
            if r.seal != self.seal or (any(r.object) and r.object not in self.roots):
                return False
            self.root = r.object if any(r.object) else None
        elif r.kind == wire.INVENTORY:
            if r.check != len(self.checks) + 1 or not any(r.object):
                return False
            self.checks[r.check] = (r, self.root)
        elif r.kind in (wire.HIT, wire.OBSERVATION, wire.CONTROL, wire.RESULT) and r.check:
            if r.check not in self.checks or r.check in self.completed:
                return False
            declared = self.checks[r.check][0]
            if (r.sink, r.mode, r.view) != (declared.sink, declared.mode, declared.view):
                return False
            if r.kind != wire.CONTROL and (r.path, r.object) != (declared.path, declared.object):
                return False
            if r.kind == wire.RESULT:
                self.completed[r.check] = r
            elif r.kind == wire.HIT:
                return r.klass == 1 and r.observed > 0 and (r.consumer, r.attempt) in self.attempts
            elif r.kind == wire.OBSERVATION:
                tag = r.klass == wire.CLASSES["tag"]
                if r.klass not in (2, 3, 4, 6) or r.observed < 1 or r.expected or r.aux \
                        or (tag and (r.consumer, r.attempt) not in self.attempts) or (not tag and (r.consumer or r.attempt)):
                    return False
                self.observations.append((r, self.checks[r.check][1]))
            elif r.kind == wire.CONTROL:
                if r.klass not in (5, 7, 8) or r.object.hex() not in self.controls or r.aux:
                    return False
                self.control_reports.append(r)
        elif r.kind == wire.RESULT:  # check 0: the sink summary, once
            if 0 in self.completed:
                return False
            self.completed[0] = r
        elif r.kind == wire.FACT:
            if r.check not in wire.FACTS.values():
                return False
            if r.check in (1, 5, 7, 8, 10, 11) and r.observed > 2:
                return False
            self.facts.append(r)
        elif r.kind == wire.COUNTER:
            if r.check not in wire.COUNTERS.values() or r.check in self.counters:
                return False
            self.counters[r.check] = r.observed
        elif r.kind == wire.END:
            self.end = r
        else:
            return False
        return True

    def outcome(self) -> dict:
        """complete only with END complete, every declared check terminated complete (absent/not covered allowed),
        the summary complete, every required control reported equal, stable seals and a clean runner exit."""
        reasons = list(self.reasons)
        end = self.end
        if end is None:
            reasons.append("protocol_error")
        elif end.status != wire.STATUS["complete"] or end.aux or end.observed != len(self.checks) \
                or end.expected != len(self.checks):
            reasons.append(wire.REASONS[self.completed[0].reason] if 0 in self.completed else "protocol_error")
        if set(self.checks) - set(self.completed):
            reasons.append("protocol_error")
        for ident, result in self.completed.items():
            if ident and result.status == wire.STATUS["incomplete"]:
                reasons.append(wire.REASONS[result.reason])
            if ident and result.status == wire.STATUS["complete"] and (
                    result.exit not in (0, 1) or result.aux or result.reason or result.observed != result.expected):
                reasons.append("protocol_error")
        summary = self.completed.get(0)
        if summary is None or summary.status != wire.STATUS["complete"]:
            reasons.append(wire.REASONS[summary.reason] if summary else "protocol_error")
        seals = {record.seal for record, _root in self.checks.values() if any(record.seal)}
        if end is not None and seals and seals != {end.seal}:
            reasons.append("inventory_unreconciled")
        reasons += self.control_gaps()
        declared_roots = {root for _record, root in self.checks.values() if root}
        if self.roots - declared_roots:
            reasons.append("protocol_error")
        reasons = list(dict.fromkeys(reason for reason in reasons if reason != "ok"))
        absent = sorted({self.checks[ident][1].hex() for ident, record in self.completed.items()
                         if ident and record.status == wire.STATUS["absent"] and self.checks[ident][1]})
        return {"status": "incomplete" if reasons else "complete", "reasons": reasons, "checks": len(self.checks),
                "completed": len(self.completed) - (0 in self.completed), "hits": self.hits,
                "counters": {name: self.counters.get(code, 0) for name, code in wire.COUNTERS.items()},
                "absent": absent,
                "roots": sorted(root.hex() for root in declared_roots),
                "ledger": [[ident, (root or bytes(16)).hex(), record.mode, record.view,
                            self.completed[ident].status if ident in self.completed else 0,
                            self.completed[ident].reason if ident in self.completed else wire.R["protocol_error"]]
                           for ident, (record, root) in self.checks.items()],
                "observations": [[r.klass, r.consumer, r.attempt, r.path, (root or bytes(16)).hex(), r.observed]
                                 for r, root in self.observations],
                "controls": [len(self.control_reports), sum(r.observed == r.expected for r in self.control_reports)]}

    def control_gaps(self) -> list:
        """Each check's required controls, and each used mode's controls, reported with observed equal to expected."""
        spec, gaps = self.plan.get("controls"), []
        if not spec:
            return gaps
        reports = {}
        for report in self.control_reports:
            reports.setdefault(report.check, {})[report.object.hex()] = report
        required = {(1, 1): [row[1] for row in spec["m1"]] + [row[1] for row in spec["m1_negative"]],
                    (1, 2): [row[1] for row in spec["bom"]] + [row[1] for row in spec["bom_negative"]],
                    (2, 4): [spec["inband"]["m2bom"]], (3, 1): [spec["inband"]["m3"], spec["anchor"]],
                    (7, 1): [spec["inband"]["u4"]]}
        formats = set()
        for ident, (record, _root) in self.checks.items():
            mode_view = (record.mode, record.view)
            wanted = required.get(mode_view, [])
            if record.expected == 1 and record.mode in (2, 4, 5) and record.view in (3, 5):
                wanted = [spec["inband"][{2: "m2raw", 4: "m4", 5: "m5"}[record.mode]]]
            if record.mode == 2 and record.expected in (2, 3, 4, 5) and record.view == 3:
                formats.add({2: "gzip", 3: "bzip2", 4: "xz", 5: "lzma"}[record.expected])
            result = self.completed.get(ident)
            if result is None or result.status != wire.STATUS["complete"] or record.expected == 0:
                continue  # a producer-only stage has no scanner of its own; its scanner check carries the controls
            for control in wanted:
                report = reports.get(ident, {}).get(control)
                if report is None or (report.observed < 1 if report.klass == 8 else report.observed != report.expected):
                    gaps.append("control_missing")
        seen = {report.object.hex() for report in self.control_reports}
        modes = {record.mode for record, _root in self.checks.values()}
        needed = [row[2] for row in spec["m2"] if row[1] in formats]
        needed += [spec["m4"][key] for key in ("loose", "packed", "keep_id")] if 4 in modes else []
        needed += [row[1] for row in spec["m5"]] if 5 in modes else []
        needed += [row[0] for row in spec["m6"]["ids"]]
        if any(ident not in seen for ident in needed):
            gaps.append("control_missing")
        if any(r.observed != r.expected and r.klass == 7 for r in self.control_reports):
            gaps.append("negative_control_matched")
        return gaps


# The fields each CP03 kind may set; every other field must be zero (contract 10.2, "unused fields must be zero").
PERMITTED = {
    wire.BEGIN: {"sink", "subpass", "seal", "object"},
    wire.INVENTORY: {"check", "sink", "mode", "view", "path", "subpass", "expected", "object", "seal", "aux"},
    wire.HIT: {"check", "sink", "mode", "view", "klass", "path", "consumer", "attempt", "subpass", "observed", "object"},
    wire.RESULT: {"check", "sink", "mode", "view", "path", "status", "reason", "subpass", "observed", "expected", "exit",
                  "object", "aux"},
    wire.CONTROL: {"check", "sink", "mode", "view", "klass", "subpass", "observed", "expected", "object"},
    wire.FACT: {"check", "observed", "expected", "object", "seal"},
    wire.END: {"sink", "subpass", "status", "observed", "expected", "seal", "aux"},
    wire.OBSERVATION: {"check", "sink", "mode", "view", "klass", "path", "consumer", "attempt", "subpass", "observed",
                       "object"},
    wire.COUNTER: {"check", "sink", "subpass", "observed"},
}


def unused_set(record) -> bool:
    """A reserved byte or a field that the record's kind does not use is nonzero."""
    for name in wire.NAMES:
        if name in ("magic", "version", "kind", "nonce", "seq") or name in PERMITTED[record.kind]:
            continue
        value = getattr(record, name)
        if value != (bytes(len(value)) if isinstance(value, bytes) else 0):
            return True
    return False


def _write_all(fd: int, data: bytes) -> None:
    view = memoryview(data)
    while view:
        view = view[os.write(fd, view):]


def setup_child(run: Run, op: str, executables: dict, extra: dict) -> Session:
    plan = {"op": op, "run_key": run.key.hex(), "setpriv": executables["setpriv"][0], "exes": executables,
            "child_path": CHILD_PATH, **extra}
    session = Session(run, plan, "setup", SCOPE_SECONDS["setup"])
    session.run_worker()
    if session.end is None or session.bad:
        raise Refused("setup_failed" if not session.reasons or session.reasons[-1] == "protocol_error"
                      else session.reasons[-1])
    return session


def fact(session: Session, name: str, **match) -> list:
    return [record for record in session.facts if record.check == wire.FACTS[name]
            and all(getattr(record, key) == value for key, value in match.items())]


# ---- Commands --------------------------------------------------------------------------------------------------------
def platform_check() -> None:
    if not sys.platform.startswith("linux"):
        raise Refused("unsupported_platform")


def prepare(args, env) -> int:
    platform_check()
    runner.disable_core_dumps()
    run = Run(env, "cp-" + datetime.now(timezone.utc).strftime("%Y%m%dt%H%M%Sz") + "-" + secrets.token_hex(3))
    run.create()
    run.key = secrets.token_bytes(32)
    run.write("key", run.key)
    run.write("ref", b"")
    ref = os.stat(run.dir / "ref")
    home = env.get("HOME") or ""
    ordinary = env.get("CODEX_HOME") or f"{home}/.codex"
    codex = [ordinary] + ([os.path.abspath(args.codex_home)] if args.codex_home else [])
    if len(set(codex)) != len(codex) or not os.path.isabs(home):
        raise Refused("codex_home_invalid")
    run.write("homes", json.dumps(codex).encode())
    if args.session:
        if not SESSION.fullmatch(args.session):
            raise Refused("session_invalid")
        run.write("session", args.session.encode())
    patterns = {}
    for consumer in CONSUMERS:
        patterns[f"{consumer}.1"] = run.write(f"patterns/{consumer}.1",
                                              ("\n".join(forms(new_canary())) + "\n").encode())
    anchor = control_value("CNRYJRN")
    run.write("anchor", anchor.encode() + b"\n")
    executables = resolve_executables()
    if not executables["rg"] or not executables["setpriv"] or not executables["python3"]:
        raise Refused("unreviewed_scanner")
    roots = all_roots(run, env)
    pointers = pointer_paths(env)
    session = setup_child(run, "prepare", executables, {
        "roots": [root for sink in roots for root in roots[sink]], "pointers": {"current": pointers, "bound": []},
        "journal": {"anchor": anchor, "cursor_file": str(run.dir / "child-cursor")}, "checkout": str(ROOT),
        "claude_dir": str(cs.claude_config_dir(env)), "store_root": str(cs.expand_template(cs.STORE_ROOT, env))})
    names = sorted(executables)
    versions = {name: record.observed for record in fact(session, "executable_version")
                for name in [names[record.expected] if record.expected < len(names) else "sqlite"]}
    if versions.get("rg") not in wire.REVIEWED_RG:
        raise Refused("unreviewed_scanner")
    if not fact(session, "journal_binding", observed=1):
        raise Refused("journal_cursor_missing")
    for record in fact(session, "executable_fingerprint"):
        name = names[record.expected]
        if executables[name] and record.seal != wire.keyed(run.key, b"exe", name, executables[name][1]):
            raise Refused("tool_changed")
    for record in fact(session, "pointer_binding"):
        if record.observed == 2:
            raise Refused("pointer_target_not_file")
    presence = {record.object.hex(): record.observed == 1 for record in fact(session, "root_presence")}
    checkout = fact(session, "checkout")
    run.append("prepared", tools={name: wire.sha256_file(path) for name, path in TOOLS.items()},
               executables={name: (value[1] if value else "") for name, value in executables.items()},
               versions=versions, rg_version=versions["rg"],
               checkout=checkout[0].seal.hex() if checkout else "", ref={"dev": ref.st_dev, "ino": ref.st_ino,
                                                                         "ctime_ns": ref.st_ctime_ns},
               threshold_ns=ref.st_ctime_ns - MARGIN_NS,
               roots={sink: [[root["id"], presence.get(root["id"], False)] for root in roots[sink]] for sink in roots},
               policy=digest({sink: [root["kind"] for root in roots[sink]] for sink in roots}),
               exclusions=digest(exclusions(home, codex, env, args.transcripts, "agent", [])),
               anchor=digest(anchor.encode()), patterns=patterns, transcripts=args.transcripts,
               session_known=bool(args.session), session=digest(args.session.encode()) if args.session else "",
               proxy_verified=False, pointers=[record.seal.hex() for record in fact(session, "pointer_binding")],
               guard_pinned=bool(fact(session, "guard_pin", observed=1)),
               journal_bound=bool(fact(session, "journal_binding", observed=1)))
    say(run, f"run: {run.id}")
    return 0


def all_roots(run: Run, env) -> dict:
    """sink -> [{id, kind, path, present?}] for every configured sink; ids are keyed with the run key."""
    recipes = sink_roots(env.get("HOME") or "", os.getuid(), homes(run), str(run.dir / "child-cursor"))
    return {sink: [{"id": keyed(run.key, b"root", sink, kind, path), "kind": kind, "path": path}
                   for kind, path in recipes[sink]] for sink in recipes}


def integrity(run: Run) -> list:
    """Codes detected at this invocation: boot, tool, executable and pattern changes and a backward clock step."""
    prepared, codes = run.events[0], []
    if boot.small_text(boot.BOOT_ID) != prepared["boot_id"]:
        codes.append("boot_changed")
    if {name: wire.sha256_file(path) for name, path in TOOLS.items()} != prepared["tools"] or {
            name: (value[1] if value else "") for name, value in resolve_executables().items()} != prepared["executables"]:
        codes.append("tool_changed")
    codes += pattern_integrity(run)
    _utc, realtime, boottime = clock()
    drift = (realtime - prepared["realtime_ns"]) - (boottime - prepared["boottime_ns"])
    if drift < -DRIFT_NS:
        codes.append("clock_stepped")
    for code in codes:
        if not any(event["event"] == "integrity_failed" and event["code"] == code for event in run.events):
            run.append("integrity_failed", code=code) if code != "clock_stepped" else run.append(
                "clock_stepped", drift_ns_seen=drift)
    return codes


def open_run(args, env) -> Run:
    platform_check()
    run = Run(env, args.run)
    run.load()
    return run


def scan(args, env) -> int:
    if args.user_run and not (os.isatty(0) and os.isatty(1) and not env.get("CLAUDECODE")):
        raise Refused("user_run_needs_terminal")
    if args.phase == "comparison" and not args.user_run:
        raise Refused("comparison_needs_user_run")
    if args.user_run and args.phase == "baseline":
        raise Refused("baseline_is_agent_run")
    run = open_run(args, env)
    if not run.valid:
        return report(run, [])
    runner.disable_core_dumps()
    group = "user" if args.user_run else "agent"
    event = run.append("scan_requested", request=secrets.token_hex(6), phase=args.phase, group=group,
                       selection="all" if args.phase == "comparison" else "changed")
    hook("after_request")
    request, results = Request(run, event), {}
    signals = install_interrupts()
    try:
        codes = integrity(run)
        if codes:
            raise Refused(codes[0])
        spec = request.build()
        union, sha, classes = build_union(run, request)
        run.extra = list(request.controls.values())
        hook("before_exec_check")
        executables = resolve_executables()
        if {name: (value[1] if value else "") for name, value in executables.items()} != run.events[0]["executables"]:
            raise Refused("tool_changed")
        setup_child(run, "controls", executables, {"controls": spec})
        sinks = sinks_for(args.phase, group)
        roots = all_roots(run, env)
        bound = [[consumer, attempt] for consumer, numbers in attempts(run).items() for attempt in numbers]
        planned = {sink: [root["id"] for root in roots[sink]] for sink in sinks}
        hook("before_plan")
        run.append("scan_planned", request=request.id, attempts=bound, union=sha,
                   classes={str(klass): sum(1 for row in classes if row[1] == klass) for klass in range(9)},
                   sinks=planned, controls={kind: request.ident(kind) for kind in sorted(request.controls)},
                   executables=digest(run.events[0]["executables"]),
                   exclusions=digest(exclusions(env.get("HOME", ""), homes(run), env,
                                                run.events[0]["transcripts"], group, [])),
                   deadlines={sink: SCOPE_SECONDS[sink] for sink in sinks})
        for sink in sinks:
            results[sink] = scan_sink(run, env, request, sink, roots, sinks, executables,
                                      (union, sha, classes), spec, bound)
            hook("between_sinks", sink)
        status = "complete" if all(result["status"] == "complete" for result in results.values()) else "incomplete"
        run.append("scan_finished", request=request.id, status=status, sinks=results,
                   reasons=sorted({reason for result in results.values() for reason in result["reasons"]}))
    except (Refused, OSError, Interrupt) as error:
        reason = "interrupted" if isinstance(error, Interrupt) else str(error) if isinstance(error, Refused) \
            else "setup_failed"
        with _suppress(Exception):
            run.append("scan_finished", request=request.id, status="incomplete", sinks=results,
                       reasons=[reason if reason in wire.R or reason in CODES else "setup_failed"])
    finally:
        request.close()
        restore_interrupts(signals)
    for sink, result in results.items():
        say(run, f"{sink}: {result['status'] if result['status'] != 'complete' or not result['absent_only'] else 'absent'}"
                 f" files={result['counters']['selected']} views={result['checks']} hits={result['hits']}"
                 f" controls={result['controls'][1]}/{result['controls'][0]}")
    return report(run, [], exit_only=True, request=request.id)


CODES = {"boot_changed", "tool_changed", "pattern_file_mismatch", "clock_stepped", "guard_not_pinned"}


def sinks_for(phase: str, group: str) -> tuple:
    if phase == "comparison":
        return AGENT_SINKS + USER_SINKS
    return USER_SINKS if group == "user" else AGENT_SINKS


def scan_sink(run: Run, env, request: Request, sink: str, roots: dict, sinks: tuple, executables: dict, union: tuple,
              spec: dict, bound: list) -> dict:
    """One sink: subpass 0, and one automatic stability retry (subpass 1) from a new pre-walk (contract 9.3)."""
    prepared, home, codex = run.events[0], env.get("HOME", ""), homes(run)
    presence = {root_id: present for pairs in prepared["roots"].values() for root_id, present in pairs}
    group = "user" if sink.startswith("U") else "agent"
    if request.phase == "comparison":
        group = "comparison"
    exact, glob = exclusions(home, codex, env, prepared["transcripts"], "user" if group != "agent" else "agent",
                             pointer_paths(env))
    session_file = run.dir / "session"
    plan = {"op": "scan", "run_key": run.key.hex(), "sink": wire.SINKS[sink], "setpriv": executables["setpriv"][0],
            "exes": executables, "child_path": CHILD_PATH, "patterns": union[0], "patterns_sha256": union[1],
            "classes": union[2], "controls": spec, "rg_version": prepared["rg_version"],
            "roots": [dict(root, present=presence.get(root["id"], False)) for root in roots[sink]],
            "covered": [root["path"] for name in sinks for root in roots[name] if root["kind"] in ("dir", "file",
                                                                                                 "tasks", "git")],
            "user_roots": [root["path"] for name in USER_SINKS for root in roots[name]] if group == "agent" else [],
            "exclude": [{"path": path, "class": klass} for path, klass in exact],
            "exclude_glob": [{"dir": directory, "glob": pattern, "class": klass} for directory, pattern, klass in glob],
            "link_pairs": [[f"{home}/.claude/skills", f"{home}/.agents/skills"]]
            + [[f"{path}/tmp/arg0", f"{home}/.local/share/codex-ecosystem"] for path in codex],
            "pointers": {"bound": prepared["pointers"], "current": pointer_paths(env)},
            "threshold_ns": prepared["threshold_ns"], "selection": request.selection,
            "session": session_file.read_text() if session_file.exists() else None,
            "dumper_argv": [executables["python3"][0], "-I", "-S", str(WORKER), "sqlite-dumper"]
            if DUMPER_COMMAND is None else DUMPER_COMMAND}
    result = None
    deadline = time.monotonic() + min(SCOPE_SECONDS[sink], PHASE_SECONDS[request.phase][sink])
    for subpass in (0, 1):
        plan["subpass"] = subpass
        seconds = max(1, int(deadline - time.monotonic()))
        plan["budget_seconds"] = seconds
        session = Session(run, plan, sink, seconds, request.id, [
            (CONSUMERS.index(consumer) + 1, attempt) for consumer, attempt in bound],
            controls={row[4] for row in union[2] if row[4]} | {row[1] for row in spec["m1_negative"]}
            | {row[1] for row in spec["bom_negative"]}, roots={bytes.fromhex(root["id"]) for root in roots[sink]})
        session.run_worker()
        result = session.outcome()
        result["subpass"] = subpass
        run.append("scan_inventory", request=request.id, sink=sink, subpass=subpass,
                   seal=(session.end.seal.hex() if session.end else ""), checks=result["checks"],
                   counters=result["counters"])
        if not result["reasons"] or not set(result["reasons"]) <= {
                "file_set_changed", "format_changed", "inventory_unreconciled"}:
            break
    result["absent_only"] = bool(result["absent"]) and len(result["absent"]) == len(roots[sink])
    return result


class Interrupt(Exception):
    pass


def install_interrupts() -> dict:
    def interrupted(_signum, _frame):
        raise Interrupt()
    return {signum: signal.signal(signum, interrupted)
            for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP, signal.SIGQUIT)}


def restore_interrupts(previous: dict) -> None:
    for signum, handler in previous.items():
        signal.signal(signum, handler)


def store_root(env) -> tuple:
    """The store directory handle, checked; never created, chmodded or listed (contract 7)."""
    root = cs.expand_template(cs.STORE_ROOT, env)
    try:
        fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except OSError:
        raise Refused("store_unusable") from None
    info = os.fstat(fd)
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
        os.close(fd)
        raise Refused("store_not_private")
    return fd, root


def arm(args, env) -> int:
    run = open_run(args, env)
    if not run.valid:
        return report(run, [])
    runner.disable_core_dumps()
    if integrity(run):
        raise Refused("integrity_failed")
    verdict = classify(run.events)
    if verdict["hits"] or any(code.startswith("baseline_") or code == "no_baseline" for code in verdict["codes"]):
        raise Refused("baseline_not_clean")
    if any(code in ("store_armed", "arming_unresolved") for code in verdict["codes"]):
        raise Refused("store_armed")
    inventory = runner.load_inventory()
    runner.check_injectable(runner.find_entry(ENTRY, inventory))
    codex, root_id, present = homes(run), "", False
    if args.consumer in ("codex-exec", "omniroute-lane"):
        wanted = codex[0] if args.consumer == "codex-exec" and not args.codex_home else args.codex_home
        if not wanted or os.path.abspath(wanted) not in codex or (args.consumer == "omniroute-lane"
                                                                  and os.path.abspath(wanted) == codex[0]):
            raise Refused("baseline_scope_missing")
        roots = all_roots(run, env)
        root = next(root for root in roots["A4"] if root["path"] == os.path.abspath(wanted))
        root_id = root["id"]
        present = dict(p for pairs in run.events[0]["roots"].values() for p in map(tuple, pairs)).get(root_id, False)
    executables = resolve_executables()
    session = setup_child(run, "arm", executables, {"claude_dir": str(cs.claude_config_dir(env)),
                                                     "store_root": str(cs.expand_template(cs.STORE_ROOT, env))})
    if not fact(session, "guard_pin", observed=1):
        raise Refused("guard_not_pinned")
    if not fact(session, "store_outside_worktree", observed=1):
        raise Refused("store_inside_worktree")
    numbers = attempts(run).get(args.consumer, [1])
    armed_before = any(e["event"] == "armed" and e["consumer"] == args.consumer for e in run.events)
    attempt = numbers[-1] + 1 if armed_before else numbers[-1]
    if attempt not in numbers:
        run.write(f"patterns/{args.consumer}.{attempt}", ("\n".join(forms(new_canary())) + "\n").encode())
    pattern = digest(run.read(f"patterns/{args.consumer}.{attempt}"))
    canary = canary_of(run, args.consumer, attempt)
    fd, _root = store_root(env)
    blocked = signal.pthread_sigmask(signal.SIG_BLOCK, (signal.SIGINT, signal.SIGTERM, signal.SIGHUP, signal.SIGQUIT))
    try:
        with _suppress(FileNotFoundError):
            os.stat(STORE_FILE, dir_fd=fd, follow_symlinks=False)
            raise Refused("store_file_exists")
        run.append("arming", consumer=args.consumer, attempt=attempt, pattern=pattern, root=root_id,
                   root_present=present)
        hook("after_arming")
        writer.create_exclusively(fd, STORE_FILE, writer.encode(VARIABLE, canary))
        hook("after_publication")
        info = os.stat(STORE_FILE, dir_fd=fd, follow_symlinks=False)
        run.append("armed", consumer=args.consumer, attempt=attempt, dev=info.st_dev, ino=info.st_ino,
                   ctime_ns=info.st_ctime_ns,
                   guard_pinned=True, recovered=False)
    except writer.Refused:
        raise Refused("store_file_exists") from None
    finally:
        signal.pthread_sigmask(signal.SIG_SETMASK, blocked)
        os.close(fd)
    leak = " --leak-check" if args.consumer == "systemd-user-unit" else ""
    say(run, f"probe: python3 -I tools/credentials/credential_run.py {ENTRY} -- python3 -I tools/credentials/"
             f"canary_probe.py --run {run.id} --consumer {args.consumer} --attempt {attempt}{leak}")
    say(run, f"then: python3 tools/credentials/canary_proof.py disarm --run {run.id}")
    return 0


def disarm(args, env, run: Run = None) -> int:
    run = run or open_run(args, env)
    if not run.valid:
        return report(run, [])
    state = arm_state(run.events)
    fd, _root = store_root(env)
    try:
        if state["pending"]:
            consumer, attempt, arming = state["pending"]
            info = _stat(fd)
            if info is None or not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1 \
                    or stat.S_IMODE(info.st_mode) != 0o600 \
                    or not arming["realtime_ns"] - ARM_RECOVERY_NS <= info.st_ctime_ns <= time.time_ns():
                raise Refused("arming_unresolved")
            run.append("armed", consumer=consumer, attempt=attempt, dev=info.st_dev, ino=info.st_ino,
                       ctime_ns=info.st_ctime_ns,
                       guard_pinned=True, recovered=True)
            state = arm_state(run.events)
        if not state["armed"]:
            raise Refused("not_armed")
        consumer, attempt, armed = state["armed"]
        info, removed = _stat(fd), False
        if info is not None:
            # (dev, ino) plus the ctime of publication: a recreated file can reuse a freed inode number.
            if (info.st_dev, info.st_ino, info.st_ctime_ns) != (armed["dev"], armed["ino"], armed["ctime_ns"]) \
                    or not stat.S_ISREG(info.st_mode) \
                    or info.st_nlink != 1:
                raise Refused("foreign_store_file")
            os.unlink(STORE_FILE, dir_fd=fd)
            removed = True
        run.append("disarmed", consumer=consumer, attempt=attempt, removed=removed, absent_verified=_stat(fd) is None)
    finally:
        os.close(fd)
    say(run, f"disarmed: {consumer} attempt {attempt}")
    return 0


def _stat(fd: int):
    try:
        return os.stat(STORE_FILE, dir_fd=fd, follow_symlinks=False)
    except FileNotFoundError:
        return None


def arm_state(events: list) -> dict:
    pending = armed = None
    for event in events:
        if event["event"] == "arming":
            pending = (event["consumer"], event["attempt"], event)
        elif event["event"] == "armed":
            armed, pending = (event["consumer"], event["attempt"], event), None
        elif event["event"] == "disarmed":
            armed = None
    return {"pending": pending, "armed": armed}


# ---- The one classifier (contract 12; C4, C13) ----------------------------------------------------------------------
# Verdict codes: record_invalid is invalid (exit 4); every other code is incomplete (exit 3); a hit is leak (5).
RECORDING = {"systemd-user-unit": ("A11", {9}), "fresh-claude-session": ("A1", {1}), "subagent": ("A1", {2}),
             "workflow-child": ("A1", None), "codex-exec": ("A4", {5}), "omniroute-lane": ("A4", {5})}


def classify(events: list, now_codes=(), masking=None) -> dict:
    codes = list(now_codes)
    hits = sum(event["count"] for event in events if event["event"] == "hit")
    prepared = events[0]
    for event in events:
        if event["event"] == "integrity_failed":
            codes.append(event["code"])
        elif event["event"] == "clock_stepped":
            codes.append("clock_stepped")
    requests, latest, arms = {}, {}, {}
    for event in events:
        kind = event["event"]
        if kind == "scan_requested":
            requests[event["request"]] = {"requested": event, "planned": None, "finished": None}
            latest[(event["phase"], event["group"])] = event["request"]
        elif kind in ("scan_planned", "scan_finished"):
            requests[event["request"]][kind.split("_")[1]] = event
        elif kind in ("arming", "armed", "disarmed"):
            arms.setdefault(event["consumer"], []).append(event)
    arm_events = [event for event in events if event["event"] in ("arming", "armed", "disarmed")]
    first_arming = next((event["seq"] for event in arm_events if event["event"] == "arming"), None)
    last_disarm = max((event["boottime_ns"] for event in arm_events if event["event"] == "disarmed"), default=None)
    latest_attempts = {consumer: max(event["attempt"] for event in rows) for consumer, rows in arms.items()}
    agent_roots = {root_id for sink in AGENT_SINKS for root_id, _present in prepared["roots"].get(sink, [])}
    current = sorted((consumer, number) for consumer, numbers in all_attempts(events).items() for number in numbers)

    def group_codes(key: tuple, name: str) -> tuple:
        """(codes, finished event or None) for the latest request of (phase, group). The latest request decides:
        a missing plan or finish is unfinished, whatever an earlier request said (contract 5)."""
        request_id = latest.get(key)
        if request_id is None:
            return ([f"no_{name}"] if name in ("baseline", "final") else []), None
        state, found = requests[request_id], []
        planned, finished, requested = state["planned"], state["finished"], state["requested"]
        if planned is None or finished is None:
            return [f"{name}_unfinished"], None
        for sink in planned["sinks"]:
            row = finished["sinks"].get(sink)
            if row is None:
                found.append(f"sink_not_scanned:{sink}" if name == "final" else f"{name}_sink_not_scanned:{sink}")
            elif row["status"] != "complete":
                found += [f"sink_incomplete:{sink}:{reason}" if name == "final" else f"{name}_sink_incomplete:{sink}"
                          for reason in row["reasons"]]
                if "control_missing" in row["reasons"]:
                    found.append(f"control_missing:{sink}" if name == "final" else f"{name}_control_missing")
            elif (row["checks"] != row["completed"] or len(row.get("ledger", [])) != row["checks"]
                  or set(planned["sinks"][sink]) != set(row.get("roots", []))
                  or any(item[4] not in (1, 3, 4) for item in row.get("ledger", []))):
                found.append("inventory_unreconciled")
        required_sinks = sinks_for(*key)
        if set(planned["sinks"]) != set(required_sinks):
            found.append(f"{name}_incomplete")
        for sink in required_sinks:
            required_roots = {root for root, _present in prepared["roots"].get(sink, [])}
            if required_roots != set(planned["sinks"].get(sink, [])):
                found.append("baseline_scope_missing" if name == "baseline" else "inventory_unreconciled")
        if finished["status"] != "complete" or found:
            found.insert(0, f"{name}_incomplete")
        if name != "baseline":
            if any(event["seq"] > requested["seq"] for event in arm_events) \
                    or sorted(map(tuple, planned["attempts"])) != current:
                found.append(f"{name}_stale")
            if last_disarm is None or requested["boottime_ns"] - last_disarm < SETTLE_SECONDS * 10**9:
                found.append(f"{name}_too_early")
        return found, (finished if not found else None)

    baseline_codes, _baseline = group_codes(("baseline", "agent"), "baseline")
    codes += baseline_codes
    if latest.get(("baseline", "agent")):
        request = requests[latest[("baseline", "agent")]]
        if first_arming is not None and request["requested"]["seq"] > first_arming:
            codes.append("baseline_after_arm")
        if request["planned"] and not agent_roots <= {i for ids in request["planned"]["sinks"].values() for i in ids}:
            codes.append("baseline_scope_missing")
    final_codes, final = group_codes(("final", "agent"), "final")
    user_codes, user = group_codes(("final", "user"), "user_run")
    codes += final_codes + user_codes + group_codes(("comparison", "user"), "comparison")[0]
    session_known = prepared["session_known"]
    for consumer in CONSUMERS:
        rows = arms.get(consumer, [])
        armed = [event for event in rows if event["event"] == "armed"]
        if not armed:
            codes.append(f"not_armed:{consumer}")
            continue
        last = armed[-1]
        after = [event for event in rows if event["seq"] > last["seq"] and event["event"] == "disarmed"]
        if not after:
            codes.append(f"not_disarmed:{consumer}")
        elif not after[-1]["absent_verified"]:
            codes.append(f"disarm_unverified:{consumer}")
        if not last["guard_pinned"]:
            codes.append(f"guard_not_pinned_at_arm:{consumer}")
        if not recorded(consumer, last["attempt"], final, events, session_known):
            codes.append(f"recording_missing:{consumer}")
    if latest.get(("final", "user")):  # a requested U final needs the fresh session's tag in agentsview (U8 root 1)
        agentsview = prepared["roots"]["U8"][0][0]
        if not recorded("fresh-claude-session", latest_attempts.get("fresh-claude-session", 1), user, events,
                        session_known, sink="U8", root=agentsview):
            codes.append("user_arrival_missing:agentsview")
    state = arm_state(events)
    if state["armed"]:
        codes.append("store_armed")
    if state["pending"]:
        codes.append("arming_unresolved")
    if not prepared["guard_pinned"]:
        codes.append("guard_not_pinned")
    if masking is not None and final is not None:  # only unit attempts whose tag reached the journal count
        rows = final["sinks"].get("A11", {}).get("observations", [])
        tagged = {row[2] for row in rows if row[0] == 2 and row[1] == 1}
        expected = sum(count for attempt, count in masking.items() if attempt in tagged)
        if sum(row[5] for row in rows if row[0] == 3) != expected or any(row[0] == 4 for row in rows):
            codes.append("masking_markers_mismatch")
    codes = list(dict.fromkeys(codes))
    verdict = "leak" if hits else ("incomplete" if codes else "clean")
    return {"verdict": verdict, "codes": codes, "hits": hits, "final": final, "user": user}


def all_attempts(events: list) -> dict:
    found = {consumer: [1] for consumer in CONSUMERS}
    for event in events:
        if event["event"] == "arming" and event["attempt"] not in found[event["consumer"]]:
            found[event["consumer"]].append(event["attempt"])
    return found


def recorded(consumer: str, attempt: int, finished, events: list, session_known: bool, sink: str = None,
             root: str = None) -> bool:
    """The latest attempt's tag in its consumer's recording class (contract 12): journal, another session's main
    transcript or subagent, the coordinator's own workflow or subagent records when its session is known (any
    session's otherwise), or the rollout of the Codex home that consumer's arm named."""
    if finished is None or finished["status"] != "complete":
        return False
    wanted_sink, classes = RECORDING[consumer] if sink is None else (sink, None)
    if consumer == "workflow-child" and sink is None:
        classes = {15, 16} if session_known else {2, 3}
    if root is None and consumer in ("codex-exec", "omniroute-lane"):
        root = next((event["root"] for event in events if event["event"] == "arming" and event["consumer"] == consumer
                     and event["attempt"] == attempt), "")
    code = CONSUMERS.index(consumer) + 1
    return any(klass == 2 and owner == code and number == attempt and count > 0
               and (classes is None or path in classes) and (root is None or where == root)
               for klass, owner, number, path, where, count in finished["sinks"].get(wanted_sink, {})
               .get("observations", []))


def expected_markers(run: Run) -> dict:
    """attempt -> the full markers the real runner's Masker makes of that unit attempt's --leak-check output, stdout
    and stderr masked separately as the runner does (contract 12)."""
    counts = {}
    for event in run.events:
        if event["event"] == "armed" and event["consumer"] == "systemd-user-unit":
            counts[event["attempt"]] = masked_markers(canary_of(run, "systemd-user-unit", event["attempt"]))
    return counts


def masked_markers(canary: str) -> int:
    needles, total = runner.needles_for({VARIABLE: canary}, [VARIABLE]), 0
    for stream in probe.leak_output(canary):
        masker = runner.Masker(needles)
        total += (masker.feed(stream, 0.0) + masker.close()).count(MARKERS[0].encode())
    return total


# ---- Verdict, receipt and claim --------------------------------------------------------------------------------------
def report(run: Run, now_codes: list, receipt: bool = False, exit_only: bool = False, request: str = None) -> int:
    if not getattr(run, "valid", False):
        hits = sum(1 for event in run.events if isinstance(event, dict) and event.get("event") == "hit")
        say(run, f"verdict: invalid codes=record_invalid hits={hits}")
        return EXIT["invalid"]
    result = classify(run.events, now_codes, expected_markers(run))
    if exit_only:
        finished = next((event for event in reversed(run.events) if event["event"] == "scan_finished"
                         and event["request"] == request), None)
        if result["hits"]:
            return EXIT["leak"]
        return EXIT["clean"] if finished and finished["status"] == "complete" else EXIT["incomplete"]
    say(run, f"verdict: {result['verdict']} hits={result['hits']} codes={','.join(result['codes']) or 'none'}")
    if receipt:
        publish(run, result)
    return EXIT[result["verdict"]]


def claim(run: Run, result: dict) -> str:
    prepared = run.events[0]
    final = result["final"] or {"sinks": {}}
    complete = sorted(sink for sink, row in final["sinks"].items() if row["status"] == "complete"
                      and not row.get("absent_only"))
    absent = sorted(sink for sink, row in final["sinks"].items() if row.get("absent_only"))
    if result["verdict"] != "clean":
        return f"Canary proof {run.id}: {result['verdict']}; codes {', '.join(result['codes']) or 'none'}."
    user = result["user"]
    return (f"Canary proof {run.id}: clean for the coverage stated here. Each of six consumers used its latest "
            f"attempt's synthetic canary through the inventory-id credential runner, and its HMAC tag was found in its "
            f"specified recording class. The named complete roots {', '.join(complete)} had zero observations of any "
            f"of this run's canaries in the runner's enumerated raw/base64/base64url/percent/JSON/hex forms. "
            f"Selection was changed-since the prepare threshold. The files and directories passed pre/post identity, "
            f"entry-list and routing checks. The final result was requested at least {SETTLE_SECONDS // 60} minutes "
            f"after the last disarm. The systemd form corpus produced the expected full markers and zero partial "
            f"markers. User-run coverage: {'U1-U8' if user else 'none requested'}. Loki: not_covered:proxy_unverified."
            f" Not covered: {', '.join(absent) or 'no absent sink'}, "
            f"{'declined transcripts, ' if prepared['transcripts'] == 'exclude' else ''}"
            f"{'' if user else 'U1-U8 and agentsview arrival, '}key homes, pointer targets, declared links and special"
            f" file content, X categories, unsupported transformed forms, freed SQLite pages and superseded WAL frames, "
            f"process memory, remote copies, future client versions, adversarial agents, the quiescence residuals, "
            f"and the scan-side worker, dumper and ripgrep, which hold sink bytes by design (C12). "
            f"Session attribution {'known' if prepared['session_known'] else 'unknown (reduced assurance)'}.")


def publish(run: Run, result: dict) -> str:
    """A value-free receipt through credential_boot_receipt's private directory and create-only link."""
    state_home = run.env.get("XDG_STATE_HOME") or ""
    if not os.path.isabs(state_home):
        state_home = os.path.join(run.env.get("HOME") or "", ".local", "state")
    directory = boot.private_directory(Path(state_home, "native-agent-stack", "canary-proof"))
    prepared, final = run.events[0], result["final"] or {"sinks": {}}
    receipt_id = f"{run.id}-{run.events[-1]['seq']:06d}"
    receipt = {"schema_version": 1, "kind": "canary_proof_receipt", "receipt": receipt_id, "run": run.id,
               "record_high_water": run.events[-1]["seq"], "versions": prepared["versions"],
               "fingerprints": prepared["tools"], "checkout": prepared["checkout"], "created": clock()[0],
               "verdict": result["verdict"], "codes": result["codes"], "hits": result["hits"],
               "consumers": {consumer: max([e["attempt"] for e in run.events if e["event"] == "armed"
                                            and e["consumer"] == consumer], default=0) for consumer in CONSUMERS},
               "sinks": {sink: {"status": row["status"], "counters": row["counters"], "subpass": row["subpass"]}
                         for sink, row in final["sinks"].items()},
               "requests": {f"{e['phase']}_{e['group']}": e["request"] for e in run.events
                            if e["event"] == "scan_requested"},
               "session_known": prepared["session_known"], "transcripts": prepared["transcripts"],
               "loki": "not_covered:proxy_unverified", "claim": claim(run, result)}
    data = json.dumps(receipt, indent=2, sort_keys=True).encode("ascii")
    check_output(data, run.secrets())
    boot.write_receipt(directory, receipt, receipt_id)
    return receipt_id


def say(run, text: str) -> None:
    data = (text + "\n").encode("ascii")
    if run is not None and getattr(run, "id", None) and (run.base / run.id).is_dir():
        check_output(data, run.secrets())
    os.write(1, data)


def status(args, env) -> int:
    run = open_run(args, env)
    return report(run, integrity(run) if run.valid else [])


def verdict(args, env) -> int:
    run = open_run(args, env)
    return report(run, integrity(run) if run.valid else [], receipt=True)


def cleanup(args, env) -> int:
    run = open_run(args, env)
    if run.valid:
        state = arm_state(run.events)
        if state["armed"] or state["pending"]:
            disarm(args, env, run)
        fd, _root = store_root(env)
        try:
            absent = _stat(fd) is None
        finally:
            os.close(fd)
        codes = integrity(run)
        result = classify(run.events, codes, expected_markers(run))
        run.append("cleaned", receipt=f"{run.id}-{len(run.events) + 1:06d}", absent_verified=absent)
        result = classify(run.events, codes, expected_markers(run))
        publish(run, result)
        code = EXIT[result["verdict"]]
    else:
        code = EXIT["invalid"]
    import shutil
    shutil.rmtree(run.dir)
    say(None, f"cleaned: {run.id}")
    return code


def parser() -> argparse.ArgumentParser:
    # allow_abbrev=False: the user-run triggers are exactly --user-run, --phase comparison and --phase=comparison (C2).
    top = argparse.ArgumentParser(prog="canary_proof.py", description=__doc__.split("\n\n", 1)[0], allow_abbrev=False)
    commands = top.add_subparsers(dest="command", required=True)
    one = commands.add_parser("prepare", allow_abbrev=False)
    one.add_argument("--codex-home")
    one.add_argument("--transcripts", choices=("confirmed", "exclude"), default="exclude")
    one.add_argument("--session")
    two = commands.add_parser("scan", allow_abbrev=False)
    two.add_argument("--run", required=True)
    two.add_argument("--phase", required=True, choices=("baseline", "final", "comparison"))
    two.add_argument("--user-run", action="store_true")
    three = commands.add_parser("arm", allow_abbrev=False)
    three.add_argument("--run", required=True)
    three.add_argument("consumer", choices=CONSUMERS)
    three.add_argument("--codex-home")
    for name in ("disarm", "status", "verdict", "cleanup"):
        commands.add_parser(name, allow_abbrev=False).add_argument("--run", required=True)
    return top


COMMANDS = {"prepare": prepare, "scan": scan, "arm": arm, "disarm": disarm, "status": status, "verdict": verdict,
            "cleanup": cleanup}


def main(argv: list) -> int:
    args = parser().parse_args(argv)
    try:
        return COMMANDS[args.command](args, os.environ)
    except Busy:
        os.write(2, b"canary_proof: busy (another invocation holds the lock)\n")
        return EXIT["busy"]
    except (Refused, runner.Refused) as refusal:
        code = str(refusal) if isinstance(refusal, Refused) and re.fullmatch(r"[a-z_]+", str(refusal)) else "refused"
        os.write(2, f"canary_proof: refused ({code})\n".encode("ascii"))
        return EXIT["refused"]
    except Exception as error:  # noqa: BLE001 - a fixed class name only, never a message or a traceback
        os.write(2, f"canary_proof: failed ({type(error).__name__})\n".encode("ascii"))
        return EXIT["refused"]


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
