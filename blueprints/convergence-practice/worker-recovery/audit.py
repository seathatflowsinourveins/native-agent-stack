#!/usr/bin/env python3
"""Independently audit retained native child events and exact local effects."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent
EXPECTED=b'{"ids":["a","b"],"total":12}\n'


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def calls(events):
    return [(i,e,b) for i,e in enumerate(events) if e.get('type')=='assistant'
            for b in e.get('message',{}).get('content',[]) if b.get('type')=='tool_use']


def results(events):
    return {b['tool_use_id']:b for e in events if e.get('type')=='user'
            for b in e.get('message',{}).get('content',[]) if isinstance(b,dict) and b.get('type')=='tool_result'}


def audit(root):
    root=Path(root); workspace=root/'fixture'
    streams=[[json.loads(x) for x in (root/(phase+'.stream.jsonl')).read_text().splitlines()] for phase in ('initial','resumed')]
    identity=json.loads((root/'native-identity.json').read_text())['parent_session_id']
    before=json.loads((root/'pre-crash-private.json').read_text())
    child=before['child_message_target']
    initial_calls,resumed_calls=[calls(e) for e in streams]
    spawn=[x for x in initial_calls if x[2]['name']=='Agent']
    assert len(spawn)==1 and not spawn[0][1].get('parent_tool_use_id')
    assert spawn[0][2]['input']['subagent_type']=='foundation-recovery-worker'
    assert spawn[0][2]['input']['run_in_background'] is True
    assert not any(b['name']=='Agent' for _,_,b in resumed_calls)
    stops=[x for x in initial_calls if x[2]['name']=='TaskStop']
    messages=[[x for x in group if x[2]['name']=='SendMessage'] for group in (initial_calls,resumed_calls)]
    assert len(stops)==1 and stops[0][2]['input']['task_id']==child
    assert all(len(group)==1 and group[0][2]['input'].get('to')==child for group in messages)
    assert spawn[0][0]<stops[0][0]<messages[0][0][0]
    task_runs=[]
    for stream in streams:
        inits=[e for e in stream if e.get('type')=='system' and e.get('subtype')=='init']
        assert inits and all(e['session_id']==identity and e['model']=='claude-opus-5' for e in inits)
        starts=[e for e in stream if e.get('type')=='system' and e.get('subtype')=='task_started']
        assert starts and all(e['task_id']==child for e in starts)
        task_runs.append(starts)
    assert [len(group) for group in task_runs]==[2,1]
    assert task_runs[0][0]['tool_use_id']==spawn[0][2]['id']
    assert task_runs[0][1]['tool_use_id']==messages[0][0][2]['id']
    assert task_runs[1][0]['tool_use_id']==messages[1][0][2]['id']
    assert any(e.get('subtype')=='task_notification' and e.get('task_id')==child and e.get('status')=='stopped' for e in streams[0])
    completed=[e for e in streams[1] if e.get('subtype')=='task_notification' and e.get('task_id')==child and e.get('status')=='completed']
    assert len(completed)==1
    child_commands=[]; parent_commands=[]; extra=[]
    for stream,group in zip(streams,(initial_calls,resumed_calls)):
        returned=results(stream)
        for _,event,block in group:
            if block['name']!='Bash':continue
            command=block['input']['command']
            if event.get('parent_tool_use_id'):
                if command.startswith('python3 stage.py '):child_commands.append(command)
                else:extra.append({'command':command,'denied_or_error':returned.get(block['id'],{}).get('is_error') is True})
            else:parent_commands.append(command)
    assert child_commands==['python3 stage.py checkpoint','python3 stage.py cancel-wait','python3 stage.py crash-wait','python3 stage.py finalize']
    assert parent_commands==['python3 control.py await-cancel-wait','python3 control.py verify-cancelled','python3 control.py await-crash-wait']
    assert extra==[{'command':'ls -1 && git status --porcelain','denied_or_error':True}]
    # Native child messages retain their original Agent linkage across resumes.
    for group in (initial_calls,resumed_calls):
        assert all(e.get('parent_tool_use_id')==spawn[0][2]['id'] for _,e,b in group if b['name']=='Bash' and b['input']['command'].startswith('python3 stage.py '))
    journal=[json.loads(x)['action'] for x in (workspace/'actions.jsonl').read_text().splitlines()]
    assert journal==['checkpoint','cancel-wait','crash-wait','finalize']
    assert (workspace/'checkpoint.json').read_bytes()==EXPECTED
    assert before['checkpoint_sha256']==hashlib.sha256(EXPECTED).hexdigest()
    assert json.loads((workspace/'final.json').read_text())=={'checkpoint_sha256':hashlib.sha256(EXPECTED).hexdigest(),'execution_count':1,'status':'complete'}
    freeze=json.loads((root/'freeze.json').read_text())
    for name,expected in freeze['sha256'].items():
        source=HERE/({'run.py':'executed-runner.py.txt','test_oracle':'executed-test-oracle.py.txt'}.get(name,name))
        assert digest(source)==expected, name
        if (workspace/name).exists():assert digest(workspace/name)==expected,name
    assert subprocess.check_output(['git','-C',str(workspace),'diff','--name-only'],text=True)==''
    original=json.loads((root/'attempt.json').read_text())
    assert original['status']=='failed' and original['failure'] is None
    assert [(x['phase'],x['exit_code']) for x in original['native_invocations']]==[('initial',-9),('resumed',0)]
    assert original['cleanup']['crash_wait_additional_cleanup'] is True and original['cleanup']['errors']==[]
    for filename in ('cancel-wait.json','crash-wait.json'):
        marker=json.loads((workspace/filename).read_text())
        path=Path('/proc')/str(marker['pid'])/'stat'
        if path.exists():
            fields=path.read_text().rsplit(')',1)[1].split()
            assert fields[0]=='Z' or fields[19]!=marker['start_ticks']
    remaining=[]
    for process in Path('/proc').iterdir():
        if not process.name.isdigit():continue
        try:
            if (process/'cwd').resolve()==workspace:remaining.append(process.name)
        except (OSError,RuntimeError):pass
    assert remaining==[]
    terminals=[e for e in streams[1] if e.get('type')=='result']
    assert len(terminals)==3 and all(e['session_id']==identity and e['is_error'] is False and e['subtype']=='success' for e in terminals)
    categories=['input_tokens','cache_creation_input_tokens','cache_read_input_tokens','output_tokens']
    usage=[{key:e['usage'].get(key) for key in categories} for e in terminals]
    assert terminals[1]['modelUsage']==terminals[2]['modelUsage']
    return {'status':'accepted_within_scope_after_explicit_cleanup','outer_native_attempts':1,'native_cli_invocations':2,
            'native_child_spawn_count':1,'same_child_run_count':3,'same_parent_identity':True,'same_child_identity':True,
            'native_child_control':['Agent','TaskStop','SendMessage','runtime_SIGKILL','parent_resume','SendMessage'],
            'child_effect_commands':child_commands,'extra_child_command':extra[0], 'parent_control_commands':parent_commands,
            'action_journal':journal,'checkpoint_sha256':hashlib.sha256(EXPECTED).hexdigest(),'final_sha256':digest(workspace/'final.json'),
            'checkpoint_unchanged':True,'single_final_effect':True,'frozen_sources_unchanged':True,'fixture_tracked_changes':[],
            'cleanup':{'original_wait_identities_not_alive':True,'fixture_cwd_processes_remaining':0,'crash_descendant_containment':'not_accepted',
                       'surviving_owned_wait_required_explicit_identity_checked_SIGKILL':True},
            'original_recorder_status':'failed','recorder_false_negative':'Resumed native background-task delivery emitted three init and three success results; the original recorder required exactly one.',
            'usage':{'initial_terminal_missing_due_to_SIGKILL':True,'resumed_terminal_category_views':usage,'repeated_final_model_usage_count':2,
                     'one_observed_cumulative_model_view':terminals[-1]['modelUsage'],'completed_child_run_usage':completed[0].get('usage'),
                     'complete_parent_child_retry_total':None,'billing':None,'savings_claim':None},
            'scope':'One same-host native child local-writing continuation after native cancellation and abrupt shared-runtime failure, with explicit coordinator descendant cleanup.',
            'limitations':['Not native crash descendant containment, independent child-process isolation or remote provider cancellation.','No power-loss, independent-host, billing-cessation or distributed exactly-once acceptance.','The child attempted an extra read-only command which was refused; exact requested tool-only behavior did not pass.','Original failed recorder result is retained; audit changes made no model calls.']}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('private_run_dir');args=p.parse_args()
    print(json.dumps(audit(args.private_run_dir),indent=2,sort_keys=True))
