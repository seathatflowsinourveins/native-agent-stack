"""One explicit partial-offload inference; never execute generated code here."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import threading
import time
import urllib.request


def digest(path):
    with Path(path).open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def check_plan(plan):
    p = plan["profile"]
    if p["kind"] != "partial-offload" or p["gpu_layers"] != 32:
        raise ValueError("frozen partial-offload profile required")
    for key, expected in {"context": 4096, "parallel": 1, "batch": 128,
                          "threads": 8, "output_cap": 1536,
                          "minimum_free_mib": 3072}.items():
        if type(p[key]) is not int or p[key] != expected:
            raise ValueError("frozen resource budget changed")
    if plan["outer_attempts"] != 1:
        raise ValueError("exactly one trial required")


def candidate_source(content):
    value = json.loads(content)
    if not isinstance(value, dict) or set(value) != {"planner_py"}:
        raise ValueError("one source field required")
    source = value["planner_py"]
    if not isinstance(source, str) or not 1 <= len(source) <= 32768:
        raise ValueError("invalid source length")
    tree = ast.parse(source)
    forbidden = {"eval", "exec", "compile", "open", "__import__", "globals",
                 "locals", "getattr", "setattr", "delattr", "breakpoint", "input"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in forbidden:
            raise ValueError("dynamic or external operation refused")
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise ValueError("introspection refused")
        if isinstance(node, ast.Import):
            if any(alias.name not in {"heapq", "collections"} for alias in node.names):
                raise ValueError("unreviewed import")
        if isinstance(node, ast.ImportFrom):
            if node.level or node.module not in {"heapq", "collections"}:
                raise ValueError("unreviewed import")
    for node in tree.body:
        docstring = isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)
        if not docstring and not isinstance(node, (ast.FunctionDef, ast.Import, ast.ImportFrom)):
            raise ValueError("top-level execution refused")
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
    if not any(node.name == "order_tasks" for node in functions):
        raise ValueError("required function missing")
    if any(node.decorator_list or node.args.defaults or any(node.args.kw_defaults) for node in functions):
        raise ValueError("definition-time execution refused")
    return source


def gpu_memory():
    result = subprocess.run([
        "/usr/lib/wsl/lib/nvidia-smi", "--query-gpu=memory.total,memory.used",
        "--format=csv,noheader,nounits", "--id=0"],
        check=True, capture_output=True, text=True, timeout=3)
    total, used = [int(value.strip()) for value in result.stdout.strip().split(",")]
    return {"total_mib": total, "used_mib": used, "free_mib": total - used}


def terminate_owned(process):
    errors = []
    if process.poll() is not None:
        return errors
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass  # The monitor and coordinator may observe exit concurrently.
    except OSError as error:
        errors.append("terminate:" + type(error).__name__)
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except OSError as error:
            errors.append("kill:" + type(error).__name__)
        try:
            process.wait(timeout=5)
        except (subprocess.TimeoutExpired, OSError) as error:
            errors.append("wait:" + type(error).__name__)
    except OSError as error:
        errors.append("wait:" + type(error).__name__)
    return errors


def run(lane, plan_path, prompt_path, port):
    plan = json.loads(plan_path.read_text())
    check_plan(plan)
    if digest(prompt_path) != plan["prompt_sha256"]:
        raise ValueError("prompt hash mismatch")
    result_path = lane / "trial.json"
    # Never overwrite a failed or completed attempt.
    with result_path.open("x") as output:
        json.dump({"status": "started", "plan_sha256": digest(plan_path)}, output)
    result = {"status": "failed", "scope": "one-local-partial-offload-patch",
              "plan_sha256": digest(plan_path), "model_sha256": plan["model"]["sha256"],
              "quality": "awaiting-independent-source-review", "savings_claim": False}
    process = None
    stopped = threading.Event()
    monitor = None
    samples = []
    breaches = []
    cleanup_errors = []
    start = time.monotonic()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        model = lane / "downloads" / plan["model"]["filename"]
        if digest(model) != plan["model"]["sha256"]:
            raise ValueError("model hash mismatch")
        native = lane / "runtime" / "llama-b11057" / "llama-server"
        if digest(native) != plan["runtime"]["server_sha256"]:
            raise ValueError("native server hash mismatch")
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", port))
        before = gpu_memory()
        result["memory_before"] = before
        if before["free_mib"] < plan["profile"]["admission_free_mib"]:
            raise ValueError("GPU admission budget unavailable")
        p = plan["profile"]
        command = [str(native), "--model", str(model), "--alias", "local-qwen38-frozen", "--host", "127.0.0.1",
                   "--port", str(port), "--ctx-size", str(p["context"]),
                   "--parallel", str(p["parallel"]), "--n-gpu-layers", str(p["gpu_layers"]),
                   "--batch-size", str(p["batch"]), "--ubatch-size", str(p["batch"]),
                   "--threads", str(p["threads"]), "--n-predict", str(p["output_cap"]),
                   "--fit", "off", "--no-webui", "--no-agent", "--jinja", "--perf"]
        env = {"PATH": "/usr/bin:/bin", "HOME": str(lane), "CUDA_VISIBLE_DEVICES": "0",
               "LD_LIBRARY_PATH": str(lane / "runtime" / "cudart-llama-b11057-bin-ubuntu-cuda-13.3-x64")}
        log_path = lane / "server.private.log"
        with log_path.open("x") as log:
            process = subprocess.Popen(command, env=env, stdout=log, stderr=log, start_new_session=True)
        start = time.monotonic()

        def watch():
            while not stopped.wait(0.25):
                try:
                    sample = gpu_memory()
                    sample["elapsed_seconds"] = round(time.monotonic() - start, 3)
                    samples.append(sample)
                    if sample["free_mib"] < p["minimum_free_mib"]:
                        breaches.append("device-memory-reserve-breached")
                        cleanup_errors.extend(terminate_owned(process))
                        return
                    if time.monotonic() - start > plan["deadlines"]["total_seconds"]:
                        breaches.append("total-deadline")
                        cleanup_errors.extend(terminate_owned(process))
                        return
                except Exception:
                    breaches.append("memory-monitor-failed")
                    cleanup_errors.extend(terminate_owned(process))
                    return

        monitor = threading.Thread(target=watch, daemon=True)
        monitor.start()
        while time.monotonic() - start < plan["deadlines"]["startup_seconds"]:
            if process.poll() is not None or breaches:
                raise RuntimeError("native-server-startup-failed")
            try:
                with opener.open(f"http://127.0.0.1:{port}/health", timeout=2) as response:
                    if response.status == 200:
                        break
            except OSError:
                time.sleep(0.2)
        else:
            raise TimeoutError("startup-deadline")
        result["cold_start_seconds"] = round(time.monotonic() - start, 3)
        request_body = {"model": "local-qwen38-frozen", "messages": [
            {"role": "user", "content": prompt_path.read_text()}], "stream": True,
            "stream_options": {"include_usage": True}, **plan["sampling"],
            "max_tokens": p["output_cap"], "response_format": {"type": "json_schema",
                "json_schema": {"name": "planner_patch", "strict": True, "schema": {
                    "type": "object", "properties": {"planner_py": {"type": "string"}},
                    "required": ["planner_py"], "additionalProperties": False}}}}
        (lane / "request.private.json").write_text(json.dumps(request_body))
        req = urllib.request.Request(f"http://127.0.0.1:{port}/v1/chat/completions",
            json.dumps(request_body).encode(), {"Content-Type": "application/json"})
        generation_start = time.monotonic()
        content = []
        finished = False
        with opener.open(req, timeout=plan["deadlines"]["generation_seconds"]) as response:
            for raw in response:
                if time.monotonic() - generation_start > plan["deadlines"]["generation_seconds"]:
                    raise TimeoutError("generation-deadline")
                if not raw.startswith(b"data: "):
                    continue
                if raw.strip() == b"data: [DONE]":
                    finished = True
                    break
                event = json.loads(raw[6:])
                if event.get("usage"):
                    result["native_usage"] = event["usage"]
                for choice in event.get("choices", []):
                    text = choice.get("delta", {}).get("content")
                    if text:
                        result.setdefault("first_content_seconds", round(time.monotonic() - generation_start, 3))
                        content.append(text)
                    if choice.get("finish_reason"):
                        result["finish_reason"] = choice["finish_reason"]
        result["generation_seconds"] = round(time.monotonic() - generation_start, 3)
        combined = "".join(content)
        (lane / "response.private.txt").write_text(combined)
        if not finished or breaches or result.get("finish_reason") != "stop":
            raise ValueError("incomplete-or-interrupted-generation")
        source = candidate_source(combined)
        (lane / "candidate.py").write_text(source)
        result.update(status="generated-awaiting-review", candidate_sha256=digest(lane / "candidate.py"))
    except Exception as error:
        result["failure_type"] = type(error).__name__
        result["failure"] = str(error).replace(str(lane), "<lane>")[:500]
    finally:
        stopped.set()
        if monitor:
            monitor.join(timeout=5)
        if process:
            cleanup_errors.extend(terminate_owned(process))
            result["server_exit"] = process.returncode
        result["elapsed_seconds"] = round(time.monotonic() - start, 3)
        result["memory_samples"] = len(samples)
        result["minimum_free_mib_observed"] = min((x["free_mib"] for x in samples), default=None)
        result["maximum_device_used_mib_observed"] = max((x["used_mib"] for x in samples), default=None)
        result["memory_guard_events"] = breaches
        result["cleanup_errors"] = cleanup_errors
        try:
            result["memory_after"] = gpu_memory()
        except Exception as error:
            result["memory_after"] = None
            result["telemetry_after_error"] = type(error).__name__
        log_path = lane / "server.private.log"
        if log_path.exists():
            logs = log_path.read_text(errors="replace")
            placements = re.findall(r"offloaded (\d+)/(\d+) layers to GPU", logs)
            result["observed_layer_placement"] = [
                {"gpu_layers": int(gpu), "total_layers": int(total)}
                for gpu, total in placements]
        (lane / "memory.private.json").write_text(json.dumps(samples))
        result_path.write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lane", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--prompt", type=Path, required=True)
    parser.add_argument("--port", type=int, default=18085)
    args = parser.parse_args()
    print(json.dumps(run(args.lane.resolve(), args.plan.resolve(), args.prompt.resolve(), args.port), indent=2))
