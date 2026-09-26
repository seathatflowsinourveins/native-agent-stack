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
# may itself contain spaces). `source` may also contain a space ("claude.ai sync").
SKILL_DOCTOR_ROW = re.compile(
    r"^\s*(?P<skill>\S+)\s+(?P<source>.+?)\s+(?P<context>-|~?\d[\d,.]*[kKmMbB]?)\s+"
    r"(?P<tokens_7d>-|~?\d[\d,.]*[kKmMbB]?)\s+(?P<uses>\d+)×\s+(?P<last_used>.+?)\s*$"
)
_COUNT_RE = re.compile(r"~?(\d[\d,.]*)([kKmMbB]?)")
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
    """"~110" -> 110, "1.2k" -> 1200, "-" (not in the current listing / no data) -> None."""
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


def scan_rollout_file(path: Path, names, mention_patterns: dict, now: datetime, windows) -> tuple[dict, int]:
    counts = _empty_counts(names, windows)
    parse_errors = 0
    try:
        handle = path.open(encoding="utf-8", errors="replace")
    except OSError:
        return counts, 1
    with handle:
        for raw_line in handle:
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                record = json.loads(raw_line)
                if not isinstance(record, dict):
                    raise ValueError("rollout line is not a JSON object")
                _score_line(record, names, mention_patterns, now, windows, counts)
            except Exception:
                parse_errors += 1
    return counts, parse_errors


def scan_codex_roots(roots, names, *, now: datetime, windows) -> dict:
    windows = tuple(sorted(set(windows)))
    mention_patterns = {name: re.compile(r"\$" + re.escape(name) + r"\b") for name in names}
    totals = _empty_counts(names, windows)
    files = iter_rollout_files(roots)
    parse_errors = 0
    for path in files:
        file_counts, file_errors = scan_rollout_file(path, names, mention_patterns, now, windows)
        parse_errors += file_errors
        for name in names:
            for window in windows:
                totals[name][window]["skill_md_reads"] += file_counts[name][window]["skill_md_reads"]
                totals[name][window]["name_mentions"] += file_counts[name][window]["name_mentions"]
    return {"roots_count": len(roots or []), "files_scanned": len(files),
            "parse_errors": parse_errors, "windows": list(windows), "counts": totals}


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
            codex_out = {"enabled": codex_enabled, "counts": per_window}
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
                   "parse_errors": codex_scan["parse_errors"]},
        "skills": skills_out,
        "prune_candidates": prune_candidates,
        "verdict_recheck": verdict_recheck,
        "limits": (
            "Claude 'uses' from /skill-doctor is not windowed by --window (only its '7d tokens' "
            "column is): the same lifetime count is reused for every window's zero-usage check, "
            "a documented gap, not a measured per-window value. Codex counts are windowed from "
            "each rollout line's own timestamp. A skill with no measured, enabled/listed client "
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
                 f"parse_errors={codex['parse_errors']}")
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
    codex_scan = scan_codex_roots(args.codex_root, names, now=now, windows=windows)

    report = build_report(manifest, claude=claude, codex_scan=codex_scan,
                           lock_installed_at=lock_installed_at, now=now, windows=windows)

    if args.out is not None:
        resolved_out = args.out.resolve()
        if resolved_out == ROOT or ROOT in resolved_out.parents:
            print(f"skill_usage: refusing --out inside the repository checkout: {args.out}",
                  file=sys.stderr)
            return 2
        resolved_out.parent.mkdir(parents=True, exist_ok=True)
        resolved_out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(json.dumps(report, indent=2, sort_keys=True) if args.json else render_text(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
