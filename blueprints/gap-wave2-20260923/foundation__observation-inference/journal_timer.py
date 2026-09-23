#!/usr/bin/env python3
"""Read-only journal analysis: did the pipeline's scheduled unit keep firing across boots,
user-manager daemon-reloads and user-manager restarts that already happened on this host?

Reads only `journalctl --user` (JSON output) and `systemctl --user show` properties; it never
starts, stops, reloads or edits any unit. Emits derived timings and counts only (no message
bodies beyond systemd's fixed unit-lifecycle phrases).

Detection: a stall after a reload or restart would show as an inter-run gap well above the
timer period (OnUnitActiveSec=2min, AccuracySec=10s), or as no 'Starting' line for the unit after
the event before the boot ended; failures show as 'Failed with result' / 'Main process exited'
lines, retained verbatim (systemd lifecycle phrases only). The service has no trigger other than
the timer (oneshot, no WantedBy), but a manual `systemctl --user start` cannot be excluded from the
journal alone. Counting the next 'Starting' line (added after review) avoids crediting a run that was
already executing before the event.
"""
import argparse
import json
import re
import subprocess
from datetime import datetime, timezone

UNIT = 'ecosystem-native-data.service'
TIMER = 'ecosystem-native-data.timer'
BACKENDS = ['ecosystem-' + n + '.service' for n in ('prometheus', 'loki', 'grafana', 'alertmanager', 'ntfy', 'otelcol')]


def ts(us):
    return datetime.fromtimestamp(int(us) / 1e6, timezone.utc)


def iso(d):
    return d.isoformat().replace('+00:00', 'Z') if d else None


def boots():
    out = subprocess.run(['journalctl', '--user', '--list-boots', '-o', 'json', '--no-pager'], capture_output=True, text=True).stdout
    try:
        return json.loads(out)
    except Exception:
        return []


def entries(boot_id):
    p = subprocess.run(['journalctl', '--user', '-b', boot_id, '-o', 'json', '--no-pager',
                        '--output-fields=MESSAGE,_PID,SYSLOG_IDENTIFIER,__REALTIME_TIMESTAMP,UNIT,USER_UNIT'],
                       capture_output=True, text=True)
    for line in p.stdout.splitlines():
        try:
            yield json.loads(line)
        except Exception:
            continue


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    R = {'analyzed_at': iso(datetime.now(timezone.utc)), 'unit': UNIT, 'timer': TIMER,
         'timer_schedule': {'OnBootSec': '45s', 'OnUnitActiveSec': '2min', 'AccuracySec': '10s',
                            'source': 'observability/native-data/native-data.timer.example'}, 'boots': []}
    show = subprocess.run(['systemctl', '--user', 'show', TIMER, '-p', 'UnitFileState,ActiveState,LastTriggerUSec', '--no-pager'],
                          capture_output=True, text=True).stdout
    R['timer_state_now'] = dict(l.split('=', 1) for l in show.splitlines() if '=' in l)
    for b in boots():
        bid = b.get('boot_id')
        rec = {'index': b.get('index'), 'first_entry': iso(ts(b['first_entry'])),
               'last_entry': iso(ts(b['last_entry']))}
        manager_pids, reloads, finished, failed, timer_started, backends_started = [], [], [], [], [], {}
        starting, failure_lines = [], []
        for e in entries(bid):
            msg = e.get('MESSAGE')
            if not isinstance(msg, str):
                continue
            t = ts(e['__REALTIME_TIMESTAMP'])
            if e.get('SYSLOG_IDENTIFIER') == 'systemd':
                pid = e.get('_PID')
                if msg.startswith('Queued start job for default target'):
                    manager_pids.append((pid, t))  # a new user-manager instance started
                if msg.startswith('Reloading finished'):
                    reloads.append(t)
                if msg.startswith('Finished ' + UNIT) or (msg.startswith(UNIT) and 'Deactivated successfully' in msg and False):
                    finished.append(t)
                if msg.startswith('Starting ' + UNIT):
                    starting.append(t)
                if UNIT in msg and ('Failed' in msg or 'Main process exited' in msg):
                    failure_lines.append(f'{iso(t)} systemd: {msg}')
                if msg.startswith(UNIT + ": Failed with result"):
                    failed.append((t, msg.split("'")[1] if "'" in msg else '?'))
                if msg.startswith('Started ' + TIMER):
                    timer_started.append(t)
                for u in BACKENDS:
                    if msg.startswith('Started ' + u):
                        backends_started.setdefault(u, 0)
                        backends_started[u] += 1
        start = ts(b['first_entry'])
        end = ts(b['last_entry'])
        gaps = [(finished[i + 1] - finished[i]).total_seconds() for i in range(len(finished) - 1)]
        rec.update({
            'duration_s': round((end - start).total_seconds()),
            'user_manager_starts': len(manager_pids),
            'timer_started_events': [iso(t) for t in timer_started],
            'finished_runs': len(finished),
            'failed_runs': len(failed),
            'failed_run_results': sorted({r for _, r in failed}),
            'failed_run_times': [iso(t) for t, _ in failed],
            'first_run_after_boot_s': round((finished[0] - start).total_seconds(), 1) if finished else None,
            'max_gap_between_runs_s': round(max(gaps), 1) if gaps else None,
            'median_gap_between_runs_s': round(sorted(gaps)[len(gaps) // 2], 1) if gaps else None,
            'gaps_over_200s': sum(1 for g in gaps if g > 200),
            'backends_started': backends_started,
            'daemon_reloads': len(reloads),
        })
        after_reload = []
        for r in reloads:
            nxt = next((f for f in finished if f > r), None)
            after_reload.append(round((nxt - r).total_seconds(), 1) if nxt else None)
        rec['next_run_after_each_reload_s'] = after_reload
        rec['next_start_after_each_reload_s'] = [round((next((x for x in starting if x > r), None) - r).total_seconds(), 1) if next((x for x in starting if x > r), None) else None for r in reloads]
        rec['reloads_without_later_start'] = sum(1 for x in rec['next_start_after_each_reload_s'] if x is None)
        rec['starting_events'] = len(starting)
        rec['failure_lines'] = failure_lines
        rec['reloads_without_later_run'] = sum(1 for x in after_reload if x is None)
        restarts = []
        for p, t in manager_pids:
            nxt = next((f for f in finished if f > t), None)
            restarts.append({'new_manager_first_seen': iso(t), 'next_run_after_s': round((nxt - t).total_seconds(), 1) if nxt else None})
        rec['next_run_after_each_manager_start_s'] = [x['next_run_after_s'] for x in restarts]
        rec['next_start_after_each_manager_start_s'] = [round((next((x for x in starting if x > t), None) - t).total_seconds(), 1) if next((x for x in starting if x > t), None) else None for _, t in manager_pids]
        rec['manager_starts_without_later_start'] = sum(1 for x in rec['next_start_after_each_manager_start_s'] if x is None)
        rec['manager_starts_without_later_run'] = sum(1 for x in restarts if x['next_run_after_s'] is None)
        R['boots'].append(rec)
    Path = __import__('pathlib').Path
    Path(a.out).write_text(json.dumps(R, indent=2) + '\n')
    for b in R['boots']:
        print({k: b[k] for k in ('index', 'duration_s', 'finished_runs', 'failed_runs', 'first_run_after_boot_s',
                                  'max_gap_between_runs_s', 'gaps_over_200s', 'daemon_reloads', 'reloads_without_later_run',
                                  'next_start_after_each_reload_s', 'reloads_without_later_start', 'user_manager_starts', 'manager_starts_without_later_start', 'failed_runs', 'failed_run_results')})


if __name__ == '__main__':
    main()
