"""Upstream SDK example with private native artifacts and upstream DRB-II grading.

Reference: GPT Researcher v3.7.0 README SDK example; agent.py:463-504,684-690;
deep_research.py:644-646 propagates actual scraped sources from child researchers.
"""
import argparse
import asyncio
from datetime import datetime, timezone
import importlib.metadata
import json
import logging
import os
from pathlib import Path
import sys
import subprocess
import uuid

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from mcp_proxy import POLICY, load_host
from check import check, export_report
from gateway import BASE_URL, GatewayTransport, model_id, render_config, validate_route
from grader import load_task, verified_source
from receipt import compression_snapshot


def now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


async def run(args, output):
    host = load_host(args.host_file)
    expected = json.loads((HERE.parent / "pins.json").read_text())
    installed = json.loads((args.prefix / "installation-pins.json").read_text())
    if installed != expected:
        raise ValueError("installation pins differ from recipe; rerun the installer")
    if not (args.prefix / "grader-venv/bin/python").is_file():
        raise ValueError("missing native grader environment; rerun the installer")
    version = importlib.metadata.version("gpt-researcher")
    if version != expected["package_version"]:
        raise ValueError("wrong installed framework version")
    output["framework_version"] = version
    # All nested native researchers reload the same config_path. No source patches.
    session = uuid.uuid4().hex
    cfg = render_config(json.loads((HERE.parent / "config.template.json").read_text()),
                        {"model": args.model, "base_url": args.base_url}, session)
    cfg["RETRIEVER"] = "duckduckgo,mcp"
    # Pass constructor mcp_configs: Config.__init__ resets cfg.mcp_servers.
    mcp_configs = [{"name": name, "connection_type": "stdio",
                    "command": str(args.prefix / "proxy-venv/bin/python"),
                    "args": [str(HERE.parent / "mcp_proxy.py"), name, "--host-file", str(args.host_file),
                             "--run-dir", str(args.run_dir)],
                    "env": {key: os.environ[key] for key in ("XDG_CACHE_HOME", "XDG_CONFIG_HOME", "XDG_STATE_HOME",
                                                             "HF_HOME", "PYTHON_DOTENV_DISABLED") if key in os.environ}}
                   for name, settings in POLICY["servers"].items() if settings["active"]]
    private_cfg = args.run_dir / "config.json"
    private_cfg.write_text(json.dumps(cfg, indent=2) + "\n")
    # Explicit config values beat the upstream paid defaults. Keyword mode lazily
    # avoids embeddings; no embedding or TypeSafe/Tavily credential is supplied.
    os.environ.update({"OPENAI_BASE_URL": cfg["LLM_KWARGS"]["base_url"],
                       "OPENAI_API_KEY": "local-loopback", "CONTEXT_FILTER": "keyword",
                       "KEYWORD_MAX_RESULTS": "16", "KEYWORD_RELATIVE_THRESHOLD": "0.5",
                       "COMPRESSION_THRESHOLD": "8000", "LANGCHAIN_TRACING_V2": "false",
                       "LANGSMITH_TRACING": "false", "DO_NOT_TRACK": "1",
                       "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
                       "CHUB_TELEMETRY": "0", "CHUB_FEEDBACK": "0", "ALLOW_PRIVATE_URLS": "false"})
    os.environ["PYTHON_DOTENV_DISABLED"] = "1"
    for role in ("FAST_LLM", "SMART_LLM", "STRATEGIC_LLM"):
        os.environ[role] = cfg[role]
    selection = json.loads((HERE / "task.json").read_text())
    task, raw = load_task(verified_source(args.prefix) / "tasks_and_rubrics.jsonl", selection)
    (args.run_dir / "tasks-and-rubrics.jsonl").write_bytes(raw)
    output["skills"] = {"listed_at_start": [], "activation_events": [],
                        "status": "no SKILL.md loader found in pinned runtime; native inventory unavailable"}
    print(json.dumps({"skills_at_start": output["skills"]}))
    from gpt_researcher import GPTResearcher
    from gpt_researcher.mcp.client import MCPClientManager
    # Fail on missing tools before spending a model call; this is discovery only.
    manager = MCPClientManager(mcp_configs)
    try:
        discovered = {tool.name for tool in await manager.get_all_tools()}
        required = {"query", "get", "ctx_index", "memory_query"}
        if not required <= discovered:
            raise ValueError("required scoped MCP tools unavailable")
        permitted = {t for s in POLICY["servers"].values() if s["active"] for t in s["enabled_tools"]}
        if not discovered <= permitted:
            raise ValueError("MCP discovery exposed tools outside the policy")
    finally:
        await manager.close_client()
    # Use the original benchmark prompt, including its blocked-reference rules.
    async with GatewayTransport(session, base_url=args.base_url, model=args.model,
                                correlation_log=args.run_dir / "worker-correlations.jsonl").worker_clients():
        worker = GPTResearcher(query=task["prompt"], report_type=selection["report_type"],
                               config_path=str(private_cfg), mcp_configs=mcp_configs,
                               mcp_strategy="fast", verbose=True, websocket=None)
        # GPTR@0957c301 utils/llm.py:120-143 permits ten attempts only without
        # a websocket during streamed report generation. Native logs stay on.
        await worker.conduct_research()
        output["report"] = await worker.write_report(custom_prompt=task["prompt"])
        # Retain actual fetched sources, never replace them with visited URLs.
        output["sources"] = worker.get_research_sources()
    export_report(output, args.run_dir / "report.md")
    export_report(output, args.run_dir / "frozen-reports/gptr" / f"idx-{task['idx']}.md")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--prefix", type=Path, required=True)
    parser.add_argument("--host-file", type=Path, required=True)
    parser.add_argument("--model", required=True, type=model_id)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--judge-model", required=True, type=model_id)
    args = parser.parse_args()
    args.run_dir = args.run_dir.resolve()
    args.host_file = args.host_file.resolve()
    args.prefix = args.prefix.resolve()
    validate_route(args.base_url, args.model)
    validate_route(BASE_URL, args.judge_model)
    # Avoid upstream dotenv discovery of checkout/host provider files.
    os.chdir(args.run_dir)
    logging.basicConfig(filename=args.run_dir / "native.log", level=logging.INFO,
                        format="%(asctime)s %(name)s %(levelname)s %(message)s", force=True)
    started = now()
    (args.run_dir / "window-start.txt").write_text(started)
    phases = {"worker_started": started}
    def persist_phases():
        path = args.run_dir / "phases.json"
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(phases) + "\n")
        temporary.replace(path)
    persist_phases()
    arm = "engines-on" if args.model.startswith("sharedgw/") else "control"
    compression = {"before": compression_snapshot(arm)}
    output = {"report": "", "sources": [], "framework_version": None}
    runtime_error = None
    original_stdout, original_stderr = sys.stdout, sys.stderr
    with (args.run_dir / "stdout.log").open("w") as stdout, (args.run_dir / "stderr.log").open("w") as stderr:
        sys.stdout, sys.stderr = stdout, stderr
        try:
            asyncio.run(asyncio.wait_for(run(args, output), timeout=1800))
        except BaseException as error:
            runtime_error = type(error).__name__
            logging.exception("Native run failed")
        finally:
            sys.stdout, sys.stderr = original_stdout, original_stderr
    (args.run_dir / "result.json").write_text(json.dumps(output, indent=2, default=str) + "\n")
    phases["worker_ended"] = now()
    persist_phases()
    compression["after"] = compression_snapshot(arm)
    (args.run_dir / "compression.json").write_text(json.dumps(compression) + "\n")
    sanity = check(output)
    (args.run_dir / "check.json").write_text(json.dumps(sanity, indent=2) + "\n")
    if runtime_error is None and sanity["ready_for_grading"]:
        phases["judge_started"] = now()
        persist_phases()
        try:
            with (args.run_dir / "grader-stdout.log").open("w") as stdout, (args.run_dir / "grader-stderr.log").open("w") as stderr:
                subprocess.run([str(args.prefix / "grader-venv/bin/python"), str(HERE / "grader.py"),
                                "--prefix", str(args.prefix), "--run-dir", str(args.run_dir),
                                "--model", args.judge_model], check=True, timeout=1800,
                               stdout=stdout, stderr=stderr)
        except (OSError, subprocess.SubprocessError) as error:
            runtime_error = "Grader" + type(error).__name__
        finally:
            phases["judge_ended"] = now()
            persist_phases()
    # The supervisor independently validates grades and observes gateway DBs.
    (args.run_dir / "execution.json").write_text(json.dumps({"runtime_error": runtime_error,
                                                            "framework_version": output["framework_version"]}) + "\n")
    return 0 if runtime_error is None and sanity["ready_for_grading"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
