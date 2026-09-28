"""Private start/wait/result glue around the pinned upstream CLI and E2E.

Sources: GPTR@0957c301 cli.py:306-336,359-362; CPython@v3.12.12
Doc/library/subprocess.rst (Popen/start_new_session), Doc/library/fcntl.rst
(LOCK_EX|LOCK_NB); existing recipe's GNU timeout process-group deadline.
No model-controlled shell, source modifications, service or host installation.
"""
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "e2e"))
from gateway import select_routes
from receipt import compression_snapshot, compression_delta, gateway_evidence_complete, phase_usage, route_metadata, write_receipt


def now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def atomic_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    temporary.chmod(0o600)
    temporary.replace(path)


def read_json(path, default=None):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {} if default is None else default


def envelope(run_id, arm, state="running", exit_class="running", exit_code=None):
    return {"schema_version": 1, "run_id": run_id, "arm": arm, "state": state,
            "exit_class": exit_class, "exit_code": exit_code,
            "result": f"runs/{run_id}/dispatch-result.json" if run_id else None,
            "receipt": f"runs/{run_id}/receipt.json" if run_id else None}


def classify(native_exit, execution_complete, evidence_complete):
    # DRB-II has scalar scores, no binary quality threshold. A negative verdict
    # here is a completed native process's failure, never a threshold on scores.
    if native_exit in (124, 137, -signal.SIGTERM, -signal.SIGKILL):
        return "incomplete_evidence", 30
    if native_exit:
        return "negative_verdict", 10
    if not execution_complete or not evidence_complete:
        return "incomplete_evidence", 30
    return "pass", 0


def finish(run_dir, job, exit_class, exit_code, receipt=None):
    if receipt is None:
        receipt = {"schema_version": 3, "arm": job["routes"]["arm"],
                   "routes": route_metadata(job["routes"]), "execution_complete": False,
                   "evidence_complete": False, "runtime_error_class": exit_class}
    atomic_json(run_dir / "receipt.json", receipt)
    result = envelope(run_dir.name, job["routes"]["arm"], "complete", exit_class, exit_code)
    result.update(execution_complete=receipt.get("execution_complete", False),
                  evidence_complete=receipt.get("evidence_complete", False))
    if "evaluation" in receipt:
        result["evaluation"] = receipt["evaluation"]
    atomic_json(run_dir / "dispatch-result.json", result)
    atomic_json(run_dir / "status.json", result)
    return result


def preflight(job):
    prefix = Path(job["prefix"])
    pins = read_json(HERE / "pins.json")
    if read_json(prefix / "installation-pins.json") != pins:
        raise ValueError("missing or stale installation pins")
    if not os.access(prefix / "venv/bin/python", os.X_OK):
        raise ValueError("worker runtime unavailable")
    source = prefix / "source" / ("gpt-researcher-" + pins["commit"])
    for name, expected in pins["upstream_files"].items():
        if hashlib.sha256((source / name).read_bytes()).hexdigest() != expected:
            raise ValueError("installed source changed")
    if job["mode"] == "e2e":
        from mcp_proxy import load_host
        from grader import verified_source
        load_host(job["host_file"])
        verified_source(prefix)
        if not os.access(prefix / "grader-venv/bin/python", os.X_OK):
            raise ValueError("grader runtime unavailable")


def child_environment(run_dir, routes):
    # No inherited provider keys, proxies, Python paths, dotenv, HOME or caches.
    env = {"HOME": str(run_dir / "home"), "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
           "LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1", "PYTHON_DOTENV_DISABLED": "1",
           "XDG_CACHE_HOME": str(run_dir / "cache"), "XDG_CONFIG_HOME": str(run_dir / "config"),
           "XDG_STATE_HOME": str(run_dir / "state"), "HF_HOME": str(run_dir / "cache/huggingface"),
           "NLTK_DATA": str(run_dir / "cache/nltk"), "ALLOW_PRIVATE_URLS": "false",
           "LANGCHAIN_TRACING_V2": "false", "LANGSMITH_TRACING": "false", "DO_NOT_TRACK": "1",
           "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "CHUB_TELEMETRY": "0", "CHUB_FEEDBACK": "0",
           "KEYWORD_MAX_RESULTS": "16", "KEYWORD_RELATIVE_THRESHOLD": "0.5", "COMPRESSION_THRESHOLD": "8000",
           "RUNTIME_WORKER_ARM": routes["arm"], "GPTR_MODEL": routes["worker"]["model"],
           "GPTR_BASE_URL": routes["worker"]["base_url"], "GPTR_JUDGE_MODEL": routes["judge"]["model"],
           "GPTR_JUDGE_BASE_URL": routes["judge"]["base_url"]}
    return env


def native_command(run_dir, job):
    prefix = Path(job["prefix"])
    args = [str(prefix / "venv/bin/python"), str(HERE / ("cli_runner.py" if job["mode"] == "cli" else "e2e/run.py")),
            "--prefix", str(prefix), "--run-dir", str(run_dir)]
    if job["mode"] == "cli":
        args += ["--report-type", job["report_type"]]
    else:
        args += ["--host-file", job["host_file"], "--model", job["routes"]["worker"]["model"],
                 "--base-url", job["routes"]["worker"]["base_url"], "--judge-model", job["routes"]["judge"]["model"]]
    return ["timeout", "--signal=TERM", "--kill-after=20s", "1800s" if job["mode"] == "cli" else "3700s", *args]


def cli_report(run_dir):
    # Native contract: cli.py:228-245,332-336. Never trust a success exit alone.
    paths = list((run_dir / "outputs").glob("*.md"))
    if len(paths) != 1 or paths[0].is_symlink() or not stat.S_ISREG(paths[0].stat().st_mode):
        raise ValueError("expected one native regular markdown report")
    if paths[0].stat().st_size > 8 * 1024 * 1024:
        raise ValueError("report exceeds receipt read bound")
    data = paths[0].read_bytes()
    report = data.decode("utf-8")
    if not re.match(r'---\ntask_id: "[a-fA-F0-9-]{36}"\n', report):
        raise ValueError("missing native front matter")
    header, separator, body = report[4:].partition("\n---\n")
    if not separator or not body.strip() or not re.search(r"^sources_count: \d+$", header, re.M):
        raise ValueError("missing native report body or metadata")
    marker = "Report written to '" + paths[0].relative_to(run_dir).as_posix() + "'"
    with (run_dir / "native-stdout.log").open(errors="replace") as handle:
        if not any(line.rstrip("\n") == marker for line in handle):
            raise ValueError("missing native completion marker")
    return {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data),
            "report": paths[0].relative_to(run_dir).as_posix()}


def event(run_dir, name, **fields):
    with (run_dir / "invocations.jsonl").open("a") as handle:
        handle.write(json.dumps({"event": name, "at": now(), **fields}) + "\n")


def supervise(run_dir):
    job = read_json(run_dir / "job.json")
    lock = (run_dir.parent.parent / "worker.lock").open("a")
    try:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return finish(run_dir, job, "busy", 75)
        try:
            preflight(job)
        except (OSError, ValueError, KeyError):
            return finish(run_dir, job, "setup_failure", 20)
        phases = {"worker_started": now()}
        atomic_json(run_dir / "phases.json", phases)
        before = compression_snapshot(job["routes"]["arm"]) if job["mode"] == "cli" else None
        event(run_dir, "native-started", entrypoint="cli.py" if job["mode"] == "cli" else "GPTResearcher SDK")
        with (run_dir / "native-stdout.log").open("w") as stdout, (run_dir / "native-stderr.log").open("w") as stderr:
            completed = subprocess.run(native_command(run_dir, job), cwd=run_dir,
                                       env=child_environment(run_dir, job["routes"]), stdout=stdout, stderr=stderr,
                                       pass_fds=(lock.fileno(),))
        event(run_dir, "native-finished", native_exit=completed.returncode)
        ended = now()
        if job["mode"] == "cli":
            phases["worker_ended"] = ended
            atomic_json(run_dir / "phases.json", phases)
            compression = compression_delta(before, compression_snapshot(job["routes"]["arm"]))
            gateway = phase_usage(run_dir, job["routes"], phases, job["engines_db_verified"])
            try:
                report = cli_report(run_dir)
            except (OSError, ValueError):
                report = None
            receipt = {"schema_version": 3, "arm": job["routes"]["arm"], "routes": route_metadata(job["routes"]),
                       "entrypoint": "assafelovic/gpt-researcher@0957c301 cli.py", "phases": phases,
                       "report": report, "gateway": {"worker": gateway["worker"]}, "compression": compression,
                       "execution_complete": completed.returncode == 0 and report is not None,
                       "evidence_complete": gateway_evidence_complete(gateway["worker"]) and
                           compression["status"] in ("observed", "not_applicable"),
                       "quality_verdict": "ungraded upstream CLI report",
                       "limitations": ["Native CLI does not receive scoped MCP configurations.",
                           "Gateway fallback attribution and aggregate compression can include other callers."]}
        else:
            phases = read_json(run_dir / "phases.json")
            execution = read_json(run_dir / "execution.json")
            receipt = write_receipt(run_dir, phases.get("worker_started", ended), ended, job["routes"]["worker"]["model"],
                                    execution.get("framework_version"), execution.get("runtime_error") or
                                    ("ProcessExit" if completed.returncode else None), routes=job["routes"], phases=phases,
                                    engines_verified=job["engines_db_verified"])
        outcome, code = classify(completed.returncode, receipt["execution_complete"], receipt["evidence_complete"])
        return finish(run_dir, job, outcome, code, receipt)
    except BaseException:
        finish(run_dir, job, "incomplete_evidence", 30)
        raise
    finally:
        lock.close()


def poll(run_dir):
    result = read_json(run_dir / "dispatch-result.json")
    if result:
        return result
    status = read_json(run_dir / "status.json")
    supervisor = read_json(run_dir / "supervisor.json")
    if supervisor:
        try:
            os.kill(supervisor["pid"], 0)
        except ProcessLookupError:
            return finish(run_dir, read_json(run_dir / "job.json"), "incomplete_evidence", 30)
    return status


def start(args, state):
    run_dir = state / "runs" / args.run_id
    run_dir.mkdir(parents=True, mode=0o700)  # no reuse: never append a second attempt
    status = envelope(args.run_id, args.arm)
    atomic_json(run_dir / "status.json", status)
    try:
        routes = select_routes({**os.environ, "RUNTIME_WORKER_ARM": args.arm})
        query = args.query_file.read_text() if args.mode == "cli" and args.query_file else ""
        if args.mode == "cli" and (not query.strip() or len(query) > 64000):
            raise ValueError("CLI requires a bounded query file")
    except (OSError, ValueError):
        # Persist a failed setup even if there is no executable query/config.
        job = {"routes": select_routes({"RUNTIME_WORKER_ARM": args.arm})}
        return finish(run_dir, job, "setup_failure", 20)
    for name in ("home", "cache", "config", "state", "mcp-work", "context-mode"):
        (run_dir / name).mkdir(mode=0o700)
    job = {"mode": args.mode, "routes": routes, "report_type": args.report_type,
           "prefix": str(Path(os.environ.get("GPTR_PREFIX", str(Path.home() / ".local/share/codex-ecosystem/tools/gpt-researcher-3.7.0"))).resolve()),
           "host_file": str(Path(os.environ.get("GPTR_HOST_FILE", str(state / "host.json"))).resolve()),
           "engines_db_verified": os.environ.get("GPTR_ENGINES_DB_VERIFIED") == "1"}
    atomic_json(run_dir / "job.json", job)
    (run_dir / "query.txt").write_text(query)
    atomic_json(run_dir / "status.json", status)
    event(run_dir, "dispatch-started", mode=args.mode, arm=args.arm)
    try:
        with (run_dir / "supervisor.log").open("w") as log:
            process = subprocess.Popen([sys.executable, str(HERE / "dispatch.py"), "_supervise", "--run-id", args.run_id],
                                       stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True,
                                       env={**os.environ, "GPTR_STATE_ROOT": str(state), "PYTHONDONTWRITEBYTECODE": "1"})
        atomic_json(run_dir / "supervisor.json", {"pid": process.pid})
    except OSError:
        return finish(run_dir, job, "setup_failure", 20)
    return status


def main():
    os.umask(0o077)
    class Parser(argparse.ArgumentParser):
        def error(self, message):
            raise ValueError(message)
    parser = Parser(description=__doc__)
    parser.add_argument("action", choices=("start", "wait", "result", "run", "_supervise"))
    parser.add_argument("--run-id", default=os.environ.get("GPTR_RUN_ID"))
    parser.add_argument("--arm", default=os.environ.get("RUNTIME_WORKER_ARM", "control"))
    parser.add_argument("--mode", choices=("cli", "e2e"), default="cli")
    parser.add_argument("--query-file", type=Path)
    parser.add_argument("--report-type", choices=("research_report", "deep"), default="research_report")
    parser.add_argument("--timeout", type=float, default=1)
    try:
        args = parser.parse_args()
    except ValueError:
        print(json.dumps(envelope(None, None, "complete", "setup_failure", 20)))
        return 20
    valid_id = bool(args.run_id and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", args.run_id))
    state = Path(os.environ.get("GPTR_STATE_ROOT", str(Path.home() / ".local/state/native-agent-stack/runtime-workers/gpt-researcher"))).resolve()
    if not valid_id or not 0 <= args.timeout <= 60 or args.arm not in ("control", "engines-on"):
        print(json.dumps(envelope(None, None, "complete", "setup_failure", 20)))
        return 20
    run_dir = state / "runs" / args.run_id
    try:
        if args.action == "_supervise":
            return supervise(run_dir)["exit_code"]
        if args.action in ("start", "run"):
            result = start(args, state)
        elif not (run_dir / "status.json").is_file():
            raise ValueError("unknown run")
        else:
            result = poll(run_dir)
        if args.action in ("wait", "run"):
            deadline = time.monotonic() + args.timeout
            while result["state"] != "complete" and (args.action == "run" or time.monotonic() < deadline):
                time.sleep(0.1)
                result = poll(run_dir)
        print(json.dumps(result, sort_keys=True))
        return result["exit_code"] if result["state"] == "complete" else (0 if args.action == "start" else 76)
    except (OSError, ValueError, KeyError) as error:
        result = envelope(args.run_id, args.arm if args.arm in ("control", "engines-on") else None,
                          "complete", "setup_failure", 20)
        result["error_class"] = type(error).__name__
        print(json.dumps(result, sort_keys=True))
        return 20


if __name__ == "__main__":
    raise SystemExit(main())
