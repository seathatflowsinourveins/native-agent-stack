#!/usr/bin/env python3
"""local_integration harness for prove.py's own verdict logic: import one prove.py, replace every native probe
(Codex, Claude, ai-memory, Worktrunk, Prometheus, the checker run) with a canned answer, run its main() and read
the verdicts it prints. Nothing starts Codex or reads a real client home; git runs read-only on the given
checkouts.

    prove_harness.py PROVE_PY CHECKOUT MAIN WORK

Scenarios, each with the verdict the fixed prove.py must print:
  P1 no native blocker (RTK text visible, every ai-memory hook trusted): "complete" cannot be contradicted by
     anything observed, so that check is UNTESTED, not PASS.
  P2 an enrolled worktree whose capture check comes from a data dir in denylist mode (which admits everything):
     the check must pass the installed hook's --data-dir and FAIL, since the marker was not what admitted it.
  P3 Prometheus unreachable: the render.py text check can pass, but the native G1 check is UNTESTED; with
     Prometheus answering 0 unscoped series it FAILs.
Exit 0 only when every expectation holds.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
from pathlib import Path

prove_py, checkout, main_checkout, work = (Path(arg).resolve() for arg in sys.argv[1:5])
work.mkdir(parents=True, exist_ok=True)
codex_home = work / "codex"
codex_home.mkdir(exist_ok=True)
(codex_home / "hooks.json").write_text(json.dumps({"hooks": {"SessionStart": [{"matcher": "", "hooks": [{
    "type": "command", "command": "/opt/example/ai-memory --data-dir /opt/example/data hook --event session-start"}]}]}}))
os.environ["CODEX_HOME"] = str(codex_home)


def load():
    spec = importlib.util.spec_from_file_location(f"prove_{id(object())}", prove_py)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CALLS: list[list[str]] = []


def fake_run(capture_verdict):
    real = subprocess.run

    def run(argv, *, cwd=None, stdin_text=None, timeout=300, env=None):
        CALLS.append(list(argv))
        if argv[0] == "git":
            return real(argv, cwd=cwd, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)
        if argv[0] == "ai-memory":
            return subprocess.CompletedProcess(argv, 0, json.dumps(capture_verdict), "")
        if argv[0] == "wt":
            return subprocess.CompletedProcess(argv, 0, json.dumps({"entries": [{"path": ".ai-memory.toml"}]}), "")
        return subprocess.CompletedProcess(argv, 0, "", "Ran 3 tests\n\nOK")  # the unittest run
    return run


REPORT = {"client_wiring": {"codex": {"rtk_instructions": True, "ai_memory_hook_events": 7,
                                      "ai_memory_hook_events_trusted": 7}, "complete": False},
          "pinned_versions_match": True,
          "profiles": [{"id": "token-efficiency", "pinned_versions_summary": {"matched": [], "mismatched": [],
                                                                               "unchecked": []}}]}
HOOKS = [{"source": "user", "command": "/opt/example/ai-memory hook --event x", "eventName": f"e{index}",
          "enabled": True, "trustStatus": "trusted"} for index in range(7)]


def run_main(module, *, capture_verdict, prometheus, worktrees=()):
    module.adoption_report = lambda checkout, python: json.loads(json.dumps(REPORT))
    module.prompt_input_rtk = lambda: True
    module.codex_hooks_list = lambda cwd: HOOKS
    module.version_of = lambda argv: None
    module.prometheus = prometheus
    module.run = fake_run(capture_verdict)
    module.RESULTS.clear()
    argv = ["prove.py", "--checkout", str(checkout), "--main", str(main_checkout), "--python", sys.executable]
    for item in worktrees:
        argv += ["--worktree", str(item)]
    sys.argv = argv
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        code = module.main()
    return code, output.getvalue()


def verdict(output: str, name_part: str) -> str | None:
    for line in output.splitlines():
        status, _, rest = line.partition("  ")
        if status in ("PASS", "FAIL", "UNTESTED") and name_part in rest:
            return status
    return None


unmet = 0


def expect(what: str, condition: bool) -> None:
    global unmet
    print(f"EXPECT {what}: {'ok' if condition else 'NOT MET'}")
    unmet += not condition


def unreachable(query):
    raise OSError("connection refused")


allowlist = {"capture_mode": "allowlist", "marker_present": True, "admits_capture": True}
print(f"prove.py under test: {prove_py.parent.name}/{prove_py.name}")

module = load()
code, output = run_main(module, capture_verdict=allowlist, prometheus=unreachable)
print("--- P1 no native blocker, P3 Prometheus unreachable\n" + output.replace(str(work), "$WORK"))
expect("P1 the complete check is not a PASS without a blocker", verdict(output, "complete") not in ("PASS", None))
expect("P3 the render.py text check passes", verdict(output, "render.py") == "PASS")
expect("P3 the native G1 check is UNTESTED", verdict(output, "holds in Prometheus") == "UNTESTED")

module = load()
worktree = work / "worker"
worktree.mkdir(exist_ok=True)
CALLS.clear()
code, output = run_main(module, worktrees=[worktree], prometheus=lambda query: [],
                        capture_verdict={"capture_mode": "denylist", "marker_present": False, "admits_capture": True})
print("--- P2 denylist data dir, P3 Prometheus with no unscoped series\n" + output.replace(str(work), "$WORK"))
capture_calls = [call for call in CALLS if call[0] == "ai-memory"]
expect("P2 the capture check passes the installed hook's --data-dir",
       bool(capture_calls) and all(call[1:3] == ["--data-dir", "/opt/example/data"] for call in capture_calls))
expect("P2 a worktree admitted by denylist mode FAILs", verdict(output, "enrolled worktree") == "FAIL")
expect("P3 no unscoped series FAILs the native G1 check", verdict(output, "holds in Prometheus") == "FAIL")
print(f"=== summary: {unmet} expectation(s) not met")
raise SystemExit(1 if unmet else 0)
