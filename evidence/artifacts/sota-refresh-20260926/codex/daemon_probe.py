#!/usr/bin/env python3
"""Background-server probe for Codex 0.157.1 against 0.155.1 (run inside sandbox_daemon.sh; scratch homes only).

Usage: daemon_probe.py <old-codex> <new-codex> <arm-dir> <results.json>

At rust-v0.157.1 the feature daemon_auto_start is stable and on by default: an eligible interactive launch copies
the calling CLI package into CODEX_HOME/packages/app-server-daemon and starts `codex app-server` from that copy
(codex-rs/tui/src/startup_orchestration.rs, app-server-daemon/src/prepare_install.rs). Every step runs the
npm-installed CLI the way bin/codex does, in a pty for interactive launches, with a fresh CODEX_HOME unless noted.
CHECK, PACKAGE and TERM_LOOP are the exact shell lines the receipt gives the coordinator; they run here through
bash with CODEX_HOME set to the step's home (CODEX_HOME is unset on the host, so there they name ~/.codex).

  T1 new: plain interactive launch. Does a server start, from where, which processes and files, and does it
     outlive the TUI? Which process holds the other end of the server's control-socket connections? CHECK.
  T2 new and old `app-server daemon version` while it runs
  T3 old: plain interactive launch on T1's home while that server runs: which process holds the other end of the
     connections the server accepts on its control socket?
  T4 rollback step 1: new `app-server daemon stop`; which processes remain? CHECK.
  T5 rollback step 2: TERM_LOOP, then CHECK
  T6 new: interactive launch with --no-daemon: no server, no package copy; then CHECK, and new
     `app-server daemon stop` and `app-server daemon version` on that home, where nothing runs
  T7 new: `features disable daemon_auto_start` on a home whose config.toml already has a comment, a top-level key
     and a [features] table; the file before and after, the `features list` line, then a plain interactive
     launch: no server, no package copy
  T8 old on T7's home: its `features list` line, and one fake-provider exec turn that reads the user config
  T9 old: plain interactive launch on T7's home: the TUI starts, no server, no package copy
"""
from __future__ import annotations

import fcntl
import json
import os
import re
import select
import signal
import struct
import subprocess
import sys
import termios
import time
from pathlib import Path

old, new, arm, results_path = sys.argv[1], sys.argv[2], Path(sys.argv[3]), Path(sys.argv[4])
here = Path(__file__).resolve().parent
HOME = str(Path.home())
PORT = 18094
CHECK = 'ls -l /proc/[0-9]*/exe 2>/dev/null | grep -cF "${CODEX_HOME:-$HOME/.codex}/packages/app-server-daemon/"'
PACKAGE = 'test -e "${CODEX_HOME:-$HOME/.codex}/packages/app-server-daemon" && echo present || echo absent'
TERM_LOOP = ('for p in /proc/[0-9]*; do case "$(readlink "$p/exe" 2>/dev/null)" in '
             '"${CODEX_HOME:-$HOME/.codex}"/packages/app-server-daemon/*) '
             'echo "TERM ${p#/proc/} $(readlink "$p/exe")"; kill -TERM "${p#/proc/}";; esac; done')
SEEDED_CONFIG = ('# synthetic pre-existing settings: this comment, the top-level key and the [features] entry must stay\n'
                 'model_reasoning_effort = "high"\n\n[features]\nhooks = true\n')
out: dict = {"commands": {"CHECK": CHECK, "PACKAGE": PACKAGE, "TERM_LOOP": TERM_LOOP}, "steps": []}
REPLIES = [  # terminal queries a TUI may send at startup, answered as a plain xterm would
    (b"\x1b[6n", b"\x1b[1;1R"),
    (b"\x1b[c", b"\x1b[?62;22c"),
    (b"\x1b[0c", b"\x1b[?62;22c"),
    (b"\x1b[?u", b"\x1b[?0u"),
    (b"\x1b]10;?\x1b\\", b"\x1b]10;rgb:ffff/ffff/ffff\x1b\\"),
    (b"\x1b]10;?\x07", b"\x1b]10;rgb:ffff/ffff/ffff\x07"),
    (b"\x1b]11;?\x1b\\", b"\x1b]11;rgb:0000/0000/0000\x1b\\"),
    (b"\x1b]11;?\x07", b"\x1b]11;rgb:0000/0000/0000\x07"),
]
ANSI = re.compile(rb"\x1b\[[0-9;?<>=]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b[@-Z\\-_]|[\x00-\x08\x0e-\x1f]")


def clean(text: str) -> str:
    return text.replace(str(arm), "<arm>").replace(HOME, "~")


def note(step: str, **data) -> None:
    record = json.loads(clean(json.dumps({"step": step, **data}, default=str)))
    out["steps"].append(record)
    print(json.dumps(record)[:1500], flush=True)


def new_home(name: str) -> Path:
    home = arm / name
    home.mkdir()
    return home


def pkg_root(home: Path) -> Path:
    return home / "packages" / "app-server-daemon"


def readlink_exe(pid: int) -> str | None:
    try:
        return os.readlink(f"/proc/{pid}/exe")
    except OSError:
        return None


def processes() -> list[dict]:
    rows = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit() or int(entry.name) == os.getpid():
            continue
        try:
            argv = [a.decode(errors="replace") for a in (entry / "cmdline").read_bytes().split(b"\0") if a]
            exe = os.readlink(entry / "exe")
        except OSError:
            continue
        if "codex" in exe or any("codex" in a for a in argv[:2]):
            rows.append({"pid": int(entry.name), "exe": exe, "argv": argv[:6]})
    return rows


def daemon_processes(home: Path) -> list[dict]:
    prefix = str(pkg_root(home)) + "/"
    return [p for p in processes() if p["exe"].startswith(prefix)]


def package_state(home: Path) -> dict:
    root = pkg_root(home)
    state = {"package_root_exists": root.exists()}
    if root.exists():
        current = root / "current"
        state["current"] = os.readlink(current) if current.is_symlink() else None
        releases = root / "releases"
        state["releases"] = sorted(p.name for p in releases.iterdir()) if releases.exists() else []
        marker = root / "auto-update-version"
        state["auto_update_version"] = marker.read_text().strip() if marker.exists() else None
        state["bytes"] = sum(p.stat().st_size for p in root.rglob("*") if p.is_file() and not p.is_symlink())
    daemon_state = home / "app-server-daemon"
    state["state_files"] = sorted(p.name for p in daemon_state.iterdir()) if daemon_state.exists() else []
    return state


def control_path(home: Path) -> str:
    # CODEX_HOME/app-server-control/app-server-control.sock is a symlink to /tmp/codex-daemon-<uid>/<hash>, the path
    # the server binds and /proc/net/unix and ss report
    return os.path.realpath(home / "app-server-control" / "app-server-control.sock")


def socket_counts(home: Path) -> dict:
    path = control_path(home)
    counts = {"listening": 0, "connected": 0}
    for line in Path("/proc/net/unix").read_text().splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 8 and parts[7] == path:
            counts["connected" if parts[5] == "03" else "listening"] += 1
    return counts


def server_socket_fds(home: Path) -> int | None:
    """Socket descriptors held by the `app-server --managed-daemon` process that runs from the package copy."""
    for proc in daemon_processes(home):
        if "--managed-daemon" in proc["argv"]:
            fds = Path("/proc") / str(proc["pid"]) / "fd"
            try:
                return sum(1 for fd in fds.iterdir() if os.readlink(fd).startswith("socket:"))
            except OSError:
                return None
    return None


def control_peers(home: Path) -> list[dict]:
    """For each connection the server accepted on its control socket, the process holding the other end (ss -xpn:
    netid, state, recv-q, send-q, local path, local inode, peer path, peer inode, users)."""
    path = control_path(home)
    rows = [line.split() for line in subprocess.run(["ss", "-xpn"], capture_output=True, text=True).stdout.splitlines()[1:]]
    by_inode = {row[5]: row for row in rows if len(row) >= 8}
    peers = []
    for row in rows:
        if len(row) >= 8 and row[1] == "ESTAB" and row[4] == path:
            other = by_inode.get(row[7])
            users = other[8] if other is not None and len(other) > 8 else None
            pids = [int(p) for p in re.findall(r"pid=(\d+)", users or "")]
            peers.append({"server_side_inode": row[5], "peer_inode": row[7], "peer_users": users,
                          "peer_exes": [readlink_exe(p) for p in pids]})
    return peers


def run(argv: list[str], home: Path, timeout: int = 60, full: bool = False) -> dict:
    proc = subprocess.run(argv, cwd=arm / "empty", env=dict(os.environ, CODEX_HOME=str(home)),
                          stdin=subprocess.DEVNULL, capture_output=True, timeout=timeout)
    stdout = proc.stdout.decode(errors="replace")
    return {"argv": [Path(argv[0]).parent.parent.name] + argv[1:], "exit": proc.returncode,
            "stdout": stdout if full else stdout[-1500:], "stderr": proc.stderr.decode(errors="replace")[-800:]}


def shell(name: str, home: Path) -> dict:
    proc = subprocess.run(["bash", "-c", out["commands"][name]], cwd=arm / "empty",
                          env=dict(os.environ, CODEX_HOME=str(home)), stdin=subprocess.DEVNULL, capture_output=True,
                          timeout=60)
    return {"command": name, "exit": proc.returncode, "stdout": proc.stdout.decode(errors="replace").strip(),
            "stderr": proc.stderr.decode(errors="replace").strip()[-400:]}


def feature_line(result: dict) -> dict:
    # the full list (about 100 lines) is kept only for the one feature; a tail cut would drop it
    result["daemon_auto_start_lines"] = [line for line in result.pop("stdout").splitlines() if "daemon_auto_start" in line]
    return result


def interactive(argv: list[str], home: Path, seconds: float, sample=None, probe_at=None) -> dict:
    """Run argv in a pty for `seconds`, answering terminal queries; sample() on change, probe_at=(s, fn) once."""
    env = dict(os.environ, CODEX_HOME=str(home))
    started = time.monotonic()
    pid, fd = os.forkpty()
    if pid == 0:  # child: size the terminal, then exec
        try:
            fcntl.ioctl(0, termios.TIOCSWINSZ, struct.pack("HHHH", 40, 120, 0, 0))
            os.chdir(arm / "empty")
            os.execvpe(argv[0], argv, env)
        finally:
            os._exit(127)
    screen, tail, status, samples, probed = bytearray(), b"", None, [], None  # samples: [seconds, value] on change
    while time.monotonic() - started < seconds:
        ready, _, _ = select.select([fd], [], [], 0.25)
        if ready:
            try:
                data = os.read(fd, 65536)
            except OSError:
                data = b""
            if not data:
                break
            screen += data
            tail = (tail + data)[-512:]
            for query, reply in REPLIES:
                if query in tail:
                    os.write(fd, reply * tail.count(query))
                    tail = tail.replace(query, b"")
        done, raw_status = os.waitpid(pid, os.WNOHANG)
        if done == pid:
            status = raw_status
            break
        if sample is not None:
            value = sample()
            if not samples or samples[-1][1] != value:
                samples.append([round(time.monotonic() - started, 1), value])
        if probe_at is not None and probed is None and time.monotonic() - started >= probe_at[0]:
            probed = {"at_s": round(time.monotonic() - started, 1), "result": probe_at[1]()}
    alive = status is None
    if alive:
        os.killpg(pid, signal.SIGTERM)
        for _ in range(40):
            done, raw_status = os.waitpid(pid, os.WNOHANG)
            if done == pid:
                status = raw_status
                break
            time.sleep(0.25)
        else:
            os.killpg(pid, signal.SIGKILL)
            _, status = os.waitpid(pid, 0)
    os.close(fd)
    text = ANSI.sub(b" ", bytes(screen)).decode(errors="replace")
    words = re.sub(r"\s+", " ", text).strip()
    result = {"argv": [Path(argv[0]).parent.parent.name] + argv[1:], "alive_until_stopped": alive,
              "seconds": round(time.monotonic() - started, 2),
              "exit_status": os.waitstatus_to_exitcode(status) if status is not None else None,
              "screen_text_head": words[:400], "screen_text_tail": words[-400:],
              "screen_error_words": sorted(set(re.findall(r"(?i)\b(?:error|invalid|unknown|failed)\w*", words))),
              "samples": samples}
    if probe_at is not None:
        result["probe"] = probed
    return result


(arm / "empty").mkdir(exist_ok=True)
note("T0-versions", old=run([old, "--version"], arm / "codex-home"), new=run([new, "--version"], arm / "codex-home"))

# T1 plain interactive launch with 0.157.1
h1 = new_home("home-T1")
t1 = interactive([new], h1, 35, sample=lambda: [len(daemon_processes(h1)), socket_counts(h1)["listening"],
                                               socket_counts(h1)["connected"]],
                 probe_at=(12, lambda: control_peers(h1)))
t1["samples_legend"] = "[seconds, [processes under the package copy, listening sockets, server-side connections]]"
time.sleep(3)
note("T1-plain-launch-new", launch=t1, daemon_processes_after_tui_stopped=daemon_processes(h1),
     all_codex_processes=processes(), package=package_state(h1), socket=socket_counts(h1),
     check=shell("CHECK", h1), package_check=shell("PACKAGE", h1))

# T2 version reports while the server runs
note("T2-daemon-version", new=run([new, "app-server", "daemon", "version"], h1),
     old=run([old, "app-server", "daemon", "version"], h1))

# T3 0.155.1 interactive launch on the same home while the 0.157.1 server runs
before = dict(socket_counts(h1), server_socket_fds=server_socket_fds(h1), control_socket_target=control_path(h1))
t3 = interactive([old], h1, 25, sample=lambda: [socket_counts(h1)["connected"], server_socket_fds(h1)],
                 probe_at=(12, lambda: control_peers(h1)))
t3["samples_legend"] = ("[seconds, [server-side connections on the running server's control socket, "
                        "socket descriptors of the server process]]")
note("T3-old-launch-while-server-runs", socket_before=before, launch=t3, socket_after=socket_counts(h1),
     daemon_processes=daemon_processes(h1))

# T4 rollback step 1: stop with the 0.157.1 binary
stop = run([new, "app-server", "daemon", "stop"], h1, timeout=120)
time.sleep(2)
note("T4-daemon-stop-new", stop=stop, remaining=daemon_processes(h1), check=shell("CHECK", h1),
     socket=socket_counts(h1), package=package_state(h1))

# T5 rollback step 2: the receipt's TERM loop, then the check
term = shell("TERM_LOOP", h1)
time.sleep(5)
note("T5-term-loop", term_loop=term, remaining=daemon_processes(h1), check=shell("CHECK", h1),
     socket=socket_counts(h1))

# T6 --no-daemon, then the rollback's stop and a version report where nothing runs
h6 = new_home("home-T6")
t6 = interactive([new, "--no-daemon"], h6, 30)
note("T6-no-daemon-launch-new", launch=t6, daemon_processes=daemon_processes(h6), package=package_state(h6),
     socket=socket_counts(h6), check=shell("CHECK", h6), package_check=shell("PACKAGE", h6),
     stop_when_idle=run([new, "app-server", "daemon", "stop"], h6, timeout=120),
     version_when_idle=run([new, "app-server", "daemon", "version"], h6),
     features_list_default=feature_line(run([new, "features", "list"], h6, full=True)))

# T7 features.daemon_auto_start = false through the supported command, on a config.toml with existing content
h7 = new_home("home-T7")
(h7 / "config.toml").write_text(SEEDED_CONFIG)
disable = run([new, "features", "disable", "daemon_auto_start"], h7)
after = (h7 / "config.toml").read_text()
kept = [line for line in SEEDED_CONFIG.splitlines() if line]
positions = [after.splitlines().index(line) if line in after.splitlines() else None for line in kept]
listed = feature_line(run([new, "features", "list"], h7, full=True))
t7 = interactive([new], h7, 30)
note("T7-features-disable-then-launch-new", disable=disable, config_toml_before=SEEDED_CONFIG, config_toml_after=after,
     seeded_lines_kept_in_order=None not in positions and positions == sorted(positions), features_list=listed,
     launch=t7, daemon_processes=daemon_processes(h7), package=package_state(h7), socket=socket_counts(h7),
     check=shell("CHECK", h7), package_check=shell("PACKAGE", h7))

# T8 0.155.1 with T7's config.toml
old_list = feature_line(run([old, "features", "list"], h7, full=True))
server = subprocess.Popen([sys.executable, str(here / "fake_responses.py"), str(PORT), "ok", str(arm / "T8-requests.jsonl")],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
time.sleep(0.8)
provider = ["-c", 'model_provider="fakeprov"', "-c", 'model_providers.fakeprov.name="fake"',
            "-c", f'model_providers.fakeprov.base_url="http://127.0.0.1:{PORT}/v1"',
            "-c", 'model_providers.fakeprov.wire_api="responses"', "-c", "model_providers.fakeprov.request_max_retries=0",
            "-c", "model_providers.fakeprov.stream_max_retries=0"]
turn = run([old, "exec", "--skip-git-repo-check", "-s", "read-only", "-m", "gpt-6-astra"] + provider +
           ["--json", "Reply with one word."], h7, timeout=180)
events = []
for line in turn.pop("stdout").splitlines():
    try:
        events.append(json.loads(line).get("type"))
    except ValueError:
        events.append("<non-json>")
turn["event_types"] = events
server.terminate()
server.wait(timeout=10)
efforts = []
for line in (arm / "T8-requests.jsonl").read_text().splitlines() if (arm / "T8-requests.jsonl").exists() else []:
    body = json.loads(line).get("body")
    if isinstance(body, dict) and "reasoning" in body:
        efforts.append((body.get("reasoning") or {}).get("effort"))
note("T8-old-with-disabled-feature-config", features_list=old_list, exec_turn_reading_user_config=turn,
     reasoning_effort_sent=efforts, daemon_processes=daemon_processes(h7), package=package_state(h7))

# T9 0.155.1 interactive launch on T7's home
t9 = interactive([old], h7, 20)
note("T9-old-launch-with-disabled-feature-config", launch=t9, daemon_processes=daemon_processes(h7),
     package=package_state(h7), check=shell("CHECK", h7))

results_path.write_text(clean(json.dumps(out, indent=2)) + "\n")
print("DONE")
