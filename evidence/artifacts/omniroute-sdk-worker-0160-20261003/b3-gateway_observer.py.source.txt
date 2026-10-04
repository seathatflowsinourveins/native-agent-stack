"""Value-free observation of an owned worker's loopback gateway traffic.

Use mitmproxy 12.2.3 (6c09d56e4c29a92f5ad01b03199977584b8ea14f)
in reverse mode. Sources: docs.mitmproxy.org/stable/concepts/modes/
and that tag's examples/addons/http-stream-simple.py, http-stream-modify.py.
This addon observes requests and returns every response chunk unchanged.
It is a local integration observer, not an upstream test or a provider oracle.
Do not use it to capture another session, write flows, or intercept TLS.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from mitmproxy import http

OUTPUT = Path(os.environ["STACK_WORKER_OBSERVATION"])
MAX_FRAME = 2 * 1024 * 1024


def emit(row: dict[str, Any]) -> None:
    """Append only selected metadata; never headers, prompts or tool arguments."""
    fd = os.open(OUTPUT, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    with os.fdopen(fd, "a") as stream:
        stream.write(json.dumps(row, separators=(",", ":")) + "\n")


def counters(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    result: dict[str, Any] = {}
    for key in ("input_tokens", "output_tokens", "total_tokens"):
        if type(value.get(key)) is int:
            result[key] = value[key]
    for key in ("input_tokens_details", "output_tokens_details"):
        details = value.get(key)
        if isinstance(details, dict):
            result[key] = {
                name: count
                for name, count in details.items()
                if name in ("cached_tokens", "reasoning_tokens") and type(count) is int
            }
    return result or None


def request(flow: http.HTTPFlow) -> None:
    if flow.request.method != "POST":
        return
    path = flow.request.path.split("?", 1)[0]
    if path not in ("/v1/responses", "/v1/messages"):
        return
    body = flow.request.content or b""
    try:
        data = json.loads(body)
    except (ValueError, UnicodeError):
        emit({"event": "unparsed_request", "flow": flow.id, "path": path})
        return
    cache_key = data.get("prompt_cache_key")
    tools = data.get("tools")
    tool_source = "top_level" if isinstance(tools, list) else None
    native_ids = []
    # Codex rust-v0.159.2 core/src/client.rs:902-933: ResponsesLite
    # carries native tool declarations in input.additional_tools, not tools.
    if not isinstance(tools, list) and isinstance(data.get("input"), list):
        declarations = [
            x for x in data["input"] if isinstance(x, dict) and x.get("type") == "additional_tools"
        ]
        if declarations:
            tools = [tool for declaration in declarations for tool in declaration.get("tools", [])]
            tool_source = "input.additional_tools"
            native_ids = [
                hashlib.sha256(x["id"].encode()).hexdigest()
                for x in declarations
                if isinstance(x.get("id"), str)
            ]
    names = []
    for tool in tools if isinstance(tools, list) else []:
        if isinstance(tool, dict):
            name = tool.get("name") or (tool.get("function") or {}).get("name")
            if isinstance(name, str):
                names.append(name)
    reasoning = data.get("reasoning")
    flow.metadata["stack_worker_observed"] = True
    emit(
        {
            "event": "request",
            "flow": flow.id,
            "path": path,
            "request_keys": sorted(data),
            "model": data.get("model"),
            "effort": reasoning.get("effort") if isinstance(reasoning, dict) else None,
            "request_bytes": len(body),
            "request_sha256": hashlib.sha256(body).hexdigest(),
            "cache_key_sha256": hashlib.sha256(cache_key.encode()).hexdigest()
            if isinstance(cache_key, str)
            else None,
            "tool_count": len(tools) if isinstance(tools, list) else None,
            "tool_names": names,
            "tool_source": tool_source,
            "native_tool_id_hashes": native_ids,
            "cache_markers_present": b'"cache_control"' in body,
        }
    )


def responseheaders(flow: http.HTTPFlow) -> None:
    if not flow.metadata.get("stack_worker_observed") or flow.response is None:
        return
    emit({"event": "response_headers", "flow": flow.id, "status": flow.response.status_code})
    pending = bytearray()
    overflow = False

    def observe(chunk: bytes) -> bytes:
        nonlocal overflow
        if not overflow:
            pending.extend(chunk)
            # A transport chunk can contain many complete, short SSE frames.
            # Split once so large batches do not repeatedly copy the remainder.
            lines = pending.split(b"\n")
            pending[:] = lines.pop()
            for line in lines:
                if not line.startswith(b"data:"):
                    continue
                try:
                    event = json.loads(line[5:].strip())
                except (ValueError, UnicodeError):
                    continue
                if isinstance(event, dict) and event.get("type") == "response.completed":
                    response = event.get("response", {})
                    emit(
                        {
                            "event": "response_completed",
                            "flow": flow.id,
                            "usage": counters(response.get("usage"))
                            if isinstance(response, dict)
                            else None,
                        }
                    )
            if len(pending) > MAX_FRAME:
                pending.clear()
                overflow = True
                emit({"event": "usage_capture_overflow", "flow": flow.id})
        if chunk == b"":
            emit({"event": "stream_closed", "flow": flow.id})
        return chunk

    # Native mitmproxy streaming callback; identity preserves response bytes.
    flow.response.stream = observe


def error(flow: http.HTTPFlow) -> None:
    if flow.metadata.get("stack_worker_observed"):
        emit({"event": "flow_error", "flow": flow.id})
