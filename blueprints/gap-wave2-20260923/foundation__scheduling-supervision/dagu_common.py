"""Shared helpers for the gap-wave2 scheduling-supervision drivers (standard library only)."""

import json
import os
from pathlib import Path
import signal
import subprocess
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DAGU = Path.home() / ".local/share/codex-ecosystem/bin/dagu"
DAGU_2166_SHA256 = "20de7ae94e16999ff997db0386dced9504db37c87de333837fd15b4892b98bd7"
CODEX_BIN_DIR = str(Path.home() / ".local/share/codex-ecosystem/bin")


def process_table():
    result = subprocess.run(["/bin/ps", "-axo", "pid=,ppid=,lstart="], capture_output=True, text=True, check=True)
    return {int(parts[0]): (int(parts[1]), " ".join(parts[2:]))
            for line in result.stdout.splitlines() if len(parts := line.split()) >= 7}


def descendants(pid, include_self=True):
    table, found = process_table(), {pid}
    while True:
        more = {child for child, (parent, _) in table.items() if parent in found}
        if more <= found:
            return {c: table[c][1] for c in found if c in table and (include_self or c != pid)}
        found |= more


def live(identities):
    current = process_table()
    return [pid for pid, started in identities.items() if pid in current and current[pid][1] == started]


def history_rows(stdout):
    value = json.loads(stdout)
    return value if isinstance(value, list) else value.get("runs", [])


class Recorder:
    """Runs native commands, retains stdout/stderr per label and their exit codes."""

    def __init__(self, work, env, default_timeout=60):
        self.work, self.env, self.codes, self.timeout = work, env, {}, default_timeout
        (work / "native").mkdir(exist_ok=True)

    def call(self, label, argv, check=True, timeout=None):
        child = subprocess.Popen(argv, cwd=self.work, env=self.env, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, text=True, start_new_session=True)
        try:
            stdout, stderr = child.communicate(timeout=timeout or self.timeout)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            stdout, stderr = child.communicate(timeout=5)
            stderr += "\n[driver] timed out and killed\n"
        (self.work / "native" / (label + ".stdout")).write_text(stdout)
        (self.work / "native" / (label + ".stderr")).write_text(stderr)
        self.codes[label] = child.returncode
        if check and child.returncode:
            raise ValueError(f"Native command failed: {label}: {stderr.strip()[-400:]}")
        return stdout


def wait_for(predicate, seconds, poll=0.1):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(poll)
    return predicate()


def stop_group(process, grace=10):
    if process is None or process.poll() is not None:
        return
    os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=grace)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=5)


# ---------------------------------------------------------------- fix round 1 (review of b7aec6b)
# Private Dagu config: `scheduler.port: 0` disables the scheduler's /health server, which
# otherwise binds ':8090' on all interfaces (internal/service/healthcheck/server.go and
# internal/cmn/config/loader.go setSchedulerDefaults at Dagu 58fed633 / v2.16.6).
PRIVATE_CONFIG = "check_updates: false\nscheduler:\n  port: 0\n"


def listeners(pids=None):
    """TCP LISTEN sockets from `ss -Hltnp`, optionally only those owned by `pids`."""
    out = subprocess.run(["ss", "-Hltnp"], capture_output=True, text=True, check=True).stdout
    rows = []
    for line in out.splitlines():
        owners = {int(p) for p in __import__("re").findall(r"pid=(\d+)", line)}
        if pids is None or owners & set(pids):
            rows.append(" ".join(line.split()))
    return rows


def listener_probe_self_test():
    """Positive control: a loopback listener opened here must be found by `listeners`."""
    import socket
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        port = s.getsockname()[1]
        found = [row for row in listeners([os.getpid()]) if f":{port} " in row + " "]
    return {"control_port": port, "detected": bool(found), "rows": found}


CODEX_EXEC_WORDS = ("exec", "e")  # `e` is the exec alias


def codex_exec_processes(exclude=()):
    """Real `codex exec` processes: argv[0] basename `codex` (or a node launcher whose argv[1]
    is codex/codex.js) with `exec` or its alias `e` anywhere in the remaining arguments, so
    `codex <global options> exec` is counted. Matching any later argument over-counts (for
    example an option value that equals `e`), which only makes the gate wait longer.
    Wrappers such as `timeout N codex exec` are not counted; their codex child is."""
    found = {}
    for entry in os.listdir("/proc"):
        if not entry.isdigit() or int(entry) in exclude:
            continue
        try:
            argv = [a.decode(errors="replace") for a in Path(f"/proc/{entry}/cmdline").read_bytes().split(b"\0") if a]
        except OSError:
            continue
        if len(argv) > 1 and os.path.basename(argv[0]) == "codex":
            rest = argv[1:]
        elif len(argv) > 2 and os.path.basename(argv[1]) in ("codex", "codex.js"):
            rest = argv[2:]
        else:
            continue
        if any(word in CODEX_EXEC_WORDS for word in rest):
            found[int(entry)] = " ".join(argv[:4])
    return found


class CodexGateTimeout(RuntimeError):
    """Raised when 2 or more other `codex exec` processes still run at max_wait. The caller
    must not make the model call; the wave's 20-minute rule records the check as not_settled."""

    def __init__(self, observation):
        super().__init__(f"codex gate not released after {observation['waited_s']} s: "
                         f"{observation['other_codex_exec_at_release']} other codex exec processes")
        self.observation = observation


def codex_gate(max_wait=1200, poll=5):
    """Wait while 2 or more other real `codex exec` processes run; return the observation.
    Fix round 3: on reaching max_wait with 2 or more still running, raise CodexGateTimeout
    instead of returning, so no caller proceeds to the model call."""
    started, samples = time.monotonic(), []
    while True:
        others = codex_exec_processes(exclude={os.getpid()})
        samples.append(len(others))
        waited = time.monotonic() - started
        if len(others) < 2 or waited >= max_wait:
            observation = {"checked_at": __import__("datetime").datetime.now().astimezone().isoformat(),
                           "rule": "wait while 2 or more real codex exec processes run",
                           "other_codex_exec_at_release": len(others), "pids_at_release": sorted(others),
                           "waited_s": round(waited, 1), "samples": samples[-20:],
                           "released_by_timeout": False}
            if len(others) >= 2:
                raise CodexGateTimeout(observation)
            return observation
        time.sleep(poll)
