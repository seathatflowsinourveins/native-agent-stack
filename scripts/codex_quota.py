#!/usr/bin/env python3
"""Read the Codex account's usage-limit snapshot through the native app-server protocol; optionally gate on it.

  python3 -B scripts/codex_quota.py [--json] [--gate PERCENT] [--timeout SECONDS]

Starts `codex app-server` (the codex on PATH; stdio JSON-RPC) in an empty temporary directory, without the caller's
RUST_LOG, and sends `initialize` (clientInfo), the `initialized` notification and `account/rateLimits/read` with
excludeResetCreditDetails (the background-poll form: it skips the separate reset-credit detail lookup and still
returns the available count). The shapes are openai/codex codex-rs/app-server-protocol/src/protocol/common.rs,
v1.rs, v2/account.rs and rpc.rs, identical at rust-v0.155.1 and rust-v0.157.1: messages carry no "jsonrpc" field,
an error answer is {"id", "error": {"code", "message", "data"?}}, and the result's rateLimits is the account's
"codex" snapshot (codex-rs/app-server/src/request_processors/account_processor.rs). Messages the server sends on its
own are skipped, and a request from the server is answered with a method-not-found error. The server then gets EOF on
stdin; whatever is left of its process group is sent TERM, then KILL. One deadline (--timeout, default 30 s) bounds
the whole exchange. Reads no session transcript and no credential file; the account id in the answer is never printed.

--json prints exactly one JSON object on stdout and nothing else:
  used_percent, window_minutes, resets_at_utc   the primary window of that snapshot (resets_at_utc to the minute)
  secondary                                     the secondary window, same keys, or null
  plan_type, limit_id, rate_limit_reached_type, ordinary_usage_allowed, reset_credits_available
  buckets                                       every metered limit id: limit_name, normal_model_slug, primary,
                                                secondary, rate_limit_reached_type
  checked_at_utc
  gate                                          with --gate: {percent, reached, reasons}
  error                                         {stage, code, message} when no snapshot was read
Without --json the same result is one line of text (errors on stderr).

Exit: 0 snapshot read and the gate, if any, not reached; 3 gate reached: a window's used_percent >= PERCENT,
rateLimitReachedType set or ordinaryUsageAllowed false; 2 no snapshot (codex missing, timeout, an error answer,
the server exiting, an unusable reply) or, with --gate, a snapshot with nothing to judge. Linux and macOS,
Python 3.9+, standard library only.
"""

from __future__ import annotations

import argparse
import json
import os
import selectors
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone

EXIT_OK, EXIT_FAILED, EXIT_GATE = 0, 2, 3
INITIALIZE, READ = "initialize", "account/rateLimits/read"
CLIENT_INFO = {"name": "codex_quota_probe", "title": "native-agent-stack quota probe", "version": "1"}
READ_PARAMS = {"excludeResetCreditDetails": True}
METHOD_NOT_FOUND = -32601
MAX_LINE_BYTES = 1 << 20
MAX_TOTAL_BYTES = 8 << 20
MESSAGE_CHARS = 300
EOF_GRACE_S, TERM_GRACE_S = 2.0, 2.0


class ProbeError(Exception):
    def __init__(self, stage: str, message: str, code=None):
        super().__init__(message)
        self.stage, self.message, self.code = stage, message, code

    def as_json(self) -> dict:
        return {"stage": self.stage, "code": self.code, "message": self.message[:MESSAGE_CHARS]}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def text(value):
    return value if isinstance(value, str) else None


def utc_minute(epoch) -> str | None:
    if number(epoch) is None:
        return None
    try:
        return datetime.fromtimestamp(epoch, timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    except (OverflowError, OSError, ValueError):
        return None


def window(raw) -> dict | None:
    """RateLimitWindow {usedPercent, windowDurationMins, resetsAt (unix seconds)}."""
    if not isinstance(raw, dict):
        return None
    return {"used_percent": number(raw.get("usedPercent")), "window_minutes": number(raw.get("windowDurationMins")),
            "resets_at_utc": utc_minute(raw.get("resetsAt"))}


def summarize(result: dict) -> dict:
    """GetAccountRateLimitsResponse -> the printed summary (never accountId or rateLimitUpsell)."""
    snapshot = result.get("rateLimits")
    if not isinstance(snapshot, dict):
        raise ProbeError(READ, "the answer has no rateLimits snapshot")
    primary = window(snapshot.get("primary")) or {"used_percent": None, "window_minutes": None, "resets_at_utc": None}
    credits = result.get("rateLimitResetCredits")
    allowed = result.get("ordinaryUsageAllowed")
    out = {**primary, "plan_type": text(snapshot.get("planType")), "secondary": window(snapshot.get("secondary")),
           "limit_id": text(snapshot.get("limitId")),
           "rate_limit_reached_type": text(snapshot.get("rateLimitReachedType")),
           "ordinary_usage_allowed": allowed if isinstance(allowed, bool) else None,
           "reset_credits_available": number(credits.get("availableCount")) if isinstance(credits, dict) else None}
    buckets = result.get("rateLimitsByLimitId")
    out["buckets"] = {str(key): {"limit_name": text(value.get("limitName")),
                                 "normal_model_slug": text(value.get("normalModelSlug")),
                                 "primary": window(value.get("primary")), "secondary": window(value.get("secondary")),
                                 "rate_limit_reached_type": text(value.get("rateLimitReachedType"))}
                      for key, value in sorted(buckets.items()) if isinstance(value, dict)} \
        if isinstance(buckets, dict) else None
    return out


def judge(summary: dict, percent: float) -> tuple[bool | None, list[str]]:
    """(reached, reasons); reached is None when the snapshot has no window and no limit flag to judge."""
    reasons, judged = [], False
    for name, found in (("primary", summary), ("secondary", summary.get("secondary") or {})):
        used = found.get("used_percent")
        if used is None:
            continue
        judged = True
        if used >= percent:
            reasons.append(f"{name} window {used:g}% used >= {percent:g}% (window {found.get('window_minutes')} min, "
                           f"resets {found.get('resets_at_utc')})")
    if summary.get("rate_limit_reached_type"):
        judged = True
        reasons.append(f"rateLimitReachedType {summary['rate_limit_reached_type']}")
    if summary.get("ordinary_usage_allowed") is False:
        judged = True
        reasons.append("ordinaryUsageAllowed false")
    return (bool(reasons) if judged else None), reasons


class AppServer:
    """`codex app-server` over stdio, in its own process group."""

    def __init__(self, codex: str, cwd: str):
        env = {key: value for key, value in os.environ.items() if not key.startswith("RUST_LOG")}
        self.process = subprocess.Popen([codex, "app-server"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.DEVNULL, cwd=cwd, env=env, bufsize=0,
                                        start_new_session=True)
        self.selector = selectors.DefaultSelector()
        self.selector.register(self.process.stdout, selectors.EVENT_READ)
        self.buffer, self.total = b"", 0

    def send(self, message: dict, stage: str) -> None:
        data = (json.dumps(message, separators=(",", ":")) + "\n").encode("utf-8")
        try:
            while data:
                data = data[self.process.stdin.write(data):]
        except (BrokenPipeError, ValueError, OSError):
            raise ProbeError(stage, "the server closed its input") from None

    def message(self, deadline: float, stage: str) -> dict:
        while True:
            newline = self.buffer.find(b"\n")
            if newline >= 0:
                line, self.buffer = self.buffer[:newline], self.buffer[newline + 1:]
                try:
                    parsed = json.loads(line)
                except ValueError:
                    continue  # not a protocol message
                if isinstance(parsed, dict):
                    return parsed
                continue
            if len(self.buffer) > MAX_LINE_BYTES:
                raise ProbeError(stage, f"a server line exceeded {MAX_LINE_BYTES} bytes")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ProbeError(stage, "no answer before the deadline (timeout)")
            if not self.selector.select(remaining):
                continue
            chunk = os.read(self.process.stdout.fileno(), 65536)
            if not chunk:
                code = self.process.poll()
                raise ProbeError(stage, "the server closed its output before answering" if code is None
                                 else f"the server exited with code {code} before answering")
            self.total += len(chunk)
            if self.total > MAX_TOTAL_BYTES:
                raise ProbeError(stage, f"the server wrote more than {MAX_TOTAL_BYTES} bytes")
            self.buffer += chunk

    def request(self, request_id: int, method: str, params, deadline: float) -> dict:
        request = {"id": request_id, "method": method}
        if params is not None:
            request["params"] = params
        self.send(request, method)
        while True:
            message = self.message(deadline, method)
            if "method" in message:
                if "id" in message:  # a server request: never left waiting
                    self.send({"id": message["id"], "error": {"code": METHOD_NOT_FOUND, "message":
                                                              "not supported by the quota probe"}}, method)
                continue
            if message.get("id") != request_id:
                continue
            error = message.get("error")
            if error is not None:
                if isinstance(error, dict):
                    raise ProbeError(method, str(error.get("message") or "error answer without a message"),
                                     number(error.get("code")))
                raise ProbeError(method, "error answer: " + json.dumps(error)[:MESSAGE_CHARS])
            result = message.get("result")
            if not isinstance(result, dict):
                raise ProbeError(method, "the answer's result is not an object")
            return result

    def close(self) -> None:
        """EOF first; then TERM and KILL whatever is left of the server's process group."""
        pgid = self.process.pid
        try:
            self.process.stdin.close()
        except OSError:
            pass
        try:
            self.process.wait(timeout=EOF_GRACE_S)
        except subprocess.TimeoutExpired:
            pass
        for sig, grace in ((signal.SIGTERM, TERM_GRACE_S), (signal.SIGKILL, None)):
            if self.process.poll() is not None and not group_alive(pgid):
                break
            try:
                os.killpg(pgid, sig)
            except ProcessLookupError:
                pass
            end = time.monotonic() + (grace or 5.0)
            while time.monotonic() < end and not (self.process.poll() is not None and not group_alive(pgid)):
                time.sleep(0.05)
        if self.process.poll() is None:
            self.process.wait()
        self.selector.close()
        self.process.stdout.close()


def group_alive(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def read_snapshot(timeout: float) -> dict:
    codex = shutil.which("codex")
    if codex is None:
        raise ProbeError("start", "codex is not on PATH")
    deadline = time.monotonic() + timeout
    workdir = tempfile.mkdtemp(prefix="codex-quota-")  # no project config, AGENTS.md or repository in scope
    try:
        try:
            server = AppServer(codex, workdir)
        except OSError as error:
            raise ProbeError("start", f"could not start codex app-server: {error.strerror or error}") from None
        try:
            server.request(1, INITIALIZE, {"clientInfo": CLIENT_INFO}, deadline)
            server.send({"method": "initialized"}, INITIALIZE)
            return summarize(server.request(2, READ, READ_PARAMS, deadline))
        finally:
            server.close()
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def human(out: dict) -> str:
    line = (f"codex quota: {out.get('used_percent')}% of the {out.get('window_minutes')}-minute window used, resets "
            f"{out.get('resets_at_utc')} (plan {out.get('plan_type')})")
    secondary = out.get("secondary")
    if secondary:
        line += (f"; secondary {secondary.get('used_percent')}% of {secondary.get('window_minutes')} min, resets "
                 f"{secondary.get('resets_at_utc')}")
    if out.get("rate_limit_reached_type"):
        line += f"; limit reached: {out['rate_limit_reached_type']}"
    gate = out.get("gate")
    if gate:
        state = {True: "REACHED", False: "not reached", None: "cannot judge"}[gate["reached"]]
        line += f"; gate {gate['percent']:g}%: {state}" + (f" ({'; '.join(gate['reasons'])})" if gate["reasons"] else "")
    return line


def percent_arg(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{value!r} is not a number") from None
    if not 0 < parsed <= 100:
        raise argparse.ArgumentTypeError("PERCENT must be above 0 and at most 100")
    return parsed


def seconds_arg(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{value!r} is not a number") from None
    if not 0 < parsed <= 600:
        raise argparse.ArgumentTypeError("SECONDS must be above 0 and at most 600")
    return parsed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true", help="print exactly one JSON object and nothing else")
    parser.add_argument("--gate", type=percent_arg, metavar="PERCENT",
                        help="exit 3 when a window's used_percent >= PERCENT, rateLimitReachedType is set or "
                             "ordinaryUsageAllowed is false")
    parser.add_argument("--timeout", type=seconds_arg, default=30.0, metavar="SECONDS",
                        help="deadline for the whole exchange (default 30)")
    args = parser.parse_args(argv)
    try:
        out = read_snapshot(args.timeout)
    except ProbeError as error:
        if args.json:
            print(json.dumps({"error": error.as_json(), "checked_at_utc": utc_now()}))
        else:
            print(f"codex quota: no snapshot ({error.stage}): {error.message[:MESSAGE_CHARS]}", file=sys.stderr)
        return EXIT_FAILED
    out["checked_at_utc"] = utc_now()
    code = EXIT_OK
    if args.gate is not None:
        reached, reasons = judge(out, args.gate)
        out["gate"] = {"percent": args.gate, "reached": reached, "reasons": reasons}
        code = EXIT_GATE if reached else (EXIT_FAILED if reached is None else EXIT_OK)
        if reached is None:
            out["error"] = {"stage": "gate", "code": None,
                            "message": "the snapshot has no usage window and no limit flag to judge"}
    print(json.dumps(out) if args.json else human(out))
    return code


if __name__ == "__main__":
    sys.exit(main())
