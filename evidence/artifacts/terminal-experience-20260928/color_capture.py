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


MAX_PARAMETER = 65535   # the pinned parser saturates a numeric parameter here (stateMachine.hpp MAX_PARAMETER_VALUE, applied by _AccumulateTo)


def field(text):
    """One parameter or sub-parameter field: None when empty (no value), else its number saturated at MAX_PARAMETER without converting an arbitrarily long digit string."""
    if text == "":
        return None
    digits = text.lstrip("0")
    return MAX_PARAMETER if len(digits) > 5 else min(int(digits or "0"), MAX_PARAMETER)


def sgr_counts(text, size=0):
    """Counts of SGR sequences (ESC [ params m: the final byte must be m, so a cursor-position sequence with the same numbers is not counted) that set a colour of each class: the number of sequences that
    contain at least one such colour. The parameters are read as the pinned Windows Terminal parser reads them (v1.24.11911.0, src/terminal/adapter/adaptDispatchGraphics.cpp): ';' separates parameters and ':' the
    sub-parameters of one; a number saturates at 65535; a missing value is 0. Semicolon form: `38`/`48` followed by `2` consumes five parameters (38;2;r;g;b) and applies the colour only when r, g and b are each
    at most 255 (a missing one is 0), followed by `5` it consumes three (38;5;n) and applies it when n is at most 255, followed by anything else it consumes two. Colon form (`38:2::r:g:b`, `38:5:n`): `2` applies
    truecolor only when the colour-space field is EMPTY and r, g and b are at most 255, `5` applies the index when it is at most 255; trailing sub-parameters are ignored. A 38/48 group that the parser reads but does not
    apply (a component above a byte, a colour-space id) is counted in `not_applied_groups` (once per sequence) and is never a colour or a basic code; 30-37, 90-97, 40-47 and 100-107 are the basic colours."""
    counts = {"bytes": size, "fg_truecolor_38;2": 0, "bg_truecolor_48;2": 0, "fg_256_38;5": 0, "bg_256_48;5": 0, "basic_16": 0, "not_applied_groups": 0}
    for match in SGR.finditer(text):
        parameters = [[field(part) for part in group.split(":")] for group in match.group(1).split(";")]
        seen, rejected, i = set(), False, 0

        def apply(selector, kind, valid):
            nonlocal rejected
            if valid:
                seen.add(("fg" if selector == 38 else "bg") + ("_truecolor_" if kind == 2 else "_256_") + f"{selector};{kind}")
            else:
                rejected = True

        while i < len(parameters):
            head = parameters[i]
            value = head[0]
            if len(head) > 1:                              # sub-parameters: handed to the sub-parameter helper
                subs = head[1:]
                if value in (38, 48) and subs[0] == 2:
                    component = [(subs[n] if n < len(subs) else None) or 0 for n in (2, 3, 4)]
                    has_colour_space_id = len(subs) > 1 and subs[1] is not None
                    apply(value, 2, not has_colour_space_id and all(part <= 255 for part in component))
                elif value in (38, 48) and subs[0] == 5:
                    apply(value, 5, ((subs[1] if len(subs) > 1 else None) or 0) <= 255)
                i += 1
            elif value in (38, 48):                        # semicolon form
                kind = parameters[i + 1][0] if i + 1 < len(parameters) else None
                if kind == 2:
                    component = [((parameters[i + n][0] if i + n < len(parameters) else None) or 0) for n in (2, 3, 4)]
                    apply(value, 2, all(part <= 255 for part in component))
                    i += 5
                elif kind == 5:
                    apply(value, 5, ((parameters[i + 2][0] if i + 2 < len(parameters) else None) or 0) <= 255)
                    i += 3
                else:
                    i += 2
            elif value is not None and (30 <= value <= 37 or 90 <= value <= 97 or 40 <= value <= 47 or 100 <= value <= 107):
                seen.add("basic_16")
                i += 1
            else:
                i += 1
        for name in seen:
            counts[name] += 1
        if rejected:
            counts["not_applied_groups"] += 1
    return counts


def selftest():
    cases = [("cursor position with truecolor numbers is not SGR", "\x1b[38;2;1;2;3H\x1b[48;5;12H", {}),
             ("the same numbers in SGR count", "\x1b[38;2;1;2;3m\x1b[48;5;12m", {"fg_truecolor_38;2": 1, "bg_256_48;5": 1}),
             ("two colours in one sequence", "\x1b[1;38;2;1;2;3;48;2;4;5;6m", {"fg_truecolor_38;2": 1, "bg_truecolor_48;2": 1}),
             ("a number that only looks like a prefix (138;2;1;2;3) is not a colour", "\x1b[138;2;1;2;3m", {}),
             ("basic colours", "\x1b[31m\x1b[1;44m\x1b[97m\x1b[0m", {"basic_16": 3}),
             ("a truecolor and a basic colour in one sequence", "\x1b[38;2;1;2;3;31m", {"fg_truecolor_38;2": 1, "basic_16": 1}),
             ("colon truecolor with an empty colour-space field is truecolor, and its components (31, 32, 33) are not basic colours", "\x1b[38:2::31:32:33m", {"fg_truecolor_38;2": 1}),
             ("colon truecolor accepts trailing sub-parameters (the parser ignores them)", "\x1b[38:2::31:32:33:0m", {"fg_truecolor_38;2": 1}),
             ("colon truecolor with a missing component reads it as 0 and applies", "\x1b[38:2::31:32m", {"fg_truecolor_38;2": 1}),
             ("colon truecolor with a colour-space id is invalid for the pinned parser: not applied", "\x1b[38:2:1:2:3m", {"not_applied_groups": 1}),
             ("colon 256-colour", "\x1b[48:5:12m", {"bg_256_48;5": 1}),
             ("colon 256-colour above a byte is not applied", "\x1b[48:5:256m", {"not_applied_groups": 1}),
             ("a colon component above a byte is not applied", "\x1b[38:2::300:1:1m", {"not_applied_groups": 1}),
             ("an underline style group is not a colour", "\x1b[4:3m", {}),
             ("a colon colour and a semicolon colour in one sequence", "\x1b[38:2::1:2:3;48;5;9m", {"fg_truecolor_38;2": 1, "bg_256_48;5": 1}),
             ("a truncated truecolor group applies with the missing components read as 0, and its numbers never count as basic colours", "\x1b[38;2;31;32m", {"fg_truecolor_38;2": 1}),
             ("a truncated 256-colour group reads the missing index as 0 and applies", "\x1b[48;5m", {"bg_256_48;5": 1}),
             ("a semicolon component above a byte is not applied", "\x1b[38;2;300;1;1m", {"not_applied_groups": 1}),
             ("a semicolon 256-colour index above a byte is not applied", "\x1b[38;5;256m", {"not_applied_groups": 1}),
             ("zero-padded components are the same numbers", "\x1b[38;2;0031;0032;0033m\x1b[48;5;0000000000000000000000000000012m", {"fg_truecolor_38;2": 1, "bg_256_48;5": 1}),
             ("an absurdly long digit string saturates instead of raising, and is above a byte", "\x1b[38;2;" + "9" * 5000 + ";1;1m", {"not_applied_groups": 1}),
             ("a 38 whose type is neither 2 nor 5 consumes the type and applies nothing", "\x1b[38;9;31m", {"basic_16": 1}),
             ("zero-padded selectors are the same numbers", "\x1b[038;2;31;32;33m\x1b[38;02;31;32;33m\x1b[48;05;41m", {"fg_truecolor_38;2": 2, "bg_256_48;5": 1}),
             ("a bare absurdly long parameter saturates instead of raising", "\x1b[" + "9" * 5000 + "m\x1b[1;" + "9" * 5000 + ";31m", {"basic_16": 1}),
             ("a component at the parser's saturation value is above a byte and not applied", "\x1b[38;2;65535;0;0m", {"not_applied_groups": 1}),
             ("a component of exactly 255 is applied", "\x1b[38;2;255;255;255m", {"fg_truecolor_38;2": 1}),
             ("empty parameters are no colour", "\x1b[;;m\x1b[38;;;;m", {}),
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
