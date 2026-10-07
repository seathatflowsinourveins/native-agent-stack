"""Synthetic config integration checks, not live unit/recovery acceptance."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("f09_render", ROOT / "observability/alert-lifecycle/render.py")
r = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(r)


class UserUnitRendererTests(unittest.TestCase):
    def policy(self):
        return r.load(ROOT / "observability/alert-lifecycle/policy.example.json")

    def test_promtool_fixture_rosters_use_renderable_contracts(self):
        fixtures = r.load(ROOT / "observability/alert-lifecycle/user-unit-alerts.test.json")
        checked = 0
        for case in fixtures["tests"]:
            for source in case.get("input_series", []):
                if not source["series"].startswith(r.EXPECTED + "{"):
                    continue
                labels = dict(re.findall(r'(\w+)="([^"]*)"', source["series"]))
                unit = {"name": labels["unit"], "failure_class": labels["failure_class"],
                        "severity": labels["severity"], "unit_kind": labels["unit_kind"],
                        "armed": source["values"].startswith("1"),
                        "recovery_contract": labels["recovery_contract"],
                        "completion_contract": labels["completion_contract"]}
                # Host labels are synthetic; validate the actual contract fields
                # through the production renderer, not a weaker duplicate rule.
                policy = self.policy()
                policy["units"] = [unit]
                with self.subTest(case=case["name"], unit=unit["name"]):
                    self.assertEqual(r.validate_policy(policy)["units"], [unit])
                checked += 1
        self.assertGreater(checked, 0)

    def continuous(self, name, failure_class="StackUnitDown", severity="warning"):
        return {"name": name, "failure_class": failure_class, "severity": severity,
                "unit_kind": "continuous", "armed": True,
                "recovery_contract": "active", "completion_contract": "unknown"}

    def test_example_matches_committed_receiver(self):
        self.assertEqual(r.encoded(r.receiver_config(self.policy())),
                         (ROOT / "observability/alert-lifecycle/receiver.example.json").read_text())

    def test_three_units_align_receiver_expected_and_scrape(self):
        policy = self.policy()
        policy["units"] = [
            self.continuous("paper-research.service", "PaperLaneUnitDown", "critical"),
            self.continuous("stack-writer.service"),
            self.continuous("paper-exec@ext.service", "PaperLaneUnitDown"),
        ]
        template = {"groups": [{"name": "source-rules", "rules": [{
            "record": "ns2604_user_unit_fresh_state", "expr": "systemd_unit_state"}]}]}
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
        self.assertEqual([row["labels"]["recovery_contract"] for row in expected], ["active"] * 3)
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
        # Preserve the real receiver metric and its real measurement unit.
        self.assertEqual(config["processors"]["filter/f09"]["metrics"]["metric"],
                         ['name != "systemd.unit.state"'])
        self.assertNotIn('set(name,', text)
        self.assertNotIn('set(unit,', text)
        self.assertNotIn('ns2604_user_unit_state', text)
        self.assertNotIn('time_unix_nano', text)
        self.assertNotIn('start_time', text)
        self.assertEqual(groups[0]["statements"][0],
                         'set(attributes["unit"], resource.attributes["systemd.unit.name"])')
        self.assertEqual(groups[0]["statements"][-1], 'keep_keys(attributes, ["host", "unit", "state"])')
        self.assertNotIn("transform/privacy", config["service"]["pipelines"]["metrics/f09"]["processors"])

    def test_reused_completion_is_explicitly_unknown_and_unarmed(self):
        policy = self.policy()
        rules = r.prometheus_rules(policy, {"groups": []})["groups"][0]["rules"]
        by_unit = {rule["labels"]["unit"]: rule for rule in rules}
        drill = by_unit["paper-drill-w2.service"]
        self.assertEqual(drill["expr"], "vector(1)")
        self.assertEqual(drill["labels"]["recovery_contract"], "failure-cleared")
        for name, kind in (("example-reused-oneshot.service", "oneshot"),
                           ("example-timer-run.service", "timer-service")):
            with self.subTest(unit=name):
                rule = by_unit[name]
                self.assertEqual(rule["expr"], "vector(0)")
                self.assertEqual(rule["labels"]["unit_kind"], kind)
                self.assertEqual(rule["labels"]["completion_contract"], "unknown")
                self.assertEqual(rule["labels"]["recovery_contract"], "unknown")
        # Observation remains enabled for held classes. Neither an inactive
        # completion nor a failed state may silently arm them or prove success.
        self.assertEqual(r.receiver_config(policy)["receivers"]["systemd/f09"]["units"],
                         [unit["name"] for unit in policy["units"]])

    def test_refuses_arming_reused_completion_and_unknown_recovery(self):
        for kind in ("oneshot", "timer-service"):
            for field, value in (("armed", True), ("recovery_contract", "failure-cleared"),
                                 ("recovery_contract", "active"), ("completion_contract", "success")):
                policy = self.policy()
                unit = next(row for row in policy["units"] if row["unit_kind"] == kind)
                unit[field] = value
                with self.subTest(kind=kind, field=field, value=value), self.assertRaises(ValueError):
                    r.validate_policy(policy)
        policy = self.policy()
        unit = self.continuous("stack-writer.service")
        unit["recovery_contract"] = "unknown"
        policy["units"] = [unit]
        with self.assertRaises(ValueError): r.validate_policy(policy)
        unit["armed"] = False
        self.assertEqual(r.prometheus_rules(policy, {"groups": []})["groups"][0]["rules"][0]["expr"],
                         "vector(0)")

    def test_explicit_contracts_are_required_and_drill_is_bounded(self):
        for field in ("unit_kind", "armed", "recovery_contract", "completion_contract"):
            policy = self.policy()
            del policy["units"][0][field]
            with self.subTest(field=field), self.assertRaises(ValueError): r.validate_policy(policy)
        policy = self.policy()
        policy["units"][0]["recovery_contract"] = "active"
        with self.assertRaises(ValueError): r.validate_policy(policy)
        policy["units"] = [self.continuous("stack-writer.service")]
        policy["units"][0]["recovery_contract"] = "failure-cleared"
        with self.assertRaises(ValueError): r.validate_policy(policy)
        policy = self.policy()
        policy["units"][0]["name"] = "another-drill.service"
        with self.assertRaises(ValueError): r.validate_policy(policy)

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
        for field, value in (("failure_class", "Unknown"), ("failure_class", "PaperLaneUnitFailed"),
                             ("failure_class", "StackUnitFailed"), ("severity", "info"),
                             ("unit_kind", "timer"), ("unit_kind", {}), ("armed", 1),
                             ("armed", "false"), ("recovery_contract", "healthy"),
                             ("recovery_contract", {}), ("completion_contract", {}), ("auth", {})):
            policy = self.policy(); policy["units"][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError): r.validate_policy(policy)


if __name__ == "__main__":
    unittest.main()
