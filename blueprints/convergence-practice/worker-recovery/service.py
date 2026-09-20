"""Only uniquely owned transient user services; no persistent configuration."""
import os
from pathlib import Path
import re
import subprocess
import time

PROPERTIES='Id,Type,ActiveState,SubState,Result,MainPID,ControlGroup,KillMode,SendSIGKILL,TimeoutStopUSec,Restart,NRestarts,ExecMainCode,ExecMainStatus'


def validate_unit(unit):
    if re.fullmatch(r'foundation-recovery-[0-9a-f]{12}-(initial|resumed|probe|readiness)',unit) is None:
        raise ValueError('only_uniquely_owned_recovery_units_allowed')
    return unit


def service_command(unit,command,environment_names=None):
    validate_unit(unit)
    # Some WSL variables (for example PROGRAMFILES(X86)) are not valid systemd
    # environment names. Native paths and ordinary variables remain unchanged.
    names=sorted((name for name in os.environ if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',name))
                 if environment_names is None else environment_names)
    if not all(re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',name) for name in names):
        raise ValueError('invalid_environment_name')
    return ['systemd-run','--user','--wait','--pipe','--quiet','--same-dir','--expand-environment=no',
            '--unit='+unit,'--property=Type=exec','--property=RuntimeMaxSec=300s',
            '--property=TimeoutStopSec=2s','--property=KillMode=control-group',
            '--property=SendSIGKILL=yes','--property=Restart=no',
            *['--setenv='+name for name in names],*command]


def show(unit):
    validate_unit(unit)
    result=subprocess.run(['systemctl','--user','show',unit+'.service','--property='+PROPERTIES],capture_output=True,text=True,check=True)
    return dict(line.split('=',1) for line in result.stdout.splitlines() if '=' in line)


def members(group):
    if not group:return []
    root=Path('/sys/fs/cgroup')
    target=(root/group.lstrip('/')).resolve()
    if not target.is_relative_to(root):raise ValueError('invalid_cgroup_path')
    if not target.exists():return []
    result=set()
    for path in target.rglob('cgroup.procs'):
        try:result.update(int(x) for x in path.read_text().split())
        except FileNotFoundError:pass
    return sorted(result)


def kill_main(unit):
    before=show(unit)
    if int(before.get('MainPID','0'))<=0 or before.get('KillMode')!='control-group':
        raise RuntimeError('owned_main_not_ready')
    before_members=members(before['ControlGroup'])
    command=['systemctl','--user','kill','--kill-whom=main','--signal=SIGKILL',unit+'.service']
    result=subprocess.run(command,capture_output=True,text=True,check=True)
    return {'command':command,'exit_code':result.returncode,'before':before,'before_members':before_members}


def wait_empty(group,timeout=15):
    deadline=time.monotonic()+timeout
    while members(group):
        if time.monotonic()>deadline:raise TimeoutError('owned_cgroup_not_empty')
        time.sleep(.05)
    return []


def cleanup(unit):
    current=show(unit)
    stop_needed=current.get('ActiveState') in ('active','activating','deactivating')
    if stop_needed:subprocess.run(['systemctl','--user','stop',unit+'.service'],capture_output=True,text=True,check=True)
    after=show(unit)
    remaining=wait_empty(current.get('ControlGroup',''))
    subprocess.run(['systemctl','--user','reset-failed',unit+'.service'],capture_output=True,text=True,check=False)
    return {'stop_needed':stop_needed,'after':after,'remaining_members':remaining}
