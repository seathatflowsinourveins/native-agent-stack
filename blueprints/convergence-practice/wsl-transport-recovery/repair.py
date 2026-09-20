#!/usr/bin/env python3
"""Reconcile the retained failed attempt once; never claim transport survival."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shlex
import subprocess

HERE=Path(__file__).resolve().parent


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path,value):
    with path.open('x') as f:json.dump(value,f,indent=2);f.write('\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host',required=True)
    parser.add_argument('--remote-prefix',required=True)
    parser.add_argument('--original-private-output',type=Path,required=True)
    args=parser.parse_args()
    original=args.original_private_output.resolve(strict=True)
    old=json.loads((original/'result.json').read_text())
    disconnect=json.loads((original/'transport-disconnect.private.json').read_text())
    after=json.loads((original/'diagnostic-reconnect.private.json').read_text())
    before_candidates=[]
    for p in original.glob('ready-*.ssh.private.json'):
        item=json.loads(json.loads(p.read_text())['stdout'])
        if item.get('ready'):before_candidates.append(item)
    if len(before_candidates)!=1:raise ValueError('exactly one original ready snapshot required')
    before=before_candidates[0]
    if old['passed'] or old['failure']['message']!='expected owned SSH client SIGTERM exit':
        raise ValueError('unexpected failure; this repair does not apply')
    if disconnect['signal']!='SIGTERM' or disconnect['exit_code']!=255 or not disconnect['active_before_signal']:
        raise ValueError('unexpected controlled transport observation')
    if (before['status']!='running' or after['status']!='aborted' or
        before['run_id']!=after['run_id'] or before['checkpoint_sha256']!=after['checkpoint_sha256']):
        raise ValueError('same-run checkpoint reconciliation failed')
    work=original/'repair';work.mkdir(mode=0o700)
    save(work/'freeze.json',{'frozen_at_utc':datetime.now(timezone.utc).isoformat(),
        'repair_source_sha256':sha(HERE/'repair.py'),'repair_plan_sha256':sha(HERE/'repair-plan.json'),
        'original_plan_sha256':sha(HERE/'plan.json'),
        'private_preconditions':{n:sha(original/n) for n in ['result.json','transport-disconnect.private.json','diagnostic-reconnect.private.json','local-freeze.json']}})
    plan=json.loads((HERE/'plan.json').read_text())
    ssh=['/usr/bin/ssh','-T']
    for option in plan['ssh_options']:ssh+=['-o',option]
    ssh+=[args.host]
    codes={}

    def call(label,command):
        cp=subprocess.run(ssh+[command],capture_output=True,text=True,timeout=30,check=False)
        save(work/(label+'.private.json'),{'argv':ssh+[command],'exit_code':cp.returncode,
              'stdout':cp.stdout,'stderr':cp.stderr})
        codes[label]=cp.returncode
        if cp.returncode:raise RuntimeError('repair native command failed: '+label)
        return json.loads(cp.stdout)

    remote=['/usr/bin/python3','-B',args.remote_prefix+'/remote.py']
    result={'schema_version':1,'started_utc':datetime.now(timezone.utc).isoformat(),
            'initial_attempt_passed':False,'transport_survival_qualified':False,
            'controlled_transport_interruptions':1,'diagnostic_repairs':1}
    try:
        call('native-selected-finalizer-retry',shlex.join(remote+['release','--retry']))
        native=call('same-run-finish',shlex.join(remote+['finish']))
        code='''import json,pathlib,sys
root=pathlib.Path(sys.argv[1]);ready=json.loads((root/"retry-ready.json").read_text())
finalizer_absent=not pathlib.Path("/proc",str(ready["pid"])).exists()
owned_unix_listeners=0
for line in pathlib.Path("/proc/net/unix").read_text().splitlines()[1:]:
 fields=line.split()
 if len(fields)>7 and fields[7].startswith(str(root)+"/") and int(fields[3],16)&0x10000:owned_unix_listeners+=1
result={"retry_finalizer_absent":finalizer_absent,"owned_prefix_unix_listeners":owned_unix_listeners}
print(json.dumps(result))
if not finalizer_absent or owned_unix_listeners:raise SystemExit(1)
'''
        cleanup=call('retry-finalizer-cleanup',shlex.join(['/usr/bin/python3','-c',code,args.remote_prefix]))
        if not native['passed'] or native['checkpoint_sha256']!=before['checkpoint_sha256']:
            raise ValueError('repair outcome differs from original checkpoint oracle')
        result.update(passed=True,same_run_recovery_qualified=True,native=native,cleanup=cleanup,
            transport={'client_active_before_signal':True,'controlled_signal':'SIGTERM',
                'local_client_exit_code':255,'fresh_independent_reconnect':True,
                'explicit_native_stop_after_harness_failure':True,'same_run_reconciled':True,
                'checkpoint_effect_count_after_reconnect':1,'same_native_run_id':True,
                'initial_native_status':'running','reconnected_native_status':'aborted',
                'final_native_status':'succeeded'})
    except Exception as exc:
        result.update(passed=False,failure={'type':type(exc).__name__,'message':str(exc)})
        raise
    finally:
        result['ssh_command_exit_codes']=codes
        result['finished_utc']=datetime.now(timezone.utc).isoformat()
        result['private_evidence_hashes']={p.name:sha(p) for p in sorted(work.iterdir()) if p.is_file()}
        save(work/'result.json',result)
        print(json.dumps({'passed':result.get('passed',False),
            'same_run_recovery_qualified':result.get('same_run_recovery_qualified',False),
            'transport_survival_qualified':False,'failure':result.get('failure'),
            'native_checks':result.get('native',{}).get('checks'),'cleanup':result.get('cleanup')}))


if __name__=='__main__':main()
