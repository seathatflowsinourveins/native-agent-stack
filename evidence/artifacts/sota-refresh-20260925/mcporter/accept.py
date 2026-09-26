#!/usr/bin/env python3
"""mcporter qualification harness, one arm per run: x = candidate 0.14.1, y = baseline 0.13.13.

Scope and safety (hard rules of the sota-refresh unit):
- Every daemon lives in a private MCPORTER_DAEMON_DIR under ~/.local/state/native-agent-stack/sota-refresh-20260925/mcporter/<arm>
  (0700). The shared per-user daemon namespace ~/.mcporter is never contacted, stopped or signalled.
- Scratch config: a copy of the host config limited to the servers under test. socraticode runs with
  SOCRATICODE_WATCHER=off + SOCRATICODE_AUTO_RESUME=off (no startup indexing, no watcher writes to production Qdrant);
  context-mode runs its server bundle inside bwrap with a read-only root and only this arm's private state writable
  (start.mjs, which self-heals ~/.claude files, is never launched); jcodemunch uses a private copy of ~/.code-index.
- A signal is sent only to a pid proven to belong to this arm: status over this arm's socket, the kernel's socket owner,
  this arm's metadata pid, the prefix cmdline and the snapshot cwd must all agree; children are tracked with start times.
"""
import hashlib
import json
import os
import pathlib
import re
import shlex
import shutil
import signal
import subprocess
import sys
import time

ARM = sys.argv[1]
VERSION = {"x": "0.14.1", "y": "0.13.13"}[ARM]
HOME = os.path.expanduser("~")
E = f"{HOME}/.local/share/codex-ecosystem"
PBIN = f"{E}/tools/mcporter-{VERSION}/bin"
DAEMON_MARK = f"/tools/mcporter-{VERSION}/lib/node_modules/mcporter/dist/cli.js daemon start --foreground"
IMPL = pathlib.Path(__file__).resolve().parent
SCRATCHPAD = str(IMPL.parents[2])
PRIV = f"{HOME}/.local/state/native-agent-stack/sota-refresh-20260925/mcporter"
AD = f"{PRIV}/{ARM}"
DD = f"{AD}/dd"
RUN = f"{DD}/daemon"
SOCK = f"{RUN}/user.sock"
META = f"{RUN}/user.json"
CFG = f"{AD}/mcporter.json"
CIDX = f"{AD}/code-index"
TMP = f"{AD}/tmp"
CMS = f"{AD}/cm"
SNAP = str(IMPL / "snap-7783682f")
MAIN = f"{HOME}/code/native-agent-stack"
RECEIPTS = f"{SNAP}/evidence/hosts/nativestack-5975wx-20260925"
PROD_CFG = f"{E}/config/mcporter.json"
CM_PLUGIN = f"{HOME}/.codex/plugins/cache/context-mode/context-mode/1.0.169"
RAW = IMPL / "raw" / ARM
REFUSAL = "Previous daemon exited unexpectedly; verify retirement of its transports before deliberate recovery. No replacement was launched."

UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)


def sanitize(s):
    s = (s or "").replace(SCRATCHPAD, "<scratchpad>").replace(HOME, "~")
    return UUID_RE.sub(lambda m: "<uuid:" + hashlib.sha256(m.group(0).lower().encode()).hexdigest()[:8] + ">", s)


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


ENV = dict(os.environ)
ENV["PATH"] = PBIN + ":" + ENV["PATH"]
ENV["MCPORTER_DAEMON_DIR"] = DD
ENV["SCRATCH_CFG"] = CFG
ENV["C"] = CFG
ENV["SCRATCH_CODE_INDEX"] = CIDX
ENV["CODE_INDEX_PATH"] = CIDX  # any jcodemunch invocation without an explicit path uses the arm-private copy
ENV["TMPDIR"] = TMP
for k in ("MCPORTER_CONFIG", "MCPORTER_NO_KEEPALIVE", "MCPORTER_DISABLE_KEEPALIVE"):
    ENV.pop(k, None)

RESULTS = []
TRACKED = {}  # pid -> start time of every daemon/descendant this arm created
REC = {"arm": ARM, "version": VERSION, "started_at": now(), "snapshot_rev": pathlib.Path(SNAP, ".snapshot-rev").read_text().strip()}


def sh(cmd, timeout=240, cwd=SNAP, extra_env=None):
    t0 = time.time()
    env = dict(ENV, **(extra_env or {}))
    p = subprocess.Popen(["bash", "-c", cmd], cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         text=True, start_new_session=True)
    try:
        out, err = p.communicate(timeout=timeout)
        rc = p.returncode
    except subprocess.TimeoutExpired:
        os.killpg(p.pid, signal.SIGTERM)  # the command's own process group only (daemons are detached sessions)
        try:
            out, err = p.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid, signal.SIGKILL)
            out, err = p.communicate()
        rc, err = 124, (err or "") + "\n[harness] TIMEOUT after %ss" % timeout
    return rc, out or "", err or "", time.time() - t0


def rec(name, cmd, rc, out, err, passed, wall, **extra):
    text = (out or "").strip()
    if (err or "").strip():
        text += "\n[stderr] " + err.strip()
    ex = sanitize(text)
    if len(ex) > 900:
        ex = ex[:560] + " ... " + ex[-300:]
    r = {"name": name, "arm": f"{ARM} ({VERSION})", "cmd": sanitize(cmd), "exit": rc, "output_excerpt": ex,
         "pass": bool(passed), "wall_s": round(wall, 1), "at_utc": now()}
    r.update(extra)
    RESULTS.append(r)
    idx = len(RESULTS)
    (RAW / f"{idx:02d}-{name}.out").write_text(sanitize(out))
    (RAW / f"{idx:02d}-{name}.err").write_text(sanitize(err))
    print(f"[{ARM}] {name}: exit={rc} pass={bool(passed)} wall={wall:.1f}s", flush=True)
    return r


# ---------------------------------------------------------------- process helpers (no environ reads)
def pstat(pid):
    try:
        s = pathlib.Path(f"/proc/{pid}/stat").read_text()
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        return None
    rp = s.rindex(")")
    f = s[rp + 2:].split()
    return {"ppid": int(f[1]), "start": int(f[19]), "comm": s[s.index("(") + 1:rp]}


def cmdline(pid):
    try:
        return pathlib.Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace").strip()
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        return None


def pcwd(pid):
    try:
        return os.readlink(f"/proc/{pid}/cwd")
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        return None


def alive(pid, start):
    st = pstat(pid)
    return st is not None and st["start"] == start


def descendants(root):
    kids = {}
    for p in (int(x) for x in os.listdir("/proc") if x.isdigit()):
        st = pstat(p)
        if st:
            kids.setdefault(st["ppid"], []).append((p, st["start"]))
    out, stack = [], [root]
    while stack:
        for c, start in kids.get(stack.pop(), []):
            out.append((c, start))
            stack.append(c)
    return out


def my_daemons():
    """Daemon processes of THIS arm: prefix daemon cmdline AND launched from this arm's snapshot cwd."""
    found = []
    for p in (int(x) for x in os.listdir("/proc") if x.isdigit()):
        c = cmdline(p) or ""
        if DAEMON_MARK in c and pcwd(p) == SNAP:
            st = pstat(p)
            if st:
                found.append((p, st["start"]))
    return found


def socket_owners(path):
    rc, out, err, _ = sh("ss -xlpn", timeout=30, cwd="/")
    pids = set()
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[4] == path:
            pids.update(int(x) for x in re.findall(r"pid=(\d+)", line))
    return pids


def listeners_under_dd():
    rc, out, err, _ = sh("ss -xlpn", timeout=30, cwd="/")
    return [sanitize(l.split()[4]) for l in out.splitlines() if len(l.split()) >= 5 and l.split()[4].startswith(DD)]


def status():
    rc, out, err, _ = sh("mcporter daemon status --json", timeout=60)
    try:
        return json.loads(out)
    except Exception:  # noqa: BLE001
        return {"_raw": sanitize(out.strip() + " " + err.strip())[:200], "_exit": rc}


def track():
    for p, s in my_daemons():
        TRACKED[p] = s
        for c, cs in descendants(p):
            TRACKED[c] = cs


def owned_daemon():
    s = status()
    d = s.get("pid") if isinstance(s, dict) else None
    ev = {"status_pid": d, "status_socket_is_arm_socket": isinstance(s, dict) and s.get("socketPath") == SOCK,
          "protocolVersion": s.get("protocolVersion") if isinstance(s, dict) else None}
    if not d:
        ev["owned"] = False
        return None, ev
    try:
        ev["metadata_pid"] = json.loads(pathlib.Path(META).read_text()).get("pid")
    except Exception:  # noqa: BLE001
        ev["metadata_pid"] = None
    ev["kernel_socket_owner_pids"] = sorted(socket_owners(SOCK))
    ev["cmdline_is_arm_prefix_daemon"] = DAEMON_MARK in (cmdline(d) or "")
    ev["cwd_is_arm_snapshot"] = pcwd(d) == SNAP
    ev["owned"] = (ev["status_socket_is_arm_socket"] and ev["metadata_pid"] == d and ev["kernel_socket_owner_pids"] == [d]
                   and ev["cmdline_is_arm_prefix_daemon"] and ev["cwd_is_arm_snapshot"])
    track()
    return (d if ev["owned"] else None), ev


def wait_dead(pairs, secs=15):
    t0 = time.time()
    while time.time() - t0 < secs:
        if not any(alive(p, s) for p, s in pairs):
            return True
        time.sleep(0.25)
    return not any(alive(p, s) for p, s in pairs)


PROBE_ARGS = json.dumps({"language": "javascript", "code": 'console.log("PPID="+process.ppid)'})
PROBE = f'mcporter --config "$C" call context-mode.ctx_execute --args {shlex.quote(PROBE_ARGS)} --output text --no-oauth'


def probe(timeout=240):
    rc, out, err, wall = sh(PROBE, timeout=timeout)
    m = re.search(r"PPID=(\d+)", out)
    track()
    return rc, out, err, wall, (int(m.group(1)) if m else None)


# ---------------------------------------------------------------- setup
def setup():
    assert not my_daemons(), "a daemon of this arm is already running"
    if os.path.exists(AD):
        assert not listeners_under_dd(), "listener still bound under the arm daemon dir"
        shutil.rmtree(AD)
    for d in (AD, DD, TMP, CMS, f"{CMS}/cm", f"{CMS}/data", f"{CMS}/claude", f"{CMS}/codex"):
        os.makedirs(d, mode=0o700, exist_ok=True)
        os.chmod(d, 0o700)
    # private copy of the jcodemunch index; the live process registry of other sessions is left out
    shutil.copytree(f"{HOME}/.code-index", CIDX, ignore=shutil.ignore_patterns("_processes"))
    RAW.mkdir(parents=True, exist_ok=True)
    for f in RAW.glob("*"):
        f.unlink()
    prod = json.loads(pathlib.Path(PROD_CFG).read_text())
    ps = prod["mcpServers"]
    socr = json.loads(json.dumps(ps["socraticode"]))
    socr["env"].update({"SOCRATICODE_WATCHER": "off", "SOCRATICODE_AUTO_RESUME": "off", "TMPDIR": TMP})
    jc = json.loads(json.dumps(ps["jcodemunch"]))
    jc.setdefault("env", {}).update({"CODE_INDEX_PATH": CIDX, "TMPDIR": TMP})
    cmp_ = ps["context-mode"]
    cwd = cmp_.get("cwd", MAIN)
    cm = {"command": "bwrap",
          "args": ["--ro-bind", "/", "/", "--dev", "/dev", "--proc", "/proc", "--tmpfs", "/tmp", "--bind", CMS, CMS,
                   "--die-with-parent", "--chdir", cwd, "--", "node", f"{CM_PLUGIN}/server.bundle.mjs"],
          "cwd": cwd,
          "env": {"CODEX_HOME": f"{CMS}/codex", "CONTEXT_MODE_PLATFORM": cmp_["env"]["CONTEXT_MODE_PLATFORM"],
                  "CONTEXT_MODE_PROJECT_DIR": cmp_["env"]["CONTEXT_MODE_PROJECT_DIR"], "CONTEXT_MODE_DIR": f"{CMS}/cm",
                  "CONTEXT_MODE_DATA_DIR": f"{CMS}/data", "CLAUDE_CONFIG_DIR": f"{CMS}/claude", "TMPDIR": "/tmp"},
          "lifecycle": cmp_.get("lifecycle", "keep-alive")}
    cfg = {"imports": [], "mcpServers": {"context-mode": cm, "ai-memory": ps["ai-memory"], "socraticode": socr, "jcodemunch": jc}}
    pathlib.Path(CFG).write_text(json.dumps(cfg, indent=1) + "\n")
    os.chmod(CFG, 0o600)
    (IMPL / f"scratch-config-{ARM}.sanitized.json").write_text(sanitize(json.dumps(cfg, indent=1)) + "\n")
    REC["scratch_config_vs_host_config"] = {
        "servers_kept": sorted(cfg["mcpServers"]), "servers_dropped": sorted(set(ps) - set(cfg["mcpServers"])),
        "socraticode_env_overrides": {"SOCRATICODE_WATCHER": [ps["socraticode"]["env"].get("SOCRATICODE_WATCHER"), "off"],
                                      "SOCRATICODE_AUTO_RESUME": [ps["socraticode"]["env"].get("SOCRATICODE_AUTO_RESUME"), "off"],
                                      "TMPDIR": "arm-private"},
        "jcodemunch_env_overrides": {"CODE_INDEX_PATH": "arm-private copy of ~/.code-index (without _processes)"},
        "context_mode": "host start.mjs replaced by bwrap(ro root, arm-private state rw, die-with-parent) + node server.bundle.mjs; "
                        "CODEX_HOME/CLAUDE_CONFIG_DIR/CONTEXT_MODE_DIR/CONTEXT_MODE_DATA_DIR arm-private; platform and project dir as host",
        "ai_memory": "unchanged (baseUrl)",
    }
    s = status()
    REC["namespace_status_before"] = s
    return


def cross(name, cond, detail, **extra):
    r = {"name": name, "arm": f"{ARM} ({VERSION})", "cmd": "(harness check)", "exit": 0 if cond else 1,
         "output_excerpt": sanitize(detail)[:900], "pass": bool(cond), "wall_s": 0.0, "at_utc": now()}
    r.update(extra)
    RESULTS.append(r)
    print(f"[{ARM}] {name}: pass={bool(cond)} {sanitize(detail)[:160]}", flush=True)


# ---------------------------------------------------------------- steps
def run_steps():
    # 1. resolution
    rc, out, err, w = sh("command -v mcporter")
    rec("S1-command-v", "command -v mcporter", rc, out, err, rc == 0 and out.strip() == f"{PBIN}/mcporter", w)

    # mcporter install receipt, verbatim
    rj = json.loads(pathlib.Path(f"{RECEIPTS}/nativestack-5975wx-20260925--mcporter--install--20260925.json").read_text())
    for i, c in enumerate(rj["commands"]):
        rc, out, err, w = sh(c["cmd"])
        ok = rc == 0 and (f"resolves: {PBIN}/mcporter" in out if i == 0 else out.strip() == VERSION)
        rec(f"R-mcporter-install-{i}", c["cmd"], rc, out, err, ok, w, receipt="nativestack-5975wx-20260925--mcporter--install--20260925.json", substitutions=[])

    # 2. socraticode use receipt -2, config path substituted by the scratch config
    sj = json.loads(pathlib.Path(f"{RECEIPTS}/nativestack-5975wx-20260925--socraticode--use--20260925-2.json").read_text())
    orig = 'C="$HOME/.local/share/codex-ecosystem/config/mcporter.json"'
    for i, c in enumerate(sj["commands"]):
        assert orig in c["cmd"], "receipt command changed"
        cmd = c["cmd"].replace(orig, 'C="$SCRATCH_CFG"')
        rc, out, err, w = sh(cmd, timeout=300)
        ok = rc == 0 and (f"mcporter {VERSION}" in out if i == 0 else True)
        rec(f"R-socraticode-use-{i}", cmd, rc, out, err, ok, w, receipt="nativestack-5975wx-20260925--socraticode--use--20260925-2.json",
            substitutions=[orig + ' -> C="$SCRATCH_CFG"'])
    track()

    # 3. context-mode doctor through the daemon
    cmd = 'mcporter --config "$C" call context-mode.ctx_doctor --args \'{}\' --output text --no-oauth'
    rc, out, err, w = sh(cmd, timeout=300)
    rec("S3-ctx_doctor", cmd, rc, out, err, rc == 0 and out.strip() != "", w)

    # 4. per-call servers: list + tool-name sets
    for srv in ("ai-memory", "jcodemunch"):
        cmd = f'mcporter --config "$C" list {srv} --json --no-oauth'
        rc, out, err, w = sh(cmd, timeout=240)
        try:
            d = json.loads(out)
            names, st = sorted(t["name"] for t in d.get("tools", [])), d.get("status")
        except Exception:  # noqa: BLE001
            names, st = None, None
        rec(f"S4-list-{srv}", cmd, rc, out, err, rc == 0 and st == "ok" and bool(names), w, status=st,
            tool_count=len(names or []), tool_names_sha256=hashlib.sha256(json.dumps(names).encode()).hexdigest()[:16], tool_names=names)

    # 5. token-report one-off stdio form (index path -> private copy)
    cmd = ('mcporter call --stdio "$(command -v jcodemunch-mcp)" --env CODE_INDEX_PATH=$SCRATCH_CODE_INDEX --env JCODEMUNCH_SHARE_SAVINGS=0 '
           '--name jcodemunch --tool order --args \'{"action":"get_session_stats","args":{}}\' --output json --no-oauth')
    rc, out, err, w = sh(cmd, timeout=240)
    rec("S5-token-report-oneoff", cmd, rc, out, err, rc == 0 and "session_calls" in out, w,
        substitutions=["CODE_INDEX_PATH=$HOME/.code-index -> $SCRATCH_CODE_INDEX (arm-private copy)"])

    # retained jcodemunch-mcp and context-mode use receipts (they drive mcporter's one-off --stdio path)
    jj = json.loads(pathlib.Path(f"{RECEIPTS}/nativestack-5975wx-20260925--jcodemunch-mcp--use--20260925-2.json").read_text())
    origj = "CODE_INDEX_PATH=$HOME/.code-index"
    for i, c in enumerate(jj["commands"]):
        assert origj in c["cmd"], "receipt command changed"
        cmd = c["cmd"].replace(origj, "CODE_INDEX_PATH=$SCRATCH_CODE_INDEX")
        rc, out, err, w = sh(cmd, timeout=300)
        rec(f"R-jcodemunch-use-{i}", cmd, rc, out, err, rc == 0, w, receipt="nativestack-5975wx-20260925--jcodemunch-mcp--use--20260925-2.json",
            substitutions=[origj + " -> CODE_INDEX_PATH=$SCRATCH_CODE_INDEX"])
    # This receipt builds its own bwrap sandbox (read-only root, private tmpfs /tmp, only "$d" writable). With TMPDIR
    # unset (production) the server's temp files land on that private tmpfs. Here TMPDIR is a scratchpad directory:
    # the host-side mktemp stays in the scratchpad, and inside the sandbox the same path lies on the private tmpfs.
    rtmp = str(IMPL / f"tmp-{ARM}")
    os.makedirs(rtmp, mode=0o700, exist_ok=True)
    cj = json.loads(pathlib.Path(f"{RECEIPTS}/nativestack-5975wx-20260925--context-mode--use--20260925-2.json").read_text())
    for i, c in enumerate(cj["commands"]):
        rc, out, err, w = sh(c["cmd"], timeout=300, extra_env={"TMPDIR": rtmp})
        ok = rc == 0 and (f"mcporter {VERSION}" in out if i == 0 else "asserted: exact match" in out)
        rec(f"R-context-mode-use-{i}", c["cmd"], rc, out, err, ok, w, receipt="nativestack-5975wx-20260925--context-mode--use--20260925-2.json",
            substitutions=["command verbatim; TMPDIR=<scratchpad>/sota-refresh/impl/mcporter/tmp-<arm> (host mktemp stays in the scratchpad; "
                           "inside the receipt's own sandbox the path is on its private tmpfs, like TMPDIR-unset /tmp in production)"])
    leftover_tmp = sorted(os.listdir(rtmp))
    cross("R-context-mode-use-tmp-clean", not leftover_tmp, json.dumps({"entries_left_in_receipt_tmpdir": leftover_tmp}))

    # 6. daemon status check (review), keep-alive persistence across a repeated socraticode health call
    s6py = ('import json,os,sys;d=json.load(sys.stdin);c=open("/proc/%d/cmdline"%d["pid"]).read().replace(chr(0)," ");'
            'ok=d["protocolVersion"]==3 and d["socketPath"].startswith(os.environ["MCPORTER_DAEMON_DIR"]) and "/tools/mcporter-' + VERSION +
            '/" in c and len(d["servers"])>=2 and all(s["connected"] and s["activeCalls"]==0 for s in d["servers"]);'
            'print(sorted((s["connectionId"],s["connectionGeneration"]) for s in d["servers"]));sys.exit(0 if ok else 1)')
    s6 = "mcporter daemon status --json | python3 -c " + shlex.quote(s6py)
    rc1, out1, err1, w = sh(s6, timeout=60)
    rec("S6a-daemon-status-check", s6, rc1, out1, err1, rc1 == 0, w)
    hc = 'mcporter --config "$C" call socraticode.codebase_health --args \'{}\' --output text --no-oauth'
    rc, out, err, w = sh(hc, timeout=240)
    rec("S6b-repeat-socraticode-health", hc, rc, out, err, rc == 0, w)
    rc2, out2, err2, w = sh(s6, timeout=60)
    rec("S6c-daemon-status-recheck", s6, rc2, out2, err2, rc2 == 0 and out2.strip() == out1.strip() and out1.strip() != "", w,
        identical_connection_list=out2.strip() == out1.strip())
    d0, own0 = owned_daemon()
    cross("S6d-daemon-ownership", d0 is not None, json.dumps(own0), ownership=own0)

    # A. retained bridge calls
    fpath = f"{MAIN}/AGENTS.md"
    b = pathlib.Path(fpath).read_bytes()
    exp = f"BYTES={len(b)} SHA256={hashlib.sha256(b).hexdigest()}"
    a1 = json.dumps({"path": fpath, "language": "python",
                     "code": 'import hashlib\nb=FILE_CONTENT.encode()\nprint("BYTES=%d SHA256=%s" % (len(b), hashlib.sha256(b).hexdigest()))'})
    cmd = f'mcporter --config "$C" call context-mode.ctx_execute_file --args {shlex.quote(a1)} --output json --no-oauth'
    rc, out, err, w = sh(cmd, timeout=240)
    rec("A1-ctx_execute_file-project-read", cmd, rc, out, err, rc == 0 and exp in out, w, expected=exp)
    cmd = 'mcporter --config "$C" call context-mode.ctx_execute --args \'{"language":"javascript","code":"console.log(6*7)"}\' --output text --no-oauth'
    rc, out, err, w = sh(cmd, timeout=240)
    rec("A2-ctx_execute-42", cmd, rc, out, err, rc == 0 and re.search(r"(^|\D)42(\D|$)", out) is not None, w)
    r1 = probe()
    r2 = probe()
    D, own = owned_daemon()
    chain, cur, reached = [], r1[4], False
    for _ in range(12):
        st = pstat(cur) if cur else None
        if not st:
            break
        chain.append(f"{cur}:{st['comm']}")
        if cur == D:
            reached = True
            break
        cur = st["ppid"]
    ok = r1[0] == 0 and r2[0] == 0 and r1[4] is not None and r1[4] == r2[4] and reached and D is not None
    rec("A3-probe-persistence-and-ppid-chain", PROBE + "  (x2)", r1[0] if r1[0] else r2[0], r1[1] + r2[1], r1[2] + r2[2], ok, r1[3] + r2[3],
        ppid_first=r1[4], ppid_second=r2[4], ppid_chain_to_daemon=chain, reached_daemon=reached, daemon_pid=D)
    cmd = 'mcporter --config "$C" call ai-memory.memory_status --args \'{"workspace":"local","project":"native-agent-stack"}\' --output json --no-oauth'
    rc, out, err, w = sh(cmd, timeout=240)
    try:
        dj = json.loads(out)
        inner = dj
        if isinstance(dj, dict) and "content" in dj:
            inner = json.loads(dj["content"][0]["text"])
        keys = sorted(inner.keys()) if isinstance(inner, dict) else None
    except Exception:  # noqa: BLE001
        keys = None
    rec("A4-ai-memory-status", cmd, rc, out, err, rc == 0 and bool(keys), w, top_level_keys=keys)

    # B1. restart and cleanup
    rP = probe()
    D, own = owned_daemon()
    P = rP[4]
    Ps = pstat(P)["start"] if P and pstat(P) else None
    Ds = pstat(D)["start"] if D and pstat(D) else None
    rc, out, err, w = sh("mcporter daemon stop", timeout=60)
    gone = wait_dead([(D, Ds), (P, Ps)]) if D and P else False
    sock_gone, meta_gone = not os.path.exists(SOCK), not os.path.exists(META)
    rec("B1a-daemon-stop-retires-daemon-and-server", "mcporter daemon stop", rc, out, err,
        rc == 0 and D is not None and gone and sock_gone and meta_gone, w, daemon_pid=D, server_pid=P, both_gone=gone,
        socket_removed=sock_gone, metadata_removed=meta_gone, ownership_before=own)
    r = probe()
    D2, own2 = owned_daemon()
    rec("B1b-next-probe-relaunches", PROBE, r[0], r[1], r[2], r[0] == 0 and r[4] not in (None, P) and D2 not in (None, D), r[3],
        new_ppid=r[4], new_daemon_pid=D2)
    rc, out, err, w = sh("mcporter daemon restart", timeout=120)
    rec("B1c-daemon-restart", "mcporter daemon restart", rc, out, err, rc == 0, w)
    r = probe()
    D3, own3 = owned_daemon()
    rec("B1d-probe-after-restart", PROBE, r[0], r[1], r[2], r[0] == 0 and D3 not in (None, D2), r[3], daemon_pid_before=D2, daemon_pid_after=D3)

    # B2. stale metadata after SIGKILL
    rW = probe()
    D, own = owned_daemon()
    if D is None:
        cross("B2-precondition-owned-daemon", False, json.dumps(own))
    else:
        Ds = pstat(D)["start"]
        kids = [(p, s) for p, s in descendants(D) if (pstat(p) or {}).get("ppid") == D]
        allk = descendants(D)
        for p, s in allk:
            TRACKED[p] = s
        TRACKED[D] = Ds
        assert alive(D, Ds) and DAEMON_MARK in (cmdline(D) or "") and pcwd(D) == SNAP
        os.kill(D, signal.SIGKILL)
        time.sleep(1)
        r = probe(timeout=120)
        combined = r[1] + r[2]
        rec("B2a-probe-refuses-after-daemon-sigkill", PROBE, r[0], r[1], r[2], r[0] != 0 and REFUSAL in combined, r[3],
            killed_daemon_pid=D, direct_children=[p for p, _ in kids], ownership_before_kill=own, refusal_printed=REFUSAL in combined)
        alive_before_term = [(p, s) for p, s in allk if alive(p, s)]
        for p, s in alive_before_term:
            if alive(p, s):
                os.kill(p, signal.SIGTERM)
        ok_term = wait_dead(alive_before_term, 15)
        escalated = []
        if not ok_term:
            for p, s in alive_before_term:
                if alive(p, s):
                    os.kill(p, signal.SIGKILL)
                    escalated.append(p)
            wait_dead(alive_before_term, 5)
        all_gone = not any(alive(p, s) for p, s in allk)
        archived = False
        if os.path.exists(META):
            os.rename(META, META + ".stale-archived")
            archived = True
        cross("B2b-retire-orphans-and-archive-metadata", all_gone and archived,
              json.dumps({"descendants_alive_after_kill": [p for p, _ in alive_before_term], "terminated_with_TERM": ok_term,
                          "escalated_to_KILL": escalated, "all_gone": all_gone, "metadata_archived": archived}))
        cmd = 'mcporter --config "$C" daemon start'
        rc, out, err, w = sh(cmd, timeout=120)
        rec("B2c-deliberate-daemon-start", cmd, rc, out, err, rc == 0 and "Single-user daemon started." in out, w)
        cmd = 'mcporter --config "$C" list context-mode --brief --no-oauth'
        rc, out, err, w = sh(cmd, timeout=240)
        tools = sorted(set(re.findall(r"\b(ctx_[a-z_]+)\b", out)))
        rec("B2d-list-context-mode-brief", cmd, rc, out, err, rc == 0 and out.strip() != "", w, brief_tool_names=tools,
            brief_output_sha256=hashlib.sha256(sanitize(out).encode()).hexdigest()[:16])
        cmd = 'mcporter --config "$C" call context-mode.ctx_execute --args \'{"language":"python","code":"print(\\"bridge-recovered\\")"}\' --output text --no-oauth'
        rc, out, err, w = sh(cmd, timeout=240)
        rec("B2e-bridge-recovered", cmd, rc, out, err, rc == 0 and "bridge-recovered" in out, w)
        track()

    # B3. held startup lock
    D, own = owned_daemon()
    Ds = pstat(D)["start"] if D and pstat(D) else None
    rc, out, err, w = sh("mcporter daemon stop", timeout=60)
    stopped = wait_dead([(D, Ds)]) if D else True
    moved = []
    for f in sorted(pathlib.Path(RUN).glob("user.json*")):
        f.rename(pathlib.Path(RUN) / f"archived-before-lock-stage.{f.name}")
        moved.append(f.name)
    holder = subprocess.Popen(["sleep", "95"], start_new_session=True, env=ENV, cwd=AD)
    TRACKED[holder.pid] = pstat(holder.pid)["start"]
    t_hold = time.time()
    pathlib.Path(RUN, "user.json.lock").write_text(f"{holder.pid}\n{now()}\n")
    rec("B3a-stop-and-hold-lock", "mcporter daemon stop; mv user.json* aside; sleep 95 & lock=<holder pid, time>", rc, out, err,
        rc == 0 and stopped, w, moved_aside=moved, holder_pid=holder.pid)
    r = probe(timeout=200)
    held_alive = holder.poll() is None
    track()
    rec("B3b-probe-while-lock-held-fails", PROBE, r[0], r[1], r[2], r[0] != 0 and held_alive, r[3], holder_alive_after_probe=held_alive)
    holder.wait(timeout=200)  # natural exit, no signal
    held_for = round(time.time() - t_hold, 1)
    time.sleep(1)
    r = probe(timeout=200)
    rec("B3c-probe-after-holder-exit-recovers", PROBE, r[0], r[1], r[2], r[0] == 0 and r[4] is not None, r[3],
        holder_exit_after_s=held_for, holder_returncode=holder.returncode)

    # Finish
    track()
    rc, out, err, w = sh("mcporter daemon stop", timeout=60)
    ok_dead = wait_dead(list(TRACKED.items()), 15)
    left = [p for p, s in TRACKED.items() if alive(p, s)]
    mine = my_daemons()
    socks = listeners_under_dd()
    rec("F-daemon-stop-no-leftovers", "mcporter daemon stop", rc, out, err, rc == 0 and ok_dead and not left and not mine and not socks, w,
        tracked_processes=len(TRACKED), leftover_tracked=left, arm_daemons_running=mine, listeners_under_daemon_dir=socks)


def cleanup():
    """Always leave nothing running: stop this arm's daemon, then TERM/KILL only tracked processes of this arm."""
    notes = {}
    try:
        rc, out, err, _ = sh("mcporter daemon stop", timeout=60)
        notes["final_stop_exit"] = rc
    except Exception as e:  # noqa: BLE001
        notes["final_stop_error"] = str(e)[:200]
    track()
    live = [(p, s) for p, s in TRACKED.items() if alive(p, s)]
    for p, s in live:
        if alive(p, s):
            os.kill(p, signal.SIGTERM)
    if not wait_dead(live, 10):
        for p, s in live:
            if alive(p, s):
                os.kill(p, signal.SIGKILL)
        wait_dead(live, 5)
    notes["terminated_in_cleanup"] = [p for p, _ in live]
    notes["alive_after_cleanup"] = [p for p, s in TRACKED.items() if alive(p, s)]
    notes["arm_daemons_after_cleanup"] = my_daemons()
    notes["listeners_under_daemon_dir_after_cleanup"] = listeners_under_dd()
    return notes


if __name__ == "__main__":
    try:
        setup()
        run_steps()
    except Exception as e:  # noqa: BLE001
        REC["harness_exception"] = sanitize(repr(e))[:500]
        print("HARNESS EXCEPTION:", REC["harness_exception"], flush=True)
    finally:
        REC["cleanup"] = cleanup()
        REC["ended_at"] = now()
        REC["steps"] = RESULTS
        REC["passed"] = all(r["pass"] for r in RESULTS) and "harness_exception" not in REC
        (IMPL / f"results-{ARM}.json").write_text(sanitize(json.dumps(REC, indent=1)) + "\n")
        print(f"[{ARM}] DONE passed={REC['passed']} steps={len(RESULTS)} failed={[r['name'] for r in RESULTS if not r['pass']]}", flush=True)
        print(f"[{ARM}] cleanup={REC['cleanup']}", flush=True)
