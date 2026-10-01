"""Trading-layer coverage for the report-only catalog-freshness path (roadmap R23).

Covers each stage the trading components pass through:
- extract: tools/sota-convergence/extract_layers.py resolves TRADING_PIN_SOURCES
  (trading pins that no selected catalogs/us-equities card carries, such as
  hftbacktest) into trading-pins.json. The selected cards stay in
  trading-by-layer.json.
- fetch: github_freshness.py reads repository URLs from trading-pins.json too.
- build: build_manifest.py's build_trading_freshness/compute_dormancy (fixed
  dates, no wall clock) and its --trading-freshness-out flag.
- report: scripts/freshness_propose.py renders the trading table into drift.md
  without touching drift-status.txt or the drift-table ids the propose job reads.

No network. The extraction tests read the checked-in repository; every other
test uses synthetic fixtures.
"""
from __future__ import annotations

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


def load_module(name, filename):
    spec = importlib.util.spec_from_file_location(name, TOOL_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


extract_layers = load_module("extract_layers_trading", "extract_layers.py")
build_manifest = load_module("build_manifest_trading", "build_manifest.py")
github_freshness = load_module("github_freshness_trading", "github_freshness.py")

# The selected trading components R23 names that live on catalogs/us-equities cards
# (card ids, not manifests/stack.json ids).
SELECTED_CARD_IDS = {
    "nautilustrader", "nautilus-ibkr-adapter", "alpaca-py", "lean", "data-edgartools",
    "skfolio", "data-exchange-calendars", "data-databento",
}


def _hftbacktest_record(**overrides):
    """Shaped like github_freshness.fetch_repository's output for
    nkaz001/hftbacktest as observed on 2026-09-25 (dormant since 2025-12-23)."""
    record = {
        "slug": "nkaz001/hftbacktest", "pushed_at": "2025-12-23T15:57:58Z", "archived": False,
        "latest_release": {"tag": "rust-v0.9.4", "published_at": "2025-12-10T09:00:00Z", "prerelease": False},
        "head": {"sha": "5f3ec40b2afb", "date": "2025-12-23T15:31:05Z"},
    }
    record.update(overrides)
    return record


class ExtractionIncludesTradingTests(unittest.TestCase):
    """Runs extract_layers.main() against the checked-in catalogs."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls._tmp.name)
        with redirect_stdout(StringIO()) as stdout:
            rc = extract_layers.main(["--repo-root", str(ROOT), "--out", str(cls.out)])
        assert rc == 0
        cls.summary = json.loads(stdout.getvalue().splitlines()[0])

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def _load(self, name):
        return json.loads((self.out / name).read_text(encoding="utf-8"))

    def test_selected_trading_cards_reach_trading_by_layer(self):
        by_layer = self._load("trading-by-layer.json")
        selected = {entry["id"] for entries in by_layer["layers"].values() for entry in entries
                    if entry.get("decision") in build_manifest.SELECTED_TRADING_DECISIONS}
        self.assertLessEqual(SELECTED_CARD_IDS, selected)

    def test_off_card_trading_pins_are_extracted(self):
        pins = {entry["id"]: entry for entry in self._load("trading-pins.json")["entries"]}
        self.assertLessEqual({"hftbacktest", "nautilus-ibapi"}, set(pins))
        self.assertEqual(self.summary["trading_pins"], sorted(pins))
        self.assertEqual(pins["hftbacktest"]["repository"], "https://github.com/nkaz001/hftbacktest")
        self.assertEqual(pins["hftbacktest"]["layer"], "backtesting-engine")

    def test_every_declared_pin_matches_its_source_record(self):
        taxonomy = self._load("trading-by-layer.json")["taxonomy"]
        pins = {entry["id"]: entry for entry in self._load("trading-pins.json")["entries"]}
        for source in extract_layers.TRADING_PIN_SOURCES:
            with self.subTest(pin=source["id"]):
                doc = json.loads((ROOT / source["path"]).read_text(encoding="utf-8"))
                entry = pins[source["id"]]
                self.assertEqual(entry["pin"], extract_layers.resolve_json_pointer(doc, source["pin_pointer"]))
                self.assertIn(entry["layer"], taxonomy)
                self.assertIsNotNone(github_freshness.github_slug(entry["repository"]))

    def test_no_declared_pin_duplicates_a_selected_card_repository(self):
        # A pin that a selected card already carries would be listed twice.
        catalog = self._load("trading-catalog.json")
        card_slugs = {github_freshness.github_slug(entry.get("repository")) for entry in catalog["entries"]
                      if entry.get("decision") in build_manifest.SELECTED_TRADING_DECISIONS}
        for entry in self._load("trading-pins.json")["entries"]:
            self.assertNotIn(github_freshness.github_slug(entry["repository"]), card_slugs, entry["id"])

    def test_fetch_step_collects_the_trading_repositories(self):
        urls = github_freshness.collect_repository_urls(self.out)
        self.assertIn("https://github.com/nkaz001/hftbacktest", urls)
        self.assertIn("https://github.com/nautechsystems/nautilus_trader", urls)


class ResolveTradingPinsTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        (self.root / "records").mkdir()
        (self.root / "records/receipt.json").write_text(json.dumps({
            "upstream": {"source_url": "https://github.com/example/engine", "pinned_version": "2.4.4"},
            "boundaries": [{"id": "ibkr", "pin": "=3.3.0"}],
        }), encoding="utf-8")

    def _source(self, **overrides):
        source = {"id": "engine", "layer": "backtesting-engine", "path": "records/receipt.json",
                  "repository_pointer": "/upstream/source_url", "pin_pointer": "/upstream/pinned_version"}
        source.update(overrides)
        return source

    def test_resolves_pin_and_repository_from_the_record(self):
        result = extract_layers.resolve_trading_pins(self.root, sources=(self._source(),))
        self.assertEqual(result["entries"], [{
            "id": "engine", "layer": "backtesting-engine", "repository": "https://github.com/example/engine",
            "pin": "2.4.4", "pin_source": {"path": "records/receipt.json", "pointer": "/upstream/pinned_version"},
            "repository_source": {"path": "records/receipt.json", "pointer": "/upstream/source_url"},
        }])

    def test_literal_repository_and_list_index_pointer(self):
        source = self._source(repository_pointer=None, repository="https://github.com/example/rust",
                              pin_pointer="/boundaries/0/pin")
        entry = extract_layers.resolve_trading_pins(self.root, sources=(source,))["entries"][0]
        self.assertEqual((entry["repository"], entry["pin"], entry["repository_source"]),
                         ("https://github.com/example/rust", "=3.3.0", None))

    def test_unresolvable_pointer_raises_instead_of_dropping(self):
        with self.assertRaisesRegex(ValueError, "engine"):
            extract_layers.resolve_trading_pins(self.root, sources=(self._source(pin_pointer="/upstream/gone"),))

    def test_missing_source_file_raises(self):
        with self.assertRaisesRegex(ValueError, "engine"):
            extract_layers.resolve_trading_pins(self.root, sources=(self._source(path="records/absent.json"),))

    def test_non_string_pin_raises(self):
        with self.assertRaisesRegex(ValueError, "pin is not a non-empty string"):
            extract_layers.resolve_trading_pins(self.root, sources=(self._source(pin_pointer="/upstream"),))

    def test_layer_outside_the_taxonomy_raises(self):
        with self.assertRaisesRegex(ValueError, "not a taxonomy layer"):
            extract_layers.resolve_trading_pins(self.root, sources=(self._source(layer="nowhere"),),
                                                taxonomy={"backtesting-engine": []})

    def test_id_colliding_with_a_card_raises(self):
        with self.assertRaisesRegex(ValueError, "duplicates"):
            extract_layers.resolve_trading_pins(self.root, sources=(self._source(),), card_ids={"engine"})

    def test_path_escaping_the_repository_raises(self):
        for path in ("../outside.json", "/etc/passwd"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                extract_layers.resolve_trading_pins(self.root, sources=(self._source(path=path),))

    def test_json_pointer_unescapes_rfc6901_tokens(self):
        doc = {"a/b": {"c~d": [10, 20]}}
        self.assertEqual(extract_layers.resolve_json_pointer(doc, "/a~1b/c~0d/1"), 20)
        with self.assertRaises(KeyError):
            extract_layers.resolve_json_pointer(doc, "/a~1b/c~0d/2")


class GithubFreshnessReadsTradingPinsTests(unittest.TestCase):
    def test_trading_pins_repositories_are_collected_and_the_file_is_optional(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            (work / "trading-catalog.json").write_text(json.dumps(
                {"entries": [{"repository": "https://github.com/example/card"}]}), encoding="utf-8")
            self.assertEqual(github_freshness.collect_repository_urls(work), {"https://github.com/example/card"})
            (work / "trading-pins.json").write_text(json.dumps(
                {"entries": [{"repository": "https://github.com/example/pinned"}]}), encoding="utf-8")
            self.assertEqual(github_freshness.collect_repository_urls(work),
                             {"https://github.com/example/card", "https://github.com/example/pinned"})


class ComputeDormancyTests(unittest.TestCase):
    AS_OF = "2026-09-25"

    def test_hftbacktest_is_dormant_since_its_last_commit(self):
        result = build_manifest.compute_dormancy(_hftbacktest_record(), self.AS_OF)
        self.assertIs(result["dormant"], True)
        self.assertEqual(result["last_activity_at"], "2025-12-23")
        self.assertEqual(result["last_release_at"], "2025-12-10")
        self.assertEqual(result["days_since_activity"], 276)
        self.assertEqual(result["basis"], "release_or_default_branch_commit")

    def test_threshold_boundary_is_inclusive_at_180_days(self):
        # 2026-03-29 is 180 days before 2026-09-25; 2026-03-30 is 179.
        at_threshold = _hftbacktest_record(latest_release=None, head={"date": "2026-03-29T00:00:00Z"})
        below = _hftbacktest_record(latest_release=None, head={"date": "2026-03-30T00:00:00Z"})
        self.assertEqual(build_manifest.compute_dormancy(at_threshold, self.AS_OF)["days_since_activity"], 180)
        self.assertIs(build_manifest.compute_dormancy(at_threshold, self.AS_OF)["dormant"], True)
        self.assertIs(build_manifest.compute_dormancy(below, self.AS_OF)["dormant"], False)

    def test_a_recent_release_alone_keeps_an_upstream_active(self):
        record = _hftbacktest_record(latest_release={"tag": "v1", "published_at": "2026-09-01T00:00:00Z"})
        result = build_manifest.compute_dormancy(record, self.AS_OF)
        self.assertIs(result["dormant"], False)
        self.assertEqual(result["last_activity_at"], "2026-09-01")

    def test_pushed_at_stands_in_only_when_the_commit_date_is_unknown(self):
        record = _hftbacktest_record(head=None, pushed_at="2026-09-20T00:00:00Z")
        result = build_manifest.compute_dormancy(record, self.AS_OF)
        self.assertEqual((result["dormant"], result["basis"]), (False, "release_or_pushed_at"))
        # A recent non-default-branch push does not hide an idle default branch.
        with_head = _hftbacktest_record(pushed_at="2026-09-20T00:00:00Z")
        self.assertIs(build_manifest.compute_dormancy(with_head, self.AS_OF)["dormant"], True)

    def test_unknown_is_null_never_false(self):
        cases = {
            "not_fetched": None,
            "fetch_error": {"error": "HTTP 502"},
            "no_activity_date": {"slug": "example/x", "latest_release": None, "head": None, "pushed_at": None},
        }
        for reason, record in cases.items():
            with self.subTest(reason=reason):
                result = build_manifest.compute_dormancy(record, self.AS_OF)
                self.assertIsNone(result["dormant"])
                self.assertEqual(result["reason"], reason)
        self.assertEqual(build_manifest.compute_dormancy(_hftbacktest_record(), None)["reason"], "no_as_of")

    def test_the_threshold_is_configurable(self):
        result = build_manifest.compute_dormancy(_hftbacktest_record(), self.AS_OF, threshold_days=365)
        self.assertEqual((result["dormant"], result["threshold_days"]), (False, 365))


def _trading_by_layer():
    card = {"id": "engine", "repository": "https://github.com/example/engine", "decision": "default",
            "version_or_commit": "1.0.0"}
    return {
        "taxonomy": {"backtesting-engine": ["backtesting"], "execution-broker": ["broker-adapter"]},
        "layers": {
            "backtesting-engine": [card, {"id": "old-engine", "repository": "https://github.com/example/old",
                                          "decision": "alternative", "version_or_commit": "0.1"}],
            "execution-broker": [card],
        },
    }


def _repositories():
    return {
        "https://github.com/example/engine": {
            "slug": "example/engine", "pushed_at": "2026-09-24T00:00:00Z", "archived": False,
            "latest_release": {"tag": "v1.1.0", "published_at": "2026-09-01T00:00:00Z"},
            "head": {"date": "2026-09-24T00:00:00Z"},
        },
        "https://github.com/nkaz001/hftbacktest": _hftbacktest_record(),
    }


TRADING_PINS = {"entries": [{
    "id": "hftbacktest", "layer": "backtesting-engine", "repository": "https://github.com/nkaz001/hftbacktest",
    "pin": "2.4.4", "pin_source": {"path": "blueprints/x/receipt.json", "pointer": "/upstream/pinned_version"},
}]}


class BuildTradingFreshnessTests(unittest.TestCase):
    def setUp(self):
        self.doc = build_manifest.build_trading_freshness(
            _trading_by_layer(), TRADING_PINS, _repositories(), "2026-09-25")
        self.rows = {row["id"]: row for row in self.doc["entries"]}

    def test_selected_cards_and_off_card_pins_each_get_one_row(self):
        self.assertEqual([row["id"] for row in self.doc["entries"]], ["engine", "hftbacktest"])
        self.assertNotIn("old-engine", self.rows)  # alternative: not the selected baseline
        self.assertEqual(self.rows["engine"]["layers"], ["backtesting-engine", "execution-broker"])
        self.assertEqual(self.rows["engine"]["source"], "catalog_card")
        self.assertEqual(self.rows["hftbacktest"]["source"], "pin_source")
        self.assertEqual(self.rows["hftbacktest"]["pin_source"]["pointer"], "/upstream/pinned_version")

    def test_pin_vs_upstream_uses_the_manifest_rule(self):
        self.assertEqual((self.rows["engine"]["upstream"]["latest"], self.rows["engine"]["pin_behind_upstream"],
                          self.rows["engine"]["pin_comparison"]), ("v1.1.0", True, "compared"))

    def test_dormancy_and_counts(self):
        self.assertIs(self.rows["hftbacktest"]["dormancy"]["dormant"], True)
        self.assertIs(self.rows["engine"]["dormancy"]["dormant"], False)
        self.assertEqual(self.doc["counts"], {
            "entries": 2, "catalog_card": 1, "pin_source": 1, "pin_behind_upstream": 1,
            "dormant": 1, "dormancy_unknown": 0, "archived": 0,
        })
        self.assertEqual((self.doc["schema"], self.doc["checked_at"], self.doc["dormancy_threshold_days"]),
                         ("trading-freshness/1", "2026-09-25", 180))

    def test_a_pin_id_equal_to_a_card_id_raises(self):
        pins = {"entries": [dict(TRADING_PINS["entries"][0], id="engine")]}
        with self.assertRaises(ValueError):
            build_manifest.build_trading_freshness(_trading_by_layer(), pins, _repositories(), "2026-09-25")

    def test_without_trading_pins_only_cards_are_listed(self):
        doc = build_manifest.build_trading_freshness(_trading_by_layer(), None, _repositories(), "2026-09-25")
        self.assertEqual([row["id"] for row in doc["entries"]], ["engine"])


class BuildManifestTradingFreshnessCliTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.work = Path(self._tmp.name)
        files = {
            "foundation-layers.json": {"checked_at": "2026-09-25", "layers": [], "top_gaps": []},
            "trading-by-layer.json": _trading_by_layer(),
            "github-freshness.json": {"repositories": _repositories()},
            "trading-pins.json": TRADING_PINS,
            "lanes.json": {"lanes": [], "critic": None, "lost": []},
            "reconciliations.json": {"reconciliations": []},
        }
        for name, doc in files.items():
            (self.work / name).write_text(json.dumps(doc), encoding="utf-8")

    def _run(self, *extra):
        argv = ["--work-dir", str(self.work), "--lanes", str(self.work / "lanes.json"),
                "--reconciliations", str(self.work / "reconciliations.json"),
                "--out", str(self.work / "manifest-20260925.json"),
                "--checked-at", "2026-09-25", "--id", "catalog-freshness-20260925", *extra]
        with redirect_stdout(StringIO()):
            return build_manifest.main(argv)

    def test_flag_writes_the_sidecar_and_leaves_the_manifest_layout_alone(self):
        self.assertEqual(self._run("--trading-freshness-out", str(self.work / "trading-freshness.json")), 0)
        doc = json.loads((self.work / "trading-freshness.json").read_text(encoding="utf-8"))
        self.assertEqual([row["id"] for row in doc["entries"]], ["engine", "hftbacktest"])
        manifest = json.loads((self.work / "manifest-20260925.json").read_text(encoding="utf-8"))
        self.assertNotIn("trading_freshness", manifest)
        self.assertNotIn("hftbacktest", {entry["id"] for layer in manifest["trading"] for entry in layer["entries"]})

    def test_without_the_flag_no_sidecar_is_written(self):
        self.assertEqual(self._run(), 0)
        self.assertFalse((self.work / "trading-freshness.json").exists())


class TradingReportTests(unittest.TestCase):
    """build_drift_report() with a trading-freshness.json in the work dir."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        base = Path(self._tmp.name)
        self.work = base / "work"
        self.work.mkdir()
        published_dir = base / "catalogs" / "sota-convergence"
        published_dir.mkdir(parents=True)
        original = Path.cwd()
        os.chdir(base)
        self.addCleanup(os.chdir, original)
        self.repositories = _repositories()
        self._write_freshness(self.repositories)
        self._write_manifest(published_dir / "manifest-20260923.json", "8.30.0")
        self._write_manifest(self.work / "manifest-20260925.json", "8.30.0")

    def _write_freshness(self, repositories, partial_errors=0):
        (self.work / "github-freshness.json").write_text(json.dumps(
            {"errors": 0, "partial_errors": partial_errors, "repositories": repositories}), encoding="utf-8")

    def _write_manifest(self, path, pin):
        row = {"id": "gitleaks", "pin": pin, "repository": "https://github.com/gitleaks/gitleaks",
               "upstream": {"latest": "v8.30.1", "pushed_at": "2026-09-20"}, "pin_behind_upstream": True}
        path.write_text(json.dumps({"foundation": [{"components": [row]}], "trading": [], "counts": {}}),
                        encoding="utf-8")

    def _write_trading(self):
        doc = build_manifest.build_trading_freshness(
            _trading_by_layer(), TRADING_PINS, self.repositories, "2026-09-25")
        (self.work / fp.TRADING_FRESHNESS_FILE).write_text(json.dumps(doc), encoding="utf-8")

    def _row(self, text, row_id):
        return next(line for line in text.splitlines() if line.startswith(f"| {fp.md_cell(row_id)} |"))

    def test_table_lists_every_trading_row_with_dormancy(self):
        self._write_trading()
        result = fp.build_drift_report(self.work)
        text = (self.work / "drift.md").read_text(encoding="utf-8")
        self.assertIn(fp.TRADING_TABLE_HEADING, text)
        self.assertIn(fp.TRADING_TABLE_HEADER + "\n" + fp.TRADING_TABLE_SEPARATOR, text)
        cells = [cell.strip() for cell in self._row(text, "hftbacktest").strip("|").split(" | ")]
        self.assertEqual(cells, [fp.md_cell(v) for v in (
            "hftbacktest", "backtesting-engine", "2.4.4", "rust-v0.9.4", "no", "2025-12-10", "2025-12-23",
            276, "yes", "no")])
        self.assertIn(fp.md_cell("yes"), self._row(text, "engine"))  # behind
        self.assertEqual(result["trading"], ["engine", "hftbacktest"])
        self.assertEqual(result["dormant"], ["hftbacktest"])
        self.assertEqual((result["archived"], result["trading_unfetched"]), ([], []))
        self.assertRegex(text, r"1 dormant upstream\(s\) \(no release or default-branch commit in 180\+ days\)")

    def test_dormant_rows_are_not_drift(self):
        self._write_trading()
        result = fp.build_drift_report(self.work)
        self.assertEqual(result["drifted"], [])
        self.assertEqual((self.work / "drift-status.txt").read_text().strip(), "false")
        self.assertEqual(fp.drifted_component_ids((self.work / "drift.md").read_text()), [])

    def test_propose_reads_only_the_drift_table_ids_when_both_tables_exist(self):
        self._write_manifest(self.work / "manifest-20260925.json", "8.30.1")
        self._write_trading()
        result = fp.build_drift_report(self.work)
        self.assertEqual(result["drifted"], ["gitleaks"])
        self.assertEqual(fp.drifted_component_ids((self.work / "drift.md").read_text()), ["gitleaks"])

    def test_unreliable_fetch_blanks_the_row_instead_of_calling_it_active_or_dormant(self):
        self.repositories["https://github.com/nkaz001/hftbacktest"]["partial_errors"] = {"commit": "HTTP 503"}
        self._write_freshness(self.repositories, partial_errors=1)
        self._write_trading()
        result = fp.build_drift_report(self.work)
        self.assertEqual((result["dormant"], result["trading_unfetched"]), ([], ["hftbacktest"]))
        row = self._row((self.work / "drift.md").read_text(), "hftbacktest")
        self.assertEqual(row.count(fp.md_cell("unknown")), 3)

    def test_archived_upstream_is_listed(self):
        self.repositories["https://github.com/example/engine"]["archived"] = True
        self._write_freshness(self.repositories)
        self._write_trading()
        result = fp.build_drift_report(self.work)
        self.assertEqual(result["archived"], ["engine"])
        self.assertIn("1 archived upstream repository(ies):", (self.work / "drift.md").read_text())

    def test_without_the_sidecar_the_report_is_unchanged(self):
        result = fp.build_drift_report(self.work)
        self.assertNotIn(fp.TRADING_TABLE_HEADING, (self.work / "drift.md").read_text())
        self.assertEqual((result["trading"], result["dormant"]), ([], []))

    def test_malformed_sidecar_fails_closed(self):
        (self.work / fp.TRADING_FRESHNESS_FILE).write_text("{", encoding="utf-8")
        with self.assertRaises(fp.FreshnessProposeError):
            fp.build_drift_report(self.work)


class WorkflowWiresTheTradingTableTests(unittest.TestCase):
    def setUp(self):
        self.text = WORKFLOW.read_text(encoding="utf-8")

    def test_build_step_writes_the_trading_sidecar(self):
        self.assertRegex(self.text, r'--trading-freshness-out "\$RUNNER_TEMP/freshness/trading-freshness\.json"')

    def test_artifact_retains_the_trading_sidecar(self):
        self.assertIn("${{ runner.temp }}/freshness/trading-freshness.json", self.text)

    def test_diff_step_prints_the_dormant_count(self):
        self.assertTrue(re.search(r"dormant=\{len\(result\['dormant'\]\)\}", self.text))


if __name__ == "__main__":
    unittest.main()
