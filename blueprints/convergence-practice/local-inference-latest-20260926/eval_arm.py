#!/usr/bin/env python3
"""Evaluate one frozen arm segment against a loopback OpenAI-compatible llama-server.

Standard library only. Raw model replies and server error bodies stay in a
private file; the public metrics file holds item codes, parse status, error
types and server timings, never filing text. The same file builds the frozen
server argv, reads the segment chain of earlier windows, and runs the read-only
preflight checks that window.sh calls before it stops the production unit.
"""
from __future__ import annotations

import argparse
from collections import namedtuple
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
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
MAX_ERROR_BYTES = 64 * 1024
CONTEXT_OVERFLOW = "exceed_context_size_error"
TIMING_FIELDS = ("prompt_n", "prompt_ms", "predicted_n", "predicted_ms", "predicted_per_second",
                 "draft_n", "draft_n_accepted")
BUILT_IN_MTP = {"type": "draft-mtp", "source": "main-model-mtp-layer", "n_max": 3}
WINDOW_ID = re.compile(r"w-[0-9]{8}T[0-9]{6}Z")
# Exit codes of `run`, which window.sh maps to an attempt status.
EXIT_COMPLETED, EXIT_STOPPED, EXIT_SEGMENT_BOUNDARY, EXIT_INTERRUPTED = 0, 3, 4, 5
# Attempt statuses that window.sh writes to an arm's window.json. Not-started
# attempts never launched a server and may be tried again in a later window; a
# boundary may be continued; every other status is a terminal failure.
NOT_STARTED = frozenset({"pending", "admission-refused", "memory-query-failed", "plan-error", "argv-failed",
                         "not-started-window-budget", "not-started-interrupted"})
METRICS_STATUS = {"completed": "completed", "segment-boundary": "segment_boundary"}

Reply = namedtuple("Reply", "status payload error body elapsed")

_SPEC = importlib.util.spec_from_file_location("li26_path_safety", REPO / "scripts/path_safety.py")
path_safety = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(path_safety)


class Interrupted(BaseException):
    """SIGTERM from window.sh while a segment runs; recorded, never resumed."""


def _interrupt(signum, frame):
    raise Interrupted()


def _ignore_interrupts():
    if signal.getsignal(signal.SIGTERM) is _interrupt:
        signal.signal(signal.SIGTERM, signal.SIG_IGN)


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
    """The frozen serving, sampling, guard and profile values this runner was written for."""
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
                       "request_seconds": 600, "startup_seconds": 300, "arm_seconds": 9600,
                       "minimum_segment_seconds": 1200, "restore_reserve_seconds": 900, "max_segments": 4,
                       "query_timeout_seconds": 10, "monitor_max_gap_seconds": 30}.items():
        if type(window[key]) is not int or window[key] != value:
            raise ValueError(f"frozen window value changed: {key}")
    ids = [arm["id"] for arm in plan["arms"]]
    if ids != ["C0", "C1", "C2", "B", "M", "X"] or plan["arms"][0]["role"] != "control":
        raise ValueError("frozen arm list changed")
    runtime = {"tag": plan["runtime"]["tag"], "commit": plan["runtime"]["commit"]}
    if runtime != {"tag": "b11146", "commit": "7fe450e19305b828c199d602c23a8337aaa1f03b"} or \
            any(arm["runtime"] != runtime for arm in plan["arms"]):
        raise ValueError("every arm must name the pinned b11146 runtime")
    for arm in plan["arms"]:
        if arm["support_status"] not in RUNNABLE:
            continue
        profile = arm["profile"]
        if type(profile["gpu_layers"]) is not int or type(profile["n_cpu_ffn"]) is not int or profile["n_cpu_ffn"] < 0:
            raise ValueError(f"arm {arm['id']}: frozen profile must name integer layer counts")
        if profile["draft"] not in (None, BUILT_IN_MTP):
            raise ValueError(f"arm {arm['id']}: only the main file's MTP layer may draft")
    if window["production_estimated_device_mib"] != arm_by_id(plan, "C0")["estimated_device_mib"]:
        raise ValueError("the production estimate must equal the C0 profile estimate")


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
    profile = arm["profile"]
    port = serving["port"] if port is None else port
    argv = [str(Path(runtime_dir) / "llama-server"), "--model", str(model_path(models_dir, arm["model"])),
            "--alias", alias(arm_id), "--host", serving["host"], "--port", str(port),
            "--ctx-size", str(serving["context"]), "--parallel", str(serving["parallel"]),
            "--gpu-layers", str(profile["gpu_layers"])]
    if profile["n_cpu_ffn"]:
        argv += ["--n-cpu-ffn", str(profile["n_cpu_ffn"])]
    argv += ["--fit", serving["fit"], "--threads", str(serving["threads"]),
             "--threads-batch", str(serving["threads_batch"]), "--batch-size", str(serving["batch"]),
             "--ubatch-size", str(serving["ubatch"]), "--cache-ram", str(serving["cache_ram_mib"]),
             *serving["flags"]]
    if profile["draft"]:
        # No --spec-draft-model: b11146 builds the MTP context on the target model's own MTP layer.
        argv += ["--spec-type", profile["draft"]["type"], "--spec-draft-n-max", str(profile["draft"]["n_max"])]
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
        model = runnable_arm(plan, arm_id)["model"]
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


def predict_admission(plan, arm_ids, free_mib, production_active):
    """Free memory expected once production stops, against the largest listed admission threshold."""
    required = max(admission_mib(plan, arm_id) for arm_id in arm_ids)
    predicted = free_mib + (plan["window"]["production_estimated_device_mib"] if production_active else 0)
    return {"free_mib": free_mib, "production_active": bool(production_active), "predicted_free_mib": predicted,
            "required_mib": required, "shortfall_mib": max(0, required - predicted)}


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
    """One request; an HTTP error keeps its body (bounded) for the private log and its error type."""
    request = urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json"})
    start = time.monotonic()
    try:
        with http.open(request, timeout=timeout) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            status = response.status
    except urllib.error.HTTPError as error:
        try:
            raw = error.read(MAX_ERROR_BYTES)
        except OSError:
            raw = b""
        finally:
            error.close()
        return Reply(error.code, None, f"http_{error.code}", raw, time.monotonic() - start)
    except (TimeoutError, socket.timeout):
        return Reply(None, None, "request_deadline", None, time.monotonic() - start)
    except urllib.error.URLError as error:
        timed_out = isinstance(error.reason, (TimeoutError, socket.timeout))
        return Reply(None, None, "request_deadline" if timed_out else "server_unavailable", None,
                     time.monotonic() - start)
    except (OSError, ValueError):
        return Reply(None, None, "server_unavailable", None, time.monotonic() - start)
    elapsed = time.monotonic() - start
    if len(raw) > MAX_RESPONSE_BYTES:
        return Reply(status, None, "response_too_large", raw[:MAX_ERROR_BYTES], elapsed)
    try:
        return Reply(status, json.loads(raw), None, None, elapsed)
    except ValueError:
        return Reply(status, None, "malformed_response", raw[:MAX_ERROR_BYTES], elapsed)


def error_details(body):
    """The server's error type and prompt size from a llama-server error body, or (None, None)."""
    try:
        error = json.loads(body).get("error")
    except (TypeError, ValueError, AttributeError):
        return None, None
    if not isinstance(error, dict):
        return None, None
    kind = error.get("type") if isinstance(error.get("type"), str) else None
    tokens = error.get("n_prompt_tokens") if type(error.get("n_prompt_tokens")) is int else None
    return kind, tokens


def well_formed(payload):
    if not isinstance(payload, dict) or not isinstance(payload.get("choices"), list) or not payload["choices"]:
        return False
    choice = payload["choices"][0]
    return isinstance(choice, dict) and isinstance(choice.get("message"), dict)


def score_reply(row, reply, request_seconds, segment):
    """Public per-filing record (no text), private raw record, and the stopping event, if any.

    Only a context overflow (HTTP 400, exceed_context_size_error) is a per-filing
    invalid output; every other server error, a deadline or an unreachable server
    is an event that stops the arm and fails criterion (4).
    """
    error, error_type, prompt_size = reply.error, None, None
    if reply.body is not None:
        error_type, prompt_size = error_details(reply.body)
    if error is None and reply.elapsed > request_seconds:
        error = "request_deadline"
    if error is None and (reply.status != 200 or not well_formed(reply.payload)):
        error = "malformed_response"
    event = None
    if error == "request_deadline":
        event = f"request-deadline:{row['accession']}"
    elif error == "server_unavailable":
        event = f"server-unavailable:{row['accession']}"
    elif error is not None:
        if reply.status == 400 and error_type == CONTEXT_OVERFLOW:
            error = "context_overflow"
        else:
            event = f"server-error:{reply.status if reply.status is not None else 'none'}:{row['accession']}"
    content = finish = None
    timings, usage = {}, {}
    if error is None:
        choice = reply.payload["choices"][0]
        content = choice["message"].get("content")
        finish = choice.get("finish_reason")
        timings = reply.payload.get("timings") if isinstance(reply.payload.get("timings"), dict) else {}
        usage = reply.payload.get("usage") if isinstance(reply.payload.get("usage"), dict) else {}
    items, parse_status = parse_items(content) if error is None else (None, "invalid")
    public = {"accession": row["accession"], "gold": row["labels"], "predicted": items,
              "parse_status": parse_status, "finish_reason": finish, "http_status": reply.status, "error": error,
              "error_type": error_type, "n_prompt_tokens": prompt_size if error == "context_overflow" else None,
              "prompt_tokens": usage.get("prompt_tokens"), "completion_tokens": usage.get("completion_tokens"),
              "elapsed_ms": None if reply.elapsed is None else round(reply.elapsed * 1000, 1), "segment": segment}
    public.update({field: timings.get(field) for field in TIMING_FIELDS})
    private = {"accession": row["accession"], "http_status": reply.status, "error": error, "response": reply.payload,
               "error_body": None if reply.body is None else reply.body.decode("utf-8", "replace")}
    return public, private, event


def not_attempted(row):
    public = {"accession": row["accession"], "gold": row["labels"], "predicted": None, "parse_status": "invalid",
              "finish_reason": None, "http_status": None, "error": "not_attempted", "error_type": None,
              "n_prompt_tokens": None, "prompt_tokens": None, "completion_tokens": None, "elapsed_ms": None,
              "segment": None}
    public.update({field: None for field in TIMING_FIELDS})
    return public


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


def _read_json(path):
    try:
        raw = Path(path).read_bytes()
        return raw, json.loads(raw)
    except (OSError, ValueError):
        return None, None


def arm_attempts(state_dir, arm_id):
    """Every recorded attempt of one arm, in window order (window ids sort by UTC start)."""
    runs = path_safety.refuse_untrusted_symlinks(Path(state_dir) / "runs", "state symlink refused")
    attempts = []
    if not runs.is_dir():
        return attempts
    for window_dir in sorted(runs.iterdir()):
        arm_dir = window_dir / arm_id
        if (not WINDOW_ID.fullmatch(window_dir.name) or window_dir.is_symlink() or not window_dir.is_dir()
                or arm_dir.is_symlink() or not arm_dir.is_dir()):
            continue
        _, record = _read_json(arm_dir / "window.json")
        raw, metrics = _read_json(arm_dir / "eval" / "metrics.json")
        status = record.get("status") if isinstance(record, dict) else None
        kind = ("not_started" if status in NOT_STARTED else "completed" if status == "completed"
                else "boundary" if status == "segment-boundary" else "failed")
        attempts.append({"window": window_dir.name, "dir": arm_dir, "status": status, "kind": kind,
                         "window_record": record if isinstance(record, dict) else None,
                         "metrics": metrics if isinstance(metrics, dict) else None,
                         "metrics_sha256": hashlib.sha256(raw).hexdigest() if raw is not None else None})
    return attempts


def read_chain(plan, state_dir, arm_id):
    """The started attempts of one arm as its segment chain, plus every inconsistency found.

    A started attempt may follow only a clean segment boundary; anything after a
    completed or failed attempt is a re-run and is reported, never used.
    """
    chain = [attempt for attempt in arm_attempts(state_dir, arm_id) if attempt["kind"] != "not_started"]
    problems = []
    for index, attempt in enumerate(chain):
        position, window = index + 1, attempt["window"]
        if index and chain[index - 1]["kind"] != "boundary":
            problems.append(f"rerun-after-terminal-attempt:{window}")
        if attempt["window_record"] is not None and attempt["window_record"].get("segment") != position:
            problems.append(f"segment-number-mismatch:{window}")
        metrics = attempt["metrics"]
        if attempt["status"] in METRICS_STATUS:
            if metrics is None or metrics.get("status") != METRICS_STATUS[attempt["status"]]:
                problems.append(f"metrics-status-mismatch:{window}")
        if metrics is not None:
            previous = chain[index - 1]["metrics_sha256"] if index else None
            if metrics.get("arm") != arm_id or metrics.get("segment") != position:
                problems.append(f"metrics-identity-mismatch:{window}")
            if metrics.get("previous_metrics_sha256") != previous:
                problems.append(f"segment-chain-broken:{window}")
    if len(chain) > plan["window"]["max_segments"]:
        problems.append("segments-exceeded")
    return chain, problems


def next_segment(plan, state_dir, arm_id):
    """(segment number, previous window id or None) for an arm's next attempt; refuses otherwise."""
    runnable_arm(plan, arm_id)
    chain, problems = read_chain(plan, state_dir, arm_id)
    if problems:
        raise ValueError(f"arm {arm_id} has an inconsistent record: {problems[0]}")
    if not chain:
        return 1, None
    last = chain[-1]
    if last["kind"] == "completed":
        raise ValueError(f"arm {arm_id} is already complete ({last['window']})")
    if last["kind"] == "failed":
        raise ValueError(f"arm {arm_id} ended as {last['status'] or 'unrecorded'} in {last['window']}; "
                         "no re-run under this plan")
    if len(chain) >= plan["window"]["max_segments"]:
        raise ValueError(f"arm {arm_id} has used all {len(chain)} segments")
    return len(chain) + 1, last["window"]


def load_previous(previous_dir, arm_id, segment, expected, rows):
    """Earlier results carried verbatim from the previous segment, and that file's SHA-256."""
    path = path_safety.refuse_untrusted_symlinks(Path(previous_dir) / "metrics.json",
                                                 "previous metrics symlink refused")
    raw = path.read_bytes()
    previous = json.loads(raw)
    for key, value in {"arm": arm_id, "segment": segment - 1, "status": "segment_boundary", "events": [],
                       **expected}.items():
        if previous.get(key) != value:
            raise ValueError(f"previous segment does not continue this arm: {key}")
    if [entry["accession"] for entry in previous["filings"]] != [row["accession"] for row in rows]:
        raise ValueError("previous segment covers different filings")
    carried = {entry["accession"]: entry for entry in previous["filings"] if entry.get("segment") is not None}
    return carried, hashlib.sha256(raw).hexdigest()


def run(plan_path, arm_id, acquisition, inputs_sha256, endpoint, out, deadline_epoch, segment=1,
        previous=None, http=None, clock=time.time):
    """One segment: requests start only while a whole request deadline still fits before `deadline_epoch`."""
    plan = load_plan(plan_path)
    verify_frozen(plan)
    arm = runnable_arm(plan, arm_id)
    template = prompt_template(plan)
    rows = load_inputs(acquisition, inputs_sha256)
    if not 1 <= segment <= plan["window"]["max_segments"] or (segment == 1) != (previous is None):
        raise ValueError("segment number and previous segment disagree")
    identity = {"plan_sha256": digest(plan_path), "prompt_sha256": plan["prompt_sha256"],
                "inputs_sha256": inputs_sha256, "model_sha256": arm["model"]["sha256"]}
    carried, previous_sha256 = ({}, None) if previous is None else load_previous(
        previous, arm_id, segment, identity, rows)
    out = path_safety.refuse_untrusted_symlinks(out, "output symlink refused")
    out.mkdir(mode=0o700)
    http = http or opener()
    request_seconds = plan["window"]["request_seconds"]
    metrics = {"schema_version": 1, "kind": "local_inference_latest_arm_metrics", "arm": arm_id,
               "segment": segment, "previous_metrics_sha256": previous_sha256, **identity,
               "profile": arm["profile"], "deadline_epoch": deadline_epoch, "request_seconds": request_seconds,
               "started_utc": now_utc(), "status": "stopped", "events": [], "server": None,
               "filings": [], "no_document_text": True}
    raw_path = out / "raw.private.jsonl"
    write_private(raw_path, b"")
    attempted = {}
    try:
        metrics["server"] = check_server(http, endpoint, arm_id, arm)
        status = "completed"
        with raw_path.open("ab") as raw_log:
            for row in rows:
                if row["accession"] in carried:
                    continue
                if deadline_epoch - clock() < request_seconds:
                    status = "segment_boundary"
                    break
                reply = post_json(http, endpoint + "/v1/chat/completions",
                                  build_request(plan, template, arm_id, row["input"]), request_seconds)
                public, private, event = score_reply(row, reply, request_seconds, segment)
                attempted[row["accession"]] = public
                raw_log.write(json.dumps(private, sort_keys=True).encode() + b"\n")
                raw_log.flush()
                if event:
                    metrics["events"].append(event)
                    status = "stopped"
                    break
        metrics["status"] = status
    except Interrupted:
        metrics["status"] = "interrupted"
        metrics["events"].append("interrupted")
    except (OSError, ValueError) as error:
        metrics["events"].append("server-check-failed:" + type(error).__name__)
    finally:
        _ignore_interrupts()
        metrics["filings"] = [carried.get(row["accession"]) or attempted.get(row["accession"]) or not_attempted(row)
                              for row in rows]
        metrics["finished_utc"] = now_utc()
        write_private(out / "metrics.json", (json.dumps(metrics, indent=2, sort_keys=True) + "\n").encode())
    return metrics


def exit_code(status):
    return {"completed": EXIT_COMPLETED, "segment_boundary": EXIT_SEGMENT_BOUNDARY,
            "interrupted": EXIT_INTERRUPTED}.get(status, EXIT_STOPPED)


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
    predict = commands.add_parser("predict")
    predict.add_argument("--plan", type=Path, default=PLAN)
    predict.add_argument("--arm", action="append", required=True)
    predict.add_argument("--free", type=int, required=True)
    predict.add_argument("--production-active", type=int, choices=(0, 1), required=True)
    segment = commands.add_parser("next-segment")
    segment.add_argument("--plan", type=Path, default=PLAN)
    segment.add_argument("--state-dir", type=Path, required=True)
    segment.add_argument("--arm", required=True)
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
    evaluate.add_argument("--segment", type=int, default=1)
    evaluate.add_argument("--previous", type=Path)
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
    elif args.command == "predict":
        result = predict_admission(load_plan(args.plan), args.arm, args.free, args.production_active)
        print(json.dumps(result, sort_keys=True), file=sys.stderr)
        return 0 if result["shortfall_mib"] == 0 else 1
    elif args.command == "next-segment":
        try:
            number, previous = next_segment(load_plan(args.plan), args.state_dir, args.arm)
        except ValueError as error:
            print(f"next-segment: {error}", file=sys.stderr)
            return 1
        print(number, previous or "-")
    elif args.command == "port-free":
        return 0 if port_free(args.port) else 1
    elif args.command == "wait-health":
        return 0 if wait_health(args.url, args.timeout, args.pid) else 1
    else:
        signal.signal(signal.SIGTERM, _interrupt)
        metrics = run(args.plan, args.arm, args.acquisition, args.inputs_sha256, args.endpoint.rstrip("/"),
                      args.out, args.deadline_epoch, args.segment, args.previous)
        print(json.dumps({"arm": metrics["arm"], "segment": metrics["segment"], "status": metrics["status"],
                          "events": metrics["events"], "filings": len(metrics["filings"])}))
        return exit_code(metrics["status"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
