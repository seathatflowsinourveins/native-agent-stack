#!/usr/bin/env python3
"""Portable SDK 1.50.1 bounded dispatcher, adapted from the supplied phase-1 worker.

Upstream: OpenHands/software-agent-sdk@v1.50.1 (1e1390acc8788346ba4804c34323284009bf3f5e):
examples/01_standalone_sdk/{01_hello_world.py:9-28,07_mcp_integration.py,
10_persistence.py,33_hooks/main.py,42_file_based_subagents.py};
openhands-tools/openhands/tools/preset/default.py:37-171;
openhands-sdk/openhands/sdk/conversation/conversation_stats.py:58-62;
openhands-sdk/openhands/sdk/llm/utils/metrics.py:113-129.
Preparation, srt policy rendering and compact reports are repository integration glue.
No credential file is read. --check prepares SDK extensions without a model call.
"""
import argparse
import json
import os
import re
import sys
import time
import uuid
from pathlib import Path

CFG = Path(__file__).resolve().parent
STATE = Path.home() / ".local/state/native-agent-stack/runtime-workers/openhands"


def log(event, **kw):
    print(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "event": event, **kw},
                     default=str), flush=True)


def proxy_env():
    out = {}
    for k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY", "http_proxy", "https_proxy", "no_proxy"):
        if k in os.environ:
            out[k] = re.sub(r"//[^/@]*@", "//<userinfo>@", os.environ[k])
    return out


def preflight(base_url, timeout=5.0):
    """Reachability of GET {base_url}/models without credentials; never a model request."""
    import httpx
    url = base_url.rstrip("/") + "/models"
    try:
        r = httpx.get(url, timeout=timeout)
        return {"ok": r.status_code in (200, 401), "status": r.status_code, "url": url}
    except Exception as e:  # noqa: BLE001 - the class is the evidence
        return {"ok": False, "error_class": type(e).__name__, "error": str(e)[:300], "url": url}


def build_llm(job):
    from pydantic import SecretStr
    from openhands.sdk import LLM
    key_env = job.get("api_key_env")
    key = os.environ.get(key_env) if key_env else None
    return LLM(api_key=SecretStr(key or "local-loopback"), **job["llm"])


def build_conversation(job, llm, workspace, persist):
    from openhands.sdk import Agent, Conversation, Tool
    from openhands.sdk.context.condenser import default_condenser
    from openhands.sdk.hooks import HookConfig
    from openhands.sdk.security.confirmation_policy import NeverConfirm
    from openhands.sdk.subagent.registry import register_file_agents
    from openhands.tools.preset.default import get_default_tools, register_builtins_agents
    from openhands.tools.terminal import TerminalTool
    try:
        from openhands.sdk import AgentContext
    except ImportError:
        from openhands.sdk.context import AgentContext

    info = {}
    ext = job.get("extensions", {})
    if ext.get("subagents", True):
        info["subagents_builtin"] = register_builtins_agents(enable_browser=False)
        info["subagents_file"] = register_file_agents(workspace)
    tools = get_default_tools(enable_browser=False, enable_sub_agents=ext.get("subagents", True))
    terminal_type = ext.get("terminal_type", "subprocess")
    tools = [Tool(name=t.name, params={"terminal_type": terminal_type}) if t.name == TerminalTool.name else t
             for t in tools]
    ctx = AgentContext(load_user_skills=ext.get("user_skills", True),
                       load_project_skills=ext.get("project_skills", True),
                       load_public_skills=False)
    agent_kw = {}
    if job.get("mcp_config"):
        agent_kw["mcp_config"] = job["mcp_config"]
        if job.get("filter_tools_regex"):
            agent_kw["filter_tools_regex"] = job["filter_tools_regex"]
    agent = Agent(llm=llm, tools=tools, agent_context=ctx,
                  system_prompt_kwargs={"cli_mode": True},
                  condenser=default_condenser(llm.model_copy(update={"usage_id": "condenser"})),
                  **agent_kw)
    hook_config = HookConfig.load(working_dir=workspace) if ext.get("hooks", True) else None
    info["hooks"] = None if hook_config is None else {"empty": hook_config.is_empty()}
    conv_id = uuid.UUID(job["conversation_id"]) if job.get("conversation_id") else uuid.uuid4()
    conv = Conversation(agent=agent, workspace=str(workspace), persistence_dir=str(persist),
                        conversation_id=conv_id, hook_config=hook_config,
                        max_iteration_per_run=int(job.get("max_iterations", 500)),
                        stuck_detection=True, delete_on_close=False,
                        **({"visualizer": None} if job.get("mode") == "check" else {}))
    conv.set_confirmation_policy(NeverConfirm())
    info["conversation_id"] = str(conv_id)
    return conv, info


def obs_text(obs):
    for attr in ("text",):
        v = getattr(obs, attr, None)
        if isinstance(v, str):
            return v[:400]
    content = getattr(obs, "content", None)
    if isinstance(content, list):
        return "".join(getattr(c, "text", "") for c in content)[:400]
    return str(obs)[:400]


def run_check(job, workspace, persist):
    from importlib.metadata import version
    from openhands.sdk.skills.skill import load_project_skills, load_user_skills
    from openhands.tools.terminal import TerminalAction, TerminalTool
    report = {"versions": {p: version(p) for p in ("openhands-sdk", "openhands-tools", "litellm", "fastmcp")},
              "terminal_tool_name": TerminalTool.name, "proxy_environment_names": sorted(proxy_env()), "requests_to_model": 0}
    report["user_skills"] = sorted(s.name for s in load_user_skills())
    report["project_skills"] = sorted(s.name for s in load_project_skills(workspace))
    try:
        llm = build_llm(job)
        report["llm"] = {k: getattr(llm, k, None) for k in ("model", "base_url", "reasoning_effort", "usage_id",
                                                           "timeout", "enable_encrypted_reasoning")}
        conv, info = build_conversation(job, llm, workspace, persist)
    except Exception as e:  # noqa: BLE001 - keep the partial read-back as evidence
        report["build_error"] = f"{type(e).__name__}: {str(e)[:900]}"
        (persist / "check-report.json").write_text(json.dumps(report, indent=1, default=str))
        log("check_report", **report)
        return 5
    report.update(info)
    ready = getattr(conv, "_ensure_agent_ready", None)
    try:
        if callable(ready):
            ready()
        report["tools"] = sorted(conv.agent.tools_map.keys())
    except Exception as e:  # noqa: BLE001
        import traceback
        report["tools_error"] = f"{type(e).__name__}: {str(e)[:600]}"
        report["tools_error_tb"] = traceback.format_exc()[-1800:]
    from openhands.sdk.subagent.registry import get_registered_agent_definitions
    report["subagents_registered"] = sorted(d.name for d in get_registered_agent_definitions())
    smoke = {}
    try:
        term = conv.agent.tools_map.get(TerminalTool.name)
    except Exception as e:  # noqa: BLE001
        term = None
        smoke["_unavailable"] = f"{type(e).__name__}: {str(e)[:200]}"
    for label, cmd in (job.get("terminal_smoke", {}).items() if term is not None else ()):
        try:
            smoke[label] = obs_text(term(TerminalAction(command=cmd), conv))
        except Exception as e:  # noqa: BLE001
            smoke[label] = f"ERROR {type(e).__name__}: {str(e)[:300]}"
    report["terminal_smoke"] = smoke
    try:
        conv.close()
    except Exception as e:  # noqa: BLE001
        report["close_error"] = f"{type(e).__name__}: {e}"
    (persist / "check-report.json").write_text(json.dumps(report, indent=1, default=str))
    log("check_report", **report)
    return 0 if "tools" in report and not report.get("tools_error") else 4


def run_job(job, workspace, persist):
    report = {"success": False, "requests_to_model": 0}
    pf = preflight(job["llm"]["base_url"])
    log("preflight", **pf)
    if not pf["ok"]:
        report["reason"] = "preflight_failed"
        (persist / "run-report.json").write_text(json.dumps(report, indent=2) + "\n")
        log("exit", code=3, **report)
        return 3
    conv = None
    try:
        llm = build_llm(job)
        conv, info = build_conversation(job, llm, workspace, persist)
        log("conversation", **info)
        conv.send_message(job["task"])
        conv.run()
        metrics = conv.conversation_stats.get_combined_metrics()
        # Native successful-response counter, never inferred from a version/preflight.
        report["requests_to_model"] = len(metrics.response_latencies)
        report["metrics"] = metrics.get_snapshot().model_dump()
        report["execution_status"] = str(conv.state.execution_status.value)
        report["success"] = report["execution_status"] == "finished" and report["requests_to_model"] > 0
    except Exception as error:
        report["error_class"] = type(error).__name__
        raise
    finally:
        if conv is not None:
            conv.close()
        (persist / "run-report.json").write_text(json.dumps(report, indent=2) + "\n")
        log("finished", **report)
    return 0 if report["success"] else 4


def prepare_job(name, task=None, workspace=None, negative=False):
    # Per-job paths are explicit srt settings, based on sandbox-runtime's documented format.
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", name):
        raise ValueError("Job ID must be 1-64 ASCII letters, digits, hyphens or underscores")
    jobs = CFG / "jobs"
    jobs.mkdir(mode=0o700, exist_ok=True)
    target = jobs / f"{name}.json"
    policy_target = CFG / f"srt-{name}.json"
    persist = STATE / name
    if target.exists() or policy_target.exists() or persist.exists():
        raise FileExistsError("Use a new job ID; existing job artifacts are retained")
    persist.mkdir(mode=0o700, parents=True)
    owned = Path(workspace).resolve() if workspace else persist / "workspace"
    owned.mkdir(parents=True, exist_ok=True)
    (persist / "tmp").mkdir(mode=0o700)
    job = json.loads((CFG / "job-template.json").read_text())
    policy = json.loads((CFG / "srt-template.json").read_text())
    job["workspace"] = str(owned)
    if task:
        job["task"] = task
    if negative:
        job["llm"]["base_url"] = "http://127.0.0.1:1/v1"
        policy["network"]["allowedDomains"] = ["127.0.0.1:1"]
    policy["filesystem"]["allowRead"] = [str(CFG)]
    policy["filesystem"]["allowWrite"] = [str(persist), str(owned)]
    for path, data in ((target, job), (policy_target, policy)):
        path.write_text(json.dumps(data, indent=2) + "\n")
        path.chmod(0o600)
    log("prepared", job=name, workspace=str(owned), negative=negative)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--job")
    ap.add_argument("--prepare", metavar="NEW_JOB_ID")
    ap.add_argument("--task")
    ap.add_argument("--workspace")
    ap.add_argument("--negative", action="store_true")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if a.prepare:
        if a.job or a.check:
            ap.error("--prepare cannot be combined with --job or --check")
        prepare_job(a.prepare, a.task, a.workspace, a.negative)
        return 0
    if not a.job or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", a.job):
        ap.error("Provide a valid --job or --prepare ID")
    job = json.loads((CFG / "jobs" / f"{a.job}.json").read_text())
    if a.check:
        job["mode"] = "check"
    if job.get("proxy_loopback"):
        # srt exports NO_PROXY with loopback, so httpx would dial 127.0.0.1 inside srt's own network namespace;
        # host loopback services are reachable only through srt's proxy, which honours IP-literal allow
        # entries such as 127.0.0.1:20128 (srt 0.0.78 README, "Resolved-address check").
        for k in ("NO_PROXY", "no_proxy"):
            if k in os.environ:
                os.environ[k] = ",".join(x for x in os.environ[k].split(",")
                                         if x.strip() not in ("localhost", "127.0.0.1", "::1"))
    persist = STATE / a.job
    persist.mkdir(parents=True, exist_ok=True)
    workspace = Path(job.get("workspace") or (persist / "workspace"))
    workspace.mkdir(parents=True, exist_ok=True)
    os.environ["TMPDIR"] = str(persist / "tmp")
    log("start", job=a.job, mode=job.get("mode", "run"), workspace=str(workspace), persistence_dir=str(persist))
    return run_check(job, workspace, persist) if job.get("mode") == "check" else run_job(job, workspace, persist)


if __name__ == "__main__":
    sys.exit(main())
