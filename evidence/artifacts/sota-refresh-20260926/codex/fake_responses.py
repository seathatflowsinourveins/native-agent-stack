#!/usr/bin/env python3
"""Loopback stand-in for the Responses API, for exercising `codex exec` without a model or credentials.

Usage: fake_responses.py <port> <mode ok|limit> <requests.jsonl>

Every request is appended to <requests.jsonl> as {method, path, headers (names only), body} before it is answered.
  ok     POST .../responses -> 200 text/event-stream: response.created, one assistant message whose text is
         {"ok": true, "probe": "codex-exec-fake-provider"}, response.completed with fixed usage
         (input 11 incl. 3 cached, output 7 incl. 2 reasoning, total 18)
  limit  POST .../responses -> 429 JSON error whose message contains "You've hit your usage limit"
Anything else -> 404.
"""
from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT, MODE, LOG = int(sys.argv[1]), sys.argv[2], sys.argv[3]
MESSAGE = json.dumps({"ok": True, "probe": "codex-exec-fake-provider"})
USAGE = {"input_tokens": 11, "input_tokens_details": {"cached_tokens": 3}, "output_tokens": 7,
         "output_tokens_details": {"reasoning_tokens": 2}, "total_tokens": 18}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):  # keep stderr quiet
        pass

    def _record(self, body: bytes) -> None:
        try:
            parsed = json.loads(body) if body else None
        except ValueError:
            parsed = {"unparsed_bytes": len(body)}
        with open(LOG, "a") as handle:
            handle.write(json.dumps({"method": self.command, "path": self.path,
                                     "headers": sorted(k.lower() for k in self.headers.keys()),
                                     "body": parsed}) + "\n")

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
        body = self.rfile.read(length) if length else b""
        self._record(body)
        if not self.path.rstrip("/").endswith("/responses"):
            self._send(404, "application/json", b'{"error":{"message":"not found"}}')
            return
        if MODE == "limit":
            error = {"error": {"type": "usage_limit_reached", "code": "usage_limit_reached",
                               "message": "You've hit your usage limit. Try again at a later time (fake provider)."}}
            self._send(429, "application/json", json.dumps(error).encode())
            return
        events = [
            {"type": "response.created", "response": {"id": "resp_fake_1"}},
            {"type": "response.output_item.done",
             "item": {"type": "message", "role": "assistant", "id": "msg_fake_1",
                      "content": [{"type": "output_text", "text": MESSAGE}]}},
            {"type": "response.completed", "response": {"id": "resp_fake_1", "usage": USAGE}},
        ]
        payload = "".join(f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in events).encode()
        self._send(200, "text/event-stream", payload)


ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
