"""Tests for tools/credentials/credential_run.py, the id-based key runner.

Local integration checks, not upstream acceptance (docs/acceptance-evidence-policy.md). Every value is a synthetic
fake generated per test. The store is a temporary XDG_CONFIG_HOME that exists only in the environment of the runner
these tests start, and no test reads a real store, a real *.env file, the kernel keyring or a native sign-in.
"""
from __future__ import annotations

import ast
import base64
import contextlib
import hashlib
import io
import json
import os
import random
import re
import select
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.parse
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools" / "credentials"
TOOL = TOOLS / "credential_run.py"
sys.path.insert(0, str(TOOLS))
import credential_run as run_mod  # noqa: E402
import set_credential as writer  # noqa: E402

INJECTABLE_IDS = {"alpaca-paper", "alpaca-paper-2", "sec-contact", "databento", "typesafe", "omniroute", "tavily",
                  "claude-oauth-token", "canary-e2e"}
NOT_INJECTABLE_IDS = ("grafana-admin", "nativestack-generation-key", "openhands-session", "claude-native",
                      "codex-native", "gh-native", "huggingface-native", "huggingface-native-stored", "ibkr-gateway",
                      "github-actions")
MARK = b"[REDACTED:TAVILY_API_KEY]"
PARTIAL = b"[REDACTED-PARTIAL:TAVILY_API_KEY]"
STORE_LINE = re.compile(rb"export +[A-Za-z_]")


def _host_hands_cores_to_a_collector() -> bool:
    """This host's own core_pattern, read here without the tool: a `|` (systemd-coredump, apport) or `@` (a core socket)."""
    try:
        with open("/proc/sys/kernel/core_pattern", "rb") as handle:
            return handle.read(1) in (b"|", b"@")
    except OSError:
        return False


# The runner refuses to start on such a host (review of 2026-09-29, finding 2), and CI runners commonly are one. There
# the tests start it through this launcher, which points CORE_PATTERN_FILE at a temporary file that holds "core"; the
# two tests of the real re-execution skip. The refusal itself is tested in process with its own pattern files.
# CREDENTIAL_RUN_TEST_LAUNCHER=1 forces the launcher on any host, to exercise this path.
HOST_PIPES_CORES = os.environ.get("CREDENTIAL_RUN_TEST_LAUNCHER") == "1" or _host_hands_cores_to_a_collector()
# The launcher also switches the watchdog off on request, to see the parent-death signal alone (a module constant, as
# CORE_PATTERN_FILE is: the tool has no environment switch for it), and runs the Python source of RUNNER_TEST_SETUP
# before main: a test uses it to replace a module constant or function of the tool (PINNED, pre_exec_pause) or to record
# the calls the runner makes (recorder_setup). The variable is read here, in the test's launcher, and never by the tool.
LAUNCHER = ("import os, sys\n"
            f"sys.path[:0] = [{str(TOOLS)!r}, {str(ROOT / 'scripts')!r}]\n"
            "import credential_run\n"
            "credential_run.CORE_PATTERN_FILE = os.environ.pop('CORE_PATTERN_TEST_FILE')\n"
            "if os.environ.pop('WATCHDOG_TEST_OFF', '') == '1':\n"
            "    credential_run.WATCHDOG = False\n"
            "exec(os.environ.pop('RUNNER_TEST_SETUP', ''))\n"
            "sys.exit(credential_run.main(sys.argv[1:]))\n")

# A child that reports what reached its environment by sha256 only, so no test output holds a value.
REPORT = ("import hashlib, json, os, sys\n"
          "names = json.loads(sys.argv[1])\n"
          "print(json.dumps({n: hashlib.sha256(os.environ[n].encode()).hexdigest() if n in os.environ else None\n"
          "                  for n in names}, sort_keys=True))\n")
# A careless child: it prints its own key raw and in the encodings the masker cites, on both streams.
FORMS = ("import base64, json, os, re, sys, urllib.parse\n"
         "v = os.environ['TAVILY_API_KEY']\n"
         "raw = v.encode()\n"
         "lines = [v]\n"
         "for prefix in (b'', b'u', b'us', b'use', b'user:'):\n"
         "    lines.append(base64.b64encode(prefix + raw + b'!').decode())\n"
         "    lines.append(base64.urlsafe_b64encode(prefix + raw + b'?').decode())\n"
         "q = urllib.parse.quote(v, safe='')\n"
         "lines += [q, re.sub('%[0-9A-F]{2}', lambda m: m.group().lower(), q), json.dumps({'key': v}),\n"
         "          raw.hex(), raw.hex().upper()]\n"
         "for stream in (sys.stdout, sys.stderr):\n"
         "    for line in lines:\n"
         "        stream.write('form ' + line + '\\n')\n")


# Synthetic values use the letters g-v, one per hex digit: the reports print hex SHA-256 digests, and a six-character
# piece of a hex value matched one of them by chance in about 0.07% of runs (assert_never_echoed then failed).
FAKE_LETTERS = str.maketrans("0123456789abcdef", "ghijklmnopqrstuv")


def fake(prefix: str = "", tail: str = "") -> str:
    return prefix + os.urandom(12).hex().translate(FAKE_LETTERS) + tail


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def py(code: str, *args: str) -> list[str]:
    """`-- python3 -I -c code args...`: the runner's command part."""
    return ["--", sys.executable, "-I", "-c", code, *args]


def marker_writer(delay: float, ignore_term: bool = False) -> str:
    """Python source of a process that creates the file named by its argv[1] after `delay` seconds, unless it is ended
    first (a process that ignores SIGTERM can only be ended by SIGKILL). It creates argv[1] + ".ready" as soon as its
    SIGTERM disposition is set, so that a test can tell when the process really ignores SIGTERM."""
    return ("import signal, sys, time\n" + ("signal.signal(signal.SIGTERM, signal.SIG_IGN)\n" if ignore_term else "")
            + "open(sys.argv[1] + '.ready', 'w').close()\n"
            + f"time.sleep({delay})\nopen(sys.argv[1], 'w').close()\n")


def spawn_marker_writers(*writers, quiet: bool = False) -> str:
    """Python source that starts one marker_writer per (marker path, delay, ignore_term) in its own process group, waits
    until each is ready, and prints "spawned" and the process ids; the caller adds what it does next. quiet: each writer
    gets /dev/null for stdin, stdout and stderr, so it holds none of the command's pipes and the runner sees end of file
    as soon as the command exits, with no drain."""
    ready = [str(path) + ".ready" for path, _delay, _ignore in writers]
    streams = ", stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL" if quiet else ""
    return ("import os, subprocess, sys, time\nkids = []\n" + "".join(
        f"kids.append(subprocess.Popen([sys.executable, '-I', '-c', {marker_writer(delay, ignore)!r}, {str(path)!r}]"
        f"{streams}))\n" for path, delay, ignore in writers)
            + f"ready = {ready!r}\ndeadline = time.monotonic() + 20\n"
            + "while not all(os.path.exists(path) for path in ready) and time.monotonic() < deadline:\n"
            + "    time.sleep(0.01)\n"
            + "print('spawned', os.getpid(), *[k.pid for k in kids], flush=True)\n")


def kill_quietly(pid: int) -> None:
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.kill(pid, signal.SIGKILL)


def process_state(pid: int) -> str:
    """The state letter of /proc/<pid>/stat ("Z" for a zombie), or "gone" (Linux)."""
    try:
        with open(f"/proc/{pid}/stat", "rb") as handle:
            return handle.read().rsplit(b")", 1)[1].split()[0].decode("ascii")
    except (FileNotFoundError, ProcessLookupError):
        return "gone"


def is_running(pid: int) -> bool:
    return process_state(pid) not in ("gone", "Z", "X")


def wait_until(predicate, seconds: float = 10.0) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return bool(predicate())


def wait_for_json(path: Path, seconds: float = 30.0):
    """The JSON that a process writes to `path`, once it is there and complete."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        with contextlib.suppress(FileNotFoundError, ValueError):
            return json.loads(path.read_text())
        time.sleep(0.02)
    raise AssertionError(f"{path.name} never appeared")


def recorder_setup(log: Path, pinned: bool | None = None) -> str:
    """RUNNER_TEST_SETUP source that records, in order, what the runner does to the command: each killpg with the state
    of the command at that moment (os.waitid with WNOWAIT still sees a command that is running or has exited, and raises
    ChildProcessError once it has been reaped), each waitpid with the pid it returned, the start of the watchdog, its
    stand-down and the byte that carries it (a write of b"."). The list is written to `log` as JSON when the runner
    exits. pinned=False also switches the tool's pinned cleanup off, as a platform without it would have it."""
    return (("credential_run.PINNED = False\n" if pinned is False else "")
            + "import atexit, json\n"
              "events = []\n"
              "real_killpg, real_waitpid, real_waitid = os.killpg, os.waitpid, getattr(os, 'waitid', None)\n"
              "def killpg(pgid, signum):\n"
              "    state = 'unknown'\n"
              "    if real_waitid is not None:\n"
              "        try:\n"
              "            found = real_waitid(os.P_PID, pgid, os.WEXITED | os.WNOHANG | os.WNOWAIT)\n"
              "            state = 'zombie' if found else 'running'\n"
              "        except ChildProcessError:\n"
              "            state = 'reaped'\n"
              "    events.append(['killpg', int(signum), state])\n"
              "    return real_killpg(pgid, signum)\n"
              "def waitpid(pid, options):\n"
              "    result = real_waitpid(pid, options)\n"
              "    events.append(['waitpid', pid, result[0]])\n"
              "    return result\n"
              "real_write = os.write\n"
              "def write(fd, data):\n"
              "    if data == b'.':\n"
              "        events.append(['byte'])\n"
              "    return real_write(fd, data)\n"
              "os.killpg, os.waitpid, os.write = killpg, waitpid, write\n"
              "real_init, real_release = credential_run.Watchdog.__init__, credential_run.Watchdog.release\n"
              "def init(self, pgid):\n"
              "    events.append(['watchdog', pgid])\n"
              "    real_init(self, pgid)\n"
              "def release(self):\n"
              "    events.append(['standdown'])\n"
              "    real_release(self)\n"
              "credential_run.Watchdog.__init__, credential_run.Watchdog.release = init, release\n"
              "def dump():\n"
              f"    with open({str(log)!r}, 'w') as handle:\n"
              "        handle.write(json.dumps(events))\n"
              "atexit.register(dump)\n")


def pause_setup(directory: Path, stage: str, pause: bool) -> str:
    """RUNNER_TEST_SETUP source that replaces the tool's pre_exec_pause: at `stage`, in the forked command, it writes the
    pid, whether each forwarded signal has its default handler, and the blocked signals to directory/state.json, and
    (pause=True) waits there until directory/go exists."""
    state, go = str(directory / "state.json"), str(directory / "go")
    return ("import json, signal, time\n"
            "def pre_exec_pause(stage):\n"
            f"    if stage != {stage!r}:\n"
            "        return\n"
            "    default = {}\n"
            "    for number in credential_run.FORWARDED:\n"
            "        default[signal.Signals(number).name] = signal.getsignal(number) == signal.SIG_DFL\n"
            "    blocked = sorted(int(number) for number in signal.pthread_sigmask(signal.SIG_BLOCK, []))\n"
            f"    with open({state!r}, 'w') as handle:\n"
            "        handle.write(json.dumps({'pid': os.getpid(), 'default': default, 'blocked': blocked}))\n"
            f"    while {pause!r} and not os.path.exists({go!r}):\n"
            "        time.sleep(0.01)\n"
            "credential_run.pre_exec_pause = pre_exec_pause\n")


def unmasked_list() -> str:
    """The "What masking does not cover" list of docs/secret-storage.md#using-a-key, with its whitespace normalised."""
    text = (ROOT / "docs" / "secret-storage.md").read_text(encoding="utf-8")
    start = text.index("**What masking does not cover")
    return " ".join(text[start:text.index("**Units and other clients.**", start)].split())


def xxd(data: bytes) -> str:
    """`xxd` columns: an offset, the bytes in groups of two, and the text of that row."""
    rows = []
    for offset in range(0, len(data), 16):
        row = data[offset:offset + 16]
        rows.append(f"{offset:08x}: " + " ".join(row[i:i + 2].hex() for i in range(0, len(row), 2)).ljust(39)
                    + "  " + row.decode("ascii"))
    return "\n".join(rows)


def hexdump_c(data: bytes) -> str:
    """`hexdump -C` columns: an offset, the bytes in two groups of eight, and the text of that row between bars."""
    rows = []
    for offset in range(0, len(data), 16):
        row = data[offset:offset + 16]
        cells = [f"{byte:02x}" for byte in row]
        rows.append(f"{offset:08x}  " + " ".join(cells[:8]).ljust(23) + "  " + " ".join(cells[8:]).ljust(23)
                    + "  |" + row.decode("ascii") + "|")
    return "\n".join(rows)


def stable_interiors(raw: bytes) -> list[bytes]:
    """The characters of base64/base64url that depend only on raw, at each byte alignment (the test's own copy)."""
    found = []
    for altchars in (None, b"-_"):
        for align in (0, 1, 2):
            encoded = base64.b64encode(b"\0" * align + raw, altchars=altchars)
            found.append(encoded[(0, 2, 3)[align]:(8 * (align + len(raw))) // 6])
    return found


class RunnerCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)
        self.config = self.base / "cfg"
        self.store = self.config / "native-agent-stack"
        self.env = {"PATH": os.environ.get("PATH", ""), "HOME": str(self.base / "home"),
                    "XDG_CONFIG_HOME": str(self.config)}
        self.core_pattern = self.base / "core_pattern"  # read only through the launcher (HOST_PIPES_CORES)
        self.core_pattern.write_text("core\n")
        self.values: list[str] = []  # every planted value, for the never-echoed checks

    def command(self, *args: str, launcher: bool = False) -> list[str]:
        """The argv that starts the runner: the tool itself, or the launcher on a host that pipes crash dumps (and for
        a test that needs the launcher's switch: launcher=True)."""
        if HOST_PIPES_CORES or launcher:
            return [sys.executable, "-I", "-S", "-c", LAUNCHER, *args]
        return [sys.executable, str(TOOL), *args]

    def tool_environment(self, extra: dict | None = None, launcher: bool = False) -> dict:
        environment = {**self.env, **(extra or {})}
        if HOST_PIPES_CORES or launcher:
            environment["CORE_PATTERN_TEST_FILE"] = str(self.core_pattern)
        return environment

    def plant(self, entry_id: str, text: str | bytes, mode: int = 0o600, store: Path | None = None) -> Path:
        store = self.store if store is None else store
        store.mkdir(parents=True, exist_ok=True)
        store.chmod(0o700)
        path = store / f"{entry_id}.env"
        path.write_bytes(text if isinstance(text, bytes) else text.encode("ascii"))
        path.chmod(mode)
        return path

    def tavily(self, value: str | None = None) -> str:
        value = fake("tvly-", "/+=:@" + os.urandom(4).hex()) if value is None else value
        self.values.append(value)
        self.plant("tavily", f"export TAVILY_API_KEY={value}\n")
        return value

    def alpaca(self, base_url: str | None = "https://paper-api.alpaca.markets") -> tuple[str, str]:
        # The second value is not named after what it stands for: CodeQL's py/clear-text-storage-sensitive-data judges a
        # variable by its name, and this one is synthetic (fake()) and written to a temporary store by plant().
        key, second = fake("PK"), fake("", "/x+y=")
        self.values += [key, second]
        text = f"# written by hand\nexport APCA_API_KEY_ID={key}\nexport APCA_API_SECRET_KEY=\"{second}\"\n"
        if base_url is not None:
            text += f"export APCA_API_BASE_URL={base_url}\n"
        self.plant("alpaca-paper", text)
        return key, second

    def run_tool(self, *args: str, input: bytes | None = None, env: dict | None = None,
                 timeout: float = 60, launcher: bool = False) -> subprocess.CompletedProcess:
        stdin = subprocess.DEVNULL if input is None else None
        return subprocess.run(self.command(*args, launcher=launcher), input=input, stdin=stdin, capture_output=True,
                              env=self.tool_environment(env, launcher), timeout=timeout)

    def run_in_process(self, command: list, relay) -> int:
        """run_mod.run_command(command) with `relay` in place of the real one; this process's own handlers for the
        signals it forwards (and for SIGCHLD, which run_command sets) are put back afterwards."""
        for signum in (*run_mod.FORWARDED, signal.SIGCHLD):
            self.addCleanup(signal.signal, signum, signal.getsignal(signum))
        with mock.patch.object(run_mod, "relay", relay):
            return run_mod.run_command(command, {"PATH": os.environ.get("PATH", "")}, [])

    def start_tool(self, *args: str) -> subprocess.Popen:
        process = subprocess.Popen(self.command(*args), stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=self.tool_environment())

        def reap():  # a failed assertion must not leave the runner or its pipes behind
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=30)

        self.addCleanup(reap)
        return process

    def read_until(self, stream, needle: bytes, seconds: float = 20.0) -> bytes:
        """Bytes read from stream until needle arrives (or the deadline passes)."""
        data, deadline = b"", time.monotonic() + seconds
        while needle not in data and time.monotonic() < deadline:
            ready, _, _ = select.select([stream], [], [], 0.2)
            if ready:
                chunk = os.read(stream.fileno(), 65536)
                if not chunk:
                    break
                data += chunk
        return data

    def assert_never_echoed(self, *texts, paths: bool = True):
        # Neither a value nor any six-character piece of one, and (unless a child printed its own environment, which
        # holds this test's HOME) no path under the temporary store.
        for text in texts:
            text = text.decode("latin-1") if isinstance(text, bytes) else text
            if paths:
                self.assertNotIn(str(self.base), text)
            for value in self.values:
                self.assertNotIn(value, text)
                pieces = {value[i:i + 6] for i in range(len(value) - 5)}
                self.assertEqual(sorted(piece for piece in pieces if piece in text), [])


class InjectionTests(RunnerCase):
    def test_injects_only_the_ids_declared_variables(self):
        key, secret = self.alpaca()
        names = ["APCA_API_KEY_ID", "APCA_API_SECRET_KEY", "APCA_API_BASE_URL", "TAVILY_API_KEY", "SEC_USER_AGENT"]
        result = self.run_tool("alpaca-paper", *py(REPORT, json.dumps(names)))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {
            "APCA_API_KEY_ID": sha(key), "APCA_API_SECRET_KEY": sha(secret),
            "APCA_API_BASE_URL": sha("https://paper-api.alpaca.markets"), "TAVILY_API_KEY": None,
            "SEC_USER_AGENT": None})
        self.assertEqual(result.stderr, b"")  # no banner, no path
        # The public base URL is injected unmasked; the key pair is masked.
        shown = self.run_tool("alpaca-paper", *py(
            "import os\nfor n in ('APCA_API_KEY_ID', 'APCA_API_SECRET_KEY', 'APCA_API_BASE_URL'):\n"
            "    print(n + '=' + os.environ[n])\n"))
        self.assertEqual(shown.stdout, b"APCA_API_KEY_ID=[REDACTED:APCA_API_KEY_ID]\n"
                                       b"APCA_API_SECRET_KEY=[REDACTED:APCA_API_SECRET_KEY]\n"
                                       b"APCA_API_BASE_URL=https://paper-api.alpaca.markets\n")
        self.assert_never_echoed(result.stdout, result.stderr, shown.stdout, shown.stderr)

    def test_strips_other_inventory_names_from_the_child(self):
        value = self.tavily()
        # The pointer variables of the other entries (paths of their store files, which the documented shell profile sets
        # for the paper units and the research scripts) are stripped too: `tavily` declares none, and a command run under
        # it must not load another entry's file through one.
        pointers = {"PAPER_ENV_FILE": "/nonexistent/p.env", "ENV_FILE": "/nonexistent/e.env",
                    "PIT_ALPACA_ENV_PATH": "/nonexistent/a.env", "PAPER_ENV_FILE_2": "/nonexistent/p2.env",
                    "SEC_CONTACT_ENV": "/nonexistent/s.env", "PIT_SEC_ENV_PATH": "/nonexistent/t.env",
                    "HF_TOKEN_PATH": "/nonexistent/hf"}
        stray = {"TAVILY_API_KEY": fake("tvly-"), "APCA_API_KEY_ID": fake("PK"), "APCA_API_SECRET_KEY": fake(),
                 "GF_SECURITY_ADMIN_PASSWORD": fake(), "GITHUB_TOKEN": fake("ghp_"), "OPENAI_API_KEY": fake("sk-"),
                 "ALPACA_API_KEY": fake(), "UNRELATED_SETTING": "kept-as-is", **pointers}
        self.values += [v for k, v in stray.items() if k != "UNRELATED_SETTING" and k not in pointers]
        result = self.run_tool("tavily", *py(REPORT, json.dumps(sorted(stray))), env=stray)
        self.assertEqual(result.returncode, 0, result.stderr)
        seen = json.loads(result.stdout)
        self.assertEqual(seen.pop("TAVILY_API_KEY"), sha(value))  # the file's value, never the caller's
        self.assertEqual(seen.pop("UNRELATED_SETTING"), sha("kept-as-is"))
        self.assertEqual(seen, dict.fromkeys(seen))  # every other inventory, pointer and must_not_be_set name is gone
        self.assertTrue(set(pointers) <= set(seen))
        self.assert_never_echoed(result.stdout, result.stderr)

    def test_only_the_selected_entrys_own_pointer_variables_stay_in_the_child(self):
        # Inventory-driven: for every injectable id, with every pointer variable of the inventory set in the caller's
        # environment, the command keeps exactly the pointers that entry declares (its own store file's path) and loses
        # every other entry's.
        inventory = json.loads((ROOT / "adoption/credential-inventory.json").read_text(encoding="utf-8"))
        everything = sorted({name for entry in inventory["entries"] for name in entry["pointer_variables"]})
        caller = {name: f"/nonexistent/{name.lower()}" for name in everything}
        injectable = [entry for entry in inventory["entries"] if run_mod.injectable(entry)]
        self.assertGreaterEqual(len(everything), 7)
        self.assertEqual({entry["id"] for entry in injectable}, INJECTABLE_IDS)
        for entry in injectable:
            with self.subTest(id=entry["id"]):
                declared = entry["variables"] + entry["optional_variables"]
                self.plant(entry["id"], "".join(f"export {name}={fake('v-')}\n" for name in declared))
                result = self.run_tool(entry["id"], *py(REPORT, json.dumps(everything)), env=caller)
                self.assertEqual(result.returncode, 0, result.stderr)
                expected = {name: sha(caller[name]) if name in entry["pointer_variables"] else None
                            for name in everything}
                self.assertEqual(json.loads(result.stdout), expected)

    def test_only_narrows_to_declared_names(self):
        key, _secret = self.alpaca()
        names = json.dumps(["APCA_API_KEY_ID", "APCA_API_SECRET_KEY", "APCA_API_BASE_URL"])
        result = self.run_tool("alpaca-paper", "--only", "APCA_API_KEY_ID", *py(REPORT, names))
        self.assertEqual(json.loads(result.stdout), {"APCA_API_KEY_ID": sha(key), "APCA_API_SECRET_KEY": None,
                                                     "APCA_API_BASE_URL": None})
        both = self.run_tool("alpaca-paper", "--only", "APCA_API_KEY_ID", "--only", "APCA_API_BASE_URL",
                             *py(REPORT, names))
        self.assertEqual(json.loads(both.stdout)["APCA_API_SECRET_KEY"], None)
        self.assertEqual(json.loads(both.stdout)["APCA_API_BASE_URL"], sha("https://paper-api.alpaca.markets"))
        # A name the entry does not declare (another entry's, or a value pasted where a name belongs) is a usage
        # error that never repeats the word.
        pasted = fake("PK").upper()
        self.values.append(pasted)
        for word in ("TAVILY_API_KEY", pasted):
            refused = self.run_tool("alpaca-paper", "--only", word, "--", "true")
            self.assertEqual(refused.returncode, 2, refused.stderr)
            self.assertNotIn(word.encode(), refused.stdout + refused.stderr)
            self.assertIn(b"APCA_API_KEY_ID, APCA_API_SECRET_KEY, APCA_API_BASE_URL", refused.stderr)
        self.assertEqual(self.run_tool("alpaca-paper", "--only").returncode, 2)
        # A declared optional variable that the file does not hold is refused, not silently left out.
        self.alpaca(base_url=None)
        absent = self.run_tool("alpaca-paper", "--only", "APCA_API_BASE_URL", "--", "true")
        self.assertEqual(absent.returncode, 1)
        self.assertIn(b"only_variable_absent: APCA_API_BASE_URL", absent.stderr)
        self.assert_never_echoed(result.stdout, both.stdout, refused.stderr, absent.stderr)

    def test_parser_never_expands(self):
        # Characters a shell would expand or glob, inside a quoted value, reach the child literally.
        quoted = fake("q-") + " ~/x * ? [a] {b} ! # % & ( ) | < > ; ' , ^ " + fake()
        single = "single quoted " + fake()
        contact = "Jane Tester jane.tester@example.invalid " + fake()
        self.values += [quoted, single, contact]
        self.plant("tavily", f'export TAVILY_API_KEY="{quoted}"\n')
        self.plant("sec-contact", f"export SEC_USER_AGENT='{single}'\n  export EDGAR_IDENTITY=\"{contact}\"  \n")
        tavily = self.run_tool("tavily", *py(REPORT, '["TAVILY_API_KEY"]'))
        self.assertEqual(json.loads(tavily.stdout), {"TAVILY_API_KEY": sha(quoted)}, tavily.stderr)
        sec = self.run_tool("sec-contact", *py(REPORT, '["SEC_USER_AGENT", "EDGAR_IDENTITY"]'))
        self.assertEqual(json.loads(sec.stdout), {"SEC_USER_AGENT": sha(single), "EDGAR_IDENTITY": sha(contact)})
        # Both are masked, including the form-encoded (space as +) copy of the contact.
        spaced = self.run_tool("sec-contact", *py(
            "import os, urllib.parse\nv = os.environ['EDGAR_IDENTITY']\nprint(v)\nprint(urllib.parse.quote_plus(v))\n"))
        self.assertEqual(spaced.stdout, b"[REDACTED:EDGAR_IDENTITY]\n[REDACTED:EDGAR_IDENTITY]\n")
        self.assert_never_echoed(tavily.stdout, tavily.stderr, sec.stdout, sec.stderr, spaced.stdout)


class RefusalTests(RunnerCase):
    def test_refuses_unknown_bad_and_engine_only_ids(self):
        marker = self.base / "child-ran"
        child = py(f"open({str(marker)!r}, 'w').close()")
        for bad in ("Tavily", "../tavily", "tavily;id", "tavily env", "", "TAVILY_API_KEY", "tvly_x"):
            with self.subTest(id=bad):
                result = self.run_tool(bad, *child)
                self.assertEqual(result.returncode, 2, result.stderr)
                if bad:
                    self.assertNotIn(bad.encode(), result.stdout + result.stderr)
        pasted = fake("tvly-")  # a lowercase value typed where the id belongs matches the id pattern
        self.values.append(pasted)
        for unknown in ("no-such-entry", "get", "print", "list", "token", pasted):
            with self.subTest(id=unknown):
                result = self.run_tool(unknown, *child)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn(b"unknown inventory id", result.stderr)
                self.assertNotIn(unknown.encode(), result.stdout + result.stderr)
        for held in NOT_INJECTABLE_IDS:
            with self.subTest(id=held):
                result = self.run_tool(held, *child)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn(f"credential_run: {held}: refused: not_injectable".encode(), result.stderr)
        # The hint names the engine or native client that holds the key.
        self.assertIn(b"observability/backends/configure.py", self.run_tool("grafana-admin", *child).stderr)
        self.assertIn(b"(claude)", self.run_tool("claude-native", *child).stderr)
        self.assertIn(b"GitHub Actions", self.run_tool("github-actions", *child).stderr)
        self.assertFalse(marker.exists(), "a refused run started its command")

    def test_refuses_unsafe_files(self):
        self.tavily()
        path = self.store / "tavily.env"
        marker = self.base / "child-ran"
        child = py(f"open({str(marker)!r}, 'w').close()")
        outputs = []

        def refused(reason: bytes, **kwargs):
            result = self.run_tool("tavily", *child, timeout=20, **kwargs)
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn(b"credential_run: tavily: unsafe: " + reason, result.stderr)
            outputs.extend((result.stdout, result.stderr))

        path.chmod(0o644)
        refused(b"mode_not_0600")
        path.chmod(0o600)
        aside = self.base / "aside.env"
        os.replace(path, aside)
        os.symlink(aside, path)
        refused(b"symlink_refused")
        path.unlink()
        os.replace(aside, path)
        os.link(path, self.store / "second-name")
        refused(b"hard_link")
        (self.store / "second-name").unlink()
        self.store.chmod(0o755)
        refused(b"store_directory_not_private")
        self.store.chmod(0o700)
        path.rename(aside)
        os.mkfifo(path, 0o600)  # a FIFO would block a plain open(); it is refused without waiting for a writer
        refused(b"not_regular_file")
        path.unlink()
        path.write_text("#" * (64 * 1024) + "\n")
        path.chmod(0o600)
        refused(b"too_large")
        path.unlink()
        os.replace(aside, path)
        moved = self.config / "real-store"
        os.replace(self.store, moved)
        os.symlink(moved, self.store)
        refused(b"store_directory_symlink")
        self.store.unlink()
        os.replace(moved, self.store)
        repo = self.base / "repo"
        (repo / ".git").mkdir(parents=True)
        self.plant("tavily", path.read_bytes(), store=repo / "cfg" / "native-agent-stack")
        refused(b"inside_git_worktree", env={"XDG_CONFIG_HOME": str(repo / "cfg")})
        self.assertFalse(marker.exists(), "a refused run started its command")
        self.assert_never_echoed(*outputs)

    def test_refuses_lines_outside_the_grammar(self):
        value = fake("tvly-")
        as_name = value.upper().replace("-", "_")  # a value pasted where a name belongs
        self.values += [value, as_name]
        cases = [
            (f"TAVILY_API_KEY={value}\n", 1, b"not_an_export_line"),
            (f"# a comment\n\nexport TAVILY_API_KEY {value}\n", 3, b"not_an_export_line"),
            (f"set -a\nexport TAVILY_API_KEY={value}\n", 1, b"not_an_export_line"),
            (f"export TAVILY_API_KEY={value}\n. other.env\n", 2, b"not_an_export_line"),
            (f"export TAVILY_API_KEY={value}\r\n", 1, b"control_character"),
            (f"export TAVILY_API_KEY=\t{value}\n", 1, b"control_character"),
            (f"export TAVILY_API_KEY={value}\x00\n", 1, b"control_character"),
            (f"export TAVILY_API_KEY={value}\nexport TAVILY_API_KEY={value}\n", 2, b"duplicate_variable"),
            (f"export TAVILY_API_KEY={value}\nexport {as_name}=x\n", 2, b"undeclared_variable"),
            ("export TAVILY_API_KEY=\n", 1, b"empty_value"),
            ('export TAVILY_API_KEY=""\n', 1, b"empty_value"),
        ]
        outputs = []
        for text, line, reason in cases:
            with self.subTest(text=text.replace(value, "<value>").replace(as_name, "<value>")):
                self.plant("tavily", text)
                result = self.run_tool("tavily", "--", "true")
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn(b"line %d: %s" % (line, reason), result.stderr)
                outputs.extend((result.stdout, result.stderr))
        self.plant("tavily", b"export TAVILY_API_KEY=" + value.encode() + b"\xc3\xa9\n")
        result = self.run_tool("tavily", "--", "true")
        self.assertIn(b"line 1: not_ascii", result.stderr)
        self.plant("tavily", "# nothing stored\n")
        missing = self.run_tool("tavily", "--", "true")
        self.assertEqual(missing.returncode, 1)
        self.assertIn(b"credential_run: tavily: missing: required_variable_missing: TAVILY_API_KEY", missing.stderr)
        self.assert_never_echoed(*outputs, result.stderr, missing.stderr)
        for text in outputs:
            self.assertIsNone(STORE_LINE.search(text))  # never a store line

    def test_refuses_values_outside_the_writer_grammar(self):
        # R8: the reader shares set_credential.py's grammar, so a hand edit cannot smuggle shell syntax into a value;
        # the value is refused, never expanded or run.
        ran = self.base / "value-ran"
        marker = self.base / "child-ran"
        child = py(f"open({str(marker)!r}, 'w').close()")
        tail = fake()
        values = [f"abc$(touch {ran}){tail}", f'"abc$(touch {ran}){tail}"', f"abc`touch {ran}`{tail}",
                  f'"abc`touch {ran}`{tail}"', f"abc\\{tail}", f'"abc\\n{tail}"', f'"abc"def{tail}"',
                  f"abc def{tail}", f"abc;touch {ran};{tail}", f"'abc'def{tail}'", f"${{HOME}}{tail}",
                  f'"${{HOME}}{tail}"', f"'$HOME-{tail}'", f'"  {tail}"', f"~/{tail}", f'"{tail}', f"'{tail}"]
        outputs = []
        for raw in values:
            with self.subTest(value=raw.replace(tail, "<tail>")):
                self.plant("tavily", f"export TAVILY_API_KEY={raw}\n")
                result = self.run_tool("tavily", *child)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn(b"credential_run: tavily: unsafe: line 1: outside_writer_grammar", result.stderr)
                self.assertNotIn(raw.encode(), result.stdout + result.stderr)
                outputs.extend((result.stdout, result.stderr))
        self.assertFalse(ran.exists(), "a value was executed")
        self.assertFalse(marker.exists(), "a refused run started its command")
        self.values.append(tail)
        self.assert_never_echoed(*outputs)

    def test_a_planted_entry_declaring_a_reserved_name_is_refused(self):
        # LD_*, DYLD_* and PYTHON* are read by the dynamic loader and the interpreter at start-up (and echoed on error,
        # scripts/kernel_keyring.py): a stored value under one would run code in the command. The schema accepts such a
        # name, so a planted inventory entry that declares one is refused by the runner, before it reads any store.
        def planted(**changes) -> dict:
            return {"id": "planted", "status": "required", "loaders": [], "store": {"kind": "private_env_file"},
                    "variables": ["PLANTED_KEY"], "optional_variables": [], "public_variables": [], **changes}

        def run_planted(entry: dict) -> tuple:
            out, err = io.StringIO(), io.StringIO()
            with mock.patch.object(run_mod, "load_inventory", return_value={"entries": [entry]}), \
                    mock.patch.object(run_mod, "read_store", side_effect=AssertionError("the store was read")), \
                    contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = run_mod.main(["planted", "--", "true"])
            return code, out.getvalue(), err.getvalue()

        for name in ("LD_PRELOAD", "LD_LIBRARY_PATH", "DYLD_INSERT_LIBRARIES", "PYTHONPATH", "PYTHONSTARTUP", "PYTHON_X"):
            for where in ("variables", "optional_variables"):
                with self.subTest(name=name, where=where):
                    code, out, err = run_planted(planted(**{where: [name]}))
                    self.assertEqual((code, out), (1, ""))
                    self.assertIn(f"credential_run: planted: refused: reserved_variable: {name}", err)
        # Only those prefixes: a name that merely starts alike is not reserved, and check_injectable lets it through.
        for name in ("LDAP_BIND_KEY", "LDX_KEY", "DYLDX_KEY", "PYTHA_KEY", "MY_PYTHON_KEY"):
            with self.subTest(name=name):
                run_mod.check_injectable(planted(variables=[name]))

    def test_short_values_are_refused(self):
        # Buildkite's LengthMin: a masked value under 6 bytes would mask ordinary output, so it is refused.
        self.plant("tavily", "export TAVILY_API_KEY=abcde\n")
        short = self.run_tool("tavily", "--", "true")
        self.assertEqual(short.returncode, 1)
        self.assertIn(b"credential_run: tavily: unsafe: value_too_short_to_mask: TAVILY_API_KEY", short.stderr)
        self.assertNotIn(b"abcde", short.stdout + short.stderr)
        self.plant("tavily", "export TAVILY_API_KEY=abcdef\n")
        self.assertEqual(self.run_tool("tavily", "--", "true").returncode, 0)
        # A masked optional variable counts too; a public one is not masked, so any length passes.
        self.plant("sec-contact", f'export SEC_USER_AGENT="{fake("Jane ")}"\nexport EDGAR_IDENTITY=abc\n')
        optional = self.run_tool("sec-contact", "--", "true")
        self.assertIn(b"value_too_short_to_mask: EDGAR_IDENTITY", optional.stderr)
        self.alpaca(base_url="x")
        self.assertEqual(self.run_tool("alpaca-paper", "--", "true").returncode, 0)

    def test_usage_errors_never_repeat_arguments(self):
        self.tavily()
        pasted = fake("--tvly-")
        self.values.append(pasted)
        for args in ((), ("tavily",), ("tavily", "--"), ("tavily", pasted, "--", "true"),
                     ("tavily", "--check", "--", "true"), ("tavily", "--only"), ("tavily", "true")):
            with self.subTest(args=len(args)):
                result = self.run_tool(*args)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn(b"usage:", result.stderr)
                self.assert_never_echoed(result.stdout, result.stderr)
        for flag in ("--help", "-h"):
            shown = self.run_tool(flag)
            self.assertEqual((shown.returncode, shown.stderr), (0, b""))
            self.assertIn(b"credential_run.py <inventory-id> [--only NAME]... -- <command> [args...]", shown.stdout)

    def test_spawn_failures_have_their_own_codes(self):
        self.tavily()
        plain = self.base / "not-executable"
        plain.write_text("#!/bin/sh\necho no\n")
        plain.chmod(0o644)
        for command, code in (("/nonexistent/no-such-command", 127), (str(plain), 126), (str(self.base), 126)):
            with self.subTest(code=code):
                result = self.run_tool("tavily", "--", command)
                self.assertEqual(result.returncode, code, result.stderr)
                self.assertIn(b"credential_run: tavily: cannot start the command", result.stderr)
                self.assert_never_echoed(result.stdout, result.stderr)


class MaskingTests(RunnerCase):
    def test_masks_raw_and_encoded_forms_on_both_streams(self):
        value = self.tavily()
        result = self.run_tool("tavily", *py(FORMS))
        self.assertEqual(result.returncode, 0, result.stderr)
        for stream in (result.stdout, result.stderr):
            lines = stream.splitlines()
            self.assertEqual(len(lines), 16)
            for line in lines:
                self.assertIn(MARK, line)  # every printed form was masked
            for form in stable_interiors(value.encode()):
                self.assertNotIn(form, stream)
            hex_form = value.encode().hex()
            for start in range(0, len(hex_form) - 11):  # no six value bytes in hex, either case
                self.assertNotIn(hex_form[start:start + 12].encode(), stream.lower())
        self.assert_never_echoed(result.stdout, result.stderr)

    def test_an_environment_dump_shows_masked_values(self):
        self.tavily()
        dump = self.run_tool("tavily", *py("import os\nfor k, v in sorted(os.environ.items()):\n    print(k + '=' + v)\n"))
        self.assertIn(b"TAVILY_API_KEY=" + MARK + b"\n", dump.stdout)
        commands = [["--", shutil.which("env") or "/usr/bin/env"], ["--", shutil.which("printenv") or "printenv"]]
        for command in commands:
            result = self.run_tool("tavily", *command)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(b"TAVILY_API_KEY=" + MARK, result.stdout)
            self.assert_never_echoed(result.stdout, result.stderr, paths=False)
        self.assert_never_echoed(dump.stdout, dump.stderr, paths=False)

    def test_masks_a_value_split_across_writes(self):
        self.tavily()
        code = ("import os, sys, time\nv = os.environ['TAVILY_API_KEY']\nh = len(v) // 2\n"
                "for s in (sys.stdout, sys.stderr):\n    s.write('before ' + v[:h]); s.flush()\n"
                "time.sleep(0.4)\n"
                "for s in (sys.stdout, sys.stderr):\n    s.write(v[h:] + ' after\\n'); s.flush()\n")
        result = self.run_tool("tavily", *py(code))
        self.assertEqual(result.stdout, b"before " + MARK + b" after\n")
        self.assertEqual(result.stderr, b"before " + MARK + b" after\n")
        self.assert_never_echoed(result.stdout, result.stderr)

    def test_flushes_an_unterminated_tail_at_eof(self):
        self.tavily()
        # "d" starts the base64 of every Tavily key ("tvly-") and "t" the key itself: a last byte that could begin a
        # value's form is held, then written at the end, because a tail of 3 bytes or less is not held back for good.
        plain = self.run_tool("tavily", *py("import sys\nsys.stdout.write('no newline at the end')\n"))
        self.assertEqual(plain.stdout, b"no newline at the end")
        last_t = self.run_tool("tavily", *py("import sys\nsys.stdout.write('ends with t')\n"))
        self.assertEqual(last_t.stdout, b"ends with t")
        whole = self.run_tool("tavily", *py("import os, sys\nsys.stdout.write('key ' + os.environ['TAVILY_API_KEY'])\n"))
        self.assertEqual(whole.stdout, b"key " + MARK)
        # A held tail (the start of the value) is never printed at EOF: it becomes a partial marker.
        held = self.run_tool("tavily", *py("import os, sys\nsys.stdout.write('tail ' + os.environ['TAVILY_API_KEY'][:9])\n"))
        self.assertEqual(held.stdout, b"tail " + PARTIAL)
        self.assert_never_echoed(plain.stdout, whole.stdout, held.stdout)

    def test_idle_flush_is_bounded(self):
        value = self.tavily()
        # A held tail of 3 bytes or less is written after about 100 ms without new data, while the child still runs;
        # the rest of the value is still masked when it arrives later.
        short = self.start_tool("tavily", *py(
            "import os, sys, time\nv = os.environ['TAVILY_API_KEY']\n"
            "sys.stdout.write(v[:3]); sys.stdout.flush(); time.sleep(3)\n"
            "sys.stdout.write(v[3:] + '\\n')\n"))
        started = time.monotonic()
        early = self.read_until(short.stdout, value[:3].encode(), seconds=2.5)
        self.assertEqual(early, value[:3].encode())
        self.assertLess(time.monotonic() - started, 2.5)
        rest, _ = short.communicate(timeout=30)
        self.assertEqual(early + rest, value[:3].encode() + MARK + b"\n")
        # A held tail of 4 bytes or more is never written on the idle timer.
        long = self.start_tool("tavily", *py(
            "import os, sys, time\nv = os.environ['TAVILY_API_KEY']\n"
            "sys.stdout.write('x' + v[:8]); sys.stdout.flush(); time.sleep(2.5)\nsys.stdout.write('\\n')\n"))
        first = self.read_until(long.stdout, b"never-arrives", seconds=1.5)
        self.assertEqual(first, b"x")
        rest, _ = long.communicate(timeout=30)
        self.assertEqual(first + rest, b"x" + value[:8].encode() + b"\n")  # released once the next byte ends the match

    def test_a_child_killed_mid_write_never_prints_a_held_partial(self):
        self.tavily()
        killed = self.run_tool("tavily", *py(
            "import os, signal, sys, time\nv = os.environ['TAVILY_API_KEY']\n"
            "sys.stdout.write('partial ' + v[:len(v) // 2]); sys.stdout.flush(); time.sleep(0.3)\n"
            "os.kill(os.getpid(), signal.SIGKILL)\n"))
        self.assertEqual(killed.returncode, 128 + signal.SIGKILL)
        self.assertEqual(killed.stdout, b"partial " + PARTIAL)
        # The runner itself is stopped: it forwards the signal, and the child's held partial is still never printed.
        runner = self.start_tool("tavily", *py(
            "import os, sys, time\nv = os.environ['TAVILY_API_KEY']\n"
            "sys.stdout.write('ready\\n' + v[:10]); sys.stdout.flush(); time.sleep(30)\n"))
        ready = self.read_until(runner.stdout, b"ready\n")
        time.sleep(0.3)
        runner.send_signal(signal.SIGTERM)
        rest, err = runner.communicate(timeout=30)
        self.assertEqual(runner.returncode, 128 + signal.SIGTERM)
        self.assertEqual(ready + rest, b"ready\n" + PARTIAL)
        self.assert_never_echoed(killed.stdout, killed.stderr, ready + rest, err)

    def test_non_utf8_bytes_pass_through_intact(self):
        self.tavily()
        result = self.run_tool("tavily", *py(
            "import os, sys\nv = os.environ['TAVILY_API_KEY'].encode()\n"
            "sys.stdout.buffer.write(b'\\xff\\xfex' + v + b'\\x80\\xc3\\x28\\n')\n"
            "sys.stderr.buffer.write(b'\\xed\\xa0\\x80' + v + b'\\x00\\n')\n"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, b"\xff\xfex" + MARK + b"\x80\xc3\x28\n")
        self.assertEqual(result.stderr, b"\xed\xa0\x80" + MARK + b"\x00\n")

    def test_masker_merges_overlaps_and_never_cuts_a_match(self):
        # In process: a complete short match inside a longer needle's partial is held with it, then masked as one.
        masker = run_mod.Masker([(b"abcdef", "SHORT"), (b"abcdefgh12", "LONG")])
        out = masker.feed(b"x abcdefgh1", 0.0)
        self.assertEqual(out, b"x ")
        out += masker.feed(b"2 y\n", 0.0)
        self.assertEqual(out, b"x [REDACTED:LONG] y\n")
        overlapping = run_mod.Masker([(b"abcdef", "A"), (b"defghi", "B")])
        self.assertEqual(overlapping.feed(b"<abcdefghi>\n", 0.0) + overlapping.close(), b"<[REDACTED:A]>\n")
        # A complete match that runs into a held tail is held with it (dotenvx safeBoundary): cutting there would mask
        # A and then print its last bytes "def" raw once "X" ends B's partial match.
        straddle = run_mod.Masker([(b"abcdef", "A"), (b"defghijk", "B")])
        self.assertEqual(straddle.feed(b"abcdefgh", 0.0) + straddle.feed(b"X\n", 0.0), b"[REDACTED:A]ghX\n")
        # After an idle flush of a short tail, the rest of the value is still masked.
        tail = run_mod.Masker([(b"abcdefgh", "K")])
        self.assertEqual(tail.feed(b"abc", 1.0), b"")
        self.assertEqual(tail.idle_due(), 1.0 + run_mod.IDLE_FLUSH_SECONDS)
        self.assertEqual(tail.idle_flush(), b"abc")
        self.assertEqual(tail.feed(b"defgh\n", 2.0), b"[REDACTED:K]\n")
        # A held tail of 4 bytes or more is never written, on the timer or at the end; a shorter one is, both ways.
        held = run_mod.Masker([(b"abcdefgh", "K")])
        self.assertEqual(held.feed(b"abcd", 1.0), b"")
        self.assertIsNone(held.idle_due())
        self.assertEqual(held.close(), b"[REDACTED-PARTIAL:K]")
        short = run_mod.Masker([(b"abcdefgh", "K")])
        self.assertEqual(short.feed(b"the end: abc", 1.0) + short.close(), b"the end: abc")
        continued = run_mod.Masker([(b"abcdefgh", "K")])
        self.assertEqual(continued.feed(b"abc", 1.0) + continued.idle_flush() + continued.feed(b"d", 2.0)
                         + continued.close(), b"abc[REDACTED-PARTIAL:K]")


MARKER = re.compile(rb"\[REDACTED(?:-PARTIAL)?:[A-Z0-9_]+\]")


def naive_mask(needles: list, data: bytes) -> bytes:
    """The whole-buffer masker, written again here: every occurrence of every needle, overlapping and touching ones
    merged into one range named after its earliest longest match, replaced by a marker."""
    found = []
    for needle, name in needles:
        at = data.find(needle)
        while at != -1:
            found.append((at, at + len(needle), name))
            at = data.find(needle, at + 1)
    merged = []
    for start, end, name in sorted(found, key=lambda item: (item[0], item[0] - item[1])):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end, name])
    out, at = [], 0
    for start, end, name in merged:
        out += [data[at:start], b"[REDACTED:" + name.encode() + b"]"]
        at = end
    return b"".join(out) + data[at:]


def stream_through(needles: list, data: bytes, rng, biggest: int) -> tuple:
    """(output, largest retained size): data fed in random chunks, then closed."""
    masker = run_mod.Masker(needles)
    out, retained, at = [], 0, 0
    while at < len(data):
        size = rng.randint(1, biggest)
        out.append(masker.feed(data[at:at + size], 0.0))
        retained = max(retained, len(masker.buf))
        at += size
    out.append(masker.close())
    return b"".join(out), retained


def lower_hex(text: str) -> str:
    return re.sub(r"%[0-9A-F]{2}", lambda match: match.group().lower(), text)


def real_encodings(text: str) -> dict:
    """The forms the common percent and JSON encoders print for text. The urllib.parse and json.dumps forms are the
    output of the real functions. The PHP json_encode (`\\/`), Go encoding/json (HTML escapes) and PHP JSON_HEX_TAG
    forms are string replacements that model what those encoders write: no PHP or Go encoder is run here."""
    plain = json.dumps(text)[1:-1]
    slashes = plain.replace("/", "\\/")
    forms = {"urllib.parse.quote": urllib.parse.quote(text),
             "quote safe=''": urllib.parse.quote(text, safe=""),
             "quote_plus": urllib.parse.quote_plus(text),
             "quote_plus safe='/'": urllib.parse.quote_plus(text, safe="/"),
             "json.dumps": plain,
             "PHP json_encode": slashes}
    for label in ("urllib.parse.quote", "quote safe=''", "quote_plus", "quote_plus safe='/'"):
        forms[label + " lower"] = lower_hex(forms[label])
    for label, base in (("Go json.Marshal", plain), ("PHP json_encode + Go escapes", slashes)):
        forms[label] = base.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    forms["PHP JSON_HEX_TAG|JSON_HEX_AMP"] = plain.replace("<", "\\u003C").replace(">", "\\u003E").replace("&", "\\u0026")
    return forms


# The same encoders inside a child, which prints each form of its own key after "form ".
ENCODERS = ("import json, os, re, sys, urllib.parse as u\n"
            "v = os.environ['TAVILY_API_KEY']\n"
            "low = lambda s: re.sub('%[0-9A-F]{2}', lambda m: m.group().lower(), s)\n"
            "j = json.dumps(v)[1:-1]\n"
            "s = j.replace('/', '\\\\/')\n"
            "go = lambda t: t.replace('<', '\\\\u003c').replace('>', '\\\\u003e').replace('&', '\\\\u0026')\n"
            "forms = [u.quote(v), u.quote(v, safe=''), u.quote_plus(v), u.quote_plus(v, safe='/'), j, s, go(j), go(s)]\n"
            "forms += [low(f) for f in forms[:4]]\n"
            "for stream in (sys.stdout, sys.stderr):\n"
            "    for f in forms:\n"
            "        stream.write('form ' + f + '\\n')\n")


class EncodedFormTests(RunnerCase):
    """Review of 2026-09-29, finding 3: the common percent and JSON encoders differ in ways the masker must cover
    (quote() keeps '/' by default, quote_plus() writes a space as '+', PHP writes '\\/', Go writes \\u003c). The
    Python encoders are executed; the PHP and Go JSON forms are string-replacement models of their output."""

    def samples(self) -> list:
        return [fake("tvly-", "/+=:@" + os.urandom(4).hex()),  # the bare grammar: + / = : @ . _ -
                fake("q-") + " a/b+c=d:e@f <x> & y'z " + fake()]  # a quoted value: a space, < > & and '

    def test_the_percent_and_json_encoder_forms_are_masked_in_process(self):
        for text in self.samples():
            forms = real_encodings(text)
            needles = run_mod.needles_for({"K": text}, ["K"])
            for label, form in forms.items():
                with self.subTest(form=label, value_kind="quoted" if " " in text else "bare"):
                    masker = run_mod.Masker(needles)
                    out = masker.feed(b"form " + form.encode("ascii") + b"\n", 0.0) + masker.close()
                    self.assertEqual(out, b"form [REDACTED:K]\n")
            # The forms really differ (else the test would prove nothing), and each is a whole-value needle.
            self.assertGreaterEqual(len(set(forms.values())), 8 if " " in text else 6)

    def test_the_percent_and_json_encoder_forms_are_masked_end_to_end(self):
        for text in self.samples():
            with self.subTest(value_kind="quoted" if " " in text else "bare"):
                self.plant("tavily", f'export TAVILY_API_KEY="{text}"\n' if " " in text
                           else f"export TAVILY_API_KEY={text}\n")
                self.values.append(text)
                result = self.run_tool("tavily", *py(ENCODERS))
                self.assertEqual(result.returncode, 0, result.stderr)
                for stream in (result.stdout, result.stderr):
                    lines = stream.splitlines()
                    self.assertEqual(len(lines), 12)
                    self.assertEqual(set(lines), {b"form " + MARK})  # nothing but the marker, in every encoding
                self.assert_never_echoed(result.stdout, result.stderr)

    def print_forms(self, forms: list) -> None:
        """Every (phrase, form) is one item of the documentation's list of what masking does not cover: the list names
        it (by the phrase), and the runner prints the form as it is."""
        listed = unmasked_list()
        for phrase, _form in forms:
            self.assertIn(phrase, listed, "docs/secret-storage.md no longer names an unmasked form that a test prints")
        code = "import sys\nfor form in %r:\n    print('form', form)\n" % ([form for _phrase, form in forms],)
        result = self.run_tool("tavily", *py(code))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "".join(f"form {form}\n" for _phrase, form in forms).encode())

    def test_forms_the_documentation_lists_as_unmasked_are_printed_as_they_are(self):
        # docs/secret-storage.md#using-a-key lists what masking does not cover, with the rule that a value is masked
        # only where a whole form of it appears unbroken in one stream. Each form below is an item of that list, which
        # the test reads. If a change starts masking one of them, this test and that list change together.
        text = fake("tvly-", "/+=:@" + os.urandom(4).hex())
        self.tavily(text)
        b64 = base64.b64encode(text.encode()).decode()
        self.print_forms([
            ("base64 wrapped across lines", "\n".join(b64[i:i + 16] for i in range(0, len(b64), 16))),
            ("nested encoding", urllib.parse.quote(urllib.parse.quote(text, safe=""), safe="")),
            ("Gson", text.replace("=", "\\u003d")),  # Gson's default escaping of '='
            ("safe set", urllib.parse.quote(text, safe="/+")),  # a safe set that neither quote() default uses
            ("fragment", text[:12] + "..." + text[-6:]),
            ("fold", "\n".join(text[i:i + 16] for i in range(0, len(text), 16))),  # wrapped
            ("xxd", xxd(text.encode())),
            ("hexdump -C", hexdump_c(text.encode())),
            ("wrapped table cells", "| " + text[:20] + " |\n| " + text[20:] + " |"),
            ("colour codes", text[:9] + "\x1b[0m" + text[9:]),
            ("hex with separators", text.encode().hex(":")),
        ])

    def test_a_value_the_shell_requotes_because_of_a_single_quote_is_printed_as_it_is(self):
        # A quoted store value may hold a single quote; set -x and printf %q write it as '\'' and \' (also shlex.quote).
        text = fake("q-") + "a'b" + fake()
        self.plant("tavily", f'export TAVILY_API_KEY="{text}"\n')
        self.print_forms([("set -x", "'" + text.replace("'", "'\\''") + "'"),
                          ("printf %q", text.replace("'", "\\'")),
                          ("set -x", shlex.quote(text))])

    def test_a_value_interleaved_with_the_bytes_of_a_second_writer_on_the_stream_is_printed_as_it_is(self):
        text = self.tavily()
        self.assertIn("two writers", unmasked_list())
        other = "import sys\nsys.stdout.write('<other writer>')\n"
        result = self.run_tool("tavily", *py(
            "import os, subprocess, sys\nv = os.environ['TAVILY_API_KEY']\nh = len(v) // 2\n"
            "sys.stdout.write(v[:h])\nsys.stdout.flush()\n"
            f"subprocess.run([sys.executable, '-I', '-c', {other!r}], check=True)\n"  # a second writer on the same pipe
            "sys.stdout.write(v[h:] + '\\n')\n"))
        h = len(text) // 2
        self.assertEqual((result.returncode, result.stdout), (0, (text[:h] + "<other writer>" + text[h:] + "\n").encode()))

    def test_a_value_written_to_an_inherited_read_write_stdin_never_passes_the_relay(self):
        # The command's stdin is the runner's (a terminal or a pty when a person runs it): a read-write descriptor, so
        # the command can write to it, and that output goes straight to the other end. A socket end stands in here.
        text = self.tavily()
        self.assertIn("read-write stdin", unmasked_list())
        mine, theirs = socket.socketpair()
        self.addCleanup(mine.close)
        self.addCleanup(theirs.close)
        result = subprocess.run(self.command("tavily", *py("import os\nos.write(0, os.environ['TAVILY_API_KEY'].encode())\n")),
                                stdin=theirs, capture_output=True, env=self.tool_environment(), timeout=60)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, b"", b""))
        mine.settimeout(10)
        self.assertEqual(mine.recv(4096), text.encode())


class BoundedHoldbackTests(RunnerCase):
    """Review of 2026-09-29, finding 4: overlapping matches kept moving the hold-back boundary to zero, so a run of
    them was never written, stayed in memory whole and was scanned again at every chunk. The masker now writes a
    complete match at once and keeps only the tail that could still begin a longer needle (at most the longest
    needle minus one byte); a long run of matches may therefore produce several markers."""

    def test_a_run_of_overlapping_matches_keeps_at_most_the_longest_needle_minus_one(self):
        masker = run_mod.Masker([(b"aaaaaa", "K")])  # the review's value: six identical characters
        pieces = []
        for _ in range(31):
            pieces.append(masker.feed(b"a" * 4096, 0.0))
            self.assertLessEqual(len(masker.buf), 5)  # was 126,976 bytes after the 31st chunk
        self.assertTrue(all(pieces), "a chunk of matching bytes wrote nothing")  # progress at every chunk
        out = b"".join(pieces) + masker.close()
        self.assertEqual(MARKER.sub(b"", out), b"")  # nothing of the run is ever printed
        self.assertEqual(set(MARKER.findall(out)), {b"[REDACTED:K]"})

    def test_the_bound_follows_the_longest_needle(self):
        needles = [(b"abcabcabcabc", "LONG"), (b"abcabc", "SHORT")]
        masker = run_mod.Masker(needles)
        for _ in range(40):
            masker.feed(b"abc" * 500 + b"ab", 0.0)
            self.assertLessEqual(len(masker.buf), 11)
        self.assertLessEqual(len(masker.buf), 11)

    def test_a_straddling_match_is_written_whole_and_its_tail_is_never_printed_raw(self):
        # A is complete while B is still a proper prefix that starts inside it (the case that used to hold everything).
        masker = run_mod.Masker([(b"abcdef", "A"), (b"defghijk", "B")])
        first = masker.feed(b"abcdefgh", 0.0)
        self.assertEqual(first, b"[REDACTED:A]")
        self.assertLessEqual(len(masker.buf), 7)
        # B completes: what B adds is masked, and the bytes of A that B reuses are not printed again.
        self.assertEqual(MARKER.sub(b"", first + masker.feed(b"ijkX\n", 0.0) + masker.close()), b"X\n")
        # B fails: only the bytes after A are printed, as before.
        other = run_mod.Masker([(b"abcdef", "A"), (b"defghijk", "B")])
        self.assertEqual(other.feed(b"abcdefgh", 0.0) + other.feed(b"Y\n", 0.0) + other.close(), b"[REDACTED:A]ghY\n")

    def test_random_outputs_that_are_not_pathological_match_the_whole_buffer_masker(self):
        rng = random.Random(20260929)
        alphabet = "abcdefghijklmnopqrstuvwxyz0123456789-_./+=:@ \n"
        for round_number in range(250):
            values = {"K1": "".join(rng.choice(alphabet[:-2]) for _ in range(rng.randint(6, 24))),
                      "K2": "".join(rng.choice(alphabet[:-2]) for _ in range(rng.randint(6, 24)))}
            needles = sorted(run_mod.needles_for(values, ["K1", "K2"]), key=lambda item: len(item[0]), reverse=True)
            pieces = []
            for _ in range(rng.randint(3, 14)):
                pieces.append("".join(rng.choice(alphabet) for _ in range(rng.randint(1, 30))).encode())
                choice = rng.random()
                if choice < 0.5:
                    pieces.append(rng.choice(needles)[0])
                elif choice < 0.8:  # a proper prefix of a needle that does not complete: it is held, then released
                    needle = rng.choice(needles)[0]
                    pieces.append(needle[:rng.randint(1, len(needle) - 1)] + b"\n")
                pieces.append(b" ")  # a separator: a needle never touches the next, which the whole-buffer masker merges
            data = b"".join(pieces) + b"\n"
            expected = naive_mask(needles, data)
            longest = max(len(needle) for needle, _name in needles)
            out, retained = stream_through(needles, data, rng, rng.choice((1, 3, 17, 300)))
            with self.subTest(round=round_number):
                self.assertEqual(out, expected)
                self.assertLessEqual(retained, longest - 1)

    def test_random_pathological_runs_hold_the_bound_and_print_no_masked_byte(self):
        rng = random.Random(20260930)
        for round_number in range(80):
            unit = "".join(rng.choice("abc") for _ in range(rng.randint(1, 3)))
            value = (unit * 12)[:rng.randint(6, 12)]
            needles = sorted(run_mod.needles_for({"K": value}, ["K"]), key=lambda item: len(item[0]), reverse=True)
            data = b""
            for _ in range(rng.randint(1, 6)):
                data += (unit * rng.randint(1, 300)).encode() + rng.choice((b"-", b" Z ", b"\n", b"xyz"))
            data += b"\n"
            out, retained = stream_through(needles, data, rng, rng.choice((1, 7, 4096)))
            longest = max(len(needle) for needle, _name in needles)
            with self.subTest(round=round_number):
                self.assertLessEqual(retained, longest - 1)
                # Only the number of markers may differ from the whole-buffer masker: the bytes left unmasked are the same.
                self.assertEqual(MARKER.sub(b"", out), MARKER.sub(b"", naive_mask(needles, data)))

    def test_a_long_run_of_a_repeated_value_reaches_the_reader_masked_and_bounded(self):
        self.plant("tavily", "export TAVILY_API_KEY=aaaaaa\n")
        result = self.run_tool("tavily", *py("import sys\nsys.stdout.write('a' * 126976 + '\\n')\n"), timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(MARKER.sub(b"", result.stdout), b"\n")
        self.assertIn(b"[REDACTED:TAVILY_API_KEY]", result.stdout)


class ProcessTests(RunnerCase):
    def test_exit_code_and_signal_propagate(self):
        self.tavily()
        self.assertEqual(self.run_tool("tavily", *py("raise SystemExit(7)")).returncode, 7)
        self.assertEqual(self.run_tool("tavily", *py(
            "import os, signal\nos.kill(os.getpid(), signal.SIGTERM)\n")).returncode, 128 + signal.SIGTERM)
        # Forwarded to the command's process group: the three shutdown signals, SIGQUIT, and the three that end a process
        # by default (SIGUSR1, SIGUSR2, SIGALRM), which used to end the runner alone and leave the command running.
        for sig, code in ((signal.SIGTERM, 5), (signal.SIGINT, 6), (signal.SIGHUP, 8), (signal.SIGQUIT, 9),
                          (signal.SIGUSR1, 11), (signal.SIGUSR2, 12), (signal.SIGALRM, 13)):
            with self.subTest(signal=sig.name):
                # os.write on both sides: a handler that prints while the interrupted print still holds the buffered
                # stdout raises RuntimeError (reentrant call) and the command exits 1 instead of its code.
                runner = self.start_tool("tavily", *py(
                    "import os, signal, sys, time\n"
                    f"signal.signal({int(sig)}, lambda *_: (os.write(1, b'got {sig.name}\\n'), sys.exit({code})))\n"
                    "os.write(1, f'ready {os.getpid()}\\n'.encode())\ntime.sleep(30)\n"))
                ready = self.read_until(runner.stdout, b"\n")
                self.addCleanup(kill_quietly, int(ready.split()[1]))
                runner.send_signal(sig)
                self.assertEqual(runner.wait(timeout=30), code)
                self.assertEqual(runner.stdout.read(), f"got {sig.name}\n".encode())

    def test_signals_the_command_does_not_handle_end_the_command_and_the_runner_reports_them(self):
        self.tavily()
        for sig in (signal.SIGTERM, signal.SIGQUIT, signal.SIGUSR1, signal.SIGUSR2, signal.SIGALRM):
            with self.subTest(signal=sig.name):
                runner = self.start_tool("tavily", *py(
                    "import os, time\nprint('ready', os.getpid(), flush=True)\ntime.sleep(30)\n"))
                ready = self.read_until(runner.stdout, b"\n")
                self.addCleanup(kill_quietly, int(ready.split()[1]))
                runner.send_signal(sig)
                self.assertEqual(runner.wait(timeout=30), 128 + sig)  # the command's death by that signal, not the runner's

    def test_stdin_passes_through(self):
        self.tavily()
        data = b"line one\n\xff\xfe\x00binary\nlast line without newline"
        result = self.run_tool("tavily", *py("import sys\nsys.stdout.buffer.write(sys.stdin.buffer.read())\n"),
                               input=data)
        self.assertEqual((result.returncode, result.stdout), (0, data))

    def test_a_descendant_holding_a_pipe_cannot_hang_the_runner(self):
        self.tavily()
        started = time.monotonic()
        result = self.run_tool("tavily", *py(
            "import subprocess, sys\n"
            "grandchild = subprocess.Popen(['sleep', '60'])\n"  # inherits the runner's pipes and keeps them open
            "print('grandchild', grandchild.pid, flush=True)\n"), timeout=45)
        elapsed = time.monotonic() - started
        pid = int(result.stdout.split()[1])
        with contextlib.suppress(ProcessLookupError):
            os.kill(pid, signal.SIGKILL)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertLess(elapsed, 20)

    def test_child_runs_in_a_new_session_without_core_dumps(self):
        self.tavily()
        result = self.run_tool("tavily", *py(
            "import json, os, resource\n"
            "print(json.dumps([resource.getrlimit(resource.RLIMIT_CORE), os.getsid(0) == os.getpid()]))\n"))
        self.assertEqual(json.loads(result.stdout), [[0, 0], True])

    @unittest.skipUnless(run_mod.PINNED, "the runner signals a finished command's group only where it can pin the group")
    def test_descendants_left_behind_are_ended_after_the_drain_and_a_stubborn_one_is_killed(self):
        # Second review, 2026-09-29: a descendant still running when the drain ended was left running, with the key in
        # its environment. The runner now sends SIGTERM to the command's process group and, after TERM_GRACE_SECONDS,
        # SIGKILL. Each descendant writes a marker file if it lives long enough to; the command itself exits at once.
        self.tavily()
        plain, stubborn = self.base / "plain-survived", self.base / "stubborn-survived"
        started = time.monotonic()
        result = self.run_tool("tavily", *py(spawn_marker_writers((plain, 3.5, False), (stubborn, 6.5, True))),
                               timeout=60)
        elapsed = time.monotonic() - started
        self.addCleanup(lambda: [kill_quietly(int(pid)) for pid in result.stdout.split()[1:]])
        self.assertEqual(result.returncode, 0, result.stderr)
        time.sleep(max(0.0, 7.2 - elapsed))  # past both markers' delays
        self.assertFalse(plain.exists(), "a descendant outlived the runner")
        self.assertFalse(stubborn.exists(), "a descendant that ignores SIGTERM outlived the runner")
        # The 2 s drain, then SIGTERM (the plain one ends), then the grace and SIGKILL (the one that ignores SIGTERM).
        self.assertGreaterEqual(elapsed, run_mod.DRAIN_SECONDS + run_mod.TERM_GRACE_SECONDS - 0.5)
        self.assertLess(elapsed, run_mod.DRAIN_SECONDS + run_mod.TERM_GRACE_SECONDS + 4)

    def test_the_command_group_is_ended_on_every_exit_path_of_the_runner(self):
        # A failure inside the relay (the runner's catch-all prints internal_error) must not leave the command running.
        marker = self.base / "descendant-survived"
        children, pids = [], []

        def failing_relay(child, needles, shutdown=()):
            children.append(child)
            pids.extend(int(pid) for pid in child.stdout.readline().split()[1:])  # "spawned <command> <descendant>"
            raise RuntimeError("the relay failed")

        self.addCleanup(lambda: [kill_quietly(pid) for pid in pids])
        code = spawn_marker_writers((marker, 2.0, False)) + "time.sleep(60)\n"
        with self.assertRaises(RuntimeError):
            self.run_in_process(py(code)[1:], failing_relay)
        self.assertEqual(children[0].returncode, -signal.SIGTERM)  # ended by the group's SIGTERM, and reaped
        time.sleep(2.6)
        self.assertFalse(marker.exists(), "the runner's failure left a descendant running")

    @unittest.skipUnless(sys.platform.startswith("linux"), "PR_SET_PDEATHSIG is Linux-only")
    def test_a_killed_runner_sends_the_command_the_parent_death_signal(self):
        # Second review, 2026-09-29: a SIGKILL of the runner (a `timeout -k`, a harness that escalates) ended only the
        # runner. The command asks the kernel for SIGTERM when its parent dies (Linux PR_SET_PDEATHSIG). The watchdog
        # is switched off here, so this is that signal alone.
        self.tavily()
        noted = self.base / "command-got-sigterm"
        runner = subprocess.Popen(
            self.command("tavily", *py(
                "import os, signal, sys, time\n"
                "def note(*_):\n    open(sys.argv[1], 'w').close()\n    os._exit(0)\n"
                "signal.signal(signal.SIGTERM, note)\nprint('ready', os.getpid(), flush=True)\ntime.sleep(60)\n",
                str(noted)), launcher=True),
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=self.tool_environment({"WATCHDOG_TEST_OFF": "1"}, launcher=True))
        self.addCleanup(lambda: (runner.kill(), runner.communicate(timeout=30)))
        ready = self.read_until(runner.stdout, b"\n")
        self.addCleanup(kill_quietly, int(ready.split()[1]))
        runner.kill()
        runner.wait(timeout=30)
        deadline = time.monotonic() + 10
        while not noted.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertTrue(noted.exists(), "the command was not sent SIGTERM when its runner was killed")

    @unittest.skipUnless(sys.platform.startswith("linux"), "checked on Linux only (with PR_SET_PDEATHSIG beside it)")
    def test_a_killed_runner_takes_the_whole_command_tree_with_it(self):
        # The parent-death signal reaches the command only (the kernel clears it for the command's children:
        # PR_SET_PDEATHSIG(2const)), so a descendant outlived a SIGKILLed runner. The watchdog ends the process group.
        # The command and two descendants each write a marker after a delay unless they are ended first; one of the
        # descendants ignores SIGTERM and needs the watchdog's SIGKILL, which follows TERM_GRACE_SECONDS (2 s) later.
        self.tavily()
        own, plain, stubborn = self.base / "command-survived", self.base / "plain-survived", self.base / "stubborn-survived"
        code = (spawn_marker_writers((plain, 1.5, False), (stubborn, 4.5, True))
                + "time.sleep(2.5)\nopen(sys.argv[1], 'w').close()\n")
        runner = subprocess.Popen(self.command("tavily", *py(code, str(own))), stdin=subprocess.DEVNULL,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=self.tool_environment())
        self.addCleanup(lambda: (runner.kill(), runner.communicate(timeout=30)))
        spawned = self.read_until(runner.stdout, b"\n").split()
        self.addCleanup(lambda: [kill_quietly(int(pid)) for pid in spawned[1:]])
        self.assertEqual(spawned[0], b"spawned")
        runner.kill()
        runner.wait(timeout=30)
        time.sleep(5.0)  # past every marker's delay, and the 2 s grace plus the SIGKILL that follows it
        self.assertFalse(own.exists(), "the command outlived its killed runner")
        self.assertFalse(plain.exists(), "a descendant outlived the killed runner")
        self.assertFalse(stubborn.exists(), "a descendant that ignores SIGTERM outlived the killed runner")

    def test_a_runner_that_ends_in_order_tells_the_watchdog_and_leaves_none_behind(self):
        made, real = [], run_mod.Watchdog

        def make(pgid):
            made.append(real(pgid))
            return made[-1]

        def quiet_relay(child, needles, shutdown=()):
            child.stdout.close()
            child.stderr.close()

        with mock.patch.object(run_mod, "Watchdog", side_effect=make):
            code = self.run_in_process([sys.executable, "-I", "-c", "pass"], quiet_relay)
        self.assertEqual(code, 0)
        # Told that the runner ended in order (exit 0), and gone by the time run_command returned: not one that ended a
        # group it had no reason to touch (exit 1, which is what a runner that dies without telling it gets).
        self.assertEqual(made[0].process.returncode, 0)


class WatchdogTests(unittest.TestCase):
    """The watchdog process on its own: a pipe, the number of a process group and a grace period. It ends the group
    when the pipe closes without a byte (the runner died), and leaves it alone when it reads one (the runner ended in
    order). Its parts follow CPython's multiprocessing resource tracker, a helper that waits for the end of a pipe and
    ignores SIGINT and SIGTERM (python/cpython@v3.13.15 Lib/multiprocessing/resource_tracker.py L8, L246-267, L425-429)."""

    def setUp(self):
        self.reads, self.processes = [], []
        self.addCleanup(self.cleanup)

    def cleanup(self):
        for process in self.processes:
            with contextlib.suppress(OSError):
                os.killpg(process.pid, signal.SIGKILL)
            with contextlib.suppress(Exception):
                process.wait(timeout=10)

    def group(self, code: str = "import time\ntime.sleep(60)\n") -> subprocess.Popen:
        """A process that leads its own group, as the command does."""
        member = subprocess.Popen([sys.executable, "-I", "-c", code], stdin=subprocess.DEVNULL,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        self.processes.append(member)
        return member

    def watch(self, pgid: int, grace: float = 0.5):
        """(the watchdog, the write end of its pipe as a file object), started as the runner starts it."""
        read, write = os.pipe()
        watchdog = subprocess.Popen([sys.executable, "-I", "-S", "-c", run_mod.WATCHDOG_CODE, str(pgid), str(grace)],
                                    stdin=read, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env={},
                                    close_fds=True, start_new_session=True)
        os.close(read)
        self.processes.append(watchdog)
        pipe = os.fdopen(write, "wb", buffering=0)
        self.addCleanup(pipe.close)  # closing twice is harmless for a file object
        return watchdog, pipe

    def test_a_pipe_that_closes_without_a_byte_ends_the_group(self):
        member = self.group()
        watchdog, pipe = self.watch(member.pid)
        time.sleep(0.3)
        self.assertIsNone(member.poll())  # nothing happens while the pipe is open
        pipe.close()
        self.assertEqual(member.wait(timeout=10), -signal.SIGTERM)
        self.assertEqual(watchdog.wait(timeout=10), 1)

    def test_a_byte_before_the_close_means_the_runner_ended_in_order_and_nothing_is_touched(self):
        member = self.group()
        watchdog, pipe = self.watch(member.pid)
        pipe.write(b".")
        pipe.close()
        self.assertEqual(watchdog.wait(timeout=10), 0)
        self.assertIsNone(member.poll())

    def test_a_member_that_ignores_sigterm_is_killed_after_the_grace(self):
        member = self.group("import signal, time\nsignal.signal(signal.SIGTERM, signal.SIG_IGN)\ntime.sleep(60)\n")
        watchdog, pipe = self.watch(member.pid, grace=0.6)
        time.sleep(0.5)  # the member has installed its handler
        started = time.monotonic()
        pipe.close()
        self.assertEqual(member.wait(timeout=10), -signal.SIGKILL)
        self.assertGreaterEqual(time.monotonic() - started, 0.5)  # after the grace, not at once
        self.assertEqual(watchdog.wait(timeout=10), 1)

    def test_the_watchdog_ignores_the_signals_a_harness_sends_a_group_or_a_terminal(self):
        member = self.group()
        watchdog, pipe = self.watch(member.pid)
        time.sleep(1.0)  # its handlers are in place
        for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP, signal.SIGQUIT, signal.SIGUSR1, signal.SIGUSR2,
                       signal.SIGALRM):
            watchdog.send_signal(signum)
        time.sleep(0.3)
        self.assertIsNone(watchdog.poll())
        self.assertIsNone(member.poll())
        pipe.close()  # and it still acts
        self.assertEqual(member.wait(timeout=10), -signal.SIGTERM)


PINNED_NEEDS = "the pinned cleanup needs os.waitid with WNOWAIT and a /proc (Linux)"


class PinnedCleanupTests(RunnerCase):
    """Third review, 2026-09-29, finding 1. The runner and the watchdog kept only the number of the command's process
    group, and signalled it after the command had been reaped. Nothing holds a number once its last process is reaped,
    and the kernel may then give it to a stranger, whose group a late signal reaches. A command that has exited but has not
    been reaped, a zombie, holds its pid and so the number of its group: the runner sees the exit without reaping it
    (os.waitid with WNOWAIT), signals the group while the command is a zombie, stands the watchdog down, and reaps last."""

    @unittest.skipUnless(run_mod.PINNED, PINNED_NEEDS)
    def test_the_group_is_signalled_while_the_zombie_command_pins_it_and_the_watchdog_stands_down_before_the_reap(self):
        # The command exits at once and leaves a descendant that ignores SIGTERM and holds none of its pipes, so the
        # runner sees end of file, and the group is ended after the command has exited and before it is reaped.
        self.tavily()
        stubborn, log = self.base / "stubborn-survived", self.base / "events.json"
        started = time.monotonic()
        result = self.run_tool("tavily", *py(spawn_marker_writers((stubborn, 4.5, True), quiet=True)),
                               env={"RUNNER_TEST_SETUP": recorder_setup(log)}, launcher=True, timeout=60)
        elapsed = time.monotonic() - started
        self.addCleanup(lambda: [kill_quietly(int(pid)) for pid in result.stdout.split()[1:]])
        self.assertEqual(result.returncode, 0, result.stderr)
        events = json.loads(log.read_text())
        leader = next(event[1] for event in events if event[0] == "watchdog")
        signals = [(index, event) for index, event in enumerate(events) if event[0] == "killpg"]
        self.assertEqual([event[1] for _index, event in signals], [signal.SIGTERM, signal.SIGKILL], events)
        # The command had exited and was not reaped: its zombie held the group's number for both signals.
        self.assertEqual([event[2] for _index, event in signals], ["zombie", "zombie"], events)
        standdown = next(index for index, event in enumerate(events) if event[0] == "standdown")
        byte = next(index for index, event in enumerate(events) if event[0] == "byte")
        reaped = next(index for index, event in enumerate(events)
                      if event[0] == "waitpid" and event[1] == leader and event[2] == leader)
        self.assertLess(signals[-1][0], standdown, events)  # the watchdog stands down after the group's cleanup...
        self.assertLess(standdown, byte, events)  # (the byte is the stand-down)...
        self.assertLess(byte, reaped, events)  # ...and before the command is reaped
        time.sleep(max(0.0, 5.0 - elapsed))
        self.assertFalse(stubborn.exists(), "a descendant that ignores SIGTERM outlived the runner")
        self.assertGreaterEqual(elapsed, run_mod.TERM_GRACE_SECONDS - 0.5)  # SIGKILL came after the grace

    @unittest.skipUnless(run_mod.PINNED, PINNED_NEEDS)
    def test_a_descendant_that_obeys_sigterm_ends_the_wait_at_once_and_is_never_sent_sigkill(self):
        # The wait after SIGTERM ends when the group's live members are counted at 0, not after the grace.
        self.tavily()
        obedient, log = self.base / "obedient-survived", self.base / "events.json"
        started = time.monotonic()
        result = self.run_tool("tavily", *py(spawn_marker_writers((obedient, 4.0, False), quiet=True)),
                               env={"RUNNER_TEST_SETUP": recorder_setup(log)}, launcher=True)
        elapsed = time.monotonic() - started
        self.addCleanup(lambda: [kill_quietly(int(pid)) for pid in result.stdout.split()[1:]])
        self.assertEqual(result.returncode, 0, result.stderr)
        events = json.loads(log.read_text())
        self.assertEqual([event[1:] for event in events if event[0] == "killpg"], [[signal.SIGTERM, "zombie"]], events)
        self.assertLess(elapsed, run_mod.TERM_GRACE_SECONDS)
        time.sleep(max(0.0, 4.5 - elapsed))
        self.assertFalse(obedient.exists(), "a descendant that obeys SIGTERM outlived the runner")

    @unittest.skipUnless(run_mod.PINNED, PINNED_NEEDS)
    def test_a_command_that_leaves_nothing_behind_is_not_signalled_and_the_watchdog_stands_down_before_the_reap(self):
        self.tavily()
        log = self.base / "events.json"
        started = time.monotonic()
        result = self.run_tool("tavily", *py("pass"), env={"RUNNER_TEST_SETUP": recorder_setup(log)}, launcher=True)
        elapsed = time.monotonic() - started
        self.assertEqual(result.returncode, 0, result.stderr)
        events = json.loads(log.read_text())
        leader = next(event[1] for event in events if event[0] == "watchdog")
        self.assertEqual([event for event in events if event[0] == "killpg"], [], events)  # nothing but its zombie left
        self.assertLess(elapsed, run_mod.TERM_GRACE_SECONDS)  # and nothing was waited for
        standdown = next(index for index, event in enumerate(events) if event[0] == "standdown")
        byte = next(index for index, event in enumerate(events) if event[0] == "byte")
        reaped = next(index for index, event in enumerate(events)
                      if event[0] == "waitpid" and event[1] == leader and event[2] == leader)
        self.assertLess(standdown, byte, events)
        self.assertLess(byte, reaped, events)

    def test_where_the_exit_cannot_be_seen_unreaped_the_group_is_never_signalled_after_the_reap(self):
        # PINNED False, as on a platform without os.waitid and WNOWAIT (macOS before CPython 3.13) or without a /proc to
        # count a group's live members: the runner learns of the exit by reaping the command, and signals nothing after
        # that. The descendant of the exited command is left running: the limit of this mode, which the documentation states.
        self.tavily()
        survivor, log = self.base / "survivor-wrote", self.base / "events.json"
        result = self.run_tool("tavily", *py(spawn_marker_writers((survivor, 1.5, False), quiet=True)),
                               env={"RUNNER_TEST_SETUP": recorder_setup(log, pinned=False)}, launcher=True)
        self.addCleanup(lambda: [kill_quietly(int(pid)) for pid in result.stdout.split()[1:]])
        self.assertEqual(result.returncode, 0, result.stderr)
        events = json.loads(log.read_text())
        self.assertEqual([event for event in events if event[0] == "killpg"], [], events)
        self.assertTrue(wait_until(survivor.exists, 5), "the descendant was ended although the group's number was not held")

    def test_where_the_exit_cannot_be_seen_unreaped_a_failure_in_the_relay_still_ends_the_group_before_the_reap(self):
        marker = self.base / "descendant-survived"
        children, pids = [], []

        def failing_relay(child, needles, shutdown=()):
            children.append(child)
            pids.extend(int(pid) for pid in child.stdout.readline().split()[1:])  # "spawned <command> <descendant>"
            raise RuntimeError("the relay failed")

        self.addCleanup(lambda: [kill_quietly(pid) for pid in pids])
        with mock.patch.object(run_mod, "PINNED", False), self.assertRaises(RuntimeError):
            self.run_in_process(py(spawn_marker_writers((marker, 2.0, False)) + "time.sleep(60)\n")[1:], failing_relay)
        self.assertEqual(children[0].returncode, -signal.SIGTERM)  # ended by the group's SIGTERM, then reaped
        time.sleep(2.2)
        self.assertFalse(marker.exists(), "the runner's failure left a descendant running")

    def test_a_signal_that_reaches_the_runner_after_the_command_was_reaped_is_not_forwarded(self):
        def quiet_relay(child, needles, shutdown=()):
            child.stdout.close()
            child.stderr.close()

        self.run_in_process([sys.executable, "-I", "-c", "pass"], quiet_relay)  # its handlers stay installed
        with mock.patch.object(os, "killpg") as killpg:
            os.kill(os.getpid(), signal.SIGUSR1)  # run_command's handler runs in this process, after the reap
            time.sleep(0.1)
        killpg.assert_not_called()

    def test_a_runner_started_with_sigchld_ignored_still_reports_the_commands_status(self):
        # An inherited SIG_IGN for SIGCHLD makes the kernel reap each child the moment it exits: no zombie holds the
        # command's number, and its status is lost. The runner sets the default disposition before it starts anything.
        self.tavily()
        runner = subprocess.Popen(self.command("tavily", *py("raise SystemExit(7)")), stdin=subprocess.DEVNULL,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=self.tool_environment(),
                                  preexec_fn=lambda: signal.signal(signal.SIGCHLD, signal.SIG_IGN))
        self.addCleanup(lambda: (runner.kill(), runner.communicate(timeout=30)))
        runner.communicate(timeout=60)
        self.assertEqual(runner.returncode, 7)


@unittest.skipUnless(run_mod.PINNED, PINNED_NEEDS)
class CommandTests(unittest.TestCase):
    """The runner's view of the command (run_mod.Command) and of its process group (run_mod.live_members)."""

    def setUp(self):
        self.processes = []
        self.addCleanup(self.cleanup)

    def cleanup(self):
        for process in self.processes:
            if process.returncode is None:  # unreaped, so its group's number is still held
                with contextlib.suppress(OSError):
                    os.killpg(process.pid, signal.SIGKILL)
                with contextlib.suppress(Exception):
                    process.wait(timeout=10)

    def start(self, code: str, **streams) -> subprocess.Popen:
        streams = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL, **streams}
        process = subprocess.Popen([sys.executable, "-I", "-c", code], start_new_session=True, **streams)
        self.processes.append(process)
        return process

    def test_the_exit_is_seen_without_reaping_and_the_group_is_signalled_only_until_the_reap(self):
        process = self.start("pass")
        command = run_mod.Command(process)
        self.assertTrue(wait_until(command.exited, 10))
        self.assertIsNone(process.returncode)  # not reaped: its zombie still holds its pid, and its group's number
        self.assertIsNotNone(os.waitid(os.P_PID, process.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT))
        self.assertFalse(command.reaped)
        with mock.patch.object(os, "killpg") as killpg:
            self.assertTrue(command.signal_group(signal.SIGTERM))
        killpg.assert_called_once_with(process.pid, signal.SIGTERM)
        self.assertEqual(command.reap(), 0)
        self.assertTrue(command.reaped)
        with mock.patch.object(os, "killpg") as killpg:
            self.assertFalse(command.signal_group(signal.SIGTERM))
        killpg.assert_not_called()

    def test_the_signals_the_runner_forwards_are_blocked_while_the_command_is_reaped(self):
        # A handler that ran between the reap and the moment the runner records it would signal a number nobody holds.
        process = self.start("pass")
        command = run_mod.Command(process)
        self.assertTrue(wait_until(command.exited, 10))
        seen, real_wait = [], process.wait

        def wait(timeout=None):
            seen.append(signal.pthread_sigmask(signal.SIG_BLOCK, []))
            return real_wait(timeout=timeout)

        with mock.patch.object(process, "wait", wait):
            command.reap()
        self.assertTrue(set(run_mod.FORWARDED) <= set(seen[0]), seen)
        self.assertFalse(set(run_mod.FORWARDED) & set(signal.pthread_sigmask(signal.SIG_BLOCK, [])))  # and put back

    def test_a_waitid_that_is_refused_falls_back_to_seeing_the_exit_by_reaping(self):
        process = self.start("pass")
        command = run_mod.Command(process)
        with mock.patch.object(os, "waitid", side_effect=OSError(38, "Function not implemented")):
            self.assertTrue(wait_until(command.exited, 10))
        self.assertFalse(command.pinned)  # from now on the group is not signalled once the command is reaped
        self.assertTrue(command.reaped)  # the exit was seen by reaping it
        self.assertEqual(command.reap(), 0)

    def test_a_zombie_is_not_a_live_member_of_its_group_and_a_running_descendant_is(self):
        code = ("import subprocess, sys\n"
                "kid = subprocess.Popen([sys.executable, '-I', '-c', 'import time; time.sleep(60)'],"
                " stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\n"
                "print(kid.pid, flush=True)\n")
        leader = self.start(code, stdout=subprocess.PIPE)
        kid = int(leader.stdout.readline())
        self.addCleanup(kill_quietly, kid)
        self.addCleanup(leader.stdout.close)
        command = run_mod.Command(leader)
        self.assertTrue(wait_until(command.exited, 10))  # the leader has exited: a zombie, still a member of its group
        self.assertEqual(run_mod.live_members(leader.pid), 1)  # the sleeper alone: a zombie is not counted
        os.killpg(leader.pid, signal.SIGKILL)  # the zombie still holds the number
        self.assertTrue(wait_until(lambda: run_mod.live_members(leader.pid) == 0, 10))
        command.reap()

    def test_a_running_command_is_a_live_member_of_its_own_group(self):
        process = self.start("import time\ntime.sleep(60)\n")
        self.assertTrue(wait_until(lambda: run_mod.live_members(process.pid) == 1, 10))
        process.kill()
        self.assertTrue(wait_until(lambda: run_mod.live_members(process.pid) == 0, 10))  # a zombie now
        process.wait(timeout=10)


@unittest.skipUnless(sys.platform.startswith("linux"), "PR_SET_PDEATHSIG and its pre-exec hook are Linux-only")
class PreExecTests(RunnerCase):
    """Third review, 2026-09-29, finding 2. The command's pre-exec code runs with a copy of the runner's signal handlers, and
    forward() only records a SIGTERM: the parent-death signal was queued in the copy instead of ending the command, which then
    ran (the reviewer's probe: pause after the parent check, kill the runner, resume: exit 42). The hook puts every handled
    signal back to its default and clears the inherited mask before it arms the signal, and checks the parent's pid after."""

    def start_held(self, stage: str, pause: bool = True, preexec=None):
        """The runner, started so that the forked command stops at `stage` (pre_exec_pause), and where it stopped."""
        self.tavily()
        directory = self.base / "held"
        directory.mkdir(exist_ok=True)
        self.ran = self.base / "command-ran"
        runner = subprocess.Popen(
            self.command("tavily", *py(f"open({str(self.ran)!r}, 'w').close()"), launcher=True),
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, preexec_fn=preexec,
            env=self.tool_environment({"RUNNER_TEST_SETUP": pause_setup(directory, stage, pause)}, launcher=True))
        self.addCleanup(lambda: (runner.kill(), runner.communicate(timeout=30)))
        return runner, directory

    def test_a_runner_killed_while_the_command_waits_between_the_parent_check_and_exec_ends_it(self):
        runner, directory = self.start_held("after_check")
        held = wait_for_json(directory / "state.json")
        self.addCleanup(kill_quietly, held["pid"])
        runner.kill()  # the kernel sends the armed command SIGTERM
        runner.wait(timeout=30)
        self.assertTrue(wait_until(lambda: not is_running(held["pid"]), 5),
                        "the command outlived its runner: the parent-death signal was swallowed before exec")
        (directory / "go").write_text("")
        time.sleep(0.5)
        self.assertFalse(self.ran.exists(), "the command ran after its runner had been killed")

    def test_a_runner_killed_before_the_command_armed_the_signal_still_ends_it_by_the_parent_pid(self):
        # Nothing is sent to a command that arms the signal after its parent has gone: it must notice, and not exec.
        runner, directory = self.start_held("before_arming")
        held = wait_for_json(directory / "state.json")
        self.addCleanup(kill_quietly, held["pid"])
        runner.kill()
        runner.wait(timeout=30)
        time.sleep(0.3)
        self.assertTrue(is_running(held["pid"]))  # held before arming: nothing has been sent to it
        (directory / "go").write_text("")
        self.assertTrue(wait_until(lambda: not is_running(held["pid"]), 5), "the command survived the death of its runner")
        time.sleep(0.3)
        self.assertFalse(self.ran.exists(), "the command ran after its runner had been killed")

    def test_the_command_starts_with_default_handlers_and_no_blocked_signals(self):
        # The runner is started with SIGUSR1 blocked, which its command would inherit through the exec.
        runner, directory = self.start_held(
            "after_check", pause=False, preexec=lambda: signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGUSR1}))
        runner.communicate(timeout=60)
        self.assertEqual(runner.returncode, 0)
        state = json.loads((directory / "state.json").read_text())
        self.assertEqual(state["default"], {signal.Signals(number).name: True for number in run_mod.FORWARDED})
        self.assertEqual(state["blocked"], [])
        self.assertTrue(self.ran.exists())


class ConsumerTests(RunnerCase):
    """Review of 2026-09-29, finding 5: blocking writes let a consumer that stopped reading hold the runner, and its
    shutdown and drain deadlines, hostage (it stayed alive 2.7 s after SIGTERM and exited 143 only when the consumer
    resumed). Output now goes through non-blocking descriptors and a bounded queue in the relay's own select loop."""

    FLOOD = "import sys\nchunk = 'x' * 65535 + '\\n'\nwhile True:\n    sys.stdout.write(chunk)\n    sys.stderr.write(chunk)\n"

    def test_a_consumer_that_never_reads_cannot_hold_the_runner_after_a_signal(self):
        self.tavily()
        runner = self.start_tool("tavily", *py(self.FLOOD))  # its output pipes are never read
        time.sleep(1.5)  # both pipes and both queues fill, and the flooding command blocks on its own pipes
        self.assertIsNone(runner.poll())
        sent = time.monotonic()
        runner.send_signal(signal.SIGTERM)
        self.assertEqual(runner.wait(timeout=20), 128 + signal.SIGTERM)  # was: blocked in write until the consumer read
        # After a shutdown signal nothing waits for the consumer, not even the drain deadline that follows an exit.
        self.assertLess(time.monotonic() - sent, run_mod.DRAIN_SECONDS - 0.5)

    def test_a_consumer_that_never_reads_holds_the_command_back_not_the_runners_memory(self):
        self.tavily()
        progress = self.base / "progress"
        code = ("import sys\nprogress = sys.argv[1]\nchunk = 'x' * 65535 + '\\n'\ni = 0\nwhile True:\n"
                "    sys.stdout.write(chunk)\n    sys.stdout.flush()\n    i += 1\n    open(progress, 'w').write(str(i))\n")
        runner = self.start_tool("tavily", *py(code, str(progress)))  # stdout is never read
        time.sleep(2.0)
        written = int(progress.read_text() or 0)
        # A pipe on each side of the runner and a 256 KiB queue hold about 7 chunks; without the read-side backpressure
        # the runner would keep reading and queue the command's whole output, and this count would run into the thousands.
        self.assertTrue(1 <= written <= 24, f"the command wrote {written} chunks of 64 KiB to a consumer that never reads")
        runner.send_signal(signal.SIGTERM)
        self.assertEqual(runner.wait(timeout=20), 128 + signal.SIGTERM)

    def test_output_that_nobody_reads_is_dropped_after_the_drain_deadline(self):
        self.tavily()
        code = "import sys\nsys.stdout.write('y' * 150000)\nsys.stderr.write('z' * 150000)\nraise SystemExit(7)\n"
        runner = self.start_tool("tavily", *py(code))  # more than a pipe holds, less than the queues do
        started = time.monotonic()
        self.assertEqual(runner.wait(timeout=20), 7)  # the command's own status, DRAIN_SECONDS after it exited
        elapsed = time.monotonic() - started
        self.assertGreaterEqual(elapsed, run_mod.DRAIN_SECONDS - 0.5)
        self.assertLess(elapsed, run_mod.DRAIN_SECONDS + 8)

    def test_a_slow_consumer_gets_every_byte_while_the_command_runs(self):
        self.tavily()
        size = 700_000
        runner = self.start_tool("tavily", *py(
            f"import sys\nsys.stdout.write('q' * {size})\nsys.stdout.flush()\nsys.stderr.write('e' * {size})\n"))
        time.sleep(1.0)  # nobody reads yet: the pipes and the queue fill, and the command waits for the runner
        out, err = runner.communicate(timeout=60)
        self.assertEqual((runner.returncode, out, err), (0, b"q" * size, b"e" * size))

    def test_stdout_and_stderr_on_one_pipe_are_relayed_and_shut_down_together(self):
        self.tavily()
        merged = subprocess.run(self.command("tavily", *py("import sys\nprint('out', flush=True)\nprint('err', file=sys.stderr)")),
                                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                env=self.tool_environment(), timeout=60)  # 2>&1: one open file description
        self.assertEqual((merged.returncode, sorted(merged.stdout.split())), (0, [b"err", b"out"]))
        runner = subprocess.Popen(self.command("tavily", *py(self.FLOOD)), stdin=subprocess.DEVNULL,
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=self.tool_environment())
        self.addCleanup(lambda: (runner.kill(), runner.communicate(timeout=30)))
        time.sleep(1.5)
        runner.send_signal(signal.SIGTERM)
        self.assertEqual(runner.wait(timeout=20), 128 + signal.SIGTERM)

    def test_output_to_a_file_or_a_terminal_is_written_directly_and_a_terminal_is_left_blocking(self):
        self.tavily()
        target = self.base / "relayed.out"
        with open(target, "wb") as handle:
            done = subprocess.run(self.command("tavily", *py("print('to a file')\n")), stdin=subprocess.DEVNULL,
                                  stdout=handle, stderr=subprocess.PIPE, env=self.tool_environment(), timeout=60)
        self.assertEqual((done.returncode, target.read_bytes(), done.stderr), (0, b"to a file\n", b""))
        # stdin, stdout and stderr are one terminal: the command's stdin must still be blocking (the runner never
        # flips a terminal, whose description the command shares).
        master, slave = os.openpty()
        self.addCleanup(os.close, master)
        runner = subprocess.Popen(self.command("tavily", *py("import os\nprint('blocking', os.get_blocking(0))")),
                                  stdin=slave, stdout=slave, stderr=slave, env=self.tool_environment())
        os.close(slave)
        self.addCleanup(lambda: (runner.kill(), runner.wait(timeout=30)))
        self.assertIn(b"blocking True", self.read_until(open(master, "rb", buffering=0, closefd=False), b"True", seconds=20))
        self.assertEqual(runner.wait(timeout=20), 0)

    def test_a_socket_shared_by_stdin_stdout_and_stderr_is_left_blocking_for_the_command(self):
        # One socketpair end is fds 0, 1 and 2 of the runner: the sinks share the command's stdin description, so the
        # runner must not flip it non-blocking (the command's reads would fail with EAGAIN). The terminal test above
        # cannot fail on this, because a terminal is never flipped; a socket is, unless the sink is compared with stdin
        # (Sink's stdin_identity, wired in relay). The command looks after its output has passed through the relay.
        self.tavily()
        mine, theirs = socket.socketpair()
        self.addCleanup(mine.close)
        self.addCleanup(theirs.close)
        runner = subprocess.Popen(
            self.command("tavily", *py("import os, time\nprint('ready', flush=True)\ntime.sleep(0.5)\n"
                                       "print('blocking', os.get_blocking(0), flush=True)\n")),
            stdin=theirs, stdout=theirs, stderr=theirs, env=self.tool_environment())
        self.addCleanup(lambda: (runner.kill(), runner.wait(timeout=30)))
        mine.settimeout(20)
        seen = b""
        while b"blocking True\n" not in seen and b"blocking False\n" not in seen:
            chunk = mine.recv(4096)
            if not chunk:
                break
            seen += chunk
        self.assertIn(b"blocking True\n", seen)
        self.assertEqual(runner.wait(timeout=20), 0)
        self.assertTrue(os.get_blocking(theirs.fileno()))  # and left as it was found

    def test_a_signal_the_command_handles_does_not_start_the_no_wait_rule_of_a_shutdown(self):
        # SIGUSR1 is forwarded, but only the shutdown signals stop the runner waiting for a slow consumer (what it has
        # queued is dropped after them). A command that handles SIGUSR1 and goes on writing is still delivered every byte.
        self.tavily()
        size = 700_000
        runner = self.start_tool("tavily", *py(
            "import signal, sys, time\nsignal.signal(signal.SIGUSR1, lambda *_: None)\nprint('ready', flush=True)\n"
            f"signal.pause()\ntime.sleep(0.5)\nsys.stdout.write('q' * {size})\n"))
        ready = self.read_until(runner.stdout, b"ready\n")
        runner.send_signal(signal.SIGUSR1)
        time.sleep(1.5)  # the command writes and nobody reads: the pipes and the queue fill, and the command waits
        rest, _ = runner.communicate(timeout=60)
        self.assertEqual((runner.returncode, ready + rest), (0, b"ready\n" + b"q" * size))

    def test_a_consumer_that_closes_its_end_ends_the_command(self):
        self.tavily()
        runner = self.start_tool("tavily", *py(
            "import sys\nwhile True:\n    sys.stdout.write('line\\n')\n    sys.stdout.flush()\n"))
        self.assertIn(b"line\n", self.read_until(runner.stdout, b"line\n", seconds=10))
        runner.stdout.close()  # the reader goes away: the runner closes the command's pipe and the command gets EPIPE
        self.assertIsNotNone(runner.wait(timeout=20))


class SinkTests(unittest.TestCase):
    """The runner's own output descriptors, on real pipes, sockets and files."""

    def tearDown(self):
        for fd in getattr(self, "fds", []):
            with contextlib.suppress(OSError):
                os.close(fd)

    def pipe(self):
        read, write = os.pipe()
        self.fds = getattr(self, "fds", []) + [read, write]
        return read, write

    def test_only_pipes_and_sockets_are_made_non_blocking_and_are_put_back(self):
        read, write = self.pipe()
        sink = run_mod.Sink(write)
        self.assertTrue(sink.polled)
        self.assertFalse(os.get_blocking(write))
        sink.restore()
        self.assertTrue(os.get_blocking(write))
        left, right = socket.socketpair()
        self.addCleanup(left.close)
        self.addCleanup(right.close)
        pair = run_mod.Sink(left.fileno())
        self.assertTrue(pair.polled)
        self.assertFalse(os.get_blocking(left.fileno()))
        pair.restore()
        self.assertTrue(os.get_blocking(left.fileno()))
        # A regular file and /dev/null cannot wait on a reader; a descriptor already non-blocking is left as found.
        with tempfile.TemporaryFile() as handle, open(os.devnull, "wb") as null:
            for descriptor in (handle.fileno(), null.fileno()):
                plain = run_mod.Sink(descriptor)
                self.assertFalse(plain.polled)
                self.assertTrue(os.get_blocking(descriptor))
                plain.restore()
        os.set_blocking(write, False)
        already = run_mod.Sink(write)
        self.assertTrue(already.polled)
        already.restore()
        self.assertFalse(os.get_blocking(write))

    def test_a_descriptor_shared_with_stdin_is_never_flipped(self):
        # A pipe or socket that is also the command's stdin shares its open file description with it: flipping the
        # flag would make the command's reads fail with EAGAIN.
        _read, write = self.pipe()
        info = os.fstat(write)
        shared = run_mod.Sink(write, (info.st_dev, info.st_ino))
        self.assertFalse(shared.polled)
        self.assertTrue(os.get_blocking(write))

    def test_the_queue_is_bounded_ordered_lossless_and_dropped_on_abandon(self):
        read, write = self.pipe()
        os.set_blocking(read, False)
        sink = run_mod.Sink(write)
        blocks = [bytes([65 + number]) * 40000 for number in range(6)]
        for block in blocks:
            sink.put(block)  # never blocks, although nobody reads yet
        self.assertGreater(len(sink.queue), 0)
        self.assertEqual(sink.size, sum(len(chunk) for chunk in sink.queue))
        self.assertFalse(sink.full())
        while not sink.full():
            sink.put(b"z" * 65536)
        self.assertTrue(sink.full())
        received, queued = b"", sink.size
        while sink.queue:
            try:
                received += os.read(read, 1 << 20)
            except BlockingIOError:
                pass
            sink.flush()
        while True:
            try:
                received += os.read(read, 1 << 20)
            except BlockingIOError:
                break
        self.assertTrue(received.startswith(b"".join(blocks)))  # in order, nothing lost before the first drop
        self.assertGreater(len(received), queued)
        sink.put(b"w" * 200000)
        sink.abandon()
        self.assertEqual((len(sink.queue), sink.size), (0, 0))
        sink.put(b"more")  # after a shutdown, at most what the consumer takes at once
        self.assertEqual(sink.size, 0)

    def test_a_consumer_that_went_away_marks_the_sink_dead(self):
        read, write = self.pipe()
        sink = run_mod.Sink(write)
        os.close(read)
        self.fds.remove(read)
        sink.put(b"nobody is listening")
        self.assertTrue(sink.dead)
        self.assertEqual((len(sink.queue), sink.size), (0, 0))
        sink.put(b"ignored")
        self.assertEqual(sink.size, 0)


class CheckAndIsolationTests(RunnerCase):
    def test_check_mode_prints_names_only(self):
        marker = self.base / "child-ran"
        missing = self.run_tool("tavily", "--check")
        self.assertEqual((missing.returncode, missing.stdout),
                         (1, b"tavily: missing (<store>/tavily.env); add it with: "
                             b"bash tools/credentials/open_credential_terminal.sh tavily\n"))
        self.tavily()
        ok = self.run_tool("tavily", "--check")
        self.assertEqual((ok.returncode, ok.stdout, ok.stderr),
                         (0, b"tavily: ok; would inject TAVILY_API_KEY (masked)\n", b""))
        self.alpaca()
        pair = self.run_tool("alpaca-paper", "--check")
        self.assertEqual(pair.stdout, b"alpaca-paper: ok; would inject APCA_API_KEY_ID (masked), "
                                      b"APCA_API_SECRET_KEY (masked), APCA_API_BASE_URL (public)\n")
        narrowed = self.run_tool("alpaca-paper", "--check", "--only", "APCA_API_KEY_ID")
        self.assertEqual(narrowed.stdout, b"alpaca-paper: ok; would inject APCA_API_KEY_ID (masked)\n")
        (self.store / "tavily.env").chmod(0o644)
        unsafe = self.run_tool("tavily", "--check")
        self.assertEqual((unsafe.returncode, unsafe.stdout), (1, b"tavily: unsafe (mode_not_0600)\n"))
        self.plant("tavily", "export TAVILY_API_KEY=$(id)\n")
        grammar = self.run_tool("tavily", "--check")
        self.assertEqual((grammar.returncode, grammar.stdout), (1, b"tavily: unsafe (line 1: outside_writer_grammar)\n"))
        engine = self.run_tool("grafana-admin", "--check")
        self.assertEqual(engine.returncode, 1)
        self.assertTrue(engine.stdout.startswith(b"grafana-admin: refused (not_injectable: "))
        # --check starts no command.
        self.assertEqual(self.run_tool("tavily", "--check", *py(f"open({str(marker)!r}, 'w').close()")).returncode, 2)
        self.assertFalse(marker.exists())
        self.assert_never_echoed(*(r.stdout + r.stderr for r in (missing, ok, pair, narrowed, unsafe, grammar, engine)))

    def test_messages_never_contain_values_or_paths(self):
        # Every refusal and every normal run, collected: no value, no piece of one, no store path, no store line.
        value = self.tavily()
        outputs = []
        scenarios = [("tavily", "--check"), ("tavily", *py("print('ok')")), ("tavily", "--", "/no/such/cmd"),
                     ("alpaca-paper", "--check"), ("alpaca-paper", "--", "true"), ("no-such", "--", "true")]
        for text in (f"export TAVILY_API_KEY={value} trailing\n", f"TAVILY_API_KEY={value}\n",
                     f"export TAVILY_API_KEY=\"{value}\n", f"export TAVILY_API_KEY={value[:5]}\n",
                     f"export OTHER_NAME={value}\n"):
            self.plant("tavily", text)
            for args in scenarios:
                result = self.run_tool(*args)
                outputs.extend((result.stdout, result.stderr))
        self.assert_never_echoed(*outputs)
        for text in outputs:
            self.assertIsNone(STORE_LINE.search(text))
            self.assertNotIn(b"native-agent-stack/", text)
        self.assertTrue(any(b"<store>/alpaca-paper.env" in text for text in outputs))

    @unittest.skipIf(HOST_PIPES_CORES, "the real re-execution is refused on a host that pipes crash dumps")
    def test_isolated_before_reading(self):
        # The first, non-isolated start runs a poisoned sitecustomize; it records every *.env open through an audit
        # hook. The runner must re-execute under -I -S before it opens the store, and the isolated run imports none
        # of the poisoned modules.
        value = self.tavily()
        poison, log = self.base / "poison", self.base / "poison.log"
        poison.mkdir()
        (poison / "sitecustomize.py").write_text(
            "import os, sys\n"
            f"LOG = {str(log)!r}\n"
            "with open(LOG, 'a') as f: f.write(f'start isolated={sys.flags.isolated}\\n')\n"
            "def hook(event, args):\n"
            "    if event == 'open' and str(args[0]).endswith('.env'):\n"
            "        with open(LOG, 'a') as f: f.write('opened a store file\\n')\n"
            "sys.addaudithook(hook)\n")
        for module in ("json", "selectors", "subprocess", "base64", "credential_status", "set_credential"):
            (poison / f"{module}.py").write_text(f"open({str(log)!r}, 'a').write('imported {module}\\n')\n")
        result = self.run_tool("tavily", *py(REPORT, '["TAVILY_API_KEY"]'), env={"PYTHONPATH": str(poison)})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"TAVILY_API_KEY": sha(value)})
        self.assertEqual(log.read_text(), "start isolated=0\n")

    @unittest.skipIf(HOST_PIPES_CORES, "the real re-execution is refused on a host that pipes crash dumps")
    def test_site_packages_code_never_runs_in_the_reading_interpreter(self):
        # A .pth line of the interpreter's own site-packages runs even under -I; -S skips it. In a throwaway venv whose
        # site-packages this test may write (as tests/test_credential_tools.py does for set_credential.py), the line
        # records each start: only the first, non-isolated one may run it, never the re-executed one that reads.
        value = self.tavily()
        venv = self.base / "venv"
        made = subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(venv)],
                              capture_output=True, text=True, timeout=120)
        if made.returncode != 0:
            self.skipTest("python3 -m venv is not available")
        python = venv / "bin" / "python"
        purelib = subprocess.run([str(python), "-c", "import sysconfig; print(sysconfig.get_paths()['purelib'])"],
                                 capture_output=True, text=True, timeout=60, check=True).stdout.strip()
        record = self.base / "starts"
        Path(purelib, "zz_probe.pth").write_text(
            f"import sys; open({str(record)!r}, 'a').write('site ran, isolated=%d;' % sys.flags.isolated)\n")
        result = subprocess.run([str(python), str(TOOL), "tavily", *py(REPORT, '["TAVILY_API_KEY"]')],
                                stdin=subprocess.DEVNULL, capture_output=True, env=self.env, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"TAVILY_API_KEY": sha(value)})
        # A set of start kinds: a Linux venv reaches its site-packages twice (lib and the lib64 link), so one start
        # can run the line twice. Only the first, non-isolated start ran it; the -I -S interpreter never did.
        self.assertEqual({start for start in record.read_text().split(";") if start}, {"site ran, isolated=0"})


class CoreDumpTests(RunnerCase):
    """Review of 2026-09-29, finding 2: RLIMIT_CORE 0 stops a core file, not a collector. The kernel ignores the limit
    for a `|` pattern and for an `@` core socket (torvalds/linux@v6.16 fs/coredump.c L795-820, L242-243 and L919), and
    systemd-coredump then journals the crashing process's environment (systemd@v257 src/coredump/coredump.c L472-479
    and L1458-1459), so the runner refuses such a host. Patterns are files of these tests, never this host's."""

    PIPE = b"|/usr/lib/systemd/systemd-coredump %P %u %g %s %t %c %h\n"

    def pattern(self, text: bytes | None) -> Path:
        path = self.base / "pattern-under-test"
        if text is not None:
            path.write_bytes(text)
        return path

    def refusal(self, text: bytes | None) -> str:
        with self.assertRaises(run_mod.Refused) as caught:
            run_mod.check_core_pattern(str(self.pattern(text)))
        return str(caught.exception)

    def test_a_piped_or_socket_pattern_is_refused_without_naming_it(self):
        for text, reason in ((self.PIPE, "core_pattern_pipe"), (b"|/bin/true", "core_pattern_pipe"),
                             (b"|", "core_pattern_pipe"), (b"@/run/systemd/coredump.socket\n", "core_pattern_socket"),
                             (b"@@/run/systemd/coredump\n", "core_pattern_socket")):
            with self.subTest(pattern=text[:12]):
                message = self.refusal(text)
                self.assertTrue(message.startswith(reason + ": "), message)
                self.assertIn("inspect /proc/sys/kernel/core_pattern", message)
                self.assertNotIn("systemd", message)  # never a value of the file

    def test_file_patterns_and_a_missing_file_are_accepted(self):
        for text in (b"core", b"core\n", b"core.%p", b"/var/crash/core.%e.%p.%t\n", b"", b"core|not-a-pipe",
                     b" |only the first byte counts"):
            with self.subTest(pattern=text[:12]):
                run_mod.check_core_pattern(str(self.pattern(text)))
        run_mod.check_core_pattern(str(self.base / "no" / "such" / "core_pattern"))  # macOS: no /proc at all
        run_mod.check_core_pattern(str(self.pattern(b"core") / "not-a-directory"))

    def test_an_unreadable_pattern_file_is_refused(self):
        directory = self.base / "a-directory"  # exists, but cannot be read as a file (also refused when run as root)
        directory.mkdir()
        with self.assertRaises(run_mod.Refused) as caught:
            run_mod.check_core_pattern(str(directory))
        self.assertTrue(str(caught.exception).startswith("core_pattern_unreadable: "))
        self.assertIn("inspect that file", str(caught.exception))
        self.assertIn("/proc/sys/kernel/core_pattern", str(caught.exception))

    def main_in_process(self, *args: str, pattern: bytes = b"core\n"):
        """run_mod.main(args) with the store and the core_pattern path of this test: (code, stdout, stderr)."""
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, self.env), \
                mock.patch.object(run_mod, "CORE_PATTERN_FILE", str(self.pattern(pattern))), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = run_mod.main(list(args))
        return code, out.getvalue(), err.getvalue()

    def test_a_refused_host_never_reads_the_store_or_starts_the_command(self):
        self.tavily()
        marker = self.base / "child-ran"
        child = py(f"open({str(marker)!r}, 'w').close()")
        secret_path = self.store / "tavily.env"
        with mock.patch.object(run_mod, "read_store", side_effect=AssertionError("the store was read")):
            for text, reason in ((self.PIPE, "core_pattern_pipe"), (b"@/run/x.socket", "core_pattern_socket")):
                code, out, err = self.main_in_process("tavily", *child, pattern=text)
                self.assertEqual(code, 1, err)
                self.assertIn(f"credential_run: tavily: refused: {reason}: ", err)
                self.assertNotIn("systemd", out + err)
                self.assertNotIn(str(secret_path), out + err)
                code, out, err = self.main_in_process("tavily", "--check", pattern=text)
                self.assertEqual((code, err), (1, ""))
                self.assertTrue(out.startswith(f"tavily: refused ({reason}: "), out)
        self.assertFalse(marker.exists(), "a refused run started its command")

    def test_a_limit_that_cannot_be_set_is_refused(self):
        self.tavily()
        marker = self.base / "child-ran"
        for failure in (OSError(1, "Operation not permitted"), ValueError("current limit exceeds maximum limit")):
            with self.subTest(failure=type(failure).__name__), \
                    mock.patch.object(run_mod.resource, "setrlimit", side_effect=failure):
                code, out, err = self.main_in_process("tavily", *py(f"open({str(marker)!r}, 'w').close()"))
                self.assertEqual(code, 1, err)
                self.assertIn("credential_run: tavily: refused: core_limit_not_set: ", err)
                self.assertNotIn("Operation not permitted", out + err)
        self.assertFalse(marker.exists(), "a refused run started its command")

    def test_the_real_tool_follows_this_hosts_own_pattern(self):
        # The real /proc file through the real tool, no launcher: a collector host is refused with the file named,
        # any other host starts (--check reads the pattern before the store, as a run does).
        self.tavily()
        real = subprocess.run([sys.executable, str(TOOL), "tavily", "--check"], stdin=subprocess.DEVNULL,
                              capture_output=True, env=self.env, timeout=60)
        self.assertEqual(real.stderr, b"")
        if _host_hands_cores_to_a_collector():
            self.assertEqual(real.returncode, 1)
            self.assertRegex(real.stdout, rb"^tavily: refused \(core_pattern_(pipe|socket): ")
            self.assertIn(b"inspect /proc/sys/kernel/core_pattern", real.stdout)
        else:
            self.assertEqual((real.returncode, real.stdout), (0, b"tavily: ok; would inject TAVILY_API_KEY (masked)\n"))


class StandardDescriptorTests(RunnerCase):
    """Review of 2026-09-29, finding 7: a standard descriptor closed at start is reopened on /dev/null, and the command
    must inherit it (os.open's descriptor is close-on-exec, which the exec would close again: EBADF, not EOF)."""

    def start_with_closed(self, redirect: str, code: str) -> subprocess.CompletedProcess:
        command = ["/bin/sh", "-c", f'exec "$@" {redirect}', "sh", *self.command("tavily", *py(code))]
        return subprocess.run(command, capture_output=True, env=self.tool_environment(), timeout=60)

    def test_a_closed_stdin_reads_end_of_file_in_the_command(self):
        self.tavily()
        result = self.start_with_closed("<&-", (
            "import os\ntry:\n    print('eof' if os.read(0, 8) == b'' else 'data')\n"
            "except OSError as error:\n    print('errno', error.errno)\n"))
        self.assertEqual((result.returncode, result.stdout), (0, b"eof\n"), result.stderr)

    def test_a_closed_stdout_or_stderr_leaves_the_other_stream_relayed(self):
        self.tavily()
        both = "import sys\nsys.stdout.write('out\\n')\nsys.stderr.write('err\\n')\n"
        closed_out = self.start_with_closed(">&-", both)
        self.assertEqual((closed_out.returncode, closed_out.stdout, closed_out.stderr), (0, b"", b"err\n"))
        closed_err = self.start_with_closed("2>&-", both)
        self.assertEqual((closed_err.returncode, closed_err.stdout, closed_err.stderr), (0, b"out\n", b""))


class InventoryAndGrammarTests(unittest.TestCase):
    def test_every_injected_name_is_masked_or_public(self):
        inventory = json.loads((ROOT / "adoption/credential-inventory.json").read_text(encoding="utf-8"))
        injectable, classified = set(), {}
        for entry in inventory["entries"]:
            if not run_mod.injectable(entry):
                continue
            injectable.add(entry["id"])
            injected = entry["variables"] + entry["optional_variables"]
            public = entry.get("public_variables", [])
            masked = run_mod.masked_names(entry)
            with self.subTest(id=entry["id"]):
                self.assertEqual(sorted(masked + public), sorted(injected))
                self.assertEqual(set(masked) & set(public), set())
                self.assertLessEqual(set(entry["variables"]), set(masked))  # a required variable is always masked
                values = {name: fake("v-") for name in injected}
                self.assertEqual({name for _needle, name in run_mod.needles_for(values, masked)}, set(masked))
            classified.update({(entry["id"], name): "public" if name in public else "masked"
                               for name in entry["optional_variables"]})
        self.assertEqual(injectable, INJECTABLE_IDS)
        # Every optional variable of an injectable entry, classified; a new one must be reviewed here.
        self.assertEqual(classified, {("alpaca-paper", "APCA_API_BASE_URL"): "public",
                                      ("alpaca-paper-2", "APCA_API_BASE_URL"): "public",
                                      ("sec-contact", "EDGAR_IDENTITY"): "masked"})

    def test_a_required_variable_is_masked_even_when_a_planted_entry_lists_it_public(self):
        # Review of 2026-09-29: masked_names() trusted public_variables as written. It now comes from the schema
        # module, where a public name is only ever an optional variable that is not also required.
        entry = {"variables": ["KEY_ID", "SECRET_KEY"], "optional_variables": ["BASE_URL", "KEY_ID"],
                 "public_variables": ["BASE_URL", "KEY_ID", "SECRET_KEY", "NOT_DECLARED"]}
        self.assertEqual(run_mod.masked_names(entry), ["KEY_ID", "SECRET_KEY"])
        self.assertEqual(run_mod.public_names(entry), ["BASE_URL"])

    def test_writer_and_reader_share_one_grammar(self):
        entry = {"id": "tavily", "variables": ["TAVILY_API_KEY"], "optional_variables": []}
        candidates = ["plain-Value_1.2+3/4=5:6@7", "with space inside", "semi;colon", "tilde~home", "quote'single",
                      "dollar$sign", "back`tick", "back\\slash", 'double"quote', " padded", "tab\there", "caf\u00e9",
                      "bell\x07"]
        for value in candidates:
            with self.subTest(value=value):
                try:
                    line = writer.encode("TAVILY_API_KEY", value)
                except writer.Refused:
                    for text in (f"export TAVILY_API_KEY={value}\n", f'export TAVILY_API_KEY="{value}"\n'):
                        with self.assertRaises(run_mod.Refused):
                            run_mod.parse("tavily", text.encode("utf-8"), entry)
                else:
                    self.assertEqual(run_mod.parse("tavily", line.encode("ascii"), entry), {"TAVILY_API_KEY": value})

    def test_grammar_is_python_3_9_compatible(self):
        # The Claude hook and a Mac's Command Line Tools python3 may be 3.9 (docs/decisions/2026-09-29-key-management.md).
        ast.parse(TOOL.read_text(encoding="utf-8"), feature_version=(3, 9))

    def test_unexpected_errors_print_only_the_type(self):
        secret = fake("tvly-")
        err = io.StringIO()
        with mock.patch.object(run_mod, "read_store", side_effect=RuntimeError(f"boom {secret}")), \
                mock.patch.object(run_mod, "disable_core_dumps"), contextlib.redirect_stderr(err):
            code = run_mod.main(["tavily", "--", "true"])
        self.assertEqual(code, 1)
        self.assertIn("RuntimeError", err.getvalue())
        self.assertIn("internal_error", err.getvalue())
        self.assertNotIn(secret, err.getvalue())
        self.assertNotIn("boom", err.getvalue())


if __name__ == "__main__":
    unittest.main()
