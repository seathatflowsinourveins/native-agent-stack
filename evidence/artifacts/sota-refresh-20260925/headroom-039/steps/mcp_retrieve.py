"""Retrieve-only MCP probe against an existing workspace (acceptance step 4 and marker check).

Run with the tool's own python under the G wrapper:
  <tool python> -s -B mcp_retrieve.py HBIN WS FIXTURE_B OUTDIR LABEL
Calls list_tools, then headroom_retrieve for:
  B        sha256(fixture B)[:24]  (the MCP compress hash; rollback probe target)
  A        sha256(fixture A)[:24]  (the MCP compress hash)
  A_marker md5(fixture A)[:24]     (the 'Retrieve more: hash=' key 0.39.0's log compressor
                                    printed inside fixture A's compressed text)
and compares each returned original_content with the fixture bytes. No compress calls.
"""

import asyncio
import hashlib
import json
import os
import sys
import time

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

hbin, ws, fixture_b_path, outdir, label = sys.argv[1:6]
os.makedirs(outdir, exist_ok=True)

lines = ['2026-09-25T10:%02d:%02dZ request=%d status=200 path=/api/items latency_ms=%d' % (i // 60, i % 60, i, 20 + i % 7) for i in range(600)]
lines[313] = '2026-09-25T10:05:13Z request=313 status=503 path=/api/items latency_ms=30000 CRITICAL upstream timeout nsr-anomaly-7f3a'
A = '\n'.join(lines)
B_bytes = open(fixture_b_path, 'rb').read()
B = B_bytes.decode('utf-8')

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
targets = {
    'B': (hashlib.sha256(B_bytes).hexdigest()[:24], B),
    'A': (hashlib.sha256(A.encode('utf-8')).hexdigest()[:24], A),
    'A_marker': (hashlib.md5(A.encode('utf-8')).hexdigest()[:24], A),
}


def text(r) -> str:
    return ''.join(getattr(x, 'text', '') for x in r.content)


async def main() -> dict:
    out: dict = {'label': label, 'workspace': os.path.basename(ws.rstrip('/'))}
    errlog = open(os.path.join(outdir, f'server-stderr-{label}.log'), 'w')
    params = StdioServerParameters(command=hbin, args=['mcp', 'serve', '--proxy-url', 'http://127.0.0.1:1'], env=env, cwd=outdir)
    t0 = time.monotonic()
    async with stdio_client(params, errlog=errlog) as (r, w):
        async with ClientSession(r, w) as s:
            await asyncio.wait_for(s.initialize(), 300)
            out['tools'] = sorted(t.name for t in (await s.list_tools()).tools)
            for key, (h, expected) in targets.items():
                o = json.loads(text(await asyncio.wait_for(s.call_tool('headroom_retrieve', {'hash': h}), 300)))
                got = o.get('original_content')
                out[key] = {
                    'hash': h,
                    'exact': got == expected,
                    'bytes_exact': (got or '').encode('utf-8') == expected.encode('utf-8'),
                    'error': (o.get('error') or '')[:80],
                }
    out['session_s'] = round(time.monotonic() - t0, 3)
    return out


result = asyncio.run(main())
json.dump(result, open(os.path.join(outdir, f'result-{label}.json'), 'w'), indent=1, sort_keys=True)
print(json.dumps(result, sort_keys=True))
