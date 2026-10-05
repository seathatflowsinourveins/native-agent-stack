"""Shared constants and helpers for the organic-invocation E2E harness, protocol organic-e2e-v1.1-20261005.

Standard library only. Every host path is derived from the running user's home directory at run time, so this file
carries no personal path. The protocol text is PROTOCOL-v1.1.md beside this directory; section numbers below refer to it.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import subprocess
import time
from pathlib import Path

PROTOCOL_ID = "organic-e2e-v1.1-20261005"
FREEZE_COMMIT = "9e955327"          # §4.2: the fixture is git archive of this commit, never HEAD
EXPERIMENT_BASE = "4c897418"        # §4.2 experiment check range start
HOME = Path.home()
COORD = HOME / ".local/state/native-agent-stack/coordination/ns2604-coop"
RUNS_ROOT = COORD / "organic-e2e-20261005" / "v11"     # the brief's run root (protocol §1 names runs/<run_id>/)
V1_ROOT = COORD / "organic-e2e-20261005"                # v1 captures: stage-0 material only (§12.1)
CLAUDE_LOCK = COORD / "claude-session.lock"            # §4.1 step 5, the host's shared Claude lock
NEUTRAL_ROOT = HOME / ".cache" / "ws"                  # §4.1 NEUTRAL_ROOT: no experiment, tool, client, arm or task word
# Per-trial files whose paths reach a client's argv or environment (settings, prompt, -o file, CODEX_HOME clone). A
# process listing shows argv to the model, so R2 (f) applies to these paths too: they live under a neutral per-run
# directory, never under the run root (whose path names the experiment). Records stay in the run root.
TRIAL_ROOT_BASE = HOME / ".cache" / "wsr"


def trial_dir(cfg: dict, run_root: Path) -> Path:
    """The run's neutral per-trial directory (run.json trial_root); runs prepared before it existed used the run root."""
    return Path(cfg["trial_root"]) if cfg.get("trial_root") else Path(run_root)
FIXTURE_CACHE = HOME / ".cache" / "ns2604-organic-fixtures" / "v11"   # templates and tarballs (never a trial cwd)
USER_CLAUDE_MD = HOME / ".claude" / "CLAUDE.md"
CODEX_HOME_REAL = HOME / ".codex"

LANE = "organic-e2e"                  # R10: prompted runs use LANE_PROMPTED
LANE_PROMPTED = "organic-e2e-prompted"
T_SECONDS = 900                       # §4.4 / §9.1 (run.json claude_completion.t_seconds overrides it only by amendment)
KILL_AFTER = "30s"
CLAUDE_SESSION_CAP = 14               # §9.1 Cap: every Claude session of one run counts (CL2, CL6, env, probe, canary)
POST_RESULT_GRACE_S = 30              # complete-at-result policy: grace between a result event and the group kill
# The stack-currency timer's due file (read by a harness SessionStart hook; hashed in S7, never read for content here).
CURRENCY_DUE_FILE = Path(os.environ.get("XDG_STATE_HOME") or HOME / ".local/state") / "native-agent-stack" / "currency-due.json"
# User-level harness instruction and definition files (G13 and the watcher log reads of these; §2.1 lists them).
USER_HARNESS_PATHS = (HOME / ".claude/CLAUDE.md", HOME / ".claude/RTK.md", HOME / ".codex/AGENTS.md", HOME / ".codex/RTK.md",
                      HOME / ".claude/agents", HOME / ".claude/hooks")
# Host checkout roots outside the fixture (G13: a trial reading the real repository reads its instruction files).
HOST_CHECKOUT_ROOTS = (HOME / "code", HOME / "projects")


def stop_flag_names(client: str) -> tuple[str, ...]:
    """Flags that refuse a client's launches: STOP (any client), STOP.<client>, and DEFER.<client> (a meter or lock
    refusal: the remaining tests wait for the next window and are carried forward, never consumed)."""
    return ("STOP", f"STOP.{client}", f"DEFER.{client}")

# §9.1 Claude meter. The prior is the pilot's start rule; the kill rule censors a running trial.
PRIOR_FIVE_HOUR = 0.50
PRIOR_SEVEN_DAY = 0.75
KILL_FIVE_HOUR = 0.80
KILL_SEVEN_DAY = 0.85
KILL_FIVE_HOUR_RISE = 0.15
METER_MAX_AGE_S = 30 * 60
LOCK_WAIT_S = 3600

# §2.1 harness markers: a hit where the client records loaded instructions invalidates a native trial.
MARKERS = (
    "Native engineering defaults",
    "Top rule: research convergence first",
    "native-agent-stack:codex-user-instructions",
    "native-agent-stack:session-lanes",
    "native-agent-stack:rtk-upstream",
    "TOKEN LANES",
    "# Repository work",
)

# §4.2 strip list and kept paths; the gate searches these names at any depth, in any ASCII case.
STRIP_PATHS = (
    "AGENTS.md", "CLAUDE.md",
    "adoption/scaffold/AGENTS.md", "adoption/scaffold/CLAUDE.md",
    "blueprints/convergence-practice/application-delivery/AGENTS.md",
    "blueprints/convergence-practice/application-delivery/CLAUDE.md",
    "blueprints/us-equities/AGENTS.md", "blueprints/us-equities/CLAUDE.md",
    "examples/claude-native/CLAUDE.md",
    ".claude",
)
KEPT_AGENTS_PATHS = ("tests/fixtures/skill_usage/fake-home/.agents", "adoption/scaffold/.agents")
GATE_NAMES = ("agents.md", "agents.override.md", "claude.md", "claude.local.md", ".claude", ".codex", ".mcp.json")

# R2 (f) and the lint lexicon's fixed part: experiment, client, arm and harness words a model must not see in a
# launch string. Item names and task ids are added from the suite at preparation.
EXPERIMENT_WORDS = (
    "organic", "e2e", "pilot", "smoke", "trial", "probe", "canary", "native", "env", "arm", "claude", "codex",
    "anthropic", "openai", "gpt", "opus", "sonnet", "harness", "experiment", "eval", "promptfoo", "fixture",
    "routing", "lane", "invocation", "oracle", "screen", "ns2604", "nativestack",
)

# R5 lane sets, for reporting lane misses (never a verdict in the pilot).
LANE_SETS = {
    "exact-symbols": ("serena", "jcodemunch", "codebase-memory"),
    "call-graph": ("codebase-memory", "serena"),
    "conceptual-code": ("socraticode", "semble"),
    "docs": ("qmd",),
    "large-output": ("context-mode", "headroom"),
    "compression-exact-recovery": ("headroom",),
    "uniform-flat-arrays": ("toon",),
    "third-party-api-docs": ("chub", "context-mode", "claude-api", "openai-docs"),
    "research-before-code": ("search-first", "deep-research", "native-stack-research"),
    "diagnosis": ("diagnosing-bugs", "debug", "codex:codex-rescue"),
    "security-review": ("security-best-practices", "security-audit", "security-review"),
}

# S4 first-token map for CLI items (after unwrapping and stripping wrappers).
CLI_PROGRAMS = {
    "sg": "ast-grep", "ast-grep": "ast-grep", "difft": "difftastic", "repomix": "repomix", "toon": "toon",
    "markitdown": "markitdown", "chub": "chub", "mcporter": "mcporter", "srt": "srt", "betterleaks": "betterleaks",
    "zizmor": "zizmor", "actionlint": "actionlint", "ccusage": "ccusage", "agentsview": "agentsview",
    "mineru": "mineru", "gh": "gh", "git": "git", "wt": "worktrunk",
}
CLI_WRAPPERS = ("rtk", "env", "sudo", "nohup", "command", "exec", "time", "nice")

# MCP server names as the clients spell them, mapped to the suite's item names.
MCP_SERVER_ITEMS = {
    "plugin_context-mode_context-mode": "context-mode", "context-mode": "context-mode", "context_mode": "context-mode",
    "serena": "serena", "qmd": "qmd", "ai-memory": "ai-memory", "ai_memory": "ai-memory",
    "socraticode": "socraticode", "headroom": "headroom", "codebase-memory": "codebase-memory",
    "codebase_memory": "codebase-memory", "jcodemunch": "jcodemunch", "semble": "semble", "promptfoo": "promptfoo",
}


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def utc_stamp() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path | str, chunk: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            block = handle.read(chunk)
            if not block:
                return digest.hexdigest()
            digest.update(block)


def sha256_json(value) -> str:
    return sha256_bytes(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())


def tree_manifest(root: Path | str) -> dict:
    """{relative path: {"sha256" | "symlink", "bytes"}} for every file and symlink under root, sorted; directories are
    implied. Symlinks are recorded by target and never followed. A file that another process removes or locks during
    the walk is recorded as unreadable, never fatal: a client's own background work (Codex's marketplace upgrade writes
    temporary git objects into CODEX_HOME/.tmp) can outlive the client's exit."""
    root = Path(root)
    entries = {}
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames.sort()
        base = Path(dirpath)
        for name in sorted(filenames) + sorted(d for d in dirnames if (base / d).is_symlink()):
            path = base / name
            rel = path.relative_to(root).as_posix()
            try:
                if path.is_symlink():
                    entries[rel] = {"symlink": os.readlink(path)}
                elif path.is_file():
                    entries[rel] = {"sha256": sha256_file(path), "bytes": path.stat().st_size}
            except (FileNotFoundError, PermissionError) as error:
                entries[rel] = {"unreadable": type(error).__name__}
    return dict(sorted(entries.items()))


def manifest_digest(manifest: dict) -> str:
    return sha256_json(manifest)


def append_jsonl(path: Path, row: dict) -> None:
    """Append one JSON line under an exclusive flock(2), so parallel launchers never interleave rows."""
    path.parent.mkdir(parents=True, exist_ok=True)
    line = (json.dumps(row, sort_keys=True) + "\n").encode()
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        os.write(fd, line)
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    if not Path(path).exists():
        return rows
    for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except ValueError:
            rows.append({"_unparsed": line[:200]})
    return rows


def load_json(path: Path | str):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path | str, value, mode: int = 0o644) -> str:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(value, indent=1, sort_keys=True) + "\n").encode()
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.chmod(tmp, mode)
    os.replace(tmp, path)
    return sha256_bytes(data)


def redact_home(text: str) -> str:
    return text.replace(str(HOME), "~") if isinstance(text, str) else text


def run(cmd, *, cwd=None, env=None, timeout=None, input_bytes=None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, env=env, input=input_bytes, capture_output=True, timeout=timeout)


def clean_login_env(extra: dict | None = None) -> dict:
    """The environment of a clean login shell (§4.1: the coordinator starts promptfoo from one; the launcher's line runs
    from bash -lc). Only identity and session-plumbing variables pass from the caller; every CLAUDE*, CODEX*, GH_TOKEN,
    GITHUB_TOKEN and OTEL_RESOURCE_ATTRIBUTES variable is dropped by construction. bash -l then sets PATH."""
    keep = ("HOME", "USER", "LOGNAME", "LANG", "XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS", "WSL_DISTRO_NAME",
            "WSL_INTEROP", "WSLENV", "DISPLAY", "WAYLAND_DISPLAY")
    env = {key: os.environ[key] for key in keep if key in os.environ}
    env.setdefault("HOME", str(HOME))
    env.setdefault("LANG", "C.UTF-8")
    env["TERM"] = "xterm-256color"
    if extra:
        env.update(extra)
    return env


def login_path() -> str:
    """PATH as a clean login shell sets it."""
    proc = run(["env", "-i", f"HOME={HOME}", f"USER={os.environ.get('USER', '')}", "LANG=C.UTF-8",
                "bash", "-lc", 'printf %s "$PATH"'], timeout=60)
    return proc.stdout.decode().strip()


# ---------------------------------------------------------------------------------------------------------------------
# S7 exposure snapshot and the trust gate (§7 S7, G4). Hashes only; no value is printed.

def _toml_tables(text: str) -> dict[str, str]:
    """Raw text of each top-level TOML table header block, keyed by header (a light reader; tomllib checks validity)."""
    tables, current, lines = {}, "", []
    for line in text.splitlines():
        match = re.match(r"^\s*\[\[?([^\]]+)\]\]?\s*$", line)
        if match:
            tables[current] = "\n".join(lines)
            current, lines = match.group(1).strip(), []
        else:
            lines.append(line)
    tables[current] = "\n".join(lines)
    return tables


def codex_config_parts(path: Path) -> dict:
    """Hashes of the [projects.*], [hooks.state.*] and [mcp_servers.*] parts of a Codex config.toml, plus the trusted
    project set itself (paths are bookkeeping in private run files, never printed by this module)."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return {"present": False}
    try:
        import tomllib
        data = tomllib.loads(text)
        projects = data.get("projects") or {}
        hooks_state = ((data.get("hooks") or {}).get("state")) or {}
        mcp = data.get("mcp_servers") or {}
        trusted = sorted(key for key, value in projects.items()
                         if isinstance(value, dict) and value.get("trust_level") == "trusted")
        return {"present": True, "parse": "ok", "projects": sha256_json(projects), "hooks_state": sha256_json(hooks_state),
                "mcp_servers": sha256_json(mcp), "trusted_projects": trusted, "trusted_count": len(trusted),
                "hooks_state_keys": sorted(hooks_state.keys())}
    except Exception as error:  # noqa: BLE001 - a parse failure is recorded, never fatal to the snapshot
        tables = _toml_tables(text)
        pick = lambda prefix: sha256_json({k: v for k, v in tables.items() if k.startswith(prefix)})  # noqa: E731
        return {"present": True, "parse": f"error:{type(error).__name__}", "projects": pick("projects."),
                "hooks_state": pick("hooks.state"), "mcp_servers": pick("mcp_servers.")}


def claude_json_parts(path: Path) -> dict:
    """~/.claude.json: the top-level mcpServers map and the trust- and MCP-bearing fields of the projects map. The full
    projects map churns with every session's bookkeeping (lastCost, lastSessionId ...), so it is recorded separately and
    never gated."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        return {"present": False, "error": type(error).__name__}
    projects = data.get("projects") or {}
    trust_fields = ("hasTrustDialogAccepted", "allowedTools", "mcpServers", "enabledMcpjsonServers",
                    "disabledMcpjsonServers", "hasClaudeMdExternalIncludesApproved")
    by_key = {key: sha256_json({field: value.get(field) for field in trust_fields}) for key, value in projects.items()
              if isinstance(value, dict)}
    trusted = sorted(key for key, value in projects.items() if isinstance(value, dict) and value.get("hasTrustDialogAccepted"))
    return {"present": True, "mcpServers": sha256_json(data.get("mcpServers") or {}),
            "trust_fields_by_key": by_key, "trusted_projects": trusted, "trusted_count": len(trusted),
            "project_keys": sorted(projects.keys()), "projects_full_info_only": sha256_json(projects)}


def _listing(root: Path, depth: int = 2) -> list[str]:
    out = []
    if not root.exists():
        return out
    base_depth = len(root.parts)
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        here = Path(dirpath)
        if len(here.parts) - base_depth >= depth:
            dirnames[:] = []
        for name in sorted(dirnames + filenames):
            path = here / name
            out.append(path.relative_to(root).as_posix() + ("@" + os.readlink(path) if path.is_symlink() else ""))
    return sorted(out)


def s7_snapshot(extra_files: dict | None = None) -> dict:
    """Host exposure snapshot (S7). extra_files maps a label to a path (per-trial clone, settings, tarball)."""
    claude_dir = HOME / ".claude"
    snap = {"taken_at": utc_now(), "files": {}}
    for label, path in (("claude/settings.json", claude_dir / "settings.json"), ("claude/CLAUDE.md", claude_dir / "CLAUDE.md"),
                        ("codex/hooks.json", CODEX_HOME_REAL / "hooks.json"), ("codex/AGENTS.md", CODEX_HOME_REAL / "AGENTS.md"),
                        ("codex/omniroute.config.toml", CODEX_HOME_REAL / "omniroute.config.toml")):
        snap["files"][label] = sha256_file(path) if path.exists() else None
    agents = sorted((claude_dir / "agents").glob("*.md"))
    snap["files"]["claude/agents/*.md"] = sha256_json({p.name: sha256_file(p) for p in agents})
    # The currency due file feeds a harness SessionStart hook's additionalContext (finding 16): its presence and hash.
    snap["files"]["state/currency-due.json"] = sha256_file(CURRENCY_DUE_FILE) if CURRENCY_DUE_FILE.is_file() else None
    rules = CODEX_HOME_REAL / "rules"
    snap["files"]["codex/rules/"] = sha256_json({p.name: sha256_file(p) for p in sorted(rules.glob("*"))}) if rules.exists() else None
    snap["claude_json"] = claude_json_parts(HOME / ".claude.json")
    snap["codex_config"] = codex_config_parts(CODEX_HOME_REAL / "config.toml")
    snap["skill_listings"] = {
        "agents/skills": sha256_json(_listing(HOME / ".agents" / "skills", 1)),
        "claude/skills": sha256_json(_listing(claude_dir / "skills", 1)),
        "codex/skills": sha256_json(_listing(CODEX_HOME_REAL / "skills", 2)),
        "claude/plugins/cache": sha256_json(_listing(claude_dir / "plugins" / "cache", 3)),
        "codex/plugins/cache": sha256_json(_listing(CODEX_HOME_REAL / "plugins" / "cache", 3)),
    }
    if extra_files:
        snap["trial_files"] = {}
        for label, path in extra_files.items():
            path = Path(path)
            if path.is_dir():
                snap["trial_files"][label] = manifest_digest(tree_manifest(path))
            elif path.exists():
                snap["trial_files"][label] = sha256_file(path)
            else:
                snap["trial_files"][label] = None
            if label == "clone":
                # The implementation brief's trust gate: the clone's [projects] (and [hooks.state]) before and after.
                snap["clone_config"] = codex_config_parts(path / "config.toml")
    return snap


def s7_gate_view(snap: dict) -> dict:
    """The gated part of a snapshot: host configuration hashes, the trusted-project sets and top-level mcpServers.
    ~/.claude.json bookkeeping is never gated; per-project trust fields are compared for pre-existing keys only (see
    s7_compare), because a headless session may add an untrusted entry for its own cwd."""
    cj, cc = snap.get("claude_json") or {}, snap.get("codex_config") or {}
    view = {"files": snap.get("files"), "skill_listings": snap.get("skill_listings"),
            "claude_json": {k: cj.get(k) for k in ("mcpServers", "trusted_projects")},
            "codex_config": {k: cc.get(k) for k in ("projects", "hooks_state", "mcp_servers", "trusted_projects")}}
    if snap.get("clone_config"):
        clone = snap["clone_config"]
        view["clone_config"] = {k: clone.get(k) for k in ("projects", "hooks_state", "trusted_projects")}
    return view


def stable_s7_snapshot(extra_files: dict | None = None, tries: int = 8, wait_s: float = 2.0) -> tuple[dict, dict]:
    """A snapshot whose gated view held still across two consecutive reads (at most `tries`, `wait_s` apart). Codex
    sessions re-sync the remote curated plugins into the shared ~/.codex/plugins/cache at start (a clone symlinks
    plugins, §4.3), so a single read can catch another session's sync half done. Returns (snapshot, {stable, reads})."""
    previous = s7_snapshot(extra_files)
    for read in range(2, tries + 1):
        time.sleep(wait_s)
        current = s7_snapshot(extra_files)
        if s7_compare(previous, current)["equal"]:
            return current, {"stable": True, "reads": read}
        previous = current
    return previous, {"stable": False, "reads": tries}


def s7_host_only(snap: dict) -> dict:
    """The snapshot without its per-trial clone part, for a comparison with the stage-1 baseline (which has none)."""
    return {k: v for k, v in snap.items() if k not in ("clone_config", "trial_files")}


def s7_persistent_change(baseline: dict, before: dict, after: dict) -> dict:
    """The S7 judgement for one trial or block: a persistent change is an `after` view that differs from the stage-1
    baseline, or any new trust entry (against `before` or the baseline). A `before` that differs from both `after` and
    the baseline is a transient another session left mid-write, recorded, never a STOP."""
    within = s7_compare(before, after)
    vs_base = s7_compare(s7_host_only(baseline), s7_host_only(after))
    new_trust = any(within["new_trust"].values()) or any(vs_base["new_trust"].values())
    return {"within": within, "vs_baseline": vs_base, "persistent": (not vs_base["equal"]) or new_trust,
            "transient_before": (not within["equal"]) and vs_base["equal"]}


def s7_compare(before: dict, after: dict) -> dict:
    """{equal, changed: [paths], new_trust: {claude, codex, clone}, new_claude_project_keys: n} for two snapshots."""
    a, b = s7_gate_view(before), s7_gate_view(after)
    changed = []

    def walk(x, y, prefix=""):
        if isinstance(x, dict) and isinstance(y, dict):
            for key in sorted(set(x) | set(y)):
                walk(x.get(key), y.get(key), f"{prefix}/{key}")
        elif x != y:
            changed.append(prefix)
    walk(a, b)
    keys_before = (before.get("claude_json") or {}).get("trust_fields_by_key") or {}
    keys_after = (after.get("claude_json") or {}).get("trust_fields_by_key") or {}
    for key in sorted(set(keys_before) & set(keys_after)):
        if keys_before[key] != keys_after[key]:
            changed.append("/claude_json/trust_fields_of_existing_project")
            break
    if set(keys_before) - set(keys_after):
        changed.append("/claude_json/project_removed")

    def trusted(snap, part):
        return set((snap.get(part) or {}).get("trusted_projects") or [])
    new = {part: sorted(trusted(after, key) - trusted(before, key))
           for part, key in (("claude", "claude_json"), ("codex", "codex_config"), ("clone", "clone_config"))}
    new_keys = sorted(set(keys_after) - set(keys_before))
    return {"equal": not changed, "changed": changed, "new_trust": {k: len(v) for k, v in new.items()},
            "new_trust_paths_private": new, "new_claude_project_keys": len(new_keys)}


# ---------------------------------------------------------------------------------------------------------------------
# Meter (§9.1): rate_limit_event readings from Claude streams.

def rate_limit_readings(events) -> list[dict]:
    out = []
    for event in events:
        if isinstance(event, dict) and event.get("type") == "rate_limit_event":
            windows = ((event.get("rate_limit_info") or {}).get("unifiedWindows")) or {}
            five = (windows.get("five_hour") or {}).get("utilization")
            seven = (windows.get("seven_day") or {}).get("utilization")
            out.append({"five_hour": five, "seven_day": seven,
                        "five_hour_resets_at": (windows.get("five_hour") or {}).get("resetsAt"),
                        "seven_day_resets_at": (windows.get("seven_day") or {}).get("resetsAt"),
                        "status": (event.get("rate_limit_info") or {}).get("status")})
    return out


def parse_stream_text(text: str) -> list:
    """Events of a Claude stream: JSONL (stream-json) or one JSON array (the retired --output-format json)."""
    text = text.strip()
    if not text:
        return []
    if text.startswith("["):
        try:
            value = json.loads(text)
            return value if isinstance(value, list) else [value]
        except ValueError:
            pass
    events = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                events.append(json.loads(line))
            except ValueError:
                continue
    return events


def newest_meter_reading(search_roots=None, max_age_s: int = METER_MAX_AGE_S) -> dict | None:
    """The latest rate_limit_event from the newest Claude stream on this host that is at most max_age_s old (§9.1).
    Searched: every v1.1 run's raw streams, the v1 captures and the U1 probe outputs."""
    roots = search_roots or [RUNS_ROOT, V1_ROOT, HOME / ".cache" / "ns2604-organic-fixtures" / "probe-noharness"]
    candidates = []
    now = time.time()
    for root in roots:
        root = Path(root)
        if not root.exists():
            continue
        for pattern in ("**/raw/*.stream.jsonl", "**/*claude*.out", "*.json"):
            for path in root.glob(pattern):
                if "/selftest-" in str(path):   # stand-in clients' streams carry no real meter reading
                    continue
                try:
                    age = now - path.stat().st_mtime
                except OSError:
                    continue
                if age <= max_age_s:
                    candidates.append((path.stat().st_mtime, path))
    for _, path in sorted(candidates, reverse=True):
        try:
            readings = rate_limit_readings(parse_stream_text(path.read_text(encoding="utf-8", errors="replace")))
        except OSError:
            continue
        if readings:
            reading = dict(readings[-1])
            reading["source_mtime"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(path.stat().st_mtime))
            reading["source_private"] = str(path)
            return reading
    return None


def prior_allows(reading: dict | None) -> tuple[bool, str]:
    if not reading:
        return True, "no-recent-stream: the trial's own first event decides"
    five, seven = reading.get("five_hour"), reading.get("seven_day")
    if five is None or seven is None:
        return True, "reading-incomplete: the trial's own first event decides"
    if five < PRIOR_FIVE_HOUR and seven < PRIOR_SEVEN_DAY:
        return True, f"prior-ok five_hour={five} seven_day={seven}"
    return False, f"prior-refused five_hour={five} seven_day={seven}"


# ---------------------------------------------------------------------------------------------------------------------
# Gateway (CL9): build from the serving process, call logs over the guard-approved read routes only.

GATEWAY = "http://127.0.0.1:21128"


def gateway_build() -> str | None:
    """The OmniRoute build directory name of the process serving the gateway (`.../omniroute-builds/<build>/...`)."""
    try:
        listing = run(["ps", "-eo", "args"], timeout=20).stdout.decode(errors="replace")
    except Exception:  # noqa: BLE001
        return None
    for line in listing.splitlines():
        if "omniroute" in line and " serve" in line:
            match = re.search(r"omniroute-builds/([^/\s]+)/", line)
            if match:
                return match.group(1)
    return None


def gateway_get(path: str, timeout: int = 30):
    import urllib.request
    with urllib.request.urlopen(GATEWAY + path, timeout=timeout) as response:
        return json.load(response)


def gateway_calls_for_threads(thread_ids: set[str], since_iso: str, until_iso: str, max_rows: int = 5000) -> dict:
    """Call-log rows in [since, until] whose request body's client_metadata.thread_id is one of thread_ids. Only the
    fields named here are kept (never the account, the request input or the response)."""
    found, scanned, offset, errors = {}, 0, 0, []
    while scanned < max_rows:
        try:
            rows = gateway_get(f"/api/usage/call-logs?limit=500&offset={offset}")
        except Exception as error:  # noqa: BLE001
            errors.append(type(error).__name__)
            break
        if not rows:
            break
        scanned += len(rows)
        offset += len(rows)
        for row in rows:
            stamp = row.get("timestamp") or ""
            if stamp < since_iso or stamp > until_iso:
                continue
            try:
                detail = gateway_get(f"/api/usage/call-logs/{row['id']}")
            except Exception as error:  # noqa: BLE001
                errors.append(type(error).__name__)
                continue
            body = detail.get("requestBody") or {}
            meta = body.get("client_metadata") or {}
            thread = meta.get("thread_id")
            if thread in thread_ids:
                pipeline = detail.get("pipelinePayloads")
                forwarded = None
                if isinstance(pipeline, dict):
                    forwarded = ((pipeline.get("providerRequest") or {}).get("reasoning"))
                found.setdefault(thread, []).append({
                    "id": row.get("id"), "timestamp": stamp, "path": row.get("path"), "status": row.get("status"),
                    "requested_model": row.get("requestedModel"), "backend_model": row.get("model"),
                    "provider": row.get("provider"), "received_effort": (body.get("reasoning") or {}).get("effort"),
                    "received_service_tier": body.get("service_tier"), "forwarded_reasoning": forwarded,
                    "pipeline_exposed": pipeline is not None, "error": bool(row.get("error")),
                    "tokens": row.get("tokens")})
        if (rows[-1].get("timestamp") or "") < since_iso:
            break
    return {"by_thread": found, "rows_scanned": scanned, "errors": errors}
