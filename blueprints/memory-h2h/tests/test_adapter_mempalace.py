"""Offline integration contract fixtures; no MemPalace install or socket is used."""

from __future__ import annotations

import importlib
import json as jsonlib
import subprocess
import sys
import tempfile
import types
import unittest
from contextlib import ExitStack
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol
from unittest.mock import MagicMock, patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# The core builder may not have created h2h/types.py yet. Keep its exact
# interface here for that case; never write a substitute file into the package.
try:
    from h2h.types import IngestStats, MemoryAdapter, ModelRoute, Retrieved, Session, Turn
except ModuleNotFoundError as exc:
    if exc.name != "h2h.types":
        raise

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

    interface = types.ModuleType("h2h.types")
    for interface_type in (Turn, Session, Retrieved, ModelRoute, IngestStats, MemoryAdapter):
        setattr(interface, interface_type.__name__, interface_type)
    sys.modules["h2h.types"] = interface

from h2h.adapters import mempalace


class FixtureRequestError(Exception):
    pass


class FixtureResponse:
    def __init__(self, body=None, status_code=200):
        self.body = body
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"fixture HTTP {self.status_code}")

    def json(self):
        if self.body is None:
            raise ValueError("fixture response has no JSON")
        return self.body


class FixtureClient:
    """Implements the HTTP methods the adapter uses, without a network stack."""

    def __init__(self, fixture, options):
        self.fixture = fixture
        self.options = options
        self.requests = []
        self.mined_exports = []
        self.closed = False

    def get(self, path, **options):
        self.requests.append(("GET", path, options))
        if self.fixture.health_error:
            raise FixtureRequestError("fixture connection unavailable")
        return FixtureResponse(status_code=self.fixture.health_status)

    def post(self, path, *, json):
        self.requests.append(("POST", path, json))
        if json["method"] == "notifications/initialized":
            return FixtureResponse(status_code=202)
        if json["method"] == "initialize":
            result = {
                "protocolVersion": "fixture-native-default",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "mempalace", "version": self.fixture.server_version},
            }
        else:
            name = json["params"]["name"]
            if name == "mempalace_mine":
                source = Path(json["params"]["arguments"]["source"])
                # Observe the actual serialized source before acknowledging mine.
                text = source.read_text(encoding="utf-8")
                export = jsonlib.loads(text) if source.suffix == ".json" else text
                self.mined_exports.append((source, export))
                data = self.fixture.mine_result
            elif name == "mempalace_search":
                data = self.fixture.search_result
            else:
                raise AssertionError(f"Unexpected native tool: {name}")
            result = {"content": [{"type": "text", "text": jsonlib.dumps(data)}]}
        body = {"jsonrpc": "2.0", "id": json["id"], "result": result}
        if self.fixture.rpc_override is not None:
            body = self.fixture.rpc_override(body)
        return FixtureResponse(body, self.fixture.rpc_status)

    def close(self):
        self.closed = True

    def tool_calls(self):
        return [body for method, path, body in self.requests if method == "POST" and body["method"] == "tools/call"]


class MemPalaceContractTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        directory = self.stack.enter_context(tempfile.TemporaryDirectory(prefix="h2h-mempalace-test-"))
        self.workdir = Path(directory)
        self.clients = []
        self.processes = []
        self.health_error = False
        self.health_status = 200
        self.server_version = "3.10.0"
        self.rpc_status = 200
        self.rpc_override = None
        self.mine_result = {"success": True, "mode": "convos", "dry_run": False, "output": "Drawers filed: 2"}
        self.search_result = {"query": "fixture", "filters": {}, "results": []}

        # Stub the dependency itself so the exact requested python3 unittest
        # command also works in a source-only environment without httpx installed.
        http_layer = types.ModuleType("httpx")
        http_layer.RequestError = FixtureRequestError
        http_layer.Timeout = lambda value, **options: (value, options)
        http_layer.Client = self.make_client
        self.stack.enter_context(patch.dict(sys.modules, {"httpx": http_layer}))
        self.stack.enter_context(patch.dict(mempalace.os.environ, {"H2H_PORT": "18765"}, clear=True))
        self.popen = self.stack.enter_context(patch.object(mempalace.subprocess, "Popen", side_effect=self.make_process))
        self.adapter = mempalace.build()
        self.addCleanup(self.adapter.stop)

    def make_client(self, **options):
        client = FixtureClient(self, options)
        self.clients.append(client)
        return client

    def make_process(self, *args, **kwargs):
        process = MagicMock()
        process.poll.return_value = None
        process.wait.return_value = 0
        self.processes.append(process)
        return process

    def start_namespace(self, namespace="question-1", *, embed=None, llm=None):
        self.adapter.start(self.workdir, llm, embed)
        self.adapter.reset(namespace)
        return self.clients[-1]

    def session(self, identifier="original-session", date="2023/05/20 (Sat) 14:30"):
        return Session(
            identifier,
            date,
            (Turn("user", "I chose the library near the park.\nIt opens at 09:00."), Turn("assistant", "I'll remember that location.\nBring your library card.")),
        )

    def test_build_and_import_have_no_process_or_http_activity(self):
        importlib.reload(mempalace)
        first, second = mempalace.build(), mempalace.build()
        self.assertIsNot(first, second)
        self.assertEqual((first.name, first.version, first.needs_llm), ("mempalace", "v3.10.0", False))
        self.popen.assert_not_called()
        self.assertEqual(self.clients, [])

    def test_start_launches_documented_foreground_loopback_command(self):
        self.adapter.start(self.workdir, None, None)
        command = self.popen.call_args.args[0]
        palace = Path(command[-1])
        self.assertEqual(command, ["mempalace", "serve", "--host", "127.0.0.1", "--port", "18765", "--palace", str(palace)])
        options = self.popen.call_args.kwargs
        self.assertTrue(palace.is_relative_to(self.workdir))
        self.assertEqual(options["cwd"], palace.parent)
        self.assertEqual(options["env"]["MEMPALACE_PALACE_PATH"], str(palace))
        self.assertEqual(options["env"]["MEMPALACE_CONFIG_DIR"], str(palace.parent / "config"))
        self.assertEqual(self.clients[0].options["base_url"], "http://127.0.0.1:18765")
        self.assertFalse(self.clients[0].options["trust_env"])
        self.assertEqual(palace.parent.stat().st_mode & 0o777, 0o700)

    def test_start_uses_native_initialize_and_bodyless_notification(self):
        self.adapter.start(self.workdir, None, None)
        requests = self.clients[0].requests
        self.assertEqual(requests[0][:2], ("GET", "/healthz"))
        self.assertEqual(requests[1], ("POST", "/mcp", {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}))
        self.assertEqual(requests[2], ("POST", "/mcp", {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}))

    def test_start_filters_host_mempalace_settings_and_keeps_defaults(self):
        with patch.dict(mempalace.os.environ, {"MEMPALACE_BACKEND": "qdrant", "MEMPALACE_COLLECTION_NAME": "host-data", "MEMPALACE_CONFIG_DIR": "/do-not-read-host-config", "MEMPALACE_EMBEDDING_MODEL": "embeddinggemma", "MEMPALACE_MCP_HTTP_TOKEN": "fixture-host-token", "MEMPAL_DIR": "/do-not-mine-host-data"}):
            self.adapter.start(self.workdir, None, None)
        child_env = self.popen.call_args.kwargs["env"]
        mempalace_settings = {key for key in child_env if key.startswith("MEMPALACE_")}
        self.assertEqual(mempalace_settings, {"MEMPALACE_CONFIG_DIR", "MEMPALACE_PALACE_PATH"})
        self.assertNotIn("MEMPAL_DIR", child_env)

    def test_embedding_route_is_passed_in_environment_and_never_written(self):
        embed = ModelRoute("http://127.0.0.1:18766/v1", "fixture-embedder", "FIXTURE_EMBED_KEY")
        llm = ModelRoute("http://127.0.0.1:18767/v1", "fixture-answerer", "FIXTURE_LLM_KEY")
        with patch.dict(mempalace.os.environ, {"FIXTURE_EMBED_KEY": "embedding-test-value", "FIXTURE_LLM_KEY": "llm-test-value"}):
            client = self.start_namespace(embed=embed, llm=llm)
            self.adapter.ingest("question-1", [self.session()])
        options = self.popen.call_args.kwargs
        child_env = options["env"]
        self.assertEqual(child_env["MEMPALACE_EMBEDDING_MODEL"], "openai-compat")
        self.assertEqual(child_env["MEMPALACE_EMBEDDING_API_URL"], embed.base_url)
        self.assertEqual(child_env["MEMPALACE_EMBEDDING_API_MODEL"], embed.model)
        self.assertEqual(child_env["MEMPALACE_EMBEDDING_API_KEY"], "embedding-test-value")
        self.assertNotIn("embedding-test-value", repr(options["cwd"]))
        self.assertNotIn("embedding-test-value", repr(self.popen.call_args.args))
        for path in self.workdir.rglob("*"):
            if path.is_file():
                self.assertNotIn("embedding-test-value", path.read_text())
                self.assertNotIn("llm-test-value", path.read_text())
        self.assertEqual([call["params"]["name"] for call in client.tool_calls()], ["mempalace_mine"])

    def test_embedding_route_supports_an_unauthenticated_endpoint(self):
        self.adapter.start(self.workdir, None, ModelRoute("http://127.0.0.1:18766/v1", "fixture-embedder"))
        self.assertNotIn("MEMPALACE_EMBEDDING_API_KEY", self.popen.call_args.kwargs["env"])

    def test_mining_submits_each_supported_export_in_input_order(self):
        client = self.start_namespace()
        sessions = [self.session("id/unsafe-path", "2023/05/20 (Sat) 14:30"), self.session("second", "2023/06/21 (Wed) 12:00")]
        stats = self.adapter.ingest("question-1", sessions)
        self.assertEqual((stats.sessions, stats.llm_calls), (2, 0))
        self.assertGreaterEqual(stats.seconds, 0)
        calls = client.tool_calls()
        self.assertEqual(len(calls), 2)
        for index, (source, export) in enumerate(client.mined_exports):
            self.assertTrue(source.is_relative_to(self.workdir))
            self.assertEqual(calls[index]["params"], {"name": "mempalace_mine", "arguments": {"source": str(source), "mode": "convos"}})
            self.assertEqual(export["uuid"], sessions[index].session_id)
            self.assertEqual(export["created_at"], sessions[index].date)
            for item, turn in zip(export["chat_messages"], sessions[index].turns, strict=True):
                self.assertEqual(item, {"role": turn.role, "content": f"[Session date: {sessions[index].date}]\n{turn.content}"})

    def test_empty_ingest_makes_no_mine_calls(self):
        client = self.start_namespace()
        stats = self.adapter.ingest("question-1", [])
        self.assertEqual((stats.sessions, stats.llm_calls), (0, 0))
        self.assertEqual(client.tool_calls(), [])

    def test_empty_session_uses_empty_native_plaintext(self):
        client = self.start_namespace()
        stats = self.adapter.ingest("question-1", [Session("empty", "2023/05/20", ())])
        source, transcript = client.mined_exports[0]
        self.assertEqual(source.suffix, ".txt")
        self.assertEqual(transcript, "")
        self.assertEqual(stats.sessions, 1)
        self.assertEqual(client.tool_calls()[0]["params"]["arguments"], {"source": str(source), "mode": "convos"})

    def test_single_user_turn_keeps_unicode_and_newlines_in_native_plaintext(self):
        client = self.start_namespace()
        date = "2023/05/20 (Sat) 14:30"
        content = "J’ai choisi Montréal.\nÀ demain 🌱."
        session = Session("one-user", date, (Turn("user", content),))
        self.adapter.ingest("question-1", [session])
        source, transcript = client.mined_exports[0]
        self.assertEqual(source.suffix, ".txt")
        self.assertEqual(transcript, f"> [Session date: {date}]\n{content}")

    def test_single_assistant_turn_keeps_unicode_and_newlines_in_native_plaintext(self):
        client = self.start_namespace()
        date = "2023/05/20 (Sat) 14:30"
        content = "Bibliothèque près du parc.\n開館は午前９時です。"
        session = Session("one-assistant", date, (Turn("assistant", content),))
        self.adapter.ingest("question-1", [session])
        source, transcript = client.mined_exports[0]
        self.assertEqual(source.suffix, ".txt")
        self.assertEqual(transcript, f"[Session date: {date}]\n{content}")

    def test_search_uses_only_query_and_limit_and_preserves_native_results(self):
        client = self.start_namespace()
        self.adapter.ingest("question-1", [self.session()])
        source = client.mined_exports[0][0]
        self.search_result = {"results": [{"text": "native verbatim\nresult", "source_path": str(source), "source_file": source.name, "similarity": 0.817}, {"text": "no reported source or score"}]}
        question = "Which library did I choose?"
        results = self.adapter.retrieve("question-1", question, 5, "2023/05/21 (Sun) 10:00")
        self.assertEqual(client.tool_calls()[-1]["params"], {"name": "mempalace_search", "arguments": {"query": question, "limit": 5}})
        self.assertEqual(results, [Retrieved("native verbatim\nresult", ("original-session",), 0.817), Retrieved("no reported source or score")])

    def test_basename_provenance_is_supported_without_guessing_unknown_sources(self):
        client = self.start_namespace()
        self.adapter.ingest("question-1", [self.session()])
        source = client.mined_exports[0][0]
        self.search_result = {"results": [{"text": "known", "source_file": source.name}, {"text": "unknown", "source_file": "unreported.json"}]}
        result = self.adapter.retrieve("question-1", "library", 2, None)
        self.assertEqual([hit.session_ids for hit in result], [("original-session",), ()])

    def test_query_is_sent_unchanged_for_native_sanitization(self):
        client = self.start_namespace()
        query = "Could you remind me " * 30 + "which library I chose?"
        self.adapter.retrieve("question-1", query, 5, None)
        self.assertEqual(client.tool_calls()[-1]["params"]["arguments"]["query"], query)

    def test_every_reset_restarts_into_a_different_store_and_clears_provenance(self):
        previous = self.start_namespace()
        self.adapter.ingest("question-1", [self.session()])
        old_source = previous.mined_exports[0][0]
        old_store = self.popen.call_args.args[0][-1]
        old_process = self.processes[-1]
        self.adapter.reset("question-1")
        self.assertNotEqual(old_store, self.popen.call_args.args[0][-1])
        self.assertTrue(previous.closed)
        old_process.terminate.assert_called_once()
        old_process.wait.assert_called_once_with(timeout=5.0)
        self.search_result = {"results": [{"text": "fixture unknown provenance", "source_path": str(old_source), "source_file": old_source.name}]}
        self.assertEqual(self.adapter.retrieve("question-1", "library", 1, None)[0].session_ids, ())
        self.adapter.reset("question-2")
        with self.assertRaisesRegex(RuntimeError, "reset"):
            self.adapter.retrieve("question-1", "library", 1, None)

    def test_unsafe_namespace_never_becomes_a_directory_component(self):
        client = self.start_namespace("../../outside")
        self.adapter.ingest("../../outside", [self.session()])
        self.assertTrue(Path(self.popen.call_args.args[0][-1]).is_relative_to(self.workdir))
        self.assertTrue(client.mined_exports[0][0].is_relative_to(self.workdir))

    def test_tool_errors_abort_instead_of_becoming_empty_retrieval(self):
        self.start_namespace()
        self.mine_result = {"success": False, "error": "fixture miner refused", "error_class": "MineAlreadyRunning"}
        with self.assertRaisesRegex(RuntimeError, "fixture miner refused"):
            self.adapter.ingest("question-1", [self.session()])
        self.search_result = {"error": "fixture query failed"}
        with self.assertRaisesRegex(RuntimeError, "fixture query failed"):
            self.adapter.retrieve("question-1", "library", 5, None)

    def test_json_rpc_errors_and_wrong_response_ids_are_not_scored(self):
        self.start_namespace()
        self.rpc_override = lambda body: {"jsonrpc": "2.0", "id": body["id"], "error": {"code": -32005, "message": "fixture stale library"}}
        with self.assertRaisesRegex(RuntimeError, "JSON-RPC error"):
            self.adapter.retrieve("question-1", "library", 5, None)
        self.rpc_override = lambda body: {**body, "id": body["id"] + 1}
        with self.assertRaisesRegex(RuntimeError, "invalid JSON-RPC response"):
            self.adapter.retrieve("question-1", "library", 5, None)

    def test_malformed_tool_content_and_result_list_are_rejected(self):
        self.start_namespace()
        self.rpc_override = lambda body: {**body, "result": {"content": [{"type": "text", "text": "not-json"}]}}
        with self.assertRaisesRegex(RuntimeError, "invalid JSON text"):
            self.adapter.retrieve("question-1", "library", 5, None)
        self.rpc_override = None
        self.search_result = {"results": None}
        with self.assertRaisesRegex(RuntimeError, "no results list"):
            self.adapter.retrieve("question-1", "library", 5, None)

    def test_reset_and_namespace_are_required(self):
        with self.assertRaisesRegex(RuntimeError, "start"):
            self.adapter.reset("question-1")
        self.adapter.start(self.workdir, None, None)
        with self.assertRaisesRegex(RuntimeError, "reset"):
            self.adapter.ingest("question-1", [self.session()])
        self.adapter.reset("question-1")
        with self.assertRaisesRegex(RuntimeError, "reset"):
            self.adapter.ingest("question-2", [self.session()])

    def test_documented_search_limit_is_validated_before_http(self):
        client = self.start_namespace()
        for limit in (0, 101):
            with self.assertRaisesRegex(ValueError, "between 1 and 100"):
                self.adapter.retrieve("question-1", "library", limit, None)
        self.assertEqual(client.tool_calls(), [])

    def test_invalid_ports_are_rejected_before_launch(self):
        for port in ("not-a-port", "0", "65536"):
            with patch.dict(mempalace.os.environ, {"H2H_PORT": port}):
                with self.assertRaisesRegex(ValueError, "H2H_PORT"):
                    self.adapter.start(self.workdir, None, None)
        with patch.dict(mempalace.os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "H2H_PORT"):
                self.adapter.start(self.workdir, None, None)
        self.popen.assert_not_called()

    def test_pin_mismatch_cleans_up_the_owned_child(self):
        self.server_version = "3.9.0"
        with self.assertRaisesRegex(RuntimeError, "3.10.0"):
            self.adapter.start(self.workdir, None, None)
        self.processes[0].terminate.assert_called_once()
        self.assertTrue(self.clients[0].closed)

    def test_missing_cli_is_reported_without_installing_it(self):
        self.popen.side_effect = FileNotFoundError("fixture CLI missing")
        with self.assertRaisesRegex(RuntimeError, "mempalace==3.10.0"):
            self.adapter.start(self.workdir, None, None)
        self.assertEqual(self.clients, [])

    def test_startup_deadline_cleans_up_the_owned_child(self):
        self.health_error = True
        with patch.object(mempalace.time, "monotonic", side_effect=[0.0, 61.0]):
            with self.assertRaisesRegex(RuntimeError, "within 60 seconds"):
                self.adapter.start(self.workdir, None, None)
        self.processes[0].terminate.assert_called_once()
        self.assertTrue(self.clients[0].closed)

    def test_stop_is_idempotent_and_escalates_only_its_owned_child(self):
        self.adapter.start(self.workdir, None, None)
        process = self.processes[-1]
        process.wait.side_effect = [subprocess.TimeoutExpired("fixture", 5.0), 0]
        self.adapter.stop()
        self.adapter.stop()
        process.terminate.assert_called_once()
        process.kill.assert_called_once()
        self.assertEqual(process.wait.call_count, 2)
        self.assertTrue(self.clients[-1].closed)


if __name__ == "__main__":
    unittest.main()
