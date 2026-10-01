#!/usr/bin/env python3
"""Merge the repository's collector-native metric relabeling into this host's ecosystem-prometheus.yml (local integration).

Keeps every host-specific part (ports, file_sd paths, other jobs) and appends missing rules from the rendered
scrape_configs[collector-native].metric_relabel_configs, the Codex bucket drop. Existing rules retain their order.
Refuses when the host has no collector-native job or when the result would change any existing host setting/rule.
"""
import argparse
import copy
import sys
from pathlib import Path

import yaml

JOB = 'collector-native'
OWNED = 'metric_relabel_configs'


def job(config, name):
    return next((j for j in config.get('scrape_configs') or [] if j.get('job_name') == name), None)


def merge(host, rendered):
    out = copy.deepcopy(host)
    target, source = job(out, JOB), job(rendered, JOB)
    if target is None or source is None or OWNED not in source:
        raise ValueError(f'no {JOB} job with {OWNED} in both the host and the rendered config')
    original_rules, owned_rules = target.get(OWNED, []), source[OWNED]
    if not isinstance(original_rules, list) or not isinstance(owned_rules, list):
        raise ValueError(f'{JOB}.{OWNED} must be a list')
    rules = copy.deepcopy(original_rules)
    for rule in owned_rules:
        if rule not in rules:
            rules.append(copy.deepcopy(rule))
    target[OWNED] = rules
    verify_merge(host, rendered, out)
    return out


def verify_merge(host, rendered, merged):
    """Prometheus v3.15.0 model/relabel/relabel.go processes rules in their configured order."""
    original = job(host, JOB)
    original_rules = original.get(OWNED, [])
    owned_rules = job(rendered, JOB)[OWNED]
    rules = job(merged, JOB)[OWNED]
    if rules[:len(original_rules)] != original_rules:
        raise ValueError(f'the merge would change existing host {JOB}.{OWNED}')
    additions = [rule for index, rule in enumerate(owned_rules)
                 if rule not in original_rules and rule not in owned_rules[:index]]
    if rules[len(original_rules):] != additions:
        raise ValueError(f'the merge must append only missing owned {JOB}.{OWNED} rules in order')

    # Restore the verified prefix, including an originally absent key, then compare every other host setting.
    restored = copy.deepcopy(merged)
    target = job(restored, JOB)
    if OWNED in original:
        target[OWNED] = copy.deepcopy(original_rules)
    else:
        target.pop(OWNED, None)
    if restored != host:
        raise ValueError('the merge would change host Prometheus settings outside the relabeling it owns')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', type=Path, required=True)
    parser.add_argument('--rendered', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    host = yaml.safe_load(args.host.read_text())
    try:
        merged = merge(host, yaml.safe_load(args.rendered.read_text()))
    except ValueError as error:
        sys.exit(f'refusing: {error}')
    args.output.write_text(yaml.safe_dump(merged, sort_keys=False))
    print('prometheus merge:', 'adds the Codex bucket drop' if merged != host else 'no change (already applied)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
