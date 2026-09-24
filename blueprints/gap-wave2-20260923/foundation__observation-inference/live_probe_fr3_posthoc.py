#!/usr/bin/env python3
"""POST-HOC (not preregistered) follow-up to live_probe_fr3.py, written after its Prometheus arm failed.

The preregistered Prometheus detector counted series with samples in the window; cumulative counters from
earlier haiku use keep being scraped, so that detector cannot separate old series from new usage, and its
exact-name control ('claude-opus-5-5') missed the live label 'claude-opus-5-5[1m]'. This descriptive check
asks instead whether any haiku-model series changed value or first appeared inside the window, with the
opus[1m] series as the change control. Read-only GETs to live Prometheus. It does not change the outcome.
"""
import argparse
import json
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone

METRIC = 'ecosystem_claude_code_token_usage_tokens_total'


def get(prom, path, params):
    with urllib.request.urlopen(prom + path + '?' + urllib.parse.urlencode(params), timeout=30) as r:
        return json.loads(r.read())


def ts(iso):
    return datetime.fromisoformat(iso.replace('Z', '+00:00')).timestamp()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--prom', default='http://127.0.0.1:19090')
    ap.add_argument('--start', required=True)
    ap.add_argument('--end', required=True)
    ap.add_argument('--lookback-s', type=int, default=3600, help='range before the window used to test first appearance')
    a = ap.parse_args()
    s, e = ts(a.start), ts(a.end)
    out = {'label': 'post-hoc, not preregistered; descriptive only', 'window': [a.start, a.end]}
    for name, sel in (('haiku', '{model=~".*haiku.*"}'), ('control_opus_1m', '{model="claude-opus-5-5[1m]"}')):
        body = get(a.prom, '/api/v1/query_range', {'query': METRIC + sel, 'start': str(s - a.lookback_s), 'end': str(e), 'step': '15'})
        series = body['data']['result']
        changed = appeared = 0
        delta_by_type = {}
        detail = []
        for r in series:
            vals = [(float(t), float(v)) for t, v in r['values']]
            before = [v for t, v in vals if t < s]
            inside = [v for t, v in vals if s <= t <= e]
            inside_t = [t for t, v in vals if s <= t <= e]
            if not inside:
                continue
            if not before:
                appeared += 1
            base = before[-1] if before else inside[0]
            d = max(inside) - base
            if d > 0:
                changed += 1
                k = r['metric'].get('type', '?')
                delta_by_type[k] = delta_by_type.get(k, 0) + d
            if (d > 0 or not before) and name == 'haiku':
                lab = {k: v for k, v in r['metric'].items() if k not in ('__name__',)}
                if lab.get('instance') not in (None, 'unscoped'):
                    lab['instance'] = '<live-instance-id>'
                detail.append({'labels': lab, 'first_sample_in_window': datetime.fromtimestamp(inside_t[0], timezone.utc).isoformat(),
                               'value_first_in_window': inside[0], 'value_last_in_window': inside[-1],
                               'last_value_before_window': before[-1] if before else None})
        out[name] = {'status': body['status'], 'series_returned': len(series), 'series_changed_in_window': changed,
                     'series_first_seen_in_window': appeared, 'delta_by_type': delta_by_type}
        if name == 'haiku':
            out[name]['changed_or_new_series'] = detail
    out['change_detection_demonstrated'] = out['control_opus_1m']['series_changed_in_window'] > 0
    out['haiku_change_or_new_series_in_window'] = out['haiku']['series_changed_in_window'] + out['haiku']['series_first_seen_in_window']
    child = {'input': 10.0, 'output': 99.0, 'cacheCreation': 6575.0}
    out['child_value_match'] = [x for x in out['haiku']['changed_or_new_series']
                                if child.get(x['labels'].get('type')) in (x['value_first_in_window'], x['value_last_in_window'],
                                    x['value_last_in_window'] - (x['last_value_before_window'] or 0))]
    print(json.dumps(out, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
