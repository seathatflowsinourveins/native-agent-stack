#!/usr/bin/env python3
"""Run one command with one inventory entry's keys in its environment, and mask those keys in its output.

    python3 tools/credentials/credential_run.py <inventory-id> [--only NAME]... -- <command> [args...]
    python3 tools/credentials/credential_run.py <inventory-id> --check
    python3 tools/credentials/credential_run.py --help

The entry's 0600 file in the per-host store is read by inventory id (adoption/credential-inventory.json). The
command gets the caller's environment minus every inventory variable, must_not_be_set name and pointer variable
(another entry's store-file path) but this entry's own pointers, plus only this entry's declared variables (narrowed by
--only). No value goes into argv, a temporary file, a socket or a shell.
The command's stdout and stderr are relayed through pipes with each injected value, raw or in a common encoding,
replaced by [REDACTED:<NAME>]; names the entry lists in public_variables (a base URL) are injected unmasked.
`--check` starts nothing and prints the names it would inject and the file state (ok, missing or unsafe). There is
no subcommand that prints, lists or returns a value, and there never will be.

Masking is accident-proofing, not a boundary: a command that transforms a value (reverses it, encrypts it, prints a
fragment such as its first eight characters) or writes it to a file or a log defeats it, and stdout and stderr are
masked separately. Core dumps are off (RLIMIT_CORE 0); a host whose core_pattern hands dumps to a collector (a
leading | or @), which sets that limit aside, is refused, with no override. Output goes through non-blocking
descriptors and a bounded queue, so a consumer that stops reading cannot hold the runner past a shutdown signal or
the drain deadline. The command leads its own session and process group. SIGINT, SIGTERM, SIGHUP, SIGQUIT, SIGUSR1,
SIGUSR2 and SIGALRM sent to the runner are forwarded to that group; once the command has exited and its output is
drained, and on every way out of the runner, the group gets SIGTERM and, after TERM_GRACE_SECONDS, SIGKILL, so no
descendant that stayed in it is left running with a key in its environment. If the runner itself dies without a chance
to do that (SIGKILL, the OOM killer), the command asks the kernel for SIGTERM (Linux PR_SET_PDEATHSIG, which reaches
the command alone) and a watchdog process started with it ends its whole group. Both are best effort: a SIGKILL
before the fork, a descendant that left the group with setsid, and a same-user debugger are out of reach. Exit status:
the command's own; 128+N when it died of signal N; 2 for a usage error; 1 for a refusal; 126 or 127 when it cannot
start. Messages carry the id, variable names, line numbers and reason codes, never a value, a store line or a path
(docs/secret-storage.md#using-a-key). The runner is available, not yet the default path: the command guard does not
read its command (phase 2 of the same change series).

Built from these references (observed 2026-09-29): the env-only exec discipline of scripts/kernel_keyring.py; the
load_env_file grammar of blueprints/us-equities/pit-availability/measure.py:51-67 with set_credential.py's value
grammar; dotenvx/dotenvx@278101db src/lib/helpers/redactOutput.js (longest first L4-9, held partial tail L36-50,
never cutting a match L52-72); actions/runner@15231bed src/Sdk/DTLogging/Logging/ValueEncoders.cs (base64 at
shifted alignments L16-39 and L146-159, JSON escape L52-58, URI data escape L60-63) and SecretMasker.cs (merged
overlaps L255-279); buildkite/agent@3345ee60 internal/redact/redact.go (LengthMin 6, L20-25) and
internal/replacer/replacer.go (buffer, merge, never spill a partial match, L99-115); dmno-dev/varlock@1b880652
packages/varlock/src/runtime/lib/redact-stream.ts (100 ms idle flush, L8 and L34-46); Generalized-Labs/ironrun@b611c7ce
internal/redact/encodings.go (hex and upper- and lower-case percent forms, L13-21); torvalds/linux@v6.16
fs/coredump.c and systemd/systemd@v257 src/coredump/coredump.c (check_core_pattern below); the man-pages
PR_SET_PDEATHSIG(2const) page of man7.org (parent_death_hook), bazelbuild/bazel@d2545923
src/main/tools/process-tools.cc KillEverything L94-110 (end_group) and python/cpython@v3.13.15
Lib/multiprocessing/resource_tracker.py L8, L246-267 and L425-429 (the pipe-and-end-of-file helper of the watchdog).
"""
from __future__ import annotations

import os
import sys

if __name__ == "__main__" and not (sys.flags.isolated and sys.flags.no_site):
    # Re-run isolated before anything is read, as set_credential.py and scripts/kernel_keyring.py do: -I ignores
    # PYTHONPATH, the PYTHON* variables and the user site directory, and -S also skips site, whose .pth lines run even
    # under -I. Values are read only in the re-executed interpreter.
    os.execv(sys.executable, [sys.executable, "-I", "-S", os.path.abspath(__file__), *sys.argv[1:]])

import base64  # noqa: E402
import collections  # noqa: E402
import contextlib  # noqa: E402
import json  # noqa: E402
import re  # noqa: E402
import resource  # noqa: E402
import select  # noqa: E402
import selectors  # noqa: E402
import signal  # noqa: E402
import stat  # noqa: E402
import subprocess  # noqa: E402
import time  # noqa: E402
import urllib.parse  # noqa: E402
from pathlib import Path  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
# -I keeps the script's own directory off sys.path, so the two sibling modules are put there explicitly.
for _directory in (ROOT / "tools" / "credentials", ROOT / "scripts"):
    if str(_directory) not in sys.path:
        sys.path.insert(0, str(_directory))
import credential_status as cs  # noqa: E402  (inventory schema and store-path resolution)
import set_credential as writer  # noqa: E402  (the writer's value grammar is the reader's)

USAGE = """usage:
  credential_run.py <inventory-id> [--only NAME]... -- <command> [args...]
  credential_run.py <inventory-id> --check
  credential_run.py --help
Runs <command> with the entry's declared variables in its environment and masks their values in its output.
  --only NAME  inject only NAME, a variable the entry declares (repeatable)
  --check      print the names it would inject and the file state (ok, missing or unsafe); start nothing
See docs/secret-storage.md#using-a-key."""
ID = re.compile(r"[a-z0-9-]+")
LINE = re.compile(r"export +([A-Za-z_][A-Za-z0-9_]*)=(.*)")
INJECTABLE_STATUSES = {"required", "optional", "user_only_paid", "test_only"}
RESERVED = re.compile(r"(?:LD_|DYLD_|PYTHON).*")  # read at start-up and echoed on error (scripts/kernel_keyring.py)
HOLDERS = {"generated_local": "generated and held by its own service",
           "native": "a native sign-in that its client reads itself",
           "interactive_only": "typed at its own login; nothing is stored",
           "ci_only": "held by GitHub Actions; no local copy"}
TERMINAL_HINT = "add it with: bash tools/credentials/open_credential_terminal.sh {}"
MAX_FILE_BYTES = 64 * 1024
LENGTH_MIN = 6               # buildkite/agent redact.go LengthMin: a shorter value would mask ordinary output
IDLE_FLUSH_SECONDS = 0.1     # varlock FLUSH_TIMEOUT_MS
# A held tail of 4 bytes or more is the start of a value: it is never written, on the idle timer or when the stream
# ends. A shorter one is written after IDLE_FLUSH_SECONDS or at the end, because it is mostly ordinary output: every
# Tavily key starts "tvly-", whose base64 starts "d", so a command's last "d" would otherwise become a marker.
SHORT_TAIL_MAX = 3
DRAIN_SECONDS = 2.0          # after the command exits, how long a descendant may keep a pipe open, and a consumer may
                             # take the output still queued for it; after a shutdown signal the consumer gets no wait
QUEUE_LIMIT = 256 * 1024     # masked bytes one stream queues for a consumer that has stopped reading
POLL_SECONDS = 0.1
READ_SIZE = 65536
CORE_PATTERN_FILE = "/proc/sys/kernel/core_pattern"  # a name, never a value, in the messages that mention it
# Signals the runner forwards to the command's process group. After the first four the relay waits for no consumer.
SHUTDOWN_SIGNALS = (signal.SIGINT, signal.SIGTERM, signal.SIGHUP, signal.SIGQUIT)
# Fatal to a process by default and often handled by a command (SIGUSR1 asks dd for its progress): forwarded, so the
# command decides and the runner does not die alone with the command left running.
PASSED_SIGNALS = (signal.SIGUSR1, signal.SIGUSR2, signal.SIGALRM)
FORWARDED = SHUTDOWN_SIGNALS + PASSED_SIGNALS
TERM_GRACE_SECONDS = 2.0     # after SIGTERM to the command's process group, how long it has to end before SIGKILL
KILL_WAIT_SECONDS = 1.0      # after SIGKILL, how long to wait for the group to be gone and the command reaped
PR_SET_PDEATHSIG = 1         # <linux/prctl.h>


class UsageError(Exception):
    """Bad arguments (exit 2). The message never repeats an argument, which could be a pasted value."""


class Refused(Exception):
    """A safety rule refused (exit 1). state is what --check prints: missing, unsafe, or refused for the rest."""

    def __init__(self, detail: str, state: str = "refused", hint: str = ""):
        super().__init__(detail)
        self.detail, self.state, self.hint = detail, state, hint


class SpawnError(Exception):
    """The command could not start: 127 when it was not found, 126 otherwise."""

    def __init__(self, code: int, reason: str):
        super().__init__(reason)
        self.code, self.reason = code, reason


def injectable(entry: dict) -> bool:
    """An operator-supplied key in its own env file; engine-held, native, interactive and CI entries are not."""
    return entry["store"]["kind"] == "private_env_file" and entry["status"] in INJECTABLE_STATUSES


def masked_names(entry: dict) -> list:
    """Every declared variable except the entry's public_variables, read from the schema module (scripts/
    credential_status.py), where a required variable is never public."""
    return cs.masked_names(entry)


def public_names(entry: dict) -> list:
    """The optional variables the entry classifies as not secret (a base URL): injected unmasked."""
    return cs.public_names(entry)


def load_inventory(root: Path = ROOT) -> dict:
    try:
        inventory = json.loads((root / cs.INVENTORY).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise Refused("inventory_unreadable; check with python3 scripts/credential_status.py") from None
    errors = cs.inventory_errors(inventory, root)
    if errors:
        raise Refused(f"invalid_inventory ({len(errors)} errors); check with python3 scripts/credential_status.py")
    return inventory


def find_entry(entry_id: str, inventory: dict) -> dict:
    entry = next((e for e in inventory["entries"] if e["id"] == entry_id), None)
    if entry is None:  # the id is not repeated: a lowercase value typed in its place matches the id pattern
        raise Refused("unknown inventory id; see adoption/credential-inventory.json")
    return entry


def check_injectable(entry: dict) -> None:
    if not injectable(entry):
        text = HOLDERS.get(entry["status"], "not an operator-supplied stored key")
        loaders = [ref.split("#", 1)[0] for ref in entry["loaders"]]
        raise Refused("not_injectable: " + (f"{text} ({loaders[0]})" if loaders else text))
    reserved = [name for name in entry["variables"] + entry["optional_variables"] if RESERVED.fullmatch(name)]
    if reserved:
        raise Refused("reserved_variable: " + ", ".join(reserved))


def read_store(entry: dict, env, uid: int) -> bytes:
    """The entry's file, opened without following links through a checked handle on the 0700 store directory."""
    root = cs.expand_template(cs.STORE_ROOT, env)
    path = cs.expand_template(entry["store"]["path_template"], env)
    if path.parent != root:
        raise Refused("not_in_store_root", "unsafe")
    missing = Refused(f"<store>/{path.name}", "missing", TERMINAL_HINT.format(entry["id"]))
    try:
        if stat.S_ISLNK(os.lstat(root).st_mode):
            raise Refused("store_directory_symlink", "unsafe")
    except FileNotFoundError:
        raise missing from None
    if cs.git_worktree_of(root) is not None:
        raise Refused("inside_git_worktree", "unsafe")
    try:
        dfd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except OSError:
        raise Refused("store_directory_unusable", "unsafe") from None
    try:
        directory = os.fstat(dfd)
        if directory.st_uid != uid or stat.S_IMODE(directory.st_mode) != 0o700:
            raise Refused("store_directory_not_private", "unsafe")
        try:
            kind = os.stat(path.name, dir_fd=dfd, follow_symlinks=False).st_mode
        except FileNotFoundError:
            raise missing from None
        if stat.S_ISLNK(kind):
            raise Refused("symlink_refused", "unsafe")
        if not stat.S_ISREG(kind):  # a FIFO would block a plain open until a writer came
            raise Refused("not_regular_file", "unsafe")
        try:
            fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK, dir_fd=dfd)
        except OSError:
            raise Refused("cannot_open", "unsafe") from None
        try:
            info = os.fstat(fd)
            for failed, reason in ((not stat.S_ISREG(info.st_mode), "not_regular_file"),
                                   (info.st_uid != uid, "foreign_owner"),
                                   (stat.S_IMODE(info.st_mode) != 0o600, "mode_not_0600"),
                                   (info.st_nlink != 1, "hard_link"),
                                   (info.st_size > MAX_FILE_BYTES, "too_large")):
                if failed:
                    raise Refused(reason, "unsafe")
            data = b""
            while True:
                chunk = os.read(fd, READ_SIZE)
                if not chunk:
                    return data
                data += chunk
                if len(data) > MAX_FILE_BYTES:
                    raise Refused("too_large", "unsafe")
        finally:
            os.close(fd)
    finally:
        os.close(dfd)


def parse(entry_id: str, data: bytes, entry: dict) -> dict:
    """`export NAME=value` lines; blank lines and # comments are skipped. Lines are reported by number only.

    measure.py's load_env_file grammar (export required, matching outer quotes stripped, no escape processing,
    expansion or substitution), held to what set_credential.py writes: no space after '=', an unquoted value in
    its BARE_VALUE, a quoted one accepted by its encode(), and a single-quoted one without a single quote."""
    declared = entry["variables"] + entry["optional_variables"]
    values = {}
    for number, raw in enumerate(data.split(b"\n"), 1):
        for byte in raw:
            if byte >= 0x80:
                raise Refused(f"line {number}: not_ascii", "unsafe")
            if byte < 0x20 or byte == 0x7F:
                raise Refused(f"line {number}: control_character", "unsafe")
        line = raw.decode("ascii").strip(" ")
        if not line or line.startswith("#"):
            continue
        match = LINE.fullmatch(line)
        if match is None:
            raise Refused(f"line {number}: not_an_export_line", "unsafe")
        name, value = match.groups()
        if name not in declared:  # not repeated: a value pasted where a name belongs matches the name pattern
            raise Refused(f"line {number}: undeclared_variable", "unsafe")
        if name in values:
            raise Refused(f"line {number}: duplicate_variable", "unsafe")
        quote = value[0] if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"" else ""
        if quote:
            value = value[1:-1]
        if not value:
            raise Refused(f"line {number}: empty_value", "unsafe")
        if not in_writer_grammar(name, value, quote):
            raise Refused(f"line {number}: outside_writer_grammar", "unsafe")
        values[name] = value
    return values


def in_writer_grammar(name: str, value: str, quote: str) -> bool:
    if not quote:
        return writer.BARE_VALUE.match(value) is not None
    if quote == "'" and "'" in value:
        return False
    try:
        writer.encode(name, value)
    except writer.Refused:
        return False
    return True


def require(entry: dict, values: dict) -> None:
    for name in entry["variables"]:
        if name not in values:
            raise Refused(f"required_variable_missing: {name}", "missing", TERMINAL_HINT.format(entry["id"]))
    for name in masked_names(entry):
        if name in values and len(values[name].encode("ascii")) < LENGTH_MIN:
            raise Refused(f"value_too_short_to_mask: {name}", "unsafe")


def child_environment(inventory: dict, entry: dict, injected: dict, env) -> dict:
    """The caller's environment minus every inventory variable, must_not_be_set name and pointer variable, and plus
    injected.

    A pointer variable holds the path of an entry's store file (PAPER_ENV_FILE, SEC_CONTACT_ENV, ...), which a command
    could load. Only the selected entry's own pointers stay, as the paper units' `--env-file` pointer does."""
    removed = set(inventory["must_not_be_set"])
    pointers = set()
    for other in inventory["entries"]:
        removed.update(other["variables"], other["optional_variables"])
        pointers.update(other["pointer_variables"])
    removed |= pointers - set(entry["pointer_variables"])
    child = {name: value for name, value in env.items() if name not in removed}
    child.update(injected)
    return child


def encoded_forms(value: bytes) -> list:
    """value and the encodings a careless command prints it in."""
    text = value.decode("ascii")
    forms = [value]
    for altchars in (None, b"-_"):  # base64 and base64url
        for align in (0, 1, 2):
            encoded = base64.b64encode(b"\0" * align + value, altchars=altchars)
            # Only the stable interior: the characters that depend on value alone at this byte alignment.
            forms.append(encoded[(0, 2, 3)[align]:(8 * (align + len(value))) // 6])
    # Percent forms, %XX in both cases: quote() keeps "/" unless told otherwise (its default safe="/") and writes a
    # space as %20, quote_plus() escapes "/" (safe="") and writes a space as "+"; both safe sets, both functions.
    for quote in (urllib.parse.quote, urllib.parse.quote_plus):
        for safe in ("", "/"):
            upper = quote(text, safe=safe).encode("ascii")
            forms += [upper, re.sub(rb"%[0-9A-F]{2}", lambda match: match.group(0).lower(), upper)]
    # JSON string forms: Python's json.dumps escapes only quotes, backslashes and controls; PHP's json_encode also
    # writes "/" as "\/"; Go's encoding/json writes < > & as \u003c \u003e \u0026 (PHP's JSON_HEX_TAG writes
    # \u003C \u003E). Every combination is a needle; a value without those characters collapses to one.
    plain = json.dumps(text)[1:-1]
    for base in (plain, plain.replace("/", "\\/")):
        for hex_case in (str.lower, str.upper, None):
            escaped = base if hex_case is None else (base.replace("<", "\\u003" + hex_case("c"))
                                                      .replace(">", "\\u003" + hex_case("e")).replace("&", "\\u0026"))
            forms.append(escaped.encode("ascii"))
    forms += [value.hex().encode("ascii"), value.hex().upper().encode("ascii")]
    return forms


def needles_for(values: dict, masked: list) -> list:
    """(needle, name) pairs for the masked values, deduplicated, none shorter than LENGTH_MIN, longest first."""
    needles, seen = [], set()
    for name in masked:
        if name in values:
            for form in encoded_forms(values[name].encode("ascii")):
                if len(form) >= LENGTH_MIN and form not in seen:
                    seen.add(form)
                    needles.append((form, name))
    return sorted(needles, key=lambda item: len(item[0]), reverse=True)


class Masker:
    """Masks the needles in one byte stream. A suffix that could still grow into a needle is held back."""

    def __init__(self, needles):
        self.needles = sorted(needles, key=lambda item: len(item[0]), reverse=True)
        self.buf = b""
        self.emitted = 0  # leading bytes of buf already written: a short tail flushed on the idle timer
        self.last = 0.0

    def _ranges(self) -> list:
        """Every complete match, overlapping ones merged; each range is named after its longest earliest match."""
        found = []
        for needle, name in self.needles:
            at = self.buf.find(needle)
            while at != -1:
                found.append((at, at + len(needle), name))
                at = self.buf.find(needle, at + 1)
        merged = []
        for start, end, name in sorted(found, key=lambda match: (match[0], match[0] - match[1])):
            if merged and start <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], end)
            else:
                merged.append([start, end, name])
        return merged

    def _held(self) -> tuple:
        """The longest suffix of buf that is a proper prefix of a needle: its length and that needle's name."""
        longest, owner = 0, ""
        for needle, name in self.needles:
            for length in range(min(len(self.buf), len(needle) - 1), longest, -1):
                if needle.startswith(self.buf[-length:]):
                    longest, owner = length, name
                    break
        return longest, owner

    def _boundary(self, ranges: list, held: int) -> int:
        """Where writing may stop: where the held tail starts, or the end of a complete match that runs into it."""
        boundary = len(self.buf) - held
        for start, end, _name in ranges:  # sorted, and touching ranges are merged: one pass is enough
            if start < boundary < end:
                boundary = end  # a match is written whole; its bytes past the tail's start stay in buf, as written
        return boundary

    def _render(self, stop: int, ranges: list) -> bytes:
        out, at = [], self.emitted
        for start, end, name in ranges:
            if end <= at or start >= stop:
                continue
            # A match that began in bytes already written (a flushed short tail) is masked from here on.
            out += [self.buf[at:max(start, at)], b"[REDACTED:" + name.encode("ascii") + b"]"]
            at = end
        out.append(self.buf[at:stop])
        return b"".join(out)

    def feed(self, data: bytes, now: float) -> bytes:
        """Write everything that no later byte can change and keep only the tail that could still begin a needle: at
        most the longest needle minus one byte, however long a run of overlapping matches is (a match that runs into
        that tail is written whole, so a long run may come out as several markers, and the bytes of it that stay
        in buf count as written). Anything longer than the tail is never re-scanned."""
        self.buf += data
        self.last = now
        ranges = self._ranges()
        held = self._held()[0]
        stop = self._boundary(ranges, held)
        out = self._render(stop, ranges) if stop > self.emitted else b""
        keep = len(self.buf) - held
        self.buf, self.emitted = self.buf[keep:], max(stop, self.emitted) - keep
        return out

    def idle_due(self):
        """When the held tail may be written: only a tail of SHORT_TAIL_MAX bytes or less, never a longer one."""
        if self.emitted < len(self.buf) <= SHORT_TAIL_MAX:
            return self.last + IDLE_FLUSH_SECONDS
        return None

    def idle_flush(self) -> bytes:
        out = self.buf[self.emitted:]
        self.emitted = len(self.buf)  # kept, so the rest of a value that arrives later is still masked
        return out

    def close(self) -> bytes:
        """The stream ended (EOF, the command killed, or the drain bound): a held tail of more than SHORT_TAIL_MAX
        bytes becomes a partial marker and is never printed; a shorter one is written as the idle timer would."""
        ranges = self._ranges()
        held, owner = self._held()
        stop = self._boundary(ranges, held)
        out = self._render(stop, ranges) if stop > self.emitted else b""
        start = max(stop, self.emitted)
        if start < len(self.buf):
            if held <= SHORT_TAIL_MAX:
                out += self.buf[start:]
            else:
                out += b"[REDACTED-PARTIAL:" + (owner or "VALUE").encode("ascii") + b"]"
        self.buf, self.emitted = b"", 0
        return out


def write_out(fd: int, data: bytes) -> bool:
    """Write all of data, waiting for room; False once the reader is gone (EPIPE) or the descriptor is closed."""
    view = memoryview(data)
    while view:
        try:
            written = os.write(fd, view)
        except BlockingIOError:  # a terminal or file that someone else made non-blocking
            select.select([], [fd], [])
            continue
        except OSError:
            return False
        view = view[written:]
    return True


class Sink:
    """One of the runner's own output descriptors (1 or 2) and the masked bytes waiting to be written to it.

    A pipe or a socket is made non-blocking for the relay and put back afterwards, so a consumer that stops reading
    cannot stall the runner: what does not fit waits in a queue (the relay stops reading the command's pipe once it
    holds QUEUE_LIMIT bytes) and is dropped, never waited for, when the runner is shutting down or the drain deadline
    passes. Dropping is safe: only masked bytes are ever queued. A terminal, a regular file or /dev/null is written
    directly, since it cannot wait on a reader that never comes, and so is a descriptor that shares its open file
    description with the command's stdin (stdin_identity is that inode): the flag must not change under the command."""

    def __init__(self, fd: int, stdin_identity=None):
        self.fd, self.queue, self.size = fd, collections.deque(), 0
        self.dead = False      # the consumer is gone (EPIPE): nothing more is written
        self.dropping = False  # shutting down: nothing waits in the queue
        self.polled = False    # non-blocking: the relay's selector watches when it can be written
        self.flipped = False   # this sink made it non-blocking, so it puts it back
        try:
            info = os.fstat(fd)
        except OSError:
            self.dead = True
            return
        if (stat.S_ISFIFO(info.st_mode) or stat.S_ISSOCK(info.st_mode)) \
                and (info.st_dev, info.st_ino) != stdin_identity:
            with contextlib.suppress(OSError):
                if os.get_blocking(fd):
                    os.set_blocking(fd, False)
                    self.flipped = True
                self.polled = True

    def full(self) -> bool:
        return self.size >= QUEUE_LIMIT

    def clear(self) -> None:
        self.queue.clear()
        self.size = 0

    def abandon(self) -> None:
        """Drop what is queued and queue nothing more: a shutdown signal arrived, or the drain deadline passed."""
        self.dropping = True
        self.clear()

    def put(self, data: bytes) -> None:
        if not data or self.dead:
            return
        if not self.polled:
            if not write_out(self.fd, data):
                self.dead = True
            return
        self.queue.append(data)
        self.size += len(data)
        self.flush()
        if self.dropping:
            self.clear()

    def flush(self) -> None:
        """Write what the consumer takes now; the rest stays queued."""
        while self.queue and not self.dead:
            chunk = self.queue[0]
            try:
                written = os.write(self.fd, chunk)
            except BlockingIOError:
                return
            except OSError:
                self.dead = True
                self.clear()
                return
            self.size -= written
            if written < len(chunk):
                self.queue[0] = chunk[written:]
                return
            self.queue.popleft()

    def demote(self) -> None:
        """The selector cannot watch this descriptor: write to it directly from now on (blocking, as for a file)."""
        self.restore()
        self.polled = False
        queued = b"".join(self.queue)
        self.clear()
        self.put(queued)

    def restore(self) -> None:
        if self.flipped:
            with contextlib.suppress(OSError):
                os.set_blocking(self.fd, True)
            self.flipped = False


def relay(child, needles, shutdown=()) -> None:
    """Relay both pipes through a Masker each until EOF, or DRAIN_SECONDS after the command exited.

    Output goes through a Sink each, so a consumer that stops reading cannot hold the runner: the relay stops reading
    a pipe while its queue is full (the command waits, as in any pipeline), and drops what is queued, then
    and later, once a shutdown signal has arrived (shutdown is not empty) or the drain deadline has passed."""
    selector = selectors.DefaultSelector()
    stdin = os.fstat(0)
    streams, sinks, watched = {}, [], {}
    for pipe, target in ((child.stdout, 1), (child.stderr, 2)):
        sinks.append(Sink(target, (stdin.st_dev, stdin.st_ino)))
        streams[pipe] = (Masker(needles), sinks[-1])
    by_fd = {sink.fd: sink for sink in sinks}

    def watch(fileobj, mask: int) -> None:
        """Register fileobj for exactly these events (0: none)."""
        current = watched.get(fileobj, 0)
        if mask == current:
            return
        if not mask:
            selector.unregister(fileobj)
            del watched[fileobj]
        elif current:
            selector.modify(fileobj, mask)
            watched[fileobj] = mask
        else:
            selector.register(fileobj, mask)
            watched[fileobj] = mask

    def finish(pipe, final: bytes) -> None:
        streams[pipe][1].put(final)
        watch(pipe, 0)
        pipe.close()  # a command still writing gets EPIPE: its reader is gone, as in any pipeline
        del streams[pipe]

    drain_until = None
    try:
        while streams or any(sink.queue for sink in sinks):
            now = time.monotonic()
            if drain_until is None and child.poll() is not None:
                drain_until = now + DRAIN_SECONDS
            if shutdown:
                for sink in sinks:
                    sink.abandon()
            for pipe, (_masker, sink) in streams.items():
                watch(pipe, selectors.EVENT_READ if shutdown or not sink.full() else 0)
            for sink in sinks:
                try:
                    watch(sink.fd, selectors.EVENT_WRITE if sink.polled and sink.queue else 0)
                except OSError:
                    sink.demote()
            wake = [due for due in (masker.idle_due() for masker, _sink in streams.values()) if due is not None]
            wake.append(drain_until if drain_until is not None else now + POLL_SECONDS)
            for key, _events in selector.select(max(0.0, min(wake) - now)):
                if key.fileobj in streams:
                    masker, sink = streams[key.fileobj]
                    data = os.read(key.fd, READ_SIZE)
                    if not data:
                        finish(key.fileobj, masker.close())
                    else:
                        sink.put(masker.feed(data, time.monotonic()))
                else:
                    by_fd[key.fd].flush()
            now = time.monotonic()
            for pipe, (masker, sink) in list(streams.items()):
                due = masker.idle_due()
                if due is not None and due <= now:
                    sink.put(masker.idle_flush())
                if sink.dead:
                    finish(pipe, b"")  # its reader is gone: the command gets EPIPE, as in any pipeline
            if drain_until is not None and now >= drain_until:
                for pipe, (masker, _sink) in list(streams.items()):
                    finish(pipe, masker.close())
                for sink in sinks:
                    sink.flush()  # one last try; what the consumer still will not take is dropped
                    sink.abandon()
    finally:
        for pipe in list(streams):
            pipe.close()
        selector.close()
        for sink in sinks:
            sink.restore()


def ensure_standard_descriptors() -> None:
    """Reopen a closed stdin, stdout or stderr on /dev/null, so that no pipe of the command takes its number."""
    for fd in (0, 1, 2):
        try:
            os.fstat(fd)
        except OSError:
            opened = os.open(os.devnull, os.O_RDWR)
            if opened != fd:
                os.dup2(opened, fd)
                os.close(opened)
            os.set_inheritable(fd, True)  # os.open's descriptor is close-on-exec: the command would get EBADF, not EOF


def check_core_pattern(path=None) -> None:
    """Refuse a host whose kernel hands a crashing process to a collector: RLIMIT_CORE 0 stops a core file, not that.

    The kernel sets the limit aside for a pattern that begins `|` (a program: systemd-coredump, apport) and for one that
    begins `@` (a core socket): torvalds/linux@v6.16 fs/coredump.c L795-820 and L242-243 and L919. systemd-coredump
    then declines to store a core when the limit is 0 but still journals the process environment, COREDUMP_ENVIRON
    (systemd/systemd@v257 src/coredump/coredump.c L472-479 and L1458-1459). There is no override. A file that does not
    exist (macOS, no /proc) skips the check; one that cannot be read is refused. The message names the file, never
    what it holds. Only the pattern is read: a debugger, ptrace or /proc reads by the same uid are out of scope."""
    path = CORE_PATTERN_FILE if path is None else path
    where = "inspect " + CORE_PATTERN_FILE
    try:
        with open(path, "rb") as handle:
            first = handle.read(1)
    except (FileNotFoundError, NotADirectoryError):
        return
    except OSError:
        raise Refused(f"core_pattern_unreadable: cannot read {CORE_PATTERN_FILE}; inspect that file") from None
    if first == b"|":
        raise Refused(f"core_pattern_pipe: this host sends crash dumps to a program; {where}")
    if first == b"@":
        raise Refused(f"core_pattern_socket: this host sends crash dumps to a socket; {where}")


def disable_core_dumps() -> None:
    """RLIMIT_CORE 0 for this process and, inherited, for the command: no core file ever holds a value. A host whose
    core_pattern hands dumps to a collector is refused first, and so is a limit that cannot be set."""
    check_core_pattern()
    try:
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    except (ValueError, OSError):
        raise Refused("core_limit_not_set: could not set RLIMIT_CORE to 0") from None


def parent_death_hook():
    """A preexec_fn that asks the kernel to send the command SIGTERM when the runner ends, or None where it cannot (not
    Linux, no ctypes, no prctl): the start never fails for it.

    prctl(PR_SET_PDEATHSIG) (man7.org PR_SET_PDEATHSIG(2const)) is the only thing that acts when the runner is killed
    with SIGKILL, which runs no code of ours. The "parent" is the thread that forked the command: here the main thread,
    because run_command's signal.signal calls raise anywhere else, and its end is the runner's end. The kernel clears
    the setting for the command's own children, so it reaches the command alone. A runner that ended before the call is
    noticed by its pid, and the command then ends before it runs."""
    if not sys.platform.startswith("linux"):
        return None
    try:
        import ctypes
        prctl = ctypes.CDLL(None, use_errno=True).prctl
        prctl.argtypes = [ctypes.c_int] + [ctypes.c_ulong] * 4
        prctl.restype = ctypes.c_int
    except (ImportError, OSError, AttributeError):
        return None
    runner, sigterm = os.getpid(), int(signal.SIGTERM)

    def hook() -> None:  # runs in the forked command, between fork and exec
        try:
            if prctl(PR_SET_PDEATHSIG, sigterm, 0, 0, 0) == 0 and os.getppid() != runner:
                os._exit(128 + sigterm)  # the runner is already gone: nothing would end this command later
        except Exception:  # never fail the start for this
            pass

    return hook


def group_exists(pgid: int) -> bool:
    """Whether any member of the process group is left to signal (a zombie counts until it is reaped)."""
    try:
        os.killpg(pgid, 0)
    except OSError:  # no member, or none this user may signal
        return False
    return True


def wait_for_group(child, seconds: float) -> bool:
    """True once the command's process group is empty, False after `seconds`; reaps the command meanwhile."""
    deadline = time.monotonic() + seconds
    while True:
        child.poll()  # a command that exited but was not reaped is still a member of its group
        if not group_exists(child.pid):
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.02)


def end_group(child) -> None:
    """SIGTERM to the command's process group, SIGKILL to what is left after TERM_GRACE_SECONDS, and reap the command.

    The command leads its own group (start_new_session), so this reaches every descendant that stayed in it, and does
    nothing but reap when none is left. run_command calls it on every way out. A descendant that left the group (setsid
    or setpgid) is out of reach. The same order as bazelbuild/bazel@d2545923 src/main/tools/process-tools.cc
    KillEverything (L94-110: SIGTERM to -pgrp, a timeout, SIGKILL to -pgrp)."""
    for signum, seconds in ((signal.SIGTERM, TERM_GRACE_SECONDS), (signal.SIGKILL, KILL_WAIT_SECONDS)):
        try:
            os.killpg(child.pid, signum)
        except OSError:  # no member left, or none that this user may signal
            break
        if wait_for_group(child, seconds):
            break
    with contextlib.suppress(subprocess.TimeoutExpired):
        child.wait(timeout=KILL_WAIT_SECONDS)


WATCHDOG = True  # a test launcher switches it off, to see the parent-death signal alone; there is no environment switch
# The watchdog is a second interpreter, started right after the command, that holds a pipe and the number of the
# command's process group and nothing else (an empty environment: no key). The runner keeps the pipe's write end open
# for as long as it lives, so when it dies by any signal (SIGKILL, the OOM killer) the kernel closes it and the watchdog
# reads end of file: it ends the group, SIGTERM first and SIGKILL after the grace. A runner that ends in order writes
# one byte first, and the watchdog leaves the group alone. It ignores the signals a harness sends a group or a terminal
# and lives in its own session, so a group-wide kill of the runner does not reach it. Exit status: 0 when told, 1 after
# acting on end of file. It follows CPython's multiprocessing resource tracker, a helper that waits for the end of a
# pipe and ignores SIGINT and SIGTERM (python/cpython@v3.13.15 Lib/multiprocessing/resource_tracker.py L8, L246-267
# and L425-429).
WATCHDOG_CODE = """\
import os, signal, sys, time
pgid, grace = int(sys.argv[1]), float(sys.argv[2])
for name in ("SIGINT", "SIGTERM", "SIGHUP", "SIGQUIT", "SIGUSR1", "SIGUSR2", "SIGALRM"):
    signal.signal(getattr(signal, name), signal.SIG_IGN)
try:
    told = os.read(0, 1)
except OSError:
    told = b""
if told:
    sys.exit(0)
for sig, seconds in ((signal.SIGTERM, grace), (signal.SIGKILL, 1.0)):
    try:
        os.killpg(pgid, sig)
    except OSError:
        break
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        try:
            os.killpg(pgid, 0)
        except OSError:
            sys.exit(1)
        time.sleep(0.02)
sys.exit(1)
"""


class Watchdog:
    """The runner's end of the watchdog: started after the command, told when the runner ends in order.

    It cannot fail the run. A watchdog that cannot start leaves the parent-death signal and the group kill at the end of
    run_command. Its pipe is made after the command starts, and is not inheritable, so nothing the command starts can
    hold the write end open and keep the watchdog from seeing the runner die."""

    def __init__(self, pgid: int):
        self.process, self.pipe = None, -1
        if not WATCHDOG or not sys.executable:
            return
        try:
            read, self.pipe = os.pipe()
        except OSError:
            return
        try:
            self.process = subprocess.Popen(
                [sys.executable, "-I", "-S", "-c", WATCHDOG_CODE, str(pgid), str(TERM_GRACE_SECONDS)],
                stdin=read, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env={}, close_fds=True,
                start_new_session=True)
        except (OSError, ValueError):
            self.close_pipe()
        finally:
            os.close(read)

    def close_pipe(self) -> None:
        if self.pipe >= 0:
            with contextlib.suppress(OSError):
                os.close(self.pipe)
            self.pipe = -1

    def release(self) -> None:
        """The runner ends in order: tell the watchdog, and wait for it, so that none is left behind."""
        if self.pipe >= 0:
            with contextlib.suppress(OSError):
                os.write(self.pipe, b".")
            self.close_pipe()
        if self.process is not None:
            try:
                self.process.wait(timeout=KILL_WAIT_SECONDS)
            except subprocess.TimeoutExpired:
                self.process.kill()
                with contextlib.suppress(subprocess.TimeoutExpired):
                    self.process.wait(timeout=KILL_WAIT_SECONDS)


def run_command(command: list, environment: dict, needles: list) -> int:
    started, pending, shutdown = [], [], []

    def forward(signum, _frame) -> None:
        if signum in SHUTDOWN_SIGNALS:
            shutdown.append(signum)  # the relay stops waiting for a consumer that is not reading
        if not started:
            pending.append(signum)
            return
        child = started[0]
        try:
            os.killpg(child.pid, signum)  # the command leads its own session and process group
        except ProcessLookupError:
            if child.returncode is None:  # not reaped, so the pid cannot have been reused
                with contextlib.suppress(ProcessLookupError):
                    os.kill(child.pid, signum)
        except PermissionError:
            pass

    for signum in FORWARDED:
        signal.signal(signum, forward)
    try:
        child = subprocess.Popen(command, env=environment, stdin=None, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, close_fds=True, start_new_session=True,
                                 preexec_fn=parent_death_hook())
    except FileNotFoundError:
        raise SpawnError(127, "not_found") from None
    except PermissionError:
        raise SpawnError(126, "not_executable") from None
    except OSError:
        raise SpawnError(126, "cannot_execute") from None
    started.append(child)
    watchdog = None
    try:
        watchdog = Watchdog(child.pid)
        for signum in pending:
            forward(signum, None)
        relay(child, needles, shutdown)
        code = child.wait()
    finally:
        try:
            end_group(child)  # on every way out: no descendant is left running with the key in its environment
        finally:
            if watchdog is not None:
                watchdog.release()
    return code if code >= 0 else 128 - code


def parse_args(argv: list):
    """(id, only, check, command), or None for --help."""
    if not argv:
        raise UsageError("missing <inventory-id>")
    if argv[0] in ("-h", "--help"):
        return None
    entry_id, rest = argv[0], list(argv[1:])
    if not ID.fullmatch(entry_id):
        raise UsageError("invalid <inventory-id>: lowercase letters, digits and '-' only")
    only, check, command, separated = [], False, [], False
    while rest:
        word = rest.pop(0)
        if word == "--":
            separated, command = True, rest
            break
        if word == "--only":
            if not rest:
                raise UsageError("--only needs a variable name")
            only.append(rest.pop(0))
        elif word == "--check":
            check = True
        elif word in ("-h", "--help"):
            return None
        else:
            raise UsageError("unknown option before --; the command goes after --")
    if check and separated:
        raise UsageError("--check starts no command; drop the part from --")
    if not check and not separated:
        raise UsageError("missing -- before the command")
    if not check and not command:
        raise UsageError("empty command after --")
    return entry_id, only, check, command


def _main(argv: list, shown: list) -> int:
    request = parse_args(argv)
    if request is None:
        print(USAGE)
        return 0
    entry_id, only, check, command = request
    ensure_standard_descriptors()
    inventory = load_inventory()
    entry = find_entry(entry_id, inventory)
    shown.append(entry_id)
    declared = entry["variables"] + entry["optional_variables"]
    try:
        check_injectable(entry)
        if [name for name in only if name not in declared]:  # the unknown word is not repeated
            raise UsageError("--only names a variable this entry does not declare; it declares "
                             + ", ".join(declared))
        disable_core_dumps()
        values = parse(entry_id, read_store(entry, os.environ, os.getuid()), entry)
        require(entry, values)
        absent = [name for name in only if name not in values]
        if absent:
            raise Refused("only_variable_absent: " + ", ".join(absent))
        names = [name for name in declared if name in values and (not only or name in only)]
        if not names:
            raise Refused("nothing_to_inject")
    except Refused as refusal:
        if not check:
            raise
        print(f"{entry_id}: {refusal.state} ({refusal.detail})" + (f"; {refusal.hint}" if refusal.hint else ""))
        return 1
    public = set(public_names(entry))
    if check:
        print(f"{entry_id}: ok; would inject "
              + ", ".join(f"{name} ({'public' if name in public else 'masked'})" for name in names))
        return 0
    environment = child_environment(inventory, entry, {name: values[name] for name in names}, os.environ)
    return run_command(command, environment, needles_for(values, [n for n in names if n not in public]))


def _say(text: str) -> None:
    with contextlib.suppress(Exception):
        sys.stderr.write(text + "\n")
        sys.stderr.flush()


def main(argv: list) -> int:
    shown = []  # the id, once it names an inventory entry; an unknown id is never repeated
    prefix = "credential_run: "
    try:
        return _main(argv, shown)
    except UsageError as error:
        _say(f"{prefix}usage error: {error}\n{USAGE}")
        return 2
    except Refused as refusal:
        where = f"{prefix}{shown[0]}: " if shown else prefix
        _say(f"{where}{refusal.state}: {refusal.detail}" + (f"; {refusal.hint}" if refusal.hint else ""))
        return 1
    except SpawnError as error:
        _say(f"{prefix}{shown[0]}: cannot start the command ({error.reason})")
        return error.code
    except KeyboardInterrupt:
        _say(f"{prefix}cancelled")
        return 130
    except Exception as error:  # no traceback and no message: either could quote whatever was being handled
        where = f"{prefix}{shown[0]}: " if shown else prefix
        _say(f"{where}unexpected {type(error).__name__} (internal_error); no value was printed")
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
