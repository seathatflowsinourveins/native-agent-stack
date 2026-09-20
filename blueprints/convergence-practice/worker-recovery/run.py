#!/usr/bin/env python3
"""One explicitly authorized native child cancellation/crash/resume trial."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
import uuid

HERE=Path(__file__).resolve().parent
LEGACY=HERE.parent/'native-recovery/claude'
sys.path.insert(0,str(LEGACY))
support_spec=importlib.util.spec_from_file_location('claude_recovery_support',LEGACY/'run.py')
support=importlib.util.module_from_spec(support_spec);support_spec.loader.exec_module(support)
NativeCLI,identity,private_directory=support.NativeCLI,support.identity,support.private_directory
spec=importlib.util.spec_from_file_location('owned_worker_stage',HERE/'stage.py')
fixture=importlib.util.module_from_spec(spec); spec.loader.exec_module(fixture)


def write(path,data):
    path.write_text(json.dumps(data,indent=2,sort_keys=True)+'\n')


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def calls(events):
    return [(event,block) for event in list(events) if event.get('type')=='assistant'
            for block in event.get('message',{}).get('content',[]) if block.get('type')=='tool_use']


def alive(marker):
    current=identity(marker['pid'])
    return current is not None and current['state']!='Z' and current['start_ticks']==marker['start_ticks']


def native_summary(events, session):
    """Native background-task delivery can emit multiple init/result messages."""
    inits=[e for e in events if e.get('type')=='system' and e.get('subtype')=='init']
    terminals=[e for e in events if e.get('type')=='result']
    return (bool(inits) and all(e.get('session_id')==session for e in inits),
            bool(inits) and all(e.get('model')=='claude-opus-5' for e in inits),
            bool(terminals) and all(e.get('subtype')=='success' and e.get('is_error') is False for e in terminals))


def stop_owned_wait(path,workspace):
    if not path.is_file():return False
    marker=json.loads(path.read_text())
    if not alive(marker):return False
    pid=marker['pid']
    command=Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\0')
    if b'stage.py' not in command or Path(f'/proc/{pid}/cwd').resolve()!=workspace:
        raise RuntimeError('owned_wait_identity_mismatch')
    try:os.kill(pid,signal.SIGKILL)
    except ProcessLookupError:pass
    end=time.monotonic()+5
    while alive(marker) and time.monotonic()<end:time.sleep(.05)
    if alive(marker):raise RuntimeError('owned_wait_not_stopped')
    return True


def run(args):
    root=private_directory(args.run_dir,HERE); root.mkdir(parents=True,exist_ok=False,mode=0o700)
    workspace=root/'fixture'; workspace.mkdir()
    for name in ('stage.py','control.py','input.json'):
        shutil.copyfile(HERE/name,workspace/name)
    subprocess.run(['git','init','-q',str(workspace)],check=True)
    subprocess.run(['git','-C',str(workspace),'add','.'],check=True)
    subprocess.run(['git','-C',str(workspace),'-c','user.name=Owned Fixture','-c','user.email=fixture@example.invalid','commit','-qm','Freeze child recovery fixture'],check=True)
    executable=Path(shutil.which(args.claude) or args.claude).resolve(strict=True)
    auth=subprocess.run([str(executable),'auth','status'],capture_output=True,text=True,check=False)
    auth_data=json.loads(auth.stdout) if auth.returncode==0 else {}
    readiness={key:auth_data.get(key) for key in ('loggedIn','authMethod','apiProvider','subscriptionType')}
    write(root/'readiness.json',readiness)
    if readiness.get('loggedIn') is not True or readiness.get('apiProvider')!='firstParty':raise RuntimeError('native_account_not_ready')
    (root/'native-help.txt').write_text(subprocess.check_output([str(executable),'--help'],text=True))
    session=str(uuid.uuid4()); write(root/'native-identity.json',{'parent_session_id':session})
    agent={'foundation-recovery-worker':{'description':'Only the owned child recovery fixture; execute exact stage commands.','prompt':'You are the sole writing worker for this owned recovery fixture. Execute only the exact python3 stage.py action requested by your parent. Never repeat checkpoint/finalize, modify inputs, delegate, access accounts or change settings. Cancellation and interruption are planned test stages; continue only when parent explicitly resumes you.','tools':['Bash'],'model':'inherit','maxTurns':8}}
    common=[str(executable),'-p','--model','claude-opus-5','--effort','ultracode','--max-turns','16','--output-format','stream-json','--verbose','--tools','Bash,Agent,SendMessage,TaskStop,TaskOutput','--allowedTools','Agent(foundation-recovery-worker)','SendMessage','TaskStop','TaskOutput','Bash(python3 stage.py *)','Bash(python3 control.py *)','--disallowedTools','mcp__*','--permission-mode','dontAsk','--permission-prompts','none','--agents',json.dumps(agent)]
    commands={'initial':common+['--session-id',session]}
    frozen={name:sha(HERE/name) for name in ('stage.py','control.py','input.json','prompt.txt','run.py','plan.json')}
    frozen['test_oracle']=sha(HERE.parents[2]/'tests/test_worker_recovery.py')
    write(root/'freeze.json',{'at_utc':datetime.now(timezone.utc).isoformat(),'sha256':frozen,'fixture_base':subprocess.check_output(['git','-C',str(workspace),'rev-parse','HEAD'],text=True).strip()})
    write(root/'commands-private.json',commands)
    clients=[]; checks={}; cleanup={'errors':[]}; failure=None; child_id=None; before=None
    start=time.monotonic()
    try:
        initial=NativeCLI(commands['initial'],(HERE/'prompt.txt').read_text(),workspace,root,'initial');clients.append(initial)
        deadline=time.monotonic()+args.timeout
        while not (workspace/'crash-wait.json').is_file():
            if initial.proc.poll() is not None:raise RuntimeError('initial_native_exit_before_child_crash_wait')
            if time.monotonic()>deadline:raise TimeoutError('child_crash_wait_deadline')
            time.sleep(.05)
        # A native SendMessage follows the native TaskStop; retain identities verbatim privately.
        native_calls=calls(initial.events)
        agent_calls=[b for _,b in native_calls if b['name']=='Agent']
        stops=[b for _,b in native_calls if b['name']=='TaskStop']
        messages=[b for _,b in native_calls if b['name']=='SendMessage']
        if len(agent_calls)!=1 or len(stops)!=1 or len(messages)!=1:raise RuntimeError('native_child_control_sequence_missing')
        child_id=messages[0]['input'].get('to') or messages[0]['input'].get('recipient')
        if not isinstance(child_id,str) or not child_id:raise RuntimeError('native_child_identity_missing')
        checks['one_native_child_spawn']=True
        checks['native_taskstop_then_message_observed']=True
        checks['cancelled_wait_stopped']=not alive(json.loads((workspace/'cancel-wait.json').read_text()))
        checks['child_second_wait_pending']=alive(json.loads((workspace/'crash-wait.json').read_text()))
        checks['pre_crash_journal_exact']=fixture.actions(workspace)==['checkpoint','cancel-wait','crash-wait']
        before=(workspace/'checkpoint.json').read_bytes()
        if not all(checks.values()) or before!=fixture.EXPECTED:raise RuntimeError('pre_crash_acceptance_failed')
        write(root/'pre-crash-private.json',{'child_message_target':child_id,'taskstop_input':stops[0]['input'],'agent_input':agent_calls[0]['input'],'native_cli_pid':initial.proc.pid,'native_cli_identity':identity(initial.proc.pid),'checkpoint_sha256':sha(workspace/'checkpoint.json'),'observed_at_utc':datetime.now(timezone.utc).isoformat()})
        os.killpg(initial.proc.pid,signal.SIGKILL); initial.proc.wait(timeout=10)
        cleanup['initial_exit']=initial.proc.returncode; initial.close()
        cleanup['crash_wait_additional_cleanup']=stop_owned_wait(workspace/'crash-wait.json',workspace)
        checks['owned_runtime_sigkill_exit']=initial.proc.returncode==-signal.SIGKILL
        checks['owned_crash_wait_stopped']=not alive(json.loads((workspace/'crash-wait.json').read_text()))
        (workspace/'resume-authorized.json').write_text('{}\n')
        prompt=f'Resume the SAME native child agent {child_id} using SendMessage only; do not invoke Agent again and do not perform fixture effects yourself. Its runtime was deliberately killed after the unchanged checkpoint and crash-wait. Tell that child: "Continue the same task. Run ONLY python3 stage.py finalize. The supervisor has authorized this final stage. Do not recreate checkpoint or run waits again." Wait for that child to finish and report its result. Native provider/quota/permission errors must be reported without fallback or retry.'
        (root/'resume-prompt-private.txt').write_text(prompt)
        commands['resumed']=common+['--resume',session];write(root/'commands-private.json',commands)
        resumed=NativeCLI(commands['resumed'],prompt,workspace,root,'resumed');clients.append(resumed)
        resumed.proc.wait(timeout=args.timeout);resumed.close()
        summaries=[native_summary(c.events,session) for c in clients]
        checks['same_parent_session']=all(x[0] for x in summaries)
        checks['native_model_preserved']=all(x[1] for x in summaries)
        follow=calls(resumed.events)
        checks['no_replacement_child']=not any(b['name']=='Agent' for _,b in follow)
        checks['same_child_message_target']=any(b['name']=='SendMessage' and (b['input'].get('to') or b['input'].get('recipient'))==child_id for _,b in follow)
        checks['checkpoint_unchanged']=before==(workspace/'checkpoint.json').read_bytes()==fixture.EXPECTED
        checks['single_effect_journal']=fixture.actions(workspace)==fixture.ORDER
        checks['final_matches_oracle']=json.loads((workspace/'final.json').read_text())=={'checkpoint_sha256':hashlib.sha256(fixture.EXPECTED).hexdigest(),'execution_count':1,'status':'complete'}
        checks['resumed_native_success']=resumed.proc.returncode==0 and summaries[-1][2]
    except Exception as exc:
        failure={'type':type(exc).__name__,'reason':str(exc)}
    finally:
        for c in clients:
            try:
                if not c.out.closed:c.close()
            except Exception as exc:cleanup['errors'].append(type(exc).__name__)
        for name in ('cancel-wait.json','crash-wait.json'):
            try:cleanup[name+'_forced_cleanup']=stop_owned_wait(workspace/name,workspace)
            except Exception as exc:cleanup['errors'].append(type(exc).__name__)
    checks['owned_cli_processes_stopped']=bool(clients) and all(c.proc.poll() is not None for c in clients)
    checks['cleanup_errors_absent']=not cleanup['errors']
    summaries=[]
    for c in clients:
        terminals=[e for e in c.events if e.get('type')=='result']
        summaries.append({'phase':c.label,'exit_code':c.proc.returncode,'invalid_stream_lines':c.invalid_lines,'terminal_count':len(terminals),'terminal_usage':[e.get('usage') for e in terminals],'model_usage':[e.get('modelUsage') for e in terminals]})
    write(root/'attempt.json',{'status':'passed_pending_independent_audit' if failure is None and all(checks.values()) else 'failed','elapsed_seconds':round(time.monotonic()-start,3),'checks':checks,'cleanup':cleanup,'failure':failure,'native_invocations':summaries,'complete_parent_child_usage':None,'billing':None,'savings_claim':None})
    print(json.dumps({'status':json.loads((root/'attempt.json').read_text())['status'],'checks':checks,'failure':failure},indent=2))
    return 0 if failure is None and all(checks.values()) else 1


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run-dir',required=True);p.add_argument('--claude',default='claude');p.add_argument('--timeout',type=int,default=240)
    raise SystemExit(run(p.parse_args()))
