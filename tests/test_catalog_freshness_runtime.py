"""GPT runtime coverage for the report-only catalog-freshness path.

Covers each stage the GPT runtime workers, SDKs and agents pass through:
- extract: tools/sota-convergence/extract_layers.py resolves RUNTIME_PIN_SOURCES
  (the pins that the new-WSL install plan, the runtime-worker recipe pin record and
  the native SDK constraints carry) and lists RUNTIME_WATCH_SOURCES (watch-only
  upstreams with no pin record on main, such as pi) into runtime-pins.json. A
  record that moved does not raise; its entry carries an error instead.
- fetch: github_freshness.py reads repository URLs from runtime-pins.json too.
- build: build_manifest.py's build_runtime_freshness (fixed dates, no wall clock)
  and its --runtime-freshness-out flag, which leaves the manifest and the trading
  sidecar byte-identical.
- report: scripts/freshness_propose.py renders the runtime table into drift.md
  without touching drift-status.txt or the drift-table ids the propose job reads.

No network. The extraction tests read the checked-in repository; every other
test uses synthetic fixtures.
"""
from __future__ import annotations

import ast
import importlib.util
import json
import os
import re
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from scripts import freshness_propose as fp

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
                rows = [row for row in plan["owners"] if row.get("slot") == slot]
                self.assertEqual(len(rows), 1)
                repository, release = rows[0]["repository"], rows[0]["release"]
                if entry_id in RESEARCH_HARNESS_PARTS:
                    position, slug = RESEARCH_HARNESS_PARTS[entry_id]
                    repositories = [part.strip() for part in repository.split(";")]
                    releases = [part.strip() for part in release.split(";")]
                    self.assertEqual((len(repositories), len(releases)), (2, 2))
                    self.assertEqual(github_freshness.github_slug(repositories[position]), slug)
                    repository, release = repositories[position], releases[position]
                entry = self.entries[entry_id]
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
                    "named_in": source["named_in"], "error": None,
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
                                      "openai-codex-cli-bin==1.2.3\ndup==1.0\nDup==2.0\n")

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
            "named_in": None, "error": None,
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
            "named_in": "docs/x.md", "error": None,
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


class GithubFreshnessReadsRuntimePinsTests(unittest.TestCase):
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


MOVED_ERROR = "plan/install-plan.json#/owners slot 'gpt-gateway': 0 rows match, expected exactly one"


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
        self.assertEqual(result["runtime_unfetched"], ["new-wsl:behind", "new-wsl:moved"])
        self.assertEqual(self._cells("new-wsl:behind").count(fp.md_cell("unknown")), 3)
        self.assertIn("2 runtime row(s) with no reliable upstream data this run:", self._text())

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
