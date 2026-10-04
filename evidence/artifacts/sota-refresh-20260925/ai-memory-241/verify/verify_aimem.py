#!/usr/bin/env python3
"""Independent verifier for the ai-memory 2.4.1 wave-2 rehearsal (2026-09-25).

Written separately from the implementer's aimem2_accept.py (no shared code). Read-only toward
production: the live DB is opened with mode=ro, production files are hashed and counted in memory,
and every ai-memory process started here gets a scratch --data-dir under VW (0700), a scratch
HOME/TMPDIR, AI_MEMORY_SERVER_URL pointing at the scratch server (or a dead port), backfill off,
and a 127.0.0.1 bind on a free port (or a private network namespace).

Subcommands:
  prod LABEL            production snapshot (services, bin symlinks, hook files, live DB digests)
  prod-compare A B      compare two snapshots, plus backup-rows-still-in-live and nonce scan
  integrity             upstream digests, fresh download, installed prefix == tarball
  upstream              tag/commit, CI check runs, compare facts, V67 SQL, lockfile crate sets
  arm-base              2.4.0 mini-baseline on a fresh copy (tools list, scope, known page)
  arm-cand              2.4.1 candidate arm on a fresh copy + negative controls + downgrade
  fdprobe ARM           #792 probe in a private user+net namespace (ARM=base|cand)
  fdprobe-inner ARM     (inside the namespace)
  hooks                 install-hooks 2.4.0 then 2.4.1 on scratch files, inside a private netns
  procs                 scratch processes still alive (argv mentions VW)
"""
import hashlib
import json
import os
import re
import secrets
import signal
import socket
import sqlite3
import string
import subprocess
import sys
import tarfile
import time
import tomllib
import urllib.error
import urllib.request
import uuid
from pathlib import Path

os.umask(0o077)
HOME = Path(os.path.expanduser("~"))
ECO = HOME / ".local/share/codex-ecosystem"
LIVE = HOME / ".local/share/ai-memory"
LIVE_DB = LIVE / "db/memory.sqlite"
V240 = ECO / "tools/ai-memory-2.4.0/ai-memory"
V241P = ECO / "tools/ai-memory-2.4.1"
V241 = V241P / "ai-memory"
BIN = ECO / "bin/ai-memory"
LIVE_URL = "http://127.0.0.1:49474"
DEAD = "http://127.0.0.1:9"
IW = HOME / ".local/state/native-agent-stack/sota-refresh-20260925/wave2/ai-memory"
VW = IW / "verify"
VD = Path(__file__).resolve().parent
RES = VD / "results"
BACKUP = IW / "pre-2.4.1.tar.gz"
BACKUP_SHA = "84389042aa2a85741a8f98397cb96af8d358a878c5974c6f25110556e4144783"
REPO = "akitaonrails/ai-memory"
ASSET = "ai-memory-linux-x86_64.tar.gz"
ASSET_URL = f"https://github.com/{REPO}/releases/download/v2.4.1/{ASSET}"
EXPECTED = "15cafdc48eabc0305c164ccc8e884b260275f5a88b4f26e8456c2e42156375e4"
WS, PROJ, PWS = "local", "native-agent-stack", "nsr-verify"
SCHEMA_MSG = "memory database schema is newer than this ai-memory build"
DIRECT = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def san(obj):
    if isinstance(obj, str):
        return obj.replace(str(HOME), "~")
    if isinstance(obj, dict):
        return {san(k): san(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [san(v) for v in obj]
    return obj


def emit(name, data):
    RES.mkdir(exist_ok=True)
    data = san(data)
    (RES / f"{name}.json").write_text(json.dumps(data, indent=1) + "\n")
    print(json.dumps(data))


def sha_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha(b):
    return hashlib.sha256(b if isinstance(b, bytes) else str(b).encode()).hexdigest()


def plog(name, text):
    (VW / "logs").mkdir(mode=0o700, parents=True, exist_ok=True)
    with open(VW / "logs" / name, "a") as fh:
        fh.write(f"[{now()}] {text}\n")


def private_dirs():
    for d in (VW, VW / "home", VW / "tmp", VW / "logs", VW / "archives"):
        d.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(d, 0o700)


def senv(url=DEAD, tag="misc"):
    arch = VW / "archives" / tag
    arch.mkdir(mode=0o700, parents=True, exist_ok=True)
    return {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "HOME": str(VW / "home"),
            "TMPDIR": str(VW / "tmp"), "AI_MEMORY_SERVER_URL": url,
            "AI_MEMORY_BACKFILL_ON_START": "false", "AI_MEMORY_BACKUP_DIR": str(arch)}


def ro(db):
    return sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=20)


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def http(method, url, timeout=10):
    req = urllib.request.Request(url, method=method)
    try:
        with DIRECT.open(req, timeout=timeout) as r:
            return r.status, {k.lower(): v for k, v in r.headers.items()}, r.read()
    except urllib.error.HTTPError as e:
        return e.code, {k.lower(): v for k, v in e.headers.items()}, e.read()


# ------------------------------------------------------------------ DB digests (own scheme)
def db_digests(db, strong=True):
    """Per-row digests. pages: id -> sha(ws|proj|path|sha(body)|title[|is_latest|frontmatter]),
    observations: id -> sha(session|title|body|created_at)."""
    con = ro(db)
    try:
        ver, nrows = con.execute("select max(version), count(*) from refinery_schema_history").fetchone()
        names = [r[0] for r in con.execute("select name from refinery_schema_history order by version")]
        qc = con.execute("pragma quick_check").fetchone()[0]
        ocols = [r[1] for r in con.execute("pragma table_info(observations)")]
        ts_col = "created_at" if "created_at" in ocols else None
        pages, pages_meta = {}, {}
        for pid, w, p, path, body, title, latest, fm in con.execute(
                "select id, workspace_id, project_id, path, body, title, is_latest, frontmatter_json from pages"):
            bb = body if isinstance(body, bytes) else (body or "").encode()
            core = b"\x1f".join([bytes(w), bytes(p), path.encode(), hashlib.sha256(bb).digest(),
                                 (title or "").encode()])
            pages[bytes(pid).hex()] = sha(core)
            pages_meta[bytes(pid).hex()] = sha(f"{latest}\x1f{fm or ''}")
        obs = {}
        q = "select id, session_id, title, body" + (f", {ts_col}" if ts_col else "") + " from observations"
        for row in con.execute(q):
            oid, sid, title, body = row[:4]
            ts = row[4] if ts_col else ""
            obs[bytes(oid).hex()] = sha(b"\x1f".join([bytes(sid or b""), (title or "").encode(),
                                                     (body or "").encode(), str(ts).encode()]))
    finally:
        con.close()
    return {"schema_max": ver, "schema_rows": nrows, "last_migration": names[-1] if names else None,
            "quick_check": qc, "pages": pages, "pages_meta": pages_meta, "observations": obs}


def superset(before, after):
    """Every row of `before` is present in `after` with the same content digest."""
    pg_missing = [k for k in before["pages"] if k not in after["pages"]]
    pg_changed = [k for k, v in before["pages"].items() if k in after["pages"] and after["pages"][k] != v]
    meta_changed = [k for k, v in before["pages_meta"].items()
                    if k in after["pages_meta"] and after["pages_meta"][k] != v]
    ob_missing = [k for k in before["observations"] if k not in after["observations"]]
    ob_changed = [k for k, v in before["observations"].items()
                  if k in after["observations"] and after["observations"][k] != v]
    return {"pages_before": len(before["pages"]), "pages_after": len(after["pages"]),
            "pages_missing": len(pg_missing), "pages_content_changed": len(pg_changed),
            "pages_latest_or_frontmatter_changed": len(meta_changed),
            "obs_before": len(before["observations"]), "obs_after": len(after["observations"]),
            "obs_missing": len(ob_missing), "obs_changed": len(ob_changed),
            "rows_intact": not (pg_missing or pg_changed or ob_missing or ob_changed)}


def brief(d):
    return {"schema_max": d["schema_max"], "schema_rows": d["schema_rows"], "last_migration": d["last_migration"],
            "quick_check": d["quick_check"], "pages": len(d["pages"]), "observations": len(d["observations"])}


# ------------------------------------------------------------------ production snapshot
def hookfile(path):
    raw = path.read_bytes()
    obj = json.loads(raw)
    hooks = obj.get("hooks", obj) if isinstance(obj, dict) else obj
    return {"sha256": sha(raw), "hooks_subtree_sha256": sha(json.dumps(hooks, sort_keys=True).encode()),
            "mtime": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(path.stat().st_mtime)),
            "cmds_2.4.0": raw.count(b"tools/ai-memory-2.4.0/ai-memory"),
            "cmds_2.4.1": raw.count(b"tools/ai-memory-2.4.1/ai-memory"),
            "cmds_2.3.2": raw.count(b"tools/ai-memory-2.3.2/ai-memory")}


def cmd_prod(label):
    private_dirs()
    snap = {"label": label, "at": now()}
    listing = subprocess.run(["systemctl", "--user", "list-units", "--type=service", "--state=active",
                              "--no-legend", "--plain"], capture_output=True, text=True).stdout
    units = {}
    for line in listing.splitlines():
        u = line.split()[0]
        out = subprocess.run(["systemctl", "--user", "show", u, "-p", "MainPID", "-p", "ExecMainStartTimestamp",
                              "-p", "NRestarts", "-p", "ActiveState", "-p", "InvocationID"],
                             capture_output=True, text=True).stdout
        d = dict(x.split("=", 1) for x in out.strip().splitlines() if "=" in x)
        d["InvocationID"] = sha(d.get("InvocationID", ""))[:12]
        units[u] = d
    snap["active_units"] = units
    unit = HOME / ".config/systemd/user/nativestack-memory.service"
    snap["memory_unit_sha256"] = sha_file(unit)
    snap["memory_dropins"] = subprocess.run(["systemctl", "--user", "show", "nativestack-memory.service", "-p",
                                             "DropInPaths", "--value"], capture_output=True, text=True).stdout.strip()
    links = {p.name: os.readlink(p) for p in sorted((ECO / "bin").iterdir()) if p.is_symlink()}
    snap["bin_symlinks"] = {"count": len(links), "digest": sha(json.dumps(links, sort_keys=True).encode())[:16],
                            "ai-memory": links.get("ai-memory"),
                            "latest_ctime": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(max(
                                (ECO / "bin" / n).lstat().st_ctime for n in links)))}
    snap["bin_ai_memory_resolves_to"] = os.path.realpath(BIN)
    snap["v240_sha256"] = sha_file(V240)
    snap["v241_sha256"] = sha_file(V241) if V241.exists() else None
    snap["tool_prefixes"] = sorted(p.name for p in (ECO / "tools").glob("ai-memory-*"))
    snap["claude_settings"] = hookfile(HOME / ".claude/settings.json")
    snap["codex_hooks"] = hookfile(HOME / ".codex/hooks.json")
    d = db_digests(LIVE_DB)
    (VW / f"live-digests-{label}.json").write_text(json.dumps(d))
    snap["live_db"] = brief(d)
    snap["live_pre_migration_receipt"] = (LIVE / "pre-migration-backup.json").exists()
    snap["home_backup_archives"] = len(list(HOME.glob("ai-memory-backup-*")))
    snap["home_cache_ai_memory"] = (HOME / ".cache/ai-memory").exists()
    hz = http("GET", LIVE_URL + "/healthz")
    gm = http("GET", LIVE_URL + "/mcp")
    snap["live_endpoints"] = {"healthz": hz[0], "healthz_body": hz[2].decode(errors="replace")[:40],
                              "get_mcp": gm[0], "allow": gm[1].get("allow")}
    snap["scratch_procs"] = scratch_procs()
    emit(f"prod-{label}", snap)


def cmd_prod_compare(a, b):
    sa = json.loads((RES / f"prod-{a}.json").read_text())
    sb = json.loads((RES / f"prod-{b}.json").read_text())
    da = json.loads((VW / f"live-digests-{a}.json").read_text())
    db_ = json.loads((VW / f"live-digests-{b}.json").read_text())
    res = {"at": now(), "a": a, "b": b}
    res["units_same"] = {u: sa["active_units"][u] == sb["active_units"].get(u) for u in sa["active_units"]}
    res["units_added"] = sorted(set(sb["active_units"]) - set(sa["active_units"]))
    res["live_rows_superset"] = superset(da, db_)
    res["live_schema_b"] = brief(db_)
    for k in ("memory_unit_sha256", "memory_dropins", "bin_symlinks", "bin_ai_memory_resolves_to", "v240_sha256",
              "v241_sha256", "tool_prefixes", "claude_settings", "codex_hooks", "live_endpoints"):
        res[f"same_{k}"] = sa[k] == sb[k]
    res["hooks_subtrees_same"] = (sa["claude_settings"]["hooks_subtree_sha256"] == sb["claude_settings"]["hooks_subtree_sha256"]
                                  and sa["codex_hooks"]["hooks_subtree_sha256"] == sb["codex_hooks"]["hooks_subtree_sha256"])
    # my own nonces and sessions must never appear in the live store
    toks = json.loads((VW / "nonces.json").read_text()) if (VW / "nonces.json").exists() else {}
    sids = json.loads((VW / "sessions.json").read_text()) if (VW / "sessions.json").exists() else {}
    con = ro(LIVE_DB)
    try:
        hits = 0
        for t in toks.values():
            hits += con.execute("select count(*) from observations where instr(body, ?) > 0 or instr(coalesce(title,''), ?) > 0",
                                (t, t)).fetchone()[0]
            hits += con.execute("select count(*) from pages where instr(coalesce(body,''), ?) > 0 or instr(path, ?) > 0",
                                (t, t)).fetchone()[0]
        shits = sum(con.execute("select count(*) from sessions where id = ?", (uuid.UUID(s).bytes,)).fetchone()[0]
                    for s in sids.values())
        ws = con.execute("select count(*) from workspaces where name in ('nsr-verify','nsr-probe')").fetchone()[0]
    finally:
        con.close()
    res["live_nonce_hits"] = hits
    res["live_session_hits"] = shits
    res["live_probe_workspaces"] = ws
    res["nonces_checked"], res["sessions_checked"] = len(toks), len(sids)
    res["scratch_procs"] = scratch_procs()
    emit(f"prod-compare-{a}-{b}", res)


def cmd_backup_vs_live(label):
    """Rows of the online backup (taken 22:43Z through the live service) must still be in live, unchanged."""
    private_dirs()
    tmp = VW / "backup-db-only"
    if not (tmp / "db/memory.sqlite").exists():
        tmp.mkdir(mode=0o700, exist_ok=True)
        with tarfile.open(BACKUP, "r:gz") as t:
            t.extractall(tmp, members=[m for m in t.getmembers() if m.name == "db/memory.sqlite"], filter="data")
    bd = db_digests(tmp / "db/memory.sqlite")
    ld = json.loads((VW / f"live-digests-{label}.json").read_text())
    res = {"at": now(), "backup_sha256_ok": sha_file(BACKUP) == BACKUP_SHA, "backup_db": brief(bd),
           "live_db": brief(ld), "backup_rows_in_live": superset(bd, ld)}
    emit(f"backup-vs-live-{label}", res)


# ------------------------------------------------------------------ processes
def scratch_procs():
    key = str(VW).encode()
    out = []
    for d in os.listdir("/proc"):
        if not d.isdigit() or int(d) == os.getpid():
            continue
        try:
            raw = open(f"/proc/{d}/cmdline", "rb").read()
            state = open(f"/proc/{d}/stat").read().rsplit(")", 1)[1].split()[0]
        except OSError:
            continue
        if key in raw and state != "Z" and b"verify_aimem.py" not in raw:
            argv = [a.decode(errors="replace") for a in raw.split(b"\0") if a]
            out.append({"pid": int(d), "argv0": argv[0].rsplit("/", 1)[-1],
                        "sub": next((a for a in argv if a in ("serve", "hook", "hook-drain", "backfill")), "?")})
    return out


def kill_mine():
    res = []
    for p in scratch_procs():
        try:
            os.kill(p["pid"], signal.SIGTERM)
        except ProcessLookupError:
            pass
        for _ in range(50):
            if not Path(f"/proc/{p['pid']}").exists():
                break
            time.sleep(0.1)
        res.append({"pid": p["pid"], "gone": not Path(f"/proc/{p['pid']}").exists()})
    return res


# ------------------------------------------------------------------ scratch copies and servers
def fresh_copy(name):
    dd = VW / name
    if dd.exists():
        raise SystemExit(f"{dd} exists; refusing to reuse")
    if sha_file(BACKUP) != BACKUP_SHA:
        raise SystemExit("backup sha256 mismatch")
    dd.mkdir(mode=0o700)
    with tarfile.open(BACKUP, "r:gz") as t:
        t.extractall(dd, filter="data")
    subprocess.run(["cp", "-a", str(LIVE / "models"), str(dd / "models")], check=True)
    subprocess.run(["cp", "-a", str(LIVE / "capture-mode"), str(dd / "capture-mode")], check=True)
    with open(dd / "config.toml", "rb") as fh:
        cfg = tomllib.load(fh)
    found = []

    def walk(o, pre):
        for k, v in o.items():
            if isinstance(v, dict):
                walk(v, pre + k + ".")
            elif k == "server_url":
                found.append(pre + k)
    walk(cfg, "")
    bos = cfg.get("backfill_on_start")
    safe = not found and bos is False
    del cfg
    if not safe:
        raise SystemExit("copied config could route scratch traffic to the live server")
    return dd, {"server_url_keys": found, "backfill_on_start": bos, "safe": safe,
                "capture_mode": (dd / "capture-mode").read_text().strip()}


def serve(binary, dd, tag, port=None):
    port = port or free_port()
    url = f"http://127.0.0.1:{port}"
    log = open(VW / "logs" / f"serve-{tag}.log", "ab")
    proc = subprocess.Popen([str(binary), "--data-dir", str(dd), "serve", "--transport", "http", "--enable-web",
                             "--bind", f"127.0.0.1:{port}", "--workspace", WS, "--project", PROJ],
                            cwd=str(VW / "tmp"), env=senv(url, tag), stdin=subprocess.DEVNULL, stdout=log,
                            stderr=subprocess.STDOUT, start_new_session=True)
    t0 = time.time()
    while time.time() - t0 < 120:
        if proc.poll() is not None:
            return proc, url, {"ready": False, "rc": proc.returncode}
        try:
            if http("GET", url + "/healthz", timeout=2)[0] == 200:
                return proc, url, {"ready": True, "seconds": round(time.time() - t0, 1)}
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(0.3)
    return proc, url, {"ready": False, "timeout": True}


def stop(proc, url):
    if proc.poll() is None:
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=10)
    try:
        http("GET", url + "/healthz", timeout=2)
        closed = False
    except (urllib.error.URLError, OSError):
        closed = True
    return {"rc": proc.returncode, "pid_gone": not Path(f"/proc/{proc.pid}").exists(), "port_closed": closed}


class RpcError(RuntimeError):
    pass


_N = [0]


def rpc(url, method, params=None):
    _N[0] += 1
    body = {"jsonrpc": "2.0", "id": _N[0], "method": method}
    if params is not None:
        body["params"] = params
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json",
                                          "Accept": "application/json, text/event-stream"})
    with DIRECT.open(req, timeout=60) as r:
        ctype = r.headers.get("Content-Type", "")
        text = r.read().decode()
    if "text/event-stream" in ctype:
        data = [ln[5:].strip() for ln in text.splitlines() if ln.startswith("data:") and ln[5:].strip()]
        text = data[-1]
    msg = json.loads(text)
    if "error" in msg:
        plog("rpc-errors.log", f"{method}: {str(msg['error'])[:300]}")
        raise RpcError(method)
    return msg["result"]


def tool(url, name, args):
    r = rpc(url, "tools/call", {"name": name, "arguments": args})
    text = "".join(c.get("text", "") for c in r.get("content", []) if c.get("type") == "text")
    if r.get("isError"):
        plog("rpc-errors.log", f"{name} isError: {text[:300]}")
        raise RpcError(name)
    try:
        return json.loads(text)
    except ValueError:
        return {"_text": text}


def nonce(label):
    path = VW / "nonces.json"
    d = json.loads(path.read_text()) if path.exists() else {}
    t = "nsv" + "".join(secrets.choice(string.ascii_lowercase) for _ in range(16))
    d[label] = t
    path.write_text(json.dumps(d))
    return t


def remember_session(label, sid):
    path = VW / "sessions.json"
    d = json.loads(path.read_text()) if path.exists() else {}
    d[label] = sid
    path.write_text(json.dumps(d))


def cli_status(binary, dd, url):
    r = subprocess.run([str(binary), "--data-dir", str(dd), "status", "--json"], env=senv(url),
                       cwd=str(VW / "tmp"), capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        return {"rc": r.returncode}
    st = json.loads(r.stdout)
    d = st.get("derived") or {}
    e = (st.get("providers") or {}).get("embedding") or {}
    return {"rc": 0, "version": st.get("version"), "capture_mode": st.get("capture_mode"),
            "pages_fts_eq": d.get("pages_fts_rows") == d.get("pages_rows"),
            "obs_fts_eq": d.get("observations_fts_rows") == d.get("observations_rows"),
            "pages_rows": d.get("pages_rows"), "observations_rows": d.get("observations_rows"),
            "missing_embeddings": d.get("latest_pages_missing_embeddings"),
            "embedding": [e.get("status"), e.get("provider"), e.get("model"), e.get("dim")],
            "top_keys": sorted(st)}


def known_page_path(db):
    con = ro(db)
    try:
        row = con.execute("""select p.path, p.body from pages p join projects pr on pr.id=p.project_id
                             join workspaces w on w.id=p.workspace_id
                             where p.is_latest=1 and w.name=? and pr.name=? and p.expires_at is null
                             order by p.created_at, p.path limit 1""", (WS, PROJ)).fetchone()
    finally:
        con.close()
    body = row[1] if isinstance(row[1], bytes) else (row[1] or "").encode()
    return row[0], sha(body)


def info(url):
    init = rpc(url, "initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                                   "clientInfo": {"name": "nsr-verifier", "version": "1"}})
    tools = sorted(t["name"] for t in rpc(url, "tools/list", {}).get("tools", []))
    st = tool(url, "memory_status", {"workspace": WS, "project": PROJ})
    scope = st.get("scope") if isinstance(st.get("scope"), dict) else {}
    return {"server": init.get("serverInfo", {}).get("name"), "version": init.get("serverInfo", {}).get("version"),
            "protocol": init.get("protocolVersion"), "tools": tools, "n_tools": len(tools),
            "resolved_by": scope.get("resolved_by")}


def marker_dir(name, project=None):
    d = VD / "probe" / name
    d.mkdir(parents=True, exist_ok=True)
    m = d / ".ai-memory.toml"
    if project:
        m.write_text(f'workspace = "{PWS}"\nproject = "{project}"\n')
    elif m.exists():
        m.unlink()
    return d


def spool_files(dd):
    root = dd / "hook-spool"
    return [p for p in root.rglob("*") if p.is_file() and not p.name.startswith(".")] if root.exists() else []


def check_capture(binary, dd, url, cwd):
    payload = {"session_id": str(uuid.uuid4()), "transcript_path": str(cwd / "t.jsonl"), "cwd": str(cwd),
               "hook_event_name": "PostToolUse", "tool_name": "Bash", "tool_input": {"command": "true"},
               "tool_response": {"stdout": "", "stderr": "", "interrupted": False}}
    n0 = len(spool_files(dd))
    r = subprocess.run([str(binary), "--data-dir", str(dd), "hook", "--event", "post-tool-use", "--agent",
                        "claude-code", "--server-url", url, "--check-capture"], input=json.dumps(payload),
                       text=True, cwd=str(cwd), env=senv(url), capture_output=True, timeout=60)
    try:
        d = json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        d = {}
    return {"rc": r.returncode, "capture_mode": d.get("capture_mode"), "marker_present": d.get("marker_present"),
            "admits_capture": d.get("admits_capture"), "spool_added": len(spool_files(dd)) - n0}


def hook_session(binary, dd, url, cwd, tok, label):
    sid = str(uuid.uuid4())
    remember_session(label, sid)
    (cwd / "t.jsonl").write_text("")
    rcs = []
    for ev, extra in (("session-start", {"hook_event_name": "SessionStart", "source": "startup"}),
                      ("post-tool-use", {"hook_event_name": "PostToolUse", "tool_name": "Bash",
                                         "tool_input": {"command": f"printf {tok}"},
                                         "tool_response": {"stdout": tok, "stderr": "", "interrupted": False}}),
                      ("session-end", {"hook_event_name": "SessionEnd", "reason": "other"})):
        payload = {"session_id": sid, "transcript_path": str(cwd / "t.jsonl"), "cwd": str(cwd), **extra}
        r = subprocess.run([str(binary), "--data-dir", str(dd), "hook", "--event", ev, "--agent", "claude-code",
                            "--server-url", url], input=json.dumps(payload), text=True, cwd=str(cwd),
                           env=senv(url), capture_output=True, timeout=60)
        rcs.append(r.returncode)
    return sid, rcs


def find_obs(url, project, sid, tok, timeout_s=45):
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        try:
            r = tool(url, "memory_read_session_observations",
                     {"workspace": PWS, "project": project, "session_id": sid, "query": tok, "limit": 20})
            rows = r.get("observations") or []
            if any(tok in json.dumps(x) for x in rows):
                return {"found": True, "seconds": round(time.time() - t0, 1), "rows": len(rows)}
        except RpcError:
            pass
        time.sleep(1)
    return {"found": False, "seconds": round(time.time() - t0, 1)}


def db_counts(db, tok, sid=None):
    con = ro(db)
    try:
        o = con.execute("select count(*) from observations where instr(body, ?) > 0 or instr(coalesce(title,''), ?) > 0",
                        (tok, tok)).fetchone()[0]
        s = con.execute("select count(*) from sessions where id = ?", (uuid.UUID(sid).bytes,)).fetchone()[0] if sid else None
    finally:
        con.close()
    return {"obs_rows": o, "session_rows": s}


def cmd_arm_base():
    """Independent A arm (2.4.0) on a fresh V66 copy: tool list, scope, known page, status."""
    private_dirs()
    dd, safety = fresh_copy("base")
    res = {"at": now(), "copy_safety": safety}
    res["before"] = brief(db_digests(dd / "db/memory.sqlite"))
    kp, kp_db_sha = known_page_path(dd / "db/memory.sqlite")
    (VW / "known-page.json").write_text(json.dumps({"path": kp, "db_body_sha": kp_db_sha}))
    proc, url, ready = serve(V240, dd, "base")
    res["ready"] = ready
    try:
        res["info"] = info(url + "/mcp")
        (VW / "tools-2.4.0.json").write_text(json.dumps(res["info"]["tools"]))
        page = tool(url + "/mcp", "memory_read_page", {"workspace": WS, "project": PROJ, "path": kp})
        res["known_page_mcp_sha256"] = sha((page.get("body") or "").encode())
        res["known_page_db_sha256"] = kp_db_sha
        res["status"] = cli_status(V240, dd, url)
    finally:
        res["stop"] = stop(proc, url)
        res["leftovers"] = kill_mine()
    res["info"]["tools"] = f"<{len(res['info']['tools'])} names>"
    emit("arm-base", res)


def cmd_arm_cand():
    private_dirs()
    dd, safety = fresh_copy("cand")
    db = dd / "db/memory.sqlite"
    res = {"at": now(), "copy_safety": safety}
    before = db_digests(db)
    res["before"] = brief(before)
    kp, kp_db_sha = known_page_path(db)
    base_kp = json.loads((VW / "known-page.json").read_text())
    res["known_page_same_path_as_base"] = kp == base_kp["path"]
    proc, url, ready = serve(V241, dd, "cand")
    res["ready"] = ready
    mcp = url + "/mcp"
    try:
        hz = http("GET", url + "/healthz")
        gm = http("GET", mcp)
        res["healthz"] = [hz[0], hz[2].decode(errors="replace")]
        res["get_mcp"] = [gm[0], gm[1].get("allow")]
        inf = info(mcp)
        base_tools = json.loads((VW / "tools-2.4.0.json").read_text())
        impl_tools = json.loads((VD.parent / "results/step3-baseline.json").read_text())["info"]["tool_names"]
        res["info"] = {k: v for k, v in inf.items() if k != "tools"}
        res["tools_equal_my_2.4.0_list"] = inf["tools"] == base_tools
        res["tools_equal_implementer_baseline_list"] = inf["tools"] == impl_tools
        res["status_start"] = cli_status(V241, dd, url)
        page = tool(mcp, "memory_read_page", {"workspace": WS, "project": PROJ, "path": kp})
        res["known_page"] = {"mcp_sha256": sha((page.get("body") or "").encode()), "db_sha256": kp_db_sha,
                             "base_db_sha256": base_kp["db_body_sha"]}
        # round trip in a probe scope
        tok = nonce("cand-mcp")
        scope = {"workspace": PWS, "project": "ai-memory-verify-mcp"}
        path = f"notes/verify-{tok}.md"
        tool(mcp, "memory_write_page", {**scope, "path": path, "title": "verifier probe",
                                        "body": f"Disposable verifier probe {tok}."})
        hits = tool(mcp, "memory_query", {**scope, "query": tok}).get("hits", [])
        got = tool(mcp, "memory_read_page", {**scope, "path": path}).get("body") or ""
        tool(mcp, "memory_delete_page", {**scope, "path": path})
        after = tool(mcp, "memory_query", {**scope, "query": tok}).get("hits", [])
        try:
            tool(mcp, "memory_read_page", {**scope, "path": path})
            gone = False
        except RpcError:
            gone = True
        res["roundtrip"] = {"hits": [h.get("path") == path for h in hits], "read_has_token": tok in got,
                            "hits_after_delete": len(after), "read_after_delete_fails": gone}
        # negative control: a query for a token that was never written returns nothing
        res["neg_query_unwritten_token_hits"] = len(tool(mcp, "memory_query", {**scope, "query": nonce("cand-neg-q")}).get("hits", []))
        mdir = marker_dir("cand-marker", "ai-memory-verify-hook")
        xdir = marker_dir("cand-cross", "ai-memory-verify-cross")
        ndir = marker_dir("cand-nomarker")
        res["check_capture_marker"] = check_capture(V241, dd, url, mdir)
        res["check_capture_nomarker"] = check_capture(V241, dd, url, ndir)
        t1 = nonce("cand-hook")
        sid1, rc1 = hook_session(V241, dd, url, mdir, t1, "cand-hook")
        res["hook_2.4.1"] = {"rcs": rc1, **find_obs(mcp, "ai-memory-verify-hook", sid1, t1)}
        t2 = nonce("cand-cross")
        sid2, rc2 = hook_session(V240, dd, url, xdir, t2, "cand-cross")
        res["hook_2.4.0_client_into_2.4.1"] = {"rcs": rc2, **find_obs(mcp, "ai-memory-verify-cross", sid2, t2)}
        # negative control: same session, a token that was never sent is not found
        res["neg_obs_unsent_token"] = find_obs(mcp, "ai-memory-verify-hook", sid1, nonce("cand-neg-obs"), timeout_s=4)
        t3 = nonce("cand-nomarker")
        sid3, rc3 = hook_session(V241, dd, url, ndir, t3, "cand-nomarker")
        res["nomarker"] = {"rcs": rc3, "spool_files": len(spool_files(dd)),
                           "spool_files_with_token": sum(1 for p in spool_files(dd) if t3.encode() in p.read_bytes())}
        # wait for any hook drains of mine to exit
        t0 = time.time()
        while time.time() - t0 < 60 and [p for p in scratch_procs() if p["pid"] != proc.pid]:
            time.sleep(1)
        res["status_after_probes"] = cli_status(V241, dd, url)
        # negative control: info must not pass as 2.4.0
        res["neg_version_is_not_2.4.0"] = inf["version"] != "2.4.0"
    finally:
        res["stop"] = stop(proc, url)
        res["leftovers"] = kill_mine()
    after_d = db_digests(db)
    res["after"] = brief(after_d)
    res["migration_rows"] = superset(before, after_d)
    res["nomarker_db"] = db_counts(db, t3, sid3)
    res["hook_db"] = db_counts(db, t1, sid1)
    res["cross_db"] = db_counts(db, t2, sid2)
    con = ro(db)
    try:
        res["managed_runs_has_native_session_linked_at"] = "native_session_linked_at" in [
            r[1] for r in con.execute("pragma table_info(managed_runs)")]
    finally:
        con.close()
    res["archives_created"] = len(list((VW / "archives").rglob("*.tar.gz"))) + len(list((VW / "home").glob("ai-memory-backup-*")))
    res["pre_migration_receipt"] = (dd / "pre-migration-backup.json").exists()
    # negative controls on the store comparison itself
    doctored = json.loads(json.dumps(after_d))
    doctored["observations"].pop(next(iter(before["observations"])))
    res["neg_superset_detects_missing_observation"] = superset(before, doctored)["rows_intact"] is False
    doctored = json.loads(json.dumps(after_d))
    k = next(iter(before["pages"]))
    doctored["pages"][k] = "0" * 64
    res["neg_superset_detects_changed_page"] = superset(before, doctored)["rows_intact"] is False
    # downgrade: 2.4.0 must refuse the V67 copy and leave it unchanged
    port = free_port()
    log = VW / "logs" / "downgrade.log"
    with open(log, "ab") as fh:
        p = subprocess.Popen([str(V240), "--data-dir", str(dd), "serve", "--transport", "http", "--enable-web",
                              "--bind", f"127.0.0.1:{port}", "--workspace", WS, "--project", PROJ],
                             cwd=str(VW / "tmp"), env=senv(f"http://127.0.0.1:{port}", "downgrade"),
                             stdin=subprocess.DEVNULL, stdout=fh, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            rc = p.wait(timeout=60)
            by_itself = True
        except subprocess.TimeoutExpired:
            p.kill()
            rc = p.wait(timeout=10)
            by_itself = False
    text = log.read_text(errors="replace")
    post = db_digests(db)
    res["downgrade"] = {"exited_by_itself": by_itself, "rc": rc, "schema_msg": SCHEMA_MSG in text,
                        "names_v67": "V67 (managed_run_session_link)" in text, "after": brief(post),
                        "unchanged": superset(after_d, post)["rows_intact"] and len(post["pages"]) == len(after_d["pages"])
                        and len(post["observations"]) == len(after_d["observations"])
                        and post["schema_max"] == 67}
    emit("arm-cand", res)


# ------------------------------------------------------------------ #792 probe
def tcp_rows(port):
    rows = []
    for line in open("/proc/net/tcp").read().splitlines()[1:]:
        f = line.split()
        lp, rp = int(f[1].split(":")[1], 16), int(f[2].split(":")[1], 16)
        if lp != port:
            continue
        tr, when = f[5].split(":")
        rows.append({"rport": rp, "st": f[3], "timer": int(tr, 16), "when_s": int(when, 16) / 100, "inode": f[9]})
    return rows


def sample(pid, port, groups, t0):
    fds = os.listdir(f"/proc/{pid}/fd")
    rows = [r for r in tcp_rows(port) if r["st"] != "0A"]
    out = {"t": round(time.time() - t0, 1), "fds": len(fds)}
    for g, ports in groups.items():
        rr = [r for r in rows if r["rport"] in ports and r["st"] == "01"]
        ka = [r for r in rr if r["timer"] == 2]
        out[g] = {"est": len(rr), "keepalive": len(ka),
                  "ka_when_min_max": [min(r["when_s"] for r in ka), max(r["when_s"] for r in ka)] if ka else None}
    return out


def cmd_fdprobe_inner(arm):
    binary = V240 if arm == "base" else V241
    dd = VW / arm
    subprocess.run(["/usr/sbin/ip", "link", "set", "lo", "up"], check=True)
    port = 18111
    proc, url, ready = serve(binary, dd, f"fd-{arm}", port=port)
    out = {"arm": arm, "uid_in_ns": os.getuid(), "ready": ready}
    kept = []
    try:
        if not ready.get("ready"):
            return out
        time.sleep(1)
        groups = {"vanished_after_response": set(), "vanished_connect_only": set(), "live_idle": set()}
        t0 = time.time()
        out["s0"] = sample(proc.pid, port, groups, t0)

        def conn(send):
            s = socket.create_connection(("127.0.0.1", port), timeout=5)
            if send:
                s.sendall(b"GET /healthz HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n")
                data = b""
                while b'"ok"' not in data:
                    chunk = s.recv(4096)
                    if not chunk:
                        break
                    data += chunk
            return s
        for _ in range(40):
            s = conn(True)
            groups["vanished_after_response"].add(s.getsockname()[1])
            s.setsockopt(socket.IPPROTO_TCP, 19, 1)  # TCP_REPAIR: close without FIN/RST
            s.close()
        for _ in range(20):
            s = conn(False)
            groups["vanished_connect_only"].add(s.getsockname()[1])
            s.setsockopt(socket.IPPROTO_TCP, 19, 1)
            s.close()
        for _ in range(5):
            s = conn(True)
            groups["live_idle"].add(s.getsockname()[1])
            kept.append(s)
        t0 = time.time()
        out["samples"] = []
        for target in (3, 50, 70, 100):
            while time.time() - t0 < target:
                time.sleep(0.25)
            out["samples"].append(sample(proc.pid, port, groups, t0))
        out["healthz_after"] = http("GET", url + "/healthz")[0]
    finally:
        for s in kept:
            s.close()
        out["stop"] = stop(proc, url)
    return out


def cmd_fdprobe(arm):
    r = subprocess.run(["unshare", "--user", "--map-root-user", "--net", "--", sys.executable, str(Path(__file__)),
                        "fdprobe-inner", arm], capture_output=True, text=True, timeout=400)
    try:
        inner = json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        inner = {"error": "no inner output", "stderr_tail": r.stderr[-500:]}
    emit(f"fdprobe-{arm}", {"at": now(), "rc": r.returncode, "inner": inner, "leftovers": scratch_procs()})


# ------------------------------------------------------------------ hooks render
def strings_with(obj, needle):
    if isinstance(obj, dict):
        return [s for v in obj.values() for s in strings_with(v, needle)]
    if isinstance(obj, list):
        return [s for v in obj for s in strings_with(v, needle)]
    return [obj] if isinstance(obj, str) and needle in obj else []


def path_only(a, b, old, new):
    al, bl = a.splitlines(), b.splitlines()
    ch = [(x, y) for x, y in zip(al, bl) if x != y]
    return len(al) == len(bl) and all(x.replace(old, new) == y for x, y in ch), len(ch)


def cmd_hooks_inner():
    hd = VW / "hooks"
    dd, cfg = hd / "dd", hd / "cfg"
    out = {"uid_in_ns": os.getuid()}
    files = {"claude-code": cfg / "claude.json", "codex": cfg / "codex.json"}
    extra = {"claude-code": ["--capture-mode", "allowlist", "--no-capture-prompts"], "codex": ["--capture-mode", "allowlist"]}
    for ver, binary in (("2.4.0", V240), ("2.4.1", V241)):
        for agent, f in files.items():
            r = subprocess.run([str(binary), "--data-dir", str(dd), "install-hooks", "--apply", "--agent", agent,
                                "--config-file", str(f), "--server-url", LIVE_URL, *extra[agent]],
                               env=senv(DEAD, "hooks"), cwd=str(VW / "tmp"), capture_output=True, text=True, timeout=120)
            out[f"{ver}-{agent}-rc"] = r.returncode
            (hd / f"{agent}-{ver}.json").write_bytes(f.read_bytes())
    return out


def cmd_hooks():
    private_dirs()
    hd = VW / "hooks"
    if hd.exists():
        raise SystemExit("hooks dir exists")
    for d in (hd, hd / "dd", hd / "cfg"):
        d.mkdir(mode=0o700)
    r = subprocess.run(["unshare", "--user", "--map-root-user", "--net", "--", sys.executable, str(Path(__file__)),
                        "hooks-inner"], capture_output=True, text=True, timeout=400)
    res = {"at": now(), "rc": r.returncode,
           "inner": json.loads(r.stdout.strip().splitlines()[-1]) if r.stdout.strip() else {"stderr_tail": r.stderr[-400:]}}
    old, new = "tools/ai-memory-2.4.0/ai-memory", "tools/ai-memory-2.4.1/ai-memory"
    prod = {"claude-code": HOME / ".claude/settings.json", "codex": HOME / ".codex/hooks.json"}
    for agent in ("claude-code", "codex"):
        a = (hd / f"{agent}-2.4.0.json").read_text()
        b = (hd / f"{agent}-2.4.1.json").read_text()
        ok, n = path_only(a, b, old, new)
        ca = strings_with(json.loads(a), "/ai-memory")
        cb = strings_with(json.loads(b), "/ai-memory")
        pc = sorted(s for s in strings_with(json.loads(prod[agent].read_bytes()), "/ai-memory") if old in s)
        norm_a = sorted(s.replace(str(hd / "dd"), str(LIVE)) for s in ca if old in s)
        norm_b = sorted(s.replace(str(hd / "dd"), str(LIVE)) for s in cb if new in s)
        # negative controls on the checker
        bad_flag = b.replace("127.0.0.1:49474", "127.0.0.1:49475", 1)
        bad_left = b.replace(new, old, 1)
        res[agent] = {"path_only": ok, "lines_changed": n, "cmds_2.4.0_render": sum(old in s for s in ca),
                      "cmds_2.4.1_render": sum(new in s for s in cb), "2.4.1_render_mentions_2.4.0": sum(old in s for s in cb),
                      "prod_cmds_2.4.0": len(pc), "prod_equals_2.4.0_render": pc == norm_a,
                      "prod_path_swapped_equals_2.4.1_render": sorted(s.replace(old, new) for s in pc) == norm_b,
                      "neg_flag_change_detected": (not path_only(a, bad_flag, old, new)[0]) and bad_flag != b,
                      "neg_leftover_old_path_detected": sum(old in s for s in strings_with(json.loads(bad_left), "/ai-memory")) == 1}
    res["scratch_home_entries"] = sorted(p.name for p in (VW / "home").iterdir())
    emit("hooks", res)


# ------------------------------------------------------------------ integrity
def gh(*args, allow_fail=False):
    r = subprocess.run(["gh", *args], capture_output=True, text=True)
    if r.returncode != 0 and not allow_fail:
        raise SystemExit(f"gh failed: {' '.join(args)}: {r.stderr[:300]}")
    return r


def cmd_integrity():
    private_dirs()
    res = {"at": now()}
    rel = json.loads(gh("api", f"repos/{REPO}/releases/tags/v2.4.1").stdout)
    a = next(x for x in rel["assets"] if x["name"] == ASSET)
    res["release"] = {"published_at": rel["published_at"], "immutable": rel.get("immutable"),
                      "prerelease": rel["prerelease"], "draft": rel["draft"]}
    res["api_digest"], res["api_size"] = a.get("digest"), a.get("size")
    res["api_asset_updated_at"] = a.get("updated_at")
    side = gh("release", "download", "v2.4.1", "--repo", REPO, "--pattern", f"{ASSET}.sha256", "-O", "-").stdout
    res["sidecar"] = side.split()[:2]
    res["body_lines"] = [ln.split()[:2] for ln in (rel.get("body") or "").splitlines() if ln.strip().endswith(ASSET)]
    att = gh("api", f"repos/{REPO}/attestations/sha256:{EXPECTED}", allow_fail=True)
    res["attestation_api"] = "404" if "404" in att.stderr or "Not Found" in att.stderr else f"rc={att.returncode}"
    dl = VD / "dl"
    dl.mkdir(exist_ok=True)
    tb = dl / "ai-memory-2.4.1-linux-x86_64.verify.tar.gz"
    if not tb.exists():
        subprocess.run(["curl", "--fail", "--location", "--proto", "=https", "--tlsv1.2", "-sS", "-o", str(tb),
                        ASSET_URL], check=True, timeout=600)
    res["fresh_download"] = {"sha256": sha_file(tb), "bytes": tb.stat().st_size}
    impl_tb = VD.parent / "dl/ai-memory-2.4.1-linux-x86_64.tar.gz"
    res["implementer_tarball_sha256"] = sha_file(impl_tb)
    res["all_agree"] = (res["fresh_download"]["sha256"] == EXPECTED == res["implementer_tarball_sha256"]
                        and res["api_digest"] == f"sha256:{EXPECTED}" and res["sidecar"][0] == EXPECTED
                        and any(x and x[0] == EXPECTED for x in res["body_lines"])
                        and res["fresh_download"]["bytes"] == res["api_size"])
    # installed prefix == tarball contents
    mism, missing, modes = [], [], []
    member_paths = set()
    with tarfile.open(tb, "r:gz") as t:
        members = t.getmembers()
        for m in members:
            rel_p = os.path.normpath(m.name)
            if rel_p == ".":
                continue
            member_paths.add(rel_p)
            dest = V241P / rel_p
            if m.isdir():
                if not dest.is_dir():
                    missing.append(rel_p)
                continue
            if not m.isfile():
                mism.append(f"non-regular:{rel_p}")
                continue
            if not dest.is_file():
                missing.append(rel_p)
                continue
            data = t.extractfile(m).read()
            if sha(data) != sha_file(dest):
                mism.append(rel_p)
            if (dest.stat().st_mode & 0o777) != (m.mode & 0o777 & ~0o022):
                modes.append(rel_p)
    extra = []
    for root, dirs, fl in os.walk(V241P):
        for n in dirs + fl:
            relp = os.path.relpath(os.path.join(root, n), V241P)
            if relp not in member_paths:
                extra.append(relp)
    res["prefix_vs_tarball"] = {"members": len(members), "content_mismatch": len(mism), "missing": len(missing),
                                "mode_mismatch": len(modes), "extra_in_prefix": len(extra),
                                "extra_names": extra[:10], "setuid_or_world_writable": sum(
                                    1 for r, _, fs in os.walk(V241P) for f in fs
                                    if os.stat(os.path.join(r, f)).st_mode & 0o6002)}
    res["installed_bin_sha256"] = sha_file(V241)
    v = subprocess.run([str(V241), "--version"], env=senv(), cwd=str(VW / "tmp"), capture_output=True, text=True, timeout=30)
    res["installed_version"] = [v.returncode, v.stdout.strip()]
    res["prefix_owner_is_me"] = V241P.stat().st_uid == os.getuid()
    res["prefix_ctime"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(V241P.stat().st_ctime))
    emit("integrity", res)


def cmd_upstream():
    res = {"at": now()}
    ref = json.loads(gh("api", f"repos/{REPO}/git/ref/tags/v2.4.1").stdout)["object"]
    res["tag_ref"] = [ref["type"], ref["sha"]]
    if ref["type"] == "tag":
        tobj = json.loads(gh("api", f"repos/{REPO}/git/tags/{ref['sha']}").stdout)
        res["tag_commit"] = tobj["object"]["sha"]
        res["tag_verified"] = tobj.get("verification", {}).get("verified")
    commit = res.get("tag_commit") or ref["sha"]
    runs, page = [], 1
    while True:
        d = json.loads(gh("api", f"repos/{REPO}/commits/{commit}/check-runs?per_page=100&page={page}").stdout)
        runs += d["check_runs"]
        if len(runs) >= d["total_count"] or not d["check_runs"]:
            break
        page += 1
    concl = {}
    for r in runs:
        concl[f"{r['status']}/{r['conclusion']}"] = concl.get(f"{r['status']}/{r['conclusion']}", 0) + 1
    res["check_runs"] = {"total_count": len(runs), "by_status_conclusion": concl}
    for label, base in (("v2.4.0", "v2.4.0"), ("fix792", "00aa6ee8634b6d26ccf8691319d83e10a6517cf0"),
                        ("pr859", "7552d4fd39")):
        r = gh("api", f"repos/{REPO}/compare/{base}...v2.4.1?per_page=1", allow_fail=True)
        if r.returncode != 0:
            res[f"compare_{label}_to_v2.4.1"] = {"error": r.stderr[:160]}
            continue
        c = json.loads(r.stdout)
        res[f"compare_{label}_to_v2.4.1"] = {"status": c["status"], "ahead_by": c["ahead_by"], "behind_by": c["behind_by"]}
    c = json.loads(gh("api", f"repos/{REPO}/compare/v2.4.0...v2.4.1").stdout)
    res["compare_files"] = {"count": len(c.get("files", [])), "added": sorted(f["filename"] for f in c.get("files", [])
                                                                               if f["status"] == "added")}
    mig = [f["filename"] for f in c.get("files", []) if "/migrations/" in f["filename"]]
    res["migration_files_changed"] = mig
    sql = gh("api", "-H", "Accept: application/vnd.github.raw",
             f"repos/{REPO}/contents/crates/ai-memory-store/migrations/V67__managed_run_session_link.sql?ref=v2.4.1").stdout
    res["v67_sql_statements"] = [ln.strip() for ln in sql.splitlines() if ln.strip() and not ln.strip().startswith("--")]
    sets = {}
    for tag in ("v2.4.0", "v2.4.1"):
        lock = gh("api", "-H", "Accept: application/vnd.github.raw", f"repos/{REPO}/contents/Cargo.lock?ref={tag}").stdout
        d = tomllib.loads(lock)
        sets[tag] = sorted({(p["name"], p["version"]) for p in d["package"] if str(p.get("source", "")).startswith("registry+")})
    res["registry_crates"] = {k: len(v) for k, v in sets.items()}
    res["registry_sets_identical"] = sets["v2.4.0"] == sets["v2.4.1"]
    rels = json.loads(gh("api", f"repos/{REPO}/releases?per_page=5").stdout)
    res["latest_releases"] = [[r["tag_name"], r["published_at"], r["prerelease"], r["draft"]] for r in rels[:4]]
    adv = json.loads(gh("api", "-X", "GET", "/advisories", "-f", "ecosystem=rust", "-f", "affects=rmcp@1.7.0").stdout)
    res["advisory_positive_control_rmcp_1.7.0"] = len(adv)
    adv2 = json.loads(gh("api", "-X", "GET", "/advisories", "-f", "ecosystem=rust", "-f",
                         "affects=rmcp@2.2.0,socket2@0.6.3").stdout)
    res["advisories_rmcp_2.2.0_socket2_0.6.3"] = len(adv2)
    emit("upstream", res)


def main():
    c = sys.argv[1]
    if c == "prod":
        return cmd_prod(sys.argv[2])
    if c == "prod-compare":
        return cmd_prod_compare(sys.argv[2], sys.argv[3])
    if c == "backup-vs-live":
        return cmd_backup_vs_live(sys.argv[2])
    if c == "integrity":
        return cmd_integrity()
    if c == "upstream":
        return cmd_upstream()
    if c == "arm-base":
        return cmd_arm_base()
    if c == "arm-cand":
        return cmd_arm_cand()
    if c == "fdprobe":
        return cmd_fdprobe(sys.argv[2])
    if c == "fdprobe-inner":
        print(json.dumps(san(cmd_fdprobe_inner(sys.argv[2]))))
        return 0
    if c == "hooks":
        return cmd_hooks()
    if c == "hooks-inner":
        print(json.dumps(san(cmd_hooks_inner())))
        return 0
    if c == "procs":
        print(json.dumps(san(scratch_procs())))
        return 0
    raise SystemExit(f"unknown {c}")


if __name__ == "__main__":
    sys.exit(main() or 0)
