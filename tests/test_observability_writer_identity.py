"""Writer identity for the native token counters (observability/collector/README.md#writer-identity-and-counter-integrity).

Structural checks always run (the YAML ones need PyYAML). Two classes run the pinned upstream binaries when they are
installed at their documented paths and skip otherwise: promtool evaluates the native-telemetry-integrity rules over
synthetic series, and otelcol-contrib runs the committed metrics pipeline on synthetic OTLP input from two Claude
sessions and two Codex processes. Both are local integration checks on synthetic data, not a model run or host
acceptance; the host proof compares live Prometheus with Loki over real sessions and is recorded separately.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COLLECTOR = ROOT / "observability/collector/collector.yaml"
LAUNCHER = ROOT / "observability/collector/codex-identity-launcher.sh.example"
CONFIGURE = ROOT / "observability/backends/configure.py"
DASHBOARD = ROOT / "observability/backends/templates/ecosystem-dashboard.json.example"
SCRAPE = ROOT / "observability/backends/templates/ecosystem-prometheus.yml.example"
_PINNED = {item["id"]: item["version"]
           for item in json.loads((ROOT / "observability/backends/pins.json").read_text())["components"]}
_TOOLS = Path.home() / ".local/share/codex-ecosystem/tools"
PROMTOOL = _TOOLS / f"ecosystem-prometheus-{_PINNED['prometheus']}/promtool"
PROMETHEUS = _TOOLS / f"ecosystem-prometheus-{_PINNED['prometheus']}/prometheus"
OTELCOL_VERSION = next(component["version"] for component in
                       json.loads((ROOT / "manifests/stack.json").read_text())["components"]
                       if component["id"] == "opentelemetry-collector-contrib")
OTELCOL = Path(os.environ.get("OTELCOL_TEST_BIN", str(_TOOLS /
               f"otelcol-{OTELCOL_VERSION}/otelcol-contrib")))
if not OTELCOL.exists() and "OTELCOL_TEST_BIN" not in os.environ:
    OTELCOL = Path.home() / ".local/bin/otelcol-contrib"  # native WSL install-plan destination
_OTELCOL_VERSION_OK = False
if OTELCOL.exists():
    try:
        _collector_version = subprocess.run([str(OTELCOL), "--version"], capture_output=True,
                                            text=True, timeout=5)
        _OTELCOL_VERSION_OK = bool(re.search(r"\b" + re.escape(OTELCOL_VERSION) + r"\b",
                                           _collector_version.stdout + _collector_version.stderr))
    except (OSError, subprocess.TimeoutExpired):
        pass
# main before the launcher read ECOSYSTEM_LANE (the negative control's launcher; CI checks out full history).
PRE_LANE_COMMIT = "1f5a791b02a230aced670c88bab3d3d0ebcf401a"

try:
    import yaml
    HAVE_YAML = True
except ImportError:
    HAVE_YAML = False


def statements(config: dict, processor: str, kind: str, context: str) -> list[str]:
    groups = config["processors"][processor][kind]
    return [s for group in groups if group["context"] == context for s in group["statements"]]


def quoted_list(statement: str) -> list[str]:
    return re.findall(r'"([^"]+)"', statement.split("[", 1)[1].split("]", 1)[0])


@unittest.skipUnless(HAVE_YAML, "optional PyYAML structural check")
class CollectorProfileTests(unittest.TestCase):
    def setUp(self):
        self.config = yaml.safe_load(COLLECTOR.read_text())

    def test_metrics_pipeline_groups_by_session_before_the_privacy_allowlist(self):
        processors = self.config["service"]["pipelines"]["metrics"]["processors"]
        self.assertLess(processors.index("groupbyattrs/session"), processors.index("transform/privacy"))
        self.assertLess(processors.index("transform/privacy"), processors.index("delta_to_cumulative"))
        self.assertEqual(self.config["processors"]["groupbyattrs/session"], {"keys": ["session.id"]})
        # The deprecated alias is gone; the logs pipelines keep their own processors.
        self.assertNotIn("deltatocumulative", self.config["processors"])

    def test_session_becomes_the_writer_identity_before_the_resource_allowlist(self):
        resource = statements(self.config, "transform/privacy", "metric_statements", "resource")
        keep = next(i for i, s in enumerate(resource) if s.startswith("keep_keys("))
        writes = [i for i, s in enumerate(resource) if 'set(attributes["service.instance.id"]' in s]
        self.assertEqual(len(writes), 2)
        self.assertTrue(all(i < keep for i in writes))
        self.assertIn('Concat([attributes["service.instance.id"], attributes["session.id"]], "/")', resource[writes[0]])
        self.assertIn('attributes["service.instance.id"] == nil and attributes["session.id"] != nil', resource[writes[1]])
        self.assertNotIn("session.id", quoted_list(resource[keep]))

    def test_dropped_attributes_are_summed_with_the_same_allowlist(self):
        metric = statements(self.config, "transform/privacy", "metric_statements", "metric")
        datapoint = statements(self.config, "transform/privacy", "metric_statements", "datapoint")
        aggregate = next(s for s in metric if s.startswith('aggregate_on_attributes("sum", ['))
        keep = next(s for s in datapoint if s.startswith("keep_keys(attributes,"))
        self.assertEqual(quoted_list(aggregate), quoted_list(keep))
        for kind in ("SUM", "HISTOGRAM", "EXPONENTIAL_HISTOGRAM"):
            self.assertIn(f"metric.type == METRIC_DATA_TYPE_{kind}", aggregate)
        self.assertNotIn("GAUGE", aggregate)

    def test_native_names_are_filtered_before_aggregation_and_keep_lists_match(self):
        groups = self.config["processors"]["transform/privacy"]["metric_statements"]
        metric_index = next(i for i, group in enumerate(groups) if group["context"] == "metric")
        sanitize = "\n".join(s for group in groups[:metric_index]
                             if group["context"] == "datapoint" for s in group["statements"])
        for name in ("server", "skill", "plugin_id", "skill.name", "agent.name",
                     "plugin.name", "mcp_server.name", "mcp_tool.name", "invoke_type"):
            self.assertIn('attributes["' + name + '"]', sanitize)
        metric = statements(self.config, "transform/privacy", "metric_statements", "metric")
        points = statements(self.config, "transform/privacy", "metric_statements", "datapoint")
        aggregates = [quoted_list(s) for s in metric if s.startswith("aggregate_on_attributes")]
        keeps = [quoted_list(s) for s in points if s.startswith("keep_keys(attributes")]
        self.assertEqual(aggregates, keeps)
        self.assertEqual(self.config["exporters"]["prometheus"]["resource_constant_labels"]["included"],
                         ["ecosystem.lane", "ecosystem.task.id"])
        self.assertNotIn("ecosystem.task.id", quoted_list(next(
            s for s in statements(self.config, "transform/privacy", "metric_statements", "resource")
            if s.startswith("keep_keys"))))

    def test_client_templates_send_session_ids_with_cumulative_temporality(self):
        for path in (ROOT / "observability/collector/claude-settings.json.example",
                     ROOT / "adoption/templates/claude.settings.template.json"):
            with self.subTest(path=path.name):
                env = json.loads(path.read_text())["env"]
                self.assertEqual(env["OTEL_METRICS_INCLUDE_SESSION_ID"], "true")
                self.assertEqual(env["OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE"], "cumulative")


def relabel(rules, labels):
    """Apply the replace/drop/labeldrop metric relabel rules the scrape template uses to one label set; None means
    dropped. A reading aid for the structural test only: NativeCollectorTests runs the pinned Prometheus."""
    labels = dict(labels)
    for rule in rules:
        action = rule.get("action", "replace")
        pattern = str(rule.get("regex", "(.*)"))
        if action == "labeldrop":
            labels = {k: v for k, v in labels.items() if not re.fullmatch(pattern, k)}
            continue
        value = rule.get("separator", ";").join(labels.get(name, "") for name in rule.get("source_labels", []))
        match = re.fullmatch(pattern, value)
        if action == "drop" and match:
            return None
        if action == "replace" and match:
            labels[rule["target_label"]] = match.expand(str(rule.get("replacement", "$1")).replace("$", "\\"))
    return labels


@unittest.skipUnless(HAVE_YAML, "optional PyYAML structural check")
class PrometheusScrapeConfigTests(unittest.TestCase):
    def test_collector_job_drops_codex_buckets_except_token_usage(self):
        # One series set per Codex process: its duration-histogram buckets, which no dashboard or rule reads, would
        # multiply storage and push the size-based retention onto every job in this Prometheus.
        doc = yaml.safe_load(SCRAPE.read_text().replace("@CONFIG_ROOT@", "/x"))
        job = next(j for j in doc["scrape_configs"] if j["job_name"] == "collector-native")
        rules = job["metric_relabel_configs"]
        codex = {"job": "codex_exec", "instance": "p1"}
        self.assertIsNone(relabel(rules, {"__name__": "ecosystem_codex_websocket_event_duration_ms_milliseconds_bucket",
                                          "le": "10", **codex}))
        for name in ("ecosystem_codex_websocket_event_duration_ms_milliseconds_sum",
                     "ecosystem_codex_websocket_event_duration_ms_milliseconds_count",
                     "ecosystem_codex_turn_token_usage_bucket", "ecosystem_codex_turn_token_usage_sum",
                     "ecosystem_claude_code_token_usage_tokens_total", "vllm:e2e_request_latency_seconds_bucket"):
            with self.subTest(name=name):
                labels = {"__name__": name, **codex}
                self.assertEqual(relabel(rules, labels), labels)
        for other in doc["scrape_configs"]:
            if other["job_name"] != "collector-native":
                self.assertNotIn("metric_relabel_configs", other)


class DashboardTests(unittest.TestCase):
    def test_token_panels_sum_per_writer_series_and_exclude_unscoped(self):
        panels = {p["id"]: p for p in json.loads(DASHBOARD.read_text())["panels"]}
        self.assertEqual(panels[2]["targets"][0]["expr"],
                         '60 * sum by (type) (rate(ecosystem_claude_code_token_usage_tokens_total{instance!="unscoped"}'
                         '[$__rate_interval]))')
        self.assertEqual(panels[1]["targets"][0]["expr"],
                         '60 * sum by (token_type) (rate(ecosystem_codex_turn_token_usage_sum{instance!="unscoped"}'
                         '[$__rate_interval]))')
        self.assertEqual(panels[25]["targets"][0]["expr"],
                         'sum by (type) (increase(ecosystem_claude_code_token_usage_tokens_total{instance!="unscoped"}'
                         '[$__range]))')
        self.assertEqual(panels[26]["targets"][0]["expr"],
                         'sum by (token_type) (increase(ecosystem_codex_turn_token_usage_sum{instance!="unscoped"}'
                         '[$__range]))')
        integrity = [t["expr"] for t in panels[27]["targets"]]
        self.assertEqual(len(integrity), 3)
        # The most resets of any one series: a resumed session restarts each of its series once, so a sum over
        # series grows with every resume while a shared series shows many resets of its own.
        self.assertTrue(integrity[0].startswith("max(resets("))
        self.assertIn('otelcol_deltatocumulative_datapoints{error!=""}', integrity[1])
        self.assertIn('instance="unscoped"', integrity[2])


@unittest.skipIf(shutil.which("bash") is None, "bash not available")
class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        fake = root / "real-codex"
        fake.write_text('#!/usr/bin/env bash\nprintf "%s|%s\\n" "${OTEL_RESOURCE_ATTRIBUTES:-}" "$*"\nexit 7\n')
        fake.chmod(0o755)
        self.fake = fake
        self.launcher = root / "codex"
        self.launcher.write_text(LAUNCHER.read_text().replace("@CODEX_BIN@", str(fake)))
        self.launcher.chmod(0o755)

    def tearDown(self):
        self.tmp.cleanup()

    def run_launcher(self, attributes=None, *args, shell=None, lane=None, env=None):
        """Returns the attributes and argv the real codex received; stderr is kept in self.stderr. A lane caller's own
        ECOSYSTEM_LANE never reaches these runs: lane sets it, and env adds other variables."""
        environment = {k: v for k, v in os.environ.items() if k not in ("OTEL_RESOURCE_ATTRIBUTES", "ECOSYSTEM_LANE")}
        environment.update(env or {})
        if attributes is not None:
            environment["OTEL_RESOURCE_ATTRIBUTES"] = attributes
        if lane is not None:
            environment["ECOSYSTEM_LANE"] = lane
        command = [shell, str(self.launcher)] if shell else [str(self.launcher)]
        result = subprocess.run([*command, *args], env=environment, capture_output=True, text=True)
        self.assertEqual(result.returncode, 7, result.stderr)
        self.stderr = result.stderr
        attrs, argv = result.stdout.rstrip("\n").split("|", 1)
        return attrs, argv

    def test_each_process_gets_a_fresh_instance_id(self):
        first, argv = self.run_launcher(None, "exec", "--json", "two words")
        second, _ = self.run_launcher(None)
        self.assertEqual(argv, "exec --json two words")
        self.assertRegex(first, r"^service\.instance\.id=[0-9a-f-]{36}$")
        self.assertNotEqual(first, second)

    def test_other_attributes_are_kept_and_an_inherited_identity_gets_a_fresh_suffix(self):
        attrs, _ = self.run_launcher("ecosystem.client.scope=worker")
        self.assertRegex(attrs, r"^service\.instance\.id=[0-9a-f-]{36},ecosystem\.client\.scope=worker$")
        # A codex started from a process that carries an id (a launched codex's shell, a worker, a nested codex)
        # inherits it; concurrent children would share one delta stream. Each still gets its own id, with the
        # inherited one kept as a prefix for correlation (the Collector does the same for <writer>/<session.id>).
        first, _ = self.run_launcher("ecosystem.client.scope=worker,service.instance.id=chosen")
        second, _ = self.run_launcher("ecosystem.client.scope=worker,service.instance.id=chosen")
        self.assertRegex(first, r"^service\.instance\.id=chosen/[0-9a-f-]{36},ecosystem\.client\.scope=worker$")
        self.assertNotEqual(first, second)
        # The OTel SDK trims keys and values; the inherited entry is replaced, not duplicated.
        spaced, _ = self.run_launcher(" service.instance.id = chosen ,a=b,,")
        self.assertRegex(spaced, r"^service\.instance\.id=chosen/[0-9a-f-]{36},a=b$")

    def test_inherited_scratch_environment_and_exact_argv_reach_child(self):
        # POSIX preserves inherited export flags even after assignment. Use a real child process,
        # not the launcher's shell state, and JSON so empty arguments and newlines remain distinct.
        child = Path(self.tmp.name) / "environment-and-argv"
        child.write_text(f"#!{sys.executable}\nimport json, os, sys\n"
                         "print(json.dumps({'env': dict(os.environ), 'argv': sys.argv[1:]}))\n")
        child.chmod(0o755)
        self.launcher.write_text(LAUNCHER.read_text().replace("@CODEX_BIN@", str(child)))
        names = ("id", "inherited", "kept", "rest", "entry", "key", "value", "lane", "listed_lane")
        env = {name: f"sentinel {name}\n'unchanged'" for name in names}
        # Even a caller using the private prefix must not receive the launcher's scratch values.
        env.update({f"__codex_identity_{name}": f"private sentinel {name}" for name in names})
        env["PATH"] = os.environ.get("PATH", "/usr/bin:/bin")
        env["OTEL_RESOURCE_ATTRIBUTES"] = "service.instance.id=parent,a=b\n"
        # A malformed lane adds no attribute, so the inherited trailing newline still ends the value, and the variable
        # itself reaches codex unchanged.
        env["ECOSYSTEM_LANE"] = "Not A Lane\n"
        argv = ["", "two words", "'single' and \"double\"", "line one\nline two", "trailing\n"]
        for shell in ("bash", "sh"):
            with self.subTest(shell=shell):
                result = subprocess.run([shell, str(self.launcher), *argv], env=env,
                                        capture_output=True, text=True, check=True)
                observed = json.loads(result.stdout)
                self.assertEqual(observed["argv"], argv)
                for name, value in env.items():
                    if name != "OTEL_RESOURCE_ATTRIBUTES":
                        self.assertEqual(observed["env"][name], value, name)
                self.assertRegex(observed["env"]["OTEL_RESOURCE_ATTRIBUTES"],
                                 r"^service\.instance\.id=parent/[0-9a-f-]{36},a=b\n$")

    def test_inherited_identity_follows_sdk_first_equals_and_last_duplicate_rules(self):
        attrs, _ = self.run_launcher("service.instance.id=first, broken , service.instance.id = last=part ,a=b=c")
        self.assertRegex(attrs, r"^service\.instance\.id=last=part/[0-9a-f-]{36}, broken ,a=b=c$")
        attrs, _ = self.run_launcher("service.instance.id=first,service.instance.id= ,a=b")
        self.assertRegex(attrs, r"^service\.instance\.id=[0-9a-f-]{36},a=b$")

    @unittest.skipIf(shutil.which("dash") is None, "no strict POSIX shell (dash) to check portability")
    def test_launcher_runs_under_a_strict_posix_shell(self):
        # macOS runs bin/codex with bash 3.2; dash accepts no bash-4 feature either.
        attrs, _ = self.run_launcher("service.instance.id=chosen,a=b", shell="dash")
        self.assertRegex(attrs, r"^service\.instance\.id=chosen/[0-9a-f-]{36},a=b$")
        attrs, _ = self.run_launcher("service.instance.id=chosen", shell="dash", lane="root")
        self.assertRegex(attrs, r"^service\.instance\.id=chosen/[0-9a-f-]{36},ecosystem\.lane=root$")
        for lane in ("Root", "root,service.instance.id=evil", "a" * 33):
            with self.subTest(lane=lane):
                attrs, _ = self.run_launcher(shell="dash", lane=lane)
                self.assertRegex(attrs, r"^service\.instance\.id=[0-9a-f-]{36}$")
                self.assertIn("ECOSYSTEM_LANE ignored", self.stderr)

    def test_a_lane_variable_adds_the_lane_attribute(self):
        attrs, _ = self.run_launcher(lane="root")
        self.assertRegex(attrs, r"^service\.instance\.id=[0-9a-f-]{36},ecosystem\.lane=root$")
        self.assertEqual(self.stderr, "")
        # Inherited entries come first and an inherited identity stays the prefix.
        attrs, _ = self.run_launcher("ecosystem.client.scope=worker,service.instance.id=parent", lane="trading")
        self.assertRegex(attrs, r"^service\.instance\.id=parent/[0-9a-f-]{36},ecosystem\.client\.scope=worker,"
                                r"ecosystem\.lane=trading$")
        # The Collector's pattern, ^[a-z][a-z0-9_-]{0,31}$: up to 32 characters, digits, '_' and '-' after the first.
        for lane in ("a" * 32, "w2_lane-b"):
            with self.subTest(lane=lane):
                attrs, _ = self.run_launcher(lane=lane)
                self.assertRegex(attrs, rf"^service\.instance\.id=[0-9a-f-]{{36}},ecosystem\.lane={lane}$")
        # An empty value names no lane, without a warning; scratch values a caller exports change nothing.
        attrs, _ = self.run_launcher(lane="", env={"__codex_identity_lane": "evil", "__codex_identity_listed_lane": "1"})
        self.assertRegex(attrs, r"^service\.instance\.id=[0-9a-f-]{36}$")
        self.assertEqual(self.stderr, "")
        attrs, _ = self.run_launcher(lane="root", env={"__codex_identity_listed_lane": "1"})
        self.assertRegex(attrs, r"^service\.instance\.id=[0-9a-f-]{36},ecosystem\.lane=root$")

    def test_a_malformed_lane_is_dropped_with_a_warning_and_codex_still_starts(self):
        # The comma case would otherwise add a second service.instance.id, which the SDK's last-duplicate rule keeps.
        for lane in ("Root", "1root", "-root", "_root", "root lane", "a" * 33, "root,service.instance.id=evil",
                     "root=x", "root\n", "rööt"):
            with self.subTest(lane=lane):
                attrs, _ = self.run_launcher(lane=lane)
                self.assertRegex(attrs, r"^service\.instance\.id=[0-9a-f-]{36}$")
                self.assertIn("ECOSYSTEM_LANE ignored", self.stderr)
                self.assertNotIn(lane.strip(), self.stderr)

    def test_an_explicit_lane_entry_wins(self):
        attrs, _ = self.run_launcher("ecosystem.lane=trading", lane="root")
        self.assertRegex(attrs, r"^service\.instance\.id=[0-9a-f-]{36},ecosystem\.lane=trading$")
        self.assertEqual(self.stderr, "")
        # The SDK trims keys (env.rs L45-58 at v0.31.0), so a spaced key is the same attribute; it is kept unchanged.
        attrs, _ = self.run_launcher(" ecosystem.lane = trading ,a=b", lane="root")
        self.assertRegex(attrs, r"^service\.instance\.id=[0-9a-f-]{36}, ecosystem\.lane = trading ,a=b$")
        # The explicit entry wins even when the variable is malformed: it is not read, so no warning.
        attrs, _ = self.run_launcher("ecosystem.lane=trading", lane="Not A Lane")
        self.assertRegex(attrs, r"^service\.instance\.id=[0-9a-f-]{36},ecosystem\.lane=trading$")
        self.assertEqual(self.stderr, "")
        # An entry without '=' is no attribute for the SDK, so the variable still names the lane.
        attrs, _ = self.run_launcher("ecosystem.lane", lane="root")
        self.assertRegex(attrs, r"^service\.instance\.id=[0-9a-f-]{36},ecosystem\.lane,ecosystem\.lane=root$")

    def test_negative_control_the_launcher_before_lane_support_ignores_the_variable(self):
        try:
            old = subprocess.run(["git", "-C", str(ROOT), "show", f"{PRE_LANE_COMMIT}:{LAUNCHER.relative_to(ROOT)}"],
                                 capture_output=True, text=True)
        except OSError:
            self.skipTest("git is not available")
        if old.returncode != 0:
            self.skipTest(f"{PRE_LANE_COMMIT} is not in this clone's history")
        self.assertNotIn("ECOSYSTEM_LANE", old.stdout)
        self.launcher.write_text(old.stdout.replace("@CODEX_BIN@", str(self.fake)))
        attrs, _ = self.run_launcher(lane="root")
        self.assertRegex(attrs, r"^service\.instance\.id=[0-9a-f-]{36}$")


@unittest.skipUnless(PROMTOOL.exists() and HAVE_YAML, "promtool not installed at the documented path, or no PyYAML")
class IntegrityRuleTests(unittest.TestCase):
    """promtool evaluates the rendered native-telemetry-integrity rules over synthetic series."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        subprocess.run([sys.executable, str(CONFIGURE), "--tools-root", str(self.root / "tools"),
                        "--config-root", str(self.root / "config"), "--data-root", str(self.root / "data"),
                        "--unit-root", str(self.root / "unit")], check=True, capture_output=True, text=True)
        self.rules = self.root / "config/ecosystem-prometheus-rules.yml"
        doc = yaml.safe_load(self.rules.read_text())
        group = next(g for g in doc["groups"] if g["name"] == "native-telemetry-integrity")
        self.by_name = {rule["alert"]: rule for rule in group["rules"]}

    def tearDown(self):
        self.tmp.cleanup()

    def firing(self, alert, **labels):
        rule = self.by_name[alert]
        annotations = {k: v.replace("{{ $labels.job }}", labels.get("job", "")) for k, v in rule["annotations"].items()}
        return [{"exp_labels": {**rule["labels"], **labels}, "exp_annotations": annotations}]

    def check(self, alert, cases):
        document = {"rule_files": [str(self.rules)], "evaluation_interval": "1m", "tests": [
            {"interval": "1m", "input_series": [{"series": s, "values": v} for s, v in inputs],
             "alert_rule_test": [{"eval_time": at, "alertname": alert, "exp_alerts": exp} for at, exp in expected]}
            for inputs, expected in cases]}
        path = self.root / f"{alert}.test.yml"
        path.write_text(json.dumps(document))
        result = subprocess.run([str(PROMTOOL), "test", "rules", str(path)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_counter_resets_fire_for_a_shared_series_only(self):
        series = 'ecosystem_claude_code_token_usage_tokens_total{job="claude-code",instance="unscoped",type="output"}'
        resumed = [series.replace("unscoped", "session-a").replace("output", kind)
                   for kind in ("input", "output", "cacheRead", "cacheCreation")]
        resumed.append('ecosystem_claude_code_cost_usage_USD_total{job="claude-code",instance="session-a",'
                       'model="claude-opus-5-5"}')
        self.check("EcosystemTokenCounterResets", [
            ([(series, " ".join(["100", "5"] * 15))], [("20m", self.firing("EcosystemTokenCounterResets", job="claude-code"))]),
            ([(series.replace("unscoped", "session-a"), "0+10x29")], [("20m", [])]),
            # a resumed session restarts its counter once: expected, silent
            ([(series.replace("unscoped", "session-a"), "0+10x9 0+10x19")], [("20m", [])]),
            # ... and it restarts every one of its type and cost series once: still silent
            ([(name, "0+10x9 0+10x19") for name in resumed], [("20m", [])]),
        ])

    def test_dropped_delta_points_fire_only_on_error_series(self):
        base = 'otelcol_deltatocumulative_datapoints{job="collector-health",instance="127.0.0.1:18888"'
        self.check("EcosystemDeltaConversionDropped", [
            ([(base + ',error="delta.ErrOutOfOrder"}', "0+5x29")], [("12m", self.firing("EcosystemDeltaConversionDropped"))]),
            ([(base + "}", "0+50x29"), (base + ',error="delta.ErrOutOfOrder"}', "3x29")], [("20m", [])]),
        ])

    def test_unscoped_writers_fire_after_five_minutes_even_for_a_short_run(self):
        # A short Codex run's series leaves the Collector's Prometheus exporter five minutes after its last export
        # (metric_expiration, default 5m) and the next scrape marks it stale. The rule keeps 15 minutes of samples,
        # longer than its 5-minute delay, so such a run still fires the alert, which resolves 15 minutes later.
        series = 'ecosystem_codex_turn_token_usage_count{job="codex_exec",instance="unscoped",token_type="input"}'
        fire = self.firing("EcosystemUnscopedTokenWriters", job="codex_exec")
        self.check("EcosystemUnscopedTokenWriters", [
            ([(series, "1+0x29")], [("4m", []), ("6m", fire)]),
            # one export, kept 5 minutes by the exporter, then stale
            ([(series, "1+0x6 stale")], [("10m", fire), ("25m", [])]),
            ([(series, "1 stale")], [("10m", fire), ("20m", [])]),
            ([(series.replace("unscoped", "codex-process-a"), "1+0x29")], [("20m", [])]),
        ])


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@unittest.skipUnless(_OTELCOL_VERSION_OK and HAVE_YAML,
                     f"requires PyYAML and otelcol-contrib {OTELCOL_VERSION}; set OTELCOL_TEST_BIN for a scratch install")
class NativeCollectorTests(unittest.TestCase):
    """The committed metrics pipeline on the pinned otelcol-contrib, with synthetic OTLP JSON (no model call)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.otlp, self.exporter, self.telemetry, self.health = (free_port() for _ in range(4))
        config = yaml.safe_load(COLLECTOR.read_text())
        config["receivers"] = {"otlp": {"protocols": {"http": {"endpoint": f"127.0.0.1:{self.otlp}"}}}}
        config["exporters"] = {"prometheus": {**config["exporters"]["prometheus"],
                                              "endpoint": f"127.0.0.1:{self.exporter}"}}
        config["extensions"] = {"health_check": {"endpoint": f"127.0.0.1:{self.health}"}}
        metrics = config["service"]["pipelines"]["metrics"]
        config["processors"] = {k: v for k, v in config["processors"].items() if k in metrics["processors"]}
        config["service"] = {"extensions": ["health_check"],
                             "telemetry": {"logs": {"level": "warn"}, "metrics": {"readers": [{"pull": {"exporter": {
                                 "prometheus": {"host": "127.0.0.1", "port": self.telemetry}}}}]}},
                             "pipelines": {"metrics": {"receivers": ["otlp"], "processors": metrics["processors"],
                                                       "exporters": ["prometheus"]}}}
        path = root / "collector.yaml"
        path.write_text(yaml.safe_dump(config))
        self.log = open(root / "otelcol.log", "w")
        self.process = subprocess.Popen([str(OTELCOL), f"--config={path}"], stdout=self.log, stderr=subprocess.STDOUT)
        deadline = time.time() + 30
        while True:
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{self.health}/", timeout=1).read()
                break
            except OSError:
                if time.time() > deadline or self.process.poll() is not None:
                    self.fail((root / "otelcol.log").read_text())
                time.sleep(0.2)

    def tearDown(self):
        self.process.terminate()
        try:
            self.process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
        self.log.close()
        self.tmp.cleanup()

    def post(self, resource, scope, metrics):
        body = {"resourceMetrics": [{"resource": {"attributes": attrs(resource)},
                                     "scopeMetrics": [{"scope": {"name": scope}, "metrics": metrics}]}]}
        request = urllib.request.Request(f"http://127.0.0.1:{self.otlp}/v1/metrics", data=json.dumps(body).encode(),
                                         headers={"Content-Type": "application/json"}, method="POST")
        urllib.request.urlopen(request, timeout=10).read()

    def scrape(self, port):
        return urllib.request.urlopen(f"http://127.0.0.1:{port}/metrics", timeout=10).read().decode()

    def test_sessions_and_processes_are_separate_writers_and_collapsed_streams_add_up(self):
        start = time.time_ns() - 5_000_000_000
        for step, now in enumerate((time.time_ns(), time.time_ns() + 1_000_000_000), start=1):
            # One Claude process: session-a with two agent.name streams, then (after /clear) session-b.
            points = [claude_point("session-a", agent, 10 * step * weight, start, now)
                      for agent, weight in (("workflow-subagent", 1), ("general-purpose", 2))]
            points.append(claude_point("session-b", "workflow-subagent", 7 * step, start, now))
            self.post({"service.name": "claude-code", "service.version": "2.1.283"}, "com.anthropic.claude_code",
                      [{"name": "claude_code.token.usage", "unit": "tokens", "sum": {
                          "aggregationTemporality": 2, "isMonotonic": True, "dataPoints": points}}])
            # Two Codex processes; per export, two startup phases collapse into one stream after the allowlist.
            for instance, scale in (("codex-proc-1", 1), ("codex-proc-2", 2)):
                interval_start = start if step == 1 else now - 1_000_000_000
                phases = [codex_histogram({"phase": phase, "status": "ok"}, 5.0, interval_start, now)
                          for phase in ("config", "auth")]
                usage = [codex_histogram({"token_type": "input", "tmp_mem_enabled": "false"}, 1000.0 * scale,
                                         interval_start, now)]
                self.post({"service.name": "codex_exec", "service.version": "0.157.1",
                           "service.instance.id": instance}, "codex_otel",
                          [{"name": "codex.startup.phase.duration_ms", "unit": "ms",
                            "histogram": {"aggregationTemporality": 1, "dataPoints": phases}},
                           {"name": "codex.turn.token_usage",
                            "histogram": {"aggregationTemporality": 1, "dataPoints": usage}}])
        time.sleep(2)
        exported = self.scrape(self.exporter)
        claude_points = list(samples(exported, "ecosystem_claude_code_token_usage_tokens_total"))
        self.assertEqual(len(claude_points), 2)
        self.assertTrue(all("agent_name" not in labels for labels, _ in claude_points))
        claude = {}
        for labels, value in claude_points:
            claude[labels["instance"]] = claude.get(labels["instance"], 0.0) + float(value)
        self.assertEqual(claude, {"session-a": 60.0, "session-b": 14.0})
        codex = {labels["instance"]: float(value) for labels, value in samples(
            exported, "ecosystem_codex_turn_token_usage_sum") if labels.get("token_type") == "input"}
        self.assertEqual(codex, {"codex-proc-1": 2000.0, "codex-proc-2": 4000.0})
        phases = {labels["instance"]: float(value) for labels, value in samples(
            exported, "ecosystem_codex_startup_phase_duration_ms_milliseconds_count")}
        self.assertEqual(phases, {"codex-proc-1": 4.0, "codex-proc-2": 4.0})
        telemetry = self.scrape(self.telemetry)
        dropped = [line for line in telemetry.splitlines()
                   if line.startswith("otelcol_deltatocumulative_datapoints") and "error=" in line]
        self.assertEqual(dropped, [])
        # The host apply reads this series back after a Collector restart to confirm the new pipeline runs.
        self.assertTrue(any(line.startswith("otelcol_processor_incoming_items{") and 'processor="groupbyattrs/session"'
                            in line for line in telemetry.splitlines()), telemetry)

    def test_invalid_native_server_names_collapse_before_sum_without_losing_valid_names(self):
        start = time.time_ns() - 5_000_000_000
        now = time.time_ns()
        points = []
        for server, count in (("serena", 7), ("qmd", 11), ("private/path", 2), ("A" * 32, 3)):
            points.append({"attributes": attrs({"server": server}), "startTimeUnixNano": str(start),
                           "timeUnixNano": str(now), "asDouble": float(count)})
        self.post({"service.name": "codex_exec", "service.instance.id": "native-name-test"}, "codex_otel",
                  [{"name": "codex.mcp.call", "sum": {"aggregationTemporality": 1,
                    "isMonotonic": True, "dataPoints": points}}])
        time.sleep(2)
        values = {labels["server"]: float(value) for labels, value in samples(
            self.scrape(self.exporter), "ecosystem_codex_mcp_call_total")}
        self.assertEqual(values, {"serena": 7.0, "qmd": 11.0, "other": 5.0})

    def test_lane_name_becomes_a_label_and_a_malformed_one_is_dropped(self):
        # A lane's launch exports OTEL_RESOURCE_ATTRIBUTES=ecosystem.lane=<lane> (codex-identity-launcher.sh.example).
        start = time.time_ns() - 5_000_000_000
        now = time.time_ns()
        for instance, lane in (("codex-proc-1", "trading"), ("codex-proc-2", "Trading Lane"), ("codex-proc-3", None)):
            resource = {"service.name": "codex_exec", "service.version": "0.160.0", "service.instance.id": instance}
            if lane is not None:
                resource["ecosystem.lane"] = lane
            self.post(resource, "codex_otel", [{"name": "codex.turn.token_usage", "histogram": {
                "aggregationTemporality": 1,
                "dataPoints": [codex_histogram({"token_type": "input"}, 1000.0, start, now)]}}])
        time.sleep(2)
        exported = {labels["instance"]: labels for labels, _ in samples(
            self.scrape(self.exporter), "ecosystem_codex_turn_token_usage_sum")}
        self.assertEqual({instance: labels.get("ecosystem_lane") for instance, labels in exported.items()},
                         {"codex-proc-1": "trading", "codex-proc-2": None, "codex-proc-3": None})
        # Only the lane becomes a label; the other kept resource attributes stay off the series.
        self.assertNotIn("service_version", exported["codex-proc-1"])

    @unittest.skipUnless(PROMETHEUS.exists(), "the pinned Prometheus is not installed at the documented path")
    def test_prometheus_scrape_drops_codex_buckets_and_counts_a_new_series_from_zero(self):
        start = time.time_ns() - 5_000_000_000
        now = time.time_ns()
        self.post({"service.name": "codex_exec", "service.version": "0.157.1", "service.instance.id": "codex-proc-1"},
                  "codex_otel",
                  [{"name": "codex.startup.phase.duration_ms", "unit": "ms", "histogram": {
                      "aggregationTemporality": 1,
                      "dataPoints": [codex_histogram({"phase": "config", "status": "ok"}, 5.0, start, now)]}},
                   {"name": "codex.turn.token_usage", "histogram": {
                       "aggregationTemporality": 1,
                       "dataPoints": [codex_histogram({"token_type": "input"}, 1000.0, start, now)]}}])
        doc = yaml.safe_load(SCRAPE.read_text().replace("@CONFIG_ROOT@", self.tmp.name))
        job = next(j for j in doc["scrape_configs"] if j["job_name"] == "collector-native")
        job["static_configs"] = [{"targets": [f"127.0.0.1:{self.exporter}"]}]
        job["scrape_interval"] = "1s"
        root = Path(self.tmp.name)
        (root / "prometheus.yml").write_text(yaml.safe_dump({"scrape_configs": [job]}))
        port = free_port()
        log = open(root / "prometheus.log", "w")
        prometheus = subprocess.Popen(
            [str(PROMETHEUS), f"--config.file={root / 'prometheus.yml'}", f"--storage.tsdb.path={root / 'tsdb'}",
             f"--web.listen-address=127.0.0.1:{port}",
             "--enable-feature=created-timestamp-zero-ingestion,promql-extended-range-selectors"],
            stdout=log, stderr=subprocess.STDOUT)
        try:
            base = f"http://127.0.0.1:{port}/api/v1/"
            deadline, names, series = time.time() + 30, set(), []
            while time.time() < deadline:
                try:
                    query = urllib.parse.urlencode({"match[]": '{__name__=~"ecosystem_codex_.+"}'})
                    series = json.load(urllib.request.urlopen(base + "series?" + query, timeout=5))["data"]
                    names = {s["__name__"] for s in series}
                    if "ecosystem_codex_turn_token_usage_sum" in names:
                        break
                except OSError:
                    pass
                time.sleep(0.5)
            self.assertIn("ecosystem_codex_turn_token_usage_bucket", names)
            self.assertIn("ecosystem_codex_startup_phase_duration_ms_milliseconds_count", names)
            self.assertIn("ecosystem_codex_startup_phase_duration_ms_milliseconds_sum", names)
            self.assertNotIn("ecosystem_codex_startup_phase_duration_ms_milliseconds_bucket", names)
            self.assertFalse([s for s in series if any(k.startswith("__tmp") for k in s)], series)
            # created-timestamp-zero-ingestion: the first scrape of a new per-process series starts from an
            # injected zero at its start time, so the whole first value counts.
            query = urllib.parse.urlencode({"query": 'sum(increase(ecosystem_codex_turn_token_usage_sum'
                                                     '{instance="codex-proc-1"}[5m] anchored))'})
            result = json.load(urllib.request.urlopen(base + "query?" + query, timeout=5))["data"]["result"]
            self.assertEqual(float(result[0]["value"][1]), 1000.0, result)
        finally:
            prometheus.terminate()
            try:
                prometheus.wait(timeout=20)
            except subprocess.TimeoutExpired:
                prometheus.kill()
                prometheus.wait()
            log.close()


def attrs(mapping):
    return [{"key": k, "value": {"stringValue": v}} for k, v in mapping.items()]


def claude_point(session, agent, value, start, now):
    return {"attributes": attrs({"session.id": session, "agent.name": agent, "type": "output",
                                 "model": "claude-opus-5-5", "query_source": "subagent", "effort": "max",
                                 "user.id": "synthetic"}),
            "startTimeUnixNano": str(start), "timeUnixNano": str(now), "asDouble": float(value)}


def codex_histogram(extra, value, start, now):
    return {"attributes": attrs({"model": "gpt-6-astra", "originator": "codex_exec", **extra}),
            "startTimeUnixNano": str(start), "timeUnixNano": str(now), "count": "1", "sum": value,
            "bucketCounts": ["1", "0"], "explicitBounds": [10000.0]}


def samples(text, name):
    for line in text.splitlines():
        if line.startswith(name + "{"):
            body, value = line[len(name) + 1:].rsplit("} ", 1)
            labels = dict(re.findall(r'(\w+)="([^"]*)"', body))
            yield labels, value.split()[0]


if __name__ == "__main__":
    unittest.main()
