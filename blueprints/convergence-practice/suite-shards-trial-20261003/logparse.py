#!/usr/bin/env python3
"""Verbose unittest log parser of the suite-shards trial (2026-10-03): trial 1's parser, copied unchanged.

Provenance. Everything below the import block is copied, unchanged, from the stdlib-only oracle of the first
suite-parallelism trial:

  blueprints/convergence-practice/macos-suite-parallelism-20261003/compare.py at commit
  1e4bb5ab7c79faa83e4cd8d04cf8dc6d33c7b0de (branch foundation/macos-suite-parallelism-trial-20261003, the head
  of draft pull request 646, never merged; file sha256
  415d648bf76c0519571c993191f0c70eaa59c392e54908a5684d54607264a3ad, the hash its experiment.json froze):
  lines 41-74 (the record grammar: separators, status words, summary and description patterns) and lines
  137-792 (status tokens, the parsed-log model, the serial and parallel parsers, parse_log, the
  self-consistency checks and _cap). The two blocks follow the import block below, separated by two blank
  lines; the sha256 of each block's text with its newlines:

    block 1 (lines 41-74):   0e2216cc9578b88f708380536d9337b6efaac216303fa5e76f2418a088537b72
    block 2 (lines 137-792): f22056d4ee4d17893c2d2920c7fe159b3a93c732a1f5aef909ab2f5804021ef4

Not copied: that file's docstring, imports, run-directory pattern, arm table, B1 id mapping, inputs, runs
and verdict code (this trial's compare.py has its own). A shard runs `python3 -m unittest -v <modules>`,
whose log has the same grammar as the serial whole-suite run (CPython Lib/unittest/main.py loads the named
modules with loadTestsFromNames and runs them through the same TextTestRunner), so the serial parser
applies to every log of this trial unchanged; the parallel parser is kept only so that the copy stays
whole, and compare.py makes any log it would select (one with a unittest-parallel header) ineligible.

The citations inside the copied code use the first trial's abbreviations:

  CPY = CPython Lib/unittest/ at tags v3.13.16 (annotated tag object 3b55c23ff4a6aa32f77be661802a3978d7324f88,
        commit cbc944f4bc59639a444dd971c737788ba2283a91) and v3.12.3 (f6650f9ad73359051f3e558c2431a109bc016664);
        runner.py, result.py and suite.py are byte-identical at the two tags, so one line number serves both;
        case.py and main.py differ, and their lines are cited per tag.
  UP  = craigahobbs/unittest-parallel at bda5d77dc1a2fa2df90f5f5a7de297ea375e345c (release 1.8.6),
        src/unittest_parallel/main.py.
"""

from __future__ import annotations

import collections
import dataclasses
import re

# CPY runner.py:35-36 (TextTestResult.separator1/separator2); UP main.py:208 and :363-365 print the same.
SEP1 = "=" * 70
SEP2 = "-" * 70
# CPY suite.py:233-235 names a class or module fixture failure "<method> (<parent>)" through an
# _ErrorHolder (suite.py:328-353: id() and str() are that description, no docstring line).
FIXTURE_NAMES = ("setUpModule", "tearDownModule", "setUpClass", "tearDownClass")
OUTCOMES = ("ok", "FAIL", "ERROR", "skipped", "expected failure", "unexpected success")
# CPY runner.py:92-140 and UP main.py:397-419 write these words after " ... ".
FIXED_STATUS = ("ok", "FAIL", "ERROR", "expected failure", "unexpected success")
# CPY runner.py:119 and UP main.py:411 write "skipped {reason!r}": a Python string literal.
_SKIP_LITERAL = r"""(?:'(?:[^'\\\n]|\\.)*'|"(?:[^"\\\n]|\\.)*")"""
STATUS_ALT = r"(?:ok|FAIL|ERROR|expected failure|unexpected success|skipped " + _SKIP_LITERAL + r")"
_SKIP_AT = re.compile(r"skipped " + _SKIP_LITERAL)
_STATUS_SUFFIX = re.compile("(" + STATUS_ALT + r")$")
# CPY runner.py:254-256 "Ran %d test%s in %.3fs"; UP main.py:209 writes "test" for 0 or 1, "tests" above.
RAN_RE = re.compile(r"^Ran (\d+) tests? in (\d+\.\d{3})s$")
# CPY runner.py:269-290 and UP main.py:181-191,211: the status word, then the infos in this order.
STATUS_LINE_RE = re.compile(r"^(OK|FAILED|NO TESTS RAN)(?: \((.+)\))?$")
INFO_ORDER = ("failures", "errors", "skipped", "expected failures", "unexpected successes")
INFO_OUTCOME = {"failures": "FAIL", "errors": "ERROR", "skipped": "skipped",
                "expected failures": "expected failure", "unexpected successes": "unexpected success"}
# UP main.py:134-137 (stderr, before any test). A prefix is tolerated: other output may precede it.
HEADER_RE = re.compile(r"Running (\d+) test suites \((\d+) total tests\) across (\d+) workers$")
# CPY runner.py:202-222 (only with --durations): rows "%-10s %s" % ("%.3fs" % elapsed, test).
_DURATION_ROW = re.compile(r"^\d+\.\d{3}s\s+\S")
# A description: CPY case.py:530-531 (v3.13.16; v3.12.3 :513-514) TestCase.__str__ is
# "<method> (<module>.<class>.<method>)"; loader-made tests keep that shape (CPY loader.py, v3.13.16
# :23-59: _FailedTest and ModuleSkipped use the module name as the method name).
_DESC_AT_START = re.compile(r"(?P<ind>  )?(?P<name>[^\s()]+) \((?P<inner>[^\s()]+)\)")
_SUB_TAIL = re.compile(r"^ (?P<sub>.+?) \.\.\. (?P<st>" + STATUS_ALT + r")$")
_DOC_STATUS = re.compile(r"^(?P<doc>.*) \.\.\. (?P<st>" + STATUS_ALT + r")$")
_RESULT_TAIL = re.compile(r"^(?: (?P<sub>.+?))? \.\.\. (?P<st>" + STATUS_ALT + r")$")
_RESULT_END = re.compile(r" \.\.\. " + STATUS_ALT + r"$")
_FRAGMENT = re.compile(r" \.\.\. (FAIL|ERROR)$")


# --------------------------------------------------------------------------- status tokens


def status_at(text: str, pos: int = 0):
    """(outcome, end) for the status word starting at pos, else None."""
    for token in FIXED_STATUS:
        if text.startswith(token, pos):
            return token, pos + len(token)
    match = _SKIP_AT.match(text, pos)
    if match:
        return "skipped", match.end()
    return None


def full_status(text: str):
    """The outcome when text is exactly one status word (a skip with its reason), else None."""
    found = status_at(text)
    return found[0] if found and found[1] == len(text) else None


def outcome_of(token: str) -> str:
    return "skipped" if token.startswith("skipped") else token


def classify_desc(name: str, inner: str):
    """("test", id) or ("fixture", key) for a "name (inner)" description, else None."""
    if inner.endswith("." + name):
        return "test", inner
    if name in FIXTURE_NAMES:
        return "fixture", f"{name} ({inner})"
    return None


def classify_glued(name: str, inner: str):
    """Like classify_desc, tolerating output glued in front of the name; returns (kind, key, prefix)."""
    found = classify_desc(name, inner)
    if found:
        return found[0], found[1], ""
    last = inner.rsplit(".", 1)[-1]
    if "." in inner and name.endswith(last) and len(name) > len(last):
        return "test", inner, name[: -len(last)]
    for fixture in FIXTURE_NAMES:
        if name.endswith(fixture) and len(name) > len(fixture):
            return "fixture", f"{fixture} ({inner})", name[: -len(fixture)]
    return None


def desc_key(text: str):
    """The record key of an error-block header description, else None."""
    match = _DESC_AT_START.match(text)
    if not match or match.group("ind"):
        return None
    kind = classify_desc(match.group("name"), match.group("inner"))
    if kind is None:
        return None
    after = text[match.end():]
    if after == "":
        return kind[1]
    if kind[0] == "test" and after.startswith(" ") and len(after) > 1:
        return f"{kind[1]} {after[1:]}"  # a subtest: CPY case.py (v3.13.16) :1468-1469 _SubTest.id()
    return None


# --------------------------------------------------------------------------- parsed log


@dataclasses.dataclass
class Execution:
    test_id: str
    line: int
    own: str | None = None
    subtests: list = dataclasses.field(default_factory=list)  # [(sub, outcome)]
    status_only: list = dataclasses.field(default_factory=list)
    glued: list = dataclasses.field(default_factory=list)

    def derived(self):
        """A test whose subtests failed gets no status of its own: CPY case.py (v3.13.16)
        :648-665 calls addSuccess only when outcome.success, and :54-84 records each failing
        subtest through addSubTest instead."""
        outcomes = {outcome for _, outcome in self.subtests}
        for outcome in ("ERROR", "FAIL", "skipped"):
            if outcome in outcomes:
                return outcome
        return None


@dataclasses.dataclass
class ParsedLog:
    mode: str = "serial"
    header: dict | None = None
    ran: int | None = None
    seconds: float | None = None
    status_word: str | None = None
    status_counts: dict = dataclasses.field(default_factory=dict)
    executions: list = dataclasses.field(default_factory=list)
    fixtures: list = dataclasses.field(default_factory=list)  # [(key, outcome)]
    error_blocks: list = dataclasses.field(default_factory=list)  # [(flavour or None, key)]
    anomalies: list = dataclasses.field(default_factory=list)
    notes: list = dataclasses.field(default_factory=list)
    durations_section: bool = False

    def records(self) -> list:
        """(kind, key, outcome) triples: the multiset the arms are compared on."""
        result = []
        for ex in self.executions:
            if ex.own is not None:
                result.append(("test", ex.test_id, ex.own))
            elif ex.derived() is not None:
                result.append(("derived", ex.test_id, ex.derived()))
            for sub, outcome in ex.subtests:
                result.append(("subtest", f"{ex.test_id} {sub}", outcome))
        result.extend(("fixture", key, outcome) for key, outcome in self.fixtures)
        return result

    def outcome_counts(self) -> dict:
        """Counts the summary line reports: CPY result.py:126-140 adds one failure or error per
        failing subtest; :147-160 one skip, expected failure or unexpected success per call."""
        counts = collections.Counter()
        for kind, _key, outcome in self.records():
            if kind != "derived":
                counts[outcome] += 1
        return {outcome: counts.get(outcome, 0) for outcome in OUTCOMES}

    def started_ids(self) -> set:
        return {ex.test_id for ex in self.executions}

    def groups(self) -> dict:
        """Records grouped by test id (subtests under their test) or fixture key."""
        grouped = collections.defaultdict(list)
        for kind, key, outcome in self.records():
            if kind == "subtest":
                group = key.split(" ", 1)[0]
            else:
                group = key
            grouped[group].append((kind, key, outcome))
        return {group: tuple(sorted(items)) for group, items in grouped.items()}


def _find_summary(lines: list):
    """Index of the final separator2 and the parsed Ran/status lines. The block is the LAST
    "separator2, Ran, blank, status" run: buffered stdout is flushed after it at exit."""
    saw_ran = False
    for index in range(len(lines) - 1, 0, -1):
        match = RAN_RE.match(lines[index])
        if not match:
            continue
        saw_ran = True
        if (lines[index - 1] == SEP2 and index + 2 < len(lines) and lines[index + 1] == ""
                and STATUS_LINE_RE.match(lines[index + 2])):
            status = STATUS_LINE_RE.match(lines[index + 2])
            return index - 1, int(match.group(1)), float(match.group(2)), status.group(1), status.group(2)
    return "ran-without-block" if saw_ran else None


def _parse_infos(infos: str | None):
    counts = {key: 0 for key in INFO_ORDER}
    if not infos:
        return counts, []
    problems, seen = [], []
    for part in infos.split(", "):
        key, sep, value = part.rpartition("=")
        if not sep or key not in counts or not value.isdigit() or key in seen:
            problems.append(f"unrecognised status info {part!r}")
            continue
        seen.append(key)
        counts[key] = int(value)
    if seen != [key for key in INFO_ORDER if key in seen]:
        problems.append("status infos out of the upstream order")
    return counts, problems


def _strip_durations(lines: list, end: int) -> tuple[int, bool]:
    """Skip CPY runner.py:202-222's optional "Slowest test durations" table before separator2."""
    k = end - 1
    if k >= 2 and lines[k] == "":
        j = k - 1
        while j >= 0 and _DURATION_ROW.match(lines[j]):
            j -= 1
        if j >= 1 and lines[j] == SEP2 and lines[j - 1] == "Slowest test durations":
            return j - 1, True
    return end, False


def _block_header(lines: list, k: int, end: int, mode: str):
    """(flavour, key, sep2_index) for an error block starting at separator1 index k, else None.
    Serial: CPY runner.py:155-161 "<FLAVOUR>: <description>" between separator1 and separator2.
    Parallel: UP main.py:361-367 the bare description between the separators."""
    if k + 2 >= end:
        return None
    first = lines[k + 1]
    flavour = None
    if mode == "serial":
        for prefix in ("ERROR: ", "FAIL: "):
            if first.startswith(prefix):
                flavour, first = prefix[:-2], first[len(prefix):]
                break
        else:
            return None
    key = desc_key(first)
    if key is None:
        return None
    for sep2_at in (k + 2, k + 3):  # the description may carry a docstring line (runner.py:49-54)
        if sep2_at < end and lines[sep2_at] == SEP2:
            if mode == "parallel" and sep2_at + 1 < end and lines[sep2_at + 1] == "UNEXPECTED SUCCESS":
                flavour = "unexpected success"  # UP main.py:357
            return flavour, key, sep2_at
    return None


def _error_section(lines: list, end: int, mode: str, counts: dict, out: ParsedLog) -> int:
    """Locate the error report that follows every test record; return where the records end.

    Serial: CPY runner.py:142-153 prints a blank line, one block per error then failure, then one
    separator1 followed by "UNEXPECTED SUCCESS: <description>" lines. Parallel: UP main.py:193-204
    prints a blank line, then one block per error, failure and unexpected success. Blocks are found
    backwards from the final separator2, as many as the status line's counts require."""
    failures, errors, unexpected = counts["failures"], counts["errors"], counts["unexpected successes"]
    blocks = []
    if mode == "serial" and unexpected:
        j = end - 1
        while j >= 0 and lines[j] != SEP1:
            j -= 1
        listed = []
        for line in lines[j + 1:end] if j >= 0 else []:
            if line.startswith("UNEXPECTED SUCCESS: "):
                listed.append(("unexpected success", desc_key(line[len("UNEXPECTED SUCCESS: "):])))
        if j < 0 or len(listed) != unexpected or any(key is None for _, key in listed):
            out.anomalies.append("the unexpected-success report does not list the counted tests")
        else:
            blocks.extend(listed)
            end = j
    wanted = failures + errors + (unexpected if mode == "parallel" else 0)
    found = []
    k = end - 1
    while len(found) < wanted and k >= 0:
        if lines[k] == SEP1:
            header = _block_header(lines, k, end, mode)
            if header:
                found.append((k, header))
        k -= 1
    if len(found) < wanted:
        out.anomalies.append(f"error report has {len(found)} of the {wanted} blocks the status line counts")
    first = found[-1][0] if found else end
    out.error_blocks = [(flavour, key) for _, (flavour, key, _) in reversed(found)] + blocks
    if first >= 1 and lines[first - 1] == "":
        return first - 1
    # Worker stdout flushed at pool shutdown can end without a newline and absorb the blank line
    # (seen in real local runs); keep that line in the parsed region so no record can hide in it.
    out.notes.append("the blank line before the error report holds other output")
    return first


def _finalize_serial(ex, out: ParsedLog) -> None:
    if ex is None or ex.own is not None or ex.subtests:
        return
    if ex.status_only:
        ex.own = ex.status_only[-1]
        out.notes.append(f"line {ex.line}: {ex.test_id} result on a later line after test output")
    elif ex.glued:
        ex.own = ex.glued[-1]
        out.notes.append(f"line {ex.line}: {ex.test_id} result glued to the end of test output")
    else:
        out.anomalies.append(f"line {ex.line}: no result for started test {ex.test_id}")


def _doc_rest(line: str):
    """The text after " ... " on a serial docstring line, or None when the line has none."""
    match = _DOC_STATUS.match(line)
    if match:
        return match.group("st")
    if line.endswith(" ... ") or line.endswith(" ..."):
        return ""
    if " ... " in line:
        return line.split(" ... ", 1)[1]
    return None


def _parse_serial(lines: list, end: int, out: ParsedLog) -> list:
    """CPY runner.py:56-62 writes "<description> ... " and flushes without a newline; the status
    follows at once (runner.py:64-75 when _newline is False) or after interleaved test output, on
    a later line or glued to an unterminated output line. Returns status lines seen while no test
    was running: runner.py:124-140 leave _newline False after "expected failure" and "unexpected
    success", so a following fixture result is printed by runner.py:64-75 as a bare status word."""
    pending = None
    anonymous = []
    i = 0
    while i < end:
        line = lines[i]
        match = _DESC_AT_START.match(line)
        kind = classify_desc(match.group("name"), match.group("inner")) if match else None
        if kind and match.group("ind"):
            # A subtest result: runner.py:64-75 writes "  " + description + " ... " + status.
            after, sub, status, used = line[match.end():], None, None, 1
            tail = _SUB_TAIL.match(after)
            if tail:
                sub, status = tail.group("sub"), outcome_of(tail.group("st"))
            elif after.startswith(" ") and len(after) > 1 and i + 1 < end and _DOC_STATUS.match(lines[i + 1]):
                sub, status, used = after[1:], outcome_of(_DOC_STATUS.match(lines[i + 1]).group("st")), 2
            if kind[0] == "test" and sub is not None:
                if pending is None or pending.test_id != kind[1]:
                    out.anomalies.append(f"line {i + 1}: subtest result for {kind[1]}, which is not running")
                else:
                    pending.subtests.append((sub, status))
                i += used
                continue
        elif kind:
            after, used = line[match.end():], 1
            if after == "":
                rest = _doc_rest(lines[i + 1]) if i + 1 < end else None
                used = 2
            elif after.startswith(" ... "):
                rest = after[5:]
            elif after == " ...":
                rest = ""
            else:
                rest = None
            if rest is not None:
                status = full_status(rest)
                if kind[0] == "fixture":
                    if status is None:
                        out.anomalies.append(f"line {i + 1}: fixture line without a status: {kind[1]}")
                    else:
                        _finalize_serial(pending, out)
                        pending = None
                        out.fixtures.append((kind[1], outcome_of(status)))
                    i += used
                    continue
                if (pending is not None and pending.test_id == kind[1] and pending.subtests
                        and pending.own is None and status is not None):
                    pending.own = outcome_of(status)  # its own result after its subtest lines
                    pending = None
                    i += used
                    continue
                _finalize_serial(pending, out)
                ex = Execution(kind[1], i + 1)
                out.executions.append(ex)
                pending = None
                if status is not None:
                    ex.own = outcome_of(status)
                else:
                    pending = ex
                    glued = _STATUS_SUFFIX.search(rest) if rest else None
                    if glued:
                        ex.glued.append(outcome_of(glued.group(1)))
                i += used
                continue
        status = full_status(line)
        if status is not None:
            status = outcome_of(status)
            if pending is not None and not pending.subtests:
                if status in ("expected failure", "unexpected success"):
                    pending.own = status
                    pending = None
                else:
                    pending.status_only.append(status)
            elif pending is None:
                anonymous.append((i + 1, status))
        elif pending is not None and not pending.subtests:
            glued = _STATUS_SUFFIX.search(line)
            if glued:
                pending.glued.append(outcome_of(glued.group(1)))
        i += 1
    _finalize_serial(pending, out)
    return anonymous


def _iter_descs(line: str):
    """Every "name (inner)" in the line, left to right: (start, end, name, inner), where name and
    inner hold no whitespace or parenthesis. A linear scan from each " (" (a regex search here
    backtracks quadratically over long unbroken output tokens)."""
    pos = line.find(" (")
    while pos != -1:
        close = line.find(")", pos + 2)
        if close == -1:
            return
        inner = line[pos + 2:close]
        if inner and not any(char.isspace() or char == "(" for char in inner):
            start = pos
            while start > 0 and not line[start - 1].isspace() and line[start - 1] not in "()":
                start -= 1
            if start < pos:
                yield start, close + 1, line[start:pos], inner
        pos = line.find(" (", pos + 1)


def _find_record(line: str):
    """First description in the line that names a test or fixture, tolerating glued output:
    (kind, key, text before the name, text after the description, where the name starts)."""
    for start, end, name, inner in _iter_descs(line):
        found = classify_glued(name, inner)
        if found:
            kind, key, glued = found
            return kind, key, line[:start] + glued, line[end:], start + len(glued)
    return None


def _orphan_fragment(line: str, awaiting: list, doc_line: bool):
    """Split a subtest's separately written " ... FAIL|ERROR" off the end of a line.

    CPY runner.py:64-75 (_write_status, used by addSubTest at :77-90) writes the indent, the
    description and " ... <status>" in separate calls; with a docstring the description holds a
    newline, so line-buffered stderr flushes it alone and other workers' text can arrive before
    the " ... FAIL" that completes it. That fragment then ends some other line: one that is whole
    without it (a "<docstring> ..." start, a "... <status>" result) or bare output. Returns
    (remaining line, status) or None."""
    if not awaiting:
        return None
    match = _FRAGMENT.search(line)
    if not match:
        return None
    rest = line[:match.start()]
    if rest == "" or rest.endswith(" ...") or _RESULT_END.search(rest):
        return rest, match.group(1)
    if not doc_line and _find_record(line) is None:
        return rest, match.group(1)
    return None


def _claim_fragment(split, awaiting: list, subs, out: ParsedLog, line_no: int) -> str:
    rest, status = split
    key, sub = awaiting.pop(0)
    subs[key].append((sub, status))
    out.notes.append(f"line {line_no}: subtest status of {key} {sub} completed by a separately written fragment")
    return rest


def _parallel_doc(line: str, known: str | None):
    """Parse the docstring line after a bare parallel description: ("result", status, suffix),
    ("start", None, suffix) or None. UP main.py:381,392 write the description and its docstring
    line in one write and the newline in a second, so another worker's line can be glued after.
    The docstring text from the test's own start line splits the line exactly; without it, the
    leftmost " ... <status>" (or " ...") wins only if what follows is empty or another record."""
    if known is not None and line.startswith(known + " ..."):
        after = line[len(known) + 4:]
        found = status_at(after, 1) if after.startswith(" ") else None
        if found:
            return "result", outcome_of(found[0]), after[found[1]:], known
        return "start", None, after, known
    if known is not None and line.startswith(known):
        return None  # the docstring line ends early: the rest is another worker's text
    for match in re.finditer(r" \.\.\.", line):
        after = line[match.end():]
        found = status_at(after, 1) if after.startswith(" ") else None
        if found:
            suffix = after[found[1]:]
            if suffix == "" or _find_record(suffix):
                return "result", outcome_of(found[0]), suffix, line[:match.start()]
        elif after == "" or _find_record(after):
            return "start", None, after, line[:match.start()]
    return None


def _parallel_doc_status(line: str, known: str | None) -> bool:
    """Whether a subtest's docstring line carries its own " ... <status>"."""
    parsed = _parallel_doc(line, known)
    return parsed is not None and parsed[0] == "result"


def _parse_parallel(lines: list, end: int, out: ParsedLog) -> None:
    """UP main.py:377-383 prints "<description> ..." when a test starts and :390-419
    "<description> ... <status>" when it ends; subtest failures come from the inherited CPY
    runner.py:77-90, whose _write_status prints "  <description> ... FAIL" (UP never sets
    _newline False). Lines of different workers interleave; only result lines decide outcomes."""
    work = list(lines[:end])
    started = collections.Counter()
    own = collections.defaultdict(list)
    subs = collections.defaultdict(list)
    docs = {}
    first_line = {}
    awaiting = []  # [(test id, subtest description)] whose " ... FAIL|ERROR" has not arrived yet
    i = 0
    while i < len(work):
        line = work[i]
        if HEADER_RE.search(line):
            i += 1
            continue
        split = _orphan_fragment(line, awaiting, False)
        if split:
            line = work[i] = _claim_fragment(split, awaiting, subs, out, i + 1)
        record = _find_record(line)
        if record is None:
            i += 1
            continue
        kind, key, prefix, after, _ = record
        if prefix.strip():
            out.notes.append(f"line {i + 1}: output glued before a record of {key}")
        first_line.setdefault(key, i + 1)
        tail = _RESULT_TAIL.match(after)
        if tail:
            _add_parallel_result(kind, key, tail.group("sub"), outcome_of(tail.group("st")), own, subs, out)
            i += 1
            continue
        if after == " ...":
            if kind == "test":
                started[key] += 1
            i += 1
            continue
        if (after == "" or after.startswith(" ")) and " ... " not in after and i + 1 < len(work):
            sub = after[1:] if after.startswith(" ") and len(after) > 1 else None
            split = _orphan_fragment(work[i + 1], awaiting, True)
            if split:
                work[i + 1] = _claim_fragment(split, awaiting, subs, out, i + 2)
            nxt, known = work[i + 1], docs.get(key)
            if kind == "test" and sub is not None and not _parallel_doc_status(nxt, known):
                # A subtest description whose " ... <status>" was written separately: the docstring
                # line ends early and other text may follow it on the same line.
                awaiting.append((key, sub))
                if known is not None and nxt.startswith(known):
                    suffix = nxt[len(known):]
                else:
                    found = _find_record(nxt)
                    suffix = nxt[found[4]:] if found else ""
                out.notes.append(f"line {i + 2}: subtest description of {key} {sub} without its status")
                if suffix:
                    work[i + 1] = suffix
                    i += 1
                else:
                    i += 2
                continue
            parsed = _parallel_doc(nxt, known)
            if parsed is not None:
                what, status, suffix, doc = parsed
                docs.setdefault(key, doc)
                if what == "result":
                    _add_parallel_result(kind, key, sub, status, own, subs, out)
                elif kind == "test" and sub is None:
                    started[key] += 1
                if suffix:
                    out.notes.append(f"line {i + 2}: another line glued after the docstring line of {key}")
                    work[i + 1] = suffix
                    i += 1
                else:
                    i += 2
                continue
        i += 1
    for key, sub in awaiting:
        out.anomalies.append(f"subtest {key} {sub}: its status never arrived")
    for key in sorted(set(started) | set(own) | set(subs)):
        n_start, n_own, sub_list = started[key], len(own[key]), subs[key]
        n_exec = max(n_start, n_own, 1 if sub_list else 0)
        executions = [Execution(key, first_line.get(key, 0)) for _ in range(n_exec)]
        for index, outcome in enumerate(own[key]):
            executions[index].own = outcome
        holder = next((ex for ex in executions if ex.own is None), executions[0])
        holder.subtests.extend(sub_list)
        for ex in executions:
            if ex.own is None and not ex.subtests:
                out.anomalies.append(f"no result line for started test {key}")
        if n_own > n_start:
            out.notes.append(f"{key}: {n_own - n_start} result line(s) without a recognised start line")
        out.executions.extend(executions)


def _add_parallel_result(kind, key, sub, outcome, own, subs, out) -> None:
    if kind == "fixture":
        out.fixtures.append((key, outcome))
    elif sub is not None:
        subs[key].append((sub, outcome))
    else:
        own[key].append(outcome)


def parse_log(text: str) -> ParsedLog:
    out = ParsedLog()
    lines = text.replace("\r\n", "\n").split("\n")
    summary = _find_summary(lines)
    limit = summary[0] if isinstance(summary, tuple) else len(lines)
    for index in range(limit):
        match = HEADER_RE.search(lines[index])
        if match:
            out.mode = "parallel"
            out.header = {"suites": int(match.group(1)), "total_tests": int(match.group(2)),
                          "workers": int(match.group(3)), "line": index + 1}
            break
    if not isinstance(summary, tuple):
        out.anomalies.append("no 'Ran N tests' line: the log is truncated or the run never finished"
                             if summary is None else
                             "the 'Ran N tests' line is not followed by a blank line and a status line")
        region_end = len(lines)
        counts = None
    else:
        sep2_index, out.ran, out.seconds, out.status_word, infos = summary
        counts, problems = _parse_infos(infos)
        out.anomalies.extend(problems)
        out.status_counts = counts
        end = sep2_index
        if out.mode == "serial":
            end, out.durations_section = _strip_durations(lines, end)
        region_end = _error_section(lines, end, out.mode, counts, out)
    if out.mode == "parallel":
        _parse_parallel(lines, region_end, out)
    else:
        anonymous = _parse_serial(lines, region_end, out)
        _attribute_anonymous(anonymous, out)
    if counts is not None:
        _check_consistency(out, counts)
    return out


def _attribute_anonymous(anonymous: list, out: ParsedLog) -> None:
    """Name the bare status words of fixtures through the error report, which lists every
    errored fixture by description (CPY runner.py:146 prints errors first, in result order)."""
    if not anonymous:
        return
    named = collections.Counter((outcome, key) for kind, key, outcome in out.records()
                                if kind != "derived" and outcome in ("FAIL", "ERROR"))
    pending = []
    for flavour, key in out.error_blocks:
        if flavour in ("FAIL", "ERROR"):
            if named[(flavour, key)]:
                named[(flavour, key)] -= 1
            elif key.split(" ", 1)[0] in FIXTURE_NAMES:
                pending.append((flavour, key))
    for line, outcome in anonymous:
        target = next((entry for entry in pending if entry[0] == outcome), None)
        if target is not None:
            pending.remove(target)
            out.fixtures.append((target[1], outcome))
            out.notes.append(f"line {line}: bare {outcome} named {target[1]} from the error report")
        elif outcome in ("ERROR", "skipped"):
            out.notes.append(f"line {line}: bare {outcome!r} line not attributable to a fixture")


def _check_consistency(out: ParsedLog, counts: dict) -> None:
    executed = len(out.executions)
    if executed != out.ran:
        out.anomalies.append(f"{executed} tests started in the log but the summary says Ran {out.ran}")
    parsed = out.outcome_counts()
    for info, outcome in INFO_OUTCOME.items():
        if parsed[outcome] != counts[info]:
            out.anomalies.append(f"{parsed[outcome]} {outcome!r} records but the status line says {info}={counts[info]}")
    failing = counts["failures"] + counts["errors"] + counts["unexpected successes"]
    # CPY result.py:172-178 wasSuccessful(); runner.py:270-280 and UP main.py:178,211.
    if out.status_word == "FAILED" and failing == 0:
        out.anomalies.append("status FAILED without failures, errors or unexpected successes")
    if out.status_word in ("OK", "NO TESTS RAN") and failing:
        out.anomalies.append(f"status {out.status_word} with failures, errors or unexpected successes")
    if out.status_word == "NO TESTS RAN" and (out.ran or counts["skipped"]):
        out.anomalies.append("status NO TESTS RAN although tests ran")
    if out.mode == "serial":
        blocks = collections.Counter(out.error_blocks)
        wanted = collections.Counter((outcome, key) for kind, key, outcome in out.records()
                                     if kind != "derived" and outcome in ("FAIL", "ERROR", "unexpected success"))
    else:
        blocks = collections.Counter(key for _, key in out.error_blocks)
        wanted = collections.Counter(key for kind, key, outcome in out.records()
                                     if kind != "derived" and outcome in ("FAIL", "ERROR", "unexpected success"))
    if blocks != wanted:
        out.anomalies.append("the error report and the result lines disagree: "
                             f"report-only {_cap(sorted(map(str, (blocks - wanted).elements())))}, "
                             f"result-only {_cap(sorted(map(str, (wanted - blocks).elements())))}")


def _cap(items: list, cap: int = 5) -> str:
    shown = ", ".join(items[:cap])
    return f"[{shown}{', ...' if len(items) > cap else ''}] ({len(items)})"
