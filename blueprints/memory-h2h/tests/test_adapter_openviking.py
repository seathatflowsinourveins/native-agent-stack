"""Offline integration checks against OpenViking's tagged HTTP contracts."""

from __future__ import annotations

import importlib
import json
import os
import sys
import tempfile
import types
import unittest
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol
from unittest.mock import Mock, patch

import httpx


HARNESS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HARNESS))

# Other builders may not yet have written h2h/types.py. Keep that contingency
# entirely in this test process; never create or overwrite their interface file.
if not (HARNESS / "h2h" / "types.py").is_file():
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

    fallback = types.ModuleType("h2h.types")
    for definition in (Turn, Session, Retrieved, ModelRoute, IngestStats, MemoryAdapter):
        setattr(fallback, definition.__name__, definition)
    sys.modules["h2h.types"] = fallback

from h2h.types import ModelRoute, Session, Turn

openviking = importlib.import_module("h2h.adapters.openviking")


def ok(result: object) -> httpx.Response:
    return httpx.Response(200, json={"status": "ok", "result": result})


class OpenVikingHTTPTests(unittest.TestCase):
    def setUp(self) -> None:
        self.requests: list[httpx.Request] = []
        self.adapter = openviking.build()
        self.adapter._namespace = "question-1"
        self.adapter._process = Mock()
        self.adapter._process.poll.return_value = None

    def attach(self, handler) -> None:
        def recording_handler(request: httpx.Request) -> httpx.Response:
            self.requests.append(request)
            return handler(request)

        self.adapter._client = httpx.Client(
            base_url="http://127.0.0.1:49152",
            transport=httpx.MockTransport(recording_handler),
            trust_env=False,
        )
        self.addCleanup(self.adapter._client.close)

    def test_ingest_dates_parts_defaults_and_serial_commit_completion(self) -> None:
        task_status = iter(["pending", "running", "completed", "completed"])
        session_number = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal session_number
            if request.url.path == "/api/v1/sessions":
                session_number += 1
                return ok({"session_id": f"server-session-{session_number}"})
            if request.url.path.endswith("/messages"):
                return ok({"message_count": 1})
            if request.url.path.endswith("/commit"):
                return ok({"status": "accepted", "task_id": f"task-{session_number}"})
            return ok({"status": next(task_status)})

        self.attach(handler)
        earlier = Session("dataset-early", "2023/05/20 (Sat) 10:30", (
            Turn("user", "I moved to Albany."),
            Turn("assistant", "You moved to Albany."),
        ))
        later = Session("dataset-late", "2023/06/21 (Wed) 11:00", (Turn("user", "I moved again."),))
        with patch.object(openviking.time, "sleep"):
            stats = self.adapter.ingest("question-1", [later, earlier])
        self.assertEqual(stats.sessions, 2)
        self.assertIsNone(stats.llm_calls)
        self.assertGreaterEqual(stats.seconds, 0)
        self.assertEqual([(r.method, r.url.path) for r in self.requests], [
            ("POST", "/api/v1/sessions"),
            ("POST", "/api/v1/sessions/server-session-1/messages"),
            ("POST", "/api/v1/sessions/server-session-1/messages"),
            ("POST", "/api/v1/sessions/server-session-1/commit"),
            ("GET", "/api/v1/tasks/task-1"),
            ("GET", "/api/v1/tasks/task-1"),
            ("GET", "/api/v1/tasks/task-1"),
            ("POST", "/api/v1/sessions"),
            ("POST", "/api/v1/sessions/server-session-2/messages"),
            ("POST", "/api/v1/sessions/server-session-2/commit"),
            ("GET", "/api/v1/tasks/task-2"),
        ])
        self.assertEqual(json.loads(self.requests[1].content), {
            "role": "user",
            "parts": [{"type": "text", "text": "I moved to Albany."}],
            "created_at": "2023-05-20T10:30:00",
        })
        self.assertEqual(json.loads(self.requests[2].content), {
            "role": "assistant",
            "parts": [{"type": "text", "text": "You moved to Albany."}],
            "created_at": "2023-05-20T10:30:01",
        })
        for request in self.requests:
            self.assertEqual(dict(request.url.params), {})
            if request.url.path.endswith("/commit") or request.url.path == "/api/v1/sessions":
                self.assertEqual(json.loads(request.content), {})

    def test_noop_commit_without_task_is_valid(self) -> None:
        self.attach(lambda r: ok({"session_id": "empty"}) if r.url.path == "/api/v1/sessions"
                    else ok({"status": "skipped", "task_id": None, "archived": False}))
        stats = self.adapter.ingest("question-1", [Session("empty", "2023/05/20 (Sat) 10:30", ())])
        self.assertEqual(stats.sessions, 1)
        self.assertEqual(len(self.requests), 2)

    def test_failed_and_cancelled_commit_tasks_fail_ingestion(self) -> None:
        for status in ("failed", "cancelled"):
            with self.subTest(status=status):
                self.adapter._client = httpx.Client(
                    base_url="http://127.0.0.1:49152",
                    transport=httpx.MockTransport(lambda r: ok({"session_id": "s"})
                        if r.url.path == "/api/v1/sessions"
                        else ok({"status": "accepted", "task_id": "t"})
                        if r.url.path.endswith("/commit")
                        else ok({"status": status})),
                )
                with self.adapter._client:
                    with self.assertRaisesRegex(RuntimeError, status):
                        self.adapter.ingest("question-1", [Session("s", "2023/05/20 (Sat) 10:30", ())])

    def test_accepted_commit_requires_task_id(self) -> None:
        self.attach(lambda r: ok({"session_id": "s"}) if r.url.path == "/api/v1/sessions"
                    else ok({"status": "accepted"}))
        with self.assertRaisesRegex(RuntimeError, "task_id"):
            self.adapter.ingest("question-1", [Session("s", "2023/05/20 (Sat) 10:30", ())])

    def test_invalid_dates_and_roles_fail_before_http(self) -> None:
        self.attach(lambda r: self.fail("Invalid source data must not be ingested"))
        for session in (
            Session("s", "unknown", ()),
            Session("s", "2023/05/20 (Sat) 10:30", (Turn("system", "instruction"),)),
        ):
            with self.subTest(session=session):
                with self.assertRaises(ValueError):
                    self.adapter.ingest("question-1", [session])
        self.assertEqual(self.requests, [])

    def test_find_and_visible_reads_preserve_scores_and_default_summaries(self) -> None:
        uris = ["viking://user/default/memories/events/move.md",
                "viking://user/default/memories/.abstract.md"]

        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "POST":
                return ok({"memories": [
                    {"uri": uris[0], "score": 0.8, "abstract": "short"},
                    {"uri": uris[1], "score": 0.7, "abstract": "summary"},
                ], "resources": [], "skills": [], "total": 2})
            return ok("full visible memory" if request.url.params["uri"] == uris[0] else "directory abstract")

        self.attach(handler)
        result = self.adapter.retrieve("question-1", "Where did I move?", 2, "2023/07/01 (Sat) 00:00")
        self.assertEqual(json.loads(self.requests[0].content), {
            "query": "Where did I move?", "limit": 2,
        })
        self.assertEqual([(r.method, r.url.path) for r in self.requests], [
            ("POST", "/api/v1/search/find"),
            ("GET", "/api/v1/content/read"),
            ("GET", "/api/v1/content/read"),
        ])
        self.assertEqual([dict(r.url.params) for r in self.requests[1:]], [{"uri": u} for u in uris])
        self.assertEqual([r.text for r in result], ["full visible memory", "directory abstract"])
        self.assertEqual([r.score for r in result], [0.8, 0.7])
        self.assertEqual([r.session_ids for r in result], [(), ()])

    def test_default_find_preserves_all_native_context_types(self) -> None:
        uris = ["viking://user/default/memories/event.md", "viking://resources/item.md",
                "viking://agent/skills/example/SKILL.md"]

        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "POST":
                return ok({category: [{"uri": uri, "score": 0.5}]
                           for category, uri in zip(("memories", "resources", "skills"), uris)})
            return ok(request.url.params["uri"])

        self.attach(handler)
        retrieved = self.adapter.retrieve("question-1", "query", 3, None)
        self.assertEqual([r.text for r in retrieved], uris)
        self.assertEqual(json.loads(self.requests[0].content), {"query": "query", "limit": 3})

    def test_directory_hit_reads_documented_overview(self) -> None:
        uri = "viking://user/default/memories/events"

        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "POST":
                return ok({"memories": [{"uri": uri, "score": 0.5, "level": 1}]})
            if request.url.path == "/api/v1/content/read":
                return httpx.Response(400, json={"status": "error", "error": {
                    "code": "INVALID_ARGUMENT", "details": {"expected": "file", "actual": "directory"},
                }})
            return ok("overview")

        self.attach(handler)
        self.assertEqual(self.adapter.retrieve("question-1", "events", 1, None)[0].text, "overview")
        self.assertEqual(self.requests[-1].url.path, "/api/v1/content/overview")
        self.assertEqual(dict(self.requests[-1].url.params), {"uri": uri})

    def test_read_failures_are_not_empty_memories(self) -> None:
        self.attach(lambda r: ok({"memories": [{"uri": "viking://user/default/memories/missing.md"}]})
                    if r.method == "POST" else httpx.Response(404, json={"status": "error"}))
        with self.assertRaises(httpx.HTTPStatusError):
            self.adapter.retrieve("question-1", "missing", 1, None)
        self.assertEqual(len(self.requests), 2)

    def test_malformed_find_success_is_not_empty_recall(self) -> None:
        self.attach(lambda r: ok({"total": 0}))
        with self.assertRaisesRegex(RuntimeError, "find result"):
            self.adapter.retrieve("question-1", "query", 1, None)

    def test_namespace_guard_and_empty_recall(self) -> None:
        self.attach(lambda r: ok({"memories": []}))
        with self.assertRaisesRegex(ValueError, "namespace"):
            self.adapter.retrieve("another-question", "query", 1, None)
        with self.assertRaisesRegex(ValueError, "namespace"):
            self.adapter.ingest("another-question", [])
        self.assertEqual(self.requests, [])
        self.assertEqual(self.adapter.retrieve("question-1", "query", 1, None), [])
        self.assertEqual(self.adapter.retrieve("question-1", "query", 0, None), [])
        self.assertEqual(len(self.requests), 1)


class OpenVikingLifecycleTests(unittest.TestCase):
    def test_start_reset_and_stop_use_only_owned_process_and_fresh_private_stores(self) -> None:
        clients: list[httpx.Client] = []
        processes: list[Mock] = []
        commands: list[tuple[list[str], dict]] = []
        ready_requests: list[httpx.Request] = []
        native_client = httpx.Client

        def client_factory(**kwargs) -> httpx.Client:
            def ready(request: httpx.Request) -> httpx.Response:
                ready_requests.append(request)
                return httpx.Response(200, json={"status": "ready"})
            client = native_client(**kwargs, transport=httpx.MockTransport(ready))
            clients.append(client)
            return client

        def popen(command, **kwargs) -> Mock:
            commands.append((command, kwargs))
            process = Mock()
            process.poll.return_value = None
            processes.append(process)
            return process

        llm = ModelRoute("http://127.0.0.1:49153/v1", "common-llm", "H2H_LLM_TEST_KEY")
        embed = ModelRoute("http://127.0.0.1:49154/v1", "text-embedding-3-small", "H2H_EMBED_TEST_KEY")
        adapter = openviking.build()
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(openviking.os, "environ", {"H2H_PORT": "49152", "H2H_LLM_TEST_KEY": "synthetic-llm-key",
                                                      "H2H_EMBED_TEST_KEY": "synthetic-embed-key"}), \
                patch.object(openviking.shutil, "which", return_value="/synthetic/bin/openviking-server"), \
                patch.object(openviking.subprocess, "Popen", side_effect=popen), \
                patch.object(openviking.httpx, "Client", side_effect=client_factory):
            adapter.start(Path(directory), llm, embed)
            with self.assertRaisesRegex(ValueError, "namespace"):
                adapter.ingest("question-1", [])
            adapter.reset("question-1")
            adapter.reset("question-1")
            self.assertEqual(adapter._namespace, "question-1")
            adapter.reset("question-2")
            with self.assertRaisesRegex(ValueError, "namespace"):
                adapter.ingest("question-1", [])
            adapter.stop()
            adapter.stop()
            stores = []
            for command, kwargs in commands:
                config_path = Path(command[2])
                config_text = config_path.read_text(encoding="utf-8")
                config = json.loads(config_text)
                stores.append(config["storage"]["workspace"])
                self.assertEqual(command, ["/synthetic/bin/openviking-server", "--config", str(config_path),
                                           "--host", "127.0.0.1", "--port", "49152"])
                self.assertEqual(kwargs["cwd"], config_path.parent)
                self.assertTrue(config_path.is_relative_to(Path(directory)))
                self.assertEqual(config["storage"], {"workspace": str(config_path.parent / "data")})
                self.assertEqual(config["vlm"], {"provider": "openai", "model": llm.model,
                    "api_base": llm.base_url, "api_key": "${H2H_LLM_TEST_KEY}"})
                self.assertEqual(config["embedding"], {"dense": {"provider": "openai", "model": embed.model,
                    "api_base": embed.base_url, "api_key": "${H2H_EMBED_TEST_KEY}"}})
                self.assertEqual(set(config), {"storage", "vlm", "embedding"})
                self.assertNotIn("synthetic-llm-key", config_text)
                self.assertNotIn("synthetic-embed-key", config_text)
                self.assertNotIn("env", kwargs)  # Keys are inherited, never serialized into argv.
                self.assertEqual(kwargs["stdin"], openviking.subprocess.DEVNULL)
            self.assertEqual(len(stores), 4)
            self.assertEqual(len(set(stores)), 4)
            self.assertTrue(all(c.is_closed for c in clients))
            self.assertTrue(all(r.method == "GET" and r.url.path == "/ready" for r in ready_requests))
            for process in processes:
                process.terminate.assert_called_once_with()
                process.wait.assert_called_once_with(timeout=10.0)
                process.kill.assert_not_called()

    def test_start_rejects_missing_routes_port_and_invalid_key_names_before_launch(self) -> None:
        route = ModelRoute("http://127.0.0.1:49153/v1", "model")
        bad_name = ModelRoute(route.base_url, route.model, "KEY-with-punctuation")
        for llm, embed, environment in (
            (None, route, {"H2H_PORT": "49152", "H2H_API_KEY": "synthetic"}),
            (route, None, {"H2H_PORT": "49152", "H2H_API_KEY": "synthetic"}),
            (route, route, {"H2H_API_KEY": "synthetic"}),
            (route, route, {"H2H_PORT": "invalid", "H2H_API_KEY": "synthetic"}),
            (route, route, {"H2H_PORT": "65536", "H2H_API_KEY": "synthetic"}),
            (bad_name, route, {"H2H_PORT": "49152", "H2H_API_KEY": "synthetic"}),
        ):
            with self.subTest(llm=llm, embed=embed, port=environment.get("H2H_PORT")), \
                    patch.object(openviking.os, "environ", environment), \
                    patch.object(openviking.subprocess, "Popen") as popen:
                with self.assertRaises(ValueError):
                    openviking.build().start(Path("/synthetic/unused"), llm, embed)
                popen.assert_not_called()

    def test_missing_install_does_not_install_or_launch(self) -> None:
        route = ModelRoute("http://127.0.0.1:49153/v1", "model")
        with patch.object(openviking.os, "environ", {"H2H_PORT": "49152", "H2H_API_KEY": "synthetic"}), \
                patch.object(openviking.shutil, "which", return_value=None), \
                patch.object(openviking.subprocess, "Popen") as popen:
            with self.assertRaisesRegex(RuntimeError, "openviking==0.4.22"):
                openviking.build().start(Path("/synthetic/unused"), route, route)
            popen.assert_not_called()

    def test_startup_exit_cleans_up_and_remains_restartable(self) -> None:
        route = ModelRoute("http://127.0.0.1:49153/v1", "model")
        process = Mock()
        process.poll.return_value = 1
        client = Mock()
        adapter = openviking.build()
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(openviking.os, "environ", {"H2H_PORT": "49152", "H2H_API_KEY": "synthetic"}), \
                patch.object(openviking.shutil, "which", return_value="/synthetic/openviking-server"), \
                patch.object(openviking.subprocess, "Popen", return_value=process), \
                patch.object(openviking.httpx, "Client", return_value=client):
            with self.assertRaisesRegex(RuntimeError, "startup"):
                adapter.start(Path(directory), route, route)
        client.get.assert_not_called()
        client.close.assert_called_once_with()
        process.terminate.assert_not_called()
        process.wait.assert_called_once_with(timeout=10.0)
        self.assertIsNone(adapter._workdir)
        self.assertIsNone(adapter._process)
        self.assertIsNone(adapter._client)


if __name__ == "__main__":
    unittest.main()
