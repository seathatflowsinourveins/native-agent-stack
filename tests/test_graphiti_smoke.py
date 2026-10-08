"""Offline checks for tools/graphiti-smoke (see the README.md there).

They pin the committed recipe files, keep the README and the three catalog copies of the recipe identical,
and run the smoke script's failure path. Nothing here installs graphiti-core or reaches the network; the live
install, smoke and pip-audit runs are recorded in that README.
"""

from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "graphiti-smoke"

WHEEL_SHA256 = "97674a49514130db175faecf23221ce9338240be3cbe13a7e23e5a5033892b9f"
PIP_AUDIT_WHEEL_SHA256 = "99ef3f600a317c1945f1e89e227ef26e1c2d618429b8bd3fa6f4f7c440c4611a"
REVIEWED_COMMIT = "de8eb5b896c05ed1b5b329d4cb52015446d65e21"
RELEASE_COMMIT = "eaa4128681bc53487138a4bbc22d58336ebe70d2"
LOCK_COMMIT = "86f1c941bea7bf53fa45fe4e08c03244b4990eee"
LOCK_BLOB = "97ae57efc2e1916a0df8b148a5754a7f0f377e2c"
FALKORDB = "falkordb/falkordb:v4.20.7@sha256:13996aa523f0dd283f6bd6df6620b094dcea525452417c4d6ef9bef15dc9998d"
FALKORDB_ROLLBACK = "falkordb/falkordb:v4.20.4@sha256:adbddd418916c25618564ff8597a919b08bc76452ebeb74eb985c38d7281df62"
RECIPE = [
    'uv venv --python 3.13 --no-python-downloads "$GRAPHITI_ENV"',
    'uv pip install --python "$GRAPHITI_ENV/bin/python" --require-hashes --no-build'
    " -r tools/graphiti-smoke/requirements.txt -c tools/graphiti-smoke/graphiti-0.30.2.constraints.txt",
    'uv pip check --python "$GRAPHITI_ENV/bin/python"',
    'uv pip freeze --python "$GRAPHITI_ENV/bin/python" > "$OUT/freeze.txt"',
    'diff tools/graphiti-smoke/expected-freeze.txt "$OUT/freeze.txt"',
    '"$GRAPHITI_ENV/bin/python" -I tools/graphiti-smoke/smoke.py',
    'uvx --from pip-audit==2.10.1 pip-audit --disable-pip --no-deps -s pypi -r "$OUT/freeze.txt"',
    'uvx --from pip-audit==2.10.1 pip-audit --disable-pip --no-deps -s osv -r "$OUT/freeze.txt"',
]
# uv export of getzep/graphiti 86f1c941's uv.lock with --no-dev --extra falkordb (2026-10-07): 34 pins, four of
# them (async-timeout, colorama, exceptiongroup, numpy 2.2.6) behind markers that CPython 3.13 does not select.
CONSTRAINTS = {
    ("annotated-types", "0.7.0"), ("anyio", "4.15.1"), ("async-timeout", "5.0.1"), ("backoff", "2.2.1"),
    ("certifi", "2026.1.4"), ("charset-normalizer", "3.4.4"), ("colorama", "0.4.6"), ("distro", "1.9.0"),
    ("exceptiongroup", "1.3.1"), ("falkordb", "1.4.0"), ("h11", "0.16.0"), ("httpcore", "1.0.9"),
    ("httpx", "0.28.1"), ("idna", "3.18"), ("jiter", "0.12.0"), ("neo4j", "6.1.0"), ("numpy", "2.2.6"),
    ("numpy", "2.4.1"), ("openai", "2.32.0"), ("posthog", "7.5.1"), ("pydantic", "2.12.5"),
    ("pydantic-core", "2.41.5"), ("python-dateutil", "2.9.0.post0"), ("python-dotenv", "1.2.2"),
    ("pytz", "2025.2"), ("redis", "7.1.0"), ("requests", "2.33.0"), ("six", "1.17.0"), ("sniffio", "1.3.1"),
    ("tenacity", "9.1.2"), ("tqdm", "4.67.1"), ("typing-extensions", "4.16.0"), ("typing-inspection", "0.4.2"),
    ("urllib3", "2.8.0"),
}
MARKER_ONLY = {("async-timeout", "5.0.1"), ("colorama", "0.4.6"), ("exceptiongroup", "1.3.1"), ("numpy", "2.2.6")}
FREEZE = (CONSTRAINTS - MARKER_ONLY) | {("graphiti-core", "0.30.2")}

# pip's requirements-file rules: a line ending in a backslash continues unless it is a comment, and a "#" that
# starts a line or follows whitespace starts a comment (https://pip.pypa.io/en/stable/reference/requirements-file-format/).
COMMENT = re.compile(r"(^|\s+)#.*$")
PIN = re.compile(r"([A-Za-z0-9][A-Za-z0-9._-]*)(?:\[[^\]]*\])?==([0-9][0-9A-Za-z.+!-]*)(?:\s*;.*)?")


def logical_lines(text: str) -> list[str]:
    lines, pending = [], ""
    for line in text.splitlines():
        if line.endswith("\\") and not line.lstrip().startswith("#"):
            pending += line[:-1] + " "
            continue
        joined = COMMENT.sub("", pending + line).strip()
        pending = ""
        if joined:
            lines.append(joined)
    return lines


def pin(line: str) -> tuple[str, str]:
    match = PIN.fullmatch(re.split(r"\s+--", line, maxsplit=1)[0].strip())
    if not match:
        raise AssertionError(f"not an exact pin: {line}")
    return match.group(1), match.group(2)


class RecipeFileTests(unittest.TestCase):
    def test_requirements_name_only_the_wheel_by_its_hash(self):
        lines = logical_lines((TOOL / "requirements.txt").read_text(encoding="utf-8"))
        self.assertEqual(lines, [f"graphiti-core[falkordb]==0.30.2 --hash=sha256:{WHEEL_SHA256}"])

    def test_constraints_are_the_hashed_lock_export(self):
        text = (TOOL / "graphiti-0.30.2.constraints.txt").read_text(encoding="utf-8")
        pins = set()
        for line in logical_lines(text):
            hashes = re.findall(r"--hash=(\S+)", line)
            self.assertTrue(hashes and all(re.fullmatch(r"sha256:[0-9a-f]{64}", value) for value in hashes), line)
            pins.add(pin(line))
        self.assertEqual(pins, CONSTRAINTS)
        self.assertFalse(text.startswith("#"), "export with --no-header: the header would carry a local path")
        self.assertNotRegex(text, r"/(?:Users|home|private|tmp)/")

    def test_expected_freeze_is_the_selected_install_set(self):
        lines = logical_lines((TOOL / "expected-freeze.txt").read_text(encoding="utf-8"))
        self.assertEqual({pin(line) for line in lines}, FREEZE)
        self.assertEqual(len(lines), 31)

    def test_osv_inventory_scans_every_pin_file(self):
        inventory = json.loads((ROOT / ".github/osv-scanner-lockfiles.json").read_text(encoding="utf-8"))
        listed = {entry["path"] for entry in inventory["lockfiles"]}
        self.assertLessEqual({f"tools/graphiti-smoke/{name}" for name in
                              ("requirements.txt", "graphiti-0.30.2.constraints.txt", "expected-freeze.txt")}, listed)

    def test_readme_runs_the_catalog_recipe_and_names_every_pin(self):
        readme = (TOOL / "README.md").read_text(encoding="utf-8")
        block = readme.split("## Install and accept", 1)[1].split("```sh\n", 1)[1].split("\n```", 1)[0]
        self.assertEqual(block.replace("\\\n  ", "").splitlines(), RECIPE)
        for value in (WHEEL_SHA256, PIP_AUDIT_WHEEL_SHA256, RELEASE_COMMIT, LOCK_COMMIT, LOCK_BLOB, FALKORDB,
                      FALKORDB_ROLLBACK):
            self.assertIn(value, readme)


class CatalogRecipeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        candidates = json.loads((ROOT / "manifests/candidates.json").read_text(encoding="utf-8"))["candidates"]
        cls.candidate = next(entry for entry in candidates if entry["repository"] == "getzep/graphiti")
        entries = json.loads((ROOT / "catalogs/us-equities/foundation-memory.json").read_text(encoding="utf-8"))
        cls.card = next(entry for entry in entries["entries"] if entry["id"] == "foundation-graphiti")
        markdown = (ROOT / "catalogs/us-equities/foundation-memory.md").read_text(encoding="utf-8")
        cls.section = markdown.split("\n## graphiti\n", 1)[1].split("\n## ", 1)[0]
        cls.block = cls.section.split("```text\n", 1)[1].split("\n```", 1)[0].splitlines()

    def test_the_reviewed_snapshot_stays_beside_the_release_commit(self):
        self.assertEqual((self.candidate["reviewed_commit"], self.candidate["release_commit"]),
                         (REVIEWED_COMMIT, RELEASE_COMMIT))
        self.assertEqual((self.card["source_commit"], self.card["release_commit"]), (REVIEWED_COMMIT, RELEASE_COMMIT))
        self.assertIn(RELEASE_COMMIT, self.section)
        self.assertEqual(self.card["evidence_level"], "source_review")

    def test_every_copy_carries_the_whole_recipe_and_no_unpinned_install(self):
        copies = {"candidates.json": self.candidate["commands_not_executed"],
                  "foundation-memory.json": self.card["native_workflow"], "foundation-memory.md": self.block}
        for label, commands in copies.items():
            with self.subTest(label):
                self.assertEqual([command for command in commands if not command.startswith("# ")][:len(RECIPE)],
                                 RECIPE)
                self.assertFalse([command for command in commands if "pip install graphiti-core" in command])
                self.assertTrue(commands[0].startswith("# ") and LOCK_COMMIT[:8] in commands[0]
                                and LOCK_BLOB[:8] in commands[0])
                self.assertTrue(any(command.startswith("# ") and FALKORDB in command and FALKORDB_ROLLBACK in command
                                    for command in commands))
        self.assertEqual(self.block, self.card["native_workflow"], "the Markdown block mirrors the catalog entry")

    def test_mcp_steps_are_deferred_comments(self):
        commands = self.candidate["commands_not_executed"]
        for step in ("cd graphiti/mcp_server", "uv sync", "docker compose up"):
            lines = [command for command in commands if step in command]
            self.assertEqual(len(lines), 1, step)
            self.assertTrue(lines[0].startswith("# Deferred MCP lane"), lines[0])


class SmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tree = ast.parse((TOOL / "smoke.py").read_text(encoding="utf-8"))

    def test_the_smoke_runs_nine_checks(self):
        calls = [node for node in self.tree.body if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
                 and isinstance(node.value.func, ast.Name) and node.value.func.id == "check"]
        self.assertEqual(len(calls) + 1, 9, "eight check() calls after the import check")

    def test_value_checks_fail_on_a_wrong_value(self):
        functions = {node.name: node for node in self.tree.body if isinstance(node, ast.FunctionDef)}
        for name in ("sdk_surface", "retry_predicate"):
            with self.subTest(name):
                raised = [node.exc.func.id for node in ast.walk(functions[name]) if isinstance(node, ast.Raise)
                          and isinstance(node.exc, ast.Call) and isinstance(node.exc.func, ast.Name)]
                self.assertIn("AssertionError", raised)

    def test_the_smoke_exits_2_without_graphiti(self):
        if importlib.util.find_spec("graphiti_core") is not None:
            self.skipTest("graphiti_core is importable in this interpreter")
        result = subprocess.run([sys.executable, "-I", str(TOOL / "smoke.py")], capture_output=True, text=True,
                                timeout=120, check=False)
        self.assertEqual(result.returncode, 2, result.stderr)
        checks = json.loads(result.stdout)["checks"]
        self.assertEqual(list(checks), ["import graphiti_core"])
        self.assertFalse(checks["import graphiti_core"]["ok"])
        self.assertIn("ModuleNotFoundError", checks["import graphiti_core"]["error"])


if __name__ == "__main__":
    unittest.main()
