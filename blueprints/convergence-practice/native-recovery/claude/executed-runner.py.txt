#!/usr/bin/env python3
"""One explicit native Claude recovery trial on Linux; logs stay private."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import threading
import time
import uuid
from datetime import datetime, timezone

from stage import EXPECTED, actions

HERE = Path(__file__).resolve().parent
RESUME = "Resume the interrupted owned recovery fixture using only Bash. The supervisor has stopped the old wait. Run exactly python3 stage.py finalize and report its returned digest and execution_count. Reuse the existing checkpoint; do not recreate it, rerun wait, edit files, or delegate."


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def identity(pid):
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        return {"state": fields[0], "start_ticks": fields[19]}
    except (FileNotFoundError, ProcessLookupError):
        return None


def wait_alive(marker):
    live = identity(marker["pid"])
    return live is not None and live["state"] != "Z" and live["start_ticks"] == marker["start_ticks"]


def stop_wait(marker, workspace):
    if not wait_alive(marker):
        return False
    pid = marker["pid"]
    try:
        cmd = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
    except FileNotFoundError:
        return False
    if b"stage.py" not in cmd or b"wait" not in cmd or Path(f"/proc/{pid}/cwd").resolve() != workspace:
        raise RuntimeError("owned_wait_identity_check_failed")
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return False
    deadline = time.monotonic() + 5
    while wait_alive(marker) and time.monotonic() < deadline:
        time.sleep(0.05)
    if wait_alive(marker):
        os.kill(pid, signal.SIGKILL)
    return True


class NativeCLI:
    def __init__(self, command, prompt, workspace, run_dir, label):
        self.events = []
        self.invalid_lines = 0
        self.label = label
        self.err = (run_dir / (label + ".stderr.txt")).open("x")
        self.out = (run_dir / (label + ".stream.jsonl")).open("x")
        self.proc = subprocess.Popen(command, cwd=workspace, stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=self.err,
                                     start_new_session=True, text=True, bufsize=1)
        self.reader = threading.Thread(target=self.read, daemon=True)
        self.reader.start()
        self.proc.stdin.write(prompt)
        self.proc.stdin.close()

    def read(self):
        for line in self.proc.stdout:
            self.out.write(line)
            self.out.flush()
            try:
                self.events.append(json.loads(line))
            except json.JSONDecodeError:
                self.invalid_lines += 1

    def close(self):
        escalated = False
        if self.proc.poll() is None:
            escalated = True
            os.killpg(self.proc.pid, signal.SIGTERM)
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(self.proc.pid, signal.SIGKILL)
                self.proc.wait(timeout=5)
        self.reader.join(timeout=5)
        self.out.close()
        self.err.close()
        return escalated


def tool_calls(events):
    return [block for event in list(events) if event.get("type") == "assistant"
            for block in event.get("message", {}).get("content", [])
            if block.get("type") == "tool_use"]


def init(events):
    return [x for x in events if x.get("type") == "system" and x.get("subtype") == "init"]


def run(args):
    root = Path(args.run_dir).resolve()
    if HERE == root or HERE in root.parents:
        raise ValueError("private_run_directory_must_be_separate")
    root.mkdir(mode=0o700, parents=True, exist_ok=False)
    workspace = root / "fixture"
    workspace.mkdir()
    frozen = {name: sha(HERE / name) for name in ("stage.py", "run.py", "test_fixture.py", "TASK.md", "plan.json", "input.json")}
    write(root / "freeze.json", {"at_utc": datetime.now(timezone.utc).isoformat(), "sha256": frozen})
    for name in ("stage.py", "input.json", "TASK.md"):
        shutil.copyfile(HERE / name, workspace / name)
    subprocess.run(["git", "init", "--quiet", str(workspace)], check=True)
    subprocess.run(["git", "-C", str(workspace), "add", "stage.py", "input.json", "TASK.md"], check=True)
    subprocess.run(["git", "-C", str(workspace), "-c", "user.name=Recovery Fixture",
                    "-c", "user.email=fixture@example.invalid", "commit", "--quiet", "-m", "Freeze Claude recovery fixture"], check=True)
    executable = Path(shutil.which(args.claude) or args.claude).resolve(strict=True)
    version = subprocess.check_output([str(executable), "--version"], text=True).strip()
    session_id = str(uuid.uuid4())
    write(root / "native-identity.json", {"session_id": session_id})
    common = [str(executable), "-p", "--model", "claude-opus-5", "--effort", "ultracode",
              "--max-turns", "6", "--output-format", "stream-json", "--verbose",
              "--tools", "Bash", "--allowedTools", "Bash(python3 stage.py *)",
              "--disallowedTools", "mcp__*", "--permission-mode", "dontAsk", "--permission-prompts", "none"]
    clients, checks = [], {}
    marker = None
    failure = None
    stage = "initial_native_turn"
    cleanup = {"explicit_wait_cleanup_needed": None, "cli_cleanup_escalations": []}
    began = time.monotonic()
    try:
        first = NativeCLI(common + ["--session-id", session_id], (HERE / "TASK.md").read_text(), workspace, root, "initial")
        clients.append(first)
        deadline = time.monotonic() + args.timeout
        while True:
            calls = tool_calls(first.events)
            if any(c.get("name") != "Bash" or c.get("input", {}).get("command") not in (
                    "python3 stage.py checkpoint", "python3 stage.py wait") for c in calls):
                raise RuntimeError("unexpected_initial_native_tool")
            if (workspace / "wait-started.json").exists() and any(
                    c.get("input", {}).get("command") == "python3 stage.py wait" for c in calls):
                break
            if first.proc.poll() is not None:
                raise RuntimeError("native_cli_exited_before_pending_wait")
            if time.monotonic() >= deadline:
                raise TimeoutError("pending_wait_deadline")
            time.sleep(0.05)
        marker = json.loads((workspace / "wait-started.json").read_text())
        initial = init(first.events)
        checks["initial_session_id_matches"] = len(initial) == 1 and initial[0].get("session_id") == session_id
        checks["initial_model_observed"] = len(initial) == 1 and initial[0].get("model") == "claude-opus-5"
        checks["native_bash_wait_observed"] = True
        wait_call = [c for c in calls if c["input"]["command"] == "python3 stage.py wait"][0]
        returned_ids = [b.get("tool_use_id") for event in first.events if isinstance(event.get("message"), dict)
                        for b in event.get("message", {}).get("content", []) if isinstance(b, dict) and b.get("type") == "tool_result"]
        checks["wait_unfinished_at_interrupt"] = wait_alive(marker) and wait_call["id"] not in returned_ids and not (workspace / "wait-finished-naturally.json").exists()
        before = (workspace / "checkpoint.json").read_bytes()
        if not checks["wait_unfinished_at_interrupt"]:
            raise RuntimeError("wait_not_pending_at_interrupt")
        stage = "sigint"
        first.proc.send_signal(signal.SIGINT)
        try:
            first.proc.wait(timeout=20)
            checks["first_cli_sigint_exit"] = True
        except subprocess.TimeoutExpired as exc:
            checks["first_cli_sigint_exit"] = False
            raise RuntimeError("sigint_did_not_exit_native_cli") from exc
        cleanup["explicit_wait_cleanup_needed"] = stop_wait(marker, workspace)
        checks["owned_wait_stopped_before_resume"] = not wait_alive(marker)
        cleanup["cli_cleanup_escalations"].append(first.close())
        (workspace / "resume-authorized.json").write_text('{}\n')
        stage = "native_resume"
        second = NativeCLI(common + ["--resume", session_id], RESUME, workspace, root, "resumed")
        clients.append(second)
        second.proc.wait(timeout=args.timeout)
        cleanup["cli_cleanup_escalations"].append(second.close())
        resumed = init(second.events)
        checks["same_native_session_id"] = len(resumed) == 1 and resumed[0].get("session_id") == session_id
        checks["resumed_model_observed"] = len(resumed) == 1 and resumed[0].get("model") == "claude-opus-5"
        checks["resumed_native_tool_is_finalize_only"] = [
            (c.get("name"), c.get("input", {}).get("command")) for c in tool_calls(second.events)
        ] == [("Bash", "python3 stage.py finalize")]
        checks["resumed_cli_exit_zero"] = second.proc.returncode == 0
        results = [x for x in second.events if x.get("type") == "result"]
        checks["native_final_result_success"] = len(results) == 1 and results[0].get("is_error") is False and results[0].get("subtype") == "success"
        checks["checkpoint_unchanged"] = before == EXPECTED == (workspace / "checkpoint.json").read_bytes()
        final = json.loads((workspace / "final.json").read_text())
        checks["final_matches_oracle"] = final == {"checkpoint_sha256": hashlib.sha256(EXPECTED).hexdigest(), "execution_count": 1, "status": "complete"}
        stage = None
    except Exception as exc:
        failure = {"stage": stage, "type": type(exc).__name__}
        write(root / "failure-private.json", {**failure, "reason": str(exc)})
    finally:
        for client in clients:
            if not client.out.closed:
                cleanup["cli_cleanup_escalations"].append(client.close())
        if marker is not None and wait_alive(marker):
            cleanup["final_wait_cleanup_needed"] = stop_wait(marker, workspace)
    checks["owned_cli_processes_stopped"] = bool(clients) and all(c.proc.poll() is not None for c in clients)
    checks["owned_wait_stopped"] = marker is not None and not wait_alive(marker)
    checks["exact_action_journal"] = actions(workspace) == ["checkpoint", "wait", "finalize"]
    checks["checkpoint_executed_once"] = actions(workspace).count("checkpoint") == 1
    checks["frozen_files_unchanged"] = all(sha(HERE / name) == value for name, value in frozen.items()) and all(sha(workspace / name) == frozen[name] for name in ("stage.py", "input.json", "TASK.md"))
    usage = []
    for client in clients:
        results = [x for x in client.events if x.get("type") == "result"]
        usage.append({"invocation": client.label, "terminal_result_observed": bool(results),
                      "terminal_usage": results[-1].get("usage") if results else None,
                      "per_model_usage": results[-1].get("modelUsage") if results else None,
                      "partial_assistant_messages": sum(x.get("type") == "assistant" for x in client.events)})
    receipt = {"schema_version": 1, "kind": "claude_native_session_recovery", "attempt": 1,
               "status": "passed" if failure is None and checks and all(checks.values()) else "failed",
               "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
               "platform": "Linux WSL2", "native_version": version, "executable_sha256": sha(executable),
               "model_requested": "claude-opus-5", "effort_requested": "ultracode",
               "wall_seconds": round(time.monotonic() - began, 3), "checks": checks,
               "failure": failure, "action_journal": actions(workspace), "cleanup": cleanup,
               "native_cli_exit_codes": [c.proc.returncode for c in clients],
               "invalid_stdout_lines": [c.invalid_lines for c in clients],
               "frozen_files": frozen, "checkpoint_sha256": hashlib.sha256(EXPECTED).hexdigest(),
               "private_stream_sha256": {c.label: sha(root / (c.label + ".stream.jsonl")) for c in clients},
               "usage": {"invocations": usage, "complete_two_invocation_total": None,
                         "native_retries": None, "provider_cancellation_confirmed": None,
                         "billed_cost": None, "coordinator_and_review_usage": None, "savings_claim": None},
               "limitations": ["One synthetic same-host CLI session recovery attempt; no independent-host, network, power-loss or whole-ecosystem guarantee.", "SIGINT and process observations do not confirm remote provider cancellation or billing cessation.", "The same native session ID is verified privately; no raw transcript replay or --fork-session is used.", "Explicit Opus5 and Ultracode are scoped to this trial; this does not qualify the best alias or another model. No child agent is allowed.", "Cumulative resumed results and per-model counters can have different scopes; interrupted usage can be incomplete. Retain categories separately and do not add them.", "Full streams, process identities and session identifiers remain private. Cleanup targets owned CLI process groups and the identity-verified owned wait, not shared services."]}
    write(root / "receipt.json", receipt)
    print(json.dumps({"status": receipt["status"], "failure": failure, "checks": checks,
                      "native_cli_exit_codes": receipt["native_cli_exit_codes"], "wall_seconds": receipt["wall_seconds"]}))
    return 0 if receipt["status"] == "passed" else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--claude", default="claude")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--timeout", type=int, default=180)
    raise SystemExit(run(parser.parse_args()))
