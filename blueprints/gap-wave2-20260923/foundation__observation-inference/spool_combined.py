#!/usr/bin/env python3
"""Fix-round gap-4 arm: overlapping collector and Loki outages with the UNCHANGED collector config.

Timeline (seconds from t0): 0 collector stopped; 5 write 8 receipts (spool only); 60 Loki stopped;
180 collector restarted while Loki is still down (file_log replays into the exporter queue);
240 Loki restarted; then wait up to 150 s and count receipts in Loki / collector file/events.
Same isolation as spool_outage.py (unprivileged user+mount namespace, 128 KiB tmpfs spool,
unchanged write_observation() helper, isolated collector + Loki).
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import isostack  # noqa: E402
from spool_outage import load_helper, loki_ids, events_ids, wait_for, now  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    if os.environ.get('GW2_IN_NS') != '1':
        return subprocess.call(['unshare', '--user', '--map-root-user', '--mount', sys.executable, __file__, *sys.argv[1:]],
                               env=dict(os.environ, GW2_IN_NS='1'))
    write_observation, helper_sha = load_helper()
    base = Path.home() / '.cache/gap-wave2-20260923/observation-inference'
    root = Path(tempfile.mkdtemp(prefix='spool-combined-', dir=base))
    stack = isostack.Stack(root, components=('otelcol', 'loki'))
    spool = stack.spool
    subprocess.run(['mount', '-t', 'tmpfs', '-o', 'size=128k,mode=0700', 'tmpfs', str(spool)], check=True)
    R = {'helper_function_sha256': helper_sha, 'config': 'repository collector.yaml unchanged', 'started_at': now(), 'timeline': {}}

    def write():
        res = {'status': 'completed', 'configured_model': 'fixture-combined', 'duration_ms': 1, 'usage_status': 'known',
               'usage': {'total': {'inputTokens': 1, 'outputTokens': 1, 'totalTokens': 2}}}
        before = {p.name for p in spool.iterdir()}
        write_observation(spool, res)
        return next(iter({p.name for p in spool.iterdir()} - before))[:-5]

    def at(t0, s):
        while time.monotonic() - t0 < s:
            time.sleep(0.5)

    try:
        stack.start()
        t0 = time.monotonic()
        stack.stop_one('otelcol')
        R['timeline']['collector_stopped'] = now()
        at(t0, 5)
        ids = [write() for _ in range(8)]
        R['written'] = len(ids)
        at(t0, 60)
        stack.stop_one('loki')
        R['timeline']['loki_stopped'] = now()
        at(t0, 180)
        stack.start_one('otelcol')
        R['timeline']['collector_restarted_loki_still_down'] = now()
        ev, _ = wait_for(lambda: events_ids(stack), ids, 40)
        R['in_events_file_before_loki_back'] = sum(1 for i in ids if i in ev)
        at(t0, 240)
        stack.start_one('loki')
        R['timeline']['loki_restarted'] = now()
        got, secs = wait_for(lambda: loki_ids(stack), ids, 150)
        R['in_loki_after_both_back'] = sum(1 for i in ids if i in got)
        R['lost_in_loki'] = len(ids) - R['in_loki_after_both_back']
        R['loki_duplicates'] = {i: c for i, c in got.items() if c > 1}
        R['seconds_after_loki_restart_to_all'] = secs
        log = (stack.log_dir / 'otelcol.log').read_text(errors='replace')
        R['collector_log_signals'] = {k: log.count(k) for k in ('Exporting failed', 'Dropping data', 'no more retries left')}
    except Exception as e:
        R['error'] = f'{type(e).__name__}: {e}'
        raise
    finally:
        stack.stop()
        subprocess.run(['umount', str(spool)])
        R['stopped_at'] = now()
        Path(a.out).write_text(json.dumps(R, indent=2) + '\n')
    print(json.dumps(R, indent=1))
    return 0 if R.get('lost_in_loki') == 0 and not R.get('loki_duplicates') else 1


if __name__ == '__main__':
    sys.exit(main())
