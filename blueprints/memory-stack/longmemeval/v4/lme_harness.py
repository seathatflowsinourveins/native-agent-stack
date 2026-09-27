"""Neutral LongMemEval-S retrieval harness: identical inputs to every memory system, official metrics.

Protocol: PREREGISTRATION.md (amendments A1-A16.3). Official pieces are imported, not copied, from
xiaowu0162/LongMemEval@9e0b455: `process_item_flat_index` (session corpus ids and the official gold
relabelling) and `evaluate_retrieval` (recall_any / recall_all / ndcg_any). Two tracks are scored per
question: the official track (official labels) and the full-session track (gold = answer_session_ids).

Failure classes (A4): `infra` (server start, refused or reset connection, HTTP 5xx) retries the whole
question with a fresh store, at most twice; `deadline` (30 min ingest, 180 min for K1 (A16.1), 120 s query,
monotonic) and any other error score an empty ranking; a timeout in a setup or teardown call (an empty-store
check, a bank reset, an MCP handshake) is `infra`, never `deadline`; `env` (an embedding failure or degraded retrieval) is recorded
and makes the whole arm invalid until it is rerun.

v4 (A15, A15.1) keeps the v3 logic of every existing arm. It adds environment-configurable paths
(defaults are the Mac layout, unchanged), the A15 arms, a document prefix for the dense baseline, a
configurable dense batch size, and an agentmemory slot base with per-slot locks, so two agentmemory
arms can run at once on disjoint slots (A15.1). A16 adds MemPalace (M2) and Hindsight (K1, on its
preregistered subset) and the pooled-store stress mode; ai-memory's and agentmemory's runners are split into
start, ingest and query steps (the same calls in the same order) so the pooled stores reuse them.

usage: python lme_harness.py ARM [--limit N] [--ids ID ...] [--workers N] [--out DIR]
Arms: bm25-full, dense-qwen3, aimem-fts, aimem-minilm, aimem-qwen3, aimem-qwen3-rerank,
      aimem-qwen3-8b, aimem-qwen3-0.6b, am-keyless, am-minilm, am-qwen3
A15:  am-nemotron-8b, am-nemotron-1b, am-harrier-0.6b (E1-E3); aimem-nemotron-8b, aimem-nemotron-1b,
      aimem-harrier-0.6b (F1-F3); dense-qwen3-bf16 (G0), dense-nemotron-8b, dense-nemotron-1b,
      dense-harrier-0.6b (G1-G3); aimem-qwen3-rerank-qwen3.6, aimem-qwen3-rerank-nemotron-lightning,
      aimem-qwen3-rerank-lfm2.5 (H1-H3); A15.2: aimem-<embedder>-fill (F cache-fill passes, no decision),
      am-minilm-hooks (D2h)
A16:  mempalace-palace (M2), hindsight-qwen3.6 (K1, on k1-subset.json); D2h joins the A16 family;
      --pooled runs an arm against one store holding every eligible session (pooled-<arm>.jsonl, descriptive)
Output: results/<arm>.jsonl, one line per question; reruns resume by question id.

Environment (A15; unset = the Mac defaults below):
  LME_HOME          data/, cache/ and models/ (default: this directory)
  LME_DATA          the dataset file (default: $LME_HOME/data/longmemeval_s_cleaned.json)
  LME_OFFICIAL_DIR  the official LongMemEval checkout at 9e0b455
  LME_AIMEM_BIN     the ai-memory 19b6429 binary
  LME_AM_ROOT       the agentmemory 0.9.29 install (node_modules, bin/iii)
  LME_III_BIN       the iii 0.11.2 engine (default: $LME_AM_ROOT/bin/iii)
  LME_MINILM_DIR    all-MiniLM-L6-v2 for ai-memory's local embedder
  LME_NODE          the node binary for agentmemory (default: `mise which node`)
  LME_EMBED_URL, LME_LLM_URL, LME_AM_SLOTS (this process's agentmemory workers) as in v3
  LME_AM_SLOT_POOL  agentmemory slots shared by every harness process on the host (default 16, A15.1)
  LME_DENSE_BATCH   texts per dense embedding request (default 8 as in v3; VelaNext sends 64, A15.1)
  LME_EMBED_UPSTREAM  the embedding server behind the A13 cache: health probes go there directly
  LME_EMBED_ID      the dense cache's embedder identity (default: the A13 proxy's upstream fingerprint)
  LME_MEMPALACE_VENV  MemPalace 3.10.0's virtual environment (bin/mempalace, bin/mempalace-mcp; A16)
  LME_MEMPALACE_ONNX  chromadb's verified all-MiniLM-L6-v2 ONNX directory (onnx/model.onnx; A16)
  LME_HINDSIGHT_URL   the Hindsight 0.10.1 API server (A16 K1; its LLM is LME_LLM_URL)

Review fixes (2026-09-25, before any VelaNext run): agentmemory slots are claimed per question from one
host-wide pool under a cross-process lock; teardown kills only agentmemory's own processes; probes bypass
the cache; agentmemory arms fail as env errors when the proxy saw upstream errors during a query; the dense
cache is namespaced by the embedder identity; exhausted infra retries of an embedding-dependent arm are env
errors when the service is down (always for the dense arms); infra retries back off; a preflight checks
binaries, tools and the embedding service before the pool starts; the first env error stops the arm; one
process per arm output (a lock file), and a truncated last row from a crash is set aside on resume.
"""
import argparse
import fcntl
import hashlib
import json
import os
import queue
import re
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
AE = Path.home() / ".local/share/agent-ecosystem"
LME_HOME = Path(os.environ.get("LME_HOME", HERE))  # A15: data, caches and models; the Mac keeps them next to the code
LME = Path(os.environ.get("LME_OFFICIAL_DIR", AE / "src/LongMemEval"))
sys.path.insert(0, str(LME))
try:
    from src.retrieval.eval_utils import evaluate_retrieval  # noqa: E402  (official)
    from src.retrieval.run_retrieval import process_item_flat_index  # noqa: E402  (official)
    OFFICIAL_IMPORT_ERROR = None
except ImportError as _official_error:  # A15: the lane's unit tests import this module without the checkout
    OFFICIAL_IMPORT_ERROR = f"{type(_official_error).__name__}: {_official_error}"

    def evaluate_retrieval(*_args, **_kwargs):
        raise RuntimeError(f"official LongMemEval code is not importable from {LME}: {OFFICIAL_IMPORT_ERROR}")

    process_item_flat_index = evaluate_retrieval

DATA = Path(os.environ.get("LME_DATA", LME_HOME / "data/longmemeval_s_cleaned.json"))
MANIFEST = HERE / "eligible-manifest.json"
KS = [1, 3, 5, 10, 30, 50]
MAX_RANK = 50
OLLAMA = "http://127.0.0.1:11434"
EMBED_URL = os.environ.get("LME_EMBED_URL", OLLAMA)  # A11: arms started later use the benchmark embed server
AM_SLOTS = int(os.environ.get("LME_AM_SLOTS", "4"))  # A11: isolated agentmemory slots (this process's workers)
AM_SLOT_POOL = int(os.environ.get("LME_AM_SLOT_POOL", "16"))  # A15.1: host-wide pool, locked per question
EMBED_UPSTREAM = os.environ.get("LME_EMBED_UPSTREAM", "")  # A15: probes reach the live server, not the cache
EMBED_ID = os.environ.get("LME_EMBED_ID", "")  # A15: the dense cache's embedder identity
LLM_URL = os.environ.get("LME_LLM_URL", OLLAMA)  # A12: the reranker LLM endpoint for C4
DENSE_BATCH = int(os.environ.get("LME_DENSE_BATCH", "8"))  # A15.1: the dense baseline sends batches of 64 on VelaNext
RERANK_FALLBACK = {"rerank_timeouts": "reranker timed out; keeping pre-rerank order",
                   "rerank_failures": "reranker failed; keeping pre-rerank order",
                   "rerank_invalid": "reranker returned incomplete or invalid scores; keeping pre-rerank order"}
AIMEM_BIN = Path(os.environ.get("LME_AIMEM_BIN", AE / "tools/ai-memory-2.5.0-19b6429/ai-memory"))
AIMEM_TOKEN = "lme-bench-token"
AIMEM_LIMIT = 50  # A10: the registered retrieval depth for every system
MINILM_DIR = Path(os.environ.get("LME_MINILM_DIR", LME_HOME / "models/all-MiniLM-L6-v2"))
AM_ROOT = Path(os.environ.get("LME_AM_ROOT", AE / "bench/agentmemory"))
AM_INDEX = AM_ROOT / "node_modules/@agentmemory/agentmemory/dist/index.mjs"
III_BIN = Path(os.environ.get("LME_III_BIN", AM_ROOT / "bin/iii"))
PROD_QUERY_PREFIX = ("Instruct: Given a question about past work, decisions or project knowledge, "
                     "retrieve the memory pages that answer it\nQuery:")
DENSE_QUERY_PREFIX = ("Instruct: Given a question about the user's past conversations, retrieve the chat "
                      "sessions that contain the answer\nQuery:")
# A15 embedders, served by embed_server_st.py from each developer's reference implementation (BF16) behind the
# A13 cache. Prefixes, dimensions and pooling are taken from each model card at the revision pinned in
# pins.json:
# - nvidia/Nemotron-3-Embed-8B-BF16 @ d1f2f25730bbd775b99b29185134bc86653bf2d1 and
#   nvidia/Nemotron-3-Embed-1B-BF16 @ c0c9fea93ea424587517f2c59e20db9f1d6bf615
#   (https://huggingface.co/nvidia/Nemotron-3-Embed-8B-BF16, .../Nemotron-3-Embed-1B-BF16): "Add the `query: `
#   prefix for queries and the `passage: ` prefix for documents"; mean pooling, L2-normalized; 4096 and 2048
#   dimensions; "We set the model sequence length to 4096 for the evaluation results".
# - microsoft/harrier-oss-v1-0.6b @ f9b9dc8d367d443f2479d27aa5d8d2850c0774ee
#   (https://huggingface.co/microsoft/harrier-oss-v1-0.6b): queries "Instruct: {task}\nQuery: {query}" (a space
#   after "Query:"), "No need to add instruction for retrieval documents"; last-token pooling, L2-normalized,
#   1024 dimensions. The task sentences are the ones production (C3) and the dense baseline (B2) already use.
# - Qwen/Qwen3-Embedding-4B @ 5cf2132abc99cad020ac570b19d031efec650f2b (G0, https://huggingface.co/Qwen/
#   Qwen3-Embedding-4B): "Instruct: {task}\nQuery:{query}" (no space), documents plain; last-token pooling,
#   2560 dimensions. G0 keeps B2's prefix, so it differs from B2 only in quantization and runtime.
NEMOTRON_8B, NEMOTRON_1B = "nvidia/Nemotron-3-Embed-8B-BF16", "nvidia/Nemotron-3-Embed-1B-BF16"
HARRIER = "microsoft/harrier-oss-v1-0.6b"
QWEN3_4B_BF16 = "Qwen/Qwen3-Embedding-4B"
NEMOTRON_QUERY_PREFIX, NEMOTRON_DOCUMENT_PREFIX = "query: ", "passage: "
HARRIER_PROD_QUERY_PREFIX = PROD_QUERY_PREFIX + " "
HARRIER_DENSE_QUERY_PREFIX = DENSE_QUERY_PREFIX + " "
A15_EMBEDDERS = {  # served model name -> (dimensions, ai-memory query prefix, dense query prefix, document prefix)
    NEMOTRON_8B: (4096, NEMOTRON_QUERY_PREFIX, NEMOTRON_QUERY_PREFIX, NEMOTRON_DOCUMENT_PREFIX),
    NEMOTRON_1B: (2048, NEMOTRON_QUERY_PREFIX, NEMOTRON_QUERY_PREFIX, NEMOTRON_DOCUMENT_PREFIX),
    HARRIER: (1024, HARRIER_PROD_QUERY_PREFIX, HARRIER_DENSE_QUERY_PREFIX, ""),
}
# A15 reranker LLMs (H1-H3): official GGUF builds on Ollama 0.34.4, pinned by digest in pins.json. A15.2: C4 and
# H use production's Modelfile parameters (num_ctx 65536 and production's sampling, ollama/*.Modelfile) and
# production's reasoning setting (AI_MEMORY_LLM_REASONING_EFFORT "low", as C4), so an H arm is C4 with only the
# model changed. A15's "thinking off" for H1 and H2 is superseded by A15.2's "the same sampling and reasoning
# settings". C4 keeps production's name, qwen3.5-9b-64k, created on VelaNext from the qwen3.5:9b GGUF.
# - H1 qwen3.6:35b-a3b (https://ollama.com/library/qwen3.6:35b-a3b, Q4_K_M).
# - H2 nemotron-3.5-lightning:30b-a3b, the Ollama tag NVIDIA's card gives for Ollama ("ollama run
#   nemotron-3.5-lightning", https://huggingface.co/nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4).
# - H3 hf.co/LiquidAI/LFM2.5-2.6B-GGUF:Q4_K_M, Liquid AI's own GGUF repository ("LFM2.5-2.6B is a pure reasoning
#   model that always thinks", https://huggingface.co/LiquidAI/LFM2.5-2.6B). Its licence (LFM1.0) needs review.
H_RERANK_MODELS = {"aimem-qwen3-rerank-qwen3.6": "qwen3.6-35b-a3b-64k",
                   "aimem-qwen3-rerank-nemotron-lightning": "nemotron-3.5-lightning-30b-a3b-64k",
                   "aimem-qwen3-rerank-lfm2.5": "lfm2.5-2.6b-64k"}
# A16 memory-system trial arms (PREREGISTRATION.md A16; alpha 0.0167, both references). Official releases only:
# - M2: MemPalace 3.10.0 (MIT, PyPI wheel sha256 9f656452..., pins.json) in palace (production) mode: `mempalace
#   init`, then each dated session as a Claude Code transcript through its shipped hook runner (`mempalace hook
#   run`: Stop after each assistant turn, SessionEnd at the end), which mines through its shipped convo miner;
#   the query is the MCP server's `mempalace_search`, sessions ranked by first hit. Embeddings: chromadb 1.5.9's
#   own all-MiniLM-L6-v2 ONNX, verified against chromadb's pinned sha256 and placed in each store's cache.
# A16.3: no arm is ever cache-only. ai-memory writes wall-clock timestamps into every session page body, so C4, F
# and H never repeat C3's requests byte for byte: each computes its own embeddings on the same GPU server.
# - K1: Hindsight 0.10.1 (MIT, PyPI hindsight-api) with Qwen3.6-35B-A3B from the H1 build (the same GGUF, served
#   by llama-server, at production's reasoning setting), one memory bank per question: retain(transcript,
#   timestamp, document_id=session_id) per session, where the session id is Protocol step 2's hashed id (no id
#   contains "answer", and a repeated session keeps one id per occurrence, A7), recall(query_timestamp=
#   question_date), sessions ranked by first-seen document_id; on the preregistered stratified subset
#   (k1-subset.json, seed 20260925), with A16.1's 180-minute ingest budget.
M2, K1 = "mempalace-palace", "hindsight-qwen3.6"
MP_VENV = Path(os.environ.get("LME_MEMPALACE_VENV", LME_HOME / ".venv-mempalace"))
MP_ONNX = Path(os.environ.get("LME_MEMPALACE_ONNX", LME_HOME / "models/chroma-onnx/all-MiniLM-L6-v2"))
MP_HOOK_TIMEOUT_S = 180
HS_URL = os.environ.get("LME_HINDSIGHT_URL", "http://127.0.0.1:11441")
K1_SUBSET = HERE / "k1-subset.json"
POOLED_BUDGET_S = 3 * 24 * 3600  # A16 pooled run: a backstop only; A16.1's 24 h estimate decides who runs
K1_INGEST_BUDGET_S = 180 * 60  # A16.1: Hindsight extracts facts with an LLM on every retain
TEARDOWN_BUDGET_S = 15 * 60  # after a K1 deadline: let abandoned extractions finish before the bank is deleted
INGEST_BUDGET_S = 30 * 60
QUERY_BUDGET_S = 120
INFRA_RETRIES = 2
INFRA_BACKOFF_S = (5, 30)  # A15 review: a short proxy or server restart must not use up the retries
AIMEM_DEGRADED = re.compile(r"embedder failed; degrading memory_query|embedding failed; page indexed without it")


class InfraError(Exception):
    """Server failed to start, connection refused or reset, or HTTP 5xx: retried with a fresh store."""


class DeadlineError(Exception):
    """A monotonic ingest or query budget ran out: scored as an empty ranking."""


class EnvError(Exception):
    """Embedding failure or degraded retrieval: the arm is invalid until rerun (A4)."""


class Deadline:
    def __init__(self, seconds: float, what: str):
        self.end, self.what = time.monotonic() + seconds, what

    def left(self) -> float:
        remaining = self.end - time.monotonic()
        if remaining <= 0:
            raise DeadlineError(f"{self.what} budget exhausted")
        return remaining


@contextmanager
def setup_step(what: str):
    """A timeout outside A4's ingest and query budgets (store checks, bank resets, handshakes) is infra, so the
    question is retried on a fresh store instead of being scored as a deadline failure (review, infra F5)."""
    try:
        yield
    except DeadlineError as e:
        raise InfraError(f"{what} timed out: {e}") from e


# ---------------------------------------------------------------- inputs and scoring

def hashed_id(qid: str, sid: str, occurrence: int) -> str:
    return "s" + hashlib.sha256(f"{qid}:{sid}:{occurrence}".encode()).hexdigest()[:16]


def parse_date(s: str) -> datetime:
    return datetime.strptime(s.split(" (")[0] + " " + s.split(") ")[-1], "%Y/%m/%d %H:%M")


def sessions_of(q: dict) -> list[dict]:
    """Haystack sessions in chronological order, each with its hashed id and original position."""
    seen: dict[str, int] = {}
    out = []
    for i, (sid, sess, date) in enumerate(zip(q["haystack_session_ids"], q["haystack_sessions"],
                                              q["haystack_dates"])):
        occ = seen.get(sid, 0)
        seen[sid] = occ + 1
        out.append({"pos": i, "hid": hashed_id(q["question_id"], sid, occ), "date": date, "turns": sess})
    out.sort(key=lambda s: (parse_date(str(s["date"])), s["pos"]))
    return out


def score(q: dict, ranking: list[int]) -> dict:
    """Official metrics on both tracks for a ranking of haystack positions."""
    ranking = ranking[:MAX_RANK]
    official_ids = []
    for sid, sess, ts in zip(q["haystack_session_ids"], q["haystack_sessions"], q["haystack_dates"]):
        _, ids, _ = process_item_flat_index(sess, "session", sid, ts)
        official_ids += ids
    official_gold = list({c for c in official_ids if "answer" in c})
    full_ids = list(q["haystack_session_ids"])
    full_gold = list(q["answer_session_ids"])
    out = {"official": {}, "full": {}}
    for k in KS:
        for track, ids, gold in (("official", official_ids, official_gold), ("full", full_ids, full_gold)):
            ra, rl, nd = evaluate_retrieval(ranking, gold, ids, k=k)
            out[track].update({f"recall_any@{k}": ra, f"recall_all@{k}": rl, f"ndcg_any@{k}": nd})
    return out


def dated(s: dict, text: str) -> str:
    return f"[session date: {s['date']}]\n{text}"


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def http_json(url: str, body=None, headers=None, timeout: float = QUERY_BUDGET_S):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=max(timeout, 0.1)) as resp:
            return resp.status, resp.headers.get("content-type", ""), resp.read().decode()
    except urllib.error.HTTPError as e:
        if e.code >= 500:
            raise InfraError(f"HTTP {e.code} from {url}: {e.read().decode(errors='replace')[:200]}") from e
        return e.code, e.headers.get("content-type", ""), e.read().decode(errors="replace")
    except TimeoutError as e:
        raise DeadlineError(f"timeout calling {url}") from e
    except (ConnectionError, urllib.error.URLError) as e:
        if isinstance(getattr(e, "reason", None), TimeoutError):
            raise DeadlineError(f"timeout calling {url}") from e
        raise InfraError(str(e)) from e


def wait_http(url: str, proc: subprocess.Popen, timeout=120, ok=lambda s, b: True):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if proc.poll() is not None:
            raise InfraError(f"server exited with {proc.returncode}")
        try:
            status, _, body = http_json(url, timeout=2)
            if ok(status, body):
                return
        except (InfraError, DeadlineError, OSError):
            pass
        time.sleep(0.2)
    raise InfraError(f"server not ready at {url}")


def stop(proc: subprocess.Popen | None):
    if proc and proc.poll() is None:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
            proc.wait(timeout=10)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


def clean_env(home: str) -> dict:
    return {"HOME": home, "PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "LANG": "en_US.UTF-8", "TMPDIR": home}


def probe_embeddings(model: str):
    """Environment check for arms that depend on the embedding service.

    A15 review: the probe must reach the live server, never the A13 cache. It goes to LME_EMBED_UPSTREAM when that
    is set, and otherwise sends a unique text with `Cache-Control: no-store`.
    """
    for base in [EMBED_UPSTREAM or EMBED_URL] + ([EMBED_URL] if EMBED_UPSTREAM and EMBED_UPSTREAM != EMBED_URL else []):
        try:  # the upstream directly, then (review, infra F7) through the proxy, which passes no-store through
            status, _, body = http_json(f"{base}/v1/embeddings",
                                        {"model": model, "input": [f"probe {uuid.uuid4().hex}"]},
                                        headers={"Cache-Control": "no-store"}, timeout=60)
            vec = json.loads(body)["data"][0]["embedding"] if status == 200 else None
        except (InfraError, DeadlineError, ValueError, KeyError, IndexError) as e:
            raise EnvError(f"embedding service probe failed at {base}: {e}") from e
        if not vec or not any(vec):
            raise EnvError(f"embedding service probe at {base} returned HTTP {status} or a zero vector")


def upstream_errors(probe_model: str | None) -> int | None:
    """The proxy's upstream-error counter before an agentmemory query, for the BM25-fallback guard. With a proxy
    in front (LME_EMBED_UPSTREAM set), unreadable stats fail closed (review, infra F7)."""
    if not probe_model:
        return None
    count = ((proxy_stats() or {}).get("counters") or {}).get("upstream_errors")
    if count is None and EMBED_UPSTREAM:
        raise EnvError("embedding proxy /__stats unavailable before the query")
    return count


def proxy_stats() -> dict | None:
    """A15: the A13 proxy's counters and upstream fingerprint (GET /__stats), or None when EMBED_URL is no such proxy."""
    try:
        status, _, body = http_json(f"{EMBED_URL}/__stats", timeout=10)
        return json.loads(body) if status == 200 else None
    except (InfraError, DeadlineError, ValueError):
        return None


def embedding_model(fn, cfg: dict) -> str | None:
    """The model an arm's embedding service must serve, or None for arms without one."""
    if cfg.get("model"):
        return cfg["model"]
    if cfg.get("probe_model"):
        return cfg["probe_model"]
    env = cfg.get("env", {})
    if env.get("AI_MEMORY_EMBEDDING_PROVIDER") == "openai-compat":
        return env.get("AI_MEMORY_EMBEDDING_MODEL")
    return None


# ---------------------------------------------------------------- neutral baselines

def run_bm25_full(q: dict, _cfg: dict) -> dict:
    from rank_bm25 import BM25Okapi
    sess = sessions_of(q)
    docs = [dated(s, " ".join(t["content"] for t in s["turns"])) for s in sess]
    bm25 = BM25Okapi([d.split(" ") for d in docs])  # official tokenisation
    t0 = time.perf_counter()
    order = np.argsort(bm25.get_scores(q["question"].split(" ")))[::-1]
    return {"ranking": [sess[i]["pos"] for i in order], "latency_ms": (time.perf_counter() - t0) * 1000}


class EmbedCache:
    """The dense arm's own vector cache.

    A15 review: it is namespaced by the embedder identity (LME_EMBED_ID, else the A13 proxy's upstream
    fingerprint), with one file per namespace and the namespace recorded in the file, so vectors from one
    server can never answer for another. The empty namespace (the Mac, v3) keeps v3's file and keys.
    """

    def __init__(self, path: Path, model: str, namespace: str = ""):
        if namespace:
            path = path.with_name(f"{path.stem}-{hashlib.sha256(namespace.encode()).hexdigest()[:12]}{path.suffix}")
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute("CREATE TABLE IF NOT EXISTS e (k TEXT PRIMARY KEY, v BLOB)")
        self.db.execute("CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT)")
        row = self.db.execute("SELECT v FROM meta WHERE k = 'namespace'").fetchone()
        if row is None:
            self.db.execute("INSERT INTO meta VALUES ('namespace', ?)", (namespace,))
            self.db.commit()
        elif row[0] != namespace:
            raise EnvError(f"dense cache {path} belongs to embedder {row[0]!r}, not {namespace!r}")
        self.model, self.ns, self.path, self.lock = model, namespace, path, threading.Lock()

    def key(self, text: str) -> str:
        if not self.ns:
            return hashlib.sha256(f"{self.model}\0{text}".encode()).hexdigest()
        return hashlib.sha256(f"{self.ns}\0{self.model}\0{text}".encode()).hexdigest()

    def embed(self, texts: list[str], deadline: Deadline) -> np.ndarray:
        keys = [self.key(t) for t in texts]
        with self.lock:
            have = {k: np.frombuffer(v, dtype=np.float32) for k, v in
                    self.db.execute(f"SELECT k, v FROM e WHERE k IN ({','.join('?' * len(keys))})", keys)}
        missing = [(k, t) for k, t in zip(keys, texts) if k not in have]
        for i in range(0, len(missing), DENSE_BATCH):
            chunk = missing[i:i + DENSE_BATCH]
            try:
                status, _, body = http_json(f"{EMBED_URL}/v1/embeddings",
                                            {"model": self.model, "input": [t for _, t in chunk]}, timeout=deadline.left())
            except InfraError:
                probe_embeddings(self.model)  # A15 review: a service that is down is an env fault (A4), not a retry
                raise
            if status != 200:
                raise EnvError(f"embeddings HTTP {status}: {body[:200]}")
            vecs = [np.asarray(d["embedding"], dtype=np.float32) for d in json.loads(body)["data"]]
            if any(not np.any(v) for v in vecs):
                raise EnvError("zero embedding vector returned")
            with self.lock:
                for (k, _), v in zip(chunk, vecs):
                    have[k] = v
                    self.db.execute("INSERT OR REPLACE INTO e VALUES (?, ?)", (k, v.tobytes()))
                self.db.commit()
        m = np.stack([have[k] for k in keys])
        return m / np.linalg.norm(m, axis=1, keepdims=True)


_CACHE: dict = {}
_CACHE_LOCK = threading.Lock()


def dense_namespace() -> str:
    """A15 review: the identity of the embedder behind EMBED_URL, for the dense cache's namespace."""
    if EMBED_ID:
        return EMBED_ID
    stats = proxy_stats()
    return (stats or {}).get("fingerprint", "")


def run_dense(q: dict, cfg: dict) -> dict:
    with _CACHE_LOCK:
        if cfg["model"] not in _CACHE:
            _CACHE[cfg["model"]] = EmbedCache(LME_HOME / "cache/embeddings.sqlite", cfg["model"], dense_namespace())
    cache = _CACHE[cfg["model"]]
    sess = sessions_of(q)
    # A15: a model card's document prompt precedes the dated session text; empty for every v3 arm.
    docs = [cfg.get("doc_prefix", "") + dated(s, " ".join(t["content"] for t in s["turns"] if t["role"] == "user"))
            for s in sess]
    t_ingest = time.perf_counter()
    dvec = cache.embed(docs, Deadline(INGEST_BUDGET_S, "ingest"))
    ingest_s = time.perf_counter() - t_ingest
    t0 = time.perf_counter()
    qvec = cache.embed([cfg["query_prefix"] + q["question"]], Deadline(QUERY_BUDGET_S, "query"))[0]
    order = np.argsort(dvec @ qvec)[::-1]
    return {"ranking": [sess[i]["pos"] for i in order], "latency_ms": (time.perf_counter() - t0) * 1000,
            "ingest_s": ingest_s}


# ---------------------------------------------------------------- ai-memory (production hook path)

def aimem_items(q: dict, sess: list[dict], project: str) -> list[dict]:
    """Mirror of ai-memory evals/src/retrieval/ingest.rs::build_items, with hashed session ids."""
    items = []

    def push(event, sid, extra):
        url = (f"/hook?event={event}&agent=claude-code&workspace=longmemeval&project={project}"
               f"&session_id={sid}")
        if event == "stop":
            url += "&capture_assistant=1"
        items.append({"url": url, "body": {"session_id": sid, "cwd": f"/lme/{project}", **extra}})

    for s in sess:
        sid, date = s["hid"], s["date"]
        push("session-start", sid, {"hook_event_name": "SessionStart", "source": "startup"})
        for turn in s["turns"]:
            if turn["role"] == "user":
                push("user-prompt-submit", sid, {"hook_event_name": "UserPromptSubmit",
                                                 "prompt": f"[session date: {date}] {turn['content']}"})
            elif turn["role"] == "assistant":
                excerpt = turn["content"].encode()[:2000].decode(errors="ignore")  # 2 KB cap, char-safe
                push("stop", sid, {"hook_event_name": "Stop",
                                   "_ai_memory_assistant": {"version": 1,
                                                            "excerpt": f"[session date: {date}] {excerpt}"}})
        push("session-end", sid, {"hook_event_name": "SessionEnd", "reason": "exit"})
    return items


def aimem_query(base: str, project: str, text: str, limit: int, deadline: Deadline) -> dict:
    status, ctype, body = http_json(f"{base}/mcp", {
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "memory_query",
                   "arguments": {"query": text, "workspace": "longmemeval", "project": project, "limit": limit}}},
        headers={"Authorization": f"Bearer {AIMEM_TOKEN}", "Accept": "application/json, text/event-stream"},
        timeout=deadline.left())
    if status != 200:
        raise RuntimeError(f"MCP HTTP {status}: {body[:300]}")
    if ctype.startswith("text/event-stream"):
        rpc = [json.loads(line[5:]) for line in body.splitlines() if line.startswith("data:") and '"id"' in line][-1]
    else:
        rpc = json.loads(body)
    if "error" in rpc or rpc["result"].get("isError"):
        raise RuntimeError(f"memory_query error: {json.dumps(rpc)[:300]}")
    return json.loads(rpc["result"]["content"][0]["text"])


def aimem_start(cfg: dict, home: str, project: str) -> tuple:
    """Start one ai-memory server on a fresh data directory and check that the project is empty (v3 logic)."""
    data_dir = Path(home) / "data"
    stderr_path = Path(home) / "stderr.log"
    if cfg.get("minilm"):
        shutil.copytree(MINILM_DIR, data_dir / "models/all-MiniLM-L6-v2")
    port = free_port()
    env = clean_env(home) | {
        "AI_MEMORY_AUTH_TOKEN": AIMEM_TOKEN, "AI_MEMORY_CAPTURE_ASSISTANT": "true",
        "AI_MEMORY_AUTO_IMPROVE__SCHEDULER__ENABLED": "false", "AI_MEMORY_CONSOLIDATE_ON_SESSION_END": "false",
        "AI_MEMORY_DREAM__ENABLED": "false", "AI_MEMORY_MAINTENANCE__ENABLED": "false",
    } | cfg["env"]
    proc = subprocess.Popen([str(AIMEM_BIN), "serve", "--transport", "http", "--bind", f"127.0.0.1:{port}",
                             "--data-dir", str(data_dir)], env=env, cwd=home, stdout=subprocess.DEVNULL,
                            stderr=open(stderr_path, "w"), start_new_session=True)
    base = f"http://127.0.0.1:{port}"
    try:
        wait_http(f"{base}/", proc)
        try:
            with setup_step("ai-memory empty-store check"):
                pre = aimem_query(base, project, "anything", 10, Deadline(QUERY_BUDGET_S, "empty-store check"))
        except RuntimeError as e:  # a fresh store has no workspace yet: that is the empty state
            if "not found" not in str(e):
                raise
            pre = {}
        if pre.get("hits") or pre.get("raw_hits"):
            raise RuntimeError("store not empty before ingest")
    except BaseException:
        stop(proc)
        raise
    return proc, base, data_dir, stderr_path


def aimem_ingest(base: str, pending: list[dict], ingest_deadline: Deadline) -> None:
    """Post the hook items in batches of 256 until every one is accepted (v3 logic)."""
    for _attempt in range(60):
        nxt = []
        for i in range(0, len(pending), 256):
            chunk = pending[i:i + 256]
            status, _, body = http_json(f"{base}/hook/batch", chunk,
                                        headers={"Authorization": f"Bearer {AIMEM_TOKEN}"},
                                        timeout=ingest_deadline.left())
            if status != 200:
                raise RuntimeError(f"hook batch HTTP {status}: {body[:300]}")
            ack = json.loads(body)
            accepted = set(ack.get("accepted_indices") or range(ack.get("accepted", 0)))
            nxt += [item for j, item in enumerate(chunk) if j not in accepted]
        if not nxt:
            break
        ingest_deadline.left()
        time.sleep(0.5)
        pending = nxt
    else:
        raise RuntimeError(f"{len(pending)} hook items never accepted")


def aimem_ranking(res: dict, key_of: dict) -> tuple[list, int]:
    """Hits in order, mapped through the session uuid (pages first, then raw hits), deduplicated (v3 logic)."""
    ranking, unattributed = [], 0
    for hit in res.get("hits", []):
        path = hit.get("path", "")
        try:
            pos = key_of.get(uuid.UUID(path.removeprefix("sessions/").removesuffix(".md")))
        except ValueError:
            pos = None
        if pos is None:
            unattributed += 1
        elif pos not in ranking:
            ranking.append(pos)
    for hit in res.get("raw_hits", []):
        pos = key_of.get(uuid.UUID(hit["session_id"])) if hit.get("session_id") else None
        if pos is not None and pos not in ranking:
            ranking.append(pos)
    return ranking, unattributed


def aimem_health(cfg: dict, data_dir: Path) -> dict:
    health = {}
    db = data_dir / "db/memory.sqlite"
    if cfg.get("check_vectors") and db.exists():
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        health["embed_failures"] = con.execute("SELECT COUNT(*) FROM page_embed_failures").fetchone()[0]
        health["pages_without_vector"] = con.execute(
            "SELECT COUNT(*) FROM pages p LEFT JOIN page_embeddings e ON e.page_id = p.id "
            "WHERE p.is_latest = 1 AND e.page_id IS NULL AND TRIM(p.body) != ''").fetchone()[0]
        con.close()
    return health


def aimem_check(cfg: dict, health: dict, server_log: str) -> None:
    degraded = AIMEM_DEGRADED.findall(server_log)
    if cfg.get("check_vectors") and (degraded or health.get("embed_failures") or health.get("pages_without_vector")):
        raise EnvError(f"degraded retrieval: {len(degraded)} embedding warnings, {health}")


def run_aimem(q: dict, cfg: dict) -> dict:
    sess = sessions_of(q)
    project = "lme-" + hashlib.sha256(q["question_id"].encode()).hexdigest()[:12]
    uuid_to_pos = {uuid.uuid5(uuid.NAMESPACE_OID, s["hid"]): s["pos"] for s in sess}
    home = tempfile.mkdtemp(prefix="lme-aimem-")
    stderr_path = Path(home) / "stderr.log"
    proc = None
    try:
        proc, base, data_dir, stderr_path = aimem_start(cfg, home, project)
        ingest_deadline = Deadline(INGEST_BUDGET_S, "ingest")
        t0 = time.perf_counter()
        aimem_ingest(base, aimem_items(q, sess, project), ingest_deadline)
        ingest_s = time.perf_counter() - t0
        t1 = time.perf_counter()
        res = aimem_query(base, project, q["question"], cfg.get("limit", AIMEM_LIMIT),
                          Deadline(QUERY_BUDGET_S, "query"))
        latency_ms = (time.perf_counter() - t1) * 1000
        ranking, unattributed = aimem_ranking(res, uuid_to_pos)
        health = aimem_health(cfg, data_dir)
        result = {"ranking": ranking, "latency_ms": latency_ms, "ingest_s": ingest_s,
                  "unattributed": unattributed, **health}
        server_log = stderr_path.read_text(errors="ignore")
        if cfg["env"].get("AI_MEMORY_RERANKER"):
            result |= {k: server_log.count(msg) for k, msg in RERANK_FALLBACK.items()}  # A12: reported, not errors
        aimem_check(cfg, health, server_log)
        return result
    except (InfraError, DeadlineError, EnvError):
        raise
    except (FileNotFoundError, PermissionError) as e:  # A15 review: a missing binary or model is an env fault
        raise EnvError(f"cannot start ai-memory: {type(e).__name__}: {e}") from e
    except Exception as e:
        tail = stderr_path.read_text(errors="ignore")[-400:] if stderr_path.exists() else ""
        raise RuntimeError(f"{type(e).__name__}: {e} | server stderr tail: {tail!r}") from e
    finally:
        stop(proc)
        shutil.rmtree(home, ignore_errors=True)


# ---------------------------------------------------------------- agentmemory (its own benchmark's API path)

_HELD: set = set()
_HELD_LOCK = threading.Lock()


def claim_slot(pool: int | None = None, wait: float = 1.0) -> tuple:
    """A15.1 review: claim a free agentmemory slot from the host-wide pool, under a cross-process lock.

    Several harness processes (a CPU-only arm beside a GPU arm) share one pool of slots. The lock file
    AM_ROOT/.slot-<n>.lock is held for the whole question, both teardowns included, because a slot's teardown
    kills the holders of that slot's ports. Returns (slot, open lock file); release with release_slot().
    """
    pool = pool or AM_SLOT_POOL
    AM_ROOT.mkdir(parents=True, exist_ok=True)
    while True:
        for slot in range(pool):
            with _HELD_LOCK:
                if slot in _HELD:
                    continue
                _HELD.add(slot)
            fh = open(AM_ROOT / f".slot-{slot}.lock", "w")
            try:
                fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return slot, fh
            except BlockingIOError:
                fh.close()
                with _HELD_LOCK:
                    _HELD.discard(slot)
        time.sleep(wait)


def release_slot(slot: int, fh) -> None:
    fcntl.flock(fh, fcntl.LOCK_UN)
    fh.close()
    with _HELD_LOCK:
        _HELD.discard(slot)


def _ours(command: str) -> bool:
    """A process this harness may kill: the iii engine or agentmemory's worker, never anything else."""
    first = command.split()[0] if command.split() else ""
    return "agentmemory" in command or str(III_BIN) in command or os.path.basename(first) == III_BIN.name


def _command(pid: int) -> str:
    return subprocess.run(["ps", "-o", "command=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()


def _port_free(port: int) -> bool:
    with socket.socket() as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def am_ports(slot: int) -> dict:
    """agentmemory's multi-instance scheme: REST anchor, streams +1, viewer +2, engine +46023."""
    rest = 3611 + 100 * slot
    return {"rest": rest, "stream": rest + 1, "engine": rest + 46023}


def _children(pid: int) -> list[int]:
    out = subprocess.run(["pgrep", "-P", str(pid)], capture_output=True, text=True).stdout.split()
    kids = [int(x) for x in out]
    return kids + [g for k in kids for g in _children(k)]


def am_teardown(proc: subprocess.Popen | None, ports: dict, timeout: float = 15.0):
    """Kill this slot's engine and every descendant it spawned, then wait until its ports are free."""
    if proc is not None:
        for pid in _children(proc.pid):
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        stop(proc)
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        holders = set()
        for port in ports.values():
            holders |= {int(x) for x in subprocess.run(["lsof", "-t", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN"],
                                                        capture_output=True, text=True).stdout.split()}
        if not holders:
            return
        for pid in holders:
            command = _command(pid)
            if command and not _ours(command):  # A15 review: never kill another program's listener
                raise InfraError(f"agentmemory slot port held by another program (pid {pid}: {command[:80]})")
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        time.sleep(0.3)
    raise InfraError(f"agentmemory slot ports still busy: {ports}")


def am_hook_session(base: str, q: dict, s: dict, deadline: Deadline) -> None:
    """A15.2 D2h: one haystack session through agentmemory 0.9.29's shipped Claude Code hooks (plugin/hooks).

    SessionStart posts session/start; UserPromptSubmit posts observe (hookType prompt_submit, data.prompt) for each
    user turn, dated as A3 requires; Stop posts session/end after each assistant turn; SessionEnd posts
    session/end (its transcript replay needs a transcript file, which a replay does not have). The hooks send
    the current time as the timestamp and never the assistant's text, exactly as shipped.
    """
    project = "lme-" + hashlib.sha256(q["question_id"].encode()).hexdigest()[:12]
    cwd = f"/lme/{project}"

    def post(path: str, body: dict) -> None:
        status, _, text = http_json(f"{base}/agentmemory/{path}", body, timeout=deadline.left())
        if not 200 <= status < 300:
            raise RuntimeError(f"{path} HTTP {status}: {text[:200]}")

    post("session/start", {"sessionId": s["hid"], "project": project, "cwd": cwd})
    for turn in s["turns"]:
        if turn["role"] == "user":
            post("observe", {"hookType": "prompt_submit", "sessionId": s["hid"], "project": project, "cwd": cwd,
                             "timestamp": datetime.now().astimezone().isoformat(),
                             "data": {"prompt": f"[session date: {s['date']}] {turn['content']}"}})
        elif turn["role"] == "assistant":
            post("session/end", {"sessionId": s["hid"]})
    post("session/end", {"sessionId": s["hid"]})


def run_agentmemory(q: dict, cfg: dict) -> dict:
    """Each question runs in an isolated slot (own engine, REST, stream and viewer ports), locked host-wide."""
    slot, fh = claim_slot()
    try:
        return _run_agentmemory_slot(q, cfg, slot)
    except (FileNotFoundError, PermissionError) as e:  # A15 review: missing iii, node, lsof or pgrep
        raise EnvError(f"cannot run agentmemory: {type(e).__name__}: {e}") from e
    finally:
        release_slot(slot, fh)


def am_start(cfg: dict, slot: int, root: str) -> tuple:
    """Start agentmemory's iii engine and worker on one slot's ports and check the store is empty (v3 logic)."""
    ports = am_ports(slot)
    am_teardown(None, ports)  # a clean slot before start
    busy = [p for p in ports.values() if not _port_free(p)]
    if busy:  # e.g. an outgoing connection's ephemeral port: retried on a fresh slot
        raise InfraError(f"agentmemory slot ports busy without a listener: {busy}")
    if cfg.get("probe_model"):
        probe_embeddings(cfg["probe_model"])
    slot_env = {"III_REST_PORT": str(ports["rest"]), "III_STREAM_PORT": str(ports["stream"]),
                "III_ENGINE_URL": f"ws://127.0.0.1:{ports['engine']}", "III_URL": f"ws://127.0.0.1:{ports['engine']}"}
    (Path(root) / "data").mkdir()
    (Path(root) / ".agentmemory").mkdir()
    (Path(root) / ".agentmemory/.env").write_text("".join(f"{k}={v}\n" for k, v in (cfg["env"] | slot_env).items()))
    (Path(root) / "iii-config.yaml").write_text(f"""workers:
  - name: iii-worker-manager
    config: {{host: 127.0.0.1, port: {ports['engine']}}}
  - name: iii-http
    config: {{port: {ports['rest']}, host: 127.0.0.1, default_timeout: 180000}}
  - name: iii-state
    config: {{adapter: {{name: kv, config: {{store_method: file_based, file_path: {root}/data/state_store.db}}}}}}
  - name: iii-queue
    config: {{adapter: {{name: builtin}}}}
  - name: iii-pubsub
    config: {{adapter: {{name: local}}}}
  - name: iii-cron
    config: {{adapter: {{name: kv}}}}
  - name: iii-stream
    config: {{port: {ports['stream']}, host: 127.0.0.1, adapter: {{name: kv, config: {{store_method: file_based, file_path: {root}/data/stream_store}}}}}}
  - name: iii-exec
    config: {{exec: ["{cfg['node']} {AM_INDEX}"]}}
""")
    env = clean_env(root) | {"PATH": f"{III_BIN.parent}:/usr/bin:/bin"} | slot_env
    proc = subprocess.Popen([str(III_BIN), "--no-update-check", "--config", f"{root}/iii-config.yaml"],
                            cwd=root, env=env, stdout=open(Path(root) / "iii.log", "w"), stderr=subprocess.STDOUT,
                            start_new_session=True)
    base = f"http://127.0.0.1:{ports['rest']}"
    try:
        wait_http(f"{base}/agentmemory/livez", proc, ok=lambda s, b: s == 200 and '"ok"' in b)
        time.sleep(1.5)  # the worker re-registers once right after livez turns ok
        with setup_step("agentmemory empty-store check"):
            status, _, body = http_json(f"{base}/agentmemory/smart-search", {"query": "anything", "limit": 50})
        if not 200 <= status < 300 or json.loads(body).get("results"):
            raise RuntimeError(f"store not empty before ingest ({status})")
    except BaseException:
        am_teardown(proc, ports)
        raise
    return proc, base, ports


def am_remember(base: str, s: dict, deadline: Deadline) -> dict:
    """One dated session through the benchmark's REST remember (v3 logic); returns the stored memory."""
    content = dated(s, "\n\n".join(f"[{t['role']}] {t['content']}" for t in s["turns"]))
    status, _, body = http_json(f"{base}/agentmemory/remember",
                                {"content": content, "type": "eval-session", "concepts": [s["hid"]]},
                                timeout=deadline.left())
    if not 200 <= status < 300:
        raise RuntimeError(f"remember HTTP {status}: {body[:200]}")
    mem = json.loads(body).get("memory") or {}
    if not mem.get("id"):
        raise RuntimeError(f"remember returned no id: {body[:200]}")
    return mem


def _run_agentmemory_slot(q: dict, cfg: dict, slot: int) -> dict:
    sess = sessions_of(q)
    ports = am_ports(slot)
    root = tempfile.mkdtemp(prefix=f"lme-am{slot}-", dir="/tmp")
    proc = None
    try:
        proc, base, ports = am_start(cfg, slot, root)
        id_to_pos, superseding = {}, 0
        ingest_deadline = Deadline(INGEST_BUDGET_S, "ingest")
        t0 = time.perf_counter()
        if cfg.get("hooks"):  # A15.2 D2h: the shipped Claude Code hooks, not the benchmark's REST remember
            for s in sess:
                am_hook_session(base, q, s, ingest_deadline)
            sess = []  # results map through each observation's sessionId below
        for s in sess:
            mem = am_remember(base, s, ingest_deadline)
            id_to_pos[mem["id"]] = s["pos"]
            superseding += bool(mem.get("supersedes"))
        ingest_s = time.perf_counter() - t0
        errors_before = upstream_errors(cfg.get("probe_model"))
        t1 = time.perf_counter()
        status, _, body = http_json(f"{base}/agentmemory/smart-search", {"query": q["question"], "limit": 50},
                                    timeout=Deadline(QUERY_BUDGET_S, "query").left())
        latency_ms = (time.perf_counter() - t1) * 1000
        if not 200 <= status < 300:
            raise RuntimeError(f"smart-search HTTP {status}: {body[:200]}")
        ranking, unattributed = [], 0
        if cfg.get("hooks"):
            id_to_pos = {}
            hid_to_pos = {s["hid"]: s["pos"] for s in sessions_of(q)}
        for row in json.loads(body).get("results", []):
            if cfg.get("hooks"):
                pos = hid_to_pos.get(row.get("sessionId") or "")
            else:
                pos = id_to_pos.get(row.get("obsId") or row.get("id") or "")
            if pos is None:
                unattributed += 1
            elif pos not in ranking:
                ranking.append(pos)
        log = (Path(root) / "iii.log").read_text(errors="ignore")
        failures = log.count("embed failed")
        if cfg.get("probe_model"):
            probe_embeddings(cfg["probe_model"])  # agentmemory falls back to BM25 silently on query-embed failure
        if failures:
            raise EnvError(f"{failures} embedding failures during ingest")
        if errors_before is not None:  # A15 review: agentmemory silently falls back to BM25 on a failed query embed
            after = (proxy_stats() or {}).get("counters", {}).get("upstream_errors")
            if after is None or after > errors_before:
                raise EnvError(f"embedding upstream errors during the query window ({errors_before} -> {after})")
        return {"ranking": ranking, "latency_ms": latency_ms, "ingest_s": ingest_s, "unattributed": unattributed,
                "embed_failures": failures, "superseding_saves": superseding, "slot": slot}
    finally:
        am_teardown(proc, ports)
        shutil.rmtree(root, ignore_errors=True)


# ---------------------------------------------------------------- A16: shared helpers

def http_method(method: str, url: str, body=None, timeout: float = QUERY_BUDGET_S) -> tuple[int, str]:
    """PUT, DELETE and GET/POST with http_json's failure classes (5xx and refused connections are infra)."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=max(timeout, 0.1)) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        if e.code >= 500:
            raise InfraError(f"HTTP {e.code} from {url}: {e.read().decode(errors='replace')[:200]}") from e
        return e.code, e.read().decode(errors="replace")
    except TimeoutError as e:
        raise DeadlineError(f"timeout calling {url}") from e
    except (ConnectionError, urllib.error.URLError) as e:
        if isinstance(getattr(e, "reason", None), TimeoutError):
            raise DeadlineError(f"timeout calling {url}") from e
        raise InfraError(str(e)) from e


def iso(lme_date: str) -> str:
    """A LongMemEval date ("2023/05/20 (Sat) 02:21") as ISO 8601 ("2023-05-20T02:21:00")."""
    return parse_date(lme_date).isoformat()


def transcript(s: dict) -> str:
    """The dated session text every system receives when it takes whole sessions (A3), as agentmemory's remember."""
    return dated(s, "\n\n".join(f"[{t['role']}] {t['content']}" for t in s["turns"]))


class StdioRpc:
    """A line-delimited JSON-RPC 2.0 client for an MCP server on stdio (the transport MemPalace ships)."""

    def __init__(self, cmd: list[str], env: dict, cwd: str, stderr_path: Path):
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=open(stderr_path, "w"),
                                     env=env, cwd=cwd, text=True, bufsize=1, start_new_session=True)
        self.lines: queue.Queue = queue.Queue()
        self.next_id = 0
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self) -> None:
        stdout = self.proc.stdout
        if stdout is not None:
            for line in stdout:
                self.lines.put(line)
        self.lines.put(None)

    def _send(self, msg: dict) -> None:
        try:
            if self.proc.stdin is None:
                raise BrokenPipeError("no stdin")
            self.proc.stdin.write(json.dumps(msg) + "\n")
            self.proc.stdin.flush()
        except (BrokenPipeError, OSError) as e:
            raise InfraError(f"MCP server stdin closed: {e}") from e

    def notify(self, method: str, params: dict | None = None) -> None:
        self._send({"jsonrpc": "2.0", "method": method, **({"params": params} if params is not None else {})})

    def call(self, method: str, params: dict, deadline: Deadline) -> dict:
        self.next_id += 1
        want = self.next_id
        self._send({"jsonrpc": "2.0", "id": want, "method": method, "params": params})
        while True:
            try:
                line = self.lines.get(timeout=deadline.left())
            except queue.Empty as e:
                raise DeadlineError(f"{deadline.what} budget exhausted waiting for {method}") from e
            if line is None:
                raise InfraError(f"MCP server exited ({self.proc.poll()}) before answering {method}")
            try:
                msg = json.loads(line)
            except ValueError:
                continue  # stray output on stdout
            if isinstance(msg, dict) and msg.get("id") == want:
                return msg

    def close(self) -> None:
        try:
            if self.proc.stdin is not None:
                self.proc.stdin.close()
        except OSError:
            pass
        stop(self.proc)


# ---------------------------------------------------------------- A16 M2: MemPalace 3.10.0 in palace mode

def mp_env(home: Path) -> dict:
    return clean_env(str(home)) | {"PATH": f"{MP_VENV / 'bin'}:/usr/bin:/bin", "HF_HUB_OFFLINE": "1"}


def mp_init(home: Path) -> None:
    """A fresh palace: chromadb's pinned MiniLM ONNX in this HOME's cache, then the shipped `mempalace init`."""
    cache = home / ".cache/chroma/onnx_models"
    cache.mkdir(parents=True)
    (cache / "all-MiniLM-L6-v2").symlink_to(MP_ONNX)  # chromadb finds the files and never downloads (A16 pin)
    (home / "project").mkdir()
    proc = subprocess.run([str(MP_VENV / "bin/mempalace"), "init", str(home / "project"), "--yes", "--auto-mine",
                           "--no-llm"], env=mp_env(home), cwd=str(home), stdin=subprocess.DEVNULL,
                          capture_output=True, text=True, timeout=600)
    if proc.returncode != 0:
        raise EnvError(f"mempalace init exited {proc.returncode}: {(proc.stderr or proc.stdout)[-300:]!r}")


def mp_hook(home: Path, hook: str, payload: dict, cwd: str, deadline: Deadline) -> None:
    """One hook exactly as the shipped Claude Code plugin runs it (`mempalace hook run --harness claude-code`)."""
    try:
        proc = subprocess.run([str(MP_VENV / "bin/mempalace"), "hook", "run", "--hook", hook, "--harness", "claude-code"],
                              input=json.dumps(payload), env=mp_env(home), cwd=cwd, capture_output=True, text=True,
                              timeout=min(deadline.left(), MP_HOOK_TIMEOUT_S))
    except subprocess.TimeoutExpired as e:
        raise DeadlineError(f"mempalace {hook} hook timed out") from e
    if proc.returncode != 0:
        raise RuntimeError(f"mempalace {hook} hook exited {proc.returncode}: {proc.stderr[-300:]!r}")


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def mp_mine_pids(home: Path) -> list[int]:
    """Live miners the hooks spawned in the background (their per-target pid files, hooks_cli._spawn_mine)."""
    live = []
    pid_dir = home / ".mempalace/hook_state/mine_pids"
    for f in sorted(pid_dir.glob("*.pid")) if pid_dir.is_dir() else []:
        try:
            pid = int(f.read_text().split()[0])
        except (OSError, ValueError, IndexError):
            continue
        if _pid_alive(pid):
            live.append(pid)
    return live


def mp_wait_mines(home: Path, deadline: Deadline) -> None:
    """Wait for the background mines, as a user's next turn would come after them; skipped fires lose content."""
    while mp_mine_pids(home):
        deadline.left()
        time.sleep(0.2)


def mp_session(home: Path, project: str, s: dict, deadline: Deadline) -> None:
    """One dated session through MemPalace's shipped Claude Code hook path.

    The transcript grows turn by turn as Claude Code writes it (JSONL, `~/.claude/projects/<project>/<id>.jsonl`,
    each user turn dated as A3 requires); the Stop hook fires after every assistant turn and SessionEnd once at
    the end (the plugin's hooks.json has no SessionStart, and a replay never compacts). The hooks mine through the
    shipped convo miner in the background; each fire waits for those mines, so no fire is skipped as a duplicate.
    """
    cwd = f"/lme/{project}"
    tdir = home / ".claude/projects" / f"-lme-{project}"
    tdir.mkdir(parents=True, exist_ok=True)
    path = tdir / f"{s['hid']}.jsonl"
    start = parse_date(s["date"])
    common = {"session_id": s["hid"], "transcript_path": str(path), "cwd": cwd}
    with path.open("a") as fh:
        for i, turn in enumerate(s["turns"]):
            role = "user" if turn["role"] == "user" else "assistant"
            text = f"[session date: {s['date']}] {turn['content']}" if role == "user" else turn["content"]
            content = text if role == "user" else [{"type": "text", "text": text}]
            fh.write(json.dumps({"type": role, "sessionId": s["hid"], "cwd": cwd,
                                 "timestamp": (start + timedelta(seconds=i)).isoformat() + "Z",
                                 "message": {"role": role, "content": content}}) + "\n")
            fh.flush()
            if role == "assistant":
                mp_hook(home, "stop", common | {"hook_event_name": "Stop", "stop_hook_active": False}, str(home), deadline)
                mp_wait_mines(home, deadline)
    mp_hook(home, "session-end", common | {"hook_event_name": "SessionEnd", "reason": "other"}, str(home), deadline)
    mp_wait_mines(home, deadline)


def mp_check_logs(home: Path) -> None:
    """A traceback in the hook or mine log means the palace is incomplete: an env fault, never a system result."""
    log = home / ".mempalace/hook_state/hook.log"
    text = log.read_text(errors="ignore") if log.exists() else ""
    if "Traceback (most recent call last)" in text:
        raise EnvError(f"mempalace hook or mine failed: {text[text.index('Traceback'):][:400]!r}")


def mp_rpc(home: Path) -> StdioRpc:
    rpc = StdioRpc([str(MP_VENV / "bin/mempalace-mcp")], mp_env(home), str(home), home / "mcp.log")
    try:
        with setup_step("mempalace MCP initialize"):
            msg = rpc.call("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                          "clientInfo": {"name": "lme-harness", "version": "4"}},
                           Deadline(QUERY_BUDGET_S, "mcp init"))
    except BaseException:
        rpc.close()
        raise
    if "error" in msg:
        rpc.close()
        raise EnvError(f"mempalace MCP initialize failed: {json.dumps(msg)[:300]}")
    rpc.notify("notifications/initialized")
    return rpc


def mp_search(rpc: StdioRpc, question: str, deadline: Deadline) -> dict:
    """MemPalace's MCP search at the registered depth (A10: 50), every other argument at its default."""
    msg = rpc.call("tools/call", {"name": "mempalace_search", "arguments": {"query": question, "limit": AIMEM_LIMIT}},
                   deadline)
    result = msg.get("result") or {}
    if "error" in msg or result.get("isError"):
        raise RuntimeError(f"mempalace_search error: {json.dumps(msg)[:300]}")
    payload = json.loads(result["content"][0]["text"])
    if payload.get("error"):
        raise EnvError(f"mempalace_search: {payload['error']} {payload.get('details', '')}")
    if payload.get("vector_disabled"):  # the palace fell back to lexical search: degraded retrieval (A4)
        raise EnvError(f"mempalace vector search disabled: {payload.get('vector_disabled_reason')}")
    return payload


def mp_ranking(payload: dict, key_of: dict) -> tuple[list, int]:
    """Sessions in order of their first hit; a hit maps through its transcript file name (<session id>.jsonl)."""
    ranking, unattributed = [], 0
    for hit in payload.get("results", []):
        source = hit.get("source_path") or hit.get("source_file") or ""
        key = key_of.get(Path(source).name.removesuffix(".jsonl"))
        if key is None:
            unattributed += 1
        elif key not in ranking:
            ranking.append(key)
    return ranking, unattributed


def mp_kill_mines(home: Path) -> None:
    for pid in mp_mine_pids(home):
        try:
            os.killpg(pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass


def run_mempalace(q: dict, cfg: dict) -> dict:
    sess = sessions_of(q)
    project = "lme-" + hashlib.sha256(q["question_id"].encode()).hexdigest()[:12]
    home = Path(tempfile.mkdtemp(prefix="lme-mp-", dir="/tmp"))
    rpc = None
    try:
        mp_init(home)
        ingest_deadline = Deadline(INGEST_BUDGET_S, "ingest")
        t0 = time.perf_counter()
        for s in sess:
            mp_session(home, project, s, ingest_deadline)
        ingest_s = time.perf_counter() - t0
        mp_check_logs(home)
        rpc = mp_rpc(home)
        t1 = time.perf_counter()
        payload = mp_search(rpc, q["question"], Deadline(QUERY_BUDGET_S, "query"))
        latency_ms = (time.perf_counter() - t1) * 1000
        ranking, unattributed = mp_ranking(payload, {s["hid"]: s["pos"] for s in sess})
        return {"ranking": ranking, "latency_ms": latency_ms, "ingest_s": ingest_s, "unattributed": unattributed,
                "hits": len(payload.get("results", []))}
    except (FileNotFoundError, PermissionError) as e:
        raise EnvError(f"cannot run mempalace: {type(e).__name__}: {e}") from e
    finally:
        if rpc is not None:
            rpc.close()
        mp_kill_mines(home)
        shutil.rmtree(home, ignore_errors=True)


# ---------------------------------------------------------------- A16 K1: Hindsight 0.10.1

def hs_bank(name: str) -> str:
    return f"{HS_URL}/v1/default/banks/{name}"


def hs_ok(status: int, body: str, what: str) -> dict:
    if not 200 <= status < 300:
        raise RuntimeError(f"hindsight {what} HTTP {status}: {body[:300]}")
    return json.loads(body) if body.strip() else {}


def hs_fresh_bank(bank: str) -> None:
    with setup_step("hindsight bank reset"):
        status, body = http_method("DELETE", hs_bank(bank))  # a retry after an infra error starts clean
        if status not in (200, 202, 204, 404):
            raise RuntimeError(f"hindsight delete bank HTTP {status}: {body[:200]}")
        hs_ok(*http_method("PUT", hs_bank(bank), {}), "create bank")


def hs_retain(bank: str, s: dict, document_id: str, deadline: Deadline) -> None:
    """retain(transcript, timestamp, document_id=session_id), synchronously (A16). The document id is always the
    Protocol step 2 hashed session id (s["hid"]), never the dataset's id, which can contain "answer"."""
    if "answer" in document_id:
        raise ValueError("a Hindsight document id must be the hashed session id (Protocol step 2)")
    item = {"content": transcript(s), "timestamp": iso(s["date"]), "document_id": document_id}
    hs_ok(*http_method("POST", f"{hs_bank(bank)}/memories", {"items": [item], "async": False},
                       timeout=deadline.left()), "retain")


def hs_count(bank: str, status: str, deadline: Deadline) -> int:
    body = hs_ok(*http_method("GET", f"{hs_bank(bank)}/operations?status={status}&limit=1",
                              timeout=min(deadline.left(), QUERY_BUDGET_S)), "operations")
    return int(body.get("total", 0))


def hs_settle(bank: str, deadline: Deadline) -> int:
    """Wait until no retain or consolidation operation is pending or running; returns the failed operations."""
    while hs_count(bank, "pending", deadline) + hs_count(bank, "processing", deadline):
        deadline.left()
        time.sleep(1.0)
    return hs_count(bank, "failed", deadline)


def hs_recall(bank: str, q: dict, deadline: Deadline) -> list[dict]:
    """recall(query_timestamp=question_date); every other parameter at Hindsight's default (A16)."""
    body = hs_ok(*http_method("POST", f"{hs_bank(bank)}/memories/recall",
                              {"query": q["question"], "query_timestamp": iso(q["question_date"])},
                              timeout=deadline.left()), "recall")
    return body.get("results", [])


def hs_ranking(results: list[dict], key_of: dict) -> tuple[list, int]:
    """Sessions in order of their first-seen document_id; facts without one (observations) are unattributed."""
    ranking, unattributed = [], 0
    for r in results:
        key = key_of.get(r.get("document_id") or "")
        if key is None:
            unattributed += 1
        elif key not in ranking:
            ranking.append(key)
    return ranking, unattributed


def hs_llm_healthy() -> bool:
    try:
        status, _ = http_method("GET", f"{LLM_URL}/health", timeout=10)
    except (InfraError, DeadlineError):
        return False
    return status == 200


def run_hindsight(q: dict, cfg: dict) -> dict:
    sess = sessions_of(q)
    bank = "lme-" + hashlib.sha256(q["question_id"].encode()).hexdigest()[:12]
    key_of = {s["hid"]: s["pos"] for s in sess}  # one hashed id per occurrence (Protocol step 2, A7)
    try:
        hs_fresh_bank(bank)
        ingest_deadline = Deadline(cfg.get("ingest_budget_s", INGEST_BUDGET_S), "ingest")
        t0 = time.perf_counter()
        try:
            for s in sess:
                hs_retain(bank, s, s["hid"], ingest_deadline)
            failed = hs_settle(bank, ingest_deadline)
        except DeadlineError as e:
            try:  # abandoned extractions keep LLM slots busy: let them finish (bounded) before the bank goes
                hs_settle(bank, Deadline(TEARDOWN_BUDGET_S, "teardown"))
            except (DeadlineError, InfraError, RuntimeError, ValueError):
                pass
            raise DeadlineError(f"ingest: {e}") from e  # the phase: A16.1's pooled estimate counts ingest deadlines
        ingest_s = time.perf_counter() - t0
        if failed and not hs_llm_healthy():
            raise EnvError(f"{failed} failed Hindsight operations and the LLM server is not healthy")
        t1 = time.perf_counter()
        try:
            results = hs_recall(bank, q, Deadline(QUERY_BUDGET_S, "query"))
        except DeadlineError as e:
            raise DeadlineError(f"query: {e}") from e
        latency_ms = (time.perf_counter() - t1) * 1000
        ranking, unattributed = hs_ranking(results, key_of)
        return {"ranking": ranking, "latency_ms": latency_ms, "ingest_s": ingest_s, "unattributed": unattributed,
                "facts": len(results), "failed_operations": failed, "sessions": len(sess)}
    finally:
        try:
            http_method("DELETE", hs_bank(bank), timeout=60)
        except (InfraError, DeadlineError):
            pass


# ---------------------------------------------------------------- A16 pooled-store stress run (descriptive)

def pool_sessions(questions: list[dict]) -> list[dict]:
    """Every eligible session once, keyed by session id and dated by its first occurrence in manifest order.

    A shared session carries different dates in different haystacks; one store holds one copy, so the first
    date stands (recorded in the rows' notes).
    """
    pool, seen = [], set()
    for q in questions:
        for sid, sess, date in zip(q["haystack_session_ids"], q["haystack_sessions"], q["haystack_dates"]):
            if sid in seen:
                continue
            seen.add(sid)
            pool.append({"pos": len(pool), "hid": hashed_id("pooled", sid, 0), "date": date, "turns": sess, "sid": sid})
    return pool


def score_pooled(q: dict, sids: list[str]) -> tuple[dict, list[int], int]:
    """Official metrics when the store holds every eligible session: a session from another question's haystack
    takes its rank as a non-gold corpus entry appended after the haystack (the official evaluate_retrieval)."""
    free: dict[str, list[int]] = {}
    for pos, sid in enumerate(q["haystack_session_ids"]):
        free.setdefault(sid, []).append(pos)
    n = len(q["haystack_session_ids"])
    ranking, positions, foreign = [], [], []
    for sid in sids[:MAX_RANK]:
        if free.get(sid):
            pos = free[sid].pop(0)
            ranking.append(pos)
            positions.append(pos)
        elif sid not in free:
            foreign.append(sid)
            ranking.append(n + len(foreign) - 1)
    official_ids = []
    for sid, sess, ts in zip(q["haystack_session_ids"], q["haystack_sessions"], q["haystack_dates"]):
        _, ids, _ = process_item_flat_index(sess, "session", sid, ts)
        official_ids += ids
    official_gold = list({c for c in official_ids if "answer" in c})
    extra = [f"pooled-foreign:{sid}" for sid in foreign]
    out = {"official": {}, "full": {}}
    for k in KS:
        for track, ids, gold in (("official", official_ids + extra, official_gold),
                                 ("full", list(q["haystack_session_ids"]) + extra, list(q["answer_session_ids"]))):
            ra, rl, nd = evaluate_retrieval(ranking, gold, ids, k=k)
            out[track].update({f"recall_any@{k}": ra, f"recall_all@{k}": rl, f"ndcg_any@{k}": nd})
    return out, positions, sum(1 for r in ranking[:5] if r >= n)


class AimemPool:
    def __init__(self, cfg: dict):
        self.cfg, self.project, self.proc = cfg, "lme-pooled", None

    def __enter__(self):
        self.home = tempfile.mkdtemp(prefix="lme-aimem-pooled-")
        try:
            self.proc, self.base, self.data_dir, self.stderr_path = aimem_start(self.cfg, self.home, self.project)
        except BaseException:
            shutil.rmtree(self.home, ignore_errors=True)
            raise
        return self

    def __exit__(self, *exc):
        stop(self.proc)
        shutil.rmtree(self.home, ignore_errors=True)

    def ingest(self, pool: list[dict], deadline: Deadline) -> None:
        aimem_ingest(self.base, aimem_items({"question_id": "pooled"}, pool, self.project), deadline)
        self.key_of = {uuid.uuid5(uuid.NAMESPACE_OID, s["hid"]): s["sid"] for s in pool}
        aimem_check(self.cfg, aimem_health(self.cfg, self.data_dir), self.stderr_path.read_text(errors="ignore"))

    def query(self, q: dict) -> tuple[list, dict]:
        before = len(self.stderr_path.read_text(errors="ignore"))
        res = aimem_query(self.base, self.project, q["question"], self.cfg.get("limit", AIMEM_LIMIT),
                          Deadline(QUERY_BUDGET_S, "query"))
        ranking, unattributed = aimem_ranking(res, self.key_of)
        delta = self.stderr_path.read_text(errors="ignore")[before:]
        aimem_check(self.cfg, {}, delta)
        extra = {"unattributed": unattributed}
        if self.cfg["env"].get("AI_MEMORY_RERANKER"):
            extra |= {k: delta.count(msg) for k, msg in RERANK_FALLBACK.items()}
        return ranking, extra


class AgentmemoryPool:
    def __init__(self, cfg: dict):
        self.cfg, self.proc, self.ports = cfg, None, None

    def __enter__(self):
        self.slot, self.fh = claim_slot()
        self.root = tempfile.mkdtemp(prefix=f"lme-am{self.slot}-pooled-", dir="/tmp")
        try:
            self.proc, self.base, self.ports = am_start(self.cfg, self.slot, self.root)
        except BaseException:
            release_slot(self.slot, self.fh)
            shutil.rmtree(self.root, ignore_errors=True)
            raise
        return self

    def __exit__(self, *exc):
        try:
            am_teardown(self.proc, self.ports or am_ports(self.slot))
        finally:
            release_slot(self.slot, self.fh)
            shutil.rmtree(self.root, ignore_errors=True)

    def ingest(self, pool: list[dict], deadline: Deadline) -> None:
        self.key_of = {}
        for s in pool:
            if self.cfg.get("hooks"):
                am_hook_session(self.base, {"question_id": "pooled"}, s, deadline)
                self.key_of[s["hid"]] = s["sid"]
            else:
                self.key_of[am_remember(self.base, s, deadline)["id"]] = s["sid"]
        failures = (Path(self.root) / "iii.log").read_text(errors="ignore").count("embed failed")
        if failures:
            raise EnvError(f"{failures} embedding failures during the pooled ingest")

    def query(self, q: dict) -> tuple[list, dict]:
        errors_before = upstream_errors(self.cfg.get("probe_model"))
        status, _, body = http_json(f"{self.base}/agentmemory/smart-search", {"query": q["question"], "limit": 50},
                                    timeout=Deadline(QUERY_BUDGET_S, "query").left())
        if not 200 <= status < 300:
            raise RuntimeError(f"smart-search HTTP {status}: {body[:200]}")
        ranking, unattributed = [], 0
        for row in json.loads(body).get("results", []):
            key = self.key_of.get((row.get("sessionId") if self.cfg.get("hooks") else row.get("obsId") or row.get("id")) or "")
            if key is None:
                unattributed += 1
            elif key not in ranking:
                ranking.append(key)
        if self.cfg.get("probe_model"):
            probe_embeddings(self.cfg["probe_model"])  # always, as the per-question path does
        if errors_before is not None:
            after = ((proxy_stats() or {}).get("counters") or {}).get("upstream_errors")
            if after is None or after > errors_before:
                raise EnvError(f"embedding upstream errors during the query window ({errors_before} -> {after})")
        return ranking, {"unattributed": unattributed}


class MempalacePool:
    def __init__(self, cfg: dict):
        self.cfg, self.rpc = cfg, None

    def __enter__(self):
        self.home = Path(tempfile.mkdtemp(prefix="lme-mp-pooled-", dir="/tmp"))
        try:
            mp_init(self.home)
        except BaseException:
            shutil.rmtree(self.home, ignore_errors=True)
            raise
        return self

    def __exit__(self, *exc):
        if self.rpc is not None:
            self.rpc.close()
        mp_kill_mines(self.home)
        shutil.rmtree(self.home, ignore_errors=True)

    def ingest(self, pool: list[dict], deadline: Deadline) -> None:
        for s in pool:
            mp_session(self.home, "lme-pooled", s, deadline)
        mp_check_logs(self.home)
        self.key_of = {s["hid"]: s["sid"] for s in pool}
        self.rpc = mp_rpc(self.home)

    def query(self, q: dict) -> tuple[list, dict]:
        rpc = self.rpc
        if rpc is None:
            raise RuntimeError("the pooled palace was never ingested")
        payload = mp_search(rpc, q["question"], Deadline(QUERY_BUDGET_S, "query"))
        ranking, unattributed = mp_ranking(payload, self.key_of)
        return ranking, {"unattributed": unattributed}


class HindsightPool:
    def __init__(self, cfg: dict):
        self.cfg, self.bank = cfg, "lme-pooled"

    def __enter__(self):
        hs_fresh_bank(self.bank)
        return self

    def __exit__(self, *exc):
        try:
            http_method("DELETE", hs_bank(self.bank), timeout=600)
        except (InfraError, DeadlineError):
            pass

    def ingest(self, pool: list[dict], deadline: Deadline) -> None:
        for s in pool:
            hs_retain(self.bank, s, s["hid"], deadline)  # the pooled hashed id, never the dataset's id
        self.failed = hs_settle(self.bank, deadline)
        if self.failed and not hs_llm_healthy():
            raise EnvError(f"{self.failed} failed Hindsight operations and the LLM server is not healthy")
        self.key_of = {s["hid"]: s["sid"] for s in pool}

    def query(self, q: dict) -> tuple[list, dict]:
        ranking, unattributed = hs_ranking(hs_recall(self.bank, q, Deadline(QUERY_BUDGET_S, "query")), self.key_of)
        return ranking, {"unattributed": unattributed, "failed_operations": self.failed}


def pooled_store(fn, cfg: dict):
    stores = {"run_aimem": AimemPool, "run_agentmemory": AgentmemoryPool, "run_mempalace": MempalacePool,
              "run_hindsight": HindsightPool}
    if fn.__name__ not in stores:
        raise SystemExit(f"{fn.__name__}: no pooled store (A16 pools ai-memory, agentmemory, MemPalace and Hindsight)")
    return stores[fn.__name__](cfg)


def run_pooled(arm: str, fn, cfg: dict, questions: list[dict], out_dir: Path) -> int:
    """A16 pooled-store stress run for one arm: one store holds every eligible session, then every eligible
    question queries it once (sequentially, so rerank fallbacks are attributed exactly). Descriptive only.
    Stores do not survive a crash, so a resumed run re-ingests the pool and queries only the missing questions."""
    out = out_dir / f"pooled-{arm}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    arm_lock = open(out.with_suffix(".jsonl.lock"), "w")
    try:
        fcntl.flock(arm_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        sys.exit(f"pooled-{arm}: another harness process holds {arm_lock.name}")
    done = read_done(out)
    todo = [q for q in questions if q["question_id"] not in done]
    pool = pool_sessions(questions)
    print(f"pooled-{arm}: {len(pool)} sessions in one store; {len(todo)} questions to run, {len(done)} done", flush=True)
    if not todo:
        return 0
    with pooled_store(fn, cfg) as store:
        t0 = time.perf_counter()
        store.ingest(pool, Deadline(POOLED_BUDGET_S, "pooled ingest"))
        ingest_s = time.perf_counter() - t0
        print(f"pooled-{arm}: ingested in {ingest_s:.0f}s", flush=True)
        for n, q in enumerate(todo, 1):
            err, sids, extra = None, [], {}
            t1 = time.perf_counter()
            try:
                sids, extra = store.query(q)
            except EnvError as e:
                err = f"env: {e}"
            except InfraError as e:
                err = f"infra: {e}"
            except DeadlineError as e:
                err = f"deadline: {e}"
            except Exception as e:  # noqa: BLE001 - recorded, scored as an empty ranking (A4)
                err = f"{type(e).__name__}: {e}"
            metrics, positions, foreign_top5 = score_pooled(q, sids)
            row = {"question_id": q["question_id"], "question_type": q["question_type"], "arm": f"pooled-{arm}",
                   "base_arm": arm, "error": err, "latency_ms": (time.perf_counter() - t1) * 1000,
                   "pool_sessions": len(pool), "pool_ingest_s": ingest_s, "pooled_ranking": sids[:MAX_RANK],
                   "foreign_in_top5": foreign_top5, **extra, "ranking": positions, "metrics": metrics}
            with out.open("a") as fh:
                fh.write(json.dumps(row) + "\n")
            if n % 25 == 0 or err:
                print(f"[{n}/{len(todo)}] {q['question_id']} err={err}", flush=True)
            if err and err.startswith("env:"):
                print(f"pooled-{arm}: stopped at an env error (A4)", flush=True)
                return 1
    return 0


# ---------------------------------------------------------------- arms

def arms() -> dict:
    node = os.environ.get("LME_NODE", "")  # A15: VelaNext pins its own node; the Mac resolves it through mise
    if not node:
        mise = shutil.which("mise") or str(Path.home() / ".local/bin/mise")
        node = subprocess.run([mise, "which", "node"], capture_output=True, text=True).stdout.strip()
    qwen3_aimem = {"AI_MEMORY_EMBEDDING_PROVIDER": "openai-compat", "AI_MEMORY_EMBEDDING_BASE_URL": f"{EMBED_URL}/v1",
                   "AI_MEMORY_EMBEDDING_MODEL": "qwen3-embedding:4b", "AI_MEMORY_EMBEDDING_DIM": "2560",
                   "AI_MEMORY_EMBEDDING_QUERY_PREFIX": PROD_QUERY_PREFIX, "AI_MEMORY_EMBEDDING_DOCUMENT_PREFIX": ""}
    rerank = {"AI_MEMORY_RERANKER": "llm", "AI_MEMORY_LLM_PROVIDER": "openai-compat",
              "AI_MEMORY_LLM_BASE_URL": f"{LLM_URL}/v1", "AI_MEMORY_LLM_MODEL": "qwen3.5-9b-64k",
              "AI_MEMORY_LLM_REASONING_EFFORT": "low"}
    return {
        "bm25-full": (run_bm25_full, {}, 4),
        "dense-qwen3": (run_dense, {"model": "qwen3-embedding:4b", "query_prefix": DENSE_QUERY_PREFIX}, 1),
        "aimem-fts": (run_aimem, {"env": {"AI_MEMORY_EMBEDDING_PROVIDER": "none"}}, 6),
        "aimem-minilm": (run_aimem, {"env": {"AI_MEMORY_EMBEDDING_PROVIDER": "local"}, "minilm": True,
                                     "check_vectors": True}, 4),
        "aimem-qwen3": (run_aimem, {"env": qwen3_aimem, "check_vectors": True}, 6),
        "aimem-qwen3-rerank": (run_aimem, {"env": qwen3_aimem | rerank, "check_vectors": True}, 3),
        "aimem-qwen3-8b": (run_aimem, {"env": qwen3_aimem | {"AI_MEMORY_EMBEDDING_MODEL": "qwen3-embedding:8b",
                                                             "AI_MEMORY_EMBEDDING_DIM": "4096"},
                                       "check_vectors": True}, 6),
        "aimem-qwen3-0.6b": (run_aimem, {"env": qwen3_aimem | {"AI_MEMORY_EMBEDDING_MODEL": "qwen3-embedding:0.6b",
                                                               "AI_MEMORY_EMBEDDING_DIM": "1024"},
                                         "check_vectors": True}, 6),
        "am-keyless": (run_agentmemory, {"node": node, "env": {}}, AM_SLOTS),
        "am-minilm": (run_agentmemory, {"node": node, "env": {"EMBEDDING_PROVIDER": "local"}}, AM_SLOTS),
        "am-qwen3": (run_agentmemory, {"node": node, "probe_model": "qwen3-embedding:4b", "env": {
            "EMBEDDING_PROVIDER": "openai", "OPENAI_EMBEDDING_API_KEY": "local",
            "OPENAI_EMBEDDING_BASE_URL": EMBED_URL, "OPENAI_EMBEDDING_MODEL": "qwen3-embedding:4b",
            "OPENAI_EMBEDDING_DIMENSIONS": "2560"}}, AM_SLOTS),
    } | a15_arms(node, qwen3_aimem, rerank) | a16_arms()


def a15_arms(node: str, qwen3_aimem: dict, rerank: dict) -> dict:
    """A15 and A15.2 arms, built from the v3 configurations with only the model (and its card's prompts) changed.

    E: agentmemory's OpenAI provider, which sends no prefix (as shipped, like D3; the benchmark API path).
    F (A15.2): C4, the production configuration, with only the embedder changed: ai-memory with the card's
    prompts through its prefix settings and the LLM reranker on. Each F arm is preceded by its cache-fill pass
    (`-fill`, reranker off, no decision), so F's embeddings come from the byte-exact cache and the reranker runs
    on an otherwise idle GPU, as C4 does after C3 (A12, A13).
    G: the dense baseline with the card's prompts; G0 is diagnostic.
    H: C4 with another reranker LLM, at production's parameters (A15.2).
    D2h (A15.2): agentmemory with MiniLM fed through its shipped Claude Code hook sequence.
    Default workers are the A15.1 values; every arm that reranks keeps A12's 3.
    """
    out = {}
    for model, (dim, aimem_query, dense_query, document) in A15_EMBEDDERS.items():
        short = {NEMOTRON_8B: "nemotron-8b", NEMOTRON_1B: "nemotron-1b", HARRIER: "harrier-0.6b"}[model]
        out[f"am-{short}"] = (run_agentmemory, {"node": node, "probe_model": model, "env": {
            "EMBEDDING_PROVIDER": "openai", "OPENAI_EMBEDDING_API_KEY": "local", "OPENAI_EMBEDDING_BASE_URL": EMBED_URL,
            "OPENAI_EMBEDDING_MODEL": model, "OPENAI_EMBEDDING_DIMENSIONS": str(dim)}}, AM_SLOTS)
        embedder = {"AI_MEMORY_EMBEDDING_MODEL": model, "AI_MEMORY_EMBEDDING_DIM": str(dim),
                    "AI_MEMORY_EMBEDDING_QUERY_PREFIX": aimem_query, "AI_MEMORY_EMBEDDING_DOCUMENT_PREFIX": document}
        out[f"aimem-{short}-fill"] = (run_aimem, {"env": qwen3_aimem | embedder, "check_vectors": True}, 16)
        out[f"aimem-{short}"] = (run_aimem, {"env": qwen3_aimem | rerank | embedder, "check_vectors": True}, 3)
        out[f"dense-{short}"] = (run_dense, {"model": model, "query_prefix": dense_query, "doc_prefix": document}, 1)
    out["dense-qwen3-bf16"] = (run_dense, {"model": QWEN3_4B_BF16, "query_prefix": DENSE_QUERY_PREFIX}, 1)  # G0
    for arm, model in H_RERANK_MODELS.items():
        out[arm] = (run_aimem, {"env": qwen3_aimem | rerank | {"AI_MEMORY_LLM_MODEL": model}, "check_vectors": True}, 3)
    out["am-minilm-hooks"] = (run_agentmemory, {"node": node, "hooks": True, "env": {"EMBEDDING_PROVIDER": "local"}},
                              AM_SLOTS)  # D2h
    return out


def a16_arms() -> dict:
    """A16 decision-capable arms (with D2h above): M2 MemPalace in palace mode and K1 Hindsight on its subset.
    M2 is CPU-only (chromadb's ONNX MiniLM); K1's LLM is the H1 build on llama-server, its embedder and reranker
    Hindsight's local defaults on the CPU (the GPU stays with the LLM, as A12 keeps it for the reranker)."""
    return {M2: (run_mempalace, {}, 16),
            K1: (run_hindsight, {"subset": str(K1_SUBSET), "ingest_budget_s": K1_INGEST_BUDGET_S}, 4)}


def preflight(fn, cfg: dict) -> list[str]:
    """A15 review: environment problems found before the pool starts, instead of hundreds of error rows."""
    problems = []
    if fn is run_aimem:
        if not os.access(AIMEM_BIN, os.X_OK):
            problems.append(f"ai-memory binary not executable: {AIMEM_BIN}")
        if cfg.get("minilm") and not MINILM_DIR.is_dir():
            problems.append(f"all-MiniLM-L6-v2 missing: {MINILM_DIR}")
    if fn is run_agentmemory:
        node = cfg.get("node") or ""
        if not node or not os.access(node, os.X_OK):
            problems.append(f"node not executable: {node!r} (set LME_NODE)")
        if not os.access(III_BIN, os.X_OK):
            problems.append(f"iii not executable: {III_BIN}")
        if not AM_INDEX.exists():
            problems.append(f"agentmemory not installed: {AM_INDEX}")
        problems += [f"{tool} not on PATH" for tool in ("lsof", "pgrep", "ps") if shutil.which(tool) is None]
    if fn is run_mempalace:
        for tool in ("mempalace", "mempalace-mcp"):
            if not os.access(MP_VENV / "bin" / tool, os.X_OK):
                problems.append(f"{tool} not executable in {MP_VENV / 'bin'} (LME_MEMPALACE_VENV)")
        if not (MP_ONNX / "onnx/model.onnx").exists():
            problems.append(f"chromadb's MiniLM ONNX model missing: {MP_ONNX / 'onnx/model.onnx'} (LME_MEMPALACE_ONNX)")
    if fn is run_hindsight:
        try:
            status, _ = http_method("GET", f"{HS_URL}/health", timeout=10)
        except (InfraError, DeadlineError) as e:
            status = f"unreachable ({e})"
        if status != 200:
            problems.append(f"Hindsight not healthy at {HS_URL}: {status}")
        if not hs_llm_healthy():
            problems.append(f"the LLM server is not healthy at {LLM_URL}")
        if cfg.get("subset") and not Path(cfg["subset"]).exists():
            problems.append(f"subset file missing: {cfg['subset']}")
    return problems


def read_done(out: Path) -> set:
    """Question ids already written. A truncated last line (a crash mid-write) is set aside, never scored."""
    if not out.exists():
        return set()
    lines = out.read_text().splitlines(keepends=True)
    done = set()
    for i, line in enumerate(lines):
        try:
            done.add(json.loads(line)["question_id"])
        except (ValueError, KeyError):
            if i != len(lines) - 1:
                sys.exit(f"{out}: unreadable row {i + 1} is not the last line; repair the file by hand")
            out.with_suffix(".partial").write_text(line)
            out.write_text("".join(lines[:-1]))
            print(f"{out}: set aside a truncated last row in {out.with_suffix('.partial')}", flush=True)
    return done


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("arm")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--ids", nargs="*")
    ap.add_argument("--workers", type=int)
    ap.add_argument("--out", default=str(HERE / "results"))
    ap.add_argument("--pooled", action="store_true", help="A16 pooled-store stress run of this arm (pooled-<arm>.jsonl)")
    a = ap.parse_args()
    if OFFICIAL_IMPORT_ERROR:  # A15: fail before any question runs, not at the first score
        sys.exit(f"official LongMemEval code is not importable from {LME}: {OFFICIAL_IMPORT_ERROR}")
    fn, cfg, default_workers = arms()[a.arm]
    workers = a.workers or default_workers
    if fn is run_agentmemory and workers > min(AM_SLOTS, AM_SLOT_POOL):
        sys.exit(f"agentmemory arms use at most {min(AM_SLOTS, AM_SLOT_POOL)} isolated slots")
    problems = preflight(fn, cfg)
    if problems:
        sys.exit(f"{a.arm}: preflight failed: " + "; ".join(problems))
    model = embedding_model(fn, cfg)
    if model:  # A15 review: fail fast when the embedding service is down before the arm starts
        try:
            probe_embeddings(model)
        except EnvError as e:
            sys.exit(f"{a.arm}: {e}")
    manifest = json.loads(MANIFEST.read_text())
    wanted = set(manifest["full_session_track"])
    questions = [q for q in json.loads(DATA.read_text()) if q["question_id"] in wanted]
    if cfg.get("subset") and not a.pooled:  # A16: K1 runs on its preregistered stratified subset
        subset = set(json.loads(Path(cfg["subset"]).read_text())["question_ids"])
        questions = [q for q in questions if q["question_id"] in subset]
    if a.ids:
        questions = [q for q in questions if q["question_id"] in set(a.ids)]
    if a.limit:
        questions = questions[:a.limit]
    if a.pooled:
        sys.exit(run_pooled(a.arm, fn, cfg, questions, Path(a.out)))
    out = Path(a.out) / f"{a.arm}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    arm_lock = open(out.with_suffix(".jsonl.lock"), "w")  # A15 review: one process per arm output
    try:
        fcntl.flock(arm_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        sys.exit(f"{a.arm}: another harness process holds {arm_lock.name}")
    done = read_done(out)
    todo = [q for q in questions if q["question_id"] not in done]
    print(f"{a.arm}: {len(todo)} to run, {len(done)} already done", flush=True)
    lock = threading.Lock()
    halt = threading.Event()  # A15 review: the first env error invalidates the arm (A4), so stop spending on it

    def one(q):
        if halt.is_set():
            return None
        attempts, err, res = 0, None, None
        while attempts <= INFRA_RETRIES:
            attempts += 1
            try:
                res = fn(q, cfg)
                err = None
                break
            except InfraError as e:
                err = f"infra: {e}"
                if attempts <= INFRA_RETRIES:
                    time.sleep(INFRA_BACKOFF_S[min(attempts, len(INFRA_BACKOFF_S)) - 1])
            except DeadlineError as e:
                err = f"deadline: {e}"
                break
            except EnvError as e:
                err = f"env: {e}"
                break
            except Exception as e:  # noqa: BLE001 - recorded, scored as an empty ranking (A4)
                err = f"{type(e).__name__}: {e}"
                break
        if err and err.startswith("infra:") and model:
            if fn is run_dense:  # A15 review: the dense arm's only dependency is the embedding service
                err = f"env: embedding service failed after retries ({err})"
            else:
                try:
                    probe_embeddings(model)
                except EnvError as e:
                    err = f"env: {e} (after {err})"
        res = res or {"ranking": []}
        row = {"question_id": q["question_id"], "question_type": q["question_type"], "arm": a.arm,
               "attempts": attempts, "error": err, "sessions": len(q["haystack_session_ids"]), **res,
               "metrics": score(q, res["ranking"]),
               "ranking": res["ranking"][:MAX_RANK]}
        with lock, out.open("a") as fh:
            fh.write(json.dumps(row) + "\n")
        if err and err.startswith("env:"):
            halt.set()
        return row

    t0, n = time.time(), 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for fut in as_completed([pool.submit(one, q) for q in todo]):
            row = fut.result()
            if row is None:
                continue
            n += 1
            if n % 25 == 0 or row["error"]:
                m = row["metrics"]["full"]
                print(f"[{n}/{len(todo)} {time.time() - t0:.0f}s] {row['question_id']} R_all@5={m['recall_all@5']:.0f} "
                      f"err={row['error']}", flush=True)
    print(f"{a.arm}: finished {n} in {time.time() - t0:.0f}s", flush=True)
    if halt.is_set():
        sys.exit(f"{a.arm}: stopped at an env error; the arm is invalid until a full rerun (A4)")


if __name__ == "__main__":
    main()
