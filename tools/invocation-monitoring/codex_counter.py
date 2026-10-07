#!/usr/bin/env python3
"""Count completed native Codex MCP calls and shell executions.

Sources: installed openai/codex 0.160.1 rollout item_completed records and
cc-codex-native-invoke-probe.py (CC v1, 2026-10-06, extended without editing).
Shell/parent decoding reuses tools/skill-usage/skill_usage.py, whose references
name openai/codex rust-v0.157.1 core/src/shell.rs and protocol/src/protocol.rs.
The skill-read proxy counts native read-command attempts, not successful loads.
MCP arguments and embedded program text are never parsed for skill reads.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import sqlite3

_HELPER = Path(__file__).resolve().parents[1] / "skill-usage" / "skill_usage.py"
_SPEC = importlib.util.spec_from_file_location("native_skill_usage", _HELPER)
_USAGE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_USAGE)
SKILL = re.compile(r"/skills/(?:\.system/)?([A-Za-z0-9_.:-]+)/SKILL\.md")
READERS = {"cat", "sed", "head", "tail", "bat", "less", "read", "nl"}
PRUNE = {"auth", "models", "node_modules", ".venv", ".git", "__pycache__"}


def instant(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from strings(child)


def shell_reads(command):
    """Native CommandExecution argv -> literal read-target attempts.

    shell_script handles recorded shell -c/-lc argv using the maintained helper.
    shlex decodes shell quoting; it does not parse embedded Python/JS or expand
    variables. The proxy covers only the first command, as CC v1 does. Later
    compound branches are omitted because the rollout does not prove they ran.
    A first-command read attempt remains an attempt even if the item fails.
    """
    script = _USAGE.shell_script(command).strip()
    counts, unknown = Counter(), 0
    argv = [str(part) for part in command] if isinstance(command, list) else None
    is_shell = argv and len(argv) >= 3 and argv[1] in {"-c", "-lc"} and os.path.basename(argv[0]) in _USAGE.SCRIPT_SHELLS
    if argv is not None and not is_shell:
        # Native argv is already decoded; punctuation inside an operand is data.
        segments = [argv]
    else:
        # A heredoc is program/data input, never another command-read site.
        if re.search(r"<<-?\s*", script):
            return counts, 1
        # Keep quotes through segmentation so quoted punctuation stays data.
        lexer = shlex.shlex(script, posix=False, punctuation_chars=";&|\n")
        lexer.whitespace = " \t\r"
        try:
            tokens = list(lexer)
        except ValueError:
            return counts, 1
        segments, words = [], []
        for token in tokens:
            if token and set(token) <= set(";&|\n"):
                segments.append(words); words = []
            else:
                words.append(token)
        segments.append(words)
        decoded = []
        for words in segments[:1]:
            try:
                decoded.append(shlex.split(" ".join(words)))
            except ValueError:
                unknown += 1
        segments = decoded[:1]
    for words in segments:
        words = list(words)
        # Shell assignments precede a program; native exec argv cannot itself
        # execute an assignment. env's assignment operands are supported.
        if argv is None or is_shell:
            while words and re.match(r"^[A-Za-z_]\w*=", words[0]):
                words.pop(0)
        if words and os.path.basename(words[0]) == "env":
            words.pop(0)
            while words and re.match(r"^[A-Za-z_]\w*=", words[0]):
                words.pop(0)
        if words and os.path.basename(words[0]) == "rtk":
            words.pop(0)
            if words and words[0] == "proxy":
                words.pop(0)
            elif words and words[0] == "--shell":
                # rtk-ai/rtk v0.51.0 positional-expansion exception in AGENTS.md.
                words.pop(0)
        if not words:
            continue
        program = os.path.basename(words[0])
        if program in READERS:
            targets, skip = set(), False
            for word in words[1:]:
                if skip:
                    skip = False; continue
                if program == "sed" and word in {"-e", "--expression", "-f", "--file"}:
                    skip = True; continue
                if word.startswith("-"):
                    continue
                match = SKILL.search(word)
                if match and match.end() == len(word) and not any(c in word for c in "$`*?["):
                    targets.add(match.group(1))
            counts.update(targets)
        elif program in {"bash", "sh", "zsh"} and len(words) > 2 and words[1] in {"-c", "-lc"}:
            found, bad = shell_reads(words); counts.update(found); unknown += bad
    return counts, unknown


def item_reads(item):
    """Only native commands qualify; MCP argument code is opaque."""
    if item.get("type") == "CommandExecution":
        return shell_reads(item.get("command", ""))
    return Counter(), 0


def discover(default, state):
    homes = {Path(default).expanduser()}
    state = Path(state).expanduser()
    for root, dirs, _ in os.walk(state):
        dirs[:] = [d for d in dirs if d not in PRUNE]
        if Path(root).name == "sessions":
            if any(Path(root).rglob("rollout-*.jsonl")):
                homes.add(Path(root))
            dirs[:] = []
    return sorted(homes, key=lambda p: (p != Path(default).expanduser(), str(p)))


def source_class(path, default):
    if Path(default).expanduser() in path.parents:
        return "default_native"
    text = str(path).lower()
    for kind, pattern in [("fixture", r"fixture|synthetic"), ("clone", r"clone|copied|replay"), ("probe", r"probe|trial|benchmark"), ("admin", r"admin")]:
        if re.search(pattern, text):
            return kind
    return "private_native_home"


def registry(database, historical):
    roots, aliases, parents = {}, {}, {}
    with sqlite3.connect(f"file:{Path(database).expanduser()}?mode=ro", uri=True) as db:
        db.row_factory = sqlite3.Row
        rows = [dict(r) for r in db.execute("SELECT name,session_id,tag,tool,parent_session_id,parent_name,transcript_path FROM instances WHERE tool='codex'")]
        by_name = {r["name"]: r for r in rows}
        for row in rows:
            sid = row["session_id"]
            if not sid:
                continue
            if row["parent_session_id"]:
                parents[sid] = row["parent_session_id"]
            else:
                roots[sid] = {"lane": row["tag"] or row["name"], "identity_source": "hcom_live"}
        for sid, name in db.execute("SELECT session_id,instance_name FROM session_bindings"):
            if name in by_name and by_name[name]["session_id"]:
                aliases[sid] = by_name[name]["session_id"]
    if historical:
        for row in json.loads(Path(historical).read_text()).get("canonical_roots", []):
            roots.setdefault(row["root_id"], {"lane": row["lane"], "identity_source": "hcom_historical"})
    return roots, aliases, parents


def metadata(path):
    with path.open(errors="replace") as file:
        for line in file:
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if row.get("type") == "session_meta":
                meta = row.get("payload") or {}
                return meta
    return {}


def bucket():
    return {"counts": Counter(), "skill_command_read_attempts": Counter(), "skill_user_injections": Counter()}


def prompt_names_by_turn(files):
    """Index the whole native turn, including user input arriving after a call."""
    names, root_turns, notes = defaultdict(set), {}, Counter()
    for path in files:
        active, pending = None, set()
        with path.open(errors="replace") as file:
            for line in file:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                p = row.get("payload") or {}; item = p.get("item") or {}
                if p.get("type") == "task_started" or row.get("type") == "turn_context":
                    active = p.get("turn_id") or active
                    if active:
                        names[active].update(pending); pending.clear()
                        root_turns[active] = p.get("root_turn_id") or active
                user = item.get("type") == "UserMessage" or p.get("type") == "user_message" or (row.get("type") == "response_item" and p.get("role") == "user")
                if user:
                    text = "\n".join(strings(p))
                    words = set(re.findall(r"[\w-]+", text))
                    for token in re.findall(r"\bmcp__([\w-]+?)__([\w-]+)\b", text):
                        words.update(token)
                    tid = p.get("turn_id") or active
                    if tid:
                        names[tid].update(words)
                    else:
                        pending.update(words)
                if p.get("type") == "task_complete":
                    active = None
        if pending:
            notes["user_prompt_text_without_turn_boundary"] += 1
    for turn, root in root_turns.items():
        if root != turn:
            names[turn].update(names[root])
    return names, notes


def load_exclusions(path):
    """Native relaunch first turns and readback turns, including unfinished turns."""
    if not path:
        return {}, []
    payload = json.loads(Path(path).read_text())
    exclusions, notes = defaultdict(list), []
    for lane, entry in payload.get("lanes", {}).items():
        for label, start, end in [("relaunch_first_turn", entry.get("first_turn_started"), entry.get("first_turn_ended")), ("mcp_readback_2_turn", entry.get("mcp_readback_2_prompt_at"), None)]:
            if not start:
                continue
            if not end:
                try:
                    with Path(entry["rollout"]).open(errors="replace") as file:
                        for line in file:
                            try:
                                row = json.loads(line)
                            except ValueError:
                                continue
                            q = row.get("payload") or {}
                            if row.get("type") == "event_msg" and q.get("type") == "task_complete" and instant(row["timestamp"]) > instant(start):
                                end = row["timestamp"]; break
                except (OSError, KeyError, ValueError):
                    notes.append({"lane": lane, "kind": label, "end": "unknown"})
            exclusions[lane].append((instant(start), instant(end) if end else None, label))
    return dict(exclusions), notes


def scan(files, roots, aliases, parents, since, until, default, exclusions=None):
    metas, diagnostics = {}, Counter()
    for path in files:
        try:
            meta = metadata(path)
        except OSError:
            diagnostics["unreadable_files"] += 1; continue
        own = meta.get("id")
        if not own:
            diagnostics["missing_owner_files"] += 1; continue
        parent = meta.get("parent_thread_id") or _USAGE.thread_spawn_source(meta).get("parent_thread_id")
        if parent:
            parents[own] = parent
        metas[path] = meta
    def canonical(own):
        visited = set()
        while own not in roots and own not in visited:
            visited.add(own)
            own = parents.get(own) or aliases.get(own) or ""
            if not own:
                return None
        return own if own in roots else None
    lanes, classes = defaultdict(lambda: {"raw": bucket(), "organic": bucket()}), defaultdict(bucket)
    turn_names, prompt_notes = prompt_names_by_turn(metas)
    diagnostics.update(prompt_notes)
    seen_items, seen_turns, seen_users, seen_owners = set(), set(), set(), set()
    file_owners, source_files, thread_info = Counter(), Counter(), {}
    for path, meta in metas.items():
        own = meta["id"]; canon = canonical(own); category = source_class(path, default)
        file_owners[own] += 1; source_files[category] += 1; seen_owners.add(own)
        lane = roots[canon]["lane"] if canon else "unregistered"
        thread_info[own] = {"canonical_root": canon, "lane": lane, "source_class": category, "identity_source": roots[canon]["identity_source"] if canon else "unregistered"}
        marker = meta.get("subagent_history_start_ordinal")
        prompt_names = set()
        with path.open(errors="replace") as file:
            for line in file:
                try:
                    row = json.loads(line)
                except ValueError:
                    diagnostics["invalid_json_rows"] += 1; continue
                ordinal = row.get("ordinal")
                if isinstance(marker, int) and isinstance(ordinal, int) and 0 < ordinal < marker:
                    diagnostics["fork_copied_rows_excluded"] += 1; continue
                if isinstance(marker, int) and ordinal is None:
                    diagnostics["fork_rows_missing_ordinal"] += 1; continue
                try:
                    stamp = instant(row.get("timestamp", ""))
                except (ValueError, TypeError):
                    diagnostics["rows_missing_timestamp"] += 1; continue
                payload = row.get("payload") or {}; item = payload.get("item") or {}
                user = row.get("type") == "response_item" and payload.get("role") == "user"
                user |= row.get("type") == "event_msg" and payload.get("type") == "user_message"
                user |= item.get("type") == "UserMessage"
                if user:
                    text = "\n".join(strings(payload))
                    prompt_names.update(re.findall(r"[\w-]+", text))
                    for token in re.findall(r"\bmcp__([\w-]+?)__([\w-]+)\b", text):
                        prompt_names.update(token)
                    if since <= stamp < until:
                        key = (own, item.get("id") or ordinal or hashlib.sha256(text.encode()).hexdigest())
                        if key not in seen_users:
                            seen_users.add(key)
                            injections = []
                            for block in re.findall(r"<skill(?:\s[^>]*)?>.*?</skill>", text, re.S):
                                injections.extend(re.findall(r"<skill>\s*(?:<name>\s*)?([\w.:-]+)", block))
                                injections.extend(re.findall(r"<skill\s+name=['\"]([^'\"]+)", block))
                                injections.extend(SKILL.findall(block))
                            for name in set(injections):
                                lanes[lane]["raw"]["skill_user_injections"][name] += 1
                if not since <= stamp < until:
                    continue
                target = lanes[lane]
                if row.get("type") == "turn_context":
                    key = (own, ordinal if ordinal is not None else row.get("timestamp"))
                    if key not in seen_turns:
                        seen_turns.add(key); target["raw"]["counts"]["turn"] += 1
                        excluded_turn = any(reason == "relaunch_first_turn" and start <= stamp and (end is None or stamp <= end) for start, end, reason in (exclusions or {}).get(lane, []))
                        if canon and category in {"default_native", "private_native_home"} and not excluded_turn:
                            target["organic"]["counts"]["turn"] += 1
                    continue
                if row.get("type") != "event_msg" or payload.get("type") != "item_completed":
                    continue
                kind, ident = item.get("type"), item.get("id")
                if not ident:
                    diagnostics["completed_items_missing_id"] += 1; continue
                key = (canon or own, kind, ident)
                if key in seen_items:
                    diagnostics["duplicate_completed_items"] += 1; continue
                seen_items.add(key)
                if kind not in {"McpToolCall", "CommandExecution"}:
                    diagnostics["non_invocation_completed_items_observed"] += 1; continue
                counters = Counter({"item:" + str(kind): 1})
                if kind == "McpToolCall":
                    counters["mcp:" + str(item.get("server"))] += 1
                    counters["mcp_tool:" + str(item.get("server")) + "/" + str(item.get("tool"))] += 1
                    if item.get("status") not in (None, "completed", "Completed"):
                        counters["mcp_fail"] += 1
                elif kind == "CommandExecution":
                    counters["cmd"] += 1
                    counters["rtk"] += int(bool(re.match(r"\s*(?:\w+=\S+\s+|env\s+)*rtk\b", _USAGE.shell_script(item.get("command", "")))))
                reads, unknown = item_reads(item)
                diagnostics["unresolved_native_command_read_proxy"] += unknown
                target["raw"]["counts"].update(counters); target["raw"]["skill_command_read_attempts"].update(reads)
                classes[category]["counts"].update(counters); classes[category]["skill_command_read_attempts"].update(reads)
                organic = category in {"default_native", "private_native_home"} and canon is not None
                all_prompts = turn_names.get(payload.get("turn_id"), prompt_names)
                organic &= not (kind == "McpToolCall" and (item.get("server") in all_prompts or item.get("tool") in all_prompts))
                for start, end, reason in (exclusions or {}).get(lane, []):
                    applies = reason == "relaunch_first_turn" or (kind == "McpToolCall" and str(item.get("server", "")).replace("_", "-") in {"chrome-devtools", "promptfoo"})
                    if applies and start <= stamp and (end is None or stamp <= end):
                        organic = False; diagnostics["excluded_" + reason] += 1
                if organic:
                    target["organic"]["counts"].update(counters); target["organic"]["skill_command_read_attempts"].update(reads)
                else:
                    diagnostics["nonorganic_completed_items"] += 1
    totals = {mode: bucket() for mode in ("raw", "organic")}
    for target in lanes.values():
        for mode in totals:
            for key in totals[mode]:
                totals[mode][key].update(target[mode][key])
    registered = {mode: bucket() for mode in ("raw", "organic")}
    for lane, target in lanes.items():
        if lane != "unregistered":
            for mode in registered:
                for key in registered[mode]:
                    registered[mode][key].update(target[mode][key])
    missing = [{"root_id": sid, **record} for sid, record in roots.items() if sid not in seen_owners]
    return {"totals": totals, "registered_totals": registered, "by_lane": dict(lanes), "by_source_class": dict(classes), "diagnostics": dict(diagnostics), "files_scanned": len(metas), "unique_owner_threads": len(seen_owners), "duplicate_owner_files": sum(n-1 for n in file_owners.values()), "source_files": dict(source_files), "threads": thread_info, "registry_roots_missing_rollouts": missing}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--since", required=True); parser.add_argument("--until", required=True)
    parser.add_argument("--sessions", default="~/.codex/sessions")
    parser.add_argument("--state", default="~/.local/state/native-agent-stack")
    parser.add_argument("--hcom-db", default="~/.hcom/hcom.db")
    parser.add_argument("--historical-registry"); parser.add_argument("--out")
    parser.add_argument("--first-turn-boundaries")
    args = parser.parse_args(); since, until = instant(args.since), instant(args.until)
    if since >= until:
        parser.error("since must precede until")
    roots, aliases, parents = registry(args.hcom_db, args.historical_registry)
    exclusions, exclusion_notes = load_exclusions(args.first_turn_boundaries)
    homes = discover(args.sessions, args.state)
    files = sorted({p for home in homes for p in home.rglob("rollout-*.jsonl")}, key=lambda p: (Path(args.sessions).expanduser() not in p.parents, str(p)))
    report = {
        "schema_version": 3,
        "evidence_class": "native_completed_item_observation",
        "window": {"since": args.since, "until": args.until, "bounds": "[since,until)"},
        "client_reference": "openai/codex 0.160.1",
        "rules": {
            "invocation_types": ["McpToolCall", "CommandExecution"],
            "identity": "first native owner id + native parent edges + hcom registry; no cwd lane inference",
            "dedup": "canonical thread + completed type + item id; owner id globally shared across files",
            "skill_reads": "native CommandExecution read-command target attempts after shell/rtk/proxy decoding; not successful semantic loads",
            "skill_read_prefix": "shell assignments, optional env assignment operands, then actual rtk with optional proxy or qualified --shell; no arbitrary flag/program stripping",
            "compound_reads": "only the first command-read attempt is proxied; later branches are not evidence of execution",
            "skill_user_injections": "informational only; never summed with read attempts",
            "program_text": "never parse JavaScript, Python or MCP argument code for skill reads",
            "organic": "PROVISIONAL: registered native homes, lexical tool-name filter, relaunch and readback exclusion intervals",
            "mtime_filter": False,
        },
        "organic_acceptance": {
            "status": "not_yet_measured",
            "all_turn_prompts_and_coop_blocks": "not_yet_fully_resolved",
            "staged_steers_understanding_guidance": "not_yet_measured",
            "first_turn_boundaries_loaded": bool(args.first_turn_boundaries),
            "boundary_notes": exclusion_notes,
        },
        "registry": {
            "live_roots": sum(r["identity_source"] == "hcom_live" for r in roots.values()),
            "historical_only_roots": sum(r["identity_source"] == "hcom_historical" for r in roots.values()),
        },
        "session_homes_discovered": len(homes),
        **scan(files, roots, aliases, parents, since, until, args.sessions, exclusions),
        "limits": [
            "Skill read attempts cover literal native read-command targets, not executed semantic skill loads.",
            "Python commands, JavaScript and MCP argument programs are outside the skill read proxy; their read behavior is unknown.",
            "Heredocs, dynamic path expansion and unresolved shell quoting are not read-proxy evidence.",
            "Later commands in compounds are omitted; native completion does not establish which branches ran.",
            "Organic counts are not yet measured; provisional candidates cannot establish zero use.",
            "All externally referenced cooperation guidance and standing-steer count semantics are not fully resolved.",
            "Absent native completed-item records remain unknown, not zero execution.",
        ],
    }
    # The user's ORGANIC-COUNT-RULE forbids reporting an incomplete filter as
    # an organic count. Keep candidates reviewable under an explicit label.
    for target in [report["totals"], report["registered_totals"], *report["by_lane"].values()]:
        target["provisional_prompt_filtered"] = target.pop("organic")
    report["organic_acceptance"]["status"] = "not_yet_measured"
    report["organic_acceptance"]["native_all_turn_prompts"] = "indexed"
    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.out:
        path = Path(args.out); path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(path.parent, 0o700)
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "w") as file:
            file.write(encoded)
        os.chmod(path, 0o600)
    print(json.dumps({"window": report["window"], "registry": report["registry"], "session_homes_discovered": len(homes), "totals": report["totals"], "diagnostics": report["diagnostics"], "files_scanned": report["files_scanned"], "unique_owner_threads": report["unique_owner_threads"]}, sort_keys=True))


if __name__ == "__main__":
    main()
