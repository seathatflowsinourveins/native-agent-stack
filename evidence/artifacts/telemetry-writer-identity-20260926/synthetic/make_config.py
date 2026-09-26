#!/usr/bin/env python3
"""Local integration: derive a private test collector config from a repository collector.yaml.

Keeps the metrics processors under test exactly as written in the source file, and replaces only
receivers, exporters, extensions and ports so the private instance cannot touch the host services.
"""
import argparse
from pathlib import Path

import yaml


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--port-base', type=int, required=True, help='e.g. 37000: OTLP http base+318, grpc base+317, '
                        'exporter base+889, self telemetry base+888, health base+333')
    args = parser.parse_args()
    b = args.port_base
    cfg = yaml.safe_load(args.source.read_text())
    cfg['receivers'] = {'otlp': {'protocols': {'grpc': {'endpoint': f'127.0.0.1:{b + 317}'},
                                               'http': {'endpoint': f'127.0.0.1:{b + 318}'}}}}
    prom = dict(cfg['exporters']['prometheus'])
    prom['endpoint'] = f'127.0.0.1:{b + 889}'
    cfg['exporters'] = {'prometheus': prom,
                        'file/events': {'path': str(args.data / 'events.jsonl'), 'flush_interval': '1s'}}
    cfg['extensions'] = {'health_check': {'endpoint': f'127.0.0.1:{b + 333}'}}
    service = cfg['service']
    service['extensions'] = ['health_check']
    service['telemetry'] = {'logs': {'level': 'warn'},
                            'metrics': {'readers': [{'pull': {'exporter': {'prometheus': {
                                'host': '127.0.0.1', 'port': b + 888}}}}]}}
    pipelines = service['pipelines']
    metrics = pipelines['metrics']
    logs = pipelines['logs']
    service['pipelines'] = {
        'metrics': {'receivers': ['otlp'], 'processors': metrics['processors'], 'exporters': ['prometheus']},
        'logs': {'receivers': ['otlp'], 'processors': logs['processors'], 'exporters': ['file/events']},
    }
    used = set(metrics['processors']) | set(logs['processors'])
    cfg['processors'] = {name: value for name, value in cfg['processors'].items() if name in used}
    args.output.write_text(yaml.safe_dump(cfg, sort_keys=False))
    print('processors under test:', ', '.join(metrics['processors']))


if __name__ == '__main__':
    main()
