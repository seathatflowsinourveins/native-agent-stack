#!/usr/bin/env python3
"""Merge the repository's collector-native metric relabeling into this host's ecosystem-prometheus.yml (local integration).

Keeps every host-specific part (ports, file_sd paths, other jobs) and takes from the rendered repository config only
scrape_configs[collector-native].metric_relabel_configs, the Codex bucket drop. Refuses when the host has no
collector-native job or when the result would differ from the host file anywhere else.
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
    target[OWNED] = copy.deepcopy(source[OWNED])
    return out


def strip_owned(config):
    c = copy.deepcopy(config)
    (job(c, JOB) or {}).pop(OWNED, None)
    return c


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
    if strip_owned(merged) != strip_owned(host):
        sys.exit('refusing: the merge would change host Prometheus settings outside the relabeling it owns')
    args.output.write_text(yaml.safe_dump(merged, sort_keys=False))
    print('prometheus merge:', 'adds the Codex bucket drop' if merged != host else 'no change (already applied)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
