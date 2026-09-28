"""ticket-tracker: the K6 fixture of the X9 round-3 comparison, a stdio MCP server that lists its tools, then stops.

Built on the official MCP Python SDK, mcp 2.2.0 (modelcontextprotocol/python-sdk, tag v2.2.0 at 9972c21a):
- README, "A server in 15 lines": `from mcp.server import MCPServer`, `mcp = MCPServer("Demo")`, `@mcp.tool()`;
- src/mcp/server/mcpserver/server.py: `run()` defaults to the stdio transport, `_handle_list_tools` answers
  tools/list with `await self.list_tools()`, and `_handle_call_tool` turns an exception other than MCPError into a
  result with `is_error=True`.
It answers initialize and tools/list like any server. It logs each event as one JSON line to the file named by
R3_MCP_LOG. R3_EXIT_AFTER_S seconds after its first tools/list it logs {"event": "exit", "reason": "timer"} and ends
the process, as a crashed server would; Claude Code does not reconnect a stdio server
(https://code.claude.com/docs/en/mcp.md). A tool call that arrives before then is logged and fails, so no call to
this server can succeed. If the client closes stdin first, it logs {"event": "exit", "reason": "stdin closed"}.
Revised 2026-09-28 after an uncounted probe (probe/p2-k6-view): Claude Code 2.1.283 started the server again when
the model called one of its tools after the timer had ended it. A server started after that exit now logs
{"event": "start-refused"} and exits 1 before answering anything, as a crashed server that cannot come back would.
"""
import json
import os
import sys
import threading
import time

from mcp.server import MCPServer

LOG = os.environ.get("R3_MCP_LOG")
DELAY = float(os.environ.get("R3_EXIT_AFTER_S", "3"))
_lock = threading.Lock()


def log(event, **fields):
    if LOG:
        with _lock, open(LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps({"event": event, "ts": round(time.time(), 3), **fields}) + "\n")


def _crash():
    log("exit", reason="timer")
    os._exit(0)


class TicketTracker(MCPServer):
    _timer = None

    async def list_tools(self):
        log("tools/list")
        if self._timer is None:
            self._timer = threading.Timer(DELAY, _crash)
            self._timer.daemon = True
            self._timer.start()
        return await super().list_tools()


mcp = TicketTracker("ticket-tracker")


@mcp.tool()
def list_open_tickets() -> str:
    """List the open tickets in the team's ticket tracker."""
    log("tools/call", name="list_open_tickets")
    raise RuntimeError("ticket-tracker backend unavailable")


@mcp.tool()
def get_ticket(ticket_id: str) -> str:
    """Get one ticket from the team's ticket tracker by its id."""
    log("tools/call", name="get_ticket")
    raise RuntimeError("ticket-tracker backend unavailable")


def ended_before():
    if not LOG or not os.path.exists(LOG):
        return False
    with open(LOG, encoding="utf-8") as f:
        return any(json.loads(line).get("reason") == "timer" for line in f if line.strip())


if __name__ == "__main__":
    if ended_before():
        log("start-refused", pid=os.getpid())
        sys.exit(1)
    log("start", pid=os.getpid())
    mcp.run()
    log("exit", reason="stdin closed")
