#!/usr/bin/env python3
"""Does tmux 3.4 wrap its redraws in DEC mode 2026 (synchronized output) when the outer terminal is declared to support it? A private tmux server (-S <a socket inside its own temporary directory>, empty config), a client in a
pty as the outer terminal, once with `terminal-features 'xterm*:sync'` and once without it (negative control); counts ESC[?2026h and ESC[?2026l in what tmux writes to the client. Reads and writes
only inside its own temporary directory; stops only its own server and verifies that it is gone before removing the socket directory (a server that will not stop keeps its socket and fails the probe).
`--selftest` runs the shutdown-failure control. usage: python3 -B tmux_sync_probe.py [--selftest]"""
import os, pty, re, select, shutil, signal, subprocess, sys, tempfile, time
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
    """(pid, start time) of the private server, read right after it started: `display-message -p '#{pid}'` answers with its pid, and /proc must say that the process is the server of THIS socket: its command name is exactly
    `tmux: server` and its argv, which the server keeps as it was started, holds the option `-S` followed by OUR socket path as a whole argument. The comparison is exact on purpose: a substring test would accept another server
    whose socket path merely contains ours (finding U1 of the post-merge GPT read). The start time tells the same process from a later one that reused the pid. None when that cannot be established (then nothing is ever signaled)."""
    try:
        pid = int(subprocess.run(base + ["display-message", "-p", "#{pid}"], capture_output=True, text=True, timeout=10).stdout.strip())
        socket = base[base.index("-S") + 1].encode()
        argv = [part for part in (Path("/proc") / str(pid) / "cmdline").read_bytes().split(b"\0") if part]
        if (Path("/proc") / str(pid) / "comm").read_text().strip() != "tmux: server" or b"-S" not in argv or argv[argv.index(b"-S") + 1] != socket:
            return None   # not a tmux server, or not the one that was started with OUR socket
        return pid, start_time(pid)
    except (OSError, ValueError, IndexError, subprocess.TimeoutExpired):
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


WORK_PREFIX = "ts"      # the prefix of the directories this probe makes under /tmp for its sockets (`mkdtemp` adds eight random characters)
OWN_SOCKET_DIRECTORIES = ("/tmp/tb", "/tmp/tw", "/tmp/ts")      # where the probes of this family put their private sockets


def work_directories():
    """The directories under /tmp that look like this probe's own socket directories now (its prefix and eight random characters of `mkdtemp`: a before and after comparison shows what a run left behind; a directory of another tool cannot match)."""
    return frozenset(path.name for path in Path("/tmp").glob(WORK_PREFIX + "*") if path.is_dir() and re.fullmatch(WORK_PREFIX + "[a-z0-9_]{8}", path.name))


def server_gone(real, socket, seconds=2.0):
    """True once no tmux server answers on `socket` (a server that was just told to exit may need a moment: it is asked again for up to `seconds`)."""
    deadline = time.time() + seconds
    while True:
        if subprocess.run([real, "-S", socket, "list-sessions"], capture_output=True).returncode != 0:
            return True
        if time.time() >= deadline:
            return False
        time.sleep(0.1)


def remove_work_directory(socket):
    """Remove the directory that holds a socket of ours, after its server was stopped, but only a directory this probe made: a direct child of /tmp that looks like its own `mkdtemp` result, never the parent of an arbitrary recorded path."""
    parent = Path(socket).parent
    if parent.parent == Path("/tmp") and re.fullmatch(WORK_PREFIX + "[a-z0-9_]{8}", parent.name):
        shutil.rmtree(parent, ignore_errors=True)


def tmux_servers():
    """The pids of the `tmux` processes that were started with a socket in one of our own directories (a before and after comparison shows what a run left behind): a tmux process of another session, on another socket, can neither fail a control nor be
    mistaken for ours."""
    found = frozenset()
    for entry in Path("/proc").glob("[0-9]*"):
        try:
            if not (entry / "comm").read_text().startswith("tmux"):
                continue
            argv = (entry / "cmdline").read_bytes().split(b"\0")
            if b"-S" in argv and argv[argv.index(b"-S") + 1].decode(errors="replace").startswith(OWN_SOCKET_DIRECTORIES):
                found = found | {int(entry.name)}
        except (OSError, ValueError, IndexError):
            continue
    return found


WRAPPER = """#!/bin/sh
prev=""; sock=""
for a in "$@"; do [ "$prev" = "-S" ] && sock="$a"; prev="$a"; done
[ -n "$sock" ] && echo "$sock" >> "$(dirname "$0")/sockets"
case " $* " in *" kill-server "*) exit 1;; esac
@ANSWER@
exec @REAL@ "$@"
"""


def shutdown_control(measure):
    """Four controls with a wrapper in place of tmux that REFUSES `kill-server` and notes every socket it is asked about. (1) It answers honestly about the server's pid: `measure()` must still finish, having stopped its own
    server by that pid, and leave no new tmux process and no socket directory. (2) It also lies about the pid (init's): the name check refuses the identity, so nothing is signaled, the measurement must raise ServerNotStopped,
    the socket must still be there and the server must still answer. (3) It answers the pid of ANOTHER private tmux server (alive, named `tmux: server`, started with a different socket): only the comparison of the socket
    argument refuses it, so that server must be left alone. (4) It answers the pid of a server whose socket path HAS OURS AS A PREFIX (`<ours>.old`): a substring test accepts it, only an exact comparison refuses it, so it too
    must be left alone. For (3) and (4) the measurement must raise ServerNotStopped and keep its socket. Every server the control caused is stopped by its exact socket path (never by pid or by name) in a `finally`, also when the
    measurement raises something else (finding U12 of the post-merge GPT read). The directory of every recorded socket is removed there too, once its server is gone (`remove_work_directory`; a server that still answers keeps its directory and fails the control), and after each mode the directories under /tmp that look like
    this probe's own must be the ones that were there before (finding B3 of the Codex review bot's read of the repairs: before it, the claim in (1) of "no socket directory" was not checked). Needs tmux; returns (ok, detail), or (None, why) without it."""
    global TMUX
    if not TMUX:
        return None, "skipped (tmux is not installed)"
    real = TMUX
    details, ok = [], True
    for label, mode in (("kill-server refused, honest pid", "honest"), ("kill-server refused and a false pid", "init"), ("kill-server refused and the pid of another tmux server", "other"),
                        ("kill-server refused and the pid of a server whose socket path has ours as a prefix", "prefix")):
        before_dirs = work_directories()
        with tempfile.TemporaryDirectory(prefix="tw", dir="/tmp") as raw:
            wrapper = Path(raw) / "tmux"
            caused, socket, other_socket = [], None, None
            try:
                answer = ""
                if mode == "init":
                    answer = 'case " $* " in *" display-message "*) echo 1; exit 0;; esac'
                elif mode == "other":
                    other_socket = str(Path(raw) / "o.sock")
                    caused.append(other_socket)
                    subprocess.run([real, "-S", other_socket, "-f", "/dev/null", "new-session", "-d", "sleep 120"], check=True, capture_output=True)
                    other_pid = int(subprocess.run([real, "-S", other_socket, "-f", "/dev/null", "display-message", "-p", "#{pid}"], capture_output=True, text=True, timeout=10).stdout.strip())
                    answer = f'case " $* " in *" display-message "*) echo {other_pid}; exit 0;; esac'
                elif mode == "prefix":
                    answer = ('case " $* " in *" display-message "*) other="$sock.old"; ' + f'{real} -S "$other" -f /dev/null has-session 2>/dev/null || {real} -S "$other" -f /dev/null new-session -d "sleep 120"; '
                              + f'echo "$other" >> "$(dirname "$0")/sockets"; {real} -S "$other" -f /dev/null display-message -p "#{{pid}}"; exit 0;; esac')
                wrapper.write_text(WRAPPER.replace("@ANSWER@", answer).replace("@REAL@", real))
                wrapper.chmod(0o755)
                before = tmux_servers()
                TMUX = str(wrapper)
                try:
                    try:
                        measure()
                        finished = True
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
                    target = other_socket if mode == "other" else (socket + ".old" if socket is not None and mode == "prefix" else None)
                    other_alive = mode == "init" or (target is not None and subprocess.run([real, "-S", target, "list-sessions"], capture_output=True).returncode == 0)
                    good = not finished and kept and alive and other_alive
                    details.append(f"{label}: the measurement raised {not finished}, the socket was kept {kept}, the server still answered {alive}"
                                   + ("" if mode == "init" else f", the other server was left alone {other_alive}") + ", then the control stopped it")
                ok = ok and good
            finally:
                recorded = Path(raw) / "sockets"
                known = set(caused) | (set(recorded.read_text().split()) if recorded.exists() else set()) | ({socket} if socket else set())
                for each in sorted(known):
                    subprocess.run([real, "-S", each, "kill-server"], capture_output=True)      # by exact socket path, never by pid or by name
                for each in sorted(known):
                    if server_gone(real, each):      # its server is gone: one that still answers keeps its socket, as `stop_server` does, and the control reports the directory it left
                        remove_work_directory(each)      # the directory of a socket of ours: also when the measurement raised something other than ServerNotStopped
            left_dirs = len(work_directories() - before_dirs)      # after the cleanup above: nothing of ours may remain under /tmp
            ok = ok and not left_dirs
            details[-1] += f", socket directories left behind {left_dirs}"
    return ok, "; ".join(details)


def cleanup_control(measure):
    """The control's own cleanup (finding U12): when the measurement raises something other than ServerNotStopped, no tmux server that `shutdown_control` caused may be left behind or lose its socket. The control runs
    twice, once with the failure in the third mode (another server) and once in the fourth (a prefix server); the failing measurement first runs the real one (so that the servers exist), then raises. The failure must
    propagate and no new tmux process and no socket directory may remain (finding B3 of the Codex review bot's read of this change: the failing path never removed the directories). Needs tmux; returns (ok, detail), or (None, why) without it."""
    if not TMUX:
        return None, "skipped (tmux is not installed)"
    results = []
    for number, mode in ((3, "another server"), (4, "a prefix server")):
        count = {"n": 0}

        def failing(number=number, count=count):
            count["n"] += 1
            if count["n"] == number:
                try:
                    measure()
                except ServerNotStopped:
                    pass
                raise RuntimeError("an unexpected failure of the measurement")
            return measure()

        before, before_dirs = tmux_servers(), work_directories()
        try:
            shutdown_control(failing)
            raised = False
        except RuntimeError:
            raised = True
        results.append((mode, raised, len(tmux_servers() - before), len(work_directories() - before_dirs)))
    ok = all(raised and not left and not dirs for _mode, raised, left, dirs in results)
    return ok, "; ".join(f"a failure with {mode}: it propagated {raised}, tmux processes left behind {left}, socket directories left behind {dirs}" for mode, raised, left, dirs in results)


def scope_control():
    """`remove_work_directory` removes the directory of a socket only when this probe made it: a directory named like its own `mkdtemp` result goes; an unrelated directory under /tmp and a directory with our prefix but another shape stay, whatever sockets
    were recorded in them. Needs no tmux. Returns (ok, detail)."""
    own = Path(tempfile.mkdtemp(prefix=WORK_PREFIX, dir="/tmp"))
    unrelated = Path(tempfile.mkdtemp(prefix="unrelated-", dir="/tmp"))
    near = Path(tempfile.mkdtemp(prefix=WORK_PREFIX + "x-", dir="/tmp"))      # our prefix, not the shape of our `mkdtemp` result
    try:
        for each in (own, unrelated, near):
            (each / "tmux.sock").write_text("")
            remove_work_directory(str(each / "tmux.sock"))
        removed, kept_unrelated, kept_near = not own.exists(), unrelated.exists(), near.exists()
    finally:
        for each in (own, unrelated, near):
            shutil.rmtree(each, ignore_errors=True)
    return removed and kept_unrelated and kept_near, f"a directory of this probe was removed {removed}, an unrelated directory was kept {kept_unrelated}, a directory with our prefix and another shape was kept {kept_near}"


def run(option, hold=0):
    """One run: a private server, a pane that prints a few lines, a client in a pty that counts the synchronized-output pairs tmux writes to it. `hold` keeps the pane (and so the server) alive that many seconds
    longer, for the shutdown-failure control, which needs a server that is still running when the probe stops it."""
    work = tempfile.mkdtemp(prefix=WORK_PREFIX, dir="/tmp")   # short path: a unix socket path is limited to about 100 bytes
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
    cleaned, cleanup_detail = cleanup_control(lambda: run(None, hold=30))
    print("SKIP cleanup control:" if cleaned is None else ("PASS cleanup control:" if cleaned else "FAIL cleanup control:"), cleanup_detail)
    scoped, scope_detail = scope_control()
    print("PASS scope control:" if scoped else "FAIL scope control:", scope_detail)
    sys.exit(0 if ok in (None, True) and cleaned in (None, True) and scoped else 1)
print("tmux:", subprocess.run([TMUX, "-V"], capture_output=True, text=True).stdout.strip())
declared, plain = run("xterm*:sync"), run(None)
print("ESC[?2026h / ESC[?2026l written to the outer terminal, with terminal-features xterm*:sync:", declared)
print("the same without it (negative control):", plain)
ok = declared[0] > 0 and declared[0] == declared[1] and plain == (0, 0)
print("synchronized output is emitted only when declared:", ok)
sys.exit(0 if ok else 1)
