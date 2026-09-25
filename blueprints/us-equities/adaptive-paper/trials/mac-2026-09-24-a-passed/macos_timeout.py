#!/usr/bin/env python3
"""Minimal GNU `timeout DURATION COMMAND [ARG]...` stand-in for macOS (no coreutils).

On expiry it sends SIGTERM (GNU default, no -k), waits for the child and exits 124;
otherwise it exits with the child's status (128+N if the child died from signal N).
SIGINT/SIGTERM/SIGHUP received by this shim are forwarded to the child.
"""
import signal
import subprocess
import sys


def main():
    if len(sys.argv) < 3:
        sys.stderr.write("usage: timeout SECONDS COMMAND [ARG]...\n")
        return 125
    seconds = float(sys.argv[1])
    child = subprocess.Popen(sys.argv[2:])
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, lambda signum, _frame: child.send_signal(signum))
    try:
        rc = child.wait(timeout=seconds)
    except subprocess.TimeoutExpired:
        child.send_signal(signal.SIGTERM)
        child.wait()
        return 124
    return rc if rc >= 0 else 128 - rc


if __name__ == "__main__":
    sys.exit(main())
