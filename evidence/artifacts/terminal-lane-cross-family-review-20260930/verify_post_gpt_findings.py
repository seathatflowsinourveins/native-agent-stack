#!/usr/bin/env python3
"""Reproductions of the findings of the post-merge GPT read (2026-10-01), run against the code of the terminal lane AS MERGED in pull request #563 (the code before this round's repairs): each check runs the merged code (a read-only
checkout, no .pyc) or a mutated copy under /var/tmp and prints one line. The outputs recorded in recorded/post_gpt_verification.txt are what the coordinator saw before repairing anything; after the repairs most checks print the
opposite (the repaired code ends by the signal, accepts no substring identity and so on), which is the point. To re-run them, check out the merge commit c99a482e. The checks that need no execution (the mutant runner discarding the
notes of a mutant run) cite the line. usage: verify_post_gpt_findings.py <checkout> <check> [<check> ...]
checks: flush handoff typing partial skips identity cleanup symlink delay wrongsignal order dash spawn (spawn takes about five minutes)"""
import importlib.util
import os
import runpy
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

CHK = Path(sys.argv[1]).resolve()
TERM = CHK / "evidence/artifacts/terminal-experience-20260928"
NOTIF = CHK / "evidence/artifacts/notification-types-20260929"
REVIEW = CHK / "evidence/artifacts/terminal-lane-cross-family-review-20260930"
ALERT = TERM / "alert_probe.py"


def load(path, name):
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def child(code, timeout=60):
    run = subprocess.run([sys.executable, "-B", "-c", code], capture_output=True, text=True, timeout=timeout)
    return run.returncode, run.stdout.strip(), run.stderr.strip()


PRELUDE = f'''
import sys, os, signal, importlib.util
spec = importlib.util.spec_from_file_location("p", {str(ALERT)!r}); p = importlib.util.module_from_spec(spec); sys.modules["p"] = p; spec.loader.exec_module(p)
'''


def check_flush():
    code = PRELUDE + '''
class Broken:
    def write(self, s): return len(s)
    def flush(self): raise BrokenPipeError("simulated closed pipe")
p.STOP["signal"] = signal.SIGTERM
sys.stdout = Broken()
try:
    p.end_by_latched_signal()
    print("returned", file=sys.stderr)
except BaseException as error:
    print("raised", type(error).__name__, file=sys.stderr)
'''
    rc, out, err = child(code)
    print(f"flush: child exit {rc} (a death by SIGTERM would be -15); stderr: {err}")


def check_handoff():
    code = PRELUDE + '''
p.with_private_dir(lambda private: os.kill(os.getpid(), signal.SIGINT))   # latches SIGINT; the handlers are restored when it returns
print("latched", p.STOP["signal"], file=sys.stderr, flush=True)
os.kill(os.getpid(), signal.SIGTERM)                                         # a second signal in the window before end_by_latched_signal
time.sleep(1)
'''.replace("import sys, os, signal", "import sys, os, signal, time")
    rc, out, err = child(code)
    print(f"handoff: latched first = SIGINT (-2 would be 'ended by the first signal'); child exit {rc} (-15 = died by the SECOND signal); {err}")


def check_typing():
    code = PRELUDE + '''
import time
log = []
def fake_write(fd, data):
    log.append((data, p.STOP["signal"]))
target = None
src = open(p.__file__).read().splitlines()
for number, line in enumerate(src, 1):
    if line.strip() == 'write(master, b"\\\\r")':
        target = number
fired = []
def local(frame, event, arg):
    if event == "line" and frame.f_lineno == target and not fired:
        fired.append(1)
        os.kill(os.getpid(), signal.SIGTERM)       # delivered at the Enter line, before it runs (the sweep's technique)
    return local
def tracer(frame, event, arg):
    return local if frame.f_code.co_name == "type_prompt" else None
p.STOP["signal"] = None
p.signal.signal(signal.SIGTERM, p.latch)
sys.settrace(tracer)
sent = p.type_prompt(0, "ab", write=fake_write, sleep=lambda s: None)
sys.settrace(None)
enter = [entry for entry in log if entry[0] == b"\\r"]
print("target line", target, "| Enter sent", sent, "| latch value at the Enter write", enter[0][1] if enter else None, file=sys.stderr)
'''
    rc, out, err = child(code)
    print(f"typing: {err}")


def check_partial():
    p = load(ALERT, "pa")
    import json
    calls = []

    def fake_run(argv, **kwargs):
        # argv: python, -B, -c, <driver code>, path, kind, target, record, pidfile, unique
        calls.append(argv[4:7])
        Path(argv[7]).write_text('{"lines": [1, 2')   # a truncated record, as a killed driver leaves it
        return subprocess.CompletedProcess(argv, 0, b"", b"")

    p.subprocess = type("S", (), {"run": staticmethod(fake_run), "TimeoutExpired": subprocess.TimeoutExpired, "Popen": subprocess.Popen, "DEVNULL": subprocess.DEVNULL, "PIPE": subprocess.PIPE, "CompletedProcess": subprocess.CompletedProcess})
    try:
        p.sweep_trial(str(ALERT), "ask", 5, "sleep", 0)
        print("partial: sweep_trial returned (no exception)")
    except Exception as error:
        print(f"partial: sweep_trial raised {type(error).__name__} on a truncated record before it could kill the stand-in")


def check_skips():
    text = (TERM / "pty_probe_mutants.py").read_text(encoding="utf-8")
    line = next(n for n, l in enumerate(text.splitlines(), 1) if "failed, _notes = failing_cases(path, kind)" in l)
    print(f"skips: pty_probe_mutants.py:{line} discards the notes of a mutant run (`_notes`); the baseline's notes end the run (`if notes: ... sys.exit(1)`)")


def check_identity():
    m = load(NOTIF / "tmux_bell_probe.py", "tbx")
    if not m.TMUX:
        print("identity: tmux not installed")
        return
    with tempfile.TemporaryDirectory(prefix="vi", dir="/tmp") as raw:
        ours = str(Path(raw) / "tmux.sock")
        other = ours + ".old"                     # another server whose socket path has OURS as a prefix
        subprocess.run([m.TMUX, "-S", other, "-f", "/dev/null", "new-session", "-d", "sleep 60"], check=True, capture_output=True)
        other_pid = int(subprocess.run([m.TMUX, "-S", other, "-f", "/dev/null", "display-message", "-p", "#{pid}"], capture_output=True, text=True, timeout=10).stdout.strip())
        wrapper = Path(raw) / "tmux"
        wrapper.write_text(f'#!/bin/sh\ncase " $* " in *" display-message "*) echo {other_pid}; exit 0;; esac\nexec {m.TMUX} "$@"\n')
        wrapper.chmod(0o755)
        identity = m.server_identity([str(wrapper), "-S", ours, "-f", "/dev/null"])
        comm = Path(f"/proc/{other_pid}/comm").read_text().strip()
        print(f"identity: another server (socket path = ours + '.old', comm '{comm}') accepted as ours: {identity is not None and identity[0] == other_pid}")
        subprocess.run([m.TMUX, "-S", other, "kill-server"], capture_output=True)


def check_cleanup():
    m = load(NOTIF / "tmux_bell_probe.py", "tbc")
    if not m.TMUX:
        print("cleanup: tmux not installed")
        return
    count = {"n": 0}

    def measure():
        count["n"] += 1
        if count["n"] == 3:
            raise RuntimeError("an unexpected failure of the measurement")
        return m.bells(m.BELL, [], seconds=2.0)

    before = m.tmux_servers()
    try:
        m.shutdown_control(measure)
    except RuntimeError as error:
        leaked = m.tmux_servers() - before
        print(f"cleanup: shutdown_control raised {error!s} on the third control; tmux servers left behind: {len(leaked)}")
        for pid in leaked:
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
        return
    print("cleanup: shutdown_control returned without raising")


def check_symlink():
    with tempfile.TemporaryDirectory(prefix="vs", dir="/var/tmp") as raw:
        victim = Path(raw) / "victim.txt"
        victim.write_text("precious content")
        link = Path(f"/var/tmp/shell_loop_control_{os.getpid()}.py")
        link.symlink_to(victim)
        try:
            runpy.run_path(str(REVIEW / "shell_loop_control.py"), run_name="__main__")
        except SystemExit:
            pass
        finally:
            if link.is_symlink() or link.exists():
                link.unlink()
        print("symlink: victim file after the run:", repr(victim.read_text()[:50]))


def check_delay():
    """SIGINT 0.5 s after the start, to the group, while the child installs its handler only after 0.8 s (a slow start on a loaded host)."""
    code = "import signal,sys,time\ntime.sleep(0.8)\nsignal.signal(signal.SIGINT, lambda *a: None)\ntime.sleep(2)\nsys.exit(130)\n"
    with tempfile.TemporaryDirectory(prefix="vdl", dir="/var/tmp") as raw:
        script = Path(raw) / "slow_child.py"
        script.write_text(code)
        loop = subprocess.Popen(["bash", "-c", f"for i in 1 2 3; do {sys.executable} {script}; echo continued-$i; done"], start_new_session=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        time.sleep(0.5)
        os.killpg(loop.pid, signal.SIGINT)
        out, _ = loop.communicate(timeout=60)
    print(f"delay: SIGINT 0.5 s after the start, the child installs its handler at 0.8 s -> {len(out.split())} of 3 runs continued, shell exit {loop.returncode} (the control expects 3 for its exit-130 arm)")


def run_mutated(script, old, new, label):
    text = (REVIEW / script).read_text(encoding="utf-8")
    assert text.count(old) == 1, (script, text.count(old))
    with tempfile.TemporaryDirectory(prefix="vm", dir="/var/tmp") as raw:
        path = Path(raw) / script
        path.write_text(text.replace(old, new), encoding="utf-8")
        run = subprocess.run([sys.executable, "-B", str(path)], capture_output=True, text=True, timeout=120)
    print(f"{label}: exit {run.returncode} | " + " / ".join(line[:150] for line in run.stdout.strip().splitlines()[-3:]))


def check_wrongsignal():
    run_mutated("shell_loop_control.py", '"os.kill(os.getpid(), signal.SIGINT)\\n"', '"os.kill(os.getppid(), signal.SIGTERM)\\n"', "wrongsignal (the 'dies by SIGINT' child kills its PARENT shell with SIGTERM: the loop stops and prints nothing)")


def check_order():
    run_mutated("signal_order_probe.py", "lambda n, _frame: seen.append(n)", "lambda n, _frame: None", "order (no handler records anything)")


def loops(shell, to_group):
    EXIT_130 = "import signal,sys,time\nsignal.signal(signal.SIGINT, lambda *a: None)\ntime.sleep(2)\nsys.exit(130)\n"
    DIE = "import os,signal,time\nsignal.signal(signal.SIGINT, lambda *a: None)\ntime.sleep(2)\nsignal.signal(signal.SIGINT, signal.SIG_DFL)\nos.kill(os.getpid(), signal.SIGINT)\ntime.sleep(5)\n"
    results = []
    for label, code in (("exit 130", EXIT_130), ("dies by SIGINT", DIE)):
        script = f"/var/tmp/vd_{os.getpid()}_{label[0]}.py"
        Path(script).write_text(code)
        loop = subprocess.Popen([shell, "-c", f"for i in 1 2 3; do python3 {script}; echo continued-$i; done"], start_new_session=True, stdout=subprocess.PIPE, text=True)
        time.sleep(0.8)
        if to_group:
            os.killpg(loop.pid, signal.SIGINT)
        else:
            kids = subprocess.run(["pgrep", "-P", str(loop.pid)], capture_output=True, text=True).stdout.split()
            for kid in kids:
                os.kill(int(kid), signal.SIGINT)
        out, _ = loop.communicate(timeout=60)
        results.append(f"{label}: {len(out.split())} of 3 runs continued, shell exit {loop.returncode}")
        os.unlink(script)
    return "; ".join(results)


def check_dash():
    import shutil
    for shell in ("bash", "dash"):
        if not shutil.which(shell):
            print(f"dash: {shell} not installed")
            continue
        print(f"dash: {shell}, SIGINT to the process group: {loops(shell, True)}")
        print(f"dash: {shell}, SIGINT to the child only:     {loops(shell, False)}")


def check_spawn():
    text = ALERT.read_text(encoding="utf-8")
    old = "        if not stopped():   # a signal latched before this point: no client is started\n"
    assert text.count(old) == 1
    with tempfile.TemporaryDirectory(prefix="vsp", dir="/var/tmp") as raw:
        path = Path(raw) / "m.py"
        path.write_text(text.replace(old, "        if True:   # MUTANT: the guard is gone\n"), encoding="utf-8")
        m = load(path, "msp")
        ok, detail = m.sweep_case("ask")
    print("spawn: sweep_case on the guard-removed copy ->", ok, "|", detail[:900])


for name in sys.argv[2:]:
    globals()["check_" + name]()
