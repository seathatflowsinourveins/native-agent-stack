#!/usr/bin/env python3
"""Fix-round-3 live-leak probe for gap 3 with positive controls (read-only HTTP GETs only).

Preregistered in preregistrations.json fix_round_3.gaps.3 before this script ran.
(a) Live Prometheus: per-model count of ecosystem_claude_code token-usage series that have samples in the
    window. Child detector = any haiku-model series; positive control = model claude-opus-5-5 > 0.
(b) Live Loki: the api_request signature matcher from live_session_probe.py (imported unchanged). Positive
    control = the field values of the live api_request stream whose first entry is earliest in the window;
    the matcher must find >= 1 event for it. Child detector = the child's exact signature, must be 0.
Writes nothing to either store and changes no service.
"""
import argparse
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import live_session_probe as lsp  # noqa: E402

SIG_FIELDS = ('model', 'input_tokens', 'output_tokens', 'cache_creation_tokens', 'cache_read_tokens')


def get(url, timeout=30):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read())


def prom_arm(prom, start, end):
    names = [n for n in get(prom + '/api/v1/label/__name__/values')['data'] if n.startswith('ecosystem_claude_code_token_usage')]
    out = {'metric_names': names, 'per_metric': {}}
    rng = int(end - start)
    haiku = control = 0
    for n in names:
        q = 'count by (model) (count_over_time({__name__="%s"}[%ds]))' % (n, rng)
        body = get(prom + '/api/v1/query?' + urllib.parse.urlencode({'query': q, 'time': str(end)}))
        per = {r['metric'].get('model', '?'): int(float(r['value'][1])) for r in body['data']['result']}
        out['per_metric'][n] = {'status': body['status'], 'series_with_samples_by_model': per}
        haiku += sum(v for m, v in per.items() if 'haiku' in m)
        control += per.get('claude-opus-5-5', 0)
    out.update({'haiku_series_with_samples': haiku, 'control_opus_series_with_samples': control,
                'detection_demonstrated': control > 0, 'child_absent': haiku == 0})
    return out


def loki_arm(loki, start_ns, end_ns, child_sig):
    q = '{service_name="claude-code"} | event_name = "api_request"'
    body = get(loki + '/loki/api/v1/query_range?' + urllib.parse.urlencode(
        {'query': q, 'start': str(start_ns), 'end': str(end_ns), 'limit': '5000', 'direction': 'forward'}))
    streams = [s for s in body['data']['result'] if s['values']]
    first = min(streams, key=lambda s: min(int(v[0]) for v in s['values']))
    control_sig = {k: first['stream'].get(k) for k in SIG_FIELDS}
    t_c, m_c, _ = lsp.signature_hits(loki, start_ns, end_ns, control_sig)
    t_x, m_x, models = lsp.signature_hits(loki, start_ns, end_ns, child_sig)
    return {'control_signature': control_sig, 'control_choice': 'stream whose first entry is earliest in the window',
            'events_in_window': t_x, 'models_in_window': models,
            'control_signature_matches': m_c, 'child_signature': child_sig, 'child_signature_matches': m_x,
            'detection_demonstrated': m_c >= 1, 'child_absent': m_x == 0}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--prom', default='http://127.0.0.1:19090')
    ap.add_argument('--loki', default='http://127.0.0.1:13100')
    ap.add_argument('--start', required=True)
    ap.add_argument('--end', required=True)
    ap.add_argument('--prom-end', required=True, help='end of the Prometheus window (export/scrape slack)')
    ap.add_argument('--child-signature', required=True)
    a = ap.parse_args()
    s, e, pe = lsp.ns(a.start), lsp.ns(a.end), lsp.ns(a.prom_end)
    out = {'method': 'read-only GETs: Prometheus /api/v1/label/__name__/values and /api/v1/query; Loki /loki/api/v1/query_range',
           'loki_window': [a.start, a.end], 'prom_window': [a.start, a.prom_end]}
    out['prometheus'] = prom_arm(a.prom, s / 1e9, pe / 1e9)
    out['loki'] = loki_arm(a.loki, s, e, json.loads(a.child_signature))
    p, l = out['prometheus'], out['loki']
    out['pass'] = bool(p['detection_demonstrated'] and p['child_absent'] and l['detection_demonstrated'] and l['child_absent'])
    print(json.dumps(out, indent=1))
    return 0 if out['pass'] else 1


if __name__ == '__main__':
    sys.exit(main())
