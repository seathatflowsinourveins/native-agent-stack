"""Execute the frozen task through native DeerFlow; retain every failed attempt.

References: DeerFlow v2.1.0 client.py, docker/docker-compose.yaml; Docker's
run/compose interfaces. The independent checker runs in a separate container
without network access, using the same digest-pinned Python runtime.
"""
from __future__ import annotations

import fcntl
import json
import os
import secrets
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from recipe import PREFIX, STATE, read, require_rootless, write
from receipt import build_receipt


def remove_owned(docker, name):
    try:
        result = subprocess.run(docker + ["rm", "--force", name], capture_output=True,
                                text=True, check=False, timeout=30)
        if result.returncode == 0 or "No such container" in result.stderr:
            return "absent"
    except (OSError, subprocess.TimeoutExpired):
        pass
    return "unknown"


def main():
    os.umask(0o077)
    settings, pins = read(STATE / "host.json"), read(PREFIX / "pins.json")
    require_rootless(settings)
    with (STATE / "e2e.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        attempt = secrets.token_hex(8)
        run = STATE / "runs" / attempt
        for path in (run, run / "work", run / "data", run / "artifacts"):
            path.mkdir(parents=True, mode=0o700)
        name = "runtime-worker-deerflow-e2e-" + attempt
        compose = read(STATE / "compose.json")
        service = compose["services"]["gateway"]
        service["environment"].update({
            "DEER_FLOW_HOME": "/run-data",
            "DEERFLOW_SQLITE_DIR": "/run-data/data",
            "DEER_FLOW_STREAM_BRIDGE_REDIS_URL": "",
            "DEERFLOW_SESSION_NAMESPACE": attempt,
        })
        for volume in service["volumes"]:
            if volume["target"] == "/work":
                volume["source"] = str(run / "work")
        for source, target in ((run / "data", "/run-data"), (run / "artifacts", "/run-artifacts")):
            service["volumes"].append({"type": "bind", "source": str(source), "target": target,
                                       "bind": {"create_host_path": False}})
        write(run / "compose.json", compose)
        docker = [settings["docker_bin"], "--context", "rootless"]
        command = docker + ["compose", "-f", str(run / "compose.json"), "run", "--rm", "--no-deps",
                            "--name", name, "-T", "gateway", "/app/backend/.venv/bin/python", "/runtime/drive.py"]
        window = {"start_epoch": time.time(), "end_epoch": None, "framework_exit_code": None,
                  "check_exit_code": None}
        write(run / "window.json", window)
        try:
            with (run / "framework.log").open("w") as log, (run / "framework-events.jsonl").open("w") as events:
                result = subprocess.run(command, stdout=events, stderr=log,
                                        timeout=2100, check=False)
                window["framework_exit_code"] = result.returncode
        except subprocess.TimeoutExpired:
            window["framework_exit_code"] = 124
        except KeyboardInterrupt:
            window["framework_exit_code"] = 130
        except OSError:
            window["framework_exit_code"] = 127
        finally:
            # Exact owned container only; never compose down the running UI or prune.
            window["framework_cleanup"] = remove_owned(docker, name)
            window["end_epoch"] = time.time()
            write(run / "window.json", window)
        checker_name = name + "-checker"
        checker = docker + ["run", "--rm", "--name", checker_name, "--network", "none", "--read-only", "--cap-drop", "ALL",
                            "--security-opt", "no-new-privileges", "--memory", "384m", "--pids-limit", "64",
                            "--tmpfs", "/tmp:rw,nosuid,nodev,size=32m",
                            "--mount", f"type=bind,source={run / 'artifacts'},target=/result,readonly",
                            "--mount", f"type=bind,source={PREFIX / 'e2e/check.py'},target=/oracle/check.py,readonly",
                            "--mount", f"type=bind,source={PREFIX / 'e2e/expected.json'},target=/oracle/expected.json,readonly",
                            pins["images"]["gateway"], "/app/backend/.venv/bin/python", "-I", "/oracle/check.py", "/result"]
        try:
            result = subprocess.run(checker, capture_output=True, text=True, timeout=45, check=False)
            window["check_exit_code"] = result.returncode
            (run / "checker.log").write_text(result.stdout + result.stderr)
            check = json.loads(result.stdout)
        except (OSError, ValueError, subprocess.TimeoutExpired):
            window["check_exit_code"] = 1
            check = {"passed": False, "reason": "checker_failed"}
        except KeyboardInterrupt:
            window["check_exit_code"] = 130
            check = {"passed": False, "reason": "checker_interrupted"}
        finally:
            window["checker_cleanup"] = remove_owned(docker, checker_name)
        write(run / "window.json", window)
        write(run / "check.json", check)
        receipt = build_receipt(run, Path.home() / ".local/share/omniroute/storage.sqlite", pins)
        obs = receipt["observations"]
        passed = (window["framework_exit_code"] == 0 and window["check_exit_code"] == 0
                  and window["framework_cleanup"] == "absent" and window["checker_cleanup"] == "absent"
                  and receipt["check"]["passed"]
                  and obs["completed_tasks_observed"] >= 2
                  and {"search-first", "verification-before-completion"} <= set(obs["skill_reads_observed"])
                  and obs["mcp_tool_results_observed"].get("context-mode_ctx_fetch_and_index", 0) > 0
                  and obs["mcp_tool_results_observed"].get("context-mode_ctx_search", 0) > 0
                  and any(r["path"] == "/v1/responses" and r["reasoning_effort_upstream"] == "max"
                          and str(r["status"]) in {"200", "success", "completed"}
                          for r in receipt["gateway"]["rows"]))
        receipt["run_gate_passed"] = passed
        write(run / "receipt.json", receipt)
        # A pointer in private state makes the receipt easy to find without publishing run IDs.
        (STATE / "last-run").write_text(str(run) + "\n")
        print(json.dumps({"run_gate_passed": passed, "task_check_passed": receipt["check"]["passed"],
                          "gateway_observation": receipt["gateway"]["state"]}))
        return 0 if passed else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, subprocess.CalledProcessError):
        print("E2E prerequisites unavailable; run install.sh and lifecycle.sh check first.")
        raise SystemExit(1) from None
