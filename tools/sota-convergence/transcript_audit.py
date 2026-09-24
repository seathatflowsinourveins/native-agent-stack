#!/usr/bin/env python3
"""Blind audit of a Claude Code workflow run's agent transcripts (Codex review of #145 at 68e74f2c).

The Claude family's blind agents (blind-lane-reviewer, blind-adjudicator) have Read, Glob and Grep with no path
limit, so their prompts' blind rule is enforced after the fact, as codex_lane.blind_audit does for a Codex child:
Claude Code keeps every workflow agent's transcript at
``~/.claude/projects/<cwd slug>/<session id>/subagents/workflows/<run id>/agent-<id>.jsonl``, and each tool call
there names the path it read. An agent is mapped to the item its prompt names (an adjudication input's
"Input file: <path>" line, a lane packet's path); every Read, Glob and Grep must stay under that item's allowed
roots (the blind export and the item's own input and packet), and no other tool may be used except the structured
return. An item no agent served, or any flagged agent that names no single item, flags the item (all items, for an
unmapped one), so a wrong or incomplete transcript directory never passes.

A heuristic lower bound, like the Codex audit: it reads the paths the tool calls name, not what a program derived.
Standard library only.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

# The input keys that name what each read tool opened; a missing path reads the agent's working directory.
READ_TOOL_PATHS = {"Read": ("file_path",), "Glob": ("path", "pattern"), "Grep": ("path",)}
QUIET_TOOLS = frozenset({"StructuredOutput"})
_GLOB_CHARS = re.compile(r"[*?\[{]")


def transcript_files(directory) -> list:
    return sorted(Path(directory).glob("agent-*.jsonl")) if directory and Path(directory).is_dir() else []


def transcripts_sha256(directory) -> str:
    """One digest over every agent transcript's name and bytes: binds a judgment to the transcripts it was audited on."""
    digest = hashlib.sha256()
    for path in transcript_files(directory):
        digest.update(f"{path.name}\0{hashlib.sha256(path.read_bytes()).hexdigest()}\n".encode("utf-8"))
    return digest.hexdigest()


def _prompt_calls_cwd(path: Path) -> tuple:
    """(first user prompt text, [(tool name, input dict)], working directory) of one agent transcript."""
    prompt, calls, cwd = None, [], None
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if not isinstance(record, dict):
            continue
        cwd = cwd or (record.get("cwd") if isinstance(record.get("cwd"), str) else None)
        message = record.get("message") if isinstance(record.get("message"), dict) else {}
        content = message.get("content")
        if prompt is None and record.get("type") == "user":
            prompt = content if isinstance(content, str) else " ".join(
                part.get("text", "") for part in content or [] if isinstance(part, dict) and part.get("type") == "text")
        if isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") == "tool_use":
                    calls.append((part.get("name"), part.get("input") if isinstance(part.get("input"), dict) else {}))
    return prompt or "", calls, cwd


def _read_paths(name: str, inputs: dict, cwd) -> list:
    """The absolute paths a read tool call opened or searched (a glob pattern up to its first wildcard)."""
    base = cwd or os.getcwd()
    paths = []
    for key in READ_TOOL_PATHS[name]:
        value = inputs.get(key)
        if key == "pattern":
            if not isinstance(value, str) or not (os.path.isabs(value) or ".." in Path(value).parts):
                continue  # a relative pattern searches under the call's path, checked on its own
            value = "/".join(part for part in value.split("/")[:next(
                (index for index, part in enumerate(value.split("/")) if _GLOB_CHARS.search(part)),
                len(value.split("/")))]) or "/"
        elif not isinstance(value, str) or not value:
            value = base  # Glob and Grep without a path search the working directory
        paths.append(os.path.normpath(value if os.path.isabs(value) else os.path.join(base, value)))
    return paths


def _within(path: str, roots) -> bool:
    candidates = {path, os.path.realpath(path)}
    for root in roots:
        for spelling in {os.path.normpath(os.path.abspath(root)), os.path.realpath(root)}:
            if any(candidate == spelling or candidate.startswith(spelling.rstrip("/") + "/") for candidate in candidates):
                return True
    return False


def audit(directory, items: dict, marker_prefix: str = None) -> dict:
    """Audit every agent transcript in ``directory`` against ``items``: {key: {"marker": text its prompt contains,
    "roots": [allowed paths]}}. Returns the per-item agent counts and reasons, the flagged unmapped agents, the
    transcripts digest and ``flagged_items``. With ``marker_prefix`` (the marker's fixed start, such as
    "Input file: "), an agent whose prompt holds that prefix but none of these items' markers served an item outside
    this audit and is skipped; any other agent that names no single item is unmapped."""
    files = transcript_files(directory)
    union = [root for item in items.values() for root in item["roots"]]
    report = {"transcripts": len(files), "transcripts_sha256": transcripts_sha256(directory),
              "items": {key: {"agents": 0, "flagged": []} for key in items}, "unmapped_flagged": []}
    for path in files:
        prompt, calls, cwd = _prompt_calls_cwd(path)
        keys = [key for key, item in items.items() if item["marker"] and item["marker"] in prompt]
        if not keys and marker_prefix and marker_prefix in prompt:
            continue
        roots = items[keys[0]]["roots"] if len(keys) == 1 else union
        reasons = []
        for name, inputs in calls:
            if name in READ_TOOL_PATHS:
                reasons += [f"{name} outside the item's input, packet and export: {read}"
                            for read in _read_paths(name, inputs, cwd) if not _within(read, roots)]
            elif name not in QUIET_TOOLS:
                reasons.append(f"used {name}")
        if len(keys) == 1:
            report["items"][keys[0]]["agents"] += 1
            report["items"][keys[0]]["flagged"] += [f"{path.name}: {reason}" for reason in reasons]
        elif reasons:
            report["unmapped_flagged"].append({"transcript": path.name, "reasons": reasons})
    flagged = {key for key, entry in report["items"].items() if entry["flagged"] or not entry["agents"]}
    if report["unmapped_flagged"]:
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
    base = Path(projects_root or Path.home() / ".claude" / "projects") / project_slug(cwd) / session_id
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
