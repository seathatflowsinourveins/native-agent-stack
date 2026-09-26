#!/usr/bin/env python3
"""Keep an API key in the Linux kernel user keyring (memory only) and hand it to one command.

  kernel_keyring.py store [--replace] <name>              read the value from stdin and store it
  kernel_keyring.py status <name>                         print present/absent (never the value)
  kernel_keyring.py exec <name> <ENV_VAR> -- <cmd...>     run cmd with ENV_VAR set to the value, only for that child
  kernel_keyring.py revoke <name>                         revoke the key and unlink it

`store` reads the value from stdin: run it in a terminal and paste at the prompt, which turns echo off
first, or pipe it in. It refuses a name that is already stored unless --replace, which revokes the old
key before storing the new one; it checks again after the value was read, under a per-uid lock that
`revoke` also takes, so two stores running at once cannot both succeed without --replace. The value is
stripped of surrounding whitespace and may not contain a control character or line break. `exec` puts
the value into the environment of that one child only (os.execvpe; never on a command line). ENV_VAR
must be a credential variable name, [A-Z_][A-Z0-9_]* ending in KEY, KEY_ID, TOKEN, SECRET, PASSWORD or
PASSPHRASE (such as TAVILY_API_KEY), and not one the dynamic loader or Python reads (LD_*, DYLD_*,
PYTHON*): a program that interprets a variable at startup can print its value in an error message.

The key lives in the calling user's user keyring (KEY_SPEC_USER_KEYRING) as type "user" with the
description "native-agent-stack:<name>": readable by every process of this uid on this kernel, gone when
the kernel restarts (for WSL2: `wsl --shutdown`, a Windows restart, or the VM stopping), and never
written to a file by this script. Permissions 0x3F0B0000: possessor all, same-uid user view/read/search,
nobody else. This script never prints or logs the value; messages name the key or an errno, never its
content, and no traceback is printed. The command that `exec` starts can print it, so give `exec` only
commands that use the key without printing it. Linux only (x86_64 and aarch64 syscall numbers); on
macOS use the login Keychain instead (docs/secret-storage.md).
"""
from __future__ import annotations

import os
import sys

if __name__ == "__main__" and not sys.flags.isolated:
    # Re-run isolated (-I), as tools/credentials/set_credential.py does: PYTHONPATH, PYTHONSTARTUP and
    # user site-packages cannot shadow a module this tool imports or hook its error output.
    os.execv(sys.executable, [sys.executable, "-I", os.path.abspath(__file__), *sys.argv[1:]])

import contextlib  # noqa: E402
import ctypes  # noqa: E402
import errno  # noqa: E402
import platform  # noqa: E402
import re  # noqa: E402
import socket  # noqa: E402
import time  # noqa: E402

SYSCALLS = {"x86_64": (248, 250), "aarch64": (217, 219)}  # (add_key, keyctl)
KEY_SPEC_PROCESS_KEYRING, KEY_SPEC_USER_KEYRING = -2, -4
KEYCTL_REVOKE, KEYCTL_SETPERM, KEYCTL_LINK, KEYCTL_UNLINK = 3, 5, 8, 9
KEYCTL_SEARCH, KEYCTL_READ, KEYCTL_INVALIDATE = 10, 11, 21
PERM = 0x3F0B0000  # possessor: all; user: view|read|search; group/other: none
PREFIX = "native-agent-stack:"
MAX_VALUE_BYTES = 32767  # the kernel's limit for a "user" key payload
LOCK_WAIT_SECONDS = 10.0
# Lowercase only: a pasted API key almost always has an uppercase letter, so it is refused as a name.
NAME = re.compile(r"[a-z0-9][a-z0-9_.-]{0,63}")
ENV_NAME = re.compile(r"[A-Z_][A-Z0-9_]*")
# `exec` sets only a credential variable, the kind a provider SDK reads. A variable that a program
# interprets at startup can make it print the value: measured with a canary on 2026-09-26, Python
# printed PYTHONWARNINGS, PYTHONHOME and PYTHONIOENCODING values, bash LC_ALL, tput TERM and git
# GIT_TRACE, and PYTHONPYCACHEPREFIX made Python create a directory named after the value.
CREDENTIAL_ENV = re.compile(r".*(?:KEY|KEY_ID|TOKEN|SECRET|PASSWORD|PASSPHRASE)")
# Refused even with such an ending: ld.so prints a value it cannot use, and Python reads PYTHON*.
RESERVED_ENV = re.compile(r"(?:LD_|DYLD_|PYTHON).*")
# Linux errno values, spelled out so importing this file never fails on another platform.
ABSENT = {getattr(errno, "ENOKEY", 126), getattr(errno, "EKEYEXPIRED", 127), getattr(errno, "EKEYREVOKED", 128)}
USAGE = """usage:
  kernel_keyring.py store [--replace] <name>
  kernel_keyring.py status <name>
  kernel_keyring.py exec <name> <ENV_VAR> -- <command> [args...]
  kernel_keyring.py revoke <name>
<name>: lowercase letters, digits, '.', '_' or '-' (at most 64).
<ENV_VAR>: the provider's key variable, such as TAVILY_API_KEY: [A-Z_][A-Z0-9_]* ending in KEY, KEY_ID,
TOKEN, SECRET, PASSWORD or PASSPHRASE, and not LD_*, DYLD_* or PYTHON*. See docs/secret-storage.md."""


class UsageError(Exception):
    """Bad arguments. The message never repeats an argument, which could be a pasted value."""


class KeyringError(Exception):
    """A refusal or a failed keyring call. The message names the key or an errno, never a value."""


def _errname(number: int) -> str:
    return errno.errorcode.get(number, f"errno {number}")


class Keyring:
    """The few add_key/keyctl calls this tool needs, through libc's syscall()."""

    def __init__(self) -> None:
        if platform.system() != "Linux" or platform.machine() not in SYSCALLS:
            raise KeyringError("Linux x86_64/aarch64 only; on macOS use the login Keychain "
                               "(docs/secret-storage.md)")
        self.libc = ctypes.CDLL(None, use_errno=True)
        self.libc.syscall.restype = ctypes.c_long
        self.nr_add, self.nr_keyctl = SYSCALLS[platform.machine()]

    def _syscall(self, number: int, *args) -> int:
        """The call's result, or -errno. Integers go in as C longs, the width syscall() reads."""
        values = [ctypes.c_long(a) if isinstance(a, int) else a for a in args]
        result = self.libc.syscall(ctypes.c_long(number), *values)
        return result if result >= 0 else -(ctypes.get_errno() or errno.EIO)

    def _keyctl(self, operation: int, *args) -> int:
        return self._syscall(self.nr_keyctl, operation, *args)

    def search(self, description: bytes) -> int:
        """Serial of the live key, or 0 when there is none (never stored, revoked, invalidated, expired)."""
        result = self._keyctl(KEYCTL_SEARCH, KEY_SPEC_USER_KEYRING, b"user", description, 0)
        if result > 0:
            return result
        if -result in ABSENT:
            return 0
        raise KeyringError(f"keyctl search failed ({_errname(-result)})")

    def read(self, serial: int) -> bytes:
        size = self._keyctl(KEYCTL_READ, serial, None, 0)
        if size < 0:
            raise KeyringError(f"key unreadable ({_errname(-size)})")
        buffer = ctypes.create_string_buffer(max(size, 1))
        got = self._keyctl(KEYCTL_READ, serial, buffer, size)
        if got < 0:
            raise KeyringError(f"key unreadable ({_errname(-got)})")
        if got != size:
            raise KeyringError("key changed while it was read; run the command again")
        return buffer.raw[:size]

    def add(self, description: bytes, value: bytes) -> int:
        """Store the value under description in the user keyring with PERM.

        The key is created in this process's own keyring first, so this process possesses it while
        setting PERM, and only then linked into the user keyring. Added to the user keyring directly,
        a session whose keyring does not link the user keyring (systemd KeyringMode=private, `keyctl
        new_session`) would not possess it: setting PERM would fail and the key would keep the
        kernel default (user: view only), which other sessions cannot read.
        """
        serial = self._syscall(self.nr_add, b"user", description, value, len(value), KEY_SPEC_PROCESS_KEYRING)
        if serial < 0:
            raise KeyringError(f"add_key failed ({_errname(-serial)})")
        try:
            result = self._keyctl(KEYCTL_SETPERM, serial, PERM)
            if result < 0:
                raise KeyringError(f"setting the key's permissions failed ({_errname(-result)})")
            result = self._keyctl(KEYCTL_LINK, serial, KEY_SPEC_USER_KEYRING)
            if result < 0:
                raise KeyringError(f"linking the key into the user keyring failed ({_errname(-result)})")
        except KeyringError:
            self._keyctl(KEYCTL_REVOKE, serial)  # still possessed through this process's keyring
            raise
        finally:
            self._keyctl(KEYCTL_UNLINK, serial, KEY_SPEC_PROCESS_KEYRING)
        return serial

    def revoke(self, serial: int) -> str:
        """Revoke the key and unlink it from the user keyring; return what was done.

        Revoking needs write or setattr, which PERM gives only a possessor. A session whose keyring
        does not link the user keyring does not possess the key, so it invalidates the key instead,
        which needs only search: the key stops working at once and the kernel removes it.
        """
        result = self._keyctl(KEYCTL_REVOKE, serial)
        action, attempt = "revoked", "revoking"
        if result == -errno.EACCES:
            result = self._keyctl(KEYCTL_INVALIDATE, serial)
            action, attempt = "invalidated", "invalidating"
        if result < 0:
            raise KeyringError(f"{attempt} the key failed ({_errname(-result)})")
        result = self._keyctl(KEYCTL_UNLINK, serial, KEY_SPEC_USER_KEYRING)
        if result < 0 and -result not in ABSENT | {errno.ENOENT}:  # an invalidated key may be gone already
            raise KeyringError(f"unlinking the key failed ({_errname(-result)})")
        return action


def _description(name: str) -> bytes:
    if not NAME.fullmatch(name):
        raise UsageError("invalid key name: use lowercase letters, digits, '.', '_' or '-' (at most 64)")
    return (PREFIX + name).encode()


def _lock_address() -> str:
    """A Linux abstract Unix socket name: no file, no payload, one per uid (per network namespace)."""
    return f"\0{PREFIX}kernel_keyring:uid={os.getuid()}"


@contextlib.contextmanager
def _exclusive():
    """Run a store's final check-and-insert, or a revoke, one at a time for this uid.

    The lock is the bound socket name above. The kernel releases it when this process exits, however
    it exits, so no stale lock is left behind. `store` takes it only after the value was read, so a
    store waiting for input never holds up another. Another uid that binds the name first can only
    make these commands wait and then give up.
    """
    deadline = time.monotonic() + LOCK_WAIT_SECONDS
    while True:
        lock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        try:
            lock.bind(_lock_address())
            break
        except OSError as error:
            lock.close()
            if error.errno != errno.EADDRINUSE:
                raise KeyringError(f"cannot take the store/revoke lock ({_errname(error.errno or 0)})") from None
            if time.monotonic() >= deadline:
                raise KeyringError("another store or revoke is still running; try again") from None
            time.sleep(0.05)
    try:
        yield
    finally:
        lock.close()


def _hidden_line() -> bytes:
    """One line from the terminal on stdin, with echo turned off before the prompt is shown."""
    import termios

    fd = sys.stdin.fileno()
    try:
        saved = termios.tcgetattr(fd)
        hidden = termios.tcgetattr(fd)
        hidden[3] &= ~termios.ECHO
        termios.tcsetattr(fd, termios.TCSAFLUSH, hidden)
    except termios.error:
        raise KeyringError("cannot turn off echo on this terminal; pipe the value in instead") from None
    try:
        sys.stderr.write("value (input hidden; paste it, then press Enter): ")
        sys.stderr.flush()
        return sys.stdin.buffer.readline()
    finally:
        termios.tcsetattr(fd, termios.TCSAFLUSH, saved)
        sys.stderr.write("\n")
        sys.stderr.flush()


def _read_value() -> bytes:
    raw = _hidden_line() if os.isatty(sys.stdin.fileno()) else sys.stdin.buffer.read()
    value = raw.strip()
    if not value:
        raise KeyringError("empty input; nothing stored")
    if any(byte < 0x20 or byte == 0x7F for byte in value):
        raise KeyringError("the value contains a control character or line break; nothing stored")
    if len(value) > MAX_VALUE_BYTES:
        raise KeyringError(f"the value is longer than {MAX_VALUE_BYTES} bytes; nothing stored")
    return value


def _store(arguments: list[str]) -> int:
    replace = "--replace" in arguments
    rest = [argument for argument in arguments if argument != "--replace"]
    if len(rest) != 1 or rest[0].startswith("-"):
        raise UsageError("store takes one key name and optionally --replace")
    name = rest[0]
    description = _description(name)
    already = f"{name} is already stored; pass --replace to revoke it and store the new value"
    keyring = Keyring()
    if not replace and keyring.search(description):  # before the prompt, so no value is typed in vain
        raise KeyringError(already)
    value = _read_value()
    with _exclusive():
        existing = keyring.search(description)  # again: another store may have finished during the read
        if existing and not replace:
            raise KeyringError(already)
        note = ""
        if existing:  # revoke first, then store: never two live keys under one name
            note = f"; the previous key was {keyring.revoke(existing)}"
        keyring.add(description, value)
    print(f"stored {name} in the kernel user keyring (memory only{note})")
    return 0


def _exec(arguments: list[str]) -> int:
    if len(arguments) < 4 or arguments[2] != "--":
        raise UsageError("exec takes <name> <ENV_VAR> -- <command> [args...]")
    name, variable, command = arguments[0], arguments[1], arguments[3:]
    description = _description(name)
    if not ENV_NAME.fullmatch(variable):
        raise UsageError("invalid ENV_VAR: use [A-Z_][A-Z0-9_]*")
    if not CREDENTIAL_ENV.fullmatch(variable) or RESERVED_ENV.fullmatch(variable):
        raise UsageError("refused ENV_VAR: use the provider's key variable, a name ending in KEY, KEY_ID, "
                         "TOKEN, SECRET, PASSWORD or PASSPHRASE; LD_*, DYLD_* and PYTHON* are read at startup")
    keyring = Keyring()
    serial = keyring.search(description)
    if not serial:
        raise KeyringError(f"{name} is not in the kernel user keyring; store it first (docs/secret-storage.md)")
    value = keyring.read(serial)
    if b"\0" in value:
        raise KeyringError(f"{name} holds a NUL byte, which an environment variable cannot carry; store it again")
    environment = dict(os.environ)
    environment[variable] = os.fsdecode(value)  # surrogateescape: exactly these bytes reach the child
    try:
        os.execvpe(command[0], command, environment)
    except OSError as error:
        print(f"kernel_keyring: cannot run {command[0]!r}: {error.strerror or type(error).__name__}",
              file=sys.stderr)
        return 127 if isinstance(error, FileNotFoundError) else 126
    return 127  # not reached: execvpe returns only by raising


def _run(argv: list[str]) -> int:
    if argv[:1] in (["-h"], ["--help"]):
        print(USAGE)
        return 0
    if not argv or argv[0] not in {"store", "status", "exec", "revoke"}:
        raise UsageError("unknown or missing subcommand")
    command, arguments = argv[0], argv[1:]
    if command == "store":
        return _store(arguments)
    if command == "exec":
        return _exec(arguments)
    if len(arguments) != 1:
        raise UsageError(f"{command} takes one key name")
    name = arguments[0]
    description = _description(name)
    keyring = Keyring()
    if command == "status":
        serial = keyring.search(description)
        print(f"{name}: {'present' if serial else 'absent'}")
        return 0 if serial else 1
    with _exclusive():
        serial = keyring.search(description)
        if not serial:
            raise KeyringError(f"{name} is not in the kernel user keyring")
        action = keyring.revoke(serial)
    print(f"{action} {name}")
    return 0


def main(argv: list[str]) -> int:
    try:
        return _run(argv)
    except UsageError as error:
        print(f"kernel_keyring: {error}\n{USAGE}", file=sys.stderr)
        return 2
    except KeyringError as error:
        print(f"kernel_keyring: {error}", file=sys.stderr)
        return 1
    except (KeyboardInterrupt, EOFError):
        print("kernel_keyring: cancelled", file=sys.stderr)
        return 130
    except Exception as error:  # no traceback: it could quote whatever was being handled
        print(f"kernel_keyring: unexpected {type(error).__name__}; no value was printed", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
