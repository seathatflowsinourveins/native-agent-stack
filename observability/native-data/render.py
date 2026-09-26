#!/usr/bin/env python3
"""Provision native Grafana panels for scoped command observations."""
import argparse
import json
from pathlib import Path


def latest(kind, entity=None):
    marker = ('{service_name="agent-stack-native-data",record_kind="snapshot"}'
              ' | json | entity_id="snapshot" | unwrap observed_unix | __error__="" [30m]')
    entity_filter = ' | entity_id="' + entity + '"' if entity else ''
    return ('last_over_time({service_name="agent-stack-native-data",record_kind="' + kind
            + '"} | json' + entity_filter + ' | unwrap observed_unix | __error__="" [30m])'
            ' == on() group_left() max(last_over_time(' + marker + '))')


def by_query_source(field):
    """Sum a claude-code api_request token field by query_source, a free-form string the
    client sets per request (recent examples observed live: repl_main_thread:outputStyle:Concise,
    agent:custom, agent:builtin:workflow-subagent, agent:builtin:general-purpose, agent_summary,
    compact, away_summary -- not an exhaustive or fixed set). Closer to actual usage than the
    Prometheus ecosystem_claude_code_token_usage_tokens_total counters, which have been observed
    to undercount; still overlaps them (both read the same provider usage)."""
    return ('sum by (query_source) (sum_over_time({service_name="claude-code"} | event_name="api_request"'
            ' | unwrap ' + field + ' [$__interval]))')


def dashboard():
    panels = []

    def add(pid, title, typ, x, y, w, h, expr=None, source='ecosystem-loki', **extra):
        item = dict(id=pid, title=title, type=typ, gridPos=dict(x=x, y=y, w=w, h=h))
        if expr:
            item.update(datasource={'uid': source}, targets=[{
                'refId': 'A', 'expr': expr,
                'queryType': 'instant' if typ in ('table', 'stat') else 'range',
                'instant': typ in ('table', 'stat'),
            }])
        item.update(extra)
        panels.append(item)

    add(1, 'Native foundation · useful views', 'text', 0, 0, 24, 7,
        options={'mode': 'markdown', 'content': (
            '# Native foundation\n'
            'Real command observations and existing service data on this PC. '
            'Source dates and failed observations remain visible.\n\n'
            '[Memory UI](http://127.0.0.1:49374/web/w/agent-lab/agent-lab) · '
            '[Qdrant collections](http://127.0.0.1:16333/dashboard#/collections) · '
            '[Code graph snapshot](http://127.0.0.1:17500/socraticode-graph.html) · '
            '[Full token report](http://127.0.0.1:17500/token-savings.html) · '
            '[Session archive](http://127.0.0.1:17384/)\n\n'
            '[Selected RAG model](https://huggingface.co/nvidia/Nemotron-3-Embed-1B-BF16) · '
            '[Upstream MTEB model dashboard](https://leaderboard.mteb.org/models/nvidia/Nemotron-3-Embed-1B-BF16) · '
            '[Model qualification](https://github.com/seathatflowsinourveins/native-agent-stack/blob/main/docs/hf-memory-model-qualification.md)\n\n'
            '[Dagu run history](http://127.0.0.1:18525/dag-runs) · '
            '[Notifications](http://127.0.0.1:18080/ecosystem-alerts) · '
            '[Promptfoo local fixture](http://127.0.0.1:17500/promptfoo.html) · '
            '[Gateway usage](http://127.0.0.1:20128/dashboard/analytics) · '
            '[Native telemetry](/d/ecosystem-native) · [Research](/d/research-grand) · '
            '[Upstream commands and evidence](https://github.com/seathatflowsinourveins/native-agent-stack/blob/main/docs/native-dashboard-data.md)\n\n'
            'Memory browser search is global FTS5; project-scoped semantic recall uses MCP. '
            'Expand System in the read-only wiki to see session pages. '
            'Dagu defaults to Today; select Last 30 days for retained runs. '
            'The code graph is an explicitly refreshed snapshot. '
            '[Memory and RAG practice](https://github.com/seathatflowsinourveins/native-agent-stack/blob/main/docs/memory-rag-native-practice.md)\n\n'
            '**Accounting:** native savings are estimates. Project counts can be subsets of global counts. '
            'Provider usage and cache reads are separate; never add these into one savings total. '
            'The catalog records prior acceptance, not new execution of every component.'
        )})
    add(2, 'Observation delivery time', 'stat', 0, 7, 8, 4,
        '1000 * max(last_over_time({service_name="agent-stack-native-data",record_kind="snapshot"}'
        ' | json | unwrap observed_unix | __error__="" [30m]))',
        description='Delivery time only. Each source has its own observation date below. No data after 30 minutes is unknown.',
        fieldConfig={'defaults': {'unit': 'dateTimeFromNow', 'noValue': 'No recent observation',
                                  'color': {'mode': 'fixed', 'fixedColor': 'text'}}, 'overrides': []})
    add(3, 'Collections in local Qdrant', 'stat', 8, 7, 8, 4,
        'collections_total{job="qdrant"}', source='ecosystem-prometheus',
        fieldConfig={'defaults': {'unit': 'short', 'noValue': 'Unknown'}, 'overrides': []})
    add(4, 'Embedding requests currently running', 'stat', 16, 7, 8, 4,
        'sum(vllm:num_requests_running{job="vllm"})', source='ecosystem-prometheus',
        description='Native embedding-server gauge. Idle zero does not mean retrieval is unavailable.',
        fieldConfig={'defaults': {'unit': 'short', 'noValue': 'Unknown'}, 'overrides': []})

    def table(pid, kind, title, y, height, fields, entity=None, widths=None):
        rename = {
            'title': 'Source / scope', 'state': 'Observation', 'value': 'Native value',
            'unit': 'Unit', 'kind': 'Measurement', 'estimated_saved': 'Retained native estimate',
            'session_estimated_saved': 'Session byte estimate',
            'source_updated_at': 'Source updated UTC', 'source_command': 'Command / source',
            'coverage_status': 'Original audit status',
            'canonical_receipt_count': 'Canonical receipts (read scope)',
            'timestamp_basis': 'Timestamp meaning',
            'boundary': 'Scope / limits',
            'embedding_status': 'Status',
            'embedding_provider': 'Provider',
            'embedding_model': 'Model',
            'embedding_dimensions': 'Dimensions',
            'embedding_rows': 'Stored',
            'latest_pages_missing_embeddings': 'Missing',
            'embed_failures_unresolved': 'Failures',
            'llm_status': 'LLM',
        }
        add(pid, title, 'table', 0, y, 24, height, latest(kind, entity),
            description='Only the latest complete published generation is displayed. Failed sources replace prior successes with unknown. Historical source time is distinct from delivery time.',
            transformations=[{'id': 'labelsToFields', 'options': {'mode': 'columns'}},
                             {'id': 'filterFieldsByName', 'options': {'include': {'names': fields}}},
                             {'id': 'organize', 'options': {'indexByName': {v: i for i, v in enumerate(fields)},
                                                           'renameByName': rename}}],
            options={'showHeader': True, 'cellHeight': 'sm', 'footer': {'show': False}},
            fieldConfig={'defaults': {'noValue': '—', 'custom': {'align': 'auto', 'wrapText': False,
                                                               'cellOptions': {'type': 'auto'}}},
                         'overrides': [{'matcher': {'id': 'byName', 'options': rename.get(name, name)},
                                        'properties': [{'id': 'custom.width', 'value': width}]}
                                       for name, width in (widths or {}).items()]})

    table(5, 'savings', 'Token-saving estimates · separate native scopes', 11, 12,
          ['title', 'state', 'estimated_saved', 'session_estimated_saved', 'source_updated_at',
           'kind', 'boundary', 'source_command'])
    table(6, 'memory', 'Memory and retrieval · actual scoped inventory', 23, 7,
          ['title', 'state', 'value', 'unit', 'source_updated_at'],
          widths={'title': 290, 'state': 125, 'value': 90, 'unit': 85, 'source_updated_at': 260})
    table(13, 'memory', 'ai-memory · model and completeness', 30, 7,
          ['state', 'embedding_model', 'embedding_dimensions', 'embedding_status', 'embedding_provider',
           'embedding_rows', 'latest_pages_missing_embeddings', 'embed_failures_unresolved',
           'llm_status'], entity='ai-memory',
          widths={'state': 100, 'embedding_model': 185, 'embedding_dimensions': 90, 'embedding_status': 85,
                  'embedding_provider': 80, 'embedding_rows': 65, 'latest_pages_missing_embeddings': 75,
                  'embed_failures_unresolved': 75, 'llm_status': 80})
    panels[-1]['description'] += (' Stored includes superseded page vectors. Missing means latest pages without '
                                  'vectors; Failures means unresolved embedding failures. LLM disabled means '
                                  'automatic model-based consolidation is not configured.')
    table(14, 'memory', 'Memory and retrieval · source commands and limits', 37, 7,
          ['title', 'source_command', 'boundary'], widths={'title': 320, 'source_command': 380})
    add(7, 'Native Qdrant vectors · keep dense and sparse separate', 'timeseries', 0, 44, 12, 8,
        'collection_vectors{job="qdrant"}', source='ecosystem-prometheus',
        description='A point can have both dense and sparse vectors. Do not sum vector series as document or chunk counts.')
    add(8, 'Native embedding-server completed requests', 'timeseries', 12, 44, 12, 8,
        'vllm:request_success_total{job="vllm"}', source='ecosystem-prometheus',
        description='Native process counters by completion reason; not token savings or lifetime across restarts.')
    add(9, 'Codex provider telemetry · typed counters', 'timeseries', 0, 52, 12, 8,
        'sum by (token_type) (ecosystem_codex_turn_token_usage_sum)', source='ecosystem-prometheus',
        description='Native exported usage; overlapping cache/input/total fields must not be added. Not a counterfactual saving.')
    add(10, 'Claude provider telemetry · typed counters (Prometheus; known to undercount)', 'timeseries', 12, 52, 12, 8,
        'sum by (type) (ecosystem_claude_code_token_usage_tokens_total)', source='ecosystem-prometheus',
        description='Only native exported samples in the selected range. This Prometheus counter has been '
                    'observed to undercount actual usage against the Loki api_request panels below (about half '
                    'the total on a measured day). The cause is identified (token-stack audit gap G1, '
                    '2026-09-26): concurrent Claude Code processes export the same cumulative series, because the '
                    'collector labels every one instance="unscoped" and OTEL_METRICS_INCLUDE_SESSION_ID is false, '
                    'so each series holds whichever process wrote last and a raw sum drops the rest. '
                    'Cross-check against the cache-read '
                    'Loki panel below (id 15): for the completed 2026-09-24 EDT day it reconciled with '
                    'transcript-based counters (ccusage) within about 1% once query_source=agent_summary was '
                    'excluded. The other three query_source-split panels (input, output, cache-creation tokens) '
                    'have not yet been reconciled this way. An inactive client may have no current series; use '
                    'its archive/report for recorded usage.')
    table(11, 'coverage', 'All selected repositories · recorded acceptance, not live process status', 60, 18,
          ['title', 'coverage_status', 'canonical_receipt_count', 'state', 'source_updated_at', 'timestamp_basis', 'boundary'])
    add(12, 'Sanitized native client activity', 'logs', 0, 78, 24, 10,
        '{service_name=~"Codex Desktop|codex-app-server|claude-code|codex-sdk-receipt"}',
        options={'showTime': True, 'sortOrder': 'Descending', 'wrapLogMessage': True},
        description='Existing native telemetry; prompt/tool bodies are removed upstream in the collector.')

    for pid, field, title, x, y in (
        (15, 'cache_read_tokens', 'Cache-read tokens by query_source', 0, 88),
        (16, 'input_tokens', 'Input tokens by query_source', 12, 88),
        (17, 'output_tokens', 'Output tokens by query_source', 0, 96),
        (18, 'cache_creation_tokens', 'Cache-creation tokens by query_source', 12, 96),
    ):
        add(pid, title + ' (Loki api_request)', 'timeseries', x, y, 12, 8, by_query_source(field),
            description='Live claude-code api_request events unwrapped and split by query_source, a free-form '
                        'string the client sets per request (recent examples: repl_main_thread:outputStyle:Concise, '
                        'agent:custom, agent:builtin:workflow-subagent, agent:builtin:general-purpose, '
                        'agent_summary, compact, away_summary). Closer to actual usage than the Prometheus '
                        'typed-counters panel above; still overlaps it (both read the same underlying provider '
                        'usage) and must not be summed with it or with the savings table. The legend sum equals '
                        'the range total only when the query step equals $__interval; verify that in Grafana '
                        'before reading it as a total.',
            options={'legend': {'displayMode': 'table', 'placement': 'bottom', 'calcs': ['sum']}})
    add(19, 'Claude provider telemetry · effort split (Prometheus; overcounts while sessions overlap)', 'timeseries',
        0, 104, 12, 8,
        'sum by (effort) (increase(ecosystem_claude_code_token_usage_tokens_total[$__rate_interval]))',
        source='ecosystem-prometheus',
        description='Per-interval increase, split by effort level (the metrics pipeline keeps the "effort" '
                    'datapoint attribute; see observability/collector/collector.yaml). increase() is used rather '
                    'than a raw sum of the cumulative counter because the collector expires stale series '
                    '(deltatocumulative max_stale 1h) and sets no metric_expiration, so exposed series appear and '
                    'disappear with session activity; a plain sum by (effort) of the raw counter follows series '
                    'lifetimes, not token use. The series collision behind the typed-counters panel\'s undercount '
                    '(G1) makes increase() overcount instead: each drop from one process\'s cumulative value to '
                    'another\'s reads as a counter reset, so while sessions overlap the increase can exceed actual '
                    'usage many times over. Read it for effort-level shape only, never as a total, until G1 is '
                    'fixed.')
    return dict(uid='native-foundation-data', title='Native foundation · memory, retrieval and savings',
                schemaVersion=39, version=4, editable=False, preload=True, timezone='browser', refresh='30s',
                time={'from': 'now-6h', 'to': 'now'}, tags=['ecosystem', 'native', 'memory', 'tokens'],
                panels=panels)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(dashboard(), indent=2) + '\n')
    print('Rendered native-foundation-data Grafana dashboard.')
