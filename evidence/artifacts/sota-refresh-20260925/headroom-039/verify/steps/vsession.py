"""Verifier's independent MCP stdio session against one headroom build.

Usage (run under steps/VG with the build's own python -s -B):
  vsession.py HBIN WS FIXTURE_B OUTDIR LABEL MODE
MODE=session : list_tools; compress+retrieve A; compress+retrieve B; retrieve unknown; stats;
               then retrieve the 'Retrieve more: hash=' marker parsed from A's compressed text.
MODE=retrieve: list_tools; retrieve sha256(A)[:24], sha256(B)[:24] and any marker hashes
               given in env-free argv[7:] (rollback probe on another build's workspace).
Fixture A generator is byte-identical to the committed host-use receipt (6752ede5).
"""

import asyncio
import hashlib
import json
import os
import re
import sys
import time

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

hbin, ws, fixture_b, outdir, label, mode = sys.argv[1:7]
extra_hashes = sys.argv[7:]
os.makedirs(outdir, exist_ok=True)

lines = ['2026-09-25T10:%02d:%02dZ request=%d status=200 path=/api/items latency_ms=%d' % (i // 60, i % 60, i, 20 + i % 7) for i in range(600)]
lines[313] = '2026-09-25T10:05:13Z request=313 status=503 path=/api/items latency_ms=30000 CRITICAL upstream timeout nsr-anomaly-7f3a'
A = '\n'.join(lines)
B_raw = open(fixture_b, 'rb').read()
B = B_raw.decode('utf-8')
UNKNOWN = '0123456789abcdef01234567'
TS = re.compile(r'\d{4}-\d{2}-\d{2}T\d{1,2}:\d{1,2}:\d{1,2}Z')
MARK = re.compile(r'hash=([0-9a-f]{24})')

ENV = {
    'HOME': os.environ['HOME'], 'PATH': '/usr/bin:/bin', 'HEADROOM_WORKSPACE_DIR': ws,
    'HEADROOM_OFFLINE': '1', 'HEADROOM_BEACON': 'off', 'DO_NOT_TRACK': '1', 'HEADROOM_TELEMETRY': 'off',
    'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1', 'PYTHONDONTWRITEBYTECODE': '1',
    'LITELLM_LOCAL_MODEL_COST_MAP': 'True',
}


def h24(s):
    return hashlib.sha256(s.encode('utf-8')).hexdigest()[:24]


async def tool(sess, name, args):
    r = await asyncio.wait_for(sess.call_tool(name, args), 300)
    return json.loads(''.join(getattr(c, 'text', '') for c in r.content))


async def run():
    res = {'label': label, 'mode': mode}
    err = open(os.path.join(outdir, f'stderr-{label}.log'), 'w')
    p = StdioServerParameters(command=hbin, args=['mcp', 'serve', '--proxy-url', 'http://127.0.0.1:1'], env=ENV, cwd=outdir)
    t0 = time.monotonic()
    async with stdio_client(p, errlog=err) as (rd, wr):
        async with ClientSession(rd, wr) as s:
            await asyncio.wait_for(s.initialize(), 300)
            res['tools'] = sorted(t.name for t in (await s.list_tools()).tools)
            if mode == 'session':
                for key, content in (('A', A), ('B', B)):
                    c = await tool(s, 'headroom_compress', {'content': content})
                    o = await tool(s, 'headroom_retrieve', {'hash': c.get('hash', '')})
                    comp = c.get('compressed')
                    comp = comp if isinstance(comp, str) else json.dumps(comp)
                    open(os.path.join(outdir, f'compressed-{key}-{label}.txt'), 'w').write(comp)
                    res[key] = {
                        'hash': c.get('hash'), 'hash_is_sha256_24': c.get('hash') == h24(content),
                        'original_tokens': c.get('original_tokens'), 'compressed_tokens': c.get('compressed_tokens'),
                        'transforms': c.get('transforms'), 'compressed_sha256': hashlib.sha256(comp.encode()).hexdigest(),
                        'retrieve_byte_exact': (o.get('original_content') or '').encode('utf-8') == content.encode('utf-8'),
                    }
                    if key == 'A':
                        ts = TS.findall(comp)
                        res['A']['ts_matches'] = len(ts)
                        res['A']['ts_not_in_fixture'] = sorted({t for t in ts if t not in A})
                        comp_lines = comp.split('\n')
                        res['A']['compressed_lines'] = len(comp_lines)
                        res['A']['fixture_rows_verbatim'] = sum(1 for ln in comp_lines if ln in set(lines))
                        res['A']['line313_verbatim'] = lines[313] in comp_lines
                        res['A']['nsr_anomaly_present'] = 'nsr-anomaly-7f3a' in comp
                        res['A']['marker_hashes'] = MARK.findall(comp)
                u = await tool(s, 'headroom_retrieve', {'hash': UNKNOWN})
                res['unknown_error'] = (u.get('error') or '')[:80]
                st = await tool(s, 'headroom_stats', {})
                res['stats_compressions'] = st.get('compressions')
                res['markers'] = {}
                for mh in res['A']['marker_hashes']:
                    m = await tool(s, 'headroom_retrieve', {'hash': mh})
                    res['markers'][mh] = {
                        'byte_exact_A': (m.get('original_content') or '').encode('utf-8') == A.encode('utf-8'),
                        'is_md5_24_of_A': mh == hashlib.md5(A.encode('utf-8')).hexdigest()[:24],
                        'error': (m.get('error') or '')[:80],
                    }
            else:
                for key, content in (('B', B), ('A', A)):
                    o = await tool(s, 'headroom_retrieve', {'hash': h24(content)})
                    res['retrieve_' + key] = {'hash': h24(content), 'byte_exact': (o.get('original_content') or '').encode('utf-8') == content.encode('utf-8'), 'error': (o.get('error') or '')[:80]}
                for mh in extra_hashes:
                    o = await tool(s, 'headroom_retrieve', {'hash': mh})
                    res['retrieve_marker_' + mh] = {'byte_exact_A': (o.get('original_content') or '').encode('utf-8') == A.encode('utf-8'), 'error': (o.get('error') or '')[:80]}
    res['session_s'] = round(time.monotonic() - t0, 1)
    return res


out = asyncio.run(run())
if mode == 'session':
    a, b = out['A'], out['B']
    out['criteria'] = {
        'tools_exact': out['tools'] == ['headroom_compress', 'headroom_retrieve', 'headroom_stats'],
        'A_hash_sha256_24': a['hash_is_sha256_24'], 'B_hash_sha256_24': b['hash_is_sha256_24'],
        'B_hash_value': b['hash'] == '2b17eb36da607cc8d2f6f0e2',
        'A_retrieve_byte_exact': a['retrieve_byte_exact'], 'B_retrieve_byte_exact': b['retrieve_byte_exact'],
        'B_compressed_lt_original': (b['compressed_tokens'] or 0) < (b['original_tokens'] or 0),
        'B_transforms_not_empty_or_noop': bool(b['transforms']) and b['transforms'] != ['router:noop'],
        'A_compressed_le_original': (a['compressed_tokens'] or 0) <= (a['original_tokens'] or 0),
        'A_no_router_search': not any(str(t).startswith('router:search') for t in (a['transforms'] or [])),
        'A_timestamps_verbatim': a['ts_not_in_fixture'] == [],
        'A_nsr_anomaly_in_compressed': a['nsr_anomaly_present'],
        'unknown_content_not_found': out['unknown_error'].startswith('Content not found'),
        'stats_compressions_2': out['stats_compressions'] == 2,
    }
    out['ALL'] = all(out['criteria'].values())
json.dump(out, open(os.path.join(outdir, f'result-{label}.json'), 'w'), indent=1, sort_keys=True)
print(json.dumps(out, sort_keys=True))
