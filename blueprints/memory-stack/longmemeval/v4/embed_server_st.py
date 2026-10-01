#!/usr/bin/env python3
"""OpenAI-compatible embedding server over a model's reference implementation (PREREGISTRATION.md A15, A15.1).

One model per process, loaded with Sentence Transformers from the Hugging Face cache at the revision pinned in
pins.json (offline), in BF16 with PyTorch SDPA attention on CUDA (CPU fallback). It serves:

- POST /v1/embeddings: `input` is a string or a list of strings, used verbatim (clients add the model card's
  prompts themselves; this server never adds one). Outputs are L2-normalized float32. Every input is capped at
  --max-tokens (4,096) model tokens, special tokens included; each truncation is logged with its request.
- GET /v1/models, GET /api/version (the run script's health check) and GET /health.

A15.1: concurrent requests are batched dynamically. A single GPU thread takes whatever is pending, sorts it by
token length and cuts it into batches whose padded size (rows x longest input) stays within --batch-tokens.
Nothing is cached between requests (no prompt or KV reuse); the A13 byte-exact cache sits in front.

Gates, run at every start before the port opens (A15, A15.1), written to --gate-report:
- reference output: the model card's published example similarities, reproduced to 2 decimal places
  (|observed - published| <= 0.005 for every pair) for at least one of the card's published tables, each
  computed the way that table's runtime computes it (embed_gates.json). Failure exits with status 3.
- batch invariance: the gate texts embedded one at a time and inside one mixed batch must agree to a cosine of at
  least 0.9999. On failure the server runs single-sequence and says so in the report and in /health.

usage: embed_server_st.py --model REPO --revision SHA --port N [--gates embed_gates.json] [--gate-report PATH]
                          [--max-tokens 4096] [--batch-tokens 16384] [--max-batch 64] [--single-sequence] [--selftest]
"""
import argparse
import base64
import copy
import hashlib
import http.server
import json
import logging
import queue
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

LOG = logging.getLogger("embed_server_st")
VERSION = "lane-v4"


@dataclass
class Item:
    """One input text on its way through the batcher."""

    text: str
    tokens: int  # model tokens after the cap, used for the batch budget
    done: threading.Event = field(default_factory=threading.Event)
    vector: np.ndarray | None = None
    error: str | None = None


def plan_batches(items: list, budget_tokens: int, max_batch: int) -> list[list]:
    """Length-sorted batches whose padded size (rows x longest) stays within the token budget (A15.1).

    An input longer than the budget still runs, alone. max_batch = 1 is single-sequence processing.
    """
    batches, current = [], []
    for item in sorted(items, key=lambda it: it.tokens, reverse=True):
        longest = current[0].tokens if current else item.tokens  # sorted longest first
        if current and (len(current) >= max_batch or (len(current) + 1) * longest > budget_tokens):
            batches.append(current)
            current = []
        current.append(item)
    if current:
        batches.append(current)
    return batches


def parse_request(body: bytes, served: str, dim: int) -> list[str]:
    """Validate an OpenAI embeddings request; returns the input texts or raises ValueError / LookupError."""
    try:
        req = json.loads(body)
    except ValueError as e:
        raise ValueError(f"request body is not JSON: {e}") from e
    if not isinstance(req, dict):
        raise ValueError("request body must be a JSON object")
    if req.get("model") not in (None, served):
        raise LookupError(f"this server serves {served!r}, not {req.get('model')!r}")
    if req.get("dimensions") not in (None, dim):
        raise ValueError(f"{served} returns {dim} dimensions; truncated dimensions are not served")
    if req.get("encoding_format", "float") not in ("float", "base64"):
        raise ValueError("encoding_format must be float or base64")
    texts = req.get("input")
    if isinstance(texts, str):
        texts = [texts]
    if not isinstance(texts, list) or not texts or not all(isinstance(t, str) for t in texts):
        raise ValueError("input must be a non-empty string or a non-empty list of strings")
    if any(not t for t in texts):
        raise ValueError("input strings must not be empty")
    return texts


def response_body(vectors: np.ndarray, served: str, prompt_tokens: int, encoding: str = "float") -> bytes:
    data = []
    for i, v in enumerate(vectors):
        emb = base64.b64encode(v.astype("<f4").tobytes()).decode() if encoding == "base64" else [float(x) for x in v]
        data.append({"object": "embedding", "index": i, "embedding": emb})
    return json.dumps({"object": "list", "data": data, "model": served,
                       "usage": {"prompt_tokens": prompt_tokens, "total_tokens": prompt_tokens}}).encode()


def l2(v: np.ndarray) -> np.ndarray:
    v = np.asarray(v, dtype=np.float32)
    return v / np.linalg.norm(v, axis=-1, keepdims=True)


def invariance(single: np.ndarray, mixed: np.ndarray, threshold: float) -> dict:
    """A15.1: per-text cosine between one-at-a-time and mixed-batch embeddings."""
    cos = np.sum(l2(single) * l2(mixed), axis=1)
    return {"min_cosine": float(cos.min()), "max_deviation": float(1.0 - cos.min()), "threshold": threshold,
            "texts": len(cos), "pass": bool(cos.min() >= threshold)}


def table_check(observed: np.ndarray, published: list, tolerance: float) -> dict:
    dev = np.abs(np.asarray(observed, dtype=np.float64) - np.asarray(published, dtype=np.float64))
    return {"max_deviation": float(dev.max()), "observed": np.round(observed, 4).tolist(), "pass": bool(dev.max() <= tolerance)}


def gate_texts(spec: dict) -> tuple[list[str], list[str]]:
    queries = [spec["query_prefix"] + t for t in spec["queries"]]
    documents = [spec["document_prefix"] + t for t in spec["documents"]]
    return queries, documents


def long_texts(spec: dict, counter, targets=(1500, 6000)) -> list[str]:
    """Deterministic long gate inputs built from the card's documents: one inside the cap, one beyond it."""
    base = " ".join(spec["documents"])
    out = []
    for target in targets:
        text = base
        while counter(text) < target:
            text = text + " " + base
        out.append(spec["document_prefix"] + text)
    return out


class Engine:
    """The model's reference implementation through Sentence Transformers (imported only here)."""

    def __init__(self, model: str, revision: str, max_tokens: int, dtype: str, attn: str, device: str):
        import torch
        from sentence_transformers import SentenceTransformer
        self.torch = torch
        if device == "cuda" and not torch.cuda.is_available():
            LOG.warning("CUDA is not available; falling back to CPU")
            device = "cpu"
        if device == "mps" and not torch.backends.mps.is_available():  # the deployability gate's target host
            LOG.warning("MPS is not available; falling back to CPU")
            device = "cpu"
        self.device = device
        kwargs = {"dtype": getattr(torch, dtype)}
        if attn:
            kwargs["attn_implementation"] = attn
        self.model = SentenceTransformer(model, revision=revision, device=device, local_files_only=True,
                                         model_kwargs=kwargs)
        self.model.max_seq_length = max_tokens
        self.max_tokens = max_tokens
        self.tokenizer = self.model.tokenizer
        self.dim = int(self.model.get_sentence_embedding_dimension())
        # Request threads count tokens on a private copy of the Rust tokenizer: the model's own tokenizer is
        # reconfigured (truncation, padding) by every encode on the GPU thread and must not be shared.
        backend = getattr(self.tokenizer, "backend_tokenizer", None) or self.tokenizer._tokenizer
        self.counter = copy.deepcopy(backend)
        self.counter.no_truncation()
        self.counter.no_padding()
        self.count_lock = threading.Lock()

    def count(self, text: str) -> int:
        with self.count_lock:
            return len(self.counter.encode(text, add_special_tokens=True).ids)

    def encode_raw(self, texts: list[str]):
        """Embeddings in the model's dtype, as Sentence Transformers returns them (its Normalize module included)."""
        with self.torch.inference_mode():
            return self.model.encode(texts, batch_size=len(texts), prompt="", convert_to_tensor=True,
                                     normalize_embeddings=False, show_progress_bar=False)

    def encode(self, texts: list[str]) -> np.ndarray:
        return l2(self.encode_raw(texts).float().cpu().numpy())

    def similarity(self, queries: list[str], documents: list[str], dtype: str) -> np.ndarray:
        """A card table's similarity, computed as its runtime computes it (A15 gate)."""
        torch = self.torch
        raw = self.encode_raw(queries + documents)
        q, d = raw[:len(queries)], raw[len(queries):]
        if dtype == "bfloat16":  # Sentence Transformers' model.similarity on BF16 tensors (cos_sim)
            qn = torch.nn.functional.normalize(q.to(torch.bfloat16), p=2, dim=1)
            dn = torch.nn.functional.normalize(d.to(torch.bfloat16), p=2, dim=1)
            return torch.mm(qn, dn.transpose(0, 1)).float().cpu().numpy()
        return (q.float().cpu() @ d.float().cpu().T).numpy()  # the card's Transformers snippets: float32 matmul

    def recipe_similarity(self, queries: list[str], documents: list[str], recipe: dict) -> np.ndarray:
        """The card's own Transformers snippet (tokenize, forward, pool, normalize) on the same weights."""
        torch = self.torch
        tok, hf = self.tokenizer, self.model[0].auto_model
        side = tok.padding_side
        tok.padding_side = recipe.get("padding_side", side)
        try:
            batch = tok(queries + documents, max_length=recipe.get("max_length", self.max_tokens), padding=True,
                        truncation=True, return_tensors="pt").to(self.device)
            with torch.inference_mode():
                hidden = hf(**batch).last_hidden_state
            mask = batch["attention_mask"]
            if recipe["pooling"] == "last":
                if bool((mask[:, -1] == 1).all()):  # left padding
                    pooled = hidden[:, -1]
                else:
                    pooled = hidden[torch.arange(hidden.shape[0], device=hidden.device), mask.sum(dim=1) - 1]
            else:
                pooled = (hidden * mask[..., None]).sum(dim=1) / mask.sum(dim=1)[..., None]
            emb = torch.nn.functional.normalize(pooled, p=2, dim=1).float().cpu()
        finally:
            tok.padding_side = side
        return (emb[:len(queries)] @ emb[len(queries):].T).numpy()


def run_gates(engine, spec: dict, tolerance: float, threshold: float) -> dict:
    """Reference-output gate (A15) and batch-invariance gate (A15.1) for one model."""
    queries, documents = gate_texts(spec)
    report = {"reference": {"tables": [], "pass": False}, "batch_invariance": None}
    if spec.get("tables"):
        for table in spec["tables"]:
            got = engine.similarity(queries, documents, table["similarity_dtype"])
            report["reference"]["tables"].append({"runtime": table["runtime"], "similarity_dtype": table["similarity_dtype"]}
                                                 | table_check(got, table["values"], tolerance))
        report["reference"]["pass"] = any(t["pass"] for t in report["reference"]["tables"])
    elif spec.get("recipe"):  # no published values: the card's own Transformers snippet is the reference
        served = engine.encode(queries + documents)
        got = served[:len(queries)] @ served[len(queries):].T
        want = engine.recipe_similarity(queries, documents, spec["recipe"])
        check = table_check(got, want, tolerance)
        ranking_ok = bool(np.all(np.argmax(got, axis=1) == np.arange(len(queries))))
        report["reference"] = {"kind": "card Transformers snippet (the card publishes no values)",
                               "tables": [check | {"recipe": np.round(want, 4).tolist()}], "expected_ranking": ranking_ok,
                               "pass": check["pass"] and ranking_ok}
    served = engine.encode(queries + documents)  # A15.2: the deployability gate compares these across hosts
    report["gate_vectors"] = {"texts_sha256": [hashlib.sha256(t.encode()).hexdigest() for t in queries + documents],
                              "vectors_b64": [base64.b64encode(v.astype("<f4").tobytes()).decode() for v in served]}
    texts = queries + documents + long_texts(spec, engine.count)
    single = np.stack([engine.encode([t])[0] for t in texts])
    mixed = engine.encode(texts)
    report["batch_invariance"] = invariance(single, mixed, threshold)
    report["truncated_gate_inputs"] = sum(engine.count(t) > engine.max_tokens for t in texts)
    return report


class Batcher:
    """Collects pending inputs from every request and runs them on one GPU thread (A15.1)."""

    def __init__(self, engine, budget_tokens: int, max_batch: int, wait_ms: float):
        self.engine, self.budget, self.max_batch, self.wait = engine, budget_tokens, max_batch, wait_ms / 1000
        self.pending: queue.Queue = queue.Queue()
        threading.Thread(target=self.loop, daemon=True, name="gpu").start()

    def submit(self, items: list[Item]) -> None:
        for it in items:
            self.pending.put(it)
        for it in items:
            it.done.wait()

    def loop(self) -> None:
        while True:
            items = [self.pending.get()]
            deadline = time.monotonic() + self.wait
            while len(items) < 4 * self.max_batch:
                try:
                    items.append(self.pending.get(timeout=max(0.0, deadline - time.monotonic())))
                except queue.Empty:
                    break
            for batch in plan_batches(items, self.budget, self.max_batch):
                self.run(batch)

    def run(self, batch: list[Item]) -> None:
        try:
            vectors = self.engine.encode([it.text for it in batch])
            for it, v in zip(batch, vectors, strict=True):
                it.vector = v
        except Exception as e:  # noqa: BLE001 - reported to the request; an OOM retries in halves
            if "out of memory" in str(e).lower() and len(batch) > 1:
                LOG.warning("CUDA out of memory on %d inputs; retrying in halves", len(batch))
                self.engine.torch.cuda.empty_cache()
                half = len(batch) // 2
                self.run(batch[:half])
                self.run(batch[half:])
                return
            LOG.exception("encode failed")
            for it in batch:
                it.error = f"{type(e).__name__}: {e}"
        for it in batch:
            it.done.set()


def make_handler(state: dict):
    class Handler(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002 - the stdlib's signature
            pass

        def reply(self, status: int, body: bytes, ctype: str = "application/json") -> None:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def error(self, status: int, message: str, kind: str = "invalid_request_error") -> None:
            self.reply(status, json.dumps({"error": {"message": message, "type": kind, "code": status}}).encode())

        def do_GET(self):
            path = self.path.split("?")[0]
            if path == "/v1/models":
                self.reply(200, json.dumps({"object": "list", "data": [
                    {"id": state["name"], "object": "model", "owned_by": "embed_server_st"}]}).encode())
            elif path == "/api/version":
                self.reply(200, json.dumps({"version": f"embed_server_st {VERSION} {state['name']}@{state['revision']}"}).encode())
            elif path == "/health":
                self.reply(200, json.dumps({"status": "ok", "model": state["name"], "mode": state["mode"]}).encode())
            else:
                self.error(404, f"no route {path}")

        def do_POST(self):
            path = self.path.split("?")[0]
            body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
            if path != "/v1/embeddings":
                self.error(404, f"no route {path}")
                return
            try:
                texts = parse_request(body, state["name"], state["engine"].dim)
            except LookupError as e:
                self.error(404, str(e), "model_not_found")
                return
            except ValueError as e:
                self.error(400, str(e))
                return
            rid = uuid.uuid4().hex[:12]
            engine, cap = state["engine"], state["engine"].max_tokens
            counts = [engine.count(t) for t in texts]
            for i, n in enumerate(counts):
                if n > cap:  # A15: every embedder is capped at 4,096 input tokens, logged per request
                    LOG.info("request %s input %d truncated from %d to %d tokens", rid, i, n, cap)
            items = [Item(t, min(n, cap)) for t, n in zip(texts, counts, strict=True)]
            t0 = time.perf_counter()
            state["batcher"].submit(items)
            failed = [it.error for it in items if it.error]
            if failed:
                self.error(500, failed[0], "server_error")
                return
            tokens = sum(it.tokens for it in items)
            LOG.info("request %s inputs=%d tokens=%d truncated=%d ms=%.0f", rid, len(items), tokens,
                     sum(n > cap for n in counts), (time.perf_counter() - t0) * 1000)
            vectors = [it.vector for it in items if it.vector is not None]
            if len(vectors) != len(items):  # never answer with fewer vectors than inputs
                self.error(500, "an input was not embedded", "server_error")
                return
            encoding = json.loads(body).get("encoding_format", "float")
            self.reply(200, response_body(np.stack(vectors), state["name"], tokens, encoding))

    return Handler


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="Hugging Face repository id; also the served model name")
    ap.add_argument("--revision", required=True, help="the commit SHA pinned in pins.json")
    ap.add_argument("--port", type=int, default=11436)
    ap.add_argument("--max-tokens", type=int, default=4096)
    ap.add_argument("--batch-tokens", type=int, default=16384, help="padded tokens per forward pass")
    ap.add_argument("--max-batch", type=int, default=64)
    ap.add_argument("--batch-wait-ms", type=float, default=5.0)
    ap.add_argument("--dtype", default="bfloat16")
    ap.add_argument("--attn", default="sdpa", help="transformers attention implementation (sdpa or flash_attention_2)")
    ap.add_argument("--device", default="cuda", help="cuda (VelaNext), mps (the deployability gate on a Mac) or cpu")
    ap.add_argument("--gates", default=str(Path(__file__).with_name("embed_gates.json")))
    ap.add_argument("--gate-report", help="write the gate results here (JSON)")
    ap.add_argument("--single-sequence", action="store_true", help="one input per forward pass")
    ap.add_argument("--selftest", action="store_true", help="run the gates and exit")
    ap.add_argument("--log", help="log file (default: stderr)")
    a = ap.parse_args()
    logging.basicConfig(filename=a.log, level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    gates = json.loads(Path(a.gates).read_text())
    spec = gates["models"].get(a.model)
    if spec is None or spec.get("revision") != a.revision:
        sys.exit(f"{a.model}@{a.revision} has no gate specification in {a.gates}")
    engine = Engine(a.model, a.revision, a.max_tokens, a.dtype, a.attn, a.device)
    import sentence_transformers
    import torch
    import transformers
    report: dict[str, Any] = {"model": a.model, "revision": a.revision, "dtype": a.dtype, "attn": a.attn, "device": engine.device,
              "dim": engine.dim, "max_tokens": a.max_tokens, "batch_tokens": a.batch_tokens, "max_batch": a.max_batch,
              "versions": {"torch": torch.__version__, "cuda": torch.version.cuda, "transformers": transformers.__version__,
                           "sentence_transformers": sentence_transformers.__version__},
              "card": spec["card"], "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    report |= run_gates(engine, spec, gates["tolerance"], gates["batch_invariance_min_cosine"])
    single = a.single_sequence or not report["batch_invariance"]["pass"]
    report["mode"] = "single-sequence" if single else "batched"
    if not report["batch_invariance"]["pass"]:
        report["mode_reason"] = "batch-invariance gate failed: runs single-sequence (A15.1)"
    if a.gate_report:
        Path(a.gate_report).write_text(json.dumps(report, indent=1))
    LOG.info("gates: reference %s; batch invariance min cosine %.6f; mode %s",
             "pass" if report["reference"]["pass"] else "FAIL", report["batch_invariance"]["min_cosine"], report["mode"])
    print(json.dumps({k: report[k] for k in ("model", "mode", "reference", "batch_invariance")}, indent=1), flush=True)
    if not report["reference"]["pass"]:
        sys.exit(3)
    if a.selftest:
        return
    state = {"name": a.model, "revision": a.revision, "engine": engine, "mode": report["mode"],
             "batcher": Batcher(engine, a.batch_tokens, 1 if single else a.max_batch, a.batch_wait_ms)}
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", a.port), make_handler(state))
    srv.daemon_threads = True
    LOG.info("serving %s@%s on 127.0.0.1:%d (%s)", a.model, a.revision, a.port, report["mode"])
    srv.serve_forever()


if __name__ == "__main__":
    main()
