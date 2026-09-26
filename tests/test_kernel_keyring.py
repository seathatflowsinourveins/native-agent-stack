"""scripts/kernel_keyring.py against the real Linux kernel user keyring.

Local integration class (docs/acceptance-evidence-policy.md). Every test stores generated throwaway
values under names unique to this run (``kktest-<pid>-<hex>-<label>``) and tearDown removes them with
its own keyctl calls, independent of the script under test; no other key is read or changed. Every
subcommand's stdout and stderr are checked for each test value. Some commands run under a wrapper that
first joins a new session keyring: ``private`` does not link the user keyring (as with systemd
``KeyringMode=private``), so the process does not possess the stored key; ``linked`` links it, as
pam_keyinit does, so it does. Two stores of one name race by holding the first at its hidden-input
prompt on a pseudo-terminal while the second completes. The lock tests hold the script's per-uid lock
for about a second, so a real ``store`` or ``revoke`` of this uid run at that moment waits. Skipped
unless Linux x86_64/aarch64, and when this environment blocks the keyring system calls (for example a
container seccomp profile).
"""
from __future__ import annotations

import ctypes
import errno
import hashlib
import importlib.util
import os
import platform
import re
import secrets
import select
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "kernel_keyring.py"
KEYCTL_NR = {"x86_64": 250, "aarch64": 219}
SUPPORTED = platform.system() == "Linux" and platform.machine() in KEYCTL_NR
PREFIX = "native-agent-stack:"
KEY_SPEC_USER_KEYRING = -4
KEYCTL_DESCRIBE, KEYCTL_UNLINK, KEYCTL_SEARCH, KEYCTL_READ, KEYCTL_INVALIDATE = 6, 9, 10, 11, 21
VARIABLE = "KK_TEST_API_KEY"
HOLD_SECONDS = 1.0  # how long a lock test holds the lock; well under the script's LOCK_WAIT_SECONDS

# Checks, printing nothing, that the variable named in argv[1] holds bytes with the SHA-256 in argv[2],
# that those bytes are not on the child's own command line, and that the rest of the environment
# came through.
CHILD = (
    "import hashlib, os, sys\n"
    "value = os.environ.get(sys.argv[1])\n"
    "if value is None: sys.exit(10)\n"
    "if hashlib.sha256(os.fsencode(value)).hexdigest() != sys.argv[2]: sys.exit(11)\n"
    "with open('/proc/self/cmdline', 'rb') as handle:\n"
    "    if os.fsencode(value) in handle.read(): sys.exit(12)\n"
    "if os.environ.get('KK_TEST_MARKER') != 'inherited': sys.exit(13)\n"
)
# Joins a new anonymous session keyring (KEYCTL_JOIN_SESSION_KEYRING), links the user keyring into it
# for `linked` (KEYCTL_LINK), then runs the rest of its arguments.
SESSION = (
    "import ctypes, os, platform, sys\n"
    "libc = ctypes.CDLL(None, use_errno=True)\n"
    "libc.syscall.restype = ctypes.c_long\n"
    "number = {'x86_64': 250, 'aarch64': 219}[platform.machine()]\n"
    "def keyctl(*args):\n"
    "    values = [ctypes.c_long(a) if isinstance(a, int) else a for a in args]\n"
    "    return libc.syscall(ctypes.c_long(number), *values)\n"
    "if keyctl(1, None) <= 0: sys.exit(90)\n"
    "if sys.argv[1] == 'linked' and keyctl(8, -4, -3) < 0: sys.exit(91)\n"
    "os.execvp(sys.argv[2], sys.argv[2:])\n"
)
TOUCH = "import sys; open(sys.argv[1], 'w').close()"


class Kernel:
    """Direct keyctl calls for independent checks and cleanup; never reads a payload."""

    def __init__(self) -> None:
        self.libc = ctypes.CDLL(None, use_errno=True)
        self.libc.syscall.restype = ctypes.c_long
        self.number = KEYCTL_NR[platform.machine()]

    def keyctl(self, *args) -> int:
        values = [ctypes.c_long(a) if isinstance(a, int) else a for a in args]
        result = self.libc.syscall(ctypes.c_long(self.number), *values)
        return result if result >= 0 else -ctypes.get_errno()

    def search(self, name: str) -> int:
        return self.keyctl(KEYCTL_SEARCH, KEY_SPEC_USER_KEYRING, b"user", (PREFIX + name).encode(), 0)

    def describe(self, serial: int) -> str | None:
        buffer = ctypes.create_string_buffer(512)
        return buffer.value.decode() if self.keyctl(KEYCTL_DESCRIBE, serial, buffer, 512) >= 0 else None

    def readable(self, serial: int) -> bool:
        return self.keyctl(KEYCTL_READ, serial, None, 0) >= 0  # length query only

    def remove(self, name: str) -> None:
        serial = self.search(name)
        if serial > 0:
            self.keyctl(KEYCTL_INVALIDATE, serial)  # needs only search, which the script's PERM grants
            self.keyctl(KEYCTL_UNLINK, serial, KEY_SPEC_USER_KEYRING)


def read_until(fd: int, marker: bytes, timeout: float) -> bytes:
    data, deadline = b"", time.monotonic() + timeout
    while marker not in data and time.monotonic() < deadline:
        ready, _, _ = select.select([fd], [], [], max(deadline - time.monotonic(), 0))
        chunk = os.read(fd, 4096) if ready else b""
        if not chunk:
            break
        data += chunk
    return data


def drain(fd: int) -> bytes:
    data = b""
    while select.select([fd], [], [], 0.3)[0]:
        try:
            chunk = os.read(fd, 4096)
        except OSError:  # EIO once no process holds the terminal open
            break
        if not chunk:
            break
        data += chunk
    return data


def load_script():
    """The script as a module, not __main__, so it does not re-execute itself."""
    spec = importlib.util.spec_from_file_location("kernel_keyring_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def stop(process: subprocess.Popen) -> None:
    if process.poll() is None:
        process.kill()
    process.communicate()


@unittest.skipUnless(SUPPORTED, "the kernel keyring script supports Linux x86_64/aarch64 only")
class KernelKeyringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.kernel = Kernel()
        probe = cls.kernel.search(f"kktest-probe-{secrets.token_hex(4)}")
        if probe < 0 and -probe not in {errno.ENOKEY, errno.EKEYREVOKED, errno.EKEYEXPIRED}:
            raise unittest.SkipTest(f"kernel keyring unavailable here ({errno.errorcode.get(-probe, -probe)})")
        cls.run_id = f"kktest-{os.getpid()}-{secrets.token_hex(4)}"

    def setUp(self) -> None:
        self.names: list[str] = []
        self.values: list[bytes] = []

    def tearDown(self) -> None:
        for name in self.names:
            self.kernel.remove(name)
        for name in self.names:
            self.assertLessEqual(self.kernel.search(name), 0, f"{name} was left in the keyring")

    def new_name(self, label: str) -> str:
        name = f"{self.run_id}-{label}"
        self.names.append(name)
        return name

    def unlink_from_user_keyring(self, serials: list[int]) -> None:
        for serial in serials:
            self.kernel.keyctl(KEYCTL_UNLINK, serial, KEY_SPEC_USER_KEYRING)  # ENOENT when not linked

    def new_value(self) -> bytes:
        value = f"kk-canary-{secrets.token_hex(16)}".encode()
        self.values.append(value)
        return value

    def assert_no_value(self, output: bytes, label: str = "output") -> None:
        for secret in self.values:
            self.assertNotIn(secret, output, f"a test value appeared in {label}")

    def cli(self, *args: str, value: bytes = b"", session: str | None = None, env=None, cwd=None):
        prefix = [sys.executable, "-c", SESSION, session] if session else []
        result = subprocess.run([*prefix, sys.executable, str(SCRIPT), *args], input=value,
                                capture_output=True, env=env, cwd=cwd, timeout=60)
        self.assert_no_value(result.stdout, f"{args[:1]} stdout")
        self.assert_no_value(result.stderr, f"{args[:1]} stderr")
        return result

    def terminal_store(self, *args: str, session: str | None = None):
        """Start `store` reading a new pseudo-terminal; return once its hidden-input prompt is shown.

        By then the script has checked for an existing key and is waiting for the value, which the
        caller writes to the returned terminal master.
        """
        try:
            master, slave = os.openpty()
        except OSError as error:
            self.skipTest(f"no pseudo-terminal ({error})")
        self.addCleanup(os.close, master)
        self.addCleanup(os.close, slave)
        prefix = [sys.executable, "-c", SESSION, session] if session else []
        process = subprocess.Popen([*prefix, sys.executable, str(SCRIPT), "store", *args], stdin=slave,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.addCleanup(stop, process)  # runs first: the process ends before its terminal is closed
        prompt = read_until(process.stderr.fileno(), b"input hidden", 30)
        self.assertIn(b"input hidden", prompt)
        return process, master, prompt

    def assert_child_sees(self, name: str, value: bytes, session: str | None = None, env=None, cwd=None,
                          variable: str = VARIABLE):
        environment = dict(os.environ if env is None else env)
        environment.pop(variable, None)
        environment["KK_TEST_MARKER"] = "inherited"
        result = self.cli("exec", name, variable, "--", sys.executable, "-c", CHILD, variable,
                          hashlib.sha256(value).hexdigest(), session=session, env=environment, cwd=cwd)
        self.assertEqual(result.returncode, 0, "child check failed (10 missing, 11 wrong value, "
                         "12 value on its command line, 13 environment not inherited)")
        self.assertEqual(result.stdout, b"")
        self.assertNotIn(variable, os.environ)

    def test_round_trip_store_status_exec_revoke(self):
        name, value = self.new_name("roundtrip"), self.new_value()
        absent = self.cli("status", name, session="linked")
        self.assertEqual((absent.returncode, absent.stdout), (1, f"{name}: absent\n".encode()))
        stored = self.cli("store", name, value=value + b"\n", session="linked")  # newline stripped
        self.assertEqual(stored.returncode, 0, stored.stderr)
        self.assertEqual(stored.stdout, f"stored {name} in the kernel user keyring (memory only)\n".encode())
        present = self.cli("status", name, session="linked")
        self.assertEqual((present.returncode, present.stdout), (0, f"{name}: present\n".encode()))
        serial = self.kernel.search(name)
        self.assertGreater(serial, 0)
        self.assertEqual(self.kernel.describe(serial),
                         f"user;{os.getuid()};{os.getgid()};3f0b0000;{PREFIX}{name}")
        self.assert_child_sees(name, value, session="linked")
        self.assert_child_sees(name, value)  # whatever session keyring this test process has
        revoked = self.cli("revoke", name, session="linked")
        self.assertEqual((revoked.returncode, revoked.stdout), (0, f"revoked {name}\n".encode()))
        self.assertFalse(self.kernel.readable(serial))
        self.assertLessEqual(self.kernel.search(name), 0)
        self.assertEqual(self.cli("status", name).returncode, 1)
        again = self.cli("revoke", name)
        self.assertEqual(again.returncode, 1)
        self.assertIn(b"not in the kernel user keyring", again.stderr)

    def test_store_refuses_an_existing_name_without_replace(self):
        name, first, second = self.new_name("exists"), self.new_value(), self.new_value()
        self.assertEqual(self.cli("store", name, value=first).returncode, 0)
        serial = self.kernel.search(name)
        refused = self.cli("store", name, value=second)
        self.assertEqual(refused.returncode, 1)
        self.assertIn(b"already stored; pass --replace", refused.stderr)
        self.assertEqual(refused.stdout, b"")
        self.assertEqual(self.kernel.search(name), serial)
        self.assert_child_sees(name, first)

    def test_replace_revokes_the_old_key_before_storing(self):
        name, first, second, third = self.new_name("replace"), self.new_value(), self.new_value(), self.new_value()
        self.names.append("--replace")  # a script that took the flag for a name would store under it
        self.assertEqual(self.cli("store", name, value=first, session="linked").returncode, 0)
        old = self.kernel.search(name)
        replaced = self.cli("store", "--replace", name, value=second, session="linked")
        self.assertEqual(replaced.returncode, 0, replaced.stderr)
        self.assertIn(b"(memory only; the previous key was revoked)", replaced.stdout)
        new = self.kernel.search(name)
        self.assertGreater(new, 0)
        self.assertNotEqual(new, old)
        self.assertFalse(self.kernel.readable(old))
        self.assert_child_sees(name, second)
        # From a session that does not possess the key, --replace (after the name) invalidates it instead.
        again = self.cli("store", name, "--replace", value=third, session="private")
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertIn(b"(memory only; the previous key was invalidated)", again.stdout)
        self.assertFalse(self.kernel.readable(new))
        self.assert_child_sees(name, third)

    def test_private_session_keyring_can_store_read_and_remove(self):
        name, value = self.new_name("private"), self.new_value()
        self.names.append("--replace")  # as in the test above
        stored = self.cli("store", "--replace", name, value=value, session="private")  # nothing to replace
        self.assertEqual(stored.returncode, 0, stored.stderr)
        self.assertNotIn(b"previous key", stored.stdout)
        serial = self.kernel.search(name)
        self.assertGreater(serial, 0)
        self.assertEqual(self.kernel.describe(serial).split(";")[3], "3f0b0000")  # permissions applied
        self.assert_child_sees(name, value, session="private")
        self.assert_child_sees(name, value, session="linked")
        removed = self.cli("revoke", name, session="private")
        self.assertEqual((removed.returncode, removed.stdout), (0, f"invalidated {name}\n".encode()))
        self.assertFalse(self.kernel.readable(serial))
        self.assertLessEqual(self.kernel.search(name), 0)

    def test_a_store_finished_during_another_stores_input_is_not_overwritten(self):
        name, first, second = self.new_name("race"), self.new_value(), self.new_value()
        waiting, master, prompt = self.terminal_store(name)  # found no key; now waits for the value
        other = self.cli("store", name, value=second)
        self.assertEqual(other.returncode, 0, other.stderr)
        serial = self.kernel.search(name)
        os.write(master, first + b"\n")
        out, err = waiting.communicate(timeout=30)
        self.assert_no_value(prompt + out + err, "the waiting store's output")
        self.assertEqual(waiting.returncode, 1, err)
        self.assertIn(b"already stored; pass --replace", err)
        self.assertEqual(out, b"")
        self.assertEqual(self.kernel.search(name), serial)
        self.assert_child_sees(name, second)

    def test_replace_revokes_a_key_stored_during_its_input(self):
        name, first, second = self.new_name("racereplace"), self.new_value(), self.new_value()
        waiting, master, prompt = self.terminal_store("--replace", name, session="linked")
        self.assertEqual(self.cli("store", name, value=second).returncode, 0)
        meanwhile = self.kernel.search(name)
        self.assertGreater(meanwhile, 0)
        os.write(master, first + b"\n")
        out, err = waiting.communicate(timeout=30)
        self.assert_no_value(prompt + out + err, "the waiting store's output")
        self.assertEqual(waiting.returncode, 0, err)
        self.assertIn(b"(memory only; the previous key was revoked)", out)
        self.assertFalse(self.kernel.readable(meanwhile))
        self.assertNotEqual(self.kernel.search(name), meanwhile)
        self.assert_child_sees(name, first)

    def hold_lock(self, module) -> socket.socket:
        lock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        try:
            lock.bind(module._lock_address())
        except OSError as error:
            lock.close()
            self.skipTest(f"cannot hold the lock here ({errno.errorcode.get(error.errno, error.errno)})")
        return lock

    def test_store_and_revoke_wait_while_the_lock_is_held(self):
        module = load_script()
        name, value = self.new_name("lock"), self.new_value()
        for args, stdin, before in ((("store", name), value, False), (("revoke", name), b"", True)):
            with self.subTest(command=args[0]):
                lock = self.hold_lock(module)
                try:
                    # The input goes through a pipe written and closed before the child starts: closing
                    # Popen.stdin by hand makes a later communicate() raise "flush of closed file" on Python 3.12.
                    read_end, write_end = os.pipe()
                    os.write(write_end, stdin)
                    os.close(write_end)
                    try:
                        process = subprocess.Popen([sys.executable, str(SCRIPT), *args], stdin=read_end,
                                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    finally:
                        os.close(read_end)
                    self.addCleanup(stop, process)
                    time.sleep(HOLD_SECONDS)
                    self.assertIsNone(process.poll(), f"{args[0]} did not wait for the lock")
                    self.assertEqual(self.kernel.search(name) > 0, before)  # nothing changed yet
                finally:
                    lock.close()
                out, err = process.communicate(timeout=30)
                self.assert_no_value(out + err, f"{args[0]} output")
                self.assertEqual(process.returncode, 0, err)
                self.assertEqual(self.kernel.search(name) > 0, not before)

    def test_the_lock_gives_up_with_a_message_and_is_released(self):
        module = load_script()
        module.LOCK_WAIT_SECONDS = 0.3
        lock = self.hold_lock(module)
        try:
            with self.assertRaises(module.KeyringError) as caught:
                with module._exclusive():
                    self.fail("took a lock that is held")
            self.assertIn("another store or revoke is still running", str(caught.exception))
        finally:
            lock.close()
        with module._exclusive():
            with self.assertRaises(module.KeyringError):
                with module._exclusive():
                    self.fail("took the lock twice")
        with module._exclusive():  # released on leaving the block
            pass

    def test_a_failed_permission_or_link_step_is_reported_and_leaves_no_key(self):
        module = load_script()
        for step in (module.KEYCTL_SETPERM, module.KEYCTL_LINK):
            with self.subTest(step=step):
                name, value = self.new_name(f"step{step}"), self.new_value()
                keyring, calls, created = module.Keyring(), [], []

                def syscall(number, *args, real=keyring._syscall, add_key=keyring.nr_add, created=created):
                    result = real(number, *args)
                    if number == add_key and result > 0:
                        created.append(result)
                    return result

                def keyctl(operation, *args, real=keyring._keyctl, calls=calls, step=step):
                    calls.append(operation)
                    return -errno.EACCES if operation == step else real(operation, *args)

                keyring._syscall, keyring._keyctl = syscall, keyctl
                self.addCleanup(self.unlink_from_user_keyring, created)  # even a revoked key, if linked
                with self.assertRaises(module.KeyringError) as caught:
                    keyring.add((PREFIX + name).encode(), value)
                self.assertIn("(EACCES)", str(caught.exception))
                self.assertNotIn(value.decode(), str(caught.exception))
                self.assertIn(module.KEYCTL_REVOKE, calls)  # the staged key is revoked, not left behind
                self.assertLessEqual(self.kernel.search(name), 0)

    def test_exec_refuses_a_missing_key_without_running_the_command(self):
        name = self.new_name("missing")
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory, "ran")
            result = self.cli("exec", name, VARIABLE, "--", sys.executable, "-c", TOUCH, str(marker))
            self.assertEqual(result.returncode, 1)
            self.assertIn(b"is not in the kernel user keyring", result.stderr)
            self.assertFalse(marker.exists())

    def test_exec_refuses_invalid_or_reserved_variable_names(self):
        name, value = self.new_name("envname"), self.new_value()
        self.assertEqual(self.cli("store", name, value=value).returncode, 0)
        with tempfile.TemporaryDirectory() as directory:
            for index, variable in enumerate((
                    "", "lower", "Mixed_Case", "1ABC", "A-B", "A=B", "A B", "kk_test_api_key",
                    "KK_TEST_VALUE", "KK_TEST_API_KEY_FILE", "LD_PRELOAD", "LD_LIBRARY_PATH",
                    "PATH", "IFS", "ENV", "BASH_ENV", "PS4", "SHELLOPTS", "BASHOPTS",
                    "PYTHONWARNINGS", "PYTHONHOME", "PYTHONIOENCODING", "PYTHONPYCACHEPREFIX",
                    "PYTHONSTARTUP", "LANG", "LC_ALL", "TERM", "GIT_TRACE", "NODE_OPTIONS",
                    "JAVA_TOOL_OPTIONS", "SSLKEYLOGFILE", "SSH_AUTH_SOCK",
                    "PYTHON_API_KEY", "LD_AUDIT_TOKEN", "DYLD_SECRET")):
                with self.subTest(variable=variable):
                    marker = Path(directory, f"ran-{index}")
                    result = self.cli("exec", name, variable, "--", sys.executable, "-c", TOUCH, str(marker))
                    self.assertEqual(result.returncode, 2)
                    self.assertIn(b"ENV_VAR", result.stderr)
                    self.assertFalse(marker.exists())

    def test_exec_accepts_credential_variable_names(self):
        name, value = self.new_name("credname"), self.new_value()
        self.assertEqual(self.cli("store", name, value=value).returncode, 0)
        for variable in ("KK_TEST_KEY", "KK_TEST_API_KEY_ID", "KK_TEST_TOKEN", "KK_TEST_AUTHTOKEN",
                         "KK_TEST_SECRET", "KKTESTPASSWORD", "KK_TEST_PASSPHRASE", "_KK_TEST_KEY"):
            with self.subTest(variable=variable):
                self.assert_child_sees(name, value, variable=variable)

    def test_exec_refuses_a_startup_variable_that_a_quiet_child_would_print(self):
        name, value = self.new_name("startup"), self.new_value()
        self.assertEqual(self.cli("store", name, value=value).returncode, 0)
        # Positive control, without the script: a child that prints nothing itself still prints a
        # PYTHONWARNINGS value it cannot parse, while it starts.
        control = subprocess.run([sys.executable, "-c", "pass"], capture_output=True, timeout=60,
                                 env={**os.environ, "PYTHONWARNINGS": value.decode()})
        self.assertIn(value, control.stderr)
        for variable in ("PYTHONWARNINGS", "PYTHONHOME", "PYTHONIOENCODING", "LC_ALL", "TERM", "GIT_TRACE"):
            with self.subTest(variable=variable):
                refused = self.cli("exec", name, variable, "--", sys.executable, "-c", "pass")
                self.assertEqual(refused.returncode, 2)
                self.assertIn(b"refused ENV_VAR", refused.stderr)
        quiet = self.cli("exec", name, VARIABLE, "--", sys.executable, "-c", "pass")
        self.assertEqual((quiet.returncode, quiet.stdout, quiet.stderr), (0, b"", b""))

    def test_invalid_key_names_are_refused_and_not_echoed(self):
        run = self.run_id
        pasted = "tvlyPastedValue" + secrets.token_hex(8)  # an uppercase letter, as in most API keys
        names = ["", f"Upper-{run}", f"{run} b", f"{run}/b", f"../{run}", f"-{run}", f".{run}",
                 run + "x" * 65, f"{run}\nb", f"{run}\ttab", pasted]
        self.names.extend(name for name in names if name)  # tearDown removes any a broken script stores
        for name in names:
            for args in (("status", name), ("revoke", name), ("store", name),
                         ("exec", name, VARIABLE, "--", "true")):
                with self.subTest(name=name, command=args[0]):
                    result = self.cli(*args, value=b"unused")
                    self.assertEqual(result.returncode, 2)
                    self.assertEqual(result.stdout, b"")
                    if name:
                        self.assertNotIn(name.encode(), result.stderr)

    def test_store_rejects_empty_input_and_control_characters(self):
        name, part = self.new_name("reject"), self.new_value()
        for raw, message in ((b"", b"empty input"), (b" \n\t", b"empty input"),
                             (part + b"\n" + part, b"control character"),
                             (part + b"\0" + part, b"control character"),
                             (part + b"\t" + part, b"control character"),
                             (part + b"\x7f", b"control character")):
            with self.subTest(raw=raw[:3]):
                result = self.cli("store", name, value=raw)
                self.assertEqual(result.returncode, 1)
                self.assertIn(message, result.stderr)
                self.assertLessEqual(self.kernel.search(name), 0)

    def test_non_ascii_value_reaches_the_child_byte_for_byte(self):
        name = self.new_name("bytes")
        value = self.new_value() + "é".encode() + b"\xff"
        self.values.append(value)
        self.assertEqual(self.cli("store", name, value=value).returncode, 0)
        self.assert_child_sees(name, value)

    def test_store_and_exec_write_no_file(self):
        name, value = self.new_name("nofile"), self.new_value()
        with tempfile.TemporaryDirectory() as home:
            env = {**os.environ, "HOME": home, "TMPDIR": home, "XDG_CONFIG_HOME": home, "XDG_CACHE_HOME": home,
                   "XDG_STATE_HOME": home, "XDG_DATA_HOME": home, "XDG_RUNTIME_DIR": home}
            self.assertEqual(self.cli("store", name, value=value, env=env, cwd=home).returncode, 0)
            self.assert_child_sees(name, value, env=env, cwd=home)
            self.assertEqual(sorted(os.listdir(home)), [])

    def test_exec_failure_names_the_command_only(self):
        name, value = self.new_name("nocmd"), self.new_value()
        self.assertEqual(self.cli("store", name, value=value).returncode, 0)
        result = self.cli("exec", name, VARIABLE, "--", f"kk-no-such-command-{secrets.token_hex(4)}")
        self.assertEqual(result.returncode, 127)
        self.assertIn(b"cannot run", result.stderr)

    def test_usage_errors(self):
        name = self.new_name("usage")
        for args in ((), ("bogus",), ("status",), ("status", name, "extra"), ("revoke",),
                     ("store",), ("store", name, "extra"), ("store", "--force", name),
                     ("exec", name, VARIABLE, "true"), ("exec", name, VARIABLE, "--"), ("exec", name)):
            with self.subTest(args=args):
                result = self.cli(*args)
                self.assertEqual(result.returncode, 2)
                self.assertIn(b"usage:", result.stderr)
        self.assertLessEqual(self.kernel.search(name), 0)
        shown = self.cli("--help")
        self.assertEqual(shown.returncode, 0)
        self.assertTrue(shown.stdout.startswith(b"usage:"))

    def test_terminal_input_is_not_echoed(self):
        name, value = self.new_name("tty"), self.new_value()
        try:
            master, slave = os.openpty()
        except OSError as error:
            self.skipTest(f"no pseudo-terminal ({error})")
        try:
            os.write(master, b"kk-echo-probe\n")  # positive control: a new terminal echoes input
            self.assertIn(b"kk-echo-probe", drain(master))
            process = subprocess.Popen([sys.executable, str(SCRIPT), "store", name], stdin=slave,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                prompt = read_until(process.stderr.fileno(), b"input hidden", 30)
                self.assertIn(b"input hidden", prompt)
                os.write(master, value + b"\n")
                out, err = process.communicate(timeout=30)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
            echoed = drain(master)
        finally:
            os.close(slave)
            os.close(master)
        self.assertEqual(process.returncode, 0, err)
        self.assertNotIn(value, echoed)
        self.assertNotIn(value, prompt + out + err)
        self.assertTrue(re.fullmatch(rb"stored \S+ in the kernel user keyring \(memory only\)\n", out))
        self.assert_child_sees(name, value)  # the pending probe line was flushed, not stored


if __name__ == "__main__":
    unittest.main()
