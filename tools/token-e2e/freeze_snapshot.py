#!/usr/bin/env python3
"""Freeze snapshot for the #381 window W: capture the frozen environment, compare two captures, check one against
the sealed expectations, and list the frozen set. Read-only glue over existing commands and file hashes; it decides nothing.

  freeze_snapshot.py capture --label NAME --out DIR [--repo CHECKOUT] [--config freeze.json] [--no-usage-probe]
  freeze_snapshot.py compare A.json B.json [--full]
  freeze_snapshot.py check CAPTURE.json --expected EXPECTED.json [--quiet]
  freeze_snapshot.py list-frozen [--config freeze.json] [--repo CHECKOUT] [--all] [--json]

`capture` writes DIR/freeze-NAME.json (private, mode 0600: item values plus the home- or checkout-relative path each
value was read from) and DIR/freeze-NAME.sanitized.json (the same items without paths). A sanitized capture is also the
format of the expectations file `check` reads: the owner captures at seal and publishes that file. Every item has an id,
a class (frozen or informational), a status (ok, missing, error, not_applicable), a value and a slash-free method.
Frozen items must not change between W-open and W-close; informational items (time, capacity) are listed and never fail.

The tool never prints or stores an environment value, a token, a host name or a user name, and reads no credential store.
Two layers keep that true: collectors derive only booleans, counts, hashes, versions, model aliases and documented setting
values (a permission rule is counted, never kept), and a final guard refuses (exit 3, nothing written) any output string
that carries an environment value of eight characters or more (except the model alias in CLAUDE_CODE_SUBAGENT_MODEL), a
permission rule, the home or checkout path, or the user or host name. Paths named
in the configuration, read from a unit file or named by CHILD_USAGE_SHELL_PARSER must lie inside the checkout or the home
directory, and the three credential stores (~/.claude.json, ~/.claude/.credentials.json, ~/.codex/auth.json) are refused by
name, by symlink and by inode. list-frozen prints no path a configuration names, and a location that came from an
environment value is not stored. Scanners are linear character scans; no regular expression is used.

Exit status: 0 done (drift, if any, is informational) or all checked items pass, 1 a frozen item drifted or failed,
2 usage, input or configuration error, 3 the privacy guard refused the output.

Sources for the rules implemented here (no upstream implementation of this glue exists):
  #381 README "Procedure" step 2 and RUNBOOK "Freeze and preflight" (this repository, evidence/artifacts/
  token-adoption-e2e-20260926): the frozen list and the no-change-inside-a-run-window rule;
  systemctl(1) "show" (systemd 255): `systemctl --user show UNIT -p PROPERTY` is the computer-parsable form;
  git(1) `--no-optional-locks` and git-status(1) `--porcelain --untracked-files=no`: a status read that writes nothing;
  https://code.claude.com/docs/en/settings-reference (fetched 2026-09-29): the behaviour settings this tool reads from each
  settings file and their documented values (permissions.defaultMode, permissions.allow|deny|ask, crossSessionInbound, ...);
  the tools' own --version outputs and the command outputs observed on 2026-09-29 (claude 2.1.284 mcp list and
  -p --output-format json, qmd 2.8.3 status, adoption_status.py and codex_quota.py --json), recorded in tests/;
  examples/claude-native/workflows/child-usage.mjs verifiedShellParser (unmerged at this base; the function is byte-identical
  on branch claude/pra-u1d-parser-ci-2d-20260929 at 967561cc, lines 656, 661 and 663-668, and on claude/pra-u1-cmdpos-2d-
  20260928 at 2bad7320, lines 643-655): the directory order (argument, CHILD_USAGE_SHELL_PARSER, the pin's default under the
  home directory), the pinned files, and the lockfile that must list both pinned packages with the pinned version and
  integrity. tools.parser.* mirrors that load check; re-read it when U1 merges.
  openai/codex rust-v0.157.1 (36650394): codex-rs/agent-roles/src/discovery.rs and loader.rs (a role comes from every *.toml
  below <config folder>/agents and from every [agents.<name>] table of an enabled layer), codex-rs/exec-server/src/
  local_file_system.rs:710-735 (read_directory classifies a link by its target, so Codex enters a linked folder: a folder link
  below agents makes a role count an error here, never a smaller count), codex-rs/config/src/state.rs
  config_folder (the user layer's folder is $CODEX_HOME, the system layer's /etc/codex, a project layer's its .codex) and
  `codex mcp list --json` (a JSON array of objects, of which only `name` and `enabled` are read). The codex.* role rows are
  the U13 rows of the Codex role carriers (adoption/agents/codex, tools/adoption/codex_roles.py); this tool stays
  self-contained and repeats their counting rules. observability/collector/codex-identity-launcher.sh.example ends with
  `exec '<absolute path>' "$@"`, the shape codex.binary.sha256 follows one hop: it hashes the file that line names, read
  through links. On the reference host that file is a link to the npm package's Node entry (@openai/codex bin/codex.js), which
  resolves and starts the native executable; the native executable itself is not hashed, and codex.version names the release.
"""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
import shutil
import signal
import socket
import stat
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, NamedTuple, Optional

try:  # the login name is one of the identities the guard keeps out of the output
    import pwd
except ImportError:  # pragma: no cover - not available off Unix
    pwd = None

TOOL_VERSION = "1"
SCHEMA = "freeze-snapshot-v1"
FROZEN, INFORMATIONAL = "frozen", "informational"
OK, MISSING, ERROR, NOT_APPLICABLE = "ok", "missing", "error", "not_applicable"
STATUSES = (OK, MISSING, ERROR, NOT_APPLICABLE)
EXIT_OK, EXIT_DRIFT, EXIT_USAGE, EXIT_PRIVACY = 0, 1, 2, 3

SEALED_DIR = "evidence/artifacts/token-adoption-e2e-20260926"
SEALED_FILES = ("preregistration.json", "token-e2e-run.mjs", "RUNBOOK.md", "fixtures/table.json", "fixtures/events.jsonl")
CARRIER_DIR = "adoption/hooks/claude"
CARRIER_HOOK = "token-lanes-subagent-start.py"
CAPABILITY_DIR = "tools/capability-gate"
WORKFLOW_DIR = "examples/claude-native/workflows"
WORKFLOW_FILES = ("child-usage.mjs", "shell-parser.pin.json", "SHA256SUMS")
PARSER_PIN = f"{WORKFLOW_DIR}/shell-parser.pin.json"
PARSER_ENV = "CHILD_USAGE_SHELL_PARSER"  # the variable child-usage.mjs reads for the installed parser directory
PARSER_PACKAGES = ("web-tree-sitter", "tree-sitter-bash")  # the two packages the kernel checks in the lockfile, by name
DEFAULT_LOCKFILE = "package-lock.json"
TOOL_FILES = (("repo.tool.skill_usage.py", "tools/skill-usage/skill_usage.py"),)
ROLES = ("stack-verifier", "isolated-builder", "source-scout", "stack-researcher", "evidence-reviewer")
ROLE_COPIES = (("adoption", "adoption/agents/claude"), ("examples", "examples/claude-native/agents"),
               ("project", ".claude/agents"), ("user", "~/.claude/agents"))
DEFAULT_UNITS = ("ecosystem-otelcol", "ecosystem-loki", "ecosystem-prometheus", "ecosystem-grafana", "omniroute",
                 "omniroute-fw", "hindsight-live", "cognee-live", "ai-memory")
QMD_INDEX = "native-agent-stack-catalog"
TOKENIZER_PREFIX = "~/.local/share/native-token-report/tokenizer"
CREDENTIAL_STORES = (".claude.json", ".claude/.credentials.json", ".codex/auth.json")
LAUNCHER = "~/.local/share/codex-ecosystem/bin/claude"
CLAUDE_BINARY = "~/.local/bin/claude"
CODEX_ROLE_FILES = ("stack-researcher.toml", "stack-verifier.toml")  # adoption/agents/codex/SHA256SUMS names exactly these two
CODEX_SYSTEM_DIR = Path("/etc/codex")  # the system layer's config folder; that layer is always pushed (config/src/loader/mod.rs)
CODEX_HOME_VARIABLE = "CODEX_HOME"
CODEX_PROFILE = "stack-worker"
SETTINGS_DERIVED = ("effort_level_env_unset", "agent_teams_env", "subagent_model_env", "has_model_settings",
                    "has_effort_level", "advisor_model")
UNSET, OTHER = "unset", "other"
# Behaviour-affecting settings keys, read from each parsed settings file. The value sets are the documented ones
# (https://code.claude.com/docs/en/settings-reference, fetched 2026-09-29); a value outside its set is the class `other`, an
# absent key is `unset`, and nothing else about the value is kept.
PERMISSION_MODES = ("default", "acceptEdits", "plan", "auto", "dontAsk", "bypassPermissions", "manual")
CROSS_SESSION_VALUES = ("accept", "hold", "refuse")
UPDATE_CHANNELS = ("latest", "stable")
WORKFLOW_SIZES = ("unrestricted", "small", "medium", "large")
EFFORT_LEVELS = ("low", "medium", "high", "xhigh")
ENUM, FLAG, COUNT, ALIAS = "enum", "flag", "count", "alias"
BEHAVIOUR_SETTINGS = (  # (id suffix, key path in the settings document, rule, documented values)
    ("permissions_default_mode", ("permissions", "defaultMode"), ENUM, PERMISSION_MODES),
    ("permissions_allow_count", ("permissions", "allow"), COUNT, ()),
    ("permissions_deny_count", ("permissions", "deny"), COUNT, ()),
    ("permissions_ask_count", ("permissions", "ask"), COUNT, ()),
    ("skip_dangerous_mode_permission_prompt", ("skipDangerousModePermissionPrompt",), FLAG, ()),
    ("cross_session_inbound", ("crossSessionInbound",), ENUM, CROSS_SESSION_VALUES),
    ("auto_continue_at_usage_limit", ("autoContinueAtUsageLimit",), FLAG, ()),
    ("auto_updates_channel", ("autoUpdatesChannel",), ENUM, UPDATE_CHANNELS),
    ("ultracode", ("ultracode",), FLAG, ()),
    ("enable_workflows", ("enableWorkflows",), FLAG, ()),
    ("workflow_size_guideline", ("workflowSizeGuideline",), ENUM, WORKFLOW_SIZES),
    ("switch_models_on_flag", ("switchModelsOnFlag",), FLAG, ()),
    ("model", ("model",), ALIAS, ()),
    ("effort_level", ("effortLevel",), ENUM, EFFORT_LEVELS),
)
BEHAVIOUR_SUFFIXES = tuple(row[0] for row in BEHAVIOUR_SETTINGS)
BEHAVIOUR_METHODS = {ENUM: "documented value of a settings key", FLAG: "boolean of a settings key",
                     COUNT: "number of permission rules", ALIAS: "model alias of a settings key"}
CONFIG_FLAGS = ("--config", "-config.file", "--config.file")
ALIAS_EXEMPT_VARIABLE = "CLAUDE_CODE_SUBAGENT_MODEL"
MIN_SECRET_LENGTH = 8
MAX_JSON_BYTES = 32 << 20
LOOPBACK_HOSTS = ("127.0.0.1", "localhost", "[::1]")

DIGITS = frozenset("0123456789")
LOWER = frozenset("abcdefghijklmnopqrstuvwxyz")
ALNUM = LOWER | frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZ") | DIGITS
ALIAS_CHARS = LOWER | DIGITS | frozenset("-._[]")
HEX = frozenset("0123456789abcdef")
PATH_CHARS = frozenset("/\\~")
ROUTE_CHARS = ALNUM | frozenset("/._-:")


class Spec(NamedTuple):
    """One catalogue entry: `id` ends with `*` for a family whose members depend on what the host holds."""

    id: str
    cls: str
    owner: str
    method: str  # slash-free, stored in every capture
    how: str  # the `how to check` line list-frozen prints


class RunResult(NamedTuple):
    state: str  # ok (exit 0), exit (nonzero), timeout, missing
    code: Optional[int]
    out: str
    err: str


class UsageError(Exception):
    """A bad argument, input file or configuration (exit 2). The message never names a path."""


class PathRefused(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class PrivacyRefusal(Exception):
    def __init__(self, items: list[str], variables: Optional[list[str]] = None):
        super().__init__("privacy guard")
        self.items = items
        self.variables = variables or []  # names only, never values


# ----------------------------------------------------------------------------------------------- text helpers


def plain_name(text: Any, extra: str = "._-", limit: int = 64) -> bool:
    """A short token of letters, digits and `extra` that starts with a letter or digit (one linear scan)."""
    if not isinstance(text, str) or not 0 < len(text) <= limit or text[0] not in ALNUM:
        return False
    allowed = ALNUM | frozenset(extra)
    for char in text:
        if char not in allowed:
            return False
    return True


def is_plain(text: Any) -> bool:
    """Text safe to store in the sanitized capture: one short line, no path character, no control character."""
    if not isinstance(text, str) or len(text) > 160:
        return False
    for char in text:
        if char in PATH_CHARS or ord(char) < 32 or ord(char) == 127:
            return False
    return "://" not in text


def alias_or_other(value: Any) -> str:
    """A model alias prints as itself; anything else is the class `other`, never the value."""
    if isinstance(value, str) and 0 < len(value) <= 40 and value[0] in LOWER:
        for char in value:
            if char not in ALIAS_CHARS:
                return "other"
        return value
    return "other"


def strip_ansi(text: str) -> str:
    """Remove CSI and OSC escape sequences in one pass; an unterminated sequence drops the rest."""
    out: list[str] = []
    index, length = 0, len(text)
    while index < length:
        char = text[index]
        if char != "\x1b":
            out.append(char)
            index += 1
            continue
        index += 1
        if index >= length:
            break
        kind = text[index]
        if kind == "[":
            index += 1
            while index < length and not "@" <= text[index] <= "~":
                index += 1
            index += 1
        elif kind == "]":
            index += 1
            while index < length and text[index] != "\x07" and not (text[index] == "\x1b" and text[index + 1:index + 2] == "\\"):
                index += 1
            index += 1 if text[index:index + 1] == "\x07" else 2
        else:
            index += 1
    return "".join(out)


def leading_int(text: str) -> Optional[int]:
    digits = []
    for char in text.strip():
        if char not in DIGITS:
            break
        digits.append(char)
    return int("".join(digits)) if digits else None


def is_hex(text: str, length: int) -> bool:
    if len(text) != length:
        return False
    for char in text:
        if char not in HEX:
            return False
    return True


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def utc_minute(epoch: Any) -> Optional[str]:
    if isinstance(epoch, bool) or not isinstance(epoch, (int, float)):
        return None
    try:
        return datetime.fromtimestamp(epoch, timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    except (OverflowError, OSError, ValueError):
        return None


def digest_body(body: Any, ignore_keys: Iterable[str] = ()) -> str:
    """sha256(json.dumps(body, sort_keys=True)), the digest rule of the gateway items; ignore_keys are removed at every depth."""
    keys = frozenset(ignore_keys)
    if keys:
        body = drop_keys(body, keys)
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode("utf-8")).hexdigest()


def drop_keys(value: Any, keys: frozenset) -> Any:
    if isinstance(value, dict):
        return {key: drop_keys(inner, keys) for key, inner in value.items() if key not in keys}
    if isinstance(value, list):
        return [drop_keys(inner, keys) for inner in value]
    return value


# ------------------------------------------------------------------------------------------------- parsers


def parse_mcp_list(text: str) -> Optional[dict]:
    """`claude mcp list` (2.1.284): a health header, a blank line, one `name: command - status` line per server, a blank
    line, then diagnostics. Returns {name: connected}; None when the text is not that report."""
    lines = strip_ansi(text).splitlines()
    header = None
    for index, line in enumerate(lines):
        if line.startswith("Checking MCP server health"):
            header = index
            break
        if line.startswith("No MCP servers configured"):
            return {}
    if header is None:
        return None
    index = header + 1
    while index < len(lines) and not lines[index].strip():
        index += 1
    servers: dict[str, bool] = {}
    while index < len(lines) and lines[index].strip():
        name, separator, rest = lines[index].partition(": ")
        cut = rest.rfind(" - ")
        if separator and cut >= 0 and plain_name(name, "._:@+-", 80):
            status = rest[cut + 3:].strip()
            start = 0
            while start < len(status) and not status[start].isalnum():
                start += 1
            servers[name] = status[start:].startswith("Connected")
        index += 1
    return servers


def parse_systemd_show(text: str) -> dict[str, str]:
    """`systemctl --user show UNIT -p ...`: KEY=VALUE lines in any order; the first occurrence of a key wins."""
    props: dict[str, str] = {}
    for line in text.splitlines():
        key, separator, value = line.partition("=")
        if separator and key not in props and plain_name(key, "", 48):
            props[key] = value
    return props


def exec_start_config_path(exec_start: str) -> Optional[str]:
    """The configuration file an ExecStart value names: --config=P, --config P, -config.file=P or --config.file=P;
    a `file:` scheme is dropped. Only the first such flag counts."""
    start = exec_start.find("argv[]=")
    if start < 0:
        return None
    start += len("argv[]=")
    end = exec_start.find(" ; ", start)
    tokens = exec_start[start:end if end >= 0 else len(exec_start)].split()
    for index, token in enumerate(tokens):
        for flag in CONFIG_FLAGS:
            if token == flag:
                following = tokens[index + 1] if index + 1 < len(tokens) else ""
                return strip_scheme(following) if following and not following.startswith("-") else None
            if token.startswith(flag + "="):
                value = token[len(flag) + 1:]
                return strip_scheme(value) if value else None
    return None


def strip_scheme(value: str) -> str:
    return value[len("file:"):] if value.startswith("file:") else value


def parse_qmd_status(text: str) -> Optional[dict]:
    """The `Documents` block of `qmd status` (2.8.3). Orphaned and Pending lines are absent when the count is zero."""
    lines = strip_ansi(text).splitlines()
    for index, line in enumerate(lines):
        if line.strip() != "Documents":
            continue
        counts: dict[str, Optional[int]] = {}
        for entry in lines[index + 1:]:
            if not entry.startswith(" "):
                break
            label, separator, rest = entry.strip().partition(":")
            if separator:
                counts[label] = leading_int(rest)
        if counts.get("Total") is None or counts.get("Vectors") is None:
            return None
        return {"documents": counts["Total"], "vectors": counts["Vectors"],
                "orphaned": counts.get("Orphaned") or 0, "pending": counts.get("Pending") or 0}
    return None


def parse_unified_windows(events: Any) -> Optional[dict]:
    """The last rate_limit_event of `claude -p --verbose --output-format json` that carries unifiedWindows:
    {five_hour|seven_day: {utilization, resets_at_utc}}; None when none does."""
    if not isinstance(events, list):
        return None
    for event in reversed(events):
        info = event.get("rate_limit_info") if isinstance(event, dict) and event.get("type") == "rate_limit_event" else None
        windows = info.get("unifiedWindows") if isinstance(info, dict) else None
        if not isinstance(windows, dict):
            continue
        found: dict[str, dict] = {}
        for name in ("five_hour", "seven_day"):
            window = windows.get(name)
            utilization = window.get("utilization") if isinstance(window, dict) else None
            resets = utc_minute(window.get("resetsAt")) if isinstance(window, dict) else None
            if isinstance(utilization, (int, float)) and not isinstance(utilization, bool) and resets:
                found[name] = {"utilization": float(utilization), "resets_at_utc": resets}
        if found:
            return found
    return None


# --------------------------------------------------------------------------------------------- path policy


def under(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def is_credential_store(path: str, home: Path) -> bool:
    """True when `path` names one of the three credential stores lexically, through a symlink, or by inode.
    A relative path is judged by the caller after it is made absolute. Text that cannot be examined is refused."""
    try:
        if path == "~" or path.startswith("~/"):
            candidate = home / path[2:]
        elif os.path.isabs(path):
            candidate = Path(path)
        else:
            return False
        candidate = Path(os.path.normpath(candidate))
        for relative in CREDENTIAL_STORES:
            store = home / relative
            if candidate == store or os.path.realpath(candidate) == os.path.realpath(store):
                return True
            if os.path.exists(candidate) and os.path.exists(store) and os.path.samefile(candidate, store):
                return True
        return False
    except (ValueError, OSError):
        return True


def check_path_policy(text: str, home: Path, repo: Optional[Path], allow_relative: bool = True) -> Path:
    """The path for a configuration or unit-file path, or PathRefused. A relative path is relative to the checkout, and a
    unit file's own relative path is refused (allow_relative=False) because its base is unknown. The path must lie inside
    the checkout or the home directory (symlinks resolved); with no checkout, inside the home directory."""
    if not isinstance(text, str) or not text or "\x00" in text:
        raise PathRefused("invalid")
    if is_credential_store(text, home):
        raise PathRefused("credential_store")
    if text == "~" or text.startswith("~/"):
        path = home / text[2:]
    elif text.startswith("~"):
        raise PathRefused("other_home")
    elif os.path.isabs(text):
        path = Path(text)
    elif allow_relative:
        path = (repo or Path(".")) / text
    else:
        raise PathRefused("invalid")
    path = Path(os.path.normpath(path))
    if is_credential_store(str(path), home):
        raise PathRefused("credential_store")
    # With no checkout (list-frozen without --repo) the home directory is the only known root, and a relative path may
    # not climb out of the checkout it will later be read from.
    roots = (home, repo) if repo is not None else (home,)
    if path.is_absolute():
        if not any(under(path, root) for root in roots):
            raise PathRefused("outside_roots")
        real = Path(os.path.realpath(path))
        if not any(under(real, Path(os.path.realpath(root))) for root in roots):
            raise PathRefused("outside_roots")
    elif path.parts[:1] == ("..",):
        raise PathRefused("outside_roots")
    return path


PATH_PHRASES = {"credential_store": "names a credential store", "outside_roots": "is outside the repository and the home directory",
                "other_home": "names another user's home directory", "invalid": "is not a usable path"}


# ---------------------------------------------------------------------------------------------- run and ctx


def kill_group(process: "subprocess.Popen[bytes]") -> None:
    for signum, grace in ((signal.SIGTERM, 2.0), (signal.SIGKILL, 5.0)):
        try:
            os.killpg(process.pid, signum)
        except (ProcessLookupError, PermissionError):
            pass
        try:
            process.communicate(timeout=grace)
            return
        except subprocess.TimeoutExpired:
            continue
    for stream in (process.stdout, process.stderr):
        if stream is not None:
            stream.close()


def regular_file_problem(path: Path) -> Optional[str]:
    """A reason token when `path` is not a regular file (a FIFO or device would block the read); None when it is one."""
    mode = os.stat(path).st_mode
    if stat.S_ISDIR(mode):
        return "is_directory"
    return None if stat.S_ISREG(mode) else "not_regular_file"


def git_environment(env: dict[str, str]) -> dict[str, str]:
    """The environment for git with every GIT_* variable dropped except the two that isolate its configuration, so a
    hook's GIT_DIR or GIT_INDEX_FILE cannot select another repository (tests/__init__.py, issue #179)."""
    return {key: value for key, value in env.items()
            if not key.startswith("GIT_") or key in ("GIT_CONFIG_GLOBAL", "GIT_CONFIG_NOSYSTEM")}


def make_item(item_id: str, cls: str, status: str, value: Any, method: str, reason: Optional[str] = None,
              path: Optional[str] = None) -> dict:
    item: dict[str, Any] = {"id": item_id, "class": cls, "status": status, "value": value, "method": method}
    if reason:
        item["reason"] = reason
    if path:
        item["path"] = path
    return item


class Ctx:
    """Everything a collector needs: the checkout, the home directory, the process environment, the catalogue."""

    def __init__(self, home: Path, repo: Path, env: dict[str, str], platform: str, specs: list[Spec], config: dict,
                 probe: bool):
        self.home = Path(os.path.normpath(home))
        self.repo = Path(os.path.normpath(repo))
        self.env = dict(env)
        self.platform = platform
        self.specs = list(specs)
        self.by_id = {spec.id: spec for spec in self.specs if not spec.id.endswith("*")}
        self.families = sorted(((spec.id[:-1], spec) for spec in self.specs if spec.id.endswith("*")),
                               key=lambda pair: -len(pair[0]))
        self.config = config
        self.probe = probe
        self.start = utc_now()
        self.public_values: set[str] = set()  # printed on purpose from a settings file (a model alias): may equal an env value
        self.private_values: set[str] = set()  # read and never printed (permission rules): the guard keeps them out

    @classmethod
    def for_tests(cls, home: Path, repo: Path, env: dict[str, str]) -> "Ctx":
        return cls(Path(home), Path(repo), env, "linux", [], {}, False)

    # -- running commands
    def run(self, argv: list[str], timeout: float = 30.0, cwd: Optional[Path] = None,
            env: Optional[dict[str, str]] = None) -> RunResult:
        """Run one command with stdin closed, in its own session; a timeout kills the whole process group."""
        environment = self.env if env is None else env
        executable = shutil.which(argv[0], path=environment.get("PATH"))
        if executable is None:
            return RunResult("missing", None, "", "")
        try:
            process = subprocess.Popen([executable, *argv[1:]], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, cwd=str(cwd or self.repo), env=environment,
                                       start_new_session=True)
        except OSError:
            return RunResult(state="missing", code=None, out="", err="")
        try:
            out, err = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            kill_group(process)
            return RunResult("timeout", None, "", "")
        return RunResult("ok" if process.returncode == 0 else "exit", process.returncode,
                         out.decode("utf-8", "replace"), err.decode("utf-8", "replace"))

    def git(self, args: list[str], directory: Optional[Path] = None) -> RunResult:
        return self.run(["git", "--no-optional-locks", "-C", str(directory or self.repo), *args],
                        env=git_environment(self.env))

    # -- files
    def expand(self, text: str) -> Path:
        if text == "~" or text.startswith("~/"):
            path = self.home / text[2:]
        elif os.path.isabs(text):
            path = Path(text)
        else:
            path = self.repo / text
        return Path(os.path.normpath(path))

    def display(self, path: Path) -> str:
        path = Path(os.path.normpath(path))
        for label, root in (("<repo>", self.repo), ("~", self.home)):
            if path == root:
                return label
            if root in path.parents:
                return f"{label}/{path.relative_to(root).as_posix()}"
        raise PathRefused("outside_roots")

    def read(self, path: Path, limit: int = MAX_JSON_BYTES) -> tuple[str, Optional[bytes], Optional[str]]:
        """(status, bytes, reason) for one file; a credential store is never opened."""
        try:
            if is_credential_store(str(path), self.home):
                return ERROR, None, "credential_store"
            kind = regular_file_problem(path)
            if kind:
                return ERROR, None, kind
            with open(path, "rb") as handle:
                data = handle.read(limit + 1)
            return (OK, data, None) if len(data) <= limit else (ERROR, None, "too_large")
        except (FileNotFoundError, NotADirectoryError):
            return MISSING, None, "file_absent"
        except IsADirectoryError:
            return ERROR, None, "is_directory"
        except PermissionError:
            return ERROR, None, "unreadable"
        except OSError:
            return ERROR, None, "os_error"

    def hash_file(self, path: Path) -> tuple[str, Optional[str], Optional[str]]:
        """(status, sha256, reason), streamed so a large binary is never held in memory."""
        try:
            if is_credential_store(str(path), self.home):
                return ERROR, None, "credential_store"
            kind = regular_file_problem(path)
            if kind:
                return ERROR, None, kind
            digest = hashlib.sha256()
            with open(path, "rb") as handle:
                while True:
                    block = handle.read(1 << 20)
                    if not block:
                        break
                    digest.update(block)
            return OK, digest.hexdigest(), None
        except (FileNotFoundError, NotADirectoryError):
            return MISSING, None, "file_absent"
        except IsADirectoryError:
            return ERROR, None, "is_directory"
        except PermissionError:
            return ERROR, None, "unreadable"
        except OSError:
            return ERROR, None, "os_error"

    # -- items
    def spec_for(self, item_id: str) -> Spec:
        spec = self.by_id.get(item_id)
        if spec is not None:
            return spec
        for prefix, family in self.families:
            if item_id.startswith(prefix):
                return family
        raise KeyError(item_id)

    def item(self, item_id: str, status: str, value: Any, reason: Optional[str] = None, path: Optional[Path] = None) -> dict:
        spec = self.spec_for(item_id)
        shown = self.display(path) if path is not None else None
        return make_item(item_id, spec.cls, status, value if status == OK else None, spec.method, reason, shown)

    def file_item(self, item_id: str, path: Path) -> dict:
        status, digest, reason = self.hash_file(path)
        return self.item(item_id, status, digest, reason, path)

    def text_item(self, item_id: str, argv: list[str], timeout: float = 30.0) -> dict:
        """The first line of a `--version`-style command, which must be one plain line."""
        result = self.run(argv, timeout=timeout)
        if result.state == "missing":
            return self.item(item_id, MISSING, None, "tool_absent")
        if result.state != "ok":
            return self.item(item_id, ERROR, None, result.state)
        text = result.out.strip() or result.err.strip()
        line = strip_ansi(text.splitlines()[0]).strip() if text else ""
        if not line or not is_plain(line):
            return self.item(item_id, ERROR, None, "unrecognized_output")
        return self.item(item_id, OK, line)

    def not_applicable(self, owner: str) -> list[dict]:
        return [make_item(spec.id, spec.cls, NOT_APPLICABLE, None, spec.method, "platform")
                for spec in self.specs if spec.owner == owner and not spec.id.endswith("*")]


# ------------------------------------------------------------------------------------------------ catalogue


def behaviour_how(where: str, key_path: tuple, rule: str, allowed: tuple) -> str:
    key = ".".join(key_path)
    if rule == ENUM:
        return f"{key} in {where}: {', '.join(allowed)}, other (any other value, never printed) or unset"
    if rule == FLAG:
        return f"{key} in {where}: true, false, other (not a boolean) or unset"
    if rule == COUNT:
        return f"number of rules in {key} of {where} (a count, never a rule; 0 when the key is absent)"
    return f"{key} in {where}: a model alias, other or unset"


def build_specs(config: dict) -> list[Spec]:
    specs: list[Spec] = []

    def add(item_id: str, owner: str, method: str, how: str, cls: str = FROZEN) -> None:
        specs.append(Spec(item_id, cls, owner, method, how))

    add("repo.head", "repo", "git rev-parse HEAD", "git -C <checkout> rev-parse HEAD in the checkout under freeze")
    add("repo.tree_clean", "repo", "git status porcelain",
        "git -C <checkout> status --porcelain --untracked-files=no prints nothing (tracked files only)")
    for relative in SEALED_FILES:
        add("repo.sealed." + relative.replace("/", ":"), "repo", "sha256 of file",
            f"sha256 of {SEALED_DIR}/{relative} in the checkout (sealed by the #381 preregistration)")
    add("repo.carrier.*", "repo", "sha256 of file",
        f"sha256 of each {CARRIER_DIR}/token-lanes-block*.md and {CARRIER_HOOK} in the checkout")
    add("repo.capability_gate.*", "repo", "sha256 of file",
        f"sha256 of each file under {CAPABILITY_DIR} except its README.md (path separators shown as a colon)")
    for name in WORKFLOW_FILES:
        add(f"repo.workflow.{name}", "repo", "sha256 of file", f"sha256 of {WORKFLOW_DIR}/{name} in the checkout")
    for item_id, relative in TOOL_FILES:
        add(item_id, "repo", "sha256 of file", f"sha256 of {relative} in the checkout")

    for role in ROLES:
        for copy, folder in ROLE_COPIES:
            add(f"roles.{role}.{copy}", "roles", "sha256 of file", f"sha256 of {folder}/{role}.md")
        add(f"roles.{role}.identical_across_copies", "roles", "four copies byte-identical",
            f"true when the adoption, examples, project and user copies of {role}.md all exist and are byte-identical")
    add("hooks.installed.*", "hooks", "sha256 of file",
        "sha256 of each file in ~/.claude/hooks (backup files skipped) and of each carrier the checkout ships")
    add("hooks.carriers_match_repo", "hooks", "installed carriers equal the checkout",
        "true when every carrier the checkout ships has a byte-identical installed copy in ~/.claude/hooks")

    add("claude.version", "claude", "claude --version", "first line of `claude --version`")
    add("claude.launcher.sha256", "claude", "sha256 of file", f"sha256 of {LAUNCHER}")
    add("claude.launcher.size", "claude", "file size in bytes", f"size in bytes of {LAUNCHER}")
    add("claude.binary.version_name", "claude", "name of the resolved binary",
        f"file name under versions/ that {CLAUDE_BINARY} resolves to")
    add("claude.binary.size", "claude", "file size in bytes", f"size in bytes of the file {CLAUDE_BINARY} resolves to")
    add("claude.binary.sha256", "claude", "sha256 of file", f"sha256 of the file {CLAUDE_BINARY} resolves to")
    add("claude.user_claude_md.sha256", "claude", "sha256 of file", "sha256 of ~/.claude/CLAUDE.md")
    add("claude.user_rtk_md.sha256", "claude", "sha256 of file", "sha256 of ~/.claude/RTK.md")
    for kind, where in (("user", "~/.claude/settings.json"), ("project", "<checkout>/.claude/settings.json"),
                        ("local", "<checkout>/.claude/settings.local.json")):
        prefix = f"claude.settings.{kind}."
        add(prefix + "sha256", "claude", "sha256 of file", f"sha256 of {where}")
        add(prefix + "effort_level_env_unset", "claude", "derived from the whole settings file",
            f"true when {where} has no CLAUDE_CODE_EFFORT_LEVEL key in its env block")
        add(prefix + "agent_teams_env", "claude", "value class from the settings file",
            f"class of CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS in the env block of {where}: 1, other or unset")
        add(prefix + "subagent_model_env", "claude", "value class from the settings file",
            f"CLAUDE_CODE_SUBAGENT_MODEL in the env block of {where}: a model alias, other or unset")
        add(prefix + "has_model_settings", "claude", "derived from the whole settings file",
            f"true when {where} has a modelSettings key")
        add(prefix + "has_effort_level", "claude", "derived from the whole settings file",
            f"true when {where} has an effortLevel key")
        add(prefix + "advisor_model", "claude", "value class from the settings file",
            f"advisorModel in {where}: a model alias, other or unset")
        for suffix, key_path, rule, allowed in BEHAVIOUR_SETTINGS:
            add(prefix + suffix, "claude", BEHAVIOUR_METHODS[rule], behaviour_how(where, key_path, rule, allowed))
    add("claude.process.effort_level_unset", "claude", "process environment", "true when CLAUDE_CODE_EFFORT_LEVEL is not set "
        "in the environment of the process running the capture")
    add("claude.process.agent_teams_env", "claude", "process environment class",
        "class of CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS in the capture process: 1, other or unset")
    add("claude.process.subagent_model_env", "claude", "process environment class",
        "CLAUDE_CODE_SUBAGENT_MODEL in the capture process: a model alias, other or unset")
    add("claude.mcp.*", "claude", "claude mcp list connected flag",
        "claude mcp list (run in the checkout): one item per server name, true when it reports Connected")
    add("claude.mcp_count", "claude", "claude mcp list", "number of servers `claude mcp list` reports")

    add("codex.version", "codex", "codex --version", "first line of `codex --version`")
    add("codex.config.sha256", "codex", "sha256 of file", "sha256 of ~/.codex/config.toml")
    add("codex.stack_worker_profile.sha256", "codex", "sha256 of file", "sha256 of ~/.codex/stack-worker.config.toml")
    add("codex.stack_worker_profile.present", "codex", "file exists", "true when ~/.codex/stack-worker.config.toml exists")
    add("codex.agents_md.sha256", "codex", "sha256 of file", "sha256 of ~/.codex/AGENTS.md")
    add("codex.rtk_md.sha256", "codex", "sha256 of file", "sha256 of ~/.codex/RTK.md")
    # The Codex role carriers and everything else that can add a role (U13). They read the Codex home as scripts/
    # adoption_status.py does ($CODEX_HOME when set and not empty, else ~/.codex); the codex.* items above read ~/.codex.
    for role in ("stack-researcher", "stack-verifier"):
        add(f"codex.agents.{role}.sha256", "codex_roles", "sha256 of file",
            f"sha256 of {role}.toml in the agents folder of the Codex home ($CODEX_HOME when set, else ~/.codex); missing when "
            "absent, error when it is a link or the folder is a link")
    add("codex.agents.toml_set", "codex_roles", "*.toml files below agents",
        "which of stack-researcher.toml and stack-verifier.toml the agents folder of the Codex home holds at its top, and `other`, "
        "the number of every other *.toml file below it (nested files and links to files named *.toml count; a name is never "
        "published): both true and 0 other is the frozen state. A link to a folder anywhere below makes it an error "
        "(linked_folder): Codex enters a linked folder, and a set that skipped one would undercount")
    add("codex.agents.role_tables", "codex_roles", "[agents.<name>] tables",
        "the number of [agents.<name>] tables in config.toml and stack-worker.config.toml of the Codex home (0 when a file is "
        "absent; error when one does not parse)")
    add("codex.system.agents_toml_count", "codex_roles", "*.toml files below agents",
        "the number of *.toml files below /etc/codex/agents, the system layer's role folder (0 when absent; error when a link to "
        "a folder is below it)")
    add("codex.system.role_tables", "codex_roles", "[agents.<name>] tables",
        "the number of [agents.<name>] tables in /etc/codex/config.toml (0 when absent)")
    add("codex.project.agents_toml_count", "codex_roles", "*.toml files below agents",
        "the number of *.toml files below .codex/agents of the checkout under freeze, its project layer's role folder (0 when "
        "absent; error when a link to a folder is below it)")
    add("codex.project.role_tables", "codex_roles", "[agents.<name>] tables",
        "the number of [agents.<name>] tables in .codex/config.toml of the checkout under freeze (0 when absent)")
    add("codex.launcher.sha256", "codex_roles", "sha256 of file",
        "sha256 of the file the `codex` on PATH names (the launcher when one is installed); missing when there is no codex on PATH")
    add("codex.binary.sha256", "codex_roles", "sha256 of the file the launcher executes",
        "sha256 of the file the launcher script on PATH ends by executing (its last line `exec '<absolute path>' \"$@\"`, one hop, "
        "read through links; the path must meet the path policy and is not stored), else of the file the `codex` on PATH resolves "
        "to. That file is the npm package's Node entry on the reference host, which starts the native executable: the row pins the "
        "entry point and codex.version names the release")
    add("codex.mcp.servers.default", "codex_roles", "codex mcp list --json names and enabled flags",
        "server name and enabled flag from `codex mcp list --json` run in an empty temporary directory, so no project layer "
        "adds a server: the parent's effective set; transport, environment, arguments and URLs are never read")
    add("codex.mcp.servers.stack_worker", "codex_roles", "codex mcp list --json names and enabled flags",
        "server name and enabled flag from `codex -p stack-worker mcp list --json` run in an empty temporary directory: "
        "the effective set of the sealed arm B parent")

    add("wiring.complete", "adoption", "adoption_status client wiring",
        "client_wiring.complete from scripts/adoption_status.py --client-wiring --json in the checkout")
    add("claude.wiring.*", "adoption", "adoption_status client wiring",
        "booleans and counts under client_wiring.claude and client_wiring.project of scripts/adoption_status.py "
        "--client-wiring --json")
    add("codex.wiring.*", "adoption", "adoption_status client wiring",
        "booleans and counts under client_wiring.codex (hook events and trusted events) of scripts/adoption_status.py "
        "--client-wiring --json")
    add("tools.pinned.*", "adoption", "adoption_status pinned versions",
        "component id with pinned version, checked flag and match flag from scripts/adoption_status.py --profile "
        "token-efficiency --pinned-versions --json")
    add("tools.pinned_versions_match", "adoption", "adoption_status pinned versions",
        "pinned_versions_match from scripts/adoption_status.py --profile token-efficiency --pinned-versions --json")

    add("tools.rtk.version", "tools", "rtk --version", "first line of `rtk --version`")
    add("tools.rtk.config.sha256", "tools", "sha256 of file", "sha256 of ~/.config/rtk/config.toml")
    add("tools.node.version", "tools", "node --version", "first line of `node --version`")
    add("tools.python.version", "tools", "python3 --version", "first line of `python3 --version`")
    add("tools.tokenizer.version", "tools", "gpt-tokenizer package version",
        "version in node_modules/gpt-tokenizer/package.json under the tokenizer prefix (default "
        f"{TOKENIZER_PREFIX}; config key tokenizer_prefix)")
    add("tools.tokenizer.o200k_base.sha256", "tools", "sha256 of file",
        "sha256 of cjs/encoding/o200k_base.js in the gpt-tokenizer package")
    add("tools.tokenizer.o200k_bpe_ranks.sha256", "tools", "sha256 of file",
        "sha256 of cjs/bpeRanks/o200k_base.js in the gpt-tokenizer package")
    for item_id, relative in (("tools.token_manifest.sha256", "tools/token-report/token_manifest.py"),
                              ("tools.token_manifest_test.sha256", "tools/token-report/test_token_manifest.py"),
                              ("tools.token_manifest_template.sha256", "tools/token-report/token_manifest.html.in"),
                              ("tools.token_manifest_full_template.sha256", "tools/token-report/token_manifest.full.html.in")):
        add(item_id, "tools", "sha256 of file", f"sha256 of {relative} in the checkout")
    for name, label in (("documents", "Total"), ("vectors", "Vectors"), ("pending", "Pending"), ("orphaned", "Orphaned")):
        add(f"tools.qmd.{name}", "tools", "qmd status count",
            f"the {label} count of the Documents block of `qmd --index {config.get('qmd_index') or QMD_INDEX} status`")
    add("tools.parser.all_match_pin", "tools", "installed parser equals the pin",
        f"true when every file named in {PARSER_PIN} has the pinned sha256 in the installed parser directory and its lockfile "
        "lists both pinned packages with the pinned version and integrity, which is what child-usage.mjs requires before it "
        "loads the parser")
    add("tools.parser.file.*", "tools", "sha256 of file",
        f"sha256 of each file named in {PARSER_PIN} (its files, and the lockfile it names at install.lockfile) read from the "
        f"installed parser directory: config key parser_dir, else the absolute path in the {PARSER_ENV} variable, else the "
        "pin's default directory under the home directory")

    for unit, unit_class in service_units(config):
        base = f"services.{unit}."
        show = f"systemctl --user show {unit} -p"
        add(base + "load_state", "services", "systemctl show LoadState", f"{show} LoadState", unit_class)
        add(base + "active_state", "services", "systemctl show ActiveState", f"{show} ActiveState", unit_class)
        add(base + "main_pid", "services", "systemctl show MainPID", f"{show} MainPID", unit_class)
        add(base + "n_restarts", "services", "systemctl show NRestarts", f"{show} NRestarts", unit_class)
        add(base + "config_sha256", "services", "sha256 of the configuration file the unit runs",
            f"sha256 of the configuration file named by --config, --config.file or -config.file in `{show} ExecStart` "
            "(the path is stored only in the private capture)", unit_class)

    for gateway in config.get("gateways", []):
        for route in gateway["routes"]:
            add(f"gateways.{gateway['id']}.route.{route['id']}", "gateways", "sha256 of sorted JSON body",
                f"unauthenticated GET of {route['path']} on the loopback gateway {gateway['id']}: "
                "sha256(json.dumps(body, sort_keys=True))" + (f" without the keys {','.join(route['ignore_keys'])}"
                                                                if route["ignore_keys"] else ""))
        if gateway.get("build_id"):
            add(f"gateways.{gateway['id']}.build_id", "gateways", "build identifier the gateway reports",
                f"the build identifier of gateway {gateway['id']} from its response")

    for entry in config.get("files", []):  # the configured path is never printed: it may carry the home path or the user name
        add(f"extra.{entry['id']}", "extra", "sha256 of file",
            "sha256 of the file the configuration names for this id (only the private capture records where it lives)",
            entry["class"])

    add("capacity.codex.weekly_used_percent", "capacity", "codex_quota.py --json",
        "used percent of the weekly window from scripts/codex_quota.py --json", INFORMATIONAL)
    add("capacity.codex.weekly_resets_at_utc", "capacity", "codex_quota.py --json",
        "reset time of the weekly window from scripts/codex_quota.py --json", INFORMATIONAL)
    for window, label in (("five_hour", "five-hour"), ("seven_day", "seven-day")):
        add(f"capacity.claude.{window}_utilization_fraction", "capacity", "claude -p unifiedWindows",
            f"utilization of the {label} window from the rate_limit_event of one headless Haiku call", INFORMATIONAL)
        add(f"capacity.claude.{window}_resets_at_utc", "capacity", "claude -p unifiedWindows",
            f"reset time of the {label} window from the same rate_limit_event", INFORMATIONAL)
    add("capacity.host.load_average", "capacity", "os.getloadavg", "the 1, 5 and 15 minute load averages", INFORMATIONAL)
    add("capacity.host.memory_available_mib", "capacity", "meminfo MemAvailable",
        "MemAvailable from /proc/meminfo in MiB (Linux only)", INFORMATIONAL)
    for item_id, method, how in (
            ("time.capture_start_utc", "clock", "UTC time the capture started"),
            ("time.capture_end_utc", "clock", "UTC time the capture ended"),
            ("time.tool_version", "constant", "the version of this tool"),
            ("time.tool_revision", "git rev-parse HEAD", "git revision of the checkout that holds this tool"),
            ("time.tool_sha256", "sha256 of file", "sha256 of this tool's file")):
        add(item_id, "time", method, how, INFORMATIONAL)
    return sorted(specs, key=lambda spec: spec.id)


# ----------------------------------------------------------------------------------------------- collectors


def collect_repo(ctx: Ctx) -> list[dict]:
    items = []
    head = ctx.git(["rev-parse", "HEAD"])
    revision = head.out.strip()
    if head.state == "ok" and (is_hex(revision, 40) or is_hex(revision, 64)):
        items.append(ctx.item("repo.head", OK, revision))
    else:
        items.append(ctx.item("repo.head", ERROR if head.state != "missing" else MISSING, None,
                              "unrecognized_output" if head.state == "ok" else head.state))
    status = ctx.git(["status", "--porcelain", "--untracked-files=no"])
    if status.state == "ok":
        items.append(ctx.item("repo.tree_clean", OK, status.out.strip() == ""))
    else:
        items.append(ctx.item("repo.tree_clean", ERROR if status.state != "missing" else MISSING, None, status.state))
    for relative in SEALED_FILES:
        items.append(ctx.file_item("repo.sealed." + relative.replace("/", ":"), ctx.repo / SEALED_DIR / relative))
    for name in carrier_names(ctx):
        items.append(ctx.file_item("repo.carrier." + name, ctx.repo / CARRIER_DIR / name))
    for relative in capability_files(ctx):
        items.append(ctx.file_item("repo.capability_gate." + relative.replace("/", ":"), ctx.repo / CAPABILITY_DIR / relative))
    for name in WORKFLOW_FILES:
        items.append(ctx.file_item(f"repo.workflow.{name}", ctx.repo / WORKFLOW_DIR / name))
    for item_id, relative in TOOL_FILES:
        items.append(ctx.file_item(item_id, ctx.repo / relative))
    return items


def list_regular_files(directory: Path) -> list[str]:
    try:
        return sorted(name for name in os.listdir(directory) if (directory / name).is_file())
    except OSError:
        return []


def carrier_names(ctx: Ctx) -> list[str]:
    """The six token-lanes blocks the checkout ships and the SubagentStart hook; the hook is listed even when absent."""
    names = [name for name in list_regular_files(ctx.repo / CARRIER_DIR)
             if name.startswith("token-lanes-block") and name.endswith(".md") and plain_name(name, "._-", 100)]
    return sorted(set(names) | {CARRIER_HOOK})


def capability_files(ctx: Ctx) -> list[str]:
    """Every file under tools/capability-gate except its README.md and bytecode, as a slash-separated relative path."""
    root = ctx.repo / CAPABILITY_DIR
    found: list[str] = []
    for folder, directories, files in os.walk(root, followlinks=False):
        directories[:] = sorted(name for name in directories if name != "__pycache__")
        for name in sorted(files):
            relative = (Path(folder) / name).relative_to(root).as_posix()
            if relative != "README.md" and not name.endswith(".pyc") and plain_name(relative.replace("/", ":"), "._:-", 120):
                found.append(relative)
    return found


def collect_roles(ctx: Ctx) -> list[dict]:
    items = []
    for role in ROLES:
        digests = []
        for copy, folder in ROLE_COPIES:
            path = ctx.expand(f"{folder}/{role}.md")
            status, digest, reason = ctx.hash_file(path)
            items.append(ctx.item(f"roles.{role}.{copy}", status, digest, reason, path))
            digests.append(digest if status == OK else None)
        identical = all(digest is not None for digest in digests) and len(set(digests)) == 1
        items.append(ctx.item(f"roles.{role}.identical_across_copies", OK, identical))
    return items


def collect_hooks(ctx: Ctx) -> list[dict]:
    folder = ctx.home / ".claude" / "hooks"
    installed = [name for name in list_regular_files(folder) if ".bak" not in name and plain_name(name, "._-", 100)]
    shipped = carrier_names(ctx)
    items = []
    for name in sorted(set(installed) | set(shipped)):
        items.append(ctx.file_item("hooks.installed." + name, folder / name))
    matches = True
    for name in shipped:
        status, repo_digest, reason = ctx.hash_file(ctx.repo / CARRIER_DIR / name)
        if status != OK:  # the checkout does not ship a readable carrier, so the comparison cannot be made
            items.append(ctx.item("hooks.carriers_match_repo", status, None, reason))
            return items
        installed_status, installed_digest, _ = ctx.hash_file(folder / name)
        matches = matches and installed_status == OK and installed_digest == repo_digest
    items.append(ctx.item("hooks.carriers_match_repo", OK, matches))
    return items


def walk_settings(document: dict, key_path: tuple) -> tuple[str, Any]:
    """("set", value), ("unset", None) when the key is absent, or ("malformed", None) when a parent is not an object."""
    node: Any = document
    for key in key_path:
        if not isinstance(node, dict):
            return "malformed", None
        if key not in node:
            return "unset", None
        node = node[key]
    return "set", node


def classify_setting(document: dict, key_path: tuple, rule: str, allowed: tuple) -> tuple[str, Any, Optional[str]]:
    """(status, value, reason) of one behaviour key: a documented value, a boolean, a count or a model alias, else the class
    `other` or `unset`. A rule list that is not a list is an error. Never a rule and never any other value."""
    state, value = walk_settings(document, key_path)
    if rule == COUNT:
        if state == "unset":
            return OK, 0, None
        if state == "set" and isinstance(value, list):
            return OK, len(value), None
        return ERROR, None, "unrecognized_value"
    if state == "unset":
        return OK, UNSET, None
    if state == "malformed":
        return OK, OTHER, None
    if rule == FLAG:
        return OK, value if isinstance(value, bool) else OTHER, None
    if rule == ENUM:
        return OK, value if isinstance(value, str) and value in allowed else OTHER, None
    return OK, alias_or_other(value), None


def permission_rules(document: dict) -> list[str]:
    """The string rules of permissions.allow, .deny and .ask that are long enough to be a value the guard lists."""
    block = document.get("permissions")
    if not isinstance(block, dict):
        return []
    return [rule for kind in ("allow", "deny", "ask") if isinstance(block.get(kind), list)
            for rule in block[kind] if isinstance(rule, str) and len(rule) >= MIN_SECRET_LENGTH]


def behaviour_items(ctx: Ctx, prefix: str, document: dict, path: Path) -> list[dict]:
    """The behaviour keys of one parsed settings file as classes and counts; the rules are only handed to the guard."""
    items = []
    for suffix, key_path, rule, allowed in BEHAVIOUR_SETTINGS:
        status, value, reason = classify_setting(document, key_path, rule, allowed)
        if rule == ALIAS and value not in (UNSET, OTHER):
            ctx.public_values.add(value)
        items.append(ctx.item(prefix + suffix, status, value, reason, path))
    ctx.private_values.update(permission_rules(document))
    return items


def teams_class(block: dict) -> str:
    if "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS" not in block:
        return "unset"
    return "1" if block["CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS"] == "1" else "other"


def model_class(block: dict, key: str) -> str:
    return alias_or_other(block[key]) if key in block else "unset"


def settings_items(ctx: Ctx, kind: str, path: Path) -> list[dict]:
    prefix = f"claude.settings.{kind}."
    status, data, reason = ctx.read(path)
    digest = hashlib.sha256(data).hexdigest() if data is not None else None
    items = [ctx.item(prefix + "sha256", status, digest, reason, path)]
    every_derived = SETTINGS_DERIVED + BEHAVIOUR_SUFFIXES
    if status != OK:
        return items + [ctx.item(prefix + name, status, None, reason, path) for name in every_derived]
    try:
        document = json.loads(data.decode("utf-8"))
        if not isinstance(document, dict):
            raise ValueError("not an object")
    except (ValueError, UnicodeDecodeError, RecursionError):
        return items + [ctx.item(prefix + name, ERROR, None, "unparsable_json", path) for name in every_derived]
    block = document.get("env") if isinstance(document.get("env"), dict) else {}
    values = {"effort_level_env_unset": "CLAUDE_CODE_EFFORT_LEVEL" not in block,
              "agent_teams_env": teams_class(block),
              "subagent_model_env": model_class(block, "CLAUDE_CODE_SUBAGENT_MODEL"),
              "has_model_settings": "modelSettings" in document,
              "has_effort_level": "effortLevel" in document,
              "advisor_model": model_class(document, "advisorModel")}
    for name in ("subagent_model_env", "advisor_model"):
        if values[name] not in (UNSET, OTHER):
            ctx.public_values.add(values[name])
    return items + [ctx.item(prefix + name, OK, value, None, path) for name, value in values.items()] + \
        behaviour_items(ctx, prefix, document, path)


def collect_claude(ctx: Ctx) -> list[dict]:
    items = [ctx.text_item("claude.version", ["claude", "--version"])]
    launcher = ctx.expand(LAUNCHER)
    items.append(ctx.file_item("claude.launcher.sha256", launcher))
    try:
        items.append(ctx.item("claude.launcher.size", OK, launcher.stat().st_size, None, launcher))
    except OSError:
        items.append(ctx.item("claude.launcher.size", MISSING, None, "file_absent", launcher))
    items.extend(binary_items(ctx))
    items.append(ctx.file_item("claude.user_claude_md.sha256", ctx.home / ".claude" / "CLAUDE.md"))
    items.append(ctx.file_item("claude.user_rtk_md.sha256", ctx.home / ".claude" / "RTK.md"))
    for kind, path in (("user", ctx.home / ".claude" / "settings.json"), ("project", ctx.repo / ".claude" / "settings.json"),
                       ("local", ctx.repo / ".claude" / "settings.local.json")):
        items.extend(settings_items(ctx, kind, path))
    items.append(ctx.item("claude.process.effort_level_unset", OK, "CLAUDE_CODE_EFFORT_LEVEL" not in ctx.env))
    items.append(ctx.item("claude.process.agent_teams_env", OK, teams_class(ctx.env)))
    items.append(ctx.item("claude.process.subagent_model_env", OK, model_class(ctx.env, "CLAUDE_CODE_SUBAGENT_MODEL")))
    items.extend(mcp_items(ctx))
    return items


def binary_items(ctx: Ctx) -> list[dict]:
    link = ctx.expand(CLAUDE_BINARY)
    ids = ("claude.binary.version_name", "claude.binary.size", "claude.binary.sha256")
    try:
        target = Path(os.path.realpath(link))
        if not target.is_file():
            return [ctx.item(item_id, MISSING, None, "file_absent", link) for item_id in ids]
        if target.parent.name != "versions" or not plain_name(target.name, "._-+", 64):
            return [ctx.item(item_id, MISSING, None, "not_versioned_layout", link) for item_id in ids]
        size = target.stat().st_size
    except OSError:
        return [ctx.item(item_id, ERROR, None, "os_error", link) for item_id in ids]
    status, digest, reason = ctx.hash_file(target)
    return [ctx.item(ids[0], OK, target.name, None, link), ctx.item(ids[1], OK, size, None, link),
            ctx.item(ids[2], status, digest, reason, link)]


def mcp_items(ctx: Ctx) -> list[dict]:
    result = ctx.run(["claude", "mcp", "list"], timeout=90.0)
    if result.state == "missing":
        return [ctx.item("claude.mcp_count", MISSING, None, "tool_absent")]
    if result.state != "ok":
        return [ctx.item("claude.mcp_count", ERROR, None, result.state)]
    servers = parse_mcp_list(result.out)
    if servers is None:
        return [ctx.item("claude.mcp_count", ERROR, None, "unrecognized_output")]
    return [ctx.item("claude.mcp_count", OK, len(servers))] + [ctx.item("claude.mcp." + name, OK, connected)
                                                                for name, connected in sorted(servers.items())]


def collect_codex(ctx: Ctx) -> list[dict]:
    home = ctx.home / ".codex"
    profile = home / "stack-worker.config.toml"
    return [ctx.text_item("codex.version", ["codex", "--version"]),
            ctx.file_item("codex.config.sha256", home / "config.toml"),
            ctx.file_item("codex.stack_worker_profile.sha256", profile),
            ctx.item("codex.stack_worker_profile.present", OK, profile.is_file(), None, profile),
            ctx.file_item("codex.agents_md.sha256", home / "AGENTS.md"),
            ctx.file_item("codex.rtk_md.sha256", home / "RTK.md")]


# ------------------------------------------------------------------- the Codex role carriers, their layers, codex itself


def codex_home(ctx: Ctx) -> tuple[Optional[Path], bool]:
    """(the Codex home, whether its location may be stored), located as scripts/adoption_status.py client_wiring does:
    $CODEX_HOME when it is set and not empty, else ~/.codex. The variable names a path this tool reads, so it must be
    absolute and meet the path policy, and a location that came from it is not stored; None when it is refused."""
    value = ctx.env.get(CODEX_HOME_VARIABLE)
    if not value:
        return ctx.home / ".codex", True
    if os.path.isabs(value):  # a relative value or `~` names a folder this tool cannot know: Codex resolves neither here
        try:
            return check_path_policy(value, ctx.home, ctx.repo, allow_relative=False), False
        except PathRefused:
            pass
    return None, False


def path_kind(path: Path) -> str:
    """absent | dir | link | file | other | error, by lstat: a link is reported and never followed."""
    try:
        mode = os.lstat(path).st_mode
    except FileNotFoundError:
        return "absent"
    except OSError:
        return "error"
    if stat.S_ISLNK(mode):
        return "link"
    if stat.S_ISDIR(mode):
        return "dir"
    return "file" if stat.S_ISREG(mode) else "other"


def toml_names(folder: Path) -> tuple[Optional[list[str]], Optional[str]]:
    """(the sorted relative names of the *.toml files below `folder`, reason), the way codex-rs/agent-roles/src/discovery.rs
    collects role files at rust-v0.157.1 and tools/adoption/codex_roles.py agents_toml_count counts them: recursively, by the
    exact extension. A link to a file named *.toml is listed and never read. Codex follows links (LocalFileSystem::read_directory
    takes a link's target's type, codex-rs/exec-server/src/local_file_system.rs:710-735; checked against codex-cli 0.157.1
    through `codex doctor --json` by tests/test_codex_worker_lane.py CodexIntegrationTests.test_codex_follows_links_below_agents_and_the_role_count_never_undercounts_it), so it enters a linked folder; this never does, and a set that skipped one would undercount:
    a link to a folder anywhere below, whatever its name, is (None, "linked_folder"). No names for an absent folder ([]), and
    (None, reason) when `folder` is not a real folder, a folder link is below it, or any part of it cannot be read."""
    kind = path_kind(folder)
    if kind == "absent":
        return [], None
    if kind != "dir":
        return None, "unreadable" if kind == "error" else "not_a_directory"
    failed: list[OSError] = []
    names: list[str] = []
    for current, directories, files in os.walk(folder, followlinks=False, onerror=failed.append):
        # os.walk lists a link to a folder with the directories and does not enter it: unknown, never skipped.
        if any(path_kind(Path(current) / name) == "link" for name in directories):
            return None, "linked_folder"
        for name in files:
            if name.endswith(".toml") and len(name) > len(".toml"):
                names.append((Path(current) / name).relative_to(folder).as_posix())
    return (None, "unreadable") if failed else (sorted(names), None)


def role_tables_in(ctx: Ctx, path: Path) -> tuple[Optional[int], Optional[str]]:
    """(the number of [agents.<name>] tables in one TOML file, reason): 0 for an absent file. The scalar keys of [agents]
    (enabled, max_concurrent_threads_per_session, ...) are not roles; agent-roles/src/loader.rs reads each table under it."""
    status, data, reason = ctx.read(path, 1 << 20)
    if status == MISSING:
        return 0, None
    if status != OK:
        return None, reason
    try:
        import tomllib  # standard library from Python 3.11
    except ImportError:
        return None, "no_toml_parser"
    try:
        agents = tomllib.loads(data.decode("utf-8")).get("agents")
    except (ValueError, UnicodeDecodeError, RecursionError):  # TOMLDecodeError is a ValueError
        return None, "unparsable"
    return sum(1 for value in agents.values() if isinstance(value, dict)) if isinstance(agents, dict) else 0, None


def count_item(ctx: Ctx, item_id: str, folder: Path) -> dict:
    names, reason = toml_names(folder)
    return ctx.item(item_id, OK, len(names)) if names is not None else ctx.item(item_id, ERROR, None, reason)


def tables_item(ctx: Ctx, item_id: str, files: list[Path]) -> dict:
    total = 0
    for path in files:
        tables, reason = role_tables_in(ctx, path)
        if tables is None:
            return ctx.item(item_id, ERROR, None, reason)
        total += tables
    return ctx.item(item_id, OK, total)


def role_file_item(ctx: Ctx, item_id: str, path: Path, shown: Optional[Path]) -> dict:
    """sha256 of one role carrier. A link is an error: the installer writes regular files, and what Codex loads through a
    link is not known here."""
    kind = path_kind(path)
    if kind == "absent":
        return ctx.item(item_id, MISSING, None, "file_absent", shown)
    if kind == "link":
        return ctx.item(item_id, ERROR, None, "link", shown)
    status, digest, reason = ctx.hash_file(path)
    return ctx.item(item_id, status, digest, reason, shown)


def toml_set_item(ctx: Ctx, item_id: str, folder: Path, shown: Optional[Path]) -> dict:
    """Which carriers the folder holds at its top and how many other *.toml files are below it. A name that is not a
    carrier's is never published, so the value carries no name a host chose."""
    names, reason = toml_names(folder)
    if names is None:
        return ctx.item(item_id, ERROR, None, reason, shown)
    value: dict[str, Any] = {name: name in names for name in CODEX_ROLE_FILES}
    value["other"] = sum(1 for name in names if name not in CODEX_ROLE_FILES)
    return ctx.item(item_id, OK, value, None, shown)


def home_role_items(ctx: Ctx) -> list[dict]:
    ids = ("codex.agents.stack-researcher.sha256", "codex.agents.stack-verifier.sha256", "codex.agents.toml_set",
           "codex.agents.role_tables")
    home, stored = codex_home(ctx)
    if home is None:
        return [ctx.item(item_id, ERROR, None, "refused_path") for item_id in ids]
    agents = home / "agents"
    kind = path_kind(agents)  # a linked or non-folder agents path is refused whole: nothing below it can be attested
    if kind in ("link", "file", "other", "error"):
        items = [ctx.item(item_id, ERROR, None, "unreadable" if kind == "error" else "not_a_directory")
                 for item_id in ids[:3]]
    else:
        items = [role_file_item(ctx, ids[0], agents / CODEX_ROLE_FILES[0], agents / CODEX_ROLE_FILES[0] if stored else None),
                 role_file_item(ctx, ids[1], agents / CODEX_ROLE_FILES[1], agents / CODEX_ROLE_FILES[1] if stored else None),
                 toml_set_item(ctx, ids[2], agents, agents if stored else None)]
    items.append(tables_item(ctx, ids[3], [home / "config.toml", home / f"{CODEX_PROFILE}.config.toml"]))
    return items


def launcher_target(text: str) -> Optional[str]:
    """The absolute path a launcher script ends by executing: its last non-blank line must be exactly
    `exec '<absolute path>' "$@"`, the last line of observability/collector/codex-identity-launcher.sh.example and of the
    older render still installed on the reference host. None for any other shape."""
    last = ""
    for line in reversed(text.splitlines()):
        last = line.strip()
        if last:
            break
    head, tail = "exec '", "' \"$@\""
    if len(last) <= len(head) + len(tail) or not last.startswith(head) or not last.endswith(tail):
        return None
    target = last[len(head):len(last) - len(tail)]
    if "'" in target or "\x00" in target or not os.path.isabs(target):
        return None
    return target


def script_text(ctx: Ctx, path: Path) -> Optional[str]:
    """The text of a script, a file that starts with `#!` and is at most 1 MiB; None for anything else, a binary included
    (only its first two bytes are read)."""
    try:
        if is_credential_store(str(path), ctx.home) or regular_file_problem(path):
            return None
        with open(path, "rb") as handle:
            head = handle.read(2)
            if head != b"#!":
                return None
            rest = handle.read((1 << 20) + 1)
    except OSError:
        return None
    return (head + rest).decode("utf-8", "replace") if len(rest) <= 1 << 20 else None


def binary_item(ctx: Ctx, item_id: str, entry: Path) -> dict:
    """sha256 of the file the codex on PATH executes. On a host with the identity launcher the entry is a script that ends by
    executing another file, and that file is hashed (one hop, read through links; its path meets the path policy and is not
    stored). It is the entry point of the codex install, not necessarily the native executable: the npm package's Node entry
    starts that one, and is what this hashes on the reference host. Otherwise it is the file the entry resolves to, the same
    file as codex.launcher.sha256."""
    text = script_text(ctx, entry)
    target = launcher_target(text) if text is not None else None
    if target is None:
        status, digest, reason = ctx.hash_file(Path(os.path.realpath(entry)))
        return ctx.item(item_id, status, digest, reason)
    try:
        path = check_path_policy(target, ctx.home, ctx.repo, allow_relative=False)
    except PathRefused:
        return ctx.item(item_id, ERROR, None, "refused_path")
    status, digest, reason = ctx.hash_file(path)
    return ctx.item(item_id, status, digest, reason)


def launcher_items(ctx: Ctx) -> list[dict]:
    ids = ("codex.launcher.sha256", "codex.binary.sha256")
    found = shutil.which("codex", path=ctx.env.get("PATH"))
    if found is None:
        return [ctx.item(item_id, MISSING, None, "tool_absent") for item_id in ids]
    entry = Path(os.path.abspath(found))
    status, digest, reason = ctx.hash_file(entry)
    return [ctx.item(ids[0], status, digest, reason), binary_item(ctx, ids[1], entry)]


def parse_codex_mcp_list(text: str) -> Optional[dict]:
    """`codex mcp list --json` (0.157.1): a JSON array with one object per server. Only `name` and `enabled` are read, so no
    transport, environment value, argument or URL can reach a capture. {name: enabled} in name order, or None when the text
    is not that array, a name is not plain, an enabled flag is not a boolean or a name repeats."""
    try:
        entries = json.loads(text)
    except (ValueError, RecursionError):
        return None
    if not isinstance(entries, list):
        return None
    servers: dict[str, bool] = {}
    for entry in entries:
        name, enabled = (entry.get("name"), entry.get("enabled")) if isinstance(entry, dict) else (None, None)
        if not plain_name(name, "._:@+-", 80) or not isinstance(enabled, bool) or name in servers:
            return None
        servers[name] = enabled
    return dict(sorted(servers.items()))


def mcp_server_item(ctx: Ctx, item_id: str, argv: list[str]) -> dict:
    """One effective server set. The command runs in an empty temporary directory, because a checkout's project layer adds
    servers that a launch in another tree never sees."""
    try:
        folder = tempfile.mkdtemp(prefix="freeze-mcp-")
    except OSError:
        return ctx.item(item_id, ERROR, None, "no_scratch_directory")
    try:
        result = ctx.run(argv, timeout=60.0, cwd=Path(folder))
    finally:
        shutil.rmtree(folder, ignore_errors=True)
    if result.state == "missing":
        return ctx.item(item_id, MISSING, None, "tool_absent")
    if result.state != "ok":
        return ctx.item(item_id, ERROR, None, result.state)
    servers = parse_codex_mcp_list(result.out)
    if servers is None:
        return ctx.item(item_id, ERROR, None, "unrecognized_output")
    return ctx.item(item_id, OK, servers)


def collect_codex_roles(ctx: Ctx) -> list[dict]:
    items = home_role_items(ctx)
    items += [count_item(ctx, "codex.system.agents_toml_count", CODEX_SYSTEM_DIR / "agents"),
              tables_item(ctx, "codex.system.role_tables", [CODEX_SYSTEM_DIR / "config.toml"]),
              count_item(ctx, "codex.project.agents_toml_count", ctx.repo / ".codex" / "agents"),
              tables_item(ctx, "codex.project.role_tables", [ctx.repo / ".codex" / "config.toml"])]
    items += launcher_items(ctx)
    items.append(mcp_server_item(ctx, "codex.mcp.servers.default", ["codex", "mcp", "list", "--json"]))
    items.append(mcp_server_item(ctx, "codex.mcp.servers.stack_worker", ["codex", "-p", CODEX_PROFILE, "mcp", "list", "--json"]))
    return items


def collect_tools(ctx: Ctx) -> list[dict]:
    items = [ctx.text_item("tools.rtk.version", ["rtk", "--version"]),
             ctx.file_item("tools.rtk.config.sha256", ctx.home / ".config" / "rtk" / "config.toml"),
             ctx.text_item("tools.node.version", ["node", "--version"]),
             ctx.text_item("tools.python.version", ["python3", "--version"])]
    items.extend(tokenizer_items(ctx))
    for item_id, relative in (("tools.token_manifest.sha256", "tools/token-report/token_manifest.py"),
                              ("tools.token_manifest_test.sha256", "tools/token-report/test_token_manifest.py"),
                              ("tools.token_manifest_template.sha256", "tools/token-report/token_manifest.html.in"),
                              ("tools.token_manifest_full_template.sha256", "tools/token-report/token_manifest.full.html.in")):
        items.append(ctx.file_item(item_id, ctx.repo / relative))
    items.extend(qmd_items(ctx))
    items.extend(parser_items(ctx))
    return items


def tokenizer_items(ctx: Ctx) -> list[dict]:
    package = ctx.expand(ctx.config.get("tokenizer_prefix") or TOKENIZER_PREFIX) / "node_modules" / "gpt-tokenizer"
    status, data, reason = ctx.read(package / "package.json", 1 << 20)
    if status != OK:
        version_item = ctx.item("tools.tokenizer.version", status, None, reason, package / "package.json")
    else:
        try:
            version = json.loads(data.decode("utf-8")).get("version")
        except (ValueError, UnicodeDecodeError, AttributeError, RecursionError):
            version = None
        version_item = (ctx.item("tools.tokenizer.version", OK, version, None, package / "package.json")
                        if isinstance(version, str) and is_plain(version)
                        else ctx.item("tools.tokenizer.version", ERROR, None, "unrecognized_output", package / "package.json"))
    return [version_item,
            ctx.file_item("tools.tokenizer.o200k_base.sha256", package / "cjs" / "encoding" / "o200k_base.js"),
            ctx.file_item("tools.tokenizer.o200k_bpe_ranks.sha256", package / "cjs" / "bpeRanks" / "o200k_base.js")]


def qmd_items(ctx: Ctx) -> list[dict]:
    names = ("documents", "vectors", "pending", "orphaned")
    result = ctx.run(["qmd", "--index", ctx.config.get("qmd_index") or QMD_INDEX, "status"], timeout=60.0)
    if result.state == "missing":
        return [ctx.item(f"tools.qmd.{name}", MISSING, None, "tool_absent") for name in names]
    if result.state != "ok":
        return [ctx.item(f"tools.qmd.{name}", ERROR, None, result.state) for name in names]
    counts = parse_qmd_status(result.out)
    if counts is None:
        return [ctx.item(f"tools.qmd.{name}", ERROR, None, "unrecognized_output") for name in names]
    return [ctx.item(f"tools.qmd.{name}", OK, counts[name]) for name in names]


def parser_key(relative: str) -> str:
    """The item id suffix of a pinned parser file: no node_modules prefix, colons for slashes."""
    return (relative[len("node_modules/"):] if relative.startswith("node_modules/") else relative).replace("/", ":")


def parse_parser_pin(data: bytes) -> tuple[dict, str, dict, str]:
    """(files, lockfile name, packages, default directory) of a shell-parser.pin.json that child-usage.mjs readShellParserPin()
    accepts (both package names with a version and an integrity, a files map, a default directory) and that is safe to read
    from: every relative path stays inside the installed directory. The lockfile name defaults to package-lock.json when the
    pin gives none, as `pin.install.lockfile || 'package-lock.json'` does. Anything else raises ValueError, KeyError or TypeError."""
    pin = json.loads(data.decode("utf-8"))
    files, install, packages = pin["files"], pin["install"], pin["packages"]
    default = install["default_directory"]  # relative to the home directory (shell-parser.pin.json)
    lockfile = install.get("lockfile")
    if lockfile is None or lockfile == "":
        lockfile = DEFAULT_LOCKFILE
    if (not isinstance(files, dict) or not files or not isinstance(packages, dict) or not isinstance(default, str)
            or default.startswith(("/", "~")) or ".." in default.split("/")):
        raise ValueError("shape")
    for relative in (*files, lockfile):
        if not (isinstance(relative, str) and not relative.startswith("/") and ".." not in relative.split("/")
                and plain_name(parser_key(relative), "._:-+", 120)):
            raise ValueError("entry")
    if not all(isinstance(expected, str) and is_hex(expected, 64) for expected in files.values()):
        raise ValueError("entry")
    for name in PARSER_PACKAGES:
        entry = packages[name]
        if not (isinstance(entry, dict) and isinstance(entry.get("version"), str) and entry["version"]
                and isinstance(entry.get("integrity"), str) and entry["integrity"]):
            raise ValueError("package")
    return files, lockfile, {name: packages[name] for name in PARSER_PACKAGES}, default


def lock_matches_pin(data: bytes, packages: dict) -> bool:
    """The lockfile half of verifiedShellParser: packages["node_modules/<name>"] of each of the two pinned packages carries the
    pinned version and integrity. Text that cannot be read as that is no match. The integrity values are compared here and
    never stored (base64 holds slashes, which the sanitized capture refuses)."""
    try:
        document = json.loads(data.decode("utf-8"))
    except (ValueError, UnicodeDecodeError, RecursionError):
        return False
    entries = document.get("packages") if isinstance(document, dict) else None
    if not isinstance(entries, dict):
        return False
    for name in PARSER_PACKAGES:
        entry = entries.get("node_modules/" + name)
        if not (isinstance(entry, dict) and entry.get("version") == packages[name]["version"]
                and entry.get("integrity") == packages[name]["integrity"]):
            return False
    return True


def parser_directory(ctx: Ctx, default: str) -> tuple[Optional[Path], bool]:
    """(directory, whether its location may be stored) in the order verifiedShellParser resolves it: the configured parser_dir
    (the kernel's --shell-parser argument), then the CHILD_USAGE_SHELL_PARSER variable (an empty one is skipped, as `a || b`
    does), then the pin's default directory under the home directory. The variable names a path the kernel reads, so it meets
    the path policy; it must be absolute, because the kernel resolves a relative one against a working directory this tool
    does not know and never expands `~`. A location that came from the environment is not stored. None when it is refused."""
    configured = ctx.config.get("parser_dir")
    if configured:
        return ctx.expand(configured), True
    value = ctx.env.get(PARSER_ENV)
    if value:
        try:
            if not os.path.isabs(value):
                raise PathRefused("invalid")
            return check_path_policy(value, ctx.home, ctx.repo), False
        except PathRefused:
            return None, False
    return ctx.home / default, True


def parser_items(ctx: Ctx) -> list[dict]:
    """The install child-usage.mjs would load, checked the way it checks it: each file the pin names is hashed in the installed
    parser directory, and so is the lockfile, which must list both pinned packages with the pinned version and integrity.
    all_match_pin is true exactly when the kernel would accept the install; the pin itself is never trusted for a value."""
    status, data, reason = ctx.read(ctx.repo / PARSER_PIN, 1 << 20)
    if status != OK:
        return [ctx.item("tools.parser.all_match_pin", status, None, "no_pin_file" if status == MISSING else reason)]
    try:
        files, lockfile, packages, default = parse_parser_pin(data)
    except (ValueError, KeyError, TypeError, AttributeError, UnicodeDecodeError, RecursionError):
        return [ctx.item("tools.parser.all_match_pin", ERROR, None, "unrecognized_pin")]
    root, stored = parser_directory(ctx, default)
    if root is None:
        return [ctx.item("tools.parser.all_match_pin", ERROR, None, "refused_path")]
    items = []
    matches = True
    for relative, expected in sorted(files.items()):
        item_status, digest, item_reason = ctx.hash_file(root / relative)
        items.append(ctx.item("tools.parser.file." + parser_key(relative), item_status, digest, item_reason,
                              root / relative if stored else None))
        matches = matches and item_status == OK and digest == expected
    lock_status, lock_data, lock_reason = ctx.read(root / lockfile, 1 << 22)
    if lockfile not in files:  # a lockfile the pin also lists under files is hashed once, above
        items.append(ctx.item("tools.parser.file." + parser_key(lockfile), lock_status,
                              hashlib.sha256(lock_data).hexdigest() if lock_data is not None else None, lock_reason,
                              root / lockfile if stored else None))
    matches = matches and lock_status == OK and lock_matches_pin(lock_data or b"", packages)
    items.append(ctx.item("tools.parser.all_match_pin", OK, matches))
    return items


def run_repo_script(ctx: Ctx, name: str, args: list[str], timeout: float,
                    accepted: tuple[int, ...]) -> tuple[str, Optional[dict], Optional[str]]:
    """(status, JSON report, reason) of one script of the checkout run with the tool's own interpreter. `accepted` are
    the exit codes that come with a usable report: adoption_status.py exits 2 for a missing prerequisite and still prints
    it; codex_quota.py exits 2 when it read no snapshot, which is an error here."""
    script = ctx.repo / "scripts" / name
    if not script.is_file():
        return MISSING, None, "script_absent"
    result = ctx.run([sys.executable, "-B", str(script), *args], timeout=timeout)
    if result.state == "missing":
        return MISSING, None, "interpreter_absent"
    if result.state == "timeout":
        return ERROR, None, "timeout"
    if result.code not in accepted:
        return ERROR, None, f"exit_{result.code}"
    try:
        report = json.loads(result.out)
    except (ValueError, RecursionError):
        return ERROR, None, "invalid_json"
    if not isinstance(report, dict):
        return ERROR, None, "invalid_json"
    return OK, report, None


def flatten_counts(prefix: str, node: Any, out: dict[str, Any], depth: int = 0) -> None:
    """Boolean and integer leaves of a nested mapping, as prefix.key.key; anything else (a string) is never taken."""
    if not isinstance(node, dict) or depth > 4:
        return
    for key in sorted(node):
        value = node[key]
        if not plain_name(key, "._-", 60):
            continue
        if isinstance(value, dict):
            flatten_counts(f"{prefix}{key}.", value, out, depth + 1)
        elif isinstance(value, (bool, int)):
            out[f"{prefix}{key}"] = value


def collect_adoption(ctx: Ctx) -> list[dict]:
    items = []
    status, report, reason = run_repo_script(ctx, "adoption_status.py", ["--client-wiring", "--json"], 60.0, (0, 2))
    wiring = report.get("client_wiring") if report else None
    if status == OK and isinstance(wiring, dict) and isinstance(wiring.get("complete"), bool):
        items.append(ctx.item("wiring.complete", OK, wiring["complete"]))
        leaves: dict[str, Any] = {}
        flatten_counts("claude.wiring.", wiring.get("claude"), leaves)
        flatten_counts("claude.wiring.project.", wiring.get("project"), leaves)
        flatten_counts("codex.wiring.", wiring.get("codex"), leaves)
        items.extend(ctx.item(key, OK, value) for key, value in sorted(leaves.items()))
    else:
        items.append(ctx.item("wiring.complete", status if status != OK else ERROR, None,
                              reason or "no_client_wiring"))
    status, report, reason = run_repo_script(ctx, "adoption_status.py",
                                             ["--profile", "token-efficiency", "--pinned-versions", "--json"], 180.0, (0, 2))
    match = report.get("pinned_versions_match") if report else None
    if status == OK and isinstance(match, bool):
        items.append(ctx.item("tools.pinned_versions_match", OK, match))
        pins: dict[str, dict] = {}
        for profile in report.get("profiles") or []:
            entries = profile.get("pinned_versions") if isinstance(profile, dict) else None
            for entry in entries if isinstance(entries, list) else []:
                component = entry.get("id") if isinstance(entry, dict) else None
                if plain_name(component, "._-", 60) and component not in pins:
                    version, matches = entry.get("pinned_version"), entry.get("matches_pin")
                    pins[component] = {"version": version if is_plain(version) else None, "checked": entry.get("checked") is True,
                                       "matches_pin": matches if isinstance(matches, bool) else None}
        items.extend(ctx.item("tools.pinned." + component, OK, value) for component, value in sorted(pins.items()))
    else:
        items.append(ctx.item("tools.pinned_versions_match", status if status != OK else ERROR, None,
                              reason or "not_reported"))
    return items


def service_units(config: dict) -> list[tuple[str, str]]:
    """(unit, class): the nine defaults are always frozen; a configured unit is frozen unless it says informational."""
    return [(unit, FROZEN) for unit in DEFAULT_UNITS] + [
        (entry["name"], entry["class"]) for entry in config.get("units", []) if entry["name"] not in DEFAULT_UNITS]


def collect_services(ctx: Ctx) -> list[dict]:
    if ctx.platform != "linux":
        return ctx.not_applicable("services")
    items = []
    for unit, _ in service_units(ctx.config):
        items.extend(unit_items(ctx, unit))
    return items


def unit_items(ctx: Ctx, unit: str) -> list[dict]:
    base = f"services.{unit}."
    names = ("load_state", "active_state", "main_pid", "n_restarts", "config_sha256")
    result = ctx.run(["systemctl", "--user", "show", unit, "-p", "LoadState", "-p", "ActiveState", "-p", "MainPID",
                      "-p", "NRestarts", "-p", "ExecStart"], timeout=30.0)
    if result.state == "missing":
        return [ctx.item(base + name, MISSING, None, "tool_absent") for name in names]
    if result.state != "ok":
        return [ctx.item(base + name, ERROR, None, result.state) for name in names]
    props = parse_systemd_show(result.out)
    load_state = props.get("LoadState")
    if not load_state or not plain_name(load_state, "-_", 32):
        return [ctx.item(base + name, ERROR, None, "unrecognized_output") for name in names]
    items = [ctx.item(base + "load_state", OK, load_state)]
    if load_state != "loaded":
        return items + [ctx.item(base + name, MISSING, None, "unit_not_loaded") for name in names[1:]]
    active = props.get("ActiveState", "")
    pid, restarts = leading_int(props.get("MainPID", "x")), leading_int(props.get("NRestarts", "x"))
    if not plain_name(active, "-_", 32) or pid is None or restarts is None:
        return items + [ctx.item(base + name, ERROR, None, "unrecognized_output") for name in names[1:]]
    items += [ctx.item(base + "active_state", OK, active), ctx.item(base + "main_pid", OK, pid),
              ctx.item(base + "n_restarts", OK, restarts)]
    candidate = exec_start_config_path(props.get("ExecStart", ""))
    if candidate is None:
        return items + [ctx.item(base + "config_sha256", NOT_APPLICABLE, None, "no_config_flag")]
    try:
        path = check_path_policy(candidate, ctx.home, ctx.repo, allow_relative=False)
    except PathRefused:
        return items + [ctx.item(base + "config_sha256", ERROR, None, "refused_path")]
    return items + [ctx.file_item(base + "config_sha256", path)]


def collect_gateways(ctx: Ctx) -> list[dict]:
    items = []
    for gateway in ctx.config.get("gateways", []):
        answers: dict[str, tuple] = {}
        for route in gateway["routes"]:
            item_id = f"gateways.{gateway['id']}.route.{route['id']}"
            status, token, body, headers = fetch_route(gateway["host"], gateway["port"], route["path"])
            digest = None
            if status == OK:
                try:
                    digest = digest_body(body, route["ignore_keys"])
                except (ValueError, RecursionError):
                    status, token = ERROR, "not_json"
            if status == OK:
                items.append(ctx.item(item_id, OK, digest))
            else:  # an error item keeps its token (http_401, not_json, timeout, unreachable) as its value
                spec = ctx.spec_for(item_id)
                items.append(make_item(item_id, spec.cls, ERROR, token, spec.method, "request_failed"))
            answers[route["id"]] = (status, body, headers)
        wanted = gateway.get("build_id")
        if wanted:
            items.append(build_id_item(ctx, gateway, wanted, answers))
    return items


def build_id_item(ctx: Ctx, gateway: dict, wanted: dict, answers: dict) -> dict:
    item_id = f"gateways.{gateway['id']}.build_id"
    status, body, headers = answers.get(wanted["route"], (ERROR, None, {}))
    if status != OK:
        return ctx.item(item_id, ERROR, None, "route_failed")
    if wanted.get("header"):
        value = headers.get(wanted["header"].lower())
    else:
        value = body
        for part in wanted["field"].split("."):
            value = value.get(part) if isinstance(value, dict) else None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        value = str(value)
    if isinstance(value, str) and value and len(value) <= 80 and is_plain(value):
        return ctx.item(item_id, OK, value)
    return ctx.item(item_id, ERROR, None, "build_id_not_found")


def fetch_route(host: str, port: int, path: str) -> tuple[str, str, Any, dict]:
    """One unauthenticated GET, no proxy, no redirect: (status, token, parsed body, lower-cased headers)."""
    connection = http.client.HTTPConnection(host, port, timeout=10)
    try:
        connection.request("GET", path, headers={"Accept": "application/json", "User-Agent": f"freeze-snapshot/{TOOL_VERSION}",
                                                 "Connection": "close"})
        response = connection.getresponse()
        raw = response.read(8 << 20)
        headers = {key.lower(): value for key, value in response.getheaders()}
        if not 200 <= response.status < 300:
            return ERROR, f"http_{response.status}", None, headers
        try:
            return OK, "ok", json.loads(raw.decode("utf-8")), headers
        except (ValueError, UnicodeDecodeError, RecursionError):
            return ERROR, "not_json", None, headers
    except socket.timeout:
        return ERROR, "timeout", None, {}
    except (OSError, http.client.HTTPException):
        return ERROR, "unreachable", None, {}
    finally:
        connection.close()


def collect_extra(ctx: Ctx) -> list[dict]:
    return [ctx.file_item(f"extra.{entry['id']}", ctx.expand(entry["path"])) for entry in ctx.config.get("files", [])]


def collect_capacity(ctx: Ctx) -> list[dict]:
    items = codex_capacity(ctx) + claude_capacity(ctx)
    try:
        items.append(ctx.item("capacity.host.load_average", OK, [round(value, 2) for value in os.getloadavg()]))
    except (OSError, AttributeError):
        items.append(ctx.item("capacity.host.load_average", ERROR, None, "os_error"))
    if ctx.platform != "linux":
        items.append(ctx.item("capacity.host.memory_available_mib", NOT_APPLICABLE, None, "platform"))
    else:
        items.append(memory_item(ctx))
    return items


def memory_item(ctx: Ctx) -> dict:
    status, data, reason = ctx.read(Path("/proc/meminfo"), 1 << 20)
    if status != OK:
        return ctx.item("capacity.host.memory_available_mib", status, None, reason)
    for line in data.decode("utf-8", "replace").splitlines():
        label, separator, rest = line.partition(":")
        if separator and label == "MemAvailable":
            kib = leading_int(rest)
            if kib is not None:
                return ctx.item("capacity.host.memory_available_mib", OK, kib // 1024)
    return ctx.item("capacity.host.memory_available_mib", ERROR, None, "unrecognized_output")


def codex_capacity(ctx: Ctx) -> list[dict]:
    names = ("capacity.codex.weekly_used_percent", "capacity.codex.weekly_resets_at_utc")
    status, report, reason = run_repo_script(ctx, "codex_quota.py", ["--json"], 60.0, (0,))
    if status != OK or report is None:
        return [ctx.item(name, status if status != OK else ERROR, None, reason or "quota_failed") for name in names]
    windows = [report if isinstance(report.get("window_minutes"), (int, float)) else None, report.get("secondary")]
    for window in windows:
        if isinstance(window, dict) and window.get("window_minutes") == 10080:
            used, resets = window.get("used_percent"), window.get("resets_at_utc")
            if isinstance(used, (int, float)) and not isinstance(used, bool) and isinstance(resets, str) and is_plain(resets):
                return [ctx.item(names[0], OK, used), ctx.item(names[1], OK, resets)]
            return [ctx.item(name, ERROR, None, "unrecognized_output") for name in names]
    return [ctx.item(name, MISSING, None, "no_weekly_window") for name in names]


def claude_capacity(ctx: Ctx) -> list[dict]:
    """One headless Haiku call, isolated from the user's settings, hooks, MCP servers and telemetry, whose only use is the
    rate_limit_event it returns. --verbose makes the output the event array whatever the user's settings say."""
    ids = [f"capacity.claude.{window}_{part}" for window in ("five_hour", "seven_day")
           for part in ("utilization_fraction", "resets_at_utc")]
    if not ctx.probe:
        return [ctx.item(item_id, MISSING, None, "skipped") for item_id in ids]
    environment = {key: value for key, value in ctx.env.items() if key not in ("OTEL_RESOURCE_ATTRIBUTES", "RTK_DB_PATH")}
    try:
        folder = tempfile.mkdtemp(prefix="freeze-probe-")
    except OSError:
        return [ctx.item(item_id, ERROR, None, "no_scratch_directory") for item_id in ids]
    try:
        result = ctx.run(["claude", "-p", "OK", "--model", "haiku", "--output-format", "json", "--verbose",
                          "--no-session-persistence", "--setting-sources", "project"],
                         timeout=120.0, cwd=Path(folder), env=environment)
    finally:
        shutil.rmtree(folder, ignore_errors=True)
    if result.state == "missing":
        return [ctx.item(item_id, MISSING, None, "tool_absent") for item_id in ids]
    if result.state not in ("ok", "exit"):
        return [ctx.item(item_id, ERROR, None, result.state) for item_id in ids]
    # A call rejected at the session limit exits 1 (HTTP 429) and still returns the rate_limit_event, whose numbers are what
    # matters then; a failed call without the event is an error.
    failed = result.state == "exit"
    try:
        events = json.loads(result.out)
    except (ValueError, RecursionError):
        return [ctx.item(item_id, ERROR, None, "exit" if failed else "invalid_json") for item_id in ids]
    windows = parse_unified_windows(events)
    if windows is None:
        return [ctx.item(item_id, ERROR if failed else MISSING, None, "exit" if failed else "no_rate_limit_event")
                for item_id in ids]
    items = []
    for window in ("five_hour", "seven_day"):
        found = windows.get(window)
        if found is None:
            items += [ctx.item(f"capacity.claude.{window}_{part}", MISSING, None, "window_absent")
                      for part in ("utilization_fraction", "resets_at_utc")]
        else:
            items += [ctx.item(f"capacity.claude.{window}_utilization_fraction", OK, found["utilization"]),
                      ctx.item(f"capacity.claude.{window}_resets_at_utc", OK, found["resets_at_utc"])]
    return items


def collect_time(ctx: Ctx) -> list[dict]:
    tool = Path(__file__).resolve()
    revision = ctx.git(["rev-parse", "HEAD"], directory=tool.parent)
    text = revision.out.strip()
    status, digest, reason = ctx.hash_file(tool)
    return [ctx.item("time.capture_start_utc", OK, ctx.start), ctx.item("time.capture_end_utc", OK, utc_now()),
            ctx.item("time.tool_version", OK, TOOL_VERSION),
            (ctx.item("time.tool_revision", OK, text) if revision.state == "ok" and is_hex(text, 40)
             else ctx.item("time.tool_revision", MISSING, None, "not_a_checkout")),
            ctx.item("time.tool_sha256", status, digest, reason)]


COLLECTORS: tuple[tuple[str, Callable[[Ctx], list[dict]]], ...] = (
    ("repo", collect_repo),
    ("roles", collect_roles),
    ("hooks", collect_hooks),
    ("claude", collect_claude),
    ("codex", collect_codex),
    ("codex_roles", collect_codex_roles),
    ("tools", collect_tools),
    ("adoption", collect_adoption),
    ("services", collect_services),
    ("gateways", collect_gateways),
    ("extra", collect_extra),
    ("capacity", collect_capacity),
)


def note(message: str) -> None:
    print(f"freeze-snapshot: {message}", file=sys.stderr)


def run_collectors(ctx: Ctx) -> list[dict]:
    """Run every collector; one that fails becomes error items for its own catalogue entries and never stops the capture."""
    items: list[dict] = []
    for owner, collector in COLLECTORS:
        try:
            produced = collector(ctx)
        except Exception as error:  # noqa: BLE001 - a collector bug must not lose the other items
            note(f"collector {owner} failed: {type(error).__name__}")
            produced = [make_item(spec.id, spec.cls, ERROR, None, spec.method, "collector_exception")
                        for spec in ctx.specs if spec.owner == owner and not spec.id.endswith("*")]
        items.extend(produced)
    try:
        items.extend(collect_time(ctx))
    except Exception as error:  # noqa: BLE001
        note(f"collector time failed: {type(error).__name__}")
    by_id = {item["id"]: item for item in items}
    for spec in ctx.specs:
        if not spec.id.endswith("*") and spec.id not in by_id:
            by_id[spec.id] = make_item(spec.id, spec.cls, ERROR, None, spec.method, "collector_did_not_report")
    return [by_id[item_id] for item_id in sorted(by_id)]


# ---------------------------------------------------------------------------------------------- privacy guard


def iter_strings(value: Any) -> Iterable[str]:
    stack = [value]
    while stack:
        current = stack.pop()
        if isinstance(current, str):
            yield current
        elif isinstance(current, dict):
            for key, inner in current.items():
                yield str(key)
                stack.append(inner)
        elif isinstance(current, (list, tuple)):
            stack.extend(current)


def identity_words() -> list[str]:
    """The user and host names the output must never carry, matched as whole words."""
    names = {os.environ.get("USER", ""), os.environ.get("LOGNAME", ""), socket.gethostname(),
             socket.gethostname().split(".")[0], os.environ.get("HOSTNAME", "")}
    if pwd is not None:
        try:
            names.add(pwd.getpwuid(os.getuid()).pw_name)
        except KeyError:
            pass
    return sorted(name.lower() for name in names if len(name) >= 3)


def has_word(text: str, word: str) -> bool:
    start = 0
    while True:
        found = text.find(word, start)
        if found < 0:
            return False
        before = text[found - 1] if found else " "
        after = text[found + len(word)] if found + len(word) < len(text) else " "
        if not before.isalnum() and not after.isalnum():
            return True
        start = found + 1


WORD_MARK = "\x00word:"  # a NUL cannot occur in an environment value, so this prefix cannot collide with one


def catalogue_tokens(ctx: Ctx) -> tuple[str, set[str]]:
    """The tool's own static text (item ids and methods) and its lower-case alphanumeric words."""
    structure = [SCHEMA, FROZEN, INFORMATIONAL, *STATUSES, "sanitized", "label", "platform", "items", "id", "class", "status",
                 "value", "method", "reason", "path", UNSET, OTHER, *PERMISSION_MODES, *CROSS_SESSION_VALUES,
                 *UPDATE_CHANNELS, *WORKFLOW_SIZES, *EFFORT_LEVELS]
    text = "\n".join([f"{spec.id}\n{spec.method}" for spec in ctx.specs] + structure)
    words: set[str] = set()
    current: list[str] = []
    for char in text.lower() + " ":
        if char.isalnum():
            current.append(char)
        elif current:
            words.add("".join(current))
            current = []
    return text, words


def forbidden_values(ctx: Ctx) -> list[str]:
    """What the output must not carry: environment values of eight characters or more (except the model alias), the home
    and checkout paths, the permission rules read from the settings files, and the user and host names (entries with
    WORD_MARK, matched as whole words). A value or name that the tool's own catalogue text already contains (item ids,
    methods, the documented setting values) cannot be a leak of it, and refusing it would stop every capture on a host
    whose user or variable happens to equal a catalogue word, so it is not listed. Nor is a model alias that a settings
    file states and the tool prints on purpose."""
    text, words = catalogue_tokens(ctx)
    values = {value for key, value in os.environ.items()
              if len(value) >= MIN_SECRET_LENGTH and key != ALIAS_EXEMPT_VARIABLE and value not in text}
    values.update(rule for rule in ctx.private_values if len(rule) >= MIN_SECRET_LENGTH and rule not in text)
    values -= ctx.public_values  # a model alias that a settings file states and the tool prints is not a leak of an env value
    values.update({str(ctx.home), str(ctx.repo), os.path.realpath(ctx.home), os.path.realpath(ctx.repo),
                   os.path.expanduser("~")})
    listed = sorted(value for value in values if value and value != "/")
    return listed + [WORD_MARK + name for name in identity_words() if name not in words]


def guard_output(record: dict, text: str, forbidden: list[str], sanitized: bool) -> None:
    """Refuse output that carries an environment value, a host path or an identity; the backstop behind the collectors.
    `forbidden` entries are substrings, or whole words when they start with WORD_MARK."""
    substrings = [value for value in forbidden if not value.startswith(WORD_MARK)]
    words = [value[len(WORD_MARK):] for value in forbidden if value.startswith(WORD_MARK)]

    def leaks(string: str) -> bool:
        return (any(value in string for value in substrings) or any(has_word(string.lower(), word) for word in words)
                or (sanitized and any(char in PATH_CHARS for char in string)))

    bad: set[str] = {str(item.get("id", "item")) for item in record.get("items", [])
                     if any(leaks(string) for string in iter_strings(item))}
    if any(leaks(string) for string in iter_strings({key: value for key, value in record.items() if key != "items"})):
        bad.add("record")
    if not bad and (any(value in text for value in substrings) or any(has_word(text.lower(), word) for word in words)):
        bad.add("record")
    if bad:
        raise PrivacyRefusal(sorted(bad))


# ------------------------------------------------------------------------------------------ configuration


def load_config(path: Optional[str], home: Path, repo: Optional[Path]) -> dict:
    """Validate freeze.json: extra frozen files, extra units, an alternative qmd index, parser and tokenizer locations,
    and loopback gateways. Unknown keys and every unusable value are usage errors; no message names a path."""
    config: dict[str, Any] = {"files": [], "units": [], "gateways": []}
    if path is None:
        return config
    try:
        with open(path, "rb") as handle:
            raw = json.loads(handle.read(1 << 20).decode("utf-8"))
    except (OSError, ValueError, UnicodeDecodeError, RecursionError):
        raise UsageError("cannot read the configuration file as JSON")
    if not isinstance(raw, dict):
        raise UsageError("the configuration must be a JSON object")
    unknown = sorted(set(raw) - {"files", "units", "qmd_index", "parser_dir", "tokenizer_prefix", "gateways"})
    if unknown:
        raise UsageError(f"unknown configuration keys: {', '.join(unknown)[:120]}")

    def path_value(text: Any, where: str) -> str:
        if not isinstance(text, str):
            raise UsageError(f"{where} must be a string path")
        try:
            check_path_policy(text, home, repo)
        except PathRefused as refusal:
            raise UsageError(f"{where}: the path {PATH_PHRASES[refusal.reason]}")
        return text

    def array(name: str, limit: int) -> list:
        value = raw.get(name, [])
        if not isinstance(value, list) or len(value) > limit:
            raise UsageError(f"{name} must be a list of at most {limit} entries")
        return value

    seen: set[str] = set()
    for index, entry in enumerate(array("files", 100)):
        where = f"files[{index}]"
        if not isinstance(entry, dict) or set(entry) - {"id", "path", "class"} or "path" not in entry:
            raise UsageError(f"{where} must be an object with id, path and an optional class")
        if not plain_name(entry.get("id"), "._-", 48) or entry["id"] in seen:
            raise UsageError(f"{where}: id must be a unique 1 to 48 character token")
        seen.add(entry["id"])
        cls = entry.get("class", FROZEN)
        if cls not in (FROZEN, INFORMATIONAL):
            raise UsageError(f"{where}: class must be frozen or informational")
        config["files"].append({"id": entry["id"], "path": path_value(entry["path"], where), "class": cls})
    for index, entry in enumerate(array("units", 100)):
        where = f"units[{index}]"
        if isinstance(entry, str):
            entry = {"name": entry}
        if not isinstance(entry, dict) or set(entry) - {"name", "class"} or "name" not in entry:
            raise UsageError(f"{where} must be a unit name or an object with name and an optional class")
        if not plain_name(entry["name"], "._@:-", 80):
            raise UsageError(f"{where}: name must be a systemd unit name")
        cls = entry.get("class", FROZEN)
        if cls not in (FROZEN, INFORMATIONAL):
            raise UsageError(f"{where}: class must be frozen or informational")
        if entry["name"] in DEFAULT_UNITS:
            if cls != FROZEN:
                raise UsageError(f"{where}: a default unit is always frozen")
        elif all(entry["name"] != known["name"] for known in config["units"]):
            config["units"].append({"name": entry["name"], "class": cls})
    if "qmd_index" in raw:
        if not plain_name(raw["qmd_index"], "._-", 64):
            raise UsageError("qmd_index must be a short token")
        config["qmd_index"] = raw["qmd_index"]
    for key in ("parser_dir", "tokenizer_prefix"):
        if key in raw:
            config[key] = path_value(raw[key], key)
    seen_gateways: set[str] = set()
    for index, entry in enumerate(array("gateways", 20)):
        config["gateways"].append(load_gateway(entry, f"gateways[{index}]", seen_gateways))
    return config


def load_gateway(entry: Any, where: str, seen: set[str]) -> dict:
    if not isinstance(entry, dict) or set(entry) - {"id", "base_url", "routes", "build_id"}:
        raise UsageError(f"{where} must be an object with id, base_url, routes and an optional build_id")
    if not plain_name(entry.get("id"), "_-", 40) or entry["id"] in seen:
        raise UsageError(f"{where}: id must be a unique short token")
    seen.add(entry["id"])
    host, port = parse_loopback(entry.get("base_url"), where)
    routes = entry.get("routes")
    if not isinstance(routes, list) or not 0 < len(routes) <= 50:
        raise UsageError(f"{where}: routes must list 1 to 50 routes")
    parsed, route_ids = [], set()
    for number, route in enumerate(routes):
        label = f"{where}.routes[{number}]"
        if not isinstance(route, dict) or set(route) - {"id", "path", "ignore_keys"}:
            raise UsageError(f"{label} must be an object with id, path and optional ignore_keys")
        if not plain_name(route.get("id"), "_-", 40) or route["id"] in route_ids:
            raise UsageError(f"{label}: id must be a unique short token")
        route_ids.add(route["id"])
        path = route.get("path")
        if (not isinstance(path, str) or not path.startswith("/") or path.startswith("//") or len(path) > 200
                or ".." in path.split("/") or any(char not in ROUTE_CHARS for char in path)):
            raise UsageError(f"{label}: path must start with one slash and use letters, digits and / . _ - : only")
        ignore = route.get("ignore_keys", [])
        if not isinstance(ignore, list) or len(ignore) > 20 or not all(plain_name(key, "._-", 40) for key in ignore):
            raise UsageError(f"{label}: ignore_keys must be a short list of key names")
        parsed.append({"id": route["id"], "path": path, "ignore_keys": list(ignore)})
    build = entry.get("build_id")
    if build is not None:
        if not isinstance(build, dict) or set(build) - {"route", "field", "header"} or build.get("route") not in route_ids \
                or ("field" in build) == ("header" in build):
            raise UsageError(f"{where}: build_id needs a route and exactly one of field or header")
        for key in ("field", "header"):
            if key in build and not plain_name(build[key], "._-", 60):
                raise UsageError(f"{where}: build_id {key} must be a short token")
    return {"id": entry["id"], "host": host, "port": port, "routes": parsed, "build_id": build}


def parse_loopback(url: Any, where: str) -> tuple[str, int]:
    """http://127.0.0.1[:port], http://localhost[:port] or http://[::1][:port], nothing after the authority."""
    prefix = "http://"
    if not isinstance(url, str) or not url.startswith(prefix):
        raise UsageError(f"{where}: base_url must be a plain http loopback origin")
    authority = url[len(prefix):]
    if authority.endswith("/"):
        authority = authority[:-1]
    for char in authority:
        if char in "/@?#\\ ":
            raise UsageError(f"{where}: base_url must be a bare origin with no user, path, query or fragment")
    if authority.startswith("["):
        close = authority.find("]")
        host, rest = authority[:close + 1], authority[close + 1:]
    else:
        host, colon, rest = authority.partition(":")
        rest = ":" + rest if colon else ""
    if host not in LOOPBACK_HOSTS:
        raise UsageError(f"{where}: base_url must name a loopback host (127.0.0.1, localhost or [::1])")
    port = 80
    if rest:
        digits = rest[1:] if rest.startswith(":") else "x"
        if not digits or any(char not in DIGITS for char in digits) or not 0 < int(digits) < 65536:
            raise UsageError(f"{where}: base_url has an unusable port")
        port = int(digits)
    return host.strip("[]"), port


# -------------------------------------------------------------------------------------------- commands


def resolve_home() -> Path:
    return Path(os.path.normpath(os.path.expanduser("~")))


def current_directory() -> Path:
    try:
        return Path.cwd()
    except OSError:
        raise UsageError("the current directory is gone; pass --repo")


def find_checkout(directory: Path, home: Path) -> Path:
    if not directory.is_dir():
        raise UsageError("the checkout is not a directory")
    probe = Ctx(home, directory, dict(os.environ), "linux", [], {}, False)
    result = probe.git(["rev-parse", "--show-toplevel"])
    top = result.out.strip()
    if result.state != "ok" or not top or not os.path.isabs(top):
        raise UsageError("the directory is not inside a git checkout")
    return Path(top)


def command_capture(args: argparse.Namespace) -> int:
    if not plain_name(args.label, "._-", 64):
        raise UsageError("the label must be 1 to 64 letters, digits, dots, dashes or underscores and start with a letter or digit")
    home = resolve_home()
    repo = find_checkout(Path(args.repo) if args.repo else current_directory(), home)
    config = load_config(args.config, home, repo)
    out = Path(os.path.realpath(args.out))
    if under(out, Path(os.path.realpath(repo))):
        raise UsageError("the output directory must be outside the checkout")
    full_path, clean_path = out / f"freeze-{args.label}.json", out / f"freeze-{args.label}.sanitized.json"
    if os.path.lexists(full_path) or os.path.lexists(clean_path):
        raise UsageError("a capture with this label already exists there; captures are never overwritten")
    platform = args.platform or ("darwin" if sys.platform == "darwin" else "linux")
    ctx = Ctx(home, repo, dict(os.environ), platform, build_specs(config), config, not args.no_usage_probe)
    items = run_collectors(ctx)
    forbidden = forbidden_values(ctx)
    records = []
    for sanitized in (False, True):
        shown = [{key: value for key, value in item.items() if not (sanitized and key == "path")} for item in items]
        record = build_record(args.label, shown, sanitized, platform)
        text = json.dumps(record, indent=2) + "\n"
        try:
            guard_output(record, text, forbidden, sanitized)
        except PrivacyRefusal as refusal:
            raise PrivacyRefusal(sorted({safe_label(ctx, item_id) for item_id in refusal.items}), leaking_variables(text))
        records.append(text)
    created = not out.exists()
    try:
        out.mkdir(parents=True, exist_ok=True, mode=0o700)
        if created:
            os.chmod(out, 0o700)
        write_new(full_path, records[0], 0o600)
        try:
            write_new(clean_path, records[1], 0o644)
        except OSError:
            os.unlink(full_path)
            raise
    except OSError:
        raise UsageError("cannot write the capture files")
    counts = {status: sum(1 for item in items if item["status"] == status) for status in STATUSES}
    not_ok = sum(1 for item in items if item["class"] == FROZEN and item["status"] != OK)
    print(f"freeze-snapshot capture: label={args.label} items={len(items)} ok={counts[OK]} missing={counts[MISSING]} "
          f"error={counts[ERROR]} not_applicable={counts[NOT_APPLICABLE]} frozen_not_ok={not_ok}")
    print(f"wrote {full_path.name} (private, mode 0600) and {clean_path.name}")
    return EXIT_OK


def leaking_variables(text: str) -> list[str]:
    """Names of the environment variables whose value the output text contains, so a refusal can be acted on."""
    return sorted(name for name, value in os.environ.items()
                  if len(value) >= MIN_SECRET_LENGTH and name != ALIAS_EXEMPT_VARIABLE and value in text)


def safe_label(ctx: Ctx, item_id: str) -> str:
    """How a refused item is named in the message: a catalogue id as it is, a host-derived family member by its family,
    because the member's own id is the string that carries the value the guard keeps out."""
    if item_id == "record":
        return item_id
    try:
        return ctx.spec_for(item_id).id
    except KeyError:
        return "unknown"


def build_record(label: str, items: list[dict], sanitized: bool, platform: str) -> dict:
    return {
        "schema": SCHEMA,
        "sanitized": sanitized,
        "label": label,
        "platform": platform,
        "items": items,
    }


def write_new(path: Path, text: str, mode: int) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), mode)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(text)
        os.fchmod(handle.fileno(), mode)


def load_record(path: str, which: str) -> dict[str, dict]:
    try:
        with open(path, "rb") as handle:
            raw = handle.read(MAX_JSON_BYTES + 1)
        if len(raw) > MAX_JSON_BYTES:
            raise ValueError("too large")
        document = json.loads(raw.decode("utf-8"))
    except (OSError, ValueError, UnicodeDecodeError, RecursionError):
        raise UsageError(f"cannot read the {which} capture as JSON")
    if not isinstance(document, dict) or document.get("schema") != SCHEMA or not isinstance(document.get("items"), list):
        raise UsageError(f"the {which} file is not a freeze-snapshot capture")
    items: dict[str, dict] = {}
    for item in document["items"]:
        if (not isinstance(item, dict) or not isinstance(item.get("id"), str) or item.get("class") not in (FROZEN, INFORMATIONAL)
                or item.get("status") not in STATUSES or item["id"] in items):
            raise UsageError(f"the {which} capture has a malformed or duplicate item")
        items[item["id"]] = item
    return items


def short(item: dict, full: bool) -> str:
    if item["status"] != OK:
        reason = item.get("reason")
        return item["status"] + (f"({reason})" if isinstance(reason, str) and plain_name(reason, "_", 40) else "")
    value = item.get("value")
    if isinstance(value, str) and not full and len(value) >= 40 and is_hex(value, len(value)):
        return value[:12]
    text = json.dumps(value, sort_keys=True)
    return text if full or len(text) <= 100 else text[:97] + "..."


def command_compare(args: argparse.Namespace) -> int:
    first, second = load_record(args.first, "first"), load_record(args.second, "second")
    counts = {"drift": 0, "missing": 0, "error": 0, "info": 0}
    for item_id in sorted(set(first) | set(second)):
        a_item, b_item = first.get(item_id), second.get(item_id)
        frozen = (a_item or b_item).get("class") == FROZEN
        if a_item is None or b_item is None:
            side = "second" if a_item is None else "first"
            kind = "MISSING" if frozen else "INFO"
            counts["missing" if frozen else "info"] += 1
            print(f"{kind} {item_id} only in the {side} capture")
            continue
        same = a_item["status"] == b_item["status"] and a_item.get("value") == b_item.get("value")
        change = f"{short(a_item, args.full)} -> {short(b_item, args.full)}"
        if not frozen:
            if not same:
                counts["info"] += 1
                print(f"INFO {item_id} {change}")
        elif ERROR in (a_item["status"], b_item["status"]):
            counts["error"] += 1
            print(f"ERROR {item_id} {change}")
        elif not same:
            counts["drift"] += 1
            print(f"DRIFT {item_id} {change}")
    print(f"compare: frozen_drift={counts['drift']} frozen_missing={counts['missing']} frozen_error={counts['error']} "
          f"informational_changed={counts['info']}")
    return EXIT_DRIFT if counts["drift"] + counts["missing"] + counts["error"] else EXIT_OK


def command_check(args: argparse.Namespace) -> int:
    captured, expected = load_record(args.capture, "capture"), load_record(args.expected, "expected")
    passed = failed = 0
    frozen_ids = {item_id for records in (captured, expected) for item_id, item in records.items() if item["class"] == FROZEN}
    for item_id in sorted(frozen_ids):
        got, want = captured.get(item_id), expected.get(item_id)
        if want is None:
            problem = "not in the expectations"
        elif got is None:
            problem = "not in the capture"
        elif got["class"] != want["class"]:
            problem = "class differs"
        else:
            problem = None
            got_status, got_value = got["status"], got.get("value")
            want_status, want_value = want["status"], want.get("value")
            if got_status == want_status and got_value == want_value:
                if got_status == ERROR:
                    problem = "the item is in error, so it attests nothing"
            else:
                problem = f"expected {short(want, False)} got {short(got, False)}"
        if problem is None:
            passed += 1
            if not args.quiet:
                print(f"PASS {item_id}")
        else:
            failed += 1
            print(f"FAIL {item_id} {problem}")
    print(f"check: pass={passed} fail={failed}")
    return EXIT_DRIFT if failed else EXIT_OK


def command_list(args: argparse.Namespace) -> int:
    home = resolve_home()
    repo = find_checkout(Path(args.repo), home) if args.repo else None
    config = load_config(args.config, home, repo)
    specs = [spec for spec in build_specs(config) if args.all or spec.cls == FROZEN]
    if args.json:
        rows = [{"id": spec.id, "class": spec.cls, "family": spec.id.endswith("*"), "owner": spec.owner, "how": spec.how}
                for spec in specs]
        print(json.dumps(rows, indent=2))
    else:
        for spec in specs:
            print(f"{spec.id}\t{spec.how}")
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="freeze_snapshot.py", description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    capture = commands.add_parser("capture", help="write the private and the sanitized capture")
    capture.add_argument("--label", required=True, help="name of the capture (letters, digits, dot, dash, underscore)")
    capture.add_argument("--out", required=True, help="output directory, outside the checkout; created private (0700) if new")
    capture.add_argument("--repo", help="the checkout under freeze (default: the checkout of the current directory)")
    capture.add_argument("--config", help="freeze.json: extra files, units, gateways and location overrides")
    capture.add_argument("--platform", choices=("linux", "darwin"), help="override the detected platform (darwin reports "
                         "services and /proc keys as not_applicable)")
    capture.add_argument("--no-usage-probe", action="store_true",
                         help="skip the one headless Haiku call that reads the Claude five-hour and seven-day windows")
    compare = commands.add_parser("compare", help="list every item that differs between two captures")
    compare.add_argument("first")
    compare.add_argument("second")
    compare.add_argument("--full", action="store_true", help="print whole hashes instead of twelve characters")
    check = commands.add_parser("check", help="compare a capture with the sealed expectations")
    check.add_argument("capture")
    check.add_argument("--expected", required=True, help="the sealed expectations: a sanitized capture")
    check.add_argument("--quiet", action="store_true", help="print failures and the summary only")
    listing = commands.add_parser("list-frozen", help="print the frozen item ids and how to check each")
    listing.add_argument("--config", help="freeze.json whose extra items are listed too")
    listing.add_argument("--repo", help="a checkout, so relative configuration paths are checked against it")
    listing.add_argument("--all", action="store_true", help="include the informational items")
    listing.add_argument("--json", action="store_true", help="print JSON rows: id, class, family, owner, how")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return {"capture": command_capture, "compare": command_compare, "check": command_check,
                "list-frozen": command_list}[args.command](args)
    except UsageError as error:
        note(str(error))
        return EXIT_USAGE
    except PrivacyRefusal as refusal:
        detail = f"; environment variables: {', '.join(refusal.variables[:10])}" if refusal.variables else ""
        note("refused: output strings carry an environment value, a host path or an identity; nothing was written "
             f"(items: {', '.join(refusal.items[:10])}{detail})")
        return EXIT_PRIVACY


if __name__ == "__main__":
    sys.exit(main())
