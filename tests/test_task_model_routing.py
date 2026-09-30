"""The task-to-model routing record against the files it names as enforcement points.

docs/decisions/2026-09-30-task-model-routing.md maps each task class to a client, a model, an effort and the place that
enforces the assignment today. These are integration checks of the repository's own record against its own files, not
upstream acceptance and not a model run. Every value the record's table quotes from a file ("`path:line` says `value`")
must still be on the cited lines, and every other `path:line` the table cites must exist, so a change to an agent's
frontmatter, a settings template key, a Codex profile or a lane constant fails here until the record is restated.
GPT-6.1 Sol stays listed only as pending qualification, with no route in any routing file.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / "docs" / "decisions" / "2026-09-30-task-model-routing.md"
POINTER = ROOT / "docs" / "token-practice.md"
SECTIONS = ["Context", "Alternatives", "Decision", "Overturn condition", "Sources"]
HEADER = ["Task class", "Client", "Model", "Effort", "Enforced today", "Rule source"]
# The task classes the routing brief names (research split into breadth and judgment, building split by whether a
# written contract's tests exist), matched case-insensitively against the table's first column.
TASK_CLASSES = ("coordinator", "design", "research, first-pass breadth", "research, judgment",
                "build with a written contract's tests", "build without a written contract's tests",
                "review from source", "security review", "verification", "adjudication", "synthesis",
                "exact extraction", "command wrappers", "cross-family review", "sweep", "mechanical",
                "interactive codex")
EXTENSIONS = r"(?:md|json|toml|py|js|mjs|sh|yml)"
CITE = re.compile(rf"`([\w./-]+\.{EXTENSIONS}):(\d+(?:-\d+)?(?:,\d+(?:-\d+)?)*)`")
# A quoted value runs from "says" to the next ";" or the end of the cell, one or more backticked strings.
SAYS = re.compile(rf"`([\w./-]+\.{EXTENSIONS}):(\d+)(?:-(\d+))?` says ([^;]+)")
PENDING = "pending unit D4 qualification (Codex >= 0.159.x pin)"
ROUTING_PLACES = (".claude/agents", "adoption/templates", "tools/adoption", "tools/sota-convergence/landscape-sweep",
                  "examples/claude-native/workflows")


def table(text: str) -> tuple[list[str], list[list[str]]]:
    section = text.split("\n## Decision\n", 1)[1].split("\n## ", 1)[0]
    header, _separator, *body = [line for line in section.splitlines() if line.startswith("|")]

    def cells(row: str) -> list[str]:
        return [cell.strip() for cell in row.strip().strip("|").split(" | ")]

    return cells(header), [cells(row) for row in body]


def lines(path: str) -> list[str]:
    return (ROOT / path).read_text(encoding="utf-8").splitlines()


class TaskModelRoutingRecordTests(unittest.TestCase):
    def setUp(self):
        self.text = RECORD.read_text(encoding="utf-8")
        self.header, self.rows = table(self.text)

    def test_the_record_has_its_sections_and_one_table(self):
        self.assertEqual(re.findall(r"^## (.+)$", self.text, flags=re.M), SECTIONS)
        self.assertEqual(len(re.findall(r"^\| *---", self.text, flags=re.M)), 1, "one table")
        self.assertEqual(self.header, HEADER)
        self.assertTrue(all(len(row) == len(HEADER) for row in self.rows), [row[0] for row in self.rows])

    def test_the_table_covers_every_task_class(self):
        classes = [row[0].lower() for row in self.rows]
        for wanted in TASK_CLASSES:
            with self.subTest(task_class=wanted):
                self.assertTrue(any(wanted in name for name in classes), classes)

    def test_every_quoted_value_is_on_its_cited_lines(self):
        checked = 0
        for row in self.rows:
            for path, first, last, said in SAYS.findall(row[4]):
                quotes = re.findall(r"`([^`]+)`", said)
                span = "\n".join(lines(path)[int(first) - 1:int(last or first)])
                self.assertTrue(quotes, f"{row[0]}: {path}:{first} quotes nothing")
                for quote in quotes:
                    with self.subTest(row=row[0], cited=f"{path}:{first}", quote=quote):
                        self.assertIn(quote, span)
                    checked += 1
        self.assertGreaterEqual(checked, 30, "the table quotes its enforcement points")

    def test_every_cited_line_exists(self):
        cited = 0
        for row in self.rows:
            for path, spans in CITE.findall(" ".join(row)):
                self.assertTrue((ROOT / path).is_file(), f"{row[0]}: {path} is missing")
                for span in spans.split(","):
                    cited += 1
                    self.assertLessEqual(int(span.split("-")[-1]), len(lines(path)), f"{row[0]}: {path}:{span}")
        self.assertGreaterEqual(cited, 60)

    def test_a_frontmatter_row_names_the_model_it_quotes(self):
        rows = [row for row in self.rows if row[4].startswith("**Agent frontmatter**")]
        self.assertGreaterEqual(len(rows), 8)
        for row in rows:
            with self.subTest(row=row[0]):
                alias = re.search(r"`(opus|sonnet)`", row[2])
                quoted = re.search(r"`model: (\w+)`", row[4])
                self.assertTrue(alias and quoted)
                self.assertEqual(alias.group(1), quoted.group(1))
                self.assertEqual(row[3], "max")

    def test_gpt_6_1_sol_is_listed_only_as_pending_and_routed_nowhere(self):
        [row] = [row for row in self.rows if "gpt-6.1" in " ".join(row)]
        self.assertEqual((row[2], row[3], row[4]), ("`gpt-6.1-sol`", "n/a", PENDING))
        for place in ROUTING_PLACES:
            for path in sorted((ROOT / place).rglob("*")):
                if path.is_file():
                    with self.subTest(path=path.relative_to(ROOT).as_posix()):
                        self.assertNotIn("gpt-6.1", path.read_text(encoding="utf-8", errors="replace"))

    def test_token_practice_points_to_the_record(self):
        self.assertIn("](decisions/2026-09-30-task-model-routing.md)", POINTER.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
