#!/usr/bin/env python3
"""Run one frozen GPT-6 family arm over the frozen 8-K batches with `codex exec`.

Standard library only (Python 3.11 or newer). An arm is one Codex model and one reasoning effort. Every arm sends
the same batches of the same filings in the same order: the frozen li26 acquisition, verified with li26's own
load_inputs, cut greedily in accession order into batches of at most 15 filings whose prompt stays under
110,000 bytes. The layout's SHA-256 is frozen in plan.json. Each batch is one call:

  codex exec --ignore-user-config --skip-git-repo-check -s read-only -m <model> \
    -c model_reasoning_effort="<effort>" <ISOLATION overrides> --output-schema <schema> -o <reply> --json "<prompt>"

with stdin /dev/null and no --search. The overrides switch off, for codex-cli 0.157.1, everything the committed
command still offered the model: web search, the shell, sub-agents, the sleep tool, image viewing, goals, hooks,
plugins and apps; and Codex's unbounded reconnect, so an outage fails a call instead of hanging it
(isolation-probe/results.json, a loopback probe). Each call gets its own CODEX_HOME inside its attempt directory,
holding only a link to the native auth.json (never a copy), so no global AGENTS.md, skill, hook or config of the
host reaches it and its session files stay private. Its HOME, TMPDIR and working directory are an empty scratch
directory outside the state tree and every repository, removed after the call. Its environment is an allowlist:
no API key, no RUST_LOG and none of the caller's other variables.

At most three calls run at once. Each call first takes one of the host's Codex slots, an fcntl.flock on
<lock dir>/slot-1 to slot-3. These are the locks the landscape-sweep runner takes, so this arm and every other Codex
job on the host together stay within the three-slot pool. codex inherits the slot lock and the arm's run lock, so a
killed runner never frees them while its codex still runs. Calls start through a state-wide launch gate, which also
guards the stop notes, so no call starts once a note is published.

Outcomes. ok. failed: the model ran but the call is unusable (a timeout, a non-zero exit or turn.failed after a
completed turn, a missing or invalid reply, or any tool call in Codex's session record); its batch runs once more,
and a batch that fails twice is final. limit: Codex's own `error` or `turn.failed` event saying "hit your usage
limit" (model content and stderr never count); the run publishes the LIMIT note as soon as the event appears, before
the call ends, starts no further call and exits 3. unavailable: no completed turn without a limit event (network,
sign-in, rate limit, server error, launch failure), or a completed turn whose session record is missing or holds an
item type this plan does not know; the run publishes the UNAVAILABLE note and exits 4. interrupted (SIGINT or SIGTERM, exit 5) and abandoned (a runner died
before recording the call). limit, unavailable, interrupted and abandoned calls never use a batch's retry; their
batch runs again in a later run. A run whose arm has a failed batch and nothing pending exits 6.

Everything a run writes stays in the private state directory, with 0700 directories and 0600 files: Codex
events, stderr, replies, session files and per-call records. Nothing is written to the repository. analyze.py
reads it.
"""
from __future__ import annotations

import argparse
from collections import deque
import contextlib
import errno
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import threading
import time

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
PLAN = HERE / "plan.json"
PROMPT = HERE / "prompt.txt"
SCHEMA = HERE / "response.schema.json"
LI26 = REPO / "blueprints/convergence-practice/local-inference-latest-20260926"
DEFAULT_STATE_DIR = Path.home() / ".local/state/native-agent-stack/gpt6-family-tiering-20260926"
COUNT_MARKER, FILINGS_MARKER = "@@FILING_COUNT@@", "@@FILINGS@@"
OPEN_TAG, CLOSE_TAG = "<<<FILING", "<<<END FILING"
ARMS = (("A0", "gpt-6-astra", "max"), ("A1", "gpt-6-astra", "medium"), ("S0", "gpt-6-sol", "max"),
        ("S1", "gpt-6-sol", "medium"), ("L0", "gpt-6-luna", "max"), ("L1", "gpt-6-luna", "medium"))
CODEX_VERSION = "codex-cli 0.157.1"
# Overrides that remove every tool the committed command still offered, measured on codex-cli 0.157.1 by
# isolation-probe/probe.py: agents.enabled=false removes the sub-agent (collaboration) tools, which the model catalog
# turns on whatever features.multi_agent says; web_search="disabled" the web search; shell_tool and unified_exec the
# shell (code mode's exec_command); view_image, goals and sleep_tool the remaining nested tools; hooks, plugins and
# apps anything a system layer or plugin sync could add; unbounded_connection_retries=false makes an outage fail the
# call instead of "Reconnecting... waiting for network" until the timeout. The file credential store keeps any
# token refresh in the native auth.json, written in place through the per-call link.
ISOLATION = ("-c", "agents.enabled=false", "-c", 'web_search="disabled"', "-c", "features.shell_tool=false",
             "-c", "features.unified_exec=false", "-c", "features.view_image=false", "-c", "features.goals=false",
             "-c", "features.sleep_tool=false", "-c", "features.hooks=false", "-c", "features.plugins=false",
             "-c", "features.apps=false", "-c", "features.unbounded_connection_retries=false",
             "-c", 'cli_auth_credentials_store="file"')
# The frozen argv after the codex binary; <...> are filled per call. No --search, never ultra.
CODEX_ARGV = ("exec", "--ignore-user-config", "--skip-git-repo-check", "-s", "read-only", "-m", "<model>",
              "-c", 'model_reasoning_effort="<effort>"', *ISOLATION, "--output-schema", "<schema>", "-o", "<reply>",
              "--json", "<prompt>")
# The only variables a call inherits (as codex_lane.py's CHILD_ENV_ALLOWLIST), besides CODEX_HOME, HOME and TMPDIR:
# no API key (the native sign-in is used), no RUST_LOG (it could log model content to stderr).
CHILD_ENV_ALLOWLIST = ("PATH", "LANG", "LC_ALL", "LC_CTYPE", "TERM", "SSL_CERT_FILE", "SSL_CERT_DIR", "HTTPS_PROXY",
                       "HTTP_PROXY", "NO_PROXY", "ALL_PROXY", "https_proxy", "http_proxy", "no_proxy", "all_proxy")
# System configuration layers that --ignore-user-config does not skip (codex-rs/config/src/loader/mod.rs at the
# pinned tag); a run refuses to start while one exists.
SYSTEM_CONFIG_FILES = ("/etc/codex/config.toml", "/etc/codex/requirements.toml", "/etc/codex/managed_config.toml")
# Item types of a call's session record (rollout) and --json stream. Model items are expected; tool items fail the
# call (tool_use), as the model used a tool; any other type stops the arm (unexpected_item) for inspection, so a
# type this plan does not know can neither be scored nor spend every batch's retry.
MODEL_ROLLOUT_ITEMS = frozenset({"message", "reasoning"})
TOOL_ROLLOUT_ITEMS = frozenset({"function_call", "function_call_output", "custom_tool_call", "custom_tool_call_output",
                                "local_shell_call", "local_shell_call_output", "web_search_call"})
MODEL_JSON_ITEMS = frozenset({"agent_message", "reasoning", "error"})
TOOL_JSON_ITEMS = frozenset({"command_execution", "web_search", "mcp_tool_call", "file_change", "todo_list",
                             "collab_tool_call"})
SCRATCH_PREFIX = "gt26-call-"
FROZEN_BATCHING = {"max_filings": 15, "max_prompt_bytes": 110000}
FROZEN_CALLS = {"max_concurrent": 3, "slots": 3, "retries_per_batch": 1, "timeout_seconds": 3000,
                "slot_poll_seconds": 5, "kill_grace_seconds": 10}
FROZEN_RULE = {"noninferiority_margin": -0.02, "json_valid_min": 0.98}
FROZEN_BOOTSTRAP = {"resamples": 10000, "seed": 20260926, "alpha": 0.05}
LIMIT_PHRASE = re.compile(r"hit your usage limit", re.IGNORECASE)
USAGE_KEYS = ("input_tokens", "cached_input_tokens", "cache_write_input_tokens", "output_tokens",
              "reasoning_output_tokens")
CORE_USAGE_KEYS = ("input_tokens", "cached_input_tokens", "output_tokens")
MAX_REPLY_BYTES = 1024 * 1024
ATTEMPT_DIR = re.compile(r"attempt-([1-9][0-9]*)")
EXIT_DONE, EXIT_ERROR, EXIT_REFUSED, EXIT_LIMIT, EXIT_UNAVAILABLE, EXIT_INTERRUPTED, EXIT_FAILED_BATCHES = (
    0, 1, 2, 3, 4, 5, 6)
# Stop notes in the state directory, in precedence order: while one exists, no call starts in any arm.
NOTES = {"LIMIT": EXIT_LIMIT, "UNAVAILABLE": EXIT_UNAVAILABLE}
NEXT_STEPS = {
    "LIMIT": "Tell the user the shared Codex usage limit was reached. After the reset, remove this file and run the "
             "same arm again; its finished batches are kept, and the limited batch runs again without using its "
             "retry.",
    "UNAVAILABLE": "Codex ended a call without a completed turn (network, sign-in, rate limit, server error or a "
                   "launch failure), or its session record is missing or holds an item type the plan does not know "
                   "(the reason says which). Read that attempt's stderr.txt, events.jsonl and call.json, fix the "
                   "cause (an unknown item type needs a plan amendment), then remove this file and run the same arm "
                   "again; the call did not use its batch's retry.",
}

_SPEC = importlib.util.spec_from_file_location("gt26_li26_eval_arm", LI26 / "eval_arm.py")
li26 = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(li26)
path_safety = li26.path_safety


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def relative(path):
    return Path(path).resolve().relative_to(REPO).as_posix()


def load_plan(path=PLAN):
    """The checked plan and the SHA-256 of its bytes."""
    raw = Path(path).read_bytes()
    plan = json.loads(raw)
    check_plan(plan)
    return plan, sha256_bytes(raw)


def check_plan(plan):
    """The frozen arms, command, batching, call limits and rule this runner was written for."""
    if plan.get("status") != "preregistered" or plan.get("frozen_before_any_call") is not True:
        raise ValueError("preregistered frozen plan required")
    arms = tuple((arm.get("id"), arm.get("model"), arm.get("effort")) for arm in plan["arms"])
    roles = [arm.get("role") for arm in plan["arms"]]
    if arms != ARMS or roles != ["control"] + ["candidate"] * (len(ARMS) - 1):
        raise ValueError("frozen arm list changed")
    for section, frozen in ((plan["batching"], FROZEN_BATCHING), (plan["calls"], FROZEN_CALLS),
                            (plan["decision_rule"]["bootstrap"], FROZEN_BOOTSTRAP)):
        for key, value in frozen.items():
            if type(section.get(key)) is not type(value) or section[key] != value:
                raise ValueError(f"frozen value changed: {key}")
    rule = plan["decision_rule"]
    if any(rule.get(key) != value for key, value in FROZEN_RULE.items()):
        raise ValueError("frozen decision rule changed")
    codex = plan["codex"]
    if codex.get("version") != CODEX_VERSION or tuple(codex.get("argv_after_binary") or ()) != CODEX_ARGV:
        raise ValueError("frozen codex command changed")
    if type(plan["batching"].get("batches")) is not int or not 1 <= plan["batching"]["batches"] <= 999:
        raise ValueError("frozen batch count required")


def verify_frozen(plan):
    """Every frozen script, dependency, the prompt and the schema match their recorded SHA-256."""
    frozen = plan["frozen_inputs"]
    required = {relative(HERE / name) for name in ("run_arm.py", "analyze.py", "prompt.txt", "response.schema.json")}
    required |= {relative(LI26 / "eval_arm.py"), relative(LI26 / "analyze.py"), "scripts/path_safety.py"}
    if not required <= frozen.keys():
        raise ValueError("frozen inputs must list the scripts, their li26 dependencies, the prompt and the schema")
    for name, expected in frozen.items():
        path = path_safety.refuse_untrusted_symlinks(REPO / name, "frozen input symlink refused")
        if li26.digest(path) != expected:
            raise ValueError(f"frozen input changed: {name}")
    if li26.digest(PROMPT) != plan["prompt_sha256"] or li26.digest(SCHEMA) != plan["schema_sha256"]:
        raise ValueError("prompt or schema hash mismatch")


def arm_by_id(plan, arm_id):
    for arm in plan["arms"]:
        if arm["id"] == arm_id:
            return arm
    raise ValueError(f"unknown arm {arm_id}")


def prompt_template(plan):
    raw = PROMPT.read_bytes()
    if sha256_bytes(raw) != plan["prompt_sha256"]:
        raise ValueError("prompt template changed")
    template = raw.decode("utf-8")
    if (template.count(COUNT_MARKER) != 1 or template.count(FILINGS_MARKER) != 1
            or template.index(COUNT_MARKER) > template.index(FILINGS_MARKER)):
        raise ValueError("prompt template markers changed")
    return template


def load_rows(plan, acquisition):
    """The eligible filings in frozen (accession) order, verified by li26's own load_inputs."""
    acquisition = path_safety.refuse_untrusted_symlinks(Path(acquisition), "acquisition symlink refused")
    rows = li26.load_inputs(acquisition, plan["task"]["inputs_sha256"])
    if len(rows) != plan["task"]["eligible_filings"]:
        raise ValueError("eligible filing count differs from the plan")
    return rows


def filing_block(row):
    accession = row["accession"]
    return f'{OPEN_TAG} accession="{accession}">>>\n{row["input"]}\n{CLOSE_TAG} accession="{accession}">>>'


def build_prompt(template, rows):
    head, rest = template.split(COUNT_MARKER)
    middle, tail = rest.split(FILINGS_MARKER)
    return head + str(len(rows)) + middle + "\n\n".join(filing_block(row) for row in rows) + tail


def prompt_bytes(template, rows):
    return len(build_prompt(template, rows).encode("utf-8"))


def plan_batches(template, rows, max_filings, max_prompt_bytes):
    """Greedy batches in input order: a filing joins the current batch while the batch then holds at most
    `max_filings` filings and its prompt stays under `max_prompt_bytes` UTF-8 bytes; otherwise it starts the
    next batch. A filing whose prompt alone reaches the bound, or whose text holds a delimiter or a NUL character
    (which no argument can carry), is refused."""
    for row in rows:
        if OPEN_TAG in row["input"] or CLOSE_TAG in row["input"] or "\x00" in row["input"]:
            raise ValueError(f"filing {row['accession']} contains a batch delimiter or a NUL character")
    batches, current = [], []
    for row in rows:
        candidate = current + [row]
        if len(candidate) <= max_filings and prompt_bytes(template, candidate) < max_prompt_bytes:
            current = candidate
            continue
        if not current or prompt_bytes(template, [row]) >= max_prompt_bytes:
            raise ValueError(f"filing {row['accession']} alone reaches the prompt bound")
        batches.append(current)
        current = [row]
    if current:
        batches.append(current)
    return batches


def layout(batches):
    return [[row["accession"] for row in batch] for batch in batches]


def layout_sha256(batches):
    return sha256_bytes(json.dumps(layout(batches), separators=(",", ":")).encode())


def layout_summary(template, batches):
    """Public-safe aggregates of a layout: counts, sizes and its hash, never filing text."""
    sizes = [prompt_bytes(template, batch) for batch in batches]
    return {"batches": len(batches), "filings": sum(len(batch) for batch in batches),
            "layout_sha256": layout_sha256(batches),
            "filings_per_batch": {"min": min(map(len, batches)), "max": max(map(len, batches))},
            "prompt_bytes": {"min": min(sizes), "max": max(sizes), "total": sum(sizes)}}


def frozen_batches(plan, template, rows):
    batching = plan["batching"]
    batches = plan_batches(template, rows, batching["max_filings"], batching["max_prompt_bytes"])
    if len(batches) != batching["batches"] or layout_sha256(batches) != batching["layout_sha256"]:
        raise ValueError("batch layout differs from the frozen layout")
    return batches


def batch_id(index):
    return f"b{index + 1:03d}"


# --------------------------------------------------------------------------- replies, events and outcomes

def _envelope(text):
    """The reply's filing entries when it is exactly {"filings": [{"accession": str, "items": ...}, ...]}."""
    try:
        value = json.loads(text, object_pairs_hook=li26._unique_keys)
    except ValueError:
        return None
    if not isinstance(value, dict) or set(value) != {"filings"} or not isinstance(value["filings"], list):
        return None
    entries = value["filings"]
    if any(not isinstance(entry, dict) or set(entry) != {"accession", "items"}
           or not isinstance(entry["accession"], str) for entry in entries):
        return None
    return entries


def parse_reply(content, accessions):
    """(reply status, {accession: (sorted codes or None, filing status)}, unexpected entry count).

    The reply status is valid, fenced_valid (one markdown fence around a valid reply) or invalid. A filing is
    valid only when the reply is, its accession has exactly one entry and that entry's items pass li26's own
    per-filing rule (unique strings matching [1-9].[0-9]{2}); otherwise it is invalid and predicts nothing.
    """
    status, entries = "invalid", None
    if isinstance(content, str):
        text = content.strip()
        entries = _envelope(text)
        if entries is not None:
            status = "valid"
        else:
            fenced = li26.FENCE.fullmatch(text)
            if fenced:
                entries = _envelope(fenced[1].strip())
                status = "fenced_valid" if entries is not None else "invalid"
    per_filing = {accession: (None, "invalid") for accession in accessions}
    if entries is None:
        return status, per_filing, 0
    grouped, unexpected = {}, 0
    for entry in entries:
        grouped.setdefault(entry["accession"], []).append(entry["items"])
    for accession, lists in grouped.items():
        if accession not in per_filing:
            unexpected += len(lists)
        elif len(lists) == 1:
            items = li26._strict_items(json.dumps({"items": lists[0]}))
            if items is not None:
                per_filing[accession] = (items, status)
    return status, per_filing, unexpected


def reply_text(path):
    """The reply Codex wrote with -o: None when missing or empty, "" (invalid) when oversized or not UTF-8."""
    try:
        with open(path, "rb") as stream:
            raw = stream.read(MAX_REPLY_BYTES + 1)
    except FileNotFoundError:
        return None
    if not raw.strip():
        return None
    if len(raw) > MAX_REPLY_BYTES:
        return ""
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return ""


def reply_status(path, accessions):
    text = reply_text(path)
    return "missing" if text is None else parse_reply(text, accessions)[0]


def parse_event_lines(raw):
    events = []
    for line in raw.decode("utf-8", "replace").splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def read_events(path):
    """The JSON objects Codex printed with --json, one per line; other lines are ignored."""
    try:
        return parse_event_lines(Path(path).read_bytes())
    except FileNotFoundError:
        return []


class EventTail:
    """The complete new lines of a growing events file, read while its codex still runs."""

    def __init__(self, path):
        self.path, self.offset, self.partial = Path(path), 0, b""

    def read(self):
        try:
            with open(self.path, "rb") as stream:
                stream.seek(self.offset)
                data = stream.read()
        except FileNotFoundError:
            return []
        self.offset += len(data)
        complete, _, self.partial = (self.partial + data).rpartition(b"\n")
        return parse_event_lines(complete)


def rollout_items(codex_home):
    """Counts of the response item types in the call's session records (CODEX_HOME/sessions/**/rollout-*.jsonl),
    or None when Codex wrote none. The record lists every tool call, including code mode's `exec` cells, which the
    --json stream does not show (isolation-probe/results.json, case committed-code-mode)."""
    sessions = Path(codex_home) / "sessions"
    paths = []
    for root, dirs, files in os.walk(sessions):  # never follows a symlinked directory
        paths += [Path(root) / name for name in files if name.startswith("rollout-") and name.endswith(".jsonl")]
    if not paths:
        return None
    counts = {}
    for path in sorted(paths):
        if path.is_symlink():
            continue
        for event in read_events(path):
            payload = event.get("payload")
            if event.get("type") == "response_item" and isinstance(payload, dict):
                kind = str(payload.get("type"))
                counts[kind] = counts.get(kind, 0) + 1
    return counts


def json_items(events):
    """Counts of the item types in the --json stream, one per item id."""
    seen = {}
    for position, event in enumerate(events):
        item = event.get("item")
        if str(event.get("type", "")).startswith("item.") and isinstance(item, dict):
            seen[item.get("id", position)] = str(item.get("type"))
    counts = {}
    for kind in seen.values():
        counts[kind] = counts.get(kind, 0) + 1
    return counts


def item_check(rollout, items):
    """(tool items, unexpected items) over the session record's response items and the --json items."""
    tools = unexpected = 0
    for counts, model, tool in (((rollout or {}), MODEL_ROLLOUT_ITEMS, TOOL_ROLLOUT_ITEMS),
                                (items, MODEL_JSON_ITEMS, TOOL_JSON_ITEMS)):
        for kind, count in counts.items():
            if kind in tool:
                tools += count
            elif kind not in model:
                unexpected += count
    return tools, unexpected


def turn_usage(events):
    """Summed `turn.completed` usage, or None when Codex reported none (no turn completed)."""
    usage, reported = {}, False
    for event in events:
        if event.get("type") == "turn.completed" and isinstance(event.get("usage"), dict):
            reported = True
            for key in USAGE_KEYS:
                value = event["usage"].get(key)
                if isinstance(value, int) and not isinstance(value, bool):
                    usage[key] = usage.get(key, 0) + value
    return usage if reported else None


def limit_message(events):
    """Codex's own usage-limit message: only `error` and `turn.failed` events count, never item.* content."""
    for event in events:
        if event.get("type") == "error":
            message = event.get("message")
        elif event.get("type") == "turn.failed" and isinstance(event.get("error"), dict):
            message = event["error"].get("message")
        else:
            continue
        if isinstance(message, str) and LIMIT_PHRASE.search(message):
            return message
    return None


def first_error(events):
    """The first message of Codex's own error or turn.failed events, for a stop note."""
    for event in events:
        message = (event.get("message") if event.get("type") == "error" else
                   (event.get("error") or {}).get("message") if event.get("type") == "turn.failed" else None)
        if isinstance(message, str):
            return message
    return None


def classify(events, exit_code, timed_out, interrupted, status, *, launch_error=False, rollout_found=True,
             tools=0, unexpected=0):
    """(outcome, reason).

    Only `failed` counts toward the batch's retry: the model ran and the call is unusable. `limit` and
    `unavailable` stop the run; `interrupted` (and `abandoned`, set by attempt_record) are the operator's or the
    host's, not the arm's."""
    if limit_message(events) is not None:
        return "limit", "usage_limit"
    if interrupted:
        return "interrupted", "interrupted"
    if launch_error:
        return "unavailable", "launch_error"
    if timed_out:
        return "failed", "timeout"
    types = {event.get("type") for event in events}
    if "turn.completed" not in types:
        return "unavailable", "no_turn_completed"
    if not rollout_found:
        return "unavailable", "rollout_missing"
    if tools:
        return "failed", "tool_use"
    if unexpected:
        return "unavailable", "unexpected_item"
    if exit_code != 0:
        return "failed", "exit"
    if "turn.failed" in types:
        return "failed", "turn_failed"
    if status == "missing":
        return "failed", "reply_missing"
    if status == "invalid":
        return "failed", "reply_invalid"
    return "ok", None


def usage_known(record):
    """Whether a call's token use is known: Codex reported it, or no billed request can have run (the launch
    failed, or Codex's usage-limit event refused the turn), which counts as zero. Any other call without a report
    (a timeout, an unavailable, interrupted or abandoned call) may have spent unreported tokens."""
    return (isinstance(record.get("usage"), dict) or record.get("outcome") == "limit"
            or record.get("reason") == "launch_error")


def event_counts(events):
    types = [event.get("type") for event in events]
    return {"turn_completed": types.count("turn.completed"), "turn_failed": types.count("turn.failed"),
            "error_events": types.count("error")}


def call_record(arm, index, batch, number, prompt, events, reply_path, codex_home, **measured):
    accessions = [row["accession"] for row in batch]
    status = reply_status(reply_path, accessions)
    rollout, items = rollout_items(codex_home), json_items(events)
    tools, unexpected = item_check(rollout, items)
    launch_error = measured.pop("launch_error", False)
    outcome, reason = classify(events, measured.get("exit_code"), measured.get("timed_out", False),
                               measured.get("interrupted", False), status, launch_error=launch_error,
                               rollout_found=rollout is not None, tools=tools, unexpected=unexpected)
    usage = turn_usage(events)
    record = {"schema_version": 2, "arm": arm["id"], "model": arm["model"], "effort": arm["effort"],
              "batch": batch_id(index), "attempt": number, "accessions": accessions,
              "prompt_sha256": sha256_bytes(prompt.encode("utf-8")), "prompt_bytes": len(prompt.encode("utf-8")),
              "exit_code": None, "timed_out": False, "interrupted": False, "wall_seconds": None, "slot": None,
              "slot_wait_seconds": None, "started_utc": None, "launched_unix_ns": None, "finished_utc": None,
              "scratch_entries": None,
              "credential_link": None, **measured, **event_counts(events), "limit": outcome == "limit",
              "limit_noted": False, "session_record_found": rollout is not None, "session_items": rollout or {},
              "json_items": items, "tool_items": tools, "unexpected_items": unexpected, "usage": usage,
              "usage_status": "reported" if usage is not None else "none",
              "reply_status": status, "outcome": outcome, "reason": reason, "no_document_text": True}
    record["usage_known"] = usage_known(record)
    return record


def attempt_dirs(batch_dir):
    """The attempt directories of one batch, in attempt-number order, with their numbers."""
    found = []
    if Path(batch_dir).is_dir():
        for child in Path(batch_dir).iterdir():
            match = ATTEMPT_DIR.fullmatch(child.name)
            if match and child.is_dir() and not child.is_symlink():
                found.append((int(match[1]), child))
    return sorted(found)


def attempt_record(arm, index, batch, number, attempt_dir, template):
    """The attempt's call.json, or, when the runner died before writing one, its abandoned record.

    An abandoned attempt never counts toward the batch's retry: the runner's death is not the arm's behaviour, and
    the batch runs again. Its usage counts when Codex reported it. When its events show the usage limit it is a
    limit call whose note was never published (limit_noted false), which the arm's next run publishes before any
    call.
    """
    try:
        record = json.loads((Path(attempt_dir) / "call.json").read_bytes())
        if isinstance(record, dict):
            return record
    except (OSError, ValueError):
        pass
    events = read_events(Path(attempt_dir) / "events.jsonl")
    record = call_record(arm, index, batch, number, build_prompt(template, batch), events,
                         Path(attempt_dir) / "reply.json", Path(attempt_dir) / "codex-home", exit_code=None)
    if record["outcome"] != "limit":
        record["outcome"], record["reason"] = "abandoned", "abandoned"
    record["usage_known"] = usage_known(record)
    return record


def batch_state(records, retries):
    """completed (an ok call), failed (more failed calls than retries) or pending. Only `failed` calls count."""
    if any(record.get("outcome") == "ok" for record in records):
        return "completed"
    failures = sum(record.get("outcome") == "failed" for record in records)
    return "failed" if failures > retries else "pending"


# --------------------------------------------------------------------------- host resources

def try_lock(fd):
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError as error:
        if error.errno in (errno.EAGAIN, errno.EACCES, errno.EWOULDBLOCK):
            return False
        raise


def open_lock(path, mode=0o644):
    return os.open(path, os.O_RDWR | os.O_CREAT, mode)


def lock_held(path):
    """True while some process holds the lock file (a runner or a codex it started)."""
    if not Path(path).exists():
        return False
    fd = open_lock(path)
    try:
        if try_lock(fd):
            fcntl.flock(fd, fcntl.LOCK_UN)
            return False
        return True
    finally:
        os.close(fd)


def acquire_slot(lock_dir, slots, poll_seconds, stop):
    """(fd, slot number) of the first free host slot, waiting while all are taken; (None, None) once stopped."""
    while not stop.is_set():
        for number in range(1, slots + 1):
            fd = open_lock(Path(lock_dir) / f"slot-{number}")
            if try_lock(fd):
                return fd, number
            os.close(fd)
        stop.wait(poll_seconds)
    return None, None


def checked_lock_dir(lock_dir):
    """The host's existing slot directory; never created here, so a mistyped path cannot start a private pool."""
    path = path_safety.refuse_untrusted_symlinks(Path(lock_dir), "lock directory symlink refused")
    if not path.is_dir():
        raise ValueError(f"lock directory {path} does not exist; pass the host's Codex slot directory")
    return path


def inside_repository(path):
    for candidate in (Path(path), *Path(path).parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def private_dir(path):
    """An owner-only (0700) directory of this user, created if missing; symlinks and wider modes are refused."""
    path = path_safety.refuse_untrusted_symlinks(Path(path).expanduser(), "state symlink refused")
    if not path.exists():
        try:
            path.mkdir(mode=0o700, parents=True)
        except FileExistsError:  # another arm's run created it first; the checks below still apply
            pass
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError(f"{path} must be a directory of this user with mode 0700")
    return path


def write_private(path, data, replace=False):
    """Write a 0600 file: exclusively, or atomically through a temporary file when `replace` is set."""
    path = Path(path)
    target = path.with_name(f".{path.name}.tmp") if replace else path
    flags = os.O_WRONLY | os.O_CREAT | (os.O_TRUNC if replace else os.O_EXCL)
    fd = os.open(target, flags, 0o600)
    with os.fdopen(fd, "wb") as stream:
        os.fchmod(stream.fileno(), 0o600)
        stream.write(data)
    if replace:
        os.replace(target, path)


def append_private(path, line):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(fd, "ab") as stream:
        stream.write((json.dumps(line, sort_keys=True) + "\n").encode())


@contextlib.contextmanager
def launch_gate(state_dir):
    """The state-wide gate: a call starts, and a stop note is published, only while holding it, so no call of any
    arm starts after a note exists. Each use opens its own descriptor, so threads exclude each other too."""
    fd = open_lock(Path(state_dir) / "launch.lock", 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


def present_note(state_dir):
    """The first stop note present in the state directory (LIMIT before UNAVAILABLE), or None."""
    for name in NOTES:
        if (Path(state_dir) / name).exists():
            return name
    return None


def native_auth_path():
    """The native Codex sign-in file, $CODEX_HOME/auth.json or ~/.codex/auth.json. It is never read here: each call's
    own CODEX_HOME links to it."""
    return Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex").expanduser().absolute() / "auth.json"


def checked_native_auth(state_dir):
    native = native_auth_path()
    if not native.is_file():
        raise ValueError(f"no native Codex sign-in file at {native}; sign in natively (the file store) first")
    home, state = native.parent.resolve(), Path(state_dir).resolve()
    if home == state or state in home.parents or home in state.parents:
        raise ValueError("the native Codex home and the state directory must not contain each other")
    return native


def system_config_issue():
    present = [path for path in SYSTEM_CONFIG_FILES if Path(path).exists()]
    if present:
        return f"system Codex configuration {', '.join(present)} applies despite --ignore-user-config"
    return None


def checked_scratch_root(state_dir):
    """The system temporary directory that holds each call's scratch HOME, TMPDIR and working directory: outside the
    state tree and every repository."""
    root = Path(tempfile.gettempdir()).resolve()
    state = Path(state_dir).resolve()
    if root == state or state in root.parents or inside_repository(root) is not None:
        raise ValueError(f"the temporary directory {root} must lie outside the state directory and every repository")
    return root


def call_env(codex_home, scratch):
    """A call's whole environment: the allowlisted variables, its own CODEX_HOME, and the scratch HOME and TMPDIR."""
    env = {key: value for key, value in os.environ.items() if key in CHILD_ENV_ALLOWLIST}
    env.update({"CODEX_HOME": str(codex_home), "HOME": str(Path(scratch) / "home"),
                "TMPDIR": str(Path(scratch) / "tmp")})
    return env


def prepare_call(attempt, native_auth, scratch_root):
    """The call's CODEX_HOME (attempt/codex-home, holding only a link to the native auth.json) and its scratch
    directory (home/, cwd/ and tmp/, all empty, 0700)."""
    codex_home = Path(attempt) / "codex-home"
    codex_home.mkdir(mode=0o700)
    (codex_home / "auth.json").symlink_to(native_auth)
    scratch = Path(tempfile.mkdtemp(prefix=SCRATCH_PREFIX, dir=scratch_root))
    for sub in ("home", "cwd", "tmp"):
        (scratch / sub).mkdir(mode=0o700)
    if inside_repository(scratch / "cwd") is not None:
        raise ValueError(f"{scratch} lies inside a repository")
    return codex_home, scratch


def finish_call(codex_home, scratch):
    """Remove the call's credential link and its scratch directory. The state of the link (removed, missing or
    replaced: Codex wrote a file in its place, which is never read or removed here) and the number of entries Codex
    left in the scratch directory."""
    link = Path(codex_home) / "auth.json"
    if link.is_symlink():
        link.unlink()
        state = "removed"
    else:
        state = "replaced" if link.exists() else "missing"
    entries = 0
    if scratch is not None and Path(scratch).is_dir():
        for sub in ("home", "cwd", "tmp"):
            for _, dirs, files in os.walk(Path(scratch) / sub):
                entries += len(dirs) + len(files)
        shutil.rmtree(scratch)
    return state, entries


def remove_stale_link(codex_home):
    """A dead runner's call may have left its credential link; only a symlink named auth.json is removed."""
    link = Path(codex_home) / "auth.json"
    if link.is_symlink():
        link.unlink()


def codex_version(codex):
    """The first line of `codex --version`, run with the allowlisted environment and a throwaway Codex home."""
    with tempfile.TemporaryDirectory(prefix=SCRATCH_PREFIX) as scratch:
        env = {key: value for key, value in os.environ.items() if key in CHILD_ENV_ALLOWLIST}
        env.update({"CODEX_HOME": scratch, "HOME": scratch, "TMPDIR": scratch})
        try:
            done = subprocess.run([codex, "--version"], stdin=subprocess.DEVNULL, capture_output=True, text=True,
                                  timeout=60, check=False, env=env, cwd=scratch)
        except (OSError, subprocess.SubprocessError):
            return None
    lines = (done.stdout or "").strip().splitlines()
    return lines[0].strip() if done.returncode == 0 and lines else None


def codex_argv(codex, model, effort, schema, reply, prompt):
    values = {"<model>": model, 'model_reasoning_effort="<effort>"': f'model_reasoning_effort="{effort}"',
              "<schema>": str(schema), "<reply>": str(reply), "<prompt>": prompt}
    return [str(codex), *(values.get(part, part) for part in CODEX_ARGV)]


def group_alive(pgid):
    try:
        os.killpg(pgid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def stop_group(process, grace_seconds):
    """TERM the call's process group, then KILL what is left after the grace period."""
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    end = time.monotonic() + grace_seconds
    while time.monotonic() < end:
        if process.poll() is not None and not group_alive(process.pid):
            return
        time.sleep(0.05)
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait()


def identity(plan, plan_sha256, arm, batches, version):
    """What every call of an arm must share; a later run of the arm must match it exactly."""
    return {"schema_version": 1, "arm": arm["id"], "model": arm["model"], "effort": arm["effort"],
            "plan_sha256": plan_sha256, "prompt_sha256": plan["prompt_sha256"],
            "schema_sha256": plan["schema_sha256"], "inputs_sha256": plan["task"]["inputs_sha256"],
            "layout_sha256": layout_sha256(batches), "batches": len(batches), "codex_version": version}


# --------------------------------------------------------------------------- one arm

class ArmRun:
    """The pending batches of one arm through at most `max_concurrent` workers sharing the host's slots."""

    def __init__(self, *, plan, arm, batches, template, codex, state_dir, arm_dir, lock_dir, schema_path,
                 run_lock_fd, native_auth, scratch_root, poll_seconds, timeout_seconds, grace_seconds):
        self.plan, self.arm, self.batches, self.template, self.codex = plan, arm, batches, template, codex
        self.state_dir, self.arm_dir, self.lock_dir = state_dir, arm_dir, lock_dir
        self.schema_path, self.run_lock_fd = schema_path, run_lock_fd
        self.native_auth, self.scratch_root = native_auth, scratch_root
        self.poll_seconds, self.timeout_seconds, self.grace_seconds = poll_seconds, timeout_seconds, grace_seconds
        self.retries = plan["calls"]["retries_per_batch"]
        self.stop, self.interrupted = threading.Event(), threading.Event()
        self.noted = {name: threading.Event() for name in NOTES}  # a stop note this run published or met
        self.mutex = threading.Lock()
        self.queue = deque()
        self.calls = 0
        self.errors = []

    def batch_dir(self, index):
        return self.arm_dir / "batches" / batch_id(index)

    def records(self, index):
        return [attempt_record(self.arm, index, self.batches[index], number, path, self.template)
                for number, path in attempt_dirs(self.batch_dir(index))]

    def finalize_abandoned(self):
        """Record every attempt a runner left without call.json (it held the run lock, so nothing runs it now) and
        remove any credential link such a runner left behind."""
        for index, batch in enumerate(self.batches):
            for number, path in attempt_dirs(self.batch_dir(index)):
                remove_stale_link(path / "codex-home")
                if not (path / "call.json").exists():
                    record = attempt_record(self.arm, index, batch, number, path, self.template)
                    write_record(path, record)

    def unpublished_limit(self):
        """(index, number, record) of the first recorded limit call whose LIMIT note was never published: its runner
        died before it saw the event, or between publishing and recording it."""
        for index in range(len(self.batches)):
            for (number, path), record in zip(attempt_dirs(self.batch_dir(index)), self.records(index)):
                if record.get("outcome") == "limit" and not record.get("limit_noted"):
                    return index, number, path, record
        return None

    def restore_limit(self, found):
        """Publish the LIMIT note of an unpublished limit call before any call, then mark the call noted."""
        index, number, path, record = found
        message = limit_message(read_events(path / "events.jsonl"))
        self.publish("LIMIT", index, number, message, "usage_limit", recovered=True)
        record["limit_noted"] = True
        write_record(path, record)

    def states(self):
        return [batch_state(self.records(index), self.retries) for index in range(len(self.batches))]

    def interrupt(self, *_):
        self.interrupted.set()
        self.stop.set()

    def publish(self, name, index, number, message, reason, recovered=False):
        """Write stop note `name` under the launch gate (never over an existing note) and stop this run."""
        note = {"note": name, "arm": self.arm["id"], "model": self.arm["model"], "effort": self.arm["effort"],
                "batch": batch_id(index), "attempt": number, "reason": reason, "recovered": recovered,
                "observed_utc": li26.now_utc(), "codex_message": (message or "")[:500], "next_step": NEXT_STEPS[name]}
        with launch_gate(self.state_dir):
            try:
                write_private(self.state_dir / name, (json.dumps(note, indent=2, sort_keys=True) + "\n").encode())
            except FileExistsError:
                pass
        self.noted[name].set()
        self.stop.set()

    def run(self):
        self.queue.extend(index for index, state in enumerate(self.states()) if state == "pending")
        workers = [threading.Thread(target=self.worker, name=f"gt26-{self.arm['id']}-{n}", daemon=True)
                   for n in range(min(self.plan["calls"]["max_concurrent"], len(self.queue)))]
        for worker in workers:
            worker.start()
        for worker in workers:
            while worker.is_alive():
                worker.join(0.2)

    def worker(self):
        try:
            while not self.stop.is_set():
                with self.mutex:
                    if not self.queue:
                        return
                    index = self.queue.popleft()
                outcome = self.call(index)
                if outcome == "failed" and not self.stop.is_set():
                    if batch_state(self.records(index), self.retries) == "pending":
                        with self.mutex:
                            self.queue.append(index)
        except Exception as error:  # a runner defect must stop the arm visibly, never drop a batch silently
            with self.mutex:
                self.errors.append(f"{type(error).__name__}: {error}")
            self.stop.set()

    def call(self, index):
        """One codex call for one batch in its own attempt directory; its outcome, or None if it never started.
        The host slot is released only after the call is recorded and any stop note is published."""
        waited = time.monotonic()
        slot_fd, slot = acquire_slot(self.lock_dir, self.plan["calls"]["slots"], self.poll_seconds, self.stop)
        if slot_fd is None:
            return None
        try:
            return self.call_in_slot(index, slot_fd, slot, round(time.monotonic() - waited, 3))
        finally:
            os.close(slot_fd)

    def call_in_slot(self, index, slot_fd, slot, slot_wait):
        batch = self.batches[index]
        prompt = build_prompt(self.template, batch)
        codex_home = scratch = process = None
        events_fd = stderr_fd = None
        measured = {"slot": slot, "slot_wait_seconds": slot_wait, "exit_code": None, "timed_out": False,
                    "interrupted": False}
        try:
            with launch_gate(self.state_dir):
                if self.stop.is_set():
                    return None
                note = present_note(self.state_dir)
                if note is not None:  # another run published a stop note meanwhile
                    self.noted[note].set()
                    self.stop.set()
                    return None
                with self.mutex:
                    batch_dir = self.batch_dir(index)
                    batch_dir.mkdir(mode=0o700, exist_ok=True)
                    number = 1 + max((n for n, _ in attempt_dirs(batch_dir)), default=0)
                    attempt = batch_dir / f"attempt-{number}"
                    attempt.mkdir(mode=0o700)
                    self.calls += 1
                codex_home, scratch = prepare_call(attempt, self.native_auth, self.scratch_root)
                reply = attempt / "reply.json"
                argv = codex_argv(self.codex, self.arm["model"], self.arm["effort"], self.schema_path, reply, prompt)
                events_fd = os.open(attempt / "events.jsonl", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                stderr_fd = os.open(attempt / "stderr.txt", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                measured["started_utc"] = li26.now_utc()
                started = time.monotonic()
                try:
                    process = subprocess.Popen(argv, cwd=scratch / "cwd", stdin=subprocess.DEVNULL, stdout=events_fd,
                                               stderr=stderr_fd, pass_fds=(slot_fd, self.run_lock_fd),
                                               start_new_session=True, env=call_env(codex_home, scratch))
                    measured["launched_unix_ns"] = time.time_ns()  # still inside the gate: before any later note
                except (OSError, ValueError) as error:
                    os.write(stderr_fd, f"launch failed: {type(error).__name__}\n".encode())
                    measured["launch_error"] = True
            tail, limit_noted = EventTail(attempt / "events.jsonl"), False
            deadline = started + self.timeout_seconds
            while process is not None:
                try:
                    measured["exit_code"] = process.wait(timeout=0.2)
                    break
                except subprocess.TimeoutExpired:
                    pass
                if not limit_noted:  # publish the limit as soon as Codex reports it, before the call ends
                    message = limit_message(tail.read())
                    if message is not None:
                        self.publish("LIMIT", index, number, message, "usage_limit")
                        limit_noted = True
                if self.interrupted.is_set():
                    measured["interrupted"] = True
                elif time.monotonic() >= deadline:
                    measured["timed_out"] = True
                else:
                    continue
                stop_group(process, self.grace_seconds)
                measured["exit_code"] = process.returncode
                break
            measured["wall_seconds"] = round(time.monotonic() - started, 3)
            measured["finished_utc"] = li26.now_utc()
            if reply.exists():
                os.chmod(reply, 0o600)
        finally:
            for fd in (events_fd, stderr_fd):
                if fd is not None:
                    os.close(fd)
            if codex_home is not None:
                measured["credential_link"], measured["scratch_entries"] = finish_call(codex_home, scratch)
        events = read_events(attempt / "events.jsonl")
        record = call_record(self.arm, index, batch, number, prompt, events, reply, codex_home, **measured)
        if record["outcome"] == "limit":
            if not limit_noted:
                self.publish("LIMIT", index, number, limit_message(events), "usage_limit")
            record["limit_noted"] = True
        elif record["outcome"] == "unavailable":
            self.publish("UNAVAILABLE", index, number, first_error(events), record["reason"])
        write_record(attempt, record)
        if record["credential_link"] == "replaced":
            raise RuntimeError(f"Codex replaced the credential link of {batch_id(index)} attempt-{number} with a "
                               "file; it was left untouched")
        return record["outcome"]


def write_record(attempt, record):
    write_private(Path(attempt) / "call.json", (json.dumps(record, indent=2, sort_keys=True) + "\n").encode(),
                  replace=True)


def run_arm(plan_path, arm_id, acquisition, state_dir, lock_dir, *, codex=None, poll_seconds=None,
            timeout_seconds=None, grace_seconds=None, on_start=None, out=None):
    """Run the arm's pending batches; the exit code (0 done, 1 runner error, 3 usage limit, 4 unavailable,
    5 interrupted, 6 done with a failed batch).

    `codex`, `poll_seconds`, `timeout_seconds` and `grace_seconds` exist for the offline tests; the command line
    always uses the codex on PATH and the plan's frozen values. `on_start` receives the ArmRun before any call
    (the command line installs its signal handlers there).
    """
    out = out or sys.stdout
    plan, plan_sha256 = load_plan(plan_path)
    verify_frozen(plan)
    arm = arm_by_id(plan, arm_id)
    template = prompt_template(plan)
    rows = load_rows(plan, acquisition)
    batches = frozen_batches(plan, template, rows)
    lock_dir = checked_lock_dir(lock_dir)
    issue = system_config_issue()
    if issue:
        raise ValueError(issue)
    codex = codex or shutil.which("codex")
    if codex is None:
        raise ValueError("codex is not on PATH")
    version = codex_version(codex)
    if version != plan["codex"]["version"]:
        raise ValueError(f"codex reports {version!r}; the plan is frozen for {plan['codex']['version']!r}")
    state_dir = private_dir(state_dir)
    native_auth = checked_native_auth(state_dir)
    scratch_root = checked_scratch_root(state_dir)
    note = present_note(state_dir)
    if note is not None:
        print(json.dumps({"arm": arm_id, "status": f"{note.lower()}_note_present", "exit": NOTES[note]}), file=out)
        return NOTES[note]
    arm_dir = private_dir(private_dir(state_dir / "arms") / arm_id)
    private_dir(arm_dir / "batches")
    run_lock_fd = open_lock(arm_dir / "run.lock", 0o600)
    try:
        if not try_lock(run_lock_fd):
            raise ValueError(f"arm {arm_id} is already running (or its codex still runs)")
        expected = identity(plan, plan_sha256, arm, batches, version)
        identity_path = arm_dir / "identity.json"
        if identity_path.exists():
            if json.loads(identity_path.read_bytes()) != expected:
                raise ValueError(f"arm {arm_id} started under a different plan, prompt, schema, inputs, layout or "
                                 "Codex version; that needs a new plan")
        else:
            write_private(identity_path, (json.dumps(expected, indent=2, sort_keys=True) + "\n").encode())
        schema_path = arm_dir / "schema.json"
        if not schema_path.exists():
            write_private(schema_path, SCHEMA.read_bytes())
        if li26.digest(schema_path) != plan["schema_sha256"]:
            raise ValueError("the arm's schema copy differs from the frozen schema")
        runner = ArmRun(plan=plan, arm=arm, batches=batches, template=template, codex=codex, state_dir=state_dir,
                        arm_dir=arm_dir, lock_dir=lock_dir, schema_path=schema_path, run_lock_fd=run_lock_fd,
                        native_auth=native_auth, scratch_root=scratch_root,
                        poll_seconds=plan["calls"]["slot_poll_seconds"] if poll_seconds is None else poll_seconds,
                        timeout_seconds=(plan["calls"]["timeout_seconds"] if timeout_seconds is None
                                         else timeout_seconds),
                        grace_seconds=plan["calls"]["kill_grace_seconds"] if grace_seconds is None else grace_seconds)
        runner.finalize_abandoned()
        started_utc, started = li26.now_utc(), time.monotonic()
        found = runner.unpublished_limit()
        if found is not None:  # a dead runner's limit call: restore the stop before any call
            runner.restore_limit(found)
        else:
            if on_start is not None:
                on_start(runner)
            runner.run()
        states = runner.states()
        if runner.errors:
            status, code = "runner_error", EXIT_ERROR
        elif runner.noted["LIMIT"].is_set():
            status, code = "limit_stopped", EXIT_LIMIT
        elif runner.noted["UNAVAILABLE"].is_set():
            status, code = "unavailable_stopped", EXIT_UNAVAILABLE
        elif runner.interrupted.is_set():
            status, code = "interrupted", EXIT_INTERRUPTED
        elif "pending" in states:
            status, code = "runner_error", EXIT_ERROR
        elif "failed" in states:
            status, code = "complete_with_failed_batches", EXIT_FAILED_BATCHES
        else:
            status, code = "complete", EXIT_DONE
        summary = {"arm": arm_id, "status": status, "exit": code, "calls": runner.calls,
                   "batches": {state: states.count(state) for state in ("completed", "failed", "pending")}}
        append_private(arm_dir / "runs.jsonl", {**summary, "started_utc": started_utc,
                                                  "finished_utc": li26.now_utc(),
                                                  "elapsed_seconds": round(time.monotonic() - started, 3),
                                                  "codex_version": version, "errors": runner.errors})
        print(json.dumps(summary, sort_keys=True), file=out)
        return code
    finally:
        os.close(run_lock_fd)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    frozen = commands.add_parser("verify-frozen", help="check every frozen hash and the plan's frozen values")
    frozen.add_argument("--plan", type=Path, default=PLAN)
    shape = commands.add_parser("layout", help="verify the inputs and print the batch layout's public aggregates")
    shape.add_argument("--plan", type=Path, default=PLAN)
    shape.add_argument("--acquisition", type=Path, required=True)
    run = commands.add_parser("run", help="run one arm's pending batches")
    run.add_argument("--plan", type=Path, default=PLAN)
    run.add_argument("--arm", required=True, choices=[arm_id for arm_id, _, _ in ARMS])
    run.add_argument("--acquisition", type=Path, required=True)
    run.add_argument("--lock-dir", type=Path, required=True, help="the host's Codex slot directory (slot-1..slot-3)")
    run.add_argument("--state-dir", type=Path, default=DEFAULT_STATE_DIR)
    args = parser.parse_args(argv)
    try:
        if args.command == "verify-frozen":
            plan, _ = load_plan(args.plan)
            verify_frozen(plan)
            print("frozen inputs verified")
            return EXIT_DONE
        if args.command == "layout":
            plan, _ = load_plan(args.plan)
            template = prompt_template(plan)
            rows = load_rows(plan, args.acquisition)
            batching = plan["batching"]
            batches = plan_batches(template, rows, batching["max_filings"], batching["max_prompt_bytes"])
            summary = layout_summary(template, batches)
            summary["matches_plan"] = (summary["batches"] == batching["batches"]
                                       and summary["layout_sha256"] == batching["layout_sha256"])
            print(json.dumps(summary, sort_keys=True))
            return EXIT_DONE if summary["matches_plan"] else EXIT_ERROR

        def install(runner):
            signal.signal(signal.SIGTERM, runner.interrupt)
            signal.signal(signal.SIGINT, runner.interrupt)

        return run_arm(args.plan, args.arm, args.acquisition, args.state_dir, args.lock_dir, on_start=install)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"run_arm: {error}", file=sys.stderr)
        return EXIT_REFUSED


if __name__ == "__main__":
    sys.exit(main())
