"""Offline integration checks against the pinned request shapes in ai_memory.md.

All subprocess and HTTP operations are stubs. When core has not landed yet,
the fixed interface is copied here in memory; no h2h/types.py is written.
The HTTP package is also stubbed while loading this isolated test module, so
these checks require only unittest, even on a source-builder host without httpx.
"""

from collections import deque
from dataclasses import dataclass, field
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import ModuleType, SimpleNamespace
from typing import Protocol
from unittest import TestCase, main
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit
import uuid


HARNESS = Path(__file__).resolve().parents[1]
SOURCE = HARNESS / "h2h" / "adapters" / "ai_memory.py"


def local_interface() -> ModuleType:
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

    module = ModuleType("h2h.types")
    for cls in (Turn, Session, Retrieved, ModelRoute, IngestStats, MemoryAdapter):
        setattr(module, cls.__name__, cls)
    return module


def load_source() -> tuple[ModuleType, ModuleType]:
    # A real core interface, if present, wins. This does not import adapters or
    # create any package files. Each module gets its own imports for isolation.
    if (HARNESS / "h2h" / "types.py").is_file():
        spec = importlib.util.spec_from_file_location("h2h.types", HARNESS / "h2h" / "types.py")
        assert spec and spec.loader
        interface = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"h2h.types": interface}):
            spec.loader.exec_module(interface)
    else:
        interface = local_interface()

    http = ModuleType("httpx")
    http.Client = Mock(name="offline_http_client")
    http.HTTPError = type("OfflineHTTPError", (Exception,), {})
    spec = importlib.util.spec_from_file_location("offline_ai_memory_adapter", SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"h2h.types": interface, "httpx": http}):
        spec.loader.exec_module(module)
    return module, interface


adapter_source, interface = load_source()
Turn, Session, ModelRoute = interface.Turn, interface.Session, interface.ModelRoute


class Response:
    def __init__(self, payload=None, *, status=200, text=None, content_type="application/json"):
        self.payload = payload
        self.status_code = status
        self.text = text if text is not None else json.dumps(payload)
        self.headers = {"content-type": content_type}

    def json(self):
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise adapter_source.httpx.HTTPError("offline HTTP failure")


class Client:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.closed = False
        self.get_calls = []
        self.post_calls = []
        self.hook_replies = deque()
        self.rpc_replies = deque()
        self.get_replies = deque()

    def get(self, path, **kwargs):
        self.get_calls.append((path, kwargs))
        if self.get_replies:
            reply = self.get_replies.popleft()
            if isinstance(reply, Exception):
                raise reply
            return reply
        return Response({"status": "ok"})

    def post(self, path, **kwargs):
        self.post_calls.append((path, json.loads(json.dumps(kwargs))))
        if path == "/hook/batch":
            return self.hook_replies.popleft() if self.hook_replies else Response({"accepted": 1})
        if path == "/mcp":
            request = kwargs["json"]
            if self.rpc_replies:
                reply = self.rpc_replies.popleft()
                return reply(request) if callable(reply) else reply
            return rpc_response(request, {"hits": [], "raw_hits": []})
        raise AssertionError(f"Undocumented test endpoint: {path}")

    def close(self):
        self.closed = True


def rpc_response(request, payload):
    return Response({
        "jsonrpc": "2.0", "id": request["id"],
        "result": {"content": [{"type": "text", "text": json.dumps(payload)}]},
    })


class AdapterTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ai-memory-contract-test-")
        self.addCleanup(self.tmp.cleanup)
        self.clients = []
        self.processes = []
        self.env_patch = patch.dict(adapter_source.os.environ, {
            "H2H_PORT": "61234", "PATH": "/offline/native/bin",
            "AI_MEMORY_CAPTURE_ASSISTANT": "true", "AI_MEMORY_RERANKER": "llm",
            "AI_MEMORY_LLM_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": "unused-test-value",
            "AI_MEMORY_DATA_DIR": "/unused", "AI_MEMORY_BASE_PATH": "/unused",
            "HTTP_PROXY": "http://unused.invalid", "LLM_API_KEY": "unused-test-value",
        }, clear=True)
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)
        self.run = self.enterContext(patch.object(adapter_source.subprocess, "run", return_value=SimpleNamespace(
            returncode=0, stdout="ai-memory 2.5.2\n",
        )))
        self.popen = self.enterContext(patch.object(adapter_source.subprocess, "Popen", side_effect=self.make_process))
        self.enterContext(patch.object(adapter_source.httpx, "Client", side_effect=self.make_client))
        self.sleep = self.enterContext(patch.object(adapter_source.time, "sleep"))
        self.adapter = adapter_source.build()
        self.addCleanup(lambda: self.adapter.stop())

    def make_process(self, *args, **kwargs):
        proc = Mock(spec=["poll", "terminate", "wait", "kill"])
        proc.poll.return_value = None
        proc.wait.return_value = 0
        self.processes.append(proc)
        return proc

    def make_client(self, **kwargs):
        client = Client(**kwargs)
        self.clients.append(client)
        return client

    def start(self, *, llm=None, embed=None):
        self.adapter.start(Path(self.tmp.name), llm, embed)

    def ready(self):
        self.start()
        self.adapter.reset("question-one")
        return self.clients[-1]

    def sample(self, sid="sharegpt-s1"):
        return Session(sid, "2023/05/20 (Sat) 02:21", (
            Turn("user", "I chose the blue bicycle."), Turn("assistant", "ASSISTANT_SENTINEL"),
        ))

    def test_import_has_no_process_or_network_side_effects(self):
        with patch.object(subprocess, "Popen", side_effect=AssertionError("import launched a process")), \
             patch.object(subprocess, "run", side_effect=AssertionError("import launched a command")):
            module, _ = load_source()
        module.httpx.Client.assert_not_called()

    def test_builders_and_instances(self):
        llm = adapter_source.build_llm()
        self.assertEqual((self.adapter.name, self.adapter.version, self.adapter.needs_llm), ("ai-memory", "v2.5.2", False))
        self.assertEqual((llm.name, llm.version, llm.needs_llm), ("ai-memory-llm", "v2.5.2", True))
        self.assertIsNot(self.adapter._session_ids, adapter_source.build()._session_ids)

    def test_start_uses_native_loopback_defaults_and_private_data_directory(self):
        self.start()
        self.assertEqual(self.run.call_args.args[0], ["ai-memory", "--version"])
        args, kwargs = self.popen.call_args
        self.assertEqual(args[0], ["ai-memory", "serve", "--transport", "http", "--bind", "127.0.0.1:61234", "--data-dir", str(self.adapter._data_dir)])
        self.assertEqual(kwargs["env"], {"PATH": "/offline/native/bin", "AI_MEMORY_EMBEDDING_PROVIDER": "local"})
        self.assertEqual(kwargs["cwd"], self.adapter._data_dir)
        self.assertEqual(self.adapter._data_dir.parent, Path(self.tmp.name))
        self.assertEqual(self.clients[-1].get_calls, [("/healthz", {"timeout": 1.0})])
        self.assertEqual(self.clients[-1].kwargs, {"base_url": "http://127.0.0.1:61234", "timeout": 960.0, "trust_env": False})

    def test_llm_route_and_key_are_only_child_environment_values(self):
        self.adapter = adapter_source.build_llm()
        with patch.dict(adapter_source.os.environ, {"MY_TEST_ROUTE_KEY": "synthetic-route-key"}):
            self.start(llm=ModelRoute("http://127.0.0.1:61235/v1/", "common-model", "MY_TEST_ROUTE_KEY"))
        env = self.popen.call_args.kwargs["env"]
        self.assertEqual(env["AI_MEMORY_LLM_PROVIDER"], "openai-compat")
        self.assertEqual(env["AI_MEMORY_LLM_BASE_URL"], "http://127.0.0.1:61235/v1")
        self.assertEqual(env["AI_MEMORY_LLM_MODEL"], "common-model")
        self.assertEqual(env["LLM_API_KEY"], "synthetic-route-key")
        self.assertNotIn("MY_TEST_ROUTE_KEY", env)
        self.assertNotIn("AI_MEMORY_CONSOLIDATE_ON_SESSION_END", env)
        self.assertEqual(list(Path(self.tmp.name).rglob("config.toml")), [])
        self.assertEqual([p for p in Path(self.tmp.name).rglob("*") if p.is_file()], [])

    def test_keyless_openai_compatible_llm_is_allowed(self):
        self.adapter = adapter_source.build_llm()
        self.start(llm=ModelRoute("http://127.0.0.1:61235/v1", "common-model"))
        self.assertNotIn("LLM_API_KEY", self.popen.call_args.kwargs["env"])

    def test_llm_builder_requires_a_route_before_launch(self):
        self.adapter = adapter_source.build_llm()
        with self.assertRaisesRegex(ValueError, "requires an OpenAI-compatible"):
            self.start()
        self.run.assert_not_called()
        self.popen.assert_not_called()

    def test_invalid_llm_urls_or_missing_models_are_rejected(self):
        self.adapter = adapter_source.build_llm()
        for url, model in [("ftp://host/v1", "m"), ("http://user:password@host/v1", "m"), ("http://host/v1?key=test", "m"), ("http://host/v1#fragment", "m"), ("http://host/v1", " ")]:
            with self.subTest(url=url), self.assertRaises(ValueError):
                self.start(llm=ModelRoute(url, model))
        self.popen.assert_not_called()

    def test_port_is_required_and_checked_without_opening_a_socket(self):
        for value in ("", "wrong", "0", "65536"):
            with self.subTest(value=value), patch.dict(adapter_source.os.environ, {"H2H_PORT": value}), self.assertRaises(ValueError):
                self.start()
        self.popen.assert_not_called()

    def test_wrong_native_version_is_rejected_before_serve(self):
        self.run.return_value.stdout = "ai-memory 2.4.2\n"
        with self.assertRaisesRegex(RuntimeError, "native v2.5.2"):
            self.start()
        self.popen.assert_not_called()

    def test_missing_native_binary_is_an_install_error(self):
        self.run.side_effect = FileNotFoundError()
        with self.assertRaisesRegex(RuntimeError, "Install the native"):
            self.start()
        self.popen.assert_not_called()

    def test_startup_exit_cleans_up_without_falling_back_to_fts(self):
        proc = self.make_process()
        proc.poll.return_value = 1
        self.popen.side_effect = None
        self.popen.return_value = proc
        with self.assertRaisesRegex(RuntimeError, "local embeddings must load"):
            self.start()
        self.assertTrue(self.clients[-1].closed)
        self.assertIsNone(self.adapter._process)
        self.assertIsNone(self.adapter._workdir)

    def test_readiness_retries_connection_errors(self):
        client = Client()
        client.get_replies.append(adapter_source.httpx.HTTPError("not listening yet"))
        with patch.object(adapter_source.httpx, "Client", return_value=client):
            self.start()
        self.assertEqual(len(client.get_calls), 2)
        self.sleep.assert_called_once_with(0.2)

    def test_readiness_deadline_cleans_up_owned_process(self):
        with patch.object(adapter_source.time, "monotonic", side_effect=[0.0, 601.0]):
            with self.assertRaisesRegex(RuntimeError, "within 600 seconds"):
                self.start()
        self.processes[-1].terminate.assert_called_once()
        self.assertTrue(self.clients[-1].closed)

    def test_reset_is_fresh_even_for_the_same_namespace(self):
        client = self.ready()
        old_store = self.adapter._data_dir
        (old_store / "old-memory.md").write_text("old namespace memory", encoding="utf-8")
        self.adapter._session_ids["old"] = "old-dataset-id"
        self.adapter.reset("question-one")
        self.assertNotEqual(old_store, self.adapter._data_dir)
        self.assertEqual(self.adapter._session_ids, {})
        self.assertTrue(client.closed)
        self.assertTrue((old_store / "old-memory.md").is_file())
        self.assertFalse((self.adapter._data_dir / "old-memory.md").exists())
        with self.assertRaises(RuntimeError):
            self.adapter.retrieve("question-two", "query", 1, None)

    def test_reset_copies_only_the_three_immutable_model_files(self):
        self.ready()
        model = self.adapter._data_dir / "models" / "all-MiniLM-L6-v2"
        model.mkdir(parents=True)
        for filename in ("config.json", "tokenizer.json", "model.safetensors", "foreign-memory.md"):
            (model / filename).write_text(filename, encoding="utf-8")
        self.adapter.reset("question-two")
        copied = self.adapter._data_dir / "models" / "all-MiniLM-L6-v2"
        self.assertEqual(sorted(p.name for p in copied.iterdir()), ["config.json", "model.safetensors", "tokenizer.json"])

    def test_reset_requires_start_and_namespace_is_required(self):
        with self.assertRaisesRegex(RuntimeError, "start"):
            self.adapter.reset("q")
        self.start()
        with self.assertRaises(ValueError):
            self.adapter.reset("")
        with self.assertRaisesRegex(RuntimeError, "reset"):
            self.adapter.ingest("q", [])

    def test_stop_is_idempotent_and_signals_only_owned_child(self):
        self.start()
        proc = self.processes[-1]
        proc.wait.side_effect = [subprocess.TimeoutExpired("owned-child", 15), 0]
        self.adapter.stop()
        self.adapter.stop()
        proc.terminate.assert_called_once()
        proc.kill.assert_called_once()
        self.assertEqual(proc.wait.call_count, 2)
        self.assertTrue(self.clients[-1].closed)
        self.assertEqual(self.adapter._env, {})

    def test_failure_to_reap_child_prevents_replacement_server(self):
        self.ready()
        proc = self.processes[-1]
        proc.wait.side_effect = subprocess.TimeoutExpired("owned-child", 15)
        count = self.popen.call_count
        with self.assertRaises(subprocess.TimeoutExpired):
            self.adapter.reset("question-two")
        self.assertEqual(self.popen.call_count, count)
        self.assertIs(self.adapter._process, proc)
        self.assertIsNone(self.adapter._namespace)
        proc.wait.side_effect = None

    def test_hook_replay_matches_defaults_and_keeps_session_dates(self):
        client = self.ready()
        stats = self.adapter.ingest("question-one", [self.sample("id &/é")])
        calls = client.post_calls
        self.assertEqual(len(calls), 4)
        events = []
        for path, kwargs in calls:
            self.assertEqual(path, "/hook/batch")
            self.assertEqual(len(kwargs["json"]), 1)
            item = kwargs["json"][0]
            query = parse_qs(urlsplit(item["url"]).query)
            events.append(query["event"][0])
            self.assertEqual(query["workspace"], ["longmemeval"])
            self.assertEqual(query["project"], [self.adapter._project])
            self.assertEqual(query["agent"], ["claude-code"])
            self.assertEqual(query["session_id"], ["id &/é"])
            self.assertNotIn("capture_assistant", query)
            self.assertEqual(item["body"]["session_id"], "id &/é")
            self.assertEqual(item["body"]["cwd"], str(self.adapter._cwd))
        self.assertEqual(events, ["session-start", "user-prompt-submit", "stop", "session-end"])
        self.assertEqual(calls[0][1]["json"][0]["body"]["source"], "startup")
        self.assertEqual(calls[1][1]["json"][0]["body"]["prompt"], "[session date: 2023/05/20 (Sat) 02:21] I chose the blue bicycle.")
        self.assertNotIn("ASSISTANT_SENTINEL", json.dumps(calls))
        self.assertNotIn("_ai_memory_assistant", json.dumps(calls))
        self.assertEqual(calls[-1][1]["json"][0]["body"]["reason"], "exit")
        self.assertEqual(stats.sessions, 1)
        self.assertGreaterEqual(stats.seconds, 0)
        self.assertIsNone(stats.llm_calls)
        self.assertTrue(any("Assistant text is not stored" in note for note in stats.notes))

    def test_user_prompt_is_not_rewritten_or_capped_by_adapter(self):
        client = self.ready()
        content = "é" * 12000
        self.adapter.ingest("question-one", [Session("long", "unchanged date", (Turn("user", content),))])
        self.assertEqual(client.post_calls[1][1]["json"][0]["body"]["prompt"], f"[session date: unchanged date] {content}")

    def test_session_order_is_preserved_and_namespace_mismatch_cannot_send(self):
        client = self.ready()
        self.adapter.ingest("question-one", [self.sample("old"), self.sample("new")])
        ids = [kwargs["json"][0]["body"]["session_id"] for _, kwargs in client.post_calls]
        self.assertEqual(ids, ["old"] * 4 + ["new"] * 4)
        before = len(client.post_calls)
        with self.assertRaises(RuntimeError):
            self.adapter.ingest("different-question", [self.sample()])
        self.assertEqual(len(client.post_calls), before)

    def test_singleton_acknowledgements_retry_before_next_event(self):
        client = self.ready()
        client.hook_replies.extend([Response({"accepted": 0, "accepted_indices": []}), Response({"accepted": 0, "accepted_indices": [0]})])
        self.adapter.ingest("question-one", [self.sample()])
        self.assertEqual(client.post_calls[0], client.post_calls[1])
        self.assertEqual(parse_qs(urlsplit(client.post_calls[2][1]["json"][0]["url"]).query)["event"], ["user-prompt-submit"])
        self.sleep.assert_called_once_with(0.5)

    def test_failed_or_invalid_hook_acknowledgements_do_not_silently_succeed(self):
        client = self.ready()
        for ack in ({"accepted": 0, "failed_index": 0}, {}, {"accepted": 2}, {"accepted": True}, {"accepted_indices": [1]}, {"accepted_indices": [0, 0]}, []):
            with self.subTest(ack=ack):
                client.hook_replies.append(Response(ack))
                with self.assertRaises(RuntimeError):
                    self.adapter.ingest("question-one", [self.sample()])

    def test_unacknowledged_event_stops_after_bounded_retries(self):
        client = self.ready()
        client.hook_replies.extend(Response({"accepted": 0}) for _ in range(60))
        with self.assertRaisesRegex(RuntimeError, "60 attempts"):
            self.adapter.ingest("question-one", [self.sample()])
        self.assertEqual(len(client.post_calls), 60)
        self.assertEqual(self.sleep.call_count, 59)

    def test_invalid_roles_and_duplicate_native_ids_fail_before_ingestion(self):
        client = self.ready()
        with self.assertRaises(ValueError):
            self.adapter.ingest("question-one", [Session("bad", "date", (Turn("system", "bad"),))])
        native = str(uuid.uuid5(uuid.NAMESPACE_OID, "sharegpt-s1"))
        with self.assertRaises(ValueError):
            self.adapter.ingest("question-one", [self.sample(), self.sample(native)])
        self.assertEqual(client.post_calls, [])
        self.adapter.ingest("question-one", [self.sample()])
        with self.assertRaises(ValueError):
            self.adapter.ingest("question-one", [self.sample()])

    def test_empty_input_does_not_contact_the_system(self):
        client = self.ready()
        self.assertEqual(self.adapter.ingest("question-one", []).sessions, 0)
        self.assertEqual(client.post_calls, [])

    def test_llm_consolidation_uses_uuid_and_only_default_tool_parameters(self):
        self.adapter = adapter_source.build_llm()
        self.start(llm=ModelRoute("http://127.0.0.1:61235/v1", "common-model"))
        self.adapter.reset("question-one")
        client = self.clients[-1]
        stats = self.adapter.ingest("question-one", [self.sample("first"), self.sample("second")])
        self.assertIsNone(stats.llm_calls)
        self.assertTrue(any("background review" in note for note in stats.notes))
        methods = [path for path, _ in client.post_calls]
        self.assertEqual(methods, ["/hook/batch"] * 4 + ["/mcp"] + ["/hook/batch"] * 4 + ["/mcp"])
        rpc_calls = [kwargs for path, kwargs in client.post_calls if path == "/mcp"]
        for sid, kwargs in zip(("first", "second"), rpc_calls, strict=True):
            self.assertEqual(kwargs["json"]["params"], {"name": "memory_consolidate", "arguments": {"session_id": str(uuid.uuid5(uuid.NAMESPACE_OID, sid))}})

    def test_llm_does_not_consolidate_lifecycle_only_session(self):
        self.adapter = adapter_source.build_llm()
        self.start(llm=ModelRoute("http://127.0.0.1:61235/v1", "common-model"))
        self.adapter.reset("question-one")
        self.adapter.ingest("question-one", [Session("empty", "date", ())])
        self.assertEqual([p for p, _ in self.clients[-1].post_calls], ["/hook/batch", "/hook/batch"])

    def test_external_embedding_route_does_not_override_required_local_model(self):
        self.start(embed=ModelRoute("http://127.0.0.1:61236/v1", "unused-remote-model"))
        self.adapter.reset("question-one")
        stats = self.adapter.ingest("question-one", [])
        self.assertEqual(self.popen.call_args.kwargs["env"]["AI_MEMORY_EMBEDDING_PROVIDER"], "local")
        self.assertNotIn("AI_MEMORY_EMBEDDING_BASE_URL", self.popen.call_args.kwargs["env"])
        self.assertTrue(any("embedding route is unused" in note for note in stats.notes))

    def test_recall_request_and_page_snippets_use_official_shapes(self):
        client = self.ready()
        self.adapter.ingest("question-one", [self.sample()])
        native = str(uuid.uuid5(uuid.NAMESPACE_OID, "sharegpt-s1"))
        client.rpc_replies.append(lambda req: rpc_response(req, {"hits": [
            {"path": f"sessions/{native}.md", "title": "Bicycle", "snippet": "<mark>blue</mark>", "rank": -0.12},
            {"path": "decisions/bicycle.md", "title": "Decision", "snippet": "plain text", "rank": -0.09},
        ]}))
        out = self.adapter.retrieve("question-one", "Which bicycle?", 2, "2023/06/01 (Thu) 12:30")
        path, kwargs = client.post_calls[-1]
        self.assertEqual(path, "/mcp")
        self.assertEqual(kwargs["headers"], {"Accept": "application/json, text/event-stream"})
        self.assertEqual(kwargs["json"], {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "memory_query", "arguments": {"query": "Which bicycle?", "workspace": "longmemeval", "project": self.adapter._project, "limit": 2}}})
        self.assertEqual(out[0].text, "Bicycle\n<mark>blue</mark>")
        self.assertEqual(out[0].session_ids, ("sharegpt-s1",))
        self.assertEqual(out[0].score, -0.12)
        self.assertEqual(out[1].session_ids, ())

    def test_raw_provenance_maps_native_uuid_back_to_dataset_id(self):
        client = self.ready()
        self.adapter.ingest("question-one", [self.sample()])
        native = str(uuid.uuid5(uuid.NAMESPACE_OID, "sharegpt-s1"))
        client.rpc_replies.append(lambda req: rpc_response(req, {"raw_hits": [{"session_id": native, "title": "prompt", "snippet": "bicycle", "rank": -0.2}]}))
        out = self.adapter.retrieve("question-one", "bicycle", 1, None)
        self.assertEqual(out[0].session_ids, ("sharegpt-s1",))

    def test_native_uuid_is_preserved_for_session_consolidation_and_provenance(self):
        value = str(uuid.uuid5(uuid.NAMESPACE_OID, "native-session-fixture"))
        self.assertEqual(self.adapter._stored_session_id(value), value)

    def test_result_order_is_pages_then_raw_with_at_most_k_hits(self):
        client = self.ready()
        client.rpc_replies.append(lambda req: rpc_response(req, {"hits": [{"path": "page.md", "title": "page", "snippet": "p"}], "raw_hits": [{"session_id": str(uuid.uuid5(uuid.NAMESPACE_OID, "native-session-fixture")), "title": "raw", "snippet": "r"}]}))
        out = self.adapter.retrieve("question-one", "query", 1, None)
        self.assertEqual([r.text for r in out], ["page\np"])
        self.assertIsNone(out[0].score)

    def test_sse_ignores_notifications_and_other_ids(self):
        client = self.ready()
        def reply(req):
            final = rpc_response(req, {"hits": [{"path": "p.md", "title": "right", "snippet": "context"}]}).text
            return Response(text=': keepalive\n\ndata: {"method":"notification"}\n\ndata: {"id":999,"result":{}}\n\ndata: invalid\n\ndata: ' + final + '\n\n', content_type="text/event-stream; charset=utf-8")
        client.rpc_replies.append(reply)
        self.assertEqual(self.adapter.retrieve("question-one", "query", 1, None)[0].text, "right\ncontext")

    def test_mcp_and_http_errors_are_not_returned_as_empty_retrieval(self):
        client = self.ready()
        replies = [
            Response({"jsonrpc": "2.0", "id": 1, "error": {"code": -32603, "message": "failure"}}),
            lambda req: Response({"id": req["id"], "result": {"isError": True}}),
            lambda req: Response({"id": req["id"], "result": {"content": []}}),
            Response({"id": 999, "result": {}}),
            Response(text="data: {}\n", content_type="text/event-stream"),
        ]
        for reply in replies:
            client.rpc_replies.append(reply)
            with self.assertRaises(RuntimeError):
                self.adapter.retrieve("question-one", "query", 1, None)
        client.rpc_replies.append(Response({}, status=503))
        with self.assertRaises(adapter_source.httpx.HTTPError):
            self.adapter.retrieve("question-one", "query", 1, None)

    def test_k_outside_upstream_limit_is_rejected_without_request(self):
        client = self.ready()
        for k in (0, 101, -1, True):
            with self.subTest(k=k), self.assertRaises(ValueError):
                self.adapter.retrieve("question-one", "query", k, None)
        self.assertEqual(client.post_calls, [])

    def test_dead_owned_server_is_reported_before_http_request(self):
        client = self.ready()
        self.processes[-1].poll.return_value = 1
        with self.assertRaisesRegex(RuntimeError, "no longer running"):
            self.adapter.retrieve("question-one", "query", 1, None)
        self.assertEqual(client.post_calls, [])


if __name__ == "__main__":
    main()
