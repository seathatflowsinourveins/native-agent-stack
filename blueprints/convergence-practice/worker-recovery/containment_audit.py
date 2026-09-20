#!/usr/bin/env python3
"""Audit deterministic cgroup proof and the retained refused native trial."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent


def load(root,name):return json.loads((root/name).read_text())


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def alive(record):
    path=Path('/proc')/str(record['pid'])/'stat'
    if not path.exists():return False
    fields=path.read_text().rsplit(')',1)[1].split()
    return fields[0]!='Z' and fields[19]==record['start_ticks']


def audit(base):
    base=Path(base);probe=base/'containment-probe-2';native=base/'systemd-attempt-1'
    initial_probe=load(base/'containment-probe-1','result-private.json')
    assert initial_probe['status']=='failed_before_service_launch' and initial_probe['model_calls']==0
    result=load(probe,'result-private.json');before=load(probe,'before-private.json');after=load(probe,'after-private.json')
    records=[load(probe,name+'.json') for name in ('main','detached-child')]
    before_members=load(probe,'before-members-private.json')
    assert result['status']=='passed' and result['model_calls']==0
    assert int(before['MainPID'])==records[0]['pid']
    assert records[1]['sid']==records[1]['pid'] and records[1]['sid']!=records[0]['sid']
    assert all(r['pid'] in before_members and before['ControlGroup'] in r['cgroup'] and r['ignores_term'] for r in records)
    assert before['KillMode']=='control-group' and before['Restart']=='no' and before['SendSIGKILL']=='yes'
    assert after['ExecMainCode']=='2' and after['ExecMainStatus']=='9' and after['NRestarts']=='0'
    assert not any(alive(r) for r in records)
    assert not (Path('/sys/fs/cgroup')/before['ControlGroup'].lstrip('/')).exists()
    assert result['source_sha256']==sha(HERE/'containment_probe.py')
    readiness=load(base/'systemd-readiness-1','result-private.json')
    assert readiness['status']=='passed' and readiness['model_calls']==0 and readiness['native_path_and_home_match'] is True
    events=[json.loads(line) for line in (native/'initial.stream.jsonl').read_text().splitlines()]
    calls=[(e,b) for e in events if e.get('type')=='assistant' for b in e.get('message',{}).get('content',[]) if b.get('type')=='tool_use']
    agents=[b for _,b in calls if b['name']=='Agent']
    assert len(agents)==1 and agents[0]['input']['subagent_type']=='foundation-recovery-worker'
    child_commands=[b for e,b in calls if b['name']=='Bash' and e.get('parent_tool_use_id')]
    assert len(child_commands)==1 and child_commands[0]['input']['command']=='ls -la && python3 stage.py checkpoint'
    returned=[b for e in events if e.get('type')=='user' for b in e.get('message',{}).get('content',[]) if isinstance(b,dict) and b.get('type')=='tool_result']
    refusal=[b for b in returned if b.get('tool_use_id')==child_commands[0]['id']]
    assert len(refusal)==1 and refusal[0]['is_error'] is True and 'Permission to use Bash has been denied' in refusal[0]['content']
    assert not any(b['name'] in ('TaskStop','SendMessage') for _,b in calls)
    assert not (native/'resumed.stream.jsonl').exists()
    workspace=native/'fixture'
    assert all(not (workspace/name).exists() for name in ('checkpoint.json','actions.jsonl','cancel-wait.json','crash-wait.json','final.json'))
    assert subprocess.check_output(['git','-C',str(workspace),'diff','--name-only'],text=True)==''
    freeze=load(native,'freeze.json')
    aliases={'run.py':'executed-systemd-runner.py.txt','service.py':'executed-systemd-service.py.txt','test_oracle':'executed-systemd-test-oracle.py.txt'}
    for name,expected in freeze['sha256'].items():
        assert sha(HERE/aliases.get(name,name))==expected,name
        if (workspace/name).exists():assert sha(workspace/name)==expected,name
    abort=load(native,'abort-main-kill-private.json');attempt=load(native,'attempt.json')
    command=abort['command']
    assert command[:5]==['systemctl','--user','kill','--kill-whom=main','--signal=SIGKILL']
    assert command[5]==abort['before']['Id']
    assert attempt['status']=='failed' and len(attempt['native_invocations'])==1
    assert attempt['cleanup']['errors']==[]
    cleanup=attempt['cleanup']['owned_services']['initial']
    assert cleanup['remaining_members']==[] and cleanup['after']['MainPID']=='0'
    assert cleanup['after']['ExecMainStatus']=='9' and cleanup['after']['NRestarts']=='0'
    assert not (Path('/sys/fs/cgroup')/abort['before']['ControlGroup'].lstrip('/')).exists()
    for p in Path('/proc').iterdir():
        if not p.name.isdigit():continue
        try:assert (p/'cwd').resolve()!=workspace
        except (OSError,RuntimeError):pass
    return {'status':'deterministic_containment_accepted_native_combination_not_accepted',
            'deterministic':{'status':'accepted_within_scope','model_calls':0,'term_ignoring_setsid_descendant':True,'same_cgroup_before':True,'main_only_SIGKILL':True,'all_original_identities_stopped':True,'cgroup_removed':True,'native_restarts':0,'initial_harness_refusal_retained':True},
            'readiness':{'status':'passed','model_calls':0,'native_version':readiness['native_version'],'native_path_and_home_match':True,'omitted_unsupported_environment_names':readiness['omitted_inherited_environment_names']},
            'native':{'status':'not_accepted','attempts':1,'cli_invocations':1,'child_spawns':1,'child_command_refused':'ls -la && python3 stage.py checkpoint','permission_mode_unchanged':'dontAsk','fixture_effects':0,'resumed_attempts':0,'permission_widening':False,'stop_condition':'native child permission refusal before checkpoint','owned_service_aborted_main_only':True,'owned_cgroup_removed':True,'owned_processes_remaining':0,'frozen_source_count':len(freeze['sha256']),'frozen_sources_unchanged':True},
            'usage':{'complete_parent_child_retry_total':None,'reason':'Native service aborted after refusal; terminal/task views are not complete enclosing usage.','billing':None,'savings_claim':None},
            'limitations':['Deterministic cgroup proof is not successful native child crash/resume acceptance.','Earlier same-child continuation still required explicit direct descendant cleanup.','No host/user-manager restart, provider cancellation, billing cessation, off-host restoration or distributed exactly-once acceptance.']}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('private_base');args=parser.parse_args()
    print(json.dumps(audit(args.private_base),indent=2,sort_keys=True))
