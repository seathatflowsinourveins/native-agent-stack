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
# The command center's decisions on v1.1 (CC item task-ns2604-coop-20261006T105529Z), recorded with their numbers in
# AMENDMENT-v1.1-20261006.md beside the protocol; PROTOCOL-v1.1.md stays verbatim.
CC_V11_DECISIONS = "task-ns2604-coop-20261006T105529Z"
PROTOCOL_T_SECONDS = 900              # §4.4 / §9.1 as written; runs prepared without a completion record keep it
T_SECONDS = 1800                      # decision 1 (finding 3): T is 1,800 s for every cell, CL7b's turn timeout included
CLAUDE_COMPLETION_DEFAULT = "complete-at-result"   # decision 1: a cell completes only when its result event arrives
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


def stop_flag_names(client: str, cell: str | None = None) -> tuple[str, ...]:
    """Flags that refuse a client's launches: STOP (any client), STOP.<client>, DEFER.<client> (a meter or lock
    refusal: the remaining tests wait for the next window and are carried forward, never consumed) and, for a cell,
    HOLD.<cell> (decision 1: a Claude trial with no result event by T holds its cell until the operator has read the
    trial's no_result_diagnosis and removed the flag)."""
    return ("STOP", f"STOP.{client}", f"DEFER.{client}") + ((f"HOLD.{cell}",) if cell else ())


# Exit reasons whose test pilot.py carries forward on resume, as it does a test refused before launch (finding 4). The
# session still counts toward the cap of 14 (the launcher counts every launched Claude session), and the grader keeps
# such a trial out of the session-content gates (G2, G3, G5, G6) while containment, S7 and kept-file gates still apply.
# - meter_headroom_first_event (meter_prior_first_event before the amendment): killed at the trial's own first
#   in-stream meter reading, so it never did the task;
# - rate_limited (decision 6): the trial hit a rate limit, so it is marked and re-run;
# - host_change_rebaselined (decision 7): the host changed while it ran and the run re-baselined, so it is re-run.
CARRY_FORWARD_REASONS = ("meter_prior_first_event", "meter_headroom_first_event", "rate_limited", "host_change_rebaselined")

# §9.1 Claude meter, amended by decision 6. A start compares the trial's expected usage with the remaining headroom of
# each window (1.0 minus its utilization; a window whose resetsAt has passed counts as fresh). There is no quiet-account
# rule and no kill on another session's use: the old prior (0.50 / 0.75), kill thresholds (0.80 / 0.85) and the +0.15
# rise guard read the account-wide meter. A trial that hits a rate limit is marked rate_limited and re-run.
EXPECTED_TRIAL_USAGE = 0.15           # per window, until prepare.py --claude-expected-usage sets the run's own value
METER_CEILING = 1.0                   # a window's limit (utilization 1.0)
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

# Decision 2 (finding 17): a CLI item counts as exposed in a trial only when a native surface that the CLI's own upstream
# installer put in place is loaded in that session (a skill, or a plugin with its skills and hooks); presence on PATH
# alone is not exposure, so such a trial is PATH-only and stays out of the item's OIR. Checked against the session's
# own listing: the Claude init (plugins, skills) and the Codex rollout's world_state skills catalog. Sources:
# - mineru: MinerU's own skill (opendatalab/MinerU skills/mineru at c221cc41, installed by the supported --manifest
#   route; docs/decisions/2026-10-04-2604-e2e-fix-wave-g3-code-docs.md);
# - worktrunk: Worktrunk's own Claude and Codex plugins (`wt config plugins ... install`; the g7-git fix-wave record).
# Not listed, so PATH-only: gh (gh-fix-ci and gh-address-comments come from openai/skills, not from gh's installer)
# and rtk on Codex (`rtk init -g` registers a hook the clone leaves untrusted, §12.3, and Codex does not expand the
# @RTK.md line, §2.2); on Claude rtk is the hook item hook/claude/rtk, not a CLI item.
CLI_NATIVE_SURFACES = {
    "mineru": (("skill", "mineru"),),
    "worktrunk": (("plugin", "worktrunk"), ("skill", "worktrunk")),
}
CLI_TASK_KINDS = ("cli", "cli+skill")
# Decision 2 as confirmed at 11:43Z (CC item task-ns2604-coop-20261006T114319Z): such a CLI stays PATH-only, and the
# trials where a client vendor's official skills repository put a skill for it in the session form their own reported
# stratum, the vendor-skill surface. First case: gh through openai/skills@49f948fa (gh-fix-ci, gh-address-comments;
# adoption/skills/manifest.json).
CLI_VENDOR_SKILL_SURFACES = {
    "gh": (("openai/skills", "gh-fix-ci"), ("openai/skills", "gh-address-comments")),
}

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


# Keys every Codex launch sets itself (CL3's -m and -c model_reasoning_effort; CL7's model and modelReasoningEffort;
# CL7b's model and model_reasoning_effort): a change to them in the omniroute profile file changes no trial.
PROFILE_KEYS_SET_BY_LAUNCH = ("model", "model_reasoning_effort")


def omniroute_profile_effective(path: Path | None = None) -> str | None:
    """Hash of the omniroute profile as the trials see it: the parsed file without the keys each launch sets. The S7
    view gates on this (smoke-20261006a stopped on another lane's edit of the profile's default model, which every cell
    overrides); the raw file hash is kept as information."""
    path = path or CODEX_HOME_REAL / "omniroute.config.toml"
    if not path.exists():
        return None
    try:
        import tomllib
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - an unparsable profile gates on its raw bytes
        return "unparsed:" + sha256_file(path)
    return sha256_json({k: v for k, v in data.items() if k not in PROFILE_KEYS_SET_BY_LAUNCH})


def s7_snapshot(extra_files: dict | None = None) -> dict:
    """Host exposure snapshot (S7). extra_files maps a label to a path (per-trial clone, settings, tarball)."""
    claude_dir = HOME / ".claude"
    snap = {"taken_at": utc_now(), "files": {}, "info": {}}
    for label, path in (("claude/settings.json", claude_dir / "settings.json"), ("claude/CLAUDE.md", claude_dir / "CLAUDE.md"),
                        ("codex/hooks.json", CODEX_HOME_REAL / "hooks.json"), ("codex/AGENTS.md", CODEX_HOME_REAL / "AGENTS.md")):
        snap["files"][label] = sha256_file(path) if path.exists() else None
    profile = CODEX_HOME_REAL / "omniroute.config.toml"
    snap["files"]["codex/omniroute profile (launch-effective)"] = omniroute_profile_effective(profile)
    snap["info"]["codex/omniroute.config.toml (raw, not gated)"] = sha256_file(profile) if profile.exists() else None
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
# In-run re-baseline (decision 7: adopted where it costs at most one extra cell per arm). A persistent host change no
# longer always stops the run: the first one, unless it touches a key in REBASELINE_REFUSED_S7_KEYS or adds a trusted
# project, becomes the run's new S7 baseline, and the trials that were running when it happened are carried forward
# and re-run: at most the Claude chain's one trial and the Codex block in flight (up to its -j trials, 3 for
# codex-native and codex-env in the pilot). A change found between blocks costs no trial. A second persistent change in
# the same run, or a refused key, still stops the run, as before. The 11:43Z confirmation (CC item
# task-ns2604-coop-20261006T114319Z, point 4) accepts that cost because the Codex trials in flight form one cell, the
# arm's concurrency unit; rebaseline_cost_ok() checks it at every re-run and stops the run if it would be exceeded.

REBASELINE_LOG = "rebaselines.jsonl"
REBASELINES_PER_RUN = 1
# Changes a re-baseline never absorbs: the env arm's single factor (§2.2), the Claude settings file whose hash the
# native arm's probe rests on (§2.1: a change needs a new probe), and every trust-bearing key. s7_compare's new_trust
# counts only newly trusted projects, so hook trust (hooks_state), the trust fields of existing projects, removed
# projects and the Codex project table are refused by path.
REBASELINE_REFUSED_S7_KEYS = ("/files/claude/CLAUDE.md", "/files/codex/AGENTS.md", "/files/claude/settings.json",
                              "/codex_config/hooks_state", "/codex_config/projects", "/codex_config/trusted_projects",
                              "/claude_json/trusted_projects", "/claude_json/trust_fields_of_existing_project",
                              "/claude_json/project_removed")


def current_s7_baseline(cfg: dict, root: Path) -> tuple[dict, str]:
    """(snapshot, path) of the S7 baseline in force: the newest in-run re-baseline, else stage 1's."""
    rows = [r for r in read_jsonl(Path(root) / REBASELINE_LOG) if r.get("baseline")]
    path = rows[-1]["baseline"] if rows else cfg["s7_baseline"]
    return load_json(path), path


def rebaseline_cost_ok(root: Path, new: dict) -> tuple[bool, str]:
    """Point 4 of the 11:43Z confirmations: a re-baseline may re-run one Claude trial and the trials in flight of one
    Codex cell (the arm's concurrency unit, up to its -j). The pilot runs one Codex cell at a time, so its in-flight
    trials always form one cell; were the Codex re-runs ever to span two cells, the cap falls back to one trial per arm.
    `new` is the trial about to be marked (client, cell, arm, trial_id)."""
    rows = [r for r in read_jsonl(Path(root) / "ledger.jsonl")
            if r.get("phase") == "exit" and r.get("reason") == "host_change_rebaselined" and r.get("trial_id") != new.get("trial_id")]
    rows.append(new)
    claude = [r for r in rows if r.get("client") == "claude"]
    codex_cells = sorted({str(r.get("cell")) for r in rows if r.get("client") == "codex"})
    if len(claude) <= 1 and len(codex_cells) <= 1:
        return True, f"one Claude trial at most ({len(claude)}) and one Codex cell ({codex_cells})"
    per_arm: dict[str, int] = {}
    for row in rows:
        per_arm[str(row.get("arm"))] = per_arm.get(str(row.get("arm")), 0) + 1
    if all(n <= 1 for n in per_arm.values()):
        return True, f"one trial per arm ({per_arm})"
    return False, f"re-runs exceed the confirmed cost: {len(claude)} Claude trials, Codex cells {codex_cells}, per arm {per_arm}"


def rebaselines_between(root: Path, since_iso: str | None, until_iso: str | None) -> list[dict]:
    """Re-baselines recorded in [since, until] (ISO stamps compare as text)."""
    return [r for r in read_jsonl(Path(root) / REBASELINE_LOG)
            if (not since_iso or r.get("at", "") >= since_iso) and (not until_iso or r.get("at", "") <= until_iso)]


def try_rebaseline(root: Path, vs_baseline: dict, new_trust: bool, after: dict, trigger: dict) -> tuple[bool, str]:
    """Record an in-run re-baseline when decision 7 allows it, under a lock (the Claude and Codex chains run in
    parallel). Returns (re-baselined, why). `after` becomes the baseline; `trigger` names the trial or block."""
    root = Path(root)
    if new_trust:
        return False, "a new trust entry needs a reviewed baseline"
    refused = sorted({key for path in vs_baseline.get("changed") or [] for key in REBASELINE_REFUSED_S7_KEYS
                      if path == key or path.startswith(key + "/")})
    if refused:
        return False, f"a change a re-baseline never absorbs: {refused}"
    lock_path = root / "rebaselines.lock"
    with open(lock_path, "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            rows = read_jsonl(root / REBASELINE_LOG)
            if len(rows) >= REBASELINES_PER_RUN:
                return False, f"the run already used its {REBASELINES_PER_RUN} in-run re-baseline"
            path = root / "s7" / f"baseline-r{len(rows) + 1}.json"
            sha = write_json(path, s7_host_only(after), 0o600)
            append_jsonl(root / REBASELINE_LOG, {"at": utc_now(), "baseline": str(path), "baseline_sha256": sha,
                                                 "changed": (vs_baseline.get("changed") or [])[:20], **trigger,
                                                 "decision": f"{CC_V11_DECISIONS} #7"})
            return True, f"re-baselined to {path.name}"
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


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


def window_utilization(reading: dict, window: str, now: float | None = None) -> float | None:
    """A window's utilization in a reading; a window whose resetsAt (epoch seconds) has passed counts as fresh (0.0),
    so a reading taken before its own window reset no longer blocks starts until the next stream (decision 6)."""
    value = reading.get(window)
    resets = reading.get(f"{window}_resets_at")
    if value is not None and isinstance(resets, (int, float)) and resets <= (time.time() if now is None else now):
        return 0.0
    return value


METER_WINDOWS = ("five_hour", "seven_day")
METER_CALIBRATION = "meter-calibration.json"   # in the run root, written by pilot.py or grade.py meter-calibration
METER_RESOLUTION = 0.01                        # rate_limit_event reports utilization in hundredths


def window_expected(expected, window: str) -> float:
    """A trial's expected usage of one window: one number for both windows, or a per-window mapping (a calibration)."""
    if isinstance(expected, dict):
        value = expected.get(window)
        return float(value) if isinstance(value, (int, float)) else EXPECTED_TRIAL_USAGE
    return float(expected)


def run_expected_usage(cfg: dict | None, root: Path | str | None = None):
    """The expected per-trial usage a start is checked against (decision 6). 0.15 of a window is the starting default
    (confirmed at 11:43Z by CC item task-ns2604-coop-20261006T114319Z, point 5), recalibrated after the first pilot block
    to the measured p90 per trial: <run root>/meter-calibration.json when present, else run.json
    claude_meter.expected_usage, else the default. A calibration is per window."""
    if root is not None and (Path(root) / METER_CALIBRATION).exists():
        try:
            calibrated = load_json(Path(root) / METER_CALIBRATION).get("expected_usage")
        except (OSError, ValueError, AttributeError):
            calibrated = None
        if isinstance(calibrated, dict):
            values = {w: float(calibrated[w]) for w in METER_WINDOWS if isinstance(calibrated.get(w), (int, float))}
            if values:
                return values
    value = ((cfg or {}).get("claude_meter") or {}).get("expected_usage")
    return float(value) if isinstance(value, (int, float)) else EXPECTED_TRIAL_USAGE


def headroom_allows(reading: dict | None, expected=EXPECTED_TRIAL_USAGE, now: float | None = None) -> tuple[bool, str]:
    """Decision 6: start when the trial's expected usage fits in the remaining headroom of both windows. Another
    session's use only matters through the headroom it leaves; the account need not be quiet."""
    if not reading:
        return True, "no-recent-stream: the trial's own first event decides"
    use = {w: window_utilization(reading, w, now) for w in METER_WINDOWS}
    if any(v is None for v in use.values()):
        return True, "reading-incomplete: the trial's own first event decides"
    head = {w: round(METER_CEILING - use[w], 4) for w in METER_WINDOWS}
    need = {w: window_expected(expected, w) for w in METER_WINDOWS}
    state = (f"five_hour={use['five_hour']} seven_day={use['seven_day']} headroom={head['five_hour']}/{head['seven_day']} "
             f"expected={need['five_hour']}/{need['seven_day']}")
    if all(need[w] <= head[w] for w in METER_WINDOWS):
        return True, f"headroom-ok {state}"
    return False, f"headroom-short {state}"


def resume_after(reading: dict | None, expected=EXPECTED_TRIAL_USAGE) -> str | None:
    """When a deferred start fits again: the latest resetsAt among the windows short of headroom (ISO), or None. Limits
    never gate for good: pilot.py clears DEFER.claude on resume once the newest reading allows a start."""
    stamps = []
    for window in METER_WINDOWS:
        value, resets = (reading or {}).get(window), (reading or {}).get(f"{window}_resets_at")
        if value is not None and isinstance(resets, (int, float)) and resets > time.time() \
                and window_expected(expected, window) > round(METER_CEILING - value, 4):
            stamps.append(resets)
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(max(stamps))) if stamps else None


def meter_calibration(root: Path | str) -> dict:
    """Point 5 of the 11:43Z confirmations: the measured p90 of each window's per-trial meter delta (the protocol's
    m_p90, §9.1) over the run's organic Claude trials so far. The deltas are account-wide, so another session's use can
    only raise them; trials carried forward, never launched or without both readings are left out; a p90 below the
    meter's resolution is raised to it. Nearest-rank p90."""
    deltas: dict[str, list[float]] = {w: [] for w in METER_WINDOWS}
    trial_ids = []
    for row in read_jsonl(Path(root) / "ledger.jsonl"):
        if row.get("phase") != "exit" or row.get("client") != "claude" or row.get("launched") is False \
                or row.get("lane") != LANE or row.get("reason") in CARRY_FORWARD_REASONS:
            continue
        first, last = row.get("meter_first") or {}, row.get("meter_last") or {}
        windows = [w for w in METER_WINDOWS if isinstance(first.get(w), (int, float)) and isinstance(last.get(w), (int, float))]
        for window in windows:
            deltas[window].append(round(max(0.0, last[window] - first[window]), 4))
        if windows:
            trial_ids.append(row.get("trial_id"))

    def p90(values: list[float]) -> float:
        ordered = sorted(values)
        return max(METER_RESOLUTION, ordered[max(0, -(-9 * len(ordered) // 10) - 1)])

    return {"expected_usage": {w: p90(v) for w, v in deltas.items() if v}, "trials": len(trial_ids),
            "trial_ids": trial_ids, "deltas": deltas,
            "method": "nearest-rank p90 of meter_last - meter_first per window over the run's organic Claude trials"}


def rate_limit_hit(event: dict) -> bool:
    """Decision 6: a Claude stream event that shows the trial hit a rate limit: a rate_limit_event with status
    rejected, or an error result naming a limit (smoke-20261006c's probe: utilization 1.08, status rejected, then the
    result "You've hit your session limit")."""
    if event.get("type") == "rate_limit_event":
        return (event.get("rate_limit_info") or {}).get("status") == "rejected"
    if event.get("type") == "result" and event.get("is_error"):
        return bool(re.search(r"session limit|usage limit|rate limit|rate_limit|too many requests|\b429\b",
                              str(event.get("result") or ""), re.I))
    return False


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


def forwarded_effort_fields(pipeline) -> dict | None:
    """Decision 8 (RP4, G11): from a call log's pipeline details keep only the effort fields of the request the gateway
    forwarded, never the rest of the payload. None when the gateway exposed no pipeline details for the row."""
    if not isinstance(pipeline, dict):
        return None
    request = pipeline.get("providerRequest") or {}
    reasoning = request.get("reasoning") if isinstance(request.get("reasoning"), dict) else {}
    return {"reasoning.effort": reasoning.get("effort"), "reasoning_effort": request.get("reasoning_effort")}


def gateway_calls_for_threads(thread_ids: set[str], since_iso: str, until_iso: str, max_rows: int = 5000) -> dict:
    """Call-log rows in [since, until] whose request body's client_metadata.thread_id is one of thread_ids. Only the
    fields named here are kept (never the account, the request input or the response); from the pipeline details,
    which the co-op turns on only for pilot runs (decision 8), only the forwarded effort fields."""
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
                found.setdefault(thread, []).append({
                    "id": row.get("id"), "timestamp": stamp, "path": row.get("path"), "status": row.get("status"),
                    "requested_model": row.get("requestedModel"), "backend_model": row.get("model"),
                    "provider": row.get("provider"), "received_effort": (body.get("reasoning") or {}).get("effort"),
                    "received_service_tier": body.get("service_tier"),
                    "forwarded_effort": forwarded_effort_fields(pipeline),
                    "pipeline_exposed": pipeline is not None, "error": bool(row.get("error")),
                    "tokens": row.get("tokens")})
        if (rows[-1].get("timestamp") or "") < since_iso:
            break
    return {"by_thread": found, "rows_scanned": scanned, "errors": errors}
