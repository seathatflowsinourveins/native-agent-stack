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
            calls.append(dict(base, name=f"mcp__{item.get('server')}__{item.get('tool')}", tool=str(item.get("tool")),
                              server=item.get("server"), input=arguments,
                              state="succeeded" if status in (None, "completed") else "failed",
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


def is_memory_call(call):
    if call.get("server") == "ai-memory":
        return True
    text = command_text(call)
    return text is not None and has_program_word(text, "ai-memory")


def memory_check(calls, records):
    """R9 at grading: a hit counts only when a succeeded ai-memory call (MCP or CLI) of the attempt returns a result that
    resolves to a record frozen before SINCE, so a later arm's own session page never counts."""
    unobservable = False
    for call in calls:
        if not is_memory_call(call) or call["state"] != "succeeded":
            continue
        if call["result_text"] is None:
            unobservable = True
        elif any(resolves_to_record(call["result_text"], record) for record in records):
            return fc.ok()
    if unobservable:
        return fc.unknown("result_unobservable")
    return fc.fail("no_historical_hit")


def recovery_check(calls, digest, readings):
    """R2-17: the recovery is shown by a succeeded call of the child whose result, persisted output followed, carries the
    key digest. A failed or absent recovery fails (decided) or is unknown (alternative)."""
    for call in calls:
        if call["state"] == "succeeded" and isinstance(call["result_text"], str) and digest in call["result_text"].lower():
            return fc.ok()
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
    """M12: incomplete when the positive control shows no Read row; fail when a blind task lacks a passing verdict."""
    if positive_read_rows == 0:
        return {"status": "incomplete", "reason": "failed_positive_control"}
    if positive_read_rows is None:
        return {"status": "unknown", "reason": "control_rows_unobserved"}
    if any(item["status"] != "pass" for item in blind.values()):
        return {"status": "fail", "reason": "blind_task_without_clean_verdict"}
    return {"status": "pass", "reason": None}


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


# --- END OF PART 2 ---
