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
OTELCOL = _TOOLS / "otelcol-0.161.0/otelcol-contrib"  # observability/collector/README.md pins 0.161.0

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
        self.launcher = root / "codex"
        self.launcher.write_text(LAUNCHER.read_text().replace("@CODEX_BIN@", str(fake)))
        self.launcher.chmod(0o755)

    def tearDown(self):
        self.tmp.cleanup()

    def run_launcher(self, attributes=None, *args, shell=None):
        env = {k: v for k, v in os.environ.items() if k != "OTEL_RESOURCE_ATTRIBUTES"}
        if attributes is not None:
            env["OTEL_RESOURCE_ATTRIBUTES"] = attributes
        command = [shell, str(self.launcher)] if shell else [str(self.launcher)]
        result = subprocess.run([*command, *args], env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 7, result.stderr)
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

    @unittest.skipIf(shutil.which("dash") is None, "no strict POSIX shell (dash) to check portability")
    def test_launcher_runs_under_a_strict_posix_shell(self):
        # macOS runs bin/codex with bash 3.2; dash accepts no bash-4 feature either.
        attrs, _ = self.run_launcher("service.instance.id=chosen,a=b", shell="dash")
        self.assertRegex(attrs, r"^service\.instance\.id=chosen/[0-9a-f-]{36},a=b$")


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


@unittest.skipUnless(OTELCOL.exists() and HAVE_YAML, "otelcol-contrib 0.161.0 not installed at the documented path")
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
        claude = {labels["instance"]: float(value) for labels, value in samples(
            exported, "ecosystem_claude_code_token_usage_tokens_total")}
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
