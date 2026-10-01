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
# The fixture CHILD_PATH holds the reviewed executables plus what the unchanged ecosystem-bounded-run resolves through
# PATH (its `#!/usr/bin/env bash` line, `id -u` and `stat -c %u`): production's CHILD_PATH has them all.
REAL = {name: shutil.which(name, path="/usr/bin:/bin") for name in (
    "rg", "git", "gzip", "bzip2", "xz", "setpriv", "nice", "ionice", "sh", "cat", "sleep", "bash", "id", "stat")}


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


# A foreign /tmp/.git exists on some shared hosts. This test-only metadata seam
# checks every owned ancestor, while leaving unrelated ancestors untouched. It
# preserves the real helper's refusal for a .git inside the fixture. No production
# environment bypass or runner change is introduced (contract 9.5).
STORE_METADATA_SEAM = r"""
import credential_status as cs
from pathlib import Path
def fixture_worktree(directory):
    current = Path(os.path.realpath(directory))
    boundary = Path(os.environ["HOME"]).parent
    while current == boundary or boundary in current.parents:
        if os.path.lexists(current / ".git"):
            return current
        current = current.parent
    return None
cs.git_worktree_of = fixture_worktree
"""


COORDINATOR = r"""
import json, os, signal, sys, time
config = json.loads(sys.argv[1])
sys.path[:0] = [config["root"] + "/tools/credentials", config["root"] + "/scripts"]
import canary_proof as cp
for name, value in config["constants"].items():
    setattr(cp, name, tuple(value) if isinstance(value, list) and name.endswith("SINKS") else value)
audit = []
protocol_audit = []
original_accept = cp.Session.accept
def accept(self, record):
    protocol_audit.append(record)
    return original_accept(self, record)
cp.Session.accept = accept
def act(spec):
    def run(*args):
        if spec.get("when") and (not args or spec["when"].encode() not in bytes(args[0], "utf-8") if isinstance(args[0] if args else b"", str) else spec["when"].encode() not in (args[0] if args else b"")):
            return
        kind = spec["do"]
        if kind == "kill":
            os.kill(os.getpid(), signal.SIGKILL)
        if kind == "fail":
            raise OSError("injected")
        if kind == "exception":
            raise RuntimeError("synthetic exception")
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
        if kind == "stdout-size":  # how many bytes the command had printed when this hook ran (C11)
            with open(spec["path"], "a") as handle:
                handle.write(str(os.fstat(1).st_size) + "\n")
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
            where = os.readlink(f"/proc/self/fd/{path}") if isinstance(path, int) else os.path.realpath(path)
            if where == forbidden:  # by name or by an open directory descriptor
                raise PermissionError("store listed")
            return function(path, *a, **k)
        return inner
    os.scandir, os.listdir = guarded(real_scandir), guarded(real_listdir2)
if config.get("core_pattern"):  # a synthetic core_pattern file for the runner's crash-collector check (C8)
    cp.runner.CORE_PATTERN_FILE = config["core_pattern"]
if config.get("fail_fsync"):  # the run record cannot be made durable: admission must fail closed (contract 5)
    def failing_fsync(fd):
        raise OSError(5, "synthetic EIO")
    os.fsync = failing_fsync
if config.get("taint_negative"):
    original_build = cp.Request.build
    def build(self):
        spec = original_build(self)
        if config["taint_negative"] == "m2":
            for path, fmt, ident, view, expected in spec["m2"]:
                if fmt == "gzip" and view == "negative":
                    with open(path, "wb") as out:
                        out.write(cp.gzip.compress(self.controls["plain"].encode()))
        else:
            old = spec["m6"]["negative"]
            new = old + self.controls["plain"]
            os.rename(old, new); spec["m6"]["negative"] = new
        return spec
    cp.Request.build = build
if config.get("stdout_to"):
    _out = os.open(config["stdout_to"], os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.dup2(_out, 1)
    os.close(_out)
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
            handle.write(b"\n" + repr(protocol_audit).encode())
sys.exit(code)
"""

WORKER_LAUNCHER = r"""
import json, os, sys, time
config = json.loads(sys.argv[1])
sys.path[:0] = [config["root"] + "/tools/credentials", config["root"] + "/scripts"]
import canary_scan_worker as w
if config.get("wrong_runtime"):
    os.environ["XDG_RUNTIME_DIR"] = config["wrong_runtime"]
if config.get("fail_spawn"):
    original_spawn = w.Child.__init__
    def fail_spawn(self, scan, argv, *args, **kwargs):
        if argv[0].endswith('/' + config['fail_spawn']):
            raise OSError(11, "synthetic EAGAIN")
        original_spawn(self, scan, argv, *args, **kwargs)
    w.Child.__init__ = fail_spawn
if config.get("argv_record"):
    original_child = w.Child.__init__
    def record_child(self, scan, argv, *args, **kwargs):
        with open(config["argv_record"], "ab") as handle:
            handle.write(repr(argv).encode() + b"\n")
        original_child(self, scan, argv, *args, **kwargs)
    w.Child.__init__ = record_child
if config.get("forbid_paths"):
    import builtins
    original_open, original_builtin = os.open, builtins.open
    forbidden = [os.fsencode(p) for p in config["forbid_paths"]]
    def guarded_open(path, *args, **kwargs):
        if isinstance(path, int):
            return original_builtin(path, *args, **kwargs)
        value = os.fsencode(path)
        if kwargs.get("dir_fd") is not None:
            value = os.fsencode(os.readlink('/proc/self/fd/' + str(kwargs["dir_fd"]))) + b'/' + value
        if any(value == p or value.startswith(p + b'/') for p in forbidden):
            raise AssertionError("excluded path opened")
        return original_open(path, *args, **kwargs)
    os.open = guarded_open
for name, value in config["constants"].items():
    setattr(w, name, value)
if config.get("stub_scope"):
    w.SCOPE_CHECK = lambda: None
if config.get("fs_magic") is not None:
    w.fs_magic = lambda fd: config["fs_magic"]
if config.get("drop_control"):
    original_control = w.Scan.control
    def control(self, check, ident, *args, **kwargs):
        request = os.path.basename(os.path.dirname(self.plan["patterns"]))[5:]
        if ident == w.keyed(self.key, b"control", request, config["drop_control"]):
            return
        return original_control(self, check, ident, *args, **kwargs)
    w.Scan.control = control
if config.get("drop_inband"):
    original_inband = w.Scan.inband
    def inband(self, name):
        ident, value = original_inband(self, name)
        return ident, b"missing synthetic control" if name == config["drop_inband"] else value
    w.Scan.inband = inband
if config.get("coarse_tuple"):  # simulates deferred timestamps (shared-mapping writes): identity without times
    w.tuple_of = lambda info: (info.st_dev, info.st_ino, info.st_size)
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
            fd = os.open(spec["path"], os.O_RDONLY | os.O_CLOEXEC)
            if spec.get("ready"):
                with open(spec["ready"], "w") as handle:
                    json.dump({"pid": os.getpid(), "fd": fd}, handle)
            os.read(fd, 1)
        elif kind == "sleep":
            time.sleep(spec["seconds"])
        elif kind == "fork-descendant":
            import signal
            pid = os.fork()
            if pid == 0:
                os.setsid(); signal.signal(signal.SIGTERM, signal.SIG_IGN)
                os.closerange(0, 256)
                time.sleep(300); os._exit(0)
            with open(spec["ready"], "w") as handle:
                handle.write(str(pid))
            deadline = time.monotonic() + 20
            while not os.path.exists(spec["release"]) and time.monotonic() < deadline:
                time.sleep(.02)
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
            if spec.get("mode"):
                os.chmod(spec["target"], spec["mode"])
        elif kind == "swap":  # the planned name now names another file; the original waits aside
            os.replace(spec["target"], spec["aside"]); os.replace(spec["source"], spec["target"])
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
        elif kind == "truncate-control":  # the control file stays, its control value does not
            import glob
            for path in glob.glob(config["runtime"] + "/native-agent-stack/canary-proof/*/scan-*/" + spec["glob"]):
                os.truncate(path, 0)
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
WORKER_LAUNCHER = WORKER_LAUNCHER.replace("import canary_scan_worker as w", STORE_METADATA_SEAM +
                                         "\nimport canary_scan_worker as w")

RUNNER_LAUNCHER = "import os, sys\nsys.path[:0] = [sys.argv[1] + '/tools/credentials', sys.argv[1] + '/scripts']\n" + \
    STORE_METADATA_SEAM + "\nimport credential_run as r\nsys.exit(r.main(sys.argv[2:]))\n"

FAKE_JOURNALCTL = r"""#!/usr/bin/python3 -I
import json, os, struct, sys
store = __STORE__
args = sys.argv[1:]
if args == ["--version"]:
    print("systemd 255 (255.4-synthetic)")
    sys.exit(0)
entries = json.load(open(store)) if os.path.exists(store) else []
cursor = next((a.split("=", 1)[1] for a in args if a.startswith("--cursor=")), None)
after = next((a.split("=", 1)[1] for a in args if a.startswith("--after-cursor=")), None)
ident = next((a.split("=", 1)[1] for a in args if a.startswith("SYSLOG_IDENTIFIER=")), None)
def seq(text):
    return int(dict(part.split("=", 1) for part in text.split(";"))["i"], 16)
start = 0
if cursor is not None or after is not None:
    # systemd v255 src/journal/journalctl.c:2463-2474: sd_journal_seek_cursor, then sd_journal_next_skip(j, 1 +
    # after_cursor). The seek lands on the first surviving entry when the cursor's own entry was vacuumed, so
    # --after-cursor then skips that surviving entry, and --cursor starts with it.
    later = [i for i, e in enumerate(entries) if seq(dict(e)["__CURSOR"]) >= seq(cursor or after)]
    start = (later[0] + (after is not None)) if later else len(entries)
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
        self.dumper = {"constants": {}, "hooks": {}, "stub_scope": not real_scope}
        self.constants = {"CHILD_PATH": str(self.bin), "RUNNER": str(RUNNER if real_scope else self.bin / "stub-runner"),
                          "SCOPE_REQUIRED": real_scope,
                          "PRIMARY_CHECKOUT": str(self.home / "code/native-agent-stack"),
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

    def tool(self, *argv, hooks=None, audit=None, unsafe=None, timeout=300, env=None, tty=False, worker=None,
             dumper=None, forbid_list=None, count_pipes=None, background=False, core_pattern=None,
             stdout_to=None, fail_fsync=False, taint_negative=None) -> subprocess.CompletedProcess:
        """Run canary_proof.main(argv) in a launcher process whose module hooks and constants are set here."""
        worker_config = copy.deepcopy(self.worker)
        worker_config.update(root=str(ROOT), **(worker or {}))
        dumper_config = copy.deepcopy(self.dumper)
        dumper_config.update(root=str(ROOT), **(dumper or {}))
        for child_config in (worker_config, dumper_config):
            for spec in child_config["hooks"].values():
                if spec["do"] == "block":
                    self.test.addCleanup(os.close, os.open(spec["path"], os.O_RDWR | os.O_NONBLOCK | os.O_CLOEXEC))
        constants = dict(self.constants)
        constants["WORKER_COMMAND"] = [str(self.bin / "python3"), "-I", "-S", "-c", WORKER_LAUNCHER,
                                       json.dumps(worker_config)]
        constants["DUMPER_COMMAND"] = [str(self.bin / "python3"), "-I", "-S", "-c", WORKER_LAUNCHER,
                                       json.dumps(dumper_config), "sqlite-dumper"]
        config = {"root": str(ROOT), "argv": [str(a) for a in argv], "constants": constants, "hooks": hooks or {},
                  "audit": str(audit) if audit else None, "unsafe_parent_read": unsafe,
                  "forbid_list": str(forbid_list) if forbid_list else None,
                  "count_pipes": str(count_pipes) if count_pipes else None,
                  "core_pattern": str(core_pattern) if core_pattern else None,
                  "stdout_to": str(stdout_to) if stdout_to else None, "fail_fsync": fail_fsync,
                  "taint_negative": taint_negative}
        command = [sys.executable, "-I", "-S", "-c", COORDINATOR, json.dumps(config)]
        if background:
            if tty:
                import pty
                master, slave = pty.openpty()
                self.test.addCleanup(os.close, master)
                process = subprocess.Popen(command, env=env or self.env(), stdin=slave, stdout=slave,
                                           stderr=subprocess.PIPE, start_new_session=True)
                os.close(slave)
                return process
            return subprocess.Popen(command, env=env or self.env(), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    start_new_session=True)
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
        import shlex
        result = self.tool("arm", "--run", self.run_id, consumer, *extra)
        self.test.assertEqual(result.returncode, 0, result.stderr)
        probe = re.search(rb"^probe: (.+)$", result.stdout, re.M)
        self.test.assertIsNotNone(probe, "CMD-emitted-probe")
        self.test.assertEqual(shlex.split(probe.group(1).decode())[:8],
            [PYTHON, "-I", str(ROOT / "tools/credentials/credential_run.py"), "canary-e2e", "--", PYTHON, "-I",
             str(ROOT / "tools/credentials/canary_probe.py")], "CMD-emitted-absolute-probe")
        return int(re.search(rb"--attempt (\d+)", result.stdout).group(1))

    def consume(self, consumer: str, attempt: int) -> tuple:
        """The probe through the real credential runner and the synthetic store: (masked stdout, masked stderr)."""
        command = [PYTHON, "-I", "-S", "-c", RUNNER_LAUNCHER, str(ROOT), "canary-e2e", "--", PYTHON, "-I",
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
            with open(f"/proc/{entry}/stat", "rb") as handle:
                state = handle.read().rsplit(b")", 1)[1].split()[0]
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


SESSION = "synthetic-coordinator-session"


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
        self.assertEqual(result.returncode, 0, "C4-cleanup-clean")  # cleanup's own absence fact stales nothing
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

    def test_rg_record_grammar_rejects_empty_unknown_and_unlabelled_records(self):
        """Only `known-label NUL planned-pattern LF` records count, even under a consistent stats block (10.3)."""
        stats = (b"\n1 matches\n1 matched lines\n1 files contained matches\n1 files searched\n0 bytes printed\n"
                 b"0 bytes searched\n0.0 seconds spent searching\n0.0 seconds\n")
        scan = type("Scan", (), {"patterns": type("Patterns", (), {"classes": {b"CNRYCTLplanned": []}})(),
                                 "plan": {"rg_version": 14001000}, "attribute": lambda *args: None})()
        for name, line in (("empty", b"<stdin>\0"), ("unknown", b"<stdin>\0CNRYCTLunplanned"),
                           ("label", b"elsewhere\0CNRYCTLplanned"), ("planned", b"<stdin>\0CNRYCTLplanned")):
            check = wire.Check(1, "M1", "raw", "other", bytes(16), 0)
            parser = wire.RgOutput(scan, check, {b"<stdin>": None})
            parser.feed(line + b"\n" + stats)
            parser.close(1)
            self.assertEqual(check.reason, "ok" if name == "planned" else "unparseable_output", "M1-grammar " + name)

    def test_scanner_settle_fails_exit_2_and_a_deadline_itself(self):
        """The worker's own rule, independent of the coordinator's refusal to trust a complete RESULT with a bad exit:
        only exit 0 or 1 settles a scanner check; exit 2 is scanner_exit and a missed deadline is deadline (10.3)."""
        for code, reason in ((0, "ok"), (1, "ok"), (2, "scanner_exit"), (None, "deadline")):
            check = wire.Check(1, "M1", "raw", "other", bytes(16), 0)
            child = type("Child", (), {"finish": lambda self, deadline, code=code: code})()
            parser = type("Parser", (), {"close": lambda self, files: None})()
            wire.Scan.settle(None, check, child, parser, 0.0, 1)
            self.assertEqual(check.reason, reason, f"M1-settle exit {code}")


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
            [PYTHON, "-I", "-S", "-c", RUNNER_LAUNCHER, str(ROOT), "canary-e2e", "--", PYTHON, "-I",
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
        self.assertEqual(result.returncode, 0, "S-no-list")
        result = host.tool("disarm", "--run", host.run_id, forbid_list=host.store)
        self.assertEqual(result.returncode, 0, "S-no-list disarm")

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

    def test_an_invalid_record_is_never_cleaned_away(self):
        """An armed run whose record no longer validates cannot be disarmed safely: cleanup reports invalid (4) and
        keeps the run directory and the synthetic store file for the operator (contract 7, 12)."""
        host = self.armed_host()
        host.arm("subagent")
        with open(host.path / "events.jsonl", "a") as handle:
            handle.write('{"seq": "not a record"}\n')
        result = host.tool("cleanup", "--run", host.run_id)
        self.assertEqual(result.returncode, 4, "R8-invalid-cleanup")
        self.assertTrue(host.path.is_dir() and (host.store / "canary-e2e.env").exists(), "R8-invalid-cleanup-keeps")

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
        s["header"] = s["header"][:24]
        (claude / "notes.txt").write_bytes(s["header"].encode() + b" " + canary.encode() + b"\n")
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
        # Git's stderr sentinel is written by the scan's fsck only: the setup child's own git call (the checkout
        # fingerprint) fails setup on any stderr byte, which is the strict rule, not this test's subject.
        wrapper(host, "git", prefix="if 'fsck' in sys.argv:\n    os.write(2, data)", data=values[2].encode() + b"\n")
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
            if kind in (wire.RESULT, wire.HIT, wire.OBSERVATION, wire.CONTROL) and fields.get("check") in session.checks:
                declared = session.checks[fields["check"]][0]
                fields = {"mode": declared.mode, "view": declared.view, "path": declared.path,
                          **({"object": declared.object} if kind != wire.CONTROL else {}), **fields}
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
        # A lying worker: its END's counts all match, yet one declared check never terminated (check completion), or a
        # RESULT calls itself complete while it counted stderr bytes or carries exit 2 (the coordinator trusts neither).
        for name, results in (("unterminated-check", [(1, 0, 0)]), ("stderr-count", [(1, 0, 0), (2, 3, 0)]),
                              ("exit-status", [(1, 0, 0), (2, 0, 2)])):
            lying = cp.Session(None, {"subpass": 0, "controls": None}, "A1", 5, "r", [(2, 1)], set(), [root])
            lying.nonce, lying.seal, obj = nonce, os.urandom(16), os.urandom(16)
            frames = [dict(kind=wire.BEGIN, seal=lying.seal), dict(kind=wire.BEGIN, seal=lying.seal, object=root)]
            frames += [dict(kind=wire.INVENTORY, check=check, sink=1, mode=1, view=1, expected=1, object=obj)
                       for check in (1, 2)]
            frames += [dict(kind=wire.RESULT, check=check, sink=1, mode=1, view=1, status=1, observed=1, expected=1,
                            object=obj, aux=stderr, exit=status) for check, stderr, status in results]
            frames += [dict(kind=wire.RESULT, check=0, sink=1, status=1),
                       dict(kind=wire.END, sink=1, status=1, observed=2, expected=2)]
            for fields in frames:
                self.assertTrue(lying.accept(wire.unpack(wire.pack(nonce=nonce, seq=lying.seq + 1, **fields))),
                                f"B4-{name} frame")
            outcome = lying.outcome()
            self.assertEqual((outcome["status"], "protocol_error" in outcome["reasons"]), ("incomplete", True),
                             f"B4-{name}")

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

    def test_b6_worker_runs_the_bound_absolute_path_after_the_plan(self):
        """An rg that appears earlier on CHILD_PATH after the coordinator's own executable check is never what the
        worker starts: the worker names the bound absolute path, never a bare name."""
        host = Host(self)
        early = host.root / "early"
        early.mkdir()
        host.constants["CHILD_PATH"] = f"{early}:{host.bin}"
        (host.home / ".claude" / "a.txt").write_text("plain\n")
        host.prepare()
        marker = host.root / "early-ran"
        script = f"#!/bin/sh\ntouch {marker}\nexec {REAL['rg']} \"$@\"\n".encode().hex()
        result = host.scan(worker={"hooks": {"after_prewalk": {"do": "create", "target": str(early / "rg"),
                                                               "data": script, "mode": 0o755}}})
        self.assertEqual(result.returncode, 0, "B6-bound-absolute-path")
        self.assertFalse(marker.exists(), "B6-bound-absolute-path")

    def test_b7_union_integrity(self):
        cases = {"dropped-form": {"hooks": {"before_plan": {"do": "union", "edit": "drop"}}},
                 "blank-line": {"hooks": {"before_plan": {"do": "union", "edit": "blank"}}},
                 "altered-form": {"hooks": {"before_plan": {"do": "union", "edit": "alter"}}},
                 "after-plan": {"worker": {"hooks": {"after_prewalk": {"do": "union"}}}},
                 "before-child": {"worker": {"hooks": {"before_child": {"do": "union", "when": "rg"}}}},
                 # An attempt pattern file altered after prepare (appended form, blank line) is refused before work.
                 "attempt-appended": {"tamper": b"CNRYE2Eappendedline\n"}, "attempt-blank": {"tamper": b"\n"}}
        for name, spec in cases.items():
            with self.subTest(name=name):
                host = Host(self)
                host.constants["AGENT_SINKS"] = ["A1"]  # one worker: no later worker's start re-reads the union
                (host.home / ".claude" / "a.txt").write_text("plain\n")
                host.prepare()
                spec = dict(spec)
                tamper = spec.pop("tamper", None)
                if tamper:
                    with open(host.path / "patterns" / "subagent.1", "ab") as handle:
                        handle.write(tamper)
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

    def test_r3_baseline_user_and_comparison_rows_and_partial_ledgers(self):
        for phase, group, name in (("baseline", "agent", "baseline"), ("final", "user", "user_run"),
                                   ("comparison", "user", "comparison")):
            if group == "user":
                self.assertEqual(self.host.scan(phase, "--user-run", tty=True).returncode, 0)
                events = self.host.events()
            else:
                events = self.events
            request = latest(events, "scan_requested", phase=phase, group=group)["request"]
            finished = latest(events, "scan_finished", request=request)
            sink = next(iter(finished["sinks"]))
            for case in ("missing", "deadline", "control", "ledger", "roots"):
                with self.subTest(group=name, case=case):
                    changed = copy.deepcopy(events)
                    rows = latest(changed, "scan_finished", request=request)["sinks"]
                    row = rows[sink]
                    if case == "missing":
                        del rows[sink]
                        expected = name + "_sink_not_scanned:" + sink
                    elif case in ("deadline", "control"):
                        row.update(status="incomplete", reasons=["deadline" if case == "deadline" else "control_missing"])
                        expected = name + ("_sink_incomplete:" + sink if case == "deadline" else "_control_missing")
                    else:
                        if case == "ledger":
                            row["ledger"][0][4] = 0
                            expected = f"{name}_check_not_scanned:{row['ledger'][0][1]}:{row['ledger'][0][0]}"
                        else:
                            row["roots"] = []
                            expected = "inventory_unreconciled"
                    result = self.codes(changed)
                    self.assertIn(expected, result["codes"], "REPAIR-R3-group-" + case)
                    self.assertNotEqual(result["verdict"], "clean", "REPAIR-R3-group-verdict")

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
        # A complete-looking sink row whose ledger holds a declared check without a terminal result names that check.
        forged = self.codes(mutate(self.events, sinks(final_seq, lambda s: s["A1"]["ledger"][0].__setitem__(4, 0))))
        self.assertTrue(any(code.startswith("check_not_scanned:") for code in forged["codes"])
                        and "inventory_unreconciled" in forged["codes"], "R3-code check_not_scanned")
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
                # Each kill point faces a passing final, never an earlier point's unfinished request.
                self.assertEqual(self.host.scan("final").returncode, 0, f"R1-passing-before {point}")
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
        # The request itself cannot be made durable: no work starts, nothing is planned, the old pass is not current.
        count = len(self.host.events())
        result = self.host.tool("scan", "--run", self.host.run_id, "--phase", "final", fail_fsync=True)
        self.assertEqual(result.returncode, 3, "R2-append-failure")
        self.assertFalse(any(event["event"] == "scan_planned" for event in self.host.events()[count:]),
                         "R2-append-failure admits no work")
        self.assertNotEqual(self.host.verdict()[1], "clean", "R2-append-failure")
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
        self.assertEqual(host.scan("baseline").returncode, 3, "R6-vanished")
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


@needs_tools
class StabilityTests(unittest.TestCase):
    """ST1–ST9: independent writers change synthetic sinks at the real worker's seams."""

    def fixture(self, data=b"original\n", name="sample"):
        host = Host(self)
        host.constants["AGENT_SINKS"] = ["A1"]
        host.prepare("--transcripts", "confirmed")
        path = host.home / ".claude" / name
        path.write_bytes(data)
        return host, path

    def test_st1_replacement_before_and_after_held_handoff(self):
        for seam in ("after_prewalk", "after_handoff"):
            with self.subTest(seam=seam):
                host, path = self.fixture()
                replacement = host.root / "replacement"
                replacement.write_text(host.canary() + "\n")
                result = host.scan(worker={"hooks": {seam: {"do": "replace", "source": str(replacement),
                    "target": str(path), "once": str(host.root / "once"), "when": "sample" if seam != "after_prewalk" else ""}}})
                self.assertEqual(result.returncode, 5, "ST1-retry-finds-replacement")
                self.assertEqual(host.finished()["sinks"]["A1"]["subpass"], 1, "ST1-stability-retry")
        # The reverse: the pre-walk's file held the canary and a clean file replaces it after the handoff. The held
        # descriptor still reads the original inode, so the hit is in subpass 0; a pathname reopen would miss it.
        host, path = self.fixture()
        path.write_text(host.canary() + "\n")
        replacement = host.root / "replacement"
        replacement.write_text("clean\n")
        result = host.scan(worker={"hooks": {"after_handoff": {"do": "replace", "source": str(replacement),
                                                               "target": str(path), "once": str(host.root / "once"),
                                                               "when": "sample"}}})
        self.assertEqual(result.returncode, 5, "ST1-held-fd-reads-original")
        self.assertTrue(any(e["subpass"] == 0 for e in hits(host)), "ST1-held-fd-reads-original")

    def test_st2_same_inode_overwrite_append_truncate_and_restored_mtime(self):
        for offset, content in ((0, "overwrite"), (None, "append"), (0, "truncate")):
            with self.subTest(content=content):
                host, path = self.fixture(b"x" * 200)
                identity = path.stat()
                spec = {"do": "write", "target": str(path), "data": host.canary().encode().hex(), "offset": offset,
                        "mtime": identity.st_mtime_ns, "once": str(host.root / "once"), "when": "sample"}
                if content == "truncate":
                    spec["do"] = "create"
                result = host.scan(worker={"hooks": {"after_file_scan": spec}})
                self.assertEqual(result.returncode, 5, "ST2-retry-finds-overwrite")
                self.assertEqual(host.finished()["sinks"]["A1"]["subpass"], 1, "ST2-ctime-retry")

    def test_st3_plain_to_compressed_and_reverse_conversion(self):
        import gzip
        for reverse in (False, True):
            host, path = self.fixture(gzip.compress(b"old\n") if reverse else b"old\n")
            replacement = host.root / "replacement"
            replacement.write_bytes(host.canary().encode() if reverse else gzip.compress(host.canary().encode()))
            result = host.scan(worker={"hooks": {"after_file_scan": {"do": "replace", "source": str(replacement),
                "target": str(path), "once": str(host.root / "once"), "when": "sample"}}})
            self.assertEqual(result.returncode, 5, "ST3-route-retry-finds-canary")
            self.assertTrue(any(e["mode"] == (1 if reverse else 2) for e in hits(host)), "ST3-new-route")

    def test_st4_new_file_directory_and_task_glob_are_reconciled(self):
        for task in (False, True):
            host, _path = self.fixture()
            if task:
                host.constants["AGENT_SINKS"] = ["A10"]
                target = host.root / "tasks" / "branch" / "second" / "tasks" / "new"
            else:
                target = host.home / ".claude" / "new-directory" / "new"
            result = host.scan(worker={"hooks": {"after_prewalk": {"do": "create", "target": str(target),
                "data": host.canary().encode().hex(), "once": str(host.root / "once")}}})
            self.assertEqual(result.returncode, 5, "ST4-retry-finds-new-entry")
            self.assertEqual(host.finished()["sinks"]["A10" if task else "A1"]["subpass"], 1, "ST4-entry-list")
        # Created after the scan pass had listed its parent and scanned its neighbour: no held descriptor or scan-pass
        # listing sees it, only the final re-walk's entry-list comparison does.
        host, _path = self.fixture()
        result = host.scan(worker={"hooks": {"after_file_scan": {"do": "create", "target": str(host.home / ".claude/late"),
            "data": host.canary().encode().hex(), "once": str(host.root / "once"), "when": "sample"}}})
        self.assertEqual(result.returncode, 5, "ST4-new-entry-after-scan-pass")
        self.assertEqual(host.finished()["sinks"]["A1"]["subpass"], 1, "ST4-new-entry-after-scan-pass")

    def test_st5_changes_in_both_subpasses_are_incomplete(self):
        host, path = self.fixture()
        result = host.scan(worker={"hooks": {"after_file_scan": {"do": "write", "target": str(path),
            "data": b"added".hex(), "when": "sample"}}})
        self.assertEqual(result.returncode, 3, "ST5-bounded-retries")
        self.assertEqual(host.finished()["sinks"]["A1"]["subpass"], 1, "ST5-one-retry")
        self.assertIn("file_set_changed", sink_reasons(host), "ST5-full-tuple")

    def test_st6_names_targets_paths_and_newlines_never_enter_argv(self):
        host, _path = self.fixture()
        root, value = host.home / ".claude", host.canary()
        first, second = value.split("/")
        (root / first).mkdir()
        (root / first / second).write_bytes(b"")
        os.symlink("/nonexistent/" + value, root / "dangling")
        os.mkfifo(root / (value.replace("/", "_") + "\nname"))
        os.close(os.open(os.fsencode(root) + b"/nonutf-\xff\n", os.O_CREAT | os.O_WRONLY, 0o600))
        (root / "newline\nfile").write_text(value)
        # A discovered Git store below a canary-named directory: Git runs with the validated store as its cwd, so
        # even Git's argv never names that path.
        git_repo(root / ("repo-" + next(f for f in cp.forms(value) if "/" not in f and "\\" not in f)), {"f": b"old\n"})
        argv_record = host.root / "argv"
        host.worker["argv_record"] = str(argv_record)
        self.assertEqual(host.scan().returncode, 5, "ST6-path-leak")
        self.assertTrue(any(e["mode"] == 6 for e in hits(host)), "ST6-name-class")
        self.assertFalse(any(form.encode() in argv_record.read_bytes() for form in cp.forms(value)), "ST6-no-sink-argv")

    def test_st6_link_outcomes_are_distinct(self):
        """Contract 9.2: a link out of every covered root is link_out (incomplete); a declared pair, a link into a
        covered root, into K and a dangling link are each counted in their own ledger class."""
        host, _path = self.fixture()
        claude = host.home / ".claude"
        (host.root / "outside").mkdir()
        os.symlink(host.root / "outside", claude / "out")
        self.assertEqual(host.scan().returncode, 3, "ST6-link-out")
        self.assertIn("link_out", sink_reasons(host), "ST6-link-out")
        os.unlink(claude / "out")
        skills = host.home / ".agents" / "skills"
        skills.mkdir(parents=True)
        os.symlink(skills, claude / "skills")
        os.symlink(claude / "sample", claude / "inside")
        (host.home / ".ssh").mkdir(mode=0o700)
        os.symlink(host.home / ".ssh", claude / "keys")
        os.symlink(host.root / "missing", claude / "dangling")
        self.assertEqual(host.scan().returncode, 0, "ST6-link-outcomes-complete")
        counters = host.finished()["sinks"]["A1"]["counters"]
        self.assertEqual([counters[name] for name in ("declared_link", "covered_link", "excluded_link",
                                                      "dangling_link")], [1, 1, 1, 1], "ST6-link-ledger")

    def test_st7_exact_exclusions_and_unreadable_entries(self):
        host, path = self.fixture()
        path.chmod(0)
        (path.parent / "locked").mkdir(mode=0)
        self.assertEqual(host.scan().returncode, 3, "ST7-permission-incomplete")
        self.assertIn("open_error", sink_reasons(host), "ST7-000-file")
        self.assertIn("walk_error", sink_reasons(host), "ST7-000-directory")
        path.chmod(0o600)
        (path.parent / "locked").chmod(0o700)
        for rel in (".credentials.json", "daemon/control.key", "sessions/x.key", "settings.json", "context-mode/x",
                    "history.jsonl", "paste-cache/x", "backups/x"):
            target = path.parent / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(host.canary())
        forbidden = [str(path.parent / name) for name in (".credentials.json", "daemon/control.key", "sessions/x.key",
            "settings.json", "context-mode", "history.jsonl", "paste-cache", "backups")]
        self.assertEqual(host.scan(worker={"forbid_paths": forbidden}).returncode, 0, "ST7-K-U-never-opened")
        (path.parent / "ordinary").mkdir()
        (path.parent / "ordinary" / "auth.json").write_text(host.canary())
        self.assertEqual(host.scan().returncode, 5, "ST7-ordinary-auth-scanned")

    def test_st8_threshold_unknown_fs_unverifiable_fs_and_clock(self):
        from unittest import mock
        host, path = self.fixture()
        path.write_text(host.canary())
        prepared = host.events()[0]
        self.assertEqual(prepared["threshold_ns"], prepared["ref"]["ctime_ns"] - 3600 * 10**9, "ST8-hour-margin")
        with mock.patch.object(cp, "clock", return_value=("x", prepared["realtime_ns"] - 61 * 10**9,
                                                       prepared["boottime_ns"])):
            run = cp.Run(host.env(), host.run_id)
            run.load()
            self.assertIn("clock_stepped", cp.integrity(run), "ST8-drift")
            os.close(run.lock)
        for magic, expected in ((1234567, 5), (0x6969, 3)):
            other, p = self.fixture()
            p.write_text(other.canary() if expected == 5 else "plain")
            self.assertEqual(other.scan(worker={"fs_magic": magic}).returncode, expected, "ST8-filesystem")
        scan = type("S", (), {"plan": {"roots": [], "threshold_ns": path.stat().st_ctime_ns + 1, "selection": "changed"}})()
        walk = wire.Walk(scan, {"id": "00" * 16, "kind": "dir", "path": str(path.parent)}, number=1)
        walk.fs_all = False
        self.assertFalse(walk.selected_by_time(path.stat()), "ST8-unselected")
        walk.threshold -= 1800 * 10**9
        self.assertTrue(walk.selected_by_time(path.stat()), "ST8-30-minute-selected")

    def test_st9_pointer_binding_and_directory_refusal(self):
        host, path = self.fixture()
        inventory = json.loads((ROOT / "adoption/credential-inventory.json").read_text())
        name = next(name for entry in inventory["entries"] for name in entry["pointer_variables"])
        refused = host.tool("prepare", env=host.env(**{name: str(path.parent)}))
        self.assertEqual(refused.returncode, 1, "ST9-pointer-directory")
        self.assertEqual(host.scan(env=host.env(**{name: str(path)})).returncode, 3, "ST9-new-pointer")
        self.assertIn("pointer_changed", sink_reasons(host), "ST9-bound-only")
        # A pointer target bound at prepare inside a root is an exact exclusion: counted, never opened, no refusal.
        bound = Host(self)
        bound.constants["AGENT_SINKS"] = ["A1"]
        target = bound.home / ".claude" / "pointed"
        target.write_text("placeholder\n")
        env = bound.env(**{name: str(target)})
        result = bound.tool("prepare", "--transcripts", "confirmed", env=env)
        self.assertEqual(result.returncode, 0, "ST9-bound-prepare")
        bound.run_id = re.search(rb"run: (cp-\S+)", result.stdout).group(1).decode()
        target.write_text(bound.canary() + "\n")
        self.assertEqual(bound.scan(env=env, worker={"forbid_paths": [str(target)]}).returncode, 0,
                         "ST9-bound-target-excluded")
        self.assertEqual(bound.finished()["sinks"]["A1"]["counters"]["excluded_key"], 1, "ST9-bound-target-counted")
        self.assertNotIn(str(target).encode(), (bound.path / "events.jsonl").read_bytes(), "ST9-no-raw-pointer-path")

    def test_st9_route_recheck_under_deferred_timestamps(self):
        """Each selected file's format decision is re-derived after its views and in the final re-walk (9.3). A seam
        drops the times from the identity tuple, as a shared-mapping writer's deferred timestamps would, so only the
        route recheck can see a same-size rewrite from gzip to plain text."""
        import gzip
        host, path = self.fixture(gzip.compress(secrets.token_bytes(96)))
        text = (host.canary() + "\n").encode().ljust(path.stat().st_size, b".")
        spec = {"do": "write", "target": str(path), "data": text.hex(), "offset": 0, "once": str(host.root / "once"),
                "when": "sample"}
        result = host.scan(worker={"coarse_tuple": True, "hooks": {"after_file_scan": spec}})
        self.assertEqual(result.returncode, 5, "ST9-route-recheck")
        self.assertEqual(host.finished()["sinks"]["A1"]["subpass"], 1, "ST9-route-recheck")


def blocked_program(host, name, phase=None, prefix="", occurrence=1, stream_only=False):
    """A labelled executable blocks on an owned FIFO, while --version remains the real upstream version."""
    fifo = host.root / ("blocked-" + name)
    os.mkfifo(fifo)
    host.test.addCleanup(os.close, os.open(fifo, os.O_RDWR | os.O_NONBLOCK | os.O_CLOEXEC))
    real = REAL.get(name) or "/usr/bin/" + name
    code = "#!/usr/bin/python3 -I\nimport os, sys, json\n"
    if phase != "--version":
        code += f"if sys.argv[1:] == ['--version']:\n    os.execv({real!r}, [{real!r}, '--version'])\n"
    if phase == "--version":
        # A setpriv wrapper also carries the target's argv. Block its own version call only, after the outer
        # upstream setpriv has installed PDEATHSIG; an argv substring would block the launcher before that step.
        code += f"if sys.argv[1:] != ['--version']:\n    os.execv({real!r}, [{real!r}] + sys.argv[1:])\n"
    elif phase:
        code += f"if {phase!r} not in sys.argv:\n    os.execv({real!r}, [{real!r}] + sys.argv[1:])\n"
    if stream_only:
        code += f"if '--' not in sys.argv or sys.argv[sys.argv.index('--') + 1:] != ['-']:\n    os.execv({real!r}, [{real!r}] + sys.argv[1:])\n"
    counter = str(host.root / ("calls-" + name))
    code += (f"n=int(open({counter!r}).read()) if os.path.exists({counter!r}) else 0\n"
             f"open({counter!r}, 'w').write(str(n+1))\n"
             f"if n+1 != {occurrence}:\n    os.execv({real!r}, [{real!r}] + sys.argv[1:])\n")
    ready = host.root / f"ready-{name}"  # created just before it blocks, so an observer knows the child is running
    code += prefix + (f"\nfd=os.open({str(fifo)!r}, os.O_RDONLY)\n"
                      f"json.dump(dict(pid=os.getpid(), fd=fd), open({str(ready)!r}, 'w'))\n"
                      "os.read(fd, 1)\n")
    host.script(name, code)
    return fifo


def observe_fifo(test, ready, fifo, process, seconds=20):
    """Independent kernel observation: the intended child holds this FIFO and is sleeping in its read."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline and process.poll() is None:
        try:
            record = json.loads(ready.read_text())
            pid, fd = record["pid"], record["fd"]
            info, expected = os.stat(f"/proc/{pid}/fd/{fd}"), fifo.stat()
            args = Path(f"/proc/{pid}/cmdline").read_bytes()
            wait = Path(f"/proc/{pid}/wchan").read_text()
            if (stat.S_ISFIFO(info.st_mode) and (info.st_dev, info.st_ino) == (expected.st_dev, expected.st_ino)
                    and str(ready.parent).encode() in args and wait in ("pipe_read", "anon_pipe_read")):
                return pid
        except (OSError, ValueError, KeyError):
            pass
        time.sleep(.02)
    test.assertTrue(False, "FIFO-intended-child-observed")


def scopes_of(pids) -> set:
    """The ecosystem-job scope cgroups (kernel paths) these processes belong to, other than this test process's own
    (a suite may itself run inside a bounded job): the independent scope observer."""
    found = set()
    for pid in [*pids, "self"]:
        try:
            with open(f"/proc/{pid}/cgroup", "rb") as handle:
                lines = handle.read().splitlines()
        except OSError:
            continue
        scopes = {line[3:].decode() for line in lines
                  if line.startswith(b"0::/") and re.search(rb"/ecosystem-job-\d+-\d+-\d+\.scope$", line)}
        found = found - scopes if pid == "self" else found | scopes
    return found


def wait_scopes_gone(paths, seconds: float) -> list:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if not any(os.path.isdir("/sys/fs/cgroup" + path) for path in paths):
            return []
        time.sleep(0.25)
    return sorted(path for path in paths if os.path.isdir("/sys/fs/cgroup" + path))


@needs_tools
class FifoTests(unittest.TestCase):
    """F-M1a/b/c, F-M2/b, F-M3/4/5/6 and F-U4: five-second deadlines, independent kernel observers."""

    def fixture(self, sink="A1"):
        host = Host(self)
        host.constants["AGENT_SINKS"] = [sink]
        host.worker["constants"]["BUDGET_CAP"] = 5.0
        host.constants["SCOPE_SECONDS"] = {**{name: 5 for name in wire.SINKS}, "setup": 120}
        return host

    def ended(self, host, result):
        self.assertEqual(result.returncode, 3, "FIFO-incomplete-never-zero")
        self.assertEqual(host.finished()["status"], "incomplete", "FIFO-incomplete-record")
        self.assertEqual(wait_gone(str(host.root), 20), [], "FIFO-kernel-processes-gone")

    def blocked_scan(self, host, name, fifo=None, ready=None, extra=(), **kwargs):
        process = host.scan("final" if extra else "baseline", *extra, background=True, **kwargs)
        self.addCleanup(ContainmentTests.reap, self, host, process)
        observe_fifo(self, ready or host.root / f"ready-{name}", fifo or host.root / f"blocked-{name}", process)
        process.communicate(timeout=40)
        self.ended(host, process)
        self.assertIn("deadline", host.finished()["reasons"], "FIFO-required-deadline")

    def test_f_m1a_special_is_named_and_never_opened(self):
        host = self.fixture()
        host.prepare()
        fifo = host.home / ".claude" / "initial-fifo"
        os.mkfifo(fifo)
        self.assertEqual(host.scan(worker={"forbid_paths": [str(fifo)]}).returncode, 0, "F-M1a-no-content-open")
        self.assertEqual(host.finished()["sinks"]["A1"]["counters"]["special"], 1, "F-M1a-special-count")
        self.assertEqual(sink_reasons(host), [], "F-M1a-complete-special-coverage")

    def test_f_m1b_c_swaps_before_and_after_handoff_raw_le_be(self):
        for data in (b"plain", b"\xff\xfep\x00l\x00", b"\xfe\xff\x00p\x00l"):
            for seam in ("before_handoff", "after_handoff"):
                with self.subTest(data=data[:2], seam=seam):
                    host = self.fixture()
                    path = host.home / ".claude" / "sample"
                    path.write_bytes(data)
                    host.prepare()
                    result = host.scan(worker={"hooks": {seam: {"do": "fifo", "target": str(path), "when": "sample",
                        "once": str(host.root / "once")}}})
                    self.ended(host, result)
                    # Before the handoff the nonblocking open plus fstat type check rejects the FIFO; after it, the
                    # final re-walk sees a regular file turned special, a hard type change no retry may absorb.
                    self.assertIn("changed_type", sink_reasons(host), "F-M1b-type-check " + seam)

    def test_f_m2_each_decoder_and_both_bom_readers(self):
        import bz2, gzip, lzma
        compressors = {"gzip": gzip.compress, "bzip2": bz2.compress, "xz": lzma.compress,
                       "lzma": lambda value: lzma.compress(value, format=lzma.FORMAT_ALONE)}
        for fmt, compress in compressors.items():
            for bom in (False, True):
                with self.subTest(fmt=fmt, bom=bom):
                    host = self.fixture()
                    name = "xz" if fmt == "lzma" else fmt
                    prefix = "os.write(1, b'\\xff\\xfe' + b'x\\x00' * 300)" if bom else ""
                    blocked_program(host, name, prefix=prefix)
                    (host.home / ".claude" / ("sample.lzma" if fmt == "lzma" else "sample")).write_bytes(compress(b"old"))
                    host.prepare()
                    self.blocked_scan(host, name)
        host = self.fixture()
        path = host.home / ".claude" / "sample.gz"
        path.write_bytes(gzip.compress(b"old"))
        host.prepare()
        self.ended(host, host.scan(worker={"hooks": {"before_handoff": {"do": "fifo", "target": str(path),
            "when": "sample"}}}))

    def test_f_m2b_one_reader_stalls(self):
        import gzip
        for encoding in ("none", "auto"):
            host = self.fixture()
            blocked_program(host, "rg", phase=encoding, stream_only=True)
            (host.home / ".claude" / "sample.gz").write_bytes(gzip.compress(b"\xff\xfe" + "old".encode("utf-16-le")))
            host.prepare()
            self.blocked_scan(host, "rg")

    def test_f_m3_journal_producer(self):
        host = self.fixture("A11")
        host.prepare()
        # Change and rebind only the synthetic executable; this exercises the stream rather than pin refusal.
        blocked_program(host, "journalctl", phase="--user")
        self.repin(host, "journalctl")
        self.blocked_scan(host, "journalctl")

    def repin(self, host, name):
        events = host.events()
        events[0]["executables"][name] = wire.sha256_file(host.bin / name)
        (host.path / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events))

    def test_f_m4_each_git_stage_and_metadata_fifo(self):
        for phase in ("fsck", "verify-pack", "--batch-check=%(objectname) %(objecttype) %(objectsize)",
                      "--batch=%(objectname) %(objecttype) %(objectsize)"):
            with self.subTest(phase=phase):
                host = self.fixture()
                git_repo(host.home / ".claude" / "plugins" / "p", {"file": b"old"})
                blocked_program(host, "git", phase=phase)
                host.prepare()
                self.blocked_scan(host, "git")
        host = self.fixture()
        repo = git_repo(host.home / ".claude" / "plugins" / "p", {"file": b"old"})
        keep = next(repo.glob("objects/pack/*.pack")).with_suffix(".keep")
        keep.write_text("old")
        host.prepare()
        self.ended(host, host.scan(worker={"hooks": {"before_handoff": {"do": "fifo", "target": str(keep),
            "when": ".keep"}}}))

    def test_f_m5_database_swap_and_dumper_stall(self):
        for swap in (True, False):
            host = self.fixture()
            path = sqlite_file(host.home / ".claude" / "sample", [("CREATE TABLE t(v)", ())])
            host.prepare()
            if swap:
                result = host.scan(worker={"hooks": {"before_handoff": {"do": "fifo", "target": str(path),
                    "when": "sample"}}})
            else:
                fifo = host.root / "dumper-fifo"
                os.mkfifo(fifo)
                ready = host.root / "ready-dumper"
                self.blocked_scan(host, "dumper", fifo, ready, dumper={"hooks": {"after_identity": {
                    "do": "block", "path": str(fifo), "ready": str(ready)}}})
                continue
            self.ended(host, result)

    def test_f_m6_name_and_link_target_are_never_opened_and_worker_deadline(self):
        host = self.fixture()
        host.prepare()
        value = next(form for form in cp.forms(host.canary()) if "/" not in form)
        fifo = host.home / ".claude" / value
        os.mkfifo(fifo)
        os.symlink(str(fifo), fifo.parent / "link")
        self.assertEqual(host.scan(worker={"forbid_paths": [str(fifo)]}).returncode, 5, "F-M6-name-hit")
        self.assertEqual(sink_reasons(host), ["link_out"], "F-M6-never-opened")
        self.assertEqual(host.finished()["sinks"]["A1"]["counters"]["special"], 1, "F-M6-special-count")
        other = self.fixture()
        other.prepare()
        block = other.root / "m6-fifo"
        os.mkfifo(block)
        ready = other.root / "ready-worker"
        self.blocked_scan(other, "worker", block, ready, worker={"hooks": {"before_m6": {
            "do": "block", "path": str(block), "ready": str(ready)}}})

    def test_f_u4_full_environment_producer_in_pty(self):
        host = self.fixture()
        host.constants["USER_SINKS"] = ["U4"]
        blocked_program(host, "systemctl", phase="show-environment")
        host.prepare()
        self.blocked_scan(host, "systemctl", extra=("--user-run",), tty=True)


@needs_tools
class ModeTests(unittest.TestCase):
    """M1–M7: actual reviewed scanners/decoders, strict failures and independent logical-vs-raw oracles."""

    def fixture(self, sink="A1"):
        host = Host(self)
        host.constants["AGENT_SINKS"] = [sink]
        return host

    def test_m1_nul_empty_bom_raw_and_utf16_views(self):
        host = self.fixture()
        host.prepare()
        value, root = host.canary(), host.home / ".claude"
        for name, data in (("nul", b"\0" + value.encode()), ("empty", b""), ("negative", b"old"),
                           ("bomraw", b"\xff\xfe" + value.encode()),
                           ("le", b"\xff\xfe" + value.encode("utf-16-le")),
                           ("be", b"\xfe\xff" + value.encode("utf-16-be"))):
            (root / name).write_bytes(data)
        self.assertEqual(host.scan().returncode, 5, "M1-positive-raw-and-bom")
        self.assertEqual({e["view"] for e in hits(host)}, {1, 2}, "M1-additive-views")
        key = (host.path / "key").read_bytes()
        for name, view in (("nul", 1), ("bomraw", 1), ("le", 2), ("be", 2)):
            obj = wire.keyed(key, b"file", 1, 1, name.encode()).hex()
            self.assertTrue(any(e["object"] == obj and e["view"] == view for e in hits(host)),
                            "M1-attributed-" + name)
        self.assertEqual(host.finished()["status"], "complete", "M1-complete-all-fixtures")
        self.assertEqual(host.finished()["sinks"]["A1"]["counters"]["selected"], 7, "M1-empty-accounted")
        # The raw pass alone must find ASCII behind a BOM: a BOM-sniffing raw pass decodes it away (encoding none).
        alone = self.fixture()
        alone.prepare()
        (alone.home / ".claude" / "bomraw").write_bytes(b"\xff\xfe" + alone.canary().encode())
        self.assertEqual(alone.scan().returncode, 5, "M1-raw-after-bom")
        self.assertEqual({e["view"] for e in hits(alone)}, {1}, "M1-raw-after-bom view")

    def test_m1_scanner_exit_stderr_stats_and_unknown_records(self):
        relay = (f"import subprocess\nsys.stdout.buffer.write(subprocess.run([{REAL['rg']!r}] + sys.argv[1:], "
                 "stdout=subprocess.PIPE).stdout)\nsys.stdout.flush()\nsys.exit(2)")
        cases = {"exit": "sys.exit(2)", "stderr": "os.write(2, b'x')",
                 "empty": "os.write(1, b'<stdin>\\0\\n'); sys.exit(0)",
                 "unknown": "os.write(1, b'<stdin>\\0unknownmatch\\n'); sys.exit(0)",
                 "label": "os.write(1, b'unknown\\0unknownmatch\\n'); sys.exit(0)",
                 "stats": "os.write(1, b'\\n0 matches\\n'); sys.exit(0)",
                 "exit2-valid-output": relay}  # the real scanner's complete output and stats, then exit 2
        for kind, prefix in cases.items():
            with self.subTest(kind=kind):
                host = self.fixture()
                wrapper(host, "rg", prefix=prefix)
                (host.home / ".claude" / "sample").write_text("old")
                host.prepare()
                self.assertEqual(host.scan().returncode, 3, "M1-invalid-output-incomplete " + kind)
                self.assertEqual(host.finished()["status"], "incomplete", "M1-no-complete " + kind)

    def test_m1_stat_counts_control_origins_and_output_cap(self):
        from unittest import mock
        scan = type("Scan", (), {"patterns": type("Patterns", (), {"classes": {b"CNRYCTLpositive": []}})(),
                                   "plan": {"rg_version": 14001000}, "attribute": lambda *args: None})()
        stats = b"\n1 matches\n1 matched lines\n1 files contained matches\n1 files searched\n0 bytes printed\n0 bytes searched\n0.0 seconds spent searching\n0.0 seconds\n"
        for old, new, expected in ((b"1 matches", b"0 matches", "matches_mismatch"),
                                   (b"1 files searched", b"0 files searched", "files_searched_mismatch")):
            check = wire.Check(1, "M1", "raw", "other", bytes(16), 0)
            parser = wire.RgOutput(scan, check, {b"<stdin>": None})
            parser.feed(b"<stdin>\0CNRYCTLpositive\n" + stats.replace(old, new))
            parser.close(1)
            self.assertEqual(check.reason, expected, "M1-reconcile " + expected)
        with mock.patch.object(wire, "STDOUT_CAP", 8):
            parser = wire.RgOutput(scan, wire.Check(1, "M1", "raw", "other", bytes(16), 0), {b"<stdin>": None})
            with self.assertRaises(wire.Stop, msg="M1-cap"):
                parser.feed(b"oversized" * 10)

    def test_m1_deleted_positive_control_is_incomplete(self):
        for control in ("m1/0001", "m1/0002", "m1/0003", "m1/0004", "m1/0005", "m1/0006-wal", "bom/0001"):
            host = self.fixture()
            (host.home / ".claude" / "sample").write_bytes(b"\xff\xfeo\x00l\x00d\x00")
            host.prepare()
            self.assertEqual(host.scan(worker={"hooks": {"after_prewalk": {"do": "unlink-control", "glob": control}}})
                             .returncode, 3, "M1-control-removal " + control)

    def test_m1_emptied_positive_control_is_incomplete(self):
        """The control file is still there and rg exits cleanly, but no record names its control value."""
        for control in ("m1/0001", "bom/0001"):
            host = self.fixture()
            (host.home / ".claude" / "sample").write_bytes(b"\xff\xfeo\x00l\x00d\x00")
            host.prepare()
            result = host.scan(worker={"hooks": {"after_prewalk": {"do": "truncate-control", "glob": control}}})
            self.assertEqual(result.returncode, 3, "M1-control-emptied " + control)
            self.assertIn("control_missing", sink_reasons(host), "M1-control-emptied " + control)

    def test_m2_every_compressor_endian_concat_and_physical_header(self):
        import bz2, gzip, lzma
        compressors = {"gz": gzip.compress, "bz2": bz2.compress, "xz": lzma.compress,
                       "lzma": lambda data: lzma.compress(data, format=lzma.FORMAT_ALONE)}
        for suffix, compress in compressors.items():
            host = self.fixture()
            host.prepare()
            root, value = host.home / ".claude", host.canary()
            for label, data in (("plain", value.encode()), ("le", b"\xff\xfe" + value.encode("utf-16-le")),
                                ("be", b"\xfe\xff" + value.encode("utf-16-be")),
                                ("rawbom", b"\xff\xfe" + value.encode())):
                (root / (label + "." + suffix)).write_bytes(compress(data))
            self.assertEqual(host.scan().returncode, 5, "M2-each-compressor " + suffix)
            self.assertTrue(any(e["mode"] == 2 and e["view"] == 4 for e in hits(host)), "M2-decoded-bom " + suffix)
            self.assertTrue(any(e["mode"] == 2 and e["view"] == 3 for e in hits(host)), "M2-decoded-raw " + suffix)
            self.assertEqual(host.finished()["status"], "complete", "M2-every-branch-complete " + suffix)
            # A compressed UTF-16 canary alone: only the BOM-first, same-encoding branch of that one decoder sees it.
            alone = self.fixture()
            alone.prepare()
            (alone.home / ".claude" / ("le." + suffix)).write_bytes(
                compress(b"\xff\xfe" + alone.canary().encode("utf-16-le")))
            self.assertEqual(alone.scan().returncode, 5, "M2-utf16-only-in-bom-view " + suffix)
            self.assertEqual({(e["mode"], e["view"]) for e in hits(alone)}, {(2, 4)}, "M2-utf16-only-in-bom-view "
                             + suffix)
        host = self.fixture()
        host.prepare()
        value = host.canary()
        (host.home / ".claude" / "two.gz").write_bytes(gzip.compress(b"first") + gzip.compress(value.encode()))
        member = gzip.compress(b"old")
        (host.home / ".claude" / "fname.gz").write_bytes(member[:3] + b"\x08" + member[4:10] + value.encode() +
                                                         b"\0" + member[10:])
        self.assertEqual(host.scan().returncode, 5, "M2-member2-and-physical-header")
        self.assertEqual({e["mode"] for e in hits(host)}, {1, 2}, "M2-physical-additive")

    def test_m2_missing_decoder_spawn_failure_stderr_trailing_nested_and_odd_bom(self):
        import bz2, gzip
        cases = {"missing": gzip.compress(b"old"), "spawn": gzip.compress(b"old"),
                 "stderr": gzip.compress(b"old"), "trailing": bz2.compress(b"old") + b"garbage",
                 "padding": gzip.compress(b"old") + b"\0" * 8 + gzip.compress(b"old"),
                 "nested": gzip.compress(gzip.compress(b"old")), "odd": gzip.compress(b"\xff\xfex"),
                 "truncated": gzip.compress(b"old")[:-3]}
        for kind, data in cases.items():
            with self.subTest(kind=kind):
                host = self.fixture()
                if kind == "missing":
                    (host.bin / "gzip").unlink()
                elif kind == "stderr":
                    wrapper(host, "gzip", stderr=b"warning")
                (host.home / ".claude" / "sample").write_bytes(data)
                host.prepare()
                worker = {"fail_spawn": "gzip"} if kind == "spawn" else {}
                self.assertEqual(host.scan(worker=worker).returncode, 3, "M2-failure-incomplete " + kind)

    def test_m2_every_magic_name_container_and_residual(self):
        import zlib
        rows = [(magic, b"opaque") for magic, _fmt in wire.UNCOVERED]
        rows += [(b"\x50\x2a\x4d\x18", b"opaque")]
        rows += [(b"x" * offset + magic, b"opaque") for offset, magic in wire.CONTAINERS]
        rows += [(b"opaque", b"x" + name) for name, _fmt in wire.UNCOVERED_NAMES + wire.NAMED]
        for header, name in rows:
            host = self.fixture()
            (host.home / ".claude" / os.fsdecode(name)).write_bytes(header + b"old")
            host.prepare()
            self.assertEqual(host.scan().returncode, 3, "M2-routing-row " + name.decode())
        self.assertEqual(wire.route(zlib.compress(b"opaque"), b"extensionless"), ("plain", None), "M2-zlib-residual")

    def test_m3_cursor_anchor_binary_fields_and_cmdline(self):
        host = self.fixture("A11")
        host.prepare()
        host.journal_add(b"old", _CMDLINE="hex:" + host.canary().encode().hex())
        self.assertEqual(host.scan().returncode, 5, "M3-full-cmdline")
        other = self.fixture("A11")
        other.prepare()
        anchor = other.path.joinpath("anchor").read_bytes().strip()
        entries = json.loads(other.journal.read_text())
        entries.clear()
        entries.append(journal_entry(2, "hex:" + other.canary().encode().hex(), BINARY="hex:" + b"\n__CURSOR=fake\n\n".hex()))
        other.journal.write_text(json.dumps(entries))
        other.journal_add(anchor)
        self.assertEqual(other.scan().returncode, 5, "M3-vacuum-retains-first-hit")
        self.assertIn("journal_cursor_missing", sink_reasons(other, "A11"), "M3-first-cursor-required")
        # The bound first entry survives with its own cursor, but its anchor text is gone: only the anchor rule fails.
        third = self.fixture("A11")
        third.prepare()
        entries = json.loads(third.journal.read_text())
        entries[0] = [[name, "not the anchor" if name == "MESSAGE" else value] for name, value in entries[0]]
        third.journal.write_text(json.dumps(entries))
        self.assertEqual(third.scan().returncode, 3, "M3-anchor-required")
        self.assertNotIn("journal_cursor_missing", sink_reasons(third, "A11"), "M3-anchor-required cursor kept")

    def test_m4_real_discovered_and_configured_stores_keep_and_duplicates(self):
        for configured in (False, True):
            host = self.fixture("A12" if configured else "A1")
            path = host.home / "code/native-agent-stack-live" if configured else host.home / ".claude/plugins/p"
            store = git_repo(path, {"packed": b"old"}, loose={"loose": b"old"})
            import hashlib, zlib
            blob = b"blob 3\0old"
            oid = hashlib.sha1(blob).hexdigest()
            loose_copy = store / "objects" / oid[:2] / oid[2:]
            loose_copy.parent.mkdir(exist_ok=True)
            loose_copy.write_bytes(zlib.compress(blob))
            packed_ids = subprocess.check_output([REAL["git"], "verify-pack", "-v", str(next(store.glob("objects/pack/*.idx")))])
            self.assertIn(oid.encode() + b" blob ", packed_ids, "M4-duplicate-packed-copy")
            self.assertTrue(loose_copy.is_file(), "M4-duplicate-loose-copy")
            host.prepare()
            canary = host.canary()
            next(store.glob("objects/pack/*.pack")).with_suffix(".keep").write_text(canary)
            self.assertEqual(host.scan().returncode, 5, "M4-keep-metadata-leak")
            self.assertTrue(any(e["mode"] == 1 for e in hits(host)), "M4-keep-raw")
            self.assertGreater(host.finished()["sinks"]["A12" if configured else "A1"]["counters"]["git_stores"],
                               0, "M4-store-discovery-complete")
            self.assertEqual(host.finished()["status"], "complete", "M4-duplicates-physical-logical")

    def test_m4_orphan_index_corrupt_payload_alternate_and_promisor(self):
        env = {"PATH": "/usr/bin:/bin", "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null"}
        for kind in ("orphan", "orphan-extra", "index", "loose", "unknown", "alternate", "promisor", "exit128"):
            with self.subTest(kind=kind):
                host = self.fixture()
                repo = git_repo(host.home / ".claude/plugins/p", {"file": b"old"})
                pack = next(repo.glob("objects/pack/*.pack"))
                if kind == "orphan":
                    pack.with_suffix(".idx").unlink()
                elif kind == "index":
                    pack.unlink()
                elif kind == "loose":
                    (repo / "objects/ab").mkdir()
                    (repo / ("objects/ab/" + "c" * 38)).write_bytes(b"corrupt")
                elif kind == "unknown":
                    (repo / "objects/pack/unindexed").write_bytes(b"PACK" + b"old")
                elif kind == "alternate":
                    (repo / "objects/info/alternates").write_text(str(host.root / "unplanned"))
                elif kind == "promisor":
                    pack.with_suffix(".promisor").write_bytes(b"")
                elif kind == "exit128":  # an existing store whose fsck fails without a stderr byte
                    wrapper(host, "git", prefix="if 'fsck' in sys.argv:\n    sys.exit(128)")
                host.prepare()
                if kind == "orphan-extra":
                    # A second pack whose index is gone, holding an unreachable blob with the canary (zlib inside the
                    # pack, so no raw view sees it): the store stays usable, only the pack/index pairing reveals it.
                    blob = subprocess.run(["git", "--git-dir", str(repo), "hash-object", "-w", "--stdin"], env=env,
                                          input=host.canary().encode() + b"\n", capture_output=True, check=True)
                    extra = subprocess.run(["git", "--git-dir", str(repo), "pack-objects", "-q",
                                            str(repo / "objects/pack/pack")], env=env, input=blob.stdout,
                                           capture_output=True, check=True).stdout.strip().decode()
                    subprocess.run(["git", "--git-dir", str(repo), "prune-packed"], env=env, check=True)
                    (repo / f"objects/pack/pack-{extra}.idx").unlink()
                result = host.scan()
                self.assertEqual(result.returncode, 3, "M4-unaccounted-incomplete " + kind)
                if kind in ("orphan-extra", "exit128"):
                    self.assertIn("git_unaccounted_payload" if kind == "orphan-extra" else "producer_exit",
                                  sink_reasons(host), "M4-unaccounted-reason " + kind)

    def test_m4_stream_exact_framing_and_marker_reconciliation(self):
        from unittest import mock
        for malformed in (False, True):
            check = wire.Check(1, "M4", "logical", "git_object", b"x" * 16, 0)
            object_id = b"a" * 40
            relay = wire.GitStream(check, {object_id: (b"blob", 3)}, {})
            relay.flow, relay.fd, relay.marker = mock.Mock(), 1, b"CNRYOBJpositive"
            if malformed:
                with self.assertRaises(wire.Stop, msg="M4-size-header"):
                    relay.transform(object_id + b" blob 4\nbody\n")
            else:
                relay.transform(object_id + b" blob 3\nold\n")
                relay.transform(b"")
                self.assertEqual(relay.seen, {object_id}, "M4-objects-accounted")
                relay.scan, relay.ident, relay.parser = mock.Mock(), bytes(16), mock.Mock(searched=1)
                relay.finish()
                self.assertEqual(check.reason, "object_count_mismatch", "M4-scanner-marker-required")

    def test_m5_schema_utf16_overflow_and_uri_names_with_empty_tables(self):
        for encoding in ("UTF-16le", "UTF-16be"):
            host = self.fixture()
            host.prepare()
            value = host.canary()
            for name in ("extensionless", "pct%41", "q?mode=memory&cache=private", "hash#x", "all%25?x#y"):
                path = sqlite_file(host.home / ".claude" / name, [(f"CREATE TABLE \"{value}\"(x TEXT DEFAULT '{'x' * 9000}{value}')", ()),
                    (f"CREATE VIEW v AS SELECT '{value}'", ()),
                    (f"CREATE TRIGGER g AFTER INSERT ON \"{value}\" BEGIN SELECT '{value}'; END", ())], encoding)
                self.assertNotIn(value.encode(), path.read_bytes(), "M5-independent-raw-miss")
            self.assertEqual(host.scan().returncode, 5, "M5-schema-uri-leak")
            self.assertTrue(hits(host) and all(e["mode"] == 5 for e in hits(host)), "M5-logical-only")
            # Every URI-special name opened its own inode: each database family's checks completed.
            self.assertEqual(host.finished()["status"], "complete", "M5-uri-names-complete")
            self.assertEqual(len({e["object"] for e in hits(host)}), 5, "M5-uri-names-each-found")

    def test_m5_wal_only_change_selects_its_main_database(self):
        """The main file is older than the threshold; only its WAL changed. UTF-16 storage keeps the ASCII canary out
        of the raw WAL frames, so only the main database's logical view (M5) can see the committed row."""
        import sqlite3
        host = self.fixture()
        host.worker["fs_magic"] = 0xEF53  # select by change time (ext4) whatever the fixture filesystem is
        host.prepare()
        path = host.home / ".claude" / "state"
        connection = sqlite3.connect(path)
        self.addCleanup(connection.close)
        connection.execute("PRAGMA encoding='UTF-16le'")
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA wal_autocheckpoint=0")
        connection.execute("CREATE TABLE t(v)")
        connection.commit()
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        time.sleep(0.2)
        threshold = time.time_ns()
        time.sleep(0.2)
        connection.execute("INSERT INTO t VALUES (?)", (host.canary(),))
        connection.commit()
        self.assertLess(path.stat().st_ctime_ns, threshold, "M5-main-unchanged")
        self.assertNotIn(host.canary().encode(), Path(str(path) + "-wal").read_bytes(), "M5-raw-wal-miss")
        events = host.events()
        events[0]["threshold_ns"] = threshold
        (host.path / "events.jsonl").write_text("".join(json.dumps(e, sort_keys=True, separators=(",", ":")) + "\n"
                                                        for e in events))
        self.assertEqual(host.scan().returncode, 5, "M5-wal-only-change-selects-main")
        self.assertTrue(any(e["mode"] == 5 for e in hits(host)), "M5-wal-only-change-selects-main")

    def test_m5_actual_main_fd_race_with_the_name_restored(self):
        """While SQLite opens the planned name, its parent directory is swapped for a decoy holding another database,
        then swapped back. The database's own inode is never touched (a rename of the file itself would change its
        ctime), so the held descriptor's tuple, PRAGMA database_list and the pathname stat before and after all
        pass: only the identity of the main descriptor SQLite actually opened catches it (contract 10.8)."""
        host = self.fixture()
        host.prepare()
        value = host.canary()
        database = host.home / ".claude" / "db"
        sqlite_file(database / "sample", [(f'CREATE TABLE "{value}"(x)', ())], "UTF-16le")
        sqlite_file(host.root / "decoy" / "sample", [("CREATE TABLE t(v)", ())])
        hooks = {"before_sqlite_open": {"do": "swap", "target": str(database), "aside": str(host.root / "original"),
                                        "source": str(host.root / "decoy"), "once": str(host.root / "once-swap")},
                 "after_sqlite_open": {"do": "swap", "target": str(database), "aside": str(host.root / "decoy-back"),
                                       "source": str(host.root / "original"), "once": str(host.root / "once-restore")}}
        self.assertEqual(host.scan(dumper={"hooks": hooks}).returncode, 3, "M5-actual-main-fd-race")
        self.assertIn("sqlite_uri_identity", sink_reasons(host), "M5-actual-main-fd-race")

    def test_m5_wal_only_change_overflow_and_virtual_shadow_policy(self):
        import sqlite3
        host = self.fixture()
        host.prepare()
        path = host.home / ".claude" / "state"
        connection = sqlite3.connect(path)
        self.addCleanup(connection.close)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA wal_autocheckpoint=0")
        connection.execute("CREATE TABLE t(v)")
        connection.execute("INSERT INTO t VALUES (?)", ("x" * 6000 + host.canary(),))
        connection.commit()
        self.assertEqual(host.scan().returncode, 5, "M5-uncheckpointed-overflow")
        self.assertTrue(any(e["mode"] == 5 for e in hits(host)), "M5-wal-logical")
        (Path(str(path) + "-shm")).unlink()
        self.assertEqual(host.scan().returncode, 5, "M5-hit-survives-incomplete-wal")
        self.assertEqual(host.finished()["status"], "incomplete", "M5-no-shm-incomplete")
        other = self.fixture()
        db = sqlite_file(other.home / ".claude" / "virtual", [("CREATE VIRTUAL TABLE t USING fts5(v)", ())])
        other.prepare()
        self.assertEqual(other.scan().returncode, 0, "M5-shadow-tables-covered")
        del db

    def test_m5_replaced_main_inode_and_schema_errors_are_incomplete(self):
        host = self.fixture()
        path = sqlite_file(host.home / ".claude" / "sample", [("CREATE TABLE t(v)", ())])
        replacement = sqlite_file(host.root / "replacement", [("CREATE TABLE t(v)", ())])
        host.prepare()
        self.assertEqual(host.scan(dumper={"hooks": {"before_sqlite_open": {"do": "replace", "source": str(replacement),
            "target": str(path), "once": str(host.root / "once")}}}).returncode, 3, "M5-actual-main-identity")
        self.assertIn("sqlite_uri_identity", sink_reasons(host), "M5-inode-mismatch")

    def test_m6_names_targets_paths_newlines_boundary_names_and_negatives(self):
        """M6 alone (no file content holds a canary): a name, a dangling target, a path spanning two components, a
        name after a newline, a key-home boundary name (checked though its content is never opened), and negatives."""
        for case in ("name", "target", "path-spanning", "newline-name", "excluded-boundary-name", "negative"):
            with self.subTest(case=case):
                host = self.fixture()
                host.prepare()
                root, value = host.home / ".claude", host.canary()
                form = next(f for f in cp.forms(value) if "/" not in f and "\\" not in f)
                if case == "name":
                    (root / ("n-" + form)).write_bytes(b"")
                elif case == "target":
                    os.symlink("/nonexistent/" + form, root / "dangling")
                elif case == "path-spanning":
                    first, second = value.split("/")
                    (root / ("p-" + first)).mkdir()
                    (root / ("p-" + first) / (second + "-end")).write_bytes(b"")
                elif case == "newline-name":
                    (root / ("x\n" + form)).write_bytes(b"")
                elif case == "excluded-boundary-name":
                    (root / "sessions").mkdir()
                    (root / "sessions" / (form + ".key")).write_bytes(b"")
                else:  # a partial value (its "/" replaced so it stays one name) is no pattern
                    partial = value.replace("/", "_")[:20]
                    (root / (partial + "-partial")).write_bytes(b"")
                    os.symlink("/nonexistent/" + partial, root / "partial-link")
                expected = 0 if case == "negative" else 5
                self.assertEqual(host.scan().returncode, expected, "M6-" + case)
                self.assertEqual(all(e["mode"] == 6 for e in hits(host)) and len(hits(host)) >= (expected == 5),
                                 True, "M6-" + case + " class")

    def test_m7_environment_value_is_scanned(self):
        host = self.fixture()
        host.constants["USER_SINKS"] = ["U4"]
        host.prepare()
        host.environment.write_text("HARMLESS=" + host.canary() + "\n")
        self.assertEqual(host.scan("final", "--user-run", tty=True).returncode, 5, "M7-full-name-value")


@needs_tools
class ContainmentTests(unittest.TestCase):
    """C2/C3/C5/C6/C7/C8/C9: direct parent-death and ownership; no cgroup claim for the CI exec stub."""

    def blocked(self, kind="rg", real=False):
        host = Host(self, real_scope=real)
        host.constants["AGENT_SINKS"] = ["A11" if kind == "journalctl" else "A1"]
        if kind == "git":
            git_repo(host.home / ".claude/plugins/p", {"file": b"old"})
        elif kind == "gzip":
            import gzip
            (host.home / ".claude/sample").write_bytes(gzip.compress(b"\xff\xfe" + b'x\x00' * 300))
        elif kind == "sqlite":
            sqlite_file(host.home / ".claude/sample", [("CREATE TABLE t(v)", ())])
        else:
            (host.home / ".claude/sample").write_bytes(b"old")
        host.prepare()
        ready = host.root / f"ready-{kind}"
        if kind not in ("worker", "sqlite"):
            blocked_program(host, kind, phase="fsck" if kind == "git" else "--user" if kind == "journalctl" else None,
                            prefix="os.write(1, b'\\xff\\xfe' + b'x\\x00' * 300)" if kind == "gzip" else "")
            FifoTests.repin(self, host, kind)
        else:
            fifo = host.root / "owned-fifo"
            os.mkfifo(fifo)
            target = host.dumper if kind == "sqlite" else host.worker
            target["hooks"]["after_identity" if kind == "sqlite" else "after_prewalk"] = {
                "do": "block", "path": str(fifo), "ready": str(ready)}
        process = host.tool("scan", "--run", host.run_id, "--phase", "baseline", background=True)
        self.addCleanup(self.reap, host, process)
        deadline = time.monotonic() + 30  # the blocked child itself says it is running, then the kill comes
        while not ready.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertTrue(ready.exists(), "C-blocked-child-running " + kind)
        owned = processes_with(str(host.root))
        self.assertGreaterEqual(len(owned), 2, "C-owned-process-started")
        host.scopes = scopes_of(owned)
        self.assertEqual(bool(host.scopes), host.real_scope, "C-scope-observed " + kind)
        return host, process

    def reap(self, host, process):
        # Emergency cleanup signals only this fixture's independently labelled pids.
        for pid in processes_with(str(host.root)):
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        process.communicate(timeout=20)

    def test_c2_coordinator_death_direct_children_for_each_kind(self):
        for kind in ("rg", "gzip", "git", "journalctl", "sqlite", "worker"):
            with self.subTest(kind=kind):
                host, process = self.blocked(kind)
                process.kill()
                process.communicate(timeout=20)
                self.assertEqual(wait_gone(str(host.root), 20), [], "C2-direct-parent-death " + kind)
                self.assertEqual(wait_scopes_gone(host.scopes, 20), [], "C1-scope-gone " + kind)
                self.assertIn("baseline_unfinished", host.verdict()[2], "C2-unfinished " + kind)

    def test_c3_worker_death_direct_scanner_and_decoder(self):
        host, process = self.blocked("gzip")
        candidates = []
        for pid in processes_with(str(host.root)):
            with open(f"/proc/{pid}/cmdline", "rb") as handle:
                args = handle.read().split(b"\0")
            # The worker itself: a python3 whose arguments hold "worker". The real runner's bash carries the same
            # arguments after its own name, and killing it instead would leave the worker running.
            if args[0].endswith(b"python3") and b"worker" in args:
                candidates.append(pid)
        self.assertTrue(candidates, "C3-worker-observed")
        os.kill(candidates[0], signal.SIGKILL)
        process.communicate(timeout=20)
        self.assertEqual(wait_gone(str(host.root), 20), [], "C3-direct-children-gone")
        self.assertEqual(wait_scopes_gone(host.scopes, 20), [], "C3-scope-gone")
        self.assertNotEqual(host.verdict()[1], "clean", "C3-incomplete")

    def test_c5_handled_signals_and_exception_reap_children(self):
        for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP, signal.SIGQUIT):
            host, process = self.blocked()
            process.send_signal(signum)
            process.communicate(timeout=20)
            self.assertEqual(wait_gone(str(host.root), 20), [], "C5-signal-cleanup")
            self.assertNotEqual(host.verdict()[1], "clean", "C5-incomplete")

    def test_c6_exited_group_leader_keeps_descendant_ownership(self):
        from unittest import mock
        host = Host(self)
        script = host.root / "forker.py"
        script.write_text("import os, time\nif os.fork() == 0:\n    os.close(0); os.close(1); os.close(2); time.sleep(60)\n")
        scan = type("Scan", (), {"setpriv": REAL["setpriv"], "child_env": host.env()})()
        child = wire.Child(scan, [PYTHON, "-I", str(script)], subprocess.DEVNULL, subprocess.DEVNULL, subprocess.DEVNULL)
        deadline = time.monotonic() + 5
        while not child.command.exited() and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertTrue(child.command.exited(), "C6-leader-exited")
        self.assertTrue(processes_with(str(host.root)), "C6-descendant-alive-before-cleanup")
        child.finish(time.monotonic() + 3)
        self.assertEqual(wait_gone(str(host.root), 5), [], "C6-descendant-reaped")
        with mock.patch.object(runner.os, "killpg") as kill:
            runner.end_group(child.command)
            kill.assert_not_called()  # The already reaped group must never be signalled again.

    def test_c7_launch_prefix_core_limit_and_inherited_fds(self):
        exes = {name: ["/usr/bin/" + name, "0" * 64] for name in cp.EXECUTABLES}
        argv = cp.launch_argv(exes)
        self.assertEqual(argv[:4], ["/usr/bin/setpriv", "--pdeathsig", "TERM", "--"], "C7-pdeath-launch")
        self.assertIn("-I", argv, "C7-isolation")
        self.assertIn("-S", argv, "C7-no-site")
        self.assertIn(str(cp.RUNNER), argv, "C7-supported-runner")
        host = Host(self)
        record = host.root / "core"
        wrapper(host, "rg", prefix=f"import resource\nopen({str(record)!r}, 'a').write(str(resource.getrlimit(resource.RLIMIT_CORE)[0]) + '\\n')")
        (host.home / ".claude/sample").write_bytes(b"old")
        host.prepare()
        self.assertEqual(host.scan().returncode, 0)
        self.assertEqual(set(record.read_text().splitlines()), {"0"}, "C7-core-zero-inherited")

    def test_c8_bootstrap_missing_handshake_and_core_collectors(self):
        from unittest import mock
        host = Host(self)
        host.prepare()
        stub = host.bin / "stub-runner"
        stub.write_text("#!/bin/sh\nexit 78\n")
        self.assertEqual(host.scan().returncode, 3, "C8-bootstrap-refusal")
        self.assertIn("containment_unavailable", host.finished()["reasons"], "C8-enum-only")
        for pattern in (b"|collector", b"@socket"):
            file = host.root / "core-pattern"
            file.write_bytes(pattern)
            with mock.patch.object(runner, "CORE_PATTERN_FILE", str(file)):
                with self.assertRaises(runner.Refused, msg="C8-core-collector-refused"):
                    cp.runner.disable_core_dumps()

    def test_c8_prepare_scan_and_arm_refuse_a_core_collector(self):
        """The tool itself calls the runner's check before prepare, any scan request and arm (contract 11)."""
        host = Host(self)
        pattern = host.root / "core-pattern"
        pattern.write_bytes(b"|/usr/lib/synthetic-collector %p\n")
        self.assertEqual(host.tool("prepare", core_pattern=pattern).returncode, 1, "C8-prepare-core-collector")
        host.prepare()
        count = len(host.events())
        self.assertEqual(host.tool("scan", "--run", host.run_id, "--phase", "baseline", core_pattern=pattern)
                         .returncode, 1, "C8-scan-core-collector")
        self.assertEqual(len(host.events()), count, "C8-scan-core-collector admits no request")
        self.assertEqual(host.scan("baseline").returncode, 0)
        self.assertEqual(host.tool("arm", "--run", host.run_id, "subagent", core_pattern=pattern).returncode, 1,
                         "C8-arm-core-collector")


@needs_scope
class ContainmentRealScopeTests(ContainmentTests):
    """C1/C3/C4/C7/C9: workstation-only manager, backstop and setsid-descendant acceptance."""

    def blocked(self, kind="rg", real=True):
        return super().blocked(kind, True)

    def test_complete_end_stops_scope_with_detached_descendant(self):
        host = Host(self, real_scope=True)
        host.constants["AGENT_SINKS"] = ["A1"]
        host.prepare()
        ready, release = host.root / "descendant-ready", host.root / "release"
        process = host.scan(background=True, worker={"hooks": {"after_prewalk": {"do": "fork-descendant",
            "ready": str(ready), "release": str(release)}}})
        self.addCleanup(self.reap, host, process)
        deadline = time.monotonic() + 20
        while not ready.exists() and time.monotonic() < deadline:
            time.sleep(.02)
        self.assertTrue(ready.exists(), "REPAIR-NATIVE-descendant-observed")
        scopes = scopes_of([int(ready.read_text())])
        self.assertTrue(scopes, "REPAIR-NATIVE-scope-observed")
        release.touch()
        process.communicate(timeout=30)
        self.assertEqual(process.returncode, 0, "REPAIR-NATIVE-completion")
        self.assertEqual(wait_scopes_gone(scopes, 3), [], "REPAIR-NATIVE-scope-removed")
        self.assertEqual(wait_gone(str(host.root), 3), [], "REPAIR-NATIVE-descendants-gone")

    def test_c9_real_runner_run_state_stays_in_the_planned_runtime(self):
        """Inside the real scope XDG_RUNTIME_DIR is /run/user/$UID (the runner exports it); every run and scan path
        comes from the plan, so no run or lock of this tool appears there (the runner keeps its own state)."""
        runtime = Path(f"/run/user/{os.getuid()}")
        before = set(os.listdir(runtime))
        host = Host(self, real_scope=True)
        (host.home / ".claude/sample").write_text("old")
        host.prepare()
        self.assertEqual(host.scan().returncode, 0, "C9-real-runner-scan")
        created = set(os.listdir(runtime)) - before
        self.assertFalse({"native-agent-stack", "ecosystem-canary-proof.lock"} & created, "C9-run-user-untouched")
        self.assertFalse((runtime / "native-agent-stack" / "canary-proof" / host.run_id).exists(),
                         "C9-run-user-untouched")
        self.assertTrue((host.path / "child-cursor").is_file() and (host.path / "events.jsonl").is_file(),
                        "C9-planned-runtime")

    def test_c4_backstop_reaches_a_child_started_after_both_deaths(self):
        """The coordinator and runner die while the worker pauses just before it starts rg (before that child's
        parent-death signal is armed): the finite scope, not a parent, must end the TERM-ignoring child."""
        host = Host(self, real_scope=True)
        host.constants["SCOPE_SECONDS"] = {**{sink: 15 for sink in wire.SINKS}, "setup": 120}
        host.worker["constants"]["BUDGET_CAP"] = 120.0  # the worker's own deadline cannot be what ends it
        (host.home / ".claude/sample").write_text("old")
        host.prepare()
        wrapper(host, "rg", prefix="import signal, time\nsignal.signal(signal.SIGTERM, signal.SIG_IGN)\ntime.sleep(60)")
        FifoTests.repin(self, host, "rg")
        host.worker["hooks"]["before_child"] = {"do": "sleep", "seconds": 3, "when": "bin/rg"}
        process = host.tool("scan", "--run", host.run_id, "--phase", "baseline", background=True)
        self.addCleanup(self.reap, host, process)
        time.sleep(1.5)
        owned = processes_with(str(host.root))
        scopes = scopes_of(owned)
        self.assertTrue(scopes, "C4-scope-observed")
        process.kill()
        for pid in owned:
            with open(f"/proc/{pid}/cmdline", "rb") as handle:
                if b"ecosystem-bounded-run" in handle.read():
                    os.kill(pid, signal.SIGKILL)
        process.communicate(timeout=20)
        self.assertEqual(wait_gone(str(host.root), 30), [], "C4-before-pdeath-arming-backstop")
        self.assertEqual(wait_scopes_gone(scopes, 30), [], "C4-before-pdeath-arming-scope-gone")

    def test_c7_every_scan_side_child_runs_inside_the_enforced_finite_scope(self):
        """Each rg the worker starts records its own cgroup and limits: an ecosystem-job scope with the runner's
        memory.max (6 GiB), pids.max (256) and cpu.max (200% of one CPU) actually in force (contract 11, C7)."""
        host = Host(self, real_scope=True)
        (host.home / ".claude/sample").write_text("old")
        host.prepare()
        record = host.root / "limits"
        wrapper(host, "rg", prefix=(
            "group = [line for line in open('/proc/self/cgroup') if line.startswith('0::/')][0][3:].strip()\n"
            "limits = [open('/sys/fs/cgroup' + group + '/' + name).read().strip() for name in "
            "('memory.max', 'pids.max', 'cpu.max')]\n"
            f"open({str(record)!r}, 'a').write('|'.join([group] + limits) + '\\n')"))
        FifoTests.repin(self, host, "rg")
        self.assertEqual(host.scan().returncode, 0, "C7-real-scope-scan")
        rows = {tuple(line.split("|")) for line in record.read_text().splitlines()}
        self.assertTrue(rows, "C7-children-observed")
        for group, memory, pids, cpu in rows:
            self.assertTrue(re.search(r"/ecosystem-job-\d+-\d+-\d+\.scope$", group), "C7-inside-scope")
            self.assertEqual((memory, pids, cpu), (str(6 << 30), "256", "200000 100000"), "C7-enforced-limits")

    def test_c4_simultaneous_coordinator_runner_death_and_setsid_backstop(self):
        host = Host(self, real_scope=True)
        host.constants["SCOPE_SECONDS"] = {**{sink: 15 for sink in wire.SINKS}, "setup": 120}
        host.worker["constants"]["BUDGET_CAP"] = 120.0  # the worker's own deadline cannot be what ends it
        (host.home / ".claude/sample").write_text("old")
        host.prepare()
        wrapper(host, "rg", prefix="import signal, time\nif os.fork() == 0:\n    os.setsid(); signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(60)\ntime.sleep(60)")
        FifoTests.repin(self, host, "rg")
        process = host.tool("scan", "--run", host.run_id, "--phase", "baseline", background=True)
        self.addCleanup(self.reap, host, process)
        time.sleep(2)
        owned = processes_with(str(host.root))
        scopes = scopes_of(owned)
        self.assertTrue(scopes, "C4-scope-observed")
        process.kill()
        for pid in owned:
            with open(f"/proc/{pid}/cmdline", "rb") as handle:
                if b"ecosystem-bounded-run" in handle.read():
                    os.kill(pid, signal.SIGKILL)
        process.communicate(timeout=20)
        self.assertEqual(wait_gone(str(host.root), 30), [], "C4-scope-backstop-kernel-observer")
        self.assertEqual(wait_scopes_gone(scopes, 30), [], "C4-scope-gone")


@needs_tools
class CommandTests(unittest.TestCase):
    """C2/C8/C9/C11 and S3–S8 templates: syntax, guard decisions and discarded consumer outputs."""

    def test_cli_exact_spellings_and_tty_guards(self):
        parser = cp.parser()
        for option in ("--user", "--user-r", "--pha"):
            with self.assertRaises(SystemExit, msg="CMD-abbreviation-refused"):
                parser.parse_args(["scan", "--run", "cp-20260930t120000z-abcdef", "--phase", "final", option])
        self.assertEqual(parser.parse_args(["scan", "--run", "x", "--phase=comparison", "--user-run"]).phase,
                         "comparison", "CMD-equals-phase")
        host = Host(self)
        host.prepare()
        self.assertEqual(host.scan("final", "--user-run").returncode, 1, "CMD-TTY-required")
        self.assertEqual(host.scan("final", "--user-run", tty=True, env=host.env(CLAUDECODE="1")).returncode, 1,
                         "CMD-no-agent-user-run")
        self.assertEqual(host.scan("baseline", "--user-run", tty=True).returncode, 1, "CMD-baseline-agent-only")

    def test_c11_scan_output_is_printed_only_after_every_sink_finished(self):
        host = Host(self)
        host.constants["AGENT_SINKS"] = ["A1", "A2", "A3"]
        host.prepare()
        sizes, out = host.root / "sizes", host.root / "stdout"
        result = host.tool("scan", "--run", host.run_id, "--phase", "baseline", stdout_to=out,
                           hooks={"between_sinks": {"do": "stdout-size", "path": str(sizes)}})
        self.assertEqual(result.returncode, 0, "C11-scan")
        self.assertEqual(sizes.read_text().split(), ["0", "0", "0"], "C11-output-after-all-sinks")
        lines = out.read_text().splitlines()
        self.assertEqual([line.split(":", 1)[0] for line in lines], ["A1", "A2", "A3", "not_covered"],
                         "C11-one-line-per-sink-and-coverage")

    def test_k4_deny_spellings_if_rule_installed(self):
        sys.path.insert(0, str(ROOT / "scripts/hooks"))
        import secret_path_guard as guard
        stem = "python3 tools/credentials/canary_proof.py scan --run cp-20260930t120000z-abcdef "
        commands = [stem + "--phase final --user-run", stem + "--phase comparison", stem + "--phase=comparison"]
        if all(guard.check(command) is None for command in commands):
            self.skipTest("guard deny rule not present (K4 item 14)")
        for command in commands:
            self.assertIsNotNone(guard.check(command), "CMD-K4-denial")

    def test_emitted_probe_workflow_and_consumer_templates_pass_guard(self):
        sys.path.insert(0, str(ROOT / "scripts/hooks"))
        import secret_path_guard as guard
        run = "cp-20260930t120000z-abcdef"
        for consumer in cp.CONSUMERS:
            import shlex
            probe_command = (f"{PYTHON} -I {shlex.quote(str(ROOT / 'tools/credentials/credential_run.py'))} canary-e2e -- "
                             f"{PYTHON} -I {shlex.quote(str(ROOT / 'tools/credentials/canary_probe.py'))} "
                             f"--run {run} --consumer {consumer} --attempt 1")
            commands = [probe_command, f"python3 tools/credentials/canary_proof.py arm --run {run} {consumer}"]
            if consumer == "systemd-user-unit":
                commands += [f"systemd-run --user --wait --collect --quiet -p Type=oneshot --unit=canary-proof-{run}-unit-1 " + probe_command + " --leak-check"]
            for command in commands:
                self.assertIsNone(guard.check(command), "CMD-allowed-template " + consumer)
                self.assertNotIn(cp.VARIABLE, command, "CMD-id-only")
        self.assertIsNone(guard.check(f"bash tools/credentials/canary_lane_consumer.sh {run} 1 /tmp/registered-lane </dev/null >/dev/null 2>&1"), "CMD-S8-allowed")
        workflow = (ROOT / "tools/credentials/canary_workflow.js").read_text()
        self.assertEqual(workflow.count("effort: 'max'"), 2, "CMD-workflow-effort")
        self.assertEqual(workflow.count("agentType: 'source-scout'"), 2, "CMD-workflow-role")

    def test_lane_wrapper_argv_home_and_null_descriptors_using_fake_client(self):
        host = Host(self)
        record, lane = host.root / "client-argv", host.root / "lane"
        lane.mkdir()
        host.script("codex", "#!/usr/bin/python3 -I\nimport os, sys, json\n" +
            f"json.dump(dict(argv=sys.argv[1:], home=os.environ['CODEX_HOME'], fds=[os.readlink('/proc/self/fd/' + str(n)) for n in range(3)]), open({str(record)!r}, 'w'))\n")
        result = subprocess.run(["bash", str(ROOT / "tools/credentials/canary_lane_consumer.sh"),
            "cp-20260930t120000z-abcdef", "1", str(lane)], env=host.env(PATH=f"{host.bin}:/usr/bin:/bin"),
            stdin=subprocess.DEVNULL, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, "CMD-wrapper")
        data = json.loads(record.read_text())
        self.assertEqual(data["home"], str(lane), "CMD-registered-home")
        self.assertEqual(data["fds"], ["/dev/null"] * 3, "CMD-null-input-and-output")
        self.assertIn('model_reasoning_effort="max"', data["argv"], "CMD-literal-TOML")
        self.assertNotIn("-o", data["argv"], "CMD-no-capture")
        self.assertIn("cx/gpt-6-astra", data["argv"], "CMD-S8-model")

    def test_setup_guard_pin_stays_child_side_and_runtime_comes_from_plan(self):
        host = Host(self)
        sentinel_value = sentinel("unrelated-")
        (host.home / ".claude/settings.json").write_text(sentinel_value)
        (host.codex / "config.toml").write_text(sentinel_value)
        audit = host.root / "setup-audit"
        result = host.tool("prepare", audit=audit)
        self.assertEqual(result.returncode, 0, "CMD-guard-setup")
        self.assertFalse(forms_in(audit.read_bytes(), sentinel_value), "C8-no-parent-configuration-read")
        self.assertFalse(any(path.name == "client_guards" for path in host.root.rglob("*")), "C8-only-guard-pin")
        host.run_id = re.search(rb"run: (cp-\S+)", result.stdout).group(1).decode()
        host.worker["wrong_runtime"] = str(host.root / "wrong-runtime")
        (host.home / ".claude/sample").write_text("old")
        self.assertEqual(host.scan().returncode, 0, "C9-paths-from-plan")
        self.assertFalse((host.root / "wrong-runtime").exists(), "C9-no-environment-derived-state")

    def test_documented_and_workflow_commands_pass_the_guard_and_name_no_variable(self):
        """Every command in the Canary proof section's command blocks and every command the workflow's stages run is
        an allowed agent command and names no secret variable; the user-run pair waits for K4 (C2)."""
        sys.path.insert(0, str(ROOT / "scripts/hooks"))
        import secret_path_guard as guard
        section = (ROOT / "docs/secret-storage.md").read_text().split("\n## Canary proof\n", 1)[1].split("\n## ", 1)[0]
        commands = [line for block in re.findall(r"```sh\n(.*?)```", section, re.S) for line in block.splitlines()
                    if line.strip()]
        workflow = (ROOT / "tools/credentials/canary_workflow.js").read_text()
        commands += re.findall(r"python3 -I tools/credentials/credential_run\.py canary-e2e --check", workflow)
        self.assertGreaterEqual(len(commands), 12, "CMD-docs-commands-found")
        for command in commands:
            self.assertNotIn(cp.VARIABLE, command, "CMD-docs-id-only")
            if "--user-run" not in command:
                self.assertIsNone(guard.check(command), "CMD-docs-allowed " + command)


@needs_tools
class RepairTests(unittest.TestCase):
    """Permanent regressions for the two independent v2 reviews; all inputs are synthetic."""

    def host(self, sink="A1"):
        host = Host(self)
        host.constants["AGENT_SINKS"] = [sink]
        host.prepare()
        return host

    def test_incomplete_end_never_becomes_complete(self):
        for changes in ({"status": 2}, {"aux": 1}, {"observed": 1}, {"expected": 1}):
            session = cp.Session(None, {"controls": None}, "A1", 5)
            session.completed[0] = wire.unpack(wire.pack(kind=wire.RESULT, status=1))
            session.end = wire.unpack(wire.pack(kind=wire.END, **{"status": 1, **changes}))
            self.assertEqual(session.outcome()["status"], "incomplete", "REPAIR-END-rejected")

    def test_discovered_git_indirections_and_damaged_stores(self):
        for kind in ("gitfile", "missing-head", "missing-refs", "gitfile-damaged-both"):
            with self.subTest(kind=kind):
                host = self.host()
                repo_path = (host.root / "outside") if kind == "gitfile" else host.home / ".claude/p"
                repo = git_repo(repo_path, {"file": host.canary().encode()}, pack=kind == "gitfile")
                (repo_path / "file").unlink()  # only compressed Git objects retain the canary
                if kind == "gitfile":
                    inside = host.home / ".claude/worktree"
                    inside.mkdir()
                    (inside / ".git").write_text("gitdir: " + str(repo) + "\n")
                elif kind == "missing-head":
                    (repo / "HEAD").unlink()
                elif kind == "missing-refs":
                    shutil.rmtree(repo / "refs")
                else:
                    renamed = repo_path / "broken-store"
                    repo.rename(renamed)
                    (renamed / "HEAD").unlink(); shutil.rmtree(renamed / "refs")
                    (repo_path / ".git").write_text("gitdir: broken-store\n")
                result = host.scan()
                self.assertNotEqual(result.returncode, 0, "REPAIR-GIT-no-false-clean")
                self.assertEqual(host.finished()["status"], "incomplete", "REPAIR-GIT-incomplete")

    def test_wal_requires_a_valid_scanned_sqlite_main(self):
        for kind in ("plain", "directory", "symlink", "missing"):
            with self.subTest(kind=kind):
                host = self.host()
                main = host.home / ".claude/family"
                if kind == "plain":
                    main.write_text("not SQLite")
                elif kind == "directory":
                    main.mkdir()
                elif kind == "symlink":
                    os.symlink("/nonexistent", main)
                main.with_name("family-wal").write_bytes(b"\x37\x7f\x06\x82" + host.canary().encode("utf-16-le"))
                main.with_name("family-shm").write_bytes(b"synthetic")
                self.assertEqual(host.scan().returncode, 3, "REPAIR-WAL-invalid-main")
                self.assertIn("sqlite_uri_identity", sink_reasons(host), "REPAIR-WAL-logical-required")

    def test_symlink_to_unselected_tasks_file_is_not_covered(self):
        host = self.host()
        host.constants["AGENT_SINKS"] = ["A1", "A10"]
        target = host.root / "tasks/unscanned.txt"
        target.write_text(host.canary())
        os.symlink(target, host.home / ".claude/link")
        self.assertEqual(host.scan().returncode, 3, "REPAIR-LINK-selection")
        self.assertIn("link_out", sink_reasons(host), "REPAIR-LINK-out")

    def test_journal_cursor_substitution_is_rejected(self):
        host = self.host("A11")
        original = (host.path / "child-cursor").read_bytes()
        host.journal_add(host.canary().encode())
        host.journal_add((host.path / "anchor").read_bytes().strip())
        last = dict(json.loads(host.journal.read_text())[-1])["__CURSOR"]
        (host.path / "child-cursor").write_text(last + "\n")
        self.assertEqual(host.scan().returncode, 3, "REPAIR-CURSOR-bound")
        self.assertIn("journal_cursor_missing", sink_reasons(host, "A11"))
        (host.path / "child-cursor").write_bytes(original)
        self.assertEqual(host.scan().returncode, 5, "REPAIR-CURSOR-original-observes-leak")

    def test_journal_unterminated_final_entry_is_rejected(self):
        host = self.host("A11")
        host.journal_add(b"ordinary final entry")
        script = host.bin / "journalctl"
        code = script.read_text().replace('out = sys.stdout.buffer', 'import io\nout = io.BytesIO()')
        script.write_text(code + '\nsys.stdout.buffer.write(out.getvalue()[:-1])\n')
        FifoTests.repin(self, host, "journalctl")
        self.assertEqual(host.scan().returncode, 3, "REPAIR-JOURNAL-final-separator")
        self.assertIn("unparseable_output", sink_reasons(host, "A11"))

    def test_virtual_table_shadow_ownership_is_exact(self):
        host = self.host()
        sqlite_file(host.home / ".claude/state", [("CREATE VIRTUAL TABLE a USING dbstat", ()),
                                                   ("CREATE VIRTUAL TABLE a_b USING fts5(v)", ())])
        self.assertEqual(host.scan().returncode, 3, "REPAIR-SHADOW-owner")
        self.assertIn("sqlite_table_error", sink_reasons(host))

    def test_runner_cleanup_preserves_leader_and_stops_after_end(self):
        for exited in (True, False):
            host = Host(self)
            pidfile = host.root / "descendant"
            code = ("import os,time,sys,signal\nchild=os.fork()\n"
                    "if child == 0:\n signal.signal(signal.SIGTERM,signal.SIG_IGN)\n"
                    " open(sys.argv[1],'w').write(str(os.getpid()))\n time.sleep(300);sys.exit(0)\n"
                    "while not os.path.exists(sys.argv[1]): time.sleep(.01)\n" +
                    ("os._exit(0)\n" if exited else "time.sleep(300)\n"))
            process = subprocess.Popen([PYTHON, "-I", "-c", code, str(pidfile)], start_new_session=True)
            self.addCleanup(lambda p=process: p.poll() is None and p.kill())
            deadline = time.monotonic() + 5
            while not pidfile.exists() and time.monotonic() < deadline:
                time.sleep(.02)
            self.assertTrue(pidfile.exists())
            descendant = int(pidfile.read_text())
            def reap_fixture():
                try: os.kill(descendant, signal.SIGKILL)
                except ProcessLookupError: pass
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=5)
            self.addCleanup(reap_fixture)
            if exited:
                os.waitid(os.P_PID, process.pid, os.WEXITED | os.WNOWAIT)
            session = cp.Session(None, {}, "A1", 5)
            session.process = process
            session.end = wire.unpack(wire.pack(kind=wire.END, status=1))
            session.stop()
            self.assertEqual(wait_gone(str(host.root), 3), [], "REPAIR-CLEANUP-descendants")

    def test_scope_stop_failure_cannot_complete(self):
        from unittest import mock
        import itertools
        for populated in (True, False):
            session = cp.Session(None, {}, "A1", 5)
            session.process = object(); session.scope = Path("/synthetic-scope")
            session.completed[0] = wire.unpack(wire.pack(kind=wire.RESULT, status=1))
            session.end = wire.unpack(wire.pack(kind=wire.END, status=1))
            command = mock.Mock()
            command.exited.return_value = command.signal_group.return_value = True
            command.reap.return_value = 143
            with mock.patch.object(cp.runner, "Command", return_value=command), mock.patch.object(cp.runner, "end_group"), \
                    mock.patch.object(cp, "SCOPE_REQUIRED", True), \
                    mock.patch.object(cp.time, "monotonic", side_effect=itertools.count(0, 20)), \
                    mock.patch.object(session, "scope_populated", return_value=populated):
                session.stop()
            self.assertEqual(session.outcome()["status"], "incomplete" if populated else "complete",
                             "REPAIR-SCOPE-survivor-refuses")

    def test_terminal_release_after_stop_signal(self):
        from unittest import mock
        host = Host(self)
        ack_r, ack_w = os.pipe()
        ready = host.root / "terminal-ready"
        process = subprocess.Popen([PYTHON, "-I", "-c",
            "import os, signal, sys; signal.signal(signal.SIGTERM, signal.SIG_IGN); "
            "open(sys.argv[2], 'w').close(); os.read(int(sys.argv[1]), 1)", str(ack_r), str(ready)],
            pass_fds=(ack_r,), start_new_session=True)
        os.close(ack_r)
        self.addCleanup(ContainmentTests.reap, self, host, process)
        deadline = time.monotonic() + 5
        while not ready.exists() and time.monotonic() < deadline:
            time.sleep(.02)
        self.assertTrue(ready.exists())
        session = cp.Session(None, {}, "A1", 5)
        session.process = process
        session.end = wire.unpack(wire.pack(kind=wire.END, status=wire.STATUS["complete"]))
        try:
            with mock.patch.object(cp, "SCOPE_REQUIRED", False):
                session.stop(ack_w)
            self.assertEqual(session.reasons, [], "REPAIR-TERMINAL-release")
            self.assertEqual(process.returncode, 0, "REPAIR-TERMINAL-exit")
        finally:
            with cp._suppress(OSError):
                os.close(ack_w)

    def test_inherited_sigchld_ignore_preserves_waitable_children(self):
        code = r'''
import json, os, signal, subprocess, sys
from types import SimpleNamespace
sys.path[:0] = [sys.argv[1] + '/tools/credentials', sys.argv[1] + '/scripts']
import canary_proof as cp
import canary_scan_worker as w
signal.signal(signal.SIGCHLD, signal.SIG_IGN)
checks = []
def observe(process):
    try:
        first = os.waitid(os.P_PID, process.pid, os.WEXITED | os.WNOWAIT)
        second = os.waitid(os.P_PID, process.pid, os.WEXITED | os.WNOWAIT)
        checks.append(first.si_status == second.si_status == 7)
    except ChildProcessError:
        checks.append(False)
argv = ['/usr/bin/python3', '-I', '-c', 'raise SystemExit(7)']
if sys.argv[2] == 'runner':
    cp.SCOPE_REQUIRED = False
    cp.launch_argv = lambda exes: argv
    run = SimpleNamespace(key=bytes(32), env={}, runtime=sys.argv[3])
    session = cp.Session(run, {'exes': {}}, 'setup', 5)
    session.read_records = lambda *fds: observe(session.process)
    session.run_worker()
    checks.append(session.process.returncode == 7)
else:
    scan = SimpleNamespace(setpriv=sys.argv[4], child_env={'PATH': '/usr/bin:/bin'})
    child = w.Child(scan, argv, subprocess.DEVNULL, subprocess.DEVNULL, subprocess.DEVNULL)
    observe(child.process)
    child.stop()
    checks.append(child.process.returncode == 7)
print(json.dumps(checks))
'''
        host = Host(self)
        for kind in ("runner", "helper"):
            with self.subTest(kind=kind):
                result = subprocess.run([PYTHON, "-I", "-c", code, str(ROOT), kind, str(host.root), REAL["setpriv"]],
                                        capture_output=True, timeout=20)
                self.assertEqual(result.returncode, 0, "REPAIR-SIGCHLD-execution")
                self.assertEqual(json.loads(result.stdout), [True, True], "REPAIR-SIGCHLD-pinned " + kind)

    def test_a12_is_primary_home_checkout_and_deduplicated(self):
        from unittest import mock
        host = Host(self)
        with mock.patch.object(cp, "ROOT", host.home / "code/native-agent-stack-live"):
            roots = cp.sink_roots(str(host.home), os.getuid(), [], "cursor")
        self.assertEqual(roots["A12"][1][1], str(host.home / "code/native-agent-stack"), "REPAIR-A12-primary")
        host.constants["PRIMARY_CHECKOUT"] = str(host.home / "code/native-agent-stack-live")
        host.constants["AGENT_SINKS"] = ["A12"]
        host.prepare()
        self.assertEqual(host.scan().returncode, 0, "REPAIR-A12-deduplicate")
        self.assertNotEqual(host.tool("status", "--run", host.run_id).returncode, 4, "REPAIR-A12-record-valid")

    def test_partial_record_preserves_durable_hit_count(self):
        host = self.host()
        (host.home / ".claude/leak").write_text(host.canary())
        self.assertEqual(host.scan().returncode, 5)
        count = sum(e["count"] for e in hits(host))
        with open(host.path / "events.jsonl", "ab") as out:
            out.write(b"{")
        result = host.tool("status", "--run", host.run_id)
        self.assertEqual(result.returncode, 4, "REPAIR-PARTIAL-invalid")
        self.assertIn(f"hits={count}".encode(), result.stdout, "REPAIR-PARTIAL-durable-count")

    def test_bound_pointer_stays_excluded_when_variable_unset(self):
        host = Host(self)
        host.constants["AGENT_SINKS"] = ["A1"]
        target = host.home / ".claude/bound-secret"
        target.write_text("synthetic unrelated value")
        result = host.tool("prepare", env=host.env(ENV_FILE=str(target)))
        self.assertEqual(result.returncode, 0)
        host.run_id = re.search(rb"run: (cp-\S+)", result.stdout)[1].decode()
        self.assertEqual(host.scan(worker={"forbid_paths": [str(target)]}).returncode, 0, "REPAIR-POINTER-unset")
        self.assertEqual(host.finished()["sinks"]["A1"]["counters"]["excluded_key"], 1)

    def test_rg15_grammar_and_empty_file_accounting(self):
        for version, tail in ((14001000, b"seconds"), (15002000, b"seconds total")):
            for files in (1, 3, 8):
                stats = (b"\n0 matches\n0 matched lines\n0 files contained matches\n" + str(files).encode()
                         + b" files searched\n0 bytes printed\n0 bytes searched\n0.0 seconds spent searching\n0.0 "
                         + tail + b"\n")
                scan = type("Scan", (), {"plan": {"rg_version": version}})()
                for actual, expected in ((files, "ok"), (files + 1, "files_searched_mismatch")):
                    check = wire.Check(1, "M1", "raw", "other", bytes(16), 0)
                    parser = wire.RgOutput(scan, check, {})
                    parser.feed(stats)
                    parser.close(actual)
                    self.assertEqual(check.reason, expected, "REPAIR-RG15-empty-accounting")
                check = wire.Check(1, "M1", "raw", "other", bytes(16), 0)
                parser = wire.RgOutput(scan, check, {})
                parser.feed(stats.replace(tail + b"\n", b"wrong terminator\n"))
                parser.close(files)
                self.assertEqual(check.reason, "unparseable_output", "REPAIR-RG15-grammar")

    def test_equal_count_replacement_and_unselected_retry(self):
        host = self.host()
        target = host.home / ".claude/sample"
        target.write_text("old")
        before = len(list(target.parent.iterdir()))
        moved = target.parent / next(v for v in cp.forms(host.canary()) if "/" not in v)
        result = host.scan(worker={"hooks": {"before_postwalk": {"do": "replace", "source": str(target),
            "target": str(moved), "once": str(host.root / "once")}}})
        self.assertEqual(len(list(target.parent.iterdir())), before, "REPAIR-S4-equal-count")
        self.assertEqual(result.returncode, 5, "REPAIR-S4-retry-hit")
        self.assertEqual(host.finished()["sinks"]["A1"]["subpass"], 1, "REPAIR-S4-retry")
        other = Host(self)
        other.constants.update(AGENT_SINKS=["A1"], MARGIN_NS=0)
        old = other.home / ".claude/old"
        old.write_text("old")
        other.prepare()
        self.assertLess(old.stat().st_ctime_ns, other.events()[0]["threshold_ns"])
        (old.parent / "trigger").write_text("new")
        result = other.scan(worker={"fs_magic": 0xEF53, "hooks": {"after_file_scan": {"do": "write",
            "target": str(old), "data": other.canary().encode().hex(), "when": "trigger", "once": str(other.root / "once")}}})
        self.assertEqual(result.returncode, 5, "REPAIR-S8-new-selection")
        self.assertTrue(any(e["subpass"] == 1 and e["mode"] == 1 for e in hits(other)), "REPAIR-S8-retry-content")

    def test_st5_removal_link_parent_pack_wal_shm_changes(self):
        import sqlite3
        for kind in ("remove", "link", "parent", "pack", "wal", "shm"):
            with self.subTest(kind=kind):
                host = self.host()
                top = host.home / ".claude"
                path = top / "sample"
                path.write_text("old")
                hook = {"do": "remove", "target": str(path)}
                if kind == "link":
                    path.unlink(); os.symlink("/nonexistent/old", path)
                    hook = {"do": "symlink", "target": str(path), "source": "/nonexistent/new"}
                elif kind == "parent":
                    path.unlink(); path.mkdir(); (path / "f").write_text("old")
                    replacement = host.root / "replacement"; replacement.mkdir(); (replacement / "f").write_text("new")
                    hook = {"do": "swap", "target": str(path), "source": str(replacement), "aside": str(host.root / "aside")}
                elif kind == "pack":
                    repo = git_repo(top / "repo", {"f": b"old"})
                    pack = next(repo.glob("objects/pack/*.pack"))
                    saved = host.root / "saved.pack"; pack.replace(saved)
                    hook = {"do": "replace", "source": str(saved), "target": str(pack)}
                elif kind in ("wal", "shm"):
                    db = top / "db"
                    connection = sqlite3.connect(db)
                    connection.execute("PRAGMA journal_mode=WAL"); connection.execute("CREATE TABLE t(v)")
                    connection.commit(); self.addCleanup(connection.close)
                    side = Path(str(db) + "-" + kind)
                    saved = host.root / ("saved-" + kind); side.replace(saved)
                    hook = {"do": "replace", "source": str(saved), "target": str(side)}
                hook["once"] = str(host.root / "once")
                result = host.scan(worker={"hooks": {"after_prewalk": hook}})
                self.assertIn(result.returncode, (0, 3), "REPAIR-S5-fixed-scope")
                inventories = [e for e in host.events() if e["event"] == "scan_inventory"]
                if len(inventories) == 1:
                    # A newly added pack/side file can also leave an unreconciled Git/SQLite view. C14 forbids
                    # retrying away that hard error, but the inventory change must still be recorded.
                    self.assertEqual(result.returncode, 3, "REPAIR-S5-inventory-change")
                    self.assertIn("file_set_changed", sink_reasons(host), "REPAIR-S5-change-reason")
                else:
                    self.assertEqual([e["subpass"] for e in inventories], [0, 1], "REPAIR-S5-inventory-retry")

    def test_requests_all_groups_supersede_previous_pass(self):
        host = self.host()
        host.constants["USER_SINKS"] = ["U4"]
        for phase, user, code in (("baseline", False, "baseline_unfinished"), ("final", False, "final_unfinished"),
                                  ("final", True, "user_run_unfinished"), ("comparison", True, "comparison_unfinished")):
            extra = ("--user-run",) if user else ()
            for point in ("after_request", "before_mkdir", "before_union", "before_plan"):
                with self.subTest(phase=phase, user=user, point=point):
                    prior = host.scan(phase, *extra, tty=user)
                    self.assertEqual(prior.returncode, 0, ("REPAIR-R1-prior-complete", prior.stdout,
                                                          prior.stderr, host.finished()))
                    killed = host.scan(phase, *extra, tty=user, hooks={point: {"do": "kill"}})
                    self.assertEqual(killed.returncode, -9)
                    self.assertIn(code, host.verdict()[2], "REPAIR-R1-group-request")

    def test_missing_registered_lane_and_present_file_roots(self):
        host = Host(self)
        lane = host.root / "missing-lane"
        host.constants["AGENT_SINKS"] = ["A4"]
        host.prepare("--codex-home", str(lane))
        self.assertEqual(host.scan().returncode, 0)
        row = host.finished()["sinks"]["A4"]
        self.assertEqual(len(row["absent"]), 1, "REPAIR-R6-absent-lane")
        self.assertFalse(row["absent_only"])
        existing = Host(self)
        existing.constants["AGENT_SINKS"] = ["A4"]
        lane = existing.root / "present-lane"
        lane.mkdir()
        existing.prepare("--codex-home", str(lane))
        lane.rmdir()
        self.assertEqual(existing.scan().returncode, 3, "REPAIR-R6-removed-lane")
        self.assertIn("vanished", sink_reasons(existing, "A4"), "REPAIR-R6-removed-reason")
        for sink, rel in (("A2", "claude-config-audit.log"), ("A2", ".bash_history"),
                          ("A3", ".cache/claude-cli-nodejs/log"), ("A9", ".local/share/codex-ecosystem/observability/collector/log")):
            other = self.host(sink)
            target = other.home / rel
            target.parent.mkdir(parents=True, exist_ok=True); target.write_text(other.canary())
            self.assertEqual(other.scan().returncode, 5, "REPAIR-A-sink-leak " + rel)
            self.assertTrue(any(e["sink"] == sink for e in hits(other)), "REPAIR-A-attribution " + rel)
            self.assertEqual(other.finished()["status"], "complete")

    def test_fact_counter_end_zero_rules_and_count_cap(self):
        permitted = {wire.FACT: {"check", "observed", "expected", "object", "seal"},
                     wire.COUNTER: {"check", "sink", "subpass", "observed"},
                     wire.END: {"sink", "subpass", "status", "observed", "expected", "seal", "aux"}}
        for kind, allowed in permitted.items():
            fields = {"check": 1} if kind != wire.END else {"status": 1}
            for field in set(wire.NAMES) - allowed - {"magic", "version", "kind", "nonce", "seq"}:
                session = cp.Session(None, {}, "A1", 5)
                session.nonce, session.seal = bytes(16), bytes(16)
                self.assertTrue(session.accept(wire.unpack(wire.pack(kind=wire.BEGIN, seq=1))))
                value = b"x" + bytes(6) if field == "r1" else b"x" + bytes(15) if field in ("object", "seal") else 1
                bad = wire.unpack(wire.pack(kind=kind, seq=2, **{**fields, field: value}))
                with self.subTest(kind=kind, field=field):
                    self.assertFalse(session.accept(bad), "REPAIR-B4-kind-zero")
        for number, accepted in ((1 << 48, True), ((1 << 48) + 1, False)):
            session = cp.Session(None, {}, "A1", 5); session.nonce = session.seal = bytes(16)
            session.accept(wire.unpack(wire.pack(kind=wire.BEGIN, seq=1)))
            self.assertEqual(session.accept(wire.unpack(wire.pack(kind=wire.COUNTER, seq=2, check=1, observed=number))),
                             accepted, "REPAIR-B4-count-cap")

    def test_schema_and_table_errors_are_distinct(self):
        import sqlite3
        for kind, reason in (("schema", "sqlite_schema_error"), ("table", "sqlite_table_error")):
            host = self.host()
            path = sqlite_file(host.home / ".claude/state", [("CREATE TABLE t(v)", ()), ("INSERT INTO t VALUES ('old')", ())])
            connection = sqlite3.connect(path)
            connection.execute("PRAGMA writable_schema=ON")
            if kind == "schema":
                connection.execute("UPDATE sqlite_master SET sql='invalid sql' WHERE name='t'")
            else:
                page = connection.execute("SELECT rootpage FROM sqlite_master WHERE name='t'").fetchone()[0]
                size = connection.execute("PRAGMA page_size").fetchone()[0]
            connection.commit(); connection.close()
            if kind == "table":
                # Keep the schema valid, but damage the table's b-tree page so SELECT * itself fails.
                with path.open("r+b") as handle:
                    handle.seek((page - 1) * size)
                    handle.write(b"\x00")
            self.assertEqual(host.scan().returncode, 3, "REPAIR-M5-error")
            self.assertIn(reason, sink_reasons(host), "REPAIR-M5-distinct-" + kind)

    def test_negative_m2_and_m6_controls_detect_union_matches(self):
        import gzip
        for mode in ("m2", "m6"):
            host = self.host()
            (host.home / ".claude/sample.gz").write_bytes(gzip.compress(b"plain"))
            self.assertEqual(host.scan(taint_negative=mode).returncode, 3, "REPAIR-NEGATIVE-refuses " + mode)
            self.assertIn("negative_control_matched", sink_reasons(host), "REPAIR-NEGATIVE-matched " + mode)

    def test_stream_roots_and_failed_requests_are_described_truthfully(self):
        host = self.host("A11")
        host.constants["USER_SINKS"] = ["U4"]
        self.assertEqual(host.scan("final").returncode, 0)
        self.assertEqual(host.scan("final", "--user-run", tty=True).returncode, 0)
        host.verdict("verdict")
        receipt = json.loads(next((host.state / "native-agent-stack/canary-proof").glob("*.json")).read_text())
        rows = receipt["not_covered"]
        self.assertFalse(any(row.startswith(("A11:absent:", "U4:absent:")) for row in rows),
                         "REPAIR-STREAM-presence")
        self.assertIn("A11:requested_incomplete", rows, "REPAIR-STREAM-requested")
        self.assertNotIn("A11:not_requested", rows, "REPAIR-STREAM-not-requested")

    def test_each_mode_control_and_inband_control_is_required(self):
        import bz2, gzip, lzma
        cases = [(f"m2_{fmt}_{kind}", "m2", fmt) for fmt in ("gzip", "bzip2", "xz", "lzma")
                 for kind in ("plain", "le", "be", "neg")]
        cases += [("m2_gzip_" + kind, "m2", "gzip") for kind in ("two", "mixed")]
        cases += [("m4_" + name, "m4", None) for name in ("loose", "packed", "keep")]
        cases += [("m5_" + name, "m5", None) for name in ("overflow", "le", "be", "default", "view", "trigger",
                                                              "name", "schema_overflow", "uri1", "uri2", "uri3", "uri4")]
        cases += [("m6_" + name, "m6", None) for name in ("name", "target", "path", "negative")]
        cases += [(name, "inband", None) for name in ("m2raw", "m2bom", "m3", "m4", "m5", "u4")]
        for name, mode, fmt in cases:
            with self.subTest(control=name):
                host = self.host("A11" if name == "m3" else "A1")
                payload = b"\xff\xfe" + "plain".encode("utf-16-le")
                target = host.home / ".claude/sample"
                if mode == "m2" or name.startswith("m2"):
                    compress = {"gzip": gzip.compress, "bzip2": bz2.compress, "xz": lzma.compress,
                                "lzma": lambda d: lzma.compress(d, format=lzma.FORMAT_ALONE)}[fmt or "gzip"]
                    target.with_suffix(".lzma" if fmt == "lzma" else ".data").write_bytes(compress(payload))
                elif mode == "m4" or name == "m4":
                    git_repo(target, {"f": b"old"})
                elif mode == "m5" or name == "m5":
                    sqlite_file(target, [("CREATE TABLE t(v)", ())])
                user = name == "u4"
                host.constants["USER_SINKS"] = ["U4"]
                config = {"drop_inband" if mode == "inband" else "drop_control": name}
                result = host.scan("final" if user else "baseline", *(("--user-run",) if user else ()),
                                   tty=user, worker=config)
                self.assertEqual(result.returncode, 3, "REPAIR-CONTROL-required " + name)
                self.assertIn("control_missing", host.finished()["reasons"], "REPAIR-CONTROL-fixed-reason " + name)

    def test_header_fields_and_xz_padding(self):
        import gzip, lzma, struct
        for kind in ("comment", "extra", "xz-padding"):
            host = self.host()
            value = host.canary().encode()
            if kind == "xz-padding":
                data = lzma.compress(b"first") + b"\0" * 4 + lzma.compress(value)
            else:
                stream = bytearray(gzip.compress(b"ordinary body"))
                stream[3] = 16 if kind == "comment" else 4
                extra = value + b"\0" if kind == "comment" else struct.pack("<H", len(value)) + value
                data = bytes(stream[:10]) + extra + bytes(stream[10:])
            (host.home / ".claude/sample").write_bytes(data)
            self.assertEqual(host.scan().returncode, 5, "REPAIR-HEADER-PADDING-hit " + kind)
            self.assertTrue(any(e["mode"] == (2 if kind == "xz-padding" else 1) for e in hits(host)),
                            "REPAIR-HEADER-PADDING-view " + kind)
            self.assertEqual(host.finished()["status"], "complete", "REPAIR-HEADER-PADDING-complete " + kind)

    def test_nested_record_carriers_reject_free_text(self):
        host = self.host()
        self.assertEqual(host.scan().returncode, 0)
        events = host.events()
        locations = [("prepared", ("ref",)), ("scan_planned", ("classes",)), ("scan_planned", ("controls",)),
                     ("scan_planned", ("deadlines",)), ("scan_inventory", ("counters",)),
                     ("scan_finished", ("sinks", "A1"))]
        for kind, path in locations:
            changed = copy.deepcopy(events); target = latest(changed, kind)
            for key in path: target = target[key]
            target["unknown"] = "synthetic free text"
            self.assertFalse(cp.validate(changed, host.run_id), "REPAIR-NESTED-closed " + kind + repr(path))

    def test_control_output_check_survives_new_invocation(self):
        host = self.host()
        self.assertEqual(host.scan().returncode, 0)
        run = cp.Run(host.env(), host.run_id)
        self.addCleanup(os.close, run.lock)
        run.load()
        control = next(line for line in next(host.path.glob("scan-*/patterns")).read_text().splitlines()
                       if line.startswith("CNRYCTL"))
        with self.assertRaises(cp.Refused, msg="REPAIR-OUTPUT-controls-loaded"):
            cp.check_output(control.encode(), run.secrets())

    def test_git_covered_alternate_and_common_directory(self):
        host = self.host()
        top = host.home / ".claude"
        source = git_repo(top / "source", {"old": b"ordinary"}, pack=False)
        alternate = git_repo(top / "alternate", {"old": b"ordinary"}, pack=False)
        subprocess.run([REAL["git"], "--git-dir=" + str(alternate), "hash-object", "-w", "--stdin"],
                       input=host.canary().encode(), capture_output=True, check=True)
        (source / "objects/info/alternates").write_text(str(alternate / "objects") + "\n")
        self.assertEqual(host.scan().returncode, 5, "REPAIR-GIT-alternate-hit")
        self.assertEqual(host.finished()["status"], "complete", "REPAIR-GIT-alternate-complete")
        self.assertTrue(any(e["mode"] == 4 for e in hits(host)), "REPAIR-GIT-alternate-logical")
        other = self.host("A12")
        primary = other.home / "code/native-agent-stack"
        common = git_repo(primary, {"old": b"ordinary"})
        subprocess.run([REAL["git"], "--git-dir=" + str(common), "hash-object", "-w", "--stdin"],
                       input=other.canary().encode(), capture_output=True, check=True)
        admin = common / "worktrees/live"; admin.mkdir(parents=True)
        (admin / "commondir").write_text("../..\n")
        live = other.home / "code/native-agent-stack-live"; live.mkdir()
        (live / ".git").write_text("gitdir: " + str(admin) + "\n")
        self.assertEqual(other.scan().returncode, 5, "REPAIR-GIT-common-hit")
        self.assertEqual(other.finished()["status"], "complete", "REPAIR-GIT-common-complete")
        self.assertEqual({e["root"] for e in hits(other) if e["mode"] == 4},
                         {root for root, _present in other.events()[0]["roots"]["A12"]},
                         "REPAIR-GIT-common-roots")

    def test_git_pack_replacement_and_missing_enumerated_object(self):
        for kind in ("replace", "omit"):
            host = Host(self)
            host.constants["AGENT_SINKS"] = ["A1"]
            repo = git_repo(host.home / ".claude/repo", {"file": b"ordinary"})
            pack = next(repo.glob("objects/pack/*.pack"))
            replacement = host.root / "replacement.pack"; replacement.write_bytes(pack.read_bytes())
            prefix = (f"import subprocess\nif '--batch-check=%(objectname) %(objecttype) %(objectsize)' in sys.argv:\n"
                      f"    p=subprocess.run([{REAL['git']!r}] + sys.argv[1:], capture_output=True)\n")
            if kind == "replace":
                prefix += f"    if os.path.exists({str(replacement)!r}): os.replace({str(replacement)!r}, {str(pack)!r})\n"
                prefix += "    sys.stdout.buffer.write(p.stdout);sys.exit(p.returncode)\n"
            else:
                prefix += "    sys.stdout.buffer.write(b'\\n'.join(p.stdout.splitlines()[1:]) + b'\\n');sys.exit(p.returncode)\n"
            wrapper(host, "git", prefix=prefix)
            host.prepare()
            self.assertEqual(host.scan().returncode, 3 if kind == "omit" else 0, "REPAIR-GIT-reconcile " + kind)
            if kind == "replace":
                self.assertEqual(host.finished()["sinks"]["A1"]["subpass"], 1, "REPAIR-GIT-pack-retry")
            else:
                self.assertIn("git_unaccounted_payload", sink_reasons(host), "REPAIR-GIT-missing-object")

    def test_exception_between_sinks_and_missing_bootstrap_handshake(self):
        host = self.host()
        host.constants["AGENT_SINKS"] = ["A1", "A3"]
        result = host.scan(hooks={"between_sinks": {"do": "exception", "when": "A1"}})
        self.assertEqual(result.returncode, 3, "REPAIR-C5-exception-incomplete")
        self.assertEqual(host.finished()["reasons"], ["setup_failed"], "REPAIR-C5-fixed-code")
        self.assertIn("baseline_sink_not_scanned:A3", host.verdict()[2], "REPAIR-C5-between-sinks")
        for action in ("exit 0", "kill -TERM $$"):
            other = self.host()
            (other.bin / "stub-runner").write_text("#!/bin/sh\n" + action + "\n")
            self.assertEqual(other.scan().returncode, 3, "REPAIR-C8-no-handshake")
            self.assertFalse(any(e["event"] == "scan_planned" for e in other.events()),
                             "REPAIR-C8-bootstrap-preplan")
            self.assertEqual(wait_gone(str(other.root), 3), [], "REPAIR-C8-no-children")

    def test_exception_with_live_child_reaps_and_keeps_hit(self):
        host = self.host()
        (host.home / ".claude/leak").write_text(host.canary())
        result = host.scan(hooks={"after_durable_hit": {"do": "exception"}})
        self.assertEqual(result.returncode, 5, "REPAIR-C5-sticky-hit")
        self.assertEqual(host.finished()["status"], "incomplete", "REPAIR-C5-live-child-incomplete")
        self.assertEqual(host.finished()["reasons"], ["setup_failed"], "REPAIR-C5-live-child-code")
        self.assertEqual(wait_gone(str(host.root), 5), [], "REPAIR-C5-live-child-cleanup")


@needs_tools
class ContainmentMatrixTests(unittest.TestCase):
    """Every worker-started executable and helper stage, under coordinator and worker death."""

    def death(self, host, process, ready, fifo, victim, label, prepared=True):
        self.addCleanup(ContainmentTests.reap, self, host, process)
        child = observe_fifo(self, ready, fifo, process)
        self.assertIn(child, processes_with(str(host.root)), "C-MATRIX-intended-child")
        if "/--version" in label:
            args = Path(f"/proc/{child}/cmdline").read_bytes().split(b"\0")[:-1]
            self.assertEqual(args, [PYTHON.encode(), b"-I", os.fsencode(host.bin / label.split("/")[0]), b"--version"],
                             "C-MATRIX-exact-version-stage")
        if victim == "worker":
            workers = []
            for pid in processes_with(str(host.root)):
                args = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
                if args[0].endswith(b"python3") and b"worker" in args:
                    workers.append(pid)
            self.assertEqual(len(workers), 1, "C-MATRIX-worker-observed")
            os.kill(workers[0], signal.SIGKILL)
        else:
            process.kill()
        process.communicate(timeout=25)
        self.assertEqual(wait_gone(str(host.root), 15), [], "C-MATRIX-death-cleanup " + label + "/" + victim)
        if prepared:
            self.assertNotEqual(host.verdict()[1], "clean", "C-MATRIX-unfinished")

    def test_parent_death_every_scan_kind_and_stage(self):
        import bz2, gzip, lzma
        rows = [("rg-raw", "rg", "none", 1, False), ("rg-bom", "rg", "auto", 1, False),
                ("rg-m2raw", "rg", "none", 1, True), ("rg-m2bom", "rg", "auto", 1, True),
                ("gzip", "gzip", None, 1, False), ("bzip2", "bzip2", None, 1, False),
                ("xz", "xz", None, 1, False), ("lzma", "xz", "--format=lzma", 1, False),
                ("journal", "journalctl", "--user", 1, False),
                ("environment", "systemctl", "show-environment", 1, False),
                ("sqlite", None, None, 1, False), ("worker", None, None, 1, False)]
        rows += [("git-" + stage + str(n), "git", stage, n, False) for stage, n in (
            ("fsck", 1), ("verify-pack", 1), ("--batch-check=%(objectname) %(objecttype) %(objectsize)", 1),
            ("--batch=%(objectname) %(objecttype) %(objectsize)", 1),
            ("--batch-check=%(objectname) %(objecttype) %(objectsize)", 2))]
        for label, executable, stage, occurrence, stream_only in rows:
            for victim in ("coordinator", "worker"):
                with self.subTest(case=label, victim=victim):
                    host = Host(self)
                    host.constants["AGENT_SINKS"] = ["A11" if label == "journal" else "A1"]
                    host.constants["USER_SINKS"] = ["U4"]
                    payload = b"\xff\xfe" + b"x\0" * 300
                    target = host.home / ".claude/sample"
                    if executable == "git":
                        git_repo(target, {"f": b"old"})
                    elif label == "sqlite":
                        sqlite_file(target, [("CREATE TABLE t(v)", ())])
                    elif label in ("gzip", "bzip2", "xz", "lzma") or stream_only:
                        compress = {"bzip2": bz2.compress, "xz": lzma.compress,
                                    "lzma": lambda d: lzma.compress(d, format=lzma.FORMAT_ALONE)}.get(label, gzip.compress)
                        if label == "lzma":
                            target = target.with_suffix(".lzma")
                        target.write_bytes(compress(payload))
                    else:
                        target.write_bytes(payload if label == "rg-bom" else b"old")
                    host.prepare()
                    if executable:
                        prefix = "os.write(1, b'\\xff\\xfe' + b'x\\x00' * 300)" if label in ("gzip", "bzip2", "xz", "lzma") else ""
                        fifo = blocked_program(host, executable, stage, prefix, occurrence, stream_only)
                        ready = host.root / ("ready-" + executable)
                        FifoTests.repin(self, host, executable)
                    else:
                        fifo, ready = host.root / "hook-fifo", host.root / "ready-hook"
                        os.mkfifo(fifo)
                        config = host.dumper if label == "sqlite" else host.worker
                        config["hooks"]["after_identity" if label == "sqlite" else "after_prewalk"] = {
                            "do": "block", "path": str(fifo), "ready": str(ready)}
                    user = label == "environment"
                    process = host.scan("final" if user else "baseline", *(("--user-run",) if user else ()),
                                        tty=user, background=True)
                    self.death(host, process, ready, fifo, victim, label)

    def test_parent_death_every_setup_helper_stage(self):
        stages = [("git", stage, n, False) for stage, n in (("init", 1), ("hash-object", 1),
                  ("hash-object", 2), ("mktree", 1), ("commit-tree", 1), ("update-ref", 1),
                  ("pack-objects", 1), ("prune-packed", 1))]
        stages += [("git", "rev-parse", 1, True), ("systemd-cat", "-t", 1, True),
                   ("journalctl", "SYSLOG_IDENTIFIER=canary-proof", 1, True)]
        stages += [(name, "--version", 1, True) for name in cp.EXECUTABLES]
        for executable, stage, occurrence, preparation in stages:
            for victim in ("coordinator", "worker"):
                with self.subTest(executable=executable, stage=stage, occurrence=occurrence, victim=victim):
                    host = Host(self)
                    host.constants["AGENT_SINKS"] = ["A1"]
                    if not preparation:
                        host.prepare()
                    fifo = blocked_program(host, executable, stage, occurrence=occurrence)
                    if not preparation:
                        FifoTests.repin(self, host, executable)
                    process = host.tool("prepare", background=True) if preparation else host.scan(background=True)
                    self.death(host, process, host.root / ("ready-" + executable), fifo, victim,
                               executable + "/" + stage + str(occurrence), not preparation)


if __name__ == "__main__":
    if "--skip-list" in sys.argv:
        result = unittest.TestResult()
        unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]).run(result)
        print(json.dumps({"skipped": [{"test": test.id(), "reason": reason} for test, reason in result.skipped],
                          "failures": len(result.failures), "errors": len(result.errors)}))
        sys.exit(not result.wasSuccessful())
    unittest.main()
