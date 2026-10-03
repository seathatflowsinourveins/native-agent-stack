#!/usr/bin/env -S uv run --locked --script
# /// script
# requires-python = ">=3.13,<3.14"
# dependencies = [
#     "openai-codex==0.160.0",
# ]
# ///
"""Local integration fixtures, not upstream tests or provider/model acceptance.

The SSE fixture derives from openai/codex rust-v0.160.0
codex-rs/core/tests/common/responses.rs::{sse,ev_response_created,
ev_assistant_message,ev_completed}. The SDK and bundled native runtime are real;
the loopback provider returns authored deterministic fixture responses.
The stdio MCP fixture derives from the same pin's
scripts/mcp_conformance/server.py::{ProtocolServer._handle_legacy,_list_tools,
run_stdio}. Its catalog responses are synthetic; no tool/model execution is
accepted by these discovery checks.
"""

import asyncio
import contextlib
import io
import json
import os
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import tomllib
import worker
from openai_codex import AsyncCodex, AsyncThread
from openai_codex.client import CodexClient

MCP_FIXTURE = r"""
import json
import sys
import time
from pathlib import Path

for line in sys.stdin:
    message = json.loads(line)
    method = message.get("method")
    with Path(sys.argv[1]).open("a") as log:
        log.write(json.dumps({"method": method}) + "\n")
    if "id" not in message:
        continue
    if method == "initialize":
        result = {
            "protocolVersion": "2025-06-18",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "native-fixture", "version": "1.0.0"},
        }
    elif method == "tools/list":
        if sys.argv[2] == "stall":
            time.sleep(30)
        if sys.argv[2] == "error":
            print(json.dumps({"jsonrpc": "2.0", "id": message["id"],
                              "error": {"code": -32603, "message": "PRIVATE_TOOL_ERROR"}}),
                  flush=True)
            continue
        result = {"tools": [] if sys.argv[2] == "empty" else [{
            "name": "fixture_echo", "description": "PRIVATE_TOOL_DESCRIPTION",
            "inputSchema": {"type": "object", "properties": {}},
        }]}
    elif method == "resources/list":
        result = {"resources": []}
    elif method == "resources/templates/list":
        result = {"resourceTemplates": []}
    else:
        print(json.dumps({"jsonrpc": "2.0", "id": message["id"],
                          "error": {"code": -32601, "message": "method not found"}}),
              flush=True)
        continue
    print(json.dumps({"jsonrpc": "2.0", "id": message["id"], "result": result}), flush=True)
"""


class FixtureGateway:
    def __init__(self, mode="complete"):
        self.mode = mode
        self.requests = []
        self.release = threading.Event()
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                index = len(owner.requests)
                owner.requests.append(
                    {
                        "path": self.path,
                        "body": body,
                        "request_id": self.headers.get("x-request-id"),
                        "has_authorization": "authorization" in self.headers,
                    }
                )
                response_id = f"fixture_response_{index}"
                events = [
                    {"type": "response.created", "response": {"id": response_id}},
                    {
                        "type": "response.output_item.done",
                        "item": {
                            "type": "message",
                            "role": "assistant",
                            "id": f"fixture_message_{index}",
                            "content": [{"type": "output_text", "text": f"fixture answer {index}"}],
                        },
                    },
                ]
                if owner.mode == "complete":
                    input_tokens, cached_tokens, output_tokens, reasoning_tokens = (
                        (20, 5, 4, 2) if index == 0 else (30, 10, 6, 4)
                    )
                    events.append(
                        {
                            "type": "response.completed",
                            "response": {
                                "id": response_id,
                                "usage": {
                                    "input_tokens": input_tokens,
                                    "input_tokens_details": {"cached_tokens": cached_tokens},
                                    "output_tokens": output_tokens,
                                    "output_tokens_details": {"reasoning_tokens": reasoning_tokens},
                                    "total_tokens": input_tokens + output_tokens,
                                },
                            },
                        }
                    )
                elif owner.mode == "content_filter":
                    # Native SSE shape: a956835d codex-api/src/sse/responses.rs:418-430.
                    events = [
                        events[0],
                        {
                            "type": "response.incomplete",
                            "response": {
                                "id": response_id,
                                "incomplete_details": {"reason": "content_filter"},
                            },
                        },
                    ]
                encoded = "".join(
                    f"event: {event['type']}\ndata: {json.dumps(event)}\n\n" for event in events
                ).encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                if owner.mode == "stall":
                    owner.release.wait(10)
                try:
                    self.wfile.write(encoded)
                except (BrokenPipeError, ConnectionResetError):
                    pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.url = f"http://127.0.0.1:{self.server.server_port}/v1"

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.release.set()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)


class NativeTransportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name) / "project"
        self.home = Path(self.temp.name) / "codex-home"
        self.project.mkdir()
        self.home.mkdir(mode=0o700)
        # Gate the unused curated Git sync in every fixture home, including
        # metadata-only fixtures. Source: a956835d core-plugins/src/manager.rs:753.
        (self.home / "config.toml").write_text("[features]\nplugins = false\n")

    def tearDown(self):
        self.assertFalse(list(self.home.glob(".tmp/plugins-clone-*")))

    def args(self, gateway, *extra):
        return worker.parse_args(
            [
                "--workspace",
                str(self.project),
                "--codex-home",
                str(self.home),
                "--base-url",
                gateway.url,
                "--request-id",
                "fixture-owned-request",
                "--sandbox",
                "read-only",
                "--timeout",
                "15",
                "--no-provider-retries",
                *extra,
            ]
        )

    def run_worker(self, args, *, sdk_factory=None, prompt="One bounded fixture task."):
        events = []
        instances, owned_pids = [], []

        class ObservedPreflightClient(worker.AsyncCodexClient):
            async def initialize(self):
                metadata = await super().initialize()
                # Observation of this test's own process, never production API.
                owned_pids.append(self._sync._proc.pid)
                return metadata

        def create_sdk(config):
            factory = sdk_factory or (ObservedPreflightClient if args.preflight else AsyncCodex)
            instance = factory(config=config)
            instances.append(instance)
            return instance

        def observe(event):
            events.append(event)
            # Observation only: inspect the PID of this test's own SDK child.
            # Pinned internals: sdk/python/src/openai_codex/client.py::CodexClient.start.
            process = (
                instances[-1]._sync._proc if args.preflight else instances[-1]._client._sync._proc
            )
            if process is not None:
                owned_pids.append(process.pid)

        invocation = (
            worker.run_preflight(args, sdk_factory=create_sdk, on_event=observe)
            if args.preflight
            else worker.run_worker(args, prompt, sdk_factory=create_sdk, on_event=observe)
        )
        result = asyncio.run(invocation)
        for pid in owned_pids:
            with self.assertRaises(ProcessLookupError):
                os.kill(pid, 0)
        return result, events

    def preflight_config(self, *, mcp_mode="complete", enabled=True):
        script = self.project / "fixture_mcp.py"
        script.write_text(MCP_FIXTURE)
        log = self.project / "fixture_mcp_calls.jsonl"
        skill = self.project / ".agents/skills/fixture-skill/SKILL.md"
        skill.parent.mkdir(parents=True, exist_ok=True)
        skill.write_text(
            "---\nname: fixture-skill\ndescription: PRIVATE_SKILL_DESCRIPTION\n---\n"
            "PRIVATE_SKILL_BODY\n"
        )
        role = self.home / "fixture-verifier.toml"
        role.write_text(
            f'model = {json.dumps(worker.DEFAULT_MODEL)}\nmodel_reasoning_effort = "max"\n'
        )
        config = (
            "[features]\nplugins = false\n"
            "[mcp_servers.fixture-mcp]\n"
            f"command = {json.dumps(sys.executable)}\n"
            f"args = {json.dumps([str(script), str(log), mcp_mode])}\n"
            f"enabled = {str(enabled).lower()}\n"
            "startup_timeout_sec = 5.0\n"
            "[agents]\n"
            "enabled = true\n"
            "max_concurrent_threads_per_session = 3\n"
            f"default_subagent_model = {json.dumps(worker.DEFAULT_MODEL)}\n"
            'default_subagent_reasoning_effort = "max"\n'
            "[agents.fixture-verifier]\n"
            'description = "PRIVATE_ROLE_DESCRIPTION"\n'
            f"config_file = {json.dumps(str(role))}\n"
            f"[projects.{json.dumps(str(self.project))}]\n"
            'trust_level = "trusted"\n'
        )
        (self.home / "config.toml").write_text(config)
        return log

    def assert_accepted(self, result):
        self.assertEqual(result["status"], "completed", result)
        self.assertEqual(result["thread_status"], {"type": "idle"}, result)
        self.assertEqual(result["cleanup_status"], "closed", result)
        self.assertEqual(result["usage_status"], "reported", result)
        self.assertEqual(result["usage_scope"], "native_thread_cumulative", result)

    def test_native_payload_header_tools_and_nonadditive_resume(self):
        with FixtureGateway() as gateway:
            first, events = self.run_worker(self.args(gateway))
            self.assert_accepted(first)
            self.assertEqual(first["final_response"], "fixture answer 0")
            self.assertEqual(events[0]["event"], "thread_ready")
            second, _ = self.run_worker(self.args(gateway, "--resume", first["thread_id"]))
            self.assert_accepted(second)
            self.assertEqual(second["thread_id"], first["thread_id"])
            self.assertEqual(second["thread_mode"], "resumed")
            self.assertEqual(len(gateway.requests), 2)
            for request in gateway.requests:
                self.assertEqual(request["path"], "/v1/responses")
                self.assertEqual(request["request_id"], "fixture-owned-request")
                self.assertFalse(request["has_authorization"])
                self.assertEqual(request["body"]["model"], worker.DEFAULT_MODEL)
                self.assertEqual(request["body"]["reasoning"]["effort"], "max")
                # Native Sol/Astra ResponsesLite carries tools inside input.
                # Source: core/src/client.rs:902–933 at rust-v0.160.0.
                tool_prefix = request["body"]["input"][0]
                self.assertEqual(tool_prefix["type"], "additional_tools")
                self.assertTrue(tool_prefix["tools"])
                self.assertIn("functions", [tool.get("name") for tool in tool_prefix["tools"]])
            self.assertEqual(
                gateway.requests[0]["body"]["prompt_cache_key"],
                gateway.requests[1]["body"]["prompt_cache_key"],
            )
            self.assertEqual(
                gateway.requests[0]["body"]["input"][0]["id"],
                gateway.requests[1]["body"]["input"][0]["id"],
            )
            self.assertIn("fixture answer 0", json.dumps(gateway.requests[1]["body"]["input"]))
            first_total, second_total = first["usage"]["total"], second["usage"]["total"]
            self.assertEqual(first_total["inputTokens"], 20)
            self.assertEqual(first_total["outputTokens"], 4)
            self.assertEqual(first_total["cachedInputTokens"], 5)
            self.assertEqual(first_total["reasoningOutputTokens"], 2)
            self.assertEqual(second_total["inputTokens"], 50)
            self.assertEqual(second_total["outputTokens"], 10)
            self.assertEqual(second_total["cachedInputTokens"], 15)
            self.assertEqual(second_total["reasoningOutputTokens"], 6)
            # Cached/reasoning counters are subsets; never add them to total.
            self.assertEqual(second_total["totalTokens"], 60)
            self.assertEqual(second["usage"]["last"]["totalTokens"], 36)

    def test_explicit_astra_model_is_preserved(self):
        with FixtureGateway() as gateway:
            selected = "cx/gpt-6-astra-max"
            result, _ = self.run_worker(self.args(gateway, "--model", selected))
            self.assert_accepted(result)
            self.assertEqual(gateway.requests[0]["body"]["model"], selected)
            self.assertEqual(gateway.requests[0]["body"]["reasoning"]["effort"], "max")

    def test_gateway_runtime_config_keeps_native_catalog_matching(self):
        with FixtureGateway() as gateway:
            config = worker.runtime_config(self.args(gateway))
            self.assertFalse(any("model_catalog_url" in value for value in config.config_overrides))
            self.assertIn("features.plugins=false", config.config_overrides)

    def test_gateway_key_binding_is_excluded_from_worker_shells(self):
        for name in ["OMNIROUTE_API_KEY", "WORKER_GATEWAY_TOKEN"]:
            with self.subTest(name=name):
                args = self.args(
                    SimpleNamespace(url=worker.DEFAULT_BASE_URL), "--api-key-env", name
                )
                overrides = worker.runtime_config(args).config_overrides
                self.assertIn(f'model_providers.{worker.PROVIDER}.env_key="{name}"', overrides)
                self.assertIn(f'shell_environment_policy.filters."{name}"="exclude"', overrides)
                self.assertIn("features.shell_snapshot=false", overrides)

    def test_private_home_template_excludes_gateway_key(self):
        template = tomllib.loads(
            Path(worker.__file__).with_name("runtime.config.template.toml").read_text()
        )
        self.assertEqual(
            template["shell_environment_policy"]["filters"]["OMNIROUTE_API_KEY"], "exclude"
        )
        self.assertFalse(template["features"]["shell_snapshot"])

    def test_custom_provider_enables_standalone_web_search(self):
        overrides = worker.runtime_config(
            self.args(SimpleNamespace(url=worker.DEFAULT_BASE_URL))
        ).config_overrides
        self.assertIn(
            f"model_providers.{worker.PROVIDER}.supports_standalone_web_search=true", overrides
        )
        self.assertIn("features.standalone_web_search=true", overrides)

    def test_private_home_template_enables_standalone_web_search(self):
        template = tomllib.loads(
            Path(worker.__file__).with_name("runtime.config.template.toml").read_text()
        )
        self.assertTrue(template["features"]["standalone_web_search"])

    def test_runtime_override_gates_plugins_without_home_features_table(self):
        (self.home / "config.toml").write_text("")
        with FixtureGateway() as gateway:
            result, _ = self.run_worker(self.args(gateway))
            self.assert_accepted(result)
            self.assertFalse(list(self.home.glob(".tmp/plugins-clone-*")))

    def test_content_filter_terminal_failure_and_guidance_survive_resume(self):
        # Native retry guidance is persisted before budget checks. Source:
        # a956835d core/src/responses_retry.rs:66-81,137-171. This authored SSE
        # fixture tests both the disarmed budget and the native default of five.
        for armed, expected in [(False, 1), (True, 6)]:
            with self.subTest(native_retries=armed), FixtureGateway("content_filter") as gateway:
                args = self.args(gateway, "--timeout", "30")
                args.no_provider_retries = not armed
                failed, _ = self.run_worker(args)
                self.assertEqual(failed["status"], "failed", failed)
                self.assertEqual(failed["phase"], "turn_run", failed)
                self.assertEqual(failed["error_type"], "RuntimeError", failed)
                self.assertEqual(failed["cleanup_status"], "closed", failed)
                self.assertEqual(len(gateway.requests), expected)
                gateway.mode = "complete"
                resumed, _ = self.run_worker(
                    self.args(gateway, "--resume", failed["thread_id"]),
                    prompt="Continue with a permitted fixture alternative.",
                )
                self.assert_accepted(resumed)
                self.assertEqual(resumed["thread_id"], failed["thread_id"])
                retained = json.dumps(gateway.requests[-1]["body"]["input"])
                self.assertEqual(retained.count("<content_filter_guidance>"), expected)
                self.assertIn("offer a permitted alternative", retained)

    def test_incomplete_stream_negative_control_fails_acceptance(self):
        with FixtureGateway("incomplete") as gateway:
            result, _ = self.run_worker(self.args(gateway))
            with self.assertRaises(AssertionError):
                self.assert_accepted(result)
            self.assertEqual(result["status"], "failed", result)
            self.assertEqual(result["usage_status"], "unknown")
            self.assertIsNone(result["usage"])
            self.assertEqual(len(gateway.requests), 1)
            self.assertEqual(result["cleanup_status"], "closed")

    def test_wrong_wire_api_negative_control_never_submits(self):
        def wrong_provider(config):
            config.config_overrides = tuple(
                value.replace('wire_api="responses"', 'wire_api="chat"')
                for value in config.config_overrides
            )
            return AsyncCodex(config=config)

        with FixtureGateway() as gateway:
            result, _ = self.run_worker(self.args(gateway), sdk_factory=wrong_provider)
            with self.assertRaises(AssertionError):
                self.assert_accepted(result)
            self.assertEqual(result["status"], "failed", result)
            self.assertEqual(result["phase"], "initialize")
            self.assertFalse(result["model_inference_submitted"])
            self.assertIsNone(result["usage"])
            self.assertFalse(gateway.requests)
            self.assertEqual(result["cleanup_status"], "closed")

    def test_deadline_interrupts_native_turn_and_closes(self):
        with FixtureGateway("stall") as gateway:
            result, _ = self.run_worker(self.args(gateway, "--timeout", "2"))
            self.assertEqual(result["status"], "deadline_exceeded", result)
            self.assertEqual(result["interrupt_status"], "requested", result)
            self.assertEqual(result["cleanup_status"], "closed")
            self.assertEqual(result["usage_status"], "unknown")
            self.assertIsNone(result["usage"])

    def startup_deadline(self, *, preflight, cleanup_expires):
        # The pinned async client offloads CodexClient.start to a thread.
        # Hold that real operation across the deadline, then observe its PID.
        entered, release = threading.Event(), threading.Event()
        instances, owned_pids = [], []
        native_start = CodexClient.start

        def delayed_start(client):
            entered.set()
            if not release.wait(5):
                raise RuntimeError("delayed fixture startup was not released")
            native_start(client)
            owned_pids.append(client._proc.pid)

        def create_sdk(config):
            factory = worker.AsyncCodexClient if preflight else AsyncCodex
            instance = factory(config=config)
            instances.append(instance)
            return instance

        async def exercise(args):
            invocation = (
                worker.run_preflight(args, sdk_factory=create_sdk)
                if preflight
                else worker.run_worker(args, "Unused fixture prompt.", sdk_factory=create_sdk)
            )
            task = asyncio.create_task(invocation)
            try:
                self.assertTrue(await asyncio.to_thread(entered.wait, 2))
                if cleanup_expires:
                    result = await asyncio.wait_for(asyncio.shield(task), 2)
                    self.assertEqual(result["cleanup_status"], "unresolved", result)
                    self.assertEqual(result["cleanup_error_type"], "TimeoutError", result)
                else:
                    await asyncio.sleep(0.15)
                    self.assertFalse(task.done(), "cleanup returned before startup settled")
                release.set()
                result = await task
                if cleanup_expires:
                    # The caller's bound expired; the owned cleanup still closes
                    # the late process while this embedding loop stays alive.
                    await asyncio.wait_for(asyncio.gather(*worker._CLEANUP_TASKS), 2)
                self.assertEqual(result["status"], "deadline_exceeded", result)
                self.assertEqual(result["phase"], "initialize", result)
                self.assertFalse(result["model_inference_submitted"])
                if not cleanup_expires:
                    self.assertEqual(result["cleanup_status"], "closed", result)
                self.assertTrue(owned_pids)
                for pid in owned_pids:
                    with self.assertRaises(ProcessLookupError):
                        os.kill(pid, 0)
            finally:
                release.set()
                # Also clean the deliberately failing pre-repair control, whose
                # cancelled coroutine can leave its start thread running.
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await task
                await asyncio.to_thread(lambda: None)
                for instance in instances:
                    await instance.close()

        with FixtureGateway() as gateway:
            args = self.args(gateway, "--timeout", "0.05", *(["--preflight"] if preflight else []))
            cleanup_timeout = 0.05 if cleanup_expires else 2
            with (
                patch.object(CodexClient, "start", delayed_start),
                patch.object(worker, "CLEANUP_TIMEOUT", cleanup_timeout),
            ):
                try:
                    asyncio.run(exercise(args))
                finally:
                    release.set()
                    for instance in instances:
                        asyncio.run(instance.close())
            self.assertFalse(gateway.requests)

    def test_initialization_deadline_waits_for_late_start_before_cleanup(self):
        for preflight in [False, True]:
            with self.subTest(preflight=preflight):
                self.startup_deadline(preflight=preflight, cleanup_expires=False)

    def test_initialization_cleanup_bound_reports_unresolved(self):
        for preflight in [False, True]:
            with self.subTest(preflight=preflight):
                self.startup_deadline(preflight=preflight, cleanup_expires=True)

    def test_post_turn_read_failure_preserves_completed_native_result(self):
        destination = Path(self.temp.name) / "post-read-native-result.json"
        native_read = AsyncThread.read
        reads = 0

        async def fail_after_turn(thread):
            nonlocal reads
            reads += 1
            if reads == 1:
                return await native_read(thread)
            raise RuntimeError("PRIVATE_POST_TURN_READ_FAILURE")

        with FixtureGateway() as gateway, patch.object(AsyncThread, "read", fail_after_turn):
            result, _ = self.run_worker(self.args(gateway, "--native-result", str(destination)))
            self.assertEqual(result["status"], "completed", result)
            self.assertEqual(result["thread_status_error_type"], "RuntimeError", result)
            self.assertEqual(result["cleanup_status"], "closed", result)
            self.assertNotIn("PRIVATE_", json.dumps(result))
            native = json.loads(destination.read_text())
            self.assertEqual(native["status"], "completed")
            self.assertTrue(native["items"])
            self.assertEqual(destination.stat().st_mode & 0o777, 0o600)

    def test_native_artifact_is_private_and_never_overwritten(self):
        destination = Path(self.temp.name) / "native-result.json"
        with FixtureGateway() as gateway:
            args = self.args(gateway, "--native-result", str(destination))
            result, _ = self.run_worker(args)
            self.assert_accepted(result)
            retained = destination.read_bytes()
            native = json.loads(retained)
            self.assertTrue(native["items"])
            self.assertEqual(destination.stat().st_mode & 0o777, 0o600)
            duplicate, _ = self.run_worker(args)
            self.assertEqual(duplicate["status"], "failed", duplicate)
            self.assertEqual(duplicate["phase"], "reserve_native_result")
            self.assertEqual(duplicate["error_type"], "FileExistsError")
            self.assertEqual(destination.read_bytes(), retained)

    def test_existing_native_result_refuses_before_thread_creation(self):
        destination = Path(self.temp.name) / "existing-native-result.json"
        destination.write_text("PRIVATE_EXISTING_RESULT")
        starts = []
        native_start = AsyncCodex.thread_start

        async def observe_start(codex, **options):
            starts.append(options)
            return await native_start(codex, **options)

        with FixtureGateway() as gateway, patch.object(AsyncCodex, "thread_start", observe_start):
            result, events = self.run_worker(
                self.args(gateway, "--native-result", str(destination))
            )
            self.assertEqual(starts, [], result)
            self.assertFalse(gateway.requests)
            self.assertEqual(events, [])
            self.assertEqual(result["status"], "failed", result)
            self.assertEqual(result["phase"], "reserve_native_result")
            self.assertEqual(result["error_type"], "FileExistsError")
            self.assertFalse(result["model_inference_submitted"])
            self.assertEqual(destination.read_text(), "PRIVATE_EXISTING_RESULT")

    def test_reserved_native_result_records_failure_before_completion(self):
        destination = Path(self.temp.name) / "failed-native-result.json"
        with FixtureGateway("incomplete") as gateway:
            result, _ = self.run_worker(self.args(gateway, "--native-result", str(destination)))
            self.assertEqual(result["status"], "failed", result)
            retained = json.loads(destination.read_text())
            self.assertEqual(retained["status"], "failed")
            self.assertEqual(retained["phase"], "turn_run")
            self.assertEqual(retained["error_type"], result["error_type"])
            self.assertEqual(retained["cleanup_status"], "closed")
            self.assertEqual(destination.stat().st_mode & 0o777, 0o600)

    def test_preflight_discovers_native_mcp_skill_and_roles_without_inference(self):
        log = self.preflight_config()
        with FixtureGateway() as gateway:
            result, events = self.run_worker(
                self.args(
                    gateway,
                    "--preflight",
                    "--require-mcp",
                    "fixture-mcp",
                    "--require-skill",
                    "fixture-skill",
                )
            )
            self.assertEqual(result["status"], "ready", result)
            self.assertEqual(result["cleanup_status"], "closed", result)
            self.assertFalse(result["model_inference_submitted"])
            self.assertFalse(gateway.requests)
            self.assertNotIn("thread_id", result)
            self.assertIsNone(result["usage"])
            self.assertEqual(result["evidence_scope"], "native_catalog_discovery")
            self.assertEqual(
                result["effective_config"],
                {
                    "model": worker.DEFAULT_MODEL,
                    "model_provider": worker.PROVIDER,
                    "model_reasoning_effort": "max",
                },
            )
            self.assertEqual(result["native_runtime"]["version"], worker.SDK_VERSION)
            self.assertEqual(result["native_runtime"]["metadata_source"], "userAgent")
            self.assertEqual(events[0]["event"], "preflight_discovered")
            server = next(s for s in result["mcp_servers"] if s["name"] == "fixture-mcp")
            self.assertTrue(server["configured"])
            self.assertTrue(server["enabled"])
            self.assertIsNone(server["runtime_status"])
            self.assertFalse(server["tools_error"])
            self.assertIn("fixture_echo", server["tool_names"])
            self.assertIn(
                {"name": "fixture-skill", "enabled": True, "scope": "repo"}, result["skills"]
            )
            self.assertIn(
                {"name": "fixture-verifier"},
                result["configured_roles"],
            )
            self.assertEqual(result["agent_defaults"]["max_concurrent_threads_per_session"], 3)
            self.assertEqual(
                result["agent_defaults"]["default_subagent_model"], worker.DEFAULT_MODEL
            )
            self.assertEqual(result["agent_defaults"]["default_subagent_reasoning_effort"], "max")
            serialized = json.dumps([result, events])
            for private in [str(self.project), str(self.home), "PRIVATE_", "config.toml"]:
                self.assertNotIn(private, serialized)
            methods = [json.loads(line)["method"] for line in log.read_text().splitlines()]
            self.assertIn("initialize", methods)
            self.assertIn("tools/list", methods)
            self.assertNotIn("tools/call", methods)

    def test_preflight_missing_mcp_and_skill_fail_without_inference(self):
        with FixtureGateway() as gateway:
            result, _ = self.run_worker(
                self.args(
                    gateway,
                    "--preflight",
                    "--require-mcp",
                    "missing-mcp",
                    "--require-skill",
                    "missing-skill",
                )
            )
            self.assertEqual(result["status"], "unavailable", result)
            self.assertEqual(result["requirements"]["unavailable_mcp"], ["missing-mcp"])
            self.assertEqual(result["requirements"]["unavailable_skills"], ["missing-skill"])
            self.assertFalse(result["model_inference_submitted"])
            self.assertFalse(gateway.requests)
            self.assertEqual(result["cleanup_status"], "closed")

    def test_preflight_disabled_empty_and_error_mcp_catalogs_fail_requirement(self):
        with FixtureGateway() as gateway:
            for mode, enabled in [("complete", False), ("empty", True), ("error", True)]:
                with self.subTest(mode=mode, enabled=enabled):
                    self.preflight_config(mcp_mode=mode, enabled=enabled)
                    result, _ = self.run_worker(
                        self.args(gateway, "--preflight", "--require-mcp", "fixture-mcp")
                    )
                    self.assertEqual(result["status"], "unavailable", result)
                    self.assertEqual(result["requirements"]["unavailable_mcp"], ["fixture-mcp"])
                    self.assertNotIn("PRIVATE_", json.dumps(result))
                    self.assertFalse(result["model_inference_submitted"])
                    self.assertFalse(gateway.requests)
                    self.assertEqual(result["cleanup_status"], "closed")

    def test_preflight_deadline_closes_without_inference(self):
        self.preflight_config(mcp_mode="stall")
        with FixtureGateway() as gateway:
            result, _ = self.run_worker(self.args(gateway, "--preflight", "--timeout", "1"))
            self.assertEqual(result["status"], "deadline_exceeded", result)
            self.assertEqual(result["phase"], "mcp_discovery")
            self.assertEqual(result["cleanup_status"], "closed")
            self.assertFalse(result["model_inference_submitted"])
            self.assertFalse(gateway.requests)

    def test_preflight_requirements_are_explicit_and_do_not_change_turns(self):
        with FixtureGateway() as gateway:
            with self.assertRaises(SystemExit):
                self.args(gateway, "--require-mcp", "fixture-mcp")
            with self.assertRaises(SystemExit):
                self.args(gateway, "--require-skill", "fixture-skill")
            with self.assertRaises(SystemExit):
                self.args(gateway, "--preflight", "--resume", "fixture-thread")
            with self.assertRaises(SystemExit):
                self.args(gateway, "--catalog-details")

    def test_preflight_cli_emits_one_compact_result_or_explicit_catalog_details(self):
        self.preflight_config()
        extra_skill = self.project / ".agents/skills/unrequired-skill/SKILL.md"
        extra_skill.parent.mkdir(parents=True)
        extra_skill.write_text(
            "---\nname: unrequired-skill\ndescription: PRIVATE_UNUSED_DESCRIPTION\n---\n"
            "PRIVATE_UNUSED_BODY\n"
        )
        with FixtureGateway() as gateway:
            argv = [
                worker.__file__,
                "--workspace",
                str(self.project),
                "--codex-home",
                str(self.home),
                "--base-url",
                gateway.url,
                "--timeout",
                "15",
                "--preflight",
                "--require-mcp",
                "fixture-mcp",
                "--require-skill",
                "fixture-skill",
            ]
            for detailed in [False, True]:
                with self.subTest(catalog_details=detailed):
                    stdout = io.StringIO()
                    with patch.object(
                        sys, "argv", argv + (["--catalog-details"] if detailed else [])
                    ):
                        with contextlib.redirect_stdout(stdout):
                            exit_code = worker.main()
                    lines = stdout.getvalue().splitlines()
                    self.assertEqual(exit_code, 0)
                    self.assertEqual(len(lines), 1, stdout.getvalue())
                    result = json.loads(lines[0])
                    self.assertEqual(result["event"], "result")
                    self.assertEqual(result["status"], "ready")
                    self.assertEqual(result["requirements"]["unavailable_mcp"], [])
                    self.assertEqual(result["requirements"]["unavailable_skills"], [])
                    self.assertEqual(result["effective_config"]["model"], worker.DEFAULT_MODEL)
                    self.assertEqual(result["cleanup_status"], "closed")
                    self.assertFalse(result["model_inference_submitted"])
                    self.assertNotIn("PRIVATE_", lines[0])
                    if detailed:
                        self.assertIn("fixture_echo", result["mcp_servers"][0]["tool_names"])
                        self.assertIn("unrequired-skill", [s["name"] for s in result["skills"]])
                    else:
                        server = result["mcp_servers"][0]
                        self.assertEqual(server["tool_count"], 1)
                        self.assertTrue(server["catalog_ready"])
                        self.assertNotIn("tool_names", server)
                        self.assertEqual(result["skills"]["required"], {"fixture-skill": True})
                        self.assertGreaterEqual(result["skills"]["enabled_count"], 2)
                        self.assertGreaterEqual(
                            result["skills"]["total_count"], result["skills"]["enabled_count"]
                        )
                        self.assertNotIn("unrequired-skill", lines[0])
                        self.assertNotIn("fixture_echo", lines[0])
            self.assertFalse(gateway.requests)

    def test_explicit_wrong_runtime_version_is_not_replaced_by_user_agent(self):
        metadata = SimpleNamespace(
            serverInfo=SimpleNamespace(name="native-fixture", version="0.0.0"),
            userAgent=f"native-fixture/{worker.SDK_VERSION}",
        )
        with self.assertRaises(RuntimeError):
            worker.native_runtime(metadata)


if __name__ == "__main__":
    unittest.main(verbosity=2)
