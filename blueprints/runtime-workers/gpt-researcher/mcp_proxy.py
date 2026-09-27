"""Local policy glue using unchanged FastMCP 4.0.10 proxy/middleware APIs.

Reference implementation: PrefectHQ/fastmcp v4.0.10
docs/servers/middleware.mdx:751-768 and docs/servers/providers/proxy.mdx:260-275.
Commands come exclusively from this checkout's two adoption MCP templates.
This is integration code, not a feature of GPT Researcher.
"""
import argparse
import json
from pathlib import Path, PurePosixPath
import re
import stat
from string import Template
from urllib.parse import unquote, urlsplit

HERE = Path(__file__).resolve().parent
POLICY = json.loads((HERE / "mcp-policy.json").read_text())


def load_host(path):
    path = Path(path).resolve()
    if path.is_relative_to(HERE.parents[2]):
        raise ValueError("host settings must be outside the checkout")
    if stat.S_IMODE(path.stat().st_mode) != 0o600:
        raise ValueError("host settings must have mode 0600")
    host = json.loads(path.read_text())
    required = {"ECO_ROOT", "HOST_PATH", "WORKER_CWD", "AI_MEMORY_URL", "MEMORY_PROJECT",
                "QMD_CONFIG_DIR", "QMD_INDEX_PATH", "MEMORY_WORKSPACE"}
    if set(host) != required or any(not isinstance(v, str) or not v or "<" in v or "\n" in v for v in host.values()):
        raise ValueError("fill all private host settings; unknown fields refused")
    for field in ("ECO_ROOT", "WORKER_CWD", "QMD_CONFIG_DIR"):
        if not Path(host[field]).is_absolute() or not Path(host[field]).is_dir():
            raise ValueError("host directory unavailable")
    index = Path(host["QMD_INDEX_PATH"])
    if not index.is_absolute() or not index.is_file():
        raise ValueError("existing catalog index unavailable")
    if not (Path(host["QMD_CONFIG_DIR"]) / "native-agent-stack-catalog.yml").is_file():
        raise ValueError("existing named QMD collection configuration unavailable")
    if not re.fullmatch(r"127\.0\.0\.1:[0-9]{1,5}", host["AI_MEMORY_URL"]):
        raise ValueError("memory endpoint must be loopback")
    return host


def allowed(server, tool):
    settings = POLICY["servers"].get(server, {})
    return (settings.get("active", False) and tool in settings.get("enabled_tools", [])
            and tool not in settings.get("disabled_tools", []))


def scope_arguments(server, tool, arguments, host):
    if not allowed(server, tool):
        raise ValueError("tool unavailable")
    args = dict(arguments or {})
    if server == "qmd":
        collections = POLICY["servers"][server]["collections"]
        if tool == "query":
            selected = args.get("collections", collections)
            if not isinstance(selected, list) or not selected or not set(selected) <= set(collections):
                raise ValueError("collection outside worker scope")
            args["collections"] = selected
            if "query" in args:
                args["searches"] = [{"type": "lex", "query": args.pop("query")}]
            if not args.get("searches") or any(s.get("type") != "lex" for s in args["searches"]):
                raise ValueError("QMD worker uses lexical search only")
            args["rerank"] = False
            args["limit"] = min(max(int(args.get("limit", 5)), 1), 5)
            args["candidateLimit"] = min(max(int(args.get("candidateLimit", 20)), 1), 20)
        elif tool == "get":
            path = urlsplit(str(args.get("file", "")))
            decoded = unquote(path.path)
            if (path.scheme != "qmd" or path.netloc not in collections or not decoded.strip("/")
                    or path.query or path.fragment or ".." in PurePosixPath(decoded).parts
                    or any(c in decoded for c in "*?[]\\%\x00")):
                raise ValueError("use qmd://allowed-collection/document path; docids refused")
            args["maxLines"] = min(max(int(args.get("maxLines", 120)), 1), 120)
    elif server == "ai-memory":
        args["project"] = host["MEMORY_PROJECT"]
        args["workspace"] = host["MEMORY_WORKSPACE"]
        if tool == "memory_query":
            # Installed MCP schema requires both fields for static clients.
            args.pop("scopes", None)
            args["global"] = False
            args["answer"] = False
            args["limit"] = min(max(int(args.get("limit", 5)), 1), 5)
        elif tool == "memory_read_page":
            args["include_related"] = False
        elif tool in ("memory_recent", "memory_briefing"):
            key = "limit" if tool == "memory_recent" else "recent_pages_limit"
            args[key] = min(max(int(args.get(key, 5)), 1), 5)
    return args


def server_config(server, host):
    settings = POLICY["servers"][server]
    if not settings["active"]:
        raise ValueError("server is not active for this role")
    values = {**host, "WORKER_STATE": str(Path.home() / ".local/state/native-agent-stack/runtime-workers/gpt-researcher")}
    def expand(value):
        if isinstance(value, str):
            return Template(value).substitute(values)
        if isinstance(value, list):
            return [expand(v) for v in value]
        return {k: expand(v) for k, v in value.items()}
    config = {k: expand(settings[k]) for k in ("command", "args", "env", "url", "cwd") if k in settings}
    if "command" in config:
        config.setdefault("cwd", host["WORKER_CWD"])
    return config


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("server", choices=[n for n, s in POLICY["servers"].items() if s["active"]])
    parser.add_argument("--host-file", required=True)
    opts = parser.parse_args()
    host = load_host(opts.host_file)
    # Imported only in the separate proxy venv (FastMCP4 needs MCP2).
    from fastmcp.server import create_proxy
    from fastmcp.server.middleware import Middleware
    from fastmcp.exceptions import ToolError

    class WorkerPolicy(Middleware):
        async def on_list_tools(self, context, call_next):
            tools = [tool for tool in await call_next(context) if allowed(opts.server, tool.name)]
            if opts.server == "qmd":
                for tool in tools:
                    tool.description += (" Worker policy: query uses lexical searches only; get requires "
                                         "qmd://collection/path, never a docid. Allowed collections: "
                                         + ", ".join(POLICY["servers"]["qmd"]["collections"]))
            return tools

        async def on_call_tool(self, context, call_next):
            try:
                context.message.arguments = scope_arguments(opts.server, context.message.name,
                                                            context.message.arguments, host)
            except (ValueError, TypeError, KeyError, AttributeError):
                raise ToolError("Tool or arguments outside worker scope") from None
            try:
                result = await call_next(context)
            except Exception:
                # QMD may suggest out-of-collection paths on failed lookup.
                raise ToolError("Scoped tool failed; details remain in private server logs") from None
            # No silent truncation: the model must narrow an oversized request.
            serialized = result.model_dump_json() if hasattr(result, "model_dump_json") else str(result)
            if len(serialized) > 32000:
                raise ToolError("Tool output exceeds 32000 characters; narrow the request")
            if opts.server == "qmd" and context.message.name == "get":
                # QMD returns successful content as an embedded resource, not
                # structured_content. Its error text may suggest unrelated files.
                if getattr(result, "is_error", False):
                    raise ToolError("Scoped document unavailable")
            return result

        async def on_list_resources(self, context, call_next):
            return []

        async def on_list_resource_templates(self, context, call_next):
            return []

        async def on_list_prompts(self, context, call_next):
            return []

        async def on_read_resource(self, context, call_next):
            raise ToolError("Resource access disabled for worker")

        async def on_get_prompt(self, context, call_next):
            raise ToolError("Prompt access disabled for worker")

    proxy = create_proxy({"mcpServers": {"default": server_config(opts.server, host)}}, name="ScopedResearchTools")
    proxy.add_middleware(WorkerPolicy())
    proxy.run(transport="stdio", show_banner=False)


if __name__ == "__main__":
    main()
