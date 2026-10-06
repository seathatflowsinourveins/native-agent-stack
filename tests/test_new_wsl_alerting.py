"""NativeStack2604 alerting in the new-WSL install plan (docs/decisions/2026-10-06-ns2604-alerting.md).

Evidence classes, kept apart:
- the plan files as committed, read structurally;
- scratch copies of the plan broken one way at a time, as negative controls for check_plan.py;
- the plan's renderer (config/observability_config.py) run against a stub promtool: a synthetic control of what it
  publishes, in which order and what it refuses;
- when the plan's pinned binaries are installed (the 2604 tool paths), their native checks of the committed files
  (native_proven); otherwise those tests skip.
Nothing here proves that a journal line reached Prometheus on a host or that a notification reached a phone.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "evidence/artifacts/new-wsl-install-plan-20261002"
CONFIG = PLAN / "config"
MANIFEST = ROOT / "evidence/artifacts/new-wsl-definitive-defaults-20261001/definitive-manifest.json"
TOOLS = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share"))) / "new-wsl-native-stack/tools"
PROMTOOL = TOOLS / "prometheus/prometheus-3.15.0.linux-amd64/promtool"
OTELCOL = shutil.which("otelcol-contrib")
BASE = "ecfa112764c664d35377dd66b8cfcb67e5a94d60"  # the plan before 2026-10-06's alerting change

# Lines in the formats ~/.local/bin/clock-offset-check prints on NativeStack2604 (journald strips the <N> prefix of
# a unit's stdout; a logger line has none). The sample lines are the 2026-10-06 boot's own CRIT and WARN.
CLOCK_LINES = {
    "CRIT 2026-10-06T02:26:00Z ref=162.159.200.123 stratum=4 offset_s=-0.214644 bound_s=0.227062 "
    "root_delay_s=0.017999 root_disp_s=0.003418 ref_age_s=25 leap=Normal trigger=timer why=bound,offset": ("crit", "sample"),
    "WARN 2026-10-06T02:29:00Z ref=162.159.200.123 stratum=4 offset_s=-0.086825 bound_s=0.154011 "
    "root_delay_s=0.017392 root_disp_s=0.058490 ref_age_s=10 leap=Normal trigger=timer why=bound": ("warn", "sample"),
    "OK 2026-10-06T04:26:00Z ref=162.159.200.123 stratum=4 offset_s=-0.000603 bound_s=0.011067 "
    "root_delay_s=0.016845 root_disp_s=0.002042 ref_age_s=49 leap=Normal trigger=timer": ("ok", "sample"),
    "CRIT 2026-10-06T05:00:00Z chronyd_not_observe_only trigger=timer: no chronyd here, or one runs without -x":
        ("crit", "chronyd_not_observe_only"),
    "CRIT 2026-10-06T05:00:00Z chronyc_failed trigger=timer port=3323: 506 Cannot talk to daemon": ("crit", "chronyc_failed"),
    "<3>CRIT 2026-10-06T05:00:00Z chronyc_malformed trigger=timer fields=3": ("crit", "chronyc_malformed"),
    "CRIT 2026-10-06T05:00:00Z chronyc_empty trigger=timer": ("crit", "chronyc_empty"),
    "CRITICAL clock drifted": ("other", "sample"),
}


def ottl_statements(text: str, processor: str) -> list[str]:
    block = re.search(rf"(?m)^  {re.escape(processor)}:\n((?:    .*\n|\s*\n)+)", text).group(1)
    return re.findall(r"(?m)^          - (set\(.*\))$", block)


def classify(statements: list[str], message: str) -> dict:
    """Apply the processor's set(...) [where IsMatch(body["MESSAGE"], "...")] statements in order (RE2 and Python
    agree on these patterns: anchors, classes, \\S, optional groups)."""
    attributes = {}
    for statement in statements:
        match = re.fullmatch(r'set\(attributes\["(\w+)"\], "(\w+)"\)'
                             r'(?: where IsMatch\(body\["MESSAGE"\], "((?:[^"\\]|\\.)*)"\))?', statement)
        if match is None:
            raise AssertionError(f"unexpected statement shape: {statement}")
        key, value, pattern = match.groups()
        if pattern is None or re.search(pattern.encode().decode("unicode_escape"), message):
            attributes[key] = value
    return attributes


class CommittedFilesTests(unittest.TestCase):
    otel = (CONFIG / "otel.yaml").read_text()
    rules = (CONFIG / "prometheus-alerts.yaml").read_text()
    scrape = (CONFIG / "prometheus.yaml").read_text()

    def test_clock_lines_are_classified_by_level_and_a_closed_reason_vocabulary(self):
        statements = ottl_statements(self.otel, "transform/clock_offset_check")
        for message, (level, reason) in CLOCK_LINES.items():
            with self.subTest(message=message[:40]):
                self.assertEqual(classify(statements, message), {"level": level, "reason": reason})
        values = {re.search(r', "(\w+)"\)', s).group(1) for s in statements if s.startswith('set(attributes["reason"]')}
        self.assertEqual(values, {"sample", "chronyd_not_observe_only", "chronyc_failed", "chronyc_malformed",
                                  "chronyc_empty"})

    def test_the_clock_receiver_matches_the_identifier_and_resumes_from_its_cursor(self):
        receiver = re.search(r"(?m)^  journald/clock_offset_check:\n((?:    .*\n)+)", self.otel).group(1)
        self.assertIn("      - SYSLOG_IDENTIFIER: clock-offset-check\n", receiver)
        self.assertNotRegex(receiver, r"(?m)^    (units|identifiers):")
        self.assertIn("    start_at: beginning\n", receiver)
        self.assertIn("    storage: file_storage\n", receiver)

    def test_clock_lines_leave_the_collector_only_as_counts(self):
        pipelines = self.otel.split("\n  pipelines:\n", 1)[1]
        logs = re.search(r"(?m)^    logs/clock_offset_check:\n((?:      .*\n)+)", pipelines).group(1)
        metrics = re.search(r"(?m)^    metrics/clock_offset_check:\n((?:      .*\n)+)", pipelines).group(1)
        self.assertIn("exporters: [count/clock_offset_check]", logs)
        self.assertIn("receivers: [count/clock_offset_check]", metrics)
        self.assertIn("exporters: [prometheus]", metrics)
        # transform/privacy keeps only an allowlist of metric attributes and would drop level and reason.
        self.assertNotIn("transform/privacy", metrics)
        self.assertEqual(pipelines.count("count/clock_offset_check"), 2)

    def test_every_alerted_http_check_url_is_a_collector_target(self):
        targets = set(re.findall(r"(?m)^      - endpoint: (\S+)$", self.otel))
        self.assertEqual(targets, {"http://127.0.0.1:21333/health/status", "http://127.0.0.1:21128/api/health",
                                   "http://127.0.0.1:21080/api/v1/health", "http://127.0.0.1:21434/api/version",
                                   "http://127.0.0.1:21808/api/ping"})
        alerted = set(re.findall(r'http_url="([^"]+)"', self.rules))
        self.assertEqual(alerted, {"http://127.0.0.1:21128/api/health", "http://127.0.0.1:21080/api/v1/health",
                                   "http://127.0.0.1:21434/api/version"})
        self.assertLessEqual(alerted, targets)

    def test_the_observation_services_are_scraped_and_only_two_are_allowlisted(self):
        jobs = dict(re.findall(r'(?m)^  - job_name: (\S+)\n(?:    .*\n)*?      - targets: \["([^"]+)"\]', self.scrape))
        for job, target in (("alertmanager", "127.0.0.1:21093"), ("loki", "127.0.0.1:21300"),
                            ("grafana", "127.0.0.1:21301")):
            self.assertEqual(jobs.get(job), target)
        self.assertEqual(self.scrape.count("action: keep"), 2)

    def test_rules_name_only_unprefixed_metrics_and_one_critical_clock_rule(self):
        self.assertNotRegex(self.rules, r"\becosystem_[a-z_]+\{")
        criticals = re.findall(r"(?m)^      - alert: (\w+)\n(?:        .*\n)*?          severity: critical$", self.rules)
        self.assertIn("EcosystemClockOffsetCritical", criticals)
        self.assertIn('level_reason:clock_offset_check_lines:increase10m{level="crit"} > 0', self.rules)


class CheckerContractTests(unittest.TestCase):
    """check_plan.py over a scratch copy of the plan, one change at a time."""

    def run_check(self, name=None, change=None):
        with tempfile.TemporaryDirectory() as scratch:
            plan_dir = Path(scratch) / "plan"
            shutil.copytree(PLAN, plan_dir, ignore=shutil.ignore_patterns("__pycache__"))
            if change:
                path = plan_dir / "config" / name
                changed = change(path.read_text())
                self.assertNotEqual(changed, path.read_text(), "the mutation must change the file")
                path.write_text(changed)
            result = subprocess.run([sys.executable, "-B", str(PLAN / "check_plan.py"), "--plan-dir", str(plan_dir),
                                     "--manifest", str(MANIFEST)], capture_output=True, text=True, timeout=180)
        return result.returncode, result.stdout + result.stderr

    def test_the_unchanged_copy_passes(self):
        code, out = self.run_check()
        self.assertEqual(code, 0, out)

    def test_a_unit_filter_is_refused(self):
        code, out = self.run_check("otel.yaml", lambda text: text.replace(
            "    matches:\n      - SYSLOG_IDENTIFIER: clock-offset-check\n", "    units:\n      - clock-offset-check\n"))
        self.assertEqual(code, 1, out)
        self.assertIn("the clock receiver must match SYSLOG_IDENTIFIER, not a unit", out)

    def test_a_unit_filter_beside_the_identifier_is_refused(self):
        code, out = self.run_check("otel.yaml", lambda text: text.replace(
            "    priority: info\n    start_at: beginning\n",
            "    priority: info\n    units: [clock-offset-check.service]\n    start_at: beginning\n"))
        self.assertEqual(code, 1, out)
        self.assertIn("the clock receiver must match SYSLOG_IDENTIFIER, not a unit", out)

    def test_an_unread_clock_receiver_is_refused(self):
        code, out = self.run_check("otel.yaml", lambda text: text.replace(
            "      receivers: [journald/clock_offset_check]\n", "      receivers: [otlp]\n"))
        self.assertEqual(code, 1, out)
        self.assertIn("no pipeline reads the clock receiver", out)

    def test_a_clock_rule_below_critical_is_refused(self):
        code, out = self.run_check("prometheus-alerts.yaml", lambda text: re.sub(
            r"(alert: EcosystemClockOffsetCritical\n(?:        .*\n)*?          severity: )critical", r"\1warning", text))
        self.assertEqual(code, 1, out)
        self.assertIn("a critical rule must read the clock-offset-check CRIT count", out)

    def test_a_prefixed_metric_name_is_refused(self):
        code, out = self.run_check("prometheus-alerts.yaml", lambda text: text.replace(
            "'absent(system_filesystem_usage_bytes{", "'absent(ecosystem_system_filesystem_usage_bytes{"))
        self.assertEqual(code, 1, out)
        self.assertIn("rules must not name ecosystem_ metrics", out)


class RendererTests(unittest.TestCase):
    """observability_config.py alerting with a stub promtool that records its calls (synthetic)."""

    STUB = """#!/bin/sh
printf 'call|%s|%s\\n' "$(basename "$PWD")" "$*" >> "$STUB_LOG"
if [ "$1 $2" = "test rules" ]; then
  sha256sum prometheus-alerts.yaml prometheus-alerts.test.yaml >> "$STUB_LOG"
  exit "${STUB_TEST_EXIT:-0}"
fi
exit 0
"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.config = self.root / "config"
        self.config.mkdir()
        stub = self.root / "tools/prometheus/prometheus-3.15.0.linux-amd64/promtool"
        stub.parent.mkdir(parents=True)
        stub.write_text(self.STUB)
        stub.chmod(0o700)
        self.log = self.root / "promtool.log"

    def render(self, **extra):
        env = {"PATH": os.environ["PATH"], "HOME": str(self.root), "XDG_CONFIG_HOME": str(self.root / "xdg"),
               "NS2604_OBSERVABILITY_DATA": str(self.root / "data"), "tool_root": str(self.root / "tools"),
               "STUB_LOG": str(self.log), **extra}
        return subprocess.run([sys.executable, str(CONFIG / "observability_config.py"), "alerting",
                               "--config-root", str(self.config), "--source-root", str(CONFIG)],
                              env=env, capture_output=True, text=True, timeout=120)

    @staticmethod
    def digest(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def test_the_new_pair_is_unit_tested_before_it_and_the_scrape_config_are_published(self):
        result = self.render()
        self.assertEqual(result.returncode, 0, result.stderr)  # no destination files: needs_user after publishing
        ledger = json.loads((self.config / ".g4-source-digests.json").read_text())
        for name in ("prometheus-alerts.yaml", "prometheus-alerts.test.yaml", "prometheus.yaml"):
            self.assertEqual((self.config / name).read_bytes(), (CONFIG / name).read_bytes())
            self.assertEqual(ledger[name], self.digest(CONFIG / name))
        calls = [line.split("|") for line in self.log.read_text().splitlines() if line.startswith("call|")]
        self.assertEqual([call[2].split(" ")[:2] for call in calls],
                         [["test", "rules"], ["check", "rules"], ["check", "config"]])
        self.assertTrue(calls[0][1].startswith(".g4-validate-"))  # the scratch directory, not the live root
        tested = dict(reversed(line.split("  ")) for line in self.log.read_text().splitlines() if "  " in line)
        self.assertEqual(tested["prometheus-alerts.yaml"], self.digest(CONFIG / "prometheus-alerts.yaml"))
        self.assertEqual(tested["prometheus-alerts.test.yaml"], self.digest(CONFIG / "prometheus-alerts.test.yaml"))
        self.assertEqual(sorted(p.name for p in self.config.iterdir() if p.name.startswith(".g4-validate")), [])

    def test_a_plan_owned_older_pair_is_replaced(self):
        for name in ("prometheus-alerts.yaml", "prometheus-alerts.test.yaml"):
            (self.config / name).write_text(f"# an earlier plan render of {name}\n")
        (self.config / ".g4-source-digests.json").write_text(json.dumps(
            {name: self.digest(self.config / name) for name in ("prometheus-alerts.yaml", "prometheus-alerts.test.yaml")}))
        result = self.render()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.config / "prometheus-alerts.yaml").read_bytes(), (CONFIG / "prometheus-alerts.yaml").read_bytes())

    def test_an_operator_edit_is_refused_and_kept(self):
        edited = "# operator rules\ngroups: []\n"
        (self.config / "prometheus-alerts.yaml").write_text(edited)
        result = self.render()
        self.assertEqual(result.returncode, 1)
        self.assertIn("retained operator configuration for prometheus-alerts.yaml", result.stderr)
        self.assertEqual((self.config / "prometheus-alerts.yaml").read_text(), edited)
        self.assertFalse((self.config / "prometheus.yaml").exists())

    def test_failing_unit_tests_leave_every_live_file_untouched(self):
        for name in ("prometheus-alerts.yaml", "prometheus-alerts.test.yaml", "prometheus.yaml"):
            (self.config / name).write_text(f"# live {name}\n")
        before = {p.name: p.read_bytes() for p in self.config.iterdir()}
        result = self.render(STUB_TEST_EXIT="1")
        self.assertEqual(result.returncode, 1)
        self.assertIn("refused prometheus-alerts.test.yaml; originals retained", result.stderr)
        self.assertEqual({p.name: p.read_bytes() for p in self.config.iterdir()}, before)

    def test_a_missing_tool_root_is_refused_before_any_write(self):
        result = self.render(tool_root="")
        self.assertEqual(result.returncode, 1)
        self.assertIn("alerting requires tool_root", result.stderr)
        self.assertEqual(list(self.config.iterdir()), [])

    def test_the_pristine_digests_are_the_pair_the_plan_shipped_before_this_change(self):
        source = (CONFIG / "observability_config.py").read_text()
        shipped = {}
        for name in ("prometheus-alerts.yaml", "prometheus-alerts.test.yaml"):
            shipped[name] = re.search(rf'"{re.escape(name)}": "([0-9a-f]{{64}})"', source).group(1)
        present = subprocess.run(["git", "-C", str(ROOT), "cat-file", "-e", BASE + "^{commit}"], capture_output=True)
        if present.returncode:
            self.skipTest(f"{BASE[:9]} is not in this clone")
        for name, digest in shipped.items():
            old = subprocess.run(["git", "-C", str(ROOT), "show", f"{BASE}:{PLAN.relative_to(ROOT).as_posix()}/config/{name}"],
                                 capture_output=True, check=True).stdout
            self.assertEqual(hashlib.sha256(old).hexdigest(), digest)


@unittest.skipUnless(PROMTOOL.exists(), "the plan's promtool is not installed at its 2604 tool path")
class NativePromtoolTests(unittest.TestCase):
    """native_proven when it runs: the pinned promtool 3.15.0 checks the committed files and runs their unit tests."""

    def test_rules_scrape_config_and_unit_tests(self):
        with tempfile.TemporaryDirectory() as scratch:
            for name in ("prometheus.yaml", "prometheus-alerts.yaml", "prometheus-alerts.test.yaml",
                         "acceptance-targets.json"):
                shutil.copy2(CONFIG / name, Path(scratch) / name)
            for command in (["check", "rules", "prometheus-alerts.yaml"], ["check", "config", "prometheus.yaml"],
                            ["test", "rules", "prometheus-alerts.test.yaml"]):
                with self.subTest(command=" ".join(command[:2])):
                    result = subprocess.run([str(PROMTOOL), *command], cwd=scratch, capture_output=True, text=True,
                                            timeout=600)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertIn("SUCCESS", result.stdout + result.stderr)


@unittest.skipUnless(OTELCOL, "otelcol-contrib is not on PATH")
class NativeCollectorTests(unittest.TestCase):
    """native_proven when it runs: the installed Collector validates the committed template (no component starts)."""

    def test_the_collector_template_validates(self):
        version = subprocess.run([OTELCOL, "--version"], capture_output=True, text=True).stdout
        if "0.162.0" not in version:
            self.skipTest(f"installed Collector is not the plan's v0.162.0: {version.strip()}")
        with tempfile.TemporaryDirectory() as scratch:
            env = {**os.environ, "NS2604_OBSERVABILITY_DATA": scratch}
            result = subprocess.run([OTELCOL, "validate", f"--config={CONFIG / 'otel.yaml'}"], env=env,
                                    capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
