"""Class D judges for the #381 token E2E grader (unit U9, design R21): packets, scrubbing, the two blind routes,
calibration, and the checks every judgment must pass before a grade may use it.

A local integration tool, not upstream acceptance. Standard library only, Python 3.11+. Nothing here grades: it turns the
deterministic grading's pending class D clauses (and unparsed extractable facts) into packets, has a second-family model
judge them blind, verifies what comes back, and writes judgments that `grade --judgments` consumes as data.

Routes (U9-D3, U9-D8):
- `codex`: Claude answers are judged by gpt-6-astra at max effort through codex_lane's `build_command` with its
  ISOLATION_ARGS, a run-scoped Codex home with an empty HOME, `child_env` (BLIND_CHILD_PATH), the strict output schema,
  the packet inline and an empty per-item working directory. Any command, MCP, web or file item voids the judgment.
- `claude`: Codex answers are judged by Claude Opus at max effort through the saved Workflow frozen-check-judge.js with
  the blind-lane-reviewer role over file packets in a scrubbed export root; `collect` audits every transcript with
  transcript_audit and requires zero hook_additional_context rows.
Every judgment carries verbatim quotes that are checked, one same-family refuter per pass, blind calibration controls per
template and route, at most one retry and only for infrastructure failure. Judgments are retained, so `regrade` needs no
model. Sources: repair-u9.design.md R21 and R22, the binding corrections 7 and 10, tools/sota-convergence/codex_lane.py
(`build_command`, `ISOLATION_ARGS`, `isolated_codex_home`, `child_env`, `blind_path_issue`, `blind_child_argv`,
`blind_audit`, `strict_output_schema`) and transcript_audit.py (`audit`), reused unchanged, and adjudication-lane.js and
adjudicate.py as the pattern for a saved blind Workflow with a collect step.

Scanners are linear character scanners (no backtracking regular expressions): answer text is data from a model.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import evidence as ev  # noqa: E402
import frozen_checks as fc  # noqa: E402

cl = ev.sibling("sota-convergence", "codex_lane")
ta = ev.sibling("sota-convergence", "transcript_audit")

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
SCHEMA_FILE = HERE / "judgment.schema.json"
TEMPLATE_FILE = HERE / "judge-template.md"
SCRIPT_FILE = HERE / "frozen-check-judge.js"
CALIBRATION_DIR = HERE / "calibration"
ROLE_NAME = "blind-lane-reviewer"

# Correction 10: the effort is passed explicitly and this module never reads the lane's default.
JUDGE_MODEL = "gpt-6-astra"
JUDGE_EFFORT = "max"
MAX_ATTEMPTS = 2  # the first try and at most one retry, only for infrastructure failure (R21)
MAX_PACKET_BYTES = 50000  # the large-Read hook tip fires above 50,000 bytes; a packet stays under it
SECTION_CHARS = 12000
CALL_TIMEOUT = 900.0
PACKET_SCHEMA = "token-e2e-judge-packet/1"
INDEX_SCHEMA = "token-e2e-judge-index/1"
CALIBRATION_SCHEMA = "token-e2e-calibration/1"
ROUTES = ("codex", "claude")
ROUTE_ORDER = {"codex": 0, "claude": 1}
USAGE_KEYS = ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens")
CLAUDE_USAGE_KEYS = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")
PAUSED = 75  # exit status of a judge run stopped by a usage limit: resumable, never a failure
EXTRACT_COMPONENT = dict({"T0": "unittest", "T9": "payload"}, **{name: "payload" for name in fc.WEB_TEMPLATES})
EXTRACT_REQUEST = {
    "payload": ("Copy verbatim, from the answer, the structured representation (JSON or TOON) that the answer presents as "
                "the requested records. Put the exact text in answer_quotes and the same text in values."),
    "unittest": ("Copy verbatim, from the answer, the words that state how many tests ran and how the run ended, with any "
                 "skipped, failure or error counts. Put the exact text in answer_quotes and the same text in values."),
}
MODEL_NAMES = ("claude", "codex", "anthropic", "openai", "gpt-6-astra", "gpt-6", "opus", "sonnet", "haiku", "arm A0", "arm A",
               "arm B", "arm N", "arm T")
ID_KEYS = ("identity", "workflow_dir", "session_dir", "tool_use_id", "transcript", "events_file", "thread_id",
           "parent_thread_id", "parent_events_file", "session_id", "agent_id", "label")


def now_seconds():
    return time.time()


# ---- Schemas and strict-mode checks -----------------------------------------------------------------------------------

_SCHEMA = {}


def load_judgment_schema():
    if "judgment" not in _SCHEMA:
        with open(SCHEMA_FILE, encoding="utf-8") as stream:
            _SCHEMA["judgment"] = json.load(stream)
    return _SCHEMA["judgment"]


def _typed(**properties):
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


REFUTATION_SCHEMA = _typed(refuted={"type": "boolean"}, reason={"type": "string"}, quote={"type": "string"},
                           leak={"type": "boolean"}, leak_text={"type": "string"})


def strict_issues(schema, path="schema"):
    """What would make Codex strict structured output reject a schema, or leave a field untyped: a keyword the strict form
    drops, a missing type, an object that is not closed, and a `required` list that is not every property."""
    issues = []
    if not isinstance(schema, dict):
        return issues
    for keyword in sorted(schema):
        if keyword in cl.STRICT_UNSUPPORTED_KEYWORDS:
            issues.append(f"{path}: unsupported keyword {keyword}")
    kind = schema.get("type")
    if kind is None:
        issues.append(f"{path}: no type")
    if kind == "object":
        properties = schema.get("properties")
        if not isinstance(properties, dict):
            issues.append(f"{path}: object without properties")
        else:
            if schema.get("additionalProperties") is not False:
                issues.append(f"{path}: additionalProperties must be false")
            if sorted(schema.get("required") or []) != sorted(properties):
                issues.append(f"{path}: required must list every property")
            for name in sorted(properties):
                issues += strict_issues(properties[name], f"{path}.{name}")
    elif kind == "array":
        if not isinstance(schema.get("items"), dict):
            issues.append(f"{path}: array without items")
        else:
            issues += strict_issues(schema["items"], f"{path}[]")
    return issues


def conforms(instance, schema):
    """The closed, complete subset the two schemas use: an object has exactly its properties, every one typed."""
    kind = schema.get("type")
    if kind == "object":
        properties = schema["properties"]
        return isinstance(instance, dict) and set(instance) == set(properties) \
            and all(conforms(instance[name], sub) for name, sub in properties.items())
    if kind == "array":
        return isinstance(instance, list) and all(conforms(item, schema["items"]) for item in instance)
    if kind == "string":
        return isinstance(instance, str)
    if kind == "boolean":
        return isinstance(instance, bool)
    return False


# ---- Quotes, leaks and the refuter's turn -------------------------------------------------------------------------------

def verbatim(needle, haystack):
    """A quote is verbatim when it is non-empty and a contiguous, exact substring."""
    return isinstance(needle, str) and needle != "" and needle in haystack


def is_leak(value):
    return isinstance(value, dict) and value.get("leak") is True


def needs_refuter(judged):
    """The grading block's refute setting is passes_only: a judgment with at least one clause where every clause holds."""
    clauses = judged.get("clauses") or []
    return bool(clauses) and all(clause.get("holds") is True for clause in clauses)


def _unknown(reason):
    return {"status": "unknown", "reason": reason, "clauses": [], "extractions": []}


def _packet_strings(packet):
    return [packet["task"]] + [clause["text"] for clause in packet["clauses"]] + [section["text"] for section in packet["sources"]] \
        + [packet["answer"]] + list(packet["evidence"])


def check_judgment(judgment, packet, scrubbed=None):
    """R21: {status ok | unknown, reason, clauses, extractions}. A quote that is not verbatim in the packet is
    unknown(judge_quote), a leak unknown(judge_leak); extraction quotes and values are mapped back to the raw answer text
    (the packet holds the scrubbed one) so the grader's own oracle can verify them again. Never a pass on a doubt."""
    if not conforms(judgment, load_judgment_schema()):
        return _unknown("judge_schema")
    if is_leak(judgment):
        return _unknown("judge_leak")
    wanted = [clause["id"] for clause in packet["clauses"]]
    got = [clause["id"] for clause in judgment["clauses"]]
    if sorted(got) != sorted(wanted):
        return _unknown("judge_schema")
    answers = [packet["answer"]] + list(packet["evidence"])
    sources = [section["text"] for section in packet["sources"]]
    for clause in judgment["clauses"]:
        holds, answer_quote, source_quote = clause["holds"], clause["answer_quote"], clause["source_quote"]
        if holds and not (verbatim(answer_quote, packet["answer"]) or any(verbatim(answer_quote, item) for item in answers)):
            return _unknown("judge_quote")
        if answer_quote and not any(verbatim(answer_quote, item) for item in answers):
            return _unknown("judge_quote")
        if (holds and sources and not source_quote) or (source_quote and not any(verbatim(source_quote, item) for item in sources)):
            return _unknown("judge_quote")
    requested = {item["component"] for item in packet["extractions"]}
    extractions = []
    for item in judgment["extractions"]:
        if item["component"] not in requested:
            return _unknown("judge_schema")
        raw_quotes, raw_values = [], []
        for quote in item["answer_quotes"]:
            if not verbatim(quote, packet["answer"]):
                return _unknown("judge_quote")
            raw = scrubbed.to_raw(quote) if scrubbed is not None else quote
            if raw is None:
                return _unknown("judge_quote")
            raw_quotes.append(raw)
        for value in item["values"]:
            if not any(verbatim(value, quote) for quote in item["answer_quotes"]):
                return _unknown("judge_quote")
            raw = scrubbed.to_raw(value) if scrubbed is not None else value
            if raw is None:
                return _unknown("judge_quote")
            raw_values.append(raw)
        extractions.append({"component": item["component"], "values": raw_values, "answer_quotes": raw_quotes})
    return {"status": "ok", "reason": None, "extractions": extractions,
            "clauses": [{"id": clause["id"], "holds": clause["holds"], "answer_quote": clause["answer_quote"],
                         "source_quote": clause["source_quote"]} for clause in judgment["clauses"]]}


def check_refutation(refutation, packet):
    """A refutation that stands makes the pass unknown(judge_refuted); one whose quote is not verbatim in the packet is
    unknown(judge_quote); a leak is unknown(judge_leak). {status ok, reason None} means the pass survived."""
    if not conforms(refutation, REFUTATION_SCHEMA):
        return {"status": "unknown", "reason": "judge_schema"}
    if is_leak(refutation):
        return {"status": "unknown", "reason": "judge_leak"}
    if refutation["refuted"]:
        quote = refutation["quote"]
        if quote and not any(verbatim(quote, text) for text in _packet_strings(packet)):
            return {"status": "unknown", "reason": "judge_quote"}
        return {"status": "unknown", "reason": "judge_refuted"}
    return {"status": "ok", "reason": None}


# ---- Scrubbing (R21): paths, identities and tool names never reach the other provider ---------------------------------------

_ALNUM = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
_HEX = frozenset("0123456789abcdefABCDEF")
_PATH_CHARS = _ALNUM | frozenset("._~%+@=,:-/")
_PATH_BOUNDARY = frozenset(" \t\r\n'\"([{=<>,;|`")


def _uuid_at(text, index):
    if index + 36 > len(text):
        return 0
    for offset in range(36):
        char = text[index + offset]
        if offset in (8, 13, 18, 23):
            if char != "-":
                return 0
        elif char not in _HEX:
            return 0
    return 36


def _run_of(text, index, allowed):
    end = index
    while end < len(text) and text[end] in allowed:
        end += 1
    return end - index


def _path_at(text, index):
    """Length of an absolute, home-relative, drive or file:// path starting at `index`, or 0."""
    char = text[index]
    before = text[index - 1] if index else ""
    if before and before not in _PATH_BOUNDARY:
        return 0
    if text.startswith("file://", index):
        length = 7
        while index + length < len(text) and text[index + length] not in " \t\r\n'\"":
            length += 1
        return length
    if text.startswith("$HOME/", index):
        return 5 + _run_of(text, index + 5, _PATH_CHARS)
    if char == "~" and text[index + 1:index + 2] == "/":
        return 1 + _run_of(text, index + 1, _PATH_CHARS)
    if char == "/" and index + 2 < len(text) and text[index + 1] in _ALNUM | frozenset("._~-"):
        run = _run_of(text, index, _PATH_CHARS)
        return run if run >= 3 else 0
    if char.isalpha() and text[index + 1:index + 2] == ":" and text[index + 2:index + 3] in ("\\", "/"):
        length = 3
        while index + length < len(text) and text[index + length] not in " \t\r\n'\"":
            length += 1
        return length
    return 0


class Scrubbed:
    """A scrubbed text and the spans that map it back: (scrubbed start, scrubbed end, raw start, raw end) per replacement."""

    def __init__(self, raw, text, spans):
        self.raw, self.text, self.spans = raw, text, [tuple(span) for span in spans]

    def _raw_offset(self, offset):
        delta = 0
        for start, end, raw_start, raw_end in self.spans:
            if offset <= start:
                break
            if offset < end:
                return None  # inside a replaced span: no raw text has this boundary
            delta = raw_end - end
        return offset + delta

    def to_raw(self, quote):
        """The raw text a scrubbed quote stands for, or None when the quote is absent or cuts through a replaced span."""
        if not isinstance(quote, str) or not quote:
            return None
        start = 0
        while True:
            at = self.text.find(quote, start)
            if at < 0:
                return None
            low, high = self._raw_offset(at), self._raw_offset(at + len(quote))
            if low is not None and high is not None:
                return self.raw[low:high]
            start = at + 1

    def to_dict(self):
        return {"raw": self.raw, "text": self.text, "spans": [list(span) for span in self.spans]}

    @classmethod
    def from_dict(cls, document):
        return cls(document["raw"], document["text"], document["spans"])


class Scrubber:
    """Replaces, in one left-to-right pass, the exact values (run token, identities, ids) with <id>, UUID and tool-call id
    shapes with <id>, absolute paths with <path>, and denylist, model, family and arm names with <tool> (case-insensitive,
    on alphanumeric boundaries, as the sealed denylist check treats underscores as separators)."""

    def __init__(self, values=(), denylist=()):
        self.values = {}
        for value in sorted({item for item in values if isinstance(item, str) and len(item) >= 4}, key=lambda v: (-len(v), v)):
            self.values.setdefault(value[0], []).append(value)
        self.names = {}
        for name in sorted({item for item in list(denylist) + list(MODEL_NAMES) if isinstance(item, str) and item},
                           key=lambda n: (-len(n), n.lower())):
            self.names.setdefault(name[0].lower(), []).append(name.lower())

    def _match(self, text, index):
        char = text[index]
        for value in self.values.get(char, ()):
            if text.startswith(value, index):
                return len(value), "<id>"
        if char in _HEX and _uuid_at(text, index):
            return 36, "<id>"
        for prefix in ("toolu_", "call_"):
            if text.startswith(prefix, index) and (index == 0 or text[index - 1] not in _ALNUM):
                run = _run_of(text, index + len(prefix), _ALNUM)
                if run >= 8:
                    return len(prefix) + run, "<id>"
        length = _path_at(text, index)
        if length:
            return length, "<path>"
        if char in _ALNUM and (index == 0 or text[index - 1] not in _ALNUM):
            for name in self.names.get(char.lower(), ()):
                end = index + len(name)
                if text[index:end].lower() == name and (end == len(text) or text[end] not in _ALNUM):
                    return len(name), "<tool>"
        return None

    def scrub(self, text):
        out, spans, index, size = [], [], 0, 0
        while index < len(text):
            found = self._match(text, index)
            if found:
                length, replacement = found
                spans.append((size, size + len(replacement), index, index + length))
                out.append(replacement)
                size += len(replacement)
                index += length
            else:
                out.append(text[index])
                size += 1
                index += 1
        return Scrubbed(text, "".join(out), spans)


def scrub_values(table, records):
    """The exact strings that name this run: the run token, every identity and id of the identity table and the records.
    The home directory and the user name are left to the canary (they are refused, not removed)."""
    values = {table.get("run", "")}
    for row in table.get("rows", []):
        for name in ID_KEYS:
            item = row.get(name)
            if isinstance(item, str) and item:
                values.add(item)
                values.add(os.path.basename(item.rstrip("/")))
    for record in records:
        for name in ("identity", "agent_id"):
            if record.get(name):
                values.add(str(record[name]))
    return sorted(value for value in values if len(value) >= 4)


# ---- Calibration files (R21) --------------------------------------------------------------------------------------------------

_CALIBRATION = {}


def calibrated_templates():
    return sorted((path.stem for path in CALIBRATION_DIR.glob("T*.json")), key=fc.template_order)


def load_calibration(template):
    """The frozen controls of one template (read-only), validated against the registry: its clauses must be the registry's."""
    if template not in _CALIBRATION:
        try:
            with open(CALIBRATION_DIR / f"{template}.json", encoding="utf-8") as stream:
                document = json.load(stream)
        except (OSError, ValueError):
            raise fc.Refusal("E_CALIBRATION", template=template) from None
        entry = fc.TEMPLATES.get(template)
        clause_ids = [f"c{number}" for number in range(1, len(document.get("clauses", [])) + 1)]
        good = (isinstance(document, dict) and document.get("schema") == CALIBRATION_SCHEMA and document.get("template") == template
                and entry is not None and document.get("clauses") == entry["clauses"]
                and all(item.get("kind") in ("reference", "paraphrased", "wrong") and sorted(item.get("expected", {})) == clause_ids
                        for item in document.get("controls", []))
                and all(item.get("component") in EXTRACT_REQUEST for item in document.get("extraction_controls", [])))
        if not good:
            raise fc.Refusal("E_CALIBRATION", template=template)
        _CALIBRATION[template] = document
    return _CALIBRATION[template]


def calibration_failures(calibration, verdicts):
    """Ids of the clause controls a judge misjudged: its verdicts must equal the planted expectation, and a control with no
    valid verdict counts as misjudged (R21: any misjudged control makes the template's D outcomes unknown)."""
    failed = []
    for control in calibration["controls"]:
        verdict = verdicts.get(control["id"])
        if verdict is None or dict(verdict.get("clauses") or {}) != control["expected"]:
            failed.append(control["id"])
    return sorted(failed)


def extraction_matches(extractions, control):
    got = sorted(value.strip() for item in extractions or [] if item.get("component") == control["component"]
                 for value in item.get("values", []))
    return got == sorted(value.strip() for value in control["expected"]["values"])


def extraction_failures(calibration, verdicts, present):
    """Ids of the extraction controls (among those `present` in the batch) whose extraction differs from the plant."""
    failed = []
    for control in calibration.get("extraction_controls") or []:
        if control["id"] not in present:
            continue
        verdict = verdicts.get(control["id"])
        if verdict is None or not extraction_matches(verdict.get("extractions"), control):
            failed.append(control["id"])
    return sorted(failed)


# ---- Source sections: the deterministic reference a judge compares an answer with ---------------------------------------------

def _bound(text):
    return text if len(text) <= SECTION_CHARS else text[:SECTION_CHARS] + "\n[truncated]"


def _sites(items):
    return "\n".join(f"{item[0]}:{item[1]}" for item in items or [])


def source_sections(template, key, exec_src=None, captures=None, recorded=None):
    """[{label, text}] for one template, from its frozen key and, where the key holds only a pointer, the pinned source. A
    memory task carries the frozen record's digest and the anti-pattern row, never any hit text (R21, RV-31)."""
    key, captures, recorded = key or {}, captures or {}, recorded or {}
    sections = []

    def add(label, text):
        if isinstance(text, str) and text.strip():
            sections.append({"label": label, "text": _bound(text)})

    def digests():
        records = key.get("memory_records") or []
        add("frozen historical record digests", "\n".join(
            f"record {number}: {str(record.get('content_sha256', ''))[:16]}" for number, record in enumerate(records, 1)))

    def catalog_lines(name):
        data = exec_src.read(key["catalog"]) if exec_src is not None and key.get("catalog") else None
        facts = [fact.lower() for fact in fc.TEMPLATES[name]["facts"]]
        if data is not None:
            lines = [line.strip() for line in data.decode("utf-8", errors="replace").split("\n")
                     if any(fact in line.lower() for fact in facts)]
            add(f"{key['catalog']} lines naming the facts", "\n".join(lines[:12]))

    if template == "T4":
        add("adoption/update.md pin lines", "\n".join(key.get("pin_lines") or []))
        add("adoption/bootstrap.md step 0", "\n".join(key.get("bootstrap_excerpt") or []))
        coverage = key.get("qmd_coverage")
        if isinstance(coverage, dict):
            add("index coverage of adoption/update.md", f"covered: {str(bool(coverage.get('covered'))).lower()}; "
                                                        f"queried: {str(bool(coverage.get('queried'))).lower()}")
    elif template == "T5":
        definition = key.get("def")
        if definition:
            add("definition", f"{definition[0]}:{definition[1]}-{definition[2]}")
        add("direct calls", _sites(key.get("name_calls")))
        add("attribute calls, not direct invocations", _sites(key.get("attr_calls")))
        add("imports", _sites(key.get("imports")))
        add("mentions in comments or strings, not invocations", _sites(key.get("mentions")))
    elif template == "T6":
        add("scripts/host_requests.py trust()", key.get("segment"))
        recipe = (key.get("files") or {}).get("recipes/host-request-lane.md") or []
        add("recipes/host-request-lane.md trust lines", "\n".join(line for line in recipe if "trust" in line.lower()))
    elif template == "T7":
        add("recipes/host-request-lane.md trust lines", "\n".join(key.get("trust_lines") or []))
        digests()
    elif template in ("T12", "T13"):
        facts = captures.get("stripe" if template == "T12" else "mcp") or {}
        add("canonical page facts (frozen captures)", "; ".join(f"{name}: {value}" for name, value in sorted(facts.items())))
    elif template == "T14":
        if recorded.get("t14"):
            detail = recorded["t14"]
            add("recorded run facts", f"sessions reported in the answer: {detail.get('reported')}; sessions that started "
                                      f"before the archive query: {detail.get('expected')}")
    elif template in fc.WEB_TEMPLATES:
        facts = dict(captures.get("json") or {})
        facts.update({name: value for name, value in (captures.get("pathlib") or {}).items()})
        add("documentation facts (frozen captures)", "; ".join(f"{name}: {value}" for name, value in sorted(facts.items())))
    elif template in fc.CATALOG_TEMPLATES:
        catalog_lines(template)
        add("anti-pattern log row", key.get("anti_pattern_row") or "")
        digests()
    elif template == "T28":
        add("opening hunk of the patch", "\n".join(key.get("opening_hunk") or []))
        add("diff facts", "; ".join(f"{name}: {key[name]}" for name in ("bytes", "files", "hunks", "added", "deleted") if name in key))
    elif template == "T37" and exec_src is not None:
        for path in ("fixtures/before.py", "fixtures/after.py"):
            data = exec_src.read(path)
            add(path, data.decode("utf-8", errors="replace") if data is not None else "")
    return sections


# ---- Packets ------------------------------------------------------------------------------------------------------------------

def render_packet(packet):
    return (json.dumps(packet, indent=1, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def _content_hash(packet):
    content = {name: value for name, value in packet.items() if name != "id"}
    return fc.sha256_hex(fc.canonical(content))


def _fit(packet):
    """Shrink the source sections until the packet is under the size cap; None when even that cannot make it fit (an
    answer is never cut: a truncated answer could be judged for what it no longer says)."""
    for limit in (SECTION_CHARS, 4000, 1500, 400, 0):
        if len(render_packet(packet)) < MAX_PACKET_BYTES:
            return packet
        for section in packet["sources"]:
            if len(section["text"]) > limit:
                section["text"] = section["text"][:limit] + "\n[truncated]"
    return packet if len(render_packet(packet)) < MAX_PACKET_BYTES else None


def route_of(task):
    """Claude answers are judged by the Codex route, Codex answers by the Claude route."""
    return "codex" if task["family"] == "claude" else "claude"


def needs_of(row, record, task, d_extract):
    """(has pending clauses, extraction components) of one graded record, or None when it needs no judge: a run that never
    answered, one that already fails deterministically, or one the oracles settled."""
    if record["class"] != "completed" or not record.get("answer") or record["actor"] not in ev.GRADED_ACTORS:
        return None
    parts = {part["id"]: part for part in row["components"]}
    clauses = "D" in task["classes"] and (parts.get("D") or {}).get("status") == "pending"
    extract = []
    component = EXTRACT_COMPONENT.get(task["template"])
    if d_extract and component and any(part["status"] == "unknown" and "unparsed" in (part["reason"] or "")
                                       for part in row["components"]):
        extract.append(component)
    return (bool(clauses), extract) if clauses or extract else None


def _real_packet(template, task_text, has_clauses, extract, sources, answer, evidence, scrubber):
    scrubbed_answer = scrubber.scrub(answer)
    packet = {"schema": PACKET_SCHEMA, "id": "", "task": scrubber.scrub(task_text).text,
              "clauses": [{"id": f"c{number}", "text": text} for number, text in enumerate(fc.TEMPLATES[template]["clauses"], 1)]
              if has_clauses else [],
              "extractions": [{"component": component, "request": EXTRACT_REQUEST[component]} for component in extract],
              "sources": [{"label": section["label"], "text": scrubber.scrub(section["text"]).text} for section in sources],
              "answer": scrubbed_answer.text, "evidence": [scrubber.scrub(item).text for item in evidence]}
    return packet, scrubbed_answer


def _control_packets(template, calibration, task_text, scrubber, want_extraction):
    """The blind calibration packets of one template: clause controls, and extraction controls when a real packet asks."""
    made = []
    for control in calibration["controls"]:
        packet = {"schema": PACKET_SCHEMA, "id": "", "task": scrubber.scrub(task_text).text,
                  "clauses": [{"id": f"c{number}", "text": text} for number, text in enumerate(calibration["clauses"], 1)],
                  "extractions": [], "sources": [{"label": section["label"], "text": scrubber.scrub(section["text"]).text}
                                                 for section in calibration["sources"]],
                  "answer": scrubber.scrub(control["answer"]).text, "evidence": [scrubber.scrub(i).text for i in control["evidence"]]}
        made.append((packet, {"id": control["id"], "kind": control["kind"], "expected": dict(control["expected"]),
                              "expected_extractions": []}))
    for control in (calibration.get("extraction_controls") or []) if want_extraction else []:
        answer = scrubber.scrub(control["answer"])
        if answer.text != control["answer"]:
            raise fc.Refusal("E_CALIBRATION", template=template)  # an extraction control must survive scrubbing unchanged
        packet = {"schema": PACKET_SCHEMA, "id": "", "task": scrubber.scrub(task_text).text, "clauses": [],
                  "extractions": [{"component": control["component"], "request": EXTRACT_REQUEST[control["component"]]}],
                  "sources": [], "answer": answer.text, "evidence": []}
        made.append((packet, {"id": control["id"], "kind": "extraction", "expected": {},
                              "expected_extractions": [{"component": control["component"],
                                                        "values": list(control["expected"]["values"]),
                                                        "answer_quotes": list(control["expected"]["answer_quotes"])}]}))
    return made


def assert_clean(packet, values):
    """R22 at packet time and again at dispatch: no gathered identifier value and no id shape may remain in a packet.
    Returns how many gathered values were checked."""
    checked = sorted({value for value in values if isinstance(value, str) and len(value) >= 8})
    strings = list(ev.all_strings(packet))
    joined = "\0".join(strings)
    if any(value in joined for value in checked) or any(ev.id_shape(text) for text in strings):
        raise fc.Refusal("E_PRIVACY")
    return len(checked)


def build_batch(spec, keys, bindings, table, records, rows, captures, task_texts, denylist, exec_src, block):
    """Every packet of the run: one per graded record that needs a judge, plus the calibration controls of each template on
    each route. Returns (entries, skipped, canary values); nothing is written and nothing refuses here but E_PRIVACY."""
    tasks = {task["id"]: task for task in spec["tasks"]}
    scrubber = Scrubber(scrub_values(table, records), denylist)
    canary = ev.canary_values(bindings, table, records)
    entries, skipped, templates = [], [], {}
    for record, row in zip(records, rows):
        task = tasks[record["task"]]
        need = needs_of(row, record, task, block["d_extract"])
        if need is None:
            continue
        has_clauses, extract = need
        template, route = task["template"], route_of(task)
        key = (keys.get("keys") or {}).get(task["id"], {}).get("key")
        pages = {}
        for kind in fc.PAGE_KINDS:
            page = ev._page(captures, "w-open", task["family"], kind)
            if page and page.get("facts"):
                pages[kind] = page["facts"]
        sections = source_sections(template, key, exec_src=exec_src, captures=pages, recorded=row.get("recorded"))
        made = _real_packet(template, task_texts.get(task["id"], ""), has_clauses, extract, sections,
                            record["answer"]["text"], record["answer"].get("evidence") or [], scrubber)
        packet, scrubbed = made
        identity = {"identity": record["identity"], "actor": record["actor"], "run_index": record["run_index"]}
        fitted = _fit(packet)
        if fitted is None:
            skipped.append(dict(identity, template=template, route=route, reason="too_large"))
            continue
        entries.append({"route": route, "kind": "real", "template": template, "packet": fitted, "scrubbed": scrubbed,
                        "control": None, "extract": list(extract), **identity})
        state = templates.setdefault((route, template), {"extract": False, "family": task["family"]})
        state["extract"] = state["extract"] or bool(extract)
    for (route, template), state in sorted(templates.items(), key=lambda item: (ROUTE_ORDER[item[0][0]], fc.template_order(item[0][1]))):
        calibration = load_calibration(template)
        family = "claude" if route == "codex" else "codex"
        task_text = next((task_texts[task["id"]] for task in spec["tasks"] if task["template"] == template
                          and task["family"] == family and task["id"] in task_texts), "")
        for packet, control in _control_packets(template, calibration, task_text, scrubber, state["extract"]):
            entries.append({"route": route, "kind": "control", "template": template, "packet": packet, "scrubbed": None,
                            "control": control, "extract": [item["component"] for item in packet["extractions"]],
                            "identity": None, "actor": None, "run_index": None})
    for entry in entries:
        entry["content_sha256"] = _content_hash(entry["packet"])
    entries.sort(key=lambda entry: (ROUTE_ORDER[entry["route"]], entry["content_sha256"]))
    for number, entry in enumerate(entries, 1):
        entry["packet"]["id"] = entry["id"] = f"p{number:04d}"
        assert_clean(entry["packet"], canary)
    return entries, skipped, canary


# ---- Windows, role and isolation preflights (R21) -----------------------------------------------------------------------------

def window_issue(windows, now):
    """The name of the first run window still open (now before its UNTIL), else None. Judges run after both windows close:
    Claude judge children would land in the projects root the sweeps scan, and GPT-6 judging draws on the Codex quota."""
    for name in ("W_C", "W_X"):
        until = fc.parse_utc((windows.get(name) or {}).get("until"))
        if until is None or now < until:
            return name
    return None


def role_issue():
    """The user-scope copy of the blind-lane-reviewer role must be byte-identical to the repository's (correction 7)."""
    try:
        repo_bytes = (REPO_ROOT / ".claude" / "agents" / f"{ROLE_NAME}.md").read_bytes()
    except OSError:
        return "repo_role_missing"
    try:
        user_bytes = (Path.home() / ".claude" / "agents" / f"{ROLE_NAME}.md").read_bytes()
    except OSError:
        return "user_copy_missing"
    return None if user_bytes == repo_bytes else "user_copy_differs"


def isolation_issue(work_dir, export):
    """Why a blind Codex judge cannot run: the run-scoped home cannot be set up (no native sign-in, a base that overlaps the
    work dir), a retrieval CLI resolves on the child's PATH, or codex is a shell-script launcher."""
    if cl.codex_home_issue(Path(work_dir)):
        return "codex_home"
    if cl.blind_path_issue():
        return "blind_path"
    if cl.codex_launch_issue():
        return "launcher"
    return None


def codex_argv(empty_dir, schema_path, out_path, prompt):
    """The judge's command line. The effort is the literal JUDGE_EFFORT and the model JUDGE_MODEL: never the lane default."""
    return cl.build_command(Path(empty_dir), Path(schema_path), Path(out_path), JUDGE_EFFORT, prompt, JUDGE_MODEL, cl.ISOLATION_ARGS)


# ---- Index and private files ----------------------------------------------------------------------------------------------------

def _write_private(path, data):
    fc.private_create(str(path), data if isinstance(data, bytes) else data.encode("utf-8"))


def _json_bytes(document):
    return (json.dumps(document, indent=1, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def read_index(index_dir):
    path = Path(index_dir) / "index.json"
    document = ev.read_json(path)
    if not isinstance(document, dict) or document.get("schema") != INDEX_SCHEMA:
        raise fc.Refusal("E_JUDGE_INDEX", reason="index")
    return document


def read_packet(index_dir, item):
    """The packet of an index entry; a file whose bytes changed since `packets` is refused before anything is dispatched."""
    path = Path(index_dir) / "packets" / f"{item['id']}.json"
    try:
        data = path.read_bytes()
    except OSError:
        raise fc.Refusal("E_JUDGE_PACKET", reason="missing") from None
    if fc.sha256_hex(data) != item["packet_sha256"]:
        raise fc.Refusal("E_JUDGE_PACKET", reason="changed")
    return json.loads(data.decode("utf-8"))


def _canary(index_dir):
    values = ev.read_json(Path(index_dir) / "canary.json")
    return values if isinstance(values, list) else []


def preflight_dispatch(index_dir, index, route, now=None):
    """The checks common to every dispatch: both run windows closed (a rehearsal runs before any window exists), every packet
    of the route unchanged and clean."""
    issue = None if index.get("rehearsal") else window_issue(index.get("windows") or {}, now_seconds() if now is None else now)
    if issue:
        raise fc.Refusal("E_WINDOW_OPEN", window=issue)
    canary = _canary(index_dir)
    packets = {}
    for item in index["packets"]:
        if item["route"] == route:
            packets[item["id"]] = read_packet(index_dir, item)
            assert_clean(packets[item["id"]], canary)
    return packets


# ---- The packets command --------------------------------------------------------------------------------------------------------

def cmd_packets(args, services):
    """`judge packets`: plan, scrub and write every packet and the index; nothing is created when a check refuses."""
    private, out = Path(args.private), Path(args.out_dir)
    services.refuse_output(out)
    context = ev.read_json(private / "context.json")
    if not isinstance(context, dict) or context.get("schema") != services.context_schema:
        raise fc.Refusal("E_JUDGE_INPUT", reason="private")
    copies = {}
    for name in ("spec.json", "keys.json", "bindings.json", "identity-table.json", "captures.json"):
        document = ev.read_json(private / name)
        if not isinstance(document, dict):
            raise fc.Refusal("E_JUDGE_INPUT", reason="private")
        copies[name] = document
    records, errors = ev.read_jsonl(private / "evidence.jsonl")
    if records is None or errors:
        raise fc.Refusal("E_JUDGE_INPUT", reason="private")
    if not services.spec_matches(private / "spec.json", args.repo):
        raise fc.Refusal("E_SPEC_MISMATCH")
    spec, keys, bindings, table, captures = (copies[name] for name in ("spec.json", "keys.json", "bindings.json",
                                                                          "identity-table.json", "captures.json"))
    export = Path(bindings["roots"]["judge_export_root"])
    issue = export_root_issue(export, bindings)
    if issue:
        raise fc.Refusal("E_EXPORT_DIR", reason=issue)
    prereg = fc.GitSources(args.repo, spec["preregistration"]["commit"]).read(fc.PREREG_PATH)
    if prereg is None:
        raise fc.Refusal("E_PREREG", reason="missing")
    document = fc.load_preregistration(prereg)
    denylist = document.get("no_tool_names_denylist")
    if not isinstance(denylist, list):
        raise fc.Refusal("E_PREREG", reason="denylist")
    task_texts = {task["id"]: task.get("task_text", "") for task in document["tasks"]}
    rows, _ = ev.evaluate(spec, keys, bindings, records, captures, {}, meta=context.get("meta") or {})
    exec_src = fc.GitSources(args.repo, bindings["exec_rev"])
    entries, skipped, canary = build_batch(spec, keys, bindings, table, records, rows, captures, task_texts, denylist,
                                           exec_src, spec["block"])
    fc.private_dir(str(out))
    for name in ("packets", "scrub", "results", "events", "work", "claude"):
        os.makedirs(out / name, mode=0o700, exist_ok=True)
    os.makedirs(export / "packets", mode=0o700, exist_ok=True)
    index_items, counts = [], {route: {"real": 0, "control": 0} for route in ROUTES}
    for entry in entries:
        data = render_packet(entry["packet"])
        _write_private(out / "packets" / f"{entry['id']}.json", data)
        if entry["route"] == "claude":
            _write_private(export / "packets" / f"{entry['id']}.json", data)
        if entry["scrubbed"] is not None:
            _write_private(out / "scrub" / f"{entry['id']}.json", _json_bytes(entry["scrubbed"].to_dict()))
        counts[entry["route"]][entry["kind"]] += 1
        item = {"id": entry["id"], "route": entry["route"], "kind": entry["kind"], "template": entry["template"],
                "identity": entry["identity"], "actor": entry["actor"], "run_index": entry["run_index"],
                "content_sha256": entry["content_sha256"], "packet_sha256": fc.sha256_hex(data),
                "clauses": [clause["id"] for clause in entry["packet"]["clauses"]], "extract": entry["extract"]}
        if entry["control"] is not None:
            item["control"] = entry["control"]
        index_items.append(item)
    _write_private(export / "README.txt", "Frozen-check judge packets. Each judge reads only the packet file named in its own "
                                          "task.\n")
    _write_private(out / "canary.json", _json_bytes(canary))
    index = {"schema": INDEX_SCHEMA, "spec_sha256": context["meta"]["spec_sha256"],
             "bindings_sha256": context["meta"]["bindings_sha256"], "keys_sha256": context["meta"]["keys_sha256"],
             "windows": bindings["windows"], "export_root": str(export), "packets": index_items, "skipped": skipped}
    _write_private(out / "index.json", _json_bytes(index))
    print(json.dumps(counts, sort_keys=True))
    return 0


def export_root_issue(export, bindings):
    """Why the judge export root cannot be used: it holds files already, lies inside a work tree, or inside the Claude root."""
    if fc.inside_git_work_tree(str(export)):
        return "work_tree"
    if os.path.isdir(export) and os.listdir(export):
        return "exists"
    if os.path.lexists(export) and not os.path.isdir(export):
        return "exists"
    claude_root = (bindings.get("roots") or {}).get("CLAUDE_ROOT")
    if claude_root and ev.under(str(export), claude_root):
        return "claude_root"
    return None


# ---- The codex route ---------------------------------------------------------------------------------------------------------------

def _load_results(index_dir, pid):
    return ev.read_json(Path(index_dir) / "results" / f"{pid}.json")


def _stage_file(index_dir, pid, stage):
    return Path(index_dir) / "results" / f"{pid}.{stage}.json"


def _usage_of(events):
    usage = cl.extract_events_summary(events)[1] if events else {}
    return {key: int(usage.get(key) or 0) for key in USAGE_KEYS}, bool(usage)


def _limit_reached(events):
    for event in events:
        if isinstance(event, dict) and event.get("type") in ("turn.failed", "error"):
            message = (event.get("error") or {}).get("message") if isinstance(event.get("error"), dict) else event.get("message")
            if ev.usage_limit_message(message):
                return True
    return False


def _tool_items(events):
    return [event for event in events if isinstance(event, dict) and event.get("type") == "item.completed"
            and isinstance(event.get("item"), dict) and event["item"].get("type") not in ("agent_message", "reasoning")]


def read_quota():
    """The live Codex capacity reading (`scripts/codex_quota.py --json`): recorded, never a gate (the user's rule)."""
    try:
        done = subprocess.run([sys.executable, "-B", str(REPO_ROOT / "scripts" / "codex_quota.py"), "--json", "--timeout", "20"],
                              capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=60)
        document = json.loads(done.stdout)
        return {"read": done.returncode in (0, 3) and "error" not in document, "reading": document}
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return {"read": False, "reading": None}


class CodexRun:
    """One run of the codex route over the index: the run-scoped home, the per-call bookkeeping and the resume state."""

    def __init__(self, index_dir, index, home, timeout):
        self.dir, self.index, self.home, self.timeout = Path(index_dir), index, home, timeout
        schema = self.dir / "work" / "judgment.schema.json"
        refute = self.dir / "work" / "refutation.schema.json"
        for path, document in ((schema, load_judgment_schema()), (refute, REFUTATION_SCHEMA)):
            if not path.exists():
                _write_private(path, _json_bytes(cl.strict_output_schema(document)))
        self.schemas = {"judge": schema, "refute": refute}
        sections = TEMPLATE_FILE.read_text(encoding="utf-8").split("<!-- refuter -->")
        self.templates = {"judge": sections[0].strip(), "refute": sections[1].strip()}

    def _event_path(self, pid, stage):
        number = 1
        while (self.dir / "events" / f"{pid}.{stage}.{number}.jsonl").exists():
            number += 1
        return self.dir / "events" / f"{pid}.{stage}.{number}.jsonl"

    def call(self, pid, stage, prompt):
        """One codex exec: {kind ok | infra | usage_limit | audit, value, usage, usage_recorded}."""
        work = self.dir / "work" / pid
        os.makedirs(work, mode=0o700, exist_ok=True)
        out_path = self.dir / "work" / f"{pid}.{stage}.out.tmp"
        out_path.unlink(missing_ok=True)
        argv = cl.blind_child_argv(codex_argv(work, self.schemas[stage], out_path, prompt))
        timed_out = False
        try:
            done = subprocess.run(argv, env=cl.child_env(self.home), stdin=subprocess.DEVNULL, capture_output=True, text=True,
                                  timeout=self.timeout)
            stdout, code = done.stdout or "", done.returncode
        except subprocess.TimeoutExpired as stop:
            stdout, code, timed_out = (stop.stdout or "") if isinstance(stop.stdout, str) else "", None, True
        except OSError:
            stdout, code = "", 127
        events_path = self._event_path(pid, stage)
        _write_private(events_path, stdout)
        events = cl.parse_events(stdout)
        usage, recorded = _usage_of(events)
        result = {"usage": usage, "usage_recorded": recorded, "value": None}
        if _limit_reached(events):
            return dict(result, kind="usage_limit")
        if timed_out or code != 0:
            return dict(result, kind="infra")
        try:
            value = json.loads(out_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return dict(result, kind="infra")
        finally:
            out_path.unlink(missing_ok=True)
        schema = load_judgment_schema() if stage == "judge" else REFUTATION_SCHEMA
        if not conforms(value, schema):
            return dict(result, kind="infra")
        report = cl.blind_audit(events_path, [str(work)])
        if _tool_items(events) or cl.audit_is_flagged(report):
            return dict(result, kind="audit", value=value)
        return dict(result, kind="ok", value=value)

    def stage(self, pid, stage, prompt):
        """A stage with its retry budget: {kind, value, calls, usage, usage_calls}. A finished stage is loaded, not repeated."""
        saved = ev.read_json(_stage_file(self.dir, pid, stage))
        if isinstance(saved, dict) and saved.get("kind") != "usage_limit":
            return saved
        calls, usage_calls, usage = 0, 0, {key: 0 for key in USAGE_KEYS}
        result = {"kind": "infra", "value": None}
        for _ in range(MAX_ATTEMPTS):
            result = self.call(pid, stage, prompt)
            calls += 1
            usage_calls += 1 if result["usage_recorded"] else 0
            usage = {key: usage[key] + result["usage"][key] for key in USAGE_KEYS}
            if result["kind"] != "infra":
                break
        stage_result = {"kind": result["kind"], "value": result["value"], "calls": calls, "usage": usage,
                        "usage_calls": usage_calls}
        if result["kind"] != "usage_limit":
            _write_private(_stage_file(self.dir, pid, stage), _json_bytes(stage_result))
        return stage_result

    def packet(self, item, packet, scrubbed):
        """Judge one packet (and refute a pass): the final result, or {"kind": "usage_limit"} to pause the run."""
        text = render_packet(packet).decode("utf-8").rstrip("\n")
        block = "Packet (JSON):\n" + text
        judged = self.stage(item["id"], "judge", self.templates["judge"].replace("{PACKET_BLOCK}", block))
        result = {"packet": item["id"], "route": "codex", "calls": judged["calls"], "usage": dict(judged["usage"]),
                  "usage_calls": judged["usage_calls"], "refuted": False, "leak": False, "unavailable": False}
        if judged["kind"] == "usage_limit":
            return {"kind": "usage_limit"}
        if judged["kind"] == "infra":
            return dict(result, **_unknown("judge_unavailable"), unavailable=True)
        if judged["kind"] == "audit":
            return dict(result, **_unknown("judge_audit"))
        checked = check_judgment(judged["value"], packet, scrubbed)
        if checked["reason"] == "judge_leak":
            return dict(result, **checked, leak=True)
        if checked["status"] == "ok" and needs_refuter(checked):
            prompt = self.templates["refute"].replace("{PACKET_BLOCK}", block).replace(
                "{JUDGMENT}", json.dumps({"clauses": judged["value"]["clauses"], "extractions": judged["value"]["extractions"]}))
            refuted = self.stage(item["id"], "refute", prompt)
            if refuted["kind"] == "usage_limit":
                return {"kind": "usage_limit"}
            result["calls"] += refuted["calls"]
            result["usage"] = {key: result["usage"][key] + refuted["usage"][key] for key in USAGE_KEYS}
            result["usage_calls"] += refuted["usage_calls"]
            if refuted["kind"] == "infra":
                return dict(result, **_unknown("judge_unavailable"), unavailable=True)
            if refuted["kind"] == "audit":
                return dict(result, **_unknown("judge_audit"))
            final = check_refutation(refuted["value"], packet)
            if final["status"] != "ok":
                return dict(result, **_unknown(final["reason"]), refuted=final["reason"] == "judge_refuted",
                            leak=final["reason"] == "judge_leak")
        return dict(result, **checked)


def _scrubbed_of(index_dir, item):
    document = ev.read_json(Path(index_dir) / "scrub" / f"{item['id']}.json")
    return Scrubbed.from_dict(document) if isinstance(document, dict) else None


def finalize_route(index, route, results, calls, usage, usage_calls, keys):
    """Judgment rows and the route summary from the per-packet results: calibration decides per template and route, a
    packet never run is unknown(judge_unavailable), and a template whose controls were misjudged (or never judged) turns
    its judged clauses into unknown(judge_calibration). Extraction controls gate the extractions only."""
    items = [item for item in index["packets"] if item["route"] == route]
    by_template = {}
    for item in items:
        by_template.setdefault(item["template"], []).append(item)
    failed_clauses, failed_extractions = set(), set()
    for template, group in sorted(by_template.items()):
        controls = [item for item in group if item["kind"] == "control"]
        if not controls:
            continue
        calibration = load_calibration(template)
        verdicts, present = {}, set()
        for item in controls:
            outcome = results.get(item["id"])
            control = item["control"]
            if item["extract"] and not control["expected"]:
                present.add(control["id"])
            if outcome and outcome.get("status") == "ok":
                verdicts[control["id"]] = {"clauses": {clause["id"]: clause["holds"] for clause in outcome["clauses"]},
                                           "extractions": outcome["extractions"]}
        if calibration_failures(calibration, verdicts):
            failed_clauses.add(template)
        if extraction_failures(calibration, verdicts, present):
            failed_extractions.add(template)
    rows, refuted, leaks, unavailable, judged_ok = [], 0, 0, 0, 0
    real = [item for item in items if item["kind"] == "real"]
    for item in real:
        outcome = results.get(item["id"]) or dict(_unknown("judge_unavailable"), unavailable=True, refuted=False, leak=False)
        row = {"kind": "judgment", "identity": item["identity"], "actor": item["actor"], "run_index": item["run_index"],
               "template": item["template"], "route": route, "packet": item["id"], "status": outcome["status"],
               "reason": outcome["reason"], "clauses": outcome["clauses"], "extractions": outcome["extractions"],
               "extraction_reason": None}
        refuted += 1 if outcome.get("refuted") else 0
        leaks += 1 if outcome.get("leak") else 0
        unavailable += 1 if outcome.get("unavailable") else 0
        if row["status"] == "ok" and item["template"] in failed_clauses:
            row.update(status="unknown", reason="judge_calibration", clauses=[], extractions=[])
        elif row["status"] == "ok" and row["extractions"] and item["template"] in failed_extractions:
            row.update(extractions=[], extraction_reason="judge_calibration")
        judged_ok += 1 if row["status"] == "ok" else 0
        rows.append(row)
    for entry in index.get("skipped") or []:
        if entry["route"] == route:
            unavailable += 1
            rows.append({"kind": "judgment", "identity": entry["identity"], "actor": entry["actor"],
                         "run_index": entry["run_index"], "template": entry["template"], "route": route, "packet": None,
                         **_unknown("judge_unavailable"), "extraction_reason": None})
    rows.sort(key=lambda row: (row["identity"], row["actor"], row["run_index"]))
    summary = {"kind": "route", "route": route, "calls": calls, "judgments": judged_ok, "refuted": refuted, "leaks": leaks,
               "calibration_failed_templates": sorted(failed_clauses | failed_extractions, key=fc.template_order),
               "unavailable": unavailable, "usage_recorded": usage_calls == calls, "usage": usage}
    return rows + [summary]


def _jsonl(rows):
    return "".join(json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n" for row in rows).encode("utf-8")


def _dispatch_codex(index_dir, index, packets, timeout):
    """Judge every packet of the codex route that has no result yet, in id order, inside the run-scoped home. Returns
    (paused, {packet id: result}): a usage limit stops the dispatch at once (a retained failed attempt, never a retry)."""
    items = [item for item in index["packets"] if item["route"] == "codex"]
    _write_private(index_dir / f"quota-{int(now_seconds())}-{len(list(index_dir.glob('quota-*.json')))}.json",
                   _json_bytes(read_quota()))
    paused = False
    with contextlib.ExitStack() as stack:
        stack.enter_context(cl.exclusive_run_lock(cl.work_run_lock(index_dir)))
        stack.enter_context(cl.exclusive_run_lock(cl.codex_home_lock(index_dir)))
        cl.sweep_stale_links(index_dir)
        try:
            home = cl.isolated_codex_home(index_dir)
        except cl.CodexHomeRefused:
            raise fc.Refusal("E_JUDGE_ISOLATION", check="codex_home") from None
        try:
            run = CodexRun(index_dir, index, home, timeout)
            for item in items:
                if isinstance(_load_results(index_dir, item["id"]), dict):
                    continue
                outcome = run.packet(item, packets[item["id"]], _scrubbed_of(index_dir, item))
                if outcome.get("kind") == "usage_limit":
                    paused = True
                    break
                _write_private(index_dir / "results" / f"{item['id']}.json", _json_bytes(outcome))
        finally:
            cl.release_codex_home(home)
    results = {item["id"]: _load_results(index_dir, item["id"]) for item in items}
    return paused, {pid: outcome for pid, outcome in results.items() if isinstance(outcome, dict)}


def _totals(results, keys):
    return (sum(outcome["calls"] for outcome in results.values()), sum(outcome["usage_calls"] for outcome in results.values()),
            {key: sum(outcome["usage"][key] for outcome in results.values()) for key in keys})


def cmd_codex(args, services):
    """`judge codex`: judge every packet of the codex route (Claude answers) with gpt-6-astra at max effort, blind and
    isolated. Exit 0 when the judgments are written, 75 when a usage limit paused the run (rerun to resume), 2 on a refusal."""
    index_dir = Path(args.index)
    index = read_index(index_dir)
    packets = preflight_dispatch(index_dir, index, "codex")
    out_path = index_dir / "judgments-codex.jsonl"
    if fc.path_exists(str(out_path)):
        raise fc.Refusal("E_PATH", reason="exists")
    issue = isolation_issue(index_dir, index.get("export_root"))
    if issue:
        raise fc.Refusal("E_JUDGE_ISOLATION", check=issue)
    paused, results = _dispatch_codex(index_dir, index, packets, args.timeout)
    if paused and not args.accept_unavailable:
        total = sum(1 for item in index["packets"] if item["route"] == "codex")
        print(json.dumps({"paused": True, "judged": len(results), "remaining": total - len(results)}, sort_keys=True))
        return PAUSED
    calls, usage_calls, usage = _totals(results, USAGE_KEYS)
    rows = finalize_route(index, "codex", results, calls, usage, usage_calls, None)
    _write_private(out_path, _jsonl(rows))
    judgments = [row for row in rows if row["kind"] == "judgment"]
    print(json.dumps({"route": "codex", "judgments": sum(1 for row in judgments if row["status"] == "ok"),
                      "unknown": sum(1 for row in judgments if row["status"] != "ok"), "calls": calls}, sort_keys=True))
    return 0


# ---- The claude route ------------------------------------------------------------------------------------------------------------------

def cmd_claude_args(args, services):
    """`judge claude-args`: the Workflow's scriptPath and args for the claude route, and the coordinator request that runs it."""
    index_dir = Path(args.index)
    index = read_index(index_dir)
    preflight_dispatch(index_dir, index, "claude")
    issue = role_issue()
    if issue:
        raise fc.Refusal("E_JUDGE_ROLE", reason=issue)
    print(json.dumps({"items": _write_claude_args(index_dir, index)}, sort_keys=True))
    return 0


def _write_claude_args(index_dir, index):
    """Write args.json (scriptPath, Workflow args, coordinator request) and snapshot.json; returns the item count."""
    export = index["export_root"]
    items = [{"name": item["id"], "path": os.path.join(export, "packets", f"{item['id']}.json"),
              "packet_sha256": item["packet_sha256"]} for item in index["packets"] if item["route"] == "claude"]
    prompt = TEMPLATE_FILE.read_text(encoding="utf-8")
    role = (REPO_ROOT / ".claude" / "agents" / f"{ROLE_NAME}.md").read_bytes()
    snapshot = {"items": items, "prompt_sha256": fc.sha256_hex(prompt), "role_sha256": fc.sha256_hex(role),
                "script_sha256": fc.sha256_hex(SCRIPT_FILE.read_bytes()), "export_root": export}
    snapshot["snapshot_id"] = fc.sha256_hex(fc.canonical(snapshot))
    workflow_args = {"repo": export, "items": items, "prompt": prompt, "snapshot_id": snapshot["snapshot_id"]}
    request = (f"First Read the file {os.path.join(export, 'README.txt')}, then run one Grep for the word packet under "
               f"{os.path.join(export, 'packets')}; only after both, call the Workflow tool once with scriptPath "
               f"{SCRIPT_FILE} and these args, unchanged: {json.dumps(workflow_args, sort_keys=True)}")
    document = {"scriptPath": str(SCRIPT_FILE), "args": workflow_args, "coordinator_request": request}
    _write_private(index_dir / "claude" / "args.json", _json_bytes(document))
    _write_private(index_dir / "claude" / "snapshot.json", _json_bytes(snapshot))
    return len(items)


def _hook_rows(path):
    rows, _ = ev.read_jsonl(path)
    return sum(1 for row in rows or [] if row.get("type") == "attachment"
               and isinstance(row.get("attachment"), dict) and row["attachment"].get("type") == "hook_additional_context")


def _transcript_usage(path):
    rows, _ = ev.read_jsonl(path)
    seen, usage, recorded = set(), {key: 0 for key in CLAUDE_USAGE_KEYS}, False
    for row in rows or []:
        message = row.get("message") if isinstance(row.get("message"), dict) else {}
        block = message.get("usage")
        if row.get("type") == "assistant" and isinstance(block, dict) and message.get("id") not in seen:
            seen.add(message.get("id"))
            recorded = True
            for key in CLAUDE_USAGE_KEYS:
                usage[key] += int(block.get(key) or 0)
    return usage, recorded


def cmd_collect(args, services):
    """`judge collect`: verify the Workflow's returned judgments against the claude-args snapshot, audit every agent
    transcript (reads confined to the packet, no tool but Read, Glob, Grep and the structured return, zero hook rows),
    apply the same checks as the codex route and write the judgments of the Codex answers."""
    index_dir = Path(args.index)
    index = read_index(index_dir)
    packets = preflight_dispatch(index_dir, index, "claude")
    issue = role_issue()
    if issue:
        raise fc.Refusal("E_JUDGE_ROLE", reason=issue)
    out_path = index_dir / "judgments-claude.jsonl"
    if fc.path_exists(str(out_path)):
        raise fc.Refusal("E_PATH", reason="exists")
    results, _, _ = _collect_results(index_dir, index, packets, args.result, args.transcripts)
    total_calls, usage_calls, usage = _totals(results, CLAUDE_USAGE_KEYS)
    rows = finalize_route(index, "claude", results, total_calls, usage, usage_calls, None)
    _write_private(out_path, _jsonl(rows))
    judgments = [row for row in rows if row["kind"] == "judgment"]
    print(json.dumps({"route": "claude", "judgments": sum(1 for row in judgments if row["status"] == "ok"),
                      "unknown": sum(1 for row in judgments if row["status"] != "ok"), "calls": total_calls}, sort_keys=True))
    return 0


def _collect_results(index_dir, index, packets, result_path, transcripts):
    """The per-packet results of one Workflow run: (results, audit report, hook rows in total). Refuses a result that is not
    the one claude-args gave (snapshot, prompt, repo, items)."""
    snapshot = ev.read_json(index_dir / "claude" / "snapshot.json")
    if not isinstance(snapshot, dict):
        raise fc.Refusal("E_JUDGE_RESULT", reason="snapshot")
    result = ev.read_json(result_path)
    if isinstance(result, dict) and "items" not in result and isinstance(result.get("result"), dict):
        result = result["result"]
    if not isinstance(result, dict) or result.get("snapshot_id") != snapshot["snapshot_id"]:
        raise fc.Refusal("E_JUDGE_RESULT", reason="snapshot")
    if not isinstance(result.get("prompt"), str) or fc.sha256_hex(result["prompt"]) != snapshot["prompt_sha256"]:
        raise fc.Refusal("E_JUDGE_RESULT", reason="prompt")
    if result.get("repo") != snapshot["export_root"]:
        raise fc.Refusal("E_JUDGE_RESULT", reason="repo")
    given = {item["name"]: item for item in snapshot["items"]}
    returned = {}
    for item in result.get("items") or []:
        name = item.get("name") if isinstance(item, dict) else None
        if name not in given or name in returned or item.get("packet_sha256") != given[name]["packet_sha256"] \
                or item.get("path") != given[name]["path"]:
            raise fc.Refusal("E_JUDGE_RESULT", reason="items")
        returned[name] = item
    audit_items = {name: {"marker": f"Packet file: {item['path']}", "roots": [item["path"]]} for name, item in given.items()}
    report = ta.audit(str(transcripts), audit_items, export=snapshot["export_root"], result=result)
    hooks, calls, usage_by_item, recorded_by_item = {}, {}, {}, {}
    for path in ta.transcript_files(str(transcripts)):
        prompt = ta._parse(path)[0]
        names = [name for name, item in audit_items.items() if item["marker"] in prompt]
        rows = _hook_rows(path)
        usage, recorded = _transcript_usage(path)
        for name in names[:1]:
            hooks[name] = hooks.get(name, 0) + rows
            calls[name] = calls.get(name, 0) + 1
            recorded_by_item[name] = recorded_by_item.get(name, True) and recorded
            usage_by_item[name] = {key: usage_by_item.get(name, {}).get(key, 0) + usage[key] for key in CLAUDE_USAGE_KEYS}
    results = {}
    for item in index["packets"]:
        if item["route"] != "claude":
            continue
        pid = item["id"]
        entry = returned.get(pid) or {}
        base = {"packet": pid, "route": "claude", "calls": calls.get(pid, 0), "refuted": False, "leak": False,
                "unavailable": False, "usage": usage_by_item.get(pid) or {key: 0 for key in CLAUDE_USAGE_KEYS},
                "usage_calls": calls.get(pid, 0) if recorded_by_item.get(pid, False) else 0}
        if pid in report["flagged_items"]:
            results[pid] = dict(base, **_unknown("judge_audit"))
        elif hooks.get(pid, 0):
            results[pid] = dict(base, **_unknown("judge_hook_rows"))
        elif isinstance(entry.get("leak"), dict) or is_leak(entry.get("judge")):
            results[pid] = dict(base, **_unknown("judge_leak"), leak=True)
        elif not isinstance(entry.get("judge"), dict):
            results[pid] = dict(base, **_unknown("judge_unavailable"), unavailable=True)
        else:
            checked = check_judgment(entry["judge"], packets[pid], _scrubbed_of(index_dir, item))
            if checked["status"] == "ok" and needs_refuter(checked):
                refutation = entry.get("refuter")
                if not isinstance(refutation, dict):
                    checked = dict(_unknown("judge_unavailable"), unavailable=True)
                else:
                    final = check_refutation(refutation, packets[pid])
                    if final["status"] != "ok":
                        checked = dict(_unknown(final["reason"]), refuted=final["reason"] == "judge_refuted",
                                       leak=final["reason"] == "judge_leak")
            results[pid] = dict(base, **checked)
            results[pid].setdefault("unavailable", False)
    return results, report, sum(hooks.values())


# ---- rehearse: two planted controls through a route, before Amendment 4 (design e8) --------------------------------------------

REHEARSAL_TASK = ("Answer from the Python json documentation: what is the default value of ensure_ascii for json.dumps, and "
                  "what does it change?")


def _rehearsal_entries(route):
    """The two planted controls of T16, one known pass (the reference-correct answer) and one known fail (a planted
    contradiction), as packets of `route`, mixed by content hash like any batch."""
    calibration = load_calibration("T16")
    made = _control_packets("T16", calibration, REHEARSAL_TASK, Scrubber(), False)
    picked = [pair for pair in made if pair[1]["kind"] == "reference"][:1] + [pair for pair in made if pair[1]["kind"] == "wrong"][:1]
    entries = [{"route": route, "kind": "control", "template": "T16", "packet": packet, "scrubbed": None, "control": control,
                "extract": [], "identity": None, "actor": None, "run_index": None} for packet, control in picked]
    for entry in entries:
        entry["content_sha256"] = _content_hash(entry["packet"])
    entries.sort(key=lambda entry: entry["content_sha256"])
    for number, entry in enumerate(entries, 1):
        entry["packet"]["id"] = entry["id"] = f"p{number:04d}"
    return entries


def _write_rehearsal(out, export, entries):
    for name in ("packets", "scrub", "results", "events", "work", "claude"):
        os.makedirs(out / name, mode=0o700, exist_ok=True)
    items = []
    for entry in entries:
        data = render_packet(entry["packet"])
        _write_private(out / "packets" / f"{entry['id']}.json", data)
        if export is not None:
            os.makedirs(export / "packets", mode=0o700, exist_ok=True)
            _write_private(export / "packets" / f"{entry['id']}.json", data)
        items.append({"id": entry["id"], "route": entry["route"], "kind": "control", "template": "T16", "identity": None,
                      "actor": None, "run_index": None, "content_sha256": entry["content_sha256"],
                      "packet_sha256": fc.sha256_hex(data), "clauses": ["c1"], "extract": [], "control": entry["control"]})
    if export is not None:
        _write_private(export / "README.txt", "Frozen-check judge rehearsal packets. Each judge reads only the packet file named "
                                              "in its own task.\n")
    _write_private(out / "canary.json", _json_bytes([]))
    index = {"schema": INDEX_SCHEMA, "rehearsal": True, "windows": {}, "export_root": str(export) if export is not None else None,
             "packets": items, "skipped": []}
    _write_private(out / "index.json", _json_bytes(index))
    return index


def _verdicts(index, results):
    """(known pass holds, known fail holds, judgments ok): what the judge said of the two planted controls."""
    def holds(kind):
        item = next(item for item in index["packets"] if item["control"]["kind"] == kind)
        outcome = results.get(item["id"]) or {}
        return outcome.get("status") == "ok" and bool(outcome.get("clauses")) and all(c["holds"] for c in outcome["clauses"])
    return holds("reference"), holds("wrong"), sum(1 for outcome in results.values() if outcome.get("status") == "ok")


def _version(program):
    try:
        done = subprocess.run([program, "--version"], capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=30)
        return done.stdout.strip().splitlines()[0][:80] if done.returncode == 0 and done.stdout.strip() else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def cmd_rehearse(args, services):
    """`judge rehearse`: run two planted controls through a route (no bindings, no windows: it runs before Amendment 4) and
    print a receipt of counts and booleans; the raw judgments and the tool versions stay in the private directory. The codex
    route runs the codex exec calls; the claude route prepares a two-item Workflow run (`--export-dir`) and, given `--result`
    and `--transcripts` from that run, collects and audits it. Exit 0 when the known pass holds and the known fail does not."""
    out = Path(args.out_dir)
    if args.route == "claude" and args.result:
        return _rehearse_collect(out, args)
    services.refuse_output(out)
    if args.route == "codex":
        issue = isolation_issue(out, None)
        if issue:
            raise fc.Refusal("E_JUDGE_ISOLATION", check=issue)
        entries = _rehearsal_entries("codex")
        fc.private_dir(str(out))
        index = _write_rehearsal(out, None, entries)
        packets = {item["id"]: read_packet(out, item) for item in index["packets"]}
        paused, results = _dispatch_codex(out, index, packets, args.timeout)
        pass_holds, fail_holds, judged = _verdicts(index, results)
        calls, usage_calls, _ = _totals(results, USAGE_KEYS)
        receipt = {"route": "codex", "model": JUDGE_MODEL, "effort": JUDGE_EFFORT, "judgments": judged,
                   "known_pass_holds": pass_holds, "known_fail_holds": fail_holds,
                   "schema_valid": len(results) == 2 and not any(item.get("unavailable") for item in results.values()),
                   "tool_items": sum(1 for item in results.values() if item.get("reason") == "judge_audit"),
                   "usage_recorded": usage_calls == calls}
        _write_private(out / "rehearsal-codex.json", _json_bytes({"receipt": receipt, "versions": {"codex": _version("codex")},
                                                                  "outcomes": results}))
        print(json.dumps(receipt, sort_keys=True))
        if paused:
            return PAUSED
        return 0 if pass_holds and not fail_holds and judged == 2 and receipt["schema_valid"] and not receipt["tool_items"] else 1
    if not args.export_dir:
        raise fc.Refusal("E_ARGS", field="export_dir")
    export = Path(args.export_dir)
    issue = export_root_issue(export, {})
    if issue:
        raise fc.Refusal("E_EXPORT_DIR", reason=issue)
    issue = role_issue()
    if issue:
        raise fc.Refusal("E_JUDGE_ROLE", reason=issue)
    entries = _rehearsal_entries("claude")
    fc.private_dir(str(out))
    index = _write_rehearsal(out, export, entries)
    print(json.dumps({"items": _write_claude_args(out, index)}, sort_keys=True))
    return 0


def _rehearse_collect(out, args):
    """The second step of the claude rehearsal: audit and check the Workflow's judgments of the two controls."""
    index = read_index(out)
    if not index.get("rehearsal"):
        raise fc.Refusal("E_JUDGE_INDEX", reason="index")
    issue = role_issue()
    if issue:
        raise fc.Refusal("E_JUDGE_ROLE", reason=issue)
    packets = preflight_dispatch(out, index, "claude")
    results, report, hook_rows = _collect_results(out, index, packets, args.result, args.transcripts)
    pass_holds, fail_holds, judged = _verdicts(index, results)
    receipt = {"route": "claude", "model": "opus", "effort": "max", "judgments": judged, "known_pass_holds": pass_holds,
               "known_fail_holds": fail_holds, "audit_clean": not report["flagged_items"] and not report["run_issue"],
               "hook_rows": hook_rows}
    _write_private(out / "rehearsal-claude.json", _json_bytes({"receipt": receipt, "versions": {"claude": _version("claude")},
                                                               "outcomes": results}))
    print(json.dumps(receipt, sort_keys=True))
    return 0 if pass_holds and not fail_holds and judged == 2 and receipt["audit_clean"] and not hook_rows else 1


def run_command(args, services):
    """Dispatch of `grade.py judge <command>`; `services` carries grade.py's shared helpers."""
    handlers = {"packets": cmd_packets, "codex": cmd_codex, "claude-args": cmd_claude_args, "collect": cmd_collect,
                "rehearse": cmd_rehearse}
    return handlers[args.judge_command](args, services)
