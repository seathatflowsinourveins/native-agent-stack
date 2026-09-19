"""Disposable Linux supervision fixture; no broker, model, or network work."""

import json
import os
from pathlib import Path
import signal
import sys


def main():
    directory = Path(sys.argv[1])
    if not directory.is_dir() or list(directory.iterdir()):
        raise SystemExit("Use a fresh, empty private fixture directory")
    os.umask(0o077)
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    role = "parent"
    if os.fork() == 0:
        role = "child"
        if os.fork() == 0:
            role = "grandchild"
    # Linux /proc starttime distinguishes the fixture from a reused numeric PID.
    stat = Path("/proc/self/stat").read_text().rsplit(")", 1)[1].split()
    with (directory / (role + ".json")).open("x") as stream:
        json.dump({"role": role, "pid": os.getpid(), "starttime": stat[19],
                   "cgroup": Path("/proc/self/cgroup").read_text(),
                   "ignores_sigterm": signal.getsignal(signal.SIGTERM) == signal.SIG_IGN}, stream)
        stream.write("\n")
    print("fixture-ready:" + role, flush=True)
    while True:
        signal.pause()


if __name__ == "__main__":
    main()
