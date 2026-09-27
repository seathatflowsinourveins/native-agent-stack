"""Host acceptance probe, based on v2.1.0 mcp/tools.py and tests/test_model_factory.py.

Run later inside the pinned image; no model invocation. Discovery and QMD status
are prerequisite checks, not acceptance of research or coding tool execution.
"""
import asyncio
import json
import os


async def main():
    from deerflow.config.app_config import reload_app_config
    from deerflow.config.extensions_config import ExtensionsConfig
    from deerflow.mcp.client import build_servers_config
    from deerflow.models.factory import create_chat_model
    from deerflow.skills.storage import get_or_new_user_skill_storage
    from langchain_mcp_adapters.client import MultiServerMCPClient
    from worker_policy import POLICY, tool_allowed

    reload_app_config(os.environ["DEER_FLOW_CONFIG_PATH"])
    model = create_chat_model("worker", thinking_enabled=True)
    one = model._get_request_payload("offline configuration probe")
    two = model._get_request_payload("offline configuration probe")
    assert model.use_responses_api and model.streaming
    assert "input" in one and "temperature" not in one
    assert one["extra_headers"]["Idempotency-Key"] != two["extra_headers"]["Idempotency-Key"]
    assert one["extra_headers"]["x-omniroute-session"] == two["extra_headers"]["x-omniroute-session"]
    config = ExtensionsConfig.from_file()
    client = MultiServerMCPClient(build_servers_config(config), tool_name_prefix=True)
    counts = {}
    for server in POLICY["servers"]:
        tools = await asyncio.wait_for(client.get_tools(server_name=server), timeout=130)
        allowed = [t.name for t in tools if tool_allowed(t.name)]
        assert allowed, "enabled MCP server has no allowed tools"
        counts[server] = len(allowed)
        if server == "qmd":
            status_tool = next(t for t in tools if t.name == "qmd_status")
            status = json.dumps(await status_tool.ainvoke({}), default=str)
            assert all(name in status for name in POLICY["qmd_collections"]), "QMD collections missing"
    names = {s.name for s in get_or_new_user_skill_storage("default").load_skills(enabled_only=True)}
    required = {"search-first", "verification-before-completion"}
    assert required <= names, "pinned skills are not visible through upstream storage"
    print(json.dumps({"passed": True, "model_invoked": False,
                      "discovered_allowed_tools": counts, "required_skills_visible": sorted(required)}))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as exc:
        print(json.dumps({"passed": False, "error_class": type(exc).__name__}))
        raise SystemExit(1) from None
