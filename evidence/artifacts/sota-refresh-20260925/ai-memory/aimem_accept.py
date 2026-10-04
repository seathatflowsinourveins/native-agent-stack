#!/usr/bin/env python3
"""ai-memory 2.3.2 -> 2.4.0 on host nativestack-5975wx-20260925 (2026-09-25).

Runs only the refuter's corrected acceptance steps 0-4: install into a fresh prefix,
read-only pre-flight, online backup through the live 2.3.2 service, a 2.3.2 baseline
on one restored copy and a 2.4.0 rehearsal (with migration) on a separate restored
copy. No cutover: the live service, bin/ symlink, hooks, ~/.claude, ~/.codex and the
live store are never modified.

Subcommands:
  prod-snapshot LABEL   read-only production state (service, symlink, hooks, live DB)
  install               step 0
  preflight             step 1
  backup                step 2
  baseline              step 3 (2.3.2 on W/base)
  rehearsal             step 4 (2.4.0 on W/rehearsal, then 2.3.2 downgrade refusal)
  rollback-check        step 4, last item (fresh extraction opens under 2.3.2 at V64)
  prod-compare A B      production before/after proof, plus a nonce scan of the live store
  procs                 list scratch ai-memory processes still alive

Safety properties:
  * Every ai-memory process started here gets an environment built from scratch (PATH,
    LANG, HOME=<private scratch home>, TMPDIR=<private>, AI_MEMORY_SERVER_URL=<the scratch
    server or a dead port>, AI_MEMORY_BACKFILL_ON_START=false, AI_MEMORY_BACKUP_DIR=
    <private>). This host exports the live URL in AI_MEMORY_SERVER_URL; nothing inherits it.
  * Nothing runs with --data-dir on the live store; config-loading commands append to
    <data-dir>/logs. The live DB is opened only with mode=ro. The backup client uses a
    private scratch --data-dir and reaches the live 2.3.2 server by URL.
  * Output is sanitized: counts, flags, versions and digests. No page or observation
    text, nonces, page paths, config values or credentials. Private artifacts stay in W (0700).
"""
import hashlib
import json
import os
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
OLD = ECO / "tools/ai-memory-2.3.2/ai-memory"
NEWP = ECO / "tools/ai-memory-2.4.0"
NEW = NEWP / "ai-memory"
BIN_LINK = ECO / "bin/ai-memory"
LIVE_URL = "http://127.0.0.1:49474"
DEAD_URL = "http://127.0.0.1:9"
W = HOME / ".local/state/native-agent-stack/sota-refresh-20260925/ai-memory"
I = Path(__file__).resolve().parent
RES = I / "results"
DL = I / "dl"
PROBES = I / "probe-dirs"
REPO = "akitaonrails/ai-memory"
TAG = "v2.4.0"
ASSET = "ai-memory-linux-x86_64.tar.gz"
ASSET_URL = f"https://github.com/{REPO}/releases/download/{TAG}/{ASSET}"
EXPECTED_SHA = "590f75ddaf0f8f1a07b70ba20900de717b89c3f6c46e6e5e0540ade302795076"
WS, PROJ, PROBE_WS = "local", "native-agent-stack", "nsr-probe"
DOWNGRADE_MSG = "memory database schema is newer than this ai-memory build"
EXPECTED_TOOLS = 23
PROBE_TOOLS = ("memory_write_page", "memory_query", "memory_read_page", "memory_delete_page",
               "memory_status", "memory_read_session_observations")
NOPROXY = urllib.request.build_opener(urllib.request.ProxyHandler({}))


# ----------------------------------------------------------------------------- helpers
def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def san(obj):
    home = str(HOME)
    if isinstance(obj, str):
        return obj.replace(home, "~")
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


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def plog(name, text):
    """Append diagnostic text to a PRIVATE log in W (never printed)."""
    with open(W / "logs" / name, "a") as fh:
        fh.write(f"[{now()}] {text}\n")


def guard(res, key, fn):
    """Record fn()'s result under key; on failure record only the exception type
    (details go to a private log, because server messages can echo probe tokens)."""
    try:
        res[key] = fn()
    except Exception as exc:  # noqa: BLE001 - every probe failure must be recorded, not raised
        plog("probe-errors.log", f"{key}: {type(exc).__name__}: {exc}")
        res[key] = {"error": type(exc).__name__}
    return res[key]


def ensure_private():
    for d in (W.parent.parent, W.parent, W):
        d.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(W, 0o700)
    for sub in ("home", "tmp", "logs", "archives", "client"):
        (W / sub).mkdir(mode=0o700, exist_ok=True)
    for arm in ("misc", "base", "rehearsal", "downgrade", "rollback"):
        (W / "archives" / arm).mkdir(mode=0o700, exist_ok=True)


def senv(url=DEAD_URL, archive_arm="misc"):
    """Environment built from scratch for every ai-memory process this script starts."""
    return {
        "PATH": "/usr/bin:/bin",
        "LANG": "C.UTF-8",
        "HOME": str(W / "home"),
        "TMPDIR": str(W / "tmp"),
        "AI_MEMORY_SERVER_URL": url,
        "AI_MEMORY_BACKFILL_ON_START": "false",
        "AI_MEMORY_BACKUP_DIR": str(W / "archives" / archive_arm),
    }


def http(method, url, timeout=10):
    req = urllib.request.Request(url, method=method)
    try:
        with NOPROXY.open(req, timeout=timeout) as resp:
            return resp.status, {k.lower(): v for k, v in resp.headers.items()}, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, {k.lower(): v for k, v in exc.headers.items()}, exc.read()


def free_port():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def ro(db):
    return sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=15)


# ----------------------------------------------------------------------------- nonces
def nonces():
    path = W / "nonces.json"
    return json.loads(path.read_text()) if path.exists() else {}


def _append_all(name, label, value):
    """Append-only record of every token/session ever issued, across attempts,
    so the final live-store scan covers all of them."""
    path = W / name
    data = json.loads(path.read_text()) if path.exists() else []
    data.append([label, value, now()])
    path.write_text(json.dumps(data))


def all_nonces():
    path = W / "nonces-all.json"
    return [v for _, v, _ in json.loads(path.read_text())] if path.exists() else []


def all_sessions():
    path = W / "sessions-all.json"
    return [v for _, v, _ in json.loads(path.read_text())] if path.exists() else []


def new_nonce(label):
    data = nonces()
    tok = "nsr" + "".join(secrets.choice(string.ascii_lowercase) for _ in range(14))
    data[label] = tok
    (W / "nonces.json").write_text(json.dumps(data))
    _append_all("nonces-all.json", label, tok)
    return tok


def record_session(label, sid):
    path = W / "sessions.json"
    data = json.loads(path.read_text()) if path.exists() else {}
    data[label] = sid
    path.write_text(json.dumps(data))
    _append_all("sessions-all.json", label, sid)


# ----------------------------------------------------------------------------- store checks
def fingerprint(db):
    con = ro(db)
    try:
        ver, rows = con.execute("select max(version), count(*) from refinery_schema_history").fetchone()
        quick = con.execute("pragma quick_check").fetchone()[0]
        pages = {}
        for pid, wsid, pjid, path, sha in con.execute(
                "select id, workspace_id, project_id, path, body_sha256 from pages"):
            pages[bytes(pid).hex()] = hashlib.sha256(
                b"|".join([bytes(wsid), bytes(pjid), path.encode(), bytes(sha or b"")])).hexdigest()
        obs = sorted(bytes(r[0]).hex() for r in con.execute("select id from observations"))
    finally:
        con.close()
    return {"schema_max": ver, "schema_rows": rows, "quick_check": quick, "pages": pages,
            "observation_ids": obs}


def fp_brief(fp):
    return (f"schema V{fp['schema_max']} ({fp['schema_rows']} rows) quick_check={fp['quick_check']} "
            f"pages={len(fp['pages'])} observations={len(fp['observation_ids'])}")


def fp_compare(before, after, expected):
    changed = [k for k, v in before["pages"].items() if after["pages"].get(k) != v]
    missing = len(set(before["observation_ids"]) - set(after["observation_ids"]))
    ok = (after["schema_max"] == expected and after["schema_rows"] == expected
          and after["quick_check"] == "ok" and not changed and missing == 0)
    line = (f"V{before['schema_max']} -> V{after['schema_max']} ({after['schema_rows']} rows) "
            f"quick_check={after['quick_check']} | pages before={len(before['pages'])} "
            f"missing_or_changed={len(changed)} after={len(after['pages'])} | "
            f"observations before={len(before['observation_ids'])} missing={missing} "
            f"after={len(after['observation_ids'])} | {'PASS' if ok else 'FAIL'}")
    return ok, line


def known_page(db):
    con = ro(db)
    try:
        row = con.execute(
            """select p.path from pages p join projects pr on pr.id = p.project_id
               join workspaces w on w.id = p.workspace_id
               where p.is_latest = 1 and w.name = ? and pr.name = ? and p.expires_at is null
               order by p.created_at, p.path limit 1""", (WS, PROJ)).fetchone()
    finally:
        con.close()
    return row[0] if row else None


def probe_scope_rows(db):
    con = ro(db)
    try:
        ws = con.execute("select count(*) from workspaces where name = ?", (PROBE_WS,)).fetchone()[0]
        pj = con.execute("select count(*) from projects where name like 'ai-memory-acceptance%'").fetchone()[0]
    finally:
        con.close()
    return {"workspaces_nsr_probe": ws, "projects_ai_memory_acceptance": pj}


def nonce_counts(db, labels=None):
    data = nonces()
    con = ro(db)
    out = {}
    try:
        for label, tok in data.items():
            if labels and label not in labels:
                continue
            o = con.execute("select count(*) from observations where instr(body, ?) > 0 "
                            "or instr(coalesce(title, ''), ?) > 0", (tok, tok)).fetchone()[0]
            p = con.execute("select count(*) from pages where instr(coalesce(body, ''), ?) > 0 "
                            "or instr(path, ?) > 0", (tok, tok)).fetchone()[0]
            out[label] = {"observations": o, "pages": p}
    finally:
        con.close()
    return out


def session_rows(db, labels=None):
    path = W / "sessions.json"
    data = json.loads(path.read_text()) if path.exists() else {}
    con = ro(db)
    out = {}
    try:
        for label, sid in data.items():
            if labels and label not in labels:
                continue
            out[label] = con.execute("select count(*) from sessions where id = ?",
                                     (uuid.UUID(sid).bytes,)).fetchone()[0]
    finally:
        con.close()
    return out


def _spool_entries(dd):
    """Spooled event files; the `.drain.lock` lock file is not an event."""
    root = dd / "hook-spool"
    if not root.exists():
        return []
    return [p for p in root.rglob("*") if p.is_file() and not p.name.startswith(".")]


def spool_hits(dd, tok):
    files = hits = 0
    for path in _spool_entries(dd):
        files += 1
        try:
            if tok.encode() in path.read_bytes():
                hits += 1
        except OSError:
            pass
    return {"spool_files": files, "files_with_nonce": hits}


def spool_count(dd):
    return len(_spool_entries(dd))


# ----------------------------------------------------------------------------- processes
def ai_procs():
    """Scratch ai-memory processes of this run: argv names an ai-memory binary and W."""
    wb = str(W).encode()
    out = []
    for d in os.listdir("/proc"):
        if not d.isdigit() or int(d) == os.getpid():
            continue
        try:
            raw = open(f"/proc/{d}/cmdline", "rb").read()
            state = open(f"/proc/{d}/stat").read().rsplit(")", 1)[1].split()[0]
        except OSError:
            continue
        if wb not in raw or state == "Z":
            continue
        argv = [a.decode(errors="replace") for a in raw.split(b"\0") if a]
        if not any(a.endswith("/ai-memory") for a in argv):
            continue
        sub = next((a for a in argv if a in ("serve", "hook", "hook-drain", "backfill", "status",
                                             "backup")), "?")
        out.append({"pid": int(d), "sub": sub})
    return out


def live_procs():
    lb = f"--data-dir\0{LIVE}\0".encode()
    subs = {}
    for d in os.listdir("/proc"):
        if not d.isdigit():
            continue
        try:
            raw = open(f"/proc/{d}/cmdline", "rb").read()
        except OSError:
            continue
        if lb not in raw:
            continue
        argv = [a.decode(errors="replace") for a in raw.split(b"\0") if a]
        sub = next((a for a in argv if a in ("serve", "hook", "hook-drain", "backfill")), "?")
        subs[sub] = subs.get(sub, 0) + 1
    return subs


def kill_scratch(procs):
    out = []
    for proc in procs:
        pid = proc["pid"]
        try:
            raw = open(f"/proc/{pid}/cmdline", "rb").read()
        except OSError:
            out.append({"pid": pid, "result": "gone"})
            continue
        if str(W).encode() not in raw:
            out.append({"pid": pid, "result": "not-ours-skipped"})
            continue
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        for _ in range(50):
            if not Path(f"/proc/{pid}").exists():
                break
            time.sleep(0.1)
        if Path(f"/proc/{pid}").exists():
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            time.sleep(0.5)
        out.append({"pid": pid, "sub": proc["sub"],
                    "result": "gone" if not Path(f"/proc/{pid}").exists() else "ALIVE"})
    return out


def wait_scratch_quiet(exclude=(), timeout_s=120):
    t0 = time.time()
    while True:
        procs = [p for p in ai_procs() if p["pid"] not in exclude]
        if not procs or time.time() - t0 > timeout_s:
            return procs, round(time.time() - t0, 1)
        time.sleep(1)


# ----------------------------------------------------------------------------- server control
def status_json(binary, dd, url):
    try:
        r = subprocess.run([str(binary), "--data-dir", str(dd), "status", "--json"], env=senv(url),
                           cwd=str(W / "tmp"), capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        return None
    if r.returncode != 0:
        return None
    try:
        return json.loads(r.stdout)
    except ValueError:
        return None


def start_server(binary, dd, arm):
    port = free_port()
    url = f"http://127.0.0.1:{port}"
    run_dir = W / f"run-{arm}"
    run_dir.mkdir(mode=0o700, exist_ok=True)
    with open(W / "logs" / f"serve-{arm}.log", "ab") as log:
        proc = subprocess.Popen(
            [str(binary), "--data-dir", str(dd), "serve", "--transport", "http", "--enable-web",
             "--bind", f"127.0.0.1:{port}", "--workspace", WS, "--project", PROJ],
            cwd=str(run_dir), env=senv(url, arm), stdin=subprocess.DEVNULL, stdout=log,
            stderr=subprocess.STDOUT, start_new_session=True, umask=0o077)
    return proc, port, url


def wait_ready(proc, binary, dd, url, timeout_s=240):
    """Ready = `status --json` answers. A fresh server reports embedding status
    "unknown" until its first embedding call, so embedding health is judged from
    a status taken after the write/query probes (attempt-1 finding)."""
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        if proc.poll() is not None:
            return None, f"server exited rc={proc.returncode}"
        st = status_json(binary, dd, url)
        if st is not None:
            return st, round(time.time() - t0, 1)
        time.sleep(0.5)
    return None, "timeout"


def stop_server(proc, url):
    if proc.poll() is None:
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=10)
    try:
        http("GET", url + "/healthz", timeout=2)
        port_closed = False
    except (urllib.error.URLError, OSError):
        port_closed = True
    return {"rc": proc.returncode, "pid_gone": not Path(f"/proc/{proc.pid}").exists(),
            "port_closed": port_closed}


def status_check(st, expected_version, require_embedding_ok=True):
    if not st:
        return {"pass": False, "error": "no status"}
    d = st.get("derived") or {}
    emb = (st.get("providers") or {}).get("embedding") or {}
    checks = {
        "version": st.get("version") == expected_version,
        "pages_fts_match": d.get("pages_fts_rows") == d.get("pages_rows"),
        "observations_fts_match": d.get("observations_fts_rows") == d.get("observations_rows"),
        "embedding_ok": emb.get("status") == "ok" if require_embedding_ok
        else emb.get("status") in ("ok", "unknown"),
        "embedding_identity": (emb.get("provider"), emb.get("model"), emb.get("dim"))
        == ("local", "all-MiniLM-L6-v2", 384),
        "latest_pages_missing_embeddings_zero": d.get("latest_pages_missing_embeddings") == 0,
    }
    return {"version": st.get("version"), "counts": st.get("counts"),
            "derived": {k: d.get(k) for k in ("pages_rows", "pages_fts_rows", "observations_rows",
                                              "observations_fts_rows",
                                              "latest_pages_missing_embeddings", "embedding_rows")},
            "embedding": {k: emb.get(k) for k in ("status", "provider", "model", "dim")},
            "embedding_keys": sorted(emb.keys()), "capture_mode": st.get("capture_mode"),
            "checks": checks, "pass": all(checks.values())}


def endpoint_facts(url):
    hz = http("GET", url + "/healthz")
    gm = http("GET", url + "/mcp")
    try:
        hz_json = json.loads(hz[2] or b"null")
    except ValueError:
        hz_json = None
    return {"healthz_code": hz[0], "healthz_body": hz_json if hz[0] == 200 else None,
            "get_mcp_code": gm[0], "get_mcp_allow": gm[1].get("allow")}


# ----------------------------------------------------------------------------- MCP probes
class ProbeError(RuntimeError):
    pass


_ID = [0]


def rpc(url, method, params=None, timeout=60):
    _ID[0] += 1
    msg = {"jsonrpc": "2.0", "id": _ID[0], "method": method}
    if params is not None:
        msg["params"] = params
    req = urllib.request.Request(url, data=json.dumps(msg).encode(), method="POST", headers={
        "Content-Type": "application/json", "Accept": "application/json, text/event-stream"})
    with NOPROXY.open(req, timeout=timeout) as resp:
        ctype = resp.headers.get("Content-Type", "")
        body = resp.read().decode()
    if "text/event-stream" in ctype:
        frames = [ln[5:].strip() for ln in body.splitlines()
                  if ln.startswith("data:") and ln[5:].strip()]
        body = frames[-1]
    out = json.loads(body)
    if "error" in out:
        plog("probe-errors.log", f"{method}: {out['error']}")
        raise ProbeError(method)
    return out["result"]


def call(url, tool, args):
    res = rpc(url, "tools/call", {"name": tool, "arguments": args})
    text = "".join(c.get("text", "") for c in res.get("content", []) if c.get("type") == "text")
    if res.get("isError"):
        plog("probe-errors.log", f"{tool} isError: {text[:500]}")
        raise ProbeError(tool)
    try:
        return json.loads(text)
    except ValueError:
        return {"_text": text}


def mcp_info(url, expected_version):
    init = rpc(url, "initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                                   "clientInfo": {"name": "nsr-acceptance", "version": "1"}})
    si = init.get("serverInfo", {})
    tools = sorted(t["name"] for t in rpc(url, "tools/list", {}).get("tools", []))
    st = call(url, "memory_status", {"workspace": WS, "project": PROJ})
    scope = st.get("scope")
    resolved_by = scope.get("resolved_by") if isinstance(scope, dict) else None
    has_probe = all(t in tools for t in PROBE_TOOLS)
    ok = (si.get("name") == "ai-memory" and si.get("version") == expected_version
          and len(tools) == EXPECTED_TOOLS and has_probe)
    if expected_version != "2.3.2":
        ok = ok and resolved_by == "explicit"
    return {"server": si.get("name"), "version": si.get("version"),
            "protocol": init.get("protocolVersion"), "tools": len(tools), "tool_names": tools,
            "has_probe_tools": has_probe, "status_has_scope": isinstance(scope, dict),
            "scope_resolved_by": resolved_by, "status_counts": st.get("counts"), "pass": ok}


def read_page_digest(url, path):
    page = call(url, "memory_read_page", {"workspace": WS, "project": PROJ, "path": path})
    body = page.get("body", "") or ""
    return {"path_matches": page.get("path") == path,
            "body_sha256": hashlib.sha256(body.encode()).hexdigest(), "body_chars": len(body)}


def roundtrip(url, tok):
    path = f"notes/ai-memory-acceptance-{tok}.md"
    scope = {"workspace": PROBE_WS, "project": "ai-memory-acceptance-mcp"}
    call(url, "memory_write_page", {**scope, "path": path, "title": "ai-memory acceptance probe",
                                    "body": f"Disposable acceptance probe page; token {tok}."})
    hits = call(url, "memory_query", {**scope, "query": tok}).get("hits", [])
    got = call(url, "memory_read_page", {**scope, "path": path}).get("body", "") or ""
    call(url, "memory_delete_page", {**scope, "path": path})
    after = call(url, "memory_query", {**scope, "query": tok}).get("hits", [])
    try:
        call(url, "memory_read_page", {**scope, "path": path})
        read_after_delete_failed = False
    except ProbeError:
        read_after_delete_failed = True
    hit_paths = [h.get("path") for h in hits]
    ok = hit_paths == [path] and tok in got and not after and read_after_delete_failed
    return {"write": "ok", "query_hits": len(hits), "query_path_matches": hit_paths == [path],
            "read_has_token": tok in got, "hits_after_delete": len(after),
            "read_after_delete_failed": read_after_delete_failed, "pass": ok}


def obs_poll(url, proj, sid, tok, timeout_s=60):
    t0 = time.time()
    attempts = 0
    while True:
        attempts += 1
        for mode, extra in (("session_id", {"session_id": sid}), ("latest_completed", {})):
            try:
                res = call(url, "memory_read_session_observations",
                           {"workspace": PROBE_WS, "project": proj, "query": tok, "limit": 20,
                            **extra})
            except ProbeError:
                continue
            rows = res.get("observations") or []
            if any(isinstance(r, dict) and (tok in str(r.get("body") or "")
                                            or tok in str(r.get("title") or "")) for r in rows):
                return {"nonce_found": True, "via": mode, "rows": len(rows),
                        "total": res.get("total"), "seconds": round(time.time() - t0, 1)}
        if time.time() - t0 > timeout_s:
            return {"nonce_found": False, "via": None, "attempts": attempts,
                    "seconds": round(time.time() - t0, 1)}
        time.sleep(1)


# ----------------------------------------------------------------------------- hook probes
def probe_dir(name, project=None):
    d = PROBES / name
    d.mkdir(parents=True, exist_ok=True)
    marker = d / ".ai-memory.toml"
    if project:
        marker.write_text(f'workspace = "{PROBE_WS}"\nproject = "{project}"\n')
    elif marker.exists():
        marker.unlink()
    return d


def hook_cmd(binary, dd, url, event, check=False):
    cmd = [str(binary), "--data-dir", str(dd), "hook", "--event", event, "--agent", "claude-code",
           "--server-url", url]
    return cmd + (["--check-capture"] if check else [])


def check_capture(binary, dd, url, cwd):
    payload = {"session_id": str(uuid.uuid4()), "transcript_path": str(cwd / "transcript.jsonl"),
               "cwd": str(cwd), "hook_event_name": "PostToolUse", "tool_name": "Bash",
               "tool_input": {"command": "true"},
               "tool_response": {"stdout": "", "stderr": "", "interrupted": False}}
    before = spool_count(dd)
    r = subprocess.run(hook_cmd(binary, dd, url, "post-tool-use", check=True),
                       input=json.dumps(payload), text=True, cwd=str(cwd), env=senv(url),
                       capture_output=True, timeout=60)
    try:
        d = json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        d = {}
    return {"rc": r.returncode, "capture_mode": d.get("capture_mode"),
            "marker_present": d.get("marker_present"), "admits_capture": d.get("admits_capture"),
            "spooled_files_added": spool_count(dd) - before}


def hook_probe(binary, dd, url, cwd, tok, label):
    sid = str(uuid.uuid4())
    record_session(label, sid)
    (cwd / "transcript.jsonl").write_text("")
    events = {}
    for ev in ("session-start", "post-tool-use", "session-end"):
        base = {"session_id": sid, "transcript_path": str(cwd / "transcript.jsonl"),
                "cwd": str(cwd)}
        if ev == "session-start":
            base.update(hook_event_name="SessionStart", source="startup")
        elif ev == "post-tool-use":
            base.update(hook_event_name="PostToolUse", tool_name="Bash",
                        tool_input={"command": f"echo {tok}"},
                        tool_response={"stdout": tok, "stderr": "", "interrupted": False})
        else:
            base.update(hook_event_name="SessionEnd", reason="other")
        t0 = time.time()
        r = subprocess.run(hook_cmd(binary, dd, url, ev), input=json.dumps(base), text=True,
                           cwd=str(cwd), env=senv(url), capture_output=True, timeout=60)
        lines = r.stdout.strip().splitlines()
        try:
            is_json = isinstance(json.loads(lines[-1]), dict) if lines else False
        except ValueError:
            is_json = False
        if r.stderr.strip():
            plog(f"hook-stderr-{label}.log", f"{ev}: {r.stderr.strip()[:2000]}")
        events[ev] = {"rc": r.returncode, "stdout_is_json_object": is_json,
                      "stderr_lines": len(r.stderr.splitlines()),
                      "seconds": round(time.time() - t0, 2)}
    return sid, events


def extract_backup(dd):
    backup = W / "pre-2.4.0.tar.gz"
    dd.mkdir(mode=0o700)
    with tarfile.open(backup, "r:gz") as tar:
        tar.extractall(dd, filter="data")
    for root, dirs, files in os.walk(dd):
        for name in dirs:
            os.chmod(os.path.join(root, name), 0o700)
        for name in files:
            os.chmod(os.path.join(root, name), 0o600)
    subprocess.run(["cp", "-a", str(LIVE / "models"), str(dd / "models")], check=True)
    subprocess.run(["cp", "-a", str(LIVE / "capture-mode"), str(dd / "capture-mode")], check=True)
    return {"models_copied": (dd / "models").is_dir(),
            "capture_mode_file": (dd / "capture-mode").read_text().strip()}


def archive_state(dd, arm):
    return {"pre_migration_receipt_present": (dd / "pre-migration-backup.json").exists(),
            "backup_dir_entries": len(list((W / "archives" / arm).iterdir())),
            "scratch_home_archives": len(list((W / "home").glob("ai-memory-backup-*"))),
            "real_home_archives": len(list(HOME.glob("ai-memory-backup-*"))),
            "data_dir_backups_dir_entries": len(list((dd / "backups").iterdir()))
            if (dd / "backups").is_dir() else 0}


# ----------------------------------------------------------------------------- steps
def cmd_prod_snapshot(label):
    ensure_private()
    snap = {"label": label, "at": now()}
    show = subprocess.run(["systemctl", "--user", "show", "nativestack-memory.service", "-p",
                           "MainPID", "-p", "ActiveState", "-p", "SubState", "-p",
                           "ExecMainStartTimestamp", "-p", "NRestarts", "-p", "InvocationID"],
                          capture_output=True, text=True).stdout
    snap["service"] = dict(ln.split("=", 1) for ln in show.strip().splitlines() if "=" in ln)
    if "InvocationID" in snap["service"]:
        snap["service"]["InvocationID"] = "sha256:" + hashlib.sha256(
            snap["service"]["InvocationID"].encode()).hexdigest()[:12]
    snap["bin_link_target"] = os.path.realpath(BIN_LINK)
    snap["old_bin_sha256"] = sha256_file(OLD)
    snap["new_prefix_exists"] = NEWP.exists()
    for name, path in (("claude_settings", HOME / ".claude/settings.json"),
                       ("codex_hooks", HOME / ".codex/hooks.json")):
        raw = path.read_bytes()
        snap[name] = {"sha256": hashlib.sha256(raw).hexdigest(),
                      "mtime": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                             time.gmtime(path.stat().st_mtime)),
                      "cmds_2.3.2": raw.count(b"tools/ai-memory-2.3.2/ai-memory"),
                      "cmds_2.4.0": raw.count(b"tools/ai-memory-2.4.0/ai-memory")}
    fp = fingerprint(LIVE_DB)
    (W / f"fp-live-{label}.json").write_text(json.dumps(fp))
    snap["live_db"] = fp_brief(fp)
    snap["live_probe_scope_rows"] = probe_scope_rows(LIVE_DB)
    snap["live_pre_migration_receipt_present"] = (LIVE / "pre-migration-backup.json").exists()
    snap["home_backup_archives"] = len(list(HOME.glob("ai-memory-backup-*")))
    snap["live_ai_memory_procs_by_subcommand"] = live_procs()
    snap["live_endpoints"] = endpoint_facts(LIVE_URL)
    snap["scratch_procs"] = ai_procs()
    emit(f"prod-snapshot-{label}", snap)


def cmd_install():
    ensure_private()
    DL.mkdir(exist_ok=True)
    res = {"at": now(), "prefix": str(NEWP)}
    if NEWP.exists():
        res["abort"] = "prefix already exists; not touching it"
        emit("step0-install", res)
        return 1
    rel = json.loads(subprocess.run(["gh", "api", f"repos/{REPO}/releases/tags/{TAG}"],
                                    capture_output=True, text=True, check=True).stdout)
    asset = next(a for a in rel["assets"] if a["name"] == ASSET)
    sidecar = subprocess.run(["gh", "release", "download", TAG, "--repo", REPO, "--pattern",
                              f"{ASSET}.sha256", "-O", "-"], capture_output=True, text=True,
                             check=True).stdout.split()
    res["release"] = {"tag": rel.get("tag_name"), "published_at": rel.get("published_at"),
                      "prerelease": rel.get("prerelease"), "draft": rel.get("draft"),
                      "immutable": rel.get("immutable")}
    res["expected_sha256"] = EXPECTED_SHA
    res["sidecar"] = {"sha256": sidecar[0] if sidecar else None,
                      "name": sidecar[1].lstrip("*") if len(sidecar) > 1 else None}
    res["api_asset"] = {"digest": asset.get("digest"), "size": asset.get("size"),
                        "url_matches": asset.get("browser_download_url") == ASSET_URL}
    res["release_body_lists_sha"] = EXPECTED_SHA in (rel.get("body") or "")
    agree = (res["sidecar"]["sha256"] == EXPECTED_SHA
             and asset.get("digest") == f"sha256:{EXPECTED_SHA}" and res["api_asset"]["url_matches"])
    res["upstream_sources_agree"] = agree
    if not agree:
        res["abort"] = "upstream checksum sources disagree with the expected value; not downloading"
        emit("step0-install", res)
        return 1
    tarball = DL / "ai-memory-2.4.0-linux-x86_64.tar.gz"
    part = tarball.with_suffix(".gz.partial")
    subprocess.run(["curl", "--fail", "--location", "--proto", "=https", "--tlsv1.2", "-sS",
                    "-o", str(part), ASSET_URL], check=True, timeout=500)
    actual = sha256_file(part)
    res["download"] = {"sha256": actual, "bytes": part.stat().st_size,
                       "size_matches_api": part.stat().st_size == asset.get("size")}
    res["integrity_verified"] = actual == EXPECTED_SHA and res["download"]["size_matches_api"]
    if not res["integrity_verified"]:
        res["abort"] = "downloaded sha256 does not match; stopped before extraction"
        emit("step0-install", res)
        return 1
    part.rename(tarball)
    with tarfile.open(tarball, "r:gz") as tar:
        members = tar.getmembers()
    names = [m.name for m in members]
    unsafe = [m.name for m in members
              if m.name.startswith("/") or ".." in Path(m.name).parts
              or m.issym() or m.islnk() or m.isdev() or (m.mode & 0o6002)]
    tops = sorted({(Path(n).parts or (".",))[0] for n in names})
    res["tar"] = {"members": len(names), "unsafe_members": len(unsafe), "top_level": tops}
    if unsafe:
        res["abort"] = "unsafe tar members (absolute, .., links, devices, setuid or world-writable)"
        emit("step0-install", res)
        return 1
    NEWP.mkdir(mode=0o755)
    os.chmod(NEWP, 0o755)
    subprocess.run(["tar", "-xzf", str(tarball), "-C", str(NEWP), "--no-same-owner"], check=True,
                   umask=0o022)
    ver = subprocess.run([str(NEW), "--version"], env=senv(), cwd=str(W / "tmp"),
                         capture_output=True, text=True, timeout=30)
    res["new_version_stdout"] = ver.stdout.strip()
    res["new_version_rc"] = ver.returncode
    res["new_bin_sha256"] = sha256_file(NEW)
    res["prefix_entries"] = sorted(p.name for p in NEWP.iterdir())
    link = os.path.realpath(BIN_LINK)
    res["bin_link_target"] = link
    res["assert"] = {"version_exact": ver.stdout.strip() == "ai-memory 2.4.0",
                     "hooks_dir_exists": (NEWP / "hooks").is_dir(),
                     "bin_link_still_old": link == str(OLD)}
    res["pass"] = all(res["assert"].values())
    emit("step0-install", res)
    return 0 if res["pass"] else 1


def cmd_preflight():
    ensure_private()
    ep = endpoint_facts(LIVE_URL)
    with open(LIVE / "config.toml", "rb") as fh:
        cfg = tomllib.load(fh)
    server_url_top = "server_url" in cfg
    nested = []

    def walk(obj, prefix):
        for key, val in obj.items():
            if isinstance(val, dict):
                walk(val, f"{prefix}{key}.")
            elif key == "server_url" and prefix:
                nested.append(f"{prefix}{key}")
    walk(cfg, "")
    bfs = cfg.get("backfill_on_start")
    # Non-secret selectors that decide what a scratch server on a copy of this
    # config.toml could reach (no values of any other key are read out).
    hosts = cfg.get("allowed_hosts", [])
    selectors = {
        "embedding_provider": cfg.get("embedding_provider"),
        "llm_provider_configured": "llm_provider" in cfg,
        "admission_webhooks_configured": bool(cfg.get("admission_webhooks")),
        "allowed_hosts": hosts if all(isinstance(h, str) and len(h) < 64 for h in hosts) else "hidden",
        "auto_improve_scheduler_enabled": cfg.get("auto_improve", {}).get("scheduler", {}).get("enabled"),
        "auto_improve_eval_enabled": cfg.get("auto_improve", {}).get("eval", {}).get("enabled"),
        "consolidate_on_session_end": cfg.get("consolidate_on_session_end"),
    }
    del cfg
    res = {"at": now(), **ep, "config_server_url_top_level_present": server_url_top,
           "config_server_url_nested_keys": nested,
           "config_backfill_on_start": bfs if isinstance(bfs, bool) else "absent-or-non-bool",
           "scratch_safety_selectors": selectors}
    res["assert"] = {"healthz_404": ep["healthz_code"] == 404,
                     "get_mcp_405_allow_post": ep["get_mcp_code"] == 405
                     and "POST" in (ep["get_mcp_allow"] or ""),
                     "server_url_absent": not server_url_top,
                     "backfill_on_start_false": bfs is False}
    res["pass"] = all(res["assert"].values())
    emit("step1-preflight", res)
    return 0 if res["pass"] else 1


def cmd_backup():
    ensure_private()
    dest = W / "pre-2.4.0.tar.gz"
    res = {"at": now()}
    if dest.exists():
        res["abort"] = "backup already exists"
        emit("step2-backup", res)
        return 1
    t0 = time.time()
    r = subprocess.run([str(OLD), "--data-dir", str(W / "client"), "backup", "--to", str(dest)],
                       env=senv(LIVE_URL), cwd=str(W / "tmp"), capture_output=True, text=True,
                       timeout=500)
    res["rc"] = r.returncode
    res["seconds"] = round(time.time() - t0, 1)
    res["stdout"] = r.stdout.strip()[:300]
    if r.stderr.strip():
        plog("backup-stderr.log", r.stderr.strip()[:4000])
    res["stderr_lines"] = len(r.stderr.splitlines())
    if r.returncode != 0 or not dest.exists():
        res["pass"] = False
        emit("step2-backup", res)
        return 1
    os.chmod(dest, 0o600)
    with tarfile.open(dest, "r:gz") as tar:
        names = tar.getnames()
    res["archive"] = {"bytes": dest.stat().st_size, "sha256": sha256_file(dest),
                      "mode": oct(dest.stat().st_mode & 0o777), "members": len(names),
                      "top_level": sorted({n.split("/")[0] for n in names})}
    res["assert"] = {"has_db_memory_sqlite": "db/memory.sqlite" in names,
                     "has_wiki": any(n == "wiki" or n.startswith("wiki/") for n in names),
                     "has_config_toml": "config.toml" in names,
                     "no_unsafe_members": not [n for n in names
                                               if n.startswith("/") or ".." in Path(n).parts]}
    res["pass"] = all(res["assert"].values())
    emit("step2-backup", res)
    return 0 if res["pass"] else 1


def run_arm(arm, binary, version):
    """Shared body of step 3 (2.3.2 on W/base) and step 4 (2.4.0 on W/rehearsal)."""
    ensure_private()
    dd = W / arm
    res = {"arm": arm, "binary": str(binary), "expected_version": version, "at": now()}
    if dd.exists():
        res["abort"] = f"{dd} already exists"
        emit(f"step-{arm}", res)
        return res
    res["extract"] = extract_backup(dd)
    fp_before = fingerprint(dd / "db/memory.sqlite")
    (W / f"fp-{arm}-before.json").write_text(json.dumps(fp_before))
    res["fingerprint_before"] = fp_brief(fp_before)
    kp = known_page(dd / "db/memory.sqlite")
    if arm == "base":
        (W / "known-page").write_text(kp or "")
    res["known_page_selected"] = bool(kp)
    res["known_page_same_as_base"] = (kp == (W / "known-page").read_text()) if kp else False
    proc, port, url = start_server(binary, dd, arm)
    mcp = url + "/mcp"
    try:
        st, ready = wait_ready(proc, binary, dd, url)
        (W / f"status-{arm}.json").write_text(json.dumps(st))
        res["ready_seconds"] = ready
        res["status"] = status_check(st, version, require_embedding_ok=False)
        guard(res, "endpoints", lambda: endpoint_facts(url))
        guard(res, "info", lambda: mcp_info(mcp, version))
        guard(res, "known_page", lambda: read_page_digest(mcp, kp) if kp else {"error": "none"})
        guard(res, "roundtrip", lambda: roundtrip(mcp, new_nonce(f"{arm}-mcp")))
        mdir = probe_dir(f"{arm}-marker", "ai-memory-acceptance-hook")
        ndir = probe_dir(f"{arm}-nomarker")
        guard(res, "check_capture_marker", lambda: check_capture(binary, dd, url, mdir))
        guard(res, "check_capture_nomarker", lambda: check_capture(binary, dd, url, ndir))

        def new_hook():
            tok = new_nonce(f"{arm}-hook")
            sid, events = hook_probe(binary, dd, url, mdir, tok, f"{arm}-hook")
            return {"events": events, "obs": obs_poll(mcp, "ai-memory-acceptance-hook", sid, tok)}
        guard(res, "hook_probe", new_hook)
        if arm == "rehearsal":
            def old_hook():
                odir = probe_dir(f"{arm}-oldhook-marker", "ai-memory-acceptance-oldhook")
                otok = new_nonce(f"{arm}-oldhook")
                osid, oevents = hook_probe(OLD, dd, url, odir, otok, f"{arm}-oldhook")
                return {"events": oevents,
                        "obs": obs_poll(mcp, "ai-memory-acceptance-oldhook", osid, otok)}
            guard(res, "old_hook_client_to_new_server", old_hook)

        def nomarker():
            ntok = new_nonce(f"{arm}-nomarker")
            _, nevents = hook_probe(binary, dd, url, ndir, ntok, f"{arm}-nomarker")
            return {"events": nevents, "spool": spool_hits(dd, ntok)}
        guard(res, "nomarker_probe", nomarker)
        left, waited = wait_scratch_quiet(exclude={proc.pid}, timeout_s=120)
        res["drain_wait"] = {"seconds": waited, "still_running": left}
        res["spool_files_before_stop"] = spool_count(dd)

        def post_status():
            st2 = status_json(binary, dd, url)
            (W / f"status-{arm}-after-probes.json").write_text(json.dumps(st2))
            return status_check(st2, version, require_embedding_ok=True)
        guard(res, "status_after_probes", post_status)
    finally:
        res["stop"] = stop_server(proc, url)
        left = ai_procs()
        res["killed_leftovers"] = kill_scratch(left) if left else []
    fp_after = fingerprint(dd / "db/memory.sqlite")
    (W / f"fp-{arm}-after.json").write_text(json.dumps(fp_after))
    ok, line = fp_compare(fp_before, fp_after, 64 if version == "2.3.2" else 66)
    res["fingerprint_compare"] = line
    res["fingerprint_pass"] = ok
    labels = [k for k in nonces() if k.startswith(arm + "-")]
    res["db_nonce_counts"] = nonce_counts(dd / "db/memory.sqlite", labels)
    res["db_session_rows"] = session_rows(dd / "db/memory.sqlite", labels)
    res["archives"] = archive_state(dd, arm)
    return res


def arm_pass(res, version):
    c = {
        "status": res.get("status", {}).get("pass") is True,
        "status_after_probes_embedding_ok": res.get("status_after_probes", {}).get("pass") is True,
        "spool_empty_before_stop": res.get("spool_files_before_stop") == 0,
        "info": res.get("info", {}).get("pass") is True,
        "roundtrip": res.get("roundtrip", {}).get("pass") is True,
        "check_capture_marker": res.get("check_capture_marker", {}).get("capture_mode") == "allowlist"
        and res["check_capture_marker"].get("marker_present") is True
        and res["check_capture_marker"].get("admits_capture") is True,
        "check_capture_nomarker": res.get("check_capture_nomarker", {}).get("marker_present") is False
        and res["check_capture_nomarker"].get("admits_capture") is False,
        "check_capture_spooled_nothing": res.get("check_capture_marker", {}).get("spooled_files_added") == 0
        and res.get("check_capture_nomarker", {}).get("spooled_files_added") == 0,
        "hook_nonce_found": res.get("hook_probe", {}).get("obs", {}).get("nonce_found") is True,
        "nomarker_spool_clean": res.get("nomarker_probe", {}).get("spool", {}).get("files_with_nonce") == 0,
        "nomarker_db_zero": res.get("db_nonce_counts", {}).get(f"{res['arm']}-nomarker", {}).get("observations") == 0,
        "hook_db_row": res.get("db_nonce_counts", {}).get(f"{res['arm']}-hook", {}).get("observations", 0) >= 1,
        "fingerprint": res.get("fingerprint_pass") is True,
        "server_stopped": res.get("stop", {}).get("pid_gone") is True
        and res.get("stop", {}).get("port_closed") is True,
        "no_pre_migration_archive": not res.get("archives", {}).get("pre_migration_receipt_present")
        and res.get("archives", {}).get("backup_dir_entries") == 0
        and res.get("archives", {}).get("scratch_home_archives") == 0,
    }
    c["known_page_read"] = (res.get("known_page") or {}).get("path_matches") is True
    if version != "2.3.2":
        c["healthz_200_ok"] = res.get("endpoints", {}).get("healthz_code") == 200 \
            and res["endpoints"].get("healthz_body") == {"status": "ok"}
    return c


def cmd_baseline():
    res = run_arm("base", OLD, "2.3.2")
    if "abort" not in res:
        res["checks"] = arm_pass(res, "2.3.2")
        res["pass"] = all(res["checks"].values())
    emit("step3-baseline", res)
    return 0 if res.get("pass") else 1


def cmd_rehearsal():
    res = run_arm("rehearsal", NEW, "2.4.0")
    if "abort" in res:
        emit("step4-rehearsal", res)
        return 1
    base = json.loads((RES / "step3-baseline.json").read_text())
    res["checks"] = arm_pass(res, "2.4.0")
    res["checks"]["known_page_sha_equals_baseline"] = (
        (res.get("known_page") or {}).get("body_sha256") is not None
        and (res.get("known_page") or {}).get("body_sha256")
        == (base.get("known_page") or {}).get("body_sha256"))
    # Downgrade: 2.3.2 must refuse the migrated V66 copy and fail closed.
    port = free_port()
    log_path = W / "logs" / "downgrade.log"
    with open(log_path, "ab") as log:
        proc = subprocess.Popen(
            [str(OLD), "--data-dir", str(W / "rehearsal"), "serve", "--transport", "http",
             "--enable-web", "--bind", f"127.0.0.1:{port}", "--workspace", WS, "--project", PROJ],
            cwd=str(W / "tmp"), env=senv(f"http://127.0.0.1:{port}", "downgrade"),
            stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
            start_new_session=True, umask=0o077)
        try:
            rc = proc.wait(timeout=90)
            exited = True
        except subprocess.TimeoutExpired:
            exited = False
            proc.kill()
            rc = proc.wait(timeout=10)
    text = log_path.read_text(errors="replace")
    msg_lines = [ln.strip() for ln in text.splitlines() if DOWNGRADE_MSG in ln]
    fp_post = fingerprint(W / "rehearsal/db/memory.sqlite")
    res["downgrade"] = {"exited_by_itself": exited, "rc": rc,
                        "log_has_schema_ahead_message": bool(msg_lines),
                        "message_excerpt": msg_lines[0][:400] if msg_lines else None,
                        "store_after_refusal": fp_brief(fp_post)}
    res["checks"]["downgrade_fails_closed"] = exited and rc != 0 and bool(msg_lines) \
        and fp_post["schema_max"] == 66
    res["pass"] = all(res["checks"].values())
    emit("step4-rehearsal", res)
    return 0 if res["pass"] else 1


def cmd_rollback_check():
    ensure_private()
    dd = W / "rollback-check"
    res = {"at": now()}
    if dd.exists():
        res["abort"] = "rollback-check dir exists"
        emit("step4-rollback-check", res)
        return 1
    res["extract"] = extract_backup(dd)
    fp_before = fingerprint(dd / "db/memory.sqlite")
    res["fingerprint_before"] = fp_brief(fp_before)
    proc, port, url = start_server(OLD, dd, "rollback")
    try:
        st, ready = wait_ready(proc, OLD, dd, url)
        res["ready_seconds"] = ready
        res["status"] = status_check(st, "2.3.2", require_embedding_ok=False)
    finally:
        res["stop"] = stop_server(proc, url)
        left = ai_procs()
        res["killed_leftovers"] = kill_scratch(left) if left else []
    fp_after = fingerprint(dd / "db/memory.sqlite")
    ok, line = fp_compare(fp_before, fp_after, 64)
    res["fingerprint_compare"] = line
    res["archives"] = archive_state(dd, "rollback")
    res["checks"] = {"opens_under_2.3.2": (res.get("status") or {}).get("version") == "2.3.2",
                     "status_pass": (res.get("status") or {}).get("pass") is True,
                     "still_v64": ok,
                     "server_stopped": res["stop"]["pid_gone"] and res["stop"]["port_closed"]}
    res["pass"] = all(res["checks"].values())
    emit("step4-rollback-check", res)
    return 0 if res["pass"] else 1


def cmd_prod_compare(a, b):
    sa = json.loads((RES / f"prod-snapshot-{a}.json").read_text())
    sb = json.loads((RES / f"prod-snapshot-{b}.json").read_text())
    fa = json.loads((W / f"fp-live-{a}.json").read_text())
    fb = json.loads((W / f"fp-live-{b}.json").read_text())
    ok, line = fp_compare(fa, fb, 64)
    res = {"at": now(), "fingerprint_superset_compare": line}
    res["checks"] = {
        "service_same_main_pid": sa["service"].get("MainPID") == sb["service"].get("MainPID"),
        "service_same_start": sa["service"].get("ExecMainStartTimestamp")
        == sb["service"].get("ExecMainStartTimestamp"),
        "service_same_invocation": sa["service"].get("InvocationID") == sb["service"].get("InvocationID"),
        "service_no_restarts": sa["service"].get("NRestarts") == sb["service"].get("NRestarts"),
        "bin_link_unchanged_old": sa["bin_link_target"] == sb["bin_link_target"]
        == str(OLD).replace(str(HOME), "~"),
        "old_bin_unchanged": sa["old_bin_sha256"] == sb["old_bin_sha256"],
        "claude_settings_unchanged": sa["claude_settings"]["sha256"] == sb["claude_settings"]["sha256"],
        "codex_hooks_unchanged": sa["codex_hooks"]["sha256"] == sb["codex_hooks"]["sha256"],
        "hooks_still_2.3.2_8_7": sb["claude_settings"]["cmds_2.3.2"] == 8
        and sb["codex_hooks"]["cmds_2.3.2"] == 7 and sb["claude_settings"]["cmds_2.4.0"] == 0
        and sb["codex_hooks"]["cmds_2.4.0"] == 0,
        "live_schema_still_v64": fb["schema_max"] == 64 and fb["schema_rows"] == 64,
        "live_existing_rows_unchanged": ok,
        "live_probe_scope_rows_unchanged": sa["live_probe_scope_rows"] == sb["live_probe_scope_rows"],
        "no_live_pre_migration_receipt": sb["live_pre_migration_receipt_present"] is False,
        "no_home_archives_added": sa["home_backup_archives"] == sb["home_backup_archives"],
        "live_endpoints_same": sa["live_endpoints"] == sb["live_endpoints"],
    }
    toks_all = all_nonces()
    con = ro(LIVE_DB)
    try:
        obs_hits = sum(con.execute("select count(*) from observations where instr(body, ?) > 0 "
                                   "or instr(coalesce(title, ''), ?) > 0", (t, t)).fetchone()[0]
                       for t in toks_all)
        page_hits = sum(con.execute("select count(*) from pages where instr(coalesce(body, ''), ?) > 0 "
                                    "or instr(path, ?) > 0", (t, t)).fetchone()[0] for t in toks_all)
        sess_hits = sum(con.execute("select count(*) from sessions where id = ?",
                                    (uuid.UUID(s).bytes,)).fetchone()[0] for s in all_sessions())
    finally:
        con.close()
    res["live_nonce_hits"] = {"observations": obs_hits, "pages": page_hits}
    res["checks"]["no_nonce_in_live_db"] = obs_hits == 0 and page_hits == 0
    wiki_hits = 0
    toks = [t.encode() for t in toks_all]
    for path in (LIVE / "wiki").rglob("*"):
        if path.is_file() and ".git" not in path.parts:
            try:
                data = path.read_bytes()
            except OSError:
                continue
            wiki_hits += sum(1 for t in toks if t in data)
    res["live_wiki_nonce_hits"] = wiki_hits
    res["checks"]["no_nonce_in_live_wiki"] = wiki_hits == 0
    res["live_probe_session_rows"] = sess_hits
    res["checks"]["no_probe_session_in_live_db"] = sess_hits == 0
    res["nonces_checked"] = len(toks_all)
    res["sessions_checked"] = len(all_sessions())
    res["scratch_procs_alive"] = ai_procs()
    res["checks"]["no_scratch_procs"] = not res["scratch_procs_alive"]
    res["pass"] = all(res["checks"].values())
    emit(f"prod-compare-{a}-{b}", res)
    return 0 if res["pass"] else 1


def main():
    cmd = sys.argv[1]
    if cmd == "prod-snapshot":
        return cmd_prod_snapshot(sys.argv[2]) or 0
    if cmd == "install":
        return cmd_install()
    if cmd == "preflight":
        return cmd_preflight()
    if cmd == "backup":
        return cmd_backup()
    if cmd == "baseline":
        return cmd_baseline()
    if cmd == "rehearsal":
        return cmd_rehearsal()
    if cmd == "rollback-check":
        return cmd_rollback_check()
    if cmd == "prod-compare":
        return cmd_prod_compare(sys.argv[2], sys.argv[3])
    if cmd == "procs":
        print(json.dumps(san(ai_procs())))
        return 0
    raise SystemExit(f"unknown subcommand {cmd}")


if __name__ == "__main__":
    sys.exit(main())
