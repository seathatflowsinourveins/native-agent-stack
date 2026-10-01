#!/usr/bin/env python3
"""Does tmux pass a BEL from a pane to the outer terminal, so a Notification hook's bell still rings for an agent-team lead in a tmux pane? The outer terminal here is a Python pty
(TERM=xterm-256color), which stands for Windows Terminal only in that a bare BEL written to it is what the hook's terminalSequence produces; nothing about Windows Terminal itself is measured.

Runs a private tmux server (-S <a socket inside its own temporary directory>, an empty config, no user config read) with one window whose command prints one BEL after a delay, attaches a client
in a pty for a few seconds and counts the BEL bytes that tmux writes to the client's terminal, after removing OSC sequences (whose terminator is also a BEL byte).
Arms: default options; `bell-action none` (negative control: the count must drop to 0 or the probe cannot tell forwarding from no forwarding); `visual-bell on`
(tmux shows a message instead of ringing); `bell-action any` set explicitly (the default that `tmux show-options -g bell-action` reports on 3.4; the manual's entry lists the values only). Also a BEL-free control command, which must count 0.
Stops only its own server and verifies that it is gone before it removes the socket directory (a server that will not stop keeps its socket and fails the probe). Prints counts and the tmux version; nothing else. Exit 0 only when every arm read its expected count (1, 1, 0, 0, 0), including the negative controls
and the visual-bell arm; `--selftest` checks that verdict on made-up counts without tmux (a wrong count in any single arm must give a nonzero verdict).
usage: python3 -B tmux_bell_probe.py [--selftest]
"""
import os, pty, re, select, shutil, signal, subprocess, sys, tempfile, time
from pathlib import Path

TMUX = shutil.which("tmux")
OSC = re.compile(rb"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)")


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
    pid, started = identity
    try:
        return start_time(pid) == started and (Path("/proc") / str(pid) / "comm").read_text().startswith("tmux")
    except OSError:
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
    """Two controls with a wrapper in place of tmux that REFUSES `kill-server`. (1) It answers honestly about the server's pid: `measure()` must still finish, having stopped its own server by that pid, and leave no
    new tmux process and no socket directory. (2) It also lies about the pid (init's): the identity is refused, so nothing is signaled, the measurement must raise ServerNotStopped, the socket must still be there and
    the server must still answer; the control then stops that server itself. Needs tmux; returns (ok, detail), or (None, why) without it."""
    global TMUX
    if not TMUX:
        return None, "skipped (tmux is not installed)"
    real = TMUX
    details, ok = [], True
    for label, lie in (("kill-server refused, honest pid", False), ("kill-server refused and a false pid", True)):
        with tempfile.TemporaryDirectory(prefix="tw", dir="/tmp") as raw:
            wrapper = Path(raw) / "tmux"
            answer = 'case " $* " in *" display-message "*) echo 1; exit 0;; esac\n' if lie else ""
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
            if not lie:
                good = finished and not (tmux_servers() - before)
                details.append(f"{label}: the measurement finished {finished}, new tmux processes left {len(tmux_servers() - before)}")
            else:
                kept = socket is not None and Path(socket).exists()
                alive = kept and subprocess.run([real, "-S", socket, "list-sessions"], capture_output=True).returncode == 0
                if socket is not None:
                    subprocess.run([real, "-S", socket, "kill-server"], capture_output=True)
                    shutil.rmtree(Path(socket).parent, ignore_errors=True)
                good = not finished and kept and alive
                details.append(f"{label}: the measurement raised {not finished}, the socket was kept {kept}, the server still answered {alive}, then the control stopped it")
            ok = ok and good
    return ok, "; ".join(details)


def bells(command, options, seconds=6.0):
    work = Path(tempfile.mkdtemp(prefix="tb", dir="/tmp"))   # short path: a unix socket path is limited to about 100 bytes
    socket = str(work / "tmux.sock")
    base = [TMUX, "-S", socket, "-f", "/dev/null"]
    pid = fd = identity = None
    counted = None
    try:
        subprocess.run(base + ["new-session", "-d", "-x", "100", "-y", "24", command], check=True, capture_output=True, cwd=work)
        identity = server_identity(base)
        for option in options:
            subprocess.run(base + ["set-option", "-g", *option.split()], check=True, capture_output=True)
        pid, fd = pty.fork()
        if pid == 0:
            os.environ["TERM"] = "xterm-256color"
            os.execv(TMUX, [TMUX, "-S", socket, "-f", "/dev/null", "attach"])
        collected, deadline = b"", time.time() + seconds
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
        counted = OSC.sub(b"", collected).count(b"\x07")
    finally:
        stop_server(base, work, pid, fd, identity)   # raises ServerNotStopped (and keeps the socket) when the server is still there
    return counted


BELL = "sh -c 'sleep 2; printf \"\\a\"; sleep 4'"
QUIET = "sh -c 'sleep 2; printf x; sleep 4'"
ARMS = [("default options, one BEL from the pane", BELL, []), ("bell-action any set explicitly (tmux 3.4's reported default), one BEL", BELL, ["bell-action any"]),
        ("negative control: bell-action none", BELL, ["bell-action none"]), ("visual-bell on", BELL, ["visual-bell on"]), ("control: pane prints no BEL", QUIET, [])]
EXPECTED = (1, 1, 0, 0, 0)  # in the order of ARMS


def verdict(counts):
    """True only when every arm read its expected count: forwarding by default and with bell-action any, none with bell-action none, none with visual-bell on, none from a pane
    that prints no BEL (the negative controls that show the probe can tell forwarding from no forwarding)."""
    return tuple(counts) == EXPECTED


def selftest():
    problems = []
    if not verdict(EXPECTED):
        problems.append("the expected counts were refused")
    for index in range(len(EXPECTED)):
        wrong = list(EXPECTED)
        wrong[index] = 1 - wrong[index] if wrong[index] in (0, 1) else 0
        if verdict(wrong):
            problems.append(f"a wrong count in arm {index} ({ARMS[index][0]}) was accepted")
    if verdict(EXPECTED[:-1]) or verdict(list(EXPECTED) + [0]):
        problems.append("a wrong number of arms was accepted")
    ok, detail = shutdown_control(lambda: bells(BELL, [], seconds=2.0))
    if ok is None:
        print("SKIP shutdown-failure control:", detail)
    else:
        print(("PASS " if ok else "FAIL ") + "shutdown-failure control:", detail)
        if not ok:
            problems.append("a server that could not be stopped was not reported with its socket kept")
    print(f"selftest: {len(EXPECTED) + 4} checks, {len(problems)} problems")
    for problem in problems:
        print("  -", problem)
    return 1 if problems else 0


def main():
    print("tmux:", subprocess.run([TMUX, "-V"], capture_output=True, text=True).stdout.strip())
    counts = []
    for label, command, options in ARMS:
        counts.append(bells(command, options))
        print(f"  {label}: {counts[-1]} BEL byte(s) reached the outer terminal")
    ok = verdict(counts)
    print("probe discriminates (1, 1, 0, visual-bell 0, control 0):", ok)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(selftest() if "--selftest" in sys.argv[1:] else main())
