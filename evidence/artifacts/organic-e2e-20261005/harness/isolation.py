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

Limits:
- Services reached over a socket outside /tmp run outside the namespace: the ai-memory server, MCP servers configured
  by URL, the OmniRoute gateway, and a user systemd or Docker daemon. So a file such a service reads for the trial is
  not hidden by this mount namespace. The grader tags user systemd, Docker, WSL interop and direct HTTP to local
  services, checks every ai-memory call's scope, and the per-trial scoping of those stores (R10) still applies.
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
# Writable over the read-only runtime: the native home, the temporary folders and the user's runtime folder (sockets).
WRITABLE = (HOME, Path(f"/run/user/{UID}"))
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
    for path in _declared(cfg):
        cover = next((root for root in HIDDEN_ROOTS if under(path, root)), path)
        rows.append(("declared answer source", path, cover,
                     "tmpfs" if cover != path or path.is_dir() else "inaccessible" if path.is_file() else "absent"))
    return [_entry(*row) for row in rows]


def plan(cfg: dict, run_root, trial_id: str, client: str, fixture, *, clone=None, settings=None, prompt=None) -> dict:
    """The mount operations for one trial, in bwrap's order: the read-only runtime, the writable home and temporary
    folders, an empty tmpfs over each hidden root with the trial's own entries bound back, and a fresh per-trial folder
    over each per-session store."""
    run_root, fixture = Path(run_root), Path(fixture)
    work, private = trial_dir(cfg, run_root), private_dir(cfg, run_root, trial_id)
    ops: list[list] = [["ro-bind", "/", "/"], ["dev-bind", "/dev", "/dev"], ["proc", None, "/proc"]]
    ops += [["bind-try", str(path), str(path)] for path in WRITABLE]
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
    ops += [["bind-try", str(CLAUDE_PROJECTS / name), str(CLAUDE_PROJECTS / name)] for name in kept]
    if own_project:
        ops.append(["bind", str(own_project), str(own_project)])
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
    mkdirs = [private / "last", *(private / label for label, _ in PRIVATE_STORES),
              *(t for _, t in PRIVATE_STORES if not any(under(t, p) for p in PRIVATE_TMP)),
              CLAUDE_PROJECTS] + ([own_project] if own_project else [])
    return {"trial_id": trial_id, "client": client, "work": work, "private": private, "fixture": fixture,
            "clone": Path(clone) if clone else None, "settings": settings, "prompt": prompt, "ops": ops,
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
            out += ["--tmpfs", dest]
        else:
            out += [f"--{op}", src, dest]
    out += ["--unshare-pid", "--unshare-ipc", "--die-with-parent", "--chdir", str(plan_["fixture"])]
    if info_fd is not None:
        out += ["--info-fd", str(info_fd)]
    return out


def receipt(plan_: dict, command: list[str]) -> dict:
    """The launched row's isolation record: the wrapper's argv as bwrap parses it (options read from the memfd, the
    info fd and the command shown as placeholders), the argv a process listing shows, the mount operations and the
    hidden list with each path's sha256 (and the content's, for a file)."""
    core = options(plan_)
    return {"decision": ISOLATION_DECISION, "wrapper": BWRAP, "version": bwrap_version(),
            "argv": [tilde(a) for a in [BWRAP, *core, "--info-fd", "<fd>", "--", *command]],
            "argv_visible": [BWRAP, "--args", "<fd>", "--", *[tilde(c) for c in command]],
            "options_sha256": sha256_text("\0".join(core)),
            "ops": [[op, tilde(src), tilde(dest)] for op, src, dest in plan_["ops"]],
            "hidden": plan_["hidden"], "kept_projects": len(plan_["kept_projects"]),
            "kept_projects_sha256": sha256_json(plan_["kept_projects"]), "own_project": tilde(plan_["own_project"]),
            "private_dir": tilde(plan_["private"]),
            "ai_memory_scope": {**plan_["ai_memory_scope"], "marker": tilde(plan_["ai_memory_scope"]["marker"]),
                                "decision": RESIDUALS_DECISION},
            "namespaces": "user (implied: unprivileged bwrap), mount, pid, ipc; network and uts are the host's",
            "environment": "inherited unchanged"}


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
        proc = subprocess.Popen([BWRAP, "--args", str(args_fd), "--", *command], pass_fds=(args_fd, info_w),
                                **popen_kwargs)
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
    triples |= {("bind-try", str(path), str(path)) for path in WRITABLE}
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
    if op != "bind-try" or not src or src != dest or dest == own_project:
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
    if fixture and sha256_text("\0".join(options({"ops": ops, "fixture": fixture}))) != rec.get("options_sha256"):
        failures.append("the receipt's options sha256 is not the one its operations give")
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
    # RESIDUALS_DECISION (a), gateway: a semantic-cache hit while a Codex trial ran may have served it another output.
    served = semantic_cache_served(launched.get("gateway_cache"), exit_row.get("gateway_cache")) if client == "codex" else None
    if served:
        failures.append(f"the gateway's semantic cache answered {served} request(s) while the trial ran")
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
    tree = runtime.get("tree") or {}
    if tree.get("outside"):
        failures.append(f"processes of the tree outside the trial's namespace: {tree['outside'][:5]}")
    return {"ok": not failures, "failures": [public_text(f) for f in failures], "required": len(required),
            "hidden": len(hidden), "namespace": namespace, "ipc_namespace": ipc,
            "tree_processes_seen": tree.get("processes_seen"), "tree_in_namespace": tree.get("in_trial_namespace"),
            "tree_in_nested": tree.get("in_nested_namespaces"), "tree_samples": tree.get("samples"),
            "ai_memory_scope": f"{scope.get('workspace')}/{scope.get('project')}" if scope else None,
            "gateway_semantic_cache_hits": served, "wrapper_version": rec.get("version")}


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
    return [(label, Path(path)) for label, path in targets if path and Path(path).is_file()]


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
    created = [fixture, work]
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
            probes = list(targets)
            if client == "codex" and rollout:
                probes.append(("the shared sessions alias in the trial's clone",
                               clone / "sessions" / rollout.relative_to(CODEX_SESSIONS)))
            inside, info = cat_inside(plan_, [p for _, p in probes])
            report["namespaces"][client] = {"info": info, "namespace": info_namespace(info),
                                            "host_namespace": mnt_namespace("self"),
                                            "ipc_namespace": info_ipc_namespace(info),
                                            "host_ipc_namespace": ipc_namespace("self")}
            for label, path in probes:
                verdict = inside.get(str(path))
                report["hidden"].append({"client": client, "location": label, "path": public_text(tilde(path)),
                                         "outside": "READABLE" if not label.startswith("the shared sessions alias in")
                                         else "alias of the shared folder",
                                         "inside": verdict, "hidden": verdict in ("ENOENT", "EACCES")})
            own = [fixture / "own.txt", prompt, work / "bin" / "c.json"] + \
                ([settings] if client == "claude" else [clone / "config.toml"])
            native = [p for p in (HOME / ".claude" / "settings.json", CODEX_HOME_REAL / "config.toml") if p.is_file()]
            kept_file = next((f for n in plan_["kept_projects"] for f in [_first_file(CLAUDE_PROJECTS / n, 2)] if f), None)
            readable, _ = cat_inside(plan_, own + native + ([kept_file] if kept_file else []))
            report["own"][client] = {tilde(p): readable.get(str(p)) for p in own}
            report["native"][client] = {public_text(tilde(p)): readable.get(str(p))
                                        for p in native + ([kept_file] if kept_file else [])}
            marker = f"selftest-{token}-{client}.txt"
            write, _ = run_wrapped(plan_, ["sh", "-c", f'echo x > "{CODEX_SESSIONS}/{marker}" && '
                                                       f'echo x > "{work}/last/{marker}" && '
                                                       f'echo x > "/tmp/{marker}" && echo x > "/var/tmp/{marker}" && '
                                                       f'echo x > "/dev/shm/{marker}" && echo x > "/tmp/claude-{UID}/{marker}"'])
            pid1, _ = run_wrapped(plan_, ["sh", "-c", 'tr "\\0" " " < /proc/1/cmdline'])
            argv1 = pid1.stdout.strip()
            report["writes"][client] = {
                "rc": write.returncode,
                "sessions_write_in_private_folder": (plan_["private"] / "codex-sessions" / marker).exists(),
                "sessions_write_not_in_native_folder": not (CODEX_SESSIONS / marker).exists(),
                "last_write_in_private_folder": (plan_["private"] / "last" / marker).exists(),
                "tmp_shm_writes_stay_in_the_namespace": not any((folder / marker).exists() for folder in PRIVATE_TMP),
                "claude_tmp_write_in_private_folder": (plan_["private"] / "claude-tmp" / marker).exists(),
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
        # A documented residual, recorded and never a pass condition: the gateway's management routes answer from the
        # trial's namespace (the network is the host's) without credentials. Only the HTTP status of two routes the
        # repository's command guard allowlists is kept; the bodies are discarded.
        report["gateway_from_namespace"] = gateway_reachability(plans["claude"])
        if clients:
            report["clients"] = _client_checks(plans, fixture, [p for _, p in targets][:1])
    finally:
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
                for w in report["writes"].values()) \
        and all(m["ok"] for m in (report.get("ai_memory") or {}).values()) and len(report.get("ai_memory") or {}) == 2 \
        and all(n["namespace"] and n["namespace"] != n["host_namespace"] for n in report["namespaces"].values()) \
        and all(n["ipc_namespace"] and n["ipc_namespace"] != n["host_ipc_namespace"] for n in report["namespaces"].values()) \
        and all(c.get("ok") for c in report["clients"].values())
    return report


GATEWAY_PROBES = ("/api/health", "/api/usage/call-logs?limit=1")


def gateway_reachability(plan_: dict) -> dict:
    """The HTTP status of the gateway's health and call-log routes, asked from inside the trial's namespace with no
    credentials (both allowlisted: scripts/hooks/secret_path_guard.py, K4_GW_ROWS). Bodies go to /dev/null."""
    urls = [GATEWAY + path for path in GATEWAY_PROBES]
    script = 'for u in "$@"; do curl -s -o /dev/null -m 15 -w "%{http_code}\\n" "$u" || echo 000; done'
    try:
        result, _ = run_wrapped(plan_, ["sh", "-c", script, "gateway-probe", *urls], timeout=60)
        codes = result.stdout.split()
    except (OSError, subprocess.SubprocessError) as error:
        return {"error": type(error).__name__}
    return {"gateway": GATEWAY, "credentials_sent": False,
            **{f"GET {path}": (codes[i] if i < len(codes) else None) for i, path in enumerate(GATEWAY_PROBES)}}


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
    wrapper.write_text("#!/bin/sh\n"
                       f"exec {BWRAP} --args 3 -- {shlex.quote(codex)} \"$@\" "
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
                   "host_ipc_namespace": ipc_namespace("self"),
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
