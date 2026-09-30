"""Host-owned start/wait/result files around the native agent-server REST API.

OpenHands/software-agent-sdk@fcc102a conversation_router.py:163-228,257-287,
304-321. This adapter does not implement an agent loop or an HTTP server.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import tempfile
import time
import uuid

from recipe import HERE, read_json
from host import (AGENT_LIMITS, DEFAULT_PORT, docker_args, grade, logged_command, owned_port, private_file,
                  result_exit, session_files, teardown_attempt, utc_now, verify_isolation, write_json)
from receipt import create_receipt, read_bounded


TERMINAL = {"finished", "error", "stuck"}
# F16 bound: a termination label is kept only as a refinement of the REST
# execution_status. The event-store label can turn "error" into an agent limit
# (exit 3 -> 1) but never stands in for "finished", the only route to exit 0.
PERMITTED_TERMINATIONS = {"finished": {"finished"}, "stuck": {"stuck"},
                          "error": {"error", "max_iterations_reached"}}
# Latest ConversationErrorEvent only. SDK@fcc102a event_router.py:68-139 serves
# the page; event_service.py:456-460 matches kind on the module-qualified class
# name; models.py:95-99 defines TIMESTAMP_DESC.
ERROR_EVENT_SEARCH = ("/events/search?kind=openhands.sdk.event.conversation_error.ConversationErrorEvent"
                      "&sort_order=TIMESTAMP_DESC&limit=1")
GOAL_EVENT_SEARCH = ("/events/search?kind=openhands.sdk.event.conversation_state.ConversationStateUpdateEvent"
                     "&sort_order=TIMESTAMP_DESC&limit=100")
# Plan E3: each native route has exactly one method. POST starts or
# interrupts a conversation; GET only reads (conversation_router.py:163-228,
# 257-287, 304-321; event_router.py:68-139).
CONVERSATION = r"/api/conversations/[a-f0-9-]{36}"
NATIVE_ROUTES = (
    ("POST", r"/api/conversations"),
    ("POST", CONVERSATION + r"/interrupt"),
    ("POST", CONVERSATION + r"/run"),
    ("POST", CONVERSATION + r"/goal"),
    ("POST", CONVERSATION + r"/goal/stop"),
    ("POST", CONVERSATION + r"/goal/resume"),
    ("GET", CONVERSATION),
    ("GET", CONVERSATION + r"/agent_final_response"),
    ("GET", CONVERSATION + re.escape(ERROR_EVENT_SEARCH)),
    ("GET", CONVERSATION + re.escape(GOAL_EVENT_SEARCH)),
)


def native_goal_status(conversation_id, port, headers):
    """Lifecycle only: model-writable event-store output cannot certify quality."""
    page = api_request("GET", f"/api/conversations/{conversation_id}{GOAL_EVENT_SEARCH}",
                       port=port, headers=headers)
    items = page.get("items") if isinstance(page, dict) else None
    if isinstance(items, list):
        for event in items:
            if isinstance(event, dict) and event.get("key") == "goal":
                value = event.get("value")
                if (isinstance(value, dict) and type(value.get("active")) is bool
                        and value.get("status") in {"running", "complete", "capped", "interrupted"}):
                    return {"active": value["active"], "status": value["status"]}
    raise ValueError("native_goal_status_unavailable")


def server_url(port):
    return f"http://127.0.0.1:{owned_port(port)}"


def curl_json(url, *, method="GET", headers=None, body=None):
    args = ["curl", "--silent", "--show-error", "--fail", "--noproxy", "*",
            "--connect-timeout", "5", "--max-time", "30", "--max-filesize", "4194304", "-X", method]
    if headers:
        args += ["-H", "@" + str(private_file(headers))]
    if body:
        args += ["-H", "Content-Type: application/json", "--data-binary", "@" + str(body)]
    # No credential values in argv, OTel or printed errors; response is bounded.
    with tempfile.TemporaryFile() as output:
        subprocess.run([*args, url], stdout=output, stderr=subprocess.DEVNULL, check=True, timeout=35)
        output.seek(0)
        raw = output.read(4 * 1024 * 1024 + 1)
    if len(raw) > 4 * 1024 * 1024:
        raise ValueError("native_response_too_large")
    return json.loads(raw)


def api_request(method, path, *, headers, body=None, port=DEFAULT_PORT):
    """headers is the attempt's host.session_files header file, checked by private_file."""
    if not any(method == allowed and re.fullmatch(pattern, path) for allowed, pattern in NATIVE_ROUTES):
        raise ValueError("unexpected_native_route")
    return curl_json(server_url(port) + path, method=method, headers=headers, body=body)


def agent_termination(conversation_id, execution, port, headers):
    """Classify a terminal native status; agent limits keep their partial patch.

    SDK@fcc102a conversation/state.py:48-79 makes finished, error and stuck
    terminal. local_conversation.py:753-755 sets STUCK; :2021-2043 and
    :2339-2360 set ERROR with ConversationErrorEvent(source="environment",
    code="MaxIterationsReached"). Every other ERROR stays an infrastructure
    failure. The event page is agent-server reported, and the server shares the
    model terminal's UID and store, so it selects only exit 1 or exit 3; it can
    never produce a pass. The module-qualified kind is source-reviewed, not yet
    observed from the image binary; a mismatch fails closed to "error".
    """
    if execution in {"finished", "stuck"}:
        return execution
    if execution != "error":
        return "error"
    page = api_request("GET", f"/api/conversations/{conversation_id}{ERROR_EVENT_SEARCH}", port=port, headers=headers)
    items = page.get("items") if isinstance(page, dict) else None
    if (isinstance(items, list) and len(items) == 1 and isinstance(items[0], dict)
            and {key: items[0].get(key) for key in ("kind", "source", "code")}
            == {"kind": "ConversationErrorEvent", "source": "environment", "code": "MaxIterationsReached"}):
        return "max_iterations_reached"
    return "error"


def compression_snapshot():
    # OmniRoute@a58000c compression/route.ts:13-24, compressionAnalytics.ts:52-55.
    try:
        value = curl_json("http://127.0.0.1:20129/api/analytics/compression?since=all",
                          headers=os.environ.get("OPENHANDS_COMPRESSION_HEADERS"))
        selected = {k: value[k] for k in ("totalRequests", "totalTokensSaved")}
        if all(isinstance(v, int) and not isinstance(v, bool) and v >= 0 for v in selected.values()):
            return selected
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        pass
    return None


def compression_delta(before, after):
    keys = ("totalRequests", "totalTokensSaved")
    if (not isinstance(before, dict) or not isinstance(after, dict)
            or any(not isinstance(snapshot.get(k), int) or isinstance(snapshot[k], bool) or snapshot[k] < 0
                   for snapshot in (before, after) for k in keys)
            or any(after[k] < before[k] for k in keys)):
        return {"delta": None, "status": "unavailable_or_counter_reset"}
    return {"delta": {k: after[k] - before[k] for k in keys}, "status": "observed",
            "basis": "entry gateway global analytics delta; separate from call_logs usage; concurrent callers may contribute"}


def server_command(pins, name, mounts, network, env_file):
    # Keep the image ENTRYPOINT. Its binary target is Dockerfile:580-590, not
    # the source target at :571. Supported preload: __main__.py:74-135,240-273.
    # O1: the server joins only <stem>-int and publishes nothing; host ingress
    # is the proxy's loopback port (host.proxy_commands).
    return [*docker_args(pins, name, network=network), *mounts, "--detach", "--env-file", str(env_file),
            "--env", "OH_ENABLE_VSCODE=0", "--env", "OH_CONVERSATIONS_PATH=/state/server/conversations",
            "--env", "OH_WORKSPACE_PATH=/workspace", "--env", "OH_BASH_EVENTS_DIR=/state/server/bash_events",
            "--env", "OPENHANDS_OWNED_CONTAINER=1", "--workdir", "/workspace",
            pins["image"]["ref"], "--extra-python-path", "/recipe", "--import-modules", "server_transport"]


def check_server(body, *, port=DEFAULT_PORT):
    """Native health/docs gate, then cross-check SDK output against live OpenAPI."""
    base = server_url(port)
    deadline = time.monotonic() + 60
    while True:
        try:
            for path in ("/health", "/docs"):
                subprocess.run(["curl", "-fsS", "--noproxy", "*", "--max-time", "5", "-o", os.devnull,
                                base + path], check=True, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, timeout=6)
            break
        except (OSError, subprocess.SubprocessError):
            if time.monotonic() >= deadline:
                raise RuntimeError("native_server_health_failed")
            time.sleep(1)
    schema = curl_json(base + "/openapi.json")
    request = schema["paths"]["/api/conversations"]["post"]["requestBody"]["content"]["application/json"]["schema"]
    if "$ref" in request:
        request = schema["components"]["schemas"][request["$ref"].split("/")[-1]]
    if (not set(request.get("required", [])) <= set(body)
            or not set(body) <= set(request["properties"])):
        raise ValueError("live_openapi_request_mismatch")


def stop_server(result, status=None):
    """Tear down the attempt at result = <state>/runs/<run-id>/<arm> (host.begin_attempt).

    host.teardown_attempt removes the proxy, the server and both networks by
    exact name and deletes the key files after confirmed container removal.
    """
    try:
        return teardown_attempt(result.parents[2], result.parent.name, result.name)
    except ValueError:
        return False


def finish_result(result, status, window):
    removed = stop_server(result, status)
    execution = status.get("execution_status")
    termination = status.get("agent_termination") or execution
    permitted = PERMITTED_TERMINATIONS.get(execution, set()) if isinstance(execution, str) else set()
    if not isinstance(termination, str) or termination not in permitted:
        termination = "error"
    window["agent_termination"] = termination
    window["worker_exit_code"] = 0 if termination == "finished" else 1
    # A partial patch after an agent limit is still officially graded; only
    # other native errors skip export (exit 3).
    graded = termination == "finished" or termination in AGENT_LIMITS
    if not graded:
        window["failure_stage"] = "agent"
    checked = {"upstream_resolved": None, "grader_exit_code": None}
    stage = "export"
    try:
        if not removed:
            raise RuntimeError("worker_removal_not_confirmed")
        if graded:
            task = read_json(result / "task-identity.json")
            workspace = result / "workspace"
            # git/git@v2.43.0 Documentation/git.txt (GIT_CONFIG_GLOBAL/NOSYSTEM)
            # and diff-options.txt (--no-ext-diff/--no-textconv). A candidate's
            # .gitattributes must not activate a host-global executable filter.
            git_env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
            if logged_command(["git", "-C", str(workspace), "add", "-A"],
                              result / "stage-patch.log", cwd=result, timeout=60, env=git_env):
                raise RuntimeError("patch_export_failed")
            patch_text = subprocess.check_output([
                "git", "-C", str(workspace), "--no-pager", "diff", "--no-color", "--no-ext-diff", "--no-textconv",
                "--cached", task["base_commit"]], text=True, timeout=60, env=git_env)
            (result / "output.jsonl").write_text(json.dumps({"instance_id": task["instance_id"],
                "test_result": {"git_patch": patch_text}, "error": None}) + "\n")
            datasets = list(result.glob("dataset.*"))
            if len(datasets) != 1:
                raise ValueError("one_frozen_dataset_required")
            prefix = Path.home() / ".local/share/codex-ecosystem/tools" / ("openhands-" + read_json(HERE / "pins.json")["version"])
            stage = "grader"
            checked = grade(prefix, result, datasets[0], task["instance_id"], window["run_id"])
    except (Exception, KeyboardInterrupt):
        window["failure_stage"] = stage
    write_json(result / "window.json", window)
    write_json(result / "check.json", checked)
    return create_receipt(result)


def execute(action, state, run_id, arm):
    """Exactly one native POST, bounded polling, deterministic host receipt."""
    if not re.fullmatch(r"rw-openhands-[a-z0-9-]{1,64}", run_id) or arm not in {"control", "engines-on"}:
        print(json.dumps({"run_id": run_id, "arm": arm, "receipt": None, "failure_stage": "preflight",
                          "task_passed": False, "evidence_complete": False}))
        return 3
    result = state / "runs" / run_id / arm
    receipt_path = result / "receipt.json"
    status, window = {}, {"run_id": run_id, "arm": arm}
    stage, code, receipt = action, 0, {"task_passed": False, "evidence_complete": False, "failure_stage": None}
    lock = state / "active-dispatch.json"
    owns_lock = False
    try:
        if result.resolve() != result.absolute():
            raise ValueError("owned_result_must_not_follow_symlinks")
        status = json.loads(read_bounded(result / "status.json"))
        window = json.loads(read_bounded(result / "window.json"))
        if window.get("run_id") != run_id or window.get("arm") != arm:
            raise ValueError("attempt_identity_mismatch")
        # Prepared by host.py into host-owned status.json; re-validated on read.
        port = owned_port(status.get("port", DEFAULT_PORT))
        # Derived from the validated identity only; curl_json re-checks the file.
        headers = session_files(state, run_id, arm)[1]
        if action == "start":
            if status.get("status") != "prepared":
                print(json.dumps({"run_id": run_id, "arm": arm, "receipt": str(receipt_path),
                                  "failure_stage": "start", "task_passed": False, "evidence_complete": False}))
                return 3  # Do not mutate the running attempt or release its lock.
            # Plan E1/G7: a fresh P0-P2 receipt bound to this live topology,
            # checked before the serial lock. A refusal changes nothing; run
            # `host.py probe` again, or tear the attempt down.
            try:
                verify_isolation(state, run_id, arm, port)
            except Exception:
                print(json.dumps({"run_id": run_id, "arm": arm, "receipt": str(receipt_path),
                                  "failure_stage": "probe", "task_passed": False, "evidence_complete": False}))
                return 3
            try:
                fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                print(json.dumps({"run_id": run_id, "arm": arm, "receipt": str(receipt_path),
                                  "failure_stage": "start", "task_passed": False, "evidence_complete": False}))
                return 3  # Another invocation owns the serial reservation.
            with os.fdopen(fd, "w") as stream:
                json.dump({"run_id": run_id, "arm": arm}, stream)
            owns_lock = True
            status.update(status="starting", deadline=time.time() + 1200)
            write_json(result / "status.json", status)
            window["compression_before"] = compression_snapshot() if arm == "engines-on" else None
            window["started_at"] = utc_now()
            window["finished_at"] = None
            write_json(result / "window.json", window)
            response = api_request("POST", "/api/conversations", body=result / "start.json", port=port, headers=headers)
            conversation_id = str(uuid.UUID(response["id"]))
            status.update(status="running", conversation_id=conversation_id)
            if window.get("profile") == "completion-review":
                write_json(result / "goal-request.json", {
                    "objective": read_bounded(result / "input/task.txt"), "max_iterations": 3,
                })
                api_request("POST", f"/api/conversations/{conversation_id}/goal",
                            body=result / "goal-request.json", port=port, headers=headers)
                status["goal_review"] = True
        elif action in {"interrupt", "resume"}:
            expected = "running" if action == "interrupt" else "paused"
            if status.get("status") != expected:
                print(json.dumps({"run_id": run_id, "arm": arm, "receipt": str(receipt_path),
                                  "failure_stage": action, "task_passed": False, "evidence_complete": False}))
                return 3
            if json.loads(read_bounded(lock)) != {"run_id": run_id, "arm": arm}:
                raise ValueError("recovery_requires_owned_serial_reservation")
            conversation_id = str(uuid.UUID(status["conversation_id"]))
            if action == "resume" and time.time() >= status["deadline"]:
                raise TimeoutError("native_conversation_deadline")
            endpoint = ("goal/stop" if action == "interrupt" else "goal/resume") if status.get("goal_review") else (
                "interrupt" if action == "interrupt" else "run")
            api_request("POST", f"/api/conversations/{conversation_id}/{endpoint}", port=port, headers=headers)
            status.update(status="paused" if action == "interrupt" else "running")
            write_json(result / (action + ".json"), {
                "action": action, "recorded_at": utc_now(), "native_conversation_preserved": True,
                "deadline_extended": False,
            })
        elif action == "wait":
            if status.get("status") != "running":
                raise ValueError("running_attempt_required")
            conversation_id = str(uuid.UUID(status["conversation_id"]))
            while True:
                if time.time() >= status["deadline"]:
                    stage = "deadline"
                    try:
                        api_request("POST", f"/api/conversations/{conversation_id}/interrupt", port=port, headers=headers)
                    finally:
                        raise TimeoutError("native_conversation_deadline")
                response = api_request("GET", f"/api/conversations/{conversation_id}", port=port, headers=headers)
                execution = response["execution_status"]
                if execution in TERMINAL:
                    if status.get("goal_review"):
                        goal = native_goal_status(conversation_id, port, headers)
                        if goal["active"]:
                            time.sleep(min(15, max(0, status["deadline"] - time.time())))
                            continue
                        status["goal_status"] = goal["status"]
                    status.update(status="terminal", execution_status=execution)
                    window["finished_at"] = utc_now()
                    if arm == "engines-on":
                        window["compression"] = compression_delta(window.pop("compression_before", None), compression_snapshot())
                    break
                if execution not in {"idle", "running", "paused", "waiting_for_confirmation"}:
                    raise ValueError("unknown_native_execution_status")
                time.sleep(min(15, max(0, status["deadline"] - time.time())))
        elif action == "result" and status.get("status") == "collected":
            # Native result is a GET; keep host collection repeatable after the
            # server has been removed, without regrading or overwriting evidence.
            receipt = json.loads(read_bounded(receipt_path))
            code = result_exit(receipt)
        elif action == "result":
            if status.get("status") != "terminal":
                raise ValueError("terminal_attempt_required")
            conversation_id = str(uuid.UUID(status["conversation_id"]))
            response = api_request("GET", f"/api/conversations/{conversation_id}/agent_final_response", port=port,
                                   headers=headers)
            if not isinstance(response.get("response"), str):
                raise ValueError("native_final_response_contract")
            write_json(result / "final-response.json", response)
            status["agent_termination"] = agent_termination(conversation_id, status.get("execution_status"), port, headers)
            receipt = finish_result(result, status, window)
            write_json(receipt_path, receipt)
            code = result_exit(receipt)
            status.update(status="collected")
        else:
            raise ValueError("unknown_dispatch_action")
        write_json(result / "window.json", window)
        write_json(result / "status.json", status)
    except (Exception, KeyboardInterrupt) as exc:
        # Never export raw exceptions (curl paths, header material, server text).
        code = 3
        receipt = {"arm": arm, "failure_stage": stage, "failure_type": type(exc).__name__,
                   "task_passed": False, "evidence_complete": False}
        if result.is_dir() and result.resolve() == result.absolute():
            write_json(receipt_path, receipt)
            write_json(result / "status.json", {**status, "status": "failed", "failure_stage": stage})
            if owns_lock or action in {"wait", "result", "interrupt", "resume"}:
                try:
                    stop_server(result, status)
                except (OSError, ValueError, subprocess.SubprocessError):
                    pass  # Keep primary failure; cleanup receipt records uncertainty.
    finally:
        if (code == 3 or action == "result") and lock.is_file():
            try:
                if json.loads(read_bounded(lock)) == {"run_id": run_id, "arm": arm}:
                    lock.unlink()
            except (OSError, ValueError):
                pass
    print(json.dumps({"run_id": run_id, "arm": arm, "receipt": str(receipt_path),
                      **{k: receipt.get(k) for k in ("failure_stage", "task_passed", "evidence_complete")}}))
    return code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("start", "wait", "result", "interrupt", "resume"))
    parser.add_argument("--run-id", default=os.environ.get("OPENHANDS_RUN_ID"), required="OPENHANDS_RUN_ID" not in os.environ)
    parser.add_argument("--arm", choices=("control", "engines-on"), default=os.environ.get("OPENHANDS_ARM", "control"))
    args = parser.parse_args()
    os.umask(0o077)
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    state = Path.home() / ".local/state/native-agent-stack/runtime-workers/openhands"
    return execute(args.action, state, args.run_id, args.arm)


if __name__ == "__main__":
    raise SystemExit(main())
