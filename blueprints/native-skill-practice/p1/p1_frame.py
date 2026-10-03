#!/usr/bin/env python3
"""P1 frame extractor: real claims that cite a source span, cut by code.

Specification: the Jev and TypeSafe design report r1, section 5.1, "Frame" row:
claims that cite a repository file:line, a pinned upstream file or a retained
receipt field, in evidence/receipts/, evidence/artifacts/*/README.md,
docs/decisions/ and retained review packets at the freeze commit. Code cuts the
cited span with a fixed window as the source excerpt. No model selects or edits
a case.

The enriched pool (section 5.1, "Cases" row) holds real pairs whose claim a
retained review corrected or refuted (verifier, critique or
adversarial_verification records). The review's verdict is provenance only; it
is never a label (the user's blind label decides each class).

Everything here is deterministic for a given frame commit. Blobs are read with
git, never from the working tree. A citation is cut at the revision it cited:
its own pin when it carries one, otherwise the commit that introduced the
citation text to the citing document (git log -S), or for a citation built from
record fields the commit that last changed the citing line (git blame). The
frame's "drift:*" counters record how many cited spans changed between that
revision and the frame commit: the line drift a frame-commit cut would test.
The only network access is an optional GET of a pinned upstream file from
raw.githubusercontent.com (public bytes at a commit id; no case text is sent);
--offline turns it off and those citations are excluded and counted.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import posixpath
import re
import subprocess
import urllib.error
import urllib.request
from collections import Counter
from json.decoder import scanstring
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]

# --------------------------------------------------------------------------- frozen rules

RULES_VERSION = "p1-frame-v1"
WINDOW_LINES = 3            # context lines on each side of the cited span (GNU diff -u default context)
MAX_CITED_SPAN_LINES = 20   # longer cited spans are excluded, not truncated (failure mode 5: large state)
MAX_EXCERPT_CHARS = 3000    # longer windows are excluded, not truncated
MIN_CLAIM_WORDS = 6
MAX_CLAIM_WORDS = 80
SUBJECT_REPLACEMENT = "The source"   # written where a removed citation was the sentence's subject
OWN_REPOSITORY =("seathatflowsinourveins", "native-agent-stack")
OWN_REPOSITORY_NAME = "native-agent-stack"
UPSTREAM_RAW = "https://raw.githubusercontent.com/{owner}/{repo}/{ref}/{path}"

# Retained review packets: tracked JSON or Markdown files under evidence/artifacts/
# whose file name carries one of these words.
REVIEW_PACKET_NAME = re.compile(r"(?i)(review|critique|verif|finding|packet)")
# Files this campaign writes never enter its own frame.
SELF_EXCLUDED_PREFIXES = ("blueprints/native-skill-practice/p1/", "evidence/artifacts/jev-p1-")
# Enriched pool: retained review records may sit anywhere under these roots.
ENRICHED_ROOTS = ("evidence/", "catalogs/", "blueprints/", "docs/")
ENRICHED_VERDICT_FIELDS = ("verifier_verdict", "verdict", "result", "disposition")
ENRICHED_VERDICT_VALUES = (
    "contradicted", "corrected", "does_not_hold", "mixed", "not_supported",
    "partially", "partly", "partly_holds", "refuted", "unsupported",
)
ENRICHED_TEXT_SIGNALS = ("correction", "problem")      # a non-empty correction or refutation text
ENRICHED_SOURCE_FIELDS = (
    "source", "sources", "evidence", "correction", "problem", "reason", "note",
    "verification", "quote", "reasoning",
)

# promptfoo 0.123.1 renders every string var as a nunjucks template and loads a
# var that starts with file:// or package: from disk (dist/src/evaluatorHelpers-*.js,
# renderPrompt); such a case would not reach an arm as frozen.
HARNESS_UNSAFE = re.compile(r"\{\{|\{%|\{#")
HARNESS_UNSAFE_PREFIXES = ("file://", "package:")
CONTROL_CHARACTERS = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")

FRAME_RULES = {
    "version": RULES_VERSION,
    "frame_documents": [
        "evidence/receipts/** (JSON string values)",
        "evidence/artifacts/<dir>/README.md",
        "docs/decisions/** (Markdown)",
        "evidence/artifacts/** .json or .md whose file name matches " + REVIEW_PACKET_NAME.pattern
        + " (retained review packets)",
    ],
    "self_excluded_prefixes": list(SELF_EXCLUDED_PREFIXES),
    "citation_forms": {
        "repository_line": "path:N, path:N-M, path:N,M, path#LN-LM or path:LN, optionally followed by ' at <commit>'",
        "pinned_upstream": "https://github.com/<owner>/<repo>/blob/<7-40 hex>/<path>#LN(-LM)",
        "own_repository_pin": "native-agent-stack@<7-40 hex>:<path>:N(-M)",
        "receipt_field": "<file>.json#/<RFC 6901 pointer>",
        "counted_never_cut": "a bare :N continuation, an anchorless blob URL and <other repo>@<commit>:<path>",
    },
    "revision": "the citation's own pin when it carries one; otherwise the oldest commit, up to the frame "
                "commit, that introduced the citation text to the citing document (git log -S); for a citation "
                "built from record fields, the commit that last changed the citing line (git blame)",
    "path_resolution": [
        "exact tracked path at the excerpt revision",
        "path relative to the citing document's directory",
        "unique tracked suffix match whose full path also appears verbatim in the citing document",
    ],
    "window_lines": WINDOW_LINES,
    "max_cited_span_lines": MAX_CITED_SPAN_LINES,
    "max_excerpt_chars": MAX_EXCERPT_CHARS,
    "excerpt": "cited lines plus the window, clipped to the file, blank lines trimmed at both ends, "
               "carriage returns removed, joined with LF, no trailing newline",
    "claim": "the sentence holding exactly one citation, with that citation removed by code and leading "
             f"punctuation stripped; {MIN_CLAIM_WORDS}-{MAX_CLAIM_WORDS} words; not a question; when the citation "
             "was the sentence's subject (it led the sentence, no ':' or dash after it, and the rest starts "
             f"lowercase), code writes '{SUBJECT_REPLACEMENT}' in its place",
    "one_pair_per_claim": "duplicate claims (case-folded, whitespace-normalized) keep the lowest candidate id",
    "exclusions": [
        "private content (scripts/validate.py PRIVATE_CONTENT patterns) in claim or excerpt",
        "promptfoo template or loader syntax ({{, {%, {#, a leading file:// or package:)",
        "an excerpt that parses as one complete JSON value",
        "control characters other than tab and LF",
    ],
    "enriched_records": {
        "roots": list(ENRICHED_ROOTS),
        "claim_field": "claim (string)",
        "signals": [
            "refuted is true",
            "holds is false",
            "one of " + ", ".join(ENRICHED_VERDICT_FIELDS) + " equals one of " + ", ".join(ENRICHED_VERDICT_VALUES),
            "a non-empty " + " or ".join(ENRICHED_TEXT_SIGNALS) + " string beside the claim",
            "adversarial_verification.votes[] with refuted true: the candidate's demonstrated_gap and evidence[] sentences",
        ],
        "source_order": ["explicit file and line fields", "the one citation inside the claim"]
                        + [f"first resolvable citation in {name}" for name in ENRICHED_SOURCE_FIELDS],
    },
}

# --------------------------------------------------------------------------- citation forms

_PATH = r"(?:[A-Za-z0-9_.@+-]+/)*[A-Za-z0-9_@+-][A-Za-z0-9_.@+-]*\.(?=[A-Za-z0-9]*[A-Za-z])[A-Za-z0-9]{1,10}"
_JSON_PATH = r"(?:[A-Za-z0-9_.@+-]+/)*[A-Za-z0-9_@+-][A-Za-z0-9_.@+-]*\.json"
_LINES = r"L?\d+(?:\s*[-–]\s*L?\d+)?(?:\s*,\s*L?\d+(?:\s*[-–]\s*L?\d+)?)*"
_BOUNDARY = r"(?<![A-Za-z0-9_/.@+:~-])"

REPO_LINE = re.compile(
    _BOUNDARY + r"(?P<path>" + _PATH + r")(?::|#)(?P<lines>" + _LINES + r")"
    r"(?:\s+at\s+(?P<pin>[0-9a-f]{7,40})\b)?")
BLOB_URL = re.compile(
    r"https://github\.com/(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+)/blob/"
    r"(?P<ref>[0-9a-f]{7,40})/(?P<path>[^\s#?)\]'\"`<>]+)(?:#L(?P<a>\d+)(?:-L(?P<b>\d+))?)?")
REPO_AT_PIN = re.compile(
    _BOUNDARY + r"(?P<repo>[A-Za-z0-9_.-]+)@(?P<ref>[0-9a-f]{7,40}):(?P<path>" + _PATH + r")"
    r"(?::(?P<lines>" + _LINES + r"))?")
JSON_POINTER = re.compile(
    _BOUNDARY + r"(?P<path>" + _JSON_PATH + r")#(?P<ptr>/[^\s`'\")\]<>,;]*)")
CONTINUATION = re.compile(r"(?:(?<=[\s(`,;\[])|^):L?\d+(?:\s*[-–]\s*L?\d+)?(?![\d:])")


def _parse_lines(spec: str) -> list[tuple[int, int]] | None:
    ranges = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        bounds = [int(token.strip().lstrip("L")) for token in re.split(r"[-–]", part)]
        start, end = bounds[0], bounds[-1]
        if start < 1 or end < start:
            return None
        ranges.append((start, end))
    return ranges or None


def find_citations(text: str) -> list[dict]:
    """Every syntactic citation in text, in order, without overlaps."""
    found: list[dict] = []
    for match in BLOB_URL.finditer(text):
        lines = None
        if match.group("a"):
            start = int(match.group("a"))
            end = int(match.group("b") or start)
            lines = [(start, end)] if 1 <= start <= end else None
        found.append({"kind": "pinned_upstream", "start": match.start(), "end": match.end(),
                      "text": match.group(0), "owner": match.group("owner"), "repo": match.group("repo"),
                      "ref": match.group("ref"), "path": match.group("path"), "lines": lines,
                      "anchored": match.group("a") is not None})
    for match in REPO_AT_PIN.finditer(text):
        lines = _parse_lines(match.group("lines")) if match.group("lines") else None
        found.append({"kind": "own_repository_pin" if match.group("repo") == OWN_REPOSITORY_NAME else "repository_pin",
                      "start": match.start(), "end": match.end(), "text": match.group(0),
                      "repo": match.group("repo"), "ref": match.group("ref"), "path": match.group("path"),
                      "lines": lines, "anchored": lines is not None})
    for match in JSON_POINTER.finditer(text):
        pointer = match.group("ptr").rstrip(".:")
        end = match.start() + len(match.group("path")) + 1 + len(pointer)
        found.append({"kind": "receipt_field", "start": match.start(), "end": end,
                      "text": text[match.start():end], "path": match.group("path"), "pointer": pointer,
                      "anchored": True})
    for match in REPO_LINE.finditer(text):
        found.append({"kind": "repository_line", "start": match.start(), "end": match.end(),
                      "text": match.group(0), "path": match.group("path"),
                      "lines": _parse_lines(match.group("lines")), "pin": match.group("pin"), "anchored": True})
    for match in CONTINUATION.finditer(text):
        found.append({"kind": "continuation", "start": match.start(), "end": match.end(),
                      "text": match.group(0), "anchored": False})
    found.sort(key=lambda item: (item["start"], -item["end"]))
    kept: list[dict] = []
    for item in found:
        if kept and item["start"] < kept[-1]["end"]:
            continue
        kept.append(item)
    return kept


# --------------------------------------------------------------------------- git snapshot


def _git_environment() -> dict:
    # Inherited Git routing variables must not select another checkout (scripts/validate.py does the same).
    return {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}


class GitSnapshot:
    """Read-only view of a repository at a frame commit, with history lookups."""

    def __init__(self, repo: Path, commit: str):
        self.repo = repo
        self.env = _git_environment()
        self._commits: dict[str, str | None] = {}
        self._blobs: dict[tuple[str, str], bytes | None] = {}
        self._trees: dict[str, tuple[set, dict]] = {}
        self._blame: dict[str, dict[int, str]] = {}
        self._pickaxe: dict[tuple[str, str], str | None] = {}
        resolved = self.resolve_commit(commit)
        if resolved is None:
            raise SystemExit(f"unknown commit {commit!r}")
        self.commit = resolved
        self.file_set, self.by_basename = self.tree(self.commit)
        self.files = sorted(self.file_set)

    def _run(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", "--no-optional-locks", "-C", str(self.repo), *args],
                              env=self.env, capture_output=True)

    def resolve_commit(self, rev: str) -> str | None:
        if rev not in self._commits:
            result = self._run("rev-parse", "--verify", "--quiet", rev + "^{commit}")
            self._commits[rev] = result.stdout.decode().strip() if result.returncode == 0 else None
        return self._commits[rev]

    def tree(self, commit: str) -> tuple[set, dict]:
        if commit not in self._trees:
            result = self._run("ls-tree", "-r", "-z", "--name-only", commit)
            names = sorted(item for item in result.stdout.decode("utf-8").split("\0") if item) \
                if result.returncode == 0 else []
            by_basename: dict[str, list[str]] = {}
            for name in names:
                by_basename.setdefault(posixpath.basename(name), []).append(name)
            self._trees[commit] = (set(names), by_basename)
        return self._trees[commit]

    def read(self, path: str, commit: str | None = None) -> bytes | None:
        commit = commit or self.commit
        key = (commit, path)
        if key not in self._blobs:
            result = self._run("cat-file", "blob", f"{commit}:{path}")
            self._blobs[key] = result.stdout if result.returncode == 0 else None
        return self._blobs[key]

    def read_text(self, path: str, commit: str | None = None) -> str | None:
        raw = self.read(path, commit)
        if raw is None:
            return None
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return None

    def first_commit_with(self, path: str, needle: str) -> str | None:
        """The oldest commit, up to the frame commit, that changed how often needle occurs in path
        (git log -S, oldest first): the commit that introduced the citation to that document."""
        key = (path, needle)
        if key not in self._pickaxe:
            result = self._run("log", "--reverse", "--format=%H", "-S" + needle, self.commit, "--", path)
            commits = result.stdout.decode().split() if result.returncode == 0 else []
            self._pickaxe[key] = commits[0] if commits else None
        return self._pickaxe[key]

    def blame_commit(self, path: str, line: int) -> str | None:
        """The commit that last changed line (1-based) of path, as of the frame commit."""
        if path not in self._blame:
            result = self._run("blame", "--porcelain", self.commit, "--", path)
            mapping: dict[int, str] = {}
            if result.returncode == 0:
                for row in result.stdout.decode("utf-8", "replace").split("\n"):
                    parts = row.split(" ")
                    if len(parts) >= 3 and re.fullmatch(r"[0-9a-f]{40}", parts[0]) and parts[2].isdigit():
                        mapping[int(parts[2])] = parts[0]
            self._blame[path] = mapping
        return self._blame[path].get(line)


class UpstreamFetcher:
    """GET a pinned upstream file once; cache by URL. Offline mode reads only the cache."""

    def __init__(self, cache_dir: Path | None, offline: bool):
        self.cache_dir = cache_dir
        self.offline = offline
        self.records: dict[str, dict] = {}

    def fetch(self, owner: str, repo: str, ref: str, path: str) -> bytes | None:
        url = UPSTREAM_RAW.format(owner=owner, repo=repo, ref=ref, path=path)
        cache_file = None
        if self.cache_dir is not None:
            cache_file = self.cache_dir / hashlib.sha256(url.encode()).hexdigest()
            if cache_file.is_file():
                raw = cache_file.read_bytes()
                self._record(url, raw, "cache")
                return raw
            if cache_file.with_suffix(".missing").is_file():
                self._record(url, None, "cached_missing")
                return None
        if self.offline:
            self._record(url, None, "offline")
            return None
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                raw = response.read()
        except (urllib.error.URLError, TimeoutError, OSError):
            if cache_file is not None:
                cache_file.parent.mkdir(parents=True, exist_ok=True)
                cache_file.with_suffix(".missing").write_text(url + "\n", encoding="utf-8")
            self._record(url, None, "unavailable")
            return None
        if cache_file is not None:
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_bytes(raw)
        self._record(url, raw, "fetched")
        return raw

    def _record(self, url: str, raw: bytes | None, how: str) -> None:
        self.records[url] = {"url": url, "status": "available" if raw is not None else how,
                             "sha256": hashlib.sha256(raw).hexdigest() if raw is not None else None,
                             "bytes": len(raw) if raw is not None else None}


# --------------------------------------------------------------------------- excerpts


def cut_window(text: str, ranges: list[tuple[int, int]]) -> tuple[str | None, tuple[int, int] | None, str | None]:
    lines = text.split("\n")
    if text.endswith("\n"):
        lines = lines[:-1]
    count = len(lines)
    low = min(start for start, _ in ranges)
    high = max(end for _, end in ranges)
    if low < 1 or high > count:
        return None, None, "line_out_of_range"
    if high - low + 1 > MAX_CITED_SPAN_LINES:
        return None, None, "cited_span_too_long"
    first = max(1, low - WINDOW_LINES)
    last = min(count, high + WINDOW_LINES)
    window = [line.replace("\r", "") for line in lines[first - 1:last]]
    while window and not window[0].strip():
        window.pop(0)
        first += 1
    while window and not window[-1].strip():
        window.pop()
        last -= 1
    if not window:
        return None, None, "blank_window"
    excerpt = "\n".join(window)
    if len(excerpt) > MAX_EXCERPT_CHARS:
        return None, None, "excerpt_too_long"
    return excerpt, (first, last), None


_WHITESPACE = re.compile(r"[ \t\n\r]*")


def locate_pointer(text: str, pointer: str) -> tuple[int, int] | None:
    """Character offsets [start, end) of the value an RFC 6901 pointer names, or None."""
    decoder = json.JSONDecoder()
    tokens = [token.replace("~1", "/").replace("~0", "~") for token in pointer.split("/")[1:]] \
        if pointer not in ("", "/") else []
    try:
        index = _WHITESPACE.match(text, 0).end()
        for token in tokens:
            if text[index] == "{":
                index = _WHITESPACE.match(text, index + 1).end()
                if text[index] == "}":
                    return None
                while True:
                    if text[index] != '"':
                        return None
                    key, index = scanstring(text, index + 1)
                    index = _WHITESPACE.match(text, index).end()
                    if text[index] != ":":
                        return None
                    index = _WHITESPACE.match(text, index + 1).end()
                    if key == token:
                        break
                    _, index = decoder.raw_decode(text, index)
                    index = _WHITESPACE.match(text, index).end()
                    if text[index] != ",":
                        return None
                    index = _WHITESPACE.match(text, index + 1).end()
            elif text[index] == "[":
                if not token.isdigit() or (len(token) > 1 and token.startswith("0")):
                    return None
                index = _WHITESPACE.match(text, index + 1).end()
                if text[index] == "]":
                    return None
                for _ in range(int(token)):
                    _, index = decoder.raw_decode(text, index)
                    index = _WHITESPACE.match(text, index).end()
                    if text[index] != ",":
                        return None
                    index = _WHITESPACE.match(text, index + 1).end()
            else:
                return None
        _, end = decoder.raw_decode(text, index)
        return index, end
    except (IndexError, ValueError):
        return None


def line_of_offset(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _load_private_patterns():
    spec = importlib.util.spec_from_file_location("p1_validate_patterns", REPO_ROOT / "scripts" / "validate.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.PRIVATE_CONTENT


PRIVATE_CONTENT = _load_private_patterns()


def screen_text(text: str) -> str | None:
    """The first exclusion reason for a claim or excerpt, or None."""
    for _description, pattern in PRIVATE_CONTENT:
        if pattern.search(text):
            return "private_content_pattern"
    if HARNESS_UNSAFE.search(text) or text.lstrip().startswith(HARNESS_UNSAFE_PREFIXES):
        return "harness_template_syntax"
    if CONTROL_CHARACTERS.search(text):
        return "control_character"
    return None


def parses_as_json(text: str) -> bool:
    try:
        json.loads(text)
    except ValueError:
        return False
    return True


# --------------------------------------------------------------------------- claim blocks and sentences

_FENCE = re.compile(r"^\s*(```|~~~)")
_TABLE_SEPARATOR = re.compile(r"^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?$")
_LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(.*)$")


def _split_table_row(row: str) -> list[str]:
    cells, current, in_code = [], [], False
    body = row.strip()
    if body.startswith("|"):
        body = body[1:]
    if body.endswith("|") and not body.endswith("\\|"):
        body = body[:-1]
    index = 0
    while index < len(body):
        char = body[index]
        if char == "`":
            in_code = not in_code
        if char == "\\" and index + 1 < len(body) and body[index + 1] == "|":
            current.append("|")
            index += 2
            continue
        if char == "|" and not in_code:
            cells.append("".join(current).strip())
            current = []
        else:
            current.append(char)
        index += 1
    cells.append("".join(current).strip())
    return cells


def markdown_blocks(text: str) -> list[tuple[int, str]]:
    """(first line, text) blocks: paragraphs, list items and table cells; fences and headings skipped."""
    blocks: list[tuple[int, str]] = []
    current: list[str] = []
    start = 0
    in_fence = False

    def flush():
        nonlocal current
        if current:
            blocks.append((start, " ".join(part.strip() for part in current if part.strip())))
        current = []

    for number, line in enumerate(text.split("\n"), start=1):
        stripped = line.strip()
        if _FENCE.match(line):
            flush()
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if not stripped:
            flush()
            continue
        if stripped.startswith("#"):
            flush()
            continue
        if stripped.startswith("|"):
            flush()
            if _TABLE_SEPARATOR.match(stripped):
                continue
            for cell in _split_table_row(stripped):
                if cell:
                    blocks.append((number, cell))
            continue
        if stripped.startswith(">"):
            stripped = stripped.lstrip(">").strip()
        item = _LIST_ITEM.match(line)
        if item:
            flush()
            current = [item.group(1)]
            start = number
            continue
        if not current:
            start = number
        current.append(stripped)
    flush()
    return [(first, block) for first, block in blocks if block]


def json_blocks(value, pointer: str = "") -> list[tuple[str, str]]:
    """(RFC 6901 pointer, string) for every string leaf, in document order."""
    blocks: list[tuple[str, str]] = []
    if isinstance(value, str):
        blocks.append((pointer or "/", value))
    elif isinstance(value, dict):
        for key, item in value.items():
            token = str(key).replace("~", "~0").replace("/", "~1")
            blocks.extend(json_blocks(item, f"{pointer}/{token}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            blocks.extend(json_blocks(item, f"{pointer}/{index}"))
    return blocks


_MASK = re.compile(r"`[^`\n]*`|https?://[^\s)\]>\"'`]+")
_BOUNDARY_SENTENCE = re.compile(r"[.!?][\"')\]*_]*\s+(?=[A-Z0-9`\"'(\[*_])")
_ABBREVIATIONS = ("e.g.", "i.e.", "etc.", "vs.", "cf.", "approx.", "No.", "Fig.", "al.", "Inc.", "Ltd.", "U.S.", "St.")


def split_sentences(block: str) -> list[tuple[int, str]]:
    """(offset, sentence) pairs; code spans and URLs never split a sentence."""
    masked = _MASK.sub(lambda match: "x" * len(match.group(0)), block)
    cuts = [0]
    for match in _BOUNDARY_SENTENCE.finditer(masked):
        if masked[:match.start() + 1].endswith(_ABBREVIATIONS):
            continue
        cuts.append(match.end())
    cuts.append(len(block))
    sentences = []
    for begin, finish in zip(cuts, cuts[1:]):
        piece = block[begin:finish]
        stripped = piece.strip()
        if stripped:
            sentences.append((begin + (len(piece) - len(piece.lstrip())), stripped))
    return sentences


_EMPTY_WRAPPERS = (
    (re.compile(r"`\s*`"), ""),
    (re.compile(r"\(\s*[,;:]?\s*\)"), ""),
    (re.compile(r"\[\s*\]"), ""),
    (re.compile(r"\s+([,.;:!?)])"), r"\1"),
    (re.compile(r"\(\s+"), "("),
    (re.compile(r"\s{2,}"), " "),
)
_LEADING_PUNCTUATION = " \t:;,.-–—•"


def strip_citation(sentence: str, start: int, end: int) -> str:
    text = sentence[:start] + sentence[end:]
    for _ in range(6):
        previous = text
        for pattern, replacement in _EMPTY_WRAPPERS:
            text = pattern.sub(replacement, text)
        if text == previous:
            break
    return text.strip().lstrip(_LEADING_PUNCTUATION).strip()


def citation_leads(sentence: str, start: int, end: int) -> bool:
    """True when the citation was the sentence's subject: nothing but wrappers precede it and no
    label separator (":", a dash) follows it, as in "`a.md:3` rejects X" but not "`a.md:3`: X"."""
    if sentence[:start].strip(" \t`'\"([*_" + _LEADING_PUNCTUATION):
        return False
    rest = sentence[end:].lstrip(" \t`'\")]*_")
    return not rest.startswith((":", "—", "–", "-"))


def claim_from(sentence: str, start: int, end: int) -> str:
    """Remove the citation; when it was the subject, name it "The source" so the claim stays a sentence."""
    claim = strip_citation(sentence, start, end)
    if claim and citation_leads(sentence, start, end) and claim[0].islower():
        claim = f"{SUBJECT_REPLACEMENT} {claim}"
    return claim


def claim_problem(claim: str) -> str | None:
    words = len(claim.split())
    if words < MIN_CLAIM_WORDS:
        return "claim_too_short"
    if words > MAX_CLAIM_WORDS:
        return "claim_too_long"
    if claim.rstrip("*_`\"') ").endswith("?"):
        return "claim_is_question"
    return screen_text(claim)


def citing_line_in_markdown(text: str, first_line: int, citation_text: str) -> int:
    lines = text.split("\n")
    for index in range(first_line - 1, min(len(lines), first_line + 199)):
        if citation_text in lines[index]:
            return index + 1
    return first_line


def citing_line_in_json(text: str, pointer: str) -> int | None:
    located = locate_pointer(text, pointer)
    return line_of_offset(text, located[0]) if located else None


# --------------------------------------------------------------------------- extraction


class Extractor:
    def __init__(self, snapshot: GitSnapshot, fetcher: UpstreamFetcher):
        self.snapshot = snapshot
        self.fetcher = fetcher

    def resolve_repo_path(self, cited: str, citing_path: str, citing_text: str, revision: str) -> str | None:
        files, by_basename = self.snapshot.tree(revision)
        cited = cited[2:] if cited.startswith("./") else cited
        if cited in files:
            return cited
        relative = posixpath.normpath(posixpath.join(posixpath.dirname(citing_path), cited))
        if not relative.startswith("..") and relative in files:
            return relative
        matches = [name for name in by_basename.get(posixpath.basename(cited), []) if name.endswith("/" + cited)]
        if len(matches) == 1 and matches[0] in citing_text:
            return matches[0]
        return None

    def cited_revision(self, citation: dict, citing_path: str, citing_text: str,
                       citing_line: int | None) -> tuple[str | None, str]:
        pin = citation.get("pin") or (citation.get("ref") if citation["kind"] in ("own_repository_pin", "pinned_upstream") else None)
        if pin:
            return self.snapshot.resolve_commit(pin), "pinned"
        if citation["text"] in citing_text:
            introduced = self.snapshot.first_commit_with(citing_path, citation["text"])
            if introduced:
                return introduced, "first_cited"
        if citing_line is None:
            return None, "blamed"
        return self.snapshot.blame_commit(citing_path, citing_line), "blamed"

    def source_for(self, citation: dict, citing_path: str, citing_text: str,
                   citing_line: int | None) -> tuple[dict | None, str | None]:
        """Cut the excerpt one citation names: (source record, None) or (None, exclusion reason)."""
        kind = citation["kind"]
        if kind in ("continuation", "repository_pin"):
            return None, f"{kind}_not_resolvable"
        if not citation.get("anchored") or (kind != "receipt_field" and not citation.get("lines")):
            return None, "no_line_anchor"
        if kind == "pinned_upstream" and (citation["owner"], citation["repo"]) != OWN_REPOSITORY:
            raw = self.fetcher.fetch(citation["owner"], citation["repo"], citation["ref"], citation["path"])
            if raw is None:
                return None, "upstream_unavailable"
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                return None, "upstream_binary"
            origin = {"repository": f"{citation['owner']}/{citation['repo']}", "path": citation["path"],
                      "revision": citation["ref"], "revision_rule": "pinned",
                      "url": UPSTREAM_RAW.format(owner=citation["owner"], repo=citation["repo"],
                                                 ref=citation["ref"], path=citation["path"]),
                      "file_sha256": hashlib.sha256(raw).hexdigest()}
            ranges = citation["lines"]
        else:
            revision, rule = self.cited_revision(citation, citing_path, citing_text, citing_line)
            if revision is None:
                return None, "pin_not_in_local_history" if rule == "pinned" else "no_blame"
            if kind in ("own_repository_pin", "pinned_upstream"):
                path = citation["path"] if citation["path"] in self.snapshot.tree(revision)[0] else None
            else:
                path = self.resolve_repo_path(citation["path"], citing_path, citing_text, revision)
            if path is None:
                return None, "unresolved_repository_path"
            text = self.snapshot.read_text(path, revision)
            if text is None:
                return None, "file_absent_or_binary_at_revision"
            origin = {"repository": OWN_REPOSITORY_NAME, "path": path, "revision": revision, "revision_rule": rule}
            if kind == "receipt_field":
                located = locate_pointer(text, citation["pointer"])
                if located is None:
                    return None, "pointer_not_found"
                start, end = located
                ranges = [(line_of_offset(text, start), line_of_offset(text, max(start, end - 1)))]
                origin["pointer"] = citation["pointer"]
            else:
                ranges = citation["lines"]
        excerpt, span, problem = cut_window(text, ranges)
        if problem:
            return None, problem
        problem = screen_text(excerpt)
        if problem:
            return None, problem
        if parses_as_json(excerpt):
            return None, "excerpt_is_complete_json"
        return {"origin": origin, "cited_lines": [list(item) for item in ranges], "excerpt_lines": list(span),
                "excerpt": excerpt, "drift": self.drift(origin, ranges, text)}, None

    def drift(self, origin: dict, ranges: list[tuple[int, int]], text: str) -> str:
        """Whether the cited lines differ at the frame commit (diagnostic only; never a filter)."""
        if origin.get("repository") != OWN_REPOSITORY_NAME or origin["revision"] == self.snapshot.commit:
            return "not_applicable"
        current = self.snapshot.read_text(origin["path"])
        if current is None:
            return "absent_at_frame_commit"
        if "pointer" in origin:
            then, now = locate_pointer(text, origin["pointer"]), locate_pointer(current, origin["pointer"])
            if then is None or now is None:
                return "changed"
            return "unchanged" if text[then[0]:then[1]] == current[now[0]:now[1]] else "changed"
        low = min(start for start, _ in ranges)
        high = max(end for _, end in ranges)
        return "unchanged" if text.split("\n")[low - 1:high] == current.split("\n")[low - 1:high] else "changed"

    def _candidate(self, base: dict, claim: str, path: str, locator: str, offset: int, citing_line: int | None,
                   citation: dict, source: dict) -> dict:
        record = dict(base)
        record.update({
            "claim": claim,
            "citing": {"path": path, "locator": locator, "sentence_offset": offset, "line": citing_line},
            "citation": {"kind": citation["kind"], "text": citation["text"]},
            **source,
        })
        return record

    def candidates_from_block(self, path: str, locator: str, block: str, document_text: str,
                              line_for, base: dict, stats: Counter) -> list[dict]:
        found = []
        for offset, sentence in split_sentences(block):
            citations = find_citations(sentence)
            if not citations:
                continue
            stats["sentences_with_citation"] += 1
            if len(citations) > 1:
                stats["excluded:multiple_citations"] += 1
                continue
            citation = citations[0]
            claim = claim_from(sentence, citation["start"], citation["end"])
            problem = claim_problem(claim)
            if problem:
                stats[f"excluded:{problem}"] += 1
                continue
            citing_line = line_for(citation)
            source, problem = self.source_for(citation, path, document_text, citing_line)
            if problem:
                stats[f"excluded:{problem}"] += 1
                continue
            stats[f"revision:{source['origin']['revision_rule']}"] += 1
            stats[f"drift:{source['drift']}"] += 1
            found.append(self._candidate(base, claim, path, locator, offset, citing_line, citation, source))
        return found

    # ----------------------------------------------------------------- natural frame

    def frame_documents(self) -> list[tuple[str, str]]:
        documents = []
        for name in self.snapshot.files:
            if name.startswith(SELF_EXCLUDED_PREFIXES):
                continue
            if name.startswith("evidence/receipts/"):
                documents.append(("receipt", name))
            elif re.fullmatch(r"evidence/artifacts/[^/]+/README\.md", name):
                documents.append(("artifact_readme", name))
            elif name.startswith("docs/decisions/"):
                documents.append(("decision", name))
            elif (name.startswith("evidence/artifacts/") and name.endswith((".json", ".md"))
                  and REVIEW_PACKET_NAME.search(posixpath.basename(name))):
                documents.append(("review_packet", name))
        return documents

    def natural_frame(self) -> tuple[list[dict], Counter, Counter]:
        stats: Counter = Counter()
        documents: Counter = Counter()
        candidates: list[dict] = []
        for kind, path in self.frame_documents():
            documents[kind] += 1
            text = self.snapshot.read_text(path)
            if text is None:
                stats["excluded_document:unreadable"] += 1
                continue
            base = {"document_kind": kind}
            if path.endswith(".md"):
                for first, block in markdown_blocks(text):
                    candidates.extend(self.candidates_from_block(
                        path, f"L{first}", block, text,
                        lambda citation, first=first: citing_line_in_markdown(text, first, citation["text"]),
                        base, stats))
            elif path.endswith(".json"):
                try:
                    blocks = json_blocks(json.loads(text))
                except ValueError:
                    stats["excluded_document:unparseable"] += 1
                    continue
                for pointer, block in blocks:
                    candidates.extend(self.candidates_from_block(
                        path, pointer, block, text,
                        lambda citation, pointer=pointer: citing_line_in_json(text, pointer), base, stats))
        return finalize(candidates, "f", stats), stats, documents

    # ----------------------------------------------------------------- enriched pool

    def enriched_documents(self) -> list[str]:
        return [name for name in self.snapshot.files
                if name.endswith(".json") and name.startswith(ENRICHED_ROOTS)
                and not name.startswith(SELF_EXCLUDED_PREFIXES)]

    @staticmethod
    def review_signal(node: dict) -> str | None:
        if node.get("refuted") is True:
            return "refuted=true"
        if node.get("holds") is False:
            return "holds=false"
        for field in ENRICHED_VERDICT_FIELDS:
            value = node.get(field)
            if isinstance(value, str) and value.strip().lower() in ENRICHED_VERDICT_VALUES:
                return f"{field}={value.strip().lower()}"
        for field in ENRICHED_TEXT_SIGNALS:
            value = node.get(field)
            if isinstance(value, str) and value.strip():
                return f"{field}_text"
        return None

    def enriched_pool(self) -> tuple[list[dict], Counter]:
        stats: Counter = Counter()
        candidates: list[dict] = []
        for path in self.enriched_documents():
            text = self.snapshot.read_text(path)
            if text is None or ('"claim"' not in text and '"adversarial_verification"' not in text):
                continue
            try:
                data = json.loads(text)
            except ValueError:
                continue
            for pointer, node in _walk_objects(data):
                if isinstance(node.get("claim"), str) and node["claim"].strip():
                    signal = self.review_signal(node)
                    if signal:
                        stats[f"records:{signal}"] += 1
                        candidates.extend(self._claim_record(path, pointer, node, signal, text, stats))
                verification = node.get("adversarial_verification")
                votes = verification.get("votes") if isinstance(verification, dict) else None
                if isinstance(votes, list) and any(isinstance(vote, dict) and vote.get("refuted") is True
                                                   for vote in votes):
                    stats["records:adversarial_verification"] += 1
                    candidates.extend(self._refuted_candidate(path, pointer, node, text, stats))
        return finalize(candidates, "e", stats), stats

    def _claim_record(self, path: str, pointer: str, node: dict, signal: str, document_text: str,
                      stats: Counter) -> list[dict]:
        claim_text = " ".join(node["claim"].split())
        review = {"family": "claim_record", "signal": signal, "record": f"{path}#{pointer or '/'}"}
        base = {"document_kind": "review_record"}
        attempts: list[tuple[str, dict]] = []
        claim = claim_text
        line_value = node.get("line")
        if isinstance(node.get("file"), str) and isinstance(line_value, (int, str)) and not isinstance(line_value, bool):
            spec = str(line_value).strip()
            match = re.fullmatch(r"(?P<lines>" + _LINES + r")(?:\s+at\s+(?P<pin>[0-9a-f]{7,40}))?", spec)
            if match:
                attempts.append(("file", {"kind": "repository_line", "text": f"{node['file']}:{spec}",
                                          "path": node["file"], "lines": _parse_lines(match.group("lines")),
                                          "pin": match.group("pin"), "anchored": True}))
        if not attempts:
            inside = find_citations(claim_text)
            if len(inside) > 1:
                stats["excluded:multiple_citations"] += 1
                return []
            if len(inside) == 1:
                claim = claim_from(claim_text, inside[0]["start"], inside[0]["end"])
                attempts.append(("claim", inside[0]))
        problem = claim_problem(claim)
        if problem:
            stats[f"excluded:{problem}"] += 1
            return []
        if not attempts:
            for field in ENRICHED_SOURCE_FIELDS:
                value = node.get(field)
                items = [(f"{field}/{index}", item) for index, item in enumerate(value)] \
                    if isinstance(value, list) else [(field, value)]
                for where, item in items:
                    if isinstance(item, str):
                        attempts.extend((where, citation) for citation in find_citations(item))
        reasons = []
        for where, citation in attempts:
            citing_line = citing_line_in_json(document_text, f"{pointer}/{where}")
            source, problem = self.source_for(citation, path, document_text, citing_line)
            if problem:
                reasons.append(problem)
                continue
            stats[f"revision:{source['origin']['revision_rule']}"] += 1
            stats[f"drift:{source['drift']}"] += 1
            record = self._candidate(base, claim, path, pointer or "/", 0, citing_line, citation, source)
            record["review"] = dict(review, source_field=where)
            return [record]
        stats["excluded:" + (reasons[0] if reasons else "no_citation")] += 1
        return []

    def _refuted_candidate(self, path: str, pointer: str, node: dict, document_text: str,
                           stats: Counter) -> list[dict]:
        found = []
        texts = []
        if isinstance(node.get("demonstrated_gap"), str):
            texts.append(("demonstrated_gap", node["demonstrated_gap"]))
        evidence = node.get("evidence")
        if isinstance(evidence, str):
            texts.append(("evidence", evidence))
        elif isinstance(evidence, list):
            texts.extend((f"evidence/{index}", item) for index, item in enumerate(evidence) if isinstance(item, str))
        review = {"family": "adversarial_verification", "signal": "votes.refuted=true",
                  "record": f"{path}#{pointer or '/'}/adversarial_verification"}
        for field, block in texts:
            locator = f"{pointer}/{field}"
            line = citing_line_in_json(document_text, locator)
            for record in self.candidates_from_block(path, locator, block, document_text, lambda _citation: line,
                                                     {"document_kind": "review_record"}, stats):
                record["review"] = dict(review, source_field=field)
                found.append(record)
        return found


def _walk_objects(value, pointer: str = ""):
    if isinstance(value, dict):
        yield pointer, value
        for key, item in value.items():
            token = str(key).replace("~", "~0").replace("/", "~1")
            yield from _walk_objects(item, f"{pointer}/{token}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _walk_objects(item, f"{pointer}/{index}")


def normalized_claim(claim: str) -> str:
    return " ".join(claim.casefold().split())


def finalize(candidates: list[dict], prefix: str, stats: Counter) -> list[dict]:
    """Assign stable ids, hash texts, keep one pair per claim (lowest id)."""
    for record in candidates:
        identity = json.dumps([record["citing"]["path"], record["citing"]["locator"],
                               record["citing"]["sentence_offset"], record["citation"]["text"], record["claim"]],
                              ensure_ascii=False)
        record["id"] = f"{prefix}-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]
        record["claim_sha256"] = hashlib.sha256(record["claim"].encode("utf-8")).hexdigest()
        record["excerpt_sha256"] = hashlib.sha256(record["excerpt"].encode("utf-8")).hexdigest()
    candidates.sort(key=lambda record: record["id"])
    seen: set[str] = set()
    unique = []
    for record in candidates:
        key = normalized_claim(record["claim"])
        if key in seen:
            stats["excluded:duplicate_claim"] += 1
            continue
        seen.add(key)
        unique.append(record)
    return unique


def build_frame(repo: Path, commit: str, cache_dir: Path | None, offline: bool) -> dict:
    snapshot = GitSnapshot(repo, commit)
    fetcher = UpstreamFetcher(cache_dir, offline)
    extractor = Extractor(snapshot, fetcher)
    natural, natural_stats, documents = extractor.natural_frame()
    enriched, enriched_stats = extractor.enriched_pool()
    return {
        "schema": "jev-p1-frame/1",
        "rules": FRAME_RULES,
        "frame_commit": snapshot.commit,
        "generator": "blueprints/native-skill-practice/p1/p1_frame.py",
        "offline": offline,
        "counts": {
            "frame_documents": dict(sorted(documents.items())),
            "natural_frame": len(natural),
            "enriched_pool": len(enriched),
        },
        "natural_stats": dict(sorted(natural_stats.items())),
        "enriched_stats": dict(sorted(enriched_stats.items())),
        "upstream_files": sorted(fetcher.records.values(), key=lambda item: item["url"]),
        "natural_frame": natural,
        "enriched_pool": enriched,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", type=Path, default=REPO_ROOT)
    parser.add_argument("--commit", required=True, help="frame commit (the freeze commit for the real draw)")
    parser.add_argument("--cache-dir", type=Path, help="pinned upstream file cache, outside the repository")
    parser.add_argument("--offline", action="store_true", help="never fetch; uncached upstream citations are excluded")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    frame = build_frame(args.repo.resolve(), args.commit, args.cache_dir, args.offline)
    args.out.write_text(json.dumps(frame, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"frame_commit": frame["frame_commit"], **frame["counts"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
