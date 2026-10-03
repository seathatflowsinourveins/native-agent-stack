"""Local stream-fidelity controls; these are not upstream/provider tests."""

import importlib.util
import json
import os
import unittest
from pathlib import Path
from types import SimpleNamespace


class GatewayObserverTests(unittest.TestCase):
    def setUp(self):
        os.environ["STACK_WORKER_OBSERVATION"] = "/unused-owned-test-output"
        path = Path(__file__).with_name("gateway_observer.py")
        spec = importlib.util.spec_from_file_location("gateway_observer", path)
        self.addon = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.addon)
        self.rows = []
        self.addon.emit = self.rows.append
        self.body = json.dumps(
            {
                "model": "cx/gpt-6.1-sol",
                "reasoning": {"effort": "max"},
                "prompt_cache_key": "owned-session",
                "input": "private-fixture-content",
                "tools": [{"type": "function", "name": "shell"}],
            }
        ).encode()
        self.flow = SimpleNamespace(
            id="owned-flow",
            metadata={},
            request=SimpleNamespace(method="POST", path="/v1/responses", content=self.body),
            response=SimpleNamespace(status_code=200, stream=None),
        )

    def test_fragmented_stream_preserves_every_byte_and_observes_terminal_usage(self):
        self.addon.request(self.flow)
        self.addon.responseheaders(self.flow)
        wire = b'data: {"type":"response.completed","response":{"usage":{"input_tokens":9,"output_tokens":4,"total_tokens":13,"input_tokens_details":{"cached_tokens":3},"output_tokens_details":{"reasoning_tokens":2}}}}\n\n'
        chunks = [wire[:7], wire[7:31], wire[31:], b""]
        returned = b"".join(self.flow.response.stream(chunk) for chunk in chunks)
        self.assertEqual(returned, wire)
        self.assertEqual(self.flow.request.content, self.body)
        completed = [r for r in self.rows if r["event"] == "response_completed"]
        self.assertEqual(len(completed), 1)
        self.assertEqual(completed[0]["usage"]["total_tokens"], 13)
        self.assertNotIn("private-fixture-content", json.dumps(self.rows))

    def test_absent_usage_stays_unknown(self):
        self.addon.request(self.flow)
        self.addon.responseheaders(self.flow)
        wire = b'data: {"type":"response.completed","response":{}}\n\n'
        self.assertEqual(self.flow.response.stream(wire), wire)
        self.assertIsNone(self.rows[-1]["usage"])

    def test_large_chunk_of_short_frames_retains_terminal_usage(self):
        self.addon.request(self.flow)
        self.addon.responseheaders(self.flow)
        frame = b'data: {"type":"response.output_text.delta","delta":"private-fixture"}\n\n'
        terminal = (
            b'data: {"type":"response.completed","response":{"usage":{"total_tokens":13}}}\n\n'
        )
        wire = frame * (self.addon.MAX_FRAME // len(frame) + 1) + terminal
        self.assertGreater(len(wire), 2 * 1024 * 1024)
        self.assertEqual(self.flow.response.stream(wire), wire)
        self.flow.response.stream(b"")
        self.assertFalse(any(r["event"] == "usage_capture_overflow" for r in self.rows))
        completed = [r for r in self.rows if r["event"] == "response_completed"]
        self.assertEqual(len(completed), 1)
        self.assertEqual(completed[0]["usage"]["total_tokens"], 13)
        self.assertNotIn("private-fixture", json.dumps(self.rows))

    def test_native_responses_lite_tools_are_observed_without_flattening_request(self):
        self.flow.request.content = json.dumps(
            {
                "model": "cx/gpt-6.1-sol-max",
                "input": [
                    {
                        "type": "additional_tools",
                        "id": "stable-native-tools",
                        "role": "developer",
                        "tools": [{"type": "namespace", "name": "functions"}],
                    }
                ],
            }
        ).encode()
        original = self.flow.request.content
        self.addon.request(self.flow)
        self.assertEqual(self.flow.request.content, original)
        self.assertEqual(self.rows[0]["tool_source"], "input.additional_tools")
        self.assertEqual(self.rows[0]["tool_names"], ["functions"])
        self.assertEqual(len(self.rows[0]["native_tool_id_hashes"]), 1)

    def test_oversized_frame_exposes_incomplete_capture_and_preserves_tail(self):
        self.addon.request(self.flow)
        self.addon.responseheaders(self.flow)
        self.addon.MAX_FRAME = 128
        wire = b"data: " + b"x" * 256 + b"TAIL_MUST_SURVIVE\n\n"
        chunks = [wire[:-2], wire[-2:]]
        self.assertEqual(b"".join(self.flow.response.stream(chunk) for chunk in chunks), wire)
        self.assertTrue(any(r["event"] == "usage_capture_overflow" for r in self.rows))
        self.assertFalse(any(r["event"] == "response_completed" for r in self.rows))

    def test_wrong_endpoint_does_not_claim_worker_observation(self):
        self.flow.request.path = "/v1/unselected"
        self.addon.request(self.flow)
        self.addon.responseheaders(self.flow)
        self.assertEqual(self.rows, [])
        self.assertIsNone(self.flow.response.stream)


if __name__ == "__main__":
    unittest.main()
