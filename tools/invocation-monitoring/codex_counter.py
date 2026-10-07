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


# Native identities: openai/codex@d27764b82f7118f674371e6d6e76271d9d606edb
# codex-rs/protocol/src/models.rs:1061-1159 (call_id, optional response id),
# protocol.rs:1948-1960 (ItemCompleted), :2179-2184 (TurnStarted),
# :3301-3307 (optional turn_id/root_turn_id); history/src/rollout_payload.rs:31-68
# and history/src/lib.rs:350-355 (unmodified payload, optional native ordinal).
# The maintained adapter/kernel own
# normalization; Q6 controls below are not an organic protocol/day qualifier.
CONTROL_SCHEMA = "codex-organic-control-input/1"
CONTROL_RESULT_SCHEMA = "codex-organic-controls/1"
CONTROL_KINDS = {"native", "mcp", "command", "rtk", "skill_read_attempt"}
# Call-free variants: openai/codex@d27764b protocol/src/items.rs:46-78.
# All other completions need a maintained normalizer or remain UNKNOWN.
NON_CALL_COMPLETIONS = {"UserMessage", "FunctionCallOutput", "HookPrompt", "AgentMessage",
                        "Plan", "Reasoning", "ContextCompaction"}
EXECUTED_STATES = {"succeeded", "failed", "interrupted"}
NOT_EXECUTED_STATES = {"rejected", "invalid", "cancelled_with_result"}


def _native_id(value):
    return isinstance(value, str) and bool(value)


def _canonical_ref(value):
    """Declaration consistency only; no external file or credential reads."""
    return (isinstance(value, dict)
            and set(value) == {"path", "pointer", "sha256", "source_commit"}
            and isinstance(value["path"], str) and bool(value["path"])
            and isinstance(value["pointer"], str)
            and (value["pointer"] == "" or value["pointer"].startswith("/"))
            and re.search(r"~(?![01])", value["pointer"]) is None
            and isinstance(value["sha256"], str)
            and re.fullmatch(r"[0-9a-f]{64}", value["sha256"]) is not None
            and isinstance(value["source_commit"], str)
            and re.fullmatch(r"[0-9a-f]{40}", value["source_commit"]) is not None)


def _prompt_words(payload):
    # Literal native user-message names, never prose inference of requestedness.
    item = payload.get("item") or {}
    content = payload.get("message", payload.get("content", item.get("content", []) if isinstance(item, dict) else []))
    text = "\n".join(strings(content))
    # Prose punctuation can surround a name; punctuation runs inside it are
    # literal name characters, so a longer name never names its prefix.
    words = set(re.findall(r"\w(?:[\w.:-]*\w)?", text))
    for server, tool in re.findall(r"\bmcp__([\w-]+?)__([\w-]+)\b", text):
        words.update((server, tool))
    return words


def _record_facts(records):
    """Index original own facts; the adapter still receives EVERY record."""
    meta = next((r.get("payload") for r in records if r.get("type") == "session_meta"), {})
    meta = meta if isinstance(meta, dict) else {}
    marker = meta.get("subagent_history_start_ordinal")
    facts, names, links, results, starts, root_turns = {}, defaultdict(set), {}, set(), [], {}
    notes, active = Counter(), None
    for row in records:
        payload = row.get("payload") or {}
        if not isinstance(payload, dict):
            notes["malformed_native_payload"] += 1; continue
        ordinal = row.get("ordinal")
        if type(marker) is int:
            if type(ordinal) is not int:
                notes["fork_ordinal_unknown"] += 1
            elif ordinal < marker:
                continue  # only the index, never the stream sent to the adapter
        event = payload.get("type")
        if row.get("type") == "event_msg" and event in {"task_started", "turn_started"}:
            active = payload.get("turn_id")
            if _native_id(active):
                starts.append(active)
            else:
                notes["native_turn_id_unknown"] += 1
        elif row.get("type") == "turn_context":
            active = payload.get("turn_id") or active
        turn = payload.get("turn_id") or active
        if _native_id(turn) and _native_id(payload.get("root_turn_id")):
            root_turns[turn] = payload["root_turn_id"]
        item = payload.get("item") or {}
        user = ((row.get("type") == "response_item" and event == "message" and payload.get("role") == "user")
                or (row.get("type") == "event_msg" and event == "user_message")
                or (isinstance(item, dict) and item.get("type") == "UserMessage"))
        if user:
            if _native_id(turn):
                names[turn].update(_prompt_words(payload))
            else:
                notes["unattributed_task_context"] += 1
        kind, ident, command, tool, identity_complete = None, None, None, None, True
        if row.get("type") == "response_item" and event in _USAGE.MODEL_CALL_TYPES - {"tool_search_call"}:
            kind, ident = event, payload.get("call_id") or payload.get("id")
            tool = _USAGE.codex_call_name(payload)
            if event in {"function_call", "custom_tool_call"}:
                identity_complete = _native_id(payload.get("call_id"))
                if _native_id(payload.get("id")) and identity_complete:
                    # Only an ORIGINAL retained response binds these native IDs.
                    links[payload["id"]] = payload["call_id"]
            if event == "local_shell_call":
                command = (payload.get("action") or {}).get("command")
            elif event == "web_search_call":
                action = payload.get("action") or {}
                tool = "WebFetch" if action.get("type") == "openPage" else "WebSearch" if action else None
            elif event == "function_call" and tool.rsplit(".", 1)[-1] in _USAGE.CODEX_SHELL_TOOLS:
                try:
                    args = payload.get("arguments")
                    args = json.loads(args) if isinstance(args, str) else args
                    command, bad = _USAGE.resolve_shell_call(args if isinstance(args, dict) else {})
                    identity_complete &= isinstance(args, dict) and bad is None
                except (ValueError, TypeError):
                    identity_complete = False
        elif row.get("type") == "event_msg" and event == "item_completed" and isinstance(item, dict):
            kind, ident = item.get("type"), item.get("id")
            if payload.get("thread_id") != meta.get("id"):
                notes["completed_owner_identity_unknown"] += 1
            if kind == "CommandExecution":
                if isinstance(item.get("source"), str) and item["source"] in _USAGE.SKIPPED_COMMAND_SOURCES:
                    continue
                tool, command = "Bash", item.get("command")
            elif kind == "McpToolCall":
                tool = "mcp__" + str(item.get("server", "unknown")) + "__" + str(item.get("tool", "unknown"))
            elif kind == "Extension" and item.get("kind") == "web.search":
                tool = "WebFetch" if (item.get("action") or {}).get("type") == "openPage" else "WebSearch"
            else:
                if kind not in NON_CALL_COMPLETIONS:
                    notes["unsupported_native_completion_format"] += 1
                continue
        elif row.get("type") == "response_item" and event in {"function_call_output", "custom_tool_call_output"}:
            if _native_id(payload.get("call_id")):
                results.add(payload["call_id"])
            else:
                notes["native_result_id_unknown"] += 1
        elif row.get("type") == "response_item" and event == "tool_search_call":
            # Current maintained adapter has no normalizer for this newer type.
            notes["unsupported_native_call_format"] += 1
        if kind is not None:
            try:
                stamp = instant(row.get("timestamp", ""))
            except (ValueError, TypeError, AttributeError):
                notes["native_call_time_unknown"] += 1; stamp = None
            if not _native_id(ident):
                notes["native_call_id_unknown"] += 1
            else:
                # Shell function names normalize to Bash, as in the adapter.
                normalized_tool = "Bash" if command is not None else tool
                model_call = row.get("type") == "response_item"
                fact = {"turn_id": turn, "timestamp": stamp, "command": command,
                        "tool": normalized_tool, "identity_complete": identity_complete,
                        "model_call": model_call, "completion_at": None if model_call else stamp,
                        "completion_status": None if model_call else item.get("status"),
                        "completion_command": None if model_call or command is None else _USAGE.shell_script(command)}
                prior = facts.get(ident)
                if prior:
                    if prior["turn_id"] != turn or (prior["tool"] and normalized_tool and prior["tool"] != normalized_tool):
                        notes["conflicting_native_identity"] += 1
                        prior["identity_complete"] = False
                    if (prior["completion_status"] is not None and fact["completion_status"] is not None
                            and prior["completion_status"] != fact["completion_status"]):
                        notes["conflicting_native_representation"] += 1
                        prior["identity_complete"] = False
                    completed_command = fact["completion_command"]
                    if (prior["completion_command"] is not None and completed_command is not None
                            and prior["completion_command"] != completed_command):
                        notes["conflicting_native_representation"] += 1
                        prior["identity_complete"] = False
                    else:
                        # Complete originals must agree. Requests may enrich
                        # them, but cannot replace an observed completed command.
                        if command is not None and (not model_call or prior["completion_command"] is None):
                            prior["command"] = command
                        if completed_command is not None:
                            prior["completion_command"] = completed_command
                    if normalized_tool:
                        prior["tool"] = normalized_tool
                    if model_call and not prior["model_call"]:
                        prior["timestamp"] = stamp
                        prior["model_call"] = True
                    if not model_call and stamp is not None:
                        prior["completion_at"] = min(prior["completion_at"], stamp) if prior["completion_at"] is not None else stamp
                    if fact["completion_status"] is not None:
                        prior["completion_status"] = fact["completion_status"]
                    prior["identity_complete"] &= identity_complete
                else:
                    facts[ident] = fact
        if row.get("type") == "event_msg" and event in set(_USAGE.TURN_EVENTS) - {"task_started", "turn_started"}:
            active = None
    for response_id, call_id in links.items():
        left, right = facts.get(response_id), facts.get(call_id)
        if left and right and ((left["tool"] and right["tool"] and left["tool"] != right["tool"]) or left["turn_id"] != right["turn_id"]):
            notes["conflicting_native_identity"] += 1
            left["identity_complete"] = right["identity_complete"] = False
        if left and right and any(left[field] is not None and right[field] is not None and left[field] != right[field]
                                  for field in ("completion_command", "completion_status")):
            notes["conflicting_native_representation"] += 1
            left["identity_complete"] = right["identity_complete"] = False
        if left and right and left["completion_at"] is not None and right["timestamp"] is not None and left["completion_at"] < right["timestamp"]:
            notes["invalid_native_chronology"] += 1
            left["identity_complete"] = right["identity_complete"] = False
        if left and right:
            left["identity_complete"] = right["identity_complete"] = left["identity_complete"] and right["identity_complete"]
    for fact in facts.values():
        if fact["model_call"] and fact["completion_at"] is not None and fact["timestamp"] is not None and fact["completion_at"] < fact["timestamp"]:
            notes["invalid_native_chronology"] += 1
            fact["identity_complete"] = False
    # Compare every completed fact that the projection deduplicates by its
    # one-hop native key, even when the canonical fact is only a request.
    alias_groups = defaultdict(list)
    for ident, fact in facts.items():
        alias_groups[links.get(ident, ident)].append(fact)
    for group in alias_groups.values():
        conflict = False
        for field in ("completion_command", "completion_status"):
            values = [fact[field] for fact in group if fact[field] is not None]
            conflict |= any(value != values[0] for value in values[1:])
        if conflict:
            notes["conflicting_native_representation"] += 1
        if conflict or not all(fact["identity_complete"] for fact in group):
            for fact in group:
                fact["identity_complete"] = False
    return {"meta": meta, "facts": facts, "names": names, "links": links,
            "results": results, "first_turn": starts[0] if starts else None,
            "root_turns": root_turns, "notes": notes}


def qualify_records(batches, *, since, until, controls):
    """Contextually classify a retained census under explicit versioned controls.

    batches: [{source_id, records, sha256}], retaining the full original stream.
    controls: schema, CanonicalRef policy_ref/masks_ref, sources[source_id]
    (owner_id/native_source/history_complete/source_ref/history_ref), tools[key]
    (kind/native_names/prompt_names), turns[] (owner_id/turn_id, requested/smoke,
    classification_ref, context_complete/context_refs, named_tools/mask_ref,
    optional parent_turn={owner_id,turn_id}/parent_ref), relaunch_masks[]
    (owner_id/turn_id/ref). Each context entry has {ref,resolved,named_tools}.

    Completeness and references are declarations, not truth or acceptance. This
    returns no READY/day/OIR/skill-activation/adoption verdict. The legacy scan
    remains separate. Unresolved scopes have null counts, never zero by default.
    """
    if since >= until:
        raise ValueError("since must precede until")
    if not isinstance(controls, dict) or controls.get("schema") != CONTROL_SCHEMA:
        raise ValueError("organic controls need codex-organic-control-input/1")
    tools, sources = controls.get("tools"), controls.get("sources")
    if (not isinstance(tools, dict) or not tools or any(
            not isinstance(key, str) or not key or not isinstance(value, dict)
            or value.get("kind") not in CONTROL_KINDS
            or any(not isinstance(value.get(field), list) or not value[field]
                   or not all(isinstance(n, str) and n for n in value[field])
                   for field in ("native_names", "prompt_names")) for key, value in tools.items())):
        raise ValueError("organic controls need explicit typed native tool and prompt names")
    if not isinstance(sources, dict) or any(not isinstance(s, dict) for s in sources.values()):
        raise ValueError("organic controls need source declarations")
    turns, masks = {}, {}
    for field, target in (("turns", turns), ("relaunch_masks", masks)):
        if not isinstance(controls.get(field), list):
            raise ValueError("organic controls need explicit turn and relaunch mask lists")
        for value in controls[field]:
            if not isinstance(value, dict) or not all(_native_id(value.get(k)) for k in ("owner_id", "turn_id")):
                raise ValueError("turn/mask declarations need native owner and turn IDs")
            key = (value["owner_id"], value["turn_id"])
            if key in target:
                raise ValueError("duplicate owner/turn control declaration")
            target[key] = value
    global_reasons = []
    if not _canonical_ref(controls.get("policy_ref")):
        global_reasons.append("policy_provenance_unknown")
    if not _canonical_ref(controls.get("masks_ref")):
        global_reasons.append("mask_provenance_unknown")
    prepared, owner_names, owner_first, parent_ids, roots_by_turn = [], defaultdict(set), {}, {}, {}
    diagnostics, seen = Counter(), {}
    for batch in batches:
        records = batch.get("records")
        if not isinstance(records, list) or any(not isinstance(r, dict) for r in records):
            raise ValueError("source batch needs its complete object record list")
        indexed = _record_facts(records)
        diagnostics.update(indexed["notes"])
        meta, owner = indexed["meta"], indexed["meta"].get("id")
        owner = owner if _native_id(owner) else None
        source = sources.get(batch.get("source_id"), {})
        source_reasons = list(global_reasons)
        if not owner or owner != source.get("owner_id"):
            source_reasons.append("owner_identity_unknown")
        if source.get("native_source") is not True:
            source_reasons.append("native_source_unknown")
        if not _canonical_ref(source.get("source_ref")) or source["source_ref"]["sha256"] != batch.get("sha256"):
            source_reasons.append("source_provenance_unknown")
        if source.get("history_complete") is not True or not _canonical_ref(source.get("history_ref")) or not indexed["first_turn"]:
            source_reasons.append("first_native_turn_unknown")
        source_reasons.extend(indexed["notes"])
        for turn_id, words in indexed["names"].items():
            owner_names[(owner, turn_id)].update(words)
        if owner in owner_first and owner_first[owner] != indexed["first_turn"]:
            source_reasons.append("first_native_turn_conflict")
        owner_first[owner] = indexed["first_turn"]
        parent = meta.get("parent_thread_id") or _USAGE.thread_spawn_source(meta).get("parent_thread_id")
        parent_ids[owner] = parent if _native_id(parent) else None
        roots_by_turn.update({(owner, turn): root for turn, root in indexed["root_turns"].items()})
        prepared.append((owner, source_reasons, indexed, records))
    # Join originals ACROSS retained sources of the same native owner before
    # the adapter, window decisions, alias dedup or masks. Do not remove any
    # original protocol row (including copied history or duplicate frames).
    grouped = {}
    for owner, reasons, indexed, records in prepared:
        group = grouped.setdefault(owner, {"streams": [], "reasons": [], "notes": Counter(), "ids": set()})
        diagnostics["duplicate_native_calls"] += len(group["ids"] & indexed["facts"].keys())
        group["ids"].update(indexed["facts"])
        group["streams"].append(records); group["reasons"].extend(reasons)
        group["notes"].update(indexed["notes"])
    prepared = []
    for owner, group in grouped.items():
        # Single-source caller identity is retained; multi-source concatenation
        # keeps every original row and its within-source order intact.
        streams = group["streams"]
        records = streams[0] if len(streams) == 1 else [row for stream in streams for row in stream]
        indexed = _record_facts(records)
        diagnostics.update(indexed["notes"] - group["notes"])
        reasons = [*group["reasons"], *indexed["notes"]]
        ledger = []
        _USAGE.measure_codex_records(records, since=since, until=until, call_ledger=ledger)
        prepared.append((owner, reasons, indexed, ledger))
    counts = {key: {"native_attempts": 0, "eligible_invocation_lower_bound": 0,
                    "excluded": 0, "unknown": 0, "reasons": Counter()} for key in tools}

    def turn_context(owner, turn_id, visited=()):
        key = (owner, turn_id)
        if key in visited:
            return set(), ["parent_context_cycle"]
        turn = turns.get(key, {})
        reasons, named = [], set()
        declared_names = turn.get("named_tools")
        if not isinstance(declared_names, list) or not all(isinstance(n, str) and n in tools for n in declared_names):
            reasons.append("named_tool_mask_unknown")
        else:
            named.update(declared_names)
        if type(turn.get("requested")) is not bool or type(turn.get("smoke")) is not bool or not _canonical_ref(turn.get("classification_ref")):
            reasons.append("run_classification_unknown")
        if turn.get("context_complete") is not True or not _canonical_ref(turn.get("mask_ref")):
            reasons.append("task_context_unknown")
        if not isinstance(turn.get("context_refs"), list):
            reasons.append("referenced_context_unknown")
        else:
            for context in turn["context_refs"]:
                if (not isinstance(context, dict) or context.get("resolved") is not True
                        or not _canonical_ref(context.get("ref")) or not isinstance(context.get("named_tools"), list)
                        or not all(isinstance(n, str) and n in tools for n in context["named_tools"])):
                    reasons.append("referenced_context_unknown")
                else:
                    named.update(context["named_tools"])
        for tool_key, spec in tools.items():
            if set(spec["prompt_names"]) & owner_names.get(key, set()):
                named.add(tool_key)
        parent = parent_ids.get(owner)
        if parent:
            target = turn.get("parent_turn") or {}
            parent_turn = target.get("turn_id") if isinstance(target, dict) else None
            root = roots_by_turn.get(key)
            parent_root = roots_by_turn.get((parent, parent_turn), parent_turn)
            if (not isinstance(target, dict) or target.get("owner_id") != parent
                    or not _native_id(parent_turn) or not _canonical_ref(turn.get("parent_ref"))
                    or parent not in owner_first or not root or root != parent_root):
                reasons.append("parent_attribution_unknown")
            else:
                inherited, unresolved = turn_context(parent, parent_turn, (*visited, key))
                named.update(inherited); reasons.extend(unresolved)
                p = turns.get((parent, parent_turn), {})
                if any(p.get(flag) is True and turn.get(flag) is not True for flag in ("requested", "smoke")):
                    reasons.append("parent_run_classification_conflict")
        return named, reasons

    observed_states, native_calls, unattributed = Counter(), 0, 0
    for owner, source_reasons, indexed, ledger in prepared:
        for call in ledger:
            ident = call.get("call_id")
            canonical_id = indexed["links"].get(ident, ident)
            # A proven response-ID alias does not move an original call across a
            # window boundary merely because its UI completion is later.
            fact = indexed["facts"].get(canonical_id) or indexed["facts"].get(ident) or {}
            if fact.get("timestamp") is not None and not since <= fact["timestamp"] < until:
                diagnostics["original_native_call_outside_window"] += 1
                continue
            key = (owner, canonical_id)
            if _native_id(canonical_id) and key in seen:
                diagnostics["duplicate_native_calls"] += 1
                if seen[key].get("tool") != call.get("tool") or seen[key].get("state") != call.get("state"):
                    diagnostics["conflicting_native_representation"] += 1
                continue
            if _native_id(canonical_id):
                seen[key] = call
            native_calls += 1
            observed_states[call.get("state", "unknown")] += 1
            turn_id = fact.get("turn_id")
            reasons = list(source_reasons)
            if not _native_id(canonical_id) or not fact.get("identity_complete"):
                reasons.append("native_call_identity_unknown")
            if not _native_id(turn_id):
                reasons.append("native_turn_attribution_unknown")
            named, context_reasons = turn_context(owner, turn_id)
            reasons.extend(context_reasons)
            turn = turns.get((owner, turn_id), {})
            exclusions = [flag for flag in ("requested", "smoke") if turn.get(flag) is True]
            if owner_first.get(owner) == turn_id and "first_native_turn_unknown" not in reasons:
                exclusions.append("first_native_turn")
            mask = masks.get((owner, turn_id))
            if mask:
                if _canonical_ref(mask.get("ref")):
                    exclusions.append("relaunch_first_turn")
                else:
                    reasons.append("relaunch_mask_unknown")
            command = fact.get("command")
            reads, read_unknown = shell_reads(command) if command is not None else (Counter(), 0)
            rtk = command is not None and bool(re.match(r"\s*(?:\w+=\S+\s+|env\s+)*rtk\b", _USAGE.shell_script(command)))
            if read_unknown:
                diagnostics["unresolved_command_read_proxy"] += 1
            matched = []
            for tool_key, spec in tools.items():
                kind = spec["kind"]
                native_tool = call.get("tool")
                matches = (native_tool in spec["native_names"] if kind == "native"
                           else native_tool == "Bash" and native_tool in spec["native_names"] if kind == "command"
                           else isinstance(native_tool, str) and native_tool.startswith("mcp__") and native_tool in spec["native_names"] if kind == "mcp"
                           else rtk if kind == "rtk" else bool(set(spec["native_names"]) & reads.keys()))
                if matches:
                    matched.append(tool_key)
                    cell = counts[tool_key]; cell["native_attempts"] += 1
                    tool_reasons = list(reasons)
                    if kind == "skill_read_attempt" and read_unknown:
                        tool_reasons.append("skill_read_proxy_unknown")
                    if call.get("state") not in EXECUTED_STATES | NOT_EXECUTED_STATES:
                        tool_reasons.append("native_execution_unknown")
                    tool_exclusions = list(exclusions)
                    if tool_key in named:
                        tool_exclusions.append("named_turn")
                    if call.get("state") in NOT_EXECUTED_STATES:
                        tool_exclusions.append("native_not_executed")
                    if tool_reasons:
                        cell["unknown"] += 1; cell["reasons"].update(set(tool_reasons))
                    elif tool_exclusions:
                        cell["excluded"] += 1; cell["reasons"].update(set(tool_exclusions))
                    else:
                        cell["eligible_invocation_lower_bound"] += 1
            if not matched:
                diagnostics["unmapped_native_call"] += 1; unattributed += 1
    # Missing original IDs/results/time/formats prevent a zero-call claim.
    for _, _, indexed, ledger in prepared:
        known = set(indexed["facts"]) | set(indexed["links"]) | set(indexed["links"].values())
        diagnostics["unjoined_native_results"] += len(indexed["results"] - known)
        represented = {indexed["links"].get(c.get("call_id"), c.get("call_id")) for c in ledger}
        diagnostics["unrepresented_native_calls"] += len({indexed["links"].get(ident, ident)
            for ident, fact in indexed["facts"].items()
            if fact["timestamp"] is not None and since <= fact["timestamp"] < until
            and indexed["links"].get(ident, ident) not in represented})
    census_unknown = (unattributed + (not prepared) + len(global_reasons)
                      + sum(bool(reasons) for _, reasons, _, _ in prepared)
                      + sum(diagnostics[key] for key in (
                          "native_call_id_unknown", "native_result_id_unknown", "native_call_time_unknown",
                          "unsupported_native_call_format", "unjoined_native_results", "unresolved_command_read_proxy",
                          "conflicting_native_representation", "unrepresented_native_calls",
                          "unsupported_native_completion_format", "invalid_native_chronology")))
    for cell in counts.values():
        cell["organic_count"] = None if cell["unknown"] or census_unknown else cell["eligible_invocation_lower_bound"]
        cell["reasons"] = dict(cell["reasons"])
    return {"schema": CONTROL_RESULT_SCHEMA,
            "status": "unknown" if census_unknown or any(c["unknown"] for c in counts.values()) else "controls_complete",
            "claim": "contextual supplied-record classification only; no READY, day, OIR, skill activation or adoption qualification",
            "policy_ref": controls.get("policy_ref"), "masks_ref": controls.get("masks_ref"),
            "native_call_attempts": native_calls, "native_call_states": dict(observed_states),
            "census_unknown": census_unknown, "by_tool": counts, "diagnostics": dict(diagnostics),
            "limits": ["CanonicalRef/completeness are producer declarations, not proof of external truth.",
                       "Per-tool counts overlap; never sum them as unique calls.",
                       "Skill read attempts are not successful activation.",
                       "Legacy counters and contextual fixtures cannot qualify the organic protocol or adoption."]}


def scan(files, roots, aliases, parents, since, until, default, exclusions=None, controls=None):
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
    result = {"totals": totals, "registered_totals": registered, "by_lane": dict(lanes), "by_source_class": dict(classes), "diagnostics": dict(diagnostics), "files_scanned": len(metas), "unique_owner_threads": len(seen_owners), "duplicate_owner_files": sum(n-1 for n in file_owners.values()), "source_files": dict(source_files), "threads": thread_info, "registry_roots_missing_rollouts": missing}
    if controls is not None:
        batches = []
        for path in files:
            try:
                encoded = path.read_bytes()
                rows = [json.loads(line) for line in encoded.splitlines() if line.strip()]
            except (OSError, ValueError):
                # Do not drop an unreadable source and certify a smaller census.
                rows, encoded = [], b""
            batches.append({"source_id": str(path), "records": rows,
                            "sha256": hashlib.sha256(encoded).hexdigest()})
        result["organic_controls"] = qualify_records(batches, since=since, until=until, controls=controls)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--since", required=True); parser.add_argument("--until", required=True)
    parser.add_argument("--sessions", default="~/.codex/sessions")
    parser.add_argument("--state", default="~/.local/state/native-agent-stack")
    parser.add_argument("--hcom-db", default="~/.hcom/hcom.db")
    parser.add_argument("--historical-registry"); parser.add_argument("--out")
    parser.add_argument("--first-turn-boundaries")
    parser.add_argument("--organic-controls", help="explicit versioned Q6 control document; references are declarations, not acceptance")
    args = parser.parse_args(); since, until = instant(args.since), instant(args.until)
    if since >= until:
        parser.error("since must precede until")
    roots, aliases, parents = registry(args.hcom_db, args.historical_registry)
    exclusions, exclusion_notes = load_exclusions(args.first_turn_boundaries)
    controls = json.loads(Path(args.organic_controls).read_text()) if args.organic_controls else None
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
        **scan(files, roots, aliases, parents, since, until, args.sessions, exclusions, controls=controls),
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
    if controls is not None:
        report["organic_acceptance"]["contextual_control_status"] = report["organic_controls"]["status"]
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
