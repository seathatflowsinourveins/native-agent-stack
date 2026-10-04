#!/usr/bin/env python3
"""Independent verifier: read-only production store check.

Opens the live ai-memory DB only with mode=ro, recomputes the implementer's fingerprint
definition (page id -> sha256(workspace_id|project_id|path|body_sha256), sorted observation
ids) and compares it with the implementer's before/after snapshots. Scans the live DB and
wiki for every probe token and probe session the implementer (and this verifier) issued.
Tokens and session ids are loaded from private files and never printed.
Usage: prod_check.py LABEL
"""
import hashlib, json, os, sqlite3, sys, time, uuid
from pathlib import Path

HOME = Path.home()
LIVE = HOME / ".local/share/ai-memory"
DB = LIVE / "db/memory.sqlite"
W = HOME / ".local/state/native-agent-stack/sota-refresh-20260925/ai-memory"
VW = W / "verify"
OUT = Path(__file__).resolve().parent


def iso(t=None):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t if t is not None else time.time()))


def fingerprint(con):
    ver, rows = con.execute("select max(version), count(*) from refinery_schema_history").fetchone()
    quick = con.execute("pragma quick_check").fetchone()[0]
    pages = {}
    for pid, ws, pj, path, bsha in con.execute(
            "select id, workspace_id, project_id, path, body_sha256 from pages"):
        pages[bytes(pid).hex()] = hashlib.sha256(
            b"|".join([bytes(ws), bytes(pj), path.encode(), bytes(bsha or b"")])).hexdigest()
    obs = set(bytes(r[0]).hex() for r in con.execute("select id from observations"))
    return ver, rows, quick, pages, obs


def compare(name, snap, ver, rows, quick, pages, obs):
    changed = [k for k, v in snap["pages"].items() if pages.get(k) != v]
    missing = len(set(snap["observation_ids"]) - obs)
    return (f"{name}: V{snap['schema_max']} -> V{ver} ({rows} rows) quick_check={quick} | pages "
            f"before={len(snap['pages'])} missing_or_changed={len(changed)} now={len(pages)} | "
            f"observations before={len(snap['observation_ids'])} missing={missing} now={len(obs)}")


def load_list(path):
    return [v for _, v, _ in json.loads(path.read_text())] if path.exists() else []


label = sys.argv[1]
res = {"label": label, "at": iso()}
con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=15)
try:
    ver, rows, quick, pages, obs = fingerprint(con)
    res["live_now"] = f"schema V{ver} ({rows} rows) quick_check={quick} pages={len(pages)} observations={len(obs)}"
    for snapname in ("fp-live-before.json", "fp-live-after.json"):
        snap = json.loads((W / snapname).read_text())
        res[snapname] = compare(snapname, snap, ver, rows, quick, pages, obs)
    res["probe_scope_rows"] = {
        "workspaces_nsr_probe": con.execute("select count(*) from workspaces where name = 'nsr-probe'").fetchone()[0],
        "projects_ai_memory_acceptance": con.execute(
            "select count(*) from projects where name like 'ai-memory-acceptance%'").fetchone()[0]}
    toks = load_list(W / "nonces-all.json") + load_list(VW / "nonces-all.json")
    sids = load_list(W / "sessions-all.json") + load_list(VW / "sessions-all.json")
    res["tokens_checked"] = {"implementer": len(load_list(W / "nonces-all.json")),
                             "verifier": len(load_list(VW / "nonces-all.json"))}
    res["sessions_checked"] = {"implementer": len(load_list(W / "sessions-all.json")),
                               "verifier": len(load_list(VW / "sessions-all.json"))}
    oh = ph = 0
    for t in toks:
        oh += con.execute("select count(*) from observations where instr(body, ?) > 0 "
                          "or instr(coalesce(title, ''), ?) > 0", (t, t)).fetchone()[0]
        ph += con.execute("select count(*) from pages where instr(coalesce(body, ''), ?) > 0 "
                          "or instr(path, ?) > 0", (t, t)).fetchone()[0]
    sh = sum(con.execute("select count(*) from sessions where id = ?", (uuid.UUID(s).bytes,)).fetchone()[0]
             for s in sids)
    res["live_db_token_hits"] = {"observations": oh, "pages": ph, "probe_sessions": sh}
finally:
    con.close()
wiki_hits = 0
btoks = [t.encode() for t in toks]
for p in (LIVE / "wiki").rglob("*"):
    if p.is_file() and ".git" not in p.parts:
        try:
            data = p.read_bytes()
        except OSError:
            continue
        wiki_hits += sum(1 for t in btoks if t in data)
res["live_wiki_token_hits"] = wiki_hits
res["live_pre_migration_receipt_present"] = (LIVE / "pre-migration-backup.json").exists()
res["home_backup_archives"] = len(list(HOME.glob("ai-memory-backup-*")))
res["live_backups_dir_entries"] = len(list((LIVE / "backups").iterdir())) if (LIVE / "backups").is_dir() else "absent"
out = json.dumps(res, indent=1)
(OUT / f"prod-check-{label}.json").write_text(out + "\n")
print(out)
