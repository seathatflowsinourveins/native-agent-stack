"""Repository policy fixtures using upstream Git/PyYAML; not upstream acceptance."""
import builtins
from contextlib import redirect_stderr
from datetime import datetime, timezone
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


dm = load("decision_metadata")
currency = load("currency_due")
VALID = {"status": "accepted", "date": "2026-10-05", "decision-makers": ["fixture"],
         "consulted": ["fixture reviewer"], "review_by": "2027-01-03",
         "evidence_class": "synthetic", "overturn_when": "A measured counterexample"}


class DecisionMetadataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="decision-metadata-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.run_git("init", "-b", "main")
        self.put("docs/decisions/2020-01-01-old.md", "old malformed metadata\n")
        self.commit("old baseline")
        self.update_main()

    def run_git(self, *args):
        r = subprocess.run(["git", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                            *args], cwd=self.root, text=True, capture_output=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.strip()

    def put(self, relative, text):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def commit(self, message):
        self.run_git("add", ".")
        self.run_git("commit", "-m", message)
        return self.run_git("rev-parse", "HEAD")

    def update_main(self):
        self.run_git("update-ref", "refs/remotes/origin/main", self.run_git("rev-parse", "HEAD"))

    def land(self):
        self.put(dm.ANCHOR, "anchor grandfathered without metadata\n")
        self.put("docs/decisions/2026-10-05-concurrent.md", "also grandfathered\n")
        sha = self.commit("R5 squash landing")
        self.update_main()
        self.put(dm.INDEX, json.dumps({"schema_version": 1, "baseline": dm.SELECTOR, "records": {}}))
        return sha

    def record(self, data=None, name="docs/decisions/2026-10-06-new.md"):
        # JSON values are valid YAML; the separate raw fixtures exercise native timestamp handling.
        data = VALID if data is None else data
        lines = [f"{k}: {json.dumps(v)}" for k, v in data.items()]
        return self.put(name, "---\n" + "\n".join(lines) + "\n---\n# Fixture\n")

    def test_pending_is_not_success_and_refresh_does_not_create_index(self):
        result = dm.check(self.root, write_index=True)
        self.assertEqual(result["status"], "pending_landing")
        self.assertEqual(dm.exit_code(result), 2)
        self.assertFalse((self.root / dm.INDEX).exists())

    def test_grandfathered_records_are_not_parsed(self):
        self.land()
        with patch.object(dm, "parse_record", side_effect=AssertionError("retrofit")):
            self.assertEqual(dm.check(self.root)["status"], "passed")

    def test_every_required_field_is_required(self):
        for field in dm.FIELDS:
            with self.subTest(field=field):
                data = {k: v for k, v in VALID.items() if k != field}
                with self.assertRaisesRegex(dm.MetadataError, f"missing {field}"):
                    dm.parse_record(self.record(data))

    def test_malformed_frontmatter_and_types(self):
        for text in ["no frontmatter", "---\nstatus: [\n---", "---\nstatus: accepted", "---\n- list\n---"]:
            with self.subTest(text=text), self.assertRaises(dm.MetadataError):
                dm.parse_record(self.put("bad.md", text))
        for field, value in [("status", []), ("date", True), ("consulted", [3]),
                             ("overturn_when", ""), ("evidence_class", "invented")]:
            with self.subTest(field=field), self.assertRaises(dm.MetadataError):
                dm.parse_record(self.record({**VALID, field: value}))

    def test_review_window_date_only_and_native_yaml_date_errors(self):
        self.assertEqual(dm.parse_record(self.record())["review_by"], "2027-01-03")  # 90 days
        for value in ["2027-01-04", "2026-10-04", "2026-02-30", "20261005", "2026-10-05T00:00:00Z"]:
            with self.subTest(value=value), self.assertRaises(dm.MetadataError):
                dm.parse_record(self.record({**VALID, "review_by": value}))
        good = self.record().read_text().replace('"2026-10-05"', "2026-10-05")
        self.assertEqual(dm.parse_record(self.put("raw.md", good))["date"], "2026-10-05")
        for value in ["2026-02-30", "2026-10-05T00:00:00Z"]:
            with self.subTest(raw=value), self.assertRaises(dm.MetadataError):
                dm.parse_record(self.put("raw.md", good.replace("2026-10-05", value)))

    def test_backdated_addition_index_drift_and_later_main_arrival(self):
        landing = self.land()
        path = self.record(name="docs/decisions/1999-01-01-backdated.md")
        result = dm.check(self.root)
        self.assertEqual(result["status"], "invalid")
        self.assertEqual(result["indexed_records"], 1)
        self.assertEqual(dm.check(self.root, write_index=True)["status"], "passed")
        self.assertEqual(dm.check(self.root)["status"], "passed")
        path.write_text("missing required frontmatter\n")
        self.commit("a later main record")
        self.update_main()
        result = dm.check(self.root)
        self.assertEqual(result["baseline"]["landing_sha"], landing)
        self.assertEqual(result["status"], "invalid")
        self.assertIn("backdated", result["errors"][0])

    def test_squash_and_first_parent_merge_include_concurrent_main_tree(self):
        for squash in [True, False]:
            with self.subTest(squash=squash):
                self.run_git("checkout", "-b", f"feature-{squash}")
                self.put(dm.ANCHOR, "feature anchor\n")
                feature = self.commit("feature creates anchor")
                self.run_git("checkout", "main")
                concurrent = f"docs/decisions/2026-10-05-concurrent-{squash}.md"
                self.put(concurrent, "concurrent main decision without metadata\n")
                self.commit("concurrent main")
                self.run_git("merge", "--squash" if squash else "--no-ff", f"feature-{squash}",
                             *([] if squash else ["-m", "merge arrival"]))
                landing = self.commit("squash arrival") if squash else self.run_git("rev-parse", "HEAD")
                self.update_main()
                result = dm.resolve_baseline(self.root)
                self.assertNotEqual(result["landing_sha"], feature)
                self.assertEqual(result["landing_sha"], landing)
                self.assertIn(concurrent, result["paths"])
                # Return to the initial tree for the second independent history case.
                self.run_git("reset", "--hard", self.run_git("rev-list", "--max-parents=0", "HEAD"))

    def test_unknown_ref_shallow_and_failed_tree_read(self):
        self.run_git("update-ref", "-d", "refs/remotes/origin/main")
        self.assertEqual(dm.exit_code(dm.check(self.root)), 3)
        self.update_main()
        self.land()
        original = dm.git
        def failed_tree(root, *args):
            if args[0] == "ls-tree":
                raise dm.MetadataError("fixture tree failure")
            return original(root, *args)
        with patch.object(dm, "git", side_effect=failed_tree):
            self.assertEqual(dm.check(self.root)["status"], "unknown")
        clone = self.root / "shallow"
        self.run_git("clone", "--depth=1", self.root.as_uri(), str(clone))
        self.assertEqual(dm.check(clone)["status"], "unknown")

    def test_currency_index_dates_are_advisory_and_unknown_stays_unknown(self):
        now = datetime(2027, 1, 4, tzinfo=timezone.utc)
        self.assertIsNone(currency.decision_reviews(self.root, now)["overdue_count"])
        self.land()
        self.record()
        dm.check(self.root, write_index=True)
        self.assertEqual(currency.decision_reviews(self.root, now)["overdue_count"], 1)
        self.assertEqual(currency.decision_reviews(self.root, datetime(2027, 1, 3))["overdue_count"], 0)
        self.assertEqual(currency.decision_reviews(self.root, now)["enforcement"], "not_observed")
        snapshot = json.loads((self.root / dm.INDEX).read_text())
        for bad in [{k: v for k, v in snapshot.items() if k != "baseline"},
                    {**snapshot, "baseline": {**dm.SELECTOR, "main_ref": "wrong/main"}}]:
            with self.subTest(bad=bad):
                self.put(dm.INDEX, json.dumps(bad))
                self.assertIsNone(currency.decision_reviews(self.root, now)["overdue_count"])
        for bad in ["bad", "2027-1-3", "2027-02-30", "2027-01-03T00:00:00Z"]:
            with self.subTest(date=bad):
                self.put(dm.INDEX, json.dumps({**snapshot, "records": {"bad": {"review_by": bad}}}))
                self.assertEqual(currency.decision_reviews(self.root, now)["state"], "unknown")

    def test_scan_and_metadata_flags_cannot_skip_the_gate(self):
        validator = load("validate")
        with patch.object(sys, "argv", ["validate.py", "--decision-metadata", "--scan-file", "clean.txt"]), \
             redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            validator.main()
        self.assertEqual(error.exception.code, 2)

    def test_default_validator_and_scan_mode_do_not_import_yaml(self):
        validator = load("validate")
        original = builtins.__import__
        def no_yaml(name, *args, **kwargs):
            if name in {"yaml", "decision_metadata"}:
                raise AssertionError("metadata imported in default mode")
            return original(name, *args, **kwargs)
        with patch("builtins.__import__", side_effect=no_yaml), patch.object(validator, "validate", return_value={}):
            with patch.object(sys, "argv", ["validate.py"]):
                self.assertEqual(validator.main(), 0)
            with patch.object(sys, "argv", ["validate.py", "--scan-file", str(self.put("clean.txt", "clean"))]):
                self.assertEqual(validator.main(), 0)


if __name__ == "__main__":
    unittest.main()
