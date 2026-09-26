"""Text/structural checks for the equities-broker-path observability additions.

Regex/text checks always run and need no extra dependency. A stricter YAML
structural check runs only when PyYAML is importable (optional; skipped
otherwise, matching this repo's existing NATIVE-skip pattern). The promtool/
amtool acceptance check renders the templates into a temporary directory with
the real observability/backends/configure.py and runs the pinned binaries
if they are installed at their documented paths; it skips, rather than
fails, when those binaries are absent on the host.
"""
from __future__ import annotations

import json
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "observability/backends/templates"
RULES = TEMPLATES / "ecosystem-prometheus-rules.yml.example"
SCRAPE = TEMPLATES / "ecosystem-prometheus.yml.example"
ALERTMANAGER = TEMPLATES / "ecosystem-alertmanager.yml.example"
CONFIGURE = ROOT / "observability/backends/configure.py"

# Documented installed-binary layout (observability/backends/README.md):
# $HOME/.local/share/codex-ecosystem/tools/ecosystem-<name>-<pinned-version>/<binary>
# The pinned version comes from observability/backends/pins.json, the file install.py and configure.py read,
# so a pin move runs the new binaries here instead of the retained rollback prefix.
_TOOLS_ROOT = Path.home() / ".local/share/codex-ecosystem/tools"
_PINNED = {item["id"]: item["version"]
           for item in json.loads((ROOT / "observability/backends/pins.json").read_text())["components"]}
PROMTOOL = _TOOLS_ROOT / f"ecosystem-prometheus-{_PINNED['prometheus']}/promtool"
AMTOOL = _TOOLS_ROOT / f"ecosystem-alertmanager-{_PINNED['alertmanager']}/amtool"

EXPECTED_ALERTS = {
    "EquitiesOrderStateDivergence",
    "EquitiesReconciliationFailed",
    "EquitiesRequestBudgetExhausted",
    "EquitiesLedgerFrozen",
    "EquitiesPaperMetricsMissing",
    "EquitiesLedgerUnreadable",
}

try:
    import yaml
    HAVE_YAML = True
except ImportError:
    HAVE_YAML = False


class RulesTemplateTests(unittest.TestCase):
    def setUp(self):
        self.text = RULES.read_text()

    def test_equities_broker_path_group_exists(self):
        self.assertIn("- name: equities-broker-path", self.text)

    def test_all_five_new_alerts_are_present(self):
        found = set(re.findall(r"- alert: (Equities\w+)", self.text))
        self.assertEqual(found, EXPECTED_ALERTS)

    def test_every_new_alert_is_labelled_scope_equities_broker(self):
        # Split the group body away from other groups so unrelated alerts
        # (scope: local-ecosystem) cannot satisfy this check by accident.
        group = self.text.split("- name: equities-broker-path", 1)[1]
        for alert in EXPECTED_ALERTS:
            match = re.search(rf"- alert: {alert}\n(.*?)(?=\n      - alert:|\Z)", group, re.S)
            self.assertIsNotNone(match, f"{alert} block not found")
            block = match.group(1)
            self.assertIn("scope: equities-broker", block)
            self.assertRegex(block, r"severity: (critical|warning)")
            self.assertIn("annotations:", block)
            self.assertIn("summary:", block)

    def test_divergence_alert_uses_a_five_minute_increase(self):
        self.assertIn('increase(paper_order_state_divergence_total[5m]) > 0', self.text)

    def test_ledger_frozen_alert_aggregates_by_reason(self):
        self.assertIn('max by (reason) (paper_ledger_frozen) == 1', self.text)

    def test_metrics_missing_alert_is_scoped_to_registered_exporters(self):
        # absent(paper_trial_active) fired permanently on a host with no trial; the job's
        # targets now come from file_sd, so only a registered exporter can raise the alert.
        self.assertIn('up{job="adaptive-paper"} unless on(job, instance) paper_trial_active', self.text)
        self.assertNotIn('absent(paper_trial_active)', self.text)

    def test_ledger_unreadable_alert_uses_readable_gauge(self):
        self.assertIn('paper_ledger_readable == 0', self.text)

    def test_reconciliation_failed_alert_covers_recovered_flat_needs_attention_status(self):
        # runner.py can end a trial at phase=finished with status=needs_attention (failed then
        # recovered flat); paper_needs_attention alone misses this, so the rule must also key
        # off paper_reconciliation_status{result="needs_attention"}.
        self.assertIn('paper_reconciliation_status{result="needs_attention"} == 1', self.text)

    def test_ecosystem_service_unavailable_excludes_the_optional_adaptive_paper_job(self):
        # adaptive-paper is a separate process not started by install.py/configure.py; without
        # this exclusion the generic up==0 rule fires permanently outside an active paper trial.
        match = re.search(r"- alert: EcosystemServiceUnavailable\n(.*?)(?=\n      - alert:|\Z)",
                           self.text, re.S)
        self.assertIsNotNone(match)
        self.assertIn('job!~"acceptance-fixture|adaptive-paper"', match.group(1))

    @unittest.skipUnless(HAVE_YAML, "optional PyYAML structural check")
    def test_rendered_yaml_is_well_formed_and_has_fourteen_rules(self):
        placeholder = self.text.replace("@CONFIG_ROOT@", "/tmp/x").replace("@DATA_ROOT@", "/tmp/y")
        doc = yaml.safe_load(placeholder)
        rule_count = sum(len(group["rules"]) for group in doc["groups"])
        self.assertEqual(rule_count, 14)
        names = {rule["alert"] for group in doc["groups"] for rule in group["rules"] if "alert" in rule}
        self.assertTrue(EXPECTED_ALERTS.issubset(names))


class ScrapeTemplateTests(unittest.TestCase):
    def test_adaptive_paper_job_scrapes_only_registered_exporters(self):
        text = SCRAPE.read_text()
        self.assertIn("job_name: adaptive-paper", text)
        job = text.split("job_name: adaptive-paper", 1)[1].split("job_name:", 1)[0]
        self.assertIn("file_sd_configs:", job)
        self.assertIn("'@CONFIG_ROOT@/adaptive-paper-targets.json'", job)
        self.assertNotIn("static_configs:", job)
        self.assertNotIn("127.0.0.1:18890", job)


class ConfigureTargetsTests(unittest.TestCase):
    """configure.py ships an empty adaptive-paper target list and keeps one exporters already wrote."""

    def render(self, root):
        subprocess.run(
            ["python3", str(CONFIGURE),
             "--tools-root", str(root / "tools"), "--config-root", str(root / "config"),
             "--data-root", str(root / "data"), "--unit-root", str(root / "unit")],
            check=True, capture_output=True, text=True,
        )
        return root / "config" / "adaptive-paper-targets.json"

    def test_an_empty_list_is_shipped_and_an_existing_one_is_kept(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            targets = self.render(root)
            self.assertEqual(targets.read_text(), "[]\n")
            registered = '[{"targets": ["127.0.0.1:18890"], "labels": {}}]\n'
            targets.write_text(registered)
            self.render(root)
            self.assertEqual(targets.read_text(), registered)


class AlertmanagerTemplateTests(unittest.TestCase):
    def test_equities_broker_scope_routes_to_local_ntfy(self):
        text = ALERTMANAGER.read_text()
        self.assertIn("routes:", text)
        routes_block = text.split("routes:", 1)[1]
        self.assertIn("scope: equities-broker", routes_block)
        self.assertIn("receiver: local-ntfy", routes_block)

    @unittest.skipUnless(HAVE_YAML, "optional PyYAML structural check")
    def test_rendered_yaml_route_matches_equities_broker(self):
        text = ALERTMANAGER.read_text()
        doc = yaml.safe_load(text)
        sub_routes = doc["route"].get("routes", [])
        matched = [r for r in sub_routes if r.get("match", {}).get("scope") == "equities-broker"]
        self.assertEqual(len(matched), 1)
        self.assertEqual(matched[0]["receiver"], "local-ntfy")


@unittest.skipUnless(PROMTOOL.exists() and AMTOOL.exists(),
                     "promtool/amtool not installed at the documented ecosystem tool paths")
class RenderedNativeValidationTests(unittest.TestCase):
    """Renders the real templates with configure.py, then runs the pinned binaries.

    native_proven when it runs: actual execution of the installed promtool/amtool
    against configure.py's real output, not a synthetic YAML fixture. Skipped
    (not failed) when the binaries are absent on the host.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.config_root = root / "config"
        subprocess.run(
            ["python3", str(CONFIGURE),
             "--tools-root", str(root / "tools"), "--config-root", str(self.config_root),
             "--data-root", str(root / "data"), "--unit-root", str(root / "unit")],
            check=True, capture_output=True, text=True,
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_promtool_check_rules(self):
        result = subprocess.run(
            [str(PROMTOOL), "check", "rules", str(self.config_root / "ecosystem-prometheus-rules.yml")],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("14 rules found", result.stdout)

    def test_promtool_check_config(self):
        result = subprocess.run(
            [str(PROMTOOL), "check", "config", str(self.config_root / "ecosystem-prometheus.yml")],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_amtool_check_config(self):
        result = subprocess.run(
            [str(AMTOOL), "check-config", str(self.config_root / "ecosystem-alertmanager.yml")],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


@unittest.skipUnless(PROMTOOL.exists(), "promtool not installed at the documented ecosystem tool path")
class PaperMetricsMissingRuleTests(unittest.TestCase):
    """``promtool test rules`` over configure.py's rendered rules: EquitiesPaperMetricsMissing fires only for a
    registered adaptive-paper target that returns no paper_trial_active, and never while nothing is registered.

    native_proven when it runs: the installed promtool evaluates the real rendered rule over synthetic series.
    Skipped (not failed) when promtool is absent on the host."""

    INSTANCE = "127.0.0.1:18890"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        subprocess.run(
            ["python3", str(CONFIGURE),
             "--tools-root", str(self.root / "tools"), "--config-root", str(self.root / "config"),
             "--data-root", str(self.root / "data"), "--unit-root", str(self.root / "unit")],
            check=True, capture_output=True, text=True,
        )
        self.rules = self.root / "config" / "ecosystem-prometheus-rules.yml"

    def tearDown(self):
        self.tmp.cleanup()

    def firing(self):
        # promtool compares annotations exactly, so take them from the rendered rule itself.
        block = self.rules.read_text().split("- alert: EquitiesPaperMetricsMissing\n", 1)[1].split("\n      - alert:")[0]
        annotations = {key: re.search(rf"^ +{key}: '((?:[^']|'')*)'$", block, re.M).group(1).replace("''", "'")
                       for key in ("summary", "description")}
        annotations["summary"] = annotations["summary"].replace("{{ $labels.instance }}", self.INSTANCE)
        return [{"exp_labels": {"severity": "warning", "scope": "equities-broker", "job": "adaptive-paper",
                                "instance": self.INSTANCE},
                 "exp_annotations": annotations}]

    def test_fires_only_for_a_registered_exporter_without_paper_metrics(self):
        up = f'up{{job="adaptive-paper", instance="{self.INSTANCE}"}}'
        active = f'paper_trial_active{{job="adaptive-paper", instance="{self.INSTANCE}"}}'
        cases = [
            # registered and down: pending at 1m, firing once down for two minutes
            ([(up, "0x5")], {"1m": [], "3m": self.firing()}),
            # registered and answering with the always-exported gauge: silent
            ([(up, "1x5"), (active, "0x5")], {"3m": []}),
            # registered, answering, but another process on the port: no paper_trial_active
            ([(up, "1x5")], {"3m": self.firing()}),
            # nothing registered (no adaptive-paper series at all): silent
            ([('up{job="prometheus", instance="127.0.0.1:19090"}', "1x5")], {"3m": []}),
            # deregistered after a clean stop: the stale series clears the pending alert
            ([(up, "0 0 stale")], {"1m": [], "4m": []}),
        ]
        document = {"rule_files": [str(self.rules)], "evaluation_interval": "1m", "tests": [
            {"interval": "1m",
             "input_series": [{"series": series, "values": values} for series, values in inputs],
             "alert_rule_test": [{"eval_time": at, "alertname": "EquitiesPaperMetricsMissing", "exp_alerts": alerts}
                                 for at, alerts in expected.items()]}
            for inputs, expected in cases]}
        unit_tests = self.root / "paper-metrics-missing.test.yml"
        unit_tests.write_text(json.dumps(document, indent=2))  # JSON is valid YAML
        result = subprocess.run([str(PROMTOOL), "test", "rules", str(unit_tests)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("SUCCESS", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
