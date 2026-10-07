"""Synthetic config integration checks, not live unit/recovery acceptance."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("f09_render", ROOT / "observability/alert-lifecycle/render.py")
r = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(r)


class UserUnitRendererTests(unittest.TestCase):
    def policy(self):
        return r.load(ROOT / "observability/alert-lifecycle/policy.example.json")

    def test_example_matches_committed_receiver(self):
        self.assertEqual(r.encoded(r.receiver_config(self.policy())),
                         (ROOT / "observability/alert-lifecycle/receiver.example.json").read_text())

    def test_three_units_align_receiver_expected_and_scrape(self):
        policy = self.policy()
        policy["units"] = [
            {"name": "paper-research.service", "failure_class": "PaperLaneUnitFailed", "severity": "critical"},
            {"name": "stack-writer.service", "failure_class": "StackUnitFailed", "severity": "warning"},
            {"name": "paper-exec@ext.service", "failure_class": "PaperLaneUnitFailed", "severity": "warning"},
        ]
        template = {"groups": [{"name": "source-rules", "rules": [{"record": "fresh", "expr": "state"}]}]}
        before = deepcopy((policy, template))
        receiver = r.receiver_config(policy)
        rules = r.prometheus_rules(policy, template)
        names = [unit["name"] for unit in policy["units"]]
        self.assertEqual(receiver["receivers"]["systemd/f09"]["units"], names)
        expected = rules["groups"][0]["rules"]
        self.assertEqual([row["labels"]["unit"] for row in expected], names)
        self.assertTrue(all(row["expr"] == "vector(1)" for row in expected))
        self.assertEqual([row["labels"]["failure_class"] for row in expected],
                         [row["failure_class"] for row in policy["units"]])
        self.assertEqual(rules["groups"][1], template["groups"][0])
        self.assertEqual((policy, template), before)
        scrape = r.prometheus_scrape(policy)["scrape_configs"][0]
        self.assertEqual(scrape["job_name"], "ns2604-user-unit-state")
        self.assertTrue(scrape["honor_timestamps"])
        self.assertEqual(scrape["static_configs"][0]["targets"], [policy["listen"]])

    def test_native_metric_contract_keeps_timestamps_and_namespace(self):
        config = r.receiver_config(self.policy())
        self.assertEqual(config["receivers"]["systemd/f09"]["scope"], "user")
        exporter = config["exporters"]["prometheus/f09"]
        self.assertTrue(exporter["send_timestamps"])
        self.assertEqual(exporter["metric_expiration"], "1m")
        self.assertEqual(exporter["translation_strategy"], "UnderscoreEscapingWithoutSuffixes")
        self.assertFalse(exporter["resource_to_telemetry_conversion"]["enabled"])
        groups = config["processors"]["transform/f09"]["metric_statements"]
        text = json.dumps(groups)
        self.assertIn('convert_sum_to_gauge()', text)
        self.assertIn('ns2604_user_unit_state', text)
        self.assertNotIn('time_unix_nano', text)
        self.assertNotIn('start_time', text)
        self.assertEqual(groups[0]["statements"][-1], 'keep_keys(attributes, ["host", "unit", "state"])')
        self.assertNotIn("transform/privacy", config["service"]["pipelines"]["metrics/f09"]["processors"])

    def test_rejects_duplicate_template_glob_and_unsafe_units(self):
        for name in ("bad@.service", "*.service", "bad/name.service", "bad name.service", "x.timer", "x\\n.service", "-x.service", "x@@a.service"):
            policy = self.policy(); policy["units"][0]["name"] = name
            with self.subTest(name=name), self.assertRaises(ValueError):
                r.validate_policy(policy)
        policy = self.policy(); policy["units"] *= 2
        with self.assertRaises(ValueError): r.validate_policy(policy)

    def test_rejects_unknown_fields_hosts_ports_and_enums(self):
        for field, value in (("host", "OtherHost"), ("listen", "0.0.0.0:21890"), ("listen", "localhost:21890"),
                             ("listen", "127.0.0.1:99999"), ("units", []), ("password", "example")):
            policy = self.policy(); policy[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError): r.validate_policy(policy)
        for field, value in (("failure_class", "Unknown"), ("severity", "info"), ("auth", {})):
            policy = self.policy(); policy["units"][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError): r.validate_policy(policy)


if __name__ == "__main__":
    unittest.main()
