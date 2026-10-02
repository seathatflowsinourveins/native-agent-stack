"""Bounded JSON-RPC probes following v0.9.4 tests/mcp/test_mcp_socket.py.

SSE framing/auth follows modelcontextprotocol/python-sdk v1.18.0
src/mcp/client/sse.py; aiohttp provides HTTP/WebSocket transport. These client
observations are local integration checks, never framework-native log evidence.
"""
import asyncio
import json
from urllib.parse import urljoin, urlsplit


INIT = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
    "protocolVersion": "2024-11-05", "capabilities": {},
    "clientInfo": {"name": "crawl4ai-recipe-check", "version": "1"},
}}
READY = {"jsonrpc": "2.0", "method": "notifications/initialized"}


def call(fixture):
    return {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {
        "name": "md", "arguments": {"url": fixture, "f": "fit", "q": None, "c": "0"},
    }}


def valid_markdown(response):
    try:
        result = response["result"]
        if result.get("isError"):
            return False
        payload = json.loads(result["content"][0]["text"])
        markdown = payload["markdown"]
        return payload["success"] is True and all(fact in markdown for fact in ("Scout Beacon", "B-101", "24.90"))
    except (ValueError, KeyError, IndexError, TypeError):
        return False


async def event(stream):
    kind, data = "message", []
    while True:
        line = await stream.content.readline()
        if not line:
            raise ValueError("SSE stream ended")
        text = line.decode().rstrip("\r\n")
        if not text:
            if data:
                return kind, "\n".join(data)
            continue
        if text.startswith("event:"):
            kind = text[6:].strip()
        elif text.startswith("data:"):
            data.append(text[5:].lstrip())


async def sse(client, base, token, fixture):
    headers = {"Authorization": "Bearer " + token}
    async with client.get(base + "/mcp/sse", headers=headers) as stream:
        stream.raise_for_status()
        kind, endpoint = await event(stream)
        if kind != "endpoint":
            raise ValueError("missing SSE message endpoint")
        target = urljoin(base, endpoint)
        if urlsplit(target).netloc != urlsplit(base).netloc or not urlsplit(target).path.startswith("/mcp/messages/"):
            raise ValueError("unexpected SSE message destination")
        async def send(payload):
            async with client.post(target, headers=headers, json=payload) as result:
                result.raise_for_status()
        await send(INIT)
        _, answer = await event(stream)
        if "result" not in json.loads(answer):
            raise ValueError("SSE initialization failed")
        await send(READY)
        await send(call(fixture))
        while True:
            _, answer = await event(stream)
            parsed = json.loads(answer)
            if parsed.get("id") == 2:
                return valid_markdown(parsed)


async def websocket(client, base, token, fixture):
    async with client.ws_connect(base.replace("http://", "ws://", 1) + "/mcp/ws",
                                 headers={"Authorization": "Bearer " + token}, protocols=("mcp",)) as connection:
        await connection.send_json(INIT)
        initialized = await connection.receive_json()
        if "result" not in initialized:
            raise ValueError("WebSocket initialization failed")
        await connection.send_json(READY)
        await connection.send_json(call(fixture))
        while True:
            response = await connection.receive_json()
            if response.get("id") == 2:
                return valid_markdown(response)


async def probe(base, fixture, token):
    import aiohttp
    results = {}
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=40)) as client:
        for route in ("/mcp/sse", "/crawl"):
            async with client.get(base + route) as response:
                results["auth_" + route] = response.status == 401
        try:
            async with client.ws_connect(base.replace("http://", "ws://", 1) + "/mcp/ws", protocols=("mcp",)):
                results["auth_/mcp/ws"] = False
        except aiohttp.WSServerHandshakeError as exc:
            results["auth_/mcp/ws"] = exc.status in (401, 403)
        # Prove API auth/control and FIT extraction even if one MCP transport fails.
        async with client.post(base + "/md", headers={"Authorization": "Bearer " + token},
                               json={"url": fixture, "f": "fit", "q": None, "c": "0"}) as response:
            payload = await response.json()
            results["api_fit"] = response.status == 200 and valid_markdown({
                "result": {"content": [{"text": json.dumps(payload)}]}})
        for transport, operation in (("sse", sse), ("websocket", websocket)):
            try:
                results[transport] = await asyncio.wait_for(operation(client, base, token, fixture), timeout=40)
            except Exception as exc:
                results[transport] = False
                results[transport + "_error"] = type(exc).__name__
    return results
