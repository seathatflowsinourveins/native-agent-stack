"""Native per-session Lanes dashboard, using existing Grafana/Loki provisioning.

Sources: grafana/grafana v13.2.3 JSON dashboards and table transformations;
grafana/loki v3.7.8 LogQL range aggregations and label_replace/vector;
openai/codex rust-v0.160.1 d27764b8 otel/src/events/session_telemetry.rs:1106.
Rate/cost: Prometheus rate/increase; Claude Code monitoring-usage#cost-counter.
Gateway: opentelemetry-collector-contrib v0.162.0 spanmetricsconnector/README.md;
semantic-conventions-genai 06ec68e7 client-inference.md (Development);
OmniRoute c1e30b76 open-sse/services/routing/otel.ts:193-216.
The named nested-call stream was qualified once on 2026-10-06. Result rows,
started turns, request token counters and native status are distinct measures.
"""
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LOKI = {"type": "loki", "uid": "ns2604-loki"}
PROMETHEUS = {"type": "prometheus", "uid": "ns2604-prometheus"}
CODEX = '{service_name=~"codex-app-server|codex_exec|codex_cli_rs"}'
CLAUDE = '{service_name="claude-code"}'
WINDOW = '${window}'


def records(selector, event, identity, extra="", groups="identity"):
    return (f'sum by ({groups}) (count_over_time({selector} | event_name="{event}" '
            f'| label_format identity={identity} {extra} [{WINDOW}]))')


def usage(selector, event, identity, field, extra=""):
    return (f'sum by (identity) (sum_over_time({selector} | event_name="{event}" '
            f'| label_format identity={identity} {extra} | unwrap {field} '
            f'| __error__="" [{WINDOW}]))')


def claude_usage_panels(base):
    """Insert the textfile usage row after request tokens, keeping existing panel IDs.

    Grafana v13.2.3 bargauge uses percentunit (0..1); datetime units use ms.
    Source timestamps are gauge values. Unknown transitions never become zeros.
    """
    panels = base['panels']
    anchor = next(i for i, p in enumerate(panels) if p['title'] == 'Claude request usage by native session')
    start = panels[anchor]['gridPos']['y'] + panels[anchor]['gridPos']['h']
    added = []
    first_id = max(p['id'] for p in panels) + 1
    link = {'title': 'GPT pool in OmniRoute', 'url': 'http://127.0.0.1:21128/dashboard/analytics',
            'targetBlank': True}
    collected = '(claude_usage_collection_timestamp_seconds > time() - 1800)'
    collection_gate = f' and on(job, instance) {collected}'

    def row(title, offset):
        added.append({'id': first_id + len(added), 'type': 'row', 'title': title, 'collapsed': False,
                      'panels': [], 'gridPos': {'x': 0, 'y': start + offset, 'w': 24, 'h': 1}})

    def chart(title, expressions, description, kind, unit, x, y, w, h):
        item = {'id': first_id + len(added), 'title': title, 'type': kind, 'datasource': PROMETHEUS,
                'gridPos': {'x': x, 'y': start + y, 'w': w, 'h': h},
                'description': description, 'links': [link.copy()],
                'targets': [{'refId': chr(65 + i), 'expr': expr, 'legendFormat': label,
                             'instant': True, 'range': False, 'format': 'time_series',
                             'datasource': PROMETHEUS} for i, (label, expr) in enumerate(expressions)],
                'fieldConfig': {'defaults': {'unit': unit, 'noValue': 'UNKNOWN'}, 'overrides': []},
                'options': {'reduceOptions': {'values': True, 'calcs': ['lastNotNull'], 'fields': ''},
                            'orientation': 'horizontal', 'showUnfilled': True, 'displayMode': 'basic',
                            'textMode': 'value_and_name'}}
        if kind == 'bargauge':
            item['fieldConfig']['defaults'].update(min=0, max=1, thresholds={
                'mode': 'absolute', 'steps': [{'color': 'green', 'value': None},
                                             {'color': 'orange', 'value': .8}, {'color': 'red', 'value': 1}]},
                color={'mode': 'thresholds'})
        added.append(item)
        return item

    row('Claude usage', 0)
    for x, window in ((0, 'five_hour'), (12, 'seven_day')):
        selector = f'{{window="{window}"}}'
        stamp = f'claude_max_observed_timestamp_seconds{selector}'
        expression = (f'max by (account) (claude_max_utilization_ratio{selector}'
                      f' and on(job,instance,account,window) ({stamp} > time() - 1800)'
                      f' and on(job,instance,account,window) ({stamp} <= time()){collection_gate})')
        chart(f'Claude Max · {window}', [('{{account}}', expression)],
              'Native rate_limit_event utilization (fraction), collected by the CC at most every 15 minutes. '
              'Rejected/exhausted limits show 100%; rejection without a supported scope conservatively shows '
              '100% for both windows. Missing utilization stays UNKNOWN; transitions do not refresh absent '
              'fields. Observations older than 30 minutes are hidden. This is Max headroom, separate from '
              'request token counts and API-equivalent cost.', 'bargauge', 'percentunit', x, 1, 12, 8)
    reset_stamp = 'claude_max_reset_observed_timestamp_seconds'
    reset_expr = ('max by (account,window) (claude_max_reset_timestamp_seconds'
                  f' and on(job,instance,account,window) ({reset_stamp} > time() - 1800)'
                  f' and on(job,instance,account,window) ({reset_stamp} <= time()){collection_gate}) * 1000')
    chart('Claude Max · reset time', [('{{account}} · {{window}}', reset_expr)],
          'Native resetsAt seconds converted to Grafana milliseconds. No reset is inferred for a rejection '
          'or missing field. Reset observations expire after 30 minutes.', 'stat', 'dateTimeAsIso', 0, 9, 12, 6)
    chart('Claude Max · utilization observation age', [('{{account}} · {{window}}',
          'time() - max by (account,window) (claude_max_observed_timestamp_seconds)')],
          'Age of the actual utilization observation, including retained stale values. A new capture without '
          'utilization does not refresh this age. UNKNOWN means the window has never been observed.',
          'stat', 'dtdurations', 12, 9, 12, 6)
    ledger_gate = f' and on(job,instance) (claude_usage_ledger_success == 1){collection_gate}'
    chart('Anthropic API · $200 edge', [('{{key}}',
          f'max by (key) ((claude_api_spend_usd / claude_api_edge_usd){ledger_gate})')],
          'Ledger accounted charges against each key’s $200 edge. This includes uncertain charges retained '
          'pending provider reconciliation; open reservations are shown separately below. Subscription '
          'limits, provider snapshots and API-equivalent OTel cost are separate sources. Key labels are '
          'persistent opaque indexes. Unattributed legacy rows receive no guessed key or $200 denominator.',
          'bargauge', 'percentunit', 0, 15, 12, 8)
    amounts = chart('Anthropic API · ledger amounts', [
        (label, f'max by (key) ({metric}{ledger_gate})') for label, metric in (
            ('Accounted charges', 'claude_api_spend_usd'), ('Open reservations', 'claude_api_pending_usd'),
            ('Uncertain subset of charges', 'claude_api_uncertain_usd'))],
        'USD from api-actions ledger values only. Uncertain is a subset of accounted charges; do not add it '
        'again. Settlement attribution follows the original debit, including after a key switch. '
        'Provider snapshots and notes do not add charges.', 'table', 'currencyUSD', 12, 15, 12, 8)
    amounts['options'] = {'showHeader': True}
    for target in amounts['targets']:
        target['format'] = 'table'
    amounts['transformations'] = [{'id': 'joinByField', 'options': {'byField': 'key', 'mode': 'outer'}}]
    chart('Claude usage · collection time', [('Collected',
          'max(claude_usage_collection_timestamp_seconds) * 1000')],
          'Latest collection of recorded limits and ledger amounts, distinct from per-window observation '
          'age. Missing or failed sources remain UNKNOWN.',
          'stat', 'dateTimeFromNow', 0, 23, 12, 5)
    chart('Anthropic API · unattributed ledger charges', [('Unattributed USD',
          f'max(claude_api_unattributed_spend_usd{ledger_gate})')],
          'Legacy rows without a key alias remain unattributed until the CC supplies the producer’s confirmed '
          'legacy alias. This amount is excluded from per-key bars, not silently lost.',
          'stat', 'currencyUSD', 12, 23, 12, 5)
    # An expanded Grafana row extends until the next row. Bound this new section.
    row('Native records and telemetry', 28)
    for existing in panels[anchor + 1:]:
        existing['gridPos']['y'] += 29
    panels[anchor + 1:anchor + 1] = added


def dashboard():
    base = json.loads((REPO / 'observability/backends/templates/ecosystem-dashboard.json.example').read_text())
    base.update(uid='cc-lanes', title='Lanes', editable=False, tags=['native', 'lanes'],
                refresh='30s', time={'from': 'now-1h', 'to': 'now'}, panels=[],
                templating={'list': [{'name': 'window', 'label': 'Count window', 'type': 'custom',
                                      'query': '1h,24h', 'current': {'text': '1h', 'value': '1h'},
                                      'options': [{'text': v, 'value': v, 'selected': v == '1h'}
                                                  for v in ('1h', '24h')]}]})

    def panel(title, expressions, description, kind='table'):
        ordinal = len(base['panels'])
        targets = [{'refId': chr(65 + i), 'expr': expression, 'queryType': 'instant',
                    'legendFormat': label, 'datasource': LOKI}
                   for i, (label, expression) in enumerate(expressions)]
        item = {'id': ordinal + 1, 'title': title, 'type': kind, 'datasource': LOKI,
                'gridPos': {'x': 0, 'y': ordinal * 9, 'w': 24, 'h': 9},
                'description': description, 'targets': targets,
                'fieldConfig': {'defaults': {'noValue': 'UNKNOWN'}, 'overrides': []},
                'options': {'showHeader': True}}
        if kind == 'table':
            item['transformations'] = [{'id': 'labelsToFields', 'options': {'mode': 'columns'}},
                                       {'id': 'joinByField', 'options': {'byField': 'identity',
                                                                        'mode': 'outer'}}]
        base['panels'].append(item)
        return item

    header = panel('Observation contract', [], '', 'text')
    header['options'] = {'mode': 'markdown', 'content': (
        'Native result records, hcom status and request usage for **1 h / 24 h**. '
        'Identity is Codex conversation ID or Claude session ID. The hcom table maps registered roots; '
        'child identities stay separate until their native parent mapping is qualified. '
        'Missing identity, exposure, export or status freshness is **UNKNOWN**. '
        'A zero inventory row means no result record was visible; it proves organic non-use only after '
        'exposure and full-window coverage are qualified. Outer code-mode wrappers are tool rows, '
        'and are not additional MCP calls. Started user turns are not completed turns. '
        'Claude Skill calls and Codex read-command observations are separate contracts. '
        'Input, output and cache counters remain separate; provider/cache totals are not summed. '
        '[Token layer](/d/token-layer) · [Native telemetry](/d/ecosystem-native)')}

    status = panel('Latest recorded hcom status and root-name lookup',
                   [('Status', '{service_name="agent-stack-lanes",record_kind="hcom"} | json')],
                   'Recorded status JSON from hcom list; registry roots missing from hcom remain unknown. '
                   'The latest complete JSON row per identity supplies every field, including null age/unread. '
                   'Observation time and native status age are separate. Inspect observation time: an old '
                   'active record is historical, not live liveness. Automatic freshness masking remains open.')
    status['targets'][0]['queryType'] = 'range'
    status['transformations'] = [
        {'id': 'extractFields', 'options': {'source': 'Line', 'format': 'json', 'replace': True,
                                           'keepTime': True}},
        # Grafana v13.2.3 sortBy.ts:16 and fieldReducer.ts:622: sort complete
        # rows, then Last selects that row's value even when it is null.
        {'id': 'sortBy', 'options': {'sort': [{'field': 'Time', 'desc': False}]}},
        {'id': 'groupBy', 'options': {'fields': {
            'identity': {'operation': 'groupby'},
            **{key: {'operation': 'aggregate', 'aggregations': ['last']}
               for key in ('Time', 'lane', 'name', 'client', 'status', 'status_context',
                           'status_age_seconds', 'unread_count', 'observed_unix')}}}}]

    codex_tools = records(CODEX, 'codex.tool_result', 'conversation_id')
    claude_tools = records(CLAUDE, 'tool_result', 'session_id')
    panel('Per-session started turns and tool result records', [
        ('Codex started user turns', records(CODEX, 'codex.user_prompt', 'conversation_id')),
        ('Claude started user turns', records(CLAUDE, 'user_prompt', 'session_id')),
        ('Codex tool results', codex_tools), ('Claude tool results', claude_tools)],
        'Started turns and result rows only; completed-turn counts require native completion evidence. '
        'Use the hcom root-name lookup above. Descendants remain separate rows.')
    shell = records(CODEX, 'codex.tool_result', 'conversation_id', '| tool_name="exec_command"')
    known_shell = records(CODEX, 'codex.tool_result', 'conversation_id',
                          '| tool_name="exec_command" | shell_rtk=~"true|false"')
    rtk = records(CODEX, 'codex.tool_result', 'conversation_id',
                  '| tool_name="exec_command" | shell_rtk="true"')
    classified = f'({known_shell}) > 0'
    panel('Per-session shells, RTK prefix share and Claude skills', [
        ('Codex shell results', shell), ('Codex RTK-first results', rtk),
        ('Codex RTK prefix % of classified shells',
         f'100 * (({rtk}) or on (identity) (0 * ({classified}))) / ({classified})'),
        ('Claude Bash results', records(CLAUDE, 'tool_result', 'session_id', '| tool_name="Bash"')),
        ('Claude Skill results', records(CLAUDE, 'tool_result', 'session_id', '| tool_name="Skill"'))],
        'exec_command only; write_stdin is not another command. RTK prefix is not hook firing/rewrite. '
        'A classified denominator with no RTK-first results gives 0%; no classified denominator stays UNKNOWN. '
        'Claude RTK-first and Codex SKILL.md read counts remain unknown in this live stream; '
        'the native-record baseline keeps those separate, rather than inferring them from MCP calls.')
    panel('Per-session native tools', [
        ('Codex', records(CODEX, 'codex.tool_result', 'conversation_id',
                          groups='identity,tool_namespace,tool_name')),
        ('Claude', records(CLAUDE, 'tool_result', 'session_id', groups='identity,tool_name'))],
        'Each native named result row; no static JavaScript or code-carrier references are counted.')
    panel('Per-session MCP server and tool results', [
        ('Codex MCP', records(CODEX, 'codex.tool_result', 'conversation_id',
                              '| mcp_server_name!=""', 'identity,mcp_server_name,mcp_tool_name')),
        ('Claude MCP', records(CLAUDE, 'tool_result', 'session_id',
                               '| mcp_server_name!=""', 'identity,mcp_server_name,mcp_tool_name'))],
        'Native MCP names, including plugin aliases, retained verbatim. Failed results remain results.')
    panel('Codex request usage by native conversation', [
        (label, usage(CODEX, 'codex.sse_event', 'conversation_id', field,
                       '| event_kind="response.completed"'))
        for label, field in [('Input', 'input_token_count'), ('Output', 'output_token_count'),
                             ('Cached input', 'cached_token_count')]],
        'Native response.completed request counters; cache is a subset of input. Not an organic savings claim.')
    panel('Claude request usage by native session', [
        (label, usage(CLAUDE, 'api_request', 'session_id', field))
        for label, field in [('Input', 'input_tokens'), ('Output', 'output_tokens'),
                             ('Cache read', 'cache_read_tokens'), ('Cache creation', 'cache_creation_tokens')]],
        'Native API request accounting. Do not add cache categories to another inclusive token total.')
    panel('Native API errors and rate limits', [
        ('Claude errors', f'sum by (status_code,error_type) (count_over_time({CLAUDE} | event_name="api_error" [{WINDOW}]))'),
        ('Codex failed tool results', f'sum by (tool_name) (count_over_time({CODEX} | event_name="codex.tool_result" | success="false" [{WINDOW}]))')],
        'Native error records only. Missing rate-limit headroom is UNKNOWN; client status-line configuration is owned by the command center.')
    panel('Native hook results by source and hook name', [
        ('Codex hooks — event coverage unqualified', f'sum by (source,hook_name,hook_event,status) (count_over_time({CODEX} | event_name=~"codex.hook.*" [{WINDOW}]))'),
        ('Claude hook completions', f'sum by (hook_name,hook_event,num_blocking) (count_over_time({CLAUDE} | event_name="hook_execution_complete" [{WINDOW}]))')],
        'Native source and hook attributes retained by collector step 6. A hook row proves RTK only when its identity names RTK; a plural hooks counter alone does not.')
    panel('MCP connections and compaction', [
        ('Claude MCP connections', f'sum by (server_name,status,transport_type) (count_over_time({CLAUDE} | event_name="mcp_server_connection" [{WINDOW}]))'),
        ('Claude compaction', f'sum by (trigger) (count_over_time({CLAUDE} | event_name="compaction" [{WINDOW}]))')],
        'Connection transitions and compactions are not tool invocations. Names require collector step 6 read-back; absent metadata stays unknown.')
    for title, expr, description in [
        ('Backends up', 'up', 'Prometheus scrape health; this is not coverage of every user unit.'),
        ('Gateway health — waits on collector step 6', 'httpcheck_status{http_url="http://127.0.0.1:21128/api/health",http_status_class="2xx"}', 'Only the model-free health route is probed. Native http_url label observed on existing targets. Gateway settings and database routes are excluded.'),
        ('Collector streams against limit', 'max_over_time(otelcol_deltatocumulative_streams_tracked[1h])', 'Watch the 8,000 review threshold against the configured 10,000 stream limit.'),
        ('Codex tokens — lower bound until step 7 read-back', f'sum by (ecosystem_lane,token_type) (increase(codex_turn_token_usage_sum[{WINDOW}]))', 'Lower bound until start-timestamp ingestion has the deployed flag and a newly born single-turn series read-back. Never add this total to Loki usage.'),
        ('Host CPU — collector observed sample', 'system_cpu_load_average_1m', 'Native hostmetrics sample; no GPU or clock-offset coverage is implied.'),
        ('Host memory — collector observed sample', 'system_memory_usage_bytes', 'Native hostmetrics sample. Unit health, clock and GPU collectors remain separately owned gates.')]:
        item = panel(title, [('Value', expr)], description)
        item['datasource'] = PROMETHEUS
        item['targets'][0]['datasource'] = PROMETHEUS
    pending = panel('Pending monitoring sources', [], '', 'text')
    pending['options'] = {'mode': 'markdown', 'content': (
        '**UNKNOWN / pending:** effective per-role tool exposure and exact organic prompt exclusions; '
        'Claude RTK rewrites and Codex skill loads; GitHub newest-complete snapshot (step 12, github-ci-finalize); '
        'unit failures (alerting PR and lm-qmd); GPU exporter (vllm-embed owner); clock offset; '
        'storage size-retention COUNT and oldest-sample AGE (CC read-back owner; deferred during paper, '
        'pending deployed Prometheus flag/effective-limit evidence and restart qualification); '
        'SDK task attribution and gateway optional OTLP span sink (CC environment and restart). '
        'OmniRoute v3.8.51 already ships an optional GenAI OTLP trace sink; no claim that it lacks export until v3.9. '
        'A newly wired zero-call tool remains unmeasured until exposure and a complete 24 h organic window are qualified.')}

    inventory = json.loads((REPO / 'observability/lanes-tool-inventory.json').read_text())
    observed = ('sum by (mcp_server_name,mcp_tool_name) (count_over_time('
                '{service_name=~"codex-app-server|codex_exec|codex_cli_rs|claude-code"} '
                '| event_name=~"codex.tool_result|tool_result" | mcp_server_name!="" '
                f'[{WINDOW}]))')
    zeros = [f'label_replace(label_replace(vector(0),"mcp_server_name",{json.dumps(row["server"])},"",""),'
             f'"mcp_tool_name",{json.dumps(row["tool"])},"","")' for row in inventory['tools']]
    zero_panel = panel('MCP inventory: zero visible result records',
                       [('Visible results or inventory zero', observed + ' or ' + ' or '.join(zeros))],
                       'Dated tool-name exposure inventory for this Codex session, not all clients/lanes. '
                       'Refresh at tools-wave MCP read-back. Zero is informational until full-window '
                       'coverage and exposure are qualified. Plugin aliases appear as separate observed rows.')
    zero_panel['transformations'] = [{'id': 'labelsToFields', 'options': {'mode': 'columns'}}]
    zero_panel['fieldConfig']['defaults']['thresholds'] = {
        'mode': 'absolute', 'steps': [{'color': 'red', 'value': None}, {'color': 'green', 'value': 1}]}
    zero_panel['fieldConfig']['overrides'] = [{
        'matcher': {'id': 'byType', 'options': 'number'},
        'properties': [{'id': 'custom.cellOptions', 'value': {'type': 'color-background'}},
                       {'id': 'color', 'value': {'mode': 'thresholds'}}]}]
    # Clock rows are journal-derived, privacy-filtered logs, not invented host gauges.
    # New state/presence attributes are bounded derivatives of native printed rows.
    clock_selector = '{service_name="clock-offset-check"}'
    clock_freshness = '3m'

    def clock_last(field):
        return (f'last_over_time({clock_selector} | unwrap {field} '
                f'| __error__="" [{clock_freshness}]) by (service_name)')

    clock_present = clock_last('offset_present')
    clock_offset = f'({clock_last("offset_s")}) and on(service_name) ({clock_present} == 1)'
    clock_bound = f'({clock_last("bound_s")}) and on(service_name) ({clock_present} == 1)'
    # Fixed matching labels make this a fallback only when the native vector is empty.
    clock_no_data = 'label_replace(vector(-1),"service_name","clock-offset-check","","")'
    clock_latest_state = f'({clock_last("state_code")}) or ({clock_no_data})'
    clock_latest_presence = f'({clock_present}) or ({clock_no_data})'

    clock_panel = panel('Clock: latest native state and signed offset', [
        ('Offset history (s)', clock_offset),
        ('Error-bound history (s)', clock_bound),
        ('Native state history', clock_last('state_code')),
        ('Latest native state (3m)', clock_latest_state),
        ('Latest offset availability (3m)', clock_latest_presence),
    ],
        'Native clock-offset-check rows. Latest state/availability use a 3m UI freshness '
        'contract for the verified 60s timer; earlier curves are historical. '
        'OK/WARN/CRIT come from the printed state, not offset classification. '
        'Native defaults: WARN bound >0.050s or reference age >1200s, plus reference/leap/trigger '
        'reasons; CRIT |offset| >0.100s. Equality alone does not cross a native threshold. '
        'The 50ms line applies to error bound, not signed offset. '
        'A failed row still shows CRIT while offset availability shows No data. '
        'Missing/stale current rows show No data; the -1 UI marker is not a native sample. '
        'Threshold environment overrides and full native render/export acceptance remain separate.',
        'timeseries')

    for target in clock_panel['targets'][:3]:
        target['queryType'] = 'range'
    # Leave the last two targets instant; never use a historical Last-not-null as current.
    clock_panel['options'] = {
        'legend': {'displayMode': 'table', 'placement': 'bottom', 'calcs': ['last']},
        'tooltip': {'mode': 'multi', 'sort': 'none'},
    }
    clock_panel['fieldConfig'] = {
        'defaults': {
            'noValue': 'No data', 'unit': 's', 'decimals': 6,
            'custom': {'drawStyle': 'line', 'lineInterpolation': 'linear',
                       'spanNulls': False, 'lineWidth': 2, 'axisPlacement': 'left'},
        },
        'overrides': [],
    }

    def clock_override(name, properties):
        clock_panel['fieldConfig']['overrides'].append({
            'matcher': {'id': 'byName', 'options': name},
            'properties': [{'id': key, 'value': value} for key, value in properties],
        })

    clock_state_mapping = [{
        'type': 'value', 'options': {
            '-1': {'text': 'No data', 'color': 'gray'},
            '0': {'text': 'OK', 'color': 'green'},
            '1': {'text': 'WARN', 'color': 'yellow'},
            '2': {'text': 'CRIT', 'color': 'red'},
            '3': {'text': 'UNKNOWN', 'color': 'gray'},
        },
    }]
    for name in ('Offset history (s)', 'Error-bound history (s)', 'Native state history'):
        clock_override(name, [('custom.hideFrom', {'legend': True, 'tooltip': False, 'viz': False})])
    clock_override('Native state history', [
        ('unit', 'none'), ('decimals', 0), ('min', 0), ('max', 3),
        ('mappings', clock_state_mapping), ('custom.axisPlacement', 'right'),
        ('custom.axisLabel', 'Native state'), ('custom.lineInterpolation', 'stepAfter'),
    ])
    clock_override('Latest native state (3m)', [
        ('unit', 'none'), ('decimals', 0), ('mappings', clock_state_mapping),
        ('custom.axisPlacement', 'hidden'),
        ('custom.hideFrom', {'legend': False, 'tooltip': True, 'viz': True}),
    ])
    clock_override('Latest offset availability (3m)', [
        ('unit', 'none'), ('decimals', 0),
        ('mappings', [{'type': 'value', 'options': {
            '-1': {'text': 'No data', 'color': 'gray'},
            '0': {'text': 'No data', 'color': 'gray'},
            '1': {'text': 'Sample available', 'color': 'green'},
        }}]),
        ('custom.axisPlacement', 'hidden'),
        ('custom.hideFrom', {'legend': False, 'tooltip': True, 'viz': True}),
    ])
    clock_override('Offset history (s)', [
        ('color', {'mode': 'fixed', 'fixedColor': 'blue'}),
        ('thresholds', {'mode': 'absolute', 'steps': [
            {'color': 'red', 'value': None}, {'color': 'green', 'value': -0.100},
            {'color': 'red', 'value': 0.100},
        ]}), ('custom.thresholdsStyle', {'mode': 'dashed'}),
    ])
    clock_override('Error-bound history (s)', [
        ('color', {'mode': 'fixed', 'fixedColor': 'yellow'}),
        ('thresholds', {'mode': 'absolute', 'steps': [
            {'color': 'green', 'value': None}, {'color': 'yellow', 'value': 0.050},
        ]}), ('custom.thresholdsStyle', {'mode': 'dashed'}),
    ])

    def plot(title, expressions, description, unit, datasource=LOKI):
        item = panel(title, expressions, description, 'timeseries')
        item['datasource'] = datasource
        item['fieldConfig']['defaults'].update(
            unit=unit, custom={'spanNulls': False})
        item['options'] = {
            'legend': {'displayMode': 'table', 'placement': 'bottom', 'calcs': ['last']},
            'tooltip': {'mode': 'multi', 'sort': 'none'},
        }
        for target in item['targets']:
            target['datasource'] = datasource
            if datasource == PROMETHEUS:
                target.pop('queryType', None)
                target.update(instant=False, range=True, format='time_series')
            else:
                target['queryType'] = 'range'
        return item

    plot('Per-lane native tool-result rate', [
        (f'{{{{ecosystem_lane}}}} · {client}',
         f'sum by (ecosystem_lane) (rate({selector} | event_name="{event}" '
         '| ecosystem_lane!="" [5m]))')
        for client, selector, event in [('Codex', CODEX, 'codex.tool_result'),
                                        ('Claude', CLAUDE, 'tool_result')]],
        'Result records per second over 5m, using the native ecosystem_lane resource label. '
        'Includes failed results and outer code-mode tool rows; this is not an MCP-call count. '
        'Missing lane labels or records remain UNKNOWN. Root/child ownership uses the lookup above.', 'ops')
    plot('Per-lane Codex API attempt rate', [
        ('{{ecosystem_lane}} · attempts',
         'sum by (ecosystem_lane) (rate(codex_api_request_total{ecosystem_lane!=""}[5m]))'),
        ('{{ecosystem_lane}} · failed attempts',
         'sum by (ecosystem_lane) (rate(codex_api_request_total{ecosystem_lane!="",success="false"}[5m]))')],
        'Native API attempt counters per second, including retries; not completed user turns. '
        'rate is applied to each writer before aggregation so counter resets are handled. '
        'No failure series is UNKNOWN, not an invented zero.', 'ops', PROMETHEUS)
    plot('Per-lane estimated Claude API cost', [
        ('{{ecosystem_lane}} · estimated USD',
         f'sum by (ecosystem_lane) (increase(claude_code_cost_usage_USD_total'
         f'{{ecosystem_lane!="",instance!="unscoped"}}[{WINDOW}]))')],
        'Estimated USD over the selected count window, from the native Claude cost counter only. '
        'Counter increase is summed per writer; cumulative snapshots are not added. '
        'This is API-equivalent cost, not a Max subscription bill. Codex cost and gateway spend '
        'are separate, unqualified sources; missing cost or lane coverage remains UNKNOWN.',
        'currencyUSD', PROMETHEUS)
    plot('Per-lane estimated Codex turn cost — conditional coverage', [
        ('{{ecosystem_lane}} · estimated USD',
         f'sum by (ecosystem_lane) (increase(codex_turn_cost_microusd_total'
         f'{{ecosystem_lane!="",instance!="unscoped"}}[{WINDOW}])) / 1000000')],
        'Native Codex 0.161.0 turn-cost counter in micro-USD, converted to estimated USD. '
        'Requires provider analytics/codex/turn-costs enrichment; absent amounts stay UNKNOWN. '
        'First samples and dropped/export-missing usage can be omitted; increase extrapolates '
        'window boundaries, so this is not an exact total or a guaranteed lower bound. '
        'Keep separate from Claude cost, SDK cumulative snapshots and gateway estimates.',
        'currencyUSD', PROMETHEUS)
    plot('Gateway routing rate by provider and model', [
        ('{{gen_ai_provider_name}} · {{gen_ai_request_model}}',
         'sum by (gen_ai_provider_name,gen_ai_request_model) '
         '(rate(traces_span_metrics_calls_total{service_name="omniroute"}[5m]))')],
        'Routing events per second after the CC enables native OmniRoute OTLP and applies '
        'the collector source. Native gateway spans have no lane/session parentage, so these '
        'provider/model totals are not assigned to lanes or added to client request rates. '
        'No received routing series remains UNKNOWN.', 'ops', PROMETHEUS)
    plot('Gateway routing rate by outcome and HTTP status', [
        ('{{gen_ai_provider_name}} · {{omniroute_routing_outcome}} · HTTP {{omniroute_routing_status}}',
         'sum by (gen_ai_provider_name,omniroute_routing_outcome,omniroute_routing_status) '
         '(rate(traces_span_metrics_calls_total{service_name="omniroute"}[5m]))')],
        'Uses vendor omniroute.routing.outcome/status dimensions, not OTel status.code: '
        'the gateway does not set span status. Native status 0 means unknown, not success. '
        'The existing metrics/spans export guard preserves these dimensions. Deployment '
        'and received-event coverage remain the CC host read-back.', 'ops', PROMETHEUS)
    claude_usage_panels(base)
    return base
