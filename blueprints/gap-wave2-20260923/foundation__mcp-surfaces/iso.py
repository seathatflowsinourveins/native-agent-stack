#!/usr/bin/env python3
"""Isolated MCP fixture for the wave-2 mcp-surfaces checks.

Starts owned, loopback-only instances of the host's installed MCP servers with temp state, writes an
mcporter config that mirrors the host config (same binaries/args) but points at the owned state, and
provides a subprocess runner that records argv, exit code, elapsed time and sanitized output.

Never contacts the shared mcporter daemon, the live ai-memory (127.0.0.1:49374) or the live Qdrant
(127.0.0.1:16333): every child gets a temp HOME/XDG tree, MCPORTER_DAEMON_DIR, AI_MEMORY_SERVER_URL and
QDRANT_URL pointing at owned instances.
"""
import hashlib
import json
import re
import os
import pathlib
import shutil
import signal
import socket
import subprocess
import time
import urllib.request

REAL_HOME = str(pathlib.Path.home())
CACHE = pathlib.Path(REAL_HOME) / ".cache/gap-wave2-20260923/mcp-surfaces"
ECO = pathlib.Path(REAL_HOME) / ".local/share/codex-ecosystem"
NODE = str(ECO / "bin/node")
BINS = {
    "mcporter-installed-0.13.13": str(ECO / "bin/mcporter"),
    "mcporter-0.13.13": str(CACHE / "mcporter-0.13.13/node_modules/.bin/mcporter"),
    "mcporter-0.14.0": str(CACHE / "mcporter-0.14.0/node_modules/.bin/mcporter"),
    "wong2-mcp-cli-2.0.0": str(CACHE / "wong2-mcp-cli-2.0.0/node_modules/.bin/mcp-cli"),
    "inspector": str(ECO / "bin/mcp-inspector"),
}
CONTEXT_MODE_NPM = str(ECO / "tools/context-mode-1.0.169/node_modules/context-mode/cli.bundle.mjs")
JCODEMUNCH = str(ECO / "bin/jcodemunch-mcp")
CBM = str(ECO / "tools/codebase-memory-mcp-0.11.0.removed-20260921/codebase-memory-mcp")
SOCRATICODE = str(ECO / "tools/socraticode-1.14.0/lib/node_modules/socraticode/dist/index.js")
QDRANT = str(ECO / "bin/qdrant")
AI_MEMORY = str(ECO / "bin/ai-memory")
LIVE = {"ai-memory": 49374, "qdrant": 16333}
SHARED_DAEMON_DIR = pathlib.Path(REAL_HOME) / ".mcporter/daemon"


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def sanitize(text):
    text = text.replace(REAL_HOME, "$HOME")
    return re.sub(r"/mnt/([a-z])/Users/[^/\s\"']+", r"/mnt/\1/Users/$WINUSER", text)


def sha(b):
    return hashlib.sha256(b if isinstance(b, bytes) else b.encode()).hexdigest()


def socket_probe(path):
    """AF_UNIX connect probe: 'connected' or the error. Pathname sockets ignore network namespaces, so this is
    the check that can detect a reachable daemon socket."""
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(2)
    try:
        s.connect(str(path))
        return "connected"
    except OSError as e:
        return f"{type(e).__name__}: {e.strerror}"
    finally:
        s.close()


def tcp_probe(port):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            return "connected"
    except OSError as e:
        return f"{type(e).__name__}: {e.strerror}"


def enforcement_probe():
    """Run inside enforce.py's namespace: the shared daemon socket path must not exist (empty tmpfs over
    $HOME/.mcporter) and the live loopback ports must be unreachable (fresh network namespace)."""
    d = SHARED_DAEMON_DIR.parent
    return {"shared_socket": socket_probe(SHARED_DAEMON_DIR / "user.sock"),
            "shared_dir_entries": sorted(os.listdir(d)) if d.exists() else "absent",
            "live_tcp": {str(p): tcp_probe(p) for p in (49374, 16333)}}


def shared_daemon_snapshot():
    """stat() only: pid from metadata, socket inode and metadata mtime of the shared daemon."""
    snap = {}
    meta = SHARED_DAEMON_DIR / "user.json"
    sock = SHARED_DAEMON_DIR / "user.sock"
    try:
        st = meta.stat()
        snap["metadata_mtime_ns"] = st.st_mtime_ns
        snap["metadata_pid"] = json.loads(meta.read_text()).get("pid")
    except FileNotFoundError:
        snap["metadata"] = "absent"
    try:
        st = sock.stat()
        snap["socket_inode"] = st.st_ino
    except FileNotFoundError:
        snap["socket"] = "absent"
    pid = snap.get("metadata_pid")
    snap["metadata_pid_alive"] = bool(pid) and os.path.exists(f"/proc/{pid}")
    return snap


class Fixture:
    def __init__(self, name):
        stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        self.root = CACHE / "runs" / f"{name}-{stamp}"
        self.home = self.root / "home"
        # Unix socket paths are limited to 108 bytes (sun_path): daemon dirs live on a short path.
        self.short = CACHE / "d" / f"{name[:6]}{stamp[9:15]}"
        self.short.mkdir(parents=True, exist_ok=True)
        for d in ["home/.config", "home/.local/share", "home/.local/state", "home/.cache", "daemon", "state", "project"]:
            (self.root / d).mkdir(parents=True, exist_ok=True)
        self.procs = {}
        self.ports = {}
        self.env = {
            "HOME": str(self.home),
            "USER": os.environ.get("USER", "user"),
            "LANG": "C.UTF-8",
            "PATH": f"{ECO}/bin:/usr/local/bin:/usr/bin:/bin",
            "XDG_CONFIG_HOME": str(self.home / ".config"),
            "XDG_DATA_HOME": str(self.home / ".local/share"),
            "XDG_STATE_HOME": str(self.home / ".local/state"),
            "XDG_CACHE_HOME": str(self.home / ".cache"),
            "MCPORTER_DAEMON_DIR": str(self.short / "daemon"),
            "MCP_AUTO_OPEN_ENABLED": "false",
            "NO_UPDATE_NOTIFIER": "1",
            "npm_config_update_notifier": "false",
            "RTK_TELEMETRY_DISABLED": "1",
        }

    # ---- owned services -------------------------------------------------
    def start_ai_memory(self):
        port = free_port()
        data = self.root / "state/ai-memory"
        data.mkdir(parents=True, exist_ok=True)
        env = dict(self.env, AI_MEMORY_DATA_DIR=str(data))
        log = open(self.root / "state/ai-memory.log", "wb")
        p = subprocess.Popen(
            [AI_MEMORY, "serve", "--transport", "http", "--bind", f"127.0.0.1:{port}", "--data-dir", str(data), "--no-watcher",
             # auto-creates the retained call's workspace/project in THIS owned temp store only
             "--workspace", "agent-lab", "--project", "agent-lab"],
            env=env, stdout=log, stderr=subprocess.STDOUT, cwd=self.root, start_new_session=True,
        )
        self.procs["ai-memory"] = p
        self.ports["ai-memory"] = port
        self.env["AI_MEMORY_SERVER_URL"] = f"http://127.0.0.1:{port}"
        self.env["AI_MEMORY_DATA_DIR"] = str(data)
        self._wait_tcp(port, "ai-memory")
        return port

    def start_qdrant(self):
        http, grpc = free_port(), free_port()
        qd = self.root / "state/qdrant"
        qd.mkdir(parents=True, exist_ok=True)
        env = dict(self.env,
                   QDRANT__SERVICE__HOST="127.0.0.1", QDRANT__SERVICE__HTTP_PORT=str(http),
                   QDRANT__SERVICE__GRPC_PORT=str(grpc), QDRANT__STORAGE__STORAGE_PATH=str(qd / "storage"),
                   QDRANT__STORAGE__SNAPSHOTS_PATH=str(qd / "snapshots"), QDRANT__TELEMETRY_DISABLED="true")
        log = open(self.root / "state/qdrant.log", "wb")
        p = subprocess.Popen([QDRANT], env=env, stdout=log, stderr=subprocess.STDOUT, cwd=qd, start_new_session=True)
        self.procs["qdrant"] = p
        self.ports["qdrant"] = http
        self._wait_tcp(http, "qdrant")
        return http

    def _wait_tcp(self, port, name, timeout=60):
        assert port not in LIVE.values(), f"refusing live port {port}"
        end = time.time() + timeout
        while time.time() < end:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=1):
                    return
            except OSError:
                if self.procs[name].poll() is not None:
                    raise RuntimeError(f"{name} exited early rc={self.procs[name].returncode}")
                time.sleep(0.2)
        raise RuntimeError(f"{name} not listening on {port}")

    # ---- configs ---------------------------------------------------------
    def project_fixture(self):
        """Small owned project: a copy of the retained search_graph target file plus a text file."""
        proj = self.root / "project"
        src = pathlib.Path(REAL_HOME) / "code/agent-lab/tools/ecosystem/linux-usage-report.cjs"
        (proj / "tools/ecosystem").mkdir(parents=True, exist_ok=True)
        shutil.copy(src, proj / "tools/ecosystem/linux-usage-report.cjs")
        (proj / "notes.md").write_text("# fixture\nretained bridge probe file\n")
        return proj

    def server_defs(self, project):
        """Mirror of $HOME/codex-ecosystem/config/mcporter.json (same commands/args) with owned state,
        plus the two retained servers no longer in that config (codebase-memory, jcodemunch)."""
        qdrant_url = f"http://127.0.0.1:{self.ports['qdrant']}" if "qdrant" in self.ports else "http://127.0.0.1:9"
        # Every stdio server gets the isolation variables explicitly: some clients (MCP SDK
        # StdioClientTransport with an env map) pass ONLY the configured env, so a missing HOME would
        # make the server fall back to the real passwd home.
        base = {k: self.env[k] for k in ("HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME", "XDG_CACHE_HOME", "PATH", "LANG")}
        defs = {
            "context-mode": {
                "command": NODE, "args": [CONTEXT_MODE_NPM], "cwd": str(project),
                "env": {"CONTEXT_MODE_PLATFORM": "codex", "CODEX_HOME": str(self.home / ".codex"),
                        "CONTEXT_MODE_PROJECT_DIR": str(project)},
                "lifecycle": "keep-alive",
            },
            "ai-memory": {"baseUrl": f"http://127.0.0.1:{self.ports.get('ai-memory', 9)}/mcp"},
            "socraticode": {
                "command": NODE, "args": [SOCRATICODE], "cwd": str(project), "lifecycle": "ephemeral",
                "env": {
                    "QDRANT_MODE": "external", "QDRANT_URL": qdrant_url, "EMBEDDING_PROVIDER": "lmstudio",
                    "LMSTUDIO_URL": "http://127.0.0.1:8231/v1", "EMBEDDING_MODEL": "nvidia/Nemotron-3-Embed-1B-BF16",
                    "EMBEDDING_DIMENSIONS": "2048", "EMBEDDING_CONTEXT_LENGTH": "4096",
                    "EMBEDDING_QUERY_PREFIX": "query: ", "EMBEDDING_DOCUMENT_PREFIX": "passage: ",
                    "EMBEDDING_DOCUMENT_INCLUDE_PATH": "true", "RESPECT_GITIGNORE": "true", "INCLUDE_DOT_FILES": "false",
                    "SOCRATICODE_WATCHER": "off", "SOCRATICODE_AUTO_RESUME": "false", "SEARCH_DEFAULT_LIMIT": "3",
                },
            },
            "codebase-memory": {
                "command": CBM, "cwd": str(project),
                "env": {"CBM_ALLOWED_ROOT": str(project), "CBM_CACHE_DIR": str(self.root / "state/cbm-cache")},
            },
            "jcodemunch": {
                "command": JCODEMUNCH,
                "env": {"CODE_INDEX_PATH": str(self.root / "state/code-index"), "JCODEMUNCH_SHARE_SAVINGS": "0"},
            },
        }
        for d in defs.values():
            if "command" in d:
                d["env"] = dict(base, **d.get("env", {}))
        defs["context-mode"]["env"]["CONTEXT_MODE_DIR"] = str(self.root / "state/context-mode")
        return defs

    def write_mcporter_config(self, project, path=None, servers=None):
        defs = self.server_defs(project)
        if servers:
            defs = {k: defs[k] for k in servers}
        cfg = {"imports": [], "mcpServers": defs}
        path = pathlib.Path(path or self.root / "state/mcporter.json")
        path.write_text(json.dumps(cfg, indent=1))
        return path

    def write_mcp_json(self, project, path, servers):
        """Claude-Desktop/.mcp.json style config (used by Inspector --config and wong2/mcp-cli -c)."""
        defs = self.server_defs(project)
        out = {}
        for k in servers:
            d = defs[k]
            if "baseUrl" in d:
                out[k] = {"type": "streamable-http", "url": d["baseUrl"]}
            else:
                out[k] = {"command": d["command"], "args": d.get("args", []), "env": d.get("env", {})}
                if "cwd" in d:
                    out[k]["cwd"] = d["cwd"]
        pathlib.Path(path).write_text(json.dumps({"mcpServers": out}, indent=1))
        return path

    # ---- runner ----------------------------------------------------------
    def run(self, argv, cwd=None, timeout=180, env_extra=None, input=None):
        env = dict(self.env, **(env_extra or {}))
        t0 = time.time()
        try:
            p = subprocess.run(argv, cwd=cwd or self.root, env=env, capture_output=True, timeout=timeout, input=input)
            rc, out, err = p.returncode, p.stdout, p.stderr
        except subprocess.TimeoutExpired as e:
            rc, out, err = "timeout", e.stdout or b"", (e.stderr or b"") + b"\n[harness] timeout"
        elapsed = round((time.time() - t0) * 1000)
        so, se = out.decode("utf-8", "replace"), err.decode("utf-8", "replace")
        return {
            "argv": [sanitize(str(a)) for a in argv],
            "cwd": sanitize(str(cwd or self.root)),
            "exit": rc,
            "elapsed_ms": elapsed,
            "stdout": sanitize(so),
            "stderr": sanitize(se),
            "stdout_sha256": sha(sanitize(so)),
        }

    def daemon_metadata(self):
        d = pathlib.Path(self.env["MCPORTER_DAEMON_DIR"]) / "daemon"
        out = {}
        if d.exists():
            for f in sorted(d.iterdir()):
                if f.suffix == ".json":
                    try:
                        out[f.name] = json.loads(f.read_text())
                    except Exception as e:  # noqa: BLE001
                        out[f.name] = f"unreadable: {e}"
                else:
                    out[f.name] = "present"
        return out

    def owned_daemon_pids(self):
        """Processes whose environ carries this fixture's MCPORTER_DAEMON_DIR and run `daemon start`."""
        mine = []
        needle = f"MCPORTER_DAEMON_DIR={self.short}".encode()
        for pid in os.listdir("/proc"):
            if not pid.isdigit():
                continue
            try:
                cmd = pathlib.Path(f"/proc/{pid}/cmdline").read_bytes()
                if b"daemon" not in cmd or b"mcporter" not in cmd:
                    continue
                if any(e.startswith(needle) for e in pathlib.Path(f"/proc/{pid}/environ").read_bytes().split(b"\0")):
                    mine.append(int(pid))
            except (FileNotFoundError, PermissionError, ProcessLookupError):
                continue
        return mine

    def owned_procs_under_root(self):
        """Any process whose environ carries this fixture's HOME (servers spawned by owned bridges)."""
        needle = f"HOME={self.home}".encode()
        res = []
        for pid in os.listdir("/proc"):
            if not pid.isdigit() or int(pid) == os.getpid():
                continue
            try:
                if needle in pathlib.Path(f"/proc/{pid}/environ").read_bytes().split(b"\0"):
                    cmd = pathlib.Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace")
                    res.append({"pid": int(pid), "cmd": sanitize(cmd[:200])})
            except (FileNotFoundError, PermissionError, ProcessLookupError):
                continue
        return res

    def stop(self):
        for pid in self.owned_daemon_pids():
            try:
                os.kill(pid, signal.SIGCONT)
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        for name, p in self.procs.items():
            if p.poll() is None:
                os.killpg(p.pid, signal.SIGTERM)
                try:
                    p.wait(10)
                except subprocess.TimeoutExpired:
                    os.killpg(p.pid, signal.SIGKILL)
        time.sleep(1)
        left = self.owned_procs_under_root()
        for r in left:
            try:
                os.kill(r["pid"], signal.SIGKILL)
            except ProcessLookupError:
                pass
        return left
