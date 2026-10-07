"""Hermetic metadata-oracle controls for the opt-in native transport cells.

Synthetic fixtures only; this CI module imports no model SDK or host account.
"""
from collections.abc import MutableMapping
from copy import deepcopy
from http.client import HTTPConnection
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

from tests import lane_gateway_transport as transport


class NameOnlyEnvironment(MutableMapping):
    """A whole-environment value copy trips the deliberately unreadable key."""
    def __init__(self):
        self.data = {"PATH": "/fixture/bin", "ANTHROPIC_API_KEY": "fixture-only"}
        self.forbidden_reads = []

    def __getitem__(self, key):
        if key not in transport.SAFE_ENV:
            self.forbidden_reads.append(key)
            raise AssertionError("unsafe environment value was read")
        return self.data[key]

    def __setitem__(self, key, value):
        self.data[key] = value

    def __delitem__(self, key):
        del self.data[key]

    def __iter__(self):
        return iter(self.data)

    def __len__(self):
        return len(self.data)


class TransportOracleTests(unittest.TestCase):
    def post(self, endpoint):
        parts = urlsplit(endpoint)
        connection = HTTPConnection(parts.hostname, parts.port, timeout=2)
        self.addCleanup(connection.close)
        connection.request("POST", parts.path, body='{"field":"fixture-only"}',
                           headers={"Content-Type": "application/json",
                                    "X-Request-Id": "fixture-correlation"})
        response = connection.getresponse()
        result = response.status, response.getheader("Location")
        response.read()
        return result

    def test_counts_change_only_for_the_listener_actually_contacted(self):
        with transport.CountingFixture("first") as first, \
                transport.CountingFixture("second") as second, \
                transport.CountingFixture("proxy") as proxy:
            self.assertEqual(sum(row["total"] for row in transport.fixture_counts(
                (first, second, proxy)).values()), 0)
            self.assertEqual(self.post(first.url + "/responses")[0], 200)
            counts = transport.fixture_counts((first, second, proxy))
            self.assertEqual(counts["first"]["model_post"], 1)
            self.assertEqual(counts["second"]["total"], 0)
            self.assertEqual(counts["proxy"]["total"], 0)
            self.assertEqual(counts["first"]["correlations"], ["fixture-correlation"])
            self.assertEqual(first.native.requests, [])
            self.assertEqual(set(counts["first"]), {
                "listener", "total", "post", "model_post", "served_307", "correlations"})
            self.assertNotIn("field", json.dumps(counts))

    def test_post_preserving_redirect_control_exposes_a_second_listener_hit(self):
        with transport.CountingFixture("second") as second, \
                transport.CountingFixture("first", redirect=second.root) as first:
            status, location = self.post(first.url + "/responses")
            self.assertEqual(status, 307)
            self.assertEqual(first.counts()["model_post"], 1)
            self.assertEqual(first.counts()["served_307"], 1)
            self.assertEqual(second.counts()["total"], 0)
            self.assertEqual(self.post(location)[0], 200)
            self.assertEqual(second.counts()["model_post"], 1)

    def test_clear_by_name_never_reads_the_credential_value(self):
        environment = NameOnlyEnvironment()
        with patch.object(transport.os, "environ", environment):
            self.assertEqual(transport.safe_environment(), {"PATH": "/fixture/bin"})
        self.assertEqual(environment.forbidden_reads, [])
        self.assertEqual(environment.data, {"PATH": "/fixture/bin"})
        # The old copy/filter pattern fails this same fixture.
        bad = NameOnlyEnvironment()
        with self.assertRaises(AssertionError):
            dict(bad.items())
        self.assertEqual(bad.forbidden_reads, ["ANTHROPIC_API_KEY"])

    def completed_row(self, client):
        row = {
            "client": client, "status": "completed", "exit_code": 0,
            "cleanup_settled": True, "native_children_alive": 0,
            "counts": {"first": {"model_post": 1, "served_307": 0},
                       "second": {"total": 0}, "proxy": {"total": 0}},
        }
        if client == "codex":
            row.update(cleanup_status="closed", native_terminal_kind="TurnCompleted",
                       native_terminal_status="completed")
        else:
            row.update(native_terminal_kind="ResultMessage", native_result_is_error=False)
        return row

    def test_a_target_post_does_not_qualify_error_nonzero_or_unsettled_normal_cells(self):
        oracle = transport.NativeTransportCells("test_proxy")
        for client in ("codex", "claude"):
            good = self.completed_row(client)
            oracle.assert_armed(good)
            for changed in ({"status": "failed", "exit_code": 2},
                            {"status": "sdk_error", "exit_code": 1},
                            {"status": "completed", "exit_code": 1},
                            {"status": "timeout", "exit_code": 1},
                            {"cleanup_settled": False}, {"native_children_alive": 1}):
                bad = deepcopy(good)
                bad.update(changed)
                with self.subTest(client=client, changed=changed), self.assertRaises(AssertionError):
                    oracle.assert_armed(bad)

    def test_http307_counter_does_not_qualify_timeout_cancel_or_unknown_native_error(self):
        oracle = transport.NativeTransportCells("test_redirect")
        for client in ("codex", "claude"):
            good = self.completed_row(client)
            good["counts"]["first"]["served_307"] = 1
            good.update(native_api_error_status=307)
            if client == "codex":
                good.update(status="failed", exit_code=2, phase="turn_run", error_type="RuntimeError",
                            native_terminal_status="failed")
            else:
                good.update(status="native_error", exit_code=1,
                            native_result_is_error=True, native_terminal_reason="completed")
            oracle.assert_redirect_refused(good)
            for changed in ({"status": "timeout"}, {"status": "deadline_exceeded"},
                            {"status": "cancelled"}, {"status": "sdk_error"},
                            {"native_api_error_status": None}, {"native_api_error_status": 500},
                            {"cleanup_settled": False}):
                bad = deepcopy(good)
                bad.update(changed)
                with self.subTest(client=client, changed=changed), self.assertRaises(AssertionError):
                    oracle.assert_redirect_refused(bad)

    def test_public_typed_status_is_read_without_a_native_error_message(self):
        class Error:
            codex_error_info = SimpleNamespace(root=SimpleNamespace(
                response_stream_connection_failed=SimpleNamespace(http_status_code=307)))
            @property
            def message(self):
                raise AssertionError("native error message was read")
        self.assertEqual(transport.codex_http_status(Error()), 307)
        self.assertIsNone(transport.codex_http_status(None))

    def test_normal_claude_fixture_uses_vendor_success_stream_grammar(self):
        with transport.CountingFixture("first", model="claude-fixture") as first:
            parts = urlsplit(first.url)
            connection = HTTPConnection(parts.hostname, parts.port, timeout=2)
            self.addCleanup(connection.close)
            connection.request("POST", "/v1/messages", body="{}")
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            self.assertEqual(response.getheader("Content-Type"), "text/event-stream")
            data = [json.loads(line[6:]) for line in response.read().decode().splitlines()
                    if line.startswith("data: ")]
            self.assertEqual([event["type"] for event in data], [
                "message_start", "content_block_start", "content_block_delta",
                "content_block_stop", "message_delta", "message_stop"])
            self.assertEqual(data[-2]["delta"]["stop_reason"], "end_turn")
            self.assertEqual(first.counts()["model_post"], 1)
            self.assertEqual(first.native.requests, [])
