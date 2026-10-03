#!/usr/bin/env python3
"""Native probe: does a model-initiated PushNotification raise a Notification hook event, of which type, and does a bell hook that matches that type ring? It also measures the
rule the client uses to decide that the user is present (in which case the tool sends nothing and no event fires). Drives a real short interactive Claude Code session in a
pty (Haiku, no keys sent while waiting). A PreToolUse observer marks the moment the tool is called, a Notification observer records every event's type, and a BEL counter that
follows Windows Terminal's output state machine counts the bare BEL bytes after that moment.

The presence rule, read from the installed client (2.1.285): the user is present when the terminal has reported its focus (DECSET 1004 focus reports) and that report says
focused; when no focus report has arrived, when the last input was less than 60 seconds ago (`function V4r`, `var KWt=60000`); `CLAUDE_CODE_DISABLE_NOTIFICATION_PRESENCE_CHECK`
bypasses the check. The prompt makes the model run `sleep N` first, so the tool is called about N seconds after the prompt's Enter. The probe prints whether the client enabled focus
reporting, whether it sent a focus-out report (only when asked to and only after the client enabled the mode) and the seconds from Enter to the tool call, so each arm says which
branch of the rule decided it.

Derived from evidence/artifacts/terminal-experience-20260928/alert_probe.py (sha256 prefix 1282ff2b at the derivation): the code after its module docstring is the same except for the
`push` kind (prompt, observer matcher, observation window), `--bell-hook`, `--no-user-settings`, `--sleep`, `--no-focus-report`, the focus-out report and its timing lines, and Haiku as the
model. Raw hook payloads (session ids, paths) go to a private temporary directory that is removed on success, on a failure and on SIGINT, SIGTERM or SIGHUP; only counts, types, message
lengths and timings are printed (the terminal screen tail only with --show-screen, and never into a receipt).

usage:
  push_notification_probe.py push --no-user-settings                        arm A: no user-scope settings, only the observers, focus-out sent (the event must fire, nothing may ring)
  push_notification_probe.py push --no-user-settings --bell-hook            arm B: the same plus one Notification hook that emits one BEL for the type push_notification
  push_notification_probe.py push                                           arm C: the user's own user-scope settings, whatever their bell hook matches (the live host)
  push_notification_probe.py push --no-user-settings --no-focus-report --sleep 75   arm D: no focus report, so the 60-second fallback applies and 75 s have passed (the event must fire)
  push_notification_probe.py push --no-user-settings --no-focus-report --sleep 15   arm E: no focus report and 15 s (the user counts as present: no event, nothing rings)
  push_notification_probe.py --selftest                                     check the BEL counter against split, doubled, interrupted and string-embedded cases
"""
import argparse, ast, codecs, concurrent.futures, fcntl, json, os, pty, re, select, shutil, signal, struct, subprocess, sys, tempfile, termios, time
from pathlib import Path


class BelCounter:
    """Counts BEL bytes that Windows Terminal would execute as an audible bell. A BEL that terminates an OSC string is not one.
    Mirrors the output state machine of v1.24.11911.0 (stateMachine.cpp ProcessCharacter L1838-L1924, _EventEscape L1084-L1161,
    _EventOscString L1487-L1508, _EventOscTermination L1519-L1532, DCS and SOS/PM/APC handlers L1667-L1830). State survives reads."""

    C0 = frozenset(list(range(0x00, 0x18)) + [0x19] + list(range(0x1C, 0x20)))  # _isC0Code: NUL-ETB, EM, FS-US

    def __init__(self):
        self.state = "ground"  # ground | escape | esc_int | csi | osc | osc_term | string
        self.decoder = codecs.getincrementaldecoder("utf-8")("replace")  # the terminal parses decoded characters, not bytes

    def feed(self, data):
        bare = 0
        for char in self.decoder.decode(data):
            byte = ord(char)
            if 0x80 <= byte <= 0x9F:                      # C1 controls are ignored by the output engine (AcceptC1 off): no state change (stateMachine.cpp L1855-1868)
                continue
            if byte in (0x18, 0x1A):                      # CAN, SUB: from anywhere back to ground
                self.state = "ground"
            elif byte == 0x1B and self.state != "osc":    # ESC interrupts every state except an OSC string, where it starts ST
                self.state = "escape"
            elif self.state == "ground":
                if byte == 0x07:
                    bare += 1
            elif self.state == "escape":
                if byte in self.C0:                        # executed in the escape state, which is kept
                    bare += 1 if byte == 0x07 else 0
                elif byte == 0x7F:
                    pass
                elif 0x20 <= byte <= 0x2F:
                    self.state = "esc_int"
                elif byte == 0x5B:                         # [  CSI
                    self.state = "csi"
                elif byte == 0x5D:                         # ]  OSC
                    self.state = "osc"
                elif byte in (0x50, 0x58, 0x5E, 0x5F):     # P X ^ _  DCS, SOS, PM, APC
                    self.state = "string"
                else:
                    self.state = "ground"
            elif self.state == "esc_int":
                if byte in self.C0:
                    bare += 1 if byte == 0x07 else 0
                elif byte == 0x7F or 0x20 <= byte <= 0x2F:
                    pass
                else:
                    self.state = "ground"
            elif self.state == "csi":
                if byte in self.C0:
                    bare += 1 if byte == 0x07 else 0
                elif byte == 0x7F or 0x20 <= byte <= 0x3F:
                    pass                                   # intermediates, parameters, private markers
                else:
                    self.state = "ground"                  # final byte
            elif self.state == "osc":
                if byte == 0x07:                           # BEL terminates the OSC: not a bare BEL
                    self.state = "ground"
                elif byte == 0x1B:
                    self.state = "osc_term"
            elif self.state == "osc_term":
                if byte == 0x5C:                           # ST
                    self.state = "ground"
                else:                                      # anything else re-enters the escape state and is handled there
                    self.state = "escape"
                    if byte in self.C0:
                        bare += 1 if byte == 0x07 else 0
                    elif 0x20 <= byte <= 0x2F:
                        self.state = "esc_int"
                    elif byte == 0x5B:
                        self.state = "csi"
                    elif byte == 0x5D:
                        self.state = "osc"
                    elif byte in (0x50, 0x58, 0x5E, 0x5F):
                        self.state = "string"
                    elif byte != 0x7F:
                        self.state = "ground"
            # "string" (DCS, SOS, PM, APC): every byte is ignored until ESC or CAN/SUB, handled above
        return bare


SWEEP_DRIVER = r"""
import importlib.util, json, os, signal, sys
path, kind, target, record, pidfile, unique = sys.argv[1:7]
target = int(target)
spec = importlib.util.spec_from_file_location("probe", path)
probe = importlib.util.module_from_spec(spec)
sys.modules["probe"] = probe
spec.loader.exec_module(probe)
WATCH = {"main", "with_private_dir", "measure", "end_by_latched_signal", "emit_report"}   # the resource lifecycle (the private directory, the pty and the client), the handoff and the output after it
seen, fired, alive_at_fire, created = [], [], [], []


import subprocess
_Popen = subprocess.Popen


class CountingPopen(_Popen):
    def __init__(self, args, *rest, **options):
        if isinstance(args, (list, tuple)) and args and str(args[0]) == "claude":
            created.append("claude")      # a client is being created: recorded before it exists
        super().__init__(args, *rest, **options)


subprocess.Popen = CountingPopen


def dump():
    open(record, "w").write(json.dumps({"lines": seen, "fired": fired, "alive_at_fire": alive_at_fire, "created": created}))


def alive():
    try:
        pid = int(open(pidfile).read().strip())
        state = open(f"/proc/{pid}/stat").read().rsplit(")", 1)[1].split()[0]
        argv = open(f"/proc/{pid}/cmdline", "rb").read().split(b"\0")
    except (OSError, ValueError, IndexError):
        return False
    return state != "Z" and argv[:2] == [b"sleep", unique.encode()]


def local(frame, event, arg):
    if event == "line":
        number = frame.f_lineno
        if number not in seen:
            seen.append(number)
        if number == target and not fired:
            fired.append(number)
            alive_at_fire.append(alive())
            dump()                                  # before the signal: a run that dies of it has still said where it was hit
            os.kill(os.getpid(), signal.SIGTERM)    # delivered at this line, before the line runs
    return local


def tracer(frame, event, arg):
    code = frame.f_code
    return local if code.co_filename == path and code.co_name in WATCH else None


sys.argv = [path, kind] + (["--no-user-settings"] if kind == "push" else [])
_end = probe.end_by_latched_signal


def end_and_dump():
    dump()      # the record is complete before the process can end BY the signal inside the handoff
    _end()


probe.end_by_latched_signal = end_and_dump
sys.settrace(tracer)
try:
    status = probe.main()
finally:
    sys.settrace(None)
    dump()
sys.exit(status)      # what the probe's own __main__ block runs after main returns: `main` has handed off in its own `finally`
"""


HANDOFF_DRIVER = r"""
import importlib.util, os, signal, sys
path, kind, first_line, second_line = sys.argv[1:5]
first_line, second_line = int(first_line), int(second_line)
spec = importlib.util.spec_from_file_location("probe", path)
probe = importlib.util.module_from_spec(spec)
sys.modules["probe"] = probe
spec.loader.exec_module(probe)
WATCH = {"main", "measure"}
sent = []


def local(frame, event, arg):
    if event == "line":
        for number, name in ((first_line, signal.SIGINT), (second_line, signal.SIGTERM)):
            if frame.f_lineno == number and number not in sent:
                sent.append(number)
                os.kill(os.getpid(), name)      # delivered at this line, before it runs
    return local


def tracer(frame, event, arg):
    return local if frame.f_code.co_filename == path and frame.f_code.co_name in WATCH else None


sys.argv = [path, kind] + (["--no-user-settings"] if kind == "push" else [])
sys.settrace(tracer)
try:
    status = probe.main()
finally:
    sys.settrace(None)
sys.exit(status)      # what the probe's own __main__ block runs after main returns: `main` has handed off in its own `finally`
"""

FLUSH_CHILD = r"""
import importlib.util, os, signal, sys
path, mode, kind = sys.argv[1:4]
spec = importlib.util.spec_from_file_location("probe", path)
probe = importlib.util.module_from_spec(spec)
sys.modules["probe"] = probe
spec.loader.exec_module(probe)
if mode == "blocked-signal":
    probe.STOP["signal"] = signal.SIGTERM      # a latched signal that a mask inherited from the parent blocks
    signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM})
    probe.end_by_latched_signal()
    sys.exit(0)      # reached only when the process was not ended by the signal


def measure(args, private):
    sys.stdout.write("a result line written earlier, still in the buffer of stdout\n")      # what a flush before the final kill would have to write
    if mode in ("closed-stdout", "full-pipe"):
        os.kill(os.getpid(), signal.SIGTERM)      # latched at the next bytecode: the latch is set when the measurement returns
    return 0


probe.measure = measure
if mode in ("closed-stdout", "closed-stdout-exit"):
    os.close(1)
sys.argv = [path, kind] + (["--no-user-settings"] if kind == "push" else [])
sys.exit(probe.main())      # what the probe's own __main__ block runs: `main` hands off in its own `finally`
"""


def blocked_mask(pid):
    """The SigBlk mask of a process as read from /proc (a hex string), or None when it cannot be read. Read from OUTSIDE the stand-in: a shell script clears its own mask at startup, the exec'd program does not."""
    try:
        for line in (Path("/proc") / str(pid) / "status").read_text().splitlines():
            if line.startswith("SigBlk:"):
                return line.split()[1]
    except OSError:
        pass
    return None


def stand_in_script(kind, pidfile, unique):
    """The stand-in `claude`: publishes its PID, then becomes `sleep <unique>` (exec keeps the PID). `trust` first enables focus reporting (the push probe waits for it) and prints the text that makes the probe abort
    by itself after about 6 s and run its normal exit path; `trust-exit` prints the same and exits at once (a client that is not there when the signal comes); `true` exits at once."""
    if kind == "true":
        return "#!/bin/sh\nexit 0\n"
    if kind in ("dialog-bell", "dialog-quiet"):   # the client shows its question after startup and, for dialog-bell, rings once while the probe observes
        bell = "printf '\\a'\n" if kind == "dialog-bell" else ""
        return f"#!/bin/sh\necho $$ > {pidfile}\nprintf '\\033[?1004h'\nsleep 8\nprintf 'Enter to select\\n'\nsleep 2\n{bell}exec sleep {unique}\n"
    text = "printf '\\033[?1004hDo you trust the files in this folder?\\n'\n" if kind in ("trust", "trust-exit") else ""   # focus reporting on (the push probe waits for it), then the trust text
    if kind == "trust-exit":
        return f"#!/bin/sh\necho $$ > {pidfile}\n{text}exit 0\n"
    return f"#!/bin/sh\necho $$ > {pidfile}\n{text}exec sleep {unique}\n"


def stand_in_alive(client, unique):
    """True when `client` is a running (not zombie) process whose argv is exactly `sleep <unique>`: our stand-in, not a process that reused the PID."""
    try:
        state = (Path("/proc") / str(client) / "stat").read_text().rsplit(")", 1)[1].split()[0]
        argv = (Path("/proc") / str(client) / "cmdline").read_bytes().split(b"\0")
    except (OSError, IndexError):
        return False
    return state != "Z" and argv[:2] == [b"sleep", unique.encode()]


def arena(root, stand_in, serial):
    """A private arena for one probe run: a stand-in `claude` first on PATH that publishes its PID, and a TMPDIR of its own. Returns (env, tmp, pidfile, unique)."""
    bindir, tmp, pidfile = root / "bin", root / "tmp", root / "stand-in.pid"
    bindir.mkdir()
    tmp.mkdir()
    unique = f"3137{os.getpid() % 100000}{serial}"   # digits only: `sleep 3137<digits>` marks our stand-ins
    (bindir / "claude").write_text(stand_in_script(stand_in, pidfile, unique))
    (bindir / "claude").chmod(0o755)
    return {**os.environ, "PATH": f"{bindir}:{os.environ['PATH']}", "TMPDIR": str(tmp)}, tmp, pidfile, unique


def signal_case(kind, signums=(signal.SIGTERM,), stand_in="sleep", delay=1.0, gap=0.1):
    """End to end: a stand-in `claude` first on PATH that publishes its PID, the real probe as a child with its own TMPDIR, the signals `signums` sent `gap` seconds apart `delay` seconds after the stand-in is running:
    the probe must be running when the first lands and end BY the FIRST signal (Popen reports the negative signal number: after the cleanups the probe kills itself with it, so a parent shell sees a death by that signal), the private directory must be gone, the recorded stand-in (exactly `sleep <unique>`) must be gone and
    it must have inherited no blocked signal. stand_in="true" starts a client that exits at once: the case must then FAIL (a client that never ran proves nothing). Returns (ok, detail); ok is None when the
    probe's working directory does not exist on this machine."""
    if not (Path.home() / "code/native-agent-stack").is_dir():
        return None, "skipped (the probe's working directory does not exist on this machine)"
    with tempfile.TemporaryDirectory(prefix="sigcase-") as raw:
        env, tmp, pidfile, unique = arena(Path(raw), stand_in, 0)
        proc = subprocess.Popen([sys.executable, "-B", str(Path(__file__).resolve()), kind, *(["--no-user-settings"] if kind == "push" else [])], env=env,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        client = None
        deadline = time.time() + (30 if stand_in != "true" else 5)
        while time.time() < deadline:
            if pidfile.exists() and pidfile.read_text().strip().isdigit():
                client = int(pidfile.read_text().strip())
                if stand_in_alive(client, unique):
                    break
            time.sleep(0.2)
        client_ran = client is not None and stand_in_alive(client, unique)
        mask = blocked_mask(client) if client_ran else None
        clean_mask = mask == "0" * 16   # the client must not inherit a blocked signal from the probe
        time.sleep(delay)
        probe_running = proc.poll() is None
        for number, sent in enumerate(signums):
            if number:
                time.sleep(gap)
            if proc.poll() is None:
                proc.send_signal(sent)
        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        time.sleep(0.5)
        left_dirs = list(tmp.glob("alert-probe-*"))
        alive = client is not None and stand_in_alive(client, unique)
        if alive:
            os.kill(client, signal.SIGKILL)   # a failing case must not leave its stand-in behind (alive means the recorded PID is still exactly our `sleep`)
        expected = -signums[0]   # the probe ends BY the first signal (Popen reports the negative number)
        detail = (f"stand-in client ran {client_ran} with signal mask {mask}, probe running when signaled {probe_running}, probe exit {proc.returncode} (expected {expected}), "
                  f"private directory left {bool(left_dirs)}, stand-in client still alive {alive}")
        return client_ran and clean_mask and probe_running and proc.returncode == expected and not left_dirs and not alive, detail


def status_case(kind, workers=3):
    """The exit status of the measurement itself, end to end (the helper `exit_status` alone shows nothing about its use): a run whose dialog never opened exits 2, a hooks-disabled control that saw a BEL exits 1,
    a quiet hooks-disabled control exits 0. Three runs in parallel, each in its own arena with a stand-in client that is killed afterwards. Returns (ok, detail); ok is None without the probe's working directory."""
    if not (Path.home() / "code/native-agent-stack").is_dir():
        return None, "skipped (the probe's working directory does not exist on this machine)"
    path = str(Path(__file__).resolve())
    runs = (("the dialog never opened", "trust", [kind], 2), ("a hooks-disabled control saw a BEL", "dialog-bell", [kind, "--control"], 1), ("a quiet hooks-disabled control", "dialog-quiet", [kind, "--control"], 0))

    def one(index):
        label, stand_in, arguments, expected = runs[index]
        with tempfile.TemporaryDirectory(prefix="status-") as raw:
            env, tmp, pidfile, unique = arena(Path(raw), stand_in, 100 + index)
            try:
                code = subprocess.run([sys.executable, "-B", path, *arguments], env=env, capture_output=True, timeout=180).returncode
            except subprocess.TimeoutExpired:
                code = "timeout"   # the stand-in is still killed below, through its pidfile
            client = int(pidfile.read_text().strip()) if pidfile.exists() and pidfile.read_text().strip().isdigit() else None
            if client is not None and stand_in_alive(client, unique):
                os.kill(client, signal.SIGKILL)
            return label, code, expected, len(list(tmp.glob("alert-probe-*")))

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(one, range(len(runs))))
    problems = [f"{label}: exit {code}, expected {expected}" for label, code, expected, _left in results if code != expected] + [f"{label}: a payload directory was left" for label, _c, _e, left in results if left]
    return not problems, "; ".join(f"{label}: exit {code} (expected {expected})" for label, code, expected, _left in results) + ("" if not problems else " | " + "; ".join(problems))


def sweep_trial(path, kind, target, stand_in, serial):
    """One run of the probe in a child process with a stand-in client; SIGTERM is delivered to it at the first execution of line `target` of its resource lifecycle (`main`, `with_private_dir`, `measure`, `end_by_latched_signal`, `emit_report`; -1
    delivers none: a dry run that records the lines). Returns what the run showed: its exit status, what the driver recorded, the payload directories and the stand-in left behind."""
    with tempfile.TemporaryDirectory(prefix="sweep-") as raw:
        root = Path(raw)
        env, tmp, pidfile, unique = arena(root, stand_in, serial)
        record = root / "record.json"
        try:
            try:
                status = subprocess.run([sys.executable, "-B", "-c", SWEEP_DRIVER, path, kind, str(target), str(record), str(pidfile), unique], env=env, capture_output=True, timeout=180).returncode
            except subprocess.TimeoutExpired:
                status = "timeout"      # the stand-in is still killed below, through its pidfile
            try:
                info = json.loads(record.read_text()) if record.exists() else {}
            except (OSError, ValueError):
                info = {"unreadable_record": True}      # a driver killed while it wrote its record: a finding of this trial, not an exception that skips the cleanup
        finally:
            client = int(pidfile.read_text().strip()) if pidfile.exists() and pidfile.read_text().strip().isdigit() else None
            alive = client is not None and stand_in_alive(client, unique)
            if alive:
                os.kill(client, signal.SIGKILL)      # never leave the stand-in behind, whatever happened above
        return {"target": target, "status": status, "info": info, "left": len(list(tmp.glob("alert-probe-*"))), "alive": alive, "started": bool(info.get("created"))}


def sweep_case(kind, stand_in="trust", workers=6):
    """A SIGTERM at each line of `main`, `with_private_dir`, `measure`, `end_by_latched_signal` and `emit_report` that a dry run reaches: the dry run uses a stand-in client that makes the probe give up at the trust dialog and take its normal exit path (about 7 s), so
    it reaches every line that acquires or releases the private directory, the pty, the client and the handlers, but NOT the lines after the prompt is typed (typing, the observation loop, the report) nor the branches it does not
    take (the detail says how many lines with code that leaves out). One run per reached line delivers the signal there. Every run must end BY SIGTERM (status -15: with the latch installed the probe ends by it at the handoff, before it the default action does, after it the default action does too), leave no payload directory and no stand-in client, and, for a signal that lands
    at or before the spawn guard, have started NO client at all (observed by counting the `subprocess.Popen` calls of the client in the driver, not by the stand-in's pidfile). The client must have been RUNNING when the signal fired at ten lines or more, so a stand-in that is not there (a control that proves nothing) fails the case.
    Returns (ok, detail)."""
    if not (Path.home() / "code/native-agent-stack").is_dir():
        return None, "skipped (the probe's working directory does not exist on this machine)"
    path = str(Path(__file__).resolve())
    lines = sweep_trial(path, kind, -1, stand_in, 0)["info"].get("lines") or []
    if len(lines) < 25:
        return False, f"the dry run recorded {len(lines)} lines of the resource lifecycle (at least 25 expected)"
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        trials = list(pool.map(lambda pair: sweep_trial(path, kind, pair[1], stand_in, pair[0] + 1), enumerate(lines)))
    source = Path(path).read_text(encoding="utf-8").splitlines()
    guard = next((number for number, text in enumerate(source, 1) if text.strip().startswith("if ") and "# SPAWN GUARD:" in text), None)
    before_spawn = lines[:lines.index(guard) + 1] if guard in lines else []
    problems = [] if before_spawn else ["the dry run did not reach the spawn guard (the line marked `# SPAWN GUARD`), so the sweep cannot tell whether a client was started after a stop request"]
    for trial in trials:
        line = trial["target"]
        if trial["info"].get("fired") != [line]:
            problems.append(f"line {line}: the signal was not delivered")
        elif trial["status"] != -signal.SIGTERM:
            problems.append(f"line {line}: exit status {trial['status']}")
        if trial["left"]:
            problems.append(f"line {line}: a payload directory was left")
        if trial["alive"]:
            problems.append(f"line {line}: the stand-in client was left running")
        if trial["info"].get("unreadable_record"):
            problems.append(f"line {line}: the driver's record was unreadable")
        if line in before_spawn and trial["started"]:
            problems.append(f"line {line}: a client was started although the signal landed at or before the spawn guard")
    live = sum(1 for trial in trials if trial["info"].get("alive_at_fire") == [True])
    if live < 10:
        problems.append(f"the client was running when the signal fired at only {live} lines (at least 10 expected): the sweep did not exercise the client's lifetime")
    code_lines = len(frozenset(number for function in (main, with_private_dir, measure, end_by_latched_signal, emit_report) for _start, _end, number in function.__code__.co_lines() if number and number > function.__code__.co_firstlineno))
    return not problems, (f"{len(lines)} lines swept of the {code_lines} lines with code in main, with_private_dir, measure, end_by_latched_signal and emit_report ({len(before_spawn)} of them up to the spawn guard), the client was running at {live} of them, "
                          f"{len(problems)} problems" + ("" if not problems else " | " + "; ".join(problems[:4])))


def wchan_exposed():
    """Whether this kernel shows a wait channel in /proc/<pid>/wchan: a short sleeping child must show something other than 0."""
    child = subprocess.Popen(["sleep", "5"])
    try:
        time.sleep(0.3)
        return Path(f"/proc/{child.pid}/wchan").read_text().strip() not in ("", "0")
    except OSError:
        return False
    finally:
        child.kill()
        child.wait()


def wait_until_blocked_in_write(pid, limit=15.0):
    """True once /proc/<pid>/wchan names a pipe wait, that is, once the child is blocked in its write to the full pipe; False when it never does within `limit` seconds (the caller sends the signal anyway and the detail says that it was not seen blocked);
    None when this kernel exposes no wait channel (a fixed 2 s wait is used, as the first version of the case did)."""
    if not wchan_exposed():
        time.sleep(2)
        return None
    deadline = time.time() + limit
    while time.time() < deadline:
        try:
            if "pipe" in Path(f"/proc/{pid}/wchan").read_text():
                return True
        except OSError:
            return False      # the child is gone
        time.sleep(0.05)
    return False


def flush_case(kind):
    """The probe must end BY the latched signal, or exit with the measurement's own status, when stdout cannot take a write (finding U2 of the post-merge GPT read and finding B2 of the Codex review bot's read of this change). The real `main` runs with a measurement that leaves
    a line in the buffer of stdout (the children run without PYTHONUNBUFFERED, which would send that line to the descriptor at once, under the latch) and, in two of the children, signals itself, so that the latch is set when the cleanup has run: the signal handoff must come before
    any output, since a flush would raise on a closed descriptor and a write to a full pipe would block for good (a handler that only returns does not interrupt it: PEP 475). The children: stdout closed and a latched SIGTERM; stdout closed and no signal (the exit status must be the
    measurement's, 0, not 120 from a failed final flush); a full pipe nobody reads and a latched SIGTERM; a full pipe and nothing latched, the SIGTERM being sent once the child is seen blocked in its write (the handoff has given the handled signals back to their default action, so the
    signal is not latched and lost); and `end_by_latched_signal` called directly with SIGTERM latched and blocked in the mask inherited from the parent (the kill would leave a blocked signal pending). Each child runs with its own temporary directory, which must hold no payload
    directory afterwards, and must end within 20 s with the status stated for it. Returns (ok, detail)."""
    path = str(Path(__file__).resolve())
    expected = {"closed-stdout-exit": 0}      # every other child must die by SIGTERM
    results = []
    for mode in ("closed-stdout", "closed-stdout-exit", "full-pipe", "late-signal", "blocked-signal"):
        with tempfile.TemporaryDirectory(prefix="flush-") as raw:
            tmp = Path(raw)
            argv = [sys.executable, "-B", "-c", FLUSH_CHILD, path, mode, kind]
            env = {key: value for key, value in os.environ.items() if key != "PYTHONUNBUFFERED"}
            env["TMPDIR"] = str(tmp)
            blocked = None
            if mode in ("full-pipe", "late-signal"):
                read_end, write_end = os.pipe()
                fcntl.fcntl(write_end, fcntl.F_SETFL, fcntl.fcntl(write_end, fcntl.F_GETFL) | os.O_NONBLOCK)
                try:
                    while True:
                        os.write(write_end, b"x" * 4096)
                except BlockingIOError:
                    pass      # the pipe is full and nobody reads it
                fcntl.fcntl(write_end, fcntl.F_SETFL, fcntl.fcntl(write_end, fcntl.F_GETFL) & ~os.O_NONBLOCK)
                child = subprocess.Popen(argv, env=env, stdout=write_end, stderr=subprocess.DEVNULL)
                os.close(write_end)
            else:
                child = subprocess.Popen(argv, env=env, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            try:
                if mode == "late-signal":
                    blocked = wait_until_blocked_in_write(child.pid)
                    child.send_signal(signal.SIGTERM)
                code = child.wait(timeout=20)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
                code = None
            if mode in ("full-pipe", "late-signal"):
                os.close(read_end)
            else:
                child.stdout.close()
            left = len(list(tmp.iterdir()))
        results.append((mode, code, left, blocked))
    ok = all(code == expected.get(mode, -signal.SIGTERM) and not left for mode, code, left, _blocked in results)
    return ok, "; ".join(f"{mode}: " + (f"the child ended with {code} (expected {expected.get(mode, -signal.SIGTERM)}), payload directories left {left}" if code is not None else "the child was still running after 20 s and was killed")
                         + ("" if mode != "late-signal" else f" (blocked in its write when the signal was sent: {'yes' if blocked else 'not observed, a fixed wait was used' if blocked is None else 'NO'})") for mode, code, left, blocked in results)


def noout_case():
    """The functions that run while the latch is installed must not write to stdout or stderr themselves: a write to a stuck descriptor cannot be interrupted by a handler that only returns (PEP 475), so `measure` collects its result lines with `say` for `emit_report`, which runs after
    the handoff, and `type_prompt` writes only to the pty (finding B2 of the Codex review bot's read of this change). Reads the probe's own source: in `measure` and in `type_prompt` no call of `print`, of `sys.stdout.write`, `sys.stderr.write` (or `writelines`) or of `os.write` with the descriptor 1 or 2,
    and at least five calls of `say` in `measure` (so that an emptied function cannot pass). It is a structural guard for the two functions that could write; the behaviour itself is the flush case. Returns (ok, detail)."""
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    functions = {each.name: each for each in ast.walk(tree) if isinstance(each, ast.FunctionDef) and each.name in ("measure", "type_prompt")}
    writes, says = [], 0
    for name, node in functions.items():
        for call in (each for each in ast.walk(node) if isinstance(each, ast.Call)):
            target = call.func
            if isinstance(target, ast.Name) and target.id == "print":
                writes.append(f"{name}:{call.lineno}")
            elif isinstance(target, ast.Attribute) and target.attr in ("write", "writelines") and ast.unparse(target.value) in ("sys.stdout", "sys.__stdout__", "sys.stderr", "sys.__stderr__"):
                writes.append(f"{name}:{call.lineno}")
            elif ast.unparse(target) == "os.write" and call.args and isinstance(call.args[0], ast.Constant) and call.args[0].value in (1, 2):
                writes.append(f"{name}:{call.lineno}")
            elif isinstance(target, ast.Name) and target.id == "say" and name == "measure":
                says += 1
    return len(functions) == 2 and not writes and says >= 5, f"`measure` collects {says} result lines with `say`; `measure` and `type_prompt` write to stdout or stderr themselves at {len(writes)} places"


def handoff_case(kind):
    """A second signal that arrives AFTER the cleanups must not replace the first one (finding U3): SIGINT is delivered at the first line of `measure` (the spawn guard then starts no client) and SIGTERM at the line of `main`
    that returns after `with_private_dir`, when the previous handlers would already be back if they were restored; the driver then runs what the probe's own `__main__` block runs. The probe must end BY SIGINT (return code
    -2) and leave no payload directory. The stand-in client of the arena stands in for the real `claude`, which must never start here. Returns (ok, detail)."""
    if not (Path.home() / "code/native-agent-stack").is_dir():
        return None, "skipped (the probe's working directory does not exist on this machine)"
    path = str(Path(__file__).resolve())
    source = Path(path).read_text(encoding="utf-8").splitlines()
    first = next(number for number, text in enumerate(source, 1) if text.strip() == 'log.write_text("")')
    second = next(number for number, text in enumerate(source, 1) if text.strip().startswith("return signal_status() or status"))
    with tempfile.TemporaryDirectory(prefix="handoff-") as raw:
        env, tmp, pidfile, unique = arena(Path(raw), "sleep", 300)
        try:
            code = subprocess.run([sys.executable, "-B", "-c", HANDOFF_DRIVER, path, kind, str(first), str(second)], env=env, capture_output=True, timeout=120).returncode
        except subprocess.TimeoutExpired:
            code = "timeout"
        client = int(pidfile.read_text().strip()) if pidfile.exists() and pidfile.read_text().strip().isdigit() else None
        alive = client is not None and stand_in_alive(client, unique)
        if alive:
            os.kill(client, signal.SIGKILL)
        left = len(list(tmp.glob("alert-probe-*")))
    ok = code == -signal.SIGINT and not left and not alive
    return ok, f"SIGINT at line {first}, SIGTERM at line {second}: the probe ended with {code} (expected {-signal.SIGINT}), payload directories left {left}, stand-in still alive {alive}"


def partial_case():
    """A sweep driver killed while it writes its record leaves a truncated record.json: `sweep_trial` must report it (info["unreadable_record"]) and still kill the stand-in client, instead of raising before the kill
    (finding U5). subprocess.run is replaced for the call by a function that starts the stand-in `sleep <unique>`, publishes its PID and writes a truncated record. Returns (ok, detail)."""
    path = str(Path(__file__).resolve())
    started = []
    real_run = subprocess.run

    def fake_run(argv, **kwargs):
        # argv: python, -B, -c, <driver code>, path, kind, target, record, pidfile, unique
        record, pidfile, unique = Path(argv[7]), Path(argv[8]), argv[9]
        client = subprocess.Popen(["sleep", unique], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        started.append(client)
        pidfile.write_text(str(client.pid))
        record.write_text('{"lines": [1, 2')
        return subprocess.CompletedProcess(argv, 0, b"", b"")

    subprocess.run = fake_run
    try:
        trial = sweep_trial(path, "ask", 5, "sleep", 7)
        error = None
    except Exception as failure:      # the repaired code does not raise
        trial, error = None, f"{type(failure).__name__}"
    finally:
        subprocess.run = real_run
        for client in started:
            if client.poll() is None:
                time.sleep(0.2)
                if client.poll() is None:
                    client.kill()
                    client.wait()
    killed = bool(started) and started[0].returncode == -signal.SIGKILL
    ok = error is None and trial["info"].get("unreadable_record") is True and killed
    return ok, f"a truncated record: sweep_trial raised {error}; record reported unreadable {None if trial is None else trial['info'].get('unreadable_record')}; the stand-in was killed {killed}"


def typing_case():
    """`type_prompt` with fake writers and sleepers: (1) a stop latched after five keystrokes sends no further keystroke and no Enter; (2) a stop latched by the LAST keystroke sends no Enter and never reaches the 0.4 s
    wait; (3) a stop latched during that wait sends no Enter; (4) a SIGTERM sent right after the final check, before the Enter is written, stays pending (the handled signals are blocked around the check and the write):
    the latch is not set when the Enter is written and is set right after, so no Enter is ever written after the latch is set; (5) with no stop every keystroke and the Enter are sent. Returns (ok, detail)."""
    global stopped
    problems = []

    def fresh():
        STOP["signal"] = None

    # (1) a stop after five keystrokes
    sent = []

    def stop_after_five(_fd, data):
        sent.append(data)
        if len(sent) == 5:
            STOP["signal"] = signal.SIGTERM

    fresh()
    first = type_prompt(0, "x" * 20, write=stop_after_five, sleep=lambda _seconds: None)
    if first is not False or len(sent) != 5 or b"\r" in sent:
        problems.append(f"(1) a stop after five keystrokes: Enter sent {first}, {len(sent)} keystrokes")
    # (2) a stop latched by the last keystroke: no Enter and no 0.4 s wait
    sent, sleeps = [], []

    def stop_at_last(_fd, data):
        sent.append(data)
        if len(sent) == 3:
            STOP["signal"] = signal.SIGTERM

    fresh()
    second = type_prompt(0, "abc", write=stop_at_last, sleep=sleeps.append)
    if second is not False or b"\r" in sent or 0.4 in sleeps:
        problems.append(f"(2) a stop at the last keystroke: Enter sent {second}, the 0.4 s wait reached {0.4 in sleeps}")
    # (3) a stop latched during the 0.4 s wait
    sent = []

    def stop_in_wait(seconds):
        if seconds == 0.4:
            STOP["signal"] = signal.SIGTERM

    fresh()
    third = type_prompt(0, "abc", write=lambda _fd, data: sent.append(data), sleep=stop_in_wait)
    if third is not False or b"\r" in sent:
        problems.append(f"(3) a stop during the wait: Enter sent {third}")
    # (4) a SIGTERM sent right after the final check
    sent, at_enter = [], []
    real_stopped, checks = stopped, []
    old_handler = signal.signal(signal.SIGTERM, latch)

    def check_then_signal():
        value = real_stopped()
        checks.append(value)
        if len(checks) == 3 and not value:      # the third check of a one-character prompt is the final one, before the Enter
            os.kill(os.getpid(), signal.SIGTERM)
        return value

    def write_and_note(_fd, data):
        sent.append(data)
        if data == b"\r":
            at_enter.append(STOP["signal"])

    fresh()
    stopped = check_then_signal
    try:
        fourth = type_prompt(0, "a", write=write_and_note, sleep=lambda _seconds: None)
        time.sleep(0.05)
        latched_after = STOP["signal"]
    finally:
        stopped = real_stopped
        signal.signal(signal.SIGTERM, old_handler)
        fresh()
    if fourth is not True or at_enter != [None] or latched_after != signal.SIGTERM:
        problems.append(f"(4) a signal right after the final check: Enter sent {fourth}, the latch when Enter was written {at_enter}, after {latched_after}")
    # (5) no stop
    plain = []
    fresh()
    fifth = type_prompt(0, "abc", write=lambda _fd, data: plain.append(data), sleep=lambda _seconds: None)
    if fifth is not True or plain != [b"a", b"b", b"c", b"\r"]:
        problems.append(f"(5) no stop: Enter sent {fifth}, writes {plain}")
    return not problems, "five typing situations checked" if not problems else " | ".join(problems)


def ignored_case():
    """A signal that the parent ignored (nohup, a background job) stays ignored: `with_private_dir` installs the latch only for the others. Ignores SIGHUP, runs `with_private_dir` with a work function that sends SIGHUP to
    the process, and checks that nothing was latched, that the disposition was SIG_IGN inside the work and that it is SIG_IGN again after it. Returns (ok, detail)."""
    before = signal.getsignal(signal.SIGHUP)
    inside = []
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
    try:
        def work(_private):
            inside.append(signal.getsignal(signal.SIGHUP))
            os.kill(os.getpid(), signal.SIGHUP)
            time.sleep(0.05)
            return 7

        result = with_private_dir(work)
        latched, after = STOP["signal"], signal.getsignal(signal.SIGHUP)
        STOP["signal"] = None
    finally:
        signal.signal(signal.SIGHUP, before)
    ok = result == 7 and latched is None and inside == [signal.SIG_IGN] and after == signal.SIG_IGN
    # the end of the process: with nothing latched, `end_by_latched_signal` gives the latch's signals back to the default action, and the one the parent ignored stays ignored
    saved = {number: signal.getsignal(number) for number in HANDLED}
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
    try:
        with_private_dir(lambda _private: 0, restore=False)
        end_by_latched_signal()
        ending = {number: signal.getsignal(number) for number in HANDLED}
    finally:
        for number, handler in saved.items():
            signal.signal(number, handler)
    expected = {signal.SIGHUP: signal.SIG_IGN, signal.SIGTERM: signal.SIG_DFL, signal.SIGINT: signal.SIG_DFL}
    ok = ok and ending == expected
    return ok, f"an ignored SIGHUP: work result {result}, latched {latched}, disposition inside the work {inside}, after {after}; at the end of the process SIGHUP {ending[signal.SIGHUP]}, SIGTERM {ending[signal.SIGTERM]}, SIGINT {ending[signal.SIGINT]}"


def selftest():
    ignored = [signal.Signals(number).name for number in HANDLED if signal.getsignal(number) is signal.SIG_IGN]
    if ignored:
        print(f"REFUSED: {', '.join(ignored)} ignored in this process (nohup, or a background job of a non-interactive sh, which ignores SIGINT): the probe honors an inherited ignore, so the cases that send it would fail; start the selftest from a shell that does not ignore it")
        return 2
    cases = [
        ("plain BEL", [b"\x07"], 1),
        ("two BELs in one read", [b"ab\x07\x07cd"], 2),
        ("OSC title ended by BEL", [b"\x1b]0;title\x07"], 0),
        ("OSC title ended by BEL, split across reads", [b"\x1b]0;tit", b"le\x07"], 0),
        ("ESC split from its bracket", [b"\x1b", b"]0;t\x07"], 0),
        ("OSC ended by ST then a bare BEL", [b"\x1b]0;t\x1b\\", b"\x07"], 1),
        ("BEL after an OSC and another bare BEL", [b"\x1b]0;x\x07\x07"], 1),
        ("CSI colour then BEL", [b"\x1b[38;2;1;2;3m\x07"], 1),
        ("ESC then BEL: executed in the escape state", [b"\x1b\x07"], 1),
        ("ESC then BEL, split across reads", [b"\x1b", b"\x07"], 1),
        ("OSC text, ESC, then BEL: the BEL executes in the escape state", [b"\x1b]0;t\x1b\x07"], 1),
        ("OSC text, ESC, then BEL, split across reads", [b"\x1b]0;t", b"\x1b", b"\x07"], 1),
        ("DCS interrupted by ESC ESC, ST, then BEL", [b"\x1bPq\x1b\x1b\\\x07"], 1),
        ("APC ended by ST, then BEL", [b"\x1b_note\x1b\\\x07"], 1),
        ("BEL inside a DCS string is not a bell", [b"\x1bPqab\x07cd\x1b\\"], 0),
        ("BEL inside an APC string is not a bell", [b"\x1b_ab\x07cd\x1b\\"], 0),
        ("BEL inside a CSI sequence executes", [b"\x1b[1\x07m"], 1),
        ("CAN inside an OSC string returns to ground, then BEL", [b"\x1b]0;t\x18\x07"], 1),
        ("SUB inside a DCS string returns to ground, then BEL", [b"\x1bPqab\x1a\x07"], 1),
        ("BEL after an escape intermediate sequence", [b"\x1b(B\x07"], 1),
        ("OSC ended by ST, split between ESC and backslash, then BEL", [b"\x1b]0;t\x1b", b"\\", b"\x07"], 1),
        ("NUL, TAB and LF are C0 controls but not bells", [b"\x00\t\n\r"], 0),
        ("UTF-8 C1 character inside an escape sequence is ignored, so ESC ] still opens an OSC that the BEL ends", [b"\x1b\xc2\x80]\x07"], 0),
        ("the same split between the two UTF-8 bytes", [b"\x1b\xc2", b"\x80]\x07"], 0),
        ("the same split before the continuation byte and after the bracket", [b"\x1b\xc2\x80", b"]", b"\x07"], 0),
        ("a C1 character in ground does not hide a following bell", [b"\xc2\x9b\x07"], 1),
        ("a two-byte character above C1 ends the escape state like any printable", [b"\x1b\xc3\xa9]\x07"], 1),
        ("an invalid UTF-8 byte is a printable replacement character", [b"\x1b\xff]\x07"], 1),
    ]
    bad = 0
    for label, reads, expected in cases:
        counter = BelCounter()
        got = sum(counter.feed(chunk) for chunk in reads)
        ok = got == expected
        bad += 0 if ok else 1
        print(("PASS " if ok else "FAIL ") + label + f": expected {expected}, got {got}")
    for label, error in (("private directory removed after an interruption", KeyboardInterrupt), ("private directory removed after a failure", RuntimeError)):
        seen = []

        def boom(private, error=error):
            seen.append(private)
            (private / "events.log").write_text("stand-in for a raw hook payload")
            raise error()

        try:
            with_private_dir(boom)
        except error:
            pass
        ok = len(seen) == 1 and not seen[0].exists()
        bad += 0 if ok else 1
        print(("PASS " if ok else "FAIL ") + label)
    for name, signums in (("SIGTERM", (signal.SIGTERM,)), ("SIGHUP", (signal.SIGHUP,)), ("SIGINT", (signal.SIGINT,)), ("SIGTERM then SIGINT (the first is kept)", (signal.SIGTERM, signal.SIGINT))):
        seen = []
        before = {number: signal.getsignal(number) for number in HANDLED}

        def carry_on(private, signums=signums):
            seen.append(private)
            (private / "events.log").write_text("stand-in for a raw hook payload")
            for number in signums:
                os.kill(os.getpid(), number)
                time.sleep(0.01)   # the handler of this signal runs before the next one is sent
            return 7   # the work carries on: a handler never interrupts it

        result = with_private_dir(carry_on)
        latched = STOP["signal"]
        after = {number: signal.getsignal(number) for number in HANDLED}
        STOP["signal"] = None
        ok = result == 7 and latched == signums[0] and len(seen) == 1 and not seen[0].exists() and after == before
        bad += 0 if ok else 1
        print(("PASS " if ok else "FAIL ") + f"a {name} in the work is latched, the work carries on, the directory is removed and the previous handlers return"
              + ("" if ok else f" (result {result}, latched {latched}, directory left {seen[0].exists() if seen else None}, handlers restored {after == before})"))
    for label, function in (("an inherited SIG_IGN stays: the latch is not installed for a signal the parent ignored", ignored_case), ("typing stops at a latched signal and sends no Enter, and never after the latch is set", typing_case), ("a truncated sweep record is reported and the stand-in killed", partial_case), ("no output is written while the latch is installed: `measure` and `type_prompt` write nothing to stdout or stderr", noout_case)):
        ok, detail = function()
        bad += 0 if ok else 1
        print(("PASS " if ok else "FAIL ") + label + f": {detail}")
    for label, given, expected in (("exit status: an observed tool call and no BEL passes", (1.0, False, 0), 0), ("exit status: a hooks-disabled control with a dialog and no BEL passes", (1.0, True, 0), 0),
                                   ("exit status: a hooks-disabled control that saw a BEL fails", (1.0, True, 1), 1), ("exit status: a control whose dialog never opened fails", (None, True, 0), 2),
                                   ("exit status: a run whose tool call was never observed fails", (None, False, 0), 2)):
        got = exit_status(*given)
        bad += 0 if got == expected else 1
        print(("PASS " if got == expected else "FAIL ") + label + f": expected {expected}, got {got}")
    for label, function, expected in (
            ("one SIGTERM", lambda: signal_case("push"), True),
            ("two SIGTERMs 100 ms apart", lambda: signal_case("push", signums=(signal.SIGTERM, signal.SIGTERM)), True),
            ("two SIGINTs 100 ms apart", lambda: signal_case("push", signums=(signal.SIGINT, signal.SIGINT)), True),
            ("SIGTERM then SIGINT: the first signal is the one that ends the probe", lambda: signal_case("push", signums=(signal.SIGTERM, signal.SIGINT)), True),
            ("a SIGTERM at each line a dry run reaches", lambda: sweep_case("push"), True),
            ("the measurement's exit status: 2 when the dialog never opened, 1 for a control that saw a BEL, 0 for a quiet one", lambda: status_case("ask"), True),
            ("a closed or stuck stdout or a blocked signal does not keep the probe from ending by the signal", lambda: flush_case("push"), True),
            ("a second signal after the cleanups does not replace the first", lambda: handoff_case("push"), True),
            ("negative control: a client that never starts is rejected by a signal case", lambda: signal_case("push", stand_in="true"), False),
            ("negative control: a client that exits at once is rejected by the sweep", lambda: sweep_case("push", stand_in="trust-exit"), False)):
        ok, detail = function()
        if ok is None:
            print(f"SKIP end to end, {label}: {detail}")
            continue
        good = ok == expected
        bad += 0 if good else 1
        print(("PASS " if good else "FAIL ") + f"end to end, {label}: {detail}")
    return 1 if bad else 0


def exit_status(t_open, control, bel_total):
    """0 when the run reached the observation point (the tool call or dialog was observed) and, for the hooks-disabled control, no BEL byte appeared; 2 when it never reached it; 1 when the control saw a BEL."""
    if t_open is None:
        return 2
    return 1 if control and bel_total else 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("kind", nargs="?", choices=["ask", "plan", "push"])
    parser.add_argument("--no-user-settings", action="store_true", help="push only: load no user-scope settings (--setting-sources local) and start in bypassPermissions, so only this probe's own hooks exist")
    parser.add_argument("--sleep", type=int, default=45, help="push only: seconds the model waits (a shell sleep) before it calls the tool")
    parser.add_argument("--no-focus-report", action="store_true", help="push only: never answer the client's focus reporting with a focus-out report")
    parser.add_argument("--show-screen", action="store_true", help="also print the last 260 characters of the terminal screen (contents of the session: never put them in a receipt)")
    parser.add_argument("--bell-hook", action="store_true", help="push only: add a Notification hook that emits one BEL for the type push_notification")
    parser.add_argument("--control", action="store_true")
    parser.add_argument("--permission-mode", choices=["default", "acceptEdits", "bypassPermissions"],
                        help="ask only: start in this mode instead of the user's own default")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    if not args.kind:
        parser.error("kind is required unless --selftest")
    if args.kind == "plan" and args.permission_mode:
        parser.error("plan is always started in plan mode")

    used = []

    def work(private):
        used.append(private)
        return measure(args, private)

    try:
        status = with_private_dir(work, restore=False)
        return signal_status() or status   # the answer of a run that latched nothing: a latched signal ends the process in the `finally` below
    finally:
        end_by_latched_signal()   # the last safe point: a latched signal ends the process BY it now, before any output; with none latched every handled signal is back to its default action
        emit_report(used)         # so a signal during the output, or a stuck stdout, cannot hold the process


HANDLED = (signal.SIGTERM, signal.SIGHUP, signal.SIGINT)
STOP = {"signal": None}   # the FIRST handled signal, latched by `latch`


def latch(signum, _frame=None):
    """The handler of SIGINT, SIGTERM and SIGHUP: remember the first signal and return, nothing else. A handler that raised (SystemExit, as an earlier version did) can fire between any two statements, between
    acquiring a resource and recording it, or at the entry of a cleanup, and cut either short; this one cannot, so no signal leaves the client, the pty or the payload directory behind. The code acts on the latch at
    explicit safe points (before the client is started, in the observation loop) and, after the cleanup has run, ends the process BY that signal (`end_by_latched_signal`). "First" means the first to be DISPATCHED: signals that are pending together run their Python handlers in ascending signal number
    (measured, `signal_order_probe.py` in the review artifact directory: SIGHUP, then SIGINT, then SIGTERM, whatever the sending order), so two signals that land within one dispatch are ordered by number, not by arrival."""
    if STOP["signal"] is None:
        STOP["signal"] = signum


def stopped():
    return STOP["signal"] is not None


def signal_status():
    """The exit status a latched signal asks for (128 + its number), or None."""
    return None if STOP["signal"] is None else 128 + STOP["signal"]


REPORT = []   # the result lines of the measurement: printed by `emit_report` after the handoff, never while the latch is installed


def say(*parts):
    """Collect one result line (the arguments of `print`, joined by spaces). `measure` runs while the latch is installed, and a write to a stuck stdout cannot be interrupted by a handler that only returns (PEP 475 retries the write):
    it collects its lines here and `emit_report` prints them after `end_by_latched_signal` (finding B2 of the Codex review bot's read of this change)."""
    REPORT.append(" ".join(str(part) for part in parts))


def emit_report(used):
    """Print the collected result lines and the cleanup's one line, after `end_by_latched_signal`: no latch is installed any more, so a signal during the output takes its default action and ends the process, and a stuck stdout cannot hold it.
    A closed or broken stdout is tolerated (what is left in its buffer goes to devnull, so that the final flush cannot change the exit status); a line that cannot be encoded is not."""
    try:
        for line in REPORT:
            print(line)
        print("raw payload directory removed:", bool(used) and not used[0].exists(), flush=True)
    except UnicodeEncodeError:
        raise      # a line that this stdout cannot encode is a defect to see, not a closed pipe to ignore
    except (OSError, ValueError):
        # a closed or broken stdout: the bytes still in its buffer would fail again in the interpreter's final flush and the exit status would be 120 instead of the measurement's,
        # so the rest goes to devnull (the Python signal documentation, "Note on SIGPIPE")
        try:
            os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        except (OSError, ValueError):
            sys.stdout = open(os.devnull, "w")


def end_by_latched_signal():
    """The last safe point: the latch's life ends here. With the handled signals BLOCKED (no handler can run, so the latch cannot change between the snapshot and what follows) the latch is read. If a signal was latched, the process ends BY it
    after the cleanups: its default action, the signal unblocked, then the signal sent to itself (a shell that waits cooperatively, bash among them, tells "died of SIGINT" from "exited with 130" when it has received the SIGINT too, as Ctrl-C
    sends it to the whole foreground group: after a child that only exits 130 its loop goes on, after a child that ends by the signal it stops, measured by `shell_loop_control.py` in the review artifact directory, which also records that dash
    behaves differently; Cracauer, "Proper handling of SIGINT/SIGQUIT", cons.org/cracauer/sigint.html: the only way to report it is to kill yourself with the signal, since an exit status cannot fake it). If none was latched, every handler that is
    still the latch goes back to the default action (a signal the parent ignored was never taken over and stays ignored) and the old mask comes back: a signal that arrived during the block is pending and now takes its default action, which ends
    the process BY it, and a later one does the same. The latch, a handler that only returns, must not outlive this point: a signal that landed after the snapshot would be latched and never acted on (the final handoff window, finding B1 of the Codex review bot's read of this change), and a blocking write after it could not be interrupted, since PEP 475 retries a system call after a handler that returns (finding B2). Nothing is flushed here (finding U2 of the post-merge GPT read): the output
    follows from `emit_report`."""
    blocked = signal.pthread_sigmask(signal.SIG_BLOCK, HANDLED)      # nothing below can be overtaken by a handler
    number = STOP["signal"]
    if number is None:
        for each in HANDLED:
            if signal.getsignal(each) is latch:
                signal.signal(each, signal.SIG_DFL)
        signal.pthread_sigmask(signal.SIG_SETMASK, blocked)      # a signal that is pending now meets its default action
        return
    signal.signal(number, signal.SIG_DFL)
    signal.pthread_sigmask(signal.SIG_UNBLOCK, {number})      # a mask inherited from the parent would leave the signal pending
    os.kill(os.getpid(), number)


def type_prompt(master, prompt, write=os.write, sleep=time.sleep):
    """Type the prompt into the client and press Enter, unless a stop request has been latched. The Enter is the only keystroke that submits a model turn, so its check and its write are made with the handled signals BLOCKED: a handler
    cannot run between them, the latch cannot flip, and a signal that arrives meanwhile stays pending and is latched right after the write. Exactly: no Enter is ever written after the latch is set (finding U4 of the post-merge GPT
    read). The block surrounds one write to the pty master, never a spawn, so no child inherits it. Returns True when the Enter was sent."""
    for character in prompt:
        if stopped():
            return False
        write(master, character.encode())
        sleep(0.004)
    if stopped():
        return False
    sleep(0.4)
    before = signal.pthread_sigmask(signal.SIG_BLOCK, HANDLED)
    try:
        if stopped():
            return False
        write(master, b"\r")
    finally:
        signal.pthread_sigmask(signal.SIG_SETMASK, before)
    return True


def with_private_dir(work, restore=True):
    """Install the latch handler first, create the private directory, run work(private_dir), and remove the directory and, when `restore` is true, restore the previous handlers whatever happened (a normal return, an exception, a latched
    signal). Returns what work returns; the caller ends the process by a latched signal after this cleanup. `main` passes restore=False: the latch then stays installed until `end_by_latched_signal` (the end of its life: the process ends BY the first signal, or every handled signal goes back to its default action), so a SECOND signal that arrives after the
    cleanups (when the previous handlers, SIGTERM's default among them, would be back) is latched too and cannot end the probe by another signal than the first one (finding U3 of the post-merge GPT read)."""
    STOP["signal"] = None
    previous = {}
    for number in HANDLED:
        if signal.getsignal(number) is not signal.SIG_IGN:   # a signal the parent ignored (nohup, a background job) stays ignored
            previous[number] = signal.signal(number, latch)
    private = None
    try:
        private = Path(tempfile.mkdtemp(prefix="alert-probe-"))
        return work(private)
    finally:
        if private is not None:
            shutil.rmtree(private, ignore_errors=True)
        if restore:
            for number, handler in previous.items():
                signal.signal(number, handler)


def measure(args, private):
    log = private / "events.log"
    log.write_text("")
    if args.kind == "push":
        prompt = f"Run the shell command sleep {args.sleep}. When it finishes, call the PushNotification tool exactly once with status proactive and the message 'readiness probe'. Then stop."
        mode = "bypassPermissions" if args.no_user_settings else args.permission_mode
    elif args.kind == "ask":
        prompt = "Call the AskUserQuestion tool exactly once with a single question about whether the probe is ready, offering the options Yes and No. Do nothing else and do not answer it yourself."
        mode = args.permission_mode  # None: the user's own default mode
    else:
        prompt = "Write the one-line plan 'do nothing' to your plan file and immediately call ExitPlanMode. Do nothing else."
        mode = "plan"

    def observer(tag):
        return f"sh -c 'printf \"%s {tag} \" \"$(date +%s.%N)\" >> {log}; cat >> {log}; echo >> {log}'"

    overlay = {"hooks": {
        "PreToolUse": [{"matcher": "AskUserQuestion|ExitPlanMode|PushNotification", "hooks": [{"type": "command", "command": observer("PRE")}]}],
        "Notification": [{"matcher": "", "hooks": [{"type": "command", "command": observer("NOTIF")}]}],
    }}
    if args.kind == "push" and args.bell_hook:
        overlay["hooks"]["Notification"].append({"matcher": "push_notification", "hooks": [{"type": "command", "command": "jq -nc --arg s \"$(printf '\\a')\" '{terminalSequence:$s}'"}]})
    sources = "local" if args.no_user_settings else "user"
    if args.control:
        # Same session with the user's settings, but every hook off: no observer and no user Notification hook. The dialog
        # still opens (detected from its own on-screen text) and no BEL may appear, which attributes the BEL to the hook.
        overlay = {"disableAllHooks": True}

    env = dict(os.environ)
    env.update({"TERM": "xterm-256color", "COLORTERM": "truecolor", "WT_SESSION": "alert-probe", "LANG": "C.UTF-8", "DISABLE_AUTOUPDATER": "1"})
    cwd = str(Path.home() / "code/native-agent-stack")  # already trusted: the probe never accepts a trust dialog
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 45, 140, 0, 0))
    mode_flags = ["--permission-mode", mode] if mode else []
    proc = None
    slave_open = True
    try:
        if not stopped():   # SPAWN GUARD: a signal latched before this point starts no client
            proc = subprocess.Popen(["claude", "--model", "haiku" if args.kind == "push" else "sonnet", *mode_flags, "--setting-sources", sources,
                                     "--settings", json.dumps(overlay), "-n", f"alert-probe-{args.kind}"],
                                    stdin=slave, stdout=slave, stderr=slave, env=env, cwd=cwd, start_new_session=True, close_fds=True)
        os.close(slave)
        slave_open = False

        ansi = re.compile(r"\x1b\[[0-9;?<>=]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b[()][A-Z0-9]|\x1b[=>MNOP78]")
        counter = BelCounter()
        bel_events = []  # (epoch seconds, bare BEL bytes in that read)
        buf = b""
        events = []
        state = "startup"
        sent_focus_out = False
        focus_reporting_enabled = False
        t_focus_out = None
        t_enter = None
        t_open = None
        t0 = time.time()

        def pump(timeout=0.2):
            nonlocal buf
            ready, _, _ = select.select([master], [], [], timeout)
            if not ready:
                return
            try:
                chunk = os.read(master, 65536)
            except OSError:
                return
            buf += chunk
            bare = counter.feed(chunk)
            if bare:
                bel_events.append((time.time(), bare))
            if b"\x1b[6n" in chunk:
                os.write(master, b"\x1b[1;1R")
            if b"\x1b[c" in chunk or b"\x1b[0c" in chunk:
                os.write(master, b"\x1b[?62;c")
            if b"\x1b]11;?" in chunk:
                os.write(master, b"\x1b]11;rgb:0000/0000/0000\x1b\\")

        def log_lines():
            return [ln for ln in log.read_text().splitlines() if ln.strip()]

        while not stopped() and time.time() - t0 < (260 if args.kind == "push" else 200):
            pump()
            now = time.time()
            if state == "startup" and now - t0 > 6 and (args.kind != "push" or b"\x1b[?1004h" in buf or now - t0 > 60):
                # push: wait until the client has enabled focus reporting (its input is drawn by then), at most 60 s, so a slow start under load does not swallow the prompt
                screen = ansi.sub("", buf.decode("utf-8", "replace")).lower()
                if "trust" in screen and ("folder" in screen or "files" in screen):
                    events.append("trust dialog appeared: aborted (the probe never accepts trust)")
                    state = "aborted"
                    break
                screen_now = re.sub(r"\s+", "", ansi.sub("", buf.decode("utf-8", "replace"))).lower()
                footers = {"bypasspermissionson": "bypassPermissions", "accepteditson": "acceptEdits", "planmodeon": "plan", "autoon": "auto"}
                seen = {name: screen_now.rfind(marker) for marker, name in footers.items() if marker in screen_now}
                mode_seen = max(seen, key=seen.get) if seen else "default (no mode footer)"
                events.append("permission mode footer at prompt time: " + mode_seen)
                typed = type_prompt(master, prompt)
                t_enter = time.time()
                state = "waiting_tool" if typed else "stopped"
                events.append("prompt sent" if typed else "a stop request arrived while the prompt was typed: no Enter sent")
            elif state == "waiting_tool" and args.control:
                # Distinctive dialog text, whitespace-insensitive: the AskUserQuestion footer, or the plan-approval question.
                compact = re.sub(r"\s+", "", ansi.sub("", buf.decode("utf-8", "replace"))).lower()
                markers = ("entertoselect",) if args.kind == "ask" else ("readytocode", "yes,anduseautomode")
                if any(m in compact for m in markers):
                    t_open = time.time()
                    state = "observing"
                    events.append("dialog text seen on screen (dialog open); hooks disabled; no keys sent for 16 s")
            elif state == "waiting_tool":
                if args.kind == "push" and b"\x1b[?1004h" in buf:
                    focus_reporting_enabled = True
                if args.kind == "push" and not args.no_focus_report and not sent_focus_out and focus_reporting_enabled:
                    os.write(master, b"\x1b[O")   # focus-out: the terminal reports that it is not focused
                    sent_focus_out = True
                    t_focus_out = time.time()
                for line in log_lines():
                    stamp, _, rest = line.partition(" ")
                    if rest.startswith("PRE ") and ("PushNotification" in rest or args.kind != "push"):
                        t_open = float(stamp)
                        state = "observing"
                        events.append("PreToolUse observed (the tool is being called); no keys sent for 16 s")
                        break
            elif state == "observing" and now - t_open > (20 if args.kind == "push" else 16):
                break
        screen_tail = ansi.sub("", buf.decode("utf-8", "replace"))[-300:].replace("\n", " ")
    finally:
        # the client's cleanup runs to its end whatever signal arrived: a handler only latches the first one
        if proc is not None:
            for key in (b"\x1b", b"\x03"):
                try:
                    os.write(master, key)
                    time.sleep(0.5)
                except OSError:
                    pass
            try:
                os.killpg(proc.pid, signal.SIGTERM)
                time.sleep(0.8)
                os.killpg(proc.pid, signal.SIGKILL)
            except (ProcessLookupError, OSError):
                pass
            try:
                proc.wait(timeout=5)
            except Exception:
                pass
        if slave_open:
            os.close(slave)
        os.close(master)
    if stopped():
        return signal_status()   # a latched signal: no measurement is reported, the exit status says why

    notifications = []
    for line in log_lines():
        stamp, _, rest = line.partition(" ")
        if rest.startswith("NOTIF "):
            try:
                data = json.loads(rest[len("NOTIF "):])
            except ValueError:
                data = {}
            notifications.append((float(stamp), data.get("notification_type"), (data.get("message") or "")[:60]))
    try:
        os.killpg(proc.pid, 0)
        group = "STILL ALIVE"
    except ProcessLookupError:
        group = "gone"

    say(f"kind={args.kind} control={args.control} state={state} dialog_opened={t_open is not None} probe_process_group={group}")
    if args.kind == "push":
        say(f"focus reporting enabled by the client: {focus_reporting_enabled} | focus-out report sent: {sent_focus_out}"
              + (f" ({round(t_focus_out - t_enter, 1)} s after Enter)" if sent_focus_out and t_enter else "")
              + f" | prompt sleep: {args.sleep} s | seconds from Enter to the tool call: {round(t_open - t_enter, 1) if t_open and t_enter else None}")
    say("events:", events)
    if args.control:
        say("Notification events: not observable (every hook is disabled, so the observer hook is off); the BEL byte count below is the measurement")
    else:
        say(f"Notification events: {len(notifications)}")
    for stamp, ntype, message in notifications[:4]:
        say(f"  +{round(stamp - t_open, 1) if t_open else None}s after open | type={ntype} | message length={len(message)}")
    total = 0
    if t_open:
        after = [(round(t - t_open, 1), n) for t, n in bel_events if t >= t_open - 0.5]
        total = sum(n for _, n in after)
        say(f"bare BEL bytes after the dialog opened: {total}  (seconds after open, bytes per read: {after})")
    if args.show_screen:
        say("screen tail (ANSI stripped):", screen_tail[-260:])
    if t_open is None:
        say("measurement failed: the tool call was never observed, so nothing above is a result")
    elif args.control and total:
        say("a hooks-disabled control saw a BEL byte: the BEL is not attributable to the notification hook")
    return exit_status(t_open, args.control, total)


if __name__ == "__main__":
    sys.exit(main())      # `main` hands off in its own `finally`: a latched signal ends the process BY it there, before any output
