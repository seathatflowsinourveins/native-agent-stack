#!/usr/bin/env python3
"""Evaluate one frozen arm against a loopback OpenAI-compatible llama-server.

Standard library only. Raw model replies stay in a private file; the public
metrics file holds item codes, parse status and server timings, never filing
text. The same file builds the frozen server argv and runs the read-only
preflight checks that window.sh calls before it stops the production unit.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import socket
import sys
import time
import urllib.error
import urllib.request

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
PLAN = HERE / "plan.json"
PROMPT = HERE / "prompt.txt"
MARKER = "@@FILING_TEXT@@"
CODE = re.compile(r"[1-9]\.[0-9]{2}")
FENCE = re.compile(r"```(?:json|JSON)?[ \t]*\n(.*?)\n?[ \t]*```", re.DOTALL)
RUNNABLE = {"runnable", "runnable_if_admitted"}
MAX_RESPONSE_BYTES = 1024 * 1024
TIMING_FIELDS = ("prompt_n", "prompt_ms", "predicted_n", "predicted_ms", "predicted_per_second",
                 "draft_n", "draft_n_accepted")

_SPEC = importlib.util.spec_from_file_location("li26_path_safety", REPO / "scripts/path_safety.py")
path_safety = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(path_safety)


def digest(path):
    with Path(path).open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def now_utc():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def load_plan(path=PLAN):
    plan = json.loads(Path(path).read_text())
    check_plan(plan)
    return plan


def check_plan(plan):
    """The frozen serving, sampling and guard values this runner was written for."""
    if plan.get("status") != "preregistered" or plan.get("frozen_before_inference") is not True:
        raise ValueError("preregistered frozen plan required")
    serving, sampling, window = plan["serving"], plan["sampling"], plan["window"]
    frozen = {"port": 18299, "context": 8192, "parallel": 1, "batch": 512, "ubatch": 128,
              "threads": 16, "threads_batch": 24, "cache_ram_mib": 0}
    for key, value in frozen.items():
        if type(serving[key]) is not int or serving[key] != value:
            raise ValueError(f"frozen serving value changed: {key}")
    if serving["host"] != "127.0.0.1" or serving["fit"] != "off":
        raise ValueError("frozen serving value changed: host/fit")
    if (sampling["seed"], sampling["temperature"], sampling["top_k"], sampling["top_p"],
            sampling["max_tokens"], sampling["stream"], sampling["cache_prompt"],
            sampling["chat_template_kwargs"]) != (0, 0.0, 1, 1.0, 256, False, False,
                                                  {"enable_thinking": False}):
        raise ValueError("frozen sampling changed")
    for key, value in {"admission_floor_mib": 16384, "minimum_free_mib": 3072, "window_seconds": 10800,
                       "request_seconds": 180, "startup_seconds": 300, "arm_seconds": 9000}.items():
        if window[key] != value:
            raise ValueError(f"frozen window value changed: {key}")
    ids = [arm["id"] for arm in plan["arms"]]
    if ids != ["C0", "C1", "C2", "B", "M", "X"] or plan["arms"][0]["role"] != "control":
        raise ValueError("frozen arm list changed")
    runtime = {"tag": plan["runtime"]["tag"], "commit": plan["runtime"]["commit"]}
    if runtime != {"tag": "b11146", "commit": "7fe450e19305b828c199d602c23a8337aaa1f03b"} or \
            any(arm["runtime"] != runtime for arm in plan["arms"]):
        raise ValueError("every arm must name the pinned b11146 runtime")


def verify_frozen(plan):
    for relative, expected in plan["frozen_inputs"].items():
        path = path_safety.refuse_untrusted_symlinks(REPO / relative, "frozen input symlink refused")
        if digest(path) != expected:
            raise ValueError(f"frozen input changed: {relative}")
    if digest(PROMPT) != plan["prompt_sha256"]:
        raise ValueError("prompt hash mismatch")


def arm_by_id(plan, arm_id):
    for arm in plan["arms"]:
        if arm["id"] == arm_id:
            return arm
    raise ValueError(f"unknown arm {arm_id}")


def runnable_arm(plan, arm_id):
    arm = arm_by_id(plan, arm_id)
    if arm["support_status"] not in RUNNABLE:
        raise ValueError(f"arm {arm_id} is {arm['support_status']}; not run under this plan")
    return arm


def alias(arm_id):
    return "li26-" + arm_id.lower()


def model_path(models_dir, model):
    return Path(models_dir) / model["local_dir"] / model["filename"]


def server_argv(plan, arm_id, runtime_dir, models_dir, port=None):
    """The exact llama-server argv for one arm; flags are cited from b11146 --help in plan.json."""
    arm, serving = runnable_arm(plan, arm_id), plan["serving"]
    port = serving["port"] if port is None else port
    argv = [str(Path(runtime_dir) / "llama-server"), "--model", str(model_path(models_dir, arm["model"])),
            "--alias", alias(arm_id), "--host", serving["host"], "--port", str(port),
            "--ctx-size", str(serving["context"]), "--parallel", str(serving["parallel"]),
            "--gpu-layers", str(arm["profile"]["gpu_layers"]), "--fit", serving["fit"],
            "--threads", str(serving["threads"]), "--threads-batch", str(serving["threads_batch"]),
            "--batch-size", str(serving["batch"]), "--ubatch-size", str(serving["ubatch"]),
            "--cache-ram", str(serving["cache_ram_mib"]), *serving["flags"]]
    draft = arm["profile"].get("draft")
    if draft:
        argv += ["--spec-type", draft["type"], "--spec-draft-model", str(model_path(models_dir, draft)),
                 "--spec-draft-ngl", str(draft["gpu_layers"]), "--spec-draft-n-max", str(draft["n_max"])]
    return argv


def runtime_manifest_sha256(runtime_dir):
    """sha256 over `sha256sum` lines of every regular file, sorted by name (symlinks excluded)."""
    runtime_dir = Path(runtime_dir)
    names = sorted(path.name for path in runtime_dir.iterdir() if path.is_file() and not path.is_symlink())
    listing = "".join(f"{digest(runtime_dir / name)}  {name}\n" for name in names)
    return hashlib.sha256(listing.encode()).hexdigest()


def verify_arms(plan, arm_ids, runtime_dir, models_dir):
    runtime = plan["runtime"]
    if digest(Path(runtime_dir) / "llama-server") != runtime["server_sha256"]:
        raise ValueError("llama-server hash mismatch")
    if runtime_manifest_sha256(runtime_dir) != runtime["runtime_manifest_sha256"]:
        raise ValueError("runtime directory manifest mismatch")
    checked = {}
    for arm_id in arm_ids:
        arm = runnable_arm(plan, arm_id)
        for model in filter(None, [arm["model"], arm["profile"].get("draft")]):
            path = model_path(models_dir, model)
            if path not in checked:
                if path.stat().st_size != model["bytes"] or digest(path) != model["sha256"]:
                    raise ValueError(f"model bytes mismatch for arm {arm_id}: {model['filename']}")
                checked[path] = model["sha256"]
    return len(checked)


def admission_mib(plan, arm_id):
    arm = runnable_arm(plan, arm_id)
    floor, reserve = plan["window"]["admission_floor_mib"], plan["window"]["minimum_free_mib"]
    required = max(floor, arm["estimated_device_mib"] + reserve)
    if arm["admission_free_mib"] != required:
        raise ValueError("admission threshold is not max(floor, estimate + reserve)")
    return required


def load_inputs(acquisition, expected_sha256):
    acquisition = Path(acquisition)
    raw = (acquisition / "inputs.jsonl").read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("inputs hash mismatch")
    manifest = json.loads((acquisition / "manifest.json").read_text())
    if manifest.get("status") != "complete" or manifest["inputs"]["sha256"] != expected_sha256:
        raise ValueError("acquisition is not complete for these inputs")
    rows = [json.loads(line) for line in raw.decode().splitlines()]
    if not rows or [row["accession"] for row in rows] != sorted({row["accession"] for row in rows}):
        raise ValueError("inputs must be unique and sorted by accession")
    return rows


def prompt_template(plan):
    template = PROMPT.read_text()
    if hashlib.sha256(template.encode()).hexdigest() != plan["prompt_sha256"] or template.count(MARKER) != 1:
        raise ValueError("prompt template changed")
    return template


def build_request(plan, template, arm_id, document):
    sampling = plan["sampling"]
    return {"model": alias(arm_id),
            "messages": [{"role": "user", "content": template.replace(MARKER, document, 1)}],
            "stream": sampling["stream"], "seed": sampling["seed"], "temperature": sampling["temperature"],
            "top_k": sampling["top_k"], "top_p": sampling["top_p"], "max_tokens": sampling["max_tokens"],
            "chat_template_kwargs": dict(sampling["chat_template_kwargs"]),
            "cache_prompt": sampling["cache_prompt"]}


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def _strict_items(text):
    try:
        value = json.loads(text, object_pairs_hook=_unique_keys)
    except ValueError:
        return None
    if not isinstance(value, dict) or set(value) != {"items"} or not isinstance(value["items"], list):
        return None
    items = value["items"]
    if any(not isinstance(item, str) or not CODE.fullmatch(item) for item in items) or len(set(items)) != len(items):
        return None
    return sorted(items)


def parse_items(content):
    """Return (sorted codes or None, status); status is valid, fenced_valid or invalid."""
    if not isinstance(content, str):
        return None, "invalid"
    text = content.strip()
    items = _strict_items(text)
    if items is not None:
        return items, "valid"
    fenced = FENCE.fullmatch(text)
    if fenced:
        items = _strict_items(fenced[1].strip())
        if items is not None:
            return items, "fenced_valid"
    return None, "invalid"


def opener():
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def get_json(http, url, timeout=5):
    with http.open(url, timeout=timeout) as response:
        return json.loads(response.read(MAX_RESPONSE_BYTES))


def post_json(http, url, body, timeout):
    request = urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json"})
    start = time.monotonic()
    try:
        with http.open(request, timeout=timeout) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                return response.status, None, "response_too_large", time.monotonic() - start
            return response.status, json.loads(raw), None, time.monotonic() - start
    except urllib.error.HTTPError as error:
        error.close()
        return error.code, None, f"http_{error.code}", time.monotonic() - start
    except (TimeoutError, socket.timeout):
        return None, None, "request_deadline", time.monotonic() - start
    except urllib.error.URLError as error:
        timed_out = isinstance(error.reason, (TimeoutError, socket.timeout))
        return None, None, "request_deadline" if timed_out else "server_unavailable", time.monotonic() - start
    except (OSError, ValueError):
        return None, None, "server_unavailable", time.monotonic() - start


def score_reply(row, status, payload, error, elapsed):
    """Public per-filing record (no text) and the private raw record."""
    content = finish = None
    timings = {}
    usage = {}
    if isinstance(payload, dict):
        choice = (payload.get("choices") or [{}])[0]
        content = (choice.get("message") or {}).get("content")
        finish = choice.get("finish_reason")
        timings = payload.get("timings") or {}
        usage = payload.get("usage") or {}
    items, parse_status = parse_items(content) if error is None else (None, "invalid")
    public = {"accession": row["accession"], "gold": row["labels"], "predicted": items,
              "parse_status": parse_status, "finish_reason": finish, "http_status": status, "error": error,
              "prompt_tokens": usage.get("prompt_tokens"), "completion_tokens": usage.get("completion_tokens"),
              "elapsed_ms": None if elapsed is None else round(elapsed * 1000, 1)}
    public.update({field: timings.get(field) for field in TIMING_FIELDS})
    private = {"accession": row["accession"], "http_status": status, "error": error, "response": payload}
    return public, private


def check_server(http, endpoint, arm_id, arm):
    models = get_json(http, endpoint + "/v1/models")
    served = {entry.get("id") for entry in models.get("data", [])}
    for entry in models.get("models", []):
        served.update(filter(None, (entry.get("name"), entry.get("model"))))
    if alias(arm_id) not in served:
        raise ValueError("endpoint does not serve this arm's alias")
    props = get_json(http, endpoint + "/props")
    basename = Path(str(props.get("model_path", ""))).name
    if basename != Path(arm["model"]["filename"]).name:
        raise ValueError("endpoint model file does not match the arm")
    return {"alias": alias(arm_id), "model_basename": basename, "build_info": props.get("build_info")}


def write_private(path, raw):
    with Path(path).open("xb") as stream:
        os.chmod(path, 0o600)
        stream.write(raw)


def run(plan_path, arm_id, acquisition, inputs_sha256, endpoint, out, deadline_epoch,
        http=None, clock=time.time):
    plan = load_plan(plan_path)
    verify_frozen(plan)
    arm = runnable_arm(plan, arm_id)
    template = prompt_template(plan)
    rows = load_inputs(acquisition, inputs_sha256)
    out = path_safety.refuse_untrusted_symlinks(out, "output symlink refused")
    out.mkdir(mode=0o700)
    http = http or opener()
    request_seconds = plan["window"]["request_seconds"]
    metrics = {"schema_version": 1, "kind": "local_inference_latest_arm_metrics", "arm": arm_id,
               "plan_sha256": digest(plan_path), "prompt_sha256": plan["prompt_sha256"],
               "inputs_sha256": inputs_sha256, "model_sha256": arm["model"]["sha256"],
               "draft_sha256": (arm["profile"].get("draft") or {}).get("sha256"),
               "started_utc": now_utc(), "status": "stopped", "events": [], "server": None,
               "filings": [], "no_document_text": True}
    raw_path = out / "raw.private.jsonl"
    write_private(raw_path, b"")
    try:
        metrics["server"] = check_server(http, endpoint, arm_id, arm)
        with raw_path.open("ab") as raw_log:
            for row in rows:
                remaining = deadline_epoch - clock()
                if remaining <= 0:
                    metrics["events"].append("arm-deadline")
                    break
                timeout = min(request_seconds, remaining)
                body = build_request(plan, template, arm_id, row["input"])
                status, payload, error, elapsed = post_json(
                    http, endpoint + "/v1/chat/completions", body, timeout)
                if error is None and elapsed > request_seconds:
                    error = "request_deadline"
                public, private = score_reply(row, status, payload, error, elapsed)
                metrics["filings"].append(public)
                raw_log.write(json.dumps(private, sort_keys=True).encode() + b"\n")
                raw_log.flush()
                if error == "request_deadline":
                    reason = "arm-deadline" if timeout < request_seconds else "request-deadline"
                    metrics["events"].append(f"{reason}:{row['accession']}")
                    break
                if error == "server_unavailable":
                    metrics["events"].append(f"server-unavailable:{row['accession']}")
                    break
            else:
                metrics["status"] = "completed"
    except (OSError, ValueError) as error:
        metrics["events"].append("server-check-failed:" + type(error).__name__)
    finally:
        attempted = {entry["accession"] for entry in metrics["filings"]}
        for row in rows:
            if row["accession"] not in attempted:
                metrics["filings"].append(score_reply(row, None, None, "not_attempted", None)[0])
        metrics["filings"].sort(key=lambda entry: entry["accession"])
        metrics["finished_utc"] = now_utc()
        write_private(out / "metrics.json", (json.dumps(metrics, indent=2, sort_keys=True) + "\n").encode())
    return metrics


def port_free(port):
    with socket.socket() as probe:
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def wait_health(url, timeout, pid=None, http=None, clock=time.monotonic, sleep=time.sleep):
    http = http or opener()
    deadline = clock() + timeout
    while clock() < deadline:
        if pid is not None:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return False
        try:
            with http.open(url, timeout=2) as response:
                if response.status == 200:
                    return True
        except (OSError, ValueError):
            pass
        sleep(0.5)
    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    frozen = commands.add_parser("verify-frozen")
    frozen.add_argument("--plan", type=Path, default=PLAN)
    arms = commands.add_parser("verify-arms")
    arms.add_argument("--plan", type=Path, default=PLAN)
    arms.add_argument("--arm", action="append", required=True)
    arms.add_argument("--runtime-dir", type=Path, required=True)
    arms.add_argument("--models-dir", type=Path, required=True)
    inputs = commands.add_parser("verify-inputs")
    inputs.add_argument("--acquisition", type=Path, required=True)
    inputs.add_argument("--inputs-sha256", required=True)
    argv = commands.add_parser("argv")
    argv.add_argument("--plan", type=Path, default=PLAN)
    argv.add_argument("--arm", required=True)
    argv.add_argument("--runtime-dir", type=Path, required=True)
    argv.add_argument("--models-dir", type=Path, required=True)
    admission = commands.add_parser("admission")
    admission.add_argument("--plan", type=Path, default=PLAN)
    admission.add_argument("--arm", required=True)
    port = commands.add_parser("port-free")
    port.add_argument("--port", type=int, required=True)
    health = commands.add_parser("wait-health")
    health.add_argument("--url", required=True)
    health.add_argument("--timeout", type=float, required=True)
    health.add_argument("--pid", type=int)
    evaluate = commands.add_parser("run")
    evaluate.add_argument("--plan", type=Path, default=PLAN)
    evaluate.add_argument("--arm", required=True)
    evaluate.add_argument("--acquisition", type=Path, required=True)
    evaluate.add_argument("--inputs-sha256", required=True)
    evaluate.add_argument("--endpoint", required=True)
    evaluate.add_argument("--out", type=Path, required=True)
    evaluate.add_argument("--deadline-epoch", type=float, required=True)
    args = parser.parse_args()
    if args.command == "verify-frozen":
        verify_frozen(load_plan(args.plan))
    elif args.command == "verify-arms":
        print(f"verified {verify_arms(load_plan(args.plan), args.arm, args.runtime_dir, args.models_dir)} model files")
    elif args.command == "verify-inputs":
        print(f"verified {len(load_inputs(args.acquisition, args.inputs_sha256))} eligible filings")
    elif args.command == "argv":
        sys.stdout.write("".join(part + "\0" for part in server_argv(
            load_plan(args.plan), args.arm, args.runtime_dir, args.models_dir)))
    elif args.command == "admission":
        print(admission_mib(load_plan(args.plan), args.arm))
    elif args.command == "port-free":
        return 0 if port_free(args.port) else 1
    elif args.command == "wait-health":
        return 0 if wait_health(args.url, args.timeout, args.pid) else 1
    else:
        metrics = run(args.plan, args.arm, args.acquisition, args.inputs_sha256, args.endpoint.rstrip("/"),
                      args.out, args.deadline_epoch)
        print(json.dumps({"arm": metrics["arm"], "status": metrics["status"], "events": metrics["events"],
                          "filings": len(metrics["filings"])}))
        return 0 if metrics["status"] == "completed" else 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
