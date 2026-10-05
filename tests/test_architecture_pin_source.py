"""Architecture citations identify named pin fields, independent of edition drift.

Reuse scripts/build_ecosystem.py's locator validation (native-agent-stack at
95cf94ca4); check the cited content against the winner's identity as well.
"""

import json
from pathlib import Path
import re
import tempfile
import unittest

from scripts.build_ecosystem import architecture_pin_source


ROOT = Path(__file__).resolve().parents[1]
CATALOG = "catalogs/foundation/new-wsl-architecture-20261001.json"
ROUND2_DECISION = "docs/decisions/2026-10-04-final-architecture-round2.md"


def record_fields(lines, identity_key, identity_value):
    """Scalar sibling fields of each named JSON record, with one-based lines."""
    identity = re.compile(r'(\s*)' + re.escape(json.dumps(identity_key)) + r':\s*'
                          + re.escape(json.dumps(identity_value)) + r",?")
    for start, line in enumerate(lines):
        match = identity.fullmatch(line)
        if match is None:
            continue
        indent = match[1]
        first = start
        while first > 0 and lines[first - 1].startswith(indent):
            first -= 1
        end = start + 1
        while end < len(lines) and lines[end].startswith(indent):
            end += 1
        fields = {}
        for index in range(first, end):
            if not re.match(re.escape(indent) + r'"[^"\\]+":', lines[index]):
                continue
            try:
                value = json.loads("{" + lines[index].strip().rstrip(",") + "}")
            except json.JSONDecodeError:
                continue  # A multiline object or array is not a pin field.
            key, value = next(iter(value.items()))
            fields[key] = (index + 1, value)
        yield fields


def expected_ranges(root, path, winner):
    """Resolve the named source contract without consulting its stored locator."""
    lines = (root / path).read_text(encoding="utf-8").splitlines()
    repository = winner["repository"]
    source_repo = repository.removeprefix("https://github.com/")
    pin = winner["pin"]
    if path == ROUND2_DECISION:
        ranges = set()
        for index, line in enumerate(lines):
            cells = [cell.strip() for cell in line.split("|")]
            if len(cells) != 8 or cells[0] or cells[-1] or cells[4] != repository:
                continue
            owner = cells[3]
            if (re.match(re.escape(winner["name"]) + r"(?=\s|$)", owner)
                    and re.search(r"(?<![\w.+-])" + re.escape(pin) + r"(?![\w.+-])", owner)):
                ranges.add((index + 1, index + 1))
        return ranges
    if path == "manifests/stack.json":
        stack = json.loads("\n".join(lines))
        component = winner.get("component_id")
        field = "version"
        records = stack["components"]
        if component is None:
            records = [model for model in stack["models"]
                       if repository == "https://huggingface.co/" + model["id"]]
            if len(records) != 1:
                raise AssertionError(f"unknown model: {repository}")
            component, field = records[0]["id"], "revision"
        record = next(record for record in records if record["id"] == component)
        fields, = record_fields(lines, "id", component)
        if fields[field][1] != record[field]:
            raise AssertionError(f"wrong pin field: {component}")
        return {(fields[field][0], fields[field][0])}
    if path == "adoption/sdk/accepted-constraints.txt":
        package = pin.split("==", 1)[0]
        packages = (package, package + "-cli-bin")
        entries = []
        for name in packages:
            matches = [(index + 1, line.split("==", 1)[1])
                       for index, line in enumerate(lines) if line.startswith(name + "==")]
            entry, = matches
            entries.append(entry)
        if entries[0][1] != entries[1][1]:
            raise AssertionError("SDK and bundled CLI constraints must be paired")
        return {(entries[0][0], entries[1][0])}
    if path == "adoption/platforms/linux-wsl2-new-distro.md":
        digest = pin.removeprefix("sha256 ")
        release = repository.rstrip("/").rsplit("/", 1)[1]
        return {(index + 1, index + 1) for index, line in enumerate(lines)
                if digest in line and f"ubuntu-{release}-wsl-amd64.wsl" in line}
    if path in {CATALOG, "evidence/receipts/guard-k4-verification-20261001.json"}:
        key = "base_commit" if path == CATALOG else "guard_sha256"
        return {(fields[key][0], fields[key][0]) for fields in record_fields(lines, key, pin)}

    if path == "adoption/skills/manifest.json":
        identity, value, keys = "source", source_repo, ("ref",)
    elif path == "blueprints/runtime-workers/openhands/pins.json":
        identity, value, keys = "repository", repository, ("tag",)
    elif path == "adoption/pins-linux-x86_64.json":
        slug = source_repo.rsplit("/", 1)[1]
        identity, value, keys = "id", {"cli": "gh"}.get(slug, slug), ("version",)
    elif path == "catalogs/foundation/automation.json":
        identity, value = "repository", source_repo
        keys = ("version", "revision") if " @ " in pin else ("version", "archive_sha256")
    elif path == "catalogs/landscape/us-equities.json":
        identity, value, keys = "repository", repository, ("pin",)
    elif path == "catalogs/us-equities/runtime-target.json":
        if winner["component_id"] == "nautilus-trader":
            identity, value, keys = "repository", repository, ("requested_version",)
        elif winner["component_id"] == "alpaca-py":
            identity, value, keys = "id", "alpaca", ("selected_path",)
        else:
            raise AssertionError(f"unknown runtime component: {winner['component_id']}")
    else:
        raise AssertionError(f"uncovered pin_source file: {path}")

    ranges = set()
    for fields in record_fields(lines, identity, value):
        if not all(key in fields for key in keys):
            continue
        if keys == ("pin",):
            version = re.search(r"v?\d+(?:\.\d+)+(?:rc\d+)?", pin)[0].removeprefix("v")
            if not re.search(r"(?<![\d.])" + re.escape(version) + r"(?![\d.])", fields["pin"][1]):
                continue
            ranges.add((fields["component_id"][0], fields["why_selected"][0]))
        else:
            values = [str(fields[key][1]) for key in keys]
            if keys == ("selected_path",):
                if not re.search(re.escape(winner["component_id"]) + r'\s*'
                                 + re.escape(pin) + r'(?![\d.])', values[0]):
                    continue
            elif not all(value in pin for value in values):
                continue
            indices = [fields[key][0] for key in keys]
            if path == "catalogs/foundation/automation.json":
                indices.append(fields["repository"][0])
            ranges.add((min(indices), max(indices)))
            if "archive_sha256" in keys and fields["source"][1].startswith(
                    f"{repository}/releases/download/v{fields['version'][1]}/"):
                ranges.add((min(indices), fields["source"][0]))
    return ranges


class ArchitecturePinSourceTests(unittest.TestCase):
    def test_decision_table_requires_owner_repository_and_exact_pin(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / ROUND2_DECISION).parent.mkdir(parents=True)
            repository = "https://github.com/example/tool"
            winner = {"name": "Example Tool", "repository": repository, "pin": "1.2.3"}
            for owner, source, accepted in (
                    ("Example Tool 1.2.3 (selected)", repository, True),
                    ("Example Tool (CLI; 1.2.3 until 1.2.4 clears cooldown)", repository, True),
                    ("Other Tool 1.2.3", repository, False),
                    ("Example Tools 1.2.3", repository, False),
                    ("Example Tool 1.2.3", "https://github.com/example/other", False),
                    ("Example Tool 1.2.4", repository, False),
                    ("Example Tool 1.2.30", repository, False),
                    ("Example Tool 1.2.3-rc1", repository, False)):
                with self.subTest(owner=owner, repository=source):
                    text = ("# Decision\n\n"
                            f"| `slot` | new row | {owner} | {source} | verified | "
                            "Compare Example Tool 1.2.3 |\n")
                    (root / ROUND2_DECISION).write_text(text, encoding="utf-8")
                    self.assertEqual(expected_ranges(root, ROUND2_DECISION, winner),
                                     {(3, 3)} if accepted else set())
                    self.assertNotIn((2, 2), expected_ranges(root, ROUND2_DECISION, winner))

    def test_all_line_citations_identify_the_winners_pin_fields(self):
        catalog = json.loads((ROOT / CATALOG).read_text(encoding="utf-8"))
        cells = [winner for row in catalog["rows"] for winner in row["winners"]]
        line_cells = sum(bool(re.search(r":\d+(?:-\d+)?$", winner["pin_source"])) for winner in cells)
        checked = 0
        for row in catalog["rows"]:
            for winner in row["winners"]:
                citation = architecture_pin_source(winner["pin_source"], ROOT,
                                                    lambda path: {"path": path, "url": path})
                anchor = citation["url"].partition("#L")[2]
                if not anchor:
                    continue
                first, _, last = anchor.partition("-L")
                actual = (int(first), int(last or first))
                with self.subTest(row=row["layer_id"], component=winner.get("component_id", winner.get("name"))):
                    expected = expected_ranges(ROOT, citation["path"], winner)
                    self.assertTrue(expected, "no pin field matches the winner's identity and pin")
                    self.assertIn(actual, expected,
                                  f"{winner['pin_source']} must identify the named pin fields")
                checked += 1
        self.assertGreater(line_cells, 0, "the architecture must exercise line citations")
        self.assertEqual(checked, line_cells, "every line-bearing pin_source must be checked")

    def test_delimiter_and_another_components_identical_version_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "manifests").mkdir()
            text = json.dumps({"components": [{"id": "target", "version": "1.0"},
                                               {"id": "other", "version": "1.0"}],
                               "models": []}, indent=2)
            (root / "manifests/stack.json").write_text(text, encoding="utf-8")
            winner = {"component_id": "target", "repository": "https://github.com/example/target",
                      "pin": "1.0"}
            ranges = expected_ranges(root, "manifests/stack.json", winner)
            other, = record_fields(text.splitlines(), "id", "other")
            wrong_line = other["version"][0]
            delimiter = next(index + 1 for index, line in enumerate(text.splitlines())
                             if line.strip() == "},")
            self.assertNotIn((wrong_line, wrong_line), ranges)
            self.assertNotIn((delimiter, delimiter), ranges)

    def test_alpaca_selected_path_accepts_whitespace_but_rejects_other_versions(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = "catalogs/us-equities/runtime-target.json"
            (root / path).parent.mkdir(parents=True)
            winner = {"component_id": "alpaca-py", "repository": "https://github.com/alpacahq/alpaca-py",
                      "pin": "0.44.0"}
            for description, accepted in (("Official alpaca-py0.44.0 for ingestion", True),
                                          ("Official alpaca-py 0.44.0 for ingestion", True),
                                          ("Official alpaca-py\t0.44.0 for ingestion", True),
                                          ("Official alpaca-py 0.45.0 for ingestion", False),
                                          ("Official alpaca-py 0.44.01 for ingestion", False),
                                          ("Official alpaca-py 0.44.0.1 for ingestion", False)):
                with self.subTest(description=description):
                    text = json.dumps({"brokers": [{"id": "alpaca", "selected_path": description}]}, indent=2)
                    (root / path).write_text(text, encoding="utf-8")
                    ranges = expected_ranges(root, path, winner)
                    self.assertEqual(ranges, {(5, 5)} if accepted else set())
                    self.assertNotIn((6, 6), ranges, "the closing delimiter is not a pin field")


if __name__ == "__main__":
    unittest.main()
