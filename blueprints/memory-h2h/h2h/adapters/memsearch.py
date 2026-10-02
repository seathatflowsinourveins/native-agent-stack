"""memsearch v0.4.21's documented Python API, ONNX + private Milvus Lite.

The upstream client runs in a short-lived subprocess so its dependencies and
Milvus resources never enter the harness process. See memsearch.md for sources.
"""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from h2h.types import IngestStats, MemoryAdapter, ModelRoute, Retrieved, Session


class MemsearchAdapter:
    name = "memsearch"
    version = "v0.4.21"
    needs_llm = False

    # Only upstream's public client API is used in this subprocess bridge.
    # Requests contain local paths, queries and version metadata, never keys.
    _program = """
import asyncio
import contextlib
import importlib.metadata
import json
import sys

request = json.load(sys.stdin)
if importlib.metadata.version("memsearch") != request["release"]:
    raise RuntimeError("Install memsearch[onnx]==0.4.21 in this Python interpreter")

async def index_files(memory, paths):
    chunks = 0
    for path in paths:
        chunks += await memory.index_file(path)
    return {"chunks": chunks}

# Keep any dependency progress output separate from the JSON result.
with contextlib.redirect_stdout(sys.stderr):
    from memsearch import MemSearch

    memory = MemSearch(
        paths=request["paths"],
        embedding_provider="onnx",
        milvus_uri=request["milvus_uri"],
    )
    try:
        if request["action"] == "start":
            result = {"ready": True}
        elif request["action"] == "index":
            result = asyncio.run(index_files(memory, request["files"]))
        elif request["action"] == "search":
            result = asyncio.run(memory.search(request["query"], top_k=request["top_k"]))
        else:
            raise ValueError("Unknown memsearch operation")
    finally:
        memory.close()

print(json.dumps(result, ensure_ascii=False))
"""

    def __init__(self) -> None:
        self._root: Path | None = None
        self._directory: Path | None = None
        self._namespace: str | None = None
        self._sources: dict[str, str] = {}
        self._indexed = False
        self._failed = False

    def start(self, workdir: Path, llm: ModelRoute | None, embed: ModelRoute | None) -> None:
        if self._root is not None:
            raise RuntimeError("memsearch is already started; call stop() first")
        if embed is not None:
            raise ValueError(
                "memsearch's requested local ONNX profile cannot use an OpenAI-compatible "
                "embedding route; pass embed=None to keep its documented ONNX model"
            )
        # There is no generative LLM role in index_file/search with ONNX and the
        # default disabled reranker. The harness's common answerer owns llm.
        workdir = workdir.resolve()
        workdir.mkdir(mode=0o700, parents=True, exist_ok=True)
        self._root = Path(tempfile.mkdtemp(prefix="memsearch-", dir=workdir))
        bootstrap = self._root / "bootstrap"
        (bootstrap / "memory").mkdir(mode=0o700, parents=True)
        try:
            result = self._invoke(bootstrap, "start")
            if result != {"ready": True}:
                raise RuntimeError("memsearch startup returned an invalid response")
        except Exception:
            self.stop()
            raise

    def reset(self, namespace: str) -> None:
        if self._root is None:
            raise RuntimeError("Call memsearch.start() before reset()")
        directory = Path(tempfile.mkdtemp(prefix="question-", dir=self._root))
        (directory / "memory").mkdir(mode=0o700)
        # A new physical database, even when resetting the same namespace.
        self._directory = directory
        self._namespace = namespace
        self._sources.clear()
        self._indexed = False
        self._failed = False

    def ingest(self, namespace: str, sessions: list[Session]) -> IngestStats:
        directory = self._active(namespace)
        started = time.perf_counter()
        seen = set(self._sources.values())
        for session in sessions:
            if session.session_id in seen:
                raise ValueError("Session IDs must be unique within a memsearch namespace")
            seen.add(session.session_id)
            if any(turn.role not in ("user", "assistant") for turn in session.turns):
                raise ValueError("memsearch conversations require user or assistant turns")
        files: dict[str, str] = {}
        chunks = 0
        try:
            for offset, session in enumerate(sessions, len(self._sources)):
                digest = hashlib.sha256(session.session_id.encode("utf-8")).hexdigest()
                path = directory / "memory" / f"{offset:06d}-{digest}.md"
                text = f"# Session {session.session_id}\n\nDate: {session.date}\n\n"
                text += "".join(f"{turn.role}: {turn.content}\n\n" for turn in session.turns)
                with path.open("x", encoding="utf-8", newline="") as stream:
                    stream.write(text)
                files[str(path)] = session.session_id
            if files:
                result = self._invoke(directory, "index", files=list(files))
                chunks = result.get("chunks") if isinstance(result, dict) else None
                if type(chunks) is not int or chunks < 0:
                    raise RuntimeError("memsearch indexing returned an invalid chunk count")
                self._indexed = True
        except Exception:
            self._failed = True
            raise
        self._sources.update(files)
        return IngestStats(
            sessions=len(sessions),
            seconds=time.perf_counter() - started,
            llm_calls=None,  # Upstream exposes chunk counts, no LLM-call counter.
            notes=[f"Indexed {chunks} chunks with the default ONNX model; no generative LLM used."],
        )

    def retrieve(
        self, namespace: str, query: str, k: int, question_date: str | None
    ) -> list[Retrieved]:
        directory = self._active(namespace)
        if type(k) is not int or k < 1:
            raise ValueError("memsearch retrieval k must be a positive integer")
        if not self._indexed:
            # v0.4.21 reads require a collection; reset/empty ingestion has none.
            return []
        # The documented search API has no question-date parameter.
        rows = self._invoke(directory, "search", query=query, top_k=k)
        if not isinstance(rows, list) or len(rows) > k:
            raise RuntimeError("memsearch search returned an invalid result list")
        results = []
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get("content"), str):
                raise RuntimeError("memsearch search returned a result without text content")
            source = row.get("source")
            if source is not None and not isinstance(source, str):
                raise RuntimeError("memsearch search returned an invalid source path")
            score = row.get("score")
            if score is not None:
                if type(score) not in (int, float) or not math.isfinite(score):
                    raise RuntimeError("memsearch search returned an invalid relevance score")
                score = float(score)
            session_id = self._sources.get(source)
            results.append(Retrieved(row["content"], (session_id,) if session_id is not None else (), score))
        return results

    def stop(self) -> None:
        # Every child has already exited and called the documented close().
        # Leave this instance's private artifacts for the caller to clean up.
        self._root = None
        self._directory = None
        self._namespace = None
        self._sources.clear()
        self._indexed = False
        self._failed = False

    def _active(self, namespace: str) -> Path:
        if self._root is None or self._directory is None:
            raise RuntimeError("Call memsearch.start() and reset() before using memory")
        if namespace != self._namespace:
            raise ValueError("Only the active memsearch namespace is reachable; call reset()")
        if self._failed:
            raise RuntimeError("memsearch ingestion failed; reset() before using this store")
        return self._directory

    def _invoke(self, directory: Path, action: str, **arguments: Any) -> Any:
        request = {
            "action": action,
            "release": self.version.removeprefix("v"),
            "paths": [str(directory / "memory")],
            "milvus_uri": str(directory / "milvus.db"),
            **arguments,
        }
        try:
            response = subprocess.run(
                [sys.executable, "-B", "-c", self._program],
                input=json.dumps(request, ensure_ascii=False),
                cwd=directory,
                capture_output=True,
                text=True,
                encoding="utf-8",
                shell=False,
                check=False,
            )
        except OSError as exc:
            raise RuntimeError("Could not launch memsearch's Python client") from exc
        if response.returncode != 0:
            raise RuntimeError(
                f"memsearch {self.version} {action} failed (exit {response.returncode}); "
                "install memsearch[onnx]==0.4.21 and its dependencies in the harness's Python interpreter"
            )
        try:
            return json.loads(response.stdout)
        except (json.JSONDecodeError, TypeError) as exc:
            raise RuntimeError(f"memsearch {action} returned invalid JSON") from exc


def build() -> MemoryAdapter:
    return MemsearchAdapter()
