#!/usr/bin/env python3
"""One controlled interruption of an owned SSH client; no host/network outage."""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import time

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[2]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path,value):
    with path.open('x') as f:json.dump(value,f,indent=2);f.write('\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host',required=True)
    parser.add_argument('--remote-prefix',required=True)
    parser.add_argument('--private-output',type=Path,required=True)
    args=parser.parse_args()
    os.umask(0o077)
    work=args.private_output.expanduser().resolve()
    if work.exists():raise ValueError('private output must be new')
    work.mkdir(parents=True,mode=0o700)
    plan=json.loads((HERE/'plan-corrected.json').read_text())
    recipe_sources={'plan.json':'plan-corrected.json','remote.py':'remote.py','driver.py':'driver-corrected.py'}
    files={name:(HERE/source).read_bytes() for name,source in recipe_sources.items()}
    for name,metadata in plan['sources'].items():
        path=REPO/metadata['path']
        if digest(path)!=metadata['sha256']:raise ValueError('source/oracle pin drift')
        files[('source/'+name) if name!='fixture.py' else name]=path.read_bytes()
    save(work/'local-freeze.json',{'frozen_at_utc':datetime.now(timezone.utc).isoformat(),
        'base_revision':plan['base_revision'],'recipe_sources':recipe_sources,
        'files':{name:hashlib.sha256(data).hexdigest() for name,data in files.items()}})
    ssh=['/usr/bin/ssh','-T']
    for option in plan['ssh_options']:ssh+=['-o',option]
    ssh+=[args.host]
    codes={}

    def call(label,command,input_text=None):
        cp=subprocess.run(ssh+[command],input=input_text,capture_output=True,text=True,
                          timeout=25,check=False)
        save(work/(label+'.ssh.private.json'),{'argv':ssh+[command],'exit_code':cp.returncode,
             'stdout':cp.stdout,'stderr':cp.stderr})
        codes[label]=cp.returncode
        if cp.returncode:raise RuntimeError('owned SSH command failed: '+label)
        return json.loads(cp.stdout)

    def remote(label,action,*extra):
        return call(label,shlex.join(['/usr/bin/python3','-B',args.remote_prefix+'/remote.py',action,*extra]))

    stage='''import base64,json,os,pathlib,sys
os.umask(0o077)
root=pathlib.Path(sys.argv[1])
if not root.is_absolute() or root.exists() or root.is_symlink(): raise ValueError("new absolute prefix required")
if any(p.is_symlink() for p in root.parents): raise ValueError("symlink ancestor refused")
root.mkdir(parents=True,mode=0o700)
for name,data in json.load(sys.stdin).items():
 p=pathlib.PurePosixPath(name)
 if p.is_absolute() or ".." in p.parts: raise ValueError("unsafe staging name")
 target=root/name; target.parent.mkdir(parents=True,exist_ok=True)
 with target.open("xb") as f:f.write(base64.b64decode(data))
print(json.dumps({"staged":True}))
'''
    call('stage',shlex.join(['/usr/bin/python3','-c',stage,args.remote_prefix]),
         json.dumps({name:base64.b64encode(data).decode() for name,data in files.items()}))
    process=None
    result={'schema_version':1,'started_utc':datetime.now(timezone.utc).isoformat(),
            'ssh_options':plan['ssh_options'],'model_calls':0,'enclosing_agent_usage':None}
    success=False
    try:
        prepared=remote('prepare','prepare')
        if not prepared.get('frozen'):raise ValueError('remote freeze missing')
        start_command=shlex.join(['/usr/bin/python3','-B',args.remote_prefix+'/remote.py','start'])
        with (work/'job-transport.stdout').open('x') as out,(work/'job-transport.stderr').open('x') as err:
            process=subprocess.Popen(ssh+[start_command],stdin=subprocess.DEVNULL,stdout=out,stderr=err)
            save(work/'owned-client.private.json',{'pid':process.pid,'argv':ssh+[start_command]})
            deadline=time.monotonic()+plan['bounds']['readiness_seconds']
            number=0
            while True:
                if process.poll() is not None:raise ValueError('job transport exited before controlled interruption')
                number+=1
                before=remote('ready-'+str(number),'snapshot','--label','before')
                if before.get('ready'):break
                if time.monotonic()>deadline:raise TimeoutError('checkpoint readiness deadline')
                time.sleep(.1)
            if before['status']!='running' or not before['checkpoint_fsynced']:
                raise ValueError('durable checkpoint and native running status required')
            if process.poll() is not None:raise ValueError('owned job transport is no longer connected')
            # Only this Popen's local SSH client is signalled. No mux, network,
            # host, remote process, firewall or shared connection is interrupted.
            process.terminate()
            code=process.wait(timeout=5)
            save(work/'transport-disconnect.private.json',{'local_client_pid':process.pid,
                'signal':'SIGTERM','exit_code':code,'active_before_signal':True})
            if code not in (-15,255):raise ValueError('unexpected owned SSH client termination result')
            after=remote('fresh-reconnect','snapshot','--label','after')
            if before['run_id']!=after['run_id'] or before['checkpoint_sha256']!=after['checkpoint_sha256']:
                raise ValueError('fresh connection did not reconcile the same run/checkpoint')
            if after['execution_count']!=1:raise ValueError('checkpoint repeated')
            if after['status']!='running':raise ValueError('survival requires native running status before cleanup')
            retry=False
            remote('release','release',*(['--retry'] if retry else []))
            native=remote('finish','finish')
            if not native['passed'] or native['native_selected_step_retry']:
                raise ValueError('native completion without retry required')
        result.update(passed=True,native=native,transport={'active_before_signal':True,
            'controlled_local_signal':'SIGTERM','local_ssh_exit_code':code,
            'separate_nonmultiplexed_sessions':True,'fresh_connection_after_disconnect':True,
            'same_native_run_id':True,'checkpoint_effect_count_after_reconnect':1,
            'real_network_outage_or_host_restart':False,'running_verified_before_cleanup':True,
            'native_stop_or_retry_used':False},ssh_command_exit_codes=codes)
        success=True
    except Exception as exc:
        result.update(passed=False,failure={'type':type(exc).__name__,'message':str(exc)},ssh_command_exit_codes=codes)
        raise
    finally:
        if not success:
            try:result['failure_cleanup']=remote('failure-cleanup','cleanup')
            except Exception as exc:result['failure_cleanup_error']=type(exc).__name__+': '+str(exc)
        if process is not None and process.poll() is None:
            process.terminate();process.wait(timeout=5)
        result['local_owned_ssh_remaining']=process is not None and process.poll() is None
        result['finished_utc']=datetime.now(timezone.utc).isoformat()
        result['private_local_log_hashes']={p.name:digest(p) for p in sorted(work.iterdir()) if p.is_file()}
        save(work/'result.json',result)
        print(json.dumps({'passed':result.get('passed',False),'failure':result.get('failure'),
            'local_owned_ssh_remaining':result['local_owned_ssh_remaining'],
            'remote_checks':result.get('native',{}).get('checks')}))


if __name__=='__main__':main()
