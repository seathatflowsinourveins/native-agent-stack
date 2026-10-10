"""Published Fleet tracking conserves rows and preserves source measurement scope."""
import base64
import copy
from html.parser import HTMLParser
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from tests import test_local_pages_fleet_tracking as tracking_contract


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('fleet_tracking_view_tests', ROOT / 'tools/local-pages/fleet_view.py')
VIEW = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VIEW)


class FleetDOM(HTMLParser):
    def __init__(self, markup):
        super().__init__(convert_charrefs=True)
        self.rows, self.links, self.tags, self.attrs, self.tokens, self.rates = [], [], [], [], [], []
        self.measurements = []
        self._row = None
        self._measurement = None
        self.feed(markup)
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.tags.append(tag)
        self.attrs.extend(attrs.values())
        if tag == 'a':
            self.links.append(attrs.get('href'))
        if attrs.get('data-tracking-metric') == 'token':
            self.tokens.append(attrs.get('data-token-type'))
        if 'data-invocation-family' in attrs:
            self.rates.append(attrs['data-invocation-family'])
            self._measurement = {'attrs': attrs, 'row': dict(self._row['attrs']) if self._row else {}, 'text': ''}
        if tag == 'tr' and any(key in attrs for key in ('data-hcom-name', 'data-tracking-lane', 'data-tracking-service', 'data-tracking-query')):
            self._row = {'attrs': attrs, 'text': ''}
    def handle_data(self, value):
        if self._row is not None:
            self._row['text'] += value + ' '
        if self._measurement is not None:
            self._measurement['text'] += value + ' '
    def handle_endtag(self, tag):
        if tag == 'li' and self._measurement is not None:
            self.measurements.append(self._measurement)
            self._measurement = None
        if tag == 'tr' and self._row is not None:
            self.rows.append(self._row)
            self._row = None
    def group(self, field):
        return [row for row in self.rows if field in row['attrs']]


def measurement(value, *, status='reported', unit='tokens/s', token_type=None, reason=None):
    item = {'value': value, 'status': status, 'unit': unit, 'reason': reason,
            'source_sample_utc': '2026-10-09T20:00:00Z', 'evaluated_utc': '2026-10-09T20:01:00Z',
            'window_seconds': 300}
    if token_type is not None:
        item['token_type'] = token_type
    return item


def fixture():
    agents = [{'name': f'agent-{index}', 'base_name': f'base-{index}', 'tool': 'codex', 'tag': f'lane-{index}',
               'status': 'listening', 'status_age_seconds': index, 'created_at': '2026-10-09T19:00:00Z'} for index in range(19)]
    for index in range(6):
        agents[index]['tag'] = f'trading-fixture-{index}'
    return {'fleet_source': 'fixture producer', 'at': '2026-10-09T20:00:00Z',
            'lanes_live': [], 'lanes_parked': [], 'claude_sessions': [], 'tiers': {},
            'tracking': {'schema': 'fleet-tracking/1', 'observed_utc': '2026-10-09T20:01:00Z',
                         'hcom': {'status': 'reported', 'agents': agents, 'count': 19, 'read_utc': '2026-10-09T20:00:30Z'},
                         'lanes': [{'lane': 'historic-source-lane', 'clients': [
                             {'client': 'codex', 'tokens': [measurement(value, status='lower bound', token_type=kind) for value, kind in [(0, 'input'), (0.00000004, 'cached_input'), (0.2, 'cache_write_input'), (0.3, 'output'), (0.1, 'reasoning_output'), (0.6, 'total')]],
                              'invocations': {**measurement(0.00000004, status='lower bound', unit='calls/s'), 'scope': 'native MCP calls'}},
                             {'client': 'claude', 'tokens': [measurement(None, status='UNKNOWN', token_type='input', reason='Client series is absent.')],
                              'invocations': measurement(None, status='UNKNOWN', unit='calls/s', reason='Native invocation metric unavailable.')}],
                                    'source_refs': []},
                                   {'lane': 'source-lane-without-client', 'clients': []}],
                         'services': [{'id': 'vllm-embed', 'title': 'Local embeddings', 'observations': [{**measurement(1, unit='scrape indicator'), 'metric': 'up', 'scope': 'Prometheus scrape observation'}]},
                                      {'id': 'hindsight', 'title': 'Hindsight', 'observations': [{**measurement(0, unit='scrape indicator'), 'metric': 'up', 'scope': 'Prometheus scrape observation'}]},
                                      {'id': 'ai-memory', 'title': 'AI memory', 'observations': [{**measurement(None, status='UNKNOWN', unit='scrape indicator', reason='Service series is absent.'), 'metric': 'up', 'scope': 'Prometheus scrape observation'}]}],
                         'grafana': {'base_url': 'http://127.0.0.1:21301', 'status': 'reported', 'read_utc': '2026-10-09T20:00:30Z',
                                     'links': [{'title': 'Agent activity', 'uid': 'fixture-agent', 'url': 'http://127.0.0.1:21301/d/fixture-agent/agent-activity?var-lane=historic-source-lane'}]},
                         'limitations': ['Scrape time does not establish invocation recency or complete writer coverage.']}}


def collected_fixture(*, api=0.2, tools=0.3):
    """Actual collector output with both native transports supplied synthetically."""
    native = tracking_contract.FleetTrackingTests('test_stopped_sender_identity_cannot_disable_the_product_roster')
    lane, now = 'historic-source-lane', tracking_contract.NOW
    def fetch(query, **kwargs):
        if 'service_name="claude-code"' in query:
            value = api if 'event_name="api_request"' in query else tools if 'event_name="tool_result"' in query else None
            return tracking_contract.vector([] if value is None else [tracking_contract.sample({'ecosystem_lane': lane}, value)])
        if 'codex_turn_token_usage_sum' in query:
            labels, value = {'ecosystem_lane': lane, 'token_type': 'input'}, 0.25
        elif 'claude_code_token_usage_tokens_total' in query:
            labels, value = {'ecosystem_lane': lane, 'type': 'input'}, 0.5
        elif any(counter in query for counter in ('codex_api_request_total', 'codex_tool_call_total', 'codex_mcp_call_total')):
            labels, value = {'ecosystem_lane': lane}, 0.1
        else:
            return tracking_contract.vector([])
        return tracking_contract.vector([tracking_contract.sample(labels, now - 30 if 'timestamp(' in query else value)])
    data = fixture()
    data['tracking'] = tracking_contract.fleet.collect_tracking(
        run=native.run_hcom(()), fetch=fetch, probe=lambda *args, **kwargs: None, now=now)
    return data


class FleetTrackingViewTests(unittest.TestCase):
    def test_every_roster_and_telemetry_row_is_retained_without_cross_joining(self):
        data = fixture()
        original = copy.deepcopy(data)
        dom = FleetDOM(VIEW.render(data))
        roster = dom.group('data-hcom-name')
        self.assertEqual(len(roster), 19)
        self.assertEqual({row['attrs']['data-hcom-name'] for row in roster}, {row['name'] for row in data['tracking']['hcom']['agents']})
        for index in range(6):
            self.assertTrue(any(f'trading-fixture-{index}' in row['text'] for row in roster))
        telemetry = dom.group('data-tracking-lane')
        self.assertEqual(len(telemetry), 3)
        self.assertEqual([row['attrs']['data-tracking-client'] for row in telemetry[:2]], ['codex', 'claude'])
        self.assertTrue(all('historic-source-lane' not in row['text'] for row in roster))
        self.assertEqual(dom.tokens, ['input', 'cached_input', 'cache_write_input', 'output', 'reasoning_output', 'total', 'input'])
        self.assertEqual({row['attrs']['data-tracking-service'] for row in dom.group('data-tracking-service')}, {'vllm-embed', 'hindsight', 'ai-memory'})
        self.assertEqual(data, original)

    def test_zero_unknown_tiny_rates_and_measurement_dates_remain_distinct(self):
        dom = FleetDOM(VIEW.render(fixture()))
        codex = next(row for row in dom.group('data-tracking-lane') if row['attrs']['data-tracking-client'] == 'codex')
        self.assertIn('UNKNOWN tokens/s', codex['text'])
        self.assertNotIn('0 tokens/s', codex['text'])
        self.assertIn('4e-08 tokens/s', codex['text'])
        self.assertIn('4e-08 calls/s', codex['text'])
        self.assertIn('lower bound', codex['text'])
        self.assertIn('2026-10-09T20:00:00Z', codex['text'])
        self.assertIn('2026-10-09T20:01:00Z', codex['text'])
        self.assertIn('Window: 300 seconds', codex['text'])
        unknown = next(row for row in dom.group('data-tracking-lane') if row['attrs']['data-tracking-client'] == 'claude')
        self.assertIn('UNKNOWN tokens/s', unknown['text'])
        self.assertIn('Native invocation metric unavailable.', unknown['text'])
        self.assertNotIn('0 calls/s', unknown['text'])
        self.assertIn('0', dom.group('data-hcom-name')[0]['text'])

    def test_invocation_families_keep_qualification_scope_and_unknowns_separate(self):
        data = fixture()
        client = data['tracking']['lanes'][0]['clients'][0]
        families = [('api_requests', 'API requests', 0.2, 'API attempts include retries'),
                    ('tool_calls', 'Tool calls', 0.3, 'Native tool-call counter, not result records'),
                    ('mcp_calls', 'MCP calls', 0.00000004, 'Native MCP calls'),
                    ('skill_invocations', 'Skill invocations', None, 'Numeric source is unqualified'),
                    ('agent_invocations', 'Agent invocations', None, 'Numeric source is unqualified')]
        client['rates'] = [{**measurement(value, status='lower bound' if value is not None else 'UNKNOWN', unit='calls/s'),
                            'family': family, 'label': label, 'scope': scope} for family, label, value, scope in families]
        dom = FleetDOM(VIEW.render(data))
        codex = next(row for row in dom.group('data-tracking-lane') if row['attrs']['data-tracking-client'] == 'codex')
        self.assertEqual(dom.rates[:5], [item[0] for item in families])
        for _, label, _, scope in families:
            self.assertIn(label, codex['text'])
            self.assertIn(scope, codex['text'])
        self.assertEqual(codex['text'].count('4e-08 calls/s'), 1)
        self.assertIn('UNKNOWN calls/s', codex['text'])
        self.assertIn('unreported', codex['text'])
        self.assertIn('lower bound', codex['text'])
        self.assertIn('Source sample:', codex['text'])
        client['rates'][0].update(value=0.4, status='reported')
        dom = FleetDOM(VIEW.render(data))
        codex = next(row for row in dom.group('data-tracking-lane') if row['attrs']['data-tracking-client'] == 'codex')
        self.assertIn('0.4 calls/s', codex['text'])
        self.assertIn('(reported)', codex['text'])

    def test_hcom_creation_epochs_display_utc_and_invalid_times_stay_unknown(self):
        data = fixture()
        agents = data['tracking']['hcom']['agents']
        agents[0]['created_at'] = 1791572400
        for agent, value in zip(agents[1:], [True, -1, float('inf'), 'invalid timestamp']):
            agent['created_at'] = value
        markup = VIEW.render(data)
        rows = FleetDOM(markup).group('data-hcom-name')
        self.assertIn('2026-10-09T19:00:00Z', rows[0]['text'])
        self.assertNotIn('1791572400', rows[0]['text'])
        self.assertIn('<time datetime="2026-10-09T19:00:00Z">', markup)
        for row in rows[1:5]:
            self.assertIn('UNKNOWN', row['text'])

    def test_scrape_readings_keep_their_scope_and_stale_measurements_are_unknown(self):
        data = fixture()
        data['tracking']['lanes'][0]['clients'][0]['tokens'][0].update(value=999, stale=True, reason='Sample is stale.')
        dom = FleetDOM(VIEW.render(data))
        codex = next(row for row in dom.group('data-tracking-lane') if row['attrs']['data-tracking-client'] == 'codex')
        self.assertIn('Sample is stale.', codex['text'])
        self.assertNotIn('999 tokens/s', codex['text'])
        rows = dom.group('data-tracking-service')
        self.assertIn('1 scrape indicator', rows[0]['text'])
        self.assertIn('0 scrape indicator', rows[1]['text'])
        self.assertIn('UNKNOWN scrape indicator', rows[2]['text'])
        for row in rows:
            self.assertIn('Prometheus scrape observation', row['text'])
            self.assertNotIn('healthy', row['text'])

    def test_native_manager_properties_preserve_scoped_states_and_reject_other_strings(self):
        data = fixture()
        service = data['tracking']['services'][0]
        states = {'LoadState': 'loaded', 'ActiveState': 'active', 'SubState': 'running', 'UnitFileState': 'enabled'}
        service['observations'] = [{**measurement(value, unit='state'), 'metric': metric, 'scope': 'native user-manager property'} for metric, value in states.items()]
        dom = FleetDOM(VIEW.render(data))
        rows = [row for row in dom.group('data-tracking-service') if row['attrs']['data-tracking-service'] == 'vllm-embed']
        self.assertEqual(len(rows), 4)
        for row, (metric, value) in zip(rows, states.items()):
            self.assertIn(metric, row['text'])
            self.assertIn(value + ' state', row['text'])
            self.assertIn('native user-manager property', row['text'])
            self.assertNotIn('model readiness', row['text'])
        service['observations'] = [{**measurement(value, unit='state'), 'metric': metric, 'scope': 'native user-manager property'} for metric, value in [('ActiveState', '<script>bad()</script>'), ('LoadState', 'active'), ('SubState', 'https://private.example.org'), ('OtherProperty', 'running')]]
        dom = FleetDOM(VIEW.render(data))
        rows = [row for row in dom.group('data-tracking-service') if row['attrs']['data-tracking-service'] == 'vllm-embed']
        self.assertTrue(all('UNKNOWN state' in row['text'] for row in rows))
        self.assertNotIn('script', dom.tags)
        self.assertNotIn('https://private.example.org', '\n'.join(row['text'] for row in rows))

    def test_failed_and_empty_query_sources_remain_visible_without_lane_rows(self):
        data = fixture()
        data['tracking']['lanes'] = []
        data['tracking']['query_observations'] = [
            {'client': 'claude', 'measurement': 'tokens', 'status': 'UNKNOWN', 'reason': 'Source query failed.', 'read_utc': '2026-10-09T20:01:00Z', 'series_count': None},
            {'client': 'codex', 'measurement': 'native MCP calls', 'status': 'UNKNOWN', 'reason': 'Source returned no matching series.', 'read_utc': '2026-10-09T20:01:00Z', 'series_count': 0},
        ]
        dom = FleetDOM(VIEW.render(data))
        rows = dom.group('data-tracking-query')
        self.assertEqual(len(rows), 2)
        self.assertIn('Source query failed.', rows[0]['text'])
        self.assertIn('UNKNOWN', rows[0]['text'])
        self.assertIn('Source returned no matching series.', rows[1]['text'])
        self.assertIn('0', rows[1]['text'])
        self.assertFalse(dom.group('data-tracking-lane'))

    def test_dashboard_links_reject_unsafe_urls_and_preserve_local_grafana_links(self):
        data = fixture()
        unsafe = ['javascript:alert(1)', 'https://chatgpt.com/c/private-item', 'http://reader:fake-password@127.0.0.1:21301/d/x/view',
                  'http://127.0.0.1:21301/d/x/view?access_token=fake-secret', 'http://127.0.0.1:21301/api/auth', 'https://outside.example.org/d/x/view']
        data['tracking']['grafana']['links'] += [{'title': 'Unsafe fixture', 'url': url} for url in unsafe]
        dom = FleetDOM(VIEW.render(data))
        self.assertEqual(dom.links, [fixture()['tracking']['grafana']['links'][0]['url']])
        self.assertFalse(any('fake-password' in value or 'fake-secret' in value for value in dom.attrs))

    def test_collected_claude_records_render_with_distinct_native_explore_datasources(self):
        dom = FleetDOM(VIEW.render(collected_fixture()))
        claude = {item['attrs']['data-invocation-family']: item for item in dom.measurements
                  if item['row'].get('data-tracking-client') == 'claude'}
        self.assertIn('API request records:', claude['api_requests']['text'])
        self.assertIn('0.2 records/s', claude['api_requests']['text'])
        self.assertIn('tool_results', claude)
        self.assertIn('Tool result records:', claude['tool_results']['text'])
        self.assertIn('0.3 records/s', claude['tool_results']['text'])
        for family in ('api_requests', 'tool_results'):
            self.assertIn('(reported)', claude[family]['text'])
            self.assertIn('Window: 300 seconds', claude[family]['text'])
        lane_rows = dom.group('data-tracking-lane')
        self.assertIn('0.25 tokens/s', next(row['text'] for row in lane_rows if row['attrs']['data-tracking-client'] == 'codex'))
        self.assertIn('0.5 tokens/s', next(row['text'] for row in lane_rows if row['attrs']['data-tracking-client'] == 'claude'))
        queries = {}
        for url in dom.links:
            parsed = urlsplit(url)
            if parsed.path != '/explore':
                continue
            parameters = parse_qs(parsed.query)
            self.assertEqual(parameters['schemaVersion'], ['1'])
            for pane in json.loads(parameters['panes'][0]).values():
                for query in pane['queries']:
                    self.assertEqual(query['datasource']['uid'], pane['datasource'])
                    self.assertIn('ecosystem_lane="historic-source-lane"', query['expr'])
                    queries.setdefault(pane['datasource'], []).append(query)
        self.assertEqual(set(queries), {'ns2604-prometheus', 'ns2604-loki'})
        self.assertTrue(all(query['datasource']['type'] == 'loki' and 'service_name="claude-code"' in query['expr'] for query in queries['ns2604-loki']))
        self.assertTrue(any('event_name="api_request"' in query['expr'] for query in queries['ns2604-loki']))
        self.assertTrue(any('event_name="tool_result"' in query['expr'] for query in queries['ns2604-loki']))
        self.assertTrue(all(query['datasource']['type'] == 'prometheus' and 'service_name=' not in query['expr'] for query in queries['ns2604-prometheus']))

    def test_loki_query_windows_do_not_claim_raw_event_freshness(self):
        data = fixture()
        client = data['tracking']['lanes'][0]['clients'][1]
        client['rates'] = [{**measurement(0.2, unit='records/s'), 'family': 'api_requests', 'label': 'API request records',
                            'source_sample_utc': None, 'source': 'http://127.0.0.1:21300',
                            'datasource': {'uid': 'ns2604-loki', 'type': 'loki'},
                            'window_start_utc': '2026-10-09T19:56:00Z', 'window_end_utc': '2026-10-09T20:01:00Z',
                            'scope': 'Exported api_request records in the query window.'}]
        dom = FleetDOM(VIEW.render(data))
        record = next(item for item in dom.measurements if item['row'].get('data-tracking-client') == 'claude')
        self.assertIn('0.2 records/s', record['text'])
        self.assertIn('(reported)', record['text'])
        self.assertIn('Query window:', record['text'])
        self.assertIn('2026-10-09T19:56:00Z', record['text'])
        self.assertIn('2026-10-09T20:01:00Z', record['text'])
        self.assertIn('Evaluated:', record['text'])
        self.assertIn('Window: 300 seconds', record['text'])
        self.assertNotIn('Source sample:', record['text'])
        self.assertNotIn('last event', record['text'].lower())

    def test_collected_zero_and_missing_claude_records_remain_unreported(self):
        dom = FleetDOM(VIEW.render(collected_fixture(api=0, tools=None)))
        claude = {item['attrs']['data-invocation-family']: item for item in dom.measurements
                  if item['row'].get('data-tracking-client') == 'claude'}
        self.assertIn('tool_results', claude)
        for family in ('api_requests', 'tool_results'):
            self.assertIn('UNKNOWN records/s', claude[family]['text'])
            self.assertIn('(unreported)', claude[family]['text'])
            self.assertNotIn('0 records/s', claude[family]['text'])

    def test_dynamic_tracking_values_are_sanitized_before_escaping_without_changing_markup(self):
        data = fixture()
        home = Path('/home') / 'synthetic-person'
        private = str(home / 'fixture')
        encoded = base64.b64encode(private.encode()).decode()
        data['tracking']['hcom']['agents'][0].update(name='synthetic-person', tag=private)
        data['tracking']['lanes'][0]['lane'] = encoded
        data['tracking']['services'][0]['title'] = '<script>bad()</script> synthetic-person'
        data['tracking']['limitations'] = [private, 'https://chatgpt.com/c/private-item']
        data['tracking']['grafana']['links'].append({'title': 'Private fixture', 'url': 'http://127.0.0.1:21301/d/x/view?var-path=' + encoded})
        with patch.object(Path, 'home', return_value=home):
            markup = VIEW.render(data)
        dom = FleetDOM(markup)
        self.assertNotIn('synthetic-person', markup)
        self.assertNotIn(private, markup)
        self.assertNotIn(encoded, markup)
        self.assertNotIn('script', dom.tags)
        self.assertIn('table', dom.tags)
        self.assertIn('li', dom.tags)
        self.assertIn('&lt;script&gt;', markup)
        self.assertEqual(len(dom.group('data-hcom-name')), 19)

    def test_unknown_roster_is_unknown_and_actual_empty_roster_is_zero(self):
        data = fixture()
        data['tracking']['hcom'].update(status='UNKNOWN', agents=None, count=None, reason='Roster source unavailable.')
        unknown = VIEW.render(data)
        self.assertIn('Published count: UNKNOWN', unknown)
        self.assertIn('Roster source unavailable.', unknown)
        data['tracking']['hcom'].update(status='reported', agents=[], count=0, reason=None)
        empty = VIEW.render(data)
        self.assertIn('Published count: 0', empty)
        self.assertIn('0 published agents', empty)
        del data['tracking']
        unavailable = VIEW.render(data)
        self.assertIn('id="fleet-tracking"', unavailable)
        self.assertIn('unreported', unavailable)
        data['tracking'] = {'schema': 'fleet-tracking/1', 'reason': 'Native tracking adapter failed.'}
        unavailable = VIEW.render(data)
        self.assertIn('Native tracking adapter failed.', unavailable)

    def test_tracking_publication_preserves_full_markup_for_a_short_home_name(self):
        specification = importlib.util.spec_from_file_location('fleet_tracking_document', ROOT / 'tools/local-pages/build_pages.py')
        pages = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(pages)
        data = fixture()
        home = Path('/home') / 'li'
        data['tracking']['limitations'] = [str(home / 'fixture')]
        with patch.object(Path, 'home', return_value=home):
            body = VIEW.render(data)
            markup = pages.document('fleet', 'Worker fleet', 'Fixture', 'Source observation', body,
                                    '2026-10-09T20:01:00Z', 'a' * 64, []).decode()
        dom = FleetDOM(markup)
        for tag in ('html', 'head', 'body', 'link', 'main', 'section', 'table', 'li'):
            self.assertIn(tag, dom.tags)
        self.assertNotIn(str(home) + '/', markup)
        self.assertEqual(len(dom.group('data-hcom-name')), 19)


if __name__ == '__main__':
    unittest.main()
