"""Structural G13 (command-center item task-ns2604-coop-20261006T132948Z): every listed answer source is hidden from each
trial's mount namespace, and G13 checks what the wrapper hid.

The item's decision: a classifier of the commands a model typed cannot converge, because shell grammar always has
another form (aliases, xargs, find actions, subshells, `python -c`, here-docs). So the answer sources leave the trial's
view instead, and the command classifier (grade.reach) stays a diagnostic tag that never invalidates a trial.

What a trial's client process tree cannot see (plan()):
- the coordination state, as an empty tmpfs: every run root (oracle runs, other trials' drafts, grades, run.json,
  gate0.json), the suite cards and the v1 captures;
- the fixture cache, as an empty tmpfs: its templates, tarballs, oracles.json and oracle work;
- the fixtures folder and the trial-files folder, as empty tmpfs with only the trial's own entries bound back: its
  fixture, and its prompt, settings, Codex clone, -o answer file and the run's neutral binaries;
- the Claude projects folder, as an empty tmpfs with every project bound back that is not under the experiment's roots,
  and the trial's own: other trials' transcripts (subagents included) are gone, the native home's own projects stay;
- the shared Codex sessions folder (the clone's `sessions` alias points at it) and the other per-session client stores
  (Claude file history, context-mode's per-project stores, Claude's /tmp area): a fresh per-trial folder is bound over
  each. The trial's own writes land in its trial folder, and finish() publishes its rollouts to the native sessions
  folder after it exits, where collect.py finds them (no isolated trial sees that folder).
The native home and the client configuration stay visible and writable. The system runtime is read-only, as in the R2a
replay's isolation. The network and the environment are unchanged, so the treatment is unchanged: legitimate work never
needs those paths.

bubblewrap 0.11.1 (/usr/bin/bwrap: Ubuntu bubblewrap 0.11.1-1ubuntu0.3, upstream github.com/containers/bubblewrap),
unprivileged: bwrap is not setuid here, so it creates a user namespace. Options relied on, as `bwrap --help` describes
them:
- --args FD: the options travel through a memfd, so the namespace's PID 1 (bwrap's reaper) shows none of the hidden paths
  in a process listing;
- --ro-bind, --bind, --bind-try, --dev-bind (a plain --bind is nodev), --tmpfs, --proc and --chdir;
- --unshare-pid: a fresh /proc, so no other process's /proc/<pid>/root leads back to the host's view;
- --unshare-ipc: System V IPC objects and POSIX message queues of its own;
- --die-with-parent;
- --info-fd FD: the child pid and the mount and pid namespace ids.
No --new-session: the launcher's TERM must reach the client for a graceful exit (launcher._kill_group).
The item's fallback, systemd's InaccessiblePaths= in a transient user unit (systemd 259, systemd.exec(5)), is not
used, because bwrap hosts every launch path (selftest(clients=True)).

Optional audit (not implemented, never a gate): a fanotify listener held by root on the hidden roots, filtered to the
trial tree's pids, would corroborate the receipt. An unprivileged listener (Linux 5.13 and later) may mark only inodes,
not a mount or filesystem, and does not receive the pid of the process that generated an event (fanotify_init(2),
man-pages, man7.org), so the pid filter needs CAP_SYS_ADMIN; this harness runs no sudo, so the audit stays an option.

Round 5 (CC item task-ns2604-coop-20261006T143846Z): /tmp, /var/tmp and /dev/shm are private per trial (Claude's /tmp
area is bound into the private /tmp; a codebase-memory MCP server then starts its own daemon there instead of joining the
host's, whose socket lives in /tmp). ai-memory keeps one scope per trial through the marker above (the grader checks
every call's returned scopes). A published receipt carries only the count and sha256 of the kept project names
(public_receipt).

GPT read of 2044b2ab, accepted by CC item task-ns2604-coop-20261006T151719Z (C1):
- G13 checks each bind as an exact (operation, source, destination) triple of the trial's plan (permitted_binds). The
  private folder comes from the trial id, never from the receipt, so a permitted destination bound from a shared source
  fails.
- No bind may come after a cover it would re-expose: a tmpfs, a private folder or an inaccessible file, declared answer
  sources included.
- The options a receipt hashes must be the ones its operations give.
- Each trial also gets an IPC namespace of its own (--unshare-ipc), the extension the read proposed to the private /tmp
  and /dev/shm ruling.
- A published receipt hashes every folder name derived from the home path (public_text).
- CL7b's process tree is sampled like the launcher's (AppServerCensus).

P2-2 of the same read, upheld by the same item: host execution brokers are out of reach.
- Each trial gets an empty private runtime folder (/run/user/$UID, tmpfs, mode 0700) and an empty /run/WSL.
- So the user manager's and the session bus's sockets (systemd-run --user), rootless Docker's socket, the ssh-agent
  and gpg-agent sockets, and WSL interop's sockets (a Windows program would read the distribution from outside) do not
  exist in its namespace.
- Nothing is passed through (RUNTIME_PASS_THROUGH, with the evidence).
- The self-test and the focused tests attempt each connection inside and require it to fail (host_broker_probes).
- The system bus stays: an unprivileged systemd-run against the system manager needs polkit's admin authentication
  (org.freedesktop.systemd1.manage-units: auth_admin, or auth_admin_keep when active, in
  /usr/share/polkit-1/actions/org.freedesktop.systemd1.policy), which a trial cannot give.

Limits:
- Services reached over the network run outside the namespace: the ai-memory server, MCP servers configured by URL
  and the OmniRoute gateway. So a file such a service reads for the trial is not hidden by this mount namespace. The
  grader tags direct HTTP to local services, checks every ai-memory call's scope, and the per-trial scoping of those
  stores (R10) still applies. Use of user systemd, Docker or WSL interop is still tagged, as a diagnostic.
- The network is the host's, so every service on its loopback is reachable. That includes the gateway's management
  routes: its call logs, with request and response payloads, answer without credentials.
- ai-memory's shared `_global` scope carries no trial ownership, so a page another trial wrote there is not caught by
  the scope check (a write to it is tagged).
- A setuid helper (sudo) does not work inside a user namespace.
- A sandbox the trial starts (Codex's own, `unshare`, a nested bwrap) runs in a namespace below the trial's, whose
  mounts are locked there (mount_namespaces(7)): it cannot unmount a hidden tmpfs.
- The process census samples every 2 s, so a process that starts and ends between two samples is not seen. The
  namespace record and the locked mounts do not depend on it: a process below bwrap cannot join the host's mount
  namespace, which needs CAP_SYS_ADMIN in the user namespace that owns it (setns(2)).

    python3 -B isolation.py selftest [--run-root <root>] [--clients]   wrapper-only smoke, no model call
"""
from __future__ import annotations

import argparse
import errno
import hashlib
import json
import os
import re
import select
import shlex
import shutil
import subprocess
import sys
import threading
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from common import (CODEX_HOME_REAL, FIXTURE_CACHE, GATEWAY, HOME, NEUTRAL_ROOT, RUNS_ROOT, TRIAL_ROOT_BASE,  # noqa: E402
                    V1_ROOT, load_json, sha256_file, sha256_json, trial_dir, utc_now, write_json)

ISOLATION_DECISION = "task-ns2604-coop-20261006T132948Z"
# Round 5's rulings on the residual channels, receipt privacy and fanotify (CC item, 14:38Z).
RESIDUALS_DECISION = "task-ns2604-coop-20261006T143846Z"
# The rulings on the GPT read of 2044b2ab (CC item, 15:17Z, section C1): bind triples, the public receipt, P2-2.
ROUND4_READ_DECISION = "task-ns2604-coop-20261006T151719Z"
# ai-memory stays in the treatment with one scope per trial (RESIDUALS_DECISION (a)): the marker that ai-memory 2.5.2
# documents for static clients and for its lifecycle hooks (docs/marker-file.md at v2.5.2: hooks walk up from cwd to
# the first `.ai-memory.toml`; a static MCP client passes the marker's workspace + project on every project-scoped
# call). It is bound above the fixture inside the trial's namespace only, so the fixture is unchanged and no other
# trial or host process sees it.
AI_MEMORY_WORKSPACE = "organic-e2e"
BWRAP = "/usr/bin/bwrap"
COORDINATION_ROOT = HOME / ".local" / "state" / "native-agent-stack" / "coordination"
FIXTURE_CACHE_ROOT = FIXTURE_CACHE.parent
CLAUDE_PROJECTS = HOME / ".claude" / "projects"
CODEX_SESSIONS = CODEX_HOME_REAL / "sessions"
UID = os.getuid()
# Per-session client stores replaced by a fresh per-trial folder in the namespace (the shared sessions alias first).
# Each holds only per-session or per-project entries that the client creates on demand, so a trial, whose fixture is a
# new project, starts from the state a fresh install or a host restart gives (the 13:47Z restart emptied /tmp, and
# sessions started normally). context-mode's own root (its install log) stays shared: only its per-project
# subfolders are private.
PRIVATE_STORES = (("codex-sessions", CODEX_SESSIONS),
                  ("claude-file-history", HOME / ".claude" / "file-history"),
                  ("claude-context-mode-sessions", HOME / ".claude" / "context-mode" / "sessions"),
                  ("claude-context-mode-content", HOME / ".claude" / "context-mode" / "content"),
                  ("codex-context-mode-sessions", CODEX_HOME_REAL / "context-mode" / "sessions"),
                  ("codex-context-mode-content", CODEX_HOME_REAL / "context-mode" / "content"),
                  ("claude-tmp", Path(f"/tmp/claude-{UID}")))
STORE_LABELS = {"codex-sessions": "Codex transcripts", "claude-file-history": "Claude file history (draft copies)",
                "claude-context-mode-sessions": "Claude context-mode session stores",
                "claude-context-mode-content": "Claude context-mode content stores",
                "codex-context-mode-sessions": "Codex context-mode session stores",
                "codex-context-mode-content": "Codex context-mode content stores",
                "claude-tmp": "Claude scratch and task output"}
# Writable over the read-only runtime: the native home (the temporary folders and the runtime folder are private).
WRITABLE = (HOME,)
# P2-2 of the GPT read of 2044b2ab, upheld by CC item task-ns2604-coop-20261006T151719Z (C1): host execution brokers.
# A process outside the namespace that runs a command on request would read a hidden answer for the trial:
# - the user manager (`systemd-run --user --pipe --wait cat <answer>`, through $XDG_RUNTIME_DIR/systemd/private or
#   the session bus);
# - the rootless Docker daemon (docker.sock, whose containers mount the host's view);
# - WSL interop: a Windows program started from the trial reads the distribution through \\wsl.localhost\<distro>.
# Each trial gets an empty private runtime folder (tmpfs, mode 0700, as XDG_RUNTIME_DIR must be) and an empty /run/WSL,
# so none of those sockets exists in its namespace. The runtime folder's ssh-agent and gpg-agent sockets go with it.
RUNTIME_DIR = Path(f"/run/user/{UID}")
WSL_INTEROP_DIR = Path("/run/WSL")
# What a trial's clients need from the host's runtime folder, each with its reason: nothing. Each launch path's client
# starts with the empty folder (selftest(clients=True)). No MCP server of either native client is launched through
# Docker. Codex keeps MCP OAuth credentials in files (mcp_oauth_credentials_store = "file"), and no Secret Service
# runs on this host. No suite task names Docker, systemd or a Windows program.
RUNTIME_PASS_THROUGH: tuple[tuple[str, str], ...] = ()
BROKER_SOCKETS = (RUNTIME_DIR / "systemd" / "private", RUNTIME_DIR / "bus", RUNTIME_DIR / "docker.sock",
                  RUNTIME_DIR / "openssh_agent")
# The answer-channel closure (CC item task-ns2604-coop-20261006T164313Z, section 3 (c); a separate, droppable commit).
# The home folder is a temporary overlay (bwrap --overlay-src HOME --tmp-overlay HOME): a trial reads it, but nothing it
# writes there outlives it, except through the explicit binds below. Each store that holds other sessions' or other
# trials' content is an empty tmpfs in the namespace.
CLOSURE_DECISION = "task-ns2604-coop-20261006T164313Z"
CLOSED_STORES = (("ai-memory's store and hook spool (every scope's database, pages and spooled events)",
                  HOME / ".local" / "share" / "ai-memory"),
                 ("agentsview's archive of every session on the host", HOME / ".agentsview"),
                 ("codebase-memory's project indexes", HOME / ".cache" / "codebase-memory-mcp"),
                 ("jcodemunch's index", HOME / ".code-index"),
                 ("Serena's logs", HOME / ".serena" / "logs"),
                 ("Claude's plans", HOME / ".claude" / "plans"),
                 ("Claude's tasks", HOME / ".claude" / "tasks"),
                 ("Claude's paste cache", HOME / ".claude" / "paste-cache"),
                 ("Codex's own state: history, session index, logs, memories, goals and queue", CODEX_HOME_REAL))
# Files, each replaced by an empty private file the trial may write.
CLOSED_FILES = (("Claude's prompt history", "claude-history.jsonl", HOME / ".claude" / "history.jsonl"),)
# What a client provably needs from the closed Codex folder: the entries a trial's clone links to (arms.SYMLINK), each
# as a temporary overlay so nothing is written back: packages (the codex binary), skills, plugins, cache and
# context-mode. The clone's sessions and context-mode stores are the trial's private folders (PRIVATE_STORES).
CODEX_BIND_BACK = ("packages", "skills", "plugins", "cache", "context-mode")
# Written back to the host on purpose, each with its reason.
PERSISTENT_BINDS = ((HOME / ".claude" / ".credentials.json",
                     "Claude Code's OAuth refresh rotates the stored token: a refresh kept only in the overlay would "
                     "leave the host's login with a spent token"),)
# Round 6 (CC item task-ns2604-coop-20261006T155742Z, section 2): (A) the gateway's response cache stays on, with a
# reading before and after each trial; (B) each trial gets a network namespace of its own with explicit forwards only.
ROUND6_DECISION = "task-ns2604-coop-20261006T155742Z"
# (B) The forwards' sockets appear inside the private runtime folder, so no hidden root's path shows in the namespace's
# process listing (the in-namespace socat listeners name them).
NET_DIR_INSIDE = RUNTIME_DIR / "net"
PROXY_PORT = 3128
# (B) Every route out of a trial's network namespace: the clients it serves and its reason. A trial gets the forwards
# its client is listed for and nothing else (netfilter.py serves them; NET_PRELUDE listens inside).
NET_FORWARDS = {
    "gateway": {
        "clients": ["codex"], "listen": 21128, "kind": "http", "upstream": ["127.0.0.1", 21128],
        "rules": [{"prefix": "/v1/", "methods": ["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]}],
        "reason": "Codex's model API: the omniroute profile's base_url http://127.0.0.1:21128/v1 (wire_api responses). "
                  "OmniRoute serves /api, its dashboard and its call logs on the same port, so the filter admits "
                  "/v1/... only."},
    "otlp": {
        "clients": ["claude", "codex"], "listen": 21318, "kind": "http", "upstream": ["127.0.0.1", 21318],
        "rules": [{"exact": path, "methods": ["POST"]} for path in ("/v1/logs", "/v1/metrics", "/v1/traces")],
        "reason": "both clients' telemetry export: Codex's [otel] otlp-http exporters (127.0.0.1:21318/v1/logs and "
                  "/v1/metrics) and Claude's OTEL_EXPORTER_OTLP_ENDPOINT (http://127.0.0.1:21318, http/protobuf). "
                  "The grader's joins read it from Loki (G2, G3), and an OTLP receiver serves no reads."},
    "ai-memory": {
        "clients": ["claude", "codex"], "listen": 29374, "kind": "http", "upstream": ["127.0.0.1", 29374],
        "rules": [{"exact": "/mcp", "methods": ["GET", "POST", "DELETE"]},
                  {"exact": "/hook", "methods": ["POST"], "scope": "query"},
                  {"exact": "/hook/batch", "methods": ["POST"], "scope": "batch"},
                  {"exact": "/handoff", "methods": ["GET"], "scope": "query"}],
        "reason": "ai-memory stays in the treatment with the trial's own scope (CC 14:38Z): both clients' MCP endpoint, "
                  "and the lifecycle hooks' routes (POST /hook, POST /hook/batch, GET /handoff: "
                  "crates/ai-memory-hooks/src/router.rs:605-611 at v2.5.2), whose queries must name the trial's "
                  "scope. The web interface, /admin and every other route stay out."},
    # Round 6b (CC item task-ns2604-coop-20261006T170607Z, (1)): the local dependencies of the tools under test.
    "vllm": {
        "clients": ["claude", "codex"], "listen": 28231, "kind": "http", "upstream": ["127.0.0.1", 28231],
        "rules": [{"exact": "/v1/embeddings", "methods": ["POST"]}, {"exact": "/v1/models", "methods": ["GET"]}],
        "tool": "socraticode (LMSTUDIO_URL http://127.0.0.1:28231/v1), and the other tools under test with an embedding "
                "mode",
        "reason": "SocratiCode and the other tools under test with embedding modes need it. Embedding calls are "
                  "stateless and store nothing, so this opens no answer channel."},
    "qdrant": {
        "clients": ["claude", "codex"], "listen": 21633, "kind": "http", "upstream": ["127.0.0.1", 21633],
        # The filter is netfilter.judge_qdrant (round 6d): these rules document it; {prefix} becomes the trial's own
        # QDRANT_COLLECTION_PREFIX (network_for, which also sets the forward's qdrant_prefix).
        "rules": [{"exact": "/healthz", "methods": ["GET"]},
                  {"exact": "/collections", "methods": ["GET"], "response": "the trial's own names only"},
                  {"prefix": "/collections/{prefix}", "operations": {"": ["GET", "PUT", "DELETE"], "/index": ["PUT"],
                                                                     "/points": ["PUT", "POST"],
                                                                     "/points/delete": ["POST"],
                                                                     "/points/scroll": ["POST"],
                                                                     "/points/query": ["POST"]},
                   "body": "every with_lookup and lookup_from collection carries the prefix"}],
        "tool": "socraticode (QDRANT_URL http://127.0.0.1:21633, QDRANT_MODE external)",
        "reason": "SocratiCode's vector store. Only the operations socraticode 1.15.0 performs are admitted "
                  "(getCollections, create, get and delete collection, payload index, upsert, retrieve, delete, "
                  "scroll and query: dist/services/qdrant.js, dist/services/symbol-graph-store.js), each on a "
                  "collection of the trial's own QDRANT_COLLECTION_PREFIX (dist/constants.js:59-66, "
                  "dist/config.js:193-226, its metadata collection dist/services/qdrant.js:1067), which the wrapper "
                  "sets per trial. Every collection a body names (with_lookup, lookup_from) must carry it too, and "
                  "grouped, batch, search, recommend and discover routes stay out. GET /collections is admitted because "
                  "socraticode cannot create its collections without it (dist/services/qdrant.js:105-118 and "
                  "1090-1100), and it answers with the trial's own names only. The trial builds its own index from "
                  "its own fixture."},
    "model-egress": {
        "clients": ["claude"], "listen": PROXY_PORT, "kind": "connect",
        "allow": [["api.anthropic.com", 443], ["platform.claude.com", 443]],
        "reason": "Claude Code's model API and OAuth token refresh: the installed 2.1.291 binary's BASE_API_URL "
                  "https://api.anthropic.com and TOKEN_URL https://platform.claude.com/v1/oauth/token. Claude Code "
                  "honours HTTPS_PROXY, which the wrapper sets for Claude trials only. TLS stays end to end. A "
                  "treatment fact, not a forward: Claude's server-side web search runs at Anthropic, reached through "
                  "this same API."},
}
# Round 6b: web tools and gh stay off (no forward) unless a task's preregistered spec requires one: none of the tools
# under test needs the internet, and GitHub or web content can carry task answers.


def qdrant_prefix(trial_id: str) -> str:
    """The trial's own Qdrant collection prefix (socraticode accepts [A-Za-z0-9_-] only)."""
    return "ns2604_trial_" + "".join(ch for ch in trial_id if ch.isalnum()).lower() + "_"
NET_ENV = {"claude": [["HTTPS_PROXY", f"http://127.0.0.1:{PROXY_PORT}"], ["https_proxy", f"http://127.0.0.1:{PROXY_PORT}"],
                      ["NO_PROXY", "127.0.0.1,localhost,::1"], ["no_proxy", "127.0.0.1,localhost,::1"]],
           "codex": []}
# Round 6b, for every trial: npm resolves only from the cache already in the home (no registry: chrome-devtools-mcp
# 1.10.1 sits in ~/.npm/_npx), and socraticode names its collections with the trial's own prefix (network_for).
NET_ENV_ALL = [["npm_config_offline", "true"]]
# (B) Inside the namespace, before the client: one socat listener per forward on its usual loopback port, connected to
# the forward's Unix socket (sandbox-runtime's bridge, README.md line 553 at v0.0.78). The client starts only once every
# port listens (read from /proc/net/tcp, so no connection is made), and the trial fails closed otherwise.
NET_PRELUDE = r'''command -v socat >/dev/null 2>&1 || { echo "network prelude: socat missing" >&2; exit 97; }
ports=""
while [ "$#" -gt 0 ] && [ "$1" != "--" ]; do
  port=${1%%=*}; sock=${1#*=}
  socat TCP-LISTEN:"$port",bind=127.0.0.1,reuseaddr,fork UNIX-CONNECT:"$sock" </dev/null >/dev/null 2>&1 &
  ports="$ports $port"; shift
done
shift
i=0
while :; do
  ready=1
  for p in $ports; do
    hex=$(printf '%04X' "$p")
    grep -q "^ *[0-9]*: 0100007F:$hex 00000000:0000 0A" /proc/net/tcp || ready=0
  done
  [ "$ready" = 1 ] && break
  i=$((i+1)); [ "$i" -ge 200 ] && { echo "network prelude: listeners not ready" >&2; exit 98; }
  sleep 0.05
done
exec "$@"'''
# Private per trial (RESIDUALS_DECISION (a)): an empty tmpfs over each, so no file passes between trials through them.
# The X11 socket folder is bound back when it exists (sockets only, no trial content), so a display keeps working.
PRIVATE_TMP = (Path("/tmp"), Path("/var/tmp"), Path("/dev/shm"))
X11_SOCKETS = Path("/tmp/.X11-unix")
# A Claude project whose cwd was under one of these is an experiment's: a trial fixture, a trial file, a v1 fixture in
# the fixture cache, or the coordination state.
EXPERIMENT_ROOTS = (NEUTRAL_ROOT, TRIAL_ROOT_BASE, FIXTURE_CACHE_ROOT, COORDINATION_ROOT)
# Roots a trial sees only as an empty tmpfs (plus its own entries where plan() binds them back).
HIDDEN_ROOTS = (COORDINATION_ROOT, FIXTURE_CACHE_ROOT, NEUTRAL_ROOT, TRIAL_ROOT_BASE, CLAUDE_PROJECTS)
SUITE_DEFAULT = V1_ROOT / "suite-v1.json"
SELFTEST_FILE = "isolation-selftest.json"
_VERSION: list[str] = []


def claude_slug(path) -> str:
    """Claude Code's project folder name for a cwd (collect.claude_slug)."""
    return "".join(ch if ch.isalnum() else "-" for ch in str(path))


def tilde(value):
    return None if value is None else str(value).replace(str(HOME), "~")


def untilde(value):
    return None if value is None else str(value).replace("~", str(HOME), 1) if str(value).startswith("~") else str(value)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def bwrap_version() -> str | None:
    if not _VERSION:
        try:
            out = subprocess.run([BWRAP, "--version"], capture_output=True, text=True, timeout=30)
            _VERSION.append(out.stdout.strip() or None)
        except OSError:
            _VERSION.append(None)
    return _VERSION[0]


def under(path, root) -> bool:
    path, root = str(path).rstrip("/"), str(root).rstrip("/")
    return path == root or path.startswith(root + "/")


def experiment_project(name: str) -> bool:
    """A Claude project folder of a trial or of anything else run under the experiment's roots."""
    for root in EXPERIMENT_ROOTS:
        slug = claude_slug(root)
        if name == slug or name.startswith(slug + "-"):
            return True
    return False


# ---------------------------------------------------------------------------------------------------------------------
# The plan and the receipt.

def _entry(location: str, path, covered_by, mount: str) -> dict:
    path = Path(path)
    kind = "file" if path.is_file() else "dir" if path.is_dir() else "absent"
    out = {"location": location, "path": tilde(path), "path_sha256": sha256_text(str(path)), "kind": kind,
           "covered_by": tilde(covered_by), "mount": mount}
    if kind == "file":
        out["content_sha256"] = sha256_file(path)
    return out


def _declared(cfg: dict) -> list[Path]:
    return [Path(untilde(str(raw))) for raw in cfg.get("answer_source_paths") or []]


def listed_locations(cfg: dict, run_root, trial_id: str, client: str, fixture, clone=None) -> list[dict]:
    """The item's listed answer-source locations for one trial (and the per-session stores beside them), each with the
    mount that hides it in plan(): the receipt's hidden list, and what G13 requires of every receipt."""
    run_root = Path(run_root)
    suite = Path((cfg.get("suite") or {}).get("path") or SUITE_DEFAULT)
    oracles = (cfg.get("fixture") or {}).get("oracles_path")
    rows = [("run roots: oracle runs, other trials' drafts, grades", RUNS_ROOT, COORDINATION_ROOT, "tmpfs"),
            ("run roots: this run", run_root, COORDINATION_ROOT, "tmpfs"),
            ("run roots: the v1 captures", V1_ROOT, COORDINATION_ROOT, "tmpfs"),
            ("suite cards", suite, COORDINATION_ROOT, "tmpfs"),
            ("the fixture cache's oracles.json", Path(oracles) if oracles else FIXTURE_CACHE / "oracles.json",
             FIXTURE_CACHE_ROOT, "tmpfs"),
            ("other trials' fixtures (and their drafts)", NEUTRAL_ROOT, NEUTRAL_ROOT, "tmpfs + own fixture"),
            ("other trials' prompts, settings, clones and -o answers", TRIAL_ROOT_BASE, TRIAL_ROOT_BASE, "tmpfs + own files"),
            ("other trials' Claude transcripts", CLAUDE_PROJECTS, CLAUDE_PROJECTS,
             "tmpfs + projects outside the experiment + own project")]
    if clone:
        rows.append(("the shared sessions alias in the trial's clone", Path(clone) / "sessions", CODEX_SESSIONS, "private"))
    rows += [(f"the shared {STORE_LABELS[label]}" if label == "codex-sessions" else f"other sessions' {STORE_LABELS[label]}",
              target, target, "private") for label, target in PRIVATE_STORES]
    rows += [(f"the host's {path} (other trials' scratch files)", path, path, "tmpfs") for path in PRIVATE_TMP]
    rows += [("the home folder's writes (they would outlive the trial)", HOME, HOME, "overlay")]
    rows += [(label, store, store, "tmpfs") for label, store in CLOSED_STORES]
    rows += [(label, target, target, "private file") for label, _, target in CLOSED_FILES if target.is_file()]
    rows.append(("the host's runtime folder: the user manager's, the session bus's and Docker's sockets (host "
                 "execution brokers)", RUNTIME_DIR, RUNTIME_DIR, "tmpfs"))
    if WSL_INTEROP_DIR.is_dir():
        rows.append(("WSL interop's sockets (a Windows program runs outside the namespace)", WSL_INTEROP_DIR,
                     WSL_INTEROP_DIR, "tmpfs"))
    for path in _declared(cfg):
        cover = next((root for root in HIDDEN_ROOTS if under(path, root)), path)
        rows.append(("declared answer source", path, cover,
                     "tmpfs" if cover != path or path.is_dir() else "inaccessible" if path.is_file() else "absent"))
    return [_entry(*row) for row in rows]


def network_for(client: str, trial_id: str, private=None) -> dict:
    """ROUND6_DECISION (B): the trial's network record. It holds the forwards its client is listed for, each with the
    socket it is served on outside when private is given; the environment the wrapper adds; and the ai-memory scope the
    hook routes must name."""
    forwards = {}
    prefix = qdrant_prefix(trial_id)
    for name, forward in NET_FORWARDS.items():
        if client in forward["clients"]:
            entry = json.loads(json.dumps({k: v for k, v in forward.items() if k != "clients"}))
            for rule in entry.get("rules") or []:
                if "{prefix}" in rule.get("prefix", ""):
                    rule["prefix"] = rule["prefix"].replace("{prefix}", prefix)
            if name == "qdrant":
                entry["qdrant_prefix"] = prefix
            if private is not None:
                entry["socket"] = str(Path(private) / "net" / client / f"{name}.sock")
            forwards[name] = entry
    setenv = [list(pair) for pair in NET_ENV.get(client, [])] + [list(pair) for pair in NET_ENV_ALL] \
        + [["QDRANT_COLLECTION_PREFIX", prefix]]
    return {"decision": ROUND6_DECISION, "namespace": "own (--unshare-net)", "forwards": forwards,
            "setenv": setenv, "inside_dir": str(NET_DIR_INSIDE),
            "scope": {"workspace": AI_MEMORY_WORKSPACE, "project": trial_id}, "qdrant_prefix": prefix}


def network_policy(network: dict | None) -> dict | None:
    """The parts of a network record G13 compares: each forward's port, kind, upstream, rules and allowlist, the added
    environment and the scope."""
    if not network:
        return None
    return {"forwards": {name: {k: forward.get(k) for k in ("listen", "kind", "upstream", "rules", "allow", "qdrant_prefix")}
                         for name, forward in sorted((network.get("forwards") or {}).items())},
            "setenv": network.get("setenv"), "scope": network.get("scope"), "inside_dir": network.get("inside_dir")}


def net_command(plan_: dict, command: list[str]) -> list[str]:
    """The namespace's command with the network prelude ahead of the client: one socat listener per forward."""
    network = plan_.get("network")
    if not network:
        return list(command)
    specs = [f"{forward['listen']}={NET_DIR_INSIDE}/{name}.sock" for name, forward in network["forwards"].items()]
    return ["sh", "-c", NET_PRELUDE, "net", *specs, "--", *command]


def plan(cfg: dict, run_root, trial_id: str, client: str, fixture, *, clone=None, settings=None, prompt=None) -> dict:
    """The mount operations for one trial, in bwrap's order: the read-only runtime, the writable home and temporary
    folders, an empty tmpfs over each hidden root with the trial's own entries bound back, and a fresh per-trial folder
    over each per-session store."""
    run_root, fixture = Path(run_root), Path(fixture)
    work, private = trial_dir(cfg, run_root), private_dir(cfg, run_root, trial_id)
    ops: list[list] = [["ro-bind", "/", "/"], ["dev-bind", "/dev", "/dev"], ["proc", None, "/proc"]]
    # CLOSURE_DECISION: the home folder as a temporary overlay; nothing a trial writes there outlives it, except through
    # the explicit binds below.
    ops += [["overlay", str(path), str(path)] for path in WRITABLE]
    ops += [["bind-try", str(path), str(path)] for path, _ in PERSISTENT_BINDS]
    # P2-2: a private runtime folder (a tmpfs op's source field carries its mode) and no WSL interop sockets.
    ops.append(["tmpfs", "0700", str(RUNTIME_DIR)])
    ops += [["bind", str(src), str(src)] for src, _ in RUNTIME_PASS_THROUGH]
    # ROUND6_DECISION (B): the forwards' sockets, read-only, inside the private runtime folder.
    ops.append(["ro-bind", str(private / "net" / client), str(NET_DIR_INSIDE)])
    if WSL_INTEROP_DIR.is_dir():
        ops.append(["tmpfs", None, str(WSL_INTEROP_DIR)])
    # Private /tmp, /var/tmp and /dev/shm; Claude's /tmp area is bound below into the private /tmp.
    ops += [["tmpfs", None, str(path)] for path in PRIVATE_TMP]
    ops.append(["bind-try", str(X11_SOCKETS), str(X11_SOCKETS)])
    ops += [["tmpfs", None, str(COORDINATION_ROOT)], ["tmpfs", None, str(FIXTURE_CACHE_ROOT)]]
    ops += [["tmpfs", None, str(NEUTRAL_ROOT)], ["bind", str(fixture), str(fixture)]]
    # The trial's ai-memory scope: a marker above its fixture, seen only in this namespace (AI_MEMORY_WORKSPACE).
    ops.append(["ro-bind", str(private / "ai-memory.toml"), str(NEUTRAL_ROOT / ".ai-memory.toml")])
    ops.append(["tmpfs", None, str(TRIAL_ROOT_BASE)])
    if (work / "bin").is_dir():
        ops.append(["ro-bind", str(work / "bin"), str(work / "bin")])
    for path in (settings, prompt):
        if path:
            ops.append(["ro-bind", str(path), str(path)])
    if clone:
        ops.append(["bind", str(clone), str(clone)])
    ops.append(["bind", str(private / "last"), str(work / "last")])
    kept = sorted(d.name for d in CLAUDE_PROJECTS.iterdir() if d.is_dir() and not experiment_project(d.name)) \
        if CLAUDE_PROJECTS.is_dir() else []
    own_project = CLAUDE_PROJECTS / claude_slug(fixture) if client == "claude" else None
    ops.append(["tmpfs", None, str(CLAUDE_PROJECTS)])
    # --bind-try: Claude Code's transcript cleanup may remove a project folder between this plan and the spawn.
    ops += [["ro-bind-try", str(CLAUDE_PROJECTS / name), str(CLAUDE_PROJECTS / name)] for name in kept]
    if own_project:
        ops.append(["bind", str(own_project), str(own_project)])
    # CLOSURE_DECISION: each closed store an empty tmpfs; the Codex entries a clone links to come back as overlays.
    for _, store in CLOSED_STORES:
        ops.append(["tmpfs", None, str(store)])
        if store == CODEX_HOME_REAL:
            ops += [["overlay", str(store / name), str(store / name)] for name in CODEX_BIND_BACK
                    if (store / name).is_dir()]
    ops += [["bind", str(private / name), str(target)] for _, name, target in CLOSED_FILES if target.is_file()]
    ops += [["bind", str(private / label), str(target)] for label, target in PRIVATE_STORES]
    blocked = []
    for path in _declared(cfg):
        if any(under(path, root) for root in HIDDEN_ROOTS):
            continue
        if path.is_dir():
            ops.append(["tmpfs", None, str(path)])
        elif path.is_file():
            ops.append(["ro-bind", str(private / "blocked"), str(path)])
            blocked.append(path)
    # Host folders are created only where a target sits on the host (the home's stores); a target under the private
    # /tmp exists only inside the namespace's tmpfs.
    mkdirs = [private / "last", private / "net" / client, *(private / label for label, _ in PRIVATE_STORES),
              *(t for _, t in PRIVATE_STORES if not any(under(t, p) for p in PRIVATE_TMP)),
              CLAUDE_PROJECTS] + ([own_project] if own_project else [])
    return {"trial_id": trial_id, "client": client, "work": work, "private": private, "fixture": fixture,
            "clone": Path(clone) if clone else None, "settings": settings, "prompt": prompt, "ops": ops,
            "network": network_for(client, trial_id, private),
            "mkdirs": mkdirs, "blocked": blocked, "kept_projects": kept, "own_project": own_project,
            "ai_memory_scope": {"workspace": AI_MEMORY_WORKSPACE, "project": trial_id,
                                "marker": str(NEUTRAL_ROOT / ".ai-memory.toml"),
                                "fixture_has_own_marker": (fixture / ".ai-memory.toml").exists()},
            "hidden": listed_locations(cfg, run_root, trial_id, client, fixture, clone)}


def prepare_dirs(plan_: dict) -> None:
    """Create the trial's private folders and every mount target on the host before the launch, so no mount creates a
    host folder as a side effect (a missing target would be created through the writable home)."""
    for path in plan_["mkdirs"]:
        Path(path).mkdir(parents=True, exist_ok=True)
    os.chmod(plan_["private"], 0o700)
    for folder in (plan_["private"] / "net", plan_["private"] / "net" / plan_["client"]):
        if folder.is_dir():
            os.chmod(folder, 0o700)
    for _, name, _ in CLOSED_FILES:
        (plan_["private"] / name).touch()
    scope = plan_["ai_memory_scope"]
    (plan_["private"] / "ai-memory.toml").write_text(f'workspace = "{scope["workspace"]}"\nproject = "{scope["project"]}"\n')
    if plan_["blocked"]:
        blocker = plan_["private"] / "blocked"
        blocker.write_text("")
        os.chmod(blocker, 0)


def options(plan_: dict, info_fd: int | None = None) -> list[str]:
    out: list[str] = []
    for op, src, dest in plan_["ops"]:
        if op == "proc":
            out += ["--proc", dest]
        elif op == "tmpfs":
            out += (["--perms", src] if src else []) + ["--tmpfs", dest]
        elif op == "overlay":
            out += ["--overlay-src", src, "--tmp-overlay", dest]
        else:
            out += [f"--{op}", src, dest]
    out += ["--unshare-pid", "--unshare-ipc", "--die-with-parent", "--chdir", str(plan_["fixture"])]
    network = plan_.get("network")
    if network:
        # ROUND6_DECISION (B): a network namespace of its own; the forwards are its only routes out.
        out += ["--unshare-net"]
        for key, value in network.get("setenv") or []:
            out += ["--setenv", key, value]
    if info_fd is not None:
        out += ["--info-fd", str(info_fd)]
    return out


def receipt(plan_: dict, command: list[str]) -> dict:
    """The launched row's isolation record: the wrapper's argv as bwrap parses it (options read from the memfd, the
    info fd and the command shown as placeholders), the argv a process listing shows, the mount operations and the
    hidden list with each path's sha256 (and the content's, for a file)."""
    core = options(plan_)
    shown = [("<network prelude>" if part == NET_PRELUDE else part) for part in net_command(plan_, command)]
    network = plan_.get("network")
    return {"decision": ISOLATION_DECISION, "wrapper": BWRAP, "version": bwrap_version(),
            "argv": [tilde(a) for a in [BWRAP, *core, "--info-fd", "<fd>", "--", *shown]],
            "argv_visible": [BWRAP, "--args", "<fd>", "--", *[tilde(c) for c in shown]],
            # ROUND6_DECISION (B): the network namespace's forwards (each with its reason) and the added environment.
            "network": {**network, "forwards": {name: {k: (tilde(v) if k == "socket" else v) for k, v in forward.items()}
                                                for name, forward in network["forwards"].items()}} if network else None,
            "options_sha256": sha256_text("\0".join(core)),
            "ops": [[op, tilde(src), tilde(dest)] for op, src, dest in plan_["ops"]],
            "hidden": plan_["hidden"], "kept_projects": len(plan_["kept_projects"]),
            "kept_projects_sha256": sha256_json(plan_["kept_projects"]), "own_project": tilde(plan_["own_project"]),
            "private_dir": tilde(plan_["private"]),
            "ai_memory_scope": {**plan_["ai_memory_scope"], "marker": tilde(plan_["ai_memory_scope"]["marker"]),
                                "decision": RESIDUALS_DECISION},
            "namespaces": "user (implied: unprivileged bwrap), mount, pid, ipc, network; uts is the host's",
            # P2-2: the runtime folder is private, so no host execution broker's socket is in the namespace.
            "runtime_dir": {"path": str(RUNTIME_DIR), "private": "tmpfs, mode 0700",
                            "passed_through": [{"path": tilde(p), "why": why} for p, why in RUNTIME_PASS_THROUGH],
                            "wsl_interop_hidden": WSL_INTEROP_DIR.is_dir()},
            "environment": "inherited, plus the network record's setenv (the model egress proxy, Claude trials only)"}


# A Claude project folder's name encodes its cwd, home path included; a published receipt keeps only a hash of it.
PROJECT_PATH = re.compile(r"(~/\.claude/projects/)([^/\s\"']+)")
# Any other name derived from a path under the home (Claude's `-home-<user>-...` slug form) is hashed as well.
HOME_SLUG = claude_slug(HOME)
HOME_SLUG_TOKEN = re.compile(r"[^\s/\"'\[\]]*" + re.escape(HOME_SLUG) + r"[^\s/\"'\[\]]*")


def public_text(value):
    """A string with the home path written as ~, every Claude project folder name replaced by the first 12 hex digits
    of its sha256, and any other token that carries the home path in Claude's slug form hashed the same way."""
    if not isinstance(value, str):
        return value
    value = value.replace(str(HOME), "~")
    value = PROJECT_PATH.sub(lambda m: f"{m.group(1)}sha256-{sha256_text(m.group(2))[:12]}", value)
    return HOME_SLUG_TOKEN.sub(lambda m: f"sha256-{sha256_text(m.group(0))[:12]}", value)


def _public(value):
    """public_text over every string of a nested record."""
    if isinstance(value, str):
        return public_text(value)
    if isinstance(value, list):
        return [_public(v) for v in value]
    if isinstance(value, dict):
        return {k: _public(v) for k, v in value.items()}
    return value


def public_receipt(rec: dict) -> dict:
    """RESIDUALS_DECISION (b) and ROUND4_READ_DECISION (P3): what a published receipt carries. The projects bound back
    from outside the experiment become their count and the sha256 of their sorted names (kept_projects,
    kept_projects_sha256); every other string goes through public_text, so no folder name derived from the home path
    is left in clear. The private ledger (0600) keeps the exact mount operations."""
    if not rec:
        return rec
    kept_prefix = f"{tilde(CLAUDE_PROJECTS)}/"
    own = rec.get("own_project")
    marker = f"[{rec.get('kept_projects')} --bind-try of projects outside the experiment; sha256 of their names " \
             f"{rec.get('kept_projects_sha256')}]"

    def is_kept(op, src, dest) -> bool:
        return op == "bind-try" and str(dest or "").startswith(kept_prefix) and dest != own

    ops, placed = [], False
    for op, src, dest in rec.get("ops") or []:
        if is_kept(op, src, dest):
            if not placed:
                ops.append(["bind-try", marker, None])
                placed = True
            continue
        ops.append([op, public_text(src), public_text(dest)])
    argv, index, placed = [], 0, False
    raw = rec.get("argv") or []
    while index < len(raw):
        if raw[index] == "--bind-try" and index + 2 < len(raw) and is_kept("bind-try", raw[index + 1], raw[index + 2]):
            if not placed:
                argv.append(marker)
                placed = True
            index += 3
            continue
        argv.append(public_text(raw[index]))
        index += 1
    return {**_public({k: v for k, v in rec.items() if k not in ("ops", "argv")}), "ops": ops, "argv": argv,
            "public": True}


# ---------------------------------------------------------------------------------------------------------------------
# Running under the wrapper.

def spawn(plan_: dict, command: list[str], **popen_kwargs) -> tuple[subprocess.Popen, int]:
    """Start command under bwrap: the options through a memfd (--args), the namespace record through a pipe
    (--info-fd). Returns the process and the info pipe's read end, which read_info() reads and closes."""
    info_r, info_w = os.pipe()
    args_fd = os.memfd_create("wrapper-args", 0)
    try:
        os.write(args_fd, b"".join(o.encode() + b"\0" for o in options(plan_, info_w)))
        os.lseek(args_fd, 0, os.SEEK_SET)
        proc = subprocess.Popen([BWRAP, "--args", str(args_fd), "--", *net_command(plan_, command)],
                                pass_fds=(args_fd, info_w), **popen_kwargs)
    except BaseException:
        os.close(info_r)
        raise
    finally:
        os.close(args_fd)
        os.close(info_w)
    return proc, info_r


def read_info(fd: int, timeout: float = 15.0) -> dict | None:
    """bwrap's --info-fd record ({"child-pid", "mnt-namespace", "pid-namespace", ...}), written once the namespace is
    set up and before the command starts."""
    data = b""
    try:
        remaining = timeout
        while remaining > 0:
            ready, _, _ = select.select([fd], [], [], min(remaining, 1.0))
            remaining -= 1.0
            if not ready:
                continue
            chunk = os.read(fd, 65536)
            if not chunk:
                break
            data += chunk
            try:
                return json.loads(data.decode())
            except ValueError:
                continue
    finally:
        os.close(fd)
    try:
        return json.loads(data.decode()) if data.strip() else None
    except ValueError:
        return None


def mnt_namespace(pid) -> str | None:
    try:
        return os.readlink(f"/proc/{pid}/ns/mnt")
    except OSError:
        return None


def info_namespace(info: dict | None) -> str | None:
    value = (info or {}).get("mnt-namespace")
    return f"mnt:[{value}]" if value is not None else None


def ipc_namespace(pid) -> str | None:
    try:
        return os.readlink(f"/proc/{pid}/ns/ipc")
    except OSError:
        return None


def info_ipc_namespace(info: dict | None) -> str | None:
    """bwrap's --info-fd record names the IPC namespace only when it made one (--unshare-ipc)."""
    value = (info or {}).get("ipc-namespace")
    return f"ipc:[{value}]" if value is not None else None


def net_namespace(pid) -> str | None:
    try:
        return os.readlink(f"/proc/{pid}/ns/net")
    except OSError:
        return None


def info_net_namespace(info: dict | None) -> str | None:
    """bwrap's --info-fd record names the network namespace only when it made one (--unshare-net)."""
    value = (info or {}).get("net-namespace")
    return f"net:[{value}]" if value is not None else None


class NetworkForwarder:
    """ROUND6_DECISION (B): the trial's forwards, served outside its namespace by netfilter.py on the Unix sockets the
    wrapper binds in. start() returns once every socket listens and raises otherwise, so a trial never starts without
    its forwards. stop() ends the process and returns its record: whether it ran, the access log's counts and first
    denied requests (forward, method, path, reason), and the gateway forward's model calls, counted at admission, with
    the ones whose response carried no request id listed (netfilter.summarize; round 6e)."""

    def __init__(self, plan_: dict):
        self.plan = plan_
        self.dir = Path(plan_["private"]) / "net" / plan_["client"]
        self.proc: subprocess.Popen | None = None
        self.started = False
        self.error: str | None = None

    def start(self, timeout: float = 20.0) -> "NetworkForwarder":
        network = self.plan.get("network")
        if not network:
            return self
        self.dir.mkdir(parents=True, exist_ok=True)
        os.chmod(self.dir, 0o700)
        spec = {"forwards": network["forwards"], "scope": network["scope"], "access_log": str(self.dir / "access.jsonl")}
        write_json(self.dir / "spec.json", spec, 0o600)
        self.err = open(self.dir / "forwarder.err", "ab")
        self.proc = subprocess.Popen([sys.executable, "-B", str(HERE / "netfilter.py"), "serve", "--spec",
                                      str(self.dir / "spec.json")], stdout=subprocess.PIPE, stderr=self.err,
                                     stdin=subprocess.DEVNULL)
        ready, _, _ = select.select([self.proc.stdout], [], [], timeout)
        line = self.proc.stdout.readline().decode(errors="replace").strip() if ready else ""
        if line != "READY":
            self.error = f"the forwarder did not start ({line or 'no READY in time'})"
            self.stop()
            raise RuntimeError(self.error)
        self.started = True
        return self

    def stop(self) -> dict:
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=10)
        if getattr(self, "err", None):
            self.err.close()
        if not self.plan.get("network"):
            return {"started": False, "reason": "no network record"}
        import netfilter
        return {"decision": ROUND6_DECISION, "started": self.started, "error": self.error,
                "forwards": sorted(self.plan["network"]["forwards"]), **netfilter.summarize(self.dir / "access.jsonl")}


def finish(plan_: dict) -> dict:
    """After the client exits: move its -o answer file into place, and publish its Codex rollouts (main and child
    threads) to the native sessions folder, where collect.py, agentsview and skill_usage read them. Every trial is
    isolated from that folder, so publishing a finished trial's rollout shows it to no trial."""
    work, private = plan_["work"], plan_["private"]
    moved, published = [], []
    last = private / "last"
    if last.is_dir():
        for path in sorted(last.iterdir()):
            dest = work / "last" / path.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            if not dest.exists():
                shutil.move(str(path), str(dest))
                moved.append(path.name)
    source = private / "codex-sessions"
    if source.is_dir():
        for path in sorted(source.rglob("*.jsonl")):
            dest = CODEX_SESSIONS / path.relative_to(source)
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists():
                continue
            try:
                os.link(path, dest)
            except OSError:
                shutil.copy2(path, dest)
            published.append(str(path.relative_to(source)))
    return {"last_moved": moved, "rollouts_published": published}


# ---------------------------------------------------------------------------------------------------------------------
# G13.

def private_dir(cfg: dict, run_root, trial_id: str) -> Path:
    """The trial's private folder, as plan() makes it: derived from the trial id, never read from a receipt."""
    return trial_dir(cfg, Path(run_root)) / "iso" / trial_id


def permitted_binds(cfg: dict, run_root, trial_id: str, client: str, fixture) -> set[tuple]:
    """ROUND4_READ_DECISION (P2-1): every bind a trial's plan may make, as exact (operation, source, destination)
    triples. They are the runtime, the home, the trial's own entries (each from its own path), its private folders
    (from private_dir()) and the inaccessible file over each declared answer source. A project outside the experiment
    bound back onto itself is checked apart (kept_project_bind)."""
    work, private, fixture = trial_dir(cfg, Path(run_root)), private_dir(cfg, run_root, trial_id), Path(fixture)
    triples = {("ro-bind", "/", "/"), ("dev-bind", "/dev", "/dev"), ("bind-try", str(X11_SOCKETS), str(X11_SOCKETS)),
               ("bind", str(fixture), str(fixture)),
               ("ro-bind", str(private / "ai-memory.toml"), str(NEUTRAL_ROOT / ".ai-memory.toml")),
               ("ro-bind", str(work / "bin"), str(work / "bin")),
               ("bind", str(private / "last"), str(work / "last"))}
    triples |= {("overlay", str(path), str(path)) for path in WRITABLE}
    triples |= {("bind-try", str(path), str(path)) for path, _ in PERSISTENT_BINDS}
    triples |= {("overlay", str(CODEX_HOME_REAL / name), str(CODEX_HOME_REAL / name)) for name in CODEX_BIND_BACK}
    triples |= {("bind", str(private / name), str(target)) for _, name, target in CLOSED_FILES}
    triples |= {("bind", str(src), str(src)) for src, _ in RUNTIME_PASS_THROUGH}
    triples.add(("ro-bind", str(private / "net" / client), str(NET_DIR_INSIDE)))
    triples |= {("ro-bind", str(path), str(path))
                for path in (work / "settings" / f"{trial_id}.json", work / "prompts" / f"{trial_id}.txt")}
    if client == "codex":
        triples.add(("bind", str(work / "clones" / trial_id), str(work / "clones" / trial_id)))
    if client == "claude":
        own = CLAUDE_PROJECTS / claude_slug(fixture)
        triples.add(("bind", str(own), str(own)))
    triples |= {("bind", str(private / label), str(target)) for label, target in PRIVATE_STORES}
    triples |= {("ro-bind", str(private / "blocked"), str(path)) for path in _declared(cfg)
                if not any(under(path, root) for root in HIDDEN_ROOTS)}
    return triples


def kept_project_bind(op: str, src, dest, own_project) -> bool:
    """A Claude project outside the experiment, bound back onto itself (plan()'s --bind-try)."""
    if op != "ro-bind-try" or not src or src != dest or dest == own_project:
        return False
    return Path(dest).parent == CLAUDE_PROJECTS and not experiment_project(Path(dest).name)


def check(cfg: dict, run_root, trial_id: str, client: str, rows: dict) -> dict:
    """G13 for one launched trial:
    - Every location listed_locations() requires is in the receipt's hidden list (by its path's sha256), and covered by
      its mount in the receipt's operations, from the trial's own private folder where the cover is one.
    - Every bind is a permitted triple of the trial's plan, and no bind re-exposes a cover placed before it.
    - The receipt's options are the ones its operations give.
    - The client tree ran in mount and IPC namespaces of its own (bwrap's --info-fd record), and every process sampled
      in the tree was in the trial's mount namespace or one below it."""
    failures: list[str] = []
    launched, exit_row, prepared = rows.get("launched") or {}, rows.get("exit") or {}, rows.get("prepared") or {}
    rec = launched.get("isolation")
    if not rec:
        return {"ok": False, "failures": ["no isolation receipt: the trial ran without the wrapper (a run prepared "
                                          "before the structural G13)"]}
    if not str(rec.get("wrapper") or "").endswith("bwrap") or rec.get("decision") != ISOLATION_DECISION:
        failures.append(f"wrapper or decision not the structural G13's: {rec.get('wrapper')} {rec.get('decision')}")
    fixture = prepared.get("fixture_private") or launched.get("fixture_private")
    work = trial_dir(cfg, Path(run_root))
    clone = work / "clones" / trial_id if client == "codex" else None
    required = listed_locations(cfg, run_root, trial_id, client, fixture or "", clone) if fixture else []
    if not fixture:
        failures.append("no fixture path in the prepared row")
    hidden = {h.get("path_sha256"): h for h in rec.get("hidden") or []}
    ops = [(op, untilde(src), untilde(dest)) for op, src, dest in rec.get("ops") or []]
    private = str(private_dir(cfg, run_root, trial_id))
    if untilde(rec.get("private_dir")) != private:
        failures.append(f"the receipt's private folder is not the trial's: {rec.get('private_dir')}")
    store_label = {str(target): label for label, target in PRIVATE_STORES}
    for need in required:
        got = hidden.get(need["path_sha256"])
        if not got:
            failures.append(f"not in the hidden list: {need['location']} ({need['path']})")
            continue
        cover = untilde(need["covered_by"])
        if need["mount"].startswith("tmpfs") and not any(op == "tmpfs" and dest == cover for op, _, dest in ops):
            failures.append(f"no tmpfs over {need['covered_by']} ({need['location']})")
        own_folder = str(Path(private) / store_label.get(cover, "?"))
        if need["mount"] == "private" and ("bind", own_folder, cover) not in ops:
            failures.append(f"no private folder over {need['covered_by']} ({need['location']})")
        if need["mount"] == "inaccessible" and ("ro-bind", str(Path(private) / "blocked"), cover) not in ops \
                and not any(op == "tmpfs" and dest == cover for op, _, dest in ops):
            failures.append(f"no inaccessible bind over {need['covered_by']}")
        # CLOSURE_DECISION: the home folder's overlay, and the private file over each closed file.
        if need["mount"] == "overlay" and ("overlay", cover, cover) not in ops:
            failures.append(f"no temporary overlay over {need['covered_by']} ({need['location']})")
        if need["mount"] == "private file":
            names = [name for _, name, target in CLOSED_FILES if str(target) == cover]
            if not names or ("bind", str(Path(private) / names[0]), cover) not in ops:
                failures.append(f"no private file over {need['covered_by']} ({need['location']})")
    # ROUND4_READ_DECISION (P2-1): every bind is an exact (operation, source, destination) triple of the plan.
    own_project = str(CLAUDE_PROJECTS / claude_slug(fixture)) if fixture and client == "claude" else None
    permitted = permitted_binds(cfg, run_root, trial_id, client, fixture) if fixture else set()
    for op, src, dest in ops:
        if op in ("tmpfs", "proc") or (op, src, dest) in permitted or kept_project_bind(op, src, dest, own_project):
            continue
        expected = sorted(f"{o} {tilde(s)}" for o, s, d in permitted if d == dest)
        if dest and under(dest, CLAUDE_PROJECTS) and dest != str(CLAUDE_PROJECTS) \
                and experiment_project(Path(dest).relative_to(CLAUDE_PROJECTS).parts[0]):
            failures.append(f"an experiment's Claude project bound back: {tilde(dest)}")
        elif expected:
            failures.append(f"{op} {tilde(src)} onto {tilde(dest)}: the plan binds it only as {expected}")
        else:
            failures.append(f"a bind outside the trial's plan: {op} {tilde(src)} -> {tilde(dest)}")
    # Nothing re-exposes a cover: a tmpfs, a private folder or the inaccessible file (declared answer sources included).
    # A later bind of host content at the cover's own path or one of its parents would put the host's view back over it.
    covers = [(index, dest) for index, (op, src, dest) in enumerate(ops)
              if op == "tmpfs" or (op in ("bind", "ro-bind") and src and under(src, private))]
    for index, (op, src, dest) in enumerate(ops):
        if op in ("tmpfs", "proc") or not dest or (src and under(src, private)):
            continue
        for start, cover in covers:
            if index > start and under(cover, dest):
                failures.append(f"{op} {tilde(dest)} after the cover over {tilde(cover)} re-exposes it")
    # The options the receipt hashes are the ones its operations give (bwrap read them from the same plan).
    if fixture and sha256_text("\0".join(options({"ops": ops, "fixture": fixture, "network": rec.get("network")}))) \
            != rec.get("options_sha256"):
        failures.append("the receipt's options sha256 is not the one its operations give")
    # ROUND6_DECISION (B): a network namespace of its own whose forwards are exactly the plan's for this client.
    network_record = rec.get("network")
    if not network_record:
        failures.append("no network record: the trial ran without a network namespace of its own (round 6)")
    elif network_policy(network_record) != network_policy(network_for(client, trial_id)):
        failures.append("the receipt's network (forwards, environment or scope) is not the plan's for this client")
    # RESIDUALS_DECISION (a): the trial's own ai-memory scope, bound above its fixture; a marker in the fixture itself
    # would override it.
    marker = str(NEUTRAL_ROOT / ".ai-memory.toml")
    scope = rec.get("ai_memory_scope") or {}
    if ("ro-bind", str(Path(private) / "ai-memory.toml"), marker) not in ops:
        failures.append("no per-trial ai-memory marker bound above the fixture")
    elif scope.get("project") != trial_id or scope.get("workspace") != AI_MEMORY_WORKSPACE:
        failures.append(f"the ai-memory scope is not the trial's: {scope.get('workspace')}/{scope.get('project')}")
    if scope.get("fixture_has_own_marker"):
        failures.append("the fixture carries its own .ai-memory.toml, which would override the trial's scope")
    # ROUND6_DECISION (A): the gateway's cache read before and after the trial (GET /api/cache): hits 0 at both, entries
    # unchanged. A missing or failed reading voids the trial too (fail closed).
    from common import gateway_cache_window
    cache_window = gateway_cache_window(launched.get("gateway_cache"), exit_row.get("gateway_cache"))
    if cache_window["void"]:
        failures.append("the gateway cache rule (CC 15:57Z): " + "; ".join(cache_window["reasons"]))
    runtime = exit_row.get("isolation_runtime") or {}
    namespace = runtime.get("namespace")
    if not namespace:
        failures.append("no namespace record from the wrapper (--info-fd)")
    elif namespace == runtime.get("host_namespace"):
        failures.append("the client ran in the host's mount namespace")
    ipc = info_ipc_namespace(runtime.get("info"))
    if namespace and not ipc:
        failures.append("no IPC namespace of its own (--unshare-ipc)")
    elif ipc and ipc == runtime.get("host_ipc_namespace"):
        failures.append("the client shared the host's IPC namespace")
    net = info_net_namespace(runtime.get("info"))
    if namespace and not net:
        failures.append("no network namespace of its own (--unshare-net)")
    elif net and net == runtime.get("host_net_namespace"):
        failures.append("the client shared the host's network namespace")
    forwarder = exit_row.get("network_runtime") or {}
    if network_record and not forwarder.get("started"):
        failures.append("no record that the trial's forwards ran (network_runtime)")
    tree = runtime.get("tree") or {}
    if tree.get("outside"):
        failures.append(f"processes of the tree outside the trial's namespace: {tree['outside'][:5]}")
    return {"ok": not failures, "failures": [public_text(f) for f in failures], "required": len(required),
            "hidden": len(hidden), "namespace": namespace, "ipc_namespace": ipc, "net_namespace": net,
            "tree_processes_seen": tree.get("processes_seen"), "tree_in_namespace": tree.get("in_trial_namespace"),
            "tree_in_nested": tree.get("in_nested_namespaces"), "tree_samples": tree.get("samples"),
            "ai_memory_scope": f"{scope.get('workspace')}/{scope.get('project')}" if scope else None,
            "gateway_cache_window": cache_window,
            "network_requests": forwarder.get("requests"), "network_denied": forwarder.get("denied"),
            "wrapper_version": rec.get("version")}


def semantic_cache_served(before: dict | None, after: dict | None) -> int | None:
    """Semantic-cache hits the gateway counted (GET /api/cache) between two readings; None when either is missing."""
    if not before or not after or before.get("error") or after.get("error"):
        return None

    def hits(state):
        return int(((state.get("semantic_cache") or {}).get("hits")) or 0)

    return max(0, hits(after) - hits(before))


# ---------------------------------------------------------------------------------------------------------------------
# The wrapper-only smoke (no model call).

# cat each argument and print one verdict per line: READABLE, ENOENT, EACCES or the error text.
CAT_SCRIPT = ('for p in "$@"; do if e=$(cat -- "$p" 2>&1 >/dev/null); then echo READABLE; else case "$e" in '
              '*"No such file or directory"*) echo ENOENT;; *"Permission denied"*) echo EACCES;; '
              '*) echo "ERROR $e";; esac; fi; done')


def _first_file(root, depth: int = 6, skip=None, suffix: str | None = None) -> Path | None:
    root = Path(root)
    if not root.is_dir():
        return None
    base = len(root.parts)
    for dirpath, dirnames, filenames in os.walk(root):
        here = Path(dirpath)
        if skip and any(under(here, s) for s in skip):
            dirnames[:] = []
            continue
        if len(here.parts) - base >= depth:
            dirnames[:] = []
        dirnames.sort()
        for name in sorted(filenames):
            path = here / name
            if (suffix is None or name.endswith(suffix)) and path.is_file() and not path.is_symlink() \
                    and os.access(path, os.R_OK):
                return path
    return None


def _probe_targets(cfg: dict, run_root: Path | None, skip: list[Path]) -> list[tuple[str, Path]]:
    """A real file in each hidden location, so a failed read in the namespace means the location was hidden."""
    suite = Path((cfg.get("suite") or {}).get("path") or SUITE_DEFAULT)
    oracles = (cfg.get("fixture") or {}).get("oracles_path")
    trial_projects = [d for d in sorted(CLAUDE_PROJECTS.iterdir()) if d.is_dir() and experiment_project(d.name)] \
        if CLAUDE_PROJECTS.is_dir() else []
    transcript = next((p for d in trial_projects for p in [_first_file(d, 3, suffix=".jsonl")] if p), None)
    targets = [("run roots: this run's run.json", run_root / "run.json" if run_root else None),
               ("run roots: another run", _first_file(RUNS_ROOT, 3, skip=[run_root] if run_root else None)),
               ("run roots: the v1 captures", _first_file(V1_ROOT, 2)),
               ("suite cards", suite),
               ("the fixture cache's oracles.json",
                Path(oracles) if oracles else _first_file(FIXTURE_CACHE_ROOT, 6, suffix="oracles.json")),
               ("coordination state: the command-center ledger", COORDINATION_ROOT / "command-center" / "ledger.jsonl"),
               ("another trial's fixture", _first_file(NEUTRAL_ROOT, 3, skip=skip)),
               ("another trial's files", _first_file(TRIAL_ROOT_BASE, 4, skip=skip)),
               ("another trial's Claude transcript", transcript)]
    targets += [(f"the shared {STORE_LABELS[label]}" if label == "codex-sessions" else f"other sessions' {STORE_LABELS[label]}",
                 _first_file(target, 5)) for label, target in PRIVATE_STORES]
    # CLOSURE_DECISION: a real file in each closed store; for Codex's folder, each of its state files by name (the
    # entries a clone links to come back as overlays, so its first file could be one of those).
    for label, store in CLOSED_STORES:
        if store == CODEX_HOME_REAL:
            targets += [(f"{label}: {name}", store / name) for name in CODEX_STATE_PROBES]
            targets.append((f"{label}: log", _first_file(store / "log", 2)))
        else:
            targets.append((label, _first_file(store, 4)))
    return [(label, Path(path)) for label, path in targets if path and Path(path).is_file()]


CODEX_STATE_PROBES = ("history.jsonl", "session_index.jsonl", "logs_2.sqlite", "memories_1.sqlite", "goals_1.sqlite",
                      "queue_1.sqlite", "auth.json")


def closed_file_probes(plan_: dict) -> dict:
    """CLOSURE_DECISION: each closed file reads empty in the namespace (its private file) while the host's is not."""
    out = {}
    for label, _, target in CLOSED_FILES:
        if not target.is_file():
            continue
        result, _ = run_wrapped(plan_, ["sh", "-c", 'wc -c < "$1"', "size", str(target)], timeout=60)
        inside = result.stdout.strip()
        out[label] = {"outside_bytes": target.stat().st_size, "inside_bytes": int(inside) if inside.isdigit() else None,
                      "ok": inside == "0"}
    return out


def _verdicts(out: str, paths: list, rc: int, err: str) -> dict[str, str]:
    lines = out.splitlines()
    return {str(p): (lines[i] if i < len(lines) else f"ERROR rc {rc}: {err.strip()[:200]}") for i, p in enumerate(paths)}


def cat_outside(paths: list) -> dict[str, str]:
    out = subprocess.run(["sh", "-c", CAT_SCRIPT, "cat-probe", *[str(p) for p in paths]], capture_output=True, text=True,
                         timeout=120)
    return _verdicts(out.stdout, paths, out.returncode, out.stderr)


def run_wrapped(plan_: dict, command: list[str], timeout: int = 180) -> tuple[subprocess.CompletedProcess, dict | None]:
    proc, info_fd = spawn(plan_, command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                          stdin=subprocess.DEVNULL)
    info = read_info(info_fd)
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        out, err = proc.communicate()
    return subprocess.CompletedProcess(proc.args, proc.returncode, out, err), info


def cat_inside(plan_: dict, paths: list) -> tuple[dict[str, str], dict | None]:
    result, info = run_wrapped(plan_, ["sh", "-c", CAT_SCRIPT, "cat-probe", *[str(p) for p in paths]])
    return _verdicts(result.stdout, paths, result.returncode, result.stderr), info


def selftest(cfg: dict | None = None, run_root=None, clients: bool = False) -> dict:
    """Wrapper-only smoke, no model call. A synthetic trial gets a fresh fixture and fresh trial files under the real
    roots. In its namespace, `cat` on a real file in each hidden location must fail with ENOENT or EACCES (the smoke
    fails if it can read one), its own inputs, the native home's client configuration and a project outside the
    experiment stay readable, its writes to the shared sessions alias and to the -o folder land in its own folders, and
    PID 1's argv shows none of the hidden paths. A control reads every probe outside the wrapper first: a probe that is
    unreadable there proves nothing and is left out. With clients, each launch path's binary also starts under the
    wrapper: claude and codex --version, Codex's own sandbox nested inside bwrap, the CL6 and CL7 SDK imports, and
    codex app-server --help through a CL7b wrapper."""
    cfg = dict(cfg or {})
    run_root = Path(run_root) if run_root else None
    token = uuid.uuid4().hex[:8]
    fixture, work = NEUTRAL_ROOT / f"st{token}", TRIAL_ROOT_BASE / f"st{token}"
    cfg["trial_root"] = str(work)
    trial_id = str(uuid.uuid4())
    report: dict = {"at": utc_now(), "decision": ISOLATION_DECISION, "wrapper": BWRAP, "version": bwrap_version(),
                    "trial_id": trial_id, "hidden": [], "own": {}, "native": {}, "writes": {}, "namespaces": {},
                    "clients": {}}
    created, forwarders = [fixture, work], []
    try:
        fixture.mkdir(parents=True)
        (fixture / "own.txt").write_text("own fixture input\n")
        for sub in ("bin", "settings", "prompts", "last", "clones"):
            (work / sub).mkdir(parents=True, exist_ok=True)
        (work / "bin" / "c.json").write_text("{}\n")
        settings = work / "settings" / f"{trial_id}.json"
        settings.write_text("{}\n")
        prompt = work / "prompts" / f"{trial_id}.txt"
        prompt.write_text("prompt\n")
        clone = work / "clones" / trial_id
        clone.mkdir()
        (clone / "config.toml").write_text("# clone\n")
        os.symlink(CODEX_SESSIONS, clone / "sessions")
        # A sibling trial of the same run: its -o answer, settings, prompt, clone history and promptfoo output sit
        # beside the trial's own files in the same trial root, and must be hidden all the same.
        sibling = str(uuid.uuid4())
        siblings = {"this run's sibling trial: its -o answer": work / "last" / f"{sibling}.txt",
                    "this run's sibling trial: its settings": work / "settings" / f"{sibling}.json",
                    "this run's sibling trial: its prompt": work / "prompts" / f"{sibling}.txt",
                    "this run's sibling trial: its clone's history": work / "clones" / sibling / "history.jsonl",
                    "this run's sibling trial: its promptfoo output": work / "o" / f"c-{sibling[:8]}.json",
                    "this run's sibling trial: its fixture's draft": NEUTRAL_ROOT / f"st{token}x" / "draft" / "answer.md"}
        created.append(NEUTRAL_ROOT / f"st{token}x")
        # Another trial's scratch file in the host's /tmp, /var/tmp and /dev/shm (round 5: each trial's are private).
        for folder in PRIVATE_TMP:
            siblings[f"the host's {folder} (another trial's scratch file)"] = folder / f"st{token}-host.txt"
            created.append(folder / f"st{token}-host.txt")
        for path in siblings.values():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("a sibling trial's answer\n")
        targets = list(siblings.items()) + _probe_targets(cfg, run_root, skip=[fixture, work, NEUTRAL_ROOT / f"st{token}x"])
        outside = cat_outside([p for _, p in targets])
        report["probes_unreadable_outside"] = [public_text(tilde(p)) for _, p in targets if outside.get(str(p)) != "READABLE"]
        targets = [(label, p) for label, p in targets if outside.get(str(p)) == "READABLE"]
        rollout = next((p for label, p in targets if label.startswith("the shared Codex")), None)
        plans = {"claude": plan(cfg, run_root or RUNS_ROOT, trial_id, "claude", fixture, settings=settings, prompt=prompt),
                 "codex": plan(cfg, run_root or RUNS_ROOT, trial_id, "codex", fixture, clone=clone, prompt=prompt)}
        for client, plan_ in plans.items():
            prepare_dirs(plan_)
            if plan_["own_project"]:
                created.append(plan_["own_project"])
            # ROUND6_DECISION (B): every probe below runs in the trial's network namespace, with its forwards served.
            forwarders.append(NetworkForwarder(plan_).start())
        for client, plan_ in plans.items():
            probes = list(targets)
            if client == "codex" and rollout:
                probes.append(("the shared sessions alias in the trial's clone",
                               clone / "sessions" / rollout.relative_to(CODEX_SESSIONS)))
            inside, info = cat_inside(plan_, [p for _, p in probes])
            report["namespaces"][client] = {"info": info, "namespace": info_namespace(info),
                                            "host_namespace": mnt_namespace("self"),
                                            "ipc_namespace": info_ipc_namespace(info),
                                            "host_ipc_namespace": ipc_namespace("self"),
                                            "net_namespace": info_net_namespace(info),
                                            "host_net_namespace": net_namespace("self")}
            for label, path in probes:
                verdict = inside.get(str(path))
                report["hidden"].append({"client": client, "location": label, "path": public_text(tilde(path)),
                                         "outside": "READABLE" if not label.startswith("the shared sessions alias in")
                                         else "alias of the shared folder",
                                         "inside": verdict, "hidden": verdict in ("ENOENT", "EACCES")})
            own = [fixture / "own.txt", prompt, work / "bin" / "c.json"] + \
                ([settings] if client == "claude" else [clone / "config.toml"])
            # The native home's client configuration (Codex's own folder is closed; a trial's clone carries its copy).
            native = [p for p in (HOME / ".claude" / "settings.json", HOME / ".claude" / "CLAUDE.md") if p.is_file()]
            kept_file = next((f for n in plan_["kept_projects"] for f in [_first_file(CLAUDE_PROJECTS / n, 2)] if f), None)
            readable, _ = cat_inside(plan_, own + native + ([kept_file] if kept_file else []))
            report["own"][client] = {tilde(p): readable.get(str(p)) for p in own}
            report["native"][client] = {public_text(tilde(p)): readable.get(str(p))
                                        for p in native + ([kept_file] if kept_file else [])}
            marker = f"selftest-{token}-{client}.txt"
            created += [HOME / marker, HOME / ".claude" / marker] + [CLAUDE_PROJECTS / n / marker for n in plan_["kept_projects"][:1]]
            write, _ = run_wrapped(plan_, ["sh", "-c", f'echo x > "{CODEX_SESSIONS}/{marker}" && '
                                                       f'echo x > "{work}/last/{marker}" && '
                                                       f'echo x > "/tmp/{marker}" && echo x > "/var/tmp/{marker}" && '
                                                       f'echo x > "/dev/shm/{marker}" && echo x > "/tmp/claude-{UID}/{marker}" && '
                                                       f'echo x > "{HOME}/{marker}" && echo x > "{HOME}/.claude/{marker}"'])
            # CLOSURE_DECISION: a project outside the experiment is bound back read-only.
            kept_dir = next((CLAUDE_PROJECTS / n for n in plan_["kept_projects"] if (CLAUDE_PROJECTS / n).is_dir()), None)
            kept_write = run_wrapped(plan_, ["sh", "-c", f'echo x > "{kept_dir}/{marker}"'])[0] if kept_dir else None
            report.setdefault("closed_files", {})[client] = closed_file_probes(plan_)
            pid1, _ = run_wrapped(plan_, ["sh", "-c", 'tr "\\0" " " < /proc/1/cmdline'])
            argv1 = pid1.stdout.strip()
            report["writes"][client] = {
                "rc": write.returncode,
                "sessions_write_in_private_folder": (plan_["private"] / "codex-sessions" / marker).exists(),
                "sessions_write_not_in_native_folder": not (CODEX_SESSIONS / marker).exists(),
                "last_write_in_private_folder": (plan_["private"] / "last" / marker).exists(),
                "tmp_shm_writes_stay_in_the_namespace": not any((folder / marker).exists() for folder in PRIVATE_TMP),
                "claude_tmp_write_in_private_folder": (plan_["private"] / "claude-tmp" / marker).exists(),
                "home_writes_stay_in_the_namespace": not (HOME / marker).exists() and not (HOME / ".claude" / marker).exists(),
                "kept_project_not_writable": kept_dir is None or (kept_write.returncode != 0 and not (kept_dir / marker).exists()),
                "pid1_argv": argv1[:160],
                "pid1_argv_shows_no_option_or_hidden_path": bool(argv1) and "--tmpfs" not in argv1
                and all(str(root) not in argv1 for root in HIDDEN_ROOTS)}
            # The trial's ai-memory scope: the marker reads back in the namespace and never exists on the host, and
            # ai-memory's own hook finds it from the fixture (`hook --check-capture` inspects the capture policy without
            # spooling or contacting the server; it reports the marker, not the scope values it would send).
            scope, _ = run_wrapped(plan_, ["cat", str(NEUTRAL_ROOT / ".ai-memory.toml")])
            capture = {}
            memory_bin = shutil.which("ai-memory") or str(HOME / ".local" / "bin" / "ai-memory")
            if os.access(memory_bin, os.X_OK):
                payload = json.dumps({"cwd": str(fixture), "session_id": f"selftest-{token}", "hook_event_name": "SessionStart"})
                probe, _ = run_wrapped(plan_, ["sh", "-c", f"printf '%s' {shlex.quote(payload)} | {shlex.quote(memory_bin)} "
                                                           "hook --event session-start --agent claude-code "
                                                           "--server-url http://127.0.0.1:9 --check-capture"])
                try:
                    capture = json.loads(probe.stdout.strip().splitlines()[-1])
                except (ValueError, IndexError):
                    capture = {"unparsed": tilde(probe.stdout.strip())[:200], "rc": probe.returncode}
            report.setdefault("ai_memory", {})[client] = {
                "marker_in_namespace": scope.stdout.strip(),
                "marker_on_host": (NEUTRAL_ROOT / ".ai-memory.toml").exists(),
                "hook_check_capture": {k: capture.get(k) for k in ("marker_present", "admits_capture", "capture_mode")
                                       if k in capture} or capture,
                "ok": scope.returncode == 0 and f'workspace = "{AI_MEMORY_WORKSPACE}"' in scope.stdout
                and f'project = "{trial_id}"' in scope.stdout and not (NEUTRAL_ROOT / ".ai-memory.toml").exists()
                and (not capture or capture.get("marker_present") is True)}
        # ROUND6_DECISION (B): what each client's namespace reaches: /v1 answers through the filter; the gateway's
        # management routes, the other local listeners and any direct egress do not; Claude's model egress reaches only
        # its listed hosts.
        report["network"] = network_probes(plans)
        # Round 6b: which tools under test can run inside a trial (the grader marks the others NOT-TESTABLE).
        report["tools_under_test"] = tool_testability(plans, report["network"])
        # P2-2: the host execution brokers are unreachable from the namespace.
        report["host_brokers"] = host_broker_probes(plans["claude"])
        if clients:
            report["clients"] = _client_checks(plans, fixture, [p for _, p in targets][:1])
    finally:
        for forwarder in forwarders:
            report.setdefault("forwarders", []).append(forwarder.stop())
        for path in created:
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path, ignore_errors=True)
            else:
                path.unlink(missing_ok=True)
    report["probes"] = len(report["hidden"])
    report["pass"] = bool(report["hidden"]) and all(h["hidden"] for h in report["hidden"]) \
        and all(v == "READABLE" for c in report["own"].values() for v in c.values()) \
        and all(v == "READABLE" for c in report["native"].values() for v in c.values()) \
        and all(w["rc"] == 0 and w["sessions_write_in_private_folder"] and w["sessions_write_not_in_native_folder"]
                and w["last_write_in_private_folder"] and w["pid1_argv_shows_no_option_or_hidden_path"]
                and w["tmp_shm_writes_stay_in_the_namespace"] and w["claude_tmp_write_in_private_folder"]
                and w["home_writes_stay_in_the_namespace"] and w["kept_project_not_writable"]
                for w in report["writes"].values()) \
        and all(m["ok"] for m in (report.get("ai_memory") or {}).values()) and len(report.get("ai_memory") or {}) == 2 \
        and all(n["namespace"] and n["namespace"] != n["host_namespace"] for n in report["namespaces"].values()) \
        and all(n["ipc_namespace"] and n["ipc_namespace"] != n["host_ipc_namespace"] for n in report["namespaces"].values()) \
        and bool((report.get("host_brokers") or {}).get("ok")) \
        and bool((report.get("network") or {}).get("ok")) \
        and all(f["ok"] for c in (report.get("closed_files") or {}).values() for f in c.values()) \
        and all(n.get("net_namespace") and n["net_namespace"] != n.get("host_net_namespace")
                for n in report["namespaces"].values()) \
        and all(c.get("ok") for c in report["clients"].values())
    return report


def _wsl_interop_socket() -> Path | None:
    value = os.environ.get("WSL_INTEROP")
    if value and Path(value).is_socket():
        return Path(value)
    return next((p for p in sorted(WSL_INTEROP_DIR.glob("*_interop")) if p.is_socket()), None) \
        if WSL_INTEROP_DIR.is_dir() else None


WINDOWS_CMD = Path("/mnt/c/Windows/System32/cmd.exe")


def broker_attempts() -> dict[str, dict]:
    """Each host execution broker present on this host: its socket, the outside control (the socket exists, and for
    the user manager and Docker a read-only query answers), and the connection a trial would make, which must fail in
    its namespace. The attempts are harmless if a broker did answer: `true` as a transient unit, Docker's /_ping and
    cmd.exe's `ver`."""
    out: dict[str, dict] = {}
    if (RUNTIME_DIR / "systemd" / "private").is_socket() or (RUNTIME_DIR / "bus").is_socket():
        out["the user manager (systemd-run --user)"] = {
            "socket": RUNTIME_DIR / "systemd" / "private",
            "control": ["systemctl", "--user", "is-system-running"],
            "attempt": ["systemd-run", "--user", "--pipe", "--wait", "--quiet", "true"]}
    if (RUNTIME_DIR / "docker.sock").is_socket():
        ping = ["curl", "-s", "-m", "10", "--unix-socket", str(RUNTIME_DIR / "docker.sock"), "http://localhost/_ping"]
        out["the Docker daemon (docker.sock)"] = {"socket": RUNTIME_DIR / "docker.sock", "control": ping, "attempt": ping}
    interop = _wsl_interop_socket()
    if interop and WINDOWS_CMD.exists():
        out["WSL interop (a Windows program)"] = {"socket": interop, "control": None,
                                                  "attempt": [str(WINDOWS_CMD), "/c", "ver"]}
    return out


def host_broker_probes(plan_: dict) -> dict:
    """P2-2's self-test: in the trial's namespace each broker socket (and the ssh-agent's) is absent, each broker's
    connection attempt fails, and the runtime folder is empty with mode 0700. Outside, the same sockets exist."""
    attempts = broker_attempts()
    sockets = [p for p in (*BROKER_SOCKETS, *(a["socket"] for a in attempts.values())) if p.is_socket()]
    sockets = list(dict.fromkeys(sockets))
    script = 'for p in "$@"; do if [ -e "$p" ]; then echo PRESENT; else echo ABSENT; fi; done'
    seen, _ = run_wrapped(plan_, ["sh", "-c", script, "socket-probe", *[str(p) for p in sockets]], timeout=60)
    lines = seen.stdout.split()
    report: dict = {"sockets": {tilde(p): {"outside": "socket", "inside": lines[i] if i < len(lines) else None}
                                for i, p in enumerate(sockets)}, "attempts": {}}
    runtime, _ = run_wrapped(plan_, ["sh", "-c", f'stat -c %a {RUNTIME_DIR}; ls -A {RUNTIME_DIR}'], timeout=60)
    mode_entries = runtime.stdout.split()
    # The folder holds only what the plan mounts there: the forwards' socket folder (round 6) and any pass-through.
    expected = {NET_DIR_INSIDE.name} if plan_.get("network") else set()
    expected |= {Path(p).name for p, _ in RUNTIME_PASS_THROUGH}
    report["runtime_dir"] = {"path": str(RUNTIME_DIR), "mode": mode_entries[0] if mode_entries else None,
                             "entries": sorted(mode_entries[1:]), "expected_entries": sorted(expected),
                             "passed_through": [{"path": tilde(p), "why": why} for p, why in RUNTIME_PASS_THROUGH]}
    for name, attempt in attempts.items():
        if (report["sockets"].get(tilde(attempt["socket"])) or {}).get("inside") != "ABSENT":
            # Fail closed without contacting a broker the namespace can reach.
            report["attempts"][name] = {"socket": tilde(attempt["socket"]), "unreachable": False,
                                        "not_attempted": "its socket is present in the namespace"}
            continue
        control = None
        if attempt["control"]:
            try:
                ran = subprocess.run(attempt["control"], capture_output=True, text=True, timeout=30)
                control = {"rc": ran.returncode, "output": public_text(tilde(ran.stdout.strip()))[:60]}
            except (OSError, subprocess.SubprocessError) as error:
                control = {"error": type(error).__name__}
        inside, _ = run_wrapped(plan_, attempt["attempt"], timeout=90)
        report["attempts"][name] = {
            "socket": tilde(attempt["socket"]), "control_outside": control, "argv": attempt["attempt"],
            "rc_inside": inside.returncode,
            "stderr_inside": public_text(tilde((inside.stderr or inside.stdout).strip().splitlines()[-1]
                                               if (inside.stderr or inside.stdout).strip() else ""))[:160],
            "unreachable": inside.returncode != 0}
    report["ok"] = all(s["inside"] == "ABSENT" for s in report["sockets"].values()) \
        and all(a["unreachable"] for a in report["attempts"].values()) \
        and report["runtime_dir"]["mode"] == "700" \
        and report["runtime_dir"]["entries"] == report["runtime_dir"]["expected_entries"]
    return report


# ROUND6_DECISION (B): local listeners the network probes sample, each asked only where it answers on the host.
LISTENER_SAMPLE = (("Dagu", 21080), ("Serena's MCP server", 24282), ("agentsview", 21808), ("Loki", 21300),
                   ("Grafana", 21301), ("the codebase-memory daemon", 9749), ("the older gateway", 20128),
                   ("Alertmanager", 21093), ("Prometheus", 21090), ("the gateway's WebSocket", 21129))
FORWARDED_PORTS = {forward["listen"] for forward in NET_FORWARDS.values()}
# One line per probe: label|curl exit code|HTTP status|X-Trial-Network header. No body is kept; no credential is sent.
PROBE_SCRIPT = ('probe() { label=$1; shift; out=$(curl -s -o /dev/null -m 20 -w "%{http_code} %header{x-trial-network}" '
                '"$@"); rc=$?; echo "$label|$rc|$out"; }\n')


# Round 6b (CC item task-ns2604-coop-20261006T170607Z, (1)): the tools under test with a network dependency, and where
# each client's configuration points them. A tool whose dependency no forward serves, or which does not start in a
# trial, has its cells marked NOT-TESTABLE with the cause (grade.mark_testability), never NOT-READY.
TOOLS_WITH_DEPENDENCIES = {"socraticode": {"forwards": ("qdrant", "vllm"), "env": ("QDRANT_URL", "LMSTUDIO_URL")},
                           "chrome-devtools": {"start": ["npx", "-y", "chrome-devtools-mcp@1.10.1", "--version"]}}


def _client_mcp_env(client: str, server: str) -> dict:
    """The env one client's own configuration gives an MCP server (URL values only are read)."""
    try:
        if client == "claude":
            servers = json.loads((HOME / ".claude.json").read_text()).get("mcpServers") or {}
        else:
            import tomllib
            servers = tomllib.loads((CODEX_HOME_REAL / "config.toml").read_text()).get("mcp_servers") or {}
    except (OSError, ValueError):
        return {}
    env = (servers.get(server) or {}).get("env") or {}
    return {k: v for k, v in env.items() if isinstance(v, str) and v.startswith("http")}


def tool_testability(plans: dict, network: dict) -> dict:
    """Per tool under test and client: testable, or NOT-TESTABLE with its cause."""
    from urllib.parse import urlparse
    expect = network.get("expect") or {}
    ports = {name: forward["listen"] for name, forward in NET_FORWARDS.items()}
    out: dict = {}
    for client, plan_ in plans.items():
        env = _client_mcp_env(client, "socraticode")
        unserved = []
        for key in TOOLS_WITH_DEPENDENCIES["socraticode"]["env"]:
            port = urlparse(env.get(key, "")).port
            if port not in (ports["qdrant"], ports["vllm"]):
                # GPT read of 50752dde: the host side is probed, not asserted.
                host = "nothing listens there on the host (probed)" if port and not _listening(port) \
                    else "a service listens there on the host but is not forwarded"
                unserved.append(f"{key} points at 127.0.0.1:{port}, which no forward serves; {host}" if port
                                else f"{key} is not configured")
        reachable = expect.get("qdrant health answers") and expect.get("vllm models answer")
        cause = "; ".join(unserved) or (None if reachable else "Qdrant or vLLM did not answer through the forwards")
        out.setdefault("socraticode", {})[client] = {"testable": cause is None, "cause": cause}
        result, _ = run_wrapped(plan_, TOOLS_WITH_DEPENDENCIES["chrome-devtools"]["start"], timeout=120)
        tail = (result.stderr or result.stdout).strip().splitlines()[-1:] or [""]
        out.setdefault("chrome-devtools", {})[client] = {
            "testable": result.returncode == 0,
            "cause": None if result.returncode == 0 else
            f"chrome-devtools-mcp@1.10.1 does not start offline (rc {result.returncode}): {public_text(tilde(tail[0]))[:120]}"}
    return out


def _listening(port: int) -> bool:
    import socket
    with socket.socket() as sock:
        sock.settimeout(2)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def _run_probes(plan_: dict, probes: list[tuple[str, list[str]]]) -> dict:
    script = PROBE_SCRIPT + "".join(f"probe {label} {' '.join(shlex.quote(a) for a in args)}\n" for label, args in probes)
    result, _ = run_wrapped(plan_, ["sh", "-c", script], timeout=240)
    out = {}
    for line in result.stdout.splitlines():
        label, _, rest = line.partition("|")
        rc, _, status = rest.partition("|")
        code, _, header = status.partition(" ")
        out[label] = {"rc": int(rc) if rc.isdigit() else None, "status": code or None, "denied": header.strip() == "denied"}
    return out


def network_probes(plans: dict) -> dict:
    """ROUND6_DECISION (B), the self-test's probe set, run in each client's namespace with its forwards served:
    - Codex: /v1 answers through the gateway filter. /api/health, /api/usage/call-logs and the dashboard are refused by
      the filter, as are dot-segment and percent-encoded detours to them. ai-memory's web interface and another scope's
      handoff are refused, while its /mcp endpoint answers. The OTLP receiver takes only POST.
    - Both: a sample of the other local listeners (each one listening on the host) refuses the connection, and direct
      egress fails.
    - Claude: the model egress proxy tunnels to api.anthropic.com only, and the gateway's port is closed.
    Each verdict keeps the curl exit code, the HTTP status and whether the filter answered."""
    other = str(uuid.uuid4())
    listeners = [(name, port) for name, port in LISTENER_SAMPLE if _listening(port) and port not in FORWARDED_PORTS]
    gw, mem, otlp = "http://127.0.0.1:21128", "http://127.0.0.1:29374", "http://127.0.0.1:21318"
    codex = [("v1_models", [f"{gw}/v1/models"]),
             ("api_health", [f"{gw}/api/health"]),
             ("api_call_logs", [f"{gw}/api/usage/call-logs?limit=1"]),
             ("dashboard", [f"{gw}/"]),
             ("dot_segment", ["--path-as-is", f"{gw}/v1/../api/health"]),
             ("percent_encoded", [f"{gw}/v1/%2e%2e/api/health"]),
             ("ai_memory_web", [f"{mem}/"]),
             ("ai_memory_other_scope", [f"{mem}/handoff?agent=codex&workspace={AI_MEMORY_WORKSPACE}&project={other}"]),
             ("ai_memory_mcp", [f"{mem}/mcp"]),
             ("otlp_get", [f"{otlp}/v1/logs"]),
             ("otlp_post_empty", ["-X", "POST", "-H", "Content-Type: application/x-protobuf", "--data-binary", "",
                                  f"{otlp}/v1/logs"]),
             ("direct_egress", ["--noproxy", "*", "https://example.com/"])]
    # Round 6b: the tools-under-test forwards, path-filtered.
    own_prefix = plans["codex"]["network"]["qdrant_prefix"]
    other_prefix = qdrant_prefix(other)
    qd, vl = "http://127.0.0.1:21633", "http://127.0.0.1:28231"
    codex += [("qdrant_healthz", [f"{qd}/healthz"]),
              ("qdrant_list", [f"{qd}/collections"]),
              ("qdrant_own", [f"{qd}/collections/{own_prefix}codebase_probe"]),
              ("qdrant_other_trial", [f"{qd}/collections/{other_prefix}codebase_probe"]),
              ("qdrant_unprefixed", [f"{qd}/collections/socraticode_metadata"]),
              ("qdrant_other_route", [f"{qd}/telemetry"]),
              ("vllm_models", [f"{vl}/v1/models"]),
              ("vllm_embeddings", ["-X", "POST", "-H", "Content-Type: application/json", "--data", "{}",
                                   f"{vl}/v1/embeddings"]),
              ("vllm_chat", ["-X", "POST", "-H", "Content-Type: application/json", "--data", "{}",
                             f"{vl}/v1/chat/completions"]),
              ("vllm_metrics", [f"{vl}/metrics"]),
              # Round 6d (GPT read of 50752dde, P1): a foreign collection named in an owned route's body, and a grouped
              # query (with_lookup), are refused.
              ("qdrant_foreign_lookup", ["-X", "POST", "-H", "Content-Type: application/json", "--data",
                                         json.dumps({"query": [0.1], "lookup_from": {"collection": f"{other_prefix}x"}}),
                                         f"{qd}/collections/{own_prefix}codebase_probe/points/query"]),
              ("qdrant_groups", ["-X", "POST", "-H", "Content-Type: application/json", "--data",
                                 json.dumps({"group_by": "x", "with_lookup": {"collection": f"{other_prefix}x"}}),
                                 f"{qd}/collections/{own_prefix}codebase_probe/points/query/groups"])]
    codex += [(f"listener_{port}", ["--noproxy", "*", f"http://127.0.0.1:{port}/"]) for _, port in listeners]
    claude = [("model_egress", ["https://api.anthropic.com/"]),
              ("egress_other_host", ["https://example.com/"]),
              ("gateway_port", ["--noproxy", "*", f"{gw}/v1/models"]),
              ("direct_egress", ["--noproxy", "*", "https://api.anthropic.com/"])]
    claude += [(f"listener_{port}", ["--noproxy", "*", f"http://127.0.0.1:{port}/"]) for _, port in listeners]
    results = {"codex": _run_probes(plans["codex"], codex), "claude": _run_probes(plans["claude"], claude)}
    listing = qdrant_listing_probe(plans["codex"])

    def denied(r):
        return bool(r) and r["status"] == "403" and r["denied"]

    def refused(r):
        return bool(r) and r["rc"] == 7

    def answered(r):
        return bool(r) and r["rc"] == 0 and (r["status"] or "000") != "000" and not r["denied"]

    c, k = results["codex"], results["claude"]
    expect = {
        "codex /v1 answers through the filter": answered(c.get("v1_models")) and c["v1_models"]["status"] == "200",
        "codex /api/health refused by the filter": denied(c.get("api_health")),
        "codex /api/usage/call-logs refused by the filter": denied(c.get("api_call_logs")),
        "codex dashboard refused by the filter": denied(c.get("dashboard")),
        "codex dot-segment detour refused": denied(c.get("dot_segment")),
        "codex percent-encoded detour refused": denied(c.get("percent_encoded")),
        "ai-memory web interface refused": denied(c.get("ai_memory_web")),
        "ai-memory handoff of another scope refused": denied(c.get("ai_memory_other_scope")),
        "ai-memory /mcp answers": answered(c.get("ai_memory_mcp")),
        "OTLP GET refused": denied(c.get("otlp_get")),
        "OTLP POST answers": answered(c.get("otlp_post_empty")),
        "codex direct egress fails": bool(c.get("direct_egress")) and c["direct_egress"]["rc"] not in (0, None),
        "claude model egress answers": answered(k.get("model_egress")),
        "claude egress to another host refused": bool(k.get("egress_other_host"))
        and k["egress_other_host"]["rc"] not in (0, None),
        "claude has no gateway port": refused(k.get("gateway_port")),
        "claude direct egress fails": bool(k.get("direct_egress")) and k["direct_egress"]["rc"] not in (0, None),
        "qdrant health answers": answered(c.get("qdrant_healthz")),
        "qdrant collection names answer": answered(c.get("qdrant_list")),
        "qdrant own collections reach Qdrant": answered(c.get("qdrant_own")),
        "qdrant: another trial's collection refused": denied(c.get("qdrant_other_trial")),
        "qdrant: an unprefixed collection refused": denied(c.get("qdrant_unprefixed")),
        "qdrant: other routes refused": denied(c.get("qdrant_other_route")),
        "vllm models answer": answered(c.get("vllm_models")),
        "vllm embeddings reach vLLM": answered(c.get("vllm_embeddings")),
        "vllm: other routes refused": denied(c.get("vllm_chat")) and denied(c.get("vllm_metrics")),
        "qdrant: a foreign collection named in a request body refused": denied(c.get("qdrant_foreign_lookup")),
        "qdrant: grouped queries refused": denied(c.get("qdrant_groups")),
        "qdrant: foreign collection names absent from the listing": listing["foreign_inside"] == 0
        and (listing["foreign_outside"] or 0) > 0,
        "local listeners refused (codex)": all(refused(c.get(f"listener_{port}")) for _, port in listeners),
        "local listeners refused (claude)": all(refused(k.get(f"listener_{port}")) for _, port in listeners)}
    return {"decision": ROUND6_DECISION, "listeners_sampled": [f"{name} ({port})" for name, port in listeners],
            "results": results, "qdrant_listing": listing, "expect": expect,
            "ok": bool(listeners) and all(expect.values())}


def qdrant_listing_probe(plan_: dict) -> dict:
    """Round 6d (P2): GET /collections inside the trial's namespace names only its own collections, while the same
    listing outside holds others' (the control). Counts only; no name is kept. Round 6e: the request inside asks for
    compression, as SocratiCode's client does (Node's fetch sends Accept-Encoding by default), so the probe fails
    unless the forward still answers with a listing it could read and filter."""
    prefix = plan_["network"]["qdrant_prefix"]

    def names(text):
        try:
            return [c.get("name", "") for c in json.loads(text)["result"]["collections"]]
        except (ValueError, KeyError, TypeError):
            return None

    inside, _ = run_wrapped(plan_, ["curl", "-s", "-m", "20", "-H", "Accept-Encoding: gzip, deflate",
                                    "http://127.0.0.1:21633/collections"], timeout=60)
    try:
        outside = subprocess.run(["curl", "-s", "-m", "20", "http://127.0.0.1:21633/collections"], capture_output=True,
                                 text=True, timeout=60).stdout
    except (OSError, subprocess.SubprocessError):
        outside = ""
    seen_in, seen_out = names(inside.stdout), names(outside)
    return {"foreign_inside": None if seen_in is None else sum(1 for n in seen_in if not n.startswith(prefix)),
            "foreign_outside": None if seen_out is None else sum(1 for n in seen_out if not n.startswith(prefix)),
            "envelope_kept": seen_in is not None, "asked_compressed": True}


def _client_checks(plans: dict, fixture: Path, hidden_probe: list[Path]) -> dict:
    """Each launch path's binary starts under the wrapper (no model call)."""
    out = {}
    claude = shutil.which("claude")
    codex = os.path.realpath(HOME / ".local/bin/codex") if (HOME / ".local/bin/codex").exists() else shutil.which("codex")
    sdk_python = HOME / ".local/share/new-wsl-native-stack/tools/claude-agent-sdk/bin/python"
    sdk_dir = HOME / ".local/share/new-wsl-native-stack/tools/codex-sdk/node_modules/@openai/codex-sdk"
    node = shutil.which("node")
    checks = {
        "claude --version (CL1, CL2 and CL6's CLI)": ("claude", [claude, "--version"] if claude else None, "Claude Code"),
        "codex --version (CL3, CL4, CL7, CL7b)": ("codex", [codex, "--version"] if codex else None, "codex"),
        "Codex's own sandbox, nested in bwrap, reads the own fixture": (
            "codex", [codex, "sandbox", "--", "cat", str(fixture / "own.txt")] if codex else None, "own fixture input"),
        "CL6: the Claude Agent SDK imports": (
            "claude", [str(sdk_python), "-c", "import claude_agent_sdk; print('sdk ok')"] if sdk_python.exists() else None,
            "sdk ok"),
        "CL7: the Codex SDK imports": (
            "codex", [node, "-e", f"import({json.dumps(str(sdk_dir / 'dist' / 'index.js'))}).then(() => console.log('sdk ok'))"]
            if node and sdk_dir.exists() else None, "sdk ok")}
    for name, (client, command, expect) in checks.items():
        if not command:
            out[name] = {"ok": False, "why": "binary not found"}
            continue
        result, _ = run_wrapped(plans[client], command)
        text = (result.stdout + result.stderr).strip()
        out[name] = {"ok": result.returncode == 0 and expect in text, "rc": result.returncode, "output": public_text(tilde(text))[:120]}
    if codex and hidden_probe:
        result, _ = run_wrapped(plans["codex"], [codex, "sandbox", "--", "cat", str(hidden_probe[0])])
        out["Codex's own sandbox, nested in bwrap, cannot read a hidden location"] = {
            "ok": result.returncode != 0 and ("No such file" in result.stderr or "Permission denied" in result.stderr),
            "rc": result.returncode, "output": public_text(tilde(result.stderr.strip()))[:120]}
    if codex:
        wrapper = write_app_server_wrapper(plans["codex"], codex)
        result = subprocess.run([str(wrapper), "app-server", "--help"], capture_output=True, text=True, timeout=120,
                                stdin=subprocess.DEVNULL)
        text = (result.stdout + result.stderr).strip()
        info = _load_info(plans["codex"]["private"] / "info.json")
        out["CL7b: codex app-server --help through the provider's wrapper"] = {
            "ok": result.returncode == 0 and "app-server" in text.lower() and bool(info_namespace(info)),
            "rc": result.returncode, "namespace": info_namespace(info), "output": public_text(tilde(text.splitlines()[0]))[:120] if text else ""}
    return out


# ---------------------------------------------------------------------------------------------------------------------
# CL7b: promptfoo's own codex-app-server provider spawns codex itself, so its codex_path_override is a per-attempt wrapper.

def app_server_wrapper_path(cfg: dict, run_root, trial_id: str) -> Path:
    return private_dir(cfg, run_root, trial_id) / "x"


def write_app_server_wrapper(plan_: dict, codex: str) -> Path:
    """The attempt's options file (NUL-separated, with --info-fd 4; mode 0600, as the exact mount operations stay
    private) and the wrapper promptfoo runs as codex: it execs bwrap with those options and the real codex, and bwrap
    writes its namespace record to info.json. A record left by an earlier attempt is removed first, so the census never
    reads a stale child pid."""
    prepare_dirs(plan_)
    private = plan_["private"]
    (private / "info.json").unlink(missing_ok=True)
    args = private / "args"
    args.write_bytes(b"".join(o.encode() + b"\0" for o in options(plan_, 4)))
    os.chmod(args, 0o600)
    wrapper = private / "x"
    # ROUND6_DECISION (B): the network prelude runs ahead of codex in the namespace, as for every other launch path.
    inner = " ".join(shlex.quote(part) for part in net_command(plan_, [codex]))
    wrapper.write_text("#!/bin/sh\n"
                       f"exec {BWRAP} --args 3 -- {inner} \"$@\" "
                       f"3< {shlex.quote(str(private / 'args'))} 4> {shlex.quote(str(private / 'info.json'))}\n")
    os.chmod(wrapper, 0o755)
    return wrapper


def _load_info(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def safe_finish(plan_: dict) -> dict:
    """finish(), recorded instead of raised: a failed move or publish costs the rollout copy (collect.py then reports
    the rollout missing), never the trial's exit row."""
    try:
        return finish(plan_)
    except Exception as error:  # noqa: BLE001
        return {"finish_error": f"{type(error).__name__}: {str(error)[:300]}"}


def _boot_ticks() -> float:
    """Clock ticks since boot, the unit of /proc/<pid>/stat's starttime (proc(5))."""
    return float(Path("/proc/uptime").read_text().split()[0]) * os.sysconf("SC_CLK_TCK")


class AppServerCensus:
    """CL7b's process census (GPT read of 2044b2ab, verification gap). promptfoo's own provider runs the attempt's
    wrapper, so no launcher samples that tree. While the eval runs, a thread reads bwrap's namespace record (info.json,
    its child-pid) every interval, and records the mount namespace of that child and each of its descendants, as
    launcher.run_client does for the other launch paths. A child that started before the census is ignored, so a reused
    pid is never sampled. Never raises."""

    def __init__(self, plan_: dict, interval: float = 2.0):
        self.info_path = Path(plan_["private"]) / "info.json"
        self.interval = interval
        self.census: dict[int, tuple[str, str]] = {}
        self.children: set[int] = set()
        self.samples = 0
        self.errors: list[str] = []
        self._started_ticks = _boot_ticks()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="cl7b-census", daemon=True)

    def start(self) -> "AppServerCensus":
        self._thread.start()
        return self

    def _sample(self) -> None:
        child = (_load_info(self.info_path) or {}).get("child-pid")
        if isinstance(child, int) and child not in self.children:
            try:
                fields = Path(f"/proc/{child}/stat").read_text().rsplit(")", 1)[1].split()
                if float(fields[19]) >= self._started_ticks - 1:
                    self.children.add(child)
            except (OSError, IndexError, ValueError):
                pass
        if not self.children:
            return
        kids: dict[int, list[int]] = {}
        for entry in os.listdir("/proc"):
            if entry.isdigit():
                try:
                    ppid = int(Path(f"/proc/{entry}/stat").read_text().rsplit(")", 1)[1].split()[1])
                except (OSError, IndexError, ValueError):
                    continue
                kids.setdefault(ppid, []).append(int(entry))
        stack, seen = list(self.children), set()
        while stack:
            pid = stack.pop()
            if pid in seen:
                continue
            seen.add(pid)
            if pid not in self.census:
                namespace = mnt_namespace(pid)
                if namespace:
                    self.census[pid] = (namespace, os.path.basename(os.path.realpath(f"/proc/{pid}/exe")))
            stack.extend(kids.get(pid, []))
        self.samples += 1

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self._sample()
            except Exception as error:  # noqa: BLE001 - the census is evidence; it never stops the eval
                self.errors.append(type(error).__name__)
            self._stop.wait(self.interval)

    def stop(self) -> dict:
        """End the census and summarise it in the launcher's tree shape."""
        self._stop.set()
        self._thread.join(timeout=30)
        trial_ns, host_ns = info_namespace(_load_info(self.info_path)), mnt_namespace("self")
        seen = dict(self.census)
        return {"processes_seen": len(seen),
                "in_trial_namespace": sum(1 for ns, _ in seen.values() if ns == trial_ns),
                "in_nested_namespaces": sum(1 for ns, _ in seen.values() if ns not in (trial_ns, host_ns)),
                "outside": [{"exe": exe, "namespace": ns} for ns, exe in seen.values() if ns == host_ns][:20],
                "samples": self.samples, "sampled_by": "block.py (AppServerCensus)",
                "sampling": f"every {self.interval:g} s while the eval ran", "errors": sorted(set(self.errors))}


def app_server_runtime(plan_: dict, tree: dict | None = None) -> dict:
    """After a CL7b eval: the namespace record bwrap wrote, the census of the tree (AppServerCensus), and the published
    rollouts (never raises: CL7b's exit row must be written)."""
    try:
        info = _load_info(plan_["private"] / "info.json")
        runtime = {"info": info, "namespace": info_namespace(info), "host_namespace": mnt_namespace("self"),
                   "host_ipc_namespace": ipc_namespace("self"), "host_net_namespace": net_namespace("self"),
                   "tree": tree or {"processes_seen": None, "in_trial_namespace": None, "outside": [],
                                    "note": "no census was taken"}}
    except Exception as error:  # noqa: BLE001
        runtime = {"runtime_error": f"{type(error).__name__}: {str(error)[:300]}"}
    return {**runtime, **safe_finish(plan_)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_self = sub.add_parser("selftest")
    p_self.add_argument("--run-root")
    p_self.add_argument("--clients", action="store_true")
    p_self.add_argument("--write", action="store_true", help=f"write {SELFTEST_FILE} into the run root")
    args = parser.parse_args(argv)
    if args.cmd == "selftest":
        cfg = load_json(Path(args.run_root) / "run.json") if args.run_root and (Path(args.run_root) / "run.json").exists() else {}
        report = selftest(cfg, args.run_root, clients=args.clients)
        if args.write and args.run_root:
            write_json(Path(args.run_root) / SELFTEST_FILE, report, 0o600)   # private: exact paths and mount details
        print(json.dumps(report, indent=1, sort_keys=True, default=str))
        return 0 if report["pass"] else 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
