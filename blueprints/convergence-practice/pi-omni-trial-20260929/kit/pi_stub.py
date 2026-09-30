"""Scripted OpenAI Responses stub for offline probes of the pi trial (local integration probe, not upstream acceptance).

Records what a client sends and answers with a scripted stream. Authorization headers are never written.

    pi_stub.py PORT LOGFILE [SCRIPT.json]

SCRIPT.json is a list; entry i answers the i-th POST. Each entry is one of
  {"text": "..."}                                   an assistant message
  {"tool_call": {"name": "bash", "arguments": {}}}  one function call
and may carry {"delay_s": N} to hold the response (used to kill the client mid-turn).
Without a script every request gets {"text": "STUB-OK"}. Entries beyond the list repeat the last one.
"""
import hashlib
import json
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

REDACT = ["authorization", "x-api-key", "proxy-authorization"]
COUNT = {"n": 0}


def sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:16]


def sse(event, data):
    return ("event: %s\ndata: %s\n\n" % (event, json.dumps(data))).encode()


def usage_block(n_in):
    return {"input_tokens": n_in, "output_tokens": 5, "total_tokens": n_in + 5,
            "input_tokens_details": {"cached_tokens": 0}, "output_tokens_details": {"reasoning_tokens": 0}}


def make_handler(log, script):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.0"

        def log_message(self, *args):
            pass

        def do_GET(self):
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"data":[]}')

        def do_POST(self):
            length = int(self.headers.get("content-length") or 0)
            raw = self.rfile.read(length) if length else b""
            try:
                body = json.loads(raw)
            except Exception:
                body = None
            index = COUNT["n"]
            COUNT["n"] += 1
            step = script[min(index, len(script) - 1)]
            headers = {k.lower(): v for k, v in self.headers.items() if k.lower() not in REDACT}
            tools, outputs, user_texts = [], 0, []
            if isinstance(body, dict):
                for t in body.get("tools") or []:
                    tools.append(t.get("name") or (t.get("function") or {}).get("name") or t.get("type"))
                for item in body.get("input") or []:
                    if not isinstance(item, dict):
                        continue
                    if item.get("type") == "function_call_output":
                        outputs += 1
                    if item.get("role") == "user":
                        content = item.get("content")
                        parts = content if isinstance(content, list) else [{"text": content}]
                        for part in parts:
                            if isinstance(part, dict) and isinstance(part.get("text"), str):
                                user_texts.append(part["text"][:120])
            ok = isinstance(body, dict)
            record = {
                "n": index, "path": self.path, "bytes": len(raw), "headers": headers,
                "model": body.get("model") if ok else None,
                "reasoning": body.get("reasoning") if ok else None,
                "prompt_cache_key": body.get("prompt_cache_key") if ok else None,
                "input_items": len(body.get("input") or []) if ok and isinstance(body.get("input"), list) else None,
                "function_call_outputs": outputs, "user_texts": user_texts,
                "tool_count": len(tools), "tool_names": tools,
                "tools_json_chars": len(json.dumps(body.get("tools"))) if ok and body.get("tools") else 0,
                "scripted": "tool_call" if "tool_call" in step else "text",
                "input_kinds": [str(i.get("role") or i.get("type")) + ("/" + str(i.get("type")) if i.get("role") and i.get("type") else "") for i in (body.get("input") or [])
                                if isinstance(i, dict)] if ok and isinstance(body.get("input"), list) else [],
                "tools_sha": sha(body.get("tools")) if ok else None,
                "instructions_sha": sha(body.get("instructions")) if ok else None,
                "input_shas": [sha(item) for item in (body.get("input") or [])] if ok and isinstance(body.get("input"), list) else [],
                "tool_search_schema": next((json.dumps(x.get("parameters"))[:400] for x in (body.get("tools") or [])
                                            if isinstance(x, dict) and x.get("name") == "tool_search"), None) if ok else None,
            }
            with open(log, "a") as fh:
                fh.write(json.dumps(record) + "\n")
            if step.get("delay_s"):
                time.sleep(step["delay_s"])
            self.send_response(200)
            self.send_header("content-type", "text/event-stream")
            self.end_headers()
            base = {"id": "resp_stub_%d" % index, "object": "response", "model": record["model"] or "stub",
                    "status": "in_progress", "output": []}
            chunks = [sse("response.created", {"type": "response.created", "response": base})]
            if "tool_call" in step:
                call = step["tool_call"]
                args = json.dumps(call.get("arguments") or {})
                fc_id, call_id = "fc_stub_%d" % index, "call_stub_%d" % index
                item = {"type": "function_call", "id": fc_id, "call_id": call_id, "name": call["name"],
                        "arguments": args, "status": "completed"}
                chunks += [
                    sse("response.output_item.added", {"type": "response.output_item.added", "output_index": 0,
                        "item": dict(item, arguments="", status="in_progress")}),
                    sse("response.function_call_arguments.delta", {"type": "response.function_call_arguments.delta",
                        "item_id": fc_id, "output_index": 0, "delta": args}),
                    sse("response.function_call_arguments.done", {"type": "response.function_call_arguments.done",
                        "item_id": fc_id, "output_index": 0, "arguments": args}),
                    sse("response.output_item.done", {"type": "response.output_item.done", "output_index": 0, "item": item}),
                    sse("response.completed", {"type": "response.completed", "response": dict(
                        base, status="completed", output=[item], usage=usage_block(100 + index))}),
                ]
            else:
                text = step.get("text", "STUB-OK")
                mid = "msg_stub_%d" % index
                msg = {"type": "message", "id": mid, "role": "assistant", "status": "completed",
                       "content": [{"type": "output_text", "text": text, "annotations": []}]}
                chunks += [
                    sse("response.output_item.added", {"type": "response.output_item.added", "output_index": 0,
                        "item": {"type": "message", "id": mid, "role": "assistant", "status": "in_progress", "content": []}}),
                    sse("response.content_part.added", {"type": "response.content_part.added", "item_id": mid,
                        "output_index": 0, "content_index": 0, "part": {"type": "output_text", "text": "", "annotations": []}}),
                    sse("response.output_text.delta", {"type": "response.output_text.delta", "item_id": mid,
                        "output_index": 0, "content_index": 0, "delta": text}),
                    sse("response.output_text.done", {"type": "response.output_text.done", "item_id": mid,
                        "output_index": 0, "content_index": 0, "text": text}),
                    sse("response.content_part.done", {"type": "response.content_part.done", "item_id": mid,
                        "output_index": 0, "content_index": 0, "part": {"type": "output_text", "text": text, "annotations": []}}),
                    sse("response.output_item.done", {"type": "response.output_item.done", "output_index": 0, "item": msg}),
                    sse("response.completed", {"type": "response.completed", "response": dict(
                        base, status="completed", output=[msg], usage=usage_block(100 + index))}),
                ]
            try:
                for chunk in chunks:
                    self.wfile.write(chunk)
                    self.wfile.flush()
            except BrokenPipeError:
                pass

    return Handler


if __name__ == "__main__":
    port, log = int(sys.argv[1]), sys.argv[2]
    steps = json.load(open(sys.argv[3])) if len(sys.argv) > 3 else [{"text": "STUB-OK"}]
    ThreadingHTTPServer(("127.0.0.1", port), make_handler(log, steps)).serve_forever()
