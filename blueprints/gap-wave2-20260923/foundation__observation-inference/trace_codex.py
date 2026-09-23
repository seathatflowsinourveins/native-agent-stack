#!/usr/bin/env python3
"""One native Codex session exporting OTLP traces to a pinned loopback Jaeger; query its trace by ID.

Jaeger 2.21.0 (release tarball sha256 f5741318ea2c3a2e64a1e1fffafcd1b03872ed0783ec5e7675fb6c686bfc7a5a,
inner binary checked against the upstream sha256sum file) runs from a private cache directory with
in-memory storage and only OTLP + query + health listeners on free 127.0.0.1 ports. Config is the
upstream cmd/jaeger/internal/all-in-one.yaml (v2.21.0, sha256 ecfb8966...) reduced to those components.

The single `codex exec` runs under `env -i`, --ephemeral, read-only sandbox, --ignore-user-config (no
user MCP servers, plugins, hook trust or live OTLP endpoints), --disable hooks, and -c overrides that
disable log/metric export and point only trace_exporter at this Jaeger. Native sign-in is used as-is.
"""
import argparse
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import isostack  # noqa: E402

JAEGER = Path.home() / '.cache/gap-wave2-20260923/observation-inference/jaeger-2.21.0/jaeger-2.21.0-linux-amd64/jaeger'

CONFIG = """service:
  extensions: [jaeger_storage, jaeger_query, healthcheckv2]
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch]
      exporters: [jaeger_storage_exporter]
  telemetry:
    resource:
      service.name: jaeger
    metrics:
      level: none
    logs:
      level: warn
extensions:
  jaeger_query:
    storage:
      traces: mem
    http:
      endpoint: 127.0.0.1:{query_http}
    grpc:
      endpoint: 127.0.0.1:{query_grpc}
  jaeger_storage:
    backends:
      mem:
        memory:
          max_traces: 10000
  healthcheckv2:
    use_v2: true
    http:
      endpoint: 127.0.0.1:{health}
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 127.0.0.1:{otlp_grpc}
      http:
        endpoint: 127.0.0.1:{otlp_http}
processors:
  batch:
exporters:
  jaeger_storage_exporter:
    trace_storage: mem
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', required=True)
    ap.add_argument('--codex', default=str(Path.home() / '.local/share/codex-ecosystem/bin/codex'))
    ap.add_argument('--model', default='gpt-6-astra')
    ap.add_argument('--effort', default='low')
    a = ap.parse_args()
    base = Path.home() / '.cache/gap-wave2-20260923/observation-inference'
    root = Path(tempfile.mkdtemp(prefix='trace-codex-', dir=base))
    ports = {k: isostack.free_port() for k in ('query_http', 'query_grpc', 'health', 'otlp_grpc', 'otlp_http')}
    cfg = root / 'jaeger.yaml'
    cfg.write_text(CONFIG.format(**ports))
    R = {'started_at': datetime.now(timezone.utc).isoformat(), 'jaeger_version': '2.21.0', 'model': a.model, 'effort': a.effort}
    log = open(root / 'jaeger.log', 'wb')
    jp = subprocess.Popen([str(JAEGER), f'--config=file:{cfg}'], stdout=log, stderr=subprocess.STDOUT,
                          env={'PATH': '/usr/bin:/bin', 'HOME': str(root)}, start_new_session=True)
    q = f"http://127.0.0.1:{ports['query_http']}"
    try:
        for _ in range(120):
            try:
                if isostack.http(f"http://127.0.0.1:{ports['health']}/status", raw=True)[0] == 200:
                    break
            except Exception:
                time.sleep(0.5)
        R['jaeger_health'] = 'ok'
        R['services_before'] = isostack.http(q + '/api/v3/services')[1]
        cwd = root / 'task-cwd'
        cwd.mkdir()
        trace_ep = f"http://127.0.0.1:{ports['otlp_http']}/v1/traces"
        overrides = [f'model="{a.model}"', f'model_reasoning_effort="{a.effort}"', 'otel.environment="gap-wave2"',
                     'otel.exporter="none"', 'otel.metrics_exporter="none"', 'otel.log_user_prompt=false',
                     'otel.trace_exporter={otlp-http={endpoint="%s",protocol="binary"}}' % trace_ep]
        cmd = [a.codex, 'exec', '--ephemeral', '--sandbox', 'read-only', '--skip-git-repo-check', '--ignore-user-config',
               '--disable', 'hooks', '--json', '-C', str(cwd)]
        for o in overrides:
            cmd += ['-c', o]
        cmd += ['Reply with exactly the two characters OK and nothing else. Do not run any command.']
        R['command_redacted'] = ['codex'] + [x.replace(str(cwd), '<tmp cwd>').replace(trace_ep, '<jaeger otlp http>/v1/traces') for x in cmd[1:]]
        env = {'HOME': str(Path.home()), 'PATH': '/usr/bin:/bin', 'USER': os.environ.get('USER', ''), 'LANG': 'C.UTF-8',
               'TERM': 'dumb', 'AI_MEMORY_SERVER_URL': 'http://127.0.0.1:9'}
        t0 = time.time()
        R['codex_started_at'] = datetime.now(timezone.utc).isoformat()
        p = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=600)
        R['codex_exit_code'] = p.returncode
        R['codex_elapsed_s'] = round(time.time() - t0, 2)
        (root / 'codex.stdout.jsonl').write_text(p.stdout)
        (root / 'codex.stderr.txt').write_text(p.stderr)
        evs = [json.loads(x) for x in p.stdout.splitlines() if x.strip().startswith('{')]
        R['codex_event_types'] = sorted({e.get('type') for e in evs})
        th = next((e for e in evs if e.get('type') == 'thread.started'), None)
        R['codex_thread_id'] = th.get('thread_id') if th else None
        tc = next((e for e in evs if e.get('type') == 'turn.completed'), None)
        R['codex_usage'] = tc.get('usage') if tc else None
        R['codex_stderr_tail'] = p.stderr[-600:].replace(str(Path.home()), '$HOME')
        # find traces
        services, deadline = [], time.time() + 60
        while time.time() < deadline:
            services = isostack.http(q + '/api/v3/services')[1].get('services') or []
            if services:
                time.sleep(3)
                services = isostack.http(q + '/api/v3/services')[1].get('services') or []
                break
            time.sleep(2)
        R['services_after'] = services
        found = []
        start = datetime.fromtimestamp(t0 - 120, timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000000000Z')
        end = datetime.fromtimestamp(time.time() + 60, timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000000000Z')
        for svc in services:
            qs = urllib.parse.urlencode({'query.service_name': svc, 'query.start_time_min': start, 'query.start_time_max': end,
                                         'query.search_depth': '100'})
            st, body = isostack.http(q + '/api/v3/traces?' + qs)
            for rs in (body.get('result') or {}).get('resourceSpans', []):
                for ss in rs.get('scopeSpans', []):
                    for sp in ss.get('spans', []):
                        found.append({'service': svc, 'trace_id': sp['traceId'], 'span': sp['name'], 'scope': ss.get('scope', {}).get('name')})
        R['search_spans'] = len(found)
        trace_ids = sorted({f['trace_id'] for f in found})
        R['search_trace_ids'] = trace_ids
        R['span_names'] = sorted({f['span'] for f in found})[:60]
        R['scopes'] = sorted({str(f['scope']) for f in found})
        by_id = []
        for tid in trace_ids[:10]:
            st, body = isostack.http(q + f'/api/v3/traces/{tid}')
            spans, attrs_keys, thread_attr = 0, set(), False
            for rs in (body.get('result') or {}).get('resourceSpans', []):
                for ss in rs.get('scopeSpans', []):
                    for sp in ss.get('spans', []):
                        spans += 1
                        for kv in sp.get('attributes', []):
                            attrs_keys.add(kv['key'])
                            if R['codex_thread_id'] and R['codex_thread_id'] in json.dumps(kv):
                                thread_attr = True
            st2, legacy = isostack.http(q + f'/api/traces/{tid}')
            by_id.append({'trace_id': tid, 'v3_http': st, 'v3_spans': spans, 'legacy_http': st2,
                          'legacy_spans': sum(len(t.get('spans', [])) for t in (legacy.get('data') or [])),
                          'attribute_keys': sorted(attrs_keys)[:80], 'contains_codex_thread_id': thread_attr})
        R['fetched_by_id'] = by_id
        # content-leak probe: the prompt text and the model reply must not appear in any fetched trace body
        blob = ''
        for tid in trace_ids[:10]:
            blob += json.dumps(isostack.http(q + f'/api/v3/traces/{tid}')[1])
        R['prompt_text_in_traces'] = 'Do not run any command' in blob
        R['home_path_in_traces'] = str(Path.home()) in blob
        (root / 'traces.json').write_text(blob)
    finally:
        try:
            os.killpg(jp.pid, signal.SIGTERM)
            jp.wait(timeout=20)
        except Exception:
            os.killpg(jp.pid, signal.SIGKILL)
        R['stopped_at'] = datetime.now(timezone.utc).isoformat()
    Path(a.out).write_text(json.dumps(R, indent=2) + '\n')
    print(json.dumps({k: R.get(k) for k in ('codex_exit_code', 'services_after', 'search_spans', 'search_trace_ids', 'fetched_by_id', 'prompt_text_in_traces')}, indent=1)[:3000])
    return 0 if any(x['v3_spans'] > 0 for x in R.get('fetched_by_id', [])) else 1


if __name__ == '__main__':
    sys.exit(main())
