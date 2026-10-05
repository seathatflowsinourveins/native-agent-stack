"""GPT runtime coverage for the report-only catalog-freshness path.

Covers each stage the GPT runtime workers, SDKs and agents pass through:
- extract: tools/sota-convergence/extract_layers.py resolves RUNTIME_PIN_SOURCES
  (the pins that the new-WSL install plan, the runtime-worker recipe pin record and
  the native SDK constraints carry) and lists RUNTIME_WATCH_SOURCES (watch-only
  upstreams that no install or runtime record on main pins, such as pi) into
  runtime-pins.json. A record that moved does not raise; its entry carries an
  error instead.
- fetch: github_freshness.py reads repository URLs from runtime-pins.json too.
- build: build_manifest.py's build_runtime_freshness (fixed dates, no wall clock)
  and its --runtime-freshness-out flag, which leaves the manifest and the trading
  sidecar byte-identical and, when a runtime upstream trips the leak gate,
  withholds only the runtime rows.
- report: scripts/freshness_propose.py renders the runtime table (or the line
  saying it was withheld) into drift.md without touching drift-status.txt or the
  drift-table ids the propose job reads.
- tag patterns: three entries declare a literal tag prefix and an anchored pattern
  (extract_layers.py's RUNTIME_TAG_KEYS); github_freshness.py lists those tags
  through git/matching-refs, build_runtime_freshness takes the highest matching
  version (ASCII digits only) as the row's upstream latest, and the report marks
  it "(tag)" or lists the rows whose pattern selected no tag. A failed list is
  kept apart from partial_errors, so it changes no row but the runtime row that
  declares the prefix. A cut list (matching_tags_truncated) shows the kept tag,
  is not compared (tag_list_truncated) and is named in the same line.
- runtime-only failures: a fetch failure on a repository that only
  runtime-pins.json names counts in runtime_only_errors or
  runtime_only_partial_errors, never in the errors and partial_errors that hold
  the propose job, and the runtime table names its rows in one line.
- declarations: a pointer that is not an RFC 6901 JSON pointer raises when the
  declaration is checked.

No network. The extraction tests read the checked-in repository; every other
test uses synthetic fixtures.
"""
from __future__ import annotations

import ast
import importlib.util
import inspect
import json
import os
import re
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

from scripts import freshness_propose as fp
from scripts import saturation_ledger

ROOT = Path(__file__).resolve().parents[1]
TOOL_DIR = ROOT / "tools" / "sota-convergence"
WORKFLOW = ROOT / ".github/workflows/catalog-freshness.yml"
CLIENT_CONFIG_TOOL = ROOT / "tools/adoption/new_wsl_client_config.py"
# The coordinator's decision record names openai-agents-js; it lands after this test.
RUNTIME_DECISION = "docs/decisions/2026-10-02-gpt-runtime-tracking.md"
CHECKED_AT = "2026-10-02"


def load_module(name, filename):
    spec = importlib.util.spec_from_file_location(name, TOOL_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


extract_layers = load_module("extract_layers_runtime", "extract_layers.py")
build_manifest = load_module("build_manifest_runtime", "build_manifest.py")
github_freshness = load_module("github_freshness_runtime", "github_freshness.py")

# Each new-WSL row source and the install-plan slot it reads.
NEW_WSL_SLOTS = {
    "new-wsl:codex": "codex",
    "new-wsl:codex-sdk": "codex-sdk-and-codex-exec-app-server",
    "new-wsl:claude-agent-sdk": "claude-agent-sdk",
    "new-wsl:omniroute": "gpt-gateway",
    "new-wsl:openhands-sdk": "agent-runtime-worker",
    "new-wsl:gpt-researcher": "research-harnesses",
    "new-wsl:deer-flow": "research-harnesses",
    "new-wsl:harbor": "harbor-containerized-agent-e2e-runner",
    "new-wsl:inspect-ai": "inspect-ai",
}
# research-harnesses holds two upstreams; each entry takes the part at this position.
RESEARCH_HARNESS_PARTS = {
    "new-wsl:gpt-researcher": (0, "assafelovic/gpt-researcher"),
    "new-wsl:deer-flow": (1, "bytedance/deer-flow"),
}
OPENHANDS_RECIPE_PINS = "blueprints/runtime-workers/openhands/pins.json"
SDK_CONSTRAINTS = "adoption/sdk/accepted-constraints.txt"
SDK_LOCK_REQUIREMENTS = {"sdk-lock:openai-codex": "openai-codex", "sdk-lock:openai": "openai"}
# The summary keys the trading test (and the workflow log) already read, in order.
EXISTING_SUMMARY_KEYS = [
    "foundation_layers", "trading_entries", "trading_layers", "unmapped_tags", "trading_pins",
    "star_candidates", "beyond_stars", "models",
]
# The tag declarations the checked-in extraction carries (extract_layers.py's RUNTIME_TAG_KEYS).
DECLARED_TAGS = {
    "new-wsl:inspect-ai": {"prefix": "", "pattern": r"^(\d+\.\d+\.\d+)$"},
    "watch:codex-action": {"prefix": "v", "pattern": r"^v(\d+\.\d+(?:\.\d+)?)$"},
    "watch:deepagents": {"prefix": "deepagents==", "pattern": r"^deepagents==(\d+\.\d+\.\d+)$"},
}
# The tag declarations in extract_layers.py's sources, which the selection tests apply.
CHECKED_IN_TAGS = {source["id"]: source["tags"] for source in
                   extract_layers.RUNTIME_PIN_SOURCES + extract_layers.RUNTIME_WATCH_SOURCES if source.get("tags")}
# Tag names shaped like each upstream's. The API returns only the names under the declared
# prefix; the Deep Agents list also carries other packages' tags, to test the pattern itself.
INSPECT_LIKE_TAGS = ["release/2025-11-28", "0.3.99", "0.3.273", "0.3.276", "0.3.275", "0.3.277rc1", "0.4.0-dev"]
DEEPAGENTS_LIKE_TAGS = ["deepagents-talon==0.0.9", "deepagents==0.7.21", "deepagents==0.7.3", "deepagents-cli==1.0.0"]
CODEX_ACTION_LIKE_TAGS = ["v1.12", "v1.9", "v1.10", "v1"]
# entry id -> (tag names, the tag its declared pattern selects, how many names it matches)
TAG_EXAMPLES = {
    "new-wsl:inspect-ai": (INSPECT_LIKE_TAGS, "0.3.276", 4),
    "watch:deepagents": (DEEPAGENTS_LIKE_TAGS, "deepagents==0.7.21", 2),
    "watch:codex-action": (CODEX_ACTION_LIKE_TAGS, "v1.12", 3),
}


class ExtractionResolvesRuntimePinsTests(unittest.TestCase):
    """Runs extract_layers.main() against the checked-in repository."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls._tmp.name)
        with redirect_stdout(StringIO()) as stdout:
            rc = extract_layers.main(["--repo-root", str(ROOT), "--out", str(cls.out)])
        assert rc == 0
        cls.summary = json.loads(stdout.getvalue().splitlines()[0])
        cls.entries = {entry["id"]: entry for entry in cls._load("runtime-pins.json")["entries"]}

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    @classmethod
    def _load(cls, name):
        return json.loads((cls.out / name).read_text(encoding="utf-8"))

    def test_summary_counts_every_runtime_entry_and_none_is_unresolved(self):
        self.assertEqual(list(self.summary), EXISTING_SUMMARY_KEYS + ["runtime_pins", "runtime_unresolved"])
        self.assertEqual(self.summary["runtime_pins"], 19)
        self.assertEqual(self.summary["runtime_unresolved"], [])
        self.assertEqual(len(self.entries), 19)
        self.assertEqual(list(self.entries), sorted(self.entries))

    def test_every_pin_source_resolves_to_a_pin_and_a_github_repository(self):
        for source in extract_layers.RUNTIME_PIN_SOURCES:
            with self.subTest(source=source["id"]):
                entry = self.entries[source["id"]]
                self.assertIsNone(entry["error"])
                self.assertEqual(entry["kind"], "pin_source")
                self.assertIsInstance(entry["pin"], str)
                self.assertTrue(entry["pin"].strip())
                self.assertIsNotNone(github_freshness.github_slug(entry["repository"]))

    def test_new_wsl_entries_match_the_install_plan_rows(self):
        plan = json.loads((ROOT / extract_layers.NEW_WSL_INSTALL_PLAN).read_text(encoding="utf-8"))
        declared = {source["id"] for source in extract_layers.RUNTIME_PIN_SOURCES if source["id"].startswith("new-wsl:")}
        self.assertEqual(declared, set(NEW_WSL_SLOTS))
        for entry_id, slot in NEW_WSL_SLOTS.items():
            with self.subTest(entry=entry_id):
                entry = self.entries[entry_id]
                # The codex and codex-sdk-and-codex-exec-app-server rows carry the same
                # repository and release, so only the declared slot shows a swap.
                self.assertEqual(entry["pin_source"]["row"]["value"], slot)
                rows = [row for row in plan["owners"] if row.get("slot") == slot]
                self.assertEqual(len(rows), 1)
                repository, release = rows[0]["repository"], rows[0]["release"]
                if entry_id in RESEARCH_HARNESS_PARTS:
                    position, slug = RESEARCH_HARNESS_PARTS[entry_id]
                    repositories = [part.strip() for part in repository.split(";")]
                    releases = [part.strip() for part in release.split(";")]
                    self.assertEqual((len(repositories), len(releases)), (2, 2))
                    self.assertEqual(github_freshness.github_slug(repositories[position]), slug)
                    self.assertEqual(github_freshness.github_slug(entry["pin_source"]["row"]["part_repository"]),
                                     github_freshness.github_slug(repositories[position]))
                    repository, release = repositories[position], releases[position]
                self.assertEqual((entry["repository"], entry["pin"]), (repository, release))

    def test_recipe_pin_matches_the_openhands_pin_record(self):
        record = json.loads((ROOT / OPENHANDS_RECIPE_PINS).read_text(encoding="utf-8"))
        entry = self.entries["recipe:openhands-sdk"]
        self.assertEqual((entry["pin"], entry["repository"]), (record["tag"], record["repository"]))

    def test_sdk_lock_pins_match_their_constraint_lines(self):
        lines = (ROOT / SDK_CONSTRAINTS).read_text(encoding="utf-8").splitlines()
        for entry_id, name in SDK_LOCK_REQUIREMENTS.items():
            with self.subTest(entry=entry_id):
                versions = [line.split("==", 1)[1].strip() for line in lines
                            if "==" in line and line.split("==", 1)[0].strip() == name]
                self.assertEqual(len(versions), 1)
                self.assertEqual(self.entries[entry_id]["pin"], versions[0])

    def test_watch_entries_are_listed_without_a_pin(self):
        for source in extract_layers.RUNTIME_WATCH_SOURCES:
            with self.subTest(source=source["id"]):
                self.assertEqual(self.entries[source["id"]], {
                    "id": source["id"], "group": source["group"], "kind": "watch_only",
                    "repository": source["repository"], "pin": None, "pin_source": None,
                    "named_in": source["named_in"], "error": None, "tags": source.get("tags"),
                })

    def test_runtime_ids_are_unique_grouped_and_never_reuse_a_report_id(self):
        sources = extract_layers.RUNTIME_PIN_SOURCES + extract_layers.RUNTIME_WATCH_SOURCES
        ids = [source["id"] for source in sources]
        self.assertEqual(len(ids), len(set(ids)))
        for source in sources:
            self.assertIn(source["group"], extract_layers.RUNTIME_GROUPS, source["id"])
        foundation = {component["id"] for layer in self._load("foundation-layers.json")["layers"]
                      for component in layer["components"]}
        trading = {entry.get("id") for entry in self._load("trading-catalog.json")["entries"]}
        trading_pins = {entry["id"] for entry in self._load("trading-pins.json")["entries"]}
        self.assertEqual(set(ids) & (foundation | trading | trading_pins), set())

    def test_fetch_step_collects_the_runtime_repositories(self):
        urls = github_freshness.collect_repository_urls(self.out)
        for entry in self.entries.values():
            self.assertIn(entry["repository"], urls, entry["id"])

    def test_exactly_three_entries_declare_a_tag_pattern(self):
        declared = {entry_id: entry["tags"] for entry_id, entry in self.entries.items() if entry["tags"] is not None}
        self.assertEqual(declared, DECLARED_TAGS)

    def test_fetch_step_reads_the_declared_tag_prefixes(self):
        self.assertEqual(github_freshness.collect_declared_tag_prefixes(self.out), {
            "ukgovernmentbeis/inspect_ai": ("",), "openai/codex-action": ("v",),
            "langchain-ai/deepagents": ("deepagents==",),
        })


class MainReservesReportIdsTests(unittest.TestCase):
    """extract_layers.main() passes every foundation, trading card and trading pin id
    to resolve_runtime_pins as reserved_ids (a spy records them and calls through)."""

    def test_main_reserves_a_trading_pin_a_trading_card_and_a_foundation_component(self):
        resolve = extract_layers.resolve_runtime_pins
        recorded = []

        def spy(*args, **kwargs):
            arguments = inspect.signature(resolve).bind(*args, **kwargs).arguments
            recorded.append(set(arguments.get("reserved_ids", ())))
            return resolve(*args, **kwargs)

        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(extract_layers, "resolve_runtime_pins", spy):
            out = Path(tmp)
            with redirect_stdout(StringIO()):
                self.assertEqual(extract_layers.main(["--repo-root", str(ROOT), "--out", str(out)]), 0)
            written = {name: json.loads((out / name).read_text(encoding="utf-8")) for name in (
                "foundation-layers.json", "trading-catalog.json", "trading-pins.json", "runtime-pins.json")}
        self.assertEqual(len(recorded), 1)
        self.assertLessEqual({"hftbacktest", "nautilustrader", "codex"}, recorded[0])
        # Each id is the kind of report id it stands for here, and only that kind, so the
        # assertion above fails when main() drops any one of the three reserve sources.
        kinds = {
            "trading pin": {entry["id"] for entry in written["trading-pins.json"]["entries"]},
            "trading card": {entry.get("id") for entry in written["trading-catalog.json"]["entries"]},
            "foundation component": {component["id"] for layer in written["foundation-layers.json"]["layers"]
                                     for component in layer["components"]},
        }
        for report_id, kind in (("hftbacktest", "trading pin"), ("nautilustrader", "trading card"),
                                ("codex", "foundation component")):
            self.assertEqual({name for name, ids in kinds.items() if report_id in ids}, {kind}, report_id)
        # The spy called through: the runtime pins were still resolved and written.
        self.assertEqual(len(written["runtime-pins.json"]["entries"]), 19)


class InstallPlanRevisionTests(unittest.TestCase):
    def test_the_tracker_reads_the_plan_the_client_config_tool_reads(self):
        # Read with ast, not imported: the tracker and the client configuration tool
        # must move to a new plan revision together.
        tree = ast.parse(CLIENT_CONFIG_TOOL.read_text(encoding="utf-8"))
        values = []
        for node in tree.body:
            if isinstance(node, ast.Assign):
                targets = node.targets
            elif isinstance(node, ast.AnnAssign):
                targets = [node.target]
            else:
                continue
            if any(isinstance(target, ast.Name) and target.id == "PLAN_REL" for target in targets):
                self.assertIsInstance(node.value, ast.Constant)
                values.append(node.value.value)
        self.assertEqual(len(values), 1)
        self.assertEqual(extract_layers.NEW_WSL_INSTALL_PLAN, values[0] + "/install-plan.json")


class WatchSourcesAreNamedOnMainTests(unittest.TestCase):
    def test_every_watch_source_is_named_in_its_file(self):
        for source in extract_layers.RUNTIME_WATCH_SOURCES:
            with self.subTest(source=source["id"]):
                named_in = ROOT / source["named_in"]
                if source["id"] == "watch:openai-agents-js":
                    self.assertEqual(source["named_in"], RUNTIME_DECISION)
                    if not named_in.exists():
                        self.skipTest(f"{RUNTIME_DECISION} is not in this checkout yet")
                slug = github_freshness.github_slug(source["repository"])
                pattern = re.compile(rf"(?<![A-Za-z0-9_.-]){re.escape(slug)}(?![A-Za-z0-9_-])", re.IGNORECASE)
                self.assertRegex(named_in.read_text(encoding="utf-8"), pattern)


class ResolveRuntimePinsTests(unittest.TestCase):
    """resolve_runtime_pins() against synthetic records in a temporary repository."""

    PLAN = "plan/install-plan.json"
    RECORD = "records/pins.json"
    CONSTRAINTS = "sdk/constraints.txt"

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        pair = "https://github.com/example/one ; https://github.com/example/two"
        self._write(self.PLAN, json.dumps({"owners": [
            {"slot": "alpha", "repository": "https://github.com/example/alpha", "release": "v1.2.0"},
            {"slot": "pair", "repository": pair, "release": "v1.0.0 ; v2.0.0"},
            {"slot": "uneven", "repository": pair, "release": "v1.0.0"},
            {"slot": "twice", "repository": "https://github.com/example/a", "release": "v1"},
            {"slot": "twice", "repository": "https://github.com/example/b", "release": "v2"},
            {"slot": "no-release", "repository": "https://github.com/example/c", "release": None},
            {"slot": "off-github", "repository": "https://releases.example.org/c/", "release": "v1"},
        ], "flat": {"slot": "alpha"}}))
        self._write(self.RECORD, json.dumps({
            "tag": "v3.0.0", "repository": "https://github.com/example/worker", "joined": "v1 ; v2",
        }))
        self._write(self.CONSTRAINTS, "# resolver constraints\n\nopenai_codex==1.2.3\nopenai == 3.0.0  # pinned\n"
                                      "openai-codex-cli-bin==9.9.9\ndup==1.0\nDup==2.0\n")

    def _write(self, relative, text):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def _row(self, value, **row):
        return {"id": f"row:{value}", "group": "runtime-worker", "path": self.PLAN,
                "row": {"array": "/owners", "key": "slot", "value": value, **row}}

    def _pointer(self, **overrides):
        source = {"id": "pointer:worker", "group": "runtime-worker", "path": self.RECORD,
                  "pin_pointer": "/tag", "repository_pointer": "/repository"}
        source.update(overrides)
        return source

    def _requirement(self, name, **overrides):
        source = {"id": f"requirement:{name}", "group": "model-sdk", "path": self.CONSTRAINTS,
                  "requirement": name, "repository": "https://github.com/example/sdk"}
        source.update(overrides)
        return source

    def _resolve(self, *pin_sources, watch_sources=(), reserved_ids=()):
        return extract_layers.resolve_runtime_pins(self.root, pin_sources=pin_sources, watch_sources=watch_sources,
                                                   reserved_ids=reserved_ids)["entries"]

    def _one(self, source):
        entries = self._resolve(source)
        self.assertEqual(len(entries), 1)
        return entries[0]

    def test_row_form_selects_the_row_by_key(self):
        self.assertEqual(self._one(self._row("alpha")), {
            "id": "row:alpha", "group": "runtime-worker", "kind": "pin_source",
            "repository": "https://github.com/example/alpha", "pin": "v1.2.0",
            "pin_source": {"path": self.PLAN, "row": {"array": "/owners", "key": "slot", "value": "alpha"}},
            "named_in": None, "error": None, "tags": None,
        })

    def test_a_missing_or_repeated_row_is_an_error_entry_not_a_raise(self):
        for value, count in (("absent", 0), ("twice", 2)):
            with self.subTest(value=value):
                entry = self._one(self._row(value))
                self.assertEqual((entry["pin"], entry["repository"]), (None, None))
                self.assertIn(self.PLAN, entry["error"])
                self.assertIn(f"{value!r}: {count} rows match", entry["error"])

    def test_an_array_that_is_not_a_list_is_an_error_entry(self):
        self.assertIn("/flat is not a list", self._one(self._row("alpha", array="/flat"))["error"])
        self.assertIn("pointer /gone does not resolve", self._one(self._row("alpha", array="/gone"))["error"])

    def test_a_composite_row_without_part_repository_is_an_error(self):
        self.assertIn("composite row", self._one(self._row("pair"))["error"])

    def test_part_repository_takes_the_release_at_the_same_position(self):
        entry = self._one(self._row("pair", part_repository="https://github.com/Example/Two"))
        self.assertEqual((entry["repository"], entry["pin"], entry["error"]),
                         ("https://github.com/example/two", "v2.0.0", None))
        self.assertEqual(entry["pin_source"]["row"]["part_repository"], "https://github.com/Example/Two")

    def test_composite_part_counts_that_differ_are_an_error(self):
        entry = self._one(self._row("uneven", part_repository="https://github.com/example/one"))
        self.assertIn("2 repository part(s) but 1 release part(s)", entry["error"])

    def test_a_part_that_is_not_in_the_row_is_an_error(self):
        entry = self._one(self._row("pair", part_repository="https://github.com/example/three"))
        self.assertIn("0 parts match part_repository", entry["error"])

    def test_requirement_matches_one_pep503_normalized_line(self):
        # 1.2.3 is only on the openai_codex line (openai-codex-cli-bin is 9.9.9), so it matched.
        entry = self._one(self._requirement("openai-codex"))
        self.assertEqual((entry["repository"], entry["pin"], entry["error"]),
                         ("https://github.com/example/sdk", "1.2.3", None))
        self.assertEqual(entry["pin_source"], {"path": self.CONSTRAINTS, "requirement": "openai-codex"})
        # openai is its own line: neither openai_codex nor openai-codex-cli-bin, and the comment is ignored.
        self.assertEqual(self._one(self._requirement("openai"))["pin"], "3.0.0")

    def test_a_missing_or_repeated_requirement_is_an_error_entry(self):
        for name, reason in (("absent", "requirement not found"), ("dup", "requirement found 2 times")):
            with self.subTest(name=name):
                entry = self._one(self._requirement(name))
                self.assertIsNone(entry["pin"])
                self.assertEqual(entry["repository"], "https://github.com/example/sdk")  # the declared literal
                self.assertIn(reason, entry["error"])

    def test_pointer_form_reads_the_pin_and_repository_pointers(self):
        entry = self._one(self._pointer())
        self.assertEqual((entry["repository"], entry["pin"], entry["pin_source"], entry["error"]),
                         ("https://github.com/example/worker", "v3.0.0", {"path": self.RECORD, "pointer": "/tag"},
                          None))
        literal = self._one(self._pointer(repository_pointer=None, repository="https://github.com/example/lit"))
        self.assertEqual((literal["repository"], literal["pin"]), ("https://github.com/example/lit", "v3.0.0"))

    def test_a_resolved_value_that_is_no_pin_or_no_github_repository_is_an_error_entry(self):
        cases = {
            "pin is not a non-empty string": self._row("no-release"),
            "pin still contains ';'": self._pointer(pin_pointer="/joined"),
            "repository is not a GitHub URL": self._row("off-github"),
        }
        for reason, source in cases.items():
            with self.subTest(reason=reason):
                entry = self._one(source)
                self.assertIsNone(entry["pin"])
                self.assertIn(reason, entry["error"])

    def test_an_unreadable_record_is_an_error_that_names_no_host_path(self):
        (self.root / "records/directory.json").mkdir()
        self._write("records/broken.json", "{")
        cases = {
            "records/absent.json": "source file is missing or unreadable",
            "records/directory.json": "source file is missing or unreadable",
            "records/broken.json": "source file is not valid JSON",
        }
        for path, reason in cases.items():
            with self.subTest(path=path):
                error = self._one(self._pointer(path=path))["error"]
                self.assertEqual(error, f"{path}#/tag: {reason}")
                for host_path in (str(self.root), str(self.root.resolve()), tempfile.gettempdir()):
                    self.assertNotIn(host_path, error)

    def test_entries_are_sorted_by_id_and_watch_sources_follow_the_same_shape(self):
        watch = {"id": "watch:x", "group": "coding-agent", "repository": "https://github.com/example/x",
                 "named_in": "docs/x.md"}
        entries = self._resolve(self._row("pair", part_repository="https://github.com/example/one"),
                                self._row("alpha"), watch_sources=(watch,))
        self.assertEqual([entry["id"] for entry in entries], ["row:alpha", "row:pair", "watch:x"])
        self.assertEqual(entries[2], {
            "id": "watch:x", "group": "coding-agent", "kind": "watch_only",
            "repository": "https://github.com/example/x", "pin": None, "pin_source": None,
            "named_in": "docs/x.md", "error": None, "tags": None,
        })

    def test_declaration_errors_raise(self):
        pin_cases = {
            "duplicate id": ((self._row("alpha"), self._row("alpha")), ()),
            "reserved id": ((self._row("alpha"),), {"row:alpha"}),
            "unknown group": ((dict(self._row("alpha"), group="nowhere"),), ()),
            "missing group": (({"id": "x", "path": self.RECORD, "pin_pointer": "/tag",
                                "repository": "https://github.com/example/x"},), ()),
            "non-GitHub literal": ((self._requirement("openai", repository="https://gitlab.com/example/sdk"),), ()),
            "literal with a path suffix": ((self._requirement(
                "openai", repository="https://github.com/example/sdk/tree/main"),), ()),
            "path with ..": ((self._pointer(path="../outside.json"),), ()),
            "absolute path": ((self._pointer(path="/etc/passwd"),), ()),
            "two source forms": ((dict(self._row("alpha"), requirement="openai"),), ()),
            "no source form": (({"id": "bare", "group": "agent-sdk", "path": self.RECORD},), ()),
            "pointer without a repository": ((self._pointer(repository_pointer=None),), ()),
            "requirement without a literal repository": ((self._requirement("openai", repository=None),), ()),
        }
        for label, (pin_sources, reserved_ids) in pin_cases.items():
            with self.subTest(label=label), self.assertRaises(ValueError):
                self._resolve(*pin_sources, reserved_ids=reserved_ids)
        watch = {"id": "watch:x", "group": "coding-agent", "repository": "https://github.com/example/x"}
        watch_cases = {
            "watch without a repository": {"id": "watch:x", "group": "coding-agent"},
            "watch non-GitHub literal": dict(watch, repository="https://example.org/x"),
            "watch id that repeats a pin id": dict(watch, id="row:alpha"),
            "watch named_in outside the repository": dict(watch, named_in="../x.md"),
        }
        for label, source in watch_cases.items():
            with self.subTest(label=label), self.assertRaises(ValueError):
                self._resolve(self._row("alpha"), watch_sources=(source,))

    def test_a_pointer_that_is_not_rfc6901_raises_at_declaration_time(self):
        # Each would otherwise reach resolve_json_pointer and read as a moved record: an
        # entry with an "error" (a warning in the daily run), not a raise.
        cases = {
            "pin_pointer without the leading slash": self._pointer(pin_pointer="tag"),
            "repository_pointer without the leading slash": self._pointer(repository_pointer="repository"),
            "row array without the leading slash": self._row("alpha", array="owners"),
            "a tilde escape other than ~0 or ~1": self._pointer(pin_pointer="/t~2ag"),
            "a trailing tilde": self._pointer(pin_pointer="/tag~"),
            "a row array with a bare tilde": self._row("alpha", array="/own~ers"),
            "repository_pointer that is not a string, beside a literal": self._pointer(
                repository_pointer=7, repository="https://github.com/example/lit"),
        }
        for label, source in cases.items():
            with self.subTest(label=label), self.assertRaisesRegex(ValueError, "RFC 6901 JSON pointer"):
                self._resolve(source)

    def test_rfc6901_escapes_and_the_empty_pointer_pass_the_declaration_check(self):
        self._write("records/escaped.json", json.dumps({
            "a/b": "v1.0.0", "c~d": "https://github.com/example/escaped", "": "v2.0.0"}))
        escaped = self._one(self._pointer(path="records/escaped.json", pin_pointer="/a~1b",
                                          repository_pointer="/c~0d"))
        self.assertEqual((escaped["repository"], escaped["pin"], escaped["error"]),
                         ("https://github.com/example/escaped", "v1.0.0", None))
        # "/" is the member named "" and the empty pointer is the whole document: both pass the
        # declaration check; the second does not resolve to a pin, which is an entry error.
        self.assertEqual(self._one(self._pointer(path="records/escaped.json", pin_pointer="/",
                                                 repository_pointer="/c~0d"))["pin"], "v2.0.0")
        whole = self._one(self._pointer(path="records/escaped.json", pin_pointer="", repository_pointer="/c~0d"))
        self.assertIn("pin is not a non-empty string", whole["error"])

    WATCH = {"id": "watch:x", "group": "coding-agent", "repository": "https://github.com/example/x"}

    def test_a_tags_declaration_is_carried_on_pin_and_watch_entries_as_a_copy(self):
        tags = {"prefix": "v", "pattern": r"^v(\d+\.\d+\.\d+)$"}
        entries = {entry["id"]: entry for entry in self._resolve(
            dict(self._row("alpha"), tags=tags), self._pointer(), watch_sources=(dict(self.WATCH, tags=tags),))}
        for entry_id in ("row:alpha", "watch:x"):
            with self.subTest(entry=entry_id):
                self.assertEqual(entries[entry_id]["tags"], tags)
                self.assertIsNot(entries[entry_id]["tags"], tags)
        self.assertIsNone(entries["pointer:worker"]["tags"])

    def test_an_empty_prefix_and_the_literal_punctuation_are_accepted(self):
        for prefix in ("", "v", "deepagents==", "rust-v", "a_b.c+d"):
            with self.subTest(prefix=prefix):
                tags = {"prefix": prefix, "pattern": rf"^{re.escape(prefix)}(\d+\.\d+\.\d+)$"}
                self.assertEqual(self._one(dict(self._row("alpha"), tags=tags))["tags"], tags)
                self.assertEqual(self._resolve(watch_sources=(dict(self.WATCH, tags=tags),))[0]["tags"], tags)

    def test_malformed_tag_declarations_raise_for_pin_and_watch_sources(self):
        good = r"^v(\d+\.\d+\.\d+)$"
        cases = {
            "not a mapping": "v",
            "missing pattern": {"prefix": "v"},
            "missing prefix": {"pattern": good},
            "an extra key": {"prefix": "v", "pattern": good, "flags": "i"},
            "pattern not anchored at the start": {"prefix": "v", "pattern": r"v(\d+\.\d+\.\d+)$"},
            "pattern not anchored at the end": {"prefix": "v", "pattern": r"^v(\d+\.\d+\.\d+)"},
            "pattern ending in an escaped dollar": {"prefix": "v", "pattern": r"^v(\d+\.\d+\.\d+)\$"},
            "two capture groups": {"prefix": "v", "pattern": r"^v(\d+)\.(\d+)$"},
            "no capture group": {"prefix": "v", "pattern": r"^v\d+\.\d+$"},
            "pattern that does not compile": {"prefix": "v", "pattern": r"^v(\d+\.\d+$"},
            "pattern that is not a string": {"prefix": "v", "pattern": None},
            "prefix that is not a string": {"prefix": None, "pattern": good},
            "prefix with a slash": {"prefix": "refs/tags/v", "pattern": good},
            "prefix with ..": {"prefix": "v..", "pattern": good},
            "prefix with whitespace": {"prefix": "v ", "pattern": good},
            "prefix with a query": {"prefix": "v?per_page=1", "pattern": good},
            "prefix with a percent escape": {"prefix": "v%2F", "pattern": good},
            "prefix with a fragment": {"prefix": "v#", "pattern": good},
        }
        for label, tags in cases.items():
            with self.subTest(label=label, kind="pin"), self.assertRaisesRegex(ValueError, "tags"):
                self._resolve(dict(self._row("alpha"), tags=tags))
            with self.subTest(label=label, kind="watch"), self.assertRaisesRegex(ValueError, "tags"):
                self._resolve(watch_sources=(dict(self.WATCH, tags=tags),))
        # A pattern that ends in an escaped backslash and then "$" is anchored.
        self._resolve(dict(self._row("alpha"), tags={"prefix": "v", "pattern": r"^v(\d+\.\d+)\\$"}))


class GithubFreshnessReadsRuntimePinsTests(unittest.TestCase):
    def test_tag_declared_prerelease_does_not_fetch_unused_list_or_suppress_shared_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            (work / "foundation-layers.json").write_text(json.dumps({"layers": [{"components": [
                {"id": "stable", "repository": TAGGED_REPOSITORY, "version": "1.0.0"}]}]}))
            runtime = {"entries": [{"id": "tagged", "repository": TAGGED_REPOSITORY,
                                    "pin": "1.0.0rc5", "kind": "pin_source",
                                    "tags": {"prefix": "v", "pattern": r"^v(\d+\.\d+)$"}}]}
            (work / "runtime-pins.json").write_text(json.dumps(runtime))
            calls = []
            base_api = _fake_gh_api(calls)

            def api(path, timeout=60, *, paginate=False):
                if path.endswith("/releases/latest"):
                    calls.append((path, paginate))
                    return {"tag_name": "v1.1.0", "published_at": "2026-10-02T00:00:00Z"}, None
                if "/releases?" in path:
                    calls.append((path, paginate))
                    return None, "HTTP 503: Service Unavailable"
                return base_api(path, timeout, paginate=paginate)

            with mock.patch.object(github_freshness, "gh_api", side_effect=api), redirect_stdout(StringIO()):
                self.assertEqual(github_freshness.main(["--work-dir", str(work), "--workers", "1"]), 0)
            document = json.loads((work / "github-freshness.json").read_text())
            repositories = document["repositories"]
            upstream = build_manifest.compute_upstream(TAGGED_REPOSITORY, repositories, pin="1.0.0")
            old = {"id": "stable", "repository": TAGGED_REPOSITORY, "pin": "1.0.0",
                   "upstream": {"latest": "v1.0.0", "pushed_at": "2026-10-01"},
                   "pin_behind_upstream": False}
            new = {**old, "upstream": upstream, **build_manifest.pin_comparison_fields(
                build_manifest.classify_pin("1.0.0", TAGGED_REPOSITORY, upstream["latest"]))}
            drifted, unfetched, no_release = fp.compute_drift({"stable": old}, {"stable": new}, repositories)
            self.assertEqual([row[0] for row in drifted], ["stable"])
            self.assertEqual((unfetched, no_release), ([], []))
            self.assertEqual(document["partial_errors"], 0)
            self.assertFalse(any("/releases?" in path for path, _ in calls))
            tagged = build_manifest.build_runtime_freshness(runtime, repositories, CHECKED_AT)["entries"][0]
            self.assertIs(tagged["pin_behind_upstream"], True)

    def test_another_stream_pin_for_a_tagged_slug_still_requires_the_release_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            tagged = {"repository": TAGGED_REPOSITORY, "pin": "1.0.0rc5", "tags": {"prefix": "v"}}
            for filename, stream in (
                ("foundation-layers.json", {"version": "1.0.0rc5"}),
                ("trading-catalog.json", {"version_or_commit": "1.0.0rc5"}),
                ("trading-pins.json", {"pin": "1.0.0rc5"}),
                ("runtime-pins.json", {"pin": "1.0.0rc5"}),
            ):
                with self.subTest(filename=filename):
                    (work / "runtime-pins.json").write_text(json.dumps({"entries": [tagged]}))
                    entries = [{"repository": TAGGED_REPOSITORY, **stream}]
                    document = {"layers": [{"components": entries}]} if filename == "foundation-layers.json" \
                        else {"entries": ([tagged] if filename == "runtime-pins.json" else []) + entries}
                    path = work / filename
                    path.write_text(json.dumps(document))
                    self.assertEqual(github_freshness.collect_prerelease_slugs(work), {TAGGED_SLUG})
                    path.unlink()

    def test_runtime_repositories_are_collected_and_the_file_is_optional(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            (work / "trading-catalog.json").write_text(json.dumps(
                {"entries": [{"repository": "https://github.com/example/card"}]}), encoding="utf-8")
            self.assertEqual(github_freshness.collect_repository_urls(work), {"https://github.com/example/card"})
            (work / "runtime-pins.json").write_text(json.dumps({"entries": [
                {"id": "new-wsl:x", "repository": "https://github.com/example/runtime"},
                {"id": "new-wsl:moved", "repository": None, "error": "plan.json#/owners slot 'x': 0 rows match"},
            ]}), encoding="utf-8")
            self.assertEqual(github_freshness.collect_repository_urls(work),
                             {"https://github.com/example/card", "https://github.com/example/runtime"})


class _FakeProc:
    def __init__(self, returncode, stdout="", stderr=""):
        self.returncode, self.stdout, self.stderr = returncode, stdout, stderr


TAGGED_SLUG = "example/a-tagged"
# Mixed case on purpose: the declared prefixes are keyed by the normalized slug.
TAGGED_REPOSITORY = "https://github.com/Example/A-Tagged"
PLAIN_REPOSITORY = "https://github.com/example/b-plain"
TAGGED_NAMES = ["0.3.276", "release/2025-11-28", "v1.0", "v1.2"]


def _fake_gh_api(calls, failing=(), primary_failing=(), releases_failing=()):
    """A github_freshness.gh_api stand-in that records (path, paginate). Every repository
    exists with no release and no tag listing and a resolvable head commit; matching-refs
    lists the TAGGED_NAMES under the prefix for TAGGED_SLUG (none for another repository)
    unless (slug, prefix) is in ``failing``, which fails like a GitHub 503. A slug in
    ``primary_failing`` fails its repos/{slug} call, and one in ``releases_failing`` its
    releases/latest call, both like a GitHub 503: github_freshness.py keeps the first as
    the record's "error" and the second, not an ordinary "not found", in "partial_errors"."""
    def fake(path, timeout=60, *, paginate=False):
        calls.append((path, paginate))
        _, owner, repo, *rest = path.split("/")
        slug, rest = f"{owner}/{repo}", "/".join(rest)
        if not rest:
            if slug in primary_failing:
                return None, "HTTP 503: Service Unavailable"
            return {"full_name": slug, "default_branch": "main", "pushed_at": "2026-10-02T00:00:00Z"}, None
        if rest == "releases/latest":
            if slug in releases_failing:
                return None, "HTTP 503: Service Unavailable"
            return None, "HTTP 404: Not Found"
        if rest == "tags?per_page=1":
            return [], None
        if rest == "commits/main":
            return {"sha": "abc", "commit": {"committer": {"date": "2026-10-02T00:00:00Z"}}}, None
        if rest.startswith("git/matching-refs/tags/"):
            prefix = rest[len("git/matching-refs/tags/"):]
            if (slug, prefix) in failing:
                return None, "HTTP 503: Service Unavailable"
            names = TAGGED_NAMES if slug == TAGGED_SLUG else []
            return [{"ref": f"refs/tags/{name}", "object": {"type": "commit"}} for name in names
                    if name.startswith(prefix)], None
        return None, f"unexpected path {path}"

    return fake


def _matching_calls(calls):
    return sorted(call for call in calls if "/git/matching-refs/" in call[0])


BOTH_PREFIX_CALLS = [(f"repos/{TAGGED_SLUG}/git/matching-refs/tags/", True),
                     (f"repos/{TAGGED_SLUG}/git/matching-refs/tags/v", True)]


class GithubFreshnessMatchingTagsTests(unittest.TestCase):
    """The matching-refs fetch for the tag prefixes runtime-pins.json declares (gh_api mocked)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.work = Path(self._tmp.name)
        self.out = self.work / "github-freshness.json"
        (self.work / "foundation-layers.json").write_text(json.dumps({"layers": [{"components": [
            {"repository": TAGGED_REPOSITORY}, {"repository": PLAIN_REPOSITORY}]}]}), encoding="utf-8")

    def _write_runtime_pins(self, *prefixes, extra=()):
        entries = [{"id": f"tagged:{index}", "repository": TAGGED_REPOSITORY,
                    "tags": {"prefix": prefix, "pattern": r"^(\d+\.\d+\.\d+)$"}}
                   for index, prefix in enumerate(prefixes)]
        entries += [{"id": "plain", "repository": PLAIN_REPOSITORY, "tags": None}, *extra]
        (self.work / "runtime-pins.json").write_text(json.dumps({"entries": entries}), encoding="utf-8")

    def _main(self, failing=()):
        calls = []
        with mock.patch.object(github_freshness, "gh_api", _fake_gh_api(calls, failing)), \
                redirect_stdout(StringIO()):
            self.assertEqual(github_freshness.main(["--work-dir", str(self.work), "--workers", "1"]), 0)
        return calls, json.loads(self.out.read_text(encoding="utf-8"))

    def test_declared_prefixes_are_collected_once_per_repository(self):
        self._write_runtime_pins("v", "", "v", extra=(
            {"id": "unresolved", "repository": None, "tags": {"prefix": "x", "pattern": r"^x(\d+\.\d+)$"}},
            {"id": "tampered", "repository": "https://github.com/example/c-tampered",
             "tags": {"prefix": "../../user", "pattern": r"^(\d+\.\d+)$"}},
        ))
        self.assertEqual(github_freshness.collect_declared_tag_prefixes(self.work), {TAGGED_SLUG: ("", "v")})
        (self.work / "runtime-pins.json").unlink()
        self.assertEqual(github_freshness.collect_declared_tag_prefixes(self.work), {})

    def test_paginate_adds_the_flag_after_the_path_only_when_asked(self):
        commands = []

        def fake_run(command, capture_output=True, text=True, timeout=60):
            commands.append(command)
            return _FakeProc(0, stdout="[]")

        with mock.patch("subprocess.run", side_effect=fake_run):
            self.assertEqual(github_freshness.gh_api("repos/a/b/git/matching-refs/tags/", paginate=True), ([], None))
            self.assertEqual(github_freshness.gh_api("repos/a/b/tags?per_page=1"), ([], None))
        self.assertEqual(commands, [["gh", "api", "repos/a/b/git/matching-refs/tags/", "--paginate"],
                                    ["gh", "api", "repos/a/b/tags?per_page=1"]])

    def test_fetch_lists_each_declared_prefix_once_by_name_and_keeps_the_other_calls(self):
        calls = []
        with mock.patch.object(github_freshness, "gh_api", _fake_gh_api(calls)):
            record = github_freshness.fetch_repository(TAGGED_SLUG, tag_prefixes=("", "v", "v"))
            plain = github_freshness.fetch_repository("example/b-plain")
        # The empty prefix lists every tag: git/matching-refs/tags/.
        self.assertEqual(calls[:6], [
            (f"repos/{TAGGED_SLUG}", False), (f"repos/{TAGGED_SLUG}/releases/latest", False),
            (f"repos/{TAGGED_SLUG}/tags?per_page=1", False), (f"repos/{TAGGED_SLUG}/commits/main", False),
            *BOTH_PREFIX_CALLS,
        ])
        self.assertEqual(record["matching_tags"], {"": TAGGED_NAMES, "v": ["v1.0", "v1.2"]})
        self.assertNotIn("partial_errors", record)
        # Without declared prefixes the calls and the record are what they were.
        self.assertEqual(calls[6:], [("repos/example/b-plain", False), ("repos/example/b-plain/releases/latest", False),
                                     ("repos/example/b-plain/tags?per_page=1", False),
                                     ("repos/example/b-plain/commits/main", False)])
        self.assertNotIn("matching_tags", plain)

    def test_main_lists_tags_only_for_the_declared_repository_and_prefixes(self):
        self._write_runtime_pins("", "v", "v")
        calls, document = self._main()
        self.assertEqual(_matching_calls(calls), BOTH_PREFIX_CALLS)
        records = document["repositories"]
        self.assertEqual(records[TAGGED_REPOSITORY]["matching_tags"], {"": TAGGED_NAMES, "v": ["v1.0", "v1.2"]})
        self.assertNotIn("matching_tags", records[PLAIN_REPOSITORY])
        self.assertEqual((document["errors"], document["partial_errors"]), (0, 0))

    def test_a_failed_list_is_kept_apart_from_partial_errors_and_retried_on_the_next_run(self):
        self._write_runtime_pins("", "v")
        _, document = self._main(failing={(TAGGED_SLUG, "v")})
        tagged = document["repositories"][TAGGED_REPOSITORY]
        self.assertEqual(tagged["matching_tags_errors"], {"v": "HTTP 503: Service Unavailable"})
        self.assertNotIn("partial_errors", tagged)
        self.assertEqual(tagged["matching_tags"], {"": TAGGED_NAMES})
        # The batch went on: the repository fetched after it has its record.
        self.assertEqual(document["repositories"][PLAIN_REPOSITORY]["full_name"], "example/b-plain")
        self.assertEqual((document["errors"], document["partial_errors"], document["matching_tags_errors"]),
                         (0, 0, 1))
        # The next run retries the incomplete record, and only it (the resume is per
        # repository, so the failed prefix is listed again with the others).
        calls, document = self._main()
        self.assertEqual(_matching_calls(calls), BOTH_PREFIX_CALLS)
        self.assertFalse(any(path.startswith("repos/example/b-plain") for path, _ in calls))
        tagged = document["repositories"][TAGGED_REPOSITORY]
        self.assertEqual(tagged["matching_tags"], {"": TAGGED_NAMES, "v": ["v1.0", "v1.2"]})
        self.assertNotIn("matching_tags_errors", tagged)
        self.assertEqual((document["partial_errors"], document["matching_tags_errors"]), (0, 0))

    def test_a_failed_list_changes_no_row_but_the_runtime_row_of_its_prefix(self):
        """The record a failed matching-refs call leaves, read the way the daily job reads
        it: the drift and trading rows of the repository stay reliable and the propose
        gate's partial-error count stays 0; the runtime row says tag_pattern_unfetched."""
        self._write_runtime_pins("")
        _, failed = self._main(failing={(TAGGED_SLUG, "")})
        _, recovered = self._main()
        failed_records, recovered_records = failed["repositories"], recovered["repositories"]
        self.assertEqual(failed_records[TAGGED_REPOSITORY]["matching_tags_errors"],
                         {"": "HTTP 503: Service Unavailable"})
        self.assertEqual((fp.upstream_partial_error_count(failed), failed["matching_tags_errors"]), (0, 1))
        self.assertFalse(fp._freshness_record_has_error(TAGGED_REPOSITORY, failed_records))

        def drift(records):
            row = {"id": "tagged", "repository": TAGGED_REPOSITORY, "pin": "1.0.0", "pin_behind_upstream": None,
                   "upstream": build_manifest.compute_upstream(TAGGED_REPOSITORY, records)}
            return fp.compute_drift({"tagged": dict(row)}, {"tagged": row}, records)

        def trading(records):
            card = {"id": "tagged", "repository": TAGGED_REPOSITORY, "decision": "default",
                    "version_or_commit": "1.0.0"}
            document = build_manifest.build_trading_freshness(
                {"taxonomy": {"evaluation": ["evaluation"]}, "layers": {"evaluation": [card]}}, None, records,
                CHECKED_AT)
            return fp.trading_freshness_rows(document, records)

        # Fetched with no release: the drift row is "no release", not unfetched, as after a good run.
        self.assertEqual(drift(failed_records), ([], [], ["tagged"]))
        self.assertEqual(drift(failed_records), drift(recovered_records))
        self.assertEqual(trading(failed_records)[3], [])
        self.assertEqual(trading(failed_records), trading(recovered_records))

        entry = _inspect_entry(id="new-wsl:tagged", repository=TAGGED_REPOSITORY,
                               tags={"prefix": "", "pattern": r"^(\d+\.\d+\.\d+)$"})

        def runtime(records):
            return build_manifest.build_runtime_freshness({"entries": [entry]}, records, CHECKED_AT)

        failed_runtime = runtime(failed_records)
        self.assertEqual(failed_runtime["entries"][0]["upstream"], {
            **build_manifest.compute_upstream(TAGGED_REPOSITORY, failed_records),
            "latest_source": "tag_pattern_unfetched"})
        self.assertEqual(runtime(recovered_records)["entries"][0]["upstream"]["latest"], "0.3.276")
        markdown, summary = fp.render_runtime_markdown(failed_runtime, failed_records)
        self.assertEqual(summary["runtime_unfetched"], [])
        self.assertIn(fp.md_cell("new-wsl:tagged (tag_pattern_unfetched)"), markdown)

    def test_at_most_the_cap_of_names_is_stored_per_prefix_and_a_cut_is_recorded(self):
        self.assertEqual(github_freshness.MATCHING_TAGS_CAP, 5000)
        for listed, truncated in ((5000, False), (5001, True)):
            names = [f"0.0.{index}" for index in range(listed)]
            fake = _fake_gh_api([])

            def listing(path, timeout=60, *, paginate=False):
                if "/git/matching-refs/" in path:
                    return [{"ref": f"refs/tags/{name}"} for name in names], None
                return fake(path, timeout, paginate=paginate)

            with self.subTest(listed=listed), mock.patch.object(github_freshness, "gh_api", listing):
                record = github_freshness.fetch_repository(TAGGED_SLUG, tag_prefixes=("",))
                # The first names in the API's order are kept.
                self.assertEqual(record["matching_tags"], {"": names[:5000]})
                self.assertEqual(record.get("matching_tags_truncated"), True if truncated else None)
                self.assertNotIn("matching_tags_errors", record)

    def test_a_failed_list_keeps_a_short_reason(self):
        with mock.patch.object(github_freshness, "gh_api", _fake_gh_api([])), \
                mock.patch.object(github_freshness, "fetch_matching_tag_names", return_value=(None, "x" * 500)):
            record = github_freshness.fetch_repository(TAGGED_SLUG, tag_prefixes=("",))
        self.assertEqual(record["matching_tags_errors"], {"": "x" * 160})
        self.assertEqual(record["matching_tags"], {})

    def test_a_record_without_a_list_for_a_declared_prefix_is_pending_on_the_next_run(self):
        self._write_runtime_pins("v")
        self._main()
        calls, _ = self._main()
        self.assertEqual(calls, [])
        # A prefix declared since: that repository is fetched again with every declared prefix.
        self._write_runtime_pins("v", "")
        calls, document = self._main()
        self.assertEqual(_matching_calls(calls), BOTH_PREFIX_CALLS)
        self.assertFalse(any(path.startswith("repos/example/b-plain") for path, _ in calls))
        self.assertEqual(document["repositories"][TAGGED_REPOSITORY]["matching_tags"],
                         {"": TAGGED_NAMES, "v": ["v1.0", "v1.2"]})

    def test_a_record_is_covered_only_with_a_list_for_every_declared_prefix(self):
        declared = {TAGGED_SLUG: ("", "v")}
        complete = {"slug": TAGGED_SLUG, "matching_tags": {"": [], "v": ["v1.0"]}}
        self.assertTrue(github_freshness.record_is_covered(complete, declared))
        self.assertTrue(github_freshness.record_is_covered({"slug": "example/b-plain"}, declared))
        cases = {
            "a missing prefix": {"slug": TAGGED_SLUG, "matching_tags": {"v": ["v1.0"]}},
            "no matching_tags": {"slug": TAGGED_SLUG},
            "a value that is not a list": {"slug": TAGGED_SLUG, "matching_tags": {"": None, "v": []}},
            "a mixed-case slug missing a prefix": {"slug": "Example/A-Tagged", "matching_tags": {"v": []}},
            "a partial error": dict(complete, partial_errors={"releases": "HTTP 503"}),
            # Even for a prefix no longer declared: the next run fetches the record again.
            "a failed list": dict(complete, matching_tags_errors={"x": "HTTP 503"}),
            "an error": dict(complete, error="timeout"),
        }
        for label, record in cases.items():
            with self.subTest(case=label):
                self.assertFalse(github_freshness.record_is_covered(record, declared))


MOVED_ERROR ="plan/install-plan.json#/owners slot 'gpt-gateway': 0 rows match, expected exactly one"


def _runtime_pins():
    plan_row = {"path": "plan/install-plan.json", "row": {"array": "/owners", "key": "slot", "value": "x"}}
    return {"entries": [
        {"id": "new-wsl:behind", "group": "native-client", "kind": "pin_source",
         "repository": "https://github.com/example/behind", "pin": "rust-v1.0.0", "pin_source": plan_row,
         "named_in": None, "error": None},
        {"id": "new-wsl:current", "group": "agent-sdk", "kind": "pin_source",
         "repository": "https://github.com/example/current", "pin": "2.0.0", "pin_source": plan_row,
         "named_in": None, "error": None},
        {"id": "new-wsl:moved", "group": "gateway", "kind": "pin_source", "repository": None, "pin": None,
         "pin_source": plan_row, "named_in": None, "error": MOVED_ERROR},
        {"id": "watch:idle", "group": "coding-agent", "kind": "watch_only",
         "repository": "https://github.com/example/idle", "pin": None, "pin_source": None,
         "named_in": "catalogs/saturation/ledger.json", "error": None},
    ]}


def _repositories():
    return {
        "https://github.com/example/behind": {
            "slug": "example/behind", "pushed_at": "2026-09-30T00:00:00Z", "archived": False,
            "latest_release": {"tag": "rust-v1.1.0", "published_at": "2026-09-20T00:00:00Z"},
            "head": {"date": "2026-09-30T00:00:00Z"},
        },
        "https://github.com/example/current": {
            "slug": "example/current", "pushed_at": "2026-09-28T00:00:00Z", "archived": False,
            "latest_release": {"tag": "v2.0.0", "published_at": "2026-09-01T00:00:00Z"},
            "head": {"date": "2026-09-28T00:00:00Z"},
        },
        # Idle since 2025-12-01 (305 days before CHECKED_AT) and archived.
        "https://github.com/example/idle": {
            "slug": "example/idle", "pushed_at": "2025-12-01T00:00:00Z", "archived": True,
            "latest_release": None, "head": {"date": "2025-12-01T00:00:00Z"},
        },
    }


INSPECT_REPOSITORY = "https://github.com/UKGovernmentBEIS/inspect_ai"
DEEPAGENTS_REPOSITORY = "https://github.com/langchain-ai/deepagents"


def _inspect_entry(**overrides):
    """new-wsl:inspect-ai as extract_layers.py writes it: a pin and the declared tag pattern."""
    entry = {"id": "new-wsl:inspect-ai", "group": "evaluation-harness", "kind": "pin_source",
             "repository": INSPECT_REPOSITORY, "pin": "0.3.273",
             "pin_source": {"path": "plan/install-plan.json",
                            "row": {"array": "/owners", "key": "slot", "value": "inspect-ai"}},
             "named_in": None, "error": None, "tags": dict(DECLARED_TAGS["new-wsl:inspect-ai"])}
    entry.update(overrides)
    return entry


def _inspect_record(**overrides):
    """A record shaped like inspect_ai's: no release, a first tag in name order that is not
    version-shaped (compute_upstream withholds it), and the tags under the empty prefix."""
    record = {"slug": "ukgovernmentbeis/inspect_ai", "pushed_at": "2026-10-02T00:00:00Z", "archived": False,
              "latest_tag": "release/2025-11-28", "head": {"date": "2026-10-02T00:00:00Z"},
              "matching_tags": {"": list(INSPECT_LIKE_TAGS)}}
    record.update(overrides)
    return record


def _deepagents_entry():
    return {"id": "watch:deepagents", "group": "runtime-worker", "kind": "watch_only",
            "repository": DEEPAGENTS_REPOSITORY, "pin": None, "pin_source": None,
            "named_in": "catalogs/landscape/foundation.json", "error": None,
            "tags": dict(DECLARED_TAGS["watch:deepagents"])}


def _deepagents_record(**overrides):
    """Deep Agents' latest release is another package's; matching-refs lists only deepagents== tags."""
    record = {"slug": "langchain-ai/deepagents", "pushed_at": "2026-10-02T00:00:00Z", "archived": False,
              "latest_release": {"tag": "deepagents-cli==1.0.0", "published_at": "2026-10-01T00:00:00Z",
                                 "prerelease": False},
              "head": {"date": "2026-10-02T00:00:00Z"},
              "matching_tags": {"deepagents==": [name for name in DEEPAGENTS_LIKE_TAGS
                                                 if name.startswith("deepagents==")]}}
    record.update(overrides)
    return record


class BuildRuntimeFreshnessTests(unittest.TestCase):
    def setUp(self):
        self.doc = build_manifest.build_runtime_freshness(_runtime_pins(), _repositories(), CHECKED_AT)
        self.rows = {row["id"]: row for row in self.doc["entries"]}

    def test_one_row_per_entry_with_the_extracted_fields_first(self):
        self.assertEqual(list(self.rows), ["new-wsl:behind", "new-wsl:current", "new-wsl:moved", "watch:idle"])
        self.assertEqual(list(self.rows["new-wsl:behind"])[:9], [
            "id", "group", "kind", "repository", "pin", "pin_source", "named_in", "error", "upstream"])
        self.assertEqual(self.rows["new-wsl:moved"]["error"], MOVED_ERROR)

    def test_a_pinned_row_uses_the_manifest_rule(self):
        behind, current = self.rows["new-wsl:behind"], self.rows["new-wsl:current"]
        self.assertEqual((behind["upstream"]["latest"], behind["pin_behind_upstream"], behind["pin_comparison"]),
                         ("rust-v1.1.0", True, "compared"))
        self.assertEqual((current["upstream"]["latest"], current["pin_behind_upstream"], current["pin_comparison"]),
                         ("v2.0.0", False, "compared"))

    def test_watch_and_unresolved_rows_are_not_compared(self):
        fields = ("pin_behind_upstream", "pin_comparison", "pin_comparison_reason")
        self.assertEqual([self.rows["watch:idle"][field] for field in fields], [None, "not_compared", "watch_only"])
        self.assertEqual([self.rows["new-wsl:moved"][field] for field in fields],
                         [None, "not_compared", "source_unresolved"])
        # A watch row still reports upstream activity; a row without a repository has none.
        self.assertIs(self.rows["watch:idle"]["upstream"]["archived"], True)
        self.assertEqual(self.rows["new-wsl:moved"]["upstream"], {})

    def test_an_upstream_without_a_version_shaped_release_is_not_compared(self):
        pins = {"entries": [dict(_runtime_pins()["entries"][1], repository="https://github.com/example/tagless",
                                 pin="0.3.273")]}
        repositories = {"https://github.com/example/tagless": {
            "slug": "example/tagless", "pushed_at": "2026-09-30T00:00:00Z", "latest_release": None,
            "latest_tag": None, "head": {"date": "2026-09-30T00:00:00Z"},
        }}
        row = build_manifest.build_runtime_freshness(pins, repositories, CHECKED_AT)["entries"][0]
        self.assertEqual((row["pin_behind_upstream"], row["pin_comparison"], row["pin_comparison_reason"]),
                         (None, "not_compared", "unversioned"))

    def test_dormancy(self):
        idle = self.rows["watch:idle"]["dormancy"]
        self.assertEqual((idle["dormant"], idle["days_since_activity"], idle["last_commit_at"]),
                         (True, 305, "2025-12-01"))
        self.assertIs(self.rows["new-wsl:behind"]["dormancy"]["dormant"], False)
        moved = self.rows["new-wsl:moved"]["dormancy"]
        self.assertEqual((moved["dormant"], moved["reason"]), (None, "not_fetched"))

    def test_counts_and_document_fields(self):
        self.assertEqual(self.doc["counts"], {
            "entries": 4, "pin_source": 3, "watch_only": 1, "unresolved": 1, "pin_behind_upstream": 1,
            "not_compared": 2, "dormant": 1, "dormancy_unknown": 1, "archived": 1,
        })
        self.assertEqual((self.doc["schema"], self.doc["checked_at"], self.doc["dormancy_threshold_days"],
                          self.doc["dormancy_rule"]),
                         ("runtime-freshness/1", CHECKED_AT, 180, build_manifest.DORMANCY_RULE))

    def test_without_runtime_pins_the_document_has_no_rows(self):
        doc = build_manifest.build_runtime_freshness(None, _repositories(), CHECKED_AT)
        self.assertEqual((doc["entries"], doc["counts"]["entries"]), ([], 0))


class MatchingTagSelectionTests(unittest.TestCase):
    """build_manifest.select_matching_tag with the checked-in patterns (CHECKED_IN_TAGS)."""

    def test_each_pattern_selects_the_highest_version_whatever_the_name_order(self):
        self.assertEqual(set(CHECKED_IN_TAGS), set(TAG_EXAMPLES))
        for entry_id, (names, expected, count) in TAG_EXAMPLES.items():
            pattern = CHECKED_IN_TAGS[entry_id]["pattern"]
            with self.subTest(entry=entry_id):
                for ordered in (names, list(reversed(names)), sorted(names)):
                    self.assertEqual(build_manifest.select_matching_tag(ordered, pattern), (expected, count))
                # The API's name order ends on another tag: the greatest matching name.
                self.assertNotEqual(max(name for name in names if re.fullmatch(pattern, name)), expected)

    def test_prereleases_other_packages_and_major_only_tags_are_never_selected(self):
        cases = {
            "new-wsl:inspect-ai": ["release/2025-11-28", "0.3.277rc1", "0.4.0-dev", "inspect-tool-support-1.2.0"],
            "watch:deepagents": ["deepagents-talon==0.0.9", "deepagents-cli==1.0.0", "deepagents==1.0.0a1"],
            "watch:codex-action": ["v1", "v2-beta", "v1.12.0-rc.1"],
        }
        for entry_id, names in cases.items():
            with self.subTest(entry=entry_id):
                self.assertEqual(build_manifest.select_matching_tag(names, CHECKED_IN_TAGS[entry_id]["pattern"]),
                                 (None, 0))

    def test_each_prefix_starts_every_example_name_its_pattern_matches(self):
        names = [name for examples, _, _ in TAG_EXAMPLES.values() for name in examples]
        self.assertEqual(set(CHECKED_IN_TAGS), set(TAG_EXAMPLES))
        for entry_id, tags in CHECKED_IN_TAGS.items():
            with self.subTest(entry=entry_id):
                matched = [name for name in names if re.fullmatch(tags["pattern"], name)]
                self.assertTrue(matched)
                self.assertEqual([name for name in matched if not name.startswith(tags["prefix"])], [])

    def test_a_tie_goes_to_the_greater_name_and_only_a_dotted_capture_is_ranked(self):
        for names in (["1.2.3", "v1.2.3"], ["v1.2.3", "1.2.3"]):
            with self.subTest(names=names):
                self.assertEqual(build_manifest.select_matching_tag(names, r"^v?(\d+\.\d+\.\d+)$"), ("v1.2.3", 2))
        self.assertEqual(build_manifest.select_matching_tag(["v1", "v2"], r"^v(\d+)$"), (None, 0))
        self.assertEqual(build_manifest.select_matching_tag(["v1.2-beta", "v1.x"], r"^v(.+)$"), (None, 0))

    def test_parse_version_reads_each_selected_tag(self):
        # classify_pin compares the selected full tag name through parse_version.
        self.assertEqual([build_manifest.parse_version(expected) for _, expected, _ in TAG_EXAMPLES.values()],
                         [(0, 3, 276), (0, 7, 21), (1, 12, 0)])

    def test_a_tag_in_fullwidth_digits_is_never_selected(self):
        # 0.3.277 in fullwidth digits: int() reads them, so without re.ASCII it would outrank 0.3.276.
        fullwidth = "\uff10.\uff13.\uff12\uff17\uff17"
        inspect = CHECKED_IN_TAGS["new-wsl:inspect-ai"]["pattern"]
        self.assertEqual(build_manifest.select_matching_tag(["0.3.276", fullwidth], inspect), ("0.3.276", 1))
        # A capture that admits any character still ranks only ASCII digits (DOTTED_VERSION_RE) ...
        self.assertEqual(build_manifest.select_matching_tag(["v0.3.276", "v" + fullwidth], r"^v(.+)$"),
                         ("v0.3.276", 1))
        # ... and a declared pattern matches only ASCII digits outside its capture too.
        self.assertEqual(build_manifest.select_matching_tag(["0.3.275", "0.3.276.post\uff11"],
                                                            r"^(\d+\.\d+\.\d+)(?:\.post\d+)?$"),
                         ("0.3.275", 1))

    def test_a_missing_or_uncompilable_pattern_selects_nothing_instead_of_raising(self):
        patterns = {
            "missing": None, "not a string": 7,
            "a syntax error": r"^(\d+\.\d+$",
            "flags that conflict with re.ASCII": r"(?u)^(\d+\.\d+\.\d+)$",
            "a repeat count too large": r"^(\d{4294967296})$",
            "nesting too deep": "^" + "(" * 3000 + r"\d" + ")" * 3000 + "$",
        }
        for label, pattern in patterns.items():
            with self.subTest(pattern=label):
                self.assertEqual(build_manifest.select_matching_tag(["0.3.276"], pattern), (None, 0))


class RuntimeTagPatternRowTests(unittest.TestCase):
    """build_runtime_freshness for entries that declare a tag pattern."""

    def _row(self, entry, repositories):
        return build_manifest.build_runtime_freshness({"entries": [entry]}, repositories, CHECKED_AT)["entries"][0]

    def test_tag_declared_prerelease_keeps_release_fallback_when_the_tag_list_is_missing(self):
        record = _inspect_record(matching_tags={}, latest_release={
            "tag": "v1.1.0", "published_at": "2026-10-01T00:00:00Z"})
        row = self._row(_inspect_entry(pin="1.0.0rc5"), {INSPECT_REPOSITORY: record})
        self.assertEqual(row["upstream"]["latest_source"], "tag_pattern_unfetched")
        self.assertEqual(row["upstream"]["latest"], "v1.1.0")
        self.assertNotIn("latest_flag", row["upstream"])

    def test_prerelease_pin_keeps_numeric_comparison_for_a_prefixed_tag_declaration(self):
        prefix = "inspect-tool-support-"
        entry = _inspect_entry(pin="1.1.0rc5", tags={"prefix": prefix,
                                                  "pattern": r"^inspect-tool-support-(\d+\.\d+\.\d+)$"})
        record = _inspect_record(matching_tags={prefix: [prefix + "1.0.0", prefix + "1.2.0"]})
        row = self._row(entry, {INSPECT_REPOSITORY: record})
        self.assertEqual(row["upstream"]["latest"], prefix + "1.2.0")
        self.assertEqual((row["pin_comparison"], row["pin_behind_upstream"], row.get("pin_comparison_reason")),
                         ("compared", True, None))

    def test_the_inspect_row_is_compared_with_its_highest_version_tag(self):
        repositories = {INSPECT_REPOSITORY: _inspect_record()}
        row = self._row(_inspect_entry(), repositories)
        upstream = row["upstream"]
        self.assertEqual((upstream["latest"], upstream["latest_source"], upstream["matching_tag_count"]),
                         ("0.3.276", "matching_tag", 4))
        self.assertEqual((row["pin_comparison"], row["pin_behind_upstream"]), ("compared", True))
        # compute_upstream withheld the first tag in name order; with a latest selected it is
        # no longer withheld in place of one, so latest_flag is dropped. released_at and
        # prerelease describe a GitHub release, not this tag: null. Every other field is
        # compute_upstream's.
        expected = build_manifest.compute_upstream(INSPECT_REPOSITORY, repositories)
        self.assertIsNone(expected["latest"])
        self.assertEqual(expected["latest_flag"]["tag"], "release/2025-11-28")
        self.assertNotIn("latest_flag", upstream)
        self.assertEqual((upstream["released_at"], upstream["prerelease"]), (None, None))
        self.assertEqual({key: value for key, value in upstream.items()
                          if key not in ("latest", "released_at", "prerelease", "latest_source", "matching_tag_count")},
                         {key: value for key, value in expected.items()
                          if key not in ("latest", "released_at", "prerelease", "latest_flag")})

    def test_a_pin_at_the_highest_tag_is_compared_and_not_behind(self):
        row = self._row(_inspect_entry(pin="0.3.276"), {INSPECT_REPOSITORY: _inspect_record()})
        self.assertEqual((row["pin_comparison"], row["pin_behind_upstream"]), ("compared", False))

    def test_without_a_list_for_the_prefix_the_row_is_unfetched_and_not_compared(self):
        without_list = {key: value for key, value in _inspect_record().items() if key != "matching_tags"}
        cases = {
            "no matching_tags": {INSPECT_REPOSITORY: without_list},
            "a list for another prefix only": {INSPECT_REPOSITORY: _inspect_record(matching_tags={"v": ["v0.3.276"]})},
            "a failed list call": {INSPECT_REPOSITORY: dict(without_list, matching_tags_errors={"": "HTTP 503"})},
            "no record": {},
        }
        for label, repositories in cases.items():
            with self.subTest(case=label):
                row = self._row(_inspect_entry(), repositories)
                self.assertEqual((row["upstream"]["latest"], row["upstream"]["latest_source"]),
                                 (None, "tag_pattern_unfetched"))
                # Every other upstream field is compute_upstream's, latest_flag included.
                self.assertEqual(row["upstream"], {**build_manifest.compute_upstream(INSPECT_REPOSITORY, repositories),
                                                   "latest_source": "tag_pattern_unfetched"})
                self.assertEqual((row["pin_behind_upstream"], row["pin_comparison"], row["pin_comparison_reason"]),
                                 (None, "not_compared", "unversioned"))

    def test_with_no_matching_tag_the_row_is_unmatched_and_keeps_compute_upstream(self):
        for names in ([], ["release/2025-11-28", "0.3.277rc1", "0.4.0-dev"]):
            with self.subTest(names=names):
                row = self._row(_inspect_entry(), {INSPECT_REPOSITORY: _inspect_record(matching_tags={"": names})})
                self.assertEqual((row["upstream"]["latest"], row["upstream"]["latest_source"]),
                                 (None, "tag_pattern_unmatched"))
                self.assertEqual((row["pin_behind_upstream"], row["pin_comparison"], row["pin_comparison_reason"]),
                                 (None, "not_compared", "unversioned"))
        # A release tag stays the latest when the pattern matches nothing, with its release fields.
        repositories = {DEEPAGENTS_REPOSITORY: _deepagents_record(matching_tags={"deepagents==": []})}
        row = self._row(_deepagents_entry(), repositories)
        self.assertEqual(row["upstream"], {**build_manifest.compute_upstream(DEEPAGENTS_REPOSITORY, repositories),
                                           "latest_source": "tag_pattern_unmatched"})
        self.assertEqual((row["upstream"]["latest"], row["upstream"]["released_at"]),
                         ("deepagents-cli==1.0.0", "2026-10-01"))

    def test_a_missing_or_uncompilable_pattern_makes_the_row_unmatched_instead_of_raising(self):
        for tags in ({"prefix": ""}, {"prefix": "", "pattern": None}, {"prefix": "", "pattern": r"^(\d+\.\d+$"}):
            with self.subTest(tags=tags):
                row = self._row(_inspect_entry(tags=tags), {INSPECT_REPOSITORY: _inspect_record()})
                self.assertEqual((row["upstream"]["latest"], row["upstream"]["latest_source"]),
                                 (None, "tag_pattern_unmatched"))
                self.assertEqual((row["pin_comparison"], row["pin_comparison_reason"]), ("not_compared", "unversioned"))

    def test_a_matching_tag_replaces_a_release_of_another_package(self):
        repositories = {DEEPAGENTS_REPOSITORY: _deepagents_record()}
        row = self._row(_deepagents_entry(), repositories)
        upstream = row["upstream"]
        self.assertEqual((upstream["latest"], upstream["latest_source"], upstream["matching_tag_count"]),
                         ("deepagents==0.7.21", "matching_tag", 2))
        # The repository's latest release is deepagents-cli==1.0.0, another package's, so its
        # date and prerelease flag are not paired with the matching tag.
        self.assertEqual((upstream["released_at"], upstream["prerelease"]), (None, None))
        expected = build_manifest.compute_upstream(DEEPAGENTS_REPOSITORY, repositories)
        self.assertEqual((expected["released_at"], expected["prerelease"]), ("2026-10-01", False))
        self.assertEqual({key: value for key, value in upstream.items()
                          if key not in ("latest", "released_at", "prerelease", "latest_source", "matching_tag_count")},
                         {key: value for key, value in expected.items()
                          if key not in ("latest", "released_at", "prerelease")})
        # Dormancy still reads the repository's activity, that release included.
        self.assertEqual((row["dormancy"]["last_release_at"], row["dormancy"]["dormant"]), ("2026-10-01", False))
        # A watch-only row stays not compared.
        self.assertEqual((row["pin_behind_upstream"], row["pin_comparison"], row["pin_comparison_reason"]),
                         (None, "not_compared", "watch_only"))

    def test_rows_without_a_declaration_keep_compute_upstream_exactly(self):
        repositories = _repositories()
        # A record's tag lists are read only through a declaration.
        repositories["https://github.com/example/behind"]["matching_tags"] = {"": ["rust-v9.9.9"]}
        for row in build_manifest.build_runtime_freshness(_runtime_pins(), repositories, CHECKED_AT)["entries"]:
            with self.subTest(row=row["id"]):
                expected = (build_manifest.compute_upstream(row["repository"], repositories)
                            if row["repository"] else {})
                self.assertEqual(row["upstream"], expected)
                self.assertNotIn("latest_source", row["upstream"])

    def test_a_cut_tag_list_keeps_the_selected_tag_and_is_not_compared(self):
        """github_freshness.py marks a record whose list it cut at MATCHING_TAGS_CAP: a higher
        version can be among the names it did not keep, so no definitive comparison."""
        repositories = {INSPECT_REPOSITORY: _inspect_record(matching_tags_truncated=True)}
        # The pin at the highest kept tag is not called current either.
        for pin in ("0.3.273", "0.3.276"):
            with self.subTest(pin=pin):
                row = self._row(_inspect_entry(pin=pin), repositories)
                upstream = row["upstream"]
                self.assertEqual((upstream["latest"], upstream["latest_source"], upstream["matching_tag_count"]),
                                 ("0.3.276", "tag_pattern_truncated", 4))
                self.assertEqual((row["pin_behind_upstream"], row["pin_comparison"], row["pin_comparison_reason"]),
                                 (None, "not_compared", "tag_list_truncated"))
                # Otherwise the selected tag's upstream is the matching tag's.
                untruncated = self._row(_inspect_entry(pin=pin), {INSPECT_REPOSITORY: _inspect_record()})["upstream"]
                self.assertEqual({**upstream, "latest_source": "matching_tag"}, untruncated)

    def test_a_cut_tag_list_with_no_match_keeps_compute_upstream_and_is_not_compared(self):
        record = _inspect_record(matching_tags={"": ["release/2025-11-28", "0.3.277rc1"]}, matching_tags_truncated=True)
        repositories = {INSPECT_REPOSITORY: record}
        row = self._row(_inspect_entry(), repositories)
        # Not tag_pattern_unmatched: "no listed tag matched" says nothing about the names cut.
        self.assertEqual(row["upstream"], {**build_manifest.compute_upstream(INSPECT_REPOSITORY, repositories),
                                           "latest_source": "tag_pattern_truncated"})
        self.assertEqual((row["pin_behind_upstream"], row["pin_comparison"], row["pin_comparison_reason"]),
                         (None, "not_compared", "tag_list_truncated"))

    def test_a_cut_tag_list_keeps_the_reason_of_a_watch_or_unresolved_row(self):
        cases = {
            "watch_only": (_deepagents_entry(), DEEPAGENTS_REPOSITORY,
                           _deepagents_record(matching_tags_truncated=True), "deepagents==0.7.21"),
            "source_unresolved": (_inspect_entry(pin=None, error=MOVED_ERROR), INSPECT_REPOSITORY,
                                  _inspect_record(matching_tags_truncated=True), "0.3.276"),
        }
        for reason, (entry, repository, record, latest) in cases.items():
            with self.subTest(reason=reason):
                row = self._row(entry, {repository: record})
                self.assertEqual((row["upstream"]["latest"], row["upstream"]["latest_source"]),
                                 (latest, "tag_pattern_truncated"))
                self.assertEqual((row["pin_behind_upstream"], row["pin_comparison"], row["pin_comparison_reason"]),
                                 (None, "not_compared", reason))

    def test_the_record_level_cut_marks_every_prefix_the_repository_declares(self):
        # matching_tags_truncated is per record, not per prefix: which list was cut is unknown.
        record = _inspect_record(matching_tags={"": list(INSPECT_LIKE_TAGS), "v": ["v0.3.276"]},
                                 matching_tags_truncated=True)
        entries = [_inspect_entry(),
                   _inspect_entry(id="new-wsl:inspect-v", tags={"prefix": "v", "pattern": r"^v(\d+\.\d+\.\d+)$"})]
        rows = build_manifest.build_runtime_freshness({"entries": entries}, {INSPECT_REPOSITORY: record},
                                                      CHECKED_AT)["entries"]
        self.assertEqual([(row["id"], row["upstream"]["latest"], row["upstream"]["latest_source"],
                           row["pin_comparison_reason"]) for row in rows],
                         [("new-wsl:inspect-ai", "0.3.276", "tag_pattern_truncated", "tag_list_truncated"),
                          ("new-wsl:inspect-v", "v0.3.276", "tag_pattern_truncated", "tag_list_truncated")])


class BuildManifestRuntimeFreshnessCliTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.work = Path(self._tmp.name)
        card = {"id": "engine", "repository": "https://github.com/example/current", "decision": "default",
                "version_or_commit": "1.0.0"}
        files = {
            "foundation-layers.json": {"checked_at": CHECKED_AT, "layers": [], "top_gaps": []},
            "trading-by-layer.json": {"taxonomy": {"backtesting-engine": ["backtesting"]},
                                      "layers": {"backtesting-engine": [card]}},
            "github-freshness.json": {"repositories": _repositories()},
            "runtime-pins.json": _runtime_pins(),
            "lanes.json": {"lanes": [], "critic": None, "lost": []},
            "reconciliations.json": {"reconciliations": []},
        }
        for name, doc in files.items():
            (self.work / name).write_text(json.dumps(doc), encoding="utf-8")

    def _run(self, *extra):
        argv = ["--work-dir", str(self.work), "--lanes", str(self.work / "lanes.json"),
                "--reconciliations", str(self.work / "reconciliations.json"),
                "--out", str(self.work / "manifest-20261002.json"),
                "--trading-freshness-out", str(self.work / "trading-freshness.json"),
                "--checked-at", CHECKED_AT, "--id", "catalog-freshness-20261002", *extra]
        with redirect_stdout(StringIO()) as stdout:
            self.assertEqual(build_manifest.main(argv), 0)
        return stdout.getvalue()

    def _written(self):
        return tuple((self.work / name).read_bytes() for name in ("manifest-20261002.json", "trading-freshness.json"))

    def _sidecar(self):
        return json.loads((self.work / "runtime-freshness.json").read_text(encoding="utf-8"))

    def test_the_flag_adds_the_sidecar_and_leaves_the_manifest_and_trading_bytes_alone(self):
        self._run()
        without = self._written()
        self.assertFalse((self.work / "runtime-freshness.json").exists())
        output = self._run("--runtime-freshness-out", str(self.work / "runtime-freshness.json"))
        self.assertEqual(self._written(), without)
        doc = self._sidecar()
        self.assertEqual([row["id"] for row in doc["entries"]],
                         ["new-wsl:behind", "new-wsl:current", "new-wsl:moved", "watch:idle"])
        self.assertEqual(json.loads(output.splitlines()[-1]), {"runtime_freshness": doc["counts"]})
        manifest_text = without[0].decode("utf-8")
        for runtime_id in ("new-wsl:behind", "watch:idle", "runtime_freshness"):
            self.assertNotIn(runtime_id, manifest_text)

    def test_without_runtime_pins_the_sidecar_is_still_written_with_no_rows(self):
        (self.work / "runtime-pins.json").unlink()
        self._run("--runtime-freshness-out", str(self.work / "runtime-freshness.json"))
        self.assertEqual((self._sidecar()["entries"], self._sidecar()["counts"]["entries"]), ([], 0))

    def test_the_runtime_pins_flag_overrides_the_work_dir_default(self):
        other = self.work / "elsewhere.json"
        other.write_text(json.dumps({"entries": _runtime_pins()["entries"][3:]}), encoding="utf-8")
        self._run("--runtime-pins", str(other), "--runtime-freshness-out", str(self.work / "runtime-freshness.json"))
        self.assertEqual([row["id"] for row in self._sidecar()["entries"]], ["watch:idle"])

    def test_a_host_path_in_an_entry_is_redacted_before_the_write(self):
        pins = _runtime_pins()
        # scripts/validate.py's placeholder home; build_manifest.sanitize redacts it like any other.
        pins["entries"][2]["error"] = "could not read /home/example/plan/install-plan.json"
        (self.work / "runtime-pins.json").write_text(json.dumps(pins), encoding="utf-8")
        self._run("--runtime-freshness-out", str(self.work / "runtime-freshness.json"))
        text = (self.work / "runtime-freshness.json").read_text(encoding="utf-8")
        self.assertNotIn("/home/", text)
        self.assertIn("<host-path>/install-plan.json", text)


class RuntimeReportTests(unittest.TestCase):
    """build_drift_report() with a runtime-freshness.json in the work dir."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        base = Path(self._tmp.name)
        self.work = base / "work"
        self.work.mkdir()
        self.published_dir = base / "catalogs" / "sota-convergence"
        self.published_dir.mkdir(parents=True)
        original = Path.cwd()
        os.chdir(base)
        self.addCleanup(os.chdir, original)
        self.repositories = _repositories()
        self._write_freshness(self.repositories)
        self._write_manifest(self.published_dir / "manifest-20260929.json", "8.30.0")
        self._write_manifest(self.work / "manifest-20261002.json", "8.30.0")

    def _write_freshness(self, repositories, partial_errors=0):
        (self.work / "github-freshness.json").write_text(json.dumps(
            {"errors": 0, "partial_errors": partial_errors, "repositories": repositories}), encoding="utf-8")

    def _write_manifest(self, path, pin):
        row = {"id": "gitleaks", "pin": pin, "repository": "https://github.com/gitleaks/gitleaks",
               "upstream": {"latest": "v8.30.1", "pushed_at": "2026-09-20"}, "pin_behind_upstream": True}
        path.write_text(json.dumps({"foundation": [{"components": [row]}], "trading": [], "counts": {}}),
                        encoding="utf-8")

    def _write_runtime(self, runtime_pins=None):
        doc = build_manifest.build_runtime_freshness(runtime_pins or _runtime_pins(), self.repositories, CHECKED_AT)
        (self.work / fp.RUNTIME_FRESHNESS_FILE).write_text(json.dumps(doc), encoding="utf-8")

    def _text(self):
        return (self.work / "drift.md").read_text(encoding="utf-8")

    def _cells(self, row_id):
        line = next(line for line in self._text().splitlines() if line.startswith(f"| {fp.md_cell(row_id)} |"))
        return [cell.strip() for cell in line.strip("|").split(" | ")]

    def test_table_lists_every_runtime_row(self):
        self._write_runtime()
        result = fp.build_drift_report(self.work)
        text = self._text()
        self.assertIn(fp.RUNTIME_TABLE_HEADING, text)
        self.assertIn(fp.RUNTIME_TABLE_HEADER + "\n" + fp.RUNTIME_TABLE_SEPARATOR, text)
        self.assertIn("never change `drift-status.txt`", text)
        self.assertIn("in the last 180 days as of `2026-10-02`", text)
        self.assertEqual(self._cells("new-wsl:behind"), [fp.md_cell(value) for value in (
            "new-wsl:behind", "native-client", "rust-v1.0.0", "rust-v1.1.0", "yes", "2026-09-20", "2026-09-30",
            2, "no", "no")])
        self.assertEqual(self._cells("watch:idle"), [fp.md_cell(value) for value in (
            "watch:idle", "coding-agent", "—", None, "not compared (watch_only)", None, "2025-12-01", 305, "yes",
            "yes")])
        self.assertEqual(result["runtime"], ["new-wsl:behind", "new-wsl:current", "new-wsl:moved", "watch:idle"])
        self.assertEqual((result["runtime_dormant"], result["runtime_archived"]), (["watch:idle"], ["watch:idle"]))

    def test_unresolved_and_behind_ids_are_listed(self):
        self._write_runtime()
        result = fp.build_drift_report(self.work)
        text = self._text()
        self.assertEqual(result["runtime_behind"], ["new-wsl:behind"])
        self.assertEqual(result["runtime_unresolved"], ["new-wsl:moved"])
        self.assertIn("1 pinned runtime row(s) behind upstream latest:\n\n" + fp.md_cell("new-wsl:behind"), text)
        self.assertIn(fp.md_cell(f"new-wsl:moved ({MOVED_ERROR})"), text)
        # The unresolved row keeps its place in the table, with no pin and nothing compared.
        self.assertEqual(self._cells("new-wsl:moved")[:3], [fp.md_cell("new-wsl:moved"), fp.md_cell("gateway"),
                                                            fp.md_cell("—")])

    def test_runtime_rows_never_change_drift_status_or_the_propose_ids(self):
        for rebuilt_pin, drifted in (("8.30.0", []), ("8.30.1", ["gitleaks"])):
            with self.subTest(rebuilt_pin=rebuilt_pin):
                self._write_manifest(self.work / "manifest-20261002.json", rebuilt_pin)
                (self.work / fp.RUNTIME_FRESHNESS_FILE).unlink(missing_ok=True)
                without = fp.build_drift_report(self.work)
                observed = [((self.work / "drift-status.txt").read_text(encoding="utf-8"),
                             fp.drifted_component_ids(self._text()), without["drifted"])]
                self._write_runtime()
                with_runtime = fp.build_drift_report(self.work)
                self.assertIn(fp.RUNTIME_TABLE_HEADING, self._text())
                observed.append(((self.work / "drift-status.txt").read_text(encoding="utf-8"),
                                 fp.drifted_component_ids(self._text()), with_runtime["drifted"]))
                self.assertEqual(observed[0], observed[1])
                self.assertEqual(observed[1][1], drifted)

    def test_unreliable_fetch_blanks_the_row_instead_of_calling_it_behind(self):
        self.repositories["https://github.com/example/behind"]["partial_errors"] = {"releases": "HTTP 503"}
        self._write_freshness(self.repositories, partial_errors=1)
        self._write_runtime()
        result = fp.build_drift_report(self.work)
        self.assertEqual(result["runtime_behind"], [])
        # new-wsl:moved has no repository to fetch; only the unresolved line reports it.
        self.assertEqual(result["runtime_unfetched"], ["new-wsl:behind"])
        self.assertEqual(result["runtime_unresolved"], ["new-wsl:moved"])
        self.assertEqual(self._cells("new-wsl:behind").count(fp.md_cell("unknown")), 3)
        self.assertIn("1 runtime row(s) with no reliable upstream data this run:\n\n" + fp.md_cell("new-wsl:behind"),
                      self._text())

    def test_an_unresolved_row_is_unfetched_only_when_it_kept_a_repository(self):
        pins = _runtime_pins()
        # A requirement source keeps its declared literal repository when its line moves;
        # github-freshness.json has no record for it, so it has no reliable upstream data.
        pins["entries"].append({
            "id": "sdk-lock:moved", "group": "model-sdk", "kind": "pin_source",
            "repository": "https://github.com/example/sdk", "pin": None,
            "pin_source": {"path": "sdk/constraints.txt", "requirement": "openai"}, "named_in": None,
            "error": "sdk/constraints.txt requirement openai: requirement not found",
        })
        self._write_runtime(pins)
        result = fp.build_drift_report(self.work)
        self.assertEqual(result["runtime_unresolved"], ["new-wsl:moved", "sdk-lock:moved"])
        self.assertEqual(result["runtime_unfetched"], ["sdk-lock:moved"])
        self.assertIn("1 runtime row(s) with no reliable upstream data this run:\n\n" + fp.md_cell("sdk-lock:moved"),
                      self._text())

    def test_an_empty_sidecar_still_renders_the_section(self):
        self._write_runtime({"entries": []})
        result = fp.build_drift_report(self.work)
        self.assertIn("No GPT runtime row was found.", self._text())
        self.assertEqual(result["runtime"], [])

    def test_without_the_sidecar_the_runtime_keys_are_empty(self):
        result = fp.build_drift_report(self.work)
        self.assertNotIn(fp.RUNTIME_TABLE_HEADING, self._text())
        self.assertEqual({key: result[key] for key in fp.RUNTIME_SUMMARY_KEYS},
                         {key: [] for key in fp.RUNTIME_SUMMARY_KEYS})
        self.assertEqual(len(fp.RUNTIME_SUMMARY_KEYS), 6)

    def test_malformed_sidecar_fails_closed(self):
        (self.work / fp.RUNTIME_FRESHNESS_FILE).write_text("{", encoding="utf-8")
        with self.assertRaises(fp.FreshnessProposeError):
            fp.build_drift_report(self.work)

    def _tagged(self, inspect_record=None, deepagents_record=None):
        """Add the two tag-declaring upstreams' records to github-freshness.json and
        return runtime pins that carry their entries."""
        self.repositories[INSPECT_REPOSITORY] = inspect_record or _inspect_record()
        self.repositories[DEEPAGENTS_REPOSITORY] = deepagents_record or _deepagents_record()
        self._write_freshness(self.repositories, partial_errors=sum(
            1 for record in self.repositories.values() if record.get("partial_errors")))
        pins = _runtime_pins()
        pins["entries"] += [_inspect_entry(), _deepagents_entry()]
        return pins

    def test_a_latest_from_matching_tags_is_marked_in_its_cell(self):
        self._write_runtime(self._tagged())
        result = fp.build_drift_report(self.work)
        self.assertEqual(self._cells("new-wsl:inspect-ai")[2:5],
                         [fp.md_cell("0.3.273"), fp.md_cell("0.3.276 (tag)"), fp.md_cell("yes")])
        self.assertEqual(self._cells("watch:deepagents")[3:5],
                         [fp.md_cell("deepagents==0.7.21 (tag)"), fp.md_cell("not compared (watch_only)")])
        # A latest from a release is not marked, and with no miss there is no miss line.
        self.assertEqual(self._cells("new-wsl:behind")[3], fp.md_cell("rust-v1.1.0"))
        self.assertNotIn(fp.RUNTIME_TAG_MISS_SENTENCE, self._text())
        self.assertEqual(result["runtime_behind"], ["new-wsl:behind", "new-wsl:inspect-ai"])

    def test_rows_whose_pattern_selected_no_tag_are_listed_in_one_line_after_the_table(self):
        deepagents = _deepagents_record()
        del deepagents["matching_tags"]
        self._write_runtime(self._tagged(_inspect_record(matching_tags={"": ["release/2025-11-28", "0.3.277rc1"]}),
                                         deepagents))
        result = fp.build_drift_report(self.work)
        text = self._text()
        self.assertIn(f"2 {fp.RUNTIME_TAG_MISS_SENTENCE}:\n\n" + fp.md_cell("new-wsl:inspect-ai (tag_pattern_unmatched)")
                      + ", " + fp.md_cell("watch:deepagents (tag_pattern_unfetched)") + "\n", text)
        self.assertGreater(text.index(fp.RUNTIME_TAG_MISS_SENTENCE), text.index(fp.RUNTIME_TABLE_HEADER))
        # The line states what each reason means, and that both keep the release or tag listing as latest.
        for meaning in ("`tag_pattern_unmatched`: no listed tag matched",
                        "`tag_pattern_unfetched`: the tag list could not be read this run",
                        "in both cases the upstream latest stays the release or tag listing"):
            self.assertIn(meaning, fp.RUNTIME_TAG_MISS_SENTENCE)
        self.assertEqual(self._cells("new-wsl:inspect-ai")[3:5],
                         [fp.md_cell(None), fp.md_cell("not compared (unversioned)")])
        self.assertEqual(self._cells("watch:deepagents")[3], fp.md_cell("deepagents-cli==1.0.0"))
        # The line changes no summary key.
        self.assertEqual(result["runtime_behind"], ["new-wsl:behind"])
        self.assertEqual([key for key in result if key.startswith("runtime")], list(fp.RUNTIME_SUMMARY_KEYS))

    def test_a_failed_tag_list_blanks_nothing_and_is_named_only_in_the_miss_line(self):
        # The record github_freshness.py writes when the matching-refs call fails.
        inspect = {key: value for key, value in _inspect_record().items() if key != "matching_tags"}
        inspect["matching_tags_errors"] = {"": "HTTP 503: Service Unavailable"}
        self._write_runtime(self._tagged(inspect))
        result = fp.build_drift_report(self.work)
        # The row keeps compute_upstream's data (no release; the first tag stays withheld).
        self.assertEqual(result["runtime_unfetched"], [])
        self.assertEqual(self._cells("new-wsl:inspect-ai")[3:], [fp.md_cell(value) for value in (
            None, "not compared (unversioned)", None, "2026-10-02", 0, "no", "no")])
        self.assertIn(f"1 {fp.RUNTIME_TAG_MISS_SENTENCE}:\n\n" + fp.md_cell("new-wsl:inspect-ai (tag_pattern_unfetched)"),
                      self._text())
        self.assertEqual((self.work / "upstream-partial-errors.txt").read_text(encoding="utf-8"), "0\n")

    def test_a_cut_tag_list_is_named_in_the_miss_line_and_its_row_is_not_compared(self):
        self._write_runtime(self._tagged(_inspect_record(matching_tags_truncated=True)))
        result = fp.build_drift_report(self.work)
        # The kept tag is shown without the "(tag)" marker, which promises the highest matching
        # version; the row is not compared and is not behind.
        self.assertEqual(self._cells("new-wsl:inspect-ai")[2:5],
                         [fp.md_cell("0.3.273"), fp.md_cell("0.3.276"), fp.md_cell("not compared (tag_list_truncated)")])
        self.assertIn(f"1 {fp.RUNTIME_TAG_MISS_SENTENCE}:\n\n" + fp.md_cell("new-wsl:inspect-ai (tag_pattern_truncated)")
                      + "\n", self._text())
        for meaning in ("`tag_pattern_truncated`: the tag list was cut", "the pin is not compared (`tag_list_truncated`)"):
            self.assertIn(meaning, fp.RUNTIME_TAG_MISS_SENTENCE)
        self.assertEqual(result["runtime_behind"], ["new-wsl:behind"])
        self.assertEqual(result["runtime_unfetched"], [])
        self.assertEqual((self.work / "upstream-partial-errors.txt").read_text(encoding="utf-8"), "0\n")

    def test_tag_rows_never_change_drift_status_or_the_propose_ids(self):
        pins = self._tagged(_inspect_record(), _deepagents_record(matching_tags={"deepagents==": []}))
        for rebuilt_pin, drifted in (("8.30.0", []), ("8.30.1", ["gitleaks"])):
            with self.subTest(rebuilt_pin=rebuilt_pin):
                self._write_manifest(self.work / "manifest-20261002.json", rebuilt_pin)
                (self.work / fp.RUNTIME_FRESHNESS_FILE).unlink(missing_ok=True)
                without = fp.build_drift_report(self.work)
                observed = [((self.work / "drift-status.txt").read_text(encoding="utf-8"),
                             fp.drifted_component_ids(self._text()), without["drifted"])]
                self._write_runtime(pins)
                with_tags = fp.build_drift_report(self.work)
                self.assertIn(fp.md_cell("0.3.276 (tag)"), self._text())
                self.assertIn(fp.RUNTIME_TAG_MISS_SENTENCE, self._text())
                observed.append(((self.work / "drift-status.txt").read_text(encoding="utf-8"),
                                 fp.drifted_component_ids(self._text()), with_tags["drifted"]))
                self.assertEqual(observed[0], observed[1])
                self.assertEqual(observed[1][1], drifted)


RUNTIME_ONLY_REPOSITORY = "https://github.com/example/runtime-only"
SHARED_REPOSITORY = "https://github.com/example/shared"
# The other working file names the shared repository in other letter case: slugs are compared.
SHARED_ALIAS = "https://github.com/Example/Shared"
# Each working file other than runtime-pins.json, as a document that names one repository.
NON_RUNTIME_FILES = {
    "foundation-layers.json": lambda url: {"layers": [{"components": [{"repository": url}]}]},
    "trading-catalog.json": lambda url: {"entries": [{"repository": url}]},
    "trading-pins.json": lambda url: {"entries": [{"repository": url}]},
    "star-candidates.json": lambda url: {"star_candidates": [{"repository": url}], "beyond_stars": []},
}
GATE_FILES = ("upstream-errors.txt", "upstream-partial-errors.txt")
COUNTER_KEYS = ("errors", "partial_errors", "runtime_only_errors", "runtime_only_partial_errors")


def _pinned_runtime_entry(entry_id, repository):
    return {"id": entry_id, "group": "runtime-worker", "kind": "pin_source", "repository": repository,
            "pin": "v1.0.0", "pin_source": {"path": "plan/install-plan.json",
                                            "row": {"array": "/owners", "key": "slot", "value": entry_id}},
            "named_in": None, "error": None, "tags": None}


class RuntimeOnlyFetchFailureTests(unittest.TestCase):
    """A fetch failure on a repository that only runtime-pins.json names, run the way the
    daily job runs: github_freshness.main (gh_api mocked), build_runtime_freshness on its
    records, then build_drift_report against a published manifest in the checkout (the
    current working directory). The failure counts in runtime_only_errors or
    runtime_only_partial_errors and leaves upstream-errors.txt and
    upstream-partial-errors.txt, which hold the propose job, at 0 and the saturation
    ledger's freshness input "read"; the same failure on a repository that another
    working file names still counts in errors or partial_errors."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        base = Path(self._tmp.name)
        self.work = base / "work"
        self.work.mkdir()
        published = base / "catalogs" / "sota-convergence"
        published.mkdir(parents=True)
        original = Path.cwd()
        os.chdir(base)
        self.addCleanup(os.chdir, original)
        row = {"id": "gitleaks", "pin": "8.30.0", "repository": "https://github.com/gitleaks/gitleaks",
               "upstream": {"latest": "v8.30.1", "pushed_at": "2026-09-20"}, "pin_behind_upstream": True}
        for path in (published / "manifest-20260929.json", self.work / "manifest-20261002.json"):
            path.write_text(json.dumps({"foundation": [{"components": [row]}], "trading": [], "counts": {}}),
                            encoding="utf-8")
        self.runtime_pins = {"entries": [_pinned_runtime_entry("new-wsl:runtime-only", RUNTIME_ONLY_REPOSITORY),
                                         _pinned_runtime_entry("new-wsl:shared", SHARED_REPOSITORY)]}
        (self.work / "runtime-pins.json").write_text(json.dumps(self.runtime_pins), encoding="utf-8")
        self._name_shared_in("foundation-layers.json")

    def _name_shared_in(self, filename):
        for name in NON_RUNTIME_FILES:
            (self.work / name).unlink(missing_ok=True)
        (self.work / filename).write_text(json.dumps(NON_RUNTIME_FILES[filename](SHARED_ALIAS)), encoding="utf-8")

    def _run(self, **failing):
        (self.work / "github-freshness.json").unlink(missing_ok=True)
        with mock.patch.object(github_freshness, "gh_api", _fake_gh_api([], **failing)), redirect_stdout(StringIO()):
            self.assertEqual(github_freshness.main(["--work-dir", str(self.work), "--workers", "1"]), 0)
        document = json.loads((self.work / "github-freshness.json").read_text(encoding="utf-8"))
        runtime = build_manifest.build_runtime_freshness(self.runtime_pins, document["repositories"], CHECKED_AT)
        (self.work / fp.RUNTIME_FRESHNESS_FILE).write_text(json.dumps(runtime), encoding="utf-8")
        result = fp.build_drift_report(self.work)
        gate = tuple((self.work / name).read_text(encoding="utf-8") for name in GATE_FILES)
        return document, result, gate, (self.work / "drift.md").read_text(encoding="utf-8")

    @staticmethod
    def _record(document, slug):
        return next(record for record in document["repositories"].values() if record["slug"] == slug)

    def _assert_runtime_only_failure(self, document, result, gate, text, counters):
        self.assertEqual(tuple(document[key] for key in COUNTER_KEYS), counters)
        self.assertEqual(document["runtime_only_repositories"], ["example/runtime-only"])
        self.assertEqual(gate, ("0\n", "0\n"))
        # The saturation ledger reads the same two counts as the freshness input's completeness.
        self.assertEqual(saturation_ledger.freshness_input({}, document), ("read", []))
        self.assertIn(f"1 {fp.RUNTIME_ONLY_FAILURE_SENTENCE}:\n\n" + fp.md_cell("new-wsl:runtime-only") + "\n", text)
        # The per-record rule is unchanged: the row is still blanked and listed as unfetched.
        self.assertEqual(result["runtime_unfetched"], ["new-wsl:runtime-only"])

    def test_a_runtime_only_primary_failure_is_counted_apart_and_holds_nothing(self):
        document, result, gate, text = self._run(primary_failing={"example/runtime-only"})
        self.assertEqual(self._record(document, "example/runtime-only")["error"], "HTTP 503: Service Unavailable")
        self._assert_runtime_only_failure(document, result, gate, text, (0, 0, 1, 0))

    def test_a_runtime_only_release_5xx_is_counted_apart_and_holds_nothing(self):
        document, result, gate, text = self._run(releases_failing={"example/runtime-only"})
        self.assertEqual(self._record(document, "example/runtime-only")["partial_errors"],
                         {"releases": "HTTP 503: Service Unavailable"})
        self._assert_runtime_only_failure(document, result, gate, text, (0, 0, 0, 1))

    def test_the_same_failures_on_a_repository_another_working_file_names_still_hold_the_gate(self):
        for filename in NON_RUNTIME_FILES:
            for failing, counters, gate in (
                ({"primary_failing": {"example/shared"}}, (1, 0, 0, 0), ("1\n", "0\n")),
                ({"releases_failing": {"example/shared"}}, (0, 1, 0, 0), ("0\n", "1\n")),
            ):
                with self.subTest(file=filename, failing=sorted(failing)):
                    self._name_shared_in(filename)
                    document, result, observed_gate, text = self._run(**failing)
                    self.assertEqual(tuple(document[key] for key in COUNTER_KEYS), counters)
                    self.assertEqual(document["runtime_only_repositories"], ["example/runtime-only"])
                    self.assertEqual(observed_gate, gate)
                    self.assertEqual(saturation_ledger.freshness_input({}, document)[0], "partial")
                    self.assertNotIn(fp.RUNTIME_ONLY_FAILURE_SENTENCE, text)
                    self.assertEqual(result["runtime_unfetched"], ["new-wsl:shared"])

    def test_a_retained_record_no_working_file_names_still_counts_in_the_gate(self):
        results = {
            "https://github.com/example/runtime-only": {"slug": "example/runtime-only", "error": "timeout"},
            SHARED_ALIAS: {"slug": "example/shared", "partial_errors": {"releases": "HTTP 503"}},
            "https://github.com/example/stale": {"slug": "Example/Stale", "error": "timeout"},
        }
        document = github_freshness.build_document(results, runtime_only_slugs={"Example/Runtime-Only"})
        self.assertEqual(tuple(document[key] for key in COUNTER_KEYS), (1, 1, 1, 0))
        self.assertEqual(document["runtime_only_repositories"], ["example/runtime-only"])
        # Without the set, as before runtime-pins.json existed, every record counts in the gate.
        document = github_freshness.build_document(results)
        self.assertEqual(tuple(document[key] for key in COUNTER_KEYS), (2, 1, 0, 0))
        self.assertEqual(document["runtime_only_repositories"], [])

    def test_runtime_only_slugs_compare_normalized_slugs(self):
        work = self.work / "slugs"
        work.mkdir()
        self.assertEqual(github_freshness.collect_runtime_only_slugs(work), set())
        (work / "runtime-pins.json").write_text(json.dumps({"entries": [
            {"id": "only", "repository": "https://github.com/example/only"},
            {"id": "aliased", "repository": "https://github.com/example/aliased"},
            {"id": "cased", "repository": "https://github.com/example/cased"},
            {"id": "moved", "repository": None},
            {"id": "off-github", "repository": "https://gitlab.com/example/off"},
        ]}), encoding="utf-8")
        (work / "trading-catalog.json").write_text(json.dumps({"entries": [
            {"repository": "https://github.com/example/aliased/releases/tag/v1"},
            {"repository": "https://github.com/EXAMPLE/Cased"},
        ]}), encoding="utf-8")
        self.assertEqual(github_freshness.collect_runtime_only_slugs(work), {"example/only"})

    def test_a_document_without_the_runtime_only_list_names_no_row(self):
        # A github-freshness.json written before the list existed: the line is simply absent.
        self.assertEqual(fp.runtime_only_repository_slugs({"errors": 0, "partial_errors": 0}), set())
        self.assertEqual(fp.runtime_only_repository_slugs({"runtime_only_repositories": "example/x"}), set())
        self.assertEqual(fp.runtime_only_repository_slugs({"runtime_only_repositories": ["Example/X", 7]}),
                         {"example/x"})


LEAKY_REPOSITORY = "https://github.com/example/leaky"
# A third-party release tag that build_manifest.assert_no_leak refuses ("APCA" is a LEAK_MARKERS entry).
LEAKY_TAG = "v1.0.0-APCA"


class RuntimeLeakGateTests(unittest.TestCase):
    """A runtime-only upstream whose own data trips build_manifest's leak gate.

    The daily path runs in one work dir, as in the workflow: build_manifest.main writes
    the manifest and both sidecars, then build_drift_report reads them against a
    published manifest in the checkout (the current working directory)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        base = Path(self._tmp.name)
        self.work = base / "work"
        self.work.mkdir()
        self.published_dir = base / "catalogs" / "sota-convergence"
        self.published_dir.mkdir(parents=True)
        original = Path.cwd()
        os.chdir(base)
        self.addCleanup(os.chdir, original)
        self.runtime_pins = _runtime_pins()
        self.runtime_pins["entries"].append({
            "id": "new-wsl:leaky", "group": "runtime-worker", "kind": "pin_source", "repository": LEAKY_REPOSITORY,
            "pin": "v0.9.0", "pin_source": self.runtime_pins["entries"][0]["pin_source"], "named_in": None,
            "error": None,
        })
        self.repositories = _repositories()
        self.repositories[LEAKY_REPOSITORY] = {
            "slug": "example/leaky", "pushed_at": "2026-09-30T00:00:00Z", "archived": False,
            "latest_release": {"tag": LEAKY_TAG, "published_at": "2026-09-30T00:00:00Z"},
            "head": {"date": "2026-09-30T00:00:00Z"},
        }
        card = {"id": "engine", "repository": "https://github.com/example/current", "decision": "default",
                "version_or_commit": "1.0.0"}
        files = {
            "foundation-layers.json": {"checked_at": CHECKED_AT, "layers": [], "top_gaps": []},
            "trading-by-layer.json": {"taxonomy": {"backtesting-engine": ["backtesting"]},
                                      "layers": {"backtesting-engine": [card]}},
            "runtime-pins.json": self.runtime_pins,
            "lanes.json": {"lanes": [], "critic": None, "lost": []},
            "reconciliations.json": {"reconciliations": []},
        }
        for name, doc in files.items():
            (self.work / name).write_text(json.dumps(doc), encoding="utf-8")
        self._write_freshness()

    def _write_freshness(self):
        (self.work / "github-freshness.json").write_text(json.dumps(
            {"errors": 0, "partial_errors": 0, "repositories": self.repositories}), encoding="utf-8")

    def _argv(self, *extra):
        return ["--work-dir", str(self.work), "--lanes", str(self.work / "lanes.json"),
                "--reconciliations", str(self.work / "reconciliations.json"),
                "--out", str(self.work / "manifest-20261002.json"),
                "--trading-freshness-out", str(self.work / "trading-freshness.json"),
                "--checked-at", CHECKED_AT, "--id", "catalog-freshness-20261002", *extra]

    def _build(self, *extra):
        # stderr is captured too, so a test can show that the matched text reaches neither stream.
        with redirect_stdout(StringIO()) as stdout, redirect_stderr(StringIO()) as stderr:
            self.assertEqual(build_manifest.main(self._argv(*extra)), 0)
        self.stderr = stderr.getvalue()
        return stdout.getvalue()

    def _written(self):
        return tuple((self.work / name).read_bytes() for name in ("manifest-20261002.json", "trading-freshness.json"))

    def _text(self):
        return (self.work / "drift.md").read_text(encoding="utf-8")

    def _status(self):
        return (self.work / "drift-status.txt").read_text(encoding="utf-8")

    def test_the_fixture_trips_the_gate_in_the_runtime_rows(self):
        runtime = build_manifest.build_runtime_freshness(self.runtime_pins, self.repositories, CHECKED_AT)
        with self.assertRaises(build_manifest.LeakDetected):
            build_manifest.assert_no_leak(json.dumps(runtime, indent=1))

    def test_a_tripped_gate_withholds_only_the_runtime_sidecar(self):
        self._build()
        without = self._written()
        output = self._build("--runtime-freshness-out", str(self.work / fp.RUNTIME_FRESHNESS_FILE))
        # The build exited 0 (see _build); the manifest and the trading sidecar exist, unchanged.
        self.assertEqual(self._written(), without)
        self.assertEqual(output.splitlines()[-1], '{"runtime_freshness": {"gate_error": "leak_gate_tripped"}}')
        # Neither the matched text nor the exception message is printed or logged.
        self.assertNotIn("APCA", output + self.stderr)
        self.assertNotIn("still contains", output + self.stderr)
        text = (self.work / fp.RUNTIME_FRESHNESS_FILE).read_text(encoding="utf-8")
        self.assertNotIn("APCA", text)
        sidecar = json.loads(text)
        self.assertEqual((sidecar["gate_error"], sidecar["entries"], set(sidecar["counts"].values())),
                         ("leak_gate_tripped", [], {0}))
        # The same schema and keys as an empty runtime document, plus the fixed gate_error.
        expected = build_manifest.build_runtime_freshness(None, {}, CHECKED_AT)
        expected["gate_error"] = build_manifest.RUNTIME_LEAK_GATE_ERROR
        self.assertEqual(sidecar, expected)

    def _assert_fatal(self):
        # Only the runtime stage catches LeakDetected; an earlier stage's leak still fails the build.
        with redirect_stdout(StringIO()), self.assertRaises(build_manifest.LeakDetected):
            build_manifest.main(self._argv("--runtime-freshness-out", str(self.work / fp.RUNTIME_FRESHNESS_FILE)))
        self.assertFalse((self.work / fp.RUNTIME_FRESHNESS_FILE).exists())

    def test_a_leak_in_the_manifest_stays_fatal(self):
        self.repositories["https://github.com/example/current"]["latest_release"]["tag"] = "v2.0.0-APCA"
        self._write_freshness()
        self._assert_fatal()
        self.assertFalse((self.work / "manifest-20261002.json").exists())

    def test_a_leak_in_the_trading_sidecar_stays_fatal(self):
        (self.work / "trading-pins.json").write_text(json.dumps({"entries": [
            {"id": "leaky-pin", "layer": "backtesting-engine", "repository": LEAKY_REPOSITORY, "pin": "v0.9.0",
             "pin_source": None},
        ]}), encoding="utf-8")
        self._assert_fatal()
        self.assertFalse((self.work / "trading-freshness.json").exists())

    def test_the_report_says_the_table_was_withheld_and_keeps_drift_status(self):
        self._build("--runtime-freshness-out", str(self.work / fp.RUNTIME_FRESHNESS_FILE))
        sidecar = self.work / fp.RUNTIME_FRESHNESS_FILE
        withheld = sidecar.read_bytes()
        rebuilt_text = (self.work / "manifest-20261002.json").read_text(encoding="utf-8")
        for published_pin, drifted in ((None, []), ("0.0.1", ["engine"])):
            with self.subTest(published_pin=published_pin):
                published = json.loads(rebuilt_text)
                engines = [entry for group in published["trading"] for entry in group["entries"]
                           if entry["id"] == "engine"]
                self.assertEqual(len(engines), 1)
                if published_pin is not None:
                    engines[0]["pin"] = published_pin
                (self.published_dir / "manifest-20260929.json").write_text(json.dumps(published), encoding="utf-8")
                sidecar.unlink()
                without = fp.build_drift_report(self.work)
                observed = [(self._status(), fp.drifted_component_ids(self._text()), without["drifted"])]
                sidecar.write_bytes(withheld)
                result = fp.build_drift_report(self.work)
                text = self._text()
                observed.append((self._status(), fp.drifted_component_ids(text), result["drifted"]))
                self.assertEqual(observed[0], observed[1])
                self.assertEqual(observed[1][1], drifted)
                self.assertIn(fp.RUNTIME_TABLE_HEADING + "\n\n" + fp.RUNTIME_WITHHELD_LINE + "\n", text)
                self.assertNotIn(fp.RUNTIME_TABLE_HEADER, text)
                self.assertNotIn("APCA", text)
                self.assertEqual({key: result[key] for key in fp.RUNTIME_SUMMARY_KEYS},
                                 {**{key: [] for key in fp.RUNTIME_SUMMARY_KEYS},
                                  "runtime_unresolved": ["leak_gate_tripped"]})


class WorkflowWiresTheRuntimeTableTests(unittest.TestCase):
    def setUp(self):
        self.text = WORKFLOW.read_text(encoding="utf-8")

    def test_build_step_writes_the_runtime_sidecar(self):
        self.assertRegex(self.text, r'--runtime-freshness-out "\$RUNNER_TEMP/freshness/runtime-freshness\.json"')

    def test_artifact_retains_the_runtime_sidecar(self):
        self.assertIn("${{ runner.temp }}/freshness/runtime-freshness.json", self.text)

    def test_diff_step_prints_the_runtime_counts(self):
        for key in ("runtime", "runtime_behind", "runtime_unresolved"):
            with self.subTest(key=key):
                self.assertRegex(self.text, rf"{key}=\{{len\(result\['{key}'\]\)\}}")


if __name__ == "__main__":
    unittest.main()
