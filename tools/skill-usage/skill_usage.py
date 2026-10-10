#!/usr/bin/env python3
"""Per-host skill invoke-rate report: joins adoption/skills/manifest.json with real usage.

Claude side reads native `/skill-doctor` (its table is the only per-skill invoke-rate signal
Claude Code exposes; see the README for why OTel, a custom hook, agentsview and ccusage cannot
answer this):

    claude -p /skill-doctor --output-format json --permission-mode dontAsk --permission-prompts none \\
        --tools '' --strict-mcp-config --max-turns 1 --max-budget-usd 0.05 > /path/outside/checkout/skill-doctor.json
    python3 tools/skill-usage/skill_usage.py --claude-skill-doctor /path/outside/checkout/skill-doctor.json \\
        --codex-root ~/.codex/sessions --out /path/outside/checkout/report.json

On a host with a managed MCP config (managed-mcp.json), drop --strict-mcp-config from that command: the client
refuses the flag there ("You cannot use --strict-mcp-config when an enterprise MCP config is present", 2.1.296), and
--run-skill-doctor drops it itself.

Or run it directly (refuses the result unless the native call was the synthetic, zero-cost
local command it is documented to be):

    python3 tools/skill-usage/skill_usage.py --run-skill-doctor --codex-root ~/.codex/sessions

Codex has no skill-invocation event, so --codex-root scans rollout-*.jsonl files under exactly
the given roots (repeatable; there is no default search) for two signals per manifest skill:
a persisted ResponseItem tool/function call whose command or arguments read a path ending in
"/<name>/SKILL.md", and a persisted user message containing the token "$<name>". Omit
--codex-root entirely to report Codex as "not-measured" rather than a measured zero.

Nothing is written unless --out is given, and --out inside this checkout is refused. The report
contains skill names and counts only: no transcript text, no file paths, no session or thread
ids (see the README's privacy boundary).

--lanes switches to the Codex lane report, the counterpart of examples/claude-native/workflows/
child-usage.mjs --lanes-sweep: per rollout session inside [--since, --until), MCP calls per server,
shell commands and their rtk prefix, fetch routing, SKILL.md reads, the injected-block marker and
the first-prompt size, with sessions that did not load the user config (--ignore-user-config lanes)
kept apart as negative controls:

    python3 tools/skill-usage/skill_usage.py --lanes --codex-root ~/.codex/sessions \\
        --since 2026-09-25T17:18:00Z --until 2026-09-26T15:05:00Z --json

With --lanes, --call-ledger PATH also writes the private per-call ledger (codex-call-ledger/1 JSONL, thread and
call ids with each call's state from the kernel's callLedger) to a new 0600 file outside every git work tree;
the report itself stays ID-free.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_MANIFEST = ROOT / "adoption" / "skills" / "manifest.json"
DEFAULT_WINDOWS = (7, 30)
ROLLOUT_GLOB = "rollout-*.jsonl"

# codex-rs/history/src/rollout_payload.rs (RolloutItemWire, #[serde(tag = "type")]) at
# rust-v0.155.1: these are the persisted ResponseItem variants that represent a model-issued
# tool/function call (its request side, never its output body, which can hold file contents).
CALL_PAYLOAD_TYPES = {"function_call", "local_shell_call", "custom_tool_call", "tool_search_call"}

# Native /skill-doctor table row, e.g. (Claude Code 2.1.282):
#   "  gh-fix-ci                       userSettings       ~110          -     0×  never"
# Columns: skill, source, context (approx tokens or "-" = not in the current listing),
# 7d tokens ("-" or approx), uses ("N×"), last used ("never" or a relative/absolute time, which
# may itself contain spaces). `source` may also contain a space ("claude.ai sync"). Claude Code
# 2.1.283 prints a listing below its display floor as "< 20" (the name-only listings); that is
# read as its bound, 20, and never folded into `source`.
_APPROX = r"(?:<\s*|~)?\d[\d,.]*[kKmMbB]?"
SKILL_DOCTOR_ROW = re.compile(
    rf"^\s*(?P<skill>\S+)\s+(?P<source>.+?)\s+(?P<context>-|{_APPROX})\s+"
    rf"(?P<tokens_7d>-|{_APPROX})\s+(?P<uses>\d+)×\s+(?P<last_used>.+?)\s*$"
)
_COUNT_RE = re.compile(r"(?:<\s*|~)?(\d[\d,.]*)([kKmMbB]?)")
_MULTIPLIERS = {"": 1, "k": 1_000, "m": 1_000_000, "b": 1_000_000_000}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def parse_iso(text: str) -> datetime:
    """Parse an ISO-8601 timestamp (accepting a trailing 'Z') as a tz-aware UTC datetime."""
    value = text.strip()
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def parse_approx_count(raw: str) -> int | None:
    """"~110" -> 110, "1.2k" -> 1200, "< 20" -> 20 (an upper bound), "-" (not in the current
    listing / no data) -> None."""
    raw = raw.strip()
    if raw == "-":
        return None
    match = _COUNT_RE.fullmatch(raw)
    if not match:
        return None
    number = float(match.group(1).replace(",", ""))
    return int(round(number * _MULTIPLIERS[match.group(2).lower()]))


# --------------------------------------------------------------------------- Claude /skill-doctor


def parse_skill_doctor_text(text: str) -> dict[str, dict]:
    """Every table row in a /skill-doctor listing, keyed by skill name. Non-row lines (header,
    footnotes, blanks) never match SKILL_DOCTOR_ROW (no row lacks a literal "N×" uses column) and
    are silently skipped, so this is safe to run over the whole command output or file."""
    rows: dict[str, dict] = {}
    for line in text.splitlines():
        match = SKILL_DOCTOR_ROW.match(line)
        if not match:
            continue
        groups = match.groupdict()
        rows[groups["skill"]] = {
            "source": groups["source"].strip(),
            "context_tokens": parse_approx_count(groups["context"]),
            "tokens_7d": parse_approx_count(groups["tokens_7d"]),
            "uses": int(groups["uses"]),
            "last_used": groups["last_used"].strip(),
        }
    return rows


def find_result_event(events: list) -> dict | None:
    """The stream-json 'result' event, scanning from the end in case of a longer transcript."""
    for event in reversed(events):
        if isinstance(event, dict) and event.get("type") == "result":
            return event
    return None


def evaluate_cost(total_cost_usd, num_turns) -> bool:
    """A native /skill-doctor run is a synthetic, zero-cost local command; anything else means
    the captured 'result' text did not come from that documented code path, so it is not trusted."""
    return total_cost_usd == 0 and num_turns == 0


def parse_claude_output(raw: str) -> dict:
    """Parse a captured `--output-format json` result object or stream-json event array, or a
    plain-text /skill-doctor table.

    `claude -p --output-format json` prints one result object (`claude --help` 2.1.283: "json"
    (single result)) or, when verbose is on, the whole message array (a read of the 2.1.283
    binary's headless print path, not a live reproduction; retained captures of both shapes are
    cited at tools/sota-convergence/transcript_audit.py result_message). An object is read as a
    one-element array, so find_result_event makes the same selection in both shapes, the last
    element of type 'result' (a message of that type is what
    anthropics/claude-agent-sdk-python@36f95486ee9f src/claude_agent_sdk/_internal/message_parser.py:308
    parses as the ResultMessage), and an object that is no result event is refused, as is a
    result whose subtype is not "success" or whose is_error is not false.

    Returns {"format", "rows", "total_cost_usd", "num_turns"} and, when the capture is refused
    or malformed, an "error" key with rows left empty. total_cost_usd/num_turns are None for a
    plain-text capture: there is no cost signal to check, because there is no result event.
    """
    try:
        events = json.loads(raw)
    except json.JSONDecodeError:
        return {"format": "text", "rows": parse_skill_doctor_text(raw),
                "total_cost_usd": None, "num_turns": None}
    if isinstance(events, dict):
        events = [events]
    if not isinstance(events, list):
        return {"format": "json", "rows": {}, "total_cost_usd": None, "num_turns": None,
                "error": "expected a result object or a JSON array of stream-json events"}
    result_event = find_result_event(events)
    if result_event is None:
        return {"format": "json", "rows": {}, "total_cost_usd": None, "num_turns": None,
                "error": "no result event in the JSON output"}
    total_cost_usd = result_event.get("total_cost_usd")
    num_turns = result_event.get("num_turns")
    # subtype and is_error are required fields of the SDK's ResultMessage (types.py:1343,1346 at the
    # pin above), and is_error can be true while subtype is "success" (an API error, types.py:1358-1360),
    # so only a result that is both "success" and not is_error carries a /skill-doctor table.
    if result_event.get("subtype") != "success" or result_event.get("is_error") is not False:
        return {"format": "json", "rows": {}, "total_cost_usd": total_cost_usd, "num_turns": num_turns,
                "error": f"refusing an error result (subtype={result_event.get('subtype')!r}, "
                         f"is_error={result_event.get('is_error')!r})"}
    if not evaluate_cost(total_cost_usd, num_turns):
        return {"format": "json", "rows": {}, "total_cost_usd": total_cost_usd, "num_turns": num_turns,
                "error": f"refusing a nonzero-cost result (total_cost_usd={total_cost_usd!r}, "
                         f"num_turns={num_turns!r}); a native /skill-doctor run is zero-cost"}
    text = result_event.get("result")
    if not isinstance(text, str):
        return {"format": "json", "rows": {}, "total_cost_usd": total_cost_usd, "num_turns": num_turns,
                "error": "result event has no string 'result' field"}
    return {"format": "json", "rows": parse_skill_doctor_text(text),
            "total_cost_usd": total_cost_usd, "num_turns": num_turns}


# /skill-doctor is a local command (0 turns, $0), so these fences change nothing while the client recognises it:
# measured 2026-10-10 on Claude Code 2.1.295 and 2.1.296, each client's table sha256-identical at $0 and 0 turns with
# the fences of b2189ba0 and with these. If a client stopped recognising it, they would keep the prompt from reaching a
# model with tools or MCP servers under the host's inherited bypassPermissions and cap what the run spends (untested: no
# such client exists). Sources: `claude --help` (2.1.295, 2.1.296) lists --permission-mode, --permission-prompts,
# --tools, --strict-mcp-config and --max-budget-usd; --max-turns is accepted but hidden from --help and documented in
# the CLI reference, https://code.claude.com/docs/en/cli-reference. Denying anything not pre-approved without prompting
# is the repository's rule PERM-03 (docs/harness-rules-convergence-20260922.md).
SKILL_DOCTOR_ARGV = ["claude", "-p", "/skill-doctor", "--output-format", "json", "--permission-mode", "dontAsk",
                     "--permission-prompts", "none", "--tools", "", "--strict-mcp-config", "--max-turns", "1",
                     "--max-budget-usd", "0.05"]

# A deployed managed-mcp.json holds exclusive control of the MCP servers, and Claude Code refuses --strict-mcp-config
# while it is there: the 2.1.296 binary carries "You cannot use --strict-mcp-config when an enterprise MCP config is
# present" (read 2026-10-10), and https://code.claude.com/docs/en/managed-mcp (read 2026-10-10) says "If a user passes it
# while such a file is deployed, Claude Code exits at startup on a workstation and in a cloud session alike". The file
# already keeps every other server out, so on such a host the argv drops only that flag and keeps the other fences.
# What the client checks, read from the 2.1.296 binary (sha256
# 24972e3bc859fab2b46ed4c1e51f7d6130f06d3bd550811a114640de3370d0de, 2026-10-10): its refusal applies only when the file is
# present and loads without a read, JSON or schema error (the reader at byte 217796118, the refusal at byte 217799919), so a
# present file it cannot read or parse gets no refusal, and its own `plugin eval init` launcher drops the flag on presence
# alone (byte 247738504). This check drops the flag for any file it can read, parsed or not, and keeps it when the file is
# absent, unreadable or not a regular file, the cases in which the client does not refuse it.
# System paths: the same page's configuration summary ("/Library/Application Support/ClaudeCode/", "/etc/claude-code/",
# "C:\Program Files\ClaudeCode\"); all three are checked on every system, so no platform branch is needed (Linux covers
# WSL), but a path counts only when it is absolute: on POSIX the Windows path is a relative filename, and a file of that
# name in the working directory is not a managed config (found by the command center's micro of #925 at 46cc5dd1 and
# reproduced by the co-op's GPT reads of #925 at 46cc5dd1 and 715229c7).
MANAGED_MCP_CONFIG_PATHS = (
    "/Library/Application Support/ClaudeCode/managed-mcp.json",
    "/etc/claude-code/managed-mcp.json",
    "C:\\Program Files\\ClaudeCode\\managed-mcp.json",
)


def _readable_system_file(path) -> bool:
    """Whether `path` is an absolute, normalised path to a readable file (a relative name is a file in the working
    directory, never a system path)."""
    name = os.fspath(path)
    return os.path.isabs(name) and os.path.abspath(name) == name and os.path.isfile(name) and os.access(name, os.R_OK)


def skill_doctor_argv(managed_paths=None) -> list:
    """SKILL_DOCTOR_ARGV, without --strict-mcp-config when a readable managed MCP config is deployed at an absolute path."""
    paths = MANAGED_MCP_CONFIG_PATHS if managed_paths is None else managed_paths
    if any(_readable_system_file(path) for path in paths):
        return [word for word in SKILL_DOCTOR_ARGV if word != "--strict-mcp-config"]
    return list(SKILL_DOCTOR_ARGV)


def run_skill_doctor(*, timeout: int = 30, runner=subprocess.run, managed_paths=None) -> dict:
    """Run skill_doctor_argv() (SKILL_DOCTOR_ARGV; without --strict-mcp-config on a host with a managed MCP config),
    stdin from /dev/null."""
    try:
        completed = runner(skill_doctor_argv(managed_paths),
                            stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"format": None, "rows": {}, "total_cost_usd": None, "num_turns": None,
                "error": f"failed to run claude -p /skill-doctor: {type(error).__name__}"}
    if completed.returncode != 0:
        return {"format": None, "rows": {}, "total_cost_usd": None, "num_turns": None,
                "error": f"claude -p /skill-doctor exited {completed.returncode}"}
    return parse_claude_output(completed.stdout)


# --------------------------------------------------------------------------- Codex rollout scan


def _walk_strings(value):
    """Yield every string in a JSON-like structure. A string that itself parses as a JSON object
    or array is also recursed into: FunctionCall/CustomToolCall carry their arguments/input as a
    JSON-encoded string (codex-rs/protocol/src/models.rs), not a nested object."""
    if isinstance(value, str):
        yield value
        try:
            parsed = json.loads(value)
        except (json.JSONDecodeError, ValueError):
            return
        if isinstance(parsed, (dict, list)):
            yield from _walk_strings(parsed)
    elif isinstance(value, dict):
        for item in value.values():
            yield from _walk_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_strings(item)


def skillmd_hits(payload: dict, names) -> set[str]:
    """Manifest skill names whose canonical or symlinked path (~/.agents/skills/<name>/SKILL.md
    or ~/.claude/skills/<name>/SKILL.md) is read anywhere in this one tool/function call."""
    hits: set[str] = set()
    for text in _walk_strings(payload):
        for name in names:
            if f"/{name}/SKILL.md" in text:
                hits.add(name)
    return hits


def user_message_text(payload: dict) -> str:
    content = payload.get("content")
    if not isinstance(content, list):
        return ""
    parts = [item.get("text", "") for item in content
             if isinstance(item, dict) and item.get("type") == "input_text"]
    return "\n".join(part for part in parts if isinstance(part, str))


def mention_hits(text: str, mention_patterns: dict) -> set[str]:
    return {name for name, pattern in mention_patterns.items() if pattern.search(text)}


def iter_rollout_files(roots) -> list[Path]:
    """rollout-*.jsonl under exactly the given roots, recursively. No default search: an empty
    or missing root list yields no files, never a fallback path."""
    seen: set[Path] = set()
    files: list[Path] = []
    for root in roots or []:
        root = Path(root)
        if not root.is_dir():
            continue
        for path in sorted(root.rglob(ROLLOUT_GLOB)):
            resolved = path.resolve()
            if resolved not in seen and path.is_file():
                seen.add(resolved)
                files.append(path)
    return files


def _empty_counts(names, windows) -> dict:
    return {name: {window: {"skill_md_reads": 0, "name_mentions": 0} for window in windows} for name in names}


def _score_line(record: dict, names, mention_patterns: dict, now: datetime, windows,
                 counts: dict) -> None:
    """Mutate `counts` in place for one decoded rollout line, or raise to have the caller count
    it as a parse error. Only response_item lines are scored: RolloutItem::ResponseItem is
    persisted unconditionally in both Legacy and Paginated history modes
    (codex-rs/rollout/src/policy.rs), unlike EventMsg, which depends on that mode."""
    timestamp = record.get("timestamp")
    if not isinstance(timestamp, str):
        return
    when = parse_iso(timestamp)
    age_days = (now - when).total_seconds() / 86400.0
    applicable = [window for window in windows if 0 <= age_days <= window]
    if not applicable:
        return
    if record.get("type") != "response_item":
        return
    payload = record.get("payload")
    if not isinstance(payload, dict):
        return
    payload_type = payload.get("type")
    if payload_type in CALL_PAYLOAD_TYPES:
        for name in skillmd_hits(payload, names):
            for window in applicable:
                counts[name][window]["skill_md_reads"] += 1
    elif payload_type == "message" and payload.get("role") == "user":
        text = user_message_text(payload)
        if text:
            for name in mention_hits(text, mention_patterns):
                for window in applicable:
                    counts[name][window]["name_mentions"] += 1


def scan_rollout_file(path: Path, names, mention_patterns: dict, now: datetime, windows,
                      codex_off=()) -> tuple[dict, dict, int, bool]:
    """(own counts, copied counts, parse errors, user config ignored). Records a spawned sub-agent's
    rollout copied from its parent (ordinal below session_meta.subagent_history_start_ordinal) are
    scored into the copied counts, apart from the session's own records; both are part of the
    trial's measurement. The last value is True when the session's skill catalog, as of `now`,
    lists a skill in codex_off (see USER_CONFIG_METHOD)."""
    counts = _empty_counts(names, windows)
    copied = _empty_counts(names, windows)
    parse_errors = 0
    ignored = False
    history_start, first_meta = None, True
    try:
        handle = path.open(encoding="utf-8", errors="replace")
    except OSError:
        return counts, copied, 1, False
    with handle:
        for raw_line in handle:
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                record = json.loads(raw_line)
                if not isinstance(record, dict):
                    raise ValueError("rollout line is not a JSON object")
                if record.get("type") == "session_meta" and first_meta:
                    first_meta = False
                    meta = record.get("payload") if isinstance(record.get("payload"), dict) else {}
                    start = meta.get("subagent_history_start_ordinal")
                    history_start = start if isinstance(start, int) and not isinstance(start, bool) else None
                if codex_off and not ignored and _at_or_before(record, now):
                    ignored = any(f"/{name}/SKILL.md" in text for text in catalog_texts(record)
                                  for name in codex_off)
                inherited = (history_start is not None and isinstance(record.get("ordinal"), int)
                             and record["ordinal"] < history_start)
                _score_line(record, names, mention_patterns, now, windows, copied if inherited else counts)
            except Exception:
                parse_errors += 1
    return counts, copied, parse_errors, ignored


def _at_or_before(record: dict, now: datetime) -> bool:
    timestamp = record.get("timestamp")
    try:
        return isinstance(timestamp, str) and parse_iso(timestamp) <= now
    except ValueError:
        return False


def scan_codex_roots(roots, names, *, now: datetime, windows, codex_off=()) -> dict:
    """Invoke-rate counts over rollout files. `counts` holds every record of every session, the
    measurement the skills trial pins. Two disjoint parts of it are reported beside it and never
    subtracted from it: of_which_user_config_ignored, the own records of sessions whose catalog lists
    a codex_off skill (a different listing state, as under --ignore-user-config), and
    of_which_copied_from_parent, the records a spawned sub-agent's rollout copied from its parent
    (the parent's rollout holds them too)."""
    windows = tuple(sorted(set(windows)))
    mention_patterns = {name: re.compile(r"\$" + re.escape(name) + r"\b") for name in names}
    totals = _empty_counts(names, windows)
    ignored_own = _empty_counts(names, windows)
    copied_all = _empty_counts(names, windows)
    files = iter_rollout_files(roots)
    parse_errors = ignored_sessions = 0
    for path in files:
        own, copied, file_errors, ignored = scan_rollout_file(path, names, mention_patterns, now,
                                                              windows, codex_off)
        parse_errors += file_errors
        ignored_sessions += ignored
        for name in names:
            for window in windows:
                for metric in ("skill_md_reads", "name_mentions"):
                    totals[name][window][metric] += own[name][window][metric] + copied[name][window][metric]
                    copied_all[name][window][metric] += copied[name][window][metric]
                    if ignored:
                        ignored_own[name][window][metric] += own[name][window][metric]
    return {"roots_count": len(roots or []), "files_scanned": len(files),
            "parse_errors": parse_errors, "windows": list(windows), "counts": totals,
            "sessions_user_config_ignored": ignored_sessions,
            "of_which_user_config_ignored": ignored_own,
            "of_which_copied_from_parent": copied_all}


# --------------------------------------------------------------------------- manifest and lock


def load_manifest(path: Path) -> dict:
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(document, dict) or not isinstance(document.get("skills"), list):
        raise ValueError("expected an object with a 'skills' array")
    return document


def skill_lock_path(home: str | None = None, environment=None) -> Path:
    """skills CLI 1.7.0 global lock (npm dist/cli.mjs L3746-3750): path.join($XDG_STATE_HOME, "skills",
    ".skill-lock.json") for any non-empty XDG_STATE_HOME, untrimmed and relative or not (the CLI does not apply
    the XDG Base Directory spec's absolute-path rule), else path.join(<home>, ".agents", ".skill-lock.json").
    --home overrides the fallback base only. The join is install_skills.py's node_path_join, so a ".." or a
    leading // collapses as in Node; a relative value resolves against this process's working directory."""
    environment = os.environ if environment is None else environment
    xdg_state = environment.get("XDG_STATE_HOME")
    if xdg_state:
        return node_path_join(xdg_state, "skills", ".skill-lock.json")
    base = home or environment.get("HOME") or os.path.expanduser("~")
    return node_path_join(str(base), ".agents", ".skill-lock.json")


def node_path_join(*parts: str) -> Path:
    """tools/adoption/install_skills.py's node_path_join, the pinned CLI's path.join, imported from this checkout
    so that one copy serves both tools."""
    sys.path.insert(0, str(ROOT / "tools" / "adoption"))
    try:
        import install_skills  # noqa: E402  (the checkout's installer)
    finally:
        sys.path.pop(0)
    return install_skills.node_path_join(*parts)


def load_lock_installed_at(lock_path: Path) -> dict[str, str]:
    """{name: installedAt} from the lock's version-3 skills{} map. Missing or unreadable is {},
    never an error: age becomes unknown for every skill rather than aborting the report."""
    try:
        document = json.loads(Path(lock_path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    skills = document.get("skills") if isinstance(document, dict) else None
    if not isinstance(skills, dict):
        return {}
    return {name: entry["installedAt"] for name, entry in skills.items()
            if isinstance(entry, dict) and isinstance(entry.get("installedAt"), str)}


# --------------------------------------------------------------------------- join and report


def effective_windows(windows, manifest: dict) -> tuple[int, ...]:
    """The requested windows, unioned with the manifest's own trial.window_days: the prune rule
    is defined at that window ("zero uses in that window"), so it must always be computable, not
    just whichever --window values the caller happened to pass. Callers scan Codex with this same
    tuple (see main()); build_report also applies it so a direct call is self-consistent."""
    trial = manifest.get("trial") if isinstance(manifest.get("trial"), dict) else {}
    trial_window_days = trial.get("window_days")
    window_set = set(windows) | ({trial_window_days} if isinstance(trial_window_days, int) else set())
    return tuple(sorted(window_set))


def _claude_summary(claude: dict | None) -> dict:
    if claude is None:
        return {"measured": False, "origin": None, "format": None,
                "total_cost_usd": None, "num_turns": None}
    if claude.get("error"):
        return {"measured": False, "origin": claude.get("origin"), "refused": True,
                "reason": claude["error"], "total_cost_usd": claude.get("total_cost_usd"),
                "num_turns": claude.get("num_turns")}
    return {"measured": True, "origin": claude.get("origin"), "format": claude.get("format"),
            "total_cost_usd": claude.get("total_cost_usd"), "num_turns": claude.get("num_turns")}


def build_report(manifest: dict, *, claude: dict | None, codex_scan: dict,
                  lock_installed_at: dict, now: datetime, windows) -> dict:
    trial = manifest.get("trial") if isinstance(manifest.get("trial"), dict) else {}
    trial_window_days = trial.get("window_days")
    windows = effective_windows(windows, manifest)
    codex_measured = codex_scan["roots_count"] > 0
    # Windows codex_scan actually computed. A window in `windows` (the union above) that is not
    # in here was never scanned: its per-skill count must read as unmeasured (None), never as a
    # fabricated zero (see the "windows" field scan_codex_roots returns).
    codex_scanned_windows = set(codex_scan.get("windows", ()))
    claude_usable = claude is not None and not claude.get("error")

    skills_out = []
    prune_candidates = []
    verdict_recheck = []
    for skill in manifest["skills"]:
        name = skill["name"]
        status = skill.get("status")
        claude_listing = skill.get("claude_listing", "off")
        codex_enabled = bool(skill.get("codex_enabled", False))
        claude_listed = claude_listing != "off"

        installed_at = lock_installed_at.get(name)
        age_days = None
        if installed_at:
            try:
                age_days = (now - parse_iso(installed_at)).total_seconds() / 86400.0
            except ValueError:
                age_days = None

        if not claude_usable:
            claude_out: dict | str = "not-measured"
            claude_zero = None
            claude_evaluated = False
        else:
            row = claude["rows"].get(name)
            if row is None:
                # Absent from this capture is unmeasured, never a fabricated zero -- the same
                # "never scanned reads as unmeasured" rule applied to Codex windows above. This
                # holds even when claude_listed is True: a captured /skill-doctor table can miss a
                # listed skill (e.g. it scrolled out of a truncated capture), and reporting 0 would
                # claim an observation that was never made.
                claude_out = {"listing": claude_listing, "in_table": False, "context_tokens": None,
                              "uses": None, "last_used": None}
            else:
                claude_out = {"listing": claude_listing, "in_table": True,
                              "context_tokens": row["context_tokens"], "uses": row["uses"],
                              "last_used": row["last_used"]}
            claude_zero = claude_out["uses"] == 0 if claude_out["uses"] is not None else None
            claude_evaluated = claude_listed and claude_out["uses"] is not None

        codex_zero_at_trial = None
        if not codex_measured:
            codex_out: dict | str = "not-measured"
            codex_evaluated = False
        else:
            per_window = {
                str(window): (codex_scan["counts"].get(name, {}).get(
                    window, {"skill_md_reads": 0, "name_mentions": 0})
                    if window in codex_scanned_windows else None)
                for window in windows
            }
            def part(key: str) -> dict:
                return {str(window): (codex_scan.get(key, {}).get(name, {}).get(
                            window, {"skill_md_reads": 0, "name_mentions": 0})
                            if window in codex_scanned_windows else None)
                        for window in windows}
            codex_out = {"enabled": codex_enabled, "counts": per_window,
                         "of_which_user_config_ignored": part("of_which_user_config_ignored"),
                         "of_which_copied_from_parent": part("of_which_copied_from_parent")}
            codex_evaluated = codex_enabled
            if isinstance(trial_window_days, int) and trial_window_days in codex_scanned_windows:
                trial_counts = per_window[str(trial_window_days)]
                codex_zero_at_trial = (trial_counts["skill_md_reads"] == 0
                                        and trial_counts["name_mentions"] == 0)

        evaluated_clients = []
        zero_flags = []
        if claude_evaluated:
            evaluated_clients.append("claude")
            zero_flags.append(bool(claude_zero))
        if codex_evaluated and codex_zero_at_trial is not None:
            evaluated_clients.append("codex")
            zero_flags.append(bool(codex_zero_at_trial))

        zero_on_evaluated = all(zero_flags) if evaluated_clients else None
        prune_eligible = bool(
            evaluated_clients and zero_on_evaluated
            and age_days is not None and isinstance(trial_window_days, int)
            and age_days >= trial_window_days
        )

        entry = {
            "name": name, "status": status, "gap": skill.get("gap"),
            "installed_at": installed_at, "age_days": age_days,
            "claude": claude_out, "codex": codex_out,
            "evaluated_clients": evaluated_clients,
            "zero_on_evaluated_clients": zero_on_evaluated,
            "prune_eligible": prune_eligible,
        }
        skills_out.append(entry)
        if prune_eligible:
            record = {"name": name, "age_days": age_days, "evaluated_clients": evaluated_clients}
            if status == "kept":
                record["flag"] = "verdict re-record required"
                verdict_recheck.append(record)
            else:
                prune_candidates.append(record)

    return {
        "schema_version": 1,
        "kind": "skill_invoke_rate_report",
        "generated_at": now.isoformat(),
        "windows_days": list(windows),
        "trial_window_days": trial_window_days,
        "claude": _claude_summary(claude),
        "codex": {"measured": codex_measured, "roots_count": codex_scan["roots_count"],
                   "files_scanned": codex_scan["files_scanned"],
                   "parse_errors": codex_scan["parse_errors"],
                   "sessions_user_config_ignored": codex_scan.get("sessions_user_config_ignored", 0)},
        "skills": skills_out,
        "prune_candidates": prune_candidates,
        "verdict_recheck": verdict_recheck,
        "limits": (
            "Claude 'uses' from /skill-doctor is not windowed by --window (only its '7d tokens' "
            "column is): the same lifetime count is reused for every window's zero-usage check, "
            "a documented gap, not a measured per-window value. Codex counts are windowed from "
            "each rollout line's own timestamp and hold every session's records, the measurement "
            "the trial pins; every flag reads them. Two disjoint parts of them are reported beside "
            "them, never subtracted: of_which_user_config_ignored (own records of sessions whose "
            "catalog lists a codex_enabled=false skill, as under --ignore-user-config: a different "
            "listing state) and of_which_copied_from_parent (records a spawned sub-agent's rollout "
            "copied from its parent, which the parent's rollout also holds). A skill with no measured, enabled/listed client "
            "is excluded from prune_candidates and verdict_recheck, never read as zero usage. "
            "The measured listing cost (claude.context_tokens) is its own counter: never mix it "
            "into tools/token-report's token-efficiency ledger."
        ),
    }


def render_text(report: dict) -> str:
    lines = [f"skill invoke-rate report  generated_at={report['generated_at']}  "
             f"windows={report['windows_days']}d  trial_window={report['trial_window_days']}d"]
    claude = report["claude"]
    if claude["measured"]:
        lines.append(f"claude: measured via {claude['origin']} ({claude['format']}) "
                     f"total_cost_usd={claude['total_cost_usd']} num_turns={claude['num_turns']}")
    elif claude.get("refused"):
        lines.append(f"claude: REFUSED via {claude['origin']}: {claude['reason']}")
    else:
        lines.append("claude: not-measured (pass --claude-skill-doctor FILE or --run-skill-doctor)")
    codex = report["codex"]
    lines.append(f"codex: {'measured' if codex['measured'] else 'not-measured (pass --codex-root)'} "
                 f"roots_count={codex['roots_count']} files_scanned={codex['files_scanned']} "
                 f"parse_errors={codex['parse_errors']} "
                 f"user_config_ignored_sessions={codex['sessions_user_config_ignored']}")
    lines.append("")
    windows = report["windows_days"]
    lines.append(f"{'skill':<34} {'status':<6} {'age_days':>9} {'claude_uses':>11} "
                 + " ".join(f"codex_{w}d(md/$)".rjust(16) for w in windows) + "  flag")
    for entry in report["skills"]:
        claude_entry = entry["claude"]
        claude_uses = "-" if claude_entry == "not-measured" or claude_entry["uses"] is None \
            else str(claude_entry["uses"])
        codex_entry = entry["codex"]
        cells = []
        for window in windows:
            counted = None if codex_entry == "not-measured" else codex_entry["counts"][str(window)]
            cells.append("-" if counted is None else f"{counted['skill_md_reads']}/{counted['name_mentions']}")
        age = "-" if entry["age_days"] is None else f"{entry['age_days']:.1f}"
        flag = ("PRUNE-CANDIDATE" if entry["prune_eligible"] and entry["status"] == "trial" else
                "VERDICT-RE-RECORD" if entry["prune_eligible"] else "")
        lines.append(f"{entry['name']:<34} {(entry['status'] or '-'):<6} {age:>9} {claude_uses:>11} "
                     + " ".join(cell.rjust(16) for cell in cells) + f"  {flag}")
    lines.append("")
    lines.append(f"prune_candidates={len(report['prune_candidates'])} "
                 f"verdict_recheck={len(report['verdict_recheck'])}")
    lines.append(report["limits"])
    return "\n".join(lines)


# --------------------------------------------------------------------------- Codex lanes

# The opening tag of Context Mode's routing block; its SessionStart hook adds the block to a Codex
# session's developer context (context-mode 1.0.169, hooks/routing-block.mjs createRoutingBlock).
DEFAULT_LANES_MARKER = "<context_window_protection>"
# curl or wget in command position, the rule examples/claude-native/workflows/child-usage.mjs uses:
# at a line start or after ; & | ( ` or $(, optionally behind the shell keywords do, then, else, elif,
# if, while, until, ! and {, and behind rtk, sudo, env, command, exec, time, nice, nohup or timeout N.
FETCH_WORD = re.compile(
    r"(?:^|[;&|(`]|\$\()\s*(?:(?:do|then|else|elif|if|while|until|!|\{|rtk|sudo|env|command|exec|time|nice"
    r"|nohup|timeout\s+\S+)\s+)*(?:curl|wget)(?=\s|$)", re.M)
URL_HOST = re.compile(r"\bhttps?://(\[[^\]\s]*\]|[^\s/:'\"`<>)?#\]]+)", re.I)
LOOPBACK = re.compile(r"^(?:localhost|127(?:\.\d{1,3}){3}|\[::1\]|0\.0\.0\.0)$", re.I)
RTK_FIRST_WORD = re.compile(r"\s*rtk\s")
# A quoted string a shell runs: the argument of sh/bash/zsh/dash/ksh/su ... -c, of eval, or of ssh <host>.
RUN_QUOTED = re.compile(r"(?:^|[\s;&|(])(?:(?:(?:ba|z|da|k)?sh|su)(?:\s+-[A-Za-z]+)*\s+-[A-Za-z]*c|eval"
                        r"|ssh(?:\s+-\S+)*\s+\S+)\s*$")
SHELL_WORD = re.compile(r"^(?:(?:ba|z|da|k)?sh|ssh)$")
HEREDOC = re.compile(r"(?<!<)<<(?!<)-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")
SHELL_WRAPPERS = {"sudo", "env", "command", "exec", "nice", "nohup", "time", "rtk"}
# Shell text is read by bash(1) (GNU bash 5.2) QUOTING, COMMENTS and Here Documents: an escaped
# character is literal and \<newline> is a line continuation; a word beginning with # ends the line
# as a comment; inside double quotes, and in the body of a heredoc whose delimiter is unquoted,
# $(...) and `...` still run, while \$ and \` are literal.
DOUBLE_QUOTED_DATA = re.compile(r"\\[\s\S]|\$\([^()]*\)|`[^`]*`|[;&|()`\n]")
SUBSTITUTION = re.compile(r"\\[\s\S]|\$\([^()]*\)|`[^`]*`")
ESCAPED_DATA = frozenset(" \t;&|()<>`$'\"\\#{}!")  # escaped, these become the data character _
WORD_BREAK = frozenset(" \t\n;&|()<>")  # bash metacharacters: a # after one begins a comment
# Report keys that come from rollouts (server, function and originator names) must be name-shaped;
# anything else (a path, text, an address) is counted under "(other)".
SAFE_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:+-]{0,79}$")
FETCH_KEYS = ("web_open_page", "web_search", "web_other", "ctx_fetch_and_index",
              "shell_curl_wget", "shell_curl_wget_loopback")
USER_CONFIG_METHOD = (
    "ignored: the session's skill catalog (developer <skills_instructions> or world_state host_skills) "
    "lists the SKILL.md of a manifest skill with codex_enabled=false. Codex reads skill enablement "
    "rules only from the User and SessionFlags config layers (codex-rs/config/src/skills_config.rs, "
    "rust-v0.157.1) and --ignore-user-config loads the User layer as an empty table "
    "(codex-rs/config/src/loader/mod.rs), so the trial's enabled=false entries in the user config "
    "stop applying. applied: the catalog lists manifest skills, none of them codex_enabled=false. "
    "unknown: no catalog.")
TOOL_ITEM_TYPES = ("McpToolCall", "CommandExecution", "Extension", "FileChange")
LANES_LIMITS = (
    "Counts come from rollout records inside [since, until): item_completed McpToolCall, "
    "CommandExecution, Extension and FileChange items and function_call records, one tool call per "
    "id (a function_call's call_id is its item's id in the rollouts of codex-cli 0.155.1 and "
    "0.157.1) counted in the window of the call's first record before until, so a call requested "
    "before since and completed inside is not counted again and adjacent windows add up, while its "
    "shell, MCP and fetch lanes count in the window of its item_completed event; token_count for "
    "the first prompt (input tokens, cached included) and response_item calls for SKILL.md reads. "
    "Shell, MCP and fetch counts therefore need item_completed events, an EventMsg whose "
    "persistence depends on the rollout's history mode (codex-rs/rollout/src/policy.rs): "
    "sessions_by_history_mode reports session_meta.history_mode, and "
    "sessions_with_tool_calls_but_no_item_events counts sessions whose own records before until "
    "hold model tool calls but no such event, whose shell, MCP and fetch lanes read as zero. "
    "Session properties (kind, originator, history mode, user_config, marker) use every record "
    "before until. Records a spawned sub-agent's rollout copied from its parent (ordinal below "
    "subagent_history_start_ordinal) count toward those properties only, never as the child's "
    "calls. The marker is looked for in developer messages only; marker_inherited and marker_injected split it by "
    "content item (in a record copied from the parent, or in the session's own), and marker_injected_kinds counts the "
    "injected items by content kind (content_item_kinds, (none) when the kinds do not align with the items). The rtk "
    "prefix is the first word "
    "of the shell script; curl/wget counts only in command position of the text a shell runs "
    "(quoted strings, heredoc bodies, escaped characters and comments are data unless sh -c, eval, "
    "ssh or a shell heredoc runs them, though $(...) and `...` inside double quotes or an unquoted "
    "heredoc still run: bash(1) QUOTING, COMMENTS and Here Documents), optionally behind the shell "
    "keywords do, then, else, elif, if, while, until, ! and { "
    "and behind rtk, sudo, env, command, exec, time, nice, nohup or timeout N, and a call whose "
    "literal URLs are all loopback is counted apart. ctx_fetch_and_index_share is "
    "ctx_fetch_and_index / (web page opens + ctx_fetch_and_index + remote curl/wget): a fetch run "
    "inside a Context Mode sandbox (ctx_execute or ctx_batch_execute code), a gh api call and "
    "fetch() or an HTTP library in a script are in no lane. Server, function, originator and "
    "history-mode names that are not name-shaped are counted under (other). Sessions whose user "
    "config was ignored are negative controls, never workers. A session's role (actors[].role, sessions_by_role, "
    "groups.workers_by_role) is session_meta.agent_role (or agent_type), else its thread_spawn source's, trimmed; a "
    "sub-agent without one is (none) and every other session (root). Rollout files not modified since the "
    "window start are skipped unread.")


def safe_key(value) -> str:
    return str(value) if SAFE_KEY.match(str(value)) else "(other)"


def model_key(value) -> str | None:
    """PR-A 10g: a model as a report key. TurnContextItem.model is a String (openai/codex rust-v0.157.1
    protocol/src/protocol.rs:3328): a name-shaped model is kept, with at most one provider segment in front (a gateway route
    such as cx/gpt-6-astra); any other string (a path, '..', more segments, an empty segment) is (other), and a value that is
    not a non-empty string is None. Comparisons of routes use the raw strings, never these keys."""
    if not isinstance(value, str) or not value:
        return None
    parts = value.split("/")
    return value if len(parts) <= 2 and all(SAFE_KEY.fullmatch(part) for part in parts) else "(other)"


def effort_key(value) -> str | None:
    """PR-A 10g: a reasoning effort as a report key. ReasoningEffort at rust-v0.157.1 is none, minimal, low, medium, high,
    xhigh, max, ultra, persistent or a model-defined custom string (protocol/src/openai_models.rs:59-72), so every name-shaped
    effort is kept, any other string is (other), and a value that is not a non-empty string is None."""
    if not isinstance(value, str) or not value:
        return None
    return value if SAFE_KEY.fullmatch(value) else "(other)"


# Rust's str::trim removes the Unicode White_Space characters (Unicode PropList.txt White_Space), not Python's str.strip
# set, which also removes U+001C to U+001F.
RUST_WHITE_SPACE = ("\t\n\x0b\x0c\r \x85\xa0            "
                    "    　")


def _role_of(fields) -> str | None:
    """A custom-agent role as Codex keeps it: agent_role, which also deserializes from agent_type, trimmed, and none when
    empty (openai/codex rust-v0.157.1 core/src/tools/handlers/multi_agents_v2/spawn.rs:126-130) or not a string."""
    if not isinstance(fields, dict):
        return None
    value = fields["agent_role"] if "agent_role" in fields else fields.get("agent_type")
    return (value.strip(RUST_WHITE_SPACE) or None) if isinstance(value, str) else None


def codex_session_kind(meta: dict) -> str:
    """A session's kind from its first session_meta's source: subagent (SessionSource::SubAgent), exec (codex exec), else
    other (another root, such as the interactive CLI)."""
    source = meta.get("source")
    return "subagent" if isinstance(source, dict) and "subagent" in source else "exec" if source == "exec" else "other"


def thread_spawn_source(meta: dict) -> dict:
    """The SubAgentSource::ThreadSpawn of a session_meta ({parent_thread_id, depth, agent_path, agent_nickname, agent_role};
    rust-v0.157.1 protocol/src/protocol.rs:2901-2916), or {}."""
    source = meta.get("source")
    subagent = source.get("subagent") if isinstance(source, dict) else None
    spawn = subagent.get("thread_spawn") if isinstance(subagent, dict) else None
    return spawn if isinstance(spawn, dict) else {}


def session_role_raw(meta: dict) -> str | None:
    """The session's trimmed role from its first session_meta: SessionMeta.agent_role (rust-v0.157.1
    protocol/src/protocol.rs:3153-3155), else the ThreadSpawn source's agent_role (:2904-2913); None without one."""
    return _role_of(meta) or _role_of(thread_spawn_source(meta))


def session_role(meta: dict, kind: str | None) -> str:
    """PR-A 10b: the session's role (session_role_raw) as a name-shaped key; a sub-agent without a role is (none), and every
    other session (root)."""
    role = session_role_raw(meta)
    if role is not None:
        return safe_key(role)
    return "(none)" if kind == "subagent" else "(root)"


def _call_arguments(value) -> dict:
    """A function call's arguments as an object (a JSON object string, or an object), else {}."""
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(value)
    except (ValueError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


# usize::MAX of the 64-bit targets Codex ships for; a larger fork_turns fails usize::from_str.
USIZE_MAX = 2 ** 64 - 1


def requested_fork_turns(value) -> tuple[str, int | None]:
    """PR-A 10g: a V2 spawn_agent fork_turns as (state, n), as SpawnAgentArgs::fork_mode reads it (openai/codex rust-v0.157.1
    core/src/tools/handlers/multi_agents_v2/spawn.rs:265-299): trimmed with str::trim (RUST_WHITE_SPACE), absent, null or
    empty is all by default (default_all), `none` and `all` match ASCII case-insensitively, and anything else must parse as a
    usize (an optional '+' then ASCII digits, within USIZE_MAX) and be nonzero (last_n), or the call fails (invalid).
    fork_turns is an Option<String>, so upstream rejects a JSON integer; the frozen launch matrix writes `fork_turns: 2`
    (preregistration.json seed-binding-2), so a positive integer reads as the string of its digits would (the U3 review).
    A bool, a float or any other JSON type is invalid. A linear check, no regular expression."""
    if value is None:
        return "default_all", None
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        return "invalid", None
    if isinstance(value, int):
        return ("last_n", value) if 0 < value <= USIZE_MAX else ("invalid", None)
    text = value.strip(RUST_WHITE_SPACE)
    if not text:
        return "default_all", None
    if text.isascii() and text.lower() in ("none", "all"):
        return text.lower(), None
    digits = text[1:] if text.startswith("+") else text
    if not (digits and digits.isascii() and digits.isdigit()):
        return "invalid", None
    # Leading zeros of any length parse in Rust; int() refuses over 4,300 digits, and USIZE_MAX has 20.
    significant = digits.lstrip("0")
    number = int(significant) if 0 < len(significant) <= 20 else 0 if not significant else USIZE_MAX + 1
    return ("last_n", number) if 0 < number <= USIZE_MAX else ("invalid", None)


def _program_of(prefix: str) -> str:
    """The program of the last simple command in prefix: assignments, options, wrappers and a
    timeout duration skipped (child-usage.mjs programOf)."""
    words = re.split(r"[;&|(]", prefix)[-1].split()
    index = 0
    while index < len(words):
        word = words[index]
        if re.match(r"[A-Za-z_][A-Za-z0-9_]*=", word) or word.startswith("-") or word in SHELL_WRAPPERS:
            index += 1
        elif word == "timeout":
            index += 2
        else:
            return word.rsplit("/", 1)[-1]
    return ""


def _double_quoted_data(match: re.Match) -> str:
    text = match.group(0)
    return "_" if text[0] == "\\" else text if len(text) > 1 else " "


def executed_text(command: str) -> str:
    """The command text a shell would run (child-usage.mjs executedText): a heredoc body is data
    unless the heredoc feeds a shell, though with an unquoted delimiter its command substitutions
    still run; a quoted string is data unless a shell runs it (RUN_QUOTED), though inside double
    quotes $(...) and `...` still run; an escaped character and a comment are data, and
    \\<newline> joins lines. Data keeps its words, so URL arguments stay, but loses the separators
    that would put a word in command position."""
    lines, kept, index = (command or "").split("\n"), [], 0
    while index < len(lines):
        kept.append(lines[index])
        match = HEREDOC.search(lines[index])
        if match and not SHELL_WORD.match(_program_of(lines[index][:match.start()])):
            while index + 1 < len(lines) and lines[index + 1].lstrip("\t") != match.group(2):
                index += 1
                kept.append("" if match.group(1) else " ".join(
                    found.group(0) for found in SUBSTITUTION.finditer(lines[index]) if found.group(0)[0] != "\\"))
        index += 1
    text, out, index = "\n".join(kept), "", 0
    while index < len(text):
        char = text[index]
        if char == "\\":
            following = text[index + 1:index + 2]
            if following and following != "\n":
                out += "_" if following in ESCAPED_DATA else following
            index += 2
            continue
        if char == "#" and (not out or out[-1] in WORD_BREAK):
            end = text.find("\n", index)
            index = len(text) if end < 0 else end
            continue
        if char not in "'\"":
            out += char
            index += 1
            continue
        end = index + 1
        while end < len(text) and text[end] != char:
            end += 2 if char == '"' and text[end] == "\\" else 1
        inner = text[index + 1:end]
        if RUN_QUOTED.search(out):
            out += ";" + inner + ";"
        elif char == '"':
            out += '"' + DOUBLE_QUOTED_DATA.sub(_double_quoted_data, inner) + '"'
        else:
            out += "'" + re.sub(r"[;&|()`$\n]", " ", inner) + "'"
        index = end + 1
    return out


def fetch_kind(command: str) -> str | None:
    """'loopback' when every literal URL of an executed curl/wget command is a loopback host, 'fetch'
    for any other executed curl/wget command (a remote URL, or no literal URL), None otherwise."""
    text = executed_text(command)
    if not FETCH_WORD.search(text):
        return None
    hosts = URL_HOST.findall(text)
    return "loopback" if hosts and all(LOOPBACK.match(host) for host in hosts) else "fetch"


SCRIPT_SHELLS = ("sh", "bash", "zsh", "dash", "ksh")


def shell_script(command) -> str:
    """The shell text a command ran. A string is that text. An argv array is one command: a shell's `-c` or
    `-lc` script argument (openai/codex rust-v0.157.1 codex-rs/core/src/shell.rs runs [shell, -lc, script]) is the
    script itself; any other argv is joined with each element quoted (shlex.join), so a metacharacter inside one
    element stays data and `-c` of a program that is not a shell is one of its arguments (U1 pivot D6, GPT-6 #11)."""
    if isinstance(command, list):
        parts = [str(part) for part in command]
        if len(parts) >= 3 and parts[1] in ("-lc", "-c") and os.path.basename(parts[0]) in SCRIPT_SHELLS:
            return parts[2]
        return shlex.join(parts)
    return command if isinstance(command, str) else ""


# PR-A U3 normalization (design section 6, with the review's shell_script finding): the PR-A measurement reads a shell call
# through resolve_command or resolve_shell_call, which also say when its text is no POSIX shell script; shell_script keeps
# the legacy lane counters' reading. exec_command's model-provided shell is typed as openai/codex rust-v0.157.1 types it
# (shell-command/src/shell_detect.rs:39-59): zsh, bash and sh run a -c script, pwsh and powershell run PowerShell text and
# cmd runs cmd text (core/src/shell.rs:22-49); any other value runs the OS fallback shell, /bin/sh on Unix and cmd.exe on
# Windows (shell_detect.rs:315-334), which the rollout does not record.
CODEX_SHELL_TYPES = {"zsh": "posix", "bash": "posix", "sh": "posix", "pwsh": "non_posix", "powershell": "non_posix",
                     "cmd": "non_posix"}
NON_POSIX_PROGRAMS = ("pwsh", "powershell", "cmd")
# measurement.codex_commands: calls whose text is no POSIX shell script (non_posix_shell) or whose shell is not known
# (unknown_shell), both unresolved, and CommandExecution items that are no model tool call: a user's own shell command
# (user_shell) and an interaction with a running process (exec_interactions). ExecCommandSource at rust-v0.157.1 is agent,
# user_shell, unified_exec_startup or unified_exec_interaction (protocol/src/protocol.rs:3534-3544).
CODEX_COMMAND_STATES = ("non_posix_shell", "unknown_shell", "user_shell", "exec_interactions")
SKIPPED_COMMAND_SOURCES = {"user_shell": "user_shell", "unified_exec_interaction": "exec_interactions"}


def _program_stem(path: str) -> str:
    """A program path's file name up to its first '.' after the first character, with '/' and, as on Windows, '\\' as
    separators and trailing separators ignored: the name Codex's detect_shell_type reaches by taking the file stem again and
    again (Rust Path::file_stem, shell_detect.rs:48-55). A linear scan."""
    end = len(path)
    while end and path[end - 1] in "/\\":
        end -= 1
    start = end
    while start and path[start - 1] not in "/\\":
        start -= 1
    name = path[start:end]
    if name in (".", ".."):
        return ""
    dot = name.find(".", 1)
    return name if dot < 0 else name[:dot]


def codex_shell_type(shell) -> str | None:
    """exec_command's shell as Codex types it: 'posix', 'non_posix' or None when the shell that ran is not known. The value
    itself, else its file stem again and again, case-sensitively (shell_detect.rs:39-59). A value that is not a string fails
    ExecCommandArgs (shell: Option<String>, core/src/tools/handlers/unified_exec.rs:27-33), so it is not known either."""
    if not isinstance(shell, str):
        return None
    return CODEX_SHELL_TYPES.get(shell) or CODEX_SHELL_TYPES.get(_program_stem(shell))


def _posix_script(parts: list) -> str | None:
    """The script of a POSIX shell's argv: with -c among its options, the shell reads commands from the first non-option
    argument (bash(1) INVOCATION and OPTIONS; the sh -c synopsis of POSIX.1-2024 XCU sh). An option word is '-' or '+'
    followed by ASCII letters, and each o or O in it takes the next word as its option name (-o option, -O shopt_option).
    '--' or '-' ends the options and the next word is the first non-option argument (bash(1) OPTIONS: "A -- signals the
    end of options ... An argument of - is equivalent to --"; POSIX.1-2024 XCU sh: "A single <hyphen-minus> shall be
    treated as the first operand and then ignored"; bash 5.2.21 and dash run it so on this stack). Any other word ends the
    options too, so a long option such as --login leaves no script. A linear scan."""
    index, run = 1, False
    while index < len(parts):
        word = parts[index]
        if word in ("--", "-"):
            index += 1
            break
        letters = word[1:]
        if not (word[:1] in ("-", "+") and letters and letters.isascii() and letters.isalpha()):
            break
        run |= word[0] == "-" and "c" in letters
        index += 1 + letters.count("o") + letters.count("O")
    return parts[index] if run and index < len(parts) else None


def resolve_command(command) -> tuple[str, str | None]:
    """(text, unresolved state) of a command as the PR-A measurement reads it. An argv (a CommandExecution's command,
    protocol/src/items.rs:259; a local_shell_call's or the shell tool's command) runs its program directly, typed by its file
    stem: pwsh, powershell and cmd, matched ASCII case-insensitively as Windows resolves program names, run text this reader
    does not parse, so the command is unresolved ('', 'non_posix_shell'); a POSIX shell (SCRIPT_SHELLS) with -c runs its
    script (_posix_script); any other argv is one command, joined with each element quoted (shlex.join, U1 pivot D6). A
    string is the text a POSIX shell ran, and any other value no text."""
    if not isinstance(command, list):
        return (command if isinstance(command, str) else ""), None
    parts = [str(part) for part in command]
    stem = _program_stem(parts[0]) if parts else ""
    if stem.isascii() and stem.lower() in NON_POSIX_PROGRAMS:
        return "", "non_posix_shell"
    script = _posix_script(parts) if stem in SCRIPT_SHELLS else None
    return (shlex.join(parts) if script is None else script), None


def resolve_shell_call(arguments: dict) -> tuple[str, str | None]:
    """(text, unresolved state) of a shell tool's function call. exec_command's cmd runs in the shell its shell argument
    names, typed by codex_shell_type, and without one (absent or null) in the session's shell (core/src/tools/handlers/
    unified_exec.rs:99-126), read as a POSIX shell; so does shell_command's command, and the shell tool's command is an argv
    (resolve_command). An unresolved call's text is ''."""
    command = arguments.get("cmd", arguments.get("command", ""))
    if isinstance(command, list) or arguments.get("shell") is None:
        return resolve_command(command)
    kind = codex_shell_type(arguments["shell"])
    if kind == "posix":
        return resolve_command(command)
    return "", "non_posix_shell" if kind == "non_posix" else "unknown_shell"


def message_text(payload: dict) -> str:
    content = payload.get("content")
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    return "\n".join(item["text"] for item in content
                     if isinstance(item, dict) and isinstance(item.get("text"), str))


# The content kind of a hook's additionalContext: Codex records it as a developer message fragment of this kind, for a root
# session's SessionStart and a spawned sub-agent's SubagentStart alike (openai/codex rust-v0.157.1 36650394
# core/src/context/hook_additional_context.rs:15-22, core/src/hook_runtime.rs:128-154, :848-872).
HOOK_CONTEXT_KIND = "hooks.additional_context"
HOOK_CONTEXT_COUNTERS = ("inserted", "with_marker", "inherited", "inherited_with_marker")


def message_items(payload: dict) -> list[tuple[str, str | None]]:
    """A message's text content items as (text, kind). Codex aligns internal_chat_message_metadata_passthrough
    .content_item_kinds with the message's content entries (rust-v0.157.1 protocol/src/models.rs:958-993, a fragment writes
    one kind per item at context-fragments/src/fragment.rs:35-53; a kind is a transparent string,
    protocol/src/models/item_metadata.rs:5-7). A kinds value that is not a list as long as the content, or a kind that is not
    a string, leaves the kind None."""
    content = payload.get("content")
    if isinstance(content, str):
        return [(content, None)]
    if not isinstance(content, list):
        return []
    metadata = payload.get("internal_chat_message_metadata_passthrough")
    kinds = metadata.get("content_item_kinds") if isinstance(metadata, dict) else None
    aligned = isinstance(kinds, list) and len(kinds) == len(content)
    items = []
    for index, item in enumerate(content):
        if isinstance(item, dict) and isinstance(item.get("text"), str):
            kind = kinds[index] if aligned else None
            items.append((item["text"], kind if isinstance(kind, str) else None))
    return items


def catalog_texts(record: dict) -> list[str]:
    """The skill-catalog texts one rollout record carries: a developer message holding the
    <skills_instructions> block, or world_state's host_skills body (codex-cli 0.157.1)."""
    payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
    if record.get("type") == "world_state":
        state = payload.get("state") if isinstance(payload.get("state"), dict) else {}
        host_skills = state.get("host_skills") if isinstance(state.get("host_skills"), dict) else {}
        return [host_skills["body"]] if isinstance(host_skills.get("body"), str) else []
    if (record.get("type") == "response_item" and payload.get("type") == "message"
            and payload.get("role") == "developer"):
        text = message_text(payload)
        return [text] if "<skills_instructions>" in text else []
    return []


# PR-A reuses child-usage.mjs's measurement kernel rather than maintaining a second
# M3/M4/M5/M-R1 implementation. Native formats: openai/codex rust-v0.157.1,
# codex-rs/protocol/src/protocol.rs:2234-2310 and rollout/src/policy.rs.
CODEX_COUNTERS = ("input_tokens", "cached_input_tokens", "cache_write_input_tokens", "output_tokens",
                  "reasoning_output_tokens", "total_tokens")
# TokenUsage.cache_write_input_tokens is serde(default) at rust-v0.157.1 (protocol.rs:2239-2241), so a rollout of an older client
# can lack it (binding correction 4 of the U3 build): its value is then null, never 0, and its absence is no usage gap.
OPTIONAL_CODEX_COUNTERS = ("cache_write_input_tokens",)
MEASUREMENT_MODULE = ROOT / "examples/claude-native/workflows/child-usage.mjs"
# The kernel's rtkAgent for Codex replay (PR-A U3 10d): rtk-ai/rtk v0.50.0 InProcess(Host::Codex), src/hooks/decision.rs:196-204.
CODEX_RTK_AGENT = "codex"
# The private per-call Codex ledger that --call-ledger writes (binding correction 1 of the U3 build, gap G1 of the U11 design):
# one record per call the kernel measured, from the kernel's callLedger, PR-A U2's export (claude/pra-u2-kernel-measures-2d-20260929
# at b2dd1eb7, examples/claude-native/workflows/child-usage.mjs:2793-2820; U2 design 4.5). A record keeps these of the kernel's
# fields; its session_id and owner, null for a Codex bridge row, give way to the thread id and owner kind the adapter reads, and
# its background and m15_class are not part of codex-call-ledger/1.
CODEX_CALL_LEDGER_SCHEMA = "codex-call-ledger/1"
LEDGER_CALL_FIELDS = ("tool", "server", "state", "cause", "native_status", "sandbox", "code_mode")
# Codex tools whose command the bridge reads as a Bash call (a local_shell_call is one as well).
CODEX_SHELL_TOOLS = ("exec_command", "shell_command", "shell")
# The unified exec response header of openai/codex rust-v0.157.1 (36650394) core/src/tools/context.rs:524-548:
# "Chunk ID: <id>" (omitted when empty), "Wall time: <s> seconds", "Process exited with code <n>" when the
# process ended, "Process running with session ID <id>" while it runs, "Original token count: <n>", then the
# line "Output:" and the output itself (:550-575).
EXEC_HEADER_SECTIONS = 5
EXEC_EXITED = "Process exited with code "
EXEC_RUNNING = "Process running with session ID "
# The exit code is an i32 written in decimal (up to 10 digits with its sign for the full i32 range). The pivot brief (D6) fixed a
# nine-digit bound: a header with more digits reads unknown, never succeeded, so a ten-digit crash status such as a Windows
# NTSTATUS (-1073741819) reads unknown, not failed (the review's low finding; both count as not successful, and no Windows Codex
# was available to check). int() never sees a digit string over CPython's conversion limit (4,300 digits, which raises ValueError).
EXEC_CODE_DIGITS = 9
# PR-A 10e (U3 design section 7 with its review). The model's own calls: CALL_PAYLOAD_TYPES and a hosted web search
# (ResponseItem::WebSearchCall, openai/codex rust-v0.157.1 protocol/src/models.rs:1182-1203, persisted by
# rollout/src/policy.rs:56). An item whose id is one of theirs is never nested.
MODEL_CALL_TYPES = CALL_PAYLOAD_TYPES | {"web_search_call"}
# Every turn event this module reads ends the turn's code-mode nesting: TurnStarted is task_started (alias turn_started) and
# TurnComplete task_complete (alias turn_complete) (protocol/src/protocol.rs:1403-1415), turn_aborted, and the attempt ends
# task_completed, turn_completed and turn_failed that measure_codex_records also reads.
TURN_EVENTS = ("task_started", "turn_started", "task_complete", "turn_complete", "task_completed", "turn_completed",
               "turn_failed", "turn_aborted")
# The code-mode wait tool, which resumes a running exec cell (code-mode-protocol/src/lib.rs:51-52, description.rs:44-51); the
# multi-agent wait is wait_agent (core/src/tools/handlers/multi_agents_spec.rs:268-291).
CODE_MODE_WAIT = "wait"
CODE_MODE_COUNTERS = ("exec_calls", "wait_calls", "nested_items", "unattributed_items", "legacy_unobservable_exec_calls",
                      "legacy_unobservable_sites", "outer_http_mentions", "outer_http_unverified_exec_calls")
# PR-A 10e legacy-mode spans (U3 design section 7, commit 8): a legacy rollout persists no CommandExecution, McpToolCall or
# web.search item_completed (rollout/src/policy.rs:94-112) and no ExecCommandEnd (:145); the McpToolCallEnd and WebSearchEnd
# events it does keep (:123-135) are not read by this adapter. So an exec there whose code can reach a fetch runs unobserved
# by this adapter. The nested tools that can fetch, by their code-mode identifiers (code-mode-protocol/src/description.rs:21
# and normalize_code_mode_identifier, :365-387): a shell command, the standalone web tool, and a Context Mode code or fetch
# tool of any MCP server.
CODE_MODE_FETCH_TOOLS = ("exec_command", "web__run")
CODE_MODE_CTX_TOOLS = ("ctx_execute", "ctx_execute_file", "ctx_batch_execute", "ctx_fetch_and_index")
JS_NAME_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_$")
# The 10e outer-JS decision (2026-09-29; tools/skill-usage/README.md, "The outer exec code"). The clients whose code-mode isolate
# was read at their tags: "Runs raw JavaScript -- no Node, no file system, no network access, no console." (code-mode-protocol/
# src/description.rs:24 at rust-v0.157.1 36650394, :20 at rust-v0.155.1 be2951ea), and globals.rs:36-48 (byte-identical at
# both tags) installs tools, ALL_TOOLS, clearTimeout, setTimeout, text, image, audio, generatedImage, store, load, notify,
# yield_control and exit, no fetch. There, a network operation is a nested tool call and the outer code is never a fetch; a
# rollout of any other client, or naming none, is the decision's overturn trigger.
NO_NETWORK_ISOLATE_CLIENTS = ("0.155.1", "0.157.1")
# The kernel's HTTP_SCRIPT detector (child-usage.mjs): \b(?:fetch\s*\(|(?:requests|httpx|urllib\.request|https?|axios)\s*\.\s*
# (?:get|post|put|request|urlopen)\s*\(), read here as a linear scan.
HTTP_WORD_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")
HTTP_MODULES = ("requests", "httpx", "urllib.request", "https", "http", "axios")
HTTP_METHODS = ("get", "post", "put", "request", "urlopen")


def _skip_blanks(code: str, index: int) -> int:
    while index < len(code) and code[index].isspace():
        index += 1
    return index


def code_mode_fetch_sites(code: str) -> int:
    """PR-A 10e: the static fetch-capable call sites in code-mode exec source. A site is the global `tools` (not part of a
    longer name, not a property such as x.tools) followed by a dot (blanks and ?. allowed) and a CODE_MODE_FETCH_TOOLS name or
    mcp__<server>__<CODE_MODE_CTX_TOOLS name>, or any bracket access tools[...], which can name any tool (conservative).
    Strings and comments are not told apart, so a mention counts; an alias (const t = tools) or destructuring is not seen.
    A linear scan."""
    sites, index = 0, 0
    while True:
        index = code.find("tools", index)
        if index < 0:
            return sites
        end = index + 5
        if (index and (code[index - 1] in JS_NAME_CHARS or code[index - 1] == ".")) or (end < len(code) and code[end] in JS_NAME_CHARS):
            index = end
            continue
        at = _skip_blanks(code, end)
        if code.startswith("?.", at) or code.startswith(".", at):
            at = _skip_blanks(code, at + (2 if code[at] == "?" else 1))
        elif not code.startswith("[", at):
            index = end
            continue
        if code.startswith("[", at):  # tools[...] or tools?.[...]
            sites += 1
            index = at + 1
            continue
        stop = at
        while stop < len(code) and code[stop] in JS_NAME_CHARS:
            stop += 1
        name = code[at:stop]
        server, _, tool = name[5:].rpartition("__") if name.startswith("mcp__") else ("", "", "")
        sites += name in CODE_MODE_FETCH_TOOLS or bool(server) and tool in CODE_MODE_CTX_TOOLS
        index = max(stop, end)


def http_script_mentions(code: str) -> int:
    """The raw matches of the kernel's HTTP_SCRIPT detector in code (HTTP_WORD_CHARS as the \\b word characters): fetch(,
    and requests, httpx, urllib.request, https, http or axios . get, post, put, request or urlopen (, with blanks around the
    dot and before the parenthesis. A linear scan over word starts."""
    mentions = 0
    for index, char in enumerate(code):
        if char not in HTTP_WORD_CHARS or (index and code[index - 1] in HTTP_WORD_CHARS):
            continue
        if code.startswith("fetch", index):
            at = _skip_blanks(code, index + 5)
            mentions += code.startswith("(", at)
            continue
        module = next((name for name in HTTP_MODULES if code.startswith(name, index)), None)
        if module is None:
            continue
        at = _skip_blanks(code, index + len(module))
        if not code.startswith(".", at):
            continue
        at = _skip_blanks(code, at + 1)
        method = next((name for name in HTTP_METHODS if code.startswith(name, at)), None)
        if method is not None:
            mentions += code.startswith("(", _skip_blanks(code, at + len(method)))
    return mentions


def codex_call_name(payload: dict) -> str:
    """A function or custom call's tool name. Native FunctionCall keeps namespace separate
    (models.rs:1073-1088), so an MCP namespace is joined back in front of its tool name."""
    name, namespace = payload.get("name", "unknown"), payload.get("namespace") or ""
    if namespace.startswith("mcp__") and not name.startswith("mcp__"):
        name = namespace.rstrip("_") + "__" + name
    return name


def exec_header_state(output) -> tuple[bool, str | None]:
    """(is_error, native_state) of a shell call's result read from its unified exec header alone, for a call
    with no persisted item state: a rollout output never carries the success flag (protocol/src/models.rs:
    2173-2182) and legacy history mode persists no CommandExecution item (rollout/src/policy.rs:94-112).
    An exit code of 0 is success and any other exit a failure. A running process (write_stdin can report a
    live process with an exit code, core/src/unified_exec/process_manager.rs:1066-1071), a header without
    either line, an exit code of more than EXEC_CODE_DIGITS digits, or text without the header leaves the
    state unknown. Only the lines before "Output:" are read, with a linear line scan and no regular
    expression."""
    if isinstance(output, list):
        first = output[0] if output else None
        output = first.get("text") if isinstance(first, dict) else None
    if not isinstance(output, str) or not output.startswith(("Chunk ID: ", "Wall time: ")):
        return False, "unknown"
    start, code, running = 0, None, False
    for _ in range(EXEC_HEADER_SECTIONS + 1):
        end = output.find("\n", start)
        line = output[start:] if end < 0 else output[start:end]
        if line == "Output:":
            if running or code is None:
                return False, "unknown"
            return code != 0, None
        if line.startswith(EXEC_RUNNING):
            running = True
        elif line.startswith(EXEC_EXITED):
            digits = line[len(EXEC_EXITED):]
            digits = digits[1:] if digits.startswith("-") else digits
            if digits.isascii() and digits.isdigit() and len(digits) <= EXEC_CODE_DIGITS:
                code = int(line[len(EXEC_EXITED):])
        if end < 0:
            break
        start = end + 1
    return False, "unknown"


def _measurement_bridge(payload, *, aggregate=False, validate_reviews=False, ledger=False):
    """Run one export of the measurement kernel in Node. A measurement (not an aggregate or a review check) first awaits the kernel's
    loadShellParser(), as the kernel's own CLI does: the CLI-lane reading needs a verified tree-sitter-bash install (the directory
    order is CHILD_USAGE_SHELL_PARSER, then the ecosystem tools directory that shell-parser.pin.json names), and without one the
    measurement reports cli_lanes as parser_unavailable and counts no lane. ledger asks for callLedger(rows, {window}) instead of
    measureTranscript, after the same load, as U2's CLI loads the parser before it writes its ledger (child-usage.mjs:3448-3465
    at b2dd1eb7)."""
    export = ("validateExceptions" if validate_reviews else "aggregateMeasurements" if aggregate
              else "callLedger" if ledger else "measureTranscript")
    load = "" if aggregate or validate_reviews else "await loadShellParser(); "
    script = ("import {readFileSync} from 'node:fs'; import {" + export + ("" if aggregate or validate_reviews else ", loadShellParser")
              + "} from " + json.dumps(MEASUREMENT_MODULE.as_uri()) + "; const x=JSON.parse(readFileSync(0,'utf8')); " + load
              + "process.stdout.write(JSON.stringify(" + export
              + ("(x)" if aggregate or validate_reviews else "(x.rows,x.options)") + ")); ")
    try:
        result = subprocess.run(["node", "--input-type=module", "-e", script],
                                input=json.dumps(payload), capture_output=True, text=True,
                                timeout=300, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ValueError("PR-A measurement requires the repository Node module") from error
    if result.returncode:
        # Never echo stderr: it could contain private transcript input.
        raise ValueError("PR-A Node measurement failed")
    return json.loads(result.stdout)


def kernel_exports(name: str) -> bool:
    """Whether the measurement kernel exports a function called name. --call-ledger needs callLedger, PR-A U2's export
    (CODEX_CALL_LEDGER_SCHEMA above), and a kernel without it cannot give a call's state, so the ledger is refused, never
    written from another source. A Node failure reads as False."""
    script = ("import * as kernel from " + json.dumps(MEASUREMENT_MODULE.as_uri())
              + "; process.stdout.write(typeof kernel[" + json.dumps(name) + "])")
    try:
        result = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True,
                                timeout=120, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0 and result.stdout == "function"


def m4_unread(commands: dict, code_mode: dict) -> bool:
    """Whether fetches may have run where they cannot be read, so M4 is incomplete for the actor or group (the U3 review):
    an unresolved command (codex_commands non_posix_shell, unknown_shell), a legacy unobservable exec span, or an outer
    HTTP_SCRIPT mention in a code-mode isolate that was not read. The kernel's aggregate recomputes M4 status from its
    counts, so a group applies this again to its sums."""
    return bool(commands["non_posix_shell"] + commands["unknown_shell"] + code_mode["legacy_unobservable_exec_calls"]
                + code_mode["outer_http_unverified_exec_calls"])


def measure_codex_records(records, *, since=None, until=None, rtk_check=False, exceptions=None,
                          marker=DEFAULT_LANES_MARKER, call_ledger=None):
    """Local transcript measurement, not a provider run. Parent copies establish the
    cumulative usage baseline but never contribute calls/results. Preserve unknowns.

    Source: ccusage/ccusage v20.0.24 rust/adapters/codex/src/parser.rs:153-246,318-346.
    Difference cumulative totals, never sum turn.completed thread totals or subsets.

    codex_hook_context counts developer content items of kind hooks.additional_context (PR-A 10a): own items
    (inserted, with_marker) in the window of their own record, and items copied from the parent (inherited,
    inherited_with_marker) once, in the window of the child's first own record (ordinal at or above the start), so
    adjacent windows add up. A window whose records are all copied is not measured, since scan_lanes_file measures a
    session only with a counted record; but scan_lanes_file counts the child's own first session_meta, read before the
    start ordinal is known, while here its ordinal (below the start) reads as copied, so a window that holds it and copied
    records only is measured and counts nothing. The kernel's hook_context counts Claude hook attachments only.

    code_mode (PR-A 10e) reads the first session_meta: a history_mode other than paginated, or none (the upstream default,
    protocol/src/protocol.rs:772-779), or no session_meta at all, is legacy, and a cli_version outside
    NO_NETWORK_ISOLATE_CLIENTS, or none, is a client whose code-mode isolate was not read.

    call_ledger, a list, receives the private codex-call-ledger/1 records (binding correction 1 of the U3 build): the
    kernel's callLedger over the same rows and window as the measurement, one record per call it counts, in row order. A
    call id is the adapter's key: the response_item call_id (else its id), or the item_completed item.id of a
    CommandExecution, McpToolCall or web.search item, so a code-mode exec and a command its JavaScript ran are two calls; a
    key the adapter made up for a record without an id (missing-N), or one that is not a string, is null. thread_id and
    owner_kind come from the first session_meta (its id, and codex_session_kind; no session_meta gives null), and
    history_mode is the mode this function reads (paginated, else legacy). Nothing of it enters the returned measurement.
    """
    start = next((r.get("payload", {}).get("subagent_history_start_ordinal") for r in records
                  if r.get("type") == "session_meta"), None)
    child = isinstance(start, int) and not isinstance(start, bool)
    meta = next((r.get("payload") for r in records if r.get("type") == "session_meta"), None)
    meta = meta if isinstance(meta, dict) else {}
    paginated = meta.get("history_mode") == "paginated"
    isolate_read = isinstance(meta.get("cli_version"), str) and meta["cli_version"] in NO_NETWORK_ISOLATE_CLIENTS
    normalized, visible, visible_at = [], [], []
    previous = None if child else dict.fromkeys(CODEX_COUNTERS, 0)
    totals = dict.fromkeys(CODEX_COUNTERS, 0)
    snapshots = duplicates = gaps = 0
    attempts, active = [], None
    model = effort = None
    hooks = dict.fromkeys(HOOK_CONTEXT_COUNTERS, 0)
    first_own_at = None

    def attempt():
        nonlocal active
        if active is None:
            active = {"ordinal": len(attempts) + 1, "state": "unfinished", "snapshots": 0,
                      "configured_model": model, "effort": effort, "max_request_input_tokens": None,
                      "usage": dict.fromkeys(CODEX_COUNTERS, 0)}
            attempts.append(active)
        return active

    for record in records:
        try:
            at = parse_iso(record.get("timestamp"))
        except (ValueError, TypeError, AttributeError):
            gaps += 1
            continue
        if until is not None and at >= until:
            continue
        p = record.get("payload") or {}
        inherited = child and isinstance(record.get("ordinal"), int) and record["ordinal"] < start
        counted = not inherited and (since is None or at >= since)
        if not inherited:
            visible.append(record)
            visible_at.append(at)
            if first_own_at is None:
                first_own_at = at
        if (record.get("type") == "response_item" and isinstance(p, dict) and p.get("type") == "message"
                and p.get("role") == "developer" and (inherited or counted)):
            for text, kind in message_items(p):
                if kind == HOOK_CONTEXT_KIND:
                    hooks["inherited" if inherited else "inserted"] += 1
                    hooks["inherited_with_marker" if inherited else "with_marker"] += marker in text
        if record.get("type") == "turn_context":
            model = model_key(p.get("model"))
            effort = effort_key(p.get("effort", p.get("reasoning_effort")))
            if counted and active is not None and not active["snapshots"]:
                active["configured_model"], active["effort"] = model, effort
        if record.get("type") != "event_msg":
            continue
        event = p.get("type")
        if counted and event == "task_started":
            active = None
            attempt()
        elif counted and event in ("task_complete", "task_completed", "turn_completed", "turn_failed", "turn_aborted"):
            attempt()["state"] = "failed" if event == "turn_failed" or p.get("error") is not None else "interrupted" if event == "turn_aborted" else "completed"
            active = None
        elif event == "token_count":
            info = p.get("info") if isinstance(p.get("info"), dict) else {}
            current = info.get("total_token_usage")
            if not isinstance(current, dict):
                if counted:
                    gaps += 1
                continue
            if current == previous:
                if counted:
                    duplicates += 1
                continue
            if counted:
                a = attempt()
                a["snapshots"] += 1
                snapshots += 1
                for key in CODEX_COUNTERS:
                    n, before = current.get(key), previous.get(key) if previous else None
                    delta = (n - before if type(n) is int and type(before) is int and n >= before else None)
                    for target in (totals, a["usage"]):
                        target[key] = target[key] + delta if target[key] is not None and delta is not None else None
                if any(v is None for k, v in a["usage"].items() if k not in OPTIONAL_CODEX_COUNTERS):
                    gaps += 1
                # The request's own input tokens (TokenUsageInfo.last_token_usage, protocol.rs:2268-2275), for the
                # long-context tier: the attempt's largest over its counted snapshots (binding correction 4).
                last = info.get("last_token_usage")
                request = last.get("input_tokens") if isinstance(last, dict) else None
                if type(request) is int and (a["max_request_input_tokens"] is None or request > a["max_request_input_tokens"]):
                    a["max_request_input_tokens"] = request
            previous = current

    # Prefer returned response_item bytes over the UI item's aggregate if both persist.
    output_ids = {r.get("payload", {}).get("call_id") for r in visible if r.get("type") == "response_item"
                  and r.get("payload", {}).get("type") in ("function_call_output", "custom_tool_call_output")}
    failed_ids = {r.get("payload", {}).get("item", {}).get("id") for r in visible
                  if r.get("type") == "event_msg" and r.get("payload", {}).get("type") == "item_completed"
                  and r.get("payload", {}).get("item", {}).get("status") == "failed"}
    # A declined command never ran: events.rs:562-573 ends a rejected exec with exit -1 and status declined.
    declined_ids = {r.get("payload", {}).get("item", {}).get("id") for r in visible
                    if r.get("type") == "event_msg" and r.get("payload", {}).get("type") == "item_completed"
                    and r.get("payload", {}).get("item", {}).get("status") == "declined"}
    item_states = {r["payload"]["item"].get("id"): r["payload"]["item"].get("status") for r in visible
                   if r.get("type") == "event_msg" and r.get("payload", {}).get("type") == "item_completed"
                   and isinstance(r.get("payload", {}).get("item"), dict)}
    # The model's own web_search_call response item carries the search's status (in_progress, searching, completed or failed); the
    # web.search Extension item that ends it has none, so a failed hosted search must not read as completed below.
    hosted_search_failed = {r["payload"].get("id") for r in visible
                            if r.get("type") == "response_item" and r.get("payload", {}).get("type") == "web_search_call"
                            and r.get("payload", {}).get("status") == "failed"}
    model_call_ids = {r["payload"].get("call_id") or r["payload"].get("id") for r in visible
                      if r.get("type") == "response_item" and r.get("payload", {}).get("type") in MODEL_CALL_TYPES}
    shell_call_ids = {r["payload"].get("call_id") or r["payload"].get("id") for r in visible
                      if r.get("type") == "response_item" and (
                          r.get("payload", {}).get("type") == "local_shell_call"
                          or (r.get("payload", {}).get("type") == "function_call"
                              and codex_call_name(r["payload"]).rsplit(".", 1)[-1] in CODEX_SHELL_TOOLS))}

    def result_state(key, output) -> dict:
        """The kernel's is_error and native_state for a call's model-visible output: a persisted item state
        decides when there is one; otherwise a shell call's unified exec header does (exec_header_state)."""
        if key in declined_ids:
            return {"is_error": True, "native_state": "declined"}
        if key in failed_ids:
            return {"is_error": True}
        if key in shell_call_ids and item_states.get(key) is None:
            failed, state = exec_header_state(output)
            return {"is_error": failed, **({"native_state": state} if state else {})}
        return {"is_error": False}

    def arguments(value):
        if isinstance(value, dict):
            return value
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except (ValueError, TypeError):
            return {}

    def emit(r, block, role):
        normalized.append({"type": role, "timestamp": r["timestamp"], "message": {"content": [block]}})

    # PR-A U3 normalization: codex_commands counts a call once, at its first record, inside [since, until), as the kernel
    # keeps a call's first tool_use; an emitted call's record decides before a skipped item with the same id.
    commands = dict.fromkeys(CODEX_COMMAND_STATES, 0)
    emitted, skipped = set(), set()
    made_up = set()  # the missing-N keys of records without an id, which the call ledger writes as null

    def count_command(at, state):
        if state is not None and (since is None or at >= since):
            commands[state] += 1

    def use(r, at, key, name, inputs, *, sandbox=False, code_mode=False, command=None):
        """Emit a tool_use. A shell call (a CODEX_SHELL_TOOLS function call, or command, the (text, state) of
        resolve_command) becomes a Bash call whose command is its text, '' when unresolved."""
        if command is None and name.rsplit(".", 1)[-1] in CODEX_SHELL_TOOLS:
            command = resolve_shell_call(inputs)
        if command is not None:
            name, inputs = "Bash", {"command": command[0]}
            if key not in emitted:
                count_command(at, command[1])
        emitted.add(key)
        emit(r, {"type": "tool_use", "id": key, "name": name, "input": inputs,
                 "sandbox": sandbox, "code_mode": code_mode, "native_status": item_states.get(key)}, "assistant")

    # PR-A 10e (U3 design section 7 with its review): openai/codex rust-v0.157.1 models.rs:1060-1165,1938-1949 and
    # core/tests/suite/code_mode.rs:721-760,3436-3752: nested returns go to JS and only the outer custom output is
    # model-visible; UI item IDs can differ. A cell keeps running after its exec returns (yield_control, and the wait tool
    # that resumes it: code-mode-protocol/src/description.rs:19-51, lib.rs:51-52), so with no explicit parent field an
    # emitted item (a model-called CommandExecution, an McpToolCall or a web.search Extension) is nested when its id is no
    # model call id and an own exec call came earlier in its turn (TURN_EVENTS end a turn); otherwise it is direct, and one
    # with no model call id counts in code_mode.unattributed_items. A wait call without a namespace after an exec of its turn
    # is code mode, since its output is the cell's. Direct response IDs win. code_mode counts a call or an item once, at its
    # first record inside [since, until), as codex_commands does, so adjacent windows add up.
    # Commit 8: an exec counted here, in a rollout that is not paginated, whose code has a static fetch-capable site
    # (code_mode_fetch_sites) and to which no nested item is attributed (an item nested after it and before the next exec
    # call or the turn's end) is an unobservable span; the outer code is never a fetch where the isolate was read
    # (NO_NETWORK_ISOLATE_CLIENTS), so its HTTP_SCRIPT mentions are only counted, and elsewhere they make M4 incomplete.
    code_mode_counts = dict.fromkeys(CODE_MODE_COUNTERS, 0)
    code_mode_seen = set()
    legacy_sites, items_of = {}, {}  # counted legacy exec -> its sites; exec -> its attributed nested items

    def count_code_mode(at, key, counter) -> bool:
        if key in code_mode_seen:
            return False
        code_mode_seen.add(key)
        if since is not None and at < since:
            return False
        code_mode_counts[counter] += 1
        return True

    turn_exec = None  # the latest own exec call of the current turn
    for index, r in enumerate(visible):
        p = r.get("payload") or {}
        at = visible_at[index]
        if r.get("type") == "response_item":
            kind, key = p.get("type"), p.get("call_id") or p.get("id")
            if not key:
                key = f"missing-{index}"
                made_up.add(key)
            if kind in ("function_call", "custom_tool_call"):
                name = codex_call_name(p)
                exec_call = kind == "custom_tool_call" and name.rsplit(".", 1)[-1] == "exec"
                wait_call = (kind == "function_call" and turn_exec is not None and p.get("name") == CODE_MODE_WAIT
                             and not p.get("namespace"))
                if exec_call:
                    turn_exec = key
                    if count_code_mode(at, ("call", key), "exec_calls"):
                        code = p.get("input") if isinstance(p.get("input"), str) else ""
                        mentions = http_script_mentions(code)
                        code_mode_counts["outer_http_mentions"] += mentions
                        code_mode_counts["outer_http_unverified_exec_calls"] += bool(mentions) and not isolate_read
                        if not paginated:
                            legacy_sites[key] = code_mode_fetch_sites(code)
                elif wait_call:
                    count_code_mode(at, ("call", key), "wait_calls")
                inputs = arguments(p.get("arguments")) if kind == "function_call" else {"code": p.get("input", "")}
                use(r, at, key, name, inputs, code_mode=exec_call or wait_call)
            elif kind == "local_shell_call":
                use(r, at, key, "Bash", {}, command=resolve_command((p.get("action") or {}).get("command")))
            elif kind in ("function_call_output", "custom_tool_call_output"):
                emit(r, {"type": "tool_result", "tool_use_id": key, "content": p.get("output"),
                         **result_state(key, p.get("output"))}, "user")
        elif r.get("type") == "event_msg" and p.get("type") == "item_completed":
            item = p.get("item") or {}
            key = item.get("id", f"missing-{index}")
            if "id" not in item:
                made_up.add(key)
            kind = item.get("type")
            direct = key in model_call_ids
            sandbox = turn_exec is not None and not direct
            # Only an emitted item (a tool_use below) without a model call id is nested or unattributed (the review's item kinds).
            attributed = None if direct else "nested_items" if sandbox else "unattributed_items"
            output, has_output, used = None, False, False
            if kind == "CommandExecution":
                source = item.get("source")
                skip = SKIPPED_COMMAND_SOURCES.get(source) if isinstance(source, str) else None
                if skip is not None:
                    # A user's own shell command (core/src/tasks/user_shell.rs:190-205), whose output is recorded as a
                    # conversation item, not a tool result (:453-481), and an interaction item (no core code sets that source
                    # at rust-v0.157.1, so this is conservative) are no model tool calls: neither a tool_use nor a result.
                    if key not in emitted and key not in skipped:
                        count_command(at, skip)
                    skipped.add(key)
                    continue
                use(r, at, key, "Bash", {}, sandbox=sandbox, command=resolve_command(item.get("command")))
                used = True
                output = item.get("aggregated_output")
                has_output = output is not None
            elif kind == "McpToolCall":
                use(r, at, key, "mcp__" + str(item.get("server", "unknown")) + "__" + str(item.get("tool", "unknown")), arguments(item.get("arguments")), sandbox=sandbox)
                used = True
                value = item.get("result")
                output = value.get("content", value) if isinstance(value, dict) else value
                has_output = output is not None
            elif kind == "Extension" and item.get("kind") == "web.search":
                action = item.get("action") or {}
                # A web.search item has no status field (WebSearchItem is {id, query, action, results}, openai/codex rust-v0.157.1
                # protocol/src/items.rs:372-381) and no result is emitted for it, so its item_completed event is its completion.
                if item_states.get(key) is None:
                    item_states[key] = "failed" if key in hosted_search_failed else "completed"
                use(r, at, key, "WebFetch" if action.get("type") == "openPage" else "WebSearch", {"url": action.get("url")}, sandbox=sandbox)
                used = True
            if used and attributed:
                count_code_mode(at, ("item", key), attributed)
                if sandbox:
                    items_of[turn_exec] = items_of.get(turn_exec, 0) + 1
            if has_output and key not in output_ids:
                status = item.get("status")
                emit(r, {"type": "tool_result", "tool_use_id": key, "content": output,
                         "is_error": status in ("failed", "declined"),
                         **({"native_state": "declined"} if status == "declined" else {})}, "user")
        elif r.get("type") == "event_msg" and p.get("type") in TURN_EVENTS:
            turn_exec = None
    for key, sites in legacy_sites.items():
        if sites and not items_of.get(key):
            code_mode_counts["legacy_unobservable_exec_calls"] += 1
            code_mode_counts["legacy_unobservable_sites"] += sites
    window = {"since": since.timestamp() * 1000 if since else -8640000000000000,
              "until": until.timestamp() * 1000 if until else 8640000000000000}
    # PR-A U3 10d: replay asks rtk what the held Codex hook would decide (`rtk hook check --agent codex`, which no Claude
    # permission rule reaches), and the kernel adds rtk_parts.d7 for it.
    # An unresolved command's text is '' in the rows (its fetches cannot be read, so M4 cannot be measured or not_applicable: the U3
    # review, m4_unread below); rtk 0.50.0 answers "No rewrite for:" for it under either agent, so replay would read a parts-free
    # measured call. The kernel counts each as an unknown call (unresolvedBash), so B8's rule, unknown_call_share and the strict D7
    # status come from one place.
    unresolved = commands["non_posix_shell"] + commands["unknown_shell"]
    measured = _measurement_bridge({"rows": normalized, "options": {
        "window": window, "rtkCheck": rtk_check, "exceptions": exceptions or {}, "rtkAgent": CODEX_RTK_AGENT,
        "unresolvedBash": unresolved}})
    # Claude per-message fields are inapplicable to Codex cumulative native counters.
    measured.pop("usage", None)
    measured["rtk_parts"]["agent"] = CODEX_RTK_AGENT
    measured["codex_commands"] = commands
    measured["code_mode"] = code_mode_counts
    if m4_unread(commands, code_mode_counts):
        measured["m4"]["status"] = "incomplete"
    if first_own_at is None or (since is not None and first_own_at < since):
        hooks["inherited"] = hooks["inherited_with_marker"] = 0  # copied items count in the window of the first own record
    measured["codex_hook_context"] = hooks
    measured["provider_usage"] = {"totals": totals if snapshots else dict.fromkeys(CODEX_COUNTERS),
        "attempts": attempts, "snapshots": snapshots, "duplicate_snapshots": duplicates, "gaps": gaps,
        "complete": bool(snapshots) and not gaps and all(a["state"] == "completed" and a["snapshots"] for a in attempts)}
    if call_ledger is not None:
        # Binding correction 1: the kernel's callLedger over the rows and window measureTranscript read, so the ledger holds
        # exactly the calls the measurement counts.
        head = {"schema": CODEX_CALL_LEDGER_SCHEMA, "thread_id": meta.get("id") if isinstance(meta.get("id"), str) else None}
        owner_kind = (codex_session_kind(meta) if any(r.get("type") == "session_meta" for r in records) else None)
        history_mode = "paginated" if paginated else "legacy"
        for record in _measurement_bridge({"rows": normalized, "options": {"window": window}}, ledger=True):
            key = record.get("tool_use_id")
            call_ledger.append({**head, "call_id": key if isinstance(key, str) and key not in made_up else None,
                                "owner_kind": owner_kind, **{field: record.get(field) for field in LEDGER_CALL_FIELDS},
                                "history_mode": history_mode})
    return measured


def _new_lanes_session() -> dict:
    return {"kind": None, "role": "(root)", "originator": None, "history_mode": None, "marker": False, "marker_inherited": False,
            "marker_injected": False, "marker_injected_kinds": {}, "catalog_off": False,
            "catalog_on": False, "in_window": False, "started_before_window": False,
            "ran_past_window_end": False, "tool_calls": 0, "mcp_calls": {}, "mcp_failed": {},
            "shell_calls": 0, "rtk_prefixed": 0, "fetch": dict.fromkeys(FETCH_KEYS, 0),
            "skill_md_reads": {}, "function_calls": {}, "file_changes": 0,
            "first_prompt_tokens": None, "own_model_calls": 0, "own_tool_items": 0,
            # PR-A 10g private join facts (never published; scan_codex_lanes publishes states only): ids, the task path and the
            # raw role of the first session_meta, whether history was forked, own turns, own spawn_agent calls, started items,
            # turn routes, the first own settings snapshot and follow-up targets.
            "_thread_id": None, "_parent_thread_id": None, "_agent_path": None, "_role_raw": None,
            "_history_start": False, "_turns": 0, "_spawns": {}, "_activity": {}, "_routes": [], "_settings": None,
            "_followups": []}


def _bump(counts: dict, key: str, by: int = 1) -> None:
    counts[key] = counts.get(key, 0) + by


# The spawn_agent arguments the join reads (SpawnAgentArgs, spawn.rs:253-263; V1's fork_context, multi_agents_spec.rs:607-613);
# the message and task name are never kept.
SPAWN_ARGUMENTS = ("fork_turns", "fork_context", "agent_type", "model", "reasoning_effort")


def _collect_spawn_facts(session: dict, kind, payload: dict, route):
    """PR-A 10g: one own record's private spawn facts, whatever its time before until (a spawn made before since still joins
    a child inside the window); returns the route of the latest own turn context. Records a forked child copied from its
    parent never reach here: they are the parent's. Sources, openai/codex rust-v0.157.1: TurnContextItem model and effort
    (protocol/src/protocol.rs:3328, :3344-3345); a spawn_agent call (spawn.rs:253-263) and the SubAgentActivity started item
    whose id is its call_id (spawn.rs:216-226, protocol/src/items.rs:364-370, kind snake_case at protocol.rs:4382-4390);
    ThreadSettingsApplied, whose copied snapshots keep their owner's thread_id (protocol.rs:2192-2231); followup_task's
    target (an agent id or canonical task name) and V1 resume_agent's id (multi_agents_spec.rs:217-266); task_started, also
    read as turn_started (protocol.rs:1403-1406)."""
    def text(value):  # ids, targets and route values are strings; any other JSON value is unknown
        return value if isinstance(value, str) else None
    if kind == "turn_context":
        route = (text(payload.get("model")), text(payload.get("effort", payload.get("reasoning_effort"))))
        session["_routes"].append(route)
    elif kind == "response_item" and payload.get("type") == "function_call":
        name = codex_call_name(payload)
        if name == "spawn_agent" and text(payload.get("call_id")) is not None:
            arguments = _call_arguments(payload.get("arguments"))
            session["_spawns"].setdefault(payload["call_id"], {
                "arguments": {key: arguments[key] for key in SPAWN_ARGUMENTS if key in arguments},
                "namespace": payload.get("namespace"), "route": route})
        elif name in ("followup_task", "resume_agent"):
            target = text(_call_arguments(payload.get("arguments")).get("target" if name == "followup_task" else "id"))
            if target is not None:
                session["_followups"].append(target)
    elif kind == "event_msg":
        event = payload.get("type")
        item = payload.get("item") if isinstance(payload.get("item"), dict) else {}
        if event in ("task_started", "turn_started"):
            session["_turns"] += 1
        elif event == "item_completed" and item.get("type") == "SubAgentActivity" and item.get("kind") == "started":
            if text(item.get("agent_thread_id")) is not None and text(item.get("id")) is not None:
                session["_activity"].setdefault(item["agent_thread_id"], {"id": item["id"], "route": route})
        elif (event == "thread_settings_applied" and session["_settings"] is None and session["_thread_id"] is not None
              and payload.get("thread_id") == session["_thread_id"]):
            settings = payload.get("thread_settings") if isinstance(payload.get("thread_settings"), dict) else {}
            session["_settings"] = (settings.get("model"), settings.get("reasoning_effort"))
    return route


def scan_lanes_file(path: Path, names, *, since, until, marker: str,
                    codex_off, codex_on, rtk_check=False, exception_records=(), call_ledger=False) -> tuple[dict, int, int]:
    """One rollout file -> (session lanes, parse errors, records without a timestamp). With call_ledger, a measured
    session keeps its private call ledger records (measure_codex_records) in session["_call_ledger"].

    A spawned sub-agent's rollout starts with records copied from its parent: those whose ordinal
    is below session_meta.subagent_history_start_ordinal. They count toward session properties
    (the marker and the catalog are part of the child's context) but never as the child's calls.
    A tool call is a function_call record or a tool item_completed event, one call per id (a
    function_call's call_id is its item's id), and counts in the window of its first record before
    until, like child-usage.mjs tool_use ids: a call requested before since and completed inside
    is not counted again, so adjacent windows add up. Its shell, MCP and fetch lanes come from the
    item_completed event and count in that event's window."""
    session = _new_lanes_session()
    parse_errors = untimed = 0
    first_usage_seen = False
    history_start = None
    call_ids: set = set()
    metric_records = []
    route = (None, None)  # the latest own turn context's (model, effort), raw

    def first_record(call_id) -> bool:
        """Whether a record is its call's first (a record without an id is a call of its own)."""
        if call_id is None:
            return True
        if call_id in call_ids:
            return False
        call_ids.add(call_id)
        return True

    def catalog(text: str) -> None:
        session["catalog_off"] |= any(f"/{name}/SKILL.md" in text for name in codex_off)
        session["catalog_on"] |= any(f"/{name}/SKILL.md" in text for name in codex_on)

    try:
        handle = path.open(encoding="utf-8", errors="replace")
    except OSError:
        return session, 1, 0
    with handle:
        for raw_line in handle:
            if not raw_line.strip():
                continue
            try:
                record = json.loads(raw_line)
                if not isinstance(record, dict):
                    raise ValueError("rollout line is not a JSON object")
            except ValueError:
                parse_errors += 1
                continue
            metric_records.append(record)
            try:
                when = parse_iso(record["timestamp"]) if isinstance(record.get("timestamp"), str) else None
            except ValueError:
                when = None
            if when is None:
                untimed += 1
                continue
            if until is not None and when >= until:
                session["ran_past_window_end"] = True
                continue
            kind = record.get("type")
            payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
            inherited = (history_start is not None and isinstance(record.get("ordinal"), int)
                         and record["ordinal"] < history_start)
            counted = (since is None or when >= since) and not inherited
            session["in_window"] |= counted
            for text in catalog_texts(record):
                catalog(text)
            if kind == "session_meta":
                if session["kind"] is None:  # a sub-agent rollout repeats its parent's meta second
                    session["kind"] = codex_session_kind(payload)
                    session["role"] = session_role(payload, session["kind"])
                    session["originator"] = safe_key(payload["originator"]) if payload.get("originator") else "(none)"
                    session["history_mode"] = (safe_key(payload["history_mode"]) if payload.get("history_mode")
                                               else "(none)")
                    session["started_before_window"] = since is not None and when < since
                    start = payload.get("subagent_history_start_ordinal")
                    history_start = start if isinstance(start, int) and not isinstance(start, bool) else None
                    spawn_source = thread_spawn_source(payload)
                    session["_thread_id"] = payload.get("id") if isinstance(payload.get("id"), str) else None
                    parent_id = spawn_source.get("parent_thread_id")
                    session["_parent_thread_id"] = parent_id if isinstance(parent_id, str) else None
                    agent_path = payload.get("agent_path") or spawn_source.get("agent_path")
                    session["_agent_path"] = agent_path if isinstance(agent_path, str) else None
                    session["_role_raw"] = session_role_raw(payload)
                    session["_history_start"] = history_start is not None
            elif kind == "response_item":
                payload_type = payload.get("type")
                if payload_type in CALL_PAYLOAD_TYPES and not inherited:
                    session["own_model_calls"] += 1
                new_call = payload_type == "function_call" and not inherited and first_record(payload.get("call_id"))
                if payload_type == "message" and payload.get("role") == "developer":
                    session["marker"] |= marker in message_text(payload)
                    # PR-A 10a: split by content item, inherited (a record copied from the parent) or injected (the
                    # session's own), with the injected item's content kind.
                    for text, kind in message_items(payload):
                        if marker not in text:
                            continue
                        if inherited:
                            session["marker_inherited"] = True
                        else:
                            session["marker_injected"] = True
                            _bump(session["marker_injected_kinds"], "(none)" if kind is None else safe_key(kind))
                elif counted and payload_type in CALL_PAYLOAD_TYPES:
                    for name in skillmd_hits(payload, names):
                        _bump(session["skill_md_reads"], name)
                    if payload_type == "function_call":
                        session["tool_calls"] += new_call
                        _bump(session["function_calls"], safe_key(payload["name"]) if payload.get("name") else "(none)")
            elif kind == "event_msg" and not inherited:
                payload_type = payload.get("type")
                item = payload.get("item") if isinstance(payload.get("item"), dict) else {}
                tool_item = payload_type == "item_completed" and item.get("type") in TOOL_ITEM_TYPES
                new_call = tool_item and first_record(item.get("id"))
                if tool_item:
                    session["own_tool_items"] += 1
                if payload_type == "token_count" and not first_usage_seen:
                    info = payload.get("info") if isinstance(payload.get("info"), dict) else {}
                    last = info.get("last_token_usage") if isinstance(info.get("last_token_usage"), dict) else {}
                    if isinstance(last.get("input_tokens"), int):
                        first_usage_seen = True
                        if counted:
                            session["first_prompt_tokens"] = last["input_tokens"]
                elif payload_type == "item_completed" and counted:
                    _score_lane_item(session, item, new_call)
            if not inherited:
                route = _collect_spawn_facts(session, kind, payload, route)
    if session["in_window"]:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        # Only counts leave the public report. Binding is per sidecar record,
        # once across all measured rollouts, not once per matching actor.
        session["_sidecar_record_indices"] = [i for i, r in enumerate(exception_records)
                                               if r["transcript_sha256"] == digest]
        exceptions = {r["tool_use_id"]: r for r in exception_records if r["transcript_sha256"] == digest}
        ledger = [] if call_ledger else None
        session["measurement"] = measure_codex_records(metric_records, since=since, until=until,
                                                       rtk_check=rtk_check, exceptions=exceptions, marker=marker,
                                                       call_ledger=ledger)
        if ledger is not None:
            session["_call_ledger"] = ledger
        session["measurement"]["parse_errors"] = parse_errors
        if parse_errors or untimed:
            session["measurement"]["provider_usage"]["complete"] = False
            session["measurement"]["bytes_complete"] = False
    return session, parse_errors, untimed


def _score_lane_item(session: dict, item: dict, new_call: bool) -> None:
    """One item_completed event inside the window: its lane, and a tool call when the event is its
    call's first record."""
    item_type = item.get("type")
    if item_type in TOOL_ITEM_TYPES:
        session["tool_calls"] += new_call
    if item_type == "McpToolCall":
        server = safe_key(item["server"]) if item.get("server") else "(none)"
        _bump(session["mcp_calls"], server)
        if item.get("status") == "failed":
            _bump(session["mcp_failed"], server)
        if item.get("tool") == "ctx_fetch_and_index":
            session["fetch"]["ctx_fetch_and_index"] += 1
    elif item_type == "CommandExecution":
        session["shell_calls"] += 1
        script = shell_script(item.get("command"))
        if RTK_FIRST_WORD.match(script):
            session["rtk_prefixed"] += 1
        kind = fetch_kind(script)
        if kind:
            session["fetch"]["shell_curl_wget_loopback" if kind == "loopback" else "shell_curl_wget"] += 1
    elif item_type == "Extension":
        action = item.get("action") if isinstance(item.get("action"), dict) else {}
        if item.get("kind") == "web.search":
            action_type = action.get("type")
            session["fetch"]["web_open_page" if action_type == "openPage" else
                             "web_search" if action_type == "search" else "web_other"] += 1
    elif item_type == "FileChange":
        session["file_changes"] += 1


def token_stats(values) -> dict:
    """Nearest-rank percentiles of the numbers in values (None entries are ignored)."""
    ordered = sorted(value for value in values if isinstance(value, int))
    if not ordered:
        return {"n": 0, "min": None, "p10": None, "median": None, "p90": None, "max": None}

    def rank(percent: int) -> int:  # the ceil(percent * n / 100)-th smallest, in integer arithmetic
        return ordered[max(0, -(-percent * len(ordered) // 100) - 1)]
    return {"n": len(ordered), "min": ordered[0], "p10": rank(10), "median": rank(50),
            "p90": rank(90), "max": ordered[-1]}


def _share(part: int, whole: int):
    return round(part / whole, 4) if whole else None


def aggregate_codex_lanes(sessions: list[dict]) -> dict:
    out = {"sessions": len(sessions), "tool_calls": 0, "mcp_calls": {}, "mcp_failed": {},
           "sessions_using_mcp_server": {}, "shell_calls": 0, "rtk_prefixed_shell_calls": 0,
           "rtk_prefix_share": None, "fetch": {**dict.fromkeys(FETCH_KEYS, 0), "ctx_fetch_and_index_share": None},
           "skill_md_reads": {}, "sessions_with_skill_md_read": 0, "function_calls": {},
           "file_changes": 0, "marker_sessions": 0, "marker_inherited_sessions": 0, "marker_injected_sessions": 0,
           "marker_inherited_only_sessions": 0, "marker_injected_by_kind": {}, "first_prompt_tokens": None}
    for session in sessions:
        out["tool_calls"] += session["tool_calls"]
        for server, count in session["mcp_calls"].items():
            _bump(out["mcp_calls"], server, count)
            _bump(out["sessions_using_mcp_server"], server)
        for server, count in session["mcp_failed"].items():
            _bump(out["mcp_failed"], server, count)
        out["shell_calls"] += session["shell_calls"]
        out["rtk_prefixed_shell_calls"] += session["rtk_prefixed"]
        for key in FETCH_KEYS:
            out["fetch"][key] += session["fetch"][key]
        for name, count in session["skill_md_reads"].items():
            _bump(out["skill_md_reads"], name, count)
        out["sessions_with_skill_md_read"] += bool(session["skill_md_reads"])
        for name, count in session["function_calls"].items():
            _bump(out["function_calls"], name, count)
        out["file_changes"] += session["file_changes"]
        out["marker_sessions"] += session["marker"]
        out["marker_inherited_sessions"] += session["marker_inherited"]
        out["marker_injected_sessions"] += session["marker_injected"]
        out["marker_inherited_only_sessions"] += session["marker_inherited"] and not session["marker_injected"]
        for kind, count in session["marker_injected_kinds"].items():  # content items, not sessions
            _bump(out["marker_injected_by_kind"], kind, count)
    fetch = out["fetch"]
    out["rtk_prefix_share"] = _share(out["rtk_prefixed_shell_calls"], out["shell_calls"])
    fetch["ctx_fetch_and_index_share"] = _share(
        fetch["ctx_fetch_and_index"], fetch["web_open_page"] + fetch["ctx_fetch_and_index"] + fetch["shell_curl_wget"])
    out["first_prompt_tokens"] = token_stats(session["first_prompt_tokens"] for session in sessions)
    measurements = [session["measurement"] for session in sessions if "measurement" in session]
    if measurements:
        out["measurement"] = _measurement_bridge(measurements, aggregate=True)
        out["measurement"].pop("usage", None)
        out["measurement"]["rtk_parts"]["agent"] = CODEX_RTK_AGENT
        out["measurement"]["provider_usage"] = {
            "complete": all(m["provider_usage"]["complete"] for m in measurements),
            "totals": {key: (sum(m["provider_usage"]["totals"][key] for m in measurements)
                              if all(m["provider_usage"]["totals"][key] is not None for m in measurements) else None)
                       for key in CODEX_COUNTERS}}
        out["measurement"]["codex_hook_context"] = {key: sum(m["codex_hook_context"][key] for m in measurements)
                                                    for key in HOOK_CONTEXT_COUNTERS}
        commands = {key: sum(m["codex_commands"][key] for m in measurements) for key in CODEX_COMMAND_STATES}
        out["measurement"]["codex_commands"] = commands
        out["measurement"]["code_mode"] = {key: sum(m["code_mode"][key] for m in measurements) for key in CODE_MODE_COUNTERS}
        if m4_unread(commands, out["measurement"]["code_mode"]):
            out["measurement"]["m4"]["status"] = "incomplete"  # aggregateMeasurements recomputes it from the counts
    return out


def user_config_state(session: dict) -> str:
    return "ignored" if session["catalog_off"] else "applied" if session["catalog_on"] else "unknown"


def _route_state(reference, values) -> str:
    """match when every known value equals the reference (raw strings), mismatch when one differs, unknown without both."""
    known = [value for value in values if value is not None]
    if reference is None or not known:
        return "unknown"
    return "match" if all(value == reference for value in known) else "mismatch"


# The spawn fields subagent_spawns counts, by value (a string state, or the JSON text of a number, bool or null).
SPAWN_STATE_FIELDS = ("join", "requested.fork_turns", "requested.fork_n", "requested.role", "requested.model", "requested.effort",
                      "effective.role", "effective.history", "effective.turns", "fork_consistent", "role_state",
                      "route_vs_request.model", "route_vs_request.effort", "route_vs_parent_turn.model",
                      "route_vs_parent_turn.effort", "route_changes_within_child", "expected_route_basis.model",
                      "expected_route_basis.effort", "reroute_evidence", "followups")


def spawn_state(child: dict, owners: dict, activity: dict) -> dict:
    """PR-A 10g: a sub-agent's spawn, as states only (design section 4 with the U3 review). The join runs in memory over every
    scanned rollout: the child's thread id names a SubAgentActivity started item in some rollout (its owner), whose id is the
    spawn_agent call_id (openai/codex rust-v0.157.1 core/src/tools/handlers/multi_agents_v2/spawn.rs:216-226). join is joined
    (the owner is the child's ThreadSpawn parent_thread_id and holds that call), activity_without_spawn_call (it holds no such
    call: a spawn made inside code-mode exec, whose arguments are not persisted), parent_mismatch (another thread owns the
    item), parent_without_started_item (the parent was scanned but holds no started item_completed for the child: a legacy
    rollout persists only completed SubAgentActivity items, rollout/src/policy.rs:107-111, and keeps the others as
    SubAgentActivity events, :136-139, which this join does not read) or parent_not_scanned. What was requested is read from a
    joined call only, else unknown. The child's route is client-side: its own turn contexts and its first own
    ThreadSettingsApplied; a provider reroute is not persisted in rollouts (policy.rs:141-204), so reroute_evidence is always
    not_persisted_in_rollout, and a mismatch is a state, not an error. Route precedence (core/src/agent/child_config.rs:62-99,
    :109-121, :196-253, :283-299): the invoking step's route, then a requested model or effort, else the [agents] defaults
    (:204-206), a model without an effort taking the [agents] default effort, else the model's (:229-238), and a role file
    last; a recorded role means its file was applied (:70-98), so its basis is role_file for both fields."""
    thread, parent_id = child["_thread_id"], child["_parent_thread_id"]
    entries = activity.get(thread, []) if thread is not None else []
    owner, item = next(((o, e) for o, e in entries if o == parent_id), entries[0] if entries else (None, None))
    parent = owners.get(parent_id) if parent_id is not None else None
    call = None
    if owner is None:
        join = "parent_without_started_item" if parent is not None else "parent_not_scanned"
    elif owner != parent_id:
        join = "parent_mismatch"
    else:
        call = owners[owner]["_spawns"].get(item["id"])
        join = "joined" if call is not None else "activity_without_spawn_call"
    if call is not None:
        arguments = call["arguments"]
        if call["namespace"] == "multi_agent_v1":  # V1: fork_context true forks, false or omitted starts fresh (spec :607-613)
            fork_turns, fork_n = ("all" if arguments.get("fork_context") is True else "none"), None
        else:
            fork_turns, fork_n = requested_fork_turns(arguments.get("fork_turns"))
        role = arguments.get("agent_type")
        role = (role.strip(RUST_WHITE_SPACE) or None) if isinstance(role, str) else None
        model = arguments.get("model") if isinstance(arguments.get("model"), str) and arguments.get("model") else None
        effort = (arguments.get("reasoning_effort") if isinstance(arguments.get("reasoning_effort"), str)
                  and arguments.get("reasoning_effort") else None)
        requested = {"fork_turns": fork_turns, "fork_n": fork_n, "role": safe_key(role) if role is not None else None,
                     "model": model_key(model), "effort": effort_key(effort)}
    else:
        role = model = effort = None
        requested = {"fork_turns": "unknown", "fork_n": None, "role": "unknown", "model": "unknown", "effort": "unknown"}
    routes, settings = child["_routes"], child["_settings"]
    effective = {"role": child["role"], "history": "forked" if child["_history_start"] else "fresh", "turns": child["_turns"],
                 "models": sorted({key for key in (model_key(m) for m, _ in routes) if key is not None}),
                 "efforts": sorted({key for key in (effort_key(e) for _, e in routes) if key is not None}),
                 "settings": {"model": model_key(settings[0]), "effort": effort_key(settings[1])} if settings else None}
    expected_history = {"none": "fresh", "all": "forked", "default_all": "forked", "last_n": "forked"}.get(requested["fork_turns"])
    models, efforts = [m for m, _ in routes], [e for _, e in routes]
    parent_route = call["route"] if call is not None else item["route"] if join == "activity_without_spawn_call" else (None, None)
    if child["_role_raw"] is not None:
        basis = {"model": "role_file", "effort": "role_file"}
    elif call is None:
        basis = {"model": "unknown", "effort": "unknown"}
    else:
        basis = {"model": "spawn_request" if model else "agents_default_or_parent_turn",
                 "effort": "spawn_request" if effort else "agents_default_or_model_default" if model else
                 "agents_default_or_parent_turn"}
    targets = {thread, child["_agent_path"]} - {None}
    return {"join": join, "requested": requested, "effective": effective,
            "fork_consistent": None if expected_history is None else expected_history == effective["history"],
            "role_state": "unknown" if call is None else "not_requested" if role is None else
            "match" if role == child["_role_raw"] else "mismatch",
            "route_vs_request": {"model": "unknown" if call is None else "not_requested" if model is None else
                                 _route_state(model, models),
                                 "effort": "unknown" if call is None else "not_requested" if effort is None else
                                 _route_state(effort, efforts)},
            "route_vs_parent_turn": {"model": _route_state(parent_route[0], models), "effort": _route_state(parent_route[1], efforts)},
            "route_changes_within_child": len(set(routes)) > 1, "expected_route_basis": basis,
            "reroute_evidence": "not_persisted_in_rollout",
            "followups": None if parent is None else sum(target in targets for target in parent["_followups"])}


def count_spawn_states(spawns: list[dict]) -> dict:
    """subagent_spawns: each SPAWN_STATE_FIELDS field of the sub-agents' spawn states, counted by value."""
    counts: dict = {}
    for spawn in spawns:
        for field in SPAWN_STATE_FIELDS:
            value = spawn
            for key in field.split("."):
                value = value.get(key) if isinstance(value, dict) else None
            _bump(counts.setdefault(field, {}), value if isinstance(value, str) else json.dumps(value))
    return {field: dict(sorted(values.items())) for field, values in counts.items()}


def scan_codex_lanes(roots, manifest: dict, *, since, until, marker: str, rtk_check=False, exception_records=(),
                     call_ledger=None) -> dict:
    """The Codex lane report over rollout-*.jsonl under exactly the given roots. call_ledger, a list, receives the private
    codex-call-ledger/1 records of every measured session, each with actor_ordinal, its session's ordinal in the published
    actors list (the precedent of U2's sweep ledger, child-usage.mjs:3209-3210 at b2dd1eb7); the report never holds them."""
    skills = [skill for skill in manifest["skills"] if isinstance(skill, dict) and "name" in skill]
    names = [skill["name"] for skill in skills]
    codex_off = [skill["name"] for skill in skills if skill.get("codex_enabled") is False]
    codex_on = [skill["name"] for skill in skills if skill.get("codex_enabled") is True]
    files = iter_rollout_files(roots)
    sessions, parse_errors, untimed, skipped, scanned = [], 0, 0, 0, 0
    # PR-A 10g: the in-memory spawn join index over every scanned rollout, inside the window or not: the session of each
    # thread id, and each child thread's started items as (owner thread id, item). Never published.
    owners: dict = {}
    activity: dict = {}
    for path in files:
        if since is not None:
            try:
                if datetime.fromtimestamp(path.stat().st_mtime, timezone.utc) < since:
                    skipped += 1
                    continue
            except OSError:
                parse_errors += 1
                continue
        scanned += 1
        session, errors, no_time = scan_lanes_file(path, names, since=since, until=until, marker=marker,
                                                   codex_off=codex_off, codex_on=codex_on,
                                                   rtk_check=rtk_check, exception_records=exception_records,
                                                   call_ledger=call_ledger is not None)
        parse_errors += errors
        untimed += no_time
        if session["_thread_id"] is not None:
            owners.setdefault(session["_thread_id"], session)
            for child, item in session["_activity"].items():
                activity.setdefault(child, []).append((session["_thread_id"], item))
        if session["in_window"]:
            session["user_config"] = user_config_state(session)
            sessions.append(session)
    for session in sessions:
        if session["kind"] == "subagent":
            session["spawn"] = spawn_state(session, owners, activity)
    if call_ledger is not None:
        for ordinal, session in enumerate(sessions, 1):
            call_ledger.extend({**record, "actor_ordinal": ordinal} for record in session.get("_call_ledger", ()))

    def count_by(key: str) -> dict:
        counts: dict = {}
        for session in sessions:
            _bump(counts, str(session[key] or "(none)"))
        return dict(sorted(counts.items()))

    workers = [s for s in sessions if s["user_config"] == "applied"]
    bound = len({i for s in sessions for i in s.get("_sidecar_record_indices", ())})
    return {
        "roots_count": len(roots or []), "files_scanned": scanned,
        "sidecar_records": {"bound": bound, "unbound": len(exception_records) - bound},
        "files_skipped_unmodified": skipped, "parse_errors": parse_errors,
        "records_without_timestamp": untimed, "sessions_in_window": len(sessions),
        "sessions_started_before_window": sum(s["started_before_window"] for s in sessions),
        "sessions_ran_past_window_end": sum(s["ran_past_window_end"] for s in sessions),
        "sessions_by_kind": count_by("kind"), "sessions_by_role": count_by("role"),
        "sessions_by_originator": count_by("originator"),
        "sessions_by_history_mode": count_by("history_mode"),
        "sessions_with_tool_calls_but_no_item_events": sum(
            1 for s in sessions if s["own_model_calls"] and not s["own_tool_items"]),
        "user_config": {**{state: sum(s["user_config"] == state for s in sessions)
                           for state in ("applied", "ignored", "unknown")}, "method": USER_CONFIG_METHOD},
        "subagent_spawns": count_spawn_states([s["spawn"] for s in sessions if "spawn" in s]),
        "actors": [{"ordinal": i + 1, "kind": s["kind"], "role": s["role"], "user_config": s["user_config"],
                    **({"spawn": s["spawn"]} if "spawn" in s else {}), "measurement": s["measurement"]}
                   for i, s in enumerate(sessions)],
        "groups": {
            "workers": aggregate_codex_lanes(workers),
            "workers_by_kind": {kind: aggregate_codex_lanes([s for s in workers if s["kind"] == kind])
                                for kind in sorted({str(s["kind"]) for s in workers})},
            "workers_by_role": {role: aggregate_codex_lanes([s for s in workers if s["role"] == role])
                                for role in sorted({s["role"] for s in workers})},
            "negative_controls": aggregate_codex_lanes([s for s in sessions if s["user_config"] == "ignored"]),
            "unclassified": aggregate_codex_lanes([s for s in sessions if s["user_config"] == "unknown"]),
        },
    }


def build_lanes_report(scan: dict, *, since, until, marker: str, now: datetime) -> dict:
    return {"schema_version": 1, "kind": "codex_lane_usage_report", "generated_at": now.isoformat(),
            "window": {"since": since.isoformat() if since else None,
                       "until": until.isoformat() if until else None},
            "marker": marker, **scan, "limits": "Legacy lane fields: " + LANES_LIMITS
            + " PR-A measurement fields use the shared child-usage.mjs kernel and own persisted response_item outputs, with item_completed fallback. Native cumulative provider_usage is separate from Claude per-message counters and from byte measurements. --rtk-check enables fixed-config eligibility replay, asked as the held Codex hook would decide (rtk hook check --agent codex, rtk_parts.agent), with the Codex-only D7 view rtk_parts.d7 (reviewed requires_raw log/find parts left out, unreviewed ones leaving it incomplete). Missing usage, output and dynamic fetch evidence cannot establish acceptance; see README.md."
            + " The PR-A measurement reads a Codex shell call by the shell that ran it: an argv's program (a POSIX shell's -c"
            " script, any other program's argv as one command) and exec_command's cmd in the shell its shell argument names, as"
            " Codex types it. A command run by pwsh, powershell or cmd, or by a shell the rollout does not name, is unresolved"
            " (measurement.codex_commands non_posix_shell, unknown_shell): a Bash call with no text, an unknown rtk replay call,"
            " and M4 incomplete. user_shell and unified_exec_interaction CommandExecution items are no model tool calls"
            " (codex_commands user_shell, exec_interactions); the legacy lane counters keep counting every CommandExecution."
            + " Code-mode attribution is positional, since no parent field is persisted: an emitted item whose id is no model"
            " call id (a hosted web_search_call included) is nested when an own exec call came earlier in its turn, else direct"
            " and counted in measurement.code_mode.unattributed_items; a wait call without a namespace after an exec of its"
            " turn is code mode; concurrent cells are not told apart."
            + " A rollout that is not paginated (no history_mode is legacy) persists no nested item that this adapter reads"
            " (no item_completed command, MCP or web item, and no ExecCommandEnd; its McpToolCallEnd and WebSearchEnd events"
            " are not read), so an exec there with a static fetch-capable tools site and no nested item attributed to it is an"
            " unobservable span"
            " (code_mode.legacy_unobservable_exec_calls, _sites) and M4 is incomplete. The outer exec code is never a fetch"
            " where the code-mode isolate was read to have no network access (cli_version 0.155.1, 0.157.1): its HTTP_SCRIPT"
            " mentions are only counted (code_mode.outer_http_mentions); for any other client an exec with one makes M4"
            " incomplete (code_mode.outer_http_unverified_exec_calls)."
            + " actors[].spawn and subagent_spawns publish sub-agent spawn states only: the join of a child to its parent's"
            " SubAgentActivity started item and spawn_agent call runs in memory, the route is client-side (turn contexts and"
            " ThreadSettingsApplied), and provider reroutes are not persisted in rollouts."
            + " --call-ledger PATH writes the private per-call ledger (codex-call-ledger/1: thread and call ids with each"
            " call's M14 state from the kernel's callLedger, PR-A U2) to a new 0600 file outside every git work tree; it"
            " is refused, with nothing written, where the kernel exports no callLedger, and this report holds no id."}


def render_lanes_text(report: dict) -> str:
    lines = [f"codex lane report  window={report['window']['since']} .. {report['window']['until']}  "
             f"sessions={report['sessions_in_window']} files_scanned={report['files_scanned']} "
             f"parse_errors={report['parse_errors']}",
             "user_config: " + " ".join(f"{state}={report['user_config'][state]}"
                                        for state in ("applied", "ignored", "unknown")),
             "history_mode: " + " ".join(f"{mode}={count}" for mode, count in report["sessions_by_history_mode"].items())
             + f" tool_calls_but_no_item_events={report['sessions_with_tool_calls_but_no_item_events']}"]
    for label, group in (("workers", report["groups"]["workers"]),
                         ("negative_controls", report["groups"]["negative_controls"]),
                         ("unclassified", report["groups"]["unclassified"])):
        lines.append(f"{label}: sessions={group['sessions']} tool_calls={group['tool_calls']} "
                     f"shell={group['shell_calls']} rtk_prefix_share={group['rtk_prefix_share']} "
                     f"marker_sessions={group['marker_sessions']} mcp={group['mcp_calls']} "
                     f"ctx_fetch_share={group['fetch']['ctx_fetch_and_index_share']} "
                     f"first_prompt_median={group['first_prompt_tokens']['median']}")
    lines.append(report["limits"])
    return "\n".join(lines)


# --------------------------------------------------------------------------- CLI


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    claude_source = parser.add_mutually_exclusive_group()
    claude_source.add_argument("--claude-skill-doctor", type=Path, metavar="FILE",
                                help=f"Parse a captured '{shlex.join(SKILL_DOCTOR_ARGV)}' result object or JSON array "
                                     "(its result event's 'result' text), or a plain-text /skill-doctor table, from "
                                     "this file")
    claude_source.add_argument("--run-skill-doctor", action="store_true",
                                help=f"Run '{shlex.join(SKILL_DOCTOR_ARGV)}' now (stdin from /dev/null; without "
                                     "--strict-mcp-config where a managed MCP config is deployed); refused "
                                     "unless total_cost_usd == 0 and num_turns == 0")
    parser.add_argument("--claude-timeout", type=int, default=30, metavar="SECONDS",
                         help="Timeout for --run-skill-doctor (default: 30)")
    parser.add_argument("--codex-root", action="append", default=[], type=Path, metavar="DIR",
                         help="Root to scan for rollout-*.jsonl (repeatable; no default search: "
                              "omit entirely to report Codex as not-measured)")
    parser.add_argument("--window", action="append", default=[], type=int, metavar="N",
                         help="Invoke-rate window in days (repeatable; default: 7 and 30)")
    parser.add_argument("--now", default=None, metavar="ISO8601",
                         help="Reference time for ages and windows (tests; default: current time)")
    parser.add_argument("--home", default=None, metavar="DIR",
                         help="Home directory the skills lock is resolved from "
                              "(XDG_STATE_HOME still takes precedence when set)")
    parser.add_argument("--json", action="store_true", help="print the JSON report")
    parser.add_argument("--out", type=Path, default=None, metavar="PATH",
                         help="Also write the JSON report here; refused if PATH resolves inside "
                              "this checkout. Nothing is written when --out is omitted.")
    lanes = parser.add_argument_group("Codex lane report (--lanes)")
    lanes.add_argument("--lanes", action="store_true",
                       help="Report Codex lane use per rollout session instead of skill invoke rates "
                            "(needs --codex-root; the Claude side is child-usage.mjs --lanes-sweep)")
    lanes.add_argument("--since", default=None, metavar="ISO8601",
                       help="Count only rollout records at or after this time (--lanes)")
    lanes.add_argument("--until", default=None, metavar="ISO8601",
                       help="Count only rollout records before this time (--lanes)")
    lanes.add_argument("--marker", default=None, metavar="TEXT",
                       help=f"Injected-block marker to look for in developer messages (--lanes; "
                            f"default {DEFAULT_LANES_MARKER})")
    lanes.add_argument("--rtk-check", action="store_true",
                       help="Replay native RTK v0.50.0 eligibility under isolated five-exclusion config (--lanes)")
    lanes.add_argument("--exceptions", type=Path,
                       help="Private transcript-SHA256-bound M3 adjudications (--lanes)")
    lanes.add_argument("--call-ledger", type=Path, default=None, metavar="PATH",
                       help="Also write the private per-call ledger (codex-call-ledger/1 JSONL: thread and call ids with "
                            "each call's state) to this new file, mode 0600; refused inside any git work tree, over an "
                            "existing path, or with a measurement kernel that exports no callLedger (--lanes)")
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        manifest = load_manifest(args.manifest)
    except (OSError, ValueError) as error:
        print(f"skill_usage: invalid manifest {args.manifest}: {type(error).__name__}: {error}",
              file=sys.stderr)
        return 2

    try:
        now = parse_iso(args.now) if args.now else now_utc()
    except ValueError as error:
        print(f"skill_usage: invalid --now: {error}", file=sys.stderr)
        return 2

    if args.lanes:
        return lanes_main(args, manifest, now)
    if args.call_ledger is not None:
        print("skill_usage: --call-ledger needs --lanes", file=sys.stderr)
        return 2
    if args.since is not None or args.until is not None or args.marker is not None or args.rtk_check or args.exceptions:
        print("skill_usage: --since, --until and --marker need --lanes", file=sys.stderr)
        return 2

    claude = None
    if args.run_skill_doctor:
        claude = run_skill_doctor(timeout=args.claude_timeout)
        claude["origin"] = "run"
    elif args.claude_skill_doctor is not None:
        try:
            raw = args.claude_skill_doctor.read_text(encoding="utf-8")
        except OSError as error:
            print(f"skill_usage: cannot read --claude-skill-doctor: {type(error).__name__}",
                  file=sys.stderr)
            return 2
        claude = parse_claude_output(raw)
        claude["origin"] = "file"
    if claude is not None and claude.get("error"):
        print(f"skill_usage: Claude skill-doctor capture not used: {claude['error']}", file=sys.stderr)

    names = [skill["name"] for skill in manifest["skills"] if isinstance(skill, dict) and "name" in skill]
    # Union with trial.window_days up front so scan_codex_roots always computes the window the
    # prune rule actually reads, even when --window omits it (build_report also unions this
    # defensively, but only a scan at that window has real counts to report there).
    windows = effective_windows(args.window or list(DEFAULT_WINDOWS), manifest)

    lock_installed_at = load_lock_installed_at(skill_lock_path(home=args.home))
    codex_off = [skill["name"] for skill in manifest["skills"]
                 if isinstance(skill, dict) and skill.get("codex_enabled") is False and "name" in skill]
    codex_scan = scan_codex_roots(args.codex_root, names, now=now, windows=windows, codex_off=codex_off)

    report = build_report(manifest, claude=claude, codex_scan=codex_scan,
                           lock_installed_at=lock_installed_at, now=now, windows=windows)

    if not write_out(args.out, report):
        return 2
    print(json.dumps(report, indent=2, sort_keys=True) if args.json else render_text(report))
    return 0


def out_refused(out: Path | None) -> bool:
    """True, with a message, when --out resolves inside the checkout, where nothing is written."""
    if out is None:
        return False
    resolved_out = out.resolve()
    if resolved_out == ROOT or ROOT in resolved_out.parents:
        print(f"skill_usage: refusing --out inside the repository checkout: {out}", file=sys.stderr)
        return True
    return False


def write_out(out: Path | None, report: dict) -> bool:
    """Write the JSON report to --out; False (nothing written) when it resolves inside the checkout."""
    if out is None:
        return True
    if out_refused(out):
        return False
    resolved_out = out.resolve()
    resolved_out.parent.mkdir(parents=True, exist_ok=True)
    resolved_out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return True


# The private file of --call-ledger (binding correction 1 of the U3 build: mode 0600, create-only, refused inside any git work
# tree, never written by default), by the rule of frozen_checks.private_create on main (a02ff13f, tools/token-e2e/
# frozen_checks.py:1309-1369, a module this unit's base does not hold) and of U2's ledgerTarget and writeLedger
# (child-usage.mjs:2821-2844 at b2dd1eb7).
def inside_git_work_tree(path) -> bool:
    """True when path, which may not exist yet, lies inside a git work tree: a .git entry (a directory, or a linked
    worktree's file) beside its nearest existing ancestor or any directory above that."""
    current = os.path.abspath(path)
    while not os.path.exists(current):
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    current = os.path.realpath(current)
    if os.path.isfile(current):
        current = os.path.dirname(current)
    while True:
        if os.path.lexists(os.path.join(current, ".git")):
            return True
        parent = os.path.dirname(current)
        if parent == current:
            return False
        current = parent


def ledger_path_issue(path) -> str | None:
    """Why --call-ledger refuses path, or None."""
    if inside_git_work_tree(path):
        return "refusing a path inside a git work tree (the ledger holds thread and call ids)"
    if os.path.lexists(path):
        return "refusing an existing path (the ledger is created, never written over)"
    return None


def write_private_ledger(path, records: list) -> None:
    """Create path as JSONL, exclusively (O_EXCL, and O_NOFOLLOW where the platform has it) with mode 0600, in a parent
    directory made 0700 when new; a file left by a failed write is removed. Raises ValueError for a refused path and
    OSError when the file cannot be created or written."""
    issue = ledger_path_issue(path)
    if issue:
        raise ValueError(issue)
    os.makedirs(os.path.dirname(os.path.abspath(path)), mode=0o700, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            descriptor = None
            stream.write("".join(json.dumps(record) + "\n" for record in records))
    except BaseException:
        if descriptor is not None:
            os.close(descriptor)
        try:
            os.unlink(path)
        except OSError:
            pass
        raise


def lanes_main(args, manifest: dict, now: datetime) -> int:
    if args.claude_skill_doctor is not None or args.run_skill_doctor:
        print("skill_usage: --lanes reports Codex rollouts only; the Claude side is "
              "examples/claude-native/workflows/child-usage.mjs --lanes-sweep", file=sys.stderr)
        return 2
    if not args.codex_root:
        print("skill_usage: --lanes needs at least one --codex-root", file=sys.stderr)
        return 2
    try:
        since = parse_iso(args.since) if args.since is not None else None
        until = parse_iso(args.until) if args.until is not None else None
    except ValueError as error:
        print(f"skill_usage: invalid --since/--until: {error}", file=sys.stderr)
        return 2
    if since is not None and until is not None and since >= until:
        print("skill_usage: --since must be earlier than --until", file=sys.stderr)
        return 2
    marker = DEFAULT_LANES_MARKER if args.marker is None else args.marker
    if not marker.strip():
        print("skill_usage: --marker needs non-blank text", file=sys.stderr)
        return 2
    # --call-ledger: every refusal comes before any work, and the file is created before the report is written or printed,
    # so a refusal or a failed write exits 2 with no report and no ledger (U2's CLI order, child-usage.mjs:3448-3460).
    ledger = None
    if args.call_ledger is not None:
        issue = ledger_path_issue(args.call_ledger)
        if issue:
            print(f"skill_usage: --call-ledger: {issue}", file=sys.stderr)
            return 2
        if out_refused(args.out):
            return 2
        if args.out is not None and args.out.resolve() == Path(os.path.abspath(args.call_ledger)).resolve():
            print("skill_usage: --call-ledger: refusing the --out path (the report would be written over the ledger)",
                  file=sys.stderr)
            return 2
        if not kernel_exports("callLedger"):
            print("skill_usage: --call-ledger: the measurement kernel exports no callLedger (PR-A U2), so no call state can "
                  "be read; nothing was written", file=sys.stderr)
            return 2
        ledger = []
    try:
        reviews = []
        if args.exceptions:
            reviews = _measurement_bridge(json.loads(args.exceptions.read_text()), validate_reviews=True)
        scan = scan_codex_lanes(args.codex_root, manifest, since=since, until=until, marker=marker,
                               rtk_check=args.rtk_check, exception_records=reviews, call_ledger=ledger)
    except (OSError, ValueError):
        print("skill_usage: measurement failed; check Node availability and exception sidecar", file=sys.stderr)
        return 2
    report = build_lanes_report(scan, since=since, until=until, marker=marker, now=now)
    if ledger is not None:
        try:
            write_private_ledger(args.call_ledger, ledger)
        except ValueError as error:
            print(f"skill_usage: --call-ledger: {error}", file=sys.stderr)
            return 2
        except OSError as error:
            print(f"skill_usage: --call-ledger: cannot create the file ({type(error).__name__})", file=sys.stderr)
            return 2
    if not write_out(args.out, report):
        return 2
    print(json.dumps(report, indent=2, sort_keys=True) if args.json else render_lanes_text(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
