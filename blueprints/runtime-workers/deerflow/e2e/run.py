"""One bounded DeerFlow invocation for Inspect's solver; never score a task.

Sources: DeerFlow v2.1.0 client.py and docker/docker-compose.yaml; Inspect AI
0.3.271 custom solver API. Every attempt retains native events and cleanup state.
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
from recipe import OWNER, PREFIX, STATE, mount, read, require_rootless, worker_model, write
from check import read_completion
from receipt import build_receipt


def remove_owned(docker, name):
    if not name.startswith("rw-deerflow-"):
        raise ValueError("refusing cleanup of a non-worker container")
    try:
        result = subprocess.run(docker + ["rm", "--force", name], capture_output=True,
                                text=True, check=False, timeout=30)
        if result.returncode == 0 or "No such container" in result.stderr:
            return "absent"
    except (OSError, subprocess.TimeoutExpired):
        pass
    return "unknown"


def run_worker(prompt, sample_id, epoch):
    if not isinstance(prompt, str) or not prompt.strip() or "/shared_files/" in prompt:
        raise ValueError("missing question or unsupported GAIA asset")
    os.umask(0o077)
    settings, pins = read(STATE / "host.json"), read(PREFIX / "pins.json")
    model = worker_model(settings)
    require_rootless(settings)
    with (STATE / "e2e.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        attempt = secrets.token_hex(8)
        run = STATE / "runs" / attempt
        for path in (run, run / "work", run / "data"):
            path.mkdir(parents=True, mode=0o700)
        (run / "input.txt").write_text(prompt)
        write(run / "sample.json", {"id": sample_id, "epoch": epoch})
        name = "rw-deerflow-e2e-" + attempt
        compose = read(STATE / "compose.json")
        service = compose["services"]["gateway"]
        service["environment"].update({
            "DEERFLOW_MODEL": model,
            "DEER_FLOW_HOME": "/run-data",
            "DEERFLOW_SQLITE_DIR": "/run-data/data",
            "DEER_FLOW_STREAM_BRIDGE_REDIS_URL": "",
            "DEERFLOW_SESSION_NAMESPACE": attempt,
            "DEERFLOW_CONVERSATION_ID": "gaia-" + attempt,
        })
        for volume in service["volumes"]:
            if volume["target"] == "/work":
                volume["source"] = str(run / "work")
        service["volumes"].extend([
            mount(run / "data", "/run-data", False),
            mount(run / "input.txt", "/run-input.txt"),
        ])
        write(run / "compose.json", compose)
        docker = [settings["docker_bin"], "--context", "rootless"]
        command = docker + ["compose", "-f", str(run / "compose.json"), "run", "--rm", "--no-deps",
                            "--name", name, "--label", OWNER, "-T", "gateway",
                            "/app/backend/.venv/bin/python", "/runtime/drive.py"]
        window = {"start_epoch": time.time(), "end_epoch": None, "framework_exit_code": None,
                  "transport_ok": False}
        write(run / "window.json", window)
        try:
            with (run / "framework.log").open("w") as log, (run / "framework-events.jsonl").open("w") as events:
                result = subprocess.run(command, stdout=events, stderr=log, timeout=2100, check=False)
                window["framework_exit_code"] = result.returncode
        except subprocess.TimeoutExpired:
            window["framework_exit_code"] = 124
        except KeyboardInterrupt:
            window["framework_exit_code"] = 130
        except OSError:
            window["framework_exit_code"] = 127
        finally:
            window["framework_cleanup"] = remove_owned(docker, name)
            window["end_epoch"] = time.time()
            write(run / "window.json", window)
        try:
            if window["framework_exit_code"] != 0 or window["framework_cleanup"] != "absent":
                raise ValueError("native worker failed or cleanup is unconfirmed")
            completion = read_completion(run / "framework-events.jsonl")
            window["transport_ok"] = True
        finally:
            write(run / "window.json", window)
            receipt = build_receipt(run, Path.home() / ".local/share/omniroute/storage.sqlite", pins)
            write(run / "receipt.json", receipt)
            (STATE / "last-run").write_text(str(run) + "\n")
        return {"completion": completion, "model": model, "receipt": receipt}
