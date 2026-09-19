#!/usr/bin/env python3
"""Publish bounded public checkpoint metadata to local Loki; no prompts or secrets."""
import argparse
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
import time
import urllib.request

MAX_BYTES = 2_000_000
SOURCES = {
    'foundation': ('catalogs/us-equities/convergence-program/foundation.json', 'repositories'),
    'trading': ('catalogs/us-equities/convergence-program/trading.json', 'entries'),
    'hosting': ('catalogs/us-equities/convergence-program/hosting.json', 'candidates'),
}


def read(root, relative):
    path = root / relative
    if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('source must remain inside the public repository')
    if path.stat().st_size > MAX_BYTES:
        raise ValueError('source exceeds size limit')
    return json.loads(path.read_text())


def token(value, pattern=r'[A-Za-z0-9_. /+()\-]{1,160}'):
    if not isinstance(value, str) or not re.fullmatch(pattern, value):
        raise ValueError('invalid public metadata token')
    return value


def stamp(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('checkpoint timestamp requires timezone')
    return parsed.astimezone(timezone.utc).isoformat()


def snapshot(root):
    root = Path(root)
    plan = read(root, 'blueprints/us-equities/convergence-program/plan.json')
    state = read(root, 'observability/grand-dashboard/state.json')
    updated = stamp(state['recorded_at_utc'])
    rows = []

    def add(kind, entity, title, status, ref, number=0):
        rows.append(dict(record_kind=kind, entity_id=token(entity), title=token(title),
                         state=token(status), evidence_ref=ref,
                         source_updated_at=updated, number=number))

    for row in state['lanes'] + state['gates'] + state['workers']:
        kind = token(row['kind'], r'lane|gate|worker')
        ref = row['evidence_ref']
        if not isinstance(ref, str) or not re.fullmatch(r'[A-Za-z0-9_./-]{1,200}', ref) or '..' in ref:
            raise ValueError('invalid evidence reference')
        target = root / ref
        if Path(ref).is_absolute() or target.is_symlink() or not target.resolve().is_relative_to(root.resolve()) or not target.is_file():
            raise ValueError('missing evidence reference')
        add(kind, row['id'], row['title'], row['state'], ref)
    for wave in plan['waves']:
        add('wave', wave['id'], wave['id'].replace('_', ' '), wave['state'],
            'blueprints/us-equities/convergence-program/plan.json')
    for group, (relative, key) in SOURCES.items():
        data = read(root, relative)
        for item in data[key]:
            repo = item['repository'].removeprefix('https://github.com/').rstrip('/')
            token(repo, r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+')
            decision = item.get('decision', item.get('selection'))
            if isinstance(decision, dict):
                decision = decision['status']
            add('decision', group + '/' + repo, repo, decision, relative)
    evidence = read(root, 'manifests/evidence.json')
    experiments_path = 'blueprints/us-equities/historical-simulation/receipt.json'
    experiments = read(root, experiments_path)
    labels = {'one_zero':'1x target / zero costs','one_stress':'1x target / stressed costs',
              'two_zero':'2x target / zero costs','two_stress':'2x target / stressed costs',
              'adaptive_stress':'Adaptive reduction / stressed costs','over_limit':'Over-limit rejection'}
    for case in experiments['cases']:
        add('experiment', 'sim/' + case['id'], labels.get(case['id'],case['id'].replace('_', ' ')),
            'rejected / no fills' if case['id']=='over_limit' else 'completed / historical stress', experiments_path)
        for source, target in [('native_end_equity_usd','equity_usd'),('fees_usd','fees_usd'),('max_observed_drawdown','drawdown_pct')]:
            value = token(case[source], r'-?[0-9]{1,14}(?:\.[0-9]{1,30})?')
            display = Decimal(value)*100 if target == 'drawdown_pct' else Decimal(value)
            rows[-1][target] = format(display.quantize(Decimal('0.01')), 'f')
        for source in ['fill_count','margin_call_count']:
            value = case[source]
            if type(value) is not int or not 0 <= value <= 100000:
                raise ValueError('invalid experiment count')
            rows[-1][source] = value
    add('summary', 'receipts', 'Registered evidence receipts', 'recorded', 'manifests/evidence.json', len(evidence['receipts']))
    add('summary', 'decisions', 'Decisions examined this wave', 'recorded', 'blueprints/us-equities/convergence-program/plan.json', sum(r['record_kind'] == 'decision' for r in rows))
    stars = read(root, 'catalogs/us-equities/convergence-program/public-stars-refresh.json')
    count = stars['current_count']
    if type(count) is not int or count < 0 or count != len(stars['repositories']):
        raise ValueError('public star count mismatch')
    add('summary', 'stars', 'Public stars enumerated', 'identity audit', 'catalogs/us-equities/convergence-program/public-stars-refresh.json', count)
    add('summary', 'snapshot', 'Snapshot marker', 'recorded', 'observability/grand-dashboard/state.json')
    if len(rows) > 80 or len({r['entity_id'] for r in rows}) != len(rows):
        raise ValueError('too many or duplicate dashboard entities')
    return rows


def payload(rows, now_ns):
    streams = {}
    for i, row in enumerate(rows):
        kind = row['record_kind']
        event = dict(row, observed_unix=now_ns / 1e9)
        streams.setdefault(kind, []).append([str(now_ns + i), json.dumps(event, separators=(',', ':'))])
    return {'streams': [{'stream': {'service_name': 'agent-stack-progress', 'record_kind': kind}, 'values': values}
                        for kind, values in streams.items()]}


def publish(root, cache, now_ns=None):
    rows = snapshot(root)
    digest = hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()
    now_ns = time.time_ns() if now_ns is None else now_ns
    cache = Path(cache)
    previous = json.loads(cache.read_text()) if cache.exists() else {}
    # Repeat a bounded heartbeat every ten minutes, or immediately on source change.
    if previous.get('digest') == digest and 0 <= now_ns - previous.get('sent_ns', 0) < 600_000_000_000:
        return {'status': 'unchanged', 'records': len(rows)}
    request = urllib.request.Request('http://127.0.0.1:13100/loki/api/v1/push',
        json.dumps(payload(rows, now_ns)).encode(), {'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=10) as response:
        if response.status != 204:
            raise ValueError('Loki did not acknowledge ingestion')
    cache.parent.mkdir(parents=True, exist_ok=True)
    temporary = cache.with_suffix('.tmp')
    temporary.write_text(json.dumps({'digest': digest, 'sent_ns': now_ns}) + '\n')
    temporary.replace(cache)
    return {'status': 'published', 'records': len(rows), 'sha256': digest}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--cache', type=Path)
    args = parser.parse_args()
    if args.cache:
        print(json.dumps(publish(args.repo, args.cache)))
    else:
        print(json.dumps(snapshot(args.repo), indent=2))


if __name__ == '__main__':
    main()
