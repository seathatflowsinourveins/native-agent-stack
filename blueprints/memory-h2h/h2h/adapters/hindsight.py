"""Hindsight v0.10.2's self-hosted HTTP API; provenance is in hindsight.md."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

from h2h.types import IngestStats, MemoryAdapter, ModelRoute, Retrieved, Session


def _timestamp(value: str) -> datetime:
    """Translate the dataset's date to the API's ISO timestamp, retaining time."""
    cleaned = re.sub(r"\s*\([A-Za-z]+\)", "", value).strip()
    try:
        parsed = datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
    except ValueError:
        for fmt in ("%Y/%m/%d %H:%M", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d"):
            try:
                parsed = datetime.strptime(cleaned, fmt)
                break
            except ValueError:
                continue
        else:
            raise ValueError(f"Unsupported Hindsight benchmark date: {value!r}") from None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed


def _route_environment(route: ModelRoute, *, embedding: bool = False) -> dict[str, str]:
    parsed = urlsplit(route.base_url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Hindsight requires an HTTP(S) OpenAI-compatible base URL without credentials")
    if not route.model:
        raise ValueError("Hindsight requires a model name for each supplied route")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", route.api_key_env):
        raise ValueError("ModelRoute.api_key_env must be an environment variable name")
    if route.api_key_env not in os.environ:
        raise RuntimeError(f"Hindsight route requires the environment variable {route.api_key_env}")
    prefix = "HINDSIGHT_API_EMBEDDINGS_OPENAI" if embedding else "HINDSIGHT_API_LLM"
    return {
        ("HINDSIGHT_API_EMBEDDINGS_PROVIDER" if embedding else "HINDSIGHT_API_LLM_PROVIDER"): "openai",
        f"{prefix}_MODEL": route.model,
        f"{prefix}_BASE_URL": route.base_url,
        f"{prefix}_API_KEY": os.environ[route.api_key_env],
    }


class HindsightAdapter:
    name = "hindsight"
    version = "v0.10.2"
    needs_llm = True

    def __init__(self) -> None:
        self._client: Any = None
        self._process: subprocess.Popen[bytes] | None = None
        self._container: str | None = None
        self._banks: dict[str, str] = {}
        self._sources: dict[str, dict[str, str]] = {}

    def start(self, workdir: Path, llm: ModelRoute | None, embed: ModelRoute | None) -> None:
        if self._container is not None:
            raise RuntimeError("Hindsight adapter is already started")
        if llm is None:
            raise ValueError("Hindsight retain and default consolidation require an LLM route")
        if sys.platform != "linux":
            raise RuntimeError("This Hindsight launch route requires Docker host networking on Linux")
        try:
            port = int(os.environ["H2H_PORT"])
        except (KeyError, ValueError):
            raise ValueError("H2H_PORT must specify a loopback API port") from None
        if not 1 <= port <= 65535:
            raise ValueError("H2H_PORT must be between 1 and 65535")
        docker = shutil.which("docker")
        if docker is None:
            raise RuntimeError("Docker is required for the pinned Hindsight API image")

        settings = {
            "HINDSIGHT_API_HOST": "127.0.0.1",
            "HINDSIGHT_API_PORT": str(port),
            **_route_environment(llm),
        }
        if embed is not None:
            settings.update(_route_environment(embed, embedding=True))
        secret_environment = {key: settings.pop(key) for key in tuple(settings) if key.endswith("_API_KEY")}

        # Hindsight's CLI and eval allocator also check availability by binding.
        # This avoids accepting another process's readiness response on this port.
        try:
            with socket.socket() as reservation:
                reservation.bind(("127.0.0.1", port))
        except OSError:
            raise RuntimeError("H2H_PORT is unavailable; refusing to start Hindsight on an occupied port") from None

        # Only the private pg0 directory is mounted; no host .env enters the image.
        run_id = uuid4().hex
        run_dir = workdir.resolve() / f"hindsight-{run_id}"
        run_dir.mkdir(mode=0o700, parents=True)
        pg_dir = run_dir / "pg0"
        pg_dir.mkdir(mode=0o700)
        if pg_dir.stat().st_uid != 1000:
            raise RuntimeError(
                "Hindsight's documented bind mount requires UID 1000 ownership; "
                "run this adapter as UID 1000 (see hindsight.md)"
            )
        if ":" in str(pg_dir):
            raise ValueError("Hindsight's Docker bind-mount path cannot contain a colon")

        import httpx

        self._client = httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=900.0, trust_env=False)
        command = [
            docker, "run", "--rm", "--name", f"h2h-hindsight-{run_id}", "--network", "host",
            "--interactive", "--entrypoint", "/app/api/.venv/bin/python",
        ]
        for key in settings:
            command.extend(["--env", key])
        # Docker persists --env values in container metadata. Keep API keys on
        # stdin instead, then exec the unchanged upstream entrypoint in memory.
        bootstrap = (
            "import json, os, sys\n"
            "os.environ.update(json.load(sys.stdin))\n"
            "os.execv('/app/start-all.sh', ['/app/start-all.sh'])\n"
        )
        command.extend([
            "--volume", f"{pg_dir}:/home/hindsight/.pg0", "ghcr.io/vectorize-io/hindsight-api:0.10.2",
            "-c", bootstrap,
        ])
        child_environment = os.environ.copy()
        child_environment.update(settings)
        try:
            self._process = subprocess.Popen(
                command, cwd=run_dir, env=child_environment,
                stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            self._container = f"h2h-hindsight-{run_id}"
            if self._process.stdin is None:
                raise RuntimeError("Hindsight's credential transport requires a subprocess stdin pipe")
            self._process.stdin.write(json.dumps(secret_environment).encode("utf-8"))
            self._process.stdin.close()
            deadline = time.monotonic() + 300.0
            while time.monotonic() < deadline:
                if self._process.poll() is not None:
                    raise RuntimeError("The pinned Hindsight API container exited during startup")
                try:
                    response = self._client.get("/health", timeout=5.0)
                    if response.status_code == 200:
                        return
                except httpx.RequestError:
                    pass
                time.sleep(1.0)
            raise TimeoutError("Hindsight API did not become ready within 300 seconds")
        except BaseException:
            self.stop()
            raise

    def _http(self) -> Any:
        if self._client is None:
            raise RuntimeError("Hindsight adapter has not been started")
        if self._process is not None and self._process.poll() is not None:
            raise RuntimeError("The Hindsight API container has exited")
        return self._client

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        response = self._http().request(method, path, **kwargs)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError("Hindsight returned an invalid JSON response")
        return payload

    def _bank(self, namespace: str) -> str:
        self._http()
        if namespace not in self._banks:
            raise RuntimeError("Call Hindsight.reset(namespace) before using a namespace")
        return self._banks[namespace]

    def reset(self, namespace: str) -> None:
        self._http()
        previous = self._banks.get(namespace)
        if previous is not None:
            response = self._http().request("DELETE", f"/v1/default/banks/{previous}")
            if response.status_code != 404:
                response.raise_for_status()
                if response.json().get("success") is not True:
                    raise RuntimeError("Hindsight did not confirm bank deletion")
            del self._banks[namespace]
            del self._sources[previous]
        # A fresh identity also prevents old in-flight work from reaching this bank.
        bank = f"h2h-{uuid4().hex}"
        self._request("PUT", f"/v1/default/banks/{bank}", json={})
        self._banks[namespace] = bank
        self._sources[bank] = {}

    def _wait_settled(self, bank: str) -> None:
        """Use the real-model upstream eval's two-quiet-poll completion rule."""
        deadline = time.monotonic() + 900.0
        quiet_polls = 0
        path = f"/v1/default/banks/{bank}/operations"
        while time.monotonic() < deadline:
            for status in ("failed", "cancelled"):
                if self._request("GET", path, params={"status": status}, timeout=5.0)["total"]:
                    raise RuntimeError(f"Hindsight bank {bank} has {status} background operations")
            busy = False
            for status in ("pending", "processing"):
                if self._request("GET", path, params={"status": status}, timeout=5.0)["total"]:
                    busy = True
            quiet_polls = 0 if busy else quiet_polls + 1
            if quiet_polls >= 2:
                return
            time.sleep(1.0)
        raise TimeoutError("Hindsight background operations did not settle within 900 seconds")

    def ingest(self, namespace: str, sessions: list[Session]) -> IngestStats:
        bank = self._bank(namespace)
        ordered = sorted(((_timestamp(session.date), i, session) for i, session in enumerate(sessions)), key=lambda v: (v[0], v[1]))
        started = time.perf_counter()
        count = 0
        for date, _, session in ordered:
            # Distinct documents preserve repeated dataset session IDs instead of upserting them away.
            document = uuid4().hex
            item = {
                "content": json.dumps([{"role": turn.role, "content": turn.content} for turn in session.turns], ensure_ascii=False),
                "timestamp": date.isoformat(),
                "document_id": document,
                "metadata": {"session_id": session.session_id, "session_date": session.date},
            }
            payload = self._request("POST", f"/v1/default/banks/{bank}/memories", json={"items": [item]})
            if payload.get("success") is not True or payload.get("async") is not False or payload.get("items_count") != 1:
                raise RuntimeError("Hindsight did not confirm synchronous retention of the session")
            self._sources[bank][document] = session.session_id
            count += 1
        if count:
            self._wait_settled(bank)
        return IngestStats(
            sessions=count, seconds=time.perf_counter() - started, llm_calls=None,
            notes=["Retain reports extraction token usage, not an LLM call count; default background work is settled."],
        )

    def retrieve(self, namespace: str, query: str, k: int, question_date: str | None) -> list[Retrieved]:
        bank = self._bank(namespace)
        if k < 0:
            raise ValueError("k must be non-negative")
        if k == 0:
            return []
        body = {"query": query}
        if question_date is not None:
            body["query_timestamp"] = _timestamp(question_date).isoformat()
        payload = self._request("POST", f"/v1/default/banks/{bank}/memories/recall", json=body)
        entity_states = payload.get("entities") or {}
        retrieved = []
        for result in payload["results"][:k]:
            # Preserve dates, types and default entity data for the common answerer.
            text_payload = dict(result)
            associated = {name: entity_states[name] for name in result.get("entities") or [] if name in entity_states}
            if associated:
                text_payload["entity_states"] = associated
            source = (result.get("metadata") or {}).get("session_id")
            if not source:
                source = self._sources[bank].get(result.get("document_id"))
            score = (result.get("scores") or {}).get("final")
            retrieved.append(Retrieved(
                text=json.dumps(text_payload, ensure_ascii=False),
                session_ids=(source,) if source else (),
                score=float(score) if score is not None else None,
            ))
        return retrieved

    def stop(self) -> None:
        if self._container is not None:
            def stop_owned() -> subprocess.CompletedProcess[str]:
                return subprocess.run(
                    ["docker", "stop", "-t", "30", self._container],
                    stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=45,
                )

            result = stop_owned()
            if result.returncode:
                missing = f"Error response from daemon: No such container: {self._container}"
                if (
                    getattr(result, "stderr", "").strip() == missing
                    and self._process is not None and self._process.poll() is None
                ):
                    # A launch CLI still pulling the image could create it later.
                    self._process.terminate()
                    self._process.wait(timeout=45)
                    result = stop_owned()
                confirmed_absent = (
                    getattr(result, "stderr", "").strip() == missing
                    and self._process is not None and self._process.poll() is not None
                )
                if result.returncode and not confirmed_absent:
                    raise RuntimeError("Could not stop the Hindsight container owned by this adapter")
            if self._process is not None:
                self._process.wait(timeout=45)
            self._container = None
            self._process = None
        if self._client is not None:
            self._client.close()
            self._client = None
        self._banks.clear()
        self._sources.clear()


def build() -> MemoryAdapter:
    return HindsightAdapter()
