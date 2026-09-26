#!/usr/bin/env python3
"""Discriminating control for the request deadline in binding_check.py.

The cross-family verification of this change found that binding_check.py's Server.request bounded each wait for
the next message, not the whole request, so a server that keeps sending other messages can hold a request past
its bound. For each script given, this loads its Server class, starts a stub MCP server that sends a
notification every 10 ms for 300 ms before it answers, and sends the stub one request bounded at 50 ms. It
prints, per script: its name and sha256, whether the request returned the answer or raised, after how many
milliseconds, how many messages the request took from the stub, and the stub's exit status and stderr size
once Server.close() has run; then its own command line, interpreter, sha256 and UTC start and end. The stub
is this interpreter running STUB below, with LANG as its only environment variable, in a temporary directory
that is removed afterwards. No path is printed.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import queue
import sys
import tempfile
import time

BOUND_SECONDS = 0.05
STUB = """\
import json, sys, time
request = json.loads(sys.stdin.readline())
end = time.monotonic() + 0.3
while time.monotonic() < end:
    print(json.dumps({"jsonrpc": "2.0", "method": "notifications/message", "params": {}}), flush=True)
    time.sleep(0.01)
print(json.dumps({"jsonrpc": "2.0", "id": request["id"], "result": {}}), flush=True)
sys.stdin.read()
"""


def utc() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class CountingQueue(queue.Queue):
    """Server.lines, counting the messages that request() takes from it."""

    def __init__(self):
        super().__init__()
        self.taken = 0

    def get(self, *args, **kwargs):
        item = super().get(*args, **kwargs)
        self.taken += 1
        return item


def check(script: Path, index: int) -> dict:
    spec = importlib.util.spec_from_file_location(f"binding_check_under_test_{index}", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = {"script": script.name, "sha256": hashlib.sha256(script.read_bytes()).hexdigest(),
              "bound_ms": int(BOUND_SECONDS * 1000)}
    with tempfile.TemporaryDirectory(prefix="deadline-control-") as scratch:
        server = module.Server([sys.executable, "-c", STUB], Path(scratch), {"LANG": "C.UTF-8"},
                               Path(scratch) / "stub.stderr")
        server.lines = CountingQueue()  # the stub sends nothing before the request, so no message is lost
        started = time.monotonic()
        try:
            reply = server.request("initialize", {}, seconds=BOUND_SECONDS)
            result["outcome"] = "returned the answer" if "result" in reply else "returned another message"
        except (RuntimeError, OSError, queue.Empty) as error:
            result["outcome"] = f"raised {type(error).__name__}"
        result["elapsed_ms"] = round((time.monotonic() - started) * 1000)
        result["messages_taken"] = server.lines.taken
        result["stub_exit"] = server.close()
        result["stub_stderr_bytes"] = (Path(scratch) / "stub.stderr").stat().st_size
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("scripts", type=Path, nargs="+", help="binding_check.py copies to load Server from")
    args = parser.parse_args()
    start = utc()
    results = [check(script, index) for index, script in enumerate(args.scripts)]
    print(json.dumps({"schema_version": 1, "control": "binding_check.py request deadline",
                      "command": " ".join(["python", Path(__file__).name, *(script.name for script in args.scripts)]),
                      "python": platform.python_version(),
                      "driver_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                      "started_at_utc": start, "ended_at_utc": utc(), "results": results}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
