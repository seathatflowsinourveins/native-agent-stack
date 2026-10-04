"""Neutral LongMemEval-S retrieval harness: identical inputs to every memory system, official metrics.

Protocol: PREREGISTRATION.md (amendments A1-A12). Official pieces are imported, not copied, from
xiaowu0162/LongMemEval@9e0b455: `process_item_flat_index` (session corpus ids and the official gold
relabelling) and `evaluate_retrieval` (recall_any / recall_all / ndcg_any). Two tracks are scored per
question: the official track (official labels) and the full-session track (gold = answer_session_ids).

Failure classes (A4): `infra` (server start, refused or reset connection, HTTP 5xx) retries the whole
question with a fresh store, at most twice; `deadline` (30 min ingest, 120 s query, monotonic) and any
other error score an empty ranking; `env` (an embedding failure or degraded retrieval) is recorded
and makes the whole arm invalid until it is rerun.

usage: python lme_harness.py ARM [--limit N] [--ids ID ...] [--workers N] [--out DIR]
Arms: bm25-full, dense-qwen3, aimem-fts, aimem-minilm, aimem-qwen3, aimem-qwen3-rerank,
      aimem-qwen3-8b, aimem-qwen3-0.6b, am-keyless, am-minilm, am-qwen3
Output: results/<arm>.jsonl, one line per question; reruns resume by question id.
"""
import argparse
import fcntl
import hashlib
import json
import os
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
from datetime import datetime
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
LME = Path.home() / ".local/share/agent-ecosystem/src/LongMemEval"
sys.path.insert(0, str(LME))
from src.retrieval.eval_utils import evaluate_retrieval  # noqa: E402  (official)
from src.retrieval.run_retrieval import process_item_flat_index  # noqa: E402  (official)

DATA = HERE / "data/longmemeval_s_cleaned.json"
MANIFEST = HERE / "eligible-manifest.json"
KS = [1, 3, 5, 10, 30, 50]
MAX_RANK = 50
OLLAMA = "http://127.0.0.1:11434"
EMBED_URL = os.environ.get("LME_EMBED_URL", OLLAMA)  # A11: arms started later use the benchmark embed server
AM_SLOTS = int(os.environ.get("LME_AM_SLOTS", "4"))  # A11: isolated agentmemory slots
LLM_URL = os.environ.get("LME_LLM_URL", OLLAMA)  # A12: the reranker LLM endpoint for C4
RERANK_FALLBACK = {"rerank_timeouts": "reranker timed out; keeping pre-rerank order",
                   "rerank_failures": "reranker failed; keeping pre-rerank order",
                   "rerank_invalid": "reranker returned incomplete or invalid scores; keeping pre-rerank order"}
AIMEM_BIN = Path.home() / ".local/share/agent-ecosystem/tools/ai-memory-2.5.0-19b6429/ai-memory"
AIMEM_TOKEN = "lme-bench-token"
AIMEM_LIMIT = 50  # A10: the registered retrieval depth for every system
MINILM_DIR = HERE / "models/all-MiniLM-L6-v2"
AM_ROOT = Path.home() / ".local/share/agent-ecosystem/bench/agentmemory"
AM_INDEX = AM_ROOT / "node_modules/@agentmemory/agentmemory/dist/index.mjs"
AM_LOCK = AM_ROOT / ".bench.lock"
PROD_QUERY_PREFIX = ("Instruct: Given a question about past work, decisions or project knowledge, "
                     "retrieve the memory pages that answer it\nQuery:")
DENSE_QUERY_PREFIX = ("Instruct: Given a question about the user's past conversations, retrieve the chat "
                      "sessions that contain the answer\nQuery:")
INGEST_BUDGET_S = 30 * 60
QUERY_BUDGET_S = 120
INFRA_RETRIES = 2
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
    out.sort(key=lambda s: (parse_date(s["date"]), s["pos"]))
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


def stop(proc: subprocess.Popen):
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
    """Environment check for arms that depend on the Ollama embedding service."""
    try:
        status, _, body = http_json(f"{EMBED_URL}/v1/embeddings", {"model": model, "input": ["probe"]}, timeout=60)
        vec = json.loads(body)["data"][0]["embedding"] if status == 200 else None
    except (InfraError, DeadlineError, ValueError, KeyError, IndexError) as e:
        raise EnvError(f"embedding service probe failed: {e}") from e
    if not vec or not any(vec):
        raise EnvError(f"embedding service probe returned HTTP {status} or a zero vector")


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
    def __init__(self, path: Path, model: str):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute("CREATE TABLE IF NOT EXISTS e (k TEXT PRIMARY KEY, v BLOB)")
        self.model, self.lock = model, threading.Lock()

    def embed(self, texts: list[str], deadline: Deadline) -> np.ndarray:
        keys = [hashlib.sha256(f"{self.model}\0{t}".encode()).hexdigest() for t in texts]
        with self.lock:
            have = {k: np.frombuffer(v, dtype=np.float32) for k, v in
                    self.db.execute(f"SELECT k, v FROM e WHERE k IN ({','.join('?' * len(keys))})", keys)}
        missing = [(k, t) for k, t in zip(keys, texts) if k not in have]
        for i in range(0, len(missing), 8):
            chunk = missing[i:i + 8]
            status, _, body = http_json(f"{EMBED_URL}/v1/embeddings",
                                        {"model": self.model, "input": [t for _, t in chunk]}, timeout=deadline.left())
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


def run_dense(q: dict, cfg: dict) -> dict:
    cache = _CACHE.setdefault(cfg["model"], EmbedCache(HERE / "cache/embeddings.sqlite", cfg["model"]))
    sess = sessions_of(q)
    docs = [dated(s, " ".join(t["content"] for t in s["turns"] if t["role"] == "user")) for s in sess]
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


def run_aimem(q: dict, cfg: dict) -> dict:
    sess = sessions_of(q)
    project = "lme-" + hashlib.sha256(q["question_id"].encode()).hexdigest()[:12]
    uuid_to_pos = {uuid.uuid5(uuid.NAMESPACE_OID, s["hid"]): s["pos"] for s in sess}
    home = tempfile.mkdtemp(prefix="lme-aimem-")
    data_dir = Path(home) / "data"
    stderr_path = Path(home) / "stderr.log"
    proc = None
    try:
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
        wait_http(f"{base}/", proc)
        try:
            pre = aimem_query(base, project, "anything", 10, Deadline(QUERY_BUDGET_S, "empty-store check"))
        except RuntimeError as e:  # a fresh store has no workspace yet: that is the empty state
            if "not found" not in str(e):
                raise
            pre = {}
        if pre.get("hits") or pre.get("raw_hits"):
            raise RuntimeError("store not empty before ingest")
        ingest_deadline = Deadline(INGEST_BUDGET_S, "ingest")
        t0 = time.perf_counter()
        pending = aimem_items(q, sess, project)
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
        ingest_s = time.perf_counter() - t0
        t1 = time.perf_counter()
        res = aimem_query(base, project, q["question"], cfg.get("limit", AIMEM_LIMIT),
                          Deadline(QUERY_BUDGET_S, "query"))
        latency_ms = (time.perf_counter() - t1) * 1000
        ranking, unattributed = [], 0
        for hit in res.get("hits", []):
            path = hit.get("path", "")
            try:
                pos = uuid_to_pos.get(uuid.UUID(path.removeprefix("sessions/").removesuffix(".md")))
            except ValueError:
                pos = None
            if pos is None:
                unattributed += 1
            elif pos not in ranking:
                ranking.append(pos)
        for hit in res.get("raw_hits", []):
            pos = uuid_to_pos.get(uuid.UUID(hit["session_id"])) if hit.get("session_id") else None
            if pos is not None and pos not in ranking:
                ranking.append(pos)
        health = {}
        db = data_dir / "db/memory.sqlite"
        if cfg.get("check_vectors") and db.exists():
            con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            health["embed_failures"] = con.execute("SELECT COUNT(*) FROM page_embed_failures").fetchone()[0]
            health["pages_without_vector"] = con.execute(
                "SELECT COUNT(*) FROM pages p LEFT JOIN page_embeddings e ON e.page_id = p.id "
                "WHERE p.is_latest = 1 AND e.page_id IS NULL AND TRIM(p.body) != ''").fetchone()[0]
            con.close()
        result = {"ranking": ranking, "latency_ms": latency_ms, "ingest_s": ingest_s,
                  "unattributed": unattributed, **health}
        server_log = stderr_path.read_text(errors="ignore")
        if cfg["env"].get("AI_MEMORY_RERANKER"):
            result |= {k: server_log.count(msg) for k, msg in RERANK_FALLBACK.items()}  # A12: reported, not errors
        degraded = AIMEM_DEGRADED.findall(server_log)
        if cfg.get("check_vectors") and (degraded or health.get("embed_failures") or health.get("pages_without_vector")):
            raise EnvError(f"degraded retrieval: {len(degraded)} embedding warnings, {health}")
        return result
    except (InfraError, DeadlineError, EnvError):
        raise
    except Exception as e:
        tail = stderr_path.read_text(errors="ignore")[-400:] if stderr_path.exists() else ""
        raise RuntimeError(f"{type(e).__name__}: {e} | server stderr tail: {tail!r}") from e
    finally:
        stop(proc)
        shutil.rmtree(home, ignore_errors=True)


# ---------------------------------------------------------------- agentmemory (its own benchmark's API path)

import queue as _queue

_SLOTS: "_queue.Queue[int]" = _queue.Queue()
for _i in range(AM_SLOTS):
    _SLOTS.put(_i)


def am_ports(slot: int) -> dict:
    """agentmemory's multi-instance scheme: REST anchor, streams +1, viewer +2, engine +46023."""
    rest = 3611 + 100 * slot
    return {"rest": rest, "stream": rest + 1, "engine": rest + 46023}


def _children(pid: int) -> list[int]:
    out = subprocess.run(["pgrep", "-P", str(pid)], capture_output=True, text=True).stdout.split()
    kids = [int(x) for x in out]
    return kids + [g for k in kids for g in _children(k)]


def am_teardown(proc: subprocess.Popen, ports: dict, timeout: float = 15.0):
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
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        time.sleep(0.3)
    raise InfraError(f"agentmemory slot ports still busy: {ports}")


def run_agentmemory(q: dict, cfg: dict) -> dict:
    """Each question runs in one of AM_SLOTS isolated slots (own engine, REST, stream and viewer ports)."""
    slot = _SLOTS.get()
    try:
        return _run_agentmemory_slot(q, cfg, slot)
    finally:
        _SLOTS.put(slot)


def _run_agentmemory_slot(q: dict, cfg: dict, slot: int) -> dict:
    sess = sessions_of(q)
    ports = am_ports(slot)
    root = tempfile.mkdtemp(prefix=f"lme-am{slot}-", dir="/tmp")
    proc = None
    try:
        am_teardown(None, ports)  # a clean slot before start
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
        env = clean_env(root) | {"PATH": f"{AM_ROOT}/bin:/usr/bin:/bin"} | slot_env
        proc = subprocess.Popen([str(AM_ROOT / "bin/iii"), "--no-update-check", "--config", f"{root}/iii-config.yaml"],
                                cwd=root, env=env, stdout=open(Path(root) / "iii.log", "w"), stderr=subprocess.STDOUT,
                                start_new_session=True)
        base = f"http://127.0.0.1:{ports['rest']}"
        wait_http(f"{base}/agentmemory/livez", proc, ok=lambda s, b: s == 200 and '"ok"' in b)
        time.sleep(1.5)  # the worker re-registers once right after livez turns ok
        status, _, body = http_json(f"{base}/agentmemory/smart-search", {"query": "anything", "limit": 50})
        if not 200 <= status < 300 or json.loads(body).get("results"):
            raise RuntimeError(f"store not empty before ingest ({status})")
        id_to_pos, superseding = {}, 0
        ingest_deadline = Deadline(INGEST_BUDGET_S, "ingest")
        t0 = time.perf_counter()
        for s in sess:
            content = dated(s, "\n\n".join(f"[{t['role']}] {t['content']}" for t in s["turns"]))
            status, _, body = http_json(f"{base}/agentmemory/remember",
                                        {"content": content, "type": "eval-session", "concepts": [s["hid"]]},
                                        timeout=ingest_deadline.left())
            if not 200 <= status < 300:
                raise RuntimeError(f"remember HTTP {status}: {body[:200]}")
            mem = json.loads(body).get("memory") or {}
            if not mem.get("id"):
                raise RuntimeError(f"remember returned no id: {body[:200]}")
            id_to_pos[mem["id"]] = s["pos"]
            superseding += bool(mem.get("supersedes"))
        ingest_s = time.perf_counter() - t0
        t1 = time.perf_counter()
        status, _, body = http_json(f"{base}/agentmemory/smart-search", {"query": q["question"], "limit": 50},
                                    timeout=Deadline(QUERY_BUDGET_S, "query").left())
        latency_ms = (time.perf_counter() - t1) * 1000
        if not 200 <= status < 300:
            raise RuntimeError(f"smart-search HTTP {status}: {body[:200]}")
        ranking, unattributed = [], 0
        for row in json.loads(body).get("results", []):
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
        return {"ranking": ranking, "latency_ms": latency_ms, "ingest_s": ingest_s, "unattributed": unattributed,
                "embed_failures": failures, "superseding_saves": superseding, "slot": slot}
    finally:
        am_teardown(proc, ports)
        shutil.rmtree(root, ignore_errors=True)


# ---------------------------------------------------------------- arms

def arms() -> dict:
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
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("arm")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--ids", nargs="*")
    ap.add_argument("--workers", type=int)
    ap.add_argument("--out", default=str(HERE / "results"))
    a = ap.parse_args()
    fn, cfg, default_workers = arms()[a.arm]
    workers = a.workers or default_workers
    if fn is run_agentmemory and workers > AM_SLOTS:
        sys.exit(f"agentmemory arms use at most {AM_SLOTS} isolated slots")
    manifest = json.loads(MANIFEST.read_text())
    wanted = set(manifest["full_session_track"])
    questions = [q for q in json.loads(DATA.read_text()) if q["question_id"] in wanted]
    if a.ids:
        questions = [q for q in questions if q["question_id"] in set(a.ids)]
    if a.limit:
        questions = questions[:a.limit]
    out = Path(a.out) / f"{a.arm}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    done = {json.loads(line)["question_id"] for line in out.open()} if out.exists() else set()
    todo = [q for q in questions if q["question_id"] not in done]
    print(f"{a.arm}: {len(todo)} to run, {len(done)} already done", flush=True)
    lock = threading.Lock()

    def one(q):
        attempts, err, res = 0, None, None
        while attempts <= INFRA_RETRIES:
            attempts += 1
            try:
                res = fn(q, cfg)
                err = None
                break
            except InfraError as e:
                err = f"infra: {e}"
            except DeadlineError as e:
                err = f"deadline: {e}"
                break
            except EnvError as e:
                err = f"env: {e}"
                break
            except Exception as e:  # noqa: BLE001 - recorded, scored as an empty ranking (A4)
                err = f"{type(e).__name__}: {e}"
                break
        res = res or {"ranking": []}
        row = {"question_id": q["question_id"], "question_type": q["question_type"], "arm": a.arm,
               "attempts": attempts, "error": err, **res, "metrics": score(q, res["ranking"]),
               "ranking": res["ranking"][:MAX_RANK]}
        with lock, out.open("a") as fh:
            fh.write(json.dumps(row) + "\n")
        return row

    t0, n = time.time(), 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for fut in as_completed([pool.submit(one, q) for q in todo]):
            row = fut.result()
            n += 1
            if n % 25 == 0 or row["error"]:
                m = row["metrics"]["full"]
                print(f"[{n}/{len(todo)} {time.time() - t0:.0f}s] {row['question_id']} R_all@5={m['recall_all@5']:.0f} "
                      f"err={row['error']}", flush=True)
    print(f"{a.arm}: finished {n} in {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
