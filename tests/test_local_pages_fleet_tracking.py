"""Native Fleet tracking contracts through bounded, synthetic transports."""

import importlib.util
from http.client import HTTPException, IncompleteRead
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("fleet_tracking_tests", ROOT / "tools/local-pages/fleet_data.py")
fleet = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fleet)
NOW = 1791578400.0


def vector(rows):
    return {"status": "success", "data": {"resultType": "vector", "result": rows}}


def sample(labels, value, evaluated=NOW):
    return {"metric": labels, "value": [evaluated, str(value)]}


class FleetTrackingTests(unittest.TestCase):
    def run_hcom(self, rows):
        def run(command, **kwargs):
            if command[0] == "systemctl":
                self.assertEqual(command, ["systemctl", "--user", "show", "vllm-embed.service", "--property=LoadState", "--property=ActiveState", "--property=SubState", "--property=UnitFileState", "--no-pager"])
                return subprocess.CompletedProcess(command, 0, "LoadState=loaded\nActiveState=active\nSubState=running\nUnitFileState=enabled\n", "")
            self.assertEqual(command, ["hcom", "list", "--format", "{name}|{base_name}|{tool}|{tag}|{status}|{status_age_seconds}|{created_at}"])
            self.assertLessEqual(kwargs["timeout"], 3)
            return subprocess.CompletedProcess(command, 0, "\n".join(rows), "")
        return run

    def collect(self, rows=(), fetch=None, probe=None):
        return fleet.collect_tracking(run=self.run_hcom(rows), fetch=fetch or (lambda query, **kwargs: vector([])),
                                      probe=probe or (lambda url, **kwargs: None), now=NOW)

    def test_every_native_hcom_row_is_retained_including_trading_labels(self):
        tags = ["us-equities-fixture-" + str(i) for i in range(6)] + ["coding-fixture-" + str(i) for i in range(13)]
        rows = [f"{tag}-navi|navi|codex|{tag}|active|0|{NOW - 30}" for tag in tags]
        result = self.collect(rows)["hcom"]
        self.assertEqual(result["status"], "reported")
        self.assertEqual(result["count"], 19)
        self.assertEqual([row["tag"] for row in result["agents"]], tags)
        self.assertTrue(all(row["status_age_seconds"] == 0 for row in result["agents"]))
        self.assertTrue(all(set(row) == {"name", "base_name", "tool", "tag", "status", "status_age_seconds", "created_at"} for row in result["agents"]))

    def test_stopped_sender_identity_cannot_disable_the_product_roster(self):
        def run(command, **kwargs):
            if command[0] == "hcom" and "--name" in command:
                return subprocess.CompletedProcess(command, 1, "", "stopped synthetic identity")
            return self.run_hcom([f"lane-alpha|alpha|codex|fixture|active|0|{NOW - 30}"])(command, **kwargs)
        result = fleet.collect_tracking(run=run, fetch=lambda *args, **kwargs: vector([]),
                                        probe=lambda *args, **kwargs: None, now=NOW)["hcom"]
        self.assertEqual(result["status"], "reported")
        self.assertEqual(result["count"], 1)

    def test_launching_and_error_rows_survive_individually_invalid_rows(self):
        rows = [f"new-alpha|alpha|codex|fixture|launching|0|{NOW - 1}",
                "unsafe|extra|delimiter|codex|fixture|active|0|1",
                f"error-beta|beta|claude|fixture|error|1|{NOW - 2}",
                f"bad-time|gamma|codex|fixture|active|0|{NOW + 1}",
                f"bad-label|delta|codex|Bearer synthetic-private|active|0|{NOW - 1}"]
        result = self.collect(rows)["hcom"]
        self.assertEqual(result["status"], "reported")
        self.assertEqual(result["count"], 2)
        self.assertEqual([row["status"] for row in result["agents"]], ["launching", "error"])
        self.assertEqual(result["rejected_rows"], 3)
        self.assertIn("3", result["reason"])
        self.assertNotIn("synthetic-private", json.dumps(result))

    def test_counter_sample_timestamp_is_used_instead_of_evaluation_time(self):
        labels = {"ecosystem_lane": "retained-lane", "token_type": "input"}
        def fetch(query, **kwargs):
            if "codex_turn_token_usage_sum" not in query:
                return vector([])
            return vector([sample(labels, NOW - 121 if "timestamp(" in query else 0)])
        tracking = self.collect(fetch=fetch)
        metric = tracking["lanes"][0]["clients"][0]["tokens"][0]
        self.assertEqual(metric["status"], "UNKNOWN")
        self.assertIsNone(metric["value"])
        self.assertIn("stale", metric["reason"])
        self.assertNotEqual(metric["source_sample_utc"], metric["evaluated_utc"])
        self.assertEqual(tracking["hcom"]["count"], 0)

    def test_codex_token_categories_keep_lower_bounds_and_unqualified_zeros(self):
        token_types = ["input", "cached_input", "cache_write_input", "output", "reasoning_output", "total"]
        queries = []
        def fetch(query, **kwargs):
            queries.append(query)
            if "codex_turn_token_usage_sum" in query:
                return vector([sample({"ecosystem_lane": "lane-a", "token_type": kind}, NOW - 5 if "timestamp(" in query else index / 100000)
                               for index, kind in enumerate(token_types)])
            if "codex_mcp_call_total" in query:
                return vector([sample({"ecosystem_lane": "lane-a"}, NOW - 5 if "timestamp(" in query else 0)])
            return vector([])
        result = self.collect(fetch=fetch)
        client = result["lanes"][0]["clients"][0]
        self.assertEqual({row["token_type"] for row in client["tokens"]}, set(token_types))
        self.assertEqual(len(client["tokens"]), 6)
        tokens = {row["token_type"]: row for row in client["tokens"]}
        self.assertEqual(tokens["input"]["status"], "UNKNOWN")
        self.assertIsNone(tokens["input"]["value"])
        self.assertIn("zero", tokens["input"]["reason"])
        self.assertTrue(all(row["status"] == "lower bound" for kind, row in tokens.items() if kind != "input"))
        self.assertTrue(all("start-timestamp" in row["scope"] for row in tokens.values()))
        self.assertEqual(client["invocations"]["status"], "UNKNOWN")
        self.assertIsNone(client["invocations"]["value"])
        self.assertEqual(client["invocations"]["unit"], "calls/s")
        self.assertTrue(any("sum by" in query and "rate(codex_mcp_call_total" in query for query in queries))
        self.assertTrue(any("codex_api_request_total" in query for query in queries))
        self.assertTrue(all('instance!="unscoped"' in query for query in queries if "rate(" in query))

    def test_api_tool_mcp_and_unsupported_rate_families_keep_distinct_contracts(self):
        counters = {"codex_api_request_total": 0.2, "codex_tool_call_total": 0.3, "codex_mcp_call_total": 0.1}
        def fetch(query, **kwargs):
            for counter, value in counters.items():
                if counter in query:
                    self.assertIn('instance!="unscoped"', query)
                    return vector([sample({"ecosystem_lane": "rates-only"}, NOW - 5 if "timestamp(" in query else value)])
            return vector([])
        client = self.collect(fetch=fetch)["lanes"][0]["clients"][0]
        rates = {row["family"]: row for row in client["rates"]}
        self.assertEqual(set(rates), {"api_requests", "tool_calls", "mcp_calls", "skill_invocations", "agent_invocations"})
        for family, counter in (("api_requests", "codex_api_request_total"), ("tool_calls", "codex_tool_call_total"), ("mcp_calls", "codex_mcp_call_total")):
            self.assertEqual(rates[family]["value"], counters[counter])
            self.assertEqual(rates[family]["status"], "lower bound")
            self.assertIn(counter, rates[family]["query"])
            self.assertIn("start-timestamp", rates[family]["reason"])
        self.assertIn("retries", rates["api_requests"]["scope"])
        self.assertIn("outer", rates["mcp_calls"]["scope"])
        for family in ("skill_invocations", "agent_invocations"):
            self.assertEqual(rates[family]["status"], "UNKNOWN")
            self.assertIsNone(rates[family]["value"])
            self.assertIsNone(rates[family]["query"])
            self.assertIn("not qualified", rates[family]["reason"])
        self.assertEqual(client["invocations"], rates["mcp_calls"])

    def test_claude_categories_are_preserved_without_invented_mcp_calls(self):
        kinds = ["input", "output", "cacheCreation", "cacheRead"]
        def fetch(query, **kwargs):
            if "claude_code_token_usage_tokens_total" in query:
                return vector([sample({"ecosystem_lane": "historical-claude", "type": kind}, NOW - 5 if "timestamp(" in query else 1)
                               for kind in kinds])
            return vector([])
        result = self.collect(fetch=fetch)
        self.assertEqual(result["hcom"]["agents"], [])
        lane = result["lanes"][0]
        self.assertEqual(lane["lane"], "historical-claude")
        self.assertEqual(len(lane["clients"]), 1)
        client = lane["clients"][0]
        self.assertEqual(client["client"], "claude")
        self.assertEqual({row["token_type"] for row in client["tokens"]}, set(kinds))
        self.assertEqual(client["invocations"]["status"], "UNKNOWN")
        self.assertIsNone(client["invocations"]["value"])
        self.assertEqual({row["family"] for row in client["rates"]}, {"api_requests", "tool_calls", "mcp_calls", "skill_invocations", "agent_invocations"})
        self.assertTrue(all(row["status"] == "UNKNOWN" and row["value"] is None and row["reason"] for row in client["rates"]))
        self.assertNotIn("active", lane)

    def test_missing_counter_rate_is_unknown_even_with_fresh_source(self):
        def fetch(query, **kwargs):
            if "codex_mcp_call_total" in query and "timestamp(" in query:
                return vector([sample({"ecosystem_lane": "new-writer"}, NOW - 5)])
            return vector([])
        metric = self.collect(fetch=fetch)["lanes"][0]["clients"][0]["invocations"]
        self.assertEqual(metric["status"], "UNKNOWN")
        self.assertIsNone(metric["value"])
        self.assertIn("absent", metric["reason"])
        self.assertIsNotNone(metric["source_sample_utc"])

    def test_future_nonfinite_and_malformed_source_samples_do_not_publish_rates(self):
        for epoch in (NOW + 1, float("nan"), float("inf"), "invalid", -1):
            with self.subTest(kind=str(epoch)):
                def fetch(query, **kwargs):
                    if "codex_mcp_call_total" in query:
                        return vector([sample({"ecosystem_lane": "lane-a"}, epoch if "timestamp(" in query else 0)])
                    return vector([])
                metric = self.collect(fetch=fetch)["lanes"][0]["clients"][0]["invocations"]
                self.assertEqual(metric["status"], "UNKNOWN")
                self.assertIsNone(metric["value"])
                self.assertTrue(metric["reason"])

    def test_duplicate_grouped_series_does_not_choose_one_writer_value(self):
        def fetch(query, **kwargs):
            if "codex_mcp_call_total" not in query:
                return vector([])
            values = [NOW - 5] if "timestamp(" in query else [2, 3]
            return vector([sample({"ecosystem_lane": "lane-a"}, value) for value in values])
        metric = self.collect(fetch=fetch)["lanes"][0]["clients"][0]["invocations"]
        self.assertEqual(metric["status"], "UNKNOWN")
        self.assertIsNone(metric["value"])
        self.assertIn("duplicated", metric["reason"])

    def test_failed_and_empty_queries_remain_distinct_source_observations(self):
        def fetch(query, **kwargs):
            if "claude_code_token_usage_tokens_total" in query:
                raise URLError("private synthetic endpoint details")
            return vector([])
        result = self.collect(fetch=fetch)
        self.assertEqual(result["lanes"], [])
        observations = result["query_observations"]
        self.assertTrue(all(row["status"] == "UNKNOWN" and row["series_count"] is None for row in observations if row["client"] == "claude"))
        self.assertTrue(all(row["status"] == "reported" and row["series_count"] == 0 for row in observations if row["client"] == "codex"))
        self.assertNotIn("private synthetic endpoint details", json.dumps(result))

    def test_hcom_failure_and_unescaped_delimiter_do_not_report_empty_roster(self):
        cases = [(1, "", "private synthetic CLI failure"), (0, "name|base|codex|tag|unexpected|active|0|1", "")]
        for exit_code, stdout, stderr in cases:
            with self.subTest(exit_code=exit_code):
                result = fleet.collect_tracking(run=lambda *args, **kwargs: subprocess.CompletedProcess(args[0], exit_code, stdout, stderr),
                                                fetch=lambda *args, **kwargs: vector([]), probe=lambda *args, **kwargs: None, now=NOW)
                self.assertEqual(result["hcom"]["status"], "UNKNOWN")
                self.assertIsNone(result["hcom"]["agents"])
                self.assertIsNone(result["hcom"]["count"])
                self.assertNotIn("private synthetic CLI failure", json.dumps(result))

    def test_service_scrape_and_independent_health_transport_are_not_combined(self):
        def fetch(query, **kwargs):
            if 'job="workstation-vllm"' in query:
                return vector([sample({"job": "workstation-vllm"}, NOW - 5 if "timestamp(" in query else 1)])
            return vector([])
        def probe(url, **kwargs):
            if ":28231/" in url:
                raise URLError("synthetic service health unavailable")
            return 200 if ":29374/" in url else 503
        result = self.collect(fetch=fetch, probe=probe)
        services = {row["id"]: row for row in result["services"]}
        self.assertEqual(set(services), {"vllm-embed", "hindsight", "ai-memory"})
        scrape, health = [row for row in services["vllm-embed"]["observations"] if row["unit"] != "state"]
        self.assertEqual(scrape["value"], 1)
        self.assertEqual(scrape["status"], "reported")
        self.assertEqual(health["status"], "UNKNOWN")
        self.assertNotIn("down", services["vllm-embed"])
        self.assertEqual(services["hindsight"]["observations"][0]["value"], 503)
        self.assertIn("Database reachability", services["hindsight"]["observations"][0]["scope"])
        self.assertIn("liveness only", services["ai-memory"]["observations"][0]["scope"])
        states = [row for row in services["vllm-embed"]["observations"] if row["unit"] == "state"]
        self.assertEqual({row["metric"]: row["value"] for row in states}, {
            "LoadState": "loaded", "ActiveState": "active", "SubState": "running", "UnitFileState": "enabled",
        })
        self.assertTrue(all("port binding" in row["scope"] for row in states))

    def test_http_protocol_errors_are_isolated_to_failed_observations(self):
        def fetch(query, **kwargs):
            if "codex_mcp_call_total" in query:
                raise IncompleteRead(b"PRIVATE-SYNTHETIC-HTTP-BODY", 7)
            if "codex_api_request_total" in query:
                return vector([sample({"ecosystem_lane": "healthy-source"}, NOW - 5 if "timestamp(" in query else 0.4)])
            return vector([])
        def probe(url, **kwargs):
            if ":28231/" in url:
                raise HTTPException("PRIVATE-SYNTHETIC-HEALTH-DETAILS")
            return 200
        result = self.collect([f"live-alpha|alpha|codex|fixture|active|0|{NOW - 1}"], fetch=fetch, probe=probe)
        self.assertEqual(result["hcom"]["count"], 1)
        rates = {row["family"]: row for row in result["lanes"][0]["clients"][0]["rates"]}
        self.assertEqual(rates["api_requests"]["status"], "lower bound")
        self.assertEqual(rates["mcp_calls"]["status"], "UNKNOWN")
        services = {row["id"]: row for row in result["services"]}
        health = next(row for row in services["vllm-embed"]["observations"] if row["unit"] == "HTTP status")
        self.assertEqual(health["status"], "UNKNOWN")
        self.assertEqual(services["hindsight"]["observations"][0]["value"], 200)
        self.assertNotIn("PRIVATE-SYNTHETIC", json.dumps(result))

    def test_reported_scrape_zero_does_not_become_an_unknown_rate_zero(self):
        def fetch(query, **kwargs):
            if 'job="workstation-vllm"' in query:
                return vector([sample({"job": "workstation-vllm"}, NOW - 5 if "timestamp(" in query else 0)])
            return vector([])
        scrape = self.collect(fetch=fetch)["services"][0]["observations"][0]
        self.assertEqual(scrape["status"], "reported")
        self.assertEqual(scrape["value"], 0)

    def test_not_found_unit_preserves_known_manager_state_and_unknown_install_state(self):
        for exit_code in (0, 1):
            with self.subTest(exit_code=exit_code):
                def run(command, **kwargs):
                    if command[0] == "hcom":
                        return self.run_hcom([])(command, **kwargs)
                    return subprocess.CompletedProcess(command, exit_code, "LoadState=not-found\nActiveState=inactive\nSubState=dead\nUnitFileState=\n", "")
                result = fleet.collect_tracking(run=run, fetch=lambda *args, **kwargs: vector([]), probe=lambda *args, **kwargs: None, now=NOW)
                states = {row["metric"]: row for row in result["services"][0]["observations"] if row["unit"] == "state"}
                self.assertEqual(states["LoadState"]["value"], "not-found")
                self.assertEqual(states["LoadState"]["status"], "reported")
                self.assertEqual(states["ActiveState"]["value"], "inactive")
                self.assertEqual(states["UnitFileState"]["status"], "UNKNOWN")
                self.assertIsNone(states["UnitFileState"]["value"])
                self.assertIn("not-found", states["UnitFileState"]["reason"])

    def test_per_lane_explore_links_use_qualified_datasource_and_encoded_queries(self):
        lane = "lane:alpha/+fixture"
        def fetch(query, **kwargs):
            if "codex_api_request_total" in query:
                return vector([sample({"ecosystem_lane": lane}, NOW - 5 if "timestamp(" in query else 0.2)])
            return vector([])
        link = next(row for row in self.collect(fetch=fetch)["grafana"]["links"] if row.get("lane") == lane)
        url = urlsplit(link["url"])
        self.assertEqual(url.scheme + "://" + url.netloc + url.path, "http://127.0.0.1:21301/explore")
        params = parse_qs(url.query)
        self.assertEqual(params["schemaVersion"], ["1"])
        self.assertNotIn("orgId", params)
        panes = json.loads(params["panes"][0])
        pane = panes["fleet"]
        self.assertEqual(pane["datasource"], "ns2604-prometheus")
        self.assertEqual(pane["range"], {"from": str(int((NOW - 300) * 1000)), "to": str(int(NOW * 1000))})
        self.assertTrue(pane["queries"])
        for query in pane["queries"]:
            self.assertEqual(query["datasource"], {"uid": "ns2604-prometheus", "type": "prometheus"})
            self.assertIn('ecosystem_lane=' + json.dumps(lane), query["expr"])
            self.assertIn('instance!="unscoped"', query["expr"])

    def test_collect_attaches_tracking_using_only_injected_transports(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            state, cache, root = (base / name for name in ("state", "cache", "repo"))
            state.mkdir()
            root.mkdir()
            rows = [f"live-navi|navi|codex|us-equities-fixture|listening|1|{NOW - 10}"]
            with patch.object(fleet.time, "time", return_value=NOW), patch.object(fleet, "_tracking_fetch", side_effect=AssertionError("real HTTP is forbidden")), patch.object(fleet, "_tracking_probe", side_effect=AssertionError("real health probe is forbidden")):
                result = fleet.collect(state, cache, root, run=lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, "[]", ""),
                                       tracking_run=self.run_hcom(rows), tracking_fetch=lambda *args, **kwargs: vector([]), tracking_probe=lambda *args, **kwargs: None)
            self.assertEqual(result["schema"], "local-fleet/1")
            self.assertEqual(result["tracking"]["hcom"]["count"], 1)

    def test_collect_preserves_core_fleet_when_optional_tracking_adapter_raises(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            state, cache, root = (base / name for name in ("state", "cache", "repo"))
            state.mkdir()
            root.mkdir()
            for error in (HTTPException("PRIVATE-SYNTHETIC-ERROR"), RuntimeError("PRIVATE-SYNTHETIC-ERROR")):
                with self.subTest(error=type(error).__name__), patch.object(fleet, "collect_tracking", side_effect=error):
                    result = fleet.collect(state, cache, root, run=lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, "[]", ""))
                self.assertEqual(result["schema"], "local-fleet/1")
                self.assertIn("actions", result)
                self.assertEqual(result["tracking"]["schema"], "fleet-tracking/1")
                self.assertEqual(result["tracking"]["status"], "UNKNOWN")
                self.assertIn(type(error).__name__, result["tracking"]["reason"])
                self.assertNotIn("PRIVATE-SYNTHETIC-ERROR", json.dumps(result))

    def test_health_probe_rejects_unreviewed_or_private_endpoints_before_transport(self):
        with patch.object(fleet, "_workstation_module", side_effect=AssertionError("private endpoint reached native client")):
            for url in ("http://127.0.0.1:29374/admin/status", "http://127.0.0.1:8888/banks", "http://127.0.0.1:8231/health", "http://127.0.0.1:8232/health", "https://example.org/health"):
                with self.subTest(url=url), self.assertRaises(ValueError):
                    fleet._tracking_probe(url, timeout=1)

    def test_manager_projection_never_requests_or_retains_unselected_properties(self):
        commands = []
        def run(command, **kwargs):
            commands.append(command)
            if command[0] == "hcom":
                return subprocess.CompletedProcess(command, 0, "", "")
            return subprocess.CompletedProcess(command, 0, "LoadState=loaded\nActiveState=active\nSubState=running\nUnitFileState=enabled\nEnvironment=PRIVATE-SYNTHETIC-SENTINEL\n", "")
        tracking = fleet.collect_tracking(run=run, fetch=lambda *args, **kwargs: vector([]), probe=lambda *args, **kwargs: None, now=NOW)
        states = [row for row in tracking["services"][0]["observations"] if row["unit"] == "state"]
        self.assertEqual(len(states), 4)
        self.assertTrue(all(row["status"] == "UNKNOWN" and row["value"] is None for row in states))
        self.assertNotIn("PRIVATE-SYNTHETIC-SENTINEL", json.dumps(tracking))
        self.assertEqual(commands[-1], fleet.VLLM_STATE_COMMAND)
        self.assertFalse(any("--property=Environment" in command or "--property=ExecStart" in command for command in commands))

    def test_health_status_transport_does_not_read_bodies_or_follow_redirects(self):
        class Response:
            status = 200
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self, *args):
                raise AssertionError("health body was read")
        class Opener:
            def __init__(self, result):
                self.result = result
            def open(self, url, **kwargs):
                if isinstance(self.result, Exception):
                    raise self.result
                return self.result
        with patch("urllib.request.build_opener", return_value=Opener(Response())):
            self.assertEqual(fleet._tracking_probe("http://127.0.0.1:8888/health", timeout=1), 200)
        redirect = HTTPError("http://127.0.0.1:8888/health", 302, "redirect", {}, None)
        with patch("urllib.request.build_opener", return_value=Opener(redirect)), self.assertRaises(ValueError):
            fleet._tracking_probe("http://127.0.0.1:8888/health", timeout=1)


if __name__ == "__main__":
    unittest.main()
