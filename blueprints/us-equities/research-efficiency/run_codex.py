#!/usr/bin/env python3
"""One prepared-context native Codex SDK turn; outer supervisor owns120s bound."""
import argparse
import asyncio
import json
from pathlib import Path
import sys


async def run(args, prompt):
    from openai_codex import AsyncCodex, ApprovalMode, CodexConfig, Sandbox
    config=CodexConfig(codex_bin=str(args.codex_bin),cwd=str(args.workspace),env={'CODEX_HOME':str(args.codex_home),'CONTEXT_MODE_PROJECT_DIR':str(args.workspace)})
    result={'status':'not_submitted','usage':None,'items':[],'model_inference_submitted':False}
    async with AsyncCodex(config) as client:
        thread=await client.thread_start(cwd=str(args.workspace),model='gpt-6-astra',ephemeral=True,sandbox=Sandbox.read_only,approval_mode=ApprovalMode.deny_all,developer_instructions=args.policy.read_text())
        selected=(await thread.read()).thread
        result.update(configured_model=selected.model,configured_provider=selected.model_provider)
        if selected.model!='gpt-6-astra' or selected.model_provider!='openai':
            result['status']='model_or_provider_mismatch';return result
        turn=await thread.turn(prompt,model='gpt-6-astra');result['model_inference_submitted']=True
        pending=asyncio.create_task(turn.run())
        try:
            native=await asyncio.wait_for(asyncio.shield(pending),100)
        except TimeoutError:
            try:
                await asyncio.wait_for(turn.interrupt(),5)
            finally:
                pending.cancel();await asyncio.gather(pending,return_exceptions=True)
            result['status']='deadline_interrupt_requested';return result
        result.update(status=native.status.value,final_response=native.final_response,duration_ms=native.duration_ms,
                      usage=native.usage.model_dump(by_alias=True,mode='json') if native.usage else None,
                      items=[i.model_dump(by_alias=True,mode='json') for i in native.items])
        return result


def main():
    p=argparse.ArgumentParser()
    for name in ['codex-bin','codex-home','workspace','policy']:
        p.add_argument('--'+name,type=Path,required=True)
    args=p.parse_args();prompt=sys.stdin.read()
    if not 1<=len(prompt.encode())<=110000:
        raise ValueError('prompt outside frozen bound')
    result=asyncio.run(run(args,prompt));print(json.dumps(result,sort_keys=True));return 0 if result['status']=='completed' else 1


if __name__=='__main__':
    raise SystemExit(main())
