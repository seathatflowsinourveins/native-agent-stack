"""A6b/T22: ratchet reviewed legacy-port lines, without rewriting history.

Sources: git/git@v2.53.0:Documentation/git-grep.adoc (tracked worktree,
binary exclusion, NUL path delimiters and pathspecs); reviewed gateway plan
revision 3.1 / changeset-github-ci-finalize.md, A6b and T22. These are
repository integration controls, not a gateway or upstream acceptance run.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ALLOWLIST = ROOT / "tests/legacy_gateway_ports_allow.json"
GREP_PATTERN = r"(^|[^0-9])2012[89]([^0-9]|$)"
LINE_PATTERN = re.compile(r"(?<![0-9])2012[89](?![0-9])")
SCOPES = (
    (".", ":!evidence/**", ":!manifests/**", ":!tests/**"),
    ("evidence/artifacts/new-wsl-install-plan-20261002/",),
)
KEPT_CLASSES = {
    "history", "fixture", "server-listen", "nativestack-era",
    "guard-table", "template-match",
}
REVIEWED_ROWS = {
    "A0", "A1", "A2", "A3", "A4", "A5", "A6", "A6b", "A6c",
    "A7", "A8", "A9", "A10", "A11", "A12",
    "B1", "B2", "B3", "B4", "B5", "B6", "B7",
    "C0", "C1", "C2", "C3", "C3b", "C4", "C5", "C6", "C7",
    "E1a", "E1b", "E1c", "E1d", "E1e",
    "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10",
}


def line_key(path: str, text: str) -> tuple[str, str]:
    return path, hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


def parse_hits(output: str) -> set[tuple[str, str]]:
    """Git -z separates the verbatim path and line number with NULs."""
    hits: set[tuple[str, str]] = set()
    cursor = 0
    while cursor < len(output):
        path_end = output.find("\0", cursor)
        number_end = output.find("\0", path_end + 1)
        if path_end < 0 or number_end < 0:
            raise ValueError("git grep did not return NUL-delimited paths")
        path = output[cursor:path_end]
        int(output[path_end + 1:number_end])
        text_end = output.find("\n", number_end + 1)
        if text_end < 0:
            text_end = len(output)
        text = output[number_end + 1:text_end]
        if not path or not LINE_PATTERN.search(text):
            raise ValueError("git grep returned a malformed legacy-port hit")
        hits.add(line_key(path, text))
        cursor = text_end + 1
    return hits


def tracked_hits(root: Path, *, run=subprocess.run) -> set[tuple[str, str]]:
    hits: set[tuple[str, str]] = set()
    # An exclude pathspec beats an include; the living plan needs its own scan.
    for scope in SCOPES:
        result = run(
            ["git", "grep", "--no-color", "-n", "-I", "-z", "-E",
             GREP_PATTERN, "--", *scope],
            cwd=root, text=True, capture_output=True, check=False,
        )
        if result.returncode not in (0, 1):
            raise RuntimeError("git grep failed with exit " + str(result.returncode))
        hits.update(parse_hits(result.stdout))
    return hits


def reviewed_keys(document: dict) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    for entry in document["entries"]:
        path, digest, category, reason = (
            entry["path"], entry["sha256"], entry["class"], entry["reason"]
        )
        if not isinstance(path, str) or not path or Path(path).is_absolute():
            raise ValueError("allowance needs a repository-relative path")
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("allowance needs the stripped line's SHA-256")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("allowance needs a reviewed reason")
        if category not in KEPT_CLASSES:
            if not isinstance(category, str) or not category.startswith("pending-"):
                raise ValueError("unreviewed allowance class")
            row = category.removeprefix("pending-")
            if row not in REVIEWED_ROWS or not re.search(r"\b" + re.escape(row) + r"\b", reason):
                raise ValueError("pending allowance must name its reviewed change row")
        key = path, digest
        if key in keys:
            raise ValueError("duplicate allowance")
        keys.add(key)
    return keys


def differences(hits, allowed):
    return hits - allowed, allowed - hits


def report_stale(stale, stream):
    for path, digest in sorted(stale):
        print("STALE legacy gateway allowance: " + path + " sha256=" + digest, file=stream)


class LegacyGatewayPortRatchetTests(unittest.TestCase):
    def test_tracked_lines_have_reviewed_allowances(self):
        document = json.loads(ALLOWLIST.read_text(encoding="utf-8"))
        allowed = reviewed_keys(document)
        new, stale = differences(tracked_hits(ROOT), allowed)
        output = io.StringIO()
        report_stale(stale, output)
        if output.tell():
            print(output.getvalue(), end="")
        self.assertFalse(
            new,
            "New or changed legacy gateway lines need review: "
            + "; ".join(path + " sha256=" + digest for path, digest in sorted(new)),
        )

    def test_changed_line_and_new_path_fail_the_ratchet(self):
        original = line_key("docs/retained.md", "old gateway 20128")
        changed = line_key("docs/retained.md", "new default 20128")
        other_path = line_key("tools/new-worker.py", "old gateway 20128")
        new, stale = differences({changed, other_path}, {original})
        self.assertEqual(new, {changed, other_path})
        self.assertEqual(stale, {original})

    def test_removal_only_reports_stale_allowance(self):
        original = line_key("docs/retained.md", "old gateway 20129")
        new, stale = differences(set(), {original})
        self.assertEqual(new, set())
        output = io.StringIO()
        report_stale(stale, output)
        self.assertIn("STALE", output.getvalue())
        self.assertIn(original[1], output.getvalue())

    def test_union_keeps_live_plan_and_handles_verbatim_paths(self):
        first = "docs/a:name.md\0" + "7\0old gateway 20128\n"
        second = "evidence/artifacts/new-wsl-install-plan-20261002/config/live.py\0" + "2\0gateway 20129\n"
        calls = []

        def run(argv, **kwargs):
            calls.append(argv)
            return subprocess.CompletedProcess(argv, 0, first if len(calls) == 1 else second)

        hits = tracked_hits(ROOT, run=run)
        self.assertEqual(hits, parse_hits(first) | parse_hits(second))
        self.assertEqual(len(hits), 2)
        self.assertIn(":!evidence/**", calls[0])
        self.assertNotIn(":!evidence/**", calls[1])
        self.assertEqual(calls[1][-1], SCOPES[1][0])

    def test_pending_class_requires_a_specific_reviewed_row(self):
        entry = {"path": "tools/worker.py", "sha256": "a" * 64,
                 "class": "pending-F2", "reason": "PLAN row F2 replaces this holder"}
        self.assertEqual(reviewed_keys({"entries": [entry]}), {(entry["path"], entry["sha256"])})
        for category in ("pending-unknown", "pending-F999", "pending-"):
            with self.subTest(category=category), self.assertRaises(ValueError):
                reviewed_keys({"entries": [{**entry, "class": category}]})

    def test_outside_digit_boundaries_are_not_gateway_ports(self):
        for value in ("120128", "201289", "9201290"):
            with self.subTest(value=value):
                self.assertIsNone(LINE_PATTERN.search(value))
