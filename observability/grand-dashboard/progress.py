#!/usr/bin/env python3
"""Publish bounded public checkpoint metadata to local Loki; no prompts or secrets."""
import argparse
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import subprocess
import time
import urllib.request

MAX_BYTES = 2_000_000
# Includes catalog checkpoints and up to HISTORY_LIMIT native runs plus summary.
# The combined foundation/paper inventory has already exceeded the former 80 rows.
MAX_ENTITIES = 128
HISTORY_BYTES = 131_072
HISTORY_LIMIT = 10
HISTORY_STATUSES = ('not_started', 'running', 'succeeded', 'failed', 'aborted',
                    'queued', 'waiting', 'rejected', 'partially_succeeded')
WORKFLOW_EVIDENCE = 'adoption/paired/README.md'
SOURCES = {
    'foundation': ('catalogs/us-equities/convergence-program/foundation.json', 'repositories'),
    'trading': ('catalogs/us-equities/convergence-program/trading.json', 'entries'),
    'hosting': ('catalogs/us-equities/convergence-program/hosting.json', 'candidates'),
}


def read(root, relative):
    if not isinstance(relative, str) or not re.fullmatch(r'[A-Za-z0-9_./-]{1,200}', relative) or relative.startswith('/') or '..' in relative:
        raise ValueError('invalid public source reference')
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


def history_output(command, home, timeout=5):
    """Bound the native CLI's stdout and lifetime; never retain raw stderr."""
    output = bytearray()
    deadline = time.monotonic() + timeout
    with subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                          stderr=subprocess.DEVNULL, cwd=home,
                          env={'HOME': str(Path.home()), 'PATH': '/usr/bin:/bin', 'TZ': 'UTC'}) as process:
        try:
            with selectors.DefaultSelector() as reader:
                reader.register(process.stdout, selectors.EVENT_READ)
                while reader.get_map():
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError('native history timed out')
                    for key, _ in reader.select(remaining):
                        chunk = os.read(key.fileobj.fileno(), 8192)
                        if not chunk:
                            reader.unregister(key.fileobj)
                            break
                        output.extend(chunk)
                        if len(output) > HISTORY_BYTES:
                            raise ValueError('native history output exceeds limit')
            try:
                result = process.wait(timeout=max(.001, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                raise TimeoutError('native history timed out') from None
            if result:
                raise ValueError('native history failed')
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
    return json.loads(output)


def workflow_unknown(state):
    return [dict(record_kind='workflow', entity_id='workflow/history',
                 title='Research pair / last 10 runs within 30 days', state=state,
                 evidence_ref=WORKFLOW_EVIDENCE, source_updated_at='unknown')]


def workflow_rows(entries):
    """Accept only the fixed native history scope; no IDs, parameters or errors."""
    if not isinstance(entries, list) or len(entries) > HISTORY_LIMIT:
        raise ValueError('invalid native history result count')
    rows = workflow_unknown('observed / bounded local history' if entries else 'no history / last 30 days')
    summary = rows[0]
    summary['history_count'] = len(entries)
    summary.update({status + '_count': 0 for status in HISTORY_STATUSES})
    known_times = []
    for i, entry in enumerate(entries, 1):
        if not isinstance(entry, dict) or entry.get('name') != 'research-pair' or entry.get('status') not in HISTORY_STATUSES:
            raise ValueError('unexpected native history scope or status')
        times = {}
        for native, field in [('startedAt', 'started_at'), ('finishedAt', 'finished_at')]:
            value = entry.get(native)
            if value is not None and value != '':
                if not isinstance(value, str) or len(value) > 40:
                    raise ValueError('invalid native timestamp')
                times[field] = stamp(value)
        duration = None
        if len(times) == 2:
            duration = (datetime.fromisoformat(times['finished_at']) - datetime.fromisoformat(times['started_at'])).total_seconds()
            if duration < 0:
                raise ValueError('native finish precedes start')
        updated = times.get('finished_at', times.get('started_at', 'unknown'))
        known_times.extend(times.values())
        row = dict(record_kind='workflow', entity_id=f'workflow/recent-{i}',
                   title=f'Research pair / recent entry {i}', state=entry['status'],
                   evidence_ref=WORKFLOW_EVIDENCE, source_updated_at=updated,
                   started_at=times.get('started_at', 'unknown'), finished_at=times.get('finished_at', 'unknown'))
        if duration is not None:
            row['duration_seconds'] = duration
        summary[entry['status'] + '_count'] += 1
        rows.append(row)
    if known_times:
        summary['source_updated_at'] = max(known_times)
    return rows


def workflow_snapshot(dagu_bin=None, dagu_home=None):
    if dagu_bin is None and dagu_home is None:
        return workflow_unknown('not configured / unknown')
    try:
        binary, home = Path(dagu_bin), Path(dagu_home)
        if not binary.is_absolute() or not home.is_absolute() or not binary.is_file() or not home.is_dir():
            raise ValueError('invalid native history paths')
        command = [str(binary), 'history', 'research-pair', '--context', 'local',
                   '--dagu-home', str(home), '--format', 'json', '--last', '30d', '--limit', str(HISTORY_LIMIT)]
        return workflow_rows(history_output(command, home))
    except (OSError, ValueError, TypeError, TimeoutError):
        # Failure must replace previous successful rows in the same generation.
        return workflow_unknown('unavailable / native history failed')


def snapshot(root, dagu_bin=None, dagu_home=None):
    root = Path(root)
    state = read(root, 'observability/grand-dashboard/state.json')
    plan_path = state.get('plan_ref', 'blueprints/us-equities/convergence-program/plan.json')
    plan = read(root, plan_path)
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
            plan_path)
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
    add('summary', 'decisions', 'Source-reviewed repository decisions', 'recorded', 'blueprints/us-equities/convergence-program/plan.json', sum(r['record_kind'] == 'decision' for r in rows))
    stars_path = state.get('stars_ref', 'catalogs/us-equities/convergence-program/public-stars-refresh.json')
    stars = read(root, stars_path)
    count = stars['current_count']
    if type(count) is not int or count < 0 or count != len(stars['repositories']):
        raise ValueError('public star count mismatch')
    add('summary', 'stars', 'Public stars enumerated', 'identity audit', stars_path, count)
    add('summary', 'snapshot', 'Snapshot marker', 'recorded', 'observability/grand-dashboard/state.json')
    rows.extend(workflow_snapshot(dagu_bin, dagu_home))
    if len(rows) > MAX_ENTITIES:
        raise ValueError('too many dashboard entities')
    if len({r['entity_id'] for r in rows}) != len(rows):
        raise ValueError('duplicate dashboard entities')
    return rows


def payload(rows, now_ns):
    streams = {}
    for i, row in enumerate(rows):
        kind = row['record_kind']
        event = dict(row, observed_unix=now_ns / 1e9)
        streams.setdefault(kind, []).append([str(now_ns + i), json.dumps(event, separators=(',', ':'))])
    return {'streams': [{'stream': {'service_name': 'agent-stack-progress', 'record_kind': kind}, 'values': values}
                        for kind, values in streams.items()]}


def publish(root, cache, now_ns=None, dagu_bin=None, dagu_home=None):
    rows = snapshot(root, dagu_bin, dagu_home)
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
    parser.add_argument('--dagu-bin', type=Path)
    parser.add_argument('--dagu-home', type=Path)
    args = parser.parse_args()
    if (args.dagu_bin is None) != (args.dagu_home is None):
        parser.error('--dagu-bin and --dagu-home must be supplied together')
    if args.cache:
        print(json.dumps(publish(args.repo, args.cache, dagu_bin=args.dagu_bin, dagu_home=args.dagu_home)))
    else:
        print(json.dumps(snapshot(args.repo, args.dagu_bin, args.dagu_home), indent=2))


if __name__ == '__main__':
    main()
