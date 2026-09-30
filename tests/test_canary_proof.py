"""Canary proof acceptance: synthetic canaries, sinks, databases, journal and stores only (contract draft 3, section 13,
with amendments C1-C14).

Local integration class. Every test builds a new synthetic host under /tmp: its own HOME and XDG directories, a 0700
runtime directory and credential store, a copy of the pinned guard, and a CHILD_PATH of the real reviewed executables
plus fakes for journalctl, systemd-cat and systemctl that serve a synthetic journal (the build suite writes nothing to
the user journal, C13). No test opens the operator's store, env or auth files, transcripts, journal or databases,
and none contacts a provider or ports 20128/20129. Synthetic sentinels exist only in test fixtures; the coordinator
subprocess never receives them. Tools run through launchers that set module hooks and constants (contract 9.5); the
real ecosystem-bounded-run is used wherever a class needs systemd scope containment.

Class prefixes (C13) and skip reasons: Boundary, Request, Stability, Mode, Fifo, Containment, Store, Probe, Command,
Integrated. `python3 -I tests/test_canary_proof.py --skip-list` prints the machine-readable skip list.
"""
import copy
import json
import os
import re
import secrets
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _directory in (ROOT / "tools" / "credentials", ROOT / "scripts", ROOT):
    if str(_directory) not in sys.path:
        sys.path.insert(0, str(_directory))
import canary_probe as probe  # noqa: E402
import canary_proof as cp  # noqa: E402
import canary_scan_worker as wire  # noqa: E402
import credential_run as runner  # noqa: E402

TOOL, WORKER, RUNNER = ROOT / "tools/credentials/canary_proof.py", cp.WORKER, cp.RUNNER
PYTHON = "/usr/bin/python3"
REAL = {name: shutil.which(name, path="/usr/bin:/bin") for name in (
    "rg", "git", "gzip", "bzip2", "xz", "setpriv", "nice", "ionice", "sh", "cat", "sleep")}


def _rg_reviewed() -> bool:
    try:
        text = subprocess.run([REAL["rg"], "--version"], capture_output=True, text=True, timeout=10).stdout
    except (OSError, TypeError, subprocess.SubprocessError):
        return False
    return wire.version_code("rg", text) in wire.REVIEWED_RG


def _real_scope() -> bool:
    try:
        return subprocess.run([str(RUNNER), "/bin/true"], env={"PATH": "/usr/bin:/bin", "ECOSYSTEM_JOB_SECONDS": "30",
                                                               "ECOSYSTEM_JOB_CPU_QUOTA": "200%"},
                              capture_output=True, timeout=60).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


LINUX = sys.platform.startswith("linux")
RG_OK = LINUX and _rg_reviewed()
SETPRIV_OK = LINUX and REAL["setpriv"] is not None
SCOPE_OK = LINUX and _real_scope()
NOT_LINUX, NO_RG, NO_SETPRIV, NO_SCOPE = ("not Linux", "reviewed ripgrep unavailable",
                                          "setpriv --pdeathsig unavailable", "systemd user scope unavailable")


def needs_tools(test):
    test = unittest.skipUnless(LINUX, NOT_LINUX)(test)
    test = unittest.skipUnless(RG_OK, NO_RG)(test)
    return unittest.skipUnless(SETPRIV_OK, NO_SETPRIV)(test)


def needs_scope(test):
    return unittest.skipUnless(SCOPE_OK, NO_SCOPE)(needs_tools(test))


COORDINATOR = r"""
import json, os, signal, sys, time
config = json.loads(sys.argv[1])
sys.path[:0] = [config["root"] + "/tools/credentials", config["root"] + "/scripts"]
import canary_proof as cp
for name, value in config["constants"].items():
    setattr(cp, name, tuple(value) if isinstance(value, list) and name.endswith("SINKS") else value)
audit = []
def act(spec):
    def run(*args):
        if spec.get("when") and (not args or spec["when"].encode() not in bytes(args[0], "utf-8") if isinstance(args[0] if args else b"", str) else spec["when"].encode() not in (args[0] if args else b"")):
            return
        kind = spec["do"]
        if kind == "kill":
            os.kill(os.getpid(), signal.SIGKILL)
        if kind == "fail":
            raise OSError("injected")
        if kind == "signal":
            os.kill(os.getpid(), getattr(signal, spec["signal"]))
            time.sleep(2)
        if kind == "record":
            with open(spec["path"], "a") as handle:
                handle.write(spec["label"] + "\n")
        if kind == "remove":
            os.unlink(spec["path"])
        if kind == "write":
            with open(spec["path"], "ab") as handle:
                handle.write(bytes.fromhex(spec["data"]))
        if kind == "union":
            union_edit(spec["edit"])
    return run
def union_edit(edit):
    import glob
    path = max(glob.glob(os.environ["XDG_RUNTIME_DIR"] + "/native-agent-stack/canary-proof/*/scan-*/patterns"),
               key=os.path.getmtime)
    lines = open(path, "rb").read().split(b"\n")
    lines = lines[1:] if edit == "drop" else lines + [b""] if edit == "blank" else [lines[0][:-1] + b"X"] + lines[1:]
    with open(path, "wb") as handle:
        handle.write(b"\n".join(lines))
if config.get("count_pipes"):
    real_pipe = os.pipe
    def pipe():
        with open(config["count_pipes"], "a") as handle:
            handle.write("pipe\n")
        return real_pipe()
    os.pipe = pipe
for name, spec in config["hooks"].items():
    cp.HOOKS[name] = act(spec)
if config.get("forbid_list"):  # the store is never listed (contract 7): a listing of it raises in this launcher
    forbidden, real_scandir, real_listdir2 = os.path.realpath(config["forbid_list"]), os.scandir, os.listdir
    def guarded(function):
        def inner(path=".", *a, **k):
            if not isinstance(path, int) and os.path.realpath(path) == forbidden:
                raise PermissionError("store listed")
            return function(path, *a, **k)
        return inner
    os.scandir, os.listdir = guarded(real_scandir), guarded(real_listdir2)
if config.get("audit"):
    import builtins, io
    real_read, real_pread, real_open, real_readlink, real_listdir = os.read, os.pread, io.open, os.readlink, os.listdir
    def read(fd, n):
        data = real_read(fd, n); audit.append(data); return data
    def pread(fd, n, offset):
        data = real_pread(fd, n, offset); audit.append(data); return data
    def readlink(*a, **k):
        data = real_readlink(*a, **k); audit.append(os.fsencode(data)); return data
    def listdir(*a, **k):
        data = real_listdir(*a, **k); audit.append(repr(data).encode()); return data
    class Recorder:
        def __init__(self, handle): self._h = handle
        def __getattr__(self, name): return getattr(self._h, name)
        def __enter__(self): return self
        def __exit__(self, *a): return self._h.__exit__(*a)
        def __iter__(self):
            for line in self._h:
                audit.append(line if isinstance(line, bytes) else line.encode("utf-8", "surrogateescape")); yield line
        def read(self, *a):
            data = self._h.read(*a); audit.append(data if isinstance(data, bytes) else data.encode("utf-8", "surrogateescape")); return data
        def readline(self, *a):
            data = self._h.readline(*a); audit.append(data if isinstance(data, bytes) else data.encode("utf-8", "surrogateescape")); return data
    def opener(*a, **k):
        return Recorder(real_open(*a, **k))
    os.read, os.pread, os.readlink, os.listdir, io.open, builtins.open = read, pread, readlink, listdir, opener, opener
    if config.get("unsafe_parent_read"):
        real_build = cp.Request.build
        def unsafe(self):  # a deliberately unsafe coordinator: it peeks at a sink's header and names (B2)
            for directory, _dirs, files in os.walk(config["unsafe_parent_read"]):
                for name in files:
                    audit.append(name.encode())
                    with open(os.path.join(directory, name), "rb") as handle:
                        handle.read(64)
            return real_build(self)
        cp.Request.build = unsafe
try:
    code = cp.main(config["argv"])
finally:
    if config.get("audit"):
        with real_open(config["audit"], "wb") as handle:
            handle.write(b"\n".join(bytes(item) if not isinstance(item, bytes) else item for item in audit))
            handle.write(b"\n" + repr(cp.AUDIT).encode())
sys.exit(code)
"""

WORKER_LAUNCHER = r"""
import json, os, sys, time
config = json.loads(sys.argv[1])
sys.path[:0] = [config["root"] + "/tools/credentials", config["root"] + "/scripts"]
import canary_scan_worker as w
for name, value in config["constants"].items():
    setattr(w, name, value)
if config.get("stub_scope"):
    w.SCOPE_CHECK = lambda: None
if config.get("fs_magic") is not None:
    w.fs_magic = lambda fd: config["fs_magic"]
def act(spec):
    def run(*args):
        if spec.get("when") and not (args and spec["when"].encode() in (args[0] if isinstance(args[0], bytes) else args[0].encode())):
            return
        if spec.get("once") and os.path.exists(spec["once"]):
            return
        if spec.get("once"):
            open(spec["once"], "w").close()
        kind = spec["do"]
        if kind == "block":
            with open(spec["path"], "rb") as handle:
                handle.read()
        elif kind == "sleep":
            time.sleep(spec["seconds"])
        elif kind == "replace":
            os.replace(spec["source"], spec["target"])
        elif kind == "fifo":
            os.unlink(spec["target"]); os.mkfifo(spec["target"])
        elif kind == "write":
            with open(spec["target"], "r+b" if spec.get("offset") is not None else "ab") as handle:
                if spec.get("offset") is not None:
                    handle.seek(spec["offset"])
                handle.write(bytes.fromhex(spec["data"]))
            if spec.get("mtime") is not None:
                os.utime(spec["target"], ns=(spec["mtime"], spec["mtime"]))
        elif kind == "create":
            os.makedirs(os.path.dirname(spec["target"]), exist_ok=True)
            with open(spec["target"], "wb") as handle:
                handle.write(bytes.fromhex(spec["data"]))
        elif kind == "symlink":
            os.unlink(spec["target"]); os.symlink(spec["source"], spec["target"])
        elif kind == "remove":
            os.unlink(spec["target"])
        elif kind == "kill":
            os.kill(os.getpid(), 9)
        elif kind == "union":
            import glob
            path = max(glob.glob(config["runtime"] + "/native-agent-stack/canary-proof/*/scan-*/patterns"),
                       key=os.path.getmtime)
            with open(path, "ab") as handle:
                handle.write(b"CNRYCTLunplannedline\n")
        elif kind == "unlink-control":
            import glob
            for path in glob.glob(config["runtime"] + "/native-agent-stack/canary-proof/*/scan-*/" + spec["glob"]):
                os.unlink(path)
    return run
if config.get("stdio"):
    with open(config["stdio"], "a") as handle:
        handle.write(os.readlink("/proc/self/fd/1") + " " + os.readlink("/proc/self/fd/2") + "\n")
for name, spec in config["hooks"].items():
    w.HOOKS[name] = act(spec)
if config.get("trace"):  # test diagnostics of synthetic fixtures only; production workers never print a traceback
    import traceback
    def traced(function):
        def inner(*args, **kwargs):
            try:
                return function(*args, **kwargs)
            except Exception:
                with open(config["trace"], "a") as handle:
                    traceback.print_exc(file=handle)
                raise
        return inner
    w.Scan.run, w.dump = traced(w.Scan.run), traced(w.dump)
sys.exit(w.main(sys.argv[2:]))
"""

FAKE_JOURNALCTL = r"""#!/usr/bin/python3 -I
import json, os, struct, sys
store = __STORE__
args = sys.argv[1:]
if args == ["--version"]:
    print("systemd 255 (255.4-synthetic)")
    sys.exit(0)
entries = json.load(open(store)) if os.path.exists(store) else []
cursor = next((a.split("=", 1)[1] for a in args if a.startswith("--cursor=")), None)
ident = next((a.split("=", 1)[1] for a in args if a.startswith("SYSLOG_IDENTIFIER=")), None)
def seq(text):
    return int(dict(part.split("=", 1) for part in text.split(";"))["i"], 16)
start = 0
if cursor is not None:
    later = [i for i, e in enumerate(entries) if seq(dict(e)["__CURSOR"]) >= seq(cursor)]
    start = later[0] if later else len(entries)
out = sys.stdout.buffer
for entry in entries[start:]:
    fields = dict(entry)
    if ident and fields.get("SYSLOG_IDENTIFIER") != ident:
        continue
    for name, value in entry:
        data = bytes.fromhex(value[4:]) if value.startswith("hex:") else value.encode("utf-8", "surrogateescape")
        if b"\n" in data or any(byte < 32 and byte != 9 for byte in data):
            out.write(name.encode() + b"\n" + struct.pack("<Q", len(data)) + data + b"\n")
        else:
            out.write(name.encode() + b"=" + data + b"\n")
    out.write(b"\n")
"""

FAKE_SYSTEMD_CAT = r"""#!/usr/bin/python3 -I
import json, os, secrets, sys
store = __STORE__
if sys.argv[1:] == ["--version"]:
    print("systemd 255 (255.4-synthetic)")
    sys.exit(0)
entries = json.load(open(store)) if os.path.exists(store) else []
for line in sys.stdin.buffer.read().decode().splitlines():
    number = len(entries) + 1
    cursor = "s=%s;i=%x;b=%s;m=%x;t=%x;x=%s" % ("a" * 32, number, "b" * 32, number, number, secrets.token_hex(8))
    entries.append([["__CURSOR", cursor], ["SYSLOG_IDENTIFIER", sys.argv[sys.argv.index("-t") + 1]], ["MESSAGE", line]])
json.dump(entries, open(store, "w"))
"""

FAKE_SYSTEMCTL = r"""#!/usr/bin/python3 -I
import sys
if sys.argv[1:] == ["--version"]:
    print("systemd 255 (255.4-synthetic)")
    sys.exit(0)
if sys.argv[1:] == ["--user", "show-environment"]:
    sys.stdout.buffer.write(open(__ENVIRONMENT__, "rb").read())
    sys.exit(0)
sys.exit(1)
"""


def journal_entry(number: int, message: str, **fields) -> list:
    cursor = "s=%s;i=%x;b=%s;m=%x;t=%x;x=%s" % ("c" * 32, number, "d" * 32, number, number, "e" * 16)
    return [["__CURSOR", cursor], ["SYSLOG_IDENTIFIER", fields.pop("ident", "canary-proof-unit")],
            ["MESSAGE", message], *[[name, value] for name, value in fields.items()]]


class Host:
    """A synthetic workstation under /tmp for one test (contract 13)."""

    def __init__(self, test: unittest.TestCase, real_scope: bool = False, session: str = None):
        self.test, self.real_scope = test, real_scope
        self.root = Path(tempfile.mkdtemp(prefix="cpt-"))
        test.addCleanup(self.cleanup)
        self.home, self.run_dir = self.root / "home", self.root / "run"
        self.state, self.config = self.home / ".local" / "state", self.home / ".config"
        for directory in (self.home, self.state, self.config, self.home / ".cache", self.root / "tasks"):
            directory.mkdir(parents=True, exist_ok=True)
        self.run_dir.mkdir(mode=0o700)
        self.store = self.config / "native-agent-stack"
        self.store.mkdir(mode=0o700)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        for name, path in REAL.items():
            if path:
                os.symlink(path, self.bin / name)
        os.symlink(PYTHON, self.bin / "python3")
        self.journal, self.environment = self.root / "journal.json", self.root / "environment"
        self.journal.write_text("[]")
        self.environment.write_bytes(b"PATH=/usr/bin\nLANG=C.UTF-8\n")
        for name, code in (("journalctl", FAKE_JOURNALCTL), ("systemd-cat", FAKE_SYSTEMD_CAT),
                           ("systemctl", FAKE_SYSTEMCTL)):
            self.script(name, code.replace("__STORE__", repr(str(self.journal))).replace(
                "__ENVIRONMENT__", repr(str(self.environment))))
        self.script("stub-runner", "#!/bin/sh\nexec \"$@\"\n")
        hooks = self.home / ".claude" / "hooks"
        hooks.mkdir(parents=True)
        shutil.copyfile(ROOT / "scripts/hooks/secret_path_guard.py", hooks / "secret_path_guard.py")
        self.codex = self.home / ".codex"
        self.codex.mkdir()
        self.session = session
        self.worker = {"constants": {"BUDGET_CAP": 30.0}, "hooks": {}, "stub_scope": not real_scope,
                       "runtime": str(self.run_dir)}
        self.dumper = {"constants": {}, "hooks": {}}
        self.constants = {"CHILD_PATH": str(self.bin), "RUNNER": str(RUNNER if real_scope else self.bin / "stub-runner"),
                          "TASKS_ROOT": str(self.root / "tasks"), "SETTLE_SECONDS": 0,
                          "SCOPE_SECONDS": {**{sink: 120 for sink in wire.SINKS}, "setup": 120}}
        self.run_id = None

    def script(self, name: str, text: str) -> Path:
        path = self.bin / name
        if path.is_symlink() or path.exists():
            path.unlink()
        path.write_text(text)
        path.chmod(0o755)
        return path

    def cleanup(self) -> None:
        for path in self.root.rglob("*"):
            try:
                if path.is_dir() and not path.is_symlink():
                    path.chmod(0o700)
            except OSError:
                pass
        shutil.rmtree(self.root, ignore_errors=True)

    def env(self, **extra) -> dict:
        env = {"HOME": str(self.home), "XDG_RUNTIME_DIR": str(self.run_dir), "XDG_STATE_HOME": str(self.state),
               "XDG_CONFIG_HOME": str(self.config), "XDG_CACHE_HOME": str(self.home / ".cache"),
               "PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"}
        env.update(extra)
        return {name: value for name, value in env.items() if value is not None}

    def tool(self, *argv, hooks=None, audit=None, unsafe=None, timeout=300, env=None, tty=False,
             worker=None, dumper=None, forbid_list=None, count_pipes=None) -> subprocess.CompletedProcess:
        """Run canary_proof.main(argv) in a launcher process whose module hooks and constants are set here."""
        worker_config = copy.deepcopy(self.worker)
        worker_config.update(root=str(ROOT), **(worker or {}))
        dumper_config = copy.deepcopy(self.dumper)
        dumper_config.update(root=str(ROOT), **(dumper or {}))
        constants = dict(self.constants)
        constants["WORKER_COMMAND"] = [str(self.bin / "python3"), "-I", "-S", "-c", WORKER_LAUNCHER,
                                       json.dumps(worker_config)]
        constants["DUMPER_COMMAND"] = [str(self.bin / "python3"), "-I", "-S", "-c", WORKER_LAUNCHER,
                                       json.dumps(dumper_config), "sqlite-dumper"]
        config = {"root": str(ROOT), "argv": [str(a) for a in argv], "constants": constants, "hooks": hooks or {},
                  "audit": str(audit) if audit else None, "unsafe_parent_read": unsafe,
                  "forbid_list": str(forbid_list) if forbid_list else None,
                  "count_pipes": str(count_pipes) if count_pipes else None}
        command = [sys.executable, "-I", "-S", "-c", COORDINATOR, json.dumps(config)]
        if tty:
            return run_in_pty(command, env or self.env(), timeout)
        return subprocess.run(command, env=env or self.env(), capture_output=True, timeout=timeout)

    def prepare(self, *extra) -> str:
        args = ["prepare", *extra] + (["--session", self.session] if self.session else [])
        result = self.tool(*args)
        self.test.assertEqual(result.returncode, 0, result.stderr)
        self.run_id = re.search(rb"run: (cp-\S+)", result.stdout).group(1).decode()
        return self.run_id

    def events(self) -> list:
        path = self.run_dir / "native-agent-stack" / "canary-proof" / self.run_id / "events.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines()]

    def scan(self, phase: str = "baseline", *extra, **kwargs) -> subprocess.CompletedProcess:
        return self.tool("scan", "--run", self.run_id, "--phase", phase, *extra, **kwargs)

    @property
    def path(self) -> Path:
        return self.run_dir / "native-agent-stack" / "canary-proof" / self.run_id

    def canary(self, consumer: str = "fresh-claude-session", attempt: int = 1) -> str:
        return (self.path / "patterns" / f"{consumer}.{attempt}").read_text().split("\n", 1)[0]

    def finished(self) -> dict:
        return [event for event in self.events() if event["event"] == "scan_finished"][-1]

    def verdict(self, command: str = "status") -> tuple:
        result = self.tool(command, "--run", self.run_id)
        match = re.search(rb"verdict: (\w+) hits=(\d+) codes=(\S*)", result.stdout)
        codes = match.group(3).decode().split(",") if match and match.group(3) != b"none" else []
        return result.returncode, (match.group(1).decode() if match else None), codes

    def arm(self, consumer: str, *extra) -> int:
        result = self.tool("arm", "--run", self.run_id, consumer, *extra)
        self.test.assertEqual(result.returncode, 0, result.stderr)
        return int(re.search(rb"--attempt (\d+)", result.stdout).group(1))

    def consume(self, consumer: str, attempt: int) -> tuple:
        """The probe through the real credential runner and the synthetic store: (masked stdout, masked stderr)."""
        command = [PYTHON, "-I", str(ROOT / "tools/credentials/credential_run.py"), "canary-e2e", "--", PYTHON, "-I",
                   str(ROOT / "tools/credentials/canary_probe.py"), "--run", self.run_id, "--consumer", consumer,
                   "--attempt", str(attempt)] + (["--leak-check"] if consumer == "systemd-user-unit" else [])
        result = subprocess.run(command, env=self.env(), capture_output=True, timeout=60)
        self.test.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout, result.stderr

    def disarm(self) -> None:
        result = self.tool("disarm", "--run", self.run_id)
        self.test.assertEqual(result.returncode, 0, result.stderr)

    def journal_add(self, *messages: bytes, **fields) -> None:
        entries = json.loads(self.journal.read_text())
        for message in messages:
            number = len(entries) + 1
            entry = journal_entry(number, "", **fields)
            entry[2] = ["MESSAGE", "hex:" + message.hex()]
            entries.append(entry)
        self.journal.write_text(json.dumps(entries))

    def record(self, consumer: str, text: str, lane: Path = None) -> Path:
        """Put a consumer's output where its client would record it (contract 12 recording classes)."""
        own, other = self.session or "own-session", "5ab1e2c3-other-session"
        line = json.dumps({"type": "tool_result", "content": text}) + "\n"
        path = {"fresh-claude-session": f".claude/projects/p/{other}.jsonl",
                "subagent": f".claude/projects/p/{other}/subagents/agent-1.jsonl",
                "workflow-child": f".claude/projects/p/{own}/subagents/workflow-1.jsonl",
                "codex-exec": ".codex/sessions/2026/09/30/rollout-a.jsonl"}.get(consumer)
        target = (lane / "sessions/2026/09/30/rollout-b.jsonl") if consumer == "omniroute-lane" else self.home / path
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "a") as handle:
            handle.write(line)
        return target

    def full_cycle(self, lane: Path) -> None:
        """Six consumer attempts through the real runner, each recorded where its client would record it."""
        for consumer in cp.CONSUMERS:
            attempt = self.arm(consumer, *(["--codex-home", str(lane)] if consumer == "omniroute-lane" else []))
            out, err = self.consume(consumer, attempt)
            if consumer == "systemd-user-unit":
                lines = (out + err).split(b"\n")
                self.journal_add(*[line for line in lines if line])
            else:
                self.record(consumer, out.decode().strip(), lane)
            self.disarm()


def run_in_pty(command, env, timeout) -> subprocess.CompletedProcess:
    import pty
    pid, fd = pty.fork()
    if pid == 0:
        os.execve(command[0], command, env)
    output, deadline = b"", time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            chunk = os.read(fd, 65536)
        except OSError:
            break
        if not chunk:
            break
        output += chunk
    _, status = os.waitpid(pid, 0)
    return subprocess.CompletedProcess(command, os.waitstatus_to_exitcode(status), output, b"")


def processes_with(marker: str) -> list:
    """The independent observer: pids of this user's processes whose command line or cwd names the fixture path."""
    found, needle = [], marker.encode()
    for entry in os.listdir("/proc"):
        if not entry.isdigit() or int(entry) == os.getpid():
            continue
        try:
            with open(f"/proc/{entry}/cmdline", "rb") as handle:
                cmdline = handle.read()
            if os.stat(f"/proc/{entry}").st_uid != os.getuid():
                continue
            state = open(f"/proc/{entry}/stat", "rb").read().rsplit(b")", 1)[1].split()[0]
        except OSError:
            continue
        if needle in cmdline and state != b"Z":
            found.append(int(entry))
    return found


def wait_gone(marker: str, seconds: float) -> list:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        left = processes_with(marker)
        if not left:
            return []
        time.sleep(0.25)
    return processes_with(marker)


SESSION = "0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0"


def clean_run(test, real_scope: bool = False, session: str = SESSION) -> tuple:
    """prepare, a complete baseline, six consumers through the real runner and a final: (host, lane home)."""
    host = Host(test, real_scope=real_scope, session=session)
    lane = host.root / "lane-home"
    lane.mkdir()
    host.prepare("--codex-home", str(lane), "--transcripts", "confirmed")
    baseline = host.scan("baseline")
    test.assertEqual(baseline.returncode, 0, baseline.stdout + baseline.stderr)
    host.full_cycle(lane)
    final = host.scan("final")
    test.assertEqual(final.returncode, 0, final.stdout + final.stderr)
    return host, lane


@needs_tools
class IntegratedTests(unittest.TestCase):
    def test_full_sequence_is_clean_and_cleanup_receipt_matches_verdict(self):
        host, _lane = clean_run(self)
        code, verdict, codes = host.verdict("verdict")
        self.assertEqual((code, verdict, codes), (0, "clean", []), "IN-clean")
        receipts = sorted((host.state / "native-agent-stack" / "canary-proof").glob("*.json"))
        self.assertEqual(len(receipts), 1)
        first = json.loads(receipts[0].read_text())
        result = host.tool("cleanup", "--run", host.run_id)
        self.assertEqual(result.returncode, 0, result.stderr)
        receipts = sorted((host.state / "native-agent-stack" / "canary-proof").glob("*.json"))
        second = json.loads(receipts[-1].read_text())
        for key in ("verdict", "codes", "claim", "hits"):
            self.assertEqual(first[key], second[key], f"C4-cleanup-receipt {key}")
        self.assertFalse(host.path.exists())
        self.assertIn("clean for the coverage stated here", first["claim"])


class UnitTests(unittest.TestCase):
    """Pure functions: canary grammar, forms, tags, CP03 layout, version codes and every routing row."""

    def test_canary_grammar(self):
        import set_credential as writer
        for _ in range(200):
            canary = cp.new_canary()
            self.assertEqual(len(canary), 42, "U-grammar length")
            self.assertTrue(canary.startswith("CNRYE2E") and writer.BARE_VALUE.match(canary), "U-grammar")
            self.assertEqual([canary.count(symbol) for symbol in "+/="], [1, 1, 1], "U-grammar symbols")

    def test_forms_are_the_runners_deduplicated_forms(self):
        canary = cp.new_canary()
        expected = list(dict.fromkeys(form.decode() for form in runner.encoded_forms(canary.encode())))
        self.assertEqual(cp.forms(canary), expected, "U-forms")
        self.assertTrue(all(len(form) >= 6 and form.isprintable() for form in expected), "U-forms grammar")

    def test_independent_probe_corpus_is_caught_by_the_forms_over_1000_canaries(self):
        for _ in range(1000):
            canary = cp.new_canary()
            forms = cp.forms(canary)
            for line in probe.leak_forms(canary):
                self.assertTrue(any(form in line for form in forms), "U-corpus")

    def test_tag_agrees_with_the_probe_and_binds_run_consumer_attempt(self):
        canary, run = cp.new_canary(), "cp-20260930t120000z-abcdef"
        line = cp.tag_line(canary, run, "subagent", 2)
        self.assertEqual(line, f"canary-probe subagent attempt 2: tag {probe.tag(canary, run, 'subagent', 2)}", "U-tag")
        tags = {probe.tag(canary, run, "subagent", 2), probe.tag(canary, run, "subagent", 1),
                probe.tag(canary, run, "workflow-child", 2), probe.tag(canary, "cp-20260930t120000z-abcdee",
                                                                       "subagent", 2)}
        self.assertEqual(len(tags), 4, "U-tag binding")

    def test_record_layout_is_128_bytes_and_round_trips(self):
        self.assertEqual(wire.RECORD.size, 128, "B4-size")
        record = wire.unpack(wire.pack(kind=wire.RESULT, check=7, reason=wire.R["deadline"], exit=-9))
        self.assertEqual((record.magic, record.check, record.reason, record.exit), (b"CP03", 7, 18, -9))
        self.assertEqual(len(wire.REASONS), 50)

    def test_version_code_formula(self):
        self.assertEqual(wire.version_code("rg", "ripgrep 14.1.0"), 14001000, "U-version")
        self.assertEqual(wire.version_code("rg", "ripgrep 15.2.0 (rev e89fff89ac)"), 15002000)
        self.assertEqual(wire.version_code("git", "git version 2.43.0"), 2043000)
        self.assertEqual(wire.version_code("journalctl", "systemd 255 (255.4-1ubuntu8.17)"), 255000000)
        self.assertEqual(wire.version_code("bzip2", "bzip2, a block-sorting file compressor.  Version 1.0.8, x"),
                         1000008)

    def test_every_routing_row(self):
        rows = [(b"SQLite format 3\x00", b"x", ("sqlite", "sqlite")), (b"\x37\x7f\x06\x82", b"x", ("wal", "sqlite")),
                (b"\x1f\x8b\x08", b"noext", ("decode", "gzip")), (b"BZh9", b"x", ("decode", "bzip2")),
                (b"\xfd7zXZ\x00", b"x", ("decode", "xz")), (b"plain", b"f.lzma", ("decode", "lzma")),
                (b"plain", b"f.tlz", ("decode", "lzma")), (b"\x28\xb5\x2f\xfd", b"x", ("uncovered", "zstd")),
                (b"\x5a\x2a\x4d\x18", b"x", ("uncovered", "zstd")), (b"\x04\x22\x4d\x18", b"x", ("uncovered", "lz4")),
                (b"\x02\x21\x4c\x18", b"x", ("uncovered", "lz4")), (b"\x1f\x9d", b"x", ("uncovered", "compress")),
                (b"LZIP", b"x", ("uncovered", "lzip")), (b"\x89LZO", b"x", ("uncovered", "lzop")),
                (b"\xff\x06\x00\x00sNaPpY", b"x", ("uncovered", "snappy")), (b"plain", b"f.zst", ("uncovered", "zstd")),
                (b"plain", b"f.br", ("uncovered", "brotli")), (b"plain", b"f.Z", ("uncovered", "compress")),
                (b"plain", b"f.sz", ("uncovered", "snappy")), (b"PK\x03\x04", b"x", ("container", "container")),
                (b"PK\x05\x06", b"x", ("container", "container")), (b"7z\xbc\xaf\x27\x1c", b"x", ("container", "container")),
                (b"Rar!\x1a\x07", b"x", ("container", "container")), (b"%PDF-1.7", b"x", ("container", "container")),
                (b"\0" * 257 + b"ustar", b"x", ("container", "container")), (b"PACK", b"x", ("container", "container")),
                (b"plain", b"f.gz", ("unknown", "gzip")), (b"plain", b"f.bz2", ("unknown", "bzip2")),
                (b"plain", b"f.txt", ("plain", None))]
        for head, name, expected in rows:
            with self.subTest(head=head[:6], name=name):
                self.assertEqual(wire.route(head, name), expected, f"M2-route {expected[1]}")
        self.assertEqual(wire.route(b"PACK", b"pack-" + b"a" * 40 + b".pack", git_pack=True), ("plain", None))


@needs_tools
class ProbeTests(unittest.TestCase):
    def run_probe(self, *args, env=None, isolated=True):
        command = [PYTHON] + (["-I"] if isolated else []) + [str(ROOT / "tools/credentials/canary_probe.py"), *args]
        return subprocess.run(command, env=env or {"PATH": "/usr/bin:/bin"}, capture_output=True, timeout=30)

    def test_refuses_without_isolation_and_without_the_value(self):
        canary = cp.new_canary()
        args = ["--run", "cp-20260930t120000z-abcdef", "--consumer", "subagent", "--attempt", "1"]
        refused = self.run_probe(*args, env={"PATH": "/usr/bin", "CANARY_E2E_KEY": canary}, isolated=False)
        self.assertEqual(refused.returncode, 2, "P-isolation")
        self.assertEqual(self.run_probe(*args).returncode, 3, "P-absent")
        leak = self.run_probe(*args, "--leak-check", env={"PATH": "/usr/bin", "CANARY_E2E_KEY": canary})
        self.assertEqual(leak.returncode, 2, "P-leak-consumer")
        good = self.run_probe(*args, env={"PATH": "/usr/bin", "CANARY_E2E_KEY": canary})
        self.assertEqual(good.stdout, (cp.tag_line(canary, args[1], "subagent", 1) + "\n").encode(), "P-tag-only")
        self.assertFalse(any(form.encode() in good.stdout + good.stderr for form in cp.forms(canary)), "P-no-form")

    def test_opens_no_file(self):
        canary, real_open, real_os_open = cp.new_canary(), open, os.open
        import builtins
        from unittest import mock
        with mock.patch.dict(os.environ, {"CANARY_E2E_KEY": canary}), \
                mock.patch.object(builtins, "open", side_effect=OSError("no file")), \
                mock.patch.object(os, "open", side_effect=OSError("no file")), \
                mock.patch.object(os, "write") as write:
            code = probe.main(["--run", "cp-20260930t120000z-abcdef", "--consumer", "codex-exec", "--attempt", "3"])
        self.assertEqual(code, 0, "P-no-file")
        self.assertEqual(write.call_args_list[0].args[1].decode().split(": tag ")[0],
                         "canary-probe codex-exec attempt 3")
        del real_open, real_os_open

    def test_real_runner_masks_every_leak_check_form_exactly(self):
        host = Host(self)
        canary = cp.new_canary()
        import set_credential as writer
        fd = os.open(host.store, os.O_RDONLY | os.O_DIRECTORY)
        writer.create_exclusively(fd, "canary-e2e.env", writer.encode("CANARY_E2E_KEY", canary))
        os.close(fd)
        result = subprocess.run(
            [PYTHON, "-I", str(ROOT / "tools/credentials/credential_run.py"), "canary-e2e", "--", PYTHON, "-I",
             str(ROOT / "tools/credentials/canary_probe.py"), "--run", "cp-20260930t120000z-abcdef", "--consumer",
             "systemd-user-unit", "--attempt", "1", "--leak-check"], env=host.env(), capture_output=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        both = result.stdout + result.stderr
        self.assertEqual(both.count(b"[REDACTED:CANARY_E2E_KEY]"), cp.masked_markers(canary), "P-mask count")
        self.assertNotIn(b"REDACTED-PARTIAL", both, "P-mask partial")
        self.assertFalse(any(form.encode() in both for form in cp.forms(canary)), "P-mask forms")
        self.assertIn(cp.tag_line(canary, "cp-20260930t120000z-abcdef", "systemd-user-unit", 1).encode(), both)


@needs_tools
class StoreTests(unittest.TestCase):
    """Create-only publication, foreign inodes, mode, no listing, recovery and refusals (D2 13.1 store list, C3)."""

    def armed_host(self):
        host = Host(self)
        host.prepare()
        self.assertEqual(host.scan("baseline").returncode, 0)
        return host

    def test_arm_is_create_only_and_an_existing_file_is_left_untouched(self):
        host = self.armed_host()
        existing = host.store / "canary-e2e.env"
        existing.write_text("export CANARY_E2E_KEY=previous-synthetic-value\n")
        existing.chmod(0o600)
        before = existing.stat()
        result = host.tool("arm", "--run", host.run_id, "subagent")
        self.assertEqual(result.returncode, 1, "S-create-only")
        self.assertEqual((existing.stat().st_ino, existing.read_text()),
                         (before.st_ino, "export CANARY_E2E_KEY=previous-synthetic-value\n"), "S-create-only kept")

    def test_store_mode_0750_and_missing_store_refuse_without_change(self):
        host = self.armed_host()
        host.store.chmod(0o750)
        self.assertEqual(host.tool("arm", "--run", host.run_id, "subagent").returncode, 1, "S-mode")
        self.assertEqual(stat.S_IMODE(host.store.stat().st_mode), 0o750, "S-mode unchanged")
        host.store.chmod(0o700)
        shutil.rmtree(host.store)
        self.assertEqual(host.tool("arm", "--run", host.run_id, "subagent").returncode, 1, "S-missing")
        self.assertFalse(host.store.exists(), "S-missing not created")

    def test_arm_and_disarm_never_list_the_store(self):
        host = self.armed_host()
        result = host.tool("arm", "--run", host.run_id, "subagent", forbid_list=host.store)
        self.assertEqual(result.returncode, 0, ("S-no-list", result.stderr))
        result = host.tool("disarm", "--run", host.run_id, forbid_list=host.store)
        self.assertEqual(result.returncode, 0, ("S-no-list disarm", result.stderr))

    def test_foreign_inode_is_never_removed_and_absence_is_verified(self):
        host = self.armed_host()
        host.arm("subagent")
        path = host.store / "canary-e2e.env"
        for replace in (False, True):  # recreated in place (a freed inode number can be reused) and renamed over
            if replace:
                other = host.store / "other"
                other.write_text("export CANARY_E2E_KEY=a-renamed-synthetic-file\n")
                other.chmod(0o600)
                os.replace(other, path)
            else:
                path.unlink()
                path.write_text("export CANARY_E2E_KEY=a-foreign-synthetic-file\n")
                path.chmod(0o600)
            self.assertEqual(host.tool("disarm", "--run", host.run_id).returncode, 1, "S-foreign")
            self.assertTrue(path.exists(), "S-foreign kept")
        path.unlink()
        host.disarm()
        last = host.events()[-1]
        self.assertEqual((last["event"], last["removed"], last["absent_verified"]), ("disarmed", False, True),
                         "S-absence")

    def test_recovery_adopts_only_an_owned_file_published_after_arming(self):
        host = self.armed_host()
        killed = host.tool("arm", "--run", host.run_id, "subagent", hooks={"after_publication": {"do": "kill"}})
        self.assertEqual(killed.returncode, -9)
        self.assertEqual(host.events()[-1]["event"], "arming")
        host.disarm()
        events = host.events()
        self.assertEqual([e["event"] for e in events[-2:]], ["armed", "disarmed"], "S-recovery")
        self.assertTrue(events[-2]["recovered"] and events[-1]["absent_verified"], "S-recovery flags")
        self.assertFalse((host.store / "canary-e2e.env").exists())

    def test_arm_refuses_armed_unbaselined_hit_and_unpinned_guard(self):
        host = Host(self)
        host.prepare()
        self.assertEqual(host.tool("arm", "--run", host.run_id, "subagent").returncode, 1, "S-refuse no-baseline")
        self.assertEqual(host.scan("baseline").returncode, 0)
        host.arm("subagent")
        self.assertEqual(host.tool("arm", "--run", host.run_id, "codex-exec").returncode, 1, "S-refuse armed")
        host.disarm()
        guard = host.home / ".claude/hooks/secret_path_guard.py"
        guard.write_text(guard.read_text() + "\n# drift\n")
        self.assertEqual(host.tool("arm", "--run", host.run_id, "codex-exec").returncode, 1, "S-refuse guard")
        guard.write_text(guard.read_text().replace("\n# drift\n", ""))
        (host.home / ".claude" / "leak.txt").write_text(host.canary("codex-exec") + "\n")
        self.assertEqual(host.scan("baseline").returncode, 5)
        self.assertEqual(host.tool("arm", "--run", host.run_id, "codex-exec").returncode, 1, "S-refuse hit")

    def test_concurrent_invocation_returns_75_and_admits_no_request(self):
        import fcntl
        host = Host(self)
        host.prepare()
        count = len(host.events())
        lock = os.open(host.run_dir / "ecosystem-canary-proof.lock", os.O_RDWR)
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            result = host.scan("baseline")
        finally:
            os.close(lock)
        self.assertEqual(result.returncode, 75, "C9-busy")
        self.assertEqual(len(host.events()), count, "C9-busy no request")


def sentinel(prefix: str) -> str:
    """An unrelated credential-like synthetic value: never a pattern, never given to the coordinator (contract 10.4)."""
    return prefix + secrets.token_hex(18)


def git_repo(path: Path, files: dict, pack: bool = True, loose: dict = None) -> Path:
    """A synthetic repository: files committed and packed, then `loose` committed loose; returns its .git."""
    env = {"PATH": "/usr/bin:/bin", "HOME": str(path), "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null",
           "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@invalid", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@invalid"}
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=path, env=env, check=True)
    for batch, repack in ((files, pack), (loose or {}, False)):
        if not batch:
            continue
        for name, data in batch.items():
            (path / name).write_bytes(data)
        subprocess.run(["git", "add", "-A"], cwd=path, env=env, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "c"], cwd=path, env=env, check=True)
        if repack:
            subprocess.run(["git", "repack", "-q", "-a", "-d"], cwd=path, env=env, check=True)
    return path / ".git"


def sqlite_file(path: Path, statements: list, encoding: str = None) -> Path:
    import sqlite3
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    if encoding:
        connection.execute(f"PRAGMA encoding='{encoding}'")
    for sql, parameters in statements:
        connection.execute(sql, parameters)
    connection.commit()
    connection.close()
    return path


def hits(host) -> list:
    return [event for event in host.events() if event["event"] == "hit"]


def sink_reasons(host, sink: str = "A1") -> list:
    return host.finished()["sinks"].get(sink, {}).get("reasons", ["not_scanned"])


def forms_in(data: bytes, value: str) -> bool:
    import base64
    raw = value.encode()
    return any(form in data for form in (raw, raw.hex().encode(), base64.b64encode(raw)[4:-4], repr(raw).encode()))


def wrapper(host, name: str, prefix: str = "", stderr: bytes = b"", data: bytes = b"") -> None:
    """Replace a CHILD_PATH executable with a small Python wrapper around the real one (a test executable only).
    Sentinel bytes live in a side file read at run time: the coordinator hashes the wrapper's source as a bound
    executable, so no sentinel may be written into that source."""
    real = REAL[name]
    side = host.root / f"side-{name}"
    side.write_bytes(stderr + b"\0" + data)
    code = ["#!/usr/bin/python3 -I", "import os, sys",
            f"if sys.argv[1:] == ['--version']:\n    os.execv({real!r}, [{real!r}, '--version'])",
            f"stderr, data = open({str(side)!r}, 'rb').read().split(b'\\0', 1)",
            "if stderr:\n    os.write(2, stderr)", prefix, f"os.execv({real!r}, [{real!r}] + sys.argv[1:])"]
    host.script(name, "\n".join(code) + "\n")


@needs_tools
class BoundaryTests(unittest.TestCase):
    """B1-B8: the coordinator reads, holds and writes no sink byte, name, target or diagnostic (contract 10.1)."""

    def audited(self, host, *argv, **kwargs):
        audit = host.root / f"audit-{secrets.token_hex(4)}"
        result = host.tool(*argv, audit=audit, **kwargs)
        return result, audit.read_bytes() if audit.exists() else b""

    def assert_absent(self, host, values, reads, *outputs):
        """Sentinels are absent from every coordinator read, output, event and receipt; the fixture's paths are
        absent from outputs, events and receipts (the coordinator's reads include its trusted configuration)."""
        artifacts = [path.read_bytes() for path in (host.state / "native-agent-stack").rglob("*") if path.is_file()]
        artifacts += [host.path.joinpath("events.jsonl").read_bytes()] if host.path.exists() else []
        for value in values:
            for blob in [reads, *outputs, *artifacts]:
                self.assertFalse(forms_in(blob, value), "B1-sentinel-absent")
        for blob in [*outputs, *artifacts]:
            self.assertFalse(str(host.root).encode() in blob, "B8-home-absent")

    def test_b1_sentinels_in_every_channel_never_reach_the_coordinator(self):
        host = Host(self)
        claude = host.home / ".claude"
        s = {kind: sentinel(prefix) for kind, prefix in (("header", "ghp_"), ("name", "AKIA"), ("target", "xoxb-"),
                                                          ("decoded", "sk-proj-"), ("journal", "glpat-"),
                                                          ("git", "hf_"), ("sqlite", "sk-ant-"), ("keep", "npm_"))}
        host.prepare("--transcripts", "confirmed")
        canary = host.canary("fresh-claude-session")
        (claude / "notes.txt").write_bytes(s["header"][:24].encode() + b" " + canary.encode() + b"\n")
        name_form = next(form for form in cp.forms(canary) if "/" not in form)
        (claude / f"{s['name']}-{name_form}").write_bytes(b"")
        os.symlink(f"/nonexistent/{s['target']}/{canary}", claude / "dangling")
        import gzip
        (claude / "log.gz").write_bytes(gzip.compress(f"{s['decoded']} {canary}\n".encode()))
        store = git_repo(claude / "plugins" / "p", {"secret.txt": f"{s['git']} {canary}\n".encode()})
        next(store.glob("objects/pack/*.pack")).with_suffix(".keep").write_text(s["keep"] + "\n")
        sqlite_file(claude / "state", [(f"CREATE TABLE t(v TEXT DEFAULT '{s['sqlite']}')", ()),
                                       ("INSERT INTO t VALUES (?)", (canary,))])
        host.journal_add(f"{s['journal']} {canary}".encode())
        result, audit = self.audited(host, "scan", "--run", host.run_id, "--phase", "baseline")
        self.assertEqual(result.returncode, 5, result.stderr)
        verdict, audit2 = self.audited(host, "verdict", "--run", host.run_id)
        self.assert_absent(host, s.values(), audit + audit2, result.stdout, result.stderr, verdict.stdout)
        # The observer: each planted channel was consumed, shown by the canary beside its sentinel (booleans only).
        seen = {(event["sink"], event["mode"], event["view"]) for event in hits(host)}
        for channel in ((1, 1), (6, 6), (2, 3), (4, 5), (5, 5)):
            self.assertTrue(any((mode, view) == channel for _sink, mode, view in seen), f"B1-observer {channel}")
        self.assertIn(("A11", 3, 1), seen, "B1-observer journal")

    def test_b1_stderr_sentinels_make_checks_incomplete_and_stay_scan_side(self):
        host = Host(self)
        values = [sentinel("ghs_"), sentinel("pypi-")]
        (host.home / ".claude" / "a.txt").write_text("plain\n")
        import gzip
        (host.home / ".claude" / "b.gz").write_bytes(gzip.compress(b"plain\n"))
        wrapper(host, "rg", stderr=values[0].encode() + b"\n")
        wrapper(host, "gzip", stderr=values[1].encode() + b"\n")
        host.prepare()
        result, audit = self.audited(host, "scan", "--run", host.run_id, "--phase", "baseline")
        self.assertEqual(result.returncode, 3, result.stdout)
        reasons = sink_reasons(host)
        self.assertIn("scanner_stderr", reasons, "B1-stderr-consumed")
        self.assertIn("producer_stderr", reasons, "B1-stderr-consumed decoder")
        self.assert_absent(host, values, audit, result.stdout, result.stderr)

    def test_b2_error_texts_are_fixed_codes_and_an_unsafe_parent_fails_the_audit(self):
        host = Host(self)
        claude = host.home / ".claude"
        values = [sentinel("dir-"), sentinel("db-"), sentinel("git-"), sentinel("rec-")]
        locked = claude / f"locked-{values[0]}"
        locked.mkdir()
        (locked / "f").write_text("x")
        (claude / f"corrupt-{values[1]}").write_bytes(b"SQLite format 3\x00" + b"\xff" * 200)
        git_repo(claude / "plugins" / "q", {"a.txt": b"a\n"})
        locked.chmod(0)
        wrapper(host, "rg", prefix="sys.stdout.buffer.write(b'<stdin>\\x00' + data + b'\\n'); sys.stdout.flush()",
                data=values[3].encode())
        wrapper(host, "git", stderr=values[2].encode() + b"\n")
        host.prepare()
        result, audit = self.audited(host, "scan", "--run", host.run_id, "--phase", "baseline")
        self.assertEqual(result.returncode, 3)
        reasons = sink_reasons(host)
        for reason in ("walk_error", "unparseable_output", "producer_stderr"):
            self.assertIn(reason, reasons, "B2-fixed-code")
        self.assert_absent(host, values, audit, result.stdout, result.stderr)
        locked.chmod(0o700)
        plain = claude / f"header-{values[0]}.txt"
        plain.write_text(values[1] + "\n")
        wrapper(host, "rg")
        wrapper(host, "git")
        host.prepare()
        _result, unsafe = self.audited(host, "scan", "--run", host.run_id, "--phase", "baseline",
                                       unsafe=str(claude))
        self.assertTrue(forms_in(unsafe, values[1]) and forms_in(unsafe, values[0]), "B2-unsafe-parent-detected")

    def test_b3_descriptor_ownership_in_prepare_and_scan(self):
        host = Host(self)
        (host.home / ".claude" / "a.txt").write_text("plain\n")
        record, stdio, pipes, launches = (host.root / name for name in ("rg-fds", "stdio", "pipes", "launches"))
        host.script("rg", "#!/usr/bin/python3 -I\nimport os, sys\nfds = []\nfor x in os.listdir('/proc/self/fd'):\n"
                          "    try:\n        fds.append((int(x), os.readlink('/proc/self/fd/' + x)))\n"
                          "    except OSError:\n        pass\n"
                          f"open({str(record)!r}, 'a').write(repr(sorted(fds)) + '\\n')\n"
                          f"os.execv({REAL['rg']!r}, [{REAL['rg']!r}] + sys.argv[1:])\n")
        host.worker["stdio"] = str(stdio)
        launch = {"before_launch": {"do": "record", "path": str(launches), "label": "launch"}}
        self.assertEqual(host.tool("prepare", hooks=launch, count_pipes=pipes).returncode, 0, "B3-prepare")
        host.run_id = sorted(os.listdir(host.run_dir / "native-agent-stack" / "canary-proof"))[-1]
        self.assertEqual(host.scan("baseline", hooks=launch, count_pipes=pipes).returncode, 0)
        rows = [eval(line) for line in record.read_text().splitlines()]  # noqa: S307 - the test's own record file
        self.assertGreater(len(rows), 3, "B3-recorded")
        for fds in rows:  # rg sees stdin, stdout and stderr only: no protocol, plan or acknowledgement descriptor
            self.assertEqual([fd for fd, _target in fds if fd > 2], [], "B3-upstream-no-protocol-fd")
        self.assertEqual(set(stdio.read_text().splitlines()), {"/dev/null /dev/null"}, "B3-worker-stdio")
        # Per contained launch: the plan, protocol and acknowledgement pipes, plus the exec-error pipe that CPython's
        # subprocess opens and closes inside Popen (Lib/subprocess.py _execute_child). No stream pipe ever.
        count = len(launches.read_text().splitlines())
        self.assertEqual(len(pipes.read_text().splitlines()), 4 * count, "B3-coordinator-three-pipes")

    def test_b4_every_kind_field_and_order_rule(self):
        root, nonce = os.urandom(16), os.urandom(16)
        session = cp.Session(None, {"subpass": 0, "controls": None}, "A1", 5, "r", [(2, 1)], {"aa" * 16}, [root])
        session.nonce, session.seal = nonce, os.urandom(16)

        def record(kind, **fields):
            return wire.unpack(wire.pack(kind=kind, nonce=nonce, seq=session.seq + 1, **fields))
        good = [record(wire.BEGIN, seal=session.seal)]
        self.assertTrue(session.accept(good[0]), "B4-begin")
        self.assertTrue(session.accept(record(wire.BEGIN, seal=session.seal, object=root)), "B4-begin-root")
        self.assertTrue(session.accept(record(wire.INVENTORY, check=1, sink=1, mode=1, view=1, expected=1,
                                              object=os.urandom(16))), "B4-inventory")
        bad = {"reserved": dict(kind=wire.OBSERVATION, check=1, sink=1, klass=2, consumer=2, attempt=1, observed=1,
                                r1=b"\x01" + bytes(6)),
               "unused-field": dict(kind=wire.CONTROL, check=1, sink=1, klass=5, observed=1, expected=1,
                                    object=bytes.fromhex("aa" * 16), aux=3),
               "unknown-consumer": dict(kind=wire.HIT, check=1, sink=1, klass=1, consumer=9, attempt=1, observed=1),
               "unbound-attempt": dict(kind=wire.HIT, check=1, sink=1, klass=1, consumer=2, attempt=7, observed=1),
               "undeclared-check": dict(kind=wire.RESULT, check=9, sink=1, status=1),
               "unknown-reason": dict(kind=wire.RESULT, check=1, sink=1, status=1, reason=99),
               "unknown-control": dict(kind=wire.CONTROL, check=1, sink=1, klass=5, observed=1, expected=1,
                                       object=os.urandom(16)),
               "wrong-sink": dict(kind=wire.RESULT, check=1, sink=4, status=1),
               "unknown-kind": dict(kind=12), "path-class": dict(kind=wire.RESULT, check=1, sink=1, path=40)}
        for name, fields in bad.items():
            with self.subTest(name=name):
                trial = copy.copy(session)
                trial.checks, trial.completed = dict(session.checks), dict(session.completed)
                self.assertFalse(trial.accept(wire.unpack(wire.pack(nonce=nonce, seq=session.seq + 1, **fields))),
                                 f"B4-reject {name}")
        for name, candidate in (("replayed-nonce", wire.pack(kind=wire.END, nonce=os.urandom(16), seq=session.seq + 1)),
                                ("reordered", wire.pack(kind=wire.END, nonce=nonce, seq=session.seq + 2)),
                                ("wrong-seal", wire.pack(kind=wire.BEGIN, nonce=nonce, seq=session.seq + 1,
                                                         seal=os.urandom(16)))):
            with self.subTest(name=name):
                trial = copy.copy(session)
                self.assertFalse(trial.accept(wire.unpack(candidate)), f"B4-reject {name}")
        self.assertTrue(session.accept(record(wire.RESULT, check=1, sink=1, status=1, observed=1, expected=1)))
        self.assertFalse(copy.copy(session).accept(record(wire.RESULT, check=1, sink=1, status=1)), "B4-duplicate")
        outcome = session.outcome()
        self.assertEqual(outcome["status"], "incomplete", "B4-missing-end")
        self.assertIn("protocol_error", outcome["reasons"], "B4-missing-end")
        reader, writer = os.pipe()
        os.write(writer, wire.pack(kind=wire.END, nonce=nonce, seq=session.seq + 1)[:100])
        os.close(writer)
        partial = cp.Session(None, {"subpass": 0}, "A1", 5)
        partial.nonce = nonce
        partial.read_records(reader, -1)
        os.close(reader)
        self.assertIn("protocol_error", partial.reasons, "B4-partial-frame")

    def test_b5_a_hit_is_sticky_through_kill_rotation_and_a_zero_rescan(self):
        host = Host(self)
        host.prepare()
        leak = host.home / ".claude" / "leak.txt"
        leak.write_text(host.canary("subagent") + "\n")
        result = host.scan("baseline", worker={"hooks": {"after_durable_hit": {"do": "kill"}}})
        self.assertEqual(result.returncode, 5, "B5-sticky exit")
        leak.unlink()
        self.assertEqual(host.scan("baseline").returncode, 5, "B5-sticky rescan")
        self.assertEqual(host.finished()["status"], "complete")
        self.assertEqual(host.verdict()[1], "leak", "B5-sticky verdict")

    def test_b5_a_hit_survives_malformed_output_exit_stderr_cap_and_timeout(self):
        emit = ("pattern = open(sys.argv[sys.argv.index('--file') + 1], 'rb').read().split(b'\\n')[0]\n"
                "sys.stdout.buffer.write(b'<stdin>\\x00' + pattern + b'\\n'); sys.stdout.flush()\n")
        tails = {"malformed": "sys.stdout.buffer.write(b'garbage\\n'); sys.exit(0)",
                 "exit2": "sys.exit(2)", "stderr": "os.write(2, b'x'); sys.exit(0)",
                 "cap": "sys.stdout.buffer.write(b'x' * 5000); sys.exit(0)", "timeout": "import time; time.sleep(60)"}
        for name, tail in tails.items():
            with self.subTest(name=name):
                host = Host(self)
                (host.home / ".claude" / "a.txt").write_text("plain\n")
                wrapper(host, "rg", prefix=emit + tail)
                host.prepare()
                worker = {"constants": {"BUDGET_CAP": 3.0, "STDOUT_CAP": 4096}}
                result = host.scan("baseline", worker=worker)
                self.assertEqual(result.returncode, 5, f"B5-sticky {name}")
                self.assertTrue(hits(host), f"B5-sticky {name}")
                self.assertEqual(host.finished()["status"], "incomplete", f"B5-incomplete {name}")

    def test_b6_bound_executables_only(self):
        host = Host(self)
        host.prepare()
        marker = host.root / "evil-ran"
        evil = host.root / "evil"
        evil.mkdir()
        (evil / "rg").write_text(f"#!/bin/sh\ntouch {marker}\nexec /usr/bin/rg \"$@\"\n")
        (evil / "rg").chmod(0o755)
        result = host.scan("baseline", env=host.env(PATH=f"{evil}:/usr/bin:/bin"))
        self.assertEqual(result.returncode, 0, "B6-path")
        self.assertFalse(marker.exists(), "B6-path not used")
        host.script("rg", f"#!/bin/sh\ntouch {marker}\nexec {REAL['rg']} \"$@\"\n")
        result = host.scan("baseline")
        self.assertEqual(result.returncode, 3, "B6-tool_changed")
        self.assertIn("tool_changed", host.finished()["reasons"], "B6-tool_changed")
        self.assertFalse(marker.exists(), "B6-changed not used")

    def test_b7_union_integrity(self):
        cases = {"dropped-form": {"hooks": {"before_plan": {"do": "union", "edit": "drop"}}},
                 "blank-line": {"hooks": {"before_plan": {"do": "union", "edit": "blank"}}},
                 "altered-form": {"hooks": {"before_plan": {"do": "union", "edit": "alter"}}},
                 "after-plan": {"worker": {"hooks": {"after_prewalk": {"do": "union"}}}},
                 "before-child": {"worker": {"hooks": {"before_child": {"do": "union", "when": "rg"}}}}}
        for name, spec in cases.items():
            with self.subTest(name=name):
                host = Host(self)
                (host.home / ".claude" / "a.txt").write_text("plain\n")
                host.prepare()
                result = host.scan("baseline", **spec)
                self.assertEqual(result.returncode, 3, f"B7-{name}")
                self.assertTrue({"union_changed", "pattern_file_mismatch"} & set(host.finished()["reasons"]),
                                f"B7-{name}")

    def test_b7_every_form_of_every_attempt_is_detected_and_attributed(self):
        host = Host(self)
        host.prepare("--transcripts", "confirmed")
        self.assertEqual(host.scan("baseline").returncode, 0)
        host.arm("codex-exec")
        host.disarm()
        host.arm("codex-exec")
        host.disarm()
        planted = {}
        for consumer, attempt in [(c, 1) for c in cp.CONSUMERS] + [("codex-exec", 2)]:
            for number, form in enumerate(cp.forms(host.canary(consumer, attempt))):
                path = host.home / ".claude" / "forms" / f"{consumer}-{attempt}-{number}.txt"
                path.parent.mkdir(exist_ok=True)
                path.write_text(f"x {form} y\n")
                planted[path.name] = (consumer, attempt)
        result = host.scan("final")
        self.assertEqual(result.returncode, 5)
        found = {(event["consumer"], event["attempt"]) for event in hits(host) if event["mode"] == 1}
        self.assertEqual(found, set(planted.values()), "B7-attribution")
        self.assertGreaterEqual(len([e for e in hits(host) if e["mode"] == 1]), len(planted), "B7-every-form")

    def test_b8_publication_refuses_a_synthetic_value_in_a_trusted_field(self):
        host, _lane = clean_run(self)
        launcher = COORDINATOR.replace("try:\n    code = cp.main", "cp.claim = (lambda original: lambda run, result: "
                                       "original(run, result) + ' ' + cp.canary_of(run, 'subagent', 1))(cp.claim)\n"
                                       "try:\n    code = cp.main")
        config = {"root": str(ROOT), "argv": ["verdict", "--run", host.run_id], "constants": dict(
            host.constants, WORKER_COMMAND=[str(host.bin / "python3")]), "hooks": {}, "audit": None}
        result = subprocess.run([sys.executable, "-I", "-S", "-c", launcher, json.dumps(config)], env=host.env(),
                                capture_output=True, timeout=120)
        self.assertEqual(result.returncode, 1, "B8-refused")
        self.assertIn(b"synthetic_value_in_output", result.stderr, "B8-refused")
        self.assertFalse(list((host.state / "native-agent-stack" / "canary-proof").glob("*.json")), "B8-no-receipt")


class Shared:
    """One clean run per class (its record is the classifier table's base); cleaned up with the class."""

    @classmethod
    def setUpClass(cls):
        cls.case = unittest.TestCase()
        cls.host, cls.lane = clean_run(cls.case)
        cls.events = cls.host.events()
        cls.masking = {attempt: cp.masked_markers(cls.host.canary("systemd-user-unit", attempt)) for attempt in (1,)}

    @classmethod
    def tearDownClass(cls):
        cls.case.doCleanups()


def mutate(events: list, *changes) -> list:
    events = copy.deepcopy(events)
    for change in changes:
        events = change(events) or events
    return events


def latest(events, kind, **match):
    return [e for e in events if e["event"] == kind and all(e.get(k) == v for k, v in match.items())][-1]


@needs_tools
class RequestTests(Shared, unittest.TestCase):
    """R1-R8: the latest request decides; incomplete, unfinished, stale or early is never clean."""

    def codes(self, events, settle: int = 0):
        from unittest import mock
        with mock.patch.object(cp, "SETTLE_SECONDS", settle):  # the launcher's patched settle (contract 13.7)
            return cp.classify(events, masking=self.masking)

    def test_r3_the_clean_record_and_every_classifier_code(self):
        self.assertEqual(self.codes(self.events)["verdict"], "clean", "R3-clean-base")
        final_seq = latest(self.events, "scan_requested", phase="final")["request"]
        base_seq = latest(self.events, "scan_requested", phase="baseline")["request"]

        def drop(kind, request):
            return lambda ev: [e for e in ev if not (e["event"] == kind and e.get("request") == request)]

        def edit(kind, request, **fields):
            def change(ev):
                for e in ev:
                    if e["event"] == kind and e.get("request") == request:
                        e.update(fields)
            return change

        def sinks(request, function):
            def change(ev):
                for e in ev:
                    if e["event"] == "scan_finished" and e["request"] == request:
                        function(e["sinks"])
            return change

        def arm_edit(kind, consumer, **fields):
            def change(ev):
                latest(ev, kind, consumer=consumer).update(fields)
            return change

        table = {
            "no_baseline": [lambda ev: [e for e in ev if e.get("request") != base_seq]],
            "baseline_unfinished": [drop("scan_finished", base_seq)],
            "baseline_incomplete": [edit("scan_finished", base_seq, status="incomplete")],
            "baseline_after_arm": [edit("scan_requested", base_seq, seq=10**6)],
            "no_final": [lambda ev: [e for e in ev if e.get("request") != final_seq]],
            "final_unfinished": [drop("scan_planned", final_seq)],
            "final_incomplete": [edit("scan_finished", final_seq, status="incomplete")],
            "final_stale": [lambda ev: ev.append(dict(latest(ev, "disarmed", consumer="subagent"), seq=10**7))],
            "final_too_early": [edit("scan_requested", final_seq, boottime_ns=latest(
                self.events, "disarmed", consumer="omniroute-lane")["boottime_ns"] + 1)],
            "sink_not_scanned:A4": [sinks(final_seq, lambda s: s.pop("A4"))],
            "sink_incomplete:A1:deadline": [sinks(final_seq, lambda s: s["A1"].update(status="incomplete",
                                                                                         reasons=["deadline"]))],
            "control_missing:A3": [sinks(final_seq, lambda s: s["A3"].update(status="incomplete",
                                                                            reasons=["control_missing"]))],
            "recording_missing:subagent": [sinks(final_seq, lambda s: s["A1"].update(observations=[
                row for row in s["A1"]["observations"] if not (row[0] == 2 and row[1] == 3)]))],
            "recording_missing:codex-exec": [sinks(final_seq, lambda s: s["A4"].update(observations=[
                row for row in s["A4"]["observations"] if not (row[0] == 2 and row[1] == 5)]))],
            "masking_markers_mismatch": [sinks(final_seq, lambda s: s["A11"]["observations"].append(
                [3, 0, 0, 9, "00" * 16, 1]))],
            "not_disarmed:subagent": [lambda ev: [e for e in ev if not (e["event"] == "disarmed"
                                                                         and e["consumer"] == "subagent")]],
            "store_armed": [lambda ev: [e for e in ev if not (e["event"] == "disarmed"
                                                              and e["consumer"] == "omniroute-lane")]],
            "disarm_unverified:codex-exec": [arm_edit("disarmed", "codex-exec", absent_verified=False)],
            "guard_not_pinned_at_arm:subagent": [arm_edit("armed", "subagent", guard_pinned=False)],
            "not_armed:workflow-child": [lambda ev: [e for e in ev if e.get("consumer") != "workflow-child"]],
            "arming_unresolved": [lambda ev: ev.append(dict(latest(ev, "arming", consumer="subagent"), seq=10**8))],
            "user_run_unfinished": [lambda ev: ev.append(dict(latest(ev, "scan_requested", phase="final"),
                                                               group="user", request="u1", seq=10**6))],
            "comparison_unfinished": [lambda ev: ev.append(dict(latest(ev, "scan_requested", phase="final"),
                                                                 phase="comparison", group="user", request="c1",
                                                                 seq=10**6))],
            "clock_stepped": [lambda ev: ev.append(dict(ev[-1], event="clock_stepped", seq=10**6))],
            "tool_changed": [lambda ev: ev.append({**{k: ev[-1][k] for k in cp.COMMON}, "event": "integrity_failed",
                                                   "code": "tool_changed", "seq": 10**6})],
        }
        for code, changes in table.items():
            with self.subTest(code=code):
                result = self.codes(mutate(self.events, *changes), settle=1 if code == "final_too_early" else 0)
                self.assertIn(code, result["codes"], f"R3-code {code}")
                self.assertEqual(result["verdict"], "incomplete", f"R3-verdict {code}")
        leaky = mutate(self.events, *table["final_incomplete"], lambda ev: ev.append(dict(
            latest(ev, "scan_requested"), event="hit", seq=10**6)))
        self.assertEqual(cp.classify([dict(e, **({"sink": "A1", "subpass": 0, "root": "", "object": "", "check": 1,
                                                  "mode": 1, "view": 1, "path": 13, "consumer": "subagent",
                                                  "attempt": 1, "count": 1} if e["event"] == "hit" else {}))
                                      for e in leaky])["verdict"], "leak", "R3-precedence leak")
        truncated = copy.deepcopy(self.events)
        truncated[3]["unknown_field"] = 1
        self.assertFalse(cp.validate(truncated, self.host.run_id), "R8-invalid unknown field")
        gap = copy.deepcopy(self.events)
        del gap[4]
        self.assertFalse(cp.validate(gap, self.host.run_id), "R8-invalid gap")
        impossible = copy.deepcopy(self.events)
        first_armed = next(i for i, e in enumerate(impossible) if e["event"] == "armed")
        del impossible[first_armed]
        for number, event in enumerate(impossible, 1):
            event["seq"] = number
        self.assertFalse(cp.validate(impossible, self.host.run_id), "R8-invalid transition")

    def test_r1_a_kill_before_the_plan_supersedes_the_passing_final(self):
        for point in ("after_request", "before_mkdir", "before_union", "before_plan"):
            with self.subTest(point=point):
                result = self.host.scan("final", hooks={point: {"do": "kill"}})
                self.assertEqual(result.returncode, -9)
                code, verdict, codes = self.host.verdict()
                self.assertNotEqual(verdict, "clean", f"R1-{point}")
                self.assertIn("final_unfinished", codes, f"R1-{point}")
        self.assertEqual(self.host.scan("final").returncode, 0)
        self.assertEqual(self.host.verdict()[1], "clean", "R1-recovered by a new request")

    def test_r2_a_setup_failure_leaves_no_earlier_pass_current(self):
        order = self.host.root / "order"
        for point in ("before_mkdir", "before_union", "before_controls", "before_exec_check", "before_launch",
                      "before_plan"):
            with self.subTest(point=point):
                result = self.host.scan("final", hooks={
                    "after_request": {"do": "record", "path": str(order), "label": "request"},
                    point: {"do": "fail"}})
                self.assertEqual(result.returncode, 3, f"R2-{point}")
                self.assertEqual(self.host.finished()["status"], "incomplete", f"R2-{point}")
                self.assertIn(self.host.verdict()[2][0] if self.host.verdict()[2] else "",
                              ("final_incomplete", "final_unfinished"), f"R2-{point}")
        self.assertEqual(order.read_text().splitlines()[0], "request", "R2-order")
        self.assertEqual(self.host.scan("final").returncode, 0)


@needs_tools
class RequestRunTests(unittest.TestCase):
    """R4-R8 on their own runs."""

    def test_r4_rearm_unbaselined_home_attempt_binding_and_settle(self):
        host, lane = clean_run(self)
        self.assertEqual(host.verdict()[1], "clean")
        attempt = host.arm("subagent")
        self.assertEqual(attempt, 2, "R4-new-attempt")
        host.consume("subagent", attempt)
        host.disarm()
        code, verdict, codes = host.verdict()
        self.assertIn("final_stale", codes, "R4-stale")
        self.assertEqual(host.scan("final").returncode, 0)
        self.assertIn("recording_missing:subagent", host.verdict()[2], "R4-attempt-1-tag-insufficient")
        other = host.root / "unregistered"
        other.mkdir()
        refused = host.tool("arm", "--run", host.run_id, "omniroute-lane", "--codex-home", str(other))
        self.assertEqual(refused.returncode, 1, "R4-unbaselined-home")
        self.assertIn(b"baseline_scope_missing", refused.stderr, "R4-unbaselined-home")
        host.constants["SETTLE_SECONDS"] = 1200
        self.assertEqual(host.scan("final").returncode, 0)
        self.assertIn("final_too_early", host.verdict()[2], "R4-settle")

    def test_r6_absent_vanished_and_declined_roots(self):
        host = Host(self, session=SESSION)
        (host.home / ".cache" / "claude-cli-nodejs").mkdir()
        (host.home / ".cache" / "claude-cli-nodejs" / "a.log").write_text("x\n")
        host.prepare()
        self.assertEqual(host.scan("baseline").returncode, 0)
        rows = host.finished()["sinks"]
        self.assertTrue(rows["A9"]["absent_only"], "R6-absent")
        self.assertEqual(rows["A12"]["status"], "complete", "R6-absent-store")
        shutil.rmtree(host.home / ".cache" / "claude-cli-nodejs")
        self.assertEqual(host.scan("baseline").returncode, 3)
        self.assertIn("vanished", host.finished()["sinks"]["A3"]["reasons"], "R6-vanished")
        (host.home / ".cache" / "claude-cli-nodejs").mkdir()
        for policy in ("exclude", "confirmed"):  # C5: exactly ~/.claude/projects/** and each home's sessions/**
            host.prepare("--transcripts", policy)
            (host.home / ".claude" / "projects" / "p").mkdir(parents=True, exist_ok=True)
            (host.home / ".claude" / "projects" / "p" / "s.jsonl").write_text(host.canary("subagent") + "\n")
            (host.codex / "sessions").mkdir(exist_ok=True)
            (host.codex / "sessions" / "rollout-x.jsonl").write_text(host.canary("codex-exec") + "\n")
            result = host.scan("baseline")
            if policy == "exclude":
                self.assertEqual(result.returncode, 0, "R6-declined not read")
                self.assertEqual(host.finished()["sinks"]["A1"]["counters"]["declined"], 1, "R6-declined A1")
                self.assertEqual(host.finished()["sinks"]["A4"]["counters"]["declined"], 1, "R6-declined A4")
            else:
                self.assertEqual(result.returncode, 5, "R6-confirmed read")
                self.assertEqual({e["sink"] for e in hits(host)}, {"A1", "A4"}, "R6-confirmed read")

    def test_r7_recording_classes_and_markers(self):
        cases = {"fresh-claude-session": ".claude/projects/p/{own}.jsonl",
                 "subagent": ".claude/projects/p/other-session.jsonl",
                 "workflow-child": ".claude/projects/p/other-session/subagents/w.jsonl",
                 "codex-exec": "lane:sessions/2026/rollout-a.jsonl"}
        for consumer, misplaced in cases.items():
            with self.subTest(consumer=consumer):
                host = Host(self, session=SESSION)
                lane = host.root / "lane-home"
                lane.mkdir()
                host.prepare("--codex-home", str(lane), "--transcripts", "confirmed")
                self.assertEqual(host.scan("baseline").returncode, 0)
                for each in cp.CONSUMERS:
                    attempt = host.arm(each, *(["--codex-home", str(lane)] if each == "omniroute-lane" else []))
                    out, err = host.consume(each, attempt)
                    if each == "systemd-user-unit":
                        host.journal_add(*[line for line in (out + err).split(b"\n") if line])
                    elif each == consumer:
                        target = (lane / misplaced[5:]) if misplaced.startswith("lane:") else \
                            host.home / misplaced.format(own=SESSION)
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_text(out.decode())
                    else:
                        host.record(each, out.decode().strip(), lane)
                    host.disarm()
                self.assertEqual(host.scan("final").returncode, 0)
                self.assertIn(f"recording_missing:{consumer}", host.verdict()[2], f"R7-class {consumer}")

    def test_r7_marker_count_and_partial_marker(self):
        for change in ("drop", "partial"):
            with self.subTest(change=change):
                host = Host(self, session=SESSION)
                lane = host.root / "lane-home"
                lane.mkdir()
                host.prepare("--codex-home", str(lane), "--transcripts", "confirmed")
                self.assertEqual(host.scan("baseline").returncode, 0)
                host.full_cycle(lane)
                entries = json.loads(host.journal.read_text())
                marked = [e for e in entries if dict(e)["MESSAGE"].startswith("hex:")
                          and b"[REDACTED:" in bytes.fromhex(dict(e)["MESSAGE"][4:])]
                if change == "drop":
                    entries.remove(marked[0])
                else:
                    host.journal_add(b"x [REDACTED-PARTIAL:CANARY_E2E_KEY]")
                    entries = json.loads(host.journal.read_text())
                host.journal.write_text(json.dumps(entries))
                self.assertEqual(host.scan("final").returncode, 0)
                self.assertIn("masking_markers_mismatch", host.verdict()[2], f"R7-markers {change}")

    def test_r7_unknown_session_fallback_and_user_arrival(self):
        host, lane = clean_run(self, session=None)
        self.assertEqual(host.verdict()[1], "clean", "R7-unknown-session workflow any session")
        (host.home / ".agentsview").mkdir()
        result = host.scan("final", "--user-run", tty=True)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("user_arrival_missing:agentsview", host.verdict()[2], "R7-agentsview")
        sqlite_file(host.home / ".agentsview" / "sessions.db", [("CREATE TABLE m(v)", ()), (
            "INSERT INTO m VALUES (?)", (cp.tag_line(host.canary(), host.run_id, "fresh-claude-session", 1),))])
        self.assertEqual(host.scan("final", "--user-run", tty=True).returncode, 0)
        self.assertEqual(host.verdict()[1], "clean", "R7-agentsview arrival")
        del lane

    def test_r5_r8_sticky_user_and_comparison_results(self):
        host, _lane = clean_run(self)
        (host.home / ".config" / "systemd" / "user").mkdir(parents=True)
        result = host.scan("comparison", "--user-run", tty=True, worker={"hooks": {"after_prewalk": {"do": "kill"}}})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("comparison_incomplete", host.verdict()[2], "R8-comparison-required")
        self.assertEqual(host.scan("comparison", "--user-run", tty=True).returncode, 0)
        self.assertEqual(host.verdict()[1], "clean", "R8-comparison-complete")
        (host.home / ".config" / "systemd" / "user" / "x.conf").write_text(host.canary("codex-exec") + "\n")
        self.assertEqual(host.scan("final", "--user-run", tty=True).returncode, 5, "R5-user-hit")
        (host.home / ".config" / "systemd" / "user" / "x.conf").unlink()
        self.assertEqual(host.scan("final", "--user-run", tty=True).returncode, 5, "R5-sticky-user")
        self.assertEqual(host.verdict()[1], "leak", "R5-sticky-user")
        self.assertEqual(host.tool("scan", "--run", host.run_id, "--phase", "comparison").returncode, 1,
                         "R8-comparison-needs-user-run")


if __name__ == "__main__":
    unittest.main()
