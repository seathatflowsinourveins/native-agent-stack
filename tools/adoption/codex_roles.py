"""Pure helpers for the two Codex role carriers: adoption/agents/codex/stack-researcher.toml and stack-verifier.toml.

Custom-agent files that Codex discovers under $CODEX_HOME/agents (no [agents.<name>] table); U13 design 3.2, added by
the coordinator's decision of 2026-09-29. One module, shared by tests/test_codex_agents.py, the installer
(tools/adoption/apply_codex_lane.py) and the static `roles` row of tools/adoption/prove_codex_lane.py, so a rule is
defined once. Standard library only, no network, no model call, no regular expression: every scanner is a linear
scan (a backtracking expression was flagged as a denial-of-service risk here before).

  sha256sums, source_problems, byte_problems
        the pinned digests in adoption/agents/codex/SHA256SUMS, and the rule ids a carrier or a repository copy breaks
  structural_problems
        the closed key set, the pins, the lane-neutral description, the F4 block and the added rules; each rule names
        its source in RULES
  agents_toml_count, role_table_count, live_role_tables, system_role_count
        the counts of what Codex would load as a role besides the two carriers
  doctor_role_state, doctor_problem
        what `codex doctor --json` says about the role files, from two reports of one scratch home (counts only)

Sources: openai/codex rust-v0.157.1 (36650394) codex-rs/agent-roles/src/{agent_role_config,loader,discovery}.rs,
codex-rs/core/src/agent/role.rs, codex-rs/cli/src/doctor.rs; rtk-ai/rtk v0.50.0 hooks/rtk-awareness-full.md.
"""

from __future__ import annotations

import functools
import hashlib
import json
import os
import stat
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROLE_FILES = ("stack-researcher.toml", "stack-verifier.toml")
ROLES = tuple(name[: -len(".toml")] for name in ROLE_FILES)
ROLES_SOURCE = ROOT / "adoption" / "agents" / "codex"
EXAMPLES_AGENTS = ROOT / "examples" / "codex-native" / "agents"
SHA256SUMS_NAME = "SHA256SUMS"
PREREGISTRATION = ROOT / "evidence" / "artifacts" / "token-adoption-e2e-20260926" / "preregistration.json"
AGENTS_TEMPLATE = ROOT / "adoption" / "templates" / "codex.AGENTS.template.md"
WORKER_PROFILE_FILE = "stack-worker.config.toml"
# The system config layer is always pushed (config/src/loader/mod.rs); its folder is /etc/codex (config/src/state.rs).
SYSTEM_CODEX_DIR = Path("/etc/codex")

# ---------------------------------------------------------------------------------------------------------------
# Pinned content of the carriers (each independent literal is repeated in tests/test_codex_agents.py, so a change
# here without the same change there fails a test).

ROLE_KEYS = frozenset({"name", "description", "model", "model_reasoning_effort", "developer_instructions"})
# role.rs:33 (DEFAULT_ROLE_NAME) and :337-380 (built_in::configs): a user role of one of these names shadows it.
BUILTIN_ROLES = frozenset({"default", "explorer", "worker"})
ROLE_MODEL = "gpt-6-astra"
ROLE_EFFORT = "max"
UPSTREAM_MARKER = "<!-- native-agent-stack:rtk-upstream rtk-ai/rtk v0.50.0 hooks/rtk-awareness-full.md, verbatim -->\n"
EXCEPTIONS_MARKER = "<!-- native-agent-stack:rtk-exceptions -->\n"
END_MARKER = "<!-- native-agent-stack:codex-user-instructions:end -->"
# Byte identity of upstream hooks/rtk-awareness-full.md (tag commit 1d87b8e719ce0a50c223cd93ca64dd16921f9aec).
RTK_SHA256 = "278274ef3d08c858d4247cc91419c4d74ef922b95719e987b22e896aef10e1fc"
ONE_AGENT_SENTENCE = "You do not spawn, message or follow up with other agents."
WORKING_DIRECTORY_BULLET = (
    "- **Working directory.** A working-directory instruction in the task wins. Context-mode is already bound to "
    "the directory this session was launched in: pass `cwd` to a context-mode call only for a different directory, "
    "and name files under the launch directory by relative path."
)
NO_WEB_SENTENCE = "You do not use web search."
# Each role's own exact-shape sentence. `jq` output is in both: the F4 exceptions list six commands, jq included.
EXACT_SHAPES = {
    "stack-researcher": (
        "For an exact blob from `git show REV:path`, a `diff` whose exit status matters, `git branch`, a complete "
        "`git log`, `jq` output, or `find` on a directory that may not exist, use the native command or "
        "`rtk proxy <command>` (the RTK exceptions below)."
    ),
    "stack-verifier": (
        "Use the native command or `rtk proxy <command>` for an exact blob from `git show REV:path`, a `diff` whose "
        "exit status matters, `git branch`, a complete `git log`, `jq` output, and `find` on a directory that may "
        "not exist (the RTK exceptions below)."
    ),
}
# Claude-only tool, frontmatter, hook and file names. Case-sensitive, as identifiers: a lowercase "bash" or
# "workflow" in ordinary prose is not a Claude tool name.
CLAUDE_ONLY_NAMES = (
    "ToolSearch", "WebFetch", "WebSearch", "Workflow", "SendMessage", "TaskCreate", "TeamCreate", "subagent_type",
    "agentType", "mcp__plugin_context-mode_context-mode__", "omitClaudeMd", "maxTurns", "BASH_MAX_TIMEOUT_MS",
    "SubagentStart", "CLAUDE.md", "Automatic RTK", "RTK hook", "Bash",
)

# ---------------------------------------------------------------------------------------------------------------
# The pinned digests

_HEX = frozenset("0123456789abcdef")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256sums(path: Path) -> dict[str, str]:
    """{file name: sha256} from a sha256sum-format file: one `<64 lowercase hex>  <name>` line per file (two spaces,
    as `sha256sum` writes text mode; the ` *` binary marker is refused), a name with no directory part, leading star
    or surrounding space, no duplicate name, no blank or other line. Raises OSError when the file cannot be read and
    ValueError, whose message names the rule and never holds file text, when a line is malformed."""
    rows: dict[str, str] = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        digest, separator, name = line[:64], line[64:66], line[66:]
        if (len(line) <= 66 or separator != "  " or not set(digest) <= _HEX or name != name.strip()
                or "/" in name or "\\" in name or name.startswith("*")):
            raise ValueError("sha256sums: malformed line")
        if name in rows:
            raise ValueError("sha256sums: duplicate name")
        rows[name] = digest
    return rows


def _read(path: Path) -> bytes | None:
    try:
        return Path(path).read_bytes()
    except OSError:
        return None


def developer_instructions(data: dict) -> str:
    """The developer_instructions string of a parsed role file; empty when it is absent or not a string."""
    value = data.get("developer_instructions") if isinstance(data, dict) else None
    return value if isinstance(value, str) else ""


def role_pins(data: dict) -> tuple:
    """(model, model_reasoning_effort) of a parsed role file; None for an absent key. The pins a spawned child must
    run at (U13 design 2.1)."""
    data = data if isinstance(data, dict) else {}
    return data.get("model"), data.get("model_reasoning_effort")


def byte_problems(root: Path) -> list[str]:
    """Sorted rule ids for the repository copies of the carriers under `root`: sha256sums_names (its
    adoption/agents/codex/SHA256SUMS is unreadable or malformed, or does not name exactly the two carriers),
    sha256_row (a carrier differs from its row) and mirror_copy (an examples/codex-native/agents copy is not
    byte-identical to its adoption source)."""
    root = Path(root)
    source, mirror = root / "adoption" / "agents" / "codex", root / "examples" / "codex-native" / "agents"
    problems = set()
    try:
        rows = sha256sums(source / SHA256SUMS_NAME)
    except (OSError, ValueError):
        rows = {}
    if sorted(rows) != sorted(ROLE_FILES):
        problems.add("sha256sums_names")
    for name in ROLE_FILES:
        original, copy = _read(source / name), _read(mirror / name)
        if original is None or sha256_bytes(original) != rows.get(name):
            problems.add("sha256_row")
        if original is None or original != copy:
            problems.add("mirror_copy")
    return sorted(problems)


def source_problems(directory: Path | None = None) -> dict[str, list[str]]:
    """The rule ids each carrier in `directory` (default: adoption/agents/codex) breaks; an empty list means it is
    exactly its pinned row and structurally sound. source_missing (unreadable), sha256sums_names (the SHA256SUMS
    beside it is unreadable or malformed, or does not name exactly the two carriers), sha256_row (its bytes differ
    from their row), toml_parse, structural_inputs (the denylist or the AGENTS template could not be read) and the
    structural_problems ids. Rule ids only: no text, no path."""
    base = ROLES_SOURCE if directory is None else Path(directory)
    try:
        rows = sha256sums(base / SHA256SUMS_NAME)
    except (OSError, ValueError):
        rows = None
    names_ok = rows is not None and sorted(rows) == sorted(ROLE_FILES)
    found = {}
    for name, role in zip(ROLE_FILES, ROLES):
        data = _read(base / name)
        if data is None:
            found[name] = ["source_missing"]
            continue
        problems = set()
        if not names_ok:
            problems.add("sha256sums_names")
        if rows is None or sha256_bytes(data) != rows.get(name):
            problems.add("sha256_row")
        try:
            parsed = tomllib.loads(data.decode("utf-8"))
        except ValueError:  # TOMLDecodeError and UnicodeDecodeError both
            problems.add("toml_parse")
        else:
            try:
                problems.update(structural_problems(role, role, parsed))
            except (OSError, ValueError, KeyError):
                problems.add("structural_inputs")
        found[name] = sorted(problems)
    return found


# ---------------------------------------------------------------------------------------------------------------
# Structural rules. Each rule is keyed by the expected role, never by the (possibly mutated) stem or name.

def _is_ascii_alnum(char: str) -> bool:
    return char.isascii() and char.isalnum()


def name_hits(text: str, names, fold: bool) -> list[str]:
    """Names of `names` that occur in `text` with no ASCII letter or digit on either side.

    This is the delimiting of tool_name_pattern() in tests/test_token_e2e_preregistration.py,
    (?<![A-Za-z0-9])name(?![A-Za-z0-9]), and fold=True is its re.I. One str.find sweep per name; no regular
    expression, so nothing can backtrack.
    """
    haystack = text.lower() if fold else text
    found = []
    for name in names:
        needle = name.lower() if fold else name
        start = 0
        while True:
            index = haystack.find(needle, start)
            if index < 0:
                break
            end = index + len(needle)
            before = haystack[index - 1] if index > 0 else ""
            after = haystack[end] if end < len(haystack) else ""
            if not (before and _is_ascii_alnum(before)) and not (after and _is_ascii_alnum(after)):
                found.append(name)
                break
            start = index + 1
    return found


def _text_of(data: dict, key: str) -> str:
    value = data.get(key)
    return value if isinstance(value, str) else ""


@functools.lru_cache(maxsize=None)
def frozen_denylist() -> tuple:
    """The sealed /no_tool_names_denylist of the E2E preregistration."""
    return tuple(json.loads(PREREGISTRATION.read_text(encoding="utf-8"))["no_tool_names_denylist"])


@functools.lru_cache(maxsize=None)
def f4_block() -> str:
    """The F4 block: from the rtk-upstream marker through the shell-builtin line of the Codex AGENTS template."""
    template = AGENTS_TEMPLATE.read_text(encoding="utf-8")
    return UPSTREAM_MARKER + template.split(UPSTREAM_MARKER, 1)[1].split(END_MARKER, 1)[0]


def _rule_keys(role, stem, data):
    return set(data) != ROLE_KEYS


def _rule_name_stem(role, stem, data):
    return data.get("name") != stem


def _rule_builtin_name(role, stem, data):
    return data.get("name") in BUILTIN_ROLES


def _rule_description_shape(role, stem, data):
    description = data.get("description")
    return (not isinstance(description, str) or not description.strip() or "\n" in description
            or "\r" in description or len(description) > 200)


def _rule_description_denylist(role, stem, data):
    return bool(name_hits(_text_of(data, "description"), frozen_denylist(), fold=True))


def _rule_model_pin(role, stem, data):
    return data.get("model") != ROLE_MODEL


def _rule_effort_pin(role, stem, data):
    return data.get("model_reasoning_effort") != ROLE_EFFORT


def _rule_f4_block(role, stem, data):
    instructions = _text_of(data, "developer_instructions")
    if (f4_block() not in instructions or instructions.count(UPSTREAM_MARKER) != 1
            or instructions.count(EXCEPTIONS_MARKER) != 1):
        return True
    # The blank separator before the exception marker is outside the upstream file.
    upstream = instructions.split(UPSTREAM_MARKER, 1)[1].split("\n" + EXCEPTIONS_MARKER, 1)[0]
    if sha256_bytes(upstream.encode("utf-8")) != RTK_SHA256:
        return True
    return any(line.startswith("@") for line in instructions.splitlines())


def _rule_claude_only_name(role, stem, data):
    text = _text_of(data, "description") + "\n" + _text_of(data, "developer_instructions")
    return bool(name_hits(text, CLAUDE_ONLY_NAMES, fold=False))


def _rule_one_agent(role, stem, data):
    return ONE_AGENT_SENTENCE not in _text_of(data, "developer_instructions")


def _rule_cwd(role, stem, data):
    return WORKING_DIRECTORY_BULLET not in _text_of(data, "developer_instructions")


def _rule_exact_shapes(role, stem, data):
    return EXACT_SHAPES[role] not in _text_of(data, "developer_instructions")


def _rule_no_web(role, stem, data):
    return NO_WEB_SENTENCE not in _text_of(data, "developer_instructions")


# (rule id, roles it applies to, source, check). Sources are openai/codex at rust-v0.157.1 (36650394) unless a
# repository path is given; a check returns True when the rule is violated.
RULES = (
    ("keys", ROLES,
     "codex-rs/core/src/agent/role.rs:36-48 (AgentRoleOverrides, the applied set) and "
     "codex-rs/agent-roles/src/agent_role_config.rs:20-28 (RawAgentRoleFileToml, deny_unknown_fields): a role "
     "file carries exactly the five keys, since every other key is unapplied or would change tool bindings",
     _rule_keys),
    ("name_stem", ROLES,
     "agent_role_config.rs:73-88 (the name field, not the file name, names the role); the stem equals the name so "
     "the discovered file and its role cannot disagree",
     _rule_name_stem),
    ("builtin_name", ROLES,
     "role.rs:33 and :337-380 (built_in::configs: default, explorer, worker); a user role of that name shadows a "
     "built-in",
     _rule_builtin_name),
    ("description_shape", ROLES,
     "agent_role_config.rs:63-66,120-130 (a blank description is rejected) and role.rs:294-334 (format_role "
     "renders it between braces in the spawn_agent description): non-blank, one line, at most 200 characters",
     _rule_description_shape),
    ("description_denylist", ROLES,
     "evidence/artifacts/token-adoption-e2e-20260926/preregistration.json /no_tool_names_denylist under "
     "tests/test_token_e2e_preregistration.py tool_name_pattern with re.I; role.rs:294-334 shows the description to "
     "every parent in every arm",
     _rule_description_denylist),
    ("model_pin", ROLES,
     "preregistration.json /tasks (every family codex task is gpt-6-astra at max) and "
     "adoption/templates/codex.stack-worker.config.toml:12",
     _rule_model_pin),
    ("effort_pin", ROLES,
     "preregistration.json /tasks; codex-rs/protocol/src/openai_models.rs:59-72 (ReasoningEffort::Max) and "
     "adoption/templates/codex.stack-worker.config.toml:17",
     _rule_effort_pin),
    ("f4_block", ROLES,
     "docs/decisions/2026-09-26-token-practice-f1-f9.md#f4-codex-rtk-guidance-2026-09-26; rtk-ai/rtk v0.50.0 "
     "hooks/rtk-awareness-full.md (RTK_SHA256); adoption/templates/codex.AGENTS.template.md",
     _rule_f4_block),
    ("claude_only_name", ROLES,
     "adoption/agents/claude/stack-*.md and adoption/hooks/claude/token-lanes-block.*.md name tools, frontmatter "
     "keys and hooks that Codex does not have; matched case-sensitively with ASCII-alphanumeric delimiters",
     _rule_claude_only_name),
    ("one_agent_rule", ROLES,
     "role.rs:80-126 (a role can only disable a few features, never the collaboration tools), so a child is "
     "told not to spawn, message or follow up with other agents",
     _rule_one_agent),
    ("cwd_rule", ROLES,
     "docs/token-session-handbook.md, Context Mode executor, 'Codex workers' bullet (context-mode binds the launch "
     "directory) and evidence/artifacts/token-adoption-e2e-20260926/README.md:370 (M13: no explicit cwd)",
     _rule_cwd),
    ("exact_shapes", ROLES,
     "adoption/templates/codex.AGENTS.template.md:41-46 (six exceptions, jq included) and "
     "evidence/artifacts/token-adoption-e2e-20260926/README.md:363 (M6c: 0 exception commands wrapped in rtk)",
     _rule_exact_shapes),
    ("no_web_rule", ("stack-verifier",),
     "role.rs:36-48 has no web_search override, so the verifier's no-web restriction is a prompt rule",
     _rule_no_web),
)


def structural_problems(expected_role: str, stem: str, data: dict) -> list[str]:
    """Sorted rule ids violated by parsed role TOML `data`, for the role a caller expects and the file stem it has."""
    return sorted(rule_id for rule_id, roles, _source, check in RULES
                  if expected_role in roles and check(expected_role, stem, data))


# ---------------------------------------------------------------------------------------------------------------
# What Codex would load as a role, besides the two carriers

def path_kind(path: Path) -> str:
    """absent | dir | file | link | other, by lstat: a link is reported, never followed."""
    try:
        mode = os.lstat(path).st_mode
    except FileNotFoundError:
        return "absent"
    except OSError:
        return "other"
    if stat.S_ISLNK(mode):
        return "link"
    if stat.S_ISDIR(mode):
        return "dir"
    return "file" if stat.S_ISREG(mode) else "other"


def agents_toml_count(directory: Path) -> int | None:
    """Files named *.toml (an extension: ".toml" alone is not one; exact case) under `directory`, recursively, the
    way codex-rs/agent-roles/src/discovery.rs collects role files.

    Codex follows links there: LocalFileSystem::read_directory takes a link's target's type (codex-rs/exec-server/src/
    local_file_system.rs:710-735 at rust-v0.157.1; observed with codex-cli 0.157.1 through `codex doctor --json`), so it
    enters a linked folder and collects a link to a regular file by the link's own name. This count never enters a link,
    so a link to a folder anywhere below `directory`, whatever its name, makes it unknown (None): what lies behind the
    link is not attested here, and a count that skipped it would report fewer role files than Codex loads. A link to a
    file named *.toml is counted and never read; so is a dangling one, which Codex skips (an overcount, the safe side).
    0 when `directory` is absent; None when it is not a real directory, a folder link is below it, or any part of it
    cannot be read."""
    kind = path_kind(directory)
    if kind == "absent":
        return 0
    if kind != "dir":
        return None
    unreadable, total = [], 0
    for current, folders, files in os.walk(directory, followlinks=False, onerror=unreadable.append):
        # os.walk lists a link to a folder with the folders and does not enter it: unknown, never skipped.
        if any(path_kind(Path(current) / name) == "link" for name in folders):
            return None
        total += sum(1 for name in files if name.endswith(".toml") and len(name) > len(".toml"))
    return None if unreadable else total


def role_table_count(config) -> int:
    """[agents.<name>] tables in a parsed config: the tables under [agents], not its scalar keys."""
    agents = config.get("agents") if isinstance(config, dict) else None
    return sum(1 for value in agents.values() if isinstance(value, dict)) if isinstance(agents, dict) else 0


def toml_role_tables(path: Path) -> int | None:
    """Role tables of one TOML file: 0 when it is absent, None when it cannot be read as TOML."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        return 0
    except (OSError, ValueError):
        return None
    try:
        return role_table_count(tomllib.loads(text))
    except ValueError:
        return None


def live_role_tables(codex_home: Path) -> int | None:
    """Role tables in a Codex home's config.toml and worker profile; None when either cannot be read."""
    counts = [toml_role_tables(Path(codex_home) / "config.toml"),
              toml_role_tables(Path(codex_home) / WORKER_PROFILE_FILE)]
    return None if None in counts else sum(counts)


def system_role_count(system_dir: Path | None = None) -> int | None:
    """What the system config layer adds: *.toml under its agents folder plus its role tables (0 for an absent
    folder; None when part of it cannot be read). It loads in every launch, N included."""
    base = SYSTEM_CODEX_DIR if system_dir is None else Path(system_dir)
    counts = [agents_toml_count(base / "agents"), toml_role_tables(base / "config.toml")]
    return None if None in counts else sum(counts)


# ---------------------------------------------------------------------------------------------------------------
# `codex doctor --json`

# The warning Codex records for a role file it cannot use (agent-roles/src/loader.rs push_agent_role_warning), and
# the value its report shows when the text held a credential word (cli/src/doctor/output.rs redact_detail).
ROLE_WARNING_PREFIX = "Ignoring malformed agent role definition"
REDACTED = "<redacted>"


def doctor_config_load(stdout: str | None) -> tuple[str, dict] | None:
    """(status, details) of checks["config.load"] in a `codex doctor --json` report; None when there is no stdout
    (a timeout), it is not a JSON report, or the check is missing. The exit code is not consulted: doctor prints the
    report and then exits 1 whenever any check fails, and in a scratch home without a sign-in auth.credentials
    always does (codex-rs/cli/src/doctor.rs). Details are strings, or lists of strings for a repeated label."""
    if not isinstance(stdout, str):
        return None
    try:
        report = json.loads(stdout)
    except (ValueError, RecursionError):
        return None
    checks = report.get("checks") if isinstance(report, dict) else None
    entry = checks.get("config.load") if isinstance(checks, dict) else None
    if not isinstance(entry, dict):
        return None
    details = entry.get("details")
    return str(entry.get("status")), details if isinstance(details, dict) else {}


def startup_warnings(details: dict) -> list[str]:
    """The `startup warning` values of a config.load check (a string, or a list when the warning repeats)."""
    value = details.get("startup warning")
    if isinstance(value, str):
        return [value]
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def startup_warning_count(details: dict) -> int:
    """The `startup warnings` count, a string of digits that survives redaction; a clean check has no such key
    (doctor.rs config_check adds it only with the first warning), so the count is then the values, i.e. 0."""
    raw = details.get("startup warnings")
    if isinstance(raw, str) and raw.isascii() and raw.isdigit():
        return int(raw)
    return len(startup_warnings(details))


def doctor_role_state(stdout_before: str | None, stdout_after: str | None) -> dict:
    """What `codex doctor --json` says about the role files, from two reports of one scratch home: before they were
    copied in and after. Counts only, never text or a path (a role warning embeds the file's absolute path).
    state: unknown when either report is unusable (no stdout, not JSON, no config.load) or config.load failed in
    both; problem when config.load fails only with the role files, or the startup warnings rise, or a role warning
    is new; ok otherwise. role_warnings and redacted count the rise, so a warning the scratch home has without the
    role files (a malformed system-layer role, which the system-role count line reports) is not blamed on them.
    load_failed is this tool's addition to the design's five keys: loader.rs propagates a directory-read error, so
    doctor reports config.load as failed, not warned."""
    result = {"state": "unknown", "startup_warnings_before": None, "startup_warnings_after": None,
              "role_warnings": 0, "redacted": 0, "load_failed": False}
    before, after = doctor_config_load(stdout_before), doctor_config_load(stdout_after)
    failed_before = before is not None and before[0] == "fail"
    failed_after = after is not None and after[0] == "fail"
    if before is not None and not failed_before:
        result["startup_warnings_before"] = startup_warning_count(before[1])
    if after is not None and not failed_after:
        result["startup_warnings_after"] = startup_warning_count(after[1])
    if before is None or after is None or failed_before:
        return result
    if failed_after:  # an unreadable agents folder fails the whole load (loader.rs propagates it with `?`)
        return {**result, "state": "problem", "load_failed": True}
    was, now = startup_warnings(before[1]), startup_warnings(after[1])
    result["role_warnings"] = max(0, sum(text.startswith(ROLE_WARNING_PREFIX) for text in now)
                                  - sum(text.startswith(ROLE_WARNING_PREFIX) for text in was))
    result["redacted"] = max(0, now.count(REDACTED) - was.count(REDACTED))
    rose = result["startup_warnings_after"] > result["startup_warnings_before"]
    result["state"] = "problem" if rose or result["role_warnings"] else "ok"
    return result


def doctor_problem(state: dict) -> str | None:
    """The rehearsal's PROBLEM text for a doctor_role_state; None unless it is a problem. Counts only."""
    if state["state"] != "problem":
        return None
    if state["load_failed"]:
        return "codex doctor could not load the config with the role files (config.load failed)"
    before, after, roles = state["startup_warnings_before"], state["startup_warnings_after"], state["role_warnings"]
    if after > before:
        return (f"codex doctor startup warnings rose from {before} to {after} with the role files "
                f"({roles} agent role warnings)")
    return f"codex doctor reports {roles} agent role warnings with the role files ({before} before, {after} after)"
