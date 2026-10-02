"""Cognee v1.6.2's local REST API; see cognee.md for pinned contracts."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import sys
import tempfile
import time
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from h2h.types import IngestStats, MemoryAdapter, ModelRoute, Retrieved, Session

if TYPE_CHECKING:
    import httpx


class CogneeAdapter:
    name = "cognee"
    version = "v1.6.2"
    needs_llm = True

    def __init__(self) -> None:
        self._workdir: Path | None = None
        self._environment: dict[str, str] | None = None
        self._process: subprocess.Popen[bytes] | None = None
        self._client: httpx.Client | None = None
        self._port: int | None = None
        self._namespace: str | None = None
        self._dataset: str | None = None
        self._processed = 0
        self._searchable = False

    def start(
        self, workdir: Path, llm: ModelRoute | None, embed: ModelRoute | None
    ) -> None:
        if self._workdir is not None:
            raise RuntimeError("Cognee is already started; call stop() before starting again.")
        port_text = os.environ.get("H2H_PORT", "")
        if not port_text.isascii() or not port_text.isdecimal():
            raise ValueError("H2H_PORT must name an unused loopback port.")
        port = int(port_text)
        if not 1 <= port <= 65535 or port in (
            3710, 3711, 3800, 5433, 5434, 20128, 20129, 49374, 49474
        ):
            raise ValueError("H2H_PORT is outside the allowed range or reserved by the host.")
        if llm is not None and embed is None:
            raise ValueError(
                "Cognee needs an explicit embedding ModelRoute with an LLM route; "
                "otherwise its default would reuse that key against OpenAI's embedding API."
            )
        try:
            installed = importlib.metadata.version("cognee")
        except importlib.metadata.PackageNotFoundError:
            raise RuntimeError("Install cognee==1.6.2 in this Python environment first.") from None
        if installed != "1.6.2":
            raise RuntimeError(f"Cognee v1.6.2 is required; installed release is {installed}.")

        # A small runtime environment prevents inherited Cognee tuning, remote
        # stores, or credentials from changing the documented default pipeline.
        environment = {
            key: os.environ[key]
            for key in (
                "PATH", "LANG", "LC_ALL", "LC_CTYPE", "TMPDIR", "TEMP", "TMP",
                "SSL_CERT_FILE", "SSL_CERT_DIR", "SYSTEMROOT", "WINDIR",
            )
            if key in os.environ
        }
        environment.update(
            ENABLE_BACKEND_ACCESS_CONTROL="false",
            PYTHONDONTWRITEBYTECODE="1",
        )
        if llm is not None:
            environment.update(self._route_environment(llm, "LLM"))
        if embed is not None:
            environment.update(self._route_environment(embed, "EMBEDDING"))

        self._workdir = workdir.resolve()
        self._workdir.mkdir(parents=True, exist_ok=True)
        self._environment = environment
        self._port = port
        self.needs_llm = llm is not None
        try:
            self._launch("startup")
        except BaseException:
            self.stop()
            raise

    @staticmethod
    def _route_environment(route: ModelRoute, role: str) -> dict[str, str]:
        parsed = urlsplit(route.base_url)
        if (
            parsed.scheme not in ("http", "https")
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError(f"Cognee {role} needs an OpenAI-compatible HTTP base URL.")
        if not route.model or not route.model.strip():
            raise ValueError(f"Cognee {role} needs a model name.")
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", route.api_key_env):
            raise ValueError(f"Cognee {role} api_key_env must be an environment variable name.")
        key = os.environ.get(route.api_key_env)
        if not key or not key.strip():
            raise RuntimeError(f"Set the {route.api_key_env} environment variable for Cognee {role}.")
        # LiteLLM's dispatch prefix is separate from the endpoint's model name.
        # No key is placed in arguments, files, or the parent's environment.
        return {
            f"{role}_PROVIDER": "openai",
            f"{role}_MODEL": f"openai/{route.model}",
            f"{role}_ENDPOINT": route.base_url.rstrip("/"),
            f"{role}_API_KEY": key,
        }

    def _launch(self, label: str) -> None:
        import httpx

        if self._workdir is None or self._environment is None or self._port is None:
            raise RuntimeError("Start Cognee before resetting it.")
        # Fail without contacting an existing listener. H2H_PORT is allocated
        # exclusively by the coordinator; Cognee itself binds without reuse_port.
        with socket.create_server(("127.0.0.1", self._port), reuse_port=False):
            pass
        digest = hashlib.sha256(label.encode("utf-8")).hexdigest()[:12]
        run_dir = Path(tempfile.mkdtemp(prefix=f"cognee-{digest}-", dir=self._workdir))
        environment = self._environment.copy()
        # Cognee's dotenv resolver otherwise searches ancestors/package roots
        # and overrides even preset environment values. Pin an empty local file.
        env_file = run_dir / "empty.env"
        env_file.touch(mode=0o600, exist_ok=False)
        environment["COGNEE_ENV_FILE"] = str(env_file)
        for setting, directory in (
            ("DATA_ROOT_DIRECTORY", "data"),
            ("SYSTEM_ROOT_DIRECTORY", "system"),
            ("CACHE_ROOT_DIRECTORY", "cache"),
            ("COGNEE_LOGS_DIR", "logs"),
        ):
            path = run_dir / directory
            path.mkdir()
            environment[setting] = str(path)
        self._process = subprocess.Popen(
            [
                sys.executable, "-m", "gunicorn", "-w", "1",
                "-k", "uvicorn.workers.UvicornWorker", "-t", "30000",
                f"--bind=127.0.0.1:{self._port}", "--log-level", "error",
                "--access-logfile", "-", "--error-logfile", "-",
                "cognee.api.client:app",
            ],
            cwd=run_dir,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=None,
            start_new_session=True,
        )
        self._client = httpx.Client(
            base_url=f"http://127.0.0.1:{self._port}",
            timeout=httpx.Timeout(30.0, read=30000.0),
            trust_env=False,
        )
        deadline = time.monotonic() + 120.0
        while time.monotonic() < deadline:
            exit_code = self._process.poll()
            if exit_code is not None:
                raise RuntimeError(
                    f"Cognee API exited with status {exit_code}; see native stderr and {run_dir / 'logs'}."
                )
            try:
                response = self._client.get("/health", timeout=2.0)
                if response.status_code == 200:
                    health = response.json()
                    if health.get("version") != "1.6.2":
                        raise RuntimeError("The Cognee API reported a release other than v1.6.2.")
                    if health.get("status") == "ready":
                        return
            except httpx.RequestError:
                pass
            time.sleep(0.1)
        raise RuntimeError(f"Cognee API did not become ready; inspect {run_dir / 'logs'}.")

    def reset(self, namespace: str) -> None:
        if self._workdir is None:
            raise RuntimeError("Start Cognee before resetting it.")
        if not namespace:
            raise ValueError("Cognee namespace must be nonempty.")
        self._namespace = None
        self._dataset = None
        self._processed = 0
        self._searchable = False
        self._stop_server()
        try:
            # Always allocate new stores, even when this namespace was used before.
            self._launch(namespace)
        except BaseException:
            self._stop_server()
            raise
        self._namespace = namespace
        self._dataset = "h2h_" + hashlib.sha256(namespace.encode("utf-8")).hexdigest()[:24]

    def _check_namespace(self, namespace: str) -> None:
        if self._client is None or self._namespace is None:
            raise RuntimeError("Start Cognee and reset a namespace before using memory.")
        if namespace != self._namespace:
            raise ValueError("Cognee can access only the namespace from its last reset().")

    @staticmethod
    def _check_run(result: object, operation: str) -> None:
        runs = [result] if isinstance(result, dict) and "status" in result else (
            list(result.values()) if isinstance(result, dict) else []
        )
        if not runs or any(
            not isinstance(run, dict)
            or run.get("status") not in ("PipelineRunCompleted", "PipelineRunAlreadyCompleted")
            for run in runs
        ):
            raise RuntimeError(f"Cognee {operation} did not report a completed blocking pipeline.")

    def ingest(self, namespace: str, sessions: list[Session]) -> IngestStats:
        self._check_namespace(namespace)
        assert self._client is not None
        stats = IngestStats()
        started = time.monotonic()
        if not sessions:
            stats.seconds = time.monotonic() - started
            return stats
        self._searchable = False
        for session in sessions:
            transcript = "\n\n".join(
                [f"Session ID: {session.session_id}", f"Session date: {session.date}"]
                + [f"{turn.role}: {turn.content}" for turn in session.turns]
            )
            digest = hashlib.sha256(session.session_id.encode("utf-8")).hexdigest()[:12]
            filename = f"{self._processed:06d}-{digest}.txt"
            response = self._client.post(
                "/api/v1/add",
                data={"datasetName": self._dataset},
                files=[("data", (filename, transcript.encode("utf-8"), "text/plain"))],
            )
            response.raise_for_status()
            self._check_run(response.json(), "add")
            response = self._client.post(
                "/api/v1/cognify", json={"datasets": [self._dataset]}
            )
            response.raise_for_status()
            self._check_run(response.json(), "cognify")
            self._processed += 1
            stats.sessions += 1
        self._searchable = True
        stats.seconds = time.monotonic() - started
        stats.notes.append("Blocking add + cognify in input order; upstream LLM call count unavailable.")
        return stats

    def retrieve(
        self, namespace: str, query: str, k: int, question_date: str | None
    ) -> list[Retrieved]:
        self._check_namespace(namespace)
        if isinstance(k, bool) or not isinstance(k, int) or k < 1:
            raise ValueError("Cognee retrieval k must be a positive integer.")
        if not self._searchable:
            return []
        assert self._client is not None
        response = self._client.post(
            "/api/v1/search",
            json={
                "query": query,
                "datasets": [self._dataset],
                "topK": k,
                "onlyContext": True,
            },
        )
        response.raise_for_status()
        rows = response.json()
        if not isinstance(rows, list):
            raise RuntimeError("Cognee search did not return its documented list of SearchResult objects.")
        retrieved = []
        for row in rows:
            # The documented single-user API returns the contexts directly;
            # access-controlled deployments wrap them in SearchResult objects.
            context = row["search_result"] if isinstance(row, dict) and "search_result" in row else row
            fragments = context if isinstance(context, list) else [context]
            for fragment in fragments:
                if fragment is None or fragment == "":
                    continue
                text = fragment if isinstance(fragment, str) else json.dumps(
                    fragment, ensure_ascii=False, sort_keys=True
                )
                retrieved.append(Retrieved(text=text))
        return retrieved

    def _stop_server(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None
        process = self._process
        if process is None:
            return
        # Cognee's default graph/vector workers are subprocesses. Signal only
        # the session created by this adapter, never a host-wide process pattern.
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=30.0)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=10.0)
        self._process = None

    def stop(self) -> None:
        self._stop_server()
        self._workdir = None
        self._environment = None
        self._port = None
        self._namespace = None
        self._dataset = None
        self._processed = 0
        self._searchable = False
        self.needs_llm = True


def build() -> MemoryAdapter:
    return CogneeAdapter()
