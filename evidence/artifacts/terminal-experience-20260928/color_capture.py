#!/usr/bin/env python3
"""Measure the colour depth Claude Code emits: run `claude --bare` in a pty for a few seconds and
count SGR colour sequences. Isolated: empty CLAUDE_CONFIG_DIR, dummy API key, no hooks (--bare)."""
import fcntl, os, pty, re, select, shutil, signal, struct, subprocess, sys, tempfile, termios, time

def capture(colorterm, seconds=7.0):
    cfg = tempfile.mkdtemp(prefix="cc-color-probe-")
    env = {
        "PATH": os.environ["PATH"],
        "HOME": os.environ["HOME"],
        "LANG": "C.UTF-8",
        "TERM": "xterm-256color",
        "WT_SESSION": "color-probe",
        "CLAUDE_CONFIG_DIR": cfg,
        "ANTHROPIC_API_KEY": "dummy-value-not-a-credential",
        "DISABLE_AUTOUPDATER": "1",
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
        "DISABLE_TELEMETRY": "1",
    }
    if colorterm is not None:
        env["COLORTERM"] = colorterm
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 40, 120, 0, 0))
    proc = subprocess.Popen(["claude", "--bare"], stdin=slave, stdout=slave, stderr=slave,
                            env=env, cwd=cfg, start_new_session=True, close_fds=True)
    os.close(slave)
    buf = b""
    end = time.time() + seconds
    while time.time() < end:
        r, _, _ = select.select([master], [], [], 0.2)
        if r:
            try:
                chunk = os.read(master, 65536)
            except OSError:
                break
            if not chunk:
                break
            buf += chunk
            # answer the two queries that commonly stall startup
            if b"\x1b[c" in chunk or b"\x1b[0c" in chunk:
                os.write(master, b"\x1b[?62;c")
            if b"\x1b]11;?" in chunk:
                os.write(master, b"\x1b]11;rgb:0000/0000/0000\x1b\\")
    try:
        os.killpg(proc.pid, signal.SIGTERM)
        time.sleep(0.5)
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    proc.wait(timeout=5)
    os.close(master)
    shutil.rmtree(cfg, ignore_errors=True)  # the throwaway configuration directory
    return sgr_counts(buf.decode("utf-8", "replace"), len(buf))


SGR = re.compile(r"\x1b\[([0-9;:]*)m")


def sgr_counts(text, size=0):
    """Counts of SGR sequences (ESC [ params m: the final byte must be m, so a cursor-position sequence with the same numbers is not counted) that set a colour of each class: the number
    of sequences that contain at least one such colour, the unit of the first version of this counter. The parameters are read in order from their boundaries (38;2;r;g;b and 48;2;r;g;b truecolor,
    38;5;n and 48;5;n 256-colour, 30-37, 90-97, 40-47 and 100-107 basic); ':' separates sub-parameters of the same colour like ';'."""
    counts = {"bytes": size, "fg_truecolor_38;2": 0, "bg_truecolor_48;2": 0, "fg_256_38;5": 0, "bg_256_48;5": 0, "basic_16": 0}
    for match in SGR.finditer(text):
        params = [p for p in re.split(r"[;:]", match.group(1))]
        seen, i = set(), 0
        while i < len(params):
            p = params[i]
            if p in ("38", "48") and i + 1 < len(params) and params[i + 1] == "2" and i + 4 < len(params) and all(x.isdigit() for x in params[i + 2:i + 5]):
                seen.add(("fg" if p == "38" else "bg") + "_truecolor_" + p + ";2")
                i += 5
            elif p in ("38", "48") and i + 1 < len(params) and params[i + 1] == "5" and i + 2 < len(params) and params[i + 2].isdigit():
                seen.add(("fg" if p == "38" else "bg") + "_256_" + p + ";5")
                i += 3
            elif p.isdigit() and (30 <= int(p) <= 37 or 90 <= int(p) <= 97 or 40 <= int(p) <= 47 or 100 <= int(p) <= 107):
                seen.add("basic_16")
                i += 1
            else:
                i += 1
        for name in seen:
            counts[name] += 1
    return counts


def selftest():
    cases = [("cursor position with truecolor numbers is not SGR", "\x1b[38;2;1;2;3H\x1b[48;5;12H", {}),
             ("the same numbers in SGR count", "\x1b[38;2;1;2;3m\x1b[48;5;12m", {"fg_truecolor_38;2": 1, "bg_256_48;5": 1}),
             ("two colours in one sequence", "\x1b[1;38;2;1;2;3;48;2;4;5;6m", {"fg_truecolor_38;2": 1, "bg_truecolor_48;2": 1}),
             ("a number that only looks like a prefix (138;2;1;2;3) is not a colour", "\x1b[138;2;1;2;3m", {}),
             ("basic colours", "\x1b[31m\x1b[1;44m\x1b[97m\x1b[0m", {"basic_16": 3}),
             ("colon sub-parameters", "\x1b[38:2:1:2:3m", {"fg_truecolor_38;2": 1}),
             ("a truncated truecolor is not counted", "\x1b[38;2;1;2m", {}),
             ("private-mode sequences are not SGR", "\x1b[?25l\x1b[?2026h", {})]
    problems = []
    for label, text, expected in cases:
        got = {k: v for k, v in sgr_counts(text).items() if v and k != "bytes"}
        if got != expected:
            problems.append(f"{label}: got {got}, expected {expected}")
    print(f"selftest: {len(cases)} cases, {len(problems)} problems")
    for problem in problems:
        print("  -", problem)
    return 1 if problems else 0

if __name__ == "__main__":
    if "--selftest" in sys.argv[1:]:
        sys.exit(selftest())
    for label, value in (("COLORTERM unset", None), ("COLORTERM=truecolor", "truecolor")):
        print(label, capture(value))
