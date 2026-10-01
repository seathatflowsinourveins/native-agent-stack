"""Stack MCP usage check for one headroom build (corrected acceptance step 2 / 4).

Run with the tool's own python:  <tool python> -s -B mcp_session.py MODE HBIN WS FIXTURE_B OUTDIR
under the G wrapper, so the spawned server's environment is exactly G.

MODE=session : list_tools; compress+retrieve fixture A; compress+retrieve fixture B;
               retrieve an unknown hash; stats.  (the refuter's call order)
MODE=retrieve: list_tools; retrieve fixture B's and fixture A's hashes only
               (the cross-version rollback probe against another version's workspace).

The fixture A generator is copied verbatim from the host-use receipt
evidence/hosts/nativestack-5975wx-20260925/nativestack-5975wx-20260925--headroom--use--20260925.json.
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

mode, hbin, ws, fixture_b_path, outdir = sys.argv[1:6]
os.makedirs(outdir, exist_ok=True)

lines = ['2026-09-25T10:%02d:%02dZ request=%d status=200 path=/api/items latency_ms=%d' % (i // 60, i % 60, i, 20 + i % 7) for i in range(600)]
lines[313] = '2026-09-25T10:05:13Z request=313 status=503 path=/api/items latency_ms=30000 CRITICAL upstream timeout nsr-anomaly-7f3a'
A = '\n'.join(lines)
B_bytes = open(fixture_b_path, 'rb').read()
B = B_bytes.decode('utf-8')
FIXTURES = {'A': A, 'B': B}
UNKNOWN = '0123456789abcdef01234567'
TS_RE = re.compile(r'\d{4}-\d{2}-\d{2}T\d{1,2}:\d{1,2}:\d{1,2}Z')
ROW_RE = re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z request=')
A_LINES = set(lines)

# G, identical to steps/G. stdio_client adds HOME/LOGNAME/PATH/SHELL/TERM/USER from this
# process's own environment; this process already runs under G, so only HOME and PATH exist.
env = {
    'HOME': os.environ['HOME'],
    'PATH': '/usr/bin:/bin',
    'HEADROOM_WORKSPACE_DIR': ws,
    'HEADROOM_OFFLINE': '1',
    'HEADROOM_BEACON': 'off',
    'DO_NOT_TRACK': '1',
    'HEADROOM_TELEMETRY': 'off',
    'HF_HUB_OFFLINE': '1',
    'TRANSFORMERS_OFFLINE': '1',
    'PYTHONDONTWRITEBYTECODE': '1',
    'LITELLM_LOCAL_MODEL_COST_MAP': 'True',
}


def sha(s: str) -> str:
    return hashlib.sha256(s.encode('utf-8')).hexdigest()


def text(r) -> str:
    return ''.join(getattr(x, 'text', '') for x in r.content)


async def call(s, name, args, timeout=300):
    t0 = time.monotonic()
    r = await asyncio.wait_for(s.call_tool(name, args), timeout)
    return json.loads(text(r)), round(time.monotonic() - t0, 3)


def fidelity_a(compressed: str) -> dict:
    ts = TS_RE.findall(compressed)
    row_lines = [ln for ln in compressed.split('\n') if ROW_RE.match(ln)]
    return {
        'timestamp_matches': len(ts),
        'timestamps_not_verbatim_in_A': sorted({t for t in ts if t not in A})[:20],
        'row_shaped_lines': len(row_lines),
        'row_shaped_lines_not_verbatim_fixture_rows': [ln for ln in row_lines if ln not in A_LINES][:10],
        'fixture_rows_verbatim_in_compressed': sum(1 for ln in lines if ln in compressed),
        'planted_line_313_verbatim': lines[313] in compressed,
        'nsr_anomaly_present': 'nsr-anomaly-7f3a' in compressed,
        'compressed_chars': len(compressed),
    }


async def main() -> dict:
    out: dict = {'mode': mode, 'workspace': os.path.basename(ws.rstrip('/'))}
    errlog = open(os.path.join(outdir, f'server-stderr-{mode}.log'), 'w')
    params = StdioServerParameters(command=hbin, args=['mcp', 'serve', '--proxy-url', 'http://127.0.0.1:1'], env=env, cwd=outdir)
    t_start = time.monotonic()
    async with stdio_client(params, errlog=errlog) as (r, w):
        async with ClientSession(r, w) as s:
            init = await asyncio.wait_for(s.initialize(), 300)
            out['server_info'] = {'name': init.serverInfo.name, 'version': init.serverInfo.version}
            out['tools'] = sorted(t.name for t in (await s.list_tools()).tools)
            if mode == 'session':
                for key in ('A', 'B'):
                    content = FIXTURES[key]
                    c, tc = await call(s, 'headroom_compress', {'content': content})
                    o, tr = await call(s, 'headroom_retrieve', {'hash': c.get('hash', '')})
                    compressed = c.get('compressed') if isinstance(c.get('compressed'), str) else json.dumps(c.get('compressed'))
                    open(os.path.join(outdir, f'compressed-{key}.txt'), 'w').write(compressed or '')
                    rec = {
                        'content_bytes': len(content.encode('utf-8')),
                        'content_sha256': sha(content),
                        'hash': c.get('hash'),
                        'hash_equals_sha256_prefix24': c.get('hash') == sha(content)[:24],
                        'original_tokens': c.get('original_tokens'),
                        'compressed_tokens': c.get('compressed_tokens'),
                        'savings_percent': c.get('savings_percent'),
                        'transforms': c.get('transforms'),
                        'compressed_sha256': sha(compressed or ''),
                        'compressed_mentions_hash': bool(c.get('hash')) and c.get('hash') in (compressed or ''),
                        'retrieve_exact': o.get('original_content') == content,
                        'retrieve_bytes_exact': (o.get('original_content') or '').encode('utf-8') == content.encode('utf-8'),
                        'compress_s': tc,
                        'retrieve_s': tr,
                        'compress_error': c.get('error'),
                    }
                    if key == 'A':
                        rec['fidelity'] = fidelity_a(compressed or '')
                    out[key] = rec
                b, _ = await call(s, 'headroom_retrieve', {'hash': UNKNOWN})
                out['unknown_hash_error'] = (b.get('error') or '')[:80]
                st, _ = await call(s, 'headroom_stats', {})
                out['stats_compressions'] = st.get('compressions')
                out['stats_retrievals'] = st.get('retrievals')
            else:
                for key in ('B', 'A'):
                    h = sha(FIXTURES[key])[:24]
                    o, tr = await call(s, 'headroom_retrieve', {'hash': h})
                    out[f'retrieve_{key}'] = {
                        'hash': h,
                        'exact': o.get('original_content') == FIXTURES[key],
                        'bytes_exact': (o.get('original_content') or '').encode('utf-8') == (B_bytes if key == 'B' else A.encode('utf-8')),
                        'error': (o.get('error') or '')[:80],
                        'retrieve_s': tr,
                    }
    out['session_s'] = round(time.monotonic() - t_start, 3)
    return out


result = asyncio.run(main())
json.dump(result, open(os.path.join(outdir, f'result-{mode}.json'), 'w'), indent=1, sort_keys=True)
print(json.dumps(result, sort_keys=True))
