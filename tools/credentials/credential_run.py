#!/usr/bin/env python3
"""Run one command with one inventory entry's keys in its environment, and mask those keys in its output.

    python3 tools/credentials/credential_run.py <inventory-id> [--only NAME]... -- <command> [args...]
    python3 tools/credentials/credential_run.py <inventory-id> --check
    python3 tools/credentials/credential_run.py --help

The entry's 0600 file in the per-host store is read by inventory id (adoption/credential-inventory.json). The
command gets the caller's environment minus every inventory variable and must_not_be_set name, plus only this
entry's declared variables (narrowed by --only). No value goes into argv, a temporary file, a socket or a shell.
The command's stdout and stderr are relayed through pipes with each injected value, raw or in a common encoding,
replaced by [REDACTED:<NAME>]; names the entry lists in public_variables (a base URL) are injected unmasked.
`--check` starts nothing and prints the names it would inject and the file state (ok, missing or unsafe). There is
no subcommand that prints, lists or returns a value, and there never will be.

Masking is accident-proofing, not a boundary: a command that transforms a value (reverses it, encrypts it, prints a
fragment such as its first eight characters) or writes it to a file or a log defeats it, and stdout and stderr are
masked separately. Exit status: the command's own; 128+N when it died of signal N; 2 for a usage error; 1 for a
refusal; 126 or 127 when it cannot start. Messages carry the id, variable names, line numbers and reason codes,
never a value, a store line or a path (docs/secret-storage.md#using-a-key).

Built from these references (observed 2026-09-29): the env-only exec discipline of scripts/kernel_keyring.py; the
load_env_file grammar of blueprints/us-equities/pit-availability/measure.py:51-67 with set_credential.py's value
grammar; dotenvx/dotenvx@278101db src/lib/helpers/redactOutput.js (longest first L4-9, held partial tail L36-50,
never cutting a match L52-72); actions/runner@15231bed src/Sdk/DTLogging/Logging/ValueEncoders.cs (base64 at
shifted alignments L16-39 and L146-159, JSON escape L52-58, URI data escape L60-63) and SecretMasker.cs (merged
overlaps L255-279); buildkite/agent@3345ee60 internal/redact/redact.go (LengthMin 6, L20-25) and
internal/replacer/replacer.go (buffer, merge, never spill a partial match, L99-115); dmno-dev/varlock@1b880652
packages/varlock/src/runtime/lib/redact-stream.ts (100 ms idle flush, L8 and L34-46); Generalized-Labs/ironrun@b611c7ce
internal/redact/encodings.go (hex and upper- and lower-case percent forms, L13-21).
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
import contextlib  # noqa: E402
import json  # noqa: E402
import re  # noqa: E402
import resource  # noqa: E402
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
DRAIN_SECONDS = 2.0          # after the command exits, how long a descendant may keep a pipe open
POLL_SECONDS = 0.1
READ_SIZE = 65536
CORE_PATTERN_FILE = "/proc/sys/kernel/core_pattern"  # a name, never a value, in the messages that mention it
FORWARDED = (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)


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


def child_environment(inventory: dict, injected: dict, env) -> dict:
    """The caller's environment minus every inventory variable and must_not_be_set name, plus injected."""
    removed = set(inventory["must_not_be_set"])
    for entry in inventory["entries"]:
        removed.update(entry["variables"], entry["optional_variables"])
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
    for quote in (urllib.parse.quote, urllib.parse.quote_plus):  # no safe characters; %XX in both cases
        upper = quote(text, safe="").encode("ascii")
        forms += [upper, re.sub(rb"%[0-9A-F]{2}", lambda match: match.group(0).lower(), upper)]
    forms.append(json.dumps(text)[1:-1].encode("ascii"))
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
        boundary, moved = len(self.buf) - held, True
        while moved:  # never cut through a complete match: hold it with the tail
            moved = False
            for start, end, _name in ranges:
                if start < boundary < end:
                    boundary, moved = start, True
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
        self.buf += data
        self.last = now
        ranges = self._ranges()
        stop = self._boundary(ranges, self._held()[0])
        if stop <= self.emitted:
            return b""
        out = self._render(stop, ranges)
        self.buf, self.emitted = self.buf[stop:], 0
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
            if len(self.buf) - stop <= SHORT_TAIL_MAX:
                out += self.buf[start:]
            else:
                out += b"[REDACTED-PARTIAL:" + (owner or "VALUE").encode("ascii") + b"]"
        self.buf, self.emitted = b"", 0
        return out


def write_out(fd: int, data: bytes) -> bool:
    """Write all of data; False once the reader is gone (EPIPE) or the descriptor is closed."""
    view = memoryview(data)
    while view:
        try:
            written = os.write(fd, view)
        except OSError:
            return False
        view = view[written:]
    return True


def relay(child, needles) -> None:
    """Relay both pipes through a Masker each until EOF, or DRAIN_SECONDS after the command exited."""
    selector = selectors.DefaultSelector()
    streams = {}
    for pipe, target in ((child.stdout, 1), (child.stderr, 2)):
        selector.register(pipe, selectors.EVENT_READ)
        streams[pipe] = (Masker(needles), target)

    def finish(pipe, final: bytes) -> None:
        write_out(streams[pipe][1], final)
        selector.unregister(pipe)
        pipe.close()  # a command still writing gets EPIPE: its reader is gone, as in any pipeline
        del streams[pipe]

    drain_until = None
    try:
        while streams:
            now = time.monotonic()
            if drain_until is None and child.poll() is not None:
                drain_until = now + DRAIN_SECONDS
            wake = [due for due in (masker.idle_due() for masker, _target in streams.values()) if due is not None]
            wake.append(drain_until if drain_until is not None else now + POLL_SECONDS)
            for key, _events in selector.select(max(0.0, min(wake) - now)):
                masker, target = streams[key.fileobj]
                data = os.read(key.fd, READ_SIZE)
                if not data:
                    finish(key.fileobj, masker.close())
                elif not write_out(target, masker.feed(data, time.monotonic())):
                    finish(key.fileobj, b"")
            now = time.monotonic()
            for pipe, (masker, target) in list(streams.items()):
                due = masker.idle_due()
                if due is not None and due <= now and not write_out(target, masker.idle_flush()):
                    finish(pipe, b"")
            if drain_until is not None and now >= drain_until:
                for pipe, (masker, _target) in list(streams.items()):
                    finish(pipe, masker.close())
    finally:
        for pipe in list(streams):
            pipe.close()
        selector.close()


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


def run_command(command: list, environment: dict, needles: list) -> int:
    started, pending = [], []

    def forward(signum, _frame) -> None:
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
                                 stderr=subprocess.PIPE, close_fds=True, start_new_session=True)
    except FileNotFoundError:
        raise SpawnError(127, "not_found") from None
    except PermissionError:
        raise SpawnError(126, "not_executable") from None
    except OSError:
        raise SpawnError(126, "cannot_execute") from None
    started.append(child)
    for signum in pending:
        forward(signum, None)
    relay(child, needles)
    code = child.wait()
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
    environment = child_environment(inventory, {name: values[name] for name in names}, os.environ)
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
