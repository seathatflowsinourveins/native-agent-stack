#!/usr/bin/env python3
"""Why the pty probes end BY a latched signal instead of exiting 128 + N, and for which shells that matters (finding F1 of the post-merge read and U9 and U10 of the post-merge GPT read, 2026-10). A shell loop of three runs of a
child (`<shell> -c 'for i in 1 2 3; do python3 <child>; echo continued-$i; done'`) is started in its own session; the child installs a SIGINT handler, says it is ready (a file with its pid), waits up to two seconds for the signal
and then ends one of three ways: it EXITS 130 after its cleanup, it DIES BY SIGINT after its cleanup (it resets the signal to its default action and sends it to itself), or, as a rejecting control, it kills its PARENT shell with
SIGTERM. SIGINT is sent once, after the ready file exists, either to the whole process group (what Ctrl-C does: the shell receives it too) or to the child only (the shell does not). Measured expectations, each shell that is
installed (bash and dash are named; others are not measured, so the documents claim nothing about them):
  bash, SIGINT to the group:    exit 130 -> the loop goes on (3 runs, shell exit 0); dies by SIGINT -> the loop stops (0 runs, shell killed by SIGINT)
  bash, SIGINT to the child only: both arms -> the loop goes on (the shell must have received the SIGINT too: Cracauer's wait-and-cooperative-exit)
  dash, SIGINT to the group:    both arms -> the loop stops (dash exits on its own SIGINT whatever the child does)
  dash, SIGINT to the child only: both arms -> the loop goes on
A death by SIGINT counts only when the shell itself ended with -SIGINT and printed no `continued` line: a loop that stopped because the shell was killed by another signal (the control) is NOT accepted. The scripts live in
a private directory (tempfile.mkdtemp, mode 0700), never at a predictable path. Prints one line per measurement and a verdict; exit 0 when every measurement equals its expectation and the control is rejected, 1 otherwise (then the
documents' statement about shells does not hold on this host). Cracauer, "Proper handling of SIGINT/SIGQUIT", https://www.cons.org/cracauer/sigint.html. usage: shell_loop_control.py"""
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

PRELUDE = ("import os, signal, sys, time\n"
           "got = []\n"
           "signal.signal(signal.SIGINT, lambda *a: got.append(1))\n"
           "open(sys.argv[1], 'w').write(str(os.getpid()))\n"
           "deadline = time.time() + 2\n"
           "while not got and time.time() < deadline:\n"
           "    time.sleep(0.02)\n")
CHILDREN = {
    "exit 130": PRELUDE + "sys.exit(130)\n",
    "dies by SIGINT": PRELUDE + "signal.signal(signal.SIGINT, signal.SIG_DFL)\nos.kill(os.getpid(), signal.SIGINT)\ntime.sleep(5)\n",
    "kills its parent shell with SIGTERM": PRELUDE + "os.kill(os.getppid(), signal.SIGTERM)\ntime.sleep(5)\n",
}


def ended_by_sigint(returncode, continued):
    """The loop's verdict for a death by SIGINT: the shell itself was killed by SIGINT and printed no `continued` line."""
    return returncode == -signal.SIGINT and not continued


def measure(shell, workdir, child, target):
    script, ready = Path(workdir) / "child.py", Path(workdir) / "ready"
    script.write_text(CHILDREN[child], encoding="utf-8")
    if ready.exists():
        ready.unlink()
    loop = subprocess.Popen([shell, "-c", f"for i in 1 2 3; do {sys.executable} {script} {ready}; echo continued-$i; done"], start_new_session=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    deadline = time.time() + 30
    while not (ready.exists() and ready.read_text().strip().isdigit()) and time.time() < deadline:
        time.sleep(0.02)
    if not ready.exists():
        loop.kill()
        loop.communicate()
        return None, None
    if target == "group":
        os.killpg(loop.pid, signal.SIGINT)
    else:
        os.kill(int(ready.read_text().strip()), signal.SIGINT)
    out, _ = loop.communicate(timeout=60)
    return len(out.split()), loop.returncode


EXPECTED = {   # (shell, signal sent to, child) -> (runs that continued, how the shell ended)
    ("bash", "group", "exit 130"): (3, 0), ("bash", "group", "dies by SIGINT"): (0, -signal.SIGINT),
    ("bash", "child only", "exit 130"): (3, 0), ("bash", "child only", "dies by SIGINT"): (3, 0),
    ("dash", "group", "exit 130"): (0, -signal.SIGINT), ("dash", "group", "dies by SIGINT"): (0, -signal.SIGINT),
    ("dash", "child only", "exit 130"): (3, 0), ("dash", "child only", "dies by SIGINT"): (3, 0),
}
problems = []
measured = 0
with tempfile.TemporaryDirectory(prefix="slc-") as workdir:
    for (shell, target, child), expected in EXPECTED.items():
        if not shutil.which(shell):
            print(f"{shell}, SIGINT to the {target}, child {child}: not measured ({shell} is not installed)")
            continue
        got = measure(shell, workdir, child, target)
        measured += 1
        ok = got == expected
        print(f"{shell}, SIGINT to the {target}, child {child}: {got[0]} of 3 runs continued, shell ended with {got[1]} | expected {expected}: {ok}", flush=True)
        if not ok:
            problems.append(f"{shell}/{target}/{child}")
    # the rejecting control: the child kills its PARENT shell with SIGTERM; the loop stops and prints nothing, which a check of the empty output alone would take for a death by SIGINT
    if shutil.which("bash"):
        continued, code = measure("bash", workdir, "kills its parent shell with SIGTERM", "group")
        accepted = ended_by_sigint(code, [] if continued == 0 else ["x"])
        print(f"control, bash, the child kills its parent shell with SIGTERM: {continued} of 3 runs continued, shell ended with {code}; accepted as a death by SIGINT: {accepted} (expected False)")
        if accepted or code != -signal.SIGTERM:
            problems.append("the wrong-signal control was not rejected")
if not measured:
    problems.append("no shell was measured")
print("the measured behaviour equals the documented one, and the wrong-signal control is rejected: " + str(not problems) + ("" if not problems else f" | problems: {problems}"))
sys.exit(0 if not problems else 1)
