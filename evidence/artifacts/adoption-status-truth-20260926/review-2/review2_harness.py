#!/usr/bin/env python3
"""local_integration harness for the second review's findings on prove.py and codex_known_answers.py.

    review2_harness.py PROVE_PY KNOWN_ANSWERS_PY CHECKOUT WORK      # WORK must not exist yet

Pin verdicts. Every native probe of PROVE_PY is stubbed, as in host-scripts/prove_harness.py, and CHECKOUT supplies
the pins file and is only read:
  V1 `codex --version` and `claude --version` unavailable: "a pin mismatch surfaces at the top" is UNTESTED;
  V2 both versions observed at their pins: no mismatch could surface, so UNTESTED;
  V3 codex observed off its pin, the checker lists it and pinned_versions_match is false: PASS;
  V4 the same observation while the checker lists no mismatch: FAIL;
  V5 codex observed at its pin while the checker lists it as mismatched: FAIL.
Bounded app-server reads. A stub `codex` is put first on PATH, and each case runs in its own process with 120 s,
which is more than the 90 s deadline plus the 15 s wait that the reviewed PROVE_PY claims as its bound:
  R1 PROVE_PY's codex_hooks_list, against an app-server that never answers and ignores SIGTERM, must return
     (with RuntimeError) inside the 120 s;
  R2 the same, against an app-server that answers, then ignores the end of its input and SIGTERM, must return the
     listing inside the 120 s;
  R3 KNOWN_ANSWERS_PY, against an app-server that never answers, must exit inside the 120 s.
The oracle's --base (codex_oracle.py beside KNOWN_ANSWERS_PY), a variant of the fixture's WORK_DIR finding:
  O1 `codex_oracle.py trust --base DIR` where DIR already holds a directory named trust with a file in it, and the
     stub app-server exits at once: the file must survive.
The stub records its pid, and every stub still alive is killed with SIGKILL after its case. Exit 0 only when every
expectation holds.
"""

from __future__ import annotations

import concurrent.futures
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

if len(sys.argv) != 5:
    raise SystemExit(__doc__)
prove_py, known_answers_py, checkout = (Path(arg).resolve() for arg in sys.argv[1:4])
work = Path(sys.argv[4])
work.mkdir()  # FileExistsError for an existing path: this harness writes only inside the WORK it created
work = work.resolve()
LIMIT = 120
unmet = 0


def expect(what: str, condition: bool) -> None:
    global unmet
    print(f"EXPECT {what}: {'ok' if condition else 'NOT MET'}")
    unmet += not condition


def sanitized(text: str) -> str:
    return text.replace(str(work), "$WORK").replace(str(checkout), "$CHECKOUT").replace(str(Path.home()), "~")


def git_env() -> dict:
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.update(HOME=str(work), GIT_CONFIG_NOSYSTEM="1")
    return env


for path in (prove_py, known_answers_py):
    print(f"under test: {path.parent.name}/{path.name} sha256 {hashlib.sha256(path.read_bytes()).hexdigest()[:16]}")

# prove.py reads CODEX_HOME's hooks.json and runs read-only git in its primary checkout: give it throwaway ones.
codex_home = work / "codex"
codex_home.mkdir()
(codex_home / "hooks.json").write_text(json.dumps({"hooks": {"SessionStart": [{"matcher": "", "hooks": [{
    "type": "command", "command": "/opt/example/ai-memory --data-dir /opt/example/data hook --event session-start"}]}]}}))
os.environ["CODEX_HOME"] = str(codex_home)
primary = work / "primary"
subprocess.run(["git", "init", "-q", str(primary)], check=True, env=git_env())
subprocess.run(["git", "-C", str(primary), "-c", "user.email=h@example.invalid", "-c", "user.name=h", "commit", "-q",
                "--allow-empty", "-m", "primary"], check=True, env=git_env())

PINS = {tool["id"]: tool["version"]
        for tool in json.loads((checkout / "adoption/pins-linux-x86_64.json").read_text(encoding="utf-8"))["tools"]}
OFF_PIN = "0.0.1"  # below every codex pin, so never an exact match
HOOKS = [{"source": "user", "command": "/opt/example/ai-memory hook --event x", "eventName": f"e{index}",
          "enabled": True, "trustStatus": "trusted"} for index in range(7)]


def load(path: Path):
    spec = importlib.util.spec_from_file_location(f"under_test_{time.monotonic_ns()}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fake_run(argv, *, cwd=None, stdin_text=None, timeout=300, env=None):
    if argv[0] == "git":
        return subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=timeout,
                              stdin=subprocess.DEVNULL, env=git_env())
    if argv[0] == "ai-memory":
        return subprocess.CompletedProcess(argv, 0, json.dumps(
            {"capture_mode": "allowlist", "marker_present": True, "admits_capture": True}), "")
    if argv[0] == "wt":
        return subprocess.CompletedProcess(argv, 0, json.dumps({"entries": [{"path": ".ai-memory.toml"}]}), "")
    return subprocess.CompletedProcess(argv, 0, "", "Ran 3 tests\n\nOK")  # the unittest run


def pin_verdict(versions: dict, mismatched: list, matched: list, top) -> tuple[str | None, str]:
    module = load(prove_py)
    report = {"client_wiring": {"codex": {"rtk_instructions": True, "ai_memory_hook_events": 7,
                                          "ai_memory_hook_events_trusted": 7}, "complete": False},
              "pinned_versions_match": top,
              "profiles": [{"id": "token-efficiency", "pinned_versions_summary": {
                  "matched": matched, "mismatched": mismatched, "unchecked": []}}]}
    module.adoption_report = lambda checkout, python: json.loads(json.dumps(report))
    module.prompt_input_rtk = lambda: True
    module.codex_hooks_list = lambda cwd, *args, **kwargs: HOOKS
    module.version_of = lambda argv: versions.get(argv[0])
    module.prometheus = lambda query: [{"value": [0, "1"]}]
    module.run = fake_run
    module.RESULTS.clear()
    sys.argv = ["prove.py", "--checkout", str(checkout), "--main", str(primary), "--python", sys.executable]
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        module.main()
    for line in output.getvalue().splitlines():
        status, _, rest = line.partition("  ")
        if status in ("PASS", "FAIL", "UNTESTED") and "a pin mismatch surfaces" in rest:
            return status, sanitized(line)
    return None, "no pin verdict printed"


print(f"pins read from $CHECKOUT: codex {PINS['codex']}, claude-code floor {PINS['claude-code']}")
PIN_CASES = [
    ("V1 no --version observation", {}, [], [], True, "UNTESTED"),
    ("V2 both at their pins", {"codex": PINS["codex"], "claude": PINS["claude-code"]}, [], ["codex", "claude-code"],
     True, "UNTESTED"),
    ("V3 codex off its pin, surfaced", {"codex": OFF_PIN, "claude": PINS["claude-code"]}, ["codex"], ["claude-code"],
     False, "PASS"),
    ("V4 codex off its pin, not surfaced", {"codex": OFF_PIN, "claude": PINS["claude-code"]}, [],
     ["codex", "claude-code"], True, "FAIL"),
    ("V5 codex at its pin, reported mismatched", {"codex": PINS["codex"], "claude": PINS["claude-code"]}, ["codex"],
     ["claude-code"], False, "FAIL"),
]
for label, versions, mismatched, matched, top, wanted in PIN_CASES:
    status, line = pin_verdict(versions, mismatched, matched, top)
    print(f"--- {label}\n{line}")
    expect(f"{label.split()[0]} the pin check reads {wanted}", status == wanted)

STUB = """#!{python}
import json, os, signal, sys, time
if sys.argv[1:] == ["--version"]:
    print("codex-cli 0.0.0-stub")
    raise SystemExit(0)
with open(os.environ["STUB_PIDS"], "a") as pids:
    pids.write(f"{{os.getpid()}}\\n")
if os.environ["STUB_MODE"] == "exit":
    raise SystemExit(0)
signal.signal(signal.SIGTERM, signal.SIG_IGN)
if os.environ["STUB_MODE"] == "answer":
    for line in sys.stdin:
        message = json.loads(line)
        if message.get("method") == "initialize":
            print(json.dumps({{"id": message["id"], "result": {{}}}}), flush=True)
        elif message.get("method") == "hooks/list":
            print(json.dumps({{"id": message["id"], "result": {{"data": [{{"cwd": "/", "hooks": [
                {{"eventName": "stop", "source": "user", "command": "stub"}}]}}]}}}}), flush=True)
time.sleep(600)  # silent from the start, or lingering after the end of its input; only SIGKILL ends it early
"""
CHILD = """
import importlib.util, inspect, json, sys, time
from pathlib import Path
spec = importlib.util.spec_from_file_location("prove_under_test", sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
kwargs = {"timeout": 2.0} if "timeout" in inspect.signature(module.codex_hooks_list).parameters else {}
try:
    outcome = f"returned {len(module.codex_hooks_list(Path('/'), **kwargs))} hook(s)"
except RuntimeError as error:
    outcome = f"raised RuntimeError: {error}"
print(json.dumps({"outcome": outcome, "answer_timeout": kwargs.get("timeout", "the script's own")}))
"""


def bounded(label: str, argv: list[str], mode: str) -> tuple[bool, float, str]:
    case = work / label
    (case / "bin").mkdir(parents=True)
    (case / "tmp").mkdir()
    stub = case / "bin" / "codex"
    stub.write_text(STUB.format(python=sys.executable))
    stub.chmod(0o755)
    pids = case / "stub.pids"
    env = dict(os.environ, PATH=f"{case / 'bin'}{os.pathsep}{os.environ.get('PATH', '')}", STUB_MODE=mode,
               STUB_PIDS=str(pids), TMPDIR=str(case / "tmp"), PYTHONDONTWRITEBYTECODE="1")
    start = time.monotonic()
    try:
        done = subprocess.run(argv, env=env, cwd=case, capture_output=True, text=True, timeout=LIMIT,
                              stdin=subprocess.DEVNULL)
        lines = (done.stdout.strip() + "\n" + done.stderr.strip()).strip().splitlines()
        finished, detail = True, f"exit {done.returncode}; last line: {lines[-1] if lines else ''}"
    except subprocess.TimeoutExpired:
        finished, detail = False, f"still running after {LIMIT} s, stopped by this harness"
    elapsed = time.monotonic() - start
    for pid in [int(item) for item in pids.read_text().split()] if pids.exists() else []:
        for kill in (os.kill, os.killpg):
            with contextlib.suppress(ProcessLookupError, PermissionError):
                kill(pid, signal.SIGKILL)
    return finished, elapsed, sanitized(detail)


READ_CASES = [
    ("R1", "prove.py codex_hooks_list, app-server never answers", [sys.executable, "-c", CHILD, str(prove_py)],
     "silent", "raised RuntimeError"),
    ("R2", "prove.py codex_hooks_list, app-server lingers after answering", [sys.executable, "-c", CHILD,
                                                                             str(prove_py)], "answer", "returned 1"),
    ("R3", "codex_known_answers.py, app-server never answers", [sys.executable, str(known_answers_py), "--timeout",
                                                                "2"], "silent", "RuntimeError"),
]
with concurrent.futures.ThreadPoolExecutor(max_workers=len(READ_CASES)) as pool:
    futures = [pool.submit(bounded, label, argv, mode) for label, _, argv, mode, _ in READ_CASES]
    outcomes = [future.result() for future in futures]
for (label, what, _, _, wanted), (finished, elapsed, detail) in zip(READ_CASES, outcomes):
    bar = next(limit for limit in (10, 30, 60, LIMIT, float("inf")) if elapsed < limit)
    timing = f"finished in under {bar} s" if finished else f"had not finished after {LIMIT} s"
    print(f"--- {label} {what}: {timing}; {detail}")
    expect(f"{label} returns inside {LIMIT} s ({wanted})", finished and wanted in detail)

oracle = known_answers_py.parent / "codex_oracle.py"
keep = work / "O1" / "base" / "trust" / "keep.txt"
keep.parent.mkdir(parents=True)
keep.write_text("a directory the oracle did not create\n")
finished, elapsed, detail = bounded("O1", [sys.executable, str(oracle), "trust", "--base", str(keep.parents[1])],
                                    "exit")
print(f"--- O1 {oracle.parent.name}/{oracle.name} sha256 {hashlib.sha256(oracle.read_bytes()).hexdigest()[:16]} "
      f"trust --base <a directory holding trust/keep.txt>: {'finished' if finished else 'did not finish'}; {detail}")
expect("O1 the existing trust/keep.txt survives", keep.is_file())
print(f"=== summary: {unmet} expectation(s) not met")
raise SystemExit(1 if unmet else 0)
