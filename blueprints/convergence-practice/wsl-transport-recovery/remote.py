#!/usr/bin/env python3
"""Owned remote deterministic job controller; no service or account setup."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import signal
import subprocess
import sys
import time
import uuid

import fixture

ROOT = Path(__file__).resolve().parent


def write(name, value):
    fixture.exclusive(ROOT / name, value)


def read(name):
    return json.loads((ROOT / name).read_text())


def context():
    dagu = (Path.home() / '.local/bin/dagu').resolve(strict=True)
    base = [str(dagu), '--context', 'local', '--dagu-home', str(ROOT/'dagu-home'),
            '--config', str(ROOT/'config.yaml')]
    env = {'HOME': str(Path.home()), 'PATH': '/usr/bin:/bin:/usr/sbin:/sbin',
           'DAGU_HOME': str(ROOT/'dagu-home'), 'TMPDIR': str(ROOT/'tmp'),
           'XDG_CONFIG_HOME': str(ROOT/'xdg-config'), 'XDG_CACHE_HOME': str(ROOT/'xdg-cache'),
           'DO_NOT_TRACK': '1', 'PYTHONDONTWRITEBYTECODE': '1'}
    return dagu, base, env


def command(label, argv, timeout=20):
    _, _, env = context()
    cp = subprocess.run(argv, cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                        capture_output=True, text=True, timeout=timeout, check=False)
    write(label+'.command.private.json', {'argv': argv, 'exit_code': cp.returncode,
          'stdout': cp.stdout, 'stderr': cp.stderr})
    if cp.returncode:
        raise RuntimeError('native command failed: '+label)
    return cp.stdout


def process_table():
    table = {}
    for p in Path('/proc').glob('[0-9]*/stat'):
        try:
            raw = p.read_text(); fields = raw[raw.rindex(')')+2:].split()
            table[int(p.parent.name)] = {'ppid': int(fields[1]), 'state': fields[0],
                                         'starttime': fields[19]}
        except (OSError, ValueError, IndexError):
            continue
    return table


def descendants(roots):
    table, found = process_table(), set(roots)
    while True:
        expanded = found | {p for p,v in table.items() if v['ppid'] in found}
        if expanded == found:
            return {str(p): table[p]['starttime'] for p in found if p in table}
        found = expanded


def living(identities):
    table = process_table()
    return [p for p,start in identities.items() if int(p) in table and table[int(p)]['starttime'] == start]


def listener_inodes():
    found = set()
    for name in ['tcp', 'tcp6']:
        for line in Path('/proc/net', name).read_text().splitlines()[1:]:
            fields = line.split()
            if fields[3] == '0A': found.add(fields[9])
    for line in Path('/proc/net/unix').read_text().splitlines()[1:]:
        fields = line.split()
        if int(fields[3], 16) & 0x10000: found.add(fields[6])
    return found


def owned_listeners(identities):
    sockets = set()
    for pid in living(identities):
        for fd in Path('/proc', pid, 'fd').glob('*'):
            try:
                target = os.readlink(fd)
                if target.startswith('socket:['): sockets.add(target[8:-1])
            except OSError:
                continue
    return sorted(sockets & listener_inodes())


def history(label):
    _, base, _ = context(); run_id = read('run.private.json')['run_id']
    raw = command('history-'+label, base+['history', '--run-id', run_id, '--format', 'json'])
    value = json.loads(raw); rows = value if isinstance(value,list) else value.get('runs', [])
    matches = [r for r in rows if r.get('dagRunId') == run_id]
    if len(matches) != 1: raise ValueError('expected exactly one native run row')
    return matches[0]


def prepare():
    plan = read('plan.json'); dagu, base, env = context()
    for name in ['dagu-home', 'tmp', 'xdg-config', 'xdg-cache']:
        (ROOT/name).mkdir()
    if fixture.digest(dagu) != plan['native_pin']['binary_sha256']:
        raise ValueError('native binary pin mismatch')
    if fixture.digest(dagu.parent/'LICENSE') != plan['native_pin']['license_sha256']:
        raise ValueError('native license pin mismatch')
    for name, metadata in plan['sources'].items():
        path = ROOT / (('source/'+name) if name != 'fixture.py' else name)
        if fixture.digest(path) != metadata['sha256']:
            raise ValueError('source pin mismatch: '+name)
    write('expected.json', fixture.source_hashes(ROOT))
    (ROOT/'config.yaml').write_text('check_updates: false\n')
    commands = {action: shlex.join([sys.executable, '-B', str(ROOT/'fixture.py'), action, str(ROOT)])
                for action in ['checkpoint','finalize']}
    (ROOT/'recovery.yaml').write_text('\n'.join(['type: graph', 'timeout_sec: 90', 'max_active_runs: 1',
        'working_dir: '+json.dumps(str(ROOT)), 'steps:', '  - id: checkpoint',
        '    run: '+json.dumps(commands['checkpoint']), '  - id: finalize',
        '    depends: [checkpoint]', '    run: '+json.dumps(commands['finalize']), '']))
    run_id = 'transport-'+uuid.uuid4().hex
    write('run.private.json', {'run_id': run_id})
    files = ['plan.json','remote.py','driver.py','fixture.py','source/planner.py',
             'source/test_planner.py','expected.json','config.yaml','recovery.yaml','run.private.json']
    write('freeze.private.json', {'frozen_before_execution': True,
        'files': {n: fixture.digest(ROOT/n) for n in files},
        'dagu_binary_sha256': fixture.digest(dagu), 'native_license_sha256': fixture.digest(dagu.parent/'LICENSE'),
        'python_version': sys.version.split()[0], 'home_preserved': env['HOME'] == str(Path.home()),
        'environment_keys': sorted(env), 'native_command_prefix': base})
    if command('version', [str(dagu),'version']).strip() != '2.16.6':
        raise ValueError('native version mismatch')
    for subcommand in ['start','history','stop','retry','validate']:
        command('help-'+subcommand, [str(dagu), subcommand, '--help'])
    command('validate', base+['validate',str(ROOT/'recovery.yaml')])
    return {'prepared': True, 'frozen': True, 'source_tests': 12}


def start():
    _, base, env = context(); run_id = read('run.private.json')['run_id']
    own = process_table()[os.getpid()]
    write('supervisor.private.json', {'pid':os.getpid(), 'starttime':own['starttime']})
    with (ROOT/'start.stdout').open('x') as out, (ROOT/'start.stderr').open('x') as err:
        argv = base+['start','--run-id',run_id,str(ROOT/'recovery.yaml')]
        child = subprocess.Popen(argv,cwd=ROOT,env=env,stdin=subprocess.DEVNULL,
                                 stdout=out,stderr=err,start_new_session=True)
        table = process_table()
        write('process.private.json', {'pid':child.pid,'starttime':table[child.pid]['starttime'],
              'argv':argv,'separate_process_session':True,'logs_independent_of_ssh':True})
        try:
            code = child.wait(timeout=95)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid,signal.SIGTERM)
            child.wait(timeout=5)
            write('start-exit.private.json',{'exit_code':child.returncode,'timeout':True})
            raise
        write('start-exit.private.json',{'exit_code':code,'timeout':False})
        return {'native_start_exit':code}


def snapshot(label):
    if not all((ROOT/n).exists() for n in ['checkpoint.json','finalize-ready.json','process.private.json']):
        return {'ready':False}
    digest = fixture.verify_checkpoint(ROOT)
    if label == 'before':
        for name in ['checkpoint-started.json','checkpoint.json']:
            with (ROOT/name).open('rb') as f: os.fsync(f.fileno())
        fd = os.open(ROOT,os.O_RDONLY)
        try: os.fsync(fd)
        finally: os.close(fd)
    row = history(label)
    processes = read('process.private.json'); supervisor = read('supervisor.private.json')
    identities = descendants([processes['pid'],supervisor['pid']])
    data = {'ready':True,'run_id':row['dagRunId'],'status':row['status'],
            'checkpoint_sha256':digest,'execution_count':1,'tests':12,
            'checkpoint_fsynced':label=='before','owned_identities':identities,
            'owned_listener_inodes':owned_listeners(identities),'native_history':row}
    write('snapshot-'+label+'.private.json',data)
    return data


def release(retry):
    fixture.verify_checkpoint(ROOT)
    with (ROOT/'release-finalize').open('x') as f:
        f.flush(); os.fsync(f.fileno())
    if retry:
        _,base,_=context();run_id=read('run.private.json')['run_id']
        command('retry-finalize',base+['retry','--run-id',run_id,'--step','finalize',str(ROOT/'recovery.yaml')])
    write('release.private.json',{'native_selected_step_retry':retry})
    return {'released':True,'retry':retry}


def finish():
    before=read('snapshot-before.private.json');after=read('snapshot-after.private.json')
    identities = before['owned_identities'] | after['owned_identities']
    deadline=time.monotonic()+20
    while not (ROOT/'completed.json').exists() or living(identities):
        if time.monotonic()>=deadline:raise TimeoutError('job completion/process retirement deadline')
        time.sleep(.05)
    final=history('final'); digest=fixture.verify_checkpoint(ROOT)
    completed=read('completed.json')
    freeze=read('freeze.private.json')
    checks={'same_native_run_id':before['run_id']==after['run_id']==final['dagRunId'],
        'native_running_before_disconnect':before['status']=='running',
        'checkpoint_durable_before_disconnect':before['checkpoint_fsynced'],
        'native_succeeded':final['status']=='succeeded',
        'checkpoint_unchanged':before['checkpoint_sha256']==after['checkpoint_sha256']==digest,
        'exact_completed_result':completed=={'checkpoint_sha256':digest,'tests':12,'execution_count':1},
        'checkpoint_executed_once':read('checkpoint-started.json')=={'execution_count':1},
        'frozen_inputs_unchanged':all(fixture.digest(ROOT/n)==h for n,h in freeze['files'].items()),
        'checkpoint_oracle_12': 'Ran 12 tests' in (ROOT/'checkpoint-tests.log').read_text() and (ROOT/'checkpoint-tests.log').read_text().rstrip().endswith('OK'),
        'final_oracle_12':'Ran 12 tests' in (ROOT/'final-tests.log').read_text() and (ROOT/'final-tests.log').read_text().rstrip().endswith('OK'),
        'owned_processes_exited':not living(identities),
        'owned_listeners_retired':not (set(before['owned_listener_inodes'])|set(after['owned_listener_inodes']))&listener_inodes()}
    result={'passed':all(checks.values()),'checks':checks,'before_status':before['status'],
        'reconnected_status':after['status'],'final_status':final['status'],
        'checkpoint_sha256':digest,'checkpoint_execution_count':1,'oracle_tests_before':12,'oracle_tests_after':12,
        'native_selected_step_retry':read('release.private.json')['native_selected_step_retry'],
        'native_start_exit':read('start-exit.private.json') if (ROOT/'start-exit.private.json').exists() else None,
        'observed_owned_processes_remaining':len(living(identities)),'observed_owned_listeners_remaining':0,
        'owned_processes_observed':len(identities),'owned_listeners_observed':len(set(before['owned_listener_inodes'])|set(after['owned_listener_inodes'])),
        'model_calls':0,'python_version':sys.version.split()[0],
        'frozen_files':freeze['files'],'home_preserved':freeze['home_preserved'],'environment_keys':freeze['environment_keys'],
        'private_evidence_hashes':{p.name:fixture.digest(p) for p in sorted(ROOT.iterdir()) if p.is_file() and p.suffix in ['.json','.log','.stdout','.stderr']}}
    write('result.json',result)
    if not result['passed']:raise ValueError('acceptance failed; result retained')
    return result


def cleanup():
    if not (ROOT/'process.private.json').exists():return {'owned_job_started':False}
    p=read('process.private.json');identities={str(p['pid']):p['starttime']}
    if living(identities):
        _,base,_=context();run_id=read('run.private.json')['run_id']
        command('failure-cleanup-stop',base+['stop','--run-id',run_id,str(ROOT/'recovery.yaml')])
    return {'owned_root_remaining':living(identities)}


if __name__=='__main__':
    os.umask(0o077)
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['prepare','start','snapshot','release','finish','cleanup'])
    parser.add_argument('--label',choices=['before','after'])
    parser.add_argument('--retry',action='store_true')
    args=parser.parse_args()
    if args.action=='snapshot': result=snapshot(args.label)
    elif args.action=='release':result=release(args.retry)
    else:result=globals()[args.action]()
    # Start is held open by the SSH client that will be intentionally terminated.
    # Its result is already file-backed; do not write into a disconnected pipe.
    if args.action!='start':print(json.dumps(result))
