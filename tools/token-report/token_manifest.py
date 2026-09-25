#!/usr/bin/env python3
"""Capture native savings reports; preserve evidence without adding overlapping counters."""
import argparse
import base64
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
import re
import shlex
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import tomllib
import uuid
import shutil
from urllib.parse import urlsplit

def now():
    return datetime.now(timezone.utc).isoformat()

def digest(data):
    return hashlib.sha256(data).hexdigest()

def artifact(path, tokens=None):
    path=Path(path)
    data=path.read_bytes()
    return dict(path=str(path),bytes=len(data),sha256=digest(data),tokens=tokens)

def json_script(value):
    return json.dumps(value,ensure_ascii=False,separators=(",",":")).replace("<","\\u003c").replace("\u2028","\\u2028").replace("\u2029","\\u2029")

def template_path():
    return Path(__file__).resolve().with_name("token_manifest.html.in")

def render_reports(config,data):
    source=Path(config["html_template"]).resolve() if config.get("html_template") else template_path().resolve()
    outputs=list(dict.fromkeys(Path(p).resolve() for p in [config["output_html"]]+config.get("output_aliases",[])))
    json_path=Path(config["output_json"]).resolve()
    if source in outputs or json_path==source or json_path in outputs:
        raise ValueError("Rendered output must not overwrite its template or JSON source")
    template=source.read_text()
    if template.count("__DATA__")!=1:
        raise ValueError("Expected exactly one data placeholder in the .html.in template")
    if "__RETURNED_RESULTS_JS__" in template:
        if template.count("__RETURNED_RESULTS_JS__")!=1:
            raise ValueError("Expected exactly one returned-results script placeholder")
        sidecar=Path(__file__).resolve().with_name("returned_results.js")
        if sidecar in outputs or json_path==sidecar:
            raise ValueError("Rendered output must not overwrite its script source")
        template=template.replace("__RETURNED_RESULTS_JS__",sidecar.read_text())
    rendered=template.replace("__DATA__",json_script(data))
    write(json_path,json.dumps(data,ensure_ascii=False,indent=2)+"\n")
    for path in outputs:
        write(path,rendered)
    return [str(p) for p in outputs]

def write(path, text):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix="."+path.name+".",dir=path.parent)
    try:
        with os.fdopen(fd,"w",encoding="utf-8",newline="") as f:
            f.write(text)
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

class Ledger:
    def __init__(self,path):
        path=Path(path)
        path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.db=sqlite3.connect(path,timeout=30)
        try:
            os.chmod(path,0o600)
            self.db.row_factory=sqlite3.Row
            self.db.executescript("""
            CREATE TABLE IF NOT EXISTS snapshots(
              id INTEGER PRIMARY KEY,tool TEXT,scope TEXT,observed_at TEXT,
              success INTEGER,metrics TEXT,evidence TEXT);
            CREATE TABLE IF NOT EXISTS comparisons(
              id TEXT PRIMARY KEY,first_seen TEXT,last_seen TEXT,payload TEXT);
            CREATE TABLE IF NOT EXISTS native_events(
              id TEXT PRIMARY KEY,tool TEXT,scope TEXT,event_time TEXT,saved INTEGER,payload TEXT);
            """)
        except BaseException:
            self.db.close()
            raise
    def close(self):
        self.db.close()
    def snapshot(self,tool,scope,metrics,success,observed_at,evidence):
        with self.db:
            self.db.execute("INSERT INTO snapshots(tool,scope,observed_at,success,metrics,evidence) VALUES(?,?,?,?,?,?)",
                (tool,scope,observed_at,int(success),json.dumps(metrics),json.dumps(evidence)))
    def native_views(self):
        result=[]
        for group in self.db.execute("SELECT DISTINCT tool,scope FROM snapshots ORDER BY tool,scope"):
            rows=list(self.db.execute("SELECT * FROM snapshots WHERE tool=? AND scope=? ORDER BY observed_at DESC,id DESC",tuple(group)))
            def unpack(row):
                return dict(observed_at=row["observed_at"],success=bool(row["success"]),metrics=json.loads(row["metrics"]),evidence=json.loads(row["evidence"]))
            good=[r for r in rows if r["success"]]
            values=[json.loads(r["metrics"]).get("saved") for r in good]
            decreased=len(values)>1 and all(isinstance(v,(int,float)) for v in values[:2]) and values[0]<values[1]
            result.append(dict(tool=group["tool"],scope=group["scope"],latest=unpack(rows[0]),latest_success=unpack(good[0]) if good else None,snapshot_count=len(rows),counter_decreased=decreased))
        return result
    def comparison(self,tool,before,after,encoding,boundary):
        for item in (before,after):
            if not isinstance(item.get("tokens"),int) or item["tokens"]<0:
                raise ValueError("An exact nonnegative tokenizer count is required")
            actual=artifact(item["path"])
            if actual["sha256"]!=item["sha256"] or actual["bytes"]!=item["bytes"]:
                raise ValueError("Evidence changed: "+item["path"])
        key=digest(json.dumps([tool,before["sha256"],after["sha256"],encoding,boundary]).encode())
        payload=dict(id=key,tool=tool,baseline=before,candidate=after,encoding=encoding,boundary=boundary,
                     tokens_removed=before["tokens"]-after["tokens"],provider_tokens_saved=None)
        stamp=now()
        with self.db:
            self.db.execute("INSERT INTO comparisons VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET last_seen=excluded.last_seen",(key,stamp,stamp,json.dumps(payload)))
        return key
    def comparisons(self):
        return [dict(json.loads(r["payload"]),first_seen=r["first_seen"],last_seen=r["last_seen"]) for r in self.db.execute("SELECT * FROM comparisons ORDER BY first_seen,id")]
    def event(self,tool,scope,event_time,saved,identity,payload):
        if not isinstance(saved,int):
            raise ValueError("Native event saved count must be an integer")
        key=digest(json.dumps([tool,scope,identity],sort_keys=True).encode())
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO native_events VALUES(?,?,?,?,?,?)",(key,tool,scope,event_time,saved,json.dumps(payload)))
    def event_totals(self):
        return [dict(r) for r in self.db.execute("SELECT tool,scope,COUNT(*) AS events,SUM(saved) AS estimated_saved,MIN(event_time) AS first_event,MAX(event_time) AS last_event FROM native_events GROUP BY tool,scope ORDER BY tool,scope")]

def capture(argv,cwd,root,label,timeout=60):
    folder=Path(root)/label
    folder.mkdir(mode=0o700)
    start=now()
    try:
        process=subprocess.run(argv,cwd=cwd,capture_output=True,timeout=timeout)
        out,err,code,error=process.stdout,process.stderr,process.returncode,None
    except (OSError,subprocess.TimeoutExpired) as exc:
        out=getattr(exc,"stdout",None) or b""
        err=getattr(exc,"stderr",None) or b""
        code,error=None,str(exc)
    for name,data in [("stdout.txt",out),("stderr.txt",err)]:
        (folder/name).write_bytes(data)
        (folder/name).chmod(0o600)
    receipt=dict(argv=argv,cwd=str(cwd),started_at=start,completed_at=now(),exit_code=code,error=error,
                 stdout=artifact(folder/"stdout.txt"),stderr=artifact(folder/"stderr.txt"),
                 stdout_text=out.decode("utf-8",errors="replace"),stderr_text=err.decode("utf-8",errors="replace"))
    write(folder/"receipt.json",json.dumps(receipt,indent=2))
    return receipt

def count_files(config,paths):
    if not config.get("tokenizer_module"):
        raise ValueError("Exact comparisons require an explicit gpt-tokenizer 3.4.0 o200k_base module path")
    code="const fs=require('fs'),path=require('path');const pkg=JSON.parse(fs.readFileSync(path.resolve(path.dirname(process.argv[1]),'../../package.json'),'utf8'));if(pkg.version!=='3.4.0')throw Error('Pinned tokenizer version mismatch');const {encode}=require(process.argv[1]);process.stdout.write(JSON.stringify(process.argv.slice(2).map(p=>encode(new TextDecoder('utf-8',{fatal:true}).decode(fs.readFileSync(p))).length)));"
    out=subprocess.run([config["node"],"-e",code,config["tokenizer_module"]]+[str(p) for p in paths],capture_output=True,text=True,timeout=30,check=True)
    values=json.loads(out.stdout)
    return [artifact(p,n) for p,n in zip(paths,values)]

def archive_native_events(config,ledger,issues):
    db=Path(config["rtk_database"]) if config.get("rtk_database") else None
    if db and db.exists():
        try:
            with closing(sqlite3.connect(db.as_uri()+"?mode=ro",uri=True)) as source:
                source.row_factory=sqlite3.Row
                rows=source.execute("SELECT id,timestamp,input_tokens,output_tokens,saved_tokens,project_path FROM commands").fetchall()
            for row in rows:
                d=dict(row)
                ledger.event("rtk","Linux tracking database",d["timestamp"],d["saved_tokens"],[str(db),d["id"],d["timestamp"]],d)
        except (sqlite3.Error,ValueError) as exc:
            issues.append("RTK event archive: "+str(exc))
    path=Path(config["headroom_events"]) if config.get("headroom_events") else None
    if path and path.exists():
        try:
            for number,line in enumerate(path.read_text().splitlines(),1):
                try:
                    d=json.loads(line)
                    chosen={k:d[k] for k in ("v","ts","before","after","saved","model","client","source","pid") if k in d}
                    ledger.event("headroom","Linux native event ledger",chosen["ts"],chosen["saved"],chosen,chosen)
                except (ValueError,KeyError) as exc:
                    issues.append("Headroom event line "+str(number)+": "+str(exc))
        except OSError as exc:
            issues.append("Headroom event archive: "+str(exc))

def capture_context(entry,ledger,run,issues):
    evidence={"root":entry["path"]}
    try:
        paths=sorted(Path(entry["path"]).glob("stats-*.json"),key=lambda p:p.stat().st_mtime,reverse=True)
        if not paths:
            raise ValueError("No native persisted stats file available")
        p=paths[0]
        raw=p.read_bytes()  # One immutable observation of an actively rewritten file.
        d=json.loads(raw)
        if not isinstance(d,dict):
            raise ValueError("Native stats must be a JSON object")
        if type(d.get("schemaVersion")) is not int or type(d.get("tokens_saved_lifetime")) is not int or d["tokens_saved_lifetime"]<0:
            raise ValueError("Invalid native schema identity or lifetime counter")
        copied=Path(run)/("context-"+entry["name"].replace(" ","-")+".json")
        copied.write_bytes(raw)
        copied.chmod(0o600)
        evidence=dict(source={"path":str(p),"bytes":len(raw),"sha256":digest(raw)},
                      captured_source=artifact(copied),session_start=d.get("session_start"),
                      source_updated_at=d.get("updated_at"),schema=d["schemaVersion"],version=d.get("version"),
                      access="Read upstream-generated stats JSON; no fresh MCP invocation implied.")
        metrics=dict(saved=d["tokens_saved_lifetime"],session_estimated_saved=d.get("tokens_saved"),kind="upstream event/byte estimate",
                     boundary="Latest persisted upstream file in this runtime root, not a sum of sessions. Lifetime = retained event count × 256; session = kept-out bytes ÷ 4. Not avoided provider usage.",
                     raw=d)
        ledger.snapshot("context-mode",entry["name"],metrics,True,now(),evidence)
    except (OSError,ValueError,TypeError) as exc:
        message="Context Mode "+entry["name"]+": "+str(exc)
        issues.append(message)
        ledger.snapshot("context-mode",entry["name"],{"saved":None,"error":str(exc)},False,now(),evidence)

def retained_projects(config,run,commands,issues):
    """One disjoint partition of the native RTK database; CLI views stay separate."""
    result=[]
    if not config.get("rtk_database"):
        return result
    source=Path(config["rtk_database"])
    if not source.exists():
        return result
    try:
        with closing(sqlite3.connect(source.as_uri()+"?mode=ro",uri=True)) as db:
            db.row_factory=sqlite3.Row
            rows=db.execute("SELECT project_path,COUNT(*) AS events,SUM(input_tokens) AS input_tokens,SUM(output_tokens) AS output_tokens,SUM(saved_tokens) AS estimated_saved,MIN(timestamp) AS first_event,MAX(timestamp) AS last_event FROM commands GROUP BY project_path ORDER BY project_path").fetchall()
        for i,row in enumerate(rows):
            d=dict(row)
            path=d["project_path"]
            d.update(source=str(source),source_method="Read-only native commands table grouped by exact stored project_path",provider_tokens_saved=None)
            if path and Path(path).is_dir():
                r=capture([config["rtk"],"gain","--project","--format","json"],path,run,"rtk-workspace-"+str(i))
                commands.append(r)
                d["native_command"]=r
                try:
                    value=json.loads(r["stdout_text"])["summary"]["total_saved"]
                    d["command_status"]="Returned native report" if r["exit_code"]==0 and type(value) is int else "Native report failed"
                except (ValueError,KeyError,TypeError):
                    d["command_status"]="Native report failed"
                if d["command_status"]=="Native report failed":
                    issues.append("RTK workspace query failed: "+path)
            else:
                d["command_status"]="Retained database records only; original working directory unavailable"
            result.append(d)
    except (OSError,sqlite3.Error) as exc:
        issues.append("RTK workspace inventory: "+str(exc))
    return result

def capture_json_source(path,run,label):
    """Retain the exact evidence read once; external receipts remain dated studies."""
    path=Path(path)
    raw=path.read_bytes()
    saved=Path(run)/(label+".json")
    saved.write_bytes(raw)
    saved.chmod(0o600)
    payload=json.loads(raw)
    return dict(origin=str(path),artifact=artifact(saved),result=payload)

def capture_choice_source(path,run,label):
    """Embed upstream streams only when retained bytes match their receipt."""
    captured=capture_json_source(path,run,label)
    def verified(item):
        data=Path(item['path']).read_bytes()
        if len(data)!=item['bytes'] or digest(data)!=item['sha256']:
            raise ValueError('Evidence changed: '+item['path'])
        return data
    for operation in captured['result'].get('operations',[]):
        for stream in ('stdout','stderr'):
            operation[stream+'_text']=verified(operation[stream]).decode('utf-8',errors='replace')
    for comparison in captured['result'].get('comparisons',[]):
        for role in ('baseline_artifact','candidate_artifact','selected_artifact'):
            verified(comparison[role])
    return captured

RETURNED_RESULTS_FILE_LIMIT=2*1024*1024
RETURNED_RESULTS_TOTAL_LIMIT=16*1024*1024

def capture_returned_results(path,run,label):
    """Import explicitly selected evidence without executing or discovering commands."""
    captured=capture_json_source(path,run,label)
    payload=captured["result"]
    def require(condition,message):
        if not condition:
            raise ValueError("Returned results: "+message)
    def text(value):
        return isinstance(value,str) and bool(value.strip())
    def argv(value):
        return isinstance(value,list) and bool(value) and all(text(x) for x in value)
    require(isinstance(payload,dict),"manifest must be an object")
    require(type(payload.get("schema_version")) is int and payload["schema_version"]==1,"schema_version must be 1")
    require(text(payload.get("captured_at")) and text(payload.get("scope")),"captured_at and scope are required")
    require(isinstance(payload.get("records"),list),"records must be an array")
    ids=set();pending=[];total=0
    for index,record in enumerate(payload["records"]):
        require(isinstance(record,dict),"each record must be an object")
        for key in ("id","runtime","kind","status","boundary"):
            require(text(record.get(key)),key+" must be a nonempty string")
        require(record["id"] not in ids,"duplicate record id: "+record["id"])
        ids.add(record["id"])
        components=record.get("component_ids")
        require(isinstance(components,list) and all(text(x) for x in components),"component_ids must be an array of strings")
        command=record.get("command")
        valid_command=argv(command) or (isinstance(command,dict) and (
            argv(command.get("argv")) or (text(command.get("tool")) and isinstance(command.get("arguments"),dict))))
        require(valid_command,"command must contain argv or a tool with arguments")
        for key in ("started_at","completed_at"):
            require(key in record and (record[key] is None or text(record[key])),key+" must be a string or null")
        require(isinstance(record.get("observation"),(str,dict)),"observation must be a string or object")
        require(isinstance(record.get("attachments"),list),"attachments must be an array")
        labels=set()
        for number,item in enumerate(record["attachments"]):
            require(isinstance(item,dict),"each attachment must be an object")
            require(text(item.get("label")) and text(item.get("path")),"attachment label and path are required")
            require(item["label"] not in labels,"duplicate attachment label: "+item["label"])
            labels.add(item["label"])
            require(type(item.get("bytes")) is int and 0<=item["bytes"]<=RETURNED_RESULTS_FILE_LIMIT,"attachment exceeds 2 MiB or has invalid bytes")
            require(isinstance(item.get("sha256"),str) and re.fullmatch(r"[0-9a-fA-F]{64}",item["sha256"]) is not None,"attachment sha256 is invalid")
            require("mime_type" not in item or text(item["mime_type"]),"attachment mime_type must be a nonempty string")
            total+=item["bytes"]
            require(total<=RETURNED_RESULTS_TOTAL_LIMIT,"attachments exceed 16 MiB in total")
            original=Path(item["path"])
            if not original.is_absolute():
                original=Path(path).resolve().parent/original
            require(original.is_file(),"attachment is missing or not a regular file: "+str(original))
            with original.open("rb") as stream:
                raw=stream.read(RETURNED_RESULTS_FILE_LIMIT+1)
            require(len(raw)==item["bytes"] and digest(raw)==item["sha256"].lower(),"evidence changed: "+str(original))
            pending.append((index,number,item,original,raw))
    destination=Path(run)/"returned-results-artifacts"
    if pending:
        destination.mkdir(mode=0o700)
    for index,number,item,original,raw in pending:
        saved=destination/f"{index:04d}-{number:04d}.bin"
        with saved.open("xb") as stream:
            stream.write(raw)
        saved.chmod(0o600)
        item.update(origin=str(original),path=str(saved),sha256=digest(raw),
                    content_base64=base64.b64encode(raw).decode("ascii"),
                    mime_type=item.get("mime_type","application/octet-stream"))
        # Never trust a caller-supplied preview or download instead of source bytes.
        item.pop("text",None)
        try:
            item["text"]=raw.decode("utf-8")
        except UnicodeDecodeError:
            pass
    captured["imported_at"]=now()
    return captured

def claude_rtk_hook_enabled(settings):
    if settings.get("disableAllHooks",False):
        return False
    for group in settings.get("hooks",{}).get("PreToolUse",[]):
        try:
            if not re.fullmatch(group.get("matcher",""),"Bash"):
                continue
        except re.error:
            continue
        for hook in group.get("hooks",[]):
            if hook.get("type")!="command":
                continue
            try:
                argv=shlex.split(hook.get("command",""))
                if argv and Path(argv[0]).name=="rtk" and argv[1:3]==["hook","claude"]:
                    return True
            except ValueError:
                continue
    return False

def codex_hooks_enabled(config):
    # codex-cli 0.155.1 `codex features list`: hooks is stable and on by default; codex_hooks is its
    # legacy alias; plugin_hooks is removed (always false), so it no longer gates plugin hooks.
    features=config.get("features",{})
    value=features.get("hooks",features.get("codex_hooks")) if isinstance(features,dict) else None
    return True if value is None else value is True

def native_hook_inventory(config,run,issues,ledger=None):
    rows=[]
    query="SELECT source_hook,COUNT(*),MIN(created_at),MAX(created_at) FROM session_events GROUP BY source_hook"
    for entry in config["context_roots"]:
        sessions=Path(entry["path"])
        home=sessions.parents[1]
        claude=home.name==".claude"
        cfg=home/("settings.json" if claude else "config.toml")
        row=dict(runtime=entry["name"],observed_at=now(),state_root=str(sessions),source_query=query,
                 configured_hooks=[],observed_hook_sources={},project_events={},databases=[],errors=[])
        try:
            raw=cfg.read_bytes()
            d=json.loads(raw) if claude else tomllib.loads(raw.decode())
            row["configuration_source"]=dict(path=str(cfg),sha256=digest(raw),disclosure="Only allowlisted enable flags; private configuration is not copied")
            row["context_mode_enabled"]=d.get("enabledPlugins",{}).get("context-mode@context-mode",False) if claude else d.get("plugins",{}).get("context-mode@context-mode",{}).get("enabled",False)
            row["hook_engine_enabled"]=not d.get("disableAllHooks",False) if claude else codex_hooks_enabled(d)
            row["rtk_automatic_configured"]=claude_rtk_hook_enabled(d) if claude else False
            row["rtk_lane"]="Native Claude Bash hook configured; historical decisions in RTK database" if row["rtk_automatic_configured"] else "Explicit RTK commands; automatic Codex RTK rewrite not configured"
            relative="hooks/hooks.json" if claude else ".codex-plugin/hooks.json"
            manifests=sorted(home.glob("plugins/cache/context-mode/context-mode/*/"+relative),key=lambda p:p.stat().st_mtime,reverse=True)
            if manifests:
                p=manifests[0];h=json.loads(p.read_text())
                row["configured_hooks"]=sorted(h.get("hooks",{}))
                row["hook_manifest"]=artifact(p)
            else:
                row["errors"].append("Installed hook manifest unavailable")
        except (OSError,ValueError,TypeError) as exc:
            row["errors"].append("Configuration query: "+str(exc))
        for p in sorted(sessions.glob("*.db")):
            try:
                with closing(sqlite3.connect(p.as_uri()+"?mode=ro",uri=True,timeout=2)) as db, db:
                    db.execute("BEGIN")
                    found=db.execute(query).fetchall()
                    projects=db.execute("SELECT project_dir,COUNT(*),MIN(created_at),MAX(created_at) FROM session_events GROUP BY project_dir").fetchall()
                    if ledger:
                        # Deliberately exclude prompts, file contents, event data and embeddings.
                        events=db.execute("SELECT id,session_id,source_hook,created_at,project_dir FROM session_events").fetchall()
                        for identifier,session,hook,stamp,project in events:
                            ledger.event("context-mode",entry["name"]+" / archived event estimate",stamp,256,
                                         [str(p),session,identifier,stamp],dict(source_database=str(p),event_id=identifier,session_id=session,source_hook=hook,project_path=project,
                                         boundary="One retained event ×256 upstream heuristic; not measured token avoidance"))
                row["databases"].append(str(p))
                for source,count,first,last in found:
                    v=row["observed_hook_sources"].setdefault(source or "unknown",dict(events=0,first_event=first,last_event=last))
                    v["events"]+=count
                    v["first_event"]=min(v["first_event"],first)
                    v["last_event"]=max(v["last_event"],last)
                for project,count,first,last in projects:
                    v=row["project_events"].setdefault(project or "Unattributed",dict(events=0,first_event=first,last_event=last))
                    v["events"]+=count;v["first_event"]=min(v["first_event"],first);v["last_event"]=max(v["last_event"],last)
            except (sqlite3.Error,TypeError) as exc:
                row["errors"].append(p.name+": "+str(exc))
        row["retained_events"]=sum(v["events"] for v in row["observed_hook_sources"].values())
        row["unobserved_hooks"]=sorted(set(row["configured_hooks"])-set(row["observed_hook_sources"]))
        row["scope_note"]="Source labels show retained observations, not complete lifecycle acceptance. Startup rule rows may use a different source label. Context Mode trims old sessions and caps events. These counts are not added to lifetime snapshots."
        if row["errors"]:
            issues.append(entry["name"]+": incomplete hook inventory; inspect retained errors")
        rows.append(row)
    path=Path(run)/"native-hook-inventory.json"
    write(path,json.dumps(rows,indent=2));path.chmod(0o600)
    return dict(observed_at=now(),artifact=artifact(path),runtimes=rows,
                prior_acceptance=config.get("prior_hook_acceptance"),
                prior_scope="Only explicitly configured local sources were inspected; no native client task acceptance is inferred.")

def capture_jcodemunch(config,ledger,run,commands,issues):
    """Retain upstream cumulative estimates; never add repeated snapshots."""
    if not config.get("jcodemunch_stats_argv"):
        return
    r=capture(config["jcodemunch_stats_argv"],config["project"],run,"jcodemunch")
    commands.append(r)
    metrics={"saved":None,"kind":"upstream bytes/4 estimate",
      "boundary":"Persistent upstream retrieval estimate, including validation calls. Whole-file counterfactual; not measured provider savings. Custom index-root accounting has an upstream gap in 1.108.319; the default root is used. Schema-size estimates are separate and never added."}
    success=r["exit_code"]==0
    try:
        parsed=json.loads(r["stdout_text"])
        saved=parsed["total_tokens_saved"]
        if type(saved) is not int or saved<0:
            raise ValueError("Invalid native cumulative counter")
        metrics.update(saved=saved,basis=parsed.get("total_tokens_saved_basis"),
          by_tool=parsed.get("lifetime_by_tool"),since=parsed.get("lifetime_by_tool_since"),
          session_calls=parsed.get("session_calls"),raw=parsed)
    except (ValueError,KeyError,TypeError) as exc:
        success=False;metrics["error"]=str(exc)
    if not success:
        issues.append("jcodemunch: native counter refresh failed; last successful snapshot remains separate")
    ledger.snapshot("jcodemunch","Linux / upstream default index",metrics,success,r["completed_at"],r)

def native_tool_identity(component_id):
    return {"jcodemunch-mcp":"jcodemunch"}.get(component_id,component_id)

def coverage_matrix(stack,audit,gaps,fresh,comparisons):
    old={c["id"]:c for c in audit.get("coverage",[])}
    gap={c["id"]:c for c in (gaps or {}).get("components",[])}
    recent={c["id"]:c for c in (fresh or {}).get("components",[])}
    ops=audit.get("operations",[])+(gaps or {}).get("operations",[])+(fresh or {}).get("operations",[])
    native={"rtk":("retained estimate","rtk gain --format json; rtk gain --project --format json","90-day configured retention; global includes project views"),
            "context-mode":("retained estimate","ctx_stats({})","Runtime-specific byte/event estimates; 7-day startup cleanup and 1000 events/session cap"),
            "headroom":("retained estimate","headroom savings --json","Native lifetime field covers last 30 days; offline artifact guards do not add events"),
            "jcodemunch":("cumulative estimate","order(action=\"get_session_stats\", args={})","Persistent bytes/4 whole-file retrieval estimate; repeated calls count again; default index root keeps retrieval accounting and stats aligned"),
            "toon":("per conversion","toon INPUT.json --stats --output OUTPUT.toon","No upstream lifetime ledger; compact JSON can be smaller")}
    usage={"codex","claude-code","ccusage","claude-hud","codex-for-claude","promptfoo","vllm","opentelemetry-collector-contrib","prometheus","loki","grafana","alertmanager","ntfy"}
    result=[]
    for c in stack["components"]:
        identity=c["id"]
        tool_identity=native_tool_identity(identity)
        merged={**old.get(identity,{}),**c,**gap.get(identity,{})}
        related=[o for o in ops if identity in o.get("components",[])]
        measured=[p for p in comparisons if p["tool"]==tool_identity]
        kind,command,boundary=native.get(tool_identity,("usage only" if identity in usage else "no verified native savings counter","", "Usage counters report consumed tokens, not avoided tokens" if identity in usage else "Role-specific tool; a before/after saving requires a defined same-task baseline"))
        baseline="Exact retained-output pair" if measured else "No matched token baseline"
        if merged.get("status")=="Guidance / source":
            baseline="Guidance: standalone token baseline not applicable"
        result.append(dict(id=identity,repository=c["repository"],profile=c.get("profile"),role=c.get("role"),version=c.get("version"),
          adoption_status=merged.get("status","Evidence unavailable"),adoption_scope=merged.get("scope"),
          latest_pass=recent.get(identity),native_lifetime_kind=kind,native_command=command,lifetime_boundary=boundary,
          exact_lifetime_provider_saved=None,baseline_status=baseline,comparison_ids=[p["id"] for p in measured],
          operations=[o["id"] for o in related],passed_operations=sum(o.get("passed") is True for o in related),
          failed_operations=sum(o.get("passed") is False for o in related),upstream_commands=c.get("commands",[]),
          hook_status="See client-specific hook evidence" if identity in {"context-mode","rtk","ai-memory","codex","claude-code","codex-for-claude","claude-hud"} else "Selected command / service / guidance; no automatic client hook verified"))
    return result

def repository_coverage(catalog,matrix):
    def key(value):
        value=value.lower().rstrip("/")
        if "://" not in value and value.count("/")==1:
            value="https://github.com/"+value
        parsed=urlsplit(value)
        if parsed.hostname=="github.com":
            parts=parsed.path.strip("/").split("/")
            if len(parts)>=2:
                return "https://github.com/"+parts[0]+"/"+parts[1].removesuffix(".git")
        return value.removesuffix(".git")
    selected={key(c["repository"]):c for c in matrix}
    result=[]
    for row in catalog["records"]:
        component=next((selected[key(url)] for url in [row["repository"]]+row.get("aliases",[]) if key(url) in selected),None)
        types=row.get("record_types",[])
        category="Selected stack" if component else "Other catalog card" if "catalog_card" in types else "Research supplement" if "research_supplement" in types else "Legacy candidate" if "legacy_candidate" in types else "Star review only"
        result.append(dict(repository=row["repository"],classification=category,component_id=component["id"] if component else None,
          execution_status=component["adoption_status"] if component else "No local command run imported for this repository; inspect source decisions",
          native_lifetime_kind=component["native_lifetime_kind"] if component else "Not verified",
          exact_lifetime_provider_saved=None,baseline_status=component["baseline_status"] if component else "No local matched token baseline",
          references=row.get("references",[])))
    return result

def dollar_explanation(context):
    text="\n".join(x.get("text","") for x in (context or {}).get("result",{}).get("content",[]) if x.get("type")=="text")
    match=re.search(r"\$([\d,.]+) this session\s*·\s*\$([\d,.]+) lifetime",text)
    dollar_line=next((line.strip() for line in text.splitlines() if re.match(r"^\s*\$[\d,.]+ of .+ tokens your team didn't burn\.",line)),None)
    return dict(quoted_source="No prior quotation imported; original host history is unknown",
      current_footer=match.group(0) if match else None,current_runtime=(context or {}).get("runtime"),captured_at=(context or {}).get("captured_at"),
      current_dollar_line=dollar_line,
      session_formula="round((bytes kept out + cache bytes saved) / 4) × assumed input price / 1,000,000",
      footer_lifetime_formula="(retained memory events × 256 + current session estimated tokens) × assumed input price / 1,000,000",
      persisted_lifetime_formula="retained memory events × 256 (excludes current session byte estimate)",
      fallback_price="Installed renderer fallback: $5 per million input tokens; PI_CONTEXT_MODE_PRICE_OUTPUT_PER_TOKEN can override it. Illustrative value; no provider billing or subscription savings measurement.",
      retention="Installed version 1.0.169 caps 1000 events per session and runs 7-day session cleanup on startup; the lifetime estimate can decrease.",
      why_small="Only observed records in that runtime's data store contribute. Other tools, clients, unrecorded history and future repository adoption are not counted.",
      practical_limit="Do not add runtime counters, repeated snapshots, artifact deltas or study differences into a PC lifetime dollar total.")

def empty_audit():
    """Absent historical receipts mean unmeasured, never a passed host run."""
    return {"operations":[],"coverage":[],"comparisons":[],"provider_pairs":[],
            "provider_runs":[],"headroom":{"fixtures":[]}}

def load_config(path):
    path=Path(path).expanduser().resolve()
    config=json.loads(path.read_text())
    for required in ("state_dir","project"):
        if not config.get(required):
            raise ValueError("Configuration must explicitly set "+required)
    repository=Path(__file__).resolve().parents[2]
    config.setdefault("publication",str(repository))
    config.setdefault("catalog_index",str(repository/"catalogs/us-equities/decision-index.json"))
    config.setdefault("stack_manifest",str(repository/"manifests/stack.json"))
    config.setdefault("practice_guide",str(Path(__file__).resolve().with_name("README.md")))
    config.setdefault("node",shutil.which("node") or "node")
    config.setdefault("context_roots",[])
    config.setdefault("supporting_inventory",[])
    fields=("state_dir","project","publication","catalog_index","stack_manifest","practice_guide",
            "output_html","output_json","tokenizer_module","rtk_database","headroom_events",
            "context_capture","audit_json","gap_summary","hook_evidence","fresh_e2e","native_study",
            "retrieval_evaluation","native_installation","native_client_acceptance","native_choices",
            "returned_results_json","html_template")
    def resolve(value):
        expanded=os.path.expandvars(os.path.expanduser(str(value)))
        if re.search(r"\$\{?[A-Za-z_]",expanded):
            raise ValueError("Unexpanded environment variable in configured path: "+str(value))
        p=Path(expanded)
        return str((path.parent/p).resolve() if not p.is_absolute() else p.resolve())
    for key in fields:
        if config.get(key):
            config[key]=resolve(config[key])
    for entry in config["context_roots"]:
        entry["path"]=resolve(entry["path"])
    if config.get("output_aliases"):
        config["output_aliases"]=[resolve(p) for p in config["output_aliases"]]
    config.setdefault("output_json",str(Path(config["state_dir"])/"manifest.json"))
    config.setdefault("output_html",str(Path(config["state_dir"])/"manifest.html"))
    config["refresh_command"]=shlex.join(["python3",str(Path(__file__).resolve()),"refresh","--config",str(path)])
    return config

def initialize_config(path,state_dir,project,rtk=None,headroom=None,jcodemunch=None,mcporter="mcporter"):
    path=Path(path).expanduser().resolve()
    if path.exists():
        raise ValueError("Configuration already exists; edit it explicitly instead of overwriting")
    project=Path(project).expanduser().resolve()
    if not project.is_dir():
        raise ValueError("Selected project directory does not exist")
    config={"schema_version":1,"state_dir":str(Path(state_dir).expanduser().resolve()),
            "project":str(project),"rtk":rtk,"headroom":headroom,"context_roots":[],
            "inspect_hook_history":False,"inspect_project_history":False,
            "rtk_database":None,"headroom_events":None,"audit_json":None,"gap_summary":None,
            "toon":None,"tokenizer_module":None}
    if jcodemunch:
        config["jcodemunch_stats_argv"]=[shutil.which(mcporter) or mcporter,"call","--stdio",
          shutil.which(jcodemunch) or jcodemunch,"--env","CODE_INDEX_PATH="+str(Path.home()/".code-index"),
          "--env","JCODEMUNCH_SHARE_SAVINGS=0","--name","jcodemunch","--tool","order",
          "--args",'{"action":"get_session_stats","args":{}}',"--output","json","--no-oauth"]
    write(path,json.dumps(config,indent=2)+"\n")
    return {"config":str(path),"state_directory":config["state_dir"],
            "next":"refresh --config "+str(path)}

def compare_artifacts(config,tool,before,after,boundary):
    """Retain immutable exact inputs; this does not certify semantic quality."""
    root=Path(config["state_dir"])
    evidence=root/"artifacts"
    evidence.mkdir(parents=True,exist_ok=True,mode=0o700)
    copies=[]
    for source in (before,after):
        raw=Path(source).read_bytes()
        target=evidence/(digest(raw)+".txt")
        if target.exists() and target.read_bytes()!=raw:
            raise ValueError("Existing retained artifact does not match its content hash")
        if not target.exists():
            write(target,raw.decode("utf-8",errors="strict"))
        copies.append(target)
    first,second=count_files(config,copies)
    ledger=Ledger(root/"ledger.sqlite3")
    try:
        key=ledger.comparison(tool,first,second,"o200k_base",boundary)
    finally:
        ledger.close()
    return {"comparison_id":key,"baseline":first,"candidate":second,
            "tokens_removed":first["tokens"]-second["tokens"],"provider_tokens_saved":None,
            "semantic_acceptance":"Not inferred. The operator-supplied boundary must describe the same task and its quality check."}

def refresh(config,context_file=None):
    scopes=config.get("counter_scopes",{})
    if not isinstance(scopes,dict) or set(scopes)-{"rtk_global","rtk_project","headroom"} or any(
            not isinstance(value,str) or not value.strip() for value in scopes.values()):
        raise ValueError("counter_scopes must map selected counter keys to nonempty scope strings")
    root=Path(config["state_dir"])
    root.mkdir(parents=True,exist_ok=True,mode=0o700)
    run=root/"captures"/(datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")+"-"+uuid.uuid4().hex[:8])
    run.mkdir(parents=True,mode=0o700)
    ledger=Ledger(root/"ledger.sqlite3")
    issues=[];commands=[]
    try:
        for label,tool,scope,argv,boundary in [
          ("rtk-global","rtk",scopes.get("rtk_global","Native / all retained projects"),[config.get("rtk"),"gain","--format","json"],"Native retained-history estimate. Global includes project counters; retention depends on the selected installation."),
          ("rtk-project","rtk",scopes.get("rtk_project","Native / project "+config["project"]),[config.get("rtk"),"gain","--project","--format","json"],"Native estimates for this working directory only; already included in global."),
          ("headroom","headroom",scopes.get("headroom","Native / last 30 days"),[config.get("headroom"),"savings","--json"],"Upstream field named lifetime is capped at 30 days in version 0.37.0; local offline guards do not append native events.")]:
            if not argv[0]:
                continue
            r=capture(argv,config["project"],run,label);commands.append(r)
            metrics={"saved":None,"boundary":boundary}
            success=r["exit_code"]==0
            try:
                parsed=json.loads(r["stdout_text"])
                value=parsed["summary"]["total_saved"] if tool=="rtk" else parsed["lifetime"]["tokens_saved"]
                if type(value) is not int or value<0: raise ValueError("Native saved counter missing or invalid")
                metrics.update(saved=value,raw=parsed,kind="upstream estimate")
            except (ValueError,KeyError,TypeError) as exc:
                success=False;metrics["error"]=str(exc)
            if not success:
                issues.append(label+": native counter refresh failed; last successful snapshot remains separate")
            ledger.snapshot(tool,scope,metrics,success,r["completed_at"],r)
        capture_jcodemunch(config,ledger,run,commands,issues)
        archive_native_events(config,ledger,issues)
        projects=retained_projects(config,run,commands,issues) if config.get("inspect_project_history") else []
        for entry in config.get("context_roots",[]):
            capture_context(entry,ledger,run,issues)
        context_value=context_file or config.get("context_capture")
        context_capture=json.loads(Path(context_value).read_text()) if context_value else None
        source_origin=Path(config["catalog_index"])
        source_bytes=source_origin.read_bytes()
        source=run/"catalog.original.json"
        source.write_bytes(source_bytes)
        source.chmod(0o600)
        index=json.loads(source_bytes)
        stack=json.loads(Path(config["stack_manifest"]).read_text())
        compact=run/"catalog.compact.json"
        write(compact,json.dumps(index,ensure_ascii=False,separators=(",",":")))
        toon_result=dict(enabled=bool(config.get("toon")),roundtrip_exact=False,upstream_has_lifetime_counter=False,
                         scope="Optional per-artifact conversion; disabled unless an executable is explicitly configured.")
        if config.get("toon"):
            candidate=run/"catalog.toon";recovered=run/"catalog.recovered.json"
            encode=capture([config["toon"],str(source),"--stats","--output",str(candidate)],config["project"],run,"toon-encode");commands.append(encode)
            decode=capture([config["toon"],str(candidate),"--decode","--strict","--output",str(recovered)],config["project"],run,"toon-decode");commands.append(decode)
            toon_result.update(baseline_catalog=artifact(source),catalog_origin=str(source_origin))
            try:
                if encode["exit_code"]!=0 or decode["exit_code"]!=0: raise ValueError("Native TOON encode/decode failed")
                if json.loads(recovered.read_text())!=index: raise ValueError("Native strict roundtrip changed catalog")
                before,after,original=count_files(config,[compact,candidate,source])
                key=ledger.comparison("toon",before,after,"o200k_base","complete grand catalog, compact JSON baseline; native semantic roundtrip")
                toon_result.update(roundtrip_exact=True,baseline=before,candidate=after,original=original,tokens_removed=before["tokens"]-after["tokens"],original_to_toon_removed=original["tokens"]-after["tokens"],comparison_id=key,
                                   selected_format="toon" if after["tokens"]<before["tokens"] else "compact JSON",selected_file=str(candidate if after["tokens"]<before["tokens"] else compact),selected_tokens=min(before["tokens"],after["tokens"]))
            except (OSError,ValueError,subprocess.SubprocessError) as exc:
                toon_result["error"]=str(exc);issues.append("TOON: "+str(exc))
        audit=empty_audit()
        if config.get("audit_json"):
            audit.update(json.loads(Path(config["audit_json"]).read_text()))
        for pair in audit["comparisons"]:
            try:
                ledger.comparison(pair["component"],pair["baseline_artifact"],pair["candidate_artifact"],"o200k_base",pair["id"]+": "+pair["type"])
            except (OSError,ValueError) as exc:
                issues.append("Prior comparison "+pair["id"]+": "+str(exc))
        gaps=json.loads(Path(config["gap_summary"]).read_text()) if config.get("gap_summary") else None
        if gaps:
            for operation in gaps.get("operations",[]):
                operation["source_operation_id"]=operation["id"]
                operation["id"]="gap-"+operation["id"]
            for component in gaps.get("components",[]):
                component["operation_ids"]=["gap-"+identifier for identifier in component.get("operation_ids",[])]
        extra={}
        for label,key in [("hook-evidence","hook_evidence"),("fresh-e2e","fresh_e2e"),("native-study","native_study"),("retrieval-evaluation","retrieval_evaluation"),("native-installation","native_installation"),("native-client-acceptance","native_client_acceptance"),("native-choices","native_choices"),("returned-results","returned_results_json")]:
            if config.get(key):
                try:
                    loader=capture_returned_results if key=='returned_results_json' else capture_choice_source if key=='native_choices' else capture_json_source
                    extra["returned_results" if key=='returned_results_json' else key]=loader(config[key],run,label)
                except (OSError,ValueError) as exc:
                    issues.append(label+": "+str(exc))
        fresh=extra.get("fresh_e2e",{}).get("result")
        for pair in (fresh or {}).get("comparisons",[]):
            try:
                if pair.get("acceptance_passed") is not True or pair.get("shared_acceptance",{}).get("passed") is not True:
                    raise ValueError("Fresh comparison has no passing shared acceptance gate")
                ledger.comparison(pair["component"],pair["baseline_artifact"],pair["candidate_artifact"],"o200k_base",pair["id"]+": "+pair["type"])
            except (OSError,ValueError,KeyError) as exc:
                issues.append("Fresh comparison: "+str(exc))
        matrix=coverage_matrix(stack,audit,gaps,fresh,ledger.comparisons())
        hooks=native_hook_inventory(config,run,issues,ledger) if config.get("inspect_hook_history") else dict(
            runtimes=[],prior_scope="Hook and session-database inspection was not selected.")
        for component in matrix:
            component["native_reports"]=[r for r in ledger.native_views() if r["tool"]==native_tool_identity(component["id"])]
        try:
            registry=capture_json_source(Path(config["publication"])/"manifests/evidence.json",run,"publication-receipt-registry")
            extra["publication_registry"]=registry
            for component in matrix:
                component["canonical_receipts"]=[r for r in registry["result"]["receipts"] if component["id"] in r.get("component_ids",[])]
        except (OSError,ValueError,KeyError) as exc:
            issues.append("Canonical acceptance registry: "+str(exc))
        data=dict(schema_version=1,generated_at=now(),state_directory=str(root),database=str(root/"ledger.sqlite3"),
          native=ledger.native_views(),preserved_native_events=ledger.event_totals(),comparisons=ledger.comparisons(),
          context_direct=context_capture,toon=toon_result,commands=commands,audit=audit,
          catalog=index,stack=stack,gaps=gaps,issues=issues,configuration=config,
          coverage_matrix=matrix,repository_coverage=repository_coverage(index,matrix),project_counters=projects,
          additional_evidence=extra,dollar_explanation=dollar_explanation(context_capture),
          hook_inventory=hooks,
          scope=str(len(stack["components"]))+" selected stack components plus explicit support runtimes; catalog research coverage is separate. No exact full-PC lifetime provider saving is established.",
          setup={"refresh_command":config.get("refresh_command","python3 tools/token-report/token_manifest.py refresh --config YOUR_CONFIG.json"),"native_hooks":"No client configuration, hooks, telemetry exporter or scheduler is installed by this reporter.",
                 "history":"Append-only local snapshots and deduplicated native events preserve observations across sessions. Missing/expired records cannot be reconstructed. Refresh within source retention windows.",
                 "artifact_history":"Unique evidenced transformations, not actual use counts or a lifetime provider counter. Re-importing the same bytes does not add savings."})
        rendered_paths=render_reports(config,data)
        write(run/"summary.json",json.dumps({"generated_at":data["generated_at"],"output_html":config["output_html"],"issues":issues,"comparison_count":len(data["comparisons"])},indent=2))
        return {"html":config["output_html"],"html_entrypoints":rendered_paths,"json":config["output_json"],"capture":str(run),"issues":issues,"native_scopes":len(data["native"]),"unique_comparisons":len(data["comparisons"])}
    finally:
        ledger.close()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action",choices=["init-config","refresh","compare"])
    parser.add_argument("--config",type=Path,required=True)
    parser.add_argument("--context-stats-file",type=Path)
    parser.add_argument("--state-dir",type=Path)
    parser.add_argument("--project",type=Path)
    parser.add_argument("--rtk")
    parser.add_argument("--headroom")
    parser.add_argument("--jcodemunch")
    parser.add_argument("--mcporter",default="mcporter")
    parser.add_argument("--tool")
    parser.add_argument("--before",type=Path)
    parser.add_argument("--after",type=Path)
    parser.add_argument("--boundary")
    args=parser.parse_args()
    if args.action=="init-config":
        if not args.state_dir or not args.project:
            parser.error("init-config requires --state-dir and --project")
        result=initialize_config(args.config,args.state_dir,args.project,args.rtk,args.headroom,args.jcodemunch,args.mcporter)
        print(json.dumps(result,indent=2));return 0
    config=load_config(args.config)
    if args.action=="compare":
        if not all([args.tool,args.before,args.after,args.boundary]):
            parser.error("compare requires --tool, --before, --after and --boundary")
        print(json.dumps(compare_artifacts(config,args.tool,args.before,args.after,args.boundary),indent=2));return 0
    result=refresh(config,args.context_stats_file)
    print(json.dumps(result,indent=2))
    return 1 if result["issues"] else 0

if __name__=="__main__":
    raise SystemExit(main())
