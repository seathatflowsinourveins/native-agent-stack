"""MemPalace v3.10.0's native conversation miner and HTTP MCP search.

See mempalace.md for the pinned API, default settings, and date limitations.
Only start() imports the HTTP dependency or launches a process.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from h2h.types import IngestStats, MemoryAdapter, ModelRoute, Retrieved, Session


class MemPalaceAdapter:
    name = "mempalace"
    version = "v3.10.0"
    needs_llm = False

    def __init__(self) -> None:
        self._workdir: Path | None = None
        self._runtime: Path | None = None
        self._namespace: str | None = None
        self._embed: ModelRoute | None = None
        self._port: int | None = None
        self._process: subprocess.Popen[bytes] | None = None
        self._client: Any = None
        self._request_id = 0
        self._file_id = 0
        self._source_sessions: dict[str, str] = {}

    def start(
        self, workdir: Path, llm: ModelRoute | None, embed: ModelRoute | None
    ) -> None:
        if self._workdir is not None:
            raise RuntimeError("MemPalace is already started; call stop() first")
        try:
            port = int(os.environ["H2H_PORT"])
        except (KeyError, ValueError) as exc:
            raise ValueError("MemPalace requires H2H_PORT to be an integer TCP port") from exc
        if not 1 <= port <= 65535:
            raise ValueError("MemPalace requires H2H_PORT between 1 and 65535")
        if embed is not None and (not embed.base_url.strip() or not embed.model.strip()):
            raise ValueError("MemPalace's embedding route needs a base_url and model")
        # The native default exchange miner and search do not use a generative LLM.
        # A common answerer's llm route must not enable optional extraction/reranking.
        self._embed = embed
        self._port = port
        self._workdir = Path(workdir).resolve()
        try:
            self._workdir.mkdir(parents=True, exist_ok=True)
            self._launch()
        except BaseException:
            self.stop()
            raise

    def _launch(self) -> None:
        try:
            import httpx
        except ImportError as exc:
            raise RuntimeError("The MemPalace adapter requires the harness's httpx dependency") from exc

        if self._workdir is None or self._port is None:
            raise RuntimeError("Call MemPalace start() first")
        self._runtime = Path(tempfile.mkdtemp(prefix="mempalace-", dir=self._workdir))
        config_dir = self._runtime / "config"
        config_dir.mkdir(mode=0o700)
        palace_dir = self._runtime / "palace"
        (self._runtime / "sessions").mkdir(mode=0o700)

        # Inherited MemPalace settings could select the host's palace, server store,
        # bearer token, or tuning. An empty private config restores native defaults.
        child_env = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("MEMPALACE_") and key != "MEMPAL_DIR"
        }
        child_env["MEMPALACE_CONFIG_DIR"] = str(config_dir)
        child_env["MEMPALACE_PALACE_PATH"] = str(palace_dir)
        if self._embed is not None:
            child_env["MEMPALACE_EMBEDDING_MODEL"] = "openai-compat"
            child_env["MEMPALACE_EMBEDDING_API_URL"] = self._embed.base_url
            child_env["MEMPALACE_EMBEDDING_API_MODEL"] = self._embed.model
            key = os.environ.get(self._embed.api_key_env)
            if key:
                child_env["MEMPALACE_EMBEDDING_API_KEY"] = key

        self._request_id = 0
        self._file_id = 0
        self._source_sessions.clear()
        try:
            self._process = subprocess.Popen(
                [
                    "mempalace",
                    "serve",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(self._port),
                    "--palace",
                    str(palace_dir),
                ],
                cwd=self._runtime,
                env=child_env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self._client = httpx.Client(
                base_url=f"http://127.0.0.1:{self._port}",
                timeout=httpx.Timeout(600.0, connect=5.0),
                trust_env=False,
            )
            deadline = time.monotonic() + 60.0
            while True:
                code = self._process.poll()
                if code is not None:
                    raise RuntimeError(f"MemPalace exited during startup (exit {code})")
                try:
                    response = self._client.get("/healthz", timeout=1.0)
                    if response.status_code == 200:
                        break
                except httpx.RequestError:
                    pass
                if time.monotonic() >= deadline:
                    raise RuntimeError("MemPalace did not become healthy within 60 seconds")
                time.sleep(0.1)

            # Upstream accepts omitted initialize params and negotiates its default
            # protocol version. Verify the actual server rather than guessing a pin.
            initialized = self._rpc("initialize", {})
            server = initialized.get("serverInfo", {})
            if server.get("name") != "mempalace" or server.get("version") != "3.10.0":
                raise RuntimeError("The MemPalace adapter requires a MemPalace 3.10.0 server")
            response = self._client.post(
                "/mcp",
                json={"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
            )
            response.raise_for_status()
        except FileNotFoundError as exc:
            self._close_runtime()
            raise RuntimeError("Install the pinned upstream CLI: pip install -U mempalace==3.10.0") from exc
        except BaseException:
            self._close_runtime()
            raise

    def _rpc(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        if self._client is None:
            raise RuntimeError("Call MemPalace start() first")
        self._request_id += 1
        request_id = self._request_id
        response = self._client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": request_id, "method": method, "params": params},
        )
        response.raise_for_status()
        body = response.json()
        if (
            not isinstance(body, dict)
            or body.get("jsonrpc") != "2.0"
            or body.get("id") != request_id
        ):
            raise RuntimeError("MemPalace returned an invalid JSON-RPC response")
        if "error" in body:
            raise RuntimeError(f"MemPalace JSON-RPC error: {body['error']}")
        result = body.get("result")
        if not isinstance(result, dict):
            raise RuntimeError("MemPalace returned an invalid JSON-RPC result")
        return result

    def _tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        result = self._rpc("tools/call", {"name": name, "arguments": arguments})
        if result.get("isError"):
            raise RuntimeError(f"MemPalace {name} returned an MCP tool error")
        content = result.get("content")
        if not isinstance(content, list) or not content or not isinstance(content[0], dict):
            raise RuntimeError(f"MemPalace {name} returned no JSON text content")
        try:
            data = json.loads(content[0]["text"])
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError(f"MemPalace {name} returned invalid JSON text content") from exc
        if not isinstance(data, dict):
            raise RuntimeError(f"MemPalace {name} returned an invalid tool result")
        if "error" in data or data.get("success") is False:
            raise RuntimeError(f"MemPalace {name} failed: {data.get('error', 'unspecified failure')}")
        return data

    def reset(self, namespace: str) -> None:
        if self._workdir is None:
            raise RuntimeError("Call MemPalace start() first")
        if not isinstance(namespace, str) or not namespace:
            raise ValueError("MemPalace namespace must be a nonempty string")
        self._close_runtime()
        # Every reset, including a repeated namespace, gets a new private store
        # and process. Old Chroma handles, config, and source mappings cannot leak.
        self._launch()
        self._namespace = namespace

    def _require_namespace(self, namespace: str) -> Path:
        if self._namespace != namespace or self._client is None or self._runtime is None:
            raise RuntimeError("Call MemPalace reset(namespace) before ingesting or retrieving")
        if self._process is None or self._process.poll() is not None:
            raise RuntimeError("The MemPalace process is no longer running")
        return self._runtime

    def ingest(self, namespace: str, sessions: list[Session]) -> IngestStats:
        runtime = self._require_namespace(namespace)
        started = time.monotonic()
        for session in sessions:
            if any(turn.role not in {"user", "assistant"} for turn in session.turns):
                raise ValueError("MemPalace conversations support only user and assistant turns")
        for session in sessions:
            extension = ".txt" if len(session.turns) < 2 else ".json"
            source = runtime / "sessions" / f"session-{self._file_id:08d}{extension}"
            self._file_id += 1
            if len(session.turns) < 2:
                # The native JSON parser requires two messages. Native plaintext
                # avoids raw-JSON fallback for singletons and invents no content
                # for an empty session (normalize_conversations returns []).
                transcript = "\n\n".join(
                    f"{'> ' if turn.role == 'user' else ''}"
                    f"[Session date: {session.date}]\n{turn.content}"
                    for turn in session.turns
                )
                source.write_text(transcript, encoding="utf-8")
            else:
                # Claude.ai's documented export parser accepts this messages shape.
                # Include the dataset's date as indexed text: its native .json parser
                # does not carry export dates through to drawer authored_at metadata.
                export = {
                    "uuid": session.session_id,
                    "created_at": session.date,
                    "chat_messages": [
                        {
                            "role": turn.role,
                            "content": f"[Session date: {session.date}]\n{turn.content}",
                        }
                        for turn in session.turns
                    ],
                }
                source.write_text(json.dumps(export, ensure_ascii=True), encoding="utf-8")
            # Submit one file at a time so native directory traversal cannot
            # reorder the coordinator's chronologically ordered sessions.
            result = self._tool("mempalace_mine", {"source": str(source), "mode": "convos"})
            if result.get("success") is not True:
                raise RuntimeError("MemPalace did not confirm completion of conversation mining")
            self._source_sessions[str(source)] = session.session_id
            self._source_sessions[source.name] = session.session_id
        return IngestStats(
            sessions=len(sessions),
            seconds=time.monotonic() - started,
            llm_calls=0,
            notes=[
                "Native convos/exchange mining; no generative LLM calls.",
                "Original session dates are indexed in transcript text; authored_at uses native defaults.",
                "Session count records completed mine calls, not reported stored drawer counts.",
            ],
        )

    def retrieve(
        self, namespace: str, query: str, k: int, question_date: str | None
    ) -> list[Retrieved]:
        self._require_namespace(namespace)
        if not 1 <= k <= 100:
            raise ValueError("MemPalace's documented search limit is between 1 and 100")
        # since/before constrain wall-clock filing time, not the dataset dates.
        # Passing question_date as either would exclude freshly ingested history.
        data = self._tool("mempalace_search", {"query": query, "limit": k})
        hits = data.get("results")
        if not isinstance(hits, list):
            raise RuntimeError("MemPalace search returned no results list")
        retrieved = []
        for hit in hits:
            if not isinstance(hit, dict) or not isinstance(hit.get("text"), str):
                raise RuntimeError("MemPalace search returned an invalid result")
            source = hit.get("source_path") or hit.get("source_file")
            session_id = self._source_sessions.get(source) if isinstance(source, str) else None
            score = hit.get("similarity")
            retrieved.append(
                Retrieved(
                    text=hit["text"],
                    session_ids=(session_id,) if session_id is not None else (),
                    score=float(score) if score is not None else None,
                )
            )
        return retrieved

    def _close_runtime(self) -> None:
        self._namespace = None
        self._source_sessions.clear()
        try:
            if self._process is not None:
                if self._process.poll() is None:
                    self._process.terminate()
                    try:
                        self._process.wait(timeout=5.0)
                    except subprocess.TimeoutExpired:
                        self._process.kill()
                        self._process.wait(timeout=5.0)
                self._process = None
        finally:
            if self._client is not None:
                self._client.close()
                self._client = None
            self._runtime = None

    def stop(self) -> None:
        self._close_runtime()
        self._workdir = None
        self._embed = None
        self._port = None


def build() -> MemoryAdapter:
    return MemPalaceAdapter()
