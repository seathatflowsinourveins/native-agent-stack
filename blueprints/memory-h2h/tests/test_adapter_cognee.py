"""Offline contract checks for the v1.6.2 sources linked in cognee.md.

The HTTP module, socket, distribution metadata, and subprocess are all fixtures.
These checks do not import, install, or run Cognee or contact a listening service.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import importlib.util
import json
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
from types import ModuleType
from typing import Protocol
import unittest
from unittest.mock import MagicMock, Mock, patch


_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

try:
    from h2h.types import ModelRoute, Session, Turn
except ModuleNotFoundError as error:
    if error.name not in ("h2h", "h2h.types"):
        raise

    # The core builder may not have written types.py yet. Keep its exact
    # interface here; never create a competing source file in the worktree.
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

    interface = ModuleType("h2h.types")
    for name in ("Turn", "Session", "Retrieved", "ModelRoute", "IngestStats", "MemoryAdapter"):
        setattr(interface, name, globals()[name])
    sys.modules["h2h.types"] = interface


def _load_adapter():
    spec = importlib.util.spec_from_file_location(
        "_cognee_contract_adapter", _ROOT / "h2h" / "adapters" / "cognee.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


adapter_module = _load_adapter()


class FixtureRequestError(Exception):
    pass


class FixtureHTTPError(Exception):
    pass


class Response:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def json(self):
        return self.payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise FixtureHTTPError(f"HTTP {self.status_code}")


class Client:
    def __init__(self, **kwargs):
        self.settings = kwargs
        self.requests = []
        self.post_responses = []
        self.health_responses = []
        self.closed = False

    def get(self, path, **kwargs):
        self.requests.append(("GET", path, kwargs))
        response = self.health_responses.pop(0) if self.health_responses else Response(
            {"status": "ready", "health": "healthy", "version": "1.6.2"}
        )
        if isinstance(response, Exception):
            raise response
        return response

    def post(self, path, **kwargs):
        self.requests.append(("POST", path, kwargs))
        if self.post_responses:
            return self.post_responses.pop(0)
        if path == "/api/v1/add":
            return Response({"status": "PipelineRunCompleted", "dataset_id": "dataset"})
        if path == "/api/v1/cognify":
            return Response({"dataset": {"status": "PipelineRunCompleted"}})
        return Response(["Question and default hybrid retrieval context"])

    def close(self):
        self.closed = True


class CogneeContractTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="h2h-cognee-test-")
        self.addCleanup(self.directory.cleanup)
        self.workdir = Path(self.directory.name)
        self.clients = []
        self.processes = []
        self.next_health = []
        self.next_exit_code = None

        def make_client(**kwargs):
            client = Client(**kwargs)
            client.health_responses = self.next_health
            self.next_health = []
            self.clients.append(client)
            return client

        def make_process(*args, **kwargs):
            process = Mock()
            process.pid = 900000 + len(self.processes)
            process.poll.return_value = self.next_exit_code
            self.next_exit_code = None
            process.wait.return_value = 0
            self.processes.append(process)
            return process

        httpx_fixture = ModuleType("httpx")
        httpx_fixture.Client = Mock(side_effect=make_client)
        httpx_fixture.Timeout = Mock(side_effect=lambda timeout, **kwargs: (timeout, kwargs))
        httpx_fixture.RequestError = FixtureRequestError
        self.httpx_fixture = httpx_fixture
        self.environment = {
            "H2H_PORT": "18632",
            "H2H_LLM_KEY": "fixture-llm-value",
            "H2H_EMBED_KEY": "fixture-embed-value",
            # These inherited settings must never change this default baseline.
            "COGNEE_SKIP_CONNECTION_TEST": "true",
            "GRAPH_DATABASE_PROVIDER": "neo4j",
            "DB_PROVIDER": "postgres",
            "VECTOR_DB_PROVIDER": "qdrant",
            "EMBEDDING_DIMENSIONS": "9999",
            "LLM_TEMPERATURE": "0.9",
            "LLM_QUERY_MODEL": "inherited-model",
            "COGNEE_ENV_FILE": "/ignored-parent-setting.env",
        }
        self.addCleanup(patch.stopall)
        patch.dict(sys.modules, {"httpx": httpx_fixture}).start()
        patch.dict(adapter_module.os.environ, self.environment, clear=True).start()
        self.distribution = patch.object(
            adapter_module.importlib.metadata, "version", return_value="1.6.2"
        ).start()
        self.popen = patch.object(
            adapter_module.subprocess, "Popen", side_effect=make_process
        ).start()
        self.socket = patch.object(adapter_module.socket, "create_server", return_value=MagicMock()).start()
        self.killpg = patch.object(adapter_module.os, "killpg").start()
        self.sleep = patch.object(adapter_module.time, "sleep").start()
        self.adapter = adapter_module.build()
        # Cleanup is registered last: it runs while every network/process stub is active.
        self.addCleanup(self.adapter.stop)
        self.llm = ModelRoute("http://127.0.0.1:18633/v1", "shared-chat", "H2H_LLM_KEY")
        self.embed = ModelRoute("http://127.0.0.1:18634/v1", "shared-embed", "H2H_EMBED_KEY")
        self.sessions = [
            Session("s/one", "2026-02-03 (Tuesday) 09:10", (
                Turn("user", "Remember café 東京."), Turn("assistant", "I will."),
            )),
            Session("s-two", "2026-02-04 11:12", (Turn("user", "A later update."),)),
        ]

    def _ready(self):
        self.adapter.start(self.workdir, self.llm, self.embed)
        self.adapter.reset("question-one")
        return self.clients[-1]

    @staticmethod
    def _posts(client):
        return [request for request in client.requests if request[0] == "POST"]

    def test_import_and_build_do_not_initialize_upstream_or_network(self):
        self.distribution.reset_mock()
        first = _load_adapter().build()
        second = adapter_module.build()
        self.assertIsNot(first, second)
        self.assertEqual((first.name, first.version, first.needs_llm), ("cognee", "v1.6.2", True))
        self.distribution.assert_not_called()
        self.popen.assert_not_called()
        self.httpx_fixture.Client.assert_not_called()
        self.socket.assert_not_called()

    def test_start_uses_native_module_routes_and_private_paths(self):
        self.adapter.start(self.workdir, self.llm, self.embed)
        args, kwargs = self.popen.call_args
        self.assertEqual(args, ([
            sys.executable, "-m", "gunicorn", "-w", "1",
            "-k", "uvicorn.workers.UvicornWorker", "-t", "30000",
            "--bind=127.0.0.1:18632", "--log-level", "error",
            "--access-logfile", "-", "--error-logfile", "-", "cognee.api.client:app",
        ],))
        env = kwargs["env"]
        self.assertEqual(env["ENABLE_BACKEND_ACCESS_CONTROL"], "false")
        for role, model, url, key in (
            ("LLM", "shared-chat", self.llm.base_url, "fixture-llm-value"),
            ("EMBEDDING", "shared-embed", self.embed.base_url, "fixture-embed-value"),
        ):
            self.assertEqual(env[f"{role}_PROVIDER"], "openai")
            self.assertEqual(env[f"{role}_MODEL"], f"openai/{model}")
            self.assertEqual(env[f"{role}_ENDPOINT"], url)
            self.assertEqual(env[f"{role}_API_KEY"], key)
            self.assertNotIn(key, repr(args))
        for inherited in self.environment.keys() - {"H2H_PORT", "H2H_LLM_KEY", "H2H_EMBED_KEY", "COGNEE_ENV_FILE"}:
            self.assertNotIn(inherited, env)
        self.assertTrue(kwargs["start_new_session"])
        self.assertEqual(kwargs["stdout"], subprocess.DEVNULL)
        self.assertIsNone(kwargs["stderr"])
        for setting in ("DATA_ROOT_DIRECTORY", "SYSTEM_ROOT_DIRECTORY", "CACHE_ROOT_DIRECTORY", "COGNEE_LOGS_DIR"):
            path = Path(env[setting])
            self.assertTrue(path.is_relative_to(self.workdir))
            self.assertEqual(path.parent, kwargs["cwd"])
        env_file = Path(env["COGNEE_ENV_FILE"])
        self.assertEqual(env_file.parent, kwargs["cwd"])
        self.assertEqual(env_file.read_bytes(), b"")
        self.assertEqual(env_file.stat().st_mode & 0o777, 0o600)
        self.assertEqual([path for path in self.workdir.rglob("*") if path.is_file()], [env_file])
        self.socket.assert_called_once_with(("127.0.0.1", 18632), reuse_port=False)
        self.assertEqual(self.clients[0].settings["base_url"], "http://127.0.0.1:18632")
        self.assertFalse(self.clients[0].settings["trust_env"])

    def test_keyless_start_leaves_extractor_and_embeddings_at_upstream_defaults(self):
        self.adapter.start(self.workdir, None, None)
        env = self.popen.call_args.kwargs["env"]
        for key in ("LLM_API_KEY", "LLM_MODEL", "EMBEDDING_PROVIDER", "GRAPH_EXTRACTOR"):
            self.assertNotIn(key, env)
        self.assertFalse(self.adapter.needs_llm)

    def test_keyed_start_requires_an_embedding_route(self):
        with self.assertRaisesRegex(ValueError, "embedding ModelRoute"):
            self.adapter.start(self.workdir, self.llm, None)
        self.popen.assert_not_called()

    def test_endpoint_model_names_are_literal_even_when_they_contain_a_provider_name(self):
        # ModelRoute names the endpoint's literal model, as the common answerer
        # does. LiteLLM removes only the added dispatch prefix (v1.96.2 source).
        route = ModelRoute(self.llm.base_url, "openai/shared-chat", "H2H_LLM_KEY")
        env = self.adapter._route_environment(route, "LLM")
        self.assertEqual(env["LLM_MODEL"], "openai/openai/shared-chat")

    def test_missing_key_does_not_use_another_credential(self):
        route = ModelRoute(self.llm.base_url, self.llm.model, "MISSING_H2H_KEY")
        with self.assertRaisesRegex(RuntimeError, "MISSING_H2H_KEY"):
            self.adapter.start(self.workdir, route, self.embed)
        self.popen.assert_not_called()

    def test_rejects_non_http_routes_and_credentials_in_urls(self):
        for url in ("file:///tmp/model", "http://user:secret@model.example/v1", "http://model.example/v1?key=secret"):
            with self.subTest(url=url), self.assertRaisesRegex(ValueError, "HTTP base URL"):
                self.adapter.start(self.workdir, ModelRoute(url, "chat", "H2H_LLM_KEY"), self.embed)
        self.popen.assert_not_called()

    def test_rejects_invalid_port_and_wrong_distribution_before_launch(self):
        with patch.dict(adapter_module.os.environ, {"H2H_PORT": "invalid"}):
            with self.assertRaisesRegex(ValueError, "H2H_PORT"):
                self.adapter.start(self.workdir, self.llm, self.embed)
        self.distribution.return_value = "1.6.1"
        with self.assertRaisesRegex(RuntimeError, "v1.6.2 is required"):
            self.adapter.start(self.workdir, self.llm, self.embed)
        self.popen.assert_not_called()

    def test_existing_listener_is_never_contacted(self):
        self.socket.side_effect = OSError("already in use")
        with self.assertRaisesRegex(OSError, "already in use"):
            self.adapter.start(self.workdir, self.llm, self.embed)
        self.popen.assert_not_called()
        self.httpx_fixture.Client.assert_not_called()

    def test_reset_replaces_all_stores_even_when_namespace_repeats(self):
        self._ready()
        first = self.popen.call_args.kwargs
        first_client = self.clients[-1]
        first_process = self.processes[-1]
        self.adapter.reset("question-two")
        second = self.popen.call_args.kwargs
        self.adapter.reset("question-one")
        third = self.popen.call_args.kwargs
        for setting in ("DATA_ROOT_DIRECTORY", "SYSTEM_ROOT_DIRECTORY", "CACHE_ROOT_DIRECTORY", "COGNEE_ENV_FILE"):
            self.assertEqual(len({first["env"][setting], second["env"][setting], third["env"][setting]}), 3)
        self.assertTrue(first_client.closed)
        first_process.wait.assert_called_once_with(timeout=30.0)
        self.killpg.assert_any_call(first_process.pid, signal.SIGTERM)
        self.assertEqual(self.adapter.retrieve("question-one", "anything", 5, None), [])
        self.assertEqual(self._posts(self.clients[-1]), [])

    def test_namespace_checks_prevent_cross_question_requests(self):
        client = self._ready()
        with self.assertRaisesRegex(ValueError, "last reset"):
            self.adapter.ingest("other-question", self.sessions)
        with self.assertRaisesRegex(ValueError, "last reset"):
            self.adapter.retrieve("other-question", "query", 5, None)
        self.assertEqual(self._posts(client), [])

    def test_ingests_one_session_at_a_time_without_cognify_tuning(self):
        client = self._ready()
        stats = self.adapter.ingest("question-one", self.sessions)
        requests = self._posts(client)
        self.assertEqual([request[1] for request in requests], [
            "/api/v1/add", "/api/v1/cognify", "/api/v1/add", "/api/v1/cognify",
        ])
        dataset = requests[0][2]["data"]["datasetName"]
        for index, session in enumerate(self.sessions):
            add = requests[index * 2][2]
            self.assertEqual(add["data"], {"datasetName": dataset})
            self.assertEqual(set(add), {"data", "files"})
            self.assertEqual(len(add["files"]), 1)
            field_name, (filename, content, content_type) = add["files"][0]
            self.assertEqual(field_name, "data")
            self.assertTrue(filename.endswith(".txt"))
            self.assertEqual(content_type, "text/plain")
            expected = "\n\n".join(
                [f"Session ID: {session.session_id}", f"Session date: {session.date}"]
                + [f"{turn.role}: {turn.content}" for turn in session.turns]
            )
            self.assertEqual(content.decode("utf-8"), expected)
            self.assertEqual(requests[index * 2 + 1][2], {"json": {"datasets": [dataset]}})
        self.assertEqual(stats.sessions, 2)
        self.assertGreaterEqual(stats.seconds, 0.0)
        self.assertIsNone(stats.llm_calls)

    def test_recall_preserves_default_strategy_and_returns_context(self):
        client = self._ready()
        self.adapter.ingest("question-one", self.sessions[:1])
        client.post_responses = [Response(["Unmodified question + retrieved prompt 東京"])]
        result = self.adapter.retrieve("question-one", "Where?", 7, "2026-02-05")
        request = self._posts(client)[-1]
        dataset = self._posts(client)[0][2]["data"]["datasetName"]
        self.assertEqual(request, ("POST", "/api/v1/search", {"json": {
            "query": "Where?", "datasets": [dataset], "topK": 7, "onlyContext": True,
        }}))
        self.assertEqual([item.text for item in result], ["Unmodified question + retrieved prompt 東京"])
        self.assertEqual(result[0].session_ids, ())
        self.assertIsNone(result[0].score)

    def test_parses_wrapped_results_without_inventing_session_ids_or_scores(self):
        client = self._ready()
        self.adapter.ingest("question-one", self.sessions[:1])
        client.post_responses = [Response([{
            "dataset_id": "dataset-uuid", "dataset_name": "dataset",
            "search_result": ["first", {"text": "second", "document_id": "not-a-session"}],
        }])]
        result = self.adapter.retrieve("question-one", "query", 5, None)
        self.assertEqual(result[0].text, "first")
        self.assertEqual(json.loads(result[1].text), {"text": "second", "document_id": "not-a-session"})
        self.assertTrue(all(item.session_ids == () and item.score is None for item in result))

    def test_empty_input_and_empty_result_remain_empty(self):
        client = self._ready()
        stats = self.adapter.ingest("question-one", [])
        self.assertEqual(stats.sessions, 0)
        self.assertEqual(self.adapter.retrieve("question-one", "query", 5, None), [])
        self.assertEqual(self._posts(client), [])
        self.adapter.ingest("question-one", self.sessions[:1])
        for body in ([], [None], [""], [{"search_result": []}]):
            with self.subTest(body=body):
                client.post_responses = [Response(body)]
                self.assertEqual(self.adapter.retrieve("question-one", "query", 5, None), [])

    def test_does_not_report_incomplete_or_failed_pipelines_as_ingested(self):
        client = self._ready()
        for body in ({"status": "PipelineRunStarted"}, {"status": "PipelineRunErrored"}, {}):
            with self.subTest(body=body):
                client.post_responses = [Response(body)]
                before = len(self._posts(client))
                with self.assertRaisesRegex(RuntimeError, "completed blocking pipeline"):
                    self.adapter.ingest("question-one", self.sessions[:1])
                self.assertEqual(len(self._posts(client)), before + 1)
        client.post_responses = [
            Response({"status": "PipelineRunCompleted"}),
            Response({"dataset": {"status": "PipelineRunErrored"}}),
        ]
        with self.assertRaisesRegex(RuntimeError, "cognify"):
            self.adapter.ingest("question-one", self.sessions[:1])
        self.assertEqual(self.adapter.retrieve("question-one", "query", 5, None), [])

    def test_http_errors_propagate_and_are_not_scored_as_empty_retrieval(self):
        client = self._ready()
        client.post_responses = [Response({"error": "bad upload"}, 400)]
        with self.assertRaisesRegex(FixtureHTTPError, "400"):
            self.adapter.ingest("question-one", self.sessions[:1])
        self.adapter.ingest("question-one", self.sessions[:1])
        client.post_responses = [Response({"detail": "NoDataError"}, 404)]
        with self.assertRaisesRegex(FixtureHTTPError, "404"):
            self.adapter.retrieve("question-one", "query", 5, None)

    def test_readiness_waits_through_transport_failure(self):
        self.next_health = [FixtureRequestError("not bound yet"), Response({"status": "not ready"}, 503)]
        self.adapter.start(self.workdir, self.llm, self.embed)
        self.assertEqual(len(self.clients[0].requests), 3)
        self.assertEqual(self.sleep.call_count, 2)

    def test_failed_start_cleans_up_only_the_owned_process(self):
        self.next_exit_code = 7
        with self.assertRaisesRegex(RuntimeError, "status 7"):
            self.adapter.start(self.workdir, self.llm, self.embed)
        self.assertTrue(self.clients[0].closed)
        self.killpg.assert_called_once_with(self.processes[0].pid, signal.SIGTERM)
        self.adapter.start(self.workdir, self.llm, self.embed)
        self.assertEqual(len(self.processes), 2)

    def test_wrong_health_version_is_rejected_and_cleaned_up(self):
        self.next_health = [Response({"status": "ready", "version": "1.6.1"})]
        with self.assertRaisesRegex(RuntimeError, "other than v1.6.2"):
            self.adapter.start(self.workdir, self.llm, self.embed)
        self.assertTrue(self.clients[0].closed)
        self.killpg.assert_called_once_with(self.processes[0].pid, signal.SIGTERM)

    def test_stop_escalates_only_its_owned_process_group_and_is_idempotent(self):
        client = self._ready()
        process = self.processes[-1]
        process.wait.side_effect = [subprocess.TimeoutExpired("fixture", 30), 0]
        self.killpg.reset_mock()
        self.adapter.stop()
        self.killpg.assert_any_call(process.pid, signal.SIGTERM)
        self.killpg.assert_any_call(process.pid, signal.SIGKILL)
        self.assertEqual(self.killpg.call_count, 2)
        self.assertTrue(client.closed)
        self.adapter.stop()
        self.assertEqual(self.killpg.call_count, 2)

    def test_rejects_bad_k_and_malformed_search_response(self):
        client = self._ready()
        for value in (0, -1, True, "5"):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "positive integer"):
                self.adapter.retrieve("question-one", "query", value, None)
        self.adapter.ingest("question-one", self.sessions[:1])
        client.post_responses = [Response({"search_result": "wrong outer shape"})]
        with self.assertRaisesRegex(RuntimeError, "documented list"):
            self.adapter.retrieve("question-one", "query", 5, None)


if __name__ == "__main__":
    unittest.main()
