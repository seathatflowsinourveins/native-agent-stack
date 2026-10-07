#!/usr/bin/env python3
"""Merge the repository's writer-identity metrics processing into this host's collector.yaml (local integration).

Keeps every host-specific part (receivers, ports, http_check targets, exporters, extensions, logs pipelines) and
takes from the repository only: processors.groupbyattrs/session, processors.transform/privacy.metric_statements,
processors.transform/metric_export_privacy when the profile uses it, processors.delta_to_cumulative
(replacing the deprecated deltatocumulative alias) and the metrics pipeline's
processor list. Verifies the result before returning or writing it: original statements, group settings,
processor settings and pipeline order must survive, apart from the delta processor's supported alias rename.
Refuses unsupported host customizations rather than silently replacing them with the repository profile.

Source: opentelemetry-collector-contrib v0.162.0 processor/transformprocessor/README.md
(ordered metric statements), and the Collector's service.pipelines.metrics.processors order.
"""
import argparse
import copy
import sys
from pathlib import Path

import yaml

METRIC_EXPORT_GUARD = 'transform/metric_export_privacy'
OWNED_PROCESSORS = ('groupbyattrs/session', 'delta_to_cumulative', 'deltatocumulative', METRIC_EXPORT_GUARD)


def merge(host, repo):
    out = copy.deepcopy(host)
    processors = out.setdefault('processors', {})
    for name in OWNED_PROCESSORS:
        processors.pop(name, None)
    processors['groupbyattrs/session'] = copy.deepcopy(repo['processors']['groupbyattrs/session'])
    processors['delta_to_cumulative'] = copy.deepcopy(repo['processors']['delta_to_cumulative'])
    if METRIC_EXPORT_GUARD in repo['service']['pipelines']['metrics']['processors']:
        if METRIC_EXPORT_GUARD not in repo['processors']:
            raise ValueError(f'refusing: processors.{METRIC_EXPORT_GUARD}: profile guard definition is missing')
        processors[METRIC_EXPORT_GUARD] = copy.deepcopy(repo['processors'][METRIC_EXPORT_GUARD])
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
    """Collector/Contrib v0.162.0 runs pipeline processors and transform statements in configuration order."""
    def refuse(path):
        raise ValueError(f'refusing: {path}: the merge would lose host settings/order or add unintended processing')

    if strip_owned(merged) != strip_owned(host):
        refuse('collector settings outside the owned metrics processing')
    profile_order = repo['service']['pipelines']['metrics']['processors']
    required_processors = ('groupbyattrs/session', 'delta_to_cumulative')
    if METRIC_EXPORT_GUARD in profile_order:
        required_processors += (METRIC_EXPORT_GUARD,)
    for name in required_processors:
        if merged['processors'][name] != repo['processors'][name]:
            refuse(f'processors.{name}')
    for name in OWNED_PROCESSORS:
        canonical = 'delta_to_cumulative' if name == 'deltatocumulative' else name
        if name in host['processors'] and (canonical not in merged['processors']
                                          or host['processors'][name] != merged['processors'][canonical]):
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
    if METRIC_EXPORT_GUARD in profile_order:
        # This is the sole additional processor the committed profile may insert. Conversion must see
        # already-scrubbed stream identities, and existing host order must not be silently rearranged.
        if (profile_order.count(METRIC_EXPORT_GUARD) != 1 or 'delta_to_cumulative' not in profile_order
                or profile_order.index(METRIC_EXPORT_GUARD) + 1 != profile_order.index('delta_to_cumulative')):
            refuse('service.pipelines.metrics.processors')
        if METRIC_EXPORT_GUARD not in expected_order:
            if 'delta_to_cumulative' not in expected_order:
                refuse('service.pipelines.metrics.processors')
            expected_order.insert(expected_order.index('delta_to_cumulative'), METRIC_EXPORT_GUARD)
    merged_order = merged['service']['pipelines']['metrics']['processors']
    if merged_order != expected_order or merged_order != profile_order:
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
