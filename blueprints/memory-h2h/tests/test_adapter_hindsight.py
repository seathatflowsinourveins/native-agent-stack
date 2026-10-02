"""Offline request-contract tests; never start Docker or contact a service.

The small fake HTTP layer works even before the coordinator installs httpx.
If the concurrently written interface is absent, its local copy lives here only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import io
import json
from pathlib import Path
import subprocess
import sys
from types import ModuleType, SimpleNamespace
from typing import Protocol
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
if not (ROOT / "h2h" / "types.py").is_file():
    interface = ModuleType("h2h.types")

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

    for name in ("Turn", "Session", "Retrieved", "ModelRoute", "IngestStats"):
        setattr(interface, name, globals()[name])
    class MemoryAdapter(Protocol):
        name: str
        version: str
        needs_llm: bool
        def start(self, workdir: Path, llm: ModelRoute | None, embed: ModelRoute | None) -> None: ...
        def reset(self, namespace: str) -> None: ...
        def ingest(self, namespace: str, sessions: list[Session]) -> IngestStats: ...
        def retrieve(self, namespace: str, query: str, k: int, question_date: str | None) -> list[Retrieved]: ...
        def stop(self) -> None: ...

    interface.MemoryAdapter = MemoryAdapter
    sys.modules["h2h.types"] = interface

from h2h.adapters import hindsight
from h2h.types import ModelRoute, Session, Turn


class HTTPFailure(RuntimeError):
    pass


class RequestFailure(RuntimeError):
    pass


class Response:
    def __init__(self, payload=None, status=200):
        self.payload = payload if payload is not None else {}
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise HTTPFailure(f"HTTP {self.status_code}")

    def json(self):
        return self.payload


class FakeClient:
    def __init__(self):
        self.requests = []
        self.handler = None
        self.health = [Response({"status": "healthy"})]
        self.closed = False

    def request(self, method, path, **kwargs):
        self.requests.append((method, path, kwargs))
        if self.handler:
            response = self.handler(method, path, kwargs)
            if response is not None:
                return response
        if path.endswith("/operations"):
            return Response({"bank_id": path.split("/")[-2], "total": 0, "limit": 20, "offset": 0, "operations": []})
        if method == "POST" and path.endswith("/memories"):
            return Response({"success": True, "bank_id": path.split("/")[-2], "items_count": 1, "async": False, "usage": {"input_tokens": 25, "output_tokens": 5, "total_tokens": 30}})
        if method == "POST" and path.endswith("/recall"):
            return Response({"results": [], "entities": None, "chunks": None})
        return Response({"success": True})

    def get(self, path, **kwargs):
        self.requests.append(("GET", path, kwargs))
        result = self.health.pop(0) if len(self.health) > 1 else self.health[0]
        if isinstance(result, Exception):
            raise result
        return result

    def close(self):
        self.closed = True


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.client = FakeClient()
        self.adapter = hindsight.build()
        self.adapter._client = self.client
        self.sleep = patch.object(hindsight.time, "sleep").start()
        self.addCleanup(patch.stopall)

    def namespace(self, namespace="q1"):
        self.adapter.reset(namespace)
        return self.adapter._banks[namespace]

    def post_requests(self, suffix):
        return [(path, kwargs["json"]) for method, path, kwargs in self.client.requests if method == "POST" and path.endswith(suffix)]

    def test_factory_has_pin_and_independent_state(self):
        other = hindsight.build()
        self.assertEqual((self.adapter.name, self.adapter.version, self.adapter.needs_llm), ("hindsight", "v0.10.2", True))
        self.namespace()
        self.assertEqual(other._banks, {})
        self.assertIsNone(other._client)

    def test_reset_defaults_new_bank_and_full_delete(self):
        first = self.namespace("question / with punctuation")
        self.adapter._sources[first]["doc"] = "old-session"
        self.adapter.reset("question / with punctuation")
        second = self.adapter._banks["question / with punctuation"]
        self.assertNotEqual(first, second)
        self.assertEqual(self.client.requests, [
            ("PUT", f"/v1/default/banks/{first}", {"json": {}}),
            ("DELETE", f"/v1/default/banks/{first}", {}),
            ("PUT", f"/v1/default/banks/{second}", {"json": {}}),
        ])
        self.assertNotIn(first, self.adapter._sources)
        self.assertEqual(self.adapter._sources[second], {})

    def test_reset_only_tolerates_missing_bank(self):
        original = self.namespace()
        self.client.handler = lambda method, path, kwargs: Response(status=503) if method == "DELETE" else None
        with self.assertRaises(HTTPFailure):
            self.adapter.reset("q1")
        self.assertEqual(self.adapter._banks["q1"], original)
        self.client.handler = lambda method, path, kwargs: Response(status=404) if method == "DELETE" else None
        self.adapter.reset("q1")
        self.assertNotEqual(self.adapter._banks["q1"], original)

    def test_namespace_isolation_and_no_implicit_bank(self):
        first = self.namespace("q1")
        second = self.namespace("q2")
        self.adapter.retrieve("q2", "the query", 10, None)
        self.assertEqual(self.post_requests("/recall"), [(f"/v1/default/banks/{second}/memories/recall", {"query": "the query"})])
        self.assertNotEqual(first, second)
        with self.assertRaisesRegex(RuntimeError, "reset"):
            self.adapter.retrieve("unknown", "query", 1, None)

    def test_conversation_ingestion_is_chronological_and_synchronous(self):
        bank = self.namespace()
        early = Session("s-early", "2023/05/20 (Sat) 02:21", (Turn("user", "café?"), Turn("assistant", "Yes.\nDetails.")))
        late = Session("s-late", "2023/05/21 (Sun) 17:09", (Turn("user", "Later"),))
        stats = self.adapter.ingest("q1", [late, early])
        posts = self.post_requests("/memories")
        self.assertEqual(len(posts), 2)
        for path, body in posts:
            self.assertEqual(path, f"/v1/default/banks/{bank}/memories")
            self.assertEqual(set(body), {"items"})  # async=false is the API default.
            self.assertEqual(len(body["items"]), 1)
            self.assertEqual(set(body["items"][0]), {"content", "timestamp", "document_id", "metadata"})
        first, second = (body["items"][0] for _, body in posts)
        self.assertEqual(json.loads(first["content"]), [{"role": "user", "content": "café?"}, {"role": "assistant", "content": "Yes.\nDetails."}])
        self.assertEqual(first["timestamp"], "2023-05-20T02:21:00+00:00")
        self.assertEqual(second["timestamp"], "2023-05-21T17:09:00+00:00")
        self.assertEqual(first["metadata"], {"session_id": early.session_id, "session_date": early.date})
        self.assertEqual(stats.sessions, 2)
        self.assertIsNone(stats.llm_calls)
        self.assertGreaterEqual(stats.seconds, 0)
        operations = [kwargs["params"] for method, path, kwargs in self.client.requests if path.endswith("/operations")]
        self.assertEqual(operations, [{"status": status} for _ in range(2) for status in ("failed", "cancelled", "pending", "processing")])

    def test_repeated_session_ids_are_not_upserted_away(self):
        self.namespace()
        sessions = [Session("same-id", "2024-01-01", (Turn("user", "first"),)), Session("same-id", "2024-01-02", (Turn("assistant", "second"),))]
        self.adapter.ingest("q1", sessions)
        items = [body["items"][0] for _, body in self.post_requests("/memories")]
        self.assertNotEqual(items[0]["document_id"], items[1]["document_id"])
        self.assertEqual([item["metadata"]["session_id"] for item in items], ["same-id", "same-id"])

    def test_dates_preserve_times_and_offsets_and_invalid_date_fails_before_writes(self):
        self.namespace()
        for raw, expected in [("2023/05/20 (Saturday) 02:21", "2023-05-20T02:21:00+00:00"), ("2023-05-20T02:21:00Z", "2023-05-20T02:21:00+00:00"), ("2023-05-20T02:21:00-04:00", "2023-05-20T02:21:00-04:00"), ("2023/05/20", "2023-05-20T00:00:00+00:00")]:
            with self.subTest(raw=raw):
                self.assertEqual(hindsight._timestamp(raw).isoformat(), expected)
        with self.assertRaises(ValueError):
            self.adapter.ingest("q1", [Session("ok", "2024-01-01", ()), Session("bad", "unknown", ())])
        self.assertEqual(self.post_requests("/memories"), [])

    def test_async_or_unsuccessful_response_is_not_completed_ingestion(self):
        self.namespace()
        for payload in [{"success": True, "async": True, "items_count": 1, "operation_id": "op"}, {"success": False, "async": False, "items_count": 1}, {"success": True, "async": False, "items_count": 0}]:
            with self.subTest(payload=payload):
                self.client.handler = lambda method, path, kwargs: Response(payload) if path.endswith("/memories") else None
                with self.assertRaisesRegex(RuntimeError, "synchronous retention"):
                    self.adapter.ingest("q1", [Session("s", "2024-01-01", (Turn("user", "x"),))])

    def test_settle_waits_for_background_work_and_two_quiet_polls(self):
        bank = self.namespace()
        rounds = 0

        def handler(method, path, kwargs):
            nonlocal rounds
            if not path.endswith("/operations"):
                return None
            status = kwargs["params"]["status"]
            if status == "failed":
                rounds += 1
            # Quiet round 2 alone is insufficient: new work appears in round 3.
            total = 1 if status == "pending" and rounds in (1, 3) else 0
            return Response({"total": total, "operations": []})

        self.client.handler = handler
        self.adapter._wait_settled(bank)
        self.assertEqual(rounds, 5)
        self.assertEqual(self.sleep.call_count, 4)

    def test_background_failures_and_timeout_propagate(self):
        bank = self.namespace()
        for failure in ("failed", "cancelled"):
            with self.subTest(failure=failure):
                self.client.handler = lambda method, path, kwargs: Response({"total": int(kwargs["params"]["status"] == failure), "operations": []})
                with self.assertRaisesRegex(RuntimeError, failure):
                    self.adapter._wait_settled(bank)
        self.client.handler = None
        with patch.object(hindsight.time, "monotonic", side_effect=[0, 901]):
            with self.assertRaises(TimeoutError):
                self.adapter._wait_settled(bank)

    def test_recall_uses_server_defaults_and_common_k_without_query_truncation(self):
        bank = self.namespace()
        query = "long question " * 180
        results = [
            {"id": "fact1", "text": "Lived in Paris", "type": "world", "occurred_start": "2023-01-01", "entities": ["User"], "metadata": {"session_id": "s1"}, "scores": {"final": 0.8}},
            {"id": "fact2", "text": "Now lives in Lyon", "document_id": "doc2", "metadata": None, "scores": None},
            {"id": "fact3", "text": "Extra", "metadata": None},
        ]
        self.adapter._sources[bank]["doc2"] = "s2"
        self.client.handler = lambda method, path, kwargs: Response({"results": results, "entities": {"User": {"canonical_name": "User", "observations": [{"text": "Moved to France"}]}}})
        out = self.adapter.retrieve("q1", query, 2, "2023/05/20 (Sat) 02:21")
        self.assertEqual(self.post_requests("/recall"), [(f"/v1/default/banks/{bank}/memories/recall", {"query": query, "query_timestamp": "2023-05-20T02:21:00+00:00"})])
        self.assertEqual(len(out), 2)
        self.assertEqual([r.session_ids for r in out], [("s1",), ("s2",)])
        self.assertEqual([r.score for r in out], [0.8, None])
        text = json.loads(out[0].text)
        self.assertEqual(text["text"], "Lived in Paris")
        self.assertEqual(text["occurred_start"], "2023-01-01")
        self.assertIn("entity_states", text)

    def test_observation_without_reported_provenance_has_empty_sources(self):
        self.namespace()
        self.client.handler = lambda method, path, kwargs: Response({"results": [{"id": "observation", "text": "Likes mountains", "type": "observation", "document_id": None, "metadata": None, "scores": None}]})
        out = self.adapter.retrieve("q1", "preferences?", 1, None)
        self.assertEqual(out[0].session_ids, ())
        self.assertEqual(self.post_requests("/recall")[0][1], {"query": "preferences?"})

    def test_empty_ingestion_and_k_zero_do_not_send_memory_requests(self):
        self.namespace()
        stats = self.adapter.ingest("q1", [])
        self.assertEqual(stats.sessions, 0)
        self.assertIsNone(stats.llm_calls)
        self.assertEqual(self.adapter.retrieve("q1", "query", 0, None), [])
        self.assertEqual(self.post_requests("/memories"), [])
        self.assertEqual(self.post_requests("/recall"), [])
        with self.assertRaises(ValueError):
            self.adapter.retrieve("q1", "query", -1, None)


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.client = FakeClient()
        self.process = Mock()
        self.process.poll.return_value = None
        self.process.wait.return_value = 0
        self.adapter = hindsight.build()
        self.llm = ModelRoute("http://127.0.0.1:18990/v1", "common-llm", "TEST_LLM_KEY")
        self.embed = ModelRoute("http://127.0.0.1:18991/v1", "common-embed", "TEST_EMBED_KEY")
        module = ModuleType("httpx")
        module.RequestError = RequestFailure
        module.Client = Mock(return_value=self.client)
        self.httpx = module
        self.enter(patch.dict(sys.modules, {"httpx": module}))
        self.enter(patch.dict(hindsight.os.environ, {"H2H_PORT": "18988", "TEST_LLM_KEY": "synthetic-llm-key", "TEST_EMBED_KEY": "synthetic-embed-key", "HINDSIGHT_API_RETAIN_EXTRACTION_MODE": "chunks", "HINDSIGHT_API_EMBEDDINGS_PROVIDER": "tei"}, clear=True))
        self.enter(patch.object(hindsight.sys, "platform", "linux"))
        self.enter(patch.object(hindsight.shutil, "which", return_value="/usr/bin/docker"))
        self.socket = self.enter(patch.object(hindsight.socket, "socket"))
        self.mkdir = self.enter(patch.object(Path, "mkdir"))
        self.enter(patch.object(Path, "stat", return_value=SimpleNamespace(st_uid=1000)))
        self.enter(patch.object(Path, "resolve", autospec=True, side_effect=lambda path: path))
        self.popen = self.enter(patch.object(hindsight.subprocess, "Popen", return_value=self.process))
        self.stop_command = self.enter(patch.object(hindsight.subprocess, "run", return_value=SimpleNamespace(returncode=0)))
        self.sleep = self.enter(patch.object(hindsight.time, "sleep"))

    def enter(self, patcher):
        result = patcher.start()
        self.addCleanup(patcher.stop)
        return result

    def start(self, embed=True):
        self.adapter.start(Path("/private/h2h-run"), self.llm, self.embed if embed else None)

    def test_start_launches_pinned_api_on_loopback_with_named_environment(self):
        self.start()
        command = self.popen.call_args.args[0]
        env = self.popen.call_args.kwargs["env"]
        self.assertEqual(command[:3], ["/usr/bin/docker", "run", "--rm"])
        self.assertIn("ghcr.io/vectorize-io/hindsight-api:0.10.2", command)
        self.assertEqual(command[command.index("--entrypoint") + 1], "/app/api/.venv/bin/python")
        self.assertIn("--interactive", command)
        self.assertEqual(command[-2], "-c")
        self.assertEqual(command[command.index("--network") + 1], "host")
        forwarded = [command[i + 1] for i, flag in enumerate(command) if flag == "--env"]
        self.assertEqual(set(forwarded), {"HINDSIGHT_API_HOST", "HINDSIGHT_API_PORT", "HINDSIGHT_API_LLM_PROVIDER", "HINDSIGHT_API_LLM_MODEL", "HINDSIGHT_API_LLM_BASE_URL", "HINDSIGHT_API_EMBEDDINGS_PROVIDER", "HINDSIGHT_API_EMBEDDINGS_OPENAI_MODEL", "HINDSIGHT_API_EMBEDDINGS_OPENAI_BASE_URL"})
        self.assertEqual(env["HINDSIGHT_API_HOST"], "127.0.0.1")
        self.assertEqual(env["HINDSIGHT_API_PORT"], "18988")
        self.assertEqual(env["HINDSIGHT_API_LLM_BASE_URL"], self.llm.base_url)
        self.assertEqual(env["HINDSIGHT_API_EMBEDDINGS_OPENAI_BASE_URL"], self.embed.base_url)
        self.assertEqual(env["HINDSIGHT_API_LLM_MODEL"], self.llm.model)
        self.assertEqual(env["HINDSIGHT_API_EMBEDDINGS_OPENAI_MODEL"], self.embed.model)
        self.assertNotIn("HINDSIGHT_API_LLM_API_KEY", env)
        self.assertNotIn("HINDSIGHT_API_EMBEDDINGS_OPENAI_API_KEY", env)
        credentials = json.loads(self.process.stdin.write.call_args.args[0])
        self.assertEqual(credentials, {"HINDSIGHT_API_LLM_API_KEY": "synthetic-llm-key", "HINDSIGHT_API_EMBEDDINGS_OPENAI_API_KEY": "synthetic-embed-key"})
        self.assertEqual(self.popen.call_args.kwargs["stdin"], subprocess.PIPE)
        self.process.stdin.close.assert_called_once()
        self.assertNotIn("HINDSIGHT_API_RETAIN_EXTRACTION_MODE", forwarded)
        self.assertNotIn("synthetic-llm-key", " ".join(command))
        self.assertNotIn("synthetic-embed-key", " ".join(command))
        self.assertNotIn("--env-file", command)
        self.assertNotIn("--user", command)
        volume = command[command.index("--volume") + 1]
        self.assertTrue(volume.startswith("/private/h2h-run/hindsight-"))
        self.assertTrue(volume.endswith("/pg0:/home/hindsight/.pg0"))
        self.assertEqual(self.client.requests, [("GET", "/health", {"timeout": 5.0})])
        self.assertEqual(self.httpx.Client.call_args.kwargs, {"base_url": "http://127.0.0.1:18988", "timeout": 900.0, "trust_env": False})

    def test_omitted_embedding_route_preserves_local_defaults(self):
        self.start(embed=False)
        command = self.popen.call_args.args[0]
        self.assertFalse(any(arg.startswith("HINDSIGHT_API_EMBEDDINGS") for arg in command))
        self.assertEqual(json.loads(self.process.stdin.write.call_args.args[0]), {"HINDSIGHT_API_LLM_API_KEY": "synthetic-llm-key"})

    def test_secret_bootstrap_only_sets_runtime_environment_and_execs_upstream_entrypoint(self):
        self.start()
        bootstrap = self.popen.call_args.args[0][-1]
        process_environment = {}
        credentials = self.process.stdin.write.call_args.args[0].decode("utf-8")
        fake_os = SimpleNamespace(environ=process_environment, execv=Mock())
        fake_sys = SimpleNamespace(stdin=io.StringIO(credentials))
        with patch.dict(sys.modules, {"os": fake_os, "sys": fake_sys}):
            exec(bootstrap, {})
        self.assertEqual(process_environment, json.loads(credentials))
        fake_os.execv.assert_called_once_with("/app/start-all.sh", ["/app/start-all.sh"])

    def test_broken_credential_pipe_cleans_up_owned_launch(self):
        self.process.stdin.write.side_effect = BrokenPipeError("closed")
        with self.assertRaises(BrokenPipeError):
            self.start()
        self.stop_command.assert_called_once()
        self.assertTrue(self.client.closed)

    def test_readiness_retries_connection_failure_and_503(self):
        self.client.health = [RequestFailure("not yet"), Response(status=503), Response({"status": "healthy"})]
        self.start()
        self.assertEqual(self.sleep.call_count, 2)

    def test_occupied_port_cannot_accept_an_existing_service(self):
        self.socket.return_value.__enter__.return_value.bind.side_effect = OSError("occupied")
        with self.assertRaisesRegex(RuntimeError, "occupied port"):
            self.start()
        self.popen.assert_not_called()
        self.mkdir.assert_not_called()
        self.assertEqual(self.client.requests, [])

    def test_missing_routes_ports_or_key_names_never_launch(self):
        with self.assertRaisesRegex(ValueError, "LLM"):
            self.adapter.start(Path("/private/h2h-run"), None, None)
        for port in ("bad", "0", "65536"):
            with self.subTest(port=port), patch.dict(hindsight.os.environ, {"H2H_PORT": port}):
                with self.assertRaises(ValueError):
                    self.start()
        with patch.dict(hindsight.os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "H2H_PORT"):
                self.start()
        with self.assertRaisesRegex(RuntimeError, "MISSING_KEY"):
            hindsight._route_environment(ModelRoute(self.llm.base_url, "model", "MISSING_KEY"))
        with self.assertRaises(ValueError):
            hindsight._route_environment(ModelRoute("http://user:password@example.invalid/v1", "model", "TEST_LLM_KEY"))
        self.popen.assert_not_called()

    def test_unsupported_host_missing_docker_and_bad_ownership_fail_before_launch(self):
        with patch.object(hindsight.sys, "platform", "darwin"):
            with self.assertRaisesRegex(RuntimeError, "Linux"):
                self.start()
        with patch.object(hindsight.shutil, "which", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "Docker"):
                self.start()
        with patch.object(Path, "stat", return_value=SimpleNamespace(st_uid=1001)):
            with self.assertRaisesRegex(RuntimeError, "UID 1000"):
                self.start()
        self.popen.assert_not_called()

    def test_start_failure_stops_only_owned_container_and_closes_http(self):
        self.process.poll.return_value = 1
        with self.assertRaisesRegex(RuntimeError, "exited during startup"):
            self.start()
        stop = self.stop_command.call_args.args[0]
        self.assertEqual(stop[:4], ["docker", "stop", "-t", "30"])
        self.assertTrue(stop[4].startswith("h2h-hindsight-"))
        self.assertTrue(self.client.closed)
        self.assertIsNone(self.adapter._container)

    def test_start_readiness_timeout_is_not_silent(self):
        with patch.object(hindsight.time, "monotonic", side_effect=[0, 301]):
            with self.assertRaisesRegex(TimeoutError, "300"):
                self.start()
        self.stop_command.assert_called_once()
        self.assertTrue(self.client.closed)

    def test_stop_is_idempotent_and_cannot_lose_failed_cleanup_identity(self):
        self.start()
        container = self.adapter._container
        self.stop_command.return_value = SimpleNamespace(returncode=1)
        with self.assertRaisesRegex(RuntimeError, "Could not stop"):
            self.adapter.stop()
        self.assertEqual(self.adapter._container, container)
        self.assertFalse(self.client.closed)
        self.process.poll.return_value = 1
        with self.assertRaisesRegex(RuntimeError, "Could not stop"):
            self.adapter.stop()
        self.assertEqual(self.adapter._container, container)
        self.assertFalse(self.client.closed)
        self.stop_command.return_value = SimpleNamespace(returncode=0)
        self.adapter.stop()
        self.adapter.stop()
        self.assertEqual(self.stop_command.call_count, 3)
        self.assertTrue(self.client.closed)

    def test_stop_only_accepts_exact_owned_container_absence_after_cli_exit(self):
        self.start()
        container = self.adapter._container
        self.process.poll.return_value = 1
        self.stop_command.return_value = SimpleNamespace(returncode=1, stderr="Error response from daemon: No such container: different-container\n")
        with self.assertRaisesRegex(RuntimeError, "Could not stop"):
            self.adapter.stop()
        self.assertEqual(self.adapter._container, container)
        self.process.poll.return_value = None
        self.stop_command.return_value = SimpleNamespace(returncode=1, stderr=f"Error response from daemon: No such container: {container}\n")
        with self.assertRaisesRegex(RuntimeError, "Could not stop"):
            self.adapter.stop()
        self.process.poll.return_value = 1
        self.adapter.stop()
        self.assertIsNone(self.adapter._container)
        self.assertTrue(self.client.closed)

    def test_stop_aborts_an_unfinished_launch_before_accepting_container_absence(self):
        self.start()
        container = self.adapter._container
        self.stop_command.return_value = SimpleNamespace(returncode=1, stderr=f"Error response from daemon: No such container: {container}\n")
        self.process.terminate.side_effect = lambda: setattr(self.process.poll, "return_value", 1)
        self.adapter.stop()
        self.process.terminate.assert_called_once()
        self.process.wait.assert_called()
        self.assertEqual(self.stop_command.call_count, 2)
        self.assertIsNone(self.adapter._container)


if __name__ == "__main__":
    unittest.main()
