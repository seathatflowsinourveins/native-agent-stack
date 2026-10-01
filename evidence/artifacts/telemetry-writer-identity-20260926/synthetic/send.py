#!/usr/bin/env python3
"""Local integration (synthetic fixture): replay concurrent Claude-like and Codex-like OTLP metric writers.

Sends the same token values to two private collectors:
  old  -- the pre-fix client shape: Claude data points carry no session.id (OTEL_METRICS_INCLUDE_SESSION_ID=false)
          and Codex resources carry no service.instance.id;
  new  -- the post-fix shape: session.id on Claude data points (the upstream default) and a per-process
          service.instance.id on each Codex resource (what the identity launcher adds).
Everything else mirrors what the pinned clients emit (Claude cumulative sums with extra attribution attributes
such as agent.name and mcp_server.name; Codex delta histograms/sums with low-cardinality tags, some of which the
collector allowlist drops). Writes the expected totals as JSON. Not a model run and not host evidence.
"""
import argparse
import json
import time
import urllib.request

TICK = 5.0
TICKS = 30
CLAUDE_TYPES = {'input': 3, 'output': 50, 'cacheRead': 4000, 'cacheCreation': 700}
CODEX_TYPES = ('input', 'cached_input', 'output', 'reasoning_output', 'total')


def attrs(mapping):
    return [{'key': k, 'value': {'stringValue': v}} for k, v in mapping.items()]


def post(endpoint, payload):
    request = urllib.request.Request(endpoint + '/v1/metrics', data=json.dumps(payload).encode(),
                                     headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(request, timeout=10) as response:
        response.read()


class ClaudeProcess:
    """Cumulative counters; every export repeats every stream seen so far (like the OTel JS SDK)."""

    def __init__(self, name, first, last, sessions, extra_key, extra_values):
        self.name, self.first, self.last = name, first, last
        self.sessions = sessions  # list of (from_tick, session_id)
        self.extra_key, self.extra_values = extra_key, extra_values
        self.streams = {}  # key -> [start_ns, value]

    def session_at(self, tick):
        current = None
        for start, session in self.sessions:
            if tick >= start:
                current = session
        return current

    def record(self, tick, now_ns, expected):
        session = self.session_at(tick)
        for i, variant in enumerate(self.extra_values):
            for token_type, per_call in CLAUDE_TYPES.items():
                value = per_call * (1 + (tick + i) % 3)
                key = (session, token_type, variant)
                stream = self.streams.setdefault(key, [now_ns - 2_000_000_000, 0])
                stream[1] += value
                expected['claude'][token_type] = expected['claude'].get(token_type, 0) + value

    def payload(self, now_ns, mode):
        # Without session.id (old mode) the SDK keeps one stream per remaining attribute set, so a /clear
        # continues the same stream; merge the per-session streams the same way.
        merged = {}
        for (session, token_type, variant), (start_ns, value) in self.streams.items():
            key = (session if mode == 'new' else None, token_type, variant)
            if key in merged:
                merged[key] = [min(merged[key][0], start_ns), merged[key][1] + value]
            else:
                merged[key] = [start_ns, value]
        points = []
        for (session, token_type, variant), (start_ns, value) in merged.items():
            labels = {'user.id': 'synthetic-installation', 'organization.id': 'synthetic-org', 'terminal.type': 'tmux',
                      'app.version': '2.1.283', 'type': token_type, 'model': 'claude-opus-5-5[1m]',
                      'query_source': 'subagent' if self.extra_key == 'agent.name' else 'main', 'effort': 'max',
                      self.extra_key: variant}
            if session is not None:
                labels['session.id'] = session
            points.append({'attributes': attrs(labels), 'startTimeUnixNano': str(start_ns),
                           'timeUnixNano': str(now_ns), 'asDouble': float(value)})
        resource = {'service.name': 'claude-code', 'service.version': '2.1.283', 'os.type': 'linux',
                    'host.arch': 'amd64'}
        return {'resourceMetrics': [{'resource': {'attributes': attrs(resource)}, 'scopeMetrics': [{
            'scope': {'name': 'com.anthropic.claude_code', 'version': '2.1.283'},
            'metrics': [{'name': 'claude_code.token.usage', 'unit': 'tokens', 'sum': {
                'aggregationTemporality': 2, 'isMonotonic': True, 'dataPoints': points}}]}]}]}


class CodexProcess:
    """Delta temporality: each export covers (previous export, now] and carries only streams with measurements."""

    def __init__(self, name, first, last, turn_ticks, scale):
        self.name, self.first, self.last, self.turn_ticks, self.scale = name, first, last, turn_ticks, scale
        self.last_ns = None
        self.instance = f'synthetic-{name}-0000-4000-8000-000000000000'

    def interval(self, now_ns):
        start_ns = self.last_ns if self.last_ns is not None else now_ns - int(TICK * 1e9)
        self.last_ns = now_ns
        return start_ns

    def payload(self, tick, start_ns, now_ns, mode, expected):
        common ={'auth_mode': 'chatgpt', 'session_source': 'exec', 'originator': 'codex_exec',
                  'model': 'gpt-6-astra', 'app.version': '0.157.1'}
        metrics = []
        if tick == self.first:
            phases = [{'attributes': attrs({**common, 'phase': phase, 'status': 'ok'}), 'startTimeUnixNano': str(start_ns),
                       'timeUnixNano': str(now_ns), 'count': '1', 'sum': 10.0 * (i + 1), 'bucketCounts': ['1', '0'],
                       'explicitBounds': [100.0]} for i, phase in enumerate(('config', 'auth', 'mcp', 'thread'))]
            metrics.append({'name': 'codex.startup.phase.duration_ms', 'unit': 'ms', 'histogram': {
                'aggregationTemporality': 1, 'dataPoints': phases}})
            features = [{'attributes': attrs({**common, 'feature': f'feature_{i}', 'value': 'true'}),
                         'startTimeUnixNano': str(start_ns), 'timeUnixNano': str(now_ns), 'asInt': '1'}
                        for i in range(6)]
            metrics.append({'name': 'codex.feature_state', 'sum': {'aggregationTemporality': 1, 'isMonotonic': True,
                                                                 'dataPoints': features}})
            expected['codex_feature_state'] = expected.get('codex_feature_state', 0) + 6
        if tick in self.turn_ticks:
            usage = {'input': 40000 * self.scale + tick, 'cached_input': 30000 * self.scale,
                     'output': 900 * self.scale + tick, 'reasoning_output': 300 * self.scale}
            usage['total'] = usage['input'] + usage['output']
            points = []
            for token_type in CODEX_TYPES:
                value = usage[token_type]
                points.append({'attributes': attrs({**common, 'token_type': token_type, 'tmp_mem_enabled': 'false'}),
                               'startTimeUnixNano': str(start_ns), 'timeUnixNano': str(now_ns), 'count': '1',
                               'sum': float(value), 'bucketCounts': ['0', '1'], 'explicitBounds': [1000.0]})
                expected['codex'][token_type] = expected['codex'].get(token_type, 0) + value
            metrics.append({'name': 'codex.turn.token_usage', 'histogram': {'aggregationTemporality': 1,
                                                                           'dataPoints': points}})
        if not metrics:
            return None
        resource = {'service.name': 'codex_exec', 'service.version': '0.157.1', 'env': 'local', 'os': 'Ubuntu'}
        if mode == 'new':
            resource['service.instance.id'] = self.instance
        return {'resourceMetrics': [{'resource': {'attributes': attrs(resource)}, 'scopeMetrics': [{
            'scope': {'name': 'codex_otel'}, 'metrics': metrics}]}]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--old', required=True, help='OTLP HTTP base URL of the collector with the old config')
    parser.add_argument('--new', required=True, help='OTLP HTTP base URL of the collector with the new config')
    parser.add_argument('--expected', required=True)
    args = parser.parse_args()
    claude = [
        ClaudeProcess('P1', 0, TICKS - 1, [(0, 'synthetic-session-1'), (15, 'synthetic-session-1b')],
                      'agent.name', ['workflow-subagent', 'general-purpose']),
        ClaudeProcess('P2', 6, TICKS - 1, [(6, 'synthetic-session-2')], 'mcp_server.name', ['serena', 'context-mode']),
        ClaudeProcess('P3', 0, 12, [(0, 'synthetic-session-3')], 'mcp_server.name', ['serena', 'jcodemunch']),
    ]
    codex = [CodexProcess('c1', 0, 11, {3, 7, 11}, 1), CodexProcess('c2', 4, 17, {8, 13, 17}, 2),
             CodexProcess('c3', 5, 14, {9, 14}, 3)]
    expected = {'claude': {}, 'codex': {}, 'started_unix': time.time(), 'tick_seconds': TICK}
    for tick in range(TICKS):
        started = time.time()
        now_ns = time.time_ns()
        for process in claude:
            if process.first <= tick <= process.last:
                process.record(tick, now_ns, expected)
                for mode, endpoint in (('old', args.old), ('new', args.new)):
                    post(endpoint, process.payload(now_ns, mode))
        for process in codex:
            if process.first <= tick <= process.last:
                start_ns = process.interval(now_ns)
                for mode, endpoint in (('old', args.old), ('new', args.new)):
                    # count the expected totals once (from the new-mode call); both modes send the same values
                    ledger = expected if mode == 'new' else {'codex': {}}
                    payload = process.payload(tick, start_ns, now_ns, mode, ledger)
                    if payload:
                        post(endpoint, payload)
        time.sleep(max(0.0, TICK - (time.time() - started)))
    expected['finished_unix'] = time.time()
    with open(args.expected, 'w') as handle:
        json.dump(expected, handle, indent=2)
    print(json.dumps(expected, indent=2))


if __name__ == '__main__':
    main()
