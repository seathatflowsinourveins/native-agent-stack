#!/usr/bin/env python3
"""Install only the grand dashboard and metadata emitter units; do not start them."""
import argparse
from pathlib import Path
import subprocess
import sys


def install(repo, config, units, data, dagu_bin=None, dagu_home=None):
    if (dagu_bin is None) != (dagu_home is None):
        raise ValueError('Dagu binary and home must be supplied together')
    paths=[Path(p).resolve() for p in (repo,config,units,data)]
    optional=[Path(p).resolve() for p in (dagu_bin,dagu_home)] if dagu_bin is not None else []
    if any(any(c in str(p) for c in '\n\r\t %\"\'\\$') for p in paths + optional):
        raise ValueError('unit paths require no whitespace, percent signs or quotes')
    if optional and (not optional[0].is_file() or not optional[1].is_dir()):
        raise ValueError('Dagu binary or home is missing')
    repo,config,units,data=paths
    units.mkdir(parents=True,exist_ok=True)
    target=config/'ecosystem-grafana-dashboards/research-grand.json'
    subprocess.run([sys.executable,str(repo/'observability/grand-dashboard/render.py'),'--output',str(target)],check=True)
    command=f'/usr/bin/python3 {repo}/observability/grand-dashboard/progress.py --repo {repo} --cache {data}/grand-dashboard/progress-cache.json'
    if optional:
        command += f' --dagu-bin {optional[0]} --dagu-home {optional[1]}'
    service='[Unit]\nDescription=Publish public research progress to local Loki\nAfter=ecosystem-loki.service\n\n[Service]\nType=oneshot\nUMask=0077\nNoNewPrivileges=true\nTimeoutStartSec=20\nExecStart='+command+'\n'
    timer='[Unit]\nDescription=Refresh research checkpoint dashboard\n\n[Timer]\nOnStartupSec=15\nOnUnitInactiveSec=30\nAccuracySec=5\nUnit=ecosystem-research-progress.service\n\n[Install]\nWantedBy=timers.target\n'
    (units/'ecosystem-research-progress.service').write_text(service)
    (units/'ecosystem-research-progress.timer').write_text(timer)
    print('Installed dashboard and two units; service activation remains explicit.')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('repo','config','units','data'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--dagu-bin',type=Path);p.add_argument('--dagu-home',type=Path)
    a=p.parse_args();install(a.repo,a.config,a.units,a.data,a.dagu_bin,a.dagu_home)
