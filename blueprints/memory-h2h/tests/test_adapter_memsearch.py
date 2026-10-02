"""Offline checks of memsearch's documented public API and isolation contract."""

from __future__ import annotations

import importlib.metadata
import io
import json
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock


HARNESS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HARNESS))

# The core builder owns types.py. Use the supplied interface in memory only if
# that concurrent file has not landed; never create a replacement on disk.
if not (HARNESS / "h2h" / "types.py").exists():
    interface = types.ModuleType("h2h.types")
    sys.modules["h2h.types"] = interface
    exec(
        """
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

@dataclass(frozen=True)
class Turn:
    role: str
    content: str

@dataclass(frozen=True)
class Session:
    session_id: str
    date: str
    turns: tuple[Turn, ...]

@dataclass(frozen=True)
class Retrieved:
    text: str
    session_ids: tuple[str, ...] = ()
    score: float | None = None

@dataclass(frozen=True)
class ModelRoute:
    base_url: str
    model: str
    api_key_env: str = "H2H_API_KEY"

@dataclass
class IngestStats:
    sessions: int = 0
    seconds: float = 0.0
    llm_calls: int | None = None
    notes: list[str] = field(default_factory=list)

class MemoryAdapter(Protocol):
    name: str
    version: str
    needs_llm: bool
    def start(self, workdir: Path, llm: ModelRoute | None, embed: ModelRoute | None) -> None: ...
    def reset(self, namespace: str) -> None: ...
    def ingest(self, namespace: str, sessions: list[Session]) -> IngestStats: ...
    def retrieve(self, namespace: str, query: str, k: int, question_date: str | None) -> list[Retrieved]: ...
    def stop(self) -> None: ...
""",
        interface.__dict__,
    )

from h2h.adapters import memsearch
from h2h.types import ModelRoute, Session, Turn


class MemsearchAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.workdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.workdir.cleanup)
        self.requests: list[dict] = []
        self.search_rows: list[dict] = []
        patcher = mock.patch.object(memsearch.subprocess, "run", side_effect=self.fake_run)
        self.process = patcher.start()
        self.addCleanup(patcher.stop)
        self.adapter = memsearch.build()
        self.adapter.start(Path(self.workdir.name), None, None)
        self.adapter.reset("q1")
        self.addCleanup(self.adapter.stop)

    def fake_run(self, command, **kwargs):
        request = json.loads(kwargs["input"])
        self.requests.append({"command": command, "kwargs": kwargs, "request": request})
        if request["action"] == "start":
            result = {"ready": True}
        elif request["action"] == "index":
            result = {"chunks": len(request["files"])}
        elif request["action"] == "search":
            result = self.search_rows
        else:
            raise AssertionError("Unexpected subprocess operation")
        return subprocess.CompletedProcess(command, 0, json.dumps(result, ensure_ascii=False), "")

    @staticmethod
    def sessions() -> list[Session]:
        return [
            Session(
                "session/one",
                "2023/05/20 (Sat) 13:45",
                (Turn("user", "Remember café bleu.\nSecond line."), Turn("assistant", "I will remember 蓝色。")),
            ),
            Session("session-two", "2023/06/01 (Thu) 09:00", (Turn("user", "The TTL is 15 minutes."),)),
        ]

    def test_build_is_lazy_and_state_is_per_instance(self) -> None:
        self.process.reset_mock()
        other = memsearch.build()
        self.assertEqual((other.name, other.version, other.needs_llm), ("memsearch", "v0.4.21", False))
        self.process.assert_not_called()
        with self.assertRaisesRegex(RuntimeError, "start"):
            other.reset("q1")
        self.adapter.ingest("q1", self.sessions())
        self.assertEqual(len(self.requests[-1]["request"]["files"]), 2)

    def test_start_uses_only_documented_profile_parameters(self) -> None:
        call = self.requests[0]
        request = call["request"]
        self.assertEqual(set(request), {"action", "release", "paths", "milvus_uri"})
        self.assertEqual(request["action"], "start")
        self.assertEqual(request["release"], "0.4.21")
        self.assertEqual(Path(request["milvus_uri"]).name, "milvus.db")
        self.assertEqual(Path(request["paths"][0]).parent, Path(request["milvus_uri"]).parent)
        self.assertTrue(Path(request["paths"][0]).is_relative_to(Path(self.workdir.name)))
        self.assertEqual(call["command"][:3], [sys.executable, "-B", "-c"])
        self.assertFalse(call["kwargs"]["shell"])
        self.assertNotIn("env", call["kwargs"])
        self.assertTrue(call["kwargs"]["capture_output"])
        self.assertEqual(call["kwargs"]["encoding"], "utf-8")

    def test_external_embedding_route_fails_before_launch(self) -> None:
        other = memsearch.build()
        count = self.process.call_count
        route = ModelRoute("https://example.invalid/v1", "external-embedding", "SYNTHETIC_KEY_NAME")
        with self.assertRaisesRegex(ValueError, "local ONNX.*OpenAI-compatible"):
            other.start(Path(self.workdir.name), None, route)
        self.assertEqual(self.process.call_count, count)

    def test_unused_llm_route_is_not_sent_to_the_client(self) -> None:
        other = memsearch.build()
        self.addCleanup(other.stop)
        route = ModelRoute("https://example.invalid/v1", "answerer", "SYNTHETIC_KEY_NAME")
        other.start(Path(self.workdir.name), route, None)
        request = self.requests[-1]["request"]
        self.assertNotIn(route.base_url, json.dumps(request))
        self.assertNotIn(route.api_key_env, json.dumps(request))

    def test_ingest_preserves_both_roles_dates_unicode_and_supplied_order(self) -> None:
        sessions = self.sessions()
        stats = self.adapter.ingest("q1", sessions)
        request = self.requests[-1]["request"]
        self.assertEqual(set(request), {"action", "release", "paths", "milvus_uri", "files"})
        self.assertEqual(request["action"], "index")
        first, second = map(Path, request["files"])
        self.assertEqual(first.parent, Path(request["paths"][0]))
        self.assertEqual(second.parent, first.parent)
        self.assertEqual(
            first.read_text(encoding="utf-8"),
            "# Session session/one\n\nDate: 2023/05/20 (Sat) 13:45\n\n"
            "user: Remember café bleu.\nSecond line.\n\nassistant: I will remember 蓝色。\n\n",
        )
        self.assertIn("# Session session-two", second.read_text(encoding="utf-8"))
        self.assertEqual(stats.sessions, 2)
        self.assertGreaterEqual(stats.seconds, 0)
        self.assertIsNone(stats.llm_calls)
        self.assertIn("Indexed 2 chunks", stats.notes[0])

    def test_search_passes_query_and_k_without_date_rewriting_or_truncation(self) -> None:
        self.adapter.ingest("q1", self.sessions())
        files = self.requests[-1]["request"]["files"]
        full_text = "蓝色 café " * 200
        self.search_rows = [
            {"content": full_text, "source": files[0], "heading": "Session session/one", "score": 0.91},
            {"content": "The TTL is 15 minutes.", "source": files[1], "score": 0.78},
        ]
        query = 'What was remembered? $(literal) `literal` "quoted"\n下一行'
        results = self.adapter.retrieve("q1", query, 2, "2024/01/01 (Mon) 12:00")
        request = self.requests[-1]["request"]
        self.assertEqual(set(request), {"action", "release", "paths", "milvus_uri", "query", "top_k"})
        self.assertEqual((request["query"], request["top_k"]), (query, 2))
        self.assertEqual(results[0].text, full_text)
        self.assertEqual(results[0].session_ids, ("session/one",))
        self.assertEqual(results[1].session_ids, ("session-two",))
        self.assertEqual(results[0].score, 0.91)
        self.assertNotIn(query, self.requests[-1]["command"][3])

    def test_unknown_or_missing_source_does_not_invent_session_ids(self) -> None:
        self.adapter.ingest("q1", self.sessions())
        self.search_rows = [
            {"content": "Reported chunk", "source": "/synthetic/unmapped.md", "score": None},
            {"content": "Another reported chunk"},
        ]
        results = self.adapter.retrieve("q1", "query", 2, None)
        self.assertEqual([row.session_ids for row in results], [(), ()])
        self.assertEqual([row.score for row in results], [None, None])

    def test_reset_rotates_physical_store_even_for_the_same_namespace(self) -> None:
        self.adapter.ingest("q1", self.sessions())
        old = self.requests[-1]["request"]
        self.adapter.reset("q2")
        count = self.process.call_count
        self.assertEqual(self.adapter.retrieve("q2", "query", 10, None), [])
        self.assertEqual(self.process.call_count, count)
        with self.assertRaisesRegex(ValueError, "active.*namespace"):
            self.adapter.retrieve("q1", "query", 10, None)
        self.adapter.ingest("q2", self.sessions()[:1])
        new = self.requests[-1]["request"]
        self.assertNotEqual(old["milvus_uri"], new["milvus_uri"])
        self.assertNotEqual(old["paths"], new["paths"])
        self.assertEqual(len(list(Path(new["paths"][0]).glob("*.md"))), 1)
        self.adapter.reset("q2")
        self.adapter.ingest("q2", self.sessions()[:1])
        self.assertNotEqual(new["milvus_uri"], self.requests[-1]["request"]["milvus_uri"])

    def test_empty_ingestion_has_no_collection_or_search_subprocess(self) -> None:
        count = self.process.call_count
        stats = self.adapter.ingest("q1", [])
        self.assertEqual(stats.sessions, 0)
        self.assertIsNone(stats.llm_calls)
        self.assertEqual(self.adapter.retrieve("q1", "query", 10, None), [])
        self.assertEqual(self.process.call_count, count)

    def test_duplicate_ids_and_invalid_roles_fail_before_writing(self) -> None:
        session = self.sessions()[0]
        count = self.process.call_count
        with self.assertRaisesRegex(ValueError, "unique"):
            self.adapter.ingest("q1", [session, session])
        invalid = Session("invalid", "date", (Turn("system", "unsupported role"),))
        with self.assertRaisesRegex(ValueError, "user or assistant"):
            self.adapter.ingest("q1", [session, invalid])
        self.assertEqual(self.process.call_count, count)
        self.assertEqual(list(Path(self.workdir.name).rglob("*.md")), [])

    def test_client_failure_requires_reset_and_does_not_relay_output(self) -> None:
        self.process.side_effect = None
        self.process.return_value = subprocess.CompletedProcess([], 17, "synthetic-private-output", "synthetic-private-error")
        with self.assertRaisesRegex(RuntimeError, "index failed.*exit 17") as failure:
            self.adapter.ingest("q1", self.sessions())
        self.assertNotIn("synthetic-private", str(failure.exception))
        with self.assertRaisesRegex(RuntimeError, "reset"):
            self.adapter.retrieve("q1", "query", 10, None)
        self.adapter.reset("q1")
        self.assertEqual(self.adapter.retrieve("q1", "query", 10, None), [])

    def test_invalid_json_and_result_shapes_raise(self) -> None:
        self.adapter.ingest("q1", self.sessions())
        self.process.side_effect = None
        self.process.return_value = subprocess.CompletedProcess([], 0, "not JSON", "")
        with self.assertRaisesRegex(RuntimeError, "invalid JSON"):
            self.adapter.retrieve("q1", "query", 10, None)
        self.process.side_effect = self.fake_run
        self.search_rows = [{"score": 0.8}]
        with self.assertRaisesRegex(RuntimeError, "text content"):
            self.adapter.retrieve("q1", "query", 10, None)
        self.search_rows = [{"content": "body", "score": float("nan")}]
        with self.assertRaisesRegex(RuntimeError, "relevance score"):
            self.adapter.retrieve("q1", "query", 10, None)

    def test_stop_is_idempotent_and_restarting_uses_a_new_private_root(self) -> None:
        original = self.requests[0]["request"]["milvus_uri"]
        count = self.process.call_count
        self.adapter.stop()
        self.adapter.stop()
        self.assertEqual(self.process.call_count, count)
        with self.assertRaisesRegex(RuntimeError, "start"):
            self.adapter.reset("q1")
        self.adapter.start(Path(self.workdir.name), None, None)
        self.assertNotEqual(original, self.requests[-1]["request"]["milvus_uri"])

    def test_failed_start_does_not_leave_an_active_adapter(self) -> None:
        other = memsearch.build()
        self.process.side_effect = None
        self.process.return_value = subprocess.CompletedProcess([], 1, "", "")
        with self.assertRaisesRegex(RuntimeError, r"memsearch\[onnx\]==0.4.21"):
            other.start(Path(self.workdir.name), None, None)
        with self.assertRaisesRegex(RuntimeError, "start"):
            other.reset("q1")

    def run_bridge(self, request, memory, *, release="0.4.21"):
        # Execute the exact child program with a fake documented client. This
        # exercises its async API calls and close(), without launching a child,
        # importing memsearch, downloading model weights or opening Milvus.
        sdk = types.ModuleType("memsearch")
        factory = mock.Mock(return_value=memory)
        sdk.MemSearch = factory
        output, diagnostic = io.StringIO(), io.StringIO()
        with (
            mock.patch.dict(sys.modules, {"memsearch": sdk}),
            mock.patch.object(importlib.metadata, "version", return_value=release),
            mock.patch.object(sys, "stdin", io.StringIO(json.dumps(request))),
            mock.patch.object(sys, "stdout", output),
            mock.patch.object(sys, "stderr", diagnostic),
        ):
            exec(compile(self.requests[0]["command"][3], "<memsearch bridge>", "exec"), {})
        return json.loads(output.getvalue()), factory

    def test_bridge_calls_index_file_in_order_with_upstream_defaults(self) -> None:
        self.adapter.ingest("q1", self.sessions())
        request = self.requests[-1]["request"]
        memory = types.SimpleNamespace(index_file=mock.AsyncMock(side_effect=[2, 5]), close=mock.Mock())
        result, factory = self.run_bridge(request, memory)
        self.assertEqual(result, {"chunks": 7})
        factory.assert_called_once_with(
            paths=request["paths"], embedding_provider="onnx", milvus_uri=request["milvus_uri"]
        )
        self.assertEqual(memory.index_file.await_args_list, [mock.call(path) for path in request["files"]])
        memory.close.assert_called_once_with()

    def test_bridge_awaits_search_query_top_k_and_closes(self) -> None:
        request = {**self.requests[0]["request"], "action": "search", "query": "What is 蓝色?", "top_k": 3}
        rows = [{"content": "Full chunk", "source": "synthetic.md", "score": 0.87}]
        memory = types.SimpleNamespace(search=mock.AsyncMock(return_value=rows), close=mock.Mock())
        result, factory = self.run_bridge(request, memory)
        self.assertEqual(result, rows)
        memory.search.assert_awaited_once_with("What is 蓝色?", top_k=3)
        memory.close.assert_called_once_with()
        self.assertEqual(set(factory.call_args.kwargs), {"paths", "embedding_provider", "milvus_uri"})

    def test_bridge_closes_after_upstream_index_failure(self) -> None:
        request = {**self.requests[0]["request"], "action": "index", "files": ["synthetic.md"]}
        memory = types.SimpleNamespace(
            index_file=mock.AsyncMock(side_effect=RuntimeError("synthetic upstream failure")), close=mock.Mock()
        )
        with self.assertRaisesRegex(RuntimeError, "synthetic upstream failure"):
            self.run_bridge(request, memory)
        memory.close.assert_called_once_with()

    def test_bridge_checks_the_pinned_release_before_constructing_memory(self) -> None:
        memory = types.SimpleNamespace(close=mock.Mock())
        with self.assertRaisesRegex(RuntimeError, "Install memsearch"):
            self.run_bridge(self.requests[0]["request"], memory, release="0.4.20")
        memory.close.assert_not_called()


if __name__ == "__main__":
    unittest.main()
