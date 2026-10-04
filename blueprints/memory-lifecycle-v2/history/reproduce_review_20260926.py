#!/usr/bin/env python3
"""Reproduce the 2026-09-26 cross-family review's analyzer findings on the retained
2026-09-25 responses (runs-20260925/), using analyze.py exactly as PR #292 merged it
(commit 310871ac, read with `git show`).

Each mutation below should have failed a check. The printed counts are the
(phase-pre passed, total, phase-post passed, total) that the 2026-09-25 analyzer still
returns for it. The repaired analyzer's answer to the same mutations is in
tests/test_memory_lifecycle_v2.py.

    python3 history/reproduce_review_20260926.py
"""
import copy
import json
from pathlib import Path
import subprocess
import types

HERE = Path(__file__).resolve().parents[1]
MERGE = '310871ac5ffc5fd3857a4d8db52cfb7607bf64cb'


def original_analyzer():
    source = subprocess.run(['git', 'show', f'{MERGE}:blueprints/memory-lifecycle-v2/analyze.py'], cwd=HERE,
                            capture_output=True, text=True, check=True).stdout
    module = types.ModuleType('analyze_20260925')
    exec(compile(source, 'analyze_20260925.py', 'exec'), module.__dict__)
    return module


def text_response(value):
    return {'jsonrpc': '2.0', 'id': 0, 'result': {'content': [{'type': 'text', 'text': json.dumps(value)}],
                                                  'isError': False}}


def main():
    old = original_analyzer()
    for run in sorted((HERE / 'runs-20260925').glob('ai-memory-*/attempt-*')):
        pre = json.loads((run / 'phase-pre/outcomes.json').read_text())
        post = json.loads((run / 'phase-post/outcomes.json').read_text())
        handoff = json.loads((run / 'handoff/fixture-state.json').read_text())

        def score(p, q):
            a, b = old.summarize_pre(p), old.summarize_post(q, handoff)
            return sum(a['checks'].values()), len(a['checks']), sum(b['checks'].values()), len(b['checks'])

        mutations = {}
        q = copy.deepcopy(post)
        for label in ('revision_deleted_current', 'revision_deleted_as_of', 'ttl_short_gone', 'expired_past_gone'):
            q[label] = text_response({})
        mutations['four restart queries answered {}'] = (pre, q)
        p = copy.deepcopy(pre)
        p['invalid_combined_scope'] = {'jsonrpc': '2.0', 'id': 0,
                                       'error': {'code': -32603, 'message': 'storage unavailable'}}
        mutations['scope conflict answered "storage unavailable"'] = (p, post)
        q = copy.deepcopy(post)
        q['revision_deleted_direct_read'] = {'jsonrpc': '2.0', 'id': 0,
                                             'error': {'code': -32601, 'message': 'method not found'}}
        mutations['deleted-page read answered -32601'] = (pre, q)
        p = copy.deepcopy(pre)
        alpha_hit = json.loads(pre['alpha_search_self']['result']['content'][0]['text'])['hits'][0]
        p['scopes_ws1_three'] = text_response({'hits': [alpha_hit] * 3})
        mutations['scopes[] answered three copies of alpha'] = (p, post)
        print(run.relative_to(HERE), 'unmodified', score(pre, post))
        for name, (p, q) in mutations.items():
            print(run.relative_to(HERE), name, score(p, q))


if __name__ == '__main__':
    main()
