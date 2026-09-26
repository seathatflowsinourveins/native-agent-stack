#!/usr/bin/env python3
"""Re-check the retained 2026-09-25 native responses (runs-20260925/) with the repaired
analyzer's rules, where that run's calls allow it.

That run made 69 + 16 calls and kept no per-call instants. The four direct reads added on
2026-09-26 and the timeline are therefore filled with stand-ins, and the six checks that
depend on a stand-in are excluded from the result instead of being reported as passed. Every
other repaired check -- list-valued hits, exact rejection codes and messages, distinct ids,
scopes[] ids, global annotation and terms -- is evaluated on the retained native responses.

    python3 history/recheck_20260925.py
"""
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import analyze  # noqa: E402

STAND_INS_PRE = {'ttl_after_sweep_direct_read': 'notes/ttl-short.md',
                 'expired_past_after_sweep_direct_read': 'notes/expired.md'}
STAND_INS_POST = {'ttl_short_direct_read_gone': 'notes/ttl-short.md',
                  'expired_past_direct_read_gone': 'notes/expired.md'}
EXCLUDED = ({f'{label}_rejected_as_expected' for label in (*STAND_INS_PRE, *STAND_INS_POST)}
            | {'ttl_before_expiry_answered_before_native_expiry', 'ttl_after_expiry_calls_sent_after_native_expiry'})


def stand_in(path):
    return {'jsonrpc': '2.0', 'id': 0,
            'error': {'code': -32603, 'message': f'page {path} not found in resolved scope lifecycle-v2/alpha'}}


def recheck(run):
    pre = json.loads((run / 'phase-pre/outcomes.json').read_text())
    post = json.loads((run / 'phase-post/outcomes.json').read_text())
    handoff = json.loads((run / 'handoff/fixture-state.json').read_text())
    pre.update({label: stand_in(path) for label, path in STAND_INS_PRE.items()})
    post.update({label: stand_in(path) for label, path in STAND_INS_POST.items()})
    timeline = {label: {'sent_utc': '2000-01-01T00:00:00+00:00', 'received_utc': '2000-01-01T00:00:00+00:00'}
                for label in pre}
    checks = {**analyze.summarize_pre(pre, timeline)['checks'], **analyze.summarize_post(post, handoff)['checks']}
    evaluated = {name: value for name, value in checks.items() if name not in EXCLUDED}
    return {'run': str(run.relative_to(HERE)), 'evaluated_checks': len(evaluated),
            'passed_checks': sum(evaluated.values()),
            'failed_checks': sorted(name for name, value in evaluated.items() if not value),
            'excluded_checks': sorted(EXCLUDED)}


if __name__ == '__main__':
    print(json.dumps([recheck(run) for run in sorted((HERE / 'runs-20260925').glob('ai-memory-*/attempt-*'))],
                     indent=2))
