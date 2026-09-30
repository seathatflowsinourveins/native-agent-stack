#!/usr/bin/env python3
"""Native probe: does a pending AskUserQuestion / ExitPlanMode dialog raise a Notification event, and does the user's hook
emit a bare BEL, and how long after the dialog opens? Drives a real short session in a pty and sends no keys while waiting.
Dialog-open time comes from a PreToolUse observer hook. Raw hook payloads (session ids, paths) go to a private temporary
directory that is deleted at the end; only counts and timings are printed.

usage:
  alert_probe.py ask|plan             measure with the user's own settings (their Notification hook produces the BEL). ask runs in
                                      the user's own default permission mode (this host: bypassPermissions) and prints the mode read
                                      from the on-screen footer; plan needs plan mode, so it is started in plan mode
  alert_probe.py ask --permission-mode default|acceptEdits|bypassPermissions
                                      the same, with an explicit permission mode (for comparing modes)
  alert_probe.py ask|plan --control   same session and user settings but every hook disabled (disableAllHooks): the dialog still
                                      opens, detected from its on-screen text, and no BEL may appear (attributes the BEL to the hook).
                                      Notification events are not observable in this mode (the observer hook is off), so none is reported
  alert_probe.py --selftest           check the BEL counter against split, doubled, interrupted and string-embedded cases

The raw hook payloads (session ids, paths) live in a private temporary directory that is removed even when the probe is
interrupted or fails; only counts and timings are printed. The counter follows the output state machine of Windows Terminal
v1.24.11911.0, src/terminal/parser/stateMachine.cpp: CAN and SUB return to ground from anywhere; ESC interrupts every state
except an OSC string, where it starts a string terminator; C0 controls, BEL included, execute in the ground, escape, escape
intermediate and CSI states; in an OSC string BEL is the terminator; DCS, SOS, PM and APC strings ignore C0 and end at ESC.
"""
import argparse, codecs, contextlib, fcntl, json, os, pty, re, select, shutil, signal, struct, subprocess, sys, tempfile, termios, time
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


DRIVER = r"""
import importlib.util, os, signal, subprocess, sys, time
from pathlib import Path
path, kind, pidfile = sys.argv[1:4]
spec = importlib.util.spec_from_file_location("probe", path)
probe = importlib.util.module_from_spec(spec)
sys.modules["probe"] = probe
spec.loader.exec_module(probe)
real_popen = subprocess.Popen


class ClientThenSignal(real_popen):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        deadline = time.time() + 10
        while not Path(pidfile).exists() and time.time() < deadline:   # the stand-in client has really started
            time.sleep(0.05)
        os.kill(os.getpid(), signal.SIGTERM)                          # the client exists and the probe has not recorded it yet


subprocess.Popen = ClientThenSignal
sys.argv = [path, kind] + (["--no-user-settings"] if kind == "push" else [])
sys.exit(probe.main())
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
    """The stand-in `claude`: publishes its PID, then becomes `sleep <unique>` (exec keeps the PID). `trust` first enables focus reporting (the push probe waits for it) and prints the text that makes the probe abort by itself after about 6 s; `true` exits at once."""
    if kind == "true":
        return "#!/bin/sh\nexit 0\n"
    text = "printf '\\033[?1004hDo you trust the files in this folder?\\n'\n" if kind == "trust" else ""   # focus reporting on (the push probe waits for it), then the trust text
    return f"#!/bin/sh\necho $$ > {pidfile}\n{text}exec sleep {unique}\n"


def signal_case(kind, signals=1, stand_in="sleep", signum=signal.SIGTERM, delay=1.0):
    """End to end: a stand-in `claude` first on PATH that publishes its PID, the real probe as a child with its own TMPDIR, `signals` signals of one kind 100 ms apart `delay` seconds after the stand-in is
    running: the probe must be running when the first lands and exit with that signal's status, the private directory must be gone and the recorded stand-in (exactly `sleep <unique>`) must be gone.
    stand_in="true" starts a client that exits at once: the case must then FAIL (a client that never ran proves nothing); stand_in="trust" makes the probe leave by itself after about 6 s, so a `delay` of
    about 6.5 s lands the signal in the first second of the probe's normal-exit cleanup, the part in which an interruption leaves the client behind. Returns (ok, detail); ok is None when the probe's working directory does not exist on this machine."""
    if not (Path.home() / "code/native-agent-stack").is_dir():
        return None, "skipped (the probe's working directory does not exist on this machine)"
    with tempfile.TemporaryDirectory(prefix="sigcase-") as raw:
        root = Path(raw)
        bindir, tmp, pidfile = root / "bin", root / "tmp", root / "stand-in.pid"
        bindir.mkdir()
        tmp.mkdir()
        unique = f"3137{os.getpid() % 100000}"
        (bindir / "claude").write_text(stand_in_script(stand_in, pidfile, unique))
        (bindir / "claude").chmod(0o755)
        env = {**os.environ, "PATH": f"{bindir}:{os.environ['PATH']}", "TMPDIR": str(tmp)}
        proc = subprocess.Popen([sys.executable, "-B", str(Path(__file__).resolve()), kind, *(["--no-user-settings"] if kind == "push" else [])], env=env,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        client = None

        def stand_in_alive():
            if client is None:
                return False
            try:
                state = (Path("/proc") / str(client) / "stat").read_text().rsplit(")", 1)[1].split()[0]
                argv = (Path("/proc") / str(client) / "cmdline").read_bytes().split(b"\0")
            except (OSError, IndexError):
                return False
            return state != "Z" and argv[:2] == [b"sleep", unique.encode()]   # our stand-in, not a process that reused the PID

        deadline = time.time() + (30 if stand_in != "true" else 5)
        while time.time() < deadline:
            if pidfile.exists() and pidfile.read_text().strip().isdigit():
                client = int(pidfile.read_text().strip())
                if stand_in_alive():
                    break
            time.sleep(0.2)
        client_ran = stand_in_alive()
        mask = blocked_mask(client) if client_ran else None
        clean_mask = mask == "0" * 16   # the client must not inherit a blocked signal from the probe
        time.sleep(delay)
        probe_running = proc.poll() is None
        for number in range(signals):
            if number:
                time.sleep(0.1)
            if proc.poll() is None:
                proc.send_signal(signum)
        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        time.sleep(0.5)
        left_dirs = list(tmp.glob("alert-probe-*"))
        alive = stand_in_alive()
        exit_ok = proc.returncode == 128 + signum
        if alive:
            os.kill(client, signal.SIGKILL)   # a failing case must not leave its stand-in behind (alive means the recorded PID is still exactly our `sleep`)
        detail = (f"stand-in client ran {client_ran} with signal mask {mask}, probe running when signaled {probe_running}, probe exit {proc.returncode} (expected {128 + signum}), "
                  f"private directory left {bool(left_dirs)}, stand-in client still alive {alive}")
        return client_ran and clean_mask and probe_running and exit_ok and not left_dirs and not alive, detail


def client_boundary_case(kind):
    """A signal that arrives while the client is being created (the child exists, the probe has not recorded it yet) must still stop the client and remove the private directory. The probe runs as a child
    that imports this file, wraps subprocess.Popen so that SIGTERM is sent to it right after the stand-in client is running, and calls main()."""
    if not (Path.home() / "code/native-agent-stack").is_dir():
        return None, "skipped (the probe's working directory does not exist on this machine)"
    with tempfile.TemporaryDirectory(prefix="boundary-") as raw:
        root = Path(raw)
        bindir, tmp, pidfile = root / "bin", root / "tmp", root / "stand-in.pid"
        bindir.mkdir()
        tmp.mkdir()
        unique = f"3137{os.getpid() % 100000}"
        (bindir / "claude").write_text(stand_in_script("sleep", pidfile, unique))
        (bindir / "claude").chmod(0o755)
        env = {**os.environ, "PATH": f"{bindir}:{os.environ['PATH']}", "TMPDIR": str(tmp)}
        driver = subprocess.Popen([sys.executable, "-B", "-c", DRIVER, str(Path(__file__).resolve()), kind, str(pidfile)], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        mask, deadline = None, time.time() + 30
        while mask is None and driver.poll() is None and time.time() < deadline:   # read the client's mask while it lives: the probe's cleanup keeps it for at least a second
            if pidfile.exists() and pidfile.read_text().strip().isdigit():
                mask = blocked_mask(int(pidfile.read_text().strip()))
            time.sleep(0.05)
        try:
            driver.wait(timeout=120)
        except subprocess.TimeoutExpired:
            driver.kill()
            driver.wait()
        run = driver
        time.sleep(0.5)
        client = int(pidfile.read_text().strip()) if pidfile.exists() and pidfile.read_text().strip().isdigit() else None
        alive = False
        if client is not None:
            try:
                alive = (Path("/proc") / str(client) / "stat").read_text().rsplit(")", 1)[1].split()[0] != "Z" and (Path("/proc") / str(client) / "cmdline").read_bytes().split(b"\0")[:2] == [b"sleep", unique.encode()]
            except (OSError, IndexError):
                alive = False
        left_dirs = list(tmp.glob("alert-probe-*"))
        if alive:
            os.kill(client, signal.SIGKILL)   # a failing case must not leave its stand-in behind
        ok = client is not None and mask == "0" * 16 and run.returncode == 128 + signal.SIGTERM and not left_dirs and not alive
        return ok, (f"stand-in client ran {client is not None} with signal mask {mask}, probe exit {run.returncode} (expected {128 + signal.SIGTERM}), private directory left {bool(left_dirs)}, "
                    f"stand-in client still alive {alive}")


def cleanup_phase_case():
    """In-process: a SIGTERM that arrives at the very start of the final cleanup (the work returned normally) must wait until the private directory is gone, and the previous handler then receives it."""
    seen, delivered = [], []
    real_rmtree = shutil.rmtree

    def terminating(number, _frame):
        delivered.append(number)
        raise SystemExit(128 + number)   # what the default action does, as an exception this case can catch

    def hostile_rmtree(path, *args, **kwargs):
        os.kill(os.getpid(), signal.SIGTERM)   # a signal at the very start of the cleanup
        return real_rmtree(path, *args, **kwargs)

    outer = signal.signal(signal.SIGTERM, terminating)
    shutil.rmtree = hostile_rmtree
    try:
        try:
            with_private_dir(lambda private: seen.append(private))
        except SystemExit:
            pass
    finally:
        shutil.rmtree = real_rmtree
        signal.signal(signal.SIGTERM, outer)
    left = bool(seen) and seen[0].exists()
    return len(seen) == 1 and not left and delivered == [signal.SIGTERM], f"private directory left {left}, the signal reached the previous handler afterwards {delivered == [signal.SIGTERM]}"


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
    for label, error in (("private directory removed after an interruption", KeyboardInterrupt), ("private directory removed after a failure", RuntimeError),
                         ("private directory removed after SIGTERM", SystemExit), ("private directory removed after SIGHUP", SystemExit)):
        seen = []

        def boom(private, error=error, label=label):
            seen.append(private)
            (private / "events.log").write_text("stand-in for a raw hook payload")
            if label.endswith("SIGTERM"):
                os.kill(os.getpid(), signal.SIGTERM)
            elif label.endswith("SIGHUP"):
                os.kill(os.getpid(), signal.SIGHUP)
            raise error()

        try:
            with_private_dir(boom)
        except error:
            pass
        ok = len(seen) == 1 and not seen[0].exists()
        bad += 0 if ok else 1
        print(("PASS " if ok else "FAIL ") + label)
    for label, given, expected in (("exit status: an opened dialog and no BEL passes", (1.0, False, 0), 0), ("exit status: a hooks-disabled control with a dialog and no BEL passes", (1.0, True, 0), 0),
                                   ("exit status: a hooks-disabled control that saw a BEL fails", (1.0, True, 1), 1), ("exit status: a control whose dialog never opened fails", (None, True, 0), 2),
                                   ("exit status: a run whose dialog never opened fails", (None, False, 0), 2)):
        got = exit_status(*given)
        bad += 0 if got == expected else 1
        print(("PASS " if got == expected else "FAIL ") + label + f": expected {expected}, got {got}")
    for label, function, expected in (
            ("one SIGTERM", lambda: signal_case("ask"), True),
            ("two SIGTERMs 100 ms apart", lambda: signal_case("ask", signals=2), True),
            ("two SIGINTs 100 ms apart", lambda: signal_case("ask", signals=2, signum=signal.SIGINT), True),
            ("one SIGTERM while the probe's own normal-exit cleanup runs", lambda: signal_case("ask", stand_in="trust", delay=6.5), True),
            ("a signal while the client is being created", lambda: client_boundary_case("ask"), True),
            ("a signal at the start of the final cleanup waits until the directory is gone", cleanup_phase_case, True),
            ("negative control: a client that never starts is rejected", lambda: signal_case("ask", stand_in="true"), False)):
        ok, detail = function()
        if ok is None:
            print(f"SKIP end to end, {label}: {detail}")
            continue
        good = ok == expected
        bad += 0 if good else 1
        print(("PASS " if good else "FAIL ") + f"end to end, {label}: {detail}")
    return 1 if bad else 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("kind", nargs="?", choices=["ask", "plan"])
    parser.add_argument("--control", action="store_true")
    parser.add_argument("--show-screen", action="store_true", help="also print the last 260 characters of the terminal screen (contents of the session: never put them in a receipt)")
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
        return with_private_dir(work)
    finally:
        print("raw payload directory removed:", bool(used) and not used[0].exists())


def exit_status(t_open, control, bel_total):
    """0 when the run reached the observation point (the dialog opened) and, for the hooks-disabled control, no BEL byte appeared; 2 when it never reached it; 1 when the control saw a BEL."""
    if t_open is None:
        return 2
    return 1 if control and bel_total else 0


HANDLED = (signal.SIGTERM, signal.SIGHUP, signal.SIGINT)
SPAWN = {"active": False, "signal": None}   # while the client is being created a signal only waits here, so the client is recorded before the exit it starts (a signal MASK would be inherited by the client)


def leave(signum, _frame=None):
    """Turn a signal into an exit. The first signal wins (later ones are ignored); one that arrives while the client is being created waits until the client is recorded."""
    if SPAWN["active"]:
        SPAWN["signal"] = signum
        return
    for number in HANDLED:
        signal.signal(number, signal.SIG_IGN)   # the first signal wins: the exit it starts must not be cut short by a second one
    raise SystemExit(128 + signum)


@contextlib.contextmanager
def deferred_signals():
    """The signals the probe turns into an exit wait until the block ends and are delivered then: a cleanup must not be cut short. Only for work that spawns nothing: a child inherits the mask."""
    saved = signal.pthread_sigmask(signal.SIG_BLOCK, HANDLED)
    try:
        yield
    finally:
        signal.pthread_sigmask(signal.SIG_SETMASK, saved)


def with_private_dir(work):
    """Run work(private_dir) and remove the private directory afterwards on success, failure and interruption alike. SIGINT, SIGTERM and SIGHUP become SystemExit for the duration, so the finally
    blocks run for them too, the one that stops the child process group included; the first signal wins (later ones are ignored), and the cleanup runs with the signals deferred until it is done, so
    none of them can cut it short."""
    private = Path(tempfile.mkdtemp(prefix="alert-probe-"))

    previous = {number: signal.signal(number, leave) for number in HANDLED}
    try:
        return work(private)
    finally:
        with deferred_signals():
            shutil.rmtree(private, ignore_errors=True)
            for number, handler in previous.items():   # the previous handlers come back only after the cleanup is done
                signal.signal(number, handler)


def measure(args, private):
    log = private / "events.log"
    log.write_text("")
    if args.kind == "ask":
        prompt = "Call the AskUserQuestion tool exactly once with a single question about whether the probe is ready, offering the options Yes and No. Do nothing else and do not answer it yourself."
        mode = args.permission_mode  # None: the user's own default mode
    else:
        prompt = "Write the one-line plan 'do nothing' to your plan file and immediately call ExitPlanMode. Do nothing else."
        mode = "plan"

    def observer(tag):
        return f"sh -c 'printf \"%s {tag} \" \"$(date +%s.%N)\" >> {log}; cat >> {log}; echo >> {log}'"

    overlay = {"hooks": {
        "PreToolUse": [{"matcher": "AskUserQuestion|ExitPlanMode", "hooks": [{"type": "command", "command": observer("PRE")}]}],
        "Notification": [{"matcher": "", "hooks": [{"type": "command", "command": observer("NOTIF")}]}],
    }}
    sources = "user"
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
    try:
        SPAWN["active"], SPAWN["signal"] = True, None   # a signal while the client is created waits until the client is recorded (a mask would be inherited by the client)
        try:
            proc = subprocess.Popen(["claude", "--model", "sonnet", *mode_flags, "--setting-sources", sources,
                                     "--settings", json.dumps(overlay), "-n", f"alert-probe-{args.kind}"],
                                    stdin=slave, stdout=slave, stderr=slave, env=env, cwd=cwd, start_new_session=True, close_fds=True)
        finally:
            SPAWN["active"] = False
        if SPAWN["signal"] is not None:
            leave(SPAWN["signal"])   # the client is recorded and the guard is active: leave now
        os.close(slave)

        ansi = re.compile(r"\x1b\[[0-9;?<>=]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b[()][A-Z0-9]|\x1b[=>MNOP78]")
        counter = BelCounter()
        bel_events = []  # (epoch seconds, bare BEL bytes in that read)
        buf = b""
        events = []
        state = "startup"
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

        while time.time() - t0 < 200:
            pump()
            now = time.time()
            if state == "startup" and now - t0 > 6:
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
                for line in log_lines():
                    stamp, _, rest = line.partition(" ")
                    if rest.startswith("PRE "):
                        t_open = float(stamp)
                        state = "observing"
                        events.append("PreToolUse observed (dialog opening); no keys sent for 16 s")
                        break
            elif state == "observing" and now - t_open > 16:
                break
        screen_tail = ansi.sub("", buf.decode("utf-8", "replace"))[-300:].replace("\n", " ")
    finally:
        with deferred_signals():   # the client's cleanup must not be cut short; a signal that arrives meanwhile is delivered when it is done
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
            os.close(master)

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
    print("events:", events)
    if args.control:
        print("Notification events: not observable (every hook is disabled, so the observer hook is off); the BEL byte count below is the measurement")
    else:
        print(f"Notification events: {len(notifications)}")
    for stamp, ntype, message in notifications[:4]:
        print(f"  +{round(stamp - t_open, 1) if t_open else None}s after open | type={ntype} | message length={len(message)}")
    if t_open:
        after = [(round(t - t_open, 1), n) for t, n in bel_events if t >= t_open - 0.5]
        total = sum(n for _, n in after)
        print(f"bare BEL bytes after the dialog opened: {total}  (seconds after open, bytes per read: {after})")
    if args.show_screen:
        print("screen tail (ANSI stripped):", screen_tail[-260:])
    status = exit_status(t_open, args.control, sum(n for t, n in bel_events if t_open and t >= t_open - 0.5))
    if status:
        print("measurement failed:", {2: "the dialog never opened, so nothing above is a result", 1: "a hooks-disabled control saw a BEL byte, so the BEL is not attributable to the hook"}[status])
    return status


if __name__ == "__main__":
    sys.exit(main())
