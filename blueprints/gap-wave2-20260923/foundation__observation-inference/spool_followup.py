#!/usr/bin/env python3
"""Follow-up to spool_outage.py (gap 4): (a) when does space freed by spool_expiry become usable,
and (b) does otlphttp/loki retry_on_failure.max_elapsed_time=0s prevent loss in a >300 s Loki outage?

Same isolation as spool_outage.py: unprivileged user+mount namespace, 128 KiB tmpfs spool, the
unchanged write_observation() helper, isolated collector + Loki. --variant baseline uses the
repository collector.yaml unchanged; --variant noexpiry merges an overlay that only sets
exporters.otlphttp/loki.retry_on_failure.max_elapsed_time: 0s.
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
import spool_expiry  # noqa: E402
from spool_outage import load_helper, loki_ids, events_ids, wait_for, now  # noqa: E402

OVERLAY = """exporters:
  otlphttp/loki:
    retry_on_failure:
      max_elapsed_time: 0s
"""


def deleted_fds(pid):
    n = 0
    try:
        for fd in os.listdir(f'/proc/{pid}/fd'):
            try:
                if os.readlink(f'/proc/{pid}/fd/{fd}').endswith('(deleted)'):
                    n += 1
            except OSError:
                pass
    except OSError:
        return None
    return n


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', required=True)
    ap.add_argument('--variant', choices=['baseline', 'noexpiry'], required=True)
    ap.add_argument('--loki-outage-s', type=int, default=330)
    a = ap.parse_args()
    if os.environ.get('GW2_IN_NS') != '1':
        return subprocess.call(['unshare', '--user', '--map-root-user', '--mount', sys.executable, __file__, *sys.argv[1:]],
                               env=dict(os.environ, GW2_IN_NS='1'))
    write_observation, helper_sha = load_helper()
    base = Path.home() / '.cache/gap-wave2-20260923/observation-inference'
    root = Path(tempfile.mkdtemp(prefix=f'spool-followup-{a.variant}-', dir=base))
    overlays = []
    if a.variant == 'noexpiry':
        (root / 'overlay.yaml').write_text(OVERLAY)
        overlays.append(root / 'overlay.yaml')
    stack = isostack.Stack(root, components=('otelcol', 'loki'), overlays=overlays)
    spool = stack.spool
    subprocess.run(['mount', '-t', 'tmpfs', '-o', 'size=128k,mode=0700', 'tmpfs', str(spool)], check=True)
    R = {'variant': a.variant, 'overlay': OVERLAY if overlays else None, 'helper_function_sha256': helper_sha,
         'started_at': now()}

    def write():
        res = {'status': 'completed', 'configured_model': 'fixture', 'duration_ms': 1, 'usage_status': 'known',
               'usage': {'total': {'inputTokens': 1, 'outputTokens': 1, 'totalTokens': 2}}}
        before = {p.name for p in spool.iterdir()}
        try:
            write_observation(spool, res)
            return next(iter({p.name for p in spool.iterdir()} - before))[:-5]
        except OSError:
            return None

    try:
        stack.start()
        pid = stack.procs['otelcol'].pid
        # (a) fill with collector up, wait for ingestion, expire, watch space release
        ids = []
        while True:
            i = write()
            if i is None:
                break
            ids.append(i)
        got, secs = wait_for(lambda: loki_ids(stack), ids, 60)
        R['a_filled'] = {'written': len(ids), 'in_loki': sum(1 for i in ids if i in got)}
        t0 = time.monotonic()
        exp = spool_expiry.run(str(spool), stack.loki_url, ttl_s=10**9, min_free_bytes=64 * 1024)
        R['a_expiry'] = {k: v for k, v in exp.items() if k != 'deleted_names'}
        R['a_deleted_open_fds_right_after'] = deleted_fds(pid)
        free_t = None
        samples = []
        while time.monotonic() - t0 < 20:
            v = os.statvfs(spool)
            fb = v.f_bavail * v.f_frsize
            samples.append((round(time.monotonic() - t0, 2), fb, deleted_fds(pid)))
            if fb > 0 and free_t is None:
                free_t = round(time.monotonic() - t0, 2)
                break
            time.sleep(0.1)
        R['a_space_released_after_s'] = free_t
        R['a_samples_first_last'] = [samples[0], samples[-1]] if samples else []
        R['a_write_after_release'] = write() is not None
        # (b) Loki outage beyond the exporter retry window
        t_l = time.time()
        R['b_loki_stopped_at'] = now()
        stack.stop_one('loki')
        time.sleep(2)
        ids_e = [i for i in (write() for _ in range(8)) if i]
        ev, _ = wait_for(lambda: events_ids(stack), ids_e, 30)
        R['b_written'] = len(ids_e)
        R['b_in_events_file_during_outage'] = sum(1 for i in ids_e if i in ev)
        while time.time() - t_l < a.loki_outage_s:
            time.sleep(5)
        R['b_loki_down_s'] = round(time.time() - t_l, 1)
        stack.start_one('loki')
        got, secs = wait_for(lambda: loki_ids(stack), ids_e, 150)
        R['b_in_loki_after_restore'] = sum(1 for i in ids_e if i in got)
        R['b_lost_in_loki'] = len(ids_e) - R['b_in_loki_after_restore']
        R['b_duplicates'] = {i: c for i, c in got.items() if c > 1}
        R['b_seconds_to_all'] = secs
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
    print(json.dumps(R, indent=1)[:2500])
    return 0


if __name__ == '__main__':
    sys.exit(main())
