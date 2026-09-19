#!/usr/bin/env python3
"""Prepare cited native engine evidence; this is NOT an SEC or market-data packet."""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import re

from run_worker import exclusive_json, packet_facts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    summary = args.results / 'BasicTemplateFrameworkAlgorithm-summary.json'
    events = args.results / 'BasicTemplateFrameworkAlgorithm-order-events.json'
    log = args.results / 'stdout.txt'
    raw_summary, raw_events, raw_log = summary.read_bytes(), events.read_bytes(), log.read_bytes()
    native_summary = json.loads(raw_summary)
    stats = native_summary['statistics']
    configuration = native_summary['algorithmConfiguration']
    start, end = configuration['startDate'], configuration['endDate']
    if datetime.fromisoformat(start.replace('Z', '+00:00')) > datetime.fromisoformat(end.replace('Z', '+00:00')):
        parser.error('Native historical period is reversed')
    rows = json.loads(raw_events)
    counts = re.findall(r'Processing total of ([\d,]+) data points\.', raw_log.decode())
    if len(counts) != 1 or not rows or not all(row.get('symbolValue') == 'SPY' for row in rows):
        parser.error('Require one completed upstream SPY baseline and nonempty order events')
    if len({row['orderId'] for row in rows}) != int(stats['Total Orders']):
        parser.error('Native event and summary order counts disagree')
    sources = [{'id': f'S{i}', 'kind': 'native_lean_simulation', 'file': name,
                'sha256': hashlib.sha256(raw).hexdigest()}
               for i, (name, raw) in enumerate([(summary.name, raw_summary), (events.name, raw_events), (log.name, raw_log)], 1)]
    facts = []
    for concept, unit in [('Total Orders', 'orders'), ('Start Equity', 'USD'),
                          ('End Equity', 'USD'), ('Total Fees', 'USD')]:
        text = str(stats[concept]).removeprefix('$')
        if not re.fullmatch(r'-?\d+(?:\.\d+)?', text) or not Decimal(text).is_finite():
            parser.error('Unexpected native number format')
        facts.append({'citation_id': f'F{len(facts)+1}', 'source_id': 'S1',
                      'concept': concept, 'value': text, 'unit': unit})
    facts.append({'citation_id': 'F5', 'source_id': 'S3', 'concept': 'Processed data points',
                  'value': counts[0].replace(',', ''), 'unit': 'data_points'})
    packet = {'status': 'ready', 'source_kind': 'lean_simulation',
              'as_of': datetime.now(timezone.utc).isoformat(),
              'artifact_prefix': summary.name.removesuffix('-summary.json'),
              'historical_period': {'start': start, 'end': end},
              'sources': sources, 'numerical_facts': facts,
              'limitations': ['Native engine result packet; not a validated strategy.',
                              'Engine build identity is not established by these result files.',
                              'Simulated historical SPY events, not broker fills or current SEC financial facts.',
                              'Short sample metrics must not be extrapolated into expected returns.']}
    packet_facts(packet)
    exclusive_json(args.out, packet)
    print(json.dumps({'status': 'ready', 'source_kind': packet['source_kind'], 'facts': len(facts),
                      'packet_sha256': hashlib.sha256(args.out.read_bytes()).hexdigest()}))


if __name__ == '__main__':
    main()
