#!/usr/bin/env python3
"""Does tmux 3.4 wrap its redraws in DEC mode 2026 (synchronized output) when the outer terminal is declared to support it? A private tmux server (-S <a socket inside its own temporary directory>, empty config), a client in a
pty as the outer terminal, once with `terminal-features 'xterm*:sync'` and once without it (negative control); counts ESC[?2026h and ESC[?2026l in what tmux writes to the client. Reads and writes
only inside its own temporary directory; kills only its own server. usage: python3 -B tmux_sync_probe.py"""
import os, pty, select, shutil, subprocess, sys, tempfile, time

TMUX = shutil.which("tmux")
SET, RESET = b"\x1b[?2026h", b"\x1b[?2026l"


def run(option):
    work = tempfile.mkdtemp(prefix="ts", dir="/tmp")   # short path: a unix socket path is limited to about 100 bytes
    socket = os.path.join(work, "tmux.sock")
    base = [TMUX, "-S", socket, "-f", "/dev/null"]
    try:
        subprocess.run(base + ["new-session", "-d", "-x", "100", "-y", "24", "sh -c 'sleep 1; i=0; while [ $i -lt 8 ]; do echo line$i; i=$((i+1)); sleep 0.3; done; sleep 2'"], check=True, capture_output=True, cwd=work)
        if option:
            subprocess.run(base + ["set-option", "-sa", "terminal-features", option], check=True, capture_output=True)
        pid, fd = pty.fork()
        if pid == 0:
            os.environ["TERM"] = "xterm-256color"
            os.execv(TMUX, [TMUX, "-S", socket, "-f", "/dev/null", "attach"])
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
        subprocess.run(base + ["kill-server"], capture_output=True)
        try:
            os.close(fd)
        except OSError:
            pass
        os.waitpid(pid, 0)
        return collected.count(SET), collected.count(RESET)
    finally:
        subprocess.run([TMUX, "-S", socket, "kill-server"], capture_output=True)
        shutil.rmtree(work, ignore_errors=True)


print("tmux:", subprocess.run([TMUX, "-V"], capture_output=True, text=True).stdout.strip())
declared, plain = run("xterm*:sync"), run(None)
print("ESC[?2026h / ESC[?2026l written to the outer terminal, with terminal-features xterm*:sync:", declared)
print("the same without it (negative control):", plain)
ok = declared[0] > 0 and declared[0] == declared[1] and plain == (0, 0)
print("synchronized output is emitted only when declared:", ok)
sys.exit(0 if ok else 1)
