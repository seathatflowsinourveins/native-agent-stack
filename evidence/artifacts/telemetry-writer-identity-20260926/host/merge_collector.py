#!/usr/bin/env python3
"""Merge the repository's writer-identity metrics processing into this host's collector.yaml (local integration).

Keeps every host-specific part (receivers, ports, http_check targets, exporters, extensions, logs pipelines) and
takes from the repository only: processors.groupbyattrs/session, processors.transform/privacy.metric_statements,
processors.delta_to_cumulative (replacing the deprecated deltatocumulative alias) and the metrics pipeline's
processor list. Refuses when the result would differ from the host file anywhere else.
"""
import argparse
import copy
import sys
from pathlib import Path

import yaml

OWNED_PROCESSORS = ('groupbyattrs/session', 'delta_to_cumulative', 'deltatocumulative')


def merge(host, repo):
    out = copy.deepcopy(host)
    processors = out.setdefault('processors', {})
    for name in OWNED_PROCESSORS:
        processors.pop(name, None)
    processors['groupbyattrs/session'] = copy.deepcopy(repo['processors']['groupbyattrs/session'])
    processors['delta_to_cumulative'] = copy.deepcopy(repo['processors']['delta_to_cumulative'])
    processors['transform/privacy']['metric_statements'] = copy.deepcopy(
        repo['processors']['transform/privacy']['metric_statements'])
    out['service']['pipelines']['metrics']['processors'] = list(repo['service']['pipelines']['metrics']['processors'])
    return out


def strip_owned(config):
    """The config with every part this merge owns removed, for the 'nothing else changed' check."""
    c = copy.deepcopy(config)
    for name in OWNED_PROCESSORS:
        c.get('processors', {}).pop(name, None)
    c['processors']['transform/privacy'].pop('metric_statements', None)
    c['service']['pipelines']['metrics'].pop('processors', None)
    return c


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', type=Path, required=True)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    host = yaml.safe_load(args.host.read_text())
    repo = yaml.safe_load(args.repo.read_text())
    merged = merge(host, repo)
    if strip_owned(merged) != strip_owned(host):
        sys.exit('refusing: the merge would change host collector settings outside the metrics processing it owns')
    if repo['processors']['transform/privacy'].get('log_statements') != host['processors']['transform/privacy'].get(
            'log_statements'):
        print('note: host transform/privacy log_statements differ from the repository; they are left unchanged')
    args.output.write_text(yaml.safe_dump(merged, sort_keys=False, width=4096))
    changed = merged != host
    print('collector merge:', 'changes the metrics processing' if changed else 'no change (already applied)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
