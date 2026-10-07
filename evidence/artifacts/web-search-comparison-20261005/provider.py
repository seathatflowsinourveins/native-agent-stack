# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Promptfoo protocol glue; call unchanged DeerFlow v2.1.0 search tools.

Sources: promptfoo@34f74d34:site/docs/providers/python.md:102-136,212-269;
DeerFlow@345f08be:backend/packages/harness/deerflow/config/app_config.py:768-783
and community/{ddg_search,searxng}/tools.py. The selected installed DeerFlow
interpreter supplies its pinned dependencies; this file installs nothing.
"""

import os

from deerflow.config.app_config import (
    AppConfig,
    pop_current_app_config,
    push_current_app_config,
)
from deerflow.config.sandbox_config import SandboxConfig
from deerflow.config.tool_config import ToolConfig


async def call_api(prompt, options, context):
    """Return the original native tool output without reformatting its results."""
    arm = options["config"]["arm"]
    if arm == "ddgs-auto":
        from deerflow.community.ddg_search.tools import web_search_tool

        tool_config = ToolConfig(
            name="web_search", group="web", use="deerflow.community.ddg_search.tools:web_search_tool",
            backend="auto", max_results=5,
        )
    elif arm == "searxng":
        from deerflow.community.searxng.tools import web_search_tool

        tool_config = ToolConfig(
            name="web_search", group="web", use="deerflow.community.searxng.tools:web_search_tool",
            base_url=os.environ["SEARXNG_TRIAL_URL"], max_results=5,
        )
    else:
        return {"error": f"Unpreregistered arm: {arm}"}
    config = AppConfig(
        sandbox=SandboxConfig(use="deerflow.sandbox.local:LocalSandbox"),
        tools=[tool_config],
    )
    push_current_app_config(config)
    try:
        return {"output": await web_search_tool.ainvoke({"query": prompt})}
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}
    finally:
        pop_current_app_config()
