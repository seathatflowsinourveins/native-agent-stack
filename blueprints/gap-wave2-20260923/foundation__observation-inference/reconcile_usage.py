#!/usr/bin/env python3
"""Scripted native Claude usage reconciliation (docs/native-telemetry-resolution.md lines 22-30).

Runs exactly ONE bounded native `claude -p` task against an isolated collector/Prometheus/Loki
stack (isostack.Stack, repository collector.yaml privacy processors unchanged) and compares
the task's native stream-json usage with the Prometheus counter delta
sum by (type) (ecosystem_claude_code_token_usage_tokens_total).

Isolation and attribution:
- The child runs under `env -i` from a fresh temp cwd with `--setting-sources local` (no user or
  project settings, so no user hooks, user-installed plugins or live OTLP endpoint are loaded; the
  two built-in plugins agents-md@builtin and telemetry@builtin still load), `--settings` JSON that
  points every OTLP signal at the isolated collector and sets disableAllHooks, an empty strict MCP
  config, no tools, --max-turns 1, --no-session-persistence and a caller-chosen --session-id.
- Only this child exports to the isolated collector, so the before snapshot is empty and the
  after-minus-before delta is attributable to it. An overlay side pipeline (metrics/attribution)
  keeps only session.id/type/model and writes them to a private file; the script reports the
  distinct session.id values seen, which must equal the --session-id passed to the child.
- Native sign-in is used as-is; no credential file is read by this script.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import isostack  # noqa: E402

OVERLAY = """processors:
  transform/attribution:
    error_mode: propagate
    metric_statements:
      - context: resource
        statements:
          - keep_keys(attributes, ["service.name"])
      - context: datapoint
        statements:
          - keep_keys(attributes, ["session.id", "type", "model"])
exporters:
  file/attribution:
    path: ${env:ECOSYSTEM_OBSERVABILITY_DATA}/collector/attribution.jsonl
    flush_interval: 1s
service:
  pipelines:
    metrics/attribution:
      receivers: [otlp]
      processors: [transform/attribution, batch]
      exporters: [file/attribution]
"""
Q = 'sum by (type) (ecosystem_claude_code_token_usage_tokens_total)'
MAP = {'input': 'input_tokens', 'output': 'output_tokens', 'cacheRead': 'cache_read_input_tokens',
       'cacheCreation': 'cache_creation_input_tokens'}
MU = {'input': 'inputTokens', 'output': 'outputTokens', 'cacheRead': 'cacheReadInputTokens',
      'cacheCreation': 'cacheCreationInputTokens'}


def snap(stack):
    return {r['metric'].get('type', '?'): float(r['value'][1]) for r in stack.prom_query(Q)}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--model', default='haiku')
    ap.add_argument('--prompt', default='Reply with exactly the two characters OK and nothing else.')
    ap.add_argument('--out')
    ap.add_argument('--claude', default=str(Path.home() / '.local/bin/claude'))
    ap.add_argument('--evaluate', help='apply verdict() to a retained result JSON; makes no model call')
    a = ap.parse_args()
    if a.evaluate:
        v = verdict(json.loads(Path(a.evaluate).read_text()))
        print(json.dumps(v, indent=1))
        return 0 if v['passed'] else 1
    base = Path.home() / '.cache/gap-wave2-20260923/observation-inference'
    root = Path(tempfile.mkdtemp(prefix='reconcile-', dir=base))
    (root / 'overlay.yaml').write_text(OVERLAY)
    stack = isostack.Stack(root, components=('otelcol', 'prometheus', 'loki'), overlays=[root / 'overlay.yaml'])
    sid = str(uuid.uuid4())
    res = {'started_at': datetime.now(timezone.utc).isoformat(), 'session_id': sid, 'model_requested': a.model,
           'query': Q}
    try:
        stack.start()
        time.sleep(3)
        res['before'] = snap(stack)
        res['before_series_count'] = len(stack.prom_query('{__name__=~"ecosystem_claude_code_.+"}'))
        env_otel = {
            'CLAUDE_CODE_ENABLE_TELEMETRY': '1', 'OTEL_METRICS_EXPORTER': 'otlp', 'OTEL_LOGS_EXPORTER': 'otlp',
            'OTEL_TRACES_EXPORTER': 'none', 'OTEL_EXPORTER_OTLP_PROTOCOL': 'http/protobuf',
            'OTEL_EXPORTER_OTLP_ENDPOINT': stack.otlp_http, 'OTEL_METRIC_EXPORT_INTERVAL': '1000',
            'OTEL_LOGS_EXPORT_INTERVAL': '1000', 'OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE': 'cumulative',
            'OTEL_LOG_USER_PROMPTS': 'false', 'OTEL_LOG_ASSISTANT_RESPONSES': 'false', 'OTEL_LOG_TOOL_DETAILS': 'false',
            'OTEL_LOG_TOOL_CONTENT': 'false', 'OTEL_LOG_RAW_API_BODIES': 'false',
            'OTEL_METRICS_INCLUDE_ACCOUNT_UUID': 'false', 'OTEL_METRICS_INCLUDE_SESSION_ID': 'true',
            'OTEL_METRICS_INCLUDE_VERSION': 'true'}
        settings = {'env': env_otel, 'disableAllHooks': True}
        cwd = root / 'task-cwd'
        cwd.mkdir()
        env = {'HOME': str(Path.home()), 'PATH': '/usr/bin:/bin', 'USER': os.environ.get('USER', ''),
               'LANG': 'C.UTF-8', 'TERM': 'dumb',
               # Any ai-memory call would fail closed against a port with no listener.
               'AI_MEMORY_SERVER_URL': 'http://127.0.0.1:9', **env_otel}
        cmd = [a.claude, '-p', '--output-format', 'stream-json', '--verbose', '--max-turns', '1',
               '--model', a.model, '--tools', '', '--setting-sources', 'local',
               '--settings', json.dumps(settings), '--strict-mcp-config', '--mcp-config', '{"mcpServers":{}}',
               '--session-id', sid, '--no-session-persistence', '--', a.prompt]
        res['command_redacted'] = ['claude'] + cmd[1:cmd.index('--settings') + 1] + ['<settings JSON: env above + disableAllHooks>'] + cmd[cmd.index('--settings') + 2:]
        res['child_env_otel'] = {k: ('<isolated collector>' if k == 'OTEL_EXPORTER_OTLP_ENDPOINT' else v) for k, v in env_otel.items()}
        t0 = time.time()
        p = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=300)
        res['claude_exit_code'] = p.returncode
        res['claude_elapsed_s'] = round(time.time() - t0, 2)
        (root / 'stream.jsonl').write_text(p.stdout)
        (root / 'stderr.txt').write_text(p.stderr)
        events = [json.loads(x) for x in p.stdout.splitlines() if x.strip().startswith('{')]
        result = next((e for e in events if e.get('type') == 'result'), None)
        init = next((e for e in events if e.get('type') == 'system' and e.get('subtype') == 'init'), None)
        res['stream_event_types'] = sorted({e.get('type') for e in events})
        res['init_session_id_matches'] = bool(init and init.get('session_id') == sid)
        res['init_model'] = init.get('model') if init else None
        res['init_tools_count'] = len(init.get('tools') or []) if init else None
        res['init_mcp_servers_count'] = len(init.get('mcp_servers') or []) if init else None
        res['init_plugins'] = [pl.get('source') for pl in (init.get('plugins') or [])] if init else None
        res['init_api_key_source'] = init.get('apiKeySource') if init else None
        if result:
            res['native_result'] = {k: result.get(k) for k in ('subtype', 'is_error', 'num_turns', 'duration_ms', 'duration_api_ms',
                                                               'total_cost_usd')}
            res['native_usage'] = {k: result.get('usage', {}).get(v) for k, v in MAP.items()}
            mu = result.get('modelUsage') or {}
            res['native_model_usage'] = {m: {k: u.get(v) for k, v in MU.items()} for m, u in mu.items()}
        # wait for export + scrape to settle
        prev, stable, deadline = None, 0, time.time() + 60
        while time.time() < deadline and stable < 3:
            time.sleep(2)
            cur = snap(stack)
            stable = stable + 1 if (cur and cur == prev) else 0
            prev = cur
        res['after'] = prev
        by_model = stack.prom_query('sum by (type, model) (ecosystem_claude_code_token_usage_tokens_total)')
        res['after_by_model'] = [{'type': r['metric'].get('type'), 'model': r['metric'].get('model'), 'value': float(r['value'][1])} for r in by_model]
        # attribution side pipeline
        sids, seen_types = set(), set()
        attr = stack.data / 'collector/attribution.jsonl'
        for line in (attr.read_text().splitlines() if attr.exists() else []):
            for rm in json.loads(line).get('resourceMetrics', []):
                for sm in rm.get('scopeMetrics', []):
                    for m in sm.get('metrics', []):
                        body = m.get('sum') or m.get('gauge') or m.get('histogram') or {}
                        for dp in body.get('dataPoints', []):
                            at = {x['key']: list(x['value'].values())[0] for x in dp.get('attributes', [])}
                            if 'session.id' in at:
                                sids.add(at['session.id'])
                            if m.get('name') == 'claude_code.token.usage':
                                seen_types.add(at.get('type'))
        res['attribution_distinct_session_ids'] = sorted(sids)
        res['attribution_only_child_session'] = sids == {sid}
        # Loki log events for this session (session.id is allowlisted for logs)
        dump = stack.loki_dump(int((t0 - 60) * 1e9), time.time_ns() + 60 * 10**9)
        d = json.loads(dump)
        ev = {}
        api_tokens = {'input_tokens': 0, 'output_tokens': 0, 'cache_read_tokens': 0, 'cache_creation_tokens': 0}
        api_events = 0
        for s in d['data']['result']:
            st = s['stream']
            if st.get('session_id') != sid:
                continue
            en = st.get('event_name') or st.get('event_name_extracted') or '?'
            ev[en] = ev.get(en, 0) + len(s['values'])
            if en in ('claude_code.api_request', 'api_request'):
                api_events += len(s['values'])
                for k in api_tokens:
                    if k in st:
                        api_tokens[k] += int(float(st[k])) * len(s['values'])
        res['loki_events_for_session'] = ev
        res['loki_api_request_events'] = api_events
        res['loki_api_request_token_sum'] = api_tokens if api_events else None
        # comparison
        cmp = {}
        before = res['before']
        for t in MAP:
            after = (prev or {}).get(t)
            b = before.get(t)
            delta = None if after is None else after - (b or 0.0)
            native = res.get('native_usage', {}).get(t)
            mu_sum = sum((u.get(t) or 0) for u in res.get('native_model_usage', {}).values()) if res.get('native_model_usage') else None
            cmp[t] = {'before': b if b is not None else 'absent', 'after': after if after is not None else 'absent',
                      'delta': delta, 'native_result_usage': native, 'native_model_usage_sum': mu_sum,
                      'delta_equals_result_usage': (delta is not None and native is not None and delta == native),
                      'delta_equals_model_usage_sum': (delta is not None and mu_sum is not None and delta == mu_sum)}
        res['comparison'] = cmp
        res['all_categories_match_result_usage'] = all(v['delta_equals_result_usage'] for v in cmp.values())
        res['all_categories_match_model_usage_sum'] = all(v['delta_equals_model_usage_sum'] for v in cmp.values())
    finally:
        stack.stop()
        res['stopped_at'] = datetime.now(timezone.utc).isoformat()
    Path(a.out).write_text(json.dumps(res, indent=2) + '\n')
    print(json.dumps({k: res.get(k) for k in ('claude_exit_code', 'native_usage', 'native_model_usage', 'before', 'after',
                                                'all_categories_match_result_usage', 'all_categories_match_model_usage_sum',
                                                'attribution_only_child_session', 'loki_events_for_session')}, indent=1))
    return 0 if verdict(res)['passed'] else 1


def verdict(res):
    """Strict acceptance (tightened after review): per-category delta equals the native result usage,
    the before snapshot is empty, and the only session.id seen is the child's."""
    checks = {'result_usage_equal_all_categories': bool(res.get('all_categories_match_result_usage')),
              'before_empty': res.get('before') == {} and res.get('before_series_count') == 0,
              'only_child_session_id': bool(res.get('attribution_only_child_session')),
              'claude_exit_zero': res.get('claude_exit_code') == 0}
    return {'checks': checks, 'passed': all(checks.values())}


if __name__ == '__main__':
    sys.exit(main())
