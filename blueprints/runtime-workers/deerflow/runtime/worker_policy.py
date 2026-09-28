"""Native AuthorizationProvider adapter for the adopted MCP tool contract.

References at DeerFlow v2.1.0: authz/provider.py:1-21,55-126,
authz/rbac.py:59-72, authz/adapter.py, authz/tool_filter.py.
DeerFlow applies this provider at schema assembly AND before tool execution.
This is tool policy, not a security sandbox for the allowed bash/ctx_execute.
"""
import json
from pathlib import Path, PurePosixPath

POLICY = json.loads(Path(__file__).with_name("tool-policy.json").read_text())


def tool_allowed(name):
    if name in POLICY["builtin_tools"]:
        return True
    for server, rule in POLICY["servers"].items():
        prefix = server + "_"
        if name.startswith(prefix):
            tool = name[len(prefix):]
            return (rule["allow"] == "*" or tool in rule["allow"]) and tool not in rule.get("deny", [])
    return False


def _scoped_qmd_path(value):
    if not isinstance(value, str) or not value.startswith("qmd://"):
        return False
    collection, sep, path = value[6:].partition("/")
    return bool(sep and path and collection in POLICY["qmd_collections"]
                and ".." not in PurePosixPath(path).parts and not path.startswith("/"))


def arguments_allowed(name, args):
    if name == "qmd_query":
        cols = args.get("collections")
        searches = args.get("searches")
        return bool(isinstance(cols, list) and cols
                    and all(c in POLICY["qmd_collections"] for c in cols)
                    and args.get("rerank") is False and "query" not in args
                    and isinstance(searches, list) and searches
                    and all(isinstance(s, dict) and s.get("type") == "lex" for s in searches))
    if name == "qmd_get":
        return _scoped_qmd_path(args.get("file"))
    if name == "qmd_multi_get":
        pattern = args.get("pattern", "")
        return bool(isinstance(pattern, str) and pattern
                    and all(_scoped_qmd_path(x.strip()) for x in pattern.split(",")))
    return True


class WorkerAuthorization:
    name = "runtime-worker-token-policy"

    def filter_resources(self, principal, resource_type, candidates):
        if resource_type == "tool":
            return [x for x in candidates if tool_allowed(x)]
        if resource_type == "mcp_server":
            return [x for x in candidates if x in POLICY["servers"]]
        return candidates

    def authorize(self, request):
        from deerflow.authz.provider import AuthzDecision, AuthzReason
        allowed = True
        if request.resource == "tool":
            allowed = tool_allowed(request.target) and arguments_allowed(
                request.target, request.context.get("tool_input", {})
            )
        elif request.resource == "mcp_server":
            allowed = request.target in POLICY["servers"]
        return AuthzDecision(allow=allowed, reasons=[AuthzReason(
            code="worker.allowed" if allowed else "worker.tool_scope"
        )])

    async def aauthorize(self, request):
        return self.authorize(request)
