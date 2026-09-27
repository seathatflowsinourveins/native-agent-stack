"""Upstream SDK example with private native artifacts and a frozen oracle.

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
import uuid

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from mcp_proxy import POLICY, load_host
from check import check
from receipt import write_receipt


def now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class NativeEvents:
    """Unmodified native websocket events, private only; no synthetic tool events."""
    def __init__(self, path):
        self.path = path

    async def send_json(self, event):
        with self.path.open("a") as output:
            output.write(json.dumps(event, default=str) + "\n")


async def run(args, output):
    host = load_host(args.host_file)
    expected = json.loads((HERE.parent / "pins.json").read_text())
    installed = json.loads((args.prefix / "installation-pins.json").read_text())
    if installed != expected:
        raise ValueError("installation pins differ from recipe; rerun the installer")
    version = importlib.metadata.version("gpt-researcher")
    if version != expected["package_version"]:
        raise ValueError("wrong installed framework version")
    output["framework_version"] = version
    # All nested native researchers reload the same config_path. No source patches.
    cfg = json.loads((HERE.parent / "config.template.json").read_text())
    if not args.model or any(c.isspace() for c in args.model) or ":" in args.model:
        raise ValueError("model must be a gateway model identifier, without provider prefix")
    for role in ("FAST_LLM", "SMART_LLM", "STRATEGIC_LLM"):
        cfg[role] = "openai:" + args.model
    cfg["LLM_KWARGS"]["default_headers"]["x-omniroute-session"] = uuid.uuid4().hex
    cfg["RETRIEVER"] = "duckduckgo,mcp"
    # Pass constructor mcp_configs: Config.__init__ resets cfg.mcp_servers.
    mcp_configs = [{"name": name, "connection_type": "stdio",
                    "command": str(args.prefix / "proxy-venv/bin/python"),
                    "args": [str(HERE.parent / "mcp_proxy.py"), name, "--host-file", str(args.host_file)],
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
                       "CHUB_TELEMETRY": "0", "CHUB_FEEDBACK": "0"})
    os.environ["PYTHON_DOTENV_DISABLED"] = "1"
    for role in ("FAST_LLM", "SMART_LLM", "STRATEGIC_LLM"):
        os.environ[role] = cfg[role]
    task = json.loads((HERE / "task.json").read_text())
    from gpt_researcher import GPTResearcher
    from gpt_researcher.mcp.client import MCPClientManager
    # Fail on missing tools before spending a model call; this is discovery only.
    manager = MCPClientManager(mcp_configs)
    try:
        discovered = {tool.name for tool in await manager.get_all_tools()}
        required = {"query", "get", "ctx_fetch_and_index", "memory_query"}
        if not required <= discovered:
            raise ValueError("required scoped MCP tools unavailable")
        permitted = {t for s in POLICY["servers"].values() if s["active"] for t in s["enabled_tools"]}
        if not discovered <= permitted:
            raise ValueError("MCP discovery exposed tools outside the policy")
    finally:
        await manager.close_client()
    query = task["question"] + "\n\n" + "\n".join("- " + s for s in task["required_statements"])
    worker = GPTResearcher(query=query, report_type=task["report_type"],
                           config_path=str(private_cfg), mcp_configs=mcp_configs,
                           mcp_strategy="fast", verbose=True,
                           query_domains=task["allowed_domains"],
                           websocket=NativeEvents(args.run_dir / "native-events.jsonl"))
    await worker.conduct_research()
    output["report"] = await worker.write_report(custom_prompt=query)
    # Never turn discovered/visited URLs into fetched-page evidence.
    output["sources"] = worker.get_research_sources()
    (args.run_dir / "report.md").write_text(output["report"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--prefix", type=Path, required=True)
    parser.add_argument("--host-file", type=Path, required=True)
    parser.add_argument("--model", required=True)
    args = parser.parse_args()
    args.run_dir = args.run_dir.resolve()
    args.host_file = args.host_file.resolve()
    args.prefix = args.prefix.resolve()
    # Avoid upstream dotenv discovery of checkout/host provider files.
    os.chdir(args.run_dir)
    logging.basicConfig(filename=args.run_dir / "native.log", level=logging.INFO,
                        format="%(asctime)s %(name)s %(levelname)s %(message)s", force=True)
    started = now()
    (args.run_dir / "window-start.txt").write_text(started)
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
    ended = now()
    (args.run_dir / "result.json").write_text(json.dumps(output, indent=2, default=str) + "\n")
    verdict = check(output)
    (args.run_dir / "check.json").write_text(json.dumps(verdict, indent=2) + "\n")
    receipt = write_receipt(args.run_dir, started, ended, args.model, output["framework_version"], runtime_error)
    print(json.dumps({"passed": receipt["passed"], "check": receipt["check"],
                      "receipt": "receipt.json in the private attempt directory",
                      "runtime_error": runtime_error}, sort_keys=True))
    return 0 if receipt["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
