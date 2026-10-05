"""Architecture citations identify current pin fields, independent of edition drift.

The component walk follows the coordinator's fix_pin_source.py reference.
Unlike build_ecosystem.py's path/bounds check, this checks the named record.
"""

import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
CATALOG = "catalogs/foundation/new-wsl-architecture-20261001.json"


class ArchitecturePinSourceTests(unittest.TestCase):
    def test_stack_citations_point_to_the_named_component_pin(self):
        stack_text = (ROOT / "manifests/stack.json").read_text(encoding="utf-8")
        stack = json.loads(stack_text)
        lines = stack_text.splitlines()
        pin_lines = {}
        for collection, field in (("components", "version"), ("models", "revision")):
            for record in stack[collection]:
                if field not in record:
                    continue
                identity = re.compile(r'(\s*)"id":\s*' + re.escape(json.dumps(record["id"])) + r",?")
                starts = [(index, identity.fullmatch(line)) for index, line in enumerate(lines)
                          if identity.fullmatch(line)]
                self.assertEqual(len(starts), 1, record["id"])
                start, match = starts[0]
                indent = match[1]
                end = next((index for index in range(start + 1, len(lines))
                            if lines[index].strip() and not lines[index].startswith(indent)), len(lines))
                fields = [index for index in range(start + 1, end)
                          if lines[index].startswith(indent + json.dumps(field) + ":")]
                self.assertEqual(len(fields), 1, (record["id"], field))
                index = fields[0]
                value = json.loads("{" + lines[index].strip().rstrip(",") + "}")[field]
                self.assertEqual(value, record[field], record["id"])
                pin_lines[record["id"]] = index + 1

        catalog = json.loads((ROOT / CATALOG).read_text(encoding="utf-8"))
        checked = 0
        for row in catalog["rows"]:
            for winner in row["winners"]:
                source = winner["pin_source"]
                if not source.startswith("manifests/stack.json:"):
                    continue
                component = winner.get("component_id")
                if component is None:
                    models = [model["id"] for model in stack["models"]
                              if winner.get("repository") == "https://huggingface.co/" + model["id"]]
                    self.assertEqual(len(models), 1, winner.get("name"))
                    component = models[0]
                with self.subTest(row=row["layer_id"], component=component):
                    self.assertIn(component, pin_lines)
                    self.assertEqual(source, f"manifests/stack.json:{pin_lines[component]}",
                                     "citation must identify the named component's version or model revision")
                checked += 1
        self.assertGreater(checked, 0, "the architecture must exercise stack citations")


if __name__ == "__main__":
    unittest.main()
