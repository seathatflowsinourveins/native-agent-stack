#!/usr/bin/env python3
"""Per-host skill invoke-rate report: joins adoption/skills/manifest.json with real usage.

Claude side reads native `/skill-doctor` (its table is the only per-skill invoke-rate signal
Claude Code exposes; see the README for why OTel, a custom hook, agentsview and ccusage cannot
answer this):

    claude -p "/skill-doctor" --output-format json > /path/outside/checkout/skill-doctor.json
    python3 tools/skill-usage/skill_usage.py --claude-skill-doctor /path/outside/checkout/skill-doctor.json \\
        --codex-root ~/.codex/sessions --out /path/outside/checkout/report.json

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
"""
from __future__ import annotations

import argparse
import json
import os
import re
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
    """Parse either a captured stream-json event array or a plain-text /skill-doctor table.

    Returns {"format", "rows", "total_cost_usd", "num_turns"} and, when the capture is refused
    or malformed, an "error" key with rows left empty. total_cost_usd/num_turns are None for a
    plain-text capture: there is no cost signal to check, because there is no result event.
    """
    try:
        events = json.loads(raw)
    except json.JSONDecodeError:
        return {"format": "text", "rows": parse_skill_doctor_text(raw),
                "total_cost_usd": None, "num_turns": None}
    if not isinstance(events, list):
        return {"format": "json", "rows": {}, "total_cost_usd": None, "num_turns": None,
                "error": "expected a JSON array of stream-json events"}
    result_event = find_result_event(events)
    if result_event is None:
        return {"format": "json", "rows": {}, "total_cost_usd": None, "num_turns": None,
                "error": "no result event in the JSON array"}
    total_cost_usd = result_event.get("total_cost_usd")
    num_turns = result_event.get("num_turns")
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


def run_skill_doctor(*, timeout: int = 30, runner=subprocess.run) -> dict:
    """Run exactly `claude -p "/skill-doctor" --output-format json`, stdin from /dev/null."""
    try:
        completed = runner(["claude", "-p", "/skill-doctor", "--output-format", "json"],
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
    """skills CLI 1.7.0 global lock: $XDG_STATE_HOME/skills/.skill-lock.json when
    XDG_STATE_HOME is set to an absolute path (the XDG Base Directory spec ignores a relative
    value), else <home>/.agents/.skill-lock.json. --home overrides the fallback base only."""
    environment = os.environ if environment is None else environment
    xdg_state = environment.get("XDG_STATE_HOME") or ""
    if os.path.isabs(xdg_state):
        return Path(xdg_state) / "skills" / ".skill-lock.json"
    base = home or environment.get("HOME") or os.path.expanduser("~")
    return Path(base) / ".agents" / ".skill-lock.json"


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
DOUBLE_QUOTED_DATA = re.compile(r"\$\([^()]*\)|`[^`]*`|[;&|()`\n]")
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
    "CommandExecution, Extension and FileChange items plus function_call records whose call_id is "
    "not also an item id (the rollout shape of codex-cli 0.155.1 and 0.157.1), token_count for the "
    "first prompt (input tokens, cached included) and response_item calls for SKILL.md reads. "
    "Shell, MCP and fetch counts therefore need item_completed events, an EventMsg whose "
    "persistence depends on the rollout's history mode (codex-rs/rollout/src/policy.rs): "
    "sessions_by_history_mode reports session_meta.history_mode, and "
    "sessions_with_tool_calls_but_no_item_events counts sessions whose own records before until "
    "hold model tool calls but no such event, whose shell, MCP and fetch lanes read as zero. "
    "Session properties (kind, originator, history mode, user_config, marker) use every record "
    "before until. Records a spawned sub-agent's rollout copied from its parent (ordinal below "
    "subagent_history_start_ordinal) count toward those properties only, never as the child's "
    "calls. The marker is looked for in developer messages only. The rtk prefix is the first word "
    "of the shell script; curl/wget counts only in command position of the text a shell runs "
    "(quoted strings and heredoc bodies are data unless sh -c, eval, ssh or a shell heredoc runs "
    "them), optionally behind the shell keywords do, then, else, elif, if, while, until, ! and { "
    "and behind rtk, sudo, env, command, exec, time, nice, nohup or timeout N, and a call whose "
    "literal URLs are all loopback is counted apart. ctx_fetch_and_index_share is "
    "ctx_fetch_and_index / (web page opens + ctx_fetch_and_index + remote curl/wget): a fetch run "
    "inside a Context Mode sandbox (ctx_execute or ctx_batch_execute code), a gh api call and "
    "fetch() or an HTTP library in a script are in no lane. Server, function, originator and "
    "history-mode names that are not name-shaped are counted under (other). Sessions whose user "
    "config was ignored are negative controls, never workers. Rollout files not modified since the "
    "window start are skipped unread.")


def safe_key(value) -> str:
    return str(value) if SAFE_KEY.match(str(value)) else "(other)"


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


def executed_text(command: str) -> str:
    """The command text a shell would run (child-usage.mjs executedText): a heredoc body is data
    unless the heredoc feeds a shell, and a quoted string is data unless a shell runs it
    (RUN_QUOTED); inside double quotes, $(...) and `...` still run. Data keeps its words, so URL
    arguments stay, but loses the separators that would put a word in command position."""
    lines, kept, index = (command or "").split("\n"), [], 0
    while index < len(lines):
        kept.append(lines[index])
        match = HEREDOC.search(lines[index])
        if match and not SHELL_WORD.match(_program_of(lines[index][:match.start()])):
            while index + 1 < len(lines) and lines[index + 1].lstrip("\t") != match.group(2):
                index += 1
                kept.append("")
        index += 1
    text, out, index = "\n".join(kept), "", 0
    while index < len(text):
        char = text[index]
        if char == "\\":
            out += text[index:index + 2]
            index += 2
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
            out += '"' + DOUBLE_QUOTED_DATA.sub(lambda m: m.group(0) if len(m.group(0)) > 1 else " ", inner) + '"'
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


def shell_script(command) -> str:
    """The script a CommandExecution item ran: argv ['bash', '-lc', script] -> script."""
    if isinstance(command, list):
        parts = [str(part) for part in command]
        if len(parts) >= 3 and parts[1] in ("-lc", "-c"):
            return parts[2]
        return " ".join(parts)
    return command if isinstance(command, str) else ""


def message_text(payload: dict) -> str:
    content = payload.get("content")
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    return "\n".join(item["text"] for item in content
                     if isinstance(item, dict) and isinstance(item.get("text"), str))


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


def _new_lanes_session() -> dict:
    return {"kind": None, "originator": None, "history_mode": None, "marker": False, "catalog_off": False,
            "catalog_on": False, "in_window": False, "started_before_window": False,
            "ran_past_window_end": False, "tool_calls": 0, "mcp_calls": {}, "mcp_failed": {},
            "shell_calls": 0, "rtk_prefixed": 0, "fetch": dict.fromkeys(FETCH_KEYS, 0),
            "skill_md_reads": {}, "function_calls": {}, "file_changes": 0,
            "first_prompt_tokens": None, "own_model_calls": 0, "own_tool_items": 0}


def _bump(counts: dict, key: str, by: int = 1) -> None:
    counts[key] = counts.get(key, 0) + by


def scan_lanes_file(path: Path, names, *, since, until, marker: str,
                    codex_off, codex_on) -> tuple[dict, int, int]:
    """One rollout file -> (session lanes, parse errors, records without a timestamp).

    A spawned sub-agent's rollout starts with records copied from its parent: those whose ordinal
    is below session_meta.subagent_history_start_ordinal. They count toward session properties
    (the marker and the catalog are part of the child's context) but never as the child's calls.
    A function_call whose call_id is also an item_completed id is one tool call, not two."""
    session = _new_lanes_session()
    parse_errors = untimed = 0
    first_usage_seen = False
    history_start = None
    item_ids: set = set()
    call_ids: list = []

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
                    source = payload.get("source")
                    session["kind"] = ("subagent" if isinstance(source, dict) and "subagent" in source
                                       else "exec" if source == "exec" else "other")
                    session["originator"] = safe_key(payload["originator"]) if payload.get("originator") else "(none)"
                    session["history_mode"] = (safe_key(payload["history_mode"]) if payload.get("history_mode")
                                               else "(none)")
                    session["started_before_window"] = since is not None and when < since
                    start = payload.get("subagent_history_start_ordinal")
                    history_start = start if isinstance(start, int) and not isinstance(start, bool) else None
            elif kind == "response_item":
                payload_type = payload.get("type")
                if payload_type in CALL_PAYLOAD_TYPES and not inherited:
                    session["own_model_calls"] += 1
                if payload_type == "message" and payload.get("role") == "developer":
                    session["marker"] |= marker in message_text(payload)
                elif counted and payload_type in CALL_PAYLOAD_TYPES:
                    for name in skillmd_hits(payload, names):
                        _bump(session["skill_md_reads"], name)
                    if payload_type == "function_call":
                        call_ids.append(payload.get("call_id"))
                        _bump(session["function_calls"], safe_key(payload["name"]) if payload.get("name") else "(none)")
            elif kind == "event_msg" and not inherited:
                payload_type = payload.get("type")
                if (payload_type == "item_completed" and isinstance(payload.get("item"), dict)
                        and payload["item"].get("type") in TOOL_ITEM_TYPES):
                    session["own_tool_items"] += 1
                if payload_type == "token_count" and not first_usage_seen:
                    info = payload.get("info") if isinstance(payload.get("info"), dict) else {}
                    last = info.get("last_token_usage") if isinstance(info.get("last_token_usage"), dict) else {}
                    if isinstance(last.get("input_tokens"), int):
                        first_usage_seen = True
                        if counted:
                            session["first_prompt_tokens"] = last["input_tokens"]
                elif payload_type == "item_completed" and counted:
                    _score_lane_item(session, payload.get("item") if isinstance(payload.get("item"), dict) else {},
                                     item_ids)
    session["tool_calls"] += sum(1 for call_id in call_ids if call_id is None or call_id not in item_ids)
    return session, parse_errors, untimed


def _score_lane_item(session: dict, item: dict, item_ids: set) -> None:
    item_type = item.get("type")
    if item_type in TOOL_ITEM_TYPES and item.get("id") is not None:
        item_ids.add(item.get("id"))
    if item_type == "McpToolCall":
        server = safe_key(item["server"]) if item.get("server") else "(none)"
        session["tool_calls"] += 1
        _bump(session["mcp_calls"], server)
        if item.get("status") == "failed":
            _bump(session["mcp_failed"], server)
        if item.get("tool") == "ctx_fetch_and_index":
            session["fetch"]["ctx_fetch_and_index"] += 1
    elif item_type == "CommandExecution":
        session["tool_calls"] += 1
        session["shell_calls"] += 1
        script = shell_script(item.get("command"))
        if RTK_FIRST_WORD.match(script):
            session["rtk_prefixed"] += 1
        kind = fetch_kind(script)
        if kind:
            session["fetch"]["shell_curl_wget_loopback" if kind == "loopback" else "shell_curl_wget"] += 1
    elif item_type == "Extension":
        session["tool_calls"] += 1
        action = item.get("action") if isinstance(item.get("action"), dict) else {}
        if item.get("kind") == "web.search":
            action_type = action.get("type")
            session["fetch"]["web_open_page" if action_type == "openPage" else
                             "web_search" if action_type == "search" else "web_other"] += 1
    elif item_type == "FileChange":
        session["tool_calls"] += 1
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
           "file_changes": 0, "marker_sessions": 0, "first_prompt_tokens": None}
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
    fetch = out["fetch"]
    out["rtk_prefix_share"] = _share(out["rtk_prefixed_shell_calls"], out["shell_calls"])
    fetch["ctx_fetch_and_index_share"] = _share(
        fetch["ctx_fetch_and_index"], fetch["web_open_page"] + fetch["ctx_fetch_and_index"] + fetch["shell_curl_wget"])
    out["first_prompt_tokens"] = token_stats(session["first_prompt_tokens"] for session in sessions)
    return out


def user_config_state(session: dict) -> str:
    return "ignored" if session["catalog_off"] else "applied" if session["catalog_on"] else "unknown"


def scan_codex_lanes(roots, manifest: dict, *, since, until, marker: str) -> dict:
    """The Codex lane report over rollout-*.jsonl under exactly the given roots."""
    skills = [skill for skill in manifest["skills"] if isinstance(skill, dict) and "name" in skill]
    names = [skill["name"] for skill in skills]
    codex_off = [skill["name"] for skill in skills if skill.get("codex_enabled") is False]
    codex_on = [skill["name"] for skill in skills if skill.get("codex_enabled") is True]
    files = iter_rollout_files(roots)
    sessions, parse_errors, untimed, skipped, scanned = [], 0, 0, 0, 0
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
                                                   codex_off=codex_off, codex_on=codex_on)
        parse_errors += errors
        untimed += no_time
        if session["in_window"]:
            session["user_config"] = user_config_state(session)
            sessions.append(session)

    def count_by(key: str) -> dict:
        counts: dict = {}
        for session in sessions:
            _bump(counts, str(session[key] or "(none)"))
        return dict(sorted(counts.items()))

    workers = [s for s in sessions if s["user_config"] == "applied"]
    return {
        "roots_count": len(roots or []), "files_scanned": scanned,
        "files_skipped_unmodified": skipped, "parse_errors": parse_errors,
        "records_without_timestamp": untimed, "sessions_in_window": len(sessions),
        "sessions_started_before_window": sum(s["started_before_window"] for s in sessions),
        "sessions_ran_past_window_end": sum(s["ran_past_window_end"] for s in sessions),
        "sessions_by_kind": count_by("kind"), "sessions_by_originator": count_by("originator"),
        "sessions_by_history_mode": count_by("history_mode"),
        "sessions_with_tool_calls_but_no_item_events": sum(
            1 for s in sessions if s["own_model_calls"] and not s["own_tool_items"]),
        "user_config": {**{state: sum(s["user_config"] == state for s in sessions)
                           for state in ("applied", "ignored", "unknown")}, "method": USER_CONFIG_METHOD},
        "groups": {
            "workers": aggregate_codex_lanes(workers),
            "workers_by_kind": {kind: aggregate_codex_lanes([s for s in workers if s["kind"] == kind])
                                for kind in sorted({str(s["kind"]) for s in workers})},
            "negative_controls": aggregate_codex_lanes([s for s in sessions if s["user_config"] == "ignored"]),
            "unclassified": aggregate_codex_lanes([s for s in sessions if s["user_config"] == "unknown"]),
        },
    }


def build_lanes_report(scan: dict, *, since, until, marker: str, now: datetime) -> dict:
    return {"schema_version": 1, "kind": "codex_lane_usage_report", "generated_at": now.isoformat(),
            "window": {"since": since.isoformat() if since else None,
                       "until": until.isoformat() if until else None},
            "marker": marker, **scan, "limits": LANES_LIMITS}


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


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    claude_source = parser.add_mutually_exclusive_group()
    claude_source.add_argument("--claude-skill-doctor", type=Path, metavar="FILE",
                                help="Parse a captured 'claude -p \"/skill-doctor\" --output-format "
                                     "json' JSON array (its result event's 'result' text), or a "
                                     "plain-text /skill-doctor table, from this file")
    claude_source.add_argument("--run-skill-doctor", action="store_true",
                                help="Run 'claude -p \"/skill-doctor\" --output-format json' now "
                                     "(stdin from /dev/null); refused unless total_cost_usd == 0 "
                                     "and num_turns == 0")
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
    if args.since is not None or args.until is not None or args.marker is not None:
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


def write_out(out: Path | None, report: dict) -> bool:
    """Write the JSON report to --out; False (nothing written) when it resolves inside the checkout."""
    if out is None:
        return True
    resolved_out = out.resolve()
    if resolved_out == ROOT or ROOT in resolved_out.parents:
        print(f"skill_usage: refusing --out inside the repository checkout: {out}", file=sys.stderr)
        return False
    resolved_out.parent.mkdir(parents=True, exist_ok=True)
    resolved_out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return True


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
    scan = scan_codex_lanes(args.codex_root, manifest, since=since, until=until, marker=marker)
    report = build_lanes_report(scan, since=since, until=until, marker=marker, now=now)
    if not write_out(args.out, report):
        return 2
    print(json.dumps(report, indent=2, sort_keys=True) if args.json else render_lanes_text(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
