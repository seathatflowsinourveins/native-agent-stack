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
import subprocess
import tempfile
import tokenize
import unicodedata
from html.parser import HTMLParser

GRAMMAR = "g1"
FAMILY_ARMS = {"claude": ["B", "A", "A0"], "codex": ["B", "A", "N"]}
M8_LANES = ("symbol-references", "qmd", "ai-memory")


# ---- Refusals and results ---------------------------------------------------------------------------------------

class Refusal(Exception):
    """A refusal is `E_CODE field=value ...`: a code and field names, never a private value."""

    def __init__(self, code, **fields):
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
    """Inline code spans of raw text outside fenced blocks: (line index, content)."""
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
            spans.append((index, line[run:found]))
            pos = found + width
    return spans


def normalize(text):
    """Grammar g1: NFKC, dash variants to '-', emphasis and backticks stripped outside fenced blocks, spaces collapsed."""
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
            while scan + 3 < size + 0 and text[scan] == "," and all(is_digit(item) for item in text[scan + 1:scan + 4]) \
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


def ints_by_label(text, label, nouns=()):
    """Integers written next to a label word: 'N label', 'N noun label', 'label: N', 'label noun: N'."""
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
    return found


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
            "judges": _object({
                "claude_answers": _object({"model": _string(), "effort": _string()}),
                "codex_answers": _object({"agent_type": _string(), "model": _string(), "effort": _string()}),
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
            continue
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
    if name in ("T29", "T30", "T31", "T37"):
        return {"fixture_path": task.get("fixture_path")}
    if name == "T38":
        return {"fixture_path": task.get("fixture_path")}
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

    def _git(self, *args, check=False):
        done = subprocess.run(["git", "-C", self.repo, *args], capture_output=True, stdin=subprocess.DEVNULL)
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
        request = "".join(f"{self.rev}:{path}\n" for path in wanted).encode("utf-8")
        done = subprocess.run(["git", "-C", self.repo, "cat-file", "--batch"], input=request, capture_output=True)
        data, result, offset = done.stdout, {}, 0
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
        return result


class DirSources:
    """Tracked files of a directory (a clone or worktree); `git ls-files` names them and the disk supplies the bytes."""

    def __init__(self, root):
        self.root = str(root)

    def read(self, path):
        try:
            with open(os.path.join(self.root, path), "rb") as stream:
                return stream.read()
        except OSError:
            return None

    def files(self, *prefixes):
        done = subprocess.run(["git", "-C", self.root, "ls-files", "-z"], capture_output=True,
                              stdin=subprocess.DEVNULL)
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


# --- END OF PART 1 ---
