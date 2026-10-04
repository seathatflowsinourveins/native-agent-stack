"""A4 of the 2026-10-03 Jev rules (blueprints/native-skill-practice/README.md, "Jev rules"): the return schema of the
semantic-evidence-reviewer role and its five copies. Structural checks only; nothing here starts a model.

Codex strict output (`codex exec --output-schema`) needs every object to list all of its properties as required and
to allow no other; the repository's precedent is tools/sota-convergence/adjudication-judge.schema.json. The control
mutates the shipped schema and shows that the strictness check finds both changes.
"""
from __future__ import annotations

import copy
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = "blueprints/native-skill-practice/semantic-evidence-reviewer.schema.json"
COPIES = (".claude/agents/semantic-evidence-reviewer.md", "adoption/agents/claude/semantic-evidence-reviewer.md",
          "examples/claude-native/agents/semantic-evidence-reviewer.md",
          "adoption/agents/codex/workers/semantic-evidence-reviewer.toml",
          "examples/codex-native/agents/semantic-evidence-reviewer.toml")
A4_FIELDS = ("case_id", "final_disposition", "retained_provider_disposition")


def strict_problems(node, where="$") -> list[str]:
    """Where an object schema allows unlisted properties or leaves a listed property optional."""
    problems = []
    if isinstance(node, dict):
        if node.get("type") == "object":
            properties = node.get("properties") or {}
            if node.get("additionalProperties") is not False:
                problems.append(f"{where}: additionalProperties is not false")
            if sorted(node.get("required") or []) != sorted(properties):
                problems.append(f"{where}: required differs from properties")
        for key, value in node.items():
            problems += strict_problems(value, f"{where}.{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            problems += strict_problems(value, f"{where}[{index}]")
    return problems


class ReviewerSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads((ROOT / SCHEMA_PATH).read_text(encoding="utf-8"))
        cls.case = cls.schema["properties"]["cases"]["items"]

    def test_the_schema_is_strict_and_the_control_breaks_it(self):
        self.assertEqual(strict_problems(self.schema), [])
        loose = copy.deepcopy(self.schema)
        loose["properties"]["cases"]["items"]["additionalProperties"] = True
        loose["required"].remove("model")
        self.assertEqual(len(strict_problems(loose)), 2)

    def test_the_a4_fields_and_the_disposition_labels(self):
        for field in A4_FIELDS:
            self.assertIn(field, self.case["properties"])
        labels = re.search(r"const labels = (\[[^\]]*\]);",
                           (ROOT / "blueprints/native-skill-practice/response.cjs").read_text(encoding="utf-8"))
        self.assertEqual(self.case["properties"]["final_disposition"]["enum"], json.loads(labels.group(1).replace("'", '"')))
        self.assertEqual(self.case["properties"]["retained_provider_disposition"]["type"], ["string", "null"])

    def test_every_copy_names_the_schema_and_the_a4_fields(self):
        for path in COPIES:
            text = (ROOT / path).read_text(encoding="utf-8")
            with self.subTest(copy=path):
                self.assertIn(SCHEMA_PATH, text)
                for field in A4_FIELDS:
                    self.assertIn(field, text)
                self.assertIn("agent({agentType, schema})" if path.endswith(".md") else "codex exec --output-schema",
                              text)


if __name__ == "__main__":
    unittest.main()
