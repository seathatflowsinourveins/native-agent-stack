#!/usr/bin/env python3
"""Run local integration checks after `tools/adoption/apply_codex_lane.py --apply`.

These checks, including --live, are local integration, not host acceptance. The JSON
retains summaries only; native events, invocation arguments and returned output are
not retained. See docs/acceptance-evidence-policy.md and the JSON evidence fields.

Static checks (no model call):
  marker        `env -C / codex debug prompt-input probe < /dev/null | grep -c 'native-agent-stack:top-rule'` is 1;
                the RTK exceptions marker is on one line too, upstream's "Prefix every shell command with" is
                there, and scripts/adoption_status.py finds RTK.md's text inline
  blind         the same render from an empty run-scoped CODEX_HOME and HOME, the way blind and sweep lanes run,
                holds no marker
  binding       `codex mcp get context-mode --json` from / and from --checkout: upstream start.mjs of the npm pin
                through ${ECO_ROOT}/bin/node, "cwd": null, env keys CONTEXT_MODE_PLATFORM, PATH and
                RTK_TELEMETRY_DISABLED, no forwarded variables; `codex mcp list --json` names context-mode once
  profile       `codex -p stack-worker debug prompt-input` carries max effort's "do not spawn sub-agents unless
                asked" and the markers; `codex -p stack-worker mcp get` shows the template's tool lists
  roles         the two role carriers under $CODEX_HOME/agents equal their pinned rows (lane.ROLE_ROWS), the
                agents folder holds exactly two *.toml files, and the live config.toml, the worker profile and the
                system layer (/etc/codex) declare no other role: counts and booleans only, no model call. There is no
                live role check here: the --live workers below run with --ephemeral, which persists no rollout, and
                the exec JSONL item of a spawn_agent call (CollabToolCallItem, codex-rs/exec/src/exec_events.rs at
                rust-v0.157.1) carries neither the child's role nor its developer text, so such a check could not
                show that a role applied. Only the child's own rollout, from a non-ephemeral run, can.
  rtk-exactness in a scratch repository whose committed big.txt is over 8 KiB: `rtk git status` exits 0,
                native `git show HEAD:big.txt` is byte-exact, and `rtk git show HEAD:big.txt` is not (the
                reason it is an exception)
Live checks (--live; each worker is a model call on the shared allowance, so scripts/codex_quota.py --gate runs
first and a reached gate refuses them):
  workers       two concurrent `codex exec -p stack-worker -m gpt-6-astra -c model_reasoning_effort="max"
                -c web_search="live" -s read-only --skip-git-repo-check` workers (every live worker carries those
                pins, since a project config outranks the profile), one started in its directory and one with -C
                from another, each asked to call ctx_execute with `pwd`: the completed mcp_tool_call item's output
                is that worker's own directory
  approval      with -p stack-worker, ai-memory's memory_query completes; the same call without the profile is
                refused ("requires approval, but approval policy is never"), the control
  rtk-worker    a worker asked to run `git status --short` and `git show HEAD:big.txt` in the scratch repository:
                its status command carries the rtk prefix, and its blob read is native (or `rtk proxy`), exits 0
                and is byte-exact
  skill-worker  a sixth worker reads one installed SKILL.md (default: first under ~/.agents/skills, or --skill-file).
                Its completed ctx_execute_file or `rtk cat` output must match the file's actual first line.
                The result names the successful route; a project-boundary refusal can fall back to the shell.
Every live check reads the `codex exec --json` item events, never the model's prose.

Exit status: 0 every check passed, 1 a check failed, 2 could not start (no codex, or the quota gate refused).
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import apply_codex_lane as lane  # noqa: E402
from scripts import adoption_status  # noqa: E402
from scripts.codex_quota import group_alive  # noqa: E402

BIG_LINES = 300  # about 15 KB: over rtk 0.50.0's roughly 8 KiB blob window, far under Codex's 1 MiB output cap
UNSET_FOR_WORKERS = ("CLAUDECODE", "CLAUDE_CODE_SESSION_ID", "CLAUDE_CODE_ENTRYPOINT", "CONTEXT_MODE_PROJECT_DIR",
                     "CLAUDE_PROJECT_DIR")
PWD_PROMPT = ('Make exactly one MCP tool call, to the context-mode server: ctx_execute with language "shell" and '
              'code "pwd". Do not run any shell command yourself. Then reply with the tool output verbatim.')
MEMORY_PROMPT = ("Make exactly one MCP tool call, to the ai-memory server: memory_query with the arguments "
                 '{"workspace": "%s", "project": "%s", "query": "codex worker lane"}. Do not run any shell '
                 "command. Then reply with one line: how many results it returned.")
# The shell tool is named: asked only for a line count, a worker may read the blob through ctx_execute instead
# (seen in the 2026-09-26 rehearsal), and then no command event carries the bytes to compare.
RTK_PROMPT = ("Use your shell tool, not an MCP tool: in the current directory run `git status --short` and then "
              "`git show HEAD:big.txt`, each as its own command. Then reply with one line: how many lines the "
              "second command printed.")
# mksglu/context-mode v1.0.169 src/server.ts: FILE_CONTENT is supplied by ctx_execute_file;
# its small successful response echoes the path and this code, then stdout. Keep the query fixed so an
# echoed/guessed answer cannot substitute for a read of the selected file.
SKILL_CODE = "print(FILE_CONTENT.splitlines()[0])"
EVIDENCE = {
    "evidence_class": "local integration check",
    "host_acceptance": False,
    "acceptance_requirements": (
        "Acceptance requires the official pinned installation and upstream commands, with retained arguments, "
        "returned output and exit statuses, and declared sanitization. This local summary does not provide them."
    ),
    "retention": {"native_events": False, "invocation_arguments": False, "returned_output": False,
                  "worker_exits": True},
    "sanitization": (
        "Summaries are not sanitized and may include local paths; keep this JSON private. "
        "Native events and full invocation/output records are omitted, not sanitized or retained."
    ),
}


class Results:
    def __init__(self):
        self.rows = []

    def add(self, name: str, ok: bool, detail: str) -> None:
        self.rows.append({"check": name, "ok": bool(ok), "detail": detail})
        print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}", flush=True)

    @property
    def ok(self) -> bool:
        return all(row["ok"] for row in self.rows)


def grep_count(text: str, needle: str) -> int:
    """`grep -c`: the number of lines that contain needle."""
    return sum(1 for line in text.splitlines() if needle in line)


def big_blob() -> bytes:
    return "".join(f"{i:04d} codex worker lane exactness fixture: a line long enough to add up\n"
                   for i in range(BIG_LINES)).encode("utf-8")


def make_repo(path: Path) -> bytes:
    """A scratch git repository whose one commit holds big.txt."""
    blob = big_blob()
    path.mkdir(parents=True)
    (path / "big.txt").write_bytes(blob)
    git = ["git", "-C", str(path), "-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false",
           "-c", "user.name=codex-lane-prove", "-c", "user.email=codex-lane-prove@example.invalid"]
    for argv in (["init", "-q"], ["add", "big.txt"], ["commit", "-q", "-m", "fixture"]):
        subprocess.run([*git, *argv], check=True, capture_output=True)
    return blob


# ---------------------------------------------------------------------------------------------------------------
# static checks

def roles_row(codex_home: Path, system_dir: Path | None = None) -> tuple[bool, str]:
    """The `roles` row: how many of the two installed role carriers equal their pinned rows (lane.ROLE_ROWS), the
    *.toml files under $CODEX_HOME/agents, the [agents.<name>] tables of the live config.toml and worker profile,
    and the roles of the system layer (/etc/codex). It passes only with 2/2, 2, 0 and 0: exactly the two carriers,
    installed by discovery, with nothing else that Codex would load as a role in any arm. Counts and booleans only;
    no name, path or content."""
    pins, agents = lane.role_pins(), codex_home / "agents"
    equal = 0
    if lane.path_kind(agents) == "dir":
        for name in lane.ROLE_FILES:
            try:
                equal += lane.path_kind(agents / name) == "file" and lane.sha256_file(agents / name) == pins[name]
            except OSError:
                pass
    count = lane.agents_toml_count(agents)
    tables = lane.live_role_tables(codex_home)
    system = lane.system_role_count(system_dir)
    expected = len(lane.ROLE_FILES)
    shown = ["unreadable" if value is None else value for value in (count, tables, system)]
    ok = equal == expected and count == expected and tables == 0 and system == 0
    return ok, (f"installed {equal}/{expected} equal to the pinned rows; *.toml under agents {shown[0]}; "
                f"role tables {shown[1]}; system roles {shown[2]}")


def static_checks(codex: str, codex_home: Path, eco_root: str, checkout: Path, repo: Path, blob: bytes,
                  results: Results) -> None:
    env = lane.codex_env(codex_home)
    got = lane.run_codex(codex, ["debug", "prompt-input", "probe"], env, "/")
    top, exceptions = grep_count(got.stdout, lane.TOP_RULE_MARKER), grep_count(got.stdout, lane.EXCEPTIONS_MARKER)
    prefix = grep_count(got.stdout, "Prefix every shell command with")
    results.add("marker", got.returncode == 0 and top == 1 and exceptions == 1 and prefix >= 1,
                f"exit {got.returncode}; grep -c top-rule {top}, rtk-exceptions {exceptions}, "
                f"'Prefix every shell command with' {prefix}")
    inline = adoption_status.rtk_instructions_inline(codex_home)
    results.add("rtk-inline", inline is True, f"scripts/adoption_status.py rtk_instructions_inline: {inline}")

    with tempfile.TemporaryDirectory(prefix="codex-lane-blind-") as tmp:
        home = Path(tmp) / "home"
        (home / ".codex").mkdir(parents=True, mode=0o700)
        blind_env = {"HOME": str(home), "CODEX_HOME": str(home / ".codex"), "LANG": "C.UTF-8",
                     "PATH": os.pathsep.join([str(Path(codex).parent), os.defpath])}
        got = lane.run_codex(codex, ["debug", "prompt-input", "probe"], blind_env, tmp)
        top = grep_count(got.stdout, lane.TOP_RULE_MARKER)
        results.add("blind", got.returncode == 0 and top == 0,
                    f"empty run-scoped CODEX_HOME: exit {got.returncode}, top-rule lines {top}")

    for cwd in ("/", str(checkout)):
        got = lane.run_codex(codex, ["mcp", "get", "context-mode", "--json"], env, cwd)
        entry = json.loads(got.stdout) if got.returncode == 0 else {"error": lane.last_line(got.stderr)}
        problems = lane.context_mode_problems(entry, eco_root)
        listed = lane.run_codex(codex, ["mcp", "list", "--json"], env, cwd)
        names = [item.get("name") for item in json.loads(listed.stdout)] if listed.returncode == 0 else []
        count = names.count("context-mode")
        if count != 1:
            problems.append(f"codex mcp list names context-mode {count} times")
        transport = entry.get("transport") or {}
        results.add(f"binding from {cwd}", not problems,
                    "; ".join(problems) or f"cwd {transport.get('cwd')}, command {transport.get('command')}, "
                    f"args {transport.get('args')}, env keys {sorted(transport.get('env') or {})}, listed once")

    found = lane.readbacks(codex, env, None, Path("/"))
    problems = lane.check_readbacks(found, eco_root)
    results.add("profile", not problems, "; ".join(problems) or
                f"-p {lane.PROFILE_NAME}: {found['prompt_input_profile']}; servers {found['profile_servers']}")
    ok, detail = roles_row(codex_home)
    results.add("roles", ok, detail)

    rtk = shutil.which("rtk")
    if not rtk:
        results.add("rtk-exactness", False, "rtk is not on PATH")
        return
    rtk_env = {**os.environ, "RTK_TELEMETRY_DISABLED": "1"}
    status = subprocess.run([rtk, "git", "status"], cwd=repo, env=rtk_env, capture_output=True, check=False)
    native = subprocess.run(["git", "show", "HEAD:big.txt"], cwd=repo, capture_output=True, check=False)
    through = subprocess.run([rtk, "git", "show", "HEAD:big.txt"], cwd=repo, env=rtk_env, capture_output=True,
                             check=False)
    results.add("rtk-exactness", status.returncode == 0 and native.stdout == blob and through.stdout != blob,
                f"rtk git status exit {status.returncode}; git show HEAD:big.txt {len(native.stdout)} of "
                f"{len(blob)} bytes, byte-exact {native.stdout == blob}; rtk git show {len(through.stdout)} bytes, "
                f"byte-exact {through.stdout == blob}")


# ---------------------------------------------------------------------------------------------------------------
# live checks

def worker_env(codex_home: Path) -> dict:
    env = {key: value for key, value in os.environ.items() if key not in UNSET_FOR_WORKERS}
    env["CODEX_HOME"] = str(codex_home)
    return env


def exec_argv(codex: str, prompt: str, profile: bool, extra: list[str] | None = None) -> list[str]:
    """A worker exactly as the lane starts one: the profile when asked for, and always the pinned model, effort and
    web search (lane.worker_pins), which a project config could otherwise override."""
    return [codex, "exec", *(["-p", lane.PROFILE_NAME] if profile else []), *lane.worker_pins(), "-s", "read-only",
            "--skip-git-repo-check", "--ephemeral", "--json", *(extra or []), prompt]


def run_workers(specs: list[dict], timeout: float) -> list[dict]:
    """Start every spec at once, each in its own process group with stdin from /dev/null, and collect its
    events. When the deadline passes, every group still running is killed; its events so far are kept."""
    running, results = [], []
    cleanup_errors = {}
    with contextlib.ExitStack() as handles:
        try:
            for spec in specs:
                out = handles.enter_context(tempfile.TemporaryFile())
                err = handles.enter_context(tempfile.TemporaryFile())
                proc = subprocess.Popen(spec["argv"], cwd=spec["cwd"], env=spec["env"], stdin=subprocess.DEVNULL,
                                        stdout=out, stderr=err, start_new_session=True)
                running.append((spec, proc, out, err, time.monotonic()))
            deadline = time.monotonic() + timeout
            for spec, proc, out, err, started in running:
                try:
                    proc.wait(timeout=max(0.0, deadline - time.monotonic()))
                    timed_out = False
                except subprocess.TimeoutExpired:
                    timed_out = True
                results.append((spec, proc, out, err, started, timed_out))
        finally:
            for _, proc, *_ in running:  # also clean earlier launches on failure or cancellation
                # scripts/codex_quota.py::AppServer.close: a group can outlive its leader,
                # including when that leader exits promptly on TERM but a descendant ignores it.
                for sig in (signal.SIGTERM, signal.SIGKILL):
                    if proc.poll() is not None and not group_alive(proc.pid):
                        break
                    try:
                        os.killpg(proc.pid, sig)
                    except ProcessLookupError:
                        pass
                    end = time.monotonic() + 5.0
                    while time.monotonic() < end and not (proc.poll() is not None and not group_alive(proc.pid)):
                        time.sleep(0.05)
                if proc.poll() is None:
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        cleanup_errors[proc.pid] = "TimeoutExpired: worker not reaped after SIGKILL and a 5s wait"
        collected = []
        for spec, proc, out, err, started, timed_out in results:
            out.seek(0)
            err.seek(0)
            events = []
            for line in out.read().decode("utf-8", "replace").splitlines():
                try:
                    events.append(json.loads(line))
                except ValueError:
                    continue
            collected.append({"name": spec["name"], "exit": proc.returncode, "timed_out": timed_out,
                              "cleanup_error": cleanup_errors.get(proc.pid),
                              "seconds": round(time.monotonic() - started, 1), "events": events,
                              "stderr_tail": err.read().decode("utf-8", "replace")[-400:]})
        return collected


def completed_items(events: list[dict], kind: str) -> list[dict]:
    return [event["item"] for event in events
            if event.get("type") == "item.completed" and (event.get("item") or {}).get("type") == kind]


def mcp_calls(events: list[dict], server: str, tool: str) -> list[dict]:
    return [item for item in completed_items(events, "mcp_tool_call")
            if item.get("server") == server and item.get("tool") == tool]


def result_text(item: dict) -> str:
    content = ((item.get("result") or {}).get("content")) or []
    return "".join(part.get("text", "") for part in content if isinstance(part, dict))


def usage(events: list[dict]) -> dict | None:
    """The turn.completed usage counters as Codex reports them; separate counters, never summed here."""
    for event in reversed(events):
        if event.get("type") == "turn.completed":
            return event.get("usage")
    return None


def pwd_verdict(run: dict, own: str, other: str) -> tuple[bool, str]:
    if run["timed_out"] or run["exit"] != 0:
        return False, f"worker exit {run['exit']}, timed out {run['timed_out']}"
    calls = mcp_calls(run["events"], "context-mode", "ctx_execute")
    if not calls:
        return False, f"no completed context-mode ctx_execute item (exit {run['exit']}, timed out {run['timed_out']})"
    call = calls[0]
    arguments = call.get("arguments") or {}
    code = (arguments.get("code") or "").strip()
    # PWD_PROMPT and the captured pwd fixtures query the inherited directory directly.
    # Full matches exclude echoes, comments and an explicit cd that would defeat the probe.
    queries_pwd = (arguments.get("language") == "shell"
                   and re.fullmatch(r"(?:rtk\s+(?:proxy\s+)?)?pwd", code) is not None) or (
                       arguments.get("language") == "javascript"
                       and re.fullmatch(r"console\.log\(\s*process\.cwd\(\s*\)\s*\)\s*;?", code) is not None)
    queries_pwd = queries_pwd and "cwd" not in arguments
    lines = [line.strip() for line in result_text(call).splitlines() if line.strip()]
    printed = lines[-1] if lines else ""
    ok = queries_pwd and call.get("status") == "completed" and printed == own and other not in result_text(call)
    return ok, f"status {call.get('status')}, direct pwd query {queries_pwd}, pwd printed {printed}"


def approval_verdict(run: dict, expect_refusal: bool) -> tuple[bool, str]:
    if run["timed_out"] or run["exit"] != 0:
        return False, f"worker exit {run['exit']}, timed out {run['timed_out']}"
    calls = mcp_calls(run["events"], "ai-memory", "memory_query")
    if not calls:
        return False, f"no completed ai-memory memory_query item (exit {run['exit']}, timed out {run['timed_out']})"
    call = calls[0]
    error = ((call.get("error") or {}).get("message")) or ""
    refused = "approval policy is never" in error or "approval policy is never" in result_text(call)
    if expect_refusal:
        return refused, f"status {call.get('status')}, refused for approval {refused}"
    return call.get("status") == "completed" and not refused, f"status {call.get('status')}, error {error[:120]!r}"


def git_operation(command: str) -> tuple[str, str] | None:
    """Recognize the probe's argv, using CPython shlex's POSIX/comment handling.

    Codex wraps shell commands in `bash -lc`. Accept that wrapper and an optional
    `cd DIR &&` prefix; other compound commands are outside this probe's contract.
    Never search inside an echo argument, a comment or an unexecuted shell string.
    """
    def tokens(source: str) -> list[str]:
        lexer = shlex.shlex(source, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        return list(lexer)

    try:
        argv = tokens(command)
        if (len(argv) == 3 and Path(argv[0]).name in {"sh", "bash", "dash", "zsh"}
                and argv[1] in {"-c", "-lc"}):
            argv = tokens(argv[2])
    except ValueError:
        return None
    if len(argv) > 3 and argv[0] == "cd" and argv[2] == "&&":
        argv = argv[3:]
    wrapper = "native"
    if argv and Path(argv[0]).name == "rtk":
        wrapper, argv = "rtk", argv[1:]
        if argv[:1] == ["proxy"]:
            wrapper, argv = "proxy", argv[1:]
    if not argv or Path(argv[0]).name != "git":
        return None
    argv = argv[1:]
    while len(argv) >= 2 and argv[0] == "-C":
        argv = argv[2:]
    if argv in (["status"], ["status", "--short"]):
        return "status", wrapper
    if argv == ["show", "HEAD:big.txt"]:
        return "show", wrapper
    return None


def rtk_verdict(run: dict, blob: bytes) -> tuple[bool, str]:
    if run["timed_out"] or run["exit"] != 0:
        return False, f"worker exit {run['exit']}, timed out {run['timed_out']}"
    commands = completed_items(run["events"], "command_execution")
    parsed = [(c, git_operation(c.get("command", ""))) for c in commands]
    status = [(c, op) for c, op in parsed if op and op[0] == "status"]
    shows = [(c, op) for c, op in parsed if op and op[0] == "show"]
    if not status or not shows:
        return False, f"commands seen: {[c.get('command') for c in commands]}"
    prefixed = [c for c, op in status if op[1] == "rtk"]
    status_ok = any(c.get("exit_code") == 0 for c in prefixed)
    show, operation = shows[-1]
    raw = operation[1] in {"native", "proxy"}
    output = (show.get("aggregated_output") or "").replace("\r\n", "\n")
    exact = output.encode("utf-8") == blob
    ok = status_ok and raw and show.get("exit_code") == 0 and exact
    return ok, (f"status command rtk-prefixed {bool(prefixed)}, exit 0 {status_ok}; "
                f"blob read {show.get('command')!r}: raw {raw}, "
                f"exit {show.get('exit_code')}, {len(output.encode('utf-8'))} of {len(blob)} bytes, byte-exact {exact}")


def skill_cat_command(command: str, skill: Path) -> bool:
    """Recognize a direct rtk cat read, using the CPython shlex POSIX parsing pattern
    of git_operation. Refuse compound commands, echoes and different files.
    Source: https://docs.python.org/3.12/library/shlex.html#improved-compatibility-with-shells
    """
    def tokens(source: str) -> list[str]:
        lexer = shlex.shlex(source, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        return list(lexer)

    try:
        argv = tokens(command)
        if (len(argv) == 3 and Path(argv[0]).name in {"sh", "bash", "dash", "zsh"}
                and argv[1] in {"-c", "-lc"}):
            argv = tokens(argv[2])
    except ValueError:
        return False
    if not argv or Path(argv[0]).name != "rtk":
        return False
    return argv[1:] in (["cat", str(skill)], ["cat", "--", str(skill)])


def skill_verdict(run: dict, skill: Path) -> tuple[bool, str]:
    """Check native tool output against the installed file, never model prose.

    Sources: openai/codex rust-v0.157.1 codex-rs/exec/src/exec_events.rs
    (item.completed, CommandExecutionItem, McpToolCallItem); mksglu/context-mode
    v1.0.169 src/server.ts L2215-2219 (path/code echo plus stdout) and
    src/security.ts::evaluateProjectContainment (#852). A refused MCP read may
    be followed by the ordinary Codex shell read; no permissions are changed.
    """
    if run["timed_out"] or run["exit"] != 0:
        return False, f"route none; worker exit {run['exit']}, timed out {run['timed_out']}"
    try:
        with skill.open(encoding="utf-8") as stream:
            first = stream.readline()
    except (OSError, UnicodeError):
        return False, "route none; selected SKILL.md is not readable"
    if not first:
        return False, "route none; selected SKILL.md is empty"
    expected = first.rstrip("\r\n")
    for item in mcp_calls(run["events"], "context-mode", "ctx_execute_file"):
        args = item.get("arguments") or {}
        direct = (args.get("path") == str(skill) and args.get("language") == "python"
                  and args.get("code") == SKILL_CODE)
        if not direct or item.get("status") != "completed" or item.get("error"):
            continue
        output = result_text(item).replace("\r\n", "\n")
        output = output.removeprefix(f"path={skill}\n")
        output = output.removeprefix(f"```python\n{SKILL_CODE}\n```\n\n")
        if output == expected + "\n" or (expected and output == expected):
            return True, "route context-mode ctx_execute_file; first line exact True"
    for item in completed_items(run["events"], "command_execution"):
        if (item.get("status") != "completed" or item.get("exit_code") != 0
                or not skill_cat_command(item.get("command", ""), skill)):
            continue
        lines = (item.get("aggregated_output") or "").splitlines()
        if lines and lines[0] == expected:
            return True, "route shell (rtk cat); first line exact True"
    return False, "route none; no successful direct read returned the selected SKILL.md first line"


def skill_prompt(skill: Path) -> str:
    """Request a native file read without supplying the expected first line.

    Codex's user skill directory: https://developers.openai.com/codex/skills/
    Shell fallback follows rtk-ai/rtk v0.50.0 hooks/rtk-awareness-full.md and
    context-mode v1.0.169's project containment policy, not a permission override.
    """
    return (f"Read the installed skill file {str(skill)!r}. Prefer the context-mode tool ctx_execute_file with "
            f"path {str(skill)!r}, language python, and exactly this code: {SKILL_CODE}. "
            "If context-mode refuses the file because it is outside the project directory, use your shell tool "
            f"to run this single command instead: {shlex.join(['rtk', 'cat', str(skill)])}. "
            "For shell reads, use only rtk cat with that path (optionally put -- before the path). "
            "Do not change any configuration or permissions. "
            "Then reply with the file's first line. Do not guess it.")


def live_checks(codex: str, codex_home: Path, scratch: Path, repo: Path, blob: bytes, args: argparse.Namespace,
                results: Results) -> list[dict]:
    env = worker_env(codex_home)
    one, two, neutral = scratch / "worker-one", scratch / "worker-two", scratch / "neutral"
    for path in (one, two, neutral):
        path.mkdir()
    one, two = str(one.resolve()), str(two.resolve())
    runs = run_workers([
        {"name": "worker-one (cwd)", "argv": exec_argv(codex, PWD_PROMPT, True), "cwd": one, "env": env},
        {"name": "worker-two (-C)", "argv": exec_argv(codex, PWD_PROMPT, True, ["-C", two]), "cwd": str(neutral),
         "env": env},
    ], args.timeout)
    for run, own, other in ((runs[0], one, two), (runs[1], two, one)):
        ok, detail = pwd_verdict(run, own, other)
        results.add(f"workers {run['name']}", ok, detail)
    memory = MEMORY_PROMPT % (args.memory_workspace, args.memory_project)
    more = run_workers([
        {"name": "approval (profile)", "argv": exec_argv(codex, memory, True), "cwd": str(neutral), "env": env},
        {"name": "approval control (no profile)", "argv": exec_argv(codex, memory, False), "cwd": str(neutral),
         "env": env},
        {"name": "rtk-worker", "argv": exec_argv(codex, RTK_PROMPT, True), "cwd": str(repo), "env": env},
    ], args.timeout)
    ok, detail = approval_verdict(more[0], expect_refusal=False)
    results.add("approval with the profile", ok, detail)
    ok, detail = approval_verdict(more[1], expect_refusal=True)
    results.add("approval control without the profile", ok, detail)
    ok, detail = rtk_verdict(more[2], blob)
    results.add("rtk-worker", ok, detail)
    # Official Codex skill discovery includes ~/.agents/skills. Use a host file,
    # not an authored fixture or a first line supplied to the worker as an answer.
    skill = (Path(args.skill_file).expanduser().absolute() if args.skill_file else
             next((p for p in sorted((Path.home() / ".agents/skills").glob("*/SKILL.md")) if p.is_file()), None))
    if skill is None or skill.name != "SKILL.md" or not skill.is_file():
        results.add("skill-worker", False, "route none; no installed SKILL.md found (or invalid --skill-file)")
    else:
        skill_runs = run_workers([
            {"name": "skill-worker", "argv": exec_argv(codex, skill_prompt(skill), True),
             "cwd": str(neutral), "env": env},
        ], args.timeout)
        ok, detail = skill_verdict(skill_runs[0], skill)
        results.add("skill-worker", ok, detail)
        more.extend(skill_runs)
    return [{key: run[key] for key in ("name", "exit", "timed_out", "seconds", "cleanup_error")}
            | {"usage": usage(run["events"])}
            for run in runs + more]


def quota_gate(percent: float) -> tuple[bool, str]:
    got = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/codex_quota.py"), "--json", "--gate",
                          str(percent)], capture_output=True, text=True, check=False, stdin=subprocess.DEVNULL)
    try:
        out = json.loads(got.stdout)
    except ValueError:
        out = {}
    used = out.get("used_percent")
    return got.returncode == 0, f"scripts/codex_quota.py --gate {percent}: exit {got.returncode}, used {used}%"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--codex-home", help="default: $CODEX_HOME, else ~/.codex")
    parser.add_argument("--eco-root", help="default: ~/.local/share/codex-ecosystem")
    parser.add_argument("--checkout", default=str(Path.home() / "code/native-agent-stack"),
                        help="the second directory for the binding read-back (default: ~/code/native-agent-stack)")
    parser.add_argument("--codex", help="default: codex on PATH")
    parser.add_argument("--live", action="store_true", help="also run the worker checks (model calls)")
    parser.add_argument("--quota-gate", type=float, default=90.0, metavar="PERCENT",
                        help="--live refuses when a usage window is at or above PERCENT (default 90)")
    parser.add_argument("--timeout", type=float, default=900.0, help="seconds per batch of live workers")
    parser.add_argument("--memory-workspace", default="local", help="ai-memory workspace for the approval check")
    parser.add_argument("--memory-project", default="native-agent-stack", help="ai-memory project for it")
    parser.add_argument("--skill-file", metavar="SKILL.md",
                        help="installed skill for --live (default: first ~/.agents/skills/*/SKILL.md)")
    parser.add_argument("--json", metavar="FILE", help="also write the results as JSON")
    args = parser.parse_args(argv)
    codex = args.codex or shutil.which("codex")
    if not codex:
        print("cannot start: no codex executable on PATH")
        return 2
    codex_home = Path(args.codex_home or os.environ.get("CODEX_HOME") or Path.home() / ".codex").expanduser()
    eco_root = str(Path(args.eco_root or Path.home() / ".local/share/codex-ecosystem").expanduser())
    results = Results()
    runs = []
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with tempfile.TemporaryDirectory(prefix="codex-lane-prove-") as tmp:
        scratch = Path(tmp)
        repo = scratch / "repo"
        blob = make_repo(repo)
        static_checks(codex, codex_home, eco_root, Path(args.checkout).expanduser(), repo, blob, results)
        if args.live:
            allowed, detail = quota_gate(args.quota_gate)
            print(f"{'quota gate open' if allowed else 'quota gate closed'}: {detail}", flush=True)
            if not allowed:
                return 2
            runs = live_checks(codex, codex_home, scratch, repo, blob, args, results)
    failed = [row["check"] for row in results.rows if not row["ok"]]
    print(f"result: {'PASS' if not failed else 'FAIL'} ({len(results.rows) - len(failed)} pass, {len(failed)} fail)")
    if args.json:
        Path(args.json).write_text(json.dumps({**EVIDENCE, "started_utc": started, "codex_home": str(codex_home),
                                               "checks": results.rows, "live_runs": runs}, indent=2) + "\n",
                                   encoding="utf-8")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
