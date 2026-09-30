"""The task-to-model routing record against the files it names as enforcement points.

docs/decisions/2026-09-30-task-model-routing.md maps each task class to a client, a model, an effort and the place that
enforces the assignment today. These are integration checks of the repository's own record against its own files, not
upstream acceptance and not a model run. Every value the record's table quotes from a file ("`path:line` says `value`")
must still be in that file as a whole value, not as the tail or head of a longer name, at least once for each distinct
line the table quotes it from, and every `path:line` the table cites must exist. The record reads its line numbers at
the revisions it names, so an edit that only moves a quoted value passes here, while a change to an agent's
frontmatter, a settings template key, a Codex profile or a lane constant fails until the record is restated.
GPT-6.1 Sol is routed where the Sol-primary routing record of unit D4 (#542) routes it and nowhere else: the table's
Sol rows are the Codex coordinator, the primary workers and the generic children, the Codex user template renders on
each pinned platform the model the coordinator row names for it, and every routing file that binds a GPT-6.1 model is
cited by a Sol row. A mention in prose is not a binding.
"""

from __future__ import annotations

import importlib.util
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / "docs" / "decisions" / "2026-09-30-task-model-routing.md"
POINTER = ROOT / "docs" / "token-practice.md"
MANIFEST = ROOT / "adoption" / "manifest.json"
FOUNDATION = ROOT / "catalogs" / "landscape" / "foundation.json"
CARRIER = ROOT / "adoption" / "hooks" / "claude" / "token-lanes-block.md"
PIN_FILES = ("adoption/pins-linux-x86_64.json", "adoption/pins-macos-arm64.json")
# The three code-navigation tools the record's Decision leaves outside the token-efficiency profile: the SubagentStart
# carrier's task-appended lanes (jCodeMunch and codebase-memory by tool id, ast-grep as a command) and the
# code-navigation layer's current choice, installed on demand until each has a reviewed pin on both platforms.
CARRIER_TOOLS = ("jcodemunch-mcp", "codebase-memory-mcp", "ast-grep")
CARRIER_LANES = ("mcp__jcodemunch__route", "mcp__jcodemunch__menu", "mcp__jcodemunch__order",
                 "mcp__codebase-memory__search_graph", "mcp__codebase-memory__trace_path")
SECTIONS = ["Context", "Alternatives", "Decision", "Overturn condition", "Sources"]
HEADER = ["Task class", "Client", "Model", "Effort", "Enforced today", "Rule source"]
# The task classes the routing brief names (research split into breadth and judgment, building split by whether a
# written contract's tests exist), matched case-insensitively against the table's first column, and the two Astra
# classes the Sol-primary routing record adds (a complex workflow's coordination, a single consequential judgment).
TASK_CLASSES = ("coordinator", "design", "research, first-pass breadth", "research, judgment",
                "build with a written contract's tests", "build without a written contract's tests",
                "review from source", "security review", "verification", "adjudication", "synthesis",
                "exact extraction", "command wrappers", "cross-family review", "sweep", "mechanical",
                "interactive codex", "complex-workflow", "consequential judgment")
EXTENSIONS = r"(?:md|json|toml|py|js|mjs|sh|yml)"
CITE = re.compile(rf"`([\w./-]+\.{EXTENSIONS}):(\d+(?:-\d+)?(?:,\d+(?:-\d+)?)*)`")
# A quoted value runs from "says" to the next ";" or the end of the cell, one or more backticked strings.
SAYS = re.compile(rf"`([\w./-]+\.{EXTENSIONS}):(\d+)(?:-(\d+))?` says ([^;]+)")
# GPT-6.1 Sol's routes as docs/decisions/2026-09-30-sol-primary-quality-defaults.md sets them: Sol/Ultra coordinates
# Codex, and Sol/Max runs the primary workers and the generic children. Each key is part of one row's task class, and
# the value is the effort that row names.
SOL_ROUTES = {"interactive codex": "ultra", "primary codex workers": "max", "generic codex children": "max"}
USER_TEMPLATE = "adoption/templates/codex.config.template.toml"
PLACEHOLDER = "${CODEX_MODEL}"
RENDER_CONFIG = ROOT / "tools" / "adoption" / "render_config.py"
# The coordinator row's statement of what the user template renders on one platform: "`<platform>` renders `<model>`".
RENDERS = re.compile(r"`([a-z0-9]+-[a-z0-9_]+)` renders `([\w.-]+)`")
ROUTING_PLACES = (".claude/agents", "adoption/agents", "adoption/templates", "tools/adoption",
                  "tools/sota-convergence/landscape-sweep", "examples/claude-native/workflows", "recipes")
# Generated folders are not routing files. A full test run leaves tools/adoption/__pycache__/prove_codex_lane.*.pyc,
# whose bytecode carries the module's help text, `-m gpt-6.1-sol` included (the `validate` job of #540, 2026-09-30).
GENERATED = {"__pycache__", "node_modules"}
# A model binding of GPT-6.1: a model key or constant assigned the ID (TOML, JSON, YAML, Python, JavaScript, including
# a constant whose name continues past "model", such as CODEX_MODEL_CURRENT) or a CLI model flag, with an optional
# gateway prefix such as `cx/`.
BINDS_GPT_6_1 = re.compile(r"""(?:model\w*["'`]?\s*[:=]\s*["'`]?|(?<![\w-])-m\s+["'`]?|--model(?:\s+|=)["'`]?)"""
                           r"""(?:[\w.-]+/)?gpt-6\.1""", re.IGNORECASE)


def table(text: str) -> tuple[list[str], list[list[str]]]:
    section = text.split("\n## Decision\n", 1)[1].split("\n## ", 1)[0]
    header, _separator, *body = [line for line in section.splitlines() if line.startswith("|")]

    def cells(row: str) -> list[str]:
        return [cell.strip() for cell in row.strip().strip("|").split(" | ")]

    return cells(header), [cells(row) for row in body]


def lines(path: str) -> list[str]:
    return (ROOT / path).read_text(encoding="utf-8").splitlines()


def effort(row: list[str]) -> str:
    """The effort a row names, without the explanation that may follow a colon."""
    return row[3].split(":", 1)[0]


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

    def test_every_quoted_value_is_in_its_cited_file(self):
        # Look each value up in the whole file, once for every distinct line the table quotes it from, so that two
        # stages binding the same value are both held and a sibling change that only moves lines does not fail here.
        # A value counts only as a whole: `model = "${CODEX_MODEL}"` inside `default_subagent_model = "${CODEX_MODEL}"`
        # is not the template's model line.
        cited: dict[tuple[str, str], set[str]] = {}
        for row in self.rows:
            for path, first, last, said in SAYS.findall(row[4]):
                quotes = re.findall(r"`([^`]+)`", said)
                self.assertTrue(quotes, f"{row[0]}: {path}:{first} quotes nothing")
                for quote in quotes:
                    cited.setdefault((path, quote), set()).add(f"{first}-{last or first}")
        self.assertGreaterEqual(sum(map(len, cited.values())), 30, "the table quotes its enforcement points")
        for (path, quote), spans in sorted(cited.items()):
            with self.subTest(cited=path, quote=quote):
                whole = re.compile(rf"(?<![\w.-]){re.escape(quote)}(?![\w.-])")
                found = len(whole.findall((ROOT / path).read_text(encoding="utf-8")))
                self.assertGreaterEqual(found, len(spans), sorted(spans))

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

    def test_gpt_6_1_sol_is_routed_where_the_sol_primary_record_routes_it_and_nowhere_else(self):
        # The table's Sol rows are the record's three routes, each a Codex row at the record's effort.
        sol = [row for row in self.rows if "`gpt-6.1-sol`" in row[2]]
        self.assertEqual(len(sol), len(SOL_ROUTES), [row[0] for row in sol])
        for route, wanted in SOL_ROUTES.items():
            with self.subTest(route=route):
                [row] = [row for row in sol if route in row[0].lower()]
                self.assertEqual((row[1], effort(row)), ("Codex CLI", wanted))
        # Nowhere else: a routing file that binds a GPT-6.1 model is an enforcement point that a Sol row cites. The
        # stack-worker profile's literal binding must be found, so a scan that matches nothing cannot pass.
        bound = set()
        for place in ROUTING_PLACES:
            for path in sorted((ROOT / place).rglob("*")):
                if (path.is_file() and not GENERATED & set(path.relative_to(ROOT).parts)
                        and BINDS_GPT_6_1.search(path.read_text(encoding="utf-8", errors="replace"))):
                    bound.add(path.relative_to(ROOT).as_posix())
        self.assertIn("adoption/templates/codex.stack-worker.config.toml", bound)
        cited = {path for row in sol for path, _spans in CITE.findall(row[4])}
        self.assertEqual(bound - cited, set(), "bound to GPT-6.1 but cited by no Sol row")
        # Each Sol row cites a file that names the model, literally or through the user template's placeholder.
        for row in sol:
            with self.subTest(row=row[0]):
                naming = [path for path, _spans in CITE.findall(row[4])
                          if path in bound or PLACEHOLDER in (ROOT / path).read_text(encoding="utf-8")]
                self.assertTrue(naming, row[4])

    def test_the_user_template_renders_on_each_platform_the_model_its_rows_name(self):
        # The coordinator and generic-children rows quote the template's placeholder lines, while a host runs the
        # render. Render the template through tools/adoption/render_config.py for every platform that has a pin file,
        # as tests/test_render_config.py's CodexModelTests do, and hold both rows to the result.
        import tomllib  # Python 3.11+, as the Codex wiring check already requires

        [coordinator] = [row for row in self.rows if "interactive codex" in row[0].lower()]
        [children] = [row for row in self.rows if "generic codex children" in row[0].lower()]
        stated = dict(RENDERS.findall(coordinator[2]))
        platforms = sorted(path.name[len("pins-"):-len(".json")] for path in (ROOT / "adoption").glob("pins-*.json"))
        self.assertEqual(sorted(stated), platforms)
        spec = importlib.util.spec_from_file_location("render_config_for_the_routing_record", RENDER_CONFIG)
        renderer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(renderer)
        values = {key: f"example-{key.lower()}" for key in renderer.REQUIRED_KEYS}
        for platform_id, model in sorted(stated.items()):
            with self.subTest(platform=platform_id):
                config = tomllib.loads(renderer.render_one(ROOT / USER_TEMPLATE, values, platform_id))
                self.assertEqual((config["model"], config["model_reasoning_effort"]), (model, effort(coordinator)))
                self.assertEqual((config["agents"]["default_subagent_model"],
                                  config["agents"]["default_subagent_reasoning_effort"]), (model, effort(children)))

    def test_the_token_efficiency_profile_is_accepted_by_this_record_and_leaves_the_three_tools_out(self):
        # The Decision's "Profile acceptance" and "Three tools stay outside the profile" paragraphs make claims about
        # adoption/manifest.json, both pin files, the carrier block and the landscape's code-navigation choice: hold
        # them to the files. Versions are not compared: manifests/stack.json owns them and the record dates the ones it
        # quotes at its base revision.
        [profile] = [item for item in json.loads(MANIFEST.read_text(encoding="utf-8"))["profiles"]
                     if item["id"] == "token-efficiency"]
        relative = RECORD.relative_to(ROOT).as_posix()
        self.assertIn("Accepted", profile["label"])
        self.assertNotIn("Drafted", profile["label"])
        self.assertIn(relative, profile["label"])
        self.assertIn(relative, profile["recipe_paths"])
        pinned = {pin_file: {tool["id"] for tool in json.loads((ROOT / pin_file).read_text(encoding="utf-8"))["tools"]}
                  for pin_file in PIN_FILES}
        for tool in CARRIER_TOOLS:
            with self.subTest(tool=tool):
                self.assertNotIn(tool, profile["component_ids"])
                self.assertNotIn(tool, profile["required_commands"])
                self.assertIn(f"`{tool}` ", self.text)
                # The record's reason is that neither pin file has an entry. A pin that arrives meets the record's
                # overturn condition, so the record, the profile and this check are restated together.
                for pin_file, ids in pinned.items():
                    self.assertNotIn(tool, ids, pin_file)
        # Every member the profile does list is pinned on both platforms, which is what the bootstraps require.
        for pin_file, ids in pinned.items():
            self.assertEqual(set(profile["component_ids"]) - ids, set(), pin_file)
        # The record's basis for naming the three: the layer's current choice and the carrier's task-appended lanes.
        layers = json.loads(FOUNDATION.read_text(encoding="utf-8"))["layers"]
        choice = next(layer for layer in layers if layer["layer_id"] == "code-navigation")["current_choice"]
        for name in ("ast-grep", "codebase-memory", "jCodeMunch"):
            self.assertIn(name, choice)
        carrier = CARRIER.read_text(encoding="utf-8")
        for lane in CARRIER_LANES:
            self.assertIn(lane, carrier)

    def test_token_practice_points_to_the_record(self):
        self.assertIn("](decisions/2026-09-30-task-model-routing.md)", POINTER.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
