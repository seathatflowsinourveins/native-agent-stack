"""One bounded DeerFlow invocation for Inspect's solver; never score a task.

Sources: DeerFlow v2.1.0 client.py and docker/docker-compose.yaml; Inspect AI
0.3.271 custom solver API. Every attempt retains native events and cleanup state.
"""
from __future__ import annotations

import fcntl
import json
import os
import secrets
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from recipe import (HERE, OWNER, PREFIX, STATE, arm_settings, dependency_mount, expand,
                    mount, read, require_rootless, usage_database, write)
from check import read_completion
from receipt import build_receipt, compression_snapshot


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


def attempt_compose(settings, pins, prefix, state, run, attempt, arm):
    """Fresh Compose graph: compose-spec@914ec15d 06-networks.md:215-218.

    No persistent service dict, token, Redis connection or writable mount is
    inherited. A host-owned QMD seed is copied into disposable attempt state.
    """
    values = dict(settings.get("variables", {}))
    values.update({"IMAGE_" + k.upper(): v for k, v in pins["images"].items()})
    values.update(DEERFLOW_MODEL=arm["model"], DEERFLOW_BASE_URL=arm["base_url"], RUNTIME_WORKER_ARM=arm["arm"])
    compose = expand(read(HERE / "compose.json.template"), values)
    name = "rw-deerflow-e2e-" + attempt
    compose["name"] = name
    compose["services"] = {k:v for k,v in compose["services"].items() if k in {"gateway", "egress"}}
    for key, network in compose["networks"].items():
        network["name"] = name + "-" + key
    service = compose["services"]["gateway"]
    for key in ("env_file", "depends_on", "healthcheck"):
        service.pop(key, None)
    service["container_name"] = name
    service["environment"].update({"DEER_FLOW_STREAM_BRIDGE_REDIS_URL":"",
        "DEERFLOW_SESSION_NAMESPACE":attempt, "DEERFLOW_CONVERSATION_ID":"gaia-" + attempt})
    for folder in (run / "data", run / "work", run / "config"):
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    seed = state / "qmd-seed"
    if seed.exists():
        shutil.copytree(seed, run / "data/mcp/qmd")
    service["volumes"] = [mount(prefix / "runtime", "/runtime"), mount(state / "config", "/config"),
        mount(run / "data", "/state", False), mount(run / "work", "/work", False),
        mount(state / "work/.agents/skills", "/skills/custom"), mount(run / "input.txt", "/run-input.txt")]
    service["volumes"].extend(dependency_mount(i, settings, prefix) for i in settings.get("mcp_mounts", []))
    egress = compose["services"]["egress"]
    egress["container_name"] = name + "-egress"
    proxy = (HERE / "egress.conf.template").read_text().replace("GATEWAY_ORIGIN", arm["base_url"].removesuffix("/v1"))
    config = run / "config/egress.conf"
    config.write_text(proxy)
    config.chmod(0o644)
    egress["volumes"] = [mount(config, "/config/egress.conf")]
    return compose


def run_worker(prompt, sample_id, epoch):
    if not isinstance(prompt, str) or not prompt.strip() or "/shared_files/" in prompt:
        raise ValueError("missing question or unsupported GAIA asset")
    os.umask(0o077)
    settings, pins = read(STATE / "host.json"), read(PREFIX / "pins.json")
    arm = arm_settings(settings)
    model = arm["model"]
    require_rootless(settings)
    with (STATE / "e2e.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        attempt = secrets.token_hex(8)
        run_id = os.environ.get("DEERFLOW_RUN_ID")
        if run_id:
            import re
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", run_id):
                raise ValueError("invalid stable run id")
        run = STATE / "runs" / run_id / ("attempt-" + attempt) if run_id else STATE / "runs" / attempt
        for path in (run, run / "work", run / "data"):
            path.mkdir(parents=True, mode=0o700)
        (run / "input.txt").write_text(prompt)
        write(run / "sample.json", {"id": sample_id, "epoch": epoch})
        name = "rw-deerflow-e2e-" + attempt
        compose = attempt_compose(settings, pins, PREFIX, STATE, run, attempt, arm)
        write(run / "compose.json", compose)
        docker = [settings["docker_bin"], "--context", "rootless"]
        command = docker + ["compose", "-f", str(run / "compose.json"), "run", "--rm", "--no-deps",
                            "--name", name, "--label", OWNER, "-T", "gateway",
                            "/app/backend/.venv/bin/python", "/runtime/drive.py"]
        window = {**arm, "start_epoch": time.time(), "end_epoch": None, "framework_exit_code": None,
                  "transport_ok": False, "compression_before": compression_snapshot(arm["arm"])}
        write(run / "window.json", window)
        try:
            subprocess.run(docker + ["compose", "-f", str(run / "compose.json"), "up", "-d",
                "--no-build", "--pull", "never", "egress"], capture_output=True, check=True, timeout=120)
            with (run / "framework.log").open("w") as log, (run / "framework-events.jsonl").open("w") as events:
                result = subprocess.run(command, stdout=events, stderr=log, timeout=2100, check=False)
                window["framework_exit_code"] = result.returncode
        except subprocess.TimeoutExpired:
            window["framework_exit_code"] = 124
        except KeyboardInterrupt:
            window["framework_exit_code"] = 130
        except (OSError, subprocess.CalledProcessError):
            window["framework_exit_code"] = 127
        finally:
            window["framework_cleanup"] = remove_owned(docker, name)
            try:
                with (run / "gateway-correlation.jsonl").open("w") as output:
                    subprocess.run(docker + ["logs", name + "-egress"], stdout=output,
                                   stderr=subprocess.DEVNULL, check=False, timeout=30)
                cleanup = subprocess.run(docker + ["compose", "-f", str(run / "compose.json"),
                    "down", "--timeout", "15"], capture_output=True, check=False, timeout=60)
                window["network_cleanup"] = "absent" if cleanup.returncode == 0 else "unknown"
            except (OSError, subprocess.TimeoutExpired):
                window["network_cleanup"] = "unknown"
            window["end_epoch"] = time.time()
            window["compression_after"] = compression_snapshot(arm["arm"])
            write(run / "window.json", window)
        try:
            if (window["framework_exit_code"] != 0 or window["framework_cleanup"] != "absent"
                    or window["network_cleanup"] != "absent"):
                raise ValueError("native worker failed or cleanup is unconfirmed")
            completion = read_completion(run / "framework-events.jsonl")
            window["transport_ok"] = True
        finally:
            write(run / "window.json", window)
            receipt = build_receipt(run, usage_database(arm["arm"]), pins)
            write(run / "receipt.json", receipt)
            (STATE / "last-run").write_text(str(run) + "\n")
        return {"completion": completion, "model": model, "receipt": receipt}
