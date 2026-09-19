#!/usr/bin/env python3
"""Render native configs and user units. Does not start services or alter clients."""
import argparse
import json
import os
from pathlib import Path
import secrets


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for option in ['tools-root','config-root','data-root','unit-root']:
        p.add_argument('--'+option, type=Path, required=True)
    a = p.parse_args()
    # These tokens are replaced by this renderer, never by YAML/systemd implicitly.
    paths = {k.upper(): str(v.resolve()) for k,v in vars(a).items()}
    if any(any(c in value for c in "\n\r'\"% ") for value in paths.values()):
        p.error('Use absolute paths without spaces, quotes, percent signs, or newlines.')
    here = Path(__file__).resolve().parent
    for dest in [a.config_root,a.data_root,a.unit_root]:
        dest.mkdir(parents=True,exist_ok=True)
    pins = json.loads((here/'pins.json').read_text())
    versions = {i['id']:i['version'] for i in pins['components']}
    for name in versions:
        (a.data_root/f'ecosystem-{name}').mkdir(mode=0o700,exist_ok=True)
    for template in (here/'templates').glob('*.example'):
        text=template.read_text()
        for k,v in paths.items(): text=text.replace('@'+k+'@',v)
        name=template.name.removesuffix('.example')
        parent=a.config_root
        if name=='ecosystem-dashboard.json': parent/= 'ecosystem-grafana-dashboards'
        elif name=='ecosystem-grafana-datasources.yml': parent/= 'ecosystem-grafana-provisioning/datasources'
        elif name=='ecosystem-grafana-dashboards.yml': parent/= 'ecosystem-grafana-provisioning/dashboards'
        parent.mkdir(parents=True,exist_ok=True)
        (parent/name).write_text(text)
    fixture=a.config_root/'acceptance-targets.json'
    if not fixture.exists(): fixture.write_text('[]\n')
    env=a.config_root/'ecosystem-grafana.env'
    if not env.exists():
        fd=os.open(env,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'w') as f:
            f.write('GF_SECURITY_ADMIN_USER=ecosystem-admin\n')
            f.write('GF_SECURITY_ADMIN_PASSWORD='+secrets.token_urlsafe(32)+'\n')
            f.write('GF_SECURITY_SECRET_KEY='+secrets.token_urlsafe(48)+'\n')
    env.chmod(0o600)
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
        (a.unit_root/f'ecosystem-{name}.service').write_text(text)
    print('Rendered five native service configurations. Grafana credentials remain in the private environment file.')


if __name__=='__main__': main()
