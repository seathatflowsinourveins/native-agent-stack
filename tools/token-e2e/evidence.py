"""Evidence side of the #381 token E2E grader (unit U9): attempts, carriers, M12, retrieval, memory, T14, M7, M8, G-Q.

A local integration tool, not upstream acceptance and not a model run. Standard library only, Python 3.11+. It turns the
retained evidence of a run (Claude Workflow journals and transcripts, Agent-tool harness sessions, Codex events and
rollouts, the private ledgers of the sibling tools) into per-attempt records, and those records plus the frozen keys
into grades. Every function here is pure over parsed data, or a thin reader that returns parsed data, so `regrade` can
repeat the grading from the stored records with no source file and no model.

Sources for the rules implemented here (each names its design id):
- The U9 build contract (repair-u9.design.md b2 R1, R2, R6-R9, R11, R13-R19, R22) and the binding corrections: 1 (the
  foreground Agent tool_result is framed and carries a trailer, removed structurally before the cross-check; the shape
  is the one observed on 33 of 33 results of this client, ids removed), 4 (a superseded run is classified by its own
  transcript's final row), 5 (`toon --stats` prints the document on stdout and two status lines on stderr, read from the
  installed CLI 4.1.1: `info("Token estimates: ~N (JSON) -> ~M (TOON)")`, `success("Saved ~N tokens (-P%)")`, and with
  -o `success("Encoded `in` -> `out`")`), 6 (payload candidates), 9 (M11 for Codex role children, the four outputs of
  U13's reference specification) and the coordinator decisions U9-D1..D25.
- The sibling interfaces as stated in design a2: U2 callLedger records {session_id, owner, tool_use_id, tool, server,
  state, cause, native_status, background}, U2 run-mode children, U4 identity rows (token-e2e-identity/1) and join-ledger
  rows (token-e2e-adoption-join/1), U10's codex-driver ledger kinds (intent, spawned, finished, interrupted_driver).
  Where a sibling is not merged at this base the stated shape is consumed as data.
- transcript_audit (`_call_reads`, `_within`) and skill_usage (`fetch_kind`, `executed_text`), reused unchanged.

Answer text and transcripts are data. Every scanner is a linear character or line scanner (no backtracking regular
expression), and nothing read from evidence is loaded, expanded, templated or executed.
"""
from __future__ import annotations

import collections
import datetime
import fractions
import hashlib
import importlib.util
import json
import os
import sys
import tomllib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import frozen_checks as fc  # noqa: E402

TOOLS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SIBLINGS = {}


def sibling(directory, name):
    """Load tools/<directory>/<name>.py once, under a private module name (the sibling's own code, unchanged)."""
    key = (directory, name)
    if key not in _SIBLINGS:
        path = os.path.join(TOOLS_DIR, directory, name + ".py")
        spec = importlib.util.spec_from_file_location(f"u9_sibling_{name}", path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        _SIBLINGS[key] = module
    return _SIBLINGS[key]


# ---- Small helpers ----------------------------------------------------------------------------------------------

def carrier(status, *reasons):
    return {"status": status, "reasons": sorted(set(reasons))}


def result_dict(result):
    return {"status": result.status, "reasons": list(result.reasons)}


def result_from(record):
    return fc.Result(record["status"], record["reasons"], record.get("detail"))


def or_null(number):
    """R17: a zero denominator is undefined, never a number."""
    return number if number else None


def counts_as_lower_pass(status):
    return status == "pass"


def counts_as_upper_pass(status):
    """Unknown counts as a pass on the upper bound; an incomplete control never does."""
    return status in ("pass", "unknown")


def iso_seconds(text):
    return fc.parse_utc(text)


def rate(part, whole):
    return round(part / whole, 4) if whole else None


# ---- Transcript primitives (R2) ---------------------------------------------------------------------------------

def read_jsonl(path):
    """(rows, parse errors) of a JSONL file: rows are the JSON objects; a line that is not one counts as an error. An
    unreadable file gives (None, 1)."""
    try:
        with open(path, "rb") as stream:
            data = stream.read()
    except OSError:
        return None, 1
    rows, errors = [], 0
    for line in data.decode("utf-8", errors="replace").split("\n"):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            errors += 1
            continue
        if isinstance(row, dict):
            rows.append(row)
        else:
            errors += 1
    return rows, errors


def read_json(path):
    try:
        with open(path, "rb") as stream:
            document = json.loads(stream.read().decode("utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return None
    return document


def blocks_of(row):
    content = (row.get("message") or {}).get("content") if isinstance(row.get("message"), dict) else None
    return [block for block in content if isinstance(block, dict)] if isinstance(content, list) else []


def text_of_content(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(item.get("text", "") for item in content if isinstance(item, dict) and item.get("type") == "text"
                       and isinstance(item.get("text"), str))
    return ""


def row_text(row):
    message = row.get("message")
    return text_of_content(message.get("content")) if isinstance(message, dict) else ""


def api_errors(rows):
    """[(kind, text)] of the assistant rows the client wrote for an API error (isApiErrorMessage)."""
    found = []
    for row in rows:
        if row.get("type") == "assistant" and row.get("isApiErrorMessage"):
            found.append((str(row.get("error") or "unknown"), row_text(row)))
    return found


def model_turns(rows):
    """Assistant rows that are model output, not API error rows."""
    return [row for row in rows if row.get("type") == "assistant" and not row.get("isApiErrorMessage")]


def final_message(rows):
    """The last assistant message: consecutive rows of one message.id are one message (the client writes each content
    block as its own row). {"kind": "text" | "tool_use" | "none", "text": joined text blocks}."""
    groups = []
    for row in model_turns(rows):
        message = row.get("message") if isinstance(row.get("message"), dict) else {}
        identifier = message.get("id") or row.get("uuid")
        if groups and identifier is not None and groups[-1]["id"] == identifier:
            groups[-1]["rows"].append(row)
        else:
            groups.append({"id": identifier, "rows": [row]})
    if not groups:
        return {"kind": "none", "text": ""}
    last = groups[-1]["rows"]
    text = "".join(text_of_content([block]) for row in last for block in blocks_of(row))
    if any(block.get("type") == "tool_use" for row in last for block in blocks_of(row)):
        return {"kind": "tool_use", "text": text}
    return {"kind": "text" if text else "none", "text": text}


def tool_uses(rows):
    """Every tool_use block once (by id), in order: {id, name, input, timestamp, index}."""
    seen, found = set(), []
    for index, row in enumerate(rows):
        if row.get("type") != "assistant":
            continue
        for block in blocks_of(row):
            if block.get("type") == "tool_use" and block.get("id") not in seen:
                seen.add(block.get("id"))
                found.append({"id": block.get("id"), "name": str(block.get("name", "")),
                              "input": block.get("input") if isinstance(block.get("input"), dict) else {},
                              "timestamp": row.get("timestamp"), "index": index})
    return found


def tool_results(rows):
    """{tool_use_id: {"content", "is_error", "row"}} of the first result of each call."""
    found = {}
    for index, row in enumerate(rows):
        if row.get("type") != "user":
            continue
        for block in blocks_of(row):
            if block.get("type") == "tool_result" and block.get("tool_use_id") not in found:
                found[block.get("tool_use_id")] = {"content": block.get("content"), "is_error": bool(block.get("is_error")),
                                                   "row": row, "index": index}
    return found


def first_timestamp(rows):
    stamps = [row.get("timestamp") for row in rows if iso_seconds(row.get("timestamp")) is not None]
    return min(stamps, key=iso_seconds) if stamps else None


def last_timestamp(rows):
    stamps = [row.get("timestamp") for row in rows if iso_seconds(row.get("timestamp")) is not None]
    return max(stamps, key=iso_seconds) if stamps else None


def under(path, root):
    """True when the resolved `path` is the resolved `root` or below it."""
    real, base = os.path.realpath(path), os.path.realpath(root)
    return real == base or real.startswith(base.rstrip("/") + "/")


# ---- The Agent tool_result frame and trailer (correction 1) ------------------------------------------------------

FRAME_START = "[Subagent hand-back]"
FRAME_END = "The report follows:"
ASYNC_START = "Async agent launched successfully."


def _usage_block(lines, start):
    """True when lines[start:] is one `<usage>` block of `name: integer` lines closed by `</usage>` and nothing else."""
    block = lines[start:]
    if not block or not block[0].startswith("<usage>") or not block[-1].endswith("</usage>"):
        return False
    for number, line in enumerate(block):
        body = line
        if number == 0:
            body = body[len("<usage>"):]
        if number == len(block) - 1:
            body = body[:-len("</usage>")]
        name, sep, value = body.partition(": ")
        if not sep or not name or not all(char.islower() or char == "_" for char in name) or not value.strip().isdigit():
            return False
    return True


def strip_agent_result(text):
    """{"status": "inline" | "async" | "unrecognized", "text"}. The documented shapes are recognised structurally: an
    optional frame line and the child's text with every line indented by two spaces, or the child's text unframed;
    either way followed by one `agentId:` line and one `<usage>` block. A structure that does not fit is not guessed."""
    if not isinstance(text, str):
        return {"status": "unrecognized", "text": text}
    if text.startswith(ASYNC_START):
        return {"status": "async", "text": None}
    lines = text.split("\n")
    usage_at = next((number for number in range(len(lines) - 1, -1, -1) if lines[number].startswith("<usage>")), None)
    if usage_at is None:
        return {"status": "inline", "text": text} if not lines[0].startswith(FRAME_START) else \
            {"status": "unrecognized", "text": text}
    if usage_at == 0 or not lines[usage_at - 1].startswith("agentId: ") or not _usage_block(lines, usage_at):
        return {"status": "unrecognized", "text": text}
    body = lines[:usage_at - 1]
    if body and body[0].startswith(FRAME_START):
        if not body[0].endswith(FRAME_END):
            return {"status": "unrecognized", "text": text}
        body, unindented = body[1:], []
        for line in body:
            if line.startswith("  "):
                unindented.append(line[2:])
            elif line == "":
                unindented.append("")
            else:
                return {"status": "unrecognized", "text": text}
        body = unindented
    return {"status": "inline", "text": "\n".join(body)}


# ---- Persisted large tool results (R2) --------------------------------------------------------------------------

PERSIST_OPEN = "<persisted-output>"
PERSIST_KEY = "Full output saved to: "


def persisted_pointer(text):
    """The file path of a persisted-output preview, or None for an ordinary result."""
    if not isinstance(text, str) or not text.startswith(PERSIST_OPEN):
        return None
    index = text.find(PERSIST_KEY)
    if index < 0:
        return None
    start = index + len(PERSIST_KEY)
    end = text.find("\n", start)
    return text[start:end if end >= 0 else len(text)].strip() or None


def follow_persisted(text, roots):
    """{"status": inline | followed | pointer_outside_roots | pointer_unreadable, "text"}: a pointer is followed only when
    the resolved file lies under a declared root (CLAUDE_ROOT), so no answer can make the grader read another file."""
    pointer = persisted_pointer(text)
    if pointer is None:
        return {"status": "inline", "text": text}
    if not roots or not any(under(pointer, root) for root in roots):
        return {"status": "pointer_outside_roots", "text": None}
    try:
        with open(os.path.realpath(pointer), "rb") as stream:
            data = stream.read()
    except OSError:
        return {"status": "pointer_unreadable", "text": None}
    return {"status": "followed", "text": data.decode("utf-8", errors="replace")}


# ---- Attempt classes and answer carriers (R1, R2) ---------------------------------------------------------------

INADMISSIBLE_REASONS = ("usage_limit", "interrupted_driver", "startup_error")
RESPONSE_KEYS = ("answer", "evidence")


def limit_message(text):
    """R1: a message beginning "You've hit your" with either apostrophe."""
    if not isinstance(text, str):
        return False
    stripped = text.lstrip()
    return stripped.startswith("You've hit your") or stripped.startswith("You’ve hit your")


def usage_limit_message(text):
    """Codex: a message beginning "You've hit your usage limit" with either apostrophe."""
    if not isinstance(text, str):
        return False
    stripped = text.lstrip()
    return stripped.startswith("You've hit your usage limit") or stripped.startswith("You’ve hit your usage limit")


_WAIT_LEAD = ("still", "now", "i'll", "i will", "i'm", "i am", "let me", "we'll", "we will")


def wait_notice(text):
    """U2's waitNotice, as a linear scan: at most 400 characters, and the first sentence starts with up to two lead
    words, then wait or waiting, then for, on or until."""
    if not isinstance(text, str):
        return False
    stripped = text.strip()
    if not stripped or len(stripped) > 400:
        return False
    sentence = stripped
    for number, char in enumerate(stripped):
        if char in ".!?" and (number + 1 == len(stripped) or stripped[number + 1].isspace()):
            sentence = stripped[:number + 1]
            break
    words = sentence.lstrip(" \t\"'([*_`").lower().split()
    position = 0
    for _ in range(2):
        for lead in _WAIT_LEAD:
            parts = lead.split()
            if words[position:position + len(parts)] == parts:
                position += len(parts)
                break
    if position < len(words) and words[position].strip(".,:;!?") in ("wait", "waiting"):
        following = words[position + 1] if position + 1 < len(words) else ""
        return following.strip(".,:;!?") in ("for", "on", "until")
    return False


def validate_response(value):
    """The runner's responseSchema: an object with exactly answer (string) and evidence (array of strings)."""
    if not isinstance(value, dict) or set(value) != set(RESPONSE_KEYS):
        return None
    if not isinstance(value["answer"], str) or not isinstance(value["evidence"], list) \
            or not all(isinstance(item, str) for item in value["evidence"]):
        return None
    return {"text": value["answer"], "evidence": list(value["evidence"])}


def canonical_equal(left, right):
    return fc.canonical(left) == fc.canonical(right)


def _attempt(identity, actor, family, **extra):
    record = {"identity": identity, "actor": actor, "family": family, "agent_id": None, "run_index": 0,
              "superseded": False, "class": "completed", "reason": None, "cause": None, "answer": None,
              "carrier": carrier("pass"), "crosscheck": None, "inline": None, "start": None, "end": None,
              "parse_errors": 0, "facts": {}}
    record.update(extra)
    return record


def _inadmissible(record, reason):
    record.update({"class": "inadmissible", "reason": reason, "cause": None, "answer": None,
                   "carrier": carrier("unknown", reason)})
    return record


def _no_answer(record, cause):
    record.update({"class": "completed", "cause": cause, "answer": None, "carrier": carrier("fail", cause)})
    return record


def transcript_signals(rows):
    """Launch-level signals of a transcript's final rows: {rate_limited, login_failed, other_errors [kind], model_turns}."""
    errors = api_errors(rows)
    return {"rate_limited": any(kind == "rate_limit" or limit_message(text) for kind, text in errors),
            "login_failed": any(kind == "authentication_failed" for kind, _ in errors),
            "other_errors": [kind for kind, _ in errors if kind not in ("rate_limit", "authentication_failed")],
            "model_turns": len(model_turns(rows))}


def last_structured_output(rows):
    """The input of the last StructuredOutput call, validated against the response schema: (answer or None, seen)."""
    last = None
    for use in tool_uses(rows):
        if use["name"] == "StructuredOutput":
            last = use["input"]
    if last is None:
        return None, False
    return validate_response(last), True


def classify_superseded_run(rows):
    """Correction 4: a run the runtime started again is classified by its own transcript's final row. An API rate limit
    or a login failure before any model turn is inadmissible; a run that ended with an answer or a task-caused failure
    is a completed attempt; a run that simply stopped is an interrupted driver."""
    rows = rows or []
    signals = transcript_signals(rows)
    if signals["rate_limited"]:
        return {"class": "inadmissible", "reason": "usage_limit", "cause": None}
    if signals["login_failed"] and not signals["model_turns"]:
        return {"class": "inadmissible", "reason": "startup_error", "cause": None}
    if signals["login_failed"]:
        return {"class": "inadmissible", "reason": "interrupted_driver", "cause": None}
    if signals["other_errors"]:
        return {"class": "completed", "reason": None, "cause": f"api_error_{signals['other_errors'][-1]}"}
    answer, seen = last_structured_output(rows)
    if answer is not None:
        return {"class": "completed", "reason": None, "cause": None, "answer": answer}
    if seen:
        return {"class": "completed", "reason": None, "cause": "schema_invalid"}
    if final_message(rows)["kind"] == "text":
        return {"class": "completed", "reason": None, "cause": "null_result"}
    return {"class": "inadmissible", "reason": "interrupted_driver", "cause": None}


def _logged(record, label):
    """Runner log lines about this label that parse: [{response, error}]. A line that does not parse is ignored (a
    truncated log is an unavailable cross-check, never a mismatch)."""
    found = []
    for line in (record or {}).get("logs") or []:
        if not isinstance(line, str) or label not in line:
            continue
        try:
            item = json.loads(line)
        except ValueError:
            continue
        if isinstance(item, dict) and item.get("identity") == label:
            found.append(item)
    return found


def read_journal(directory):
    rows, _ = read_jsonl(os.path.join(directory, "journal.jsonl"))
    return rows or []


def run_record(directory):
    """The run record `<session>/workflows/<run>.json` next to a workflow directory, or None."""
    audit = sibling("sota-convergence", "transcript_audit")
    path = audit.run_record_path(directory)
    if path is None:
        return None
    document = read_json(str(path))
    return document if isinstance(document, dict) else None


def workflow_runs(directory, label):
    """The runs of one label in journal order, each with its journal entries, progress entry and transcript rows."""
    journal = read_journal(directory)
    record = run_record(directory)
    progress = [entry for entry in (record or {}).get("workflowProgress") or []
                if isinstance(entry, dict) and entry.get("type") == "workflow_agent"]
    results = {entry.get("agentId"): entry for entry in journal if entry.get("type") == "result"}
    failed = {entry.get("agentId") for entry in journal if entry.get("type") == "failed"}
    started = [entry for entry in journal if entry.get("type") == "started" and entry.get("agentId")]
    superseded_by = {}
    for number, entry in enumerate(started):
        if entry["agentId"] in results or not isinstance(entry.get("key"), str) or not entry["key"]:
            continue
        if any(later.get("key") == entry["key"] for later in started[number + 1:]):
            superseded_by[entry["agentId"]] = True
    runs = []
    for entry in started:
        if entry.get("label") != label:
            continue
        agent_id = entry["agentId"]
        rows, errors = read_jsonl(os.path.join(directory, f"agent-{agent_id}.jsonl"))
        runs.append({"agent_id": agent_id, "started": entry, "result": results.get(agent_id), "failed": agent_id in failed,
                     "progress": next((item for item in progress if item.get("agentId") == agent_id), None),
                     "rows": rows, "errors": errors, "superseded": bool(superseded_by.get(agent_id))})
    if not runs:  # a child that never started has only a record entry, with no agent id
        for item in progress:
            if item.get("label") == label and not item.get("agentId"):
                runs.append({"agent_id": None, "started": None, "result": None, "failed": True, "progress": item,
                             "rows": None, "errors": 0, "superseded": False})
    return runs, record


def _classify_final_workflow_run(run, record, label):
    """The launch-level class of a run the runtime did not supersede (R1)."""
    identity, rows = label, run["rows"]
    attempt = _attempt(identity, "workflow_child", "claude", agent_id=run["agent_id"])
    entry = run["result"]
    if entry is not None and entry.get("result") is not None:
        answer = validate_response(entry["result"])
        if answer is None:
            attempt.update({"class": "completed", "cause": "schema_invalid", "carrier": carrier("fail", "schema")})
            return attempt
        attempt["answer"] = answer
        logged = _logged(record, label)
        seen = [item for item in logged if "response" in item]
        if not seen:
            attempt["crosscheck"] = "unavailable"
        elif any(canonical_equal(item["response"], entry["result"]) for item in seen):
            attempt["crosscheck"] = "equal"
        else:
            attempt["crosscheck"] = "mismatch"
            attempt["carrier"] = carrier("unknown", "carrier_mismatch")
        return attempt
    progress = run["progress"] or {}
    error = progress.get("error") if isinstance(progress.get("error"), str) else ""
    logged_error = next((item.get("error") for item in _logged(record, label) if isinstance(item.get("error"), str)), "")
    signals = transcript_signals(rows or [])
    if signals["rate_limited"] or limit_message(error) or limit_message(logged_error):
        return _inadmissible(attempt, "usage_limit")
    if run["started"] is None or (signals["login_failed"] and not signals["model_turns"]):
        return _inadmissible(attempt, "startup_error")
    if entry is not None and entry.get("result") is None:
        return _no_answer(attempt, "null_result")
    if run["failed"] or progress.get("state") == "error":
        if "StructuredOutput retry cap" in error:
            return _no_answer(attempt, "schema_invalid")
        if signals["login_failed"]:
            return _inadmissible(attempt, "interrupted_driver")
        if signals["other_errors"]:
            return _no_answer(attempt, f"api_error_{signals['other_errors'][-1]}")
        return _no_answer(attempt, "null_result")
    status = (record or {}).get("status")
    if status in (None, "killed"):
        return _inadmissible(attempt, "interrupted_driver")
    attempt.update({"class": "unresolved", "carrier": carrier("unknown", "attempt_class_unresolved")})
    return attempt


def workflow_attempts(directory, label):
    """R1, R2, correction 4: one attempt per run of `label` under a Workflow directory, superseded runs first."""
    runs, record = workflow_runs(str(directory), label)
    attempts = []
    for number, run in enumerate(runs):
        if run["superseded"]:
            verdict = classify_superseded_run(run["rows"])
            attempt = _attempt(label, "workflow_child", "claude", agent_id=run["agent_id"], superseded=True)
            if verdict["class"] == "inadmissible":
                _inadmissible(attempt, verdict["reason"])
            elif verdict.get("answer") is not None:
                attempt["answer"] = verdict["answer"]
            elif verdict["cause"] == "schema_invalid":
                attempt.update({"cause": "schema_invalid", "carrier": carrier("fail", "schema")})
            else:
                _no_answer(attempt, verdict["cause"])
        else:
            attempt = _classify_final_workflow_run(run, record, label)
        attempt["run_index"] = number
        rows = run["rows"] or []
        attempt["start"], attempt["end"] = first_timestamp(rows), last_timestamp(rows)
        attempt["parse_errors"] = run["errors"]
        attempt["_rows"] = rows
        attempts.append(attempt)
    return attempts


def _read_events(path):
    rows, errors = read_jsonl(path)
    return rows, errors


def codex_exec_attempt(path, identity, ledger, exit_status=None):
    """R1 and R2 for a Codex exec launch: the last agent_message is the answer; the closed reasons come from the JSONL
    events and U10's ledger records of this identity (intent, spawned, finished, interrupted_driver)."""
    attempt = _attempt(identity, "codex_exec", "codex")
    rows, errors = _read_events(path)
    attempt["parse_errors"] = errors
    mine = [item for item in ledger if item.get("identity") == identity]
    kinds = [item.get("kind") for item in mine]
    finished = next((item for item in mine if item.get("kind") == "finished"), None)
    types = [row.get("type") for row in rows or []]
    if rows is None or "thread.started" not in types and not errors:
        return _inadmissible(attempt, "startup_error")
    limit = False
    failure = None
    for row in rows:
        if row.get("type") == "turn.failed":
            failure = (row.get("error") or {}).get("message") if isinstance(row.get("error"), dict) else None
            limit = limit or usage_limit_message(failure)
        elif row.get("type") == "error":
            limit = limit or usage_limit_message(row.get("message"))
    if limit:
        return _inadmissible(attempt, "usage_limit")
    if "interrupted_driver" in kinds or (("intent" in kinds or "spawned" in kinds) and finished is None):
        return _inadmissible(attempt, "interrupted_driver")
    if errors:
        attempt.update({"class": "unresolved", "carrier": carrier("unknown", "parse")})
        return attempt
    if finished is not None and finished.get("timed_out"):
        return _no_answer(attempt, "timeout")
    if "turn.failed" in types:
        return _no_answer(attempt, "turn_failed")
    messages = [row["item"] for row in rows if row.get("type") == "item.completed" and isinstance(row.get("item"), dict)
                and row["item"].get("type") == "agent_message"]
    if "turn.completed" not in types:
        attempt.update({"class": "unresolved", "carrier": carrier("unknown", "attempt_class_unresolved")})
        return attempt
    text = messages[-1].get("text") if messages else None
    if isinstance(exit_status, int) and not isinstance(exit_status, bool) and exit_status != 0 and not (text or "").strip():
        return _no_answer(attempt, "exit_nonzero")
    if not isinstance(text, str) or not text.strip():
        return _no_answer(attempt, "empty")
    attempt["answer"] = {"text": text, "evidence": []}
    return attempt


def _agent_result_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(item.get("text", "") for item in content if isinstance(item, dict) and isinstance(item.get("text"), str))
    return ""


def _classify_child_transcript(attempt, rows, errors):
    """Launch-level class of a transcript-backed child from its own final rows; returns the final message."""
    signals = transcript_signals(rows)
    final = final_message(rows)
    if signals["rate_limited"] and final["kind"] != "text":
        _inadmissible(attempt, "usage_limit")
    elif signals["login_failed"] and not signals["model_turns"]:
        _inadmissible(attempt, "startup_error")
    elif signals["login_failed"]:
        _inadmissible(attempt, "interrupted_driver")
    elif signals["other_errors"] and final["kind"] != "text":
        _no_answer(attempt, f"api_error_{signals['other_errors'][-1]}")
    elif final["kind"] != "text":
        _inadmissible(attempt, "interrupted_driver")
    return final


def _answer_from_final(attempt, final, errors):
    text = final["text"]
    if attempt["class"] != "completed" or attempt["cause"]:
        return
    if not text.strip():
        _no_answer(attempt, "empty")
    elif wait_notice(text):
        _no_answer(attempt, "wait_notice")
    else:
        attempt["answer"] = {"text": text, "evidence": []}
        if errors:
            attempt["carrier"] = carrier("unknown", "parse")


def agent_child_attempt(session_dir, tool_use_id, identity, roots=()):
    """R2 agent_child and correction 1: the child's own final assistant text is the answer; the harness tool_result is a
    cross-check after its frame and trailer are removed structurally (a mismatch is unknown, never a guess)."""
    session_dir = str(session_dir)
    attempt = _attempt(identity, "agent_child", "claude")
    harness, herrors = read_jsonl(session_dir + ".jsonl")
    child_rows, cerrors, agent_id = None, 0, None
    subagents = os.path.join(session_dir, "subagents")
    matches = []
    try:
        names = sorted(os.listdir(subagents))
    except OSError:
        names = []
    for name in names:
        if name.startswith("agent-") and name.endswith(".meta.json"):
            meta = read_json(os.path.join(subagents, name))
            if isinstance(meta, dict) and meta.get("toolUseId") == tool_use_id:
                matches.append(name[len("agent-"):-len(".meta.json")])
    if len(matches) == 1:
        agent_id = matches[0]
        child_rows, cerrors = read_jsonl(os.path.join(subagents, f"agent-{agent_id}.jsonl"))
    attempt["agent_id"] = agent_id
    if child_rows is None:
        attempt.update({"class": "unresolved", "carrier": carrier("unknown", "attempt_class_unresolved")})
        return attempt
    attempt["start"], attempt["end"] = first_timestamp(child_rows), last_timestamp(child_rows)
    attempt["parse_errors"] = cerrors
    attempt["_rows"] = child_rows
    final = _classify_child_transcript(attempt, child_rows, cerrors)
    _answer_from_final(attempt, final, cerrors)
    result = tool_results(harness or []).get(tool_use_id)
    stripped = strip_agent_result(_agent_result_text(result["content"])) if result else {"status": "unrecognized", "text": None}
    attempt["inline"] = result is not None and stripped["status"] != "async"
    if attempt["class"] == "completed" and not attempt["cause"]:
        if stripped["status"] == "async":
            attempt["carrier"] = carrier("fail", "not_inline")
        elif herrors:
            attempt["carrier"] = carrier("unknown", "parse")
        elif result is None:
            attempt["carrier"] = carrier("unknown", "carrier_mismatch")
        else:
            compared = stripped["text"] if stripped["status"] == "inline" else _agent_result_text(result["content"])
            if (compared or "").rstrip() != final["text"].rstrip():
                attempt["carrier"] = carrier("unknown", "carrier_mismatch")
    return attempt


def transcript_attempt(path, identity, actor, stdout_path=None):
    """R2 main and strict_process: the redirected stdout is the answer when present, cross-checked with the session
    transcript's final assistant text; without stdout the transcript's final text is the answer."""
    attempt = _attempt(identity, actor, "claude")
    rows, errors = read_jsonl(path) if path else (None, 1)
    if rows is None:
        attempt.update({"class": "unresolved", "carrier": carrier("unknown", "attempt_class_unresolved")})
        return attempt
    attempt["start"], attempt["end"] = first_timestamp(rows), last_timestamp(rows)
    attempt["parse_errors"] = errors
    attempt["_rows"] = rows
    final = _classify_child_transcript(attempt, rows, errors)
    _answer_from_final(attempt, final, errors)
    if stdout_path is not None and attempt["class"] == "completed" and not attempt["cause"]:
        try:
            with open(stdout_path, "rb") as stream:
                out = stream.read().decode("utf-8", errors="replace")
        except OSError:
            out = None
        if out is not None and out.rstrip() != final["text"].rstrip():
            attempt["carrier"] = carrier("unknown", "carrier_mismatch")
    return attempt


# ---- Task, blind and control outcomes (R6), G-Q (R16), G-C (R17), M8 (R15) --------------------------------------

def attempt_effect(attempt, reading):
    """What one attempt does to its task: pass | fail | unknown | ignore. Inadmissible attempts never pass or fail a task
    (U9-D1); the alternative reading (R2-10 every_recorded) counts them, and unresolved ones, as failures."""
    if reading == "every_recorded":
        if attempt["class"] in ("inadmissible", "unresolved"):
            return "fail"
        return attempt["status"]
    if attempt["class"] == "inadmissible":
        return "ignore"
    if attempt["class"] == "unresolved":
        return "unknown"
    return attempt["status"]


def blind_effect(attempt, reading):
    """The same for a blind attempt: only clean attempts speak; a contaminated one is retained and excluded (README,
    Blind qualification and controls); an attempt of unknown cleanliness can block a pass but never fails the task."""
    if attempt["class"] in ("inadmissible", "unresolved"):
        return "fail" if reading == "every_recorded" else "ignore"
    clean = attempt.get("clean")
    if clean == "contaminated":
        return "ignore"
    if clean == "clean":
        return attempt["status"]
    return "unknown" if attempt["status"] == "fail" else "ignore"


def decide_task(attempts, reading, *, kind="plain", read_rows=None):
    """R6: the outcome of one task in one arm from its attempts. pass needs a completed attempt and every considered one
    passing; fail needs one failing attempt; the rest is unknown. Blind tasks use their own effects; the positive
    control follows the task rule and a zero Read-row count makes it incomplete_control."""
    inadmissible = sum(1 for item in attempts if item["class"] == "inadmissible")
    last = attempts[-1] if attempts else None
    last_status = None
    if last is not None:
        effect = attempt_effect(last, "completed_attempts") if kind != "blind" else blind_effect(last, "completed_attempts")
        last_status = "pass" if effect == "pass" else "fail" if effect == "fail" else "unknown"
    if reading == "last_attempt" and last is not None:
        return {"status": last_status, "reason": None, "last_attempt": last_status, "inadmissible": inadmissible}
    effects = [blind_effect(item, reading) if kind == "blind" else attempt_effect(item, reading) for item in attempts]
    considered = [effect for effect in effects if effect != "ignore"]
    reason = None
    if "fail" in considered:
        status = "fail"
    elif kind == "blind":
        if "pass" not in considered:
            status, reason = "unknown", "no_clean_verdict"
        elif "unknown" in considered:
            status, reason = "unknown", "unclean_verdict"
        else:
            status = "pass"
    elif not considered:
        status, reason = "unknown", "no_completed_attempt"
    elif "unknown" in considered:
        status = "unknown"
        reason = "attempt_class_unresolved" if any(item["class"] == "unresolved" for item in attempts) else "attempt_unknown"
    else:
        status = "pass"
    if kind == "control":
        if read_rows == 0:
            status, reason = "incomplete_control", "zero_read_rows"
        elif read_rows is None and status == "pass":
            status, reason = "unknown", "control_rows_unobserved"
    return {"status": status, "reason": reason, "last_attempt": last_status, "inadmissible": inadmissible}


def _population(tasks, readings):
    organic_only = readings.get("R2-07") == "organic_only"
    return [task for task in tasks if "B" in task["arms"] and (not organic_only or task["opportunity"] == "organic")]


def _outcome(outcomes, arm, task):
    return outcomes.get((arm, task["id"]), {"status": "unknown"})["status"]


def _clause1(population, outcomes):
    statuses = [_outcome(outcomes, "B", task) for task in population]
    lower = sum(1 for status in statuses if counts_as_lower_pass(status))
    upper = sum(1 for status in statuses if counts_as_upper_pass(status))
    status = "pass" if lower == len(population) else "fail"
    return {"population": len(population), "pass_lower": lower, "pass_upper": upper, "status": status,
            "sensitive": status == "fail" and upper == len(population)}


def _pairs(matched, outcomes):
    def counts(arm, bound):
        statuses = [_outcome(outcomes, arm, task) for task in matched]
        test = counts_as_lower_pass if bound == "lower" else counts_as_upper_pass
        return sum(1 for status in statuses if test(status))
    return {"B_lower": counts("B", "lower"), "A_lower": counts("A", "lower"), "B_upper": counts("B", "upper"),
            "A_upper": counts("A", "upper")}


PAIRINGS = (("lower", "lower"), ("upper", "lower"), ("lower", "upper"), ("upper", "upper"))


def _holds(numbers, pair):
    return numbers[f"B_{pair[0]}"] >= numbers[f"A_{pair[1]}"]


def g_q(tasks, outcomes, readings):
    """R16: clause 1 (every arm-B task with a frozen check passes) and clause 2 (B is at least A over the matched tasks,
    per family and pooled), with the bounds, the sensitivity flags and the published alternatives."""
    population = _population(tasks, readings)
    clause1 = _clause1(population, outcomes)
    matched = [task for task in tasks if "B" in task["arms"] and "A" in task["arms"]]
    if readings.get("R2-08") == "matched_organic":
        matched = [task for task in matched if task["opportunity"] == "organic"]
    numbers = {"claude": _pairs([task for task in matched if task["family"] == "claude"], outcomes),
               "codex": _pairs([task for task in matched if task["family"] == "codex"], outcomes),
               "pooled": _pairs(matched, outcomes)}
    judged = ("pooled",) if readings.get("R2-08") == "pooled_only" else ("claude", "codex", "pooled")
    overall = {pair: all(_holds(numbers[name], pair) for name in judged) for pair in PAIRINGS}
    clause2 = {}
    for name, counts in numbers.items():
        holds = {_holds(counts, pair) for pair in PAIRINGS}
        clause2[name] = dict(counts, status="pass" if _holds(counts, PAIRINGS[0]) else "fail", sensitive=len(holds) > 1)
    clause2.update(status="pass" if overall[PAIRINGS[0]] else "fail", sensitive=len(set(overall.values())) > 1)
    organic = readings.get("R2-07") == "organic_only"
    alternative = [task for task in tasks if "B" in task["arms"] and (organic or task["opportunity"] == "organic")]
    return {"clause1": clause1, "clause2": clause2,
            "status": "pass" if clause1["status"] == "pass" and clause2["status"] == "pass" else "fail",
            "failed_positive_control": any(_outcome(outcomes, "B", task) == "incomplete_control" for task in population),
            "alternatives": {"all_B_with_check" if organic else "organic_only": {"clause1": _clause1(alternative, outcomes)}}}


def g_c_denominators(tasks, outcomes):
    """R17: per family and arm, the tasks passing under R6 as lower and upper bounds plus the matched breakdown; a zero
    denominator is null (undefined), never zero. U9 does not price."""
    result = {}
    for family, arms in fc.FAMILY_ARMS.items():
        result[family] = {}
        members = [task for task in tasks if task["family"] == family]
        for arm in arms:
            in_arm = [task for task in members if arm in task["arms"]]
            matched = [task for task in in_arm if "B" in task["arms"] and "A" in task["arms"]]

            def count(items, test):
                return sum(1 for task in items if test(_outcome(outcomes, arm, task)))
            result[family][arm] = {"lower": or_null(count(in_arm, counts_as_lower_pass)),
                                   "upper": or_null(count(in_arm, counts_as_upper_pass)),
                                   "matched_lower": or_null(count(matched, counts_as_lower_pass)),
                                   "matched_upper": or_null(count(matched, counts_as_upper_pass))}
    return result


M8_DEFAULTS = {"minimum": 5, "threshold": 0.8}
_ADOPTION_AS_STATUS = {"adopted": "pass", "not_adopted": "fail", "unknown": "unknown"}


def m8_lane(opportunities, readings, criteria=None):
    """R15: O opportunities (not_launched included), R recorded attempts; the lower bound counts adopted and correct, the
    upper bound counts (adopted or unknown) and (correct or unknown); an inadmissible attempt is unknown in the
    denominator (R2-21 alternative: excluded)."""
    criteria = dict(M8_DEFAULTS, **(criteria or {}))
    items = [item for item in opportunities if not (readings.get("R2-21") == "excluded" and item["kind"] == "inadmissible")]
    total = len(items)
    recorded = sum(1 for item in items if item["kind"] != "not_launched")
    lower = upper = 0
    for item in items:
        grade = "unknown" if item["kind"] in ("inadmissible", "not_launched") else item["grade"]
        adopted = _ADOPTION_AS_STATUS.get(item["adopted"], "unknown")
        lower += counts_as_lower_pass(adopted) and counts_as_lower_pass(grade)
        upper += counts_as_upper_pass(adopted) and counts_as_upper_pass(grade)
    theta = fractions.Fraction(str(criteria["threshold"]))
    meets = total > 0 and fractions.Fraction(lower, total) >= theta
    status = "incomplete" if recorded < criteria["minimum"] else "pass" if meets else "fail"
    could = total > 0 and fractions.Fraction(upper, total) >= theta
    return {"O": total, "R": recorded, "correct_lower": lower, "correct_upper": upper, "rate_lower": rate(lower, total),
            "rate_upper": rate(upper, total), "status": status, "sensitive": (not meets) and could}


SHELL_TOOLS = ("Bash", "command", "shell")
CTX_SHELL_TOOLS = ("ctx_execute", "ctx_batch_execute")


# ---- Call views (R2, R8, R9): tool calls with their state and result text ---------------------------------------

def result_text_of(content):
    """The text of a tool_result content (a string, or the text blocks of a list)."""
    return _agent_result_text(content)


def claude_calls(rows, ledger, owner, roots=()):
    """Every tool call of a Claude transcript: {id, name, tool, server, input, ts, state, cause, background, result_text,
    result_status, is_error}. The state comes from U2's call ledger, the one classifier (joined on the owner and the
    tool_use id); a call without a record has no state. A persisted-output result is followed only under `roots`."""
    records = {(item.get("owner"), item.get("tool_use_id")): item for item in ledger}
    results = tool_results(rows)
    calls = []
    for use in tool_uses(rows):
        name = use["name"]
        parts = name.split("__")
        server = parts[1] if name.startswith("mcp__") and len(parts) >= 3 else None
        tool = "__".join(parts[2:]) if server else name
        result = results.get(use["id"])
        record = records.get((owner, use["id"]))
        text, status = None, None
        if result is not None:
            followed = follow_persisted(result_text_of(result["content"]), list(roots))
            text, status = followed["text"], followed["status"]
        calls.append({"id": use["id"], "name": name, "tool": tool, "server": server, "input": use["input"],
                      "ts": use["timestamp"], "state": record.get("state") if record else None,
                      "cause": record.get("cause") if record else None,
                      "background": bool(record.get("background")) if record else False, "result_text": text,
                      "result_status": status, "is_error": bool(result and result["is_error"])})
    return calls


def codex_calls(records):
    """The calls of a Codex exec events file: web_search, command_execution and mcp_tool_call items, with the state from
    the item's own status and exit code. Exec events carry no timestamps: the launch is the unit of the window."""
    calls = []
    for row in records:
        item = row.get("item") if row.get("type") == "item.completed" and isinstance(row.get("item"), dict) else None
        if item is None:
            continue
        kind = item.get("type")
        status = item.get("status")
        base = {"id": item.get("id"), "ts": None, "cause": None, "background": False, "result_status": "inline",
                "is_error": False}
        if kind == "web_search":
            action = item.get("action") if isinstance(item.get("action"), dict) else {}
            calls.append(dict(base, name="web_search", tool="web_search", server=None, input={"action": action, "query": item.get("query")},
                              state="succeeded" if status in (None, "completed") else "failed", result_text=None))
        elif kind == "command_execution":
            code = item.get("exit_code")
            ok = status in (None, "completed") and code == 0
            calls.append(dict(base, name="command_execution", tool="command", server=None, input={"command": item.get("command")},
                              state="succeeded" if ok else "failed", result_text=item.get("aggregated_output")))
        elif kind == "mcp_tool_call":
            arguments = item.get("arguments") if isinstance(item.get("arguments"), dict) else {}
            result = item.get("result")
            # A retained item is {arguments, error, id, result, server, status, tool, type}: an error beside a completed
            # status is still an error, never a retrieval.
            ok = status in (None, "completed") and item.get("error") is None
            calls.append(dict(base, name=f"mcp__{item.get('server')}__{item.get('tool')}", tool=str(item.get("tool")),
                              server=item.get("server"), input=arguments, state="succeeded" if ok else "failed",
                              result_text=json.dumps(result) if result is not None else None))
    return calls


def command_text(call):
    """The shell text of a call (Bash command, ctx_execute shell code, ctx_batch_execute commands), or None."""
    payload = call.get("input") or {}
    if call["tool"] in SHELL_TOOLS and isinstance(payload.get("command"), str):
        return payload["command"]
    if call["tool"] == "ctx_execute" and payload.get("language") in (None, "shell", "bash", "sh") \
            and isinstance(payload.get("code"), str):
        return payload["code"]
    if call["tool"] == "ctx_batch_execute":
        texts = [item.get("command") for item in payload.get("commands") or [] if isinstance(item, dict)]
        return "\n".join(text for text in texts if isinstance(text, str)) or None
    return None


def code_text(call):
    """Any code or command text of a call, whatever the language (used to see that a call names something)."""
    payload = call.get("input") or {}
    parts = [payload.get(name) for name in ("command", "code")]
    parts += [item.get("command") for item in payload.get("commands") or [] if isinstance(item, dict)]
    return "\n".join(part for part in parts if isinstance(part, str))


_PROGRAM_BEFORE = frozenset(" \t\n;&|(`$/\"'")
_PROGRAM_AFTER = frozenset(" \t\n;&|)`\"'")


def has_program_word(text, word):
    """True when `word` appears as a whole command word: not part of a longer name (toon-format, atoon) or a path."""
    start = 0
    while True:
        index = text.find(word, start)
        if index < 0:
            return False
        before = text[index - 1] if index else " "
        after = text[index + len(word)] if index + len(word) < len(text) else " "
        if before in _PROGRAM_BEFORE and after in _PROGRAM_AFTER:
            return True
        start = index + 1


# ---- Retrieval (R8) -----------------------------------------------------------------------------------------------

def call_urls(call):
    """URLs a call names: its input url and requests[].url, and every URL in its command or code text."""
    payload = call.get("input") or {}
    urls = []
    if isinstance(payload.get("url"), str):
        urls.append(fc.normalize_url(payload["url"]))
    for item in payload.get("requests") or []:
        if isinstance(item, dict) and isinstance(item.get("url"), str):
            urls.append(fc.normalize_url(item["url"]))
    action = payload.get("action") if isinstance(payload.get("action"), dict) else {}
    if isinstance(action.get("url"), str):
        urls.append(fc.normalize_url(action["url"]))
    urls += fc.extract_urls(code_text(call))
    return urls


def call_retrieves_url(call, url, reading):
    """R8: "yes" when the call is a succeeded, classifiable retrieval of `url`; "unconfirmed" when it names the URL but
    its state or its kind cannot show a retrieval; "no" otherwise."""
    if not any(fc.url_matches(found, url, reading) for found in call_urls(call)):
        return "no"
    if call["state"] is None:
        return "unconfirmed"
    if call["state"] != "succeeded":
        return "no"
    tool, payload = call["tool"], call.get("input") or {}
    if tool in ("WebFetch", "ctx_fetch_and_index"):
        return "yes"
    if tool == "web_search":
        return "yes" if (payload.get("action") or {}).get("type") in ("open_page", "find_in_page") else "no"
    shell = command_text(call)
    if shell is not None:
        skill = sibling("skill-usage", "skill_usage")
        if skill.fetch_kind(shell) == "fetch" and any(fc.url_matches(found, url, reading)
                                                       for found in fc.extract_urls(skill.executed_text(shell))):
            return "yes"
    return "unconfirmed"


def retrieval_check(calls, urls, window, readings):
    """R8: every frozen URL needs a succeeded, in-window retrieval by the child itself. A cited URL with no call fails
    (missing_source); a call that names it without a classifiable kind leaves it unknown (retrieval_unconfirmed)."""
    since, until = iso_seconds(window["since"]), iso_seconds(window["until"])
    inside = [call for call in calls
              if call["ts"] is None or (iso_seconds(call["ts"]) is not None and since <= iso_seconds(call["ts"]) < until)]
    outcomes = []
    for url in urls:
        verdicts = [call_retrieves_url(call, url, readings["R2-18"]) for call in inside]
        outcomes.append("yes" if "yes" in verdicts else "unconfirmed" if "unconfirmed" in verdicts else "no")
    if "no" in outcomes:
        return fc.fail("missing_source")
    if "unconfirmed" in outcomes:
        return fc.unknown("retrieval_unconfirmed")
    return fc.ok()


# ---- Historical memory (R9) and T2 recovery (R2-17) ---------------------------------------------------------------

def _stem(path):
    name = path.rsplit("/", 1)[-1]
    return name[:-3] if name.endswith(".md") else name


def _bounded(text, token):
    """True when `token` occurs in `text` with no name character on either side (a longer id is another record)."""
    start = 0
    while True:
        index = text.find(token, start)
        if index < 0:
            return False
        before = text[index - 1] if index else " "
        after = text[index + len(token)] if index + len(token) < len(text) else " "
        if not (fc.is_word_char(before) or before == "-") and not (fc.is_word_char(after) or after == "-"):
            return True
        start = index + 1


def resolves_to_record(text, record):
    """A result resolves to a frozen record when it names its path, its bare id or its content digest."""
    if not isinstance(text, str):
        return False
    if record.get("content_sha256") and record["content_sha256"] in text:
        return True
    return record["path"] in text or _bounded(text, _stem(record["path"]))


def names_server_call(text, server):
    """True for `mcporter call <server>.<tool>`: a command that runs mcporter and has a word that starts with the server
    name, a dot and a tool name. A file called `<server>.md` is not such a call, and neither is a command without mcporter."""
    if not has_program_word(text, "mcporter"):
        return False
    prefix = server + "."
    for word in text.split():
        word = word.strip("'\"")
        if word.startswith(prefix) and len(word) > len(prefix) and (word[len(prefix)].isalpha() or word[len(prefix)] == "_"):
            return True
    return False


def is_memory_call(call):
    if call.get("server") == "ai-memory":
        return True
    text = command_text(call)
    return text is not None and (has_program_word(text, "ai-memory") or names_server_call(text, "ai-memory"))


def memory_check(calls, records):
    """R9 at grading: a hit counts only when a succeeded ai-memory call (MCP or CLI) of the attempt returns a result that
    resolves to a record frozen before SINCE, so a later arm's own session page never counts. A call with no ledger record
    has no state: when it could show a hit its outcome is unknown (call_state_unknown), never a miss."""
    unobservable = stateless = False
    for call in calls:
        if not is_memory_call(call):
            continue
        text = call["result_text"]
        if call["state"] is None:
            stateless = stateless or text is None or any(resolves_to_record(text, record) for record in records)
            continue
        if call["state"] != "succeeded":
            continue
        if text is None:
            unobservable = True
        elif any(resolves_to_record(text, record) for record in records):
            return fc.ok()
    if unobservable:
        return fc.unknown("result_unobservable")
    if stateless:
        return fc.unknown("call_state_unknown")
    return fc.fail("no_historical_hit")


def recovery_check(calls, digest, readings):
    """R2-17: the recovery is shown by a succeeded call of the child whose result, persisted output followed, carries the
    key digest. A failed or absent recovery fails (decided) or is unknown (alternative); a call with no ledger record that
    carries the digest is unknown under both readings, because its state was never observed."""
    stateless = False
    for call in calls:
        if isinstance(call["result_text"], str) and digest in call["result_text"].lower():
            if call["state"] == "succeeded":
                return fc.ok()
            stateless = stateless or call["state"] is None
    if stateless:
        return fc.unknown("call_state_unknown")
    return fc.fail("recovery_missing") if readings["R2-17"] == "fail" else fc.unknown("recovery_missing")


# ---- M12 (R7) -----------------------------------------------------------------------------------------------------

SERVER_BLOCK_HEADERS = ("MCP Server Instructions", "The following MCP servers have provided instructions")
DENYLISTED_ATTACHMENTS = ("instructions", "deferred_tools_delta", "skill_listing", "hook_additional_context")
READ_TOOL_NAMES = ("Read", "Glob", "Grep")
QUIET_TOOL_NAMES = ("StructuredOutput",)


def first_user_text(rows):
    for row in rows:
        if row.get("type") == "user" and not row.get("isMeta"):
            text = row_text(row)
            if text:
                return text
    return ""


def _attachments_before_answer(rows):
    found = []
    for row in rows:
        if row.get("type") == "assistant":
            break
        if row.get("type") == "attachment" and isinstance(row.get("attachment"), dict):
            found.append(str(row["attachment"].get("type")))
    return found


def first_prompt_ok(rows, config, readings):
    """R7 test 3: the first user message carries no routing marker, server-instructions header or instruction-file anchor
    line, and every attachment before the first answer is of a frozen kind (allowlist), or of no denylisted kind."""
    text = first_user_text(rows)
    if config["marker"] in text or any(header in text for header in SERVER_BLOCK_HEADERS):
        return False
    lines = {line.strip() for line in text.split("\n")}
    if any(anchor.strip() in lines for anchor in config["anchors"] if anchor.strip()):
        return False
    kinds = _attachments_before_answer(rows)
    if readings["R2-12"] == "denylist":
        return not any(kind in DENYLISTED_ATTACHMENTS for kind in kinds)
    return all(kind in config["attachment_allowlist"] for kind in kinds)


def _marker_ok(rows, config, readings):
    marker = config["marker"]
    if readings["R2-14"] == "first_prompt_and_hook_context":
        if marker in first_user_text(rows):
            return False
        return not any(row.get("type") == "attachment" and isinstance(row.get("attachment"), dict)
                       and row["attachment"].get("type") == "hook_additional_context"
                       and marker in json.dumps(row["attachment"]) for row in rows)
    for row in rows:
        if row.get("type") == "user" and marker in json.dumps(row.get("message") or {}):
            return False
        if row.get("type") == "attachment" and marker in json.dumps(row.get("attachment") or {}):
            return False
    return True


def _calls_ok(rows, readings):
    for use in tool_uses(rows):
        name = use["name"]
        if readings["R2-11"] == "mcp_skill_bash_only":
            if name.startswith("mcp__") or name in ("Skill", "Bash"):
                return False
        elif name not in READ_TOOL_NAMES and name not in QUIET_TOOL_NAMES:
            return False
    return True


def _memory_index_status(rows, config, readings):
    audit = sibling("sota-convergence", "transcript_audit")
    cwd = next((row.get("cwd") for row in rows if isinstance(row.get("cwd"), str)), config.get("cwd"))
    status = "pass"
    for use in tool_uses(rows):
        if use["name"] not in READ_TOOL_NAMES:
            continue
        reads, problems = audit._call_reads(use["name"], use["input"], cwd)
        if problems:
            status = "unknown" if status == "pass" else status
            continue
        for path in reads:
            if readings["R2-13"] == "memory_index_roots":
                if audit._within(path, config["memory_roots"]):
                    return "fail"
            elif not audit._within(path, config["packet_roots"]):
                return "fail"
    return status


def m12_attempt(rows, config, readings, hook_rows):
    """R7: the five tests of one completed blind attempt. Clean iff all pass, contaminated iff any fails, else unknown."""
    tests = {"calls": "pass" if _calls_ok(rows, readings) else "fail",
             "injection": "unknown" if hook_rows is None else "pass" if hook_rows == 0 else "fail",
             "first_prompt": "pass" if first_prompt_ok(rows, config, readings) else "fail",
             "memory_index": _memory_index_status(rows, config, readings),
             "marker": "pass" if _marker_ok(rows, config, readings) else "fail"}
    values = set(tests.values())
    clean = "contaminated" if "fail" in values else "unknown" if "unknown" in values else "clean"
    return {"clean": clean, "tests": tests}


def m12_hook_source(agent_id, label, join_row, children):
    """R7 test 2 for a Workflow child: identity, then U4's join-ledger row (its agent id), then U2's run-mode child with
    the same agent id and label; hook_context.inserted and by_hook['PreToolUse:Read'] come from that child."""
    unknown = {"status": "unknown", "reason": "m12_join", "hook_rows": None, "read_rows": None}
    if join_row is None or join_row.get("agent_id") != agent_id:
        return unknown
    child = next((item for item in children if item.get("agent_id") == agent_id and item.get("label") == label), None)
    if child is None:
        return unknown
    hook = ((child.get("lanes") or {}).get("measurement") or {}).get("hook_context")
    if not isinstance(hook, dict) or not isinstance(hook.get("inserted"), int):
        return unknown
    by_hook = hook.get("by_hook") if isinstance(hook.get("by_hook"), dict) else {}
    return {"status": "ok", "reason": None, "hook_rows": hook["inserted"], "read_rows": by_hook.get("PreToolUse:Read", 0)}


M12_FIELDS = {"blind_workflow": ("rows", "hook_rows", "mcp_skill_bash_calls"), "positive_control": ("rows", "pretooluse_read_rows"),
              "strict_process": ("rows", "hook_rows", "mcp_skill_bash_calls")}


def m12_cross_check(mine, theirs):
    """R7: U9's per-attempt sums must equal U4's m12_inputs; a difference stops the grade, naming the kind and field."""
    for kind in sorted(M12_FIELDS):
        left, right = mine.get(kind) or {}, theirs.get(kind) or {}
        for field in M12_FIELDS[kind]:
            if field in left and field in right and left[field] != right[field]:
                raise fc.Refusal("E_M12_INPUTS", kind=kind, field=field)


def m12_status(blind, positive_read_rows):
    """M12 (R7): incomplete when the positive control shows no Read row; fail when a blind task lacks a clean completed
    verdict on the lower bound (the correctness of the answer plays no part: `blind` is {task: {clean, contaminated,
    unknown}} counts of completed attempts); otherwise pass. An unknown cleanliness only sets the sensitivity flag."""
    if positive_read_rows == 0:
        return {"status": "incomplete", "reason": "failed_positive_control", "sensitive": False}
    if positive_read_rows is None:
        return {"status": "unknown", "reason": "control_rows_unobserved", "sensitive": False}
    if any(item["clean"] < 1 for item in blind.values()):
        return {"status": "fail", "reason": "blind_task_without_clean_verdict",
                "sensitive": all(item["clean"] + item["unknown"] >= 1 for item in blind.values())}
    return {"status": "pass", "reason": None, "sensitive": False}


# ---- The Node bridge to the kernel (U2's measureTranscript today; U1 and U4 names when they merge) ----------------

BRIDGE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "node_bridge.mjs")


def bridge(request):
    """One JSON request to node_bridge.mjs, one JSON answer. The bridge never reads anything but the named file."""
    import subprocess
    try:
        done = subprocess.run(["node", BRIDGE], input=json.dumps(request), capture_output=True, text=True, timeout=300,
                              env=fc.minimal_env())
    except (OSError, subprocess.TimeoutExpired):
        raise fc.Refusal("E_TOOL", tool="node", reason="run") from None
    if done.returncode != 0:
        raise fc.Refusal("E_TOOL", tool="node", reason="exit")
    try:
        return json.loads(done.stdout)
    except ValueError:
        raise fc.Refusal("E_TOOL", tool="node", reason="output") from None


def kernel_hook_context(path):
    """U2's hook_context of one transcript: {inserted, by_hook} from the kernel's own measureTranscript."""
    answer = bridge({"op": "measure", "path": str(path)})
    hook = answer.get("hook_context") or {}
    return {"inserted": hook.get("inserted"), "by_hook": hook.get("by_hook") or {}}


# ---- M7 (R14) and the toon CLI's merged streams (correction 5) ----------------------------------------------------

STATUS_MARKS = "●✔✖"  # the CLI's info, success and error marks


def strip_ansi(text):
    """Remove ESC [ ... final-byte colour sequences, in one linear pass."""
    out, index = [], 0
    while index < len(text):
        if text[index] == "\x1b" and text[index + 1:index + 2] == "[":
            index += 2
            while index < len(text) and not ("@" <= text[index] <= "~"):
                index += 1
            index += 1
            continue
        out.append(text[index])
        index += 1
    return "".join(out)


def is_status_line(line):
    """The three status lines `toon --stats` writes to stderr (toon CLI 4.1.1, src/log.ts and the encode path): the token
    estimates, the savings and, with -o, the encoded-file line. Recognised by their documented shape only."""
    plain = strip_ansi(line).strip()
    if not plain or plain[0] not in STATUS_MARKS:
        return False
    body = plain[1:].strip()
    if body.startswith("Token estimates: ~") and " (JSON) → ~" in body and body.endswith(" (TOON)"):
        return True
    if body.startswith("Saved ~") and " tokens (" in body and body.endswith("%)"):
        return True
    return body.startswith("Encoded `") and "` → `" in body and body.endswith("`")


def drop_status_lines(text):
    return "\n".join(line for line in text.split("\n") if not is_status_line(line))


def isolate_toon_document(text):
    """Correction 5: the document of a merged toon result is the first contiguous block that decodes strictly, found after
    the status lines are dropped by their documented shape. {"status": "decoded" | "strict_decode" | "unparsed",
    "document", "value"}: strict_decode only when a candidate block was found, else unparsed."""
    cleaned = drop_status_lines(text)
    lines = cleaned.split("\n")
    found, index = False, 0
    while index < len(lines):
        line = lines[index]
        if fc.toon_header(line) and not line.lstrip().startswith("- "):
            rows, follow = [line], index + 1
            while follow < len(lines) and lines[follow][:1] in (" ", "\t") and lines[follow].strip():
                rows.append(lines[follow])
                follow += 1
            found = True
            block = "\n".join(rows)
            try:
                return {"status": "decoded", "document": block, "value": fc.decode_candidate(block)}
            except fc.DecodeError:
                index = follow
                continue
        index += 1
    whole = cleaned.strip()
    if whole and whole[:1] not in "[{":
        try:
            value = fc.toon_decode(whole)
        except fc.DecodeError:
            return {"status": "strict_decode" if found else "unparsed", "document": None, "value": None}
        if isinstance(value, (list, dict)):
            return {"status": "decoded", "document": whole, "value": value}
    return {"status": "strict_decode" if found else "unparsed", "document": None, "value": None}


def uniform_flat(value, minimum):
    """U2's uniform_flat rule: an array of at least `minimum` objects with one key set and only scalar values."""
    if not isinstance(value, list) or len(value) < minimum or not all(isinstance(item, dict) for item in value):
        return False
    keys = list(value[0])
    return all(list(item) == keys and all(not isinstance(field, (list, dict)) for field in item.values()) for item in value)


def heredoc_bodies(command):
    """The bodies of the heredocs of a shell text (`<<TAG`, `<<'TAG'`, `<<-TAG`), read as data and never run."""
    lines, bodies, index = command.split("\n"), [], 0
    while index < len(lines):
        at = lines[index].find("<<")
        if at >= 0 and lines[index][at:at + 3] != "<<<":
            words = lines[index][at + 2:].lstrip("-").split()
            tag = words[0].strip("'\"") if words else ""
            if tag:
                body, index = [], index + 1
                while index < len(lines) and lines[index].strip() != tag:
                    body.append(lines[index])
                    index += 1
                bodies.append("\n".join(body))
        index += 1
    return bodies


def _records_equal(value, records, readings):
    reasons, order_bad = fc.compare_values(value, records, readings["R2-02"] == "ordered")
    return not reasons and not order_bad


def _document_records(value, readings):
    """The records list of a decoded document under the R2-01 reading (a root array; a single-key wrapper where the reading
    accepts one), or None: the decided reading calls a wrapper a shape failure, the alternative unwraps it."""
    return fc.payload_records(value, readings["R2-01"])[0]


def _answer_toon_items(ans, records, readings):
    items = []
    for candidate in fc.payload_candidates(ans):
        first = next((line for line in candidate["text"].split("\n") if line.strip()), "")
        if not fc.toon_header(first) or first.lstrip().startswith("- "):
            continue
        if records is None:
            if readings["R2-16"] == "unknown_in_denominator":
                items.append({"source": "answer", "status": "unknown"})
            continue
        try:
            value = fc.decode_candidate(candidate["text"])
        except fc.DecodeError:
            items.append({"source": "answer", "status": "unequal"})
            continue
        shaped = _document_records(value, readings)
        items.append({"source": "answer",
                      "status": "equal" if shaped is not None and _records_equal(shaped, records, readings) else "unequal"})
    return items


def _answer_payload_shapes(ans, readings):
    """[(is_toon, records or None)] for every payload candidate of the answer that strictly decodes, JSON or TOON."""
    shapes = []
    for candidate in fc.payload_candidates(ans):
        text = candidate["text"]
        if not fc.looks_like_payload(text):
            continue
        try:
            value = fc.decode_candidate(text)
        except fc.DecodeError:
            continue
        first = next((line for line in text.split("\n") if line.strip()), "")
        shapes.append((bool(fc.toon_header(first)) and not first.lstrip().startswith("- "), _document_records(value, readings)))
    return shapes


def toon_facts(calls, ans, key, readings, seeded=True):
    """R14 for one completed arm-B attempt: the CLI encode, the ineligible encodes and every strict round trip (each answer
    payload against the frozen original, each observable child-side decode). A seeded attempt encodes when a succeeded toon
    CLI call's document strictly decodes to the seeded array; any other attempt (a natural payload) encodes when a document
    is an eligible flat array of at least five records. The R2-01 reading decides whether a single-key wrapper around such
    an array is a shape failure (an ineligible encode) or the array itself. A call with no ledger record has no state: it can
    only make the outcome unknown (call_state_unknown), and counts on the lower bound as ineligible when it cannot be
    proven eligible."""
    records = key.get("records") if isinstance(key, dict) else None
    facts = {"encode": "not_encoded", "encode_reason": None, "ineligible": 0, "ineligible_unknown": 0, "roundtrip": [],
             "cli_encodes": 0, "has_payload": False}
    encoded, unknown, eligible_encodes = False, None, 0
    for call in calls:
        text = command_text(call)
        if text is None or call["state"] not in ("succeeded", None) or not has_program_word(text, "toon"):
            continue
        stateless = call["state"] is None
        words = set(text.split())
        if words & {"-d", "--decode"}:
            bodies = heredoc_bodies(text)
            if not bodies:
                continue
            item = {"source": "child_decode", "status": "unknown"}
            try:
                expected = fc.toon_decode(bodies[0].strip())
            except fc.DecodeError:
                item["status"] = "unknown" if stateless else "unequal"
            else:
                try:
                    observed = fc.json_decode((call["result_text"] or "").strip())
                except fc.DecodeError:
                    observed = None
                if observed is not None and not stateless:
                    reasons, order_bad = fc.compare_values(observed, expected, readings["R2-02"] == "ordered")
                    item["status"] = "equal" if not reasons and not order_bad else "unequal"
            facts["roundtrip"].append(item)
            continue
        facts["cli_encodes"] += 1
        if any(word in ("-o", "--output") or word.startswith("--output=") for word in words):
            unknown = unknown or "output_file"
            continue
        isolated = isolate_toon_document(call["result_text"] or "")
        if isolated["status"] != "decoded":
            facts["ineligible_unknown"] += 1
            unknown = unknown or isolated["status"]
            continue
        shaped = _document_records(isolated["value"], readings)
        eligible = shaped is not None and uniform_flat(shaped, 5)
        matches = eligible if not seeded else records is not None and shaped is not None and _records_equal(shaped, records, readings)
        if matches:
            if stateless:
                unknown = unknown or "call_state_unknown"
            else:
                encoded = True
                eligible_encodes += 1 if eligible else 0
        elif not eligible:
            facts["ineligible_unknown" if stateless else "ineligible"] += 1
        elif not stateless:
            eligible_encodes += 1
    items = _answer_toon_items(ans, records, readings)
    facts["roundtrip"] += items
    answer_eligible = [is_toon for is_toon, shaped in _answer_payload_shapes(ans, readings)
                       if shaped is not None and uniform_flat(shaped, 5)]
    facts["has_payload"] = eligible_encodes > 0 or bool(answer_eligible)
    if not encoded and readings["R2-15"] == "any_toon_form":
        encoded = any(item["status"] == "equal" for item in items) if seeded else any(answer_eligible)
    facts["encode"] = "encoded" if encoded else "unknown" if unknown else "not_encoded"
    facts["encode_reason"] = None if encoded else unknown
    return facts


M7_DEFAULTS = {"minimum_flat_array_records": 5, "minimum_seeded_payloads": 5, "seeded_encode_rate_eq": 1,
               "strict_roundtrip_rate_eq": 1, "ineligible_encodes_eq": 0, "natural_encode_rate_gte": 0.8,
               "natural_required": False, "natural_NA_below": 5}


def m7(attempts, criteria, readings):
    """R14: the seeded encode rate, the strict round-trip rate and the ineligible-encode count of completed arm-B
    attempts, on the lower and upper bounds. Fewer than the minimum of seeded payloads is a fail with its reason (B1: no
    new incomplete); natural payloads are optional and never gate."""
    criteria = dict(M7_DEFAULTS, **(criteria or {}))
    seeded = [item for item in attempts if item.get("seeded")]
    natural = [item for item in attempts if not item.get("seeded") and item.get("has_payload")]
    payloads = len(seeded)
    encoded_lower = sum(1 for item in seeded if item["encode"] == "encoded")
    encoded_upper = sum(1 for item in seeded if item["encode"] in ("encoded", "unknown"))
    trips = [trip for item in attempts for trip in item["roundtrip"]]
    equal = sum(1 for trip in trips if trip["status"] == "equal")
    unknown = sum(1 for trip in trips if trip["status"] == "unknown")
    ineligible_upper = sum(item["ineligible"] for item in attempts)
    ineligible_lower = ineligible_upper + sum(item["ineligible_unknown"] for item in attempts)
    rate_lower, rate_upper = rate(encoded_lower, payloads), rate(encoded_upper, payloads)
    trip_lower, trip_upper = rate(equal, len(trips)), rate(equal + unknown, len(trips))

    def failures(encode_rate, trip_rate, ineligible):
        reasons = []
        if payloads < criteria["minimum_seeded_payloads"]:
            reasons.append("seeded_payloads_below_minimum")
        if encode_rate != criteria["seeded_encode_rate_eq"]:
            reasons.append("seeded_encode_rate")
        if trip_rate != criteria["strict_roundtrip_rate_eq"]:
            reasons.append("strict_roundtrip")
        if ineligible != criteria["ineligible_encodes_eq"]:
            reasons.append("ineligible_encodes")
        return reasons
    reasons = failures(rate_lower, trip_lower, ineligible_lower)
    upper = failures(rate_upper, trip_upper, ineligible_upper)
    natural_encoded = sum(1 for item in natural if item["encode"] == "encoded")
    natural_status = "not_applicable" if len(natural) < criteria["natural_NA_below"] else \
        "pass" if (rate(natural_encoded, len(natural)) or 0) >= criteria["natural_encode_rate_gte"] else "fail"
    return {"seeded_payloads": payloads, "encoded_lower": encoded_lower, "encoded_upper": encoded_upper,
            "seeded_encode_rate_lower": rate_lower, "seeded_encode_rate_upper": rate_upper,
            "roundtrip": {"checked": len(trips), "equal": equal, "unknown": unknown, "rate_lower": trip_lower,
                          "rate_upper": trip_upper},
            "ineligible_encodes_lower": ineligible_lower, "ineligible_encodes_upper": ineligible_upper,
            "natural": {"payloads": len(natural), "encoded": natural_encoded, "status": natural_status},
            "status": "fail" if reasons else "pass", "reasons": reasons, "sensitive": bool(reasons) and not upper}


# ---- T14 (R11) -------------------------------------------------------------------------------------------------

_ID_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.:-")


def reported_identities(text, run_token):
    """Tokens of the answer that start with the run token and a dot: the identities it reports (trailing dots trimmed)."""
    found, start, prefix = [], 0, run_token + "."
    while True:
        index = text.find(prefix, start)
        if index < 0:
            return found
        end = index
        while end < len(text) and text[end] in _ID_CHARS:
            end += 1
        token = text[index:end].rstrip(".:-")
        if (index == 0 or text[index - 1] not in _ID_CHARS) and token not in found:
            found.append(token)
        start = max(end, index + 1)


def t14_check(text, *, run_token, starts, q, background_pending, survivors, readings, q_status=None, survival_observed=True):
    """R11 (U9-D21): the reported sessions must be rows of the private table that started before the child's first
    archive query q; the counts must agree with the list; an owned process must not survive (R2-20). `q_status` is
    "unobserved" when the child did query the archive but nothing timestamped shows when (unknown, not a missing query);
    `survival_observed` is false when neither a process listing nor a resolved lifetime could show survival."""
    q_seconds = iso_seconds(q) if q is not None else None
    reasons, soft = set(), set()
    if q_seconds is None:
        if q is None and q_status != "unobserved":
            return fc.fail("no_archive_query")
        soft.add("archive_query_unobserved")
    reported = reported_identities(text, run_token)
    expected = [] if q_seconds is None else [name for name, start in starts.items()
                                             if start is not None and iso_seconds(start) is not None and iso_seconds(start) < q_seconds]
    for identity in reported:
        if identity not in starts:
            reasons.add("session_outside_table")
        elif q_seconds is None:
            continue
        elif starts[identity] is None or iso_seconds(starts[identity]) is None:
            soft.add("start_unresolved")
        elif iso_seconds(starts[identity]) >= q_seconds:
            reasons.add("session_not_before_query")
    if q_seconds is not None and readings["R2-19"] == "equal" and [name for name in expected if name not in reported]:
        reasons.add("session_missing")
    detail = {"reported": len(reported), "expected": len(expected) if q_seconds is not None else None}  # the descriptive ratio (R11)
    plain = text
    for identity in reported:
        plain = plain.replace(identity, "ID")
    counts = fc.count_before_noun(fc.normalize(plain), ("sessions", "session", "matches", "match", "identities"))
    if counts and len(reported) not in counts:
        # a count that disagrees with the listed identities is wrong; a count with no identity the grader can read cannot be checked
        (reasons if reported else soft).add("count_mismatch" if reported else "unparsed")
    if not reported and not counts:
        soft.add("unparsed")
    if background_pending or survivors:
        (reasons if readings["R2-20"] == "fail" else soft).add("owned_process_survives")
    elif not survival_observed:
        soft.add("survival_unobserved")
    if reasons:
        return fc.fail(*reasons, **detail)
    return fc.unknown(*soft, **detail) if soft else fc.ok(**detail)


_WRAPPER_WORDS = frozenset({"nohup", "setsid", "env", "command", "exec", "time", "nice", "sudo", "stdbuf", "ionice", "rtk",
                            "proxy"})


def _is_assignment(word):
    name, sep, _ = word.partition("=")
    return bool(sep) and bool(name) and (name[0].isalpha() or name[0] == "_") and all(char.isalnum() or char == "_" for char in name)


def _shell_commands(text):
    """Simple commands of a shell text as word lists: quotes kept together, separators split, heredoc bodies and
    comments dropped. A coarse linear reading, used only to see which programs a child started."""
    lines, kept, index = text.split("\n"), [], 0
    while index < len(lines):
        kept.append(lines[index])
        at = lines[index].find("<<")
        if at >= 0 and lines[index][at:at + 3] != "<<<":
            words = lines[index][at + 2:].lstrip("-").split()
            tag = words[0].strip("'\"") if words else ""
            if tag:
                index += 1
                while index < len(lines) and lines[index].strip() != tag:
                    index += 1
        index += 1
    source = "\n".join(kept)
    commands, words, word, quote, position = [], [], [], None, 0

    def end_word():
        if word:
            words.append("".join(word))
            word.clear()

    def end_command():
        end_word()
        if words:
            commands.append(list(words))
            words.clear()
    while position < len(source):
        char = source[position]
        if quote:
            if char == quote:
                quote = None
            else:
                word.append(char)
        elif char in "'\"":
            quote = char
        elif char == "\\" and position + 1 < len(source):
            word.append(source[position + 1])
            position += 1
        elif char == "#" and not word:
            while position < len(source) and source[position] != "\n":
                position += 1
            continue
        elif char in " \t":
            end_word()
        elif char in ";\n|(){}":
            end_command()
        elif char == "&":
            before = source[position - 1] if position else " "
            after = source[position + 1] if position + 1 < len(source) else " "
            if before in "<>" or after == ">":
                word.append(char)
            else:
                end_command()
        else:
            word.append(char)
        position += 1
    end_command()
    return commands


def _program_of(words):
    index = 0
    while index < len(words):
        word = words[index]
        digits = word.lstrip("0123456789")
        if digits[:1] in (">", "<"):
            index += 2 if digits in (">", ">>", "<", "<<") else 1
        elif _is_assignment(word) or word in _WRAPPER_WORDS:
            index += 1
        elif word == "timeout":
            index += 1
            while index < len(words) and (words[index].startswith("-") or words[index][:1].isdigit()):
                index += 1
        else:
            return word.rsplit("/", 1)[-1]
    return None


def command_programs(texts):
    """The program names a child's shell texts start (wrappers, assignments and redirections skipped)."""
    programs = set()
    for text in texts:
        for words in _shell_commands(text):
            program = _program_of(words)
            if program:
                programs.add(program)
    return programs


def owned_survivors(processes, lifetime, programs):
    """R2-20 with the ownership filter: a process alive at the post-arm capture is owned when it started within the
    child's lifetime and its name is a program the child ran, or when its parent is an owned survivor. Processes that
    started inside the lifetime with no proven owner are counted apart and never fail the child."""
    first, last = iso_seconds(lifetime[0]), iso_seconds(lifetime[1])
    inside = [item for item in processes if iso_seconds(item.get("start")) is not None
              and first <= iso_seconds(item["start"]) <= last]
    owned = [item for item in inside if item.get("comm") in programs]
    known = {item.get("pid") for item in owned}
    changed = True
    while changed:
        changed = False
        for item in processes:
            if item not in owned and item.get("ppid") in known and item.get("pid") is not None:
                owned.append(item)
                known.add(item["pid"])
                changed = True
    return {"owned": sorted(owned, key=lambda item: (item["start"], item.get("pid") or 0)),
            "unattributed": sum(1 for item in inside if item not in owned)}


def _command_words(command):
    """A command field of a rollout item: a list of words or one string, as one text."""
    if isinstance(command, list):
        return " ".join(str(word) for word in command)
    return command if isinstance(command, str) else ""


def _rollout_call(record):
    """(texts, mcp server) of the call a rollout record issues or completes: a function call's arguments, a custom tool
    call's input, a local shell action's command, an item_completed CommandExecution's command, or an MCP call's server."""
    payload = _payload(record)
    texts, server = [], None
    if record.get("type") == "response_item":
        kind = payload.get("type")
        if kind == "function_call":
            texts.append(payload.get("arguments") if isinstance(payload.get("arguments"), str) else "")
            server = _mcp_server(payload.get("name"))
        elif kind == "custom_tool_call":
            texts.append(payload.get("input") if isinstance(payload.get("input"), str) else "")
        elif kind == "local_shell_call":
            action = payload.get("action") if isinstance(payload.get("action"), dict) else {}
            texts.append(_command_words(action.get("command")))
    elif record.get("type") == "event_msg" and payload.get("type") == "item_completed":
        item = payload.get("item") if isinstance(payload.get("item"), dict) else {}
        if item.get("type") == "CommandExecution":
            texts.append(_command_words(item.get("command")))
        elif item.get("type") == "McpToolCall":
            server = item.get("server") if isinstance(item.get("server"), str) else None
    return texts, server


def names_archive_query(texts, server):
    """The one detector of an archive query for both families: the whole word agentsview in a command or code text (also in
    ctx_execute shell code), or a call to the agentsview MCP server."""
    return server == "agentsview" or any(fc._has_agentsview(text) for text in texts)


def codex_archive_query_time(records):
    """q for a Codex child (R11): the timestamp of the first rollout record that issues a call naming agentsview. Exec
    events carry no timestamps, so the timestamped rollout copy that U10 retains is the source. unknown(no_query) when no
    record names it; unknown(archive_query_unobserved) when the first such record has no readable timestamp."""
    for record in records:
        texts, server = _rollout_call(record)
        if names_archive_query(texts, server):
            when = record.get("timestamp")
            return fc.ok(q=when) if iso_seconds(when) is not None else fc.unknown("archive_query_unobserved")
    return fc.unknown("no_query")


def t14_facts(*, family, rows, calls, attempt, post, pending, rollout):
    """The R11 facts of one completed T14 attempt: the query time and how it was observed, the pending background jobs, the
    owned processes still alive at the post-arm capture and whether survival could be observed at all. A Claude child's query
    time and lifetime come from its transcript; a Codex child's from the timestamped rollout copy, and without one a query
    the events show is unobserved (the time is unknown) rather than absent."""
    if family == "claude":
        found = fc.archive_query_time(rows or [])
        lifetime = (attempt.get("start"), attempt.get("end"))
    elif rollout and rollout.get("status") == "ok":
        found = codex_archive_query_time(rollout["records"])
        lifetime = (first_timestamp(rollout["records"]), last_timestamp(rollout["records"]))
    else:
        named = any(names_archive_query([code_text(call)], call.get("server")) for call in calls)
        found = fc.unknown("archive_query_unobserved" if named else "no_query")
        lifetime = (attempt.get("start"), attempt.get("end"))
    q_status = "observed" if found.status == "pass" else "unobserved" if "archive_query_unobserved" in found.reasons else "none"
    observed = post.get("processes") is not None and all(lifetime)
    owned = {"owned": [], "unattributed": 0}
    if observed:
        owned = owned_survivors(post["processes"], lifetime, command_programs([code_text(call) for call in calls]))
    return {"q": found.detail.get("q") if found.status == "pass" else None, "q_status": q_status,
            "background_pending": pending, "survivors": [{"comm": item["comm"], "start": item["start"]} for item in owned["owned"]],
            "unattributed": owned["unattributed"], "survival_observed": observed}


# ---- Tree drift (R13) and the builder (T31) from the post-arm capture --------------------------------------------

DRIFT_TEMPLATES = ("T1", "T3", "T5", "T8", "T10", "T26")
DRIFT_SCOPES = ("scripts/", "tests/", "fixtures/", "docs/")


def drift_entries(entries):
    """The inventory entries inside a task's key scope (modified, deleted, untracked or ignored; never bytecode caches)."""
    return [entry for entry in entries if entry["path"].startswith(DRIFT_SCOPES) and not fc.is_bytecode_path(entry["path"].rstrip("/"))]


def apply_tree_drift(template, result, entries):
    """R13 baseline: a clean tracked tree at the freeze, so any in-scope entry in an arm's pre-arm inventory is drift. It
    turns that arm's FAIL of a scope-keyed template into unknown(tree_drift); passes and unknowns stay as they are."""
    if template in DRIFT_TEMPLATES and result.status == "fail" and drift_entries(entries):
        return fc.unknown("tree_drift")
    return result


def builder_observed_tree(rows):
    """The tree the child actually edited: the root of the fixtures/before.py path of its Edit and Write calls."""
    suffix = "/fixtures/before.py"
    roots = set()
    for use in tool_uses(rows):
        path = use["input"].get("file_path")
        if use["name"] in ("Edit", "Write", "MultiEdit", "NotebookEdit") and isinstance(path, str) and path.endswith(suffix):
            roots.add(path[:-len(suffix)])
    if not roots:
        return {"status": "missing"}
    if len(roots) > 1:
        return {"status": "conflict"}
    return {"status": "ok", "path": next(iter(roots))}


def grade_builder_capture(record, *, prepared_path, prepared_base, observed, exec_rev, after_bytes, key):
    """T31 from the post-arm capture: the same rules as the live-tree check, and the greeting runs on the key's own
    after.py bytes once the captured digest equals theirs (the captured text is lossy and never executed)."""
    if fc.sha256_hex(after_bytes) != key["after_sha256"]:
        return fc.unknown("input_hash")
    if observed["status"] == "missing":
        return fc.unknown("block_grading")
    if observed["status"] == "conflict" or os.path.realpath(observed["path"]) != os.path.realpath(prepared_path):
        return fc.unknown("conflicting_identity")
    if not (fc.is_hex(exec_rev, 40) and prepared_base == exec_rev and record.get("head") == prepared_base):
        return fc.unknown("block_grading")
    entries = [entry for entry in record.get("entries") or [] if not fc.is_bytecode_path(entry["path"].rstrip("/"))]
    reasons = set()
    if [entry for entry in entries if entry["path"] != "fixtures/before.py"]:
        reasons.add("extra_changes")
    if not any(entry["path"] == "fixtures/before.py" for entry in entries):
        reasons.add("empty_diff")
    if reasons:
        return fc.fail(*reasons)
    if record.get("before_sha256") != key["after_sha256"]:
        return fc.fail("bytes_differ")
    greeting = fc._isolated_greeting(after_bytes)
    if greeting != fc.GREETINGS:
        return fc.fail("greeting", greeting=greeting)
    return fc.ok(greeting=greeting)


# ---- Privacy (R22) ----------------------------------------------------------------------------------------------

def all_strings(value):
    """Every string of a JSON document, keys included."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from all_strings(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from all_strings(item)


def _has_uuid(text):
    for index in range(len(text) - 35):
        if text[index + 8] == "-" and text[index + 13] == "-" and text[index + 18] == "-" and text[index + 23] == "-":
            parts = (text[index:index + 8], text[index + 9:index + 13], text[index + 14:index + 18],
                     text[index + 19:index + 23], text[index + 24:index + 36])
            if all(all(char in "0123456789abcdefABCDEF" for char in part) for part in parts):
                return True
    return False


def _has_drive_prefix(text):
    for index in range(1, len(text) - 1):
        if text[index] == ":" and text[index + 1] in "\\/" and text[index - 1].isalpha() \
                and (index == 1 or not text[index - 2].isalnum()):
            return True
    return False


def has_private_shape(text):
    """A UUID, a tool_use or call id prefix, a leading '/' or ' /', a drive prefix, or the project-slug shape of a home path."""
    if text.startswith("/") or " /" in text or "toolu_" in text or "call_" in text:
        return True
    if _has_uuid(text) or _has_drive_prefix(text):
        return True
    for marker in ("-home-", "-Users-"):
        index = text.find(marker)
        while index >= 0:
            rest = text[index + len(marker):]
            if "-" in rest[1:] and rest[:1].isalnum():
                return True
            index = text.find(marker, index + 1)
    return False


def assert_no_private(document, values):
    """R22: refuse (E_PRIVACY, a generic message) when any string of the document holds a gathered value of eight or more
    characters or has a private shape. Returns how many gathered values were checked."""
    checked = sorted({value for value in values if isinstance(value, str) and len(value) >= 8})
    strings = list(all_strings(document))
    joined = "\0".join(strings)
    if any(value in joined for value in checked) or any(has_private_shape(text) for text in strings):
        raise fc.Refusal("E_PRIVACY")
    return len(checked)


# ---- Identity (R19): the table, its validation and the launch records --------------------------------------------

IDENTITY_SCHEMA = "token-e2e-identity/1"
TEAM_ACTOR = "team_teammate"
ACTORS_BY_DISPATCH = {"workflow": ("workflow_child",), "agent-tool": ("agent_child",), "exec": ("codex_exec",),
                      "sub-agent": ("codex_subagent",), "main": ("main",)}
GRAPHED_LOCATORS = {"workflow_child": ("workflow_dir",), "agent_child": ("session_dir", "tool_use_id"),
                    "codex_exec": ("thread_id", "events_file"), "codex_subagent": ("parent_thread_id", "parent_events_file")}
_RUN_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")


def parse_identity(identity):
    """`<run>.<arm>.<task>.<attempt>`: exactly four non-empty fields and an attempt without a leading zero, or None."""
    fields = identity.split(".") if isinstance(identity, str) else []
    if len(fields) != 4 or not all(fields):
        return None
    attempt = fields[3]
    if not attempt.isdigit() or attempt[0] == "0" or len(attempt) > 6:
        return None
    return {"run": fields[0], "arm": fields[1], "task": fields[2], "attempt": int(attempt)}


def _invalid(code, **fields):
    return fc.Refusal("E_IDENTITY_INVALID", code=code, **fields)


def validate_identity_table(table, tasks):
    """The local twin of U4's R5 validation, with arm-T rows accepted as reported-only (U9-D15). A row that breaks a rule
    raises E_IDENTITY_INVALID code=E_ROW row=<i> field=<name>; the value is never printed."""
    if not isinstance(table, dict) or table.get("schema") != IDENTITY_SCHEMA:
        raise _invalid("E_TABLE", field="schema")
    run = table.get("run")
    if not isinstance(run, str) or not 8 <= len(run) <= 64 or any(char not in _RUN_CHARS for char in run):
        raise _invalid("E_TABLE", field="run")
    if not isinstance(table.get("rows"), list):
        raise _invalid("E_TABLE", field="rows")
    seen = set()
    for number, row in enumerate(table["rows"]):
        def refuse(field):
            return _invalid("E_ROW", row=number, field=field)
        if not isinstance(row, dict):
            raise refuse("row")
        parsed = parse_identity(row.get("identity"))
        if parsed is None:
            raise refuse("identity")
        if parsed["run"] != run:
            raise refuse("run")
        task = tasks.get(parsed["task"])
        if task is None:
            raise refuse("task")
        arm, actor = parsed["arm"], row.get("actor")
        if arm == "T":
            if task["family"] != "claude":
                raise refuse("arm")
            allowed = (TEAM_ACTOR,)
        else:
            if arm not in fc.FAMILY_ARMS[task["family"]] or arm not in task["arms"]:
                raise refuse("arm")
            allowed = ACTORS_BY_DISPATCH.get(task["dispatch"], ()) + (("strict_process",) if task["strict_repeat"] else ())
        if actor not in allowed:
            raise refuse("actor")
        if (row["identity"], actor) in seen:
            raise refuse("duplicate")
        seen.add((row["identity"], actor))
        excluded = arm == "T" or "blind" in task["lane_tags"] or task["opportunity"] != "organic" or actor in ("main", "strict_process")
        needed = GRAPHED_LOCATORS.get(actor)
        if needed and not excluded:
            names = needed if actor in ("workflow_child", "agent_child") else None
            if names is not None and any(not isinstance(row.get(name), str) or not row[name] for name in names):
                raise refuse(names[0])
            if names is None and not any(isinstance(row.get(name), str) and row[name] for name in needed):
                raise refuse(needed[0])


def validator_state(answer):
    """The identity command's reading of the bridge's validate_identity answer: "absent" (the sibling validator has not
    merged), "agrees", "unchecked" (the validator could not run: ok is null, which is never a refusal), or a refusal that
    carries the validator's own E_* code when it rejected the table."""
    if not answer.get("available"):
        return "absent"
    if answer.get("ok") is True:
        return "agrees"
    if answer.get("ok") is False:
        raise fc.Refusal("E_IDENTITY_INVALID", code=str(answer.get("code") or "E_ROW"))
    return "unchecked"


def session_transcript(claude_root, session_id):
    """`<CLAUDE_ROOT>/<project slug>/<session id>.jsonl`, or None: the session id is unique, the slug is not guessed."""
    if not isinstance(session_id, str) or not session_id or "/" in session_id or session_id.startswith("."):
        return None
    try:
        slugs = sorted(os.listdir(claude_root))
    except OSError:
        return None
    found = [os.path.join(claude_root, slug, session_id + ".jsonl") for slug in slugs
             if os.path.isfile(os.path.join(claude_root, slug, session_id + ".jsonl"))]
    return found[0] if len(found) == 1 else None


def session_directory(claude_root, session_id):
    """`<CLAUDE_ROOT>/<project slug>/<session id>/` (the directory a session's children and tool results live in), or None."""
    if not isinstance(session_id, str) or not session_id or "/" in session_id or session_id.startswith("."):
        return None
    try:
        slugs = sorted(os.listdir(claude_root))
    except OSError:
        return None
    found = [os.path.join(claude_root, slug, session_id) for slug in slugs
             if os.path.isdir(os.path.join(claude_root, slug, session_id))]
    return found[0] if len(found) == 1 else None


def journal_dirs(claude_root):
    """Every Workflow directory (`.../subagents/workflows/<run>` holding journal.jsonl) below CLAUDE_ROOT, sorted."""
    found = []
    for base, dirs, files in os.walk(claude_root):
        dirs.sort()
        if "journal.jsonl" in files and os.path.basename(os.path.dirname(base)) == "workflows" \
                and os.path.basename(os.path.dirname(os.path.dirname(base))) == "subagents":
            found.append(base)
    return found


def build_identity_table(spec, bindings, token, launches, codex_document):
    """R19 identity: Claude Workflow rows from the started labels of the journals under CLAUDE_ROOT (run-token hash
    match), the other Claude rows from the launch records, Codex rows merged from U10's file. Anything that would need
    guesswork is refused with its kind: E_IDENTITY_SOURCE kind=<workflow|main|agent|team|codex_rows|run_token>."""
    tasks = {task["id"]: task for task in spec["tasks"]}
    if fc.sha256_hex(token) != bindings.get("run_token_sha256"):
        raise fc.Refusal("E_IDENTITY_SOURCE", kind="run_token")
    root = bindings["roots"]["CLAUDE_ROOT"]
    rows, foreign, dirs_of = [], set(), {}
    for directory in journal_dirs(root):
        for entry in read_journal(directory):
            label = entry.get("label")
            if entry.get("type") != "started" or not isinstance(label, str):
                continue
            parsed = parse_identity(label)
            if parsed is None or fc.sha256_hex(parsed["run"]) != bindings["run_token_sha256"]:
                foreign.add(label)
                continue
            dirs_of.setdefault(label, set()).add(directory)
    for label, found in sorted(dirs_of.items()):
        if len(found) > 1:
            raise fc.Refusal("E_IDENTITY_SOURCE", kind="workflow")
        rows.append({"identity": label, "actor": "workflow_child", "workflow_dir": next(iter(found))})
    main_sessions, team_claims, strict_missing = collections.Counter(), collections.Counter(), 0
    for record in (launches or {}).get("records", []):
        main_sessions[(record.get("session_id"),) if record.get("actor") == "main" else ()] += 1
    for record in (launches or {}).get("records", []):
        actor, identity, session = record.get("actor"), record.get("identity"), record.get("session_id")
        transcript = session_transcript(root, session)
        session_dir = session_directory(root, session)
        if actor == "main":
            # A dedicated session belongs to one launch record and hosts no Workflow run; that the model called the Agent
            # tool once (a subagents/agent-*.jsonl child) does not make it shared.
            if main_sessions[(session,)] > 1 or (session_dir and os.path.isdir(os.path.join(session_dir, "subagents", "workflows"))):
                raise fc.Refusal("E_IDENTITY_SOURCE", kind="main")
            rows.append({"identity": identity, "actor": actor, **({"transcript": transcript} if transcript else {})})
        elif actor == "strict_process":
            if transcript is None:
                strict_missing += 1
            rows.append({"identity": identity, "actor": actor, **({"transcript": transcript} if transcript else {})})
        elif actor == "agent_child":
            harness = read_jsonl(transcript)[0] if transcript else None
            uses = [use for use in tool_uses(harness or []) if use["name"] in ("Agent", "Task")]
            if len(uses) != 1:
                raise fc.Refusal("E_IDENTITY_SOURCE", kind="agent")
            rows.append({"identity": identity, "actor": actor, "session_dir": session_dir, "tool_use_id": uses[0]["id"]})
        elif actor == TEAM_ACTOR:
            agent = record.get("agent_id")
            claim = (session, agent)
            team_claims[claim] += 1
            meta = read_json(os.path.join(session_dir, "subagents", f"agent-{agent}.meta.json")) if session_dir else None
            if team_claims[claim] > 1 or not isinstance(meta, dict) or meta.get("taskKind") != "in_process_teammate":
                raise fc.Refusal("E_IDENTITY_SOURCE", kind="team")
            rows.append({"identity": identity, "actor": actor,
                         "transcript": os.path.join(session_dir, "subagents", f"agent-{agent}.jsonl")})
        else:
            raise _invalid("E_ROW", row=len(rows), field="actor")
    if codex_document is not None:
        if not isinstance(codex_document, dict) or codex_document.get("schema") != IDENTITY_SCHEMA \
                or codex_document.get("run") != token or not isinstance(codex_document.get("rows"), list):
            raise fc.Refusal("E_IDENTITY_SOURCE", kind="codex_rows")
        rows.extend(item for item in codex_document["rows"] if isinstance(item, dict))
    rows.sort(key=lambda row: (str(row.get("identity")), str(row.get("actor"))))
    table = {"schema": IDENTITY_SCHEMA, "run": token, "rows": rows}
    validate_identity_table(table, tasks)
    return table, {"foreign_labels": len(foreign), "strict_without_transcript": strict_missing}


# ---- M11 for Codex role children (correction 9, U13's reference specification) -----------------------------------

def parse_role_toml(data):
    """The fields U9 needs from a role TOML: name, model, effort (model_reasoning_effort) and developer_instructions."""
    try:
        document = tomllib.loads(data.decode("utf-8") if isinstance(data, bytes) else data)
    except (tomllib.TOMLDecodeError, UnicodeDecodeError):
        return None
    return {"name": document.get("name"), "model": document.get("model"), "effort": document.get("model_reasoning_effort"),
            "developer_instructions": document.get("developer_instructions")}


def _payload(record):
    return record.get("payload") if isinstance(record.get("payload"), dict) else {}


def _mcp_server(name):
    parts = str(name).split("__")
    return parts[1] if str(name).startswith("mcp__") and len(parts) >= 3 else None


def _same_server(name, allowed):
    return name.replace("-", "_") in {item.replace("-", "_") for item in allowed}


def role_child_state(child, parent, role, parent_servers):
    """The M11 grader for a Codex child that applied a role: the role's developer_instructions occur exactly once in the
    child's developer messages, every own turn_context carries the role's model and effort, and the child's sandbox,
    working directory and MCP servers equal the parent's effective set. Outputs follow U13's reference specification:
    developer_text_contains_role_once, model_equals_pin, effort_equals_pin, tools_equal_parent_set."""
    meta = next((record for record in child if record.get("type") == "session_meta"), None)
    start = _payload(meta).get("subagent_history_start_ordinal") if meta else None
    own = [record for record in child if not (isinstance(start, int) and isinstance(record.get("ordinal"), int)
                                             and record["ordinal"] < start)]
    contexts = [_payload(record) for record in own if record.get("type") == "turn_context"]
    instructions = role["developer_instructions"]
    count = 0
    for record in child:
        payload = _payload(record)
        if record.get("type") == "response_item" and payload.get("type") == "message" and payload.get("role") == "developer":
            count += sum(item.get("text", "").count(instructions) for item in payload.get("content") or []
                         if isinstance(item, dict) and isinstance(item.get("text"), str))
    servers = set()
    for record in own:
        payload = _payload(record)
        if record.get("type") == "response_item" and payload.get("type") == "function_call" and _mcp_server(payload.get("name")):
            servers.add(_mcp_server(payload["name"]))
        item = payload.get("item") if isinstance(payload.get("item"), dict) else {}
        # A rollout records an MCP call as an item_completed McpToolCall item (exec events spell it mcp_tool_call).
        if record.get("type") == "event_msg" and item.get("type") in ("McpToolCall", "mcp_tool_call") and item.get("server"):
            servers.add(str(item["server"]))
    parent_contexts = [_payload(record) for record in parent or [] if record.get("type") == "turn_context"]
    parent_context = parent_contexts[-1] if parent_contexts else None
    tools = all(_same_server(server, parent_servers) for server in servers)
    if parent_context is not None:
        tools = tools and all(context.get("sandbox_policy") == parent_context.get("sandbox_policy")
                              and context.get("cwd") == parent_context.get("cwd") for context in contexts)
    state = {"developer_text_contains_role_once": count == 1,
             "model_equals_pin": all(context.get("model") == role["model"] for context in contexts) if contexts else None,
             "effort_equals_pin": all(context.get("effort", context.get("reasoning_effort")) == role["effort"]
                                      for context in contexts) if contexts else None,
             "tools_equal_parent_set": tools, "agent_role": _payload(meta).get("agent_role") if meta else None}
    reasons = []
    if meta is not None and state["agent_role"] != role["name"]:
        reasons.append("agent_role")
    for field, reason in (("developer_text_contains_role_once", "developer_text"), ("model_equals_pin", "model"),
                          ("effort_equals_pin", "effort"), ("tools_equal_parent_set", "bindings")):
        if state[field] is False:
            reasons.append(reason)
    unknown = meta is None or state["model_equals_pin"] is None or state["effort_equals_pin"] is None
    state.update(reasons=sorted(reasons, key=["agent_role", "developer_text", "model", "effort", "bindings"].index),
                 status="fail" if reasons else "unknown" if unknown else "pass")
    return state


def m11_summary(states):
    """Per-arm counts of the role-child states, unknowns included (M11 is a required row). A child that applied no role
    (seed-binding-4 spawns one in every run) has no role to compare with and is counted as not_applicable."""
    result = {}
    for item in states:
        entry = result.setdefault(item["arm"], {"children": 0, "pass": 0, "fail": 0, "unknown": 0, "not_applicable": 0})
        entry["children"] += 1
        entry[item["status"]] += 1
    return dict(sorted(result.items()))


def _assistant_texts(records, after=None):
    """Texts of the assistant messages of a rollout, optionally only those after the record index `after`."""
    found = []
    for number, record in enumerate(records):
        payload = _payload(record)
        if (after is None or number > after) and record.get("type") == "response_item" and payload.get("type") == "message" \
                and payload.get("role") == "assistant":
            found.append("".join(item.get("text", "") for item in payload.get("content") or []
                                 if isinstance(item, dict) and isinstance(item.get("text"), str)))
    return found


def find_rollout(driver_dir, identity, thread):
    """The rollout copy of one thread that U10 retains in `<driver>/attempts/<identity>/rollouts/` as
    `rollout-<time>-<thread>.jsonl` (design section 3.1; codex_launch.copy_rollouts): {"status": "ok" | "missing" |
    "compressed" | "duplicate" | "parse", "records", "errors"}. Exactly one copy per thread is read; a compressed copy is not
    parsed and several copies are never guessed between."""
    directory = os.path.join(str(driver_dir or ""), "attempts", str(identity), "rollouts")
    try:
        names = sorted(os.listdir(directory)) if thread and driver_dir else []
    except OSError:
        names = []
    plain = [name for name in names if name.startswith("rollout-") and name.endswith(f"-{thread}.jsonl")]
    if not plain:
        compressed = any(name.startswith("rollout-") and name.endswith(f"-{thread}.jsonl.zst") for name in names)
        return {"status": "compressed" if compressed else "missing", "records": None, "errors": 0}
    if len(plain) > 1:
        return {"status": "duplicate", "records": None, "errors": 0}
    records, errors = read_jsonl(os.path.join(directory, plain[0]))
    if errors or records is None:
        return {"status": "parse", "records": records, "errors": errors}
    return {"status": "ok", "records": records, "errors": 0}


def codex_subagent_attempt(driver_dir, identity, row, boundary=None):
    """R2 codex_subagent: the child rollout copy U10 retains under attempts/<identity>/rollouts/ (rollout-*-<thread>.jsonl);
    its last assistant message is the answer. With boundary "last_turn" (seed-binding-5, U10-D12) only a message after the
    last task_started counts, so a followup turn that said nothing is an empty answer, not the earlier reply."""
    attempt = _attempt(identity, "codex_subagent", "codex")
    found = find_rollout(driver_dir, identity, row.get("thread_id"))
    if found["status"] in ("missing", "compressed", "duplicate"):
        reason = {"missing": "attempt_class_unresolved", "compressed": "parse", "duplicate": "duplicate_rollout"}[found["status"]]
        attempt.update({"class": "unresolved", "carrier": carrier("unknown", reason)})
        return attempt
    records, errors = found["records"], found["errors"]
    attempt["parse_errors"] = errors
    attempt["_rows"] = records or []
    if found["status"] == "parse":
        attempt.update({"class": "unresolved", "carrier": carrier("unknown", "parse")})
        return attempt
    cut = None
    if boundary == "last_turn":
        started = [number for number, record in enumerate(records) if record.get("type") == "event_msg"
                   and _payload(record).get("type") == "task_started"]
        cut = started[-1] if started else None
    texts = _assistant_texts(records, cut)
    text = texts[-1] if texts else ""
    if not text.strip():
        return _no_answer(attempt, "empty")
    attempt["answer"] = {"text": text, "evidence": []}
    return attempt


# ---- Collect: the retained evidence of each identity row becomes one JSON record per run ------------------------

RECORDS_SCHEMA = "token-e2e-evidence/1"
BOUNDARIES = {"seed-binding-5": "last_turn"}
WINDOW_OF = {"claude": "W_C", "codex": "W_X"}


def _variants(function, readings, names):
    """`function(readings)` under the decided readings, plus one result per single alternative of `names` (R5)."""
    variants = {}
    for name in names:
        for value in fc.READINGS[name]:
            if value != readings[name]:
                variants[f"{name}|{value}"] = function(dict(readings, **{name: value}))
    return {"base": function(readings), "variants": variants}


def pick(entry, readings, decided):
    """The stored variant that matches `readings` when exactly one reading differs from the decided one."""
    changed = [(name, readings[name]) for name in readings if readings[name] != decided.get(name)]
    if len(changed) == 1:
        return entry["variants"].get(f"{changed[0][0]}|{changed[0][1]}", entry["base"])
    return entry["base"]


def _load_events(path):
    rows, _ = read_jsonl(path)
    return rows or []


def _resolve_events_path(row, events_dir):
    path = row.get("events_file")
    if not isinstance(path, str) or not path:
        return None
    return path if os.path.isabs(path) else os.path.join(events_dir, path)


def _driver_ledger(driver_dir):
    if not driver_dir:
        return []
    rows, _ = read_jsonl(os.path.join(str(driver_dir), "ledger.jsonl"))
    return rows or []


def _ledger_start(ledger, identity):
    for kind in ("finished", "spawned"):
        for item in ledger:
            if item.get("identity") == identity and item.get("kind") == kind and isinstance(item.get("start"), str):
                return item["start"]
    return None


def _attempts_for_row(row, task, bindings, sources, codex_ledger):
    actor, identity = row["actor"], row["identity"]
    roots = bindings["roots"]
    out_dir = roots["E2E_DIR"]
    if actor == "workflow_child":
        attempts = workflow_attempts(row.get("workflow_dir", ""), identity)
        if not attempts:
            attempt = _attempt(identity, actor, "claude")
            attempt.update({"class": "unresolved", "carrier": carrier("unknown", "attempt_class_unresolved")})
            attempts = [attempt]
        return attempts
    if actor == "agent_child":
        return [agent_child_attempt(row.get("session_dir", ""), row.get("tool_use_id"), identity, [roots["CLAUDE_ROOT"]])]
    if actor in ("main", "strict_process"):
        suffix = "main" if actor == "main" else "strict"
        stdout = os.path.join(out_dir, f"{identity}.{suffix}.out")
        return [transcript_attempt(row.get("transcript"), identity, actor, stdout if os.path.exists(stdout) else None)]
    if actor == TEAM_ACTOR:
        return [transcript_attempt(row.get("transcript"), identity, actor)]
    if actor == "codex_exec":
        path = _resolve_events_path(row, sources.get("events_dir") or out_dir)
        attempt = codex_exec_attempt(path, identity, codex_ledger, row.get("exit_status"))
        attempt["start"] = _ledger_start(codex_ledger, identity)
        attempt["_events"] = _load_events(path) if path else []
        return [attempt]
    if actor == "codex_subagent":
        attempt = codex_subagent_attempt(sources.get("driver_dir") or "", identity, row, BOUNDARIES.get(task["id"]))
        attempt["start"] = _ledger_start(codex_ledger, identity)
        return [attempt]
    attempt = _attempt(identity, actor, "claude")
    attempt.update({"class": "unresolved", "carrier": carrier("unknown", "attempt_class_unresolved")})
    return [attempt]


def _m12_config(bindings, task, spec):
    block = spec["block"]["m12"]
    return {"marker": block["marker"], "attachment_allowlist": block["attachment_allowlist"],
            "anchors": bindings["roots"].get("instruction_anchors") or bindings.get("instruction_anchors") or [],
            "packet_roots": [os.path.join(bindings["exec_checkout"], task["params"].get("fixture_path", ""))],
            "memory_roots": bindings["roots"].get("memory_index_roots") or [], "cwd": bindings["exec_checkout"]}


def _hook_source(attempt, row, sources, arm):
    """R7 test 2: Workflow children through the join row and the run-mode child, strict processes through the kernel."""
    if attempt["actor"] == "workflow_child":
        family = "claude"
        join = (sources.get("join") or {}).get(family, {}).get((attempt["identity"], "workflow_child"))
        return m12_hook_source(attempt.get("agent_id"), attempt["identity"], join, (sources.get("run_mode") or {}).get(arm, []))
    path = row.get("transcript")
    if not path or not os.path.exists(path):
        return {"status": "unknown", "reason": "no_transcript", "hook_rows": None, "read_rows": None}
    context = kernel_hook_context(path)
    if context["inserted"] is None:
        return {"status": "unknown", "reason": "kernel_unavailable", "hook_rows": None, "read_rows": None}
    return {"status": "ok", "reason": None, "hook_rows": context["inserted"],
            "read_rows": (context["by_hook"] or {}).get("PreToolUse:Read", 0)}


def _parent_rollout(driver_dir, identity, row):
    found = find_rollout(driver_dir, identity, row.get("parent_thread_id"))
    return found["records"] if found["status"] == "ok" else None


def _role_child(rows, row, attempt, bindings, sources):
    """M11 for a Codex child that applied a role (correction 9): the role file at exec_rev, the parent's effective server
    set from the bindings, the parent's rollout copy; anything missing leaves the state unknown, never a pass."""
    meta = next((record for record in rows if record.get("type") == "session_meta"), None)
    name = _payload(meta).get("agent_role") if meta else None
    if not name:
        return {"status": "not_applicable", "reasons": []}
    data = fc.GitSources(bindings["exec_checkout"], bindings["exec_rev"]).read(f"adoption/agents/codex/{name}.toml")
    role = parse_role_toml(data) if data else None
    servers = (bindings.get("codex") or {}).get("parent_servers")
    parent = _parent_rollout(sources.get("driver_dir"), attempt["identity"], row)
    if not role or servers is None or parent is None or not role.get("developer_instructions"):
        return {"status": "unknown", "reasons": ["role_inputs_missing"]}
    state = role_child_state(rows, parent, role, list(servers))
    return {"status": state["status"], "reasons": state["reasons"]}


def _record_facts(attempt, rows, events, row, task, keys, spec, bindings, sources, captures, arm):
    readings = spec["readings"]
    template, family = task["template"], task["family"]
    if attempt["class"] != "completed":
        return {}
    entry = (keys.get("keys") or {}).get(task["id"]) or {}
    key = entry.get("key") if entry.get("status") == "ok" else None
    if family == "claude":
        owner = attempt.get("agent_id") or "main"
        calls = claude_calls(rows or [], sources.get("call_ledger") or [], owner, [bindings["roots"]["CLAUDE_ROOT"]])
    else:
        calls = codex_calls(events or [])
    window = bindings["windows"][WINDOW_OF[family]]
    facts = {}
    if template in fc.WEB_TEMPLATES:
        facts["retrieval"] = _variants(lambda r: result_dict(retrieval_check(calls, task["params"].get("urls") or [], window, r)),
                                       readings, ["R2-18"])
    if template == "T2" and key:
        facts["recovery"] = _variants(lambda r: result_dict(recovery_check(calls, key["sha256"], r)), readings, ["R2-17"])
    if template == "T7" or template in fc.CATALOG_TEMPLATES:
        records = (key or {}).get("memory_records")
        facts["memory"] = result_dict(memory_check(calls, records) if records else fc.unknown("key_missing"))
    if template == "T14":
        post = captures.get(f"arm-{family}-{arm}-post-arm.json") or {}
        children = (sources.get("run_mode") or {}).get(arm, []) if family == "claude" else []
        child = next((item for item in children if item.get("agent_id") == attempt.get("agent_id")), None)
        pending = ((child or {}).get("final_return") or {}).get("background_pending") or 0
        rollout = None
        if family == "codex":  # exec events carry no timestamps: U10's rollout copy times the query and the lifetime
            thread = row.get("thread_id") or next((item.get("thread_id") for item in events or []
                                                   if item.get("type") == "thread.started"), None)
            rollout = find_rollout(sources.get("driver_dir"), attempt["identity"], thread)
        facts["t14"] = t14_facts(family=family, rows=rows, calls=calls, attempt=attempt, post=post, pending=pending,
                                 rollout=rollout)
    if template == "T31" and key:
        post = captures.get(f"arm-{family}-{arm}-post-arm.json") or {}
        capture = (post.get("builders") or {}).get(task["id"])
        source = fc.GitSources(bindings["exec_checkout"], bindings["exec_rev"])
        after = source.read("fixtures/after.py")
        arms = bindings["arms"].get(arm, {})
        if capture is None or after is None:
            facts["builder"] = result_dict(fc.unknown("input_missing"))
        else:
            facts["builder"] = result_dict(grade_builder_capture(
                capture, prepared_path=arms.get("worktree_paths", {}).get(task["id"], ""),
                prepared_base=arms.get("worktree_bases", {}).get(task["id"], ""), observed=builder_observed_tree(rows or []),
                exec_rev=bindings["exec_rev"], after_bytes=after, key=key))
    if arm == "B" and attempt["actor"] in GRADED_ACTORS:  # M7 covers every completed arm-B attempt of both families (R14)
        ans = fc.Answer(attempt["answer"]["text"] if attempt["answer"] else "", tuple((attempt["answer"] or {}).get("evidence", ())))
        seeded = "toon-seeded" in task["lane_tags"]
        facts["toon"] = _variants(lambda r: toon_facts(calls, ans, key, r, seeded=seeded), readings,
                                  ["R2-01", "R2-02", "R2-15", "R2-16"])
    if attempt["actor"] == "codex_subagent":
        facts["role_child"] = _role_child(rows or [], row, attempt, bindings, sources)
    if template == "T34" and isinstance(row.get("transcript"), str) and os.path.exists(row["transcript"]):
        facts["main_transcript_bytes"] = os.path.getsize(row["transcript"])  # measured separately (RV-30)
    if template == "T13":
        page = spec["block"]["pages"]["mcp"]
        named = [call for call in calls if any(fc.url_matches(found, page, "exact_url") for found in call_urls(call))]
        first = named[0] if named else None
        text = (first or {}).get("result_text")
        facts["conversion"] = {"tool": first["tool"] if first else None, "state": first["state"] if first else None,
                               "bytes": len(text.encode("utf-8")) if isinstance(text, str) else None,
                               "missing_scopes": [scope for scope in ("local", "project", "user")
                                                  if isinstance(text, str) and not fc.has_word(text, scope)] if text else None}
    if template in ("T32", "T33"):
        hooks = _hook_source(attempt, row, sources, arm)
        config = _m12_config(bindings, task, spec)
        facts["hooks"] = {"status": hooks["status"], "reason": hooks["reason"], "hook_rows": hooks["hook_rows"],
                          "read_rows": hooks["read_rows"]}
        facts["mcp_skill_bash_calls"] = sum(1 for use in tool_uses(rows or [])
                                            if use["name"].startswith("mcp__") or use["name"] in ("Skill", "Bash"))
        if template == "T32":  # the positive control is never blind evidence: only its Read rows are measured
            facts["m12"] = _variants(lambda r: m12_attempt(rows or [], config, r, hooks["hook_rows"]), readings,
                                     ["R2-11", "R2-12", "R2-13", "R2-14"])
    return facts


def collect(spec, bindings, keys, table, sources, captures):
    """One private JSON record per run of every identity row: the attempt (class, cause, answer, carrier) plus the facts
    the grading rules need from the transcript or the events (retrieval, memory, encodes, M12, T14, builder)."""
    tasks = {task["id"]: task for task in spec["tasks"]}
    codex_ledger = _driver_ledger(sources.get("driver_dir"))
    records = []
    for row in table["rows"]:
        parsed = parse_identity(row["identity"])
        task = tasks.get(parsed["task"]) if parsed else None
        if task is None:
            continue
        for attempt in _attempts_for_row(row, task, bindings, sources, codex_ledger):
            rows = attempt.pop("_rows", None)
            events = attempt.pop("_events", None)
            attempt.update(arm=parsed["arm"], task=task["id"], number=parsed["attempt"], template=task["template"],
                           family=task["family"], actor=row["actor"])
            attempt["facts"] = _record_facts(attempt, rows, events, row, task, keys, spec, bindings, sources, captures,
                                             parsed["arm"])
            join = (sources.get("join") or {}).get(task["family"], {}).get((row["identity"], row["actor"]))
            attempt["lanes"] = (join or {}).get("lanes") or {}
            records.append(attempt)
    records.sort(key=lambda record: (record["identity"], record["actor"], record["run_index"]))
    return records


# ---- Evaluate: the pure grading of the collected records (R3-R6, R14-R18, R22) ----------------------------------

ORACLE_READINGS = {"T1": ("R2-09",), "T2": ("R2-17",), "T3": ("R2-03",), "T5": ("R2-04",), "T9": ("R2-01", "R2-02"),
                   "T11": ("R2-05",), "T14": ("R2-19", "R2-20")}
ORACLE_READINGS.update({name: ("R2-01", "R2-02", "R2-18") for name in fc.WEB_TEMPLATES})
GRADED_ACTORS = ("workflow_child", "agent_child", "codex_exec", "codex_subagent")
STRICT_KEYS = {"T32", "T33"}


def _page(captures, phase, family, kind):
    document = captures.get(f"pages-{phase}-{family}.json") or {}
    return next((page for page in document.get("pages") or [] if page.get("kind") == kind), None)


def _judged(components, classes, judgment):
    if "D" not in classes or any(result.status == "fail" for result in components.values()):
        return
    if judgment is None:
        components["D"] = fc.pending("judge_pending")
    elif judgment.get("status") != "ok":
        components["D"] = fc.unknown(judgment.get("reason") or "judge_unavailable")
    else:
        clauses = judgment.get("clauses") or []
        components["D"] = fc.ok() if clauses and all(item.get("holds") for item in clauses) else fc.fail("clause")


def grade_record(record, task, keys, captures, readings, decided, starts, judgment):
    """The components and the combined result of one recorded run. A run that never had a chance to answer is not graded;
    a run with no answer fails with its cause; otherwise the carrier and the template's oracles decide."""
    if record["class"] == "inadmissible":
        return {}, fc.unknown(record["reason"] or "inadmissible")
    components = {"C": result_from(record["carrier"])}
    if record["class"] == "unresolved" or record["answer"] is None or components["C"].status == "unknown":
        return components, fc.combine(components)
    template, params, facts = task["template"], task["params"], record.get("facts") or {}
    ans = fc.Answer(record["answer"]["text"], tuple(record["answer"]["evidence"]))
    entry = (keys.get("keys") or {}).get(task["id"]) or {}
    key = entry.get("key") if entry.get("status") == "ok" else None
    reason = entry.get("reason") or "key_missing"
    family, arm = task["family"], record["arm"]
    post = captures.get(f"arm-{family}-{arm}-post-arm.json") or {}
    extractions = (judgment or {}).get("extractions")
    ctx = {"extractions": extractions}
    if template == "T0":
        pre = (((captures.get(f"arm-{family}-{arm}-pre-arm.json") or {}).get("t0")) or {}).get(task["id"])
        after = ((post.get("t0")) or {}).get(task["id"])
        if pre and "arm" in pre and "plain" in pre:
            ctx["captures"] = {"pre": pre, "post": after if after and ("arm" in after or "discarded" in after) else None}
        components.update(fc.ORACLES["T0"](params, {}, ans, readings, ctx))
    elif template == "T14":
        run_token = record["identity"].split(".")[0]
        t14 = facts.get("t14") or {}
        components["B"] = t14_check(ans.text, run_token=run_token, starts=starts, q=t14.get("q"),
                                    background_pending=t14.get("background_pending", 0), survivors=t14.get("survivors", []),
                                    readings=readings, q_status=t14.get("q_status"),
                                    survival_observed=t14.get("survival_observed", True))
    elif template == "T31":
        components["B"] = result_from(facts["builder"]) if "builder" in facts else fc.unknown("input_missing")
    elif template == "T36":
        components["A"] = fc.grade_binding(key, ans) if key else fc.unknown(reason)
    elif template in ("T12", "T13"):
        kind = "stripe" if template == "T12" else "mcp"
        state, value = fc.page_key(_page(captures, "w-open", family, kind) or {}, _page(captures, "w-close", family, kind) or {},
                                   (key or {}).get("facts_required") or [])
        if state == "ok":
            ctx["facts"] = value
            components.update(fc.ORACLES[template](params, key or {}, ans, readings, ctx))
        else:
            components["A"] = fc.unknown(value)
    elif template == "T27":
        acceptance = ((captures.get("post-w.json") or {}).get("acceptance") or {}).get(task["id"])
        components.update(fc.ORACLES[template](params, dict(key, acceptance=acceptance), ans, readings, ctx) if key
                          else {"A": fc.unknown(reason)})
    elif template == "T30":
        compiled = (captures.get("post-w.json") or {}).get("py_compile")
        if compiled is None:
            components["A"] = fc.unknown("post_w_missing")
        else:
            components.update(fc.ORACLES[template](params, compiled, ans, readings, ctx))
            components["B"] = fc.ok() if compiled.get("exit") == 0 and not compiled.get("stdout_bytes") and \
                not compiled.get("stderr_bytes") else fc.fail("py_compile")
    elif template == "T11":
        clone = (post.get("clones") or {}).get(task["id"])
        if clone and clone.get("key") and clone.get("base_ok") and clone.get("clean"):
            components.update(fc.ORACLES[template](params, clone["key"], ans, readings, ctx))
            components["B"] = fc.ok()
        else:
            components["A"] = components["B"] = fc.unknown("input_missing")
    elif key is None:
        components["A"] = fc.unknown(reason)
    else:
        components.update(fc.ORACLES[template](params, key, ans, readings, ctx))
    if template in fc.WEB_TEMPLATES and "retrieval" in facts:
        components["R"] = result_from(pick(facts["retrieval"], readings, decided))
    if template == "T2" and "recovery" in facts:
        components["V"] = result_from(pick(facts["recovery"], readings, decided))
    if "memory" in facts:
        components["H"] = result_from(facts["memory"])
    _judged(components, task["classes"], judgment)
    combined = fc.combine(components)
    entries = ((captures.get(f"arm-{family}-{arm}-pre-arm.json") or {}).get("exec_checkout") or {}).get("entries") or []
    return components, apply_tree_drift(template, combined, entries)


def _attempt_view(record, row, task, readings, decided):
    """The dict `decide_task` reads: class, status, and for blind tasks the cleanliness of the run."""
    view = {"class": record["class"], "status": row["status"] if record["class"] != "inadmissible" else "unknown",
            "actor": record["actor"], "reason": record["reason"], "cause": record["cause"]}
    if task["template"] == "T32" and record["class"] == "completed":
        facts = record.get("facts") or {}
        view["clean"] = pick(facts["m12"], readings, decided)["clean"] if "m12" in facts else "unknown"
    return view


def _recorded(record, task, components):
    """Descriptive fields of the private row (c1): payload bytes, main-transcript bytes, conversion state and the T14
    reported/expected ratio. They decide nothing."""
    facts = record.get("facts") or {}
    recorded = {}
    if task["template"] in ("T9",) + fc.WEB_TEMPLATES and record["answer"]:
        found = fc.payload_candidates(fc.Answer(record["answer"]["text"], ()))
        if found:
            recorded["payload_bytes"] = len(found[0]["text"].encode("utf-8"))
    for name in ("main_transcript_bytes", "conversion"):
        if name in facts:
            recorded[name] = facts[name]
    if task["template"] == "T14" and "B" in components:
        recorded["t14"] = dict(components["B"].detail)
    return recorded


def _judgment_key(record):
    return (record["identity"], record["actor"], record["run_index"])


def _kind(task):
    return "blind" if task["template"] == "T32" else "control" if task["template"] == "T33" else "plain"


def _counter(items):
    return dict(sorted(collections.Counter(items).items()))


def evaluate(spec, keys, bindings, records, captures, judgments, *, meta=None, join=None):
    """Grade the collected records: the private rows and the ID-free aggregate (task outcomes per family and arm, G-Q, G-C,
    M7, M8, M11, M12, the alternatives). Pure: the same inputs give the same bytes, and no source file or model is read.
    `join` is {family: [U4 join-ledger rows]} for the families whose ledger was supplied: M8's opportunities follow those
    rows, and the other families' opportunities come from the spec and the records."""
    rows, aggregate, _ = _evaluate(spec, keys, bindings, records, captures, judgments, meta=meta, join=join)
    return rows, aggregate


def _evaluate(spec, keys, bindings, records, captures, judgments, *, readings=None, with_alternatives=True, cache=None,
              meta=None, join=None):
    decided = spec["readings"]
    readings = dict(decided) if readings is None else readings
    cache = {} if cache is None else cache
    tasks = {task["id"]: task for task in spec["tasks"]}
    starts = {}
    for record in records:
        if record["start"] and (record["identity"] not in starts or iso_seconds(record["start"]) < iso_seconds(starts[record["identity"]])):
            starts[record["identity"]] = record["start"]
    for record in records:
        starts.setdefault(record["identity"], None)
    rows = []
    for record in records:
        task = tasks[record["task"]]
        judgment = judgments.get(_judgment_key(record))
        key = (_judgment_key(record), tuple(readings[name] for name in ORACLE_READINGS.get(task["template"], ())))
        if key not in cache:
            cache[key] = grade_record(record, task, keys, captures, readings, decided, starts, judgment)
        components, result = cache[key]
        row = {"identity": record["identity"], "actor": record["actor"], "run_index": record["run_index"],
               "template": task["template"], "arm": record["arm"], "task": record["task"], "attempt": record["number"],
               "family": record["family"], "class": record["class"], "reason": record["reason"], "cause": record["cause"],
               "superseded": record["superseded"], "status": result.status, "reasons": list(result.reasons),
               "components": [{"id": name, "class": name, "status": part.status, "reason": ",".join(part.reasons) or None}
                              for name, part in sorted(components.items())],
               "answer_sha256": fc.sha256_hex(record["answer"]["text"]) if record["answer"] else None,
               "cleanliness": None, "m12_tests": None, "recorded": _recorded(record, task, components)}
        if task["template"] == "T32" and record["class"] == "completed" and "m12" in (record.get("facts") or {}):
            picked = pick(record["facts"]["m12"], readings, decided)
            row["cleanliness"], row["m12_tests"] = picked["clean"], picked["tests"]
        rows.append(row)
    by_task = collections.defaultdict(list)
    for record, row in zip(records, rows):
        if record["arm"] != "T":
            by_task[(record["family"], record["arm"], record["task"])].append((record, row))
    outcomes, details = {}, {}
    for task in spec["tasks"]:
        for arm in task["arms"]:
            items = by_task.get((task["family"], arm, task["id"]), [])
            if not items:
                outcomes[(arm, task["id"])] = {"status": "unknown", "reason": "not_launched", "last_attempt": None,
                                               "inadmissible": 0}
                details[(arm, task["id"])] = {"not_launched": True}
                continue
            attempts = [_attempt_view(record, row, task, readings, decided) for record, row in items]
            read_rows = None
            if task["template"] == "T33":
                observed = [record["facts"]["hooks"]["read_rows"] for record, _ in items
                            if record["actor"] == "workflow_child" and (record.get("facts") or {}).get("hooks")]
                read_rows = observed[0] if observed and observed[0] is not None else None
            outcomes[(arm, task["id"])] = decide_task(attempts, readings["R2-10"], kind=_kind(task), read_rows=read_rows)
            details[(arm, task["id"])] = {"not_launched": False, "read_rows": read_rows}
    aggregate = _aggregate(spec, keys, records, rows, outcomes, details, readings, decided, by_task, captures, judgments, meta or {},
                           join)
    if with_alternatives:
        aggregate["alternatives"] = _alternatives(spec, keys, bindings, records, captures, judgments, decided, cache, outcomes, join)
    return rows, aggregate, outcomes


def _summary_of(aggregate):
    return {"g_q": aggregate["g_q"]["status"], "m7": aggregate["m7"]["status"],
            "m8": {lane: item["status"] for lane, item in sorted(aggregate["m8"].items())}, "m12": aggregate["m12"]["status"]}


def _alternatives(spec, keys, bindings, records, captures, judgments, decided, cache, base_outcomes, join=None):
    """Every reading of the R5 register that has an alternative, evaluated one at a time against the decided run; the
    counts are what the sealed rule would have said under that reading (tasks whose outcome changes, and the gates)."""
    published = {}
    for name, values in fc.READINGS.items():
        for value in values:
            if value == decided[name]:
                continue
            _, other, outcomes = _evaluate(spec, keys, bindings, records, captures, judgments,
                                           readings=dict(decided, **{name: value}), with_alternatives=False, cache=cache,
                                           join=join)
            changed = sum(1 for key, outcome in outcomes.items() if outcome["status"] != base_outcomes[key]["status"])
            published.setdefault(name, {})[value] = dict(_summary_of(other), tasks_changed=changed)
    published["attempt_rule_every_recorded"] = published.get("R2-10", {}).get("every_recorded")
    published["organic_only"] = published.get("R2-07", {}).get("organic_only")
    return published


def _attempt_item(task, runs, state, readings, decided):
    """One M8 opportunity from the runs (records and their graded rows) of one attempt identity and its lane state."""
    views = [_attempt_view(record, row, task, readings, decided) for record, row in runs]
    outcome = decide_task(views, readings["R2-10"])
    kind = "inadmissible" if all(view["class"] == "inadmissible" for view in views) else "attempt"
    return {"adopted": state if state in ("adopted", "not_adopted") else "unknown",
            "grade": outcome["status"] if outcome["status"] in ("pass", "fail") else "unknown", "kind": kind}


def _lane_opportunities(spec, lane, records, rows, readings, decided, join=None):
    """R15: the opportunities of one M8 lane in arm B. For a family whose U4 join ledger was supplied they are its rows
    (excluded rows aside): a row that names the lane is one opportunity; a `not_launched` row was never launched, an
    `unlisted` row is a recorded attempt no identity row lists (unknown, never graded) and any other row is graded from the
    records of its identity. For a family without a ledger they are one per recorded attempt (identity) of each organic task
    that carries the lane tag, and one not_launched opportunity for a task with none."""
    items = []
    tasks = {task["id"]: task for task in spec["tasks"]}
    graded = collections.defaultdict(list)
    for record, row in zip(records, rows):
        if record["arm"] == "B" and record["actor"] in GRADED_ACTORS:
            graded[(record["task"], record["identity"], record["actor"])].append((record, row))
    for family in fc.FAMILY_ARMS:
        ledger = (join or {}).get(family)
        if ledger is not None:
            for entry in ledger:
                task = tasks.get(entry.get("task"))
                if task is None or task["family"] != family or entry.get("arm") != "B" or entry.get("excluded_kind") \
                        or lane not in (entry.get("lanes") or {}):
                    continue
                state = (entry["lanes"][lane] or {}).get("state")
                if entry.get("source") == "not_launched":
                    items.append({"adopted": "unknown", "grade": "unknown", "kind": "not_launched"})
                elif entry.get("source") == "unlisted":
                    items.append({"adopted": "unknown", "grade": "unknown", "kind": "attempt"})
                elif graded.get((task["id"], entry.get("identity"), entry.get("actor"))):
                    items.append(_attempt_item(task, graded[(task["id"], entry["identity"], entry["actor"])], state, readings,
                                               decided))
                else:
                    items.append({"adopted": state if state in ("adopted", "not_adopted") else "unknown", "grade": "unknown",
                                  "kind": "attempt"})
            continue
        for task in spec["tasks"]:
            if task["family"] != family or "B" not in task["arms"] or task["opportunity"] != "organic" \
                    or lane not in task["lane_tags"]:
                continue
            by_identity = collections.defaultdict(list)
            for record, row in zip(records, rows):
                if record["task"] == task["id"] and record["arm"] == "B" and record["actor"] in GRADED_ACTORS:
                    by_identity[record["identity"]].append((record, row))
            if not by_identity:
                items.append({"adopted": "unknown", "grade": "unknown", "kind": "not_launched"})
            for identity in sorted(by_identity):
                runs = by_identity[identity]
                lanes = next((record.get("lanes") for record, _ in runs if record.get("lanes")), {}) or {}
                items.append(_attempt_item(task, runs, (lanes.get(lane) or {}).get("state", "unknown"), readings, decided))
    return items


GRADES_SCHEMA = "token-e2e-grades/1"


def _verdict_word(text):
    yes, no = fc.has_word(text, "yes"), fc.has_word(text, "no")
    return "yes" if yes and not no else "no" if no and not yes else None


def _stats(numbers):
    numbers = sorted(numbers)
    if not numbers:
        return {"min": None, "median": None, "max": None, "n": 0}
    return {"min": numbers[0], "median": numbers[len(numbers) // 2], "max": numbers[-1], "n": len(numbers)}


def _status_counts(statuses):
    counts = collections.Counter(statuses)
    return {name: counts.get(name, 0) for name in ("pass", "fail", "unknown")}


def m12_sums(records):
    """U9's per-attempt sums in the shape of U4's m12_inputs (R7), for the cross-check. U4 counts one join row per identity,
    so a superseded run of an identity never enters the sums."""
    sums = {kind: {"rows": 0, "hook_rows": 0, "mcp_skill_bash_calls": 0, "pretooluse_read_rows": 0} for kind in M12_FIELDS}
    for record in records:
        facts = record.get("facts") or {}
        if record["template"] not in STRICT_KEYS or record["family"] != "claude" or record["arm"] != "B" or record["superseded"]:
            continue
        kind = "strict_process" if record["actor"] == "strict_process" else \
            "positive_control" if record["template"] == "T33" else "blind_workflow"
        if record["actor"] not in ("workflow_child", "strict_process"):
            continue
        sums[kind]["rows"] += 1
        hooks = facts.get("hooks") or {}
        sums[kind]["hook_rows"] += hooks.get("hook_rows") or 0
        sums[kind]["pretooluse_read_rows"] += hooks.get("read_rows") or 0
        sums[kind]["mcp_skill_bash_calls"] += facts.get("mcp_skill_bash_calls") or 0
    return sums


def _aggregate(spec, keys, records, rows, outcomes, details, readings, decided, by_task, captures, judgments, meta, join=None):
    tasks = spec["tasks"]
    thresholds = spec.get("thresholds") or {}
    aggregate = {"schema": GRADES_SCHEMA, "tool": spec["block"]["tool"],
                 "preregistration": {"sha256": spec["preregistration"]["sha256"], "commit": spec["preregistration"]["commit"]},
                 "grading_block": {"sha256": spec["grading_block"]["sha256"], "grammar": spec["grading_block"]["grammar"],
                                   "readings": readings},
                 "controls": {"run": False}}
    aggregate.update(meta)
    attempts = {}
    for family, arms in fc.FAMILY_ARMS.items():
        attempts[family] = {}
        for arm in arms:
            mine = [record for record in records if record["family"] == family and record["arm"] == arm]
            attempts[family][arm] = {
                "recorded": len(mine), "completed": sum(1 for r in mine if r["class"] == "completed"),
                "inadmissible": {reason: sum(1 for r in mine if r["class"] == "inadmissible" and r["reason"] == reason)
                                 for reason in INADMISSIBLE_REASONS},
                "unresolved": sum(1 for r in mine if r["class"] == "unresolved"),
                "no_answer_causes": _counter(r["cause"] for r in mine if r["class"] == "completed" and r["cause"]),
                "superseded_runs": sum(1 for r in mine if r["superseded"])}
    aggregate["attempts"] = attempts
    per_arm, per_template = {}, {}
    for family, arms in fc.FAMILY_ARMS.items():
        per_arm[family] = {}
        for arm in arms:
            planned = [task for task in tasks if task["family"] == family and arm in task["arms"]]
            got = [outcomes[(arm, task["id"])] for task in planned]
            statuses = collections.Counter(item["status"] for item in got if not (item["reason"] == "not_launched"))
            per_arm[family][arm] = {
                "planned": len(planned), "pass": statuses["pass"], "fail": statuses["fail"], "unknown": statuses["unknown"],
                "not_launched": sum(1 for item in got if item["reason"] == "not_launched"),
                "incomplete_control": statuses["incomplete_control"],
                "pass_lower": statuses["pass"], "pass_upper": statuses["pass"] + statuses["unknown"]
                + sum(1 for item in got if item["reason"] == "not_launched"),
                "last_attempt_pass": sum(1 for item in got if item["last_attempt"] == "pass")}
    aggregate["tasks"] = per_arm
    for task in tasks:
        for arm in task["arms"]:
            entry = per_template.setdefault(task["template"], {}).setdefault(arm, {"pass": 0, "fail": 0, "unknown": 0})
            status = outcomes[(arm, task["id"])]["status"]
            entry[status if status in ("pass", "fail") else "unknown"] += 1
    aggregate["templates"] = {name: per_template[name] for name in sorted(per_template, key=fc.template_order)}
    gq = g_q(tasks, outcomes, readings)
    aggregate["g_q"] = gq
    aggregate["g_c_denominators"] = g_c_denominators(tasks, outcomes)
    seeded_tasks = {task["id"] for task in tasks if "toon-seeded" in task["lane_tags"]}
    toon_items = []
    for record in records:
        toon = (record.get("facts") or {}).get("toon")
        if toon and record["class"] == "completed" and record["arm"] == "B" and record["actor"] in GRADED_ACTORS:
            toon_items.append(dict(pick(toon, readings, decided), seeded=record["task"] in seeded_tasks))
    aggregate["m7"] = m7(toon_items, thresholds.get("M7"), readings)
    m8_criteria = {"threshold": (thresholds.get("M8") or {}).get("correct_lane_use_rate_gte", 0.8),
                   "minimum": thresholds.get("minimum_arm_b_opportunities", 5)}
    aggregate["m8"] = {lane: m8_lane(_lane_opportunities(spec, lane, records, rows, readings, decided, join), readings,
                                     m8_criteria) for lane in fc.M8_LANES}
    blind, strict_hooks = {}, 0
    for task in tasks:
        if task["template"] != "T32":
            continue
        items = by_task.get(("claude", "B", task["id"]), [])
        completed = [row for record, row in items if record["class"] == "completed"]
        counts = collections.Counter(row["cleanliness"] or "unknown" for row in completed)
        blind[task["id"]] = {"clean": counts["clean"], "contaminated": counts["contaminated"], "unknown": counts["unknown"],
                             "strict_replacement": any(record["actor"] == "strict_process" and row["cleanliness"] == "clean"
                                                       for record, row in items)}
    for record in records:
        if record["actor"] == "strict_process" and record["template"] in STRICT_KEYS:
            strict_hooks += ((record.get("facts") or {}).get("hooks") or {}).get("hook_rows") or 0
    control = next((task for task in tasks if task["template"] == "T33"), None)
    read_rows = details.get(("B", control["id"]), {}).get("read_rows") if control else None
    status = m12_status(blind, read_rows)
    parity = {}
    for task_id, entry in blind.items():
        items = by_task.get(("claude", "B", task_id), [])
        words = {actor: next((_verdict_word(record["answer"]["text"]) for record, _ in items
                              if record["actor"] == actor and record["answer"]), None)
                 for actor in ("workflow_child", "strict_process")}
        parity[task_id] = {"workflow": words["workflow_child"], "strict": words["strict_process"],
                           "parity": None if None in words.values() else words["workflow_child"] == words["strict_process"]}
    aggregate["m12"] = {"blind": blind, "positive_read_rows": read_rows, "strict": {"hook_rows": strict_hooks},
                        "status": status["status"], "reason": status["reason"], "sensitive": status["sensitive"]}
    aggregate["blind"] = {"verdict_parity": parity}
    aggregate["optional"] = {task["id"]: _status_counts([outcomes[(arm, task["id"])]["status"] for arm in task["arms"]])
                             for task in tasks if task["opportunity"] == "optional"}
    team = [(record, row) for record, row in zip(records, rows) if record["arm"] == "T"]
    aggregate["team_T"] = {"tasks": len({record["task"] for record, _ in team}),
                           **_status_counts([row["status"] for record, row in team if record["class"] != "inadmissible"]),
                           "inadmissible": sum(1 for record, _ in team if record["class"] == "inadmissible"),
                           "unmapped_teammates": sum(1 for record, _ in team if record["class"] == "unresolved")}
    sizes = []
    for record in records:
        if record["template"] in ("T9",) + fc.WEB_TEMPLATES and record["answer"]:
            found = fc.payload_candidates(fc.Answer(record["answer"]["text"], ()))
            if found:
                sizes.append(len(found[0]["text"].encode("utf-8")))
    aggregate["representation_sizes"] = {"payload_bytes": _stats(sizes)}
    binding = [row for record, row in zip(records, rows) if record["template"] == "T36" and record["class"] == "completed"]
    aggregate["m13_organic"] = {"own": sum(1 for row in binding if row["status"] == "pass"),
                                "sibling": sum(1 for row in binding if "sibling_value" in row["reasons"]),
                                "unknown": sum(1 for row in binding if row["status"] == "unknown")}
    roles = [{"arm": record["arm"], "status": (record.get("facts") or {}).get("role_child", {}).get("status", "unknown")}
             for record in records if record["actor"] == "codex_subagent" and record["class"] == "completed"]
    aggregate["m11_roles"] = m11_summary(roles)
    discarded = 0
    for name, document in sorted(captures.items()):
        if name.endswith("-post-arm.json"):
            discarded += sum(1 for item in (document.get("t0") or {}).values() if isinstance(item, dict) and "discarded" in item)
    aggregate["t0_post_discarded"] = discarded
    counts = collections.Counter(part["status"] for row in rows for part in row["components"] if part["id"] == "D")
    aggregate["judges"] = {"judged": counts["pass"] + counts["fail"], "pending": counts["pending"],
                           "unavailable": counts["unknown"], "judgments_supplied": len(judgments)}
    aggregate["privacy"] = {"canary_values_checked": 0}
    return aggregate


def exit_status(aggregate):
    """0 when G-Q, M7, every M8 lane and M12 pass; 1 otherwise (judgments pending included)."""
    ok = aggregate["g_q"]["status"] == "pass" and aggregate["m7"]["status"] == "pass" \
        and all(item["status"] == "pass" for item in aggregate["m8"].values()) and aggregate["m12"]["status"] == "pass"
    return 0 if ok else 1


def canary_values(bindings, table, records):
    """R22: the identifier values the aggregate must never hold: the run token, every identity, label, id, path and root of
    the inputs, the home directory and the user name."""
    values = {table.get("run", "")}
    for row in table.get("rows", []):
        values.update(str(item) for item in row.values() if isinstance(item, str))
        for name in ("events_file", "transcript", "workflow_dir", "session_dir"):
            if isinstance(row.get(name), str):
                values.add(os.path.basename(row[name]))
    for record in records:
        values.update(str(record.get(name)) for name in ("identity", "agent_id") if record.get(name))
    roots = bindings.get("roots") or {}
    values.update(str(item) for item in roots.values() if isinstance(item, str))
    values.update(str(item) for name in ("memory_index_roots", "instruction_anchors") for item in roots.get(name) or [])
    values.add(str(bindings.get("exec_checkout", "")))
    for arm in (bindings.get("arms") or {}).values():
        values.update(str(item) for item in (arm.get("worktree_paths") or {}).values())
        values.update(str(item.get("path")) for item in (arm.get("input_paths") or {}).values())
    for tree in ((bindings.get("codex") or {}).get("trees") or []):
        values.add(str(tree.get("path")))
    for entry in (bindings.get("sentinels") or {}).values():
        values.update(str(entry.get(name)) for name in ("value", "sibling_value") if entry.get(name))
    home = os.path.expanduser("~")
    values.update({home, os.path.basename(home.rstrip("/")), os.environ.get("USER", "")})
    return sorted(value for value in values if len(value) >= 8)


# --- END OF PART 6 ---
