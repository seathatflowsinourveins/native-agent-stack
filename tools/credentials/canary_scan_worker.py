#!/usr/bin/env python3
"""The contained scan side of the canary proof: every read of sink bytes, names and diagnostics happens here.

    python3 -I -S tools/credentials/canary_scan_worker.py worker <plan-fd> <protocol-fd> <ack-fd>
    python3 -I -S tools/credentials/canary_scan_worker.py sqlite-dumper <control-fd>

Internal entry points. tools/credentials/canary_proof.py (the coordinator) starts `worker` inside
adoption/tools/ecosystem-bounded-run's systemd scope with stdout and stderr on /dev/null, hands it one plan frame on
<plan-fd> and reads fixed 128-byte CP03 records from <protocol-fd>; a HIT waits for its acknowledgement on <ack-fd>.
Every upstream child (rg, gzip, bzip2, xz, journalctl, git, systemctl, systemd-cat and the SQLite dumper) starts
through `setpriv --pdeathsig TERM`, leads its own session and gets only the descriptors it needs. What it prints is
parsed here and leaves only as enums, opaque keyed ids and counts: no path, name, header, stderr byte, schema text or
object id crosses to the coordinator (contract draft 3, section 10, amendments C7, C9, C12). Like ripgrep, this
process and the dumper hold sink bytes: they are pinned code on the scanner side of the boundary (C12).

Sources: BurntSushi/ripgrep@14.1.0 (e50df40a) crates/core/flags/defs.rs and main.rs, the argv and --stats grammar
(15.2.0, e89fff89, ends its stats with "seconds total"); git v2.43.0 Documentation/git-cat-file.txt (--batch framing),
git-verify-pack.txt, git-fsck.txt and gitrepository-layout.txt; systemd v255 docs/JOURNAL_EXPORT_FORMATS.md; SQLite
uri.html, fileformat2.html (header bytes 18-19) and wal.html (read-only WAL databases); credential_run.py Command and
end_group (the pinned-unreaped-leader group ending), reused unchanged.
"""
from __future__ import annotations

import os
import sys

if __name__ == "__main__" and not (sys.flags.isolated and sys.flags.no_site):
    os.execv(sys.executable, [sys.executable, "-I", "-S", os.path.abspath(__file__), *sys.argv[1:]])

import codecs  # noqa: E402
import collections  # noqa: E402
import ctypes  # noqa: E402
import fnmatch  # noqa: E402
import hashlib  # noqa: E402
import hmac  # noqa: E402
import json  # noqa: E402
import re  # noqa: E402
import resource  # noqa: E402
import select  # noqa: E402
import selectors  # noqa: E402
import signal  # noqa: E402
import stat  # noqa: E402
import struct  # noqa: E402
import subprocess  # noqa: E402
import time  # noqa: E402
import urllib.parse  # noqa: E402
from pathlib import Path  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
for _directory in (ROOT / "tools" / "credentials", ROOT / "scripts"):
    if str(_directory) not in sys.path:
        sys.path.insert(0, str(_directory))
import credential_run as runner  # noqa: E402  (Command, end_group)
import credential_status as cs  # noqa: E402  (guard_matches_pin, git_worktree_of: run here, never in the coordinator)

# ---- CP03 (contract 10.2). C7 adds kind 9 COUNTER, class 8 anchor and path classes 14-16 (the coordinator's own
# session). The coordinator imports these definitions: one shared schema.
FIELDS = ("magic 4s", "version B", "kind B", "r0 H", "nonce 16s", "seq Q", "check Q", "sink H", "mode B", "view B",
          "klass B", "path B", "status B", "reason B", "consumer B", "r1 7s", "attempt I", "subpass I", "observed Q",
          "expected Q", "exit i", "r2 I", "object 16s", "seal 16s", "aux Q")
NAMES = tuple(field.split()[0] for field in FIELDS)
RECORD = struct.Struct("!" + "".join(field.split()[1] for field in FIELDS))
Record = collections.namedtuple("Record", NAMES)
MAGIC, VERSION = b"CP03", 1
BEGIN, INVENTORY, HIT, RESULT, CONTROL, FACT, END, OBSERVATION, COUNTER = range(1, 10)
# Coordinator to worker (C7). PLAN: b"CPPL", version 1, kind 1, 0, 16-byte nonce, body length, sha256(body), 0, then
# the body: canonical JSON (sorted keys, ASCII, paths as surrogate-escaped strings). ACK: b"CPAK", 1, 1, 0, nonce,
# the sequence number of the HIT acknowledged.
PLAN = struct.Struct("!4sBBH16sI32sI")
ACK = struct.Struct("!4sBBH16sQ")
PLAN_MAX = 1 << 22
SINKS = {"A1": 1, "A2": 2, "A3": 3, "A4": 4, "A9": 9, "A10": 10, "A11": 11, "A12": 12,
         **{f"U{number}": 100 + number for number in range(1, 9)}}
MODES = {"setup": 0, "M1": 1, "M2": 2, "M3": 3, "M4": 4, "M5": 5, "M6": 6, "U4": 7}
VIEWS = {"none": 0, "raw": 1, "bom": 2, "decoded_raw": 3, "decoded_bom": 4, "logical": 5, "name": 6, "metadata": 7}
CLASSES = {"none": 0, "canary": 1, "tag": 2, "full_marker": 3, "partial_marker": 4, "control": 5, "object_header": 6,
           "negative": 7, "anchor": 8}
PATHS = {name: code for code, name in enumerate(
    "none claude_main claude_subagent claude_workflow claude_other codex_rollout codex_other sqlite wal journal "
    "git_object git_metadata name other own_main own_subagent own_workflow".split())}
STATUS = {"planned": 0, "complete": 1, "incomplete": 2, "absent": 3, "not_covered": 4}
REASONS = ("ok walk_error open_error changed_type root_symlink vanished link_out uncovered_format output_cap "
           "unparseable_output files_searched_mismatch matches_mismatch scanner_exit scanner_stderr producer_exit "
           "producer_stderr object_count_mismatch union_changed deadline interrupted containment_unavailable "
           "file_set_changed format_changed quiescence_unverifiable git_unaccounted_payload git_alternate_unplanned "
           "git_validation_failed bom_invalid sqlite_uri_identity sqlite_schema_error sqlite_table_error "
           "control_missing negative_control_matched protocol_error setup_failed pointer_changed "
           "pointer_target_not_file journal_cursor_missing absent_since_prepare declared_exclusion "
           "unsupported_platform unreviewed_scanner tool_changed pattern_file_mismatch user_scope_declined "
           "nested_format unknown_format git_indirection_unplanned git_promisor_unsupported "
           "sqlite_readonly_failed").split()
R = {name: code for code, name in enumerate(REASONS)}
CONSUMERS = ("systemd-user-unit", "fresh-claude-session", "subagent", "workflow-child", "codex-exec", "omniroute-lane")
FACTS = {"root_presence": 1, "executable_version": 2, "executable_fingerprint": 3, "pointer_binding": 4,
         "journal_binding": 5, "git_inventory": 6, "root_registration": 7, "baseline_policy": 8, "checkout": 9,
         "guard_pin": 10, "store_outside_worktree": 11, "scope_binding": 12}
COUNTERS = {name: code for code, name in enumerate(
    ("selected unselected special excluded_key excluded_user declined declared_link dangling_link covered_link "
     "excluded_link directories git_stores").split(), 1)}
FORMATS = {"sqlite": 1, "gzip": 2, "bzip2": 3, "xz": 4, "lzma": 5, "zstd": 6, "lz4": 7, "compress": 8, "lzip": 9,
           "lzop": 10, "snappy": 11, "brotli": 12, "container": 13, "other": 14}
# One version-code formula for every executable (C13): major * 1,000,000 + minor * 1,000 + patch.
VERSION_TEXT = {"rg": r"ripgrep (\d+)\.(\d+)\.(\d+)", "git": r"git version (\d+)\.(\d+)\.(\d+)",
                "gzip": r"gzip (\d+)\.(\d+)", "bzip2": r"Version (\d+)\.(\d+)\.(\d+)",
                "xz": r"xz \(XZ Utils\) (\d+)\.(\d+)\.(\d+)", "journalctl": r"systemd (\d+)",
                "systemctl": r"systemd (\d+)", "systemd-cat": r"systemd (\d+)",
                "setpriv": r"util-linux (\d+)\.(\d+)(?:\.(\d+))?", "ionice": r"util-linux (\d+)\.(\d+)(?:\.(\d+))?",
                "nice": r"coreutils\) (\d+)\.(\d+)", "python3": r"Python (\d+)\.(\d+)\.(\d+)"}
REVIEWED_RG = {14001000: b"seconds", 15002000: b"seconds total"}  # version code -> the last --stats line's words
CURSOR = re.compile(rb"s=[0-9a-f]{32};i=[0-9a-f]{1,16};b=[0-9a-f]{32};m=[0-9a-f]{1,16};t=[0-9a-f]{1,16};x=[0-9a-f]{1,16}")
OID = re.compile(rb"[0-9a-f]{40}(?:[0-9a-f]{24})?")
PACK_FILE = re.compile(rb"pack-([0-9a-f]{40}(?:[0-9a-f]{24})?)\.(pack|idx|keep|rev|bitmap|mtimes|promisor)")
OPEN_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_NOCTTY | os.O_CLOEXEC
DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
BUDGET_CAP = float("inf")  # a test launcher's short deadline (contract 13.5); production uses the formulas only
STDOUT_CAP = 64 << 20
DECODED_CAP = 16 << 30
BACKLOG = 1 << 20
SNIFF = 512
ACK_SECONDS = 120.0
FS_CHANGED_OK = {0xEF53, 0x58465342, 0x9123683E}                            # ext2/3/4, xfs, btrfs
FS_UNVERIFIABLE = {0x01021997, 0x65735546, 0x6969, 0xFF534D42, 0xFE534D42}  # 9p, FUSE, NFS, CIFS, SMB2
DUMPER_EXITS = {10: "sqlite_uri_identity", 11: "sqlite_schema_error", 12: "sqlite_table_error",
                13: "sqlite_readonly_failed"}
HOOKS: dict = {}  # a test launcher's module hooks (contract 9.5); there is no environment switch


def budget(base: float, size: int = 0, rate: float = 1.0, cap: float = 1800.0) -> float:
    return min(cap, base + size / rate, BUDGET_CAP)


def hook(name: str, *args) -> None:
    function = HOOKS.get(name)
    if function is not None:
        function(*args)


def pack(**fields) -> bytes:
    values = dict.fromkeys(NAMES, 0)
    values.update(magic=MAGIC, version=VERSION, nonce=bytes(16), r1=bytes(7), object=bytes(16), seal=bytes(16))
    values.update(fields)
    return RECORD.pack(*(values[name] for name in NAMES))


def unpack(data: bytes) -> Record:
    return Record(*RECORD.unpack(data))


def keyed(key: bytes, *parts) -> bytes:
    """The first 16 bytes of HMAC-SHA256(run key, length-prefixed parts): the only binary ids the scan side sends."""
    mac = hmac.new(key, digestmod=hashlib.sha256)
    for part in parts:
        data = part if isinstance(part, bytes) else str(part).encode("utf-8", "surrogateescape")
        mac.update(struct.pack("!I", len(data)) + data)
    return mac.digest()[:16]


def version_code(name: str, text: str) -> int:
    match = re.search(VERSION_TEXT.get(name, r"(\d+)\.(\d+)(?:\.(\d+))?"), text)
    if not match:
        return 0
    parts = [int(part or 0) for part in match.groups()] + [0, 0]
    return parts[0] * 1_000_000 + parts[1] * 1_000 + parts[2]


def sha256_file(path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def tuple_of(info) -> tuple:
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def under(path: bytes, prefix: bytes) -> bool:
    return path == prefix or path.startswith(prefix.rstrip(b"/") + b"/")


class Stop(Exception):
    """A fixed reason code ends the current operation; it never carries text."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class Deadline(Exception):
    pass


class Interrupted(Exception):
    pass


def _interrupt(_signum, _frame) -> None:
    raise Interrupted()


# ---- Children -------------------------------------------------------------------------------------------------------
LIVE: set = set()


class Child:
    """One upstream executable: setpriv --pdeathsig TERM, its own session and group, only the descriptors given."""

    def __init__(self, scan, argv: list, stdin, stdout, stderr, pass_fds=(), cwd=None):
        hook("before_child", argv[0])
        signal.signal(signal.SIGCHLD, signal.SIG_DFL)  # Same pinned-leader prerequisite as credential_run.run_command.
        self.process = subprocess.Popen([scan.setpriv, "--pdeathsig", "TERM", "--", *argv], stdin=stdin, stdout=stdout,
                                        stderr=stderr, pass_fds=pass_fds, close_fds=True, start_new_session=True,
                                        cwd=cwd, env=scan.child_env)
        self.command = runner.Command(self.process)
        LIVE.add(self)

    def finish(self, deadline: float):
        """Wait for the exit until deadline, end what is left of the group, reap: the signed status, None on timeout."""
        while not self.command.exited() and time.monotonic() < deadline:
            time.sleep(0.02)
        exited = self.command.exited()
        runner.end_group(self.command)
        code = self.command.reap(None if exited else runner.KILL_WAIT_SECONDS)
        LIVE.discard(self)
        return code if exited else None

    def stop(self) -> None:
        runner.end_group(self.command)
        self.command.reap(runner.KILL_WAIT_SECONDS)
        LIVE.discard(self)


def stop_all() -> None:
    for child in list(LIVE):
        try:
            child.stop()
        except Exception:  # noqa: BLE001 - every way out ends every child
            LIVE.discard(child)


def spawn(scan, argv: list, stdin=subprocess.DEVNULL, piped_stdin: bool = False, pass_fds=(), cwd=None) -> tuple:
    """(child, stdin write end or None, stdout read end, stderr read end); the worker owns every pipe end it gets."""
    ends = [os.pipe(), os.pipe()] + ([os.pipe()] if piped_stdin else [])
    try:
        child = Child(scan, argv, ends[2][0] if piped_stdin else stdin, ends[0][1], ends[1][1], pass_fds, cwd)
    except BaseException:
        for read_end, write_end in ends:
            os.close(read_end)
            os.close(write_end)
        raise
    os.close(ends[0][1])
    os.close(ends[1][1])
    if piped_stdin:
        os.close(ends[2][0])
    return child, ends[2][1] if piped_stdin else None, ends[0][0], ends[1][0]


class Flow:
    """Pipes between producers and scanners, driven from the main thread until EOF everywhere or the deadline."""

    def __init__(self, deadline: float):
        self.selector, self.deadline = selectors.DefaultSelector(), deadline
        self.readers, self.pending, self.closing, self.throttled = {}, {}, set(), set()

    def read(self, fd: int, function, throttle: bool = False) -> None:
        os.set_blocking(fd, False)
        self.readers[fd] = function
        if throttle:
            self.throttled.add(fd)
        self.selector.register(fd, selectors.EVENT_READ)

    def write(self, fd: int, data: bytes = b"") -> None:
        os.set_blocking(fd, False)
        self.pending[fd] = bytearray(data)

    def send(self, fd: int, data: bytes) -> None:
        if fd in self.pending:
            self.pending[fd] += data

    def close(self, fd: int) -> None:
        if fd in self.pending:
            self.closing.add(fd)

    def _drop(self, fd: int) -> None:
        self.readers.pop(fd, None)
        self.throttled.discard(fd)
        if fd in self.selector.get_map():
            self.selector.unregister(fd)
        os.close(fd)

    def _flush(self, fd: int) -> None:
        buffer = self.pending[fd]
        try:
            while buffer:
                del buffer[:os.write(fd, buffer[:65536])]
        except BlockingIOError:
            return
        except OSError:  # the scanner is gone; its own exit status fails its check
            buffer.clear()
        if not buffer and fd in self.closing:
            if fd in self.selector.get_map():
                self.selector.unregister(fd)
            del self.pending[fd]
            self.closing.discard(fd)
            os.close(fd)

    def run(self) -> None:
        while self.readers or self.pending:
            for fd in list(self.pending):
                self._flush(fd)
            backlog = max((len(buffer) for buffer in self.pending.values()), default=0)
            registered = self.selector.get_map()
            for fd in self.throttled:
                if backlog > BACKLOG and fd in registered:
                    self.selector.unregister(fd)
                elif backlog <= BACKLOG and fd not in registered:
                    self.selector.register(fd, selectors.EVENT_READ)
            for fd, buffer in self.pending.items():
                if buffer and fd not in self.selector.get_map():
                    self.selector.register(fd, selectors.EVENT_WRITE)
                elif not buffer and fd in self.selector.get_map():
                    self.selector.unregister(fd)
            if not self.readers and not any(self.pending.values()):
                for fd in list(self.pending):
                    if fd not in self.closing:
                        self.close(fd)
                    self._flush(fd)
                continue
            remaining = self.deadline - time.monotonic()
            if remaining <= 0:
                raise Deadline()
            for key, events in self.selector.select(min(remaining, 0.5)):
                if events & selectors.EVENT_WRITE and key.fd in self.pending:
                    self._flush(key.fd)
                if events & selectors.EVENT_READ and key.fd in self.readers:
                    try:
                        data = os.read(key.fd, 65536)
                    except BlockingIOError:
                        continue
                    self.readers[key.fd](data)
                    if not data:
                        self._drop(key.fd)
        self.selector.close()

    def abandon(self) -> None:
        for fd in list(self.readers):
            self._drop(fd)
        for fd in list(self.pending):
            os.close(fd)
        self.pending.clear()
        self.selector.close()


# ---- Wire -----------------------------------------------------------------------------------------------------------
class Wire:
    def __init__(self, proto: int, ack: int, nonce: bytes):
        self.proto, self.ack, self.nonce, self.seq = proto, ack, nonce, 0

    def emit(self, kind: int, **fields) -> int:
        if kind == END:
            signal.pthread_sigmask(signal.SIG_BLOCK, (signal.SIGINT, signal.SIGTERM, signal.SIGHUP, signal.SIGQUIT))
        self.seq += 1
        view = memoryview(pack(kind=kind, nonce=self.nonce, seq=self.seq, **fields))
        while view:
            view = view[os.write(self.proto, view):]
        return self.seq

    def hit(self, **fields) -> None:
        """A HIT, then nothing more until the coordinator acknowledges it after fsyncing its event (contract 5)."""
        sequence = self.emit(HIT, klass=CLASSES["canary"], **fields)
        data, deadline = b"", time.monotonic() + ACK_SECONDS
        while len(data) < ACK.size:
            if not select.select([self.ack], [], [], max(0.0, deadline - time.monotonic()))[0]:
                raise Stop("protocol_error")
            chunk = os.read(self.ack, ACK.size - len(data))
            if not chunk:
                raise Stop("protocol_error")
            data += chunk
        if ACK.unpack(data) != (b"CPAK", 1, 1, 0, self.nonce, sequence):
            raise Stop("protocol_error")


def read_exact(fd: int, size: int) -> bytes:
    data = b""
    while len(data) < size:
        chunk = os.read(fd, size - len(data))
        if not chunk:
            raise Stop("protocol_error")
        data += chunk
    return data


def read_plan(fd: int) -> tuple:
    magic, version, kind, reserved, nonce, length, digest, tail = PLAN.unpack(read_exact(fd, PLAN.size))
    if (magic, version, kind, reserved, tail) != (b"CPPL", 1, 1, 0, 0) or length > PLAN_MAX:
        raise Stop("protocol_error")
    body = read_exact(fd, length)
    if hashlib.sha256(body).digest() != digest:
        raise Stop("protocol_error")
    return nonce, body, json.loads(body.decode("ascii"))


def verify_scope() -> None:
    """Inside the runner's ecosystem-job scope, whose memory, pids and cpu limits are finite, or refuse (contract 11)."""
    with open("/proc/self/cgroup", "rb") as handle:
        lines = [line for line in handle.read().splitlines() if line.startswith(b"0::/")]
    group = lines[0][3:] if len(lines) == 1 else b""
    if not re.fullmatch(rb"/[\w@.:/-]*/ecosystem-job-\d+-\d+-\d+\.scope", group):
        raise Stop("containment_unavailable")
    for name in (b"memory.max", b"pids.max", b"cpu.max"):
        with open(b"/sys/fs/cgroup" + group + b"/" + name, "rb") as handle:
            if handle.read().split()[:1] in ([], [b"max"]):
                raise Stop("containment_unavailable")
    return os.getpid(), int(group.rsplit(b"-", 1)[1].split(b".", 1)[0])


def fs_magic(fd: int):
    """statfs f_type of an open descriptor, or None."""
    try:
        buffer = ctypes.create_string_buffer(256)
        if ctypes.CDLL(None, use_errno=True).fstatfs(fd, buffer) != 0:
            return None
        return struct.unpack_from("l", buffer.raw)[0] & 0xFFFFFFFF
    except (OSError, AttributeError):
        return None


# ---- Patterns -------------------------------------------------------------------------------------------------------
class Patterns:
    """The request's union file and its many-to-many classes; re-hashed before every scanner starts (contract 5)."""

    def __init__(self, path: str, digest: str, classes: list):
        self.path, self.digest = path, digest
        lines = self.read().split(b"\n")
        if lines[-1] != b"" or any(len(line) < 6 or not line.isascii() for line in lines[:-1]):
            raise Stop("pattern_file_mismatch")
        self.classes, self.by_id = collections.defaultdict(list), {}
        for number, klass, consumer, attempt, ident in classes:
            ident = bytes.fromhex(ident) if ident else bytes(16)
            self.classes[lines[number]].append((klass, consumer, attempt, ident))
            if any(ident):
                self.by_id[ident] = lines[number]
        self.index = collections.defaultdict(list)
        for pattern in self.classes:
            self.index[pattern[:6]].append(pattern)
        self.longest = max((len(pattern) for pattern in self.classes), default=6)

    def read(self) -> bytes:
        fd = os.open(self.path, OPEN_FLAGS)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600 or info.st_uid != os.getuid():
                raise Stop("pattern_file_mismatch")
            data = b"".join(iter(lambda: os.read(fd, 1 << 20), b""))
        finally:
            os.close(fd)
        if hashlib.sha256(data).hexdigest() != self.digest:
            raise Stop("union_changed")
        return data

    def find(self, data: bytes, first_end: int = 0) -> list:
        """Every pattern that occurs in data ending at index first_end or later (M6 byte substring matching)."""
        found = []
        for start in range(max(0, first_end - self.longest + 1), len(data) - 5):
            for pattern in self.index.get(data[start:start + 6], ()):
                if data.startswith(pattern, start) and start + len(pattern) - 1 >= first_end:
                    found.append(pattern)
        return found


# ---- Routing (contract 9.4) -----------------------------------------------------------------------------------------
DECODED = ((b"\x1f\x8b", "gzip"), (b"BZh", "bzip2"), (b"\xfd7zXZ\x00", "xz"))
UNCOVERED = ((b"\x28\xb5\x2f\xfd", "zstd"), (b"\x04\x22\x4d\x18", "lz4"), (b"\x02\x21\x4c\x18", "lz4"),
             (b"\x1f\x9d", "compress"), (b"LZIP", "lzip"), (b"\x89LZO", "lzop"), (b"\xff\x06\x00\x00sNaPpY", "snappy"))
# Container magics and offsets (C13): zip (local, empty, spanned), 7z, RAR, PDF, POSIX tar at 257, cpio (newc, crc,
# odc), ar, Microsoft cabinet, xar, and a Git pack outside a reconciled store.
CONTAINERS = ((0, b"PK\x03\x04"), (0, b"PK\x05\x06"), (0, b"PK\x07\x08"), (0, b"7z\xbc\xaf\x27\x1c"),
              (0, b"Rar!\x1a\x07"), (0, b"%PDF-"), (257, b"ustar"), (0, b"070701"), (0, b"070702"), (0, b"070707"),
              (0, b"!<arch>\n"), (0, b"MSCF"), (0, b"xar!"), (0, b"PACK"))
UNCOVERED_NAMES = ((b".zst", "zstd"), (b".zstd", "zstd"), (b".lz4", "lz4"), (b".br", "brotli"), (b".Z", "compress"),
                   (b".lz", "lzip"), (b".lzo", "lzop"), (b".sz", "snappy"))
NAMED = ((b".gz", "gzip"), (b".tgz", "gzip"), (b".bz2", "bzip2"), (b".tbz2", "bzip2"), (b".tbz", "bzip2"),
         (b".xz", "xz"), (b".txz", "xz"))


def route(head: bytes, name: bytes, git_pack: bool = False) -> tuple:
    """(kind, format): sqlite, wal, decode, uncovered, container, unknown (46: a compression name that its bytes do
    not match) or plain. A BOM is an additive view (bom_of); raw M1 is never replaced."""
    if head.startswith(b"SQLite format 3\x00"):
        return "sqlite", "sqlite"
    if head[:4] in (b"\x37\x7f\x06\x82", b"\x37\x7f\x06\x83"):
        return "wal", "sqlite"
    for magic, fmt in DECODED:
        if head.startswith(magic):
            return "decode", fmt
    for magic, fmt in UNCOVERED:
        if head.startswith(magic):
            return "uncovered", fmt
    if len(head) >= 4 and 0x50 <= head[0] <= 0x5F and head[1:4] == b"\x2a\x4d\x18":
        return "uncovered", "zstd"
    for offset, magic in CONTAINERS:
        if head[offset:offset + len(magic)] == magic and not (git_pack and magic == b"PACK"):
            return "container", "container"
    for suffix, fmt in UNCOVERED_NAMES:
        if name.endswith(suffix):
            return "uncovered", fmt
    if name.endswith((b".lzma", b".tlz")):
        return "decode", "lzma"
    for suffix, fmt in NAMED:
        if name.endswith(suffix):
            return "unknown", fmt
    return "plain", None


def classify(head: bytes, name: bytes, store) -> tuple:
    """route() for a file at its place: a pack that a reconciled store names is its payload; any other `PACK` inside a
    store is an unaccounted payload, never demoted to metadata (contract 10.7)."""
    kind, fmt = route(head, name, store is not None and PACK_FILE.fullmatch(name) is not None)
    if store is not None and kind == "container" and head.startswith(b"PACK"):
        return "unaccounted", "container"
    return kind, fmt


def bom_of(head: bytes):
    return {b"\xff\xfe": "utf-16-le", b"\xfe\xff": "utf-16-be"}.get(head[:2])


def strict_utf16(fd: int, encoding: str, size: int) -> bool:
    decoder = codecs.getincrementaldecoder(encoding)("strict")
    try:
        for offset in range(2, max(size, 2), 1 << 20):
            decoder.decode(os.pread(fd, 1 << 20, offset))
        decoder.decode(b"", final=True)
    except UnicodeDecodeError:
        return False
    return True


# ---- Checks and the scanner -------------------------------------------------------------------------------------------
class Check:
    def __init__(self, ident: int, mode: str, view: str, path: str, obj: bytes, root: int):
        self.id, self.mode, self.view, self.path, self.object, self.root = ident, mode, view, path, obj, root
        self.reason, self.exit, self.stderr, self.observed = "ok", 0, 0, 0
        self.matches = 0
        self.counts = collections.Counter()  # (klass, consumer, attempt, id) -> occurrences of non-canary patterns

    def fail(self, reason: str) -> None:
        if self.reason == "ok":
            self.reason = reason


class RgOutput:
    """rg's stdout: `label NUL pattern LF` records, a blank line, then the pinned --stats block (contract 10.3)."""

    def __init__(self, scan, check: Check, labels: dict):
        self.scan, self.check, self.labels = scan, check, labels
        self.buffer, self.total, self.records, self.stats, self.searched = bytearray(), 0, 0, None, 0
        self.per_control = collections.Counter()

    def feed(self, data: bytes) -> None:
        """Complete records are attributed before the cap is enforced: a canary record that arrived is never lost."""
        self.total += len(data)
        self.buffer += data
        while (end := self.buffer.find(b"\n")) >= 0:
            line = bytes(self.buffer[:end])
            del self.buffer[:end + 1]
            if self.stats is not None:
                self.stats.append(line)
            elif line == b"":
                self.stats = []
            else:
                self.record(line)
        if self.total > STDOUT_CAP:
            raise Stop("output_cap")

    def record(self, line: bytes) -> None:
        label, separator, pattern = line.partition(b"\0")
        if not separator or label not in self.labels or pattern not in self.scan.patterns.classes:
            self.check.fail("unparseable_output")
            return
        self.records += 1
        if self.labels[label] is None:
            self.scan.attribute(self.check, pattern)
        else:
            self.per_control[(label, pattern)] += 1

    def close(self, files: int) -> None:
        stats = self.stats or []
        words = [b"matches", b"matched lines", b"files contained matches", b"files searched", b"bytes printed",
                 b"bytes searched", b"seconds spent searching", REVIEWED_RG.get(self.scan.plan["rg_version"], b"-")]
        values = [re.fullmatch(rb"(\d+(?:\.\d+)?) " + re.escape(word), line) for line, word in zip(stats, words)]
        if self.buffer or len(stats) != len(words) or None in values:
            self.check.fail("unparseable_output")
            return
        self.searched = int(values[3].group(1))
        if int(values[0].group(1)) != self.records:
            self.check.fail("matches_mismatch")
        if self.searched != files:
            self.check.fail("files_searched_mismatch")
        for label, control in self.labels.items():
            if control is None:
                continue
            ident, expected, negative = control
            pattern = self.scan.patterns.by_id.get(ident)
            found = sum(count for (seen, p), count in self.per_control.items() if seen == label and p == pattern)
            stray = sum(count for (seen, p), count in self.per_control.items() if seen == label and p != pattern)
            self.scan.control(self.check, ident, stray if negative else found, 0 if negative else expected,
                              "negative" if negative else "control")
            if stray and not negative:
                self.check.fail("negative_control_matched")


class Relay:
    """A producer's stdout into one raw scanner, after its in-band control and a line feed (M3, M4, M5, U4)."""

    def __init__(self, check: Check, inband: str, expect=None):
        self.check, self.inband, self.expect, self.total = check, inband, expect, 0

    def start(self, scan, flow: Flow, started: list) -> None:
        self.scan, self.flow, self.started = scan, flow, started
        self.ident, control = scan.inband(self.inband)
        self.child, self.fd, self.parser = scan.scanner(self.check, "none", None, [], flow)
        started.append((self.check, self.child, self.parser))
        self.flow.send(self.fd, control + b"\n")

    def data(self, data: bytes) -> None:
        self.total += len(data)
        if self.total > self.scan.plan["decoded_cap"]:
            raise Stop("output_cap")
        self.transform(data)

    def transform(self, data: bytes) -> None:
        if data:
            self.flow.send(self.fd, data)
        else:
            self.flow.close(self.fd)

    def finish(self) -> None:
        self.scan.control(self.check, self.ident, self.check.counts.pop((CLASSES["control"], 0, 0, self.ident), 0), 1)
        self.check.observed = self.parser.searched
        if self.expect is not None:
            for ident, expected in self.expect.items():
                self.scan.control(self.check, ident, self.check.counts.pop((CLASSES["control"], 0, 0, ident), 0),
                                  expected)


class Decoded(Relay):
    """M2 (contract 10.5): sniff the decoded head before any control goes in. The raw view gets the ASCII control, a
    line feed and every decoded byte; after a decoded BOM a BOM-aware view gets the BOM, the control encoded in the
    same UTF-16 and the bytes after the BOM, from the same single decoder stream, with strict validation."""

    def __init__(self, check: Check, expect=None):
        super().__init__(check, "m2raw", None)
        self.head, self.encoding, self.skip, self.control_expect = bytearray(), None, 2, expect

    def transform(self, data: bytes) -> None:
        if self.head is not None:
            self.head += data
            if data and len(self.head) < SNIFF:
                return
            head, self.head = bytes(self.head), None
            if route(head, b"")[0] != "plain":
                raise Stop("nested_format")
            self.encoding = bom_of(head)
            if self.encoding:
                self.bom_check = self.scan.declare("M2", "decoded_bom", self.check.object, self.check.path, 1,
                                                   root=self.check.root)
                self.bom_ident, control = self.scan.inband("m2bom")
                child, self.bom_fd, self.bom_parser = self.scan.scanner(self.bom_check, "auto", None, [], self.flow)
                self.started.append((self.bom_check, child, self.bom_parser))
                self.flow.send(self.bom_fd, head[:2] + (control + b"\n").decode("ascii").encode(self.encoding))
                self.decoder = codecs.getincrementaldecoder(self.encoding)("strict")
            if head:
                self.forward(head)
            if data:
                return
        elif data:
            return self.forward(data)
        if self.encoding:
            try:
                self.decoder.decode(b"", final=True)
            except UnicodeDecodeError:
                self.bom_check.fail("bom_invalid")
            self.flow.close(self.bom_fd)
        self.flow.close(self.fd)

    def forward(self, data: bytes) -> None:
        self.flow.send(self.fd, data)
        if self.encoding:
            body, self.skip = data[self.skip:], max(0, self.skip - len(data))
            try:
                self.decoder.decode(body)
            except UnicodeDecodeError:
                self.bom_check.fail("bom_invalid")
            self.flow.send(self.bom_fd, body)

    def finish(self) -> None:
        super().finish()
        views = {"raw": self.check}
        if self.encoding:
            ident = self.bom_ident
            self.scan.control(self.bom_check, ident, self.bom_check.counts.pop((CLASSES["control"], 0, 0, ident), 0), 1)
            self.bom_check.observed = self.bom_parser.searched
            views["bom"] = self.bom_check
        if self.control_expect is not None:
            ident, view, expected = self.control_expect
            target = views.get(view)
            found = (sum(max(0, check.matches - 1) for check in views.values()) if view == "negative" else
                     target.counts.pop((CLASSES["control"], 0, 0, ident), 0) if target else 0)
            self.scan.control(target or self.check, ident, found, expected,
                              "negative" if view == "negative" else "control")
        if self.encoding:
            self.scan.result(self.bom_check, self.bom_check.observed, 1)


class ExportParser:
    """Incremental systemd v255 export framing; a final field LF does not terminate its entry."""

    def __init__(self, entry):
        self.entry, self.buffer, self.fields, self.binary = entry, bytearray(), {}, None

    def feed(self, data: bytes, final: bool = False) -> None:
        self.buffer += data
        while self.parse():
            pass
        if len(self.buffer) > STDOUT_CAP or final and (self.buffer or self.binary or self.fields):
            raise Stop("unparseable_output")

    def parse(self) -> bool:
        if self.binary is not None:
            name, size = self.binary
            if len(self.buffer) < size + 1:
                return False
            if self.buffer[size] != 10:
                raise Stop("unparseable_output")
            self.fields[name] = bytes(self.buffer[:size])
            del self.buffer[:size + 1]
            self.binary = None
            return True
        end = self.buffer.find(b"\n")
        if end < 0:
            return False
        line = bytes(self.buffer[:end])
        if not line:
            del self.buffer[:1]
            if not self.fields:
                raise Stop("unparseable_output")
            self.entry(self.fields)
            self.fields = {}
            return True
        name, separator, value = line.partition(b"=")
        if not re.fullmatch(rb"[A-Z0-9_]+", name):
            raise Stop("unparseable_output")
        if separator:
            self.fields[name] = value
            del self.buffer[:end + 1]
        else:
            if len(self.buffer) < end + 9:
                return False
            size = struct.unpack_from("<Q", self.buffer, end + 1)[0]
            if size > STDOUT_CAP:
                raise Stop("output_cap")
            self.binary = name, size
            del self.buffer[:end + 9]
        return True


class Journal(Relay):
    """M3: the export stream's framing parsed by declared lengths; its first entry's __CURSOR must be the bound one
    (contract 10.6), and the journal anchor must be in the stream."""

    def __init__(self, check: Check, cursor: bytes, anchor: bytes):
        super().__init__(check, "m3")
        self.cursor, self.anchor, self.entries = cursor, anchor, 0
        self.export_parser = ExportParser(self.entry)

    def transform(self, data: bytes) -> None:
        self.export_parser.feed(data, final=not data)
        super().transform(data)

    def entry(self, fields: dict) -> None:
        self.entries += 1
        if self.entries == 1 and fields.get(b"__CURSOR") != self.cursor:
            self.check.fail("journal_cursor_missing")

    def finish(self) -> None:
        super().finish()
        if self.entries == 0:
            self.check.fail("journal_cursor_missing")
        ident = self.anchor
        self.scan.control(self.check, ident, self.check.counts.pop((CLASSES["anchor"], 0, 0, ident), 0), 1, "anchor")


class GitStream(Relay):
    """M4: `cat-file --batch` framing parsed in the worker, every header checked against the enumeration; each body
    goes to rg behind the synthetic object marker (contract 10.7)."""

    def __init__(self, check: Check, objects: dict, expect: dict):
        super().__init__(check, "m4", expect)
        self.objects, self.seen, self.buffer, self.need, self.state = objects, set(), bytearray(), 0, "header"

    def start(self, scan, flow: Flow, started: list) -> None:
        super().start(scan, flow, started)
        self.marker = scan.patterns.by_id[bytes.fromhex(scan.plan["controls"]["objhdr"])]

    def transform(self, data: bytes) -> None:
        if not data:
            if self.state != "header" or self.buffer:
                self.check.fail("object_count_mismatch")
            return super().transform(b"")
        self.buffer += data
        while self.buffer:
            if self.state == "header":
                end = self.buffer.find(b"\n")
                if end < 0:
                    if len(self.buffer) > 256:
                        raise Stop("unparseable_output")
                    return
                parts = bytes(self.buffer[:end]).split(b" ")
                del self.buffer[:end + 1]
                if len(parts) != 3 or not OID.fullmatch(parts[0]) or not parts[2].isdigit() \
                        or self.objects.get(parts[0]) != (parts[1], int(parts[2])) or parts[0] in self.seen:
                    raise Stop("object_count_mismatch")
                self.seen.add(parts[0])
                self.need, self.state = int(parts[2]), "body"
                self.flow.send(self.fd, self.marker + b"\n")
            elif self.state == "body":
                take = min(self.need, len(self.buffer))
                self.flow.send(self.fd, bytes(self.buffer[:take]))
                del self.buffer[:take]
                self.need -= take
                if self.need == 0:
                    self.state = "delimiter"
            else:
                if self.buffer[0] != 0x0A:
                    raise Stop("object_count_mismatch")
                del self.buffer[:1]
                self.flow.send(self.fd, b"\n")
                self.state = "header"

    def finish(self) -> None:
        super().finish()
        markers = sum(count for key, count in self.check.counts.items() if key[0] == CLASSES["object_header"])
        if self.seen != set(self.objects) or markers != len(self.objects):  # parsed ids and scanner markers
            self.check.fail("object_count_mismatch")


# ---- The scan -------------------------------------------------------------------------------------------------------
class Scan:
    def __init__(self, plan: dict, wire: Wire, body: bytes):
        self.plan, self.wire, self.key = plan, wire, bytes.fromhex(plan["run_key"])
        self.seal = keyed(self.key, b"plan", body)
        self.sink, self.subpass = plan.get("sink", 0), plan.get("subpass", 0)
        self.setpriv, self.exes = plan["setpriv"], plan.get("exes", {})
        self.child_env = {name: value for name, value in os.environ.items()
                          if name in ("HOME", "XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS")}
        self.child_env.update(PATH=plan["child_path"], LC_ALL="C", GIT_CONFIG_NOSYSTEM="1", GIT_TERMINAL_PROMPT="0",
                              GIT_CONFIG_GLOBAL="/dev/null", GIT_NO_REPLACE_OBJECTS="1", GIT_OPTIONAL_LOCKS="0")
        self.checks, self.done, self.counters, self.reasons, self.used = {}, set(), collections.Counter(), [], set()
        self.patterns, self.inventory_seal, self.root = None, bytes(16), 0

    def exe(self, name: str) -> str:
        """The bound absolute executable; a changed file is tool_changed, never a silent substitute (B6)."""
        if not self.exes.get(name):
            raise Stop("uncovered_format")
        path, digest = self.exes[name]
        try:
            if sha256_file(path) != digest:
                raise Stop("tool_changed")
        except OSError:
            raise Stop("tool_changed") from None
        return path

    def declare(self, mode: str, view: str, obj: bytes, path: str = "other", expected: int = 0, size: int = 0,
                root: int = None) -> Check:
        check = Check(len(self.checks) + 1, mode, view, path, obj, self.root if root is None else root)
        self.checks[check.id] = check
        self.wire.emit(INVENTORY, check=check.id, sink=self.sink, mode=MODES[mode], view=VIEWS[view], path=PATHS[path],
                       subpass=self.subpass, expected=expected, object=obj, seal=self.inventory_seal, aux=size)
        return check

    def result(self, check: Check, observed: int = 0, expected: int = 0) -> None:
        for (klass, consumer, attempt, _ident), count in sorted(check.counts.items()):
            if klass in (CLASSES["tag"], CLASSES["full_marker"], CLASSES["partial_marker"], CLASSES["object_header"]):
                self.wire.emit(OBSERVATION, check=check.id, sink=self.sink, mode=MODES[check.mode],
                               view=VIEWS[check.view], klass=klass, path=PATHS[check.path], subpass=self.subpass,
                               consumer=consumer if klass == CLASSES["tag"] else 0,
                               attempt=attempt if klass == CLASSES["tag"] else 0, observed=count, object=check.object)
        status = {"absent_since_prepare": "absent", "declared_exclusion": "not_covered",
                  "user_scope_declined": "not_covered"}.get(check.reason, "complete" if check.reason == "ok"
                                                                          else "incomplete")
        if status == "incomplete":
            self.reasons.append(check.reason)
        self.wire.emit(RESULT, check=check.id, sink=self.sink, mode=MODES[check.mode], view=VIEWS[check.view],
                       path=PATHS[check.path], status=STATUS[status], reason=R[check.reason], subpass=self.subpass,
                       observed=observed, expected=expected, exit=check.exit, object=check.object, aux=check.stderr)
        self.done.add(check.id)

    def control(self, check: Check, ident: bytes, observed: int, expected: int, klass: str = "control") -> None:
        self.wire.emit(CONTROL, check=check.id, sink=self.sink, mode=MODES[check.mode], view=VIEWS[check.view],
                       klass=CLASSES[klass], subpass=self.subpass, observed=observed, expected=expected, object=ident)
        if klass == "anchor" and observed < 1 or klass != "anchor" and observed != expected:
            check.fail("negative_control_matched" if klass == "negative" else "control_missing")

    def attribute(self, check: Check, pattern: bytes) -> None:
        """One match: a canary is a HIT now, acknowledged before anything else runs; other classes are counted."""
        check.matches += 1
        for klass, consumer, attempt, ident in self.patterns.classes[pattern]:
            if klass == CLASSES["canary"]:
                self.wire.hit(check=check.id, sink=self.sink, mode=MODES[check.mode], view=VIEWS[check.view],
                              path=PATHS[check.path], consumer=consumer, attempt=attempt, subpass=self.subpass,
                              observed=1, object=check.object)
                hook("after_durable_hit")
            else:
                check.counts[(klass, consumer, attempt, ident)] += 1

    def inband(self, name: str) -> tuple:
        ident = bytes.fromhex(self.plan["controls"]["inband"][name])
        return ident, self.patterns.by_id[ident]

    def rg_argv(self, encoding: str, controls: list) -> list:
        return [self.exe("rg"), "--no-config", "--no-mmap", "--text", "--encoding", encoding, "--fixed-strings",
                "--only-matching", "--with-filename", "--null", "--no-line-number", "--no-heading", "--color", "never",
                "--stats", "--no-ignore", "--hidden", "--file", self.patterns.path, "--", *controls, "-"]

    def scanner(self, check: Check, encoding: str, stdin, controls: list, flow: Flow) -> tuple:
        """rg on stdin (a held descriptor, or a pipe when stdin is None), wired into flow: (child, stdin fd, parser)."""
        self.patterns.read()
        labels = {b"<stdin>": None}
        labels.update({os.fsencode(path): (ident, expected, negative) for path, ident, expected, negative in controls})
        child, stdin_fd, out, err = spawn(self, self.rg_argv(encoding, [path for path, *_rest in controls]),
                                          stdin=stdin, piped_stdin=stdin is None)
        parser = RgOutput(self, check, labels)
        flow.read(out, parser.feed)
        flow.read(err, lambda data: self.stderr(check, data, "scanner_stderr"))
        if stdin_fd is not None:
            flow.write(stdin_fd)
        return child, stdin_fd, parser

    def stderr(self, check: Check, data: bytes, reason: str) -> None:
        if data:
            check.stderr += len(data)
            check.fail(reason)

    def settle(self, check: Check, child: Child, parser: RgOutput, deadline: float, files: int) -> None:
        code = child.finish(deadline)
        check.exit = -int(signal.SIGKILL) if code is None else code
        if code is None:
            check.fail("deadline")
        parser.close(files)
        if code not in (0, 1):
            check.fail("scanner_exit")

    def m1_controls(self, bom: bool) -> list:
        spec = self.plan["controls"]
        positive, negative = (spec["bom"], spec["bom_negative"]) if bom else (spec["m1"], spec["m1_negative"])
        return ([(path, bytes.fromhex(ident), expected, False) for path, ident, expected in positive]
                + [(path, bytes.fromhex(ident), 0, True) for path, ident in negative])

    def file_view(self, check: Check, fd: int, bom: bool, size: int, keep: str = None) -> None:
        """M1: rg reads the held descriptor as stdin from offset zero, beside the request's owned control files."""
        controls = self.m1_controls(bom)
        os.lseek(fd, 0, os.SEEK_SET)
        flow, child, parser = Flow(time.monotonic() + budget(120, size, 50e6)), None, None
        try:
            child, _stdin, parser = self.scanner(check, "auto" if bom else "none", fd, controls, flow)
            flow.run()
            self.settle(check, child, parser, flow.deadline, 1 + len(controls))
        except (Deadline, Stop) as error:
            check.fail(getattr(error, "reason", "deadline"))
            flow.abandon()
            if child is not None:
                child.stop()
        if keep:  # the control repository's .keep: a control expected in the scanned file itself
            ident = bytes.fromhex(keep)
            self.control(check, ident, check.counts.pop((CLASSES["control"], 0, 0, ident), 0), 1)
        self.result(check, parser.searched if parser else 0, 1 + len(controls))

    def stream(self, check: Check, producer: Check, argv: list, feed: Relay, seconds: float, stdin=subprocess.DEVNULL,
               cwd=None, pass_fds=()) -> None:
        """One contained producer whose stdout the worker relays into its scanner(s) with backpressure."""
        flow, started = Flow(time.monotonic() + seconds), []
        try:
            child, _in, out, err = spawn(self, argv, stdin=stdin, pass_fds=pass_fds, cwd=cwd)
            started.append((producer, child, None))
            feed.start(self, flow, started)
            flow.read(out, feed.data, throttle=True)
            flow.read(err, lambda data: self.stderr(producer, data, "producer_stderr"))
            flow.run()
            for owner, process, parser in started:
                if parser is not None:
                    self.settle(owner, process, parser, flow.deadline, 1)
                    continue
                code = process.finish(flow.deadline)
                owner.exit = -int(signal.SIGKILL) if code is None else code
                reason = DUMPER_EXITS.get(code, "producer_exit") if producer.mode == "M5" else "producer_exit"
                owner.fail("deadline" if code is None else reason if code else "ok")
            feed.finish()
        except (Deadline, Stop) as error:
            flow.abandon()
            for owner, process, _parser in started:
                owner.fail(getattr(error, "reason", "deadline"))
                process.stop()
            check.fail(getattr(error, "reason", "deadline"))

    # -- the three traversals, the stores and the once-per-worker controls
    def run(self) -> None:
        self.wire.emit(BEGIN, sink=self.sink, subpass=self.subpass, seal=self.seal)
        if self.scope_binding is not None:
            self.wire.emit(FACT, check=FACTS["scope_binding"], observed=self.scope_binding[0], expected=self.scope_binding[1])
        if self.plan["op"] != "scan":
            return SETUP[self.plan["op"]](self)
        self.patterns = Patterns(self.plan["patterns"], self.plan["patterns_sha256"], self.plan["classes"])
        self.pointers()
        walks = [Walk(self, root) for root in self.plan["roots"]]
        for walk in walks:
            self.root = walk.number
            self.wire.emit(BEGIN, sink=self.sink, subpass=self.subpass, seal=self.seal, object=walk.id)
            walk.name_check = self.declare("M6", "name", keyed(self.key, b"names", self.sink, walk.number), "name")
            walk.traverse("pre")
        self.inventory_seal = keyed(self.key, b"inventory", *(walk.canonical() for walk in walks))
        self.wire.emit(BEGIN, sink=self.sink, subpass=self.subpass, seal=self.seal)
        self.root = 0
        self.m6_controls()
        hook("after_prewalk")
        for walk in walks:  # each root is bound again before its checks are declared (BEGIN names the root)
            self.root = walk.number
            self.wire.emit(BEGIN, sink=self.sink, subpass=self.subpass, seal=self.seal, object=walk.id)
            walk.traverse("scan")
            for store in walk.stores:
                store.cover()
        self.root = 0
        self.wire.emit(BEGIN, sink=self.sink, subpass=self.subpass, seal=self.seal)
        self.mode_controls()
        hook("before_postwalk")
        final = [Walk(self, root) for root in self.plan["roots"]]
        for before, after in zip(walks, final):
            after.selected = before.selected
            after.traverse("post")
            before.reconcile(after)
            self.result(before.name_check, before.named, before.named)
        self.finish(keyed(self.key, b"inventory", *(walk.canonical() for walk in final)))

    def finish(self, seal: bytes) -> None:
        for name, count in sorted(self.counters.items()):
            self.wire.emit(COUNTER, check=COUNTERS[name], sink=self.sink, subpass=self.subpass, observed=count)
        outstanding = len(self.checks) - len(self.done)
        failed = [reason for reason in self.reasons if reason != "ok"] + (["protocol_error"] if outstanding else [])
        status = STATUS["incomplete" if failed else "complete"]
        roots = len(self.plan.get("roots", ()))
        self.wire.emit(RESULT, check=0, sink=self.sink, status=status, reason=R[failed[0] if failed else "ok"],
                       subpass=self.subpass, observed=roots, expected=roots)
        self.wire.emit(END, sink=self.sink, subpass=self.subpass, status=status, observed=len(self.done),
                       expected=len(self.checks), seal=seal, aux=outstanding)

    def pointers(self) -> None:
        """A pointer target that is not bound at prepare and lies inside a root refuses the scan (contract 8)."""
        bound = set(self.plan["pointers"]["bound"])
        for path in self.plan["pointers"]["current"]:
            target = os.fsencode(path)
            if pointer_seal(self.key, target).hex() not in bound and any(
                    under(target, os.fsencode(root["path"])) for root in self.plan["roots"]):
                raise Stop("pointer_changed")

    def m6_controls(self) -> None:
        spec = self.plan["controls"]["m6"]
        check = self.declare("M6", "name", keyed(self.key, b"m6-controls"), "name", root=0)
        walk = Walk(self, {"id": "00" * 16, "kind": "dir", "path": spec["dir"], "present": True}, number=0)
        walk.name_check = check
        walk.traverse("pre")
        if not os.path.isfile(spec["negative"]):
            check.fail("control_missing")
        for ident, expected, klass in spec["ids"]:
            key = (CLASSES[klass], 0, 0, bytes.fromhex(ident))
            count = (len(self.patterns.find(os.fsencode(spec["negative"]))) if klass == "negative"
                     else check.counts.pop(key, 0))
            self.control(check, bytes.fromhex(ident), count, expected, klass)
        self.counters.subtract(walk.counted)
        self.result(check, walk.named, walk.named)

    def mode_controls(self) -> None:
        spec = self.plan["controls"]
        for fmt in sorted(fmt for mode, fmt in self.used if mode == "M2"):
            for path, _fmt, ident, view, expected in (row for row in spec["m2"] if row[1] == fmt):
                self.control_file(path, lambda fd, size, ident=ident, view=view, expected=expected, fmt=fmt: self.decode(
                    fd, fmt, keyed(self.key, b"m2-control", ident), size, expect=(bytes.fromhex(ident), view, expected)))
        if ("M4", None) in self.used:
            repo = os.fsencode(spec["m4"]["repo"])
            store = Store(self, repo, keyed(self.key, b"m4-control"))
            store.inventory_from_disk()
            store.cover({bytes.fromhex(spec["m4"]["loose"]): 1, bytes.fromhex(spec["m4"]["packed"]): 1})
            keeps = [name for name in os.listdir(repo + b"/objects/pack") if name.endswith(b".keep")]
            check = self.declare("M1", "raw", keyed(self.key, b"m4-keep"), "git_metadata",
                                 1 + len(self.m1_controls(False)))
            if len(keeps) == 1:  # the .keep metadata control, scanned by M1 like any metadata file
                self.control_file(repo + b"/objects/pack/" + keeps[0],
                                  lambda fd, size: self.file_view(check, fd, False, size, keep=spec["m4"]["keep_id"]))
            else:
                check.fail("control_missing")
                self.result(check)
        if ("M5", None) in self.used:
            for path, ident, expected in spec["m5"]:
                family = {suffix: os.path.lexists(path + suffix) for suffix in ("-wal", "-shm")}
                self.control_file(path, lambda fd, size, path=path, ident=ident, expected=expected, family=family:
                                  self.sqlite(fd, os.fsencode(path), tuple_of(os.fstat(fd)), family,
                                              keyed(self.key, b"m5-control", ident),
                                              expect={bytes.fromhex(ident): expected}))

    def control_file(self, path, function) -> None:
        fd = os.open(path, OPEN_FLAGS)
        try:
            function(fd, os.fstat(fd).st_size)
        finally:
            os.close(fd)

    # -- one selected regular file (contract 9.3): open at the validated parent, verify, sniff, every view, recheck
    def file(self, dir_fd: int, name: bytes, identity: tuple, rel: bytes, path_class: str, family: dict,
             store) -> tuple:
        hook("before_handoff", rel)
        obj = keyed(self.key, b"file", self.sink, self.root, rel)
        try:
            fd = os.open(name, OPEN_FLAGS, dir_fd=dir_fd)
        except OSError:
            check = self.declare("M1", "raw", obj, path_class)
            check.fail("open_error")
            self.result(check)
            return ("error", None)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or tuple_of(info) != identity:
                check = self.declare("M1", "raw", obj, path_class)
                check.fail("file_set_changed" if stat.S_ISREG(info.st_mode) else "changed_type")
                self.result(check)
                return ("error", None)
            hook("after_handoff", rel)
            head = os.pread(fd, SNIFF, 0)
            kind, fmt = classify(head, name, store)
            if store is not None and b"/objects/" in family.get("path", b"") and len(head) >= 2 \
                    and head[0] & 15 == 8 and int.from_bytes(head[:2], "big") % 31 == 0 \
                    and not store.payload(family["path"]):
                kind, fmt = "unaccounted", "container"
            path_class = {"sqlite": "sqlite", "wal": "wal"}.get(kind, path_class)
            raw = self.declare("M1", "raw", obj, path_class, 1 + len(self.m1_controls(False)), info.st_size)
            self.file_view(raw, fd, False, info.st_size)
            encoding = bom_of(head) if kind == "plain" else None
            if encoding:
                bom = self.declare("M1", "bom", obj, path_class, 1 + len(self.m1_controls(True)), info.st_size)
                if not strict_utf16(fd, encoding, info.st_size):
                    bom.fail("bom_invalid")
                self.file_view(bom, fd, True, info.st_size)
            if kind in ("uncovered", "container", "unknown", "unaccounted"):
                check = self.declare("M2", "decoded_raw", obj, path_class, FORMATS.get(fmt, 14))
                check.fail({"unknown": "unknown_format", "unaccounted": "git_unaccounted_payload"}.get(
                    kind, "uncovered_format"))
                self.result(check, 0, FORMATS.get(fmt, 14))
            elif kind == "decode":
                self.decode(fd, fmt, obj, info.st_size, path_class)
            elif kind == "sqlite":
                self.sqlite(fd, None, identity, family, obj)
            elif kind == "wal" and not family.get("main"):
                check = self.declare("M5", "logical", obj, "wal")
                check.fail("sqlite_uri_identity")
                self.result(check)
            hook("after_file_scan", rel)
            if tuple_of(os.fstat(fd)) != identity:  # the held descriptor's full tuple and route, after every view
                self.reasons.append("file_set_changed")
            elif classify(os.pread(fd, SNIFF, 0), name, store) != (kind, fmt):
                self.reasons.append("format_changed")
            return (kind, fmt)
        finally:
            os.close(fd)

    def decode(self, fd: int, fmt: str, obj: bytes, size: int, path_class: str = "other", expect=None) -> None:
        """M2: one contained decoder per file reading the held descriptor as stdin; no raw fallback (contract 10.5)."""
        routing = self.declare("M2", "metadata", obj, path_class, FORMATS[fmt])
        self.result(routing, FORMATS[fmt], FORMATS[fmt])
        self.used.add(("M2", fmt))
        producer = self.declare("M2", "decoded_raw", obj, path_class, 0, size)
        check = self.declare("M2", "decoded_raw", obj, path_class, 1, size)
        try:
            argv = [self.exe("xz"), "--format=lzma", "-d", "-c"] if fmt == "lzma" else [self.exe(fmt), "-d", "-c"]
        except Stop as stop:
            producer.fail(stop.reason)
            check.fail(stop.reason)
        else:
            os.lseek(fd, 0, os.SEEK_SET)
            self.stream(check, producer, argv, Decoded(check, expect), budget(120, size, 5e6), stdin=fd)
        self.result(producer)
        self.result(check, check.observed, 1)

    def sqlite(self, fd: int, path, identity: tuple, family: dict, obj: bytes, expect=None) -> None:
        """M5 (contract 10.8): the contained dumper opens the planned database read-only through an escaped URI and
        proves the main file SQLite opened is this held descriptor's inode."""
        self.used.add(("M5", None))
        producer = self.declare("M5", "logical", obj, "sqlite")
        check = self.declare("M5", "logical", obj, "sqlite", 1)
        header = os.pread(fd, 20, 0)
        wal_mode = len(header) == 20 and header[18] == 2 and header[19] == 2
        if wal_mode and not (family.get("-wal") and family.get("-shm")) or family.get("-wal") and not family.get("-shm"):
            producer.fail("sqlite_readonly_failed")
            check.fail("sqlite_readonly_failed")
        else:
            request = json.dumps({"path": os.fsdecode(path if path is not None else family["path"]), "fd": fd,
                                  "tuple": list(identity)}).encode("ascii") + b"\n"
            read_end, write_end = os.pipe()
            os.write(write_end, request)
            os.close(write_end)
            try:
                self.stream(check, producer, [*self.plan["dumper_argv"], str(read_end)], Relay(check, "m5", expect),
                            budget(120, family.get("bytes", identity[2]), 20e6, 3600), pass_fds=(read_end, fd))
            finally:
                os.close(read_end)
        self.result(producer)
        self.result(check, check.observed, 1)


def pointer_seal(key: bytes, target: bytes) -> bytes:
    try:
        info = os.lstat(target)
    except FileNotFoundError:
        return keyed(key, b"pointer-missing", target)
    return keyed(key, b"pointer", info.st_dev, info.st_ino, stat.S_IFMT(info.st_mode))


def git_directory(candidate: bytes) -> bytes:
    """Git v2.43 gitrepository-layout: gitfile relative to its parent, commondir relative to gitdir."""
    info = os.lstat(candidate)
    if stat.S_ISREG(info.st_mode):
        fd = os.open(candidate, OPEN_FLAGS)
        try:
            text = os.read(fd, 4097).strip()
        finally:
            os.close(fd)
        if len(text) > 4096 or not text.startswith(b"gitdir: "):
            raise Stop("git_indirection_unplanned")
        candidate = os.path.normpath(os.path.join(os.path.dirname(candidate), text[8:]))
    elif not stat.S_ISDIR(info.st_mode):
        raise Stop("git_indirection_unplanned")
    try:
        fd = os.open(candidate + b"/commondir", OPEN_FLAGS)
    except FileNotFoundError:
        return candidate
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise Stop("git_indirection_unplanned")
        common = os.read(fd, 4097).strip()
        if not common or len(common) > 4096:
            raise Stop("git_indirection_unplanned")
        return os.path.normpath(os.path.join(candidate, common))
    finally:
        os.close(fd)


def object_shaped(path: bytes) -> bool:
    """Git object-store shape from a file's own path (git v2.43.0 gitrepository-layout): a loose object
    objects/<2 hex>/<rest of its name>, the same names Store.payload counts, or a pack or index file in objects/pack."""
    parts = path.split(b"/")[-3:]
    if len(parts) < 3 or parts[0] != b"objects":
        return False
    if parts[1] == b"pack":
        match = PACK_FILE.fullmatch(parts[2])
        return match is not None and match.group(2) in (b"pack", b"idx")
    return re.fullmatch(rb"[0-9a-f]{2}", parts[1]) is not None and OID.fullmatch(parts[1] + parts[2]) is not None


class Walk:
    """One root. `pre` records identities and complete entry lists and checks every name, target and full path (M6);
    `scan` hands selected files to their views at their validated parents; `post` re-walks and re-sniffs (contract 9)."""

    def __init__(self, scan: Scan, root: dict, number: int = None):
        self.scan, self.root, self.path, self.kind = scan, root, os.fsencode(root["path"]), root["kind"]
        self.id = bytes.fromhex(root["id"])
        self.number = scan.plan["roots"].index(root) + 1 if number is None else number
        self.items, self.lists, self.routes, self.selected, self.stores = {}, {}, {}, set(), []
        self.state, self.name_check, self.named, self.mode, self.counted = "ok", None, 0, "pre", collections.Counter()
        self.threshold, self.all = scan.plan.get("threshold_ns", 0), scan.plan.get("selection") == "all"

    def count(self, name: str) -> None:
        if self.mode == "pre":
            self.scan.counters[name] += 1
            self.counted[name] += 1

    def names(self, data: bytes, first_end: int) -> None:
        if self.mode == "pre":
            hook("before_m6", data)
            for pattern in self.scan.patterns.find(data, first_end):
                self.scan.attribute(self.name_check, pattern)

    def traverse(self, mode: str) -> None:
        self.mode = mode
        if self.kind in ("journal", "environment"):
            if mode == "scan":
                self.stream_root()
            return
        path = self.path
        if self.kind == "glob":
            path, self.match_pattern = os.path.split(path)
        if self.kind == "git":
            path = self.git_directory()
            if path is None:
                return
        try:
            info = os.lstat(path)
        except FileNotFoundError:
            self.state = "vanished" if self.root["present"] else "absent_since_prepare"
            return
        except OSError:
            self.state = "walk_error"
            return
        self.names(path, 0)
        if stat.S_ISLNK(info.st_mode):
            target = os.readlink(path)
            self.names(target, 0)
            self.items[b""] = ("l", info.st_dev, info.st_ino, target)
            self.state = "root_symlink"
            return
        if stat.S_ISDIR(info.st_mode) and self.kind != "file":
            fd = os.open(path, DIR_FLAGS)
            try:
                if (os.fstat(fd).st_dev, os.fstat(fd).st_ino) != (info.st_dev, info.st_ino):
                    self.state = "file_set_changed"
                    return
                self.directory(fd, b"", path, 0, None)
            finally:
                os.close(fd)
        elif stat.S_ISREG(info.st_mode) and self.kind == "file":
            parent = os.open(os.path.dirname(path), DIR_FLAGS)
            try:
                self.fs_all = fs_magic(parent) not in FS_CHANGED_OK
                if mode == "pre" and self.selected_by_time(info):
                    self.selected.add(b"")
                self.entry(parent, os.path.basename(path), b"", path, info, 0, None, {})
            finally:
                os.close(parent)
        else:
            self.state = "changed_type"

    def git_directory(self):
        """A configured store (A12): the checkout's .git directory, or the common directory that its .git file and
        commondir name; resolved only here (contract 8)."""
        candidate = self.path + b"/.git"
        try:
            info = os.lstat(candidate)
        except FileNotFoundError:
            self.state = "vanished" if self.root["present"] else "absent_since_prepare"
            return None
        try:
            return git_directory(candidate)
        except (OSError, Stop):
            self.state = "git_validation_failed"
            return None

    def excluded(self, child: bytes, parent: bytes, name: bytes):
        plan = self.scan.plan
        if pointer_seal(self.scan.key, child).hex() in plan["pointers"]["bound"]:
            return "key"
        for rule in plan["exclude"]:
            if child == os.fsencode(rule["path"]):
                return rule["class"]
        for rule in plan["exclude_glob"]:
            if parent == os.fsencode(rule["dir"]) and fnmatch.fnmatchcase(name, os.fsencode(rule["glob"])):
                return rule["class"]
        return None

    def selected_by_time(self, info) -> bool:
        """Changed since the threshold by ctime; everything on a filesystem other than ext4, xfs or btrfs, and in a
        comparison (contract 9.1)."""
        return self.all or self.fs_all or info.st_ctime_ns >= self.threshold

    def directory(self, fd: int, rel: bytes, path: bytes, depth: int, store) -> None:
        info = os.fstat(fd)
        magic = fs_magic(fd)
        if magic in FS_UNVERIFIABLE:
            self.state = "quiescence_unverifiable"
        self.fs_all = magic not in FS_CHANGED_OK
        try:
            names = sorted(os.fsencode(name) for name in os.listdir(fd))
        except OSError:
            self.state = "walk_error"
            return
        stats = {}
        for name in names:
            try:
                stats[name] = os.stat(name, dir_fd=fd, follow_symlinks=False)
            except FileNotFoundError:
                self.state = "file_set_changed"
            except OSError:
                self.state = "walk_error"
        identity = ("d",) + tuple_of(info) + (info.st_mode,)
        entries = tuple((name, stat.S_IFMT(entry.st_mode), entry.st_dev, entry.st_ino)
                        for name, entry in stats.items())
        if self.mode == "scan":
            if self.items.get(b"d:" + rel) != identity or self.lists.get(rel) != entries:
                self.scan.reasons.append("file_set_changed")
        else:
            self.items[b"d:" + rel], self.lists[rel] = identity, entries
        self.count("directories")
        # A Git directory by the pinned layout (git v2.43.0 setup.c: HEAD, objects/, refs/), wherever it sits.
        if (os.path.basename(path).endswith(b".git") or
                b"objects" in stats and ({b"HEAD", b"refs"} & stats.keys())):
            store = Store(self.scan, path, keyed(self.scan.key, b"store", self.scan.sink, self.number, rel))
            if self.mode == "scan":
                self.stores.append(store)
            self.count("git_stores")
        families = {}
        for name, entry in stats.items():
            for suffix in (b"-wal", b"-shm"):
                if name.endswith(suffix) and stat.S_ISREG(entry.st_mode):
                    families.setdefault(name[:-4], {})[suffix] = entry
        if self.mode == "pre":
            for name, entry in stats.items():
                # A changed WAL or SHM selects its main database too (contract 9.4); each member keeps its own ctime.
                if stat.S_ISREG(entry.st_mode) and (self.selected_by_time(entry) or any(
                        self.selected_by_time(member) for member in families.get(name, {}).values())):
                    self.selected.add(rel + b"/" + name if rel else name)
            for main, sides in families.items():
                members = {main: stats.get(main), **{main + suffix: entry for suffix, entry in sides.items()}}
                if any(entry is not None and self.selected_by_time(entry) for entry in members.values()):
                    self.selected.update(rel + b"/" + member if rel else member for member in members)
        for name in names:
            if name in stats:
                if self.kind == "glob" and depth == 0 and not fnmatch.fnmatchcase(name, self.match_pattern):
                    continue
                family = {"path": path + b"/" + name,
                          "main": self.routes.get(rel + b"/" + name[:-4] if rel else name[:-4]) == ("sqlite", "sqlite"),
                          "bytes": stats[name].st_size + sum(e.st_size for e in families.get(name, {}).values()),
                          **{suffix.decode(): True for suffix in families.get(name, {})}}
                self.entry(fd, name, rel + b"/" + name if rel else name, path + b"/" + name, stats[name], depth, store,
                           family)
        if self.mode == "scan":
            for main, sides in families.items():
                main_rel = rel + b"/" + main if rel else main
                if any((rel + b"/" + main + suffix if rel else main + suffix) in self.selected for suffix in sides):
                    if self.routes.get(main_rel) != ("sqlite", "sqlite"):
                        self.scan.reasons.append("sqlite_uri_identity")

    def entry(self, fd: int, name: bytes, rel: bytes, path: bytes, info, depth: int, store, family: dict) -> None:
        self.named += self.mode == "pre"
        if rel:  # a file root's own path was checked whole by traverse
            self.names(path, len(path) - len(name) - 1)
        excluded = self.excluded(path, os.path.dirname(path), name)
        if excluded:
            self.items[rel] = ("x", excluded)
            self.count({"key": "excluded_key", "declined": "declined"}.get(excluded, "excluded_user"))
            return
        mode = info.st_mode
        previous = self.items.get(rel)
        current = (("l", info.st_dev, info.st_ino, os.readlink(name, dir_fd=fd)) if stat.S_ISLNK(mode)
                   else ("s", info.st_dev, info.st_ino, stat.S_IFMT(mode)) if not (
                       stat.S_ISDIR(mode) or stat.S_ISREG(mode)) else None)
        if self.mode == "scan" and current is not None and previous != current:
            self.scan.reasons.append("file_set_changed")
            return
        if stat.S_ISLNK(mode):
            target = current[3]
            if self.mode != "scan":
                self.items[rel] = ("l", info.st_dev, info.st_ino, target)
            self.names(target, 0)
            if self.mode == "pre":
                self.link(path)
        elif stat.S_ISDIR(mode):
            if self.kind == "tasks" and depth == 2 and name != b"tasks":
                return
            try:
                child = os.open(name, DIR_FLAGS, dir_fd=fd)
            except OSError:
                self.state = "walk_error"
                return
            try:
                if (os.fstat(child).st_dev, os.fstat(child).st_ino) != (info.st_dev, info.st_ino):
                    self.state = "file_set_changed"
                else:
                    self.directory(child, rel, path, depth + 1, store)
            finally:
                os.close(child)
        elif stat.S_ISREG(mode):
            identity = ("f",) + tuple_of(info)
            if self.mode == "scan":
                if previous != identity:
                    self.scan.reasons.append("file_set_changed")
                    return
            else:
                self.items[rel] = identity
            if self.kind == "tasks" and depth < 3:
                return
            if name == b".git" and self.mode == "scan":
                try:
                    target = git_directory(path)
                    if not self.covered(target):
                        raise Stop("git_indirection_unplanned")
                    # The target must also be a directory this walk discovers as a logical store, including
                    # damaged .git directories. Ordinary directory coverage alone cannot cover Git objects.
                    if not (os.path.basename(target).endswith(b".git") or os.path.lexists(target + b"/objects")
                            and (os.path.lexists(target + b"/HEAD") or os.path.lexists(target + b"/refs"))):
                        raise Stop("git_indirection_unplanned")
                except (OSError, Stop):
                    self.scan.reasons.append("git_indirection_unplanned")
            # The same refusal for a store reached directly: object-store shape (objects/<2 hex>/<name> or a pack or
            # index file) where no logical store was recognized (no HEAD, refs or *.git name). Its zlib loose objects
            # have no Git view, and the plain view cannot read them; selection does not matter (the layout refuses).
            if store is None and self.mode == "scan" and object_shaped(path):
                self.scan.reasons.append("git_indirection_unplanned")
            payload = store.payload(path) if store is not None else False
            chosen = rel in self.selected or (store is not None and not payload)
            if self.mode == "pre":
                self.count("selected" if chosen else "unselected")
                return
            if not chosen:
                return
            if self.mode == "scan":
                self.routes[rel] = self.scan.file(fd, name, tuple_of(info), rel, self.path_class(rel, store, payload),
                                                  family, store)
            else:
                self.routes[rel] = self.recheck(fd, name, tuple_of(info), store)
        else:
            if self.mode != "scan":
                self.items[rel] = ("s", info.st_dev, info.st_ino, stat.S_IFMT(mode))
            self.count("special")

    def recheck(self, fd: int, name: bytes, identity: tuple, store) -> tuple:
        """The final re-walk reopens the name without following links and re-derives its route (contract 9.3)."""
        try:
            handle = os.open(name, OPEN_FLAGS, dir_fd=fd)
        except OSError:
            return ("error", None)
        try:
            if tuple_of(os.fstat(handle)) != identity:
                return ("changed", None)
            return classify(os.pread(handle, SNIFF, 0), name, store)
        finally:
            os.close(handle)

    def link(self, path: bytes) -> None:
        """Resolve a link's target metadata here only: dangling, into a covered root, into K/U, a declared pair, or
        link_out (contract 9.2)."""
        plan, resolved = self.scan.plan, os.path.realpath(path)
        if not os.path.lexists(resolved):
            return self.count("dangling_link")
        for source, target in plan["link_pairs"]:
            if under(path, os.fsencode(source)) and under(resolved, os.fsencode(target)):
                return self.count("declared_link")
        if any(under(resolved, os.fsencode(rule["path"])) for rule in plan["exclude"]) or any(
                under(resolved, os.fsencode(root)) for root in plan["user_roots"]):
            return self.count("excluded_link")
        if self.covered(resolved):
            return self.count("covered_link")
        self.state = "link_out" if self.state == "ok" else self.state

    def covered(self, target: bytes) -> bool:
        """A root recipe must actually select this target; a common path prefix is insufficient."""
        for root in self.scan.plan["coverage"]:
            kind, path = root["kind"], os.fsencode(root["path"])
            if kind == "git":
                try:
                    path = git_directory(path + b"/.git")
                except (OSError, Stop):
                    continue
            if kind not in ("dir", "file", "tasks", "git") or not under(target, path):
                continue
            if kind == "file" and target != path:
                continue
            parts = os.path.relpath(target, path).split(b"/")
            if kind == "tasks" and (len(parts) < 4 or parts[2] != b"tasks"):
                continue
            current = target
            while under(current, path):
                if self.excluded(current, os.path.dirname(current), os.path.basename(current)):
                    break
                try:
                    info = os.lstat(current)
                except OSError:
                    break
                if stat.S_ISLNK(info.st_mode):
                    break
                if current == target and not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
                    break
                if current == target and stat.S_ISREG(info.st_mode):
                    parent = os.open(os.path.dirname(current), DIR_FLAGS)
                    try:
                        selected = (self.all or fs_magic(parent) not in FS_CHANGED_OK or
                                    info.st_ctime_ns >= self.threshold or kind == "git")
                    finally:
                        os.close(parent)
                    if not selected:
                        break
                if current == path:
                    return True
                current = os.path.dirname(current)
        return False

    def path_class(self, rel: bytes, store, payload: bool) -> str:
        if store is not None:
            return "git_object" if payload else "git_metadata"
        parts = rel.split(b"/")
        if self.scan.sink == SINKS["A1"]:
            session = os.fsencode(self.scan.plan["session"]) if self.scan.plan.get("session") else None
            if parts[0] == b"projects" and len(parts) >= 3:
                own = session is not None and parts[2].split(b".")[0] == session
                if len(parts) == 3 and parts[2].endswith(b".jsonl"):
                    return "own_main" if own else "claude_main"
                for word, name in ((b"subagents", "subagent"), (b"workflows", "workflow")):
                    if word in parts[3:]:
                        return ("own_" if own else "claude_") + name
            return "claude_workflow" if b"workflows" in parts else "claude_other"
        if self.scan.sink == SINKS["A4"]:
            return "codex_rollout" if parts[0] == b"sessions" and fnmatch.fnmatchcase(
                parts[-1], b"rollout-*.jsonl") else "codex_other"
        return "other"

    def stream_root(self) -> None:
        scan = self.scan
        if self.kind == "journal":
            check = scan.declare("M3", "raw", keyed(scan.key, b"journal"), "journal", 1)
            producer = scan.declare("M3", "raw", keyed(scan.key, b"journal"), "journal")
            try:
                with open(self.path, "rb") as handle:
                    cursor = handle.read(256).strip()
                if not CURSOR.fullmatch(cursor) or keyed(scan.key, b"cursor", cursor).hex() != scan.plan["journal_seal"]:
                    raise OSError()
            except OSError:
                check.fail("journal_cursor_missing")
                scan.result(producer)
                return scan.result(check, 0, 1)
            anchor = bytes.fromhex(scan.plan["controls"]["anchor"])
            argv = [scan.exe("journalctl"), "--user", "-o", "export", "--no-pager", "--cursor=" + cursor.decode()]
            scan.stream(check, producer, argv, Journal(check, cursor, anchor), budget(600, cap=600))
        else:
            check = scan.declare("U4", "raw", keyed(scan.key, b"environment"), "other", 1)
            producer = scan.declare("U4", "raw", keyed(scan.key, b"environment"), "other")
            scan.stream(check, producer, [scan.exe("systemctl"), "--user", "show-environment"], Relay(check, "u4"),
                        budget(30, cap=30))
        scan.result(producer)
        scan.result(check, check.observed, 1)

    def canonical(self) -> bytes:
        return repr((self.number, sorted(self.items.items()), sorted(self.lists.items()))).encode()

    def reconcile(self, after: "Walk") -> None:
        """Pre-walk against the final re-walk: identities, entry lists, link targets and routes (contract 9.3)."""
        if self.state == "ok" and after.state != "ok":
            self.state = after.state
        if (self.items, self.lists) != (after.items, after.lists):
            self.scan.reasons.append("file_set_changed")
            if any(item[0] == "f" and after.items.get(rel, (None,))[0] == "s"
                   for rel, item in self.items.items()):
                self.state = "changed_type"
        elif any(after.routes.get(rel) != route_ for rel, route_ in self.routes.items()):
            self.scan.reasons.append("format_changed")
        if self.state != "ok":
            self.name_check.fail(self.state)


class Store:
    """A Git directory inside a root or configured (A12): physical objects inventory, fsck, verify-pack, enumeration
    and the framed object stream, reconciled physical-to-logical (contract 10.7)."""

    def __init__(self, scan: Scan, path: bytes, obj: bytes):
        self.scan, self.path, self.object = scan, path, obj
        self.loose, self.packs, self.indexes, self.odd, self.alternates = {}, set(), set(), None, False

    def payload(self, file_path: bytes) -> bool:
        rel = os.path.relpath(file_path, self.path)
        parts = rel.split(b"/")
        if parts[0] != b"objects" or len(parts) < 2:
            return False
        if len(parts) == 3 and re.fullmatch(rb"[0-9a-f]{2}", parts[1]):
            if OID.fullmatch(parts[1] + parts[2]):
                self.loose[parts[1] + parts[2]] = rel
            else:
                self.odd = self.odd or "git_unaccounted_payload"
            return True
        match = PACK_FILE.fullmatch(parts[-1]) if len(parts) == 3 and parts[1] == b"pack" else None
        if match:
            {b"pack": self.packs, b"idx": self.indexes}.get(match.group(2), set()).add(match.group(1))
            if match.group(2) == b"promisor":
                self.odd = "git_promisor_unsupported"
            return match.group(2) == b"pack"
        if parts[-1].startswith((b"tmp_", b"incoming-")):
            self.odd = self.odd or "git_unaccounted_payload"
            return True
        return False

    def inventory_from_disk(self) -> None:
        for directory, _dirs, files in os.walk(self.path + b"/objects"):
            for name in files:
                self.payload(os.path.join(directory, name))

    def git(self, check: Check, args: list, seconds: float) -> bytes:
        """A producer-only git stage: exit 0, no stderr, its stdout parsed here."""
        flow, output = Flow(min(time.monotonic() + seconds, self.deadline)), bytearray()
        child = None
        try:
            child, _in, out, err = spawn(self.scan, [self.scan.exe("git"), "--git-dir=.", *args], cwd=self.path)
            flow.read(out, output.extend)
            flow.read(err, lambda data: self.scan.stderr(check, data, "producer_stderr"))
            flow.run()
            code = child.finish(flow.deadline)
            check.exit = -int(signal.SIGKILL) if code is None else code
            check.fail("deadline" if code is None else "producer_exit" if code else "ok")
        except (Deadline, Stop) as error:
            flow.abandon()
            check.fail(getattr(error, "reason", "deadline"))
            if child is not None:
                child.stop()
        return bytes(output)

    def validate(self) -> str:
        covered = [os.fsencode(root) for root in self.scan.plan["covered"]]
        if os.path.lexists(self.path + b"/commondir"):
            with open(self.path + b"/commondir", "rb") as handle:
                common = os.path.normpath(os.path.join(self.path, handle.read(4096).strip()))
            if not any(under(common, root) for root in covered):
                return "git_indirection_unplanned"
        try:  # an alternate object store must be a root this request covers; that root's own scan reconciles it
            with open(self.path + b"/objects/info/alternates", "rb") as handle:
                for line in handle.read().splitlines():
                    if not line.strip() or line.startswith(b"#"):
                        continue
                    target = os.path.normpath(os.path.join(self.path + b"/objects", line.strip()))
                    if not any(under(target, root) for root in covered) or any(
                            under(target, os.fsencode(rule["path"])) for rule in self.scan.plan["exclude"]):
                        return "git_alternate_unplanned"
                    self.alternates = True
        except FileNotFoundError:
            pass
        try:
            with open(self.path + b"/config", "rb") as handle:
                config = handle.read().lower()
            if b"promisor" in config or b"partialclone" in config:
                return "git_promisor_unsupported"
            if b"[include" in config or b"alternaterefscommand" in config:
                return "git_indirection_unplanned"
        except FileNotFoundError:
            pass
        if self.odd:
            return self.odd
        if self.packs != self.indexes:  # an orphan pack or an index-only file
            return "git_unaccounted_payload"
        return "ok"

    def cover(self, expect: dict = None) -> None:
        scan = self.scan
        scan.used.add(("M4", None))
        seconds = budget(1800, cap=1800)
        self.deadline = time.monotonic() + seconds
        fsck = scan.declare("M4", "logical", self.object, "git_object")
        verdict = self.validate()
        if verdict != "ok":
            fsck.fail(verdict)
            return scan.result(fsck)
        if self.git(fsck, ["fsck", "--full", "--strict", "--no-reflogs", "--no-dangling"], seconds):
            fsck.fail("git_validation_failed")
        scan.result(fsck)
        members = set()
        for name in sorted(self.packs):
            check = scan.declare("M4", "logical", self.object, "git_object")
            output = self.git(check, ["verify-pack", "--verbose", "objects/pack/pack-" + name.decode() + ".idx"],
                              seconds)
            lines = output.splitlines()
            if not lines or not lines[-1].endswith(b": ok"):
                check.fail("git_validation_failed")
            for line in lines[:-1]:
                fields = line.split()
                if len(fields) >= 5 and OID.fullmatch(fields[0]):
                    members.add(fields[0])
                elif not (line.startswith(b"non delta: ") or line.startswith(b"chain length")):
                    check.fail("unparseable_output")
            scan.result(check)
        objects = self.enumerate()
        if objects is None:
            return
        check = scan.declare("M4", "logical", self.object, "git_object", 1)
        producer = scan.declare("M4", "logical", self.object, "git_object")
        # Physical to logical: every loose payload and pack member is enumerated, and (without a planned alternate)
        # every enumerated object has a physical copy here. Sets, not counts: duplicates map many to one.
        physical, logical = set(self.loose) | members, set(objects)
        if not physical <= logical or not (self.alternates or logical <= physical):
            check.fail("git_unaccounted_payload")
        argv = [scan.exe("git"), "--git-dir=.", "cat-file", "--batch-all-objects", "--unordered",
                "--batch=%(objectname) %(objecttype) %(objectsize)"]
        scan.stream(check, producer, argv, GitStream(check, objects, expect),
                    max(0, self.deadline - time.monotonic()), cwd=self.path)
        scan.result(producer)
        scan.result(check, check.observed, 1)
        again = self.enumerate()
        if again is not None and again != objects:
            scan.reasons.append("file_set_changed")

    def enumerate(self):
        check = self.scan.declare("M4", "logical", self.object, "git_object")
        output = self.git(check, ["cat-file", "--batch-all-objects",
                                  "--batch-check=%(objectname) %(objecttype) %(objectsize)"], budget(1800, cap=1800))
        objects = {}
        for line in output.splitlines():
            parts = line.split(b" ")
            if len(parts) != 3 or not OID.fullmatch(parts[0]) or not parts[2].isdigit():
                check.fail("unparseable_output")
                break
            objects[parts[0]] = (parts[1], int(parts[2]))
        self.scan.result(check)
        return objects if check.reason == "ok" else None


# ---- Setup operations (contract 5 and 7): every one contained, each answering with FACT records only ----------------
def setup_prepare(scan: Scan) -> None:
    plan, key = scan.plan, scan.key
    for index, name in enumerate(sorted(plan["exes"])):
        path, digest = plan["exes"][name] or (None, None)
        code, seal = 0, bytes(16)
        if path:
            text = run_text(scan, [path, "--version"])
            code = version_code(name, text)
            seal = keyed(key, b"exe", name, sha256_file(path)) if sha256_file(path) == digest else bytes(16)
        scan.wire.emit(FACT, check=FACTS["executable_version"], observed=code, expected=index)
        scan.wire.emit(FACT, check=FACTS["executable_fingerprint"], expected=index, seal=seal)
    import sqlite3
    scan.wire.emit(FACT, check=FACTS["executable_version"], observed=version_code("sqlite", sqlite3.sqlite_version),
                   expected=len(plan["exes"]))
    for root in plan["roots"]:
        try:
            path = os.fsencode(root["path"])
            if root["kind"] == "glob":
                path = os.path.dirname(path)
            info = os.lstat(path + (b"/.git" if root["kind"] == "git" else b""))
            present = 2 if stat.S_ISLNK(info.st_mode) else 1
        except OSError:
            present = 0
        if root["kind"] in ("journal", "environment"):
            present = 1
        scan.wire.emit(FACT, check=FACTS["root_presence"], observed=present, object=bytes.fromhex(root["id"]))
    for index, path in enumerate(plan["pointers"]["current"]):
        target = os.fsencode(path)
        try:
            info = os.lstat(target)
            kind = 1 if stat.S_ISREG(info.st_mode) else 2 if stat.S_ISDIR(info.st_mode) else 3
        except FileNotFoundError:
            kind = 0
        scan.wire.emit(FACT, check=FACTS["pointer_binding"], observed=kind, expected=index,
                       seal=pointer_seal(key, target))
    journal = plan.get("journal")
    if journal:
        cursor = journal_anchor(scan, journal["anchor"].encode("ascii"))
        if cursor:
            fd = os.open(journal["cursor_file"], os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            os.write(fd, cursor + b"\n")
            os.close(fd)
        scan.wire.emit(FACT, check=FACTS["journal_binding"], observed=1 if cursor else 0,
                       seal=keyed(key, b"cursor", cursor) if cursor else bytes(16))
    revision = run_text(scan, [scan.exes["git"][0], "-C", plan["checkout"], "rev-parse", "--verify", "HEAD"],
                        stderr=False).strip()
    scan.wire.emit(FACT, check=FACTS["checkout"], observed=1 if OID.fullmatch(revision.encode()) else 0,
                   seal=keyed(key, b"checkout", revision) if OID.fullmatch(revision.encode()) else bytes(16))
    setup_arm(scan)


def setup_arm(scan: Scan) -> None:
    plan = scan.plan
    scan.wire.emit(FACT, check=FACTS["guard_pin"],
                   observed=int(cs.guard_matches_pin(Path(plan["claude_dir"]), ROOT)))
    scan.wire.emit(FACT, check=FACTS["store_outside_worktree"],
                   observed=int(cs.git_worktree_of(Path(plan["store_root"])) is None))
    scan.wire.emit(END, status=STATUS["complete"], seal=scan.seal)


def setup_controls(scan: Scan) -> None:
    """The request's synthetic control repository: one packed and one loose control blob and a .keep control
    (contract 10.7), built with contained git init, hash-object, mktree, commit-tree, update-ref and pack-objects."""
    spec, repo = scan.plan["controls"]["m4"], os.fsencode(scan.plan["controls"]["m4"]["repo"])
    git = scan.exe("git")
    env = dict(GIT_AUTHOR_NAME="canary-proof", GIT_AUTHOR_EMAIL="canary-proof@invalid", GIT_AUTHOR_DATE="@0 +0000",
               GIT_COMMITTER_NAME="canary-proof", GIT_COMMITTER_EMAIL="canary-proof@invalid",
               GIT_COMMITTER_DATE="@0 +0000")
    scan.child_env.update(env)

    def run(*args, stdin=b"") -> bytes:
        read_end, write_end = os.pipe()
        os.write(write_end, stdin)
        os.close(write_end)
        try:
            return run_text(scan, [git, *args], stdin=read_end, cwd=repo if os.path.isdir(repo) else None,
                            stderr=False).strip().encode()
        finally:
            os.close(read_end)

    run("init", "-q", "--bare", os.fsdecode(repo))
    packed = run("--git-dir=.", "hash-object", "-w", "--stdin", stdin=spec["packed_value"].encode() + b"\n")
    loose = run("--git-dir=.", "hash-object", "-w", "--stdin", stdin=spec["loose_value"].encode() + b"\n")
    tree = run("--git-dir=.", "mktree", stdin=b"100644 blob " + packed + b"\tp\n100644 blob " + loose + b"\tl\n")
    commit = run("--git-dir=.", "commit-tree", tree.decode(), "-m", "canary-proof control")
    run("--git-dir=.", "update-ref", "refs/heads/master", commit.decode())
    name = run("--git-dir=.", "pack-objects", "-q", "objects/pack/pack", stdin=packed + b"\n")
    run("--git-dir=.", "prune-packed")
    ok = all(OID.fullmatch(value) for value in (packed, loose, tree, commit, name))
    if ok:
        fd = os.open(repo + b"/objects/pack/pack-" + name + b".keep", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.write(fd, spec["keep_value"].encode() + b"\n")
        os.close(fd)
    scan.wire.emit(FACT, check=FACTS["git_inventory"], observed=int(ok))
    scan.wire.emit(END, status=STATUS["complete" if ok else "incomplete"], seal=scan.seal)


def run_text(scan: Scan, argv: list, stdin=subprocess.DEVNULL, cwd=None, stderr=True, raw=False):
    """A short contained helper's stdout (and stderr when asked, for --version texts), bounded by the setup budget."""
    child, _in, out, err = spawn(scan, argv, stdin=stdin, cwd=cwd)
    flow, output, diagnostics = Flow(time.monotonic() + budget(30, cap=30)), bytearray(), bytearray()
    def collect(data):
        output.extend(data)
        if len(output) > STDOUT_CAP:
            raise Stop("output_cap")
    flow.read(out, collect)
    flow.read(err, collect if stderr else diagnostics.extend)
    try:
        flow.run()
        code = child.finish(flow.deadline)
        if code != 0 or diagnostics:
            raise Stop("producer_stderr" if diagnostics else "producer_exit")
    except (Deadline, Stop):
        flow.abandon()
        child.stop()
        raise
    finally:
        flow.selector.close()
    return bytes(output) if raw else output.decode("ascii", "replace")


def export_entries(data: bytes) -> list:
    """systemd v255 JOURNAL_EXPORT_FORMATS: binary fields have uint64 LE lengths; delimiters inside them are data."""
    entries = []
    ExportParser(entries.append).feed(data, final=True)
    return entries


def journal_anchor(scan: Scan, anchor: bytes):
    """Write the synthetic anchor with systemd-cat and find its exported entry's cursor (contract 10.6)."""
    read_end, write_end = os.pipe()
    os.write(write_end, anchor + b"\n")
    os.close(write_end)
    try:
        run_text(scan, [scan.exe("systemd-cat"), "-t", "canary-proof"], stdin=read_end)
    finally:
        os.close(read_end)
    for _attempt in range(20):
        text = run_text(scan, [scan.exe("journalctl"), "--user", "-o", "export", "--no-pager",
                               "SYSLOG_IDENTIFIER=canary-proof"], stderr=False, raw=True)
        for fields in export_entries(text):
            if fields.get(b"MESSAGE") == anchor and CURSOR.fullmatch(fields.get(b"__CURSOR", b"")):
                return fields[b"__CURSOR"]
        time.sleep(0.25)
    return None


SETUP = {"prepare": setup_prepare, "arm": setup_arm, "controls": setup_controls}


# ---- The SQLite dumper (a separate contained process) -----------------------------------------------------------------
def own_descriptors() -> set:
    listing = os.open("/proc/self/fd", os.O_RDONLY | os.O_DIRECTORY)
    try:
        return {int(name) for name in os.listdir(listing)} - {listing}
    finally:
        os.close(listing)


def dump(control_fd: int) -> int:
    import sqlite3
    request = json.loads(b"".join(iter(lambda: os.read(control_fd, 65536), b"")).decode("ascii"))
    fd, path, planned = request["fd"], os.fsencode(request["path"]), tuple(request["tuple"])
    held = os.fstat(fd)
    if tuple_of(held) != planned:
        return 10
    before = own_descriptors()
    hook("before_sqlite_open")
    uri = "file:" + urllib.parse.quote_from_bytes(path, safe="/") + "?mode=ro"
    try:
        connection = sqlite3.connect(uri, uri=True, isolation_level=None)
    except sqlite3.Error:
        return 13
    hook("after_sqlite_open")
    connection.text_factory = bytes
    try:
        connection.execute("PRAGMA query_only=1")
        if hasattr(connection, "enable_load_extension"):
            connection.enable_load_extension(False)
        connection.execute("BEGIN")
        mains = [row for row in connection.execute("PRAGMA database_list").fetchall() if row[1] == b"main"]
        schema = connection.execute("SELECT type, name, tbl_name, sql FROM main.sqlite_master").fetchall()
    except sqlite3.Error:
        return 11
    if len(mains) != 1 or not mains[0][2] or os.path.realpath(mains[0][2]) != os.path.realpath(path):
        return 10
    opened = []
    for descriptor in own_descriptors() - before:
        try:
            info = os.fstat(descriptor)
        except OSError:
            continue
        if (info.st_dev, info.st_ino) == (held.st_dev, held.st_ino):
            opened.append(descriptor)
    hook("after_identity")
    if len(opened) != 1:
        return 10
    out = os.fdopen(1, "wb", buffering=1 << 16)
    for row in schema:
        for value in row:
            if isinstance(value, bytes):
                out.write(value + b"\n")
    # Virtual tables are never executed; each needs its ordinary shadow tables, which are scanned (C13).
    virtual = {row[1] for row in schema if row[0] == b"table"
               and (row[3] or b"").lstrip().upper().startswith(b"CREATE VIRTUAL TABLE")}
    tables = [row[1] for row in schema if row[0] == b"table" and row[1] not in virtual]
    try:
        shadows = {row[1] for row in connection.execute("PRAGMA main.table_list") if row[2] == b"shadow"}
    except sqlite3.Error:
        return 12
    # SQLite version-3.45.1: fts3ShadowName, fts5ShadowName and rtreeShadowName. The module and exact suffix
    # establish ownership; a_b_data is not a shadow of a. Optional content/docsize tables may be absent.
    required = {b"fts3": (b"segments", b"segdir"), b"fts4": (b"segments", b"segdir"),
                b"fts5": (b"config", b"data", b"idx"), b"rtree": (b"node", b"parent", b"rowid"),
                b"rtree_i32": (b"node", b"parent", b"rowid")}
    identifier = rb'(?:"(?:[^"]|"")+"|`(?:[^`]|``)+`|\[[^\]]+\]|[^\s(]+)'
    for row in schema:
        if row[1] not in virtual:
            continue
        match = re.match(rb"\s*CREATE\s+VIRTUAL\s+TABLE\s+" + identifier + rb"\s+USING\s+(" + identifier + rb")",
                         row[3], re.IGNORECASE)
        module = match[1].strip(b'"`[]').lower() if match else b""
        suffixes = required.get(module)
        if not suffixes or not {row[1] + b"_" + suffix for suffix in suffixes} <= shadows:
            return 12
    try:
        for table in tables:
            quoted = '"' + table.decode("utf-8").replace('"', '""') + '"'
            for row in connection.execute("SELECT * FROM main." + quoted):
                for value in row:
                    if isinstance(value, bytes):
                        out.write(value + b"\n")
        connection.execute("COMMIT")
    except (sqlite3.Error, UnicodeDecodeError):
        return 12
    connection.close()
    out.flush()
    after = os.stat(path)
    if tuple_of(os.fstat(fd)) != planned or (after.st_dev, after.st_ino) != (held.st_dev, held.st_ino):
        return 10
    return 0


# ---- Entry ----------------------------------------------------------------------------------------------------------
SCOPE_CHECK = verify_scope  # a CI launcher's exec stub replaces this; the real runner's scope is checked otherwise


def main(argv: list) -> int:
    for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP, signal.SIGQUIT):
        signal.signal(signum, _interrupt)
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    if argv[:1] == ["sqlite-dumper"] and len(argv) == 2:
        try:
            SCOPE_CHECK()
            return dump(int(argv[1]))
        except Exception:  # noqa: BLE001 - a fixed code, never a traceback
            return 1
    if len(argv) != 4 or argv[0] != "worker":
        return 2
    plan_fd, proto_fd, ack_fd = (int(value) for value in argv[1:])
    try:
        nonce, body, plan = read_plan(plan_fd)
    except Exception:  # noqa: BLE001 - no handshake: no record at all
        return 3
    finally:
        os.close(plan_fd)
    wire, scan, reason = Wire(proto_fd, ack_fd, nonce), None, "ok"
    try:
        binding = SCOPE_CHECK()
        scan = Scan(plan, wire, body)
        scan.scope_binding = binding
        if plan.get("budget_seconds"):
            signal.signal(signal.SIGALRM, lambda *_args: (_ for _ in ()).throw(Deadline()))
            signal.setitimer(signal.ITIMER_REAL, plan["budget_seconds"])
        scan.run()
    except Deadline:
        reason = "deadline"
    except Interrupted:
        reason = "interrupted"
    except Stop as stop:
        reason = stop.reason
    except Exception:  # noqa: BLE001 - fixed enum only (contract 10.1)
        reason = "setup_failed"
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        stop_all()
    if reason != "ok":
        try:
            wire.emit(RESULT, check=0, sink=plan.get("sink", 0), status=STATUS["incomplete"], reason=R[reason],
                      subpass=plan.get("subpass", 0))
            wire.emit(END, sink=plan.get("sink", 0), subpass=plan.get("subpass", 0), status=STATUS["incomplete"],
                      observed=len(scan.done) if scan else 0, expected=len(scan.checks) if scan else 0,
                      aux=(len(scan.checks) - len(scan.done)) if scan else 0)
        except OSError:
            pass
        return 1
    # Keep the native runner alive until the coordinator explicitly stops its scope after END. Closing the ACK
    # channel also releases a terminal worker if the coordinator disappears. No second END is emitted.
    try:
        signal.pthread_sigmask(signal.SIG_UNBLOCK, (signal.SIGINT, signal.SIGTERM, signal.SIGHUP, signal.SIGQUIT))
        if select.select([ack_fd], [], [], ACK_SECONDS)[0]:
            os.read(ack_fd, 1)
    except (Interrupted, OSError):
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
