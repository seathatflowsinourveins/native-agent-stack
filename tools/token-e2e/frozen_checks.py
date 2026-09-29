"""Frozen-check kernel for the #381 token E2E grader (unit U9): registry, keys, pure oracles and captures.

This is a local integration tool, not upstream acceptance and not a model run. Standard library only, Python 3.11+.
It reads pinned Git content, runs the upstream TOON CLI 4.1.1 for strict decoding and curl for page captures, and
decides nothing about token savings: it grades answers against keys that were frozen before the answers existed.

Sources for the rules implemented here (each rule names its design id):
- The U9 build contract (repair-u9.design.md sections a3, a4, b2 R3-R5, R10, R12, R13, R19, R20) with the binding
  corrections (item 2: the T0 re-run is the arm's own command in a temporary copy of the tree, because
  `python3 -I -S` cannot import the tests package; item 3: the T14 query time is the first tool_use naming the whole
  word agentsview, because the shell parser's closed program set returns null for it) and the coordinator
  decisions U9-D1..D25.
- TOON spec v4.1.1 SPEC.md section 2, "JSON-model equality" (toon-format/spec, tag v4.1.1, commit 62f16b36):
  strings by Unicode scalar sequence without normalization, numbers by mathematical value, arrays in order, objects
  by ordered key sequence. JSON-type identity is added on top: a boolean never equals a number and "17" never
  equals 17. Decoding uses the TOON CLI 4.1.1 `--decode`, strict by default; `--no-strict` is never passed.
- JSON Schema 2020-12, validation vocabulary (https://json-schema.org/draft/2020-12/json-schema-validation): the
  subset the grading block uses (type, properties, required, additionalProperties, items, enum, const,
  minItems); any other keyword is refused so an unchecked keyword can never slip through.
- CPython ast, tokenize, json, hashlib, html.parser and unicodedata; git-status(1) porcelain v1 with -z; curl.

Answer text is data. Nothing in it is loaded, expanded, templated or executed, and every scanner below is a
linear character scanner (no backtracking regular expressions), so an answer can neither read a file nor stall
the grader.
"""
from __future__ import annotations

import ast
import collections
import datetime
import hashlib
import io
import json
import os
import shutil
import site
import subprocess
import sys
import tempfile
import tokenize
import unicodedata
from html.parser import HTMLParser

GRAMMAR = "g1"
FAMILY_ARMS = {"claude": ["B", "A", "A0"], "codex": ["B", "A", "N"]}
M8_LANES = ("symbol-references", "qmd", "ai-memory")
M9_LANES = ("repomix", "markitdown")  # the lanes of the seeded optional tasks; reported (M9), never gating


# ---- Refusals and results ---------------------------------------------------------------------------------------

class Refusal(Exception):
    """A refusal is `E_CODE field=value ...`: a code and field names, never a private value."""

    def __init__(self, code, /, **fields):  # positional-only: a field may itself be named `code` (E_IDENTITY_INVALID)
        self.code = code
        self.fields = fields
        super().__init__(" ".join([code] + [f"{name}={value}" for name, value in fields.items()]))


class Result:
    """A graded component: status pass | fail | unknown | pending, sorted reasons, and descriptive detail."""

    __slots__ = ("status", "reasons", "detail")

    def __init__(self, status, reasons=(), detail=None):
        self.status = status
        self.reasons = tuple(sorted(set(reasons)))
        self.detail = detail if detail is not None else {}

    def __repr__(self):
        return f"Result({self.status!r}, {self.reasons!r})"


def ok(**detail):
    return Result("pass", (), detail)


def fail(*reasons, **detail):
    return Result("fail", reasons, detail)


def unknown(*reasons, **detail):
    return Result("unknown", reasons, detail)


def pending(*reasons, **detail):
    return Result("pending", reasons, detail)


def combine(components):
    """Task-level outcome of a component dict: any fail fails, else any unknown or pending is unknown (R6)."""
    reasons, detail, status = [], {}, "pass"
    for name in sorted(components):
        result = components[name]
        detail[name] = result.detail
        if result.status == "pass":
            continue
        reasons.extend(result.reasons)
        if result.status == "fail":
            status = "fail"
        elif status != "fail":
            status = "unknown"
    return Result(status, reasons, detail)


Answer = collections.namedtuple("Answer", "text evidence")


def answer_text(value):
    """The one door through which an oracle reads answer text; it returns the text as data, never dereferenced."""
    return value.text


def answer_evidence(value):
    return tuple(value.evidence)


def canonical(document):
    """Canonical JSON bytes: sorted keys, compact separators, UTF-8 (R20)."""
    return json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_hex(data):
    return hashlib.sha256(data if isinstance(data, bytes) else data.encode("utf-8")).hexdigest()


def is_hex(text, length):
    return isinstance(text, str) and len(text) == length and all(char in "0123456789abcdef" for char in text)


# ---- Linear text scanners (grammar g1, R3) ----------------------------------------------------------------------

_DASHES = "‐‑‒–—―−﹘﹣－"
_DASH_TABLE = {ord(char): "-" for char in _DASHES}
_PATH_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_./-")
NUMBER_WORDS = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
                "nine": 9, "ten": 10}


def is_digit(char):
    return "0" <= char <= "9"


def is_word_char(char):
    return char.isalnum() or char == "_"


def fence_open(line):
    """(char, length, info) when the line opens a fenced block, else None."""
    stripped = line.lstrip(" \t")
    if stripped[:3] not in ("```", "~~~"):
        return None
    char = stripped[0]
    length = 0
    while length < len(stripped) and stripped[length] == char:
        length += 1
    info = stripped[length:].strip()
    if char == "`" and "`" in info:
        return None
    return char, length, info


def fence_close(line, char, length):
    stripped = line.strip()
    return len(stripped) >= length and all(item == char for item in stripped)


def fenced_blocks(text):
    """Fenced blocks of raw text: dicts with lang, body, start, end (line indexes) and closed."""
    lines = text.split("\n")
    blocks, index = [], 0
    while index < len(lines):
        opened = fence_open(lines[index])
        if opened is None:
            index += 1
            continue
        char, length, info = opened
        end = index + 1
        while end < len(lines) and not fence_close(lines[end], char, length):
            end += 1
        blocks.append({"lang": info.split()[0].lower() if info else "", "body": "\n".join(lines[index + 1:end]),
                       "start": index, "end": end, "closed": end < len(lines)})
        index = end + 1
    return blocks


def outside_fences(text):
    """The lines of raw text that are not inside a fenced block, as (index, line) pairs."""
    lines = text.split("\n")
    inside = set()
    for block in fenced_blocks(text):
        inside.update(range(block["start"], min(block["end"], len(lines) - 1) + 1))
    return [(index, line) for index, line in enumerate(lines) if index not in inside]


def code_spans(text):
    """Inline code spans of raw text outside fenced blocks: (line index, content, column of the opening backtick)."""
    spans = []
    for index, line in outside_fences(text):
        pos, size = 0, len(line)
        while pos < size:
            if line[pos] != "`":
                pos += 1
                continue
            run = pos
            while run < size and line[run] == "`":
                run += 1
            width = run - pos
            scan = run
            found = -1
            while scan < size:
                if line[scan] == "`":
                    end = scan
                    while end < size and line[end] == "`":
                        end += 1
                    if end - scan == width:
                        found = scan
                        break
                    scan = end
                else:
                    scan += 1
            if found < 0:
                pos = run
                continue
            spans.append((index, line[run:found], pos))
            pos = found + width
    return spans


def normalize(text):
    """Grammar g1: NFKC, dash variants to '-', emphasis and backticks stripped outside fenced blocks, spaces collapsed.

    Every '*' outside a fenced block is removed (emphasis markers, but also varargs and globs in inline code), so any
    comparison between an answer and a key string must send BOTH sides through normalize or flat; the oracles do."""
    text = unicodedata.normalize("NFKC", text).translate(_DASH_TABLE)
    out, fence = [], None
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if fence is not None:
            out.append(line)
            if fence_close(line, fence[0], fence[1]):
                fence = None
            continue
        opened = fence_open(line)
        if opened is not None:
            fence = opened[:2]
            out.append(line)
            continue
        out.append(" ".join(line.replace("*", "").replace("`", "").split()))
    return "\n".join(out)


def flat(text):
    """Normalized text with every whitespace run, newlines included, collapsed to one space."""
    return " ".join(normalize(text).split())


def word_positions(text, word, ignore_case=True):
    """Start offsets where `word` occurs as a whole word (word characters are letters, digits and '_')."""
    haystack = text.lower() if ignore_case else text
    needle = word.lower() if ignore_case else word
    found, start = [], 0
    while needle:
        index = haystack.find(needle, start)
        if index < 0:
            break
        before = haystack[index - 1] if index else ""
        after = haystack[index + len(needle)] if index + len(needle) < len(haystack) else ""
        if not (before and is_word_char(before)) and not (after and is_word_char(after)):
            found.append(index)
        start = index + 1
    return found


def has_word(text, word, ignore_case=True):
    return bool(word_positions(text, word, ignore_case))


def iter_words(text):
    """(start, end, word) for every maximal run of word characters."""
    index, size = 0, len(text)
    while index < size:
        if not is_word_char(text[index]):
            index += 1
            continue
        end = index
        while end < size and is_word_char(text[end]):
            end += 1
        yield index, end, text[index:end]
        index = end


def int_tokens(text):
    """Standalone integers: {value, start, end, parts, grouped}.

    A digit run touching a letter or '_' belongs to an identifier and is skipped; a dotted number (2.0.0rc5, 17.5) is
    skipped whole; 'd,ddd' groups are one number with thousands separators outside brackets, where a comma separates
    list items (so [64,128] is two integers), and `parts` keeps the separate readings.
    """
    tokens, size, index, depth = [], len(text), 0, 0
    while index < size:
        char = text[index]
        if char in "[({":
            depth += 1
        elif char in "])}":
            depth = max(0, depth - 1)
        elif char == "\n":
            depth = 0
        if not is_digit(char):
            index += 1
            continue
        end = index
        while end < size and is_digit(text[end]):
            end += 1
        before = text[index - 1] if index else ""
        after = text[end] if end < size else ""
        if (before and (before.isalpha() or before == "_")) or (after and (after.isalpha() or after == "_")):
            index = end
            continue
        if after == "." and end + 1 < size and is_digit(text[end + 1]):
            scan = end
            while scan < size and (is_digit(text[scan]) or (text[scan] == "." and scan + 1 < size
                                                            and is_digit(text[scan + 1]))):
                scan += 1
            index = scan
            continue
        digits, parts, grouped, stop = text[index:end], [int(text[index:end])], False, end
        if depth == 0 and end - index <= 3:
            scan = end
            while scan + 3 < size and text[scan] == "," and all(is_digit(item) for item in text[scan + 1:scan + 4]) \
                    and not (scan + 4 < size and is_digit(text[scan + 4])):
                digits += text[scan + 1:scan + 4]
                parts.append(int(text[scan + 1:scan + 4]))
                grouped = True
                scan += 4
            stop = scan
            if grouped and stop < size and (text[stop].isalpha() or text[stop] == "_"):
                digits, parts, grouped, stop = text[index:end], [int(text[index:end])], False, end
        tokens.append({"value": int(digits), "start": index, "end": stop, "parts": parts, "grouped": grouped})
        index = stop
    return tokens


def has_int(tokens, number):
    return any(token["value"] == number or (token["grouped"] and number in token["parts"]) for token in tokens)


def int_values(tokens):
    values = []
    for token in tokens:
        values.append(token["value"])
        if token["grouped"]:
            values.extend(token["parts"])
    return values


def _skip_back(text, index):
    while index > 0 and text[index - 1] in " \t":
        index -= 1
    return index


def count_before_noun(text, nouns):
    """Counts written directly before a noun: an integer, or a number word zero..ten (hyphenated compounds such as
    forty-nine are deliberately not recognised, so they stay unparsed)."""
    wanted = {noun.lower() for noun in nouns}
    tokens = int_tokens(text)
    ends = {token["end"]: token for token in tokens}
    found = []
    for start, end, word in iter_words(text):
        if word.lower() not in wanted:
            continue
        stop = _skip_back(text, start)
        if stop in ends:
            found.append(ends[stop]["value"])
            continue
        first = stop
        while first > 0 and is_word_char(text[first - 1]):
            first -= 1
        if first < stop and text[first:stop].lower() in NUMBER_WORDS and not (first > 0 and text[first - 1] == "-"):
            found.append(NUMBER_WORDS[text[first:stop].lower()])
    return found


_LINKING = {"is", "are", "was", "were", "of", "equals", "equal", "to", "at", "about", "totals", "total"}


def ints_by_label(text, label, nouns=(), link_or=True):
    """Integers written next to a label word: 'N label', 'N noun label', 'label: N', 'label noun: N', and, unless
    `link_or` is off, the alternatives joined to them by 'or' ("9 or 10", "exit code 1 or exit code 0")."""
    tokens = int_tokens(text)
    ends = {token["end"]: token for token in tokens}
    starts = {token["start"]: token for token in tokens}
    noun_set = {noun.lower() for noun in nouns}
    found = []
    for position in word_positions(text, label):
        stop = _skip_back(text, position)
        if stop in ends:
            found.append(ends[stop])
        else:
            first = stop
            while first > 0 and is_word_char(text[first - 1]):
                first -= 1
            if first < stop and text[first:stop].lower() in noun_set:
                back = _skip_back(text, first)
                if back in ends:
                    found.append(ends[back])
        scan = position + len(label)
        while scan < len(text) and text[scan] in " \t:=-(":
            scan += 1
        while True:
            word = ""
            probe = scan
            while probe < len(text) and is_word_char(text[probe]):
                probe += 1
            word = text[scan:probe].lower()
            if word and (word in noun_set or word in _LINKING) and not is_digit(word[0]):
                scan = probe
                while scan < len(text) and text[scan] in " \t:=-(":
                    scan += 1
                continue
            break
        if scan in starts:
            found.append(starts[scan])
    return _or_links(text, tokens, found) if link_or else found


def _delimited(text, low, high):
    """True when a clause boundary (newline, ';' or a sentence end) lies between two offsets."""
    span = text[low:high]
    return "\n" in span or ";" in span or ". " in span


_OR_WORDS = ("or", "vs", "versus")


def _or_links(text, tokens, chosen):
    """Integers joined to a chosen one by 'or' (either direction, within one clause): the alternatives of a hedge."""
    ordered = sorted(tokens, key=lambda token: token["start"])
    extra = []
    for token in chosen:
        pos = token["end"]
        while pos < len(text) and text[pos] in " \t)(":
            pos += 1
        word_end = pos
        while word_end < len(text) and text[word_end].isalpha():
            word_end += 1
        connector = text[pos:word_end].lower()
        if connector in _OR_WORDS or text[pos:pos + 1] == "/":
            after = word_end if connector in _OR_WORDS else pos + 1
            for other in ordered:
                if after <= other["start"] <= after + 40 and not _delimited(text, after, other["start"]):
                    extra.append(other)
                    break
        back = token["start"]
        while back > 0 and text[back - 1] in " \t(":
            back -= 1
        head = text[:back].rstrip(" \t").lower()
        if head.endswith(" or") or head.endswith("(or") or head in _OR_WORDS:
            cut = len(text[:back].rstrip(" \t")) - 2
            for other in reversed(ordered):
                if other["end"] <= cut and cut - 40 <= other["end"] and not _delimited(text, other["end"], cut):
                    extra.append(other)
                    break
    seen, merged = set(), []
    for token in list(chosen) + extra:
        if token["start"] not in seen:
            seen.add(token["start"])
            merged.append(token)
    return merged


def single(values, expected):
    """Single-valued fact: pass when every recognised value equals the key, hedge when they disagree and one equals it,
    wrong when none does, none when nothing was recognised (review H-1: a hedge never raises the lower bound)."""
    if not values:
        return "none"
    if all(value == expected for value in values):
        return "pass"
    if any(value == expected for value in values):
        return "hedge"
    return "wrong"


def decide(values, expected, reason, reasons):
    """Record a wrong single-valued fact as a failure reason; True when the fact is unparsed (absent or hedged)."""
    verdict = single(values, expected)
    if verdict == "wrong":
        reasons.add(reason)
        return False
    return verdict in ("none", "hedge")


def path_like(token):
    if len(token) < 4 or "." not in token:
        return False
    stem, _, extension = token.rpartition(".")
    return bool(stem) and 1 <= len(extension) <= 8 and extension[0].isalpha() and extension.isalnum()


def _read_int(text, index):
    end = index
    while end < len(text) and is_digit(text[end]):
        end += 1
    return (int(text[index:end]), end) if end > index else (None, index)


def citations(text):
    """`path:LINE`, `path:START-END`, `path, lines N-M` and `path (lines N-M)`: dicts path, start, end, pos."""
    found, size, index = [], len(text), 0
    while index < size:
        if text[index] not in _PATH_CHARS:
            index += 1
            continue
        end = index
        while end < size and text[end] in _PATH_CHARS:
            end += 1
        token, position = text[index:end], index
        index = end
        token = token.rstrip(".")
        if token.startswith("./"):
            token = token[2:]
        if not path_like(token):
            continue
        if end < size and text[end] == ":" and end + 1 < size and is_digit(text[end + 1]):
            start, stop = _read_int(text, end + 1)
            last = start
            if stop < size and text[stop] == "-" and stop + 1 < size and is_digit(text[stop + 1]):
                last, stop = _read_int(text, stop + 1)
            found.append({"path": token, "start": start, "end": last, "pos": position})
            index = stop
            continue
        scan = end
        while scan < size and text[scan] in ", (":
            scan += 1
        word_end = scan
        while word_end < size and text[word_end].isalpha():
            word_end += 1
        if text[scan:word_end].lower() in ("line", "lines"):
            scan = word_end
            while scan < size and text[scan] in " :":
                scan += 1
            start, stop = _read_int(text, scan)
            if start is not None:
                last = start
                if stop < size and text[stop] == "-" and stop + 1 < size and is_digit(text[stop + 1]):
                    last, stop = _read_int(text, stop + 1)
                found.append({"path": token, "start": start, "end": last, "pos": position})
                index = stop
    return found


def identifier_tokens(text):
    """Identifier-like word tokens with the character before and after each: (word, before, after)."""
    found = []
    for start, end, word in iter_words(text):
        if word[0].isdigit():
            continue
        found.append((word, text[start - 1] if start else "", text[end] if end < len(text) else ""))
    return found


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_utc(text):
    """Seconds since the epoch for an ISO-8601 UTC timestamp, or None."""
    if not isinstance(text, str):
        return None
    try:
        parsed = datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed.timestamp()


# ---- Readings (R5) and the grading-block schema (R20) -----------------------------------------------------------

# One table: the decided (harder) reading first, then the published alternatives in order. The schema's enums and
# the spec's `alternatives` are both derived from it. R2-01 gains `wrapper_with_extras` beyond the design's register
# (recheck finding on R4: a Workflow answer may put the records and the requested sum into one object).
READINGS = collections.OrderedDict([
    ("R2-01", ["root_array", "single_key_wrapper", "wrapper_with_extras"]),
    ("R2-02", ["ordered", "unordered"]),
    ("R2-03", ["full_segment", "def_line_range"]),
    ("R2-04", ["complete_and_precise", "precision_only"]),
    ("R2-05", ["sites_and_functions", "sites_only", "functions_only"]),
    ("R2-06", ["answer_elements", "element_contents"]),
    ("R2-07", ["all_B_with_check", "organic_only"]),
    ("R2-08", ["matched_all_per_family_and_pooled", "matched_organic", "pooled_only"]),
    ("R2-09", ["whole_word", "substring", "alnum_boundary"]),
    ("R2-10", ["completed_attempts", "every_recorded", "last_attempt"]),
    ("R2-11", ["read_tools_only", "mcp_skill_bash_only"]),
    ("R2-12", ["allowlist", "denylist"]),
    ("R2-13", ["packet_roots", "memory_index_roots"]),
    ("R2-14", ["any_row", "first_prompt_and_hook_context"]),
    ("R2-15", ["cli_encode", "any_toon_form"]),
    ("R2-16", ["unknown_in_denominator", "excluded"]),
    ("R2-17", ["fail", "unknown"]),
    ("R2-18", ["exact_url", "host_and_path_suffix"]),
    ("R2-19", ["subset", "equal"]),
    ("R2-20", ["fail", "unknown"]),
    ("R2-21", ["unknown_in_denominator", "excluded"]),
])
MEMORY_TASKS = ["reuse-296-07", "reuse-343-01", "seed-catalog-history-1", "seed-catalog-history-2",
                "seed-catalog-history-3", "seed-catalog-history-4", "seed-catalog-history-5"]
PAGE_KINDS = ["json", "pathlib", "stripe", "mcp"]


def alternatives(decided):
    return {name: [value for value in READINGS[name] if value != decided[name]] for name in READINGS}


def _string():
    return {"type": "string"}


def _object(properties, required=None):
    return {"type": "object", "properties": properties, "required": list(properties if required is None else required),
            "additionalProperties": False}


def grading_block_schema():
    """The JSON schema of the Amendment 4 `grading` block (design f2), derived from the readings table."""
    return {
        "type": "object",
        "properties": {
            "schema": {"const": "token-e2e-grading/1"},
            "tool": _object({"path": _string(), "revision": _string(),
                             "sha256": {"type": "object", "additionalProperties": _string()}}),
            "registry_sha256": _string(),
            "grammar": {"enum": [GRAMMAR]},
            "d_extract": {"type": "boolean"},
            "dropped_tasks": {"type": "array", "items": _string()},
            "readings": _object({name: {"enum": list(values)} for name, values in READINGS.items()}),
            "m12": _object({"marker": _string(), "attachment_allowlist": {"type": "array", "items": _string(),
                                                                          "minItems": 1}}),
            "memory": _object({task: _object({"query": _string(), "anchors": {"type": "array", "items": _string(),
                                                                                 "minItems": 1}})
                               for task in MEMORY_TASKS}),
            "memory_scope": _object({"workspace": _string(), "project": _string()}),
            "qmd": _object({"index": _string(), "collections": {"type": "array", "items": _string(), "minItems": 1}}),
            "pages": _object({kind: _string() for kind in PAGE_KINDS}),
            # The GPT-6 judge runs at max effort, never on codex_lane's default `high` (standing rule); the route is
            # frozen as design f2 lists it, so a block cannot name another model, role or effort.
            "judges": _object({
                "claude_answers": _object({"model": {"const": "gpt-6-astra"}, "effort": {"const": "max"}}),
                "codex_answers": _object({"agent_type": {"const": "blind-lane-reviewer"}, "model": {"const": "opus"},
                                          "effort": {"const": "max"}}),
                "refute": {"enum": ["passes_only"]},
                "calibration": _object({"correct": {"type": "integer"}, "paraphrased": {"type": "integer"},
                                        "wrong": {"type": "integer"}}),
                "retries": {"type": "integer"}}),
        },
        "required": ["schema", "tool", "registry_sha256", "grammar", "d_extract", "dropped_tasks", "readings", "m12",
                     "memory", "memory_scope", "qmd", "pages", "judges"],
        "additionalProperties": False,
    }


_SCHEMA_KEYWORDS = {"type", "properties", "required", "additionalProperties", "items", "enum", "const", "minItems"}


def _type_ok(value, name):
    if name == "object":
        return isinstance(value, dict)
    if name == "array":
        return isinstance(value, list)
    if name == "string":
        return isinstance(value, str)
    if name == "boolean":
        return isinstance(value, bool)
    if name == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    return False


def _check_schema_keywords(schema):
    for keyword, value in schema.items():
        if keyword not in _SCHEMA_KEYWORDS:
            raise Refusal("E_SCHEMA", keyword=keyword)
        if keyword == "properties":
            for sub in value.values():
                _check_schema_keywords(sub)
        elif keyword == "items" or (keyword == "additionalProperties" and isinstance(value, dict)):
            _check_schema_keywords(value)


def validate_schema(instance, schema, path=""):
    """Validate against the supported keyword subset; refuse `E_GRADING_BLOCK field=<dotted path>` on the first failure."""
    if not path:
        _check_schema_keywords(schema)

    def refuse(where):
        raise Refusal("E_GRADING_BLOCK", field=where or "block")

    if "const" in schema and instance != schema["const"]:
        refuse(path)
    if "enum" in schema and instance not in schema["enum"]:
        refuse(path)
    if "type" in schema and not _type_ok(instance, schema["type"]):
        refuse(path)
    if isinstance(instance, dict):
        properties = schema.get("properties", {})
        for name in schema.get("required", []):
            if name not in instance:
                refuse(f"{path}.{name}" if path else name)
        for name, value in instance.items():
            where = f"{path}.{name}" if path else name
            if name in properties:
                validate_schema(value, properties[name], where)
            elif schema.get("additionalProperties") is False:
                refuse(where)
            elif isinstance(schema.get("additionalProperties"), dict):
                validate_schema(value, schema["additionalProperties"], where)
    if isinstance(instance, list):
        if len(instance) < schema.get("minItems", 0):
            refuse(path)
        if "items" in schema:
            for number, value in enumerate(instance):
                validate_schema(value, schema["items"], f"{path}.{number}" if path else str(number))


def validate_grading_block(block):
    """The schema, then the hex fields the schema cannot express: E_GRADING_BLOCK field=<dotted path> either way."""
    validate_schema(block, grading_block_schema())
    if not is_hex(block["tool"]["revision"], 40):
        raise Refusal("E_GRADING_BLOCK", field="tool.revision")
    for name, digest in block["tool"]["sha256"].items():
        if not is_hex(digest, 64):
            raise Refusal("E_GRADING_BLOCK", field=f"tool.sha256.{name}")
    if not is_hex(block["registry_sha256"], 64):
        raise Refusal("E_GRADING_BLOCK", field="registry_sha256")
    for kind, url in block["pages"].items():
        if not url.startswith(("https://", "http://")):  # curl also reads file:// and other schemes
            raise Refusal("E_GRADING_BLOCK", field=f"pages.{kind}")
    for task, topic in block["memory"].items():
        if topic["query"].startswith("-"):  # a query is a positional argument and must not parse as an option
            raise Refusal("E_GRADING_BLOCK", field=f"memory.{task}.query")


# ---- Registry (52 exact-text keys, 40 templates) and template classes (a3, a4) ----------------------------------

REGISTRY = {
    "c56e13ed1ee49f0e275523dc7141c2266fc9c8e121e4994dd29994c467009128": "T0",
    "8f260ed6d1e554e15a9377b90e78dae19cdcfc1e4a3de2b1240a3703f7482c79": "T1",
    "22d1ad626b4a50f65833cc936a3d07f655648c1ae0ca2c517ed16211b5ac9f04": "T2",
    "d1c8162c6d6128ebcc6e28cbd08ef462b80932a4bbf78aabc6f10b7454f62a6e": "T3",
    "9983cc19986bd6957e9fc19f0e5cef81ce28a053f4100fc1d868b6e1800abaf5": "T4",
    "cab56a4ea362f22ab0c9bd8d734855759273d5ffb24ece232170e0817a757414": "T5",
    "3d6554f4cfcb1a9ddf80485f0e5056f27e7e812d9d492daf70d133cbe29a478c": "T6",
    "5b2b6bc0448d7454967e294bb5e295dfa827b2964543dd92439a67ea6a749a71": "T7",
    "6a49a6a4a177b519b5f47f5614c2b10d38fd10c152d179f6bc92b3e21ea455c7": "T8",
    "f2c924b49e3e31f209064427741252a29ce48e295c1c577682c36872ae3d2c05": "T9",
    "77626eca9cf84729bfe99e75a273a17aca5b980827ab886b3c10dbd00d434181": "T10",
    "072533e67955b09537f352bf472500d026d647dfbc2e642433052b01a84fe3bf": "T11",
    "e2aad544b5415a1461f00ac5c7b0b51ef87e68de059137599c1909cd7f53451e": "T12",
    "4628f1c5fcec7400d97e30377bc4c5a821e7d5da1bd84e4ca5d50e9b82c291f1": "T13",
    "0694c8ebd34aef8f5acaa0d6335135246b73c90ed840da7590554516c30ac2e1": "T14",
    "4edfde82b95e611e9417942b761dbc6eb8d6f472286711413735aaf96d39235c": "T15",
    "2d81a5e04a2114d9507768bf24b8b6524dce665ff1e19ad178bf90df8ca1da3b": "T16",
    "ab51c0b7f4c7835dbcf0b6750b8d7ae120511027854e606f2b7692c8ddbef97a": "T17",
    "1b465d468091412aefd338851c10b6020c41ead200f450ceb3147342892d6cc3": "T18",
    "a8144e81694599f108338796624c9d6c4e7e9627465a6175d557fb260079afa4": "T19",
    "8ca8401bce1f52d980fced788784eb7e3c987dbdc2748f6825ec3817920cac22": "T20",
    "c3f2366bf1f5715995e5435450300ab7435c5241a6c1479edced1104ed845a70": "T21",
    "1ef657c9510283a0500bfaa6227066401e150c92e356c8d6818d7a1360b90469": "T22",
    "c980f9d63344b73ad9304162949f812ad22a89c80d38813515f4fae07ee5e104": "T23",
    "da3071f2d2fffe50951843ac817e1bb4f684c4066d655fdd253a20961e66db4a": "T24",
    "f4aa5cb56f0710a396452e85663249775f1a6a7df142e0859462d65153944fce": "T25",
    "273433b983dbf790743e1579f2975b63dcb25e6b49c02e4594ece3a95314ce97": "T26",
    "e011294f7fbc8f32af403fcd6f91b267243e8e634f68a5c1f8214e9a3d5c0678": "T26",
    "87ba99e7d44f21f05c7a274af42587b15dd0f3f1c37b41d93394beb1fd00ce6f": "T26",
    "1dbc4291994954ea169ad137b625ac57cd212364dc3207ba5a24595971f23cba": "T26",
    "6bd1244649b7354979b6e76564c69dc56c06daea4344b1660744248becb72ad8": "T26",
    "a6f16f7365bbf187cd07766dcedecb093b336425a61a76f57113672e9b59cdfe": "T27",
    "072e1d701ffeadd90a2efb82e11ff2d03d7422706186f0c2abff65a60ff613c0": "T27",
    "7ddf9b72a2f678a3950a09697804198decc29d392728b2f7ef45c77d7b4b6e06": "T27",
    "86cd624866d8850cf05ec57da7c9adb137b7be58ac53598f7f6cec593333e9a6": "T27",
    "00451d98b755247893c907955553c241a69686d844271e354815ed6fff45bc7f": "T27",
    "bed544eb3299e353722ed2492b31f5e591a9ec17eb248c12aa36a0d48784b626": "T28",
    "ea13f7ad9cdfab1ca2a008c508d329798151c2dc1383e1e6b70c582291d3dd9a": "T29",
    "47ad637e7a6a7994ad291bf5ba50c01ab4feab4801c050468ac6e86e62d6136f": "T30",
    "746afd3634fb6e149b71dde4ff4c8df94acc0930a09300bf98084c6ac0eb7a6f": "T31",
    "93ab65dabb4fbd24b78a351738294472223b44bcf63103323d88c52ec300d4ea": "T32",
    "c018dae83c4acd7be5e9351b449b8bf0294f4b9d936359ea31378a4e8121d2e6": "T32",
    "7551a487563ff388469ce0a08296e68c2ebb105b5790fefce3e4a38dc7496a1a": "T32",
    "6535038c9d5f7207184eb689ec064fe8dc81a4176453b688191a34d9505119a7": "T32",
    "a5035b9c84f8251e35b0ea08657c79ea694880e514de366a847f4668dddc5e55": "T32",
    "617bc50c7cb13397d42537b96a4d75d9731adf95ce973d3ed8a3674c20fbb20e": "T33",
    "e84bf8b9b7bc8742add4edef8130bf9c6e8db62072a487323c9c782e338f5d68": "T34",
    "0a3af411c1a01bcf38798d23b2d25f9f2e3d811cef1ffd930500a579f9bca0dc": "T35",
    "1c3c2ebb211cd1b3ee5c617d04099738f3647eeaae11b2e064b068e49f8056a6": "T36",
    "a213c9751955b5bb95572084ae7acd5851e525631ab0288fd1518995c61e7dc3": "T37",
    "79655de5bedb025f3bbe372daa8c653dc46ddfec0f5c9f08f770c9d53988fc58": "T38",
    "a817c44069bb2177bd22287471557b1878f26efe1b054cd4856aa243144ab0d4": "T39",
}


def _template(tasks, classes, clauses=(), literals=(), facts=()):
    return {"tasks": list(tasks), "classes": classes, "clauses": list(clauses), "literals": list(literals),
            "facts": list(facts)}


_WEB_PROSE = ("ensure_ascii defaults to true; non-ASCII characters are escaped when true.",
              "allow_nan=false raises ValueError for NaN or infinity instead of emitting nonstandard values.",
              "Object/dictionary output keys are sorted; array order is not sorted by this option.",
              "JSONDecodeError identifies invalid JSON decoding.",
              "loads also accepts bytes and bytearray.")
_READ_TEXT = "pathlib.Path.read_text(encoding=...)"
_HISTORY_ROW = "Historical retrieval must contain a scoped result for "

# Class sets follow the a4 table: A independent originals, B a re-run or the observed tree, C the carrier structure
# (checked with the carrier in evidence.py), D a semantic clause settled by the blind second-family judge.
TEMPLATES = {
    "T0": _template(["reuse-296-00", "reuse-343-13"], "CBA", literals=["tests.test_host_requests"]),
    "T1": _template(["reuse-296-01", "reuse-343-05"], "CA"),
    "T2": _template(["reuse-296-02", "reuse-343-06"], "CA"),
    "T3": _template(["reuse-296-03", "reuse-343-07"], "CA"),
    "T4": _template(["reuse-296-04", "reuse-343-10"], "CAD",
                    clauses=["Answer agrees with adoption/update.md and its linked bootstrap step",
                             "an index coverage gap is stated rather than a fabricated catalog hit"],
                    literals=["adoption/update.md"], facts=["release_tag", "release_commit", "bootstrap"]),
    "T5": _template(["reuse-296-05", "reuse-343-14"], "CAD",
                    clauses=["Definition and each listed call site agree with original source",
                             "comments and string literals do not count as invocations"]),
    "T6": _template(["reuse-296-06", "reuse-343-15"], "CAD",
                    clauses=["Conditions agree with the frozen scripts/host_requests.py implementation and "
                             "recipes/host-request-lane.md"],
                    literals=["scripts/host_requests.py", "recipes/host-request-lane.md"]),
    "T7": _template(["reuse-296-07", "reuse-343-01"], "CAD",
                    clauses=["Retain an actual scoped historical hit and verify its claim against "
                             "recipes/host-request-lane.md", "no savings counter or current authority is inferred"],
                    literals=["recipes/host-request-lane.md"]),
    "T8": _template(["reuse-296-08", "reuse-343-12"], "CA", literals=["status_body"]),
    "T9": _template(["reuse-296-09", "reuse-343-16"], "CA"),
    "T10": _template(["reuse-296-10", "reuse-343-02"], "CA"),
    "T11": _template(["reuse-296-11", "reuse-343-03"], "CB"),
    "T12": _template(["reuse-296-12", "reuse-343-04"], "CAD",
                     clauses=["Report Idempotency-Key and the canonical page's retention qualification, or a "
                              "faithful content-gap result",
                              "a curated source lacking either fact cannot establish that capability"],
                     literals=["Idempotency-Key"]),
    "T13": _template(["reuse-296-13", "reuse-343-09"], "CAD",
                     clauses=["The answer states local, project and user and agrees with retained original HTML",
                              "preserve conversion omissions and exit status"],
                     literals=["local, project and user"]),
    "T14": _template(["reuse-296-14", "reuse-343-00"], "CBAD",
                     clauses=["Archive observations match the private run identity table",
                              "no absent automation is reported as observed and no owned process survives"]),
    "T15": _template(["reuse-296-15"], ""),
    "T16": _template(["seed-web-table-1", "seed-codex-web-table-1"], "CAD", clauses=[_WEB_PROSE[0]],
                     literals=[_READ_TEXT, "missing source evidence fails"]),
    "T17": _template(["seed-web-table-2", "seed-codex-web-table-2"], "CAD", clauses=[_WEB_PROSE[1]],
                     literals=[_READ_TEXT, "missing source evidence fails"]),
    "T18": _template(["seed-web-table-3", "seed-codex-web-table-3"], "CAD", clauses=[_WEB_PROSE[2]],
                     literals=[_READ_TEXT, "missing source evidence fails"]),
    "T19": _template(["seed-web-table-4", "seed-codex-web-table-4"], "CAD", clauses=[_WEB_PROSE[3]],
                     literals=[_READ_TEXT, "missing source evidence fails"]),
    "T20": _template(["seed-web-table-5", "seed-codex-web-table-5"], "CAD", clauses=[_WEB_PROSE[4]],
                     literals=[_READ_TEXT, "missing source evidence fails"]),
    "T21": _template(["seed-catalog-history-1"], "CAD",
                     clauses=["NautilusTrader 2.0.0rc5; IBKR; separate Alpaca boundary.",
                              _HISTORY_ROW + "stdin left open in unattended workers; compare with "
                              "docs/harness-defaults.md, Anti-pattern log: Close stdin for unattended launches; the "
                              "retained failure was waiting for input until timeout."],
                     literals=["catalogs/us-equities/README.md", "docs/harness-defaults.md"],
                     facts=["NautilusTrader", "2.0.0rc5", "IBKR", "Alpaca"]),
    "T22": _template(["seed-catalog-history-2"], "CAD",
                     clauses=["Default is preferred design/adoption, not installed; native_proven is only the cited "
                              "bounded behavior.",
                              _HISTORY_ROW + "filtered output mistaken for complete originals; compare with "
                              "docs/harness-defaults.md, Anti-pattern log: Exact originals and exit statuses require "
                              "raw recovery; a filtered window is not the full source."],
                     literals=["catalogs/us-equities/agents-operations.md", "docs/harness-defaults.md"],
                     facts=["native_proven"]),
    "T23": _template(["seed-catalog-history-3"], "CAD",
                     clauses=["Company FB to META before June 9, 2022 open; fund META to METV at January 31, 2022 "
                              "open; distinct identities.",
                              _HISTORY_ROW + "a wait loop matching its own command line; compare with "
                              "docs/harness-defaults.md, Anti-pattern log: Anchor or bracket the process pattern, or "
                              "wait on a PID/exit marker with a timeout."],
                     literals=["catalogs/us-equities/lifecycle-source-review.md", "docs/harness-defaults.md"],
                     facts=["META", "METV"]),
    "T24": _template(["seed-catalog-history-4"], "CAD",
                     clauses=["catalogs/us-equities -> us-equities-catalog; blueprints/us-equities -> "
                              "us-equities-foundation; unrelated folders are excluded.",
                              _HISTORY_ROW + "a pipeline masking the producing command's failure; compare with "
                              "docs/harness-defaults.md, Anti-pattern log: Retain stdout/stderr and the command's own "
                              "exit status; a downstream success is insufficient."],
                     literals=["catalogs/us-equities/native-workflows.md", "docs/harness-defaults.md"],
                     facts=["us-equities-catalog", "us-equities-foundation"]),
    "T25": _template(["seed-catalog-history-5"], "CAD",
                     clauses=["One primary memory store and one retrieval lane per artifact.",
                              _HISTORY_ROW + "assuming a worker owns an independent web-search budget; compare with "
                              "docs/harness-defaults.md, Anti-pattern log: The session search budget is shared across "
                              "the coordinator and its workers."],
                     literals=["catalogs/us-equities/foundation-memory.md", "docs/harness-defaults.md"],
                     facts=["primary memory store", "retrieval lane"]),
    "T26": _template(["seed-log-symbol-1", "seed-log-symbol-2", "seed-log-symbol-3", "seed-log-symbol-4",
                      "seed-log-symbol-5"], "CA",
                     literals=["answer lists each real site exactly once", "(excluding attribute calls)"]),
    "T27": _template(["seed-acceptance-1", "seed-acceptance-2", "seed-acceptance-3", "seed-acceptance-4",
                      "seed-acceptance-5"], "CBA",
                     literals=["PASS partition", "exit 0 and that exact summary are required"]),
    "T28": _template(["seed-review-diff"], "CAD",
                     clauses=["The opening contract removes the SIGINT/SIGTERM/SIGHUP cleanup sentence and the "
                              "SIGKILL/status-started exception, retaining the no-overwrite rule and a simpler "
                              "interrupted-run receipt guarantee."]),
    "T29": _template(["seed-scout-inventory"], "CA", literals=["Both files define greeting"]),
    "T30": _template(["seed-scout-acceptance"], "CBA", literals=["Both compile successfully"]),
    "T31": _template(["seed-builder-1", "seed-builder-2"], "CBA",
                     literals=["Only fixtures/before.py changes", "an empty diff from the prepared path cannot pass"]),
    "T32": _template(["seed-blind-1", "seed-blind-2", "seed-blind-3", "seed-blind-4", "seed-blind-5"], "CA",
                     literals=["Verdict yes; id", "strict process repeats the identical packet"]),
    "T33": _template(["seed-blind-positive"], "CA", literals=["each with level INFO"]),
    "T34": _template(["seed-main-output"], "CA", literals=["measure main-transcript bytes separately"]),
    "T35": _template(["seed-agent-path"], "CA", literals=["requested answer returns inline"]),
    "T36": _template(["seed-binding-1", "seed-binding-2", "seed-binding-3", "seed-binding-4", "seed-binding-5"], "CA",
                     literals=["Merely printing a directory path is insufficient."]),
    "T37": _template(["seed-overview"], "CAD",
                     clauses=["Names greeting and the added exclamation mark; confirm against both original files."]),
    "T38": _template(["seed-conversion"], "CA", literals=["All ten structure checks"]),
    "T39": _template(["seed-graph"], ""),
}
WEB_TEMPLATES = ("T16", "T17", "T18", "T19", "T20")
CATALOG_TEMPLATES = ("T21", "T22", "T23", "T24", "T25")


def check_key(text):
    """The registry key of one check text: the sha256 of its exact bytes (RV-23)."""
    return sha256_hex(text)


def registry_sha256():
    return sha256_hex(canonical({"registry": REGISTRY, "templates": TEMPLATES, "readings": READINGS,
                                 "grammar": GRAMMAR}))


def template_order(name):
    return int(name[1:])


def verify_clauses(templates, exact_texts):
    """E_CLAUSE: every D clause and recipe literal of a mapped template is a verbatim substring of every exact text
    that maps to it."""
    for name in sorted(exact_texts, key=template_order):
        entry = templates[name]
        for text in exact_texts[name]:
            for item in entry["clauses"] + entry["literals"]:
                if item not in text:
                    raise Refusal("E_CLAUSE", template=name)


def load_preregistration(prereg_bytes):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result
    try:
        document = json.loads(prereg_bytes.decode("utf-8"), object_pairs_hook=unique)
    except (ValueError, UnicodeDecodeError):
        raise Refusal("E_PREREG", reason="json") from None
    if not isinstance(document, dict) or not isinstance(document.get("tasks"), list):
        raise Refusal("E_PREREG", reason="tasks")
    return document


def _map_tasks(document, dropped_tasks, templates):
    """Map every task to its template by exact check text; enforce E_CHECK_UNMAPPED and E_TEMPLATE_TASKS."""
    dropped = set(dropped_tasks)
    mapped = collections.OrderedDict()
    exact = collections.OrderedDict()
    live = []
    for task in document["tasks"]:
        if task["id"] in dropped:
            raise Refusal("E_TEMPLATE_TASKS", reason="dropped_present", task=task["id"])
        key = check_key(task["pass_fail_check"])
        if key not in REGISTRY:
            raise Refusal("E_CHECK_UNMAPPED", task=task["id"])
        name = REGISTRY[key]
        mapped.setdefault(name, []).append(task["id"])
        exact.setdefault(name, set()).add(task["pass_fail_check"])
        live.append((task, name))
    declared_all = set()
    for name in sorted(templates, key=template_order):
        declared = set(templates[name]["tasks"])
        declared_all |= declared
        if not set(mapped.get(name, ())) <= declared:
            raise Refusal("E_TEMPLATE_TASKS", template=name)
        if not (declared - set(mapped.get(name, ()))) <= dropped:
            raise Refusal("E_TEMPLATE_TASKS", template=name)
    if not dropped <= declared_all:
        raise Refusal("E_TEMPLATE_TASKS", template="dropped")
    verify_clauses(templates, exact)
    return live, mapped, exact


def _first_ints(text, marker, count):
    index = text.find(marker)
    if index < 0:
        return []
    return [token["value"] for token in int_tokens(text[index + len(marker):])][:count]


def task_params(name, task):
    """Frozen fields the oracles need, derived from the preregistered task and never from an outcome."""
    if name in WEB_TEMPLATES:
        return {"range": _first_ints(task["task_text"], "return records ", 2), "urls": list(task["urls"]),
                "fixture_path": task["fixture_path"]}
    if name == "T26":
        return {"symbol": task["symbol"], "symbol_fixture": task["symbol_fixture"],
                "fixture_path": task["fixture_path"], "event_range": _first_ints(task["task_text"],
                                                                                   "inclusive range ", 2)}
    if name == "T27":
        argv = task["acceptance_argv"]
        partition = _first_ints(argv[-1], "PASS partition ", 1)
        return {"partition": partition[0] if partition else None, "fixture_path": task["fixture_path"],
                "acceptance_argv": list(argv)}
    if name == "T32":
        record = _first_ints(task["task_text"], "Does record ", 1)
        return {"record_id": record[0] if record else None, "fixture_path": task["fixture_path"]}
    if name in CATALOG_TEMPLATES:
        return {"catalog": task["fixture_path"], "historical_fixture": task["historical_fixture"]}
    if name == "T9":
        return {"frozen_input": task["frozen_input"]}
    if name in ("T3", "T5", "T11"):
        return {"symbol": "register_file", "symbol_fixture": "scripts/host_receipts.py"}
    if "fixture_path" in task:
        return {"fixture_path": task["fixture_path"]}
    return {}


def build_tasks(prereg_bytes, dropped_tasks, templates=None):
    """The graded tasks in preregistration order: template, classes and frozen fields (no outcome is read)."""
    templates = TEMPLATES if templates is None else templates
    document = load_preregistration(prereg_bytes)
    live, _, _ = _map_tasks(document, dropped_tasks, templates)
    graded = []
    for task, name in live:
        classes = templates[name]["classes"]
        if not classes:
            continue
        graded.append({
            "id": task["id"], "template": name, "classes": classes, "family": task["family"],
            "actor": task["actor"], "dispatch": task["dispatch"], "arms": list(task["arms"]),
            "opportunity": task["opportunity"], "lane_tags": list(task["lane_tags"]),
            "strict_repeat": bool(task.get("strict_repeat")), "check_sha256": check_key(task["pass_fail_check"]),
            "params": task_params(name, task)})
    return graded


def build_inventory(prereg_bytes, dropped_tasks, templates=None):
    """Every a3 count, computed from the preregistration bytes and stamped with their sha256."""
    templates = TEMPLATES if templates is None else templates
    document = load_preregistration(prereg_bytes)
    live, mapped, exact = _map_tasks(document, dropped_tasks, templates)
    graded = build_tasks(prereg_bytes, dropped_tasks, templates)
    graded_ids = {task["id"] for task in graded}
    classes = collections.Counter()
    for task in graded:
        classes.update(task["classes"])
        if "D" in task["classes"]:
            classes["D_" + task["family"]] += 1
    by_family = collections.defaultdict(collections.Counter)
    for task in graded:
        for arm in task["arms"]:
            by_family[task["family"]][arm] += 1
        if task["strict_repeat"]:
            by_family[task["family"]]["strict"] += 1
    answers = {"total": sum(sum(counter.values()) for counter in by_family.values())}
    for family in ("claude", "codex"):
        order = FAMILY_ARMS[family] + (["strict"] if by_family[family]["strict"] else [])
        answers[family] = {arm: by_family[family][arm] for arm in order}
    d_answers = collections.Counter()
    for task in graded:
        if "D" in task["classes"]:
            d_answers[task["family"]] += len(task["arms"])
    arm_b = [task for task in graded if "B" in task["arms"]]
    matched = [task for task in arm_b if "A" in task["arms"]]

    def split(items):
        return {"claude": sum(task["family"] == "claude" for task in items),
                "codex": sum(task["family"] == "codex" for task in items)}

    organic_b = [task for task in arm_b if task["opportunity"] == "organic"]
    organic_matched = [task for task in matched if task["opportunity"] == "organic"]
    return {
        "preregistration_sha256": sha256_hex(prereg_bytes),
        "counts": {
            "tasks": len(live),
            "distinct_check_texts": len({text for texts in exact.values() for text in texts}),
            "templates": len(mapped),
            "graded_templates": sum(1 for name in mapped if templates[name]["classes"]),
            "graded_tasks": len(graded),
            "not_graded": sorted(task["id"] for task, _ in live if task["id"] not in graded_ids),
            "classes": {"C": classes["C"], "A": classes["A"], "B": classes["B"], "D": classes["D"],
                        "D_claude": classes["D_claude"], "D_codex": classes["D_codex"]},
            "g_q": {"clause1": dict({"population": len(arm_b)}, **split(arm_b),
                                    organic_only=len(organic_b),
                                    organic_claude=split(organic_b)["claude"], organic_codex=split(organic_b)["codex"]),
                    "clause2": dict({"matched": len(matched)}, **split(matched), organic=len(organic_matched),
                                    organic_claude=split(organic_matched)["claude"],
                                    organic_codex=split(organic_matched)["codex"])},
            "attempt1_answers": answers,
            "d_bearing_answers": {"total": sum(d_answers.values()), "claude": d_answers["claude"],
                                  "codex": d_answers["codex"]},
            "m8_lanes": {lane: sum(1 for task in organic_b if lane in task["lane_tags"]) for lane in M8_LANES},
            "toon_seeded": sum(1 for task in organic_b if "toon-seeded" in task["lane_tags"]),
        },
    }


# ---- Pinned sources ---------------------------------------------------------------------------------------------

class GitSources:
    """Files of one commit read through `git cat-file`; the working tree is never consulted."""

    def __init__(self, repo, rev):
        self.repo, self.rev = str(repo), rev
        self._listing = {}
        self._blobs = {}
        self.parsed = {}

    def _git(self, *args, check=False):
        try:
            done = subprocess.run(["git", "-C", self.repo, *args], capture_output=True, stdin=subprocess.DEVNULL,
                                  timeout=120)
        except subprocess.TimeoutExpired:
            raise Refusal("E_GIT", reason="timeout") from None
        if check and done.returncode != 0:
            raise Refusal("E_GIT", reason="failed")
        return done

    def read(self, path):
        done = self._git("cat-file", "blob", f"{self.rev}:{path}")
        return done.stdout if done.returncode == 0 else None

    def files(self, *prefixes):
        """Tracked paths under the prefixes (all paths when none are given), sorted."""
        cache_key = tuple(prefixes)
        if cache_key not in self._listing:
            args = ["ls-tree", "-r", "--name-only", "-z", self.rev]
            if prefixes:
                args += ["--"] + [prefix.rstrip("/") + "/" for prefix in prefixes]
            done = self._git(*args, check=True)
            self._listing[cache_key] = sorted(item for item in done.stdout.decode("utf-8").split("\0") if item)
        return self._listing[cache_key]

    def read_many(self, paths):
        """{path: bytes} through one `git cat-file --batch` process."""
        wanted = list(paths)
        if not wanted:
            return {}
        fetch = [path for path in wanted if path not in self._blobs]
        if fetch:
            self._blobs.update(self._batch(fetch))
        return {path: self._blobs[path] for path in wanted}

    def _batch(self, wanted):
        request = "".join(f"{self.rev}:{path}\n" for path in wanted).encode("utf-8")
        try:
            done = subprocess.run(["git", "-C", self.repo, "cat-file", "--batch"], input=request, capture_output=True,
                                  timeout=300)
        except subprocess.TimeoutExpired:
            raise Refusal("E_GIT", reason="timeout") from None
        if done.returncode != 0:
            raise Refusal("E_GIT", reason="failed")
        data, result, offset = done.stdout, {}, 0
        try:
            for path in wanted:
                end = data.index(b"\n", offset)
                header = data[offset:end].split()
                offset = end + 1
                if len(header) == 3 and header[1] == b"blob":
                    size = int(header[2])
                    result[path] = data[offset:offset + size]
                    offset += size + 1
                else:
                    result[path] = None
        except ValueError:
            raise Refusal("E_GIT", reason="malformed") from None
        return result


class DirSources:
    """Tracked files of a directory (a clone or worktree); `git ls-files` names them and the disk supplies the bytes."""

    def __init__(self, root):
        self.root = str(root)
        self.parsed = {}

    def read(self, path):
        try:
            with open(os.path.join(self.root, path), "rb") as stream:
                return stream.read()
        except OSError:
            return None

    def files(self, *prefixes):
        try:
            done = subprocess.run(["git", "-C", self.root, "ls-files", "-z"], capture_output=True,
                                  stdin=subprocess.DEVNULL, timeout=120)
        except subprocess.TimeoutExpired:
            raise Refusal("E_GIT", reason="timeout") from None
        if done.returncode != 0:
            raise Refusal("E_GIT", reason="failed")
        paths = sorted(item for item in done.stdout.decode("utf-8").split("\0") if item)
        if prefixes:
            paths = [path for path in paths if any(path.startswith(prefix.rstrip("/") + "/") for prefix in prefixes)]
        return paths

    def read_many(self, paths):
        return {path: self.read(path) for path in paths}


# ---- Private writes (R22): create-only, 0600, never inside a git work tree --------------------------------------

def inside_git_work_tree(path):
    """True when `path` (which may not exist yet) lies inside a git work tree: a `.git` entry in any ancestor."""
    current = os.path.abspath(path)
    while current and not os.path.exists(current):
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    current = os.path.realpath(current)
    if os.path.isfile(current):
        current = os.path.dirname(current)
    while True:
        if os.path.lexists(os.path.join(current, ".git")):
            return True
        parent = os.path.dirname(current)
        if parent == current:
            return False
        current = parent


def path_exists(path):
    return os.path.lexists(path)


def open_new(path):
    return os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)


def private_path_issue(path):
    if inside_git_work_tree(path):
        return "work_tree"
    if path_exists(path):
        return "exists"
    return None


def private_create(path, data):
    """Create `path` exclusively with mode 0600; refuse an existing path, a symlink or a work-tree location first."""
    issue = private_path_issue(path)
    if issue:
        raise Refusal("E_PATH", reason=issue)
    parent = os.path.dirname(os.path.abspath(path))
    os.makedirs(parent, mode=0o700, exist_ok=True)
    try:
        descriptor = open_new(path)
    except FileExistsError:
        raise Refusal("E_PATH", reason="exists") from None
    except OSError:
        raise Refusal("E_PATH", reason="unwritable") from None
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
    except BaseException:
        try:
            os.unlink(path)
        except OSError:
            pass
        raise


def private_dir(path):
    """A private output directory: refused inside a work tree, created 0700 when new, files inside stay create-only."""
    if inside_git_work_tree(path):
        raise Refusal("E_PATH", reason="work_tree")
    os.makedirs(path, mode=0o700, exist_ok=True)


# ---- Key recipes (a4): keys computed from pinned Git content, never from an answer -------------------------------

E2E_DIR = "evidence/artifacts/token-adoption-e2e-20260926"
PREREG_PATH = f"{E2E_DIR}/preregistration.json"
README_PATH = f"{E2E_DIR}/README.md"
TABLE_PATH = f"{E2E_DIR}/fixtures/table.json"
EVENTS_PATH = f"{E2E_DIR}/fixtures/events.jsonl"
# The Amendment 3 seal rows for the two fixtures (README "Amendment 3 seal"); Amendment 4 leaves them unchanged.
SEALED_FIXTURES = {TABLE_PATH: "fdf314394a9854039da18b2f827f8caf2d8ffb3651594733eb84699f74c09448",
                   EVENTS_PATH: "81ef838c18cc81006269024e7270b991dbdfcb72bf223dec324f2fba9307930e"}
# T2 originals: `git log --stat -150` at each receipt's catalog revision (README pre-run record, 2026-09-28).
RECORDED_T2 = {
    "reuse-296-02": {"sha256": "82e9249222bafd5daee41ee74840a92d2a00feabd70f4e1149adb21a600d630b", "bytes": 891615},
    "reuse-343-06": {"sha256": "5939b5451e55a3744b7a8f299733904979046974a5c2aea340ecb6b3b9149c2c", "bytes": 774521},
}
# The six recovered command identities, in order (README "Command identities"); the bare command is the identity.
T0_IDENTITIES = (
    ("git-log", ["git", "log", "-30"]),
    ("git-status", ["git", "status"]),
    ("git-diff", ["git", "diff", "HEAD~5", "--stat"]),
    ("grep", ["grep", "-rn", "def register_file", "scripts"]),
    ("ls", ["ls", "-la", "scripts"]),
    ("unittest", ["python3", "-m", "unittest", "tests.test_host_requests"]),
)
TRUST_CONDITIONS = ["author_association", "user.type", "performed_via_github_app", "repository_owner"]
ANTI_PATTERN_KEYWORDS = {"T21": "stdin", "T22": "filtered", "T23": "wait loop", "T24": "pipeline", "T25": "budget"}


class KeyUnavailable(Exception):
    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


def _need(data, reason="key_missing"):
    if data is None:
        raise KeyUnavailable(reason)
    return data


def _text(data):
    return _need(data).decode("utf-8", errors="replace")


def parse_py(data):
    try:
        text = data.decode("utf-8")
        return text, ast.parse(text)
    except (SyntaxError, ValueError, UnicodeDecodeError):
        return None, None


def _top_functions(tree):
    return [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]


def _line_count(text):
    return len(text.splitlines())


def _enclosing_names(tree):
    """{call node: innermost enclosing function name} for every Call in the tree (module level is '<module>')."""
    names, stack = {}, []

    def visit(node):
        pushed = isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        if pushed:
            stack.append(node.name)
        if isinstance(node, ast.Call):
            names[node] = stack[-1] if stack else "<module>"
        for child in ast.iter_child_nodes(node):
            visit(child)
        if pushed:
            stack.pop()
    visit(tree)
    return names


def _token_strings(text):
    """(line, string) of the comment and string tokens of a Python source."""
    found = []
    kinds = {tokenize.COMMENT, tokenize.STRING}
    middle = getattr(tokenize, "FSTRING_MIDDLE", None)
    if middle is not None:
        kinds.add(middle)
    try:
        for token in tokenize.generate_tokens(io.StringIO(text).readline):
            if token.type in kinds:
                found.append((token.start[0], token.string))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        pass
    return found


class _Parsed:
    """One Python source parsed once: the tree at once, comment/string tokens and enclosing names on demand."""

    def __init__(self, data):
        self.text, self.tree = parse_py(data)
        self._tokens = self._enclosing = None

    @property
    def tokens(self):
        if self._tokens is None:
            self._tokens = _token_strings(self.text) if self.tree is not None else []
        return self._tokens

    @property
    def enclosing(self):
        if self._enclosing is None:
            self._enclosing = _enclosing_names(self.tree) if self.tree is not None else {}
        return self._enclosing


def parsed_file(src, path, data):
    if path not in src.parsed:
        src.parsed[path] = _Parsed(data)
    return src.parsed[path]


def symbol_sites(src, prefixes, symbol, with_functions=False):
    """Definition-independent site analysis of one symbol over the tracked Python files under the prefixes. A file
    that never spells the symbol has no site for it, so only files that do are parsed."""
    paths = [path for path in src.files(*prefixes) if path.endswith(".py")]
    sources = src.read_many(paths)
    needle = symbol.encode("utf-8")
    name_calls, attr_calls, imports, mentions = [], [], [], []
    for path in paths:
        data = sources.get(path)
        if data is None or needle not in data:
            continue
        parsed = parsed_file(src, path, data)
        if parsed.tree is None:
            continue
        enclosing = parsed.enclosing if with_functions else {}
        for node in ast.walk(parsed.tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == symbol:
                    entry = [path, node.lineno]
                    if with_functions:
                        entry.append(enclosing.get(node, "<module>"))
                    name_calls.append(entry)
                elif isinstance(node.func, ast.Attribute) and node.func.attr == symbol:
                    attr_calls.append([path, node.lineno])
            elif isinstance(node, ast.ImportFrom) and any(alias.name == symbol for alias in node.names):
                imports.append([path, node.lineno])
        mentions.extend([path, line] for line, string in parsed.tokens
                        if word_positions(string, symbol, ignore_case=False))
    for group in (name_calls, attr_calls, imports, mentions):
        group.sort()
    return {"name_calls": name_calls, "attr_calls": attr_calls, "imports": imports, "mentions": mentions}


def _definition(src, path, symbol):
    data = _need(src.read(path))
    text, tree = parse_py(data)
    if tree is None:
        raise KeyUnavailable("key_missing")
    for node in _top_functions(tree):
        if node.name == symbol:
            return [path, node.lineno, node.end_lineno], node, text
    raise KeyUnavailable("key_missing")


def token_line_counts(text):
    """R2-09 (U9-D22): lines holding `token` as a substring, a whole word (grep -w: letters, digits and '_' are word
    characters) and with an alphanumeric boundary only."""
    counts = {"substring": 0, "whole_word": 0, "alnum_boundary": 0}
    for line in text.split("\n"):
        low = line.lower()
        if "token" not in low:
            continue
        counts["substring"] += 1
        whole = alnum = False
        start = 0
        while True:
            index = low.find("token", start)
            if index < 0:
                break
            before = low[index - 1] if index else ""
            after = low[index + 5] if index + 5 < len(low) else ""
            if not (before and is_word_char(before)) and not (after and is_word_char(after)):
                whole = True
            if not (before and before.isalnum()) and not (after and after.isalnum()):
                alnum = True
            start = index + 1
        counts["whole_word"] += whole
        counts["alnum_boundary"] += alnum
    return counts


def key_T1(src, params):
    text = _text(src.read("docs/grand-catalog-handbook.md"))
    headings = [line[3:].strip() for line in text.split("\n") if line.startswith("## ")]
    return {"path": "docs/grand-catalog-handbook.md", "heading_count": len(headings), "first_ten": headings[:10],
            "token_lines": token_line_counts(text)}


def key_T3(src, params):
    where, node, text = _definition(src, params["symbol_fixture"], params["symbol"])
    segment = ast.get_source_segment(text, node) or ""
    return {"path": where[0], "lineno": where[1], "end_lineno": where[2], "segment": segment,
            "def_line": segment.split("\n", 1)[0]}


def key_T4(src, params):
    update = _text(src.read("adoption/update.md"))
    bootstrap = _text(src.read("adoption/bootstrap.md")).split("\n")
    pins = [line.strip() for line in update.split("\n")
            if "source.release_tag" in line or "source.release_commit" in line]
    start = next((index for index, line in enumerate(bootstrap) if line.startswith("**Step 0")), None)
    excerpt = []
    if start is not None:
        for line in bootstrap[start:start + 60]:
            if excerpt and line.startswith("**Step "):
                break
            excerpt.append(line)
    return {"update_path": "adoption/update.md", "pin_lines": pins, "bootstrap_path": "adoption/bootstrap.md",
            "bootstrap_excerpt": excerpt, "qmd_coverage": None}


def key_T5(src, params):
    where, _, _ = _definition(src, params["symbol_fixture"], params["symbol"])
    sites = symbol_sites(src, ("scripts", "tests"), params["symbol"])
    return dict({"symbol": params["symbol"], "def": where}, **sites)


def key_T6(src, params):
    where, node, text = _definition(src, "scripts/host_requests.py", "trust")
    lines = {}
    for path in ("scripts/host_requests.py", "recipes/host-request-lane.md"):
        lines[path] = _text(src.read(path)).split("\n")
    return {"function": "trust", "path": where[0], "lineno": where[1], "end_lineno": where[2],
            "segment": ast.get_source_segment(text, node) or "", "conditions": list(TRUST_CONDITIONS), "files": lines}


def key_T7(src, params):
    recipe = _text(src.read("recipes/host-request-lane.md")).split("\n")
    return {"recipe_path": "recipes/host-request-lane.md", "recipe_sha256": sha256_hex("\n".join(recipe)),
            "trust_lines": [line.strip() for line in recipe if "trust" in line.lower()], "memory_records": None}


def key_T8(src, params):
    data = _need(src.read("scripts/host_requests.py"))
    text, tree = parse_py(data)
    if tree is None:
        raise KeyUnavailable("key_missing")
    names = [node.name for node in _top_functions(tree)]
    methods = sorted({node.name for cls in ast.walk(tree) if isinstance(cls, ast.ClassDef)
                      for node in ast.walk(cls) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
                     - set(names))
    other = []
    data2 = src.read("scripts/credential_status.py")
    if data2 is not None:
        _, tree2 = parse_py(data2)
        if tree2 is not None:
            other = sorted({node.name for node in _top_functions(tree2)} - set(names))
    return {"path": "scripts/host_requests.py", "names": names, "distractors": sorted(set(methods) | set(other))}


def key_T9(src, params, prereg_src):
    frozen = params["frozen_input"]
    data = _need(prereg_src.read(frozen["path"]))
    try:
        node = json.loads(data.decode("utf-8"))
        for part in frozen["pointer"].lstrip("/").split("/"):
            node = node[part]
    except (ValueError, KeyError, TypeError):
        raise KeyUnavailable("key_missing") from None
    serialized = json.dumps(node, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if sha256_hex(serialized) != frozen["sha256"] or len(serialized) != frozen["bytes"] \
            or not isinstance(node, list) or len(node) != frozen["records"]:
        raise KeyUnavailable("input_hash")
    return {"sha256": frozen["sha256"], "bytes": frozen["bytes"], "record_count": frozen["records"],
            "records": json.loads(serialized.decode("utf-8"))}


def key_T10(src, params):
    sites = []
    paths = [item for item in src.files("scripts") if item.endswith(".py")]
    blobs = src.read_many(paths)
    for path in paths:
        data = _need(blobs.get(path))
        if b"subprocess" not in data:
            continue
        tree = parsed_file(src, path, data).tree
        if tree is None:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "run" \
                    and isinstance(node.func.value, ast.Name) and node.func.value.id == "subprocess":
                sites.append([path, node.lineno])
    sites.sort()
    return {"count": len(sites), "files": len({path for path, _ in sites}), "sites": sites}


def key_T11(src, params):
    sites = symbol_sites(src, (), params["symbol"], with_functions=True)
    return {"symbol": params["symbol"], "sites": sites["name_calls"], "attr_calls": sites["attr_calls"],
            "imports": sites["imports"], "mentions": sites["mentions"]}


def _fixture(src, path):
    data = _need(src.read(path))
    if path in SEALED_FIXTURES and sha256_hex(data) != SEALED_FIXTURES[path]:
        raise KeyUnavailable("input_hash")
    return data


def _table_records(src):
    try:
        return json.loads(_fixture(src, TABLE_PATH).decode("utf-8"))
    except ValueError:
        raise KeyUnavailable("input_hash") from None


def _event_rows(data):
    rows = []
    for line in data.decode("utf-8").split("\n"):
        if line.strip():
            rows.append(json.loads(line))
    return rows


def key_web(src, params):
    low, high = params["range"]
    records = [record for record in _table_records(src) if low <= record["id"] <= high]
    return {"records": records, "latency_sum": sum(record["latency_ms"] for record in records),
            "range": [low, high], "urls": list(params["urls"])}


def anti_pattern_row(history_lines, keyword):
    """The first anti-pattern log row (a table row starting with a date) whose anti-pattern column holds the keyword."""
    for line in history_lines:
        if not line.startswith("| 20"):
            continue
        cells = line.split("|")
        if len(cells) > 2 and keyword in cells[2].lower():
            return line.strip()
    return None


def key_catalog(src, params, name):
    catalog = _text(src.read(params["catalog"]))
    history = _text(src.read(params["historical_fixture"])).split("\n")
    row = anti_pattern_row(history, ANTI_PATTERN_KEYWORDS[name])
    facts = {fact: fact.lower() in catalog.lower() for fact in TEMPLATES[name]["facts"]}
    return {"catalog": params["catalog"], "catalog_sha256": sha256_hex(catalog), "facts_in_source": facts,
            "anti_pattern_row": row, "memory_records": None}


def key_T26(src, params, events_bytes):
    where, _, _ = _definition(src, params["symbol_fixture"], params["symbol"])
    sites = symbol_sites(src, ("scripts", "tests"), params["symbol"])
    low, high = params["event_range"]
    errors = [row for row in _event_rows(events_bytes) if row["level"] == "ERROR" and low <= row["event"] <= high]
    return dict({"symbol": params["symbol"], "def": where, "range": [low, high],
                 "error_events": [row["event"] for row in errors], "value_sum": sum(row["value"] for row in errors)},
                **sites)


def key_T27(src, params):
    data = _fixture(src, EVENTS_PATH)
    rows = _event_rows(data)
    directory = EVENTS_PATH.rsplit("/", 1)[0] + "/"
    listing = sorted({path[len(directory):].split("/", 1)[0] for path in src.files(directory) if path.startswith(directory)})
    return {"partition": params["partition"], "fixture_bytes": len(data), "rows": len(rows),
            "error_rows": sum(1 for row in rows if row["level"] == "ERROR"), "wc_l": data.count(b"\n"),
            "ls": listing, "summary": f"PASS partition {params['partition']}", "fixture_sha256": sha256_hex(data),
            "acceptance": None}


def key_T28(src, params):
    patch = _text(src.read(params["fixture_path"]))
    lines = patch.split("\n")
    files = [line[4:].strip() for line in lines if line.startswith("+++ ")]
    hunk_starts = [index for index, line in enumerate(lines) if line.startswith("@@")]
    opening = lines[hunk_starts[0]:hunk_starts[1]] if len(hunk_starts) > 1 else lines[hunk_starts[0]:] if hunk_starts \
        else []
    return {"bytes": len(patch.encode("utf-8")), "files": files, "hunks": len(hunk_starts),
            "added": sum(1 for line in lines if line.startswith("+") and not line.startswith("+++")),
            "deleted": sum(1 for line in lines if line.startswith("-") and not line.startswith("---")),
            "opening_hunk": opening}


def key_T29(src, params):
    before = _text(src.read("fixtures/before.py"))
    after = _text(src.read("fixtures/after.py"))
    _, tree = parse_py(before.encode("utf-8"))
    names = [node.name for node in _top_functions(tree)] if tree is not None else []
    return {"function": names[0] if names else None, "before_lines": _line_count(before),
            "after_lines": _line_count(after)}


def key_T31(src, params):
    after = _need(src.read("fixtures/after.py"))
    before = _text(src.read("fixtures/before.py"))
    return {"after_sha256": sha256_hex(after), "after_bytes": len(after), "before_lines": _line_count(before)}


def key_T32(src, params):
    record = next((item for item in _table_records(src) if item["id"] == params["record_id"]), None)
    _need(record)
    verdict = "yes" if record["status"] == "ok" and record["region"] == "us-east-1" else "no"
    return {"record_id": record["id"], "verdict": verdict, "latency_ms": record["latency_ms"]}


def key_T33(src, params):
    data = _fixture(src, EVENTS_PATH)
    first = _event_rows(data)[:5]
    return {"events": [row["event"] for row in first], "levels": [row["level"] for row in first],
            "file_bytes": len(data)}


def key_T34(src, params):
    return {"count": sum(1 for row in _event_rows(_fixture(src, EVENTS_PATH)) if row["level"] == "ERROR")}


def key_T35(src, params):
    errors = [row["event"] for row in _event_rows(_fixture(src, EVENTS_PATH)) if row["level"] == "ERROR"]
    _need(errors or None)
    return {"first": errors[0], "last": errors[-1]}


def key_T36(src, params, task_id, bindings):
    record = ((bindings or {}).get("sentinels") or {}).get(task_id)
    _need(record, "input_missing")
    names = sorted({path.split("/", 1)[1].split("/", 1)[0] for path in src.files("fixtures")} | {"sentinel.txt"})
    before = _text(src.read("fixtures/before.py"))
    return {"value": record["value"], "sha256": record["sha256"], "sibling_value": record.get("sibling_value"),
            "inventory": names, "before_lines": _line_count(before)}


def key_T37(src, params):
    return key_T29(src, params)


# The ten elements of the T38 fixture, named as scripts/native_token_ci.py markdown_elements names them.
ELEMENT_KINDS = ("headings", "table", "ordered_list", "nested_list", "link", "emphasis", "blockquote", "code_block",
                 "inline_code_and_entity", "image")
_HEADING_TAGS = frozenset({"h1", "h2", "h3", "h4", "h5", "h6"})
_CONTENT_TAGS = _HEADING_TAGS | {"th", "td", "li", "ol", "ul", "blockquote", "pre", "code", "strong", "em", "a", "p"}


class _ElementContents(HTMLParser):
    """R2-06 element_contents: the text of each element the ten structure checks look for, in document order. Script, style
    and comment text is never content, and of the attributes only a link's target and an image's alt text are read. A list
    item keeps its own text (a nested list's items are separate entries), so the nested list reads as three items."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.contents = {kind: [] for kind in ELEMENT_KINDS}
        self.stack, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ("script", "style"):
            self.skip += 1
        elif tag == "img":
            self.contents["image"].append(attrs.get("alt") or "")
        elif tag in _CONTENT_TAGS:
            frame = {"tag": tag, "parts": [], "href": attrs.get("href"), "inline_code": False}
            if tag == "li":
                lists = [item["tag"] for item in self.stack if item["tag"] in ("ol", "ul")]
                frame["kind"] = "ordered_list" if lists and lists[-1] == "ol" else "nested_list"
                frame["slot"] = len(self.contents[frame["kind"]])
                self.contents[frame["kind"]].append("")  # reserve the slot so an outer item precedes its nested items
            elif tag == "code" and not any(item["tag"] == "pre" for item in self.stack):
                for item in self.stack:
                    if item["tag"] == "p":
                        item["inline_code"] = True
            self.stack.append(frame)

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip = max(0, self.skip - 1)
            return
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index]["tag"] == tag:
                while len(self.stack) > index:
                    self.close_frame(self.stack.pop())
                return

    def handle_data(self, data):
        if self.skip:
            return
        innermost = max((index for index, item in enumerate(self.stack) if item["tag"] == "li"), default=None)
        for index, frame in enumerate(self.stack):
            if frame["tag"] != "li" or index == innermost:
                frame["parts"].append(data)

    def close_frame(self, frame):
        raw, tag = "".join(frame["parts"]), frame["tag"]
        text = " ".join(raw.split())
        if tag in _HEADING_TAGS:
            self.contents["headings"].append(text)
        elif tag in ("th", "td"):
            self.contents["table"].append(text)
        elif tag == "li":
            self.contents[frame["kind"]][frame["slot"]] = text
        elif tag == "blockquote":
            self.contents["blockquote"].append(text)
        elif tag == "pre":
            self.contents["code_block"] += [" ".join(line.split()) for line in raw.splitlines()]
        elif tag in ("strong", "em"):
            self.contents["emphasis"].append(text)
        elif tag == "a":
            self.contents["link"] += [text, frame["href"] or ""]
        elif tag == "p" and frame["inline_code"]:
            self.contents["inline_code_and_entity"].append(text)


def html_contents(html_bytes):
    """{element kind: [content strings]} of the T38 fixture, document order, no empty strings."""
    parser = _ElementContents()
    parser.feed(html_bytes.decode("utf-8", errors="replace"))
    parser.close()
    while parser.stack:
        parser.close_frame(parser.stack.pop())
    return {kind: [text for text in parser.contents[kind] if text] for kind in ELEMENT_KINDS}


def key_T38(src, params, inputs):
    data = _need(src.read(params["fixture_path"]))
    contents = html_contents(data)
    _need(all(contents.values()) or None)  # a fixture without one of the ten elements would make its check vacuous
    bound = (inputs or {}).get("seed-conversion")
    return {"fixture_sha256": sha256_hex(data), "input_sha256": bound.get("sha256") if bound else None,
            "contents": contents}


def key_T2(task_id, inputs):
    recorded = RECORDED_T2[task_id]
    bound = _need((inputs or {}).get(task_id), "input_missing")
    if bound.get("sha256") != recorded["sha256"] or bound.get("bytes") != recorded["bytes"]:
        raise KeyUnavailable("input_hash")
    return dict(recorded)


def compute_keys(tasks, exec_src, prereg_src, inputs=None, memory=None, qmd=None, bindings=None, captures=None):
    """{task id: {template, status, reason, key, key_sha256}} for every graded task; a key that cannot be computed
    is recorded as unknown with its reason, never guessed."""
    inputs = inputs or {}
    captures = captures or {}
    events = {}

    def events_bytes():
        if "data" not in events:
            events["data"] = _fixture(exec_src, EVENTS_PATH)
        return events["data"]

    cache = {}

    def memo(name, build):
        if name not in cache:
            cache[name] = build()
        return cache[name]

    result = collections.OrderedDict()
    for task in tasks:
        name, params, task_id = task["template"], task["params"], task["id"]
        try:
            if name == "T0":
                key = {"identities": [list(argv) for _, argv in T0_IDENTITIES], "source": "captures"}
            elif name == "T1":
                key = memo(name, lambda: key_T1(exec_src, params))
            elif name == "T2":
                key = key_T2(task_id, inputs)
            elif name == "T3":
                key = memo(name, lambda: key_T3(exec_src, params))
            elif name == "T4":
                key = memo(name, lambda: key_T4(exec_src, params))
                key = dict(key, qmd_coverage=(qmd or {}).get("adoption/update.md"))
            elif name == "T5":
                key = memo(name, lambda: key_T5(exec_src, params))
            elif name == "T6":
                key = memo(name, lambda: key_T6(exec_src, params))
            elif name == "T7":
                key = dict(memo(name, lambda: key_T7(exec_src, params)),
                           memory_records=(memory or {}).get(task_id))
            elif name == "T8":
                key = memo(name, lambda: key_T8(exec_src, params))
            elif name == "T9":
                key = memo(name, lambda: key_T9(exec_src, params, prereg_src))
            elif name == "T10":
                key = memo(name, lambda: key_T10(exec_src, params))
            elif name == "T11":
                key = {"symbol": params["symbol"], "source": "clone_post_arm"}
            elif name in ("T12", "T13"):
                key = {"pages": ["stripe"] if name == "T12" else ["mcp"], "source": "captures",
                       "facts_required": ["idempotency_key_header", "retention_hours"] if name == "T12"
                       else ["scopes"]}
            elif name == "T14":
                key = {"source": "identity_table_and_transcript"}
            elif name in WEB_TEMPLATES:
                key = key_web(exec_src, params)
                key["pages"] = ["json", "pathlib"]
            elif name in CATALOG_TEMPLATES:
                key = dict(key_catalog(exec_src, params, name), memory_records=(memory or {}).get(task_id))
            elif name == "T26":
                key = key_T26(exec_src, params, events_bytes())
            elif name == "T27":
                key = key_T27(exec_src, params)
                if captures.get("post_w"):
                    key["acceptance"] = captures["post_w"].get("acceptance", {}).get(task_id)
            elif name == "T28":
                key = memo(name, lambda: key_T28(exec_src, params))
            elif name == "T29":
                key = memo(name, lambda: key_T29(exec_src, params))
            elif name == "T30":
                post = (captures.get("post_w") or {}).get("py_compile")
                key = _need(post, "post_w_missing")
            elif name == "T31":
                key = memo(name, lambda: key_T31(exec_src, params))
            elif name == "T32":
                key = key_T32(exec_src, params)
            elif name == "T33":
                key = memo(name, lambda: key_T33(exec_src, params))
            elif name == "T34":
                key = memo(name, lambda: key_T34(exec_src, params))
            elif name == "T35":
                key = memo(name, lambda: key_T35(exec_src, params))
            elif name == "T36":
                key = key_T36(exec_src, params, task_id, bindings)
            elif name == "T37":
                key = memo(name, lambda: key_T37(exec_src, params))
            elif name == "T38":
                key = key_T38(exec_src, params, inputs)
            else:
                raise KeyUnavailable("key_missing")
            result[task_id] = {"template": name, "status": "ok", "reason": None, "key": key,
                               "key_sha256": sha256_hex(canonical(key))}
        except KeyUnavailable as stop:
            result[task_id] = {"template": name, "status": "unknown", "reason": stop.reason, "key": None,
                               "key_sha256": None}
    return result


# ---- Strict decode and equality (R4) ---------------------------------------------------------------------------

class DecodeError(Exception):
    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


def _no_duplicates(pairs):
    result = {}
    for name, value in pairs:
        if name in result:
            raise ValueError("duplicate key")
        result[name] = value
    return result


def _no_constant(name):
    raise ValueError("non-finite constant")


def json_decode(text):
    try:
        return json.loads(text, object_pairs_hook=_no_duplicates, parse_constant=_no_constant)
    except (ValueError, RecursionError):
        raise DecodeError("json_strict_decode") from None


TOON_PINNED = "4.1.1"
_TOON_VERSIONS = {}


def toon_version():
    """The version line of the `toon` on PATH, read once per binary; None when it cannot be read."""
    path = shutil.which("toon")
    if path is None:
        return None
    if path not in _TOON_VERSIONS:
        try:
            done = subprocess.run([path, "--version"], capture_output=True, text=True, stdin=subprocess.DEVNULL,
                                  timeout=30)
            _TOON_VERSIONS[path] = done.stdout.strip() if done.returncode == 0 else None
        except (OSError, subprocess.TimeoutExpired):
            _TOON_VERSIONS[path] = None
    return _TOON_VERSIONS[path]


def toon_decode_argv():
    """The TOON CLI decode command by bare name (no host path reaches a recorded argv); strict is the CLI default
    and `--no-strict` is never passed."""
    return ["toon", "--decode"]


def toon_decode(text):
    if toon_version() != TOON_PINNED:
        raise Refusal("E_TOOL", tool="toon", reason="version")
    try:
        done = subprocess.run(toon_decode_argv(), input=text, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        raise DecodeError("toon_strict_decode") from None
    if done.returncode != 0:
        raise DecodeError("toon_strict_decode")
    try:
        return json.loads(done.stdout)
    except ValueError:
        raise DecodeError("toon_strict_decode") from None


def toon_header(line):
    """True for a TOON array header line: `[N]:`, `[N]{fields}:` or `key[N]{fields}:` (optionally with inline values)."""
    stripped = line.strip()
    index = stripped.find("[")
    if index < 0 or any(char in " \t:" for char in stripped[:index]):
        return False
    scan = index + 1
    digits = 0
    while scan < len(stripped) and is_digit(stripped[scan]):
        scan += 1
        digits += 1
    if not digits:
        return False
    if scan < len(stripped) and stripped[scan] in "\t|":
        scan += 1
    if scan >= len(stripped) or stripped[scan] != "]":
        return False
    scan += 1
    if scan < len(stripped) and stripped[scan] == "{":
        close = stripped.find("}", scan)
        if close < 0:
            return False
        scan = close + 1
    return scan < len(stripped) and stripped[scan] == ":"


def _json_block(lines, start):
    """Consecutive lines from `start` that close the JSON array or object opened on the first line, or None."""
    depth, in_string, escaped, collected = 0, False, False, []
    for number in range(start, len(lines)):
        collected.append(lines[number])
        for char in lines[number]:
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
            elif char == '"':
                in_string = True
            elif char in "[{":
                depth += 1
            elif char in "]}":
                depth -= 1
        if depth <= 0 and not in_string:
            return "\n".join(collected), number
        if number - start > 5000:
            break
    return "\n".join(collected), len(lines) - 1


def looks_like_payload(text):
    first = next((line for line in text.split("\n") if line.strip()), "")
    return first.lstrip()[:1] in ("[", "{") or toon_header(first)


def payload_candidates(ans):
    """Structural candidates (fenced blocks and contiguous line blocks that start like a TOON header or a JSON
    array or object) and bare ones (each evidence string, then the whole answer), in that order, without repeats."""
    raw = answer_text(ans)
    found, seen = [], set()

    def add(kind, text, structural):
        key = text.strip()
        if key and key not in seen:
            seen.add(key)
            found.append({"kind": kind, "text": text, "structural": structural})

    for block in fenced_blocks(raw):
        if block["lang"] in ("", "json", "toon"):
            add("fence", block["body"], True)
    lines = raw.split("\n")
    outside = outside_fences(raw)
    position = 0
    while position < len(outside):
        index, line = outside[position]
        stripped = line.lstrip()
        block, last = None, index
        if toon_header(line) and not stripped.startswith("- "):
            rows = [line]
            follow = index + 1
            while follow < len(lines) and lines[follow][:1] in (" ", "\t") and lines[follow].strip():
                rows.append(lines[follow])
                follow += 1
            if "{" in stripped or len(rows) > 1:  # a tabular or indented array; `[1]: url` is prose
                block, last = "\n".join(rows), follow - 1
        elif stripped[:1] == "{" or stripped[:2] == "[{" or stripped.rstrip() == "[":
            block, last = _json_block(lines, index)
        if block is not None:
            add("lines", block, True)
            while position < len(outside) and outside[position][0] <= last:
                position += 1
            continue
        position += 1
    for text in answer_evidence(ans):
        add("evidence", text, False)
    add("whole", raw, False)
    return found


def decode_candidate(text):
    stripped = text.strip()
    if stripped[:1] in ("[", "{"):
        try:
            return json_decode(stripped)
        except DecodeError:
            first = next((line for line in stripped.split("\n") if line.strip()), "")
            if toon_header(first):
                return toon_decode(stripped)
            raise
    return toon_decode(stripped)


def type_class(value):
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    if value is None:
        return "null"
    return "array" if isinstance(value, list) else "object"


def scalar_equal(answer_value, key_value):
    """TOON spec section 2 scalar equality plus JSON-type identity: numbers by mathematical value (-0 = 0,
    17 = 17.0), strings by scalar sequence, and a boolean never equals a number nor a string a number."""
    if type_class(answer_value) != type_class(key_value):
        return False
    return answer_value == key_value


def _lenient_equal(answer_value, key_value):
    try:
        if isinstance(answer_value, str) and type_class(key_value) == "number":
            return float(answer_value) == float(key_value)
        if isinstance(key_value, str) and type_class(answer_value) == "number":
            return float(key_value) == float(answer_value)
    except ValueError:
        return False
    return answer_value == key_value


def compare_values(answer_value, key_value, ordered):
    """(reasons, key_order_differs) for one decoded value against the key, per R4."""
    reasons, order_bad = set(), [False]

    def walk(left, right):
        kind_left, kind_right = type_class(left), type_class(right)
        if kind_right == "object" and kind_left == "object":
            if set(left) != set(right):
                reasons.add("records")
                return
            if ordered and list(left) != list(right):
                order_bad[0] = True
            for name in right:
                walk(left[name], right[name])
        elif kind_right == "array" and kind_left == "array":
            if len(left) != len(right):
                reasons.add("records")
                return
            for one, other in zip(left, right):
                walk(one, other)
        elif kind_left in ("array", "object") or kind_right in ("array", "object"):
            reasons.add("strict_types" if kind_left != kind_right else "records")
        elif not scalar_equal(left, right):
            reasons.add("strict_types" if kind_left != kind_right and _lenient_equal(left, right) else "records")

    walk(answer_value, key_value)
    return reasons, order_bad[0]


def payload_records(value, reading):
    """(records, extras) when the decoded value has an accepted shape under R2-01, else (None, None)."""
    if isinstance(value, list) and all(isinstance(item, dict) for item in value):
        return value, {}
    if isinstance(value, dict) and reading in ("single_key_wrapper", "wrapper_with_extras"):
        lists = [(name, item) for name, item in value.items()
                 if isinstance(item, list) and item and all(isinstance(entry, dict) for entry in item)]
        if len(lists) == 1:
            others = {name: item for name, item in value.items() if name != lists[0][0]}
            if not others:
                return lists[0][1], {}
            if reading == "wrapper_with_extras" and all(not isinstance(item, (list, dict))
                                                       for item in others.values()):
                return lists[0][1], others
    return None, None


def _stated_sum(ans, structural_texts):
    """Integers in lines that name a sum or total, outside fenced blocks and payload line blocks."""
    lines = [line for _, line in outside_fences(answer_text(ans))]
    values = []
    for text in list(answer_evidence(ans)):
        lines.extend(text.split("\n"))
    for line in lines:
        if any(line.strip() and line in block for block in structural_texts):
            continue
        low = normalize(line).lower()
        for label in ("sum", "total"):
            values.extend(token["value"] for token in ints_by_label(low, label))
    return values


def _extracted_payloads(ans, extractions):
    """The D-extract fallback (R3, R21): payload texts a judge quoted from the answer. Every quote must be verbatim in the
    answer; a quote that is not makes the component unknown(judge_quote). Returns (texts, refusal Result or None)."""
    raw, texts = answer_text(ans), []
    for item in extractions or []:
        if item.get("component") != "payload":
            continue
        quotes = item.get("answer_quotes") or []
        if not quotes or any(quote not in raw for quote in quotes):
            return [], unknown("judge_quote")
        texts.extend(value for value in item.get("values", []) if isinstance(value, str) and value.strip())
    return texts, None


def grade_payload(ans, key, readings, extractions=None):
    """R4: every payload candidate must strictly decode and equal the key; the requested latency sum is checked
    when the key has one. No candidate at all is unknown(unparsed), and then a verified D-extract payload may decide;
    a found candidate that does not decode fails."""
    reading = readings["R2-01"]
    ordered = readings["R2-02"] == "ordered"
    decoded, structural_texts = [], []
    for candidate in payload_candidates(ans):
        if candidate["structural"]:
            if not looks_like_payload(candidate["text"]):
                continue
            try:
                value = decode_candidate(candidate["text"])
            except DecodeError as stop:
                return fail(stop.reason)
            if payload_records(value, "wrapper_with_extras")[0] is not None:
                structural_texts.append(candidate["text"])
                decoded.append(value)
        else:
            try:
                value = decode_candidate(candidate["text"]) if looks_like_payload(candidate["text"]) else None
            except DecodeError:
                value = None
            if value is not None and (payload_records(value, "wrapper_with_extras")[0] is not None):
                decoded.append(value)
    if not decoded:
        texts, refused = _extracted_payloads(ans, extractions)
        if refused is not None:
            return refused
        for text in texts:
            try:
                value = decode_candidate(text)
            except DecodeError as stop:
                return fail(stop.reason)
            if payload_records(value, "wrapper_with_extras")[0] is not None:
                structural_texts.append(text)
                decoded.append(value)
    if not decoded:
        return unknown("unparsed")
    reasons, extras_sum, soft = set(), None, False
    for value in decoded:
        records, extras = payload_records(value, reading)
        if records is None:
            reasons.add("strict_shape")
            continue
        found, order_bad = compare_values(records, key["records"], ordered)
        reasons |= found
        if not found and order_bad:
            reasons.add("key_order")
        if extras.get("latency_sum") is not None:
            extras_sum = extras["latency_sum"]
    if "latency_sum" in key:
        values = [extras_sum] if extras_sum is not None else _stated_sum(ans, structural_texts)
        soft = decide(values, key["latency_sum"], "latency_sum", reasons)
    if reasons:
        return fail(*reasons)
    return unknown("unparsed") if soft else ok()


# ---- Class A oracles: an answer against its frozen key (R3) -----------------------------------------------------

def order_ok(positions):
    return all(left < right for left, right in zip(positions, positions[1:]))


def site_is_excluded(kind):
    return kind in ("attr_call", "import", "mention")


def _list_marker(line, token):
    stripped = line.lstrip()
    lead = len(line) - len(stripped)
    return token["start"] == lead and token["end"] < len(line) and line[token["end"]] in ".)" \
        and token["end"] + 1 < len(line) and line[token["end"] + 1] == " "


def _line_values(line):
    return [token for token in int_tokens(line) if not _list_marker(line, token)]


def t1_token_lines_check(text, counts, reading):
    expected = counts[reading]
    values = []
    for line in normalize(text).split("\n"):
        if "token" in line.lower():
            values.extend(token["value"] for token in _line_values(line))
    verdict = single(values, expected)
    if verdict == "wrong":
        return fail("token_lines")
    return ok() if verdict == "pass" else unknown("unparsed", hedged=verdict == "hedge")


def _without_second_level(text):
    """'10 second-level headings' and 'Second-level headings: 10' both read as a count of headings."""
    lowered, out, start = text.lower(), [], 0
    while True:
        index = lowered.find("second-level ", start)
        if index < 0:
            out.append(text[start:])
            return "".join(out)
        out.append(text[start:index])
        start = index + len("second-level ")


def _finish(reasons, unparsed, **detail):
    if reasons:
        return fail(*reasons, **detail)
    if unparsed:
        return unknown("unparsed", **detail)
    return ok(**detail)


def oracle_T1(params, key, ans, readings, ctx=None):
    text = normalize(answer_text(ans))
    lowered = " ".join(text.split()).lower()
    reasons, unparsed = set(), False
    positions, missing = [], False
    for heading in key["first_ten"]:
        index = lowered.find(" ".join(normalize(heading).split()).lower())
        if index < 0:
            missing = True
        else:
            positions.append(index)
    if missing:
        reasons.add("headings_missing")
    elif not order_ok(positions):
        reasons.add("headings_order")
    counts = [token["value"] for token in ints_by_label(_without_second_level(text), "headings")]
    unparsed |= decide(counts, key["heading_count"], "heading_count", reasons)
    token = t1_token_lines_check(text, key["token_lines"], readings["R2-09"])
    if token.status == "fail":
        reasons.add("token_lines")
    elif token.status != "pass":
        unparsed = True
    return {"A": _finish(reasons, unparsed)}


def _is_hex64(word):
    return len(word) == 64 and all(char in "0123456789abcdefABCDEF" for char in word)


def oracle_T2(params, key, ans, readings, ctx=None):
    text = normalize(answer_text(ans))
    reasons, unparsed = set(), False
    digests = [word.lower() for _, _, word in iter_words(text) if _is_hex64(word)]
    if not digests:
        reasons.add("digest_missing")
    elif key["sha256"] not in digests:
        reasons.add("sha256")
    sizes = [token["value"] for token in int_tokens(text) if token["value"] >= 1000]
    if not sizes:
        reasons.add("bytes_missing")
    else:
        unparsed |= decide(sizes, key["bytes"], "bytes", reasons)
    low = text.lower()
    negative = any(has_word(low, word) for word in ("mismatch", "mismatched", "differ", "differs", "differed")) \
        or "not match" in low or "n't match" in low or "no match" in low
    positive = any(has_word(low, word) for word in ("match", "matches", "matched", "identical", "equal", "verified"))
    if negative:
        reasons.add("verdict")
    elif not positive:
        unparsed = True
    return {"A": _finish(reasons, unparsed)}


def _citation_matches(cite, path):
    return cite["path"] == path or path.endswith("/" + cite["path"])


def oracle_T3(params, key, ans, readings, ctx=None):
    raw = answer_text(ans)
    cites = citations(normalize(raw))
    reading = readings["R2-03"]
    located = False
    for cite in cites:
        if _citation_matches(cite, key["path"]) and cite["start"] == key["lineno"]:
            if reading == "def_line_range":
                located = located or cite["end"] == key["end_lineno"]
            else:
                located = located or cite["end"] in (cite["start"], key["end_lineno"])
    reasons = set()
    if not located:
        reasons.add("definition_location")
    wanted = key["def_line"] if reading == "def_line_range" else key["segment"]
    if flat(wanted) not in flat(raw):
        reasons.add("definition_text")
    return {"A": _finish(reasons, False)}


def oracle_T4(params, key, ans, readings, ctx=None):
    text = flat(answer_text(ans))
    if "adoption/update.md" not in text:
        return {"A": fail("citation_missing")}
    low = text.lower()
    missing = [fact for fact in TEMPLATES["T4"]["facts"] if fact.lower() not in low]
    return {"A": unknown("unparsed", missing=missing) if missing else ok()}


_LABEL_WORDS = (("import", ("import", "imports", "imported")),
                ("mention", ("mention", "mentions", "comment", "comments", "string", "strings", "docstring",
                             "textual", "documentation", "excluded", "exclude")),
                ("definition", ("definition", "defined", "def")))


def claim_label(line):
    words = {word.lower() for _, _, word in iter_words(line)}
    for label, names in _LABEL_WORDS:
        if words & set(names):
            return label
    return "invocation"


def _resolve_path(path, known):
    if path in known:
        return path
    matches = [item for item in known if item.endswith("/" + path)]
    return matches[0] if len(matches) == 1 else None


def claims_from_text(text, known):
    """Every cited `path:line` claim with the label its own line carries (invocation unless it says otherwise)."""
    claims = []
    for line in normalize(text).split("\n"):
        cites = citations(line)
        if not cites:
            continue
        label = claim_label(line)
        for cite in cites:
            path = _resolve_path(cite["path"], known)
            span = list(range(cite["start"], cite["end"] + 1)) if 0 <= cite["end"] - cite["start"] <= 500 \
                else [cite["start"]]
            claims.append({"path": path or cite["path"], "resolved": path is not None, "lines": span,
                           "label": label, "line_text": line})
    return claims


def _kind_map(key):
    kinds = collections.defaultdict(set)
    for group, kind in (("name_calls", "name_call"), ("attr_calls", "attr_call"), ("imports", "import"),
                        ("mentions", "mention")):
        for entry in key.get(group, []):
            kinds[(entry[0], entry[1])].add(kind)
    return kinds


def evaluate_sites(key, text, *, complete, once, names=None):
    """Reasons and the claimed true sites for one answer against a symbol-site key (R2-04, R2-05)."""
    sites = key["sites"] if "sites" in key else key["name_calls"]
    true_sites = {(entry[0], entry[1]) for entry in sites}
    known = {entry[0] for group in ("name_calls", "attr_calls", "imports", "mentions") for entry in key.get(group, [])}
    known |= {entry[0] for entry in sites}
    if "def" in key:
        known.add(key["def"][0])
    kinds = _kind_map(key)
    for site in true_sites:
        kinds[site].add("name_call")
    definition = key.get("def")
    reasons, claimed, defined, claim_lines = set(), [], definition is None, {}
    for claim in claims_from_text(text, known):
        if not claim["resolved"]:
            continue
        if definition and claim["path"] == definition[0] and any(definition[1] <= n <= definition[2]
                                                                 for n in claim["lines"]):
            defined = True
        if claim["label"] != "invocation":
            continue
        for number in claim["lines"]:
            position = (claim["path"], number)
            found = kinds.get(position, set())
            if "name_call" in found:
                claimed.append(position)
                claim_lines.setdefault(position, claim["line_text"])
            elif any(kind in found and site_is_excluded(kind) for kind in ("attr_call", "import", "mention")):
                reasons.add("site_excluded")
            elif len(claim["lines"]) == 1 and not (definition and position[0] == definition[0]
                                                    and definition[1] <= number <= definition[2]):
                reasons.add("site_spurious")
    if once and len(claimed) != len(set(claimed)):
        reasons.add("site_duplicated")
    if complete and true_sites - set(claimed):
        reasons.add("sites_missing")
    if not defined:
        reasons.add("definition_missing")
    return reasons, claimed, claim_lines


def oracle_T5(params, key, ans, readings, ctx=None):
    complete = readings["R2-04"] == "complete_and_precise"
    reasons, _, _ = evaluate_sites(key, answer_text(ans), complete=complete, once=False)
    return {"A": _finish(reasons, False)}


def _events_and_sum(text, key):
    reasons, unparsed = set(), False
    low_lines = normalize(text).split("\n")
    lo, hi = key["range"]
    found_events = False
    for line in low_lines:
        if not has_word(line, "error"):
            continue
        cut = len(line)
        for word in ("sum", "value", "total"):
            positions = word_positions(line, word)
            if positions:
                cut = min(cut, positions[0])
        values = int_values(_line_values(line[:cut]))
        if not values:
            continue
        found_events = True
        wanted = sorted(key["error_events"])
        if sorted(values) != wanted:
            trimmed = list(values)
            for bound in (lo, hi):
                if bound in trimmed and bound not in wanted:
                    trimmed.remove(bound)
            if sorted(trimmed) != wanted:
                reasons.add("events")
        break
    if not found_events:
        unparsed = True
    sums = []
    for line in low_lines:
        for label in ("sum", "total"):
            sums.extend(token["value"] for token in ints_by_label(line, label))
    unparsed |= decide(sums, key["value_sum"], "value_sum", reasons)
    return reasons, unparsed


def oracle_T26(params, key, ans, readings, ctx=None):
    text = answer_text(ans)
    reasons, unparsed = _events_and_sum(text, key)
    site_reasons, _, _ = evaluate_sites(key, text, complete=True, once=True)
    return {"A": _finish(reasons | site_reasons, unparsed)}


def _resolve_quote_lines(key, path, start, end):
    lines = key["files"].get(path)
    if lines is None:
        return None
    return " ".join(flat(item) for item in lines[max(start - 1, 0):max(end, start)])


def oracle_T6(params, key, ans, readings, ctx=None):
    raw = answer_text(ans)
    reasons = set()
    lines = raw.split("\n")
    in_range = False
    for line in lines:
        for cite in citations(line):
            if _citation_matches(cite, key["path"]) and key["lineno"] <= cite["start"] <= key["end_lineno"]:
                in_range = True
    for index, content, column in code_spans(raw):
        line = lines[index]
        earlier = [cite for cite in citations(line) if cite["pos"] < column]
        if not earlier:
            continue
        cite = earlier[-1]
        target = next((path for path in key["files"] if _citation_matches(cite, path)), None)
        haystack = _resolve_quote_lines(key, target, cite["start"], cite["end"]) if target else None
        if haystack is not None and flat(content) not in haystack:
            reasons.add("citation_unresolved")
    for block in fenced_blocks(raw):
        before = lines[block["start"] - 1] if block["start"] > 0 else ""
        cites = citations(before)
        if not cites:
            continue
        cite = cites[-1]
        target = next((path for path in key["files"] if _citation_matches(cite, path)), None)
        if target is None:
            continue
        span = " ".join(flat(item) for item in key["files"][target][max(cite["start"] - 1, 0):
                                                                    cite["start"] + len(block["body"].split("\n")) + 1])
        for row in block["body"].split("\n"):
            if row.strip() and flat(row) not in span:
                reasons.add("citation_unresolved")
    if not in_range:
        reasons.add("citation_missing")
    low = flat(raw).lower()
    named = {"author_association": "author_association" in low,
             "user.type": "user.type" in low or "user type" in low,
             "performed_via_github_app": "performed_via_github_app" in low or "github app" in low,
             "repository_owner": "repository_owner" in low or "repository owner" in low or "repo owner" in low}
    missing = [name for name in key["conditions"] if not named[name]]
    return {"A": _finish(reasons, False, conditions_missing=missing, d_packet_incomplete=bool(missing))}


def oracle_T7(params, key, ans, readings, ctx=None):
    if "recipes/host-request-lane.md" not in flat(answer_text(ans)):
        return {"A": fail("citation_missing")}
    return {"A": ok()}


def _strip_list_marker(body):
    body = body.strip()
    if body[:1] in ("-", "*", "\u2022") and body[1:2] == " ":
        return body[2:].strip()
    end = 0
    while end < len(body) and body[end].isdigit():
        end += 1
    if end and end < len(body) and body[end] in ".)" and body[end + 1:end + 2] == " ":
        return body[end + 2:].strip()
    return body


def _identifier(item):
    item = item.strip().strip("`'\"()[]")
    return item if item and not item[0].isdigit() and all(is_word_char(char) for char in item) else None


def listed_identifiers(raw):
    """Bare identifiers written as list items, in code spans or in fenced blocks (dot-qualified names never count)."""
    found = set()
    for block in fenced_blocks(raw):
        found.update(word for _, _, word in iter_words(block["body"]) if _identifier(word))
    for _, content, _ in code_spans(raw):
        if _identifier(content):
            found.add(content.strip())
    for _, line in outside_fences(raw):
        body = _strip_list_marker(line)
        if ":" in body and body.count(",") >= 2:
            body = body.rsplit(":", 1)[1]
        items = body.replace("`", "").split(",")
        if len(items) >= 3:
            named = [_identifier(piece) for piece in items]
            if sum(1 for item in named if item) >= 0.7 * len(items):
                found.update(item for item in named if item)
        elif len(items) == 1 and _identifier(body):
            found.add(_identifier(body))
    return found


def oracle_T8(params, key, ans, readings, ctx=None):
    raw = answer_text(ans)
    words = {word for _, _, word in iter_words(raw)}
    reasons = set()
    if [name for name in key["names"] if name not in words]:
        reasons.add("names_missing")
    listed = listed_identifiers(raw)
    if [name for name in key["distractors"] if name in listed]:
        reasons.add("name_excluded")
    stated = [token["value"] for label in ("total", "functions", "names") for token in ints_by_label(normalize(raw), label)]
    if stated and single(stated, len(key["names"])) == "wrong":
        reasons.add("count")
    return {"A": _finish(reasons, False)}


def oracle_T9(params, key, ans, readings, ctx=None):
    return {"A": grade_payload(ans, key, readings, (ctx or {}).get("extractions"))}


def oracle_T10(params, key, ans, readings, ctx=None):
    text = normalize(answer_text(ans))
    reasons, unparsed = set(), False
    files = {path for path, _ in key["sites"]}
    if [path for path in files if path not in text]:
        reasons.add("files_missing")
    counts = []
    for line in text.split("\n"):
        if any(has_word(line, word) for word in ("subprocess", "count", "total", "calls", "invocations", "occurrences")):
            for token in _line_values(line):
                following = line[token["end"]:].lstrip().split(" ", 1)[0].strip(",.;:").lower()
                if following not in ("files", "file", "scripts", "modules"):  # a file count is not the call count
                    counts.append(token["value"])
    unparsed |= decide(counts, key["count"], "count", reasons)
    true_sites = {(path, line) for path, line in key["sites"]}
    claimed = []
    for claim in claims_from_text(text, files):
        if not claim["resolved"] or claim["label"] != "invocation" or len(claim["lines"]) != 1:
            continue
        position = (claim["path"], claim["lines"][0])
        if position in true_sites:
            claimed.append(position)
        else:
            reasons.add("site_spurious")
    if claimed and true_sites - set(claimed):
        reasons.add("sites_missing")
    return {"A": _finish(reasons, unparsed)}


def oracle_T11(params, key, ans, readings, ctx=None):
    reading = readings["R2-05"]
    text = answer_text(ans)
    sites = [(entry[0], entry[1], entry[2]) for entry in key["sites"]]
    view = {"name_calls": [[p, n] for p, n, _ in sites], "attr_calls": key.get("attr_calls", []),
            "imports": key.get("imports", []), "mentions": key.get("mentions", [])}
    functions = sorted({name for _, _, name in sites if name != "<module>"})
    reasons = set()
    if reading == "functions_only":
        words = {word for _, _, word in iter_words(text)}
        if [name for name in functions if name not in words]:
            reasons.add("functions_missing")
        return {"A": _finish(reasons, False)}
    found, claimed, lines = evaluate_sites(view, text, complete=True, once=False)
    reasons |= {reason for reason in found if reason != "definition_missing"}
    if reading == "sites_and_functions":
        for path, number, name in sites:
            line = lines.get((path, number))
            if line is not None and name != "<module>" and not has_word(line, name, ignore_case=False):
                reasons.add("functions_missing")
    return {"A": _finish(reasons, False)}


def oracle_T12(params, key, ans, readings, ctx=None):
    facts = (ctx or {}).get("facts")
    if not facts:
        return {"A": unknown("key_missing")}
    text = flat(answer_text(ans))
    reasons, unparsed = set(), False
    if "Idempotency-Key" not in text:
        unparsed = True
    hours = [token["value"] for token in ints_by_label(text, "hours")]
    unparsed |= decide(hours, facts["retention_hours"], "retention", reasons)
    return {"A": _finish(reasons, unparsed)}


def oracle_T13(params, key, ans, readings, ctx=None):
    scopes = ((ctx or {}).get("facts") or {}).get("scopes") or ["local", "project", "user"]
    text = flat(answer_text(ans))
    missing = [scope for scope in scopes if not has_word(text, scope)]
    return {"A": unknown("unparsed", missing=missing) if missing else ok()}


def normalize_url(url):
    """R2-18: lowercase scheme and host, no fragment, no default port, trailing punctuation removed."""
    url = url.strip().rstrip(".,;:)>]}'\"")
    if "#" in url:
        url = url.split("#", 1)[0]
    scheme, sep, rest = url.partition("://")
    if not sep:
        return url
    host, slash, path = rest.partition("/")
    host = host.lower()
    for default in (":443", ":80"):
        if host.endswith(default):
            host = host[:-len(default)]
    return scheme.lower() + "://" + host + (slash + path if slash else "")


def extract_urls(text):
    urls = []
    for scheme in ("https://", "http://"):
        start = 0
        while True:
            index = text.find(scheme, start)
            if index < 0:
                break
            end = index
            while end < len(text) and not text[end].isspace() and text[end] not in "<>\"'`":
                end += 1
            urls.append(normalize_url(text[index:end]))
            start = end
    return urls


def url_matches(found, wanted, reading):
    if reading == "host_and_path_suffix":
        host, _, path = normalize_url(wanted).partition("://")[2].partition("/")
        f_host, _, f_path = found.partition("://")[2].partition("/")
        return f_host == host and (f_path.endswith(path.rsplit("/", 1)[-1]) if path else True)
    return found == normalize_url(wanted)


PATHLIB_URL = "https://docs.python.org/3/library/pathlib.html"


def oracle_web(params, key, ans, readings, ctx=None):
    payload = grade_payload(ans, key, readings, (ctx or {}).get("extractions"))
    raw = answer_text(ans)
    reasons = set()
    words = {word for _, _, word in iter_words(raw)}
    urls = extract_urls(raw)
    wanted = (params.get("urls") or [None, PATHLIB_URL])[-1]
    if "read_text" not in words or "encoding" not in words \
            or not any(url_matches(found, wanted, readings["R2-18"]) for found in urls):
        reasons.add("citation_missing")
    return {"A": combine({"payload": payload, "citation": fail(*reasons) if reasons else ok()})}


def _oracle_catalog(name):
    def oracle(params, key, ans, readings, ctx=None):
        text = flat(answer_text(ans))
        entry = TEMPLATES[name]
        reasons = set()
        unparsed = False
        if [item for item in entry["literals"] if item.startswith("catalogs/") and item not in text]:
            reasons.add("citation_missing")
        if "docs/harness-defaults.md" not in text:
            unparsed = True  # a paraphrased mention of the anti-pattern log is the judge's to read
        low = text.lower()
        if [fact for fact in entry["facts"] if fact.lower() not in low]:
            unparsed = True
        return {"A": _finish(reasons, unparsed)}
    return oracle


def _exit_values(text):
    values = []
    for label in ("exit", "exited", "returned"):
        values.extend(token["value"] for token in ints_by_label(text, label, nouns=("code", "status", "with")))
    return values


def _has_summary(text, summary):
    """The exact summary line text, not followed by another digit (PASS partition 2 is not PASS partition 20)."""
    start = 0
    while True:
        index = text.find(summary, start)
        if index < 0:
            return False
        after = text[index + len(summary):index + len(summary) + 1]
        if not (after and is_digit(after)):
            return True
        start = index + 1


def oracle_T27(params, key, ans, readings, ctx=None):
    text = normalize(answer_text(ans))
    reasons, unparsed = set(), False
    unparsed |= decide(_exit_values(text), 0, "exit", reasons)
    if not _has_summary(text, key["summary"]):
        reasons.add("summary_literal")
    if [name for name in key["ls"] if name not in text]:
        reasons.add("inventory")
    if not has_int(int_tokens(text), key["wc_l"]):
        reasons.add("line_count")
    components = {"A": _finish(reasons, unparsed)}
    run = key.get("acceptance")
    if run is None:
        components["B"] = unknown("key_missing")
    else:
        components["B"] = ok() if run.get("exit") == 0 and run.get("last_line") == key["summary"] else fail("acceptance_run")
    return components


def _labelled(text, labels, expected, nouns, reason, reasons):
    """True when no integer sits next to any of the labels (unparsed); records a wrong one as a failure reason."""
    values = [token["value"] for label in labels for token in ints_by_label(text, label, nouns)]
    return decide(values, expected, reason, reasons)


def oracle_T28(params, key, ans, readings, ctx=None):
    text = normalize(answer_text(ans))
    reasons, unparsed = set(), False
    if [name for name in key["files"] if name not in text]:
        reasons.add("files")
    unparsed |= _labelled(text, ("hunks", "hunk"), key["hunks"], (), "hunks", reasons)
    unparsed |= _labelled(text, ("added",), key["added"], ("lines", "line"), "added", reasons)
    unparsed |= _labelled(text, ("deleted", "removed"), key["deleted"], ("lines", "line"), "deleted", reasons)
    return {"A": _finish(reasons, unparsed)}


def oracle_T29(params, key, ans, readings, ctx=None):
    text = normalize(answer_text(ans))
    reasons, unparsed = set(), False
    if not has_word(text, key["function"], ignore_case=False):
        reasons.add("name_missing")
    counts = count_before_noun(text, ("lines", "line"))
    if not counts:
        unparsed = True
    elif any(value not in (key["before_lines"], key["after_lines"]) for value in counts) \
            or (key["before_lines"] == key["after_lines"] and any(value != key["before_lines"] for value in counts)):
        reasons.add("line_count")
    return {"A": _finish(reasons, unparsed)}


def oracle_T30(params, key, ans, readings, ctx=None):
    text = normalize(answer_text(ans))
    reasons = set()
    unparsed = decide(_exit_values(text), key["exit"], "exit", reasons)
    return {"A": _finish(reasons, unparsed)}


def oracle_T32(params, key, ans, readings, ctx=None):
    text = normalize(answer_text(ans))
    reasons, unparsed = set(), False
    verdicts = []
    for position in word_positions(text, "verdict"):
        clause = text[position + len("verdict"):]
        for stop in ("\n", ";", ". "):
            cut = clause.find(stop)
            if cut >= 0:
                clause = clause[:cut]
        verdicts.extend(word for word in ("yes", "no") if has_word(clause, word))
    if not verdicts:
        present = {word for word in ("yes", "no") if has_word(text, word)}
        verdicts = list(present) if len(present) == 1 else []
    if len(set(verdicts)) != 1:
        unparsed = True  # none, or both ("yes or no"): a hedge is not a verdict
    elif verdicts[0] != key["verdict"]:
        reasons.add("verdict")
    unparsed |= decide([token["value"] for token in ints_by_label(text, "id")], key["record_id"], "record_id", reasons)
    latencies = [token["value"] for label in ("latency", "ms") for token in ints_by_label(text, label,
                                                                                            ("ms", "milliseconds"))]
    unparsed |= decide(latencies, key["latency_ms"], "latency", reasons)
    return {"A": _finish(reasons, unparsed)}


def oracle_T33(params, key, ans, readings, ctx=None):
    text = normalize(answer_text(ans))
    reasons, unparsed = set(), False
    listed = None
    open_at = text.find("[")
    if open_at >= 0 and text.find("]", open_at) > open_at:
        listed = int_values(int_tokens(text[open_at:text.find("]", open_at) + 1]))
    if listed is None:
        listed = []
        for line in text.split("\n"):
            if has_word(line, "event") or has_word(line, "events"):
                listed.extend(int_values(_line_values(line)))
    if not listed:
        unparsed = True
    elif listed != key["events"]:
        reasons.add("events")
    if any(has_word(text, level, ignore_case=False) for level in ("WARN", "WARNING", "ERROR", "DEBUG")):
        reasons.add("levels")
    elif not has_word(text, "INFO", ignore_case=False):
        unparsed = True
    return {"A": _finish(reasons, unparsed)}


def oracle_T34(params, key, ans, readings, ctx=None):
    """A bare integer is the answer; otherwise integers written next to a count word; otherwise every integer."""
    text = normalize(answer_text(ans))
    bare = int_tokens(text.strip().strip("."))
    if len(bare) == 1 and bare[0]["start"] == 0 and bare[0]["end"] == len(text.strip().strip(".")):
        values = [bare[0]["value"]]
    else:
        values = [token["value"] for label in ("error", "errors", "count", "records")
                  for token in ints_by_label(text, label)]
        if not values:
            values = [token["value"] for token in int_tokens(text)]
    reasons = set()
    unparsed = decide(values, key["count"], "count", reasons)
    return {"A": _finish(reasons, unparsed)}


def oracle_T35(params, key, ans, readings, ctx=None):
    text = normalize(answer_text(ans))
    firsts = [token["value"] for token in ints_by_label(text, "first")]
    lasts = [token["value"] for token in ints_by_label(text, "last")]
    if not firsts and not lasts:
        values = int_values(int_tokens(text))
        if len(values) == 2:
            firsts, lasts = [values[0]], [values[1]]
        else:
            return {"A": unknown("unparsed")}
    reasons = set()
    unparsed = decide(firsts, key["first"], "first", reasons)
    unparsed |= decide(lasts, key["last"], "last", reasons)
    return {"A": _finish(reasons, unparsed)}


def oracle_T37(params, key, ans, readings, ctx=None):
    text = normalize(answer_text(ans))
    reasons = set()
    if not has_word(text, key["function"], ignore_case=False) or ("!" not in text and "exclamation" not in text.lower()):
        reasons.add("names_missing")
    return {"A": _finish(reasons, False)}


_ELEMENTS = []


def markdown_elements(text):
    """scripts/native_token_ci.py markdown_elements, loaded once from this checkout (upstream code, unchanged)."""
    if not _ELEMENTS:
        import importlib.util
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        spec = importlib.util.spec_from_file_location("native_token_ci_for_grader",
                                                      os.path.join(root, "scripts", "native_token_ci.py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _ELEMENTS.append(module.markdown_elements)
    return _ELEMENTS[0](text)


def oracle_T38(params, key, ans, readings, ctx=None):
    """R2-06: `answer_elements` (decided) reads the answer as Markdown, the ten structure checks of markdown_elements;
    `element_contents` reads the content of the same ten elements wherever it sits (each string of the fixture's element,
    as a whole word, in the normalized answer), so a plain report of the fixture passes only the second reading."""
    if key.get("input_sha256") is not None and key["input_sha256"] != key["fixture_sha256"]:
        return {"A": unknown("input_hash")}
    if readings["R2-06"] == "element_contents":
        contents = key.get("contents")
        if not isinstance(contents, dict) or not contents:
            return {"A": unknown("key_missing")}
        text = flat(answer_text(ans))
        missing = sorted(kind for kind, strings in contents.items()
                         if not all(has_word(text, flat(string), ignore_case=False) for string in strings))
    else:
        held = markdown_elements(answer_text(ans))
        missing = sorted(name for name, present in held.items() if not present)
    return {"A": fail("elements_missing", missing=missing) if missing else ok()}


def oracle_pending(reason):
    def oracle(params, key, ans, readings, ctx=None):
        return {"A": pending(reason)}
    return oracle


ORACLES = {
    "T1": oracle_T1, "T2": oracle_T2, "T3": oracle_T3, "T4": oracle_T4, "T5": oracle_T5, "T6": oracle_T6,
    "T7": oracle_T7, "T8": oracle_T8, "T9": oracle_T9, "T10": oracle_T10, "T11": oracle_T11, "T12": oracle_T12,
    "T13": oracle_T13, "T14": oracle_pending("needs_identity_table"),
    "T26": oracle_T26, "T27": oracle_T27, "T28": oracle_T28, "T29": oracle_T29, "T30": oracle_T30,
    "T32": oracle_T32, "T33": oracle_T33, "T34": oracle_T34, "T35": oracle_T35, "T37": oracle_T37, "T38": oracle_T38,
}
for _name in WEB_TEMPLATES:
    ORACLES[_name] = oracle_web
for _name in CATALOG_TEMPLATES:
    ORACLES[_name] = _oracle_catalog(_name)


# ---- T0: six captures per arm, pre and post, under the arm's conditions and plain (R10, U9-D11) -----------------

T0_FIELDS = ("ran", "status", "skipped", "failures", "errors")
_T0_REASONS = {"ran": "test_count", "status": "test_status", "skipped": "test_skipped", "failures": "test_failures",
               "errors": "test_errors"}


def minimal_env(home=None):
    """The allowlisted environment of every grader subprocess: PATH, LANG, TMPDIR, a HOME that is not the operator's
    and the operator's per-user Python base. No operator secret and not RUN_TOKEN reaches a command that runs a tree's
    code (review J-5, K-3). The throwaway HOME would also hide the user site packages the child ran with (a PyYAML
    there changes how many tests tests.test_host_requests skips), so PYTHONUSERBASE names the base the operator's own
    interpreter uses; a path to a package directory carries no secret."""
    source = os.environ
    env = {"PATH": source.get("PATH", "/usr/bin:/bin"), "LANG": source.get("LANG") or "C.UTF-8",
           "TMPDIR": source.get("TMPDIR", "/tmp"), "HOME": home or tempfile.gettempdir()}
    base = source.get("PYTHONUSERBASE") or site.getuserbase()
    if base:
        env["PYTHONUSERBASE"] = base
    return env


def _git_env(env):
    merged = dict(minimal_env() if env is None else env)
    merged["GIT_OPTIONAL_LOCKS"] = "0"  # `git status` must not refresh (write) the index of a tree we only observe
    merged["GIT_PAGER"] = "cat"
    return merged


def _git(tree, *args, env=None):
    return subprocess.run(["git", "-C", str(tree), *args], capture_output=True, stdin=subprocess.DEVNULL,
                          env=_git_env(env))


def is_bytecode_path(path):
    """A bytecode cache: a `__pycache__` path component or a .pyc/.pyo file. A child that ran Python leaves these, and
    they are neither a change to the tree nor ever copied into a grader run (a planted one would execute)."""
    return "__pycache__" in path.split("/") or path.endswith((".pyc", ".pyo"))


def porcelain_entries(tree):
    """git status --porcelain=v1 -z --untracked-files=all --ignored=matching as sorted {status, path} entries (R13),
    without bytecode caches (review F-1: they would make every post capture `tree_changed` and every builder tree
    carry an extra file); every other ignored file stays."""
    done = _git(tree, "status", "--porcelain=v1", "-z", "--untracked-files=all", "--ignored=matching")
    fields = done.stdout.decode("utf-8", errors="replace").split("\0")
    entries, index = [], 0
    while index < len(fields):
        item = fields[index]
        index += 1
        if len(item) < 4:
            continue
        code, path = item[:2], item[3:]
        if code[0] in "RC":
            index += 1
        if not is_bytecode_path(path.rstrip("/")):
            entries.append({"status": code.replace(" ", "") or code, "path": path})
    return sorted(entries, key=lambda entry: entry["path"])


def tree_state(tree):
    """HEAD plus the digest of the porcelain status (ignored files included): the identity of a tree's contents."""
    head = _git(tree, "rev-parse", "HEAD").stdout.decode("utf-8", errors="replace").strip()
    return {"head": head, "status_sha256": sha256_hex(canonical(porcelain_entries(tree)))}


def parse_git_log_subjects(text):
    subjects, in_block, taken = [], False, False
    for line in text.split("\n"):
        if line.startswith("commit ") and is_hex(line[7:47], 40):
            in_block, taken = True, False
        elif in_block and not taken and line.startswith("    ") and line.strip():
            subjects.append(line.strip())
            taken = True
    return subjects


def _parse_paren_counts(text):
    counts = {}
    if "(" in text and ")" in text:
        inner = text[text.index("(") + 1:text.rindex(")")]
        for part in inner.split(","):
            name, sep, number = part.strip().partition("=")
            if sep and number.strip().isdigit():
                counts[name.strip()] = int(number)
    return counts


def parse_unittest_facts(text):
    """{ran, status, skipped, failures, errors} from unittest's own summary lines (structural, not free text)."""
    facts = {"ran": None, "status": None, "skipped": 0, "failures": 0, "errors": 0}
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("Ran ") and " test" in stripped:
            number = stripped[4:].split(" ", 1)[0]
            if number.isdigit():
                facts["ran"] = int(number)
        elif stripped == "OK" or stripped.startswith("OK ("):
            facts["status"] = "OK"
            facts["skipped"] = _parse_paren_counts(stripped).get("skipped", 0)
        elif stripped == "FAILED" or stripped.startswith("FAILED ("):
            facts["status"] = "FAILED"
            counts = _parse_paren_counts(stripped)
            facts["skipped"] = counts.get("skipped", 0)
            facts["failures"] = counts.get("failures", 0)
            facts["errors"] = counts.get("errors", 0)
    return facts


def _prefix(sandbox_prefix, cwd):
    return list(sandbox_prefix(cwd)) if callable(sandbox_prefix) else list(sandbox_prefix)


def _run_capture(identity, argv, cwd, env, sandbox_prefix, timeout):
    start = utc_now()
    try:
        done = subprocess.run(_prefix(sandbox_prefix, cwd) + list(argv), cwd=cwd, env=_git_env(env),
                              capture_output=True, stdin=subprocess.DEVNULL, timeout=timeout)
        code, out, err, error = done.returncode, done.stdout, done.stderr, None
    except subprocess.TimeoutExpired:
        code, out, err, error = None, b"", b"", "timeout"
    except OSError:
        code, out, err, error = None, b"", b"", "spawn_failed"
    run = {"id": identity, "argv": list(argv), "exit": code, "stdout_sha256": sha256_hex(out),
           "stderr_sha256": sha256_hex(err), "start": start, "end": utc_now(), "facts": {}}
    if error:
        run["error"] = error
    return run, out.decode("utf-8", errors="replace"), err.decode("utf-8", errors="replace")


def _copy_tree(tree, destination):
    listing = _git(tree, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
    os.makedirs(destination, exist_ok=True)
    if listing.returncode != 0:
        shutil.copytree(tree, destination, ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc", "*.pyo"),
                        dirs_exist_ok=True, symlinks=True)
        return
    for name in sorted(item for item in listing.stdout.decode("utf-8", errors="replace").split("\0") if item):
        source = os.path.join(tree, name)
        if is_bytecode_path(name) or not os.path.lexists(source):
            continue
        target = os.path.join(destination, name)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.copy2(source, target, follow_symlinks=False)


def rerun_unittest_in_copy(tree, env, sandbox_prefix=(), timeout=900):
    """Correction 2: the arm's own command in a temporary COPY of the tree (isolate the tree, not the interpreter),
    with PYTHONDONTWRITEBYTECODE=1. The command imports the tests package because the copy is its working directory."""
    argv = list(dict(T0_IDENTITIES)["unittest"])
    with tempfile.TemporaryDirectory(prefix="u9-copy-") as scratch:
        copy = os.path.join(scratch, "tree")
        cache = os.path.join(scratch, "pycache")
        os.makedirs(cache)
        _copy_tree(str(tree), copy)
        run_env = dict(minimal_env(scratch) if env is None else env)
        # A fresh, empty pycache prefix makes the interpreter ignore any cached bytecode next to the sources, so a
        # planted .pyc cannot run (it would even under -I -S); DONTWRITEBYTECODE keeps the copy source-only.
        run_env["PYTHONDONTWRITEBYTECODE"] = "1"
        run_env["PYTHONPYCACHEPREFIX"] = cache
        run, out, err = _run_capture("unittest", argv, copy, run_env, sandbox_prefix, timeout)
    run["facts"] = parse_unittest_facts(err + "\n" + out)
    run["env"] = {"PYTHONDONTWRITEBYTECODE": "1", "PYTHONPYCACHEPREFIX": "<fresh-empty-dir>"}
    return run


def capture_t0(tree, env, sandbox_prefix=(), timeout=300):
    """The six recovered identities in one tree under one set of conditions; the unittest runs in a copy."""
    before = tree_state(tree)
    started = utc_now()
    runs = []
    for identity, argv in T0_IDENTITIES:
        if identity == "unittest":
            runs.append(rerun_unittest_in_copy(tree, env, sandbox_prefix))
            continue
        run, out, _ = _run_capture(identity, argv, str(tree), env, sandbox_prefix, timeout)
        if identity == "git-log":
            run["facts"] = {"subjects": parse_git_log_subjects(out)}
        runs.append(run)
    after = tree_state(tree)
    return {"tree": before, "tree_after": after, "tree_changed_during_capture": before != after, "runs": runs,
            "started_at": started, "completed_at": utc_now(), "sandboxed": bool(callable(sandbox_prefix)
                                                                                  or sandbox_prefix)}


def post_capture_t0(tree, pre_tree, env, sandbox_prefix=(), timeout=300):
    """A tree that changed since the pre-arm capture is not re-run: the post capture is discarded (R10, R13)."""
    if tree_state(tree) != pre_tree:
        return {"discarded": "tree_changed"}
    return capture_t0(tree, env, sandbox_prefix, timeout)


def mismatch_outcome(env_dependent):
    """An answer that disagrees with an environment-dependent field is unknown(env_mismatch), otherwise a failure."""
    return "unknown" if env_dependent else "fail"


def _t0_runs(capture):
    return {run["id"]: run for run in capture["runs"]}


def _t0_key_facts(capture):
    runs = _t0_runs(capture)
    subjects = (runs.get("git-log") or {}).get("facts", {}).get("subjects") or [None]
    unit = (runs.get("unittest") or {}).get("facts", {})
    return subjects[0], tuple(unit.get(name) for name in T0_FIELDS)


def _t0_capture_status(pre, post):
    ids = [name for name, _ in T0_IDENTITIES]
    captures = [pre["arm"], pre["plain"]]
    complete_post = bool(post) and "discarded" not in post
    if complete_post:
        captures += [post["arm"], post["plain"]]
    for capture in captures:
        if [name for name in ids if name not in _t0_runs(capture)]:
            return fail("capture_missing")
    if complete_post:
        for condition in ("arm", "plain"):
            if _t0_key_facts(pre[condition]) != _t0_key_facts(post[condition]):
                return unknown("capture_conflict")
    return ok()


def _answer_unittest(text):
    """Structural unittest facts in an answer: counts before 'tests', OK or FAILED, skipped/failures/errors numbers."""
    facts = {"ran": count_before_noun(text, ("tests", "test")), "status": [], "skipped": [], "failures": [],
             "errors": []}
    for word, status in (("OK", "OK"), ("FAILED", "FAILED")):
        if has_word(text, word, ignore_case=False):
            facts["status"].append(status)
    if not facts["status"]:
        if has_word(text, "passed"):
            facts["status"].append("OK")
        elif has_word(text, "failed"):
            facts["status"].append("FAILED")
    for name in ("skipped", "failures", "errors"):
        facts[name] = [token["value"] for token in ints_by_label(text, name)]
    return facts


def _apply_extraction(facts, extractions, raw):
    """A D-extract fallback: quotes must be verbatim in the answer; the values are parsed by the same grammar."""
    for item in extractions or []:
        if item.get("component") != "unittest":
            continue
        if any(quote not in raw for quote in item.get("answer_quotes", [])) or not item.get("answer_quotes"):
            return None
        extracted = _answer_unittest(" ".join(item.get("values", [])))
        for name in ("ran", "status"):
            if not facts[name] and extracted[name]:
                facts[name] = extracted[name]
        for name in ("skipped", "failures", "errors"):
            if not facts[name] and extracted[name]:
                facts[name] = extracted[name]
        return facts
    return facts


def oracle_T0(params, key, ans, readings, ctx=None):
    ctx = ctx or {}
    captures = ctx.get("captures")
    if not captures or not captures.get("pre"):
        return {"B": unknown("key_missing"), "A": unknown("key_missing")}
    pre, post = captures["pre"], captures.get("post")
    components = {"B": _t0_capture_status(pre, post)}
    if components["B"].status == "fail":
        return dict(components, A=unknown("capture_missing"))
    arm_runs, plain_runs = _t0_runs(pre["arm"]), _t0_runs(pre["plain"])
    subjects = arm_runs["git-log"]["facts"].get("subjects") or []
    if not subjects:
        return dict(components, A=unknown("key_missing"))
    unit_arm, unit_plain = arm_runs["unittest"]["facts"], plain_runs["unittest"]["facts"]
    verified = (pre["arm"].get("conditions") or {}).get("verified", True)
    dependent = {name for name in T0_FIELDS if unit_arm.get(name) != unit_plain.get(name)}
    if not verified:
        dependent = set(T0_FIELDS)
    raw = answer_text(ans)
    text = flat(raw)
    reasons, soft, unparsed = set(), set(), False
    seen = sorted((text.find(flat(subject)), number) for number, subject in enumerate(subjects)
                  if flat(subject) and text.find(flat(subject)) >= 0)
    if not seen:
        reasons.add("subject_missing")
    elif seen[0][1] != 0:
        reasons.add("subject_not_newest")  # the first subject the answer names must be the newest
    stated = _answer_unittest(normalize(raw))
    if not stated["ran"] or not stated["status"]:
        extracted = _apply_extraction(stated, ctx.get("extractions"), raw)
        if extracted is None:
            return dict(components, A=unknown("judge_quote"))
        stated = extracted
    for name in T0_FIELDS:
        values = stated[name]
        if not values:
            if name in ("ran", "status"):
                unparsed = True
            continue
        verdict = single(values, unit_arm.get(name))  # the arm's own capture is the key; the plain one marks the fields
        if verdict == "hedge":
            unparsed = True
        elif verdict == "wrong":
            if mismatch_outcome(name in dependent) == "unknown":
                soft.add("env_mismatch")
            else:
                reasons.add(_T0_REASONS[name])
    if reasons:
        components["A"] = fail(*reasons)
    elif soft:
        components["A"] = unknown(*soft)
    elif unparsed:
        components["A"] = unknown("unparsed")
    else:
        components["A"] = ok()
    return components


ORACLES["T0"] = oracle_T0


# ---- T31 builder and T36 binding (R13, F9, F10) -----------------------------------------------------------------

GREETINGS = {"Ada": "Hello, Ada!", "Grace": "Hello, Grace!"}


def _isolated_greeting(source):
    """greeting('Ada') and greeting('Grace') from the verified bytes, compiled and run in an isolated interpreter
    (-I -S -B): nothing is imported from a file, so no planted bytecode or module next to it can run."""
    code = ("import sys\nnamespace = {}\nexec(compile(sys.stdin.buffer.read(), 'before.py', 'exec'), namespace)\n"
            "print(namespace['greeting']('Ada'))\nprint(namespace['greeting']('Grace'))\n")
    with tempfile.TemporaryDirectory(prefix="u9-greet-") as scratch:
        done = subprocess.run([sys.executable, "-I", "-S", "-B", "-c", code], input=source, capture_output=True,
                              timeout=60, env=minimal_env(scratch), cwd=scratch)
    lines = done.stdout.decode("utf-8", errors="replace").split("\n")
    return {"Ada": lines[0] if len(lines) > 0 else None, "Grace": lines[1] if len(lines) > 1 else None}


def grade_builder(prepared_path, prepared_base, observed_path, observed_base, exec_rev, after_bytes, key):
    """T31: the observed child tree is diffed against its recorded base; the code runs only after the bytes match."""
    if sha256_hex(after_bytes) != key["after_sha256"]:
        return unknown("input_hash")
    if os.path.realpath(observed_path) != os.path.realpath(prepared_path):
        return unknown("conflicting_identity")
    if not (is_hex(exec_rev, 40) and observed_base == exec_rev and prepared_base == exec_rev):
        return unknown("block_grading")
    head = _git(observed_path, "rev-parse", "HEAD").stdout.decode("utf-8", errors="replace").strip()
    if head != observed_base:
        return unknown("block_grading")
    entries = porcelain_entries(observed_path)
    reasons = set()
    if [entry for entry in entries if entry["path"] != "fixtures/before.py"]:
        reasons.add("extra_changes")
    if not any(entry["path"] == "fixtures/before.py" for entry in entries):
        reasons.add("empty_diff")
    if reasons:
        return fail(*reasons)
    target = os.path.join(observed_path, "fixtures", "before.py")
    try:
        with open(target, "rb") as stream:
            final = stream.read()
    except OSError:
        return fail("empty_diff")
    if final != after_bytes:
        return fail("bytes_differ")
    greeting = _isolated_greeting(final)
    if greeting != GREETINGS:
        return fail("greeting", greeting=greeting)
    return ok(greeting=greeting)


def grade_binding(record, ans, parent_texts=()):
    """T36: the tree's own sentinel is returned, no sibling value appears anywhere, a path alone is insufficient."""
    if record is None:
        return unknown("input_missing")
    text = answer_text(ans)
    reasons = set()
    sibling = record.get("sibling_value")
    if sibling and any(sibling in item for item in (text, *parent_texts)):
        reasons.add("sibling_value")
    if record["value"] not in text:
        has_path = any(token.startswith("/") and len(token) > 3 for token in text.split())
        reasons.add("path_only" if has_path else "sentinel_missing")
        return fail(*reasons)
    if [name for name in record["inventory"] if name not in text]:
        reasons.add("inventory_missing")
    counts = count_before_noun(normalize(text), ("lines", "line"))
    if counts and record["before_lines"] not in counts:
        reasons.add("before_lines")
    return _finish(reasons, not counts)


def binding_conflicts(record, arm, run_args):
    """Tasks whose recorded worktree path, base or input path differs from a run record's args (F26)."""
    bound = record["arms"][arm]
    everything = set(bound.get("worktree_paths", {})) | set(bound.get("worktree_bases", {})) \
        | set(bound.get("input_paths", {})) | set(run_args.get("worktree_paths", {})) \
        | set(run_args.get("worktree_bases", {})) | set(run_args.get("input_paths", {}))
    if (run_args.get("run") is not None and sha256_hex(run_args["run"]) != record.get("run_token_sha256")) \
            or (run_args.get("arm") is not None and run_args["arm"] != arm):
        return sorted(everything)
    conflicts = set()
    for group in ("worktree_paths", "worktree_bases"):
        left, right = bound.get(group, {}), run_args.get(group, {})
        conflicts |= {task for task in set(left) | set(right) if left.get(task) != right.get(task)}
    left = {task: entry["path"] for task, entry in bound.get("input_paths", {}).items()}
    right = run_args.get("input_paths", {})
    conflicts |= {task for task in set(left) | set(right) if left.get(task) != right.get(task)}
    return sorted(conflicts)


# ---- T14 archive query time (correction 3) ---------------------------------------------------------------------

def _has_agentsview(text):
    """The whole word agentsview, case-sensitive: a letter, digit or '_' on either side makes it a different word."""
    start = 0
    while True:
        index = text.find("agentsview", start)
        if index < 0:
            return False
        before = text[index - 1] if index else ""
        after = text[index + 10] if index + 10 < len(text) else ""
        if not (before and is_word_char(before)) and not (after and is_word_char(after)):
            return True
        start = index + 1


def _tool_use_texts(block):
    payload = block.get("input") or {}
    texts = []
    for name in ("command", "code"):
        if isinstance(payload.get(name), str):
            texts.append(payload[name])
    for item in payload.get("commands") or []:
        if isinstance(item, dict) and isinstance(item.get("command"), str):
            texts.append(item["command"])
    return texts


def archive_query_time(rows):
    """q: the timestamp of the child's first tool_use whose command or code holds the whole word agentsview (also in
    ctx_execute shell code) or that calls the agentsview MCP server. U1's program vocabulary cannot see it."""
    for row in rows:
        if row.get("type") != "assistant":
            continue
        content = (row.get("message") or {}).get("content")
        for block in content if isinstance(content, list) else []:
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            if "agentsview" in str(block.get("name", "")).split("__") \
                    or any(_has_agentsview(text) for text in _tool_use_texts(block)):
                return ok(q=row.get("timestamp"))
    return unknown("no_query")


# ---- Pages (R12), memory (R9) and process captures --------------------------------------------------------------

_BLOCK_TAGS = {"p", "div", "br", "li", "ul", "ol", "dt", "dd", "dl", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "td",
               "th", "pre", "section", "nav", "article", "table"}


class _PageText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        elif tag in _BLOCK_TAGS:
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip = max(0, self.skip - 1)
        elif tag in _BLOCK_TAGS:
            self.parts.append(" ")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def page_text(html_bytes):
    parser = _PageText()
    parser.feed(html_bytes.decode("utf-8", errors="replace"))
    parser.close()
    return " ".join("".join(parser.parts).split())


def _window_after(text, marker, size):
    index = text.find(marker)
    return text[index:index + size] if index >= 0 else ""


def extract_page_facts(kind, html_bytes):
    """Deterministic facts over html.parser text (R12): the frozen facts of each page, never bytes."""
    text = page_text(html_bytes)
    low = text.lower()
    if kind == "stripe":
        hours = None
        start = 0
        while hours is None:
            index = low.find("at least ", start)
            if index < 0:
                break
            tokens = int_tokens(low[index + 9:index + 20])
            if tokens and tokens[0]["start"] == 0 and low[index + 9 + tokens[0]["end"]:].lstrip().startswith("hour"):
                hours = tokens[0]["value"]
            start = index + 1
        return {"idempotency_key_header": "Idempotency-Key" in text, "retention_hours": hours}
    if kind == "mcp":
        both = "local, project, or user scope" in low or "local, project and user scope" in low
        return {"scopes": [scope for scope in ("local", "project", "user") if both or f"{scope} scope" in low]}
    if kind == "pathlib":
        window = _window_after(text, "Path.read_text(", 200)
        signature = window[len("Path.read_text("):window.find(")")] if window and ")" in window else None
        return {"read_text_signature": signature}
    if kind == "json":
        ascii_window = _window_after(text, "If ensure_ascii is true", 300)
        nan_window = _window_after(text, "If allow_nan is", 500)
        decode_window = _window_after(text, "JSONDecodeError", 200)
        return {
            "ensure_ascii_default_true": "ensure_ascii is true (the default)" in text,
            "ensure_ascii_escapes_non_ascii": "non-ASCII" in ascii_window and "escaped" in ascii_window,
            "allow_nan_false_valueerror": "ValueError" in nan_window,
            "sort_keys_sorts_dicts": "If sort_keys is true" in text and "sorted by key" in _window_after(
                text, "If sort_keys is true", 300),
            "jsondecodeerror_invalid_document": "not a valid JSON document" in decode_window,
            "loads_bytes_bytearray": "str, bytes or bytearray" in text,
        }
    return {}


def page_key(first, second, required):
    """Key drift compares facts, not bytes, between the window's open and close captures (F33)."""
    facts_a, facts_b = first.get("facts"), second.get("facts")
    if not facts_a or not facts_b:
        return "unknown", "key_missing"

    def present(value):
        return value not in (None, False, [], "")

    if any(not present(facts_a.get(name)) or not present(facts_b.get(name)) for name in required):
        return "unknown", "key_missing"
    if any(facts_a.get(name) != facts_b.get(name) for name in required):
        return "unknown", "key_drift"
    return "ok", {name: facts_a[name] for name in required}


def capture_page(kind, url):
    """One frozen page through `curl --fail -sSL`: status, effective URL, bytes, sha256 and the extracted facts."""
    failed = {"kind": kind, "status": None, "effective_url": None, "bytes": None, "sha256": None, "facts": None,
              "error": "download_failed"}
    if not url.startswith(("https://", "http://")):
        return dict(failed, error="bad_url")  # never hand curl something that could parse as an option
    with tempfile.TemporaryDirectory(prefix="u9-page-") as scratch:
        target = os.path.join(scratch, "page")
        try:
            done = subprocess.run(["curl", "--fail", "-sSL", "--proto", "=http,https", "--proto-redir", "=http,https",
                                   "-o", target, "-w", "%{http_code} %{url_effective}", url],
                                  capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=180)
        except (OSError, subprocess.TimeoutExpired):
            return failed
        if done.returncode != 0 or not os.path.exists(target):
            return failed
        with open(target, "rb") as stream:
            body = stream.read()
    code, _, effective = done.stdout.strip().partition(" ")
    if not code.isdigit():
        return failed
    return {"kind": kind, "status": int(code), "effective_url": effective, "bytes": len(body),
            "sha256": sha256_hex(body), "facts": extract_page_facts(kind, body)}


def _ai_memory_json(arguments, task):
    try:
        done = subprocess.run(["ai-memory", *arguments], capture_output=True, text=True, stdin=subprocess.DEVNULL,
                              timeout=180)
        if done.returncode != 0:
            raise ValueError("exit")
        return json.loads(done.stdout)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        raise Refusal("E_MEMORY_KEY", task=task, reason="query") from None


def memory_keys(topics, scope, since):
    """R9 at freeze: the qualifying historical records per topic, created before SINCE, holding the anchor terms.
    A topic with no such record refuses (`E_MEMORY_KEY task=<id>`), in sorted task order, before anything launches."""
    cutoff = parse_utc(since)
    where = ["--workspace", scope["workspace"], "--project", scope["project"]]
    frozen = {}
    for task in sorted(topics):
        config = topics[task]
        rows = _ai_memory_json(["search", "--json", "-n", "50", *where, "--", config["query"]], task)
        records = []
        for row in rows if isinstance(rows, list) else []:
            page = _ai_memory_json(["read-page", "--json", "--path", row["path"], *where], task)
            created = ((page.get("frontmatter") or {}).get("generated") or {}).get("at")
            stamp = parse_utc(created)
            body = page.get("body") or ""
            haystack = (body + " " + (page.get("title") or "")).lower()
            if stamp is None or cutoff is None or stamp >= cutoff:
                continue
            if not all(anchor.lower() in haystack for anchor in config["anchors"]):
                continue
            records.append({"path": row["path"], "created_at": created, "content_sha256": sha256_hex(body)})
        records.sort(key=lambda record: record["path"])
        if not records:
            raise Refusal("E_MEMORY_KEY", task=task)
        frozen[task] = records
    return frozen


def qmd_coverage(config, documents):
    """Whether each repository document appears in the frozen qmd collections (read-only `qmd ls`)."""
    coverage = {}
    listings = {}
    for collection in config["collections"]:
        try:
            done = subprocess.run(["qmd", "--index", config["index"], "ls", collection], capture_output=True,
                                  text=True, stdin=subprocess.DEVNULL, timeout=120)
        except (OSError, subprocess.TimeoutExpired):
            done = None
        listings[collection] = done.stdout if done is not None and done.returncode == 0 else None
    for document in documents:
        base = document.rsplit("/", 1)[-1]
        found = [name for name, text in listings.items()
                 if text and any(line.strip().endswith("/" + base) for line in text.split("\n"))]
        coverage[document] = {"covered": bool(found), "collection": found[0] if found else None,
                              "queried": all(text is not None for text in listings.values())}
    return coverage


def list_processes(since_epoch):
    """Processes that started at or after `since_epoch` (Linux /proc): start (UTC), comm and parent pid."""
    try:
        with open("/proc/stat", "rb") as stream:
            boot = next(int(line.split()[1]) for line in stream.read().decode().split("\n") if line.startswith("btime "))
        ticks = os.sysconf("SC_CLK_TCK")
    except (OSError, StopIteration, ValueError):
        return None
    found = []
    for name in os.listdir("/proc"):
        if not name.isdigit():
            continue
        try:
            with open(f"/proc/{name}/stat", "rb") as stream:
                stat = stream.read().decode("utf-8", errors="replace")
            fields = stat[stat.rindex(")") + 2:].split()
            started = boot + int(fields[19]) / ticks
            with open(f"/proc/{name}/comm", "rb") as stream:
                comm = stream.read().decode("utf-8", errors="replace").strip()
        except (OSError, ValueError, IndexError):
            continue
        if started >= since_epoch:
            found.append({"start": datetime.datetime.fromtimestamp(started, datetime.timezone.utc)
                          .strftime("%Y-%m-%dT%H:%M:%SZ"), "comm": comm, "ppid": int(fields[1]), "pid": int(name)})
    return sorted(found, key=lambda entry: (entry["start"], entry["comm"], entry["ppid"], entry["pid"]))


def _export_paths(repo, rev, paths, destination):
    """Extract the named paths of a commit with `git archive` (regular files and directories only)."""
    import tarfile
    done = subprocess.run(["git", "-C", str(repo), "archive", "--format=tar", rev, *paths], capture_output=True,
                          stdin=subprocess.DEVNULL)
    if done.returncode != 0:
        raise Refusal("E_CAPTURE", field="exec_rev")
    with tarfile.open(fileobj=io.BytesIO(done.stdout)) as archive:
        for member in archive:
            name = os.path.normpath(member.name)
            if name.startswith("..") or os.path.isabs(name):
                continue
            target = os.path.join(destination, name)
            if member.isdir():
                os.makedirs(target, exist_ok=True)
            elif member.isreg():
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with archive.extractfile(member) as source, open(target, "wb") as sink:
                    sink.write(source.read())
                os.chmod(target, member.mode & 0o755 or 0o644)


def capture_post_w(repo, exec_rev, acceptance):
    """T27 and T30: the acceptance commands and py_compile in an exported (git archive) tree at exec_rev, with a
    private PYTHONPYCACHEPREFIX, so the exec checkout is never written (design deviation D-08)."""
    result = {"acceptance": {}, "py_compile": None}
    with tempfile.TemporaryDirectory(prefix="u9-postw-") as scratch:
        tree = os.path.join(scratch, "tree")
        cache = os.path.join(scratch, "pycache")
        os.makedirs(tree)
        os.makedirs(cache)
        _export_paths(repo, exec_rev, [E2E_DIR + "/fixtures", "fixtures"], tree)
        env = dict(minimal_env(scratch), PYTHONDONTWRITEBYTECODE="1", PYTHONPYCACHEPREFIX=cache)
        for task_id in sorted(acceptance):
            done = subprocess.run(list(acceptance[task_id]), cwd=tree, env=env, capture_output=True,
                                  stdin=subprocess.DEVNULL, timeout=300)
            lines = [line for line in done.stdout.decode("utf-8", errors="replace").split("\n") if line.strip()]
            result["acceptance"][task_id] = {"exit": done.returncode, "last_line": lines[-1] if lines else "",
                                             "stdout_bytes": len(done.stdout), "stdout_sha256": sha256_hex(done.stdout)}
        done = subprocess.run(["python3", "-m", "py_compile", "fixtures/before.py", "fixtures/after.py"], cwd=tree,
                              env=env, capture_output=True, stdin=subprocess.DEVNULL, timeout=120)
        result["py_compile"] = {"exit": done.returncode, "stdout_bytes": len(done.stdout),
                                "stderr_bytes": len(done.stderr)}
    return result


# --- END OF PART 4 ---
