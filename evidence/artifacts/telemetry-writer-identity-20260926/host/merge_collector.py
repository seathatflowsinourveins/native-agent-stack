#!/usr/bin/env python3
"""Merge the repository's writer-identity metrics processing into this host's collector.yaml (local integration).

Keeps every host-specific part (receivers, ports, http_check targets, exporters, extensions, logs pipelines) and
takes from the repository only: processors.groupbyattrs/session, processors.transform/privacy.metric_statements,
processors.delta_to_cumulative (replacing the deprecated deltatocumulative alias) and the metrics pipeline's
processor list. Verifies the result before returning or writing it: original statements, group settings,
processor settings and pipeline order must survive, apart from the delta processor's supported alias rename.
Refuses unsupported host customizations rather than silently replacing them with the repository profile.
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
    verify_merge(host, repo, out)
    return out


def strip_owned(config):
    """The config with every part this merge owns removed, for the 'nothing else changed' check."""
    c = copy.deepcopy(config)
    for name in OWNED_PROCESSORS:
        c.get('processors', {}).pop(name, None)
    # YAML aliases survive deepcopy. Detach the two owned mappings before removing their fields so an
    # aliased, unowned processor or pipeline remains fully visible to the preservation comparison.
    c['processors']['transform/privacy'] = copy.deepcopy(c['processors']['transform/privacy'])
    c['service']['pipelines']['metrics'] = copy.deepcopy(c['service']['pipelines']['metrics'])
    c['processors']['transform/privacy'].pop('metric_statements', None)
    c['service']['pipelines']['metrics'].pop('processors', None)
    return c


def is_subsequence(original, merged):
    """Preserve order and multiplicity; sets would hide dropped or reordered OTTL statements."""
    remaining = iter(merged)
    return all(any(item == candidate for candidate in remaining) for item in original)


def verify_merge(host, repo, merged):
    """Collector v0.161.0 runs pipeline processors and transform statements in configuration order."""
    def refuse(path):
        raise ValueError(f'refusing: {path}: the merge would lose host settings/order or add unintended processing')

    if strip_owned(merged) != strip_owned(host):
        refuse('collector settings outside the owned metrics processing')
    for name in ('groupbyattrs/session', 'delta_to_cumulative'):
        if merged['processors'][name] != repo['processors'][name]:
            refuse(f'processors.{name}')
    for name in OWNED_PROCESSORS:
        canonical = 'delta_to_cumulative' if name == 'deltatocumulative' else name
        if name in host['processors'] and host['processors'][name] != merged['processors'][canonical]:
            refuse(f'processors.{name}')

    original_groups = host['processors']['transform/privacy'].get('metric_statements', [])
    merged_groups = merged['processors']['transform/privacy']['metric_statements']
    metric_path = 'processors.transform/privacy.metric_statements'
    if merged_groups != repo['processors']['transform/privacy']['metric_statements']:
        refuse(metric_path)
    remaining = iter(merged_groups)
    for original in original_groups:
        # Match whole groups in order, including conditions/context/error_mode. Only statements may be added.
        for group in remaining:
            if isinstance(original, dict) and isinstance(group, dict):
                metadata = {key: value for key, value in original.items() if key != 'statements'}
                if (metadata == {key: value for key, value in group.items() if key != 'statements'}
                        and is_subsequence(original.get('statements', []), group.get('statements', []))):
                    break
            elif original == group:
                break
        else:
            refuse(metric_path)

    original_order = host['service']['pipelines']['metrics']['processors']
    expected_order = ['delta_to_cumulative' if name == 'deltatocumulative' else name for name in original_order]
    if 'groupbyattrs/session' not in expected_order:
        if 'transform/privacy' not in expected_order:
            refuse('service.pipelines.metrics.processors')
        expected_order.insert(expected_order.index('transform/privacy'), 'groupbyattrs/session')
    merged_order = merged['service']['pipelines']['metrics']['processors']
    if merged_order != expected_order or merged_order != repo['service']['pipelines']['metrics']['processors']:
        refuse('service.pipelines.metrics.processors')
    for name, pipeline in merged['service']['pipelines'].items():
        # Removing the deprecated alias must not leave another, otherwise unchanged pipeline dangling.
        if any(processor not in merged['processors'] for processor in pipeline.get('processors', [])):
            refuse(f'service.pipelines.{name}.processors')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', type=Path, required=True)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    host = yaml.safe_load(args.host.read_text())
    repo = yaml.safe_load(args.repo.read_text())
    try:
        merged = merge(host, repo)
    except ValueError as error:
        sys.exit(str(error))
    if repo['processors']['transform/privacy'].get('log_statements') != host['processors']['transform/privacy'].get(
            'log_statements'):
        print('note: host transform/privacy log_statements differ from the repository; they are left unchanged')
    args.output.write_text(yaml.safe_dump(merged, sort_keys=False, width=4096))
    changed = merged != host
    print('collector merge:', 'changes the metrics processing' if changed else 'no change (already applied)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
