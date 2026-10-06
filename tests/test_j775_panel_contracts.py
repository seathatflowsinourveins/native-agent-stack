"""Local renderer contract fixtures; native Grafana/Loki read-back stays separate."""
import importlib.util
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


if __name__ == '__main__':
    unittest.main()
