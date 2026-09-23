#!/usr/bin/env python3
"""Synthetic Alertmanager -> ntfy notification latency distribution (isolated stack).

Starts isolated Alertmanager 0.34.1 and ntfy 2.28.0 (isostack.Stack) rendered from the
repository templates (route group_wait 5s, group_interval 30s; ntfy alertmanager template
override), subscribes to the ntfy topic's JSON stream, posts N synthetic alerts with
distinct alertnames (one new group each) through the Alertmanager v2 API, then resolves
them all and records firing and resolved latency = ntfy stream arrival - alert POST.
Both timestamps come from this process's monotonic clock; ntfy's own 'time' field is
whole seconds and is recorded only as a cross-check.
"""
import argparse
import json
import statistics
import sys
import tempfile
import threading
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import isostack  # noqa: E402


def pct(xs, p):
    xs = sorted(xs)
    if not xs:
        return None
    k = (len(xs) - 1) * p
    f = int(k)
    c = min(f + 1, len(xs) - 1)
    return xs[f] + (xs[c] - xs[f]) * (k - f)


def summary(xs):
    if not xs:
        return {'n': 0}
    return {'n': len(xs), 'min_s': round(min(xs), 3), 'median_s': round(statistics.median(xs), 3),
            'p90_s': round(pct(xs, 0.9), 3), 'max_s': round(max(xs), 3), 'mean_s': round(statistics.mean(xs), 3),
            'stdev_s': round(statistics.pstdev(xs), 3)}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('-n', type=int, default=20)
    ap.add_argument('--spacing', type=float, default=1.0)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    base = Path.home() / '.cache/gap-wave2-20260923/observation-inference'
    base.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix='alert-latency-', dir=base))
    stack = isostack.Stack(root, components=('alertmanager', 'ntfy'))
    run = datetime.now(timezone.utc).strftime('%H%M%S')
    arrivals = []  # (monotonic, message)
    stop = threading.Event()
    result = {'n_requested': a.n, 'spacing_s': a.spacing, 'started_at': datetime.now(timezone.utc).isoformat()}

    def listen():
        req = urllib.request.Request(stack.ntfy_url + '/ecosystem-alerts/json')
        with urllib.request.urlopen(req, timeout=300) as r:
            for line in r:
                t = time.monotonic()
                if stop.is_set():
                    return
                try:
                    m = json.loads(line)
                except Exception:
                    continue
                if m.get('event') == 'message':
                    arrivals.append((t, time.time(), m))

    try:
        stack.start()
        th = threading.Thread(target=listen, daemon=True)
        th.start()
        time.sleep(1.0)  # let the subscription open
        posted = {}
        names = [f'SyntheticLatency{run}N{i:02d}' for i in range(a.n)]
        for name in names:
            now = datetime.now(timezone.utc)
            alert = [{'labels': {'alertname': name, 'job': 'latency-fixture', 'scope': 'synthetic', 'severity': 'info'},
                      'annotations': {'summary': 'Synthetic latency fixture; no service affected.'},
                      'startsAt': now.isoformat(), 'generatorURL': 'http://127.0.0.1/synthetic'}]
            t = time.monotonic()
            st, _ = isostack.http(stack.am_url + '/api/v2/alerts', alert)
            posted[name] = {'fire_post_mono': t, 'fire_http': st, 'starts': now}
            time.sleep(a.spacing)
        # wait for firing notifications
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline and sum(1 for _, _, m in arrivals if 'Alert: ' in m.get('title', '')) < a.n:
            time.sleep(0.2)
        # resolve all at once
        t_res = time.monotonic()
        now = datetime.now(timezone.utc)
        for name in names:
            alert = [{'labels': {'alertname': name, 'job': 'latency-fixture', 'scope': 'synthetic', 'severity': 'info'},
                      'annotations': {'summary': 'Synthetic latency fixture; no service affected.'},
                      'startsAt': posted[name]['starts'].isoformat(), 'endsAt': now.isoformat(),
                      'generatorURL': 'http://127.0.0.1/synthetic'}]
            posted[name]['resolve_post_mono'] = time.monotonic()  # taken before sending, as for firing
            st, _ = isostack.http(stack.am_url + '/api/v2/alerts', alert)
            posted[name]['resolve_http'] = st
        deadline = time.monotonic() + 75
        while time.monotonic() < deadline and sum(1 for _, _, m in arrivals if 'Resolved: ' in m.get('title', '')) < a.n:
            time.sleep(0.2)
        fire, res, rows = [], [], []
        for name in names:
            f = [x for x in arrivals if x[2].get('title', '').strip().endswith('Alert: ' + name)]
            r = [x for x in arrivals if x[2].get('title', '').strip().endswith('Resolved: ' + name)]
            row = {'alertname': name, 'fire_http': posted[name]['fire_http'], 'resolve_http': posted[name].get('resolve_http'),
                   'fire_notifications': len(f), 'resolved_notifications': len(r)}
            if f:
                row['fire_latency_s'] = round(f[0][0] - posted[name]['fire_post_mono'], 3)
                fire.append(row['fire_latency_s'])
            if r:
                row['resolve_latency_s'] = round(r[0][0] - posted[name]['resolve_post_mono'], 3)
                res.append(row['resolve_latency_s'])
            rows.append(row)
        sample = next((m for _, _, m in arrivals if 'Alert: ' in m.get('title', '')), None)
        result.update({
            'route': {'group_wait': '5s', 'group_interval': '30s', 'source': 'observability/backends/templates/ecosystem-alertmanager.yml.example'},
            'firing': summary(fire), 'resolved': summary(res),
            'fire_delivered': len(fire), 'resolved_delivered': len(res),
            'fire_lost': a.n - len(fire), 'resolved_lost': a.n - len(res),
            'total_messages_seen': len(arrivals), 'rows': rows,
            'sample_firing_message': {k: sample.get(k) for k in ('title', 'message')} if sample else None,
            'resolve_all_posted_over_s': round(max(p['resolve_post_mono'] for p in posted.values()) - t_res, 3),
        })
    finally:
        stop.set()
        stack.stop()
        result['stopped_at'] = datetime.now(timezone.utc).isoformat()
    Path(a.out).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: result.get(k) for k in ('firing', 'resolved', 'fire_lost', 'resolved_lost')}, indent=1))
    return 0 if result.get('fire_lost') == 0 and result.get('resolved_lost') == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
