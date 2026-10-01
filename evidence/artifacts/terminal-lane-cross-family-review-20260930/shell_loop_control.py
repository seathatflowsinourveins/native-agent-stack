#!/usr/bin/env python3
"""Why the pty probes end BY a latched signal instead of exiting 128 + N (finding F1 of the post-merge read, 2026-09-30). Two loops of three runs each are started under `bash -c`; SIGINT goes to the whole process group
0.5 s after the start, as Ctrl-C does. In the first loop the child catches SIGINT, finishes its cleanup and EXITS 130 (what the probes did); in the second it finishes its cleanup, resets SIGINT to its default action and
sends the signal to itself (what the probes do now). Bash tells the two apart: after an exit 130 it runs the next command, after a death by SIGINT it stops the loop (Cracauer, "Proper handling of SIGINT/SIGQUIT",
cons.org/cracauer/sigint.html: a shell can only be told by a child that kills itself with the signal). Prints one line per loop. Exit 0 when the first loop went on for all three runs and the second stopped before the first
`continued` line; exit 1 when bash behaved differently (then the premise of the change does not hold on this host). Writes two temporary child scripts under /var/tmp and removes them. usage: shell_loop_control.py"""
import os
import signal
import subprocess
import sys
import time

EXIT_130 = ("import signal, sys, time\n"
            "signal.signal(signal.SIGINT, lambda *a: None)\n"
            "time.sleep(2)\n"
            "sys.exit(130)\n")
DIE_BY_SIGINT = ("import os, signal, time\n"
                 "signal.signal(signal.SIGINT, lambda *a: None)\n"
                 "time.sleep(2)\n"
                 "signal.signal(signal.SIGINT, signal.SIG_DFL)\n"
                 "os.kill(os.getpid(), signal.SIGINT)\n"
                 "time.sleep(5)\n")


def run(code):
    script = f"/var/tmp/shell_loop_control_{os.getpid()}.py"
    with open(script, "w", encoding="utf-8") as handle:
        handle.write(code)
    try:
        loop = subprocess.Popen(["bash", "-c", f"for i in 1 2 3; do python3 {script}; echo continued-$i; done"], start_new_session=True, stdout=subprocess.PIPE, text=True)
        time.sleep(0.5)
        os.killpg(loop.pid, signal.SIGINT)
        output, _ = loop.communicate(timeout=60)
        return loop.returncode, output.split()
    finally:
        os.unlink(script)


exited_code, exited_lines = run(EXIT_130)
died_code, died_lines = run(DIE_BY_SIGINT)
print(f"child exits 130 after its cleanup: bash exit {exited_code}, lines {exited_lines}")
print(f"child ends BY SIGINT after its cleanup: bash exit {died_code}, lines {died_lines}")
went_on = exited_lines == ["continued-1", "continued-2", "continued-3"]
stopped = died_lines == []
print(f"the loop went on after an exit 130: {went_on}; the loop stopped after a death by SIGINT: {stopped}")
sys.exit(0 if went_on and stopped else 1)
