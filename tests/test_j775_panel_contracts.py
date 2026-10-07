"""Local renderer contract fixtures; native Grafana/Loki read-back stays separate."""
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def module(relative, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


class J775PanelContracts(unittest.TestCase):
    def test_token_qualification_follows_prometheus_metric_and_is_idempotent(self):
        renderer = module('observability/ns2604_dashboards.py', 'j775_ns2604')
        board = {'panels': [
            {'title': 'Selected-range Codex tokens', 'datasource': {'type': 'prometheus', 'uid': 'ecosystem-prometheus'},
             'targets': [{'expr': 'sum(increase(ecosystem_codex_turn_token_usage_sum[1h]))'}]},
            {'title': 'Nested row', 'panels': [
                {'title': 'Codex per-minute tokens', 'datasource': {'type': 'prometheus', 'uid': 'ns2604-prometheus'},
                 'targets': [{'expr': 'rate(codex_turn_token_usage_sum[1m])'}]}]},
            {'title': 'Native request records', 'datasource': {'type': 'loki', 'uid': 'ns2604-loki'},
             'targets': [{'expr': 'codex_turn_token_usage_sum'}]},
        ]}
        renderer.retarget(board)
        selected, nested, records = board['panels']
        for panel in (selected, nested['panels'][0]):
            self.assertIn('lower bound', panel['title'].lower())
            self.assertIn('lower bound', panel['description'].lower())
            self.assertIn('newly born single-turn', panel['description'])
        before = selected['title']
        renderer.retarget(board)
        self.assertEqual(before, selected['title'])
        self.assertEqual('Native request records', records['title'])
        self.assertNotIn('description', records)

    def test_native_status_rows_sort_before_null_preserving_last(self):
        renderer = module('observability/lanes_dashboard.py', 'j775_lanes')
        status = next(p for p in renderer.dashboard()['panels'] if p['title'].startswith('Latest recorded hcom'))
        transformations = status['transformations']
        self.assertEqual(['extractFields', 'sortBy', 'groupBy'], [t['id'] for t in transformations])
        self.assertEqual([{'field': 'Time', 'desc': False}], transformations[1]['options']['sort'])
        fields = transformations[2]['options']['fields']
        for name in ('status', 'status_age_seconds', 'unread_count', 'observed_unix'):
            self.assertEqual(['last'], fields[name]['aggregations'])
        self.assertEqual('UNKNOWN', status['fieldConfig']['defaults']['noValue'])

    def test_rtk_zero_uses_only_positive_classified_denominator_identities(self):
        renderer = module('observability/lanes_dashboard.py', 'j775_lanes_rtk')
        panel = next(p for p in renderer.dashboard()['panels'] if p['title'].startswith('Per-session shells'))
        expression = next(t['expr'] for t in panel['targets'] if t['legendFormat'].startswith('Codex RTK prefix %'))
        self.assertIn('or on (identity) (0 *', expression)
        self.assertIn('shell_rtk=~"true|false"', expression)
        self.assertIn('> 0', expression)
        self.assertNotIn('vector(0)', expression)

    def test_superseded_prometheus_drop_in_has_no_active_exec_start(self):
        example = (ROOT / 'observability/collector/ns2604-prometheus-start-timestamps.conf.example').read_text()
        first_line = example.splitlines()[0]
        self.assertIn('SUPERSEDED on 2026-10-07', first_line)
        self.assertIn('DO NOT APPLY', first_line)
        self.assertNotRegex(example, r'(?m)^\s*ExecStart\s*=')
        self.assertIn('\n# ExecStart=\n', example)
        self.assertIn('# ExecStart=%h/.local/bin/prometheus ', example)

    def test_rendered_prometheus_unit_retains_both_required_features(self):
        plan = json.loads((ROOT / 'evidence/artifacts/new-wsl-install-plan-20261002/install-plan.json').read_text())
        rows = [row for row in plan['owners'] if row['slot'] == 'prometheus']
        self.assertEqual(1, len(rows))
        service = rows[0]['service']
        for feature in ('created-timestamp-zero-ingestion', 'promql-extended-range-selectors'):
            with self.subTest(feature=feature):
                self.assertIn(feature, service['enable_features'])
        self.assertEqual('$config_root/ns2604-prometheus.service', service['rendered_unit'])
        proposal = service['startup_proposal']
        self.assertIn('Superseded on 2026-10-07', proposal['status'])
        self.assertTrue(proposal['apply_gate'].startswith('none;'))
        self.assertIn('rendered ns2604-prometheus.service', proposal['readback_gate'])


if __name__ == '__main__':
    unittest.main()
