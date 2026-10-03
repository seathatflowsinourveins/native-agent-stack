#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13,<3.14"
# dependencies = [
#     "openai-codex==0.159.2",
# ]
# ///
"""Local integration fixtures, not upstream tests or provider/model acceptance.

The SSE fixture derives from openai/codex rust-v0.159.2
codex-rs/core/tests/common/responses.rs::{sse,ev_response_created,
ev_assistant_message,ev_completed}. The SDK and bundled native runtime are real;
the loopback provider returns authored deterministic fixture responses.
"""

import asyncio
import json
import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import worker
from openai_codex import AsyncCodex


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

    def run_worker(self, args, *, sdk_factory=AsyncCodex):
        events = []
        instances, owned_pids = [], []

        def create_sdk(config):
            instance = sdk_factory(config=config)
            instances.append(instance)
            return instance

        def observe(event):
            events.append(event)
            # Observation only: inspect the PID of this test's own SDK child.
            # Native source: sdk/python/src/openai_codex/client.py::_start_process.
            process = instances[-1]._client._sync._proc
            if process is not None:
                owned_pids.append(process.pid)

        result = asyncio.run(
            worker.run_worker(
                args, "One bounded fixture task.", sdk_factory=create_sdk, on_event=observe
            )
        )
        for pid in owned_pids:
            with self.assertRaises(ProcessLookupError):
                os.kill(pid, 0)
        return result, events

    def assert_accepted(self, result):
        self.assertEqual(result["status"], "completed", result)
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
                # Source: core/src/client.rs:902–933 at rust-v0.159.2.
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
            self.assertEqual(duplicate["phase"], "retain_native_result")
            self.assertEqual(duplicate["error_type"], "FileExistsError")
            self.assertEqual(destination.read_bytes(), retained)


if __name__ == "__main__":
    unittest.main(verbosity=2)
