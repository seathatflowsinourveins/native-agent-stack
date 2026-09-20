"""Invoke unchanged pinned restic tests and require their native Go test results."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
from verify import HERE, digest, load


def check_test_events(text, selected):
    expected = {(item['package'], item['name']) for item in selected}
    terminal = {}
    for line in text.splitlines():
        event = json.loads(line)
        identity = (event.get('Package'), event.get('Test'))
        if identity in expected and event.get('Action') in ('pass', 'fail', 'skip'):
            if identity in terminal:
                raise ValueError('duplicate native test terminal event')
            terminal[identity] = event['Action']
    if set(terminal) != expected or any(value != 'pass' for value in terminal.values()):
        raise ValueError('selected upstream tests missing, skipped or failed')
    return [{'package':p,'name':n,'status':terminal[(p,n)]} for p,n in sorted(expected)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--reports', type=Path, required=True)
    args = parser.parse_args()
    source = args.source.resolve(strict=True)
    reports = args.reports.resolve(strict=True)
    spec = load(HERE/'upstream-source.json')
    report = {'schema_version':1,'provenance_type':'upstream-unmodified', 'status':'started',
              'started_at_utc':datetime.now(timezone.utc).isoformat(),
              'source_commit':spec['source_commit'], 'selection_sha256':digest(HERE/'upstream-source.json'),
              'scope':'Selected unchanged upstream restic Go integration/unit tests using their own upstream fixtures and temporary repositories; separate from the private-key transfer acceptance.',
              'commands':[], 'limitations':spec['execution_limitations']}
    def save():
        (reports/'upstream-tests.json').write_text(json.dumps(report,indent=2)+'\n')
    def call(label, command, timeout=30, env=None):
        record={'id':label,'argv':[v.replace(str(source),'$UPSTREAM_SOURCE') for v in command]}
        try:
            result=subprocess.run(command,cwd=source,env=env,stdin=subprocess.DEVNULL,capture_output=True,timeout=timeout)
            out,err,code=result.stdout,result.stderr,result.returncode
            record.update(exit_code=code,timeout=False)
        except subprocess.TimeoutExpired as error:
            out,err,code=error.stdout or b'',error.stderr or b'',None
            record.update(exit_code=None,timeout=True)
        for name,raw in [('stdout',out),('stderr',err)]:
            path=reports/(label+'.'+name);path.write_bytes(raw)
            record[name]={'path':path.name,'sha256':digest(path),'bytes':len(raw)}
        report['commands'].append(record);save()
        if code!=0:raise RuntimeError('upstream command failed: '+label)
        return out.decode()
    try:
        actual=call('upstream-commit',['git','rev-parse','HEAD']).strip()
        if actual!=spec['source_commit']:raise ValueError('upstream source commit differs')
        for item in spec['source_files']:
            if digest(source/item['path'])!=item['sha256']:raise ValueError('pinned upstream file differs: '+item['path'])
        if call('upstream-clean-before',['git','status','--porcelain','--untracked-files=all']).strip():
            raise ValueError('upstream test checkout is modified')
        version=call('upstream-go-version',['go','version']).strip()
        if version!='go version go1.25.10 linux/amd64':raise ValueError('Go toolchain differs from upstream-selected exact pin')
        report['native_toolchain']=version
        root=source.parent
        # No host account variables, cloud test secrets or transfer key enter Go.
        env={'PATH':os.environ['PATH'],'HOME':str(root/'upstream-home'),'LANG':'C.UTF-8',
             'GOTOOLCHAIN':'local','GOFLAGS':'-mod=readonly','GO111MODULE':'on',
             'GOPROXY':'https://proxy.golang.org','GOSUMDB':'sum.golang.org',
             'GOPATH':str(root/'upstream-go'),'GOCACHE':str(root/'upstream-go-cache'),
             'GOMODCACHE':str(root/'upstream-go-mod'),'TMPDIR':str(root/'upstream-tmp'),
             'RESTIC_TEST_TMPDIR':str(root/'upstream-tmp'),'RESTIC_TEST_INTEGRATION':'true',
             'RESTIC_TEST_CLEANUP':'true','RESTIC_TEST_FUSE':'false'}
        for name in ['HOME','GOPATH','GOCACHE','GOMODCACHE','TMPDIR']:Path(env[name]).mkdir(mode=0o700)
        events=call('upstream-go-tests',spec['test_command'],timeout=480,env=env)
        report['tests']=check_test_events(events,spec['selected_tests'])
        call('upstream-modules-verify',['go','mod','verify'],timeout=60,env=env)
        if call('upstream-clean-after',['git','status','--porcelain','--untracked-files=all']).strip():
            raise ValueError('upstream sources changed during execution')
        report['status']='passed-selected-unmodified-upstream-tests'
    except Exception as error:
        report['status']='failed';report['failure']={'type':type(error).__name__,'message':str(error)}
    finally:
        report['finished_at_utc']=datetime.now(timezone.utc).isoformat();save()
    print(json.dumps({'status':report['status'],'passed_selected_tests':len(report.get('tests',[]))}))
    return report['status']!='passed-selected-unmodified-upstream-tests'


if __name__=='__main__':sys.exit(main())
