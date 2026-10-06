"""Native per-session Lanes dashboard, using existing Grafana/Loki provisioning.

Sources: grafana/grafana v13.2.3 JSON dashboards and table transformations;
grafana/loki v3.7.8 LogQL range aggregations and label_replace/vector;
openai/codex rust-v0.160.1 d27764b8 otel/src/events/session_telemetry.rs:1106.
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
                   'Observation time and native status age are separate. Inspect observation time: an old '
                   'active record is historical, not live liveness. Automatic freshness masking remains open.')
    status['targets'][0]['queryType'] = 'range'
    status['transformations'] = [
        {'id': 'extractFields', 'options': {'source': 'Line', 'format': 'json', 'replace': True,
                                           'keepTime': True}},
        {'id': 'groupBy', 'options': {'fields': {
            'identity': {'operation': 'groupby'},
            **{key: {'operation': 'aggregate', 'aggregations': ['lastNotNull']}
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
    panel('Per-session shells, RTK prefix share and Claude skills', [
        ('Codex shell results', shell), ('Codex RTK-first results', rtk),
        ('Codex RTK prefix % of classified shells', f'100 * ({rtk}) / ({known_shell})'),
        ('Claude Bash results', records(CLAUDE, 'tool_result', 'session_id', '| tool_name="Bash"')),
        ('Claude Skill results', records(CLAUDE, 'tool_result', 'session_id', '| tool_name="Skill"'))],
        'exec_command only; write_stdin is not another command. RTK prefix is not hook firing/rewrite. '
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
        ('Codex tokens — lower bound until step 7 read-back', f'sum by (ecosystem_lane,token_type) (increase(codex_turn_token_usage_sum[{WINDOW}]))', 'Start-timestamp ingestion still needs deployed flag and a newly born single-turn series read-back. Never add this total to Loki usage.'),
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
    return base
