"""Temporal arm for wave-2 gaps 6 and 7: a two-activity workflow on a local
`temporal server start-dev` (loopback ports, temp sqlite file).

  temporal_arm.py worker --address A --spans FILE --marks DIR
  temporal_arm.py drive  --address A --temporal CLI --work DIR --spans FILE --out FILE

The same shape as the Dagu kill DAG: step1 writes a started marker, sleeps
(heartbeating once per second), writes a finished marker; step2 depends on it.
Scenarios driven: happy, retry (step1 raises on attempt 1), fail_hard
(non-retryable step1 failure, workflow failed), cancel (workflow cancel while
step1 sleeps) and kill (SIGKILL the worker process group mid-step1, then start a
new worker). Spans come from the SDK's TracingInterceptor, exported by a
SimpleSpanProcessor to a JSON-lines file per process.
"""
import argparse
import asyncio
import json
import os
import signal
import subprocess
import sys
import time
from datetime import timedelta
from pathlib import Path

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult
from temporalio import activity, workflow
from temporalio.client import Client, WorkflowFailureError
from temporalio.common import RetryPolicy
from temporalio.contrib.opentelemetry import TracingInterceptor
from temporalio.exceptions import ApplicationError
from temporalio.worker import UnsandboxedWorkflowRunner, Worker

TASK_QUEUE = "g2dqo-two-step"


def utc():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class JsonLinesExporter(SpanExporter):
    def __init__(self, path):
        self.path = path

    def export(self, spans):
        with open(self.path, "a") as f:
            for s in spans:
                f.write(json.dumps({
                    "name": s.name, "trace_id": format(s.context.trace_id, "032x"),
                    "span_id": format(s.context.span_id, "016x"),
                    "parent_id": format(s.parent.span_id, "016x") if s.parent else None,
                    "start_ns": s.start_time, "end_ns": s.end_time,
                    "status": s.status.status_code.name,
                    "attributes": dict(s.attributes or {}),
                    "service": s.resource.attributes.get("service.name"),
                }) + "\n")
        return SpanExportResult.SUCCESS


def setup_tracing(path, service):
    provider = TracerProvider(resource=Resource.create({"service.name": service}))
    provider.add_span_processor(SimpleSpanProcessor(JsonLinesExporter(path)))
    trace.set_tracer_provider(provider)


@activity.defn
async def step1(cfg: dict) -> str:
    info = activity.info()
    marks = Path(cfg["marks"])
    with open(marks / f"{cfg['wid']}.step1.started", "a") as f:
        f.write(f"{int(time.time())} attempt={info.attempt} pid={os.getpid()}\n")
    if cfg.get("mode") == "retry" and info.attempt == 1:
        raise ApplicationError("injected failure on attempt 1")
    if cfg.get("mode") == "fail_hard":
        raise ApplicationError("injected non-retryable failure", non_retryable=True)
    for _ in range(cfg["sleep"]):
        activity.heartbeat()
        await asyncio.sleep(1)
    with open(marks / f"{cfg['wid']}.step1.finished", "a") as f:
        f.write(f"{int(time.time())} attempt={info.attempt} pid={os.getpid()}\n")
    return f"step1 done attempt {info.attempt}"


@activity.defn
async def step2(cfg: dict) -> str:
    with open(Path(cfg["marks"]) / f"{cfg['wid']}.step2.ran", "a") as f:
        f.write(f"{int(time.time())} pid={os.getpid()}\n")
    return "step2 done"


@workflow.defn
class TwoStep:
    @workflow.run
    async def run(self, cfg: dict) -> list:
        opts = dict(start_to_close_timeout=timedelta(seconds=120), heartbeat_timeout=timedelta(seconds=5),
                    retry_policy=RetryPolicy(initial_interval=timedelta(seconds=1), maximum_attempts=5))
        a = await workflow.execute_activity(step1, cfg, **opts)
        b = await workflow.execute_activity(step2, cfg, **opts)
        return [a, b]


async def worker_main(a):
    setup_tracing(a.spans, "g2dqo-temporal-worker")
    client = await Client.connect(a.address, interceptors=[TracingInterceptor()])
    w = Worker(client, task_queue=TASK_QUEUE, workflows=[TwoStep], activities=[step1, step2],
               workflow_runner=UnsandboxedWorkflowRunner())
    print(f"worker pid {os.getpid()} polling", flush=True)
    await w.run()


def spawn_worker(a, work, label):
    log = open(work / f"worker-{label}.log", "w")
    p = subprocess.Popen([sys.executable, __file__, "worker", "--address", a.address,
                          "--spans", str(work / f"spans-worker-{label}.jsonl")],
                         stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    time.sleep(3)
    return p


def stop(p, sig=signal.SIGTERM):
    if p.poll() is None:
        try:
            os.killpg(p.pid, sig)
        except ProcessLookupError:
            pass
        try:
            p.wait(timeout=20)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid, signal.SIGKILL)
            p.wait(timeout=10)


def history(a, wid, work):
    p = subprocess.run([a.temporal, "workflow", "show", "--address", a.address, "--workflow-id", wid,
                        "--output", "json"], capture_output=True, text=True, timeout=60)
    (work / f"history-{wid}.json").write_text(p.stdout)
    try:
        events = json.loads(p.stdout).get("events", [])
    except Exception:
        return {"exit": p.returncode, "stderr": p.stderr[-300:], "events": []}
    summary = []
    for e in events:
        et = e.get("eventType", "")
        item = {"id": e.get("eventId"), "type": et.replace("EVENT_TYPE_", "")}
        attrs = next((v for k, v in e.items() if k.endswith("EventAttributes")), {}) or {}
        if "attempt" in attrs:
            item["attempt"] = attrs["attempt"]
        if "lastFailure" in attrs:
            item["lastFailure"] = (attrs["lastFailure"] or {}).get("message")
        if "failure" in attrs:
            item["failure"] = (attrs["failure"] or {}).get("message")
        if "timeoutType" in attrs:
            item["timeoutType"] = attrs["timeoutType"]
        if "activityType" in attrs:
            item["activity"] = attrs["activityType"].get("name")
        summary.append(item)
    return {"exit": p.returncode, "events": summary}


async def drive(a):
    work = Path(a.work)
    marks = work / "marks"
    marks.mkdir(parents=True, exist_ok=True)
    setup_tracing(a.spans, "g2dqo-temporal-client")
    client = await Client.connect(a.address, interceptors=[TracingInterceptor()])
    out = {"started_at_utc": utc(), "scenarios": {}}

    async def run_wf(wid, mode, sleep):
        cfg = {"wid": wid, "mode": mode, "sleep": sleep, "marks": str(marks)}
        t = time.monotonic()
        try:
            res = await client.execute_workflow(TwoStep.run, cfg, id=wid, task_queue=TASK_QUEUE,
                                                execution_timeout=timedelta(seconds=300))
            outcome = {"result": res}
        except WorkflowFailureError as exc:
            outcome = {"workflow_failure": type(exc.cause).__name__, "message": str(exc.cause)[:200]}
        outcome["seconds"] = round(time.monotonic() - t, 1)
        return outcome

    w1 = spawn_worker(a, work, "1")
    try:
        for wid, mode, sleep in (("g2-happy", "happy", 2), ("g2-retry", "retry", 2), ("g2-fail-hard", "fail_hard", 2)):
            o = await run_wf(wid, mode, sleep)
            o["history"] = history(a, wid, work)
            out["scenarios"][mode] = o
        # cancel: request cancellation while step1 sleeps
        cfg = {"wid": "g2-cancel", "mode": "cancel", "sleep": 60, "marks": str(marks)}
        handle = await client.start_workflow(TwoStep.run, cfg, id="g2-cancel", task_queue=TASK_QUEUE,
                                             execution_timeout=timedelta(seconds=300))
        for _ in range(60):
            if (marks / "g2-cancel.step1.started").exists():
                break
            await asyncio.sleep(0.25)
        await asyncio.sleep(2)
        cancel = subprocess.run([a.temporal, "workflow", "cancel", "--address", a.address, "--workflow-id", "g2-cancel"],
                                capture_output=True, text=True, timeout=60)
        try:
            await asyncio.wait_for(handle.result(), timeout=60)
            cres = "completed"
        except WorkflowFailureError as exc:
            cres = type(exc.cause).__name__
        await asyncio.sleep(2)
        out["scenarios"]["cancel"] = {"cancel_cli_exit": cancel.returncode, "cancel_cli_stdout": cancel.stdout[-200:],
                                      "result": cres, "step1_finished_marker": (marks / "g2-cancel.step1.finished").exists(),
                                      "history": history(a, "g2-cancel", work)}
        # kill: SIGKILL the worker mid-step1, then start a new worker
        cfg = {"wid": "g2-kill", "mode": "kill", "sleep": 20, "marks": str(marks)}
        handle = await client.start_workflow(TwoStep.run, cfg, id="g2-kill", task_queue=TASK_QUEUE,
                                             execution_timeout=timedelta(seconds=300))
        for _ in range(60):
            if (marks / "g2-kill.step1.started").exists():
                break
            await asyncio.sleep(0.25)
        await asyncio.sleep(2)
        t_kill = time.monotonic()
        kill_at_utc = utc()
        os.killpg(w1.pid, signal.SIGKILL)
        w1.wait(timeout=10)
        desc = subprocess.run([a.temporal, "workflow", "describe", "--address", a.address, "--workflow-id", "g2-kill",
                               "--output", "json"], capture_output=True, text=True, timeout=60)
        try:
            d = json.loads(desc.stdout)
            status_after_kill = d.get("workflowExecutionInfo", {}).get("status")
            pending = [{"activity": p.get("activityType", {}).get("name"), "state": p.get("state"),
                        "attempt": p.get("attempt")} for p in d.get("pendingActivities", [])]
        except Exception:
            status_after_kill, pending = None, desc.stderr[-200:]
        await asyncio.sleep(3)
        # Fix round 2: measure the real launch delay (the describe call above
        # also takes time) instead of reporting the fixed 3 s sleep.
        t_w2 = time.monotonic()
        w2 = spawn_worker(a, work, "2")
        try:
            res = await asyncio.wait_for(handle.result(), timeout=180)
            kres = {"result": res}
        except Exception as exc:
            kres = {"error": type(exc).__name__}
        kres.update({"seconds_from_kill_to_completion": round(time.monotonic() - t_kill, 1),
                     "status_immediately_after_kill": status_after_kill, "pending_after_kill": pending,
                     "second_worker_launched_s_after_kill": round(t_w2 - t_kill, 1),
                     "kill_at_utc": kill_at_utc,
                     "history": history(a, "g2-kill", work)})
        out["scenarios"]["kill"] = kres
        stop(w2)
    finally:
        stop(w1, signal.SIGKILL)
    out["finished_at_utc"] = utc()
    out["markers"] = {m.name: m.read_text().split("\n")[:-1] for m in sorted(marks.iterdir())}
    Path(a.out).write_text(json.dumps(out, indent=2) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["worker", "drive"])
    ap.add_argument("--address", required=True)
    ap.add_argument("--spans", required=True)
    ap.add_argument("--temporal")
    ap.add_argument("--work")
    ap.add_argument("--out")
    a = ap.parse_args()
    asyncio.run(worker_main(a) if a.cmd == "worker" else drive(a))


if __name__ == "__main__":
    main()
