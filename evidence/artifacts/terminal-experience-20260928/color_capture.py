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
    text = buf.decode("utf-8", "replace")
    counts = {
        "bytes": len(buf),
        "fg_truecolor_38;2": len(re.findall(r"\x1b\[[0-9;:]*?38;2;\d+;\d+;\d+", text)),
        "bg_truecolor_48;2": len(re.findall(r"\x1b\[[0-9;:]*?48;2;\d+;\d+;\d+", text)),
        "fg_256_38;5": len(re.findall(r"\x1b\[[0-9;:]*?38;5;\d+", text)),
        "bg_256_48;5": len(re.findall(r"\x1b\[[0-9;:]*?48;5;\d+", text)),
        "basic_16": len(re.findall(r"\x1b\[(?:[0-9;]*;)?(?:3[0-7]|9[0-7]|4[0-7]|10[0-7])m", text)),
    }
    return counts

if __name__ == "__main__":
    for label, value in (("COLORTERM unset", None), ("COLORTERM=truecolor", "truecolor")):
        print(label, capture(value))
