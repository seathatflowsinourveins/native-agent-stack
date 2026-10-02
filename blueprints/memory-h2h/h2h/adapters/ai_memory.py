"""ai-memory v2.5.2's hook replay and stateless HTTP MCP interfaces.

See ai_memory.md for pinned sources and the assistant-capture limitation.
Importing this module neither starts a process nor makes a network request.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from typing import Any
from urllib.parse import urlencode, urlsplit
import uuid

import httpx

from h2h.types import IngestStats, MemoryAdapter, ModelRoute, Retrieved, Session


class AiMemoryAdapter:
    """One owned native server and a fresh, private store for every reset."""

    def __init__(self, *, consolidate: bool = False) -> None:
        self.name = "ai-memory-llm" if consolidate else "ai-memory"
        self.version = "v2.5.2"
        self.needs_llm = consolidate
        self._workdir: Path | None = None
        self._data_dir: Path | None = None
        self._cwd: Path | None = None
        self._process: subprocess.Popen[bytes] | None = None
        self._client: httpx.Client | None = None
        self._env: dict[str, str] = {}
        self._namespace: str | None = None
        self._project = ""
        self._base_url = ""
        self._session_ids: dict[str, str] = {}
        self._rpc_id = 0
        self._embedding_route_supplied = False

    def start(
        self, workdir: Path, llm: ModelRoute | None, embed: ModelRoute | None
    ) -> None:
        if self._workdir is not None:
            raise RuntimeError("ai-memory adapter is already started")
        raw_port = os.environ.get("H2H_PORT", "")
        try:
            port = int(raw_port)
        except ValueError:
            raise ValueError("H2H_PORT must name a loopback TCP port") from None
        if not 1 <= port <= 65535:
            raise ValueError("H2H_PORT must be between 1 and 65535")

        # Only ordinary process settings cross the boundary. Ambient ai-memory
        # options, provider credentials, proxies, and user config are excluded.
        child_env = {
            key: os.environ[key]
            for key in ("PATH", "LANG", "LC_ALL", "TZ", "SYSTEMROOT", "WINDIR")
            if key in os.environ
        }
        # Explicit local selects the default model but requires it to load;
        # an unset provider could silently run FTS-only on the first boot.
        child_env["AI_MEMORY_EMBEDDING_PROVIDER"] = "local"
        if self.needs_llm:
            if llm is None:
                raise ValueError("build_llm() requires an OpenAI-compatible LLM route")
            parsed = urlsplit(llm.base_url)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.netloc
                or parsed.username is not None
                or parsed.password is not None
                or parsed.query
                or parsed.fragment
                or not llm.model.strip()
            ):
                raise ValueError("LLM route requires a base URL without credentials and a model")
            child_env.update(
                AI_MEMORY_LLM_PROVIDER="openai-compat",
                AI_MEMORY_LLM_BASE_URL=llm.base_url.rstrip("/"),
                AI_MEMORY_LLM_MODEL=llm.model,
            )
            # Upstream permits keyless self-hosted compat endpoints. If a key
            # is supplied, translate only its env name; never serialize it.
            if llm.api_key_env in os.environ:
                child_env["LLM_API_KEY"] = os.environ[llm.api_key_env]

        root = workdir.resolve()
        root.mkdir(parents=True, exist_ok=True)
        # A version mismatch is rejected before serve can migrate any store.
        try:
            result = subprocess.run(
                ["ai-memory", "--version"],
                cwd=root,
                env=child_env,
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
        except FileNotFoundError:
            raise RuntimeError("Install the native ai-memory v2.5.2 binary first (see ai_memory.md)") from None
        if result.returncode != 0 or result.stdout.strip() != "ai-memory 2.5.2":
            raise RuntimeError("The ai-memory adapter requires the native v2.5.2 binary on PATH")

        self._workdir = root
        self._env = child_env
        self._base_url = f"http://127.0.0.1:{port}"
        self._embedding_route_supplied = embed is not None
        try:
            self._launch()
        except BaseException:
            self.stop()
            raise

    def _launch(self) -> None:
        if self._workdir is None:
            raise RuntimeError("Call start() before launching ai-memory")
        model_source = (
            self._data_dir / "models" / "all-MiniLM-L6-v2"
            if self._data_dir is not None else None
        )
        self._data_dir = Path(tempfile.mkdtemp(prefix="ai-memory-v252-", dir=self._workdir))
        if model_source is not None:
            files = ("config.json", "tokenizer.json", "model.safetensors")
            if all((model_source / filename).is_file() for filename in files):
                model_dest = self._data_dir / "models" / "all-MiniLM-L6-v2"
                model_dest.mkdir(parents=True)
                for filename in files:
                    shutil.copyfile(model_source / filename, model_dest / filename)
        self._cwd = self._data_dir / "conversation"
        self._cwd.mkdir()
        # A retained store is an inspection artifact, never reused by reset.
        # Native serve creates its own wiki, database, model cache, and logs.
        self._process = subprocess.Popen(
            [
                "ai-memory", "serve", "--transport", "http", "--bind",
                self._base_url.removeprefix("http://"),
                "--data-dir", str(self._data_dir),
            ],
            cwd=self._data_dir,
            env=self._env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self._client = httpx.Client(base_url=self._base_url, timeout=960.0, trust_env=False)
        # Explicit local can download its checksum-pinned model before HTTP
        # startup. This is a readiness deadline, not a memory tuning option.
        deadline = time.monotonic() + 600.0
        while time.monotonic() < deadline:
            if self._process.poll() is not None:
                raise RuntimeError(
                    "ai-memory exited during startup; explicit local embeddings must load "
                    "(see the private store's logs/)"
                )
            try:
                response = self._client.get("/healthz", timeout=1.0)
                if response.status_code == 200 and response.json() == {"status": "ok"}:
                    return
            except (httpx.HTTPError, ValueError):
                pass
            time.sleep(0.2)
        raise RuntimeError("ai-memory did not become ready within 600 seconds")

    def _stop_server(self) -> None:
        # Signal only the process this instance created. If waiting fails,
        # retain the handle and refuse to launch another server on this port.
        if self._process is not None:
            if self._process.poll() is None:
                self._process.terminate()
                try:
                    self._process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    self._process.kill()
                    self._process.wait(timeout=15)
            self._process = None
        if self._client is not None:
            self._client.close()
            self._client = None

    def reset(self, namespace: str) -> None:
        if self._workdir is None:
            raise RuntimeError("Call start() before reset()")
        if not namespace:
            raise ValueError("namespace must be nonempty")
        self._namespace = None
        self._stop_server()
        self._session_ids.clear()
        self._rpc_id = 0
        # Repeating even the same namespace always gets an empty store.
        self._project = f"q-{uuid.uuid5(uuid.NAMESPACE_OID, namespace).hex}"
        try:
            self._launch()
        except BaseException:
            self._stop_server()
            raise
        self._namespace = namespace

    def _require_namespace(self, namespace: str) -> httpx.Client:
        if self._client is None or self._namespace != namespace:
            raise RuntimeError("Call reset(namespace) before ingest or retrieve")
        if self._process is None or self._process.poll() is not None:
            raise RuntimeError("The owned ai-memory server is no longer running")
        return self._client

    @staticmethod
    def _stored_session_id(raw: str) -> str:
        try:
            return str(uuid.UUID(raw))
        except ValueError:
            return str(uuid.uuid5(uuid.NAMESPACE_OID, raw))

    def _hook(self, client: httpx.Client, event: str, sid: str, extra: dict[str, Any]) -> None:
        # Singleton batches preserve event order even when rate limiting skips
        # an item. /hook alone returns 202 before its writes finish.
        url = "/hook?" + urlencode({
            "event": event, "agent": "claude-code", "workspace": "longmemeval",
            "project": self._project, "session_id": sid,
        })
        item = {"url": url, "body": {"session_id": sid, "cwd": str(self._cwd), **extra}}
        for attempt in range(60):
            response = client.post("/hook/batch", json=[item])
            response.raise_for_status()
            ack = response.json()
            if not isinstance(ack, dict):
                raise RuntimeError("Invalid ai-memory hook acknowledgement")
            indices = ack.get("accepted_indices")
            if indices is not None:
                if (
                    not isinstance(indices, list)
                    or any(type(index) is not int or index != 0 for index in indices)
                    or len(indices) > 1
                ):
                    raise RuntimeError("Invalid ai-memory accepted_indices for a singleton batch")
                accepted = indices == [0]
            else:
                count = ack.get("accepted")
                if type(count) is not int or count not in (0, 1):
                    raise RuntimeError("Invalid ai-memory accepted prefix for a singleton batch")
                accepted = count == 1
            if ack.get("failed_index") is not None:
                raise RuntimeError("ai-memory failed to process a hook event")
            if accepted:
                return
            if attempt < 59:
                time.sleep(0.5)
        raise RuntimeError("ai-memory did not acknowledge the hook event after 60 attempts")

    def ingest(self, namespace: str, sessions: list[Session]) -> IngestStats:
        client = self._require_namespace(namespace)
        # Validate the whole input before leaving a partially ingested session.
        ids = [self._stored_session_id(session.session_id) for session in sessions]
        if len(set(ids)) != len(ids) or any(sid in self._session_ids for sid in ids):
            raise ValueError("Session IDs must be unique within a namespace")
        if any(turn.role not in {"user", "assistant"} for s in sessions for turn in s.turns):
            raise ValueError("ai-memory replay accepts only user and assistant turns")
        started = time.perf_counter()
        for session, stored_id in zip(sessions, ids, strict=True):
            self._hook(client, "session-start", session.session_id, {
                "hook_event_name": "SessionStart", "source": "startup",
            })
            for turn in session.turns:
                if turn.role == "user":
                    self._hook(client, "user-prompt-submit", session.session_id, {
                        "hook_event_name": "UserPromptSubmit",
                        "prompt": f"[session date: {session.date}] {turn.content}",
                    })
                else:
                    # Upstream's default server strips assistant excerpts.
                    # Replay Stop cadence without enabling either opt-in.
                    self._hook(client, "stop", session.session_id, {"hook_event_name": "Stop"})
            self._hook(client, "session-end", session.session_id, {
                "hook_event_name": "SessionEnd", "reason": "exit",
            })
            self._session_ids[stored_id] = session.session_id
            if self.needs_llm and session.turns:
                # Synchronous single-page consolidation; every optional tool
                # parameter and the SessionEnd queue setting retain defaults.
                self._call_tool(client, "memory_consolidate", {"session_id": stored_id})
        notes = [
            "AI_MEMORY_EMBEDDING_PROVIDER=local (default all-MiniLM-L6-v2)",
            "Assistant text is not stored: default assistant capture is off; Stop events are metadata only.",
        ]
        if self.needs_llm:
            notes.append("Manual default single-page memory_consolidate per nonempty session; native default background review may make additional LLM calls; upstream does not report total call counts.")
        if self._embedding_route_supplied:
            notes.append("The supplied embedding route is unused: this configuration requires upstream local embeddings.")
        return IngestStats(sessions=len(sessions), seconds=time.perf_counter() - started, notes=notes)

    def _call_tool(self, client: httpx.Client, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        self._rpc_id += 1
        request_id = self._rpc_id
        response = client.post("/mcp", headers={"Accept": "application/json, text/event-stream"}, json={
            "jsonrpc": "2.0", "id": request_id, "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        })
        response.raise_for_status()
        if response.headers.get("content-type", "").startswith("text/event-stream"):
            rpc = None
            for line in response.text.splitlines():
                if line.startswith("data:"):
                    try:
                        candidate = json.loads(line[5:].strip())
                    except ValueError:
                        continue
                    if isinstance(candidate, dict) and candidate.get("id") == request_id:
                        rpc = candidate
            if rpc is None:
                raise RuntimeError("MCP SSE response did not contain the requested id")
        else:
            rpc = response.json()
        if not isinstance(rpc, dict) or rpc.get("id") != request_id:
            raise RuntimeError("Invalid or mismatched ai-memory JSON-RPC response")
        if "error" in rpc:
            raise RuntimeError(f"ai-memory MCP {name} returned an error")
        result = rpc.get("result")
        if not isinstance(result, dict) or result.get("isError"):
            raise RuntimeError(f"ai-memory MCP {name} failed")
        for content in result.get("content", []):
            if isinstance(content, dict) and content.get("type") == "text":
                parsed = json.loads(content["text"])
                if isinstance(parsed, dict):
                    return parsed
        raise RuntimeError(f"ai-memory MCP {name} returned no JSON text result")

    def retrieve(
        self, namespace: str, query: str, k: int, question_date: str | None
    ) -> list[Retrieved]:
        client = self._require_namespace(namespace)
        if type(k) is not int or not 1 <= k <= 100:
            raise ValueError("ai-memory memory_query supports k between 1 and 100")
        # Dataset dates describe conversations; as_of instead filters the
        # store's wall-clock ingestion history and disables normal streams.
        payload = self._call_tool(client, "memory_query", {
            "query": query, "workspace": "longmemeval", "project": self._project, "limit": k,
        })
        out: list[Retrieved] = []
        for group in ("hits", "raw_hits"):
            hits = payload.get(group, [])
            if not isinstance(hits, list):
                raise RuntimeError(f"Invalid ai-memory {group} result")
            for hit in hits:
                if not isinstance(hit, dict):
                    raise RuntimeError("Invalid ai-memory retrieval hit")
                source_id = hit.get("session_id") if group == "raw_hits" else None
                if group == "hits":
                    path = hit.get("path", "")
                    if isinstance(path, str) and path.startswith("sessions/") and path.endswith(".md"):
                        source_id = path[len("sessions/"):-len(".md")]
                provenance: tuple[str, ...] = ()
                if isinstance(source_id, str):
                    try:
                        source_id = str(uuid.UUID(source_id))
                    except ValueError:
                        source_id = ""
                    if source_id:
                        provenance = (self._session_ids.get(source_id, source_id),)
                title, snippet = hit.get("title"), hit.get("snippet")
                if not isinstance(title, str) or not isinstance(snippet, str):
                    raise RuntimeError("ai-memory retrieval hit is missing its title or snippet")
                rank = hit.get("rank")
                score = float(rank) if type(rank) in (float, int) else None
                out.append(Retrieved(text=f"{title}\n{snippet}", session_ids=provenance, score=score))
        # Preserve the official harness's page-then-raw ordering and snippets.
        # Supplemental global preferences cannot exist in a new private store.
        return out[:k]

    def stop(self) -> None:
        self._namespace = None
        self._stop_server()
        self._env.clear()
        self._session_ids.clear()
        self._workdir = None
        self._data_dir = None
        self._cwd = None


def build() -> MemoryAdapter:
    """Zero chat-LLM defaults, with explicitly enabled local embeddings."""
    return AiMemoryAdapter()


def build_llm() -> MemoryAdapter:
    """Local embeddings plus documented manual, default single-page consolidation."""
    return AiMemoryAdapter(consolidate=True)
