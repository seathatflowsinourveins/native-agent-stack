"""Two-stage, synthetic-only native restic qualification with durable receipts."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import stat
import subprocess
import sys
import time
from fixture import assert_restored, expected_manifest, materialize
from corruption import corrupt_repository_copy

BINARY_SHA = '20d4142678d0d95ec11a4759def1b73fd9190abc9ca19e4b62d067c0b387e639'
OWNER = 'synthetic-wsl-restic-20260920'


def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def now(): return datetime.now(timezone.utc).isoformat()
def save(path, value):
    temporary=path.with_suffix('.next')
    temporary.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')
    temporary.replace(path)

def private_key(path):
    descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(descriptor,'w') as stream: stream.write(os.urandom(32).hex()+'\n')

def repository_manifest(root):
    return [{'path':p.relative_to(root).as_posix(),'sha256':digest(p),'bytes':p.stat().st_size}
            for p in sorted(root.rglob('*')) if p.is_file()]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage',choices=['prepare','recover'])
    parser.add_argument('--run-dir',type=Path,required=True)
    parser.add_argument('--restic',type=Path,required=True)
    args=parser.parse_args()
    root=args.run_dir.expanduser().absolute()
    binary=args.restic.expanduser().resolve(strict=True)
    if digest(binary)!=BINARY_SHA: raise ValueError('native binary digest differs from verified pin')
    if root.resolve()!=root: raise ValueError('run directory must be canonical without symlinks')
    plan=Path(__file__).with_name('plan.json')
    frozen=json.loads(plan.read_text())
    fixture_source=Path(__file__).with_name('fixture.py')
    if digest(fixture_source)!=frozen['fixture_source_sha256']:
        raise ValueError('fixture source differs from frozen plan')
    report_path=root/'receipt.json'
    if args.stage=='prepare':
        root.mkdir(mode=0o700)
        for directory in ('public','home','tmp'): (root/directory).mkdir(mode=0o700)
        save(root/'owner.json',{'owner':OWNER,'plan_sha256':digest(plan),'runner_sha256':digest(Path(__file__))})
        report={'schema_version':1,'id':OWNER,'started_at_utc':now(),'host_profile':'velanext-linux-wsl2',
                'scope':'Synthetic task state in one isolated encrypted local repository on the qualified WSL host.',
                'binary_sha256':BINARY_SHA,'plan_sha256':digest(plan),'runner_sha256':digest(Path(__file__)),
                'status':'started','commands':[],'checks':[],'stages':[],'limits':frozen['limits'],
                'exact_causal_lifetime_provider_tokens_saved':None}
        private_key(root/'password'); private_key(root/'wrong-password')
    else:
        owner=json.loads((root/'owner.json').read_text())
        if owner!={'owner':OWNER,'plan_sha256':digest(plan),'runner_sha256':digest(Path(__file__))}:
            raise ValueError('owned frozen run marker differs')
        report=json.loads(report_path.read_text())
        if report['status']!='prepared-awaiting-fresh-channel': raise ValueError('run is not ready for recovery')
    for name in ('password','wrong-password'):
        p=root/name
        if not stat.S_ISREG(p.lstat().st_mode) or stat.S_IMODE(p.stat().st_mode)!=0o600:
            raise ValueError('task-local password file must be regular and mode0600')
    env={'PATH':'/usr/bin:/bin','HOME':str(root/'home'),'TMPDIR':str(root/'tmp'),'LANG':'C.UTF-8'}
    username=pwd.getpwuid(os.getuid()).pw_name
    def sanitize(s):
        return s.replace(str(root),'$RUN_DIR').replace(str(binary),'$RESTIC').replace(username,'$USER')
    def call(label,arguments,*,repo=None,password=None,expect_failure=False):
        argv=[str(binary),'--no-cache','--repo',str(repo or root/'repository'),'--password-file',str(password or root/'password'),*arguments]
        started=time.monotonic(); output=''; error=''; code=None; timed_out=False
        try:
            p=subprocess.run(argv,env=env,cwd=root,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=frozen['command_timeout_seconds'])
            code=p.returncode;output=p.stdout;error=p.stderr
        except subprocess.TimeoutExpired as e:
            timed_out=True
            output=e.stdout.decode(errors='replace') if isinstance(e.stdout,bytes) else e.stdout or ''
            error=e.stderr.decode(errors='replace') if isinstance(e.stderr,bytes) else e.stderr or ''
        record={'id':label,'argv':[sanitize(s) for s in argv],'exit_code':code,'timeout':timed_out,
                'expected_failure':expect_failure,'seconds':round(time.monotonic()-started,3),
                'stdout':sanitize(output),'stderr':sanitize(error)}
        report['commands'].append(record);save(report_path,report)
        if timed_out or (code==0 if expect_failure else code!=0):
            raise RuntimeError('native command did not meet its frozen exit condition: '+label)
        return output,code
    def check(name,condition):
        report['checks'].append({'name':name,'passed':bool(condition)})
        save(report_path,report)
        if not condition:raise AssertionError(name)
    report['stages'].append({'stage':args.stage,'started_at_utc':now()})
    try:
        if args.stage=='prepare':
            call('init',['init','--repository-version','2'])
            snapshots=[]
            for n in (1,2):
                materialize(root/'fixture',n)
                check(f'snapshot-{n}-matches-independent-frozen-oracle',assert_restored(root/'fixture',n)==expected_manifest(n))
                save(root/'public'/f'expected-{n}.json',expected_manifest(n))
                call(f'backup-{n}',['backup','--json','--host','synthetic-wsl-restore','--tag',f'synthetic-{n}',str(root/'fixture')])
                raw,_=call(f'snapshot-id-{n}',['snapshots','--json','--tag',f'synthetic-{n}'])
                values=json.loads(raw)
                check(f'exact-snapshot-{n}-identity',len(values)==1 and bool(re.fullmatch('[0-9a-f]{64}',values[0]['id'])))
                snapshots.append(values[0]['id'])
            report['snapshots']=snapshots
            call('healthy-read-all-data',['check','--read-data'])
            _, wrong_exit = call('wrong-password-restore',['restore',snapshots[1]+':'+str(root/'fixture'),'--target',str(root/'wrong-target'),'--verify'],password=root/'wrong-password',expect_failure=True)
            check('wrong-password-native-exit-12',wrong_exit==12)
            check('wrong-password-produced-no-files',not (root/'wrong-target').exists() or not list((root/'wrong-target').rglob('*')))
            original=repository_manifest(root/'repository')
            report['corruption']=corrupt_repository_copy(root/'repository',root/'corrupted-copy')
            _, corrupt_exit = call('corrupted-copy-read-all-data',['check','--read-data'],repo=root/'corrupted-copy',expect_failure=True)
            check('corrupted-copy-native-exit-1',corrupt_exit==1)
            check('original-repository-unchanged-by-negative-tests',repository_manifest(root/'repository')==original)
            save(root/'public'/'original-repository-manifest.json',original)
            report['status']='prepared-awaiting-fresh-channel'
        else:
            snapshots=report['snapshots']
            check('same-host-key-files-still-mode0600',all(stat.S_IMODE((root/n).stat().st_mode)==0o600 for n in ('password','wrong-password')))
            check('original-bytes-match-prior-channel',repository_manifest(root/'repository')==json.loads((root/'public'/'original-repository-manifest.json').read_text()))
            for n,snapshot in enumerate(snapshots,1):
                if not re.fullmatch('[0-9a-f]{64}',snapshot):raise ValueError('invalid frozen snapshot ID')
                target=root/f'restore-{n}'
                if target.exists():raise ValueError('restore requires a fresh owned target')
                call(f'restore-{n}-fresh-channel',['restore',snapshot+':'+str(root),'--target',str(target),'--verify'])
                if set(p.name for p in target.iterdir()) != {'fixture'}:
                    raise ValueError('parent-subtree restore has unexpected top-level paths')
                restored=assert_restored(target/'fixture',n)
                save(root/'public'/f'restored-{n}.json',restored)
                check(f'restore-{n}-paths-types-bytes-hashes-modes-match',restored==expected_manifest(n))
            call('final-healthy-read-all-data',['check','--read-data'])
            report['status']='qualified-synthetic-same-host-restore'
    except Exception as e:
        report['status']='failed';report['failure']={'type':type(e).__name__,'message':sanitize(str(e))}
    finally:
        report['stages'][-1]['finished_at_utc']=now()
        save(report_path,report)
        save(root/'public'/'receipt.json',report)
    print(json.dumps({'status':report['status'],'commands':len(report['commands']),'checks':len(report['checks'])}))
    return 1 if report['status']=='failed' else 0

if __name__=='__main__':sys.exit(main())
