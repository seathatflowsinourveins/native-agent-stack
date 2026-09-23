#!/usr/bin/env python3
"""Re-runnable synthetic privacy-canary check for the local observation pipeline.

Emits a distinct synthetic canary through every tested telemetry field of the three
collector ingestion lanes (OTLP logs, OTLP metrics, SDK receipt files), then searches
the exported Prometheus text, Prometheus federation/metadata, Loki query_range and
label values, and the collector's file/events receipt file for each canary.

Default target is an isolated stack (isostack.Stack) running the repository
collector.yaml privacy processors unchanged. --mode passthrough merges an overlay
that removes the privacy processors: it is the detection self-test and MUST report
leaks (exit 1). Exit codes: 0 no leak and every positive control found; 1 leak;
2 a positive control was not found (the query path could not have detected a leak).

Canaries are random hex tokens with a CNRY prefix (not credential-shaped, so secret
scanners do not flag the committed evidence). Detection is plain substring search
for the unique token in the full returned bytes of each backend.
"""
import argparse
import hashlib
import json
import secrets
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import isostack  # noqa: E402

PASSTHROUGH = """service:
  pipelines:
    logs:
      processors: [batch]
    metrics:
      processors: [deltatocumulative, batch]
    logs/sdk_receipts:
      processors: [transform/sdk_receipt, batch]
"""


def kv(d):
    return [{'key': k, 'value': {'stringValue': v}} for k, v in d.items()]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--mode', choices=['privacy', 'passthrough'], default='privacy')
    ap.add_argument('--root', default=None, help='private temp root (default: new dir under ~/.cache/gap-wave2-20260923/observation-inference)')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    base = Path.home() / '.cache/gap-wave2-20260923/observation-inference'
    base.mkdir(parents=True, exist_ok=True)
    root = Path(a.root or tempfile.mkdtemp(prefix=f'canary-{a.mode}-', dir=base))
    run = secrets.token_hex(4)
    C = {}  # field -> token

    def c(field):
        C[field] = f'CNRY{secrets.token_hex(8)}'
        return C[field]

    # Negative canaries: must NOT appear anywhere. Positive/boundary controls: expected to appear
    # because the allowlists are key-based and assume trusted instrumentation.
    negative = {}
    positive = {}
    overlays = []
    if a.mode == 'passthrough':
        ov = root / 'passthrough.yaml'
        root.mkdir(parents=True, exist_ok=True)
        ov.write_text(PASSTHROUGH)
        overlays.append(ov)
    stack = isostack.Stack(root, components=('otelcol', 'prometheus', 'loki'), overlays=overlays)
    result = {'mode': a.mode, 'run': run, 'started_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    try:
        stack.start()
        t0 = time.time_ns()
        svc = f'canary-svc-{run}'
        # ---------------- OTLP logs ----------------
        res_attrs = {'service.name': svc,
                     'user.email': c('logs.resource.user.email'), 'host.name': c('logs.resource.host.name'),
                     'process.command_line': c('logs.resource.process.command_line'),
                     'ecosystem.task.id': c('logs.resource.ecosystem.task.id(allowlisted)')}
        rec_attrs = {'receipt_id': f'canary-{run}',
                     'prompt': c('logs.attr.prompt'), 'tool_input': c('logs.attr.tool_input'),
                     'user.account_uuid': c('logs.attr.user.account_uuid'), 'api_key': c('logs.attr.api_key'),
                     'user.email': c('logs.attr.user.email'), 'error.message': c('logs.attr.error.message'),
                     'tool_name': c('logs.attr.tool_name(allowlisted)')}
        logs = {'resourceLogs': [{
            'resource': {'attributes': kv(res_attrs)}, 'schemaUrl': 'https://example.invalid/' + c('logs.resource.schema_url'),
            'scopeLogs': [{
                'scope': {'name': c('logs.scope.name'), 'version': c('logs.scope.version'),
                          'attributes': kv({'scope.secret': c('logs.scope.attr')})},
                'schemaUrl': 'https://example.invalid/' + c('logs.scope.schema_url'),
                'logRecords': [{
                    'timeUnixNano': str(time.time_ns()), 'observedTimeUnixNano': str(time.time_ns()),
                    'severityNumber': 9, 'severityText': c('logs.severity_text'), 'eventName': c('logs.event_name'),
                    'body': {'stringValue': c('logs.body')}, 'attributes': kv(rec_attrs)}]}]}]}
        st_logs, _ = isostack.http(stack.otlp_http + '/v1/logs', logs)
        # ---------------- OTLP metrics ----------------
        mname = 'canary_counter_' + c('metrics.name(boundary)').lower()
        m_res = {'service.name': svc, 'user.email': c('metrics.resource.user.email'),
                 'host.name': c('metrics.resource.host.name'), 'organization.id': c('metrics.resource.organization.id')}
        dp_attrs = {'type': 'input', 'user.email': c('metrics.attr.user.email'), 'session.id': c('metrics.attr.session.id'),
                    'prompt': c('metrics.attr.prompt'), 'user.account_uuid': c('metrics.attr.user.account_uuid'),
                    'model': c('metrics.attr.model(allowlisted)')}
        now = time.time_ns()
        metrics = {'resourceMetrics': [{
            'resource': {'attributes': kv(m_res)}, 'schemaUrl': 'https://example.invalid/' + c('metrics.resource.schema_url'),
            'scopeMetrics': [{
                'scope': {'name': c('metrics.scope.name'), 'version': c('metrics.scope.version'),
                          'attributes': kv({'scope.secret': c('metrics.scope.attr')})},
                'schemaUrl': 'https://example.invalid/' + c('metrics.scope.schema_url'),
                'metrics': [{
                    'name': mname, 'description': c('metrics.description'), 'unit': '1',
                    'metadata': kv({'meta.secret': c('metrics.metadata')}),
                    'sum': {'aggregationTemporality': 2, 'isMonotonic': True, 'dataPoints': [{
                        'attributes': kv(dp_attrs), 'startTimeUnixNano': str(now - 10**9), 'timeUnixNano': str(now),
                        'asDouble': 7,
                        'exemplars': [{'filteredAttributes': kv({'exemplar.secret': c('metrics.exemplar.attr')}),
                                       'timeUnixNano': str(now), 'asDouble': 1,
                                       'traceId': secrets.token_hex(16), 'spanId': secrets.token_hex(8)}]}]}}]}]}]}
        st_metrics, _ = isostack.http(stack.otlp_http + '/v1/metrics', metrics)
        # ---------------- SDK receipt file lane ----------------
        receipt = {'observation_id': f'canary-receipt-{run}', 'configured_model': c('sdk.configured_model(allowlisted-as-model)'),
                   'usage_status': 'known', 'usage': {'total': {'inputTokens': 11, 'outputTokens': 3, 'totalTokens': 14}},
                   'final_response': c('sdk.final_response'), 'items': [{'text': c('sdk.items.text')}],
                   'error': c('sdk.error'), 'prompt': c('sdk.prompt'), 'cwd': c('sdk.cwd')}
        tmp = stack.spool / f'.canary-{run}.tmp'
        tmp.write_text(json.dumps(receipt, indent=2) + '\n')
        tmp.rename(stack.spool / f'canary-{run}.json')
        for k in list(C):
            (positive if ('(allowlisted' in k or '(boundary)' in k) else negative)[k] = C[k].lower() if '(boundary)' in k else C[k]
        # ---------------- wait for export ----------------
        found = {'prom': False, 'loki_otlp': False, 'loki_sdk': False}
        deadline = time.time() + 60
        while time.time() < deadline and not all(found.values()):
            time.sleep(2)
            try:
                found['prom'] = bool(stack.prom_query('{__name__=~"ecosystem_canary_counter_.*"}'))
                dump = stack.loki_dump(t0 - 120 * 10**9, time.time_ns() + 60 * 10**9)
                found['loki_otlp'] = f'canary-{run}' in dump
                found['loki_sdk'] = f'canary-receipt-{run}' in dump
            except Exception as e:  # keep polling; record last error
                result['last_poll_error'] = repr(e)
        time.sleep(3)
        end = time.time_ns() + 60 * 10**9
        start = t0 - 120 * 10**9
        texts = {
            'collector_prometheus_exporter': isostack.http(stack.col_prom_url + '/metrics', raw=True)[1].decode(),
            'prometheus_federate': stack.prom_federate_text(),
            'prometheus_metadata': stack.prom_metadata_text(),
            'loki_query_range': stack.loki_dump(start, end),
            'loki_labels_and_values': stack.loki_labels_text(start, end),
            'collector_file_events': stack.events_text(),
        }
        leaks = []
        for field, tok in negative.items():
            for backend, text in texts.items():
                if tok in text:
                    leaks.append({'field': field, 'backend': backend})
        pos = {}
        for field, tok in positive.items():
            pos[field] = sorted(b for b, t in texts.items() if tok in t)
        result.update({
            'otlp_post_status': {'logs': st_logs, 'metrics': st_metrics},
            'arrival': found,
            'negative_fields': sorted(negative),
            'negative_count': len(negative),
            'backends_searched': {k: {'bytes': len(v)} for k, v in texts.items()},
            'leaks': leaks,
            'leak_count': len(leaks),
            'positive_controls_found_in': pos,
            # Publish only a sha256 prefix per canary: a raw value under a secret-like label (e.g. logs.attr.api_key)
            # trips the repository's gitleaks generic-api-key rule. Raw values stay in the private run root.
            'canary_sha256_prefix': {k: hashlib.sha256(v.encode()).hexdigest()[:12] for k, v in C.items()},
        })
        # Explicit field -> backends where the positive/boundary control must appear (the detection matrix).
        LOGS = {'loki_query_range', 'collector_file_events'}
        PROM = {'collector_prometheus_exporter', 'prometheus_federate'}
        expected = {'logs.resource.ecosystem.task.id(allowlisted)': LOGS, 'logs.attr.tool_name(allowlisted)': LOGS,
                    'sdk.configured_model(allowlisted-as-model)': LOGS, 'metrics.attr.model(allowlisted)': PROM,
                    'metrics.name(boundary)': PROM | {'prometheus_metadata'}}
        missing = {f: sorted(b - set(pos.get(f, []))) for f, b in expected.items() if b - set(pos.get(f, []))}
        result['positive_control_expected_backends'] = {f: sorted(b) for f, b in expected.items()}
        result['positive_control_missing'] = missing
        pos_ok = not missing and set(expected) == set(positive) and all(found.values())
        result['status'] = 'leak' if leaks else ('passed' if pos_ok else 'positive_control_missing')
        # retain the searched text privately for audit (synthetic only)
        (root / 'canaries.private.json').write_text(json.dumps(C, indent=2))
        (root / 'searched').mkdir(exist_ok=True)
        for k, v in texts.items():
            (root / 'searched' / f'{k}.txt').write_text(v)
    finally:
        stack.stop()
        result['stopped_at'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    Path(a.out).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: result.get(k) for k in ('mode', 'status', 'leak_count', 'negative_count', 'arrival', 'positive_controls_found_in', 'positive_control_missing')}, indent=1))
    return {'passed': 0, 'leak': 1}.get(result.get('status'), 2)


if __name__ == '__main__':
    sys.exit(main())
