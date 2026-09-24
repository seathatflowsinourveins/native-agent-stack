#!/usr/bin/env python3
"""Read-only leak probe for gap 3: did the isolated child session also export to the LIVE pipeline?

Issues only HTTP GET query_range requests to the live Loki (default http://127.0.0.1:13100); it
writes nothing and changes no service. First detector (preregistered): the repository collector
config keeps session.id on logs, so a child that exported there would appear under structured
metadata session_id; positive control = the same query for a session known to export live in the
same window. Prints counts only.

Observed 2026-09-23: the live Loki records carry no session_id field at all (label/field discovery in
raw/3-live-loki-probe.txt), so the session.id query has no detection power there. --signature adds a
second detector: the child's exact api_request token counts and model, which the same collector
configuration preserved in the isolated Loki; live api_request events in the window demonstrate the
query path returns such events.
"""
import argparse
import json
import sys
import urllib.parse
import urllib.request
from datetime import datetime


def hits(loki, sid, start, end):
    q = '{service_name=~".+"} | session_id = "%s"' % sid
    url = loki + '/loki/api/v1/query_range?' + urllib.parse.urlencode(
        {'query': q, 'start': str(start), 'end': str(end), 'limit': '1000', 'direction': 'forward'})
    with urllib.request.urlopen(url, timeout=20) as r:
        body = json.loads(r.read())
    return sum(len(s['values']) for s in body['data']['result']), body['status']


def signature_hits(loki, start, end, sig):
    """Count live claude-code api_request events and those matching the child's exact token signature."""
    q = '{service_name="claude-code"} | event_name = "api_request"'
    url = loki + '/loki/api/v1/query_range?' + urllib.parse.urlencode(
        {'query': q, 'start': str(start), 'end': str(end), 'limit': '5000', 'direction': 'forward'})
    with urllib.request.urlopen(url, timeout=30) as r:
        body = json.loads(r.read())
    total, match, models = 0, 0, {}
    for s in body['data']['result']:
        st = s['stream']
        n = len(s['values'])
        total += n
        models[st.get('model', '?')] = models.get(st.get('model', '?'), 0) + n
        if all(str(st.get(k)) == str(v) for k, v in sig.items()):
            match += n
    return total, match, models


def ns(iso):
    return int(datetime.fromisoformat(iso.replace('Z', '+00:00')).timestamp() * 1e9)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--loki', default='http://127.0.0.1:13100')
    ap.add_argument('--child', required=True)
    ap.add_argument('--control', required=True)
    ap.add_argument('--start', required=True)
    ap.add_argument('--end', required=True)
    ap.add_argument('--signature', help='JSON of exact api_request fields of the child, e.g. token counts and model')
    a = ap.parse_args()
    s, e = ns(a.start), ns(a.end)
    c, cs = hits(a.loki, a.child, s, e)
    p, ps = hits(a.loki, a.control, s, e)
    out = {'method': 'read-only GET /loki/api/v1/query_range on the live Loki', 'window': [a.start, a.end],
           'child_session_hits': c, 'child_query_status': cs, 'positive_control_hits': p, 'control_query_status': ps,
           'detection_demonstrated': p > 0, 'child_absent': c == 0}
    if a.signature:
        sig = json.loads(a.signature)
        t, m, models = signature_hits(a.loki, s, e, sig)
        out.update({'signature': sig, 'live_api_request_events_in_window': t, 'live_events_matching_child_signature': m,
                    'live_api_request_models_in_window': models,
                    'signature_detection_demonstrated': t > 0, 'child_signature_absent': m == 0})
    print(json.dumps(out, indent=1))
    if a.signature:
        return 0 if (out['signature_detection_demonstrated'] and out['child_signature_absent']) else 1
    return 0 if (p > 0 and c == 0) else 1


if __name__ == '__main__':
    sys.exit(main())
