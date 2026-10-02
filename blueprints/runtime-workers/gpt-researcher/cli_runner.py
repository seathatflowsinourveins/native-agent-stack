"""Launch the unchanged upstream CLI main with scoped client hooks.

assafelovic/gpt-researcher@0957c301 cli.py:306-336,359-362; config/config.py:158-166.
Calling the CLI's parser/main in-process retains HTTPX hooks without patching
its source or replacing its research/report pipeline. No MCP tools are added.
"""
import argparse
import asyncio
import json
import logging
import os
from pathlib import Path
import runpy
import sys
import uuid

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from gateway import GatewayTransport, render_config, select_routes


async def execute_cli(prefix, run_dir, route, query, report_type):
    pins = json.loads((HERE / "pins.json").read_text())
    source = prefix / "source" / ("gpt-researcher-" + pins["commit"])
    session = uuid.uuid4().hex
    cfg = render_config(json.loads((HERE / "config.template.json").read_text()), route, session)
    cfg.update(RETRIEVER="duckduckgo", CONTEXT_FILTER="keyword", MCP_SERVERS=[])
    config_path = run_dir / "config.json"
    config_path.write_text(json.dumps(cfg, indent=2) + "\n")
    config_path.chmod(0o600)
    os.chdir(run_dir)
    os.environ.update(CONFIG_PATH=str(config_path), OPENAI_BASE_URL=route["base_url"],
                      OPENAI_API_KEY="local-loopback", RETRIEVER="duckduckgo", CONTEXT_FILTER="keyword",
                      PYTHON_DOTENV_DISABLED="1", ALLOW_PRIVATE_URLS="false")
    for role in ("FAST_LLM", "SMART_LLM", "STRATEGIC_LLM"):
        os.environ[role] = cfg[role]
    sys.path.insert(0, str(source))  # CLI imports backend.* from its source tree
    native = runpy.run_path(str(source / "cli.py"), run_name="gptr_native_cli")
    args = native["cli"].parse_args([query, "--report_type", report_type, "--tone", "objective", "--no-pdf", "--no-docx"])
    async with GatewayTransport(session, **route, correlation_log=run_dir / "worker-correlations.jsonl").worker_clients():
        await native["main"](args)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prefix", required=True, type=Path)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--report-type", default="research_report", choices=("research_report", "deep"))
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    logging.basicConfig(filename=run_dir / "native.log", level=logging.INFO,
                        format="%(asctime)s %(name)s %(levelname)s %(message)s", force=True)
    asyncio.run(execute_cli(args.prefix.resolve(), run_dir, select_routes(os.environ)["worker"],
                            (run_dir / "query.txt").read_text(), args.report_type))


if __name__ == "__main__":
    main()
