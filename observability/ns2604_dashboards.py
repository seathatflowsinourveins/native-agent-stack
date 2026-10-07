#!/usr/bin/env python3
"""Render the ecosystem dashboards for NativeStack2604's Grafana.

The output is the install plan's config folder (evidence/artifacts/new-wsl-install-plan-20261002/config/),
from which the plan's `observability_config.py grafana` provisions them; this script never touches a host.

NativeStack2604's Grafana (127.0.0.1:21301, anonymous Viewer) has the datasources `ns2604-prometheus` and
`ns2604-loki` (plan config/grafana-datasources.yaml), and its OTel Collector's Prometheus exporter sets no
`namespace` (plan config/otel.yaml, exporters.prometheus; opentelemetry-collector-contrib v0.162.0
exporter/prometheusexporter/README.md:27, "namespace (no default)"), so its metrics carry no `ecosystem_`
prefix. The workstation's collector sets `namespace: ecosystem`
(observability/collector/collector.yaml, exporters.prometheus).
Each dashboard is rendered by its own workstation renderer and then retargeted: datasource UIDs, and metric
names in Prometheus queries only. `ecosystem_lane` is a label (resource_constant_labels), not a metric, and
stays.

usage: python3 observability/ns2604_dashboards.py [--plan-dir DIR] [--check]
"""
import argparse
import importlib.util
import json
from pathlib import Path
import re
import sys

REPO = Path(__file__).resolve().parents[1]
PLAN = REPO / 'evidence/artifacts/new-wsl-install-plan-20261002'
DATASOURCES = {'ecosystem-loki': 'ns2604-loki', 'ecosystem-prometheus': 'ns2604-prometheus'}
PROMETHEUS_UIDS = {'ecosystem-prometheus', 'ns2604-prometheus'}
METRIC_PREFIX = re.compile(r'(?<![A-Za-z0-9_:])ecosystem_(?!lane\b)')
# DAGs in NativeStack2604's DAGU_HOME on 2026-10-06; the emitter unit (plan config/ns2604-research-progress.service)
# passes the same list to observability/grand-dashboard/progress.py.
DAGS = ('restic-backup', 'restic-restore-check', 'tz-currency-check')
# Qdrant collections, the vLLM gauge, Qdrant vectors and vLLM completions: neither service runs on NativeStack2604.
NATIVE_DATA_OMIT = (3, 4, 7, 8)
NATIVE_DATA_HEADER = (
    '# Native foundation · NativeStack2604\n'
    'Real command observations and existing service data on this host. '
    'Source dates and failed observations remain visible.\n\n'
    '**Collector-fed tables:** the savings, memory and coverage tables come from the native-data collector '
    '(`observability/native-data/snapshot.py`, run by `ecosystem-native-data.timer`) and stay empty while it does '
    'not run on this host; the provider-telemetry panels below read the live OTel Collector.\n\n'
    '[Memory UI](http://127.0.0.1:29374/web) · '
    '[Code graph (Codebase Memory)](http://127.0.0.1:9749/) · '
    '[Gateway usage](http://127.0.0.1:21128/dashboard/analytics) · '
    '[Dagu (operator sign-in)](http://127.0.0.1:21080/) · '
    '[Alerts (Alertmanager)](http://127.0.0.1:21093/#/alerts) · '
    '[Prometheus targets](http://127.0.0.1:21090/targets)\n\n'
    '[Native telemetry](/d/ecosystem-native) · [Research and Dagu run history](/d/research-grand) · '
    '[Token layer](/d/token-layer) · '
    '[Upstream commands and evidence](https://github.com/seathatflowsinourveins/native-agent-stack/blob/main/docs/native-dashboard-data.md)\n\n'
    'Dagu run history needs no sign-in on the research dashboard; the Dagu UI itself keeps its operator login. '
    '[Memory and RAG practice](https://github.com/seathatflowsinourveins/native-agent-stack/blob/main/docs/memory-rag-native-practice.md)\n\n'
    '**Accounting:** native savings are estimates. Project counts can be subsets of global counts. '
    'Provider usage and cache reads are separate; never add these into one savings total. '
    'The catalog records prior acceptance, not new execution of every component.'
)


def module(relative, name):
    spec = importlib.util.spec_from_file_location(name, REPO / relative)
    loaded = importlib.util.module_from_spec(spec)
    # Keep installed configuration assets free of import-generated files.
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(loaded)
    finally:
        sys.dont_write_bytecode = previous
    return loaded


GRAFANA_POLICY = module(
    'evidence/artifacts/new-wsl-install-plan-20261002/config/observability_config.py',
    'ns2604_grafana_policy',
)


def retarget(board):
    """Swap datasource UIDs and drop the `ecosystem_` metric prefix from Prometheus queries, in place."""
    def panels(items):
        for item in items:
            yield item
            yield from panels(item.get('panels', []))

    for panel in panels(board.get('panels', [])):
        source = panel.get('datasource') or {}
        for target in panel.get('targets', []):
            effective = target.get('datasource') or source
            if 'expr' in target and (effective.get('uid') in PROMETHEUS_UIDS or effective.get('type') == 'prometheus'):
                target['expr'] = METRIC_PREFIX.sub('', target['expr'])

    def walk(value):
        if isinstance(value, dict):
            reference = value.get('datasource')
            if isinstance(reference, dict) and reference.get('uid') in DATASOURCES:
                reference['uid'] = DATASOURCES[reference['uid']]
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)
    walk(board)
    return GRAFANA_POLICY.qualify_codex_token_panels(board)


def dashboards():
    research = module('observability/grand-dashboard/render.py', 'grand_render').dashboard(DAGS)
    native = json.loads((REPO / 'observability/backends/templates/ecosystem-dashboard.json.example').read_text())
    native = retarget(native)
    health = next(panel for panel in native['panels'] if panel['id'] == 4)
    health['title'] = 'Collector HTTP response status (200 expected)'
    health['description'] = (
        'NativeStack2604\'s http_check/ecosystem receiver checks the Collector health endpoint '
        'on loopback port 21333. This panel reports that endpoint\'s HTTP status.'
    )
    foundation = module('observability/native-data/render.py', 'native_render').dashboard(
        header=NATIVE_DATA_HEADER, omit=NATIVE_DATA_OMIT)
    lanes = module('observability/lanes_dashboard.py', 'lanes_render').dashboard()
    token_layer = json.loads((PLAN / 'config/grafana-token-layer.json').read_text())
    return {
        'grafana-token-layer.json': retarget(token_layer),
        'grafana-research-grand.json': retarget(research),
        'grafana-ecosystem-native.json': native,
        'grafana-native-foundation-data.json': retarget(foundation),
        'grafana-lanes.json': retarget(lanes),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--plan-dir', type=Path, default=PLAN)
    parser.add_argument('--check', action='store_true', help='exit 1 when a committed copy differs from a fresh render')
    args = parser.parse_args()
    stale = []
    for name, board in dashboards().items():
        text = json.dumps(board, indent=2) + '\n'
        path = args.plan_dir / 'config' / name
        if args.check:
            if not path.is_file() or path.read_text() != text:
                stale.append(name)
        else:
            path.write_text(text)
            print(f'Rendered {path.relative_to(args.plan_dir)}')
    if stale:
        print('stale: ' + ', '.join(stale) + '; run python3 observability/ns2604_dashboards.py', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
