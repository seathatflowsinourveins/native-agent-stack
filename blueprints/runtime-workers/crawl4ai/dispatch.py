#!/usr/bin/env python3
"""Bash child lifecycle for the native worker, not a second crawler/runtime.

Sources: Crawl4AI@133e1d92 docs/examples/llm_extraction_openai_pricing.py:15-53;
CPython@v3.12.12 Lib/subprocess.py (Popen/start_new_session, run/timeout).
The stable status/result contract is local integration required by round 3.
"""
import argparse
import fcntl
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from urllib.parse import urlsplit
from pathlib import Path

from host import locations, load_host, private_file
from worker import arm_settings, selected_arm

ROOT = Path(__file__).resolve().parent
OUTCOMES = {0: "pass", 2: "setup_failure", 3: "negative_verdict", 4: "incomplete_evidence"}


def write_json(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


def finish(directory, receipt, code):
    receipt.update(outcome=OUTCOMES[code], exit_code=code)
    write_json(directory / "receipt.json", receipt)
    status = json.loads((directory / "status.json").read_text())
    status.update(state="finished", exit_code=code)
    write_json(directory / "status.json", status)


def announce(directory):
    status = json.loads((directory / "status.json").read_text())
    print(json.dumps(status, sort_keys=True))
    return status.get("exit_code") if status["state"] == "finished" else 4


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        raise ValueError("authenticated local API redirect refused")


def api_request(path, payload=None):
    """Crawl4AI@133e1d92 deploy/docker/job.py:114-149; token stays in headers."""
    if not re.fullmatch(r"/crawl/job(?:/crawl_[a-f0-9]{8})?", path):
        raise ValueError("unknown native job route")
    _, state = locations()
    secret = state / "secrets/api_token"
    private_file(secret)
    base = f"http://127.0.0.1:{load_host()['api_port']}"
    request = urllib.request.Request(base + path,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={"Authorization": "Bearer " + secret.read_text().strip(), "Content-Type": "application/json"})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    with opener.open(request, timeout=30) as response:
        raw = response.read(16 * 1024 * 1024 + 1)
        if len(raw) > 16 * 1024 * 1024:
            raise ValueError("native result exceeds bounded transport")
        return json.loads(raw), response.status


def crawl_job(directory, urls):
    """Native non-LLM fallback: api.py:997-1078,587-605 at the Crawl4AI pin.

    Server status owns the verdict. No local content scoring or model call.
    """
    for url in urls:
        parsed = urlsplit(url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("REST fallback requires credential-free HTTPS seed URLs")
    if not urls:
        raise ValueError("REST fallback requires at least one seed URL")
    accepted, code = api_request("/crawl/job", {"urls": urls})
    task = accepted.get("task_id", "")
    if code != 202 or not re.fullmatch(r"crawl_[a-f0-9]{8}", task):
        raise ValueError("native enqueue did not return the pinned task contract")
    deadline = time.monotonic() + 180
    polls = 0
    while time.monotonic() < deadline:
        try:
            data, code = api_request("/crawl/job/" + task)
        except (OSError, ValueError) as exc:
            return {"passed": False, "native_status": "unobserved_after_enqueue",
                    "error_class": type(exc).__name__, "poll_count": polls}, 4
        polls += 1
        if code != 200:
            break
        status = data.get("status")
        if status == "failed":
            return {"passed": False, "native_status": "failed", "poll_count": polls}, 3
        if status == "completed":
            result = data.get("result", {})
            write_json(directory / "result.json", result)
            rows = result.get("results", []) if isinstance(result, dict) else []
            complete = (isinstance(result, dict) and type(result.get("success")) is bool and
                        isinstance(rows, list) and len(rows) == len(urls) and all(
                            isinstance(row, dict) and type(row.get("success")) is bool for row in rows))
            passed = complete and result["success"] and all(row["success"] for row in rows)
            return {"passed": passed, "native_status": status, "poll_count": polls,
                    "source": "native /crawl/job status; content is not graded",
                    "result_sha256": hashlib.sha256((directory / "result.json").read_bytes()).hexdigest()}, (0 if passed else 3 if complete else 4)
        if status != "processing":
            break
        time.sleep(1)
    return {"passed": False, "native_status": "incomplete", "poll_count": polls}, 4


def execute(directory, arm):
    """Only one provider/container trial uses the fixed fixture ports at a time."""
    prefix, state = locations()
    status = json.loads((directory / "status.json").read_text())
    status["state"] = "running"
    write_json(directory / "status.json", status)
    try:
        request = json.loads((directory / "request.json").read_text())
        if request["kind"] == "crawl":
            receipt, code = crawl_job(directory, request["urls"])
            receipt.update(arm=arm, route_applicability="separate_responses_caller_only",
                           llm_used=False, usage={"status": "not_applicable"})
            finish(directory, receipt, code)
            return code
        with (state / "extraction.lock").open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                finish(directory, {"passed": False, "reason": "another extraction run owns the fixture ports"}, 4)
                return 4
            with (directory / "dispatch.log").open("a") as log:
                result = subprocess.run([str(prefix / "venv/bin/python"), str(ROOT / "e2e/run.py"),
                    "--run-dir", str(directory), "--arm", arm], env=dict(os.environ, CRAWL4AI_ARM=arm,
                    PYTHONDONTWRITEBYTECODE="1"), stdout=log, stderr=subprocess.STDOUT, timeout=2400)
            receipt = json.loads((directory / "receipt.json").read_text())
            code = result.returncode if result.returncode in OUTCOMES else 4
            if receipt.get("outcome") == "incomplete_evidence" and code == 0:
                code = 4
            finish(directory, receipt, code)
            return code
    except Exception as exc:
        code = 4 if isinstance(exc, subprocess.TimeoutExpired) else 2
        finish(directory, {"passed": False, "error_class": type(exc).__name__}, code)
        return code


def main(argv=None):
    os.umask(0o077)
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("start", "wait", "result", "_run"))
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--arm", choices=("control", "engines-on", "comparison"), default=None)
    parser.add_argument("--timeout", type=float, default=55)
    parser.add_argument("--kind", choices=("extraction", "crawl"), default="crawl",
                        help="model-free crawl for a Responses caller; extraction is the historical Chat Completions comparison")
    parser.add_argument("--url", action="append", default=[])
    args = parser.parse_args(argv)
    try:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", args.run_id):
            raise ValueError("invalid run id")
        arm = args.arm or selected_arm()
        _, state = locations()
        directory = state / "runs" / args.run_id
        if args.action == "start":
            request = {"kind": args.kind, "urls": args.url}
            request_hash = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
            directory.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            try:
                directory.mkdir(mode=0o700)
            except FileExistsError:
                existing = json.loads((directory / "status.json").read_text())
                if directory.is_symlink() or existing["arm"] != arm or existing["request_sha256"] != request_hash:
                    raise ValueError("run id already belongs to another request")
                return announce(directory)
            write_json(directory / "status.json", {"run_id": args.run_id, "arm": arm, "state": "starting",
                "kind": args.kind, "request_sha256": request_hash,
                "receipt_path": str(directory / "receipt.json"), "status_path": str(directory / "status.json"),
                "exit_code": None})
            write_json(directory / "receipt.json", {"passed": False, "outcome": "incomplete_evidence", "exit_code": 4})
            write_json(directory / "request.json", request)
            try:
                if (args.kind == "crawl") != bool(args.url):
                    raise ValueError("--url is required for crawl and unavailable for the frozen extraction trial")
                if args.kind == "extraction":
                    arm_settings(json.loads((ROOT / "config/worker.json").read_text()), arm)
                with (directory / "dispatch.log").open("a") as log:
                    subprocess.Popen([sys.executable, str(ROOT / "dispatch.py"), "_run", "--run-id", args.run_id,
                        "--arm", arm], stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                        start_new_session=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
                announce(directory)
                return 0  # submission accepted; verdict is obtained with wait/result
            except Exception as exc:
                finish(directory, {"passed": False, "error_class": type(exc).__name__}, 2)
                return announce(directory)
        status = json.loads((directory / "status.json").read_text())
        if directory.is_symlink() or status["arm"] != arm:
            raise ValueError("run identity mismatch")
        if args.action == "_run":
            return execute(directory, arm)
        if args.action == "wait":
            deadline = time.monotonic() + max(0, min(args.timeout, 55))
            while status["state"] != "finished" and time.monotonic() < deadline:
                time.sleep(min(0.25, max(0, deadline - time.monotonic())))
                status = json.loads((directory / "status.json").read_text())
        return announce(directory)
    except (OSError, ValueError, KeyError) as exc:
        print(json.dumps({"outcome": "setup_failure", "error_class": type(exc).__name__, "exit_code": 2}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
