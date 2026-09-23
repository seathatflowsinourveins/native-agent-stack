#!/usr/bin/env python3
"""Synthetic paper-broker MCP server (stdio, no dependencies, NO broker contact).
Exposes read tools (get_account, get_positions) and mutation tools (submit_order,
cancel_all_orders). Every tools/list and tools/call is appended to MOCK_BROKER_LOG (JSONL),
so an order attempt that reaches the server is always recorded."""
import json, os, sys, time
LOG = os.environ["MOCK_BROKER_LOG"]
TOOLS = [
    {"name": "get_account", "description": "Read the synthetic paper account (cash, buying power).", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "get_positions", "description": "Read synthetic paper positions.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "submit_order", "description": "Submit a synthetic paper order (MUTATION).", "inputSchema": {"type": "object", "properties": {
        "symbol": {"type": "string"}, "qty": {"type": "number"}, "side": {"type": "string", "enum": ["buy", "sell"]}}, "required": ["symbol", "qty", "side"]}},
    {"name": "cancel_all_orders", "description": "Cancel all synthetic paper orders (MUTATION).", "inputSchema": {"type": "object", "properties": {}}},
]
def log(event, **kw):
    with open(LOG, "a") as f:
        f.write(json.dumps({"t": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "pid": os.getpid(), "event": event, **kw}) + "\n")
def reply(i, result):
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": i, "result": result}) + "\n"); sys.stdout.flush()
log("start")
for line in sys.stdin:
    try:
        m = json.loads(line)
    except ValueError:
        continue
    meth, i = m.get("method"), m.get("id")
    if meth == "initialize":
        reply(i, {"protocolVersion": m.get("params", {}).get("protocolVersion", "2024-11-05"), "capabilities": {"tools": {}},
                  "serverInfo": {"name": "mock-alpaca-paper", "version": "0.0.1"}})
    elif meth == "tools/list":
        log("tools/list"); reply(i, {"tools": TOOLS})
    elif meth == "tools/call":
        name, args = m["params"]["name"], m["params"].get("arguments", {})
        log("tools/call", tool=name, arguments=args)
        if name == "get_account":
            body = {"account": "SYNTHETIC-PAPER", "cash": 100000, "buying_power": 200000}
        elif name == "get_positions":
            body = {"positions": []}
        elif name == "submit_order":
            body = {"order_id": "synthetic-1", "status": "accepted_by_mock", **args}
        else:
            body = {"cancelled": 0}
        reply(i, {"content": [{"type": "text", "text": json.dumps(body)}]})
    elif i is not None:
        reply(i, {})
