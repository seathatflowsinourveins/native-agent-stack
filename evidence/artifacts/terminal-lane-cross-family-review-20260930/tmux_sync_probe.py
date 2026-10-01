#!/usr/bin/env python3
"""Does tmux 3.4 wrap its redraws in DEC mode 2026 (synchronized output) when the outer terminal is declared to support it? A private tmux server (-S <a socket inside its own temporary directory>, empty config), a client in a
pty as the outer terminal, once with `terminal-features 'xterm*:sync'` and once without it (negative control); counts ESC[?2026h and ESC[?2026l in what tmux writes to the client. Reads and writes
only inside its own temporary directory; stops only its own server and verifies that it is gone before removing the socket directory (a server that will not stop keeps its socket and fails the probe).
`--selftest` runs the shutdown-failure control. usage: python3 -B tmux_sync_probe.py [--selftest]"""
import os, pty, select, shutil, signal, subprocess, sys, tempfile, time
from pathlib import Path

TMUX = shutil.which("tmux")
SET, RESET = b"\x1b[?2026h", b"\x1b[?2026l"


class ServerNotStopped(RuntimeError):
    """The private tmux server could not be stopped: its socket directory was KEPT so that it can be stopped by hand (`tmux -S <socket> kill-server`)."""

    def __init__(self, socket):
        super().__init__(f"the private tmux server did not stop; its socket {socket} was kept (stop it with `tmux -S {socket} kill-server`)")
        self.socket = socket


def start_time(pid):
    """The start time (clock ticks since boot) of a process from /proc, or None."""
    try:
        return (Path("/proc") / str(pid) / "stat").read_text().rsplit(")", 1)[1].split()[19]
    except (OSError, IndexError):
        return None


def server_identity(base):
    """(pid, start time) of the private server, read right after it started: `display-message -p '#{pid}'` answers with its pid, /proc says it is a `tmux` process whose command line holds OUR socket path (the
    server keeps the command line it was started with) and when it started, so the same process can be told from a later one that reused the pid. None when that cannot be established (then nothing is ever signaled)."""
    try:
        pid = int(subprocess.run(base + ["display-message", "-p", "#{pid}"], capture_output=True, text=True, timeout=10).stdout.strip())
        socket = base[base.index("-S") + 1].encode()
        if not (Path("/proc") / str(pid) / "comm").read_text().startswith("tmux") or socket not in (Path("/proc") / str(pid) / "cmdline").read_bytes():
            return None   # not a tmux process, or not the one that was started with OUR socket
        return pid, start_time(pid)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


def server_alive(identity):
    """True while the process that was identified is still the same running tmux: the start time must match, the name must be tmux and the state must not be `Z` (a zombie keeps its /proc entry but is dead)."""
    pid, started = identity
    try:
        state = (Path("/proc") / str(pid) / "stat").read_text().rsplit(")", 1)[1].split()[0]
        return start_time(pid) == started and state != "Z" and (Path("/proc") / str(pid) / "comm").read_text().startswith("tmux")
    except (OSError, IndexError):
        return False


def stop_server(base, work, client_pid=None, fd=None, identity=None):
    """Stop the private server, close the attach client's pty and reap the client (our own child), then remove the private directory ONLY when the server is really gone. `kill-server` is tried twice; a server that
    survives it is signaled by its verified identity (pid and start time: SIGTERM, then SIGKILL); with no identity the server is asked with `list-sessions`. A server that is still there keeps its directory and
    socket and ServerNotStopped is raised, so the caller fails the measurement."""
    for _ in range(2):
        try:
            subprocess.run(base + ["kill-server"], capture_output=True, timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            pass
        if identity is None or not server_alive(identity):
            break
    if identity is not None:
        for sent in (signal.SIGTERM, signal.SIGKILL):
            if not server_alive(identity):
                break
            try:
                os.kill(identity[0], sent)
            except ProcessLookupError:
                break
            deadline = time.time() + 3
            while time.time() < deadline and server_alive(identity):
                time.sleep(0.1)
        gone = not server_alive(identity)
    else:
        try:
            gone = subprocess.run(base + ["list-sessions"], capture_output=True, timeout=10).returncode != 0
        except (OSError, subprocess.TimeoutExpired):
            gone = False   # cannot tell: keep the socket
    if fd is not None:
        try:
            os.close(fd)
        except OSError:
            pass
    if client_pid is not None:
        deadline = time.time() + 5
        while time.time() < deadline:
            try:
                if os.waitpid(client_pid, os.WNOHANG)[0]:
                    break
            except ChildProcessError:
                break
            time.sleep(0.1)
        else:
            try:
                os.kill(client_pid, 9)   # our own attach client, still attached to a server that would not stop
                os.waitpid(client_pid, 0)
            except (ProcessLookupError, ChildProcessError):
                pass
    if not gone:
        raise ServerNotStopped(base[base.index("-S") + 1])
    shutil.rmtree(work, ignore_errors=True)


def tmux_servers():
    """The pids of every `tmux` process now (a before and after comparison shows what a run left behind)."""
    found = frozenset()
    for entry in Path("/proc").glob("[0-9]*"):
        try:
            if (entry / "comm").read_text().startswith("tmux"):
                found = found | {int(entry.name)}
        except (OSError, ValueError):
            continue
    return found


def shutdown_control(measure):
    """Three controls with a wrapper in place of tmux that REFUSES `kill-server`. (1) It answers honestly about the server's pid: `measure()` must still finish, having stopped its own server by that pid, and leave no
    new tmux process and no socket directory. (2) It also lies about the pid (init's): the name check refuses the identity, so nothing is signaled, the measurement must raise ServerNotStopped, the socket must still be
    there and the server must still answer; the control then stops that server itself. (3) It answers the pid of ANOTHER private tmux server (alive, named tmux, started with a different socket): only the command-line
    check refuses it, so that server must not be signaled (it must still answer afterwards) and the measurement must raise ServerNotStopped and keep its socket; the control then stops both servers. Needs tmux;
    returns (ok, detail), or (None, why) without it."""
    global TMUX
    if not TMUX:
        return None, "skipped (tmux is not installed)"
    real = TMUX
    details, ok = [], True
    for label, mode in (("kill-server refused, honest pid", "honest"), ("kill-server refused and a false pid", "init"), ("kill-server refused and the pid of another tmux server", "other")):
        with tempfile.TemporaryDirectory(prefix="tw", dir="/tmp") as raw:
            other_socket = None
            answer = ""
            if mode == "init":
                answer = 'case " $* " in *" display-message "*) echo 1; exit 0;; esac\n'
            elif mode == "other":
                other_socket = str(Path(raw) / "o.sock")
                subprocess.run([real, "-S", other_socket, "-f", "/dev/null", "new-session", "-d", "sleep 120"], check=True, capture_output=True)
                other_pid = int(subprocess.run([real, "-S", other_socket, "-f", "/dev/null", "display-message", "-p", "#{pid}"], capture_output=True, text=True, timeout=10).stdout.strip())
                answer = f'case " $* " in *" display-message "*) echo {other_pid}; exit 0;; esac\n'
            wrapper = Path(raw) / "tmux"
            wrapper.write_text(f'#!/bin/sh\ncase " $* " in *" kill-server "*) exit 1;; esac\n{answer}exec {real} "$@"\n')
            wrapper.chmod(0o755)
            before = tmux_servers()
            TMUX = str(wrapper)
            try:
                try:
                    measure()
                    finished, socket = True, None
                except ServerNotStopped as failure:
                    finished, socket = False, failure.socket
            finally:
                TMUX = real
            if mode == "honest":
                good = finished and not (tmux_servers() - before)
                details.append(f"{label}: the measurement finished {finished}, new tmux processes left {len(tmux_servers() - before)}")
            else:
                kept = socket is not None and Path(socket).exists()
                alive = kept and subprocess.run([real, "-S", socket, "list-sessions"], capture_output=True).returncode == 0
                other_alive = other_socket is None or subprocess.run([real, "-S", other_socket, "list-sessions"], capture_output=True).returncode == 0
                if socket is not None:
                    subprocess.run([real, "-S", socket, "kill-server"], capture_output=True)
                    shutil.rmtree(Path(socket).parent, ignore_errors=True)
                if other_socket is not None:
                    subprocess.run([real, "-S", other_socket, "kill-server"], capture_output=True)
                good = not finished and kept and alive and other_alive
                details.append(f"{label}: the measurement raised {not finished}, the socket was kept {kept}, the server still answered {alive}"
                               + (f", the other server was left alone {other_alive}" if other_socket else "") + ", then the control stopped it")
            ok = ok and good
    return ok, "; ".join(details)


def run(option, hold=0):
    """One run: a private server, a pane that prints a few lines, a client in a pty that counts the synchronized-output pairs tmux writes to it. `hold` keeps the pane (and so the server) alive that many seconds
    longer, for the shutdown-failure control, which needs a server that is still running when the probe stops it."""
    work = tempfile.mkdtemp(prefix="ts", dir="/tmp")   # short path: a unix socket path is limited to about 100 bytes
    socket = os.path.join(work, "tmux.sock")
    base = [TMUX, "-S", socket, "-f", "/dev/null"]
    pid = fd = identity = None
    counted = None
    try:
        subprocess.run(base + ["new-session", "-d", "-x", "100", "-y", "24", "sh -c 'sleep 1; i=0; while [ $i -lt 8 ]; do echo line$i; i=$((i+1)); sleep 0.3; done; sleep 2" + (f"; sleep {hold}" if hold else "") + "'"], check=True, capture_output=True, cwd=work)
        identity = server_identity(base)
        if option:
            subprocess.run(base + ["set-option", "-sa", "terminal-features", option], check=True, capture_output=True)
        pid, fd = pty.fork()
        if pid == 0:
            try:
                os.environ["TERM"] = "xterm-256color"
                os.execv(TMUX, [TMUX, "-S", socket, "-f", "/dev/null", "attach"])
            finally:
                os._exit(127)   # the child never returns into the parent's code (and its cleanup) when the exec fails
        collected, deadline = b"", time.time() + 6
        while time.time() < deadline:
            ready, _, _ = select.select([fd], [], [], 0.2)
            if ready:
                try:
                    chunk = os.read(fd, 65536)
                except OSError:
                    break
                if not chunk:
                    break
                collected += chunk
        counted = (collected.count(SET), collected.count(RESET))
    finally:
        stop_server(base, Path(work), pid, fd, identity)   # raises ServerNotStopped (and keeps the socket) when the server is still there
    return counted


if "--selftest" in sys.argv[1:]:
    ok, detail = shutdown_control(lambda: run(None, hold=30))
    print("SKIP shutdown-failure control:" if ok is None else ("PASS shutdown-failure control:" if ok else "FAIL shutdown-failure control:"), detail)
    sys.exit(0 if ok in (None, True) else 1)
print("tmux:", subprocess.run([TMUX, "-V"], capture_output=True, text=True).stdout.strip())
declared, plain = run("xterm*:sync"), run(None)
print("ESC[?2026h / ESC[?2026l written to the outer terminal, with terminal-features xterm*:sync:", declared)
print("the same without it (negative control):", plain)
ok = declared[0] > 0 and declared[0] == declared[1] and plain == (0, 0)
print("synchronized output is emitted only when declared:", ok)
sys.exit(0 if ok else 1)
