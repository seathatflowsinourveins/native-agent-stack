#!/usr/bin/env python3
"""Render native configs and user units. Does not start services or alter clients."""
import argparse
import json
import os
from pathlib import Path
import re
import secrets

LOOPBACK = re.compile(r'127\.0\.0\.1:(\d+)(?!\d)')
PORT_OVERRIDES = 'port-overrides.json'


def load_port_overrides(path, error):
    """{template port: host port} from a JSON object such as {"8231": 18231}; anything else is an error."""
    try:
        raw = json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError) as exc:
        error(f'{path}: cannot read port overrides ({exc})')
    if not isinstance(raw, dict):
        error(f'{path}: port overrides must be a JSON object of "template port": host port')
    overrides = {}
    for key, value in raw.items():
        if not (isinstance(key, str) and key.isascii() and key.isdigit() and type(value) is int
                and 0 < int(key) < 65536 and 0 < value < 65536 and int(key) != value):
            error(f'{path}: {key!r}: {value!r} is not a "template port": different host port pair (1-65535)')
        overrides[int(key)] = value
    if len(set(overrides.values())) != len(overrides):
        error(f'{path}: two template ports map to the same host port')
    return overrides


def apply_port_overrides(outputs, overrides, error, roots=()):
    """Rewrite every 127.0.0.1:<template port> address in the rendered files in one pass (no chaining).

    Fails closed when an override matches no rendered address (a stale entry), when its port also appears outside
    a 127.0.0.1:<port> address (such as Grafana's http_port or Loki's listen ports, which this does not rewrite),
    or when its host port is already a rendered port that is not itself overridden. The checks ignore the
    caller's root paths (``roots``), so a directory name that contains the port's digits is not a collision."""
    texts = []
    for path, text in outputs:
        for root in sorted(roots, key=len, reverse=True): text = text.replace(root, '')
        texts.append((path, text))
    rendered = {int(port) for _, text in texts for port in LOOPBACK.findall(text)}
    for port, new in sorted(overrides.items()):
        address = rf'127\.0\.0\.1:{port}(?!\d)'
        if not any(re.search(address, text) for _, text in texts):
            error(f'port override {port}: no rendered file has a 127.0.0.1:{port} address')
        bare = [path.name for path, text in texts
                if len(re.findall(rf'(?<!\d){port}(?!\d)', text)) > len(re.findall(address, text))]
        if bare:
            error(f'port override {port}: {bare[0]} also has the port outside a 127.0.0.1:{port} address, '
                  'which this override does not rewrite')
        if new in rendered and new not in overrides:
            error(f'port override {port} -> {new}: 127.0.0.1:{new} is already a rendered address')
    def replace(match):
        return '127.0.0.1:%d' % overrides.get(int(match.group(1)), int(match.group(1)))
    return [(path, LOOPBACK.sub(replace, text)) for path, text in outputs]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for option in ['tools-root','config-root','data-root','unit-root']:
        p.add_argument('--'+option, type=Path, required=True)
    p.add_argument('--port-overrides', type=Path,
                   help='JSON object {"template port": host port} for 127.0.0.1 addresses this host moved (WSL 2 '
                        'distributions share one network namespace). It is kept as <config-root>/'+PORT_OVERRIDES+
                        ', which later renders reuse; delete that file to render the template ports again.')
    a = p.parse_args()
    # These tokens are replaced by this renderer, never by YAML/systemd implicitly.
    paths = {k.upper(): str(v.resolve()) for k,v in vars(a).items() if k!='port_overrides'}
    if any(any(c in value for c in "\n\r'\"% ") for value in paths.values()):
        p.error('Use absolute paths without spaces, quotes, percent signs, or newlines.')
    saved=a.config_root/PORT_OVERRIDES
    source=a.port_overrides or (saved if saved.exists() else None)
    overrides=load_port_overrides(source,p.error) if source else {}
    here = Path(__file__).resolve().parent
    pins = json.loads((here/'pins.json').read_text())
    versions = {i['id']:i['version'] for i in pins['components']}
    outputs=[]
    for template in (here/'templates').glob('*.example'):
        text=template.read_text()
        for k,v in paths.items(): text=text.replace('@'+k+'@',v)
        name=template.name.removesuffix('.example')
        parent=a.config_root
        if name=='ecosystem-dashboard.json': parent/= 'ecosystem-grafana-dashboards'
        elif name=='ecosystem-grafana-datasources.yml': parent/= 'ecosystem-grafana-provisioning/datasources'
        elif name=='ecosystem-grafana-dashboards.yml': parent/= 'ecosystem-grafana-provisioning/dashboards'
        elif name=='ecosystem-ntfy-alertmanager.yml':
            parent/= 'ecosystem-ntfy-templates'
            name='alertmanager.yml'
        outputs.append((parent/name,text))
    env=a.config_root/'ecosystem-grafana.env'
    cfg=str(a.config_root.resolve()); data=str(a.data_root.resolve())
    def tool(name): return str(a.tools_root.resolve()/f'ecosystem-{name}-{versions[name]}')
    commands={
      'prometheus': f'{tool("prometheus")}/prometheus --config.file={cfg}/ecosystem-prometheus.yml --storage.tsdb.path={data}/ecosystem-prometheus --storage.tsdb.retention.time=7d --storage.tsdb.retention.size=512MB --web.listen-address=127.0.0.1:19090',
      'loki': f'{tool("loki")}/loki-linux-amd64 -config.file={cfg}/ecosystem-loki.yml',
      'alertmanager': f'{tool("alertmanager")}/alertmanager --config.file={cfg}/ecosystem-alertmanager.yml --storage.path={data}/ecosystem-alertmanager --data.retention=72h --web.listen-address=127.0.0.1:19093 --cluster.listen-address=',
      'grafana': f'{tool("grafana")}/bin/grafana server --homepath={tool("grafana")} --config={cfg}/ecosystem-grafana.ini',
      'ntfy': f'{tool("ntfy")}/ntfy serve --config={cfg}/ecosystem-ntfy.yml',
    }
    for name,command in commands.items():
        text='[Unit]\nDescription=Local ecosystem '+name+'\nAfter=network.target\nStartLimitIntervalSec=60\nStartLimitBurst=3\n\n[Service]\nType=simple\nUMask=0077\nNoNewPrivileges=true\n'
        if name=='grafana': text+=f'EnvironmentFile={env.resolve()}\n'
        text+=f'WorkingDirectory={data}/ecosystem-{name}\nExecStart={command}\nRestart=on-failure\nRestartSec=5\nTimeoutStopSec=60\n\n[Install]\nWantedBy=default.target\n'
        outputs.append((a.unit_root/f'ecosystem-{name}.service',text))
    # Every override is checked against the whole render before anything is written.
    if overrides: outputs=apply_port_overrides(outputs,overrides,p.error,paths.values())
    for dest in [a.config_root,a.data_root,a.unit_root]:
        dest.mkdir(parents=True,exist_ok=True)
    for name in versions:
        (a.data_root/f'ecosystem-{name}').mkdir(mode=0o700,exist_ok=True)
    for path,text in outputs:
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(text)
    if a.port_overrides:
        saved.write_text(json.dumps({str(k):v for k,v in sorted(overrides.items())},indent=2)+'\n')
    fixture=a.config_root/'acceptance-targets.json'
    if not fixture.exists(): fixture.write_text('[]\n')
    # adaptive-paper exporters (metrics.py --file-sd) add and remove their own targets; keep what they wrote.
    paper_targets=a.config_root/'adaptive-paper-targets.json'
    if not paper_targets.exists(): paper_targets.write_text('[]\n')
    if not env.exists():
        fd=os.open(env,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'w') as f:
            f.write('GF_SECURITY_ADMIN_USER=ecosystem-admin\n')
            f.write('GF_SECURITY_ADMIN_PASSWORD='+secrets.token_urlsafe(32)+'\n')
            f.write('GF_SECURITY_SECRET_KEY='+secrets.token_urlsafe(48)+'\n')
    env.chmod(0o600)
    if overrides: print(f'Applied {len(overrides)} loopback port overrides from {source}.')
    print('Rendered five native service configurations. Grafana credentials remain in the private environment file.')


if __name__=='__main__': main()
