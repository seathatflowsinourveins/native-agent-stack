"""The fetch transport runs in its own process (review round 10, H1).

run.py never imports study/fetch/ into the process that plans, seals, parses or evaluates. Each planned request goes
to a child interpreter (this file run as a script, `python -I -B`), which imports fetch.transport and answers with
the raw pages only: a JSON line {"pages": [base64 bytes, ...], "complete": bool, "error": str | None}. Anything
else is an incomplete request. So a transport deviation (a change under study/fetch/) can change which bytes arrive,
or fail a request, but it cannot patch the plan, the parser, the seeds, the statistics or the labels, and the
evaluation step of a count or read (core/holdout.py) makes no request at all. If the child ends, the run stops with
an error, as an exception inside the transport did before.
"""
from __future__ import annotations

import base64
import json
import subprocess
import sys
from pathlib import Path

STUDY = Path(__file__).resolve().parents[1]
WORKER = (sys.executable, "-I", "-B", str(Path(__file__).resolve()))
KEYS = {"pages", "complete", "error"}


class TransportProcessEnded(RuntimeError):
    pass


def incomplete(error: str) -> dict:
    return {"pages": [], "complete": False, "error": error}


def decode(line: str) -> dict:
    """The child's reply: raw pages, a completeness flag and an error string, nothing else."""
    try:
        msg = json.loads(line)
    except ValueError:
        return incomplete("transport process: unreadable reply")
    if not isinstance(msg, dict) or set(msg) != KEYS or not isinstance(msg["complete"], bool) or \
            not (msg["error"] is None or isinstance(msg["error"], str)) or not isinstance(msg["pages"], list) or \
            not all(isinstance(p, str) for p in msg["pages"]):
        return incomplete("transport process: malformed reply")
    try:
        pages = [base64.b64decode(p.encode("ascii"), validate=True) for p in msg["pages"]]
    except ValueError:
        return incomplete("transport process: malformed page")
    return {"pages": pages, "complete": msg["complete"], "error": msg["error"]}


class TransportProcess:
    def __init__(self, cmd=None):
        self.cmd = list(cmd or WORKER)
        self.proc = None

    def _start(self):
        if self.proc is None:
            self.proc = subprocess.Popen(self.cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
                                         encoding="utf-8")

    def get(self, api: str, endpoint: str, params: dict) -> dict:
        self._start()
        try:
            self.proc.stdin.write(json.dumps({"api": api, "endpoint": endpoint, "params": params}) + "\n")
            self.proc.stdin.flush()
            line = self.proc.stdout.readline()
        except (BrokenPipeError, OSError):
            line = ""
        if not line:
            raise TransportProcessEnded("the transport process ended")
        return decode(line)

    def close(self):
        """Close the child's stdin, wait for it and close its stdout, so no pipe handle is left open (review round
        12, F10: the unclosed stdout raised a ResourceWarning at teardown)."""
        if self.proc is not None:
            try:
                self.proc.stdin.close()
                self.proc.wait(timeout=30)
            except (OSError, subprocess.TimeoutExpired):
                self.proc.kill()
                self.proc.wait()
            finally:
                if self.proc.stdout is not None:
                    self.proc.stdout.close()
            self.proc = None


class ApiTransport:
    """The transport interface core.driver uses (get(endpoint, params)), for one API of the child process."""

    def __init__(self, proc: TransportProcess, api: str):
        self.proc, self.api = proc, api

    def get(self, endpoint: str, params: dict) -> dict:
        return self.proc.get(self.api, endpoint, params)


def transports(cmd=None, per_minute=None, trading_per_minute=None) -> dict:
    """The data and trading hosts, served by one child process started at the first request. per_minute and
    trading_per_minute are the pinned rate limits (review round 11, C2; review round 15, F12: one per API), passed to
    the child, which paces each host's requests at its own."""
    import atexit
    if cmd is None and per_minute is not None:
        cmd = [*WORKER, "--per-minute", repr(float(per_minute))]
        if trading_per_minute is not None:
            cmd += ["--trading-per-minute", repr(float(trading_per_minute))]
    proc = TransportProcess(cmd)
    atexit.register(proc.close)
    return {"data": ApiTransport(proc, "data"), "trading": ApiTransport(proc, "trading")}


def serve(apis: dict, stdin, stdout) -> None:
    """The child's loop: one request line in, one reply line out."""
    for line in stdin:
        req = json.loads(line)
        res = apis[req["api"]].get(req["endpoint"], req["params"])
        stdout.write(json.dumps({"pages": [base64.b64encode(p).decode("ascii") for p in res["pages"]],
                                 "complete": bool(res["complete"]), "error": res["error"]}) + "\n")
        stdout.flush()


def worker_apis(per_minute=None, trading_per_minute=None) -> dict:
    """The child's transports: the data host and the trading host (the asset master is a trading-API endpoint), each
    paced at its own pinned rate (review round 15, F12; review round 11, C2 shared one pacer). Without a trading
    rate both share the data pacer, as before."""
    from fetch.transport import TRADING_HOST, Pacer, Transport
    pacer = Pacer(per_minute)
    trading = Pacer(trading_per_minute) if trading_per_minute is not None else pacer
    return {"data": Transport(pacer=pacer), "trading": Transport(host=TRADING_HOST, pacer=trading)}


def per_minute_arg(argv: list, flag: str = "--per-minute"):
    if flag not in argv:
        return None
    v = float(argv[argv.index(flag) + 1])
    if not v > 0:
        raise SystemExit(f"{flag} must be positive")
    return v


def main() -> None:
    import tempfile
    sys.dont_write_bytecode = True
    sys.pycache_prefix = tempfile.mkdtemp(prefix="mover-v3-transport-pycache-")
    sys.path.insert(0, str(STUDY))
    serve(worker_apis(per_minute_arg(sys.argv[1:]), per_minute_arg(sys.argv[1:], "--trading-per-minute")), sys.stdin,
          sys.stdout)


if __name__ == "__main__":
    main()
