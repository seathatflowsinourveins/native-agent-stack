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

from concurrent.futures import ThreadPoolExecutor
import fcntl
import json
import re
import runpy
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request
from pathlib import Path
from unittest.mock import patch

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
ALERTMANAGER_BIN = _TOOLS_ROOT / f"ecosystem-alertmanager-{_PINNED['alertmanager']}/alertmanager"
# The lane routes' own grouping (ecosystem-alertmanager.yml.example); the negative control below removes these lines.
LANE_GROUP_BY = "      group_by: [alertname, scope, ecosystem_lane]\n"

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
    def test_rendered_yaml_is_well_formed_and_has_twenty_one_rules(self):
        placeholder = self.text.replace("@CONFIG_ROOT@", "/tmp/x").replace("@DATA_ROOT@", "/tmp/y")
        doc = yaml.safe_load(placeholder)
        rule_count = sum(len(group["rules"]) for group in doc["groups"])
        self.assertEqual(rule_count, 21)
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

    def test_initialization_keeps_a_registration_created_after_observing_an_absent_list(self):
        update_file_sd = runpy.run_path(str(ROOT / "blueprints/us-equities/adaptive-paper/metrics.py"))[
            "update_file_sd"]
        with tempfile.TemporaryDirectory() as tmp, ThreadPoolExecutor(max_workers=1) as workers:
            root = Path(tmp)
            targets = root / "config" / "adaptive-paper-targets.json"
            registrations = []
            exists = Path.exists

            def exists_then_register(path):
                observed = exists(path)
                if path == targets and not observed and not registrations:
                    # Inject the exporter after the absence check. If configure holds the sibling lock,
                    # the real exporter writer must wait until initialization releases it.
                    with open(targets.with_name(targets.name + ".lock"), "a") as probe:
                        try:
                            fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        except BlockingIOError:
                            locked = True
                        else:
                            locked = False
                    registration = workers.submit(update_file_sd, targets, "127.0.0.1:18890", registered=True)
                    registrations.append(registration)
                    if not locked:
                        registration.result(timeout=10)
                return observed

            argv = [str(CONFIGURE), "--tools-root", str(root / "tools"), "--config-root", str(root / "config"),
                    "--data-root", str(root / "data"), "--unit-root", str(root / "unit")]
            with patch.object(sys, "argv", argv), patch.object(Path, "exists", exists_then_register):
                runpy.run_path(str(CONFIGURE), run_name="__main__")
            self.assertEqual(len(registrations), 1)
            registrations[0].result(timeout=10)
            self.assertEqual(json.loads(targets.read_text()),
                             [{"targets": ["127.0.0.1:18890"], "labels": {}}],
                             "initialization erased the concurrent exporter's registration")


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

    @unittest.skipUnless(HAVE_YAML, "optional PyYAML structural check")
    def test_both_lane_routes_group_by_lane_and_the_other_routes_inherit(self):
        # The lane rules sum job away, so the inherited [alertname, job, scope] would put every lane in one group.
        doc = yaml.safe_load(ALERTMANAGER.read_text())
        routes = doc["route"]["routes"]
        lanes = [r for r in routes if r.get("match", {}).get("scope") == "codex-lanes"]
        self.assertEqual(len(lanes), 2)
        self.assertEqual([r["group_by"] for r in lanes], [["alertname", "scope", "ecosystem_lane"]] * 2)
        self.assertEqual(doc["route"]["group_by"], ["alertname", "job", "scope"])
        self.assertEqual([r for r in routes if r not in lanes and "group_by" in r], [])
        self.assertEqual(ALERTMANAGER.read_text().count(LANE_GROUP_BY), 2)

    def test_operator_instructions_subscribe_to_and_poll_every_topic(self):
        # A topic missing from the setup and verification instructions has no subscriber, although Alertmanager
        # reports a successful delivery (PR #671 review).
        topics = re.findall(r"url: 'http://127\.0\.0\.1:18080/([a-z-]+)\?template=alertmanager'", ALERTMANAGER.read_text())
        self.assertEqual(topics, ["ecosystem-alerts", "ecosystem-lanes"])
        backends = (ROOT / "observability/backends/README.md").read_text()
        overview = (ROOT / "observability/README.md").read_text()
        for topic in topics:
            with self.subTest(topic=topic):
                poll = f"curl --fail --silent 'http://127.0.0.1:18080/{topic}/json?poll=1&since=all'"
                self.assertIn(poll, backends)
                self.assertIn(poll, overview)
                self.assertIn(f"`http://127.0.0.1:18080/{topic}`", backends)


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
        self.assertIn("21 rules found", result.stdout)

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


def render_backends(root: Path) -> Path:
    subprocess.run(
        ["python3", str(CONFIGURE),
         "--tools-root", str(root / "tools"), "--config-root", str(root / "config"),
         "--data-root", str(root / "data"), "--unit-root", str(root / "unit")],
        check=True, capture_output=True, text=True,
    )
    return root / "config"


@unittest.skipUnless(PROMTOOL.exists(), "promtool not installed at the documented ecosystem tool path")
class CodexLaneRuleTests(unittest.TestCase):
    """``promtool test rules`` over configure.py's rendered ecosystem-lanes group, with synthetic series.

    A goal event counter reaches Prometheus as a delta point that the Collector's delta_to_cumulative converts: the
    new series starts at 0 (Prometheus created-timestamp-zero-ingestion), reads 1 while Codex exports it and goes
    stale five minutes after the last export. native_proven when it runs: the installed promtool evaluates the real
    rendered rules. Skipped (not failed) when promtool is absent on the host."""

    LANE = 'job="codex_exec",instance="proc-a",ecosystem_lane="root"'

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.rules = render_backends(self.root) / "ecosystem-prometheus-rules.yml"
        group = self.rules.read_text().split("  - name: ecosystem-lanes\n", 1)[1].split("\n  - name: ", 1)[0]
        # promtool compares annotations exactly, so take labels and annotations from the rendered rules themselves.
        self.by_name = {}
        for name, block in re.findall(r"- alert: (\w+)\n(.*?)(?=\n      - alert: |\Z)", group, re.S):
            self.by_name[name] = {
                "labels": dict(re.findall(r"^          (severity|scope): (\S+)$", block, re.M)),
                "annotations": {key: re.search(rf"^ +{key}: '((?:[^']|'')*)'$", block, re.M).group(1).replace("''", "'")
                                for key in ("summary", "description")}}

    def tearDown(self):
        self.tmp.cleanup()

    def firing(self, alert, lane="root"):
        rule = self.by_name[alert]
        annotations = {k: v.replace("{{ $labels.ecosystem_lane }}", lane) for k, v in rule["annotations"].items()}
        return [{"exp_labels": {**rule["labels"], "ecosystem_lane": lane}, "exp_annotations": annotations}]

    def check(self, alert, cases):
        document = {"rule_files": [str(self.rules)], "evaluation_interval": "1m", "tests": [
            {"interval": "1m", "input_series": [{"series": s, "values": v} for s, v in inputs],
             "alert_rule_test": [{"eval_time": at, "alertname": alert, "exp_alerts": exp} for at, exp in expected]}
            for inputs, expected in cases]}
        path = self.root / f"{alert}.test.yml"
        path.write_text(json.dumps(document))  # JSON is valid YAML
        result = subprocess.run([str(PROMTOOL), "test", "rules", str(path)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_every_lane_rule_is_scoped_and_usage_limits_are_critical(self):
        self.assertEqual(set(self.by_name), {"CodexLaneGoalBlocked", "CodexLaneToolErrorBurst",
                                             "CodexLaneMcpErrorRatio", "CodexLaneUsageLimited"})
        self.assertEqual({rule["labels"]["scope"] for rule in self.by_name.values()}, {"codex-lanes"})
        self.assertEqual({name: rule["labels"]["severity"] for name, rule in self.by_name.items()},
                         {"CodexLaneGoalBlocked": "warning", "CodexLaneToolErrorBurst": "warning",
                          "CodexLaneMcpErrorRatio": "warning", "CodexLaneUsageLimited": "critical"})

    def test_goal_events_fire_at_once_and_keep_firing_after_their_series_expires(self):
        for alert, metric in (("CodexLaneGoalBlocked", "ecosystem_codex_goal_blocked_total"),
                              ("CodexLaneUsageLimited", "ecosystem_codex_goal_usage_limited_total")):
            series = f"{metric}{{{self.LANE}}}"
            fire = self.firing(alert)
            self.check(alert, [
                # One event, exported for five minutes and then dropped. The 15-minute window holds it until 14m;
                # keep_firing_for holds the alert for 30 minutes after that.
                ([(series, "0 1 1 1 1 1 stale")], [("1m", fire), ("14m", fire), ("40m", fire), ("50m", [])]),
                ([(series, "0x30")], [("10m", [])]),
            ])

    def test_tool_errors_fire_above_ten_percent_of_at_least_thirty_calls_after_fifteen_minutes(self):
        tool = "ecosystem_codex_tool_call_total{" + self.LANE + ',success="%s"}'
        fire = self.firing("CodexLaneToolErrorBurst")
        self.check("CodexLaneToolErrorBurst", [
            # 72 calls an hour, 12 failed (16.7%): 30 calls by 25m, firing 15 minutes later
            ([(tool % "true", "0+1x90"), (tool % "false", "0+0.2x90")], [("30m", []), ("45m", fire), ("70m", fire)]),
            # the same share of 18 calls an hour
            ([(tool % "true", "0+0.25x90"), (tool % "false", "0+0.05x90")], [("70m", [])]),
            # 61 calls an hour, 1 failed
            ([(tool % "true", "0+1x90"), (tool % "false", "0+0.0167x90")], [("70m", [])]),
        ])

    def test_mcp_errors_fire_above_ten_percent_of_at_least_twenty_calls_after_fifteen_minutes(self):
        calls = "ecosystem_codex_mcp_call_total{" + self.LANE + ',tool="ctx_search",status="%s"}'
        errors = "ecosystem_codex_mcp_call_error_total{" + self.LANE + ',tool="ctx_search",status="error"}'
        fire = self.firing("CodexLaneMcpErrorRatio")
        self.check("CodexLaneMcpErrorRatio", [
            # 60 calls an hour, 12 errors (20%): 20 calls by 20m, firing 15 minutes later
            ([(calls % "ok", "0+0.8x90"), (calls % "error", "0+0.2x90"), (errors, "0+0.2x90")],
             [("30m", []), ("45m", fire)]),
            # the same share of 15 calls an hour
            ([(calls % "ok", "0+0.2x90"), (calls % "error", "0+0.05x90"), (errors, "0+0.05x90")], [("70m", [])]),
        ])


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@unittest.skipUnless(AMTOOL.exists(), "amtool not installed at the documented ecosystem tool path")
class CodexLaneRouteTests(unittest.TestCase):
    """``amtool config routes test`` over configure.py's rendered Alertmanager config: lane warnings go to their own (separate, mutable)
    topic, critical lane alerts to the alert topic, and the other routes are unchanged. That command prints receivers only
    (in simple, extended and json output alike), so the grouping test runs the pinned Alertmanager itself on the rendered
    config, with alerts added by the pinned amtool, and reads its groups API. native_proven when it runs."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.config = render_backends(Path(self.tmp.name)) / "ecosystem-alertmanager.yml"

    def tearDown(self):
        self.tmp.cleanup()

    def assertRoute(self, receiver, *labels):
        result = subprocess.run([str(AMTOOL), "config", "routes", "test", f"--config.file={self.config}",
                                 f"--verify.receivers={receiver}", *labels], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_lane_warnings_use_their_own_topic_and_critical_lane_alerts_reach_the_alert_topic(self):
        self.assertRoute("local-ntfy-lanes", "alertname=CodexLaneGoalBlocked", "scope=codex-lanes", "severity=warning")
        self.assertRoute("local-ntfy", "alertname=CodexLaneUsageLimited", "scope=codex-lanes", "severity=critical")
        self.assertRoute("local-ntfy", "scope=equities-broker", "severity=warning")
        self.assertRoute("local-ntfy", "scope=local-ecosystem", "severity=warning")
        self.assertIn("/ecosystem-lanes?template=alertmanager'", self.config.read_text())
        # ntfy 2.28.0 ignores a query priority in template mode (server_template.go L58, L103 at 10cb6506), so none is promised.
        self.assertNotIn("priority=", self.config.read_text())

    def test_every_lane_routes_alike(self):
        for lane in ("root", "trading"):
            with self.subTest(lane=lane):
                self.assertRoute("local-ntfy-lanes", "alertname=CodexLaneGoalBlocked", "scope=codex-lanes",
                                 "severity=warning", f"ecosystem_lane={lane}")
                self.assertRoute("local-ntfy", "alertname=CodexLaneUsageLimited", "scope=codex-lanes",
                                 "severity=critical", f"ecosystem_lane={lane}")

    @unittest.skipUnless(ALERTMANAGER_BIN.exists(), "alertmanager not installed at the documented ecosystem tool path")
    def test_two_lanes_form_two_groups_and_without_the_lane_grouping_share_one(self):
        # A socket that is bound but never listens refuses every connection, so no webhook of these instances can reach
        # the live ntfy that the rendered receivers name.
        with socket.socket() as refusing:
            refusing.bind(("127.0.0.1", 0))
            text, count = re.subn(r"url: 'http://127\.0\.0\.1:\d+/",
                                  f"url: 'http://127.0.0.1:{refusing.getsockname()[1]}/", self.config.read_text())
            self.assertEqual(count, 2)

            def group(alert, lane):
                return ("alertname", alert), ("ecosystem_lane", lane), ("scope", "codex-lanes")

            self.assertEqual(self.groups(text), [
                ("local-ntfy", group("CodexLaneUsageLimited", "root"), ("root",)),
                ("local-ntfy", group("CodexLaneUsageLimited", "trading"), ("trading",)),
                ("local-ntfy-lanes", group("CodexLaneGoalBlocked", "root"), ("root",)),
                ("local-ntfy-lanes", group("CodexLaneGoalBlocked", "trading"), ("trading",))])
            # Negative control: without the override both routes inherit [alertname, job, scope], and the two lanes
            # share one group (one notification, one status) per alert.
            inherited, removed = re.subn(re.escape(LANE_GROUP_BY), "", text)
            self.assertEqual(removed, 2)
            self.assertEqual(self.groups(inherited), [
                ("local-ntfy", (("alertname", "CodexLaneUsageLimited"), ("scope", "codex-lanes")), ("root", "trading")),
                ("local-ntfy-lanes", (("alertname", "CodexLaneGoalBlocked"), ("scope", "codex-lanes")),
                 ("root", "trading"))])

    def groups(self, text):
        """Run the pinned Alertmanager on text, add a warning and a critical lane alert for each of two lanes with the
        pinned amtool, and return /api/v2/alerts/groups as sorted (receiver, group labels, lanes) once all four are in."""
        root = Path(tempfile.mkdtemp(dir=self.tmp.name))
        (root / "data").mkdir()
        config = root / "alertmanager.yml"
        config.write_text(text)
        address = f"127.0.0.1:{free_port()}"
        url = f"http://{address}"
        with open(root / "alertmanager.log", "w") as log:
            process = subprocess.Popen(
                [str(ALERTMANAGER_BIN), f"--config.file={config}", f"--storage.path={root / 'data'}",
                 f"--web.listen-address={address}", "--cluster.listen-address="],
                stdout=log, stderr=subprocess.STDOUT)
            try:
                deadline = time.time() + 30
                while True:
                    try:
                        urllib.request.urlopen(f"{url}/-/ready", timeout=1).read()
                        break
                    except OSError:
                        if time.time() > deadline or process.poll() is not None:
                            self.fail((root / "alertmanager.log").read_text())
                        time.sleep(0.2)
                for lane in ("root", "trading"):
                    for alert, severity in (("CodexLaneGoalBlocked", "warning"), ("CodexLaneUsageLimited", "critical")):
                        result = subprocess.run(
                            [str(AMTOOL), "alert", "add", f"--alertmanager.url={url}", f"alertname={alert}",
                             "scope=codex-lanes", f"severity={severity}", f"ecosystem_lane={lane}"],
                            capture_output=True, text=True)
                        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                # The dispatcher groups alerts asynchronously; read until it holds all four.
                deadline = time.time() + 10
                while True:
                    groups = json.loads(urllib.request.urlopen(f"{url}/api/v2/alerts/groups", timeout=5).read())
                    if sum(len(g["alerts"]) for g in groups) == 4 or time.time() > deadline:
                        break
                    time.sleep(0.2)
            finally:
                process.terminate()
                try:
                    process.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
        return sorted((g["receiver"]["name"], tuple(sorted(g["labels"].items())),
                       tuple(sorted(a["labels"]["ecosystem_lane"] for a in g["alerts"]))) for g in groups)


if __name__ == "__main__":
    unittest.main()
