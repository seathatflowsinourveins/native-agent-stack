#!/usr/bin/env python3
"""Does tmux pass a BEL from a pane to the outer terminal, so a Notification hook's bell still rings for an agent-team lead in a tmux pane? The outer terminal here is a Python pty
(TERM=xterm-256color), which stands for Windows Terminal only in that a bare BEL written to it is what the hook's terminalSequence produces; nothing about Windows Terminal itself is measured.

Runs a private tmux server (-L <unique socket>, an empty config, no user config read) with one window whose command prints one BEL after a delay, attaches a client
in a pty for a few seconds and counts the BEL bytes that tmux writes to the client's terminal, after removing OSC sequences (whose terminator is also a BEL byte).
Arms: default options; `bell-action none` (negative control: the count must drop to 0 or the probe cannot tell forwarding from no forwarding); `visual-bell on`
(tmux shows a message instead of ringing); `bell-action any` set explicitly (the default that `tmux show-options -g bell-action` reports on 3.4; the manual's entry lists the values only). Also a BEL-free control command, which must count 0.
Kills only its own server. Prints counts and the tmux version; nothing else.
usage: python3 -B tmux_bell_probe.py
"""
import os, pty, re, select, shutil, subprocess, sys, tempfile, time
from pathlib import Path

TMUX = shutil.which("tmux")
OSC = re.compile(rb"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)")


def bells(command, options, seconds=6.0):
    work = Path(tempfile.mkdtemp(prefix="tb"))
    socket = f"probe{os.getpid()}"
    base = [TMUX, "-L", socket, "-f", "/dev/null"]
    try:
        subprocess.run(base + ["new-session", "-d", "-x", "100", "-y", "24", command], check=True, capture_output=True, cwd=work)
        for option in options:
            subprocess.run(base + ["set-option", "-g", *option.split()], check=True, capture_output=True)
        pid, fd = pty.fork()
        if pid == 0:
            os.environ["TERM"] = "xterm-256color"
            os.execv(TMUX, [TMUX, "-L", socket, "-f", "/dev/null", "attach"])
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
        subprocess.run(base + ["kill-server"], capture_output=True)
        try:
            os.close(fd)
        except OSError:
            pass
        os.waitpid(pid, 0)
        return OSC.sub(b"", collected).count(b"\x07")
    finally:
        subprocess.run([TMUX, "-L", socket, "kill-server"], capture_output=True)
        shutil.rmtree(work, ignore_errors=True)


BELL = "sh -c 'sleep 2; printf \"\\a\"; sleep 4'"
QUIET = "sh -c 'sleep 2; printf x; sleep 4'"
print("tmux:", subprocess.run([TMUX, "-V"], capture_output=True, text=True).stdout.strip())
arms = [("default options, one BEL from the pane", BELL, []), ("bell-action any set explicitly (tmux 3.4's reported default), one BEL", BELL, ["bell-action any"]),
        ("negative control: bell-action none", BELL, ["bell-action none"]), ("visual-bell on", BELL, ["visual-bell on"]), ("control: pane prints no BEL", QUIET, [])]
results = {}
for label, command, options in arms:
    results[label] = bells(command, options)
    print(f"  {label}: {results[label]} BEL byte(s) reached the outer terminal")
ok = (results[arms[0][0]] == 1 and results[arms[1][0]] == 1 and results[arms[2][0]] == 0 and results[arms[4][0]] == 0)
print("probe discriminates (1, 1, 0, control 0):", ok)
sys.exit(0 if ok else 1)
