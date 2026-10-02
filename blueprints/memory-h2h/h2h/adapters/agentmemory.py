"""agentmemory v0.9.29 observations/search, with private container state.

The coordinator builds the upstream image first; this adapter never installs it.
See agentmemory.md for the upstream sources and default truncation behavior.
"""

from __future__ import annotations

from contextlib import ExitStack
import json
import math
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import tempfile
import time
from typing import Any
from urllib.parse import urlsplit
import uuid

import httpx

from h2h.types import IngestStats, MemoryAdapter, ModelRoute, Retrieved, Session


class AgentMemoryAdapter:
    name = "agentmemory"
    version = "v0.9.29"
    # These two REST functions use synthetic compression and search, not chat.
    needs_llm = False

    def __init__(self) -> None:
        self._workdir: Path | None = None
        self._store: Path | None = None
        self._process: subprocess.Popen[bytes] | None = None
        self._client: httpx.Client | None = None
        self._container: str | None = None
        self._namespace: str | None = None
        self._env: dict[str, str] = {}
        self._port = 0
        self._session_ids: set[str] = set()
        self._route_notes: list[str] = []

    def start(
        self, workdir: Path, llm: ModelRoute | None, embed: ModelRoute | None
    ) -> None:
        if self._workdir is not None:
            raise RuntimeError("agentmemory is already started")
        try:
            port = int(os.environ.get("H2H_PORT", ""))
        except ValueError:
            raise ValueError("Set H2H_PORT to the loopback REST port") from None
        # Preserve upstream's documented quartet offsets, including its bus.
        if not 1024 <= port <= 19512:
            raise ValueError("H2H_PORT must be 1024..19512 (engine uses port + 46023)")
        if sys.platform != "linux":
            raise RuntimeError("agentmemory isolation requires Linux Docker host networking")
        docker_host = os.environ.get("DOCKER_HOST")
        if docker_host is not None:
            parsed_host = urlsplit(docker_host)
            if (
                not docker_host.startswith("unix:///")
                or parsed_host.scheme != "unix"
                or parsed_host.netloc
                or not parsed_host.path.startswith("/")
                or parsed_host.path == "/"
                or parsed_host.query
                or parsed_host.fragment
                or any(char in docker_host for char in ("\x00", "\n", "\r"))
            ):
                raise ValueError(
                    "DOCKER_HOST must name a local absolute Unix socket (unix:///...); "
                    "remote Docker endpoints are unsupported"
                )
        if llm is not None and embed is not None and llm.api_key_env != embed.api_key_env:
            raise ValueError(
                "agentmemory v0.9.29 ignores the embedding key when OPENAI_API_KEY "
                "is set (#1435); both routes must use the same api_key_env"
            )

        # Do not inherit ambient memory settings, provider keys or proxy settings.
        env = {
            name: os.environ[name]
            for name in ("PATH", "LANG", "LC_ALL", "TZ", "DOCKER_HOST")
            if name in os.environ
        }
        notes: list[str] = []
        if llm is not None:
            env.update(self._route_env(llm, embedding=False))
        if embed is not None:
            env.update(self._route_env(embed, embedding=True))
            # This is required model metadata, not a ranking/compression option.
            dimensions = os.environ.get("OPENAI_EMBEDDING_DIMENSIONS")
            if dimensions is not None:
                if not dimensions.isascii() or not dimensions.isdecimal() or int(dimensions) < 1:
                    raise ValueError("OPENAI_EMBEDDING_DIMENSIONS must be a positive integer")
                env["OPENAI_EMBEDDING_DIMENSIONS"] = dimensions
            bare_model = embed.model.split("/", 1)[-1]
            if dimensions is None and bare_model not in {
                "text-embedding-3-small", "text-embedding-3-large", "text-embedding-ada-002"
            }:
                raise ValueError(
                    "agentmemory v0.9.29 guesses 1536 dimensions for custom models "
                    "(#1373); set the documented OPENAI_EMBEDDING_DIMENSIONS "
                    "to the model's actual output width"
                )
            notes.append("Embedding width uses the upstream model table or OPENAI_EMBEDDING_DIMENSIONS.")
        elif llm is not None:
            notes.append(
                "No embedding route supplied: upstream auto-selects OpenAI embeddings "
                "at the LLM base URL with its default text-embedding-3-small model."
            )
        else:
            notes.append("No provider routes supplied: upstream runs synthetic compression and BM25 only.")

        root = workdir.resolve()
        if any(char in str(root) for char in (",", "\n", "\r")):
            raise ValueError("Docker bind-mount workdir cannot contain commas or newlines")
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        docker_config = root / "docker-config"
        docker_config.mkdir(mode=0o700, exist_ok=True)
        env["DOCKER_CONFIG"] = str(docker_config)
        env["III_REST_PORT"] = str(port)
        # Use IPv4 consistently with the loopback engine bind below.
        env["III_ENGINE_URL"] = f"ws://127.0.0.1:{port + 46023}"
        self._workdir, self._env, self._port = root, env, port
        self._route_notes = notes
        try:
            self._launch()
        except BaseException:
            self.stop()
            raise

    @staticmethod
    def _route_env(route: ModelRoute, *, embedding: bool) -> dict[str, str]:
        parsed = urlsplit(route.base_url)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or not route.model.strip()
        ):
            raise ValueError("Model routes need an HTTP(S) base URL without credentials and a model")
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", route.api_key_env):
            raise ValueError("api_key_env must be an environment variable name")
        key = os.environ.get(route.api_key_env)
        if not key or not key.strip():
            raise ValueError(f"Set the credential environment variable {route.api_key_env}")
        if embedding:
            return {
                "EMBEDDING_PROVIDER": "openai",
                "OPENAI_EMBEDDING_BASE_URL": route.base_url.rstrip("/"),
                "OPENAI_EMBEDDING_MODEL": route.model,
                "OPENAI_EMBEDDING_API_KEY": key,
            }
        return {
            "OPENAI_BASE_URL": route.base_url.rstrip("/"),
            "OPENAI_MODEL": route.model,
            "OPENAI_API_KEY": key,
        }

    @staticmethod
    def _engine_config(port: int) -> str:
        # rohitg00/agentmemory v0.9.29 iii-config.yaml: native defaults.
        # Explicit infrastructure addresses work around upstream #1245.
        # iii/v0.11.2 documents the worker-manager's port/host configuration.
        return f"""workers:
  - name: iii-worker-manager
    config:
      port: {port + 46023}
      host: 127.0.0.1
  - name: iii-http
    config:
      port: {port}
      host: 127.0.0.1
      default_timeout: 180000
      cors:
        allowed_origins: ["http://localhost:{port}", "http://localhost:{port + 2}", "http://127.0.0.1:{port}", "http://127.0.0.1:{port + 2}"]
        allowed_methods: [GET, POST, PUT, DELETE, OPTIONS]
  - name: iii-state
    config:
      adapter:
        name: kv
        config:
          store_method: file_based
          file_path: ./data/state_store.db
  - name: iii-queue
    config:
      adapter:
        name: builtin
  - name: iii-pubsub
    config:
      adapter:
        name: local
  - name: iii-cron
    config:
      adapter:
        name: kv
  - name: iii-stream
    config:
      port: {port + 1}
      host: 127.0.0.1
      adapter:
        name: kv
        config:
          store_method: file_based
          file_path: ./data/stream_store
  - name: iii-observability
    config:
      enabled: true
      service_name: agentmemory
      exporter: memory
      sampling_ratio: 0.1
      metrics_enabled: true
      logs_enabled: true
      logs_console_output: false
  - name: iii-exec
    config:
      watch:
        - src/**/*.ts
      exec:
        - node dist/index.mjs
"""

    def _launch(self) -> None:
        if self._workdir is None:
            raise RuntimeError("Call start() first")
        # Binding detects an occupied port without querying someone else's API.
        with ExitStack() as stack:
            for port in (self._port, self._port + 1, self._port + 2, self._port + 46023):
                probe = stack.enter_context(socket.socket(socket.AF_INET, socket.SOCK_STREAM))
                try:
                    probe.bind(("127.0.0.1", port))
                except OSError:
                    raise RuntimeError(f"agentmemory requires unused loopback port {port}") from None

        generation = Path(tempfile.mkdtemp(prefix="agentmemory-v0929-", dir=self._workdir))
        self._store = generation / "data"
        self._store.mkdir(mode=0o700)
        config = generation / "iii-config.yaml"
        config.write_text(self._engine_config(self._port), encoding="utf-8")
        self._container = f"h2h-agentmemory-{uuid.uuid4().hex}"
        command = [
            "docker", "run", "--rm", "--pull", "never", "--no-healthcheck",
            "--name", self._container, "--network", "host",
            "--mount", f"type=bind,source={self._store},target=/data",
            "--mount", f"type=bind,source={config},target=/opt/agentmemory/iii-config.yaml,readonly",
            "--entrypoint", "/usr/bin/tini",
        ]
        for name in sorted(self._env):
            if name.startswith(("OPENAI_", "III_")) or name == "EMBEDDING_PROVIDER":
                # Docker inherits the child environment; argv never contains a key.
                command.extend(("--env", name))
        command.extend((
            "agentmemory-h2h:0.9.29", "--", "agentmemory",
            "--port", str(self._port), "--data-dir", "/data",
        ))
        try:
            self._process = subprocess.Popen(
                command, cwd=self._workdir, env=self._env,
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            self._container = None
            raise RuntimeError("Install Docker and build agentmemory-h2h:0.9.29 (see agentmemory.md)") from None
        self._client = httpx.Client(
            base_url=f"http://127.0.0.1:{self._port}", timeout=180.0, trust_env=False
        )
        deadline = time.monotonic() + 60.0
        while time.monotonic() < deadline:
            if self._process.poll() is not None:
                raise RuntimeError("agentmemory container exited; verify the pinned local image and Docker host networking")
            try:
                response = self._client.get("/agentmemory/health", timeout=2.0)
                if response.status_code == 200:
                    body = response.json()
                    if not isinstance(body, dict) or body.get("service") != "agentmemory" or body.get("version") != "0.9.29":
                        raise RuntimeError("agentmemory health did not report the pinned version 0.9.29")
                    return
            except httpx.TransportError:
                pass
            time.sleep(0.1)
        raise RuntimeError("agentmemory did not become ready within 60 seconds")

    def _stop_container(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None
        if self._container is not None:
            # A docker-run attach error can leave the container running after
            # the CLI exits. Ownership follows its UUID name, not CLI liveness.
            try:
                result = subprocess.run(
                    ["docker", "stop", "--timeout", "20", self._container],
                    cwd=self._workdir, env=self._env, stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30, check=False,
                )
                stopped = result.returncode == 0
            except (OSError, subprocess.TimeoutExpired):
                stopped = False
            if not stopped:
                # --rm may already have removed this container. Only a
                # successful empty query proves absence; errors retain ownership.
                try:
                    remaining = subprocess.run(
                        ["docker", "container", "ls", "--all", "--filter",
                         f"name={self._container}", "--format", "{{.ID}}"],
                        cwd=self._workdir, env=self._env, stdin=subprocess.DEVNULL,
                        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=30, check=False,
                    )
                except (OSError, subprocess.TimeoutExpired):
                    raise RuntimeError("Docker could not stop or verify absence of the owned agentmemory container") from None
                if remaining.returncode != 0 or remaining.stdout.strip():
                    raise RuntimeError("Docker could not stop or verify absence of the owned agentmemory container")
        if self._process is not None:
            self._process.wait(timeout=30)
        self._process = None
        self._container = None

    def reset(self, namespace: str) -> None:
        if self._workdir is None:
            raise RuntimeError("Call start() before reset()")
        if not isinstance(namespace, str) or not namespace.strip():
            raise ValueError("namespace must be a non-empty string")
        self._namespace = None
        self._session_ids.clear()
        self._stop_container()
        try:
            self._launch()
        except BaseException:
            self._stop_container()
            raise
        self._namespace = namespace

    def _require_namespace(self, namespace: str) -> httpx.Client:
        if self._client is None or self._namespace is None or namespace != self._namespace:
            raise RuntimeError("Call reset(namespace) before ingest/retrieve; only that namespace is reachable")
        return self._client

    @staticmethod
    def _post(client: httpx.Client, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = client.post(path, json=payload)
        response.raise_for_status()
        result = response.json()
        if not isinstance(result, dict) or result.get("success") is False or "error" in result:
            raise RuntimeError(f"agentmemory {path} returned an invalid or failed response")
        return result

    def ingest(self, namespace: str, sessions: list[Session]) -> IngestStats:
        client = self._require_namespace(namespace)
        ids = [session.session_id for session in sessions]
        if (
            any(not isinstance(sid, str) or not sid.strip() or sid != sid.strip() for sid in ids)
            or len(set(ids)) != len(ids)
            or any(sid in self._session_ids for sid in ids)
        ):
            raise ValueError("Session IDs must be non-empty, unpadded and unique within the namespace")
        if any(not isinstance(s.date, str) or not s.date.strip() for s in sessions):
            raise ValueError("Session dates must be non-empty strings")
        if any(t.role not in {"user", "assistant"} for s in sessions for t in s.turns):
            raise ValueError("Conversation turns must have user or assistant roles")
        started = time.perf_counter()
        for session in sessions:
            # Same one-transcript-per-session representation as upstream's LME
            # benchmark; no splitting to evade its 400 UTF-16 code-unit cap.
            result = self._post(client, "/agentmemory/observe", {
                "hookType": "prompt_submit",
                "sessionId": session.session_id,
                "project": "memory-h2h",
                "cwd": "/data",
                "timestamp": session.date,
                "data": {"prompt": "\n".join(f"{turn.role}: {turn.content}" for turn in session.turns)},
            })
            if not isinstance(result.get("observationId"), str) or not result["observationId"]:
                raise RuntimeError("agentmemory did not acknowledge the conversation observation")
            self._session_ids.add(session.session_id)
        return IngestStats(
            sessions=len(sessions), seconds=time.perf_counter() - started,
            llm_calls=None,
            notes=[
                "Default synthetic compression retains at most 400 UTF-16 code units per session transcript, including a truncation ellipsis.",
                "Observe awaits indexing; no session-end/summarize or opt-in LLM compression is requested.",
                "Upstream does not report total LLM calls; default background jobs remain enabled.",
                *self._route_notes,
            ],
        )

    def retrieve(
        self, namespace: str, query: str, k: int, question_date: str | None
    ) -> list[Retrieved]:
        client = self._require_namespace(namespace)
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string")
        if type(k) is not int or not 1 <= k <= 100:
            raise ValueError("agentmemory search supports k from 1 to 100")
        # No as-of parameter exists on this API. Preserve the original query.
        result = self._post(client, "/agentmemory/search", {"query": query, "limit": k})
        rows = result.get("results")
        if not isinstance(rows, list):
            raise RuntimeError("agentmemory search response is missing results")
        retrieved: list[Retrieved] = []
        for row in rows[:k]:
            if not isinstance(row, dict) or not isinstance(row.get("observation"), dict):
                raise RuntimeError("agentmemory full search result is missing its observation")
            score = row.get("score")
            if score is not None and (type(score) not in (int, float) or not math.isfinite(score)):
                raise RuntimeError("agentmemory search result has an invalid score")
            sid = row.get("sessionId")
            retrieved.append(Retrieved(
                # Retain all returned text and timestamps, with no raw-store
                # expansion that would undo the system's compression choices.
                text=json.dumps(row["observation"], ensure_ascii=False),
                session_ids=(sid,) if isinstance(sid, str) and sid else (),
                score=float(score) if score is not None else None,
            ))
        return retrieved

    def stop(self) -> None:
        self._namespace = None
        self._stop_container()
        self._env.clear()
        self._session_ids.clear()
        self._route_notes.clear()
        self._workdir = None
        self._store = None


def build() -> MemoryAdapter:
    return AgentMemoryAdapter()
