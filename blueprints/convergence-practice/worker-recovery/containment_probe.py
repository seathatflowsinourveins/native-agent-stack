#!/usr/bin/env python3
"""Native deterministic detached-descendant containment; never calls a model."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import uuid
from service import service_command,show,members,kill_main,wait_empty,cleanup


def write(path,value):path.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')


def identity(pid):
    try:
        fields=Path('/proc/'+str(pid)+'/stat').read_text().rsplit(')',1)[1].split()
        return {'state':fields[0],'start_ticks':fields[19]}
    except (FileNotFoundError,ProcessLookupError):return None


def same_alive(record):
    now=identity(record['pid'])
    return now is not None and now['state']!='Z' and now['start_ticks']==record['start_ticks']


def fixture(root):
    signal.signal(signal.SIGTERM,signal.SIG_IGN)
    role='main'
    if os.fork()==0:
        os.setsid();role='detached-child'
    record={'role':role,'pid':os.getpid(),'pgid':os.getpgid(0),'sid':os.getsid(0),**identity(os.getpid()),'cgroup':Path('/proc/self/cgroup').read_text(),'ignores_term':True}
    write(root/(role+'.json'),record)
    while True:signal.pause()


def run(root):
    root.mkdir(parents=True,exist_ok=False,mode=0o700)
    unit='foundation-recovery-'+uuid.uuid4().hex[:12]+'-probe'
    command=service_command(unit,[sys.executable,str(Path(__file__).resolve()),'--fixture',str(root)])
    write(root/'command-private.json',command)
    out=(root/'stdout.txt').open('x');err=(root/'stderr.txt').open('x')
    process=subprocess.Popen(command,stdout=out,stderr=err)
    checks={};failure=None;started=time.monotonic()
    try:
        deadline=time.monotonic()+15
        while not all((root/(name+'.json')).is_file() for name in ('main','detached-child')):
            if process.poll() is not None:raise RuntimeError('service_exited_before_markers')
            if time.monotonic()>deadline:raise TimeoutError('marker_deadline')
            time.sleep(.05)
        records=[json.loads((root/(name+'.json')).read_text()) for name in ('main','detached-child')]
        before=show(unit);write(root/'before-private.json',before)
        before_members=members(before['ControlGroup']);write(root/'before-members-private.json',before_members)
        checks['native_main_identity_matches']=int(before['MainPID'])==records[0]['pid']
        checks['child_has_distinct_session']=records[1]['sid']==records[1]['pid'] and records[1]['sid']!=records[0]['sid']
        checks['both_in_owned_service_cgroup']=all(r['pid'] in before_members and before['ControlGroup'] in r['cgroup'] for r in records)
        checks['term_ignored_by_fixture']=all(r['ignores_term'] for r in records)
        if not all(checks.values()):raise RuntimeError('detached_fixture_preconditions_failed')
        write(root/'main-kill-private.json',kill_main(unit))
        process.wait(timeout=20);wait_empty(before['ControlGroup'])
        after=show(unit);write(root/'after-private.json',after)
        checks['main_native_sigkill_recorded']=after['ExecMainCode']=='2' and after['ExecMainStatus']=='9'
        checks['all_original_identities_stopped']=not any(same_alive(r) for r in records)
        checks['owned_cgroup_empty']=members(before['ControlGroup'])==[]
        checks['no_native_restart']=after['NRestarts']=='0'
    except Exception as exc:failure={'type':type(exc).__name__,'reason':str(exc)}
    finally:
        cleanup_result=cleanup(unit)
        if process.poll() is None:process.wait(timeout=10)
        out.close();err.close()
    result={'status':'passed' if failure is None and all(checks.values()) else 'failed','kind':'native_cli_deterministic_containment','model_calls':0,'checks':checks,'failure':failure,'native_launcher_exit':process.returncode,'elapsed_seconds':round(time.monotonic()-started,3),'cleanup':cleanup_result,'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    write(root/'result-private.json',result)
    print(json.dumps({'status':result['status'],'checks':checks,'model_calls':0},indent=2))
    return 0 if result['status']=='passed' else 1


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run-dir');p.add_argument('--fixture');a=p.parse_args()
    if a.fixture:fixture(Path(a.fixture))
    elif a.run_dir:raise SystemExit(run(Path(a.run_dir)))
    else:p.error('choose --run-dir or --fixture')
