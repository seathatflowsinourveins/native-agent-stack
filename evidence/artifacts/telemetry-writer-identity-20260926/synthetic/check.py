#!/usr/bin/env python3
"""Local integration: compare the two private Prometheus instances with the synthetic expected totals."""
import argparse
import json
import urllib.parse
import urllib.request


def query(base, expr, at):
    url = base + '/api/v1/query?' + urllib.parse.urlencode({'query': expr, 'time': f'{at:.3f}'})
    with urllib.request.urlopen(url, timeout=20) as response:
        body = json.load(response)
    if body.get('status') != 'success':
        raise RuntimeError(f'{expr}: {body}')
    return body['data']['result']


def by(result, label):
    return {row['metric'].get(label, ''): float(row['value'][1]) for row in result}


def pct(got, want):
    return None if not want else round(100.0 * (got - want) / want, 3)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--expected', required=True)
    parser.add_argument('--prom', action='append', required=True, help='mode=url')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    expected = json.load(open(args.expected))
    report = {'expected': expected, 'modes': {}}
    for spec in args.prom:
        mode, base = spec.split('=', 1)
        at = expected['finished_unix'] + 20
        window = '15m'
        m = {}
        m['claude_increase_anchored'] = by(query(base, 'sum by (type) (increase(ecosystem_claude_code_token_usage_tokens_total[%s] anchored))' % window, at), 'type')
        m['claude_increase'] = by(query(base, 'sum by (type) (increase(ecosystem_claude_code_token_usage_tokens_total[%s]))' % window, at), 'type')
        m['claude_resets'] = sum(by(query(base, 'sum(resets(ecosystem_claude_code_token_usage_tokens_total[%s]))' % window, at), '').values())
        m['claude_instances'] = sorted(by(query(base, 'count by (instance) (last_over_time(ecosystem_claude_code_token_usage_tokens_total[%s]))' % window, at), 'instance'))
        m['codex_increase_anchored'] = by(query(base, 'sum by (token_type) (increase(ecosystem_codex_turn_token_usage_sum[%s] anchored))' % window, at), 'token_type')
        m['codex_increase'] = by(query(base, 'sum by (token_type) (increase(ecosystem_codex_turn_token_usage_sum[%s]))' % window, at), 'token_type')
        m['codex_instances'] = sorted(by(query(base, 'count by (instance) (last_over_time(ecosystem_codex_turn_token_usage_sum[%s]))' % window, at), 'instance'))
        m['codex_feature_state_anchored'] = sum(by(query(base, 'sum(increase(ecosystem_codex_feature_state_total[%s] anchored))' % window, at), '').values())
        m['delta_to_cumulative_datapoints'] = by(query(base, 'sum by (error) (max_over_time(otelcol_deltatocumulative_datapoints[%s]))' % window, at), 'error')
        m['claude_error_pct_anchored'] = {t: pct(m['claude_increase_anchored'].get(t, 0.0), v) for t, v in expected['claude'].items()}
        m['claude_error_pct_increase'] = {t: pct(m['claude_increase'].get(t, 0.0), v) for t, v in expected['claude'].items()}
        m['codex_error_pct_anchored'] = {t: pct(m['codex_increase_anchored'].get(t, 0.0), v) for t, v in expected['codex'].items()}
        m['codex_error_pct_increase'] = {t: pct(m['codex_increase'].get(t, 0.0), v) for t, v in expected['codex'].items()}
        report['modes'][mode] = m
    with open(args.output, 'w') as handle:
        json.dump(report, handle, indent=2)
    for mode, m in report['modes'].items():
        print(f'== {mode}')
        for key in ('claude_resets', 'delta_to_cumulative_datapoints', 'claude_instances', 'codex_instances',
                    'claude_error_pct_anchored', 'claude_error_pct_increase', 'codex_error_pct_anchored',
                    'codex_error_pct_increase', 'codex_feature_state_anchored'):
            print(f'  {key}: {m[key]}')
    print('expected codex_feature_state:', expected.get('codex_feature_state'))


if __name__ == '__main__':
    main()
