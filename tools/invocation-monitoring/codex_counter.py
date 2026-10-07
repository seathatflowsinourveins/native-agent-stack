#!/usr/bin/env python3
"""Count completed native Codex items; never infer MCP calls from JavaScript.

Sources: installed openai/codex 0.160.1 rollout item_completed records and
cc-codex-native-invoke-probe.py (CC v1, 2026-10-06, extended without editing).
Shell/parent decoding reuses tools/skill-usage/skill_usage.py, whose references
name openai/codex rust-v0.157.1 core/src/shell.rs and protocol/src/protocol.rs.
All read-site counts are STATIC observations, not proof the read executed.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import sqlite3
import subprocess
import warnings
from functools import lru_cache

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


def python_reads(code):
    """Resolve literal paths and simple path variables at AST read sites."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            tree = ast.parse(code)
    except (SyntaxError, ValueError):
        return Counter(), 1
    env = {}
    def value(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.Name):
            return env.get(node.id, "")
        if isinstance(node, ast.Call) and node.args:
            name = getattr(node.func, "id", getattr(node.func, "attr", ""))
            if name in {"Path", "PurePath", "expanduser"}:
                return value(node.args[0])
        if isinstance(node, ast.BinOp):
            a, b = value(node.left), value(node.right)
            if a and b:
                return a.rstrip("/") + "/" + b if isinstance(node.op, ast.Div) else a + b if isinstance(node.op, ast.Add) else ""
        return ""
    counts = Counter()
    for node in sorted(ast.walk(tree), key=lambda n: (getattr(n, "lineno", 0), getattr(n, "col_offset", 0))):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    env[target.id] = value(node.value)
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        path = value(node.args[0]) if isinstance(f, ast.Name) and f.id == "open" and node.args else ""
        if isinstance(f, ast.Attribute) and f.attr in {"read_text", "read_bytes", "open"}:
            path = value(f.value)
        if path and getattr(f, "id", getattr(f, "attr", "")) == "open":
            mode = value(node.args[1]) if len(node.args) > 1 else "r"
            mode = next((value(k.value) for k in node.keywords if k.arg == "mode"), mode)
            if any(flag in mode for flag in "wax"):
                continue
        counts.update(SKILL.findall(path))
    return counts, 0


def shell_reads(command):
    script = _USAGE.shell_script(command)
    counts, unknown = Counter(), 0
    # Literal Python -c and Python heredocs are parsed as Python, not shell data.
    for match in re.finditer(r"\bpython(?:3)?\b[^\n]*<<-?\s*['\"]?(\w+)['\"]?[^\n]*\n(.*?)\n\1\b", script, re.S):
        found, bad = python_reads(match.group(2)); counts.update(found); unknown += bad
    for segment in re.split(r"[\n;]|&&|\|\|", script):
        try:
            words = shlex.split(segment)
        except ValueError:
            continue
        while words and (re.match(r"^[A-Za-z_]\w*=", words[0]) or words[0] in {"env", "rtk", "proxy", "--shell"} or words[0].startswith("-")):
            words.pop(0)
        if not words:
            continue
        program = os.path.basename(words[0])
        if program in READERS:
            counts.update(SKILL.findall(" ".join(words[1:])))
        elif program in {"bash", "sh", "zsh"} and len(words) > 2 and words[1] in {"-c", "-lc"}:
            found, bad = shell_reads(words); counts.update(found); unknown += bad
        elif program in {"python", "python3"} and "-c" in words:
            index = words.index("-c") + 1
            if index < len(words):
                found, bad = python_reads(words[index]); counts.update(found); unknown += bad
    return counts, unknown


@lru_cache(maxsize=512)
def javascript_reads(code, language):
    """Maintained ast-grep parser selects real calls, excluding strings/comments."""
    binary = shutil.which("ast-grep")
    if not binary:
        return Counter(), int("SKILL.md" in code)
    try:
        result = subprocess.run([binary, "run", "-l", language, "-k", "call_expression", "--stdin", "--json=compact"], input=code, text=True, capture_output=True, timeout=10)
        if result.returncode not in (0, 1):
            return Counter(), int("SKILL.md" in code)
        calls = json.loads(result.stdout or "[]")
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return Counter(), int("SKILL.md" in code)
    counts = Counter()
    for call in calls:
        match = re.match(r"^(?:[\w$.]+\.)?(?:readFileSync|readFile)\s*\(\s*(['\"])(.*?)\1", call.get("text", ""), re.S)
        if match:
            counts.update(SKILL.findall(match.group(2)))
    return counts, int("SKILL.md" in code and not counts)


def item_reads(item):
    if item.get("type") == "CommandExecution":
        return shell_reads(item.get("command", ""))
    args = item.get("arguments") or {}
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except ValueError:
            return Counter(), 1
    if not isinstance(args, dict) or not str(item.get("tool", "")).startswith("ctx_execute"):
        return Counter(), 0
    language, code = args.get("language"), args.get("code", "")
    if language == "python":
        return python_reads(code)
    if language == "shell":
        return shell_reads(code)
    if language in {"javascript", "typescript"}:
        return javascript_reads(code, language)
    return Counter(), int("SKILL.md" in code)


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
    return {"counts": Counter(), "skill_static_read_sites": Counter(), "skill_user_injections": Counter()}


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
                counters = Counter({"item:" + str(kind): 1})
                if kind == "McpToolCall":
                    counters["mcp:" + str(item.get("server"))] += 1
                    counters["mcp_tool:" + str(item.get("server")) + "/" + str(item.get("tool"))] += 1
                    if item.get("status") not in (None, "completed", "Completed"):
                        counters["mcp_fail"] += 1
                elif kind == "CommandExecution":
                    counters["cmd"] += 1
                    counters["rtk"] += int(bool(re.match(r"\s*(?:\w+=\S+\s+|env\s+)*rtk\b", _USAGE.shell_script(item.get("command", "")))))
                elif kind == "Extension" and item.get("kind") == "web.search":
                    counters["web_search"] += 1
                reads, unknown = item_reads(item)
                diagnostics["unresolved_static_read_code"] += unknown
                target["raw"]["counts"].update(counters); target["raw"]["skill_static_read_sites"].update(reads)
                classes[category]["counts"].update(counters); classes[category]["skill_static_read_sites"].update(reads)
                organic = category in {"default_native", "private_native_home"} and canon is not None
                all_prompts = turn_names.get(payload.get("turn_id"), prompt_names)
                organic &= not (kind == "McpToolCall" and (item.get("server") in all_prompts or item.get("tool") in all_prompts))
                for start, end, reason in (exclusions or {}).get(lane, []):
                    applies = reason == "relaunch_first_turn" or (kind == "McpToolCall" and str(item.get("server", "")).replace("_", "-") in {"chrome-devtools", "promptfoo"})
                    if applies and start <= stamp and (end is None or stamp <= end):
                        organic = False; diagnostics["excluded_" + reason] += 1
                if organic:
                    target["organic"]["counts"].update(counters); target["organic"]["skill_static_read_sites"].update(reads)
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
    report = {"schema_version": 2, "evidence_class": "native_completed_item_observation", "window": {"since": args.since, "until": args.until, "bounds": "[since,until)"}, "client_reference": "openai/codex 0.160.1", "rules": {"identity": "first native owner id + native parent edges + hcom registry; no cwd lane inference", "dedup": "canonical thread + completed type + item id; owner id globally shared across files", "skill_reads": "static read sites, not proof of executed loads", "organic": "PROVISIONAL: registered native homes, lexical tool-name filter, relaunch and readback exclusion intervals", "mtime_filter": False}, "organic_acceptance": {"status": "provisional_not_final_measurement", "all_turn_prompts_and_coop_blocks": "not_yet_fully_resolved", "staged_steers_understanding_guidance": "not_yet_measured", "first_turn_boundaries_loaded": bool(args.first_turn_boundaries), "boundary_notes": exclusion_notes}, "registry": {"live_roots": sum(r["identity_source"] == "hcom_live" for r in roots.values()), "historical_only_roots": sum(r["identity_source"] == "hcom_historical" for r in roots.values())}, "session_homes_discovered": len(homes), **scan(files, roots, aliases, parents, since, until, args.sessions, exclusions), "limits": ["Static read-site evaluation is bounded to literal paths and simple Python path variables.", "Organic counters are provisional; zero cannot establish non-use.", "All prompts of a turn and externally referenced cooperation guidance are not fully resolved.", "Standing steer understanding-guidance counts are not yet measured.", "Absent native completed-item records remain unknown, not zero execution."]}
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
