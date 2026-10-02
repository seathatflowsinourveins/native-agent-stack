"""OpenViking v0.4.22 session ingestion and default HTTP find/read retrieval.

The coordinator installs the pinned server. See openviking.md for the tagged
upstream interfaces, default settings, and embedding dimension limitation.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit

import httpx

from h2h.types import IngestStats, MemoryAdapter, ModelRoute, Retrieved, Session


class OpenVikingAdapter:
    name = "openviking"
    version = "v0.4.22"
    needs_llm = True

    def __init__(self) -> None:
        self._workdir: Path | None = None
        self._config: dict[str, Any] | None = None
        self._executable: str | None = None
        self._port: int | None = None
        self._process: subprocess.Popen[bytes] | None = None
        self._client: httpx.Client | None = None
        self._namespace: str | None = None

    @staticmethod
    def _model_config(route: ModelRoute, role: str) -> dict[str, str]:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", route.api_key_env):
            raise ValueError(f"OpenViking {role} api_key_env must be an environment variable name")
        if route.api_key_env not in os.environ:
            raise RuntimeError(f"OpenViking {role} requires environment variable {route.api_key_env}")
        url = urlsplit(route.base_url)
        if (
            url.scheme not in {"http", "https"}
            or not url.hostname
            or url.username is not None
            or url.password is not None
            or url.query
            or url.fragment
            or "$" in route.base_url
            or not route.model.strip()
            or "$" in route.model
        ):
            raise ValueError(f"OpenViking {role} requires a model and a credential-free HTTP base URL")
        # Upstream expands these placeholders in memory when loading ov.conf.
        # The adapter neither reads a key value nor writes one to disk.
        return {
            "provider": "openai",
            "model": route.model,
            "api_base": route.base_url,
            "api_key": "${" + route.api_key_env + "}",
        }

    def start(self, workdir: Path, llm: ModelRoute | None, embed: ModelRoute | None) -> None:
        if self._workdir is not None:
            raise RuntimeError("OpenViking is already started; stop it before starting again")
        if llm is None or embed is None:
            raise ValueError("OpenViking requires both an OpenAI-compatible LLM and embedding route")
        vlm = self._model_config(llm, "LLM")
        dense = self._model_config(embed, "embedding")
        try:
            port = int(os.environ["H2H_PORT"])
        except (KeyError, ValueError) as exc:
            raise ValueError("OpenViking requires H2H_PORT to contain a loopback TCP port") from exc
        if not 1 <= port <= 65535:
            raise ValueError("OpenViking H2H_PORT must be between 1 and 65535")
        executable = shutil.which("openviking-server")
        if executable is None:
            raise RuntimeError("Install openviking==0.4.22 before starting this adapter (see openviking.md)")
        private_root = workdir.resolve()
        private_root.mkdir(parents=True, exist_ok=True)
        self._workdir = private_root
        self._config = {"vlm": vlm, "embedding": {"dense": dense}}
        self._executable = executable
        self._port = port
        try:
            self._launch()
        except BaseException:
            self.stop()
            raise

    def _launch(self) -> None:
        if self._workdir is None or self._config is None or self._executable is None:
            raise RuntimeError("OpenViking has not been started")
        private_dir = Path(tempfile.mkdtemp(prefix="openviking-", dir=self._workdir))
        config_path = private_dir / "ov.conf"
        config = {**self._config, "storage": {"workspace": str(private_dir / "data")}}
        config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
        log_path = private_dir / "server.log"
        with log_path.open("ab") as log:
            self._process = subprocess.Popen(
                [
                    self._executable,
                    "--config", str(config_path),
                    "--host", "127.0.0.1",
                    "--port", str(self._port),
                ],
                cwd=private_dir,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
        self._client = httpx.Client(
            base_url=f"http://127.0.0.1:{self._port}",
            timeout=60.0,
            trust_env=False,
        )
        deadline = time.monotonic() + 120.0
        while time.monotonic() < deadline:
            if self._process.poll() is not None:
                raise RuntimeError(f"OpenViking exited during startup; inspect {log_path}")
            try:
                response = self._client.get("/ready")
                response.raise_for_status()
                if response.json().get("status") == "ready":
                    return
            except (httpx.HTTPError, ValueError):
                pass
            time.sleep(0.1)
        raise TimeoutError(f"OpenViking was not ready after 120 seconds; inspect {log_path}")

    def _shutdown(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None
        if self._process is not None:
            if self._process.poll() is None:
                try:
                    self._process.terminate()
                except ProcessLookupError:
                    pass
            try:
                self._process.wait(timeout=10.0)
            except subprocess.TimeoutExpired:
                try:
                    self._process.kill()
                except ProcessLookupError:
                    pass
                self._process.wait(timeout=10.0)
            self._process = None

    def reset(self, namespace: str) -> None:
        if self._workdir is None:
            raise RuntimeError("Start OpenViking before resetting a namespace")
        if not namespace:
            raise ValueError("OpenViking namespace must be nonempty")
        self._namespace = None
        self._shutdown()
        try:
            self._launch()
        except BaseException:
            self._shutdown()
            raise
        self._namespace = namespace

    def _check_namespace(self, namespace: str) -> None:
        if self._client is None or self._process is None:
            raise RuntimeError("Start and reset OpenViking before using it")
        if self._process.poll() is not None:
            raise RuntimeError("The adapter's OpenViking subprocess has exited")
        if self._namespace is None or namespace != self._namespace:
            raise ValueError("Reset OpenViking to this namespace before using it")

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        if self._client is None:
            raise RuntimeError("OpenViking has no active HTTP client")
        response = self._client.request(method, path, **kwargs)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or payload.get("status") != "ok" or "result" not in payload:
            raise RuntimeError(f"OpenViking returned an invalid success response for {path}")
        return payload["result"]

    def _wait_task(self, task_id: str) -> None:
        deadline = time.monotonic() + 3600.0
        while time.monotonic() < deadline:
            task = self._request("GET", f"/api/v1/tasks/{quote(task_id, safe='')}")
            if not isinstance(task, dict):
                raise RuntimeError("OpenViking returned an invalid commit task")
            status = task.get("status")
            if status == "completed":
                return
            if status not in {"pending", "running", "cancelling"}:
                raise RuntimeError(f"OpenViking commit task {task_id} ended with status {status!r}")
            time.sleep(1.0)
        raise TimeoutError(f"OpenViking commit task {task_id} did not finish within 3600 seconds")

    def ingest(self, namespace: str, sessions: list[Session]) -> IngestStats:
        self._check_namespace(namespace)
        ordered: list[tuple[datetime, Session]] = []
        for session in sessions:
            try:
                date = datetime.strptime(session.date, "%Y/%m/%d (%a) %H:%M")
            except ValueError as exc:
                raise ValueError(f"Invalid LongMemEval date for session {session.session_id}") from exc
            if any(turn.role not in {"user", "assistant"} for turn in session.turns):
                raise ValueError(f"OpenViking requires user/assistant roles in session {session.session_id}")
            ordered.append((date, session))
        ordered.sort(key=lambda item: item[0])
        started = time.monotonic()
        for date, session in ordered:
            created = self._request("POST", "/api/v1/sessions", json={})
            if not isinstance(created, dict) or not isinstance(created.get("session_id"), str) or not created["session_id"]:
                raise RuntimeError("OpenViking did not return a session_id")
            path = f"/api/v1/sessions/{quote(created['session_id'], safe='')}"
            for index, turn in enumerate(session.turns):
                # Match upstream's LongMemEval importer; options.created_at in
                # the SDK is the top-level created_at field on the HTTP wire.
                self._request(
                    "POST", path + "/messages",
                    json={
                        "role": turn.role,
                        "parts": [{"type": "text", "text": turn.content}],
                        "created_at": (date + timedelta(seconds=index)).isoformat(),
                    },
                )
            committed = self._request("POST", path + "/commit", json={})
            if not isinstance(committed, dict):
                raise RuntimeError("OpenViking returned an invalid commit response")
            if committed.get("status") == "skipped" and committed.get("task_id") is None:
                continue
            task_id = committed.get("task_id")
            if committed.get("status") != "accepted" or not isinstance(task_id, str) or not task_id:
                raise RuntimeError("OpenViking did not accept the session commit with a task_id")
            self._wait_task(task_id)
        return IngestStats(
            sessions=len(ordered),
            seconds=time.monotonic() - started,
            llm_calls=None,
            notes=["Default commit/task responses do not report an aggregate LLM call count."],
        )

    def _read_context(self, uri: str) -> str:
        try:
            text = self._request("GET", "/api/v1/content/read", params={"uri": uri})
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 400:
                raise
            error = exc.response.json().get("error", {})
            details = error.get("details", {})
            if (
                error.get("code") != "INVALID_ARGUMENT"
                or details.get("expected") != "file"
                or details.get("actual") != "directory"
            ):
                raise
            # Hierarchical find can return a directory. The retrieval guide
            # documents overview() for directory hits and read() for files.
            text = self._request("GET", "/api/v1/content/overview", params={"uri": uri})
        if not isinstance(text, str):
            raise RuntimeError("OpenViking returned non-text memory content")
        return text

    def retrieve(self, namespace: str, query: str, k: int, question_date: str | None) -> list[Retrieved]:
        self._check_namespace(namespace)
        if k <= 0:
            return []
        # question_date does not restrict processing-time created_at/updated_at
        # metadata. Upstream's benchmark also issues an unfiltered find.
        result = self._request(
            "POST", "/api/v1/search/find",
            json={"query": query, "limit": k},
        )
        categories = ("memories", "resources", "skills")
        if not isinstance(result, dict) or not any(category in result for category in categories):
            raise RuntimeError("OpenViking returned an invalid find result")
        # Match FindResult.__iter__ without narrowing the default target or
        # context types, and without applying another ranking model.
        hits = []
        for category in categories:
            contexts = result.get(category, [])
            if not isinstance(contexts, list):
                raise RuntimeError("OpenViking returned an invalid find result")
            hits.extend(contexts)
        retrieved = []
        for hit in hits[:k]:
            if not isinstance(hit, dict) or not isinstance(hit.get("uri"), str) or not hit["uri"]:
                raise RuntimeError("OpenViking find returned a context without a URI")
            score = hit.get("score")
            if score is not None and (isinstance(score, bool) or not isinstance(score, (int, float))):
                raise RuntimeError("OpenViking find returned a nonnumeric score")
            retrieved.append(Retrieved(
                text=self._read_context(hit["uri"]),
                score=float(score) if score is not None else None,
            ))
        return retrieved

    def stop(self) -> None:
        self._namespace = None
        self._shutdown()
        self._workdir = None
        self._config = None
        self._executable = None
        self._port = None


def build() -> MemoryAdapter:
    return OpenVikingAdapter()
