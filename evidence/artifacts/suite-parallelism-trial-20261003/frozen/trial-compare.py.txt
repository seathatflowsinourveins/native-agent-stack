#!/usr/bin/env python3
"""Independent, stdlib-only oracle for the suite-parallelism trial (2026-10-03).

It reads the logs of actual GitHub-hosted arm runs and decides whether each
unittest-parallel arm ran exactly the tests the serial production command (arm
S) ran on the same OS, with exactly the same outcomes, then applies the
preregistered speed rule. README.md states the rules and the input layout.

  python3 compare.py --results DIR --inventory-base FILE --inventory-trial FILE \
      --out result.json [--summary-md FILE]

Exit status: 0 when result.json was written (the verdict is inside it), 2 for
unusable inputs. Every parsing rule cites the upstream line it relies on:

  CPY = CPython Lib/unittest/ at tags v3.13.16 (3b55c23ff4a6aa32f77be661802a3978d7324f88)
        and v3.12.3 (f6650f9ad73359051f3e558c2431a109bc016664); runner.py, result.py and
        suite.py are byte-identical at the two tags, so one line number serves both.
        case.py and main.py differ; their lines are cited per tag.
  UP  = craigahobbs/unittest-parallel at bda5d77dc1a2fa2df90f5f5a7de297ea375e345c
        (release 1.8.6), src/unittest_parallel/main.py.
"""

from __future__ import annotations

import argparse
import collections
import dataclasses
import hashlib
import json
import re
import shlex
import statistics
import sys
from fractions import Fraction
from pathlib import Path

SCHEMA = "suite-parallelism-oracle/1"
HERE = Path(__file__).resolve().parent
DEFAULT_EXPECTATIONS = HERE / "controls" / "control_expectations.json"

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
RUN_DIR_RE = re.compile(
    r"^(?P<os>macos-15|ubuntu-24\.04)-(?P<arm>[A-Za-z0-9]+)-"
    r"(?:r(?P<rep>[1-9][0-9]*)|(?P<kind>controls|crash)(?:-r(?P<krep>[1-9][0-9]*))?)$")

# The preregistered arms (README.md, "Arms"). Baseline arm per OS is S. "command" is the arm's exact command,
# token for token: the workflow's `set --` words, which it records in command.txt as "$*" before any time limit
# wraps them. Any other token (an interpreter flag such as -X or -O, a wrapper such as coverage run or timeout, a
# reordering or an extra argument) makes the run ineligible; S alone may append "--durations N" (DURATIONS).
_SERIAL = ("python3", "-m", "unittest", "-v")
ARMS = {
    "macos-15": {
        "S": {"runner": "unittest", "command": _SERIAL},
        "P3": {"runner": "unittest_parallel", "jobs": 3, "level": "module", "pooling": True,
               "command": ("python3", "-m", "unittest_parallel", "-j", "3", "--level", "module", "-v")},
        "P3F": {"runner": "unittest_parallel", "jobs": 3, "level": "module", "pooling": False,
                "command": ("python3", "-m", "unittest_parallel", "-j", "3", "--level", "module",
                            "--disable-process-pooling", "-v")},
        "P3C": {"runner": "unittest_parallel", "jobs": 3, "level": "class", "pooling": True,
                "command": ("python3", "-m", "unittest_parallel", "-j", "3", "--level", "class", "-v")},
        "P4": {"runner": "unittest_parallel", "jobs": 4, "level": "module", "pooling": True,
               "command": ("python3", "-m", "unittest_parallel", "-j", "4", "--level", "module", "-v")},
    },
    "ubuntu-24.04": {
        "S": {"runner": "unittest", "command": _SERIAL},
        "L4": {"runner": "unittest_parallel", "jobs": 4, "level": "module", "pooling": True,
               "command": ("python3", "-m", "unittest_parallel", "-j", "4", "--level", "module", "-v")},
        "L4F": {"runner": "unittest_parallel", "jobs": 4, "level": "module", "pooling": False,
                "command": ("python3", "-m", "unittest_parallel", "-j", "4", "--level", "module",
                            "--disable-process-pooling", "-v")},
        "L4C": {"runner": "unittest_parallel", "jobs": 4, "level": "class", "pooling": True,
                "command": ("python3", "-m", "unittest_parallel", "-j", "4", "--level", "class", "-v")},
    },
}
# The plan's S diagnostic: the workflow appends "--durations 25" (CPY main.py:184 at v3.12.3 defines
# "--durations N"); a positive count after the exact S command is the only extra any arm may carry.
DURATIONS = re.compile(r"[1-9][0-9]*")
# The plan's preference: the unpooled variant wins when its median is within 10% of the pooled arm.
UNPOOLED_OF = {"P3": "P3F", "L4": "L4F"}
RULE = {"median_ratio_max": 0.60, "max_ratio_max": 0.75, "unpooled_within": 1.10, "min_repeats": 3}
# The same thresholds as exact rationals. The rule compares the exact ratios of the recorded step_seconds with
# these (no rounding before the comparison); result.json rounds the ratios for display only.
EXACT_RULE = {"median_ratio_max": Fraction("0.60"), "max_ratio_max": Fraction("0.75"),
              "unpooled_within": Fraction("1.10")}
# B1 (experiment.json task_and_failure): at the trial base e88d59e4 (TRIAL_BASE_SHA), as at the first base 56473e4b,
# tests/test_native_maintenance.py loads these six TestCase classes inside load_tests under bare module names; the
# trial head loads them as child modules of the wrapper. ids.py on both bases lists 29 ids for them (6 + 7 + 2 + 2 +
# 2 + 10, in this order), and the inventories may differ by nothing but this prefix on exactly those 29 ids.
B1_PREFIX = "tests.test_native_maintenance."
B1_CLASSES = (
    "memory_patch_evidence_tests.EvidenceTests",
    "memory_patch_evidence_tests.FunctionalFactsTests",
    "application_portability_tests.MakeBoundaryTests",
    "application_portability_tests.RecipeHistoryTests",
    "application_portability_tests.RestartPortTests",
    "wsl_transport_evidence_tests.TransportEvidenceTests",
)
B1_IDS = 29
META_FIELDS = ("os", "arm", "repeat", "command", "python_version", "platform", "runner_image",
               "checkout_sha", "step_seconds")
LIST_CAP = 200


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


# --------------------------------------------------------------------------- inputs


class InputError(Exception):
    """An unusable input file or directory (exit 2)."""


def load_inventory(path: Path) -> list:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise InputError(f"{path.name}: cannot read the inventory ({error.strerror})") from None
    ids = text.split("\n")
    if ids and ids[-1] == "":
        ids.pop()
    if not ids:
        raise InputError(f"{path.name}: the inventory is empty")
    if any(not item or item != item.strip() for item in ids):
        raise InputError(f"{path.name}: blank or padded line in the inventory")
    if ids != sorted(set(ids)):
        raise InputError(f"{path.name}: the inventory is not sorted and de-duplicated (ids.py output)")
    return ids


def check_id_mapping(base: list, trial: list, classes: tuple = B1_CLASSES, prefix: str = B1_PREFIX,
                     expected_ids: int = B1_IDS) -> dict:
    """The base and trial inventories may differ only by the B1 rewrite: the single prefix B1_PREFIX on exactly
    the base ids of the six B1_CLASSES, of which the base inventory must hold B1_IDS, as a bijection. Anything else
    (a partial rewrite, another prefix, identical inventories, any other id) sets ok to false, and build_result then
    gives every OS no verdict (experiment.json quality_rule, ID MAPPING)."""
    base_only = sorted(set(base) - set(trial))
    trial_only = sorted(set(trial) - set(base))
    rewritten = sorted(item for item in base if item.rsplit(".", 1)[0] in classes)
    report = {"base_count": len(base), "trial_count": len(trial), "base_only": len(base_only),
              "trial_only": len(trial_only), "expected_prefix": prefix, "expected_ids": expected_ids,
              "base_ids_of_the_classes": len(rewritten), "mapped": 0, "prefixes": {}, "classes": [], "problems": []}
    # The preregistered rewrite itself: exactly these ids leave the base and exactly their prefixed forms arrive.
    if len(rewritten) != expected_ids:
        report["problems"].append(f"the base inventory holds {len(rewritten)} ids of the six B1 classes; "
                                  f"the preregistration names {expected_ids}")
    absent = [name for name in classes if not any(item.rsplit(".", 1)[0] == name for item in rewritten)]
    if absent:
        report["problems"].append(f"B1 classes without a base id: {_cap(absent)}")
    left_bare = sorted(set(rewritten) - set(base_only))
    if left_bare:
        report["problems"].append(f"{len(left_bare)} of the {len(rewritten)} B1 base ids are not rewritten in the "
                                  f"trial: {_cap(left_bare)}")
    other_base = sorted(set(base_only) - set(rewritten))
    if other_base:
        report["problems"].append(f"{len(other_base)} base ids outside the B1 classes are missing from the trial: "
                                  f"{_cap(other_base)}")
    wanted = {prefix + item for item in rewritten}
    other_trial = sorted(set(trial_only) - wanted)
    if other_trial:
        report["problems"].append(f"{len(other_trial)} trial ids are not {prefix!r} plus a B1 base id: "
                                  f"{_cap(other_trial)}")
    missing_target = sorted(wanted - set(trial))
    if missing_target:
        report["problems"].append(f"{len(missing_target)} prefixed B1 ids are missing from the trial: "
                                  f"{_cap(missing_target)}")
    # Diagnostics: how the trial actually renamed the base-only ids (one target per id, one prefix per module).
    by_suffix = collections.defaultdict(list)
    for item in trial_only:
        parts = item.split(".")
        for cut in range(1, len(parts)):
            by_suffix[".".join(parts[cut:])].append(item)
    mapping = {}
    for item in base_only:
        candidates = by_suffix.get(item, [])
        if len(candidates) != 1:
            report["problems"].append(f"{item}: {len(candidates)} trial ids end with it")
        else:
            mapping[item] = candidates[0]
    used = collections.Counter(mapping.values())
    report["problems"].extend(f"{item}: target of {count} base ids" for item, count in used.items() if count > 1)
    unmapped = sorted(set(trial_only) - set(mapping.values()))
    report["problems"].extend(f"{item}: trial id with no base id" for item in unmapped[:LIST_CAP])
    prefixes = collections.defaultdict(set)
    for item, target in mapping.items():
        prefixes[item.split(".", 1)[0]].add(target[: -len(item) - 1])
    for module, found in prefixes.items():
        if len(found) != 1:
            report["problems"].append(f"{module}: rewritten with {len(found)} different prefixes")
        elif found != {prefix[:-1]}:
            report["problems"].append(f"{module}: rewritten with the prefix {sorted(found)[0]!r}, "
                                      f"not {prefix[:-1]!r}")
    report["mapped"] = len(mapping)
    report["prefixes"] = {module: sorted(found) for module, found in sorted(prefixes.items())}
    report["classes"] = sorted({item.rsplit(".", 1)[0] for item in mapping})
    if sorted(report["classes"]) != sorted(classes):
        report["problems"].append(f"{len(report['classes'])} classes rewritten; the preregistration names the "
                                  f"{len(classes)} B1 classes")
    report["ok"] = not report["problems"]
    report["problems"] = report["problems"][:LIST_CAP]
    return report


def parse_command(command: str):
    """How a command line reads, for diagnostics only (command_problems decides by exact tokens):
    {"runner", "before", "jobs", "level", "pooling", "verbose", "extra"}; "before" holds the tokens before the
    runner other than the interpreter python3 and its -m."""
    try:
        tokens = shlex.split(command)
    except ValueError:
        return None
    for index, token in enumerate(tokens):
        if token == "-m" and index + 1 < len(tokens) and tokens[index + 1] in ("unittest", "unittest_parallel"):
            runner, args, before = tokens[index + 1], tokens[index + 2:], tokens[:index]
            break
        if Path(token).name == "unittest-parallel":
            runner, args, before = "unittest_parallel", tokens[index + 1:], tokens[:index + 1]
            break
    else:
        return None
    before = before[1:] if before[:1] == ["python3"] else before
    spec = {"runner": runner, "before": before, "verbose": False, "extra": []}
    if runner == "unittest_parallel":
        spec.update({"jobs": None, "level": "module", "pooling": True})
    position = 0
    while position < len(args):
        token = args[position]
        if token in ("-v", "--verbose"):
            spec["verbose"] = True
        elif runner == "unittest_parallel" and token in ("-j", "--jobs") and position + 1 < len(args):
            position += 1
            spec["jobs"] = int(args[position]) if args[position].isdigit() else args[position]
        elif runner == "unittest_parallel" and re.fullmatch(r"-j\d+|--jobs=\d+", token):
            spec["jobs"] = int(re.sub(r"\D", "", token))
        elif runner == "unittest_parallel" and token == "--level" and position + 1 < len(args):
            position += 1
            spec["level"] = args[position]
        elif runner == "unittest_parallel" and token.startswith("--level="):
            spec["level"] = token.split("=", 1)[1]
        elif runner == "unittest_parallel" and token == "--disable-process-pooling":
            spec["pooling"] = False
        elif runner == "unittest" and token == "--durations" and position + 1 < len(args):
            position += 1  # the plan's optional S diagnostic; CPY runner.py:202-222 output is skipped
        else:
            spec["extra"].append(token)
        position += 1
    return spec


def command_matches(tokens: list, arm_spec: dict) -> bool:
    """Whether the tokens are the arm's preregistered command exactly; S may append "--durations N"."""
    expected = list(arm_spec["command"])
    if tokens == expected:
        return True
    return (arm_spec["runner"] == "unittest" and len(tokens) == len(expected) + 2
            and tokens[:len(expected)] == expected and tokens[-2] == "--durations"
            and DURATIONS.fullmatch(tokens[-1]) is not None)


def command_problems(command, arm_spec: dict) -> list:
    """[] when meta.json's command is the arm's preregistered command token for token (ARMS "command"; S may append
    "--durations N"); otherwise the mismatch first, then how the command reads (parse_command)."""
    if not isinstance(command, str) or not command.strip():
        return ["meta.json command is missing"]
    try:
        tokens = shlex.split(command)
    except ValueError:
        tokens = None
    if tokens is not None and command_matches(tokens, arm_spec):
        return []
    allowed = " (optionally followed by --durations N)" if arm_spec["runner"] == "unittest" else ""
    problems = [f"command {command!r} is not the arm's preregistered command "
                f"{' '.join(arm_spec['command'])!r}{allowed}"]
    spec = parse_command(command)
    if spec is None:
        problems.append(f"command {command!r} runs neither python3 -m unittest nor unittest_parallel")
        return problems
    if spec["runner"] != arm_spec["runner"]:
        problems.append(f"command runs {spec['runner']}, the arm needs {arm_spec['runner']}")
        return problems
    if spec["before"]:
        problems.append(f"command has tokens before the runner (a wrapper or interpreter flags): {spec['before']}")
    if not spec["verbose"]:
        problems.append("command lacks -v: per-test result lines are required")
    if spec["extra"]:
        problems.append(f"command has arguments outside the preregistration: {spec['extra']}")
    for field in ("jobs", "level", "pooling"):
        if field in arm_spec and spec.get(field) != arm_spec[field]:
            problems.append(f"command {field}={spec.get(field)!r}, the arm needs {arm_spec[field]!r}")
    return problems


def read_run_dir(path: Path) -> tuple:
    """(log text or None, exit code or None, meta dict or None, problems)."""
    problems = []
    log = exit_code = meta = None
    try:
        log = (path / "log.txt").read_text(encoding="utf-8", errors="replace")
    except OSError:
        problems.append("log.txt is missing")
    if log is not None and not log.strip():
        problems.append("log.txt is empty")
    try:
        raw = (path / "exit-code.txt").read_text(encoding="utf-8").strip()
        if re.fullmatch(r"-?\d+", raw):
            exit_code = int(raw)
        else:
            problems.append(f"exit-code.txt is not one integer: {raw[:40]!r}")
    except OSError:
        problems.append("exit-code.txt is missing")
    try:
        meta = json.loads((path / "meta.json").read_text(encoding="utf-8"))
        if not isinstance(meta, dict):
            problems.append("meta.json is not an object")
            meta = None
    except (OSError, ValueError):
        problems.append("meta.json is missing or not JSON")
    return log, exit_code, meta, problems


def read_checkout_status(path: Path) -> tuple:
    """(git-status.txt text or None, problems). ORACLE PART 2 (experiment.json quality_rule): after every run the
    workflow records `git status --porcelain=v1 --untracked-files=all` of the checkout in git-status.txt, or the text
    "git status failed". The file must exist and be empty; a dirty or unrecorded run is ineligible. This applies to
    every run directory, the control runs included, and the workflow's clean-checkout step repeats the check."""
    try:
        status = (path / "git-status.txt").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None, ["git-status.txt is missing: the checkout status after the run is unrecorded"]
    if status == "":
        return status, []
    if status.strip() == "git status failed":
        return status, ["git-status.txt says git status failed: the checkout status after the run is unrecorded"]
    lines = status.splitlines() or [repr(status)]
    return status, [f"the checkout was not clean after the run (git-status.txt holds {len(lines)} line(s): "
                    f"{_cap(lines)})"]


def read_run_attempt(path: Path) -> tuple:
    """(run attempt or None, problems). The workflow records GITHUB_RUN_ATTEMPT (github.run_attempt: 1 for a run's
    first attempt, one more for each re-run) in runtime.json for every run directory. A job re-run voids the run
    (experiment.json), so an attempt above 1, or none recorded, makes the run ineligible (fail-closed)."""
    try:
        runtime = json.loads((path / "runtime.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None, ["runtime.json is missing or not JSON: the run attempt is unrecorded"]
    raw = runtime.get("run_attempt") if isinstance(runtime, dict) else None
    attempt = None
    if isinstance(raw, str) and re.fullmatch(r"[0-9]+", raw):
        attempt = int(raw)
    elif isinstance(raw, int) and not isinstance(raw, bool):
        attempt = raw
    if attempt is None or attempt < 1:
        return None, [f"runtime.json run_attempt {raw!r} is not a recorded attempt: the run attempt is unrecorded"]
    if attempt > 1:
        return attempt, [f"run_attempt {attempt}: a job re-run voids this run (reported as a failed attempt; the "
                         "trial is repeated by a new synchronize of the draft pull request, never by a re-run)"]
    return attempt, []


def meta_problems(meta, os_name: str, arm: str, repeat: int, kind: str = "arm") -> list:
    if meta is None:
        return []
    required = META_FIELDS if kind == "arm" else tuple(f for f in META_FIELDS if f != "step_seconds")
    problems = [f"meta.json lacks {field}" for field in required if field not in meta]
    if meta.get("os", os_name) != os_name:
        problems.append(f"meta.json os {meta.get('os')!r} differs from the directory name")
    if meta.get("arm", arm) != arm:
        problems.append(f"meta.json arm {meta.get('arm')!r} differs from the directory name")
    if "repeat" in meta and meta.get("repeat") != repeat:
        problems.append(f"meta.json repeat {meta.get('repeat')!r} differs from the directory name")
    seconds = meta.get("step_seconds")
    if "step_seconds" in meta and (isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or seconds <= 0):
        problems.append("meta.json step_seconds is not a positive number")
    for field in ("checkout_sha", "python_version", "command"):
        if field in meta and (not isinstance(meta[field], str) or not meta[field].strip()):
            problems.append(f"meta.json {field} is not a non-empty string")
    return problems


def header_problems(parsed: ParsedLog, arm_spec: dict) -> list:
    if arm_spec["runner"] == "unittest":
        return ["a unittest-parallel header in a serial log"] if parsed.header else []
    if not parsed.header:
        return ["no 'Running N test suites ... across K workers' header (UP main.py:134-137)"]
    header = parsed.header
    problems = []
    expected_workers = max(1, min(header["suites"], arm_spec["jobs"]))  # UP main.py:131
    if header["workers"] != expected_workers:
        problems.append(f"header reports {header['workers']} workers, the arm implies {expected_workers}")
    if parsed.ran is not None and header["total_tests"] < parsed.ran:
        problems.append(f"header counts {header['total_tests']} tests but Ran {parsed.ran}")
    return problems


# --------------------------------------------------------------------------- runs


@dataclasses.dataclass
class Run:
    name: str
    os: str
    arm: str
    kind: str  # "arm" | "controls" | "crash"
    repeat: int
    exit_code: int | None = None
    meta: dict | None = None
    parsed: ParsedLog | None = None
    problems: list = dataclasses.field(default_factory=list)
    mismatches: list = dataclasses.field(default_factory=list)
    mismatch_total: int = 0
    missing_ids: list = dataclasses.field(default_factory=list)
    extra_ids: list = dataclasses.field(default_factory=list)
    count_deltas: dict = dataclasses.field(default_factory=dict)  # arm minus the first eligible S run
    checkout_status: str | None = None  # git-status.txt, "" when clean, None when missing
    run_attempt: int | None = None  # runtime.json run_attempt, None when unrecorded

    @property
    def seconds(self):
        value = (self.meta or {}).get("step_seconds")
        return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0 else None


def load_runs(results: Path) -> tuple:
    runs, ignored = [], []
    for entry in sorted(results.iterdir()):
        if not entry.is_dir():
            ignored.append(f"{entry.name}: not a run directory")
            continue
        match = RUN_DIR_RE.match(entry.name)
        if not match:
            ignored.append(f"{entry.name}: name outside <os>-<arm>-r<N>, -controls[-r<N>], -crash[-r<N>]")
            continue
        kind = match.group("kind") or "arm"
        repeat = int(match.group("rep") or match.group("krep") or 1)
        run = Run(entry.name, match.group("os"), match.group("arm"), kind, repeat)
        log, run.exit_code, run.meta, run.problems = read_run_dir(entry)
        run.checkout_status, status_problems = read_checkout_status(entry)
        run.run_attempt, attempt_problems = read_run_attempt(entry)
        run.problems.extend(status_problems + attempt_problems)
        arm_spec = ARMS[run.os].get(run.arm)
        if arm_spec is None:
            run.problems.append(f"arm {run.arm} is not preregistered for {run.os}")
        run.problems.extend(meta_problems(run.meta, run.os, run.arm, repeat, kind))
        if run.meta is not None and arm_spec is not None:
            run.problems.extend(command_problems(run.meta.get("command"), arm_spec))
        if log is not None:
            run.parsed = parse_log(log)
        runs.append(run)
    return runs, ignored


def integrity_problems(run: Run, inventory: set) -> list:
    """Reasons an arm-run cannot be compared at all (independent of the baseline)."""
    problems = list(run.problems)
    parsed = run.parsed
    if parsed is None:
        return problems
    problems.extend(parsed.anomalies)
    arm_spec = ARMS[run.os].get(run.arm)
    if arm_spec is not None:
        problems.extend(header_problems(parsed, arm_spec))
    if parsed.status_word is not None and run.exit_code is not None:
        # Zero versus non-zero only: CPY main.py exits 1 on failure (v3.13.16 :271-277, v3.12.3
        # :282-288) and 5 when no test ran; UP main.py:240-242 exits min(255, failures+errors+unexpected).
        if (parsed.status_word == "OK") != (run.exit_code == 0):
            problems.append(f"exit status {run.exit_code} disagrees with the status line {parsed.status_word}")
    executed = parsed.started_ids()
    covered = set()
    for key, outcome in parsed.fixtures:
        name, _, parent = key.partition(" (")
        parent = parent[:-1]
        if name in ("setUpClass", "setUpModule") and outcome in ("ERROR", "skipped"):
            # CPY suite.py:117-118: a failed or skipped class or module fixture runs none of its tests.
            covered.update(item for item in inventory if item.startswith(parent + "."))
    run.missing_ids = sorted(inventory - executed - covered)
    run.extra_ids = sorted(executed - inventory)
    if run.missing_ids:
        problems.append(f"{len(run.missing_ids)} inventory ids never ran: {_cap(run.missing_ids)}")
    if run.extra_ids:
        problems.append(f"{len(run.extra_ids)} ids outside the trial inventory ran: {_cap(run.extra_ids)}")
    if parsed.header and parsed.ran is not None and not parsed.anomalies:
        not_run = len(covered & inventory)
        if parsed.header["total_tests"] != parsed.ran + not_run:
            problems.append(f"header counts {parsed.header['total_tests']} tests; Ran {parsed.ran} plus "
                            f"{not_run} behind failed fixtures")
    return problems


def compare_os(os_name: str, runs: list, inventory: set, sha: str | None) -> dict:
    """Eligibility of every arm-run of one OS against its S baseline; returns the baseline report."""
    arm_runs = [run for run in runs if run.kind == "arm"]
    for run in arm_runs:
        run.problems = integrity_problems(run, inventory)
        if sha and run.meta and run.meta.get("checkout_sha") not in (None, sha):
            run.problems.append(f"checkout_sha {run.meta.get('checkout_sha')} is not the frozen corpus {sha}")
    s_runs = [run for run in arm_runs if run.arm == "S" and not run.problems and run.parsed]
    report = {"s_runs": sum(1 for run in arm_runs if run.arm == "S"), "s_eligible": len(s_runs),
              "flaky_ids": [], "flaky_total": 0}
    if not s_runs:
        for run in arm_runs:
            if run.arm != "S":
                run.problems.append("no eligible S baseline on this OS")
        return report
    python_versions = {run.meta.get("python_version") for run in s_runs}
    report["python_version"] = sorted(python_versions)
    report["runner_images"] = sorted({str((run.meta or {}).get("runner_image")) for run in arm_runs})
    if len(python_versions) > 1:
        # The runtime is not frozen: every comparison on this OS is void.
        for run in arm_runs:
            run.problems.append(f"the S runs used different python_version values {sorted(python_versions)}")
        return report
    grouped = [run.parsed.groups() for run in s_runs]
    keys = set().union(*grouped)
    flaky = sorted(key for key in keys if len({g.get(key) for g in grouped}) > 1)
    report["flaky_ids"], report["flaky_total"] = flaky[:1000], len(flaky)
    flaky_set = set(flaky)
    reference = grouped[0]
    for run in arm_runs:
        if run.arm == "S" or run.parsed is None:
            continue
        if run.meta and run.meta.get("python_version") not in python_versions:
            run.problems.append(f"python_version {run.meta.get('python_version')!r} differs from S {sorted(python_versions)}")
        mine = run.parsed.groups()
        diffs = []
        for key in sorted((set(reference) | set(mine)) - flaky_set):
            if reference.get(key) != mine.get(key):
                diffs.append({"id": key, "S": [list(r) for r in reference.get(key, ())],
                              "arm": [list(r) for r in mine.get(key, ())]})
        run.mismatch_total = len(diffs)
        run.mismatches = diffs[:LIST_CAP]
        if diffs:
            run.problems.append(f"{len(diffs)} ids differ from the S baseline: {_cap([d['id'] for d in diffs])}")
        s_ran = {r.parsed.ran for r in s_runs}
        if run.parsed.ran not in s_ran and not flaky_set:
            run.problems.append(f"Ran {run.parsed.ran}, S ran {sorted(s_ran)}")
        mine_counts = dict(run.parsed.status_counts, ran=run.parsed.ran)
        s_counts = dict(s_runs[0].parsed.status_counts, ran=s_runs[0].parsed.ran)
        run.count_deltas = {field: (mine_counts.get(field) or 0) - (value or 0)
                            for field, value in s_counts.items() if mine_counts.get(field) != value}
    return report


def check_controls(run: Run, expectations: dict) -> list:
    """A standalone control run against control_expectations.json (README.md, "Controls")."""
    problems = list(run.problems)
    parsed = run.parsed
    if parsed is None:
        return problems or ["no log"]
    if run.kind == "crash":
        crash = expectations["crash_control"]
        if run.exit_code is None:
            problems.append("no recorded exit status: the 300 s bound must record one (124 when it fires)")
        elif run.exit_code == 0:
            problems.append("exit status 0 after a test ended its process: the arm fails open")
        if parsed.status_word == "OK":
            problems.append("an OK summary after a test ended its process: the arm fails open")
        if crash["test_id"] not in parsed.started_ids():
            problems.append(f"{crash['test_id']} never started: the crash control did not run")
        return problems
    standalone = expectations["standalone_run"]
    problems.extend(parsed.anomalies)
    arm_spec = ARMS[run.os].get(run.arm)
    if parsed.ran != standalone["ran"]:
        problems.append(f"Ran {parsed.ran}, expected {standalone['ran']}")
    if parsed.status_word != standalone["status_word"]:
        problems.append(f"status {parsed.status_word}, expected {standalone['status_word']}")
    if parsed.status_counts and parsed.status_counts != standalone["status_counts"]:
        problems.append(f"status counts {parsed.status_counts}, expected {standalone['status_counts']}")
    if run.exit_code is None or run.exit_code == 0:
        problems.append(f"exit status {run.exit_code}, expected non-zero")
    want = collections.Counter(tuple(item) for item in standalone["records"])
    got = collections.Counter(parsed.records())
    if want != got:
        problems.append(f"records differ: missing {_cap(sorted(map(str, (want - got).elements())))}, "
                        f"unexpected {_cap(sorted(map(str, (got - want).elements())))}")
    if arm_spec is not None:
        if arm_spec["runner"] == "unittest":
            if parsed.header:
                problems.append("a unittest-parallel header in a serial control log")
        elif not parsed.header:
            problems.append("no unittest-parallel header")
        else:
            header = standalone["parallel_header"]
            suites = header["suites_by_level"][arm_spec["level"]]
            expected = (suites, header["total_tests"], min(suites, arm_spec["jobs"]))
            got_header = (parsed.header["suites"], parsed.header["total_tests"], parsed.header["workers"])
            if got_header != expected:
                problems.append(f"header (suites, tests, workers) {got_header}, expected {expected}")
    return problems


# --------------------------------------------------------------------------- verdict


def timing(values: list) -> dict | None:
    if not values:
        return None
    return {"median": statistics.median(values), "min": min(values), "max": max(values), "n": len(values)}


def exact_median(values: list) -> Fraction:
    """The median as an exact rational of the recorded values (whole seconds in the workflow; a float counts at its
    exact binary value), so that no rule compares a rounded or float-divided number."""
    ordered = sorted(Fraction(value) for value in values)
    middle = len(ordered) // 2
    return ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2


def ratio_text(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


def verdict_for_os(os_name: str, runs: list, controls: dict, min_repeats: int) -> dict:
    arm_runs = [run for run in runs if run.kind == "arm"]
    s_runs = [run for run in arm_runs if run.arm == "S" and not run.problems]
    s_times = [run.seconds for run in s_runs if run.seconds is not None]
    s_timing = timing(s_times)
    s_exact = (exact_median(s_times), min(Fraction(value) for value in s_times)) if s_times else None
    medians = {}  # exact medians: the speed rule, the fastest-arm choice and the unpooled preference use these
    arms = {}
    for arm in ARMS[os_name]:
        mine = [run for run in arm_runs if run.arm == arm]
        eligible = [run for run in mine if not run.problems]
        times = [run.seconds for run in mine if run.seconds is not None]
        stats = timing(times)
        if times:
            medians[arm] = exact_median(times)
        control = controls.get((os_name, arm), {})
        reasons = []
        if len(mine) < min_repeats:
            reasons.append(f"{len(mine)} runs, the preregistration needs {min_repeats}")
        if len(eligible) != len(mine):
            reasons.append(f"{len(mine) - len(eligible)} ineligible runs")
        if len(times) != len(mine):
            reasons.append("a run lacks step_seconds")
        for kind in ("controls", "crash"):
            state = control.get(kind)
            if state is None:
                reasons.append(f"no {kind} run")
            elif not state["passed"]:
                reasons.append(f"{kind} run failed")
        entry = {"runs": len(mine), "eligible_runs": len(eligible), "timing": stats,
                 "controls_passed": (control.get("controls") or {}).get("passed"),
                 "crash_passed": (control.get("crash") or {}).get("passed")}
        if arm != "S" and stats and s_timing:
            # Exact ratios against the exact thresholds (EXACT_RULE); the two rounded fields are for display only.
            median_ratio = medians[arm] / s_exact[0]
            max_ratio = max(Fraction(value) for value in times) / s_exact[1]
            entry["median_vs_s_median"] = round(float(median_ratio), 4)
            entry["max_vs_s_fastest"] = round(float(max_ratio), 4)
            entry["median_vs_s_median_exact"] = ratio_text(median_ratio)
            entry["max_vs_s_fastest_exact"] = ratio_text(max_ratio)
            entry["meets_speed_rule"] = (median_ratio <= EXACT_RULE["median_ratio_max"]
                                         and max_ratio <= EXACT_RULE["max_ratio_max"])
        entry["eligible"] = not reasons
        entry["reasons"] = reasons
        arms[arm] = entry
    report = {"arms": arms, "s_timing": s_timing, "selected_arm": None, "reasons": []}
    if not arms["S"]["eligible"]:
        report["outcome"] = "no verdict"
        report["reasons"].append("the S baseline is not eligible: " + "; ".join(arms["S"]["reasons"]))
        return report
    candidates = [arm for arm, entry in arms.items() if arm != "S" and entry["eligible"] and entry["timing"]]
    if not candidates:
        report["outcome"] = "reject"
        report["reasons"].append("no parallel arm is eligible")
        return report
    fastest = min(candidates, key=lambda arm: (medians[arm], arm))
    report["fastest_eligible_arm"] = fastest
    if not arms[fastest].get("meets_speed_rule"):
        report["outcome"] = "reject"
        report["reasons"].append(f"the fastest eligible arm {fastest} misses the speed rule "
                                 f"(median {arms[fastest]['median_vs_s_median_exact']} of S median, "
                                 f"max {arms[fastest]['max_vs_s_fastest_exact']} of S fastest; "
                                 f"the rule allows {ratio_text(EXACT_RULE['median_ratio_max'])} and "
                                 f"{ratio_text(EXACT_RULE['max_ratio_max'])})")
        return report
    chosen = fastest
    unpooled = UNPOOLED_OF.get(fastest)
    if unpooled and unpooled in candidates and arms[unpooled].get("meets_speed_rule"):
        ratio = medians[unpooled] / medians[fastest]
        applied = ratio <= EXACT_RULE["unpooled_within"]
        report["unpooled_preference"] = {"from": fastest, "to": unpooled, "median_ratio": round(float(ratio), 4),
                                         "median_ratio_exact": ratio_text(ratio), "applied": applied}
        if applied:
            chosen = unpooled
    report["selected_arm"] = chosen
    report["outcome"] = "adopt"
    return report


def run_summary(run: Run) -> dict:
    parsed = run.parsed
    item = {"name": run.name, "os": run.os, "arm": run.arm, "kind": run.kind, "repeat": run.repeat,
            "eligible": not run.problems, "reasons": run.problems[:LIST_CAP], "exit_code": run.exit_code,
            "step_seconds": run.seconds, "run_attempt": run.run_attempt,
            "checkout_clean": None if run.checkout_status is None else run.checkout_status == ""}
    for field in ("python_version", "platform", "runner_image", "checkout_sha", "command"):
        item[field] = (run.meta or {}).get(field)
    if parsed is not None:
        item.update({"mode": parsed.mode, "header": parsed.header, "ran": parsed.ran,
                     "status_word": parsed.status_word, "status_counts": parsed.status_counts,
                     "outcome_counts": parsed.outcome_counts(), "notes": parsed.notes[:LIST_CAP],
                     "notes_total": len(parsed.notes), "durations_section": parsed.durations_section})
    if run.kind == "arm":
        item.update({"count_deltas_vs_s": run.count_deltas,
                     "mismatch_total": run.mismatch_total, "mismatches": run.mismatches,
                     "missing_ids": run.missing_ids[:LIST_CAP], "missing_total": len(run.missing_ids),
                     "extra_ids": run.extra_ids[:LIST_CAP], "extra_total": len(run.extra_ids)})
    return item


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_result(results: Path, base_path: Path, trial_path: Path, expectations_path: Path,
                 min_repeats: int = RULE["min_repeats"], expected_sha: str | None = None) -> dict:
    if not results.is_dir():
        raise InputError("--results is not a directory")
    base = load_inventory(base_path)
    trial = load_inventory(trial_path)
    try:
        expectations = json.loads(expectations_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise InputError("the control expectations file is missing or not JSON") from None
    runs, ignored = load_runs(results)
    inventory = set(trial)
    shas = collections.Counter(run.meta.get("checkout_sha") for run in runs if run.kind == "arm" and run.meta)
    frozen = expected_sha or (shas.most_common(1)[0][0] if shas else None)
    baselines = {}
    for os_name in ARMS:
        baselines[os_name] = compare_os(os_name, [run for run in runs if run.os == os_name], inventory, frozen)
    controls = {}
    control_items = []
    for run in runs:
        if run.kind == "arm":
            continue
        problems = check_controls(run, expectations)
        state = controls.setdefault((run.os, run.arm), {})
        previous = state.get(run.kind)
        passed = not problems and (previous is None or previous["passed"])
        state[run.kind] = {"passed": passed}
        control_items.append({"name": run.name, "os": run.os, "arm": run.arm, "kind": run.kind,
                              "passed": not problems, "problems": problems[:LIST_CAP],
                              "exit_code": run.exit_code, "ran": run.parsed.ran if run.parsed else None,
                              "status_word": run.parsed.status_word if run.parsed else None,
                              "run_attempt": run.run_attempt,
                              "checkout_clean": None if run.checkout_status is None else run.checkout_status == ""})
    mapping = check_id_mapping(base, trial)
    verdicts = {}
    for os_name in ARMS:
        # Every preregistered OS is listed, with its arms, whether or not any of its runs arrived.
        mine = [run for run in runs if run.os == os_name]
        verdicts[os_name] = verdict_for_os(os_name, mine, controls, min_repeats)
        verdicts[os_name]["baseline"] = baselines[os_name]
        if not mine:
            # No run directory of this OS (timed, control or crash) reached compare.py: no verdict, said plainly.
            verdicts[os_name].update(outcome="no verdict", selected_arm=None, reasons=["no run directory"])
        if not mapping["ok"]:
            # experiment.json quality_rule, ID MAPPING: otherwise neither OS gets a verdict, with or without runs.
            verdicts[os_name]["outcome"] = "no verdict"
            verdicts[os_name]["selected_arm"] = None
            verdicts[os_name]["reasons"].insert(
                0, "id_mapping.ok is false: the base and trial inventories differ by more than the B1 rewrite, "
                   "so neither OS gets a verdict")
    return {
        "schema": SCHEMA,
        "decision_rule": {
            "eligibility": "every run of the arm is eligible under both oracle parts (part 1: zero mismatches "
                           "against S outside flaky ids, the exact preregistered command, run_attempt 1 recorded in "
                           "runtime.json; part 2: an existing, empty git-status.txt), at least "
                           f"{min_repeats} runs, and its controls and crash control passed on that OS (their run "
                           "directories under the same two parts)",
            "speed": "take the fastest eligible arm by median step_seconds; adopt it only if its median <= "
                     f"{RULE['median_ratio_max']} x S median and its max <= {RULE['max_ratio_max']} x S fastest, "
                     "compared as exact ratios (rounded for display only); otherwise reject (no fall-through to a "
                     "slower arm)",
            "unpooled_preference": f"if the adopted arm is P3 (L4), take P3F (L4F) when it is eligible, meets the "
                                   f"speed rule and its median is <= {RULE['unpooled_within']} x the pooled median "
                                   "(exact ratio)",
            "id_mapping": "the inventories differ only by the prefix " + repr(B1_PREFIX) + f" on exactly the "
                          f"{B1_IDS} base ids of the six B1 classes, as a bijection; otherwise every OS gets "
                          "no verdict",
            "every_os": "every OS of the preregistration is listed in verdicts; one without any run directory "
                        "gets no verdict (reason: no run directory)",
        },
        "inputs": {"inventory_base": {"count": len(base), "sha256": sha256_of(base_path)},
                   "inventory_trial": {"count": len(trial), "sha256": sha256_of(trial_path)},
                   "control_expectations_sha256": sha256_of(expectations_path),
                   "frozen_checkout_sha": frozen, "checkout_shas_seen": sorted(k for k in shas if k),
                   "ignored_entries": ignored},
        "id_mapping": mapping,
        "runs": [run_summary(run) for run in runs if run.kind == "arm"],
        "controls": control_items,
        "verdicts": verdicts,
    }


def summary_markdown(result: dict) -> str:
    def number(value, digits=1):
        return "-" if value is None else (f"{value:.{digits}f}" if isinstance(value, float) else str(value))

    lines = ["### Suite-parallelism oracle (compare.py)", "",
             "| OS | Arm | Runs | Eligible runs | Median s | Min s | Max s | Median / S median | Max / S fastest "
             "| Controls | Crash | Arm eligible |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for os_name, verdict in result["verdicts"].items():
        for arm, entry in verdict["arms"].items():
            stats = entry["timing"] or {}
            lines.append(f"| {os_name} | {arm} | {entry['runs']} | {entry['eligible_runs']} | "
                         f"{number(stats.get('median'))} | {number(stats.get('min'))} | {number(stats.get('max'))} | "
                         f"{number(entry.get('median_vs_s_median'), 3)} | {number(entry.get('max_vs_s_fastest'), 3)} | "
                         f"{number(entry['controls_passed'])} | {number(entry['crash_passed'])} | "
                         f"{'yes' if entry['eligible'] else 'no'} |")
    lines.append("")
    for os_name, verdict in result["verdicts"].items():
        reasons = "; ".join(verdict["reasons"])
        lines.append(f"- **{os_name}**: {verdict['outcome']}"
                     f"{' ' + verdict['selected_arm'] if verdict['selected_arm'] else ''}"
                     f"{' (' + reasons + ')' if reasons else ''}; flaky ids in S: "
                     f"{verdict['baseline']['flaky_total']}")
    mapping = result["id_mapping"]
    lines.append(f"- id mapping: {'ok' if mapping['ok'] else 'FAILED, so no OS gets a verdict'} "
                 f"({mapping['mapped']} ids, {len(mapping['classes'])} classes rewritten)")
    bad = [run["name"] for run in result["runs"] if not run["eligible"]]
    lines.append(f"- ineligible arm-runs: {', '.join(bad) if bad else 'none'}")
    failed = [item["name"] for item in result["controls"] if not item["passed"]]
    lines.append(f"- failed control runs: {', '.join(failed) if failed else 'none'}")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--results", required=True, type=Path)
    parser.add_argument("--inventory-base", required=True, type=Path)
    parser.add_argument("--inventory-trial", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--summary-md", type=Path)
    parser.add_argument("--expectations", type=Path, default=DEFAULT_EXPECTATIONS)
    parser.add_argument("--min-repeats", type=int, default=RULE["min_repeats"])
    parser.add_argument("--expected-sha", help="the frozen corpus SHA (default: the most common checkout_sha)")
    args = parser.parse_args(argv)
    try:
        result = build_result(args.results, args.inventory_base, args.inventory_trial, args.expectations,
                              args.min_repeats, args.expected_sha)
    except InputError as error:
        print(f"compare.py: {error}", file=sys.stderr)
        return 2
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    if args.summary_md:
        args.summary_md.write_text(summary_markdown(result), encoding="utf-8")
    for os_name, verdict in result["verdicts"].items():
        print(f"{os_name}: {verdict['outcome']} {verdict['selected_arm'] or ''}".rstrip())
    return 0


if __name__ == "__main__":
    sys.exit(main())
