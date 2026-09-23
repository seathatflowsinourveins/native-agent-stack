#!/usr/bin/env bash
# run_arm.sh TASK(t1|t2) ARM(with|without) OUT_DIR : one codex exec run, read-only, ephemeral, hooks off.
set -u
T=$1; ARM=$2; OUT=$3; D=$(cd "$(dirname "$0")" && pwd); B=$HOME/.cache/gap-wave2-20260923/agents-models-workers
WS=$B/ws/g15-$T-$ARM; rm -rf "$WS"; mkdir -p "$WS" "$OUT"; cp -r $B/g15-snapshot/. "$WS"/
PROMPT=$(cat "$D/$T.md" "$D/$ARM-lane-note.md")
EXTRA=()
if [ "$ARM" = with ]; then EXTRA=(-c 'plugins."context-mode@context-mode".mcp_servers.context-mode.default_tools_approval_mode="approve"');
else EXTRA=(-c 'plugins."context-mode@context-mode".enabled=false'); fi
S=$(date -u +%FT%TZ); t0=$(date +%s.%N)
printf '%s' "$PROMPT" | timeout 600 codex exec --sandbox read-only --ephemeral --skip-git-repo-check -C "$WS" \
  -c features.hooks=false -c features.plugin_hooks=false "${EXTRA[@]}" --json - > "$OUT/$T-$ARM.events.jsonl" 2> "$OUT/$T-$ARM.stderr"
RC=$?; t1=$(date +%s.%N)
python3 - "$OUT/$T-$ARM.events.jsonl" "$D/gold.json" "$T" "$ARM" "$RC" "$S" "$t0" "$t1" <<'PY' > "$OUT/$T-$ARM.summary.json"
import json,sys,subprocess
ev,gold,t,arm,rc,s,t0,t1=sys.argv[1:]
usage=[];tools=[];final=None
for l in open(ev):
    if not l.startswith('{'): continue
    e=json.loads(l)
    if e.get('type')=='turn.completed': usage.append(e['usage'])
    if e.get('type') in ('turn.failed','error'): tools.append({'event':e})
    if e.get('type')=='item.completed':
        it=e['item']
        if it['type'] in ('mcp_tool_call','command_execution'):
            tools.append({'type':it['type'],'name':it.get('tool') or (it.get('command') or '')[:120],'status':it.get('status'),
                          'error':(it.get('error') or {}).get('message') if isinstance(it.get('error'),dict) else it.get('error'),
                          'output_chars':len(it.get('aggregated_output') or '') })
        if it['type']=='agent_message': final=it['text']
sc=subprocess.run([sys.executable, gold.replace('gold.json','score.py'), gold, t], input=final or '', capture_output=True, text=True).stdout
tot={k:sum(u.get(k,0) for u in usage) for k in ('input_tokens','cached_input_tokens','output_tokens','reasoning_output_tokens')}
tot['total_tokens']=tot['input_tokens']+tot['output_tokens']
print(json.dumps({'task':t,'arm':arm,'exit':int(rc),'started_at':s,'wall_seconds':round(float(t1)-float(t0),2),'turns':len(usage),'usage_sum':tot,
  'tool_calls':tools,'failed_tool_calls':sum(1 for x in tools if x.get('status')=='failed' or 'event' in x),'final':final,'score':json.loads(sc) if sc else None},indent=1))
PY
cat "$OUT/$T-$ARM.summary.json" | python3 -c "import json,sys;d=json.load(sys.stdin);print(d['task'],d['arm'],d['exit'],d['wall_seconds'],d['usage_sum'],'failed',d['failed_tool_calls'],[ (x.get('type'),x.get('name'),x.get('status'),x.get('output_chars')) for x in d['tool_calls']],d['score'])"
