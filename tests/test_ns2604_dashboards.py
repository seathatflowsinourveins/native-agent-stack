"""Local integration checks for NativeStack2604's ported dashboards and research emitter (no host, no network)."""
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "evidence/artifacts/new-wsl-install-plan-20261002"
SPEC = importlib.util.spec_from_file_location("ns2604_dashboards", ROOT / "observability/ns2604_dashboards.py")
G = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(G)


def exprs(board):
    return [t["expr"] for panel in board["panels"] for t in panel.get("targets", []) if "expr" in t]


class Ns2604DashboardTests(unittest.TestCase):
    def test_committed_plan_dashboards_match_a_fresh_render(self):
        result = subprocess.run([sys.executable, str(ROOT / "observability/ns2604_dashboards.py"), "--check"],
                                capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)

    def test_retarget_changes_only_datasources_and_prometheus_metric_names(self):
        board = {"panels": [
            {"id": 1, "datasource": {"type": "prometheus", "uid": "ecosystem-prometheus"}, "targets": [
                {"refId": "A", "expr": 'sum by (ecosystem_lane) (rate(ecosystem_codex_tool_call_total[5m]))'},
                {"refId": "B", "expr": '{__name__=~"ecosystem_a_total|ecosystem_b_total"}'}]},
            {"id": 2, "datasource": {"type": "loki", "uid": "ecosystem-loki"}, "targets": [
                {"refId": "A", "expr": '{service_name="ecosystem_logs"} | json'}]},
            {"id": 3, "type": "row", "panels": [
                {"id": 4, "targets": [{"refId": "A", "datasource": {"uid": "ecosystem-prometheus"},
                                       "expr": "ecosystem_system_memory_usage_bytes"}]}]},
        ]}
        G.retarget(board)
        self.assertEqual(["sum by (ecosystem_lane) (rate(codex_tool_call_total[5m]))", '{__name__=~"a_total|b_total"}',
                          '{service_name="ecosystem_logs"} | json'], exprs(board))
        self.assertEqual("system_memory_usage_bytes", board["panels"][2]["panels"][0]["targets"][0]["expr"])
        self.assertEqual(["ns2604-prometheus", "ns2604-loki"], [p["datasource"]["uid"] for p in board["panels"][:2]])
        self.assertEqual("ns2604-prometheus", board["panels"][2]["panels"][0]["targets"][0]["datasource"]["uid"])

    def test_plan_dashboards_target_this_host_only(self):
        for name, uid in (("grafana-research-grand.json", "research-grand"),
                          ("grafana-ecosystem-native.json", "ecosystem-native"),
                          ("grafana-native-foundation-data.json", "native-foundation-data")):
            with self.subTest(name=name):
                text = (PLAN / "config" / name).read_text()
                board = json.loads(text)
                self.assertEqual(uid, board["uid"])
                self.assertFalse(board["editable"])
                self.assertEqual({"ns2604-loki", "ns2604-prometheus"},
                                 set(re.findall(r'"uid": "(ns2604-[a-z]+)"', text)))
                self.assertNotRegex(text, r'ecosystem-(?:loki|prometheus)|(?<![\w:])ecosystem_(?!lane\b)|:1[0-9]{4}\b')
        research = json.loads((PLAN / "config/grafana-research-grand.json").read_text())
        table = next(p for p in research["panels"] if p["id"] == 15)
        self.assertEqual("Native workflow history · " + ", ".join(G.DAGS), table["title"])
        unit = (PLAN / "config/ns2604-research-progress.service").read_text()
        self.assertEqual(list(G.DAGS), re.findall(r"--dagu-dag (\S+)", unit))

    def render(self, root):
        env = dict(os.environ, NS2604_OBSERVABILITY_DATA=str(root / "data"), XDG_CONFIG_HOME=str(root / "xdg"))
        def run(*args):
            return subprocess.run([sys.executable, str(PLAN / "config/observability_config.py"), *args,
                                   "--config-root", str(root / "config")], capture_output=True, text=True, env=env)
        return run

    def test_grafana_action_publishes_dashboards_units_and_news_setting(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            run = self.render(root)
            result = run("grafana", "--source-root", str(PLAN / "config"))
            self.assertEqual(0, result.returncode, result.stderr)
            config = root / "config"
            for uid in ("research-grand", "ecosystem-native", "native-foundation-data"):
                self.assertEqual(uid, json.loads((config / f"ecosystem-grafana-dashboards/{uid}.json").read_text())["uid"])
            providers = (config / "grafana-provisioning/dashboards/native-stack.yaml").read_text()
            self.assertIn(f'path: {json.dumps(str(config / "ecosystem-grafana-dashboards"))}', providers)
            self.assertIn(f'path: {json.dumps(str(config / "grafana-dashboards"))}', providers)
            self.assertRegex((config / "grafana.ini").read_text(), r"(?m)^\[news\]\nnews_feed_enabled = false$")
            service = (config / "systemd/ns2604-research-progress.service").read_text()
            self.assertIn(f"ExecStart=/usr/bin/python3 {ROOT}/observability/grand-dashboard/progress.py --repo {ROOT} "
                          f"--cache {root / 'data'}/grand-dashboard/progress-cache.json "
                          "--loki-url http://127.0.0.1:21300/loki/api/v1/push", service)
            self.assertNotRegex(service, r"@[A-Z_]+@")
            ledger = json.loads((config / ".g4-source-digests.json").read_text())
            self.assertIn("systemd/ns2604-research-progress.timer", ledger)
            # grafana-check also requires the units where install.sh puts them.
            self.assertEqual(1, run("grafana-check").returncode)
            units = root / "xdg/systemd/user"
            units.mkdir(parents=True)
            for name in ("ns2604-research-progress.service", "ns2604-research-progress.timer"):
                shutil.copy(config / "systemd" / name, units / name)
            result = run("grafana-check")
            self.assertEqual(0, result.returncode, result.stderr)
            # A dashboard that still points at the workstation fails the check.
            stale = config / "ecosystem-grafana-dashboards/ecosystem-native.json"
            stale.write_text(stale.read_text().replace("ns2604-prometheus", "ecosystem-prometheus"))
            self.assertEqual(1, run("grafana-check").returncode)

    def test_grafana_action_refuses_a_source_outside_a_checkout(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source = root / "source"
            shutil.copytree(PLAN / "config", source)
            result = self.render(root)("grafana", "--source-root", str(source))
            self.assertEqual(1, result.returncode)
            self.assertIn("--repo-root", result.stderr)

    def test_emitter_unit_arguments_run_against_a_synthetic_dagu(self):
        # Synthetic fixture: the rendered ExecStart, with %h at a temporary home and without --cache (no push).
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self.assertEqual(0, self.render(root)("grafana", "--source-root", str(PLAN / "config")).returncode)
            line = next(l for l in (root / "config/systemd/ns2604-research-progress.service").read_text().splitlines()
                        if l.startswith("ExecStart="))
            home = root / "home"
            (home / ".local/bin").mkdir(parents=True)
            (home / ".dagu").mkdir()
            dagu = home / ".local/bin/dagu"
            dagu.write_text('#!/usr/bin/python3\nimport sys,json\nprint(json.dumps([dict(name=sys.argv[2], status="succeeded", '
                            'startedAt="2026-10-05T07:30:00Z", finishedAt="2026-10-05T07:31:00Z")]))\n')
            dagu.chmod(0o700)
            argv = shlex.split(line.removeprefix("ExecStart=").replace("%h", str(home)))
            cache = argv.index("--cache")
            del argv[cache:cache + 2]
            argv[0] = sys.executable
            result = subprocess.run(argv, capture_output=True, text=True)
            self.assertEqual(0, result.returncode, result.stderr)
            workflow = [r for r in json.loads(result.stdout) if r["record_kind"] == "workflow"]
            self.assertEqual([f"workflow/{dag}/history" for dag in G.DAGS],
                             [r["entity_id"] for r in workflow if r["entity_id"].endswith("/history")])
            self.assertTrue(all(r["state"] in ("observed / bounded local history", "succeeded") for r in workflow))


if __name__ == "__main__":
    unittest.main()
