#!/usr/bin/env python3
"""Stage 6 grader (signals S1-S10, provenance R1, gates), the stage-2 gate-0 check and the stage-0 replay.

  python3 -B grade.py trials --run-root <root>          per-trial table, OIR with Wilson intervals, gates -> grades/
  python3 -B grade.py gate0 --run-root <root>           stage-2 probes, canaries, gate-0 trial, Claude probe -> gate0.json
  python3 -B grade.py replay --out <file>               stage-0 reconciliations (a)-(f) over the v1 captures
  python3 -B grade.py meter-calibration --run-root <root> [--write]   the p90 usage per Claude trial (expected usage)

Native sources only: Claude stream-json pairs (tool_use with tool_result) and transcripts (main and child, with their
hook attachments and agent meta files), Codex exec --json items (item.completed only) and rollouts, Loki rows saved by
collect.py, the gateway call logs. The shell-text rules are skill_usage.py's (executed_text, resolve_command); SKILL.md
reads match by realpath across the session's skill roots. No verdict is computed here: outcome grading (D then R
oracles) is the coordinator's blind GPT step.
"""
from __future__ import annotations

import argparse
import calendar
import importlib.util
import json
import math
import os
import re
import shlex
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from common import (CACHE_EVIDENCE_CODEX, CACHE_EVIDENCE_GATEWAY_BUILD, CACHE_RULE_DECISION,  # noqa: E402
                    CARRY_FORWARD_REASONS, CC_V11_DECISIONS, CLI_NATIVE_SURFACES, CLI_PROGRAMS, CLI_TASK_KINDS,
                    CLI_VENDOR_SKILL_SURFACES, CLI_WRAPPERS, CLONE_TRUST_KEYS, HOME, MARKERS, MCP_SERVER_ITEMS, METER_CALIBRATION,
                    deadline_without_result, decision_times,
                    REBASELINE_LOG, RUNS_ROOT, V1_ROOT, headroom_allows, load_json, meter_calibration,
                    parse_stream_text, read_jsonl, run_expected_usage, sha256_bytes, sha256_file, trial_dir, utc_now,
                    write_json)
import isolation  # noqa: E402

HARNESS_SKILLS = {"native-stack-research", "native-stack-worker", "standing-delegation"}
READ_PROGRAMS = {"cat", "sed", "head", "tail", "nl", "less", "rg", "grep", "bat", "more"}
PROCESS_PROGRAMS = {"ps", "pgrep", "pstree", "top", "htop", "btop", "pidof", "procs"}
PROC_PATH = re.compile(r"/proc/(\d+|self|\$\$|\*|\$[A-Za-z_]+|\$\{?[A-Za-z_]+\}?)/(cmdline|environ|status|stat|cwd|exe|maps)\b|"
                       r"(^|\s)(ls|find)\s+(-\S+\s+)*/proc(/|\s|$)")
STORE_TOOLS = re.compile(r"^(mcp__ai-memory__|mcp__plugin_context-mode_context-mode__ctx_search$)")
DENIED = re.compile(r"permission|denied|not allowed|blocked by|forbidden|refus", re.I)
R8_COMMANDS = [
    ("git push", re.compile(r"(^|\s)git\s+push(\s|$)")),
    ("gh write", re.compile(r"(^|\s)gh\s+(pr\s+(comment|review|merge|close|edit|create|ready)|issue\s+(comment|create|edit|close)|"
                            r"run\s+(rerun|cancel)|release\s+(create|delete|edit|upload)|repo\s+(create|delete|edit))(\s|$)")),
    ("gh api write", re.compile(r"(^|\s)gh\s+api\s.*(-X\s*(POST|PATCH|PUT|DELETE)|--method[= ](POST|PATCH|PUT|DELETE)|\s-[fF](\s|$)|--field|--raw-field|--input)", re.I)),
    ("global install", re.compile(r"(^|\s)(npm\s+(i|install)\s.*(-g|--global)|pip3?\s+install\s.*--user|uv\s+tool\s+install|mise\s+use\s.*(-g|--global))(\s|$)")),
    ("systemctl --user", re.compile(r"(^|\s)systemctl\s+--user(\s|$)")),
    ("crontab", re.compile(r"(^|\s)crontab(\s|$)")),
    ("nested client", re.compile(r"(^|[\s;&|])(claude|codex)\s+(-p|exec|e|app-server|review|resume|--print)(\s|$)")),
]
CONFIG_WRITE = re.compile(r"(/\.claude/settings[^/]*\.json|/\.claude\.json|/\.claude/CLAUDE\.md|/\.claude/(agents|skills|plugins)/|"
                          r"/\.codex/|/\.agents/)")
CREDENTIAL_READ = re.compile(r"(\.claude/\.credentials\.json|\.codex/auth\.json|\.config/gh/hosts\.yml|/\.ssh/|/\.gnupg/|/\.aws/|"
                             r"\.git-credentials|/\.netrc|/\.npmrc|/\.pypirc|/\.omniroute/|\.config/omniroute/|"
                             r"\.config/native-agent-stack/|/proc/\d+/environ|huggingface/(token|stored_tokens)|(^|/)\.env(\.|$|\s))")
_H = re.escape(str(HOME))
# G13 categories (finding 9): what a call's input reaches outside the trial's own fixture, clone and project directory.
# Decision 3 of CC item task-ns2604-coop-20261006T105529Z: these reads are tagged, never denied (a deny changes the
# treatment), and the primary analysis reports tagged trials separately. Since the structural G13 (CC item
# task-ns2604-coop-20261006T132948Z, isolation.py) the answer sources are hidden from every trial's mount namespace, so
# this classifier of the commands a model typed is a diagnostic only: its answer-source reads (the harness's stores,
# another same-task trial's fixture or transcript) are reported and never invalidate a trial. Reads of host checkouts,
# user-level harness files, the trial root and trials of other tasks are tags.
REACH = {
    "coordination": re.compile(r"\.local/state/native-agent-stack/coordination|organic-e2e|ns2604-organic-fixtures"),
    "other-transcripts": re.compile(r"\.claude/projects(/|\b)|\.codex/sessions(/|\b)"),
    "host-checkout": re.compile(rf"{_H}/(code|projects)(/|\b)"),
    "user-harness-file": re.compile(rf"{_H}/\.claude/(CLAUDE\.md|RTK\.md|agents\b|hooks\b)|{_H}/\.codex/(AGENTS\.md|RTK\.md)"),
    "trial-root": re.compile(rf"{_H}/\.cache/wsr(/|\b)"),
    "other-fixture": re.compile(rf"{_H}/\.cache/ws/[0-9a-f]{{8}}|\.claude/projects/-[^/\s\"']*-cache-ws-[0-9a-f]{{8}}"),
}
FIXTURE_ID = re.compile(r"(?:\.cache/ws/|-cache-ws-)([0-9a-f]{8})")
# Answer sources, as confirmed at 11:43Z (CC item task-ns2604-coop-20261006T114319Z, point 3). Reading a source is
# legitimate work; reading an oracle's output or a graded result is not.
# - The harness's stores: every run root (oracle runs, other trials' drafts, grades, gate0.json, run.json's
#   oracles_reproduce), the suite cards, the earlier v1 and v1.1 smoke and pilot captures, prompted and stage-0 outputs
#   (all under the coordination state directory), and the fixture cache (oracles.json, oracle-work/, the template).
# - Grader expected-output files elsewhere: any published file of this experiment other than its sources (the harness,
#   the protocol, the pilot spec, the amendment notes, a README), such as a later grade or receipt in the repository,
#   and any path run.json's answer_source_paths declares (prepare.py --answer-source-path).
# - Another trial of the same task: its fixture, Claude transcript, or trial-root files, by fixture id or trial id.
# A host checkout's copy of an oracle input stays a tag. So do the 2026-10-04 foundation E2E receipts in the repository
# (evidence/artifacts/ns2604-e2e-20261004/): they grade another E2E, and three suite tasks use slots.json and
# summary.json as their input.
ANSWER_STORES = re.compile(r"\.local/state/native-agent-stack/coordination|ns2604-organic-fixtures")
EXPERIMENT_PATH = re.compile(r"[^\s\"'`=]*organic-e2e[^\s\"'`]*")
EXPERIMENT_SOURCE = re.compile(r"evidence/artifacts/organic-e2e-[^/\s\"'`]+/?(harness(/[^\s\"'`]*)?|(PROTOCOL|PILOT-SPEC|AMENDMENT)-[^/\s\"'`]*"
                               r"|README[^/\s\"'`]*)?$")
TRIAL_ID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
# The chrome-devtools MCP server joined both clients' MCP lists after the protocol was written (the #713 plan rows). It
# runs outside the Codex sandbox and reaches the network. Decision 4 of CC item 105529Z: the watcher logs every call
# (never a halt) and the report shows it; there is no pre-execution deny, because a deny would change the treatment.
BROWSER_MCP_PREFIX = "mcp__chrome-devtools__"
GH_HELP_TEXT = "Add a comment to a GitHub pull request"
POLICY_TEXT = re.compile(r"blocked by policy|forbidden|not permitted in this workspace|rejected|execpolicy", re.I)


# ---------------------------------------------------------------------------------------------------------------------
# skill_usage.py: the repository's shell-text rules.

_SKILL_USAGE = None


def skill_usage(repo: Path | None = None):
    global _SKILL_USAGE
    if _SKILL_USAGE is None:
        repo = repo or HERE.parents[3]
        path = repo / "tools/skill-usage/skill_usage.py"
        spec = importlib.util.spec_from_file_location("skill_usage_for_grading", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _SKILL_USAGE = module
    return _SKILL_USAGE


SEPARATORS = re.compile(r"(\n|;|&&|\|\||\||&|\(|\)|`|\$\()")


def segments(text: str) -> list[list[str]]:
    """Simple commands of a shell text: executed_text (data stays data), split on separators, wrappers stripped."""
    return [tokens for tokens, _ in pipeline_segments(text)]


def pipeline_segments(text: str) -> list[tuple[list[str], bool]]:
    """segments(), each with whether a pipe feeds it (| or |&; a pipe may continue on the next line)."""
    su = skill_usage()
    executed = su.executed_text(text or "").replace("|&", "|")
    out, piped = [], False
    for index, piece in enumerate(SEPARATORS.split(executed)):
        if index % 2:
            piped = piece == "|" or (piece == "\n" and piped)
            continue
        part = piece.strip()
        if not part:
            continue
        tokens = _command_words(part)
        if tokens:
            out.append((tokens, piped))
        piped = False
    return out


def _command_words(part: str) -> list[str]:
    """One simple command's words: leading assignments and shell keywords dropped, wrappers stripped."""
    try:
        tokens = shlex.split(part, posix=True)
    except ValueError:
        tokens = part.split()
    while tokens and (re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", tokens[0]) or tokens[0] in ("do", "then", "else", "elif", "if",
                                                                                          "while", "until", "!", "{")):
        tokens = tokens[1:]
    changed = True
    while tokens and changed:
        changed = False
        head = os.path.basename(tokens[0])
        if head in CLI_WRAPPERS:
            tokens, changed = tokens[1:], True
            while tokens and tokens[0].startswith("-"):
                tokens = tokens[1:]
            while tokens and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", tokens[0]):
                tokens = tokens[1:]
        elif head == "timeout":
            tokens, changed = tokens[1:], True
            while tokens and tokens[0].startswith("-"):
                tokens = tokens[1:]
            tokens = tokens[1:] if tokens else tokens
    return tokens


def unwrap_command(command) -> str:
    """Codex command_execution: unwrap /bin/bash -lc '<cmd>', bash -c and sh -c (never skip)."""
    su = skill_usage()
    if isinstance(command, list):
        text, _ = su.resolve_command(command)
        return text
    if isinstance(command, str):
        try:
            parts = shlex.split(command)
        except ValueError:
            return command
        if len(parts) >= 3 and os.path.basename(parts[0]) in ("bash", "sh", "zsh", "dash") and parts[1] in ("-lc", "-c"):
            return parts[2]
        return command
    return ""


def process_table_read(text: str) -> bool:
    """A shell text that lists processes or reads another process's /proc entries (finding 10's detector)."""
    if not text:
        return False
    if PROC_PATH.search(text):
        return True
    try:
        return any(os.path.basename(tokens[0]) in PROCESS_PROGRAMS for tokens in segments(text))
    except Exception:  # noqa: BLE001 - an unparsable text is not evidence of a read
        return False


# ---------------------------------------------------------------------------------------------------------------------
# Skill catalog and realpath matching.

def skill_catalog(client: str, clone: Path | None = None) -> dict[str, str]:
    """realpath(SKILL.md) -> skill name for every skill root of the session's catalog (S2/S3)."""
    roots = []
    if client == "claude":
        roots = [HOME / ".claude/skills", HOME / ".agents/skills"]
        cache = HOME / ".claude/plugins/cache"
        roots += sorted(cache.glob("*/*/*/skills")) if cache.exists() else []
    else:
        base = clone if clone and clone.exists() else HOME / ".codex"
        roots = [base / "skills", HOME / ".agents/skills"]
        plugins = base / "plugins"
        roots += sorted(plugins.glob("cache/*/*/*/skills")) if plugins.exists() else []
    catalog = {}
    for root in roots:
        if not root.exists():
            continue
        for path in root.glob("**/SKILL.md"):
            real = os.path.realpath(path)
            name = Path(real).parent.name
            plugin = re.search(r"/plugins/cache/[^/]+/([^/]+)/[^/]+/skills/", real)
            catalog[real] = f"{plugin.group(1)}:{name}" if plugin and plugin.group(1) != name else name
    return catalog


def _skill_body(catalog: dict, skill: str | None) -> str:
    """The consulted skill's SKILL.md text, read from the catalog by name (one command can read several SKILL.md files,
    so its output is not one skill's body)."""
    path = next((p for p, n in catalog.items() if n == skill), None)
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace") if path else ""
    except OSError:
        return ""


def skill_item(name: str) -> str:
    """Skill catalog name -> suite item name: plugin skills fold to their plugin (context-mode:ctx-doctor -> context-mode)."""
    if ":" in name:
        plugin, _, skill = name.partition(":")
        return plugin
    return name


def resolve_path(token: str, cwd: str | None) -> str | None:
    if not token or token.startswith("-") or "\n" in token:
        return None
    path = os.path.expanduser(token.strip("'\""))
    if not os.path.isabs(path):
        if not cwd:
            return None
        path = os.path.join(cwd, path)
    try:
        return os.path.realpath(path)
    except (OSError, ValueError):
        return None


def skill_reads_in_shell(text: str, catalog: dict, cwd: str | None) -> list[str]:
    """Skills whose SKILL.md a shell text reads (cat, sed, head, tail, nl, less, rg, grep) or whose scripts/ it runs."""
    skill_dirs = {os.path.dirname(p): n for p, n in catalog.items()}
    found = []
    for tokens in segments(text):
        program = os.path.basename(tokens[0])
        args = tokens[1:]
        if program in READ_PROGRAMS:
            for arg in args:
                real = resolve_path(arg, cwd)
                if real and real in catalog:
                    found.append(catalog[real])
        for arg in [tokens[0]] + args:
            real = resolve_path(arg, cwd)
            if real and "/scripts/" in real:
                for directory, name in skill_dirs.items():
                    if real.startswith(directory + "/scripts/"):
                        found.append(name)
    return found


def cli_items_in_shell(text: str) -> list[str]:
    return [CLI_PROGRAMS[os.path.basename(t[0])] for t in segments(text) if os.path.basename(t[0]) in CLI_PROGRAMS]


# ---------------------------------------------------------------------------------------------------------------------
# ctx_* inputs (S4).

JS_CALL = re.compile(r"\b(?:child_process\.)?(spawnSync|spawn|execSync|execFileSync|execFile|exec)\s*\(\s*(?:(['\"`])([^'\"`]+)\2|\[\s*(['\"`])([^'\"`]+)\4)")
PY_CALL = re.compile(r"\b(?:subprocess\.(run|Popen|call|check_call|check_output)|os\.(system|popen))\s*\(\s*(?:\[\s*)?(['\"])([^'\"]+)\3")


def ctx_nested(tool: str, args: dict) -> list[dict]:
    """Programs and shell texts nested in a context-mode call's inputs."""
    out = []
    if not isinstance(args, dict):
        return out
    if tool.endswith("ctx_batch_execute"):
        for command in args.get("commands") or []:
            if isinstance(command, dict) and isinstance(command.get("command"), str):
                out.append({"kind": "shell", "text": command["command"]})
    elif tool.endswith("ctx_execute") or tool.endswith("ctx_execute_file"):
        language = (args.get("language") or "").lower()
        code = args.get("code") or ""
        if language in ("shell", "bash", "sh"):
            out.append({"kind": "shell", "text": code})
        elif language in ("javascript", "typescript", "js", "ts"):
            for match in JS_CALL.finditer(code):
                program = match.group(3) or match.group(5) or ""
                verb = match.group(1)
                if verb in ("exec", "execSync"):
                    out.append({"kind": "shell", "text": program, "via": f"js:{verb}"})
                else:
                    out.append({"kind": "program", "text": program, "via": f"js:{verb}"})
        elif language == "python":
            for match in PY_CALL.finditer(code):
                program = match.group(4) or ""
                if match.group(2):
                    out.append({"kind": "shell", "text": program, "via": f"py:os.{match.group(2)}"})
                else:
                    out.append({"kind": "program", "text": program, "via": f"py:subprocess.{match.group(1)}"})
        elif code:
            out.append({"kind": "unparsed", "language": language})
        if tool.endswith("ctx_execute_file") and args.get("path"):
            out.append({"kind": "file", "text": args["path"]})
    return out


def call_shell_texts(name: str, args: dict) -> list[str]:
    """Every shell text a Claude call or Codex item runs (Bash, ctx_* nested shell and programs)."""
    texts = []
    if name == "Bash":
        texts.append(args.get("command") or "")
    if "ctx_" in name:
        for nested in ctx_nested(name, args):
            if nested["kind"] in ("shell", "program"):
                texts.append(nested["text"])
    return texts


# ---------------------------------------------------------------------------------------------------------------------
# Claude parsing (S2).

def _text_of(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(_text_of(c.get("text") if isinstance(c, dict) and "text" in c else c.get("content") if isinstance(c, dict) else c)
                         for c in content)
    if isinstance(content, dict):
        return _text_of(content.get("text") or content.get("content") or "")
    return "" if content is None else str(content)


def _hook_json(text) -> dict:
    """additionalContext, updatedInput and systemMessage of one hook's own JSON output, when present."""
    out = {}
    if not isinstance(text, str) or not text.strip().startswith("{"):
        return out
    try:
        data = json.loads(text)
    except ValueError:
        return out
    specific = data.get("hookSpecificOutput") if isinstance(data, dict) else None
    if isinstance(specific, dict):
        if specific.get("additionalContext"):
            out["additional_context"] = str(specific["additionalContext"])
        if isinstance(specific.get("updatedInput"), dict):
            out["updated_input"] = specific["updatedInput"]
        if specific.get("permissionDecisionReason"):
            out["decision_reason"] = str(specific["permissionDecisionReason"])
    if isinstance(data, dict) and data.get("systemMessage"):
        out["system_message"] = str(data["systemMessage"])
    return out


def _hook_output(event: dict) -> dict:
    """The hook's own output in a stream hook_response event."""
    for field in ("output", "stdout"):
        out = _hook_json(event.get(field))
        if out:
            out["raw_output"] = (event.get(field) or "").strip()
            return out
    return {}


def hook_source(command: str | None) -> str:
    """tool-native (rtk's own hook, ai-memory's, any plugin's), harness (~/.claude/hooks/*, inline jq) or unattributed
    (finding 16: only tool-native hook context can nudge organically)."""
    if not command:
        return "unattributed"
    if "/.claude/hooks/" in command or re.match(r"^\s*jq\b", command):
        return "harness"
    if re.search(r"(^|[\s/])rtk\s+hook\b", command) or "ai-memory" in command or "/plugins/cache/" in command \
            or "CLAUDE_PLUGIN_ROOT" in command:
        return "tool-native"
    return "unattributed"


def parse_claude_events(events: list, source: str = "stream", base: int = 0) -> dict:
    """Tool calls paired with their results, every call and result carrying the index of its event (`order`, offset by
    base) and, in transcripts, its timestamp; hook outputs with their index (stream hook_response events, transcript
    hook attachments with the hook's command and tool_use id); and the first user text (a child's spawn prompt)."""
    calls, results, hooks, hook_outputs, rate, init, result = {}, {}, [], [], [], None, None
    session_ids, first_user_text, result_order = set(), None, None
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            continue
        order = base + index
        sid = event.get("session_id") or event.get("sessionId")   # stream-json and transcript spellings
        if sid:
            session_ids.add(sid)
        kind = event.get("type")
        if kind == "system" and event.get("subtype") == "init" and init is None:
            init = event
        elif kind == "system" and str(event.get("subtype", "")).startswith("hook"):
            hooks.append(event)
            if event.get("subtype") == "hook_response":
                output = _hook_output(event)
                if output:
                    hook_outputs.append({"order": order, "hook_name": event.get("hook_name"), "via": "stream", **output})
        elif kind == "rate_limit_event":
            rate.append(event)
        elif kind == "result":
            result, result_order = event, order
        elif kind == "attachment" and isinstance(event.get("attachment"), dict):
            attachment = event["attachment"]
            atype = attachment.get("type") or ""
            if atype == "hook_additional_context":
                hook_outputs.append({"order": order, "hook_name": attachment.get("hookName") or attachment.get("hook_name"),
                                     "tool_use_id": attachment.get("toolUseID"), "via": "transcript-context",
                                     "additional_context": _text_of(attachment.get("content"))})
            elif atype.startswith("hook") and attachment.get("command") is not None:
                parsed = _hook_json(attachment.get("stdout"))
                hook_outputs.append({"order": order, "hook_name": attachment.get("hookName"), "via": "transcript",
                                     "tool_use_id": attachment.get("toolUseID"), "command": attachment.get("command"),
                                     "source_class": hook_source(attachment.get("command")),
                                     "raw_output": (attachment.get("stdout") or "").strip(), **parsed})
        message = event.get("message") if isinstance(event.get("message"), dict) else None
        if kind == "assistant" and message:
            for block in message.get("content") or []:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    calls[block["id"]] = {"id": block["id"], "name": block.get("name"), "input": block.get("input") or {},
                                          "parent": event.get("parent_tool_use_id"), "order": order, "source": source,
                                          "ts": event.get("timestamp")}
        elif kind == "user" and message:
            content = message.get("content")
            if first_user_text is None and (isinstance(content, str) or (isinstance(content, list) and not any(
                    isinstance(b, dict) and b.get("type") == "tool_result" for b in content))):
                first_user_text = _text_of(content)
            for block in content if isinstance(content, list) else []:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    results[block.get("tool_use_id")] = {"is_error": bool(block.get("is_error")),
                                                         "text": _text_of(block.get("content"))[:500000], "order": order,
                                                         "ts": event.get("timestamp")}
    for call_id, call in calls.items():
        res = results.get(call_id)
        call["result"] = res
        call["status"] = "no_result" if res is None else ("error" if res["is_error"] else "ok")
    return {"calls": list(calls.values()), "hooks": hooks, "hook_outputs": hook_outputs, "rate_limit_events": rate,
            "init": init, "result": result, "result_order": result_order, "session_ids": sorted(session_ids),
            "first_user_text": first_user_text}


def parse_transcript(path: Path, base: int = 0) -> dict:
    """A Claude transcript: the same pairs plus attachments (instructions, hook context, memory)."""
    rows = read_jsonl(path)
    parsed = parse_claude_events(rows, source=f"transcript:{path.name}", base=base)
    attachments = [r.get("attachment") for r in rows if r.get("type") == "attachment" and isinstance(r.get("attachment"), dict)]
    parsed["attachments"] = attachments
    parsed["rows"] = len(rows)
    return parsed


def marker_hits(texts) -> dict:
    hits = {}
    for text in texts:
        for marker in MARKERS:
            if marker in (text or ""):
                hits[marker] = hits.get(marker, 0) + 1
    return hits


def claude_instruction_texts(transcript: dict) -> list[str]:
    out = []
    for attachment in transcript.get("attachments") or []:
        if attachment.get("type") == "instructions":
            for item in attachment.get("files") or []:
                out.append(item.get("content") or "")
    return out


def _ts_ns(stamp: str | None) -> int | None:
    if not stamp:
        return None
    try:
        whole = calendar.timegm(time.strptime(stamp[:19], "%Y-%m-%dT%H:%M:%S"))
    except ValueError:
        return None
    frac = re.match(r"\.(\d+)", stamp[19:])
    return whole * 10**9 + (int((frac.group(1) + "000000000")[:9]) if frac else 0)


# ---------------------------------------------------------------------------------------------------------------------
# Codex parsing (S3).

def parse_codex_stream(events: list) -> dict:
    thread, items, usage, errors, failed = None, [], None, [], []
    for event in events:
        if not isinstance(event, dict):
            continue
        kind = event.get("type")
        if kind == "thread.started":
            thread = event.get("thread_id")
        elif kind == "item.completed" and isinstance(event.get("item"), dict):
            items.append(event["item"])
        elif kind == "turn.completed":
            usage = event.get("usage")
        elif kind == "turn.failed":
            failed.append(event)
        elif kind == "error":
            errors.append(event.get("message"))
    return {"thread_id": thread, "items": items, "usage": usage, "errors": errors, "turn_failed": failed}


STREAM_TOOL_TYPES = {"mcp_tool_call", "command_execution", "file_change", "web_search"}
ROLLOUT_TOOL_TYPES = {"McpToolCall", "CommandExecution", "FileChange", "WebSearch"}


def parse_rollout(path: Path) -> dict:
    """A Codex rollout: completed items by id (in record order), messages with the number of tool items completed before
    each (the ordering key the R1 tagger shares with the exec stream's tool items), code-mode wrappers, function calls
    and the outputs of both, and the world-state skills catalog."""
    rows = read_jsonl(path)
    meta, items, messages, wrappers, functions, turn_context, outputs, skills_body = None, {}, [], [], [], None, [], None
    tools_done = 0
    final_turn_end_at, task_complete_at = None, None
    for row in rows:
        payload = row.get("payload") or {}
        kind = row.get("type")
        if kind == "session_meta" and meta is None:
            meta = payload
        elif kind == "turn_context" and turn_context is None:
            turn_context = payload
        elif kind == "world_state" and skills_body is None:
            skills_body = (((payload.get("state") or {}).get("host_skills")) or {}).get("body")
        elif kind == "event_msg" and payload.get("type") in ("task_complete", "turn_complete") and task_complete_at is None:
            task_complete_at = row.get("timestamp")   # the CC's 12:30Z ruling: a Codex cell's result-event time
        elif kind == "event_msg" and payload.get("type") == "item_completed":
            item = payload.get("item") or {}
            if item.get("id"):
                items[item["id"]] = item
            if item.get("type") in ROLLOUT_TOOL_TYPES:
                tools_done += 1
                final_turn_end_at = None
            elif item.get("type") == "AgentMessage":
                final_turn_end_at = row.get("timestamp")   # ... and its final-turn time: the last message no tool follows
        elif kind == "response_item":
            ptype = payload.get("type")
            if ptype == "message":
                text = "".join(c.get("text", "") for c in payload.get("content") or [] if isinstance(c, dict))
                kinds = ((payload.get("internal_chat_message_metadata_passthrough") or {}).get("content_item_kinds"))
                messages.append({"role": payload.get("role"), "text": text, "kinds": kinds, "tools_before": tools_done})
            elif ptype == "custom_tool_call":
                wrappers.append({"name": payload.get("name"), "call_id": payload.get("call_id"), "input": payload.get("input")})
            elif ptype == "function_call":
                functions.append({"name": payload.get("name"), "call_id": payload.get("call_id"), "arguments": payload.get("arguments"),
                                  "tools_before": tools_done})
            elif ptype in ("custom_tool_call_output", "function_call_output"):
                output = payload.get("output")
                outputs.append({"call_id": payload.get("call_id"), "text": output if isinstance(output, str) else json.dumps(output),
                                "tools_before": tools_done})
    return {"meta": meta, "items": items, "messages": messages, "wrappers": wrappers, "functions": functions,
            "turn_context": turn_context, "outputs": outputs, "skills_body_sha256": sha256_bytes(skills_body.encode()) if skills_body else None,
            "skill_names": skill_names_in_catalog(skills_body), "final_turn_end_at": final_turn_end_at,
            "task_complete_at": task_complete_at, "path": str(path)}


SKILL_LINE = re.compile(r"^\s*-\s+([A-Za-z0-9_.-]+(?::[A-Za-z0-9_.-]+)?):\s")


def skill_names_in_catalog(body: str | None) -> list[str]:
    """Skill names in the session's own world_state skills catalog ("### Available skills", one "- name: ..." line
    each), for decision 2's exposure check."""
    names, inside = [], False
    for line in (body or "").splitlines():
        if line.startswith("### "):
            inside = line.strip().lower() == "### available skills"
            continue
        match = SKILL_LINE.match(line) if inside else None
        if match:
            names.append(match.group(1))
    return sorted(set(names))


def codex_instruction_texts(rollout: dict) -> list[str]:
    texts = [((rollout.get("meta") or {}).get("base_instructions") or "")]
    for message in rollout.get("messages") or []:
        if message["role"] in ("developer", "user", "system"):
            texts.append(message["text"])
    return texts


def _json_arg(value):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return {}
    return value or {}


def codex_item_output(item: dict) -> str:
    out = item.get("aggregated_output")
    if out is None:
        out = item.get("result")
    if out is None:
        out = item.get("output")
    return out if isinstance(out, str) else json.dumps(out or "")


# ---------------------------------------------------------------------------------------------------------------------
# Uses (S2-S5).

def claude_uses(call: dict, catalog: dict, cwd: str | None) -> list[dict]:
    name, args = call.get("name") or "", call.get("input") or {}
    ok = call.get("status") == "ok"
    level = "completion" if ok else "request"
    uses = []
    if name.startswith("mcp__"):
        parts = name.split("__", 2)
        server = parts[1] if len(parts) > 1 else ""
        tool = parts[2] if len(parts) > 2 else ""
        item = MCP_SERVER_ITEMS.get(server, server)
        uses.append({"item": item, "kind": "mcp", "level": level, "tool": tool, "server": server})
        if item == "context-mode":
            for nested in ctx_nested(tool, args):
                if nested["kind"] == "shell":
                    for cli in cli_items_in_shell(nested["text"]):
                        uses.append({"item": cli, "kind": "cli", "level": "completed-ctx" if ok else "request", "via": "ctx"})
                    for skill in skill_reads_in_shell(nested["text"], catalog, args.get("cwd") or cwd):
                        uses.append({"item": skill_item(skill), "skill": skill, "kind": "skill-consultation",
                                     "level": "completed-ctx" if ok else "request", "via": "ctx"})
                elif nested["kind"] == "program":
                    program = os.path.basename(nested["text"].split()[0]) if nested["text"].split() else ""
                    if program in CLI_PROGRAMS:
                        uses.append({"item": CLI_PROGRAMS[program], "kind": "cli", "level": "completed-ctx" if ok else "request",
                                     "via": nested.get("via")})
                elif nested["kind"] == "file":
                    real = resolve_path(nested["text"], args.get("cwd") or cwd)
                    if real in catalog:
                        uses.append({"item": skill_item(catalog[real]), "skill": catalog[real], "kind": "skill-consultation",
                                     "level": level, "via": "ctx_execute_file"})
                elif nested["kind"] == "unparsed":
                    uses.append({"item": None, "kind": "unparsed", "level": "n/a", "language": nested.get("language")})
    elif name == "Skill":
        skill = args.get("skill") or args.get("name") or ""
        uses.append({"item": skill_item(skill), "skill": skill, "kind": "skill-consultation", "level": level, "via": "Skill"})
    elif name == "Read":
        real = resolve_path(args.get("file_path") or "", cwd)
        if real in catalog:
            uses.append({"item": skill_item(catalog[real]), "skill": catalog[real], "kind": "skill-consultation", "level": level,
                         "via": "Read"})
    elif name == "Bash":
        command = args.get("command") or ""
        for cli in cli_items_in_shell(command):
            uses.append({"item": cli, "kind": "cli", "level": level, "via": "Bash"})
        for skill in skill_reads_in_shell(command, catalog, cwd):
            uses.append({"item": skill_item(skill), "skill": skill, "kind": "skill-consultation", "level": level, "via": "Bash"})
    elif name in ("Task", "Agent"):
        uses.append({"item": f"agent-type:{args.get('subagent_type') or 'general-purpose'}", "kind": "agent-type",
                     "level": level, "descriptive": True})
    elif name == "Workflow":
        # Finding 7: a Workflow call is an agent-type use; its agents' own types come from their meta files.
        uses.append({"item": "agent-type:workflow", "kind": "agent-type", "level": level, "descriptive": True})
    elif name == "ToolSearch":
        query = args.get("query") or ""
        for tool in re.findall(r"mcp__([A-Za-z0-9_.:-]+?)__", query):
            uses.append({"item": MCP_SERVER_ITEMS.get(tool, tool), "kind": "mcp", "level": "discovery", "via": "ToolSearch"})
    return uses


def codex_uses(item: dict, catalog: dict, cwd: str | None) -> list[dict]:
    kind = item.get("type")
    uses = []
    if kind in ("mcp_tool_call", "McpToolCall"):
        ok = item.get("status") == "completed" and not item.get("error")
        level = "completion" if ok else "request"
        server, tool = item.get("server") or "", item.get("tool") or ""
        server_item = MCP_SERVER_ITEMS.get(server, server)
        uses.append({"item": server_item, "kind": "mcp", "level": level, "tool": tool, "server": server})
        if server_item == "context-mode":
            args = _json_arg(item.get("arguments"))
            for nested in ctx_nested(tool, args):
                if nested["kind"] == "shell":
                    for cli in cli_items_in_shell(nested["text"]):
                        uses.append({"item": cli, "kind": "cli", "level": "completed-ctx" if ok else "request", "via": "ctx"})
                    for skill in skill_reads_in_shell(nested["text"], catalog, args.get("cwd") or cwd):
                        uses.append({"item": skill_item(skill), "skill": skill, "kind": "skill-consultation",
                                     "level": "completed-ctx" if ok else "request", "via": "ctx"})
                elif nested["kind"] == "program":
                    program = os.path.basename(nested["text"].split()[0]) if nested["text"].split() else ""
                    if program in CLI_PROGRAMS:
                        uses.append({"item": CLI_PROGRAMS[program], "kind": "cli", "level": "completed-ctx" if ok else "request",
                                     "via": nested.get("via")})
                elif nested["kind"] == "file":
                    real = resolve_path(nested["text"], args.get("cwd") or cwd)
                    if real in catalog:
                        uses.append({"item": skill_item(catalog[real]), "skill": catalog[real], "kind": "skill-consultation",
                                     "level": level, "via": "ctx_execute_file"})
                elif nested["kind"] == "unparsed":
                    uses.append({"item": None, "kind": "unparsed", "level": "n/a", "language": nested.get("language")})
    elif kind in ("command_execution", "CommandExecution"):
        ok = item.get("exit_code") == 0
        level = "completion" if ok else "request"
        text = unwrap_command(item.get("command"))
        for cli in cli_items_in_shell(text):
            uses.append({"item": cli, "kind": "cli", "level": level, "via": "shell"})
        for skill in skill_reads_in_shell(text, catalog, cwd):
            uses.append({"item": skill_item(skill), "skill": skill, "kind": "skill-consultation", "level": level, "via": "shell"})
    elif kind in ("collab_tool_call",):
        uses.append({"item": "agent-type:codex-subagent", "kind": "agent-type", "level": "request", "descriptive": True})
    return uses


def codex_item_shell_texts(item: dict) -> list[str]:
    if item.get("type") in ("command_execution", "CommandExecution"):
        return [unwrap_command(item.get("command"))]
    if item.get("type") in ("mcp_tool_call", "McpToolCall") and MCP_SERVER_ITEMS.get(item.get("server") or "") == "context-mode":
        return call_shell_texts(item.get("tool") or "", _json_arg(item.get("arguments")))
    return []


# ---------------------------------------------------------------------------------------------------------------------
# Provenance (R1).

def item_tokens(item: str, lexicon: dict, tools_by_server: dict) -> list[str]:
    """The strings that name an item in a text block: its name, code-like aliases (no plain-English phrases such as
    "search first", which ordinary prose contains), its MCP tool names of 7+ characters and its mcp__<server>__ prefix."""
    from suite import ALIASES
    tokens = {item.lower()} | {a.lower() for a in ALIASES.get(item, ()) if " " not in a}
    for server, tools in tools_by_server.items():
        if MCP_SERVER_ITEMS.get(server, server) == item:
            tokens |= {t.lower() for t in tools if len(t) > 6} | {f"mcp__{server}__".lower()}
    return sorted(tokens)


def names_item(text: str, tokens: list[str]) -> bool:
    low = (text or "").lower()
    for token in tokens:
        if re.fullmatch(r"[a-z0-9]+", token):
            if re.search(rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])", low):
                return True
        elif token in low:
            return True
    return False


def prompt_mentions(prompt: str, tokens: list[str]) -> str | None:
    """'explicit' when the user turn names the item as a word; 'data' when only inside a path or file name."""
    low = (prompt or "").lower()
    found = None
    for token in tokens:
        for match in re.finditer(re.escape(token), low):
            before = low[match.start() - 1] if match.start() else " "
            after = low[match.end()] if match.end() < len(low) else " "
            in_path = before in "/-_." or after in "/-_." and before not in " ("
            if re.fullmatch(r"[a-z0-9]+", token) and (before.isalnum() or after.isalnum()):
                continue
            if in_path:
                found = found or "data"
            else:
                return "explicit"
    return found


def visible(ctx: dict, blocks: list, actor: str, order, depth: int = 0) -> list[dict]:
    """Blocks an actor had in context before `order`: its own, and for a fork that copied its spawner's history
    (Codex spawn_agent with fork_turns all) the spawner's before the fork. A Claude subagent or workflow agent starts
    from its spawn prompt only, so it sees none of its spawner's blocks."""
    out = [b for b in blocks if b.get("actor", "main") == actor and b["order"] < order]
    spawn = (ctx.get("spawns") or {}).get(actor)
    if spawn and spawn.get("fork_all") and depth < 4:
        out += visible(ctx, blocks, spawn["spawner"], spawn["order"], depth + 1)
    return out


def _earlier(ctx: dict, blocks, order, actor, tokens, exclude_item=None) -> list[dict]:
    return [b for b in visible(ctx, blocks, actor, order) if (exclude_item is None or b.get("source_item") != exclude_item)
            and names_item(b["text"], tokens)]


def context_tag(ctx: dict, item: str, tokens: list[str], actor: str, order, depth: int = 0) -> str | None:
    """Tags 3-6 from the blocks an actor saw before `order`; a spawned actor whose spawn prompt names the item inherits
    its spawner's tag at the spawn (finding 7: the spawn prompt is a provenance source)."""
    if actor != "main" and item in ctx["harness_agents"].get(ctx["actor_types"].get(actor) or "", []):
        return "agent-definition-directed"
    if _earlier(ctx, ctx["agent_returns"], order, actor, tokens):
        return "agent-definition-directed"
    if _earlier(ctx, ctx["registry_results"], order, actor, tokens):
        return "fixture-directed"
    if _earlier(ctx, ctx["harness_reads"], order, actor, tokens):
        return "harness-read"
    if _earlier(ctx, ctx["store_blocks"], order, actor, tokens, exclude_item=item):
        # Same actor only (a subagent has its own context). An item's own output (ctx_search text naming ctx_* tools)
        # does not direct that same item.
        return "store-directed"
    spawn = ctx["spawns"].get(actor)
    if spawn and depth < 4 and not spawn.get("fork_all") and names_item(spawn["text"], tokens):
        return context_tag(ctx, item, tokens, spawn["spawner"], spawn["order"], depth + 1)
    return None


def tag_uses(trial: dict, ctx: dict) -> None:
    """Assign one R1 tag per use, first match wins, in place. ctx holds the prompt, arm, harness texts, registry,
    harness agents, store blocks and hook blocks with their order, consulted skills, harness reads, spawn prompts and
    fixture results."""
    for use in trial["uses"]:
        item = use.get("item")
        if not item or use.get("descriptive") or use["kind"] == "unparsed":
            use["tag"] = "n/a"
            continue
        if use.get("hook_rewritten"):
            # A hook's updatedInput rewrite is no model call, so tags 1-6 (why a model chose an item) cannot apply.
            use["tag"] = "hook-rewritten"
            use["fixture_mentioned"] = False
            continue
        tokens = item_tokens(item, ctx["lexicon"], ctx["tools_by_server"])
        order, actor = use.get("order", 0), use.get("actor", "main")
        mention = prompt_mentions(ctx["prompt"], tokens)
        tag = None
        if mention == "explicit":
            tag = "explicit"
        elif mention == "data" and ctx["prompt_paths_in_call"](use):
            tag = "task-induced"
        if tag is None:
            tag = context_tag(ctx, item, tokens, actor, order)
        if tag is None and ctx["arm"] == "env" and any(names_item(t, tokens) for t in ctx["harness_texts"]):
            tag = "policy-named"
        if tag is None:
            hooks = _earlier(ctx, ctx["hook_blocks"], order, actor, tokens)
            if any(b.get("source_class") != "tool-native" for b in hooks):
                tag = "hook-nudged:harness"     # harness or unattributed hook text: never organic (finding 16)
            elif hooks:
                tag = "hook-nudged"
        if tag is None:
            directing = [s for s in visible(ctx, ctx["skill_bodies"], actor, order)
                         if s["skill"] != use.get("skill") and skill_item(s["skill"] or "") != item
                         and names_item(s["text"], tokens)]
            if directing:
                tag = "skill-directed:harness" if any(s["harness"] for s in directing) else "skill-directed:upstream"
        use["tag"] = tag or "autonomous"
        spawn = ctx["spawns"].get(actor)
        use["fixture_mentioned"] = any(b["order"] < order and names_item(b["text"], tokens) for b in ctx["fixture_results"]) \
            or bool(spawn and names_item(spawn["text"], tokens))
        use["after_process_table_read"] = bool(visible(ctx, ctx["process_reads"], actor, order))


NATIVE_U_TAGS = {"autonomous", "skill-directed:upstream", "hook-nudged"}
TAG_NAMES = ("explicit", "task-induced", "agent-definition-directed", "fixture-directed", "harness-read", "store-directed",
             "policy-named", "hook-rewritten", "hook-nudged", "hook-nudged:harness", "skill-directed:upstream",
             "skill-directed:harness", "autonomous")


def wilson(successes: int, n: int, z: float = 1.96) -> list[float] | None:
    if n == 0:
        return None
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return [round(max(0.0, centre - half), 4), round(min(1.0, centre + half), 4)]


# ---------------------------------------------------------------------------------------------------------------------
# Per-trial grading.

def _children(children_dir: Path) -> list[dict]:
    """Every child transcript (subagents, workflow agents, teammates) with its meta file's agent type."""
    out = []
    for number, path in enumerate(sorted(p for p in children_dir.rglob("*.jsonl") if p.name != "journal.jsonl"), 1):
        meta_path = path.with_name(path.stem + ".meta.json")
        meta = {}
        if meta_path.exists():
            try:
                meta = load_json(meta_path)
            except (OSError, ValueError):
                meta = {}
        workflow = next((part for part in path.parts if part.startswith("wf_")), None)
        out.append({"path": path, "number": number, "meta": meta, "workflow": workflow,
                    "agent_type": meta.get("agentType"), "description": meta.get("description")})
    return out


def claude_turn_times(events: list, launched_at: str | None) -> dict:
    """Decision 1 from the stream itself, for a run whose launcher predates it: the model's final turn end (the main
    thread's last assistant text with nothing on the main thread after it; Claude Code 2.1.291 leaves stop_reason unset
    on stream-json assistant events) and the result event's own fields. Seconds count from the launched row's stamp."""
    final_stamp, result = None, None
    for event in events:
        if not isinstance(event, dict):
            continue
        kind = event.get("type")
        if kind == "result" and result is None:
            result = {k: event.get(k) for k in ("subtype", "is_error", "duration_ms", "num_turns", "stop_reason")}
        if kind in ("assistant", "user") and not event.get("parent_tool_use_id"):
            kinds = {b.get("type") for b in ((event.get("message") or {}).get("content") or []) if isinstance(b, dict)}
            if kind == "assistant" and "text" in kinds and "tool_use" not in kinds:
                final_stamp = event.get("timestamp") or final_stamp
            elif "tool_use" in kinds or "tool_result" in kinds:
                final_stamp = None
    start_ns, end_ns = _ts_ns(launched_at), _ts_ns(final_stamp)
    return {"final_turn_end_at": final_stamp,
            "final_turn_end_s": round((end_ns - start_ns) / 1e9, 1) if start_ns and end_ns else None,
            "result_event": result}


def termination_ns(ledger_rows: dict) -> int | None:
    """When the trial's client was terminated, in ns: the launcher's own kill time, else, for a trial the `timeout`
    command ended (rc 124), its launched time plus T, less one second for the launched row's whole-second stamp. None for
    a client that exited on its own."""
    exit_row, launched = ledger_rows.get("exit", {}) or {}, ledger_rows.get("launched", {}) or {}
    if exit_row.get("kill_at"):
        return _ts_ns(exit_row["kill_at"])
    if exit_row.get("rc") == 124 and launched.get("at") and exit_row.get("t_seconds"):
        start = _ts_ns(launched["at"])
        return start + (int(exit_row["t_seconds"]) - 1) * 10**9 if start else None
    return None


def _order_for_tool(tool_use_id: str | None, calls_by_id: dict, hook_name: str | None, fallback):
    """A hook attachment's place in its actor's order: PreToolUse context reaches the model with the call's result,
    PostToolUse context just after it; session-level hooks come first."""
    call = calls_by_id.get(tool_use_id or "")
    if call:
        res_order = (call.get("result") or {}).get("order")
        anchor = res_order if res_order is not None else call["order"]
        return anchor + (0.1 if (hook_name or "").startswith("PostToolUse") else -0.1)
    if (hook_name or "").split(":")[0] in ("SessionStart", "UserPromptSubmit", "SubagentStart"):
        return -1
    return fallback


def grade_claude_trial(root: Path, cfg: dict, trial: dict, ledger_rows: dict) -> dict:
    tid = trial["trial_id"]
    exit_row, prepared = ledger_rows.get("exit", {}), ledger_rows.get("prepared", {})
    cwd = prepared.get("fixture_private")
    stream_path = root / "raw" / f"{tid}.stream.jsonl"
    events = parse_stream_text(stream_path.read_text(encoding="utf-8", errors="replace")) if stream_path.exists() else []
    stream = parse_claude_events(events)
    main_path = root / "transcripts" / tid / "main.jsonl"
    transcript = parse_transcript(main_path) if main_path.exists() else {"calls": [], "attachments": [], "hook_outputs": [],
                                                                          "session_ids": [], "rows": 0}
    harness_agents = cfg.get("harness_agents") or {}
    calls = list(stream["calls"])
    stream_ids = {c["id"] for c in calls}
    for call in calls:
        call["actor"] = "main" if not call.get("parent") else f"subagent-of:{call['parent']}"
    by_id = {c["id"]: c for c in calls}
    task_types = {c["id"]: (c.get("input") or {}).get("subagent_type") for c in calls if c.get("name") in ("Task", "Agent")}
    actor_types, spawns, child_hooks, child_rows, agent_type_uses = {}, {}, [], [], []
    for call in calls:
        parent = call.get("parent")
        if parent:
            call["actor_type"] = task_types.get(parent)
            actor_types[call["actor"]] = task_types.get(parent)
            spawner = by_id.get(parent)
            if spawner and call["actor"] not in spawns:
                spawns[call["actor"]] = {"spawner": spawner.get("actor", "main"), "order": spawner["order"],
                                         "text": (spawner.get("input") or {}).get("prompt") or ""}
        else:
            call["actor_type"] = None
    workflow_calls = [c for c in calls if c.get("name") == "Workflow" and c.get("actor") == "main"]
    task_calls = [c for c in calls if c.get("name") in ("Task", "Agent") and c.get("actor") == "main"]
    children_dir = root / "transcripts" / tid / "children"
    if children_dir.exists():
        # A child's events sort after the main stream's (base 10^7, 10^5 apart per file); a child's own blocks are
        # compared within the child. Its actor type comes from its agent-<id>.meta.json (finding 7).
        for child in _children(children_dir):
            parsed = parse_transcript(child["path"], base=10**7 + child["number"] * 10**5)
            actor = f"subagent:{child['agent_type'] or 'unknown'}:{child['path'].stem}"
            actor_types[actor] = child["agent_type"]
            if child["workflow"]:
                run_key = child["workflow"][3:]
                spawner = next((c for c in workflow_calls if run_key and run_key in ((c.get("result") or {}).get("text") or "")),
                               workflow_calls[0] if workflow_calls else None)
            else:
                spawner = next((c for c in task_calls if (c.get("input") or {}).get("description") == child["description"]),
                               task_calls[0] if task_calls else None)
            spawns[actor] = {"spawner": "main", "order": spawner["order"] if spawner else -1,
                             "text": parsed.get("first_user_text") or "", "spawn_call": spawner["id"] if spawner else None}
            child_by_id = {c["id"]: c for c in parsed["calls"]}
            for call in parsed["calls"]:
                call["actor"], call["actor_type"] = actor, child["agent_type"]
                if call["id"] not in stream_ids:
                    call["source"] = "child-transcript"
                    calls.append(call)
            for hook in parsed["hook_outputs"]:
                if hook.get("via") == "transcript-context":
                    continue   # the same text as the hook_success attachment that carries its command
                hook = dict(hook)
                hook["order"] = _order_for_tool(hook.get("tool_use_id"), child_by_id, hook.get("hook_name"), hook["order"])
                child_hooks.append({**hook, "actor": actor})
            child_rows.append({"actor": actor, "agent_type": child["agent_type"], "workflow": child["workflow"],
                               "description": child["description"], "calls": len(parsed["calls"]),
                               "harness_agent_type": child["agent_type"] in harness_agents,
                               "spawn_call": spawns[actor].get("spawn_call")})
            agent_type_uses.append({"item": f"agent-type:{child['agent_type'] or 'unknown'}", "kind": "agent-type",
                                    "level": "completion", "descriptive": True, "actor": actor,
                                    "order": spawns[actor]["order"], "call_id": spawns[actor].get("spawn_call"),
                                    "source": "child meta"})
    catalog = skill_catalog("claude")
    result_order = stream.get("result_order")
    result_ns = _ts_ns(exit_row.get("result_at"))
    # A call still running when the trial was terminated gets a shutdown result in the transcript ("Connection closed",
    # written as the client exits) and no Loki row (smoke-20261006c claude-env: a ctx_batch_execute started at
    # 10:30:06Z, result at 10:43:17Z after the timeout's SIGTERM). Such a call is marked terminated: never a completed use,
    # and unresolved in G3, like a call with no result.
    terminated_ns = termination_ns(ledger_rows)
    for call in calls:
        res_ns = _ts_ns((call.get("result") or {}).get("ts"))
        if terminated_ns and res_ns and res_ns >= terminated_ns and call.get("status") != "no_result":
            call["status"] = "terminated"
    uses = []
    for call in calls:
        for use in claude_uses(call, catalog, cwd):
            after = (call["order"] > result_order) if (call.get("source") == "stream" and result_order is not None) else \
                (bool(result_ns and _ts_ns(call.get("ts")) and _ts_ns(call.get("ts")) > result_ns))
            use.update({"call_id": call["id"], "order": call["order"], "actor": call["actor"], "actor_type": call.get("actor_type"),
                        "tool_name": call.get("name"), "source": call.get("source"), "after_result": after,
                        "input_text": json.dumps(call.get("input") or {})})
            uses.append(use)
    uses += agent_type_uses
    # Main-actor hook blocks: the main transcript's hook attachments (they carry the hook's command and tool_use id),
    # placed at the stream order of their call; without a transcript, the stream's hook_response outputs.
    main_hooks = []
    if transcript.get("hook_outputs"):
        for hook in transcript["hook_outputs"]:
            if hook.get("via") == "transcript-context":
                continue
            main_hooks.append({**hook, "actor": "main",
                               "order": _order_for_tool(hook.get("tool_use_id"), by_id, hook.get("hook_name"), -1)})
    else:
        commands_by_output = {}
        for hook in child_hooks:
            if hook.get("raw_output"):
                commands_by_output.setdefault(hook["raw_output"], set()).add(hook.get("source_class"))
        for hook in stream["hook_outputs"]:
            classes = commands_by_output.get(hook.get("raw_output") or "", set())
            source_class = "tool-native" if classes == {"tool-native"} else ("harness" if "harness" in classes else "unattributed")
            main_hooks.append({**hook, "actor": "main", "source_class": source_class, "via": "stream-fallback"})
    # S6 and R1 tag 7 (finding 8): RTK's PreToolUse rewrites from every transcript's hook attachments (command rtk hook,
    # updatedInput), matched to their Bash call by tool_use id across all actors; the denominator is every Bash call.
    all_hooks = main_hooks + child_hooks
    calls_by_id = {c["id"]: c for c in calls}
    bash_calls = [c for c in calls if c.get("name") == "Bash"]
    rtk_hooks = [h for h in all_hooks if re.search(r"(^|[\s/])rtk\s+hook\b", h.get("command") or "")
                 and isinstance((h.get("updated_input") or {}).get("command"), str)]
    rewritten, unmatched, unchanged, per_actor = set(), [], 0, {}
    for call in bash_calls:
        per_actor.setdefault(call["actor"], {"bash_calls": 0, "rewritten": 0})["bash_calls"] += 1
    for hook in rtk_hooks:
        call = calls_by_id.get(hook.get("tool_use_id") or "")
        if call is None or call.get("name") != "Bash":
            unmatched.append({"tool_use_id": hook.get("tool_use_id"), "actor": hook.get("actor")})
            continue
        original = " ".join(((call.get("input") or {}).get("command") or "").split())
        updated = " ".join(hook["updated_input"]["command"].split())
        if updated == original:
            unchanged += 1
            continue
        if call["id"] in rewritten:
            continue
        rewritten.add(call["id"])
        per_actor[call["actor"]]["rewritten"] += 1
        uses.append({"item": "rtk", "kind": "hook", "level": "completion" if call.get("status") == "ok" else "request",
                     "hook_rewritten": True, "call_id": call["id"], "order": call["order"] + 0.01, "actor": call["actor"],
                     "tool_name": "Bash", "source": "transcript hook attachment", "via": "PreToolUse updatedInput"})
    stream_rtk = sum(1 for h in stream["hook_outputs"] if (h.get("decision_reason") or "").startswith("RTK")
                     or "rtk " in ((h.get("updated_input") or {}).get("command") or ""))
    rtk_s6 = {"bash_calls_all_actors": len(bash_calls), "rewritten": len(rewritten),
              "rewritten_share_of_all_bash": round(len(rewritten) / len(bash_calls), 4) if bash_calls else None,
              "per_actor": per_actor, "rtk_hook_outputs_with_updated_input": len(rtk_hooks),
              "updated_input_equal_to_original": unchanged, "unmatched_rewrites": unmatched[:50],
              "unmatched_rewrite_count": len(unmatched),
              "stream_rtk_rewrite_outputs_cross_check": stream_rtk,
              "note": "transcript hook attachments joined by tool_use id; the stream count is a cross-check, never summed"}
    loki = load_json(root / "loki" / f"{tid}.json") if (root / "loki" / f"{tid}.json").exists() else {}
    by_session = loki.get("by_session_id") or []
    by_task = loki.get("by_ecosystem_task_id") or []
    # G2 joins. A Claude trial without its transcript fails the join (finding 12: the marker scan needs it).
    transcript_found = bool(transcript.get("rows")) and (not transcript.get("session_ids") or tid in transcript["session_ids"])
    joins = {"stream_session_id": stream["session_ids"] == [tid] or (tid in stream["session_ids"] and len(stream["session_ids"]) == 1),
             "loki_session_rows": len(by_session), "loki_task_rows": len(by_task),
             "loki_task_rows_same_session": all(r.get("session_id") == tid for r in by_task) if by_task else False,
             "transcript_found": transcript_found}
    joins["pass"] = joins["stream_session_id"] and joins["loki_session_rows"] > 0 and joins["loki_task_rows"] > 0 \
        and joins["loki_task_rows_same_session"] and transcript_found
    # G3 agreement on MCP and Skill calls, by tool_use_id.
    loki_results = {r.get("tool_use_id"): r for r in by_session if r.get("event_name") == "tool_result" and r.get("tool_use_id")}
    disagreements, checked, checked_children, unresolved, unresolved_terminated = [], 0, 0, 0, 0
    for call in calls:
        name = call.get("name") or ""
        if not (name.startswith("mcp__") or name == "Skill"):
            continue
        row = loki_results.get(call["id"])
        if call.get("status") == "no_result":
            # Killed before its result: agreement means neither source holds a completion.
            if row is not None:
                disagreements.append({"tool_use_id": call["id"], "issue": "Loki has a result the transcript lacks"})
            unresolved += 1
            continue
        if call.get("status") == "terminated":
            # Its only result is the shutdown one, written after the trial was terminated (termination_ns).
            unresolved_terminated += 1
            continue
        checked += 1
        if call.get("source") == "child-transcript":
            checked_children += 1
        if row is None:
            disagreements.append({"tool_use_id": call["id"], "issue": "missing in Loki"})
            continue
        if name.startswith("mcp__"):
            server = name.split("__")[1]
            if MCP_SERVER_ITEMS.get(row.get("mcp_server_name"), row.get("mcp_server_name")) != MCP_SERVER_ITEMS.get(server, server):
                disagreements.append({"tool_use_id": call["id"], "issue": "server differs", "stream": server, "loki": row.get("mcp_server_name")})
        loki_ok = str(row.get("success")).lower() == "true"
        if loki_ok != (call.get("status") == "ok"):
            disagreements.append({"tool_use_id": call["id"], "issue": "success differs", "stream": call.get("status"), "loki": row.get("success")})
    stream_call_ids = {c["id"] for c in calls}
    extra_loki = [k for k, r in loki_results.items() if (r.get("mcp_server_name") or r.get("tool_name") == "Skill") and k not in stream_call_ids]
    skill_rows = [r for r in by_session if r.get("event_name") == "skill_activated"]
    agreement = {"checked": checked, "checked_child_transcript_calls": checked_children, "unresolved_both_sides": unresolved,
                 "unresolved_terminated": unresolved_terminated,
                 "disagreements": disagreements, "loki_only_mcp_or_skill": len(extra_loki),
                 "skill_activated_rows": [{k: r.get(k) for k in ("skill_name", "invocation_trigger")} for r in skill_rows]}
    agreement["pass"] = not disagreements and not extra_loki
    # Markers (G5) and instruction records.
    instruction_texts = claude_instruction_texts(transcript)
    markers = marker_hits(instruction_texts)
    requests = [r for r in by_session if r.get("event_name") == "api_request"]
    efforts_by = {}
    for r in requests:
        key = f"{r.get('model')}|{r.get('query_source')}"
        efforts_by.setdefault(key, {})
        efforts_by[key][str(r.get("effort"))] = efforts_by[key].get(str(r.get("effort")), 0) + 1
    main_model = (stream["init"] or {}).get("model")
    # G6 reads the trial's own model: auxiliary requests (titles, compaction, a smaller model) are reported, not gated.
    efforts = sorted({str(r.get("effort")) for r in requests if r.get("model") == main_model}) if main_model else []
    models = sorted({r.get("model") for r in requests if r.get("model")})
    cost_loki = round(sum(float(r.get("cost_usd") or 0) for r in requests), 6)
    # Finding 3: spend before and after the result event, each request counted once.
    cost_pre = round(sum(float(r.get("cost_usd") or 0) for r in requests if not result_ns or r.get("ts_ns", 0) <= result_ns), 6)
    post_requests = [r for r in requests if result_ns and r.get("ts_ns", 0) > result_ns]
    init = stream["init"] or {}
    tools = init.get("tools") or []
    tools_by_server = {}
    for tool in tools:
        if tool.startswith("mcp__") and tool.count("__") >= 2:
            _, server, fn = tool.split("__", 2)
            tools_by_server.setdefault(server, []).append(fn)
    return {"stream": stream, "transcript": transcript, "calls": calls, "uses": uses, "joins": joins, "agreement": agreement,
            "turn_times": claude_turn_times(events, ledger_rows.get("launched", {}).get("at")),
            "markers": markers, "instruction_files": [len(t) for t in instruction_texts],
            "instruction_records": sum(1 for a in transcript.get("attachments") or [] if a.get("type") == "instructions"),
            "efforts": efforts, "models": models,
            "efforts_by_model_and_source": efforts_by, "main_model": main_model,
            "cost_usd_result": (stream["result"] or {}).get("total_cost_usd"), "cost_usd_loki": cost_loki,
            "cost_usd_loki_pre_result": cost_pre, "cost_usd_loki_post_result": round(cost_loki - cost_pre, 6),
            "requests_post_result": len(post_requests),
            "init": {"cwd": init.get("cwd"), "mcp_servers": init.get("mcp_servers"), "skills": init.get("skills"),
                     "agents": init.get("agents"), "plugins": [p.get("name") for p in init.get("plugins") or []],
                     "permissionMode": init.get("permissionMode"), "model": init.get("model"),
                     "denied_tools_absent": [t for t in ("CronCreate", "RemoteTrigger", "PushNotification") if t not in tools],
                     "memory_paths": init.get("memory_paths")},
            "tools_by_server": tools_by_server, "rate_limit_events": len(stream["rate_limit_events"]),
            "hook_events": len(stream["hooks"]), "cwd": cwd, "main_hooks": main_hooks, "child_hooks": child_hooks,
            "rtk_s6": rtk_s6, "actor_types": actor_types, "spawns": spawns, "children": child_rows,
            "hook_sources": _count([h.get("hook_name") for h in stream["hooks"] if h.get("subtype") == "hook_response"]),
            "hook_output_classes": _count([h.get("source_class") for h in all_hooks
                                          if h.get("additional_context") or h.get("system_message")])}


def codex_turn_times(rollout: dict | None, launched_at: str | None) -> dict:
    """The CC's 12:30Z ruling (item task-ns2604-coop-20261006T123036Z, b): a Codex cell's final-turn time (its last
    agent message with no tool item after it) and result-event time (task_complete), from the main rollout's own
    timestamps, in seconds from the launched row's stamp. CL7b has no launcher, and runs prepared before the ruling
    recorded neither, so the grader reads both here; a launcher trial's own arrival times take precedence."""
    rollout = rollout or {}
    start_ns = _ts_ns(launched_at)
    final_ns, result_ns = _ts_ns(rollout.get("final_turn_end_at")), _ts_ns(rollout.get("task_complete_at"))
    return {"final_turn_end_at": rollout.get("final_turn_end_at"), "result_at": rollout.get("task_complete_at"),
            "final_turn_end_s": round((final_ns - start_ns) / 1e9, 1) if start_ns and final_ns else None,
            "time_to_result_s": round((result_ns - start_ns) / 1e9, 1) if start_ns and result_ns else None,
            "result_event": {"type": "task_complete"} if result_ns else None}


def _forwarded_efforts(call: dict) -> list:
    """The forwarded effort values of one gateway call-log row: decision 8's effort-only record, or the effort inside
    the reasoning object a row collected before it kept."""
    fields = call.get("forwarded_effort")
    if isinstance(fields, dict):
        return [fields.get("reasoning.effort"), fields.get("reasoning_effort")]
    legacy = call.get("forwarded_reasoning")
    return [legacy.get("effort")] if isinstance(legacy, dict) else []


def _count(values) -> dict:
    out = {}
    for value in values:
        out[str(value)] = out.get(str(value), 0) + 1
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


def grade_codex_trial(root: Path, cfg: dict, trial: dict, ledger_rows: dict) -> dict:
    tid = trial["trial_id"]
    prepared = ledger_rows.get("prepared", {}) or ledger_rows.get("pre-launch", {})
    cwd = prepared.get("fixture_private")
    stream_path = root / "raw" / f"{tid}.stream.jsonl"
    events = parse_stream_text(stream_path.read_text(encoding="utf-8", errors="replace")) if stream_path.exists() else []
    stream = parse_codex_stream(events)
    rollouts = [parse_rollout(p) for p in sorted((root / "rollouts" / tid).glob("rollout-*.jsonl"))] if (root / "rollouts" / tid).exists() else []
    stream_source = "exec stream"
    if not stream["thread_id"] and rollouts:
        # CL7b has no exec stream: the thread collect.py took from Loki, and that thread's rollout is the primary source.
        collected = (load_json(root / "collect.json").get("trials") or {}).get(tid, {}) if (root / "collect.json").exists() else {}
        thread = collected.get("thread_id") or (rollouts[0].get("meta") or {}).get("id")
        main_rollout = next((r for r in rollouts if (r.get("meta") or {}).get("id") == thread), rollouts[0])
        stream = {**stream, "thread_id": (main_rollout.get("meta") or {}).get("id"),
                  "items": [dict(it) for it in main_rollout["items"].values()]}
        stream_source = "rollout (no exec stream)"
    main = next((r for r in rollouts if (r.get("meta") or {}).get("id") == stream["thread_id"]), rollouts[0] if rollouts else None)
    clone = trial_dir(cfg, root) / "clones" / tid
    catalog = skill_catalog("codex", clone)
    uses = []
    # Ordering key: the tool item's ordinal (1-based) among the session's tool items; a rollout message's key is the
    # number of tool items completed before it plus 0.5. Child threads are offset by 10^6 per child.
    ordinal = 0
    for item in stream["items"]:
        if item.get("type") in STREAM_TOOL_TYPES | ROLLOUT_TOOL_TYPES:
            ordinal += 1
        item["_ordinal"] = ordinal
        item["_actor"] = "main"
        for use in codex_uses(item, catalog, cwd):
            use.update({"call_id": item.get("id"), "order": ordinal, "actor": "main", "source": "stream",
                        "input_text": json.dumps(item.get("arguments") or item.get("command") or "")})
            uses.append(use)
    child_rollouts = [r for r in rollouts if r is not main]
    spawns, actor_types = {}, {}
    # A child thread comes from its parent's spawn_agent call (the k-th child in start order from the k-th call). Its
    # message is encrypted in the rollout, so the spawn prompt is not readable; fork_turns "all" copies the parent's
    # history, so such a child saw every block its parent saw before the call (visible()).
    spawn_calls = {}
    for rollout in rollouts:
        calls_here = [f for f in rollout.get("functions") or [] if f.get("name") == "spawn_agent"]
        spawn_calls[(rollout.get("meta") or {}).get("id")] = calls_here
    taken = {}
    for number, rollout in enumerate(child_rollouts, 1):
        ordinal = 0
        rollout["_offset"] = number * 10**6
        meta = rollout.get("meta") or {}
        actor = f"child:{meta.get('id')}"
        spawn_meta = (((meta.get("source") or {}) if isinstance(meta.get("source"), dict) else {}).get("subagent") or {}).get("thread_spawn") or {}
        actor_types[actor] = spawn_meta.get("agent_role") or meta.get("agent_role")
        parent = spawn_meta.get("parent_thread_id") or meta.get("parent_thread_id") or (main or {}).get("meta", {}).get("id")
        parent_rollout = next((r for r in rollouts if (r.get("meta") or {}).get("id") == parent), main or {})
        spawner = "main" if parent_rollout is main else f"child:{parent}"
        index = taken.get(parent, 0)
        taken[parent] = index + 1
        calls_list = spawn_calls.get(parent) or []
        call = calls_list[index] if index < len(calls_list) else None
        args = _json_arg((call or {}).get("arguments"))
        offset_parent = parent_rollout.get("_offset", 0) if parent_rollout is not main else 0
        spawns[actor] = {"spawner": spawner, "order": offset_parent + (call or {}).get("tools_before", 0) + 0.5 if call else 0,
                         "text": "", "fork_all": args.get("fork_turns") == "all", "spawn_call": (call or {}).get("call_id")}
        for item in rollout["items"].values():
            if item.get("type") in ROLLOUT_TOOL_TYPES:
                ordinal += 1
            item["_ordinal"] = rollout["_offset"] + ordinal
            item["_actor"] = actor
            for use in codex_uses(item, catalog, cwd):
                use.update({"call_id": item.get("id"), "order": item["_ordinal"], "actor": actor, "source": "child-rollout",
                            "input_text": json.dumps(item.get("arguments") or item.get("command") or "")})
                uses.append(use)
    subagent_activity = sum(1 for r in rollouts for it in r["items"].values() if it.get("type") == "SubAgentActivity")
    loki = load_json(root / "loki" / f"{tid}.json") if (root / "loki" / f"{tid}.json").exists() else {}
    rows = loki.get("by_env") or []
    conv_ids = sorted({r.get("conversation_id") for r in rows if r.get("conversation_id")})
    joins = {"loki_env_rows": len(rows), "thread_id": stream["thread_id"],
             "rollout_session_meta_id": (main or {}).get("meta", {}).get("id") if main else None,
             "loki_conversation_ids": conv_ids, "rollout_found": main is not None}
    joins["pass"] = bool(rows) and bool(stream["thread_id"]) and joins["rollout_session_meta_id"] == stream["thread_id"] and stream["thread_id"] in conv_ids
    # G3: rollout McpToolCall ids vs Loki codex.tool_result call_ids (wrappers excluded); stream count vs rollout count.
    rollout_mcp = {i: it for r in rollouts for i, it in r["items"].items() if it.get("type") == "McpToolCall"}
    loki_mcp = {r.get("call_id"): r for r in rows if r.get("event_name") == "codex.tool_result" and r.get("mcp_server_name")}
    wrappers = [r for r in rows if r.get("event_name") == "codex.tool_result" and r.get("tool_name") == "exec"
                and r.get("tool_namespace") == "functions"]
    stream_mcp = [it for it in stream["items"] if it.get("type") in ("mcp_tool_call", "McpToolCall")]
    disagreements = []
    for call_id, item in rollout_mcp.items():
        row = loki_mcp.get(call_id)
        if row is None:
            disagreements.append({"call_id": call_id, "issue": "missing in Loki"})
        elif row.get("mcp_server_name") != item.get("server") or row.get("mcp_tool_name") != item.get("tool"):
            disagreements.append({"call_id": call_id, "issue": "server or tool differs"})
    for call_id in loki_mcp:
        if call_id not in rollout_mcp:
            disagreements.append({"call_id": call_id, "issue": "missing in rollout"})
    stream_counts, rollout_counts = {}, {}
    for it in stream_mcp:
        key = f"{it.get('server')}/{it.get('tool')}"
        stream_counts[key] = stream_counts.get(key, 0) + 1
    for it in rollout_mcp.values():
        if main and it.get("id") in main["items"]:
            key = f"{it.get('server')}/{it.get('tool')}"
            rollout_counts[key] = rollout_counts.get(key, 0) + 1
    agreement = {"rollout_mcp": len(rollout_mcp), "loki_mcp": len(loki_mcp), "stream_mcp_by_tool": stream_counts,
                 "rollout_mcp_by_tool_main": rollout_counts, "code_mode_wrappers_rollout": sum(len(r["wrappers"]) for r in rollouts),
                 "loki_functions_exec_excluded": len(wrappers), "disagreements": disagreements}
    agreement["pass"] = not disagreements and stream_counts == rollout_counts
    markers = marker_hits(codex_instruction_texts(main)) if main else {}
    gateway = load_json(root / "gateway" / f"{tid}.json") if (root / "gateway" / f"{tid}.json").exists() else {}
    calls = [c for v in (gateway.get("by_thread") or {}).values() for c in v]
    starts = [r for r in rows if r.get("event_name") == "codex.conversation_starts"]
    exposed = [c for c in calls if c.get("pipeline_exposed")]
    effort = {"requested_turn_context": ((main or {}).get("turn_context") or {}).get("effort"),
              "conversation_starts": sorted({r.get("reasoning_effort") for r in starts if r.get("reasoning_effort")}),
              "gateway_received": sorted({c.get("received_effort") for c in calls if c.get("received_effort")}),
              # Decision 8: only the forwarded effort fields (rows collected before it kept the reasoning object).
              "gateway_forwarded": sorted({str(v) for c in exposed for v in _forwarded_efforts(c) if v}) or None,
              "gateway_forwarded_exposed": bool(exposed),
              "gateway_calls_with_pipeline": len(exposed),
              # GPT read of 5aa2bfdc, finding 7: the calls whose record holds no forwarded effort value, exposed or not.
              "gateway_calls_missing_forwarded_effort": [c.get("id") for c in calls if not any(_forwarded_efforts(c))],
              "gateway_service_tier": sorted({str(c.get("received_service_tier")) for c in calls}),
              # CC item task-ns2604-coop-20261006T144256Z: the tier the gateway forwarded (pipeline details only).
              "gateway_forwarded_service_tier": sorted({str(c.get("forwarded_service_tier")) for c in exposed}),
              # GPT read of a513616d, P2: every call's forwarded tier as recorded, null when missing (never "None").
              "tier_calls": [{"id": c.get("id"), "forwarded": c.get("forwarded_service_tier")} for c in calls],
              # GPT read of 80be1483, P2-1: every collected call with the request id it matched, failed details kept.
              "evidence_calls": evidence_calls(calls),
              # CC item task-ns2604-coop-20261006T143846Z, (a): calls the gateway's semantic cache answered.
              "gateway_semantic_cache_calls": [c.get("id") for c in calls if c.get("cache_source") == "semantic"],
              "gateway_backend_models": sorted({c.get("backend_model") for c in calls if c.get("backend_model")}),
              "gateway_calls": len(calls), "gateway_build": ledger_rows.get("pre-launch", {}).get("gateway_build")
              or ledger_rows.get("launched", {}).get("gateway_build")}
    all_items = list(stream["items"]) + [it for r in child_rollouts for it in r["items"].values()]
    return {"stream": {"thread_id": stream["thread_id"], "items": len(stream["items"]), "errors": stream["errors"],
                       "turn_failed": len(stream["turn_failed"]), "usage": stream["usage"], "source": stream_source},
            "uses": uses, "joins": joins, "agreement": agreement, "markers": markers, "effort": effort,
            "rollouts": [Path(r["path"]).name for r in rollouts], "model_provider": (main or {}).get("meta", {}).get("model_provider") if main else None,
            "main_rollouts": sum(1 for r in rollouts if not (r.get("meta") or {}).get("parent_thread_id")),
            "skills_body_sha256": (main or {}).get("skills_body_sha256"), "skill_names": (main or {}).get("skill_names") or [],
            "hook_context_items": sum(1 for r in rollouts for m in r["messages"] if m.get("kinds") and "hooks.additional_context" in json.dumps(m["kinds"])),
            "hook_context_items_nonempty": sum(1 for r in rollouts for m in r["messages"] if m.get("kinds")
                                               and "hooks.additional_context" in json.dumps(m["kinds"]) and m["text"].strip()),
            "subagent_activity_items": subagent_activity, "child_rollouts": child_rollouts, "spawns": spawns,
            "turn_times": codex_turn_times(main, (ledger_rows.get("launched") or {}).get("at")),
            "actor_types": actor_types, "cwd": cwd, "items": stream["items"], "all_items": all_items, "rollout_main": main}


def provenance_context(root: Path, cfg: dict, trial: dict, graded: dict, task: dict) -> dict:
    """Blocks with their order for the R1 tagger, from the trial's own sources."""
    client, arm = trial.get("client"), trial.get("arm")
    registry_doc = load_json(root / "registry.json") if (root / "registry.json").exists() else {}
    registry = set(registry_doc.get("reviewed") or registry_doc.get("provisional_reviewed") or [])
    cwd = graded.get("cwd") or ""
    store_blocks, hook_blocks, registry_results, fixture_results, skill_bodies, agent_returns = [], [], [], [], [], []
    harness_reads, process_reads = [], []
    own_memory = f"/.claude/projects/{_claude_slug(cwd)}/memory/" if cwd else None
    harness_agents = cfg.get("harness_agents") or {}

    def is_store_injection(text: str) -> bool:
        low = (text or "").lower()
        return "ai-memory" in low or "pending handoff" in low or "handoff from previous session" in low

    if client == "claude":
        # The env arm's harness text is what the client loaded (the transcript's instructions records), never the file
        # as it is at grading time.
        harness_texts = claude_instruction_texts(graded["transcript"]) if arm == "env" else []
        for hook in list(graded.get("main_hooks") or []) + list(graded.get("child_hooks") or []):
            text = "\n".join(str(hook.get(k) or "") for k in ("additional_context", "system_message"))
            if not text.strip():
                continue
            block = {"order": hook["order"], "actor": hook.get("actor", "main"), "text": text, "source": hook.get("hook_name"),
                     "source_class": hook.get("source_class") or "unattributed"}
            (store_blocks if is_store_injection(text) else hook_blocks).append(block)
        workflow_children_types = {}
        for child in graded.get("children") or []:
            if child.get("spawn_call"):
                workflow_children_types.setdefault(child["spawn_call"], set()).add(child.get("agent_type"))
        for call in graded["calls"]:
            result = (call.get("result") or {}).get("text") or ""
            order = (call.get("result") or {}).get("order", call["order"])
            actor = call.get("actor", "main")
            name, args = call.get("name") or "", call.get("input") or {}
            touched = json.dumps(args)
            if STORE_TOOLS.match(name):
                store_blocks.append({"order": order, "actor": actor, "text": result, "source": name,
                                     "source_item": "ai-memory" if "ai-memory" in name else "context-mode"})
            elif own_memory and own_memory in os.path.expanduser(touched).replace(str(HOME), ""):
                # Claude auto memory: a read of the trial's own memory directory is a store retrieval. Text that the
                # reading tool wraps around it (a ctx_* summary naming ctx_* tools) does not direct that tool's item.
                reader = name.split("__")[1] if name.startswith("mcp__") else name
                store_blocks.append({"order": order, "actor": actor, "text": result, "source": "auto-memory read",
                                     "source_item": MCP_SERVER_ITEMS.get(reader, reader)})
            if any(path in touched for path in registry) and call.get("status") == "ok":
                registry_results.append({"order": order, "actor": actor, "text": result})
            elif (cwd and cwd in touched) or name in ("Read", "Grep", "Glob", "Bash") or "ctx_" in name:
                fixture_results.append({"order": order, "actor": actor, "text": result})
            if call.get("status") == "ok" and marker_hits([result]):
                # Finding 9: harness instruction text read through any tool, inside or outside the fixture.
                harness_reads.append({"order": order, "actor": actor, "text": result, "call_id": call["id"],
                                      "markers": sorted(marker_hits([result]))})
            if any(process_table_read(t) for t in call_shell_texts(name, args)) or \
                    (name == "Read" and PROC_PATH.search(args.get("file_path") or "")):
                process_reads.append({"order": call["order"], "actor": actor, "call_id": call["id"]})
            if name in ("Task", "Agent") and args.get("subagent_type") in harness_agents:
                agent_returns.append({"order": order, "actor": actor, "text": result})
            if name == "Workflow" and (workflow_children_types.get(call["id"], set()) & set(harness_agents)):
                agent_returns.append({"order": order, "actor": actor, "text": result})
        catalog = skill_catalog("claude")
        for use in graded["uses"]:
            if use["kind"] == "skill-consultation" and use.get("level") in ("completion", "completed-ctx"):
                call = next((c for c in graded["calls"] if c["id"] == use["call_id"]), None)
                skill_bodies.append({"order": ((call or {}).get("result") or {}).get("order", use["order"]),
                                     "skill": use.get("skill"), "actor": use.get("actor", "main"),
                                     "text": _skill_body(catalog, use.get("skill")),
                                     "harness": skill_item(use.get("skill") or "") in HARNESS_SKILLS})
    else:
        main = graded.get("rollout_main") or {}
        harness_texts = [t for t in codex_instruction_texts(main) if "AGENTS.md instructions" in t] if arm == "env" else []
        rollouts = [(main, 0)] + [(r, r.get("_offset", 0)) for r in graded.get("child_rollouts") or []]
        for rollout, offset in rollouts:
            actor = "main" if offset == 0 else f"child:{(rollout.get('meta') or {}).get('id')}"
            for message in rollout.get("messages") or []:
                if message.get("kinds") and "hooks.additional_context" in json.dumps(message["kinds"]) and message["text"].strip():
                    # Codex hook context: user-layer hooks are untrusted in a clone, so what reaches a trial is a plugin
                    # hook's (tool-native); an ai-memory injection is a store block.
                    block = {"order": offset + message.get("tools_before", 0) + 0.5, "actor": actor, "text": message["text"],
                             "source": "hooks.additional_context", "source_class": "tool-native"}
                    (store_blocks if is_store_injection(message["text"]) else hook_blocks).append(block)
        for item in graded.get("all_items") or graded["items"]:
            if item.get("type") not in STREAM_TOOL_TYPES | ROLLOUT_TOOL_TYPES:
                continue
            order = item.get("_ordinal", 0) + 0.25   # the result exists once the item completed
            text = codex_item_output(item)
            args = json.dumps(item.get("arguments") or item.get("command") or "")
            server, tool = item.get("server") or "", item.get("tool") or ""
            actor = item.get("_actor", "main")
            if item.get("type") in ("mcp_tool_call", "McpToolCall") and (server in ("ai-memory", "ai_memory") or tool == "ctx_search"):
                store_blocks.append({"order": order, "actor": actor, "text": text, "source": f"{server}/{tool}",
                                     "source_item": MCP_SERVER_ITEMS.get(server, server)})
            if any(path in args for path in registry):
                registry_results.append({"order": order, "actor": actor, "text": text})
            else:
                fixture_results.append({"order": order, "actor": actor, "text": text})
            if marker_hits([text]):
                harness_reads.append({"order": order, "actor": actor, "text": text, "call_id": item.get("id"),
                                      "markers": sorted(marker_hits([text]))})
            if any(process_table_read(t) for t in codex_item_shell_texts(item)):
                process_reads.append({"order": item.get("_ordinal", 0), "actor": actor, "call_id": item.get("id")})
        catalog = skill_catalog("codex", trial_dir(cfg, root) / "clones" / trial["trial_id"])
        for use in graded["uses"]:
            if use["kind"] == "skill-consultation" and use.get("level") in ("completion", "completed-ctx"):
                skill_bodies.append({"order": use["order"] + 0.25, "skill": use.get("skill"), "actor": use.get("actor", "main"),
                                     "text": _skill_body(catalog, use.get("skill")),
                                     "harness": skill_item(use.get("skill") or "") in HARNESS_SKILLS})
    prompt = task.get("prompt") or ""
    prompt_paths = [t for t in re.findall(r"[\w./-]+/[\w./-]+|\./[\w./-]+", prompt)]

    def prompt_paths_in_call(use):
        # Finding 13: the call's own input (paths and commands), never the use record.
        text = use.get("input_text") or ""
        return any(p in text or p.lstrip("./") in text for p in prompt_paths)

    return {"prompt": prompt, "arm": arm, "lexicon": cfg["lexicon"],
            "tools_by_server": graded.get("tools_by_server") or cfg.get("tools_by_server") or {},
            "harness_texts": harness_texts, "harness_agents": harness_agents, "store_blocks": store_blocks,
            "hook_blocks": hook_blocks, "registry_results": registry_results, "fixture_results": fixture_results,
            "skill_bodies": skill_bodies, "agent_returns": agent_returns, "harness_reads": harness_reads,
            "process_reads": process_reads, "spawns": graded.get("spawns") or {},
            "actor_types": graded.get("actor_types") or {}, "prompt_paths_in_call": prompt_paths_in_call,
            "registry_status": "reviewed" if registry_doc.get("reviewed") else "provisional"}


def _claude_slug(path: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in path or "")


def _call_texts(graded: dict, client: str) -> list[tuple[str, str]]:
    if client == "claude":
        return [(call["id"], json.dumps(call.get("input") or {})) for call in graded["calls"]]
    return [(item.get("id"), json.dumps(item.get("command") or item.get("arguments") or ""))
            for item in graded.get("all_items") or graded["items"]]


# GPT read of 5aa2bfdc, finding 6: an answer source invalidates a trial only through a successful read that returned
# content; a path mentioned, listed, written or read without success stays a tag.
# GPT micro-check of 87f9f1d7, finding 1: access is judged from each command's arguments and each tool's output mode.
# Content access: a program that prints file content or runs code over it, grep/rg printing matching lines, find or
# xargs running such a program, git show/cat-file/blame/diff/grep (log with a patch), tar or unzip to stdout, an input
# redirection, the Read tool, the Grep tool in content mode. Names or metadata only, so a tag: ls, find, stat, file,
# realpath, readlink, du, tree, wc, git ls-files/status/log, rg --files, grep/rg -l/-L/-c/-q, cp/mv/rsync, Glob, LS, and
# the Grep tool's default files_with_matches or count mode. A filter that a pipe feeds and that names no file (ls dir |
# head) reads the listing, not a file, so it is no read either (shell_read_texts).
CONTENT_PROGRAMS = READ_PROGRAMS | {"jq", "yq", "python", "python3", "node", "ruby", "perl", "awk", "gawk", "cut", "diff",
                                    "cmp", "xxd", "od", "hexdump", "strings", "tac", "sort", "uniq", "base64", "zcat", "bzcat",
                                    "xzcat", "zless", "sqlite3", "view", "vim", "nano", "emacs", "difft", "markitdown",
                                    "toon", "column", "fold", "fmt", "pr", "paste", "tr", "iconv", "sed", "awk"}
GREP_PROGRAMS = {"grep", "egrep", "fgrep", "rg", "ugrep", "ag", "ack"}
GREP_NAME_ONLY_LONG = {"--files-with-matches", "--files-without-match", "--count", "--count-matches", "--files", "--quiet",
                       "--silent", "--list-files"}
GREP_NAME_ONLY_SHORT = set("lLcq")
CODE_READ_API = re.compile(r"\bopen\s*\(|readFileSync|readFile\s*\(|read_text\s*\(|read_bytes\s*\(|\.read\s*\(|"
                           r"json\.load|createReadStream|fs\.promises", re.I)
MCP_READ_TOOL = re.compile(r"read|get|view|open|cat|fetch|search|grep|symbol|outline|content|quote|chunk|source|show", re.I)
MCP_LIST_TOOL = re.compile(r"list|find_file|glob|tree|\bls\b|_dir\b|exists|stat", re.I)


def _grep_reads_content(args: list[str]) -> bool:
    """grep or rg prints matching content unless a flag makes it print names, counts or nothing."""
    longs = {a.split("=", 1)[0] for a in args if a.startswith("--")}
    shorts = {ch for a in args if a.startswith("-") and not a.startswith("--") for ch in a[1:] if ch.isalpha()}
    return not (longs & GREP_NAME_ONLY_LONG or shorts & GREP_NAME_ONLY_SHORT)


GIT_VALUE_OPTIONS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--super-prefix", "--config-env"}
# xargs options whose value is the next word, as the installed GNU findutils xargs 4.10.0 `--help` lists them. -i, -l
# and -e (and --replace, --eof) take a value only when it is attached (-i{}, -l1, -eEND), so they take no word.
XARGS_VALUE_OPTIONS = {"-a", "--arg-file", "-d", "--delimiter", "-E", "-I", "-L", "--max-lines", "-n", "--max-args",
                       "-P", "--max-procs", "-s", "--max-chars", "--process-slot-var"}
FIND_ACTIONS = {"-exec", "-execdir", "-ok", "-okdir"}
# An action ends at ; or +. In segments() an escaped \; reads as _ (skill_usage.executed_text: an escaped character is
# data) and a quoted ";" as a blank word.
FIND_ACTION_ENDS = {";", "\\;", "+", "_", ""}


def _inner_commands(program: str, args: list[str]) -> list[list[str]]:
    """The commands find runs (every -exec/-execdir/-ok/-okdir action) or xargs runs (after its own options)."""
    if program == "find":
        commands, current = [], None
        for arg in args:
            if arg in FIND_ACTIONS:
                current = []
                commands.append(current)
            elif current is not None:
                if arg.strip() in FIND_ACTION_ENDS:
                    current = None
                else:
                    current.append(arg)
        return [command for command in commands if command]
    index = 0
    while index < len(args):
        arg = args[index]
        if arg in XARGS_VALUE_OPTIONS:
            index += 2
        elif arg.startswith("-"):
            index += 1
        else:
            return [args[index:]]
    return []


def segment_reads_content(tokens: list[str]) -> bool:
    """Whether one simple command (wrappers stripped) reads file content into its output."""
    if not tokens:
        return False
    if "<" in tokens:
        return True
    program, args = os.path.basename(tokens[0]), tokens[1:]
    if program in GREP_PROGRAMS:
        return _grep_reads_content(args)
    if program == "git":
        # Global options before the subcommand, some with a value (git -C <dir> show ...).
        index = 0
        while index < len(args) and args[index].startswith("-"):
            index += 2 if args[index] in GIT_VALUE_OPTIONS else 1
        sub, rest = (args[index], args[index + 1:]) if index < len(args) else ("", [])
        if sub in ("show", "cat-file", "blame", "annotate", "diff"):
            return True
        if sub == "grep":
            return _grep_reads_content(rest)
        if sub == "log":
            return any(a in ("-p", "--patch") or (a.startswith("-p") and not a.startswith("--")) for a in rest)
        return False
    if program in ("find", "xargs"):
        # The commands they run decide: grep -l over the files still returns only names.
        return any(segment_reads_content(inner) for inner in _inner_commands(program, args))
    if program == "tar":
        cluster = [a for a in args[:1] if not a.startswith("-")] + [a for a in args if a.startswith("-") and not a.startswith("--")]
        return "--to-stdout" in args or any("O" in a for a in cluster)
    if program == "unzip":
        return any(a in ("-p", "-c") for a in args)
    return program in CONTENT_PROGRAMS


# The first word a pattern-first program takes is its pattern or script unless an option gives it.
PATTERN_FIRST = GREP_PROGRAMS | {"sed", "awk", "gawk", "mawk", "jq", "yq"}
PATTERN_GIVEN = {"-e", "-f", "--regexp", "--file", "--expression", "--from-file"}
INFO_ONLY = {"--version", "-V", "--help", "-h"}
PLACEHOLDER = re.compile(r"\$\{?[A-Za-z_0-9@*#?]|\{\}")
PATH_WORD = re.compile(r"[^\s;&|()<>'\"`=]*/[^\s;&|()<>'\"`]*")
FILE_LIKE = re.compile(r"/|[*?\[]|^~|\.[A-Za-z][A-Za-z0-9]{0,7}$")   # an operand that names a file, not a count
REDIRECTION = re.compile(r"^\d*(&>>?|>>?|<<<|<<-?|<)(.*)$")
INTERPRETERS = {"python", "python3", "node", "ruby", "perl"}


def _operands(tokens: list[str]) -> list[str] | None:
    """The words a simple command reads from: its non-option words, without a pattern-first program's pattern or
    script, an output redirection or a heredoc marker (an input redirection's file stays). None for a --version or
    --help call, which reads nothing."""
    program, args = os.path.basename(tokens[0]), tokens[1:]
    if args and all(arg in INFO_ONLY for arg in args):
        return None
    words, skip = [], False
    for arg in args:
        if skip:
            skip = False
            continue
        redirection = REDIRECTION.match(arg)
        if redirection:
            operator, rest = redirection.groups()
            if operator == "<" and rest:
                words.append(rest)
            elif operator != "<":
                skip = not rest
            continue
        if arg == "-" or not arg.startswith("-"):
            words.append(arg)
    if program in PATTERN_FIRST and words and not any(arg.split("=", 1)[0] in PATTERN_GIVEN for arg in args):
        words = words[1:]
    return words


def shell_read_texts(text: str) -> list[str]:
    """The simple commands of a shell text that read file content, each with the places its operands come from.

    - A pipeline that hands a listing to xargs running a content program (rg -l ... | xargs cat) reads the listed
      files, so all its commands count.
    - A command that a pipe feeds and that names no file (ls dir | head -n 5, ... | sort -r, ... | grep x) reads the
      previous command's output, so it is not a read.
    - A read with a relative operand, or none, after a cd in the same text also names that directory. A read whose
      operand is a variable or {} (a loop, a find action's sh -c), or that names no operand (cat $(ls ...)), also names
      every path in the text, since one of them produced its operand. An interpreter that takes its program from a
      heredoc or stdin (python3 - <<'PY') names what the whole text names."""
    segs = pipeline_segments(text)
    if any(os.path.basename(t[0]) == "xargs" and segment_reads_content(t) for t, _ in segs):
        return [" ".join(t) for t, _ in segs]
    home = str(HOME)

    def expand(word: str) -> str:
        return word.replace("${HOME}", home).replace("$HOME", home)

    out, cwd, paths = [], None, None
    for tokens, piped in segs:
        tokens = [expand(token) for token in tokens]
        if os.path.basename(tokens[0]) in ("cd", "pushd"):
            target = next((token for token in tokens[1:] if not token.startswith("-")), "~")
            cwd = target if cwd is None or target.startswith(("/", "~", "$")) else f"{cwd}/{target}"
            continue
        if not segment_reads_content(tokens):
            continue
        operands = _operands(tokens)
        if operands is None or (piped and "<" not in tokens and not any(FILE_LIKE.search(o) for o in operands)):
            continue
        context = [" ".join(tokens)]
        if cwd and (not operands or any(not operand.startswith(("/", "~", "$")) for operand in operands)):
            context.append(cwd)
        if not operands or any(PLACEHOLDER.search(operand) for operand in operands):
            if paths is None:
                paths = PATH_WORD.findall(expand(skill_usage().executed_text(text or "")))
            context += paths
        if os.path.basename(tokens[0]) in INTERPRETERS and operands in ([], ["-"]):
            context.append(expand(text or ""))
        out.append(" ".join(context))
    return out


def claude_tool_read_texts(name: str, args: dict) -> list[str]:
    """The paths a Claude tool reads content from: Read and NotebookRead always, Grep only in content output mode (its
    default, files_with_matches, and count return names or counts)."""
    if name == "Read" and args.get("file_path"):
        return [str(args["file_path"])]
    if name == "NotebookRead" and args.get("notebook_path"):
        return [str(args["notebook_path"])]
    if name == "Grep" and args.get("output_mode") == "content":
        return [str(args.get("path") or ""), str(args.get("glob") or "")]
    return []


def call_access(call: dict, client: str) -> dict:
    """{ok, returned_chars, read_texts} for one Claude call or Codex item: whether it succeeded, how much it returned,
    and the parts of its input that read file content (finding 6)."""
    if client == "claude":
        name, args = call.get("name") or "", call.get("input") or {}
        ok = call.get("status") == "ok"
        text = ((call.get("result") or {}).get("text")) or ""
        reads = claude_tool_read_texts(name, args)
        if name == "Bash":
            reads += shell_read_texts(args.get("command") or "")
        elif name.startswith("mcp__"):
            tool = name.split("__", 2)[-1]
            reads += _mcp_read_texts(tool, args)
    else:
        kind = call.get("type")
        ok = call.get("status") == "completed" and (call.get("exit_code") in (0, None)) and not call.get("error")
        text = (codex_item_output(call) or "") if ok else ""
        reads = []
        if kind in ("command_execution", "CommandExecution"):
            reads = shell_read_texts(unwrap_command(call.get("command")))
        elif kind in ("mcp_tool_call", "McpToolCall"):
            reads = _mcp_read_texts(call.get("tool") or "", _json_arg(call.get("arguments")))
    text = text if isinstance(text, str) else json.dumps(text)
    return {"ok": ok, "returned_chars": len(text), "read_texts": reads, "returned_text": text}


def _mcp_read_texts(tool: str, args) -> list[str]:
    """The input parts of an MCP call that read content: context-mode's nested shell (judged per command), code that
    opens files and ctx_execute_file's path; for another server, the whole input of a tool whose name reads, gets,
    shows or searches content, never one that lists names or checks existence."""
    args = args if isinstance(args, dict) else {}
    if "ctx_" in tool:
        out = []
        for nested in ctx_nested(tool, args):
            if nested["kind"] == "shell":
                out += shell_read_texts(nested["text"])
            elif nested["kind"] == "file":
                out.append(nested["text"])
        code = args.get("code") or ""
        if code and CODE_READ_API.search(code):
            out.append(code)
        if tool.endswith("ctx_index") and args.get("path"):
            out.append(str(args["path"]))
        return out
    return [json.dumps(args)] if MCP_READ_TOOL.search(tool) and not MCP_LIST_TOOL.search(tool) else []


def answer_source_reasons(text: str, same_task_fixtures: set[str], same_task_trials: set[str],
                          declared: list[str], same_task_threads: set[str] | None = None) -> list[str]:
    """Why a call's input reads an answer source (decision 3 as confirmed at 11:43Z), or [] for a source or a tag. GPT
    micro-check of 87f9f1d7, finding 4: a same-task Codex trial's rollout is matched by its thread ids (main and
    collected child threads), wherever the read finds it: the native original under ~/.codex/sessions, a clone's alias
    of it, or a collected copy."""
    reasons = []
    if ANSWER_STORES.search(text):
        reasons.append("harness store")
    if any("/" in token and not ANSWER_STORES.search(token) and not EXPERIMENT_SOURCE.search(token)
           for token in EXPERIMENT_PATH.findall(text)):
        reasons.append("experiment output")
    if set(FIXTURE_ID.findall(text)) & same_task_fixtures:
        reasons.append("same-task fixture")
    ids = set(TRIAL_ID.findall(text))
    if ids & same_task_trials:
        reasons.append("same-task trial")
    if ids & (same_task_threads or set()):
        reasons.append("same-task transcript")
    if any(prefix and prefix in text for prefix in declared):
        reasons.append("declared grader output")
    return reasons


def reach(graded: dict, client: str, cfg: dict, trial_id: str, same_task_fixtures: set[str] | None = None,
          same_task_trials: set[str] | None = None, same_task_threads: set[str] | None = None) -> list[dict]:
    """G13 (extended by finding 9): calls whose input reaches coordination paths, other sessions' transcripts, host
    checkouts (~/code, ~/projects), user-level harness files, harness trial roots or another trial's fixture. The
    trial's own fixture, clone, trial files and project directory (its auto memory, exempt and logged under §8.4) are
    not counted. Decision 3: each entry is a tag; answer_source marks the reads the classifier takes for answer-source
    reads (answer_source_reasons: the harness's stores, this experiment's published outputs, a declared grader-output
    path, or the fixture, transcript or trial-root files of another trial of the same task). Since the structural G13
    (CC item task-ns2604-coop-20261006T132948Z) that mark is a diagnostic only: the wrapper hides those locations, and
    G13 checks what it hid (isolation.check)."""
    cwd = graded.get("cwd") or ""
    own = [p for p in (cwd, f"{HOME}/.claude/projects/{_claude_slug(cwd)}" if cwd else None) if p]
    work = cfg.get("trial_root")
    declared = [str(p).replace("~/", f"{HOME}/", 1) for p in cfg.get("answer_source_paths") or []]
    fixtures, trials, threads = same_task_fixtures or set(), same_task_trials or set(), same_task_threads or set()

    def clean(text: str) -> str:
        text = text.replace("~/", f"{HOME}/").replace('"~"', f'"{HOME}"')
        for path in own:
            text = text.replace(path, "<own>")
        if work:
            text = re.sub(re.escape(work) + r"/[a-z]+/" + re.escape(trial_id) + r"[^\s\"']*", "<own-trial-file>", text)
        return text

    found = []
    calls = graded["calls"] if client == "claude" else (graded.get("all_items") or graded["items"])
    for call in calls:
        raw = (call.get("input") or {}) if client == "claude" else (call.get("command") or call.get("arguments") or "")
        text = clean(json.dumps(raw))
        cats = sorted(name for name, pattern in REACH.items() if pattern.search(text))
        mentions = answer_source_reasons(text, fixtures, trials, declared, threads)
        if not (cats or mentions):
            continue
        # Finding 6: an answer source needs a successful read that returned content; a mention, listing, write or
        # failed read stays a tag (answer_source_mentions).
        access = call_access(call, client)
        content_read = access["ok"] and access["returned_chars"] > 0 and bool(access["read_texts"])
        parts = [clean(part) for part in access["read_texts"]] if content_read else []
        reasons = sorted({r for part in parts for r in answer_source_reasons(part, fixtures, trials, declared, threads)})
        evidence = "input" if reasons else None
        if reasons or any(pattern.search(part) for part in parts for pattern in REACH.values()):
            # Round 3 (finding 4): a glob or directory-wide content read (cat ~/.codex/sessions/.../*.jsonl, rg over
            # ~/.claude/projects) names no thread or session id in its input; the content it returned does. Only a read
            # that itself reaches such a place is scanned, so a listing next to an unrelated read (ls ... && cat
            # notes.md) does not count; a filter a pipe feeds is no read at all (shell_read_texts).
            ids = set(TRIAL_ID.findall(access["returned_text"]))
            from_content = (["same-task trial"] if ids & trials else []) + (["same-task transcript"] if ids & threads else [])
            if from_content:
                reasons = sorted(set(reasons) | set(from_content))
                evidence = evidence or "returned content"
        found.append({"call_id": call.get("id"), "categories": cats or ["answer-source mention"],
                      "answer_source": bool(reasons), "answer_source_reasons": reasons,
                      "answer_source_evidence": evidence,
                      "answer_source_mentions": mentions, "read_ok": access["ok"],
                      "returned_chars": access["returned_chars"], "read_parts": len(access["read_texts"]),
                      "same_task_fixture": "same-task fixture" in reasons})
    return found


# Round 5 (CC item task-ns2604-coop-20261006T143846Z, (a)). ai-memory stays in the treatment with one scope per trial
# (isolation.AI_MEMORY_WORKSPACE / <trial_id>, from the marker the wrapper binds above the fixture). Its server is
# reached over a socket, outside the mount namespace, so the grader checks every ai-memory call: a global query is
# a tag, and a call that returned a page of another trial's scope makes the trial invalid. User systemd, Docker and
# direct HTTP to the ai-memory server are tags, like G13's other categories.
AI_MEMORY_SERVER = "ai-memory"
AI_MEMORY_HTTP = re.compile(r"(?:127\.0\.0\.1|localhost):(?:29374|49374)\b")
HOST_SERVICE_PROGRAMS = {"docker": "docker", "docker-compose": "docker", "podman": "docker"}
# GPT read of 2044b2ab, residual channels: services outside the namespace that the shared network or WSL reaches.
# Diagnostic tags only. A Windows program started through WSL interop runs outside the trial's namespace and reads the
# distribution through \\wsl.localhost\<distro>. The gateway's management routes (/api/..., its call logs among them)
# answer without credentials. Every other loopback service (Dagu, Serena's MCP servers, agentsview, Loki, Grafana) is
# reached over the shared network.
GATEWAY_MANAGEMENT = re.compile(r"(?:127\.0\.0\.1|localhost):(?:20128|21128)/api/")
LOCAL_HTTP = re.compile(r"(?:https?://)?(?:127\.0\.0\.1|localhost|0\.0\.0\.0|\[::1\]):(\d{2,5})")
SERVICE_TIER_FLAG = re.compile(r"(?:^|\s)-c\s+service_tier=(['\"]?)([A-Za-z_-]+)\1(?=\s|$)")


def ai_memory_calls(graded: dict, client: str) -> list[dict]:
    """Every ai-memory MCP call of a trial, with its arguments and the text it returned."""
    out = []
    if client == "claude":
        for call in graded.get("calls") or []:
            parts = (call.get("name") or "").split("__")
            if len(parts) >= 3 and parts[0] == "mcp" and parts[1].endswith(AI_MEMORY_SERVER):
                out.append({"id": call.get("id"), "tool": parts[-1], "args": call.get("input") or {},
                            "result": ((call.get("result") or {}).get("text")) or "", "ok": call.get("status") == "ok"})
    else:
        for item in graded.get("all_items") or graded.get("items") or []:
            if item.get("type") in ("mcp_tool_call", "McpToolCall") and str(item.get("server") or "").endswith(AI_MEMORY_SERVER):
                out.append({"id": item.get("id"), "tool": item.get("tool"), "args": _json_arg(item.get("arguments")),
                            "result": codex_item_output(item) or "", "ok": item.get("status") == "completed"})
    return out


def _scope_pairs(value, out: list | None = None) -> list[tuple]:
    """Every (workspace, project) pair a result names: global hits carry theirs, and so may other pages."""
    out = [] if out is None else out
    if isinstance(value, dict):
        workspace, project = value.get("workspace"), value.get("project")
        if isinstance(workspace, str) and isinstance(project, str):
            out.append((workspace, project))
        for item in value.values():
            _scope_pairs(item, out)
    elif isinstance(value, list):
        for item in value:
            _scope_pairs(item, out)
    return out


def _parse(text):
    if isinstance(text, (dict, list)):
        return text
    try:
        return json.loads(text) if text else None
    except (TypeError, ValueError):
        return text if isinstance(text, str) and text.strip() else None


def mcp_payloads(raw) -> list:
    """GPT read of a513616d, P2: the transport envelope, normalized apart from content detection. A Claude transcript
    keeps the tool's text; a Codex mcp_tool_call item keeps the MCP result envelope ({"content": [{"type": "text",
    "text": ...}], "structuredContent": ...}). Returns the payloads the tool sent, each parsed JSON or plain text, with
    no wrapper added."""
    data = _parse(raw)
    if data is None:
        return []
    if isinstance(data, dict) and ("content" in data or "structuredContent" in data) \
            and set(data) <= {"content", "structuredContent", "isError", "_meta"}:
        if isinstance(data.get("structuredContent"), (dict, list)):
            return [data["structuredContent"]]
        out = []
        for block in data.get("content") or []:
            if isinstance(block, dict) and isinstance(block.get("text"), str):
                parsed = _parse(block["text"])
                if parsed is not None:
                    out.append(parsed)
        return out
    return [data]


# Each ai-memory 2.5.2 tool's response contract for content a trial could read (crates/ai-memory-mcp/src/server.rs):
# memory_query returns {"hits": [...]}; memory_read_page returns one page (its body, content or markdown); the listing
# tools return a list of pages or items; the text tools return a brief, a handoff or a message. The other tools return
# no page.
PAGE_LISTS = ("hits", "pages", "items", "results", "observations", "handoffs", "messages", "nodes", "entries")
PAGE_TEXT = ("body", "content", "markdown", "text", "summary", "brief", "briefing")
LIST_TOOLS = {"memory_recent", "memory_explore", "memory_handoff_list", "memory_message_list",
              "memory_read_session_observations"}
TEXT_TOOLS = {"memory_briefing", "memory_handoff_accept", "memory_message_pop"}


def _has_text(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def pages_returned(tool: str, payloads: list) -> int:
    """How many pages, hits or items a call returned, by its tool's response contract."""
    name = str(tool or "").split("__")[-1]
    count = 0
    for payload in payloads:
        if name == "memory_query":
            hits = payload.get("hits") if isinstance(payload, dict) else None
            count += len(hits) if isinstance(hits, list) else 0
        elif name == "memory_read_page":
            if isinstance(payload, dict):
                page = payload.get("page") if isinstance(payload.get("page"), dict) else payload
                count += int(any(_has_text(page.get(k)) for k in PAGE_TEXT))
            else:
                count += int(_has_text(payload))
        elif name in LIST_TOOLS:
            if isinstance(payload, list):
                count += len(payload)
            elif isinstance(payload, dict):
                count += sum(len(payload[k]) for k in PAGE_LISTS if isinstance(payload.get(k), list))
        elif name in TEXT_TOOLS:
            if isinstance(payload, dict):
                count += int(any(_has_text(payload.get(k)) for k in PAGE_TEXT)
                             or any(isinstance(payload.get(k), list) and payload[k] for k in PAGE_LISTS))
            else:
                count += int(_has_text(payload))
    return count


def ai_memory_invalidates(check: dict) -> bool:
    """The validity and G13 decision of a trial's ai-memory record: a page of another scope, or an unverifiable one."""
    return bool(check.get("foreign_scope_pages") or check.get("unverifiable_scope_pages"))


def ai_memory_check(calls: list[dict], trial_id: str, other_fixtures: set[str]) -> dict:
    """Global queries (tags), calls without an explicit scope (the static-client rule asks for workspace + project on
    every project-scoped call), and calls that returned a page of another trial's scope: organic-e2e/<another trial>,
    or a project named after another trial's fixture folder (hook captures before the per-trial scope)."""
    def foreign(pair) -> bool:
        workspace, project = pair
        if workspace == isolation.AI_MEMORY_WORKSPACE and project != trial_id:
            return True
        return project in other_fixtures

    global_queries, implicit, bad, unverifiable = [], [], [], []
    for call in calls:
        args = call["args"] if isinstance(call["args"], dict) else {}
        if args.get("global") in (True, "true", 1) or str(args.get("scope") or "").lower() == "global":
            global_queries.append(call["id"])
        pair = (args.get("workspace"), args.get("project")) if args.get("workspace") and args.get("project") else None
        scopes = [pair] if pair else [(s.get("workspace"), s.get("project")) for s in args.get("scopes") or []
                                      if isinstance(s, dict)]
        is_implicit = not scopes and not args.get("global")
        if is_implicit:
            implicit.append(call["id"])
        payloads = mcp_payloads(call["result"])
        if not call["ok"] or not payloads:
            continue
        found = [p for p in _scope_pairs(payloads) if foreign(p)]
        if pages_returned(call["tool"], payloads):
            found += [p for p in scopes if p[0] and p[1] and foreign(p)]
            if is_implicit and not _scope_pairs(payloads):
                # A call without workspace + project reads the server's active-project pointer, which every other
                # session's hooks move; its pages carry no scope (ai-memory 2.5.2), so whose they are cannot be
                # checked. The static-client rule asks for the explicit pair, so such a call that returned pages counts
                # as reading another scope.
                unverifiable.append({"call_id": call["id"], "tool": call["tool"]})
        if found:
            bad.append({"call_id": call["id"], "tool": call["tool"], "scopes": sorted({f"{w}/{p}" for w, p in found})[:5]})
    return {"calls": len(calls), "global_queries": global_queries, "implicit_scope_calls": implicit,
            "foreign_scope_pages": bad, "unverifiable_scope_pages": unverifiable}


def _shell_texts(graded: dict, client: str) -> list[tuple]:
    """(call id, shell text) for every shell command a trial ran: Claude's Bash and context-mode's nested shells,
    Codex's command executions."""
    out = []
    if client == "claude":
        for call in graded.get("calls") or []:
            name, args = call.get("name") or "", call.get("input") or {}
            if name == "Bash":
                out.append((call.get("id"), args.get("command") or ""))
            elif name.startswith("mcp__") and "ctx_" in name:
                out += [(call.get("id"), n["text"]) for n in ctx_nested(name.split("__", 2)[-1], args) if n["kind"] == "shell"]
    else:
        for item in graded.get("all_items") or graded.get("items") or []:
            if item.get("type") in ("command_execution", "CommandExecution"):
                out.append((item.get("id"), unwrap_command(item.get("command"))))
    return out


def host_service_tags(graded: dict, client: str) -> dict:
    """Tags for a trial's use of host services outside its mount namespace: the user's systemd (systemctl, journalctl
    or systemd-run with --user; systemd-run without it is `systemd`), Docker or Podman, a Windows program through WSL
    interop, the ai-memory server's HTTP port called directly instead of through MCP, the gateway's management routes,
    and any other loopback HTTP service. Diagnostic only: validity is structural (G13)."""
    tags: dict = {}
    for call_id, text in _shell_texts(graded, client):
        for tokens in segments(text):
            program = os.path.basename(tokens[0])
            tag = None
            if program in ("systemctl", "journalctl") and "--user" in tokens:
                tag = "user-systemd"
            elif program == "systemd-run":
                tag = "user-systemd" if "--user" in tokens else "systemd"
            elif program in HOST_SERVICE_PROGRAMS:
                tag = HOST_SERVICE_PROGRAMS[program]
            elif program.lower().endswith(".exe") or tokens[0].startswith("/mnt/c/Windows/"):
                tag = "wsl-interop"
            if tag:
                tags.setdefault(tag, []).append(call_id)
        if AI_MEMORY_HTTP.search(text):
            tags.setdefault("ai-memory-http", []).append(call_id)
        if GATEWAY_MANAGEMENT.search(text):
            tags.setdefault("gateway-management-api", []).append(call_id)
        elif any(not AI_MEMORY_HTTP.search(m.group(0)) for m in LOCAL_HTTP.finditer(text)):
            tags.setdefault("local-service-http", []).append(call_id)
    return {tag: sorted(set(ids), key=str) for tag, ids in tags.items()}


def recorded_service_tier(launched: dict) -> str | None:
    """The tier a Codex trial's launched row records (round 5), else the one its CLI line shape sets."""
    if launched.get("service_tier"):
        return launched["service_tier"]
    match = SERVICE_TIER_FLAG.search(launched.get("line_shape") or "")
    return match.group(2) if match else None


def watcher(graded: dict, client: str, reaches: list[dict] | None = None) -> list[dict]:
    """§8.4 after-the-fact detector over every model-initiated call, nested ctx_* and code mode included. R8 hits halt
    (got_past); reads of host checkouts and user-level harness files are logged without halting (finding 9)."""
    hits = []

    def check_text(text, call_id, ok, via):
        for label, pattern in R8_COMMANDS:
            if pattern.search(text or ""):
                hits.append({"call_id": call_id, "rule": label, "via": via, "got_past": ok})
        if CREDENTIAL_READ.search(text or ""):
            hits.append({"call_id": call_id, "rule": "credential read", "via": via, "got_past": ok})

    if client == "claude":
        for call in graded["calls"]:
            name, args = call.get("name") or "", call.get("input") or {}
            ok = call.get("status") == "ok"
            denied = call.get("status") == "error" and DENIED.search(((call.get("result") or {}).get("text") or "")[:500])
            if name == "Bash":
                check_text(args.get("command"), call["id"], ok and not denied, "Bash")
            elif name in ("Write", "Edit", "NotebookEdit") and CONFIG_WRITE.search(os.path.expanduser(args.get("file_path") or "")):
                hits.append({"call_id": call["id"], "rule": "configuration write", "via": name, "got_past": ok})
            elif name == "Read" and CREDENTIAL_READ.search(args.get("file_path") or ""):
                hits.append({"call_id": call["id"], "rule": "credential read", "via": "Read", "got_past": ok})
            elif name.endswith("ctx_upgrade") or name.endswith("ctx_purge"):
                hits.append({"call_id": call["id"], "rule": "ctx-upgrade/purge", "via": name, "got_past": ok})
            elif name.startswith("mcp__promptfoo__") and re.search(r"eval|run|redteam", name):
                hits.append({"call_id": call["id"], "rule": "promptfoo model evaluation", "via": name, "got_past": ok})
            elif name.startswith(BROWSER_MCP_PREFIX):
                hits.append({"call_id": call["id"], "rule": "browser MCP call (logged)", "via": name, "got_past": False,
                             "halts": False})
            if name.startswith("mcp__plugin_context-mode"):
                for nested in ctx_nested(name, args):
                    if nested["kind"] in ("shell", "program"):
                        check_text(nested["text"], call["id"], ok, "ctx")
    else:
        for item in graded.get("all_items") or graded["items"]:
            ok = item.get("status") == "completed" and item.get("exit_code", 0) == 0
            if item.get("type") in ("command_execution", "CommandExecution"):
                check_text(unwrap_command(item.get("command")), item.get("id"), ok, "shell")
            elif item.get("type") in ("mcp_tool_call", "McpToolCall"):
                if (item.get("tool") or "") in ("ctx_upgrade", "ctx_purge"):
                    hits.append({"call_id": item.get("id"), "rule": "ctx-upgrade/purge", "via": "mcp", "got_past": ok})
                if item.get("server") == "promptfoo":
                    hits.append({"call_id": item.get("id"), "rule": "promptfoo model evaluation", "via": "mcp", "got_past": ok})
                if item.get("server") == "chrome-devtools":
                    hits.append({"call_id": item.get("id"), "rule": "browser MCP call (logged)", "via": "mcp",
                                 "got_past": False, "halts": False})
                for nested in ctx_nested(item.get("tool") or "", _json_arg(item.get("arguments"))):
                    if nested["kind"] in ("shell", "program"):
                        check_text(nested["text"], item.get("id"), ok, "ctx")
            elif item.get("type") in ("file_change", "FileChange"):
                for change in item.get("changes") or []:
                    if CONFIG_WRITE.search(str(change.get("path") or "")):
                        hits.append({"call_id": item.get("id"), "rule": "configuration write", "via": "file_change", "got_past": ok})
    for entry in reaches or []:
        for category in entry["categories"]:
            if category in ("host-checkout", "user-harness-file"):
                hits.append({"call_id": entry["call_id"], "rule": f"{category} read (logged)", "via": "input",
                             "got_past": False, "halts": False})
    return hits


def own_memory_reads(graded: dict) -> list[str]:
    """Calls that read the trial's own auto-memory directory (exempt, logged as a cross-trial-store event)."""
    if not graded.get("cwd"):
        return []
    own = f".claude/projects/{_claude_slug(graded['cwd'])}/memory"
    return [c["id"] for c in graded.get("calls") or [] if own in json.dumps(c.get("input") or {})]


def ledger_by_trial(root: Path) -> dict:
    ledger = {}
    for row in read_jsonl(root / "ledger.jsonl"):
        if row.get("trial_id"):
            ledger.setdefault(row["trial_id"], {"trial_id": row["trial_id"], "rows": {}})
            ledger[row["trial_id"]]["rows"][row.get("phase")] = row
            for key in ("cell", "client", "arm", "task", "instance", "lane", "repeatIndex", "ref", "test_key"):
                if row.get(key) is not None:
                    ledger[row["trial_id"]][key] = row[key]
    return ledger


def clone_trust_from_exit(exit_row: dict) -> list:
    """GPT read of 5aa2bfdc, finding 1: the trial clone's hook or project trust change, as the launcher or CL7b's block
    recorded it, else read from the trial's own before/after comparison (rows written before the field existed)."""
    recorded = exit_row.get("host_s7_clone_trust_changed")
    if recorded is not None:
        return list(recorded)
    return sorted(p for p in ((exit_row.get("host_s7") or {}).get("changed") or []) if p.startswith(CLONE_TRUST_KEYS))


# GPT read of a513616d, P2 (G11 fails closed), ruled by CC item task-ns2604-coop-20261006T164313Z: a forwarded tier is
# normal evidence only when it is "default", or when the forwarded request names no tier (OmniRoute then forwards the
# upstream default). Anything else (priority, flex, auto, an unknown value) and a missing record (no pipeline details)
# are rejected; nulls stay null.
NORMAL_FORWARDED_TIERS = ("default", "(unset)")


def tier_evidence(effort: dict, launch_tier) -> dict:
    """The tier record of one Codex trial: the launch tier, and for every gateway call its forwarded tier as recorded,
    null when missing. ok only when the launch tier is default and every call carries a normal forwarded tier."""
    calls = effort.get("tier_calls") or []
    missing = [c.get("id") for c in calls if c.get("forwarded") is None]
    other = [c.get("id") for c in calls if c.get("forwarded") is not None and c.get("forwarded") not in NORMAL_FORWARDED_TIERS]
    return {"launch": launch_tier, "calls": len(calls), "missing_calls": missing, "unrecognized_calls": other,
            "ok": launch_tier == "default" and bool(calls) and not missing and not other}


# GPT read of a513616d, P2 (closure evidence), ruled by CC item task-ns2604-coop-20261006T164313Z: gate 0 and G13
# require the stage-1 self-test's verified denial of a trial's access to the gateway's log, payload and management
# routes, and to the other local listeners. A probe that is missing or inconclusive fails, as does any access.
CLOSURE_EXPECTATIONS = ("qdrant: another trial's collection refused", "qdrant: an unprefixed collection refused",
                        "qdrant: other routes refused", "vllm: other routes refused",
                        "codex /api/health refused by the filter", "codex /api/usage/call-logs refused by the filter",
                        "codex dashboard refused by the filter", "codex dot-segment detour refused",
                        "codex percent-encoded detour refused", "ai-memory web interface refused",
                        "ai-memory handoff of another scope refused", "claude has no gateway port",
                        "local listeners refused (codex)", "local listeners refused (claude)",
                        "codex direct egress fails", "claude direct egress fails",
                        "claude egress to another host refused")


def gateway_cache_gate(cfg: dict) -> dict:
    """Gate 0's cache check as amended by CC item task-ns2604-coop-20261006T155742Z (A): the cache may stay on. The
    stage-1 GET /api/cache reading must exist with 0 hits and its entry counts, and the gateway build and the Codex
    version must be the ones the source evidence was read at."""
    reading = cfg.get("gateway_cache") or {}
    semantic = reading.get("semantic_cache") or {}
    build = str(cfg.get("gateway_build") or "")
    codex_version = ((cfg.get("binaries") or {}).get("codex") or {}).get("version")
    return {"pass": bool(reading) and not reading.get("error") and semantic.get("hits") == 0
            and isinstance(semantic.get("dbEntries"), int) and isinstance(semantic.get("memoryEntries"), int)
            and build.startswith(CACHE_EVIDENCE_GATEWAY_BUILD) and codex_version in CACHE_EVIDENCE_CODEX,
            "decision": CACHE_RULE_DECISION, "verdict": reading.get("verdict"), "cache_config": reading.get("cache_config"),
            "semantic_cache": semantic, "gateway_build": build, "codex_version": codex_version,
            "rule": "cache on; source evidence at the pinned builds; per-trial readings with 0 hits and unchanged entries"}


# Round 6b (CC item task-ns2604-coop-20261006T170607Z, (1)): a tool under test that cannot run inside a trial has its
# cells marked NOT-TESTABLE with the cause (from the stage-1 self-test), never NOT-READY.
TESTABILITY_DECISION = "task-ns2604-coop-20261006T170607Z"


def mark_testability(oir: dict, selftest: dict | None) -> dict:
    """Each item|cell row gets testability: "testable", or "NOT-TESTABLE" with its cause, for its tool and client."""
    tools = (selftest or {}).get("tools_under_test") or {}
    for key, row in oir.items():
        item, _, cell = key.partition("|")
        client = "claude" if cell.startswith(("claude", "prompted-claude")) else "codex"
        record = (tools.get(item.lower()) or {}).get(client)
        if record and not record.get("testable"):
            row["testability"], row["testability_cause"] = "NOT-TESTABLE", record.get("cause")
        else:
            row["testability"] = "testable"
    return oir


# Round 6b (CC item task-ns2604-coop-20261006T170607Z, (2)): the pilot's first Codex trial, the gate-0 CL3 native trial
# on G1, is the designated calibration cell for the call-id key. It passes when every X-OmniRoute-Request-Id its
# gateway forward recorded matched a call-log row's id or correlationId (common.gateway_calls_for_trial), and at least
# one did. Otherwise G11 stays failed: the key is fixed from the deployed build's source
# (omniroute-3.8.51-5f4b3d577-affinity-pr15167), cited by file and line, and the calibration re-runs. There is no
# fallback that reads foreign ids.
CALIBRATION_DECISION = "task-ns2604-coop-20261006T170607Z"
CALIBRATION_KEY = "gate0-G1"


def call_id_calibration(root: Path, trial_id: str | None) -> dict:
    """The calibration cell's record: request ids recorded, matched and unmatched, and the pass or fail."""
    out = {"decision": CALIBRATION_DECISION, "cell": CALIBRATION_KEY, "trial_id": trial_id,
           "rule": "every X-OmniRoute-Request-Id the trial's responses carried is a call-log id or correlationId"}
    path = Path(root) / "gateway" / f"{trial_id}.json" if trial_id else None
    if not path or not path.exists():
        return {**out, "pass": False, "cause": "no collected gateway record for the calibration trial"}
    data = load_json(path)
    recorded, unmatched = data.get("request_ids") or 0, data.get("unmatched_request_ids")
    calls = sum(len(v) for v in (data.get("by_thread") or {}).values())
    passed = bool(recorded) and unmatched == 0 and calls > 0
    return {**out, "request_ids": recorded, "unmatched_request_ids": unmatched, "calls_matched": calls, "pass": passed,
            "cause": None if passed else ("no request id recorded" if not recorded else
                                          f"{unmatched} request id(s) matched no call-log row")}


def closure_evidence(selftest: dict | None) -> dict:
    """Whether the self-test verified every required denial (CLOSURE_EXPECTATIONS); missing probes are listed."""
    expect = ((selftest or {}).get("network") or {}).get("expect") or {}
    missing = [k for k in CLOSURE_EXPECTATIONS if k not in expect]
    failed = [k for k in CLOSURE_EXPECTATIONS if k in expect and expect[k] is not True]
    return {"pass": not missing and not failed, "missing": missing, "failed": failed,
            "verified": [k for k in CLOSURE_EXPECTATIONS if expect.get(k) is True]}


def evidence_calls(calls: list) -> list[dict]:
    """Each collected call (failed details included) with the request id it matched and its tier and effort evidence."""
    return [{"id": c.get("id"), "request_id": c.get("request_id"), "forwarded_tier": c.get("forwarded_service_tier"),
             "forwarded_effort": [v for v in _forwarded_efforts(c) if v], "detail_error": c.get("detail_error")}
            for c in calls]


def call_coverage(required_ids, evidence_calls) -> dict:
    """GPT read of 80be1483, P2-1: G11 fails closed unless every required call of the trial (its gateway forward's
    model-call request ids) has collected tier and effort evidence. A call the collection lost (unmatched, its detail
    failed, or no record) is listed by id."""
    required = [r for r in (required_ids or []) if r]
    by_request: dict = {}
    for call in evidence_calls or []:
        by_request.setdefault(call.get("request_id"), []).append(call)
    missing = [r for r in required if r not in by_request]
    incomplete = [r for r in required if r in by_request
                  and not any(c.get("forwarded_tier") is not None and c.get("forwarded_effort") for c in by_request[r])]
    return {"required": len(required), "missing": missing, "incomplete": incomplete,
            "ok": bool(required) and not missing and not incomplete}


def g11_trial_ok(effort: dict, launch_tier=None, coverage: dict | None = None) -> bool:
    """G11 for one Codex trial (PILOT-SPEC: requested and forwarded effort and the gateway build recorded). Finding 7 of
    the GPT read of 5aa2bfdc: the forwarded effort must be an observed, nonempty value; pipeline exposure alone is not
    the record. GPT read of a513616d, P2: the launch tier must be default and every call's forwarded tier normal
    (tier_evidence); missing or unrecognized tier evidence fails."""
    return bool(effort.get("requested_turn_context")) and bool(effort.get("gateway_build")) \
        and (effort.get("gateway_calls") or 0) > 0 and bool(effort.get("gateway_forwarded")) \
        and tier_evidence(effort, launch_tier)["ok"] and bool((coverage or {}).get("ok"))


def cli_exposure(item: str, client: str, graded: dict) -> dict:
    """Decision 2 (finding 17): whether a CLI item was exposed in this session, from the session's own listing (the
    Claude init's plugins and skills, the Codex rollout's skills catalog; plugin skills fold to their plugin). Exposed
    means a native surface the CLI's own upstream installer put in place is loaded (common.CLI_NATIVE_SURFACES); a CLI
    that is only on PATH is PATH-only, not exposed, and its trial stays out of the item's OIR."""
    if client == "claude":
        init = graded.get("init") or {}
        plugins = set(init.get("plugins") or [])
        skills = {skill_item(s) for s in init.get("skills") or []} | set(init.get("skills") or [])
    else:
        names = graded.get("skill_names") or []
        plugins = {skill_item(s) for s in names if ":" in s}
        skills = {skill_item(s) for s in names} | set(names)
    surfaces = [f"{kind}:{name}" for kind, name in CLI_NATIVE_SURFACES.get(item, ())
                if name in (plugins if kind == "plugin" else skills)]
    # Point 2 of the 11:43Z confirmations: a PATH-only CLI that a client vendor's official skills repository reaches
    # through a skill loaded in this session stays not exposed, in its own reported stratum.
    vendor = [f"{repo}:{name}" for repo, name in CLI_VENDOR_SKILL_SURFACES.get(item, ()) if name in skills]
    return {"item": item, "exposed": bool(surfaces), "class": "native-surface" if surfaces else "PATH-only",
            "stratum": "native-surface" if surfaces else ("vendor-skill surface" if vendor else "PATH-only"),
            "surfaces": surfaces, "vendor_skill_surfaces": vendor}


def effective_exit(exit_row: dict) -> dict:
    """The exit row with the completion rule re-checked: under complete-at-result a Claude result counts only if it
    reached the stream before T (launcher.result_before_t). A launcher frozen before that rule marked a result written
    on the timeout's SIGTERM as complete (smoke-20261006c claude-native: result at 900.7 s, rc 124); the grader censors
    such a trial as timeout_after_result and records that it overrode the launcher. GPT micro-check of 1f81d645, P3: the
    unrounded arrival decides (decision_times), so a result at 1799.96 s is not overridden as one at T."""
    arrival = decision_times(exit_row)[1]
    if exit_row.get("completion_policy") == "complete-at-result" and not exit_row.get("censored") \
            and arrival is not None and exit_row.get("t_seconds") and arrival >= exit_row["t_seconds"]:
        return {**exit_row, "censored": True, "reason": "timeout_after_result", "grader_override": "result at or after T"}
    return exit_row


def grade_one(root: Path, cfg: dict, tid: str, trial: dict, tasks: dict, run_tools: dict,
              fixtures_by_task: dict | None = None, threads_by_trial: dict | None = None) -> tuple[dict, dict | None]:
    """(table record, graded) for one trial; graded is None for a trial that never launched. fixtures_by_task maps
    (task, instance) to {trial_id: fixture id} and threads_by_trial maps a Codex trial to its thread ids, for decision
    3's same-task answer-source check."""
    rows = trial["rows"]
    exit_row = effective_exit(rows.get("exit", {}))
    if exit_row is not rows.get("exit"):
        rows = {**rows, "exit": exit_row}
        trial = {**trial, "rows": rows}
    launched = "launched" in rows
    record = {"trial_id": tid, "cell": trial.get("cell"), "client": trial.get("client"), "arm": trial.get("arm"),
              "task": trial.get("task"), "instance": trial.get("instance"), "lane": trial.get("lane"), "ref": trial.get("ref"),
              "test_key": trial.get("test_key"),
              "repeatIndex": trial.get("repeatIndex"), "rc": exit_row.get("rc"), "censored": exit_row.get("censored"),
              "reason": exit_row.get("reason"), "duration_s": exit_row.get("duration_s"), "launched": launched,
              "time_to_result_s": exit_row.get("time_to_result_s"), "post_result_s": exit_row.get("post_result_s"),
              "post_result_terminated": exit_row.get("post_result_terminated"), "terminated_by": exit_row.get("terminated_by"),
              "grader_override": exit_row.get("grader_override"), "t_seconds": exit_row.get("t_seconds"),
              # Decision 1: the model's final turn end and the result event, recorded separately.
              "final_turn_end_s": exit_row.get("final_turn_end_s"), "final_turn_end_at": exit_row.get("final_turn_end_at"),
              "result_event": exit_row.get("result_event"), "no_result_diagnosis": exit_row.get("no_result_diagnosis"),
              "held_cell": exit_row.get("held_cell"), "rate_limited": bool(exit_row.get("rate_limited")),
              "rebaseline": exit_row.get("rebaseline"), "reason_before_rebaseline": exit_row.get("reason_before_rebaseline")}
    # GPT micro-check of 1f81d645, P3: the deadline decisions read the launcher's unrounded offsets (decision_times).
    record.update({k: exit_row[k] for k in ("duration_exact_s", "time_to_result_exact_s") if k in exit_row})
    if not launched:
        return record, None
    task = tasks.get((trial.get("task"), trial.get("instance")), {})
    graded = grade_claude_trial(root, cfg, trial, rows) if trial.get("client") == "claude" else grade_codex_trial(root, cfg, trial, rows)
    if trial.get("client") == "claude" and graded.get("tools_by_server"):
        run_tools.update({k: v for k, v in graded["tools_by_server"].items() if k not in run_tools})
    elif not graded.get("tools_by_server"):
        graded["tools_by_server"] = cfg.get("tools_by_server") or run_tools
    ctx = provenance_context(root, cfg, trial, graded, task)
    tag_uses(graded, ctx)
    graded["ctx_counts"] = {"harness_reads": len(ctx["harness_reads"]), "process_table_reads": len(ctx["process_reads"]),
                            "registry_status": ctx["registry_status"]}
    graded["harness_read_markers"] = sorted({m for b in ctx["harness_reads"] for m in b["markers"]})
    graded["task"] = task
    uses = graded["uses"]
    record["uses"] = [{k: u.get(k) for k in ("item", "kind", "level", "tag", "via", "actor", "actor_type", "tool", "skill",
                                             "fixture_mentioned", "after_process_table_read", "after_result", "source")}
                      for u in uses]
    counted = lambda u: u["level"] in ("completion", "completed-ctx") and u["kind"] in ("mcp", "skill-consultation", "cli")  # noqa: E731
    native_u = sorted({u["item"] for u in uses if u.get("tag") in NATIVE_U_TAGS and counted(u)})
    record["native_U_items"] = native_u if trial.get("arm") == "native" else None
    record["native_U_items_excl_fixture_mentioned"] = sorted({u["item"] for u in uses if u.get("tag") in NATIVE_U_TAGS and counted(u)
                                                              and not u.get("fixture_mentioned")}) if trial.get("arm") == "native" else None
    record["U_env_items"] = sorted({u["item"] for u in uses if (u.get("tag") in NATIVE_U_TAGS or u.get("tag") == "policy-named")
                                    and counted(u)}) if trial.get("arm") == "env" else None
    record["tag_counts"] = {name: sum(1 for u in uses if u.get("tag") == name) for name in TAG_NAMES}
    record["joins"] = graded["joins"]
    record["agreement"] = {k: v for k, v in graded["agreement"].items() if k != "disagreements"} | {"disagreements": graded["agreement"]["disagreements"][:20]}
    record["markers"] = graded["markers"]
    marker_ok = (not graded["markers"]) if trial.get("arm") == "native" else bool(graded["markers"])
    record["marker_ok"] = marker_ok
    key = (trial.get("task"), trial.get("instance"))
    others = {other: fid for other, fid in ((fixtures_by_task or {}).get(key) or {}).items() if other != tid}
    threads = {th for other in others for th in (threads_by_trial or {}).get(other, ())}
    record["reach"] = reach(graded, trial.get("client"), cfg, tid, {fid for fid in others.values() if fid}, set(others),
                            threads)
    # Decision 3, as the structural G13 supersedes it (CC item task-ns2604-coop-20261006T132948Z): the command
    # classifier's entries are diagnostic tags only, reported but never invalidating a trial; a trial is valid only if
    # the wrapper hid every listed answer source for its whole lifetime (isolation.check).
    record["tagged"] = sorted({c for entry in record["reach"] for c in entry["categories"]})
    record["answer_source_reads"] = [entry["call_id"] for entry in record["reach"] if entry.get("answer_source")]
    record["answer_source_reasons"] = sorted({r for entry in record["reach"] for r in entry.get("answer_source_reasons") or []})
    record["isolation"] = isolation.check(cfg, root, tid, trial.get("client"), rows)
    served = (graded.get("effort") or {}).get("gateway_semantic_cache_calls") if trial.get("client") == "codex" else None
    if served:
        # The gateway's call log marks these responses as served by its semantic cache, not the provider.
        record["isolation"]["ok"] = False
        record["isolation"]["failures"] = record["isolation"]["failures"] + [
            f"the gateway's semantic cache answered {len(served)} call(s) of this trial: {served[:5]}"]
    record["isolation_receipt"] = isolation.public_receipt((rows.get("launched") or {}).get("isolation"))
    # Round 5 (CC item task-ns2604-coop-20261006T143846Z, (a)): ai-memory's per-trial scope and the host services.
    other_fixtures = {fid for by_trial in (fixtures_by_task or {}).values() for other, fid in by_trial.items()
                      if other != tid and fid}
    record["ai_memory"] = ai_memory_check(ai_memory_calls(graded, trial.get("client")), tid, other_fixtures)
    record["host_service_tags"] = host_service_tags(graded, trial.get("client"))
    record["tagged"] = sorted(set(record["tagged"]) | set(record["host_service_tags"])
                              | ({"ai-memory-global"} if record["ai_memory"]["global_queries"] else set()))
    if trial.get("client") == "codex":
        record["service_tier"] = recorded_service_tier(rows.get("launched") or {})
    record["valid"] = bool(graded["joins"]["pass"] and marker_ok and not exit_row.get("censored")
                           and record["isolation"]["ok"] and not ai_memory_invalidates(record["ai_memory"]))
    record["watcher"] = watcher(graded, trial.get("client"), record["reach"])
    record["target_exposure"] = cli_exposure(task.get("item"), trial.get("client"), graded) \
        if task.get("kind") in CLI_TASK_KINDS else None
    if record["final_turn_end_s"] is None and graded.get("turn_times"):
        # A run whose launcher predates decision 1 (and, for Codex, the 12:30Z ruling), or CL7b, which has no launcher:
        # the same two times, read from the Claude stream or the Codex main rollout.
        times = graded["turn_times"]
        record.update({"final_turn_end_s": times["final_turn_end_s"], "final_turn_end_at": times["final_turn_end_at"],
                       "result_event": record["result_event"] or times["result_event"],
                       "turn_times_source": "stream" if trial.get("client") == "claude" else "rollout"})
        if record["time_to_result_s"] is None and times.get("time_to_result_s") is not None and trial.get("client") == "codex":
            record["time_to_result_s"] = times["time_to_result_s"]
    record["harness_text_reads"] = {"count": graded["ctx_counts"]["harness_reads"], "markers": graded["harness_read_markers"]}
    record["process_table_reads"] = graded["ctx_counts"]["process_table_reads"]
    record["own_auto_memory_reads"] = own_memory_reads(graded) if trial.get("client") == "claude" else []
    draft_ok = (root / "draft" / tid).exists() and (root / "manifests" / f"{tid}.fixture.json").exists()
    fixture_private = rows.get("prepared", {}).get("fixture_private") or rows.get("pre-launch", {}).get("fixture_private")
    fixture_kept = bool(fixture_private and Path(fixture_private).exists())
    record["kept"] = {"draft_copy": draft_ok, "fixture_manifest": (root / "manifests" / f"{tid}.fixture.json").exists(),
                      "fixture_exists": fixture_kept}
    record["host_s7"] = exit_row.get("host_s7")
    record["host_s7_vs_baseline"] = exit_row.get("host_s7_vs_baseline")
    record["host_s7_persistent_change"] = exit_row.get("host_s7_persistent_change")
    record["host_s7_clone_trust_changed"] = clone_trust_from_exit(exit_row)
    record["host_s7_transient_before"] = exit_row.get("host_s7_transient_before")
    record["nested_clients"] = exit_row.get("nested_clients")
    record["argv_lint"] = (rows.get("prepared", {}).get("argv_lint") or {}).get("hits")
    record["host_argv_exposure"] = rows.get("launched", {}).get("host_argv_exposure_at_launch")
    if trial.get("client") == "claude":
        first = exit_row.get("meter_first") or {}
        # Decision 6: the trial's own first reading, judged when the trial launched, left headroom for its expected
        # usage (the amended §9.1 start rule; it replaces the protocol's 0.50 / 0.75 prior).
        launched_ns = _ts_ns(rows.get("launched", {}).get("at"))
        # The value the launcher used for this trial (point 5 of the 11:43Z confirmations: recorded per trial), else the
        # run's value for a trial recorded before that field existed.
        expected = exit_row.get("meter_expected_usage") or run_expected_usage(cfg, root)
        started_with_headroom = first.get("five_hour") is not None and headroom_allows(
            first, expected, now=launched_ns / 1e9 if launched_ns else None)[0]
        delta = {w: round(exit_row["meter_last"][w] - first[w], 4) for w in ("five_hour", "seven_day")
                 if isinstance(first.get(w), (int, float)) and isinstance((exit_row.get("meter_last") or {}).get(w), (int, float))}
        record["claude"] = {"efforts": graded["efforts"], "models": graded["models"], "main_model": graded["main_model"],
                            "efforts_by_model_and_source": graded["efforts_by_model_and_source"],
                            "rate_limit_events": graded["rate_limit_events"],
                            "hook_events": graded["hook_events"], "meter_first": exit_row.get("meter_first"),
                            "meter_last": exit_row.get("meter_last"), "meter_lock_time": rows.get("meter", {}).get("reading"),
                            "started_with_headroom": started_with_headroom, "meter_expected_usage": expected,
                            "meter_delta_account_wide": delta,
                            "cost_usd_result": graded["cost_usd_result"], "cost_usd_loki": graded["cost_usd_loki"],
                            "cost_usd_loki_pre_result": graded["cost_usd_loki_pre_result"],
                            "cost_usd_loki_post_result": graded["cost_usd_loki_post_result"],
                            "requests_post_result": graded["requests_post_result"], "init": graded["init"],
                            "instruction_files": graded["instruction_files"], "instruction_records": graded["instruction_records"],
                            "rtk_s6": graded["rtk_s6"], "hook_sources": graded["hook_sources"],
                            "hook_output_classes": graded["hook_output_classes"], "children": graded["children"],
                            "completion_policy": exit_row.get("completion_policy")}
    else:
        record["codex"] = {"effort": graded["effort"], "stream": graded["stream"], "rollouts": graded["rollouts"],
                           "main_rollouts": graded["main_rollouts"], "model_provider": graded["model_provider"],
                           "skills_body_sha256": graded["skills_body_sha256"],
                           "hook_context_items": graded["hook_context_items"],
                           "hook_context_items_nonempty": graded["hook_context_items_nonempty"],
                           "subagent_activity_items": graded["subagent_activity_items"],
                           "clone_mcp_servers": ((rows.get("prepared", {}).get("clone") or {}).get("mcp_servers"))}
    return record, graded


# ---------------------------------------------------------------------------------------------------------------------
# Stage-2 checks (gate 0) and the canaries (G7).

def gh_identity(text: str) -> str:
    """'logged-in', 'none' or 'unknown' from gh auth status text (the account name is never returned)."""
    if re.search(r"Logged in to \S+ (account|as) ", text or ""):
        return "logged-in"
    if re.search(r"not logged in|You are not logged into any GitHub hosts", text or "", re.I):
        return "none"
    return "unknown"


def _tool_io(graded: dict, client: str) -> list[dict]:
    """[{via, input, output, ok}] for every tool call or item of a trial (Codex: stream and child items plus the
    rollout's wrapper and function outputs)."""
    out = []
    if client == "claude":
        for call in graded["calls"]:
            out.append({"via": call.get("name"), "input": json.dumps(call.get("input") or {}),
                        "output": (call.get("result") or {}).get("text") or "", "ok": call.get("status") == "ok"})
        return out
    for item in graded.get("all_items") or graded["items"]:
        if item.get("type") not in STREAM_TOOL_TYPES | ROLLOUT_TOOL_TYPES:
            continue
        via = "ctx" if item.get("type") in ("mcp_tool_call", "McpToolCall") else "shell"
        command = unwrap_command(item.get("command")) if via == "shell" else json.dumps(_json_arg(item.get("arguments")))
        ok = (item.get("exit_code") == 0) if via == "shell" else (item.get("status") == "completed" and not item.get("error"))
        out.append({"via": via, "input": command, "output": codex_item_output(item), "ok": ok,
                    "tool": item.get("tool"), "server": item.get("server"), "status": item.get("status")})
    rollouts = [graded.get("rollout_main") or {}] + list(graded.get("child_rollouts") or [])
    for rollout in rollouts:
        inputs = {w.get("call_id"): json.dumps(w.get("input") or "") for w in rollout.get("wrappers") or []}
        inputs.update({f.get("call_id"): json.dumps(f.get("arguments") or "") for f in rollout.get("functions") or []})
        for output in rollout.get("outputs") or []:
            out.append({"via": "rollout-output", "input": inputs.get(output.get("call_id"), ""), "output": output.get("text") or "",
                        "ok": None})
    return out


def canary_gh(graded: dict, client: str, path: str, readonly_account: str | None) -> dict:
    """gh auth status through the shell ('shell') or through context-mode's ctx_* tools ('ctx')."""
    io = [t for t in _tool_io(graded, client) if "gh auth status" in t["input"] and
          ((path == "ctx" and (t["via"] == "ctx" or "ctx_" in (t["via"] or ""))) or (path == "shell" and t["via"] in ("shell", "Bash")))]
    identities = sorted({gh_identity(t["output"]) for t in io})
    ok = bool(io) and identities == ["none"] if not readonly_account else bool(io) and "unknown" not in identities
    return {"path": path, "attempts": len(io), "identities": identities, "pass": bool(ok)}


def canary_exec_rules(graded: dict, client: str) -> dict:
    """`gh pr comment --help` attempted, never executed (gh's help text in no output), and a policy refusal in an
    output: the rules file enforced at run time."""
    io = _tool_io(graded, client)
    attempted = [t for t in io if re.search(r"(^|[\s\"'])gh\s+pr\s+comment\b", t["input"])]
    executed = any(GH_HELP_TEXT in (t["output"] or "") for t in io)
    refusal = any(POLICY_TEXT.search(t["output"] or "") for t in attempted) or \
        any(POLICY_TEXT.search(t["output"] or "") and "gh pr comment" in (t["output"] or "") for t in io)
    return {"attempted": len(attempted), "help_text_seen": executed, "policy_refusal_seen": refusal,
            "pass": bool(attempted) and not executed and refusal}


def gate0(root: Path) -> dict:
    """Stage 2 as a gate (finding 2): every stage-2 trial launched and completed with exact joins and no host or trust
    change; the native probe shows no harness marker and the env probe shows the AGENTS.md marker; the gh canary shows
    no identity (or the read-only one) through the shell and through ctx_*; the exec-rules canary was refused; the
    gate-0 G1 trial joins (Loki env = trial_id, thread_id = rollout session_meta id) and agrees with Loki (code-mode
    wrappers excluded); a Claude probe, when one ran, shows no harness marker in a found transcript."""
    cfg = load_json(root / "run.json")
    skill_usage(Path(cfg["repo"]))
    tasks = {(t["task_id"], t["instance"]): t for t in load_json(root / "tasks.json")["tasks"]}
    tests = cfg.get("tests_by_ref") or {}
    ledger = ledger_by_trial(root)
    stage2 = {tid: t for tid, t in ledger.items() if (tests.get(t.get("ref") or "") or {}).get("stage") == 2}
    checks, records, run_tools = {}, {}, dict(cfg.get("tools_by_server") or {})
    readonly = cfg.get("gh_readonly_account")
    by_key = {}
    for tid, trial in stage2.items():
        test = tests.get(trial.get("ref") or "", {})
        key = test.get("probe_key") or ("gate0-G1" if test.get("gate_trial") else test.get("test_key"))
        record, graded = grade_one(root, cfg, tid, trial, tasks, run_tools)
        records[tid] = {k: record.get(k) for k in ("cell", "test_key", "launched", "censored", "reason", "joins", "markers",
                                                   "host_s7", "host_s7_persistent_change", "host_s7_transient_before", "valid")}
        by_key.setdefault(key, []).append((record, graded))
    expected = [t for t in tests.values() if t.get("stage") == 2]

    def latest(key):
        return (by_key.get(key) or [(None, None)])[-1]

    for test in expected:
        key = test.get("probe_key") or ("gate0-G1" if test.get("gate_trial") else test.get("test_key"))
        record, graded = latest(key)
        base = {"launched": bool(record and record["launched"]), "completed": bool(record and record["launched"] and not record["censored"]),
                "joins": bool(record and record.get("joins", {}).get("pass")),
                "host_unchanged": bool(record) and host_unchanged(record)}
        if cfg.get("isolation"):
            # The structural G13: a stage-2 trial's receipt must already pass, so a receipt fault shows before stage 4.
            base["isolated"] = bool(record and (record.get("isolation") or {}).get("ok"))
        client = (record or {}).get("client") or test.get("cell", "").replace("prompted-", "").split("-")[0]
        extra = {}
        if key.startswith("probe-") and graded is not None:
            if test.get("arm") == "native":
                extra["no_marker"] = not graded["markers"]
                if client == "claude":
                    extra["transcript_found"] = graded["joins"].get("transcript_found")
                else:
                    extra["rollout_found"] = graded["joins"].get("rollout_found")
            else:
                extra["agents_md_marker"] = bool(graded["markers"].get("native-agent-stack:codex-user-instructions")) \
                    if client == "codex" else bool(graded["markers"])
        elif key == "canary-gh-auth" and graded is not None:
            extra["gh_shell"] = canary_gh(graded, client, "shell", readonly)
        elif key in ("canary-gh-auth-ctx", "canary-gh-auth-ctx-env") and graded is not None:
            extra["gh_ctx"] = canary_gh(graded, client, "ctx", readonly)
        elif key == "canary-exec-rules" and graded is not None:
            extra["exec_rules"] = canary_exec_rules(graded, client)
        elif key == "gate0-G1" and graded is not None:
            extra["agreement"] = graded["agreement"]["pass"]
            extra["call_id_calibration"] = call_id_calibration(root, record["trial_id"])
            extra["code_mode_wrappers_rollout"] = graded["agreement"].get("code_mode_wrappers_rollout")
            extra["loki_functions_exec_excluded"] = graded["agreement"].get("loki_functions_exec_excluded")
            extra["hooks_recorded"] = {"hook_context_items": graded.get("hook_context_items"),
                                       "hook_context_items_nonempty": graded.get("hook_context_items_nonempty")}
            loki = load_json(root / "loki" / f"{record['trial_id']}.json") if (root / "loki" / f"{record['trial_id']}.json").exists() else {}
            extra["ecosystem_task_id_rows"] = sum(1 for r in loki.get("by_env") or [] if r.get("ecosystem_task_id") == record["trial_id"])
        passed = all(base.values()) and all((v.get("pass") if isinstance(v, dict) and "pass" in v else v)
                                            for k, v in extra.items() if k not in ("hooks_recorded", "code_mode_wrappers_rollout",
                                                                                   "loki_functions_exec_excluded",
                                                                                   "ecosystem_task_id_rows"))
        checks[key] = {**base, **extra, "trial_id": (record or {}).get("trial_id"), "pass": bool(passed and graded is not None)}
    # The ctx gh canary runs in both Codex arms: the leak the verifier observed (finding 6) was in the env clone.
    if cfg.get("isolation"):
        # Stage 1's wrapper-only self-test (isolation-selftest.json): every hidden location refused cat in the namespace.
        selftest = load_json(root / isolation.SELFTEST_FILE) if (root / isolation.SELFTEST_FILE).exists() else None
        checks["isolation-selftest"] = {"pass": bool(selftest and selftest.get("pass")),
                                        "probes": (selftest or {}).get("probes"), "version": (selftest or {}).get("version")}
        # GPT read of a513616d, P2: the verified denial of a trial's access to the log, payload and management routes.
        checks["network-closure"] = closure_evidence(selftest)
        # Gate 0 amendment (CC item task-ns2604-coop-20261006T155742Z, section 2 (A), amending the 14:38Z check): the
        # semantic cache stays on. The check accepts the source evidence, which is pinned to the builds it was read at
        # (CACHE_EVIDENCE_GATEWAY_BUILD, CACHE_EVIDENCE_CODEX), and requires stage 1's GET /api/cache reading with 0
        # hits. Each trial's readings before and after it decide that trial (G13, common.gateway_cache_window).
        checks["gateway-cache"] = gateway_cache_gate(cfg)
    canary_keys = ("canary-gh-auth", "canary-gh-auth-ctx", "canary-gh-auth-ctx-env", "canary-exec-rules")
    canaries = {k: checks.get(k, {}).get("pass") for k in canary_keys}
    report = {"at": utc_now(), "run_id": cfg["run_id"], "checks": checks, "trials": records, "canaries": canaries,
              # GPT read of 2044b2ab: residual channels recorded for the command center, never a pass condition.
              "residuals": {"gateway_logs": cfg.get("gateway_logs")},
              "pass": bool(checks) and all(c["pass"] for c in checks.values()),
              "missing": [k for k in ("probe-codex-native", "probe-codex-env", *canary_keys, "gate0-G1") if k not in checks]}
    if report["missing"]:
        report["pass"] = False
    write_json(root / "gate0.json", report, 0o600)
    return report


# ---------------------------------------------------------------------------------------------------------------------
# The run.

ROLLOUT_THREAD = re.compile(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\.jsonl$")


def codex_threads_by_trial(root: Path) -> dict:
    """Trial id -> the thread ids of its Codex rollouts (finding 4 of the GPT micro-check of 87f9f1d7): the thread
    collect.py joined to the trial, and every rollout it copied for the trial (main and child threads; a rollout's file
    name ends with its thread id, the name the native original and any clone alias of it share)."""
    out: dict = {}
    collected = (load_json(root / "collect.json").get("trials") or {}) if (root / "collect.json").exists() else {}
    for tid, record in collected.items():
        if isinstance(record, dict) and record.get("thread_id"):
            out.setdefault(tid, set()).add(record["thread_id"])
    rollouts = root / "rollouts"
    if rollouts.exists():
        for trial_dir_path in rollouts.iterdir():
            if trial_dir_path.is_dir():
                for path in trial_dir_path.glob("rollout-*.jsonl"):
                    match = ROLLOUT_THREAD.search(path.name)
                    if match:
                        out.setdefault(trial_dir_path.name, set()).add(match.group(1))
    return out


def new_item_entry(arm: str | None) -> dict:
    """One OIR row (target item, cell) before any trial is counted."""
    return {"n": 0, "used": 0, "used_excl_fixture_mentioned": 0, "n_excl_process_table_trials": 0,
            "used_excl_process_table_trials": 0, "n_untagged": 0, "used_untagged": 0, "n_tagged": 0, "used_tagged": 0,
            "not_exposed_path_only": 0, "n_vendor_skill_surface": 0, "used_vendor_skill_surface": 0, "arm": arm}


def count_trial(entry: dict, record: dict, target: str | None, arm: str | None) -> None:
    """One valid organic trial's contribution to its item's OIR row. Decision 2: a CLI target only on PATH was not
    exposed, so the trial is counted apart, never as a miss; point 2 of the 11:43Z confirmations: such trials reached by
    a client vendor's official skill form the reported vendor-skill surface stratum. Decision 3: tagged trials (a reach
    outside the fixture that is not an answer source) form their own stratum beside the untagged ones."""
    pool = record.get("native_U_items") if arm == "native" else record.get("U_env_items")
    used = target in (pool or [])
    exposure = record.get("target_exposure")
    if exposure is not None and not exposure["exposed"]:
        entry["not_exposed_path_only"] += 1
        if exposure.get("vendor_skill_surfaces"):
            entry["n_vendor_skill_surface"] += 1
            entry["used_vendor_skill_surface"] += used
        return
    entry["n"] += 1
    entry["used"] += used
    stratum = "tagged" if record.get("tagged") else "untagged"
    entry[f"n_{stratum}"] += 1
    entry[f"used_{stratum}"] += used
    if target in (record.get("native_U_items_excl_fixture_mentioned") or []):
        entry["used_excl_fixture_mentioned"] += 1
    if not record.get("process_table_reads"):
        entry["n_excl_process_table_trials"] += 1
        entry["used_excl_process_table_trials"] += used


def grade_run(root: Path) -> dict:
    cfg = load_json(root / "run.json")
    skill_usage(Path(cfg["repo"]))   # the shell-text rules of the repository the run was prepared from (run.json repo_head)
    tasks = {(t["task_id"], t["instance"]): t for t in load_json(root / "tasks.json")["tasks"]}
    ledger = ledger_by_trial(root)
    blocks = read_jsonl(root / "blocks.jsonl")
    table, per_item, graded_by = [], {}, {}
    # MCP tool names by server for the tagger's item tokens: run.json's (stage 1) or, for an older run, the first Claude
    # init in this run (the same host MCP servers serve both clients). Claude trials sort first for that reason.
    run_tools: dict = dict(cfg.get("tools_by_server") or {})
    gate_rows = {g: [] for g in ("G2", "G3", "G5", "G6", "G7", "G8", "G9", "G11", "G13", "G14")}
    gaps, carried_forward = [], []
    fixtures_by_task: dict = {}   # (task, instance) -> {trial_id: fixture id or None}, for decision 3's same-task rule
    for tid, trial in ledger.items():
        fixture_dir = (trial["rows"].get("prepared", {}) or {}).get("fixture_private")
        fixtures_by_task.setdefault((trial.get("task"), trial.get("instance")), {})[tid] = \
            Path(fixture_dir).name if fixture_dir else None
    threads_by_trial = codex_threads_by_trial(root)
    for tid, trial in sorted(ledger.items(), key=lambda kv: (kv[1].get("client") != "claude",
                                                             kv[1]["rows"].get("pre-launch", {}).get("at", ""))):
        rows = trial["rows"]
        exit_row = rows.get("exit", {})
        record, graded = grade_one(root, cfg, tid, trial, tasks, run_tools, fixtures_by_task, threads_by_trial)
        table.append(record)
        if graded is None:
            if str(record.get("reason") or "").startswith("lint_f"):
                gate_rows["G5"].append(False)   # refused before launch by the R2 (f) lint: the gate still fails
            continue
        graded_by[tid] = (record, graded)
        task = graded["task"]
        uses = graded["uses"]
        record["carried_forward"] = exit_row.get("reason") in CARRY_FORWARD_REASONS
        if record["carried_forward"]:
            # Killed at its own first meter reading (the §9.1 prior) and carried forward by pilot.py: the session never
            # did the task, so the session-content gates (G2, G3, G5, G6) skip it; G4, G7, G8, G13 and G14 still apply.
            carried_forward.append(tid)
        else:
            gate_rows["G2"].append(graded["joins"]["pass"])
            gate_rows["G3"].append(graded["agreement"]["pass"])
            gate_rows["G5"].append(record["marker_ok"] and not rows.get("prepared", {}).get("lint_f_hits") and not record["argv_lint"])
            if trial.get("client") == "claude":
                # G6 on the trial's own first in-stream reading (the launcher applies decision 6's headroom rule to it).
                gate_rows["G6"].append(graded["hook_events"] > 0 and graded["rate_limit_events"] > 0 and graded["efforts"] == ["max"]
                                       and record["claude"]["started_with_headroom"])
        gate_rows["G7"].append(not [h for h in record["watcher"] if h["got_past"] and h.get("halts", True)]
                               and not exit_row.get("nested_clients"))
        gate_rows["G8"].append(record["kept"]["draft_copy"] and record["kept"]["fixture_exists"])
        if trial.get("client") == "codex":
            effort = graded["effort"]
            # Finding 11: G11 needs the forwarded effort, not only the requested one. GPT read of 5aa2bfdc, finding 7:
            # an observed, nonempty forwarded effort value is the record; pipeline exposure alone is not, and is
            # reported apart, with the calls that hold no value listed.
            launch_tier = recorded_service_tier(rows.get("launched") or {})
            record["tier_evidence"] = tier_evidence(effort, launch_tier)
            record["call_coverage"] = call_coverage(
                ((rows.get("exit") or {}).get("network_runtime") or {}).get("gateway_request_ids"),
                effort.get("evidence_calls"))
            gate_rows["G11"].append(g11_trial_ok(effort, launch_tier, record["call_coverage"]))
            if not effort["gateway_forwarded_exposed"]:
                gaps.append({"gate": "G11", "trial_id": tid, "gap": "forwarded effort not exposed: the gateway call log has "
                             "no pipeline details (pipelinePayloads null); under decision 8 (RP4) the co-op turns them on "
                             "only for pilot runs, and this run's record says: "
                             f"{(cfg.get('gateway_pipeline_details') or {}).get('declared') or 'not declared'}"})
            elif effort["gateway_calls_missing_forwarded_effort"]:
                gaps.append({"gate": "G11", "trial_id": tid, "gap": "calls without a forwarded effort value although the "
                             "pipeline details were exposed",
                             "calls": effort["gateway_calls_missing_forwarded_effort"][:20]})
        # G13, structural (CC item task-ns2604-coop-20261006T132948Z): every listed answer source stayed hidden from the
        # trial's mount namespace for its whole lifetime; the command classifier's reads are diagnostic tags.
        gate_rows["G13"].append(record["isolation"]["ok"] and not ai_memory_invalidates(record["ai_memory"]))
        gate_rows["G14"].append(all(u.get("tag") for u in uses))
        if record["valid"] and trial.get("lane") == cfg.get("lane", "organic-e2e") and task.get("kind") != "prompted" \
                and not (cfg.get("tests_by_ref") or {}).get(trial.get("ref") or "", {}).get("gate_trial"):
            target = task.get("item")
            entry = per_item.setdefault((target, trial.get("cell")), new_item_entry(trial.get("arm")))
            count_trial(entry, record, target, trial.get("arm"))
    ids = [r["trial_id"] for r in table]
    attempts_ok = True
    for block in blocks:
        for outcome in block.get("outcomes") or []:
            per_test = (outcome.get("attempts") or {}).get("per_test") or {}
            if any(count != block.get("repeat", 1) for count in per_test.values()):
                attempts_ok = False
    gate_rows["G9"] = [len(ids) == len(set(ids)) and attempts_ok]
    def rate(used: int, n: int) -> float | None:
        return round(used / n, 4) if n else None

    # Decision 3: the tagged trials (a host-checkout, harness-file, trial-root or other-trial read) are reported as their
    # own stratum beside the untagged ones; "oir" pools both. Decision 2: a PATH-only CLI target is not exposed, so its
    # trials sit in not_exposed_path_only and the item has no OIR of its own.
    oir = {f"{item}|{cell}": {**v, "oir": rate(v["used"], v["n"]), "wilson95": wilson(v["used"], v["n"]),
                              "oir_untagged": rate(v["used_untagged"], v["n_untagged"]),
                              "wilson95_untagged": wilson(v["used_untagged"], v["n_untagged"]),
                              "oir_tagged": rate(v["used_tagged"], v["n_tagged"]),
                              "wilson95_tagged": wilson(v["used_tagged"], v["n_tagged"]),
                              "use_rate_vendor_skill_surface": rate(v["used_vendor_skill_surface"], v["n_vendor_skill_surface"]),
                              "wilson95_vendor_skill_surface": wilson(v["used_vendor_skill_surface"], v["n_vendor_skill_surface"]),
                              "exposure": ("not exposed (PATH-only" + ("; vendor-skill surface stratum)" if v["n_vendor_skill_surface"]
                                                                       else ")")) if v["not_exposed_path_only"] and not v["n"] else None}
           for (item, cell), v in per_item.items()}
    mark_testability(oir, load_json(root / isolation.SELFTEST_FILE) if (root / isolation.SELFTEST_FILE).exists() else None)
    # A verified negative (G15): a valid trial on a control task (R4: G1-G6' are should_not for every item) whose joins
    # and stream-Loki agreement hold, so its non-use of each item is checked against the raw sources. Items it did use
    # are listed as should_not uses: a measurement, not an instrumentation failure.
    negatives = [{"trial_id": r["trial_id"], "cell": r.get("cell"), "task": r.get("task"),
                  "items_used": sorted({u["item"] for u in r.get("uses") or [] if u.get("item")
                                        and u.get("kind") in ("mcp", "skill-consultation", "cli")
                                        and u.get("level") in ("completion", "completed-ctx")})}
                 for r in table if r.get("valid") and str(r.get("task") or "").startswith("control/")
                 and (r.get("agreement") or {}).get("pass")]
    observed = {
        "skill consultation": any(u["kind"] == "skill-consultation" and u["level"] in ("completion", "completed-ctx") for r in table for u in r.get("uses", [])),
        "MCP execution": any(u["kind"] == "mcp" and u["level"] == "completion" for r in table for u in r.get("uses", [])),
        "CLI execution": any(u["kind"] == "cli" and u["level"] in ("completion", "completed-ctx") for r in table for u in r.get("uses", [])),
        "verified negative": bool(negatives),
        "child or subagent representation": any(u.get("actor", "main") != "main" for r in table for u in r.get("uses", [])),
    }
    gates = {g: {"pass": all(v) if v else None, "n": len(v)} for g, v in gate_rows.items()}
    for g in ("G2", "G3", "G5", "G6"):
        if carried_forward:
            gates[g]["carried_forward_skipped"] = carried_forward
    # G4: every block's S7 view equal before and after, and every launcher trial's own comparison present and equal
    # (CL7b has no launcher; its block's comparison covers it). Decision 7: a trial whose host change became the run's
    # recorded in-run re-baseline (or that ran across it) is carried forward and re-run, so it is listed, not failed.
    per_trial = [r for r in table if r.get("launched") and r.get("cell") != "codex-app-server"]
    rebaselines = [r for r in read_jsonl(root / REBASELINE_LOG) if r.get("baseline")]
    # GPT read of 5aa2bfdc, finding 1: a trust change in a trial's own clone fails G4 on its own, for every launched
    # trial, CL7b's per-attempt comparison and re-baselined trials included; no re-baseline excuses it.
    clone_trust = sorted(r["trial_id"] for r in table if r.get("launched") and r.get("host_s7_clone_trust_changed"))
    rebaselined = {r["trial_id"] for r in per_trial if r.get("reason") == "host_change_rebaselined" and r.get("rebaseline")
                   and not r.get("host_s7_clone_trust_changed")}
    gates["G4"] = {"pass": all(host_unchanged(b, block=True) for b in blocks if b.get("outcomes"))
                   and all(host_unchanged(r) for r in per_trial if r["trial_id"] not in rebaselined) and not clone_trust,
                   "clone_trust_changed_trials": clone_trust,
                   "blocks": len([b for b in blocks if b.get("outcomes")]),
                   "trials_without_host_comparison": [r["trial_id"] for r in per_trial if not r.get("host_s7")],
                   "transient_states_recorded": sum(1 for r in per_trial if r.get("host_s7_transient_before"))
                   + sum(1 for b in blocks if b.get("transient_pre")),
                   "rebaselines": [{k: r.get(k) for k in ("at", "trigger", "trial_id", "cell", "arm", "changed", "baseline_sha256")}
                                   for r in rebaselines],
                   "rebaselined_trials": sorted(rebaselined)}
    # Point 4 of the 11:43Z confirmations: the re-runs a re-baseline cost (CL7b included), checked against one Claude
    # trial plus one Codex cell, the arm's concurrency unit (else one trial per arm).
    reruns = [r for r in table if r.get("reason") == "host_change_rebaselined"]
    rerun_arms = _count([r.get("arm") for r in reruns])
    codex_cells = sorted({str(r.get("cell")) for r in reruns if r.get("client") == "codex"})
    claude_reruns = sum(1 for r in reruns if r.get("client") == "claude")
    gates["G4"]["rebaseline_cost"] = {
        "claude_trials": claude_reruns, "codex_cells": codex_cells, "trials_per_arm": rerun_arms,
        "within_confirmed_cost": (claude_reruns <= 1 and len(codex_cells) <= 1) or all(n <= 1 for n in rerun_arms.values())}
    # G7 also needs the stage-2 canaries (finding 11): the exec-rules canary refused, gh showing no identity (or the
    # read-only one) through the shell and through ctx_*.
    g0 = load_json(root / "gate0.json") if (root / "gate0.json").exists() else None
    canaries = (g0 or {}).get("canaries") or {}
    gates["G7"]["canaries"] = canaries or "missing (no gate0.json: stage 2 has not run)"
    gates["G7"]["pass"] = bool(gates["G7"]["pass"]) and bool(canaries) and all(canaries.values())
    gates["G10"] = sdk_parity(cfg, graded_by)
    gates["G10"]["gateway_entry"] = (f"best-effort, confirmed by decision 5 of {CC_V11_DECISIONS}: the gateway's call "
                                     "logs undercount clients that exit fast (right after response.completed), so a "
                                     "missing entry is a gap, never the gate")
    gaps += gates["G10"].get("gaps") or []
    # G11 and decision 8: the operator's record of the gateway's pipeline details for this run, and what the call logs
    # showed (only the forwarded effort fields are kept).
    codex_effort = [g["effort"] for _, (r, g) in graded_by.items() if r.get("client") == "codex" and g.get("effort")]
    calls_seen = sum(e.get("gateway_calls") or 0 for e in codex_effort)
    with_pipeline = sum(e.get("gateway_calls_with_pipeline") or 0 for e in codex_effort)
    gates["G11"]["gateway_pipeline_details"] = {
        "declared": (cfg.get("gateway_pipeline_details") or {}).get("declared"),
        "observed": ("on" if with_pipeline == calls_seen else "partly on") if with_pipeline else ("off" if calls_seen else "no calls"),
        "calls": calls_seen, "calls_with_pipeline": with_pipeline}
    # CC item task-ns2604-coop-20261006T144256Z: every Codex cell runs on the normal tier, set explicitly; a recorded
    # tier other than default fails G11 (runs before round 5 recorded it only in the CLI line's shape).
    tiers = {r["trial_id"]: r.get("service_tier") for r in table if r.get("launched") and r.get("client") == "codex"}
    gates["G11"]["service_tier"] = {
        "rule": "task-ns2604-coop-20261006T144256Z: service_tier=default set explicitly on every Codex cell",
        "default": sum(1 for tier in tiers.values() if tier == "default"),
        "unrecorded": sorted(tid for tid, tier in tiers.items() if tier is None),
        "other": {tid: tier for tid, tier in tiers.items() if tier not in (None, "default")},
        "stage1_check": cfg.get("service_tier_check"),
        # codex-cli 0.160.0 omits service_tier when it is "default", so OmniRoute's own Codex tier settings decide the
        # outbound tier; the forwarded tier (pipeline details) is the effective one.
        "forwarded": {r["trial_id"]: (g.get("effort") or {}).get("gateway_forwarded_service_tier")
                      for r, g in graded_by.values() if r.get("client") == "codex" and g
                      and (g.get("effort") or {}).get("gateway_forwarded_service_tier")}}
    fast = {tid: tiers_ for tid, tiers_ in gates["G11"]["service_tier"]["forwarded"].items() if "priority" in tiers_}
    gates["G11"]["service_tier"]["forwarded_priority"] = fast
    # GPT read of a513616d, P2: fail closed. Each Codex trial's tier evidence, with the affected call ids.
    evidence = {r["trial_id"]: r.get("tier_evidence") for r in table if r.get("launched") and r.get("client") == "codex"}
    gates["G11"]["service_tier"]["evidence"] = {
        "rule": f"launch tier default and every call's forwarded tier in {list(NORMAL_FORWARDED_TIERS)}",
        "failing": {tid: {k: v for k, v in (e or {}).items() if k != "ok"} for tid, e in evidence.items()
                    if not (e or {}).get("ok")}}
    # GPT read of 80be1483, P2-1: every required call collected, with the lost ones listed by id.
    gates["G11"]["call_coverage"] = {r["trial_id"]: r.get("call_coverage") for r in table
                                     if r.get("launched") and r.get("client") == "codex"
                                     and not (r.get("call_coverage") or {}).get("ok")}
    if gates["G11"]["service_tier"]["other"] or fast or gates["G11"]["service_tier"]["evidence"]["failing"] \
            or gates["G11"]["call_coverage"]:
        gates["G11"]["pass"] = False
    # Round 6b (2): the calibration cell must have passed (gate0.json); otherwise G11 stays failed.
    calibration = (((load_json(root / "gate0.json") if (root / "gate0.json").exists() else {}).get("checks") or {})
                   .get(CALIBRATION_KEY) or {}).get("call_id_calibration") or {"pass": False, "cause": "no calibration record"}
    gates["G11"]["call_id_calibration"] = calibration
    if not calibration.get("pass"):
        gates["G11"]["pass"] = False
    # G13, structural (CC item task-ns2604-coop-20261006T132948Z): every launched trial's receipt shows each listed
    # answer source hidden from its mount namespace for its whole lifetime, and stage 1's wrapper-only self-test
    # passed. The command classifier (decision 3's tags and answer-source reads) is reported as a diagnostic only.
    selftest = load_json(root / isolation.SELFTEST_FILE) if (root / isolation.SELFTEST_FILE).exists() else None
    isolation_failures = {r["trial_id"]: r["isolation"]["failures"] for r in table
                          if r.get("launched") and r.get("isolation") and not r["isolation"]["ok"]}
    gates["G13"].update({"rule": f"structural ({isolation.ISOLATION_DECISION}): every listed answer source (run roots, "
                                 "suite cards, the fixture cache's oracles.json, other trials' fixtures and transcripts, "
                                 "the shared sessions alias) was hidden from the trial's mount namespace for its whole "
                                 "lifetime; the command classifier is a diagnostic tag that never invalidates a trial",
                         "isolation": {"configured": cfg.get("isolation"),
                                       "selftest": {"pass": (selftest or {}).get("pass"), "probes": (selftest or {}).get("probes"),
                                                    "version": (selftest or {}).get("version")} if selftest else None,
                                       "trials_failing": isolation_failures},
                         "classifier_diagnostic": {
                             "tagged_trials": sorted(r["trial_id"] for r in table if r.get("tagged")),
                             "tag_categories": _count([c for r in table for c in r.get("tagged") or []]),
                             "answer_source_trials": sorted(r["trial_id"] for r in table if r.get("answer_source_reads"))},
                         # Round 5 (CC item task-ns2604-coop-20261006T143846Z, (a)): ai-memory's per-trial scope (a page
                         # of another trial's scope invalidates the trial and fails G13), the host services a trial
                         # used (tags), and the gateway's cache reading at stage 1.
                         "ai_memory": {
                             "rule": "workspace organic-e2e, project <trial_id>, from the marker bound above the fixture",
                             "calls": sum((r.get("ai_memory") or {}).get("calls") or 0 for r in table),
                             "global_query_trials": sorted(r["trial_id"] for r in table
                                                           if (r.get("ai_memory") or {}).get("global_queries")),
                             "implicit_scope_calls": sum(len((r.get("ai_memory") or {}).get("implicit_scope_calls") or [])
                                                         for r in table),
                             "foreign_scope_trials": {r["trial_id"]: r["ai_memory"]["foreign_scope_pages"] for r in table
                                                      if (r.get("ai_memory") or {}).get("foreign_scope_pages")},
                             "unverifiable_scope_trials": {r["trial_id"]: r["ai_memory"]["unverifiable_scope_pages"]
                                                           for r in table
                                                           if (r.get("ai_memory") or {}).get("unverifiable_scope_pages")}},
                         "host_service_tags": _count([tag for r in table for tag in r.get("host_service_tags") or {}]),
                         "gateway_cache_stage1": {k: (cfg.get("gateway_cache") or {}).get(k)
                                                  for k in ("verdict", "cache_config", "semantic_cache", "idempotency")},
                         # Round 6 (CC item task-ns2604-coop-20261006T155742Z, section 2): (A) the trials the cache rule
                         # voided; (B) the forwards' requests, and the ones the filters refused (diagnostic: a refused
                         # request changes nothing, and the trial stays valid).
                         "gateway_cache_voided": {r["trial_id"]: (r["isolation"].get("gateway_cache_window") or {}).get("reasons")
                                                  for r in table if r.get("isolation")
                                                  and (r["isolation"].get("gateway_cache_window") or {}).get("void")},
                         "network": {"requests": sum((r.get("isolation") or {}).get("network_requests") or 0 for r in table),
                                     "denied_trials": {r["trial_id"]: r["isolation"]["network_denied"] for r in table
                                                       if (r.get("isolation") or {}).get("network_denied")},
                                     "selftest_probes": ((selftest or {}).get("network") or {}).get("expect")},
                         "gateway_logs_stage1": cfg.get("gateway_logs")})
    gates["G13"]["network_closure"] = closure_evidence(selftest)
    if gates["G13"].get("pass") is not None:
        gates["G13"]["pass"] = bool(gates["G13"]["pass"] and cfg.get("isolation") and (selftest or {}).get("pass")
                                    and gates["G13"]["network_closure"]["pass"])
    g12 = cfg.get("oracles_reproduce") or {}
    gates["G12"] = {"pass": g12.get("pass"), "differing": g12.get("differing"), "tests_run": g12.get("tests_run")}
    gates["G15"] = {"observed": observed, "gaps": [k for k, v in observed.items() if not v], "negatives": negatives}
    exposure = [{"trial_id": r["trial_id"], "cell": r.get("cell"), **r["target_exposure"]}
                for r in table if r.get("target_exposure")]
    # Point 5 of the 11:43Z confirmations: the expected usage each Claude trial was started with, the run's
    # recalibration (if the pilot or the operator wrote one) and what the p90 over this run's trials is now.
    meter = {"default_or_run_value": (cfg.get("claude_meter") or {}).get("expected_usage"),
             "calibration": load_json(root / METER_CALIBRATION) if (root / METER_CALIBRATION).exists() else None,
             "values_used": sorted({json.dumps((r.get("claude") or {}).get("meter_expected_usage"), sort_keys=True)
                                    for r in table if r.get("claude")}),
             "p90_now": {k: v for k, v in meter_calibration(root).items() if k != "deltas"}}
    return {"graded_at": utc_now(), "run_id": cfg["run_id"], "grader_sha256": sha256_file(Path(__file__)),
            "common_sha256": sha256_file(HERE / "common.py"), "cc_decisions": CC_V11_DECISIONS, "trials": table,
            "oir": oir, "gates": gates, "gaps": gaps,
            "carried_forward": carried_forward, "registry_status": (cfg.get("registry") or {}).get("status"),
            "claude_completion": cfg.get("claude_completion"), "claude_meter": cfg.get("claude_meter"),
            "meter_expected_usage": meter, "cli_exposure_strata": _count([e.get("stratum") for e in exposure]),
            "completion_times": [{k: r.get(k) for k in ("trial_id", "client", "cell", "reason", "final_turn_end_s",
                                                        "time_to_result_s", "turn_times_source")}
                                 for r in table if r.get("launched")],
            # The 12:30Z ruling's check: every launched Codex trial carries both times (one schema across arms).
            "timing_record": {"codex_trials": sum(1 for r in table if r.get("launched") and r.get("client") == "codex"),
                              "codex_missing": sorted(r["trial_id"] for r in table if r.get("launched")
                                                      and r.get("client") == "codex" and (r.get("final_turn_end_s") is None
                                                                                          or r.get("time_to_result_s") is None))},
            # Finding 3 of the GPT micro-check of 87f9f1d7: the deadline cases by evidence (reached T, no result before T),
            # whatever ended the session, so the timeout's SIGKILL is listed too.
            "no_result_trials": [{"trial_id": r["trial_id"], "cell": r.get("cell"), "reason": r.get("reason"),
                                  "diagnosis": r.get("no_result_diagnosis")}
                                 for r in table if r.get("client") == "claude" and r.get("launched")
                                 and deadline_without_result(*decision_times(r), r.get("t_seconds"))],
            "held_cells": sorted(p.name for p in root.glob("HOLD.*")),
            "rate_limited_trials": sorted(r["trial_id"] for r in table if r.get("rate_limited")),
            "cli_exposure": exposure,
            "notes": ["Outcome grading (D then R oracles, 0-4) is the coordinator's blind GPT step; none is computed here.",
                      "Labels (R4) are pending, so OIR uses each task's own item as the target; no verdict is derived.",
                      "fixture-directed uses the reviewed routing registry when run.json has one, else the provisional list.",
                      f"The command center's v1.1 decisions ({CC_V11_DECISIONS}) are recorded in AMENDMENT-v1.1-20261006.md "
                      "beside the protocol: completion at the result event with T = 1,800 s (1), CLI exposure by native "
                      "surface (2), tagged host reads with gold-only invalidation (3), watcher-only chrome-devtools (4), "
                      "best-effort G10 gateway entry (5), the headroom meter rule (6), one in-run re-baseline (7) and "
                      "effort-only pipeline receipts (8).",
                      "Confirmed at 11:43Z (task-ns2604-coop-20261006T114319Z): the hold for every Claude cell, gh as "
                      "PATH-only with a vendor-skill surface stratum, the answer-source list with grader outputs and "
                      "earlier graded receipts added, the re-baseline cost of one Claude trial plus one Codex cell, and "
                      "0.15 of a window per trial until the first pilot block's p90 recalibrates it."]}


def host_unchanged(row: dict, block: bool = False) -> bool:
    """S7 for one trial (its exit row) or one block: no persistent change against the stage-1 baseline and no new trust
    entry (a transient another session left mid-write is recorded, not counted). Rows written before that judgement
    existed fall back to their before-and-after comparison."""
    key = "persistent_change" if block else "host_s7_persistent_change"
    if row.get(key) is not None:
        return row[key] is False
    compare = row.get("post_vs_pre") if block else row.get("host_s7")
    return bool(compare) and compare.get("equal") is True and not any((compare.get("new_trust") or {}).values())


def sdk_parity(cfg: dict, graded_by: dict) -> dict:
    """G10 (finding 11). Claude: each CL6 init lists the same MCP servers, skills and agents as the CL2 init. Codex: each
    CL7 and CL7b trial's rollout shows the omniroute provider, the clone's MCP servers and the session's skills catalog
    equal CL3's, a gateway call-log entry exists, and a CL7b trial has exactly one main rollout. The session-level MCP
    list is not in a Codex rollout or in Loki (the collector keeps no conversation_starts mcp_servers attribute), so
    the clone's configured list stands in for it."""
    by_cell = {}
    for tid, (record, graded) in graded_by.items():
        if record.get("carried_forward"):
            continue   # finding 5: a carried attempt is re-run under its own trial id; the parity check reads the re-run
        by_cell.setdefault(record.get("cell"), []).append((record, graded))
    out, checks = {}, []

    def names(values):
        return sorted({(v.get("name") if isinstance(v, dict) else str(v)) for v in values or []})

    ref_claude = next((g["init"] for r, g in by_cell.get("claude-native", []) if g.get("init", {}).get("mcp_servers")), None)
    for record, graded in by_cell.get("claude-sdk", []):
        init = graded.get("init") or {}
        row = {"trial_id": record["trial_id"], "reference": bool(ref_claude)}
        if ref_claude:
            row.update({k: names(init.get(k)) == names(ref_claude.get(k)) for k in ("mcp_servers", "skills", "agents")})
        row["pass"] = bool(ref_claude) and all(row.get(k) for k in ("mcp_servers", "skills", "agents"))
        checks.append(row)
    ref_codex = next(((r, g) for r, g in by_cell.get("codex-native", []) if g.get("skills_body_sha256")), (None, None))
    gaps = []
    for cell in ("codex-sdk", "codex-app-server"):
        for record, graded in by_cell.get(cell, []):
            ref_record, ref_graded = ref_codex
            row = {"trial_id": record["trial_id"], "cell": cell, "provider_omniroute": graded.get("model_provider") == "omniroute",
                   "skills_equal_cl3": bool(ref_graded) and graded.get("skills_body_sha256") == ref_graded.get("skills_body_sha256"),
                   "clone_mcp_equal_cl3": bool(ref_record) and (record.get("codex") or {}).get("clone_mcp_servers")
                   == (ref_record.get("codex") or {}).get("clone_mcp_servers")}
            if cell == "codex-app-server":
                row["one_main_rollout"] = graded.get("main_rollouts") == 1
            row["pass"] = all(v for k, v in row.items() if k not in ("trial_id", "cell"))
            # The route rests on client-side telemetry (the rollout's session_meta provider). The gateway call log is
            # best-effort under the command center's telemetry caveat (item task-ns2604-coop-20261005T200956Z), which
            # decision 5 of item task-ns2604-coop-20261006T105529Z confirmed: the call logs undercount clients that exit
            # fast, right after response.completed, and can leave their rows unfinished (smoke-20261006c CL7b: three
            # /v1/responses rows with status 0 whose detail returns 404, so no thread join). A joined entry is recorded;
            # its absence is a gap, never the gate.
            row["gateway_entry_best_effort"] = graded["effort"]["gateway_calls"] > 0
            if not row["gateway_entry_best_effort"]:
                gaps.append({"gate": "G10", "trial_id": record["trial_id"], "gap": "no gateway call-log entry joined to the "
                             "thread (best-effort source under CC item 200956Z's telemetry caveat); the route rests on the "
                             "rollout's omniroute provider"})
            checks.append(row)
    # G10 holds only when every SDK cell was exercised and passed: a cell with no graded trial is reported as not
    # exercised, never as a pass (a failed check still fails the gate).
    cells = {"CL6 claude-sdk": "claude-sdk", "CL7 codex-sdk": "codex-sdk", "CL7b codex-app-server": "codex-app-server"}
    not_exercised = [label for label, cell in cells.items() if not by_cell.get(cell)]
    failed = [c["trial_id"] for c in checks if not c["pass"]]
    if not checks:
        return {"pass": None, "n": 0, "not_exercised": not_exercised, "note": "no CL6, CL7 or CL7b trial in this run",
                "gaps": gaps}
    return {"pass": False if failed else (None if not_exercised else True), "n": len(checks), "checks": checks,
            "failed": failed, "not_exercised": not_exercised, "gaps": gaps}


# ---------------------------------------------------------------------------------------------------------------------
# Stage 0 replay over the v1 captures (no sessions).

STAGE0_LOKI = RUNS_ROOT / "stage0" / "loki-v1-captures.json"


def _v1_outs(run: str) -> list[Path]:
    return sorted((V1_ROOT / ("smoke" if run == "smoke1" else "pilot") / f"run-{run}").glob("*.out"))


def _v1_claude_captures():
    """(path, parsed events, source) for every v1 Claude capture of pilot1, pilot1env and smoke1. The v1 runner's
    fixture was <fixtures>/runs/<run>/<tag without the run prefix>, so an empty stdout capture is read from the
    transcript in that path's project directory."""
    from collect import claude_slug
    fixtures = HOME / ".cache/ns2604-organic-fixtures/runs"
    for run in ("pilot1", "pilot1env", "smoke1"):
        for path in _v1_outs(run):
            if "-claude-" not in path.name:
                continue
            if path.stat().st_size:
                yield path, parse_claude_events(parse_stream_text(path.read_text(encoding="utf-8", errors="replace"))), "stdout"
                continue
            work = fixtures / run / path.stem[len(run) + 1:]
            project = HOME / ".claude/projects" / claude_slug(str(work))
            transcripts = sorted(project.glob("*.jsonl")) if project.exists() else []
            if transcripts:
                yield path, parse_transcript(transcripts[0]), f"transcript ({len(transcripts)} in project)"


def _rollout_for_thread(thread: str) -> Path | None:
    hits = sorted((HOME / ".codex/sessions").glob(f"*/*/*/rollout-*{thread}.jsonl"))
    return hits[0] if hits else None


def _stage0_window() -> tuple[int, int]:
    """The v1 captures' own time window (finding 6): every capture file's mtime, 3 h before the first (a session starts
    before its output is written) to 1 h after the last."""
    mtimes = [p.stat().st_mtime for run in ("smoke1", "pilot1", "pilot1env") for p in _v1_outs(run)]
    if not mtimes:
        now = time.time()
        return int((now - 30 * 3600) * 1e9), int(now * 1e9)
    return int((min(mtimes) - 3 * 3600) * 1e9), int((max(mtimes) + 3600) * 1e9)


def _loki_rows(query: str, sources: dict) -> list[dict]:
    """Stage-0 Loki rows from the saved copy when it holds the query, else from Loki over the captures' fixed window,
    saved into the copy, so the replay keeps working after Loki's retention or any rolling window has moved on."""
    snap = load_json(STAGE0_LOKI) if STAGE0_LOKI.exists() else {"queries": {}, "window_ns": None, "saved_at": None}
    if query in snap["queries"]:
        sources[query[:80]] = "saved copy"
        return snap["queries"][query]
    from collect import loki
    start, end = _stage0_window()
    rows = loki(query, start, end)
    snap["queries"][query] = rows
    snap["window_ns"] = [start, end]
    snap["saved_at"] = utc_now()
    write_json(STAGE0_LOKI, snap, 0o600)
    sources[query[:80]] = "Loki (fixed capture window), saved"
    return rows


def replay(out_path: Path | None) -> dict:
    report = {"at": utc_now(), "class": "stage-0 replay of v1-runner captures (no sessions)", "loki_sources": {}}
    sources = report["loki_sources"]
    # (a) and (b): smoke1-s01-codex-native.
    smoke_out = V1_ROOT / "smoke/run-smoke1/smoke1-s01-codex-native.out"
    stream = parse_codex_stream(parse_stream_text(smoke_out.read_text(encoding="utf-8", errors="replace")))
    clone_v1 = HOME / ".cache/ns2604-organic-fixtures/codex-home-native"
    catalog = skill_catalog("codex", clone_v1)
    commands = [it for it in stream["items"] if it.get("type") == "command_execution"]
    started_cmds = sum(1 for e in parse_stream_text(smoke_out.read_text()) if isinstance(e, dict) and e.get("type") == "item.started"
                       and (e.get("item") or {}).get("type") == "command_execution")
    uses_a = [u for it in commands for u in codex_uses(it, catalog, None)]
    report["a"] = {"command_execution_completed": len(commands), "command_execution_started_events": started_cmds,
                   "unwrapped": [unwrap_command(c.get("command"))[:160].replace(str(HOME), "~") for c in commands],
                   "skill_consultations": [u.get("skill") for u in uses_a if u["kind"] == "skill-consultation"],
                   "pass": len(commands) == 1 and any(u.get("skill") == "context-mode" for u in uses_a)}
    rollout_path = _rollout_for_thread(stream["thread_id"])
    rollout = parse_rollout(rollout_path) if rollout_path else {"items": {}, "wrappers": []}
    rollout_mcp = [it for it in rollout["items"].values() if it.get("type") == "McpToolCall"]
    by_tool = {}
    for it in rollout_mcp:
        by_tool[it.get("tool")] = by_tool.get(it.get("tool"), 0) + 1
    stream_mcp = [it for it in stream["items"] if it.get("type") == "mcp_tool_call"]
    try:
        rows = _loki_rows('{service_name=~"codex.*"} | env="smoke1-s01-codex-native" | event_name="codex.tool_result"', sources)
    except Exception as error:  # noqa: BLE001
        rows = []
        report["loki_error"] = type(error).__name__
    wrappers = [r for r in rows if r.get("tool_name") == "exec" and r.get("tool_namespace") == "functions"]
    loki_mcp = {r.get("call_id") for r in rows if r.get("mcp_server_name")}
    report["b"] = {"stream_mcp_completed": len(stream_mcp), "rollout_mcp_by_tool": by_tool, "rollout_code_mode_wrappers": len(rollout["wrappers"]),
                   "wrappers_counted": 0, "loki_functions_exec_excluded": len(wrappers),
                   "loki_mcp_ids_equal_rollout_ids": loki_mcp == {it.get("id") for it in rollout_mcp},
                   "pass": len(stream_mcp) == 10 and by_tool == {"ctx_execute": 6, "ctx_batch_execute": 4}
                           and len(rollout["wrappers"]) == 11 and len(wrappers) == 11 and loki_mcp == {it.get("id") for it in rollout_mcp}}
    # (c) ctx-nested CLI: rg in ctx_batch_execute commands[] and in a ctx_execute JavaScript spawnSync.
    batch_rg = [u for it in stream_mcp for u in codex_uses(it, catalog, None) if u["kind"] == "cli" and u.get("via") == "ctx"]
    found_js = None
    for path in sorted((V1_ROOT).glob("**/*.out")):
        text = path.read_text(encoding="utf-8", errors="replace")
        if "spawnSync" in text and "ctx_execute" in text:
            for event in parse_stream_text(text):
                items = []
                if isinstance(event, dict) and event.get("type") == "item.completed":
                    items = [event.get("item") or {}]
                for it in items:
                    if it.get("type") == "mcp_tool_call" and it.get("tool") == "ctx_execute":
                        args = _json_arg(it.get("arguments"))
                        if "spawnSync" in (args.get("code") or ""):
                            nested = ctx_nested("ctx_execute", args)
                            if any(os.path.basename(n["text"].split()[0]) == "rg" for n in nested if n["kind"] == "program" and n["text"].split()):
                                found_js = {"capture": path.name, "nested": [n for n in nested if n["kind"] == "program"][:3]}
            if found_js:
                break
    synthetic = None
    if not found_js:
        args = {"language": "javascript", "code": "const { spawnSync } = require('child_process');\n"
                                                  "const r = spawnSync('rg', ['-n', 'parse_iso', 'tools']);\nconsole.log(r.stdout.toString());"}
        nested = ctx_nested("ctx_execute", args)
        synthetic = {"label": "synthetic fixture (no captured ctx_execute JavaScript spawnSync of rg exists)", "nested": nested,
                     "detected_rg": any(n["kind"] == "program" and n["text"] == "rg" for n in nested)}
    batch_rg_count = 0
    for it in stream_mcp:
        if it.get("tool") != "ctx_batch_execute":
            continue
        for nested in ctx_nested("ctx_batch_execute", _json_arg(it.get("arguments"))):
            if nested["kind"] == "shell":
                batch_rg_count += sum(1 for tokens in segments(nested["text"]) if os.path.basename(tokens[0]) == "rg")
    report["c"] = {"batch_commands_rg": batch_rg_count, "batch_cli_item_uses": len(batch_rg),
                   "js_spawnSync_capture": found_js, "js_spawnSync_synthetic": synthetic}
    report["c"]["pass"] = report["c"]["batch_commands_rg"] > 0 and bool(found_js or (synthetic and synthetic["detected_rg"]))
    report["c"]["note"] = "rg is not a CLI item; S4 detection is shown on the executed-program parse, which is item-independent"
    # (d) Claude pilot1 and pilot1env: MCP calls by server through the stream names and Loki mcp_server_name, joined on
    # session.id. A v1 capture whose --output-format json stdout is empty (a timeout loses it, §12.1) is read from its
    # transcript, located through the v1 fixture path's project slug.
    d_rows = []
    for path, parsed, source in _v1_claude_captures():
        session = parsed["session_ids"][0] if parsed["session_ids"] else None
        stream_mcp_c = {c["id"]: c["name"].split("__")[1] for c in parsed["calls"] if (c.get("name") or "").startswith("mcp__")}
        try:
            rows = _loki_rows(f'{{service_name="claude-code"}} | session_id="{session}" | event_name="tool_result"', sources) if session else []
        except Exception:  # noqa: BLE001
            rows = []
        loki_mcp_c = {r.get("tool_use_id"): r.get("mcp_server_name") for r in rows if r.get("mcp_server_name")}
        tag = path.stem
        d_rows.append({"capture": tag, "source": source, "stream_mcp": len(stream_mcp_c), "loki_mcp": len(loki_mcp_c),
                       "servers": sorted(set(stream_mcp_c.values())), "agree": stream_mcp_c == loki_mcp_c,
                       "loki_task_tag_matches": bool(rows) and all(r.get("ecosystem_task_id") == tag for r in rows)})
    report["d"] = {"captures": d_rows, "pass": bool(d_rows) and all(r["agree"] for r in d_rows)}
    # (e) marker scan.
    e = {}
    env_tr = native_tr = None
    for path, parsed, source in _v1_claude_captures():
        if not parsed["session_ids"]:
            continue
        hits = sorted((HOME / ".claude/projects").glob(f"*/{parsed['session_ids'][0]}.jsonl"))
        if not hits:
            continue
        transcript = parse_transcript(hits[0])
        markers = marker_hits(claude_instruction_texts(transcript))
        if "-claude-env" in path.name and env_tr is None:
            env_tr = {"capture": path.stem, "markers": markers}
        if "-claude-native" in path.name and native_tr is None:
            native_tr = {"capture": path.stem, "markers": markers}
    e["claude_env"], e["claude_native"] = env_tr, native_tr
    home_rollout = clone_rollout = None
    for path in _v1_outs("pilot1env"):
        if "-codex-env" in path.name:
            thread = parse_codex_stream(parse_stream_text(path.read_text(encoding="utf-8", errors="replace")))["thread_id"]
            rp = _rollout_for_thread(thread) if thread else None
            if rp:
                home_rollout = {"capture": path.stem, "rollout": parse_rollout(rp)}
                break
    for path in _v1_outs("pilot1"):
        if "serena" in path.name and "-codex-native" in path.name:
            thread = parse_codex_stream(parse_stream_text(path.read_text(encoding="utf-8", errors="replace")))["thread_id"]
            rp = _rollout_for_thread(thread) if thread else None
            if rp:
                clone_rollout = {"capture": path.stem, "rollout": parse_rollout(rp)}
                break
    e["codex_home"] = {"capture": home_rollout["capture"], "markers": marker_hits(codex_instruction_texts(home_rollout["rollout"]))} if home_rollout else None
    e["codex_clone"] = {"capture": clone_rollout["capture"], "markers": marker_hits(codex_instruction_texts(clone_rollout["rollout"]))} if clone_rollout else None
    e["pass"] = bool(env_tr and env_tr["markers"] and native_tr is not None and not native_tr["markers"]
                     and e["codex_home"] and e["codex_home"]["markers"].get("native-agent-stack:codex-user-instructions")
                     and e["codex_clone"] is not None and not e["codex_clone"]["markers"])
    report["e"] = e
    # (f) store-directed on the real-home rollout's ai-memory pending-handoff block.
    f = {"capture": home_rollout["capture"] if home_rollout else None}
    if home_rollout:
        blocks = [m for m in home_rollout["rollout"]["messages"] if "pending handoff" in (m.get("text") or "").lower()]
        f["pending_handoff_blocks"] = len(blocks)
        f["block_kinds"] = [m.get("kinds") for m in blocks][:3]
        from suite import ALIASES
        named = sorted({name for m in blocks for name in ("ai-memory", "serena", "jcodemunch", "qmd", "context-mode", "headroom",
                                                           "socraticode", "semble", "codebase-memory")
                        if names_item(m["text"], [name] + list(ALIASES.get(name, ())))})
        f["items_named_in_block"] = named
        trial = {"uses": []}
        rows_items = list(home_rollout["rollout"]["items"].values())
        for index, item in enumerate(rows_items, 1):
            for use in codex_uses(item, skill_catalog("codex"), None):
                use.update({"order": index, "actor": "main"})
                trial["uses"].append(use)
        ctx = {"prompt": "", "arm": "env", "lexicon": {}, "tools_by_server": {}, "harness_texts": [], "harness_agents": {},
               "store_blocks": [{"order": 0, "actor": "main", "text": m["text"]} for m in blocks], "hook_blocks": [],
               "registry_results": [], "fixture_results": [], "skill_bodies": [], "agent_returns": [], "harness_reads": [],
               "process_reads": [], "spawns": {}, "actor_types": {}, "prompt_paths_in_call": lambda use: False}
        tag_uses(trial, ctx)
        f["uses"] = [{"item": u["item"], "tag": u["tag"]} for u in trial["uses"] if u.get("item")]
        f["store_directed"] = sum(1 for u in trial["uses"] if u.get("tag") == "store-directed")
        probe = {"uses": [{"item": named[0] if named else "ai-memory", "kind": "mcp", "level": "completion", "order": 1, "actor": "main"}]}
        tag_uses(probe, ctx)
        f["tagger_on_block_named_item"] = probe["uses"][0]["tag"]
        f["pass"] = bool(blocks) and probe["uses"][0]["tag"] == "store-directed"
    else:
        f["pass"] = False
    report["f"] = f
    report["G1"] = all(report[k].get("pass") for k in ("a", "b", "c", "d", "e", "f"))
    if out_path:
        write_json(out_path, report, 0o600)
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_trials = sub.add_parser("trials")
    p_trials.add_argument("--run-root", required=True)
    p_gate0 = sub.add_parser("gate0")
    p_gate0.add_argument("--run-root", required=True)
    p_replay = sub.add_parser("replay")
    p_replay.add_argument("--out", default=None)
    p_meter = sub.add_parser("meter-calibration", help="the run's measured p90 usage per Claude trial (point 5 of the "
                             "11:43Z confirmations); --write records it as the run's expected usage")
    p_meter.add_argument("--run-root", required=True)
    p_meter.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    if args.cmd == "meter-calibration":
        # The operator step beside pilot.py's automatic one: print the p90; with --write, record it for later starts.
        root = Path(args.run_root)
        calibration = meter_calibration(root)
        if args.write and calibration["expected_usage"]:
            write_json(root / METER_CALIBRATION, {**calibration, "at": utc_now(), "source": "operator: grade.py "
                                                  "meter-calibration --write", "previous": run_expected_usage(
                                                      load_json(root / "run.json"), root),
                                                  "decision": f"{CC_V11_DECISIONS} #6; confirmed by "
                                                              "task-ns2604-coop-20261006T114319Z point 5"}, 0o600)
        print(json.dumps({"expected_usage": calibration["expected_usage"], "trials": calibration["trials"],
                          "written": bool(args.write and calibration["expected_usage"])}))
        return 0
    if args.cmd == "replay":
        report = replay(Path(args.out) if args.out else None)
        print(json.dumps({k: (v.get("pass") if isinstance(v, dict) else v) for k, v in report.items() if k in ("a", "b", "c", "d", "e", "f", "G1")}))
        return 0
    root = Path(args.run_root)
    if args.cmd == "gate0":
        report = gate0(root)
        print(json.dumps({"gate0": report["pass"], "checks": {k: v["pass"] for k, v in report["checks"].items()},
                          "missing": report["missing"]}))
        return 0
    result = grade_run(root)
    path = root / "grades" / f"grade-{utc_now().replace(':', '')}.json"
    write_json(path, result, 0o600)
    print(json.dumps({"grade": str(path), "trials": len(result["trials"]),
                      "gates": {k: v.get("pass") for k, v in result["gates"].items() if isinstance(v, dict) and "pass" in v},
                      "G15_gaps": result["gates"]["G15"]["gaps"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
