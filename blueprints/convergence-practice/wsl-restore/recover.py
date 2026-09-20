"""Resume the frozen synthetic backup with parent-subtree restore semantics."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
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
from fixture import assert_restored,expected_manifest

BINARY_SHA='20d4142678d0d95ec11a4759def1b73fd9190abc9ca19e4b62d067c0b387e639'
OWNER='synthetic-wsl-restic-20260920'

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):
    next_file=p.with_suffix('.next');next_file.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n');next_file.replace(p)
def repository_manifest(root):
    return [{'path':p.relative_to(root).as_posix(),'sha256':digest(p),'bytes':p.stat().st_size}
            for p in sorted(root.rglob('*')) if p.is_file()]

def verify_target(target:Path,snapshot:int):
    if set(p.name for p in target.iterdir())!={'fixture'}:
        raise ValueError('parent-subtree restore has unexpected top-level paths')
    return assert_restored(target/'fixture',snapshot)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir',type=Path,required=True)
    parser.add_argument('--restic',type=Path,required=True)
    args=parser.parse_args();root=args.run_dir.expanduser().absolute();binary=args.restic.resolve(strict=True)
    if root.resolve()!=root or digest(binary)!=BINARY_SHA:raise ValueError('unexpected root or native binary')
    plan_path=Path(__file__).with_name('recovery-plan.json');plan=json.loads(plan_path.read_text())
    previous=json.loads((root/'receipt.json').read_text());owner=json.loads((root/'owner.json').read_text())
    if (owner!={'owner':OWNER,'plan_sha256':plan['original_plan_sha256'],'runner_sha256':plan['original_runner_sha256']}
        or previous['plan_sha256']!=plan['original_plan_sha256']):raise ValueError('prior owned run differs from frozen recovery plan')
    if digest(Path(__file__).with_name('fixture.py'))!=plan['fixture_source_sha256']:
        raise ValueError('fixture/oracle source changed')
    if previous['status'] not in ('prepared-awaiting-fresh-channel','failed'):
        raise ValueError('prior run is not eligible for this bounded recovery')
    required={'backup-1':0,'backup-2':0,'healthy-read-all-data':0,'wrong-password-restore':12,'corrupted-copy-read-all-data':1}
    observed={c['id']:c['exit_code'] for c in previous['commands']}
    if any(observed.get(k)!=v for k,v in required.items()):raise ValueError('required native preparation gates did not pass')
    if any(p.is_symlink() for p in root.rglob('*')):raise ValueError('owned synthetic run contains a symlink')
    key=root/'password'
    if not stat.S_ISREG(key.lstat().st_mode) or stat.S_IMODE(key.stat().st_mode)!=0o600:
        raise ValueError('task-local key is not a regular mode0600 file')
    original=json.loads((root/'public/original-repository-manifest.json').read_text())
    if repository_manifest(root/'repository')!=original:raise ValueError('healthy repository changed since preparation')
    destination=root/'corrected-recovery'
    destination.mkdir(mode=0o700)
    report={'schema_version':1,'id':'native-wsl-restic-restore-20260920','kind':'native_cli_e2e','component_ids':['restic'],
        'host_scope':{'profile':'velanext-linux-wsl2','platform':'Linux x86_64 on WSL2','import_limit':'Synthetic same-host qualification only; no Mac, legacy WSL, offhost repository or disaster-recovery inference.'},
        'recorded_at_utc':datetime.now(timezone.utc).isoformat(),'status':'started',
        'claim':'Native restic restores both exact synthetic snapshots after wrong-password and corrupted-copy failures, through a fresh SSH connection.',
        'binary_sha256':BINARY_SHA,'plan_sha256':digest(plan_path),'runner_sha256':digest(Path(__file__)),
        'prior_run_receipt_sha256':digest(root/'receipt.json'),'commands':[],'checks':[],
        'limitations':plan['limitations'],'exact_causal_lifetime_provider_tokens_saved':None}
    user=pwd.getpwuid(os.getuid()).pw_name
    def sanitize(s):return s.replace(str(root),'$RUN_DIR').replace(str(binary),'$RESTIC').replace(user,'$USER')
    env={'PATH':'/usr/bin:/bin','HOME':str(root/'home'),'TMPDIR':str(root/'tmp'),'LANG':'C.UTF-8'}
    def call(label,arguments):
        argv=[str(binary),'--no-cache','--repo',str(root/'repository'),'--password-file',str(key),*arguments]
        started=time.monotonic();code=None;out='';err='';timeout=False
        try:
            p=subprocess.run(argv,cwd=root,env=env,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=120)
            code=p.returncode;out=p.stdout;err=p.stderr
        except subprocess.TimeoutExpired as e:
            timeout=True
            out=e.stdout.decode(errors='replace') if isinstance(e.stdout,bytes) else e.stdout or ''
            err=e.stderr.decode(errors='replace') if isinstance(e.stderr,bytes) else e.stderr or ''
        report['commands'].append({'id':label,'argv':[sanitize(v) for v in argv],'exit_code':code,'timeout':timeout,
            'seconds':round(time.monotonic()-started,3),'stdout':sanitize(out),'stderr':sanitize(err)})
        save(destination/'receipt.json',report)
        if code!=0 or timeout:raise RuntimeError('native recovery command failed: '+label)
    try:
        report['checks'].append({'name':'same-host-key-regular-mode0600-and-original-repository-bytes-intact','passed':True})
        for number,snapshot in enumerate(previous['snapshots'],1):
            if number>2 or not re.fullmatch('[0-9a-f]{64}',snapshot):raise ValueError('invalid frozen snapshot identity')
            target=destination/f'restore-{number}'
            call(f'restore-{number}-parent-subtree',['restore',snapshot+':'+str(root),'--target',str(target),'--verify'])
            actual=verify_target(target,number)
            save(destination/f'restored-{number}.json',actual)
            report['checks'].append({'name':f'snapshot-{number}-exact-path-type-byte-sha256-mode-equality-including-fixture-root','passed':actual==expected_manifest(number)})
        if len(previous['snapshots'])!=2:raise ValueError('expected exactly two snapshots')
        call('healthy-repository-final-read-all-data',['check','--read-data'])
        if repository_manifest(root/'repository')!=original:raise ValueError('recovery changed original repository bytes')
        report['checks'].append({'name':'healthy-repository-byte-manifest-unchanged-after-recovery','passed':True})
        report['status']='qualified-synthetic-same-host-restore'
    except Exception as e:
        report['status']='failed';report['failure']={'type':type(e).__name__,'message':sanitize(str(e))}
    finally:
        report['finished_at_utc']=datetime.now(timezone.utc).isoformat();save(destination/'receipt.json',report)
    print(json.dumps({'status':report['status'],'commands':len(report['commands']),'checks':len(report['checks'])}))
    return report['status']=='failed'
if __name__=='__main__':sys.exit(main())
