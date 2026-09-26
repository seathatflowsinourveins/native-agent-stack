#!/usr/bin/env python3
"""GPT-6 (Codex CLI) job runner for the landscape sweep; codex_call.sh is its command-line front.

  codex_call.sh [--work-dir DIR] start  <job-id> <prompt-file> <schema-file>
  codex_call.sh [--work-dir DIR] wait   <job-id> [seconds]    default 540; prints "done exit=N" or "running"
  codex_call.sh [--work-dir DIR] result <job-id>              one JSON line: status, exit, started, finished,
                                                              usage, output_text, stderr_tail, limit,
                                                              limit_marker, model, effort, codex_version

`start` detaches one job and returns at once. The job waits for a semaphore slot (an fcntl lock on
<lock dir>/slot-<n>, held by the runner and by codex itself, so a killed runner never frees a slot early), then runs
this, in the empty directory <work-dir>/empty, bounded to 3000 s (exit 124 on timeout):

  codex --search exec --ignore-user-config --skip-git-repo-check -s read-only -m gpt-6-astra \
    -c model_reasoning_effort="max" --output-schema <job>/schema.json -o <job>/last.json --json "<prompt>" </dev/null

--ignore-user-config keeps the host's Codex config out of the lane, the sandbox is read-only, stdin is /dev/null
(background `codex exec` otherwise waits on stdin), and the effort is max. Never ultra: ultra lets Codex delegate to
sub-agents, which breaks the one-model lane. The model and slot count come from <work-dir>/staged.json (build_args.py
--gpt6-model / --slots / --lock-dir); defaults gpt-6-astra, 3 slots, <work-dir>/locks. The codex binary is the one
on PATH.

Usage limit: when Codex reports "hit your usage limit" the job ends with exit 3 and writes <work-dir>/LIMIT; while
that file exists no job starts and jobs still waiting for a slot end with exit 3, so the coordinator can stop and
notify. Only Codex's own error reports count: its stderr, and the `error` / `turn.failed` events that
`codex exec --json` prints on stdout (openai/codex rust-v0.155.1, codex-rs/exec/src/exec_events.rs and
event_processor_with_jsonl_output.rs). Model content (item.* events: messages, web results, cited pages) never
counts: on 2026-09-26 a grep of the whole event stream matched a cited README's "Usage limitation" and set the
marker falsely.

A job whose earlier attempt finished with exit 0 is not rerun ("already done"); a job that failed is cleaned and
started again, and a job that is still running is left alone ("already running").

Work dir: --work-dir, else this file's directory when build_args.py staged it there (staged.json present), else
$SWEEP_WORK_DIR. It must lie outside every git repository: Codex would otherwise load that repository's AGENTS.md
into the lane. Standard library only; Linux and macOS (Python 3.9+).
"""

from __future__ import annotations

import errno
import fcntl
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
DEFAULTS = {"slots": 3, "timeout_s": 3000.0, "wait_poll_s": 10.0, "slot_poll_s": 5.0}
LIMIT_PHRASE = re.compile(r"hit your usage limit", re.IGNORECASE)
# The prompt is one argv string, as in the 2026-09-26 runner; Linux caps one argument at 131072 bytes.
MAX_PROMPT_BYTES = 120_000
JOB_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
MODEL_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")
OUTPUTS = ("events.jsonl", "stderr.txt", "last.json", "started", "finished", "exit", "slot", "model", "codex_version",
           "done")
KILL_GRACE_S = 10
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


def limit_error(directory: Path) -> bool:
    """Codex itself reported the usage limit: in stderr, or in an `error` / `turn.failed` event."""
    if LIMIT_PHRASE.search(read(directory / "stderr.txt") or ""):
        return True
    for line in (read(directory / "events.jsonl") or "").splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if not isinstance(event, dict):
            continue
        if event.get("type") == "error":
            message = event.get("message")
        elif event.get("type") == "turn.failed" and isinstance(event.get("error"), dict):
            message = event["error"].get("message")
        else:
            continue  # item.* events carry model content: never evidence of a limit
        if isinstance(message, str) and LIMIT_PHRASE.search(message):
            return True
    return False


def codex_argv(codex: str, directory: Path, model: str, prompt: str) -> list[str]:
    return [codex, "--search", "exec", "--ignore-user-config", "--skip-git-repo-check", "-s", "read-only",
            "-m", model, "-c", f'model_reasoning_effort="{EFFORT}"',
            "--output-schema", str(directory / "schema.json"), "-o", str(directory / "last.json"), "--json", prompt]


def start(base: Path, job: str, prompt_file: str, schema_file: str) -> int:
    directory = job_dir(base, job)
    if (directory / "done").exists() and exit_code(directory) == 0:
        print(f"already done: {job}")
        return 0
    if (base / "LIMIT").exists():
        print(f"LIMIT marker present; refusing to start {job}")
        return EXIT_LIMIT
    prompt_bytes = Path(prompt_file).read_bytes()
    schema_bytes = Path(schema_file).read_bytes()
    directory.mkdir(parents=True, exist_ok=True)
    lock_fd = open_lock(directory / "job.lock")
    if not try_lock(lock_fd):
        os.close(lock_fd)
        print(f"already running: {job}")
        return 0
    try:
        for name in OUTPUTS:  # an earlier attempt that failed or died
            (directory / name).unlink(missing_ok=True)
        (directory / "prompt.txt").write_bytes(prompt_bytes)
        (directory / "schema.json").write_bytes(schema_bytes)
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
        settings(base)  # refuse a broken staged.json before detaching
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


def stop_group(process: subprocess.Popen) -> None:
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(process.pid, sig)
        except ProcessLookupError:
            return
        try:
            process.wait(timeout=KILL_GRACE_S)
            return
        except subprocess.TimeoutExpired:
            continue


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
        write_atomic(directory / "stderr.txt", "LIMIT marker present; the job did not start\n")
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
                                   pass_fds=(slot_fd, lock_fd), start_new_session=True)
        try:
            code = process.wait(timeout=config["timeout_s"])
        except subprocess.TimeoutExpired:
            stop_group(process)
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
    usage: dict[str, int] = {}
    for line in (read(directory / "events.jsonl") or "").splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict) and event.get("type") == "turn.completed" and isinstance(event.get("usage"), dict):
            for key, value in event["usage"].items():
                if isinstance(value, int) and not isinstance(value, bool):
                    usage[key] = usage.get(key, 0) + value
    out["usage"] = usage
    out["output_text"] = compact(read(directory / "last.json"))
    stderr = read(directory / "stderr.txt")
    out["stderr_tail"] = stderr[-400:] if stderr is not None else None
    out["limit"] = limit_error(directory)
    out["limit_marker"] = (base / "LIMIT").exists()
    out["model"] = (read(directory / "model") or "").strip() or settings(base)["model"]
    out["effort"] = EFFORT
    out["codex_version"] = (read(directory / "codex_version") or "").strip() or None
    return out


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
