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
import argparse, codecs, concurrent.futures, fcntl, json, os, pty, re, select, shutil, signal, struct, subprocess, sys, tempfile, termios, time
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
WATCH = {"main", "with_private_dir", "measure"}   # the resource lifecycle: the private directory, the pty and the client
seen, fired, alive_at_fire = [], [], []


def dump():
    open(record, "w").write(json.dumps({"lines": seen, "fired": fired, "alive_at_fire": alive_at_fire}))


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
sys.settrace(tracer)
try:
    status = probe.main()
finally:
    sys.settrace(None)
    dump()
sys.exit(status)
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
    the probe must be running when the first lands and exit with the FIRST signal's status (128 + its number), the private directory must be gone, the recorded stand-in (exactly `sleep <unique>`) must be gone and
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
        expected = 128 + signums[0]
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
            run = subprocess.run([sys.executable, "-B", path, *arguments], env=env, capture_output=True, timeout=180)
            client = int(pidfile.read_text().strip()) if pidfile.exists() and pidfile.read_text().strip().isdigit() else None
            if client is not None and stand_in_alive(client, unique):
                os.kill(client, signal.SIGKILL)
            return label, run.returncode, expected, len(list(tmp.glob("alert-probe-*")))

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(one, range(len(runs))))
    problems = [f"{label}: exit {code}, expected {expected}" for label, code, expected, _left in results if code != expected] + [f"{label}: a payload directory was left" for label, _c, _e, left in results if left]
    return not problems, "; ".join(f"{label}: exit {code} (expected {expected})" for label, code, expected, _left in results) + ("" if not problems else " | " + "; ".join(problems))


def sweep_trial(path, kind, target, stand_in, serial):
    """One run of the probe in a child process with a stand-in client; SIGTERM is delivered to it at the first execution of line `target` of its resource lifecycle (`main`, `with_private_dir`, `measure`; -1
    delivers none: a dry run that records the lines). Returns what the run showed: its exit status, what the driver recorded, the payload directories and the stand-in left behind."""
    with tempfile.TemporaryDirectory(prefix="sweep-") as raw:
        root = Path(raw)
        env, tmp, pidfile, unique = arena(root, stand_in, serial)
        record = root / "record.json"
        run = subprocess.run([sys.executable, "-B", "-c", SWEEP_DRIVER, path, kind, str(target), str(record), str(pidfile), unique], env=env, capture_output=True, timeout=180)
        info = json.loads(record.read_text()) if record.exists() else {}
        client = int(pidfile.read_text().strip()) if pidfile.exists() and pidfile.read_text().strip().isdigit() else None
        alive = client is not None and stand_in_alive(client, unique)
        if alive:
            os.kill(client, signal.SIGKILL)   # never leave the stand-in behind, whatever the verdict
        return {"target": target, "status": run.returncode, "info": info, "left": len(list(tmp.glob("alert-probe-*"))), "alive": alive}


def sweep_case(kind, stand_in="trust", workers=6):
    """A SIGTERM at EVERY line of the probe's resource lifecycle: a dry run records the lines of `main`, `with_private_dir` and `measure` that a run reaches with a stand-in client that makes the probe take its normal
    exit path (about 7 s), then one run per line delivers the signal there. Every run must exit with 128 + SIGTERM (the latch, after the cleanup) or -SIGTERM (a signal before the latch exists or after the previous handlers
    returned, when nothing is left to protect), leave no payload directory and no stand-in client. The client must have been RUNNING when the signal fired at ten lines or more, so a stand-in that is not there (a
    control that proves nothing) fails the case. Returns (ok, detail)."""
    if not (Path.home() / "code/native-agent-stack").is_dir():
        return None, "skipped (the probe's working directory does not exist on this machine)"
    path = str(Path(__file__).resolve())
    lines = sweep_trial(path, kind, -1, stand_in, 0)["info"].get("lines") or []
    if len(lines) < 25:
        return False, f"the dry run recorded {len(lines)} lines of the resource lifecycle (at least 25 expected)"
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        trials = list(pool.map(lambda pair: sweep_trial(path, kind, pair[1], stand_in, pair[0] + 1), enumerate(lines)))
    problems = []
    for trial in trials:
        line = trial["target"]
        if trial["info"].get("fired") != [line]:
            problems.append(f"line {line}: the signal was not delivered")
        elif trial["status"] not in (128 + signal.SIGTERM, -signal.SIGTERM):
            problems.append(f"line {line}: exit status {trial['status']}")
        if trial["left"]:
            problems.append(f"line {line}: a payload directory was left")
        if trial["alive"]:
            problems.append(f"line {line}: the stand-in client was left running")
    live = sum(1 for trial in trials if trial["info"].get("alive_at_fire") == [True])
    if live < 10:
        problems.append(f"the client was running when the signal fired at only {live} lines (at least 10 expected): the sweep did not exercise the client's lifetime")
    return not problems, f"{len(lines)} lines swept, the client was running at {live} of them, {len(problems)} problems" + ("" if not problems else " | " + "; ".join(problems[:4]))


def selftest():
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
            ("SIGTERM then SIGINT: the first signal decides the exit status", lambda: signal_case("push", signums=(signal.SIGTERM, signal.SIGINT)), True),
            ("a SIGTERM at every line of the resource lifecycle", lambda: sweep_case("push"), True),
            ("the measurement's exit status: 2 when the dialog never opened, 1 for a control that saw a BEL, 0 for a quiet one", lambda: status_case("ask"), True),
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
        status = with_private_dir(work)
        return signal_status() or status   # a latched signal is the exit status, produced after the cleanup
    finally:
        print("raw payload directory removed:", bool(used) and not used[0].exists())


HANDLED = (signal.SIGTERM, signal.SIGHUP, signal.SIGINT)
STOP = {"signal": None}   # the FIRST handled signal, latched by `latch`


def latch(signum, _frame=None):
    """The handler of SIGINT, SIGTERM and SIGHUP: remember the first signal and return, nothing else. A handler that raised (SystemExit, as an earlier version did) can fire between any two statements, between
    acquiring a resource and recording it, or at the entry of a cleanup, and cut either short; this one cannot, so no signal leaves the client, the pty or the payload directory behind. The code acts on the latch at
    explicit safe points (before the client is started, in the observation loop) and turns it into the exit status 128 + the signal after the cleanup has run."""
    if STOP["signal"] is None:
        STOP["signal"] = signum


def stopped():
    return STOP["signal"] is not None


def signal_status():
    """The exit status a latched signal asks for (128 + its number), or None."""
    return None if STOP["signal"] is None else 128 + STOP["signal"]


def with_private_dir(work):
    """Install the latch handler first, create the private directory, run work(private_dir), and remove the directory and restore the previous handlers whatever happened (a normal return, an exception, a latched
    signal). Returns what work returns; the caller turns a latched signal into the exit status after this cleanup."""
    STOP["signal"] = None
    previous = {number: signal.signal(number, latch) for number in HANDLED}
    private = None
    try:
        private = Path(tempfile.mkdtemp(prefix="alert-probe-"))
        return work(private)
    finally:
        if private is not None:
            shutil.rmtree(private, ignore_errors=True)
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
        if not stopped():   # a signal latched before this point: no client is started
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
                for ch in prompt:
                    os.write(master, ch.encode())
                    time.sleep(0.004)
                time.sleep(0.4)
                os.write(master, b"\r")
                t_enter = time.time()
                state = "waiting_tool"
                events.append("prompt sent")
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

    print(f"kind={args.kind} control={args.control} state={state} dialog_opened={t_open is not None} probe_process_group={group}")
    if args.kind == "push":
        print(f"focus reporting enabled by the client: {focus_reporting_enabled} | focus-out report sent: {sent_focus_out}"
              + (f" ({round(t_focus_out - t_enter, 1)} s after Enter)" if sent_focus_out and t_enter else "")
              + f" | prompt sleep: {args.sleep} s | seconds from Enter to the tool call: {round(t_open - t_enter, 1) if t_open and t_enter else None}")
    print("events:", events)
    if args.control:
        print("Notification events: not observable (every hook is disabled, so the observer hook is off); the BEL byte count below is the measurement")
    else:
        print(f"Notification events: {len(notifications)}")
    for stamp, ntype, message in notifications[:4]:
        print(f"  +{round(stamp - t_open, 1) if t_open else None}s after open | type={ntype} | message length={len(message)}")
    total = 0
    if t_open:
        after = [(round(t - t_open, 1), n) for t, n in bel_events if t >= t_open - 0.5]
        total = sum(n for _, n in after)
        print(f"bare BEL bytes after the dialog opened: {total}  (seconds after open, bytes per read: {after})")
    if args.show_screen:
        print("screen tail (ANSI stripped):", screen_tail[-260:])
    if t_open is None:
        print("measurement failed: the tool call was never observed, so nothing above is a result")
    elif args.control and total:
        print("a hooks-disabled control saw a BEL byte: the BEL is not attributable to the notification hook")
    return exit_status(t_open, args.control, total)


if __name__ == "__main__":
    sys.exit(main())
