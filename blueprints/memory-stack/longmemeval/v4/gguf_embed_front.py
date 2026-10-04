#!/usr/bin/env python3
"""The 4,096-token cap in front of llama.cpp's `llama-server` for the GGUF embedders (PREREGISTRATION.md A15.1).

A15.1 serves the Qwen3-Embedding controls with a pinned llama.cpp CUDA `llama-server` (`--embeddings --pooling
last`, 16 slots) over the same GGUF blobs Ollama pulled, instead of single-slot Ollama. llama-server rejects an
input longer than a slot's context; Ollama, which the Mac arms used, truncated it (OLLAMA_CONTEXT_LENGTH=4096,
the production guard, A15: "Every embedder, old and new, is capped at 4,096 input tokens"). This front restores
the cap: each input keeps its first (4,096 - special tokens) content tokens plus the tokenizer's own special
tokens (Qwen3-Embedding's GGUF appends <|endoftext|>, which last-token pooling reads), and every truncation is
logged with its request. Inputs go to llama-server as token ids, so nothing is tokenized twice.

It answers /v1/embeddings (the model name must match the served name, e.g. `qwen3-embedding:4b`, so the
requests are byte-identical to the Mac's), /v1/models, /api/version and /health. The A13 cache sits in front.

`--selftest` runs the batch-invariance gate (A15.1): the gate texts one request at a time against one request
holding all of them (llama-server batches its slots), cosine >= 0.9999 per text; and, for information only, the
Qwen3-Embedding card's published example similarities (the card's model is unquantized; these are GGUF quants).

usage: gguf_embed_front.py --upstream http://127.0.0.1:11440 --port 11436 --name qwen3-embedding:4b
                           [--cap 4096] [--single-sequence] [--selftest --gate-report PATH]
"""
import argparse
import http.client
import http.server
import json
import logging
import sys
import threading
import time
import urllib.parse
import uuid
from pathlib import Path
from typing import Any

import numpy as np

from embed_server_st import invariance, l2, long_texts, parse_request, response_body, table_check

LOG = logging.getLogger("gguf_embed_front")
VERSION = "lane-v4"


def cap_tokens(full: list[int], content: list[int], cap: int) -> tuple[list[int], bool]:
    """Keep the tokenizer's special tokens and the first (cap - specials) content tokens.

    `full` is the tokenization with special tokens (as llama-server's embeddings endpoint tokenizes), `content`
    the same text without them. Returns the ids to embed and whether they were truncated.
    """
    if len(full) <= cap:
        return full, False
    n_special = len(full) - len(content)
    for start in range(max(n_special, 0) + 1):  # where the content sits inside the full tokenization
        if full[start:start + len(content)] == content:
            prefix, suffix = full[:start], full[start + len(content):]
            break
    else:
        raise ValueError("the special tokens do not wrap the content tokens")
    keep = cap - len(prefix) - len(suffix)
    if keep <= 0:
        raise ValueError(f"cap {cap} leaves no room for content")
    return prefix + content[:keep] + suffix, True


class Upstream:
    def __init__(self, url: str):
        self.url = urllib.parse.urlsplit(url.rstrip("/"))
        if not self.url.hostname:
            raise SystemExit(f"upstream URL has no host: {url!r}")
        self.host = self.url.hostname

    def post(self, path: str, body: dict, timeout: float = 3600) -> dict:
        conn = http.client.HTTPConnection(self.host, self.url.port, timeout=timeout)
        try:
            conn.request("POST", path, body=json.dumps(body), headers={"Content-Type": "application/json"})
            resp = conn.getresponse()
            data = resp.read()
        finally:
            conn.close()
        if resp.status != 200:
            raise RuntimeError(f"llama-server {path} HTTP {resp.status}: {data[:300]!r}")
        return json.loads(data)

    def get(self, path: str) -> tuple[int, bytes]:
        conn = http.client.HTTPConnection(self.host, self.url.port, timeout=30)
        try:
            conn.request("GET", path)
            resp = conn.getresponse()
            return resp.status, resp.read()
        finally:
            conn.close()

    def tokenize(self, text: str, special: bool) -> list[int]:
        return self.post("/tokenize", {"content": text, "add_special": special, "parse_special": True})["tokens"]

    def embed_ids(self, ids: list[list[int]]) -> np.ndarray:
        out = self.post("/v1/embeddings", {"input": ids, "encoding_format": "float"})
        data = sorted(out["data"], key=lambda d: d["index"])
        return l2(np.asarray([d["embedding"] for d in data], dtype=np.float32))


class Front:
    def __init__(self, upstream: Upstream, name: str, cap: int, single: bool):
        self.up, self.name, self.cap, self.single = upstream, name, cap, single
        self.lock = threading.Lock()
        self.dim = len(self.embed(["dimension probe"])[0][0])

    def prepare(self, text: str) -> tuple[list[int], int, bool]:
        full = self.up.tokenize(text, True)
        if len(full) <= self.cap:
            return full, len(full), False
        ids, truncated = cap_tokens(full, self.up.tokenize(text, False), self.cap)
        return ids, len(full), truncated

    def embed(self, texts: list[str], rid: str = "-") -> tuple[np.ndarray, int]:
        prepared = [self.prepare(t) for t in texts]
        for i, (ids, n, truncated) in enumerate(prepared):
            if truncated:
                LOG.info("request %s input %d truncated from %d to %d tokens", rid, i, n, len(ids))
        ids = [p[0] for p in prepared]
        if self.single:  # A15.1 fallback: one input per llama-server request, one request at a time
            with self.lock:
                vectors = np.concatenate([self.up.embed_ids([x]) for x in ids])
        else:
            vectors = self.up.embed_ids(ids)
        return vectors, sum(len(x) for x in ids)


def make_handler(front: Front, build: str):
    class Handler(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002 - the stdlib's signature
            pass

        def reply(self, status: int, body: bytes) -> None:
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def error(self, status: int, message: str, kind: str = "invalid_request_error") -> None:
            self.reply(status, json.dumps({"error": {"message": message, "type": kind, "code": status}}).encode())

        def do_GET(self):
            path = self.path.split("?")[0]
            if path == "/v1/models":
                self.reply(200, json.dumps({"object": "list", "data": [
                    {"id": front.name, "object": "model", "owned_by": "llama.cpp"}]}).encode())
            elif path == "/api/version":
                self.reply(200, json.dumps({"version": f"gguf_embed_front {VERSION} {front.name} llama.cpp {build}"}).encode())
            elif path == "/health":
                status, body = front.up.get("/health")
                self.reply(status, body)
            else:
                self.error(404, f"no route {path}")

        def do_POST(self):
            path = self.path.split("?")[0]
            body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
            if path != "/v1/embeddings":
                self.error(404, f"no route {path}")
                return
            try:
                texts = parse_request(body, front.name, front.dim)
            except LookupError as e:
                self.error(404, str(e), "model_not_found")
                return
            except ValueError as e:
                self.error(400, str(e))
                return
            rid = uuid.uuid4().hex[:12]
            t0 = time.perf_counter()
            try:
                vectors, tokens = front.embed(texts, rid)
            except (OSError, RuntimeError, ValueError) as e:
                LOG.exception("request %s failed", rid)
                self.error(502, f"llama-server: {e}", "server_error")
                return
            LOG.info("request %s inputs=%d tokens=%d ms=%.0f", rid, len(texts), tokens, (time.perf_counter() - t0) * 1000)
            self.reply(200, response_body(vectors, front.name, tokens, json.loads(body).get("encoding_format", "float")))

    return Handler


def selftest(front: Front, spec: dict, gates: dict) -> dict:
    queries = [spec["query_prefix"] + t for t in spec["queries"]]
    documents = [spec["document_prefix"] + t for t in spec["documents"]]
    texts = queries + documents + long_texts(spec, lambda t: len(front.up.tokenize(t, True)))
    single = np.concatenate([front.embed([t])[0] for t in texts])
    mixed = front.embed(texts)[0]
    report = {"batch_invariance": invariance(single, mixed, gates["batch_invariance_min_cosine"])}
    got = mixed[:len(queries)] @ mixed[len(queries):len(queries) + len(documents)].T
    report["card_reference_informational"] = [
        {"runtime": t["runtime"], "note": "the card's unquantized model; reported only"}
        | table_check(got, t["values"], gates["tolerance"]) for t in spec.get("tables", [])]
    return report


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--upstream", default="http://127.0.0.1:11440")
    ap.add_argument("--port", type=int, default=11436)
    ap.add_argument("--name", required=True, help="the served model name, e.g. qwen3-embedding:4b")
    ap.add_argument("--cap", type=int, default=4096)
    ap.add_argument("--build", default="v0.5.0 (b11146)", help="the llama.cpp release behind this front")
    ap.add_argument("--single-sequence", action="store_true")
    ap.add_argument("--gates", default=str(Path(__file__).with_name("embed_gates.json")))
    ap.add_argument("--gate-report")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--log")
    a = ap.parse_args()
    logging.basicConfig(filename=a.log, level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    front = Front(Upstream(a.upstream), a.name, a.cap, a.single_sequence)
    if a.selftest:
        gates = json.loads(Path(a.gates).read_text())
        spec = gates["gguf"][a.name]
        report: dict[str, Any] = {"model": a.name, "llama_cpp": a.build, "cap": a.cap, "dim": front.dim,
                  "mode": "single-sequence" if a.single_sequence else "batched", "card": spec["card"],
                  "at": time.strftime("%Y-%m-%dT%H:%M:%S")} | selftest(front, spec, gates)
        if a.gate_report:
            Path(a.gate_report).write_text(json.dumps(report, indent=1))
        print(json.dumps(report, indent=1), flush=True)
        sys.exit(0 if report["batch_invariance"]["pass"] else 4)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", a.port), make_handler(front, a.build))
    srv.daemon_threads = True
    LOG.info("serving %s on 127.0.0.1:%d -> %s (%s)", a.name, a.port, a.upstream,
             "single-sequence" if a.single_sequence else "batched")
    srv.serve_forever()


if __name__ == "__main__":
    main()
