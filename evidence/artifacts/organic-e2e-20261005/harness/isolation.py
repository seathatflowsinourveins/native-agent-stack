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
- --die-with-parent;
- --info-fd FD: the child pid and the mount and pid namespace ids.
No --new-session: the launcher's TERM must reach the client for a graceful exit (launcher._kill_group).
The item's fallback, systemd's InaccessiblePaths= in a transient user unit (systemd 259, systemd.exec(5)), is not
used, because bwrap hosts every launch path (selftest(clients=True)).

Optional audit (not implemented, never a gate): a fanotify listener held by root on the hidden roots, filtered to the
trial tree's pids, would corroborate the receipt. An unprivileged listener (Linux 5.13 and later) may mark only inodes,
not a mount or filesystem, and does not receive the pid of the process that generated an event (fanotify_init(2),
man-pages, man7.org), so the pid filter needs CAP_SYS_ADMIN; this harness runs no sudo, so the audit stays an option.

Limits: services reached over a socket run outside the namespace (the ai-memory server, MCP servers configured by URL,
the OmniRoute gateway, a user systemd or Docker daemon), so a file such a service reads for the trial is not hidden by
this mount namespace; the per-trial scoping of those stores (R10) still applies. /tmp and /dev/shm stay shared outside
Claude's own area. A setuid helper (sudo) does not work inside a user namespace. A sandbox the trial starts (Codex's
own, `unshare`, a nested bwrap) runs in a namespace below the trial's, whose mounts are locked there
(mount_namespaces(7)): it cannot unmount a hidden tmpfs.

    python3 -B isolation.py selftest [--run-root <root>] [--clients]   wrapper-only smoke, no model call
"""
from __future__ import annotations

import argparse
import errno
import hashlib
import json
import os
import select
import shlex
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from common import (CODEX_HOME_REAL, FIXTURE_CACHE, HOME, NEUTRAL_ROOT, RUNS_ROOT, TRIAL_ROOT_BASE, V1_ROOT,  # noqa: E402
                    load_json, sha256_file, sha256_json, trial_dir, utc_now)

ISOLATION_DECISION = "task-ns2604-coop-20261006T132948Z"
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
WRITABLE = (HOME, Path("/tmp"), Path("/var/tmp"), Path(f"/run/user/{UID}"))
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
    work = trial_dir(cfg, run_root)
    private = work / "iso" / trial_id
    ops: list[list] = [["ro-bind", "/", "/"], ["dev-bind", "/dev", "/dev"], ["proc", None, "/proc"]]
    ops += [["bind-try", str(path), str(path)] for path in WRITABLE]
    ops += [["tmpfs", None, str(COORDINATION_ROOT)], ["tmpfs", None, str(FIXTURE_CACHE_ROOT)]]
    ops += [["tmpfs", None, str(NEUTRAL_ROOT)], ["bind", str(fixture), str(fixture)]]
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
    mkdirs = [private / "last", *(private / label for label, _ in PRIVATE_STORES), *(t for _, t in PRIVATE_STORES),
              CLAUDE_PROJECTS] + ([own_project] if own_project else [])
    return {"trial_id": trial_id, "client": client, "work": work, "private": private, "fixture": fixture,
            "clone": Path(clone) if clone else None, "settings": settings, "prompt": prompt, "ops": ops,
            "mkdirs": mkdirs, "blocked": blocked, "kept_projects": kept, "own_project": own_project,
            "hidden": listed_locations(cfg, run_root, trial_id, client, fixture, clone)}


def prepare_dirs(plan_: dict) -> None:
    """Create the trial's private folders and every mount target on the host before the launch, so no mount creates a
    host folder as a side effect (a missing target would be created through the writable home)."""
    for path in plan_["mkdirs"]:
        Path(path).mkdir(parents=True, exist_ok=True)
    os.chmod(plan_["private"], 0o700)
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
    out += ["--unshare-pid", "--die-with-parent", "--chdir", str(plan_["fixture"])]
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
            "namespaces": "user (implied: unprivileged bwrap), mount, pid; network, ipc and uts are the host's",
            "environment": "inherited unchanged"}


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

def check(cfg: dict, run_root, trial_id: str, client: str, rows: dict) -> dict:
    """G13 for one launched trial. Every location listed_locations() requires is in the receipt's hidden list (by its
    path's sha256) and covered by its mount in the receipt's operations; nothing is bound back into a hidden root but
    the trial's own entries, and nothing re-exposes a hidden root after its tmpfs; the client tree ran in a mount
    namespace of its own (bwrap's --info-fd record), and every process the launcher sampled in the tree was in it."""
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
    private = untilde(rec.get("private_dir")) or ""
    for need in required:
        got = hidden.get(need["path_sha256"])
        if not got:
            failures.append(f"not in the hidden list: {need['location']} ({need['path']})")
            continue
        cover = untilde(need["covered_by"])
        if need["mount"].startswith("tmpfs") and not any(op == "tmpfs" and dest == cover for op, _, dest in ops):
            failures.append(f"no tmpfs over {need['covered_by']} ({need['location']})")
        if need["mount"] == "private" and not any(op == "bind" and dest == cover and under(src or "", private)
                                                  for op, src, dest in ops):
            failures.append(f"no private folder over {need['covered_by']} ({need['location']})")
        if need["mount"] == "inaccessible" and not any(dest == cover and op in ("ro-bind", "tmpfs") for op, _, dest in ops):
            failures.append(f"no inaccessible bind over {need['covered_by']}")
    # Nothing bound back into a hidden root but the trial's own entries; nothing re-exposes a root after its tmpfs.
    own_project = str(CLAUDE_PROJECTS / claude_slug(fixture)) if fixture and client == "claude" else None
    allowed = {str(fixture), str(work / "bin"), str(work / "last"), str(work / "settings" / f"{trial_id}.json"),
               str(work / "prompts" / f"{trial_id}.txt")} | ({str(clone)} if clone else set())
    tmpfs_at = {dest: index for index, (op, _, dest) in enumerate(ops) if op == "tmpfs"}
    for index, (op, src, dest) in enumerate(ops):
        if op in ("tmpfs", "proc"):
            continue
        for root in HIDDEN_ROOTS:
            start = tmpfs_at.get(str(root))
            if start is None or index < start:
                continue
            if under(str(root), dest):
                failures.append(f"{op} {tilde(dest)} after the tmpfs re-exposes {tilde(root)}")
            elif under(dest, str(root)) and dest != str(root):
                if root == CLAUDE_PROJECTS:
                    name = Path(dest).relative_to(CLAUDE_PROJECTS).parts[0]
                    if experiment_project(name) and dest != own_project:
                        failures.append(f"an experiment's Claude project bound back: {tilde(dest)}")
                elif dest not in allowed:
                    failures.append(f"bound back into {tilde(root)}: {tilde(dest)}")
    runtime = exit_row.get("isolation_runtime") or {}
    namespace = runtime.get("namespace")
    if not namespace:
        failures.append("no namespace record from the wrapper (--info-fd)")
    elif namespace == runtime.get("host_namespace"):
        failures.append("the client ran in the host's mount namespace")
    tree = runtime.get("tree") or {}
    if tree.get("outside"):
        failures.append(f"processes of the tree outside the trial's namespace: {tree['outside'][:5]}")
    return {"ok": not failures, "failures": failures, "required": len(required), "hidden": len(hidden),
            "namespace": namespace, "tree_processes_seen": tree.get("processes_seen"),
            "tree_in_namespace": tree.get("in_trial_namespace"), "wrapper_version": rec.get("version")}


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
        for path in siblings.values():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("a sibling trial's answer\n")
        targets = list(siblings.items()) + _probe_targets(cfg, run_root, skip=[fixture, work, NEUTRAL_ROOT / f"st{token}x"])
        outside = cat_outside([p for _, p in targets])
        report["probes_unreadable_outside"] = [tilde(p) for _, p in targets if outside.get(str(p)) != "READABLE"]
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
                                            "host_namespace": mnt_namespace("self")}
            for label, path in probes:
                verdict = inside.get(str(path))
                report["hidden"].append({"client": client, "location": label, "path": tilde(path),
                                         "outside": "READABLE" if not label.startswith("the shared sessions alias in")
                                         else "alias of the shared folder",
                                         "inside": verdict, "hidden": verdict in ("ENOENT", "EACCES")})
            own = [fixture / "own.txt", prompt, work / "bin" / "c.json"] + \
                ([settings] if client == "claude" else [clone / "config.toml"])
            native = [p for p in (HOME / ".claude" / "settings.json", CODEX_HOME_REAL / "config.toml") if p.is_file()]
            kept_file = next((f for n in plan_["kept_projects"] for f in [_first_file(CLAUDE_PROJECTS / n, 2)] if f), None)
            readable, _ = cat_inside(plan_, own + native + ([kept_file] if kept_file else []))
            report["own"][client] = {tilde(p): readable.get(str(p)) for p in own}
            report["native"][client] = {tilde(p): readable.get(str(p)) for p in native + ([kept_file] if kept_file else [])}
            marker = f"selftest-{token}-{client}.txt"
            write, _ = run_wrapped(plan_, ["sh", "-c", f'echo x > "{CODEX_SESSIONS}/{marker}" && '
                                                       f'echo x > "{work}/last/{marker}"'])
            pid1, _ = run_wrapped(plan_, ["sh", "-c", 'tr "\\0" " " < /proc/1/cmdline'])
            argv1 = pid1.stdout.strip()
            report["writes"][client] = {
                "rc": write.returncode,
                "sessions_write_in_private_folder": (plan_["private"] / "codex-sessions" / marker).exists(),
                "sessions_write_not_in_native_folder": not (CODEX_SESSIONS / marker).exists(),
                "last_write_in_private_folder": (plan_["private"] / "last" / marker).exists(),
                "pid1_argv": argv1[:160],
                "pid1_argv_shows_no_option_or_hidden_path": bool(argv1) and "--tmpfs" not in argv1
                and all(str(root) not in argv1 for root in HIDDEN_ROOTS)}
        if clients:
            report["clients"] = _client_checks(plans, fixture, [p for _, p in targets][:1])
    finally:
        for path in created:
            shutil.rmtree(path, ignore_errors=True)
    report["probes"] = len(report["hidden"])
    report["pass"] = bool(report["hidden"]) and all(h["hidden"] for h in report["hidden"]) \
        and all(v == "READABLE" for c in report["own"].values() for v in c.values()) \
        and all(v == "READABLE" for c in report["native"].values() for v in c.values()) \
        and all(w["rc"] == 0 and w["sessions_write_in_private_folder"] and w["sessions_write_not_in_native_folder"]
                and w["last_write_in_private_folder"] and w["pid1_argv_shows_no_option_or_hidden_path"]
                for w in report["writes"].values()) \
        and all(n["namespace"] and n["namespace"] != n["host_namespace"] for n in report["namespaces"].values()) \
        and all(c.get("ok") for c in report["clients"].values())
    return report


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
        out[name] = {"ok": result.returncode == 0 and expect in text, "rc": result.returncode, "output": text[:120]}
    if codex and hidden_probe:
        result, _ = run_wrapped(plans["codex"], [codex, "sandbox", "--", "cat", str(hidden_probe[0])])
        out["Codex's own sandbox, nested in bwrap, cannot read a hidden location"] = {
            "ok": result.returncode != 0 and ("No such file" in result.stderr or "Permission denied" in result.stderr),
            "rc": result.returncode, "output": result.stderr.strip()[:120]}
    if codex:
        wrapper = write_app_server_wrapper(plans["codex"], codex)
        result = subprocess.run([str(wrapper), "app-server", "--help"], capture_output=True, text=True, timeout=120,
                                stdin=subprocess.DEVNULL)
        text = (result.stdout + result.stderr).strip()
        info = _load_info(plans["codex"]["private"] / "info.json")
        out["CL7b: codex app-server --help through the provider's wrapper"] = {
            "ok": result.returncode == 0 and "app-server" in text.lower() and bool(info_namespace(info)),
            "rc": result.returncode, "namespace": info_namespace(info), "output": text.splitlines()[0][:120] if text else ""}
    return out


# ---------------------------------------------------------------------------------------------------------------------
# CL7b: promptfoo's own codex-app-server provider spawns codex itself, so its codex_path_override is a per-attempt wrapper.

def app_server_wrapper_path(cfg: dict, run_root, trial_id: str) -> Path:
    return trial_dir(cfg, Path(run_root)) / "iso" / trial_id / "x"


def write_app_server_wrapper(plan_: dict, codex: str) -> Path:
    """The attempt's options file (NUL-separated, with --info-fd 4) and the wrapper promptfoo runs as codex: it execs
    bwrap with those options and the real codex, and bwrap writes its namespace record to info.json."""
    prepare_dirs(plan_)
    private = plan_["private"]
    (private / "args").write_bytes(b"".join(o.encode() + b"\0" for o in options(plan_, 4)))
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


def app_server_runtime(plan_: dict) -> dict:
    """After a CL7b eval: the namespace record bwrap wrote, and the published rollouts (never raises: CL7b's exit row
    must be written)."""
    try:
        info = _load_info(plan_["private"] / "info.json")
        runtime = {"info": info, "namespace": info_namespace(info), "host_namespace": mnt_namespace("self"),
                   "tree": {"processes_seen": None, "in_trial_namespace": None, "outside": [],
                            "note": "CL7b runs under promptfoo's provider, which the launcher does not sample; bwrap "
                                    "execs codex"}}
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
            (Path(args.run_root) / SELFTEST_FILE).write_text(json.dumps(report, indent=1, sort_keys=True) + "\n")
        print(json.dumps(report, indent=1, sort_keys=True, default=str))
        return 0 if report["pass"] else 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
