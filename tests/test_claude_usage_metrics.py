"""Offline Claude usage contracts: synthetic streams, ledger values and real exposition."""
import importlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

PROMTOOL = os.environ.get("CLAUDE_USAGE_PROMTOOL") or shutil.which("promtool")


def event(status="allowed", **info):
    return {"type": "rate_limit_event", "rate_limit_info": {"status": status, **info}}


class ClaudeUsageMetricsTests(unittest.TestCase):
    def setUp(self):
        self.metrics = importlib.import_module("observability.claude_usage_metrics")
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        self.capture = self.root / "capture.jsonl"
        self.ledger = self.root / "ledger.jsonl"
        self.ledger.write_text("")
        self.output = self.root / "claude-usage.prom"
        self.state = self.root / "state.json"

    def export(self, events, *, rows=None, captured_at=1990, now=2000, legacy=None):
        self.capture.write_text("\n".join(json.dumps(e) for e in events) + "\n")
        os.utime(self.capture, (captured_at, captured_at))
        if rows is not None:
            self.ledger.write_text("\n".join(json.dumps(r) for r in rows))
        self.metrics.collect({"acct-1": self.capture}, self.ledger, self.state, self.output,
                             now=now, legacy_key_alias=legacy)
        return self.output.read_text()

    def samples(self, name, **labels):
        from prometheus_client.parser import text_string_to_metric_families
        return [s for f in text_string_to_metric_families(self.output.read_text()) for s in f.samples
                if s.name == name and all(s.labels.get(k) == v for k, v in labels.items())]

    def value(self, name, **labels):
        samples = self.samples(name, **labels)
        self.assertEqual(1, len(samples), (name, labels, samples))
        return samples[0].value

    def test_allowed_native_single_window_uses_fraction_and_epoch_seconds(self):
        self.export([event(rateLimitType="five_hour", utilization=.42, resetsAt=2300)])
        self.assertEqual(.42, self.value("claude_max_utilization_ratio", account="acct-1", window="five_hour"))
        self.assertEqual(2300, self.value("claude_max_reset_timestamp_seconds", window="five_hour"))
        self.assertEqual(1990, self.value("claude_max_observed_timestamp_seconds", window="five_hour"))
        self.assertFalse(self.samples("claude_max_utilization_ratio", window="seven_day"))

    def test_warning_and_cc_unified_windows_keep_independent_values(self):
        self.export([event("allowed_warning", unifiedWindows={
            "five_hour": {"utilization": .91, "resetsAt": 2100},
            "seven_day": {"utilization": .36, "resetsAt": 9000}})])
        self.assertEqual(.91, self.value("claude_max_utilization_ratio", window="five_hour"))
        self.assertEqual(.36, self.value("claude_max_utilization_ratio", window="seven_day"))
        self.assertEqual(9000, self.value("claude_max_reset_timestamp_seconds", window="seven_day"))

    def test_rejected_native_window_with_missing_or_zero_usage_is_one(self):
        for value in (None, 0, .75):
            with self.subTest(value=value):
                self.export([event("rejected", rateLimitType="five_hour", utilization=value)])
                self.assertEqual(1.0, self.value("claude_max_utilization_ratio", window="five_hour"))
                self.assertFalse(self.samples("claude_max_utilization_ratio", window="seven_day"))

    def test_unscoped_rejection_is_conservatively_one_for_both_windows(self):
        self.export([event("rejected")])
        for window in ("five_hour", "seven_day"):
            self.assertEqual(1.0, self.value("claude_max_utilization_ratio", window=window))
        self.assertFalse(self.samples("claude_max_reset_timestamp_seconds"))

    def test_scoped_rejected_unified_window_does_not_overwrite_other_window(self):
        self.export([event("rejected", rateLimitType="five_hour", unifiedWindows={
            "five_hour": {"resetsAt": 2300}, "seven_day": {"utilization": .2}})])
        self.assertEqual(1.0, self.value("claude_max_utilization_ratio", window="five_hour"))
        self.assertEqual(.2, self.value("claude_max_utilization_ratio", window="seven_day"))

    def test_rejection_still_exhausts_window_with_malformed_optional_child_metadata(self):
        self.export([event("rejected", rateLimitType="five_hour", unifiedWindows={
            "five_hour": {"status": "unrecognized", "utilization": None}})])
        self.assertEqual(1.0, self.value("claude_max_utilization_ratio", window="five_hour"))
        self.assertGreater(self.value("claude_usage_input_errors", source="capture"), 0)

    def test_exhausted_numeric_usage_saturates_at_one(self):
        self.export([event(rateLimitType="seven_day", utilization=1.1)])
        self.assertEqual(1.0, self.value("claude_max_utilization_ratio", window="seven_day"))

    def test_missing_windows_and_utilization_never_invent_zero_or_reset(self):
        self.export([event(unifiedWindows={"five_hour": {"resetsAt": 2300}})])
        self.assertFalse(self.samples("claude_max_utilization_ratio"))
        self.assertEqual(2300, self.value("claude_max_reset_timestamp_seconds", window="five_hour"))
        self.assertFalse(self.samples("claude_max_reset_timestamp_seconds", window="seven_day"))

    def test_transition_without_usage_preserves_value_and_original_freshness(self):
        self.export([event(rateLimitType="five_hour", utilization=.7, resetsAt=2300)])
        self.export([event(rateLimitType="five_hour")], captured_at=2010, now=2020)
        self.assertEqual(.7, self.value("claude_max_utilization_ratio", window="five_hour"))
        self.assertEqual(1990, self.value("claude_max_observed_timestamp_seconds", window="five_hour"))
        self.assertEqual(2010, self.value("claude_max_capture_timestamp_seconds", account="acct-1"))

    def test_replaying_an_older_capture_cannot_replace_a_newer_observation(self):
        self.export([event("rejected", rateLimitType="five_hour")], captured_at=1990)
        self.export([event(rateLimitType="five_hour", utilization=.1)], captured_at=1900)
        self.assertEqual(1, self.value("claude_max_utilization_ratio", window="five_hour"))
        self.assertEqual(1990, self.value("claude_max_observed_timestamp_seconds", window="five_hour"))

    def test_malformed_json_and_values_are_bounded_errors_and_unknown_usage(self):
        self.capture.write_text('{broken\n' + json.dumps(event(rateLimitType="five_hour", utilization=-1,
                                                              resetsAt="tomorrow")) + "\n")
        os.utime(self.capture, (1990, 1990))
        self.metrics.collect({"acct-1": self.capture}, self.ledger, self.state, self.output, now=2000)
        self.assertFalse(self.samples("claude_max_utilization_ratio"))
        self.assertGreater(self.value("claude_usage_input_errors", source="capture"), 0)

    def test_future_capture_is_unknown_and_missing_capture_keeps_old_age(self):
        self.export([event("rejected")])
        self.capture.unlink()
        self.metrics.collect({"acct-1": self.capture}, self.ledger, self.state, self.output, now=10000)
        self.assertEqual(0, self.value("claude_max_capture_success", account="acct-1"))
        self.assertEqual(1990, self.value("claude_max_observed_timestamp_seconds", window="five_hour"))
        self.export([event(rateLimitType="five_hour", utilization=.1)], captured_at=11000, now=10000)
        self.assertEqual(1, self.value("claude_max_utilization_ratio", window="five_hour"))

    def test_output_and_state_ignore_prompt_response_identity_and_key_alias(self):
        poison = "private-fixture@example.invalid"
        text = self.export([
            {"type": "assistant", "prompt": poison, "response": poison, "org": poison},
            {**event(rateLimitType="five_hour", utilization=.3), "email": poison}], rows=[
                {"kind": "settle", "ref": "opaque-ref", "key": "fixture-key-private", "actual_usd": 4,
                 "prompt": poison, "detail": {"response": poison}}])
        for source in (text, self.state.read_text()):
            self.assertNotIn(poison, source)
            self.assertNotIn("fixture-key-private", source)
            self.assertNotIn("opaque-ref", source)
        for name in ("claude_max_utilization_ratio", "claude_api_spend_usd"):
            for sample in self.samples(name):
                self.assertLessEqual(set(sample.labels), {"account", "window", "key"})

    def test_nonopaque_account_is_rejected_without_echoing_it(self):
        with self.assertRaises(self.metrics.InputError) as raised:
            self.metrics.collect({"person@example.invalid": self.capture}, self.ledger,
                                 self.state, self.output, now=2000)
        self.assertNotIn("example.invalid", str(raised.exception))

    def test_ledger_settlement_attribution_reservations_voids_and_snapshots(self):
        self.export([], rows=[
            {"kind": "debit", "ref": "a", "key": "fixture-a", "max_usd": 10},
            {"kind": "settle", "ref": "a", "key": "fixture-b", "actual_usd": 2},
            {"kind": "debit", "ref": "b", "key": "fixture-b", "max_usd": 7},
            {"kind": "debit", "ref": "v", "key": "fixture-a", "max_usd": 20},
            {"kind": "void", "ref": "v", "actual_usd": 0},
            {"kind": "debit", "ref": "u", "key": "fixture-a", "max_usd": 5},
            {"kind": "settle", "ref": "u", "actual_usd": 5, "outcome": "unknown"},
            {"kind": "provider_snapshot", "actual_usd": 999, "console": {"spend_this_month_usd": 888}},
            {"kind": "note", "actual_usd": 999}])
        spends = sorted(s.value for s in self.samples("claude_api_spend_usd"))
        self.assertEqual([0, 7], spends)
        self.assertEqual([0, 7], sorted(s.value for s in self.samples("claude_api_pending_usd")))
        self.assertEqual([0, 5], sorted(s.value for s in self.samples("claude_api_uncertain_usd")))
        self.assertEqual([200, 200], [s.value for s in self.samples("claude_api_edge_usd")])

    def test_legacy_rows_are_unattributed_until_explicit_producer_alias_is_supplied(self):
        rows = [{"kind": "debit", "ref": "legacy", "max_usd": 10},
                {"kind": "settle", "ref": "legacy", "actual_usd": 3}]
        self.export([], rows=rows)
        self.assertEqual(3, self.value("claude_api_unattributed_spend_usd"))
        self.assertFalse(self.samples("claude_api_edge_usd"))
        self.export([], rows=rows, legacy="fixture-legacy-alias")
        self.assertEqual(3, self.value("claude_api_spend_usd", key="key-1"))
        self.assertEqual(0, self.value("claude_api_unattributed_spend_usd"))

    def test_key_indexes_are_persistent_when_the_pool_grows(self):
        first = {"kind": "settle", "ref": "a", "key": "fixture-z", "actual_usd": 30}
        self.export([], rows=[first])
        self.assertEqual(30, self.value("claude_api_spend_usd", key="key-1"))
        self.export([], rows=[first, {"kind": "settle", "ref": "b", "key": "fixture-a", "actual_usd": 2}])
        self.assertEqual(30, self.value("claude_api_spend_usd", key="key-1"))
        self.assertEqual(2, self.value("claude_api_spend_usd", key="key-2"))

    def test_malformed_financial_rows_do_not_publish_partial_spend(self):
        self.export([], rows=[{"kind": "settle", "ref": "a", "key": "fixture-a", "actual_usd": 4},
                              {"kind": "settle", "ref": "b", "key": "fixture-a", "actual_usd": "unknown"}])
        self.assertFalse(self.samples("claude_api_spend_usd"))
        self.assertEqual(0, self.value("claude_usage_ledger_success"))
        self.assertEqual(1, self.value("claude_usage_input_errors", source="ledger"))

    def test_signed_reconciliation_credit_reduces_the_keys_accounted_charges(self):
        self.export([], rows=[{"kind": "settle", "ref": "charge", "key": "fixture-a", "actual_usd": 20},
                              {"kind": "settle", "ref": "credit", "key": "fixture-a", "actual_usd": -3}])
        self.assertEqual(17, self.value("claude_api_spend_usd", key="key-1"))
        self.assertEqual(1, self.value("claude_usage_ledger_success"))

    def test_exposition_contains_gauge_values_without_sample_timestamps(self):
        self.export([event("rejected", rateLimitType="five_hour", resetsAt=2300)])
        from prometheus_client.parser import text_string_to_metric_families
        families = list(text_string_to_metric_families(self.output.read_text()))
        self.assertTrue(families)
        self.assertTrue(all(f.type == "gauge" for f in families))
        self.assertTrue(all(s.timestamp is None for f in families for s in f.samples))
        self.assertEqual(2000, self.value("claude_usage_collection_timestamp_seconds"))


class ClaudeUsageDashboardTests(unittest.TestCase):
    def setUp(self):
        self.builder = importlib.import_module("observability.lanes_dashboard")
        self.board = self.builder.dashboard()

    def test_usage_row_follows_request_tokens_and_preserves_existing_ids(self):
        panels = self.board["panels"]
        anchor = next(i for i, p in enumerate(panels) if p["title"] == "Claude request usage by native session")
        self.assertEqual("Claude usage", panels[anchor + 1]["title"])
        self.assertEqual("row", panels[anchor + 1]["type"])
        self.assertFalse(panels[anchor + 1]["collapsed"])
        self.assertEqual(9, next(p for p in panels if p["title"] == "Native API errors and rate limits")["id"])
        self.assertEqual(len(panels), len({p["id"] for p in panels}))

    def test_limit_bars_use_fraction_instant_queries_and_staleness_without_zero_fallback(self):
        for window in ("five_hour", "seven_day"):
            panel = next(p for p in self.board["panels"] if p["title"] == f"Claude Max · {window}")
            self.assertEqual("bargauge", panel["type"])
            defaults = panel["fieldConfig"]["defaults"]
            self.assertEqual(("percentunit", 0, 1, "UNKNOWN"),
                             (defaults["unit"], defaults["min"], defaults["max"], defaults["noValue"]))
            target = panel["targets"][0]
            self.assertTrue(target["instant"])
            self.assertIn("claude_max_observed_timestamp_seconds", target["expr"])
            self.assertIn("1800", target["expr"])
            self.assertNotIn("vector(0)", target["expr"])
            self.assertEqual(self.builder.PROMETHEUS, target["datasource"])
            self.assertIn("http://127.0.0.1:21128/dashboard/analytics", [l["url"] for l in panel["links"]])

    def test_reset_unit_api_edge_and_ledger_accounting_are_explicit(self):
        resets = next(p for p in self.board["panels"] if p["title"] == "Claude Max · reset time")
        self.assertIn("* 1000", resets["targets"][0]["expr"])
        self.assertEqual("dateTimeAsIso", resets["fieldConfig"]["defaults"]["unit"])
        spend = next(p for p in self.board["panels"] if p["title"] == "Anthropic API · $200 edge")
        self.assertIn("claude_api_spend_usd / claude_api_edge_usd", spend["targets"][0]["expr"])
        self.assertIn("uncertain", spend["description"])
        self.assertIn("reservations", spend["description"])
        self.assertEqual("percentunit", spend["fieldConfig"]["defaults"]["unit"])

    @unittest.skipUnless(PROMTOOL, "native query integration needs promtool (or CLAUDE_USAGE_PROMTOOL)")
    def test_native_dashboard_queries_return_exhausted_one_and_hide_stale_data(self):
        import yaml
        panels = {p["title"]: p for p in self.board["panels"]}
        labels = 'job="node-exporter",instance="loopback"'

        def series(name, value, extra=""):
            return {"series": f'{name}{{{labels}{extra}}}', "values": f"{value}+0x65"}

        inputs = [series("claude_usage_collection_timestamp_seconds", 1900),
                  series("claude_usage_ledger_success", 1)]
        for account, stamp in (("acct-1", 1900), ("acct-2", 1)):
            fields = f',account="{account}",window="five_hour"'
            inputs.extend([series("claude_max_utilization_ratio", 1, fields),
                           series("claude_max_observed_timestamp_seconds", stamp, fields),
                           series("claude_max_reset_timestamp_seconds", 2500, fields),
                           series("claude_max_reset_observed_timestamp_seconds", stamp, fields)])
        fields = ',account="acct-1",window="seven_day"'
        inputs.extend([series("claude_max_utilization_ratio", .25, fields),
                       series("claude_max_observed_timestamp_seconds", 1900, fields)])
        inputs.extend([series("claude_api_spend_usd", 200, ',key="key-1"'),
                       series("claude_api_edge_usd", 200, ',key="key-1"')])
        cases = []
        for title, expected in (
            ("Claude Max · five_hour", [{"labels": '{account="acct-1"}', "value": 1.0}]),
            ("Claude Max · seven_day", [{"labels": '{account="acct-1"}', "value": .25}]),
            ("Claude Max · reset time", [{"labels": '{account="acct-1",window="five_hour"}', "value": 2500000}]),
            ("Anthropic API · $200 edge", [{"labels": '{key="key-1"}', "value": 1.0}]),
        ):
            expression = panels[title]["targets"][0]["expr"]
            cases.extend([{"expr": expression, "eval_time": "33m", "exp_samples": expected},
                          {"expr": expression, "eval_time": "65m", "exp_samples": []}])
        document = {"rule_files": [], "evaluation_interval": "1m",
                    "tests": [{"interval": "1m", "input_series": inputs, "promql_expr_test": cases}]}
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / "usage.test.yml"
            fixture.write_text(yaml.safe_dump(document))
            result = subprocess.run([PROMTOOL, "test", "rules", str(fixture)],
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
