#!/usr/bin/env python3
"""Export all attempted answers for blind review without publishing transcripts."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import secrets

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('efficiency_review_helpers', HERE/'experiment.py')
E = importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(E)


def export(source, anchor, out):
    source, out = E.safe(source), E.safe(out)
    raw = (source/'freeze.json').read_bytes()
    if E.sha(raw) != anchor:
        raise ValueError('freeze anchor mismatch')
    E.verify_files(source,json.loads(raw)['files'])
    if (source/'experiment.py').read_bytes() != (HERE/'experiment.py').read_bytes():
        raise ValueError('review helper differs from frozen execution helper')
    if out.exists():
        raise FileExistsError('choose a fresh private review directory')
    if any((p/'.git').exists() for p in [out,*out.parents]):
        raise ValueError('blind answers must remain outside Git')
    plan = json.loads((source/'plan.json').read_bytes())
    runs = []
    for directory in sorted((source/'runs').iterdir()):
        reservation = json.loads((directory/'reservation.json').read_bytes())
        if not (directory/'receipt.json').is_file():
            raise ValueError('unfinished invocation must be resolved before blind export')
        receipt = json.loads((directory/'receipt.json').read_bytes())
        if any(receipt[k] != reservation[k] for k in ['provider','task','condition']):
            raise ValueError('receipt reservation mismatch')
        command = json.loads((directory/'command.json').read_bytes())
        if E.sha(E.encode(command['argv'])) != plan['runtime']['commands'][receipt['provider']]['sha256']:
            raise ValueError('command anchor mismatch')
        if receipt['freeze_sha256'] != anchor:
            raise ValueError('run anchor mismatch')
        if receipt['condition'] not in ['full','focused'] or receipt['task'] not in plan['tasks']:
            raise ValueError('invalid frozen task/condition')
        source_ids = [d['id'] for d in plan['corpus']] if receipt['condition']=='full' else plan['selected'][receipt['task']]
        if receipt['source_ids'] != source_ids:
            raise ValueError('receipt source scope mismatch')
        prompt = (source/'prompts'/(receipt['task']+'-'+receipt['condition']+'.txt')).read_bytes()
        if E.sha(prompt) != receipt['prompt_sha256'] or len(prompt) != receipt['prompt_bytes']:
            raise ValueError('run prompt mismatch')
        raw_native = (directory/'native.stdout').read_text()
        try:
            native = json.loads(raw_native) if receipt['provider']=='codex' else [json.loads(line) for line in raw_native.splitlines() if line.strip()]
            replay = E.summarize_native(receipt['provider'],native,source_ids)
            replay['completed'] = replay['completed'] and receipt['process_exit_code']==0 and not receipt['process_timeout']
            if any(replay[k]!=receipt[k] for k in ['completed','usage','report','validation_error','hook_event_count']):
                raise ValueError('native receipt replay mismatch')
        except json.JSONDecodeError:
            if receipt['completed'] or receipt['usage']['total'] is not None or receipt['report'] is not None:
                raise ValueError('malformed native output has unsupported success/usage/report')
        runs.append((directory,receipt))
    if len(runs)>8 or len({(r['provider'],r['task'],r['condition']) for _,r in runs}) != len(runs):
        raise ValueError('duplicate or excess native submissions')
    out.mkdir(mode=0o700,parents=True)
    E.write(out/'rubric.json',E.encode(plan['rubric']))
    E.write(out/'questions.json',E.encode({k:v['question'] for k,v in plan['tasks'].items()}))
    E.write(out/'source-manifest.json',E.encode(plan['corpus']))
    for doc in plan['corpus']:
        raw = (source/'corpus'/(doc['id'].lower()+'.md')).read_bytes()
        if E.sha(raw)!=doc['sha256']:
            raise ValueError('source hash mismatch')
        E.write(out/'sources'/(doc['id']+'.md'),raw)
    secrets.SystemRandom().shuffle(runs)
    mapping = []
    for number,(directory,receipt) in enumerate(runs,1):
        identifier=f'answer-{number:02}'
        response=receipt['report']
        if response is None:
            # Preserve non-JSON answers rather than silently discarding failures.
            raw=(directory/'native.stdout').read_text()
            try:
                native=json.loads(raw) if receipt['provider']=='codex' else [json.loads(line) for line in raw.splitlines() if line.strip()]
                response=native.get('final_response') if isinstance(native,dict) else next((e.get('result') for e in native if e.get('type')=='result'),None)
            except (ValueError,TypeError):
                response=None
        answer={'id':identifier,'task':receipt['task'],'response':response}
        E.write(out/(identifier+'.json'),E.encode(answer))
        mapping.append({'id':identifier,'run':directory.name,'receipt_sha256':E.sha((directory/'receipt.json').read_bytes()),'answer_sha256':E.sha(E.encode(answer))})
    # Stored alongside the experiment, never in the reviewer's directory.
    E.write(source/'blind-mapping.json',E.encode(mapping))
    files=[E.digest(str(p.relative_to(out)),p.read_bytes()) for p in sorted(out.rglob('*')) if p.is_file()]
    E.write(out/'manifest.json',E.encode({'source_freeze_sha256':anchor,'answers':len(runs),'files':files}))
    return {'answers':len(runs),'manifest_sha256':E.sha((out/'manifest.json').read_bytes())}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--freeze-sha256',required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    print(json.dumps(export(a.source,a.freeze_sha256,a.out),sort_keys=True))


if __name__=='__main__':
    main()
