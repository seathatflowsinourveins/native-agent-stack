"""Native unittest shard CLI fixtures; never run the repository's full suite."""

import json
import importlib.util
from collections import Counter
from itertools import permutations
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/validate_shards.py"


class ShardCliFixtures(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="validate-shards-fixture-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.pkg = self.root / "suitepkg"
        self.pkg.mkdir()
        (self.pkg / "__init__.py").write_text("")
        self.reports = self.root / "reports"

    def write(self, name, text):
        (self.pkg / name).write_text(text, encoding="utf-8")

    def commit(self):
        for argv in (["git", "init", "-q"], ["git", "add", "."],
                     ["git", "-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid",
                      "commit", "-qm", "fixture"]):
            subprocess.run(argv, cwd=self.root, check=True, capture_output=True)

    def cli(self, *args):
        return subprocess.run([sys.executable, "-B", str(SCRIPT), *args],
                              cwd=self.root, env=dict(os.environ), capture_output=True,
                              text=True, timeout=20)

    def run_shards(self, shards=2):
        rows = []
        for shard in range(shards):
            path = self.reports / f"shard-{shard}" / "report.json"
            result = self.cli("run", "--shard", str(shard), "--shards", str(shards),
                              "--report", str(path), "-v", "--durations", "50")
            rows.append((result, json.loads(path.read_text())))
        return rows

    def finish(self, shards=2, result="success"):
        return self.cli("aggregate", "--reports", str(self.reports), "--shards", str(shards),
                        "--job-result", result, "--summary", str(self.root / "summary.md"))

    def simple(self, body="pass"):
        self.write("test_simple.py", f"import unittest\nclass Example(unittest.TestCase):\n def test_one(self): {body}\n")
        self.commit()

    def test_class_fixture_skip_preserves_native_zero_started_count(self):
        self.write("test_class_skip.py", "import unittest\nclass Example(unittest.TestCase):\n @classmethod\n def setUpClass(cls): raise unittest.SkipTest('fixture class skip')\n def test_a(self): self.fail('must not run')\n def test_b(self): self.fail('must not run')\n")
        self.commit()
        self.assertTrue(all(result.returncode == 0 for result, _ in self.run_shards()))
        self.assertEqual(self.finish().returncode, 0)
        receipt = json.loads((self.reports / "aggregate.json").read_text())
        self.assertEqual(receipt["counts"]["ran"], 0)
        self.assertEqual(receipt["counts"]["skipped"], 1)
        self.assertEqual(sum(receipt["scheduled_case_id_counts"].values()), 2)
        self.assertEqual(receipt["case_id_counts"], {})

    def test_package_load_tests_nested_discovery_keeps_one_package_owner(self):
        (self.pkg / "__init__.py").write_text(
            "from pathlib import Path\n"
            "def load_tests(loader, tests, pattern):\n"
            " return loader.discover(str(Path(__file__).parent), pattern=pattern)\n")
        self.write("test_leaf.py", "import unittest\nclass Leaf(unittest.TestCase):\n def test_once(self): pass\n")
        self.commit()
        rows = self.run_shards()
        self.assertTrue(all(result.returncode == 0 for result, _ in rows))
        self.assertEqual(self.finish().returncode, 0)
        receipt = json.loads((self.reports / "aggregate.json").read_text())
        self.assertEqual(receipt["executed_modules"], ["suitepkg"])
        self.assertEqual(receipt["discovered_modules"], 1)
        self.assertEqual(receipt["counts"]["ran"], 1)
        self.assertEqual(receipt["case_id_counts"], {"suitepkg.test_leaf.Leaf.test_once": 1})

    def test_native_import_skip_has_an_owner_and_is_not_dropped(self):
        self.write("test_import_skip.py", "import unittest\nraise unittest.SkipTest('fixture import skip')\n")
        self.commit()
        self.assertTrue(all(result.returncode == 0 for result, _ in self.run_shards()))
        self.assertEqual(self.finish().returncode, 0)
        receipt = json.loads((self.reports / "aggregate.json").read_text())
        self.assertEqual(receipt["executed_modules"], ["suitepkg", "suitepkg.test_import_skip"])
        self.assertEqual(receipt["counts"]["skipped"], 1)

    def test_failed_native_test_counts_remain_visible_in_failed_aggregate(self):
        self.simple("self.fail('fixture failure')")
        rows = self.run_shards()
        self.assertTrue(any(result.returncode == 1 for result, _ in rows))
        self.assertEqual(self.finish(result="failure").returncode, 1)
        receipt = json.loads((self.reports / "aggregate.json").read_text())
        self.assertFalse(receipt["success"])
        self.assertTrue(receipt["counts_complete"])
        self.assertEqual(receipt["counts"]["ran"], 1)
        self.assertEqual(receipt["counts"]["failures"], 1)
        self.assertIn("failures=1", (self.root / "summary.md").read_text())

    def test_import_error_cannot_pass_and_its_native_error_count_is_retained(self):
        self.write("test_broken_import.py", "raise ImportError('fixture import failure')\n")
        self.commit()
        rows = self.run_shards()
        self.assertTrue(any(result.returncode == 1 for result, _ in rows))
        self.assertEqual(self.finish(result="failure").returncode, 1)
        receipt = json.loads((self.reports / "aggregate.json").read_text())
        self.assertEqual(receipt["counts"]["errors"], 1)

    def test_missing_report_and_failed_needs_states_never_pass(self):
        self.simple()
        self.run_shards()
        for result in ["failure", "cancelled", "skipped", "unknown"]:
            with self.subTest(result=result):
                self.assertEqual(self.finish(result=result).returncode, 1)
        (self.reports / "shard-1/report.json").unlink()
        self.assertEqual(self.finish().returncode, 1)
        receipt = json.loads((self.reports / "aggregate.json").read_text())
        self.assertFalse(receipt["counts_complete"])
        self.assertEqual(receipt["unknown_count_shards"], [1])

    def test_duplicate_receipt_is_not_counted_twice_or_accepted(self):
        self.simple()
        self.run_shards()
        duplicate = self.reports / "extra/report.json"
        duplicate.parent.mkdir()
        duplicate.write_text((self.reports / "shard-0/report.json").read_text())
        self.assertEqual(self.finish().returncode, 1)
        receipt = json.loads((self.reports / "aggregate.json").read_text())
        self.assertIn(0, receipt["unknown_count_shards"])
        self.assertEqual(receipt["counts"]["ran"], 0)

    def test_receipt_corruption_is_detected_at_the_public_aggregate_boundary(self):
        self.simple()
        rows = self.run_shards()
        path = next(self.reports / f"shard-{row['shard']}/report.json"
                    for _, row in rows if row["counts"]["ran"])
        original = path.read_text()
        corruptions = [lambda row: row.pop("inventory"),
                       lambda row: row.update(executed_modules=[]),
                       lambda row: row["counts"].update(ran=0),
                       lambda row: row["counts"].update(skipped=True),
                       lambda row: row.update(head_commit="0" * 40),
                       lambda row: row.update(elapsed_seconds=float("nan"))]
        for mutate in corruptions:
            with self.subTest(mutation=mutate):
                row = json.loads(original)
                mutate(row)
                path.write_text(json.dumps(row))
                self.assertEqual(self.finish().returncode, 1)
        path.write_text(original)
        self.assertEqual(self.finish().returncode, 0)

    def test_empty_shards_are_explicit_noops_but_empty_native_discovery_fails(self):
        self.simple()
        rows = self.run_shards(8)
        self.assertEqual(sum(row["counts"]["ran"] for _, row in rows), 1)
        self.assertTrue(all(result.returncode == 0 for result, _ in rows))
        self.assertEqual(self.finish(8).returncode, 0)
        (self.pkg / "test_simple.py").unlink()
        self.commit()
        empty_rows = self.run_shards(8)
        self.assertTrue(all(result.returncode == 1 for result, _ in empty_rows))
        self.assertTrue(all(row["counts"]["ran"] == 0 for _, row in empty_rows))
        self.assertTrue(all("native discovery loaded no tests" in row["errors"] for _, row in empty_rows))
        self.assertEqual(self.finish(8).returncode, 1)
        receipt = json.loads((self.reports / "aggregate.json").read_text())
        self.assertFalse(receipt["success"])
        self.assertTrue(receipt["counts_complete"])
        self.assertEqual(receipt["counts"]["ran"], 0)


    def test_native_hook_imported_cases_and_module_union_keep_multiplicity(self):
        self.write("test_alpha.py", "import unittest\nclass Example(unittest.TestCase):\n def test_pass(self): pass\n")
        self.write("test_alias.py", "from suitepkg.test_alpha import Example\n")
        self.write("support.py", "import unittest\nclass HookCase(unittest.TestCase):\n @unittest.skip('fixture skip')\n def test_skip(self): pass\n")
        self.write("test_hook.py", "from suitepkg.support import HookCase\ndef load_tests(loader, tests, pattern):\n return loader.loadTestsFromTestCase(HookCase)\n")
        self.commit()
        rows = self.run_shards()
        self.assertTrue(all(result.returncode == 0 for result, _ in rows),
                        [(result.returncode, result.stderr) for result, _ in rows])
        summary = self.root / "summary.md"
        aggregate = self.cli("aggregate", "--reports", str(self.reports), "--shards", "2",
                             "--job-result", "success", "--summary", str(summary))
        self.assertEqual(aggregate.returncode, 0, aggregate.stderr)
        receipt = json.loads((self.reports / "aggregate.json").read_text())
        self.assertEqual(receipt["counts"]["ran"], 3)
        self.assertEqual(receipt["counts"]["skipped"], 1)
        self.assertEqual(receipt["executed_modules"], ["suitepkg", "suitepkg.test_alias", "suitepkg.test_alpha", "suitepkg.test_hook"])
        self.assertEqual(receipt["case_id_counts"]["suitepkg.test_alpha.Example.test_pass"], 2)


class PlannerProperties(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("validate_shards_fixture_api", SCRIPT)
        cls.api = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.api)

    def test_small_exhaustive_assignments_cover_once_and_ignore_input_order(self):
        for modules in range(1, 5):
            rows = [{"module": f"fixture_{n}", "case_count": n % 2,
                     "origins": [f"origin_{n}"] if n % 2 else []} for n in range(modules)]
            for shards in range(1, 5):
                for weights in [{}, {row["module"]: 0 for row in rows}, {row["module"]: 5 for row in rows}]:
                    expected = self.api.assignment(rows, shards, weights, 10)
                    self.assertEqual(Counter(expected[0].keys()), Counter({row["module"]: 1 for row in rows}))
                    self.assertTrue(all(0 <= slot < shards for slot in expected[0].values()))
                    for ordering in permutations(rows):
                        self.assertEqual(self.api.assignment(ordering, shards, weights, 10), expected)

    def test_unknown_new_module_is_present_without_editing_weights(self):
        rows = [{"module": "known", "case_count": 1, "origins": ["known"]},
                {"module": "new_unknown", "case_count": 1, "origins": ["new_unknown"]}]
        mapping, _, _ = self.api.assignment(rows, 8, {"known": 25}, 10)
        self.assertEqual(set(mapping), {"known", "new_unknown"})

    def test_shared_native_fixture_origins_preserve_global_serial_order(self):
        rows = [{"module": "owner_a", "case_count": 1, "origins": ["shared"]},
                {"module": "owner_b", "case_count": 1, "origins": ["shared"]}]
        mapping, strategy, constraints = self.api.assignment(rows, 8, {}, 10)
        self.assertEqual(mapping, {"owner_a": 0, "owner_b": 0})
        self.assertEqual(strategy, "serial-native-fixture-fallback")
        self.assertEqual(constraints, {"shared": ["owner_a", "owner_b"]})



if __name__ == "__main__":
    unittest.main()
