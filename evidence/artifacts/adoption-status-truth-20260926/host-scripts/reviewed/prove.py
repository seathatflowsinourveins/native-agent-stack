#!/usr/bin/env python3
"""u5 E2E proof (read-only): does scripts/adoption_status.py tell this host's truth, and are the G13 hygiene fixes live?

local_integration. Every observation comes from an upstream command or native API; this script only compares them:
  * the checker itself: `scripts/adoption_status.py --profile token-efficiency --client-wiring --pinned-versions --json`
    from the checkout under test (run with Python 3.13 by prove.sh);
  * what Codex's model actually sees: `codex debug prompt-input` (no model call; hooks, plugins and MCP servers
    disabled for the probe, so no SessionStart hook or MCP server runs);
  * which hooks Codex actually runs: `codex app-server` over stdio, `initialize` then `hooks/list` (no thread, no
    write request);
  * installed versions: `codex --version`, `claude --version`, against adoption/pins-linux-x86_64.json;
  * ai-memory capture admission: `ai-memory hook --check-capture` (no spool, no server contact);
  * Worktrunk's copy plan: `wt step copy-ignored --require-include --dry-run` (no write);
  * the Prometheus series behind render.py's G1 text: anonymous loopback query API (read-only).
It prints booleans, counts and ids, never a hook command, credential or environment value. Exit 0 only when every
check passes.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path, PurePosixPath

HOME = str(Path.home())
RESULTS: list[tuple[str, bool, str]] = []


def show(text: str) -> str:
    return text.replace(HOME, "~")


def check(name: str, passed: bool, detail: str) -> None:
    RESULTS.append((name, passed, detail))
    print(f"{'PASS' if passed else 'FAIL'}  {name}: {show(detail)}", flush=True)


def run(argv, *, cwd=None, stdin_text=None, timeout=300, env=None) -> subprocess.CompletedProcess:
    return subprocess.run(argv, cwd=cwd, input=stdin_text, capture_output=True, text=True, timeout=timeout,
                          env=env, stdin=None if stdin_text is not None else subprocess.DEVNULL)


def norm(text: str) -> str:
    lines = [line for line in text.splitlines() if not line.lstrip().startswith("<!-- rtk-owned:")]
    return " ".join(" ".join(lines).split())


def runs_ai_memory_hook(command: str) -> bool:
    try:
        argv = shlex.split(command)
    except ValueError:
        return False
    return bool(argv) and PurePosixPath(argv[0]).name == "ai-memory" and "hook" in argv[1:]


def codex_home() -> Path:
    value = os.environ.get("CODEX_HOME")
    return Path(os.path.realpath(value)) if value else Path(HOME) / ".codex"


def adoption_report(checkout: Path, python: list[str]) -> dict | None:
    result = run([*python, "scripts/adoption_status.py", "--profile", "token-efficiency", "--client-wiring",
                  "--pinned-versions", "--json"], cwd=checkout, timeout=900)
    try:
        return json.loads(result.stdout)
    except ValueError:
        check("adoption_status runs", False, f"exit {result.returncode}; stderr: {result.stderr.strip()[:200]}")
        return None


def prompt_input_rtk() -> bool:
    """Whether RTK.md's text reaches the Codex model (upstream `codex debug prompt-input`)."""
    result = run(["codex", "debug", "prompt-input", "--disable", "hooks", "--disable", "plugins",
                  "-c", "mcp_servers={}", "u5 prove"], cwd="/", timeout=180)
    if result.returncode != 0:
        raise RuntimeError(f"codex debug prompt-input exited {result.returncode}")
    texts = []

    def collect(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key in ("text", "content") and isinstance(item, str):
                    texts.append(item)
                else:
                    collect(item)
        elif isinstance(value, list):
            for item in value:
                collect(item)

    collect(json.loads(result.stdout))
    rtk_path = codex_home() / "RTK.md"
    body = norm(rtk_path.read_text(encoding="utf-8")) if rtk_path.is_file() else ""
    return bool(body) and body in norm("\n".join(texts))


def codex_hooks_list(cwd: Path) -> list[dict]:
    """hooks/list from Codex's own app-server; returns the hook entries for ``cwd``."""
    env = dict(os.environ, RUST_LOG="error")
    process = subprocess.Popen(["codex", "app-server"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, cwd="/", env=env, text=True, start_new_session=True)

    def send(message):
        process.stdin.write(json.dumps(message) + "\n")
        process.stdin.flush()

    def response(request_id):
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            line = process.stdout.readline()
            if not line:
                raise RuntimeError("codex app-server closed its output")
            try:
                message = json.loads(line)
            except ValueError:
                continue
            if message.get("id") == request_id and ("result" in message or "error" in message):
                if "error" in message:
                    raise RuntimeError(f"app-server error: {message['error'].get('message')}")
                return message["result"]
        raise RuntimeError("codex app-server timed out")

    try:
        send({"id": 1, "method": "initialize",
              "params": {"clientInfo": {"name": "u5-prove", "title": None, "version": "0.1.0"}}})
        response(1)
        send({"method": "initialized"})
        send({"id": 2, "method": "hooks/list", "params": {"cwds": [str(cwd)]}})
        listed = response(2)
    finally:
        try:
            process.stdin.close()
            process.wait(timeout=15)
        except (OSError, subprocess.TimeoutExpired):
            os.killpg(process.pid, 15)
            process.wait()
    return [hook for entry in listed["data"] for hook in entry.get("hooks", [])]


def version_of(argv: list[str]) -> str | None:
    try:
        result = run(argv, cwd="/", timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    found = re.search(r"[0-9]+(?:\.[0-9]+)+", result.stdout + "\n" + result.stderr)
    return found.group() if result.returncode == 0 and found else None


def at_least(observed: str, floor: str) -> bool:
    a, b = [int(x) for x in observed.split(".")], [int(x) for x in floor.split(".")]
    width = max(len(a), len(b))
    return a + [0] * (width - len(a)) >= b + [0] * (width - len(b))


def check_capture(path: Path) -> dict:
    result = run(["ai-memory", "hook", "--event", "pre-tool-use", "--agent", "codex", "--server-url",
                  os.environ.get("AI_MEMORY_HOOK_URL", "http://127.0.0.1:49474"), "--check-capture"],
                 cwd="/", stdin_text=json.dumps({"cwd": str(path), "session_id": "u5-prove"}), timeout=60)
    try:
        return json.loads(result.stdout)
    except ValueError:
        return {}


def prometheus(query: str):
    url = "http://127.0.0.1:19090/api/v1/query?" + urllib.parse.urlencode({"query": query})
    with urllib.request.urlopen(url, timeout=20) as response:
        return json.load(response)["data"]["result"]


def git(main: Path, *args: str) -> subprocess.CompletedProcess:
    return run(["git", "--no-optional-locks", "-C", str(main), *args], timeout=60)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkout", required=True, help="checkout whose adoption_status.py and files are proven")
    parser.add_argument("--main", required=True, help="the host's primary checkout (the .worktreeinclude source)")
    parser.add_argument("--python", required=True, help="Python 3.13 command line, shell-quoted")
    parser.add_argument("--worktree", action="append", default=[], help="an enrolled worker worktree to prove")
    args = parser.parse_args()
    checkout, main_checkout = Path(args.checkout).resolve(), Path(args.main).resolve()
    python = shlex.split(args.python)
    print(f"checkout under test: {show(str(checkout))} @ {git(checkout, 'rev-parse', '--short', 'HEAD').stdout.strip()}")
    print(f"primary checkout:    {show(str(main_checkout))} @ {git(main_checkout, 'rev-parse', '--short', 'HEAD').stdout.strip()}")

    # G9: the checker against native observations.
    report = adoption_report(checkout, python)
    wiring = (report or {}).get("client_wiring") or {}
    codex = wiring.get("codex") or {}
    fixed = report is not None and "ai_memory_hook_events_trusted" in codex and "pinned_versions_match" in report
    check("G9 checker reports hook trust and a top-level pin verdict", fixed,
          "fields present" if fixed else "this checkout's adoption_status.py predates the fix")
    try:
        visible = prompt_input_rtk()
        check("G9 rtk_instructions equals what Codex's model sees", fixed and codex.get("rtk_instructions") is visible,
              f"codex debug prompt-input carries RTK.md text: {visible}; checker rtk_instructions: "
              f"{codex.get('rtk_instructions')}")
    except (RuntimeError, OSError, ValueError, subprocess.TimeoutExpired) as error:
        visible = None
        check("G9 rtk_instructions equals what Codex's model sees", False, f"native probe failed: {error}")
    try:
        hooks = [hook for hook in codex_hooks_list(checkout) if hook.get("source") == "user"
                 and runs_ai_memory_hook(hook.get("command") or "")]
        events = {hook["eventName"] for hook in hooks}
        running = {hook["eventName"] for hook in hooks if hook.get("enabled") and hook.get("trustStatus") == "trusted"}
        agree = fixed and (codex.get("ai_memory_hook_events"), codex.get("ai_memory_hook_events_trusted")) == (
            len(events), len(running))
        check("G9 hook counts equal Codex's own hooks/list", agree,
              f"hooks/list: {len(events)} ai-memory events, {len(running)} enabled and trusted; checker: "
              f"{codex.get('ai_memory_hook_events')} and {codex.get('ai_memory_hook_events_trusted')}")
    except (RuntimeError, OSError, ValueError, KeyError, subprocess.TimeoutExpired) as error:
        events = running = None
        check("G9 hook counts equal Codex's own hooks/list", False, f"native probe failed: {error}")
    native_complete_blockers = []
    if visible is False:
        native_complete_blockers.append("RTK text not model-visible")
    if events is not None and (len(running) != len(events) or not events):
        native_complete_blockers.append("ai-memory hooks not all trusted")
    if native_complete_blockers:
        check("G9 complete is false while Codex misses the practice", wiring.get("complete") is False,
              f"native: {', '.join(native_complete_blockers)}; checker complete: {wiring.get('complete')}")
    else:
        check("G9 complete agrees with the native observations", fixed and isinstance(wiring.get("complete"), bool),
              f"no native blocker; checker complete: {wiring.get('complete')} (other booleans may still be false)")
    pins = {tool["id"]: tool for tool in json.loads((checkout / "adoption/pins-linux-x86_64.json").read_text())["tools"]}
    observed = {"codex": version_of(["codex", "--version"]), "claude-code": version_of(["claude", "--version"])}
    expected_mismatch = set()
    for name, version in observed.items():
        pin = pins.get(name, {})
        floor = (pin.get("version_probe") or {}).get("match") == "minimum"
        if version is None or not pin:
            continue
        if not (at_least(version, pin["version"]) if floor else version == pin["version"]):
            expected_mismatch.add(name)
    profile = next((item for item in (report or {}).get("profiles", []) if item["id"] == "token-efficiency"), {})
    summary = profile.get("pinned_versions_summary") or {}
    reported = set(summary.get("mismatched", [])) & set(observed)
    surfaced = fixed and reported == expected_mismatch and (
        report.get("pinned_versions_match") is False if summary.get("mismatched") else True)
    check("G9 a pin mismatch surfaces at the top", surfaced,
          f"--version: codex {observed['codex']} (pin {pins.get('codex', {}).get('version')}), claude "
          f"{observed['claude-code']} (floor {pins.get('claude-code', {}).get('version')}); checker mismatched "
          f"{sorted(summary.get('mismatched', []))}, pinned_versions_match {report.get('pinned_versions_match') if report else None}")

    # G13: stack.json pin, render.py text, profile reconciliation.
    stack = {row["id"]: row for row in json.loads((checkout / "manifests/stack.json").read_text())["components"]}
    floor = pins.get("claude-code", {}).get("version")
    installed = observed["claude-code"]
    check("G13 stack.json claude-code follows the pins floor",
          stack.get("claude-code", {}).get("version") == floor and installed is not None and at_least(installed, floor),
          f"stack.json {stack.get('claude-code', {}).get('version')}, pins floor {floor}, claude --version {installed}")
    render = (checkout / "observability/native-data/render.py").read_text(encoding="utf-8")
    try:
        unscoped = prometheus('count(ecosystem_claude_code_token_usage_tokens_total{instance="unscoped"})')
        resets = prometheus("sum(resets(ecosystem_claude_code_token_usage_tokens_total[1h]))")
        native = (f"Prometheus now: {unscoped[0]['value'][1] if unscoped else 0} series with instance=unscoped, "
                  f"{resets[0]['value'][1] if resets else 0} counter resets in 1 h")
    except (OSError, ValueError, KeyError, IndexError) as error:
        native = f"Prometheus not queried ({error})"
    check("G13 render.py cites the identified G1 cause", "the cause is open" not in render and "G1" in render
          and 'instance="unscoped"' in render, native)
    test = run([*python, "-m", "unittest", "tests.test_adoption_status.TokenEfficiencyProfileTests"], cwd=checkout,
               timeout=300)
    check("G13 the 14-id profile and the 16-tool run reconcile", test.returncode == 0
          and "test_the_sixteen_subagent_tools_are_ten_profile_rows_and_six_optional_rows" in
          (checkout / "tests/test_adoption_status.py").read_text(encoding="utf-8"),
          (test.stderr.strip().splitlines() or ["no output"])[-1])

    # G13 / G5a: the capture marker reaches worker worktrees through the native recipe.
    include = git(main_checkout, "show", "HEAD:.worktreeinclude")
    ignored = git(main_checkout, "check-ignore", "-q", ".ai-memory.toml").returncode == 0
    marker = (main_checkout / ".ai-memory.toml").is_file()
    tracked_include = include.returncode == 0 and ".ai-memory.toml" in include.stdout.splitlines()
    check("G13 primary checkout carries the worktree recipe", tracked_include and ignored and marker,
          f".worktreeinclude tracked with the marker: {tracked_include}; marker ignored: {ignored}; marker present: {marker}")
    listing = git(main_checkout, "worktree", "list", "--porcelain").stdout
    worktrees = [Path(line.split(" ", 1)[1]) for line in listing.splitlines() if line.startswith("worktree ")]
    linked = [path for path in worktrees if path != main_checkout and path.is_dir()]
    outside = [path for path in linked if not str(path).startswith(HOME + "/")]
    enrolled = [path for path in linked if (path / ".ai-memory.toml").is_file()]
    admitted = [path for path in enrolled if check_capture(path).get("admits_capture") is True]
    print(f"      worktrees: {len(linked)} linked, {len(outside)} outside $HOME, {len(enrolled)} carry the marker, "
          f"{len(admitted)} of those admit capture")
    sample = next((path for path in outside if path not in enrolled), None)
    if sample is not None:
        plan = run(["wt", "-C", str(sample), "step", "copy-ignored", "--require-include", "--dry-run", "--format",
                    "json"], timeout=120)
        try:
            entries = [entry["path"] for entry in json.loads(plan.stdout).get("entries", [])]
        except ValueError:
            entries = None
        check("G13 Worktrunk would copy exactly the marker into an unenrolled worktree", entries == [".ai-memory.toml"],
              f"wt step copy-ignored --require-include --dry-run plans {entries}")
    for path in (Path(item).resolve() for item in args.worktree):
        verdict = check_capture(path)
        check(f"G13 enrolled worktree admits capture ({path.name})", verdict.get("admits_capture") is True,
              f"marker_present {verdict.get('marker_present')}, admits_capture {verdict.get('admits_capture')}")
    behind = git(main_checkout, "rev-list", "--count", "HEAD..origin/main").stdout.strip()
    carries = git(main_checkout, "grep", "-q", "ai_memory_hook_events_trusted", "HEAD", "--",
                  "scripts/adoption_status.py").returncode == 0
    check("G13 primary checkout carries the fix", carries,
          f"HEAD has the fixed checker: {carries}; {behind} commits behind origin/main (local ref)")

    failed = [name for name, passed, _ in RESULTS if not passed]
    print(f"\n{len(RESULTS) - len(failed)} of {len(RESULTS)} checks passed" + (f"; failed: {len(failed)}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
