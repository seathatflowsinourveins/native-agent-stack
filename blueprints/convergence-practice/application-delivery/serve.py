#!/usr/bin/env python3
"""Run only the two owned loopback application processes in the foreground."""
import os
from pathlib import Path
import signal
import socket
import subprocess
import time

HERE = Path(__file__).resolve().parent


def main():
    for port in (18080, 18081):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", port))
    logs = HERE / ".runtime"
    logs.mkdir(exist_ok=True)
    children, handles = [], []

    def interrupted(_number, _frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupted)
    try:
        for name, command in [
            ("api", [str(HERE / ".venv/bin/python"), "-m", "uvicorn", "backend.app:app", "--host", "127.0.0.1", "--port", "18081"]),
            ("web", ["pnpm", "start"]),
        ]:
            handle = (logs / f"{name}.log").open("a")
            handles.append(handle)
            children.append(subprocess.Popen(command, cwd=HERE, stdout=handle, stderr=subprocess.STDOUT,
                                             env={**os.environ, "NEXT_TELEMETRY_DISABLED": "1"}, start_new_session=True))
        print("Run ledger: http://127.0.0.1:18080 (Ctrl-C stops both owned application processes)", flush=True)
        while all(child.poll() is None for child in children):
            time.sleep(0.2)
        return 1
    except KeyboardInterrupt:
        return 0
    finally:
        for child in children:
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGTERM)
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid, signal.SIGKILL)
                    child.wait(timeout=5)
        for handle in handles:
            handle.close()


if __name__ == "__main__":
    raise SystemExit(main())
