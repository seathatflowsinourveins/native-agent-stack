#!/usr/bin/env python3
"""Reproductions of the three findings the Codex review bot (chatgpt-codex-connector) left on pull request 572 on 2026-10-01 (commit 5c484647), run against the probe files of a checkout. Each prints one line; the first value is what the code before the
repairs gives, the second what the repaired code gives:
R1 (alert and push probe): a SIGTERM delivered at the line after the snapshot of the latch in `end_by_latched_signal` must still end the process BY SIGTERM (before: the child exits 0 and the signal is lost; after: exit -15);
R2 (alert and push probe): the real `main()` with a stub measurement that signals itself and with stdout a full pipe that nobody reads must end by SIGTERM within a few seconds (before: still running after 6 s; after: exit -15);
R3 (bell and sync probe): the selftest must leave no socket directory behind, counted as the new directories under /tmp that look like the probe's own `mkdtemp` result (before: 2 for each probe; after: 0).
Run one probe family at a time: the tmux selftests count each other's servers. Exit 0 when the expectation holds: with `--before` every finding reproduces (the check that the reproduction can see the defect), without it none does (the repaired code).
usage: verify_codex_bot_findings.py <checkout> r1|r2|r3 [--before]"""
import fcntl
import glob
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

root = Path(sys.argv[1])
which = sys.argv[2]
BEFORE = "--before" in sys.argv[3:]
PROBES = {
    "alert": (root / "evidence/artifacts/terminal-experience-20260928/alert_probe.py", ["ask"]),
    "push": (root / "evidence/artifacts/notification-types-20260929/push_notification_probe.py", ["push", "--no-user-settings"]),
}

R1_CHILD = r"""
import importlib.util, os, signal, sys
path = sys.argv[1]
spec = importlib.util.spec_from_file_location("probe", path)
probe = importlib.util.module_from_spec(spec)
sys.modules["probe"] = probe
spec.loader.exec_module(probe)
source = open(path, encoding="utf-8").read().splitlines()
start = next(n for n, text in enumerate(source, 1) if text.startswith("def end_by_latched_signal"))
target = next(n for n, text in enumerate(source, 1) if n > start and text.strip() == "number = STOP[\"signal\"]")
for number in probe.HANDLED:
    signal.signal(number, probe.latch)
probe.STOP["signal"] = None


def local(frame, event, arg):
    if event == "line" and frame.f_lineno == target + 1:
        os.kill(os.getpid(), signal.SIGTERM)      # the signal lands after the snapshot was taken
    return local


def tracer(frame, event, arg):
    return local if frame.f_code.co_name == "end_by_latched_signal" else None


sys.settrace(tracer)
probe.end_by_latched_signal()
sys.settrace(None)
print("returned; latch =", probe.STOP["signal"])
sys.exit(0)
"""

R2_CHILD = r"""
import importlib.util, os, signal, sys
path, kind_args = sys.argv[1], sys.argv[2:]
spec = importlib.util.spec_from_file_location("probe", path)
probe = importlib.util.module_from_spec(spec)
sys.modules["probe"] = probe
spec.loader.exec_module(probe)


def measure(args, private):
    os.kill(os.getpid(), signal.SIGTERM)      # latched at the next bytecode
    return 0


probe.measure = measure
sys.argv = [path] + kind_args
status = probe.main()
probe.end_by_latched_signal()
sys.exit(status)
"""


def r1(name):
    path, _args = PROBES[name]
    run = subprocess.run([sys.executable, "-B", "-c", R1_CHILD, str(path)], capture_output=True, text=True, timeout=60)
    print(f"R1 {name}: SIGTERM after the snapshot line -> child exit {run.returncode} (-15 = ended BY SIGTERM; 0 = the signal was lost)" + (f" | {run.stdout.strip()[:60]}" if run.stdout.strip() else ""))
    return run.returncode


def r2(name):
    path, args = PROBES[name]
    read_end, write_end = os.pipe()
    fcntl.fcntl(write_end, fcntl.F_SETFL, fcntl.fcntl(write_end, fcntl.F_GETFL) | os.O_NONBLOCK)
    filled = 0
    try:
        while True:
            filled += os.write(write_end, b"x" * 4096)
    except BlockingIOError:
        pass
    fcntl.fcntl(write_end, fcntl.F_SETFL, fcntl.fcntl(write_end, fcntl.F_GETFL) & ~os.O_NONBLOCK)
    child = subprocess.Popen([sys.executable, "-B", "-c", R2_CHILD, str(path), *args], stdout=write_end, stderr=subprocess.DEVNULL)
    os.close(write_end)
    deadline = time.time() + 6
    while time.time() < deadline and child.poll() is None:
        time.sleep(0.1)
    code = child.poll()
    if code is None:
        child.kill()
        child.wait()
    os.close(read_end)
    print(f"R2 {name}: stdout a full pipe that nobody reads, a latched SIGTERM -> " + (f"child exit {code}" if code is not None else "STILL RUNNING after 6 s (killed by SIGKILL)") + " (-15 = ended BY SIGTERM)")
    return code


def r3(name):
    script, prefix = {"bell": ("evidence/artifacts/notification-types-20260929/tmux_bell_probe.py", "/tmp/tb*"),
                      "sync": ("evidence/artifacts/terminal-lane-cross-family-review-20260930/tmux_sync_probe.py", "/tmp/ts*")}[name]
    shape = re.compile(prefix[len("/tmp/"):-1] + "[a-z0-9_]{8}")      # the probe's own `mkdtemp` result: another tool's /tmp/ts* (tsx-1000) cannot match
    before = frozenset(each for each in glob.glob(prefix) if shape.fullmatch(os.path.basename(each)))
    run = subprocess.run([sys.executable, "-B", str(root / script), "--selftest"], capture_output=True, text=True, timeout=900)
    after = frozenset(each for each in glob.glob(prefix) if shape.fullmatch(os.path.basename(each)))
    new = sorted(after - before)
    print(f"R3 {name}: selftest exit {run.returncode}; new {prefix} socket directories left behind: {len(new)}")
    return len(new)


results = []      # per probe: True when the finding reproduces
if which == "r1":
    results = [r1(each) != -signal.SIGTERM for each in PROBES]
elif which == "r2":
    results = [r2(each) != -signal.SIGTERM for each in PROBES]
else:
    results = [r3(each) > 0 for each in ("bell", "sync")]
holds = all(results) if BEFORE else not any(results)
print(f"{which}: " + ("every finding reproduces" if all(results) else "no finding reproduces" if not any(results) else "some findings reproduce") + f" | the expectation ({'before' if BEFORE else 'after'} the repairs) holds: {holds}")
sys.exit(0 if holds else 1)
