"""Offline integration fixtures for the pinned observation/search contracts.

Docker, sockets, filesystem creation and HTTP transport are stubbed. These are
request-shape checks, not upstream tests or evidence of a running memory system.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import importlib.util
import itertools
import json
import os
from pathlib import Path
import subprocess
import sys
from types import ModuleType
from typing import Protocol
import unittest
from unittest.mock import MagicMock, patch
import uuid

import httpx


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    from h2h.types import ModelRoute, Session, Turn
except ModuleNotFoundError as exc:
    if exc.name != "h2h.types":
        raise
    # Local copy of the fixed interface, used only while the core builder is
    # creating types.py. No substitute file is created in another owner's path.
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

    local_types = ModuleType("h2h.types")
    for name in ("Turn", "Session", "Retrieved", "ModelRoute", "IngestStats", "MemoryAdapter"):
        setattr(local_types, name, globals()[name])
    sys.modules["h2h.types"] = local_types

from h2h.adapters import agentmemory


HTTP_CLIENT = httpx.Client


class AgentMemoryAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.requests: list[httpx.Request] = []
        self.clients: list[httpx.Client] = []
        self.errors: dict[str, tuple[int, object]] = {}
        self.search_body: object = {"format": "full", "results": []}
        self.health_version = "0.9.29"
        self.environment = {
            "PATH": "/usr/bin", "H2H_PORT": "8310",
            "H2H_API_KEY": "synthetic-fixture-key",
            "EMBEDDING_PROVIDER": "local", "BM25_WEIGHT": "0.99",
            "AGENTMEMORY_AUTO_COMPRESS": "true",
            "AGENTMEMORY_III_CONFIG": "/unrelated/config.yaml",
            "ANTHROPIC_API_KEY": "unrelated-fixture-key",
        }
        patches = {
            "environ": patch.dict(os.environ, self.environment, clear=True),
            "mkdir": patch.object(Path, "mkdir", autospec=True),
            "write": patch.object(Path, "write_text", autospec=True),
            "temp": patch.object(agentmemory.tempfile, "mkdtemp"),
            "uuid": patch.object(agentmemory.uuid, "uuid4"),
            "socket": patch.object(agentmemory.socket, "socket"),
            "popen": patch.object(agentmemory.subprocess, "Popen"),
            "run": patch.object(agentmemory.subprocess, "run"),
            "client": patch.object(agentmemory.httpx, "Client", side_effect=self._client),
            "sleep": patch.object(agentmemory.time, "sleep"),
        }
        self.mocks = {name: self.enterContext(patcher) for name, patcher in patches.items()}
        generation_ids = itertools.count(1)
        self.mocks["temp"].side_effect = lambda **kw: str(Path(kw["dir"]) / f"fixture-{next(generation_ids)}")
        container_ids = itertools.count(1)
        self.mocks["uuid"].side_effect = lambda: uuid.UUID(int=next(container_ids))
        self.mocks["popen"].side_effect = self._process
        self.mocks["run"].return_value.returncode = 0
        self.adapter = agentmemory.build()
        self.addCleanup(self.adapter.stop)

    @staticmethod
    def _process(*args: object, **kwargs: object) -> MagicMock:
        process = MagicMock()
        process.poll.return_value = None
        process.wait.return_value = 0
        return process

    def _client(self, **kwargs: object) -> httpx.Client:
        client = HTTP_CLIENT(**kwargs, transport=httpx.MockTransport(self._http))
        self.clients.append(client)
        return client

    def _http(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        if path in self.errors:
            status, body = self.errors[path]
            return httpx.Response(status, json=body)
        if path == "/agentmemory/health":
            return httpx.Response(200, json={"service": "agentmemory", "version": self.health_version})
        if path == "/agentmemory/observe":
            return httpx.Response(201, json={"observationId": f"obs-{len(self.requests)}"})
        if path == "/agentmemory/search":
            return httpx.Response(200, json=self.search_body)
        raise AssertionError(f"Undocumented request: {request.method} {path}")

    def _start(self, llm: ModelRoute | None = None, embed: ModelRoute | None = None) -> None:
        self.adapter.start(Path("/tmp/h2h-agentmemory-fixture"), llm, embed)

    def _ready(self) -> None:
        self._start()
        self.adapter.reset("question-1")
        self.requests.clear()

    @staticmethod
    def _session(sid: str = "s-1", content: str = "My bike is blue.") -> Session:
        return Session(sid, "2023/05/20 (Sat) 10:00", (Turn("user", content), Turn("assistant", "Recorded.")))

    def test_build_and_import_do_not_start_or_connect(self) -> None:
        self.assertEqual((self.adapter.name, self.adapter.version, self.adapter.needs_llm), ("agentmemory", "v0.9.29", False))
        spec = importlib.util.spec_from_file_location("agentmemory_import_fixture", agentmemory.__file__)
        assert spec is not None and spec.loader is not None
        spec.loader.exec_module(importlib.util.module_from_spec(spec))
        self.mocks["client"].assert_not_called()
        self.mocks["popen"].assert_not_called()
        self.mocks["run"].assert_not_called()

    def test_start_uses_local_pinned_image_private_mounts_and_loopback_health(self) -> None:
        self._start()
        args, kwargs = self.mocks["popen"].call_args
        command = args[0]
        self.assertEqual(command[:7], ["docker", "run", "--rm", "--pull", "never", "--no-healthcheck", "--name"])
        self.assertEqual(command[command.index("--network") + 1], "host")
        self.assertIn("type=bind,source=/tmp/h2h-agentmemory-fixture/fixture-1/data,target=/data", command)
        self.assertIn("type=bind,source=/tmp/h2h-agentmemory-fixture/fixture-1/iii-config.yaml,target=/opt/agentmemory/iii-config.yaml,readonly", command)
        self.assertEqual(command[-7:], ["agentmemory-h2h:0.9.29", "--", "agentmemory", "--port", "8310", "--data-dir", "/data"])
        self.assertEqual(command[command.index("--entrypoint") + 1], "/usr/bin/tini")
        self.assertEqual(kwargs["env"]["DOCKER_CONFIG"], "/tmp/h2h-agentmemory-fixture/docker-config")
        self.assertNotIn("HOME", kwargs["env"])
        self.assertEqual(str(self.requests[0].url), "http://127.0.0.1:8310/agentmemory/health")
        self.assertEqual(self.requests[0].method, "GET")

    def test_engine_config_relocates_only_transport_and_retains_native_defaults(self) -> None:
        self._start()
        config = self.mocks["write"].call_args.args[1]
        self.assertIn("name: iii-worker-manager\n    config:\n      port: 54333\n      host: 127.0.0.1", config)
        self.assertIn("name: iii-http\n    config:\n      port: 8310\n      host: 127.0.0.1", config)
        self.assertIn("name: iii-stream\n    config:\n      port: 8311\n      host: 127.0.0.1", config)
        self.assertIn("default_timeout: 180000", config)
        self.assertIn("sampling_ratio: 0.1", config)
        self.assertIn("logs_console_output: false", config)
        self.assertIn("store_method: file_based", config)
        self.assertIn("file_path: ./data/state_store.db", config)
        self.assertIn("file_path: ./data/stream_store", config)
        self.assertNotIn("synthetic-fixture-key", config)
        bind_calls = self.mocks["socket"].return_value.__enter__.return_value.bind.call_args_list
        self.assertEqual([call.args[0] for call in bind_calls], [("127.0.0.1", p) for p in (8310, 8311, 8312, 54333)])

    def test_local_unix_docker_socket_is_forwarded_without_ambient_context(self) -> None:
        os.environ["DOCKER_HOST"] = "unix:///run/user/1000/docker.sock"
        os.environ["DOCKER_CONTEXT"] = "unrelated-remote-context"
        self._start()
        env = self.mocks["popen"].call_args.kwargs["env"]
        self.assertEqual(env["DOCKER_HOST"], "unix:///run/user/1000/docker.sock")
        self.assertNotIn("DOCKER_CONTEXT", env)

    def test_remote_or_malformed_docker_hosts_fail_before_launch(self) -> None:
        for host in (
            "tcp://remote.example:2376", "tcp://127.0.0.1:2375",
            "ssh://user@remote.example", "npipe:////./pipe/docker_engine",
            "unix://relative/socket", "unix:relative", "unix:///",
            "unix:///tmp/docker.sock?endpoint=remote", "unix:///tmp/docker.sock#fragment",
            "unix:///tmp/docker.sock\n",
        ):
            with self.subTest(host=host), patch.dict(os.environ, {"DOCKER_HOST": host}):
                with self.assertRaisesRegex(ValueError, "local absolute Unix socket"):
                    self._start()
        self.mocks["popen"].assert_not_called()
        self.mocks["run"].assert_not_called()
        self.assertEqual(self.requests, [])

    def test_non_linux_host_fails_before_launch(self) -> None:
        with patch.object(sys, "platform", "darwin"):
            with self.assertRaisesRegex(RuntimeError, "Linux Docker host networking"):
                self._start()
        self.mocks["popen"].assert_not_called()
        self.assertEqual(self.requests, [])

    def test_separate_base_urls_same_key_reference_and_defaults_only(self) -> None:
        self._start(
            ModelRoute("http://127.0.0.1:8300/v1/", "fixture-chat"),
            ModelRoute("http://127.0.0.1:8301/v1", "text-embedding-3-small"),
        )
        command = self.mocks["popen"].call_args.args[0]
        env = self.mocks["popen"].call_args.kwargs["env"]
        self.assertEqual(env["OPENAI_BASE_URL"], "http://127.0.0.1:8300/v1")
        self.assertEqual(env["OPENAI_EMBEDDING_BASE_URL"], "http://127.0.0.1:8301/v1")
        self.assertEqual(env["OPENAI_MODEL"], "fixture-chat")
        self.assertEqual(env["OPENAI_EMBEDDING_MODEL"], "text-embedding-3-small")
        self.assertEqual(env["EMBEDDING_PROVIDER"], "openai")
        for name in ("OPENAI_API_KEY", "OPENAI_EMBEDDING_API_KEY"):
            self.assertEqual(env[name], "synthetic-fixture-key")
            self.assertIn(name, command)
        self.assertNotIn("synthetic-fixture-key", " ".join(command))
        for name in ("BM25_WEIGHT", "AGENTMEMORY_AUTO_COMPRESS", "AGENTMEMORY_III_CONFIG", "ANTHROPIC_API_KEY"):
            self.assertNotIn(name, env)

    def test_embedding_only_keeps_chat_provider_key_absent(self) -> None:
        self._start(embed=ModelRoute("http://127.0.0.1:8301/v1", "text-embedding-3-small"))
        env = self.mocks["popen"].call_args.kwargs["env"]
        self.assertIn("OPENAI_EMBEDDING_API_KEY", env)
        self.assertNotIn("OPENAI_API_KEY", env)
        self.assertNotIn("OPENAI_API_KEY_FOR_LLM", env)

    def test_distinct_key_references_fail_before_launch(self) -> None:
        with self.assertRaisesRegex(ValueError, "#1435"):
            self._start(ModelRoute("http://localhost:8300/v1", "chat", "CHAT_KEY"), ModelRoute("http://localhost:8301/v1", "text-embedding-3-small", "EMBED_KEY"))
        self.mocks["popen"].assert_not_called()

    def test_custom_embedding_width_is_required_and_forwarded_without_probe(self) -> None:
        embed = ModelRoute("http://localhost:8301/v1", "custom-embedding")
        with self.assertRaisesRegex(ValueError, "#1373"):
            self._start(embed=embed)
        self.mocks["popen"].assert_not_called()
        os.environ["OPENAI_EMBEDDING_DIMENSIONS"] = "4096"
        self._start(embed=embed)
        self.assertEqual(self.mocks["popen"].call_args.kwargs["env"]["OPENAI_EMBEDDING_DIMENSIONS"], "4096")
        self.assertTrue(all(r.url.path == "/agentmemory/health" for r in self.requests))

    def test_invalid_configuration_fails_without_requests_or_processes(self) -> None:
        for port in ("", "invalid", "1023", "19513", "65536"):
            with self.subTest(port=port), patch.dict(os.environ, {"H2H_PORT": port}):
                with self.assertRaises(ValueError):
                    self._start()
        for route in (
            ModelRoute("http://user:password@localhost:8300/v1", "chat"),
            ModelRoute("http://localhost:8300/v1?key=secret", "chat"),
            ModelRoute("file:///tmp/model", "chat"),
            ModelRoute("http://localhost:8300/v1", ""),
            ModelRoute("http://localhost:8300/v1", "chat", "missing-key"),
            ModelRoute("http://localhost:8300/v1", "chat", "ABSENT_KEY"),
        ):
            with self.subTest(route=route), self.assertRaises(ValueError):
                self._start(llm=route)
        self.mocks["popen"].assert_not_called()
        self.assertEqual(self.requests, [])

    def test_occupied_port_fails_without_querying_an_existing_service(self) -> None:
        self.mocks["socket"].return_value.__enter__.return_value.bind.side_effect = OSError("occupied")
        with self.assertRaisesRegex(RuntimeError, "unused loopback port"):
            self._start()
        self.mocks["popen"].assert_not_called()
        self.assertEqual(self.requests, [])

    def test_health_pin_mismatch_stops_only_the_owned_container(self) -> None:
        self.health_version = "0.9.30"
        with self.assertRaisesRegex(RuntimeError, "pinned version"):
            self._start()
        started = self.mocks["popen"].call_args.args[0]
        owned = started[started.index("--name") + 1]
        self.assertEqual(self.mocks["run"].call_args.args[0], ["docker", "stop", "--timeout", "20", owned])
        self.assertTrue(self.clients[0].is_closed)

    def test_observe_transmits_full_role_labeled_sessions_and_original_dates_in_order(self) -> None:
        self._ready()
        first = self._session(content="Long conversation " + "x" * 800)
        second = Session("s-2", "2022/01/01 (Sat) 09:00", (Turn("user", "Earlier date supplied second."),))
        stats = self.adapter.ingest("question-1", [first, second])
        self.assertEqual(stats.sessions, 2)
        self.assertGreaterEqual(stats.seconds, 0.0)
        self.assertIsNone(stats.llm_calls)
        self.assertTrue(any("400" in note for note in stats.notes))
        self.assertEqual([r.url.path for r in self.requests], ["/agentmemory/observe", "/agentmemory/observe"])
        payloads = [json.loads(r.content) for r in self.requests]
        self.assertEqual(payloads[0], {
            "hookType": "prompt_submit", "sessionId": "s-1", "project": "memory-h2h",
            "cwd": "/data", "timestamp": first.date,
            "data": {"prompt": f"user: {first.turns[0].content}\nassistant: Recorded."},
        })
        self.assertEqual(payloads[1]["sessionId"], "s-2")
        self.assertEqual(payloads[1]["timestamp"], second.date)
        self.assertTrue(all(r.method == "POST" and r.headers["Content-Type"] == "application/json" for r in self.requests))

    def test_observe_checks_application_errors_even_with_http_201(self) -> None:
        self._ready()
        self.errors["/agentmemory/observe"] = (201, {"success": False, "error": "Session observation limit reached"})
        with self.assertRaisesRegex(RuntimeError, "failed response"):
            self.adapter.ingest("question-1", [self._session()])

    def test_observe_requires_an_ack_and_rejects_http_failures(self) -> None:
        self._ready()
        for status, body, error in ((201, {"deduplicated": True}, RuntimeError), (400, {"error": "invalid"}, httpx.HTTPStatusError)):
            with self.subTest(status=status):
                self.errors["/agentmemory/observe"] = (status, body)
                with self.assertRaises(error):
                    self.adapter.ingest("question-1", [self._session()])

    def test_invalid_sessions_fail_before_partial_ingestion(self) -> None:
        self._ready()
        for sessions in (
            [self._session(), self._session()],
            [Session(" ", "date", ())],
            [Session(" s ", "date", ())],
            [Session("s", "", ())],
            [Session("s", "date", (Turn("system", "unsupported"),))],
        ):
            with self.subTest(sessions=sessions), self.assertRaises(ValueError):
                self.adapter.ingest("question-1", sessions)
        self.assertEqual(self.requests, [])
        self.adapter.ingest("question-1", [self._session()])
        self.requests.clear()
        with self.assertRaises(ValueError):
            self.adapter.ingest("question-1", [self._session()])
        self.assertEqual(self.requests, [])

    def test_search_uses_default_full_format_and_keeps_returned_text_and_provenance(self) -> None:
        self._ready()
        observation = {"id": "obs-1", "sessionId": "s-1", "timestamp": "original session date", "title": "prompt_submit", "facts": ["A fact"], "narrative": "A blue bicycle — café", "concepts": ["bike"]}
        self.search_body = {"format": "full", "results": [{"observation": observation, "sessionId": "s-1", "score": 0.87}], "truncated": False}
        results = self.adapter.retrieve("question-1", "What colour was the bike?", 5, "2023/06/01")
        self.assertEqual(json.loads(self.requests[0].content), {"query": "What colour was the bike?", "limit": 5})
        self.assertEqual(self.requests[0].url.path, "/agentmemory/search")
        self.assertEqual(json.loads(results[0].text), observation)
        self.assertIn("café", results[0].text)
        self.assertEqual(results[0].session_ids, ("s-1",))
        self.assertEqual(results[0].score, 0.87)
        self.assertEqual(len(self.requests), 1)

    def test_search_empty_and_missing_provenance_are_not_invented(self) -> None:
        self._ready()
        self.assertEqual(self.adapter.retrieve("question-1", "query", 5, None), [])
        self.search_body = {"results": [{"observation": {"narrative": "returned"}}]}
        result = self.adapter.retrieve("question-1", "query", 5, None)[0]
        self.assertEqual(result.session_ids, ())
        self.assertIsNone(result.score)

    def test_search_validates_limits_and_rejects_malformed_responses(self) -> None:
        self._ready()
        for k in (0, 101, True, 1.5):
            with self.subTest(k=k), self.assertRaises(ValueError):
                self.adapter.retrieve("question-1", "query", k, None)
        self.assertEqual(self.requests, [])
        for body in ({}, {"results": {}}, {"results": [{}]}, {"results": [{"observation": {}, "score": True}]}, {"results": [{"observation": {}, "score": "0.5"}]}):
            with self.subTest(body=body), self.assertRaises(RuntimeError):
                self.search_body = body
                self.adapter.retrieve("question-1", "query", 5, None)

    def test_reset_replaces_container_store_and_allows_same_session_id_again(self) -> None:
        self._ready()
        self.adapter.ingest("question-1", [self._session()])
        old_command = self.mocks["popen"].call_args.args[0]
        old_client = self.clients[-1]
        self.adapter.reset("question-2")
        new_command = self.mocks["popen"].call_args.args[0]
        self.assertNotEqual(old_command[old_command.index("--name") + 1], new_command[new_command.index("--name") + 1])
        self.assertNotEqual(old_command[old_command.index("--mount") + 1], new_command[new_command.index("--mount") + 1])
        self.assertTrue(old_client.is_closed)
        self.requests.clear()
        with self.assertRaisesRegex(RuntimeError, "only that namespace"):
            self.adapter.retrieve("question-1", "query", 5, None)
        self.assertEqual(self.requests, [])
        self.adapter.ingest("question-2", [self._session()])
        self.assertEqual(len(self.requests), 1)
        self.adapter.reset("question-2")
        self.adapter.ingest("question-2", [self._session()])

    def test_start_requires_reset_and_stop_is_idempotent(self) -> None:
        self._start()
        with self.assertRaises(RuntimeError):
            self.adapter.ingest("question-1", [self._session()])
        self.adapter.stop()
        stops = self.mocks["run"].call_count
        self.adapter.stop()
        self.assertEqual(self.mocks["run"].call_count, stops)
        with self.assertRaises(RuntimeError):
            self.adapter.reset("question-1")

    def test_exited_docker_client_does_not_abandon_owned_container(self) -> None:
        self._start()
        process = self.adapter._process
        owned = self.adapter._container
        process.poll.return_value = 125
        self.adapter.stop()
        self.assertEqual(self.mocks["run"].call_args.args[0], ["docker", "stop", "--timeout", "20", owned])
        process.wait.assert_called_once_with(timeout=30)
        self.assertIsNone(self.adapter._container)

    def test_start_failure_after_client_exit_still_cleans_up_container(self) -> None:
        process = self._process()
        process.poll.return_value = 125
        self.mocks["popen"].side_effect = lambda *args, **kwargs: process
        with self.assertRaisesRegex(RuntimeError, "container exited"):
            self._start()
        command = self.mocks["popen"].call_args.args[0]
        owned = command[command.index("--name") + 1]
        self.assertEqual(self.mocks["run"].call_args.args[0], ["docker", "stop", "--timeout", "20", owned])
        self.assertIsNone(self.adapter._container)

    def test_already_removed_container_requires_successful_empty_owned_name_query(self) -> None:
        self._start()
        owned = self.adapter._container
        self.adapter._process.poll.return_value = 0
        self.mocks["run"].side_effect = [
            subprocess.CompletedProcess([], 1),
            subprocess.CompletedProcess([], 0, stdout=b""),
        ]
        self.adapter.stop()
        commands = [call.args[0] for call in self.mocks["run"].call_args_list]
        self.assertEqual(commands, [
            ["docker", "stop", "--timeout", "20", owned],
            ["docker", "container", "ls", "--all", "--filter", f"name={owned}", "--format", "{{.ID}}"],
        ])
        self.assertEqual(self.mocks["run"].call_args.kwargs["stdout"], subprocess.PIPE)
        self.assertIsNone(self.adapter._container)
        self.assertIsNone(self.adapter._workdir)
        self.mocks["run"].side_effect = None

    def test_failed_absence_verification_retains_ownership_and_prevents_reset(self) -> None:
        self._ready()
        owned = self.adapter._container
        process = self.adapter._process
        launches = self.mocks["popen"].call_count
        try:
            for query_result in (
                subprocess.CompletedProcess([], 0, stdout=b"owned-container-id\n"),
                subprocess.CompletedProcess([], 1, stdout=b""),
                subprocess.TimeoutExpired(["docker", "container", "ls"], 30),
            ):
                with self.subTest(query_result=query_result):
                    self.mocks["run"].side_effect = [subprocess.CompletedProcess([], 1), query_result]
                    with self.assertRaisesRegex(RuntimeError, "could not stop"):
                        self.adapter.reset("question-2")
                    self.assertEqual(self.adapter._container, owned)
                    self.assertIs(self.adapter._process, process)
                    self.assertEqual(self.mocks["popen"].call_count, launches)
                    with self.assertRaises(RuntimeError):
                        self.adapter.retrieve("question-1", "query", 5, None)
        finally:
            self.mocks["run"].side_effect = None

    def test_stop_failure_does_not_launch_a_replacement_store(self) -> None:
        self._ready()
        launches = self.mocks["popen"].call_count
        self.mocks["run"].return_value.returncode = 1
        try:
            with self.assertRaisesRegex(RuntimeError, "could not stop"):
                self.adapter.reset("question-2")
            self.assertEqual(self.mocks["popen"].call_count, launches)
            with self.assertRaises(RuntimeError):
                self.adapter.retrieve("question-1", "query", 5, None)
        finally:
            self.mocks["run"].return_value.returncode = 0


if __name__ == "__main__":
    unittest.main()
