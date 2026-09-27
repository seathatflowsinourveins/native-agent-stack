"""The Context Mode practice text stays aligned with the reviewed upstream revision (1.0.169 at 6f0cc684).

Each check pins one practice that the 2026-09-26 context-mode audit settled against the pinned source, so a
later edit cannot silently restore a withdrawn claim: the session handbook's executor and session-store notes
and their link from the tool table; the label on every quoted `ctx_stats` figure (upstream-rendered, not
verified avoidance or provider usage); the two persisted counters in docs/token-practice.md; and the dated
child-hook note in the example workflows README. These are repository-text checks, not a run of Context Mode.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HANDBOOK = ROOT / "docs/token-session-handbook.md"
ANCHOR = "context-mode-executor-and-session-store"
LABEL = "upstream-rendered figure"


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def handbook_section() -> str:
    text = read("docs/token-session-handbook.md")
    return text.split("### Context Mode executor and session store\n", 1)[1].split("\n## ", 1)[0]


class HandbookNotesTests(unittest.TestCase):
    def test_the_tool_table_links_the_notes(self):
        row = next(line for line in read("docs/token-session-handbook.md").splitlines()
                   if line.startswith("| [`context-mode`]"))
        self.assertIn(f"(#{ANCHOR})", row)
        self.assertIn(f"token-session-handbook.md#{ANCHOR}", read("docs/token-practice.md"))

    def test_the_notes_carry_each_settled_practice(self):
        section = handbook_section()
        for phrase in (
            "writes persist",                                   # ctx code runs in a real directory
            "Keep no `Read(...)` allow rules",                  # outside-root files take another route
            "`ctx_index` then `ctx_search`",
            "compared as an exact string",                      # Claude Code never matches the bare `mcp__`
            "`start.mjs`",                                      # Codex: user-scope server, per-session root
            "codex exec -C",
            "Never run `context-mode upgrade` or `ctx_upgrade`",
            "`bash -c",                                          # the batch NODE_OPTIONS prefix
            "recent window",                                    # session memory is not wave continuity
            LABEL,                                              # ctx_stats figures
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, section)
        # Upstream issue numbers are read-only references here; the notes cite the reviewed source.
        self.assertIn("6f0cc684", section)
        self.assertNotRegex(section, r"(?i)\b(?:file|open) an? (?:upstream )?(?:issue|report|pull request)")


class CtxStatsLabelTests(unittest.TestCase):
    def test_every_quoted_ctx_stats_figure_carries_the_label(self):
        row = next(line for line in read("docs/token-session-handbook.md").splitlines()
                   if line.startswith("| Context Mode `ctx_stats({})`"))
        self.assertIn(LABEL, row)
        stack_row = next(line for line in read("docs/token-efficiency-stack.md").splitlines()
                         if line.startswith("| [Context Mode]"))
        self.assertIn(LABEL, stack_row)
        quoted = []

        def walk(node):
            if isinstance(node, dict):
                for key, value in node.items():
                    if key != "value" and isinstance(value, str) and "1.1M" in value:
                        quoted.append(value)
                    walk(value)
            elif isinstance(node, list):
                for item in node:
                    walk(item)

        walk(json.loads(read("docs/token-efficiency-stack.json")))
        self.assertGreaterEqual(len(quoted), 3, quoted)
        for text in quoted:
            with self.subTest(text=text[:60]):
                self.assertIn(LABEL, text)

    def test_token_practice_separates_the_persisted_counters_from_the_rendered_bytes(self):
        text = read("docs/token-practice.md")
        for phrase in ("tokens_saved", "tokens_saved_lifetime", "bytes_avoided",
                       "(bytes_indexed + bytes_sandboxed + cache_bytes_saved) / 4"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)


class ChildHookNoteTests(unittest.TestCase):
    def test_the_example_readme_dates_the_child_hook_behaviour(self):
        text = read("examples/claude-native/workflows/README.md")
        self.assertNotIn("Context Mode has no child hook", text)
        note = next(paragraph for paragraph in text.split("\n\n") if "Context Mode's PreToolUse" in paragraph)
        for phrase in ("2.1.283", "1.0.169", "routing block", "parent's session"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, note)


if __name__ == "__main__":
    unittest.main()
