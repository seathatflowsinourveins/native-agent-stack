"""Hermetic metadata-oracle controls for the opt-in native transport cells.

Synthetic fixtures only; this CI module imports no model SDK or host account.
"""
from collections.abc import MutableMapping
from http.client import HTTPConnection
import json
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
                "listener", "total", "post", "model_post", "correlations"})
            self.assertNotIn("field", json.dumps(counts))

    def test_post_preserving_redirect_control_exposes_a_second_listener_hit(self):
        with transport.CountingFixture("second") as second, \
                transport.CountingFixture("first", redirect=second.root) as first:
            status, location = self.post(first.url + "/responses")
            self.assertEqual(status, 307)
            self.assertEqual(first.counts()["model_post"], 1)
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

