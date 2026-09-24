#!/usr/bin/env python3
"""SDK receipt spool: full-disk, extended collector outage, expiry and backend-outage acceptance.

Runs inside an unprivileged user+mount namespace (re-execs itself with
`unshare --user --map-root-user --mount`) so the spool can be a size-limited tmpfs
without root. Uses the UNCHANGED write_observation() helper from
blueprints/us-equities/workers/native_worker.py (extracted by AST so the SDK import is
not needed) and an isolated collector + Loki (isostack.Stack, repository collector.yaml).

Phases: A baseline ingest; B collector stopped for >= --outage-s while the spool is
filled to ENOSPC; C collector restored, count replayed vs lost vs duplicated; D the
spool_expiry policy frees confirmed receipts and new writes succeed; E Loki stopped
longer than the Loki exporter retry window (max_elapsed_time 300s) while receipts
arrive, then restored; count Loki arrivals vs collector file/events exports.
"""
import argparse
import ast
import errno
import json
import os
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import isostack  # noqa: E402
import spool_expiry  # noqa: E402

HELPER = isostack.REPO / 'blueprints/us-equities/workers/native_worker.py'


def load_helper():
    src = HELPER.read_text()
    tree = ast.parse(src)
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'write_observation')
    code = ast.get_source_segment(src, fn)
    ns = {'json': json, 'os': os, 'uuid': uuid, 'Path': Path}
    exec(compile('from __future__ import annotations\n' + code, str(HELPER), 'exec'), ns)
    import hashlib
    return ns['write_observation'], hashlib.sha256(code.encode()).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def loki_ids(stack):
    d = json.loads(stack.loki_dump(time.time_ns() - 3 * 3600 * 10**9, time.time_ns() + 60 * 10**9,
                                   query='{service_name="codex-sdk-receipt"}'))
    counts = {}
    for s in d['data']['result']:
        oid = s['stream'].get('observation_id')
        if oid:
            counts[oid] = counts.get(oid, 0) + len(s['values'])
    return counts


def events_ids(stack):
    counts = {}
    for line in stack.events_text().splitlines():
        try:
            doc = json.loads(line)
        except Exception:
            continue
        for rl in doc.get('resourceLogs', []):
            for sl in rl.get('scopeLogs', []):
                for lr in sl.get('logRecords', []):
                    at = {x['key']: next(iter(x.get('value', {}).values()), None) for x in lr.get('attributes', [])}
                    oid = at.get('observation_id')
                    if oid:
                        counts[oid] = counts.get(oid, 0) + 1
    return counts


def wait_for(fn, ids, timeout):
    t = time.time()
    while time.time() - t < timeout:
        got = fn()
        if set(ids) <= set(got):
            return got, round(time.time() - t, 1)
        time.sleep(2)
    return fn(), None


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', required=True)
    ap.add_argument('--tmpfs-size', default='128k')
    ap.add_argument('--outage-s', type=int, default=180)
    ap.add_argument('--loki-outage-s', type=int, default=330)
    a = ap.parse_args()
    if os.environ.get('GW2_IN_NS') != '1':
        env = dict(os.environ, GW2_IN_NS='1')
        return subprocess.call(['unshare', '--user', '--map-root-user', '--mount', sys.executable, __file__, *sys.argv[1:]], env=env)
    write_observation, helper_sha = load_helper()
    base = Path.home() / '.cache/gap-wave2-20260923/observation-inference'
    root = Path(tempfile.mkdtemp(prefix='spool-outage-', dir=base))
    stack = isostack.Stack(root, components=('otelcol', 'loki'))
    spool = stack.spool
    subprocess.run(['mount', '-t', 'tmpfs', '-o', f'size={a.tmpfs_size},mode=0700', 'tmpfs', str(spool)], check=True)
    R = {'helper': str(HELPER.relative_to(isostack.REPO)), 'helper_function_sha256': helper_sha,
         'tmpfs_size': a.tmpfs_size, 'phases': {}, 'started_at': now()}

    def write(tag):
        res = {'status': 'completed', 'configured_model': f'fixture-{tag}', 'duration_ms': 1, 'usage_status': 'known',
               'usage': {'total': {'inputTokens': 1, 'outputTokens': 1, 'totalTokens': 2}}}
        before = {p.name for p in spool.iterdir()}
        try:
            write_observation(spool, res)
            new = {p.name for p in spool.iterdir()} - before
            return ('ok', next(iter(new))[:-5])
        except OSError as e:
            return ('enospc' if e.errno == errno.ENOSPC else f'oserror:{e.errno}', None)

    try:
        stack.start()
        # ---- A: baseline
        ids_a = [write('A')[1] for _ in range(5)]
        got, secs = wait_for(lambda: loki_ids(stack), ids_a, 60)
        R['phases']['A_baseline'] = {'written': 5, 'in_loki': sum(1 for i in ids_a if i in got), 'seconds_to_all': secs}
        # ---- B: collector down, fill spool
        t_stop = time.time()
        R['phases']['B_outage'] = {'collector_stopped_at': now(), 'collector_exit': stack.stop_one('otelcol')}
        ok_ids, outcomes, after_full = [], {}, 0
        for _ in range(2000):
            o, i = write('B')
            outcomes[o] = outcomes.get(o, 0) + 1
            if o == 'ok':
                ok_ids.append(i)
            else:
                after_full += 1
                if after_full >= 10:
                    break
        pend = [p.name for p in spool.iterdir() if p.name.endswith('.pending')]
        vfs = os.statvfs(spool)
        R['phases']['B_outage'].update({'write_outcomes': outcomes, 'written_ok': len(ok_ids), 'pending_leftovers': len(pend),
                                        'json_files_in_spool': sum(1 for p in spool.iterdir() if p.name.endswith('.json')),
                                        'free_bytes_when_full': vfs.f_bavail * vfs.f_frsize,
                                        'invalid_json_files': sum(1 for p in spool.iterdir() if p.name.endswith('.json') and not _valid(p))})
        while time.time() - t_stop < a.outage_s:
            time.sleep(5)
        R['phases']['B_outage']['collector_down_s'] = round(time.time() - t_stop, 1)
        # ---- C: restore collector
        stack.start_one('otelcol')
        R['phases']['C_restore'] = {'collector_started_at': now()}
        want = ids_a + ok_ids
        got, secs = wait_for(lambda: loki_ids(stack), want, 120)
        ev = events_ids(stack)
        R['phases']['C_restore'].update({
            'expected_distinct': len(want), 'loki_distinct': sum(1 for i in want if i in got),
            'lost_in_loki': [i for i in want if i not in got], 'loki_duplicates': {i: c for i, c in got.items() if c > 1},
            'events_file_distinct': sum(1 for i in want if i in ev), 'events_duplicates': {i: c for i, c in ev.items() if c > 1},
            'seconds_to_all_replayed': secs})
        # ---- D: expiry policy frees confirmed receipts, then writes succeed
        exp = spool_expiry.run(str(spool), stack.loki_url, ttl_s=10**9, min_free_bytes=64 * 1024)
        post = [write('D') for _ in range(3)]
        R['phases']['D_expiry'] = {'expiry': {k: v for k, v in exp.items() if k != 'deleted_names'},
                                   'post_expiry_writes': [o for o, _ in post]}
        ids_d = [i for o, i in post if o == 'ok']
        got, secs = wait_for(lambda: loki_ids(stack), ids_d, 60)
        R['phases']['D_expiry']['post_expiry_in_loki'] = sum(1 for i in ids_d if i in got)
        # ---- E: Loki down beyond exporter retry window
        t_l = time.time()
        R['phases']['E_backend_outage'] = {'loki_stopped_at': now(), 'loki_exit': stack.stop_one('loki')}
        time.sleep(2)
        ids_e = []
        for _ in range(8):
            o, i = write('E')
            if o == 'ok':
                ids_e.append(i)
        ev_wait, _ = wait_for(lambda: events_ids(stack), ids_e, 30)
        R['phases']['E_backend_outage']['written_ok'] = len(ids_e)
        R['phases']['E_backend_outage']['in_events_file_during_outage'] = sum(1 for i in ids_e if i in ev_wait)
        while time.time() - t_l < a.loki_outage_s:
            time.sleep(5)
        R['phases']['E_backend_outage']['loki_down_s'] = round(time.time() - t_l, 1)
        stack.start_one('loki')
        R['phases']['E_backend_outage']['loki_restarted_at'] = now()
        got, secs = wait_for(lambda: loki_ids(stack), ids_e, 120)
        R['phases']['E_backend_outage'].update({
            'in_loki_after_restore': sum(1 for i in ids_e if i in got), 'lost_in_loki': len([i for i in ids_e if i not in got]),
            'still_in_spool': sum(1 for i in ids_e if (spool / f'{i}.json').exists()),
            'seconds_to_all': secs})
        R['phases']['E_backend_outage']['earlier_receipts_still_in_loki'] = sum(1 for i in ids_a + ok_ids if i in got)
        log = (stack.log_dir / 'otelcol.log').read_text(errors='replace')
        R['collector_log_signals'] = {k: log.count(k) for k in ('Exporting failed', 'Dropping data', 'dropped', 'no more retries left', 'max elapsed time', 'Retrying')}
        R['collector_log_drop_lines'] = [l[:400] for l in log.splitlines() if 'ropp' in l or 'no more retries' in l or 'max elapsed' in l][:5]
    except Exception as e:
        R['error'] = f'{type(e).__name__}: {e}'
        raise
    finally:
        stack.stop()
        subprocess.run(['umount', str(spool)])
        R['stopped_at'] = now()
        Path(a.out).write_text(json.dumps(R, indent=2) + '\n')
    print(json.dumps(R['phases'], indent=1)[:4000])
    return 0


def _valid(p):
    try:
        json.loads(p.read_text())
        return True
    except Exception:
        return False


if __name__ == '__main__':
    sys.exit(main())
