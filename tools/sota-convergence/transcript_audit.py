#!/usr/bin/env python3
"""Blind audit of a Claude Code workflow run's agent transcripts (Codex review of #145 at 68e74f2c).

The Claude family's blind agents (blind-lane-reviewer, blind-adjudicator) have Read, Glob and Grep with no path
limit, so their prompts' blind rule is enforced after the fact, as codex_lane.blind_audit does for a Codex child.
Claude Code keeps a headless session's workflow run as
``~/.claude/projects/<cwd slug>/<session id>/workflows/<run id>.json`` (status, returned result and the agents it
ran) and each agent's transcript as ``.../<session id>/subagents/workflows/<run id>/agent-<agent id>.jsonl``, where
every tool call names what it read.

The audit is bound to one run: the run record must exist and be completed, list each agent's final attempt, whose
transcript must be present, and (when the caller passes it) hold the very result being collected; any other
transcript must be an earlier attempt of a retried agent's item (at most attempt - 1 per item), audited against that
item's boundary; each agent must have run from the export. An agent is mapped to the item its prompt names (an adjudication input's "Input file: <path>" line, a
lane packet's path). Its Read, Glob and Grep calls must stay under that item's allowed roots (the export and the
item's own input and packet, compared as resolved paths), and it may use no other tool except the structured
return. It fails closed: an unreadable transcript line, a tool call it does not model, a relative path without a
recorded working directory, a glob that climbs with ``..``, an agent naming several items, or an item no agent
served flags the item; an unmapped flagged agent or a run-level problem flags every item.

A heuristic lower bound, like the Codex audit: it reads the paths the tool calls name, not what a program derived.
Standard library only.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

READ_TOOLS = frozenset({"Read", "Glob", "Grep"})
# ECMA-262 WhiteSpace and LineTerminator: what JavaScript's trim() removes. Claude Code trims a Read, Glob or Grep
# path before expanding it, while the transcript keeps the raw value (round 10, TA10-1).
JS_TRIM = "\t\n\v\f\r \u00a0\u1680" + "".join(chr(code) for code in range(0x2000, 0x200B)) + "\u2028\u2029\u202f\u205f\u3000\ufeff"
QUIET_TOOLS = frozenset({"StructuredOutput"})
_GLOB_CHARS = re.compile(r"[*?\[{]")


def transcript_files(directory) -> list:
    """Every agent transcript under ``directory``, nested ones included."""
    return sorted(Path(directory).rglob("agent-*.jsonl")) if directory and Path(directory).is_dir() else []


def transcripts_sha256(directory) -> str:
    """One digest over every agent transcript's relative path and bytes and the run record's bytes: binds a judgment
    to the transcripts and run it was audited on."""
    digest = hashlib.sha256()
    for path in transcript_files(directory):
        relative = path.relative_to(directory).as_posix()
        digest.update(f"{relative}\0{hashlib.sha256(path.read_bytes()).hexdigest()}\n".encode("utf-8"))
    record = run_record_path(directory)
    if record is not None and record.is_file():
        digest.update(f"run\0{hashlib.sha256(record.read_bytes()).hexdigest()}\n".encode("utf-8"))
    return digest.hexdigest()


def run_record_path(directory):
    """``<session>/workflows/<run id>.json`` for ``<session>/subagents/workflows/<run id>``, or None."""
    directory = Path(directory)
    if len(directory.parents) < 3 or directory.parent.name != "workflows" or directory.parents[1].name != "subagents":
        return None
    return directory.parents[2] / "workflows" / f"{directory.name}.json"


def _canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _agent_id(path: Path) -> str:
    return path.name[len("agent-"):-len(".jsonl")]


def _attempt(entry: dict) -> int:
    value = entry.get("attempt")
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else 1


def run_agents(directory) -> dict:
    """{agent id: attempt} of the run record's agents (each agent's final attempt), or {} without a readable record."""
    record_path = run_record_path(directory)
    try:
        record = json.loads(record_path.read_text(encoding="utf-8")) if record_path is not None else None
    except (OSError, ValueError):
        record = None
    entries = record.get("workflowProgress") if isinstance(record, dict) else None
    # An entry without an agent id (an errored or blocked attempt) names no transcript (round 10, TA10-3); its item,
    # if no other agent served it, is flagged as unserved.
    return {entry["agentId"]: _attempt(entry) for entry in entries or []
            if isinstance(entry, dict) and entry.get("type") == "workflow_agent"
            and isinstance(entry.get("agentId"), str) and entry["agentId"]}


def run_issue(directory, files, result=None):
    """Why the transcripts are not one completed run's record (of ``result``, when given), or None. Transcripts the
    record does not list are earlier attempts, which ``audit`` accounts per item."""
    record_path = run_record_path(directory)
    if record_path is None or not record_path.is_file():
        return "no workflow run record next to the transcripts (<session>/workflows/<run id>.json)"
    try:
        record = json.loads(record_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "the workflow run record is unreadable"
    if not isinstance(record, dict) or record.get("status") != "completed":
        return "the workflow run did not complete"
    agents = set(run_agents(directory))
    missing = agents - {_agent_id(path) for path in files}
    if not agents or missing:
        return f"the run's agents ({len(agents)}) have no transcript: missing {sorted(missing, key=str)[:3]}"
    if result is not None:
        returned = record.get("result")
        candidates = [result] + ([result["result"]] if isinstance(result, dict) and "result" in result else [])
        if not any(_canonical(returned) == _canonical(candidate) for candidate in candidates):
            return "the workflow run record holds another result than the one collected"
    return None


def _parse(path: Path) -> tuple:
    """(first user prompt text, [(tool name, input)], working directory, unreadable line count) of a transcript."""
    prompt, calls, cwd, unreadable = None, [], None, 0
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except ValueError:
            unreadable += 1
            continue
        if not isinstance(record, dict):
            unreadable += 1
            continue
        cwd = cwd or (record.get("cwd") if isinstance(record.get("cwd"), str) else None)
        message = record.get("message") if isinstance(record.get("message"), dict) else {}
        content = message.get("content")
        if prompt is None and record.get("type") == "user":
            prompt = content if isinstance(content, str) else " ".join(
                part.get("text", "") for part in content or [] if isinstance(part, dict) and part.get("type") == "text")
        if isinstance(content, list):
            for part in content:
                # tool_use, server_tool_use (web search and fetch), mcp_tool_use: every kind of call counts.
                if isinstance(part, dict) and str(part.get("type", "")).endswith("tool_use"):
                    calls.append((part.get("name"), part.get("input")))
    return prompt or "", calls, cwd, unreadable


def _pattern_prefix(pattern: str) -> str:
    parts = pattern.split("/")
    stop = next((index for index, part in enumerate(parts) if _GLOB_CHARS.search(part)), len(parts))
    return "/".join(parts[:stop]) or "/"


def _call_reads(name, inputs, cwd) -> tuple:
    """(absolute paths the call opened or searched, reasons it cannot be checked) for a read tool call."""
    if not isinstance(inputs, dict):
        return [], [f"{name} call without an input object"]
    paths, reasons = [], []

    def expands(value):
        # Claude Code trims a path, then expands a leading '~', while the transcript keeps the raw text (round 9, F1;
        # round 10, TA10-1). Glob also trims an absolute pattern's base, the text up to its first wildcard's last
        # '/', so '<export>/.. /*' lists the export's parent (round 11, NORM11-1). A value with a '/'-separated
        # component trim() would change (which covers the whole value's ends), one starting with '~' or one
        # holding '$' is never checked as written, it flags.
        if any(part.strip(JS_TRIM) != part for part in value.split("/")) or value.startswith("~") or "$" in value:
            reasons.append(f"{name} path {value!r} is changed by the runtime (whitespace, home or variable) "
                           "before it opens it")
            return True
        return False

    def resolve(value):
        if expands(value):
            return
        if os.path.isabs(value):
            paths.append(value)
        elif cwd:
            paths.append(os.path.join(cwd, value))
        else:
            reasons.append(f"{name} relative path {value!r} without a recorded working directory")

    def pattern_check(label, value):
        if not isinstance(value, str) or not value or expands(value):
            return
        if ".." in Path(value).parts:
            reasons.append(f"{name} {label} climbs with ..: {value}")
        elif os.path.isabs(value):
            paths.append(_pattern_prefix(value))

    if name == "Read":
        value = inputs.get("file_path")
        if isinstance(value, str) and value:
            resolve(value)
        else:
            reasons.append("Read call without a file_path")
    else:
        value = inputs.get("path")
        resolve(value if isinstance(value, str) and value else ".")
        pattern_check("pattern", inputs.get("pattern") if name == "Glob" else None)
        pattern_check("glob", inputs.get("glob") if name == "Grep" else None)
    return paths, reasons


def _within(path: str, roots) -> bool:
    """Whether ``path``, resolved (symlinks and ``..``), is one of ``roots`` or under one, also resolved."""
    real = os.path.realpath(path)
    for root in roots:
        if not root:
            continue
        base = os.path.realpath(root)
        if real == base or real.startswith(base.rstrip("/") + "/"):
            return True
    return False


def audit(directory, items: dict, marker_prefix: str = None, export=None, result=None) -> dict:
    """Audit the workflow run's agent transcripts in ``directory`` against ``items``: {key: {"marker": text its prompt
    contains, "roots": [allowed paths]}}. ``marker_prefix`` (the marker's fixed start) skips an agent that names an
    item outside this audit; ``export`` requires every agent to have run from it; ``result`` requires the run record to
    hold that result. Returns the per-item agent counts and reasons, the flagged unmapped agents, the run issue, the
    transcripts digest and ``flagged_items``."""
    files = transcript_files(directory)
    union = [root for item in items.values() for root in item["roots"]]
    report = {"transcripts": len(files), "transcripts_sha256": transcripts_sha256(directory),
              "run_issue": run_issue(directory, files, result),
              "items": {key: {"agents": 0, "flagged": []} for key in items}, "unmapped_flagged": []}
    export_real = os.path.realpath(export) if export else None
    attempts = run_agents(directory)
    parsed = {path: _parse(path) for path in files}
    mapped = {path: [key for key, item in items.items() if item["marker"] and item["marker"] in parsed[path][0]]
              for path in files}
    # The record lists each agent's final attempt; a retried agent's earlier attempts (attempt n > 1) leave their own
    # transcripts. Each such extra must map to the item of an agent retried at least that often, and is audited
    # against that item's boundary; any other extra fails the run (a planted transcript cannot hide in another item's
    # allowance).
    allowance = {key: 0 for key in items}
    for path in files:
        attempt = attempts.get(_agent_id(path))
        if attempt and attempt > 1 and len(mapped[path]) == 1:
            allowance[mapped[path][0]] += attempt - 1
    unaccounted = []
    for path in files:
        if _agent_id(path) in attempts:
            continue
        keys = mapped[path]
        if not keys and marker_prefix and marker_prefix in parsed[path][0]:
            continue  # an earlier attempt for an item outside this audit, accounted in that item's audit
        if len(keys) == 1 and allowance[keys[0]] > 0:
            allowance[keys[0]] -= 1
        else:
            unaccounted.append(path.name)
    if unaccounted and not report["run_issue"]:
        report["run_issue"] = (f"transcripts the run record does not account for as an earlier attempt of their "
                               f"item: {unaccounted[:3]}")
    for path in files:
        prompt, calls, cwd, unreadable = parsed[path]
        keys = mapped[path]
        if not keys and marker_prefix and marker_prefix in prompt:
            continue
        roots = items[keys[0]]["roots"] if len(keys) == 1 else union
        reasons = [f"{unreadable} unreadable transcript line(s)"] if unreadable else []
        if len(keys) > 1:
            reasons.append(f"the prompt names {len(keys)} items")
        if export_real and (not cwd or os.path.realpath(cwd) != export_real):
            reasons.append(f"ran from {cwd!r}, not the export")
        for name, inputs in calls:
            if not isinstance(name, str):
                reasons.append(f"a tool call without a tool name: {name!r}")
            elif name in READ_TOOLS:
                reads, problems = _call_reads(name, inputs, cwd)
                reasons += problems
                reasons += [f"{name} outside the item's input, packet and export: {read}"
                            for read in reads if not _within(read, roots)]
            elif name not in QUIET_TOOLS:
                reasons.append(f"used {name}")
        for key in keys:
            report["items"][key]["agents"] += 1
            report["items"][key]["flagged"] += [f"{path.name}: {reason}" for reason in reasons]
        if not keys and reasons:
            report["unmapped_flagged"].append({"transcript": path.name, "reasons": reasons})
    flagged = {key for key, entry in report["items"].items() if entry["flagged"] or not entry["agents"]}
    if report["unmapped_flagged"] or report["run_issue"]:
        flagged = set(items)
    report["flagged_items"] = sorted(flagged)
    return report


def project_slug(cwd) -> str:
    """Claude Code's per-directory project name: the resolved working directory with every character other than a
    letter or digit written as '-' (/home/example/export -> -home-example-export)."""
    return re.sub(r"[^A-Za-z0-9]", "-", str(Path(cwd).resolve()))


def workflow_transcript_dir(cwd, session_id: str, projects_root=None) -> Path:
    """The one workflow run's agent transcript directory of a headless session run from ``cwd``; ValueError when the
    session holds no workflow run or more than one."""
    if not isinstance(session_id, str) or not re.fullmatch(r"[A-Za-z0-9-]+", session_id):
        raise ValueError(f"not a session id: {session_id!r}")
    projects = Path(projects_root or Path.home() / ".claude" / "projects")
    base = projects / project_slug(cwd) / session_id
    try:
        exact = base.is_dir()
    except OSError:  # a slug past NAME_MAX; Claude Code shortened it (round 10, TA10-2)
        exact = False
    if not exact:
        # Claude Code shortens a long project directory name (round 9, REG9-7); a session id is unique, so find it.
        found = sorted(path for path in projects.glob(f"*/{session_id}") if path.is_dir())
        if len(found) != 1:
            raise ValueError(f"no single session directory {session_id} under {projects} (found {len(found)})")
        base = found[0]
    runs = sorted(path for path in (base / "subagents" / "workflows").glob("*") if path.is_dir())
    if len(runs) != 1:
        raise ValueError(f"expected one workflow run under {base}/subagents/workflows, found {len(runs)}")
    return runs[0]


def main(argv=None) -> int:
    import argparse
    import sys
    parser = argparse.ArgumentParser(description="Locate a headless session's workflow agent transcripts.")
    sub = parser.add_subparsers(dest="command", required=True)
    locate = sub.add_parser("locate", help="Print the workflow run's agent transcript directory.")
    locate.add_argument("--cwd", required=True, type=Path, help="The directory the session ran from (the export).")
    locate.add_argument("--session-json", required=True, type=Path,
                        help="The session's `claude -p --output-format json` output (its session_id).")
    args = parser.parse_args(argv)
    try:
        session_id = json.loads(args.session_json.read_text(encoding="utf-8"))["session_id"]
        print(workflow_transcript_dir(args.cwd, session_id))
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"transcript_audit: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
