#!/usr/bin/env python3
"""Spot checks of review statements (counts and booleans only)."""
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import tarfile
from pathlib import Path

HOME = Path(os.path.expanduser("~"))
VD = Path(__file__).resolve().parent
ECO = HOME / ".local/share/codex-ecosystem"
REPO = "akitaonrails/ai-memory"
out = {}

serve = (VD / "src/v2.4.1__crates_ai-memory-cli_src_commands_serve.rs").read_text()
out["serve_rs_keepalive"] = {"with_time": bool(re.search(r"with_time\(", serve)),
                             "with_interval": bool(re.search(r"with_interval\(", serve)),
                             "tcp_keepalive_secs_mentions": serve.count("tcp_keepalive_secs"),
                             "set_tcp_keepalive": serve.count("set_tcp_keepalive")}
cfg = (VD.parent / "src/v2.4.1__crates_ai-memory-cli_src_config.rs").read_text()
out["config_rs"] = {"embedding_query_prefix": cfg.count("embedding_query_prefix"),
                    "embedding_document_prefix": cfg.count("embedding_document_prefix"),
                    "tcp_keepalive_secs": cfg.count("tcp_keepalive_secs"),
                    "default_60_near_keepalive": bool(re.search(r"tcp_keepalive_secs[^\n]{0,200}60|60[^\n]{0,80}tcp_keepalive", cfg))}


def tree(root):
    res = {}
    for p in sorted(root.rglob("*")):
        if p.is_file():
            res[str(p.relative_to(root))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return res


h0, h1 = tree(ECO / "tools/ai-memory-2.4.0/hooks"), tree(ECO / "tools/ai-memory-2.4.1/hooks")
out["hooks_bundle_diff"] = {"only_in_2.4.0": sorted(set(h0) - set(h1)), "only_in_2.4.1": sorted(set(h1) - set(h0)),
                            "changed": sorted(k for k in set(h0) & set(h1) if h0[k] != h1[k])}

con = sqlite3.connect(f"file:{HOME / '.local/share/ai-memory/db/memory.sqlite'}?mode=ro", uri=True, timeout=20)
try:
    rows = con.execute("select frontmatter_json from pages where is_latest = 1").fetchall()
finally:
    con.close()
n_exp = 0
for (fm,) in rows:
    try:
        d = json.loads(fm or "{}")
    except ValueError:
        continue
    if isinstance(d, dict) and d.get("expires_at"):
        n_exp += 1
out["live_latest_pages"] = len(rows)
out["live_latest_pages_with_expires_at"] = n_exp

wiki_files = crlf_md = 0
with tarfile.open(HOME / ".local/state/native-agent-stack/sota-refresh-20260925/wave2/ai-memory/pre-2.4.1.tar.gz") as t:
    for m in t.getmembers():
        if m.isfile() and m.name.startswith("wiki/") and "/.git/" not in m.name and not m.name.startswith("wiki/.git/"):
            wiki_files += 1
            if m.name.endswith(".md") and b"\r\n" in t.extractfile(m).read():
                crlf_md += 1
out["backup_wiki_files_excluding_git"] = wiki_files
out["backup_md_with_crlf"] = crlf_md


def blobs(tag):
    sha = json.loads(subprocess.run(["gh", "api", f"repos/{REPO}/commits/{tag}"], capture_output=True, text=True,
                                    check=True).stdout)["commit"]["tree"]["sha"]
    t = json.loads(subprocess.run(["gh", "api", f"repos/{REPO}/git/trees/{sha}?recursive=1"], capture_output=True,
                                  text=True, check=True).stdout)
    return {x["path"]: x["sha"] for x in t["tree"] if x["type"] == "blob"}, t.get("truncated")


b0, tr0 = blobs("v2.4.0")
b1, tr1 = blobs("v2.4.1")
claimed = ["crates/ai-memory-cli/src/cli.rs", "crates/ai-memory-cli/src/lib.rs", "crates/ai-memory-cli/src/main.rs",
           "crates/ai-memory-cli/src/commands/hook.rs", "crates/ai-memory-cli/src/commands/hook_spool.rs",
           "crates/ai-memory-cli/src/commands/hook_capture.rs", "crates/ai-memory-cli/src/commands/hook_drain_process.rs",
           "crates/ai-memory-cli/src/commands/backup.rs", "crates/ai-memory-cli/src/commands/restore.rs",
           "crates/ai-memory-cli/src/commands/status.rs", "crates/ai-memory-cli/src/marker.rs",
           "crates/ai-memory-cli/src/http_client.rs", "crates/ai-memory-store/src/error.rs",
           "crates/ai-memory-wiki/src/backup.rs", "crates/ai-memory-llm/src/local.rs", "crates/ai-memory-llm/src/lib.rs"]
out["trees_truncated"] = [tr0, tr1]
out["claimed_identical"] = {p: (p in b0 and p in b1 and b0[p] == b1[p])
                            for p in claimed}
out["blob_diff_counts"] = {"changed": sum(1 for p in set(b0) & set(b1) if b0[p] != b1[p]),
                           "added": len(set(b1) - set(b0)), "removed": len(set(b0) - set(b1))}
print(json.dumps(out, indent=1))
