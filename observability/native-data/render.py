#!/usr/bin/env python3
"""Provision native Grafana panels for scoped command observations."""
import argparse
import json
from pathlib import Path


def latest(kind):
    marker = ('{service_name="agent-stack-native-data",record_kind="snapshot"}'
              ' | json | entity_id="snapshot" | unwrap observed_unix | __error__="" [30m]')
    return ('last_over_time({service_name="agent-stack-native-data",record_kind="' + kind
            + '"} | json | unwrap observed_unix | __error__="" [30m])'
            ' == on() group_left() max(last_over_time(' + marker + '))')


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
            '[Code graph](http://127.0.0.1:17500/socraticode-graph.html) · '
            '[Full token report](http://127.0.0.1:17500/token-savings.html) · '
            '[Session archive](http://127.0.0.1:17384/)\n\n'
            '[Dagu run history](http://127.0.0.1:18525/dag-runs) · '
            '[Notifications](http://127.0.0.1:18080/ecosystem-alerts) · '
            '[Promptfoo local fixture](http://127.0.0.1:17500/promptfoo.html) · '
            '[Gateway usage](http://127.0.0.1:20128/dashboard/usage) · '
            '[Native telemetry](/d/ecosystem-native) · [Research](/d/research-grand) · '
            '[Upstream commands and evidence](https://github.com/seathatflowsinourveins/native-agent-stack/blob/main/docs/native-dashboard-data.md)\n\n'
            '**Accounting:** native savings are estimates. Project counts can be subsets of global counts. '
            'Provider usage and cache reads are separate; never add these into one savings total. '
            'The catalog records prior acceptance, not new execution of every component.'
        )})
    add(2, 'Observation delivery time', 'stat', 0, 7, 8, 4,
        '1000 * max(last_over_time({service_name="agent-stack-native-data",record_kind="snapshot"}'
        ' | json | unwrap observed_unix | __error__="" [30m]))',
        description='Delivery time only. Each source has its own observation date below. No data after 30 minutes is unknown.',
        fieldConfig={'defaults': {'unit': 'dateTimeFromNow', 'noValue': 'No recent observation'}, 'overrides': []})
    add(3, 'Collections in local Qdrant', 'stat', 8, 7, 8, 4,
        'collections_total{job="qdrant"}', source='ecosystem-prometheus',
        fieldConfig={'defaults': {'unit': 'short', 'noValue': 'Unknown'}, 'overrides': []})
    add(4, 'Embedding requests currently running', 'stat', 16, 7, 8, 4,
        'sum(vllm:num_requests_running{job="vllm"})', source='ecosystem-prometheus',
        description='Native embedding-server gauge. Idle zero does not mean retrieval is unavailable.',
        fieldConfig={'defaults': {'unit': 'short', 'noValue': 'Unknown'}, 'overrides': []})

    def table(pid, kind, title, y, height, fields):
        rename = {
            'title': 'Source / scope', 'state': 'Observation state', 'value': 'Native value',
            'unit': 'Unit', 'kind': 'Measurement', 'estimated_saved': 'Retained native estimate',
            'session_estimated_saved': 'Session byte estimate',
            'source_updated_at': 'Source updated UTC', 'source_command': 'Command / source',
            'coverage_status': 'Original audit status',
            'canonical_receipt_count': 'Canonical receipts (read scope)',
            'timestamp_basis': 'Timestamp meaning',
            'boundary': 'Scope / limits',
        }
        add(pid, title, 'table', 0, y, 24, height, latest(kind),
            description='Only the latest complete published generation is displayed. Failed sources replace prior successes with unknown. Historical source time is distinct from delivery time.',
            transformations=[{'id': 'labelsToFields', 'options': {'mode': 'columns'}},
                             {'id': 'filterFieldsByName', 'options': {'include': {'names': fields}}},
                             {'id': 'organize', 'options': {'indexByName': {v: i for i, v in enumerate(fields)},
                                                           'renameByName': rename}}],
            options={'showHeader': True, 'cellHeight': 'sm', 'footer': {'show': False}},
            fieldConfig={'defaults': {'noValue': '—', 'custom': {'align': 'auto', 'wrapText': True,
                                                               'cellOptions': {'type': 'auto'}}}, 'overrides': []})

    table(5, 'savings', 'Token-saving estimates · separate native scopes', 11, 12,
          ['title', 'state', 'estimated_saved', 'session_estimated_saved', 'source_updated_at',
           'kind', 'boundary', 'source_command'])
    table(6, 'memory', 'Memory and retrieval · actual scoped inventory', 23, 11,
          ['title', 'state', 'value', 'unit', 'source_updated_at', 'kind', 'boundary', 'source_command'])
    add(7, 'Native Qdrant vectors · keep dense and sparse separate', 'timeseries', 0, 34, 12, 8,
        'collection_vectors{job="qdrant"}', source='ecosystem-prometheus',
        description='A point can have both dense and sparse vectors. Do not sum vector series as document or chunk counts.')
    add(8, 'Native embedding-server completed requests', 'timeseries', 12, 34, 12, 8,
        'vllm:request_success_total{job="vllm"}', source='ecosystem-prometheus',
        description='Native process counters by completion reason; not token savings or lifetime across restarts.')
    add(9, 'Codex provider telemetry · typed counters', 'timeseries', 0, 42, 12, 8,
        'sum by (token_type) (ecosystem_codex_turn_token_usage_sum)', source='ecosystem-prometheus',
        description='Native exported usage; overlapping cache/input/total fields must not be added. Not a counterfactual saving.')
    add(10, 'Claude provider telemetry · typed counters', 'timeseries', 12, 42, 12, 8,
        'sum by (type) (ecosystem_claude_code_token_usage_tokens_total)', source='ecosystem-prometheus',
        description='Only native exported samples in the selected range. An inactive client may have no current series; use its archive/report for recorded usage.')
    table(11, 'coverage', 'All selected repositories · recorded acceptance, not live process status', 50, 18,
          ['title', 'coverage_status', 'canonical_receipt_count', 'state', 'source_updated_at', 'timestamp_basis', 'boundary'])
    add(12, 'Sanitized native client activity', 'logs', 0, 68, 24, 10,
        '{service_name=~"Codex Desktop|codex-app-server|claude-code|codex-sdk-receipt"}',
        options={'showTime': True, 'sortOrder': 'Descending', 'wrapLogMessage': True},
        description='Existing native telemetry; prompt/tool bodies are removed upstream in the collector.')
    return dict(uid='native-foundation-data', title='Native foundation · memory, retrieval and savings',
                schemaVersion=39, version=2, editable=False, preload=True, timezone='browser', refresh='30s',
                time={'from': 'now-6h', 'to': 'now'}, tags=['ecosystem', 'native', 'memory', 'tokens'],
                panels=panels)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(dashboard(), indent=2) + '\n')
    print('Rendered native-foundation-data Grafana dashboard.')
