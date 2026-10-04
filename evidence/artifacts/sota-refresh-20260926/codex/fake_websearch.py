#!/usr/bin/env python3
"""Loopback stand-in for the Responses API plus Codex's standalone search endpoint (POST .../alpha/search).

Usage: fake_websearch.py <port> <requests.jsonl>

Every request is appended to <requests.jsonl> ({method, path, header names, body}) before it is answered.
POST .../responses is answered by how many function_call_output items the request input already holds:
  0 -> a function_call to the `web` namespace tool `run` with {"search_query":[{"q":"codex fake query"}]}
  1 -> a function_call to web.run with {"open":[{"ref_id":"https://example.com/docs"}]}
  2+ -> the final assistant message {"ok": true, "probe": "codex-exec-fake-websearch"}
Each response ends with response.completed and fixed usage (input 11 incl. 3 cached, output 7 incl. 2 reasoning).
POST .../alpha/search -> {"output": "...", "results": [{"type": "page", "url": ..., "title": ...}]}
Anything else -> 404.
"""
from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT, LOG = int(sys.argv[1]), sys.argv[2]
USAGE = {"input_tokens": 11, "input_tokens_details": {"cached_tokens": 3}, "output_tokens": 7,
         "output_tokens_details": {"reasoning_tokens": 2}, "total_tokens": 18}
CALLS = [{"search_query": [{"q": "codex fake query"}]}, {"open": [{"ref_id": "https://example.com/docs"}]}]
FINAL = json.dumps({"ok": True, "probe": "codex-exec-fake-websearch"})


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def _record(self, body: bytes):
        try:
            parsed = json.loads(body) if body else None
        except ValueError:
            parsed = {"unparsed_bytes": len(body)}
        with open(LOG, "a") as handle:
            handle.write(json.dumps({"method": self.command, "path": self.path,
                                     "headers": sorted(k.lower() for k in self.headers.keys()),
                                     "body": parsed}) + "\n")
        return parsed

    def _send(self, status: int, content_type: str, payload: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        self._record(b"")
        self._send(404, "application/json", b'{"error":{"message":"not found"}}')

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = self._record(self.rfile.read(length) if length else b"")
        path = self.path.rstrip("/")
        if path.endswith("/alpha/search"):
            answer = {"output": "Fake search output for the qualification probe.",
                      "results": [{"type": "page", "url": "https://example.com/docs", "title": "Fake docs"}]}
            self._send(200, "application/json", json.dumps(answer).encode())
            return
        if not path.endswith("/responses"):
            self._send(404, "application/json", b'{"error":{"message":"not found"}}')
            return
        outputs = sum(1 for item in (body or {}).get("input", []) if item.get("type") == "function_call_output")
        if outputs < len(CALLS):
            item = {"type": "function_call", "id": f"fc_{outputs}", "call_id": f"call_web_{outputs}",
                    "namespace": "web", "name": "run", "arguments": json.dumps(CALLS[outputs])}
        else:
            item = {"type": "message", "role": "assistant", "id": "msg_final",
                    "content": [{"type": "output_text", "text": FINAL}]}
        events = [{"type": "response.created", "response": {"id": f"resp_{outputs}"}},
                  {"type": "response.output_item.done", "item": item},
                  {"type": "response.completed", "response": {"id": f"resp_{outputs}", "usage": USAGE}}]
        payload = "".join(f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in events).encode()
        self._send(200, "text/event-stream", payload)


ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
