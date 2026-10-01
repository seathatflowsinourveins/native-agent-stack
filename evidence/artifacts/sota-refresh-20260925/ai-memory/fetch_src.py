import json, subprocess, base64, sys, os
REPO="akitaonrails/ai-memory"
def gh(path):
    return json.loads(subprocess.run(["gh","api",path],check=True,capture_output=True,text=True).stdout)
trees={}
for tag in ("v2.3.2","v2.4.0"):
    t=gh(f"repos/{REPO}/git/trees/{tag}?recursive=1")
    assert not t.get("truncated"), tag
    trees[tag]={e["path"]:e["sha"] for e in t["tree"] if e["type"]=="blob"}
    json.dump(trees[tag],open(f"tree_{tag}.json","w"),indent=0)
want=["crates/ai-memory-cli/src/lib.rs","crates/ai-memory-cli/src/cli.rs","crates/ai-memory-cli/src/marker.rs",
"crates/ai-memory-cli/src/process_guard.rs","crates/ai-memory-cli/src/http_client.rs","crates/ai-memory-cli/src/config.rs",
"crates/ai-memory-cli/src/commands/hook.rs","crates/ai-memory-cli/src/commands/hook_spool.rs",
"crates/ai-memory-cli/src/commands/hook_drain_process.rs","crates/ai-memory-cli/src/commands/hook_capture.rs",
"crates/ai-memory-cli/src/commands/backup.rs","crates/ai-memory-cli/src/commands/restore.rs",
"crates/ai-memory-cli/src/commands/serve.rs","crates/ai-memory-cli/src/commands/status.rs",
"crates/ai-memory-mcp/src/server.rs"]
for p in want:
    a=trees["v2.3.2"].get(p); b=trees["v2.4.0"].get(p)
    print(f"{'SAME' if a==b else 'DIFF'} {p} v2.3.2={str(a)[:10]} v2.4.0={str(b)[:10]}")
    for tag,sha in (("v2.4.0",b),("v2.3.2",a)):
        if sha is None: continue
        if tag=="v2.3.2" and a==b: continue
        blob=gh(f"repos/{REPO}/git/blobs/{sha}")
        data=base64.b64decode(blob["content"])
        import hashlib
        assert hashlib.sha1(b"blob %d\0"%len(data)+data).hexdigest()==sha
        open(f"{tag}__"+p.replace("/","_"),"wb").write(data)
