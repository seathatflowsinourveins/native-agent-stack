#!/usr/bin/env python3
"""G1 proof: are the Prometheus Claude/Codex token counters valid under concurrency on this host?

Read-only. Queries the loopback Prometheus and Loki HTTP query APIs (no credentials), reads the host collector
config, one Claude settings key and the codex launcher. Starts no model call and changes nothing.

Checks over the window W = (T0, T1], T1 = now - end_offset:
  setup      Prometheus runs both features and the Codex bucket drop, the native-telemetry-integrity rules are
             loaded, the collector has the writer-identity profile, Claude sends session ids and bin/codex is the
             identity launcher (equal to the repository template when this checkout has it);
  integrity  at most --max-resets-per-series resets of any scoped Claude token/cost series (a resumed session
             restarts each of its series once) and none of an unscoped one; the collector-health scrape observed
             all of W: every up sample 1, the first and last within 1.5 scrape intervals of T0 and T1 and no gap
             longer than 1.5 intervals (a missed scrape), so its self-metrics cover the window; no
             delta_to_cumulative errors, and accepted points whenever Codex processes are compared; no unscoped
             token writers;
  claude     per writer (the session id, or the launcher id of a process without one) and type, Prometheus
             increase(... anchored) against the Loki api_request unwrap sums. A writer with api_request events
             within --edge-margin of T0 or T1 is left out: export and scrape lag can put an edge request on the
             other side of the edge in Prometheus;
  codex      every codex_exec process that started in W, has no event after T1 - --codex-settle and completed a
             turn (a Loki response.completed with output tokens, or turn tokens in Prometheus): Prometheus turn
             tokens against the Loki response.completed sums with the same service_instance_id (startup prewarm
             responses, output_token_count=0, excluded). A process missing from Prometheus is -100 percent; one
             with neither is listed, not compared (0 against 0 is no evidence);
  coverage   at least two compared Claude writers, subagent (Ultracode child) usage among them, and two compared
             Codex processes whose activity spans (first to last Loki event, at 1 s resolution up to a 10,000 s
             window) overlap;
  capacity   information only: head series, storage against the retention limit, size-based deletions in the
             last 7 days and delta_to_cumulative streams against max_streams.
Verdict: FAIL names each failed check; PASS when nothing failed, both comparisons compared something and the
coverage holds; INCONCLUSIVE otherwise (clean, but the window lacks the scenario: run it and prove again).
Writer ids appear only as 12-hex-digit sha256 prefixes. Exit 0 PASS, 1 FAIL, 2 INCONCLUSIVE.
"""
import argparse
import hashlib
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

CLAUDE = 'ecosystem_claude_code_token_usage_tokens_total'
CLAUDE_COST = 'ecosystem_claude_code_cost_usage_USD_total'
CODEX_SUM = 'ecosystem_codex_turn_token_usage_sum'
CODEX_COUNT = 'ecosystem_codex_turn_token_usage_count'
CLAUDE_TYPES = {'input': 'input_tokens', 'output': 'output_tokens', 'cacheRead': 'cache_read_tokens',
                'cacheCreation': 'cache_creation_tokens'}
CODEX_TYPES = {'input': 'input_token_count', 'output': 'output_token_count', 'cached_input': 'cached_token_count',
               'reasoning_output': 'reasoning_token_count'}
FEATURES = ('created-timestamp-zero-ingestion', 'promql-extended-range-selectors')
RULES = ('EcosystemTokenCounterResets', 'EcosystemDeltaConversionDropped', 'EcosystemUnscopedTokenWriters')
BUCKET_DROP = 'ecosystem_codex_.+_bucket;'
LAUNCHER_MARK = 'Codex telemetry identity launcher'
LAUNCHER_TEMPLATE = 'observability/collector/codex-identity-launcher.sh.example'
CLAUDE_EVENTS = '{service_name=~"claude-code|claude-code-desktop"} | event_name="api_request"'
WRITER = ' | session_id!="" or service_instance_id!=""'
CODEX_EVENTS = '{service_name="codex_exec"}'
STATE = Path(os.environ.get('XDG_STATE_HOME') or Path.home() / '.local/state') / 'native-agent-stack/g1-writer-identity'


class QueryError(Exception):
    pass


class Api:
    def __init__(self, prom, loki, log):
        self.prom, self.loki, self.log = prom.rstrip('/'), loki.rstrip('/'), log

    def get(self, url):
        try:
            with urllib.request.urlopen(url, timeout=120) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            body = error.read().decode(errors='replace')[:300]
            return {'status': 'error', 'error': f'HTTP {error.code}: {body}'}
        except (OSError, ValueError) as error:
            return {'status': 'error', 'error': str(error)}

    def status(self, path):
        body = self.get(self.prom + path)
        self.log.append({'api': 'prometheus', 'path': path, 'status': body.get('status'), 'error': body.get('error')})
        return body.get('data') or {} if body.get('status') == 'success' else {}

    def prom_query(self, expr, at):
        body = self.get(self.prom + '/api/v1/query?' + urllib.parse.urlencode({'query': expr, 'time': f'{at:.3f}'}))
        return self._result('prometheus', expr, {'time': at}, body)

    def loki_query(self, expr, at):
        body = self.get(self.loki + '/loki/api/v1/query?' + urllib.parse.urlencode(
            {'query': expr, 'time': str(int(at * 1e9)), 'limit': '5000'}))
        return self._result('loki', expr, {'time': at}, body)

    def loki_range(self, expr, start, end, step):
        body = self.get(self.loki + '/loki/api/v1/query_range?' + urllib.parse.urlencode(
            {'query': expr, 'start': str(int(start * 1e9)), 'end': str(int(end * 1e9)), 'step': f'{step}s',
             'limit': '5000'}))
        return self._result('loki', expr, {'range': [start, end, step]}, body)

    def _result(self, api, expr, when, body):
        self.log.append({'api': api, 'query': expr, **when, 'status': body.get('status'), 'error': body.get('error')})
        if body.get('status') != 'success':
            raise QueryError(body.get('error', 'unknown error'))
        return body['data']['result']


def vector(rows, *labels):
    out = {}
    for row in rows:
        key = tuple(row['metric'].get(label, '') for label in labels)
        key = key if len(labels) > 1 else key[0]
        out[key] = out.get(key, 0.0) + float(row['value'][1])
    return out


def scalar(rows):
    """The sum of an instant vector; None when it is empty (no series is not the same as zero)."""
    return sum(float(row['value'][1]) for row in rows) if rows else None


def deviation(got, want):
    if want == 0:
        return 0.0 if got == 0 else None
    return 100.0 * (got - want) / want


def within(dev, tolerance):
    return dev is not None and abs(dev) <= tolerance


def masked(writer):
    return hashlib.sha256(writer.encode()).hexdigest()[:12]


def parse_duration(text):
    match = re.fullmatch(r'(\d+)([smh])', text)
    if not match:
        raise argparse.ArgumentTypeError(f'{text!r}: use <n>s, <n>m or <n>h')
    return int(match.group(1)) * {'s': 1, 'm': 60, 'h': 3600}[match.group(2)]


def prom_range(seconds):
    return f'{int(seconds)}s'


PROM_DURATION = re.compile(r'(\d+)(ms|s|m|h|d|w|y)')
PROM_UNITS = {'ms': 0.001, 's': 1, 'm': 60, 'h': 3600, 'd': 86400, 'w': 604800, 'y': 31536000}


def prom_duration_seconds(text):
    """A Prometheus duration such as 15s or 1m30s in seconds; None when the text is not one."""
    parts = PROM_DURATION.findall(text or '')
    if not parts or ''.join(number + unit for number, unit in parts) != text:
        return None
    return sum(int(number) * PROM_UNITS[unit] for number, unit in parts)


def default_repo():
    root = Path(__file__).resolve().parents[4] if len(Path(__file__).resolve().parents) > 4 else None
    return root if root and (root / LAUNCHER_TEMPLATE).is_file() else None


# ---------------------------------------------------------------------------------------------------------- setup

def setup_checks(api, args, report):
    checks = report['setup'] = {}
    flags = api.status('/api/v1/status/flags')
    enabled = set(filter(None, str(flags.get('enable-feature', '')).split(',')))
    checks['prometheus_features'] = {'ok': all(f in enabled for f in FEATURES), 'enabled': sorted(enabled),
                                     'required': list(FEATURES)}
    config = str(api.status('/api/v1/status/config').get('yaml', ''))
    checks['prometheus_codex_bucket_drop'] = {'ok': BUCKET_DROP in config, 'regex': BUCKET_DROP}
    rules = api.status('/api/v1/rules?type=alert')
    loaded = {rule['name']: rule.get('state') for group in rules.get('groups', [])
              if group['name'] == 'native-telemetry-integrity' for rule in group['rules']}
    checks['integrity_rules'] = {'ok': all(name in loaded for name in RULES), 'loaded': loaded}
    collector = Path(args.collector_config).expanduser()
    text = collector.read_text() if collector.is_file() else ''
    markers = {'groupbyattrs/session': 'groupbyattrs/session' in text,
               'session to service.instance.id': 'attributes["session.id"]' in text and 'service.instance.id' in text,
               'aggregate_on_attributes': 'aggregate_on_attributes("sum"' in text,
               'delta_to_cumulative': re.search(r'^\s+delta_to_cumulative:', text, re.M) is not None}
    checks['collector_profile'] = {'ok': all(markers.values()), 'markers': markers}
    settings = Path(args.claude_settings).expanduser()
    value = None
    if settings.is_file():
        try:
            value = (json.loads(settings.read_text()).get('env') or {}).get('OTEL_METRICS_INCLUDE_SESSION_ID')
        except ValueError:
            value = 'unreadable'
    checks['claude_session_ids'] = {'ok': value in (None, 'true', '1'), 'OTEL_METRICS_INCLUDE_SESSION_ID': value,
                                    'note': 'unset means the upstream default, true'}
    checks['codex_launcher'] = launcher_check(Path(args.eco).expanduser() / 'bin/codex', args.repo)
    alerts = api.status('/api/v1/alerts')
    firing = sorted({a['labels'].get('alertname') for a in alerts.get('alerts', [])
                     if a.get('state') == 'firing' and a['labels'].get('alertname') in RULES})
    checks['firing_integrity_alerts'] = {'ok': not firing, 'firing': firing}


def launcher_check(launcher, repo):
    info = {'is_symlink': launcher.is_symlink()}
    if not launcher.is_file() or launcher.is_symlink():
        return dict(ok=False, **info)
    body = launcher.read_text(errors='replace')
    target = re.search(r"^exec '([^']+)' \"\$@\"$", body, re.M)
    info['marker'] = LAUNCHER_MARK in body
    info['target_exists'] = bool(target) and os.path.exists(target.group(1))
    ok = info['marker'] and info['target_exists']
    template = Path(repo) / LAUNCHER_TEMPLATE if repo else None
    if template and template.is_file() and target:
        info['equals_repository_template'] = body == template.read_text().replace('@CODEX_BIN@', target.group(1))
        ok = ok and info['equals_repository_template']
    else:
        info['equals_repository_template'] = 'not checked: no repository template (pass --repo)'
    return dict(ok=ok, **info)


# ------------------------------------------------------------------------------------------------------ integrity

SCRAPE_SLACK = 1.5  # scrape intervals: timing jitter passes; one missed scrape, a two-interval gap, does not


def collector_self_metrics(api, window, t1):
    """The collector-health scrape over W = (T0, T1]: every up sample 1, and no stretch without a sample longer than
    SCRAPE_SLACK scrape intervals, counting T0 to the first sample and the last sample to T1. min_over_time(up[W])
    alone is 1 for a few samples at the end of W, which leave the rest of W unobserved."""
    t0 = t1 - window
    targets = api.status('/api/v1/targets?state=active').get('activeTargets') or []
    intervals = [prom_duration_seconds(target.get('scrapeInterval')) for target in targets
                 if (target.get('labels') or {}).get('job') == 'collector-health']
    interval = max((seconds for seconds in intervals if seconds), default=None)
    rows = api.prom_query(f'up{{job="collector-health"}}[{prom_range(window)}]', t1)
    samples = sorted((float(when), float(value)) for row in rows for when, value in row.get('values') or [])
    times = [when for when, _ in samples]
    stretches = [later - earlier for earlier, later in zip([t0] + times, times + [t1])] if times else [float(window)]
    out = {'scrape_interval_s': interval, 'samples': len(samples),
           'min_up': min((value for _, value in samples), default=None), 'longest_gap_s': round(max(stretches), 3),
           'allowed_gap_s': None if interval is None else SCRAPE_SLACK * interval,
           'note': 'without this scrape over all of W the dropped-point count below proves nothing'}
    if interval is None:
        out['reason'] = 'no active collector-health target with a scrape interval (/api/v1/targets)'
    elif not samples:
        out['reason'] = 'no collector-health up sample in the window'
    elif out['min_up'] != 1:
        out['reason'] = 'a collector-health scrape failed (up 0)'
    elif max(stretches) > SCRAPE_SLACK * interval:
        out['reason'] = 'part of the window has no collector-health scrape'
    out['ok'] = 'reason' not in out
    return out


def integrity_checks(api, window, t1, max_resets, report):
    rng = prom_range(window)
    out = report['integrity'] = {}
    counters = f'__name__=~"{CLAUDE}|{CLAUDE_COST}"'
    worst = scalar(api.prom_query(f'max(resets({{{counters}, instance!="unscoped"}}[{rng}]))', t1)) or 0.0
    unscoped = scalar(api.prom_query(f'sum(resets({{{counters}, instance="unscoped"}}[{rng}]))', t1)) or 0.0
    out['claude_counter_resets'] = {
        'ok': worst <= max_resets and unscoped == 0, 'most_resets_of_one_scoped_series': worst,
        'allowed_per_series': max_resets, 'unscoped_resets': unscoped,
        'note': 'a resumed session keeps its session.id in a new process: one reset of each of its series'}
    out['collector_self_metrics'] = collector_self_metrics(api, window, t1)
    observed = out['collector_self_metrics']['ok']
    dropped = vector(api.prom_query(
        f'sum by (error) (increase(otelcol_deltatocumulative_datapoints{{error!=""}}[{rng}]))', t1), 'error')
    accepted = scalar(api.prom_query(
        f'sum(increase(otelcol_deltatocumulative_datapoints{{error=""}}[{rng}]))', t1))
    out['delta_to_cumulative_errors'] = {'ok': observed and sum(dropped.values()) < 0.5, 'by_error': dropped,
                                         'accepted': accepted}
    writers = vector(api.prom_query(
        f'count by (job) (last_over_time({{__name__=~"{CLAUDE}|{CODEX_COUNT}", instance="unscoped"}}[{rng}]))',
        t1), 'job')
    out['unscoped_token_writers'] = {'ok': not writers, 'series_by_job': writers}


# --------------------------------------------------------------------------------------------------------- claude

def loki_writer(labels):
    """A Loki event's writer: its session id, else its launcher service_instance_id."""
    return labels.get('session_id') or labels.get('service_instance_id') or ''


def prom_writer(instance, known):
    """The Collector sets instance to the session id or <launcher id>/<session id>; without a session id it is the
    launcher id itself."""
    last = instance.rsplit('/', 1)[-1]
    return instance if instance in known and last not in known else last


def claude_comparison(api, window, t1, margin, tolerance, report):
    rng = prom_range(window)
    read_at = t1 + margin  # every compared writer is quiet within the margin, so this reads its whole window
    loki = {}
    for prom_type, field in CLAUDE_TYPES.items():
        for row in api.loki_query(f'sum by (session_id, service_instance_id) (sum_over_time({CLAUDE_EVENTS}{WRITER}'
                                  f' | unwrap {field} | __error__="" [{rng}]))', t1):
            writer = loki_writer(row['metric'])
            loki.setdefault(writer, {}).setdefault(prom_type, 0.0)
            loki[writer][prom_type] += float(row['value'][1])
    edges = {}
    for name, edge in (('start', t1 - window), ('end', t1)):
        for row in api.loki_query(f'sum by (session_id, service_instance_id) (count_over_time({CLAUDE_EVENTS}{WRITER}'
                                  f' [{prom_range(2 * margin)}]))', edge + margin):
            if float(row['value'][1]) > 0:
                edges.setdefault(loki_writer(row['metric']), []).append(name)
    prom = {}
    rows = api.prom_query(f'sum by (instance, type) (increase({CLAUDE}{{instance!="unscoped"}}[{rng}] anchored))',
                          read_at)
    for (instance, prom_type), value in vector(rows, 'instance', 'type').items():
        writer = prom_writer(instance, loki)
        prom.setdefault(writer, {}).setdefault(prom_type, 0.0)
        prom[writer][prom_type] += value
    subagent = {}
    for instance, value in vector(api.prom_query(
            f'sum by (instance) (increase({CLAUDE}{{instance!="unscoped", query_source="subagent"}}[{rng}] anchored))',
            read_at), 'instance').items():
        writer = prom_writer(instance, loki)
        subagent[writer] = subagent.get(writer, 0.0) + value
    active = {w for w in set(prom) | set(loki) if any(prom.get(w, {}).values()) or any(loki.get(w, {}).values())}
    compared = sorted(w for w in active if w not in edges)
    writers, ok = {}, True
    for writer in compared:
        row = {}
        for prom_type in CLAUDE_TYPES:
            want = loki.get(writer, {}).get(prom_type, 0.0)
            got = prom.get(writer, {}).get(prom_type, 0.0)
            row[prom_type] = {'loki': want, 'prometheus_anchored': got, 'deviation_pct': deviation(got, want)}
            ok = ok and within(row[prom_type]['deviation_pct'], tolerance)
        writers[masked(writer)] = row
    totals = {}
    for prom_type in CLAUDE_TYPES:
        want = sum(loki.get(w, {}).get(prom_type, 0.0) for w in compared)
        got = sum(prom.get(w, {}).get(prom_type, 0.0) for w in compared)
        totals[prom_type] = {'loki': want, 'prometheus_anchored': got, 'deviation_pct': deviation(got, want)}
    plain = vector(api.prom_query(f'sum by (type) (increase({CLAUDE}{{instance!="unscoped"}}[{rng}]))', read_at),
                   'type')
    legacy = {}
    for prom_type, field in CLAUDE_TYPES.items():
        want = scalar(api.loki_query(f'sum(sum_over_time({CLAUDE_EVENTS} | session_id="" and service_instance_id=""'
                                     f' | unwrap {field} | __error__="" [{rng}]))', t1)) or 0.0
        legacy[prom_type] = {'loki_without_writer': want}
    report['claude'] = {
        'status': 'no_data' if not compared else ('ok' if ok else 'fail'), 'tolerance_pct': tolerance,
        'edge_margin_s': margin, 'prometheus_read_at_t1_plus_s': margin, 'compared_writers': len(compared),
        'left_out_at_edges': {masked(w): sorted(set(e)) for w, e in edges.items() if w in active},
        'by_writer': writers, 'totals_compared': totals,
        'information_only': {'prometheus_plain_increase_all_scoped': plain, 'legacy_loki_events_without_writer': legacy},
        'subagent_tokens_compared': sum(subagent.get(w, 0.0) for w in compared)}
    return compared


# ---------------------------------------------------------------------------------------------------------- codex

def codex_comparison(api, window, t1, now, settle, tolerance, report):
    rng = prom_range(window)
    started = vector(api.loki_query(
        f'sum by (service_instance_id) (count_over_time({CODEX_EVENTS} | event_name="codex.conversation_starts"'
        f' | service_instance_id!="" [{rng}]))', t1), 'service_instance_id')
    # Any event after T1 - settle, up to now: still running near T1, or active after the window (then its Loki
    # window sum would miss what Prometheus counted later).
    active = vector(api.loki_query(
        f'sum by (service_instance_id) (count_over_time({CODEX_EVENTS} | service_instance_id!=""'
        f' [{prom_range(now - (t1 - settle))}]))', now), 'service_instance_id')
    loki = {}
    for token_type, field in CODEX_TYPES.items():
        loki[token_type] = vector(api.loki_query(
            f'sum by (service_instance_id) (sum_over_time({CODEX_EVENTS} | event_name="codex.sse_event"'
            f' | event_kind="response.completed" | output_token_count!="0" | service_instance_id!=""'
            f' | unwrap {field} | __error__="" [{rng}]))', t1), 'service_instance_id')
    read_at, prom_rng = t1 + settle, prom_range(window + settle)
    tokens = vector(api.prom_query(
        f'sum by (instance, token_type) (increase({CODEX_SUM}{{job="codex_exec", instance!="unscoped"}}'
        f'[{prom_rng}] anchored))', read_at), 'instance', 'token_type')
    turns = vector(api.prom_query(
        f'sum by (instance) (increase({CODEX_COUNT}{{job="codex_exec", instance!="unscoped", token_type="input"}}'
        f'[{prom_rng}] anchored))', read_at), 'instance')
    # A finished process is evidence only when it completed a turn: a non-prewarm response.completed in Loki or turn
    # tokens in Prometheus. With neither, both sides read 0, and 0 against 0 says nothing about the counters.
    compared, idle = [], []
    for instance in sorted(i for i in started if i not in active):
        completed = any(loki[token_type].get(instance, 0.0) > 0 for token_type in CODEX_TYPES)
        counted = turns.get(instance, 0.0) > 0 or any(tokens.get((instance, t), 0.0) > 0 for t in CODEX_TYPES)
        (compared if completed or counted else idle).append(instance)
    processes, ok = {}, True
    totals = {t: {'loki': 0.0, 'prometheus_anchored': 0.0} for t in CODEX_TYPES}
    for instance in compared:
        row = {'prometheus_turns': turns.get(instance, 0.0)}
        for token_type in CODEX_TYPES:
            want = loki[token_type].get(instance, 0.0)
            got = tokens.get((instance, token_type), 0.0)
            totals[token_type]['loki'] += want
            totals[token_type]['prometheus_anchored'] += got
            row[token_type] = {'loki': want, 'prometheus_anchored': got, 'deviation_pct': deviation(got, want)}
            ok = ok and within(row[token_type]['deviation_pct'], tolerance)
        processes[masked(instance)] = row
    for total in totals.values():
        total['deviation_pct'] = deviation(total['prometheus_anchored'], total['loki'])
    report['codex'] = {
        'status': 'no_data' if not compared else ('ok' if ok else 'fail'), 'tolerance_pct': tolerance,
        'settle_s': settle, 'compared_processes': len(compared), 'totals': totals, 'by_process': processes,
        'not_compared_active_after_t1_minus_settle': sorted(masked(i) for i in started if i in active),
        'finished_without_a_completed_turn': sorted(masked(i) for i in idle),
        'note': 'a compared process missing from Prometheus shows prometheus 0 (-100 percent); a process with no '
                'completed turn in Loki or Prometheus is listed, not compared'}
    return compared


# ------------------------------------------------------------------------------------------- coverage and capacity

def activity_spans(api, window, t1, instances):
    """Each process's first and last Loki event in W, to `step` seconds. Loki 3.7.8 refuses more than 11,000 points
    per series, so the step is 1 s up to a 10,000 s window and coarser beyond."""
    step = max(1, math.ceil(window / 10000))
    rows = api.loki_range(f'sum by (service_instance_id) (count_over_time({CODEX_EVENTS}'
                          f' | service_instance_id!="" [{step}s]))', t1 - window, t1, step)
    spans = {}
    for row in rows:
        instance = row['metric'].get('service_instance_id')
        times = [float(ts) for ts, value in row['values'] if float(value) > 0]
        if instance in instances and times:
            first, last = spans.get(instance, (min(times), max(times)))
            spans[instance] = (min(first, min(times)), max(last, max(times)))
    return spans, step


def most_together(spans):
    """The most spans that share a stretch of time. Events in one minute are not concurrency: one process can end
    before the next starts. Spans that only touch do not overlap."""
    return max((sum(1 for start, end in spans if start <= moment < end) for moment, _ in spans), default=0)


def coverage(api, window, t1, claude_writers, codex_instances, report):
    together, step = 0, None
    if codex_instances:
        spans, step = activity_spans(api, window, t1, codex_instances)
        together = most_together(list(spans.values()))
    subagent = report.get('claude', {}).get('subagent_tokens_compared', 0.0)
    report['coverage'] = {
        'ok': len(claude_writers) >= 2 and subagent > 0 and together >= 2,
        'compared_claude_writers': len(claude_writers), 'subagent_tokens_in_compared_writers': subagent,
        'max_compared_codex_processes_active_together': together, 'codex_activity_resolution_s': step}


def capacity(api, now, report):
    def value(expr):
        try:
            return scalar(api.prom_query(expr, now))
        except QueryError:
            return None
    out = {
        'head_series': value('max(prometheus_tsdb_head_series{job="prometheus"})'),
        'blocks_bytes': value('max(prometheus_tsdb_storage_blocks_bytes{job="prometheus"})'),
        'wal_bytes': value('max(prometheus_tsdb_wal_storage_size_bytes{job="prometheus"})'),
        'retention_limit_bytes': value('max(prometheus_tsdb_retention_limit_bytes{job="prometheus"})'),
        'oldest_sample_age_s': value('time() - min(prometheus_tsdb_lowest_timestamp_seconds{job="prometheus"})'),
        'size_based_deletions_7d': value('sum(increase(prometheus_tsdb_size_retentions_total{job="prometheus"}[7d]))'),
        'delta_streams_tracked': value('max(otelcol_deltatocumulative_streams_tracked)'),
        'delta_streams_limit': value('max(otelcol_deltatocumulative_streams_limit)')}
    try:
        out['writer_series_by_job'] = vector(api.prom_query(
            'count by (job) ({__name__=~"ecosystem_.+", job=~"claude-code|claude-code-desktop|codex_exec|codex_cli_rs'
            '|codex-app-server"})', now), 'job')
    except QueryError:
        out['writer_series_by_job'] = None
    warnings = []
    used = (out['blocks_bytes'] or 0) + (out['wal_bytes'] or 0)
    if out['retention_limit_bytes'] and used > 0.8 * out['retention_limit_bytes']:
        warnings.append('storage above 80 percent of the size limit')
    if out['size_based_deletions_7d']:
        warnings.append('blocks were deleted for size, not age, in the last 7 days (retention below 7 days)')
    if out['delta_streams_limit'] and (out['delta_streams_tracked'] or 0) > 0.8 * out['delta_streams_limit']:
        warnings.append('delta_to_cumulative streams above 80 percent of max_streams')
    out['warnings'] = warnings
    out['note'] = 'information only; the verdict does not depend on it'
    report['capacity'] = out


# ----------------------------------------------------------------------------------------------------------- main

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--window', type=parse_duration, default=parse_duration('60m'))
    parser.add_argument('--end-offset', type=parse_duration, default=parse_duration('120s'),
                        help='T1 = now - end-offset, so exports and scrapes of the window are complete')
    parser.add_argument('--edge-margin', type=parse_duration, default=parse_duration('30s'),
                        help='leave out Claude writers with requests this close to T0 or T1 (export 10 s + scrape '
                             '15 s); Prometheus is read this long after T1')
    parser.add_argument('--codex-settle', type=parse_duration, default=parse_duration('90s'),
                        help='compare only codex processes without events after T1 - settle; Prometheus is read '
                             'this long after T1 (60 s export interval + scrape)')
    parser.add_argument('--tolerance', type=float, default=2.0, help='percent')
    parser.add_argument('--max-resets-per-series', type=int, default=1,
                        help='resumes of one session allowed in the window')
    parser.add_argument('--prom', default='http://127.0.0.1:19090')
    parser.add_argument('--loki', default='http://127.0.0.1:13100')
    parser.add_argument('--eco', default='~/.local/share/codex-ecosystem')
    parser.add_argument('--collector-config', default='~/.config/ecosystem-observability/collector.yaml')
    parser.add_argument('--claude-settings', default='~/.claude/settings.json')
    parser.add_argument('--repo', type=Path, default=default_repo(),
                        help='checkout whose launcher template bin/codex must equal (default: this checkout)')
    parser.add_argument('--out', type=Path, help='default: $XDG_STATE_HOME/native-agent-stack/g1-writer-identity/'
                                                 'prove-<UTC>')
    args = parser.parse_args()
    if max(args.edge_margin, args.codex_settle) > args.end_offset:
        parser.error('--edge-margin and --codex-settle must not exceed --end-offset (Prometheus is read after T1)')
    log = []
    api = Api(args.prom, args.loki, log)
    now = time.time()
    t1 = now - args.end_offset
    report = {'generated_unix': now, 'window': {'start_unix': t1 - args.window, 'end_unix': t1,
                                                'seconds': args.window}}
    failures = []
    setup_checks(api, args, report)
    failures += [f'setup.{k}' for k, v in report['setup'].items() if not v['ok']]
    try:
        integrity_checks(api, args.window, t1, args.max_resets_per_series, report)
        claude = claude_comparison(api, args.window, t1, args.edge_margin, args.tolerance, report)
        codex = codex_comparison(api, args.window, t1, now, args.codex_settle, args.tolerance, report)
        delta = report['integrity']['delta_to_cumulative_errors']
        if codex and not (delta['accepted'] or 0) > 0:
            delta['ok'] = False
            delta['reason'] = 'no accepted points while Codex processes were compared'
        failures += [f'integrity.{k}' for k, v in report['integrity'].items() if not v['ok']]
        failures += [f'{name}.prometheus_vs_loki' for name in ('claude', 'codex') if report[name]['status'] == 'fail']
        coverage(api, args.window, t1, claude, set(codex), report)
    except QueryError as error:
        failures.append(f'query_error: {error}')
    capacity(api, now, report)
    compared = all(report.get(name, {}).get('status') == 'ok' for name in ('claude', 'codex'))
    covered = report.get('coverage', {}).get('ok', False)
    report['verdict'] = 'FAIL' if failures else ('PASS' if compared and covered else 'INCONCLUSIVE')
    report['failed_checks'] = failures
    out = args.out or STATE / time.strftime('prove-%Y%m%dT%H%M%SZ', time.gmtime(now))
    old = os.umask(0o077)
    try:
        out.mkdir(parents=True, exist_ok=True)
        (out / 'report.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
        (out / 'queries.json').write_text(json.dumps(log, indent=2) + '\n')
    finally:
        os.umask(old)
    summarize(report)
    print(f'report: {out / "report.json"} (queries.json lists every API call)')
    return 0 if report['verdict'] == 'PASS' else (2 if report['verdict'] == 'INCONCLUSIVE' else 1)


def fmt(value):
    """A deviation in percent."""
    return 'n/a' if value is None else f'{value:+.2f}%'


def num(value):
    return 'n/a' if value is None else f'{value:.0f}'


def summarize(report):
    window = report['window']
    print(f"G1 prove verdict: {report['verdict']}  window {time.strftime('%H:%M:%S', time.gmtime(window['start_unix']))}"
          f"-{time.strftime('%H:%M:%SZ', time.gmtime(window['end_unix']))} ({window['seconds'] // 60} min)")
    for name, check in report.get('setup', {}).items():
        print(f"  setup {name}: {'ok' if check['ok'] else 'MISSING'}")
    for name, check in report.get('integrity', {}).items():
        detail = {k: v for k, v in check.items() if k not in ('ok', 'note')}
        print(f"  integrity {name}: {'ok' if check['ok'] else 'FAIL'} {json.dumps(detail, sort_keys=True)}")
    claude = report.get('claude')
    if claude:
        print(f"  claude per writer: {claude['status']} ({claude['compared_writers']} compared, "
              f"{len(claude['left_out_at_edges'])} left out for requests within {claude['edge_margin_s']} s of an edge)")
        for token_type, row in claude['totals_compared'].items():
            print(f"    {token_type}: loki {row['loki']:.0f}, increase anchored {num(row['prometheus_anchored'])} "
                  f"[{fmt(row['deviation_pct'])}]")
        for writer, row in claude['by_writer'].items():
            worst = max((abs(v['deviation_pct']) if v['deviation_pct'] is not None else float('inf'))
                        for v in row.values())
            print(f"    writer {writer}: worst deviation {'n/a' if worst == float('inf') else f'{worst:.2f}%'}")
    codex = report.get('codex')
    if codex:
        print(f"  codex per process: {codex['status']} ({codex['compared_processes']} compared, "
              f"{len(codex['not_compared_active_after_t1_minus_settle'])} still active, "
              f"{len(codex['finished_without_a_completed_turn'])} without a completed turn)")
        for token_type, total in codex['totals'].items():
            print(f"    {token_type}: loki {total['loki']:.0f}, prometheus {total['prometheus_anchored']:.0f} "
                  f"[{fmt(total['deviation_pct'])}]")
        for instance, row in codex['by_process'].items():
            devs = [v['deviation_pct'] for k, v in row.items() if isinstance(v, dict)]
            worst = max((abs(d) if d is not None else float('inf')) for d in devs)
            print(f"    process {instance}: turns {row['prometheus_turns']:.0f}, worst deviation "
                  f"{'n/a' if worst == float('inf') else f'{worst:.2f}%'}")
    cov = report.get('coverage')
    if cov:
        print(f"  coverage: {'ok' if cov['ok'] else 'not met'} {json.dumps({k: v for k, v in cov.items() if k != 'ok'})}")
    cap = report.get('capacity')
    if cap:
        shown = {k: cap[k] for k in ('head_series', 'blocks_bytes', 'wal_bytes', 'retention_limit_bytes',
                                     'size_based_deletions_7d', 'delta_streams_tracked', 'delta_streams_limit')}
        print(f"  capacity: {'WARN ' + '; '.join(cap['warnings']) if cap['warnings'] else 'ok'} {json.dumps(shown)}")
    if report['failed_checks']:
        print('  failed: ' + ', '.join(report['failed_checks']))


if __name__ == '__main__':
    sys.exit(main())
