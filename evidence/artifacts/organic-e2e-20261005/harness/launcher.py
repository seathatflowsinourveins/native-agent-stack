#!/usr/bin/env python3
"""promptfoo exec: launcher for one trial (§4.1 launcher contract). Thin: no scheduling, no retries, no deletion.

promptfoo's ScriptCompletionProvider runs `execFile(cmd, [...args, prompt, JSON(options), JSON(context)])` with
cwd = config.basePath. The shim <trial_root>/bin/<cell code> execs <trial_root>/bin/l.py, which imports this file from
the run root's frozen harness, with the opaque cell code first. Every argv on the way (shim, launcher, promptfoo, block,
pilot) holds only neutral paths, opaque codes and refs, so a process listing names no item, cell, arm or experiment;
the launcher lints every ancestor's argv before it starts a client (R2 (f)).

Steps (numbering as in §4.1): read argv; trial_id = uuid4; pre-launch ledger row; extract the hashed fixture to
NEUTRAL_ROOT/<8 hex>/ and build the per-trial settings file (Claude) or CODEX_HOME clone (Codex); refuse an organic
trial while the routing-file registry is unreviewed; Claude takes the shared lock on a file descriptor and, inside it,
checks the session cap (14 per run) and reads the meter; the S7 before-snapshot is taken after the lock; the native
line runs from bash -lc under timeout in a clean login environment; a Claude stream is tailed for rate_limit_event (the
prior applies to every trial's first in-stream reading) and killed on the §9.1 thresholds; the run's completion policy
decides what a result event before T means; after exit the fixture is hash-manifested, ./draft/ is copied to the run
root, nothing is deleted; exactly one JSON line is printed and the exit status is always 0, so promptfoo can never
relaunch a paid session.
"""
from __future__ import annotations

import fcntl
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import time
import traceback
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from common import (CLAUDE_LOCK, CLAUDE_SESSION_CAP, KILL_AFTER, KILL_FIVE_HOUR, KILL_FIVE_HOUR_RISE, KILL_SEVEN_DAY,  # noqa: E402
                    LANE, LOCK_WAIT_S, POST_RESULT_GRACE_S, PRIOR_FIVE_HOUR, PRIOR_SEVEN_DAY, T_SECONDS, append_jsonl,
                    clean_login_env, gateway_build, load_json, manifest_digest, newest_meter_reading, prior_allows,
                    rate_limit_readings, read_jsonl, s7_persistent_change, sha256_bytes, sha256_file, stable_s7_snapshot,
                    stop_flag_names, trial_dir, tree_manifest, utc_now, write_json)

RATE_LIMIT_WORDS = ("rate limit", "rate_limit", "429", "usage limit", "too many requests", "quota")
# Kill reasons that end a trial at or above a §9.1 window threshold: the client's remaining tests wait for the next
# window (DEFER.<client>, cleared by pilot.py on resume once the meter allows), never consumed as censored.
DEFER_REASONS = ("meter_kill_five_hour", "meter_kill_seven_day", "meter_prior_first_event")


class Censored(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def run_root() -> Path:
    return HERE.parent


def ledger(root: Path, row: dict) -> None:
    append_jsonl(root / "ledger.jsonl", row)


def iso_ms(stamp: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(stamp)) + f".{int((stamp % 1) * 1000):03d}Z"


def completion_policy(cfg: dict) -> dict:
    """The run's Claude completion policy (run.json claude_completion). censor-at-T is the protocol as written (§9.1:
    T = 900 s censors); complete-at-result counts a result event before T as completion and ends the process group
    after a grace. Either one, and any T other than 900 s, is set at stage 1 with the CC amendment it rests on."""
    raw = cfg.get("claude_completion") or {}
    return {"policy": raw.get("policy") or "censor-at-T", "grace_s": int(raw.get("grace_s") or POST_RESULT_GRACE_S),
            "t_seconds": int(raw.get("t_seconds") or T_SECONDS), "amendment": raw.get("amendment")}


# ---------------------------------------------------------------------------------------------------------------------
# Process-tree watcher: nested claude or codex sessions (§8.4).

def _proc_table() -> dict[int, tuple[int, str, list[str]]]:
    table = {}
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        pid = int(entry)
        try:
            stat = Path(f"/proc/{pid}/stat").read_text()
            ppid = int(stat.rsplit(")", 1)[1].split()[1])
            exe = os.path.realpath(f"/proc/{pid}/exe")
            argv = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
            table[pid] = (ppid, exe, [a.decode(errors="replace")[:64] for a in argv if a][:32])
        except (OSError, IndexError, ValueError):
            continue
    return table


def descendants(root_pid: int) -> list[tuple[int, int, str, list[str]]]:
    table = _proc_table()
    children = {}
    for pid, (ppid, _, _) in table.items():
        children.setdefault(ppid, []).append(pid)
    out, stack = [], [(root_pid, 0)]
    while stack:
        pid, depth = stack.pop()
        for child in children.get(pid, []):
            ppid, exe, argv = table[child]
            out.append((child, depth + 1, exe, argv))
            stack.append((child, depth + 1))
    return out


SESSION_SUBCOMMANDS = {"exec", "e", "app-server", "review", "resume", "mcp-server", "proto", "fork"}
# Claude Code's native binary is multi-call: run under argv[0] bfs, ugrep or rg it is the embedded find, grep or
# ripgrep that its Bash, Glob and Grep tools use (observed on 2.1.290: `exec -a bfs <binary> DIR -type f` lists files,
# `exec -a ugrep <binary> --version` prints ugrep 7.8.4, `exec -a rg <binary> --version` prints ripgrep 14.1.1). The
# smoke-20261005f claude-native trial was killed as nested when the model ran `find / -xdev -type f ...`: the bfs
# process's `-type` passed the short-flag test below.
_VERSION_NAME = re.compile(r"\d+\.\d+\.\d+")


def _claude_like_argv0(argv: list[str], claude_bin: str) -> bool:
    """argv[0] names the client itself (`claude` from PATH, the versions file the launcher runs, or that file by any
    version name), never an embedded tool name such as bfs, ugrep or rg."""
    name = os.path.basename(argv[0]) if argv else ""
    return name in ("claude", os.path.basename(claude_bin)) or bool(_VERSION_NAME.fullmatch(name))


def _claude_session_argv(argv: list[str]) -> bool:
    """A claude process runs a session only in print mode here: -p, --print or a short-flag cluster holding p. A hook or
    plugin calling `claude --version` (the ecosystem wrapper resolves to the same binary) is not a session."""
    for arg in argv[1:]:
        if arg == "--":
            break
        if arg in ("-p", "--print") or arg.startswith("--print=") or (re.fullmatch(r"-[A-Za-z]+", arg) and "p" in arg[1:]):
            return True
    return False


def _is_claude_exe(exe: str, claude_bin: str) -> bool:
    """The trial's Claude binary or another version beside it (the native installer updates in place, so a nested
    `claude -p` started after an update runs a newer file in the same versions directory)."""
    return exe == claude_bin or (os.path.dirname(exe) == os.path.dirname(claude_bin) and bool(_VERSION_NAME.fullmatch(os.path.basename(exe))))


def _is_codex_exe(exe: str, codex_bin: str) -> bool:
    return exe == codex_bin or os.path.basename(exe) == "codex"


def nested_clients(root_pid: int, claude_bin: str, codex_bin: str) -> tuple[list[dict], list[str]]:
    """Client sessions below the trial's own client. The trial client is the shallowest claude or codex process; a
    deeper claude process whose argv[0] names the client and that runs in print mode, or a deeper codex process running
    a session subcommand, is nested. The Claude binary run as an embedded tool (argv[0] bfs, ugrep, rg) and Codex's
    sandbox helper (its own binary without a session subcommand) are not nested."""
    procs = descendants(root_pid)
    clients = [p for p in procs if _is_claude_exe(p[2], claude_bin) or _is_codex_exe(p[2], codex_bin)]
    seen_exes = sorted({os.path.basename(p[2]) for p in procs})
    if not clients:
        return [], seen_exes
    top_depth = min(p[1] for p in clients)
    top = [p for p in clients if p[1] == top_depth][:1]
    nested = []
    for pid, depth, exe, argv in clients:
        if top and pid == top[0][0]:
            continue
        if _is_claude_exe(exe, claude_bin):
            if _claude_like_argv0(argv, claude_bin) and _claude_session_argv(argv):
                nested.append({"pid": pid, "binary": "claude", "argv0": os.path.basename(argv[0]) if argv else ""})
        else:
            first = next((a for a in argv[1:] if not a.startswith("-")), "")
            if first in SESSION_SUBCOMMANDS:
                nested.append({"pid": pid, "binary": "codex", "subcommand": first})
    return nested, seen_exes


# ---------------------------------------------------------------------------------------------------------------------
# R2 (f) over every argv a trial can see (finding 10). A process listing shows the trial each ancestor's argv; the
# disclosed residue is the runner's own `eval` subcommand and promptfoo's evaluationId (eval-…), which the protocol's
# runner line fixes, and the client lines' fixed parts (binary, model, the OTEL lane tag), linted separately.

_DISCLOSED = (re.compile(r"(?<![A-Za-z0-9])eval-[A-Za-z0-9:._-]+"),)


def _full_cmdline(pid: int) -> list[str]:
    try:
        return [a.decode(errors="replace") for a in Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0") if a]
    except OSError:
        return []


def _ppid(pid: int) -> int | None:
    try:
        return int(Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[1])
    except (OSError, IndexError, ValueError):
        return None


def _scrub_argv(argv: list[str], prompt: str) -> list[str]:
    """Drop what the model already sees as its own prompt (the prompt argument and the prompt-bearing fields of
    promptfoo's context JSON); mask the disclosed runner tokens."""
    out = []
    for index, arg in enumerate(argv):
        if prompt and arg == prompt:
            continue
        if arg.startswith("{"):
            try:
                value = json.loads(arg)
            except ValueError:
                value = None
            if isinstance(value, dict):
                for holder in (value, value.get("test") or {}, value.get("vars") or {}, (value.get("test") or {}).get("vars") or {}):
                    if isinstance(holder, dict):
                        holder.pop("task_text", None)
                        holder.pop("prompt", None)
                if value.get("env") == {}:
                    value.pop("env")   # promptfoo's provider-options key, empty: structure, not a word the trial reads
                arg = json.dumps(value, sort_keys=True)
        if index >= 1 and arg == "eval" and any(a.endswith("/bin/r") for a in argv[:index]):
            continue   # the runner subcommand (promptfoo eval), fixed by §4.1
        for pattern in _DISCLOSED:
            arg = pattern.sub("<disclosed>", arg)
        out.append(arg)
    return out


def ancestor_argv_lint(lex: dict, prompt: str) -> dict:
    """R2 (a), (b) and (f) over the launcher's own argv and every ancestor's, up to PID 1."""
    from suite import lint_text
    hits, chain, pid = [], [], os.getpid()
    home = str(Path.home())
    while pid and pid > 1 and len(chain) < 64:
        argv = _scrub_argv(_full_cmdline(pid), prompt)
        text = " ".join(argv).replace(home, "~")
        found = [h for h in lint_text(text, lex, launch_string=True) if h["check"] in ("a", "b", "f")]
        low = text.lower()
        excerpts = [low[max(0, low.find(h["token"]) - 40): low.find(h["token"]) + len(h["token"]) + 40]
                    for h in found if low.find(h["token"]) >= 0][:4]
        chain.append({"depth": len(chain), "argv0": os.path.basename(argv[0]) if argv else "", "hits": [h["token"] for h in found],
                      "excerpts": excerpts})
        hits += found
        pid = _ppid(pid)
    return {"processes": len(chain), "hits": sorted({h["token"] for h in hits}), "chain": chain}


def host_argv_exposure(lex: dict, own_pids: set[int]) -> dict:
    """Covariate, not a gate: how many other processes of this user show an experiment or task word in their argv."""
    from suite import _word_hit
    words = list(lex.get("experiment_words", [])) + list(lex.get("task_words", []))
    uid, counts, procs = os.getuid(), {}, 0
    for entry in os.listdir("/proc"):
        if not entry.isdigit() or int(entry) in own_pids:
            continue
        try:
            if os.stat(f"/proc/{entry}").st_uid != uid:
                continue
        except OSError:
            continue
        text = " ".join(_scrub_argv(_full_cmdline(int(entry)), "")).lower()
        found = [w for w in words if _word_hit(text, w)]
        if found:
            procs += 1
            for word in found:
                counts[word] = counts.get(word, 0) + 1
    return {"processes_with_hits": procs, "words": dict(sorted(counts.items()))}


# ---------------------------------------------------------------------------------------------------------------------
# Command lines (§4.4).

def otel_attributes(trial_id: str, lane: str) -> str:
    return f"ecosystem.task.id={trial_id},ecosystem.lane={lane},service.instance.id={trial_id}"


def claude_line(cfg: dict, trial_id: str, prompt_file: Path, settings_file: Path, lane: str, t_seconds: int) -> str:
    q = shlex.quote
    return (f"OTEL_RESOURCE_ATTRIBUTES={q(otel_attributes(trial_id, lane))} "
            f"GH_CONFIG_DIR={q(cfg['gh_config_dir'])} "
            f"timeout --signal=TERM --kill-after={KILL_AFTER} {t_seconds} "
            f"{q(cfg['binaries']['claude']['path'])} -p \"$(cat {q(str(prompt_file))})\" --model opus --effort max "
            f"--session-id {trial_id} -n s-{trial_id.replace('-', '')[:8]} "
            f"--output-format stream-json --verbose --include-hook-events "
            f"--settings {q(str(settings_file))}")


def codex_line(cfg: dict, trial_id: str, fixture: Path, clone: Path, prompt_file: Path, last_file: Path, sandbox: str,
               effort: str, lane: str, t_seconds: int) -> str:
    q = shlex.quote
    # GH_CONFIG_DIR on the client process too (§8.3, every trial on both clients): hooks and plugins inherit it; the
    # shell tool and the MCP servers get it from the clone's config.toml.
    return (f"cd {q(str(fixture))} && CODEX_HOME={q(str(clone))} OMNIROUTE_API_KEY=local-loopback "
            f"GH_CONFIG_DIR={q(cfg['gh_config_dir'])} "
            f"OTEL_RESOURCE_ATTRIBUTES={q(otel_attributes(trial_id, lane))} "
            f"timeout --signal=TERM --kill-after={KILL_AFTER} {t_seconds} "
            f"{q(cfg['binaries']['codex']['path'])} exec --json -p omniroute -m gpt-6.1-sol "
            f"-c model_reasoning_effort={effort} -c service_tier=default "
            f"-c otel.environment={trial_id} --skip-git-repo-check -s {q(sandbox)} "
            f"-o {q(str(last_file))} - < {q(str(prompt_file))}")


def _neutral_bin(cfg: dict, name: str, fallback: str) -> str:
    """A neutral path in the run's trial root (bin/run.py, bin/run.mjs, bin/sdk), so a process listing shows no
    experiment or arm word; runs prepared before trial_root existed use the original path."""
    base = cfg.get("trial_root")
    return str(Path(base) / "bin" / name) if base and (Path(base) / "bin" / name).exists() else fallback


def claude_sdk_line(cfg: dict, trial_id: str, fixture: Path, prompt_file: Path, settings_file: Path, lane: str,
                    t_seconds: int) -> str:
    q = shlex.quote
    script = _neutral_bin(cfg, "run.py", "")
    # bin/run.py puts the SDK venv's site-packages on sys.path itself, so the base interpreter, under its neutral link
    # bin/py, runs it.
    interpreter = (cfg["binaries"].get("python_neutral") or cfg["binaries"]["python"]) if script else cfg["binaries"]["claude_sdk_python"]
    return (f"timeout --signal=TERM --kill-after={KILL_AFTER} {t_seconds} "
            f"{q(interpreter)} -B {q(script or str(HERE / 'sdk_claude.py'))} "
            f"--trial-id {trial_id} --cwd {q(str(fixture))} --prompt-file {q(str(prompt_file))} "
            f"--settings {q(str(settings_file))} --cli-path {q(cfg['binaries']['claude']['path'])} "
            f"--otel {q(otel_attributes(trial_id, lane))} --gh-config-dir {q(cfg['gh_config_dir'])}")


def codex_sdk_line(cfg: dict, trial_id: str, fixture: Path, clone: Path, prompt_file: Path, sandbox: str, effort: str,
                   lane: str, t_seconds: int) -> str:
    """CL7. The omniroute profile reaches the SDK as its config object (prepare.codex_profile_layer: the SDK cannot pass
    --profile, and codex 0.160.0 refuses `profile = ...` through --config)."""
    q = shlex.quote
    layer = (cfg.get("codex_profile_layer") or {}).get("file")
    if not layer:
        raise Censored("codex_profile_layer_missing")
    return (f"cd {q(str(fixture))} && timeout --signal=TERM --kill-after={KILL_AFTER} {t_seconds} "
            f"{q(cfg['binaries'].get('node_neutral') or cfg['binaries']['node'])} {q(_neutral_bin(cfg, 'run.mjs', str(HERE / 'sdk_codex.mjs')))} "
            f"--trial-id {trial_id} --cwd {q(str(fixture))} --prompt-file {q(str(prompt_file))} --codex-home {q(str(clone))} "
            f"--codex-path {q(cfg['binaries']['codex']['path'])} --sdk-dir {q(_neutral_bin(cfg, 'sdk', cfg['binaries']['codex_sdk_dir']))} "
            f"--sandbox {q(sandbox)} --effort {effort} --otel {q(otel_attributes(trial_id, lane))} "
            f"--gh-config-dir {q(cfg['gh_config_dir'])} --profile-config {q(layer)}")


# ---------------------------------------------------------------------------------------------------------------------

def _lock(timeout_s: int):
    fd = os.open(CLAUDE_LOCK, os.O_RDWR | os.O_CREAT, 0o600)
    deadline = time.time() + timeout_s
    while True:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return fd
        except BlockingIOError:
            if time.time() >= deadline:
                os.close(fd)
                return None
            time.sleep(2)


def _kill_group(proc: subprocess.Popen) -> None:
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def _stop_flag(root: Path, client: str) -> Path | None:
    for name in stop_flag_names(client):
        if (root / name).exists():
            return root / name
    return None


def _defer(root: Path, client: str, reason: str) -> None:
    (root / f"DEFER.{client}").write_text(f"{utc_now()} {reason}\n")


def run_client(root: Path, cfg: dict, client: str, line: str, fixture: Path, stream_path: Path, err_path: Path,
               meter_source: dict | None) -> dict:
    """Run the line and watch it. Returns rc, the kill reason (if the launcher killed it), the result event's arrival,
    meter readings and the process-tree observations."""
    env = clean_login_env()
    policy = completion_policy(cfg)
    claude_bin, codex_bin = cfg["binaries"]["claude"]["realpath"], cfg["binaries"]["codex"]["realpath"]
    with open(stream_path, "wb") as out, open(err_path, "wb") as err:
        proc = subprocess.Popen(["bash", "-lc", line], cwd=str(fixture), env=env, stdout=out, stderr=err,
                                stdin=subprocess.DEVNULL, start_new_session=True)
    started = time.time()
    offset, buffer = 0, b""
    first, last, readings = None, None, 0
    kill_reason, kill_at, nested_seen, exes = None, None, [], set()
    result_at = None
    rate_limit_error = False
    next_tree = 0.0

    def set_kill(reason: str) -> None:
        nonlocal kill_reason, kill_at
        if kill_reason is None:
            kill_reason, kill_at = reason, time.time()

    while True:
        rc = proc.poll()
        try:
            with open(stream_path, "rb") as handle:
                handle.seek(offset)
                chunk = handle.read()
            offset += len(chunk)
            buffer += chunk
        except OSError:
            chunk = b""
        lines = buffer.split(b"\n")
        buffer = lines.pop()
        for raw in lines:
            raw = raw.strip()
            if not raw.startswith(b"{"):
                continue
            try:
                event = json.loads(raw)
            except ValueError:
                continue
            if client == "claude":
                if event.get("type") == "result" and result_at is None:
                    result_at = time.time()
                for reading in rate_limit_readings([event]):
                    readings += 1
                    last = reading
                    five, seven = reading.get("five_hour"), reading.get("seven_day")
                    if first is None:
                        first = reading
                        # The prior applies to every trial's own first in-stream reading (G6), whatever the lock-time
                        # reading said.
                        if five is not None and seven is not None and not (five < PRIOR_FIVE_HOUR and seven < PRIOR_SEVEN_DAY):
                            set_kill("meter_prior_first_event")
                    if five is not None and five >= KILL_FIVE_HOUR:
                        set_kill("meter_kill_five_hour")
                    if seven is not None and seven >= KILL_SEVEN_DAY:
                        set_kill("meter_kill_seven_day")
                    if (five is not None and first and first.get("five_hour") is not None
                            and five - first["five_hour"] >= KILL_FIVE_HOUR_RISE):
                        set_kill("meter_kill_rise")
            else:
                kind = event.get("type")
                if kind in ("error", "turn.failed"):
                    text = json.dumps(event).lower()
                    if any(word in text for word in RATE_LIMIT_WORDS):
                        rate_limit_error = True
        if time.time() >= next_tree and rc is None:
            nested, seen = nested_clients(proc.pid, claude_bin, codex_bin)
            exes.update(seen)
            if nested:
                nested_seen.extend(nested)
                set_kill("nested_client")
            next_tree = time.time() + 2
        if (client == "claude" and policy["policy"] == "complete-at-result" and result_at is not None and rc is None
                and time.time() - result_at >= policy["grace_s"]):
            set_kill("post_result_grace")
        if kill_reason and rc is None:
            _kill_group(proc)
            rc = proc.wait()
        if rc is not None:
            break
        if time.time() - started > policy["t_seconds"] + 90:
            set_kill("wall_guard")
            _kill_group(proc)
            rc = proc.wait()
            break
        time.sleep(1)
    ended = time.time()
    if kill_reason in DEFER_REASONS:
        _defer(root, client, kill_reason)
    if rate_limit_error:
        (root / f"STOP.{client}").write_text(f"{utc_now()} rate_limit_error_in_stream\n")
    return {"rc": rc, "kill_reason": kill_reason, "kill_at": iso_ms(kill_at) if kill_at else None,
            "duration_s": round(ended - started, 1), "result_at": iso_ms(result_at) if result_at else None,
            "time_to_result_s": round(result_at - started, 1) if result_at else None,
            "post_result_s": round(ended - result_at, 1) if result_at else None,
            "result_before_kill": bool(result_at and (kill_at is None or result_at <= kill_at)),
            "meter_first": first, "meter_last": last, "meter_readings": readings, "nested": nested_seen,
            "tree_exes": sorted(exes), "rate_limit_error": rate_limit_error}


def stream_completed(client: str, stream_path: Path) -> bool:
    try:
        text = stream_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    for line in reversed(text.splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if client == "claude" and event.get("type") == "result":
            return True
        if client == "codex" and event.get("type") in ("turn.completed",):
            return True
    return False


def result_before_t(policy: dict, outcome: dict) -> bool:
    """The result event reached the stream before T. Claude Code in print mode holds its result event while a background
    task (a Workflow run) is still going and writes it when the process is terminated: smoke-20261006c's claude-native
    result reported duration_ms 575920 but arrived at 900.7 s, after the timeout's SIGTERM, so arrival time decides."""
    ttr = outcome.get("time_to_result_s")
    return ttr is not None and ttr < policy["t_seconds"]


def trial_reason(client: str, policy: dict, outcome: dict, completed: bool) -> tuple[str | None, bool]:
    """(censoring reason or None, post_result_terminated). Under complete-at-result a Claude trial whose result event
    arrived before T and before any kill counts as complete, however the process then ended (grace, T, a window kill);
    a result that arrived only at or after T (written on the timeout's SIGTERM) censors as timeout_after_result; a nested
    client always censors."""
    rc, kill = outcome["rc"], outcome["kill_reason"]
    if (client == "claude" and policy["policy"] == "complete-at-result" and outcome["result_at"]
            and outcome["result_before_kill"] and result_before_t(policy, outcome) and kill != "nested_client"):
        terminated = bool(kill) or rc in (124, 137, -9, 143, -15)
        return None, terminated
    if kill:
        return kill, False
    if rc == 124:
        return ("timeout_after_result" if outcome["result_at"] else "timeout"), False
    if rc in (137, -9, 143, -15):
        return "killed", False
    if not completed:
        return f"incomplete_stream_rc{rc}", False
    return None, False


def resolve_test(cfg: dict, cell_arg: str, context: dict) -> tuple[str, dict]:
    """(cell name, test record). The shim passes the opaque cell code and promptfoo's vars carry the opaque test ref;
    both map through run.json. A run prepared before the codes existed passes clear names and clear vars."""
    cell = (cfg.get("cell_codes") or {}).get(cell_arg, cell_arg)
    test_vars = context.get("vars") or {}
    ref = test_vars.get("ref")
    record = dict((cfg.get("tests_by_ref") or {}).get(ref) or {})
    if not record:
        record = {k: test_vars.get(k) for k in ("task_id", "instance", "arm", "cell", "sandbox", "network", "lane",
                                                  "prompt_sha256")}
    record["ref"] = ref
    if record.get("cell") and record["cell"] != cell:
        raise ValueError("test ref belongs to another cell")
    return cell, record


def launch(cell_arg: str, prompt: str, options: dict, context: dict) -> dict:
    root = run_root()
    cfg = load_json(root / "run.json")
    cell, test = resolve_test(cfg, cell_arg, context)
    cell_cfg = cfg["cells"][cell]
    client, arm, kind = cell_cfg["client"], cell_cfg["arm"], cell_cfg["kind"]
    lane = test.get("lane") or LANE
    policy = completion_policy(cfg)
    t_seconds = policy["t_seconds"]
    trial_id = str(uuid.uuid4())
    short = trial_id.replace("-", "")[:8]
    base = {"run_id": cfg["run_id"], "trial_id": trial_id, "cell": cell, "client": client, "arm": arm,
            "task": test.get("task_id"), "instance": test.get("instance"), "lane": lane, "ref": test.get("ref"),
            "test_key": test.get("test_key"), "repeatIndex": context.get("repeatIndex"), "testIdx": context.get("testIdx"),
            "evaluationId": context.get("evaluationId")}
    prompt_sha = sha256_bytes(prompt.encode())
    frozen_sha = test.get("prompt_sha256")
    ledger(root, {**base, "phase": "pre-launch", "at": utc_now(),
                  "hashes": {"fixture_tar": cfg["fixture"]["tar_sha256"], "prompt": prompt_sha, "prompt_frozen": frozen_sha,
                             "settings_template": cfg["claude_settings_sha256"].get(arm) if client == "claude" else None,
                             "clone_rules": cfg["codex_rules_sha256"] if client == "codex" else None,
                             "label_vector": cfg.get("label_vector_sha256")},
                  "client_version": cfg["binaries"][client]["version"], "model": cell_cfg.get("model"),
                  "requested_effort": cell_cfg["effort"], "tier": cell_cfg.get("tier"), "route": cell_cfg.get("route"),
                  "gateway_build": gateway_build() if client == "codex" else None, "sandbox": test.get("sandbox"),
                  "network": test.get("network"), "completion_policy": policy if client == "claude" else None})
    result = {"trial_id": trial_id, "rc": None, "censored": True, "reason": None}
    fixture = None
    lock_fd = None
    try:
        if frozen_sha and frozen_sha != prompt_sha:
            raise Censored("prompt_mismatch")
        if _stop_flag(root, client):
            raise Censored("block_stopped")
        if client == "codex" and test.get("network") not in (None, "", "off"):
            raise Censored("network_on_unsupported_in_pilot")
        registry = cfg.get("registry") or {}
        if (lane == LANE and not test.get("gate_trial") and registry.get("status") != "reviewed"
                and not registry.get("allow_provisional")):
            # Finding 9: organic trials wait for the hint reader's reviewed routing-file registry.
            raise Censored("registry_provisional")
        from fixture import extract_fixture
        fixture = extract_fixture(Path(cfg["fixture"]["tar_path"]), cfg["fixture"]["tar_sha256"])
        work = trial_dir(cfg, root)   # neutral: these paths reach the client's argv or environment
        prompt_file = work / "prompts" / f"{trial_id}.txt"
        prompt_file.parent.mkdir(parents=True, exist_ok=True)
        prompt_file.write_text(prompt, encoding="utf-8")
        trial_files = {"fixture_tar": cfg["fixture"]["tar_path"]}
        prepared = {"fixture_private": str(fixture), "session_name": f"s-{short}"}
        settings_file = clone = None
        visible = [str(fixture), f"s-{short}", str(prompt_file), str(work / "last" / f"{trial_id}.txt"), cfg["gh_config_dir"]]
        if client == "claude":
            settings_file = work / "settings" / f"{trial_id}.json"
            prepared["settings_sha256"] = write_json(settings_file, cfg["claude_settings"][arm], 0o600)
            trial_files["settings"] = str(settings_file)
            visible.append(str(settings_file))
        else:
            from arms import build_clone
            clone = work / "clones" / trial_id
            rules_text = (root / "codex-rules" / "organic-e2e.rules").read_text(encoding="utf-8")
            record = build_clone(clone, arm, Path(cfg["gh_config_dir"]), rules_text)
            prepared["clone"] = record
            trial_files["clone"] = str(clone)
            visible.append(str(clone))
            if not record["gate"]["pass"]:
                raise Censored("clone_gate")
        from suite import lint_text
        home = str(Path.home())
        lint_hits = lint_text(" ".join(v.replace(home, "~") for v in visible), cfg["lexicon"], launch_string=True)
        lint_hits = [h for h in lint_hits if h["check"] in ("a", "f")]
        prepared["lint_f_hits"] = lint_hits
        argv_lint = ancestor_argv_lint(cfg["lexicon"], prompt)
        prepared["argv_lint"] = argv_lint
        ledger(root, {**base, "phase": "prepared", "at": utc_now(), **prepared})
        if lint_hits:
            raise Censored("lint_f")
        if argv_lint["hits"]:
            raise Censored("lint_f_argv")
        meter_source = None
        if client == "claude":
            lock_fd = _lock(LOCK_WAIT_S)
            if lock_fd is None:
                _defer(root, client, "lock_timeout")
                raise Censored("lock_timeout")
            if _stop_flag(root, client):
                raise Censored("block_stopped")
            cap = int(cfg.get("claude_session_cap") or CLAUDE_SESSION_CAP)
            launched = {r.get("trial_id") for r in read_jsonl(root / "ledger.jsonl")
                        if r.get("phase") == "launched" and r.get("client") == "claude"}
            if len(launched) >= cap:
                (root / "STOP.claude").write_text(f"{utc_now()} claude session cap {cap} reached\n")
                raise Censored("claude_cap")
            meter_source = newest_meter_reading()
            allowed, why = prior_allows(meter_source)
            ledger(root, {**base, "phase": "meter", "at": utc_now(), "allowed": allowed, "why": why,
                          "claude_sessions_launched_before": len(launched), "cap": cap,
                          "reading": {k: v for k, v in (meter_source or {}).items() if k != "source_private"}})
            if not allowed:
                _defer(root, client, f"meter_prior {why}")
                raise Censored("meter_prior")
        # S7 before-snapshot after the lock wait (finding 15), so a change another lane makes while this trial waits
        # is not attributed to it; read until it holds still (another session's plugin sync can be half done).
        before, before_read = stable_s7_snapshot(trial_files)
        write_json(root / "s7" / f"{trial_id}.before.json", before, 0o600)
        (root / "raw").mkdir(exist_ok=True)
        (work / "last").mkdir(exist_ok=True)
        stream_path, err_path = root / "raw" / f"{trial_id}.stream.jsonl", root / "raw" / f"{trial_id}.err"
        sandbox = test.get("sandbox") or "read-only"
        if client == "claude" and kind == "cli":
            line = claude_line(cfg, trial_id, prompt_file, settings_file, lane, t_seconds)
        elif client == "claude" and kind == "sdk":
            line = claude_sdk_line(cfg, trial_id, fixture, prompt_file, settings_file, lane, t_seconds)
        elif client == "codex" and kind == "cli":
            line = codex_line(cfg, trial_id, fixture, clone, prompt_file, work / "last" / f"{trial_id}.txt", sandbox,
                              cell_cfg["effort"], lane, t_seconds)
        elif client == "codex" and kind == "sdk":
            line = codex_sdk_line(cfg, trial_id, fixture, clone, prompt_file, sandbox, cell_cfg["effort"], lane, t_seconds)
        else:
            raise Censored(f"unsupported_cell_kind:{kind}")
        exposure = host_argv_exposure(cfg["lexicon"], {os.getpid()})
        ledger(root, {**base, "phase": "launched", "at": utc_now(), "line_sha256": sha256_bytes(line.encode()),
                      "line_shape": line.replace(trial_id, "<trial_id>").replace(str(Path.home()), "~"),
                      "host_argv_exposure_at_launch": exposure})
        outcome = run_client(root, cfg, client, line, fixture, stream_path, err_path, meter_source)
        completed = stream_completed(client, stream_path)
        reason, post_result_terminated = trial_reason(client, policy, outcome, completed)
        result.update({"rc": outcome["rc"], "censored": reason is not None, "reason": reason})
        exit_row = {**base, "phase": "exit", **result,
                    "completed_stream": completed, "duration_s": outcome["duration_s"],
                    "completion_policy": policy["policy"] if client == "claude" else None, "t_seconds": t_seconds,
                    "terminated_by": outcome["kill_reason"], "kill_at": outcome["kill_at"],
                    "result_at": outcome["result_at"], "time_to_result_s": outcome["time_to_result_s"],
                    "post_result_s": outcome["post_result_s"], "post_result_terminated": post_result_terminated,
                    "meter_first": outcome["meter_first"], "meter_last": outcome["meter_last"],
                    "meter_readings": outcome["meter_readings"], "nested_clients": outcome["nested"],
                    "tree_exes": outcome["tree_exes"], "rate_limit_error": outcome["rate_limit_error"],
                    "stream_sha256": sha256_file(stream_path), "stream_bytes": stream_path.stat().st_size}
        judged = None
        try:
            # A launched trial always gets its exit row: a failure here is recorded, and G4 then fails for want of the
            # host comparison instead of the trial vanishing from the ledger.
            after, after_read = stable_s7_snapshot(trial_files)
            write_json(root / "s7" / f"{trial_id}.after.json", after, 0o600)
            judged = s7_persistent_change(load_json(cfg["s7_baseline"]), before, after)
            host_compare = judged["within"]
            fixture_manifest = tree_manifest(fixture)
            write_json(root / "manifests" / f"{trial_id}.fixture.json", fixture_manifest, 0o600)
            template_manifest = load_json(cfg["fixture"]["template_manifest_path"])
            changed = sorted(k for k in fixture_manifest if template_manifest.get(k) != fixture_manifest[k])
            removed = sorted(k for k in template_manifest if k not in fixture_manifest)
            draft_src, draft_dst = fixture / "draft", root / "draft" / trial_id
            if draft_src.exists():
                shutil.copytree(draft_src, draft_dst, symlinks=True)
            else:
                draft_dst.mkdir(parents=True, exist_ok=True)
            exit_row.update({"fixture_manifest_sha256": manifest_digest(fixture_manifest),
                             "fixture_changed": changed[:200], "fixture_changed_count": len(changed),
                             "fixture_removed": removed[:200], "fixture_removed_count": len(removed),
                             "draft_manifest_sha256": manifest_digest(tree_manifest(draft_dst)),
                             "host_s7": {k: v for k, v in host_compare.items() if k != "new_trust_paths_private"},
                             "host_s7_private": host_compare.get("new_trust_paths_private"),
                             "host_s7_vs_baseline": {k: v for k, v in judged["vs_baseline"].items() if k != "new_trust_paths_private"},
                             "host_s7_persistent_change": judged["persistent"],
                             "host_s7_transient_before": judged["transient_before"],
                             "s7_reads": {"before": before_read, "after": after_read}})
        except Exception as error:  # noqa: BLE001
            exit_row["bookkeeping_error"] = f"{type(error).__name__}: {str(error)[:300]}"
            with open(root / "launcher-errors.log", "a") as handle:
                handle.write(f"{utc_now()} {trial_id} after exit: {traceback.format_exc()}\n")
        ledger(root, {**exit_row, "at": utc_now()})
        if judged is not None and judged["persistent"]:
            vs_base = judged["vs_baseline"]
            (root / "STOP").write_text(f"{utc_now()} host exposure or trust changed during {trial_id}: "
                                       f"{vs_base['changed'][:6]} new_trust={vs_base['new_trust']} "
                                       f"within={judged['within']['changed'][:6]}\n")
        return result
    except Censored as censor:
        result.update({"censored": True, "reason": censor.reason})
        ledger(root, {**base, "phase": "exit", "at": utc_now(), **result, "launched": False,
                      "fixture_private": str(fixture) if fixture else None})
        return result
    finally:
        if lock_fd is not None:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            os.close(lock_fd)


def main(argv: list[str]) -> int:
    result = {"trial_id": None, "rc": None, "censored": True, "reason": "launcher_error"}
    try:
        if len(argv) < 5:
            raise ValueError("usage: launcher.py <cell code> <prompt> <options-json> <context-json>")
        cell, prompt, options, context = argv[1], argv[-3], json.loads(argv[-2]), json.loads(argv[-1])
        result = launch(cell, prompt, options, context)
    except Exception as error:  # noqa: BLE001 - every failure is a censored trial, never a promptfoo error
        result["reason"] = f"launcher_error:{type(error).__name__}"
        try:
            root = run_root()
            with open(root / "launcher-errors.log", "a") as handle:
                handle.write(f"{utc_now()} {traceback.format_exc()}\n")
        except OSError:
            pass
    sys.stdout.write(json.dumps(result) + "\n")
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
