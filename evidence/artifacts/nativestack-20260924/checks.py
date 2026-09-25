"""Bounded checks of this NativeStack host. No credential values are printed."""
import argparse,hashlib,json,math,os,pathlib,sqlite3,subprocess,sys,tempfile,time,urllib.request
p=argparse.ArgumentParser();p.add_argument('component');p.add_argument('--version-only',action='store_true');p.add_argument('--plan',action='store_true');a=p.parse_args()
h=pathlib.Path.home();e=h/'.local/share/codex-ecosystem';repo=h/'code/native-agent-stack'
versions={'codex':['codex','--version'],'claude-code':['claude','--version'],'rtk':['rtk','--version'],'qmd':['qmd','--version'],'ai-memory':['ai-memory','--version'],'mcporter':['mcporter','--version'],'huggingface-hub-native':['hf','version'],'restic':['restic','version'],'dagu':['dagu','version'],'worktrunk':['wt','--version'],'difftastic':['difft','--version'],'gitleaks':['gitleaks','version'],'zizmor':['zizmor','--version'],'syft':['syft','version'],'qdrant':['qdrant','--version'],'vllm':['vllm','--version'],'systemd':['systemctl','--version'],'prometheus':['prometheus','--version'],'loki':['loki','--version'],'grafana':['grafana','--version'],'alertmanager':['alertmanager','--version'],'ntfy':['ntfy','--version'],'opentelemetry-collector-contrib':['otelcol-contrib','--version'],'llama-cpp':['llama-server','--version'],'candidate:cli-cli':['gh','--version'],'candidate:astral-sh-uv':['uv','--version'],'ccusage':['ccusage','--version']}
def run(args):
 r=subprocess.run(args,cwd=repo,capture_output=True,text=True,timeout=180)
 if r.returncode:print('Native command failed; exit',r.returncode,'Raw diagnostic output is withheld.');raise SystemExit(r.returncode)
 return r.stdout+(r.stderr if a.version_only else '')
def http(port,path,body=None):
 req=urllib.request.Request(f'http://127.0.0.1:{port}{path}',data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=90) as r:return json.load(r)
def mcp(tool,args):
 raw=run(['mcporter','--config',str(e/'config/mcporter.json'),'call',tool,'--args',json.dumps(args),'--output','json','--no-oauth'])
 x=json.loads(raw);assert not x.get('isError',False),str(x)[:300];return x
if a.plan:
 import shutil
 if a.version_only:
  assert a.component in versions;assert shutil.which(versions[a.component][0]),'Required executable absent'
 else:
  assert a.component in {'qmd','ai-memory','jcodemunch-mcp','serena','context-mode','headroom','socraticode','vllm','qdrant','markitdown','rtk','opentelemetry-collector-contrib','prometheus','loki','llama-cpp'}
  assert repo.is_dir() and e.is_dir()
 print('Plan validated component, mode, and local prerequisite paths; functional behavior has not run:',a.component,'version_only',a.version_only);raise SystemExit(0)
if a.version_only:
 assert a.component in versions;v=run(versions[a.component]);print(v[:350]);raise SystemExit(0)
c=a.component
if c=='qmd':
 raw=run(['qmd','--index','nativestack-catalog','search','Native verification tiers','-c','adoption','-n','3','--json']);assert 'adoption' in raw;print('QMD lexical query returned the indexed adoption source.')
elif c=='ai-memory':
 raw=run(['ai-memory','read-page','--workspace','local','--project','native-agent-stack','--path','decisions/nativestack-isolation.md','--json']);assert 'NativeStack' in raw and 'ext4' in raw;print('Native read-page returned the project-scoped isolation decision; body withheld.')
elif c=='jcodemunch-mcp':
 x=mcp('jcodemunch.order',{'action':'get_symbol_source','args':{'repo':'seathatflowsinourveins/native-agent-stack','symbol_id':'fixtures/before.py::greeting#function'}});assert 'Hello' in json.dumps(x);print('Exact indexed greeting source returned with Hello expression.')
elif c=='serena':
 x=mcp('serena.get_symbols_overview',{'relative_path':'fixtures/before.py','depth':1,'max_answer_chars':4000});assert 'greeting' in json.dumps(x);print('Native Serena symbol overview found greeting in fixtures/before.py.')
elif c=='context-mode':
 x=mcp('context-mode.ctx_search',{'queries':['Native verification tiers'],'source':'nativestack-adoption-readme','limit':2});s='\n'.join(i.get('text','') for i in x.get('content',[]));assert 'Repository integrity' in s and 'No installed-runtime claim' in s and 'nativestack-adoption-readme' in s;print('Context Mode returned the indexed Repository integrity row and its No installed-runtime claim boundary.')
elif c=='headroom':
 x=mcp('headroom.headroom_retrieve',{'hash':'40eadeac746d884a2f7b7217'});s=json.dumps(x);assert 'request=0 ' in s and 'request=999 ' in s;print('Headroom restored the first log line and critical 503 anomaly from the retained compression artifact.')
elif c=='socraticode':
 x=mcp('socraticode.codebase_search',{'projectPath':str(repo/'fixtures'),'query':'function greeting returns Hello name','limit':3});s='\n'.join(i.get('text','') for i in x.get('content',[]));assert 'before.py' in s and 'def greeting(name):' in s and 'return "Hello, " + name' in s;print('Semantic search returned before.py with the exact greeting definition and return expression.')
elif c=='vllm':
 x=http(18231,'/v1/embeddings',{'model':'nvidia/Nemotron-3-Embed-1B-BF16','input':['query: NativeStack scoped repository search']});v=x['data'][0]['embedding'];assert len(v)==2048 and all(math.isfinite(i) for i in v);print('Native CUDA vLLM generated 2048 finite embedding values; Nemotron-3-Embed-1B-BF16.')
elif c=='qdrant':
 x=http(26333,'/collections/codebase_b053c4b010f2')['result'];assert x['status']=='green' and x['points_count']>=8;print(json.dumps({'status':x['status'],'points':x['points_count']}))
elif c=='markitdown':
 raw=run(['markitdown',str(h/'.local/state/nativestack/final-acceptance/document.html')]);assert '# NativeStack evidence' in raw and 'Scoped memory' in raw;print('Native HTML conversion preserved the heading and list item.')
elif c=='rtk':
 db=sqlite3.connect(f'file:{h}/.local/share/rtk/history.db?mode=ro',uri=True);n=db.execute("select count(*) from commands where rtk_cmd like '%git status%'").fetchone()[0];assert n>=1;print('RTK local history contains git-status executions; count',n,'Client attribution requires the separate native Claude receipt. No billed-savings claim.')
elif c in ['opentelemetry-collector-contrib','prometheus','loki']:
 if c=='opentelemetry-collector-contrib':
  count=0;services=set()
  for line in (e/'observability/collector/events.jsonl').read_text().splitlines():
   for resource in json.loads(line).get('resourceLogs',[]):
    for scope in resource.get('scopeLogs',[]):
     for log in scope.get('logRecords',[]):assert log.get('body',{}).get('stringValue')=='[content omitted]';count+=1
  assert count>0;print('Native collector retained',count,'logs with all bodies omitted.')
 elif c=='prometheus':
  names=http(19090,'/api/v1/label/__name__/values')['data'];assert any('codex_turn_token_usage' in n for n in names);print('Prometheus contains the native Codex turn-token metric family.')
 else:
  labels=http(13100,'/loki/api/v1/label/service_name/values')['data'];assert 'codex_exec' in labels and 'claude-code' in labels;print('Loki indexed both actual native client service labels.')
elif c=='llama-cpp':
 key=(h/'.config/nativestack/generation.key').read_text().strip();body={'model':'qwen3.8-27b-local','messages':[{'role':'user','content':'Output only {"answer":42}'}],'chat_template_kwargs':{'enable_thinking':False},'response_format':{'type':'json_object'},'max_tokens':64}
 req=urllib.request.Request('http://127.0.0.1:18232/v1/chat/completions',data=json.dumps(body).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+key})
 with urllib.request.urlopen(req,timeout=120) as r:x=json.load(r)
 assert json.loads(x['choices'][0]['message']['content'])=={'answer':42};print(json.dumps({'structured_answer':42,'usage':x.get('usage')}))
else:raise SystemExit('No functional check implemented for '+c)
