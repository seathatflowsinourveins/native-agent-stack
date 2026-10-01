#!/usr/bin/env python3
"""Independent verifier re-run for unit ai-memory (2.3.2 -> 2.4.0), read-only w.r.t. production.

Re-runs the key candidate-arm steps on FRESH extractions of the implementer's online backup,
with this verifier's own probe code:
  R1 rehearsal: 2.4.0 serve on VW/rehearsal (migration V64->V66), healthz, MCP info/scope,
     known page, roundtrip, --check-capture (marker / no marker), 2.4.0 hook client,
     2.3.2 hook client into the 2.4.0 server, marker-less probe, embedding status.
  R2 downgrade: 2.3.2 serve on the migrated copy must exit non-zero with DataSchemaAhead
     and leave the store unchanged.
  R3 baseline A/B: 2.3.2 serve on VW/base (fresh extraction), read-only probes.
  D  discrimination: the implementer's own check functions against wrong-version servers
     and a tampered scratch DB copy must FAIL.
Content fingerprint here is stronger than the implementer's: page id -> sha256 over
(workspace, project, path, body_sha256, sha256(body), title, is_latest); observation id ->
sha256 over (session_id, title, body).
Safety: env built from scratch for every ai-memory process (HOME/TMPDIR private, explicit
AI_MEMORY_SERVER_URL of the scratch port); --data-dir only ever VW/*; the live DB is not
opened here; models/ and capture-mode are copied (read) from the live data dir; tokens and
page paths are never printed.
"""
import hashlib, importlib.util, json, os, secrets, signal, socket, sqlite3, string, subprocess
import sys, tarfile, time, urllib.error, urllib.request, uuid
from pathlib import Path

os.umask(0o077)
HOME = Path.home()
ECO = HOME / ".local/share/codex-ecosystem"
LIVE = HOME / ".local/share/ai-memory"
OLD = ECO / "tools/ai-memory-2.3.2/ai-memory"
NEW = ECO / "tools/ai-memory-2.4.0/ai-memory"
W = HOME / ".local/state/native-agent-stack/sota-refresh-20260925/ai-memory"
VW = W / "verify"
BACKUP = W / "pre-2.4.0.tar.gz"
BACKUP_SHA = "c5b14adbeb0c891a1d0cea481f2f230a27c1e7bcc7e854bb45bce7e85f86dd8e"
IMPL_KNOWN_SHA = "98eb1dfb4fc6b0f5aa496ad78443b0d75cca699c9fa25e2a2fbccea46adba356"
OUT = Path(__file__).resolve().parent
PROBES = OUT / "probe-dirs"
WS, PROJ, PWS = "local", "native-agent-stack", "nsr-probe"
DOWNGRADE_MSG = "memory database schema is newer than this ai-memory build"
NOPROXY = urllib.request.build_opener(urllib.request.ProxyHandler({}))
RES = {"at": None}


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def san(o):
    if isinstance(o, str):
        return o.replace(str(HOME), "~")
    if isinstance(o, dict):
        return {san(k): san(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [san(v) for v in o]
    return o


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def plog(name, text):
    with open(VW / "logs" / name, "a") as fh:
        fh.write(f"[{now()}] {text}\n")


def env(url, arm="misc"):
    return {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "HOME": str(VW / "home"),
            "TMPDIR": str(VW / "tmp"), "AI_MEMORY_SERVER_URL": url,
            "AI_MEMORY_BACKFILL_ON_START": "false", "AI_MEMORY_BACKUP_DIR": str(VW / "archives" / arm)}


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def http(method, url, timeout=10):
    req = urllib.request.Request(url, method=method)
    try:
        with NOPROXY.open(req, timeout=timeout) as r:
            return r.status, {k.lower(): v for k, v in r.headers.items()}, r.read()
    except urllib.error.HTTPError as e:
        return e.code, {k.lower(): v for k, v in e.headers.items()}, e.read()


def append_record(name, label, value):
    p = VW / name
    data = json.loads(p.read_text()) if p.exists() else []
    data.append([label, value, now()])
    p.write_text(json.dumps(data))


def token(label):
    t = "nsv" + "".join(secrets.choice(string.ascii_lowercase) for _ in range(16))
    append_record("nonces-all.json", label, t)
    return t


# ------------------------------------------------------------------ store
def ro(db):
    return sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=15)


def cols(con, table):
    return [r[1] for r in con.execute(f"pragma table_info({table})")]


def strong_fp(db):
    con = ro(db)
    try:
        ver, rows = con.execute("select max(version), count(*) from refinery_schema_history").fetchone()
        names = {v: n for v, n in con.execute(
            "select version, name from refinery_schema_history where version > 63")}
        quick = con.execute("pragma quick_check").fetchone()[0]
        pages = {}
        for pid, ws, pj, path, bsha, body, title, latest in con.execute(
                "select id, workspace_id, project_id, path, body_sha256, body, title, is_latest from pages"):
            h = hashlib.sha256()
            for part in (bytes(ws), bytes(pj), path.encode(), bytes(bsha or b""),
                         hashlib.sha256((body or "").encode()).digest(), (title or "").encode(),
                         str(latest).encode()):
                h.update(len(part).to_bytes(8, "big") + part)
            pages[bytes(pid).hex()] = h.hexdigest()
        oc = cols(con, "observations")
        sid_col = "session_id" if "session_id" in oc else "NULL"
        obs = {}
        for oid, sid, title, body in con.execute(
                f"select id, {sid_col}, coalesce(title, ''), coalesce(body, '') from observations"):
            h = hashlib.sha256()
            for part in (bytes(sid) if isinstance(sid, (bytes, memoryview)) else str(sid).encode(),
                         title.encode(), body.encode()):
                h.update(len(part).to_bytes(8, "big") + part)
            obs[bytes(oid).hex()] = h.hexdigest()
        emb = con.execute("select count(*) from sqlite_master where name like '%embedding%'").fetchone()[0]
    finally:
        con.close()
    return {"schema_max": ver, "schema_rows": rows, "migration_names_gt63": names, "quick_check": quick,
            "pages": pages, "obs": obs, "embedding_objects": emb, "obs_has_session_id": sid_col != "NULL"}


def strong_cmp(a, b):
    pch = sum(1 for k, v in a["pages"].items() if b["pages"].get(k) != v)
    omiss = sum(1 for k in a["obs"] if k not in b["obs"])
    och = sum(1 for k, v in a["obs"].items() if k in b["obs"] and b["obs"][k] != v)
    return {"schema": f"V{a['schema_max']}({a['schema_rows']}) -> V{b['schema_max']}({b['schema_rows']})",
            "migration_names_after": {str(k): v for k, v in b["migration_names_gt63"].items()},
            "quick_check_after": b["quick_check"],
            "pages_before": len(a["pages"]), "pages_changed_or_missing": pch, "pages_after": len(b["pages"]),
            "obs_before": len(a["obs"]), "obs_missing": omiss, "obs_content_changed": och,
            "obs_after": len(b["obs"])}


def known_page_path(db):
    con = ro(db)
    try:
        r = con.execute("""select p.path from pages p join projects pr on pr.id = p.project_id
                           join workspaces w on w.id = p.workspace_id
                           where p.is_latest = 1 and w.name = ? and pr.name = ? and p.expires_at is null
                           order by p.created_at, p.path limit 1""", (WS, PROJ)).fetchone()
    finally:
        con.close()
    return r[0] if r else None


def token_rows(db, tok):
    con = ro(db)
    try:
        o = con.execute("select count(*) from observations where instr(coalesce(body,''), ?) > 0 "
                        "or instr(coalesce(title,''), ?) > 0", (tok, tok)).fetchone()[0]
        p = con.execute("select count(*) from pages where instr(coalesce(body,''), ?) > 0 "
                        "or instr(path, ?) > 0", (tok, tok)).fetchone()[0]
    finally:
        con.close()
    return {"observations": o, "pages": p}


def session_row(db, sid):
    con = ro(db)
    try:
        return con.execute("select count(*) from sessions where id = ?", (uuid.UUID(sid).bytes,)).fetchone()[0]
    finally:
        con.close()


def spool_files(dd):
    root = dd / "hook-spool"
    return [p for p in root.rglob("*") if p.is_file() and not p.name.startswith(".")] if root.exists() else []


def spool_token_files(dd, tok):
    return sum(1 for p in spool_files(dd) if tok.encode() in p.read_bytes())


def extract(dd):
    dd.mkdir(mode=0o700)
    with tarfile.open(BACKUP, "r:gz") as tar:
        tar.extractall(dd, filter="data")
    for root, dirs, files in os.walk(dd):
        for n in dirs:
            os.chmod(os.path.join(root, n), 0o700)
        for n in files:
            os.chmod(os.path.join(root, n), 0o600)
    subprocess.run(["cp", "-a", str(LIVE / "models"), str(dd / "models")], check=True)
    subprocess.run(["cp", "-a", str(LIVE / "capture-mode"), str(dd / "capture-mode")], check=True)


# ------------------------------------------------------------------ processes
def vw_procs(exclude=()):
    key = str(VW).encode()
    out = []
    for d in os.listdir("/proc"):
        if not d.isdigit() or int(d) == os.getpid() or int(d) in exclude:
            continue
        try:
            raw = open(f"/proc/{d}/cmdline", "rb").read()
            state = open(f"/proc/{d}/stat").read().rsplit(")", 1)[1].split()[0]
        except OSError:
            continue
        if key in raw and state != "Z" and any(a.endswith(b"/ai-memory") for a in raw.split(b"\0")):
            argv = [a.decode(errors="replace") for a in raw.split(b"\0") if a]
            out.append({"pid": int(d), "sub": next((a for a in argv if a in (
                "serve", "hook", "hook-drain", "backfill", "status")), "?")})
    return out


def wait_quiet(exclude=(), timeout_s=150):
    t0 = time.time()
    while True:
        left = vw_procs(exclude)
        if not left or time.time() - t0 > timeout_s:
            return left, round(time.time() - t0, 1)
        time.sleep(1)


def kill_ours(pid):
    try:
        raw = open(f"/proc/{pid}/cmdline", "rb").read()
    except OSError:
        return "gone"
    if str(VW).encode() not in raw:
        return "not-ours-skipped"
    for sig, wait in ((signal.SIGTERM, 50), (signal.SIGKILL, 20)):
        try:
            os.kill(pid, sig)
        except ProcessLookupError:
            return "gone"
        for _ in range(wait):
            if not Path(f"/proc/{pid}").exists():
                return "gone"
            time.sleep(0.1)
    return "ALIVE"


def start(binary, dd, arm):
    port = free_port()
    url = f"http://127.0.0.1:{port}"
    rd = VW / f"run-{arm}"
    rd.mkdir(mode=0o700, exist_ok=True)
    (VW / "archives" / arm).mkdir(mode=0o700, exist_ok=True)
    log = open(VW / "logs" / f"serve-{arm}.log", "ab")
    p = subprocess.Popen([str(binary), "--data-dir", str(dd), "serve", "--transport", "http", "--enable-web",
                          "--bind", f"127.0.0.1:{port}", "--workspace", WS, "--project", PROJ],
                         cwd=str(rd), env=env(url, arm), stdin=subprocess.DEVNULL, stdout=log,
                         stderr=subprocess.STDOUT, start_new_session=True)
    log.close()
    return p, url


def status_json(binary, dd, url):
    try:
        r = subprocess.run([str(binary), "--data-dir", str(dd), "status", "--json"], env=env(url),
                           cwd=str(VW / "tmp"), capture_output=True, text=True, timeout=60)
        return json.loads(r.stdout) if r.returncode == 0 else None
    except (subprocess.TimeoutExpired, ValueError):
        return None


def wait_ready(p, binary, dd, url, timeout_s=180):
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        if p.poll() is not None:
            return None, f"exited rc={p.returncode}"
        st = status_json(binary, dd, url)
        if st:
            return st, round(time.time() - t0, 1)
        time.sleep(0.5)
    return None, "timeout"


def stop(p, url):
    if p.poll() is None:
        p.send_signal(signal.SIGTERM)
        try:
            p.wait(timeout=30)
        except subprocess.TimeoutExpired:
            p.kill()
            p.wait(timeout=10)
    try:
        http("GET", url + "/healthz", timeout=2)
        closed = False
    except (urllib.error.URLError, OSError):
        closed = True
    return {"rc": p.returncode, "pid_gone": not Path(f"/proc/{p.pid}").exists(), "port_closed": closed}


def status_brief(st):
    if not st:
        return None
    d = st.get("derived") or {}
    e = (st.get("providers") or {}).get("embedding") or {}
    return {"version": st.get("version"), "pages_rows": d.get("pages_rows"),
            "fts_parity_pages": d.get("pages_fts_rows") == d.get("pages_rows"),
            "obs_rows": d.get("observations_rows"),
            "fts_parity_obs": d.get("observations_fts_rows") == d.get("observations_rows"),
            "latest_pages_missing_embeddings": d.get("latest_pages_missing_embeddings"),
            "embedding": [e.get("status"), e.get("provider"), e.get("model"), e.get("dim")],
            "capture_mode": st.get("capture_mode")}


# ------------------------------------------------------------------ MCP
class RpcErr(RuntimeError):
    pass


_id = [0]


def rpc(url, method, params=None):
    _id[0] += 1
    msg = {"jsonrpc": "2.0", "id": _id[0], "method": method}
    if params is not None:
        msg["params"] = params
    req = urllib.request.Request(url, data=json.dumps(msg).encode(), method="POST", headers={
        "Content-Type": "application/json", "Accept": "application/json, text/event-stream"})
    with NOPROXY.open(req, timeout=60) as r:
        ct = r.headers.get("Content-Type", "")
        body = r.read().decode()
    if "text/event-stream" in ct:
        body = [ln[5:].strip() for ln in body.splitlines() if ln.startswith("data:") and ln[5:].strip()][-1]
    out = json.loads(body)
    if "error" in out:
        plog("rpc-errors.log", f"{method}: {out['error']}")
        raise RpcErr(method)
    return out["result"]


def tool(url, name, args):
    res = rpc(url, "tools/call", {"name": name, "arguments": args})
    text = "".join(c.get("text", "") for c in res.get("content", []) if c.get("type") == "text")
    if res.get("isError"):
        plog("rpc-errors.log", f"{name} isError: {text[:400]}")
        raise RpcErr(name)
    try:
        return json.loads(text)
    except ValueError:
        return {"_text": text}


def info(mcp):
    init = rpc(mcp, "initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                                   "clientInfo": {"name": "nsr-verifier", "version": "1"}})
    names = sorted(t["name"] for t in rpc(mcp, "tools/list", {}).get("tools", []))
    st = tool(mcp, "memory_status", {"workspace": WS, "project": PROJ})
    sc = st.get("scope")
    return {"server": (init.get("serverInfo") or {}).get("name"),
            "version": (init.get("serverInfo") or {}).get("version"),
            "protocol": init.get("protocolVersion"), "tools": len(names),
            "tool_names_sha256": hashlib.sha256("\n".join(names).encode()).hexdigest()[:16],
            "scope_resolved_by": sc.get("resolved_by") if isinstance(sc, dict) else None,
            "status_has_scope": isinstance(sc, dict),
            "evidence_rows_present": "evidence_rows" in (st.get("counts") or {})}


def page_digest(mcp, path):
    pg = tool(mcp, "memory_read_page", {"workspace": WS, "project": PROJ, "path": path})
    b = pg.get("body") or ""
    return {"path_matches": pg.get("path") == path, "body_sha256": hashlib.sha256(b.encode()).hexdigest()}


def roundtrip(mcp, tok):
    sc = {"workspace": PWS, "project": "ai-memory-verify-mcp"}
    path = f"notes/verify-{tok}.md"
    tool(mcp, "memory_write_page", {**sc, "path": path, "title": "verifier probe",
                                    "body": f"Disposable verifier probe page {tok}."})
    hits = [h.get("path") for h in tool(mcp, "memory_query", {**sc, "query": tok}).get("hits", [])]
    got = tool(mcp, "memory_read_page", {**sc, "path": path}).get("body") or ""
    tool(mcp, "memory_delete_page", {**sc, "path": path})
    after = tool(mcp, "memory_query", {**sc, "query": tok}).get("hits", [])
    try:
        tool(mcp, "memory_read_page", {**sc, "path": path})
        gone = False
    except RpcErr:
        gone = True
    return {"query_exact_one_hit": hits == [path], "read_has_token": tok in got,
            "hits_after_delete": len(after), "read_after_delete_fails": gone,
            "pass": hits == [path] and tok in got and not after and gone}


def obs_by_session(mcp, proj, sid, tok, timeout_s=60):
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        try:
            r = tool(mcp, "memory_read_session_observations",
                     {"workspace": PWS, "project": proj, "session_id": sid, "limit": 50})
            rows = r.get("observations") or []
            if any(tok in str(x.get("body") or "") or tok in str(x.get("title") or "")
                   for x in rows if isinstance(x, dict)):
                return {"found": True, "rows": len(rows), "seconds": round(time.time() - t0, 1)}
        except RpcErr:
            pass
        time.sleep(1)
    return {"found": False, "seconds": round(time.time() - t0, 1)}


# ------------------------------------------------------------------ hooks
def pdir(name, project=None):
    d = PROBES / name
    d.mkdir(parents=True, exist_ok=True)
    m = d / ".ai-memory.toml"
    if project:
        m.write_text(f'workspace = "{PWS}"\nproject = "{project}"\n')
    elif m.exists():
        m.unlink()
    (d / "transcript.jsonl").write_text("")
    return d


def hook(binary, dd, url, cwd, event, payload, check=False):
    cmd = [str(binary), "--data-dir", str(dd), "hook", "--event", event, "--agent", "claude-code",
           "--server-url", url] + (["--check-capture"] if check else [])
    return subprocess.run(cmd, input=json.dumps(payload), text=True, cwd=str(cwd), env=env(url),
                          capture_output=True, timeout=60)


def check_capture(binary, dd, url, cwd):
    before = len(spool_files(dd))
    r = hook(binary, dd, url, cwd, "post-tool-use",
             {"session_id": str(uuid.uuid4()), "transcript_path": str(cwd / "transcript.jsonl"),
              "cwd": str(cwd), "hook_event_name": "PostToolUse", "tool_name": "Bash",
              "tool_input": {"command": "true"}, "tool_response": {"stdout": "", "stderr": ""}},
             check=True)
    try:
        d = json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        d = {}
    return {"rc": r.returncode, "capture_mode": d.get("capture_mode"), "marker_present": d.get("marker_present"),
            "admits_capture": d.get("admits_capture"), "spooled_added": len(spool_files(dd)) - before}


def session(binary, dd, url, cwd, tok, label):
    sid = str(uuid.uuid4())
    append_record("sessions-all.json", label, sid)
    base = {"session_id": sid, "transcript_path": str(cwd / "transcript.jsonl"), "cwd": str(cwd)}
    rcs = []
    for ev, extra in (("session-start", {"hook_event_name": "SessionStart", "source": "startup"}),
                      ("post-tool-use", {"hook_event_name": "PostToolUse", "tool_name": "Bash",
                                         "tool_input": {"command": f"printf {tok}"},
                                         "tool_response": {"stdout": tok, "stderr": "", "interrupted": False}}),
                      ("session-end", {"hook_event_name": "SessionEnd", "reason": "other"})):
        r = hook(binary, dd, url, cwd, ev, {**base, **extra})
        if r.stderr.strip():
            plog(f"hook-{label}.log", f"{ev}: {r.stderr.strip()[:1500]}")
        rcs.append(r.returncode)
    return sid, rcs


def g(res, key, fn):
    try:
        res[key] = fn()
    except Exception as e:  # noqa: BLE001
        plog("errors.log", f"{key}: {type(e).__name__}: {e}")
        res[key] = {"error": type(e).__name__}


# ------------------------------------------------------------------ implementer's checks (for D)
def impl_module():
    spec = importlib.util.spec_from_file_location("aimem_accept", str(OUT.parent / "aimem_accept.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.plog = lambda name, text: plog("impl-" + name, text)
    m.W = VW  # never let their helpers touch the implementer's W
    return m


# ------------------------------------------------------------------ arms
def arm_rehearsal(IM):
    dd = VW / "rehearsal"
    r = {}
    extract(dd)
    fpb = strong_fp(dd / "db/memory.sqlite")
    ifpb = IM.fingerprint(dd / "db/memory.sqlite")
    r["fp_before"] = f"V{fpb['schema_max']} ({fpb['schema_rows']} rows) pages={len(fpb['pages'])} obs={len(fpb['obs'])} quick_check={fpb['quick_check']}"
    kp = known_page_path(dd / "db/memory.sqlite")
    r["known_page_same_as_implementer"] = kp is not None and kp == (W / "known-page").read_text()
    p, url = start(NEW, dd, "rehearsal")
    mcp = url + "/mcp"
    try:
        st, ready = wait_ready(p, NEW, dd, url)
        r["ready"] = ready
        r["status_at_start"] = status_brief(st)
        g(r, "endpoints", lambda: {"healthz": [http("GET", url + "/healthz")[0],
                                               json.loads(http("GET", url + "/healthz")[2] or b"null")],
                                   "get_mcp": [http("GET", mcp)[0], http("GET", mcp)[1].get("allow")]})
        g(r, "info", lambda: info(mcp))
        g(r, "impl_mcp_info_expect_2.4.0_pass", lambda: IM.mcp_info(mcp, "2.4.0")["pass"])
        g(r, "impl_mcp_info_expect_2.3.2_pass", lambda: IM.mcp_info(mcp, "2.3.2")["pass"])
        def kpd():
            x = page_digest(mcp, kp)
            x["equals_implementer_sha"] = x["body_sha256"] == IMPL_KNOWN_SHA
            return x
        g(r, "known_page", kpd)
        g(r, "roundtrip", lambda: roundtrip(mcp, token("rehearsal-mcp")))
        md = pdir("rehearsal-marker", "ai-memory-verify-hook")
        nd = pdir("rehearsal-nomarker")
        od = pdir("rehearsal-oldhook", "ai-memory-verify-oldhook")
        g(r, "check_capture_marker_new", lambda: check_capture(NEW, dd, url, md))
        g(r, "check_capture_nomarker_new", lambda: check_capture(NEW, dd, url, nd))
        toks = {}

        def new_hook():
            toks["hook"] = token("rehearsal-hook")
            sid, rcs = session(NEW, dd, url, md, toks["hook"], "rehearsal-hook")
            toks["hook_sid"] = sid
            return {"rcs": rcs, "obs": obs_by_session(mcp, "ai-memory-verify-hook", sid, toks["hook"])}
        g(r, "hook_new_client", new_hook)

        def old_hook():
            toks["old"] = token("rehearsal-oldhook")
            sid, rcs = session(OLD, dd, url, od, toks["old"], "rehearsal-oldhook")
            toks["old_sid"] = sid
            return {"rcs": rcs, "obs": obs_by_session(mcp, "ai-memory-verify-oldhook", sid, toks["old"])}
        g(r, "hook_old_client_into_new_server", old_hook)

        def nomarker():
            toks["nm"] = token("rehearsal-nomarker")
            sid, rcs = session(NEW, dd, url, nd, toks["nm"], "rehearsal-nomarker")
            toks["nm_sid"] = sid
            return {"rcs": rcs, "spool_files_with_token": spool_token_files(dd, toks["nm"]),
                    "spool_files_total": len(spool_files(dd))}
        g(r, "nomarker_probe", nomarker)
        left, waited = wait_quiet(exclude={p.pid})
        r["drain_wait"] = {"seconds": waited, "left": left}
        r["spool_files_before_stop"] = len(spool_files(dd))
        r["status_after_probes"] = status_brief(status_json(NEW, dd, url))
    finally:
        r["stop"] = stop(p, url)
        r["leftovers_killed"] = [kill_ours(x["pid"]) for x in vw_procs()]
    fpa = strong_fp(dd / "db/memory.sqlite")
    r["migration"] = strong_cmp(fpb, fpa)
    ifpa = IM.fingerprint(dd / "db/memory.sqlite")
    r["impl_fp_compare_66"] = IM.fp_compare(ifpb, ifpa, 66)
    r["db_token_rows"] = {k: token_rows(dd / "db/memory.sqlite", toks[k]) for k in ("hook", "old", "nm") if k in toks}
    r["db_session_rows"] = {k: session_row(dd / "db/memory.sqlite", toks[k + "_sid"])
                            for k in ("hook", "old", "nm") if k + "_sid" in toks}
    r["archives"] = {"pre_migration_receipt": (dd / "pre-migration-backup.json").exists(),
                     "backup_dir_entries": len(list((VW / "archives/rehearsal").iterdir())),
                     "scratch_home_entries": len(list((VW / "home").iterdir())),
                     "real_home_archives": len(list(HOME.glob("ai-memory-backup-*")))}
    return r, fpa, ifpa, ifpb


def arm_downgrade(fpa):
    dd = VW / "rehearsal"
    port = free_port()
    logp = VW / "logs" / "downgrade.log"
    with open(logp, "ab") as log:
        p = subprocess.Popen([str(OLD), "--data-dir", str(dd), "serve", "--transport", "http", "--enable-web",
                              "--bind", f"127.0.0.1:{port}", "--workspace", WS, "--project", PROJ],
                             cwd=str(VW / "tmp"), env=env(f"http://127.0.0.1:{port}", "downgrade"),
                             stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            rc, exited = p.wait(timeout=90), True
        except subprocess.TimeoutExpired:
            exited = False
            p.kill()
            rc = p.wait(timeout=10)
    lines = [ln.strip() for ln in logp.read_text(errors="replace").splitlines() if DOWNGRADE_MSG in ln]
    fpd = strong_fp(dd / "db/memory.sqlite")
    c = strong_cmp(fpa, fpd)
    return {"exited_by_itself": exited, "rc": rc, "schema_ahead_message": bool(lines),
            "names_V65": bool(lines) and "V65" in lines[0],
            "store_after": c["schema"], "quick_check_after": c["quick_check_after"],
            "pages_changed_by_refusal": c["pages_changed_or_missing"],
            "obs_missing_or_changed_by_refusal": c["obs_missing"] + c["obs_content_changed"],
            "pid_gone": not Path(f"/proc/{p.pid}").exists()}


def arm_baseline(IM, rehearsal_status):
    dd = VW / "base"
    r = {}
    extract(dd)
    fpb = strong_fp(dd / "db/memory.sqlite")
    kp = known_page_path(dd / "db/memory.sqlite")
    p, url = start(OLD, dd, "base")
    mcp = url + "/mcp"
    try:
        st, ready = wait_ready(p, OLD, dd, url)
        r["ready"] = ready
        r["status_at_start"] = status_brief(st)
        g(r, "endpoints", lambda: {"healthz": http("GET", url + "/healthz")[0],
                                   "get_mcp": [http("GET", mcp)[0], http("GET", mcp)[1].get("allow")]})
        g(r, "info", lambda: info(mcp))
        g(r, "impl_mcp_info_expect_2.3.2_pass", lambda: IM.mcp_info(mcp, "2.3.2")["pass"])
        g(r, "impl_mcp_info_expect_2.4.0_pass", lambda: IM.mcp_info(mcp, "2.4.0")["pass"])
        g(r, "known_page", lambda: page_digest(mcp, kp))
        g(r, "impl_status_check_2.4.0_on_2.3.2_pass", lambda: IM.status_check(st, "2.4.0", False)["pass"])
        md = pdir("base-marker", "ai-memory-verify-hook")
        nd = pdir("base-nomarker")
        g(r, "check_capture_marker_old", lambda: check_capture(OLD, dd, url, md))
        g(r, "check_capture_nomarker_old", lambda: check_capture(OLD, dd, url, nd))
    finally:
        r["stop"] = stop(p, url)
        r["leftovers_killed"] = [kill_ours(x["pid"]) for x in vw_procs()]
    fpa = strong_fp(dd / "db/memory.sqlite")
    r["store"] = strong_cmp(fpb, fpa)
    return r


def discrimination(IM, ifpb, rehearsal_db):
    """The implementer's fingerprint compare must FAIL on a tampered copy / wrong expected version."""
    d = {}
    neg = VW / "neg"
    neg.mkdir(mode=0o700)
    dst = neg / "memory.sqlite"
    src = sqlite3.connect(f"file:{rehearsal_db}?mode=ro", uri=True)
    out = sqlite3.connect(str(dst))
    src.backup(out)
    src.close()
    out.close()
    base = IM.fingerprint(dst)
    d["untampered_copy_expect_66"] = IM.fp_compare(ifpb, base, 66)[0]
    d["untampered_copy_expect_64"] = IM.fp_compare(ifpb, base, 64)[0]
    con = sqlite3.connect(str(dst))
    try:
        pid = con.execute("select id from pages order by id limit 1").fetchone()[0]
        con.execute("update pages set body_sha256 = zeroblob(32) where id = ?", (pid,))
        con.commit()
        d["one_page_body_sha_changed_expect_66"] = IM.fp_compare(ifpb, IM.fingerprint(dst), 66)[0]
    except sqlite3.DatabaseError as e:
        d["one_page_body_sha_changed_expect_66"] = f"update refused: {type(e).__name__}"
    con.close()
    # restore a fresh copy, then delete one pre-existing observation
    dst.unlink()
    src = sqlite3.connect(f"file:{rehearsal_db}?mode=ro", uri=True)
    out = sqlite3.connect(str(dst))
    src.backup(out)
    src.close()
    out.close()
    con = sqlite3.connect(str(dst))
    oid = bytes.fromhex(ifpb["observation_ids"][0])
    con.execute("pragma foreign_keys = off")
    try:
        con.execute("delete from observations where id = ?", (oid,))
        con.commit()
        d["one_observation_deleted_expect_66"] = IM.fp_compare(ifpb, IM.fingerprint(dst), 66)[0]
    except sqlite3.DatabaseError as e:
        d["one_observation_deleted_expect_66"] = f"delete refused: {type(e).__name__}"
    con.close()
    # the implementer's status_check and arm_pass on doctored copies of their own records
    st = json.loads((VW.parent / "status-rehearsal-after-probes.json").read_text())
    d["impl_status_check_real_after_probes"] = IM.status_check(st, "2.4.0", True)["pass"]
    bad = json.loads(json.dumps(st))
    bad["derived"]["observations_fts_rows"] = (bad["derived"]["observations_fts_rows"] or 0) - 1
    d["impl_status_check_fts_off_by_one"] = IM.status_check(bad, "2.4.0", True)["pass"]
    bad = json.loads(json.dumps(st))
    bad["providers"]["embedding"]["status"] = "unknown"
    d["impl_status_check_embedding_unknown_strict"] = IM.status_check(bad, "2.4.0", True)["pass"]
    bad = json.loads(json.dumps(st))
    bad["derived"]["latest_pages_missing_embeddings"] = 1
    d["impl_status_check_missing_embedding"] = IM.status_check(bad, "2.4.0", True)["pass"]
    rec = json.loads((OUT.parent / "results/step4-rehearsal.json").read_text())
    d["impl_arm_pass_recorded_all_true"] = all(IM.arm_pass(rec, "2.4.0").values())
    for label, mutate in (
            ("hook_not_found", lambda x: x["hook_probe"]["obs"].__setitem__("nonce_found", False)),
            ("allowlist_bypass_db_row", lambda x: x["db_nonce_counts"]["rehearsal-nomarker"].__setitem__("observations", 1)),
            ("nomarker_admits", lambda x: x["check_capture_nomarker"].__setitem__("admits_capture", True)),
            ("healthz_404", lambda x: x["endpoints"].__setitem__("healthz_code", 404)),
            ("archive_written", lambda x: x["archives"].__setitem__("backup_dir_entries", 1)),
            ("fingerprint_fail", lambda x: x.__setitem__("fingerprint_pass", False))):
        x = json.loads(json.dumps(rec))
        mutate(x)
        d[f"impl_arm_pass_{label}"] = all(IM.arm_pass(x, "2.4.0").values())
    return d


def main():
    if VW.exists():
        raise SystemExit("verify dir exists; refusing to reuse")
    VW.mkdir(mode=0o700)
    for sub in ("home", "tmp", "logs", "archives", "archives/downgrade"):
        (VW / sub).mkdir(mode=0o700)
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(SystemExit(143)))
    signal.signal(signal.SIGHUP, lambda *_: (_ for _ in ()).throw(SystemExit(129)))
    RES["at"] = now()
    RES["backup"] = {"sha256_matches": sha_file(BACKUP) == BACKUP_SHA, "bytes": BACKUP.stat().st_size,
                     "mode": oct(BACKUP.stat().st_mode & 0o777)}
    with tarfile.open(BACKUP, "r:gz") as t:
        names = t.getnames()
    RES["backup"]["members"] = len(names)
    RES["backup"]["top_level"] = sorted({n.split("/")[0] for n in names})
    if not RES["backup"]["sha256_matches"]:
        print(json.dumps(san(RES)))
        return 1
    IM = impl_module()
    try:
        RES["R1_rehearsal_2.4.0"], fpa, ifpa, ifpb = arm_rehearsal(IM)
        RES["R2_downgrade_2.3.2_on_V66"] = arm_downgrade(fpa)
        RES["R3_baseline_2.3.2"] = arm_baseline(IM, None)
        RES["D_discrimination"] = discrimination(IM, ifpb, VW / "rehearsal/db/memory.sqlite")
    finally:
        RES["final_vw_procs"] = [dict(x, kill=kill_ours(x["pid"])) for x in vw_procs()]
        RES["final_vw_procs_after_kill"] = vw_procs()
        RES["finished"] = now()
        s = json.dumps(san(RES), indent=1)
        (OUT / "rerun.json").write_text(s + "\n")
        print(s)
    return 0


if __name__ == "__main__":
    sys.exit(main())
