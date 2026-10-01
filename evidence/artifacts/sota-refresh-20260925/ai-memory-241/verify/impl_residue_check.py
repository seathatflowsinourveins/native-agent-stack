#!/usr/bin/env python3
"""Counts only: do the implementer's and the verifier's probe nonces or session ids appear anywhere
in the live store (DB opened read-only) or the live wiki files? Which live-dir files changed in the
window, outside db/, wiki/ and hook-spool/ (the live service's own writes)?"""
import json
import os
import sqlite3
import time
import uuid
from pathlib import Path

HOME = Path(os.path.expanduser("~"))
LIVE = HOME / ".local/share/ai-memory"
IW = HOME / ".local/state/native-agent-stack/sota-refresh-20260925/wave2/ai-memory"
toks = [v for _, v, _ in json.loads((IW / "nonces-all.json").read_text())]
sids = [v for _, v, _ in json.loads((IW / "sessions-all.json").read_text())]
toks += list(json.loads((IW / "verify/nonces.json").read_text()).values())
sids += list(json.loads((IW / "verify/sessions.json").read_text()).values())
con = sqlite3.connect(f"file:{LIVE / 'db/memory.sqlite'}?mode=ro", uri=True, timeout=20)
try:
    obs = sum(con.execute("select count(*) from observations where instr(body, ?) > 0 or instr(coalesce(title,''), ?) > 0",
                          (t, t)).fetchone()[0] for t in toks)
    pages = sum(con.execute("select count(*) from pages where instr(coalesce(body,''), ?) > 0 or instr(path, ?) > 0",
                            (t, t)).fetchone()[0] for t in toks)
    sess = sum(con.execute("select count(*) from sessions where id = ?", (uuid.UUID(s).bytes,)).fetchone()[0] for s in sids)
    probe_ws = con.execute("select count(*) from workspaces where name like 'nsr-%'").fetchone()[0]
    probe_pj = con.execute("select count(*) from projects where name like 'ai-memory-acceptance%' "
                           "or name like 'ai-memory-verify%'").fetchone()[0]
finally:
    con.close()
wiki_hits = 0
btoks = [t.encode() for t in toks]
for p in (LIVE / "wiki").rglob("*"):
    if p.is_file() and ".git" not in p.parts:
        data = p.read_bytes()
        wiki_hits += sum(1 for t in btoks if t in data)
cut = time.mktime(time.strptime("2026-09-25 18:20:00", "%Y-%m-%d %H:%M:%S"))  # local EDT = 22:20Z
changed = []
for root, dirs, files in os.walk(LIVE):
    rel = os.path.relpath(root, LIVE)
    top = rel.split(os.sep)[0]
    if top in ("db", "wiki", "hook-spool"):
        continue
    for n in files + dirs:
        p = os.path.join(root, n)
        st = os.lstat(p)
        if max(st.st_mtime, st.st_ctime) > cut:
            changed.append(os.path.relpath(p, LIVE))
print(json.dumps({"nonces_checked": len(toks), "sessions_checked": len(sids), "live_obs_hits": obs,
                  "live_page_hits": pages, "live_session_hits": sess, "live_probe_workspaces": probe_ws,
                  "live_probe_projects": probe_pj, "live_wiki_hits": wiki_hits,
                  "live_dir_changes_outside_db_wiki_spool_since_22:20Z": changed}, indent=1))
