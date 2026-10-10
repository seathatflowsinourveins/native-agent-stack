"""Local checks of the repository's pinned jCodeMunch project configuration.

Sources: jgravelle/jcodemunch-mcp v1.108.333, src/jcodemunch_mcp/config.py
L542-548 (schema), L642-739 (JSONC algorithm), L1278-1305 (project loading):
https://github.com/jgravelle/jcodemunch-mcp/blob/v1.108.333/src/jcodemunch_mcp/config.py

The JSONC helper follows the pinned loader, including its adjacent-comment
handling. Keeping this small, sourced helper here lets ordinary stdlib unittest
runs check the configuration without installing an MCP server or reading host
settings. These are local integration checks, not unchanged upstream tests.
"""

import io
import json
import re
import subprocess
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / ".jcodemunch.jsonc"
CONFIG_TYPES = {"max_folder_files": int, "context_providers": bool, "extra_ignore_patterns": list}

# Synthetic JSONC inputs; expected values are independent of the stripping
# helper. Cover the pinned loader's strings, comments, and trailing commas.
JSONC_CASES = (
    (
        r'''// project settings
        {
          "url": "https://example.invalid/a/*literal*/,}",
          "patterns": ["evidence/artifacts/**", "folder/\"quoted\"/**", "end\\",],
          /* block comment */
          "limit": 4000, // whitespace separates the comma and line comment
        }''',
        {
            "url": "https://example.invalid/a/*literal*/,}",
            "patterns": ["evidence/artifacts/**", 'folder/"quoted"/**', "end\\"],
            "limit": 4000,
        },
    ),
    ('{"value": 1,// adjacent line comment\n}', {"value": 1}),
    ('{"value": 1/* adjacent block comment */,}', {"value": 1}),
    ('{"value": 1,/* block before newline */\n}', {"value": 1}),
)


def strip_jsonc(text):
    """Follow upstream config.py L630-727; retain comment markers in strings."""
    result, i, n = [], 0, len(text)
    in_str = False
    while i < n:
        ch = text[i]
        if in_str:
            result.append(ch)
            if ch == "\\" and i + 1 < n:
                result.append(text[i + 1])
                i += 2
                continue
            if ch == '"':
                in_str = False
            i += 1
        elif ch == '"':
            in_str = True
            result.append(ch)
            i += 1
        elif ch == "/" and i + 1 < n and text[i + 1] == "/":
            if result and result[-1] == ",":
                result.pop()
                while result and result[-1] in (" ", "\t"):
                    result.pop()
            end = text.find("\n", i)
            i = n if end == -1 else end
        elif ch == "/" and i + 1 < n and text[i + 1] == "*":
            end = text.find("*/", i + 2)
            if end == -1:
                i = n
            else:
                end_i = end + 2
                if end_i < n and text[end_i] == ",":
                    i = end_i + 1
                elif end_i < n and text[end_i] == "\n":
                    j = len(result) - 1
                    while j >= 0 and result[j] in (" ", "\t"):
                        j -= 1
                    if j >= 0 and result[j] == ",":
                        result.pop()
                    i = end_i
                else:
                    i = end_i
        else:
            result.append(ch)
            i += 1

    output = "".join(result)
    final = []
    j = 0
    m = len(output)
    while j < m:
        ch = output[j]
        if ch == '"':
            backslash_count = 0
            k = j - 1
            while k >= 0 and output[k] == "\\":
                backslash_count += 1
                k -= 1
            if backslash_count % 2 == 1:
                final.append(ch)
                j += 1
                continue
            final.append(ch)
            j += 1
            while j < m:
                final.append(output[j])
                if output[j] == '"':
                    backslash_count = 0
                    k = j - 1
                    while k >= 0 and output[k] == "\\":
                        backslash_count += 1
                        k -= 1
                    if backslash_count % 2 == 0:
                        j += 1
                        break
                j += 1
        elif ch in ("}", "]"):
            while final and final[-1] in (" ", "\t", "\n", "\r"):
                final.pop()
            if final and final[-1] == ",":
                final.pop()
            final.append(ch)
            j += 1
        else:
            final.append(ch)
            j += 1
    return "".join(final)


def load_config():
    return json.loads(strip_jsonc(CONFIG_PATH.read_text(encoding="utf-8-sig")))


def tracked_files(*args):
    """Use native Git's complete NUL-delimited inventory and ignore matcher.

    Source: https://git-scm.com/docs/git-ls-files (--cached, --ignored,
    --exclude, -z). No --exclude-standard: only the project patterns are tested.
    Upstream index_folder.py L1273-1279 uses pathspec's gitignore dialect.
    """
    output = subprocess.check_output(
        ["git", "ls-files", "--cached", "-z", *args], cwd=ROOT
    )
    return {path.decode("utf-8") for path in output.split(b"\0") if path}


class JCodeMunchJsoncTests(unittest.TestCase):
    def test_pinned_jsonc_rules_preserve_quoted_comment_markers(self):
        for text, expected in JSONC_CASES:
            with self.subTest(text=text):
                self.assertEqual(json.loads(strip_jsonc(text)), expected)

    def test_invalid_json_is_not_silently_accepted(self):
        with self.assertRaises(json.JSONDecodeError):
            json.loads(strip_jsonc('{"max_folder_files": invalid}'))


class JCodeMunchConfigTests(unittest.TestCase):
    def test_config_matches_pinned_upstream_schema(self):
        config = load_config()
        self.assertIsInstance(config, dict)
        self.assertEqual(set(config), set(CONFIG_TYPES))
        self.assertIs(config["context_providers"], False)
        for key, expected in CONFIG_TYPES.items():
            with self.subTest(key=key):
                self.assertIs(type(config[key]), expected)
        self.assertGreater(config["max_folder_files"], 0)
        for pattern in config["extra_ignore_patterns"]:
            self.assertIsInstance(pattern, str)
            self.assertTrue(pattern.strip())

    def test_index_coverage_and_measured_cap(self):
        config = load_config()
        files = tracked_files()
        self.assertTrue(files, "coverage must inspect a nonempty Git inventory")
        patterns = config["extra_ignore_patterns"]
        ignored = (
            tracked_files("--ignored", *("--exclude=" + p for p in patterns))
            if patterns else set()
        )
        protected_roots = (
            "scripts/", "tools/", "tests/", "docs/", "examples/", "adoption/",
            "observability/", "catalogs/",
        )
        for prefix in protected_roots:
            with self.subTest(retained=prefix):
                protected = {p for p in files if p.startswith(prefix)}
                self.assertTrue(protected, "source coverage must not be vacuous")
                overlap = protected & ignored
                self.assertEqual(len(overlap), 0, sorted(overlap)[:5])

        code_extensions = {
            ".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".sh",
            ".bash", ".go", ".rs", ".toml", ".yaml", ".yml", ".sql",
            ".cs", ".css", ".html",
        }
        blueprint_code = {
            p for p in files
            if p.startswith("blueprints/") and Path(p).suffix in code_extensions
        }
        self.assertTrue(blueprint_code)
        overlap = blueprint_code & ignored
        self.assertEqual(len(overlap), 0, sorted(overlap)[:5])

        for prefix in ("evidence/artifacts/", "evidence/receipts/"):
            with self.subTest(excluded=prefix):
                data = {p for p in files if p.startswith(prefix)}
                self.assertTrue(data)
                missing = data - ignored
                self.assertEqual(len(missing), 0, sorted(missing)[:5])

        # Known repository data families must be removed without hiding the
        # source files alongside them. These predicates are the test oracle,
        # independent of the patterns read from the project configuration.
        # docs/lanes.md separates trading blueprints: an individual family can
        # disappear when that lane moves. Require a nonempty union instead.
        # Directory exclusions cover every suffix; data patterns cover four.
        families = {
            "receipts": None,
            "native-outputs": None,
            "judge_results": None,
            "data": {".json", ".jsonl", ".csv", ".tsv"},
        }
        blueprint_data = set()
        for directory, suffixes in families.items():
            with self.subTest(blueprint_data=directory):
                data = {
                    p for p in files if p.startswith("blueprints/")
                    and directory in Path(p).parts[1:-1]
                    and (suffixes is None or Path(p).suffix in suffixes)
                }
                blueprint_data.update(data)
                missing = data - ignored
                self.assertEqual(len(missing), 0, sorted(missing)[:5])
        self.assertTrue(blueprint_data, "blueprint output coverage must not be vacuous")

        remaining = len(files - ignored)
        cap = config["max_folder_files"]
        # All remaining extensions count, before upstream language/size/secret
        # filters. This is a conservative tracked inventory, not a host reindex.
        self.assertLess(remaining, cap, f"{remaining} candidates reach cap {cap}")
        print(
            f"jCodeMunch tracked inventory: total={len(files)} "
            f"ignored={len(ignored)} remaining={remaining} cap={cap} "
            f"margin={cap - remaining}"
        )


class JCodeMunchCoverageRegressionTests(unittest.TestCase):
    """Exercise the coverage contract with changed Git inventories.

    Sources: docs/lanes.md (trading extraction); the configured gitignore
    dialect at upstream index_folder.py L1273-1279; Python's supported mock:
    https://docs.python.org/3/library/unittest.mock.html#patch
    """

    def setUp(self):
        self.files = tracked_files()
        patterns = load_config()["extra_ignore_patterns"]
        self.ignored = tracked_files(
            "--ignored", *("--exclude=" + p for p in patterns)
        )

    def run_coverage(self, files, ignored):
        result = unittest.TestResult()
        with patch(__name__ + ".tracked_files", side_effect=(files, ignored)):
            with redirect_stdout(io.StringIO()):
                JCodeMunchConfigTests(
                    "test_index_coverage_and_measured_cap"
                ).run(result)
        return result

    def test_coverage_survives_trading_blueprint_removal(self):
        files = {p for p in self.files if not p.startswith("blueprints/us-equities/")}
        result = self.run_coverage(files, self.ignored & files)
        self.assertTrue(result.wasSuccessful(), result.failures + result.errors)

    def test_data_text_file_does_not_require_an_unconfigured_exclusion(self):
        files = self.files | {"blueprints/convergence-practice/data/notes.txt"}
        result = self.run_coverage(files, self.ignored)
        self.assertTrue(result.wasSuccessful(), result.failures + result.errors)

    def test_retained_wave_sources_fit_configured_cap(self):
        # Keep every current coverage obligation and add retained source files
        # as the consolidation wave does, without creating files on disk.
        additions = {
            f"tests/jcodemunch_wave/source_{number:04d}.py"
            for number in range(1000)
        }
        self.assertFalse(additions & self.files)
        files = self.files | additions
        self.assertGreater(len(files - self.ignored), 4000)
        result = self.run_coverage(files, self.ignored)
        self.assertFalse(result.errors)
        self.assertTrue(result.wasSuccessful(), result.failures)

    def test_empty_blueprint_output_union_is_rejected(self):
        directories = {"receipts", "native-outputs", "judge_results", "data"}
        files = {
            p for p in self.files
            if not (
                p.startswith("blueprints/")
                and directories.intersection(Path(p).parts[1:-1])
            )
        }
        result = self.run_coverage(files, self.ignored & files)
        self.assertFalse(result.errors)
        self.assertTrue(result.failures, "empty coverage must still fail")


class JCodeMunchRecipeTests(unittest.TestCase):
    def test_root_reindex_order_has_required_flags_and_no_extra_exclusions(self):
        # Upstream v1.108.319: index_folder.py L1439-1451/L1528;
        # counter.py L129-133; config.py L1230 (requested-folder lookup).
        recipe = (ROOT / "recipes" / "README.md").read_text(encoding="utf-8")
        root_orders = []
        for block in re.findall(r"```json\n(.*?)\n```", recipe, re.DOTALL):
            try:
                order = json.loads(block)
            except json.JSONDecodeError:
                continue
            if (
                isinstance(order, dict)
                and order.get("action") == "index_folder"
                and order.get("args", {}).get("path") == "/absolute/checkout/root"
            ):
                root_orders.append(order)
        self.assertEqual(len(root_orders), 1, "document one complete root reindex call")
        self.assertEqual(root_orders[0], {
            "action": "index_folder",
            "args": {
                "path": "/absolute/checkout/root",
                "incremental": False,
                "use_ai_summaries": False,
            },
            "allow_state_change": True,
        })


if __name__ == "__main__":
    unittest.main()
