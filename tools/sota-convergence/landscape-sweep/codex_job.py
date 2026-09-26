#!/usr/bin/env python3
"""GPT-6 (Codex CLI) job runner for the landscape sweep; codex_call.sh is its command-line front.

  codex_call.sh [--work-dir DIR] start  <job-id> <prompt-file> <schema-file>
  codex_call.sh [--work-dir DIR] wait   <job-id> [seconds]    default 540; prints "done exit=N" or "running"
  codex_call.sh [--work-dir DIR] result <job-id>              one JSON line: status, exit, started, finished,
                                                              usage, usage_status, output_text, stderr_tail,
                                                              limit, limit_marker, model, effort, codex_version,
                                                              inputs, attempts, quota

`start` detaches one job and returns at once. The job waits for a semaphore slot (an fcntl lock on
<lock dir>/slot-<n>, held by the runner and by codex itself, so a killed runner never frees a slot early), then runs
this, in the empty directory <work-dir>/empty, bounded to 3000 s (exit 124 on timeout):

  codex exec --ignore-user-config --skip-git-repo-check -s read-only -m gpt-6-astra \
    -c model_reasoning_effort="max" -c web_search="live" --output-schema <job>/schema.json -o <job>/last.json --json "<prompt>" </dev/null

--ignore-user-config keeps the host's Codex config out of the lane, the sandbox is read-only, stdin is /dev/null
(background `codex exec` otherwise waits on stdin), and the effort is max. Never ultra: ultra lets Codex delegate to
sub-agents, which breaks the one-model lane. Codex runs without the caller's RUST_LOG, so its stderr carries only
its default `error`-level diagnostics (EXEC_DEFAULT_LOG_FILTER, codex-rs/exec/src/lib.rs at rust-v0.155.1): at
trace level Codex logs model response data (codex-rs/codex-api/src/sse/responses.rs), which could quote any text. The model and slot count come from <work-dir>/staged.json (build_args.py
--gpt6-model / --slots / --lock-dir); defaults gpt-6-astra, 3 slots, <work-dir>/locks. The codex binary is the one
on PATH.

Usage limit: when Codex reports "hit your usage limit" the job ends with exit 3 and writes <work-dir>/LIMIT; while
that file exists no job starts and jobs still waiting for a slot end with exit 3, so the coordinator can stop and
notify. Only Codex's own error reports count: the `error` / `turn.failed` events that `codex exec --json` prints on
stdout (openai/codex rust-v0.155.1, codex-rs/exec/src/exec_events.rs and event_processor_with_jsonl_output.rs), and,
only when no turn completed, an ERROR/Error line on stderr. Model content (item.* events: messages, web results,
cited pages) never counts: on 2026-09-26 a grep of the whole event stream matched a cited README's "Usage
limitation" and set the marker falsely.

Quota gate (optional; off unless staged.json codex.quota_stop_percent is set, a number above 0 and at most 100):
after a job gets its slot and before codex starts, the runner runs `codex_quota.py --json --gate <percent>` (the
copy build_args.py staged beside this file, else the checkout's scripts/codex_quota.py), which reads the account's
usage snapshot through `codex app-server` (account/rateLimits/read) and exits 3 when a window's used_percent reaches
the percent, rateLimitReachedType is set or ordinaryUsageAllowed is false. Exit 3 is refused like a usage limit: the
job ends with exit 3 before codex starts, and <work-dir>/LIMIT (when absent) and the job's stderr.txt get the
reason, so the coordinator can tell the user to reset. Every probe is recorded in <job>/quota.json (`result` gives
its summary as `quota`); a probe that fails (no codex, timeout after codex.quota_timeout_s, default 30 s, an error
answer, a missing script) is recorded and never blocks the job.

A job is bound to its inputs: <job>/inputs.json holds the sha256 of its prompt and schema, the model and the effort.
A job whose attempt finished with exit 0 for the same inputs is not rerun ("already done"). Any other earlier
attempt (failed, refused, or done for different inputs, as after a Workflow resume regenerated the prompt) is moved
unchanged to <job>/attempts/<n>/ and the job starts again; `result` lists every earlier attempt with its exit and
usage ("unavailable" when Codex reported none), so failed attempts stay counted. A job that is still running is left
alone ("already running"), or refused (exit 2) when it runs for different inputs.

Work dir: --work-dir, else this file's directory when build_args.py staged it there (staged.json present), else
$SWEEP_WORK_DIR. It must lie outside every git repository: Codex would otherwise load that repository's AGENTS.md
into the lane. Standard library only; Linux and macOS (Python 3.9+).
"""

from __future__ import annotations

import errno
import fcntl
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
STAGED = "staged.json"
DEFAULT_MODEL = "gpt-6-astra"
EFFORT = "max"
DEFAULTS = {"slots": 3, "timeout_s": 3000.0, "wait_poll_s": 10.0, "slot_poll_s": 5.0, "kill_grace_s": 10.0,
            "quota_timeout_s": 30.0}
QUOTA_SCRIPT = "codex_quota.py"
QUOTA_BACKSTOP_S = 30.0  # beyond the probe's own deadline, for a probe that itself hangs
LIMIT_PHRASE = re.compile(r"hit your usage limit", re.IGNORECASE)
# Codex's own error lines: "ERROR: ...", "Error: ..." (eprintln) or a tracing record "<timestamp> ERROR <target>: ...".
STDERR_ERROR_LINE = re.compile(r"^(?:\S+\s+)?(?:ERROR|Error)\b")
# The prompt is one argv string, as in the 2026-09-26 runner; Linux caps one argument at 131072 bytes.
MAX_PROMPT_BYTES = 120_000
JOB_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
MODEL_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")
# Everything one attempt writes; an earlier attempt's files move together to attempts/<n>/.
ATTEMPT_FILES = ("events.jsonl", "stderr.txt", "last.json", "started", "finished", "exit", "slot", "model",
                 "codex_version", "done", "prompt.txt", "schema.json", "inputs.json", "runner.log", "quota.json")
EXIT_LIMIT, EXIT_TIMEOUT, EXIT_NO_CODEX, EXIT_REFUSED = 3, 124, 127, 2


class UsageError(Exception):
    """A refusal before any job state changes (bad arguments, work dir inside a repository)."""


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def inside_repository(path: Path) -> Path | None:
    for candidate in (path, *path.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def resolve_work_dir(explicit: str | None, script_dir: Path = HERE) -> Path:
    """--work-dir, else the staged copy's own directory, else $SWEEP_WORK_DIR; never inside a repository."""
    if explicit:
        base = Path(explicit)
    elif (script_dir / STAGED).is_file():
        base = script_dir
    elif os.environ.get("SWEEP_WORK_DIR"):
        base = Path(os.environ["SWEEP_WORK_DIR"])
    else:
        raise UsageError("no work directory: pass --work-dir, set SWEEP_WORK_DIR, or run the copy build_args.py "
                         "staged into the work directory")
    base = base.expanduser().resolve()
    if not base.is_dir():
        raise UsageError(f"work directory {base} does not exist")
    repo = inside_repository(base)
    if repo is not None:
        raise UsageError(f"work directory {base} is inside the git repository {repo}; use a directory outside "
                         "every repository")
    return base


def settings(base: Path) -> dict:
    staged = {}
    if (base / STAGED).is_file():
        staged = (json.loads((base / STAGED).read_text(encoding="utf-8")) or {}).get("codex") or {}
    out = {key: type(value)(staged.get(key, value)) for key, value in DEFAULTS.items()}
    if out["slots"] < 1:
        raise UsageError("codex.slots must be at least 1")
    lock_dir = Path(staged.get("lock_dir") or "locks").expanduser()
    out["lock_dir"] = lock_dir if lock_dir.is_absolute() else base / lock_dir
    out["model"] = str(staged.get("model") or DEFAULT_MODEL)
    if not MODEL_NAME.fullmatch(out["model"]):
        raise UsageError(f"codex.model {out['model']!r} is not a model name")
    stop = staged.get("quota_stop_percent")
    if stop is not None and (isinstance(stop, bool) or not isinstance(stop, (int, float)) or not 0 < stop <= 100):
        raise UsageError(f"codex.quota_stop_percent {stop!r} must be a number above 0 and at most 100 (or absent)")
    out["quota_stop_percent"] = None if stop is None else float(stop)
    if not 0 < out["quota_timeout_s"] <= 600:
        raise UsageError("codex.quota_timeout_s must be above 0 and at most 600")
    return out


def job_dir(base: Path, job: str) -> Path:
    if not JOB_ID.fullmatch(job or ""):
        raise UsageError(f"job id {job!r} must match {JOB_ID.pattern}")
    return base / "gpt6" / job


def read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return None


def write_atomic(path: Path, text: str) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def try_lock(fd: int) -> bool:
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError as error:
        if error.errno in (errno.EAGAIN, errno.EACCES, errno.EWOULDBLOCK):
            return False
        raise


def open_lock(path: Path) -> int:
    return os.open(path, os.O_RDWR | os.O_CREAT, 0o644)


def exit_code(directory: Path) -> int | None:
    text = read(directory / "exit")
    try:
        return int(text.strip()) if text is not None else None
    except ValueError:
        return None


def finish(directory: Path, code: int) -> None:
    write_atomic(directory / "finished", utc_now() + "\n")
    write_atomic(directory / "exit", f"{code}\n")
    (directory / "done").touch()


def running(directory: Path) -> bool:
    """True while a runner or its codex holds the job lock."""
    if not (directory / "job.lock").exists():
        return False
    fd = open_lock(directory / "job.lock")
    try:
        if try_lock(fd):
            fcntl.flock(fd, fcntl.LOCK_UN)
            return False
        return True
    finally:
        os.close(fd)


def events(directory: Path) -> list[dict]:
    out = []
    for line in (read(directory / "events.jsonl") or "").splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict):
            out.append(event)
    return out


def turn_usage(directory: Path) -> dict | None:
    """Summed `turn.completed` usage, or None when Codex reported no usage (no turn completed)."""
    usage, reported = {}, False
    for event in events(directory):
        if event.get("type") == "turn.completed" and isinstance(event.get("usage"), dict):
            reported = True
            for key, value in event["usage"].items():
                if isinstance(value, int) and not isinstance(value, bool):
                    usage[key] = usage.get(key, 0) + value
    return usage if reported else None


def limit_error(directory: Path) -> bool:
    """Codex itself reported the usage limit: in an `error` / `turn.failed` event, or, when no turn completed, in one
    of its own error lines on stderr. A completed turn was not limited, whatever a diagnostic line quotes."""
    parsed = events(directory)
    for event in parsed:
        if event.get("type") == "error":
            message = event.get("message")
        elif event.get("type") == "turn.failed" and isinstance(event.get("error"), dict):
            message = event["error"].get("message")
        else:
            continue  # item.* events carry model content: never evidence of a limit
        if isinstance(message, str) and LIMIT_PHRASE.search(message):
            return True
    if any(event.get("type") == "turn.completed" for event in parsed):
        return False
    return any(STDERR_ERROR_LINE.match(line) and LIMIT_PHRASE.search(line)
               for line in (read(directory / "stderr.txt") or "").splitlines())


def codex_env() -> dict:
    """The caller's environment without Rust tracing settings (see the module docstring)."""
    return {key: value for key, value in os.environ.items() if not key.startswith("RUST_LOG")}


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def job_inputs(prompt: bytes, schema: bytes, model: str) -> dict:
    return {"prompt_sha256": sha256_hex(prompt), "schema_sha256": sha256_hex(schema), "model": model,
            "effort": EFFORT}


def read_json(path: Path):
    text = read(path)
    try:
        return json.loads(text) if text is not None else None
    except ValueError:
        return None


def archive_attempt(directory: Path) -> int | None:
    """Move an earlier attempt's files, unchanged, to attempts/<n>/ (n = 1, 2, ...); None when there was none."""
    present = [name for name in ATTEMPT_FILES if (directory / name).exists()]
    if not present:
        return None
    attempts = directory / "attempts"
    attempts.mkdir(exist_ok=True)
    number = 1 + max((int(p.name) for p in attempts.iterdir() if p.name.isdigit()), default=0)
    target = attempts / str(number)
    target.mkdir()
    for name in present:
        os.replace(directory / name, target / name)
    return number


def codex_argv(codex: str, directory: Path, model: str, prompt: str) -> list[str]:
    # Live web search: `--search` before exec (and no flag) sends external_web_access false, a cached index;
    # only web_search="live" sends true (evidence/artifacts/sota-refresh-20260926/codex/results/websearch-*.json).
    return [codex, "exec", "--ignore-user-config", "--skip-git-repo-check", "-s", "read-only",
            "-m", model, "-c", f'model_reasoning_effort="{EFFORT}"', "-c", 'web_search="live"',
            "--output-schema", str(directory / "schema.json"), "-o", str(directory / "last.json"), "--json", prompt]


def retire(directory: Path) -> None:
    """Archive a finished attempt without starting a new one (skipped while a runner holds the job)."""
    lock_fd = open_lock(directory / "job.lock")
    try:
        if try_lock(lock_fd):
            archive_attempt(directory)
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
    finally:
        os.close(lock_fd)


def start(base: Path, job: str, prompt_file: str, schema_file: str) -> int:
    directory = job_dir(base, job)
    prompt_bytes = Path(prompt_file).read_bytes()
    schema_bytes = Path(schema_file).read_bytes()
    inputs = job_inputs(prompt_bytes, schema_bytes, settings(base)["model"])  # also refuses a broken staged.json
    changed = False
    if (directory / "done").exists() and exit_code(directory) == 0:
        if read_json(directory / "inputs.json") == inputs:
            print(f"already done: {job}")
            return 0
        changed = True
        print(f"inputs changed since {job} finished; its attempt is kept under attempts/")
    if (base / "LIMIT").exists():
        if changed:
            retire(directory)  # a refused start must not leave another claim's output as this job's result
        print(f"LIMIT marker present; refusing to start {job}")
        reason = limit_reason(base)
        if reason:
            print(f"LIMIT: {reason}")
        return EXIT_LIMIT
    directory.mkdir(parents=True, exist_ok=True)
    lock_fd = open_lock(directory / "job.lock")
    if not try_lock(lock_fd):
        os.close(lock_fd)
        if read_json(directory / "inputs.json") not in (None, inputs):
            print(f"already running with different inputs: {job}; not started")
            return EXIT_REFUSED
        print(f"already running: {job}")
        return 0
    try:
        archive_attempt(directory)
        (directory / "prompt.txt").write_bytes(prompt_bytes)
        (directory / "schema.json").write_bytes(schema_bytes)
        write_atomic(directory / "inputs.json", json.dumps(inputs, sort_keys=True) + "\n")
        problem = None
        try:
            json.loads(schema_bytes)
        except ValueError:
            problem = (EXIT_REFUSED, f"schema {schema_file} is not JSON")
        if problem is None and len(prompt_bytes) > MAX_PROMPT_BYTES:
            problem = (EXIT_REFUSED, f"prompt is {len(prompt_bytes)} bytes; one argument holds at most "
                                     f"{MAX_PROMPT_BYTES}")
        if problem is None and shutil.which("codex") is None:
            problem = (EXIT_NO_CODEX, "codex is not on PATH")
        if problem is not None:
            write_atomic(directory / "stderr.txt", problem[1] + "\n")
            finish(directory, problem[0])
            print(f"not started {job}: {problem[1]}")
            return problem[0]
        (base / "empty").mkdir(exist_ok=True)
        with open(directory / "runner.log", "wb") as log:
            subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--work-dir", str(base), "run", job],
                             cwd=str(base), stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                             start_new_session=True, pass_fds=(lock_fd,),
                             env={**os.environ, "SWEEP_JOB_LOCK_FD": str(lock_fd)})
    finally:
        os.close(lock_fd)  # the detached runner keeps its inherited copy, so the job stays locked
    print(f"started {job}")
    return 0


def acquire_slot(base: Path, config: dict) -> tuple[int | None, int | None]:
    config["lock_dir"].mkdir(parents=True, exist_ok=True)
    while True:
        for number in range(1, config["slots"] + 1):
            fd = open_lock(config["lock_dir"] / f"slot-{number}")
            if try_lock(fd):
                return fd, number
            os.close(fd)
        time.sleep(config["slot_poll_s"])
        if (base / "LIMIT").exists():
            return None, None


def codex_version(codex: str) -> str | None:
    try:
        done = subprocess.run([codex, "--version"], stdin=subprocess.DEVNULL, capture_output=True, text=True,
                              timeout=60, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    lines = (done.stdout or "").strip().splitlines()
    return lines[0].strip() if done.returncode == 0 and lines else None


def quota_script(script_dir: Path = HERE) -> Path | None:
    """The copy build_args.py staged beside this file; in the checkout (no staged.json here), scripts/codex_quota.py."""
    staged = script_dir / QUOTA_SCRIPT
    if staged.is_file():
        return staged
    if (script_dir / STAGED).is_file() or len(script_dir.parents) <= 2:
        return None  # a staged runner uses only its own frozen copy
    checkout = script_dir.parents[2] / "scripts" / QUOTA_SCRIPT
    return checkout if checkout.is_file() else None


def quota_gate(base: Path, directory: Path, config: dict) -> str | None:
    """Run the quota probe with --gate and record it in <job>/quota.json; the reason when the gate is reached, else
    None. A failed probe is recorded and never blocks the job."""
    percent = config["quota_stop_percent"]
    record = {"checked_at": utc_now(), "stop_percent": percent, "status": "probe_failed", "exit": None,
              "report": None}
    script = quota_script()
    if script is None:
        record["error"] = f"{QUOTA_SCRIPT} is neither beside the runner nor in the checkout's scripts/"
    else:
        try:
            done = subprocess.run([sys.executable, "-B", str(script), "--json", "--gate", repr(float(percent)),
                                   "--timeout", repr(float(config['quota_timeout_s']))],
                                  cwd=str(base / "empty"), stdin=subprocess.DEVNULL, capture_output=True, text=True,
                                  timeout=config["quota_timeout_s"] + QUOTA_BACKSTOP_S, env=codex_env(), check=False)
            lines = (done.stdout or "").strip().splitlines()
            try:
                report = json.loads(lines[-1]) if lines else None
            except ValueError:
                report = None
            record.update(exit=done.returncode, report=report if isinstance(report, dict) else None)
            if done.returncode in (0, 3) and record["report"] is not None:
                record["status"] = "gate" if done.returncode == 3 else "ok"
            else:
                error = (record["report"] or {}).get("error")
                record["error"] = (f"{error.get('stage')}: {error.get('message')}" if isinstance(error, dict)
                                   else (done.stderr or "").strip()[-400:] or f"exit {done.returncode}")
        except subprocess.TimeoutExpired:
            record["error"] = f"the quota probe did not finish within {config['quota_timeout_s'] + QUOTA_BACKSTOP_S:g} s"
        except (OSError, subprocess.SubprocessError) as error:
            record["error"] = f"the quota probe could not run ({type(error).__name__})"
    write_atomic(directory / "quota.json", json.dumps(record, sort_keys=True) + "\n")
    if record["status"] != "gate":
        return None
    reasons = ((record["report"] or {}).get("gate") or {}).get("reasons") or []
    return "; ".join(str(reason) for reason in reasons) or "the quota gate was reached"


def quota_summary(directory: Path) -> dict | None:
    record = read_json(directory / "quota.json")
    if not isinstance(record, dict):
        return None
    report = record.get("report") if isinstance(record.get("report"), dict) else {}
    return {"status": record.get("status"), "stop_percent": record.get("stop_percent"),
            "checked_at": record.get("checked_at"), "used_percent": report.get("used_percent"),
            "resets_at_utc": report.get("resets_at_utc"),
            "reasons": (report.get("gate") or {}).get("reasons") if isinstance(report.get("gate"), dict) else None,
            "error": record.get("error")}


def mark_limit(base: Path, text: str) -> None:
    """Create <work-dir>/LIMIT holding text; an existing marker (another job's reason, a real limit) is kept."""
    try:
        fd = os.open(base / "LIMIT", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError:
        return
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(text + "\n")


def limit_reason(base: Path) -> str:
    return " ".join((read(base / "LIMIT") or "").split())[:400]


def group_alive(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def stop_group(process: subprocess.Popen, grace_s: float) -> None:
    """TERM the job's whole process group, then KILL whatever is left of it after the grace period, including
    children that ignore TERM after Codex itself has exited (they would keep the slot and job locks)."""
    pgid = process.pid
    try:
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    end = time.monotonic() + grace_s
    while time.monotonic() < end:
        if process.poll() is not None and not group_alive(pgid):
            return
        time.sleep(0.1)
    try:
        os.killpg(pgid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait()


def run(base: Path, job: str) -> int:
    directory = job_dir(base, job)
    config = settings(base)
    lock_fd = int(os.environ.get("SWEEP_JOB_LOCK_FD", "-1"))
    if lock_fd < 0:  # started by hand, not by `start`
        lock_fd = open_lock(directory / "job.lock")
        if not try_lock(lock_fd):
            print(f"already running: {job}")
            return 0
    slot_fd, slot = acquire_slot(base, config)
    if slot_fd is None or (base / "LIMIT").exists():
        reason = limit_reason(base)
        write_atomic(directory / "stderr.txt", "LIMIT marker present; the job did not start"
                     + (f" ({reason})" if reason else "") + "\n")
        finish(directory, EXIT_LIMIT)
        return EXIT_LIMIT
    if config["quota_stop_percent"] is not None:
        (base / "empty").mkdir(exist_ok=True)
        reason = quota_gate(base, directory, config)
        if reason is not None:
            text = (f"quota gate: {reason}; codex.quota_stop_percent {config['quota_stop_percent']:g}; checked "
                    f"{utc_now()} before {job} started")
            mark_limit(base, text)
            write_atomic(directory / "stderr.txt", text + "\n")
            finish(directory, EXIT_LIMIT)
            return EXIT_LIMIT
    write_atomic(directory / "started", utc_now() + "\n")
    write_atomic(directory / "slot", f"{slot}\n")
    write_atomic(directory / "model", config["model"] + "\n")
    codex = shutil.which("codex")
    if codex is None:
        write_atomic(directory / "stderr.txt", "codex is not on PATH\n")
        finish(directory, EXIT_NO_CODEX)
        return EXIT_NO_CODEX
    version = codex_version(codex)
    if version:
        write_atomic(directory / "codex_version", version + "\n")
    # Bash's "$(cat prompt.txt)" in the 2026-09-26 runner dropped trailing newlines; keep that exact prompt.
    prompt = (directory / "prompt.txt").read_text(encoding="utf-8").rstrip("\n")
    (base / "empty").mkdir(exist_ok=True)
    with open(directory / "events.jsonl", "wb") as events, open(directory / "stderr.txt", "wb") as errors:
        process = subprocess.Popen(codex_argv(codex, directory, config["model"], prompt), cwd=str(base / "empty"),
                                   stdin=subprocess.DEVNULL, stdout=events, stderr=errors,
                                   pass_fds=(slot_fd, lock_fd), start_new_session=True, env=codex_env())
        try:
            code = process.wait(timeout=config["timeout_s"])
        except subprocess.TimeoutExpired:
            stop_group(process, config["kill_grace_s"])
            code = EXIT_TIMEOUT
    if limit_error(directory):
        (base / "LIMIT").touch()
        code = EXIT_LIMIT
    finish(directory, code)
    return code


def wait(base: Path, job: str, seconds: float) -> int:
    directory = job_dir(base, job)
    config = settings(base)
    end = time.monotonic() + seconds
    while not (directory / "done").exists():
        if not running(directory):
            # Never started (a refused start) or its runner died: nothing will write done.
            print("done exit=none (the job is not running)")
            return 0
        remaining = end - time.monotonic()
        if remaining <= 0:
            print("running")
            return 0
        time.sleep(min(config["wait_poll_s"], remaining))
    code = exit_code(directory)
    print(f"done exit={'none' if code is None else code}")
    return 0


def compact(text: str | None) -> str | None:
    if text is None:
        return None
    try:
        return json.dumps(json.loads(text), ensure_ascii=False, separators=(",", ":"))
    except ValueError:
        return text


def result(base: Path, job: str) -> dict:
    directory = job_dir(base, job)
    done = (directory / "done").exists()
    out = {"status": "done" if done else ("running" if running(directory) else "not_running"),
           "exit": exit_code(directory),
           "started": (read(directory / "started") or "").strip() or None,
           "finished": (read(directory / "finished") or "").strip() or None}
    usage = turn_usage(directory)
    out["usage"] = usage or {}
    out["usage_status"] = "reported" if usage is not None else "unavailable"
    out["output_text"] = compact(read(directory / "last.json"))
    stderr = read(directory / "stderr.txt")
    out["stderr_tail"] = stderr[-400:] if stderr is not None else None
    out["limit"] = limit_error(directory)
    out["limit_marker"] = (base / "LIMIT").exists()
    out["model"] = (read(directory / "model") or "").strip() or settings(base)["model"]
    out["effort"] = EFFORT
    out["codex_version"] = (read(directory / "codex_version") or "").strip() or None
    out["inputs"] = read_json(directory / "inputs.json")
    out["attempts"] = [attempt_summary(path) for path in sorted(
        (p for p in (directory / "attempts").glob("*") if p.name.isdigit()), key=lambda p: int(p.name))]
    out["quota"] = quota_summary(directory)
    return out


def attempt_summary(path: Path) -> dict:
    usage = turn_usage(path)
    return {"attempt": int(path.name), "exit": exit_code(path),
            "started": (read(path / "started") or "").strip() or None,
            "finished": (read(path / "finished") or "").strip() or None,
            "usage": usage, "usage_status": "reported" if usage is not None else "unavailable",
            "limit": limit_error(path), "inputs": read_json(path / "inputs.json")}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    explicit = None
    if argv[:1] == ["--work-dir"]:
        if len(argv) < 2:
            print("--work-dir needs a directory", file=sys.stderr)
            return EXIT_REFUSED
        explicit, argv = argv[1], argv[2:]
    elif argv and argv[0].startswith("--work-dir="):
        explicit, argv = argv[0].split("=", 1)[1], argv[1:]
    command, rest = (argv[0], argv[1:]) if argv else ("", [])
    arity = {"start": (3, 3), "wait": (1, 2), "result": (1, 1), "run": (1, 1)}
    if command not in arity or not arity[command][0] <= len(rest) <= arity[command][1]:
        print("usage: codex_call.sh [--work-dir DIR] start <job-id> <prompt-file> <schema-file> | "
              "wait <job-id> [seconds] | result <job-id>", file=sys.stderr)
        return EXIT_REFUSED
    try:
        base = resolve_work_dir(explicit)
        if command == "start":
            return start(base, *rest)
        if command == "run":
            return run(base, rest[0])
        if command == "wait":
            return wait(base, rest[0], float(rest[1]) if len(rest) > 1 else 540.0)
        print(json.dumps(result(base, rest[0])))
        return 0
    except (UsageError, ValueError, OSError) as error:
        print(f"codex_call.sh: {error}", file=sys.stderr)
        return EXIT_REFUSED


if __name__ == "__main__":
    raise SystemExit(main())
