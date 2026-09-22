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
_TOOLS_ROOT = Path.home() / ".local/share/codex-ecosystem/tools"
PROMTOOL = _TOOLS_ROOT / "ecosystem-prometheus-3.14.0/promtool"
AMTOOL = _TOOLS_ROOT / "ecosystem-alertmanager-0.34.1/amtool"

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

    def test_metrics_missing_alert_uses_absent(self):
        self.assertIn('absent(paper_trial_active)', self.text)

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
    def test_adaptive_paper_job_targets_the_exporter_port(self):
        text = SCRAPE.read_text()
        self.assertIn("job_name: adaptive-paper", text)
        job = text.split("job_name: adaptive-paper", 1)[1].split("job_name:", 1)[0]
        self.assertIn("127.0.0.1:18890", job)


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


if __name__ == "__main__":
    unittest.main()
